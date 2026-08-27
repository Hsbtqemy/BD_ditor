# Image de l'application BéDéditeur (FastAPI + moteurs ML + Kumiko).
#
# TROIS étapes (QA-5) :
#   base     — dépendances d'exécution, partagées ; jamais lancée telle quelle
#   test     — base + outils de test, pour exécuter la suite DANS l'image
#   runtime  — base + code, l'image LIVRÉE, sans aucun outil de test  (défaut)
#
# Pourquoi : jusqu'au 2026-08-27 le dépôt n'avait pas d'artefact, et sa vérification
# reposait sur une hypothèse alors vraie — ce qu'on teste EST ce qu'on exécute. Le premier
# build l'a rompue : 451 tests verts sur la machine de dev, et TROIS moteurs morts dans
# l'image (spaCy absent, torchvision incompatible, OpenCV 5 cassant Kumiko). Aucun n'était
# visible depuis le venv local. L'étape `test` existe pour que ça ne se reproduise pas ;
# `runtime` reste indemne, donc à 3,5 Go et sans navigateur embarqué.
#
#   docker build -f deploy/Dockerfile -t bdediteur .                      # runtime
#   docker build -f deploy/Dockerfile --target test -t bdediteur:test .   # suite
#   docker run --rm bdediteur:test                                        # lance pytest
#
# Python 3.12 : wheels torch/easyocr matures, conforme au README.

# --------------------------------------------------------------------------- #
# base — tout ce dont l'application a besoin pour TOURNER
# --------------------------------------------------------------------------- #
FROM python:3.12-slim AS base

# Dépendances système :
#   git           -> cloner Kumiko (segmentation, passe 1)
#   libgl1/glib   -> requis par opencv (tiré par ultralytics) à l'import de cv2
RUN apt-get update && apt-get install -y --no-install-recommends \
        git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Dépendances Python d'abord (couche de cache indépendante du code).
#    On installe le VERROU (requirements.lock, QA-1), pas les requirements*.txt à
#    bornes ouvertes : sans lui, deux reconstructions ne donnent pas la même image.
#    Le lock runtime couvre noyau + OCR/bulles + spaCy + les deps de Kumiko
#    (opencv/numpy/requests) ; les outils de test vivent dans requirements-dev.lock
#    et n'entrent QUE dans l'étape `test`.
COPY requirements.lock ./

#    1a) torch en variante CPU, AVANT le reste. Mesuré le 2026-08-27 : la roue torch
#    par défaut de PyPI est compilée pour CUDA 13 et traîne 2 196 Mo de wheels GPU
#    (cublas 423, cudnn 366, cufft 214, nccl 206, cusolver 201, triton 198…) — pour
#    une image de 10 Go dont le conteneur répond `torch.cuda.is_available() == False`.
#    Les specs du projet disent « CPU suffit » (requirements-ocr.txt, requirements-nlp.txt)
#    et le déploiement ne prévoit aucun GPU. On installe donc torch d'abord depuis
#    l'index CPU ; `ultralytics` et `easyocr` le trouvent ensuite déjà satisfait.
#    Pour repasser au GPU : supprimer cette étape, rien d'autre.
#    torchvision DOIT venir du MÊME index : c'est une extension native compilée
#    contre torch. Mesuré le 2026-08-27 : `torch==2.13.0+cpu` (index CPU) avec
#    `torchvision==0.28.0` (PyPI, compilé pour le torch CUDA) donne un
#    « RuntimeError: operator torchvision::nms does not exist » au premier import
#    d'ultralytics — et `/api/sante` n'y voit RIEN, car il ne fait que localiser
#    le module (`find_spec`), jamais l'importer.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        torch==2.13.0 torchvision==0.28.0

#    1b) le reste, depuis le verrou.
RUN pip install --no-cache-dir -r requirements.lock

# 2) Modèle NLP français — couche séparée, ~15 Mo, indépendante du reste.
#    SANS lui, `nlp_available()` est False et tout dégrade EN SILENCE : la table
#    `tokens` reste vide, donc l'Exploration ne montre rien, le statut de relecture
#    (ANN-4) reste « à faire » partout, les rapports d'accord (NLP-1, ANN-5) sortent
#    vides et la recherche perd les lemmes. Aucune erreur ne le signalerait.
#    Modèle surchargeable au runtime par BD_SPACY_MODEL (défaut : celui-ci).
RUN python -m spacy download fr_core_news_sm

# 3) Kumiko (passe 1) cloné dans lib/kumiko (ses dépendances opencv/numpy/requests
#    sont installées par le lock ci-dessus).
RUN git clone --depth 1 https://github.com/njean42/kumiko.git lib/kumiko

# --------------------------------------------------------------------------- #
# test — la suite s'exécute sur les MÊMES dépendances que la production
# --------------------------------------------------------------------------- #
# L'intérêt tient à ce partage : `test` hérite de `base`, donc du même torch, du même
# OpenCV et du même Kumiko que `runtime`. Un écart de version qui casse un moteur y est
# visible, alors qu'il ne l'est pas depuis le venv de dev.
#
# Deux exclusions ASSUMÉES, à connaître pour ne pas se croire couvert :
#   · e2e   — `pytest -m e2e` exige un navigateur ; installer Chromium ici ramènerait
#             les centaines de mégaoctets que `runtime` vient d'économiser. Ces tests
#             restent sur la machine de dev.
#   · JS    — `tests/test_js_unit.py` appelle `node`, absent de l'image : il se skippe
#             proprement, et sa logique est pure (aucun accès DOM), donc indépendante
#             de l'image.
FROM base AS test

# `openpyxl` n'entre PAS dans `runtime` (seuls les scripts `tools/` s'en servent) mais
# ICI, parce que deux tests d'export s'y skippaient sans lui.
#
# `iiif-prezi3` NE PEUT PAS y entrer, et c'est une découverte du 2026-08-27 :
# `iiif-prezi3==3.1.1` exige `Pillow<=12.0.0` (dépendance OBLIGATOIRE, pas un extra) et
# `requirements.lock` épingle `pillow==12.1.0`. Les deux sont mutuellement exclusifs — pip
# répond `ResolutionImpossible`. Conséquence : le test de conformance IIIF se skippe dans
# l'image ET sur la machine de dev, donc il ne tourne NULLE PART, alors que
# `docs/roadmap.md` donne l'IIIF pour « validé via iiif-prezi3 ». C'était vrai quand ça a
# été écrit ; ça ne l'est plus, et un skip se lit comme un succès. Cf. QA-4.
COPY requirements.lock requirements-dev.lock ./
RUN pip install --no-cache-dir -r requirements-dev.lock openpyxl==3.1.5

COPY . .

# Répertoires de travail ÉCRIVABLES et distincts de /data : la suite ne doit jamais
# écrire là où un volume de production serait monté. Les tests isolent de toute façon
# leurs données via BD_DATA_DIR/BD_DB_PATH (cf. tests/conftest.py), ceci ne sert qu'au
# `mkdir` fait par config.py à l'import.
ENV BD_DATA_DIR=/tmp/bd-test-data \
    HOME=/tmp/bd-test-home \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "pytest", "-q"]

# --------------------------------------------------------------------------- #
# runtime — l'image LIVRÉE  (étape par défaut : la dernière du fichier)
# --------------------------------------------------------------------------- #
FROM base AS runtime

# Code de l'application (lib/kumiko, .venv, corpus… sont exclus via .dockerignore).
COPY . .

# Données ET caches de modèles (HOME) sous /data -> persistés par un volume,
# donc les modèles ML ne sont téléchargés qu'une seule fois.
ENV BD_DATA_DIR=/data \
    HOME=/data \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# 1 SEUL worker : l'app garde des états en mémoire (jobs, session, modèles).
# L'app n'écoute qu'en interne ; elle n'est jamais exposée hors du réseau Docker.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
