"""Annulation (undo) des actions d'annotation (D1) — adossée au journal A3.

Le journal `evenement` (append-only, `avant`/`apres`, instantané PROFOND à la suppression,
`cible_id` qui survit à la cible) EST l'historique : on n'ajoute pas de pile, on le REMONTE.

Modèle de pile, sans jamais mettre à jour un événement (append-only préservé) : annuler un
acte = exécuter son INVERSE + journaliser un événement `annulation` (`cible_table='evenement'`,
`cible_id` = l'acte annulé). La « dernière action annulable » est l'événement HUMAIN le plus
récent, d'un type annulable, dont l'id n'est PAS déjà référencé par une annulation → Ctrl+Z
répété remonte l'historique. Pas de redo dans ce cran (le redo = annuler une annulation).

Les inversions font des mutations BRUTES (+ réindex FTS) sans repasser par les routes, sinon
elles rejournaliseraient (bruit + boucle). Un seul événement `annulation` est ajouté par undo.
Périmètre : régions (créer/modifier/supprimer+cascade), annotations (note+tags), locuteur,
présence. Hors périmètre (pour l'instant) : correction grammaticale, validation.
Cf. `docs/undo.md`.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Optional

import journal
from database import reindex_region, unindex_region

# Types d'événements et tables que l'undo sait inverser (le reste est ignoré : ni annulé,
# ni bloquant — l'undo « saute » un acte non annulable et remonte au précédent).
_TYPES = ("creation", "modification", "suppression", "lien", "delien")
_TABLES = ("regions", "annotations", "bulle_locuteur", "personnage_presence")
_LIENS = ("bulle_locuteur", "personnage_presence")   # tables lien région→personnage (region_id UNIQUE)

_DESCRIPTIONS = {
    ("creation", "regions"): "création d'une région",
    ("modification", "regions"): "modification d'une région",
    ("suppression", "regions"): "suppression d'une région",
    ("creation", "annotations"): "ajout d'une annotation",
    ("modification", "annotations"): "modification d'une annotation",
    ("suppression", "annotations"): "suppression d'une annotation",
    ("lien", "bulle_locuteur"): "attribution d'un locuteur",
    ("delien", "bulle_locuteur"): "retrait d'un locuteur",
    ("lien", "personnage_presence"): "attribution d'une présence",
    ("delien", "personnage_presence"): "retrait d'une présence",
}


class UndoImpossible(Exception):
    """L'inverse ne peut pas s'appliquer (p. ex. identifiant réattribué, entité disparue)."""


def _description(e) -> str:
    return _DESCRIPTIONS.get((e["type"], e["cible_table"]), f"{e['type']} {e['cible_table']}")


def _charge(champ) -> Optional[dict]:
    return json.loads(champ) if champ else None


# --------------------------------------------------------------------------- #
# Sélection : la dernière action annulable (non déjà annulée)
# --------------------------------------------------------------------------- #
# Sentinelle : « ne filtre pas par agent ». `agent=None` veut dire tout autre chose —
# l'agent ANONYME, celui du mono-poste, qui est une valeur légitime en base.
TOUS = object()


def derniere_action_annulable(conn: sqlite3.Connection, agent=TOUS):
    """Événement HUMAIN le plus récent, d'un type/table annulable, non encore annulé
    (aucun événement `annulation` ne le référence). None si rien à annuler.

    `agent` restreint aux actes de CETTE personne (AUTH-2). Ctrl+Z est un geste personnel :
    annuler l'acte d'un collègue à son insu serait une surprise, pas une fonctionnalité.

    Et c'est le seul filtre possible ici. Scoper par collection reviendrait à remonter de
    l'événement à sa région, puis à son album — or l'acte le plus important à pouvoir
    annuler est justement une SUPPRESSION, dont la cible n'existe plus. Le journal survit à
    sa cible (`cible_id` n'est pas une FK) ; un filtre par album rendrait donc l'annulation
    d'une suppression impossible, c'est-à-dire l'inverse du service rendu.
    """
    ou, params = "", []
    if agent is not TOUS:
        ou = "  AND agent IS ? "                # `IS` et non `=` : gère l'agent NULL
        params = [agent]
    return conn.execute(
        f"SELECT * FROM evenement "
        f"WHERE agent_type = 'humain' "
        f"  AND type IN ({','.join('?' * len(_TYPES))}) "
        f"  AND cible_table IN ({','.join('?' * len(_TABLES))}) "
        f"{ou}"
        f"  AND id NOT IN (SELECT cible_id FROM evenement "
        f"                 WHERE type = 'annulation' AND cible_table = 'evenement' "
        f"                   AND cible_id IS NOT NULL) "
        f"ORDER BY id DESC LIMIT 1",
        (*_TYPES, *_TABLES, *params)).fetchone()


def apercu(conn: sqlite3.Connection, agent=TOUS) -> Optional[dict]:
    """Ce que ferait la prochaine annulation (sans l'exécuter) : {evenement_id, description}."""
    e = derniere_action_annulable(conn, agent)
    return {"evenement_id": e["id"], "description": _description(e)} if e else None


# --------------------------------------------------------------------------- #
# Inversions élémentaires (mutations brutes + réindex ; PAS de journalisation ici)
# --------------------------------------------------------------------------- #
def _descendants(conn, region_id):
    return [r["id"] for r in conn.execute(
        "WITH RECURSIVE d(id) AS (SELECT id FROM regions WHERE id = ? "
        "UNION SELECT r.id FROM regions r JOIN d ON r.parent_id = d.id) SELECT id FROM d",
        (region_id,))]


def _supprimer_region(conn, region_id):
    """Inverse d'une CRÉATION de région : supprime la région et son sous-arbre (cascade)."""
    for rid in _descendants(conn, region_id):
        unindex_region(conn, rid)
    conn.execute("DELETE FROM regions WHERE id = ?", (region_id,))


def _restaurer_region_cols(conn, region_id, avant):
    """Inverse d'une MODIFICATION de région : réécrit les colonnes métier depuis `avant`."""
    cols = ", ".join(f"{c} = ?" for c in journal._REGION_COLS)
    conn.execute(f"UPDATE regions SET {cols} WHERE id = ?",
                 (*[avant[c] for c in journal._REGION_COLS], region_id))
    reindex_region(conn, region_id)


def _ensure_tag(conn, label) -> int:
    row = conn.execute("SELECT id FROM tags WHERE label = ?", (label,)).fetchone()
    if row:
        return row["id"]
    return conn.execute("INSERT INTO tags (label) VALUES (?)", (label,)).lastrowid


def _restaurer_annotation(conn, region_id, annot):
    """(Re)pose une annotation {note, tags} sur une région (upsert) + réindexe."""
    conn.execute("INSERT INTO annotations (region_id, note) VALUES (?, ?) "
                 "ON CONFLICT(region_id) DO UPDATE SET note = excluded.note",
                 (region_id, annot.get("note")))
    ann_id = conn.execute("SELECT id FROM annotations WHERE region_id = ?",
                          (region_id,)).fetchone()["id"]
    conn.execute("DELETE FROM annotation_tags WHERE annotation_id = ?", (ann_id,))
    for label in annot.get("tags", []):
        conn.execute("INSERT OR IGNORE INTO annotation_tags (annotation_id, tag_id) "
                     "VALUES (?, ?)", (ann_id, _ensure_tag(conn, label)))
    reindex_region(conn, region_id)


def _supprimer_annotation(conn, region_id):
    conn.execute("DELETE FROM annotations WHERE region_id = ?", (region_id,))   # cascade tags
    reindex_region(conn, region_id)


def _recreer_region_profond(conn, snap):
    """Inverse d'une SUPPRESSION : recrée la région, son annotation et son sous-arbre depuis
    l'instantané PROFOND. Réutilise les `id` d'origine (préserve citations / deep-links) ;
    parent créé avant enfants (FK). Lève UndoImpossible si un id a été réattribué depuis."""
    cols = ["id", *journal._REGION_COLS]
    try:
        conn.execute(
            f"INSERT INTO regions ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            (snap["id"], *[snap.get(c) for c in journal._REGION_COLS]))
    except sqlite3.IntegrityError as exc:
        raise UndoImpossible(
            f"identifiant de région {snap['id']} réattribué depuis la suppression") from exc
    annot = snap.get("annotation")
    if annot is not None:
        _restaurer_annotation(conn, snap["id"], annot)
    else:
        reindex_region(conn, snap["id"])
    for enfant in snap.get("enfants", []):
        _recreer_region_profond(conn, enfant)


def _poser_lien(conn, table, region_id, personnage_id):
    conn.execute(f"INSERT INTO {table} (region_id, personnage_id) VALUES (?, ?) "
                 f"ON CONFLICT(region_id) DO UPDATE SET personnage_id = excluded.personnage_id",
                 (region_id, personnage_id))


def _retirer_lien(conn, table, region_id):
    conn.execute(f"DELETE FROM {table} WHERE region_id = ?", (region_id,))


# --------------------------------------------------------------------------- #
# Aiguillage + orchestration
# --------------------------------------------------------------------------- #
def _inverser(conn, e) -> int:
    """Applique l'inverse de l'événement `e` et renvoie la région concernée (pour l'UI).

    Toute violation de contrainte (FK d'un personnage supprimé entre-temps, id réattribué…)
    devient un UndoImpossible → 409 explicite, jamais un 500. `_recreer_region_profond` capte
    déjà `IntegrityError` en amont pour un message dédié (id réattribué)."""
    t, table, cid = e["type"], e["cible_table"], e["cible_id"]
    avant, apres = _charge(e["avant"]), _charge(e["apres"])
    try:
        if table == "regions":
            if t == "creation":
                _supprimer_region(conn, cid)
            elif t == "modification":
                _restaurer_region_cols(conn, cid, avant)
            elif t == "suppression":
                _recreer_region_profond(conn, avant)
            return cid
        if table == "annotations":        # cible_id = region_id (v20 : stable, cf. put_annotation)
            if t == "creation":
                _supprimer_annotation(conn, cid)
            else:                         # modification / suppression → restaurer `avant`
                _restaurer_annotation(conn, cid, avant)
            return cid
        if table in _LIENS:                # cible_id = region_id
            if t == "lien" and avant is None:
                _retirer_lien(conn, table, cid)
            else:                         # lien (avec avant) ou delien → rétablir l'ancien lien
                _poser_lien(conn, table, cid, avant["personnage_id"])
            return cid
    except sqlite3.IntegrityError as exc:  # entité référencée disparue, contrainte violée…
        raise UndoImpossible(str(exc)) from exc
    raise UndoImpossible(f"acte non inversible : {t}/{table}")


def _planche_de(conn, region_id, e) -> Optional[int]:
    """Planche de la région concernée (pour rafraîchir l'UI) : lue en base si la région
    existe encore, sinon depuis l'instantané de l'événement (cas d'une création annulée)."""
    row = conn.execute("SELECT planche_id FROM regions WHERE id = ?", (region_id,)).fetchone()
    if row:
        return row["planche_id"]
    snap = _charge(e["apres"]) or _charge(e["avant"]) or {}
    return snap.get("planche_id")


def annuler(conn: sqlite3.Connection, evenement_id: Optional[int] = None,
            agent=TOUS) -> Optional[dict]:
    """Annule la dernière action (ou l'événement `evenement_id`) : exécute l'inverse puis
    journalise un événement `annulation`. Renvoie un descripteur {description, planche_id,
    region_id, …} pour le rafraîchissement UI, ou None s'il n'y a rien à annuler. NE COMMITE
    PAS (la route commite → inversion + journal atomiques ; rollback en cas d'échec)."""
    if evenement_id is None:
        e = derniere_action_annulable(conn, agent)
    else:
        e = conn.execute("SELECT * FROM evenement WHERE id = ?", (evenement_id,)).fetchone()
        # Viser un événement par son id ne contourne pas la règle : on n'annule que le sien.
        if e is not None and agent is not TOUS and e["agent"] != agent:
            e = None
    if e is None:
        return None
    region_id = _inverser(conn, e)
    planche_id = _planche_de(conn, region_id, e)
    journal.journaliser(conn, "annulation", "evenement", e["id"],
                        avant={"acte": e["type"], "cible_table": e["cible_table"],
                               "cible_id": e["cible_id"]})
    return {"evenement_id": e["id"], "acte": e["type"], "cible_table": e["cible_table"],
            "region_id": region_id, "planche_id": planche_id, "description": _description(e)}
