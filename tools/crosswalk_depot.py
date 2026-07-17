"""Crosswalk de dépôt — sérialise une collection vers Dublin Core & DataCite.

Additif, EN LECTURE SEULE, hors-app (comme les autres `tools/`). Produit, pour un
périmètre (défaut : corpus entier ; `--collection <id>` pour scoper), des notices dans
les schémas d'entrepôt :

  • Dublin Core (dcterms + relators MARC), en JSON-LD → fiche descriptive Nakala ;
  • DataCite 4.x (JSON + XML) → demande de DOI (réutilisé par Nakala/HAL).

Cadrage éditorial, paternité « à la Zotero » (cf. docs/crosswalk-depot.md) :
  • `creators`  = contributions à `bucket = creator` (scénariste, dessinateur…) ;
  • `contributors` = contributions à `bucket = contributor` (coloriste, lettreur…) + les
    ANNOTATEURS (`collection.responsables`) en `contributorType = DataCurator` ;
  • le rôle fin est gardé en DC via les relators MARC (`contribution_role.marc`) ; DataCite
    ne connaît pas « coloriste » → il retombe en `Other`.

Deux granularités : une notice PAR album (auteurs de CET album) + une notice de COLLECTION
(union dédupliquée + annotateurs ; `resourceTypeGeneral = Collection`, `HasPart` vers les
albums). Le DOI est HORS PÉRIMÈTRE : c'est l'entrepôt qui le frappe.

Usage :
    python tools/crosswalk_depot.py                          # JSON (DC + DataCite) sur stdout
    python tools/crosswalk_depot.py --collection 3 --out-dir depot/
    python tools/crosswalk_depot.py --publisher "Huma-Num (Nakala)" --annee-depot 2026
La base suit la config du projet (BD_DB_PATH / BD_DATA_DIR).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402  (collection_row / collection_album_ids / contributions_album)
from config import DB_PATH, BASE_DIR  # noqa: E402
from _commun import version_outil  # noqa: E402  (provenance de l'outil — paradonnée)


# --------------------------------------------------------------------------- #
# Vocabulaires de correspondance
# --------------------------------------------------------------------------- #
# Licences → URI (SPDX / Creative Commons). Inconnue → pas d'URI (mention seule, valide).
_LICENCE_URI = {
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-SA-4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC-BY-NC-4.0": "https://creativecommons.org/licenses/by-nc/4.0/",
    "CC-BY-ND-4.0": "https://creativecommons.org/licenses/by-nd/4.0/",
    "CC-BY-NC-SA-4.0": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "CC-BY-NC-ND-4.0": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
}

# Rôle d'un responsable (annotateur) → `contributorType` DataCite (liste contrôlée courte).
# Défaut : DataCurator (celui/celle qui annote/curate la donnée).
_CONTRIB_TYPE = {
    "annotateur": "DataCurator", "annotatrice": "DataCurator", "curateur": "DataCurator",
    "chercheur": "Researcher", "chercheuse": "Researcher", "researcher": "Researcher",
    "responsable": "ProjectLeader", "editeur": "Editor", "éditeur": "Editor",
    "superviseur": "Supervisor",
}

_NS = "http://datacite.org/schema/kernel-4"
_XSI = "http://www.w3.org/2001/XMLSchema-instance"


def _licence_uri(licence):
    if not licence:
        return None
    l = licence.strip()
    return _LICENCE_URI.get(l) or _LICENCE_URI.get(l.upper())


def _type_annotateur(role):
    return _CONTRIB_TYPE.get((role or "").strip().lower(), "DataCurator")


def _responsables(row) -> list:
    """`collection.responsables` (JSON) → liste de dicts (vide si absent/illisible)."""
    if not row or not row["responsables"]:
        return []
    try:
        val = json.loads(row["responsables"])
        return val if isinstance(val, list) else []
    except (ValueError, TypeError):
        return []


# --------------------------------------------------------------------------- #
# Contributions → créateurs / contributeurs (le cœur du crosswalk)
# --------------------------------------------------------------------------- #
def _split_contributions(contribs) -> tuple[list, list]:
    """Répartit les contributions d'un album selon `bucket` : `creator` → créateurs,
    `contributor` → contributeurs (type DataCite `Other`). Un rôle ABSENT (role NULL)
    est traité comme créateur (auteur par défaut, à la Zotero)."""
    creators, contributors = [], []
    for c in contribs:
        person = {"nom": c["nom"], "orcid": None, "role": c["role"], "marc": c["marc"]}
        if c["bucket"] == "contributor":
            person["type"] = "Other"
            contributors.append(person)
        else:
            creators.append(person)
    return creators, contributors


def _annotateurs(resp_list) -> list:
    """Responsables (créateurs de la notice) → contributeurs `DataCurator`."""
    out = []
    for r in resp_list:
        nom = (r.get("nom") or "").strip()
        if not nom:
            continue
        out.append({"nom": nom, "orcid": (r.get("orcid") or None),
                    "role": r.get("role"), "marc": None,
                    "type": _type_annotateur(r.get("role"))})
    return out


def _union(persons) -> list:
    """Dé-doublonne une liste de personnes par nom (préserve l'ordre d'apparition)."""
    seen, out = set(), []
    for p in persons:
        if p["nom"] not in seen:
            seen.add(p["nom"])
            out.append(p)
    return out


# --------------------------------------------------------------------------- #
# Sérialiseurs : modèle neutre → Dublin Core (JSON-LD) et DataCite (JSON)
# --------------------------------------------------------------------------- #
def _to_dublin_core(rec: dict) -> dict:
    """Modèle neutre → Dublin Core en JSON-LD (dcterms + relators MARC pour les rôles fins)."""
    dc = {
        "@context": {
            "dc": "http://purl.org/dc/elements/1.1/",
            "dcterms": "http://purl.org/dc/terms/",
            "marcrel": "http://id.loc.gov/vocabulary/relators/",
        },
        "@type": rec["type"],
        "dcterms:title": rec["titre"],
    }
    creators = [p["nom"] for p in rec["creators"]]
    contributors = [p["nom"] for p in rec["contributors"]]
    if creators:
        dc["dc:creator"] = creators
    if contributors:
        dc["dc:contributor"] = contributors
    by_marc = {}                                        # rôle fin conservé via relators LoC
    for p in rec["creators"] + rec["contributors"]:
        if p.get("marc"):
            by_marc.setdefault(p["marc"], []).append(p["nom"])
    for code, noms in sorted(by_marc.items()):
        dc[f"marcrel:{code}"] = noms
    if rec.get("issued"):
        dc["dcterms:issued"] = rec["issued"]
    if rec.get("created"):
        dc["dcterms:created"] = rec["created"]
    if rec.get("collected"):
        dc["dcterms:temporal"] = rec["collected"]
    if rec.get("editeur_bd"):
        dc["dc:publisher"] = rec["editeur_bd"]          # éditeur BD (bibliographique, niveau album)
    if rec.get("langue"):
        dc["dc:language"] = rec["langue"]
    if rec.get("resource_type"):
        dc["dc:type"] = rec["resource_type"]
    if rec.get("isbn"):
        dc["dc:identifier"] = rec["isbn"]
    if rec.get("licence"):
        dc["dcterms:license"] = rec.get("licence_uri") or rec["licence"]
    if rec.get("base_legale"):
        dc["dc:rights"] = rec["base_legale"]
    if rec.get("access_rights"):
        dc["dcterms:accessRights"] = rec["access_rights"]
    if rec.get("subjects"):
        dc["dc:subject"] = rec["subjects"]
    if rec.get("description"):
        dc["dc:description"] = rec["description"]
    return dc


def _person_datacite(p: dict) -> dict:
    o = {"name": p["nom"], "nameType": "Personal"}
    if p.get("orcid"):
        o["nameIdentifiers"] = [{"nameIdentifier": p["orcid"],
                                 "nameIdentifierScheme": "ORCID",
                                 "schemeUri": "https://orcid.org"}]
    return o


def _to_datacite(rec: dict) -> dict:
    """Modèle neutre → DataCite 4.x (représentation JSON). `publisher`/`publicationYear`
    sont ceux du DÉPÔT (l'entrepôt), pas de l'œuvre. Pas de `identifier`/DOI (l'entrepôt)."""
    d = {
        "types": {"resourceTypeGeneral": rec["type"],
                  "resourceType": rec.get("resource_type") or rec["type"]},
        "titles": [{"title": rec["titre"]}],
        "creators": [_person_datacite(p) for p in rec["creators"]],
        "publisher": rec["publisher"],
        "publicationYear": rec["publication_year"],
    }
    contribs = []
    for p in rec["contributors"]:
        c = _person_datacite(p)
        c["contributorType"] = p.get("type") or "Other"
        contribs.append(c)
    if contribs:
        d["contributors"] = contribs
    dates = []
    for val, typ in ((rec.get("issued"), "Issued"), (rec.get("created"), "Created"),
                     (rec.get("collected"), "Collected"), (rec.get("available"), "Available")):
        if val:
            dates.append({"date": val, "dateType": typ})
    if dates:
        d["dates"] = dates
    if rec.get("langue"):
        d["language"] = rec["langue"]
    related = list(rec.get("related", []))
    if rec.get("isbn"):
        related.insert(0, {"relatedIdentifier": rec["isbn"],
                           "relatedIdentifierType": "ISBN", "relationType": "IsPartOf"})
    if related:
        d["relatedIdentifiers"] = related
    rights = []
    if rec.get("licence"):
        r = {"rights": rec["licence"]}
        if rec.get("licence_uri"):
            r["rightsUri"] = rec["licence_uri"]
        rights.append(r)
    if rec.get("access_rights"):
        rights.append({"rights": rec["access_rights"]})
    if rec.get("base_legale"):
        rights.append({"rights": rec["base_legale"]})
    if rights:
        d["rightsList"] = rights
    if rec.get("subjects"):
        d["subjects"] = [{"subject": s} for s in rec["subjects"]]
    descrs = []
    if rec.get("description"):
        descrs.append({"description": rec["description"], "descriptionType": "Abstract"})
    if rec.get("editeur_bd"):                            # source décrite (pas le publisher du dépôt)
        src = f"Source publiée par {rec['editeur_bd']}"
        if rec.get("lieu_edition"):
            src += f" ({rec['lieu_edition']})"
        descrs.append({"description": src, "descriptionType": "Other"})
    if descrs:
        d["descriptions"] = descrs
    return d


def champs_manquants(datacite: dict) -> list:
    """Champs OBLIGATOIRES DataCite absents (le DOI est exclu — attribué par l'entrepôt)."""
    manque = []
    if not datacite.get("creators"):
        manque.append("creators")
    if not (datacite.get("titles") and datacite["titles"][0].get("title")):
        manque.append("titles")
    if not datacite.get("publisher"):
        manque.append("publisher")
    if not datacite.get("publicationYear"):
        manque.append("publicationYear")
    if not datacite.get("types", {}).get("resourceTypeGeneral"):
        manque.append("resourceType")
    return manque


# --------------------------------------------------------------------------- #
# DataCite : représentation JSON → XML (schema kernel-4)
# --------------------------------------------------------------------------- #
def _safe(text):
    """Retire les caractères interdits par XML 1.0 (garde tab/LF/CR)."""
    if text is None:
        return None
    return "".join(c for c in str(text)
                   if ord(c) in (0x09, 0x0A, 0x0D)
                   or 0x20 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD
                   or ord(c) >= 0x10000)


def _q(tag):
    return f"{{{_NS}}}{tag}"


def _sub(parent, tag, text=None, **attrs):
    el = ET.SubElement(parent, _q(tag))
    for k, v in attrs.items():
        if v is not None:
            el.set(k, _safe(v))
    if text is not None:
        el.text = _safe(text)
    return el


def datacite_xml(d: dict) -> str:
    """Représentation DataCite JSON → XML conforme au namespace kernel-4. L'`identifier`
    (DOI) est laissé à l'entrepôt : on le signale par un commentaire, on ne le forge pas."""
    ET.register_namespace("", _NS)
    ET.register_namespace("xsi", _XSI)
    root = ET.Element(_q("resource"))
    root.set(f"{{{_XSI}}}schemaLocation",
             f"{_NS} http://schema.datacite.org/meta/kernel-4/metadata.xsd")
    root.append(ET.Comment(" identifier (DOI) attribué par l'entrepôt au moment du dépôt "))

    cs = _sub(root, "creators")
    for p in d.get("creators", []):
        c = _sub(cs, "creator")
        _sub(c, "creatorName", p["name"], nameType=p.get("nameType"))
        for ni in p.get("nameIdentifiers", []):
            _sub(c, "nameIdentifier", ni["nameIdentifier"],
                 nameIdentifierScheme=ni.get("nameIdentifierScheme"),
                 schemeURI=ni.get("schemeUri"))
    ts = _sub(root, "titles")
    for t in d.get("titles", []):
        _sub(ts, "title", t["title"])
    _sub(root, "publisher", d.get("publisher"))
    _sub(root, "publicationYear", d.get("publicationYear"))
    rt = d.get("types", {})
    _sub(root, "resourceType", rt.get("resourceType"),
         resourceTypeGeneral=rt.get("resourceTypeGeneral"))
    if d.get("subjects"):
        ss = _sub(root, "subjects")
        for s in d["subjects"]:
            _sub(ss, "subject", s["subject"])
    if d.get("contributors"):
        cbs = _sub(root, "contributors")
        for p in d["contributors"]:
            cb = _sub(cbs, "contributor", contributorType=p.get("contributorType"))
            _sub(cb, "contributorName", p["name"], nameType=p.get("nameType"))
            for ni in p.get("nameIdentifiers", []):
                _sub(cb, "nameIdentifier", ni["nameIdentifier"],
                     nameIdentifierScheme=ni.get("nameIdentifierScheme"),
                     schemeURI=ni.get("schemeUri"))
    if d.get("dates"):
        ds = _sub(root, "dates")
        for dt in d["dates"]:
            _sub(ds, "date", dt["date"], dateType=dt.get("dateType"))
    if d.get("language"):
        _sub(root, "language", d["language"])
    if d.get("relatedIdentifiers"):
        ris = _sub(root, "relatedIdentifiers")
        for ri in d["relatedIdentifiers"]:
            _sub(ris, "relatedIdentifier", ri["relatedIdentifier"],
                 relatedIdentifierType=ri.get("relatedIdentifierType"),
                 relationType=ri.get("relationType"))
    if d.get("rightsList"):
        rs = _sub(root, "rightsList")
        for r in d["rightsList"]:
            _sub(rs, "rights", r.get("rights"), rightsURI=r.get("rightsUri"))
    if d.get("descriptions"):
        des = _sub(root, "descriptions")
        for de in d["descriptions"]:
            _sub(des, "description", de["description"],
                 descriptionType=de.get("descriptionType"))
    xml = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml


# --------------------------------------------------------------------------- #
# Construction : lecture de la base → notices album + collection
# --------------------------------------------------------------------------- #
def _sujets(conn) -> list:
    """Sujets = valeurs canoniques du vocabulaire facetté + étiquettes (tags). Catalogues
    globaux (canoniques au corpus) — cf. `docs/export-metadonnees.md` (portée)."""
    vals = [r[0] for r in conn.execute(
        "SELECT DISTINCT valeur FROM attribut_valeur ORDER BY valeur")]
    tags = [r[0] for r in conn.execute("SELECT label FROM tags ORDER BY label")]
    vus, out = set(), []
    for s in vals + tags:
        if s and s not in vus:
            vus.add(s)
            out.append(s)
    return out


def _plage(debut, fin):
    if not (debut or fin):
        return None
    return f"{debut or ''}/{fin or ''}".strip("/")


def _serialiser(rec: dict) -> dict:
    dcite = _to_datacite(rec)
    return {"dublin_core": _to_dublin_core(rec), "datacite": dcite,
            "datacite_xml": datacite_xml(dcite),
            "champs_obligatoires_manquants": champs_manquants(dcite)}


def construire(conn, collection_id=None, publisher="BéDéditeur", annee_depot=None) -> dict:
    """Construit le crosswalk complet (notices album + notice collection) pour un périmètre."""
    annee_depot = str(annee_depot or datetime.now().year)
    row = database.collection_row(conn, collection_id) if collection_id is not None else None
    if collection_id is not None and row is None:
        raise SystemExit(f"Collection {collection_id} introuvable.")
    licence = row["licence_defaut"] if row else None
    licence_uri = _licence_uri(licence)

    if collection_id is not None:
        album_ids = database.collection_album_ids(conn, collection_id)
    else:
        album_ids = [r[0] for r in conn.execute("SELECT id FROM albums ORDER BY id")]

    albums_out, tous_creators, tous_contributors, isbns = [], [], [], []
    for aid in album_ids:
        a = conn.execute(
            "SELECT id, titre, editeur, date_edition, date_originale, langue, "
            "type_oeuvre, lieu_edition, isbn FROM albums WHERE id = ?", (aid,)).fetchone()
        if a is None:
            continue
        creators, contributors = _split_contributions(database.contributions_album(conn, aid))
        tous_creators += creators
        tous_contributors += contributors
        if a["isbn"]:
            isbns.append(a["isbn"])
        rec = {
            "type": "Text", "resource_type": a["type_oeuvre"] or "bande dessinée",
            "titre": a["titre"], "creators": creators, "contributors": contributors,
            "issued": a["date_edition"], "created": a["date_originale"],
            "editeur_bd": a["editeur"], "lieu_edition": a["lieu_edition"],
            "langue": a["langue"], "isbn": a["isbn"],
            "licence": licence, "licence_uri": licence_uri,
            "publisher": publisher, "publication_year": annee_depot,
        }
        albums_out.append({"id": a["id"], "titre": a["titre"], **_serialiser(rec)})

    collection_out = None
    if row is not None:
        annot = _annotateurs(_responsables(row))
        # On relie la collection à ses albums par ISBN quand il existe (HasPart).
        related = [{"relatedIdentifier": isbn, "relatedIdentifierType": "ISBN",
                    "relationType": "HasPart"} for isbn in isbns]
        rec = {
            "type": "Collection", "resource_type": "corpus de bande dessinée annoté",
            "titre": row["nom"], "description": row["description"],
            "creators": _union(tous_creators),
            "contributors": _union(tous_contributors) + annot,
            "collected": _plage(row["date_debut"], row["date_fin"]),
            "available": row["date_embargo"],
            "langue": None, "isbn": None, "editeur_bd": None,
            "licence": licence, "licence_uri": licence_uri,
            "base_legale": row["base_legale"],
            "access_rights": row["statut_diffusion"],
            "subjects": _sujets(conn), "related": related,
            "publisher": publisher, "publication_year": annee_depot,
        }
        collection_out = _serialiser(rec)

    return {"crosswalk_depot": {
        "genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "outil": version_outil(BASE_DIR),
        "cadre": "dépôt éditorial · paternité Zotero · DOI attribué par l'entrepôt",
        "perimetre": {"collection_id": collection_id,
                      "portee": row["nom"] if row else "corpus entier",
                      "albums": len(album_ids)},
        "publisher": publisher, "annee_depot": annee_depot,
        "collection": collection_out, "albums": albums_out,
    }}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _connexion_ro():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _ecrire_fichiers(doc: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)

    def _paire(prefixe, bloc):
        with open(os.path.join(out_dir, f"{prefixe}_dublin_core.jsonld"), "w",
                  encoding="utf-8") as f:
            json.dump(bloc["dublin_core"], f, ensure_ascii=False, indent=2)
        with open(os.path.join(out_dir, f"{prefixe}_datacite.json"), "w",
                  encoding="utf-8") as f:
            json.dump(bloc["datacite"], f, ensure_ascii=False, indent=2)
        with open(os.path.join(out_dir, f"{prefixe}_datacite.xml"), "w",
                  encoding="utf-8") as f:
            f.write(bloc["datacite_xml"] + "\n")

    cw = doc["crosswalk_depot"]
    if cw["collection"]:
        _paire("collection", cw["collection"])
    for a in cw["albums"]:
        _paire(f"album_{a['id']}", a)
    n = len(cw["albums"]) + (1 if cw["collection"] else 0)
    print(f"{n} notices écrites dans {out_dir}/ (Dublin Core + DataCite JSON/XML)",
          file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Crosswalk d'une collection vers Dublin Core & DataCite (dépôt).")
    ap.add_argument("--collection", type=int, metavar="ID",
                    help="restreint le périmètre à cette collection (défaut : corpus entier)")
    ap.add_argument("--publisher", default="BéDéditeur", metavar="NOM",
                    help="'publisher' DataCite = l'entrepôt / l'institution (pas l'éditeur BD)")
    ap.add_argument("--annee-depot", type=int, metavar="AAAA",
                    help="'publicationYear' DataCite = année de mise à disposition (défaut : courante)")
    ap.add_argument("--out-dir", metavar="DIR",
                    help="écrit les notices en fichiers (défaut : JSON complet sur stdout)")
    args = ap.parse_args(argv)

    try:                      # stdout en UTF-8 même en sous-processus Windows (console cp1252)
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    with _connexion_ro() as conn:
        doc = construire(conn, collection_id=args.collection,
                         publisher=args.publisher, annee_depot=args.annee_depot)

    if args.out_dir:
        _ecrire_fichiers(doc, args.out_dir)
    else:
        print(json.dumps(doc, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
