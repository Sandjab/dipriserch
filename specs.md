# Specs — dipriserch

## Problème

`scriptorium/triptych` produit des documents vérifiés de haute qualité mais consomme des millions de tokens
Claude (Verify domine : 50-70 agents × ~70k tokens chacun). Sur des sujets peu critiques ou à fort volume,
ce coût est prohibitif.

## Solution envisagée

Déléguer les phases token-intensives à un LLM local (Ollama) ou hébergé (RunPod, API OpenAI-compatible),
en conservant Claude pour les tâches où sa qualité justifie le coût.

## Découpe des responsabilités

| Phase | Responsable | Outil |
|-------|-------------|-------|
| Brief / cadrage | Claude | SKILL.md |
| Sweep (recherche web) | LLM externe | `duckduckgo-search` + `r.jina.ai` |
| Extract (rédaction sections) | LLM externe | appels JSON structurés |
| Verify (vérification adversariale) | LLM externe | appels JSON structurés |
| Widget (HTML interactif) | Claude | génération créative |
| Compose (manifestes JSON) | Claude | logique d'édition |
| Build (assemblage HTML) | `build.py` | déterministe, inchangé |

## Dépendances connues

- `duckduckgo-search` — recherche gratuite sans clé API
- `r.jina.ai/<url>` — lecture de pages web en markdown, gratuit
- `openai` Python SDK — compatible Ollama (`base_url=http://localhost:11434/v1`) et RunPod
- `build.py` + charte CSS depuis scriptorium

## Questions ouvertes (à brainstormer)

- Structure du repo : script Python monolithique ou package ?
- Interface Claude ↔ script : Bash pur, MCP server, ou autre ?
- Gestion des erreurs : que fait Claude si le script Python échoue en cours de route ?
- Config LLM : fichier `.env`, argument CLI, ou settings Claude ?
- Qualité de Verify avec un modèle local : seuil minimum de taille/capacité à documenter ?
- Réutilisation de `knowledge.json` entre runs (cache) ?
- Format de retour du script vers Claude : stdout JSON, fichiers sur disque, ou les deux ?
