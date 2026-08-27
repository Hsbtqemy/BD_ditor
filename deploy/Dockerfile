# Image de l'application BéDéditeur (FastAPI + moteurs ML + Kumiko).
# Python 3.12 : wheels torch/easyocr matures, conforme au README.
FROM python:3.12-slim

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
#    et n'ont rien à faire ici.
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
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu         torch==2.13.0 torchvision==0.28.0

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

# 4) Code de l'application (lib/kumiko, .venv, corpus… sont exclus via .dockerignore).
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
