"""Cycle de vie mémoire des moteurs ML (CONC-2).

Les modèles (bulles YOLOv8, OCR EasyOCR, spaCy) se chargent paresseusement puis
restent RÉSIDENTS pour la vie du process : trois modèles torch + spaCy ensemble
peuvent saturer la RAM (OOM) sur poste/VPS contraint — observé en enchaînant
segmentation → bulles → OCR → NLP sur une vraie planche. On expose de quoi les
DÉCHARGER (rendre la RAM) à la demande, en fin de lot, ou avant une grosse passe.

Limite assumée (différée, cf. backlog CONC-2) : tant qu'un modèle torch est chargé,
le runtime torch occupe la mémoire du process ; le « zéro-OOM » garanti demanderait
d'isoler l'inférence dans un sous-process redémarrable. Ici on borne la RÉSIDENCE.
Cf. docs/backlog.md (CONC-2).
"""
from __future__ import annotations

import gc


def _moteurs() -> dict:
    """Moteurs « lourds » résidents (import paresseux : n'impose pas les deps ML)."""
    from pipeline import bulles, nlp, ocr
    return {"bulles": bulles, "ocr": ocr, "nlp": nlp}


def etat_modeles() -> dict:
    """{moteur: chargé en mémoire ?} — visibilité (sert `/api/sante`)."""
    return {nom: m.est_charge() for nom, m in _moteurs().items()}


def liberer_modeles_ml(sauf: tuple = ()) -> list:
    """Décharge les modèles ML résidents, SAUF ceux nommés dans `sauf`. Renvoie la
    liste des moteurs effectivement libérés.

    À appeler HORS inférence (lot terminé, ou sous `jobs.ML_LOCK`) : une inférence en
    cours garde sa propre référence locale et n'est pas cassée. Un `gc.collect()`
    (+ vidage du cache CUDA si présent) suit, pour rendre la RAM au plus tôt.
    """
    libere = [nom for nom, m in _moteurs().items() if nom not in sauf and m.liberer()]
    if libere:
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass        # torch absent ou sans CUDA : le gc.collect() suffit (CPU)
    return libere
