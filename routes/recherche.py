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

import io
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

import autorisation
from config import STATUTS
from database import (citations_regions, est_bac_a_sable, sql_projet_d_album,
                      sql_region_sortante)
from pipeline import nlp
from sortie_csv import ecrivain_csv_dict

from socle import (_clause_lemme, _csv_response, _csv_safe, _get_projet,
                   _portee_d_export, _rows, _sql_annotee, db, portee_courante,
                   refuser_le_vocabulaire)

router = APIRouter()

# Les colonnes de l'index plein texte que la Recherche interroge (cf. `_recherche_rows`) :
# les dialogues, les notes, les ÉTIQUETTES — les libellés des relevés des grilles OUVERTES
# (ANN-7, J6, `database.sql_etiquettes`) — et les lemmes.
COLONNES_CHERCHEES = "ocr_texte note etiquettes lemmes"


# --------------------------------------------------------------------------- #
# Les RELEVÉS dans la Recherche (ANN-7, le mode libre ; J7, élargi par Hugo le 2026-11-06)
# --------------------------------------------------------------------------- #
# Le filtre « porte… » : `porte=<grille>/<sorte>/…`, répétable. Une valeur de `porte` est UN
# filtre ; deux filtres se combinent par « et » ; les dernières parties d'un filtre sont ses
# VALEURS, qui se combinent par « ou ». La barre oblique sépare, parce qu'aucun identifiant de
# grille ne la porte (`grille_ecriture.cle_donnee` la refuse, à l'import comme au formulaire).
#   <g>/entree/<e1>[/<e2>…]               une entrée (toute variante), l'une OU l'autre
#   <g>/variante/<e>/<v1>[/<v2>…]         l'entrée <e> posée avec l'une de ces variantes
#   <g>/rubrique/<r1>[/<r2>…]             une entrée rangée sous l'une de ces rubriques, ou
#                                         sous l'une de leurs sous-rubriques
#   <g>/qualificatif/<liste>/<q1>[/<q2>…] un relevé qui coche l'une de ces cases de la liste
# De N'IMPORTE QUELLE grille, ouverte ou fermée — celle qu'on peut lire (`clause_grille`,
# 404 sinon, comme sa fiche) ; une entrée se reconnaît par sa CLÉ, quelle que soit la version
# de son relevé (une rubrique se lit dans la version de chaque relevé). Les relevés de la
# PLANCHE n'y entrent pas : la Recherche rend des régions (l'héritance d'une case vers ses
# bulles attend la tranche 4).
SORTES_PORTE = ("entree", "variante", "rubrique", "qualificatif")
PORTE_FILTRES_MAX, PORTE_VALEURS_MAX = 20, 50
_PORTE_FORME = ("« porte » s'écrit <grille>/entree/<entrée>…, <grille>/variante/<entrée>/"
                "<variante>…, <grille>/rubrique/<rubrique>… ou <grille>/qualificatif/<liste>/"
                "<case>…")


def _lire_porte(valeur: str) -> dict:
    """Une valeur de `porte`, lue — `{grille_id, sorte, parent, valeurs}` —, ou 422 nommé."""
    parts = [p.strip() for p in str(valeur or "").split("/")]
    if len(parts) < 3 or not parts[0].isdigit() or parts[1] not in SORTES_PORTE \
            or any(not p for p in parts[2:]):
        raise HTTPException(422, f"{_PORTE_FORME} : « {valeur} » ne se lit pas.")
    sorte = parts[1]
    parent = None
    valeurs = parts[2:]
    if sorte in ("variante", "qualificatif"):
        if len(valeurs) < 2:
            raise HTTPException(422, f"{_PORTE_FORME} : « {valeur} » ne nomme pas de valeur.")
        parent, valeurs = valeurs[0], valeurs[1:]
    if len(valeurs) > PORTE_VALEURS_MAX:
        raise HTTPException(422, f"Un filtre « porte » tient {PORTE_VALEURS_MAX} valeurs au "
                                 "plus.")
    return {"grille_id": int(parts[0]), "sorte": sorte, "parent": parent,
            "valeurs": list(dict.fromkeys(valeurs))}


def _entrees_sous_les_rubriques(conn, grille_id: int, rubriques) -> list:
    """`(version, entrée)` de chaque entrée rangée, dans sa version, sous l'une de ces
    rubriques ou l'une de leurs descendantes — version par version : une rubrique se lit
    dans la version de chaque relevé."""
    paires = []
    for (vid,) in conn.execute("SELECT id FROM grille_version WHERE grille_id = ?",
                               (grille_id,)).fetchall():
        parents = {r[0]: r[1] for r in conn.execute(
            "SELECT cle, parent_cle FROM grille_rubrique WHERE version_id = ?", (vid,))}
        dedans = set()
        for cle in parents:
            vus, x = set(), cle
            while x is not None and x not in vus:
                if x in rubriques:
                    dedans.add(cle)
                    break
                vus.add(x)
                x = parents.get(x)
        if dedans:
            paires += [(vid, e[0]) for e in conn.execute(
                f"SELECT cle FROM grille_entree WHERE version_id = ? AND rubrique_cle IN "
                f"({', '.join('?' * len(dedans))})", (vid, *sorted(dedans)))]
    return paires


def _clause_porte(conn, portee, filtres) -> tuple[list, list]:
    """Les clauses `EXISTS` des filtres « porte » sur la région `r`, et leurs paramètres.
    Chaque grille nommée doit être LISIBLE (`clause_grille`) : 404 sinon, le même qu'une
    grille qui n'existe pas."""
    if len(filtres) > PORTE_FILTRES_MAX:
        raise HTTPException(422, f"La Recherche tient {PORTE_FILTRES_MAX} filtres « porte » au "
                                 "plus.")
    lus = [_lire_porte(f) for f in filtres]
    ou, p_ou = portee.clause_grille("g.id")
    for gid in sorted({f["grille_id"] for f in lus}):
        if conn.execute(f"SELECT 1 FROM grille g WHERE g.id = ? AND {ou}",
                        (gid, *p_ou)).fetchone() is None:
            raise HTTPException(404, f"Grille {gid} introuvable")
    clauses, params = [], []
    for f in lus:
        v = f["valeurs"]
        marques = ", ".join("?" * len(v))
        base = "SELECT 1 FROM releve _pr WHERE _pr.region_id = r.id AND _pr.grille_id = ?"
        if f["sorte"] == "entree":
            clauses.append(f"EXISTS ({base} AND _pr.entree_cle IN ({marques}))")
            params += [f["grille_id"], *v]
        elif f["sorte"] == "variante":
            clauses.append(f"EXISTS ({base} AND _pr.entree_cle = ? "
                           f"AND _pr.variante_cle IN ({marques}))")
            params += [f["grille_id"], f["parent"], *v]
        elif f["sorte"] == "rubrique":
            paires = _entrees_sous_les_rubriques(conn, f["grille_id"], set(v))
            if not paires:
                clauses.append("0")
                continue
            valeurs = ", ".join("(?, ?)" for _ in paires)
            clauses.append(f"EXISTS ({base} AND (_pr.version_id, _pr.entree_cle) IN "
                           f"(VALUES {valeurs}))")
            params += [f["grille_id"], *[x for p in paires for x in p]]
        else:
            clauses.append(
                "EXISTS (SELECT 1 FROM releve _pr JOIN releve_qualificatif _pq "
                "ON _pq.releve_id = _pr.id JOIN grille_entree _pe "
                "ON _pe.version_id = _pr.version_id AND _pe.cle = _pr.entree_cle "
                "WHERE _pr.region_id = r.id AND _pr.grille_id = ? AND _pe.liste_cle = ? "
                f"AND _pq.qualificatif_cle IN ({marques}))")
            params += [f["grille_id"], f["parent"], *v]
    return clauses, params


def _releves_des_resultats(conn, region_ids) -> dict:
    """{région → ses relevés}, de TOUTES les grilles, ouvertes ou fermées, pour qu'un résultat
    les lise en ligne (« Grille : entrée · variante ») et en isole un d'un clic (`porte`, la
    valeur du filtre qui le désigne ; une case cochée a la sienne). Les libellés se lisent
    dans la version de chaque relevé. Bornés comme l'album : ce sont les régions que la
    Recherche rend déjà, sous `clause_album` — et qui lit une région lit le plan des grilles
    de ses relevés (`clause_grille`, moitié (c)). Rien de qui les a posés. La grille de
    travail d'abord, puis les autres par leur nom."""
    sortie = {rid: [] for rid in region_ids}
    if not region_ids:
        return sortie
    ids = sorted(sortie)
    lignes, qualifs = [], {}
    for debut in range(0, len(ids), 500):
        paquet = ids[debut:debut + 500]
        marques = ", ".join("?" * len(paquet))
        lignes += conn.execute(
            "SELECT rl.id, rl.region_id, rl.grille_id, g.nom AS grille, g.ouverte, g.travail, "
            "rl.entree_cle, e.libelle AS entree, e.liste_cle, rl.variante_cle, "
            "v.libelle AS variante "
            "FROM releve rl JOIN grille g ON g.id = rl.grille_id "
            "LEFT JOIN grille_entree e ON e.version_id = rl.version_id AND e.cle = rl.entree_cle "
            "LEFT JOIN grille_variante v ON v.version_id = rl.version_id "
            "AND v.entree_cle = rl.entree_cle AND v.cle = rl.variante_cle "
            f"WHERE rl.region_id IN ({marques})", paquet).fetchall()
        for q in conn.execute(
                "SELECT rq.releve_id, rq.qualificatif_cle, q.libelle FROM releve_qualificatif rq "
                "JOIN releve rl ON rl.id = rq.releve_id "
                "LEFT JOIN grille_entree e ON e.version_id = rl.version_id "
                "AND e.cle = rl.entree_cle "
                "LEFT JOIN grille_qualificatif q ON q.version_id = rl.version_id "
                "AND q.liste_cle = e.liste_cle AND q.cle = rq.qualificatif_cle "
                f"WHERE rl.region_id IN ({marques}) ORDER BY rq.qualificatif_cle", paquet):
            qualifs.setdefault(q[0], []).append((q[1], q[2]))
    lignes.sort(key=lambda r: (not r["travail"], r["grille"], r["grille_id"], r["id"]))
    for r in lignes:
        g = r["grille_id"]
        porte = (f"{g}/variante/{r['entree_cle']}/{r['variante_cle']}" if r["variante_cle"]
                 else f"{g}/entree/{r['entree_cle']}")
        sortie[r["region_id"]].append({
            "id": r["id"], "grille_id": g, "grille": r["grille"],
            "ouverte": bool(r["ouverte"]), "travail": bool(r["travail"]),
            "entree_cle": r["entree_cle"], "entree": r["entree"] or r["entree_cle"],
            "variante_cle": r["variante_cle"],
            "variante": (r["variante"] or r["variante_cle"]) if r["variante_cle"] else None,
            "qualificatifs": [
                {"cle": qc, "libelle": lib or qc,
                 **({"porte": f"{g}/qualificatif/{r['liste_cle']}/{qc}"}
                    if r["liste_cle"] else {})}
                for qc, lib in qualifs.get(r["id"], [])],
            "porte": porte})
    return sortie


def _recherche_rows(conn, portee, q, album, type, pos, lemme, morph, provenance, limit,
                    personnage=None, porte=()):
    """Construit et exécute la requête de recherche (régions + contexte).
    Partagé par /api/recherche (JSON) et l'export CSV — une seule logique de requête.

    AUTH-2 — la portée est un paramètre OBLIGATOIRE, et c'est ici que se referme le piège
    le plus vicieux du dépôt : la table FTS `recherche` est DÉNORMALISÉE et globale (elle
    agrège OCR + note + lemmes) et ne porte aucune trace d'album ni de collection.
    Une requête plein texte non filtrée renverrait donc le contenu de tout le corpus,
    quelle que soit la rigueur des routes de lecture par identifiant. Le filtre passe par
    la jointure `albums a` déjà présente, pas par la table FTS.

    COL-4 (S8) — ni bac à sable ni jeu, pour personne (`Portee.pour_le_corpus`).

    ANN-7 — `porte` : les filtres « porte… » (`_clause_porte`) ; chaque résultat rend les
    relevés de sa zone (`releves`, `_releves_des_resultats`).
    """
    clauses_porte, params_porte = (_clause_porte(conn, portee, porte) if porte else ([], []))
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
        # ANN-7 — le préfixe cherche dans les dialogues, les notes, les étiquettes des grilles
        # ouvertes (J6) et les lemmes : les colonnes que nomme `COLONNES_CHERCHEES`. Une
        # colonne de l'index qu'elle ne nomme pas n'est pas cherchée.
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

    # ANN-7 — « porte… » : un `EXISTS` par filtre (« et » entre eux), sous la clause d'album.
    where.extend(clauses_porte)
    params.extend(params_porte)

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
    releves = _releves_des_resultats(conn, [row["region_id"] for row in results])
    for row in results:
        row["citation"] = cits.get(row["region_id"])
        row["releves"] = releves[row["region_id"]]
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
              personnage: Optional[int] = None, porte: list[str] = Query([]),
              limit: int = 100, conn: sqlite3.Connection = Depends(db),
              portee: autorisation.Portee = Depends(portee_courante)):
    """La Recherche : le champ (`q`), les filtres d'album, de type, de grammaire, de locuteur,
    et « porte… » (`porte`, répétable : cf. `_lire_porte`). Chaque résultat rend ses relevés
    (`releves`), de toutes les grilles."""
    limit = max(1, min(limit, 500))   # borne : évite LIMIT -1 (= tout le corpus) / DoS
    results = _recherche_rows(conn, portee, q, album, type, pos, lemme, morph,
                              provenance, limit, personnage, porte)
    return {"q": q, "count": len(results), "results": results,
            "sans_terme": _sans_terme_cherchable(q)}


@router.get("/api/recherche/export.csv", dependencies=[Depends(refuser_le_vocabulaire)])
def recherche_export(q: str = "", album: Optional[int] = None,
                     type: Optional[str] = None,
                     pos: Optional[str] = None, lemme: Optional[str] = None,
                     morph: Optional[str] = None, provenance: Optional[str] = None,
                     personnage: Optional[int] = None, porte: list[str] = Query([]),
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Export CSV du jeu de résultats courant (mêmes critères que /api/recherche).
    Borne haute relevée (5000) : on exporte le jeu trouvé, pas seulement l'aperçu.

    DROIT-2 — le fichier n'emporte que ce qu'on a le droit de SORTIR : la portée
    d'export, pas celle de lecture. L'écran peut donc montrer plus de résultats que le
    fichier n'en porte, et c'est exactement la décision : voir n'est pas emporter.

    ANN-7 — le filtre « porte… » s'y applique (le même cœur) : le fichier porte les zones qui
    portent ces relevés. Il ne porte PAS les relevés eux-mêmes — ni colonne, ni libellé :
    ce qui sort des grilles est la tranche 4."""
    results = _recherche_rows(conn, _portee_d_export(portee), q, album, type, pos,
                              lemme, morph, provenance, 5000, personnage, porte)
    buf = io.StringIO()
    # `planche` = numéro ÉDITORIAL (cité), `citation` = repère complet « pl·c(·b) » ;
    # le CSV est l'artefact que le chercheur emporte pour citer. Cf.
    # docs/numerotation-et-citation.md.
    # ANN-7 — la colonne `tags` est RETIRÉE, et non laissée vide (cadrage, « se tranchent
    # en route ») : une colonne toujours vide se lirait « aucun tag », pas « plus de tags ».
    cols = ["album", "planche", "citation", "region_id", "type",
            "ocr_texte", "note"]
    w = ecrivain_csv_dict(buf, cols, extrasaction="ignore")
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
