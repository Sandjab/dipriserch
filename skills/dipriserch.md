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
- Exit code 1 + stderr → diagnostiquer :
  - Erreur config LLM (connexion refusée, clé manquante) → demander correction `.env`, relancer sans `--from`
  - Erreur réseau (Jina/DDG) → relancer avec `--from sweep`
  - Crash mid-extract → relancer avec `--from extract`
  - Crash mid-verify → relancer avec `--from verify`

## 3. Lire le contenu extrait

Lire ces deux fichiers pour comprendre le document :
- `run/<slug>/sections_draft.json`
- `run/<slug>/knowledge.json`

## 4. Générer les widgets (phase créative)

Pour chaque section ou concept dans `sections_draft.json`, évaluer :
**Ce principe est-il plus clair montré qu'expliqué ?**

Si oui → inventer le widget le plus pédagogiquement adapté et le coder.

**Critères orientateurs — ne générer un widget QUE si l'un d'eux s'applique clairement :**
- Algorithme avec états successifs → simulation pas à pas
- Formule avec paramètres → sliders interactifs
- Relation spatiale/graphique → visualisation manipulable
- Comparaison → vue avant/après

Si aucun critère ne s'applique, laisser la section en texte seul.

**Règles de génération :**
- Chaque widget est un fichier HTML+CSS+JS autonome, sans dépendance externe CDN
- Nommer les fichiers `widget_1.html`, `widget_2.html`, etc. — l'ID dans manifest (`widget_1`) doit correspondre exactement au nom de fichier sans `.html`
- Créer `run/<slug>/widgets/` et placer les fichiers dedans
- Les widgets existants (fichiers déjà présents) ne sont pas regénérés

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

Règle de placement : un widget suit immédiatement la section qui **définit** le concept ou la formule qu'il visualise (pas seulement la mentionne — la section où le concept est expliqué pour la première fois).
Les IDs de section proviennent de `sections_draft.json` (ne pas inventer de nouveaux IDs).
Les ancres sont les IDs sans le préfixe `section_`, en kebab-case.

## 6. Assembler le HTML final

```bash
python build.py run/<slug>/
```

Vérifier que `run/<slug>/output.html` est généré sans erreur.
Signaler à l'utilisateur : chemin du fichier, nombre de widgets intégrés.
