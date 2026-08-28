"""Génère des manifests IIIF Presentation 3.0 à partir du corpus.

Une **Manifest** par album ; un **Canvas** par planche (aux dimensions MASTER,
`largeur_px`/`hauteur_px`) ; l'image (dérivé web) peinte dessus ; **une annotation
par région** ciblant `canvas#xywh=x,y,w,h` (les coordonnées master = le repère
IIIF, cf. docs/dictionnaire-metadonnees.md). Une **Collection** englobe les albums.

Ce n'est qu'une sérialisation des données existantes — aucune transformation de
coordonnées. Il reste à servir les images (serveur IIIF Image ou statiques) sous
`--base-url`. Lecture SEULE.

**`--base-url` ne doit PAS désigner l'application (AUTH-2).** Un manifeste est fait pour
être remis à quelqu'un : sa visionneuse ira chercher les images aux URL qu'il contient,
sans la session Authelia du producteur. Or depuis AUTH-2 l'application sert `/derivatives`
par une route CLOISONNÉE — un manifeste pointant vers elle ne montrerait que des 404 chez
son destinataire. Les images doivent donc venir d'un serveur qui leur est accessible :
serveur IIIF Image de l'entrepôt, ou copie exposée des dérivés.

Rien n'est publié par cet outil : il écrit du JSON, sur la sortie standard ou dans un
dossier. Et ce que ces images doivent devenir — publiques ou non — relève du tiering de
droits (DROIT-1) : les images ne sortent que d'une collection déclarée `public`, et
seulement si elle est NOMMÉE (`--collection`). Sans elle, aucun régime n'est déclaré et le
manifeste est écrit sans images — la géométrie et l'enrichissement restent publiables.

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
import datetime as _dt
import json
import os
import sqlite3
import sys
from collections import namedtuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH, WEB_SCALE  # noqa: E402
import database  # noqa: E402  (etat_embargo : le même dérivé que l'écran Collections)
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


def _canvas(p, aid, base, verbatim, images=True):
    """Un Canvas. `images=False` (DROIT-1) le prive de son AnnotationPage `painting`.

    Le Canvas SURVIT sans image : il garde ses dimensions master et ses annotations de
    régions, donc la géométrie et l'enrichissement restent publiables. C'est le scénario
    de la piste A — déposer ouvertement son travail sur un fonds qu'on ne peut pas
    diffuser. Une visionneuse affichera une page vide annotée, ce qui est la description
    exacte de ce qu'on a le droit de montrer.
    """
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
              "height": H, "width": W, "items": [painting] if images else []}

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


# --------------------------------------------------------------------------- #
# DROIT-1 — publier n'est pas citer
# --------------------------------------------------------------------------- #
# Ce manifeste est le SEUL artefact du dépôt qui émette des URL d'images vers l'extérieur.
# Il est donc le point où le régime de diffusion devient opposable : une collection qui
# n'est pas `public` ne fait pas sortir ses scans.
#
# La règle est fail-closed et tient en une phrase : PUBLIER SUPPOSE DE NOMMER LA COLLECTION
# QU'ON PUBLIE. Sans `--collection`, l'outil porte sur le corpus entier — donc sur aucun
# régime déclaré — et n'emporte aucune image. C'est aussi ce qui règle le cas d'un album
# vivant dans plusieurs collections (AUTH-3) sans inventer d'arbitrage : le régime qui
# s'applique est celui de la collection AU NOM DE LAQUELLE on publie.
#
# Ce n'est pas le renversement de la doctrine « décrire, pas imposer » (2026-07-16) : une
# déclaration doit mordre là où la donnée quitte l'outil, et nulle part ailleurs. À
# l'intérieur de l'instance, `statut_diffusion` ne borde toujours rien.
#
# `date_embargo` entre ici, et dans un seul sens : ELLE RETIENT, ELLE NE PROMEUT JAMAIS.
#
#   · une collection `public` dont l'embargo COURT encore ne fait pas sortir ses scans —
#     la date est plus restrictive que le statut, donc la date gagne ;
#   · une collection `embargo` dont la date est ÉCHUE ne devient pas publiable pour
#     autant : la passer en `public` est un ACTE, avec quelqu'un derrière.
#
# La raison de l'asymétrie tient à ce que l'outil IGNORE : il ne sait pas POURQUOI
# l'embargo existe. Un délai qu'on s'est donné (soutenance, accord d'éditeur) se lève de
# soi-même ; un délai imposé par un ayant droit ne se lève pas — son échéance dit que la
# contrainte a couru, pas que les droits sont à nous. Le champ qui ferait la différence,
# c'est `base_legale`, et il est vide par construction (DEPOT-1). Publier sur la foi d'une
# date serait exactement la politique inventée contre laquelle la fiche met en garde.
#
# Ce qui ne veut pas dire se taire : une échéance dépassée est SIGNALÉE (cf. `main`), et
# l'écran Collections l'affiche. Un embargo échu que personne ne remarque garde un corpus
# fermé par inertie — ce qui trahit l'orientation open-science aussi sûrement qu'une fuite
# trahit les droits.

# Tout ce que le manifeste doit savoir du régime, en un seul objet. Quatre valeurs traînées
# de main en main finissaient par se croiser dans les appels positionnels.
#
# `genere_le` n'est pas du régime, mais il voyage avec lui pour une raison : ce que le
# manifeste DÉCLARE (« régime : restreint ») n'est vrai qu'à une date. Déposé à Nakala,
# qui est l'entrepôt du FIGÉ, il l'affirmera encore quand la collection sera passée
# `public` — d'où la date, qui transforme une assertion intemporelle en constat daté.
Regime = namedtuple("Regime", "images statut embargo date genere_le")
Regime.__new__.__defaults__ = (True, None, None, None, None)


def _regime(bloc, aujourdhui=None):
    """Le `Regime` du bloc `collection` de l'arbre — None = corpus entier.

    `embargo` est l'état de la date (`database.etat_embargo`) : None | 'pendant' | 'echu'
    | 'illisible'. Il est porté au lieu d'être recalculé par l'appelant, parce que le
    message qui accompagne un manifeste amputé doit dire LAQUELLE des deux raisons
    s'applique — « la collection n'est pas publique » et « son embargo court encore » ne se
    corrigent pas de la même façon.
    """
    jour = aujourdhui or _dt.date.today().isoformat()
    statut = (bloc or {}).get("statut_diffusion")
    embargo = database.etat_embargo(bloc, jour)
    return Regime(images=statut == "public" and embargo in (None, "echu"),
                  statut=statut, embargo=embargo,
                  date=(bloc or {}).get("date_embargo"), genere_le=jour)


# Libellé du `requiredStatement` qui DÉCLARE l'absence des scans. Un consommateur doit
# pouvoir distinguer « ce manifeste retient ses images » de « ce manifeste a oublié ses
# images » — sans quoi les deux se ressemblent, et le second cesse d'être détectable.
# `requiredStatement` est le bon véhicule : IIIF impose aux visionneuses de l'AFFICHER.
DECLARATION_SANS_IMAGES = "Scans non diffusés"


def manifeste_album(a, base, verbatim, regime=None):
    reg = regime if regime is not None else Regime()
    images, statut, embargo = reg.images, reg.statut, reg.embargo
    date_embargo = reg.date
    # Le manifeste est le SEUL artefact de la chaîne de dépôt qui ne datait pas — les
    # notices posent `genere_le`, la figure citable `date_export`. Or c'est justement lui
    # qu'on fige à Nakala : sans sa date, deux manifestes du même album déposés à un an
    # d'intervalle sont indistinguables, et la déclaration de droits qu'il porte se lit
    # comme une vérité de toujours.
    meta = _album_metadata(a)
    if reg.genere_le:
        meta = meta + [_meta("Manifeste généré le", reg.genere_le)]
    man = {
        "@context": CTX,
        "id": f"{base}/album/{a['id']}/manifest.json",
        "type": "Manifest",
        "label": _lang(a["titre"]),
        "metadata": meta,
        "items": [c for c in (_canvas(p, a["id"], base, verbatim, images)
                              for p in a["planches"]) if c is not None],
    }
    if not images:
        # DROIT-1 — le manifeste porte la géométrie et l'enrichissement, pas les scans.
        # Le dire dans l'artefact plutôt que dans un message de console : la console se
        # perd au premier pipeline, le manifeste voyage avec les données.
        # La raison énoncée doit être la VRAIE. Une collection `public` retenue par un
        # embargo qui court dirait sinon « régime : public » tout en retenant ses images —
        # une déclaration qui se contredit elle-même, et le lecteur n'aurait aucun moyen
        # de savoir laquelle des deux moitiés croire.
        if embargo == "pendant":
            raison = f" : un embargo court jusqu'au {date_embargo} (régime : {statut})."
        elif embargo == "illisible":
            raison = (f" : une date d'embargo est déclarée mais illisible "
                      f"(« {date_embargo} », attendu AAAA-MM-JJ ; régime : {statut}).")
        elif statut:
            raison = f" (régime : {statut})."
        else:
            raison = " : aucun régime de diffusion n'est déclaré."
        # « au {date} » n'est pas un ornement : déposé dans un entrepôt qui FIGE, ce
        # manifeste affirmera encore « régime : restreint » le jour où la collection sera
        # passée `public`. Daté, il cesse d'être une vérité de toujours pour redevenir ce
        # qu'il est — un constat, que son lecteur peut aller vérifier à la source.
        quand = f" Constat du {reg.genere_le}." if reg.genere_le else ""
        man["requiredStatement"] = {
            "label": _lang(DECLARATION_SANS_IMAGES),
            "value": _lang(
                "Les images de ce corpus ne sont pas diffusées" + raison + quand
                + " La géométrie des planches et l'enrichissement le sont. Pour un usage "
                  "savant ponctuel, citer un extrait plutôt que publier le corpus."),
        }
    return man


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

    # Garde-fous sur `--base-url` (AUTH-2). Aucun des deux ne peut PROUVER que l'URL
    # désigne un serveur d'images ; ils attrapent les deux méprises qui se voient.
    hote = base.split("//", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    if args.out_dir and base == ap.get_default("base_url").rstrip("/"):
        print("REFUS — `--base-url` est resté sur le placeholder. Écrire des manifests "
              "destinés à être remis avec des URL d'images mortes ne rend service à "
              "personne : précisez le serveur qui servira les images.", file=sys.stderr)
        return 2
    if hote in ("localhost", "127.0.0.1", "::1", "[::1]") or hote.endswith(".local"):
        print(f"ATTENTION — `--base-url` désigne un hôte local ({hote}), qui est sans "
              "doute l'application elle-même. Depuis AUTH-2, elle sert /derivatives par "
              "une route cloisonnée : un destinataire de ce manifeste n'obtiendrait que "
              "des 404. Les images doivent venir d'un serveur qui lui est accessible.",
              file=sys.stderr)

    with _connexion_ro() as conn:
        arbre = mc.collecter(conn, verbatim=args.verbatim, collection_id=args.collection)
    albums = arbre["metadonnees_collection"]["albums"]
    bloc = arbre["metadonnees_collection"].get("collection")   # None = corpus entier
    nom_collection = bloc["nom"] if bloc else None

    # DROIT-1 — le régime de la collection NOMMÉE décide si les images sortent, et la
    # date d'embargo peut le restreindre encore.
    reg = _regime(bloc)
    images, statut, embargo, date_embargo = reg.images, reg.statut, reg.embargo, reg.date

    # Une échéance dépassée ne change RIEN au calcul — elle ne promeut pas — mais elle
    # cesse d'être muette. C'est le seul endroit où quelqu'un s'apprête à publier : c'est
    # donc là que « l'embargo est fini, et personne ne l'a levé » se dit utilement.
    if embargo == "echu" and statut == "embargo":
        print(f"ATTENTION — l'embargo de « {nom_collection} » est ÉCHU depuis le "
              f"{date_embargo}, et la collection est toujours déclarée « embargo ». "
              "L'outil ne la publie pas pour autant : une date qui passe ne dit pas que "
              "les droits sont acquis. Si l'embargo est bien levé, déclarez-la `public`.",
              file=sys.stderr)

    if not images:
        # Deux pannes distinctes, deux gestes distincts : « déclarez-la `public` » ne sert
        # à rien quand elle L'EST déjà et qu'un embargo la retient.
        cause = (f"la collection « {nom_collection} » est déclarée « {statut} », et son "
                 f"embargo court jusqu'au {date_embargo}" if embargo == "pendant" else
                 f"la collection « {nom_collection} » déclare une date d'embargo illisible "
                 f"(« {date_embargo} », attendu AAAA-MM-JJ)" if embargo == "illisible" else
                 f"la collection « {nom_collection} » est déclarée « {statut} »" if statut
                 else f"la collection « {nom_collection} » ne déclare aucun régime de "
                      "diffusion" if bloc else
                 "aucune collection n'est nommée (--collection), donc aucun régime n'est "
                 "déclaré")
        if args.verbatim:
            print(f"REFUS — `--verbatim` fait sortir le texte de l'œuvre, et {cause}."
                  " Publier suppose une collection déclarée `public` et hors embargo ; "
                  "pour un usage savant ponctuel, citez plutôt (export de figure).",
                  file=sys.stderr)
            return 2
        print(f"ATTENTION — manifeste SANS IMAGES : {cause}. "
              "La géométrie et l'enrichissement sont publiables, les scans non."
              # Ne promettre la sortie automatique QUE si elle aura bien lieu : sur une
              # collection qui n'est pas déclarée `public`, l'échéance ne publiera rien,
              # et l'annoncer serait le message qui ment — déjà attrapé sur AUTH-3.
              + (" Les images sortiront d'elles-mêmes une fois la date passée."
                 if embargo == "pendant" and statut == "public" else
                 " À l'échéance il faudra encore la déclarer `public` : l'outil ne lève "
                 "pas un embargo tout seul."
                 if embargo == "pendant" else
                 " Corrigez la date (AAAA-MM-JJ) pour que l'outil puisse la lire."
                 if embargo == "illisible" else
                 # Ne pas présenter le cas NORMAL comme un manque (précision du
                 # 2026-08-28) : un dépôt Nakala reçoit d'abord le manifeste et ses
                 # Canvas, pas les planches. « Déclarez-la public » en conclusion sèche
                 # ferait de la forme attendue une déficience à corriger.
                 " C'est la forme habituelle d'un dépôt, qui porte le manifeste et ses "
                 "Canvas ; pour y joindre les scans, la collection doit être déclarée "
                 "`public`."),
              file=sys.stderr)

    if not args.out_dir:
        if not albums:
            print("{}")
            return 0
        print(json.dumps(manifeste_album(albums[0], base, args.verbatim, reg),
                         ensure_ascii=False, indent=2))
        return 0

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "collection.json"), "w", encoding="utf-8") as f:
        json.dump(collection(albums, base, nom_collection), f, ensure_ascii=False, indent=2)
    for a in albums:
        man = manifeste_album(a, base, args.verbatim, reg)
        with open(os.path.join(args.out_dir, f"manifest-a{a['id']}.json"),
                  "w", encoding="utf-8") as f:
            json.dump(man, f, ensure_ascii=False, indent=2)
        print(f"  manifest-a{a['id']}.json : {len(man['items'])} canvas", file=sys.stderr)
    print(f"Manifests IIIF écrits : {args.out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
