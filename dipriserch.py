#!/usr/bin/env python3
"""dipriserch — pipeline recherche → document HTML avec widgets Claude."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values, load_dotenv
from duckduckgo_search import DDGS
from openai import OpenAI


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    load_dotenv(dotenv_path=Path(".env"), override=True)
    env = {**dotenv_values(Path(".env"))}
    required = {"LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"}
    missing = required - set(env)
    if missing:
        print(f"[error] Variables .env manquantes : {', '.join(sorted(missing))}", file=sys.stderr)
        sys.exit(1)
    return {
        "base_url": env["LLM_BASE_URL"],
        "model":    env["LLM_MODEL"],
        "api_key":  env["LLM_API_KEY"],
    }


def make_llm_client(cfg: dict) -> OpenAI:
    return OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])


def chat_structured(client: OpenAI, model: str, prompt: str, max_retries: int = 3) -> dict:
    """Appelle le LLM et retourne un dict JSON. Réessaie si la réponse n'est pas du JSON valide."""
    for attempt in range(max_retries):
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            if attempt == max_retries - 1:
                print(f"[error] Réponse LLM non-JSON après {max_retries} tentatives.", file=sys.stderr)
                raise
    raise ValueError("max_retries doit être >= 1")


# ---------------------------------------------------------------------------
# Phase 1 : Sweep
# ---------------------------------------------------------------------------

JINA_PREFIX = "https://r.jina.ai/"
MAX_RESULTS_PER_QUERY = 5


def _build_queries(slug: str) -> list[str]:
    topic = slug.replace("-", " ").replace("_", " ")
    return [topic, f"{topic} tutorial", f"{topic} explained"]


def run_sweep(slug: str, run_dir: Path, queries: list[str] | None = None) -> None:
    out_path = run_dir / "sweep_results.json"
    if out_path.exists():
        print("[sweep] sweep_results.json déjà présent, skip.")
        return

    if queries is None:
        queries = _build_queries(slug)

    results: list[dict] = []
    with DDGS() as ddg:
        for query in queries:
            hits = ddg.text(query, max_results=MAX_RESULTS_PER_QUERY)
            print(f"[sweep] '{query}' → {len(hits)} résultats")
            for hit in hits:
                url = hit["href"]
                try:
                    resp = requests.get(f"{JINA_PREFIX}{url}", timeout=15)
                    markdown = resp.text
                except Exception as e:
                    print(f"[sweep] Jina échec {url}: {e}", file=sys.stderr)
                    continue
                results.append({"query": query, "url": url, "markdown": markdown})

    print(f"[sweep] {len(results)} pages récupérées")
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Phase 2 : Extract
# ---------------------------------------------------------------------------

EXTRACT_PROMPT = """\
Tu es un rédacteur technique expert. Analyse le contenu web ci-dessous et produis :
1. Une liste de faits vérifiables extraits du contenu, chacun avec ses sources URL.
2. Les sections d'un document pédagogique structuré sur le sujet.

Sujet : {slug}

Contenu web :
{content}

Réponds UNIQUEMENT avec un JSON valide de cette structure exacte :
{{
  "facts": [
    {{"id": "fact_001", "fact": "...", "sources": ["url1", "url2"]}}
  ],
  "sections": [
    {{"id": "section_<slug_snake_case>", "title": "...", "level": 1, "content": "..."}}
  ]
}}

Règles :
- IDs de section préfixés "section_" en snake_case (ex: "section_gradient_descent").
- Chaque fait référence les URLs sources où il apparaît.
- Le contenu des sections est en markdown.
- level 1 = section principale, level 2 = sous-section.
"""

MAX_CONTENT_CHARS = 80_000


def run_extract(slug: str, run_dir: Path, client: OpenAI, model: str) -> None:
    if (run_dir / "knowledge.json").exists() and (run_dir / "sections_draft.json").exists():
        print("[extract] Fichiers déjà présents, skip.")
        return

    sweep = json.loads((run_dir / "sweep_results.json").read_text())
    content = "\n\n---\n\n".join(
        f"Source: {r['url']}\n{r['markdown']}" for r in sweep
    )[:MAX_CONTENT_CHARS]

    print(f"[extract] Appel LLM ({len(content)} chars)...")
    result = chat_structured(client, model,
                             EXTRACT_PROMPT.format(slug=slug.replace("-", " ").replace("_", " "), content=content))

    facts = result.get("facts", [])
    for f in facts:
        f.setdefault("confirmed", False)

    sections = result.get("sections", [])
    print(f"[extract] {len(facts)} faits, {len(sections)} sections")

    (run_dir / "knowledge.json").write_text(
        json.dumps(facts, ensure_ascii=False, indent=2))
    (run_dir / "sections_draft.json").write_text(
        json.dumps(sections, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Phase 3 : Verify
# ---------------------------------------------------------------------------

VERIFY_PROMPT = """\
Vérifie si le fait suivant est confirmé par au moins 2 sources indépendantes dans le contenu fourni.

Fait (id={fact_id}) : {fact}

Contenu des sources :
{source_content}

Réponds UNIQUEMENT avec un JSON :
{{"confirmed": true, "reason": "..."}}
ou
{{"confirmed": false, "reason": "..."}}

Un fait est confirmé si au moins 2 domaines différents le mentionnent explicitement.
"""

MAX_SOURCE_CHARS = 4_000


def run_verify(run_dir: Path, client: OpenAI, model: str) -> None:
    done_flag = run_dir / ".verify_done"
    if done_flag.exists():
        print("[verify] Déjà effectué, skip.")
        return

    facts  = json.loads((run_dir / "knowledge.json").read_text())
    sweep  = json.loads((run_dir / "sweep_results.json").read_text())
    source_index = {r["url"]: r["markdown"] for r in sweep}

    confirmed_count = 0
    for fact in facts:
        source_content = "\n\n---\n\n".join(
            f"URL: {url}\n{source_index.get(url, '')}"
            for url in fact.get("sources", [])
        )[:MAX_SOURCE_CHARS]

        result = chat_structured(client, model, VERIFY_PROMPT.format(
            fact_id=fact["id"], fact=fact["fact"], source_content=source_content
        ))
        fact["confirmed"] = bool(result.get("confirmed", False))
        if fact["confirmed"]:
            confirmed_count += 1

    total = len(facts)
    print(f"[verify] {confirmed_count}/{total} faits confirmés")
    (run_dir / "knowledge.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2))
    done_flag.write_text("done")

    status = {"status": "ok", "confirmed": confirmed_count, "total": total}
    if total > 0 and confirmed_count / total < 0.5:
        status["status"] = "partial"
        print(f"[verify] Avertissement : ratio confirmés insuffisant ({confirmed_count}/{total})",
              file=sys.stderr)
        print(json.dumps(status))
        sys.exit(2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

PHASES = ["sweep", "extract", "verify"]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="dipriserch — pipeline recherche → document")
    parser.add_argument("slug", help="Identifiant du sujet (ex: gradient-descent)")
    parser.add_argument("--from", dest="from_phase", choices=PHASES, default="sweep",
                        help="Reprendre à partir de cette phase")
    args = parser.parse_args(argv)

    cfg    = load_config()
    client = make_llm_client(cfg)
    model  = cfg["model"]

    run_dir = Path("run") / args.slug
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[dipriserch] slug={args.slug} from={args.from_phase} run_dir={run_dir}")

    start = PHASES.index(args.from_phase)
    if start <= PHASES.index("sweep"):
        run_sweep(args.slug, run_dir)
    if start <= PHASES.index("extract"):
        run_extract(args.slug, run_dir, client, model)
    if start <= PHASES.index("verify"):
        run_verify(run_dir, client, model)

    print(json.dumps({"status": "ok", "run_dir": str(run_dir)}))


if __name__ == "__main__":
    main()
