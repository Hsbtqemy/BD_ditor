"""Fiche de description des métadonnées d'une collection (roll-up).

Parcourt la base EN LECTURE SEULE et instancie, pour un périmètre donné (par
défaut : le corpus entier), les métadonnées décrites dans
`docs/dictionnaire-metadonnees.md`. Produit deux vues du MÊME modèle :

  • JSON — fiche roll-up (identité + couverture + provenance + vocabulaire + droits) ;
  • CSV  — catalogue champ par champ (le dictionnaire instancié, une ligne = un élément).

Les champs marqués « absent — à prévoir » dans le dictionnaire apparaissent dans le
catalogue mais restent VIDES tant qu'ils ne sont pas en base : la sortie est ainsi
honnête sur la couverture réelle. Périmètre par défaut : le corpus entier ; `--collection
<id>` restreint la couverture aux albums d'une collection et renseigne l'identité depuis
la ligne `collection` (v14). Gérer les collections : `gerer_collections.py`.

Usage :
    python tools/description_collection.py                     # JSON sur stdout
    python tools/description_collection.py --csv               # CSV sur stdout
    python tools/description_collection.py --json f.json --csv f.csv
    python tools/description_collection.py --json f.json --collection 3
La base suit la config du projet (BD_DB_PATH / BD_DATA_DIR).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402  (collection_row / collection_album_ids — palier collection)
import journal  # noqa: E402  (indicateurs de provenance dérivés du journal — A3)
from config import DB_PATH, BASE_DIR  # noqa: E402
from _commun import version_outil, environnement, portee_albums  # noqa: E402  (provenance / env / portée)


# --------------------------------------------------------------------------- #
# Petits helpers de requête
# --------------------------------------------------------------------------- #
def _un(conn, sql, params=()):
    """Renvoie la première colonne de la première ligne (ou None)."""
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def _dist(conn, sql, params=()):
    """Renvoie {clé: compte} à partir d'un GROUP BY à deux colonnes."""
    return {r[0]: r[1] for r in conn.execute(sql, params).fetchall()}


def _pct(n, d):
    return round(100 * n / d, 1) if d else None


def _fmt(d: dict) -> str:
    """Distribution → 'case:12; bulle:34' (VIDE si rien)."""
    return "; ".join(f"{k}:{v}" for k, v in d.items() if v)


def _responsables_desc(row) -> list:
    """`collection.responsables` (JSON) → liste de dicts (vide si absent/illisible)."""
    if not row or not row["responsables"]:
        return []
    try:
        val = json.loads(row["responsables"])
        return val if isinstance(val, list) else []
    except (ValueError, TypeError):
        return []


# --------------------------------------------------------------------------- #
# Collecte des agrégats (roll-up JSON + carte plate pour le CSV)
# --------------------------------------------------------------------------- #
def collecter(conn, collection_id=None) -> tuple[dict, dict]:
    """Calcule la fiche de description. Renvoie (rollup_json, agg_plat).

    `agg_plat` : {(niveau, element): "valeur ou agrégat"} — sert à remplir le CSV.
    `collection_id` (scoping `--collection`) restreint la COUVERTURE aux albums de la
    collection et renseigne l'IDENTITÉ depuis la ligne `collection` ; les catalogues de
    référence (personnages, vocabulaire, tags) restent comptés GLOBALEMENT (canoniques au
    corpus), seuls leurs LIENS vers des régions scopées sont restreints.
    """
    # --- Périmètre : identité + prédicats de portée ------------------------- #
    row = database.collection_row(conn, collection_id) if collection_id is not None else None
    if collection_id is not None and row is None:
        raise SystemExit(f"Collection {collection_id} introuvable.")
    album_ids = (database.collection_album_ids(conn, collection_id)
                 if collection_id is not None else None)
    P = portee_albums(album_ids)
    if P is None:                                   # corpus entier : aucun filtre
        W_alb = W_pl = W_reg = W_tok = A_reg = A_tok = W_pose = ""
    else:
        W_alb = f" WHERE id IN {P['albums']}"
        W_pl = f" WHERE album_id IN {P['albums']}"
        W_reg = f" WHERE id IN {P['regions']}"           # regions.id
        A_reg = f" AND id IN {P['regions']}"
        W_tok = f" WHERE region_id IN {P['regions']}"    # tables portant region_id
        A_tok = f" AND region_id IN {P['regions']}"
        W_pose = (f" WHERE annotation_id IN (SELECT id FROM annotations "
                  f"WHERE region_id IN {P['regions']})")

    # --- Volumes de base ---------------------------------------------------- #
    albums = _un(conn, "SELECT COUNT(*) FROM albums" + W_alb)
    a = conn.execute(
        "SELECT COUNT(auteur) auteur, COUNT(annee) annee, COUNT(editeur) editeur, "
        "COUNT(serie) serie, COUNT(description) descr, MIN(annee) amin, MAX(annee) amax "
        "FROM albums" + W_alb).fetchone()
    # N0 enrichi (v15) : contributions (Zotero-like) + couverture des champs d'édition.
    contrib = _un(conn, "SELECT COUNT(*) FROM contribution"
                        + (f" WHERE album_id IN {P['albums']}" if P else ""))
    roles_n = _un(conn, "SELECT COUNT(*) FROM contribution_role")   # catalogue global
    ed = conn.execute(
        "SELECT COUNT(date_edition) de, COUNT(date_originale) do, COUNT(langue) la, "
        "COUNT(type_oeuvre) ty, COUNT(lieu_edition) li, COUNT(edition_tirage) et, "
        "COUNT(isbn) isb, COUNT(format_physique) fo FROM albums" + W_alb).fetchone()

    p = conn.execute(
        "SELECT COUNT(*) t, SUM(CASE WHEN role='recit' THEN 1 ELSE 0 END) recit, "
        "COUNT(validee) validees, COUNT(chemin_tiff) tiff, COUNT(largeur_px) dims, "
        "COUNT(date_segmentation) seg, COUNT(verrouillee) verr FROM planches" + W_pl).fetchone()
    planches, recit = p["t"], (p["recit"] or 0)
    paratexte = planches - recit
    statuts = _dist(conn, "SELECT statut, COUNT(*) FROM planches" + W_pl + " GROUP BY statut")

    regions = _un(conn, "SELECT COUNT(*) FROM regions" + W_reg)
    par_type = _dist(conn, "SELECT type, COUNT(*) FROM regions" + W_reg
                           + " GROUP BY type ORDER BY COUNT(*) DESC")
    enfants = _un(conn, "SELECT COUNT(*) FROM regions WHERE parent_id IS NOT NULL" + A_reg)
    avec_geom = _un(conn, "SELECT COUNT(*) FROM regions WHERE x IS NOT NULL" + A_reg)
    avec_ordre = _un(conn, "SELECT COUNT(*) FROM regions WHERE ordre IS NOT NULL" + A_reg)
    sources = _dist(conn, "SELECT source, COUNT(*) FROM regions WHERE source IS NOT NULL"
                          + A_reg + " GROUP BY source ORDER BY COUNT(*) DESC")

    # --- OCR (contenu textuel) --------------------------------------------- #
    txt_tot = _un(conn, "SELECT COUNT(*) FROM regions WHERE type IN "
                        "('bulle','cartouche','texte')" + A_reg)
    txt_ocr = _un(conn, "SELECT COUNT(*) FROM regions WHERE type IN "
                        "('bulle','cartouche','texte') AND ocr_texte IS NOT NULL "
                        "AND TRIM(ocr_texte) <> ''" + A_reg)

    # --- Tokens (analyse linguistique) ------------------------------------- #
    tokens = _un(conn, "SELECT COUNT(*) FROM tokens" + W_tok)
    prov = _dist(conn, "SELECT provenance, COUNT(*) FROM tokens_effectifs" + W_tok
                       + " GROUP BY provenance")
    par_pos = _dist(conn, "SELECT pos, COUNT(*) FROM tokens_effectifs WHERE pos IS NOT NULL"
                          + A_tok + " GROUP BY pos ORDER BY COUNT(*) DESC LIMIT 8")
    corr = conn.execute(
        "SELECT SUM(CASE WHEN etat='corrige' THEN 1 ELSE 0 END) c, "
        "SUM(CASE WHEN etat='valide' THEN 1 ELSE 0 END) v, "
        "SUM(obsolete) obs FROM token_correction" + W_tok).fetchone()

    # --- Annotation interprétative ----------------------------------------- #
    notes = _un(conn, "SELECT COUNT(*) FROM annotations WHERE note IS NOT NULL "
                      "AND TRIM(note) <> ''" + A_tok)
    tags_n = _un(conn, "SELECT COUNT(*) FROM tags")           # catalogue de référence (global)
    poses = _un(conn, "SELECT COUNT(*) FROM annotation_tags" + W_pose)

    # --- Entités personnages (entités globales ; LIENS scopés) ------------- #
    perso = _un(conn, "SELECT COUNT(*) FROM personnages")     # entités canoniques (globales)
    loc_liens = _un(conn, "SELECT COUNT(*) FROM bulle_locuteur" + W_tok)
    loc_distinct = _un(conn, "SELECT COUNT(DISTINCT personnage_id) FROM bulle_locuteur" + W_tok)
    pres_liens = _un(conn, "SELECT COUNT(*) FROM personnage_presence" + W_tok)

    # --- Vocabulaire facetté (catalogue global ; poses `ra` scopées) ------- #
    dimensions = []
    for d in conn.execute("SELECT id, cible, nom FROM attribut_dimension "
                          "ORDER BY cible, nom"):
        vals = [r[0] for r in conn.execute(
            "SELECT valeur FROM attribut_valeur WHERE dimension_id = ? ORDER BY valeur",
            (d["id"],))]
        dimensions.append({"cible": d["cible"], "nom": d["nom"],
                           "valeurs": vals, "pct_defini": None})
    val_tot = _un(conn, "SELECT COUNT(*) FROM attribut_valeur")
    pa = _un(conn, "SELECT COUNT(*) FROM personnage_attribut")   # profils (entité globale)
    ra = _un(conn, "SELECT COUNT(*) FROM region_attribut" + W_tok)

    # --- Paradonnée / système ---------------------------------------------- #
    meta = {r[0]: r[1] for r in conn.execute("SELECT cle, valeur FROM meta")}
    schema_version = _un(conn, "PRAGMA user_version")
    resp = _responsables_desc(row)

    # --- Roll-up JSON ------------------------------------------------------- #
    rollup = {
        "description_collection": {
            "genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "outil": version_outil(BASE_DIR),
            "schema_version": schema_version,
            "perimetre": {"type": "collection", "collection_id": collection_id,
                          "portee": row["nom"] if row else "corpus entier",
                          **({"albums_scope": len(album_ids)} if album_ids is not None else {})},
            "identite": {  # renseignée depuis la ligne `collection` (v14) ; None = corpus entier
                "nom": row["nom"] if row else None,
                "description": row["description"] if row else None,
                "responsables": resp,
                "date_constitution": row["date_creation"] if row else None,
                "periode_couverte": ({"debut": row["date_debut"], "fin": row["date_fin"]}
                                     if row else None),
                "licence_defaut": row["licence_defaut"] if row else None,
                "base_legale": row["base_legale"] if row else None,
                "statut_diffusion": row["statut_diffusion"] if row else None,
                "date_embargo": row["date_embargo"] if row else None,
                "pid": None,
            },
            "couverture": {
                "albums": albums,
                "descriptif_n0": {                       # enrichissement bibliographique (v15)
                    "contributions": contrib, "roles_vocabulaire": roles_n,
                    "avec_date_edition": ed["de"], "avec_langue": ed["la"],
                    "avec_type": ed["ty"], "avec_isbn": ed["isb"],
                    "avec_lieu": ed["li"], "avec_format": ed["fo"]},
                "planches": {"total": planches, "recit": recit,
                             "paratexte": paratexte, "validees": p["validees"],
                             "par_statut": statuts},
                "regions": {"total": regions, "par_type": par_type,
                            "imbriquees": enfants},
                "ocr": {"regions_textuelles": txt_tot, "renseignees": txt_ocr,
                        "taux_pct": _pct(txt_ocr, txt_tot)},
                "tokens": {"total": tokens, "par_provenance": prov,
                           "par_pos": par_pos},
                "annotations": {"notes": notes, "tags_distincts": tags_n,
                                "poses": poses},
                "personnages": {"total": perso, "locuteurs_distincts": loc_distinct,
                                "liens_locuteur": loc_liens, "liens_presence": pres_liens,
                                "avec_alignement_autorite": None},
            },
            "provenance_globale": {
                "geometrie": sources,
                "nlp": {"modele": meta.get("nlp_model"), "spacy": meta.get("nlp_spacy"),
                        "tokens_indexes": meta.get("nlp_reindexed_count"),
                        "reindexe_le": meta.get("nlp_reindexed_at")},
                # A3 : indicateurs dérivés du journal de provenance/audit (part machine vs
                # humaine, dérive = pré-remplissage retouché, comptes de runs & d'actes).
                "audit": journal.indicateurs_provenance(conn, album_ids),
                "environnement": environnement(),  # python + versions installées (à l'export)
            },
            # A4 : maturité du lexique situé (% défini), scopée par appartenance à la collection.
            "vocabulaire": {"dimensions": dimensions,
                            "lexique": database.lexique_resume(conn, collection_id)},
            "droits": {
                "ouvert": ["géométrie", "structure", "ordre", "citation", "lemme",
                           "pos", "morph", "tags", "notes", "personnages", "attributs",
                           "provenance"],
                "agregat": ["tokens.texte", "token_correction.forme"],
                "restreint": ["regions.ocr_texte", "planches.chemin_tiff",
                              "planches.chemin_web"],
            },
        }
    }

    # --- Carte plate pour le CSV ------------------------------------------- #
    def dims_couv():
        return _pct(sum(1 for d in dimensions if d["valeurs"]), len(dimensions)) \
            if dimensions else None

    debut, fin = (row["date_debut"], row["date_fin"]) if row else (None, None)
    agg = {
        ("collection", "nom"): row["nom"] if row else "",
        ("collection", "description"): (row["description"] if row else "") or "",
        ("collection", "licence_defaut"): (row["licence_defaut"] if row else "") or "",
        ("collection", "base_legale"): (row["base_legale"] if row else "") or "",
        ("collection", "statut_diffusion"):
            ((row["statut_diffusion"] or "")
             + (f" (levée {row['date_embargo']})" if row and row["date_embargo"] else ""))
            if row else "",
        ("collection", "responsables"): "; ".join(r.get("nom", "") for r in resp),
        ("collection", "dates"): (f"{debut or '?'} → {fin or '?'}") if (debut or fin) else "",
        ("collection", "collection_album"): (len(album_ids) if album_ids is not None else ""),
        ("collection", "couverture_volume"):
            f"{albums} albums; {planches} planches; {regions} régions; {tokens} tokens",
        ("collection", "provenance_globale"):
            f"géométrie: {_fmt(sources)}; nlp: {meta.get('nlp_model') or '∅'}",
        ("album", "id"): albums,
        ("album", "titre"): albums,
        ("album", "auteur"): a["auteur"],
        ("album", "annee"): (f"{a['annee']} renseignées "
                             f"({a['amin']}–{a['amax']})" if a["annee"] else 0),
        ("album", "editeur"): a["editeur"],
        ("album", "serie"): a["serie"],
        ("album", "description"): a["descr"],
        ("album", "date_import"): albums,
        ("album", "nombre_pages"): planches,
        ("album", "contribution"): contrib,
        ("album", "contribution.role"): f"{roles_n} rôles au vocabulaire",
        ("album", "date_edition"): ed["de"],
        ("album", "date_originale"): ed["do"],
        ("album", "type_oeuvre"): ed["ty"],
        ("album", "langue"): ed["la"],
        ("album", "lieu_edition"): ed["li"],
        ("album", "edition_tirage"): ed["et"],
        ("album", "isbn"): ed["isb"],
        ("album", "format_physique"): ed["fo"],
        ("planche", "id"): planches,
        ("planche", "album_id"): planches,
        ("planche", "numero"): planches,
        ("planche", "role"): f"recit:{recit}; paratexte:{paratexte}",
        ("planche", "numero_editorial"): recit,
        ("planche", "chemin_tiff"): p["tiff"],
        ("planche", "chemin_web"): planches,
        ("planche", "largeur_px/hauteur_px"): p["dims"],
        ("planche", "statut"): _fmt(statuts),
        ("planche", "date_segmentation"): p["seg"],
        ("planche", "validee"): p["validees"],
        ("planche", "verrouillee"): p["verr"],
        ("region", "id"): regions,
        ("region", "planche_id"): regions,
        ("region", "parent_id"): enfants,
        ("region", "type"): _fmt(par_type),
        ("region", "x·y·w·h"): avec_geom,
        ("region", "ordre"): avec_ordre,
        ("region", "source"): _fmt(sources),
        ("region", "date_creation"): regions,
        ("region", "citation"): "dérivé",
        ("ocr", "ocr_texte"): f"{txt_ocr}/{txt_tot} ({_pct(txt_ocr, txt_tot)}%)",
        ("tokens", "ordre"): tokens,
        ("tokens", "texte"): tokens,
        ("tokens", "lemme"): tokens,
        ("tokens", "pos"): _fmt(par_pos),
        ("tokens", "morph"): tokens,
        ("tokens", "correction.etat"):
            f"corrige:{corr['c'] or 0}; valide:{corr['v'] or 0}; obsolète:{corr['obs'] or 0}",
        ("tokens", "effectifs.provenance"): _fmt(prov),
        ("annotation", "note"): notes,
        ("annotation", "tags.label"): tags_n,
        ("annotation", "annotation_tags"): poses,
        ("personnage", "nom"): perso,
        ("personnage", "bulle_locuteur"): f"{loc_liens} liens; {loc_distinct} distincts",
        ("personnage", "personnage_presence"): pres_liens,
        ("vocabulaire", "dimension.nom"): len(dimensions),
        ("vocabulaire", "valeur"): val_tot,
        ("vocabulaire", "personnage_attribut"): pa,
        ("vocabulaire", "region_attribut"): ra,
        ("paradonnee", "nlp_model"): meta.get("nlp_model") or "",
        ("paradonnee", "nlp_reindexed_count/_at"):
            f"{meta.get('nlp_reindexed_count') or 0} le {meta.get('nlp_reindexed_at') or '∅'}",
        ("paradonnee", "schema_version"): schema_version,
    }
    return rollup, {k: ("" if v is None else str(v)) for k, v in agg.items()}


# --------------------------------------------------------------------------- #
# Catalogue — le dictionnaire, ligne par ligne (statut figé, valeur instanciée)
# Colonnes : niveau, element, qualifie, provenance, statut, standard, ouvrable.
# --------------------------------------------------------------------------- #
CATALOGUE = [
    ("collection", "nom", "nom du corpus", "descriptif", "structuré", "DC:title", "ouvert"),
    ("collection", "description", "objet/périmètre", "descriptif", "libre", "DC:description", "ouvert"),
    ("collection", "licence_defaut", "régime de diffusion", "descriptif", "structuré", "DC:rights", "ouvert"),
    ("collection", "base_legale", "base légale d'accès aux données", "descriptif", "libre", "DC:rights/PROV", "ouvert"),
    ("collection", "statut_diffusion", "régime d'accès (public/embargo/restreint/privé)", "descriptif", "structuré", "DataCite/Nakala", "ouvert"),
    ("collection", "responsables", "qui gère (JSON nom+rôle+orcid)", "descriptif", "structuré", "DC:creator", "ouvert"),
    ("collection", "dates", "constitution/couverture", "descriptif", "structuré", "DC:date", "ouvert"),
    ("collection", "collection_album", "appartenance album↔collection (N-N statique)", "humain", "structuré", "—", "ouvert"),
    ("collection", "couverture_volume", "ampleur du jeu", "dérivé", "dérivé", "DC:extent", "ouvert"),
    ("collection", "provenance_globale", "moteurs+versions", "dérivé", "dérivé", "PROV", "ouvert"),
    ("collection", "version_gel", "instantané citable", "système", "absent — à prévoir (dormant)", "DataCite", "ouvert"),
    ("collection", "pid", "DOI du dépôt", "système", "absent — à prévoir (dormant)", "DataCite", "ouvert"),
    ("album", "id", "identifiant interne", "système", "structuré", "—", "ouvert"),
    ("album", "titre", "titre de l'œuvre", "descriptif", "structuré", "DC:title", "ouvert"),
    ("album", "auteur", "responsabilité (legacy)", "descriptif", "libre", "DC:creator", "ouvert"),
    ("album", "annee", "année (legacy)", "descriptif", "structuré", "DC:date", "ouvert"),
    ("album", "editeur", "maison d'édition", "descriptif", "libre", "DC:publisher", "ouvert"),
    ("album", "serie", "série", "descriptif", "libre", "DC:isPartOf", "ouvert"),
    ("album", "description", "note libre", "descriptif", "libre", "DC:description", "ouvert"),
    ("album", "date_import", "entrée dans l'outil", "système", "structuré", "PROV", "ouvert"),
    ("album", "nombre_pages", "volume", "dérivé", "dérivé", "DC:extent", "ouvert"),
    ("album", "contribution", "contributeur (nom+rôle)", "descriptif", "structuré (v15)", "DCterms", "ouvert"),
    ("album", "contribution.role", "rôle du contributeur (contrôlé-ouvert)", "descriptif", "structuré (v15)", "MARC Relators", "ouvert"),
    ("album", "contributeur_entite", "alias personne canonique", "descriptif", "absent — à prévoir (dormant)", "VIAF/IdRef", "ouvert"),
    ("album", "date_edition", "édition détenue (ancre)", "descriptif", "structuré (v15)", "DC:issued", "ouvert"),
    ("album", "date_originale", "1re parution", "descriptif", "structuré (v15)", "DC:created", "ouvert"),
    ("album", "type_oeuvre", "BD/roman graphique", "descriptif", "structuré (v15)", "DC:type", "ouvert"),
    ("album", "langue", "langue de l'expression", "descriptif", "structuré (v15)", "DC:language", "ouvert"),
    ("album", "lieu_edition", "ville d'édition", "descriptif", "structuré (v15)", "DC:coverage", "ouvert"),
    ("album", "edition_tirage", "mention d'édition", "descriptif", "structuré (v15)", "DC", "ouvert"),
    ("album", "isbn", "ISBN / dépôt légal", "descriptif", "structuré (v15)", "DC:identifier", "ouvert"),
    ("album", "format_physique", "dimensions/reliure", "matériel", "structuré (v15)", "DC:format", "ouvert"),
    ("album", "pid", "DOI/ARK", "système", "absent — à prévoir", "DataCite", "ouvert"),
    ("planche", "id", "identifiant", "système", "structuré", "—", "ouvert"),
    ("planche", "album_id", "rattachement", "système", "structuré", "—", "ouvert"),
    ("planche", "numero", "ordre d'import (page physique)", "système", "structuré", "—", "ouvert"),
    ("planche", "role", "statut éditorial", "humain", "structuré", "—", "ouvert"),
    ("planche", "numero_editorial", "rang parmi les récits", "dérivé", "dérivé", "—", "ouvert"),
    ("planche", "chemin_tiff", "pointeur master", "système", "structuré", "—", "restreint"),
    ("planche", "chemin_web", "pointeur dérivé", "système", "structuré", "IIIF", "restreint"),
    ("planche", "largeur_px/hauteur_px", "dimensions master", "matériel", "structuré", "TEI surface", "ouvert"),
    ("planche", "statut", "avancement", "système", "structuré", "—", "ouvert"),
    ("planche", "date_segmentation", "date passe cases", "paradonnée", "structuré", "PROV", "ouvert"),
    ("planche", "validee", "validation humaine", "humain", "structuré", "PROV", "ouvert"),
    ("planche", "verrouillee", "protection passes auto", "humain", "structuré", "—", "ouvert"),
    ("planche", "dpi", "résolution du scan", "matériel", "absent — à prévoir", "—", "ouvert"),
    ("planche", "mode", "espace colorimétrique", "matériel", "absent — à prévoir", "—", "ouvert"),
    ("planche", "dimensions_physiques", "taille réelle (cm)", "matériel", "absent — à prévoir", "DC:format", "ouvert"),
    ("planche", "source_numerisation", "appareil/conditions", "matériel", "absent — à prévoir", "PREMIS", "ouvert"),
    ("region", "id", "identifiant", "système", "structuré", "—", "ouvert"),
    ("region", "planche_id", "rattachement", "système", "structuré", "—", "ouvert"),
    ("region", "parent_id", "contenance hiérarchique", "machine/humain", "structuré", "TEI", "ouvert"),
    ("region", "type", "nature de la zone", "machine/humain", "structuré", "TEI zone@type", "ouvert"),
    ("region", "x·y·w·h", "boîte englobante (px master)", "machine→humain", "structuré", "IIIF xywh", "ouvert"),
    ("region", "ordre", "rang de lecture", "machine→humain", "structuré", "—", "ouvert"),
    ("region", "source", "producteur de la géométrie", "provenance", "structuré", "PROV", "ouvert"),
    ("region", "date_creation", "création de la zone", "paradonnée", "structuré", "PROV", "ouvert"),
    ("region", "citation", "repère éditorial", "dérivé", "dérivé", "—", "ouvert"),
    ("region", "activite_id", "run générateur", "paradonnée", "structuré", "PROV wasGeneratedBy", "ouvert"),
    ("region", "touche+date_modification", "retouche humaine", "paradonnée", "structuré", "PROV/TEI @resp", "ouvert"),
    ("region", "certitude", "confiance sur la zone", "machine/humain", "absent — à prévoir", "TEI @cert", "ouvert"),
    ("ocr", "ocr_texte", "texte reconnu de la zone", "machine→humain", "libre", "TEI line", "restreint"),
    ("tokens", "ordre", "position du mot", "machine", "structuré", "UD", "ouvert"),
    ("tokens", "texte", "forme de surface", "machine", "structuré", "UD FORM", "agrégat"),
    ("tokens", "lemme", "forme canonique", "machine", "structuré", "UD LEMMA", "ouvert"),
    ("tokens", "pos", "catégorie grammaticale", "machine", "structuré", "UD UPOS", "ouvert"),
    ("tokens", "morph", "traits morphologiques", "machine", "structuré", "UD FEATS", "ouvert"),
    ("tokens", "correction.lemme/pos/morph", "correction humaine", "humain", "structuré", "UD", "ouvert"),
    ("tokens", "correction.forme", "forme visée (ancrage)", "humain", "structuré", "—", "agrégat"),
    ("tokens", "correction.etat", "état de la correction", "humain", "structuré", "PROV", "ouvert"),
    ("tokens", "correction.auteur", "qui a corrigé/validé", "humain", "structuré", "PROV/TEI @resp", "ouvert"),
    ("tokens", "correction.date_modif", "quand", "paradonnée", "structuré", "PROV", "ouvert"),
    ("tokens", "correction.obsolete", "à revérifier", "système", "structuré", "—", "ouvert"),
    ("tokens", "effectifs.provenance", "valeur effective", "dérivé", "dérivé", "PROV", "ouvert"),
    ("tokens", "effectifs.a_revoir", "une correction a dérivé", "dérivé", "dérivé", "—", "ouvert"),
    ("annotation", "note", "commentaire libre", "humain", "libre", "TEI note", "ouvert"),
    ("annotation", "date_creation/date_modification", "vie de l'annotation", "paradonnée", "structuré", "PROV", "ouvert"),
    ("annotation", "tags.label", "étiquette émergente", "humain", "structuré", "SKOS prefLabel", "ouvert"),
    ("annotation", "tags.description", "glose du tag", "humain", "libre", "SKOS definition", "ouvert"),
    ("annotation", "tags.couleur", "présentation", "humain", "structuré", "—", "ouvert"),
    ("annotation", "annotation_tags", "pose d'un tag", "humain", "structuré", "—", "ouvert"),
    ("personnage", "nom", "identité récurrente", "humain", "structuré", "—", "ouvert"),
    ("personnage", "serie", "désambiguïsation", "humain", "structuré", "—", "ouvert"),
    ("personnage", "notes", "note libre", "humain", "libre", "—", "ouvert"),
    ("personnage", "bulle_locuteur", "qui parle", "humain", "structuré", "—", "ouvert"),
    ("personnage", "personnage_presence", "qui est montré", "humain", "structuré", "—", "ouvert"),
    ("personnage", "alignement_autorite", "lien vers référentiel", "humain", "absent — à prévoir", "SKOS exactMatch", "ouvert"),
    ("vocabulaire", "dimension.cible", "à quoi s'applique l'axe", "humain", "structuré", "—", "ouvert"),
    ("vocabulaire", "dimension.nom", "axe (registre, origine…)", "humain", "structuré", "SKOS", "ouvert"),
    ("vocabulaire", "valeur", "valeur canonique de l'axe", "humain", "structuré", "SKOS concept", "ouvert"),
    ("vocabulaire", "personnage_attribut", "profil du personnage", "humain", "structuré", "—", "ouvert"),
    ("vocabulaire", "region_attribut", "situation de la case", "humain", "structuré", "—", "ouvert"),
    ("vocabulaire", "collection_id", "portée d'appartenance (NULL=global)", "humain", "structuré (v17)", "SKOS", "ouvert"),
    ("vocabulaire", "definition", "sens dimension/valeur (tag = description)", "humain", "structuré (v17)", "SKOS definition", "ouvert"),
    ("vocabulaire", "note_portee", "cadre d'emploi", "humain", "structuré (v17)", "SKOS scopeNote", "ouvert"),
    ("vocabulaire", "etat_definitionnel", "provisoire→défini", "humain", "structuré (v17)", "—", "ouvert"),
    ("vocabulaire", "pct_defini", "part du vocabulaire documenté", "dérivé", "dérivé (v17)", "—", "ouvert"),
    ("paradonnee", "nlp_model", "modèle NLP ayant indexé", "paradonnée", "structuré", "PROV", "ouvert"),
    ("paradonnee", "nlp_reindexed_count/_at", "ampleur+date de réindex", "paradonnée", "structuré", "PROV", "ouvert"),
    ("paradonnee", "schema_version", "version du schéma", "système", "structuré", "—", "ouvert"),
    ("paradonnee", "activite_run", "exécution de passe", "paradonnée", "structuré", "PROV Activity", "ouvert"),
    ("paradonnee", "evenement_journal", "acte atomique append-only", "paradonnée", "structuré", "PROV/TEI change", "ouvert"),
    ("paradonnee", "indicateurs_couverture", "% touché/dérive/runs/actes", "dérivé", "dérivé", "—", "ouvert"),
    ("paradonnee", "licence_droits", "régime de diffusion par jeu", "descriptif", "absent — à prévoir", "DC:rights", "ouvert"),
]

_CSV_COLS = ["niveau", "element", "qualifie", "provenance", "statut", "standard",
             "ouvrable", "valeur_ou_agregat"]


def catalogue_csv(agg: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_CSV_COLS)
    for niveau, element, *reste in CATALOGUE:
        w.writerow([niveau, element, *reste, agg.get((niveau, element), "")])
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _connexion_ro():
    """Connexion LECTURE SEULE sur la base configurée (URI mode=ro)."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fiche de description des métadonnées "
                                             "d'une collection (corpus entier).")
    ap.add_argument("--json", nargs="?", const="-", metavar="FICHIER",
                    help="écrit le roll-up JSON (défaut si aucun format demandé)")
    ap.add_argument("--csv", nargs="?", const="-", metavar="FICHIER",
                    help="écrit le catalogue CSV")
    ap.add_argument("--collection", type=int, metavar="ID",
                    help="restreint le périmètre à cette collection (défaut : corpus entier)")
    args = ap.parse_args(argv)

    with _connexion_ro() as conn:
        rollup, agg = collecter(conn, collection_id=args.collection)

    if args.json is None and args.csv is None:
        args.json = "-"                      # défaut : JSON sur stdout

    if args.json is not None:
        texte = json.dumps(rollup, ensure_ascii=False, indent=2)
        if args.json == "-":
            print(texte)
        else:
            with open(args.json, "w", encoding="utf-8") as f:
                f.write(texte + "\n")
            print(f"JSON écrit : {args.json}", file=sys.stderr)

    if args.csv is not None:
        texte = catalogue_csv(agg)
        if args.csv == "-":
            sys.stdout.write(texte)
        else:
            with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:  # BOM → Excel
                f.write(texte)
            print(f"CSV écrit : {args.csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
