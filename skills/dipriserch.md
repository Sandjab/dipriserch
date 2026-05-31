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

Lire ces deux fichiers pour comprendre le document :
- `run/<slug>/sections_draft.json`
- `run/<slug>/knowledge.json`

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
