# BD Annotator

Outil de recherche pour l'analyse de bandes dessinées numérisées (corpus
franco-belge). Trois étapes : **segmentation automatique** des planches
(Kumiko), **correction manuelle**, et **annotation humaine** à plusieurs niveaux
hiérarchiques. Aucune IA dans la boucle d'annotation — tout le travail
interprétatif est humain.

L'app s'organise en **trois espaces** : la **Bibliothèque** (`/corpus`) pour
gérer le corpus et lancer des traitements par lot, la **Visionneuse** (`/`) pour
segmenter / corriger / annoter / transcrire, et la **Recherche** (`/recherche`)
pour interroger les dialogues corrigés.

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

Lançables **par planche** (visionneuse) ou **par lot en arrière-plan** depuis la
Bibliothèque — un *job* (`threading`, worker sérialisé) traite un ensemble de
planches multi-albums avec progression et annulation.

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
   **Bulles** (ogkalu YOLOv8) → **OCR** (EasyOCR, pré-remplit le texte), par
   planche ou **par lot** depuis la Bibliothèque. L'**ordre de lecture** (rangées
   haut→bas, gauche→droite ; bulles groupées par case) est recalculé
   automatiquement après chaque passe.
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
9. **Bibliothèque (`/corpus`)** : gérer les albums (créer, éditer les
   métadonnées + description, supprimer) et les planches (ouvrir, supprimer) ;
   **lancer un traitement par lot** (segmentation / bulles / OCR) sur une
   sélection d'albums et/ou de planches, exécuté en **tâche de fond** avec
   barre de progression et annulation.
10. **Recherche (`/recherche`)** : plein texte FTS5 sur dialogues + notes + tags,
    filtres album / type / tags + nuage de tags ; chaque résultat (extrait
    surligné + vignette) **ouvre la visionneuse pile sur la région**.

## Modèle de données

`albums → planches → regions` (arbre via `parent_id`) `→ annotations → tags`
(N-N). Coordonnées **toujours en pixels master** ; la conversion master↔web est
faite côté frontend (`web_scale = web_width / master_width`).

La table FTS5 `recherche` agrège texte OCR + note + tags ; elle est maintenue
explicitement par `database.reindex_region()` / `unindex_region()`.

## API

| Méthode | Route | Rôle |
|---|---|---|
| `GET/POST` | `/api/albums` | liste (+ compteurs) / création d'albums |
| `PUT/DELETE` | `/api/albums/{id}` | éditer les métadonnées / supprimer un album |
| `GET` | `/api/albums/{id}/planches` | planches d'un album |
| `POST` | `/api/albums/{id}/import` | import d'une planche (multipart) |
| `DELETE` | `/api/planches/{id}` | supprimer une planche (+ fichiers, FTS) |
| `POST` | `/api/planches/{id}/segmenter` | passe 1 — cases (Kumiko) |
| `POST` | `/api/planches/{id}/detecter-bulles` | passe 2 — bulles (ogkalu YOLOv8) |
| `POST` | `/api/planches/{id}/ocr` | passe 3 — pré-remplit `ocr_texte` (EasyOCR) |
| `POST` | `/api/planches/{id}/reordonner` | recalcul de l'ordre de lecture |
| `GET/POST` | `/api/planches/{id}/regions` | régions / création manuelle |
| `PUT/DELETE` | `/api/regions/{id}` | modifier / supprimer une région |
| `POST` | `/api/regions/{id}/deplacer` | réordonner une région (↑/↓) |
| `GET` | `/api/regions/{id}/crop?taille=` | crop net (master) — vignette (recherche) ou transcription |
| `PATCH` | `/api/planches/{id}/statut` | statut (`importee→segmentee→corrigee→annotee`) |
| `GET/PUT` | `/api/regions/{id}/annotation` | lire / écrire l'annotation |
| `GET/POST` | `/api/tags` | tags (avec fréquences) |
| `GET` | `/api/recherche?q=&album=&type=&tags=` | recherche FTS5 |
| `GET` | `/api/corpus` | compteurs globaux du corpus |
| `POST/GET` | `/api/jobs` · `/api/jobs/{id}` | lancer / suivre un lot (multi-albums, arrière-plan) |
| `POST` | `/api/jobs/{id}/annuler` | annuler un lot |
| `GET` | `/api/export/{json,csv,tei}?album_id=` | export |
| `GET/POST` | `/api/sharedocs/{etat,connexion,deconnexion}` | session WebDAV ShareDocs (RAM only) |
| `GET/POST` | `/api/sharedocs/{liste,importer}` | explorer / importer depuis ShareDocs |
| `GET` | `/api/sauvegarde` | télécharger une sauvegarde (`.sqlite` zippé) |
| `POST` | `/api/sharedocs/deposer-sauvegarde` | déposer la sauvegarde sur ShareDocs |
| `GET` | `/api/sante` | disponibilité des moteurs (kumiko / bulles / ocr) |

**Pages** : `/` (visionneuse) · `/recherche` · `/corpus` (Bibliothèque).
Documentation interactive de l'API : `http://127.0.0.1:8000/docs`.

## Structure

```
bd_annotator/
├── main.py              # app FastAPI + routes
├── database.py          # init SQLite, schéma, FTS5, helpers
├── config.py            # chemins & constantes partagés
├── pipeline/
│   ├── ingest.py        # image → dérivé web + métadonnées + suppression fichiers
│   ├── segmentation.py  # wrapper Kumiko (cases)
│   ├── bulles.py        # détection des bulles (ogkalu YOLOv8)
│   ├── ocr.py           # OCR EasyOCR + crop net master
│   ├── ordering.py      # ordre de lecture (recalcul auto + déplacement)
│   ├── sharedocs.py     # client WebDAV ShareDocs (explorer / import / dépôt)
│   ├── backup.py        # snapshot SQLite (VACUUM INTO) zippé
│   └── jobs.py          # traitement par lot en arrière-plan (worker)
├── templates/
│   ├── index.html       # shell visionneuse
│   ├── recherche.html   # page Recherche
│   └── corpus.html      # page Bibliothèque
├── static/
│   ├── viewer.js        # visionneuse + modes + arbre + ShareDocs + deep-link
│   ├── recherche.js     # recherche FTS5 + résultats + nuage de tags
│   ├── corpus.js        # gestion albums/planches + lots + progression
│   └── style.css        # thème sombre (partagé par les 3 pages)
├── corpus/              # (gitignore) masters TIFF
└── derivatives/         # (gitignore) dérivés web
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest                     # toute la suite (194 tests)
pytest -m "not live"       # sans le test d'intégration (pas de serveur lancé)
pytest --cov=. --cov-report=term-missing   # couverture (100 %)
```

La suite (`tests/`, **194 tests, couverture 100 %**) couvre le schéma SQLite +
FTS5 (et la migration), le pipeline (ingestion, segmentation Kumiko, détection
de bulles, OCR, ordre de lecture), la sauvegarde, l'intégration **ShareDocs**
(WebDAV simulé via httpx `MockTransport`, sans réseau réel), la **gestion de
corpus** (CRUD albums/planches) et les **jobs par lot** (worker à passes mockées,
annulation déterministe), toutes les routes API, et un test de non-régression
par bug corrigé (`tests/test_regressions.py`).
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
