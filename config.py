"""Chemins et constantes partagés par l'application."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "bd_annotator.sqlite"

CORPUS_DIR = BASE_DIR / "corpus"            # masters TIFF (gitignore)
DERIVATIVES_DIR = BASE_DIR / "derivatives"  # PNG/JPEG web générés (gitignore)
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
