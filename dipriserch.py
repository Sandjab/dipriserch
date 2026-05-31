#!/usr/bin/env python3
"""dipriserch — pipeline recherche → document HTML avec widgets Claude."""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values, load_dotenv
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
