"""Le fonds — ce que l'instance détient, et les demandes qui en sortent (COL-3, tranche 2).

Tout album est la COPIE DE TRAVAIL d'un document, et le document appartient à l'instance
(v30). Le FONDS n'est pas une table : c'est l'ensemble des documents, dont certains ne sont
plus appelés par aucune collection — une copie qu'on a supprimée de sa dernière collection
y est GARDÉE avec son travail, et un administrateur peut la rendre.

« Supprimer définitivement » a deux réponses, et ce module porte la seconde. Qui a importé
un document, seul à y avoir travaillé, l'efface tout de suite (`DELETE /api/albums/{id}`,
règle `Portee.clause_suppression_directe`). Sinon il DEMANDE : la demande dit qui, quand et
pourquoi, et un administrateur y répond — détruire, ou garder. Aucune messagerie. Le même
mécanisme porte la demande de suppression d'un PROJET par son responsable ; il est bâti
pour porter plusieurs documents, ce qu'une entrée de documents demandera à la tranche
suivante.

Qui voit quoi. Le fonds et les demandes sont à qui TIENT le fonds — une portée totale :
l'administrateur, et le mono-poste (`Portee.peut_tenir_le_fonds`). Les trois routes qui leur
répondent refusent sur le DROIT de l'appelant AVANT de chercher l'objet : un 403 nommé, le
même que l'identifiant existe ou non — la forme de `comptes_et_groupes`. Déposer une
demande, lui, passe par l'accesseur gardé en écriture : 404 à qui n'écrit pas dans l'album,
comme partout.

Ce module APPLIQUE ; `autorisation.py` tranche. Il ne lit ni `config.AUTH_PROXY` (la
fixture des tests ne remplace que celui de `main` et d'`autorisation`) ni l'annuaire : les
noms viennent du miroir `utilisateur`.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

import autorisation
import conflit
import journal
from database import (DEMANDE_SUPPRESSION_DOCUMENT, DEMANDE_SUPPRESSION_PROJET,
                      GENRES_DEMANDE, LONGUEUR_MOTIF, REPONSE_ACCEPTEE, REPONSE_REFUSEE,
                      REPONSES_DEMANDE, noms_lisibles, projet_d_album, sql_projet_d_album)

from socle import (
    DemandeIn, ReponseIn, _clore_demandes, _detruire_album, _get_album, _get_projet,
    _rows, _supprimer_projet, db, portee_courante,
)

router = APIRouter()


_MOTIF_FONDS = ("Le fonds et les demandes sont réservés aux administrateurs de l'instance : "
                "ils portent sur tout ce qu'elle détient.")


def _exiger_le_fonds(portee: autorisation.Portee) -> None:
    """403 nommé à qui ne tient pas le fonds — AVANT toute lecture : il parle du droit de
    l'appelant, pas d'un objet, et se lit donc pareil sur un identifiant qui n'existe pas."""
    if not portee.peut_tenir_le_fonds():
        raise HTTPException(403, _MOTIF_FONDS)


def _motif(texte) -> str:
    """Le « pourquoi » d'une demande, OBLIGATOIRE : c'est la moitié de ce que
    l'administrateur doit lire. Borné, pour qu'un champ libre ne devienne pas un dépôt."""
    motif = (texte or "").strip()
    if not motif:
        raise HTTPException(422, "Dites pourquoi : une demande sans motif ne se lit pas.")
    if len(motif) > LONGUEUR_MOTIF:
        raise HTTPException(422, f"Le motif tient en {LONGUEUR_MOTIF} caractères au plus "
                                 f"({len(motif)} reçus).")
    return motif


def _en_attente(conn, *, document_id=None, projet_id=None):
    """La demande EN ATTENTE sur ce document, ou sur ce projet ; None s'il n'y en a pas."""
    if document_id is not None:
        return conn.execute(
            "SELECT d.* FROM demande d JOIN demande_document dd ON dd.demande_id = d.id "
            "WHERE d.genre = ? AND dd.document_id = ? AND d.reponse IS NULL "
            "ORDER BY d.id LIMIT 1",
            (DEMANDE_SUPPRESSION_DOCUMENT, document_id)).fetchone()
    return conn.execute(
        "SELECT * FROM demande WHERE genre = ? AND projet_id = ? AND reponse IS NULL "
        "ORDER BY id LIMIT 1", (DEMANDE_SUPPRESSION_PROJET, projet_id)).fetchone()


def _deja_demandee(conn, ligne) -> HTTPException:
    nom = noms_lisibles(conn, [ligne["demandeur"]]).get(ligne["demandeur"])
    qui = nom or ligne["demandeur"] or "quelqu'un"
    return HTTPException(409, f"Cette suppression est déjà demandée, par {qui} le "
                              f"{(ligne['date_creation'] or '')[:10]} : un administrateur "
                              "y répondra.")


# --------------------------------------------------------------------------- #
# Déposer une demande
# --------------------------------------------------------------------------- #
@router.post("/api/demandes", status_code=201)
def deposer_demande(payload: DemandeIn, conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Demander à un administrateur ce qu'on ne peut pas faire seul : supprimer
    définitivement un album, ou — pour son responsable — supprimer un projet.

    Un DOCUMENT se demande depuis l'album où l'on écrit : l'accesseur gardé en écriture
    répond 404 à qui ne l'y écrit pas, comme à un album qui n'existe pas. Un PROJET se
    demande par qui le gère : 404 à qui ne le voit pas, 403 nommé à qui le voit sans le
    gérer. Deux refus 409 qui se nomment, dans les deux cas : la même suppression est déjà
    demandée ; et l'appelant peut la faire lui-même — demander ce qu'on a le droit de faire
    enverrait à un administrateur un geste qui ne lui revient pas."""
    if payload.genre not in GENRES_DEMANDE:
        raise HTTPException(422, f"Genre de demande inconnu : {payload.genre} "
                                 f"({' | '.join(GENRES_DEMANDE)}).")
    motif = _motif(payload.motif)
    if payload.genre == DEMANDE_SUPPRESSION_DOCUMENT:
        return _demander_un_document(conn, portee, payload.album_id, motif)
    return _demander_un_projet(conn, portee, payload.projet_id, motif)


def _demander_un_document(conn, portee, album_id, motif):
    if album_id is None:
        raise HTTPException(422, "Quel album ? (`album_id`)")
    a = _get_album(conn, portee, album_id, ecriture=True)
    # Ce qui suit se lit sous le verrou d'écriture : deux demandes simultanées sur le même
    # document passaient sinon toutes deux le refus du doublon.
    conflit.verrouiller(conn)
    ou, params = portee.clause_suppression_directe("a.id")
    if conn.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ou}",
                    (album_id, *params)).fetchone():
        raise HTTPException(409, "Vous pouvez supprimer cet album définitivement vous-même : "
                                 "il n'y a rien à demander.")
    if a["document_id"] is None:
        # Un album posé hors de tout chemin d'écriture (base retouchée) : la demande ne
        # saurait pas quel document elle vise.
        raise HTTPException(409, "Cet album n'est la copie d'aucun document : sa "
                                 "suppression ne peut pas se demander. Signalez-le à un "
                                 "administrateur.")
    attente = _en_attente(conn, document_id=a["document_id"])
    if attente is not None:
        raise _deja_demandee(conn, attente)
    projet_id = projet_d_album(conn, album_id)
    projet = conn.execute("SELECT nom FROM projet WHERE id = ?", (projet_id,)).fetchone()
    cur = conn.execute(
        "INSERT INTO demande (genre, demandeur, motif, projet_id, projet_nom) "
        "VALUES (?, ?, ?, ?, ?)",
        (DEMANDE_SUPPRESSION_DOCUMENT, portee.utilisateur, motif, projet_id,
         projet[0] if projet else None))
    conn.execute("INSERT INTO demande_document (demande_id, document_id, album_id, titre) "
                 "VALUES (?, ?, ?, ?)", (cur.lastrowid, a["document_id"], album_id,
                                         a["titre"]))
    # Le motif reste sur la demande : le journal dit qu'elle a été déposée, et sur quoi.
    journal.journaliser(conn, "creation", "demande", cur.lastrowid,
                        apres={"genre": DEMANDE_SUPPRESSION_DOCUMENT,
                               "document_id": a["document_id"], "album_id": album_id})
    conn.commit()
    return _vue_demande(conn, cur.lastrowid)


def _demander_un_projet(conn, portee, projet_id, motif):
    if projet_id is None:
        raise HTTPException(422, "Quel projet ? (`projet_id`)")
    p = _get_projet(conn, portee, projet_id, gerer=True,
                    motif="Demander la suppression d'un projet revient à son responsable.")
    if p["repli"]:
        raise HTTPException(409, "C'est le projet de repli : il se renomme, il ne se "
                                 "supprime pas.")
    if portee.peut_decider_des_projets():
        raise HTTPException(409, "Vous pouvez supprimer ce projet vous-même : il n'y a rien "
                                 "à demander.")
    conflit.verrouiller(conn)                 # le refus du doublon, sous le verrou
    attente = _en_attente(conn, projet_id=projet_id)
    if attente is not None:
        raise _deja_demandee(conn, attente)
    cur = conn.execute(
        "INSERT INTO demande (genre, demandeur, motif, projet_id, projet_nom) "
        "VALUES (?, ?, ?, ?, ?)",
        (DEMANDE_SUPPRESSION_PROJET, portee.utilisateur, motif, projet_id, p["nom"]))
    journal.journaliser(conn, "creation", "demande", cur.lastrowid,
                        apres={"genre": DEMANDE_SUPPRESSION_PROJET, "projet_id": projet_id})
    conn.commit()
    return _vue_demande(conn, cur.lastrowid)


# --------------------------------------------------------------------------- #
# Lire les demandes, y répondre
# --------------------------------------------------------------------------- #
def _vues_demandes(conn, ids=None) -> list[dict]:
    """Les demandes telles qu'une route les REND, les plus récentes d'abord. Quatre
    requêtes, aucune par demande."""
    where, params = "", []
    if ids is not None:
        where = f"WHERE id IN ({', '.join('?' * len(ids))})"
        params = list(ids)
    demandes = _rows(conn.execute(f"SELECT * FROM demande {where} ORDER BY id DESC", params))
    if not demandes:
        return []
    marques = ", ".join("?" * len(demandes))
    docs: dict[int, list] = {}
    for dd in _rows(conn.execute(
            "SELECT dd.*, (SELECT a.id FROM albums a WHERE a.document_id = dd.document_id "
            "              ORDER BY a.id LIMIT 1) AS copie "
            f"FROM demande_document dd WHERE dd.demande_id IN ({marques}) "
            "ORDER BY dd.document_id", [d["id"] for d in demandes])):
        docs.setdefault(dd.pop("demande_id"), []).append(dd)
    # Une demande ENCORE en attente dit si la même suppression a déjà été refusée : sans
    # cela, l'administrateur répondrait sans savoir qu'il a déjà gardé ce document.
    refus = {}
    for d in _rows(conn.execute(
            "SELECT d.genre, d.projet_id, dd.document_id, d.id FROM demande d "
            "LEFT JOIN demande_document dd ON dd.demande_id = d.id "
            "WHERE d.reponse = ?", (REPONSE_REFUSEE,))):
        cle = (d["genre"], d["document_id"] if d["genre"] == DEMANDE_SUPPRESSION_DOCUMENT
               else d["projet_id"])
        refus.setdefault(cle, set()).add(d["id"])
    noms = noms_lisibles(conn, [x for d in demandes
                                for x in (d["demandeur"], d["repondu_par"]) if x])
    for d in demandes:
        d["demandeur_nom"] = noms.get(d["demandeur"])
        d["repondu_par_nom"] = noms.get(d["repondu_par"])
        d["en_attente"] = d["reponse"] is None
        d["documents"] = [{"document_id": x["document_id"], "album_id": x["album_id"],
                           "titre": x["titre"], "reponse": x["reponse"],
                           "copie": x["copie"]}
                          for x in docs.get(d["id"], [])]
        if d["genre"] == DEMANDE_SUPPRESSION_DOCUMENT:
            cles = [(d["genre"], x["document_id"]) for x in d["documents"]]
        else:
            cles = [(d["genre"], d["projet_id"])]
        d["refus_anterieurs"] = len({i for c in cles for i in refus.get(c, ())
                                     if i < d["id"]})
    return demandes


def _vue_demande(conn, demande_id: int) -> dict:
    return _vues_demandes(conn, [demande_id])[0]


@router.get("/api/demandes")
def list_demandes(conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Toutes les demandes, en attente ou répondues — une demande répondue RESTE : c'est
    ce qui permet de dire qu'une même suppression a déjà été refusée. Réservée à qui tient
    le fonds : elle nomme qui demande, et dit pourquoi."""
    _exiger_le_fonds(portee)
    return _vues_demandes(conn)


@router.post("/api/demandes/{demande_id}/reponse")
def repondre_demande(demande_id: int, payload: ReponseIn,
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Répondre à une demande : l'accepter — le document est détruit, le projet supprimé —
    ou la refuser — il est gardé. Une seule réponse par demande : 409 sur la seconde.

    Le droit d'abord, l'objet ensuite : 403 nommé à qui ne tient pas le fonds, que la
    demande existe ou non. Accepter la suppression d'un projet passe par les MÊMES refus
    que `DELETE /api/projets/{id}`, qui se nomment : la demande reste alors en attente, et
    l'administrateur sait ce qui manque. Refuser n'efface rien : la demande reste, close,
    et celui qui l'avait déposée peut la déposer de nouveau."""
    _exiger_le_fonds(portee)
    if payload.reponse not in REPONSES_DEMANDE:
        raise HTTPException(422, f"Réponse inconnue : {payload.reponse} "
                                 f"({' | '.join(REPONSES_DEMANDE)}).")
    # La demande se lit SOUS LE VERROU d'écriture, et la réponse suit dans la même
    # transaction : deux administrateurs qui répondent ensemble ne passent plus tous deux
    # le 409 « déjà répondue » (relecture croisée de la tranche 2).
    conflit.verrouiller(conn)
    d = conn.execute("SELECT * FROM demande WHERE id = ?", (demande_id,)).fetchone()
    if d is None:
        raise HTTPException(404, f"Demande {demande_id} introuvable")
    if d["reponse"] is not None:
        raise HTTPException(409, "Cette demande a déjà reçu sa réponse.")

    if payload.reponse == REPONSE_REFUSEE:
        _clore_demandes(conn, portee, [demande_id], REPONSE_REFUSEE)
        conn.commit()
        return _vue_demande(conn, demande_id)

    if d["genre"] == DEMANDE_SUPPRESSION_PROJET:
        p = conn.execute("SELECT * FROM projet WHERE id = ?", (d["projet_id"],)).fetchone()
        if p is None:
            # Supprimé depuis, par un autre geste : la demande est satisfaite.
            _clore_demandes(conn, portee, [demande_id], REPONSE_ACCEPTEE)
        else:
            _supprimer_projet(conn, portee, dict(p))      # ses refus 409, tels quels
        conn.commit()
        return _vue_demande(conn, demande_id)

    # Un document : chacune de ses copies est détruite, et la destruction clôt d'elle-même
    # toute demande qui la visait — celle-ci comprise. Un document déjà parti n'a plus
    # rien à détruire : la demande se clôt seule.
    copies = [r[0] for r in conn.execute(
        "SELECT a.id FROM albums a JOIN demande_document dd ON dd.document_id = a.document_id "
        "WHERE dd.demande_id = ? ORDER BY a.id", (demande_id,))]
    if not copies:
        _clore_demandes(conn, portee, [demande_id], REPONSE_ACCEPTEE)
        conn.commit()
    for album_id in copies:
        _detruire_album(conn, portee, album_id)        # commite, puis efface les fichiers
    return _vue_demande(conn, demande_id)


# --------------------------------------------------------------------------- #
# Le fonds
# --------------------------------------------------------------------------- #
@router.get("/api/fonds")
def lire_le_fonds(conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Les documents de l'instance : d'où chacun vient (qui l'a importé, quand, dans quel
    projet d'abord), ses copies de travail avec leur projet et leurs collections, s'il est
    appelé par personne, et la demande de suppression qui l'attend.

    Réservée à qui tient le fonds. Un responsable de projet n'en reçoit rien dans cette
    tranche : la notice qu'on lui ouvrira arrivera avec le geste qui en a besoin (« prendre
    un document »), par une lecture à part. Un nombre FIXE de requêtes — une dizaine,
    demandes comprises —, aucune par document : rien n'en a été mesuré sur un gros fonds."""
    _exiger_le_fonds(portee)
    documents = _rows(conn.execute(
        "SELECT d.id, d.importe_par, d.importe_le, d.projet_origine_id, "
        "       p.nom AS projet_origine_nom "
        "FROM document d LEFT JOIN projet p ON p.id = d.projet_origine_id "
        "ORDER BY d.id"))
    copies: dict[int, list] = {}
    for a in _rows(conn.execute(
            f"SELECT a.id AS album_id, a.document_id, a.titre, a.serie, a.auteur, "
            f"       {sql_projet_d_album('a')} AS projet_id, "
            "       (SELECT COUNT(*) FROM planches pl WHERE pl.album_id = a.id) AS nb_planches "
            "FROM albums a WHERE a.document_id IS NOT NULL ORDER BY a.id")):
        a["collections"] = []
        copies.setdefault(a.pop("document_id"), []).append(a)
    par_album = {a["album_id"]: a for liste in copies.values() for a in liste}
    for r in conn.execute(
            "SELECT ca.album_id, c.id, c.nom FROM collection_album ca "
            "JOIN collection c ON c.id = ca.collection_id ORDER BY c.nom, c.id"):
        if r["album_id"] in par_album:
            par_album[r["album_id"]]["collections"].append({"id": r["id"], "nom": r["nom"]})
    projets = {r["id"]: r["nom"] for r in conn.execute("SELECT id, nom FROM projet")}
    for a in par_album.values():
        a["projet_nom"] = projets.get(a["projet_id"])
    attente = {}
    for d in _vues_demandes(conn):
        if d["en_attente"] and d["genre"] == DEMANDE_SUPPRESSION_DOCUMENT:
            for x in d["documents"]:
                attente.setdefault(x["document_id"], d)
    noms = noms_lisibles(conn, [d["importe_par"] for d in documents if d["importe_par"]])
    for d in documents:
        d["importe_par_nom"] = noms.get(d["importe_par"])
        d["copies"] = copies.get(d["id"], [])
        d["appele"] = any(a["collections"] for a in d["copies"])
        dem = attente.get(d["id"])
        d["demande"] = None if dem is None else {
            k: dem[k] for k in ("id", "demandeur", "demandeur_nom", "motif",
                                "date_creation", "refus_anterieurs")}
    sans = [r[0] for r in conn.execute(
        "SELECT id FROM albums WHERE document_id IS NULL ORDER BY id")]
    return {"documents": documents, "copies_sans_document": sans}
