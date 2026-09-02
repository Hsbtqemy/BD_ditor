"""Recherche plein texte (FTS5) et statistiques de corpus.  ARCH-1.

Premier bloc sorti de `main.py`, et choisi pour cela : 243 lignes qui ne dépendent que de
CINQ noms partagés — le minimum mesuré des dix-huit sections. Éprouver le patron sur le
bloc le moins couplé coûte moins cher que de le découvrir sur le plus gros.

Deux critères ont décidé de l'ordre d'extraction, et le second ne se voit pas :

  · le COUPLAGE, mesuré (5 à 20 noms de `main.py` par bloc, presque toujours les mêmes) ;
  · les noms que les tests remplacent PAR `main` — `monkeypatch.setattr(main, "…")`. Un
    bloc qui en contient ne peut pas déménager sans réécrire ces tests : la route y
    chercherait le nom dans SON module, pas dans `main`, et le remplacement cesserait
    d'agir en silence. Segmentation, ShareDocs, Sauvegarde, Jobs et Santé sont épinglés
    par là ; Recherche, Personnages, Lexique et Analyse ne le sont pas. C'est ce qui rend
    ces quatre-là déplaçables sans toucher un test — la condition que pose ARCH-1.

Le cloisonnement (AUTH-2) ne change pas d'un iota : `_recherche_rows` porte toujours la
portée en paramètre obligatoire, et c'est toujours le seul endroit qui referme le piège de
la table FTS dénormalisée.
"""
from __future__ import annotations

import csv
import io
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

import autorisation
from config import STATUTS
from database import citations_regions
from pipeline import nlp

from socle import _csv_response, _csv_safe, _norm_tag, _rows, db, portee_courante

router = APIRouter()


def _recherche_rows(conn, portee, q, album, type, tags, pos, lemme, morph, provenance, limit,
                    tag_scope="propre", personnage=None, attributs=None):
    """Construit et exécute la requête de recherche (régions + contexte, tags joints).
    Partagé par /api/recherche (JSON) et l'export CSV — une seule logique de requête.

    AUTH-2 — la portée est un paramètre OBLIGATOIRE, et c'est ici que se referme le piège
    le plus vicieux du dépôt : la table FTS `recherche` est DÉNORMALISÉE et globale (elle
    agrège OCR + note + tags + lemmes) et ne porte aucune trace d'album ni de collection.
    Une requête plein texte non filtrée renverrait donc le contenu de tout le corpus,
    quelle que soit la rigueur des routes de lecture par identifiant. Le filtre passe par
    la jointure `albums a` déjà présente, pas par la table FTS.
    """
    where, params = [], []
    ou, params_portee = portee.clause_album("a.id")
    where.append(ou)
    params.extend(params_portee)

    base = (
        "SELECT r.id AS region_id, r.type, r.x, r.y, r.w, r.h, r.ocr_texte, "
        "       p.id AS planche_id, p.numero AS planche_numero, "
        "       p.chemin_web, p.largeur_px, p.hauteur_px, "       # pour l'aperçu en place
        "       a.id AS album_id, a.titre AS album_titre, "
        "       an.note AS note "
        "FROM regions r "
        "JOIN planches p ON p.id = r.planche_id "
        "JOIN albums a ON a.id = p.album_id "
        "LEFT JOIN annotations an ON an.region_id = r.id "
    )

    if q.strip():
        # (1) PRÉFIXE échappé sur le texte brut (ET implicite) : « otage » → « otages ».
        #     Insensible aux accents (tokenizer FTS remove_diacritics).
        raw = " ".join('"' + t.replace('"', '""') + '"*' for t in q.split())
        # (2) LEMMES : on lemmatise aussi la requête et on la matche sur la colonne
        #     `lemmes` → attrape ce que le préfixe rate (cheval↔chevaux, conjugaisons,
        #     élisions). Moteur optionnel : si spaCy absent, lemmatise() renvoie ""
        #     → on garde seulement (1) (repli propre).
        lemmes = nlp.lemmatise(q).split()
        if lemmes:
            lemma_expr = " ".join('"' + l.replace('"', '""') + '"' for l in lemmes)
            match_expr = f"({raw}) OR (lemmes : ({lemma_expr}))"
        else:
            match_expr = raw
        base += "JOIN recherche rch ON rch.region_id = r.id "
        where.append("recherche MATCH ?")
        params.append(match_expr)

    if album is not None:
        where.append("a.id = ?")
        params.append(album)
    if type:
        where.append("r.type = ?")
        params.append(type)
    if tags:
        # un paramètre `tags` par tag (robuste aux virgules dans les labels).
        # tag_scope : 'propre' = la région porte le tag ; 'herite' = la région OU sa
        # case parente — aligné sur /api/analyse/* pour que la descente aux preuves
        # (drill Exploration → Recherche) ne perde pas les tokens tagués au niveau case.
        cible = ("a2.region_id = r.id" if tag_scope == "propre"
                 else "a2.region_id IN (r.id, r.parent_id)")
        wanted = [_norm_tag(t) for t in tags if _norm_tag(t)]
        for label in wanted:
            where.append(
                "EXISTS (SELECT 1 FROM annotation_tags at "
                "        JOIN tags tg ON tg.id = at.tag_id "
                "        JOIN annotations a2 ON a2.id = at.annotation_id "
                f"       WHERE {cible} AND tg.label = ?)"
            )
            params.append(label)

    # Facettes GRAMMATICALES (lot 3) : la région contient-elle un token (valeur
    # EFFECTIVE) répondant aux critères ? EXISTS sur tokens_effectifs, scopé à la région.
    if pos or lemme or morph or provenance:
        tw, tp = [], []
        if pos:
            tw.append("te.pos = ?"); tp.append(pos.upper())
        if lemme:
            tw.append("te.lemme = ?"); tp.append(lemme.lower())
        if morph:
            tw.append("te.morph LIKE ?"); tp.append(f"%{morph}%")
        if provenance:
            tw.append("te.provenance = ?"); tp.append(provenance)
        where.append("EXISTS (SELECT 1 FROM tokens_effectifs te "
                     "WHERE te.region_id = r.id AND " + " AND ".join(tw) + ")")
        params.extend(tp)

    # Facettes ANN-2 : locuteur de la bulle, et attribut (profil du locuteur OU situation
    # de la case) — alignées sur /api/analyse/* pour que le drill Exploration→Recherche colle.
    if personnage is not None:
        where.append("EXISTS (SELECT 1 FROM bulle_locuteur bl "
                     "WHERE bl.region_id = r.id AND bl.personnage_id = ?)")
        params.append(personnage)
    for vid in (attributs or []):
        where.append(
            "(EXISTS (SELECT 1 FROM bulle_locuteur bl JOIN personnage_attribut pa "
            "         ON pa.personnage_id = bl.personnage_id "
            "         WHERE bl.region_id = r.id AND pa.valeur_id = ?) "
            " OR EXISTS (SELECT 1 FROM region_attribut ra "
            "            WHERE ra.region_id IN (r.id, r.parent_id) AND ra.valeur_id = ?))")
        params.extend([vid, vid])

    sql = base
    if where:
        sql += "WHERE " + " AND ".join(where) + " "
    sql += "ORDER BY p.numero, r.ordre LIMIT ?"
    params.append(limit)

    try:
        results = _rows(conn.execute(sql, params))
    except sqlite3.OperationalError as exc:
        raise HTTPException(400, f"Requête de recherche invalide : {exc}")

    # Joint les tags de chaque résultat.
    for row in results:
        row["tags"] = [t["label"] for t in _rows(conn.execute(
            """SELECT tg.label FROM annotation_tags at
               JOIN tags tg ON tg.id = at.tag_id
               JOIN annotations an ON an.id = at.annotation_id
               WHERE an.region_id = ? ORDER BY tg.label""",
            (row["region_id"],),
        ))]
        row["url_web"] = "/" + row["chemin_web"] if row["chemin_web"] else None
    cits = citations_regions(conn, [row["region_id"] for row in results])
    for row in results:
        row["citation"] = cits.get(row["region_id"])
    return results


@router.get("/api/recherche")
def recherche(q: str = "", album: Optional[int] = None,
              type: Optional[str] = None, tags: Optional[list[str]] = Query(None),
              pos: Optional[str] = None, lemme: Optional[str] = None,
              morph: Optional[str] = None, provenance: Optional[str] = None,
              tag_scope: str = "propre",
              personnage: Optional[int] = None, attributs: Optional[list[int]] = Query(None),
              limit: int = 100, conn: sqlite3.Connection = Depends(db),
              portee: autorisation.Portee = Depends(portee_courante)):
    limit = max(1, min(limit, 500))   # borne : évite LIMIT -1 (= tout le corpus) / DoS
    results = _recherche_rows(conn, portee, q, album, type, tags, pos, lemme, morph,
                              provenance, limit, tag_scope, personnage, attributs)
    return {"q": q, "count": len(results), "results": results}


@router.get("/api/recherche/export.csv")
def recherche_export(q: str = "", album: Optional[int] = None,
                     type: Optional[str] = None, tags: Optional[list[str]] = Query(None),
                     pos: Optional[str] = None, lemme: Optional[str] = None,
                     morph: Optional[str] = None, provenance: Optional[str] = None,
                     tag_scope: str = "propre",
                     personnage: Optional[int] = None, attributs: Optional[list[int]] = Query(None),
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Export CSV du jeu de résultats courant (mêmes critères que /api/recherche).
    Borne haute relevée (5000) : on exporte le jeu trouvé, pas seulement l'aperçu."""
    results = _recherche_rows(conn, portee, q, album, type, tags, pos, lemme, morph,
                              provenance, 5000, tag_scope,
                              personnage, attributs)
    buf = io.StringIO()
    # `planche` = numéro ÉDITORIAL (cité), `citation` = repère complet « pl·c(·b) » ;
    # le CSV est l'artefact que le chercheur emporte pour citer. Cf.
    # docs/numerotation-et-citation.md.
    cols = ["album", "planche", "citation", "region_id", "type",
            "ocr_texte", "note", "tags"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in results:
        cit = r.get("citation") or {}
        planche = cit.get("planche")
        w.writerow({"album": _csv_safe(r["album_titre"]),
                    "planche": planche if planche is not None else "",
                    "citation": cit.get("texte", ""),
                    "region_id": r["region_id"], "type": r["type"],
                    "ocr_texte": _csv_safe(r["ocr_texte"] or ""),
                    "note": _csv_safe(r["note"] or ""),
                    "tags": _csv_safe("|".join(r["tags"]))})
    return _csv_response(buf.getvalue(), "recherche.csv")


@router.get("/api/corpus")
def corpus_stats(conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Compteurs globaux du corpus (pour l'aperçu de la page de recherche)."""
    # AUTH-2 : des compteurs GLOBAUX diraient combien d'albums et de planches existent
    # ailleurs — la composition du corpus fuit par les nombres aussi bien que par les
    # titres. Chaque sous-requête est donc rattachée à son album, puis filtrée.
    ou, pp = portee.clause_album("alb.id")
    oup, _ = portee.clause_album("pl.album_id")
    our, _ = portee.clause_album("plr.album_id")
    ou_tag, p_tag = portee.clause_terme("t.collection_id")
    row = conn.execute(
        f"""SELECT
             (SELECT COUNT(*) FROM albums alb WHERE {ou})   AS albums,
             (SELECT COUNT(*) FROM planches pl WHERE {oup}) AS planches,
             (SELECT COUNT(*) FROM regions r
                JOIN planches plr ON plr.id = r.planche_id WHERE {our})  AS regions,
             (SELECT COUNT(*) FROM annotations an JOIN regions r ON r.id = an.region_id
                JOIN planches plr ON plr.id = r.planche_id WHERE {our}) AS annotees,
             (SELECT COUNT(*) FROM regions r
                JOIN planches plr ON plr.id = r.planche_id
                WHERE {our} AND TRIM(COALESCE(r.ocr_texte, '')) <> '') AS transcrites,
             -- `tags` suit la règle du VOCABULAIRE et non celle des données : visible
             -- s'il est global ou local à une collection qu'on lit (cf. clause_terme).
             (SELECT COUNT(*) FROM tags t WHERE {ou_tag}) AS tags,
             (SELECT COUNT(*) FROM planches pl
                WHERE {oup} AND pl.validee IS NOT NULL) AS validees""",
        # 5 clauses d'album, puis celle des tags, puis la 6e d'album — dans l'ORDRE
        # d'apparition dans le SQL ci-dessus.
        [*pp * 5, *p_tag, *pp],
    ).fetchone()
    res = dict(row)
    # Distribution des planches par statut (pour la barre d'avancement du corpus).
    res["statuts"] = {s: 0 for s in STATUTS}
    for r in conn.execute(
            f"SELECT pl.statut, COUNT(*) AS n FROM planches pl WHERE {oup} "
            "GROUP BY pl.statut", pp):
        if r["statut"] in res["statuts"]:
            res["statuts"][r["statut"]] = r["n"]
    return res
