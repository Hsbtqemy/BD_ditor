"""Validateur structurel IIIF Presentation 3.0 (hors ligne).

Le validateur OFFICIEL (validator.iiif.io) va CHERCHER le document à une URL
publique — inutilisable sur des fichiers locaux à URLs placeholder. Ce script
vérifie donc la conformité *structurelle* au spec Presentation 3.0, plus des
contrôles SÉMANTIQUES qu'un simple JSON-Schema ne fait pas :

  • ids présents et de forme URI, uniques dans le document ;
  • Manifest → items = Canvas ; Canvas → height/width + AnnotationPage `painting` ;
  • Annotation → motivation / body / target ; cible `#xywh` = 4 entiers ;
  • la cible pointe un Canvas EXISTANT et la boîte tient DANS ses dimensions.

En complément, si **iiif-prezi3** (bibliothèque IIIF officielle) est installé, une passe
de conformité STRICTE re-parse chaque document dans ses modèles typés — validation
INDÉPENDANTE de ce script, exécutée automatiquement quand la lib est présente (sinon
ignorée : la validation structurelle reste la seule). `pip install -r requirements-export.txt`.

Sortie : erreurs (violation) + avertissements (recommandation SHOULD non tenue).
Code de sortie 1 s'il y a au moins une erreur.

Usage :
    python tools/valider_iiif.py docs/exemples/iiif           # un dossier (collection + manifests)
    python tools/valider_iiif.py chemin/manifest.json ...     # un ou des fichiers
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

CTX3 = "http://iiif.io/api/presentation/3/context.json"
XYWH = re.compile(r"^xywh=(\d+),(\d+),(\d+),(\d+)$")
URI = re.compile(r"^https?://", re.I)
PURPOSES = {"identifying", "tagging", "commenting", "describing", "transcribing",
            "supplementing", "classifying", "highlighting", "bookmarking",
            "linking", "moderating", "questioning", "replying", "assessing", "editing"}


class Rapport:
    def __init__(self, nom):
        self.nom = nom
        self.err: list[str] = []
        self.warn: list[str] = []

    def e(self, msg):
        self.err.append(msg)

    def w(self, msg):
        self.warn.append(msg)


def _uri(s):
    return isinstance(s, str) and bool(URI.match(s))


def _langmap(v):
    return isinstance(v, dict) and bool(v) and all(
        isinstance(k, str) and isinstance(vv, list)
        and all(isinstance(x, str) for x in vv) for k, vv in v.items())


def _uniq(ident, ids, rap):
    if ident in ids:
        rap.e(f"id dupliqué : {ident}")
    ids.add(ident)


def _top(doc, typ, rap, ids):
    ctx = doc.get("@context")
    if not (ctx == CTX3 or (isinstance(ctx, list) and CTX3 in ctx)):
        rap.e(f"{typ}: @context Presentation 3 manquant")
    if doc.get("type") != typ:
        rap.e(f"type attendu '{typ}', trouvé {doc.get('type')!r}")
    if not _uri(doc.get("id")):
        rap.e(f"{typ}.id absent ou non-URI : {doc.get('id')!r}")
    else:
        _uniq(doc["id"], ids, rap)
    if not _langmap(doc.get("label")):
        rap.e(f"{typ}.label absent ou pas une language map")


def _metadata(md, rap):
    if md is None:
        return
    if not isinstance(md, list):
        rap.e("metadata doit être une liste"); return
    for i, entry in enumerate(md):
        if not (_langmap(entry.get("label")) and _langmap(entry.get("value"))):
            rap.e(f"metadata[{i}] : label/value doivent être des language maps")


def _annotation(a, rap, ids, canvas_ids, dims, peinture=False):
    if a.get("type") != "Annotation":
        rap.e(f"Annotation.type attendu 'Annotation', trouvé {a.get('type')!r}")
    if not _uri(a.get("id")):
        rap.e(f"Annotation.id absent ou non-URI : {a.get('id')!r}")
    else:
        _uniq(a["id"], ids, rap)
    if "motivation" not in a:
        rap.w(f"Annotation {a.get('id')} sans motivation (SHOULD)")
    if "body" not in a and not peinture:
        rap.w(f"Annotation {a.get('id')} sans body")
    if peinture and a.get("motivation") != "painting":
        rap.e(f"Annotation de peinture : motivation attendue 'painting', "
              f"trouvée {a.get('motivation')!r}")

    target = a.get("target")
    if not isinstance(target, str):
        rap.e(f"Annotation {a.get('id')} : target attendu (chaîne canvas#xywh)"); return
    base, _, frag = target.partition("#")
    if base not in canvas_ids:
        rap.e(f"cible ne pointe aucun Canvas connu : {target}")
    if frag:
        m = XYWH.match(frag)
        if not m:
            rap.e(f"fragment de cible mal formé (attendu xywh=x,y,w,h) : {frag}")
        elif base in dims:
            x, y, w, h = (int(g) for g in m.groups())
            W, H = dims[base]
            if W and H and (x + w > W or y + h > H):
                rap.w(f"boîte hors des dimensions du Canvas ({x+w}×{y+h} > {W}×{H}) : {target}")

    # corps textuels
    bodies = a.get("body")
    for b in (bodies if isinstance(bodies, list) else [bodies] if bodies else []):
        if isinstance(b, dict) and b.get("type") == "TextualBody":
            if "value" not in b:
                rap.e(f"TextualBody sans 'value' (annotation {a.get('id')})")
            pur = b.get("purpose")
            if pur is not None and pur not in PURPOSES:
                rap.w(f"purpose inhabituel : {pur!r}")


def _canvas(c, rap, ids, canvas_ids, dims):
    if c.get("type") != "Canvas":
        rap.e(f"Canvas.type attendu 'Canvas', trouvé {c.get('type')!r}"); return
    cid = c.get("id")
    if not _uri(cid):
        rap.e(f"Canvas.id absent ou non-URI : {cid!r}"); return
    _uniq(cid, ids, rap)
    canvas_ids.add(cid)
    W, H = c.get("width"), c.get("height")
    if not (isinstance(W, int) and W > 0 and isinstance(H, int) and H > 0):
        rap.e(f"Canvas {cid} : width/height entiers positifs requis (trouvé {W}×{H})")
    else:
        dims[cid] = (W, H)
    if not _langmap(c.get("label")):
        rap.w(f"Canvas {cid} sans label (SHOULD)")

    items = c.get("items")
    if not isinstance(items, list) or not items:
        rap.e(f"Canvas {cid}.items absent ou vide (AnnotationPage de peinture attendue)")
    else:
        for page in items:
            if page.get("type") != "AnnotationPage":
                rap.e(f"Canvas {cid}.items : AnnotationPage attendue, {page.get('type')!r}")
                continue
            if not _uri(page.get("id")):
                rap.e(f"AnnotationPage.id absent ou non-URI dans Canvas {cid}")
            for anno in page.get("items", []):
                _annotation(anno, rap, ids, canvas_ids, dims, peinture=True)

    for page in c.get("annotations", []) or []:
        if page.get("type") != "AnnotationPage":
            rap.e(f"Canvas {cid}.annotations : AnnotationPage attendue")
            continue
        for anno in page.get("items", []):
            _annotation(anno, rap, ids, canvas_ids, dims)


def valider_manifest(doc) -> Rapport:
    rap = Rapport(doc.get("id", "manifest"))
    ids: set = set()
    _top(doc, "Manifest", rap, ids)
    _metadata(doc.get("metadata"), rap)
    items = doc.get("items")
    if not isinstance(items, list) or not items:
        rap.e("Manifest.items absent ou vide (liste de Canvas attendue)")
        return rap
    canvas_ids: set = set()
    dims: dict = {}
    for c in items:                       # 1re passe : dimensions des canvas
        if isinstance(c, dict) and _uri(c.get("id")) and c.get("type") == "Canvas":
            W, H = c.get("width"), c.get("height")
            if isinstance(W, int) and isinstance(H, int):
                dims[c["id"]] = (W, H)
            canvas_ids.add(c["id"])
    for c in items:                       # 2e passe : validation complète
        _canvas(c, rap, ids, canvas_ids, dims)
    return rap


def valider_collection(doc, manifests_connus) -> Rapport:
    rap = Rapport(doc.get("id", "collection"))
    ids: set = set()
    _top(doc, "Collection", rap, ids)
    items = doc.get("items")
    if not isinstance(items, list) or not items:
        rap.e("Collection.items absent ou vide (liste de Manifest attendue)")
        return rap
    for m in items:
        if m.get("type") != "Manifest":
            rap.e(f"Collection.items : Manifest attendu, {m.get('type')!r}")
        if not _uri(m.get("id")):
            rap.e(f"référence de Manifest non-URI : {m.get('id')!r}")
        elif manifests_connus and m["id"] not in manifests_connus:
            rap.w(f"Manifest référencé mais absent du lot : {m['id']}")
        if not _langmap(m.get("label")):
            rap.w(f"référence de Manifest sans label : {m.get('id')}")
    return rap


def _charger(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def _strict(doc, rap) -> bool:
    """Passe de conformité STRICTE via iiif-prezi3 (lib IIIF officielle) : re-parse le
    document dans les modèles typés. Renvoie True si la passe a pu s'exécuter (lib
    présente), False sinon (import protégé → dégradation propre). Tout écart de
    conformité est ajouté au rapport, préfixé « strict: »."""
    try:
        from iiif_prezi3 import Collection, Manifest
    except ImportError:
        return False
    cls = {"Manifest": Manifest, "Collection": Collection}.get(doc.get("type"))
    if cls is None:                       # type racine déjà signalé par la passe structurelle
        return True
    try:
        cls.model_validate(doc)
    except Exception as exc:              # pydantic ValidationError (ou autre)
        details = getattr(exc, "errors", None)
        if callable(details):
            for e in exc.errors()[:8]:
                loc = ".".join(str(x) for x in e.get("loc", ())) or "(racine)"
                rap.e(f"strict: {loc} — {e.get('msg', '')}")
        else:
            rap.e(f"strict: {str(exc).splitlines()[0]}")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Validateur IIIF Presentation 3.0 : structurel (toujours) + strict "
                    "iiif-prezi3 (auto si installé).")
    ap.add_argument("chemins", nargs="+", help="fichiers .json ou un dossier")
    args = ap.parse_args(argv)

    fichiers = []
    for ch in args.chemins:
        if os.path.isdir(ch):
            fichiers += sorted(os.path.join(ch, f) for f in os.listdir(ch)
                               if f.endswith(".json"))
        else:
            fichiers.append(ch)

    docs = {ch: _charger(ch) for ch in fichiers}
    manifest_ids = {d.get("id") for d in docs.values() if d.get("type") == "Manifest"}

    rapports = []
    strict_exec = None
    for ch, doc in docs.items():
        typ = doc.get("type")
        if typ == "Manifest":
            rap = valider_manifest(doc)
        elif typ == "Collection":
            rap = valider_collection(doc, manifest_ids)
        else:
            rap = Rapport(ch)
            rap.e(f"type racine non géré : {typ!r} (Manifest ou Collection attendu)")
        rap.nom = os.path.basename(ch)
        ran = _strict(doc, rap)           # passe stricte (auto si iiif-prezi3 présent)
        strict_exec = ran if strict_exec is None else (strict_exec and ran)
        rapports.append(rap)

    total_err = total_warn = 0
    for rap in rapports:
        statut = "OK" if not rap.err else f"{len(rap.err)} ERREUR(S)"
        print(f"── {rap.nom} : {statut}"
              + (f", {len(rap.warn)} avertissement(s)" if rap.warn else ""))
        for m in rap.err:
            print(f"   ✗ {m}")
        for m in rap.warn:
            print(f"   ! {m}")
        total_err += len(rap.err)
        total_warn += len(rap.warn)

    if strict_exec is None:               # aucun document traité
        etat = "—"
    else:
        etat = "exécutée" if strict_exec else "non exécutée (iiif-prezi3 absent)"
    print(f"\nConformité stricte (iiif-prezi3) : {etat}.")
    print(f"Total : {total_err} erreur(s), {total_warn} avertissement(s) "
          f"sur {len(rapports)} document(s).")
    return 1 if total_err else 0


if __name__ == "__main__":
    raise SystemExit(main())
