# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Langue

Tout le projet est en **français** : commentaires, docstrings, noms de fonctions/variables/routes/colonnes, UI, messages d'erreur, commits, docs. Écris dans le même registre — code, commentaires et messages de commit en français.

## Vue d'ensemble

Outil de recherche pour annoter des bandes dessinées numérisées (corpus franco-belge). Aucune IA dans la boucle d'annotation : le travail interprétatif est 100 % humain ; les moteurs ML ne font que du **pré-remplissage éditable**. Auto-hébergé, traitement local, mono-utilisateur par défaut (pas d'authentification dans le code — voir `docs/hebergement-securite.md`).

Backend **Python 3.12 / FastAPI** ; frontend **JavaScript/HTML/CSS vanilla** — aucun framework, **aucune étape de build**. On édite `static/*.js` et `templates/*.html` directement.

## Commandes

```bash
# Lancer (base + dossiers data créés au 1er démarrage)
uvicorn main:app --reload          # → http://127.0.0.1:8000 (API docs : /docs)

# Dépendances
pip install -r requirements.txt          # noyau (FastAPI, Pillow, httpx)
pip install -r requirements-dev.txt      # + pytest, playwright
pip install -r requirements-ocr.txt      # moteurs ML optionnels (bulles YOLOv8, EasyOCR)
pip install -r requirements-nlp.txt && python -m spacy download fr_core_news_sm  # NLP optionnel

# Kumiko (segmentation auto, optionnelle) — cloné à part, pas de requirements.txt
git clone https://github.com/njean42/kumiko.git lib/kumiko
pip install opencv-python-headless numpy requests
```

### Tests

```bash
pytest                       # suite par défaut (exclut e2e ; INCLUT le test `live` = serveur uvicorn en sous-processus)
pytest -m "not live"         # sans le test d'intégration sous-processus
pytest -m e2e                # E2E navigateur Playwright (nécessite : python -m playwright install chromium)
pytest tests/test_api.py::test_nom_du_test      # un seul test
pytest --cov=. --cov-report=term-missing        # couverture (dépend des moteurs optionnels installés)
```

- Le marqueur `e2e` est exclu par défaut via `pytest.ini` (`addopts = -m "not e2e"`).
- **Tests JS purs** (`static/lib/*.js`) : lancés par `tests/test_js_unit.py`, qui appelle `node --test tests/js/*.test.js`. Skippés proprement si Node absent. Pas de runner JS séparé.
- **Accessibilité** : `tests/test_e2e_a11y.py` (marqueur `e2e`) audite les 4 surfaces × thèmes (sombre/clair) via **axe-core** (WCAG 2.1 AA) et échoue à toute violation sérieuse/critique. axe est **vendu hors ligne** dans `tests/js/vendor/axe.min.js` (skip si absent — cf. son README).
- Les tests des moteurs ML (Kumiko, bulles, OCR) et du NLP se **skippent automatiquement** si le moteur n'est pas installé (`requires_kumiko` / `requires_bulles` / `requires_ocr` dans `tests/conftest.py`). La couverture mesurée en dépend (les routes `/api/analyse/*` + correction de tokens ne sont pas encore couvertes — cf. `docs/backlog.md` QA-3).

## Architecture

### Les quatre surfaces (pages)

Routes HTML servies par `main.py`, chacune avec son fichier JS et son template, partageant `static/style.css` et `static/theme.js` (thèmes clair/sombre + contraste élevé + zoom UI, et nav transverse + skip-link injectés sur les 4 pages) :

| Route | Template | JS | Rôle |
|---|---|---|---|
| `/` | `index.html` | `viewer.js` | **Visionneuse** : modes Édition / Annotation / Transcription / Navigation, arbre de structure, ShareDocs, deep-link |
| `/recherche` | `recherche.html` | `recherche.js` | **Recherche** FTS5 + nuage de tags |
| `/corpus` | `corpus.html` | `corpus.js` | **Bibliothèque** : CRUD albums/planches + lancement de lots |
| `/exploration` | `exploration.html` | `exploration.js` | **Exploration** linguistique du corpus (fréquences, concordance, comparaison) |

`static/lib/` contient des modules **UMD réutilisables et testés sous Node** (pas d'accès DOM au chargement) : `nav.js` (navigation/round-trip entre surfaces) et `dialog.js` (modale accessible : piège à focus, Échap, retour du focus). Leur logique pure est verrouillée par `tests/js/*.test.js`.

### Données : tout en pixels MASTER

`albums → planches → regions` (arbre hiérarchique via `regions.parent_id`) `→ annotations → tags` (N-N). Les coordonnées `x,y,w,h` des régions sont **toujours en pixels master** (le scan haute résolution), indépendantes du dérivé web. La conversion master↔web se fait **côté frontend** : `web_scale = web_width / master_width`. Ne jamais stocker de coordonnées web.

Le master TIFF va dans `corpus/`, un dérivé web JPEG à 25 % (`WEB_SCALE` dans `config.py`) dans `derivatives/` ; les deux dossiers sont gitignore.

### Recherche FTS5 — index maintenu explicitement

La table virtuelle FTS5 `recherche` est **dénormalisée** (agrège OCR + note + tags + lemmes). Elle est maintenue **à la main** via `database.reindex_region()` / `unindex_region()` appelés depuis l'API — **pas par des triggers** (la relation N-N tags les rendrait fragiles). Toute route qui modifie le texte/les tags/la note d'une région doit réindexer. Tokenizer `unicode61 remove_diacritics 2` → recherche insensible aux accents.

### Schéma & migrations

`database.py` : `SCHEMA_VERSION` (actuellement 14). À tout changement structurel : incrémenter et ajouter une étape dans `_migrate()`. Conventions :
- La table FTS est **séparée** du schéma (`_FTS_SQL`) pour pouvoir la **recréer en migration** (le tokenizer est figé à la création).
- Les **vues** (`_VIEWS_SQL`) sont **toujours DROP+CREATE** au démarrage : sans données, leur définition évolue gratuitement, sans migration.

### Couche NLP (spaCy) — OPTIONNELLE, deux paliers

`pipeline/nlp.py`. Sans spaCy/modèle, `nlp_available()` est False et tout retombe proprement sur la recherche préfixe + accents.
- **Palier A (lemmes)** : indexés dans FTS pour que « otage » trouve « otages ». Le lettrage BD étant en capitales, on **minuscule avant** analyse (sinon tout est pris pour des noms propres).
- **Palier B (grammaire)** : table `tokens` (un mot du dialogue : lemme, POS/UPOS, morph), **régénérée à chaque reindex**. La correction humaine vit dans `token_correction`, une couche **overlay JAMAIS touchée par le reindex**. La vue `tokens_effectifs` est le **read model canonique** (correction vivante ⊕ auto + provenance + `a_revoir`) : toutes les surfaces d'analyse lisent CECI, jamais `tokens` brut.
- Le modèle est configurable (`BD_SPACY_MODEL`, défaut `fr_core_news_sm`), chargé paresseusement sous verrou (non thread-safe). `tools/reindex_nlp.py` réindexe tout le corpus en lot après un changement de paramètre.

### Pipeline de reconnaissance — 3 passes, moteurs OPTIONNELS

`pipeline/` : `ingest.py` (image → dérivé + métadonnées), puis 3 passes ML : `segmentation.py` (passe 1, cases, **Kumiko** en sous-processus), `bulles.py` (passe 2, **ogkalu YOLOv8**), `ocr.py` (passe 3, **EasyOCR** fr). `ordering.py` recalcule l'ordre de lecture (rangées haut→bas, gauche→droite ; bulles groupées par case) après chaque passe.

Invariants :
- Chaque moteur est **optionnel** : si non installé, sa route renvoie **503** ; `GET /api/sante` indique la disponibilité de chacun.
- **L'OCR ne fait que pré-remplir** (`only_empty=True`) : il **n'écrase jamais** une correction humaine.
- `pipeline/jobs.py` : traitement **par lot en arrière-plan** (`threading`, worker sérialisé, multi-albums) avec progression et annulation. Sérialisé par un `ML_LOCK`.

### Concurrence SQLite

Fichier unique, mode **WAL**, `foreign_keys=ON` + `ON DELETE CASCADE`, `busy_timeout=5000`. Un job ML de fond peut entrer en contention avec une requête : `main.py` a un `@app.exception_handler(sqlite3.OperationalError)` qui transforme un « database is locked/busy » en **409** explicite (réessayer) plutôt qu'un 500. Le chargement à froid de spaCy (~10 s) doit se faire **hors transaction d'écriture** (`nlp.ensure_loaded()` / `prewarm()`), sinon il bloque les écritures concurrentes.

### Chemins : code vs données (`config.py`)

Les chemins de **code** (`static/`, `templates/`, `lib/kumiko`) sont relatifs au dépôt (`BASE_DIR`). Les chemins de **données** dérivent de `DATA_DIR`, **configurable** :
- `BD_DATA_DIR` : racine de `corpus/` + `derivatives/` + base (défaut : le dépôt). Un chemin relatif est résolu contre le dépôt, pas contre le CWD.
- `BD_DB_PATH` : chemin explicite de la base SQLite.

Ces variables servent à isoler les tests (`tests/conftest.py` les patche ou lance un serveur isolé) et à déployer les données ailleurs que dans le dépôt.

### Numérotation éditoriale & citation

Une planche a un `role` (`recit` = narrative/numérotée ; sinon paratexte, écarté de la numérotation). Le **numéro éditorial est DÉRIVÉ, jamais stocké** (`database.numeros_editoriaux()` : rang parmi les planches `recit`). Les citations `pl·c` / `pl·c·b` sont aussi dérivées (`citations_regions()`). Voir `docs/numerotation-et-citation.md`.

### ShareDocs (WebDAV)

`pipeline/sharedocs.py` : client WebDAV (RFC 4918) pour ShareDocs Huma-Num — `PROPFIND` / `GET` / `PUT`, Basic Auth. Les identifiants restent **en mémoire serveur uniquement, jamais sur disque**. Les tests le simulent via httpx `MockTransport` (aucun réseau réel).

### Sauvegarde

`pipeline/backup.py` : snapshot SQLite cohérent par `VACUUM INTO` → zip horodaté. Téléchargeable (`/api/sauvegarde`) ou déposable sur ShareDocs.

## Conventions de code

- **Routes API** : préfixe `/api/`, verbes/noms en français (`/api/planches/{id}/segmenter`, `/deplacer`, `/reordonner`). Pages HTML sans préfixe.
- Pas de cache sur les assets : un middleware force `Cache-Control: no-cache` sur `/static` et les pages, car le navigateur intégré d'un IDE sert sinon des CSS/JS périmés.
- Export disponible en **JSON-LD / CSV / TEI P5** (`main.py`, routes `/api/export/*`).
- `tests/test_regressions.py` : un test de non-régression par bug corrigé.
- **Accessibilité (WCAG 2.1 AA)** : les accents pleins `--accent-*` servent les fills / bordures / marqueurs (seuil graphique 3:1) ; pour du **petit texte** coloré, utiliser les tokens d'encre AA-sûrs (`--ink-red`, `--danger`, ou un accent **assombri** en thème clair) — **jamais l'accent brut**, qui échoue le 4.5:1. L'audit axe (`pytest -m e2e`) verrouille la non-régression.
- `docs/` documente les décisions de conception non évidentes (grammaire, numérotation, round-trip, sécurité, Docker) ; `docs/backlog.md` est le **suivi vivant** ticket-par-ticket (features + dette technique/sécurité §7), `docs/roadmap.md` la **vue stratégique par pistes** (cap + ordre conseillé), `AUDIT.md` l'audit technique daté. `spike/` et `tools/` sont hors couverture (`.coveragerc`). L'**export de métadonnées** (description du corpus + IIIF ; scripts hors-app `tools/description_collection.py`, `metadonnees_collection.py`, `iiif_manifest.py`, `valider_iiif.py`) est documenté dans `docs/export-metadonnees.md`.
