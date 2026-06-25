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

# 1) Dépendances Python d'abord (couche de cache indépendante du code) :
#    cœur + moteurs ML optionnels (bulles/OCR). `requests` est requis par Kumiko.
COPY requirements.txt requirements-ocr.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-ocr.txt requests

# 2) Kumiko (passe 1) cloné dans lib/kumiko (ses dépendances opencv/numpy/requests
#    sont déjà installées via ultralytics ci-dessus).
RUN git clone --depth 1 https://github.com/njean42/kumiko.git lib/kumiko

# 3) Code de l'application (lib/kumiko, .venv, corpus… sont exclus via .dockerignore).
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
