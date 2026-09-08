"""Interrupteur de passe ML — « arrête-toi » d'un fil à un autre (CONC-1).

L'annulation d'un lot n'était consultée qu'ENTRE deux planches et entre deux passes.
Une passe longue — Kumiko peut tourner jusqu'à cinq minutes sur une planche, l'OCR
boucle sur toutes les régions — ne la voyait jamais : le lot continuait, et l'écran
affichait « en cours » avec un bouton Annuler sur lequel on venait de cliquer.

**Un interrupteur PAR FIL, et non un paramètre à enfiler.** C'est l'idiome que le dépôt
emploie déjà pour l'agent courant du journal (« pas de `request` à threader ») et il vaut
mieux ici pour une raison mesurée : neuf doublures de test remplacent `segment_planche`
par un `lambda c, pid`, et un paramètre de plus les aurait toutes cassées — un coût réel,
pour rendre visible dans quatre signatures une chose qui n'intéresse qu'un appelant.

Le fil est le bon grain, et ce n'est pas un accident : le worker de lot est UN fil, la
passe s'exécute dedans, et les routes directes (`/segmenter`, `/ocr`) tournent dans
d'autres fils du pool — sans interrupteur, donc rigoureusement inchangées. Rien à
désactiver pour elles, il n'y a simplement rien à voir.

**`PasseInterrompue` n'est pas une erreur, et le reste du code doit le savoir.** Trois
endroits en dépendent : le worker ne la collecte pas dans `job["errors"]` (personne n'a
raté quoi que ce soit), le journal A3 clôt l'activité sur `interrompu` et non sur `echec`
(un faux échec dans une couche append-only ne se corrige plus), et `run_kumiko` tue son
sous-processus. C'est pourquoi elle vit ici plutôt que dans l'un des trois.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

_local = threading.local()


class PasseInterrompue(RuntimeError):
    """Une passe ML s'est arrêtée parce qu'on le lui a DEMANDÉ, non parce qu'elle a raté."""


def poser(sonde: Callable[[], bool]) -> None:
    """Installe la sonde d'interruption pour le fil courant."""
    _local.sonde = sonde


def retirer() -> None:
    """Retire la sonde du fil courant — à faire dans un `finally`.

    Un fil de pool est RÉUTILISÉ : une sonde oubliée déciderait de l'arrêt d'un travail
    qui n'a rien à voir avec le lot qui l'a posée.
    """
    _local.sonde = None


def demandee() -> bool:
    """L'interruption est-elle demandée ? False quand aucune sonde n'est posée."""
    sonde: Optional[Callable[[], bool]] = getattr(_local, "sonde", None)
    return bool(sonde and sonde())


def verifier() -> None:
    """Lève `PasseInterrompue` si l'interruption est demandée ; sinon ne fait rien."""
    if demandee():
        raise PasseInterrompue("passe interrompue à la demande")
