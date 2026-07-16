"""Helpers partagés par les scripts d'export de métadonnées (tools/)."""
from __future__ import annotations

import importlib.metadata as _im
import sys
from functools import lru_cache
from pathlib import Path

# Racine du dépôt (tools/_commun.py → dépôt) et clone Kumiko vendu dedans.
_REPO = Path(__file__).resolve().parent.parent
_KUMIKO_DIR = _REPO / "lib" / "kumiko"        # clone git (cf. requirements-kumiko.txt)

# Paquets suivis (union des requirements : noyau + ocr + nlp + kumiko + export).
# `opencv-python-headless`, `numpy` et `requests` sont les dépendances d'EXÉCUTION
# de Kumiko (passe 1) — voir requirements-kumiko.txt.
_PAQUETS = ("fastapi", "uvicorn", "pydantic", "pillow", "python-multipart", "httpx",
            "ultralytics", "easyocr", "torch", "huggingface-hub", "spacy",
            "opencv-python-headless", "numpy", "requests", "openpyxl")

# Catalogue documentaire des composants logiciels : pour chaque brique,
# (catégorie, site officiel, rôle DANS le projet). La *description générique* (résumé
# éditeur) n'est PAS recopiée ici : elle est lue à l'export depuis les métadonnées du
# paquet installé (cf. `_resume_installe`), donc toujours à jour et sans doublon à
# maintenir. `python` / `kumiko` ne sont pas des paquets pip (traités à part).
_CATALOGUE = {
    "python": ("exécution", "https://www.python.org/",
               "Interpréteur qui exécute l'outil et les scripts d'export."),
    "kumiko": ("segmentation (passe 1)", "https://github.com/njean42/kumiko",
               "Découpe automatique des planches en cases (clone git vendu dans lib/kumiko)."),
    "fastapi": ("noyau", "https://fastapi.tiangolo.com/",
                "Framework web : sert l'API /api/ et les pages."),
    "uvicorn": ("noyau", "https://www.uvicorn.org/",
                "Serveur ASGI qui fait tourner l'application."),
    "pydantic": ("noyau", "https://docs.pydantic.dev/",
                 "Validation des corps de requête/réponse de l'API."),
    "pillow": ("noyau", "https://python-pillow.github.io/",
               "Lecture des images master + génération des dérivés web."),
    "python-multipart": ("noyau", "https://github.com/Kludex/python-multipart",
                         "Décodage des envois multipart (import de planches)."),
    "httpx": ("noyau", "https://www.python-httpx.org/",
              "Client HTTP du connecteur WebDAV ShareDocs (Huma-Num)."),
    "ultralytics": ("bulles (passe 2)", "https://docs.ultralytics.com/",
                    "YOLOv8 : détection des bulles (moteur optionnel)."),
    "huggingface-hub": ("bulles (passe 2)", "https://huggingface.co/docs/huggingface_hub",
                        "Téléchargement du modèle de bulles ogkalu (optionnel)."),
    "easyocr": ("OCR (passe 3)", "https://github.com/JaidedAI/EasyOCR",
                "OCR français : pré-remplit le texte des bulles (optionnel)."),
    "torch": ("ML (bulles / OCR)", "https://pytorch.org/",
              "Moteur tensoriel requis par YOLOv8 et EasyOCR (optionnel)."),
    "spacy": ("NLP", "https://spacy.io/",
              "Lemmes + grammaire (POS/morph) : recherche par lemme, analyse (optionnel)."),
    "opencv-python-headless": ("segmentation (passe 1)", "https://opencv.org/",
                               "Vision par ordinateur : dépendance d'exécution de Kumiko."),
    "numpy": ("segmentation (passe 1)", "https://numpy.org/",
              "Calcul matriciel : socle de Kumiko / OpenCV (et du ML)."),
    "requests": ("segmentation (passe 1)", "https://requests.readthedocs.io/",
                 "Client HTTP utilisé par Kumiko."),
    "openpyxl": ("export", "https://openpyxl.readthedocs.io/",
                 "Écriture des classeurs XLSX (dont cet export)."),
}


def _revision_git(git_dir) -> str | None:
    """Révision courte (7 car.) lue DIRECTEMENT dans un dossier `.git` (HEAD → ref,
    ou `packed-refs`), **sans invoquer `git`** : fiable et instantané même sur système
    de fichiers lent (Google Drive, réseau), où un subprocess `git` peut se bloquer
    indéfiniment. None si illisible (dossier absent, HEAD introuvable, hors dépôt)."""
    try:
        git = Path(git_dir)
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()          # ex. refs/heads/dev
            loose = git / ref
            if loose.exists():
                rev = loose.read_text(encoding="utf-8").strip()
            else:                                         # ref empaquetée (packed-refs)
                rev = None
                packed = git / "packed-refs"
                if packed.exists():
                    for ligne in packed.read_text(encoding="utf-8").splitlines():
                        if ligne and ligne[0] not in "#^" and ligne.endswith(ref):
                            rev = ligne.split()[0]
                            break
        else:
            rev = head                                    # HEAD détaché : SHA direct
    except Exception:
        rev = None
    return rev[:7] if rev else None


def _resume_installe(nom: str) -> str | None:
    """Description GÉNÉRIQUE (résumé éditeur) d'un paquet, lue dans ses métadonnées
    **installées** (champ `Summary` du .dist-info) — hors ligne, sans réseau. None si
    le paquet n'est pas installé ou n'expose pas de résumé."""
    try:
        resume = _im.metadata(nom).get("Summary")
        return resume.strip() if resume and resume.strip() else None
    except Exception:
        return None


@lru_cache(maxsize=None)
def _kumiko() -> dict:
    """Provenance du moteur de SEGMENTATION Kumiko (passe 1). Kumiko est un clone git
    *vendu* dans `lib/kumiko` — **pas un paquet pip**, donc invisible à
    `importlib.metadata` : on identifie sa version par sa **révision git**. Ses
    dépendances d'exécution (opencv-python-headless, numpy, requests) sont dans
    `paquets`. Non installé → `present=False`, `revision=None`."""
    entree = _KUMIKO_DIR / "kumiko"                       # script d'entrée (cf. segmentation.py)
    return {"present": entree.exists(),
            "revision": _revision_git(_KUMIKO_DIR / ".git")}


@lru_cache(maxsize=None)
def composants() -> list:
    """Inventaire logiciel documenté (SBOM léger) qui a produit CET export : une entrée
    par composant (Python + Kumiko + chaque paquet suivi), avec version **réellement
    installée** (révision git pour Kumiko), catégorie, rôle dans le projet, site officiel
    et description générique (résumé PyPI local). Un composant absent garde son
    entrée (version=None, installe=False) pour documenter ce qui *pourrait* servir."""
    lignes = []

    cat, site, role = _CATALOGUE["python"]
    lignes.append({"composant": "python", "categorie": cat,
                   "version": sys.version.split()[0], "installe": True,
                   "role": role, "site": site, "resume": None})

    k = _kumiko()
    cat, site, role = _CATALOGUE["kumiko"]
    lignes.append({"composant": "kumiko", "categorie": cat,
                   "version": k["revision"], "installe": k["present"],
                   "role": role, "site": site,
                   "resume": "Découpe de planches de bande dessinée en cases."})

    for nom in _PAQUETS:
        cat, site, role = _CATALOGUE.get(nom, ("", "", ""))
        try:
            ver = _im.version(nom)
        except Exception:
            ver = None
        lignes.append({"composant": nom, "categorie": cat, "version": ver,
                       "installe": ver is not None, "role": role, "site": site,
                       "resume": _resume_installe(nom)})
    return lignes


@lru_cache(maxsize=None)
def environnement() -> dict:
    """Environnement logiciel à l'EXPORT (paradonnée / reproductibilité) : version de
    Python + versions **réellement installées** des paquets des requirements (absent →
    None) + provenance des **moteurs vendus** (Kumiko : clone git, pas un paquet pip).
    C'est l'env qui a produit CET export ; les versions par passe (segmentation / OCR /
    NLP, à leur date) restent à-prévoir (journal d'activités). Vue documentée détaillée
    (rôle + site + description) : cf. `composants()`."""
    paquets = {}
    for nom in _PAQUETS:
        try:
            paquets[nom] = _im.version(nom)
        except Exception:
            paquets[nom] = None
    return {"python": sys.version.split()[0], "paquets": paquets,
            "moteurs": {"kumiko": _kumiko()}}


def portee_albums(album_ids) -> dict | None:
    """PORTÉE d'export par ensemble d'albums (scoping `--collection`).

    `album_ids=None` → renvoie None (corpus entier : aucun filtre). Sinon, renvoie des
    ENSEMBLES de valeurs SQL prêts à l'emploi dans un `IN` — les entiers sont inlinés (ils
    viennent de la base, JAMAIS d'une saisie utilisateur ; aucune injection possible) :

      • `albums`   : `(1,2,3)`                       → `... WHERE id IN {p['albums']}`
      • `planches` : `(SELECT id FROM planches …)`    → `... WHERE planche_id IN {p['planches']}`
      • `regions`  : `(SELECT id FROM regions …)`     → `... WHERE region_id IN {p['regions']}`

    Un ensemble vide (collection sans album) donne `(-1)` : aucun id ne matche → sortie vide,
    honnête. Partagé par metadonnees_collection.py et description_collection.py."""
    if album_ids is None:
        return None
    a = ",".join(str(int(i)) for i in album_ids) or "-1"
    planches = f"(SELECT id FROM planches WHERE album_id IN ({a}))"
    regions = f"(SELECT id FROM regions WHERE planche_id IN {planches})"
    return {"albums": f"({a})", "planches": planches, "regions": regions}


@lru_cache(maxsize=None)
def version_outil(base_dir) -> dict:
    """Provenance de l'outil produisant l'export (paradonnée / PROV).

    BéDéditeur n'a pas de version déclarée → on identifie le code par sa **révision
    git** (hash court), lue directement dans `.git` (cf. `_revision_git`), sans invoquer
    `git`. `version` reste None tant qu'aucune n'est déclarée. Pas de détection « arbre
    modifié » (elle exigerait `git status`, coûteux). Hors dépôt → revision=None.
    """
    return {"nom": "BéDéditeur", "version": None,
            "revision": _revision_git(Path(base_dir) / ".git")}
