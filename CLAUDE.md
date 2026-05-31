# dipriserch — instructions projet

Pipeline hybride : LLM local/RunPod pour les phases coûteuses, Claude pour la synthèse créative.

## Concept central

Même rigueur de vérification que `scriptorium` (faits confirmés par ≥ 2 sources indépendantes), mais avec
une économie de tokens radicale : Sweep + Extract + Verify sont délégués à un LLM externe via un script
Python appelé par Bash. Claude reprend la main pour les widgets et Compose.

L'output est **un document HTML unique** (`output.html`) mêlant sections rédigées et widgets interactifs,
assemblé par `build.py`. Ce n'est pas le triptyque à 3 éditions de scriptorium : le design a divergé vers
un doc enrichi de widgets.

## Architecture cible

```
Claude          → brief (slug, cadrage, paramètres)
Python/LLM ext  → Sweep (duckduckgo + Jina) + Extract + Verify → knowledge.json + sections_draft.json
Claude          → widgets + Compose (manifest.json)
build.py        → 1 HTML déterministe (sections + widgets)
```

## Contraintes non négociables

- Le LLM externe doit exposer une API compatible OpenAI (Ollama ou RunPod).
- La frontière code/jugement de scriptorium est conservée : `build.py` reste déterministe.
- Tout fait `confirmed` dans `knowledge.json` exige ≥ 2 sources indépendantes — même règle, même structure.

## À ne pas faire

- Ne pas recoder `build.py` — il est déjà implémenté ici et doit rester déterministe (aucune logique LLM).
- Ne pas supposer un modèle spécifique : la cible (Ollama local vs RunPod) est un paramètre de config.
