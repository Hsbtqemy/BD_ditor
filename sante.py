"""Contrôle des moteurs — RAPIDE (présence) ou PROFOND (import réel).  SANTE-1.

Pourquoi deux profondeurs, et pourquoi ce module existe.

`/api/sante` répondait jusqu'ici en interrogeant `importlib.util.find_spec`, qui LOCALISE
un module sans jamais l'importer. Le raccourci est délibéré et bon : importer torch coûte
plusieurs secondes et des centaines de mégaoctets de RAM, ce qu'une route de SANTÉ ne peut
pas se permettre — une sonde de conteneur l'appelle en boucle, et un écran de diagnostic
doit s'ouvrir instantanément.

Mais il ne voit RIEN d'une incompatibilité binaire. Mesuré le 2026-08-27, trois fois dans
la même journée :
  · `torchvision` de PyPI posé sur un torch CPU → `import ultralytics` lève
    « RuntimeError: operator torchvision::nms does not exist ». `/api/sante` : `bulles: true`.
  · OpenCV 5 écrasant OpenCV 4 → Kumiko casse sur `HoughLinesP`, la passe 1 renvoie 500.
    `/api/sante` : `kumiko: true`.
  · Modèle spaCy absent → `lemmes: false`, honnête cette fois, mais rien ne dit que quatre
    chantiers livrés viennent de mourir avec lui.

En mono-poste le raccourci est sans gravité : on clique, on voit l'erreur, on comprend.
DÉPLOYÉ, cette route devient l'unique fenêtre sur l'état des moteurs pour quelqu'un qui
n'a plus d'accès shell — et elle affiche vert sur une machine en panne. Un vert qui ne
mesure rien est pire que pas de contrôle.

D'où la séparation : la voie RAPIDE reste ce qu'elle était (aucune régression de latence),
la voie PROFONDE importe réellement et dit POURQUOI quand ça échoue. Le résultat profond
est mémorisé : un import qui a réussi ne peut pas échouer ensuite dans le même process, et
on ne recharge pas torch à chaque appel.

Le même cœur sert `tools/verifier_moteurs.py`, lancé À LA CONSTRUCTION de l'image — c'est
là que le troisième cas se rattrape. La suite de tests, elle, ne le peut pas : la couche
NLP est conçue pour dégrader proprement et les tests encodent la même hypothèse, si bien
qu'une image sans spaCy passe la suite à 100 % vert (mesuré, cf. `pilotage/QA-5.md`).
Un contrat d'IMAGE est donc distinct d'un contrat de test.

Cette phrase a cessé d'être vraie sans que personne ne le voie, et c'est QA-6 : sans le
modèle spaCy, le cliquet des sorties d'identité ÉCHOUAIT — sa correction sentinelle
n'avait plus de token auto à rejoindre — et deux tests d'ici même importaient `cv2` sans
garde, donc tombaient sur une installation noyau. Trois configurations remesurées le
2026-09-05 (avec modèle, spaCy sans modèle, noyau seul) : 0 échec dans chacune. La
dégradation propre n'est pas une propriété acquise, c'est une propriété qui se REMESURE.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

# Ce qu'il faut RÉELLEMENT importer pour prouver qu'un moteur fonctionne. Ce ne sont pas
# les mêmes noms que ceux sondés par `find_spec` : on veut le module dont l'import
# déclenche le chargement des extensions natives, là où une ABI cassée se révèle.
#   · bulles : `ultralytics` tire torch ET torchvision — c'est cet import qui a levé
#     `torchvision::nms` le 2026-08-27.
#   · ocr    : `easyocr` tire torch de son côté.
#   · kumiko : `cv2` seul ne suffit PAS à prouver que Kumiko marche (OpenCV 5 s'importe
#     très bien et casse ensuite dans `HoughLinesP`) — on vérifie donc aussi la VERSION
#     majeure, cf. `_verifier_kumiko`.
#   · nlp    : charger le modèle, pas seulement le localiser.
MOTEURS = ("kumiko", "bulles", "ocr", "nlp")

_profond: dict = {}
_verrou = threading.Lock()


def _verifier_bulles() -> None:
    import ultralytics                              # noqa: F401  (tire torch + torchvision)
    from ultralytics import YOLO                    # noqa: F401


def _verifier_ocr() -> None:
    import easyocr                                  # noqa: F401


def _verifier_nlp() -> None:
    """CHARGE le modèle, ne se contente pas de le localiser : un paquet présent mais
    corrompu passe `find_spec` sans broncher. Le nom vient de `BD_SPACY_MODEL`
    (`pipeline.nlp._MODEL`), donc on vérifie CELUI qui sera réellement utilisé."""
    import spacy
    from pipeline.nlp import _MODEL
    spacy.load(_MODEL)


def _verifier_kumiko() -> None:
    """Kumiko est un SCRIPT, pas une bibliothèque : on ne peut pas l'importer pour le
    prouver. On vérifie donc son point d'entrée ET la majeure d'OpenCV, parce que c'est
    précisément là qu'il casse — `HoughLinesP` renvoie (N, 4) en OpenCV 5 contre
    (N, 1, 4) en 4.x, et Kumiko indexe `dline[0][0]`."""
    from pipeline.segmentation import KUMIKO_ENTRY
    if not KUMIKO_ENTRY.is_file():
        raise RuntimeError(f"point d'entrée absent : {KUMIKO_ENTRY}")
    import cv2
    majeure = int(cv2.__version__.split(".")[0])
    if majeure >= 5:
        raise RuntimeError(
            f"OpenCV {cv2.__version__} : Kumiko attend la 4.x "
            "(HoughLinesP a changé de forme de retour en 5.0)")


_CONTROLES: dict[str, Callable[[], None]] = {
    "kumiko": _verifier_kumiko,
    "bulles": _verifier_bulles,
    "ocr": _verifier_ocr,
    "nlp": _verifier_nlp,
}


def rapide() -> dict:
    """Présence des moteurs, sans rien importer. Le contrat historique de `/api/sante`."""
    from pipeline.bulles import bulles_available
    from pipeline.nlp import nlp_available
    from pipeline.ocr import ocr_available
    from pipeline.segmentation import kumiko_available
    return {"kumiko": kumiko_available(), "bulles": bulles_available(),
            "ocr": ocr_available(), "lemmes": nlp_available()}


def profond(moteur: str) -> dict:
    """{ok, erreur} pour UN moteur, en l'important réellement. Mémorisé par moteur."""
    with _verrou:
        if moteur in _profond:
            return _profond[moteur]
    try:
        _CONTROLES[moteur]()
        res = {"ok": True, "erreur": None}
    except Exception as exc:                        # tout est bon à attraper ici : un
        res = {"ok": False,                         # moteur cassé lève n'importe quoi
               "erreur": f"{type(exc).__name__}: {exc}"[:300]}
    with _verrou:
        _profond[moteur] = res
    return res


def rapport(moteurs: Optional[tuple] = None) -> dict:
    """Contrôle PROFOND de plusieurs moteurs. `{moteur: {ok, erreur}}`."""
    return {m: profond(m) for m in (moteurs or MOTEURS)}


def _reset() -> None:
    """Vide la mémoïsation — pour les tests uniquement."""
    with _verrou:
        _profond.clear()
