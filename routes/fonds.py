"""Le fonds — ce que l'instance détient, et les demandes qui en sortent (COL-3, tranche 2).

Tout album est la COPIE DE TRAVAIL d'un document, et le document appartient à l'instance
(v30). Le FONDS n'est pas une table : c'est l'ensemble des documents, dont certains ne sont
plus appelés par aucune collection — une copie qu'on a supprimée de sa dernière collection
y est GARDÉE avec son travail, et un administrateur peut la rendre.

« Supprimer définitivement » a deux réponses, et ce module porte la seconde. Qui a importé
un document, seul à y avoir travaillé, l'efface tout de suite (`DELETE /api/albums/{id}`,
règle `Portee.clause_suppression_directe`). Sinon il DEMANDE : la demande dit qui, quand et
pourquoi, et un administrateur y répond — détruire, ou garder. Aucune messagerie. Le même
mécanisme porte la demande de suppression d'un PROJET par son responsable.

PRENDRE un document (COL-3, tranche 3a) vit ici aussi, parce qu'il puise au fonds et qu'il
se répond par le même mécanisme. Un responsable de projet parcourt les NOTICES du fonds
(`GET /api/fonds/notices` — titre, série, auteur, rien d'autre) et demande des documents
pour une collection de son projet : une ENTRÉE, à laquelle un administrateur répond document
par document. Une collection prend un document que le projet a déjà : une copie vierge
sans rien demander, ou REJOINDRE le travail d'une autre collection — immédiat pour qui tient
toutes les collections de la copie, sinon une demande au propriétaire, qui y répond depuis
la fiche de SA collection. Les deux routes de la prise (`…/collections/{id}/prendre`,
`…/projets/{id}/prendre`, qui délègue à la collection de base) rendent leur résultat
document par document.

Qui voit quoi. Le fonds et les demandes sont à qui TIENT le fonds — une portée totale :
l'administrateur, et le mono-poste (`Portee.peut_tenir_le_fonds`). Les routes qui leur
répondent refusent sur le DROIT de l'appelant AVANT de chercher l'objet : un 403 nommé, le
même que l'identifiant existe ou non — la forme de `comptes_et_groupes`. Trois exceptions
depuis la tranche 3, chacune tranchée par `autorisation.py` : les notices
(`peut_lire_les_notices`), la réponse à un `rejoindre` (`peut_repondre_a`), et les
demandes lues là où vit qui les lit — un responsable dans la fiche de son projet, un
propriétaire dans celle de sa collection (D11). Déposer une
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
from pipeline import nlp
from database import (CRAN_IMAGES, CRANS, DEMANDE_AMORCER, DEMANDE_AMORCER_ENTRE_PROJETS,
                      DEMANDE_ENTREE_DOCUMENTS, DEMANDE_REJOINDRE, DEMANDE_RENDRE,
                      DEMANDE_REPARTIR, niveau_de_travail, rang_du_cran,
                      compter_repartir, copies_rangees_du_projet,
                      est_isole, projets_qui_tiennent, proprietaires_communs,
                      titre_de_notice,
                      DEMANDE_SUPPRESSION_DOCUMENT, DEMANDE_SUPPRESSION_PROJET,
                      GENRES_CONSENTIS, GENRES_DEMANDE, LONGUEUR_MOTIF, NATURE_COLLECTIF, REPONSE_ACCEPTEE,
                      REPONSE_REFUSEE, REPONSES_DEMANDE, collection_de_base, collection_row,
                      compter_le_travail, etat_des_reponses, noms_lisibles, projet_d_album, projet_de_collection,
                      SQL_BACS_EFFACES, ranger_copie, rangement_traverse, sql_album_isole,
                      sql_projet_d_album,
                      un_proprietaire_tient_toute_la_copie)

from socle import (
    DEMANDE, FAIT, REFUSE, DemandeIn, PriseIn, RepartirIn, ReponseIn, _MOTIF_BAC_ISOLE,
    _MOTIF_JEU_SOURCE, _MOTIF_BAC_PROPRIETAIRE, _MOTIF_BAC_SANS_DEMANDE,
    _MOTIF_REPARTIR_PLANCHE, _bac_a_sable_de, _clore_demandes, _cran_de_repartir,
    _deposer, _detruire_album, _en_attente_vers,
    _get_album, _get_collection, _get_planche, _get_projet, _nouvelle_copie, _plan_rejoindre,
    _MOTIF_BAC_SANS_FONDS, _refuser_le_bac_a_sable,
    _repartir,
    _refuser_le_jeu, _retour_en_attente, _rows, _sans_accents, _supprimer_projet, db,
    portee_courante,
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
    if payload.genre in (DEMANDE_ENTREE_DOCUMENTS, DEMANDE_REJOINDRE, DEMANDE_RENDRE,
                         DEMANDE_AMORCER, DEMANDE_AMORCER_ENTRE_PROJETS):
        # COL-3, tranche 3 — ces genres naissent d'un GESTE, qui décide s'il se fait ou se
        # demande : la prise (`…/prendre`, dont la réponse `reprendre` dépose un retour, et
        # `amorcer` — tranche 3b — une demande d'en partir) et « + Ranger ici ». Les déposer ici contournerait ce tri — on demanderait ce
        # qu'on peut faire, ou l'inverse.
        raise HTTPException(422, f"Une demande « {payload.genre} » se dépose en prenant le "
                                 "document : `POST /api/collections/{id}/prendre`, ou en le "
                                 "rangeant dans la collection.")
    motif = _motif(payload.motif)
    if payload.genre == DEMANDE_REPARTIR:
        # E8 — le patron de la suppression d'un document : la certification, exigée ICI.
        if payload.certifie is not True:
            raise HTTPException(422, _MOTIF_CERTIFIER_REPARTIR)
        return _demander_un_repartir(conn, portee, payload.album_id, payload.cran, motif)
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
    # COL-4 (S3) — dans un bac à sable, son propriétaire supprime lui-même (règle de
    # `clause_suppression_directe`, reçue juste au-dessus) ; un invité ne demande rien à
    # un administrateur.
    bac, _ = _bac_a_sable_de(conn, album_id=album_id)
    if bac is not None:
        raise HTTPException(403, _MOTIF_BAC_PROPRIETAIRE)
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


_MOTIF_CERTIFIER_REPARTIR = ("Cochez la certification : repartir de zéro efface ce qui a été "
                             "posé sur les planches au-dessus du cran choisi, et la demande ne "
                             "part pas sans que vous certifiiez que ces données ne sont pas "
                             "importantes.")


def _demander_un_repartir(conn, portee, album_id, cran, motif):
    """Demander à un administrateur de RAMENER une copie à un cran (E8, COL-3, tranche 3b),
    quand on ne peut pas l'effacer soi-même. Le patron de `_demander_un_document` : 404 à qui
    n'écrit pas dans l'album, 409 nommé si l'appelant peut le faire lui-même, si rien n'est
    au-dessus du cran, si la même demande attend déjà sur cette copie (une par copie, quel
    que soit le cran) ; dans un bac à sable, rien ne se demande."""
    if album_id is None:
        raise HTTPException(422, "Quel album ? (`album_id`)")
    cran = _cran_de_repartir(cran)
    a = _get_album(conn, portee, album_id, ecriture=True)
    conflit.verrouiller(conn)
    soi_meme, p_soi_meme = portee.clause_repartir_directe("a.id")
    if conn.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {soi_meme}",
                    (album_id, *p_soi_meme)).fetchone():
        raise HTTPException(409, "Vous pouvez repartir de zéro sur cet album vous-même : il "
                                 "n'y a rien à demander.")
    bac, _ = _bac_a_sable_de(conn, album_id=album_id)
    if bac is not None:
        raise HTTPException(403, _MOTIF_BAC_PROPRIETAIRE)
    if a["document_id"] is None:
        raise HTTPException(409, "Cet album n'est la copie d'aucun document : repartir de zéro "
                                 "ne peut pas se demander. Signalez-le à un administrateur.")
    niveau = niveau_de_travail(conn, album_id)
    if rang_du_cran(cran) >= niveau:
        raise HTTPException(409, f"Rien à retirer au-dessus du cran « {cran} » : cet album "
                                 f"n'y porte que « {CRANS[niveau]} ».")
    if conn.execute("SELECT 1 FROM demande d JOIN demande_document dd "
                    "ON dd.demande_id = d.id WHERE d.genre = ? AND dd.album_id = ? "
                    "AND d.reponse IS NULL", (DEMANDE_REPARTIR, album_id)).fetchone():
        raise HTTPException(409, "Repartir de zéro sur cet album est déjà demandé : un "
                                 "administrateur y répondra.")
    projet_id = projet_d_album(conn, album_id)
    projet = conn.execute("SELECT nom FROM projet WHERE id = ?", (projet_id,)).fetchone()
    cur = conn.execute(
        "INSERT INTO demande (genre, demandeur, motif, certifie_le, projet_id, projet_nom, "
        "cran) VALUES (?, ?, ?, datetime('now'), ?, ?, ?)",
        (DEMANDE_REPARTIR, portee.utilisateur, motif, projet_id,
         projet[0] if projet else None, cran))
    conn.execute("INSERT INTO demande_document (demande_id, document_id, album_id, titre) "
                 "VALUES (?, ?, ?, ?)", (cur.lastrowid, a["document_id"], album_id,
                                         a["titre"]))
    journal.journaliser(conn, "creation", "demande", cur.lastrowid,
                        apres={"genre": DEMANDE_REPARTIR, "document_id": a["document_id"],
                               "album_id": album_id, "cran": cran})
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
    if p["bac_a_sable_de"] is not None:
        # COL-4 (S3) — un bac à sable ne se supprime pas, et rien ne s'y demande.
        raise HTTPException(409, "C'est un bac à sable : il ne se supprime pas, il se remet à "
                                 "neuf, et s'efface avec les autres chaque lundi.")
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
        cle = (d["genre"], d["projet_id"] if d["genre"] == DEMANDE_SUPPRESSION_PROJET
               else d["document_id"])
        refus.setdefault(cle, set()).add(d["id"])
    noms = noms_lisibles(conn, [x for d in demandes
                                for x in (d["demandeur"], d["repondu_par"]) if x])
    for d in demandes:
        d["demandeur_nom"] = noms.get(d["demandeur"])
        d["repondu_par_nom"] = noms.get(d["repondu_par"])
        d["en_attente"] = d["reponse"] is None
        # `copie_id` (COL-3, tranche 3) : la copie où une entrée acceptée a fait entrer le
        # document, ou la copie rangée par un `rejoindre` accepté.
        d["documents"] = [{"document_id": x["document_id"], "album_id": x["album_id"],
                           "titre": x["titre"], "reponse": x["reponse"],
                           "copie": x["copie"], "copie_id": x["copie_id"]}
                          for x in docs.get(d["id"], [])]
        if d["genre"] == DEMANDE_SUPPRESSION_PROJET:
            cles = [(d["genre"], d["projet_id"])]
        else:
            cles = [(d["genre"], x["document_id"]) for x in d["documents"]]
        d["refus_anterieurs"] = len({i for c in cles for i in refus.get(c, ())
                                     if i < d["id"]})
        if detail and d["en_attente"] and d["genre"] in (DEMANDE_SUPPRESSION_DOCUMENT,
                                                         DEMANDE_REPARTIR):
            collectifs = _comptes_partages(conn)
            # Derrière un compte partagé, « personne d'autre » et « certifié par » ne
            # désignent pas une personne : le détail le dit, pour que l'écran le dise
            # (relecture croisée). La règle de suppression, elle, n'en change pas.
            d["demandeur_collectif"] = d["demandeur"] in collectifs
            for x in d["documents"]:
                x.update(_travail_des_autres(conn, x["document_id"], x["copie"],
                                             d["demandeur"], collectifs))
        if detail and d["en_attente"] and d["genre"] == DEMANDE_RENDRE:
            # De quelle collection la copie était SORTIE, si le journal le sait (la fin de son
            # dernier emploi) — pour qu'un administrateur ne rende pas dans une base ouverte,
            # sans le savoir, un travail fait dans une collection fermée (relecture croisée de
            # l'écran de la 3a). Le nom écrit ce jour-là ; `None` quand rien n'est écrit.
            d["sortie_de"] = None
            for x in d["documents"]:
                r = conn.execute(
                    "SELECT json_extract(avant, '$.collection') FROM evenement "
                    "WHERE cible_table = 'collection_album' AND type = 'delien' "
                    "AND json_extract(avant, '$.album_id') = ? ORDER BY id DESC LIMIT 1",
                    (x["album_id"],)).fetchone()
                if r and r[0]:
                    d["sortie_de"] = r[0]
        if detail and d["en_attente"] and d["genre"] == DEMANDE_AMORCER_ENTRE_PROJETS:
            # E7 — à qui la demande s'adresse AUJOURD'HUI : les projets qui tiennent ce
            # travail, et leurs copies. Pour qui tient le fonds seulement (`detail`) : c'est
            # précisément ce que le demandeur ne doit pas apprendre. Une liste vide dit que
            # l'administrateur est seul à pouvoir répondre.
            # Écran de la 3b (Hugo, 2026-10-25) : « attend … » — les responsables de chaque
            # projet source, qu'il remplace en répondant —, et l'aperçu de chaque copie.
            projets = {r[0]: r[1] for r in conn.execute("SELECT id, nom FROM projet")}
            d["sources"] = []
            for x in d["documents"]:
                for pid, copies in projets_qui_tiennent(
                        conn, x["document_id"], d["cran"], sauf=d["projet_id"]).items():
                    d["sources"] += [{**c, "projet_id": pid, "projet_nom": projets.get(pid),
                                      "responsables": _responsables(conn, pid),
                                      "apercu": _apercu(conn, c["album_id"], d)}
                                     for c in copies]
        if detail and d["en_attente"] and d["genre"] == DEMANDE_AMORCER:
            x = d["documents"][0] if d["documents"] else None
            d["apercu"] = (_apercu(conn, x["copie"], d) if x and x["copie"] else None)
        if detail and d["en_attente"] and d["genre"] in GENRES_CONSENTIS:
            # Écran de la 3b (Hugo, 2026-10-25) — « attend … » : qui tient AUJOURD'HUI toutes
            # les collections de la copie visée, à qui la demande s'adresse et que
            # l'administrateur remplace en répondant, comme pour un rejoindre. Une liste vide
            # dit que personne ne les tient toutes : c'est à lui.
            x = d["documents"][0] if d["documents"] else None
            d["attend"] = _attend(conn, x["copie"]) if x and x["copie"] else []
    return demandes


def _attend(conn, copie: int) -> list[str]:
    """Les principaux qui tiennent toutes les collections de `copie`, NOMMÉS — pour
    l'administrateur seul (« attend … ») : le nom lisible d'un login, le login sinon ; un
    groupe, « groupe <nom> »."""
    communs = sorted(proprietaires_communs(conn, copie),
                     key=lambda x: (x[0] != autorisation.UTILISATEUR, x[1]))
    noms = noms_lisibles(conn, [p for g, p in communs if g == autorisation.UTILISATEUR])
    return [noms.get(p) or p if g == autorisation.UTILISATEUR else f"groupe {p}"
            for g, p in communs]


def _apercu(conn, source: int, d: dict):
    """Ce qu'une demande d'en partir copierait de `source` vers sa collection d'arrivée, en
    NOMBRES (`database.compter_le_travail`) — l'aperçu que l'écran de la 3b montre à qui
    répond. None quand la collection d'arrivée n'existe plus, ou le cran est illisible."""
    if (d.get("cran") not in CRANS or d["cran"] == CRAN_IMAGES
            or d.get("collection_id") is None
            or collection_row(conn, d["collection_id"]) is None):
        return None
    return compter_le_travail(conn, source, d["cran"], d["collection_id"])


def _responsables(conn, projet_id: int) -> list[dict]:
    """Les responsables d'un projet, nommés — pour l'administrateur seul (« attend … »)."""
    lignes = _rows(conn.execute(
        "SELECT genre, principal FROM projet_acces WHERE projet_id = ? AND role = ? "
        "ORDER BY genre, principal", (projet_id, autorisation.RESPONSABLE)))
    noms = noms_lisibles(conn, [x["principal"] for x in lignes
                                if x["genre"] == autorisation.UTILISATEUR])
    for x in lignes:
        x["nom"] = noms.get(x["principal"])
    return lignes


def _comptes_partages(conn) -> set:
    """Les logins déclarés COLLECTIFS (AUTH-6) : plusieurs personnes derrière un login."""
    return {r[0] for r in conn.execute("SELECT login FROM utilisateur WHERE nature = ?",
                                       (NATURE_COLLECTIF,))}


def _travail_des_autres(conn, document_id: int, copie, demandeur, collectifs: set, *,
                        recopie_a_part: bool = False) -> dict:
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
    plusieurs personnes.

    `recopie_a_part` (tranche 3b) : le travail RECOPIÉ — fait sur une région source avant
    la copie, la sixième source de la règle — ne s'y nomme pas, et se compte à part, sans
    auteur (`travail_recopie` : les gestes par sorte et la date du dernier ; None s'il n'y
    en a pas). Pour un écran qui ne tient pas le fonds : ses auteurs ont travaillé dans une
    autre copie, peut-être un autre projet, et ce travail ne part pas avec cette copie."""
    doc = conn.execute("SELECT importe_par FROM document WHERE id = ?",
                       (document_id,)).fetchone()
    par_agent: dict = {}
    recopie: dict | None = None
    for album_id in ([] if copie is None else [copie]):
        for agent, sorte, origine, n, dernier in conn.execute(
                "SELECT agent, sorte, recopie, COUNT(*), MAX(quand) FROM ("
                f"{autorisation.sql_actes_sur_album(str(int(album_id)))}"
                # Un geste sans auteur écrit n'est jamais celui du demandeur — même d'une
                # demande sans demandeur, que `IS NOT NULL` seul aurait vidée.
                ") WHERE agent IS NULL OR agent IS NOT ? GROUP BY agent, sorte, recopie",
                (demandeur,)):
            if recopie_a_part and origine:
                recopie = recopie or {"gestes": {}, "dernier": None}
                recopie["gestes"][sorte] = recopie["gestes"].get(sorte, 0) + n
                if dernier and (recopie["dernier"] is None or dernier > recopie["dernier"]):
                    recopie["dernier"] = dernier
                continue
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
    rendu = {"importe_par": importe_par,
             "importe_par_nom": noms.get(importe_par) if importe_par else None,
             "creee_par": creee_par,
             "creee_par_nom": noms.get(creee_par) if creee_par else None,
             "demandeur_collectif": demandeur in collectifs,
             "travail_des_autres": autres}
    if recopie_a_part:
        rendu["travail_recopie"] = recopie
    return rendu


_MOTIF_TRAVAIL = ("Ce que d'autres ont fait sur cet album se lit par qui peut l'effacer sans "
                  "rien demander : son propriétaire, le responsable de son projet, ou qui "
                  "l'a créé.")


@router.post("/api/albums/{album_id}/repartir")
def repartir_album(album_id: int, payload: RepartirIn, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """REPARTIR DE ZÉRO sur un album : le ramener au `cran` dit, en gardant ses images (E8,
    COL-3, tranche 3b) — `images`, `decoupage`, `transcription` ou `grammaire`.

    La règle de l'effacement (`Portee.clause_repartir_directe`, Hugo, 2026-10-21) : son
    créateur s'il est seul à y avoir travaillé, le propriétaire de toutes ses collections,
    le responsable de son projet — la dernière copie d'un document comprise : repartir garde
    les images, rien ne sort du fonds commun (le pilotage, 2026-10-25).
    404 à qui n'y écrit pas ; 403 nommé à qui y écrit sans pouvoir l'effacer — il le
    DEMANDE (`POST /api/demandes`, genre `repartir`, motif et certification) ; 409 nommé si
    rien n'est au-dessus du cran. UN acte au journal, non annulable : l'écran doit le dire
    (« ne s'annule pas »), et Ctrl+Z ne remonte pas au-delà."""
    cran = _cran_de_repartir(payload.cran)
    _get_album(conn, portee, album_id, ecriture=True)
    if rang_du_cran(cran) >= rang_du_cran(CRANS[1]):
        nlp.ensure_loaded()                 # le texte qui reste se réindexe, hors transaction
    rendu = _repartir(conn, portee, album_id, cran)
    conn.commit()
    return rendu


@router.post("/api/planches/{planche_id}/repartir")
def repartir_planche(planche_id: int, payload: RepartirIn,
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """REPARTIR DE ZÉRO sur UNE planche (Hugo, 2026-10-21, demandé par des testeurs) : les
    mêmes crans et la même règle que l'album — celle de son album. Une planche n'a pas de
    demande à elle (la décision B4, tenue pour elle aussi) : à qui y écrit sans pouvoir
    l'effacer, un 403 qui renvoie à un administrateur. Un acte, non annulable."""
    cran = _cran_de_repartir(payload.cran)
    p = _get_planche(conn, portee, planche_id, ecriture=True)
    if rang_du_cran(cran) >= rang_du_cran(CRANS[1]):
        nlp.ensure_loaded()
    rendu = _repartir(conn, portee, p["album_id"], cran, planche_id=planche_id,
                      motif_refus=_MOTIF_REPARTIR_PLANCHE)
    conn.commit()
    return rendu


@router.get("/api/albums/{album_id}/repartir/apercu")
def apercu_de_repartir(album_id: int, cran: str, planche: int | None = None,
                       conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """Ce que « repartir de zéro » vers `cran` retirerait de cet album — ou de sa planche
    `planche` —, sans rien écrire : le panneau de l'écran de la 3b (Hugo, 2026-10-25) —
    « Part », en nombres, validations comprises (`database.compter_repartir`, égal aux
    comptes de l'acte) ; `niveau`, le plus haut travail que la copie porte, pour éteindre
    les crans au-dessus ; `direct`, si l'appelant le fait lui-même ou le demande
    (`Portee.clause_repartir_directe`). Pour qui ÉCRIT dans l'album : 404 sinon, et sur
    une planche d'un autre album ; 422 sur un cran hors de la liste."""
    cran = _cran_de_repartir(cran)
    _get_album(conn, portee, album_id, ecriture=True)
    if planche is not None:
        p = _get_planche(conn, portee, planche, ecriture=True)
        if p["album_id"] != album_id:
            raise HTTPException(404, f"Planche {planche} introuvable")
    ou, params = portee.clause_repartir_directe("a.id")
    direct = conn.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ou}",
                          (album_id, *params)).fetchone() is not None
    niveau = niveau_de_travail(conn, album_id, planche)
    return {"album_id": album_id, "planche_id": planche, "cran": cran,
            "niveau": CRANS[niveau], "rien_a_retirer": rang_du_cran(cran) >= niveau,
            "comptes": compter_repartir(conn, album_id, cran, planche_id=planche),
            "direct": direct}


@router.get("/api/albums/{album_id}/retirer-du-projet/apercu")
def apercu_du_retrait(album_id: int, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Ce que « Retirer du projet » ferait, AVANT de le faire — le panneau de l'écran de la
    3b (Hugo, 2026-10-25) : les collections quittées et les PROPRIÉTAIRES qui le verront
    disparaître (ceux de `collection_acces`, et pour la base, les responsables du projet),
    et qui y a travaillé (« rien n'est effacé ») — la mesure de « qui perd quoi », le travail
    recopié d'une autre copie compté sans nom. Pour qui peut retirer : 404 à qui ne lit pas
    l'album, 403 nommé à qui le lit sans gérer son projet, 409 dans un bac à sable et sur
    le jeu."""
    a = _get_album(conn, portee, album_id)
    _refuser_le_jeu(conn, album_id=album_id)
    _refuser_le_bac_a_sable(conn, _MOTIF_BAC_SANS_FONDS, album_id=album_id)
    projet_id = projet_d_album(conn, album_id)
    if projet_id is None or not portee.peut_gerer_projet(projet_id):
        raise HTTPException(403, "Retirer un album de son projet revient au responsable du "
                                 "projet.")
    collections = _rows(conn.execute(
        "SELECT c.id, c.nom FROM collection_album ca JOIN collection c "
        "ON c.id = ca.collection_id WHERE ca.album_id = ? ORDER BY c.id", (album_id,)))
    logins = set()
    for c in collections:
        c["proprietaires"] = autorisation.proprietaires_de(conn, c["id"])
        logins |= {x["principal"] for x in c["proprietaires"]
                   if x["genre"] == autorisation.UTILISATEUR}
    noms = noms_lisibles(conn, sorted(logins))
    for c in collections:
        for x in c["proprietaires"]:
            x["nom"] = noms.get(x["principal"]) if x["genre"] == autorisation.UTILISATEUR \
                else None
    vue = _travail_des_autres(conn, a["document_id"], album_id, portee.utilisateur,
                              _comptes_partages(conn), recopie_a_part=not portee.tout)
    return {"album_id": album_id, "projet_id": projet_id, "collections": collections,
            "travail_des_autres": vue["travail_des_autres"],
            "travail_recopie": vue.get("travail_recopie")}


@router.get("/api/albums/{album_id}/travail-des-autres")
def travail_des_autres_avant_d_effacer(album_id: int, conn: sqlite3.Connection = Depends(db),
                                       portee: autorisation.Portee = Depends(portee_courante)):
    """Ce que d'AUTRES ont fait sur cet album — qui, combien de gestes de chaque sorte, la
    date du dernier —, pour qui va l'effacer (COL-3, tranche 3b ; Hugo, 2026-10-21 : la
    protection du travail des membres passe de la permission à la VISIBILITÉ, l'écran dit
    qui perd quoi AVANT d'effacer). La mesure que l'administrateur lit déjà sous une
    demande, lue par la même source que la règle (`autorisation.sql_actes_sur_album`) : ce
    que l'écran montre est ce que la règle a lu.

    Bornée à qui PEUT effacer cet album sans rien demander — le supprimer ou en repartir
    de zéro, la plus large des deux (`Portee.clause_repartir_directe`) : son propriétaire,
    le responsable de son projet, qui l'a créé, une portée totale. 404 à qui n'y écrit pas
    (l'accesseur gardé), 403 nommé à qui y écrit sans pouvoir l'effacer. Le travail RECOPIÉ d'une autre copie se compte à
    part, sans nom (`travail_recopie`) : il ne part pas avec celle-ci, et ses auteurs
    peuvent être d'un autre projet. Ce sont des GESTES, défaits compris, pas ce qui reste
    sur les planches."""
    a = _get_album(conn, portee, album_id, ecriture=True)
    ou, params = portee.clause_repartir_directe("a.id")
    if conn.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ou}",
                    (album_id, *params)).fetchone() is None:
        raise HTTPException(403, _MOTIF_TRAVAIL)
    vue = _travail_des_autres(conn, a["document_id"], album_id, portee.utilisateur,
                              _comptes_partages(conn), recopie_a_part=not portee.tout)
    vue.pop("demandeur_collectif", None)
    if not portee.tout:
        # Qui a importé le DOCUMENT peut l'avoir fait dans un autre projet, dont la copie
        # d'origine vit ailleurs : seul `creee_par`, qui a créé CETTE copie, se lit ici.
        vue.pop("importe_par", None)
        vue.pop("importe_par_nom", None)
    return {"album_id": album_id, **vue}


def _vue_demande(conn, demande_id: int) -> dict:
    return _vues_demandes(conn, [demande_id])[0]


@router.get("/api/demandes")
def list_demandes(conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Toutes les demandes, en attente ou répondues — une demande répondue RESTE : c'est
    ce qui permet de dire qu'une même suppression a déjà été refusée. Réservée à qui tient
    le fonds : elle nomme qui demande, et dit pourquoi.

    COL-4 (S3) — sans celles des BACS À SABLE, pour personne : l'administrateur n'y lit
    rien (Hugo, 2026-10-24). Aucune n'y naît plus (`socle._deposer`) ; le filtre reste, et
    il ne dépend pas de l'existence du projet : un bac à sable EFFACÉ n'est plus une ligne
    de `projet`, mais son effacement est écrit au journal, et ses identifiants ne reviennent
    pas (`_projets_isoles_ou_effaces`)."""
    _exiger_le_fonds(portee)
    vues = _vues_demandes(conn, detail=True)
    isoles = _projets_isoles_ou_effaces(conn)
    return [d for d in vues if d["projet_id"] not in isoles]


@router.post("/api/demandes/{demande_id}/reponse")
def repondre_demande(demande_id: int, payload: ReponseIn,
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Répondre à une demande : l'accepter ou la refuser. Une demande close ne reçoit pas
    d'autre réponse : 409.

    QUI répond (`Portee.peut_repondre_a`) : qui tient le fonds, pour une suppression et une
    entrée de documents ; pour un `rejoindre`, qui administre chacune des collections où vit
    la copie visée — c'est la première demande à laquelle répond quelqu'un qui ne tient pas
    le fonds. Le droit d'abord, l'objet ensuite : 403 nommé, avant toute lecture, à qui
    n'administre rien — il ne peut répondre à aucune demande, qu'elle existe ou non. À qui
    administre une collection sans tenir le fonds, 404 sur ce qu'il ne peut pas connaître :
    une demande qui n'existe pas, une demande d'un genre réservé, un `rejoindre` sur une
    copie qu'il ne lit pas ; 403 nommé sur un `rejoindre` qu'il lit sans pouvoir y répondre.

    Ce qu'accepter fait, par genre. Une suppression de document : la COPIE demandée est
    détruite, elle seule (D5). Une suppression de projet : les mêmes refus que
    `DELETE /api/projets/{id}`, qui se nomment. Une entrée de documents : chaque document
    accepté entre dans la collection demandée, en copie VIERGE — ou, pour une copie gardée
    au fonds qu'on reprend, cette copie elle-même —, et la ligne dit laquelle (`copie_id`).
    Un `rejoindre` : la copie est rangée dans la collection d'arrivée. Un retour
    (`DEMANDE_RENDRE`) : la copie gardée au fonds revient, avec son travail, dans la
    collection que le responsable a nommée ; refusé, elle reste au fonds.

    DOCUMENT PAR DOCUMENT pour une entrée (D9) : `document_id` désigne la ligne à laquelle
    on répond ; sans lui, la réponse vaut pour toutes les lignes qui attendent — « tout
    accepter », « tout refuser ». La demande se clôt quand chaque ligne a sa réponse, et son
    état vaut alors `acceptee`, `refusee` ou `partielle`. Refuser n'efface rien : la demande
    reste, close, et peut être redéposée.

    Une demande d'en partir ENTRE DEUX PROJETS (E7, tranche 3b) se répond par le
    RESPONSABLE d'un projet qui tient aujourd'hui le travail demandé — 404 à tout autre qui
    ne tient pas le fonds, le même qu'elle existe ou non —, et par l'administrateur. Pour
    l'accepter, qui répond nomme SA copie source (`album_id`) : une copie rangée de son
    projet, qui tient ce travail ; l'administrateur, toute copie hors d'un projet isolé. La
    copie neuve est au DEMANDEUR. Refusée par l'un, elle est close pour tous."""
    if not (portee.tout or portee.admin or portee.propriete or portee.projets_geres):
        raise HTTPException(403, _MOTIF_FONDS)
    if payload.reponse not in REPONSES_DEMANDE:
        raise HTTPException(422, f"Réponse inconnue : {payload.reponse} "
                                 f"({' | '.join(REPONSES_DEMANDE)}).")
    # Accepter une demande d'en partir recopie l'index de ses régions, et peut en recalculer
    # les lemmes : spaCy se charge HORS de la transaction d'écriture (CLAUDE.md
    # § Concurrence). Lu avant le verrou, le genre ne décide rien d'autre.
    if payload.reponse == REPONSE_ACCEPTEE and conn.execute(
            "SELECT 1 FROM demande WHERE id = ? AND genre IN (?, ?)",
            (demande_id, DEMANDE_AMORCER, DEMANDE_AMORCER_ENTRE_PROJETS)).fetchone():
        nlp.ensure_loaded()
    # La demande se lit SOUS LE VERROU d'écriture, et la réponse suit dans la même
    # transaction : deux administrateurs qui répondent ensemble ne passent plus tous deux
    # le 409 « déjà répondue » (relecture croisée de la tranche 2).
    conflit.verrouiller(conn)
    d = conn.execute("SELECT * FROM demande WHERE id = ?", (demande_id,)).fetchone()
    introuvable = HTTPException(404, f"Demande {demande_id} introuvable")
    if d is None:
        raise introuvable
    copie = collections_de_la_copie = None
    sources: dict = {}
    if d["genre"] in GENRES_CONSENTIS:
        ligne = conn.execute("SELECT album_id FROM demande_document WHERE demande_id = ? "
                             "ORDER BY document_id LIMIT 1", (demande_id,)).fetchone()
        copie = ligne["album_id"] if ligne else None
        collections_de_la_copie = [r[0] for r in conn.execute(
            "SELECT collection_id FROM collection_album WHERE album_id = ? "
            "ORDER BY collection_id", (copie,))]
    elif d["genre"] == DEMANDE_AMORCER_ENTRE_PROJETS:
        # E7 — à qui elle s'adresse, relu ICI, sous le verrou : le travail tel qu'il est.
        ligne = conn.execute("SELECT document_id FROM demande_document WHERE demande_id = ? "
                             "ORDER BY document_id LIMIT 1", (demande_id,)).fetchone()
        if ligne is not None and d["cran"] in CRANS:
            sources = projets_qui_tiennent(conn, ligne["document_id"], d["cran"],
                                           sauf=d["projet_id"])
    if not portee.tout:
        # Qui n'a pas le fonds ne connaît que les demandes consenties (`rejoindre`, en
        # partir) sur une copie qu'il LIT — et, entre deux projets, celles qui s'adressent à
        # un projet qu'il GÈRE.
        if d["genre"] == DEMANDE_AMORCER_ENTRE_PROJETS:
            if not any(portee.peut_gerer_projet(p) for p in sources):
                raise introuvable
        elif (d["genre"] not in GENRES_CONSENTIS
                or not _lues(conn, portee, [copie] if copie else [])):
            raise introuvable
    if not portee.peut_repondre_a({"genre": d["genre"],
                                   "collections": collections_de_la_copie,
                                   "projets": list(sources)}):
        geste = "Rejoindre" if d["genre"] == DEMANDE_REJOINDRE else "En partir de"
        raise HTTPException(403, f"{geste} ce travail se consent par le propriétaire de "
                                 "chacune des collections où il vit : vous ne les tenez pas "
                                 "toutes. Un administrateur peut y répondre.")
    if d["reponse"] is not None:
        raise HTTPException(409, "Cette demande a déjà reçu sa réponse.")
    if payload.document_id is not None and d["genre"] != DEMANDE_ENTREE_DOCUMENTS:
        raise HTTPException(422, "Seule une entrée de documents se répond document par "
                                 "document : ne précisez pas `document_id`.")
    if payload.album_id is not None and d["genre"] != DEMANDE_AMORCER_ENTRE_PROJETS:
        raise HTTPException(422, "Seule une demande d'en partir entre deux projets se répond "
                                 "en nommant une copie : ne précisez pas `album_id`.")

    if d["genre"] == DEMANDE_ENTREE_DOCUMENTS:
        _repondre_a_une_entree(conn, portee, dict(d), payload)
        conn.commit()
        return _vue_demande(conn, demande_id)

    if payload.reponse == REPONSE_REFUSEE:
        _clore_demandes(conn, portee, [demande_id], REPONSE_REFUSEE)
        conn.commit()
        return _vue_demande(conn, demande_id)

    if d["genre"] == DEMANDE_REJOINDRE:
        _accepter_un_rejoindre(conn, portee, dict(d), copie)
        conn.commit()
        return _vue_demande(conn, demande_id)

    if d["genre"] == DEMANDE_AMORCER:
        _accepter_un_amorcer(conn, portee, dict(d), copie)
        conn.commit()
        return _vue_demande(conn, demande_id)

    if d["genre"] == DEMANDE_AMORCER_ENTRE_PROJETS:
        _accepter_un_amorcer_entre_projets(conn, portee, dict(d), payload.album_id, sources)
        conn.commit()
        return _vue_demande(conn, demande_id)

    if d["genre"] == DEMANDE_RENDRE:
        _accepter_un_retour(conn, portee, dict(d))
        conn.commit()
        return _vue_demande(conn, demande_id)

    if d["genre"] == DEMANDE_REPARTIR:
        _accepter_un_repartir(conn, portee, dict(d))
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


def _repondre_a_une_entree(conn, portee, d: dict, payload) -> None:
    """Répond à une entrée de documents — une ligne (`payload.document_id`), ou toutes celles
    qui attendent. Ne commite pas. Un document accepté entre dans la collection demandée ;
    rien n'est fait pour un refusé. La demande se clôt à la DERNIÈRE ligne répondue, pas à
    la première (D9)."""
    attente = _rows(conn.execute(
        "SELECT document_id, album_id, titre FROM demande_document "
        "WHERE demande_id = ? AND reponse IS NULL ORDER BY document_id", (d["id"],)))
    if payload.document_id is not None:
        attente = [x for x in attente if x["document_id"] == payload.document_id]
        if not attente:
            if conn.execute("SELECT 1 FROM demande_document WHERE demande_id = ? "
                            "AND document_id = ?", (d["id"], payload.document_id)).fetchone():
                raise HTTPException(409, "Ce document a déjà reçu sa réponse.")
            raise HTTPException(404, f"Le document {payload.document_id} n'est pas dans "
                                     "cette demande.")
    reponses = {}
    for x in attente:
        copie_id = None
        if payload.reponse == REPONSE_ACCEPTEE:
            copie_id = _faire_entrer(conn, portee, d, x)
        conn.execute("UPDATE demande_document SET reponse = ?, copie_id = ? "
                     "WHERE demande_id = ? AND document_id = ?",
                     (payload.reponse, copie_id, d["id"], x["document_id"]))
        reponses[x["document_id"]] = payload.reponse
    etat = etat_des_reponses(r[0] for r in conn.execute(
        "SELECT reponse FROM demande_document WHERE demande_id = ?", (d["id"],)))
    if etat is not None:
        conn.execute("UPDATE demande SET reponse = ?, repondu_par = ?, "
                     "date_reponse = datetime('now') WHERE id = ? AND reponse IS NULL",
                     (etat, portee.utilisateur, d["id"]))
    journal.journaliser(conn, "modification", "demande", d["id"],
                        apres={"documents": reponses, "reponse": etat})


def _faire_entrer(conn, portee, d: dict, ligne: dict) -> int:
    """Le document d'une ligne acceptée entre dans la collection demandée, et rend la copie
    qui l'y porte. Les refus se NOMMENT (409), et la demande reste en attente : qui répond
    sait ce qui manque, et peut refuser la ligne."""
    collection_id = d["collection_id"]
    if collection_id is None or collection_row(conn, collection_id) is None:
        raise HTTPException(409, "La collection demandée n'existe plus : refusez cette "
                                 "demande.")
    if ligne["album_id"] is not None:
        # Une copie gardée au fonds qu'on REPREND : elle doit l'être encore, et rester dans
        # le projet de la collection — elle n'en change pas.
        gardee = conn.execute(
            "SELECT 1 FROM albums a WHERE a.id = ? AND NOT EXISTS "
            "(SELECT 1 FROM collection_album ca WHERE ca.album_id = a.id)",
            (ligne["album_id"],)).fetchone()
        if gardee is None or rangement_traverse(conn, ligne["album_id"], collection_id):
            raise HTTPException(409, f"« {ligne['titre']} » n'est plus gardé au fonds pour "
                                     "ce projet : refusez cette ligne.")
        ranger_copie(conn, ligne["album_id"], collection_id)
        return ligne["album_id"]
    source = conn.execute("SELECT MIN(id) FROM albums WHERE document_id = ?",
                          (ligne["document_id"],)).fetchone()[0]
    if source is None:
        raise HTTPException(409, f"« {ligne['titre']} » n'est plus au fonds — détruit depuis "
                                 "la demande : refusez cette ligne.")
    return _nouvelle_copie(conn, portee, ligne["document_id"], collection_id, source,
                           pour=d["demandeur"])


def _accepter_un_rejoindre(conn, portee, d: dict, copie) -> None:
    """La copie visée est rangée dans la collection d'arrivée. Ses refus se nomment, et la
    demande reste en attente : la copie détruite depuis, la collection supprimée, un
    rangement qui traverserait les projets (une copie qui, entre-temps, est passée au fonds
    d'un autre projet ne le peut pas)."""
    collection_id = d["collection_id"]
    if copie is None or conn.execute("SELECT 1 FROM albums WHERE id = ?",
                                     (copie,)).fetchone() is None:
        raise HTTPException(409, "Cette copie n'existe plus : refusez cette demande.")
    if collection_id is None or collection_row(conn, collection_id) is None:
        raise HTTPException(409, "La collection demandée n'existe plus : refusez cette "
                                 "demande.")
    if rangement_traverse(conn, copie, collection_id):
        raise HTTPException(409, "Cette copie vit dans un autre projet que la collection "
                                 "demandée : le rangement ne traverse pas les projets.")
    ranger_copie(conn, copie, collection_id)
    conn.execute("UPDATE demande_document SET copie_id = ? WHERE demande_id = ?",
                 (copie, d["id"]))
    _clore_demandes(conn, portee, [d["id"]], REPONSE_ACCEPTEE)


def _accepter_un_amorcer(conn, portee, d: dict, source) -> None:
    """Une demande d'EN PARTIR acceptée (tranche 3b, E4) : la copie neuve naît dans la
    collection d'arrivée, amorcée avec le travail de la copie SOURCE jusqu'au cran demandé,
    et elle est au DEMANDEUR (`copie.creee_par`, comme une entrée acceptée) — c'est lui qui
    a voulu en partir. Le travail copié est celui de la source AU MOMENT de l'acceptation :
    ce qui s'y est fait depuis la demande suit, et c'est ce que le propriétaire a sous les
    yeux quand il consent. Ses refus se nomment (409), et la demande reste en attente : la
    source détruite ou gardée au fonds depuis (la destruction et la sortie au fonds closent
    d'ailleurs la demande), la collection supprimée, une source passée dans un autre
    projet."""
    collection_id = d["collection_id"]
    if source is None or conn.execute("SELECT 1 FROM albums WHERE id = ?",
                                      (source,)).fetchone() is None:
        raise HTTPException(409, "Le travail d'où partir n'existe plus : refusez cette "
                                 "demande.")
    if collection_id is None or collection_row(conn, collection_id) is None:
        raise HTTPException(409, "La collection demandée n'existe plus : refusez cette "
                                 "demande.")
    if conn.execute("SELECT 1 FROM collection_album WHERE album_id = ?",
                    (source,)).fetchone() is None:
        raise HTTPException(409, "Le travail d'où partir est gardé au fonds : refusez cette "
                                 "demande.")
    if projet_d_album(conn, source) != projet_de_collection(conn, collection_id):
        raise HTTPException(409, "Le travail d'où partir vit dans un autre projet que la "
                                 "collection demandée : refusez cette demande.")
    if d["cran"] not in CRANS or d["cran"] == CRAN_IMAGES:
        raise HTTPException(409, f"Cran illisible sur cette demande ({d['cran']}) : "
                                 "refusez-la.")
    ligne = conn.execute("SELECT document_id FROM demande_document WHERE demande_id = ? "
                         "ORDER BY document_id LIMIT 1", (d["id"],)).fetchone()
    nouvelle = _nouvelle_copie(conn, portee, ligne["document_id"], collection_id, source,
                               pour=d["demandeur"], cran=d["cran"])
    conn.execute("UPDATE demande_document SET copie_id = ? WHERE demande_id = ?",
                 (nouvelle, d["id"]))
    _clore_demandes(conn, portee, [d["id"]], REPONSE_ACCEPTEE)


def _accepter_un_amorcer_entre_projets(conn, portee, d: dict, source, sources: dict) -> None:
    """Une demande d'en partir ENTRE DEUX PROJETS acceptée (E7, tranche 3b) : qui répond a
    choisi SA copie source (`source`), et la copie neuve naît dans la collection d'arrivée,
    amorcée jusqu'au cran demandé, au DEMANDEUR (`copie.creee_par`, comme une entrée
    acceptée, D11). Ne commite pas.

    La source, pour un responsable : une copie RANGÉE d'un projet qu'il gère, qui tient le
    travail (`sources`), et qu'il LIT — le même 404 pour toute autre, qu'elle existe ou non :
    il n'apprend rien d'une copie qu'il ne tient pas. Gérer un projet n'ouvre aucune de ses
    collections (D10, hors sa base) : sans la lecture, un responsable qui ne lit pas la
    collection d'une copie en ferait passer le travail dans un autre projet — dont il peut
    être aussi responsable, et le lire alors par la copie neuve (relecture croisée de la 3b,
    constat 2 ; la règle de `_source_d_amorce` dans un même projet, E4). Pour la portée totale : toute copie du document hors
    d'un projet isolé et hors du projet d'arrivée — c'est le recours quand aucun projet ne le
    tient. Ses autres refus se nomment (409), et la demande reste en attente : la collection
    supprimée, passée dans un autre projet, un cran illisible."""
    if source is None:
        raise HTTPException(422, "Accepter : de quelle copie le projet d'arrivée part-il ? "
                                 "(`album_id`, une copie de votre projet)")
    ligne = conn.execute("SELECT document_id FROM demande_document WHERE demande_id = ? "
                         "ORDER BY document_id LIMIT 1", (d["id"],)).fetchone()
    introuvable = HTTPException(404, f"Album {source} introuvable")
    if ligne is None:
        raise introuvable
    if portee.tout:
        a = conn.execute("SELECT id FROM albums WHERE id = ? AND document_id = ?",
                         (source, ligne["document_id"])).fetchone()
        projet_source = projet_d_album(conn, source) if a else None
        if a is None or est_isole(conn, projet_source):
            raise introuvable
        if projet_source == d["projet_id"]:
            raise HTTPException(409, "Cette copie est déjà du projet d'arrivée : on en part "
                                     "dans le projet, sans cette demande.")
    else:
        tenues = {c["album_id"] for pid, copies in sources.items()
                  if portee.peut_gerer_projet(pid) for c in copies}
        if source not in tenues or source not in _lues(conn, portee, [source]):
            raise introuvable
    collection_id = d["collection_id"]
    if collection_id is None or collection_row(conn, collection_id) is None:
        raise HTTPException(409, "La collection demandée n'existe plus : refusez cette "
                                 "demande.")
    if projet_de_collection(conn, collection_id) != d["projet_id"]:
        raise HTTPException(409, "La collection demandée n'est plus du projet qui l'a "
                                 "demandée : refusez cette demande.")
    if d["cran"] not in CRANS or d["cran"] == CRAN_IMAGES:
        raise HTTPException(409, f"Cran illisible sur cette demande ({d['cran']}) : "
                                 "refusez-la.")
    doc, demandeur = ligne["document_id"], d["demandeur"]
    nouvelle = _nouvelle_copie(conn, portee, doc, collection_id, source, pour=demandeur,
                               cran=d["cran"])
    conn.execute("UPDATE demande_document SET copie_id = ? WHERE demande_id = ?",
                 (nouvelle, d["id"]))
    _clore_demandes(conn, portee, [d["id"]], REPONSE_ACCEPTEE)


def _accepter_un_repartir(conn, portee, d: dict) -> None:
    """Une demande de REPARTIR DE ZÉRO acceptée (E8) : la copie demandée est ramenée au cran
    demandé, par qui répond — la portée totale, qui efface tout (`_repartir`, sa garde et son
    acte). La copie détruite depuis : la destruction a déjà clos la demande. Rien au-dessus
    du cran (quelqu'un l'a fait entre-temps) : la demande est satisfaite, elle se clôt
    acceptée sans rien écrire d'autre. Ne commite pas."""
    ligne = conn.execute("SELECT album_id FROM demande_document WHERE demande_id = ? "
                         "ORDER BY document_id LIMIT 1", (d["id"],)).fetchone()
    copie = ligne["album_id"] if ligne else None
    if copie is None or conn.execute("SELECT 1 FROM albums WHERE id = ?",
                                     (copie,)).fetchone() is None:
        raise HTTPException(409, "Cette copie n'existe plus : refusez cette demande.")
    if d["cran"] not in CRANS[:-1]:
        raise HTTPException(409, f"Cran illisible sur cette demande ({d['cran']}) : "
                                 "refusez-la.")
    if rang_du_cran(d["cran"]) < niveau_de_travail(conn, copie):
        _repartir(conn, portee, copie, d["cran"])
    _clore_demandes(conn, portee, [d["id"]], REPONSE_ACCEPTEE)


def _accepter_un_retour(conn, portee, d: dict) -> None:
    """« Rendre à … » : la copie gardée au fonds revient dans la collection que le
    responsable a nommée, avec tout son travail — c'est le geste « Rendre » de la fiche du
    document, fait sur demande. Ses refus se NOMMENT (409) et la demande reste en attente,
    comme pour un `rejoindre` : la copie détruite depuis (la destruction clôt d'ailleurs la
    demande), la collection supprimée (sa suppression aussi), une copie qui n'est plus
    gardée, un rangement qui traverserait les projets."""
    ligne = conn.execute("SELECT album_id, titre FROM demande_document WHERE demande_id = ? "
                         "ORDER BY document_id LIMIT 1", (d["id"],)).fetchone()
    copie = ligne["album_id"] if ligne else None
    collection_id = d["collection_id"]
    if copie is None or conn.execute("SELECT 1 FROM albums WHERE id = ?",
                                     (copie,)).fetchone() is None:
        raise HTTPException(409, "Cette copie n'existe plus : refusez cette demande.")
    if collection_id is None or collection_row(conn, collection_id) is None:
        raise HTTPException(409, "La collection demandée n'existe plus : refusez cette "
                                 "demande.")
    if conn.execute("SELECT 1 FROM collection_album WHERE album_id = ?",
                    (copie,)).fetchone() is not None:
        raise HTTPException(409, f"« {ligne['titre']} » n'est plus gardé au fonds : "
                                 "refusez cette demande.")
    if rangement_traverse(conn, copie, collection_id):
        raise HTTPException(409, "Cette copie appartient à un autre projet que la collection "
                                 "demandée : le rangement ne traverse pas les projets.")
    ranger_copie(conn, copie, collection_id)
    conn.execute("UPDATE demande_document SET copie_id = ? WHERE demande_id = ?",
                 (copie, d["id"]))
    _clore_demandes(conn, portee, [d["id"]], REPONSE_ACCEPTEE)


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
        a["cran"] = a["creee_par"] = a["creee_le"] = a["retour"] = None
        a["retire_du_projet"] = None
    # COL-3, écran de la 3a — la PROVENANCE de chaque copie (« Copies de travail · n » de la
    # fiche) : qui l'a créée, quand, et si c'est une copie vierge née d'une autre (`cran`).
    for r in conn.execute("SELECT album_id, creee_par, creee_le, cran FROM copie"):
        if r["album_id"] in par_album:
            par_album[r["album_id"]].update(creee_par=r["creee_par"], creee_le=r["creee_le"],
                                            cran=r["cran"])
    # COL-3, tranche 3b — une copie gardée parce que le RESPONSABLE de son projet l'en a
    # retirée (« Retirer du projet », Hugo, 2026-10-21) : qui, et quand — le dernier acte qui
    # le dit, si aucune sortie n'a suivi (rendue puis ressortie d'une collection, elle est
    # gardée pour une autre raison).
    sorties = {r[0]: r[1] for r in conn.execute(
        "SELECT json_extract(avant, '$.album_id'), MAX(id) FROM evenement "
        "WHERE cible_table = 'collection_album' AND type = 'delien' AND json_valid(avant) "
        "GROUP BY json_extract(avant, '$.album_id')")}
    for r in conn.execute(
            "SELECT id, json_extract(apres, '$.album_id') AS album_id, agent, date "
            "FROM evenement WHERE cible_table = 'document' AND type = 'modification' "
            "AND json_valid(apres) AND json_extract(apres, '$.retire_du_projet') IS NOT NULL "
            "ORDER BY id"):
        a = par_album.get(r["album_id"])
        if a is not None and not a["collections"] and r["id"] > sorties.get(r["album_id"], 0):
            a["retire_du_projet"] = {"par": r["agent"], "le": r["date"]}
    # Et le RETOUR qui attend sur une copie gardée : la fiche le dit, et mène à « À faire ».
    for r in conn.execute(
            "SELECT dd.album_id, d.id, d.date_creation, d.collection_nom FROM demande d "
            "JOIN demande_document dd ON dd.demande_id = d.id "
            "WHERE d.genre = ? AND d.reponse IS NULL ORDER BY d.id", (DEMANDE_RENDRE,)):
        a = par_album.get(r["album_id"])
        if a is not None and a["retour"] is None:
            a["retour"] = {"id": r["id"], "date_creation": r["date_creation"],
                           "collection_nom": r["collection_nom"]}
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
    noms = noms_lisibles(conn, [d["importe_par"] for d in documents if d["importe_par"]]
                         + [a["creee_par"] for a in par_album.values() if a["creee_par"]])
    noms.update(noms_lisibles(conn, [a["retire_du_projet"]["par"] for a in par_album.values()
                                     if a["retire_du_projet"] and a["retire_du_projet"]["par"]]))
    for a in par_album.values():
        a["creee_par_nom"] = noms.get(a["creee_par"]) if a["creee_par"] else None
        if a["retire_du_projet"]:
            par = a["retire_du_projet"]["par"]
            a["retire_du_projet"]["par_nom"] = noms.get(par) if par else None
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
    # COL-4 (S3) — les copies des BACS À SABLE et du JEU n'y paraissent pas, pour personne
    # (Hugo, 2026-10-24 : l'administrateur ne lit rien d'un bac à sable) : un document qui
    # n'a de copie que là (le jeu, ce qu'on a importé dans un bac à sable) disparaît de la
    # liste, les autres perdent ces copies.
    isoles = _projets_isoles(conn)["tous"]
    for d in documents:
        d["copies"] = [a for a in d["copies"] if a["projet_id"] not in isoles]
        d["appele"] = any(a["collections"] for a in d["copies"])
        if d["demande"] is not None and all(a["album_id"] != d["demande"]["album_id"]
                                             for a in d["copies"]):
            d["demande"] = None
    documents = [d for d in documents
                 if d["copies"] or d["projet_origine_id"] not in isoles]
    return {"documents": documents, "copies_sans_document": sans}


# --------------------------------------------------------------------------- #
# Les notices du fonds (COL-3, tranche 3) — ce qu'un responsable parcourt pour puiser
# --------------------------------------------------------------------------- #
# Les clés d'une notice, NOMMÉES : la route est une requête à elle, et non `lire_le_fonds`
# filtré — une colonne neuve ne doit pas s'y publier par défaut (la leçon de
# `GET /api/export/json`). `tests/test_prendre.py` exige ces clés et AUCUNE autre, sur le
# JSON brut.
CLES_NOTICE = ("document_id", "titre", "serie", "auteur")
_NOTICES_PAR_PAGE, _NOTICES_PAGE_MAX = 50, 200


@router.get("/api/fonds/notices")
def lire_les_notices(q: str = "", offset: int = 0, limit: int = _NOTICES_PAR_PAGE,
                     projet_id: int | None = None,
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Les NOTICES du fonds — titre, série, auteur, et rien d'autre —, cherchées et par
    pages (D3 ; « un millier de documents visés d'ici un an », maquette v8).

    Le droit d'abord, l'objet ensuite : 403 nommé à qui ne lit pas les notices
    (`Portee.peut_lire_les_notices` — une portée totale, ou un responsable de projet), le
    même quels que soient les paramètres. La notice est celle de la plus ANCIENNE copie
    vivante du document (D7) : deux copies peuvent dire deux titres, l'administrateur le
    voit dans la fiche du document.

    `q` cherche dans le titre, la série et l'auteur, sans égard à la casse ni aux accents.
    `projet_id` — un projet que l'appelant GÈRE (404 s'il ne le voit pas, 403 nommé s'il le
    voit sans le gérer) — ajoute deux faits par notice, et deux seulement : le projet a-t-il
    déjà une copie RANGÉE de ce document (`dans_le_projet`), en a-t-il une GARDÉE au fonds
    (`garde_au_fonds`, qui se reprend). Jamais dans QUELLE collection : être responsable
    n'ouvre aucune collection du projet, et dire laquelle décrirait une étude qu'il ne lit
    peut-être pas. Que le document soit employé AILLEURS n'est jamais dit."""
    if not portee.peut_lire_les_notices():
        raise HTTPException(403, "Les notices du fonds se lisent par les responsables de "
                                 "projet et les administrateurs de l'instance.")
    if projet_id is not None:
        _get_projet(conn, portee, projet_id, gerer=True,
                    motif="Ce que ce projet a déjà se lit par son responsable.")
    limit = max(1, min(int(limit), _NOTICES_PAGE_MAX))
    offset = max(0, int(offset))
    # COL-4 (S3) — un document né dans un BAC À SABLE, ou du JEU, n'existe pour aucun autre
    # projet : seules comptent les copies hors des projets isolés, et la notice est celle de
    # la plus ancienne d'entre elles. Pour toute portée.
    lignes = conn.execute(
        "SELECT a.document_id, a.titre, a.serie, a.auteur FROM albums a "
        "WHERE a.document_id IS NOT NULL "
        "AND a.id = (SELECT MIN(b.id) FROM albums b WHERE b.document_id = a.document_id "
        f"            AND NOT {sql_album_isole('b')}) "
        "ORDER BY a.titre COLLATE NOCASE, a.document_id").fetchall()
    cherche = _sans_accents((q or "").strip())
    if cherche:
        lignes = [r for r in lignes
                  if any(cherche in _sans_accents(r[k] or "") for k in ("titre", "serie",
                                                                       "auteur"))]
    page = lignes[offset:offset + limit]
    notices = [{k: r[k] for k in CLES_NOTICE} for r in page]
    if projet_id is not None and notices:
        ids = [n["document_id"] for n in notices]
        marques = ", ".join("?" * len(ids))
        etats = {}
        for r in conn.execute(
                f"SELECT a.document_id, EXISTS (SELECT 1 FROM collection_album ca "
                f"                              WHERE ca.album_id = a.id) AS range "
                f"FROM albums a WHERE a.document_id IN ({marques}) "
                f"AND {sql_projet_d_album('a')} = ?", (*ids, projet_id)):
            e = etats.setdefault(r[0], {"dans_le_projet": False, "garde_au_fonds": False})
            e["dans_le_projet" if r[1] else "garde_au_fonds"] = True
        for n in notices:
            n.update(etats.get(n["document_id"],
                               {"dans_le_projet": False, "garde_au_fonds": False}))
    return {"total": len(lignes), "offset": offset, "limit": limit, "notices": notices}


# --------------------------------------------------------------------------- #
# Prendre des documents pour une collection (COL-3, tranche 3a)
# --------------------------------------------------------------------------- #
REPONSE_ZERO, REPONSE_REJOINDRE, REPONSE_REPRENDRE = "zero", "rejoindre", "reprendre"
# Tranche 3b — EN PARTIR d'un travail qu'on lit, jusqu'à un cran (E1, E4).
REPONSE_AMORCER = "amorcer"
REPONSES_PRISE = (REPONSE_ZERO, REPONSE_REJOINDRE, REPONSE_REPRENDRE, REPONSE_AMORCER)
_DOCUMENTS_PAR_PRISE = 100


def _introuvable(document_id) -> HTTPException:
    """Le même refus, que le document existe ou non : qui n'a pas le droit de le NOMMER
    n'apprend rien de lui (« 404, jamais 403 », AUTH-2)."""
    return HTTPException(404, f"Document {document_id} introuvable")


def _copies_du_document(conn, document_id) -> list[dict]:
    """Les copies VIVANTES d'un document, la plus ancienne d'abord : id, projet LU, et si
    elle est rangée quelque part."""
    return _rows(conn.execute(
        f"SELECT a.id, a.titre, {sql_projet_d_album('a')} AS projet_id, "
        "EXISTS (SELECT 1 FROM collection_album ca WHERE ca.album_id = a.id) AS range "
        "FROM albums a WHERE a.document_id = ? ORDER BY a.id", (document_id,)))


def _lues(conn, portee, album_ids) -> set:
    """Celles de ces copies que l'appelant LIT (`clause_album`)."""
    if not album_ids:
        return set()
    ou, params = portee.clause_album("a.id")
    marques = ", ".join("?" * len(album_ids))
    return {r[0] for r in conn.execute(
        f"SELECT a.id FROM albums a WHERE a.id IN ({marques}) AND {ou}",
        (*album_ids, *params))}


def _plan_d_une_ligne(conn, portee, collection_id, projet_id, gere, ligne) -> dict:
    """Ce que deviendra UNE ligne d'une prise, sans rien écrire : `fait` (et comment),
    `demande` (et quel genre), ou `refuse` (et pourquoi). Lève 404 sur un document que
    l'appelant n'a pas le droit de NOMMER — la prise entière s'arrête alors, avant toute
    écriture, et le refus est le même que le document existe ou non.

    Qui nomme quoi (D3) : une portée totale et le RESPONSABLE du projet d'arrivée nomment
    tout document du fonds — ils en lisent les notices ; tout autre écrivain de la
    collection ne nomme qu'un document dont il LIT déjà une copie dans ce projet."""
    doc = ligne.document_id
    toutes = _copies_du_document(conn, doc)
    # COL-4 (S3) — un bac à sable est un cul-de-sac, et c'est la NATURE du projet qui le
    # tient, pour toute portée : une copie d'un projet ISOLÉ (bac à sable, jeu) n'est la
    # source de rien dans un autre projet, et rien n'entre dans un bac à sable qui ne lui
    # appartienne déjà. Ce qui reste est tout ce que la prise peut nommer.
    isoles = _projets_isoles(conn)
    bac_arrivee = projet_id in isoles["bacs"]
    copies = [c for c in toutes
              if c["projet_id"] == projet_id
              or (not bac_arrivee and c["projet_id"] not in isoles["tous"])]
    lues = _lues(conn, portee, [c["id"] for c in toutes])
    nommee = next((c for c in toutes if c["id"] == ligne.album_id), None)
    # Ce qu'on ne LIT pas reste introuvable, même à une portée totale : bornée, elle ne lit
    # pas le bac à sable d'un autre (Hugo, 2026-10-24), et le refus « cul-de-sac » y dirait
    # qu'une copie y vit.
    # Le refus nomme ce qui isole : le JEU pour une copie de référence (contre-relecture :
    # « un bac à sable est un cul-de-sac » se disait de la référence du jeu), un bac à sable
    # sinon.
    jeu = isoles["tous"] - set(isoles["bacs"])
    if (ligne.album_id is not None and nommee is not None and nommee not in copies
            and nommee["id"] in lues):
        return {"document_id": doc, "reponse": ligne.reponse, "etat": REFUSE,
                "motif": _MOTIF_JEU_SOURCE if nommee["projet_id"] in jeu
                else _MOTIF_BAC_ISOLE}
    if not copies and toutes and portee.tout and any(c["id"] in lues for c in toutes):
        lues_jeu = any(c["id"] in lues and c["projet_id"] in jeu for c in toutes)
        return {"document_id": doc, "reponse": ligne.reponse, "etat": REFUSE,
                "motif": _MOTIF_JEU_SOURCE if lues_jeu else _MOTIF_BAC_ISOLE}
    du_projet_lues = [c for c in copies if c["id"] in lues and c["projet_id"] == projet_id]
    if not copies or not (portee.tout or gere or du_projet_lues):
        raise _introuvable(doc)
    plan = {"document_id": doc, "reponse": ligne.reponse}

    if ligne.reponse == REPONSE_ZERO:
        # La copie d'où partent les images : celle qu'on nomme, si on la lit ; sinon la
        # plus ancienne qu'on lit dans le projet ; sinon — portée totale ou responsable —
        # la plus ancienne du document, celle dont le fonds montre la notice (D7).
        if ligne.album_id is not None:
            source = next((c for c in copies if c["id"] == ligne.album_id
                           and (portee.tout or c["id"] in lues)), None)
            if source is None:
                raise HTTPException(404, f"Album {ligne.album_id} introuvable")
            # La source d'une copie vierge est une copie de CE projet (relecture croisée) :
            # nommer une copie d'un autre projet ferait entrer sa notice et ses scans ici
            # sans que personne y consente — entre deux projets, c'est le responsable qui
            # demande au fonds, et un administrateur qui accepte (D3).
            if not portee.tout and source["projet_id"] != projet_id:
                return {**plan, "etat": REFUSE,
                        "motif": "Cette copie vit dans un autre projet : faire entrer ce "
                                 "document dans celui-ci se demande par son responsable, "
                                 "depuis les notices du fonds."}
        else:
            source = (du_projet_lues or copies)[0]
        plan["source"], plan["titre"] = source["id"], source["titre"]
        # « Partir de zéro » sans rien demander à personne (geste 5) : la portée totale, et
        # qui LIT déjà une copie du document dans ce projet — le projet l'a, et une copie
        # vierge ne suppose le travail de personne. Sinon le responsable DEMANDE l'entrée
        # du document dans son projet, et un administrateur y répond (gestes 2 et 3).
        if portee.tout or du_projet_lues:
            plan["etat"] = FAIT
        else:
            plan["etat"], plan["genre"] = DEMANDE, DEMANDE_ENTREE_DOCUMENTS
            plan["album_id"] = None
        return plan

    if ligne.reponse == REPONSE_AMORCER:
        return {**plan, **_plan_amorcer(conn, portee, copies, lues, projet_id, gere, ligne)}

    if ligne.reponse == REPONSE_REJOINDRE:
        if ligne.album_id is None:
            raise HTTPException(422, "Rejoindre : quelle copie ? (`album_id`)")
        copie = next((c for c in copies if c["id"] == ligne.album_id and c["id"] in lues),
                     None)
        if copie is None:
            raise HTTPException(404, f"Album {ligne.album_id} introuvable")
        plan["album_id"], plan["titre"] = copie["id"], copie["titre"]
        return {**plan, **_plan_rejoindre(conn, portee, copie["id"], collection_id)}

    # REPRENDRE une copie gardée au fonds de CE projet (geste 6) — le « Rendre » de
    # l'administrateur, qu'un responsable DEMANDE : la copie porte un travail fait dans une
    # collection qu'il ne lit peut-être pas.
    # Le droit AVANT l'objet (relecture croisée) : à qui n'est ni responsable du projet ni
    # administrateur, le même refus, qu'une copie y soit gardée ou non — sinon la réponse
    # disait l'existence d'une copie gardée au fonds, que seul le fonds montre.
    if bac_arrivee:
        # COL-4 — dans un bac à sable, rien ne part au fonds (`sortir_album`) : il n'y a
        # rien à reprendre, ni à demander.
        return {**plan, "etat": REFUSE,
                "motif": "Dans un bac à sable, rien n'est gardé au fonds : il n'y a rien à "
                         "reprendre."}
    if not (portee.tout or gere):
        return {**plan, "etat": REFUSE,
                "motif": "Reprendre une copie gardée au fonds se demande par un responsable "
                         "du projet."}
    gardees = [c for c in copies if not c["range"] and c["projet_id"] == projet_id
               and (ligne.album_id is None or c["id"] == ligne.album_id)]
    if not gardees:
        return {**plan, "etat": REFUSE,
                "motif": "Aucune copie de ce document n'est gardée au fonds pour ce projet."}
    plan["album_id"], plan["titre"] = gardees[0]["id"], gardees[0]["titre"]
    if portee.tout:
        plan["etat"] = FAIT
    else:
        # Un RETOUR, et non une ligne d'entrée (écran de la 3a, Hugo, 2026-10-17) : la copie
        # existe avec son travail, l'administrateur répond « Rendre à … » ou « Garder au
        # fonds », et la demande s'attend une fois par copie.
        plan["etat"], plan["genre"] = DEMANDE, DEMANDE_RENDRE
    return plan


def _projets_isoles_ou_effaces(conn) -> set:
    """Les projets isolés d'aujourd'hui, et les bacs à sable déjà EFFACÉS — lus au journal,
    où leur effacement s'écrit (`suppression` sous `projet`, charge `bac_a_sable`). Les
    identifiants de projet ne reviennent pas (v31) : un projet effacé ne se confond avec
    aucun autre."""
    effaces = {r[0] for r in conn.execute(SQL_BACS_EFFACES)}
    return _projets_isoles(conn)["tous"] | effaces


def _projets_isoles(conn) -> dict:
    """`{"tous": {ids des projets isolés}, "bacs": {id d'un bac à sable: son
    propriétaire}}` — COL-4, une requête."""
    tous, bacs = set(), {}
    for pid, de, jeu in conn.execute(
            "SELECT id, bac_a_sable_de, jeu FROM projet "
            "WHERE bac_a_sable_de IS NOT NULL OR jeu = 1"):
        tous.add(pid)
        if de is not None:
            bacs[pid] = de
    return {"tous": tous, "bacs": bacs}


def _cran_d_amorce(cran) -> str:
    """Le cran d'une copie amorcée : un cran de l'échelle AU-DESSUS d'`images` — une copie
    vierge est la réponse `zero`. 422 nommé sinon."""
    if cran not in CRANS or cran == CRAN_IMAGES:
        haut = " | ".join(c for c in CRANS if c != CRAN_IMAGES)
        raise HTTPException(422, f"En partir : jusqu'à quel cran ? ({haut} ; une copie "
                                 "vierge est la réponse « zero »).")
    return cran


def _source_d_amorce(conn, portee, copies, lues, projet_id, album_id):
    """La copie d'où l'on part, qu'on doit LIRE — 404 sinon, le même qu'elle existe ou
    non — et ce qu'on peut en faire : `None` si elle est du projet d'arrivée (ou pour une
    portée totale), sinon le motif du refus. Entre deux projets, en partir se demande par
    le responsable, sans nommer la source (E7) : ce n'est pas ce geste-ci."""
    if album_id is None:
        raise HTTPException(422, "En partir : de quelle copie ? (`album_id`)")
    source = next((c for c in copies if c["id"] == album_id and c["id"] in lues), None)
    if source is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
    if not portee.tout and source["projet_id"] != projet_id:
        return source, ("Cette copie vit dans un autre projet : en partir pour celui-ci se "
                        "demande par son responsable, depuis les notices du fonds.")
    return source, None


def _plan_amorcer(conn, portee, copies, lues, projet_id, gere, ligne) -> dict:
    """EN PARTIR d'une copie qu'on lit dans le projet (tranche 3b, E4) : une copie à soi,
    amorcée avec son travail jusqu'au cran dit. La règle de `rejoindre`, telle quelle —
    immédiat pour qui administre chacune des collections où vit la source
    (`Portee.clause_rejoindre_directe`) et pour la portée totale ; sinon une DEMANDE
    (`DEMANDE_AMORCER`) au propriétaire. Copier un travail dans une autre collection le fait
    lire par ses lecteurs : c'est élargir le cercle, ce que D4 réserve au propriétaire — sans
    cette règle, qui se voit refuser `rejoindre` copierait le travail à la place.

    ENTRE DEUX PROJETS (E7) : le RESPONSABLE du projet d'arrivée ne nomme aucune copie
    (`album_id` absent) — il demande un document et un cran, qu'il a trouvés dans les notices.
    La ligne est TOUJOURS une demande (`DEMANDE_AMORCER_ENTRE_PROJETS`), quoi que porte le
    fonds : une réponse qui dirait « personne n'a ce travail », ou qui nommerait qui
    répondra, lui apprendrait ce qu'un autre projet tient. Le plan ne lit donc RIEN de ce
    que portent les copies. Qui n'est pas responsable nomme sa copie, ou se voit dire de le
    faire."""
    cran = _cran_d_amorce(ligne.cran)
    if ligne.album_id is None and gere and not portee.tout:
        return {"album_id": None, "titre": titre_de_notice(conn, ligne.document_id),
                "cran": cran, "etat": DEMANDE, "genre": DEMANDE_AMORCER_ENTRE_PROJETS}
    source, refus = _source_d_amorce(conn, portee, copies, lues, projet_id, ligne.album_id)
    plan = {"album_id": source["id"], "titre": source["titre"], "cran": cran}
    if refus:
        return {**plan, "etat": REFUSE, "motif": refus}
    ou, params = portee.clause_rejoindre_directe("a.id")
    if conn.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ou}",
                    (source["id"], *params)).fetchone():
        return {**plan, "etat": FAIT}
    return {**plan, "etat": DEMANDE, "genre": DEMANDE_AMORCER}


def prendre(conn, portee, collection_id: int, payload) -> dict:
    """Le cœur de la prise, pour les deux routes qui la servent. Cf. `prendre_pour_collection`."""
    collection = collection_row(conn, collection_id)
    if collection is None or not portee.peut_ecrire(collection_id):
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    _refuser_le_jeu(conn, collection_id=collection_id)    # COL-4 : rien n'entre dans le jeu
    lignes = payload.documents
    if not lignes:
        raise HTTPException(422, "Quels documents ? La liste est vide.")
    if len(lignes) > _DOCUMENTS_PAR_PRISE:
        raise HTTPException(422, f"Une prise porte {_DOCUMENTS_PAR_PRISE} documents au plus "
                                 f"({len(lignes)} reçus).")
    if len({x.document_id for x in lignes}) != len(lignes):
        raise HTTPException(422, "Un même document figure deux fois dans la prise.")
    for x in lignes:
        if x.reponse not in REPONSES_PRISE:
            raise HTTPException(422, f"Réponse inconnue : {x.reponse} "
                                     f"({' | '.join(REPONSES_PRISE)}).")
    projet_id = projet_de_collection(conn, collection_id)
    # COL-4 (S2) — être responsable de son bac à sable ne fait nommer AUCUN document du
    # fonds : seuls ceux dont on lit déjà une copie dans le bac à sable (le jeu, ce qu'on y
    # a importé).
    bac_arrivee, _ = _bac_a_sable_de(conn, projet_id=projet_id)
    if bac_arrivee is not None:
        # COL-4 (Hugo, 2026-10-24) — dans un bac à sable, une portée totale bornée prend
        # comme un arrivant : ses ensembles ordinaires répondent, jamais `tout`.
        portee = portee.dans_les_bacs()
    gere = portee.peut_gerer_projet(projet_id) and bac_arrivee is None
    # En partir recopie l'index des régions, et peut en recalculer les lemmes : spaCy se
    # charge HORS de la transaction d'écriture (CLAUDE.md § Concurrence).
    if any(x.reponse == REPONSE_AMORCER for x in lignes):
        nlp.ensure_loaded()
    # Tout se lit et s'écrit sous le verrou d'écriture : deux prises simultanées passaient
    # sinon toutes deux le refus du doublon, et une copie lue « gardée au fonds » pouvait
    # être rendue entre-temps.
    conflit.verrouiller(conn)
    plans = [_plan_d_une_ligne(conn, portee, collection_id, projet_id, gere, x)
             for x in lignes]
    for p in plans:
        if p["etat"] != DEMANDE:
            continue
        if p["genre"] == DEMANDE_RENDRE:
            # Un retour s'attend une fois par COPIE, quelle que soit la collection nommée.
            if _retour_en_attente(conn, p["album_id"]) is not None:
                p.update(etat=REFUSE, motif="Le retour de cette copie est déjà demandé : la "
                                            "demande attend sa réponse.")
        elif _en_attente_vers(conn, p["genre"], collection_id, p["document_id"],
                              p.get("album_id")):
            p.update(etat=REFUSE, motif="Déjà demandé pour cette collection : la demande "
                                        "attend sa réponse.")
    if bac_arrivee is not None:
        # COL-4 — aucune demande, d'aucun genre, ne naît d'un bac à sable : ni à un
        # administrateur (une entrée de documents, un retour), ni à son propriétaire (un
        # « rejoindre », un « en partir ») — relecture croisée. Chaque ligne qui se
        # demanderait est refusée, et dit pourquoi ; rien n'est écrit pour elle.
        for p in plans:
            if p["etat"] == DEMANDE:
                p.update(etat=REFUSE, motif=_MOTIF_BAC_SANS_DEMANDE)
    entrees = [p for p in plans if p["etat"] == DEMANDE
               and p["genre"] == DEMANDE_ENTREE_DOCUMENTS]
    ailleurs = [p for p in plans if p["etat"] == DEMANDE
                and p["genre"] == DEMANDE_AMORCER_ENTRE_PROJETS]
    if entrees or ailleurs:
        # Une entrée, ou une demande d'en partir entre deux projets, sans motif ne se lit
        # pas : le responsable qui consent lit pourquoi son travail partirait.
        motif = _motif(payload.motif)
    else:
        motif = _motif(payload.motif) if (payload.motif or "").strip() else None
    # Les gestes faits tout de suite.
    for p in plans:
        if p["etat"] != FAIT:
            continue
        if p.get("deja"):
            p["copie_id"] = p["album_id"]
        elif p["reponse"] == REPONSE_ZERO:
            p["copie_id"] = _nouvelle_copie(conn, portee, p["document_id"], collection_id,
                                            p["source"])
        elif p["reponse"] == REPONSE_AMORCER:
            p["copie_id"] = _nouvelle_copie(conn, portee, p["document_id"], collection_id,
                                            p["album_id"], cran=p["cran"])
        else:                                   # rejoindre, reprendre : un rangement
            # Reprise directe (portée totale) : `ranger_copie` clôt aussi le retour demandé
            # pour cette copie.
            ranger_copie(conn, p["album_id"], collection_id)
            p["copie_id"] = p["album_id"]
    # Les demandes : UNE entrée pour tous les documents qui en demandent une (case « Une
    # entrée de documents porte PLUSIEURS albums à la fois ») ; un `rejoindre` par copie —
    # chacun s'adresse aux propriétaires de SES collections, qui ne sont pas les mêmes.
    if entrees:
        did = _deposer(conn, portee, DEMANDE_ENTREE_DOCUMENTS, collection, projet_id, motif,
                       entrees)
        for p in entrees:
            p["demande_id"] = did
    # Un RETOUR par copie gardée (écran de la 3a) : chacun se répond à part, « Rendre à … »
    # ou « Garder au fonds ».
    for p in plans:
        if p["etat"] == DEMANDE and p["genre"] == DEMANDE_RENDRE:
            p["demande_id"] = _deposer(conn, portee, DEMANDE_RENDRE, collection, projet_id,
                                       motif, [p])
    for p in plans:
        if p["etat"] == DEMANDE and p["genre"] in GENRES_CONSENTIS:
            # Une demande par copie (un rejoindre, ou en partir) : chacune s'adresse aux
            # propriétaires des collections de SA copie.
            p["demande_id"] = _deposer(conn, portee, p["genre"], collection,
                                       projet_id, motif, [p], cran=p.get("cran"))
            # Qui y répondra (Hugo, 2026-10-17 : le message ne ment pas) — un propriétaire
            # qui tient toutes les collections de la copie, sinon un administrateur seul.
            p["repondra"] = ("proprietaire"
                             if un_proprietaire_tient_toute_la_copie(conn, p["album_id"])
                             else "administrateur")
    # E7 — une demande par document, sans copie nommée, et SANS `repondra` : qui y répondra
    # dépend de ce que les autres projets tiennent, que le demandeur ne doit pas apprendre.
    for p in ailleurs:
        p["demande_id"] = _deposer(conn, portee, DEMANDE_AMORCER_ENTRE_PROJETS, collection,
                                   projet_id, motif, [p], cran=p["cran"])
    conn.commit()
    return {"collection_id": collection_id,
            "documents": [{k: p[k] for k in ("document_id", "reponse", "cran", "etat",
                                             "copie_id", "demande_id", "repondra", "motif")
                           if k in p}
                          for p in plans]}


@router.post("/api/collections/{collection_id}/prendre")
def prendre_pour_collection(collection_id: int, payload: PriseIn,
                            conn: sqlite3.Connection = Depends(db),
                            portee: autorisation.Portee = Depends(portee_courante)):
    """Prendre des documents pour une collection — la tranche 3a de COL-3, en une route.

    Chaque ligne nomme un document et sa réponse : `zero` (une copie VIERGE dans cette
    collection), `rejoindre` (ranger ici une copie qu'on lit, `album_id`), `reprendre`
    (rendre à cette collection une copie du projet gardée au fonds). Le résultat est rendu
    DOCUMENT PAR DOCUMENT : `fait` (la copie, `copie_id`), `demande` (`demande_id`), ou
    `refuse` (`motif`).

    404 sur une collection où l'on n'écrit pas, comme `ranger_album`. 404 sur un document
    qu'on n'a pas le droit de NOMMER — le même qu'il existe ou non —, et la prise entière
    s'arrête alors avant toute écriture (D3 : la portée totale et le responsable du projet
    nomment tout le fonds, un autre écrivain ce dont il lit une copie dans le projet). Une
    entrée de documents, qui se demande, exige un motif (422 nommé sans lui).

    Ce qui se fait sans rien demander : partir de zéro sur un document dont on lit déjà une
    copie dans le projet ; rejoindre une copie dont on administre chacune des collections
    (`Portee.clause_rejoindre_directe`) ; tout, pour la portée totale. Le reste se demande :
    l'entrée d'un document dans le projet, à un administrateur ; rejoindre, aux
    propriétaires des collections de la copie (D4 stricte, D11)."""
    return prendre(conn, portee, collection_id, payload)


@router.post("/api/projets/{projet_id}/prendre")
def prendre_pour_projet(projet_id: int, payload: PriseIn,
                        conn: sqlite3.Connection = Depends(db),
                        portee: autorisation.Portee = Depends(portee_courante)):
    """Prendre des documents pour un PROJET sans nommer de collection : ils arrivent dans
    sa collection de BASE (D10, Hugo, 2026-10-17 — « le fonds commence avec le projet »).

    Une route à part plutôt qu'un `collection_id` facultatif sur la première, pour deux
    raisons. Les deux écrans qui prennent pour un projet — « Prendre dans… » de la fiche
    d'un document, qui nomme un PROJET, et les notices parcourues depuis la fiche d'un
    projet — n'ont pas à connaître l'identifiant de sa base : c'est le serveur qui la
    désigne, par son drapeau, comme partout. Et le refus se dit dans les mots du geste :
    404 sur un projet qu'on ne peut pas nommer ; 403 nommé sur un projet dont on n'écrit
    pas dans la base — elle existe pour tout projet, son existence n'apprend rien.
    Ensuite c'est la MÊME prise, `prendre_pour_collection` sur la base, mêmes règles et
    mêmes résultats."""
    _get_projet(conn, portee, projet_id)
    base = collection_de_base(conn, projet_id)
    if base is None:
        raise HTTPException(409, "Ce projet n'a pas de collection de base : signalez-le à un "
                                 "administrateur.")
    if not portee.peut_ecrire(base):
        raise HTTPException(403, "Prendre pour ce projet sans nommer de collection fait "
                                 "entrer les documents dans sa collection de base, où vous "
                                 "n'écrivez pas : nommez une collection où vous écrivez.")
    return prendre(conn, portee, base, payload)


# --------------------------------------------------------------------------- #
# Lire ses demandes, là où vit qui les lit (D11)
# --------------------------------------------------------------------------- #
@router.get("/api/projets/{projet_id}/demandes")
def demandes_du_projet(projet_id: int, conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """Les ENTRÉES de documents demandées pour ce projet, et les RETOURS de ses copies
    gardées au fonds (`genre` les distingue), avec leur état — ce que lit son responsable
    dans la fiche du projet (D9 : « le dit à qui l'a déposée »). Les plus récentes d'abord ;
    une demande répondue reste.

    Réservée à qui GÈRE le projet : 404 à qui ne le voit pas, 403 nommé à qui le voit sans
    le gérer. Chaque document dit sa réponse et, accepté, la copie où il est entré. Ce que
    la vue ne dit PAS : qui a répondu, ce qu'un administrateur pèse dans le fonds. Qui a
    déposé ne s'y nomme que pour soi-même et pour une portée totale
    (`Portee.peut_nommer_le_demandeur`), comme partout.

    Tranche 3b (E7) — les demandes d'en partir ENTRE DEUX PROJETS aussi, avec leur `cran`. La
    vue en dit l'état et rien d'autre : ni à qui elle s'adresse, ni si un autre projet tient
    ce travail, ni qui l'a refusée — le demandeur lit « demandée » au bit près, que le
    travail existe ailleurs ou non. Acceptée, la copie neuve (`copie_id`) est la sienne."""
    _get_projet(conn, portee, projet_id, gerer=True,
                motif="Les demandes d'un projet se lisent par son responsable.")
    demandes = _rows(conn.execute(
        "SELECT id, genre, cran, demandeur, motif, date_creation, reponse, date_reponse, "
        "collection_id, collection_nom FROM demande WHERE genre IN (?, ?, ?) "
        "AND projet_id = ? ORDER BY id DESC",
        (DEMANDE_ENTREE_DOCUMENTS, DEMANDE_RENDRE, DEMANDE_AMORCER_ENTRE_PROJETS, projet_id)))
    lignes: dict[int, list] = {}
    if demandes:
        marques = ", ".join("?" * len(demandes))
        for x in _rows(conn.execute(
                "SELECT demande_id, document_id, titre, reponse, copie_id, "
                "album_id IS NOT NULL AS reprise FROM demande_document "
                f"WHERE demande_id IN ({marques}) ORDER BY document_id",
                [d["id"] for d in demandes])):
            x["reprise"] = bool(x["reprise"])
            lignes.setdefault(x.pop("demande_id"), []).append(x)
    noms = noms_lisibles(conn, [d["demandeur"] for d in demandes if d["demandeur"]
                                and portee.peut_nommer_le_demandeur(d["demandeur"])])
    for d in demandes:
        demandeur = d.pop("demandeur")
        if demandeur and portee.peut_nommer_le_demandeur(demandeur):
            d["demandeur"], d["demandeur_nom"] = demandeur, noms.get(demandeur)
        d["en_attente"] = d["reponse"] is None
        d["documents"] = lignes.get(d["id"], [])
    return demandes


@router.get("/api/projets/{projet_id}/demandes-recues")
def demandes_recues_du_projet(projet_id: int, conn: sqlite3.Connection = Depends(db),
                              portee: autorisation.Portee = Depends(portee_courante)):
    """Les demandes d'en partir ENTRE DEUX PROJETS qui s'adressent à CE projet (E7, tranche
    3b) — ce que son responsable lit dans la fiche du projet, là où il vit (D11 ; l'endroit
    exact se tranche sur maquette, E10). Une demande s'y lit tant qu'elle attend et que le
    projet TIENT le travail demandé (`database.projets_qui_tiennent`) : une copie rangée,
    travaillée au moins jusqu'au cran.

    Réservée à qui GÈRE le projet : 404 à qui ne le voit pas, 403 nommé à qui le voit sans le
    gérer ; un bac à sable n'en reçoit aucune (rien n'en sort). Chaque demande dit QUI
    demande et le NOM du projet d'arrivée — accepté par écrit au cadrage : on ne laisse pas
    partir son travail vers quelqu'un qu'on ne connaît pas —, le document (son titre de
    notice), le cran, le motif, et les copies du projet qui tiennent ce travail
    (`copies` : `album_id`, `titre`, `niveau`), parmi lesquelles qui accepte choisit la
    source. Jamais la collection d'arrivée : le projet suffit à consentir. `repondable` :
    `Portee.peut_repondre_a`.

    `copies` ne porte que les copies qu'il LIT, leur aperçu compris (relecture croisée de la
    3b, constat 2) : gérer le projet n'ouvre pas ses collections, et l'aperçu compterait le
    travail d'une collection fermée. Une demande dont il ne lit aucune copie se lit encore,
    sans copie à nommer : il peut la refuser — un refus la clôt pour tous (Hugo,
    2026-10-25) —, et l'administrateur, qui lit tout, y répond à sa place."""
    p = _get_projet(conn, portee, projet_id, gerer=True,
                    motif="Les demandes reçues par un projet se lisent par son responsable.")
    if est_isole(conn, p["id"]):
        return []
    demandes = _rows(conn.execute(
        "SELECT d.id, d.genre, d.cran, d.demandeur, d.motif, d.date_creation, d.projet_id, "
        "d.projet_nom, d.collection_id, dd.document_id, dd.titre FROM demande d "
        "JOIN demande_document dd ON dd.demande_id = d.id "
        "WHERE d.genre = ? AND d.reponse IS NULL AND d.projet_id IS NOT ? ORDER BY d.id",
        (DEMANDE_AMORCER_ENTRE_PROJETS, projet_id)))
    recues = []
    for d in demandes:
        if d["cran"] not in CRANS:
            continue
        sources = projets_qui_tiennent(conn, d["document_id"], d["cran"], sauf=d["projet_id"])
        if projet_id not in sources:
            continue
        consentement = {"genre": d["genre"], "projets": list(sources)}
        if not portee.peut_nommer_le_demandeur(d["demandeur"], consentement=consentement):
            d["demandeur"] = None                  # par ceinture : la garde l'exclut déjà
        # Écran de la 3b (Hugo, 2026-10-25) : « Depuis quelle copie », les copies trop peu
        # travaillées ÉTEINTES — toutes les copies rangées du projet, `tient` disant celles
        # qu'accepter peut nommer, chacune avec son aperçu en nombres.
        tenues = {c["album_id"] for c in sources[projet_id]}
        rangees = copies_rangees_du_projet(conn, d["document_id"], projet_id)
        lues = _lues(conn, portee, [c["album_id"] for c in rangees])
        d["copies"] = [{**c, "tient": c["album_id"] in tenues,
                        "apercu": _apercu(conn, c["album_id"], d)}
                       for c in rangees if c["album_id"] in lues]
        d["repondable"] = portee.peut_repondre_a(consentement)
        recues.append(d)
    noms = noms_lisibles(conn, [d["demandeur"] for d in recues if d["demandeur"]])
    for d in recues:
        d["demandeur_nom"] = noms.get(d["demandeur"]) if d["demandeur"] else None
        d.pop("collection_id")              # le projet suffit à consentir
    return recues


@router.get("/api/projets/{projet_id}/copies-gardees")
def copies_gardees_du_projet(projet_id: int, conn: sqlite3.Connection = Depends(db),
                             portee: autorisation.Portee = Depends(portee_courante)):
    """Les copies de ce projet GARDÉES AU FONDS — sorties de leur dernière collection, avec
    leur travail —, ce que la fiche du projet montre à son responsable pour qu'il demande à
    les RENDRE (écran de la 3a, Hugo, 2026-10-17 : « Copies gardées au fonds · n », «
    Demander à la rendre… »).

    Réservée à qui GÈRE le projet, comme ses demandes : 404 à qui ne le voit pas, 403 nommé à
    qui le voit sans le gérer. Ce que le responsable en savait déjà : les notices du fonds
    lui disent, document par document, que son projet en a une copie gardée
    (`garde_au_fonds`), et une demande de retour lui rend le titre de la copie. Ce que la vue
    ajoute : la copie à nommer (`album_id`), sa notice, depuis quand elle est gardée (la fin
    de son dernier emploi, lue au journal ; `None` quand elle n'est pas écrite), et la
    demande de retour qui l'attend. Ni qui l'a retirée, ni de quelle collection, ni son
    travail : être responsable n'ouvre aucune collection du projet."""
    _get_projet(conn, portee, projet_id, gerer=True,
                motif="Les copies gardées d'un projet se lisent par son responsable.")
    copies = _rows(conn.execute(
        "SELECT a.id AS album_id, a.document_id, a.titre, a.serie, a.auteur FROM albums a "
        "WHERE a.projet_id = ? AND a.document_id IS NOT NULL AND NOT EXISTS "
        "(SELECT 1 FROM collection_album ca WHERE ca.album_id = a.id) "
        "ORDER BY a.titre COLLATE NOCASE, a.id", (projet_id,)))
    for c in copies:
        r = conn.execute(
            "SELECT MAX(date) FROM evenement WHERE cible_table = 'collection_album' "
            "AND type = 'delien' AND json_extract(avant, '$.album_id') = ?",
            (c["album_id"],)).fetchone()
        c["garde_depuis"] = r[0] if r else None
        c["retire_du_projet"] = _retrait_garde(conn, c["album_id"])
        retour = _retour_en_attente(conn, c["album_id"])
        c["retour"] = None if retour is None else {
            "id": retour["id"], "date_creation": retour["date_creation"],
            "collection_id": retour["collection_id"],
            "collection_nom": retour["collection_nom"]}
    return copies


def _retrait_garde(conn, album_id: int):
    """Le retrait du projet qui a envoyé cette copie au fonds, si aucune sortie ne l'a suivi
    (écran de la 3b, « retiré du projet par … ») : qui, son nom, quand, le motif ; None
    sinon."""
    sortie = conn.execute(
        "SELECT MAX(id) FROM evenement WHERE cible_table = 'collection_album' "
        "AND type = 'delien' AND json_valid(avant) "
        "AND json_extract(avant, '$.album_id') = ?", (album_id,)).fetchone()[0] or 0
    r = conn.execute(
        "SELECT id, agent, date, json_extract(apres, '$.retire_du_projet.motif') AS motif "
        "FROM evenement WHERE cible_table = 'document' AND type = 'modification' "
        "AND json_valid(apres) AND json_extract(apres, '$.retire_du_projet') IS NOT NULL "
        "AND json_extract(apres, '$.album_id') = ? ORDER BY id DESC LIMIT 1",
        (album_id,)).fetchone()
    if r is None or r["id"] < sortie:
        return None
    nom = noms_lisibles(conn, [r["agent"]]).get(r["agent"]) if r["agent"] else None
    return {"par": r["agent"], "par_nom": nom, "le": r["date"], "motif": r["motif"]}


@router.get("/api/collections/{collection_id}/demandes")
def demandes_recues(collection_id: int, conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Les demandes de REJOINDRE qui attendent sur une copie rangée dans cette collection
    — ce que son propriétaire lit dans la fiche de SA collection, là où il vit (D11). Et,
    depuis la tranche 3b, celles d'EN PARTIR (E4) : `genre` les distingue, et une demande
    d'en partir dit son `cran`.

    Réservée à qui ADMINISTRE la collection : 404 à qui ne la lit pas, 403 nommé à qui la
    lit sans la posséder. Chaque demande dit QUI demande et pour quelle collection
    d'ARRIVÉE, son nom compris : on ne consent pas à partager un travail avec une collection
    dont on ignore le nom, ni avec quelqu'un qu'on ne connaît pas — ce que le cadrage de la
    tranche 3 a accepté par écrit (« Ce qui fuit si l'on se trompe »), dans le même projet,
    le rangement ne traversant pas les projets. `repondable` dit si l'appelant peut y
    répondre (`Portee.peut_repondre_a`) : une copie qui vit aussi dans une collection qu'il
    ne possède pas se consent par qui les tient toutes, ou par un administrateur."""
    _get_collection(conn, portee, collection_id, administrer=True,
                    motif="Les demandes reçues par une collection se lisent par son "
                          "propriétaire.")
    demandes = _rows(conn.execute(
        "SELECT d.id, d.genre, d.cran, d.demandeur, d.motif, d.date_creation, d.collection_id, "
        "d.collection_nom, dd.document_id, dd.album_id, dd.titre FROM demande d "
        "JOIN demande_document dd ON dd.demande_id = d.id "
        "JOIN collection_album ca ON ca.album_id = dd.album_id AND ca.collection_id = ? "
        "WHERE d.genre IN (?, ?) AND d.reponse IS NULL ORDER BY d.id",
        (collection_id, *GENRES_CONSENTIS)))
    for d in demandes:
        consentement = {"genre": d["genre"], "collections": [r[0] for r in conn.execute(
            "SELECT collection_id FROM collection_album WHERE album_id = ?",
            (d["album_id"],))]}
        if not portee.peut_nommer_le_demandeur(d["demandeur"], consentement=consentement):
            d["demandeur"] = None                  # par ceinture : la garde l'exclut déjà
        d["repondable"] = portee.peut_repondre_a(consentement)
        # Écran de la 3b (Hugo, 2026-10-25) : la demande d'en partir se lit avec son aperçu.
        d["apercu"] = (_apercu(conn, d["album_id"], d) if d["genre"] == DEMANDE_AMORCER
                       else None)
    noms = noms_lisibles(conn, [d["demandeur"] for d in demandes if d["demandeur"]])
    for d in demandes:
        d["demandeur_nom"] = noms.get(d["demandeur"]) if d["demandeur"] else None
    return demandes


# --------------------------------------------------------------------------- #
# L'aperçu d'« en partir » (tranche 3b, E5, E6)
# --------------------------------------------------------------------------- #
@router.get("/api/albums/{album_id}/amorcer/apercu")
def apercu_d_amorce(album_id: int, collection: int, cran: str,
                    conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Ce qu'« en partir » de cette copie ferait, AVANT de le faire : une copie amorcée
    jusqu'au `cran` dit, rangée dans `collection` (E5, Hugo, 2026-10-20).

    `copies` : ce qui partirait, table par table — la même forme que la charge de la
    naissance (`database.compter_le_travail`, qui compte comme `copier_le_travail` copie).
    `laisses` : les tags et attributs qui RESTENT, parce que la collection d'arrivée ne les
    voit pas — leur NOMBRE seul, jamais leurs libellés, que l'appelant ne lit peut-être pas.
    `personnages` : les fiches de personnage que la copie rendrait lisibles depuis la
    collection d'arrivée (E6, une fuite écrite). Et ce que la prise répondrait : `fait`, ou
    `demande` avec `repondra` — sans rien écrire.

    Les gardes de la prise : 404 sur une copie qu'on ne lit pas et sur une collection où
    l'on n'écrit pas ; 422 nommé sur un cran hors de l'échelle ; 409 nommé sur une copie
    d'un autre projet, hors portée totale (entre deux projets, en partir se demande par le
    responsable, sans nommer la source — E7)."""
    cran = _cran_d_amorce(cran)
    a = _get_album(conn, portee, album_id)
    arrivee = collection_row(conn, collection)
    if arrivee is None or not portee.peut_ecrire(collection):
        raise HTTPException(404, f"Collection {collection} introuvable")
    projet_id = projet_de_collection(conn, collection)
    copies = _copies_du_document(conn, a["document_id"])
    source, refus = _source_d_amorce(conn, portee, copies, {album_id}, projet_id, album_id)
    if refus:
        raise HTTPException(409, refus)
    isoles = _projets_isoles(conn)
    if source["projet_id"] != projet_id and (source["projet_id"] in isoles["tous"]
                                             or projet_id in isoles["bacs"]):
        # COL-4 (S3), pour toute portée — et le refus nomme le jeu pour sa référence.
        jeu = isoles["tous"] - set(isoles["bacs"])
        raise HTTPException(409, _MOTIF_JEU_SOURCE if source["projet_id"] in jeu
                            else _MOTIF_BAC_ISOLE)
    ou, params = portee.clause_rejoindre_directe("a.id")
    directe = conn.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ou}",
                           (album_id, *params)).fetchone() is not None
    rendu = {"album_id": album_id, "collection_id": collection, "cran": cran,
             **compter_le_travail(conn, album_id, cran, collection),
             "etat": FAIT if directe else DEMANDE}
    if not directe:
        rendu["repondra"] = ("proprietaire"
                             if un_proprietaire_tient_toute_la_copie(conn, album_id)
                             else "administrateur")
    return rendu
