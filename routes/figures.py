"""Figure citable (DROIT-1) — CITER n'est pas PUBLIER.

Bloc sorti de `main.py` (ARCH-1). Chemins et contrat d'API inchangés : un routeur
inclus apparaît dans `app.routes` comme une route déclarée sur `app`, ce dont
dépendent les trois cliquets du dépôt. Les imports ci-dessous sont CALCULÉS depuis
les noms libres du bloc, jamais recopiés à l'œil — c'est cette erreur-là qui a
produit 49 tests rouges au premier bloc extrait.
"""
from __future__ import annotations

import io
import json
import re
import sqlite3
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

import autorisation
import figure as figure_citable
from pipeline.ocr import region_crop_png

from socle import FigureIn, _get_region, db, portee_courante

router = APIRouter()

# `statut_diffusion` ne borde RIEN à l'intérieur de l'instance (arbitrage du 2026-08-28) :
# l'annotation repose sur les images, et le travail interne relève de l'usage savant. Ce
# que le régime oppose, c'est la SORTIE — et il faut alors distinguer deux gestes que rien
# ne rapproche :
#
#   PUBLIER — mettre un corpus à disposition (manifeste IIIF, paquet de dépôt). Porte sur
#   une collection entière, n'emporte d'images que si elle est déclarée `public`.
#
#   CITER — extraire une case identifiée pour l'accompagner d'un discours. Jamais bloqué
#   par le régime : c'est l'usage que la recherche revendique, et un fonds sous droits est
#   celui qu'on cite plutôt que de le diffuser. Le régime ACCOMPAGNE la figure au lieu de
#   l'interdire — « décrire, pas imposer » appliqué à l'artefact lui-même.
#
# La ligne passe donc par la NATURE de l'acte et non par un volume : un plafond serait un
# chiffre qu'on ne sait pas justifier, et DROIT-1 met en garde contre le fait de coder une
# politique qu'on ne connaît pas encore (DEPOT-1).
# =========================================================================== #
def _figure_zip(conn, portee: autorisation.Portee, payload: FigureIn) -> tuple[str, bytes]:
    """Construit le zip : un PNG par région, plus sa légende et sa notice structurée.

    Chaque région est vérifiée par l'accesseur GARDÉ : citer ne contourne pas le
    cloisonnement d'AUTH-2, il s'y ajoute. Une région hors portée est un 404, comme partout.
    """
    if not payload.regions:
        raise HTTPException(422, "Aucune région à exporter.")
    champs = payload.champs if payload.champs is not None else list(figure_citable.CHAMPS)
    inconnus = [c for c in champs if c not in figure_citable.CHAMPS]
    if inconnus:
        raise HTTPException(
            422, f"Mention(s) inconnue(s) : {', '.join(inconnus)} "
                 f"({' | '.join(figure_citable.CHAMPS)}).")
    if payload.collection_id is not None and not portee.peut_lire(payload.collection_id):
        raise HTTPException(404, f"Collection {payload.collection_id} introuvable")
    taille = max(40, min(payload.taille, 2000))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rid in payload.regions:
            _get_region(conn, portee, rid)          # 404 si hors portée — pas de passe-droit
            png = region_crop_png(conn, rid, max_dim=taille)
            if png is None:
                raise HTTPException(404, f"Région {rid} introuvable")
            leg = figure_citable.legende(
                conn, rid, champs, collection_id=payload.collection_id,
                lisibles=None if portee.tout else portee.lecture)
            base = _nom_figure(leg, rid)
            zf.writestr(f"{base}.png", png)
            zf.writestr(f"{base}.txt", figure_citable.texte(leg))
            zf.writestr(f"{base}.json", json.dumps(
                {"region_id": rid, **leg}, ensure_ascii=False, indent=2))
    horodate = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"figures_{horodate}.zip", buf.getvalue()


def _nom_figure(leg: dict, region_id: int) -> str:
    """Nom de fichier lisible, dérivé de la citation (« pl. 3 · c2 » → « pl3-c2 »).

    Le nom porte le repère plutôt qu'un id interne : une figure se retrouve dans un dossier
    de travail par ce qu'elle montre, pas par sa clé primaire. Repli sur l'id quand la
    citation n'a pas été demandée dans les mentions.
    """
    brut = (leg.get("citation") or "").strip()
    if not brut:
        return f"region-{region_id}"
    garde = [c.lower() if c.isalnum() else "-" for c in brut]
    nom = re.sub(r"-+", "-", "".join(garde)).strip("-")
    return nom or f"region-{region_id}"


@router.get("/api/figure/champs")
def figure_champs():
    """Les mentions offertes pour la légende, avec leur libellé. Sert le sélecteur de l'UI.

    Route SANS portée, et c'est écrit : elle décrit le FORMAT d'une légende, pas un corpus.
    Elle renverrait la même chose sur une instance vide.
    """
    libelles = {
        "titre": "Titre (et série)", "auteur": "Responsabilité", "editeur": "Éditeur",
        "annee": "Année d'édition", "isbn": "ISBN / dépôt légal",
        "citation": "Repère dans l'album (pl. · case · bulle)",
        "collection": "Corpus d'étude", "licence": "Licence du jeu enrichi",
        "base_legale": "Base légale du corpus",
        "mention_citation": "Mention de courte citation",
        "date_export": "Date de consultation",
    }
    return [{"champ": c, "libelle": libelles[c]} for c in figure_citable.CHAMPS]


@router.post("/api/figures")
def exporter_figures(payload: FigureIn, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Figure(s) citable(s) : le crop, sa légende prête à coller, sa notice structurée.

    Le régime de diffusion n'est PAS consulté, et c'est la décision du chantier : citer
    relève du droit de citation, pas de la diffusion. Il n'est pas ignoré pour autant — il
    part DANS la légende (`licence`, `base_legale`), y compris « base légale non établie »
    quand c'est le cas, ce qui est aujourd'hui la vérité du dépôt. La taire ferait passer
    pour réglé ce qui ne l'est pas.

    Le cloisonnement d'AUTH-2 s'applique entièrement : on ne cite que ce qu'on voit.
    """
    nom, octets = _figure_zip(conn, portee, payload)
    return Response(
        octets, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nom}"'})
