# dipriserch — instructions projet

Pipeline hybride : LLM local/RunPod pour les phases coûteuses, Claude pour la synthèse créative.

## Concept central

Même output que `scriptorium/triptych` (3 éditions HTML vérifiées), mais avec une économie de tokens
radicale : Sweep + Extract + Verify sont délégués à un LLM externe via un script Python appelé par Bash.
Claude reprend la main pour le widget, Compose et Build.

## Architecture cible

```
Claude          → brief (slug, cadrage, paramètres)
Python/LLM ext  → Sweep (duckduckgo + Jina) + Extract + Verify → knowledge.json + sections_draft.json
Claude          → widget + Compose (manifestes)
build.py        → 3 HTML déterministes
```

## Contraintes non négociables

- Le LLM externe doit exposer une API compatible OpenAI (Ollama ou RunPod).
- La frontière code/jugement de scriptorium est conservée : `build.py` reste déterministe.
- Tout fait `confirmed` dans `knowledge.json` exige ≥ 2 sources indépendantes — même règle, même structure.

## À ne pas faire

- Ne pas recoder `build.py` — il sera importé ou copié depuis scriptorium.
- Ne pas supposer un modèle spécifique : la cible (Ollama local vs RunPod) est un paramètre de config.
