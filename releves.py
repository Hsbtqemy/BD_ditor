"""Les RELEVÉS, côté données — l'instantané, le ré-ancrage, la restitution (ANN-7, tranche 1 ;
cadrage R6, R10, R11).

Ce que plusieurs couches lisent ou écrivent d'un relevé sans passer par ses routes : le
journal (l'instantané profond d'une région emporte ses relevés), l'annulation (rendre un
relevé sous son identifiant), la réindexation d'une région (le ré-ancrage de ses passages).
Ce module ne décide d'aucun droit — les routes (`routes/releves.py`) et l'annulation les
posent — et ne commite rien.
"""
from __future__ import annotations

import sqlite3

import mots


def qualificatifs_de(conn: sqlite3.Connection, releve_id: int) -> list:
    return [q[0] for q in conn.execute(
        "SELECT qualificatif_cle FROM releve_qualificatif WHERE releve_id = ? "
        "ORDER BY qualificatif_cle", (releve_id,))]


def instantane(conn: sqlite3.Connection, releve_id: int, *, profond: bool = False) -> dict:
    """L'état d'un relevé, pour le journal : ses colonnes, ses qualificatifs (triés), son
    passage — `mots` (les rangs, dans l'ordre) et `formes` —, et, `profond`, ses doutes et
    leur fil (une suppression : Ctrl+Z les rend). `releve_id` dans la charge : la cible au
    journal est la région ou la planche, que plusieurs relevés partagent."""
    r = conn.execute("SELECT * FROM releve WHERE id = ?", (releve_id,)).fetchone()
    if r is None:
        return {}
    passage = conn.execute("SELECT position, rang, forme FROM releve_mot WHERE releve_id = ? "
                           "ORDER BY position", (releve_id,)).fetchall()
    out = {"releve_id": r["id"], "region_id": r["region_id"], "planche_id": r["planche_id"],
           "grille_id": r["grille_id"], "version_id": r["version_id"],
           "entree_cle": r["entree_cle"], "variante_cle": r["variante_cle"],
           "precision": r["precision"], "lien_region_id": r["lien_region_id"],
           "lien_texte": r["lien_texte"], "texte_ancre": r["texte_ancre"], "une": r["une"],
           "origine_id": r["origine_id"], "auteur": r["auteur"], "cree_le": r["cree_le"],
           "modifie_par": r["modifie_par"], "modifie_le": r["modifie_le"],
           "qualificatifs": qualificatifs_de(conn, releve_id),
           "mots": [m["rang"] for m in passage], "formes": [m["forme"] for m in passage]}
    if profond:
        out["doutes"] = [
            {**dict(d), "messages": [dict(m) for m in conn.execute(
                "SELECT * FROM doute_message WHERE doute_id = ? ORDER BY id", (d["id"],))]}
            for d in conn.execute("SELECT * FROM doute WHERE releve_id = ? ORDER BY id",
                                  (releve_id,))]
    return out


def instantanes_de_la_region(conn: sqlite3.Connection, region_id: int) -> tuple[list, list]:
    """Les relevés (profonds) et les passes d'une région — ce que sa suppression emporte par
    CASCADE, et que Ctrl+Z doit rendre (R10)."""
    releves = [instantane(conn, r[0], profond=True) for r in conn.execute(
        "SELECT id FROM releve WHERE region_id = ? ORDER BY id", (region_id,))]
    passes = [dict(p) for p in conn.execute("SELECT * FROM passe WHERE region_id = ? "
                                            "ORDER BY id", (region_id,))]
    return releves, passes


def rendre(conn: sqlite3.Connection, snap: dict) -> None:
    """Recrée un relevé depuis son instantané profond, sous son identifiant — ses mots, ses
    qualificatifs, ses doutes et leur fil. Lève `sqlite3.IntegrityError` si quelque chose
    s'y oppose (l'identifiant, la cardinalité `une`, une clé) ; l'appelant décide."""
    conn.execute(
        "INSERT INTO releve (id, region_id, planche_id, grille_id, version_id, entree_cle, "
        "variante_cle, precision, lien_region_id, lien_texte, texte_ancre, une, origine_id, "
        "auteur, cree_le, modifie_par, modifie_le) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (snap["releve_id"], snap["region_id"], snap["planche_id"], snap["grille_id"],
         snap["version_id"], snap["entree_cle"], snap["variante_cle"], snap["precision"],
         snap["lien_region_id"], snap["lien_texte"], snap["texte_ancre"], snap["une"],
         snap.get("origine_id"), snap.get("auteur"), snap.get("cree_le"),
         snap.get("modifie_par"), snap.get("modifie_le")))
    conn.executemany("INSERT INTO releve_mot (releve_id, position, rang, forme) "
                     "VALUES (?, ?, ?, ?)",
                     [(snap["releve_id"], i, rang, forme)
                      for i, (rang, forme) in enumerate(zip(snap["mots"], snap["formes"]))])
    conn.executemany("INSERT INTO releve_qualificatif (releve_id, qualificatif_cle) "
                     "VALUES (?, ?)", [(snap["releve_id"], q) for q in snap["qualificatifs"]])
    for d in snap.get("doutes", []):
        conn.execute("INSERT INTO doute (id, releve_id, ouvert_par, ouvert_le, leve_par, "
                     "leve_le, issue) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (d["id"], snap["releve_id"], d["ouvert_par"], d["ouvert_le"],
                      d["leve_par"], d["leve_le"], d["issue"]))
        conn.executemany("INSERT INTO doute_message (id, doute_id, auteur, date, texte) "
                         "VALUES (?, ?, ?, ?, ?)",
                         [(m["id"], d["id"], m["auteur"], m["date"], m["texte"])
                          for m in d["messages"]])


def reancrer_releves(conn: sqlite3.Connection, region_id: int) -> int:
    """Le RÉ-ANCRAGE des relevés sur des mots d'une région, après un changement de son texte
    (R6 ; le patron de `database._reancrer_corrections`, à une différence près : l'ancien
    découpage n'est pas en base, d'où `texte_ancre`, le texte de l'ancrage). Appelé par
    `database.reindex_region`, le point unique où passe tout chemin qui change un texte.

    Pour chaque relevé dont le texte d'ancrage n'est plus celui de la zone, l'alignement
    (`mots.aligner`) de l'ancien découpage sur le nouveau :
    - tous les mots du passage RETROUVÉS, même déplacés : le passage suit — ses rangs et ses
      formes sont réécrits, son texte d'ancrage aussi ;
    - un mot disparu ou changé : RIEN n'est écrit. Le relevé reste ancré sur l'ancien texte,
      ce qui le rend « à revoir » (`releves_effectifs`, cause `texte_change`), et l'écran lit
      où chacun de ses mots est aujourd'hui (`rang_actuel`, null pour un mot perdu) — ses
      anciennes formes restent, pour qu'on voie ce qu'il désignait. Jamais perdu, jamais
      déplacé en silence ; et un Ctrl+Z du texte le rend normal sans rien réécrire.
    C'est l'écart, écrit, avec le cadrage (qui passait le rang d'un mot perdu à NULL) : la
    marque, posée, survivait au retour du texte, et le relevé restait « à revoir » après un
    Ctrl+Z. Rend le nombre de relevés ré-ancrés."""
    texte = conn.execute("SELECT ocr_texte FROM regions WHERE id = ?", (region_id,)).fetchone()
    if texte is None:
        return 0
    texte = texte[0] or ""
    n = 0
    decoupe = None
    for r in conn.execute("SELECT id, texte_ancre FROM releve WHERE region_id = ? "
                          "AND texte_ancre IS NOT NULL AND texte_ancre <> ?",
                          (region_id, texte)).fetchall():
        passage = conn.execute("SELECT position, rang FROM releve_mot WHERE releve_id = ?",
                               (r["id"],)).fetchall()
        correspondance = mots.aligner(r["texte_ancre"], texte)
        if not passage or any(m["rang"] is None or m["rang"] not in correspondance
                              for m in passage):
            continue
        decoupe = decoupe if decoupe is not None else mots.decouper(texte)
        for m in passage:
            neuf = correspondance[m["rang"]]
            conn.execute("UPDATE releve_mot SET rang = ?, forme = ? WHERE releve_id = ? "
                         "AND position = ?", (neuf, decoupe[neuf]["forme"], r["id"],
                                              m["position"]))
        conn.execute("UPDATE releve SET texte_ancre = ? WHERE id = ?", (texte, r["id"]))
        n += 1
    return n
