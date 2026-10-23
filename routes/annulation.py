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
from pydantic import BaseModel

import autorisation
import conflit
import undo
from pipeline import nlp

from socle import (_get_personnage, _get_planche, _get_region, _get_valeur, db,
                   portee_courante)

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
            # ANN-8 — la valeur d'un attribut de case que rendrait l'annulation d'une
            # suppression : un terme, qui se VOIT par la portée des termes. La route qui la
            # pose ne demande que de la voir (`_affecter`) : la même question ici.
            for vid in lieux.get("valeurs", []):
                _get_valeur(conn, portee, vid)
            # ANN-8 — un tag que l'annulation retrouverait par sa CLÉ (`undo._tag_a_rendre`)
            # doit être un tag que l'agent VOIT : sinon, deux lignes de même clé lui feraient
            # poser celle d'une collection qu'il ne lit pas.
            ou, params = portee.clause_terme("t.collection_id")
            for tid in lieux.get("tags", []):
                if conn.execute(f"SELECT 1 FROM tags t WHERE t.id = ? AND {ou}",
                                (tid, *params)).fetchone() is None:
                    return False
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
    return undo.apercu(conn, agent=_agent_undo(portee),
                       voit=undo.voit_valeur(_ecrivable(conn, portee)))


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
    # spaCy HORS transaction : l'inversion réindexe, verrou tenu. Mais pas toujours — défaire
    # un locuteur ou une présence ne réindexe rien, et le premier Ctrl+Z après un redémarrage
    # payait pour rien les 9 à 17 s du chargement à froid (ANN-8, mesuré). L'acte se regarde
    # ici hors verrou ; si un autre le remplace d'ici l'inversion, celle-ci chargera le moteur
    # elle-même, verrou tenu — plus lent, jamais faux.
    prochain = undo.derniere_action_annulable(conn, agent)
    if prochain is not None and undo.reindexe(prochain):
        nlp.ensure_loaded()
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
        # arrière ce que l'inversion avait commencé). ANN-8 — le corps dit QUEL acte reste en
        # tête de la pile, pour que l'écran offre de le passer (`POST /api/undo/passer`) :
        # celui que `annuler` a relu SOUS le verrou et joint au refus, et non `prochain`, lu
        # avant lui — un geste arrivé entre-temps aurait fait désigner le mauvais acte.
        detail = exc.detail()
        refuse = getattr(exc, "evenement", None)
        if refuse is not None:
            detail["passable"] = {"evenement_id": refuse["id"]}
        raise HTTPException(409, detail)
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

class PasserIn(BaseModel):
    evenement_id: int


@router.post("/api/undo/passer")
def undo_passer(payload: PasserIn, conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    """« Passer ce geste » — ANN-8, décision de Hugo du 2026-10-22.

    Quand Ctrl+Z est refusé par un conflit (CONC-3 : l'annuler écraserait ce qu'un autre a
    fait depuis), l'acte RESTE en tête de la pile, et chaque Ctrl+Z redonne le même refus :
    les gestes plus anciens étaient hors de portée (`docs/undo.md`). À la demande de la
    personne, cette route pose la trace `abandon` d'AUTH-14 (`undo.ecarter`) : l'acte sort de
    la pile, le Ctrl+Z suivant remonte au geste d'avant, et le travail de l'autre reste.

    Deux gardes, posées sous le verrou d'écriture :
    - l'acte est bien le PROCHAIN que CET agent annulerait — on ne passe ni l'acte d'un autre,
      ni un acte enfoui sous un geste plus récent (409 sinon) ;
    - le conflit TIENT au moment du clic : l'annulation est rejouée, puis défaite. Si elle
      passe désormais — l'autre a défait son geste —, rien n'est passé : 409, « refaites
      Ctrl+Z ». Un acte qui ne s'annule plus du tout (AUTH-14) est passé, comme Ctrl+Z
      l'aurait fait."""
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Annuler demande un droit d'écriture.")
    agent = _agent_undo(portee)
    prochain = undo.derniere_action_annulable(conn, agent)
    if prochain is not None and undo.reindexe(prochain):
        nlp.ensure_loaded()
    conflit.verrouiller(conn)
    e = undo.derniere_action_annulable(conn, agent)
    if e is None or e["id"] != payload.evenement_id:
        raise HTTPException(409, "Ce geste n'est plus le prochain à annuler : refaites Ctrl+Z.")
    ecrivable = _ecrivable(conn, portee)
    conn.execute("SAVEPOINT passer_un_geste")
    try:
        undo.annuler(conn, e["id"], agent=agent, ecrivable=ecrivable)
    except (conflit.Perime, undo.NeSAnnulePlus):
        pass                                 # le refus tient : on passe
    except undo.UndoImpossible as exc:
        conn.execute("ROLLBACK TO passer_un_geste")
        raise HTTPException(409, f"Annulation impossible : {exc}")
    else:
        conn.execute("ROLLBACK TO passer_un_geste")
        raise HTTPException(409, "Ce geste s'annule maintenant : refaites Ctrl+Z.")
    conn.execute("ROLLBACK TO passer_un_geste")
    conn.execute("RELEASE passer_un_geste")
    undo.ecarter(conn, e)
    conn.commit()
    return {"evenement_id": e["id"],
            "description": undo.apercu_de(e, voit=undo.voit_valeur(ecrivable))}
