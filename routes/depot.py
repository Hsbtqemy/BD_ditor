"""Exports de dépôt, produits côté serveur et téléchargeables (EXP-1).

La doctrine « scripts hors-app » (`tools/`) supposait le MONO-POSTE : le chercheur était
*sur* la machine de la base et lançait les scripts au shell. Déployé derrière Authelia,
cet accès disparaît — plus personne n'a de shell sauf qui administre le VPS, et les trois
outils de description deviennent hors d'atteinte de ceux à qui ils servent.

Ce module n'invente rien : il applique deux patrons déjà présents dans le dépôt. Le
fichier produit côté serveur et renvoyé en pièce jointe, c'est `/api/sauvegarde` ; le cœur
partagé entre une CLI et une route, c'est `lexique_import.py`. **Aucune logique d'export
n'est réécrite ici** — c'est la condition que pose la fiche, et elle se lit dans le corps
des routes : elles rassemblent des appels, elles ne calculent rien.

**La collection est NOMMÉE, et c'est structurel — pas un confort d'URL.** Les trois outils
acceptent `collection_id=None`, qui vaut « corpus entier » ; c'est le défaut de leur CLI,
et c'est exactement ce qu'une route ne peut jamais faire. Sans identifiant de collection,
`collecter()` balaie tous les albums sans consulter la moindre portée : ce n'est pas un
export trop large, c'est un export qui ne connaît pas AUTH-2. En faisant du `collection_id`
un segment de CHEMIN plutôt qu'un paramètre facultatif, le cas « aucune collection » cesse
d'être atteignable — une route qui l'oublierait ne s'écrit pas, elle ne répond pas.
`test_depot_export.py` le vérifie sur les routes déclarées, parce qu'un chemin est plus
facile à relire qu'à garantir.

**Lire la collection SUFFIT** (arbitrage du 2026-09-07). Ces artefacts DÉCRIVENT un
périmètre auquel on est déjà admis : la fiche compte des planches qu'on peut ouvrir, les
enregistrements décrivent des albums qu'on peut lister. Rien n'en sort qui ne soit déjà
lisible à l'écran, et DROIT-1 le dit dans ces termes — à l'intérieur de l'instance, qui
est admis sur une collection en reçoit tout. La comparaison avec `/api/sauvegarde` éclaire
la différence : celle-là est réservée aux administrateurs parce qu'elle déverse la base
ENTIÈRE, toutes collections confondues, et qu'aucune portée ne s'y applique. Ici la portée
s'applique, et elle décide.

Une conséquence à ne pas manquer : `_get_collection` refuse par un **404**, jamais un 403.
C'est la règle d'AUTH-2 — « existe mais pas pour vous » révèle la composition du corpus —
et l'accesseur gardé la porte pour nous, ce qui est la raison de sa descente au socle.

Les identités ne sortent pas nommées : les outils pseudonymisent déjà (AUTH-1,
`tools/_commun.pseudonymes()`), et la fiche de description ne porte plus aucun nom depuis
le 2026-08-31 — seulement `nb_auteurs` et des paires reclassées par taux. Ces routes étant
des GET, le cliquet des sorties (`tests/test_sorties_identite.py`) les balaie d'office :
si un nom repassait, il échouerait ici sans qu'on ait rien à déclarer.
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

import autorisation
from config import BASE_DIR
from socle import _get_collection, db, portee_courante

# `tools/` n'est pas un paquet et ne s'importe pas depuis la racine : les scripts s'y
# importent entre eux à plat (`import metadonnees_collection as mc`), donc c'est le dossier
# lui-même qui doit être sur le chemin. Mesuré avant de s'y engager, et les deux mesures
# comptent : AUCUN nom de `tools/` ne masque un module de la racine (une collision ferait
# gagner le premier chemin, en silence), et l'import complet coûte 0,09 s parce que les
# dépendances lourdes — `openpyxl`, `iiif_prezi3` — y sont paresseuses.
_TOOLS = os.path.join(BASE_DIR, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

import description_collection      # noqa: E402  (cf. l'insertion de chemin ci-dessus)
import metadonnees_collection      # noqa: E402
import iiif_manifest               # noqa: E402

router = APIRouter()

_TYPES = {
    "json": "application/json",
    "csv": "text/csv; charset=utf-8",
    "zip": "application/zip",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _nom_fichier(quoi: str, collection_id: int, ext: str) -> str:
    """Le nom de la pièce, DATÉ.

    Datée pour la même raison que le manifeste IIIF l'est depuis DROIT-1 : ce qui part
    d'ici est figé, et deux exports de la même collection à un an d'intervalle seraient
    autrement indistinguables dans un dossier. L'horodatage est UTC, comme le reste de la
    chaîne (`journal.py`, les notices), et non l'heure locale du serveur — un fuseau qui
    change deux fois l'an ferait reculer des noms de fichiers.

    Le nom ne porte QUE l'identifiant de la collection, jamais son intitulé : un nom saisi
    par un humain contient tôt ou tard un guillemet, un accent ou une barre oblique, et
    `Content-Disposition` n'est pas l'endroit où découvrir lequel.
    """
    horo = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"depot-{quoi}-c{collection_id}-{horo}.{ext}"


def _piece_jointe(fabrique) -> Response:
    """Emballe le résultat de `produire` en pièce jointe téléchargeable."""
    nom, media_type, data = fabrique
    return Response(data, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{nom}"'})


def _json_bytes(obj) -> bytes:
    """Même sérialisation que les CLI : indenté, accents en clair (`ensure_ascii=False`).

    Un JSON de dépôt se relit à l'œil et se diffe entre deux versions ; les échappements
    `\\uXXXX` rendraient les deux gestes pénibles pour un corpus francophone.
    """
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


# Ce que chaque export accepte. Les routes GET le redisent dans leur `Query(pattern=…)`,
# qui est ce que /docs publie ; le DÉPÔT ShareDocs, lui, reçoit un corps JSON libre et
# n'avait rien pour le contredire. Sans cette table, `{"quoi": "metadonnees", "format":
# "csv"}` tombait dans la dernière branche de `_faire_metadonnees` et déposait un CLASSEUR
# XLSX — nom et contenu cohérents entre eux, et sans rapport avec la demande. Une
# réinterprétation silencieuse est pire qu'un refus : le fichier a l'air bon.
_FORMATS = {
    "description": ("json", "csv"),
    "metadonnees": ("json", "zip", "xlsx"),
    "iiif": ("zip",),
}


def produire(conn, portee, collection_id: int, quoi: str, format: str, *,
             verbatim: bool = False, base_url: str = "") -> tuple:
    """Fabrique UN artefact de dépôt. Rend `(nom_de_fichier, type_mime, octets)`.

    Point de passage unique des DEUX voies de sortie : le téléchargement, juste en
    dessous, et le dépôt ShareDocs — qui vit dans `main.py`, parce que SHARE-1 y épingle
    la résolution du compte (`_principal_sharedocs`) et qu'un module de routes ne remonte
    jamais vers `main`. Les laisser fabriquer chacun de leur côté donnerait deux artefacts
    au même nom et au contenu différent, ce qu'un entrepôt ne pardonne pas : il garde les
    deux versions, et plus rien ne dit laquelle a été déposée.

    La garde est ici, donc commune aux deux voies : LIRE la collection. Ce que le dépôt
    ShareDocs exige en plus lui appartient et se pose là-bas — envoyer dans un dossier
    partagé que l'application ne contrôle pas n'est pas le même geste que télécharger
    pour soi.
    """
    if quoi not in _FORMATS:
        raise HTTPException(422, f"Export « {quoi} » inconnu (attendu : "
                                 f"{', '.join(_FORMATS)}).")
    if format not in _FORMATS[quoi]:
        raise HTTPException(422, f"Le format « {format} » n'existe pas pour l'export "
                                 f"« {quoi} » (attendu : {', '.join(_FORMATS[quoi])}).")

    _get_collection(conn, portee, collection_id)
    if quoi == "description":
        data, ext = _faire_description(conn, collection_id, format)
    elif quoi == "metadonnees":
        data, ext = _faire_metadonnees(conn, collection_id, format, verbatim)
    else:
        data, ext = _faire_iiif(conn, collection_id, base_url, verbatim), "zip"
    return _nom_fichier(quoi, collection_id, ext), _TYPES[ext], data


@router.get("/api/collections/{collection_id}/depot/description")
def depot_description(collection_id: int,
                      format: str = Query("json", pattern="^(json|csv)$"),
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """La fiche de description de la collection — `tools/description_collection.py`.

    Deux formats, ceux que l'outil produit déjà : le roll-up JSON (identité, couverture,
    provenance, droits) et le catalogue CSV (une ligne par élément de métadonnée, avec son
    standard cible). Le CSV part en `utf-8-sig` exactement comme la CLI l'écrit : le BOM
    est ce qui fait lire les accents à Excel, et un chercheur qui télécharge un CSV
    l'ouvre dans un tableur.
    """
    return _piece_jointe(produire(conn, portee, collection_id, "description", format))


def _faire_description(conn, collection_id: int, format: str) -> tuple:
    rollup, agg = description_collection.collecter(conn, collection_id=collection_id)
    if format == "csv":
        return description_collection.catalogue_csv(agg).encode("utf-8-sig"), "csv"
    return _json_bytes(rollup), "json"


@router.get("/api/collections/{collection_id}/depot/metadonnees")
def depot_metadonnees(collection_id: int,
                      format: str = Query("json", pattern="^(json|zip|xlsx)$"),
                      verbatim: bool = False,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Les enregistrements de métadonnées — `tools/metadonnees_collection.py`.

    Trois formats : l'arbre JSON, l'archive des tables CSV, le classeur XLSX. Le troisième
    n'est pas un luxe ici : c'est le seul des trois qu'on ouvre sans outil, et ce chantier
    existe précisément pour ceux qui n'ont plus de shell.

    `verbatim` fait sortir le texte de l'œuvre, et DROIT-1 ne l'y oppose pas : sa frontière
    passe entre l'instance et l'ENTREPÔT, pas entre l'instance et le disque de qui y
    travaille. Celui qui télécharge ici lit déjà cet OCR dans l'Atelier — le lui rendre en
    tableau ne lui apprend rien. Le régime de diffusion mordra au moment de publier, et
    c'est la route IIIF qui porte cette question.

    Le XLSX peut manquer sa dépendance : `openpyxl` est un extra d'export, absent de
    l'image `runtime`. Le cas répond **503** en NOMMANT le paquet, parce qu'un format
    indisponible n'est pas une erreur de l'appelant — les deux autres formats marchent, et
    lui dire lequel installer est la seule chose utile.
    """
    return _piece_jointe(produire(conn, portee, collection_id, "metadonnees", format,
                                 verbatim=verbatim))


def _faire_metadonnees(conn, collection_id: int, format: str, verbatim: bool) -> tuple:
    if format == "json":
        arbre = metadonnees_collection.collecter(conn, verbatim=verbatim,
                                                 collection_id=collection_id)
        return _json_bytes(arbre), "json"

    tbls = metadonnees_collection.tables(conn, verbatim=verbatim,
                                         collection_id=collection_id)
    if format == "zip":
        return metadonnees_collection.zip_tables(tbls), "zip"

    # XLSX — le classeur porte en plus l'arbre et la fiche descriptive, comme `--xlsx`.
    arbre = metadonnees_collection.collecter(conn, verbatim=verbatim,
                                             collection_id=collection_id)
    fiche = description_collection.collecter(
        conn, collection_id=collection_id)[0]["description_collection"]
    try:
        return metadonnees_collection.xlsx_tables(tbls, arbre, fiche), "xlsx"
    except metadonnees_collection.ExportIndisponible as exc:
        raise HTTPException(503, str(exc))


# --------------------------------------------------------------------------- #
# Manifeste IIIF — le seul des trois qui PUBLIE
# --------------------------------------------------------------------------- #
_REFUS_HTTP = {
    # Un `base_url` inutilisable est une erreur d'appelant : 422, et le message dit quoi
    # corriger.
    "placeholder": 422,
    # Le verbatim hors régime n'est pas une erreur de saisie : la demande est bien formée
    # et c'est le DROIT qui manque. 403, et le message nomme la cause exacte — « pas
    # publique » et « embargo en cours » ne se corrigent pas de la même façon.
    "verbatim_hors_regime": 403,
}


@router.get("/api/collections/{collection_id}/depot/iiif")
def depot_iiif(collection_id: int,
               base_url: str = Query(..., min_length=1),
               verbatim: bool = False,
               conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    """Les manifests IIIF Presentation 3.0 de la collection, en archive.

    C'est le seul des trois artefacts qui serve à PUBLIER, et il porte donc la seule
    question de droits du module : DROIT-1 fait mordre `statut_diffusion` à la sortie, et
    `date_embargo` peut retenir davantage. La règle n'est pas rejouée ici — elle vit dans
    `iiif_manifest.diagnostic_regime`, que la CLI et cette route consultent toutes deux.

    **`base_url` est OBLIGATOIRE, et l'application ne peut pas le deviner.** Elle sert bien
    `/derivatives`, mais par une route cloisonnée depuis AUTH-2 : s'y désigner elle-même
    fabriquerait un manifeste dont chaque image répond 404 chez le destinataire. Il n'y a
    pas de défaut raisonnable, seulement un défaut plausible — et c'est le pire des deux.

    **Les avertissements voyagent DANS l'archive** (`AVERTISSEMENTS.txt`). La CLI les
    écrit sur `stderr`, où un humain les lit au moment où il tape la commande ; un
    téléchargement n'a personne devant lui. Les perdre serait le vrai risque : le message
    « manifeste SANS IMAGES » est ce qui distingue un dépôt qui RETIENT ses scans d'un
    dépôt qui les a OUBLIÉS, et c'est exactement la confusion que `requiredStatement`
    existe pour empêcher côté visionneuse.
    """
    return _piece_jointe(produire(conn, portee, collection_id, "iiif", "zip",
                                 verbatim=verbatim, base_url=base_url))


def _faire_iiif(conn, collection_id: int, base_url: str, verbatim: bool) -> bytes:
    # L'ordre compte, et il est celui de la CLI : un `base_url` inutilisable se signale
    # avant qu'on parle de régime, sinon le seul message corrigeable se noie.
    constats = iiif_manifest.diagnostic_base_url(base_url, remis=True)
    _refuser(constats)

    arbre = metadonnees_collection.collecter(conn, verbatim=verbatim,
                                             collection_id=collection_id)
    bloc = arbre["metadonnees_collection"].get("collection")
    albums = arbre["metadonnees_collection"]["albums"]
    reg = iiif_manifest.regime(bloc)
    constats += iiif_manifest.diagnostic_regime(bloc, reg, verbatim=verbatim)
    _refuser(constats)

    base = base_url.rstrip("/")
    nom = bloc["nom"] if bloc else None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("collection.json",
                   _json_bytes(iiif_manifest.collection(albums, base, nom)))
        for a in albums:
            z.writestr(f"manifest-a{a['id']}.json",
                       _json_bytes(iiif_manifest.manifeste_album(a, base, verbatim, reg)))
        if constats:
            z.writestr("AVERTISSEMENTS.txt", _avertissements(constats).encode("utf-8"))
    return buf.getvalue()


def _refuser(constats) -> None:
    """Traduit un constat de REFUS en réponse HTTP, en gardant le message de l'outil.

    Le message est repris au mot près plutôt que reformulé : c'est lui qui distingue les
    quatre causes possibles d'un manifeste amputé, et les redire ici les ferait diverger
    au premier ajustement.
    """
    for c in constats:
        if c.gravite == "refus":
            raise HTTPException(_REFUS_HTTP.get(c.code, 422), c.message)


def _avertissements(constats) -> str:
    """Le fichier qui accompagne l'archive. Daté, pour la même raison que l'archive l'est."""
    quand = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lignes = [f"Constats émis à la génération de cette archive ({quand}).", ""]
    lignes += [f"ATTENTION — {c.message}" for c in constats if c.gravite == "attention"]
    return "\n".join(lignes) + "\n"

