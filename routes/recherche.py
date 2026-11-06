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

from fastapi import APIRouter, Depends, HTTPException

import autorisation
from config import STATUTS
from database import (citations_regions, est_bac_a_sable, sql_projet_d_album,
                      sql_region_sortante)
from pipeline import nlp

from socle import (_clause_lemme, _csv_response, _csv_safe, _get_projet,
                   _portee_d_export, _rows, _sql_annotee, db, portee_courante,
                   refuser_le_vocabulaire)

router = APIRouter()

# Les colonnes de l'index plein texte que la Recherche interroge (cf. `_recherche_rows`).
COLONNES_CHERCHEES = "ocr_texte note lemmes"


def _recherche_rows(conn, portee, q, album, type, pos, lemme, morph, provenance, limit,
                    personnage=None):
    """Construit et exécute la requête de recherche (régions + contexte).
    Partagé par /api/recherche (JSON) et l'export CSV — une seule logique de requête.

    AUTH-2 — la portée est un paramètre OBLIGATOIRE, et c'est ici que se referme le piège
    le plus vicieux du dépôt : la table FTS `recherche` est DÉNORMALISÉE et globale (elle
    agrège OCR + note + lemmes) et ne porte aucune trace d'album ni de collection.
    Une requête plein texte non filtrée renverrait donc le contenu de tout le corpus,
    quelle que soit la rigueur des routes de lecture par identifiant. Le filtre passe par
    la jointure `albums a` déjà présente, pas par la table FTS.

    COL-4 (S8) — ni bac à sable ni jeu, pour personne (`Portee.pour_le_corpus`).
    """
    portee = portee.pour_le_corpus()
    where, params = [], []
    ou, params_portee = portee.clause_album("a.id")
    where.append(ou)
    params.extend(params_portee)
    # Un DÉTAIL ne se cherche pas, et donc ne s'exporte pas (G17) : ce cœur sert l'écran ET
    # l'export CSV, et la tranche 4 décidera de ce qui compte et de ce qui sort.
    where.append(sql_region_sortante("r"))

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
        # ANN-7 — le préfixe ne cherche que dans les colonnes que nomme `COLONNES_CHERCHEES` :
        # une colonne de l'index qu'elle ne nomme pas n'est pas cherchée.
        raw = f"{{{COLONNES_CHERCHEES}}} : ({raw})"
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
    # Facettes GRAMMATICALES (lot 3) : la région contient-elle un token (valeur
    # EFFECTIVE) répondant aux critères ? EXISTS sur tokens_effectifs, scopé à la région.
    if pos or lemme or morph or provenance:
        tw, tp = [], []
        if pos:
            tw.append("te.pos = ?"); tp.append(pos.upper())
        if lemme:                               # exact, ou préfixe `otage*` (ANA-6)
            clause = _clause_lemme("te.lemme", lemme)
            if clause:
                tw.append(clause[0]); tp.extend(clause[1])
        if morph:
            tw.append("te.morph LIKE ?"); tp.append(f"%{morph}%")
        if provenance:
            tw.append("te.provenance = ?"); tp.append(provenance)
        # `tw` peut rester VIDE : un lemme réduit à « * » ne pose aucune clause. Sans
        # cette garde, la requête finissait en `WHERE … AND )` — une erreur de syntaxe.
        if tw:
            where.append("EXISTS (SELECT 1 FROM tokens_effectifs te "
                         "WHERE te.region_id = r.id AND " + " AND ".join(tw) + ")")
            params.extend(tp)

    # Facette ANN-2 : le locuteur de la zone de texte — alignée sur /api/analyse/* pour que
    # le drill Exploration→Recherche colle. (Le locuteur n'a pas besoin de la garde des
    # termes : il ne cherche que dans les régions qu'on lit, où un locuteur qu'on ne voit
    # pas n'apparaît par définition nulle part.) Le filtre par ATTRIBUT est parti avec le
    # basculement d'ANN-7, comme celui par tag.
    if personnage is not None:
        where.append("EXISTS (SELECT 1 FROM bulle_locuteur bl "
                     "WHERE bl.region_id = r.id AND bl.personnage_id = ?)")
        params.append(personnage)

    sql = base
    if where:
        sql += "WHERE " + " AND ".join(where) + " "
    sql += "ORDER BY p.numero, r.ordre LIMIT ?"
    params.append(limit)

    try:
        results = _rows(conn.execute(sql, params))
    except sqlite3.OperationalError as exc:
        raise HTTPException(400, f"Requête de recherche invalide : {exc}")

    for row in results:
        row["url_web"] = "/" + row["chemin_web"] if row["chemin_web"] else None
    cits = citations_regions(conn, [row["region_id"] for row in results])
    for row in results:
        row["citation"] = cits.get(row["region_id"])
    return results


def _sans_terme_cherchable(q: str) -> bool:
    """La requête contient-elle quelque chose que l'index puisse chercher ?  (C2)

    `???`, `...`, `++` renvoyaient zéro résultat sans un mot d'explication, et l'écran
    affichait « Aucun résultat » — la même phrase que pour une recherche parfaitement
    valide qui ne trouve rien. Les deux situations n'ont pourtant rien à voir : dans un
    cas le corpus ne contient pas ce qu'on cherche, dans l'autre on n'a rien cherché.

    Le mécanisme est en amont, dans `_recherche_rows` : la requête devient une PHRASE
    FTS5 (`"???"*`), et le tokenizer `unicode61` jette la ponctuation. La phrase est
    donc vide, et une phrase vide ne correspond à rien.

    **C'est le serveur qui répond, et non le client, parce que la règle appartient au
    TOKENIZER.** Le client pourrait la deviner avec une expression régulière — ce serait
    reproduire ailleurs une règle qui vit ici, exactement l'écart que le croisement
    (`x_tronque`) évite en renvoyant un drapeau plutôt qu'en laissant déduire.

    L'approximation restante est écrite : `isalnum()` couvre les catégories Unicode L* et
    N*, ce que `unicode61` retient par défaut. Un test l'épingle contre le VRAI moteur —
    tout ce que cette fonction déclare incherchable doit réellement ne rien trouver, y
    compris quand le corpus contient ces caractères à la lettre. L'inverse (une requête
    non signalée que FTS réduit tout de même à rien) reste possible et n'aggrave rien :
    on retombe alors sur l'ancien « Aucun résultat ».
    """
    return bool(q.strip()) and not any(c.isalnum() for c in q)


@router.get("/api/recherche", dependencies=[Depends(refuser_le_vocabulaire)])
def recherche(q: str = "", album: Optional[int] = None,
              type: Optional[str] = None,
              pos: Optional[str] = None, lemme: Optional[str] = None,
              morph: Optional[str] = None, provenance: Optional[str] = None,
              personnage: Optional[int] = None,
              limit: int = 100, conn: sqlite3.Connection = Depends(db),
              portee: autorisation.Portee = Depends(portee_courante)):
    limit = max(1, min(limit, 500))   # borne : évite LIMIT -1 (= tout le corpus) / DoS
    results = _recherche_rows(conn, portee, q, album, type, pos, lemme, morph,
                              provenance, limit, personnage)
    return {"q": q, "count": len(results), "results": results,
            "sans_terme": _sans_terme_cherchable(q)}


@router.get("/api/recherche/export.csv", dependencies=[Depends(refuser_le_vocabulaire)])
def recherche_export(q: str = "", album: Optional[int] = None,
                     type: Optional[str] = None,
                     pos: Optional[str] = None, lemme: Optional[str] = None,
                     morph: Optional[str] = None, provenance: Optional[str] = None,
                     personnage: Optional[int] = None,
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Export CSV du jeu de résultats courant (mêmes critères que /api/recherche).
    Borne haute relevée (5000) : on exporte le jeu trouvé, pas seulement l'aperçu.

    DROIT-2 — le fichier n'emporte que ce qu'on a le droit de SORTIR : la portée
    d'export, pas celle de lecture. L'écran peut donc montrer plus de résultats que le
    fichier n'en porte, et c'est exactement la décision : voir n'est pas emporter."""
    results = _recherche_rows(conn, _portee_d_export(portee), q, album, type, pos,
                              lemme, morph, provenance, 5000, personnage)
    buf = io.StringIO()
    # `planche` = numéro ÉDITORIAL (cité), `citation` = repère complet « pl·c(·b) » ;
    # le CSV est l'artefact que le chercheur emporte pour citer. Cf.
    # docs/numerotation-et-citation.md.
    # ANN-7 — la colonne `tags` est RETIRÉE, et non laissée vide (cadrage, « se tranchent
    # en route ») : une colonne toujours vide se lirait « aucun tag », pas « plus de tags ».
    cols = ["album", "planche", "citation", "region_id", "type",
            "ocr_texte", "note"]
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
                    "note": _csv_safe(r["note"] or "")})
    return _csv_response(buf.getvalue(), "recherche.csv")


@router.get("/api/corpus")
def corpus_stats(bac_a_sable: Optional[int] = None, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Compteurs globaux du corpus (pour l'aperçu de la page de recherche). COL-4 (S8) : ni
    bac à sable ni jeu.

    COL-4 — `bac_a_sable=<id>` : les compteurs de CE bac à sable, et de lui seul, pour la
    Bibliothèque quand son projet courant en est un (relevé sur la maquette, 2026-10-24 :
    « 0 albums » dans un bac à sable tout neuf). Les surfaces qui traversent les projets ne
    passent pas le paramètre et restent aveugles aux bacs. Borné comme le reste : 404 sur
    un projet qu'on ne nomme pas — le bac d'un autre, pour un administrateur comme pour
    tous (`Portee.clause_projet`) — ou qui n'est pas un bac à sable ; et chaque compte
    garde la clause de la portée, qui ne rend du bac que ce qu'on y lit."""
    if bac_a_sable is None:
        portee = portee.pour_le_corpus()
        dans, p_dans = "1", []
    else:
        _get_projet(conn, portee, bac_a_sable)
        if not est_bac_a_sable(conn, bac_a_sable):
            raise HTTPException(404, f"Projet {bac_a_sable} introuvable")
        dans = f"IN (SELECT _a.id FROM albums _a WHERE {sql_projet_d_album('_a')} = ?)"
        p_dans = [bac_a_sable]
    # AUTH-2 : des compteurs GLOBAUX diraient combien d'albums et de planches existent
    # ailleurs — la composition du corpus fuit par les nombres aussi bien que par les
    # titres. Chaque sous-requête est donc rattachée à son album, puis filtrée.
    ou, pp = portee.clause_album("alb.id")
    oup, _ = portee.clause_album("pl.album_id")
    our, _ = portee.clause_album("plr.album_id")
    if bac_a_sable is not None:
        ou, oup, our = (f"({ou}) AND alb.id {dans}", f"({oup}) AND pl.album_id {dans}",
                        f"({our}) AND plr.album_id {dans}")
        pp = [*pp, *p_dans]
    # « annotées » compte les RÉGIONS annotées — une note non vide ou un relevé (ANN-7, I4,
    # `socle._sql_annotee`) : la même règle que la coche de l'arbre et `nb_annotees`.
    annotee = _sql_annotee("r")
    row = conn.execute(
        f"""SELECT
             (SELECT COUNT(*) FROM albums alb WHERE {ou})   AS albums,
             (SELECT COUNT(*) FROM planches pl WHERE {oup}) AS planches,
             (SELECT COUNT(*) FROM regions r
                JOIN planches plr ON plr.id = r.planche_id WHERE {our})  AS regions,
             (SELECT COUNT(*) FROM regions r
                JOIN planches plr ON plr.id = r.planche_id
                WHERE {our} AND {annotee}) AS annotees,
             (SELECT COUNT(*) FROM regions r
                JOIN planches plr ON plr.id = r.planche_id
                WHERE {our} AND TRIM(COALESCE(r.ocr_texte, '')) <> '') AS transcrites,
             (SELECT COUNT(*) FROM planches pl
                WHERE {oup} AND pl.validee IS NOT NULL) AS validees""",
        # six clauses d'album, dans l'ordre d'apparition dans le SQL ci-dessus.
        [*pp * 6],
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
