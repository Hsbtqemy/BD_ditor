"""Analyse grammaticale (Palier B) — fréquences, concordance, croisement, comparaison.

Bloc sorti de `main.py` (ARCH-1). Chemins et contrat d'API inchangés : un routeur
inclus apparaît dans `app.routes` comme une route déclarée sur `app`, ce dont
dépendent les trois cliquets du dépôt. Les imports ci-dessous sont CALCULÉS depuis
les noms libres du bloc, jamais recopiés à l'œil — c'est cette erreur-là qui a
produit 49 tests rouges au premier bloc extrait.
"""
from __future__ import annotations

import csv
import io
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
from vraisemblance import log_vraisemblance

from socle import (
    TokenCorrectionIn, _auteur, _clause_lemme, _csv_response, _csv_safe, _get_dimension,
    _get_personnage, _get_region, _get_valeur, _norm_tag, _portee_d_export, _rows, db,
    portee_courante,
)

router = APIRouter()

# ANA-7 — deux plafonds, et l'écart entre eux EST la décision du chantier.
#
# Les plafonds d'AFFICHAGE bornent un aperçu à l'écran ; celui de l'EXPORT borne un jeu
# qu'on emporte pour le retravailler. `recherche_export` avait déjà tranché dans ce sens
# — « on exporte le jeu trouvé, pas seulement l'aperçu » — avec 5000.
#
# Ce que la mesure dit du risque : le corpus de développement compte 443 tokens pour 235
# lemmes distincts, si bien qu'aucun plafond n'y mord et qu'un export tronqué s'y verrait
# identique à un export complet. Sur un corpus réel de quelques centaines de milliers de
# tokens, l'ordre de grandeur (loi de Heaps) est de 8 000 à 10 000 lemmes distincts : le
# plafond d'affichage n'en montrerait qu'un dixième. Un CSV muet ferait passer ce dixième
# pour un tout — d'où le plafond relevé ET la ligne de troncature écrite dans le fichier.
PLAFOND_FREQ = 1000
PLAFOND_CONCORDANCE = 500
PLAFOND_COMPARAISON = 200
PLAFOND_CROISEMENT = 50
PLAFOND_EXPORT = 5000

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
    if lemme:                                   # exact, ou préfixe `otage*` (ANA-6)
        clause = _clause_lemme("te.lemme", lemme)
        if clause:
            where.append(clause[0]); params.extend(clause[1])
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
        # Un tag qu'on ne lit pas ne filtre rien — la même règle que `_joindre_tags`, qui
        # ne l'affiche pas : sinon son nom resterait un critère opérant sans être visible.
        ou_tag, p_tag = portee.clause_terme("tg.collection_id")
        for label in (_norm_tag(t) for t in tags):
            if not label:
                continue
            where.append(
                "EXISTS (SELECT 1 FROM annotation_tags at2 "
                "        JOIN tags tg ON tg.id = at2.tag_id "
                "        JOIN annotations a2 ON a2.id = at2.annotation_id "
                f"       WHERE {cible} AND tg.label = ? AND {ou_tag})")
            params.append(label)
            params.extend(p_tag)
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


def _valider_facette(conn, portee: autorisation.Portee, personnage=None, attributs=None):
    """404 si un id de facette (personnage / valeur d'attribut) n'existe pas — évite
    un résultat vide silencieux sur un id erroné (revue ANN-2 #6).

    AUTH-11 — et 404 aussi, au mot près, s'il existe mais qu'on ne le VOIT pas : les
    accesseurs gardés tranchent, avec le message qu'on rendait à un identifiant libre. Ne
    vérifier que l'existence faisait de ce contrôle un oracle — 200 pour une valeur d'une
    collection qu'on ne lit pas, ou un locuteur qui n'apparaît que là, 404 pour le reste —
    et énumérer les identifiants disait lesquels existent ailleurs."""
    if personnage is not None:
        _get_personnage(conn, portee, personnage)
    for vid in (attributs or []):
        _get_valeur(conn, portee, vid)


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
    return {"champ": champ,
            "results": _frequences_rows(conn, portee, champ, album, type, pos, lemme,
                                        morph, provenance, auteur, tags, tag_scope,
                                        personnage, attributs, limit, PLAFOND_FREQ)}


def _frequences_rows(conn, portee, champ, album, type, pos, lemme, morph, provenance,
                     auteur, tags, tag_scope, personnage, attributs, limit, plafond):
    """Cœur de la distribution — PARTAGÉ par la route JSON et son export CSV (ANA-7).

    Extrait pour que l'export ne réécrive pas le calcul : deux chemins finiraient par
    diverger sur un filtre, et c'est le genre de divergence qu'on ne voit pas — les deux
    réponses restent plausibles. Même patron que `_recherche_rows`, partagé de la même
    façon par `/api/recherche` et son `export.csv`.

    `plafond` est un PARAMÈTRE et non une constante, parce que les deux appelants n'ont pas
    le même : l'écran affiche un aperçu, l'export rend le jeu trouvé. C'est la seule chose
    qui les distingue, et la rendre explicite évite qu'un troisième appelant hérite d'un
    plafond d'affichage sans le savoir.
    """
    if champ not in ("lemme", "pos", "morph"):
        raise HTTPException(422, "champ invalide (lemme | pos | morph).")
    limit = max(1, min(limit, plafond))
    _valider_facette(conn, portee, personnage, attributs)
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
    return _rows(conn.execute(sql, params))


# DROIT-2 — les six exports CSV de ce module sont des PORTES DE SORTIE. Chacun passe à
# son cœur la portée d'EXPORT (`_portee_d_export`) et non celle de lecture : l'écran
# montre tout ce qu'on lit, le fichier n'emporte que ce qu'on a le droit de sortir, et
# c'est un 403 si l'on n'exporte nulle part. Les cœurs n'ont rien appris : c'est une
# Portee de plus, que `clause_album` et `clause_terme` consomment telle quelle.
@router.get("/api/analyse/frequences.csv")
def analyse_frequences_export(champ: str = "lemme", album: Optional[int] = None,
                              type: Optional[str] = None, pos: Optional[str] = None,
                              lemme: Optional[str] = None, morph: Optional[str] = None,
                              provenance: Optional[str] = None, auteur: Optional[str] = None,
                              tags: Optional[list[str]] = Query(None), tag_scope: str = "herite",
                              personnage: Optional[int] = None,
                              attributs: Optional[list[int]] = Query(None),
                              conn: sqlite3.Connection = Depends(db),
                              portee: autorisation.Portee = Depends(portee_courante)):
    """Export CSV de la distribution — MÊMES critères que `/api/analyse/frequences` (ANA-7).

    Pas de paramètre `limit` : l'écran affiche un aperçu, le fichier rend le jeu trouvé
    jusqu'à `PLAFOND_EXPORT`. C'est la décision du chantier, et elle suit celle que
    `recherche_export` avait déjà prise.
    """
    lignes = _frequences_rows(conn, _portee_d_export(portee), champ, album, type, pos,
                              lemme, morph, provenance, auteur, tags, tag_scope,
                              personnage, attributs, PLAFOND_EXPORT, PLAFOND_EXPORT)
    cols = (["lemme", "pos", "frequence"] if champ == "lemme" else [champ, "frequence"])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in lignes:
        w.writerow([_csv_safe(r["lemme"]), _csv_safe(r["pos"]), r["freq"]]
                   if champ == "lemme" else [_csv_safe(r[champ]), r["freq"]])
    return _csv_response(buf.getvalue(), _nom_export("distribution", champ, lignes))


def _nom_export(vue: str, precision: Optional[str], lignes, tronque=None) -> str:
    """Nom de fichier d'un export d'analyse — et il PORTE la troncature (ANA-7).

    Le fichier doit dire qu'il est tronqué, sans quoi il fait passer un aperçu pour un
    tout. Restait à choisir OÙ le dire, et aucune place n'est neutre : une ligne de
    commentaire en tête décale l'en-tête pour un tableur, une ligne en pied entre dans les
    données pour pandas, un en-tête HTTP ne survit pas au premier déplacement du fichier.

    Le NOM voyage avec le fichier et ne touche pas son contenu — c'est la seule place qui
    ne coûte rien à aucun des deux lecteurs. Un `-tronque-5000` dans le nom se voit dans un
    dossier, dans une pièce jointe et dans un `ls`, six mois après.

    `tronque` se passe explicitement quand la coupe ne se lit pas au nombre de lignes —
    le croisement tronque par AXE, et un fichier de dix lignes peut y être amputé.
    """
    # Un joker de préfixe se LIT dans le nom (ANA-6) : « otage* » → `…-otage-prefixe.csv`.
    # Laissé tel quel, `_disposition` l'aurait remplacé par un `_` muet.
    if precision and precision.endswith("*"):
        precision = precision.rstrip("*") + "-prefixe"
    bout = f"-{precision}" if precision else ""
    if tronque is None:
        tronque = len(lignes) >= PLAFOND_EXPORT
    coupe = f"-tronque-{PLAFOND_EXPORT}" if tronque else ""
    return f"{vue}{bout}{coupe}.csv"


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
    results = _concordance_rows(conn, portee, lemme, pos, morph, provenance, auteur,
                                album, type, tags, tag_scope, personnage, attributs,
                                limit, PLAFOND_CONCORDANCE)
    return {"count": len(results), "results": results}


def _concordance_rows(conn, portee, lemme, pos, morph, provenance, auteur, album, type,
                      tags, tag_scope, personnage, attributs, limit, plafond):
    """Cœur de la concordance KWIC — PARTAGÉ par la route JSON et son export CSV (ANA-7)."""
    if not (lemme or pos or morph or tags or personnage or attributs or auteur):
        raise HTTPException(422, "Préciser au moins un critère (grammatical, tag, personnage, attribut ou auteur).")
    limit = max(1, min(limit, plafond))
    _valider_facette(conn, portee, personnage, attributs)
    where, params, _n = _analyse_filtres(portee, album, type, pos, lemme, morph, provenance, tags, tag_scope,
                                     personnage, attributs, auteur)
    if not _n:      # critères fournis mais aucun effectif (p.ex. tag vide) → évite un
        # sous-corpus « tout ce qui est visible », qui n'est pas ce qu'on a demandé
        raise HTTPException(422, "Aucun critère de recherche effectif.")
    sql = ("SELECT te.region_id, te.ordre, te.texte, te.lemme, te.pos, te.morph, "
           "       te.provenance, r.type, r.parent_id, p.id AS planche_id, "
           "       p.numero AS planche_numero, a.id AS album_id, a.titre AS album_titre, "
           "       r.ocr_texte, loc.nom AS locuteur, an.note AS note "
           "FROM tokens_effectifs te "
           "JOIN regions r ON r.id = te.region_id "
           "JOIN planches p ON p.id = r.planche_id "
           "JOIN albums a ON a.id = p.album_id "
           "LEFT JOIN annotations an ON an.region_id = r.id "       # 1:1 (region_id UNIQUE)
           "LEFT JOIN bulle_locuteur blc ON blc.region_id = r.id "
           "LEFT JOIN personnages loc ON loc.id = blc.personnage_id "
           "WHERE " + " AND ".join(where) + " "
           "ORDER BY a.id, p.numero, r.ordre, te.ordre LIMIT ?")
    params.append(limit)
    results = _rows(conn.execute(sql, params))
    cits = citations_regions(conn, [r["region_id"] for r in results])
    for r in results:
        r["citation"] = cits.get(r["region_id"])   # chaque ligne KWIC se cite
    _joindre_tags(conn, portee, results)
    return results


def _joindre_tags(conn, portee, lignes) -> None:
    """Pose sur chaque ligne ses TAGS — ceux de sa région, puis ceux de sa case (ANA-6).

    Les HÉRITÉS sont là parce que c'est la portée par défaut du filtre
    (`tag_scope=herite`) : sans eux, une ligne trouvée par un tag posé sur la case
    n'afficherait rien qui explique sa présence. Un tag porté par les deux est PROPRE, et
    ne se répète pas en hérité.

    Filtrés par `clause_terme`, et ce n'est pas une précaution : un tag peut devenir LOCAL
    après avoir été posé (lexique situé), et un album vit dans plusieurs collections. Une
    région qu'on lit peut donc porter un tag d'une collection qu'on ne lit pas — son nom
    est alors un morceau de grille d'analyse qui n'est pas à nous.

    Une seule requête pour tout le jeu, jamais une par ligne : la concordance s'exporte
    jusqu'au plafond d'export. `parent_id` sert ici et ne sort pas.
    """
    parents = {r["region_id"]: r.pop("parent_id") for r in lignes}
    cibles = sorted(set(parents) | {p for p in parents.values() if p is not None})
    par_region: dict = {}
    if cibles:
        ou, pp = portee.clause_terme("tg.collection_id")
        marques = ",".join("?" * len(cibles))
        for row in conn.execute(
                "SELECT an.region_id, tg.label FROM annotation_tags at "
                "JOIN tags tg ON tg.id = at.tag_id "
                "JOIN annotations an ON an.id = at.annotation_id "
                f"WHERE an.region_id IN ({marques}) AND {ou} ORDER BY tg.label",
                (*cibles, *pp)):
            par_region.setdefault(row["region_id"], []).append(row["label"])
    for r in lignes:
        propres = par_region.get(r["region_id"], [])
        herites = [t for t in par_region.get(parents[r["region_id"]], []) if t not in propres]
        r["tags"] = ([{"label": t, "herite": False} for t in propres]
                     + [{"label": t, "herite": True} for t in herites])
        r["note"] = r["note"] or ""


@router.get("/api/analyse/concordance.csv")
def analyse_concordance_export(lemme: Optional[str] = None, pos: Optional[str] = None,
                               morph: Optional[str] = None, provenance: Optional[str] = None,
                               auteur: Optional[str] = None, album: Optional[int] = None,
                               type: Optional[str] = None,
                               tags: Optional[list[str]] = Query(None), tag_scope: str = "herite",
                               personnage: Optional[int] = None,
                               attributs: Optional[list[int]] = Query(None),
                               conn: sqlite3.Connection = Depends(db),
                               portee: autorisation.Portee = Depends(portee_courante)):
    """Export CSV de la concordance — MÊMES critères que `/api/analyse/concordance` (ANA-7).

    La CITATION est en tête, avant le texte : c'est ce qu'on emporte une concordance pour
    faire — citer un emploi en contexte. Même choix que `recherche_export`, dont le
    commentaire dit « le CSV est l'artefact que le chercheur emporte pour citer ».
    """
    lignes = _concordance_rows(conn, _portee_d_export(portee), lemme, pos, morph,
                               provenance, auteur, album, type, tags, tag_scope,
                               personnage, attributs, PLAFOND_EXPORT, PLAFOND_EXPORT)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator=chr(10))
    w.writerow(["citation", "album", "planche", "region_id", "type", "locuteur",
                "texte", "lemme", "pos", "morph", "provenance", "ocr_texte",
                "tags", "note"])
    for r in lignes:
        cit = r.get("citation") or {}
        w.writerow([cit.get("texte", ""), _csv_safe(r["album_titre"]),
                    cit.get("planche") if cit.get("planche") is not None else "",
                    r["region_id"], r["type"], _csv_safe(r["locuteur"] or ""),
                    _csv_safe(r["texte"]), _csv_safe(r["lemme"]), _csv_safe(r["pos"]),
                    _csv_safe(r["morph"] or ""), r["provenance"],
                    _csv_safe(r["ocr_texte"] or ""),
                    # Même séparateur que l'export de la Recherche ; l'hérité se DIT.
                    _csv_safe("|".join(("case:" if t["herite"] else "") + t["label"]
                                       for t in r["tags"])),
                    _csv_safe(r["note"])])
    return _csv_response(buf.getvalue(), _nom_export("concordance", lemme or pos or morph, lignes))


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
                        tag_scope: str = "herite", metrique: str = "diff",
                        limit: int = 50, conn: sqlite3.Connection = Depends(db),
                        portee: autorisation.Portee = Depends(portee_courante)):
    """Compare deux sous-corpus A et B : valeurs (lemme|pos|morph) les plus
    SUR-représentées dans chacun, par différence de fréquence RELATIVE (rel = freq /
    total du sous-corpus → comparable malgré des tailles différentes) — ou, avec
    `metrique=ll`, par keyness (log-vraisemblance, ANA-4), qui pèse l'écart par le nombre
    d'occurrences au lieu de favoriser les mots fréquents. Le côté ne dépend pas du
    choix : les deux mesures ont toujours le même signe."""
    out, ta, tb = _comparaison_rows(
        conn, portee, champ, tag_scope,
        (a_album, a_type, a_pos, a_morph, a_provenance, a_tags, a_personnage, a_attributs, a_auteur),
        (b_album, b_type, b_pos, b_morph, b_provenance, b_tags, b_personnage, b_attributs, b_auteur),
        metrique)
    limit = max(1, min(limit, PLAFOND_COMPARAISON))
    return {"champ": champ, "metrique": metrique, "total_a": ta, "total_b": tb,
            "sur_a": [x for x in out[:limit] if x[metrique] > 0],
            "sur_b": [x for x in reversed(out[-limit:]) if x[metrique] < 0]}


def _comparaison_rows(conn, portee, champ, tag_scope, cote_a, cote_b, metrique="diff"):
    """Cœur de la comparaison A/B — PARTAGÉ par la route JSON et son export CSV (ANA-7).

    Rend la liste ENTIÈRE, triée par différence décroissante, et les deux totaux. La
    troncature reste à l'appelant, et ce n'est pas un détail de découpage : la route
    JSON coupe en DEUX listes (`sur_a`, `sur_b`), l'export rend une ligne par valeur —
    deux formes de la même mesure, qui doivent partir du même calcul faute de quoi le
    fichier et l'écran finiraient par se contredire sur les valeurs de bord.

    `metrique` choisit l'ORDRE (ANA-4) : `diff`, l'écart de fréquence relative, ou `ll`, la
    log-vraisemblance (`vraisemblance.py`). Chaque ligne porte les deux, si bien que le
    fichier se retrie sur l'autre sans rien recalculer.
    """
    if champ not in ("lemme", "pos", "morph"):
        raise HTTPException(422, "champ invalide (lemme | pos | morph).")
    if metrique not in ("diff", "ll"):
        raise HTTPException(422, "metrique invalide (diff | ll).")
    (a_album, a_type, a_pos, a_morph, a_provenance, a_tags, a_personnage, a_attributs, a_auteur) = cote_a
    (b_album, b_type, b_pos, b_morph, b_provenance, b_tags, b_personnage, b_attributs, b_auteur) = cote_b
    _valider_facette(conn, portee, a_personnage, a_attributs)
    _valider_facette(conn, portee, b_personnage, b_attributs)
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
                    "diff": round(ra - rb, 6),
                    "ll": round(log_vraisemblance(fa, fb, ta, tb), 4)})
    out.sort(key=lambda x: x[metrique], reverse=True)
    return out, ta, tb


@router.get("/api/analyse/comparaison.csv")
def analyse_comparaison_export(champ: str = "lemme",
                               a_album: Optional[int] = None, a_type: Optional[str] = None,
                               a_pos: Optional[str] = None, a_morph: Optional[str] = None,
                               a_provenance: Optional[str] = None, a_auteur: Optional[str] = None,
                               a_tags: Optional[list[str]] = Query(None),
                               a_personnage: Optional[int] = None,
                               a_attributs: Optional[list[int]] = Query(None),
                               b_album: Optional[int] = None, b_type: Optional[str] = None,
                               b_pos: Optional[str] = None, b_morph: Optional[str] = None,
                               b_provenance: Optional[str] = None, b_auteur: Optional[str] = None,
                               b_tags: Optional[list[str]] = Query(None),
                               b_personnage: Optional[int] = None,
                               b_attributs: Optional[list[int]] = Query(None),
                               tag_scope: str = "herite", metrique: str = "diff",
                               conn: sqlite3.Connection = Depends(db),
                               portee: autorisation.Portee = Depends(portee_courante)):
    """Export CSV de la comparaison A/B — MÊMES critères que `/api/analyse/comparaison`.

    UNE ligne par valeur, et non les deux listes de l'écran. L'écran montre les têtes de
    chaque côté parce qu'un humain lit un classement ; un fichier se trie et se filtre tout
    seul, et couper le milieu lui retirerait justement ce qui distingue une valeur ABSENTE
    d'un sous-corpus d'une valeur également répartie. Les deux totaux sont en tête, sans
    quoi les fréquences relatives ne se recalculent pas — en COLONNES répétées, pas en
    ligne de commentaire, qui décalerait l'en-tête pour un tableur.
    """
    out, ta, tb = _comparaison_rows(
        conn, _portee_d_export(portee), champ, tag_scope,
        (a_album, a_type, a_pos, a_morph, a_provenance, a_tags, a_personnage, a_attributs, a_auteur),
        (b_album, b_type, b_pos, b_morph, b_provenance, b_tags, b_personnage, b_attributs, b_auteur),
        metrique)
    lignes = out[:PLAFOND_EXPORT]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator=chr(10))
    # Les deux TOTAUX sont des colonnes répétées, et non une ligne de commentaire en tête.
    # Une telle ligne décalerait l'en-tête pour un tableur — le défaut que le nom de
    # fichier a justement été choisi pour éviter sur la troncature. La redondance coûte
    # deux colonnes constantes et rend le fichier lisible des deux côtés sans convention.
    # ANA-4 : les DEUX mesures en colonnes, triées selon celle de l'écran — le fichier se
    # retrie sur l'autre sans recalcul.
    w.writerow(["valeur", "freq_a", "rel_a", "freq_b", "rel_b", "diff", "ll",
                "total_a", "total_b"])
    for x in lignes:
        w.writerow([_csv_safe(x["valeur"]), x["freq_a"], x["rel_a"],
                    x["freq_b"], x["rel_b"], x["diff"], x["ll"], ta, tb])
    return _csv_response(buf.getvalue(), _nom_export("comparaison", champ, lignes))


@router.get("/api/analyse/croisement.csv")
def analyse_croisement_export(axe_x: str, axe_y: str, forme: str = "plat",
                              album: Optional[int] = None, type: Optional[str] = None,
                              pos: Optional[str] = None, lemme: Optional[str] = None,
                              morph: Optional[str] = None, provenance: Optional[str] = None,
                              auteur: Optional[str] = None,
                              tags: Optional[list[str]] = Query(None), tag_scope: str = "herite",
                              personnage: Optional[int] = None,
                              attributs: Optional[list[int]] = Query(None),
                              conn: sqlite3.Connection = Depends(db),
                              portee: autorisation.Portee = Depends(portee_courante)):
    """Export CSV du tableau croisé — MÊMES critères que `/api/analyse/croisement` (ANA-7).

    DEUX formes, parce que les deux usages sont réels et qu'aucun ne se déduit de l'autre.
    `forme=plat` (défaut) rend une ligne par cellule non vide, avec les deux marges en
    colonnes : c'est ce qui se retraite dans R ou pandas, et une matrice s'en reconstruit
    par pivot. `forme=matrice` rend le tableau de contingence tel qu'on le cite, avec sa
    ligne et sa colonne de totaux — l'opération inverse, elle, perd de l'information dès
    qu'un axe est coupé.

    LE PIÈGE EST DANS LA MATRICE, et il est écrit plutôt que corrigé : les marges sont les
    fréquences réelles quand les cellules sont coupées au top-N, si bien qu'une matrice
    tronquée montre des totaux qui ne somment pas à ses propres cases. Le plafond d'export
    (`PLAFOND_EXPORT` par axe, contre 50 à l'écran) rend le cas rare ; quand il arrive, le
    NOM du fichier porte `-tronque-`. Corriger en recalculant les marges sur les seules
    cellules retenues serait pire : le fichier deviendrait cohérent et FAUX, en affirmant
    un total que le corpus ne porte pas.
    """
    if forme not in ("plat", "matrice"):
        raise HTTPException(422, "forme invalide (plat | matrice).")
    d = _croisement_data(conn, _portee_d_export(portee), axe_x, axe_y, album, type, pos,
                         lemme, morph, provenance, auteur, tags, tag_scope, personnage,
                         attributs, PLAFOND_EXPORT, PLAFOND_EXPORT)
    tronque = d["x_tronque"] or d["y_tronque"]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator=chr(10))
    if forme == "matrice":
        w.writerow([f"{d['libelle_x']} × {d['libelle_y']}"]
                   + [_csv_safe(y["libelle"]) for y in d["y"]] + ["Total"])
        for i, x in enumerate(d["x"]):
            w.writerow([_csv_safe(x["libelle"])] + list(d["grille"][i]) + [x["total"]])
        w.writerow(["Total"] + [y["total"] for y in d["y"]] + [d["total"]])
    else:
        w.writerow([d["libelle_x"], d["libelle_y"], "n", "marge_x", "marge_y"])
        for i, x in enumerate(d["x"]):
            for j, y in enumerate(d["y"]):
                n = d["grille"][i][j]
                if n:                      # une cellule vide n'est pas une observation
                    w.writerow([_csv_safe(x["libelle"]), _csv_safe(y["libelle"]),
                                n, x["total"], y["total"]])
    return _csv_response(buf.getvalue(),
                         _nom_export("croisement", f"{axe_x}-{axe_y}-{forme}", [],
                                     tronque=tronque))


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


def _axe_croisement(kind, sfx, tag_scope, conn, portee):
    """Un axe → (joins, expr_valeur, expr_cle, params, filtre_concordance, libellé). `sfx`
    (x|y) désambiguïse les alias entre les deux axes. `expr_cle` = clé de drill (id pour
    locuteur/dimension, sinon = la valeur). `portee` sert aux deux axes dont les libellés
    SONT des termes, les tags et les dimensions (AUTH-11) : un terme qu'on ne lit pas n'a
    pas à devenir une ligne."""
    if kind in _AXES_SIMPLES:
        expr, filtre, lib = _AXES_SIMPLES[kind]
        return "", expr, expr, [], filtre, lib
    if kind == "locuteur":
        bl, lo = f"blx_{sfx}", f"lox_{sfx}"
        joins = (f"LEFT JOIN bulle_locuteur {bl} ON {bl}.region_id = r.id "
                 f"LEFT JOIN personnages {lo} ON {lo}.id = {bl}.personnage_id")
        return joins, f"{lo}.nom", f"{lo}.id", [], "personnage", "locuteur"
    if kind == "tag":
        an, at, tg, tz = f"anx_{sfx}", f"atx_{sfx}", f"tgx_{sfx}", f"tzx_{sfx}"
        cible = (f"{an}.region_id = r.id" if tag_scope == "propre"
                 else f"{an}.region_id IN (r.id, r.parent_id)")
        # La portée des termes se pose sur la LIAISON, pas sur le tag joint : posée sur le
        # tag, une région portant un tag lisible ET un illisible produirait une seconde
        # ligne sans libellé, comptée comme une région sans tag.
        ou_tag, p_tag = portee.clause_terme(f"{tz}.collection_id")
        joins = (f"LEFT JOIN annotations {an} ON {cible} "
                 f"LEFT JOIN annotation_tags {at} ON {at}.annotation_id = {an}.id "
                 f"AND {at}.tag_id IN (SELECT {tz}.id FROM tags {tz} WHERE {ou_tag}) "
                 f"LEFT JOIN tags {tg} ON {tg}.id = {at}.tag_id")
        return joins, f"{tg}.label", f"{tg}.label", p_tag, "tags", "tag"
    if kind.startswith("dim:"):
        try:
            dim_id = int(kind[4:])
        except ValueError:
            raise HTTPException(422, f"Axe dimension invalide : {kind}")
        # AUTH-11 — par l'accesseur gardé : une dimension qu'on ne lit pas répond comme une
        # dimension absente. Lue par son seul identifiant, elle rendait son NOM, qui devient
        # le libellé de l'axe — une grille d'analyse, pas un mot.
        d = _get_dimension(conn, portee, dim_id)
        # Le filtre de dimension porte sur l'AFFECTATION (valeur_id d'un attribut de cette
        # dimension), pas sur la valeur jointe : sinon un locuteur/case portant AUSSI d'autres
        # dimensions produirait une fausse ligne « (vide) » (fan-out sur toutes les dimensions).
        # La portée des valeurs s'y pose aussi, sur la LIAISON comme pour l'axe des tags : une
        # valeur qu'on ne lit pas ne fait pas de ligne, et une case qui ne porte qu'elle compte
        # parmi les « (vide) ».
        av, vz = f"avx_{sfx}", f"vzx_{sfx}"
        ou_val, p_val = portee.clause_terme(f"{vz}.collection_id")
        sous = (f"{{}}.valeur_id IN (SELECT {vz}.id FROM attribut_valeur {vz} "
                f"WHERE {vz}.dimension_id = ? AND {ou_val})")
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
        return joins, f"{av}.valeur", f"{av}.id", [dim_id, *p_val], "attributs", d["nom"]
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
    return _croisement_data(conn, portee, axe_x, axe_y, album, type, pos, lemme, morph,
                            provenance, auteur, tags, tag_scope, personnage, attributs,
                            limit, PLAFOND_CROISEMENT)


def _croisement_data(conn, portee, axe_x, axe_y, album, type, pos, lemme, morph,
                     provenance, auteur, tags, tag_scope, personnage, attributs,
                     limit, plafond):
    """Cœur du tableau croisé — PARTAGÉ par la route JSON et son export CSV (ANA-7).

    À retenir en le lisant : les MARGES (`x[].total`, `y[].total`) sont calculées sur
    TOUTES les lignes, puis les axes sont coupés au top-N. Marges réelles, cellules
    tronquées — c'est voulu à l'écran, qui l'annonce, et c'est le piège d'un CSV en
    matrice, dont la colonne « Total » ne sommerait alors pas à ses propres cases.
    """
    limit = max(1, min(limit, plafond))
    _valider_facette(conn, portee, personnage, attributs)
    jx, ex, cx, px, fx, lx = _axe_croisement(axe_x, "x", tag_scope, conn, portee)
    jy, ey, cy, py, fy, ly = _axe_croisement(axe_y, "y", tag_scope, conn, portee)
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
                   portee: autorisation.Portee = Depends(portee_courante),
                   modele: Optional[str] = Query(
                       None, description="NLP-2 : restreindre aux relectures faites sur la "
                                         "sortie de ce modèle, et le mesurer au moment de "
                                         "la relecture (cf. `par_modele`)")):
    """Rapport d'accord modèle↔humain (NLP-1) : part des tokens RELUS où le modèle NLP avait
    déjà la valeur finale (par champ lemme/POS/morpho) + confusion POS + modèle évalué. Étalon
    de qualité de l'index (transition Phase 1→2). Cf. accord.rapport / docs/rapport-accord.md.

    AUTH-2 — le rapport porte sur le sous-corpus lisible. Un taux d'accord global ne
    montrerait aucun contenu, mais dirait combien de tokens ont été relus ailleurs, donc
    l'ampleur du travail des autres."""
    return accord.rapport(conn, album_ids=_albums_lisibles(conn, portee),
                          modele=modele or None)


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


@router.get("/api/analyse/accord.csv")
def analyse_accord_export(conn: sqlite3.Connection = Depends(db),
                          portee: autorisation.Portee = Depends(portee_courante),
                          modele: Optional[str] = Query(
                              None, description="NLP-2 : comme sur `/api/analyse/accord`")):
    """Export CSV de l'accord modèle↔humain — même cœur que `/api/analyse/accord` (ANA-7).

    Une ligne par champ, comme `tools/rapport_accord.py --csv`, PLUS le modèle et la date
    de réindexation en colonnes répétées. Sans eux le fichier ne sert pas à ce pour quoi
    ce rapport existe — comparer `sm` et `lg` sur le même corpus relu : deux fichiers de
    taux sans le nom du modèle ne se distinguent pas. Pour la même raison, `releve_sur`
    nomme le filtre de NLP-2 quand il y en a un : restreint, le fichier ne porte plus sur
    tout le corpus relu. Les taux restent ceux de l'index actuel ; la mesure « au moment de
    la relecture » est dans le JSON.

    La matrice de confusion POS n'y est pas, comme dans le CLI : c'est un second tableau,
    de forme différente, et l'entasser sous le premier ferait un fichier qu'aucun des deux
    lecteurs — tableur ou pandas — ne saurait ouvrir d'une pièce. Elle reste à l'écran.

    Ce rapport NE NOMME PERSONNE : `accord.py` n'a ni `agent` ni `auteur`, c'est ce qui le
    laisse ouvert en lecture là où son voisin `accord-inter` est réservé.
    """
    r = accord.rapport(conn, album_ids=_albums_lisibles(conn, _portee_d_export(portee)),
                       modele=modele or None)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator=chr(10))
    w.writerow(["champ", "revus", "accord", "taux", "modele", "indexe_le", "releve_sur"])
    for ch, c in r["champs"].items():
        w.writerow([ch, c.get("revus"), c.get("accord"), c.get("taux"),
                    _csv_safe(r.get("modele") or ""), r.get("indexe_le") or "",
                    _csv_safe(r.get("filtre_modele") or "")])
    return _csv_response(buf.getvalue(), _nom_export("accord", None, [], tronque=False))


@router.get("/api/analyse/accord-inter.csv")
def analyse_accord_inter_export(conn: sqlite3.Connection = Depends(db),
                                portee: autorisation.Portee = Depends(portee_courante)):
    """Export CSV de l'accord INTER-annotateurs — même cœur que sa route JSON (ANA-7).

    **IL NOMME, et c'est une décision datée du 2026-09-08**, prise en connaissance des
    trois positions que le dépôt tenait déjà : l'écran nomme (réservé à qui écrit), le CLI
    nomme (« un rapport d'accord se lit pour arbitrer, puis se jette »), le dépôt ne publie
    que `nb_auteurs` et des taux. Un fichier téléchargé tombait entre le CLI et le dépôt,
    et AUTH-1 n'avait jamais tranché ce cas. Retenu : nommer, parce que refuser au fichier
    ce que l'écran donne déjà à la même personne serait une friction sans protection — la
    capture d'écran reste possible — et parce que ce fichier a UN usage, réunir deux
    personnes pour arbitrer un désaccord, que des pseudonymes rendraient impraticable.

    Ce qu'on accepte en échange, et qu'il faut avoir en tête : un fichier PERSISTE et
    circule là où le CLI se lit puis se jette. La garde n'est donc pas dans la forme mais
    dans l'accès — le 403 ci-dessous est celui de la route JSON, hérité et non réécrit.

    UNE LIGNE PAR CHAMP DIVERGENT, et le taux de la paire en colonnes : c'est le document
    d'une réunion d'arbitrage, où l'on veut à la fois le cas précis et le contexte qui dit
    s'il est isolé. Les taux par champ restent à l'écran et dans le CLI.
    """
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(
            403, "L'accord inter-annotateurs nomme les annotateurs et cite leurs "
                 "désaccords : il est réservé à qui écrit sur le corpus, de sorte que "
                 "ceux qui voient la mesure soient ceux qu'elle mesure.")
    # Deux gardes, et elles ne se remplacent pas : écrire (ceux qui voient la mesure sont
    # ceux qu'elle mesure), puis exporter (le fichier SORT). Le périmètre est donc ce
    # qu'on écrit ET qu'on peut sortir.
    r = accord_inter.rapport(conn, album_ids=_albums_inscriptibles(
        conn, _portee_d_export(portee)))
    taux = {tuple(sorted((p["a"], p["b"]))): p for p in r["paires"]}
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator=chr(10))
    w.writerow(["citation", "forme", "champ", "de", "valeur_de", "a", "valeur_a",
                "taux_paire", "retouches_paire"])
    for d in r["divergences"]:
        cit = (d.get("citation") or {}).get("texte", "")
        pr = taux.get(tuple(sorted((d["de"], d["a"]))), {})
        for df in d["diffs"]:
            w.writerow([cit, _csv_safe(d.get("forme") or ""), df["champ"],
                        _csv_safe(d["de"]), _csv_safe(df.get("avant") or ""),
                        _csv_safe(d["a"]), _csv_safe(df.get("apres") or ""),
                        pr.get("taux"), pr.get("retouches")])
    return _csv_response(buf.getvalue(),
                         _nom_export("accord-inter", None, [],
                                     tronque=bool(r.get("divergences_tronque"))))


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
    L'auteur connecté (en-tête Remote-User, INFRA-2) est enregistré sur la correction.

    NLP-2 — ce que l'annotateur a VU l'est aussi : la proposition du token avant la
    correction, et le modèle chargé. Un champ laissé vide accepte CETTE proposition, pas
    celle du prochain modèle. Limite écrite : entre un changement de `BD_SPACY_MODEL` et la
    réindexation qui doit le suivre, une région encore indexée par l'ancien modèle recevrait
    le nom du nouveau — la proposition gardée, elle, reste celle qui s'affichait."""
    # AUTH-2 — corriger la grammaire, c'est écrire sur la région.
    _get_region(conn, portee, region_id, ecriture=True)
    tok = conn.execute("SELECT texte, lemme, pos, morph FROM tokens "
                       "WHERE region_id = ? AND ordre = ?", (region_id, ordre)).fetchone()
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
    modele = nlp.model_info().get("model") or None      # NLP-2 ; modèle déjà chargé
    vu = ["" if tok[k] is None else tok[k] for k in ("lemme", "pos", "morph")]
    _corr_cols = ("ordre", "forme", "lemme", "pos", "morph", "etat")
    avant_corr = conn.execute(
        f"SELECT {', '.join(_corr_cols)} FROM token_correction "
        "WHERE region_id = ? AND ordre = ?", (region_id, ordre)).fetchone()
    conn.execute(
        "INSERT INTO token_correction "
        "  (region_id, ordre, forme, lemme, pos, morph, etat, auteur, obsolete, date_modif, "
        "   modele_auto, auto_lemme, auto_pos, auto_morph) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now'), ?, ?, ?, ?) "
        "ON CONFLICT(region_id, ordre) DO UPDATE SET "
        "  forme=excluded.forme, lemme=excluded.lemme, pos=excluded.pos, "
        "  morph=excluded.morph, etat=excluded.etat, auteur=excluded.auteur, "
        "  obsolete=0, date_modif=datetime('now'), modele_auto=excluded.modele_auto, "
        "  auto_lemme=excluded.auto_lemme, auto_pos=excluded.auto_pos, "
        "  auto_morph=excluded.auto_morph",
        (region_id, ordre, tok["texte"], lemme, pos, morph, payload.etat, auteur,
         modele, *vu))
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
    avait pas — sans jamais écraser le correcteur d'origine (COALESCE).

    NLP-2 — la proposition validée est gardée, avec le modèle, sur chaque ligne dont le token
    s'affiche, y compris une correction existante : là où elle laisse un champ vide, la
    validation se porte garante de ce qui s'affiche maintenant. L'auteur, lui, reste celui
    d'origine. Sans token (moteur absent), le relevé précédent est gardé tel quel."""
    # AUTH-2 — corriger la grammaire, c'est écrire sur la région.
    _get_region(conn, portee, region_id, ecriture=True)
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    nlp.ensure_loaded()          # spaCy hors transaction (cf. corriger_token)
    auteur = _auteur(request)
    modele = nlp.model_info().get("model") or None      # NLP-2 ; modèle déjà chargé
    reindex_region(conn, region_id)   # ré-ancre (aligne) d'abord → nettoie toute dérive du texte
    # 1) corrections cohérentes existantes → validées (auteur préservé : valider ≠ corriger)
    conn.execute("UPDATE token_correction "
                 "SET etat='valide', auteur=COALESCE(auteur, ?), date_modif=datetime('now') "
                 "WHERE region_id = ? AND obsolete = 0", (auteur, region_id))
    # 1 bis) NLP-2 : leur relevé suit ce qui s'affiche — là seulement où un token s'affiche.
    # Sans moteur, la réindexation ci-dessus vient de vider `tokens` sans ré-ancrer : relever
    # quand même remettrait à NULL ce que l'annotateur avait vu, au seul motif que le moteur
    # manque.
    ici = ("t.region_id = token_correction.region_id "
           "AND t.ordre = token_correction.ordre")
    vu = ", ".join(f"auto_{ch} = (SELECT COALESCE(t.{ch}, '') FROM tokens t WHERE {ici})"
                   for ch in ("lemme", "pos", "morph"))
    conn.execute(f"UPDATE token_correction SET modele_auto = ?, {vu} "
                 "WHERE region_id = ? AND obsolete = 0 "
                 f"  AND EXISTS (SELECT 1 FROM tokens t WHERE {ici})", (modele, region_id))
    # 2) tokens sans correction → ligne 'valide' (accepte l'auto ; auteur = le validateur)
    conn.execute(
        "INSERT INTO token_correction (region_id, ordre, forme, etat, auteur, obsolete, "
        "  modele_auto, auto_lemme, auto_pos, auto_morph) "
        "SELECT t.region_id, t.ordre, t.texte, 'valide', ?, 0, ?, "
        "       COALESCE(t.lemme, ''), COALESCE(t.pos, ''), COALESCE(t.morph, '') "
        "FROM tokens t WHERE t.region_id = ? AND NOT EXISTS "
        "  (SELECT 1 FROM token_correction c WHERE c.region_id=t.region_id AND c.ordre=t.ordre)",
        (auteur, modele, region_id))
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
