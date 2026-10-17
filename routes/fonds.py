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
                      GENRES_DEMANDE, LONGUEUR_MOTIF, NATURE_COLLECTIF, REPONSE_ACCEPTEE,
                      REPONSE_REFUSEE, REPONSES_DEMANDE, noms_lisibles, projet_d_album,
                      sql_projet_d_album)

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


_MOTIF_CERTIFIER = ("Cochez la certification : supprimer définitivement détruit tout ce qui a "
                    "été posé sur les planches, et la demande ne part pas sans que vous "
                    "certifiiez que ces données ne sont pas importantes.")


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


def _en_attente(conn, *, album_id=None, projet_id=None):
    """La demande EN ATTENTE sur cette copie, ou sur ce projet ; None s'il n'y en a pas.

    Par COPIE et non par document (COL-3, tranche 3, D5) : « supprimer définitivement »
    détruit une copie, et la même demande sur la copie SŒUR, dans un autre projet, est une
    autre demande — la chercher par document y aurait répondu « déjà demandée » pour un geste
    fait ailleurs, en nommant au passage qui l'avait fait."""
    if album_id is not None:
        return conn.execute(
            "SELECT d.* FROM demande d JOIN demande_document dd ON dd.demande_id = d.id "
            "WHERE d.genre = ? AND dd.album_id = ? AND d.reponse IS NULL "
            "ORDER BY d.id LIMIT 1",
            (DEMANDE_SUPPRESSION_DOCUMENT, album_id)).fetchone()
    return conn.execute(
        "SELECT * FROM demande WHERE genre = ? AND projet_id = ? AND reponse IS NULL "
        "ORDER BY id LIMIT 1", (DEMANDE_SUPPRESSION_PROJET, projet_id)).fetchone()


def _deja_demandee(conn, portee, ligne) -> HTTPException:
    """Le refus du doublon. Il dit QUI a demandé à la seule personne qui le peut lire —
    elle-même (« par vous ») ou une portée totale (`Portee.peut_nommer_le_demandeur`) ;
    aux autres, qu'elle est demandée et depuis quand, sans nom. Une portée totale n'arrive
    d'ailleurs jamais ici : elle reçoit d'abord « vous pouvez le faire vous-même »."""
    quand = (ligne["date_creation"] or "")[:10]
    qui = ""
    if ligne["demandeur"] and portee.peut_nommer_le_demandeur(ligne["demandeur"]):
        if ligne["demandeur"] == portee.utilisateur:
            qui = "vous"
        else:
            qui = (noms_lisibles(conn, [ligne["demandeur"]]).get(ligne["demandeur"])
                   or ligne["demandeur"])
    if qui:
        return HTTPException(409, f"Cette suppression est déjà demandée, par {qui} le "
                                  f"{quand} : un administrateur y répondra.")
    return HTTPException(409, f"Cette suppression est déjà demandée, depuis le {quand} : "
                              "un administrateur y répondra.")


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
    enverrait à un administrateur un geste qui ne lui revient pas.

    Un document demande en plus une CERTIFICATION (Hugo, 2026-10-15) : que les données
    posées sur ses planches — découpage, transcription, annotations, métadonnées — ne
    sont pas importantes. 422 nommé sans elle ; sa date est écrite sur la demande
    (`certifie_le`), et l'administrateur la lit."""
    if payload.genre not in GENRES_DEMANDE:
        raise HTTPException(422, f"Genre de demande inconnu : {payload.genre} "
                                 f"({' | '.join(GENRES_DEMANDE)}).")
    motif = _motif(payload.motif)
    if payload.genre == DEMANDE_SUPPRESSION_DOCUMENT:
        # La certification (Hugo, 2026-10-15) : une case du formulaire, exigée ICI aussi —
        # un écran qui l'oublierait, ou un appel sans écran, ne doit pas la contourner.
        if payload.certifie is not True:
            raise HTTPException(422, _MOTIF_CERTIFIER)
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
    attente = _en_attente(conn, album_id=album_id)
    if attente is not None:
        raise _deja_demandee(conn, portee, attente)
    projet_id = projet_d_album(conn, album_id)
    projet = conn.execute("SELECT nom FROM projet WHERE id = ?", (projet_id,)).fetchone()
    cur = conn.execute(
        "INSERT INTO demande (genre, demandeur, motif, certifie_le, projet_id, projet_nom) "
        "VALUES (?, ?, ?, datetime('now'), ?, ?)",
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
        raise _deja_demandee(conn, portee, attente)
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
def _vues_demandes(conn, ids=None, *, detail: bool = False) -> list[dict]:
    """Les demandes telles qu'une route les REND, les plus récentes d'abord. Quatre
    requêtes, aucune par demande.

    `detail` : pour chaque document d'une demande EN ATTENTE, ce que les AUTRES que le
    demandeur y ont fait (`_travail_des_autres`) et qui l'a importé — une requête de plus
    par document en attente. Il nomme des comptes : seules les routes réservées à qui tient
    le fonds le demandent, jamais la réponse rendue à qui dépose."""
    where, params = "", []
    if ids is not None:
        where = f"WHERE id IN ({', '.join('?' * len(ids))})"
        params = list(ids)
    demandes = _rows(conn.execute(f"SELECT * FROM demande {where} ORDER BY id DESC", params))
    if not demandes:
        return []
    marques = ", ".join("?" * len(demandes))
    docs: dict[int, list] = {}
    # `copie` : la copie d'où le geste est parti, si elle vit encore — `album_id`, et non
    # « le plus petit album du document », qui désigne une copie au hasard dès que le
    # document a une sœur (COL-3, tranche 3). Le document recoupé, par ceinture.
    for dd in _rows(conn.execute(
            "SELECT dd.*, (SELECT a.id FROM albums a WHERE a.id = dd.album_id "
            "              AND a.document_id = dd.document_id) AS copie "
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
        if detail and d["en_attente"] and d["genre"] == DEMANDE_SUPPRESSION_DOCUMENT:
            collectifs = _comptes_partages(conn)
            # Derrière un compte partagé, « personne d'autre » et « certifié par » ne
            # désignent pas une personne : le détail le dit, pour que l'écran le dise
            # (relecture croisée). La règle de suppression, elle, n'en change pas.
            d["demandeur_collectif"] = d["demandeur"] in collectifs
            for x in d["documents"]:
                x.update(_travail_des_autres(conn, x["document_id"], x["copie"],
                                             d["demandeur"], collectifs))
    return demandes


def _comptes_partages(conn) -> set:
    """Les logins déclarés COLLECTIFS (AUTH-6) : plusieurs personnes derrière un login."""
    return {r[0] for r in conn.execute("SELECT login FROM utilisateur WHERE nature = ?",
                                       (NATURE_COLLECTIF,))}


def _travail_des_autres(conn, document_id: int, copie, demandeur, collectifs: set) -> dict:
    """Ce que les AUTRES que `demandeur` ont fait sur la COPIE demandée, lu au journal au
    moment de la lecture, par la source même de la règle de suppression
    (`autorisation.sql_actes_sur_album`) — Hugo, 2026-10-15 : l'administrateur doit voir,
    sous la demande, qui d'autre perdrait son travail. Sur cette copie seule (COL-3, tranche
    3, D5) : c'est elle seule qu'accepter détruit, et le travail d'une copie sœur, dans un
    autre projet, n'est pas en jeu. Une copie qui n'existe plus n'a plus de travail à
    perdre (`copie` None).

    Rend `importe_par` (et son nom lisible) — NULL pour un document d'avant le fonds, dont
    l'importateur n'est écrit nulle part —, `creee_par` (et son nom) : qui a créé la COPIE
    demandée, ce que lit la règle — et `travail_des_autres` : une entrée par
    personne, `agent` NULL pour les gestes dont l'auteur n'est pas écrit (un acte sans
    agent, un attribut de case posé avant que le geste s'écrive), avec le nombre de gestes
    de chaque sorte et la date du dernier, le plus récent d'abord. Ce que la règle ne lit
    pas n'y est pas non plus : un travail sur une région supprimée depuis, une passe
    automatique. Ce sont des GESTES écrits au journal, pas ce qui reste sur les planches :
    une annotation posée puis retirée en compte deux.

    Chaque entrée dit si son compte est PARTAGÉ (`collectif`), et `demandeur_collectif`
    celui du demandeur : sous un login partagé, une seule entrée peut être le travail de
    plusieurs personnes."""
    doc = conn.execute("SELECT importe_par FROM document WHERE id = ?",
                       (document_id,)).fetchone()
    par_agent: dict = {}
    for album_id in ([] if copie is None else [copie]):
        for agent, sorte, n, dernier in conn.execute(
                "SELECT agent, sorte, COUNT(*), MAX(quand) FROM ("
                f"{autorisation.sql_actes_sur_album(str(int(album_id)))}"
                # Un geste sans auteur écrit n'est jamais celui du demandeur — même d'une
                # demande sans demandeur, que `IS NOT NULL` seul aurait vidée.
                ") WHERE agent IS NULL OR agent IS NOT ? GROUP BY agent, sorte",
                (demandeur,)):
            e = par_agent.setdefault(agent, {"agent": agent, "gestes": {}, "dernier": None})
            e["gestes"][sorte] = e["gestes"].get(sorte, 0) + n
            if dernier and (e["dernier"] is None or dernier > e["dernier"]):
                e["dernier"] = dernier
    importe_par = doc["importe_par"] if doc else None
    # Qui a créé CETTE copie (COL-3, tranche 3) — c'est elle que lit la règle de suppression
    # directe (`copie.creee_par`), et non l'importateur du document : les deux ne disent la
    # même chose que pour la copie d'origine. None quand on ne le sait pas, ou que la copie
    # n'existe plus.
    ligne = None if copie is None else conn.execute(
        "SELECT creee_par FROM copie WHERE album_id = ?", (copie,)).fetchone()
    creee_par = ligne["creee_par"] if ligne else None
    noms = noms_lisibles(conn, [a for a in (*par_agent, importe_par, creee_par) if a])
    # Le plus récent d'abord ; les gestes sans date (un attribut sans auteur) en dernier.
    autres = sorted(par_agent.values(), key=lambda e: e["dernier"] or "", reverse=True)
    for e in autres:
        e["agent_nom"] = noms.get(e["agent"]) if e["agent"] else None
        e["collectif"] = e["agent"] in collectifs
    return {"importe_par": importe_par,
            "importe_par_nom": noms.get(importe_par) if importe_par else None,
            "creee_par": creee_par,
            "creee_par_nom": noms.get(creee_par) if creee_par else None,
            "demandeur_collectif": demandeur in collectifs,
            "travail_des_autres": autres}


def _vue_demande(conn, demande_id: int) -> dict:
    return _vues_demandes(conn, [demande_id])[0]


@router.get("/api/demandes")
def list_demandes(conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Toutes les demandes, en attente ou répondues — une demande répondue RESTE : c'est
    ce qui permet de dire qu'une même suppression a déjà été refusée. Réservée à qui tient
    le fonds : elle nomme qui demande, et dit pourquoi."""
    _exiger_le_fonds(portee)
    return _vues_demandes(conn, detail=True)


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

    # Un document : la COPIE demandée est détruite, et elle seule (COL-3, tranche 3, D5) —
    # la demande d'un membre d'un projet ne détruit pas, acceptée, la copie d'un autre
    # projet et son travail. Le document part avec sa dernière copie. La destruction clôt
    # d'elle-même toute demande qui visait cette copie — celle-ci comprise ; une copie déjà
    # partie n'a plus rien à détruire : la demande se clôt seule.
    copies = [r[0] for r in conn.execute(
        "SELECT a.id FROM albums a JOIN demande_document dd "
        "ON dd.album_id = a.id AND dd.document_id = a.document_id "
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
    # L'origine se dit par le NOM écrit à l'import (v31, D8), plus par une jointure sur
    # `projet` : un projet d'origine peut être supprimé sous un document vivant, et son
    # identifiant se réattribuait jusqu'à la v31 — la jointure aurait nommé le suivant.
    documents = _rows(conn.execute(
        "SELECT d.id, d.importe_par, d.importe_le, d.projet_origine_id, "
        "       d.projet_origine_nom "
        "FROM document d ORDER BY d.id"))
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
    # La demande se rattache à SA COPIE (COL-3, tranche 3) — `copie` dans la vue d'une
    # demande, la copie d'où le geste est parti et qui vit encore —, et non au document : une
    # demande déposée sur la copie d'un projet ne vise pas la copie sœur d'un autre. Chaque
    # copie dit la sienne ; le document dit la plus ancienne de celles de ses copies, avec la
    # copie qu'elle vise (`album_id`), pour la pastille de sa ligne.
    attente = {}
    for d in sorted(_vues_demandes(conn), key=lambda d: d["id"]):
        if d["en_attente"] and d["genre"] == DEMANDE_SUPPRESSION_DOCUMENT:
            for x in d["documents"]:
                if x["copie"] is not None:
                    attente.setdefault(x["copie"], d)
    noms = noms_lisibles(conn, [d["importe_par"] for d in documents if d["importe_par"]])
    for d in documents:
        d["importe_par_nom"] = noms.get(d["importe_par"])
        d["copies"] = copies.get(d["id"], [])
        d["appele"] = any(a["collections"] for a in d["copies"])
        d["demande"] = None
        for a in d["copies"]:
            dem = attente.get(a["album_id"])
            a["demande"] = None if dem is None else {
                k: dem[k] for k in ("id", "demandeur", "demandeur_nom", "motif", "certifie_le",
                                    "date_creation", "refus_anterieurs")}
            if a["demande"] and (d["demande"] is None or a["demande"]["id"] < d["demande"]["id"]):
                d["demande"] = {**a["demande"], "album_id": a["album_id"]}
    sans = [r[0] for r in conn.execute(
        "SELECT id FROM albums WHERE document_id IS NULL ORDER BY id")]
    return {"documents": documents, "copies_sans_document": sans}
