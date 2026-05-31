# dipriserch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire le pipeline dipriserch — LLM externe pour sweep/extract/verify, Claude pour génération de N widgets HTML interactifs inventés sur mesure, build.py pour l'assemblage en 1 édition HTML référence.

**Architecture:** Script Python monolithique `dipriserch.py` (sweep → extract → verify) déclenché via Bash avec `--from` pour reprises partielles. Claude lit `sections_draft.json`, invente et génère N widgets autonomes, compose `manifest.json`. `build.py` assemble le tout en `output.html`.

**Tech Stack:** Python 3.11+, `openai` SDK (compatible Ollama/RunPod), `duckduckgo-search`, `requests` (Jina), `python-dotenv`, `markdown`, `pytest`

---

## Schémas JSON — source de vérité

Tous les fichiers intermédiaires respectent ces schémas. Toutes les phases s'y conforment.

**`sweep_results.json`**
```json
[{"query": "str", "url": "str", "markdown": "str"}]
```

**`knowledge.json`**
```json
[{"id": "fact_001", "fact": "str", "sources": ["url1", "url2"], "confirmed": true}]
```

**`sections_draft.json`**
```json
[{"id": "section_introduction", "title": "str", "level": 1, "content": "markdown str"}]
```
IDs de section : slugs stables en snake_case préfixés `section_`.

**`manifest.json`** (écrit par Claude)
```json
[
  {"type": "section", "id": "section_introduction", "title": "str", "anchor": "str"},
  {"type": "widget",  "id": "widget_1", "title": "str", "anchor": "str", "after_section": "section_<slug>"}
]
```

---

## Structure des fichiers

```
dipriserch.py          ← entrée CLI + toutes les phases (sweep, extract, verify)
build.py               ← assemblage HTML déterministe
requirements.txt
.env.example
assets/
  style.css
skills/
  dipriserch.md        ← SKILL.md pour Claude (brief → widgets → compose → build)
tests/
  conftest.py
  test_config.py
  test_sweep.py
  test_extract.py
  test_verify.py
  test_cli.py
  test_build.py
  fixtures/
    sweep_results.json
    knowledge.json
    sections_draft.json
    manifest.json
    widget_1.html
run/                   ← gitignored, créé à l'exécution
  <slug>/
    sweep_results.json
    knowledge.json
    sections_draft.json
    widgets/
      widget_<n>.html
    manifest.json
    output.html
```

---

## Task 1 : Scaffold du projet

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Modify: `.gitignore`
- Create: `assets/style.css`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/sweep_results.json`
- Create: `tests/fixtures/knowledge.json`
- Create: `tests/fixtures/sections_draft.json`
- Create: `tests/fixtures/manifest.json`
- Create: `tests/fixtures/widget_1.html`

- [ ] **Step 1 : Créer requirements.txt**

```
duckduckgo-search>=6.0.0
requests>=2.31.0
openai>=1.30.0
python-dotenv>=1.0.0
markdown>=3.6
pytest>=8.0.0
pytest-mock>=3.12.0
```

- [ ] **Step 2 : Créer .env.example**

```
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5:32b
LLM_API_KEY=ollama
```

- [ ] **Step 3 : Ajouter au .gitignore**

```
.env
run/
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

- [ ] **Step 4 : Créer assets/style.css**

```css
:root {
  --font: system-ui, sans-serif;
  --max-width: 860px;
  --widget-bg: #f8f9fa;
  --widget-border: #dee2e6;
}
body { font-family: var(--font); max-width: var(--max-width); margin: 2rem auto; padding: 0 1.5rem; line-height: 1.7; }
h1, h2, h3 { margin-top: 2rem; }
nav { background: #f0f0f0; padding: 1rem; border-radius: 6px; margin-bottom: 2rem; }
nav ul { margin: 0; padding-left: 1.5rem; }
.widget-container { background: var(--widget-bg); border: 1px solid var(--widget-border); border-radius: 8px; padding: 1rem; margin: 1.5rem 0; }
.widget-container h3 { margin-top: 0; font-size: 1rem; color: #555; }
.widget-container iframe { width: 100%; border: none; min-height: 400px; }
```

- [ ] **Step 5 : Créer tests/conftest.py**

```python
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.fixture
def fixtures_dir():
    return FIXTURES

@pytest.fixture
def run_dir(tmp_path):
    d = tmp_path / "test-slug"
    d.mkdir()
    return d
```

- [ ] **Step 6 : Créer les fixtures de test**

`tests/fixtures/sweep_results.json` :
```json
[
  {
    "query": "gradient descent neural network",
    "url": "https://example.com/gradient",
    "markdown": "# Gradient Descent\n\nGradient descent is an optimization algorithm that minimizes a loss function by iteratively adjusting parameters in the direction of the negative gradient."
  },
  {
    "query": "gradient descent neural network",
    "url": "https://other.org/ml-basics",
    "markdown": "## Optimization Methods\n\nGradient descent iteratively updates parameters using the gradient of the loss function. The learning rate controls step size."
  }
]
```

`tests/fixtures/knowledge.json` :
```json
[
  {
    "id": "fact_001",
    "fact": "Gradient descent minimizes a loss function by iteratively adjusting parameters in the direction of the negative gradient.",
    "sources": ["https://example.com/gradient", "https://other.org/ml-basics"],
    "confirmed": true
  },
  {
    "id": "fact_002",
    "fact": "The learning rate controls the step size in gradient descent.",
    "sources": ["https://other.org/ml-basics"],
    "confirmed": false
  }
]
```

`tests/fixtures/sections_draft.json` :
```json
[
  {
    "id": "section_introduction",
    "title": "Introduction",
    "level": 1,
    "content": "Gradient descent is a fundamental optimization algorithm in machine learning."
  },
  {
    "id": "section_gradient_descent",
    "title": "Gradient Descent",
    "level": 2,
    "content": "Gradient descent minimizes a loss function by iteratively adjusting parameters in the direction of the negative gradient. The learning rate controls the step size."
  }
]
```

`tests/fixtures/manifest.json` :
```json
[
  {"type": "section", "id": "section_introduction",    "title": "Introduction",      "anchor": "introduction"},
  {"type": "section", "id": "section_gradient_descent","title": "Gradient Descent",  "anchor": "gradient-descent"},
  {"type": "widget",  "id": "widget_1", "title": "Descente de gradient interactive", "anchor": "widget-gradient-descent", "after_section": "section_gradient_descent"}
]
```

`tests/fixtures/widget_1.html` :
```html
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><style>body{font-family:sans-serif;padding:1rem;}</style></head>
<body><h2>Gradient Descent Demo</h2><p>Widget de démonstration.</p></body>
</html>
```

- [ ] **Step 7 : Installer les dépendances**

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```
Expected : `Successfully installed ...` sans erreur.

- [ ] **Step 8 : Commit**

```bash
git add requirements.txt .env.example .gitignore assets/ tests/
git commit -m "chore: scaffold projet dipriserch"
```

---

## Task 2 : Config + client LLM

**Files:**
- Create: `dipriserch.py` (config + client uniquement)
- Create: `tests/test_config.py`

- [ ] **Step 1 : Écrire le test config**

```python
# tests/test_config.py
import sys
import pytest

def test_load_config_valid(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://localhost:11434/v1\nLLM_MODEL=qwen2.5:32b\nLLM_API_KEY=ollama\n"
    )
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("dipriserch", None)
    import dipriserch
    cfg = dipriserch.load_config()
    assert cfg["base_url"] == "http://localhost:11434/v1"
    assert cfg["model"] == "qwen2.5:32b"
    assert cfg["api_key"] == "ollama"

def test_load_config_missing_key(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("LLM_BASE_URL=http://localhost:11434/v1\n")
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("dipriserch", None)
    import dipriserch
    with pytest.raises(SystemExit):
        dipriserch.load_config()
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
pytest tests/test_config.py -v
```
Expected : `ModuleNotFoundError: No module named 'dipriserch'`

- [ ] **Step 3 : Créer dipriserch.py**

```python
#!/usr/bin/env python3
"""dipriserch — pipeline recherche → document HTML avec widgets Claude."""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from openai import OpenAI


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    load_dotenv()
    required = {"LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"}
    missing = required - set(os.environ)
    if missing:
        print(f"[error] Variables .env manquantes : {', '.join(sorted(missing))}", file=sys.stderr)
        sys.exit(1)
    return {
        "base_url": os.environ["LLM_BASE_URL"],
        "model":    os.environ["LLM_MODEL"],
        "api_key":  os.environ["LLM_API_KEY"],
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
    return {}
```

- [ ] **Step 4 : Relancer les tests**

```bash
pytest tests/test_config.py -v
```
Expected : PASS (2 tests)

- [ ] **Step 5 : Commit**

```bash
git add dipriserch.py tests/test_config.py
git commit -m "feat: config loader + client LLM"
```

---

## Task 3 : Phase Sweep

**Files:**
- Modify: `dipriserch.py` (ajouter `run_sweep`)
- Create: `tests/test_sweep.py`

- [ ] **Step 1 : Écrire le test sweep**

```python
# tests/test_sweep.py
import json
from unittest.mock import patch, MagicMock

def test_sweep_writes_results(run_dir):
    mock_hits = [
        {"href": "https://example.com/1", "title": "Page 1"},
        {"href": "https://other.org/2",   "title": "Page 2"},
    ]
    mock_markdown = "# Title\n\nSome content about gradient descent."

    with patch("dipriserch.DDGS") as mock_ddgs_cls, \
         patch("dipriserch.requests.get") as mock_get:

        instance = MagicMock()
        instance.text.return_value = mock_hits
        mock_ddgs_cls.return_value.__enter__.return_value = instance
        mock_get.return_value.text = mock_markdown

        import dipriserch
        dipriserch.run_sweep("gradient-descent", run_dir,
                             queries=["gradient descent neural network"])

    results = json.loads((run_dir / "sweep_results.json").read_text())
    assert len(results) == 2
    assert results[0]["url"] == "https://example.com/1"
    assert results[0]["markdown"] == mock_markdown
    assert results[0]["query"] == "gradient descent neural network"

def test_sweep_skipped_if_results_exist(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")

    with patch("dipriserch.DDGS") as mock_ddgs_cls:
        dipriserch.run_sweep("gradient-descent", run_dir, queries=["test"])
        mock_ddgs_cls.assert_not_called()
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
pytest tests/test_sweep.py -v
```
Expected : FAIL (`AttributeError: module 'dipriserch' has no attribute 'run_sweep'`)

- [ ] **Step 3 : Implémenter run_sweep dans dipriserch.py**

Ajouter après la section Config :

```python
# ---------------------------------------------------------------------------
# Phase 1 : Sweep
# ---------------------------------------------------------------------------

from duckduckgo_search import DDGS

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
```

- [ ] **Step 4 : Relancer les tests**

```bash
pytest tests/test_sweep.py -v
```
Expected : PASS (2 tests)

- [ ] **Step 5 : Commit**

```bash
git add dipriserch.py tests/test_sweep.py
git commit -m "feat: phase sweep (duckduckgo + jina)"
```

---

## Task 4 : Phase Extract

**Files:**
- Modify: `dipriserch.py` (ajouter `run_extract`)
- Create: `tests/test_extract.py`

- [ ] **Step 1 : Écrire le test extract**

```python
# tests/test_extract.py
import json
from unittest.mock import patch, MagicMock

LLM_RESPONSE = {
    "facts": [
        {"id": "fact_001", "fact": "Gradient descent minimizes a loss function.",
         "sources": ["https://example.com/gradient", "https://other.org/ml-basics"]}
    ],
    "sections": [
        {"id": "section_introduction",     "title": "Introduction",    "level": 1, "content": "Gradient descent is fundamental."},
        {"id": "section_gradient_descent", "title": "Gradient Descent","level": 2, "content": "It adjusts parameters iteratively."}
    ]
}

def test_extract_writes_files(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")

    with patch("dipriserch.chat_structured", return_value=LLM_RESPONSE):
        dipriserch.run_extract("gradient-descent", run_dir, MagicMock(), "test-model")

    knowledge = json.loads((run_dir / "knowledge.json").read_text())
    sections  = json.loads((run_dir / "sections_draft.json").read_text())

    assert len(knowledge) == 1
    assert knowledge[0]["id"] == "fact_001"
    assert knowledge[0]["confirmed"] is False  # non vérifié à ce stade

    assert len(sections) == 2
    assert sections[0]["id"] == "section_introduction"

def test_extract_skipped_if_files_exist(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "knowledge.json",      run_dir / "knowledge.json")
    shutil.copy(fixtures_dir / "sections_draft.json", run_dir / "sections_draft.json")

    with patch("dipriserch.chat_structured") as mock_chat:
        dipriserch.run_extract("gradient-descent", run_dir, MagicMock(), "test-model")
        mock_chat.assert_not_called()
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
pytest tests/test_extract.py -v
```
Expected : FAIL

- [ ] **Step 3 : Implémenter run_extract dans dipriserch.py**

```python
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
                             EXTRACT_PROMPT.format(slug=slug.replace("-", " "), content=content))

    facts = result.get("facts", [])
    for f in facts:
        f.setdefault("confirmed", False)

    sections = result.get("sections", [])
    print(f"[extract] {len(facts)} faits, {len(sections)} sections")

    (run_dir / "knowledge.json").write_text(
        json.dumps(facts, ensure_ascii=False, indent=2))
    (run_dir / "sections_draft.json").write_text(
        json.dumps(sections, ensure_ascii=False, indent=2))
```

- [ ] **Step 4 : Relancer les tests**

```bash
pytest tests/test_extract.py -v
```
Expected : PASS (2 tests)

- [ ] **Step 5 : Commit**

```bash
git add dipriserch.py tests/test_extract.py
git commit -m "feat: phase extract (LLM → knowledge + sections)"
```

---

## Task 5 : Phase Verify

**Files:**
- Modify: `dipriserch.py` (ajouter `run_verify`)
- Create: `tests/test_verify.py`

- [ ] **Step 1 : Écrire le test verify**

```python
# tests/test_verify.py
import json
from unittest.mock import patch, MagicMock

def test_verify_marks_confirmed_facts(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")

    knowledge = [
        {"id": "fact_001", "fact": "Gradient descent minimizes loss.",
         "sources": ["https://example.com/gradient", "https://other.org/ml-basics"], "confirmed": False},
        {"id": "fact_002", "fact": "Learning rate must be tuned.",
         "sources": ["https://example.com/gradient"], "confirmed": False},
    ]
    (run_dir / "knowledge.json").write_text(json.dumps(knowledge))

    def mock_verify(client, model, prompt):
        if "fact_001" in prompt:
            return {"confirmed": True,  "reason": "Two independent sources confirm this."}
        return     {"confirmed": False, "reason": "Only one source found."}

    with patch("dipriserch.chat_structured", side_effect=mock_verify):
        dipriserch.run_verify(run_dir, MagicMock(), "test-model")

    updated   = json.loads((run_dir / "knowledge.json").read_text())
    confirmed = [f for f in updated if f["confirmed"]]
    assert len(confirmed) == 1
    assert confirmed[0]["id"] == "fact_001"

def test_verify_skipped_if_done_flag_exists(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "knowledge.json", run_dir / "knowledge.json")
    (run_dir / ".verify_done").write_text("done")

    with patch("dipriserch.chat_structured") as mock_chat:
        dipriserch.run_verify(run_dir, MagicMock(), "test-model")
        mock_chat.assert_not_called()
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
pytest tests/test_verify.py -v
```
Expected : FAIL

- [ ] **Step 3 : Implémenter run_verify dans dipriserch.py**

```python
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
```

- [ ] **Step 4 : Relancer les tests**

```bash
pytest tests/test_verify.py -v
```
Expected : PASS (2 tests)

- [ ] **Step 5 : Commit**

```bash
git add dipriserch.py tests/test_verify.py
git commit -m "feat: phase verify (vérification adversariale LLM)"
```

---

## Task 6 : CLI — orchestration

**Files:**
- Modify: `dipriserch.py` (ajouter `main()` + `__main__`)
- Create: `tests/test_cli.py`

- [ ] **Step 1 : Écrire le test CLI**

```python
# tests/test_cli.py
from unittest.mock import patch, MagicMock

def test_cli_orchestre_toutes_les_phases(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://x\nLLM_MODEL=test\nLLM_API_KEY=x\n"
    )
    monkeypatch.chdir(tmp_path)

    with patch("dipriserch.run_sweep")   as ms, \
         patch("dipriserch.run_extract") as me, \
         patch("dipriserch.run_verify")  as mv, \
         patch("dipriserch.make_llm_client", return_value=MagicMock()):
        import dipriserch
        dipriserch.main(["gradient-descent"])

    run_dir = tmp_path / "run" / "gradient-descent"
    assert run_dir.exists()
    ms.assert_called_once()
    me.assert_called_once()
    mv.assert_called_once()

def test_cli_from_extract_saute_sweep(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://x\nLLM_MODEL=test\nLLM_API_KEY=x\n"
    )
    monkeypatch.chdir(tmp_path)

    with patch("dipriserch.run_sweep")   as ms, \
         patch("dipriserch.run_extract") as me, \
         patch("dipriserch.run_verify")  as mv, \
         patch("dipriserch.make_llm_client", return_value=MagicMock()):
        import dipriserch
        dipriserch.main(["gradient-descent", "--from", "extract"])

    ms.assert_not_called()
    me.assert_called_once()
    mv.assert_called_once()

def test_cli_from_verify_saute_sweep_et_extract(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://x\nLLM_MODEL=test\nLLM_API_KEY=x\n"
    )
    monkeypatch.chdir(tmp_path)

    with patch("dipriserch.run_sweep")   as ms, \
         patch("dipriserch.run_extract") as me, \
         patch("dipriserch.run_verify")  as mv, \
         patch("dipriserch.make_llm_client", return_value=MagicMock()):
        import dipriserch
        dipriserch.main(["gradient-descent", "--from", "verify"])

    ms.assert_not_called()
    me.assert_not_called()
    mv.assert_called_once()
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
pytest tests/test_cli.py -v
```
Expected : FAIL

- [ ] **Step 3 : Implémenter main() dans dipriserch.py**

Ajouter à la fin du fichier :

```python
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
```

- [ ] **Step 4 : Relancer les tests**

```bash
pytest tests/test_cli.py -v
```
Expected : PASS (3 tests)

- [ ] **Step 5 : Smoke test (sans LLM)**

```bash
python dipriserch.py --help
```
Expected : affiche l'aide argparse sans erreur.

- [ ] **Step 6 : Commit**

```bash
git add dipriserch.py tests/test_cli.py
git commit -m "feat: CLI orchestration avec --from pour reprises partielles"
```

---

## Task 7 : build.py — assemblage HTML

**Files:**
- Create: `build.py`
- Create: `tests/test_build.py`

- [ ] **Step 1 : Écrire le test build**

```python
# tests/test_build.py
import shutil
from pathlib import Path

def test_build_produit_html(run_dir, fixtures_dir):
    import build

    shutil.copy(fixtures_dir / "manifest.json",       run_dir / "manifest.json")
    shutil.copy(fixtures_dir / "sections_draft.json", run_dir / "sections_draft.json")
    widgets_dir = run_dir / "widgets"
    widgets_dir.mkdir()
    shutil.copy(fixtures_dir / "widget_1.html", widgets_dir / "widget_1.html")

    css_path = fixtures_dir.parent.parent / "assets" / "style.css"
    build.build(run_dir, css_path=css_path)

    html = (run_dir / "output.html").read_text()
    assert "<html" in html
    assert "Introduction" in html
    assert "Gradient Descent" in html
    assert "Descente de gradient interactive" in html
    assert 'id="widget-gradient-descent"' in html

def test_build_echoue_si_widget_manquant(run_dir, fixtures_dir):
    import build, pytest

    shutil.copy(fixtures_dir / "manifest.json",       run_dir / "manifest.json")
    shutil.copy(fixtures_dir / "sections_draft.json", run_dir / "sections_draft.json")
    (run_dir / "widgets").mkdir()
    # widget_1.html intentionnellement absent

    with pytest.raises(FileNotFoundError, match="widget_1.html"):
        build.build(run_dir)
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
pytest tests/test_build.py -v
```
Expected : FAIL (`ModuleNotFoundError: No module named 'build'`)

- [ ] **Step 3 : Créer build.py**

```python
#!/usr/bin/env python3
"""build.py — assemblage déterministe HTML depuis manifest.json."""

import json
import re
import sys
from pathlib import Path

import markdown as md


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _toc(entries: list[dict]) -> str:
    items = []
    for e in entries:
        indent = "  " if e["type"] == "widget" else ""
        items.append(f'{indent}<li><a href="#{e["anchor"]}">{e["title"]}</a></li>')
    return "<nav><ul>\n" + "\n".join(items) + "\n</ul></nav>\n"


def _section(entry: dict, sections_index: dict) -> str:
    sec = sections_index.get(entry["id"])
    if not sec:
        raise KeyError(f"Section '{entry['id']}' absente de sections_draft.json")
    level = sec.get("level", 2)
    body  = md.markdown(sec["content"])
    return (f'<section id="{entry["anchor"]}">\n'
            f'<h{level}>{entry["title"]}</h{level}>\n{body}\n</section>\n')


def _widget(entry: dict, widgets_dir: Path) -> str:
    wpath = widgets_dir / f"{entry['id']}.html"
    if not wpath.exists():
        raise FileNotFoundError(f"{entry['id']}.html introuvable dans {widgets_dir}")
    raw  = wpath.read_text()
    # Extraire le contenu du body si le widget est un document HTML complet
    m    = re.search(r"<body[^>]*>(.*?)</body>", raw, re.DOTALL | re.IGNORECASE)
    body = m.group(1).strip() if m else raw
    # Extraire les <style> du <head>
    styles = "\n".join(re.findall(r"<style[^>]*>.*?</style>", raw, re.DOTALL | re.IGNORECASE))
    return (f'<div class="widget-container" id="{entry["anchor"]}">\n'
            f'<h3>{entry["title"]}</h3>\n'
            f'{styles}\n{body}\n</div>\n')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build(run_dir: Path, css_path: Path | None = None) -> None:
    run_dir    = Path(run_dir)
    manifest   = json.loads((run_dir / "manifest.json").read_text())
    sections   = json.loads((run_dir / "sections_draft.json").read_text())
    sec_index  = {s["id"]: s for s in sections}
    widgets_dir = run_dir / "widgets"

    # Validation préalable : tous les widgets référencés doivent exister
    for e in manifest:
        if e["type"] == "widget":
            wpath = widgets_dir / f"{e['id']}.html"
            if not wpath.exists():
                raise FileNotFoundError(f"{e['id']}.html manquant dans {widgets_dir}")

    css = (css_path or Path("assets/style.css")).read_text()

    parts = [_toc(manifest)]
    for e in manifest:
        if e["type"] == "section":
            parts.append(_section(e, sec_index))
        elif e["type"] == "widget":
            parts.append(_widget(e, widgets_dir))

    title = sections[0]["title"] if sections else "Document"
    html  = (
        f'<!DOCTYPE html>\n<html lang="fr">\n<head>\n'
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{title}</title>\n'
        f'<style>{css}</style>\n'
        f'</head>\n<body>\n'
        + "".join(parts)
        + '</body>\n</html>'
    )

    out = run_dir / "output.html"
    out.write_text(html)
    n_widgets = sum(1 for e in manifest if e["type"] == "widget")
    print(f"[build] {out} généré ({len(html)} chars, {n_widgets} widget(s))")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build.py run/<slug>/", file=sys.stderr)
        sys.exit(1)
    build(Path(sys.argv[1]))
```

- [ ] **Step 4 : Relancer les tests**

```bash
pytest tests/test_build.py -v
```
Expected : PASS (2 tests)

- [ ] **Step 5 : Lancer la suite complète**

```bash
pytest tests/ -v
```
Expected : tous les tests PASS.

- [ ] **Step 6 : Commit**

```bash
git add build.py tests/test_build.py
git commit -m "feat: build.py assemblage HTML déterministe (1 édition, N widgets)"
```

---

## Task 8 : SKILL.md — instructions Claude

**Files:**
- Create: `skills/dipriserch.md`

- [ ] **Step 1 : Créer skills/dipriserch.md**

```markdown
# dipriserch — SKILL

Génère un document HTML de référence avec N widgets interactifs sur mesure.
Les phases lourdes (sweep, extract, verify) sont déléguées au LLM externe.
Claude gère le brief, la création des widgets et la composition finale.

## 1. Brief

Demander à l'utilisateur (ou inférer du contexte) :
- **slug** : identifiant kebab-case du sujet (ex: `gradient-descent`, `transformer-attention`)
- **langue** : fr ou en (défaut : fr)
- Confirmer que `.env` est configuré (LLM_BASE_URL, LLM_MODEL, LLM_API_KEY)

## 2. Lancer le pipeline LLM externe

```bash
python dipriserch.py <slug>
```

Lire stdout ligne par ligne. La dernière ligne est un JSON de status :
- `{"status": "ok", "run_dir": "run/<slug>"}` → continuer
- `{"status": "partial", "confirmed": N, "total": M}` → demander confirmation avant de continuer
- Exit code 1 + stderr → diagnostiquer l'erreur (config LLM ? réseau ?)

En cas d'erreur mid-run, reprendre avec `--from sweep|extract|verify` selon la phase échouée.

## 3. Lire le contenu extrait

```python
# Lire ces deux fichiers pour comprendre le document
Read("run/<slug>/sections_draft.json")
Read("run/<slug>/knowledge.json")
```

## 4. Générer les widgets (phase créative)

Pour chaque section ou concept dans `sections_draft.json`, évaluer :
**Ce principe est-il plus clair montré qu'expliqué ?**

Si oui → inventer le widget le plus pédagogiquement adapté et le coder.

**Critères orientateurs :**
- Algorithme avec états successifs → simulation pas à pas
- Formule avec paramètres → sliders interactifs
- Relation spatiale/graphique → visualisation manipulable
- Comparaison → vue avant/après

**Règles de génération :**
- Chaque widget est un fichier HTML+CSS+JS autonome, sans dépendance externe CDN
- Nommer les fichiers `run/<slug>/widgets/widget_1.html`, `widget_2.html`, etc.
- Les widgets existants (fichiers déjà présents) ne sont pas regénérés
- Pas de limite de nombre : générer autant que le contenu le justifie
- Créer `run/<slug>/widgets/` si le dossier n'existe pas

## 5. Composer manifest.json

Écrire `run/<slug>/manifest.json` — liste ordonnée sections + widgets :

```json
[
  {"type": "section", "id": "section_introduction", "title": "Introduction", "anchor": "introduction"},
  {"type": "section", "id": "section_gradient_descent", "title": "Gradient Descent", "anchor": "gradient-descent"},
  {"type": "widget",  "id": "widget_1", "title": "Descente de gradient interactive",
   "anchor": "widget-gradient-descent", "after_section": "section_gradient_descent"}
]
```

Règle de placement : un widget suit immédiatement la section qui introduit le principe qu'il illustre.
Les IDs de section proviennent de `sections_draft.json` (ne pas inventer de nouveaux IDs).
Les ancres sont les IDs sans le préfixe `section_`, en kebab-case.

## 6. Assembler le HTML final

```bash
python build.py run/<slug>/
```

Vérifier que `run/<slug>/output.html` est généré sans erreur.
Signaler à l'utilisateur : chemin du fichier, nombre de widgets intégrés.
```

- [ ] **Step 2 : Commit**

```bash
git add skills/dipriserch.md
git commit -m "docs: SKILL.md dipriserch (brief → widgets → compose → build)"
```

---

## Vérification finale

- [ ] **Lancer la suite de tests complète**

```bash
pytest tests/ -v --tb=short
```
Expected : tous les tests PASS, aucun warning critique.

- [ ] **Vérifier la structure du repo**

```bash
find . -not -path './.git/*' -not -path './.venv/*' -not -path './run/*' | sort
```
Expected : les fichiers suivants présents — `dipriserch.py`, `build.py`, `requirements.txt`,
`.env.example`, `assets/style.css`, `skills/dipriserch.md`, `tests/` avec tous les fichiers.
