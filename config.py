"""Chemins et constantes partagés par l'application.

Les chemins de *code* (statics, templates, Kumiko) sont relatifs au dépôt
(BASE_DIR). Les chemins de *données* (base SQLite, corpus, dérivés) dérivent de
DATA_DIR, configurable via les variables d'environnement — ce qui permet de
déployer les données ailleurs que dans le dépôt et d'isoler les tests :

    BD_DATA_DIR   répertoire racine des données (défaut : le dépôt)
    BD_DB_PATH    chemin explicite de la base   (défaut : DATA_DIR/bd_annotator.sqlite)
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Racine des données (overridable). Par défaut : le dépôt lui-même.
DATA_DIR = Path(os.environ.get("BD_DATA_DIR", BASE_DIR)).resolve()

DB_PATH = (Path(os.environ["BD_DB_PATH"]).resolve()
           if os.environ.get("BD_DB_PATH")
           else DATA_DIR / "bd_annotator.sqlite")

CORPUS_DIR = DATA_DIR / "corpus"            # masters TIFF (gitignore)
DERIVATIVES_DIR = DATA_DIR / "derivatives"  # PNG/JPEG web générés (gitignore)

# Chemins de code (toujours relatifs au dépôt).
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
KUMIKO_DIR = BASE_DIR / "lib" / "kumiko"

# Paramètres de dérivation web
WEB_SCALE = 0.25          # le dérivé fait 25 % de la taille du master
WEB_JPEG_QUALITY = 82

# Statuts possibles d'une planche (progression linéaire)
STATUTS = ("importee", "segmentee", "corrigee", "annotee")

# Types de régions autorisés
TYPES_REGION = ("case", "bulle", "personnage", "texte", "cartouche")

# S'assure que les répertoires de données existent
for _d in (CORPUS_DIR, DERIVATIVES_DIR):
    _d.mkdir(parents=True, exist_ok=True)
