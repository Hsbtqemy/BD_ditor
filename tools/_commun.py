"""Helpers partagés par les scripts d'export de métadonnées (tools/)."""
from __future__ import annotations

import importlib.metadata as _im
import sys
from functools import lru_cache
from pathlib import Path

# Paquets suivis (union des requirements : noyau + ocr + nlp + kumiko + export).
_PAQUETS = ("fastapi", "uvicorn", "pydantic", "pillow", "python-multipart", "httpx",
            "ultralytics", "easyocr", "torch", "huggingface-hub", "spacy",
            "opencv-python-headless", "numpy", "openpyxl")


@lru_cache(maxsize=None)
def environnement() -> dict:
    """Environnement logiciel à l'EXPORT (paradonnée / reproductibilité) : version de
    Python + versions **réellement installées** des paquets des requirements (absent →
    None). C'est l'env qui a produit CET export ; les versions par passe (segmentation /
    OCR / NLP, à leur date) restent à-prévoir (journal d'activités)."""
    paquets = {}
    for nom in _PAQUETS:
        try:
            paquets[nom] = _im.version(nom)
        except Exception:
            paquets[nom] = None
    return {"python": sys.version.split()[0], "paquets": paquets}


@lru_cache(maxsize=None)
def version_outil(base_dir) -> dict:
    """Provenance de l'outil produisant l'export (paradonnée / PROV).

    BéDéditeur n'a pas de version déclarée → on identifie le code par sa **révision
    git** (hash court). `version` reste None tant qu'aucune n'est déclarée. On lit la
    révision **directement dans `.git`** (HEAD → ref, ou packed-refs), **sans invoquer
    `git`** : fiable et instantané même sur système de fichiers lent (Google Drive,
    réseau), où un subprocess `git` peut se bloquer indéfiniment. Pas de détection
    « arbre modifié » (elle exigerait `git status`, coûteux). Hors dépôt → revision=None.
    """
    rev = None
    try:
        git = Path(base_dir) / ".git"
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()          # ex. refs/heads/dev
            loose = git / ref
            if loose.exists():
                rev = loose.read_text(encoding="utf-8").strip()
            else:                                         # ref empaquetée (packed-refs)
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
    return {"nom": "BéDéditeur", "version": None,
            "revision": rev[:7] if rev else None}
