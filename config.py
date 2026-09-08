"""Chemins et constantes partagés par l'application.

Les chemins de *code* (statics, templates, Kumiko) sont relatifs au dépôt
(BASE_DIR). Les chemins de *données* (base SQLite, corpus, dérivés) dérivent de
DATA_DIR, configurable via les variables d'environnement — ce qui permet de
déployer les données ailleurs que dans le dépôt et d'isoler les tests :

    BD_DATA_DIR   répertoire racine des données (défaut : le dépôt)
    BD_DB_PATH    chemin explicite de la base   (défaut : DATA_DIR/bd_annotator.sqlite)
"""
import os
import re
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

# Confiance accordée aux en-têtes d'identité (AUTH-1). `Remote-User`, `Remote-Groups`,
# `Remote-Name` et `Remote-Email` sont posés par le proxy d'auth — et un client qui
# atteindrait l'application EN DIRECT pourrait les forger de toutes pièces. Tant que rien
# n'est autorisé sur cette base, c'est sans conséquence ; dès qu'une autorisation en
# dépendra (AUTH-2, AUTH-3), ce serait une escalade de privilège en une ligne de curl.
#
# D'où un OPT-IN explicite : sans `BD_AUTH_PROXY`, les en-têtes sont IGNORÉS et tout acte
# reste anonyme — le comportement mono-poste actuel, inchangé. Le déploiement pose le
# drapeau (cf. deploy/docker-compose.yml), et lui seul.
#
# Ce n'est pas un doublon de la topologie réseau (l'app n'écoute qu'en interne) : une
# erreur de `ports:` dans un compose ne laisse aucune trace, ce drapeau si.
AUTH_PROXY = os.environ.get("BD_AUTH_PROXY", "").strip().lower() in ("1", "true", "oui", "yes")

# Groupes dont les membres voient TOUT le corpus et administrent les accès (AUTH-2).
# Noms de groupes Authelia, séparés par des virgules. La composition de ces groupes n'est
# jamais stockée ici : elle vit dans Authelia et se relit dans `Remote-Groups` à chaque
# requête, comme le reste (invariant AUTH-1).
#
# Sans proxy d'auth, ce réglage ne sert à rien : le mono-poste voit tout de toute façon.
AUTH_ADMIN_GROUPS = frozenset(
    g for g in (x.strip() for x in
                os.environ.get("BD_AUTH_ADMIN_GROUPS", "bd-admins").split(","))
    if g)

# Référent d'INSTANCE (AUTH-4) — à qui écrire quand on est bloqué.
#
# Il vit dans l'environnement et non en base, pour une raison de PORTÉE : c'est le seul
# référent qui puisse s'afficher à quelqu'un dont la portée est VIDE, donc qui ne peut lire
# aucune collection, donc aucun référent de collection. Or c'est précisément la personne
# que le bandeau de portée vide envoie « demander un accès à un administrateur » sans lui
# dire à qui. Le mettre en base le rendrait invisible à qui en a le plus besoin.
#
# Il n'est ni vérifié ni vérifiable : l'application ne connaît les groupes que de la
# personne qui frappe, à l'instant de sa requête (AUTH-1). Que ce nom appartienne encore à
# `bd-admins` lui est structurellement inconnaissable — la déclaration est DÉCLARATIVE, et
# c'est écrit plutôt que laissé à découvrir.
REFERENT_NOM = os.environ.get("BD_REFERENT_NOM", "").strip()
REFERENT_CONTACT = os.environ.get("BD_REFERENT_CONTACT", "").strip()

# Le commit que sert CETTE instance (INFRA-10). `deployer.sh` le passe en argument de
# build ; l'image le porte DEUX fois — en `LABEL bd.commit`, que le script relit de
# l'extérieur pour décider s'il y a à déployer, et en variable d'environnement, seule
# forme qu'un processus puisse lire de l'INTÉRIEUR. Un `LABEL` ne survit pas au build.
#
# Cela existe parce que la donnée ne quittait jamais le script qui la calcule : elle
# n'était lisible qu'au cours d'un déploiement, c'est-à-dire au seul instant où quelqu'un
# regardait déjà. Le 2026-09-07, l'instance a servi `305e0bc` pendant que `main` avait
# six commits d'avance, dont une fonctionnalité livrée et annoncée — et l'écart n'avait
# aucun endroit où apparaître.
#
# ON RECONNAÎT UN COMMIT À SA FORME, jamais en énumérant ce qui n'en est pas. Hors
# conteneur la variable est absente ; construite sans l'argument, elle vaut la chaîne
# `inconnu` (le défaut de l'`ARG` du Dockerfile). Deux états distincts pour une seule
# conclusion — on ne sait pas —, et la règle par la forme couvre aussi le troisième cas
# qu'on n'a pas prévu. C'est la leçon de l'étape 2 bis de `deployer.sh`, où une liste
# noire aurait fermé le bon cas pour la mauvaise raison.
#
# La règle est une FONCTION plutôt qu'une expression posée ici : `COMMIT_SERVI` se fige à
# l'import, si bien qu'une table de vérité sur la forme exigerait de recharger le module
# dans le processus de test — ce qui casserait les autres modules qui ont importé ses
# constantes par valeur. La fonction s'appelle, et la table se lit.
def commit_valide(brut: str):
    """Le commit si `brut` en est un, sinon None. Même règle que `deployer.sh`.

    Volontairement SANS `.lower()`, alors que ce serait une tolérance gratuite : la même
    valeur est lue à deux endroits — ici pour l'affichage, et par `deployer.sh` en
    `grep -qE '^[0-9a-f]{40}$'` pour DÉCIDER s'il redémarre Authelia. Deux lecteurs d'une
    même donnée qui n'appliquent pas la même règle finissent par se contredire sur un cas
    que personne n'a prévu, et c'est le lecteur qui décide qui aurait raison.
    """
    brut = (brut or "").strip()
    return brut if re.fullmatch(r"[0-9a-f]{40}", brut) else None


COMMIT_SERVI = commit_valide(os.environ.get("BD_COMMIT", ""))

# Garde-fou anti-bombe de décompression : nombre max de pixels décodés par image.
# Très au-dessus d'un scan de BD (≤ ~100 Mpx même en haute résolution) mais bloque
# les images-bombes AVANT l'allocation mémoire (Pillow vérifie via l'en-tête).
# Configurable via l'environnement.
MAX_IMAGE_PIXELS = int(os.environ.get("BD_MAX_IMAGE_PIXELS", 200_000_000))

# Les formats d'image que le corpus accepte, et RIEN d'autre (SEC-3).
#
# Un seul endroit, et les deux vues en DÉRIVENT : `IMG_EXTS` filtre ce qu'on peut
# téléverser, `PILLOW_FORMATS` borne ce que Pillow a le droit de DÉCODER. Les tenir à deux
# endroits reviendrait à parier qu'on pensera aux deux ; or c'est le format resté hors de
# la seconde liste qui rouvrirait le trou, et il ne se remarquerait pas — le corpus
# marcherait exactement pareil.
#
# Pourquoi borner le décodage alors que l'extension est déjà filtrée : parce que Pillow
# ne regarde PAS l'extension. `Image.open` renifle l'en-tête, si bien qu'un PSD renommé
# `.tif` passe le filtre d'extension et arrive au décodeur PSD. C'est le vecteur de
# `CVE-2026-25990` (écriture hors limites sur des tuiles à décalage négatif), et le
# paramètre `formats` est le contournement que l'avis lui-même propose. Il vaut quelle que
# soit la version de Pillow installée — donc il ne dépend pas du plafond que
# `iiif-prezi3` nous impose.
#
# Les clés sont les identifiants de format de Pillow, PAS des extensions
# (`Image.EXTENSION` fait la correspondance ; vérifié le 2026-09-08).
FORMATS_IMAGE = {
    "TIFF": (".tif", ".tiff"),                                   # masters de numérisation
    "JPEG": (".jpg", ".jpeg"),                                   # dérivés web
    "JPEG2000": (".jp2", ".j2k", ".jpf", ".jpx", ".jpc", ".j2c"),
    "PNG": (".png",),
    "BMP": (".bmp",),
    "GIF": (".gif",),
    "WEBP": (".webp",),
}

# Ce que Pillow a le droit de décoder. Tuple figé : `Image.open(..., formats=…)`.
PILLOW_FORMATS = tuple(FORMATS_IMAGE)

# Ce qu'on accepte de recevoir. Dérivé, jamais recopié.
IMG_EXTS = tuple(e for exts in FORMATS_IMAGE.values() for e in exts)

# Statuts possibles d'une planche (progression linéaire)
STATUTS = ("importee", "segmentee", "corrigee", "annotee")

# Statut de RELECTURE grammaticale (ANN-4) : DÉRIVÉ des provenances de tokens, OVERRIDABLE.
RELECTURE = ("a_faire", "en_cours", "faite")

# Régime de diffusion d'une COLLECTION (v14, palier dépôt). Il vivait dans
# `tools/gerer_collections.py`, seul chemin d'écriture jusqu'à AUTH-3 ; la route d'édition
# a fait de lui un vocabulaire à DEUX portes, dont une seule validait. Un champ contrôlé
# n'est contrôlé que si tous ses chemins d'écriture partagent la même liste.
STATUTS_DIFFUSION = ("public", "embargo", "restreint", "prive")

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
