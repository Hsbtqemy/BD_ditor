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
import conflit
import undo
from pipeline import nlp

from socle import _get_personnage, _get_planche, _get_region, db, portee_courante

router = APIRouter()


def _ecrivable(conn: sqlite3.Connection, portee: autorisation.Portee):
    """Ce que `undo.annuler` demande avant d'écrire : l'agent peut-il écrire MAINTENANT
    les lieux de l'inverse ? Par les accesseurs gardés, en écriture — la même question
    que la route qui aurait fait le geste, posée au moment où on le défait (AUTH-14).

    Un refus (404) devient `False` : `undo` passe alors l'acte sans rien dire de l'objet,
    qu'on ne lit peut-être pas. Tout autre refus remonte tel quel."""
    def peut(lieux: dict) -> bool:
        try:
            for rid in lieux["regions"]:
                _get_region(conn, portee, rid, ecriture=True)
            for pid in lieux["planches"]:
                _get_planche(conn, portee, pid, ecriture=True)
            # Un personnage n'a pas de collection : il se VOIT par ses apparitions, et
            # l'écrire ne demande que d'écrire quelque part — le plancher de la route.
            for pid in lieux.get("personnages", []):
                _get_personnage(conn, portee, pid)
        except HTTPException as refus:
            if refus.status_code == 404:
                return False
            raise
        return True
    return peut


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
    # Annuler REJOUE une écriture : il faut en avoir le droit quelque part. Ce plancher ne
    # dit pas OÙ ; c'est `_ecrivable` qui le dit, acte par acte, sur les lieux mêmes de
    # l'inverse (AUTH-14 : le résiduel « un droit d'écriture ailleurs suffit » est fermé).
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Annuler demande un droit d'écriture.")
    agent = _agent_undo(portee)
    nlp.ensure_loaded()            # spaCy HORS transaction : l'inversion réindexe, verrou tenu
    conflit.verrouiller(conn)      # l'état que l'annulation garde se lit sous le verrou (Q4)
    try:
        res = undo.annuler(conn, agent=agent, ecrivable=_ecrivable(conn, portee))
    except undo.NeSAnnulePlus as exc:
        # AUTH-14 — l'acte ne s'annule plus (objet disparu, identifiant repris ailleurs,
        # collection qu'on n'écrit plus). On le PASSE : une trace au journal le sort de la
        # pile, et le Ctrl+Z suivant défait le geste d'avant. La trace est validée MALGRÉ
        # le refus — sans elle, ce même 409 reviendrait à chaque Ctrl+Z. Le corps ne porte
        # que la phrase et l'acte passé : rien de l'objet présent, qu'on ne lit peut-être pas.
        # Ce que l'inversion aurait commencé d'écrire est défait AVANT la trace : valider la
        # trace validerait sinon le reste avec elle.
        conn.rollback()
        undo.ecarter(conn, exc.evenement)
        conn.commit()
        raise HTTPException(409, {"message": str(exc),
                                  "ecarte": {"evenement_id": exc.evenement["id"],
                                             "description": exc.description}})
    except undo.UndoImpossible as exc:
        raise HTTPException(409, f"Annulation impossible : {exc}")
    except conflit.Perime as exc:
        # CONC-3 (Q4) — annuler écraserait ce qu'un autre a changé depuis : même 409 nommé
        # qu'un enregistrement périmé, et rien n'est défait (la dépendance `db` roule en
        # arrière ce que l'inversion avait commencé).
        raise HTTPException(409, exc.detail())
    if res is None:
        # Sous un compte partagé, « rien » peut vouloir dire « rien d'assez récent » (AUTH-6) :
        # le dire, sans quoi on croirait l'historique vide. Le message garde « Rien à
        # annuler » en tête — l'Atelier l'affiche alors comme une information, pas une erreur.
        if undo.est_borne(conn, agent):
            raise HTTPException(
                404, f"Rien à annuler dans les {undo.DELAI_COLLECTIF_MINUTES} dernières "
                     "minutes : sur un compte partagé, Ctrl+Z ne remonte pas plus loin.")
        raise HTTPException(404, "Rien à annuler.")
    conn.commit()
    return res
