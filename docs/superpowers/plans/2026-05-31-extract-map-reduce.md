# Extract map-reduce verbatim — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer la stratégie « équitable par page » de la phase Extract par un map-reduce verbatim : MAP condense chaque page entière en passages factuels mot-pour-mot, REDUCE agrège tous les passages en faits corroborés + sections.

**Architecture:** `run_extract` devient un orchestrateur `run_map` → `run_reduce`. Le MAP fait 1 appel LLM par page (markdown nettoyé) et écrit `passages.json` (cacheable). Le REDUCE concatène tous les passages étiquetés URL et réutilise l'`EXTRACT_PROMPT` actuel pour produire `knowledge.json` + `sections_draft.json`. 3 paramètres `.env`. Le contexte du modèle reste un prérequis serveur (`OLLAMA_CONTEXT_LENGTH ≥ 32768`), pas un paramètre client.

**Tech Stack:** Python 3.12, SDK `openai` (endpoint OpenAI-compat d'Ollama), `pytest` + `unittest.mock`.

Spec de référence : `docs/superpowers/specs/2026-05-31-extract-map-reduce-design.md`.

---

## File Structure

- `dipriserch.py` (modifié) — ajoute `_env_int`, étend `load_config`, ajoute `MAP_PROMPT`, `run_map`, `run_reduce`, recâble `run_extract`, met à jour `main`. Supprime le bloc « équitable par page ».
- `tests/test_map.py` (créé) — tests unitaires de `run_map`.
- `tests/test_extract.py` (réécrit) — tests de `run_reduce` + test d'orchestration de `run_extract`.
- `tests/test_config.py` (modifié) — test des 3 paramètres `.env`.
- `tests/fixtures/passages.json` (créé) — fixture d'entrée pour `run_reduce`.
- `.env.example` (modifié) — documente les 3 params.
- `README.md` (modifié) — documente le prérequis serveur `OLLAMA_CONTEXT_LENGTH`.

---

## Task 0 : Committer les corrections déjà appliquées (base propre)

Le working tree contient les corrections validées (TLS/ddgs, garde-fous, `clean_md`, verify « par source »), non commitées. On les fige avant de construire le map-reduce par-dessus.

**Files:**
- Modify (déjà modifiés, à committer) : `dipriserch.py`, `requirements.txt`, `pyrightconfig.json`

- [ ] **Step 1 : Vérifier que la suite passe**

Run: `.venv/bin/python -m pytest -q`
Expected: `15 passed`

- [ ] **Step 2 : Vérifier le périmètre du commit**

Run: `git status --short`
Expected: exactement `dipriserch.py`, `requirements.txt`, `pyrightconfig.json` modifiés (`M`), rien d'autre en `run/`.

- [ ] **Step 3 : Committer**

```bash
git add dipriserch.py requirements.txt pyrightconfig.json
git commit -m "fix: réparer le pipeline (ddgs/TLS, garde-fous fail-loud, nettoyage Jina, verify par source)"
```

---

## Task 1 : Paramètres `.env` (`_env_int` + `load_config`)

**Files:**
- Modify: `dipriserch.py` (section Config, autour de `load_config:22`)
- Test: `tests/test_config.py`

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_config.py` :

```python
def test_env_int_helper():
    import dipriserch
    assert dipriserch._env_int({"K": "5"}, "K", 8) == 5
    assert dipriserch._env_int({}, "K", 8) == 8           # absent → défaut
    assert dipriserch._env_int({"K": ""}, "K", 8) == 8    # vide → défaut
    assert dipriserch._env_int({"K": "abc"}, "K", 8) == 8 # invalide → défaut

def test_load_config_extract_defaults(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://x/v1\nLLM_MODEL=m\nLLM_API_KEY=k\n"
    )
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("dipriserch", None)
    import dipriserch
    cfg = dipriserch.load_config()
    assert cfg["map_k"] == 8
    assert cfg["map_page_cap"] == 60000
    assert cfg["reduce_max_chars"] == 32000

def test_load_config_extract_overrides(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://x/v1\nLLM_MODEL=m\nLLM_API_KEY=k\n"
        "EXTRACT_MAP_K=5\nEXTRACT_MAP_PAGE_CAP=40000\nEXTRACT_REDUCE_MAX_CHARS=20000\n"
    )
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("dipriserch", None)
    import dipriserch
    cfg = dipriserch.load_config()
    assert cfg["map_k"] == 5
    assert cfg["map_page_cap"] == 40000
    assert cfg["reduce_max_chars"] == 20000
```

- [ ] **Step 2 : Lancer pour vérifier l'échec**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: FAIL (`AttributeError: module 'dipriserch' has no attribute '_env_int'`).

- [ ] **Step 3 : Implémenter**

Dans `dipriserch.py`, juste avant `def load_config` (vers la ligne 22), ajouter le helper :

```python
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
```

Puis, dans `load_config`, remplacer le `return { ... }` existant par :

```python
    return {
        "base_url": env["LLM_BASE_URL"],
        "model":    env["LLM_MODEL"],
        "api_key":  env["LLM_API_KEY"],
        "map_k":            _env_int(env, "EXTRACT_MAP_K", EXTRACT_MAP_K),
        "map_page_cap":     _env_int(env, "EXTRACT_MAP_PAGE_CAP", EXTRACT_MAP_PAGE_CAP),
        "reduce_max_chars": _env_int(env, "EXTRACT_REDUCE_MAX_CHARS", EXTRACT_REDUCE_MAX_CHARS),
    }
```

(Les constantes `EXTRACT_MAP_K`, `EXTRACT_MAP_PAGE_CAP`, `EXTRACT_REDUCE_MAX_CHARS` sont définies en Task 2, section Extract. Elles sont résolues à l'appel de `load_config`, donc l'ordre dans le fichier n'a pas d'importance — mais Task 2 doit être faite avant d'exécuter le pipeline réel. Les tests de cette task ne touchent pas ces constantes pour les défauts car ils passent par `load_config` qui les lit ; définir les constantes en Task 2 lèvera tout `NameError`. Pour que les tests de cette task tournent isolément, définir dès maintenant les 3 constantes en tête de la section Extract — voir Step 3 bis.)

- [ ] **Step 3 bis : Définir les constantes maintenant (pour que load_config résolve)**

Dans `dipriserch.py`, remplacer la ligne `MAX_CONTENT_CHARS = 28_000` (vers la ligne 143) par :

```python
EXTRACT_MAP_K = 8                  # passages verbatim extraits par page (MAP)
EXTRACT_MAP_PAGE_CAP = 60_000      # cap chars/page au MAP (edge case page > contexte)
EXTRACT_REDUCE_MAX_CHARS = 32_000  # budget total de contenu passé au REDUCE
MIN_CONTENT_CHARS = 200
```

(On supprime `MAX_CONTENT_CHARS` : il n'est plus utilisé après Task 4. La ligne `MIN_CONTENT_CHARS = 200` existante est absorbée ici ; supprimer l'ancienne ligne `MIN_CONTENT_CHARS = 200` restée plus bas si dupliquée.)

- [ ] **Step 4 : Lancer pour vérifier le succès**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: PASS (tous les tests config).

- [ ] **Step 5 : Committer**

```bash
git add dipriserch.py tests/test_config.py
git commit -m "feat: paramètres Extract configurables via .env (_env_int + load_config)"
```

---

## Task 2 : MAP — extraction verbatim par page (`run_map`)

**Files:**
- Modify: `dipriserch.py` (section Extract)
- Test: `tests/test_map.py` (créé)

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `tests/test_map.py` :

```python
import json
from unittest.mock import patch, MagicMock
import pytest

MAP_RESPONSE = {"passages": [
    "Gradient descent minimise une fonction de perte.",
    "Il ajuste les paramètres itérativement.",
]}

def test_map_writes_passages(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")
    with patch("dipriserch.chat_structured", return_value=MAP_RESPONSE):
        dipriserch.run_map("gradient-descent", run_dir, MagicMock(), "test-model")
    passages = json.loads((run_dir / "passages.json").read_text())
    assert len(passages) == 2                       # 2 pages du fixture
    assert passages[0]["url"] == "https://example.com/gradient"
    assert passages[0]["passages"] == MAP_RESPONSE["passages"]

def test_map_skipped_if_passages_exist(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")
    (run_dir / "passages.json").write_text("[]")
    with patch("dipriserch.chat_structured") as mock_chat:
        dipriserch.run_map("gradient-descent", run_dir, MagicMock(), "test-model")
        mock_chat.assert_not_called()

def test_map_fails_if_fewer_than_two_sources(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")
    # 0 passage retourné → aucune page retenue → < 2 sources → exit
    with patch("dipriserch.chat_structured", return_value={"passages": []}):
        with pytest.raises(SystemExit):
            dipriserch.run_map("gradient-descent", run_dir, MagicMock(), "test-model")
```

- [ ] **Step 2 : Lancer pour vérifier l'échec**

Run: `.venv/bin/python -m pytest tests/test_map.py -q`
Expected: FAIL (`AttributeError: module 'dipriserch' has no attribute 'run_map'`).

- [ ] **Step 3 : Implémenter `MAP_PROMPT` + `run_map`**

Dans `dipriserch.py`, section Extract, juste avant `EXTRACT_PROMPT` (vers la ligne 116), ajouter :

```python
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
```

Puis, après la définition de `clean_md`/`run_sweep` et avant `EXTRACT_PROMPT` (ou juste après les constantes `EXTRACT_*`), ajouter `run_map` :

```python
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
```

- [ ] **Step 4 : Lancer pour vérifier le succès**

Run: `.venv/bin/python -m pytest tests/test_map.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5 : Committer**

```bash
git add dipriserch.py tests/test_map.py
git commit -m "feat: MAP extraction verbatim par page (run_map + passages.json)"
```

---

## Task 3 : REDUCE — extraction + corroboration (`run_reduce`)

**Files:**
- Modify: `dipriserch.py` (remplace le corps de `run_extract` par `run_reduce`)
- Create: `tests/fixtures/passages.json`
- Test: `tests/test_extract.py` (réécrit)

- [ ] **Step 1 : Créer la fixture `passages.json`**

Créer `tests/fixtures/passages.json` :

```json
[
  {
    "url": "https://example.com/gradient",
    "passages": [
      "Gradient descent minimizes a loss function.",
      "It updates parameters in the direction of the negative gradient."
    ]
  },
  {
    "url": "https://other.org/ml-basics",
    "passages": [
      "Gradient descent is fundamental to machine learning.",
      "The learning rate controls the size of each step."
    ]
  }
]
```

- [ ] **Step 2 : Réécrire `tests/test_extract.py` avec les tests REDUCE (échouent)**

Remplacer **tout** le contenu de `tests/test_extract.py` par :

```python
import json
from unittest.mock import patch, MagicMock

LLM_RESPONSE = {
    "facts": [
        {"id": "fact_001", "fact": "Gradient descent minimizes a loss function.",
         "sources": ["https://example.com/gradient", "https://other.org/ml-basics"]}
    ],
    "sections": [
        {"id": "section_introduction",     "title": "Introduction",     "level": 1, "content": "Gradient descent is fundamental."},
        {"id": "section_gradient_descent", "title": "Gradient Descent", "level": 2, "content": "It adjusts parameters iteratively."}
    ]
}

def test_reduce_writes_files(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "passages.json", run_dir / "passages.json")
    with patch("dipriserch.chat_structured", return_value=LLM_RESPONSE):
        dipriserch.run_reduce("gradient-descent", run_dir, MagicMock(), "test-model")
    knowledge = json.loads((run_dir / "knowledge.json").read_text())
    sections  = json.loads((run_dir / "sections_draft.json").read_text())
    assert len(knowledge) == 1
    assert knowledge[0]["id"] == "fact_001"
    assert knowledge[0]["confirmed"] is False
    assert len(sections) == 2
    assert sections[0]["id"] == "section_introduction"

def test_reduce_skipped_if_files_exist(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "knowledge.json",      run_dir / "knowledge.json")
    shutil.copy(fixtures_dir / "sections_draft.json", run_dir / "sections_draft.json")
    with patch("dipriserch.chat_structured") as mock_chat:
        dipriserch.run_reduce("gradient-descent", run_dir, MagicMock(), "test-model")
        mock_chat.assert_not_called()

def test_extract_orchestrates_map_then_reduce(run_dir):
    import dipriserch
    with patch("dipriserch.run_map") as m_map, patch("dipriserch.run_reduce") as m_reduce:
        dipriserch.run_extract("gradient-descent", run_dir, MagicMock(), "test-model")
        m_map.assert_called_once()
        m_reduce.assert_called_once()
```

- [ ] **Step 3 : Lancer pour vérifier l'échec**

Run: `.venv/bin/python -m pytest tests/test_extract.py -q`
Expected: FAIL (`AttributeError: ... has no attribute 'run_reduce'`).

- [ ] **Step 4 : Implémenter `run_reduce`**

Dans `dipriserch.py`, remplacer **toute** la fonction `run_extract` actuelle (lignes ~147-180, le bloc « équitable par page ») par `run_reduce` :

```python
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
```

- [ ] **Step 5 : Lancer (REDUCE passe, orchestration échoue encore)**

Run: `.venv/bin/python -m pytest tests/test_extract.py -q`
Expected: `test_reduce_*` PASS ; `test_extract_orchestrates_map_then_reduce` FAIL (`run_extract` n'existe plus / appelle l'ancien code). On le règle en Task 4.

- [ ] **Step 6 : Committer**

```bash
git add dipriserch.py tests/test_extract.py tests/fixtures/passages.json
git commit -m "feat: REDUCE extraction+corroboration sur les passages (run_reduce)"
```

---

## Task 4 : Orchestration — `run_extract` = MAP + REDUCE + câblage `main`

**Files:**
- Modify: `dipriserch.py` (nouveau `run_extract`, `main`)
- Test: `tests/test_extract.py` (le test d'orchestration doit passer)

- [ ] **Step 1 : Implémenter le nouvel `run_extract`**

Dans `dipriserch.py`, juste après `run_reduce`, ajouter l'orchestrateur :

```python
def run_extract(slug: str, run_dir: Path, client: OpenAI, model: str,
                map_k: int = EXTRACT_MAP_K, map_page_cap: int = EXTRACT_MAP_PAGE_CAP,
                reduce_max_chars: int = EXTRACT_REDUCE_MAX_CHARS) -> None:
    """Extract = MAP (verbatim par page) puis REDUCE (agrégation + corroboration)."""
    run_map(slug, run_dir, client, model, map_k, map_page_cap)
    run_reduce(slug, run_dir, client, model, reduce_max_chars)
```

- [ ] **Step 2 : Câbler `main` pour passer les paramètres de `cfg`**

Dans `main`, remplacer l'appel `run_extract(args.slug, run_dir, client, model)` par :

```python
    if start <= PHASES.index("extract"):
        run_extract(args.slug, run_dir, client, model,
                    cfg["map_k"], cfg["map_page_cap"], cfg["reduce_max_chars"])
```

- [ ] **Step 3 : Lancer toute la suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (tous, dont `test_extract_orchestrates_map_then_reduce` et les 2 du config).

- [ ] **Step 4 : Vérifier qu'il ne reste aucune référence morte**

Run: `grep -n "MAX_CONTENT_CHARS\|per_page\|équitable" dipriserch.py`
Expected: aucune occurrence (l'ancienne stratégie est entièrement supprimée).

- [ ] **Step 5 : Committer**

```bash
git add dipriserch.py
git commit -m "feat: run_extract orchestre MAP+REDUCE, main passe les params .env"
```

---

## Task 5 : Documentation (`.env.example` + `README.md`)

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1 : Documenter les paramètres dans `.env.example`**

Ajouter à la fin de `.env.example` :

```
# --- Phase Extract (map-reduce) — optionnels, défauts entre parenthèses ---
# EXTRACT_MAP_K=8                  # passages verbatim extraits par page
# EXTRACT_MAP_PAGE_CAP=60000       # cap chars/page au MAP (edge case page longue)
# EXTRACT_REDUCE_MAX_CHARS=32000   # budget total de contenu passé au REDUCE
```

- [ ] **Step 2 : Documenter le prérequis serveur dans `README.md`**

Ajouter une section au `README.md` :

```markdown
## Prérequis serveur (Ollama)

Le serveur Ollama doit tourner avec une fenêtre de contexte suffisante :

    OLLAMA_CONTEXT_LENGTH >= 32768

Le client (dipriserch) **ne peut pas** forcer le contexte par requête : l'endpoint
OpenAI-compatible d'Ollama ignore `num_ctx`. La cohérence entre ce réglage serveur et
`EXTRACT_REDUCE_MAX_CHARS` (client) est de la responsabilité du déploiement — au-delà de
la fenêtre serveur, le prompt est tronqué silencieusement.
```

- [ ] **Step 3 : Committer**

```bash
git add .env.example README.md
git commit -m "docs: paramètres Extract (.env) et prérequis OLLAMA_CONTEXT_LENGTH"
```

---

## Task 6 : Validation end-to-end (manuelle, hors CI)

Le serveur Ollama doit tourner avec `OLLAMA_CONTEXT_LENGTH ≥ 32768` et un `.env` valide pointant `qwen3.6`.

- [ ] **Step 1 : Lancer un run complet sur un slug neuf**

Run: `.venv/bin/python dipriserch.py decision-tree`
Expected: logs `[map] ... → N passages` par page, puis `[reduce] N faits, M sections`, puis `[verify] X/N faits confirmés`. Le `passages.json`, `knowledge.json`, `sections_draft.json` sont écrits dans `run/decision-tree/`.

- [ ] **Step 2 : Vérifier qu'au moins quelques faits ont ≥ 2 sources**

Run: `.venv/bin/python -c "import json; f=json.load(open('run/decision-tree/knowledge.json')); print(sum(1 for x in f if len(x['sources'])>=2), '/', len(f), 'faits multi-sources')"`
Expected: un compte multi-sources > 0 (la corroboration fonctionne).

- [ ] **Step 3 : Caler les paramètres si besoin**

Si le REDUCE est trop pauvre ou hors-sujet, ajuster `EXTRACT_MAP_K` / `EXTRACT_REDUCE_MAX_CHARS` dans `.env` et relancer `--from extract` (le cache `passages.json` évite de refaire le MAP ; le supprimer pour reforcer le MAP).

---

## Self-Review (rempli par l'auteur du plan)

- **Spec coverage** : MAP verbatim (Task 2) ✓ ; REDUCE (Task 3) ✓ ; params `.env` (Task 1, 5) ✓ ; suppression « équitable par page » (Task 3-4 + grep Task 4 Step 4) ✓ ; garde-fous MAP (Task 2) et REDUCE (Task 3) ✓ ; cache `passages.json` (Task 2) ✓ ; prérequis serveur documenté (Task 5) ✓ ; Verify inchangé (aucune task — correct, déjà en place). ✓
- **Cohérence des noms** : `run_map`, `run_reduce`, `run_extract`, `passages.json`, `cfg["map_k"]/["map_page_cap"]/["reduce_max_chars"]`, constantes `EXTRACT_MAP_K/EXTRACT_MAP_PAGE_CAP/EXTRACT_REDUCE_MAX_CHARS` — identiques entre tasks. ✓
- **Pas de placeholder** : chaque step de code montre le code complet. ✓
