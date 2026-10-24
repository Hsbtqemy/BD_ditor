"""Mon bac à sable (COL-4) — un projet à soi, rempli d'un jeu, effacé chaque lundi.

Un clic crée, pour CE compte, un projet dont il est le seul responsable, rempli d'une copie
de chaque document du jeu (`jeu_document`, préparé par `tools/preparer_jeu.py`) ; recliquer
y ramène. Le propriétaire peut le remettre à neuf, y faire entrer des collègues au rôle de
membre (`PUT /api/projets/{id}/membres`, borné dans `routes/projets.py`), et il part avec
tous les autres le lundi à 4 h, heure de Paris, sans exception (Hugo, 2026-10-22).

**Une exception écrite, et une seule** : aujourd'hui seule une portée totale décide quels
projets existent (`peut_decider_des_projets`). Ouvrir son bac à sable n'élargit pas cette
question — elle garde son sens —, il en pose une NEUVE, `peut_ouvrir_un_bac_a_sable` : un
login, derrière le proxy. Un compte PARTAGÉ en a un comme les autres, avec tous ses gestes,
« Remettre à neuf » compris, et s'y fait inviter (Hugo, 2026-10-24, qui renverse S1 du
cadrage) : « C'est un bac à sable, fait pour itérer, essayer, recommencer, effacer. Le
travail produit n'y a aucune valeur, d'autant qu'on ne peut pas exporter. » Aucune garde du
bac à sable ne lit la nature d'un compte.

Ce que la responsabilité d'un bac à sable NE donne PAS ailleurs — les notices du fonds, le
vocabulaire et les personnages globaux, l'annuaire, le bandeau de portée vide — est tenu
dans `autorisation.Portee` (S2 du cadrage) ; ce qui n'en sort pas et n'y entre pas (S3), par
la nature du projet, dans les routes du fonds, des demandes et du rangement.

Ce module APPLIQUE ; `autorisation.py` tranche, `socle.py` crée et efface.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

import autorisation
import conflit
from config import BAC_A_SABLE_PLAFOND_PLANCHES
from database import ROLES_JEU, collection_de_base
from pipeline import nlp

from socle import (_creer_bac_a_sable, _effacer_bac_a_sable, _planches_importees_du_bac,
                   _sortir_du_bac, db, portee_courante)

router = APIRouter()

NOM_AFFICHE_MIEN = "Mon bac à sable"

_MOTIF_OUVRIR = ("Un bac à sable s'ouvre pour un compte nommé, derrière l'authentification : "
                 "aucune identité ne parvient à l'application pour cette requête.")


def _exiger_d_ouvrir(conn, portee: autorisation.Portee) -> None:
    """403 nommé : il parle de l'appelant, jamais d'un objet."""
    if not peut_ouvrir(conn, portee):
        raise HTTPException(403, _MOTIF_OUVRIR)


def peut_ouvrir(conn, portee: autorisation.Portee) -> bool:
    """La même question que `_exiger_d_ouvrir`, en booléen : l'écran n'offre « Mon bac à
    sable » qu'à qui le serveur l'ouvrirait (`GET /api/moi`, `bac_a_sable_ouvrable`). Un
    `null` de `GET /api/bac-a-sable` ne le dit pas : il vaut aussi pour qui n'en a pas. Un
    compte partagé y répond oui, comme tout login (Hugo, 2026-10-24)."""
    return portee.peut_ouvrir_un_bac_a_sable()


def _mien(conn, login):
    """Le bac à sable de ce login, ou None. Un par login, tenu sous le verrou d'écriture."""
    if not login:
        return None
    r = conn.execute("SELECT * FROM projet WHERE bac_a_sable_de = ? ORDER BY id LIMIT 1",
                     (login,)).fetchone()
    return dict(r) if r else None


def _carte_du_jeu(conn, projet_id: int) -> list[dict]:
    """Ce que le jeu a posé dans ce bac à sable — S10 du cadrage, la place du wizard (lot
    4) : une entrée par copie d'un document du jeu, son rôle, son rang, son cran, l'album et
    ses planches. Lue par `copie.depuis_album_id` = la référence. Un document retiré du jeu
    depuis la naissance du bac à sable n'y est plus, sa copie restant dans le projet."""
    lignes = [dict(r) for r in conn.execute(
        "SELECT jd.role, jd.rang, jd.cran, jd.document_id, jd.exportable, a.id AS album_id, "
        "a.titre FROM jeu_document jd JOIN copie c ON c.depuis_album_id = jd.album_reference "
        "JOIN albums a ON a.id = c.album_id AND a.document_id = jd.document_id "
        "WHERE a.projet_id = ? ORDER BY jd.rang, a.id", (projet_id,))]
    for ligne in lignes:
        ligne["exportable"] = bool(ligne["exportable"])
        ligne["planche_ids"] = [r[0] for r in conn.execute(
            "SELECT id FROM planches WHERE album_id = ? ORDER BY numero", (ligne["album_id"],))]
    return sorted(lignes, key=lambda x: (ROLES_JEU.index(x["role"])
                                         if x["role"] in ROLES_JEU else len(ROLES_JEU),
                                         x["rang"], x["album_id"]))


def _vue(conn, p: dict) -> dict:
    """Ce que rend la route : rien qui nomme une personne (`mien` va de soi ici)."""
    base = collection_de_base(conn, p["id"])
    nom_base = None if base is None else conn.execute(
        "SELECT nom FROM collection WHERE id = ?", (base,)).fetchone()[0]
    return {"id": p["id"], "nom": NOM_AFFICHE_MIEN, "efface_le": p["efface_le"],
            "date_creation": p["date_creation"],
            "base": None if base is None else {"id": base, "nom": nom_base},
            "jeu": _carte_du_jeu(conn, p["id"]),
            "planches_importees": _planches_importees_du_bac(conn, p["id"]),
            "plafond_planches": BAC_A_SABLE_PLAFOND_PLANCHES}


@router.get("/api/bac-a-sable")
def lire_mon_bac_a_sable(conn: sqlite3.Connection = Depends(db),
                         portee: autorisation.Portee = Depends(portee_courante)):
    """Mon bac à sable — son identifiant, la date de son effacement (UTC), sa collection de
    base, la carte du jeu posé —, ou `null` si je n'en ai pas (ou si personne ne s'annonce :
    le mono-poste n'a pas de « mien »). Rien d'un bac à sable où l'on est seulement invité :
    celui-là se lit dans `GET /api/projets`."""
    if not portee.peut_ouvrir_un_bac_a_sable():
        return None
    p = _mien(conn, portee.utilisateur)
    return None if p is None else _vue(conn, p)


def _jeu_a_un_travail(conn) -> bool:
    return conn.execute("SELECT 1 FROM jeu_document WHERE cran <> 'images' "
                        "LIMIT 1").fetchone() is not None


@router.post("/api/bac-a-sable", status_code=201)
def ouvrir_mon_bac_a_sable(response: Response, conn: sqlite3.Connection = Depends(db),
                           portee: autorisation.Portee = Depends(portee_courante)):
    """Ouvre MON bac à sable, ou y ramène : 201 et le bac à sable créé, 200 et le même s'il
    existe déjà — le bouton est « y aller », idempotent. Un par login, relu sous le verrou
    d'écriture : deux clics simultanés n'en créent pas deux.

    403 nommé sans identité (mono-poste compris) ; un compte partagé en ouvre un."""
    _exiger_d_ouvrir(conn, portee)
    # Une copie au-dessus du cran `images` recopie l'index des régions : spaCy se charge
    # HORS de la transaction d'écriture (CLAUDE.md § Concurrence), comme pour la prise.
    if _jeu_a_un_travail(conn):
        nlp.ensure_loaded()
    conflit.verrouiller(conn)
    p = _mien(conn, portee.utilisateur)
    if p is not None:
        conn.rollback()
        response.status_code = 200
        return _vue(conn, p)
    if not _naitre_sous_le_verrou(conn, portee.utilisateur):
        response.status_code = 200
    return _vue(conn, _mien(conn, portee.utilisateur))


def _naitre_sous_le_verrou(conn, login: str) -> bool:
    """Fait naître le bac à sable de `login`, le verrou d'écriture TENU et l'absence RELUE
    par l'appelant ; commite. L'index unique partiel (`idx_projet_bac_a_sable_de`) est le
    dernier mot : s'il refuse — un autre chemin a créé le sien sans le verrou —, rien n'est
    écrit et le sien est rendu. Rend True si le bac à sable est né ici."""
    try:
        _creer_bac_a_sable(conn, login)
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        if _mien(conn, login) is None:
            raise
        return False


@router.post("/api/bac-a-sable/{projet_id}/quitter", status_code=204)
def quitter_un_bac_a_sable(projet_id: int, conn: sqlite3.Connection = Depends(db),
                           portee: autorisation.Portee = Depends(portee_courante)):
    """QUITTER de soi-même le bac à sable où l'on est invité (Hugo, 2026-10-24). On y perd
    tout ce qu'on y tenait, la propriété des collections qu'on y a créées comprise
    (`socle._sortir_du_bac`) ; rien n'est détruit, et le journal garde son travail.

    404 si l'on n'y est pas invité — un bac à sable qu'on ne voit pas, ou qui n'en est pas
    un : la même réponse, rien n'en fuit. 409 nommé à son propriétaire : le sien ne se
    quitte pas, il se remet à neuf. Un invité l'est par son LOGIN (S11 : on n'invite pas un
    groupe) ; c'est cette ligne-là qui part."""
    if not portee.utilisateur:
        raise HTTPException(403, _MOTIF_OUVRIR)
    conflit.verrouiller(conn)
    p = conn.execute("SELECT bac_a_sable_de FROM projet WHERE id = ? "
                     "AND bac_a_sable_de IS NOT NULL", (projet_id,)).fetchone()
    if p is not None and p[0] == portee.utilisateur:
        conn.rollback()
        raise HTTPException(409, "C'est votre bac à sable : il ne se quitte pas, il se "
                                 "remet à neuf.")
    if p is None or not _sortir_du_bac(conn, projet_id, autorisation.UTILISATEUR,
                                       portee.utilisateur):
        conn.rollback()
        raise HTTPException(404, f"Projet {projet_id} introuvable")
    conn.commit()
    return Response(status_code=204)


@router.post("/api/bac-a-sable/remise-a-neuf")
def remettre_a_neuf(conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Remet MON bac à sable à son jeu de départ : tout ce qui y a été fait part — le
    travail des invités aussi —, et un bac à sable neuf naît, avec une date d'effacement
    neuve. Au propriétaire seul : on ne remet à neuf que le sien (404 nommé si l'on n'en a
    pas). Les albums partent un par un (`socle._detruire_album` commite par album) : un arrêt
    au milieu laisse un bac à sable à moitié effacé, qu'une nouvelle remise à neuf finit."""
    _exiger_d_ouvrir(conn, portee)
    p = _mien(conn, portee.utilisateur)
    if p is None:
        raise HTTPException(404, "Vous n'avez pas de bac à sable à remettre à neuf.")
    if _jeu_a_un_travail(conn):
        nlp.ensure_loaded()
    _effacer_bac_a_sable(conn, portee, p["id"], motif="remise à neuf")
    # Relu SOUS le verrou (relecture croisée) : un clic sur « Mon bac à sable », arrivé
    # entre l'effacement et la création, en a peut-être déjà fait naître un neuf — c'est
    # lui qu'on rend, sans en créer un second.
    conflit.verrouiller(conn)
    if _mien(conn, portee.utilisateur) is not None:
        conn.rollback()
    else:
        _naitre_sous_le_verrou(conn, portee.utilisateur)
    return _vue(conn, _mien(conn, portee.utilisateur))
