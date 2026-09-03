"""Annulation de la dernière action d'annotation — Ctrl+Z (D1).

Deux routes, et un domaine à part entière : le cœur vit dans `undo.py`, la doctrine dans
`docs/undo.md`. Annuler ne défait pas une pile en mémoire — cela REMONTE le journal de
provenance (A3) et rejoue l'inverse du dernier acte humain annulable, puis journalise
l'annulation à son tour.

Le bloc dormait au milieu de « Personnages & attribution » dans `main.py`, et l'extraction
l'y a suivi : un module nommé d'après le registre des entités s'est mis à servir
`/api/undo`. Trouvé en relisant, pas par un test — aucun ne demande dans QUEL module vit
une route, et l'application, elle, répondait juste. C'est le même désordre d'accrétion que
l'affectation d'attributs, à ceci près qu'il ne se voyait plus une fois le fichier coupé.

Le module s'appelle `annulation` et non `undo` : `routes/undo.py` importerait `undo`, et
un module qui porte le nom de sa propre dépendance est une confusion qu'on paie plus tard
— `routes/figure.py` a déjà été renommé `figures.py` pour cette raison exacte.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

import autorisation
import undo

from socle import db, portee_courante

router = APIRouter()


def _agent_undo(portee: autorisation.Portee):
    """Quels actes cette requête peut-elle annuler ?  AUTH-2.

    En mono-poste (portée totale ET aucune identité), on ne filtre pas : c'est le
    comportement d'avant AUTH-2, et il n'y a qu'une personne devant la machine. Dès qu'il
    y a une identité, chacun n'annule que ses propres actes — administrateur compris :
    Ctrl+Z est un geste personnel, pas un outil de modération.
    """
    if portee.tout and portee.utilisateur is None:
        return undo.TOUS
    return portee.utilisateur


@router.get("/api/undo/prochain")
def undo_prochain(conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Aperçu : ce que ferait la prochaine annulation (ou `null` s'il n'y a rien à annuler)."""
    return undo.apercu(conn, agent=_agent_undo(portee))


@router.post("/api/undo")
def undo_dernier(conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Annule la dernière action d'annotation (Ctrl+Z). Renvoie un descripteur de l'acte
    annulé (description + planche/région touchée) pour le rafraîchissement de l'UI, ou 404
    s'il n'y a rien à annuler. Inversion + journal `annulation` atomiques (rollback si échec)."""
    # Annuler REJOUE une écriture : il faut en avoir le droit quelque part. Le filtre par
    # agent ne suffit pas — quelqu'un rétrogradé en lecture seule pourrait sinon défaire
    # ses anciens actes. Résiduel assumé : ce plancher ne dit pas SUR QUELLE collection
    # portait l'acte (la cible d'une suppression n'existe plus), donc un droit d'écriture
    # ailleurs suffit encore. Cf. docs/undo.md.
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Annuler demande un droit d'écriture.")
    try:
        res = undo.annuler(conn, agent=_agent_undo(portee))
    except undo.UndoImpossible as exc:
        raise HTTPException(409, f"Annulation impossible : {exc}")
    if res is None:
        raise HTTPException(404, "Rien à annuler.")
    conn.commit()
    return res
