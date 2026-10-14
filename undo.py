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
Sous un compte COLLECTIF (AUTH-6), seuls les actes récents : `DELAI_COLLECTIF_MINUTES`.
Cf. `docs/undo.md`.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Optional

import conflit
import journal
from database import NATURE_COLLECTIF, reindex_region, unindex_region

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


# AUTH-14 — la phrase que l'écran montre quand Ctrl+Z passe un acte. UNE pour tous les
# cas (région disparue, identifiant repris ailleurs, collection qu'on n'écrit plus) :
# deux phrases diraient à qui ne lit plus la planche si la région a été supprimée ou si
# elle vit encore hors de sa portée — exactement ce que le 404 garde ailleurs.
PHRASE_NE_S_ANNULE_PLUS = "Ne s'annule plus : {description} — la région n'est plus à votre portée."
# La seconde, pour un acte dont l'objet est bien à portée, mais dont l'état d'avant n'a plus
# où se poser : un parent disparu ou qui ferait un cycle, un personnage supprimé. L'agent
# écrit la région : la phrase ne lui apprend rien qu'il ne puisse lire.
PHRASE_IRRETABLISSABLE = ("Ne s'annule plus : {description} — "
                          "l'état d'avant ne peut plus être rétabli.")


class NeSAnnulePlus(Exception):
    """L'acte ne s'annule plus : ce qu'il a touché n'est plus l'objet sur lequel il a
    porté, ou plus un objet que l'agent peut écrire. La route le PASSE (`ecarter`) au lieu
    de bloquer la pile. Le message ne dit rien de l'objet présent, qu'on ne lit peut-être
    pas."""

    def __init__(self, e, phrase: str = PHRASE_NE_S_ANNULE_PLUS):
        self.evenement = e
        self.description = _description(e)
        super().__init__(phrase.format(description=self.description))


class Irretablissable(Exception):
    """Levée PENDANT l'inversion : l'état d'avant n'a plus où se poser. `annuler` la change
    en `NeSAnnulePlus` (seconde phrase) ; la route défait ce qui aurait été écrit."""


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

# AUTH-6 — sous un compte COLLECTIF, Ctrl+Z ne remonte que les actes RÉCENTS. Un login
# partagé est tenu par plusieurs personnes, en même temps ou tour à tour, et le filtre par
# agent ne sépare plus « mes actes » de « ceux du collègue sous le même login » :
# l'application ne voit que `Remote-User`, et ne doit pas fabriquer d'identité (AUTH-1).
# Le TEMPS et non la session, parce qu'elle n'a aucune notion de session — et parce que le
# vrai risque est de défaire ce qu'un autre a fait avant la pause, pas il y a trente
# secondes. Cinq minutes, tranché par l'équipe le 2026-09-11 : le plus sûr des délais
# proposés.
DELAI_COLLECTIF_MINUTES = 5


def _borne(conn: sqlite3.Connection, agent) -> Optional[str]:
    """Date du journal (UTC, `datetime('now')`) avant laquelle un acte n'est plus annulable
    par cet agent — ou None s'il n'y a pas de borne : compte nominatif, agent anonyme,
    mono-poste. La nature se lit dans `utilisateur`, à UN endroit (`database.NATURES`) ; un
    login que la table ne connaît pas est nominatif, comme le défaut de la colonne."""
    if agent is TOUS or agent is None:
        return None
    row = conn.execute("SELECT nature FROM utilisateur WHERE login = ?", (agent,)).fetchone()
    if row is None or row["nature"] != NATURE_COLLECTIF:
        return None
    return conn.execute("SELECT datetime('now', ?)",
                        (f"-{DELAI_COLLECTIF_MINUTES} minutes",)).fetchone()[0]


def est_borne(conn: sqlite3.Connection, agent) -> bool:
    """L'annulation de cet agent est-elle bornée dans le temps ? La route s'en sert pour
    dire POURQUOI il n'y a rien à annuler, sans recalculer la règle."""
    return _borne(conn, agent) is not None


def derniere_action_annulable(conn: sqlite3.Connection, agent=TOUS):
    """Événement HUMAIN le plus récent, d'un type/table annulable, non encore annulé
    (aucun événement `annulation` ne le référence). None si rien à annuler.

    `agent` restreint aux actes de CETTE personne (AUTH-2). Ctrl+Z est un geste personnel :
    annuler l'acte d'un collègue à son insu serait une surprise, pas une fonctionnalité.
    Sous un compte collectif, l'agent ne désigne plus une personne : la recherche s'arrête
    donc aux `DELAI_COLLECTIF_MINUTES` dernières minutes (AUTH-6).

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
    borne = _borne(conn, agent)
    if borne is not None:
        ou += "  AND date >= ? "                # même format que la colonne : comparaison de chaînes
        params.append(borne)
    # Hors de la pile : ce qui a été annulé, et ce que Ctrl+Z a PASSÉ (AUTH-14) — sans
    # quoi un acte qui ne s'annule plus revenait à chaque Ctrl+Z, indéfiniment.
    return conn.execute(
        f"SELECT * FROM evenement "
        f"WHERE agent_type = 'humain' "
        f"  AND type IN ({','.join('?' * len(_TYPES))}) "
        f"  AND cible_table IN ({','.join('?' * len(_TABLES))}) "
        f"{ou}"
        f"  AND id NOT IN (SELECT cible_id FROM evenement "
        f"                 WHERE ((type = 'annulation' AND cible_table = 'evenement') "
        f"                     OR (type = 'abandon' AND cible_table = 'annulation')) "
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


# CONC-3 (Q4) — colonnes qu'une annulation remet sans garde. L'ordre se recalcule à chaque
# passe et à chaque ajout ; la source suit la retouche ; la planche ne change jamais.
_SANS_GARDE = ("ordre", "source", "planche_id")


def _garder_creation(conn, region_id, apres):
    """Refuse d'annuler la création d'une région que QUELQU'UN D'AUTRE a travaillée depuis.

    Supprimer la région emporterait ce travail sans instantané : l'annulation est une
    mutation brute, qui ne journalise que l'acte `annulation`. Ses propres gestes plus récents
    sont annulés AVANT celui-ci, si bien que ce qui reste ici vient d'un autre.
    """
    actuel = journal.snapshot_region(conn, region_id)
    if actuel is None:
        return
    for c in journal._REGION_COLS:
        if c not in _SANS_GARDE and not conflit.egal(actuel.get(c), (apres or {}).get(c)):
            raise conflit.Perime("regions", region_id, c, actuel.get(c),
                                 conflit.auteur_du_champ(conn, "regions", region_id, c,
                                                         actuel.get(c)))
    if journal.snapshot_annotation(conn, region_id) is not None:
        e = conn.execute("SELECT * FROM evenement WHERE cible_table = 'annotations' "
                         "AND cible_id = ? ORDER BY id DESC LIMIT 1", (region_id,)).fetchone()
        raise conflit.Perime("annotations", region_id, "annotation", None,
                             conflit.auteur(conn, e) if e else None)
    enfant = conn.execute("SELECT id FROM regions WHERE parent_id = ? ORDER BY id DESC LIMIT 1",
                          (region_id,)).fetchone()
    if enfant is not None:
        e = conn.execute("SELECT * FROM evenement WHERE cible_table = 'regions' AND "
                         "type = 'creation' AND cible_id = ? ORDER BY id DESC LIMIT 1",
                         (enfant["id"],)).fetchone()
        raise conflit.Perime("regions", region_id, "enfants", None,
                             conflit.auteur(conn, e) if e else None)


def _supprimer_region(conn, region_id):
    """Inverse d'une CRÉATION de région : supprime la région et son sous-arbre (cascade)."""
    for rid in _descendants(conn, region_id):
        unindex_region(conn, rid)
    conn.execute("DELETE FROM regions WHERE id = ?", (region_id,))


def _inverser_modification_region(conn, region_id, avant, apres):
    """Inverse d'une MODIFICATION de région : défait CE QUE l'acte a changé, rien d'autre.

    CONC-3 (Q4) — lu le 2026-09-17 et vu rouge sur le code d'avant : toutes les colonnes
    étaient réécrites depuis `avant`. A déplaçait la bulle, B la transcrivait, A faisait
    Ctrl+Z, et le texte de B disparaissait avec le déplacement. Seules les colonnes que l'acte
    a changées reviennent désormais, et l'annulation est REFUSÉE si l'une d'elles a changé
    depuis (sauf par un moteur, Q2) : sinon Ctrl+Z écraserait le geste d'un autre.
    """
    avant, apres = avant or {}, apres or {}
    actuel = conn.execute("SELECT * FROM regions WHERE id = ?", (region_id,)).fetchone()
    if actuel is None:
        raise UndoImpossible("la région n'existe plus")
    changees = [c for c in journal._REGION_COLS if not conflit.egal(avant.get(c), apres.get(c))]
    # AUTH-14 — le parent qu'on rend se valide comme la route le valide (`_validate_parent`) :
    # présent, dans la MÊME planche, sans cycle. Sans quoi Ctrl+Z rattachait une bulle à une
    # case d'une autre collection (relecture croisée, S1).
    if "parent_id" in changees and avant.get("parent_id") is not None \
            and not _parent_valide(conn, region_id, avant["parent_id"], actuel["planche_id"]):
        raise Irretablissable()
    for c in changees:
        if c not in _SANS_GARDE:
            conflit.verifier(conn, "regions", region_id, c, vu=apres.get(c),
                             actuel=actuel[c], nouveau=avant.get(c))
    if changees:
        conn.execute(f"UPDATE regions SET {', '.join(f'{c} = ?' for c in changees)} "
                     "WHERE id = ?", (*[avant.get(c) for c in changees], region_id))
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


def _inverser_annotation(conn, region_id, avant, apres):
    """Défait CE QUE l'acte a changé, et rien d'autre (CONC-3).

    Restaurer l'instantané `avant` entier défaisait aussi ce qu'une autre personne avait fait
    sur l'AUTRE champ entre-temps : annuler une note rendait la liste de tags d'avant, donc
    effaçait le tag posé par un collègue. L'inverse se calcule donc par différence, sur l'état
    ACTUEL : la note revient à sa valeur d'avant si l'acte l'a changée ; les tags que l'acte
    a ajoutés sont retirés, ceux qu'il a retirés sont remis, les autres ne bougent pas. Tant
    que personne d'autre n'a touché l'annotation, c'est exactement l'instantané `avant`.
    """
    avant, apres = avant or {}, apres or {}
    actuel = journal.snapshot_annotation(conn, region_id) or {}
    note = actuel.get("note")
    if (avant.get("note") or "") != (apres.get("note") or ""):
        # Second temps (Q4) : si la note a changé depuis l'acte, la rendre écraserait celle
        # écrite ensuite par un autre. Les tags n'ont pas de garde : ils vont par différence.
        conflit.verifier(conn, "annotations", region_id, "note", vu=apres.get("note"),
                         actuel=actuel.get("note"), nouveau=avant.get("note"))
        note = avant.get("note")
    t_avant, t_apres = set(avant.get("tags", [])), set(apres.get("tags", []))
    tags = (set(actuel.get("tags", [])) - (t_apres - t_avant)) | (t_avant - t_apres)
    if not (note or "").strip() and not tags:
        _supprimer_annotation(conn, region_id)
    else:
        _restaurer_annotation(conn, region_id, {"note": note, "tags": sorted(tags)})


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

    Toute violation de contrainte (FK d'un personnage supprimé entre-temps…) rend l'acte
    IRRÉTABLISSABLE : il est passé, jamais un 500 — et plus un 409 qui revenait à chaque
    Ctrl+Z (AUTH-14, relecture croisée S5). Le texte de l'erreur SQL ne sort plus.
    `_recreer_region_profond` capte `IntegrityError` en amont pour un message dédié (id
    réattribué), que `_meme_objet` rend inatteignable en vérifiant les ids d'abord."""
    t, table, cid = e["type"], e["cible_table"], e["cible_id"]
    avant, apres = _charge(e["avant"]), _charge(e["apres"])
    try:
        if table == "regions":
            if t == "creation":
                _garder_creation(conn, cid, apres)
                _supprimer_region(conn, cid)
            elif t == "modification":
                _inverser_modification_region(conn, cid, avant, apres)
            elif t == "suppression":
                _recreer_region_profond(conn, avant)
            return cid
        if table == "annotations":        # cible_id = region_id (v20 : stable, cf. put_annotation)
            _inverser_annotation(conn, cid, avant, apres)
            return cid
        if table in _LIENS:                # cible_id = region_id
            if t == "lien" and avant is None:
                _retirer_lien(conn, table, cid)
            else:                         # lien (avec avant) ou delien → rétablir l'ancien lien
                _poser_lien(conn, table, cid, avant["personnage_id"])
            return cid
    except sqlite3.IntegrityError as exc:  # entité référencée disparue, contrainte violée…
        raise Irretablissable() from exc
    raise UndoImpossible(f"acte non inversible : {t}/{table}")


def _planche_de(conn, region_id, e) -> Optional[int]:
    """Planche de la région concernée (pour rafraîchir l'UI) : lue en base si la région
    existe encore, sinon depuis l'instantané de l'événement (cas d'une création annulée)."""
    row = conn.execute("SELECT planche_id FROM regions WHERE id = ?", (region_id,)).fetchone()
    if row:
        return row["planche_id"]
    snap = _charge(e["apres"]) or _charge(e["avant"]) or {}
    return snap.get("planche_id")


# --------------------------------------------------------------------------- #
# AUTH-14 — l'acte porte-t-il encore sur le même objet, et où l'inverse écrirait-il ?
# --------------------------------------------------------------------------- #
# Les identifiants de `regions` et de `planches` se RÉATTRIBUENT (pas d'`AUTOINCREMENT`) :
# la région créée après la suppression de celle d'identifiant le plus haut reprend cet
# identifiant, dans n'importe quelle collection. Le `cible_id` d'un acte peut donc désigner,
# aujourd'hui, un objet que son auteur n'a jamais touché. Filtrer par agent ne dit rien de
# l'objet : Ctrl+Z effaçait un locuteur de l'Incubateur au nom d'une collègue qui n'y entre
# pas, et le 409 de CONC-3 lui rendait le texte de la région et le login de son auteur
# (mesuré sur 5311ccc). Deux questions, posées AVANT toute écriture : l'objet est-il le
# même (`_meme_objet`, ici, sans portée) ; l'agent peut-il l'écrire MAINTENANT (`ecrivable`,
# fourni par la route, qui tient les accesseurs gardés de `socle.py`).

def _noeuds(snap: dict):
    """Les nœuds d'un instantané profond : la région et tout son sous-arbre."""
    if snap:
        yield snap
    for enfant in (snap or {}).get("enfants", []):
        yield from _noeuds(enfant)


def _ids_instantane(snap: dict):
    """Les identifiants d'un instantané profond : la région et tout son sous-arbre."""
    for n in _noeuds(snap):
        if n.get("id") is not None:
            yield n["id"]


def _planches_instantane(snap: dict) -> list:
    """Les planches de TOUS les nœuds, et pas seulement de la racine : une base retouchée
    par une annulation d'avant ce correctif peut porter un enfant dans une autre planche
    que son parent — le rétablir écrirait là aussi (relecture croisée, S1)."""
    return sorted({n.get("planche_id") for n in _noeuds(snap)}, key=lambda x: (x is None, x))


def _parent_valide(conn, region_id, parent_id, planche_id) -> bool:
    """Ce que la route exige d'un parent (`socle._validate_parent`) : présent, dans la même
    planche, ni la région elle-même ni l'un de ses descendants."""
    r = conn.execute("SELECT planche_id FROM regions WHERE id = ?", (parent_id,)).fetchone()
    if r is None or r["planche_id"] != planche_id or parent_id == region_id:
        return False
    return parent_id not in set(_descendants(conn, region_id))


def _recreee_depuis(conn, region_id, e) -> bool:
    """Une région a-t-elle été CRÉÉE sous cet identifiant après l'acte `e` ?

    C'est le signe le plus sûr d'un identifiant repris : toute création par une route ou
    par une passe ML est journalisée. Rétablir une suppression ne l'est pas comme création
    — c'est le MÊME objet qui revient, sous le même identifiant, et il ne doit pas compter.
    Cas limite, fermé du côté sûr : une région reprise puis supprimée, et l'originale
    rétablie ensuite, passe pour reprise — Ctrl+Z refuse là où il aurait pu agir."""
    return conn.execute(
        "SELECT 1 FROM evenement WHERE cible_table = 'regions' AND type = 'creation' "
        "AND cible_id = ? AND id > ? LIMIT 1", (region_id, e["id"])).fetchone() is not None


def _supprimee_depuis(conn, region_id, e) -> bool:
    """Une suppression JOURNALISÉE de cette région — directe, ou par celle d'un ancêtre —
    est-elle postérieure à l'acte, sans avoir été annulée ? Alors l'objet de l'acte n'existe
    plus, quoi que porte aujourd'hui l'identifiant : c'est le témoin qui voit une reprise
    SANS événement de création dans un album plus ancien que l'acte (relecture croisée,
    S3). Une suppression annulée ne compte pas : son annulation a rendu le même objet.

    Le `LIKE` n'écarte que vite ; la décision se prend sur l'instantané relu, comme dans
    `conflit.suppression_de_region`, pour qu'un `"id": 12` ne réponde pas pour la 123."""
    for ev in conn.execute(
            "SELECT s.id, s.cible_id, s.avant FROM evenement s "
            "WHERE s.cible_table = 'regions' AND s.type = 'suppression' AND s.id > ? "
            "  AND (s.cible_id = ? OR s.avant LIKE ?) "
            "  AND NOT EXISTS (SELECT 1 FROM evenement a WHERE a.type = 'annulation' "
            "                  AND a.cible_table = 'evenement' AND a.cible_id = s.id)",
            (e["id"], region_id, f'%"id": {region_id}%')):
        if (ev["cible_id"] == region_id
                or region_id in set(_ids_instantane(_charge(ev["avant"]) or {}))):
            return True
    return False


def _planche_au_moment(conn, region_id, e) -> Optional[int]:
    """La planche où vivait la région au moment de l'acte, lue au journal — None s'il n'en
    dit rien. Un second témoin, pour les régions nées sans événement de création (la
    segmentation lancée à l'import depuis ShareDocs n'en écrit pas)."""
    for ev in conn.execute(
            "SELECT type, avant, apres FROM evenement WHERE cible_table = 'regions' "
            "AND cible_id = ? AND id <= ? ORDER BY id DESC", (region_id, e["id"])):
        if ev["type"] == "suppression":
            return None          # l'objet de l'acte est né après : le journal n'en sait rien
        for etat in (_charge(ev["apres"]), _charge(ev["avant"])):
            if etat and etat.get("planche_id") is not None:
                return etat["planche_id"]
    return None


def _album_ne_apres(conn, planche_id, e) -> bool:
    """La planche appartient-elle à un album importé APRÈS l'acte ? Alors elle n'est pas
    celle de l'acte. Les dates sont à la seconde : dans la même seconde, rien n'est vu."""
    row = conn.execute("SELECT a.date_import FROM planches p JOIN albums a "
                       "ON a.id = p.album_id WHERE p.id = ?", (planche_id,)).fetchone()
    return bool(row and row["date_import"] and e["date"] and row["date_import"] > e["date"])


def _meme_objet(conn, e) -> bool:
    """L'inverse de `e` porterait-il sur l'objet même que `e` a touché ?

    Pour une SUPPRESSION, l'objet est la place où la région reviendrait : ses identifiants
    libres, sa planche présente et née avant l'acte, son parent — s'il en a un — dans la
    même planche et jamais recréé depuis. Pour tout autre acte, la région présente sous
    `cible_id`, jamais recréée depuis, dans la planche où elle vivait. Une région absente
    n'est pas « la même » : l'inverse n'aurait rien sur quoi s'appliquer."""
    if e["type"] == "suppression" and e["cible_table"] == "regions":
        snap = _charge(e["avant"]) or {}
        ids = list(_ids_instantane(snap))
        if not ids or conn.execute(
                f"SELECT 1 FROM regions WHERE id IN ({','.join('?' * len(ids))}) LIMIT 1",
                ids).fetchone():
            return False
        for pl in _planches_instantane(snap):
            if conn.execute("SELECT 1 FROM planches WHERE id = ?", (pl,)).fetchone() is None:
                return False
            if _album_ne_apres(conn, pl, e):
                return False
        planche = snap.get("planche_id")
        parent = snap.get("parent_id")
        if parent is not None:
            r = conn.execute("SELECT planche_id FROM regions WHERE id = ?", (parent,)).fetchone()
            if (r is None or r["planche_id"] != planche
                    or _recreee_depuis(conn, parent, e)
                    or _supprimee_depuis(conn, parent, e)):
                return False
        return True
    rid = e["cible_id"]
    r = conn.execute("SELECT planche_id FROM regions WHERE id = ?", (rid,)).fetchone()
    if r is None or _recreee_depuis(conn, rid, e) or _supprimee_depuis(conn, rid, e):
        return False
    alors = _planche_au_moment(conn, rid, e)
    if alors is not None and alors != r["planche_id"]:
        return False
    if _album_ne_apres(conn, r["planche_id"], e):
        return False
    # Le parent que l'inverse rendrait est un objet lui aussi : repris ailleurs, il n'est
    # plus celui de l'acte. Absent, c'est l'inversion qui le dira (seconde phrase).
    avant, apres = _charge(e["avant"]) or {}, _charge(e["apres"]) or {}
    if e["cible_table"] == "regions" and e["type"] == "modification" \
            and avant.get("parent_id") is not None \
            and avant.get("parent_id") != apres.get("parent_id"):
        p = conn.execute("SELECT planche_id FROM regions WHERE id = ?",
                         (avant["parent_id"],)).fetchone()
        if p is not None and (p["planche_id"] != r["planche_id"]
                              or _recreee_depuis(conn, avant["parent_id"], e)
                              or _supprimee_depuis(conn, avant["parent_id"], e)):
            return False
    return True


def lieux(conn, e) -> dict:
    """Où l'inverse de `e` ÉCRIRAIT : `{"regions": [...], "planches": [...]}`.

    Une suppression se rétablit DANS une planche — la région n'existe pas encore ; tout
    autre acte s'inverse sur sa région. C'est ce que la route éprouve avec les accesseurs
    gardés, en écriture, sous la portée de la requête."""
    if e["type"] == "suppression" and e["cible_table"] == "regions":
        return {"regions": [], "planches": _planches_instantane(_charge(e["avant"]) or {})}
    return {"regions": [e["cible_id"]], "planches": []}


def ecarter(conn: sqlite3.Connection, e) -> int:
    """PASSE un acte qui ne s'annule plus : une trace au journal, append-only, qui le sort
    de la pile (`derniere_action_annulable`). Rien d'autre n'est écrit. NE COMMITE PAS.

    `abandon` et non `annulation` : rien n'a été défait, et `conflit.auteur_du_champ` lit
    une annulation comme ayant reposé l'état `avant`. La `cible_table` « annulation »
    n'est pas une table — comme `sharedocs` — mais la clé sous laquelle `tools/_commun.py`
    RETIENT la trace hors du dépôt ; elle s'écrit en clair, parce que le cliquet du journal
    ne relève que les littéraux (`test_journal_publie_par_decision`)."""
    return journal.journaliser(conn, "abandon", "annulation", e["id"],
                               avant={"acte": e["type"], "cible_table": e["cible_table"],
                                      "cible_id": e["cible_id"]})


def annuler(conn: sqlite3.Connection, evenement_id: Optional[int] = None,
            agent=TOUS, *, ecrivable) -> Optional[dict]:
    """Annule la dernière action (ou l'événement `evenement_id`) : exécute l'inverse puis
    journalise un événement `annulation`. Renvoie un descripteur {description, planche_id,
    region_id, …} pour le rafraîchissement UI, ou None s'il n'y a rien à annuler. NE COMMITE
    PAS (la route commite → inversion + journal atomiques ; rollback en cas d'échec).

    `ecrivable(lieux) -> bool` dit si l'agent peut écrire MAINTENANT là où l'inverse
    écrirait (AUTH-14). Il est OBLIGATOIRE, sans défaut — comme la `Portee` des accesseurs
    gardés : un défaut qui sauterait le contrôle rendrait l'oubli invisible. Lève
    `NeSAnnulePlus` si l'objet n'est plus le même ou n'est plus à la portée de l'agent."""
    if evenement_id is None:
        e = derniere_action_annulable(conn, agent)
    else:
        e = conn.execute("SELECT * FROM evenement WHERE id = ?", (evenement_id,)).fetchone()
        # Viser un événement par son id ne contourne pas la règle : on n'annule que le sien.
        if e is not None and agent is not TOUS and e["agent"] != agent:
            e = None
        # … ni le délai d'un compte collectif : nommer un acte ne le rajeunit pas.
        borne = _borne(conn, agent)
        if e is not None and borne is not None and (e["date"] or "") < borne:
            e = None
    if e is None:
        return None
    if not _meme_objet(conn, e) or not ecrivable(lieux(conn, e)):
        raise NeSAnnulePlus(e)
    try:
        region_id = _inverser(conn, e)
    except Irretablissable:
        raise NeSAnnulePlus(e, PHRASE_IRRETABLISSABLE)
    planche_id = _planche_de(conn, region_id, e)
    journal.journaliser(conn, "annulation", "evenement", e["id"],
                        avant={"acte": e["type"], "cible_table": e["cible_table"],
                               "cible_id": e["cible_id"]})
    return {"evenement_id": e["id"], "acte": e["type"], "cible_table": e["cible_table"],
            "region_id": region_id, "planche_id": planche_id, "description": _description(e)}
