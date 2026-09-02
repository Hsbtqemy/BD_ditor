"""Analyse grammaticale (Palier B) — fréquences, concordance, croisement, comparaison.

Bloc sorti de `main.py` (ARCH-1). Chemins et contrat d'API inchangés : un routeur
inclus apparaît dans `app.routes` comme une route déclarée sur `app`, ce dont
dépendent les trois cliquets du dépôt. Les imports ci-dessous sont CALCULÉS depuis
les noms libres du bloc, jamais recopiés à l'œil — c'est cette erreur-là qui a
produit 49 tests rouges au premier bloc extrait.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

import accord
import accord_inter
import autorisation
import journal
from config import UPOS_TAGS
from database import citations_regions, reindex_region
from pipeline import nlp

from socle import (
    TokenCorrectionIn, _auteur, _get_region, _norm_tag, _rows, db, portee_courante,
)

router = APIRouter()

def _analyse_filtres(portee, album, type, pos, lemme, morph, provenance, tags=None,
                     tag_scope="herite", personnage=None, attributs=None, auteur=None):
    """Clauses WHERE communes aux requêtes par token (sur la vue `tokens_effectifs` te,
    jointe à regions r / planches p). Valeurs EFFECTIVES (correction humaine ⊕ auto).

    AUTH-2 — la portée est le PREMIER paramètre, et obligatoire : c'est ici que passent
    les quatre surfaces d'analyse (distribution, concordance, croisement, comparaison).
    Les filtrer une par une aurait été quatre occasions d'oublier ; la jointure
    `planches p` est déjà là, le cloisonnement se pose donc au seul endroit qu'elles
    partagent toutes.
    """
    # La clause de PORTÉE est posée d'office et à part : `n_criteres` (3e valeur de
    # retour) compte les clauses qui viennent réellement de l'utilisateur, pour que
    # « aucun critère effectif » reste distinguable de « la portée a filtré ».
    ou, pp = portee.clause_album("p.album_id")
    where, params = [ou], list(pp)
    if album is not None:
        where.append("p.album_id = ?"); params.append(album)
    if type:
        where.append("r.type = ?"); params.append(type)
    if pos:
        where.append("te.pos = ?"); params.append(pos.upper())          # UPOS
    if lemme:
        where.append("te.lemme = ?"); params.append(lemme.lower())       # lemmes minusculés
    if morph:
        where.append("te.morph LIKE ?"); params.append(f"%{morph}%")     # trait UD (sous-chaîne)
    if provenance:
        where.append("te.provenance = ?"); params.append(provenance)     # auto|corrige|valide
    if auteur:
        # INFRA-2 : tokens portant une correction de cet auteur (qui a corrigé/validé là).
        where.append("te.corr_auteur = ?"); params.append(auteur)
    # Filtre par TAGS (annotation humaine) — un EXISTS par tag ⇒ ET (toutes présentes),
    # comme /api/recherche. `tag_scope` : 'propre' = la région porte le tag ;
    # 'herite' (défaut) = la région OU sa case parente (profondeur ≤ 2 ; une émotion /
    # situation est souvent taguée sur la case). Cf. docs/personnages-et-attribution.md.
    if tags:
        cible = ("a2.region_id = r.id" if tag_scope == "propre"
                 else "a2.region_id IN (r.id, r.parent_id)")
        for label in (_norm_tag(t) for t in tags):
            if not label:
                continue
            where.append(
                "EXISTS (SELECT 1 FROM annotation_tags at2 "
                "        JOIN tags tg ON tg.id = at2.tag_id "
                "        JOIN annotations a2 ON a2.id = at2.annotation_id "
                f"       WHERE {cible} AND tg.label = ?)")
            params.append(label)
    # Filtre par LOCUTEUR (ANN-2) : la bulle est attribuée à ce personnage.
    if personnage is not None:
        where.append("EXISTS (SELECT 1 FROM bulle_locuteur bl "
                     "WHERE bl.region_id = r.id AND bl.personnage_id = ?)")
        params.append(personnage)
    # Filtre par ATTRIBUT (valeur_id) : profil du LOCUTEUR (dimension 'personnage') OU
    # situation de la CASE (dimension 'case' ; région ou case parente). Un (EXISTS OR
    # EXISTS) par valeur ⇒ ET entre attributs. Une valeur n'existe que dans UNE des deux
    # tables (garde de cohérence à l'affectation), donc tester les deux est neutre.
    for vid in (attributs or []):
        where.append(
            "(EXISTS (SELECT 1 FROM bulle_locuteur bl JOIN personnage_attribut pa "
            "         ON pa.personnage_id = bl.personnage_id "
            "         WHERE bl.region_id = r.id AND pa.valeur_id = ?) "
            " OR EXISTS (SELECT 1 FROM region_attribut ra "
            "            WHERE ra.region_id IN (r.id, r.parent_id) AND ra.valeur_id = ?))")
        params.extend([vid, vid])
    return where, params, len(where) - 1


def _valider_facette(conn, personnage=None, attributs=None):
    """404 si un id de facette (personnage / valeur d'attribut) n'existe pas — évite
    un résultat vide silencieux sur un id erroné (revue ANN-2 #6)."""
    if personnage is not None and conn.execute(
            "SELECT 1 FROM personnages WHERE id = ?", (personnage,)).fetchone() is None:
        raise HTTPException(404, f"Personnage {personnage} introuvable")
    for vid in (attributs or []):
        if conn.execute("SELECT 1 FROM attribut_valeur WHERE id = ?", (vid,)).fetchone() is None:
            raise HTTPException(404, f"Valeur d'attribut {vid} introuvable")


@router.get("/api/analyse/frequences")
@router.get("/api/analyse/lemmes")          # alias rétro-compat (champ=lemme)
def analyse_frequences(champ: str = "lemme", album: Optional[int] = None,
                       type: Optional[str] = None, pos: Optional[str] = None,
                       lemme: Optional[str] = None, morph: Optional[str] = None,
                       provenance: Optional[str] = None, auteur: Optional[str] = None,
                       tags: Optional[list[str]] = Query(None), tag_scope: str = "herite",
                       personnage: Optional[int] = None, attributs: Optional[list[int]] = Query(None),
                       limit: int = 100,
                       conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """Distributions de fréquence sur les valeurs EFFECTIVES. `champ` : `lemme`
    (défaut, groupé avec son POS) | `pos` | `morph`. Filtres : album, type de région,
    pos, lemme, morph (sous-chaîne UD), provenance, auteur (de la correction). Base
    des champs lexicaux et distributions (Exploration)."""
    if champ not in ("lemme", "pos", "morph"):
        raise HTTPException(422, "champ invalide (lemme | pos | morph).")
    limit = max(1, min(limit, 1000))
    _valider_facette(conn, personnage, attributs)
    where, params, _n = _analyse_filtres(portee, album, type, pos, lemme, morph, provenance, tags, tag_scope,
                                     personnage, attributs, auteur)
    cols = "te.lemme, te.pos" if champ == "lemme" else f"te.{champ}"
    sql = (f"SELECT {cols}, COUNT(*) AS freq "
           "FROM tokens_effectifs te JOIN regions r ON r.id = te.region_id "
           "JOIN planches p ON p.id = r.planche_id ")
    if where:
        sql += "WHERE " + " AND ".join(where) + " "
    sql += f"GROUP BY {cols} ORDER BY freq DESC, {champ if champ != 'lemme' else 'te.lemme'} LIMIT ?"
    params.append(limit)
    return {"champ": champ, "results": _rows(conn.execute(sql, params))}


@router.get("/api/analyse/concordance")
def analyse_concordance(lemme: Optional[str] = None, pos: Optional[str] = None,
                        morph: Optional[str] = None, provenance: Optional[str] = None,
                        auteur: Optional[str] = None,
                        album: Optional[int] = None, type: Optional[str] = None,
                        tags: Optional[list[str]] = Query(None), tag_scope: str = "herite",
                        personnage: Optional[int] = None, attributs: Optional[list[int]] = Query(None),
                        limit: int = 200, conn: sqlite3.Connection = Depends(db),
                        portee: autorisation.Portee = Depends(portee_courante)):
    """Concordance grammaticale : occurrences de tokens (valeurs EFFECTIVES) répondant
    aux critères, AVEC leur contexte (région, planche, album, texte OCR) — pour montrer
    chaque emploi en contexte multimodal (socle de Recherche+++). Au moins un critère
    grammatical (lemme / pos / morph) est requis."""
    if not (lemme or pos or morph or tags or personnage or attributs or auteur):
        raise HTTPException(422, "Préciser au moins un critère (grammatical, tag, personnage, attribut ou auteur).")
    limit = max(1, min(limit, 500))
    _valider_facette(conn, personnage, attributs)
    where, params, _n = _analyse_filtres(portee, album, type, pos, lemme, morph, provenance, tags, tag_scope,
                                     personnage, attributs, auteur)
    if not _n:      # critères fournis mais aucun effectif (p.ex. tag vide) → évite un
        # sous-corpus « tout ce qui est visible », qui n'est pas ce qu'on a demandé
        raise HTTPException(422, "Aucun critère de recherche effectif.")
    sql = ("SELECT te.region_id, te.ordre, te.texte, te.lemme, te.pos, te.morph, "
           "       te.provenance, r.type, p.id AS planche_id, p.numero AS planche_numero, "
           "       a.id AS album_id, a.titre AS album_titre, r.ocr_texte, "
           "       loc.nom AS locuteur "
           "FROM tokens_effectifs te "
           "JOIN regions r ON r.id = te.region_id "
           "JOIN planches p ON p.id = r.planche_id "
           "JOIN albums a ON a.id = p.album_id "
           "LEFT JOIN bulle_locuteur blc ON blc.region_id = r.id "
           "LEFT JOIN personnages loc ON loc.id = blc.personnage_id "
           "WHERE " + " AND ".join(where) + " "
           "ORDER BY a.id, p.numero, r.ordre, te.ordre LIMIT ?")
    params.append(limit)
    results = _rows(conn.execute(sql, params))
    cits = citations_regions(conn, [r["region_id"] for r in results])
    for r in results:
        r["citation"] = cits.get(r["region_id"])   # chaque ligne KWIC se cite
    return {"count": len(results), "results": results}


def _distribution(conn, portee, champ, album, type, pos, morph, provenance, tags=None,
                  tag_scope="herite", personnage=None, attributs=None, auteur=None):
    """Compte {valeur: fréquence} d'un champ (lemme|pos|morph) sur un sous-corpus, et
    le total. Sur les valeurs EFFECTIVES. `champ` doit être validé par l'appelant."""
    where, params, _n = _analyse_filtres(portee, album, type, pos, None, morph, provenance, tags, tag_scope,
                                     personnage, attributs, auteur)
    sql = (f"SELECT te.{champ} AS v, COUNT(*) AS f "
           "FROM tokens_effectifs te JOIN regions r ON r.id = te.region_id "
           "JOIN planches p ON p.id = r.planche_id ")
    if where:
        sql += "WHERE " + " AND ".join(where) + " "
    sql += f"GROUP BY te.{champ}"
    d = {row["v"]: row["f"] for row in conn.execute(sql, params)}
    return d, sum(d.values())


@router.get("/api/analyse/comparaison")
def analyse_comparaison(champ: str = "lemme",
                        a_album: Optional[int] = None, a_type: Optional[str] = None,
                        a_pos: Optional[str] = None, a_morph: Optional[str] = None,
                        a_provenance: Optional[str] = None, a_auteur: Optional[str] = None,
                        a_tags: Optional[list[str]] = Query(None),
                        b_album: Optional[int] = None, b_type: Optional[str] = None,
                        b_pos: Optional[str] = None, b_morph: Optional[str] = None,
                        a_personnage: Optional[int] = None, a_attributs: Optional[list[int]] = Query(None),
                        b_provenance: Optional[str] = None, b_auteur: Optional[str] = None,
                        b_tags: Optional[list[str]] = Query(None),
                        b_personnage: Optional[int] = None, b_attributs: Optional[list[int]] = Query(None),
                        tag_scope: str = "herite",
                        limit: int = 50, conn: sqlite3.Connection = Depends(db),
                        portee: autorisation.Portee = Depends(portee_courante)):
    """Compare deux sous-corpus A et B : valeurs (lemme|pos|morph) les plus
    SUR-représentées dans chacun, par différence de fréquence RELATIVE (rel = freq /
    total du sous-corpus → comparable malgré des tailles différentes)."""
    if champ not in ("lemme", "pos", "morph"):
        raise HTTPException(422, "champ invalide (lemme | pos | morph).")
    limit = max(1, min(limit, 200))
    _valider_facette(conn, a_personnage, a_attributs)
    _valider_facette(conn, b_personnage, b_attributs)
    da, ta = _distribution(conn, portee, champ, a_album, a_type, a_pos, a_morph, a_provenance, a_tags, tag_scope,
                           a_personnage, a_attributs, a_auteur)
    db_, tb = _distribution(conn, portee, champ, b_album, b_type, b_pos, b_morph, b_provenance, b_tags, tag_scope,
                            b_personnage, b_attributs, b_auteur)
    out = []
    for v in set(da) | set(db_):
        fa, fb = da.get(v, 0), db_.get(v, 0)
        ra = fa / ta if ta else 0.0
        rb = fb / tb if tb else 0.0
        out.append({"valeur": v, "freq_a": fa, "freq_b": fb,
                    "rel_a": round(ra, 6), "rel_b": round(rb, 6),
                    "diff": round(ra - rb, 6)})
    out.sort(key=lambda x: x["diff"], reverse=True)
    return {"champ": champ, "total_a": ta, "total_b": tb,
            "sur_a": [x for x in out[:limit] if x["diff"] > 0],
            "sur_b": [x for x in reversed(out[-limit:]) if x["diff"] < 0]}


# --- Tableaux croisés 2D (ANA-2) : contingence TOKEN × TOKEN sur deux facettes. Réutilise
#     `_analyse_filtres` pour le sous-corpus ; chaque axe est une colonne du token/région
#     (POS, type, provenance, auteur) ou une facette « fan-out » (locuteur, tag, dimension
#     d'attribut) jointe en LEFT JOIN (NULL = absence). Grain TOKEN : les cases sans texte ne
#     sont pas comptées (limite assumée). Cf. docs/domaines.md / backlog ANA-2.
_AXES_SIMPLES = {
    "pos":        ("te.pos",         "pos",        "catégorie (POS)"),
    "morph":      ("te.morph",       "morph",      "morphologie"),
    "type":       ("r.type",         "type",       "type de région"),
    "provenance": ("te.provenance",  "provenance", "provenance"),
    "auteur":     ("te.corr_auteur", "auteur",     "auteur (correction)"),
}


def _axe_croisement(kind, sfx, tag_scope, conn):
    """Un axe → (joins, expr_valeur, expr_cle, params, filtre_concordance, libellé). `sfx`
    (x|y) désambiguïse les alias entre les deux axes. `expr_cle` = clé de drill (id pour
    locuteur/dimension, sinon = la valeur)."""
    if kind in _AXES_SIMPLES:
        expr, filtre, lib = _AXES_SIMPLES[kind]
        return "", expr, expr, [], filtre, lib
    if kind == "locuteur":
        bl, lo = f"blx_{sfx}", f"lox_{sfx}"
        joins = (f"LEFT JOIN bulle_locuteur {bl} ON {bl}.region_id = r.id "
                 f"LEFT JOIN personnages {lo} ON {lo}.id = {bl}.personnage_id")
        return joins, f"{lo}.nom", f"{lo}.id", [], "personnage", "locuteur"
    if kind == "tag":
        an, at, tg = f"anx_{sfx}", f"atx_{sfx}", f"tgx_{sfx}"
        cible = (f"{an}.region_id = r.id" if tag_scope == "propre"
                 else f"{an}.region_id IN (r.id, r.parent_id)")
        joins = (f"LEFT JOIN annotations {an} ON {cible} "
                 f"LEFT JOIN annotation_tags {at} ON {at}.annotation_id = {an}.id "
                 f"LEFT JOIN tags {tg} ON {tg}.id = {at}.tag_id")
        return joins, f"{tg}.label", f"{tg}.label", [], "tags", "tag"
    if kind.startswith("dim:"):
        try:
            dim_id = int(kind[4:])
        except ValueError:
            raise HTTPException(422, f"Axe dimension invalide : {kind}")
        d = conn.execute("SELECT nom, cible FROM attribut_dimension WHERE id = ?",
                         (dim_id,)).fetchone()
        if d is None:
            raise HTTPException(404, f"Dimension {dim_id} introuvable")
        # Le filtre de dimension porte sur l'AFFECTATION (valeur_id d'un attribut de cette
        # dimension), pas sur la valeur jointe : sinon un locuteur/case portant AUSSI d'autres
        # dimensions produirait une fausse ligne « (vide) » (fan-out sur toutes les dimensions).
        av = f"avx_{sfx}"
        sous = f"{{}}.valeur_id IN (SELECT id FROM attribut_valeur WHERE dimension_id = ?)"
        if d["cible"] == "personnage":                       # valeur via le LOCUTEUR
            bl, pa = f"bld_{sfx}", f"pax_{sfx}"
            joins = (f"LEFT JOIN bulle_locuteur {bl} ON {bl}.region_id = r.id "
                     f"LEFT JOIN personnage_attribut {pa} ON {pa}.personnage_id = {bl}.personnage_id "
                     f"  AND {sous.format(pa)} "
                     f"LEFT JOIN attribut_valeur {av} ON {av}.id = {pa}.valeur_id")
        else:                                                # valeur via la CASE (région/parent)
            ra = f"rax_{sfx}"
            joins = (f"LEFT JOIN region_attribut {ra} ON {ra}.region_id IN (r.id, r.parent_id) "
                     f"  AND {sous.format(ra)} "
                     f"LEFT JOIN attribut_valeur {av} ON {av}.id = {ra}.valeur_id")
        return joins, f"{av}.valeur", f"{av}.id", [dim_id], "attributs", d["nom"]
    raise HTTPException(422, f"Axe inconnu : {kind} (pos|morph|type|provenance|auteur|"
                             "locuteur|tag|dim:<id>)")


@router.get("/api/analyse/croisement")
def analyse_croisement(axe_x: str, axe_y: str,
                       album: Optional[int] = None, type: Optional[str] = None,
                       pos: Optional[str] = None, lemme: Optional[str] = None,
                       morph: Optional[str] = None, provenance: Optional[str] = None,
                       auteur: Optional[str] = None,
                       tags: Optional[list[str]] = Query(None), tag_scope: str = "herite",
                       personnage: Optional[int] = None, attributs: Optional[list[int]] = Query(None),
                       limit: int = 20, conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """Tableau croisé 2D (contingence) : compte les TOKENS effectifs par (axe_x × axe_y) sur
    un sous-corpus filtré. Axes : pos|morph|type|provenance|auteur|locuteur|tag|dim:<id>. Un
    axe « fan-out » (tag/dimension) fait compter le token dans CHAQUE valeur présente (NULL =
    absence → ligne « (vide) »). Marges = fréquences réelles (les cellules visibles peuvent
    moins sommer à cause du top-N). Cellule → preuves (concordance)."""
    limit = max(1, min(limit, 50))
    _valider_facette(conn, personnage, attributs)
    jx, ex, cx, px, fx, lx = _axe_croisement(axe_x, "x", tag_scope, conn)
    jy, ey, cy, py, fy, ly = _axe_croisement(axe_y, "y", tag_scope, conn)
    where, wparams, _n = _analyse_filtres(portee, album, type, pos, lemme, morph, provenance, tags, tag_scope,
                                      personnage, attributs, auteur)
    sql = (f"SELECT {ex} AS vx, {cx} AS cx, {ey} AS vy, {cy} AS cy, COUNT(*) AS n "
           "FROM tokens_effectifs te JOIN regions r ON r.id = te.region_id "
           "JOIN planches p ON p.id = r.planche_id "
           f"{jx} {jy} ")
    params = px + py
    if where:
        sql += "WHERE " + " AND ".join(where) + " "
        params += wparams
    sql += "GROUP BY cx, cy, vx, vy"
    rows = conn.execute(sql, params).fetchall()

    xt, yt, cells = {}, {}, {}
    for row in rows:
        cx_, vx_, cy_, vy_, n = row["cx"], row["vx"], row["cy"], row["vy"], row["n"]
        xt.setdefault(cx_, {"cle": cx_, "libelle": vx_, "total": 0})["total"] += n
        yt.setdefault(cy_, {"cle": cy_, "libelle": vy_, "total": 0})["total"] += n
        cells[(cx_, cy_)] = cells.get((cx_, cy_), 0) + n
    xs = sorted(xt.values(), key=lambda d: d["total"], reverse=True)
    ys = sorted(yt.values(), key=lambda d: d["total"], reverse=True)
    x_tronque, y_tronque = len(xs) > limit, len(ys) > limit
    xs, ys = xs[:limit], ys[:limit]
    grille = [[cells.get((x["cle"], y["cle"]), 0) for y in ys] for x in xs]
    return {"axe_x": axe_x, "axe_y": axe_y, "filtre_x": fx, "filtre_y": fy,
            "libelle_x": lx, "libelle_y": ly, "x": xs, "y": ys, "grille": grille,
            "total": sum(cells.values()), "x_tronque": x_tronque, "y_tronque": y_tronque}


def _albums_portee(conn, portee: autorisation.Portee, *, ecriture: bool):
    """Ids des albums de la portée, ou None si elle est totale.  AUTH-2.

    `None` n'est pas « aucun » mais « pas de restriction » : les cœurs d'analyse
    (`accord`, `accord_inter`) l'entendent ainsi, et matérialiser la liste complète
    reviendrait à figer un corpus qui bouge."""
    if portee.tout:
        return None
    ou, params = portee.clause_album("a.id", ecriture=ecriture)
    return [r[0] for r in conn.execute(f"SELECT a.id FROM albums a WHERE {ou}", params)]


def _albums_lisibles(conn, portee: autorisation.Portee):
    """Les albums qu'on LIT — la portée ordinaire d'une surface d'analyse."""
    return _albums_portee(conn, portee, ecriture=False)


def _albums_inscriptibles(conn, portee: autorisation.Portee):
    """Les albums où l'on ÉCRIT. Deux fonctions plutôt qu'un drapeau à l'appel : un nom qui
    dit « lisibles » et rend autre chose selon un booléen se relit mal sur la ligne d'appel,
    et c'est précisément là qu'on vérifie une décision d'autorisation."""
    return _albums_portee(conn, portee, ecriture=True)


@router.get("/api/analyse/accord")
def analyse_accord(conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Rapport d'accord modèle↔humain (NLP-1) : part des tokens RELUS où le modèle NLP avait
    déjà la valeur finale (par champ lemme/POS/morpho) + confusion POS + modèle évalué. Étalon
    de qualité de l'index (transition Phase 1→2). Cf. accord.rapport / docs/rapport-accord.md.

    AUTH-2 — le rapport porte sur le sous-corpus lisible. Un taux d'accord global ne
    montrerait aucun contenu, mais dirait combien de tokens ont été relus ailleurs, donc
    l'ampleur du travail des autres."""
    return accord.rapport(conn, album_ids=_albums_lisibles(conn, portee))


@router.get("/api/analyse/accord-inter")
def analyse_accord_inter(conn: sqlite3.Connection = Depends(db),
                         portee: autorisation.Portee = Depends(portee_courante)):
    """Rapport d'accord INTER-ANNOTATEURS (ANN-5) : sur les tokens qu'un annotateur a RE-TOUCHÉS
    après un autre (chaîne de révisions du journal A3), taux d'accord par champ + par paire
    d'auteurs + points de divergence. Cf. accord_inter.rapport / docs/accord-inter.md.

    AUTH-1 — réservée à qui ÉCRIT, et c'est le seul rapport d'analyse à l'être. Les autres
    portent sur le CORPUS ; celui-ci porte sur des PERSONNES. Il nomme (`auteurs`), il
    apparie (`paires` : le taux d'accord de deux gens précis) et il cite à la ligne près
    (`divergences` : « en pl·3·c2·b1, alice avait NOUN, bob a mis VERB »).

    La règle est donc que **ceux qui voient la mesure sont ceux qu'elle mesure** — les
    propriétaires cumulant l'écriture, ils gardent leur rôle d'arbitre. Un lecteur seul (un
    étudiant, un partenaire, un relecteur externe) n'obtient plus le relevé nominatif des
    erreurs de gens qui n'ont pas choisi d'être mesurés par lui. Le voisin `/api/analyse/
    accord` (NLP-1) reste ouvert en lecture : il ne nomme personne — `accord.py` n'a ni
    `agent` ni `auteur`.

    403 et non 404 : la route est publique (elle est dans `/docs`), c'est son CONTENU qui
    ne l'est pas, et refuser sans le dire redonnerait le silence qu'AUTH-2 combat. Rien
    n'est révélé du corpus — la réponse ne parle que du compte de l'appelant.
    """
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(
            403, "L'accord inter-annotateurs nomme les annotateurs et cite leurs "
                 "désaccords : il est réservé à qui écrit sur le corpus, de sorte que "
                 "ceux qui voient la mesure soient ceux qu'elle mesure.")
    return accord_inter.rapport(conn, album_ids=_albums_inscriptibles(conn, portee))


@router.get("/api/regions/{region_id}/tokens")
def region_tokens(region_id: int, conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Analyse grammaticale d'une région : ses mots avec lemme / POS / morphologie."""
    _get_region(conn, portee, region_id)
    return _tokens_effectifs(conn, region_id)


def _tokens_effectifs(conn, region_id: int) -> list:
    """Tokens EFFECTIFS d'une région (correction humaine ⊕ auto) + provenance —
    jamais `tokens` brut (invariant projet)."""
    return _rows(conn.execute(
        "SELECT ordre, texte, lemme, pos, morph, provenance, a_revoir, "
        "       corr_lemme, corr_pos, corr_morph, corr_auteur "
        "FROM tokens_effectifs WHERE region_id = ? ORDER BY ordre", (region_id,)))


def _norm_corr(v: Optional[str]) -> Optional[str]:
    """'' / espaces → None : un champ non corrigé doit être NULL (sinon la vue
    interpréterait '' comme un override « valeur vide »)."""
    v = (v or "").strip()
    return v or None


@router.put("/api/regions/{region_id}/tokens/{ordre}")
def corriger_token(region_id: int, ordre: int, payload: TokenCorrectionIn,
                   request: Request, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Corrige (ou valide) UN token : impose lemme/POS/morph et/ou marque l'état.
    Champ absent/vide = NULL = auto accepté. POS contrôlé (UPOS). La correction est
    ancrée sur la FORME actuelle du token (anti-dérive ; cf. docs/correction-grammaticale.md).
    L'auteur connecté (en-tête Remote-User, INFRA-2) est enregistré sur la correction."""
    # AUTH-2 — corriger la grammaire, c'est écrire sur la région.
    _get_region(conn, portee, region_id, ecriture=True)
    tok = conn.execute("SELECT texte FROM tokens WHERE region_id = ? AND ordre = ?",
                       (region_id, ordre)).fetchone()
    if tok is None:
        raise HTTPException(404, f"Aucun token à la position {ordre} (région {region_id}).")
    if payload.etat not in ("corrige", "valide"):
        raise HTTPException(422, "État invalide (corrige | valide).")
    pos = _norm_corr(payload.pos)
    if pos and pos not in UPOS_TAGS:
        raise HTTPException(422, f"POS invalide : {pos} (jeu UPOS).")
    lemme, morph = _norm_corr(payload.lemme), _norm_corr(payload.morph)
    # Une correction (etat='corrige') doit changer au moins un champ ; sinon c'est un
    # faux signal. Confirmer l'auto sans rien changer se fait avec etat='valide'.
    if payload.etat == "corrige" and not (lemme or pos or morph):
        raise HTTPException(422, "Correction vide : fournir lemme, POS ou morph "
                            "(ou etat='valide' pour confirmer l'auto).")
    nlp.ensure_loaded()   # charge spaCy HORS transaction (sinon le cold-load tiendrait le verrou DB → 409)
    auteur = _auteur(request)
    _corr_cols = ("ordre", "forme", "lemme", "pos", "morph", "etat")
    avant_corr = conn.execute(
        f"SELECT {', '.join(_corr_cols)} FROM token_correction "
        "WHERE region_id = ? AND ordre = ?", (region_id, ordre)).fetchone()
    conn.execute(
        "INSERT INTO token_correction "
        "  (region_id, ordre, forme, lemme, pos, morph, etat, auteur, obsolete, date_modif) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now')) "
        "ON CONFLICT(region_id, ordre) DO UPDATE SET "
        "  forme=excluded.forme, lemme=excluded.lemme, pos=excluded.pos, "
        "  morph=excluded.morph, etat=excluded.etat, auteur=excluded.auteur, "
        "  obsolete=0, date_modif=datetime('now')",
        (region_id, ordre, tok["texte"], lemme, pos, morph, payload.etat, auteur))
    # Correction humaine de l'étiquetage machine (NLP) : événement avant/après + retouche.
    corr = conn.execute(
        f"SELECT id, {', '.join(_corr_cols)} FROM token_correction "
        "WHERE region_id = ? AND ordre = ?", (region_id, ordre)).fetchone()
    journal.journaliser(conn, "modification" if avant_corr else "creation",
                        "token_correction", corr["id"],
                        avant=(dict(avant_corr) if avant_corr else None),
                        apres={k: corr[k] for k in _corr_cols})
    journal.marquer_touche(conn, region_id)
    reindex_region(conn, region_id)      # FTS reflète la correction ; ancrage re-vérifié
    conn.commit()
    return _tokens_effectifs(conn, region_id)


@router.post("/api/regions/{region_id}/grammaire/valider")
def valider_grammaire(region_id: int, request: Request,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Valide tous les tokens de la région (etat='valide') — geste courant des
    linguistes. Garde les corrections existantes (non obsolètes) et accepte l'auto
    ailleurs ; ne touche pas aux corrections « à revérifier ». NON bloquant : c'est
    une assertion de qualité, jamais un prérequis. L'auteur connecté (INFRA-2) est
    posé sur les tokens auto-acceptés, et REMPLIT l'auteur d'une correction qui n'en
    avait pas — sans jamais écraser le correcteur d'origine (COALESCE)."""
    # AUTH-2 — corriger la grammaire, c'est écrire sur la région.
    _get_region(conn, portee, region_id, ecriture=True)
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    nlp.ensure_loaded()          # spaCy hors transaction (cf. corriger_token)
    auteur = _auteur(request)
    reindex_region(conn, region_id)   # ré-ancre (aligne) d'abord → nettoie toute dérive du texte
    # 1) corrections cohérentes existantes → validées (auteur préservé : valider ≠ corriger)
    conn.execute("UPDATE token_correction "
                 "SET etat='valide', auteur=COALESCE(auteur, ?), date_modif=datetime('now') "
                 "WHERE region_id = ? AND obsolete = 0", (auteur, region_id))
    # 2) tokens sans correction → ligne 'valide' (accepte l'auto ; auteur = le validateur)
    conn.execute(
        "INSERT INTO token_correction (region_id, ordre, forme, etat, auteur, obsolete) "
        "SELECT t.region_id, t.ordre, t.texte, 'valide', ?, 0 FROM tokens t "
        "WHERE t.region_id = ? AND NOT EXISTS "
        "  (SELECT 1 FROM token_correction c WHERE c.region_id=t.region_id AND c.ordre=t.ordre)",
        (auteur, region_id))
    journal.journaliser(conn, "validation", "regions", region_id,
                        apres={"grammaire": "validee"})
    conn.commit()
    return _tokens_effectifs(conn, region_id)


@router.delete("/api/regions/{region_id}/tokens/{ordre}")
def annuler_correction(region_id: int, ordre: int,
                       conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """Annule la correction d'un token → retour à l'auto pur (retire aussi le lemme
    corrigé du FTS)."""
    # AUTH-2 — corriger la grammaire, c'est écrire sur la région.
    _get_region(conn, portee, region_id, ecriture=True)
    nlp.ensure_loaded()   # charge spaCy HORS transaction (le reindex qui suit ne tiendra pas le verrou pendant le cold-load)
    _corr_cols = ("ordre", "forme", "lemme", "pos", "morph", "etat")
    avant_corr = conn.execute(
        f"SELECT id, {', '.join(_corr_cols)} FROM token_correction "
        "WHERE region_id = ? AND ordre = ?", (region_id, ordre)).fetchone()
    cur = conn.execute("DELETE FROM token_correction WHERE region_id = ? AND ordre = ?",
                       (region_id, ordre))
    if cur.rowcount:
        journal.journaliser(conn, "suppression", "token_correction", avant_corr["id"],
                            avant={k: avant_corr[k] for k in _corr_cols})
        reindex_region(conn, region_id)
    conn.commit()
    return _tokens_effectifs(conn, region_id)


@router.get("/api/analyse/info")
def analyse_info(conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """État de l'index linguistique : modèle NLP utilisé (reproductibilité),
    date de réindexation, et volumétrie. La réindexation en lot se lance via
    `tools/reindex_nlp.py` (modèle configurable BD_SPACY_MODEL).

    AUTH-2 — `meta` (modèle, date de réindexation) est un fait d'exploitation, pas une
    donnée de corpus : il reste entier. La VOLUMÉTRIE, elle, est filtrée — c'est une
    mesure du corpus, et sa valeur globale dirait la taille de ce qu'on ne voit pas."""
    meta = {r["cle"]: r["valeur"] for r in conn.execute("SELECT cle, valeur FROM meta")}
    ou, params = portee.clause_album("pl.album_id")
    nb_tokens = conn.execute(
        f"SELECT COUNT(*) AS n FROM tokens t "
        f"  JOIN regions r   ON r.id = t.region_id "
        f"  JOIN planches pl ON pl.id = r.planche_id WHERE {ou}", params).fetchone()["n"]
    nb_lemmes = conn.execute(
        f"SELECT COUNT(*) AS n FROM recherche rch "
        f"  JOIN regions r   ON r.id = rch.region_id "
        f"  JOIN planches pl ON pl.id = r.planche_id "
        f" WHERE rch.lemmes <> '' AND {ou}", params).fetchone()["n"]
    return {"moteur_disponible": nlp.nlp_available(),
            "modele_configure": nlp.configured_model(),   # léger : pas de chargement du modèle
            "meta": meta, "tokens": nb_tokens, "regions_lemmatisees": nb_lemmes}
