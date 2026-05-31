# Design — Extract en map-reduce verbatim (dipriserch)

Date : 2026-05-31

## Contexte et problème

La phase **Extract** transforme les 12-15 pages web récupérées par le Sweep
(~352k chars nettoyés / ~88k tokens) en `knowledge.json` (faits) + `sections_draft.json`,
avec la règle non-négociable : un fait `confirmed` exige **≥ 2 sources indépendantes**.

Deux approches naïves échouent :

- **« Tout en un appel »** : dépasse le contexte exploitable, lent au prefill, sujet au
  *lost-in-the-middle*.
- **« Début de chaque page tronqué »** (stratégie « équitable par page » actuelle,
  `markdown[:per_page]`) : **troncature positionnelle aveugle** → rate les faits situés
  en milieu ou en conclusion de page.

### Découverte de session (qui débloque le design)

Le plafond observé en cours de debug (~32k chars fiables) venait de
`OLLAMA_CONTEXT_LENGTH=16384` côté serveur — **et non d'une limite du modèle**.
L'endpoint OpenAI-compat d'Ollama **ignore** `extra_body={"options":{"num_ctx":...}}`,
donc tous les tests « à 32768 » tournaient en réalité à 16384. À 32768 réel, le modèle
traite ~80k chars de façon fiable.

Mais augmenter le contexte indéfiniment coûte cher : la **vitesse de prefill** croît avec
la longueur, et la **qualité** se dégrade (*lost-in-the-middle*) bien avant la limite
technique (qwen3.6 : 262144). Le bon réglage est le **minimum suffisant** (~32-64k tokens),
pas le maximum.

## Décision

**Map-reduce, LLM local uniquement**, où le MAP fait une **extraction verbatim sélective**
par page (et non un résumé reformulé).

Justification du verbatim : la valeur de dipriserch *est* la vérification. Une reformulation
au MAP (a) fait diverger la formulation d'un même fait entre deux pages → le REDUCE corrobore
moins bien, et (b) peut déformer un chiffre/une nuance → le Verify (qui relit le markdown réel)
rejette, ou pire laisse passer un fait faux. Le verbatim préserve la fidélité aux sources.

## Architecture

```
sweep → extract[ MAP → passages.json → REDUCE → knowledge.json + sections_draft.json ] → verify
```

Sweep et Verify sont **inchangés**. Le map-reduce vit entièrement dans la phase Extract.

## MAP — extraction verbatim par page

- **Entrée** : chaque page de `sweep_results.json` (markdown déjà nettoyé par `clean_md`).
- **1 appel LLM par page** avec un nouveau `MAP_PROMPT` :
  > « Extrais les K passages **factuels** les plus importants de cette page sur `<sujet>`,
  > **mot pour mot** (copie exacte, aucune reformulation). Conserve chiffres, dates, noms
  > propres, définitions. Ignore navigation/publicité. »
- **Sortie** : `passages.json = [{ "url": ..., "passages": [str, ...] }]` — passages
  verbatim, étiquetés par leur URL d'origine.
- **Borne** : `K` passages/page pour limiter le volume ; cap par page (~60k chars) pour
  l'edge case d'une page dépassant le contexte du MAP (rare après nettoyage).
- **Cache** : si `passages.json` existe, sauter le MAP (cohérent avec le cache `sweep_results.json`).
- **Garde-fou (fail-loud)** : une page dont le MAP échoue (JSON vide/invalide) est **sautée
  avec log stderr** ; si le nombre total de passages retenus tombe sous un seuil minimal,
  `exit(1)` plutôt que d'alimenter le REDUCE avec du vide.

## REDUCE — extraction + corroboration

- Concatène **tous** les passages verbatim, étiquetés `Source: <url>` (volume cible ~30k chars,
  tient dans un contexte de 32k).
- **1 appel** avec l'`EXTRACT_PROMPT` **actuel** (inchangé) → faits avec **sources multiples**
  + sections.
- Écrit `knowledge.json` + `sections_draft.json`.

Le REDUCE voit ainsi **toutes les sources d'un coup**, sous forme condensée mais **fidèle et
complète** (chaque page a été lue intégralement au MAP), ce qui rend la corroboration ≥ 2
sources naturelle.

## VERIFY — inchangé

Reste l'arbitre final, sur le **markdown réel** (`sweep_results.json`), avec la correction
« budget par source » déjà appliquée (chaque source tronquée à `MAX_SOURCE_CHARS`, pas la
concaténation).

## Changements de code

- `run_extract` éclaté en `run_map` (condensation) + `run_reduce` (extraction), orchestrés
  dans la phase Extract.
- Nouveau `MAP_PROMPT`.
- Nouveau fichier intermédiaire `passages.json`.
- **Suppression** de la stratégie « équitable par page » (le bloc `per_page = MAX_CONTENT_CHARS
  // len(sweep)` + `markdown[:per_page]`).
- `MAX_CONTENT_CHARS` recalibré pour le REDUCE (budget sur les passages, plus sur les pages brutes).
- `--from extract` relance MAP + REDUCE (le cache `passages.json` évite de refaire le MAP si présent).

## Paramètres configurables (`.env`)

Exposés via le `.env` du projet (cohérent avec `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY`),
avec des défauts prudents. Valeurs de départ à affiner par test.

| Variable `.env` | Rôle | Défaut |
|---|---|---|
| `EXTRACT_MAP_K` | nombre de passages verbatim par page (MAP) | `8` |
| `EXTRACT_MAP_PAGE_CAP` | cap chars/page au MAP (edge case page > contexte) | `60000` |
| `EXTRACT_REDUCE_MAX_CHARS` | budget total de contenu passé au REDUCE | `32000` |

Le **contexte du modèle n'est délibérément PAS un paramètre client** : le client ne peut pas
le contrôler (l'endpoint OpenAI-compat d'Ollama **ignore** `extra_body num_ctx`, vérifié
empiriquement). C'est un réglage **serveur** — voir « Dépendances / prérequis de déploiement ».

Autre paramètre, à observer (non exposé au départ) : la longueur max d'un passage verbatim.

## Trade-offs

| Pour | Contre |
|---|---|
| Chaque page lue **intégralement** → aucun fait raté (règle la critique de la troncature) | **~N appels MAP** (14 pages ≈ 14 appels, ~5-8 min sur qwen — gratuit + cacheable) |
| Corroboration **globale** (tous les passages vus ensemble au REDUCE) | Une couche de plus dans le pipeline |
| **Verbatim** → fidélité aux sources, Verify quasi-mécanique | Moins compact qu'un résumé reformulé (absorbé par la marge de contexte) |
| REDUCE réutilise l'`EXTRACT_PROMPT` existant | — |

## Dépendances / prérequis de déploiement

- Le serveur Ollama doit tourner avec **`OLLAMA_CONTEXT_LENGTH ≥ 32768`**. Le client
  (dipriserch) **ne peut pas** forcer le contexte par requête (ignoré par l'endpoint
  OpenAI-compat) — il **subit** le réglage serveur. À documenter explicitement (README).
- Corollaire : `EXTRACT_REDUCE_MAX_CHARS` (+ l'output attendu) doit rester sous cette fenêtre.
  À 32768 de contexte, ~32k chars de REDUCE est sûr (≈ 8k tokens d'input + marge pour l'output).
  Au-delà du réglage serveur, le serveur **tronque silencieusement** — d'où le défaut prudent.

## Lien avec les corrections déjà appliquées (working tree, à committer séparément)

Conservées telles quelles : migration `ddgs` (+ venv Python 3.12 pour le TLS), garde-fous
fail-loud (Sweep vide / Extract contenu insuffisant), `clean_md` (nettoyage des liens/images
Jina), `pyrightconfig` en 3.12, correction Verify « budget par source ».

**Remplacée** par ce design : la stratégie « équitable par page » (cap à 28k + troncature
`per_page`). Le `clean_md` reste en amont (le MAP travaille sur du markdown nettoyé).
