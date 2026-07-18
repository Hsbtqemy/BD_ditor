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

# Racine des données (overridable). Par défaut : le dépôt lui-même. Un chemin
# RELATIF est résolu contre le dépôt (BASE_DIR), pas contre le CWD du process —
# sinon l'app pointerait vers une base/un corpus différents selon le répertoire
# de lancement.
_data_env = os.environ.get("BD_DATA_DIR")
DATA_DIR = Path(_data_env) if _data_env else BASE_DIR
if not DATA_DIR.is_absolute():
    DATA_DIR = BASE_DIR / DATA_DIR
DATA_DIR = DATA_DIR.resolve()

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

# Déconnexion (INFRA-1). Derrière le proxy d'authentification (Authelia), l'URL de
# logout vit sur le sous-domaine du PORTAIL (ex. https://auth.example.fr/logout) :
# elle est propre au déploiement, donc configurable. Vide en local (pas de proxy
# d'auth) → l'UI n'affiche ni utilisateur ni lien de déconnexion (dégradation propre).
AUTH_LOGOUT_URL = os.environ.get("BD_AUTH_LOGOUT_URL", "").strip()

# Garde-fou anti-bombe de décompression : nombre max de pixels décodés par image.
# Très au-dessus d'un scan de BD (≤ ~100 Mpx même en haute résolution) mais bloque
# les images-bombes AVANT l'allocation mémoire (Pillow vérifie via l'en-tête).
# Configurable via l'environnement.
MAX_IMAGE_PIXELS = int(os.environ.get("BD_MAX_IMAGE_PIXELS", 200_000_000))

# Statuts possibles d'une planche (progression linéaire)
STATUTS = ("importee", "segmentee", "corrigee", "annotee")

# Statut de RELECTURE grammaticale (ANN-4) : DÉRIVÉ des provenances de tokens, OVERRIDABLE.
RELECTURE = ("a_faire", "en_cours", "faite")

# Rôle éditorial d'une planche (cf. docs/numerotation-et-citation.md). 'recit' =
# planche narrative, numérotée ; les autres valeurs = paratexte (couverture,
# liminaire, pub…), écartées de la numérotation et du décompte de cases citables.
# Vocabulaire extensible ; seul 'recit' a un sens spécial côté dérivation.
ROLES_PLANCHE = ("recit", "paratexte")

# Types de régions autorisés
TYPES_REGION = ("case", "bulle", "personnage", "texte", "cartouche")

# Cibles d'un attribut facetté (ANN-2) : un axe émergent s'applique soit au profil
# (socio)linguistique d'un PERSONNAGE, soit à la situation d'une CASE (scène).
# Cf. docs/personnages-et-attribution.md (§13).
CIBLES_ATTRIBUT = ("personnage", "case")

# Jeu d'étiquettes POS universel (UPOS) — vocabulaire CONTRÔLÉ pour la correction
# grammaticale humaine (cf. docs/correction-grammaticale.md). C'est aussi le jeu que
# spaCy produit, donc corrections et auto restent comparables/requêtables.
UPOS_TAGS = ("ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN", "NUM",
             "PART", "PRON", "PROPN", "PUNCT", "SCONJ", "SYM", "VERB", "X")

# S'assure que les répertoires de données existent. Encadré : un DATA_DIR non
# inscriptible (RO, permissions, disque plein) doit donner un message clair
# nommant le chemin fautif, pas une stack-trace brute à l'import.
for _d in (CORPUS_DIR, DERIVATIVES_DIR):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Impossible de créer le répertoire de données {_d} — "
            f"vérifiez BD_DATA_DIR et les permissions ({exc})") from exc
