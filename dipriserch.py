#!/usr/bin/env python3
"""dipriserch — pipeline recherche → document HTML avec widgets Claude."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values, load_dotenv
from ddgs import DDGS
from openai import OpenAI


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _env_int(env: dict, name: str, default: int) -> int:
    """Lit un entier depuis l'env ; retombe sur le défaut si absent/vide/invalide."""
    raw = env.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"[config] {name}={raw!r} invalide, défaut {default} utilisé.", file=sys.stderr)
        return default


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
        "map_k":            _env_int(env, "EXTRACT_MAP_K", EXTRACT_MAP_K),
        "map_page_cap":     _env_int(env, "EXTRACT_MAP_PAGE_CAP", EXTRACT_MAP_PAGE_CAP),
        "reduce_max_chars": _env_int(env, "EXTRACT_REDUCE_MAX_CHARS", EXTRACT_REDUCE_MAX_CHARS),
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


def clean_md(md: str) -> str:
    """Réduit le bruit du markdown Jina : liens → texte seul, images supprimées."""
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)        # images
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)    # liens markdown → texte
    md = re.sub(r"\n{3,}", "\n\n", md)                  # compacter lignes vides
    return md.strip()


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
                results.append({"query": query, "url": url, "markdown": clean_md(markdown)})

    if not results:
        print("[sweep] ERREUR : 0 page récupérée — recherche web vide, arrêt.", file=sys.stderr)
        sys.exit(1)

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

EXTRACT_MAP_K = 8                  # passages verbatim extraits par page (MAP)
EXTRACT_MAP_PAGE_CAP = 60_000      # cap chars/page au MAP (edge case page > contexte)
EXTRACT_REDUCE_MAX_CHARS = 32_000  # budget total de contenu passé au REDUCE
MIN_CONTENT_CHARS = 200

MAP_PROMPT = """\
Voici le contenu d'une page web sur le sujet « {slug} ».

Extrais les {k} passages les plus IMPORTANTS et FACTUELS, recopiés MOT POUR MOT depuis le
texte (aucune reformulation). Conserve chiffres, dates, noms propres, définitions exactes.
Ignore navigation, menus, publicité, pieds de page.

Page :
{content}

Réponds UNIQUEMENT avec un JSON valide de cette structure exacte :
{{"passages": ["passage verbatim 1", "passage verbatim 2"]}}
"""


def run_map(slug: str, run_dir: Path, client: OpenAI, model: str,
            k: int = EXTRACT_MAP_K, page_cap: int = EXTRACT_MAP_PAGE_CAP) -> None:
    """MAP : extrait K passages verbatim par page → passages.json (cacheable)."""
    out_path = run_dir / "passages.json"
    if out_path.exists():
        print("[map] passages.json déjà présent, skip.")
        return

    sweep = json.loads((run_dir / "sweep_results.json").read_text())
    topic = slug.replace("-", " ").replace("_", " ")

    results: list[dict] = []
    for page in sweep:
        content = page["markdown"][:page_cap]
        try:
            d = chat_structured(client, model,
                                MAP_PROMPT.format(slug=topic, k=k, content=content))
            passages = [p for p in d.get("passages", []) if isinstance(p, str) and p.strip()]
        except Exception as e:
            print(f"[map] échec {page['url']}: {e}", file=sys.stderr)
            continue
        if passages:
            results.append({"url": page["url"], "passages": passages})
        print(f"[map] {page['url']} → {len(passages)} passages")

    # Règle ≥ 2 sources : il faut au moins 2 pages distinctes pour corroborer quoi que ce soit.
    if len(results) < 2:
        print(f"[map] ERREUR : {len(results)} page(s) avec passages (< 2), corroboration "
              "impossible, arrêt.", file=sys.stderr)
        sys.exit(1)

    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    total = sum(len(r["passages"]) for r in results)
    print(f"[map] {len(results)} pages → {total} passages → passages.json")


def run_reduce(slug: str, run_dir: Path, client: OpenAI, model: str,
               max_chars: int = EXTRACT_REDUCE_MAX_CHARS) -> None:
    """REDUCE : agrège les passages en faits corroborés + sections."""
    if (run_dir / "knowledge.json").exists() and (run_dir / "sections_draft.json").exists():
        print("[reduce] Fichiers déjà présents, skip.")
        return

    passages = json.loads((run_dir / "passages.json").read_text())
    content = "\n\n---\n\n".join(
        f"Source: {p['url']}\n" + "\n".join(p["passages"]) for p in passages
    )[:max_chars]

    if len(content.strip()) < MIN_CONTENT_CHARS:
        print(f"[reduce] ERREUR : contenu insuffisant ({len(content)} chars < {MIN_CONTENT_CHARS}).",
              file=sys.stderr)
        sys.exit(1)

    topic = slug.replace("-", " ").replace("_", " ")
    print(f"[reduce] Appel LLM ({len(content)} chars)...")
    result = chat_structured(client, model, EXTRACT_PROMPT.format(slug=topic, content=content))

    facts = result.get("facts", [])
    for f in facts:
        f.setdefault("confirmed", False)
    sections = result.get("sections", [])
    print(f"[reduce] {len(facts)} faits, {len(sections)} sections")

    (run_dir / "knowledge.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2))
    (run_dir / "sections_draft.json").write_text(json.dumps(sections, ensure_ascii=False, indent=2))


def run_extract(slug: str, run_dir: Path, client: OpenAI, model: str,
                map_k: int = EXTRACT_MAP_K, map_page_cap: int = EXTRACT_MAP_PAGE_CAP,
                reduce_max_chars: int = EXTRACT_REDUCE_MAX_CHARS) -> None:
    """Extract = MAP (verbatim par page) puis REDUCE (agrégation + corroboration)."""
    run_map(slug, run_dir, client, model, map_k, map_page_cap)
    run_reduce(slug, run_dir, client, model, reduce_max_chars)


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
        # Règle non-négociable : ≥ 2 sources indépendantes requises
        if len(fact.get("sources", [])) < 2:
            fact["confirmed"] = False
            continue

        source_content = "\n\n---\n\n".join(
            f"URL: {url}\n{source_index.get(url, '')[:MAX_SOURCE_CHARS]}"
            for url in fact.get("sources", [])
        )

        result = chat_structured(client, model, VERIFY_PROMPT.format(
            fact_id=fact["id"], fact=fact["fact"], source_content=source_content
        ))
        fact["confirmed"] = bool(result.get("confirmed", False))
        if fact["confirmed"]:
            confirmed_count += 1

    total = len(facts)
    print(f"[verify] {confirmed_count}/{total} faits confirmés")
    (run_dir / "knowledge.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2))

    if total > 0 and confirmed_count / total < 0.5:
        print(f"[verify] Avertissement : ratio confirmés insuffisant ({confirmed_count}/{total})",
              file=sys.stderr)
        print(json.dumps({"status": "partial", "confirmed": confirmed_count, "total": total}))
        sys.exit(2)  # done_flag NON écrit → --from verify peut relancer

    done_flag.write_text("done")


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
        run_extract(args.slug, run_dir, client, model,
                    cfg["map_k"], cfg["map_page_cap"], cfg["reduce_max_chars"])
    if start <= PHASES.index("verify"):
        run_verify(run_dir, client, model)

    print(json.dumps({"status": "ok", "run_dir": str(run_dir)}))


if __name__ == "__main__":
    main()
