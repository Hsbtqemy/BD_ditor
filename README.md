# BD Annotator

Outil de recherche pour l'analyse de bandes dessinées numérisées (corpus
franco-belge). Trois étapes : **segmentation automatique** des planches
(Kumiko), **correction manuelle**, et **annotation humaine** à plusieurs niveaux
hiérarchiques. Aucune IA dans la boucle d'annotation — tout le travail
interprétatif est humain.

## Spécifications techniques

### Langage & exécution

Python 3.12 · frontend JavaScript/HTML/CSS **vanilla** (aucun framework, aucun
build) · auto-hébergé, traitement 100 % local.

### Serveur / API

| Composant | Version | Rôle |
|---|---|---|
| FastAPI | ≥ 0.110 | API REST + service templates/statics |
| Uvicorn | ≥ 0.27 (`[standard]`) | serveur ASGI |
| Pydantic | via FastAPI | validation des modèles d'entrée |
| python-multipart | ≥ 0.0.9 | upload de fichiers (import multipart) |

### Données

- **SQLite** — fichier unique, mode **WAL**, `foreign_keys=ON` + `ON DELETE CASCADE`
- Recherche plein texte **SQLite FTS5** (table `recherche` : OCR + note + tags)
- **Pillow** ≥ 10 — masters TIFF/scan + dérivés web **JPEG 25 % / qualité 82**
- Régions stockées en **pixels MASTER** (indépendantes du dérivé)
- Sauvegarde par **`VACUUM INTO`** (snapshot cohérent) → **zip** horodaté

### Pipeline de reconnaissance (3 passes, optionnelles, CPU)

| Passe | Spec | Détail |
|---|---|---|
| 1 · Cases | [Kumiko](https://github.com/njean42/kumiko) | sous-processus ; `opencv-python-headless`, `numpy`, `requests` |
| 2 · Bulles | `ogkalu/comic-speech-bubble-detector-yolov8m` | YOLOv8, **Apache-2.0** ; `ultralytics` ≥ 8.0 + `huggingface_hub` ≥ 0.20 |
| 3 · OCR | **EasyOCR** ≥ 1.7 | français, CPU ; pré-remplissage éditable |

### Réseau & intégration

**httpx** ≥ 0.27, client **WebDAV** (RFC 4918) pour ShareDocs Huma-Num :
`PROPFIND` (lister) · `GET` (télécharger) · `PUT` (déposer), **Basic Auth**.
Identifiants gardés **en mémoire serveur uniquement** (jamais sur disque).

### Export

JSON-LD · CSV · TEI P5 (facsimile).

### Tests & qualité

**pytest** ≥ 8.0 + **pytest-cov** ≥ 4.0 (couverture 100 %) · FastAPI **TestClient** ·
httpx **MockTransport** (WebDAV simulé) · **Playwright** + Edge headless
(vérification visuelle du frontend).

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
2. **Importer des planches** — en local (⤓, dépose un TIFF/PNG/JPEG) ou depuis
   **ShareDocs** (bouton *ShareDocs* → connexion → navigation → sélection multiple
   → import vers un album existant ou nouveau). Le master est rangé dans `corpus/`,
   un dérivé web JPEG à 25 % est généré dans `derivatives/`.
3. **Reconnaissance** (3 passes, cf. plus bas) : **Segmenter** (cases, Kumiko) →
   **Bulles** (ogkalu YOLOv8) → **OCR** (EasyOCR, pré-remplit le texte). L'**ordre
   de lecture** (rangées haut→bas, gauche→droite ; bulles groupées par case) est
   recalculé automatiquement après chaque passe.
4. **Mode Édition (E)** : corriger les régions (poignées de redimensionnement,
   saisie numérique des coordonnées), dessiner de nouvelles régions au
   cliquer-glisser, supprimer (Suppr). Passer le statut à `corrigee`.
5. **Mode Annotation (A)** : sélectionner une région, lui attribuer des tags
   (vocabulaire cumulatif avec autocomplétion) et une note libre. Sauvegarde
   automatique (debounce 500 ms).
6. **Mode Transcription (T)** : correction rapide de l'OCR bulle à bulle, en plein
   écran — crop net (résolution master) + éditeur, navigation Tab / Maj+Tab,
   enchaînement possible sur tout l'album. Sauvegarde automatique.
7. **Mode Navigation (N)** : zoom molette, pan au cliquer-glisser, navigation aux
   flèches ← →. Le panneau droit affiche l'**arbre de structure** de la planche
   (planche → cases → bulles, avancement OCR par case) : clic = sélection +
   recentrage, survol = surbrillance dans l'image, et **réordonnancement manuel**
   (↑/↓ ou Alt+↑/↓, bouton « recalculer l'ordre »).
8. **Sauvegarde / archivage** : bouton *Sauvegarde* (télécharge un snapshot
   `.sqlite` zippé) et, dans l'explorateur ShareDocs, *💾 Sauvegarde ici* (dépôt
   WebDAV de la sauvegarde dans un dossier inscriptible).

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
| `POST` | `/api/planches/{id}/segmenter` | passe 1 — cases (Kumiko) |
| `POST` | `/api/planches/{id}/detecter-bulles` | passe 2 — bulles (ogkalu YOLOv8) |
| `POST` | `/api/planches/{id}/ocr` | passe 3 — pré-remplit `ocr_texte` (EasyOCR) |
| `POST` | `/api/planches/{id}/reordonner` | recalcul de l'ordre de lecture |
| `GET/POST` | `/api/planches/{id}/regions` | régions / création manuelle |
| `PUT/DELETE` | `/api/regions/{id}` | modifier / supprimer une région |
| `POST` | `/api/regions/{id}/deplacer` | réordonner une région (↑/↓) |
| `GET` | `/api/regions/{id}/crop` | crop net (master) pour la transcription |
| `PATCH` | `/api/planches/{id}/statut` | statut (`importee→segmentee→corrigee→annotee`) |
| `GET/PUT` | `/api/regions/{id}/annotation` | lire / écrire l'annotation |
| `GET/POST` | `/api/tags` | tags (avec fréquences) |
| `GET` | `/api/recherche?q=&album=&type=&tags=` | recherche FTS5 |
| `GET` | `/api/export/{json,csv,tei}?album_id=` | export |
| `GET/POST` | `/api/sharedocs/{etat,connexion,deconnexion}` | session WebDAV ShareDocs (RAM only) |
| `GET/POST` | `/api/sharedocs/{liste,importer}` | explorer / importer depuis ShareDocs |
| `GET` | `/api/sauvegarde` | télécharger une sauvegarde (`.sqlite` zippé) |
| `POST` | `/api/sharedocs/deposer-sauvegarde` | déposer la sauvegarde sur ShareDocs |
| `GET` | `/api/sante` | disponibilité des moteurs (kumiko / bulles / ocr) |

Documentation interactive : `http://127.0.0.1:8000/docs`.

## Structure

```
bd_annotator/
├── main.py              # app FastAPI + routes
├── database.py          # init SQLite, schéma, FTS5, helpers
├── config.py            # chemins & constantes partagés
├── pipeline/
│   ├── ingest.py        # image → dérivé web + métadonnées
│   ├── segmentation.py  # wrapper Kumiko (cases)
│   ├── bulles.py        # détection des bulles (ogkalu YOLOv8)
│   ├── ocr.py           # OCR EasyOCR + crop net master
│   ├── ordering.py      # ordre de lecture (recalcul auto + déplacement)
│   ├── sharedocs.py     # client WebDAV ShareDocs (explorer / import / dépôt)
│   └── backup.py        # snapshot SQLite (VACUUM INTO) zippé
├── templates/index.html  # shell HTML
├── static/
│   ├── viewer.js        # visionneuse + modes + arbre + ShareDocs
│   └── style.css        # thème sombre
├── corpus/              # (gitignore) masters TIFF
└── derivatives/         # (gitignore) dérivés web
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest                     # toute la suite (157 tests)
pytest -m "not live"       # sans le test d'intégration (pas de serveur lancé)
pytest --cov=. --cov-report=term-missing   # couverture (100 %)
```

La suite (`tests/`, **157 tests, couverture 100 %**) couvre le schéma SQLite +
FTS5, le pipeline (ingestion, segmentation Kumiko, détection de bulles, OCR,
ordre de lecture), la sauvegarde et l'intégration **ShareDocs** (WebDAV simulé
via httpx `MockTransport`, sans réseau réel), toutes les routes API, et un test
de non-régression par bug corrigé (`tests/test_regressions.py`).
`tests/test_live_race.py` lance un vrai serveur uvicorn isolé (via
`BD_DATA_DIR`/`BD_DB_PATH`) pour vérifier la cohérence écriture→lecture — chose
que `TestClient` ne peut pas reproduire. Les tests des moteurs ML (Kumiko,
bulles, OCR) sont automatiquement ignorés si le moteur n'est pas installé.

Les données sont configurables par variables d'environnement :
`BD_DATA_DIR` (racine corpus/derivatives/base) et `BD_DB_PATH` (base SQLite).

## Pipeline en 3 passes (moteurs optionnels)

```
import → passe 1 : cases   (Kumiko)            → POST …/segmenter
       → passe 2 : bulles  (ogkalu YOLOv8)     → POST …/detecter-bulles
       → passe 3 : OCR fr  (EasyOCR, par bulle) → POST …/ocr  (pré-remplit ocr_texte)
       → correction + annotation humaines (mode Annotation)
```

Les passes 2 et 3 sont des **moteurs ML optionnels** (`pip install -r
requirements-ocr.txt`, CPU suffisant). Sans eux, l'app tourne et leurs routes
renvoient 503 ; on dessine alors les bulles à la main. **L'OCR n'est qu'un
pré-remplissage éditable** (`only_empty=True` n'écrase jamais une correction
humaine) — la qualité finale vient de la relecture humaine.

## Notes

- **Sans Kumiko**, tout fonctionne sauf la segmentation automatique : on peut
  créer les régions manuellement en mode Édition. `/api/sante` indique si
  Kumiko est détecté.
- Les tags sont insensibles à la casse et stockés en minuscules ; un tag
  s'applique à n'importe quel niveau de la hiérarchie. Aucune taxonomie n'est
  imposée — les catégories émergent du corpus.
