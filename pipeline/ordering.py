"""Ordre de lecture des régions (sens occidental : rangées haut→bas, puis
gauche→droite dans chaque rangée) et réordonnancement.

`ordre` est stocké comme RANG RELATIF AUX FRÈRES (régions de même parent) :
  • les régions de premier niveau (cases + bulles orphelines, parent NULL) sont
    classées ensemble ;
  • les bulles d'une case sont classées entre elles.
La séquence de lecture globale (transcription) se reconstruit par parcours de
l'arbre dans cet ordre. Ce schéma rend le déplacement manuel trivial (échange de
deux frères) et reste cohérent avec l'affichage en arbre.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict


def reading_order(boxes: list[dict]) -> list[dict]:
    """Trie des boîtes (dicts avec x, y, w, h) en ordre de lecture occidental.

    Regroupe en RANGÉES par proximité du bord HAUT (tolérance = 0,4 × hauteur
    médiane), trie les rangées de haut en bas, puis chaque rangée de gauche à
    droite. Le bord haut est plus fiable que le centre : les cases d'une même
    rangée s'alignent en haut même quand leurs hauteurs diffèrent (une grande
    case qui enjambe deux rangées ne capture alors pas les cases du dessous).
    """
    if not boxes:
        return []
    # Coordonnées défensives : une région manuelle peut avoir x/y/w/h NULL
    # (PATCH partiel) ; on les traite comme 0 plutôt que de lever un TypeError.
    def _y(b): return b["y"] or 0
    def _x(b): return b["x"] or 0
    items = sorted(boxes, key=lambda b: (_y(b), _x(b)))
    heights = sorted((b["h"] or 0) for b in items)
    med_h = heights[len(heights) // 2] or 1
    tol = med_h * 0.4
    rows: list[dict] = []
    for b in items:
        for row in rows:
            if abs(_y(b) - row["top"]) <= tol:
                row["items"].append(b)
                row["top"] = min(row["top"], _y(b))
                break
        else:  # aucune rangée compatible : on en ouvre une nouvelle
            rows.append({"top": _y(b), "items": [b]})
    rows.sort(key=lambda r: r["top"])
    out: list[dict] = []
    for row in rows:
        row["items"].sort(key=_x)
        out.extend(row["items"])
    return out


def reorder_planche(conn: sqlite3.Connection, planche_id: int) -> dict:
    """Recalcule `ordre` (rang per-niveau) de toutes les régions d'une planche.

    Chaque fratrie (régions de même parent) est classée indépendamment en ordre
    de lecture et reçoit des rangs 1..N. Renvoie {'planche_id', 'regions'}.
    """
    rows = conn.execute(
        "SELECT id, parent_id, x, y, w, h FROM regions WHERE planche_id = ?",
        (planche_id,),
    ).fetchall()
    groups: dict = defaultdict(list)
    for r in rows:
        groups[r["parent_id"]].append(dict(r))
    n = 0
    for group in groups.values():
        for rank, r in enumerate(reading_order(group), start=1):
            conn.execute("UPDATE regions SET ordre = ? WHERE id = ?", (rank, r["id"]))
            n += 1
    return {"planche_id": planche_id, "regions": n}


def move_region(conn: sqlite3.Connection, region_id: int, sens: str) -> dict:
    """Déplace une région d'un cran parmi ses frères ('haut' ou 'bas').

    Réassigne des rangs propres (1..N) à la fratrie avec les deux éléments
    permutés. Renvoie {'moved': bool, 'region_id', ['ordre']}. Lève ValueError
    si la région est introuvable ou le sens invalide.
    """
    if sens not in ("haut", "bas"):
        raise ValueError(f"Sens invalide : {sens!r}")
    r = conn.execute(
        "SELECT id, parent_id, planche_id FROM regions WHERE id = ?", (region_id,)
    ).fetchone()
    if r is None:
        raise ValueError(f"Région {region_id} introuvable")
    sibs = conn.execute(
        "SELECT id FROM regions WHERE planche_id = ? AND parent_id IS ? "
        "ORDER BY ordre, id",
        (r["planche_id"], r["parent_id"]),
    ).fetchall()
    ids = [s["id"] for s in sibs]
    i = ids.index(region_id)
    j = i - 1 if sens == "haut" else i + 1
    if j < 0 or j >= len(ids):
        return {"moved": False, "region_id": region_id}   # déjà en bout de fratrie
    ids[i], ids[j] = ids[j], ids[i]
    for rank, sid in enumerate(ids, start=1):
        conn.execute("UPDATE regions SET ordre = ? WHERE id = ?", (rank, sid))
    return {"moved": True, "region_id": region_id, "ordre": j + 1}
