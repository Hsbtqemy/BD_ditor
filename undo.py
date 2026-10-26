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
présence, relevés (poser/modifier/retirer, ANN-7 ; une région rétablie rend les siens). Hors
périmètre : correction grammaticale, validation, doutes et passes (ils se répondent et se
rouvrent).
Sous un compte COLLECTIF (AUTH-6), seuls les actes récents : `DELAI_COLLECTIF_MINUTES`.
Cf. `docs/undo.md`.
"""
from __future__ import annotations

import contextvars
import json
import sqlite3
from typing import Optional

import conflit
import journal
from config import TYPES_LOCUTEUR, TYPES_PRESENCE, TYPES_SITUATION
from database import (NATURE_COLLECTIF, annotation_vide, cle_tag, espace_de_region,
                      reindex_region,
                      unindex_region)

# Types d'événements et tables que l'undo sait inverser (le reste est ignoré : ni annulé,
# ni bloquant — l'undo « saute » un acte non annulable et remonte au précédent).
_TYPES = ("creation", "modification", "suppression", "lien", "delien")
_TABLES = ("regions", "annotations", "bulle_locuteur", "personnage_presence", "releve",
           "releve_planche")
# ANN-7 (tranche 1, R10) — les relevés, sous la cible de leur région ou de leur planche.
_RELEVES = ("releve", "releve_planche")
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
    ("creation", "releve"): "pose d'un relevé",
    ("modification", "releve"): "modification d'un relevé",
    ("suppression", "releve"): "retrait d'un relevé",
    ("creation", "releve_planche"): "pose d'un relevé",
    ("modification", "releve_planche"): "modification d'un relevé",
    ("suppression", "releve_planche"): "retrait d'un relevé",
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

    def __init__(self, e, phrase: str = PHRASE_NE_S_ANNULE_PLUS, voit=None):
        self.evenement = e
        self.description = _description(e, voit)
        super().__init__(phrase.format(description=self.description))


class Irretablissable(Exception):
    """Levée PENDANT l'inversion : l'état d'avant n'a plus où se poser. `annuler` la change
    en `NeSAnnulePlus` (seconde phrase) ; la route défait ce qui aurait été écrit."""


# ANN-8 — ce qu'un changement de type peut retirer, sous sa clé dans `avant` (celle d'un nœud
# d'instantané profond), et comment la description du geste le nomme.
_RETRAITS = (("locuteur", "de son locuteur"), ("presence", "du personnage montré"),
             ("attributs", "de sa situation"))


def _description(e, voit=None) -> str:
    """La phrase d'un acte. `voit(valeur_id) -> bool` : la situation retirée ne se nomme que
    si l'agent en voit au moins une valeur — dire « retrait de sa situation » d'une case dont
    il ne lit aucune valeur lui apprendrait qu'il y en avait une (relecture de la suite
    d'ANN-8, S2). Sans `voit`, tout se nomme."""
    retires = _liens_retires(e)
    if voit is not None and "attributs" in retires \
            and not any(voit(v) for v in retires["attributs"]):
        del retires["attributs"]
    if retires:
        quoi = [nom for cle, nom in _RETRAITS if cle in retires]
        quoi = quoi[0] if len(quoi) == 1 else ", ".join(quoi[:-1]) + " et " + quoi[-1]
        return f"modification d'une région et retrait {quoi}"
    return _DESCRIPTIONS.get((e["type"], e["cible_table"]), f"{e['type']} {e['cible_table']}")


def _liens_retires(e) -> dict:
    """Ce que la modification d'une région a retiré avec son type (ANN-8 : `PUT
    /api/regions/{id}` le range sous `locuteur`, `presence`, `attributs` dans son `avant`) :
    ces clés seulement, et seulement si elles portent quelque chose ; vide sinon."""
    if e["type"] != "modification" or e["cible_table"] != "regions":
        return {}
    avant = _charge(e["avant"]) or {}
    return {cle: avant[cle] for cle, _ in _RETRAITS if avant.get(cle)}


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


def reindexe(e) -> bool:
    """L'inverse de `e` réindexe-t-il une région — donc demande-t-il le moteur de langue ?
    Non pour un lien (locuteur, présence : `_poser_lien` / `_retirer_lien` n'indexent rien),
    ni pour l'annulation d'une création (`_supprimer_region` ne fait que DÉSINDEXER). La
    route s'en sert pour ne charger spaCy que lorsqu'il servira (ANN-8)."""
    if e["cible_table"] in _LIENS or e["cible_table"] in _RELEVES:
        return False
    return not (e["cible_table"] == "regions" and e["type"] == "creation")


def apercu(conn: sqlite3.Connection, agent=TOUS, voit=None) -> Optional[dict]:
    """Ce que ferait la prochaine annulation (sans l'exécuter) : {evenement_id, description}.
    `voit` : cf. `_description`."""
    e = derniere_action_annulable(conn, agent)
    return {"evenement_id": e["id"], "description": _description(e, voit)} if e else None


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


def _garder_creation(conn, region_id, apres, depuis=None, agent=None, voit=None):
    """Refuse d'annuler la création d'une région que QUELQU'UN D'AUTRE a travaillée depuis.

    Supprimer la région emporterait ce travail sans instantané : l'annulation est une
    mutation brute, qui ne journalise que l'acte `annulation`. Ses propres gestes plus récents
    sont annulés AVANT celui-ci, si bien que ce qui reste ici vient d'un autre.

    `depuis` : l'acte de création — l'auteur ne se cherche qu'APRÈS lui (ANN-8, cf.
    `conflit.auteur_du_champ`) : avant la v30, ce qui précède dans le journal du même
    identifiant est un autre objet.

    CONC-4 — les LIENS de la région se gardent aussi (`_garder_liens_de_creation`) : le
    locuteur, le personnage montré et la situation partaient par cascade. `agent` : l'auteur
    de la création, dont les liens ne bloquent pas ; `voit` : les valeurs de situation que
    l'agent lit (cf. `_garder_liens_de_creation`).

    ANN-7 — les RELEVÉS et les PASSES de la région et de ses descendants se gardent comme
    l'annotation (`_garder_releves_de_creation`) ; une passe, seulement celle d'un autre ;
    et un relevé d'un autre qui désigne la région par son LIEN.
    """
    actuel = journal.snapshot_region(conn, region_id)
    if actuel is None:
        return
    for c in journal._REGION_COLS:
        if c not in _SANS_GARDE and not conflit.egal(actuel.get(c), (apres or {}).get(c)):
            raise conflit.Perime("regions", region_id, c, actuel.get(c),
                                 conflit.auteur_du_champ(conn, "regions", region_id, c,
                                                         actuel.get(c), depuis=depuis))
    if journal.snapshot_annotation(conn, region_id) is not None:
        e = conn.execute("SELECT * FROM evenement WHERE cible_table = 'annotations' "
                         "AND cible_id = ? AND id > ? ORDER BY id DESC LIMIT 1",
                         (region_id, depuis or 0)).fetchone()
        raise conflit.Perime("annotations", region_id, "annotation", None,
                             conflit.auteur(conn, e) if e else None)
    _garder_releves_de_creation(conn, region_id, agent)
    _garder_liens_de_creation(conn, region_id, depuis, agent, voit)
    enfant = conn.execute("SELECT id FROM regions WHERE parent_id = ? ORDER BY id DESC LIMIT 1",
                          (region_id,)).fetchone()
    if enfant is not None:
        # La même borne pour l'enfant : une création sous son identifiant d'AVANT l'acte est
        # celle d'un autre objet, avant la v30 (contre-relecture de la garde des liens). Un
        # enfant né avant l'acte et rattaché depuis se dit donc « modifié ailleurs ».
        e = conn.execute("SELECT * FROM evenement WHERE cible_table = 'regions' AND "
                         "type = 'creation' AND cible_id = ? AND id > ? "
                         "ORDER BY id DESC LIMIT 1", (enfant["id"], depuis or 0)).fetchone()
        raise conflit.Perime("regions", region_id, "enfants", None,
                             conflit.auteur(conn, e) if e else None)


def _garder_releves_de_creation(conn, region_id, agent) -> None:
    """Annuler la création d'une région n'emporte pas les relevés ni les passes qui vivent sur
    elle ou sur l'un de ses descendants (ANN-7, tranche 1 ; relecture croisée, constat 1).
    `_supprimer_region` est une mutation brute : le CASCADE les effaçait sans instantané pour
    les rendre — le relevé et la passe qu'un autre avait posés sur la bulle d'une stagiaire
    partaient avec son Ctrl+Z, en 200.

    Trois gardes, dans cet ordre, et le 409 nommé de CONC-3, que « Passer ce geste » franchit :
    - un RELEVÉ sur ces régions, quel qu'en soit l'auteur — le patron des annotations : ses
      propres relevés plus récents sont annulés AVANT la création. Un relevé d'une grille
      DÉSACTIVÉE compte comme les autres : désactiver ne supprime aucun relevé ;
    - une PASSE d'un autre (`par`) — la sienne ne bloque pas : une passe ne s'annule pas, et
      la marquer sur sa propre zone ne doit pas rendre sa création inannulable, la doctrine
      de CONC-4 pour la situation (décision du pilotage, 2026-10-26 ; contre-relecture,
      r5). Elle part avec la région ;
    - un relevé d'un AUTRE, posé ailleurs, dont le LIEN désigne l'une de ces régions
      (contre-relecture, r2) : la règle de CONC-4 pour les liens — annulée, la région le
      laisserait « à revoir ». « D'un autre » : son dernier auteur, `modifie_par` sinon
      `auteur` ; un auteur inconnu (recopié entre deux projets) est un autre.
    Le refus nomme l'auteur de ce qui VIT et bloque — `modifie_par` sinon `auteur` pour un
    relevé, `par` pour une passe —, et le champ selon cet objet (contre-relecture, r1 : il
    nommait le dernier acte sous la cible, qui pouvait être celui de l'agent)."""
    zones = _descendants(conn, region_id)
    marques = ", ".join("?" * len(zones))
    # Un relevé : celui d'un autre d'abord, le plus récent sinon.
    r = conn.execute(
        f"SELECT * FROM releve r WHERE region_id IN ({marques}) "
        f"ORDER BY {_SQL_RELEVE_D_UN_AUTRE} DESC, COALESCE(modifie_le, cree_le) DESC, "
        f"id DESC LIMIT 1", (*zones, agent, agent)).fetchone()
    if r is not None:
        raise conflit.Perime("releve", region_id, "releve", None,
                             _auteur_d_un_releve(conn, r, agent))
    p = conn.execute(f"SELECT par AS qui, le FROM passe WHERE region_id IN ({marques}) "
                     f"AND par IS NOT ? ORDER BY le DESC, id DESC LIMIT 1",
                     (*zones, agent)).fetchone()
    if p is not None:
        raise conflit.Perime("releve", region_id, "passe", None,
                             conflit.auteur_nomme(conn, p["qui"], p["le"]))
    lien = conn.execute(
        f"SELECT * FROM releve r WHERE lien_region_id IN ({marques}) "
        f"AND {_SQL_RELEVE_D_UN_AUTRE} "
        f"ORDER BY COALESCE(modifie_le, cree_le) DESC, id DESC LIMIT 1",
        (*zones, agent, agent)).fetchone()
    if lien is not None:
        raise conflit.Perime("releve", region_id, "lien_region_id", lien["lien_region_id"],
                             _auteur_d_un_releve(conn, lien, agent))


# Un relevé (alias `r`) est-il celui d'un AUTRE que l'agent (deux `?`, l'agent deux fois) ?
# La forme FERMÉE (contre-relecture n°2, consigne du pilotage) : son AUTEUR n'est pas l'agent
# — un auteur inconnu, recopié entre deux projets, est un autre —, ou un autre humain a agi
# sur lui au journal (sa cible, sa charge `releve_id`), défait ou non. Jamais le seul dernier
# retoucheur : une retouche de soi ne fait pas passer le relevé d'un autre pour le sien.
_SQL_RELEVE_D_UN_AUTRE = (
    "(r.auteur IS NOT ? OR EXISTS (SELECT 1 FROM evenement _ue "
    "WHERE ((_ue.cible_table = 'releve' AND _ue.cible_id = r.region_id) "
    "OR (_ue.cible_table = 'releve_planche' AND _ue.cible_id = r.planche_id)) "
    "AND _ue.agent_type = 'humain' AND _ue.agent IS NOT ? "
    "AND COALESCE(CASE WHEN json_valid(_ue.apres) THEN json_extract(_ue.apres, '$.releve_id') "
    "END, CASE WHEN json_valid(_ue.avant) THEN json_extract(_ue.avant, '$.releve_id') END) "
    "= r.id))")


def _auteur_d_un_releve(conn, r, agent) -> Optional[dict]:
    """Qui nommer pour un relevé qui bloque : un auteur AUTRE que l'agent parmi `auteur` puis
    `modifie_par` ; sinon personne — le refus dit « ailleurs » (contre-relecture n°2)."""
    if r["auteur"] is not None and r["auteur"] != agent:
        return conflit.auteur_nomme(conn, r["auteur"], r["cree_le"])
    if r["modifie_par"] is not None and r["modifie_par"] != agent:
        return conflit.auteur_nomme(conn, r["modifie_par"], r["modifie_le"])
    return None


# CONC-4 — les liens qu'une région emporte par cascade : (table, colonne de la charge, champ
# nommé par le 409).
_LIENS_DE_CREATION = (("bulle_locuteur", "personnage_id", "locuteur"),
                      ("personnage_presence", "personnage_id", "presence"),
                      ("region_attribut", "valeur_id", "situation"))


def _poseur(conn, table, colonne, region_id, valeur, depuis) -> Optional[dict]:
    """Qui a POSÉ ce lien : le dernier `lien` de `table` qui l'a mis, après `depuis`.

    Seuls les vrais `lien` comptent. Une annulation qui repose un lien — celle d'un changement
    de type, d'une suppression ou d'un retrait — ne rend pas son auteur propriétaire du lien :
    Alice crée une bulle, Bob lui donne Zed, Alice la passe en case puis fait Ctrl+Z (Zed
    revient) ; lue par `conflit.auteur_des_champs`, cette annulation désignait Alice comme
    celle qui avait posé Zed, et le Ctrl+Z suivant emportait la création et le Zed de Bob, en
    200 (relecture de CONC-4). Le `lien` d'origine, lui, reste au journal : la région est née
    après la v30, son identifiant n'a désigné personne d'autre."""
    for e in conn.execute("SELECT * FROM evenement WHERE cible_table = ? AND cible_id = ? "
                          "AND type = 'lien' AND id > ? ORDER BY id DESC",
                          (table, region_id, depuis or 0)):
        if (_charge(e["apres"]) or {}).get(colonne) == valeur:
            return conflit.auteur(conn, e)
    return None


def _garder_liens_de_creation(conn, region_id, depuis, agent, voit=None) -> None:
    """Annuler la création d'une région n'emporte pas le locuteur, le personnage montré ni la
    situation qu'un AUTRE lui a donnés (CONC-4 ; reproduit par la relecture croisée d'ANN-8,
    `test_h5_…`). La suppression les effaçait par cascade, sans instantané pour les rendre.

    Pour chaque lien que la région porte, le `lien` qui l'a posé APRÈS la création
    (`_poseur`) : de l'auteur de la création, il passe — une situation ne s'annule pas, et la
    poser sur sa propre case ne doit pas rendre sa création inannulable ; d'un autre, ou
    d'aucun acte (outil, base retouchée : le journal NOMME, il ne décide pas), l'annulation est
    refusée par le 409 nommé, rien d'écrit. Seul compte ce qui RESTE : un lien posé puis retiré
    par un autre ne bloque rien.

    Une valeur de situation que l'agent ne VOIT pas (`voit`) suit la doctrine S2 d'ANN-8, celle
    de `_garder_liens_du_type` : elle refuse comme une autre — sans quoi le travail d'une
    collection qu'il ne lit pas partirait avec la case —, mais le refus ne rend que les valeurs
    VUES (`valeur_actuelle`), ne nomme l'auteur que d'une valeur vue, et dit sinon « modifiée
    ailleurs » (relecture de CONC-4 : il rendait l'identifiant de la valeur cachée et le login
    de son auteur)."""
    for table, colonne, champ in _LIENS_DE_CREATION:
        portes = [r[0] for r in conn.execute(
            f"SELECT {colonne} FROM {table} WHERE region_id = ? ORDER BY {colonne}",
            (region_id,))]
        poseurs = {v: _poseur(conn, table, colonne, region_id, v, depuis) for v in portes}
        d_autrui = [v for v, qui in poseurs.items()
                    if not (qui is not None and qui["agent_type"] == "humain"
                            and qui["login"] == agent)]
        if not d_autrui:
            continue
        if table != "region_attribut":
            raise conflit.Perime(table, region_id, champ, d_autrui[0], poseurs[d_autrui[0]])
        vues = [v for v in portes if voit is None or voit(v)]
        nommee = next((v for v in d_autrui if v in vues), None)
        raise conflit.Perime(table, region_id, champ, vues,
                             poseurs[nommee] if nommee is not None else None)


def _supprimer_region(conn, region_id):
    """Inverse d'une CRÉATION de région : supprime la région et son sous-arbre (cascade)."""
    for rid in _descendants(conn, region_id):
        unindex_region(conn, rid)
    conn.execute("DELETE FROM regions WHERE id = ?", (region_id,))


def _inverser_modification_region(conn, region_id, avant, apres, voit=None, depuis=None):
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
    # ANN-8 — défaire un changement de type, c'est aussi décider de ses liens : les gardes
    # passent AVANT toute écriture (`_garder_liens_du_type`).
    if "type" in changees:
        _garder_liens_du_type(conn, region_id, avant, voit, depuis)
    # AUTH-14 — le parent qu'on rend se valide comme la route le valide (`_validate_parent`) :
    # présent, dans la MÊME planche, sans cycle. Sans quoi Ctrl+Z rattachait une bulle à une
    # case d'une autre collection (relecture croisée, S1).
    if "parent_id" in changees and avant.get("parent_id") is not None \
            and not _parent_valide(conn, region_id, avant["parent_id"], actuel["planche_id"]):
        raise Irretablissable()
    for c in changees:
        if c not in _SANS_GARDE:
            conflit.verifier(conn, "regions", region_id, c, vu=apres.get(c),
                             actuel=actuel[c], nouveau=avant.get(c), depuis=depuis)
    if changees:
        conn.execute(f"UPDATE regions SET {', '.join(f'{c} = ?' for c in changees)} "
                     "WHERE id = ?", (*[avant.get(c) for c in changees], region_id))
    reindex_region(conn, region_id)


# ANN-8 — ce que l'inversion d'une annotation doit savoir des TAGS, posé par `annuler` :
# `perdus`, les libellés qui ne se résolvent plus (rendus en `tags_non_rendus`) ; `lisible`,
# la question « l'agent voit-il ce tag ? » (`clause_terme`, par le `ecrivable` de la route).
# Une variable de contexte plutôt qu'un argument de `_inverser` : sa signature `(conn, e)`
# est un contrat que des tests remplacent tel quel. Absente, rien n'est lisible par la
# clé : seul le libellé exact de l'instantané revient — la règle qui se ferme.
_CONTEXTE_TAGS: contextvars.ContextVar = contextvars.ContextVar("contexte_tags")


def _contexte_tags() -> dict:
    return _CONTEXTE_TAGS.get(None) or {"perdus": [], "lisible": lambda _tag_id: False}


def _tag_a_rendre(conn, label, depuis, lisible, *, espace: int = 0) -> Optional[dict]:
    """Le tag qu'un INSTANTANÉ nomme `label`, tel qu'il est aujourd'hui — ou None. ANN-8.

    L'instantané d'une annotation nomme ses tags par LIBELLÉ (`journal.snapshot_annotation`),
    et un tag se renomme, se fusionne, se supprime depuis le panneau Lexique. L'annulation
    créait jadis le libellé manquant (`INSERT INTO tags`) : un ancien libellé LOCAL revenait
    en tag GLOBAL, visible de toute l'instance, et un tag supprimé exprès ressuscitait
    (relecture croisée du 2026-10-22). **Elle ne crée plus jamais de tag.**

    1. La chaîne du journal `tags` APRÈS l'acte annulé (`depuis`, son identifiant
       d'événement — append-only, ses identifiants ne reviennent pas) : un renommage ou une
       fusion dont l'`avant` porte ce libellé (par sa clé) mène au libellé suivant ; une
       suppression arrête tout — le tag a été retiré exprès, et un tag du même nom créé
       depuis n'est pas lui. Elle se suit par les LIBELLÉS des charges, jamais par
       `cible_id` : les identifiants de `tags` se réattribuent.
    2. Si la chaîne n'a rien changé, le LIBELLÉ EXACT de l'instantané, lisible ou non : un
       tag caché revient comme il était — cacher n'est pas saisir (`_tags_caches`).
    3. Sinon, la clé (`database.cle_tag`), et seulement parmi les tags que l'agent VOIT
       (`lisible`) : deux lignes d'avant de même clé, l'une globale et l'autre locale à une
       collection qu'il ne lit pas, ne lui font pas poser la seconde (contre-relecture du
       2026-10-22). Un tag hors de portée trouvé ainsi compte comme perdu.

    Ne se demande QUE pour un libellé de l'instantané de l'acte : les tags que la région
    porte aujourd'hui se reposent par leur identifiant, sans passer par la chaîne.

    COL-4 — tout se cherche dans l'ESPACE de libellés de la région (`espace`, celui de son
    bac à sable, ou 0) : le même libellé vit dans le corpus et dans un bac à sable, et un
    renommage dans l'un n'est pas celui de l'autre (une charge sans `espace` est de
    l'instance)."""
    cle, suivi = cle_tag(label), False
    for ev in conn.execute("SELECT type, avant, apres FROM evenement "
                           "WHERE cible_table = 'tags' AND id > ? ORDER BY id", (depuis,)):
        charge = _charge(ev["avant"]) or {}
        if cle_tag(charge.get("label")) != cle or (charge.get("espace") or 0) != espace:
            continue
        if ev["type"] == "suppression":
            return None
        cle, suivi = cle_tag((_charge(ev["apres"]) or {}).get("label")), True
    if not cle:
        return None
    if not suivi:
        exact = conn.execute("SELECT id, label FROM tags WHERE espace = ? AND label = ?",
                             (espace, label)).fetchone()
        if exact is not None:
            return dict(exact)
    for row in conn.execute("SELECT id, label FROM tags WHERE espace = ? "
                            "AND cle_tag(label) = ? ORDER BY (label = ?) DESC, id",
                            (espace, cle, cle)):
        if lisible(row["id"]):
            return dict(row)
    return None


def _poser_annotation(conn, region_id, note, tag_ids):
    """Pose une annotation {note, tags par IDENTIFIANT} sur une région (upsert) + réindexe ;
    la supprime s'il ne lui reste rien à porter (`annotation_vide`)."""
    if annotation_vide(note, len(tag_ids)):
        _supprimer_annotation(conn, region_id)
        return
    conn.execute("INSERT INTO annotations (region_id, note) VALUES (?, ?) "
                 "ON CONFLICT(region_id) DO UPDATE SET note = excluded.note",
                 (region_id, note))
    ann_id = conn.execute("SELECT id FROM annotations WHERE region_id = ?",
                          (region_id,)).fetchone()["id"]
    conn.execute("DELETE FROM annotation_tags WHERE annotation_id = ?", (ann_id,))
    for tag_id in tag_ids:
        conn.execute("INSERT OR IGNORE INTO annotation_tags (annotation_id, tag_id) "
                     "VALUES (?, ?)", (ann_id, tag_id))
    reindex_region(conn, region_id)


def _restaurer_annotation(conn, region_id, annot, *, depuis):
    """(Re)pose l'annotation d'un INSTANTANÉ {note, tags par libellé} sur une région.

    Les libellés passent par `_tag_a_rendre` : ce qui ne se résout plus est compté dans les
    `perdus` du contexte et ne revient pas."""
    ctx = _contexte_tags()
    tag_ids = []
    espace = espace_de_region(conn, region_id)
    for label in annot.get("tags", []):
        tag = _tag_a_rendre(conn, label, depuis, ctx["lisible"], espace=espace)
        if tag is None:
            ctx["perdus"].append(label)
        elif tag["id"] not in tag_ids:
            tag_ids.append(tag["id"])
    _poser_annotation(conn, region_id, annot.get("note"), tag_ids)


def _supprimer_annotation(conn, region_id):
    conn.execute("DELETE FROM annotations WHERE region_id = ?", (region_id,))   # cascade tags
    reindex_region(conn, region_id)


def _inverser_annotation(conn, region_id, avant, apres, *, depuis):
    """Défait CE QUE l'acte a changé, et rien d'autre (CONC-3).

    Restaurer l'instantané `avant` entier défaisait aussi ce qu'une autre personne avait fait
    sur l'AUTRE champ entre-temps : annuler une note rendait la liste de tags d'avant, donc
    effaçait le tag posé par un collègue. L'inverse se calcule donc par différence, sur l'état
    ACTUEL : la note revient à sa valeur d'avant si l'acte l'a changée ; les tags que l'acte
    a ajoutés sont retirés, ceux qu'il a retirés sont remis, les autres ne bougent pas. Tant
    que personne d'autre n'a touché l'annotation, c'est exactement l'instantané `avant`.

    ANN-8 — la différence se calcule par IDENTIFIANT. Les libellés de l'instantané de l'acte
    — et eux seuls — passent par `_tag_a_rendre` : un tag ajouté par l'acte puis fusionné se
    retire sous sa cible, un tag retiré puis renommé revient sous son nouveau nom. Les tags
    que la région porte aujourd'hui restent ceux qu'ils sont, sans passer par la chaîne :
    un « x » posé depuis par un autre n'est pas l'ancien « x » renommé. Un tag que l'acte a changé et qui ne se résout plus
    (supprimé depuis) ne revient pas ; si l'acte ne portait QUE sur de tels tags, il n'y a
    rien à rétablir, et l'acte est passé (`Irretablissable`, seconde phrase d'AUTH-14).
    """
    avant, apres = avant or {}, apres or {}
    actuel = journal.snapshot_annotation(conn, region_id) or {}
    note = actuel.get("note")
    if (avant.get("note") or "") != (apres.get("note") or ""):
        # Second temps (Q4) : si la note a changé depuis l'acte, la rendre écraserait celle
        # écrite ensuite par un autre. Les tags n'ont pas de garde : ils vont par différence.
        conflit.verifier(conn, "annotations", region_id, "note", vu=apres.get("note"),
                         actuel=actuel.get("note"), nouveau=avant.get("note"),
                         depuis=depuis)
        note = avant.get("note")
    ctx = _contexte_tags()
    t_avant, t_apres = set(avant.get("tags", [])), set(apres.get("tags", []))
    espace = espace_de_region(conn, region_id)
    resolus = {l: _tag_a_rendre(conn, l, depuis, ctx["lisible"], espace=espace)
               for l in t_avant | t_apres}
    r_avant = {resolus[l]["id"] for l in t_avant if resolus[l]}
    r_apres = {resolus[l]["id"] for l in t_apres if resolus[l]}
    sans_suite = sorted(l for l in t_avant ^ t_apres if resolus[l] is None)
    if (sans_suite and r_avant == r_apres
            and (avant.get("note") or "") == (apres.get("note") or "")):
        raise Irretablissable()
    ctx["perdus"].extend(sans_suite)
    portes = {r["tag_id"] for r in conn.execute(
        "SELECT at.tag_id FROM annotation_tags at JOIN annotations an "
        "ON an.id = at.annotation_id WHERE an.region_id = ?", (region_id,))}
    _poser_annotation(conn, region_id, note,
                      sorted((portes - (r_apres - r_avant)) | (r_avant - r_apres)))


def _recreer_region_profond(conn, snap, *, depuis):
    """Inverse d'une SUPPRESSION : recrée la région, son annotation et son sous-arbre depuis
    l'instantané PROFOND. Réutilise les `id` d'origine (préserve citations / deep-links) ;
    parent créé avant enfants (FK). Lève UndoImpossible si un id a été réattribué depuis.
    Les LIENS des régions rétablies reviennent ensuite, par `_rendre_liens` (ANN-8)."""
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
        _restaurer_annotation(conn, snap["id"], annot, depuis=depuis)
    else:
        reindex_region(conn, snap["id"])
    for enfant in snap.get("enfants", []):
        _recreer_region_profond(conn, enfant, depuis=depuis)


def _rendre_liens(conn, snap, rendables) -> int:
    """ANN-8 — repose les liens des régions qu'une annulation vient de rétablir — par une
    suppression défaite, ou par un changement de type défait qui les avait emportés : le
    locuteur, le personnage montré, les attributs de case. Seulement ceux qui sont RENDABLES
    (`_liens_rendables`, calculé avant toute écriture) : le personnage ou la valeur existe
    encore, est celui de l'acte, et l'agent le voit — et sur une région dont le type montre
    ce lien (`_montre`). Un lien qui ne l'est pas ne
    revient pas, et la région revient quand même — elle est l'objet de l'acte, et le lien
    serait parti de toute façon avec ce qu'il désignait. Rend combien de liens ne reviennent
    pas, compté par NŒUD : deux bulles du même locuteur font deux liens.

    Le miroir (Hugo, 2026-10-21) : un personnage montré ne revient que sur une boîte
    personnage, une situation que sur une case — sur une région dont le type ne le montre
    pas, le lien ne revient pas et se compte, comme un locuteur sur une case."""
    manque = 0
    for n in _noeuds(snap):
        for cle, table in _LIENS_INSTANTANE:
            if n.get(cle) is None:
                continue
            if n[cle] not in rendables["personnages"] or not _montre(conn, table, n["id"]):
                manque += 1
                continue
            _poser_lien(conn, table, n["id"], n[cle])
        montre = _montre(conn, "region_attribut", n["id"])
        for vid in n.get("attributs", []):
            if vid not in rendables["valeurs"] or not montre:
                manque += 1
                continue
            conn.execute("INSERT OR IGNORE INTO region_attribut (region_id, valeur_id) "
                         "VALUES (?, ?)", (n["id"], vid))
    return manque


# Les liens d'un nœud d'instantané profond vers un personnage : (clé, table).
_LIENS_INSTANTANE = (("locuteur", "bulle_locuteur"), ("presence", "personnage_presence"))


def _liens_de_l_instantane(snap: dict) -> tuple[set, set]:
    """Les personnages et les valeurs d'attribut que l'instantané reposerait."""
    personnages, valeurs = set(), set()
    for n in _noeuds(snap):
        for cle, _ in _LIENS_INSTANTANE:
            if n.get(cle) is not None:
                personnages.add(n[cle])
        valeurs.update(n.get("attributs", []))
    return personnages, valeurs


def _valeur_nee_apres(conn, valeur_id, e) -> bool:
    """La valeur d'attribut a-t-elle été créée APRÈS l'acte ? Alors elle a repris
    l'identifiant de celle que la case portait — `attribut_valeur` n'a pas
    d'`AUTOINCREMENT`. Le témoin de `_personnage_ne_apres`, et sa limite : dans la même
    seconde, rien n'est vu."""
    row = conn.execute("SELECT date_creation FROM attribut_valeur WHERE id = ?",
                       (valeur_id,)).fetchone()
    return bool(row and row["date_creation"] and e["date"] and row["date_creation"] > e["date"])


def _liens_a_rendre(e) -> Optional[dict]:
    """Les liens que l'annulation de `e` reposerait, sous la forme d'un instantané profond
    (`_noeuds`), ou None si elle n'en repose aucun.

    Deux actes en portent. La SUPPRESSION d'une région : son instantané profond, tel quel.
    La MODIFICATION qui a changé le type d'une région et lui a retiré ce que son nouveau
    type ne montre pas (ANN-8, Hugo, 2026-10-21) — locuteur, personnage montré, situation :
    un nœud seul, la région de l'acte et ces liens. Un acte et non plusieurs — pas de
    `delien` à part — pour que UN Ctrl+Z rende le type et ses liens : deux actes en auraient
    demandé deux, et le premier aurait rendu une bulle muette que personne n'a voulue (le
    défaut qu'`UX-5` relève déjà pour les retouches). Et les liens reviennent par la même
    porte que ceux d'une suppression, sous les mêmes questions."""
    if e["cible_table"] != "regions":
        return None
    if e["type"] == "suppression":
        return _charge(e["avant"]) or {}
    retires = _liens_retires(e)
    if retires:
        noeud = {"id": e["cible_id"], **retires}
        dims = (_charge(e["avant"]) or {}).get("attributs_dimensions")
        if "attributs" in retires and dims:
            noeud["attributs_dimensions"] = dims
        return noeud
    return None


def _liens_rendables(conn, e, snap, ecrivable) -> dict:
    """Ce que l'annulation de `e` peut reposer des LIENS de `snap` (ANN-8).

    Les trois questions d'AUTH-14, posées lien par lien et AVANT toute écriture : l'objet
    désigné existe-t-il encore ; est-il celui de l'acte (né avant lui) ; l'agent le voit-il
    MAINTENANT (`ecrivable`, la question de la route : un personnage par ses apparitions,
    une valeur par la portée des termes). Ce qui échoue n'est pas reposé, en silence pour
    l'objet — l'écran apprend seulement COMBIEN de liens ne sont pas revenus.

    Sauf une : la valeur de situation que CE changement de type a retirée se rend même si
    l'agent ne la voit pas — elle existe encore et n'est pas née après l'acte suffit.
    « Cacher n'est pas saisir » (`_tags_caches`, `docs/undo.md`) : passer en bulle une case
    qui porte la situation locale d'une collection qu'on ne lit pas la retire avec le type,
    et Ctrl+Z la perdait — le travail de l'autre collection effacé par un geste qui ne la
    voyait pas (relecture de la suite d'ANN-8, S1). Une suppression rétablie garde la
    question de la portée.

    Et une valeur dont l'acte a photographié la DIMENSION (`attributs_dimensions`, R1) ne se
    rend que si elle est encore de cette dimension : un identifiant de valeur repris DANS LA
    MÊME SECONDE échappe au témoin de la date, et Ctrl+Z aurait posé un terme d'une autre
    grille — peut-être d'une collection fermée — sur la région. Un acte d'avant cette
    photographie garde la règle de la date seule."""
    retire_par_l_acte = e["type"] == "modification"
    dimension_d_alors = dict(map(tuple, snap.get("attributs_dimensions") or []))

    def meme_dimension(v) -> bool:
        if v not in dimension_d_alors:
            return True
        r = conn.execute("SELECT dimension_id FROM attribut_valeur WHERE id = ?",
                         (v,)).fetchone()
        return r is not None and r["dimension_id"] == dimension_d_alors[v]
    personnages, valeurs = _liens_de_l_instantane(snap)
    ok_p = {p for p in personnages
            if conn.execute("SELECT 1 FROM personnages WHERE id = ?", (p,)).fetchone()
            and not _personnage_ne_apres(conn, p, e)
            and ecrivable({"regions": [], "planches": [], "personnages": [p]})}
    ok_v = {v for v in valeurs
            if conn.execute("SELECT 1 FROM attribut_valeur WHERE id = ?", (v,)).fetchone()
            and not _valeur_nee_apres(conn, v, e)
            and meme_dimension(v)
            and (retire_par_l_acte
                 or ecrivable({"regions": [], "planches": [], "personnages": [], "valeurs": [v]}))}
    return {"personnages": ok_p, "valeurs": ok_v}


# ANN-8 — les liens d'une région qu'un changement de type photographie (`liens_vus`, cf.
# `database.liens_vus`) et que son annulation garde : (clé, table, champ nommé par le 409,
# types qui le montrent). Les deux premiers désignent UN personnage ; la situation est un
# ensemble de valeurs.
_LIENS_DU_TYPE = (("locuteur", "bulle_locuteur", "locuteur", TYPES_LOCUTEUR),
                  ("presence", "personnage_presence", "presence", TYPES_PRESENCE),
                  ("attributs", "region_attribut", "situation", TYPES_SITUATION))


def _garder_liens_du_type(conn, region_id, avant, voit=None, depuis=None) -> None:
    """Les liens sont des champs GARDÉS de l'annulation d'un changement de type (ANN-8,
    CONC-3). Lien par lien, ce que la région porte au moment de défaire doit être ce que
    l'acte y avait LAISSÉ — la photographie `liens_vus`, moins ce qu'il a retiré —, ou ce que
    l'annulation laissera sans rien effacer. Sinon quelqu'un l'a changé depuis l'acte, et
    l'annulation est refusée par le même 409 nommé qu'un enregistrement périmé, avec l'auteur
    du dernier `lien` qui l'a posé. Rien n'est écrit : la garde passe avant l'inversion.

    Deux cas, selon le type RENDU (`avant["type"]`) :

    - il montre le lien, et l'acte l'avait retiré : l'annulation le repose. Admis : aucun
      (rien n'a bougé), ou celui-là (déjà remis). Un AUTRE serait écrasé — Alice passe la
      bulle de Tintin en case, Bob la repasse en bulle et lui donne Haddock (h1). La
      situation, un ENSEMBLE, revient par différence, comme les tags (CONC-3) : ses valeurs
      se reposent à côté de celles qu'un autre a mises, sans rien écraser — pas de garde.
      S'il le montre et que l'acte n'y a pas touché, l'annulation n'y touche pas non plus :
      rien à garder ;
    - il ne le montre pas : l'annulation ne repose rien, et ce que la région porte resterait,
      caché. Admis : aucun, ou celui que l'acte avait laissé — une case d'avant ANN-8 qui
      portait déjà un locuteur, repassée en bulle puis Ctrl+Z, retrouve l'état d'avant tel
      qu'il était (c3), et c'est `tools/retirer_locuteurs_muets.py` qui le nettoie. Un autre,
      posé depuis, deviendrait invisible — Alice passe une case en bulle, Bob lui donne
      Haddock (h2). Pour la situation : ce que la région porte doit être une PARTIE de ce
      que l'acte avait laissé.

    Un acte d'avant la photographie n'a pas `liens_vus` : la garde y suppose ce qu'elle
    supposait alors, qu'aucun lien n'était laissé — et le 409 faux de c3 y reste possible.

    Une valeur de situation que l'agent ne VOIT pas (`voit`, la portée des termes : une
    valeur locale à une collection qu'il ne lit pas) refuse comme une autre — elle serait
    cachée par le type rendu. Le refus ne rend ni son identifiant (`valeur_actuelle` ne porte
    que les valeurs vues), ni son auteur, et sa phrase dit « modifiée ailleurs » (relecture
    de la suite d'ANN-8, S2). Il dit en revanche qu'une valeur que l'agent ne voit pas est
    LÀ — « modifiée ailleurs » avec une `valeur_actuelle` vide —, et c'est inévitable :
    refuser sans le dire, ou passer outre, effacerait le travail de l'autre collection. Un
    oracle de CONFIRMATION, accepté comme celui de `tags_concat` : il ne joue que sur une
    région qu'on écrit, et ne nomme rien.

    `depuis` : le changement de type défait — l'auteur ne se cherche qu'APRÈS lui (cf.
    `conflit.auteur_du_champ`)."""
    vus = avant.get("liens_vus") or {}
    for cle, table, champ, types in _LIENS_DU_TYPE:
        ensemble = table == "region_attribut"
        colonne = "valeur_id" if ensemble else "personnage_id"
        retire = set(_en_liste(avant.get(cle)))
        laisse = set() if retire else set(_en_liste(vus.get(cle)))
        if avant.get("type") in types:
            if not retire or ensemble:
                continue
            admis = retire
        else:
            admis = laisse
        actuel = {r[colonne] for r in conn.execute(
            f"SELECT {colonne} FROM {table} WHERE region_id = ?", (region_id,))}
        if actuel <= admis:
            continue
        de_trop = actuel - admis
        if ensemble and voit is not None:
            vues = {v for v in actuel if voit(v)}
            de_trop_vues = de_trop & vues
            qui = (conflit.auteur_du_champ(conn, table, region_id, colonne, min(de_trop_vues),
                                           depuis=depuis)
                   if de_trop_vues else None)
            raise conflit.Perime(table, region_id, champ, sorted(vues), qui)
        pose = min(de_trop)                 # nommer qui a posé ce qui n'était pas admis
        valeur = sorted(actuel) if ensemble else pose
        raise conflit.Perime(table, region_id, champ, valeur,
                             conflit.auteur_du_champ(conn, table, region_id, colonne, pose,
                                                     depuis=depuis))


def _en_liste(valeur) -> list:
    """Un lien photographié, en liste : un personnage (ou None) devient [id] (ou []), une
    situation est déjà une liste."""
    if valeur is None:
        return []
    return list(valeur) if isinstance(valeur, list) else [valeur]


# Quels types MONTRENT le lien de chaque table (ANN-8) : `config`, à un seul endroit.
_TYPES_QUI_MONTRENT = {"bulle_locuteur": TYPES_LOCUTEUR,
                       "personnage_presence": TYPES_PRESENCE,
                       "region_attribut": TYPES_SITUATION}


def _montre(conn, table, region_id) -> bool:
    """La région existe-t-elle, d'un type qui montre le lien de `table` — un locuteur, un
    personnage montré, une situation (`config.TYPES_LOCUTEUR`, `TYPES_PRESENCE`,
    `TYPES_SITUATION`) ?"""
    r = conn.execute("SELECT type FROM regions WHERE id = ?", (region_id,)).fetchone()
    return r is not None and r["type"] in _TYPES_QUI_MONTRENT[table]


def _poser_lien(conn, table, region_id, personnage_id):
    """Repose un lien région→personnage. ANN-8 (Hugo, 2026-10-21) — un locuteur ne se repose
    que sur une région dont le type en porte un. La route d'attribution le refusait seule
    (422) : une bulle dont on avait retiré le locuteur, passée en case par une collègue,
    le retrouvait EN TANT QUE CASE au Ctrl+Z suivant. L'état d'avant n'a plus où se poser :
    l'acte est irrétablissable, donc passé (`annuler`). Le miroir : un personnage montré ne
    se repose que sur une boîte personnage."""
    if not _montre(conn, table, region_id):
        raise Irretablissable()
    conn.execute(f"INSERT INTO {table} (region_id, personnage_id) VALUES (?, ?) "
                 f"ON CONFLICT(region_id) DO UPDATE SET personnage_id = excluded.personnage_id",
                 (region_id, personnage_id))


def _retirer_lien(conn, table, region_id):
    conn.execute(f"DELETE FROM {table} WHERE region_id = ?", (region_id,))


# Le champ qu'un refus nomme pour chaque table de lien, et la clé sous laquelle un
# changement de type range le lien qu'il retire (`database.retirer_liens_caches`).
_CHAMP_DU_LIEN = {"bulle_locuteur": "locuteur", "personnage_presence": "presence"}


def _garder_lien(conn, e, *, laisse, rendu) -> None:
    """L'annulation d'un `lien` ou d'un `delien` est GARDÉE (ANN-8, CONC-3 ; trouvé par Hugo
    à la QA du lot 1, 2026-10-23, présent depuis D1). Proprio donne Zed à une bulle ;
    Stagiaire le remplace par Yann ; le Ctrl+Z de Proprio retirait Yann — la bulle n'avait
    plus aucun locuteur, et le geste de Stagiaire disparaissait sans un mot.

    Ce que la région porte au moment de défaire doit être l'un de ceux-ci, sans quoi
    quelqu'un l'a changé depuis l'acte et l'annulation est refusée par le même 409 nommé
    qu'un enregistrement périmé — le champ (`locuteur`, `presence`), le personnage présent,
    l'auteur du dernier acte, POSTÉRIEUR à celui qu'on défait, qui l'a posé ou ôté. Rien
    n'est écrit : la garde passe avant l'inversion.

    - ce que l'acte y avait LAISSÉ (`laisse` : le personnage d'un `lien`, aucun pour un
      `delien`), ou ce que l'annulation laissera (`rendu`) : rien ne se perd ;
    - AUCUN, quand le personnage que l'acte avait laissé n'existe plus — sa suppression a
      emporté le lien par CASCADE, sans rien écrire au journal, et ce n'est le geste de
      personne sur cette région (relecture croisée, R2) ;
    - ce qu'a laissé un geste PLUS RÉCENT du même agent sur ce lien, PASSÉ depuis (`abandon`
      — « Ne s'annule plus », ou « Passer ce geste »), si rien ne l'a changé ensuite
      (`_laisse_par_un_geste_passe`, R4). Sans quoi chaque geste d'avant sur le même lien se
      refusait à son tour, face au travail de l'agent lui-même. Un geste passé après le
      conflit d'un AUTRE n'y entre pas : le dernier geste sur le lien est alors celui de
      l'autre, et le refus le nomme.

    Elle ne joue qu'APRÈS les questions d'AUTH-14 (`annuler` : l'objet est le même, l'agent
    l'écrit maintenant, le personnage rendu est le sien) et après le « passé » d'un type qui
    ne montre plus le lien (`_inverser`) : un refus nommé ne se rend que sur une région que
    l'agent écrit — dont il lit donc le locuteur et son auteur, comme ceux de tout champ
    gardé —, jamais sur une région qui a quitté sa portée. Et l'auteur ne se cherche
    qu'après l'acte : sous la numérotation d'avant la v30, ce qui précède dans le journal
    du même identifiant est un autre objet, peut-être dans une collection qu'il ne lit pas
    (R5).

    L'auteur se cherche aussi dans les changements de type (`regions`, sous `locuteur` ou
    `presence`), qui retirent le lien et dont l'annulation le repose."""
    table, region_id = e["cible_table"], e["cible_id"]
    ligne = conn.execute(f"SELECT personnage_id FROM {table} WHERE region_id = ?",
                         (region_id,)).fetchone()
    actuel = ligne["personnage_id"] if ligne is not None else None
    admis = {laisse, rendu}
    if laisse is not None and conn.execute("SELECT 1 FROM personnages WHERE id = ?",
                                           (laisse,)).fetchone() is None:
        admis.add(None)
    passe = _laisse_par_un_geste_passe(conn, e)
    if passe is not _AUCUN_GESTE_PASSE:
        admis.add(passe)
    if actuel in admis:
        return
    champ = _CHAMP_DU_LIEN[table]
    raise conflit.Perime(table, region_id, champ, actuel, conflit.auteur_des_champs(
        conn, ((table, "personnage_id"), ("regions", champ)), region_id, actuel,
        depuis=e["id"]))


_AUCUN_GESTE_PASSE = object()


def _laisse_par_un_geste_passe(conn, e):
    """Ce qu'a laissé sur le lien de `e` le DERNIER geste qui l'a touché depuis, si c'est un
    `lien` ou un `delien` du même agent, PASSÉ (`abandon`) : son personnage, ou None pour un
    retrait. Sinon `_AUCUN_GESTE_PASSE`.

    « Le dernier geste qui l'a touché » : sur la table du lien, une annulation d'un acte sur
    cette table, ou un acte sur `regions` (ou son annulation) dont la charge porte le lien —
    un changement de type qui l'ôte, une suppression rétablie qui le rend. Un geste plus
    récent, de qui que ce soit, fait que ce n'est plus la valeur du geste passé qui est là."""
    table, region_id = e["cible_table"], e["cible_id"]
    cle = _CHAMP_DU_LIEN[table]
    for ev in conn.execute(
            "SELECT ev.*, a.cible_table AS acte_table, a.avant AS acte_avant, "
            "       a.apres AS acte_apres FROM evenement ev "
            "LEFT JOIN evenement a ON ev.cible_table = 'evenement' AND a.id = ev.cible_id "
            "WHERE ev.id > ? AND ((ev.cible_table IN (?, 'regions') AND ev.cible_id = ?) "
            "   OR (ev.cible_table = 'evenement' AND ev.type = 'annulation' "
            "       AND a.cible_table IN (?, 'regions') AND a.cible_id = ?)) "
            "ORDER BY ev.id DESC", (e["id"], table, region_id, table, region_id)):
        annulation = ev["cible_table"] == "evenement"
        if (ev["acte_table"] if annulation else ev["cible_table"]) == "regions":
            charges = ((ev["acte_avant"], ev["acte_apres"]) if annulation
                       else (ev["avant"], ev["apres"]))
            if not any(cle in (_charge(c) or {}) for c in charges):
                continue                    # un geste sur la région qui n'a pas touché le lien
        if annulation or ev["cible_table"] != table or ev["type"] not in ("lien", "delien") \
                or ev["agent"] != e["agent"]:
            return _AUCUN_GESTE_PASSE
        if conn.execute("SELECT 1 FROM evenement WHERE type = 'abandon' "
                        "AND cible_table = 'annulation' AND cible_id = ?",
                        (ev["id"],)).fetchone() is None:
            return _AUCUN_GESTE_PASSE
        return (_charge(ev["apres"]) or {}).get("personnage_id") if ev["type"] == "lien" \
            else None
    return _AUCUN_GESTE_PASSE


# --------------------------------------------------------------------------- #
# Les relevés (ANN-7, tranche 1, R10)
# --------------------------------------------------------------------------- #
# Les valeurs d'un relevé qu'une annulation remet, gardées comme les champs de CONC-3.
_VALEURS_DU_RELEVE = ("variante_cle", "qualificatifs", "precision", "lien_region_id", "mots")


def _activation_du_releve(conn, snap) -> bool:
    """La grille du relevé est-elle active, dans SA version, dans le projet de l'album de sa
    cible ? Sinon l'acte ne s'annule plus (seconde phrase) : un relevé d'une grille
    désactivée se lit, il ne s'écrit plus — pas même par Ctrl+Z."""
    from database import projet_d_album
    if snap.get("region_id") is not None:
        a = conn.execute("SELECT p.album_id FROM regions g JOIN planches p "
                         "ON p.id = g.planche_id WHERE g.id = ?",
                         (snap["region_id"],)).fetchone()
    else:
        a = conn.execute("SELECT album_id FROM planches WHERE id = ?",
                         (snap.get("planche_id"),)).fetchone()
    if a is None:
        return False
    act = conn.execute("SELECT version_id FROM projet_grille WHERE projet_id = ? "
                       "AND grille_id = ?", (projet_d_album(conn, a[0]),
                                             snap["grille_id"])).fetchone()
    return act is not None and act[0] == snap["version_id"]


def _entree_existe(conn, snap) -> bool:
    """L'entrée du relevé existe-t-elle encore dans sa version ? Ctrl+Z rétablit un relevé
    par la `cle` de son entrée, jamais par un libellé (ANN-8) ; une entrée remaniée depuis
    (une grille ouverte) rend l'acte irrétablissable."""
    return conn.execute("SELECT 1 FROM grille_entree WHERE version_id = ? AND cle = ?",
                        (snap["version_id"], snap["entree_cle"])).fetchone() is not None


def _inverser_releve(conn, e, avant, apres) -> None:
    """Défait la pose, la modification ou le retrait d'un relevé. Les gardes passent avant
    toute écriture : la grille active dans la version du relevé, l'entrée encore là ; puis,
    comme pour une région, ce qu'un AUTRE a changé depuis n'est pas écrasé (CONC-3) — le 409
    nommé, que « Passer ce geste » franchit (ANN-8)."""
    import releves
    t = e["type"]
    snap = apres if t == "creation" else (avant or {})
    rid = snap.get("releve_id")
    actuel = releves.instantane(conn, rid) if rid is not None else {}
    if t == "suppression":
        if actuel:
            raise UndoImpossible("le relevé existe déjà")
        if not (_activation_du_releve(conn, snap) and _entree_existe(conn, snap)):
            raise Irretablissable()
        if snap.get("une"):
            autre = conn.execute(
                "SELECT * FROM releve WHERE COALESCE(region_id, 0) = ? "
                "AND COALESCE(planche_id, 0) = ? AND grille_id = ? AND entree_cle = ? "
                "AND une = 1", (snap.get("region_id") or 0, snap.get("planche_id") or 0,
                                snap["grille_id"], snap["entree_cle"])).fetchone()
            if autre is not None:
                pose = conn.execute(
                    "SELECT * FROM evenement WHERE cible_table IN ('releve', 'releve_planche') "
                    "AND type = 'creation' AND id > ? AND json_extract(apres, '$.releve_id') = ? "
                    "ORDER BY id DESC LIMIT 1", (e["id"], autre["id"])).fetchone()
                raise conflit.Perime(e["cible_table"], e["cible_id"], "releve", autre["id"],
                                     conflit.auteur(conn, pose) if pose else None)
        releves.rendre(conn, snap)
        return
    if not actuel:
        raise Irretablissable()                  # retiré depuis : il n'y a rien à défaire
    if not (_activation_du_releve(conn, actuel) and _entree_existe(conn, actuel)):
        raise Irretablissable()
    objet = ("releve_id", rid)
    if t == "creation":
        for champ in _VALEURS_DU_RELEVE:
            if not conflit.egal(actuel[champ], snap.get(champ)):
                raise conflit.Perime(e["cible_table"], e["cible_id"], champ, actuel[champ],
                                     conflit.auteur_du_champ(conn, e["cible_table"],
                                                             e["cible_id"], champ,
                                                             actuel[champ], depuis=e["id"],
                                                             objet=objet))
        doute = conn.execute("SELECT 1 FROM doute WHERE releve_id = ?", (rid,)).fetchone()
        if doute is not None:
            ouvert = conn.execute(
                "SELECT * FROM evenement WHERE cible_table = ? AND cible_id = ? "
                "AND type = 'doute' AND id > ? AND json_extract(apres, '$.releve_id') = ? "
                "ORDER BY id DESC LIMIT 1",
                (e["cible_table"], e["cible_id"], e["id"], rid)).fetchone()
            raise conflit.Perime(e["cible_table"], e["cible_id"], "doute", "ouvert",
                                 conflit.auteur(conn, ouvert) if ouvert else None)
        conn.execute("DELETE FROM releve WHERE id = ?", (rid,))
        return
    # Une modification : ce que l'acte a changé revient, et lui seul.
    avant, apres = avant or {}, apres or {}
    changes = [c for c in _VALEURS_DU_RELEVE if c in apres]
    for champ in changes:
        conflit.verifier(conn, e["cible_table"], e["cible_id"], champ, vu=apres.get(champ),
                         actuel=actuel[champ], nouveau=avant.get(champ), depuis=e["id"],
                         objet=objet)
    if "variante_cle" in changes:
        conn.execute("UPDATE releve SET variante_cle = ? WHERE id = ?",
                     (avant.get("variante_cle"), rid))
    if "qualificatifs" in changes:
        conn.execute("DELETE FROM releve_qualificatif WHERE releve_id = ?", (rid,))
        conn.executemany("INSERT INTO releve_qualificatif (releve_id, qualificatif_cle) "
                         "VALUES (?, ?)", [(rid, q) for q in avant.get("qualificatifs") or []])
    if "precision" in changes:
        conn.execute("UPDATE releve SET precision = ? WHERE id = ?",
                     (avant.get("precision"), rid))
    if "lien_region_id" in changes:
        conn.execute("UPDATE releve SET lien_region_id = ?, lien_texte = ? WHERE id = ?",
                     (avant.get("lien_region_id"), avant.get("lien_texte"), rid))
    if "mots" in changes:
        conn.execute("DELETE FROM releve_mot WHERE releve_id = ?", (rid,))
        conn.executemany("INSERT INTO releve_mot (releve_id, position, rang, forme) "
                         "VALUES (?, ?, ?, ?)",
                         [(rid, i, rang, forme) for i, (rang, forme)
                          in enumerate(zip(avant.get("mots") or [], avant.get("formes") or []))])
        conn.execute("UPDATE releve SET texte_ancre = ? WHERE id = ?",
                     (avant.get("texte_ancre"), rid))
    # Qui l'avait modifié, et quand, revient avec les valeurs (contre-relecture n°2) : une
    # retouche annulée ne laisse pas le relevé d'un autre passer pour le sien. Un acte d'avant
    # que la charge ne le porte n'y touche pas.
    if changes and "modifie_par" in avant:
        conn.execute("UPDATE releve SET modifie_par = ?, modifie_le = ? WHERE id = ?",
                     (avant.get("modifie_par"), avant.get("modifie_le"), rid))


def _rendre_releves(conn, snap) -> int:
    """Les relevés et les passes que la suppression d'une région avait emportés par CASCADE,
    rendus avec elle sous leurs identifiants (R10 ; « Supprimer une région supprime ses
    relevés, Ctrl+Z les rend »). Ne reviennent pas — comptés, sans rien dire d'eux : ceux
    dont la grille n'est plus active dans leur version, ou dont l'entrée a disparu, ou qu'une
    contrainte refuse. Le patron de `liens_non_rendus`."""
    import releves
    manque = 0
    for n in _noeuds(snap):
        for r in n.get("releves", []):
            if not (_activation_du_releve(conn, r) and _entree_existe(conn, r)):
                manque += 1
                continue
            conn.execute("SAVEPOINT rendre_un_releve")
            try:
                releves.rendre(conn, r)
                conn.execute("RELEASE rendre_un_releve")
            except sqlite3.IntegrityError:
                conn.execute("ROLLBACK TO rendre_un_releve")
                conn.execute("RELEASE rendre_un_releve")
                manque += 1
        for p in n.get("passes", []):
            if not _activation_du_releve(conn, {**p, "region_id": n["id"]}):
                manque += 1
                continue
            conn.execute("INSERT OR IGNORE INTO passe (id, region_id, planche_id, grille_id, "
                         "version_id, rubrique_cle, par, le, recopiee) "
                         "VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?)",
                         (p["id"], n["id"], p["grille_id"], p["version_id"],
                          p["rubrique_cle"], p["par"], p["le"], p.get("recopiee", 0)))
    return manque


# --------------------------------------------------------------------------- #
# Aiguillage + orchestration
# --------------------------------------------------------------------------- #
def _inverser(conn, e, voit=None) -> int:
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
                _garder_creation(conn, cid, apres, depuis=e["id"], agent=e["agent"], voit=voit)
                _supprimer_region(conn, cid)
            elif t == "modification":
                _inverser_modification_region(conn, cid, avant, apres, voit, depuis=e["id"])
            elif t == "suppression":
                _recreer_region_profond(conn, avant, depuis=e["id"])
            return cid
        if table == "annotations":        # cible_id = region_id (v20 : stable, cf. put_annotation)
            _inverser_annotation(conn, cid, avant, apres, depuis=e["id"])
            return cid
        if table in _RELEVES:              # cible_id = la région, ou la planche
            _inverser_releve(conn, e, avant, apres)
            return cid
        if table in _LIENS:                # cible_id = region_id
            if t == "lien" and avant is None:
                _garder_lien(conn, e, laisse=apres["personnage_id"], rendu=None)
                _retirer_lien(conn, table, cid)
            else:                         # lien (avec avant) ou delien → rétablir l'ancien lien
                # Le « passé » d'un type qui ne montre plus le lien prime sur la garde : il ne
                # dit rien de ce que la région porte (ANN-8).
                if not _montre(conn, table, cid):
                    raise Irretablissable()
                _garder_lien(conn, e,
                             laisse=(apres or {}).get("personnage_id") if t == "lien" else None,
                             rendu=avant["personnage_id"])
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
# Les identifiants de `regions` et de `planches` se RÉATTRIBUAIENT jusqu'à la v30 (pas
# d'`AUTOINCREMENT`) : la région créée après la suppression de celle d'identifiant le plus
# haut reprenait cet identifiant, dans n'importe quelle collection. Depuis la v30 ils ne
# reviennent plus (COL-3), compteur amorcé au-dessus de ce que le journal nommait ; la garde
# reste, pour les actes d'avant la v30 et comme défense en profondeur — un identifiant
# rendu par une transaction défaite, une ligne posée à la main. Le `cible_id` d'un acte
# pouvait donc désigner un objet que son auteur n'a jamais touché. Filtrer par agent ne
# dit rien de l'objet : Ctrl+Z effaçait un locuteur de l'Incubateur au nom d'une collègue
# qui n'y entre pas, et le 409 de CONC-3 lui rendait le texte de la région et le login de son auteur
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
    if e["cible_table"] == "releve_planche":
        # ANN-7 — la cible est la PLANCHE (la surface) : présente, et d'un album né avant
        # l'acte. Ses identifiants ne reviennent plus depuis la v30.
        pl = e["cible_id"]
        return (conn.execute("SELECT 1 FROM planches WHERE id = ?", (pl,)).fetchone()
                is not None and not _album_ne_apres(conn, pl, e))
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


def planches_remises_a_zero(conn, e) -> list:
    """Les planches où l'acte `e` a porté et qui ont été REMISES À ZÉRO depuis — elles, ou
    leur album entier : vide si aucune.
    COL-3, tranche 3b (E8, Hugo, 2026-10-20) : repartir de zéro est UN acte sous le document
    (`socle._repartir`, charge `repartir`), non annulable, qui efface d'un geste les couches
    au-dessus d'un cran ; Ctrl+Z ne remonte pas au-delà. Défaire un acte d'avant ferait
    revenir une couche de travail sous une copie qu'on a voulue vide — ou buterait sur une
    région qui n'existe plus. Le cinquième témoin, à côté de ceux de `_meme_objet` : il ne
    regarde pas l'objet, il regarde ce qui s'est passé SUR son album depuis l'acte.

    Une remise à zéro d'une PLANCHE (`repartir.planche_id`) ne vaut que pour les actes de
    cette planche ; celle de l'album, pour tous les siens. Les planches de l'acte sont celles
    de `lieux` : la planche d'une suppression à rétablir, ou celle de la région — présente,
    ou celle où elle vivait au moment de l'acte, lue au journal (`_planche_au_moment`) : une
    région que la remise à zéro a EFFACÉE n'a plus de ligne, et c'est le cas même que le
    témoin doit reconnaître (relecture croisée de la 3b, constat 4)."""
    ou = lieux(conn, e)
    planches = {pl for pl in ou["planches"] if pl is not None}
    for rid in ou["regions"]:
        r = conn.execute("SELECT planche_id FROM regions WHERE id = ?", (rid,)).fetchone()
        if r is not None:
            planches.add(r[0])
        alors = _planche_au_moment(conn, rid, e)
        if alors is not None:
            planches.add(alors)
    remises = []
    for pl in sorted(planches):
        a = conn.execute("SELECT album_id FROM planches WHERE id = ?", (pl,)).fetchone()
        if a is not None and conn.execute(
                "SELECT 1 FROM evenement WHERE cible_table = 'document' "
                "AND type = 'modification' AND id > ? AND json_valid(apres) "
                "AND json_extract(apres, '$.repartir') IS NOT NULL "
                "AND json_extract(apres, '$.album_id') = ? "
                "AND (json_extract(apres, '$.repartir.planche_id') IS NULL "
                "     OR json_extract(apres, '$.repartir.planche_id') = ?) LIMIT 1",
                (e["id"], a[0], pl)).fetchone():
            remises.append(pl)
    return remises


def _personnage_rendu(e) -> Optional[int]:
    """Le personnage que l'inverse d'un lien REPOSERAIT (lien qui en remplaçait un, ou
    retrait), ou None."""
    if e["cible_table"] in _LIENS:
        avant = _charge(e["avant"])
        if avant and avant.get("personnage_id") is not None:
            return avant["personnage_id"]
    return None


def _personnage_ne_apres(conn, personnage_id, e) -> bool:
    """Le personnage a-t-il été créé APRÈS l'acte ? Alors il a repris l'identifiant de
    celui que l'acte avait retiré (relecture croisée, S2). L'acte n'en garde que
    l'identifiant, et le journal ne trace ni la création ni la suppression d'un
    personnage : sa `date_creation`, que rien ne réécrit, est le seul témoin. Même limite
    que l'album : dans la même seconde, rien n'est vu."""
    row = conn.execute("SELECT date_creation FROM personnages WHERE id = ?",
                       (personnage_id,)).fetchone()
    return bool(row and row["date_creation"] and e["date"] and row["date_creation"] > e["date"])


def lieux(conn, e) -> dict:
    """Où l'inverse de `e` ÉCRIRAIT : `{"regions": [...], "planches": [...],
    "personnages": [...]}` — le dernier pour un personnage qu'il reposerait, que l'agent
    doit VOIR (la règle des personnages : visibles par leurs apparitions).

    Une suppression se rétablit DANS une planche — la région n'existe pas encore ; tout
    autre acte s'inverse sur sa région. C'est ce que la route éprouve avec les accesseurs
    gardés, en écriture, sous la portée de la requête."""
    if e["type"] == "suppression" and e["cible_table"] == "regions":
        return {"regions": [], "planches": _planches_instantane(_charge(e["avant"]) or {}),
                "personnages": []}
    if e["cible_table"] == "releve_planche":     # ANN-7 : un relevé de la surface
        return {"regions": [], "planches": [e["cible_id"]], "personnages": []}
    return {"regions": [e["cible_id"]], "planches": [], "personnages": []}


def apercu_de(e, voit=None) -> str:
    """La phrase d'un acte donné, pour la réponse de « Passer ce geste »."""
    return _description(e, voit)


def voit_valeur(ecrivable):
    """La question « l'agent voit-il cette valeur de situation ? », tirée d'`ecrivable` —
    celle de la route qui la pose (`_affecter` : la voir suffit)."""
    return lambda v: ecrivable({"regions": [], "planches": [], "personnages": [], "valeurs": [v]})


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
    voit = voit_valeur(ecrivable)
    # COL-3, tranche 3b (E8) — une remise à zéro de l'album, ou de la planche, depuis l'acte :
    # Ctrl+Z ne remonte pas au-delà (`planches_remises_a_zero`). Lu AVANT l'objet et ses
    # lieux : la création d'une région que la remise à zéro a effacée n'a plus d'objet, et
    # tombait dans la première phrase, « n'est plus à votre portée », pour un acte que
    # l'agent peut toujours lire (relecture croisée de la 3b, constat 4). La seconde phrase
    # ne se dit qu'à qui écrit encore la planche remise à zéro : à tout autre, elle
    # apprendrait ce qui s'est passé sur un album qu'il ne lit peut-être plus.
    remises = planches_remises_a_zero(conn, e)
    if remises and ecrivable({"regions": [], "planches": remises, "personnages": []}):
        raise NeSAnnulePlus(e, PHRASE_IRRETABLISSABLE, voit)
    if remises or not _meme_objet(conn, e) or not ecrivable(lieux(conn, e)):
        raise NeSAnnulePlus(e, voit=voit)
    # Le personnage qu'on reposerait : créé après l'acte, ou invisible pour l'agent, ce n'est
    # plus celui de l'acte, ou pas un à lui montrer. Seconde phrase : elle ne dit pas s'il
    # existe. Absent, c'est la clé étrangère qui le dira, pendant l'inversion.
    perso = _personnage_rendu(e)
    if perso is not None and conn.execute("SELECT 1 FROM personnages WHERE id = ?",
                                          (perso,)).fetchone():
        if _personnage_ne_apres(conn, perso, e) or not ecrivable(
                {"regions": [], "planches": [], "personnages": [perso]}):
            raise NeSAnnulePlus(e, PHRASE_IRRETABLISSABLE, voit)
    # ANN-8 — une suppression rend aussi les liens de ses régions, et un changement de type
    # le locuteur qu'il avait emporté : ceux qui sont rendables.
    # Celui qu'un autre a posé depuis n'est pas écrasé : `_garder_liens_du_type`, dans
    # l'inversion, avant toute écriture (CONC-3).
    a_rendre = _liens_a_rendre(e)
    rendables = (_liens_rendables(conn, e, a_rendre, ecrivable)
                 if a_rendre is not None else None)
    non_rendus = 0
    perdus = []                    # ANN-8 : les tags qui ne se résolvent plus (`_tag_a_rendre`)
    jeton = _CONTEXTE_TAGS.set({"perdus": perdus, "lisible": lambda tag_id: ecrivable(
        {"regions": [], "planches": [], "personnages": [], "tags": [tag_id]})})
    releves_non_rendus = None
    try:
        region_id = _inverser(conn, e, voit)
        if rendables is not None:
            try:
                non_rendus = _rendre_liens(conn, a_rendre, rendables)
            except sqlite3.IntegrityError as exc:
                raise Irretablissable() from exc
        if e["type"] == "suppression" and e["cible_table"] == "regions":
            releves_non_rendus = _rendre_releves(conn, a_rendre)
    except Irretablissable:
        raise NeSAnnulePlus(e, PHRASE_IRRETABLISSABLE, voit)
    except conflit.Perime as exc:
        # ANN-8 — l'acte refusé, tel que l'annulation l'a relu sous le verrou d'écriture :
        # c'est lui que « Passer ce geste » doit désigner (`passable`, dans la route).
        exc.evenement = e
        raise
    finally:
        _CONTEXTE_TAGS.reset(jeton)
    if e["cible_table"] == "releve_planche":     # la cible est la planche elle-même
        planche_id, region_id = e["cible_id"], None
    else:
        planche_id = _planche_de(conn, region_id, e)
    journal.journaliser(conn, "annulation", "evenement", e["id"],
                        avant={"acte": e["type"], "cible_table": e["cible_table"],
                               "cible_id": e["cible_id"]})
    res = {"evenement_id": e["id"], "acte": e["type"], "cible_table": e["cible_table"],
           "region_id": region_id, "planche_id": planche_id,
           "description": _description(e, voit)}
    if rendables is not None:
        res["liens_non_rendus"] = non_rendus
    if perdus:
        res["tags_non_rendus"] = len(perdus)        # ANN-8 : un tag supprimé depuis l'acte
    if releves_non_rendus:
        res["releves_non_rendus"] = releves_non_rendus   # ANN-7 : grille désactivée depuis
    return res
