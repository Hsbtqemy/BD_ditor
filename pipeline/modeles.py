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

**Décharger ne rendait RIEN au système** (mesuré en production le 2026-11-25) : les deux
modèles déchargés par `POST /api/ml/liberer`, la mémoire du process est passée de 1,94 à
2,12 Go au lieu de baisser. glibc garde ce que Python libère, et chaque passe interactive
déchargeait l'autre modèle torch pour charger le sien : le parcours segmentation → bulles →
OCR, refait planche après planche toute la journée, fragmentait la mémoire jusqu'à l'OOM
(2,4 Go au plus haut, conteneur tué deux fois). D'où deux changements :

- après un déchargement, `malloc_trim(0)` DEMANDE à glibc de rendre ce qu'il garde
  (`rendre_au_systeme`) ;
- les passes interactives ne déchargent plus l'autre modèle : les deux restent chargés
  (833 Mio mesurés ensemble, CONC-2) et partent ENSEMBLE après `TTL_MODELES` sans passe
  (`signaler_usage`, une minuterie d'inactivité, le patron du cache des crops de
  `pipeline/ocr.py`). spaCy n'y part pas : chaque transcription l'emploie, et le
  recharger coûte 9 à 17 s.
"""
from __future__ import annotations

import gc
import threading
import time

from config import TTL_MODELES

# Les moteurs que l'échéance d'inactivité décharge : les deux modèles torch. spaCy reste,
# cf. la docstring du module.
MOTEURS_A_ECHEANCE = ("bulles", "ocr")


def _moteurs() -> dict:
    """Moteurs « lourds » résidents (import paresseux : n'impose pas les deps ML)."""
    from pipeline import bulles, nlp, ocr
    return {"bulles": bulles, "ocr": ocr, "nlp": nlp}


def etat_modeles() -> dict:
    """{moteur: chargé en mémoire ?} — visibilité (sert `/api/sante`)."""
    return {nom: m.est_charge() for nom, m in _moteurs().items()}


def rendre_au_systeme() -> bool:
    """Demande à l'allocateur de rendre au système la mémoire libre qu'il garde
    (`malloc_trim(0)` de glibc). True s'il a rendu quelque chose.

    Sans effet, et sans erreur, là où la fonction n'existe pas : Windows, macOS, une libc
    musl. L'image de production est sous glibc, c'est là que la mesure a été faite."""
    try:
        import ctypes
        return bool(ctypes.CDLL("libc.so.6").malloc_trim(0))
    except (OSError, AttributeError):
        return False


def liberer_modeles_ml(sauf: tuple = ()) -> list:
    """Décharge les modèles ML résidents, SAUF ceux nommés dans `sauf`. Renvoie la
    liste des moteurs effectivement libérés.

    À appeler HORS inférence (lot terminé, ou sous `jobs.ML_LOCK`) : une inférence en
    cours garde sa propre référence locale et n'est pas cassée. Un `gc.collect()`
    (+ vidage du cache CUDA si présent) suit, puis `rendre_au_systeme` : sans lui, la
    mémoire libérée restait au process (cf. la docstring du module).
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
        rendre_au_systeme()
    return libere


# --------------------------------------------------------------------------- #
# L'échéance d'inactivité
# --------------------------------------------------------------------------- #
# Une minuterie et non un fil de fond : armée par une passe, elle meurt avec les modèles
# qu'elle décharge (le raisonnement de `pipeline/ocr.py`, CONC-1).
#
# ORDRE DES VERROUS : `jobs.ML_LOCK` PUIS `_verrou`, jamais l'inverse. Les passes appellent
# `signaler_usage` sous `ML_LOCK` ; l'échéance prend `ML_LOCK` sans attendre, et `_verrou`
# seulement ensuite.
_verrou = threading.Lock()
_dernier_usage = 0.0
_minuterie: threading.Timer | None = None


def _armer(delai: float) -> None:
    """(Ré)arme la minuterie. **À appeler SOUS `_verrou`.** À `TTL_MODELES <= 0`, rien
    n'est armé : les modèles restent jusqu'à la fin d'un lot ou `POST /api/ml/liberer`."""
    global _minuterie
    if _minuterie is not None:
        _minuterie.cancel()
        _minuterie = None
    if TTL_MODELES <= 0:
        return
    _minuterie = threading.Timer(delai, _echoir)
    _minuterie.daemon = True                # ne retient jamais l'arrêt du process
    _minuterie.start()


def signaler_usage() -> None:
    """Une passe ML vient de servir : l'échéance repart de maintenant."""
    global _dernier_usage
    with _verrou:
        _dernier_usage = time.monotonic()
        _armer(TTL_MODELES)


def _echoir() -> None:
    """Corps de la minuterie : décharge les modèles torch si aucune passe n'a servi depuis
    `TTL_MODELES`. Une passe en cours (le verrou des moteurs tenu) la repousse d'autant :
    elle ne décharge jamais pendant une inférence, et ne l'attend pas."""
    from pipeline import jobs                   # import paresseux : évite un cycle d'import
    if not jobs.ML_LOCK.acquire(blocking=False):
        with _verrou:
            _armer(TTL_MODELES)
        return
    try:
        with _verrou:
            reste = TTL_MODELES - (time.monotonic() - _dernier_usage)
            if reste > 0:                       # réveil anticipé, ou passe plus récente
                _armer(reste)
                return
        liberer_modeles_ml(sauf=tuple(m for m in _moteurs() if m not in MOTEURS_A_ECHEANCE))
    finally:
        jobs.ML_LOCK.release()


def annuler_echeance() -> None:
    """Désarme la minuterie — pour les tests : une échéance armée par un test ne doit pas
    décharger les modèles factices d'un autre."""
    global _minuterie
    with _verrou:
        if _minuterie is not None:
            _minuterie.cancel()
            _minuterie = None
