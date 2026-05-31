# Design — dipriserch

**Date :** 2026-05-31
**Statut :** approuvé

---

## Problème

`scriptorium/triptych` produit des documents vérifiés de haute qualité mais à coût prohibitif (Verify
domine : 50-70 agents × ~70k tokens chacun). De plus, générer 3 éditions HTML complique le pipeline
sans apporter de valeur systématique.

**dipriserch** résout les deux problèmes :
- Délègue les phases token-intensives à un LLM externe (Ollama local ou RunPod)
- Produit 1 seule édition HTML (référence), enrichie de N widgets interactifs inventés par Claude

---

## Architecture globale

```
run/
  <slug>/
    sweep_results.json      ← résultats bruts des recherches web
    knowledge.json          ← faits vérifiés (≥2 sources chacun)
    sections_draft.json     ← sections rédigées par le LLM externe
    widgets/
      widget_<n>.html       ← N widgets générés par Claude
    manifest.json           ← manifeste unique (sections + widgets ordonnés)
    output.html             ← HTML final assemblé par build.py
```

**Flux d'exécution :**

```
Claude (brief)
  → python dipriserch.py <slug> [--from sweep|extract|verify]
      sweep   → sweep_results.json
      extract → knowledge.json + sections_draft.json
      verify  → knowledge.json (mis à jour)
      [stdout : logs de progression + JSON de status sur la dernière ligne]
  → Claude lit sections_draft.json + knowledge.json
  → Claude génère widgets/widget_1.html … widget_N.html
  → Claude écrit manifest.json
  → python build.py run/<slug>/
      → output.html
```

L'argument `--from` permet de reprendre à n'importe quelle phase sans tout refaire.

---

## Découpe des responsabilités

| Phase | Responsable | Outil |
|-------|-------------|-------|
| Brief / cadrage | Claude | SKILL.md |
| Sweep (recherche web) | LLM externe | `duckduckgo-search` + `r.jina.ai` |
| Extract (rédaction sections) | LLM externe | appels JSON structurés |
| Verify (vérification adversariale) | LLM externe | appels JSON structurés |
| Widgets (HTML interactifs, N par doc) | Claude | génération créative libre |
| Compose (manifeste JSON unique) | Claude | logique d'assemblage |
| Build (assemblage HTML) | `build.py` | déterministe, 1 édition référence |

---

## Script `dipriserch.py`

### Config

Fichier `.env` à la racine du projet (ou du run) :

```
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5:32b
LLM_API_KEY=ollama
```

### Phase Sweep

- Génère des requêtes de recherche à partir du slug
- `duckduckgo-search` → liste d'URLs
- `r.jina.ai/<url>` → markdown brut pour chaque page
- Écrit `sweep_results.json`

### Phase Extract

- Le LLM externe lit `sweep_results.json`
- Rédige les sections du document en JSON structuré
- Extrait les faits avec leurs sources
- Écrit `knowledge.json` + `sections_draft.json`

### Phase Verify

- Pour chaque fait dans `knowledge.json`, vérifie ≥ 2 sources indépendantes
- Faits non vérifiés marqués `"confirmed": false` (pas supprimés)
- Met à jour `knowledge.json`

### Stdout / stderr

- **Stdout :** logs human-readable ligne par ligne (`[sweep] 12 pages fetched`, `[verify] 34/40 facts confirmed`) + JSON de status sur la dernière ligne
- **Stderr :** messages d'erreur fatale uniquement

### Exit codes

| Code | Signification |
|------|---------------|
| `0` | Succès complet |
| `1` | Erreur fatale |
| `2` | Succès partiel (ex. ratio de faits confirmés insuffisant) |

---

## Phase Claude — Widgets + Compose

### Étape 1 — Analyse du draft

Claude lit `sections_draft.json` et `knowledge.json`. Pour chaque section/concept, il évalue si le
principe est plus clair montré qu'expliqué. Critères orientateurs :

- Algorithme avec états successifs (tri, parsing, rétropropagation…)
- Formule avec paramètres manipulables
- Relation spatiale ou graphique (construction de graphe…)
- Comparaison interactive (avant/après, A vs B)

### Étape 2 — Génération des widgets

Pour chaque principe retenu, Claude invente le type de widget le plus pédagogiquement adapté et génère
`widgets/widget_<n>.html` — HTML+CSS+JS autonome, aucune dépendance externe.

Chaque widget est accompagné d'un bloc metadata dans `manifest.json` :

```json
{
  "id": "widget_1",
  "title": "Rétropropagation pas à pas",
  "anchor": "backprop",
  "after_section": "section_3"
}
```

### Étape 3 — Compose

Claude écrit `manifest.json` : liste ordonnée des sections (depuis `sections_draft.json`) avec les
widgets intercalés après la section qui introduit le principe illustré.

---

## `build.py` — Assemblage HTML

`build.py` est copié depuis scriptorium (pas importé). Il reste entièrement déterministe.

**Inputs :**
- `manifest.json`
- `sections_draft.json`
- `widgets/widget_<n>.html`
- Charte CSS (copiée depuis scriptorium)

**Output :** `output.html` auto-contenu (CSS inline, widgets injectés).

**Logique :**
1. Lire `manifest.json` dans l'ordre
2. Entrée `section` → injecter le HTML rendu depuis le markdown
3. Entrée `widget` → injecter dans `<div class="widget-container">` avec titre et ancre
4. Générer une table des matières (sections + ancres widgets)
5. Écrire `output.html`

`build.py` refuse de tourner si un widget référencé dans le manifeste est absent — erreur explicite.

---

## Gestion des erreurs et résilience

Claude est le coordinateur : en cas d'échec du script, il lit stderr, évalue la situation et décide.

| Situation | Exit code | Comportement Claude |
|-----------|-----------|---------------------|
| Succès complet | `0` | Passe à la génération widgets |
| Erreur réseau (Jina/DDG) | `1` | Relance avec `--from sweep` |
| LLM externe injoignable | `1` | Signale, propose de vérifier `.env` |
| Trop peu de faits confirmés | `2` | Affiche le ratio, demande confirmation |
| Crash mid-extract | `1` | Relance avec `--from extract` |

**Cache implicite :** les fichiers intermédiaires servent de cache naturel via `--from`. Pas de logique
de cache explicite.

**Widgets partiels :** si Claude s'interrompt en cours de génération, le prochain run reprend depuis
`manifest.json` existant. `build.py` valide la présence de tous les widgets avant de démarrer.

---

## Dépendances

- `duckduckgo-search` — recherche gratuite sans clé API
- `r.jina.ai/<url>` — lecture de pages web en markdown, gratuit
- `openai` Python SDK — compatible Ollama et RunPod (`base_url` configurable)
- `python-dotenv` — lecture du `.env`
- `build.py` + charte CSS depuis scriptorium (copiés)
