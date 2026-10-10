"""Projets — l'étage au-dessus des collections (COL-3, tranche 1).

Un PROJET est le périmètre à l'intérieur duquel un travail pourra se partager ; une
collection appartient à UN projet. Dans cette tranche le projet EXISTE et se RÈGLE, et rien
d'autre ne change : ce module ne lit ni n'écrit aucune donnée du corpus, et n'ouvre aucune
collection à personne. Entrer dans un projet n'ouvre pas ses collections — chacune garde son
« Qui entre », dans `routes/collections.py`.

Deux pouvoirs, et le second ne découle pas du premier — c'est la séparation d'AUTH-3, un
étage plus haut. DÉCIDER quels projets existent (créer, renommer, supprimer) revient à une
portée totale : l'administrateur, et le mono-poste. RÉGLER qui est d'un projet (faire
entrer, faire sortir, nommer un autre responsable) revient à son responsable, et à
l'administrateur qui passe outre. Trois refus sont des 409 qui se NOMMENT : supprimer le
projet de repli, supprimer un projet qui porte encore une collection, retirer ou
rétrograder son DERNIER responsable. Un projet peut en revanche naître sans responsable :
seule une portée totale le règle alors.

Ce module APPLIQUE ces règles ; `autorisation.py` les tranche (`clause_projet`,
`peut_gerer_projet`, `peut_decider_des_projets`).

**Une route de ce domaine vit ailleurs, et c'est voulu** : `GET …/membres/choix`, qui lit
l'annuaire pour proposer des groupes, est dans `routes/collections.py`. Les routes qui
lisent l'annuaire tiennent dans UN module, et un test le verrouille par égalité
(`tests/test_annuaire.py`) : en ouvrir un second ici aurait demandé de desserrer cette
garde pour un rangement.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

import autorisation
import journal
from database import LONGUEUR_NOM_PROJET, sql_projet_de

from socle import (
    MembreIn, ProjetIn, ProjetUpdate, _get_projet, _rows, db, portee_courante,
)

router = APIRouter()


_MOTIF_DECIDER = ("Créer, renommer ou supprimer un projet est réservé aux administrateurs "
                  "de l'instance.")


def _exiger_de_decider(portee: autorisation.Portee) -> None:
    """403 nommé à qui ne décide pas des projets. Un 403 et non un 404 : il parle du droit
    de l'appelant, pas d'un projet — rien n'en fuit."""
    if not portee.peut_decider_des_projets():
        raise HTTPException(403, _MOTIF_DECIDER)


def _role_dans(portee: autorisation.Portee, projet_id: int):
    """Le rôle de l'APPELANT dans ce projet. `None` pour une portée totale — même raison
    que `mon_niveau` : elle règle tout sans figurer nulle part — et pour qui ne voit le
    projet que par une collection qu'il lit."""
    if portee.tout:
        return None
    if projet_id in portee.projets_geres:
        return autorisation.RESPONSABLE
    return autorisation.MEMBRE if projet_id in portee.projets else None


def _vue(conn, portee: autorisation.Portee, p: dict) -> dict:
    """Ce qu'on REND d'un projet — le seul endroit où sa ligne devient une réponse.

    `justification` n'y entre QUE pour qui gère le projet (responsable, administrateur) :
    elle dit pourquoi le projet existe, à ceux qui en répondent. Un simple membre, et qui
    ne voit le projet que par une collection, ne reçoivent pas la clé du tout — une clé à
    `null` ne se distinguerait pas d'une justification jamais écrite.

    `nb_collections` compte les collections LUES par l'appelant, pas celles du projet :
    le total dirait à un membre combien d'études existent hors de sa portée, ce que
    « 404, jamais 403 » existe pour ne pas dire."""
    gerable = portee.peut_gerer_projet(p["id"])
    ids = [r[0] for r in conn.execute(
        f"SELECT c.id FROM collection c WHERE {sql_projet_de('c')} = ?", (p["id"],))]
    vue = {"id": p["id"], "nom": p["nom"], "description": p["description"],
           "repli": bool(p["repli"]), "date_creation": p["date_creation"],
           "mon_role": _role_dans(portee, p["id"]), "gerable": gerable,
           "nb_collections": sum(1 for i in ids if portee.peut_lire(i))}
    if gerable:
        vue["justification"] = p["justification"]
    return vue


def _nom_valide(conn, nom, *, sauf: int | None = None) -> str:
    """Le nom d'un projet, nettoyé, ou le refus qui dit pourquoi.

    Il est BORNÉ, et court (`database.LONGUEUR_NOM_PROJET`) : il se lit dans la bande du
    haut de chaque page, où il ne doit ni se couper ni pousser le reste hors de la
    fenêtre. Et il est UNIQUE sans égard à la casse, tenu ici plutôt que par un `UNIQUE`
    en base, qui laisserait passer « Émotions » à côté d'« émotions »."""
    nom = (nom or "").strip()
    if not nom:
        raise HTTPException(422, "Le nom du projet est requis.")
    if len(nom) > LONGUEUR_NOM_PROJET:
        raise HTTPException(
            422, f"Le nom d'un projet tient en {LONGUEUR_NOM_PROJET} caractères au plus "
                 f"(« {nom} » en fait {len(nom)}) : il se lit en haut de chaque page, où "
                 "il ne doit pas se couper.")
    for r in conn.execute("SELECT id, nom FROM projet"):
        if r["id"] != sauf and r["nom"].strip().casefold() == nom.casefold():
            raise HTTPException(409, f"Un projet s'appelle déjà « {r['nom']} ».")
    return nom


def _membres_de(conn, projet_id: int) -> list[dict]:
    """Les membres d'un projet, responsables d'abord. Le jumeau de `_acces_de`.

    `jamais_vu` RAPPORTE et n'explique rien : un login absent du miroir `utilisateur` est
    une faute de frappe ou un arrivant qui n'est pas encore venu, et rien ne les
    départage. `None` pour un groupe, jamais `False` — l'application ne sait d'un groupe
    que ce que le portail transmet pour la personne qui frappe."""
    lignes = _rows(conn.execute(
        "SELECT genre, principal, role, date_creation FROM projet_acces "
        "WHERE projet_id = ? ORDER BY CASE role WHEN ? THEN 0 ELSE 1 END, genre, principal",
        (projet_id, autorisation.RESPONSABLE)))
    logins = sorted({m["principal"] for m in lignes
                     if m["genre"] == autorisation.UTILISATEUR})
    connus = set()
    if logins:
        qm = ",".join("?" * len(logins))
        connus = {r[0] for r in conn.execute(
            f"SELECT login FROM utilisateur WHERE login IN ({qm})", logins)}
    for m in lignes:
        m["jamais_vu"] = (m["principal"] not in connus
                          if m["genre"] == autorisation.UTILISATEUR else None)
    return lignes


def _compte_responsables(conn, projet_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM projet_acces WHERE projet_id = ? AND role = ?",
        (projet_id, autorisation.RESPONSABLE)).fetchone()[0]


# --------------------------------------------------------------------------- #
# Les projets
# --------------------------------------------------------------------------- #
@router.get("/api/projets")
def list_projets(conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Les projets qu'on peut NOMMER : ceux dont on est, et ceux d'une collection qu'on
    lit. Le projet de repli d'abord, puis par nom.

    C'est ce que la barre du haut lira pour dire dans quel projet on travaille. Une
    portée vide rend une liste vide, comme partout ; une portée totale les rend tous.
    Aucune identité n'en sort : la liste ne nomme ni membres ni responsables."""
    ou, params = portee.clause_projet("p.id")
    lignes = _rows(conn.execute(
        f"SELECT p.* FROM projet p WHERE {ou} "
        "ORDER BY p.repli DESC, p.nom COLLATE NOCASE, p.id", params))
    return [_vue(conn, portee, p) for p in lignes]


@router.post("/api/projets", status_code=201)
def create_projet(payload: ProjetIn, conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Crée un projet, VIDE : ni collection, ni membre, ni responsable. Qui le crée n'y
    entre pas pour autant — un administrateur règle tout projet sans en être, et lui
    inventer un rôle fausserait la liste de ceux qui y travaillent (la raison écrite sur
    `create_collection`).

    `justification` se saisit ici : pourquoi ce projet existe."""
    _exiger_de_decider(portee)
    nom = _nom_valide(conn, payload.nom)
    cur = conn.execute(
        "INSERT INTO projet (nom, description, justification) VALUES (?, ?, ?)",
        (nom, payload.description, payload.justification))
    pid = cur.lastrowid
    journal.journaliser(conn, "creation", "projet", pid, apres={"nom": nom})
    conn.commit()
    return _vue(conn, portee, _get_projet(conn, portee, pid))


@router.patch("/api/projets/{projet_id}")
def update_projet(projet_id: int, payload: ProjetUpdate,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Renomme un projet, ou en change la description et la justification.

    Réservé à qui DÉCIDE des projets, pas à qui gère celui-ci : le nom d'un projet se lit
    sur l'écran de tous ceux qui y travaillent. 404 sur un projet qu'on ne voit pas, 403
    nommé sur un projet qu'on voit — y compris pour son responsable.

    Le projet de repli se renomme comme un autre : il est désigné par son drapeau."""
    p = _get_projet(conn, portee, projet_id)
    _exiger_de_decider(portee)
    fields = payload.model_dump(exclude_unset=True)
    if "nom" in fields:
        # Un nom INCHANGÉ ne se revalide pas : baisser le plafond un jour ne doit pas rendre
        # impossible de corriger la description d'un projet nommé avant.
        nom = (fields["nom"] or "").strip()
        fields["nom"] = nom if nom == p["nom"] else _nom_valide(conn, nom, sauf=projet_id)
    # Ce qui CHANGE, et rien d'autre : le journal n'a pas à inventer une modification.
    changes = {k: v for k, v in fields.items() if p[k] != v}
    if changes:
        cols = ", ".join(f"{k} = ?" for k in changes)
        conn.execute(f"UPDATE projet SET {cols} WHERE id = ?",
                     (*changes.values(), projet_id))
        journal.journaliser(conn, "modification", "projet", projet_id,
                            avant={k: p[k] for k in changes}, apres=changes)
        conn.commit()
    return _vue(conn, portee, _get_projet(conn, portee, projet_id))


@router.delete("/api/projets/{projet_id}", status_code=204)
def delete_projet(projet_id: int, conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime un projet VIDE. Ses membres en sortent avec lui (`ON DELETE CASCADE`).

    Deux refus qui se nomment. Le projet de REPLI ne se supprime pas : c'est là que tombe
    toute collection qui ne nomme pas le sien. Et un projet qui PORTE une collection non
    plus : la reverser en silence dans le repli la ferait changer de projet sans que
    personne l'ait décidé, et aucun geste ne déplace une collection dans cette tranche. La
    clé étrangère, sans action, est la ceinture derrière ce refus."""
    p = _get_projet(conn, portee, projet_id)
    _exiger_de_decider(portee)
    if p["repli"]:
        raise HTTPException(409, "C'est le projet de repli : les collections qui ne "
                                 "nomment aucun projet y sont rangées. Il se renomme, il "
                                 "ne se supprime pas.")
    n = conn.execute(f"SELECT COUNT(*) FROM collection c WHERE {sql_projet_de('c')} = ?",
                     (projet_id,)).fetchone()[0]
    if n:
        raise HTTPException(409, f"{n} collection(s) appartiennent à ce projet : un "
                                 "projet ne se supprime que vide.")
    conn.execute("DELETE FROM projet WHERE id = ?", (projet_id,))
    journal.journaliser(conn, "suppression", "projet", projet_id, avant={"nom": p["nom"]})
    conn.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Qui est d'un projet
# --------------------------------------------------------------------------- #
@router.get("/api/projets/{projet_id}/membres")
def list_membres(projet_id: int, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Qui est de ce projet, et sous quel rôle. Réservé à qui le GÈRE : la liste des
    membres est une donnée sur des PERSONNES, et un simple membre n'a pas à savoir qui
    d'autre en est, ni qui en répond."""
    _get_projet(conn, portee, projet_id, gerer=True)
    return _membres_de(conn, projet_id)


@router.put("/api/projets/{projet_id}/membres")
def poser_membre(projet_id: int, payload: MembreIn,
                 conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Fait entrer quelqu'un dans le projet, ou change son rôle. Idempotent : « nommer
    responsable » et « rétrograder » sont le même geste, comme pour un accès.

    `principal` est un NOM — un login, ou un groupe tel que le portail le transmet. Cette
    route NE LIT PAS l'annuaire : un nom mal orthographié n'ouvre simplement rien, et c'est
    la relecture par `…/membres/choix` qui le signale, jamais un refus ici.

    ELLE N'OUVRE AUCUNE COLLECTION. Être du projet permet d'y créer une collection, et
    c'est tout ; lire l'une des siennes se règle dans son « Qui entre »."""
    _get_projet(conn, portee, projet_id, gerer=True)
    if payload.genre not in autorisation.GENRES:
        raise HTTPException(422, f"Genre invalide : {payload.genre} (utilisateur | groupe).")
    if payload.role not in autorisation.ROLES_PROJET:
        raise HTTPException(
            422, f"Rôle invalide : {payload.role} ({' | '.join(autorisation.ROLES_PROJET)}).")
    principal = (payload.principal or "").strip()
    if not principal:
        raise HTTPException(422, "Le principal (login ou nom de groupe) est requis.")
    avant = conn.execute(
        "SELECT role FROM projet_acces WHERE projet_id = ? AND genre = ? AND principal = ?",
        (projet_id, payload.genre, principal)).fetchone()
    # Un projet peut NAÎTRE sans responsable ; il ne PERD pas son dernier par ce geste.
    # Sans ce refus, un responsable se rétrograderait seul et laisserait un projet que
    # plus personne ne règle, hors l'administrateur.
    if (payload.role != autorisation.RESPONSABLE and avant is not None
            and avant["role"] == autorisation.RESPONSABLE
            and _compte_responsables(conn, projet_id) == 1):
        raise HTTPException(409, "C'est le dernier responsable de ce projet : "
                                 "désignez-en un autre avant de le rétrograder.")
    conn.execute(
        "INSERT INTO projet_acces (projet_id, genre, principal, role) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(projet_id, genre, principal) DO UPDATE SET role = excluded.role",
        (projet_id, payload.genre, principal, payload.role))
    # Qui a fait entrer qui, et quand — non annulable : `projet_acces` n'est pas dans la
    # liste blanche de l'annulation. `cible_id` est le PROJET, la table n'ayant pas d'id.
    journal.journaliser(conn, "lien", "projet_acces", projet_id,
                        avant={"genre": payload.genre, "principal": principal,
                               "role": avant["role"]} if avant else None,
                        apres={"genre": payload.genre, "principal": principal,
                               "role": payload.role})
    conn.commit()
    return _membres_de(conn, projet_id)


@router.delete("/api/projets/{projet_id}/membres/{genre}/{principal}", status_code=204)
def retirer_membre(projet_id: int, genre: str, principal: str,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Fait sortir quelqu'un du projet. Ne retire AUCUN accès de collection, et ne détruit
    rien : ce qu'il lisait, il le lit encore, et le journal lui attribue toujours son
    travail. Refus sur le dernier responsable."""
    _get_projet(conn, portee, projet_id, gerer=True)
    ligne = conn.execute(
        "SELECT role FROM projet_acces WHERE projet_id = ? AND genre = ? AND principal = ?",
        (projet_id, genre, principal)).fetchone()
    if ligne is None:
        raise HTTPException(404, "Ce membre n'existe pas.")
    if (ligne["role"] == autorisation.RESPONSABLE
            and _compte_responsables(conn, projet_id) == 1):
        raise HTTPException(409, "C'est le dernier responsable de ce projet : "
                                 "désignez-en un autre avant de le retirer.")
    conn.execute("DELETE FROM projet_acces WHERE projet_id = ? AND genre = ? "
                 "AND principal = ?", (projet_id, genre, principal))
    journal.journaliser(conn, "delien", "projet_acces", projet_id,
                        avant={"genre": genre, "principal": principal,
                               "role": ligne["role"]})
    conn.commit()
    return Response(status_code=204)
