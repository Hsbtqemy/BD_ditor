"""Génère des manifests IIIF Presentation 3.0 à partir du corpus.

Une **Manifest** par album ; un **Canvas** par planche (aux dimensions MASTER,
`largeur_px`/`hauteur_px`) ; l'image (dérivé web) peinte dessus ; **une annotation
par région** ciblant `canvas#xywh=x,y,w,h` (les coordonnées master = le repère
IIIF, cf. docs/dictionnaire-metadonnees.md). Une **Collection** englobe les albums.

Ce n'est qu'une sérialisation des données existantes — aucune transformation de
coordonnées. Il reste à servir les images (serveur IIIF Image ou statiques) sous
`--base-url`. Lecture SEULE.

Le texte OCR (contenu `restreint`) n'est PAS inclus par défaut ; `--verbatim`
l'ajoute en annotation `supplementing` (transcription).

`--collection <id>` restreint aux albums d'une collection (la Collection IIIF prend alors
son nom) ; sinon, corpus entier. Gérer les collections : `tools/gerer_collections.py`.

Usage :
    python tools/iiif_manifest.py --base-url https://host/iiif           # manifest album 1 → stdout
    python tools/iiif_manifest.py --base-url https://host/iiif --out-dir iiif/
    python tools/iiif_manifest.py --base-url https://host/iiif --out-dir iiif/ --collection 3
La base suit la config du projet (BD_DB_PATH / BD_DATA_DIR).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH, WEB_SCALE  # noqa: E402
import metadonnees_collection as mc  # noqa: E402  (réutilise l'arbre déjà construit)

CTX = "http://iiif.io/api/presentation/3/context.json"


def _lang(txt):
    return {"fr": [txt if txt is not None else "—"]}


def _meta(label, valeur):
    return {"label": _lang(label), "value": _lang(str(valeur))}


def _album_metadata(a):
    # Contributions (N0) d'abord : une entrée « Rôle : Nom » par contributeur.
    meta = [_meta((ct.get("role") or "contributeur").capitalize(), ct["nom"])
            for ct in a.get("contributions", [])]
    champs = [("Auteur", a.get("auteur")), ("Année", a.get("annee")),
              ("Éditeur", a.get("editeur")), ("Série", a.get("serie")),
              ("Date d'édition", a.get("date_edition")),
              ("Première parution", a.get("date_originale")),
              ("Langue", a.get("langue")), ("Type", a.get("type_oeuvre")),
              ("Lieu d'édition", a.get("lieu_edition")),
              ("Édition / tirage", a.get("edition_tirage")),
              ("ISBN", a.get("isbn")), ("Format", a.get("format_physique"))]
    return meta + [_meta(lbl, v) for lbl, v in champs if v not in (None, "")]


def _region_anno(reg, cid, base, aid, verbatim):
    rid = reg["id"]
    bodies = [{"type": "TextualBody", "language": "fr", "format": "text/html",
               "value": f"<b>{reg['type']}</b>"
                        + (f" — {reg['citation']}" if reg.get("citation") else "")}]
    if reg.get("locuteur"):
        bodies.append({"type": "TextualBody", "purpose": "identifying", "language": "fr",
                       "value": f"locuteur : {reg['locuteur']}"})
    if reg.get("presence"):
        bodies.append({"type": "TextualBody", "purpose": "identifying", "language": "fr",
                       "value": f"présence : {reg['presence']}"})
    ann = reg.get("annotation") or {}
    for tag in ann.get("tags", []):
        bodies.append({"type": "TextualBody", "purpose": "tagging", "value": tag})
    if ann.get("note"):
        bodies.append({"type": "TextualBody", "purpose": "commenting", "language": "fr",
                       "format": "text/plain", "value": ann["note"]})
    if verbatim and reg["ocr"].get("texte"):
        bodies.append({"type": "TextualBody", "purpose": "transcribing", "language": "fr",
                       "format": "text/plain", "value": reg["ocr"]["texte"]})
    return {
        "id": f"{base}/album/{aid}/annotation/region-{rid}",
        "type": "Annotation",
        "motivation": "commenting",
        "body": bodies if len(bodies) > 1 else bodies[0],
        "target": f"{cid}#xywh={reg['x']},{reg['y']},{reg['w']},{reg['h']}",
    }


def _canvas(p, aid, base, verbatim):
    W, H = p["largeur_px"], p["hauteur_px"]
    if not (isinstance(W, int) and W > 0 and isinstance(H, int) and H > 0):
        return None            # sans dimensions master, pas de Canvas IIIF valide → planche omise
    cid = f"{base}/album/{aid}/canvas/p{p['id']}"
    ed = p["numero_editorial"]
    label = f"Planche {p['numero']}" + (f" (pl.{ed})" if ed else " (paratexte)")

    painting = {
        "id": f"{cid}/painting", "type": "AnnotationPage",
        "items": [{
            "id": f"{cid}/painting/image", "type": "Annotation", "motivation": "painting",
            "body": {"id": f"{base}/{p['chemin_web']}", "type": "Image", "format": "image/jpeg",
                     "height": round((H or 0) * WEB_SCALE), "width": round((W or 0) * WEB_SCALE)},
            "target": cid,
        }],
    }
    canvas = {"id": cid, "type": "Canvas", "label": _lang(label),
              "height": H, "width": W, "items": [painting]}

    annos = []
    def walk(reg):
        if all(reg.get(k) is not None for k in ("x", "y", "w", "h")):
            annos.append(_region_anno(reg, cid, base, aid, verbatim))   # sinon xywh invalide
        for e in reg.get("enfants", []):
            walk(e)
    for reg in p["regions"]:
        walk(reg)
    if annos:
        canvas["annotations"] = [{"id": f"{cid}/annotations", "type": "AnnotationPage",
                                  "items": annos}]
    return canvas


def manifeste_album(a, base, verbatim):
    return {
        "@context": CTX,
        "id": f"{base}/album/{a['id']}/manifest.json",
        "type": "Manifest",
        "label": _lang(a["titre"]),
        "metadata": _album_metadata(a),
        "items": [c for c in (_canvas(p, a["id"], base, verbatim)
                              for p in a["planches"]) if c is not None],
    }


def collection(albums, base, nom=None):
    return {
        "@context": CTX,
        "id": f"{base}/collection.json",
        "type": "Collection",
        "label": _lang(nom or "Corpus entier"),
        "items": [{"id": f"{base}/album/{a['id']}/manifest.json", "type": "Manifest",
                   "label": _lang(a["titre"])} for a in albums],
    }


def _connexion_ro():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def main(argv=None) -> int:
    from _commun import forcer_utf8
    forcer_utf8()                             # Windows : stdout/stderr en UTF-8 (cp1252 sinon)
    ap = argparse.ArgumentParser(description="Génère des manifests IIIF Presentation 3.0.")
    ap.add_argument("--base-url", default="https://exemple.org/iiif",
                    help="préfixe d'URI des identifiants et des images (défaut : placeholder)")
    ap.add_argument("--out-dir", metavar="DOSSIER",
                    help="écrit collection.json + un manifest par album ; sinon stdout (album 1)")
    ap.add_argument("--verbatim", action="store_true",
                    help="inclut l'OCR en annotation supplementing (contenu restreint)")
    ap.add_argument("--collection", type=int, metavar="ID",
                    help="restreint aux albums d'une collection (défaut : corpus entier)")
    args = ap.parse_args(argv)
    base = args.base_url.rstrip("/")

    with _connexion_ro() as conn:
        arbre = mc.collecter(conn, verbatim=args.verbatim, collection_id=args.collection)
    albums = arbre["metadonnees_collection"]["albums"]
    bloc = arbre["metadonnees_collection"].get("collection")   # None = corpus entier
    nom_collection = bloc["nom"] if bloc else None

    if not args.out_dir:
        if not albums:
            print("{}")
            return 0
        print(json.dumps(manifeste_album(albums[0], base, args.verbatim),
                         ensure_ascii=False, indent=2))
        return 0

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "collection.json"), "w", encoding="utf-8") as f:
        json.dump(collection(albums, base, nom_collection), f, ensure_ascii=False, indent=2)
    for a in albums:
        man = manifeste_album(a, base, args.verbatim)
        with open(os.path.join(args.out_dir, f"manifest-a{a['id']}.json"),
                  "w", encoding="utf-8") as f:
            json.dump(man, f, ensure_ascii=False, indent=2)
        print(f"  manifest-a{a['id']}.json : {len(man['items'])} canvas", file=sys.stderr)
    print(f"Manifests IIIF écrits : {args.out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
