"""CONC-4 — l'empreinte d'une planche OUVERTE : dire « elle a changé ailleurs » sans recharger
ses régions.

Réécrit par Hugo le 2026-10-21 : ni temps réel ni rien — un SIGNAL. L'Atelier charge les
régions à l'ouverture d'une planche et ne les recharge plus ; une région créée, modifiée ou
supprimée ailleurs (autre personne, passe automatique) n'y apparaissait jamais. Il demande
désormais, de temps en temps et au retour sur l'onglet, cette empreinte, la compare à celle
qu'il avait, et propose « Actualiser » — sans rien recharger d'office.

**Une empreinte PAR RÉGION, pas une pour la planche.** L'écran doit distinguer ce qui a changé
AILLEURS de ce qu'il vient de changer lui-même : une empreinte globale bouge aussi à chaque
enregistrement de l'écran, et l'adopter après chacun absorbait le changement d'un autre
tombé dans le même intervalle — le cas ordinaire de deux personnes qui annotent ensemble
(la note part toutes les 500 ms). Par région, l'écran n'adopte que les régions qu'il a
touchées (`static/lib/signal-planche.js`).

**Ce qu'elle couvre** : ce que l'Atelier montre d'une région et que « Actualiser » rendrait —
type, géométrie, rattachement, rang parmi ses sœurs (l'arbre de structure), texte transcrit,
note, tags, locuteur, personnage montré, situation. Pas la provenance, ni la grammaire (le
dernier gagne, CONC-4). Le rang ne change que par « monter / descendre » (il échange deux
sœurs), « réordonner » et les passes automatiques ; après chacun de ces gestes, l'écran qui
les fait relit ses régions, donc reprend sa base : le rang de la voisine n'y est jamais un
faux signal. Une création prend le rang suivant sans toucher aux autres.

**Bornée comme la planche, et comme ce qu'on en LIT.** La route passe par l'accesseur gardé
de la planche (404 hors portée). Les tags et les valeurs de situation se filtrent comme à
l'écran (`clause_terme` — le terme ET sa dimension, `socle._attributs_de`) : une empreinte qui
compterait un tag local à une collection qu'on ne lit pas signalerait « changé » sans rien à
montrer, et dirait qu'un travail invisible bouge sur cette région.

Un condensé court (12 caractères hexadécimaux) : il ne sert qu'à comparer deux états de la
même région, et rien n'en sort qui ne soit déjà lisible par la route des régions.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict


def empreintes(conn: sqlite3.Connection, planche_id: int, portee) -> dict[str, str]:
    """{identifiant de région (texte) → condensé} pour toutes les régions de la planche."""
    ou_tag, p_tag = portee.clause_terme("t.collection_id")
    ou_val, p_val = portee.clause_terme("v.collection_id")
    ou_dim, p_dim = portee.clause_terme("d.collection_id")
    sur_la_planche = "JOIN regions r ON r.id = {}.region_id WHERE r.planche_id = ?"

    notes = dict(conn.execute(
        "SELECT a.region_id, a.note FROM annotations a " + sur_la_planche.format("a"),
        (planche_id,)).fetchall())
    tags = defaultdict(list)
    for rid, label in conn.execute(
            "SELECT a.region_id, t.label FROM annotations a "
            "JOIN annotation_tags at ON at.annotation_id = a.id JOIN tags t ON t.id = at.tag_id "
            "JOIN regions r ON r.id = a.region_id "
            f"WHERE r.planche_id = ? AND {ou_tag}", (planche_id, *p_tag)):
        tags[rid].append(label)
    locuteurs = dict(conn.execute(
        "SELECT x.region_id, x.personnage_id FROM bulle_locuteur x " + sur_la_planche.format("x"),
        (planche_id,)).fetchall())
    montres = dict(conn.execute(
        "SELECT x.region_id, x.personnage_id FROM personnage_presence x "
        + sur_la_planche.format("x"), (planche_id,)).fetchall())
    situations = defaultdict(list)
    for rid, vid in conn.execute(
            "SELECT x.region_id, v.id FROM region_attribut x "
            "JOIN attribut_valeur v ON v.id = x.valeur_id "
            "JOIN attribut_dimension d ON d.id = v.dimension_id "
            "JOIN regions r ON r.id = x.region_id "
            f"WHERE r.planche_id = ? AND {ou_val} AND {ou_dim}",
            (planche_id, *p_val, *p_dim)):
        situations[rid].append(vid)

    resultat = {}
    for r in conn.execute("SELECT id, type, x, y, w, h, parent_id, ordre, ocr_texte "
                          "FROM regions WHERE planche_id = ? ORDER BY id", (planche_id,)):
        rid = r[0]
        canon = [r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8] or "", notes.get(rid) or "",
                 sorted(tags.get(rid, [])), locuteurs.get(rid), montres.get(rid),
                 sorted(situations.get(rid, []))]
        brut = json.dumps(canon, ensure_ascii=False, separators=(",", ":"))
        resultat[str(rid)] = hashlib.sha1(brut.encode("utf-8")).hexdigest()[:12]
    return resultat
