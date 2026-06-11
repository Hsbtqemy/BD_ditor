# BD Annotator

Outil de recherche pour l'analyse de bandes dessinées numérisées (corpus
franco-belge). Trois étapes : **segmentation automatique** des planches
(Kumiko), **correction manuelle**, et **annotation humaine** à plusieurs niveaux
hiérarchiques. Aucune IA dans la boucle d'annotation — tout le travail
interprétatif est humain.

## Stack

- **Backend** : FastAPI (Python 3.11+)
- **Base** : SQLite + FTS5 (recherche plein texte)
- **Frontend** : HTML/CSS/JS vanilla (pas de framework)
- **Segmentation** : [Kumiko](https://github.com/njean42/kumiko)
- **Images** : masters TIFF, dérivés JPEG web (25 %)
- **Export** : JSON-LD, CSV, TEI P5 facsimile

## Installation

```bash
pip install -r requirements.txt

# Segmentation automatique (optionnelle au démarrage) :
git clone https://github.com/njean42/kumiko.git lib/kumiko
pip install opencv-python-headless numpy requests   # deps de Kumiko (pas de requirements.txt)
```

## Démarrage

```bash
uvicorn main:app --reload
# puis ouvrir http://127.0.0.1:8000
```

La base `bd_annotator.sqlite` et les dossiers `corpus/` (masters) et
`derivatives/` (dérivés web) sont créés automatiquement au premier lancement.

## Flux de travail

1. **Nouvel album** (＋ dans la barre latérale) → titre, auteur, année.
2. **Importer une planche** (⤓) : dépose un TIFF/PNG/JPEG. Le master est rangé
   dans `corpus/`, un dérivé web JPEG à 25 % est généré dans `derivatives/`.
3. **Segmenter** : lance Kumiko, qui détecte les cases. Les coordonnées sont
   reconverties en pixels master avant stockage.
4. **Mode Édition (E)** : corriger les cases (poignées de redimensionnement,
   saisie numérique des coordonnées), dessiner de nouvelles régions au
   cliquer-glisser, supprimer (Suppr). Passer le statut à `corrigee`.
5. **Mode Annotation (A)** : sélectionner une région, lui attribuer des tags
   (vocabulaire cumulatif avec autocomplétion) et une note libre. Sauvegarde
   automatique (debounce 500 ms).
6. **Mode Navigation (N)** : zoom molette, pan au cliquer-glisser, navigation
   entre régions aux flèches ← →, descente dans la hiérarchie (case → bulles /
   personnages) via le fil d'Ariane.

## Modèle de données

`albums → planches → regions` (arbre via `parent_id`) `→ annotations → tags`
(N-N). Coordonnées **toujours en pixels master** ; la conversion master↔web est
faite côté frontend (`web_scale = web_width / master_width`).

La table FTS5 `recherche` agrège texte OCR + note + tags ; elle est maintenue
explicitement par `database.reindex_region()` / `unindex_region()`.

## API

| Méthode | Route | Rôle |
|---|---|---|
| `GET/POST` | `/api/albums` | liste / création d'albums |
| `GET` | `/api/albums/{id}/planches` | planches d'un album |
| `POST` | `/api/albums/{id}/import` | import d'une planche (multipart) |
| `POST` | `/api/planches/{id}/segmenter` | lancer Kumiko |
| `GET/POST` | `/api/planches/{id}/regions` | régions / création manuelle |
| `PUT/DELETE` | `/api/regions/{id}` | modifier / supprimer une région |
| `PATCH` | `/api/planches/{id}/statut` | statut (`importee→segmentee→corrigee→annotee`) |
| `GET/PUT` | `/api/regions/{id}/annotation` | lire / écrire l'annotation |
| `GET/POST` | `/api/tags` | tags (avec fréquences) |
| `GET` | `/api/recherche?q=&album=&type=&tags=` | recherche FTS5 |
| `GET` | `/api/export/{json,csv,tei}?album_id=` | export |
| `GET` | `/api/sante` | disponibilité de Kumiko |

Documentation interactive : `http://127.0.0.1:8000/docs`.

## Structure

```
bd_annotator/
├── main.py              # app FastAPI + routes
├── database.py          # init SQLite, schéma, FTS5, helpers
├── config.py            # chemins & constantes partagés
├── pipeline/
│   ├── ingest.py        # TIFF → dérivé web + métadonnées
│   └── segmentation.py   # wrapper Kumiko + insertion régions
├── templates/index.html  # shell HTML
├── static/
│   ├── viewer.js        # visionneuse + 3 modes + annotation
│   └── style.css        # thème sombre
├── corpus/              # (gitignore) masters TIFF
└── derivatives/         # (gitignore) dérivés web
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest                     # toute la suite (79 tests, ~7 s)
pytest -m "not live"       # sans le test d'intégration (pas de serveur lancé)
pytest --cov=. --cov-report=term-missing   # couverture (100 %)
```

La suite (`tests/`) couvre le schéma SQLite + FTS5, le pipeline (ingestion,
segmentation Kumiko), toutes les routes API, et un test de non-régression par
bug corrigé (`tests/test_regressions.py`). `tests/test_live_race.py` lance un
vrai serveur uvicorn isolé (via `BD_DATA_DIR`/`BD_DB_PATH`) pour vérifier la
cohérence écriture→lecture — chose que `TestClient` ne peut pas reproduire. Les
tests de segmentation sont automatiquement ignorés si Kumiko n'est pas installé.

Les données sont configurables par variables d'environnement :
`BD_DATA_DIR` (racine corpus/derivatives/base) et `BD_DB_PATH` (base SQLite).

## Notes

- **Sans Kumiko**, tout fonctionne sauf la segmentation automatique : on peut
  créer les régions manuellement en mode Édition. `/api/sante` indique si
  Kumiko est détecté.
- Les tags sont insensibles à la casse et stockés en minuscules ; un tag
  s'applique à n'importe quel niveau de la hiérarchie. Aucune taxonomie n'est
  imposée — les catégories émergent du corpus.
