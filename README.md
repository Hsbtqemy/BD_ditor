# BD Annotator

Outil de recherche pour l'analyse de bandes dessinées numérisées (corpus
franco-belge). Trois étapes : **segmentation automatique** des planches
(Kumiko), **correction manuelle**, et **annotation humaine** à plusieurs niveaux
hiérarchiques. Aucune IA dans la boucle d'annotation — tout le travail
interprétatif est humain.

L'app s'organise en **quatre espaces** : la **Bibliothèque** (`/corpus`) pour
gérer le corpus et lancer des traitements par lot, la **Visionneuse** (`/`) pour
segmenter / corriger / annoter / transcrire (+ corriger l'analyse grammaticale),
la **Recherche** (`/recherche`) pour interroger les dialogues corrigés, et
l'**Exploration** (`/exploration`) pour les distributions et comparaisons
linguistiques du corpus.

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
- Recherche plein texte **SQLite FTS5** (table `recherche` : OCR + note + tags + lemmes)
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

### Analyse linguistique (optionnelle)

**spaCy** ≥ 3.7 (CPU, léger) ajoute deux couches sur le texte OCR corrigé, sans
jamais bloquer le reste :

- **Lemmes** indexés dans FTS5 — « otage » trouve « otages », « obéir » trouve
  « obéissait » (ce que le préfixe + accents ne couvre pas).
- **Analyse grammaticale** par token (lemme, POS/**UPOS**, traits morphologiques)
  — corrigeable à la main dans la Visionneuse. La correction humaine est une
  couche *overlay* (`token_correction`) qui survit à toute réindexation ; la vue
  `tokens_effectifs` expose la valeur effective (correction vivante ⊕ auto).

Modèle **configurable** (`BD_SPACY_MODEL`, défaut `fr_core_news_sm`). Sans spaCy
ni modèle, l'app tourne et la recherche **retombe proprement** sur le préfixe +
accents. La page **Exploration** (`/exploration`) exploite cette couche :
distributions (lemme / POS / morph) d'un sous-corpus et comparaison
différentielle de deux sous-corpus, avec descente aux preuves (Recherche
pré-filtrée).

### Réseau & intégration

**httpx** ≥ 0.27, client **WebDAV** (RFC 4918) pour ShareDocs Huma-Num :
`PROPFIND` (lister) · `GET` (télécharger) · `PUT` (déposer), **Basic Auth**.
Identifiants gardés **en mémoire serveur uniquement** (jamais sur disque).

### Export

JSON-LD · CSV · TEI P5 (facsimile).

### Tests & qualité

**pytest** ≥ 8.0 + **pytest-cov** ≥ 4.0 · FastAPI **TestClient** · httpx
**MockTransport** (WebDAV simulé) · logique front pure testée sous **Node**
(`node --test`, pont `tests/test_js_unit.py`) · **Playwright** + Chromium pour
les tests E2E (marqueur `e2e`, hors run par défaut).

## Installation

```bash
pip install -r requirements.txt

# Segmentation automatique (optionnelle au démarrage) :
git clone https://github.com/njean42/kumiko.git lib/kumiko
pip install opencv-python-headless numpy requests   # deps de Kumiko (pas de requirements.txt)

# Moteurs ML optionnels — détection de bulles (YOLOv8) + OCR (EasyOCR) :
pip install -r requirements-ocr.txt

# Analyse linguistique optionnelle (lemmes + grammaire) :
pip install -r requirements-nlp.txt
python -m spacy download fr_core_news_sm
```

Tous les moteurs ci-dessus sont **optionnels** : sans eux l'app démarre, et leurs
routes renvoient **503** (cf. `GET /api/sante` pour leur disponibilité).

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
   automatique (debounce 500 ms). Pour une bulle, le panneau **analyse
   grammaticale** liste ses mots (lemme / POS / morphologie) ; chaque token est
   **corrigeable à la main** ou validable (geste « valider la grammaire »).
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
   définir le **rôle** d'une planche (`récit` numéroté / `paratexte` écarté),
   la **valider** (✔ relue/finalisée, décompte par album) et la **verrouiller**
   (🔒 protège des passes automatiques — les planches verrouillées sont sautées
   par les lots) ; **lancer un traitement par lot** (segmentation / bulles / OCR)
   sur une sélection d'albums et/ou de planches, exécuté en **tâche de fond** avec
   barre de progression et annulation.
10. **Recherche (`/recherche`)** : plein texte FTS5 sur dialogues + notes + tags
    (+ lemmes si le NLP est actif), filtres album / type / tags + nuage de tags ;
    chaque résultat (extrait surligné + vignette) **ouvre la visionneuse pile sur
    la région**. Export CSV des résultats.
11. **Exploration (`/exploration`)** : distributions (lemme / POS / morph) d'un
    sous-corpus, ou **comparaison différentielle** de deux sous-corpus A / B ;
    cliquer une valeur **descend aux preuves** (Recherche pré-filtrée). État dans
    l'URL (partageable).

## Modèle de données

`albums → planches → regions` (arbre via `parent_id`) `→ annotations → tags`
(N-N). Coordonnées **toujours en pixels master** ; la conversion master↔web est
faite côté frontend (`web_scale = web_width / master_width`).

Une **planche** porte un `role` (`recit` / `paratexte`), un horodatage de
validation (`validee`) et de verrou (`verrouillee`). Le **numéro éditorial** est
**dérivé, jamais stocké** (rang parmi les seules planches `recit`) ; les citations
`pl·c` / `pl·c·b` le sont aussi (`database.numeros_editoriaux()` /
`citations_regions()`, cf. `docs/numerotation-et-citation.md`).

La table FTS5 `recherche` agrège texte OCR + note + tags + **lemmes** ; elle est
maintenue explicitement par `database.reindex_region()` / `unindex_region()`.

**Couche linguistique** (NLP optionnel) : la table `tokens` (un mot du dialogue :
lemme / POS / morph) est **régénérée à chaque réindexation** ; la correction
humaine vit dans `token_correction`, une couche *overlay* **jamais écrasée** par
le reindex. La vue `tokens_effectifs` est le **read model canonique** (valeur
effective = correction vivante ⊕ auto, + provenance + drapeau « à revérifier ») :
toutes les surfaces d'analyse lisent CETTE vue, jamais `tokens` brut. La table
`meta` trace le modèle NLP ayant produit l'index (reproductibilité).

Le schéma est **versionné** (`database.SCHEMA_VERSION`, migrations dans
`_migrate()`) : la table FTS est séparée pour être recréable, les vues sont
toujours recréées au démarrage.

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
| `PATCH` | `/api/planches/{id}/validation` | marquer / retirer la validation humaine (`validee`) |
| `PATCH` | `/api/planches/{id}/verrou` | verrouiller / déverrouiller (protège des passes auto) |
| `PATCH` | `/api/planches/{id}/role` | rôle éditorial (`recit` / `paratexte`) |
| `GET/PUT` | `/api/regions/{id}/annotation` | lire / écrire l'annotation |
| `GET` | `/api/regions/{id}/tokens` | analyse grammaticale d'une région (valeurs effectives) |
| `PUT/DELETE` | `/api/regions/{id}/tokens/{ordre}` | corriger / annuler la correction d'un token |
| `POST` | `/api/regions/{id}/grammaire/valider` | valider toute la grammaire d'une région |
| `GET/POST` | `/api/tags` | tags (avec fréquences) |
| `GET` | `/api/recherche?q=&album=&type=&tags=` | recherche FTS5 |
| `GET` | `/api/recherche/export.csv` | export CSV des résultats de recherche |
| `GET` | `/api/analyse/frequences?champ=&album=&type=&pos=…` | distribution lemme / POS / morph (alias `/api/analyse/lemmes`) |
| `GET` | `/api/analyse/concordance?lemme=&pos=&morph=…` | occurrences en contexte (KWIC, multimodal) |
| `GET` | `/api/analyse/comparaison?champ=&a_*=&b_*=` | sur-représentation A vs B (fréquences relatives) |
| `GET` | `/api/analyse/info` | état de l'index linguistique (modèle, volumétrie) |
| `GET` | `/api/corpus` | compteurs globaux du corpus |
| `POST/GET` | `/api/jobs` · `/api/jobs/{id}` | lancer / suivre un lot (multi-albums, arrière-plan) |
| `POST` | `/api/jobs/{id}/annuler` | annuler un lot |
| `GET` | `/api/export/{json,csv,tei}?album_id=` | export |
| `GET/POST` | `/api/sharedocs/{etat,connexion,deconnexion}` | session WebDAV ShareDocs (RAM only) |
| `GET/POST` | `/api/sharedocs/{liste,importer}` | explorer / importer depuis ShareDocs |
| `GET` | `/api/sauvegarde` | télécharger une sauvegarde (`.sqlite` zippé) |
| `POST` | `/api/sharedocs/deposer-sauvegarde` | déposer la sauvegarde sur ShareDocs |
| `GET` | `/api/sante` | disponibilité des moteurs (kumiko / bulles / ocr / lemmes) |

**Pages** : `/` (Visionneuse) · `/recherche` · `/corpus` (Bibliothèque) ·
`/exploration`. Documentation interactive de l'API : `http://127.0.0.1:8000/docs`.

## Structure

```
bd_annotator/
├── main.py              # app FastAPI + routes
├── database.py          # init SQLite, schéma, FTS5, vues, migrations, helpers
├── config.py            # chemins & constantes partagés
├── pipeline/
│   ├── ingest.py        # image → dérivé web + métadonnées + suppression fichiers
│   ├── segmentation.py  # wrapper Kumiko (cases)
│   ├── bulles.py        # détection des bulles (ogkalu YOLOv8)
│   ├── ocr.py           # OCR EasyOCR + crop net master
│   ├── ordering.py      # ordre de lecture (recalcul auto + déplacement)
│   ├── nlp.py           # lemmatisation + analyse grammaticale (spaCy, optionnel)
│   ├── sharedocs.py     # client WebDAV ShareDocs (explorer / import / dépôt)
│   ├── backup.py        # snapshot SQLite (VACUUM INTO) zippé
│   └── jobs.py          # traitement par lot en arrière-plan (worker)
├── templates/           # index.html · recherche.html · corpus.html · exploration.html
├── static/
│   ├── viewer.js        # visionneuse + modes + arbre + grammaire + ShareDocs + deep-link
│   ├── recherche.js     # recherche FTS5 + résultats + nuage de tags
│   ├── corpus.js        # gestion albums/planches + rôle/validation/verrou + lots
│   ├── exploration.js   # distributions + comparaison de sous-corpus
│   ├── theme.js         # réglages d'affichage partagés (thème, contraste, zoom)
│   ├── lib/             # modules UMD réutilisables et testés sous Node : nav.js, dialog.js
│   └── style.css        # thème sombre/clair (partagé par les 4 pages)
├── tools/               # scripts hors-app : reindex_nlp.py, pdf_check.py, sharedocs_check.py
├── deploy/              # Docker Compose + Caddy + Authelia (cf. docs/deploiement-docker.md)
├── docs/                # décisions de conception (grammaire, numérotation, sécurité…) + backlog
├── corpus/              # (gitignore) masters TIFF
└── derivatives/         # (gitignore) dérivés web
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest                     # run par défaut — ~238 tests (E2E exclus, test `live` inclus)
pytest -m "not live"       # sans le test d'intégration (pas de serveur lancé)
pytest -m e2e              # E2E navigateur Playwright (~32 tests) — python -m playwright install chromium
pytest tests/test_api.py::test_nom            # un seul test
pytest --cov=. --cov-report=term-missing      # couverture
```

Trois couches de tests, toutes lançables via `python -m pytest` :

- **Serveur / API** (`tests/`) : schéma SQLite + FTS5 (et migration), pipeline
  (ingestion, segmentation Kumiko, bulles, OCR, ordre de lecture), sauvegarde,
  intégration **ShareDocs** (WebDAV simulé via httpx `MockTransport`, sans réseau
  réel), **gestion de corpus** (CRUD albums/planches), **jobs par lot** (worker à
  passes mockées, annulation déterministe), les routes API, et un test de
  non-régression par bug corrigé (`tests/test_regressions.py`).
- **Front pur** (`static/lib/*.js`) : `tests/test_js_unit.py` lance `node --test`
  sur `tests/js/*.test.js` (logique de navigation et de piège à focus). Skippé si
  Node est absent.
- **E2E navigateur** (`tests/test_e2e_navigation.py`, marqueur `e2e`, **hors run
  par défaut**) : deep-link, round-trip entre surfaces, durcissement anti-XSS,
  rendu — dans un vrai Chromium piloté par Playwright.
- **Accessibilité** (`tests/test_e2e_a11y.py`, marqueur `e2e`) : audit
  **axe-core** (WCAG 2.1 A/AA) des 4 surfaces en thèmes sombre + clair et de
  quelques états interactifs (modes, modale) ; échoue à la moindre violation
  sérieuse/critique. axe est **vendu hors ligne** dans `tests/js/vendor/`
  (cf. son README) ; le test se skippe si le fichier est absent.

`tests/test_live_race.py` lance un vrai serveur uvicorn isolé (via
`BD_DATA_DIR`/`BD_DB_PATH`) pour vérifier la cohérence écriture→lecture — chose
que `TestClient` ne peut pas reproduire. Les tests des moteurs **optionnels**
(Kumiko, bulles, OCR, NLP) sont automatiquement ignorés si le moteur ou son
modèle n'est pas installé ; la couverture mesurée dépend donc de ce qui est
présent dans l'environnement.

Variables d'environnement (cf. `config.py` / `pipeline/nlp.py`) :

| Variable | Rôle | Défaut |
|---|---|---|
| `BD_DATA_DIR` | racine corpus / derivatives / base | le dépôt |
| `BD_DB_PATH` | chemin explicite de la base SQLite | `DATA_DIR/bd_annotator.sqlite` |
| `BD_MAX_IMAGE_PIXELS` | garde-fou anti-bombe de décompression | 200 000 000 |
| `BD_SPACY_MODEL` | modèle spaCy pour le NLP | `fr_core_news_sm` |
| `BD_NLP_PREWARM` | pré-charger spaCy au démarrage (multi-utilisateurs) | désactivé |

## Pipeline en 3 passes (moteurs optionnels)

```
import → passe 1 : cases   (Kumiko)            → POST …/segmenter
       → passe 2 : bulles  (ogkalu YOLOv8)     → POST …/detecter-bulles
       → passe 3 : OCR fr  (EasyOCR, par bulle) → POST …/ocr  (pré-remplit ocr_texte)
       → correction + annotation humaines (mode Annotation)
       → (option) lemmes + analyse grammaticale (spaCy) → recherche + Exploration
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
- **Sans spaCy** (ou sans son modèle), tout fonctionne sauf les lemmes et
  l'analyse grammaticale : la recherche **retombe** sur le préfixe + accents.
  Après un changement de modèle/paramètre, réindexer le corpus avec
  `tools/reindex_nlp.py`.
- Les tags sont insensibles à la casse et stockés en minuscules ; un tag
  s'applique à n'importe quel niveau de la hiérarchie. Aucune taxonomie n'est
  imposée — les catégories émergent du corpus.
- Déploiement multi-comptes (HTTPS, 2FA) via Docker Compose + Authelia :
  `deploy/` et `docs/deploiement-docker.md`. Par défaut, l'app n'a **aucune
  authentification** (usage local mono-utilisateur, cf. `docs/hebergement-securite.md`).
