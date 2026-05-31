# dipriserch

Pipeline hybride recherche → document, conçu pour minimiser le coût en tokens Claude.

Les phases lourdes (recherche web, extraction, vérification adversariale) tournent sur un LLM local ou RunPod.  
Claude Code gère la préparation, la création des widgets et l'assemblage final.

## Prérequis serveur (Ollama)

Le serveur Ollama doit tourner avec une fenêtre de contexte suffisante :

    OLLAMA_CONTEXT_LENGTH >= 32768

Le client (dipriserch) **ne peut pas** forcer le contexte par requête : l'endpoint
OpenAI-compatible d'Ollama ignore `num_ctx`. La cohérence entre ce réglage serveur et
`EXTRACT_REDUCE_MAX_CHARS` (client) relève du déploiement — au-delà de la fenêtre serveur,
le prompt est tronqué silencieusement.

## Paramètres Extract (`.env`, optionnels)

| Variable | Rôle | Défaut |
|---|---|---|
| `EXTRACT_MAP_K` | passages verbatim extraits par page (MAP) | 8 |
| `EXTRACT_MAP_PAGE_CAP` | cap chars/page au MAP | 60000 |
| `EXTRACT_REDUCE_MAX_CHARS` | budget total passé au REDUCE | 32000 |

**Statut : spécification en cours.**
