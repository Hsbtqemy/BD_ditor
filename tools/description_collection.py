"""Fiche de description des métadonnées d'une collection (roll-up).

Parcourt la base EN LECTURE SEULE et instancie, pour un périmètre donné (par
défaut : le corpus entier), les métadonnées décrites dans
`docs/dictionnaire-metadonnees.md`. Produit deux vues du MÊME modèle :

  • JSON — fiche roll-up (identité + couverture + provenance + vocabulaire + droits) ;
  • CSV  — catalogue champ par champ (le dictionnaire instancié, une ligne = un élément).

Les champs marqués « absent — à prévoir » dans le dictionnaire apparaissent dans le
catalogue mais restent VIDES tant qu'ils ne sont pas en base : la sortie est ainsi
honnête sur la couverture réelle. L'entité `collection` n'existant pas encore, le
périmètre par défaut est le corpus entier (collection implicite).

Usage :
    python tools/description_collection.py                     # JSON sur stdout
    python tools/description_collection.py --csv               # CSV sur stdout
    python tools/description_collection.py --json f.json --csv f.csv
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

from config import DB_PATH, BASE_DIR  # noqa: E402
from _commun import version_outil  # noqa: E402  (provenance de l'outil, partagée)


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


# --------------------------------------------------------------------------- #
# Collecte des agrégats (roll-up JSON + carte plate pour le CSV)
# --------------------------------------------------------------------------- #
def collecter(conn) -> tuple[dict, dict]:
    """Calcule la fiche de description. Renvoie (rollup_json, agg_plat).

    `agg_plat` : {(niveau, element): "valeur ou agrégat"} — sert à remplir le CSV.
    """
    # --- Volumes de base ---------------------------------------------------- #
    albums = _un(conn, "SELECT COUNT(*) FROM albums")
    a = conn.execute(
        "SELECT COUNT(auteur) auteur, COUNT(annee) annee, COUNT(editeur) editeur, "
        "COUNT(serie) serie, COUNT(description) descr, MIN(annee) amin, MAX(annee) amax "
        "FROM albums").fetchone()
    p = conn.execute(
        "SELECT COUNT(*) t, SUM(CASE WHEN role='recit' THEN 1 ELSE 0 END) recit, "
        "COUNT(validee) validees, COUNT(chemin_tiff) tiff, COUNT(largeur_px) dims, "
        "COUNT(date_segmentation) seg, COUNT(verrouillee) verr FROM planches").fetchone()
    planches, recit = p["t"], (p["recit"] or 0)
    paratexte = planches - recit
    statuts = _dist(conn, "SELECT statut, COUNT(*) FROM planches GROUP BY statut")

    regions = _un(conn, "SELECT COUNT(*) FROM regions")
    par_type = _dist(conn, "SELECT type, COUNT(*) FROM regions GROUP BY type "
                           "ORDER BY COUNT(*) DESC")
    enfants = _un(conn, "SELECT COUNT(*) FROM regions WHERE parent_id IS NOT NULL")
    avec_geom = _un(conn, "SELECT COUNT(*) FROM regions WHERE x IS NOT NULL")
    avec_ordre = _un(conn, "SELECT COUNT(*) FROM regions WHERE ordre IS NOT NULL")
    sources = _dist(conn, "SELECT source, COUNT(*) FROM regions WHERE source IS NOT NULL "
                          "GROUP BY source ORDER BY COUNT(*) DESC")

    # --- OCR (contenu textuel) --------------------------------------------- #
    txt_tot = _un(conn, "SELECT COUNT(*) FROM regions WHERE type IN "
                        "('bulle','cartouche','texte')")
    txt_ocr = _un(conn, "SELECT COUNT(*) FROM regions WHERE type IN "
                        "('bulle','cartouche','texte') AND ocr_texte IS NOT NULL "
                        "AND TRIM(ocr_texte) <> ''")

    # --- Tokens (analyse linguistique) ------------------------------------- #
    tokens = _un(conn, "SELECT COUNT(*) FROM tokens")
    prov = _dist(conn, "SELECT provenance, COUNT(*) FROM tokens_effectifs "
                       "GROUP BY provenance")
    par_pos = _dist(conn, "SELECT pos, COUNT(*) FROM tokens_effectifs WHERE pos IS NOT NULL "
                          "GROUP BY pos ORDER BY COUNT(*) DESC LIMIT 8")
    corr = conn.execute(
        "SELECT SUM(CASE WHEN etat='corrige' THEN 1 ELSE 0 END) c, "
        "SUM(CASE WHEN etat='valide' THEN 1 ELSE 0 END) v, "
        "SUM(obsolete) obs FROM token_correction").fetchone()

    # --- Annotation interprétative ----------------------------------------- #
    notes = _un(conn, "SELECT COUNT(*) FROM annotations WHERE note IS NOT NULL "
                      "AND TRIM(note) <> ''")
    tags_n = _un(conn, "SELECT COUNT(*) FROM tags")
    poses = _un(conn, "SELECT COUNT(*) FROM annotation_tags")

    # --- Entités personnages ----------------------------------------------- #
    perso = _un(conn, "SELECT COUNT(*) FROM personnages")
    loc_liens = _un(conn, "SELECT COUNT(*) FROM bulle_locuteur")
    loc_distinct = _un(conn, "SELECT COUNT(DISTINCT personnage_id) FROM bulle_locuteur")
    pres_liens = _un(conn, "SELECT COUNT(*) FROM personnage_presence")

    # --- Vocabulaire facetté ----------------------------------------------- #
    dimensions = []
    for d in conn.execute("SELECT id, cible, nom FROM attribut_dimension "
                          "ORDER BY cible, nom"):
        vals = [r[0] for r in conn.execute(
            "SELECT valeur FROM attribut_valeur WHERE dimension_id = ? ORDER BY valeur",
            (d["id"],))]
        dimensions.append({"cible": d["cible"], "nom": d["nom"],
                           "valeurs": vals, "pct_defini": None})
    val_tot = _un(conn, "SELECT COUNT(*) FROM attribut_valeur")
    pa = _un(conn, "SELECT COUNT(*) FROM personnage_attribut")
    ra = _un(conn, "SELECT COUNT(*) FROM region_attribut")

    # --- Paradonnée / système ---------------------------------------------- #
    meta = {r[0]: r[1] for r in conn.execute("SELECT cle, valeur FROM meta")}
    schema_version = _un(conn, "PRAGMA user_version")

    # --- Roll-up JSON ------------------------------------------------------- #
    rollup = {
        "description_collection": {
            "genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "outil": version_outil(BASE_DIR),
            "schema_version": schema_version,
            "perimetre": {"type": "collection", "collection_id": None,
                          "portee": "corpus entier"},
            "identite": {  # entité `collection` absente (à prévoir) → non renseignée
                "nom": None, "description": None, "responsables": [],
                "date_constitution": None, "periode_couverte": None,
                "licence_defaut": None, "pid": None,
            },
            "couverture": {
                "albums": albums,
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
                "versions_moteurs": None,  # kumiko/yolo/easyocr non tracées (run — à prévoir)
            },
            "vocabulaire": {"dimensions": dimensions},
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

    agg = {
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
    ("collection", "nom", "nom du corpus", "descriptif", "absent — à prévoir", "DC:title", "ouvert"),
    ("collection", "description", "objet/périmètre", "descriptif", "absent — à prévoir", "DC:description", "ouvert"),
    ("collection", "licence_defaut", "régime de diffusion", "descriptif", "absent — à prévoir", "DC:rights", "ouvert"),
    ("collection", "responsables", "qui gère", "descriptif", "absent — à prévoir", "DC:creator", "ouvert"),
    ("collection", "dates", "constitution/couverture", "descriptif", "absent — à prévoir", "DC:date", "ouvert"),
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
    ("album", "contribution", "contributeur (nom+rôle)", "descriptif", "absent — à prévoir", "DCterms", "ouvert"),
    ("album", "contribution.role", "rôle du contributeur", "descriptif", "absent — à prévoir", "MARC Relators", "ouvert"),
    ("album", "contributeur_entite", "alias personne canonique", "descriptif", "absent — à prévoir (dormant)", "VIAF/IdRef", "ouvert"),
    ("album", "date_edition", "édition détenue (ancre)", "descriptif", "absent — à prévoir", "DC:issued", "ouvert"),
    ("album", "date_originale", "1re parution", "descriptif", "absent — à prévoir", "DC:created", "ouvert"),
    ("album", "type_oeuvre", "BD/roman graphique", "descriptif", "absent — à prévoir", "DC:type", "ouvert"),
    ("album", "langue", "langue de l'expression", "descriptif", "absent — à prévoir", "DC:language", "ouvert"),
    ("album", "lieu_edition", "ville d'édition", "descriptif", "absent — à prévoir", "DC:coverage", "ouvert"),
    ("album", "edition_tirage", "mention d'édition", "descriptif", "absent — à prévoir", "DC", "ouvert"),
    ("album", "identifiant_editeur", "ISBN/dépôt légal", "descriptif", "absent — à prévoir", "DC:identifier", "ouvert"),
    ("album", "format_physique", "dimensions/reliure", "matériel", "absent — à prévoir", "DC:format", "ouvert"),
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
    ("region", "activite_id", "run générateur", "paradonnée", "absent — à prévoir", "PROV wasGeneratedBy", "ouvert"),
    ("region", "touche+date_modification", "retouche humaine", "paradonnée", "absent — à prévoir", "PROV/TEI @resp", "ouvert"),
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
    ("vocabulaire", "collection_id", "portée d'appartenance", "humain", "absent — à prévoir", "SKOS", "ouvert"),
    ("vocabulaire", "definition", "sens dimension/valeur", "humain", "absent — à prévoir", "SKOS definition", "ouvert"),
    ("vocabulaire", "note_portee", "cadre d'emploi", "humain", "absent — à prévoir", "SKOS scopeNote", "ouvert"),
    ("vocabulaire", "etat_definitionnel", "provisoire→défini", "humain", "absent — à prévoir", "—", "ouvert"),
    ("vocabulaire", "pct_defini", "part du vocabulaire documenté", "dérivé", "absent — à prévoir", "—", "ouvert"),
    ("paradonnee", "nlp_model", "modèle NLP ayant indexé", "paradonnée", "structuré", "PROV", "ouvert"),
    ("paradonnee", "nlp_reindexed_count/_at", "ampleur+date de réindex", "paradonnée", "structuré", "PROV", "ouvert"),
    ("paradonnee", "schema_version", "version du schéma", "système", "structuré", "—", "ouvert"),
    ("paradonnee", "activite_run", "exécution de passe", "paradonnée", "absent — à prévoir", "PROV Activity", "ouvert"),
    ("paradonnee", "evenement_journal", "acte atomique append-only", "paradonnée", "absent — à prévoir", "PROV/TEI change", "ouvert"),
    ("paradonnee", "indicateurs_couverture", "% validé/touché/dérive", "dérivé", "absent — à prévoir", "—", "ouvert"),
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
    args = ap.parse_args(argv)

    with _connexion_ro() as conn:
        rollup, agg = collecter(conn)

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
