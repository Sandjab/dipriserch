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
