"""Les RELEVÉS — ce qu'on pose avec une grille (ANN-7, tranche 1 ; cadrage R5 à R7).

Un relevé est une entrée d'une version de grille posée sur une cible : des mots d'une zone de
texte, une région entière, ou la planche (la surface). Ce module en porte les routes, sans
écran — la page Annotation (tranche 2) les consommera.

Le découpage en mots d'abord (R6, G11) : `GET /api/regions/{id}/mots` rend celui de l'outil
(`mots.py`), le seul — la page Annotation dessine depuis lui, elle ne découpe jamais.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

import autorisation
import mots
from socle import _get_region, db, portee_courante

router = APIRouter()


@router.get("/api/regions/{region_id}/mots")
def mots_de_la_region(region_id: int, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Le découpage en mots du texte d'une région : `{region_id, texte, mots: [{rang, forme,
    debut, fin}]}` — `texte[debut:fin] == forme`. À qui LIT la région (404 sinon). Une
    région sans texte n'a aucun mot. Sans moteur de langue, rien ne change : le découpage
    n'en dépend pas (la raison de la décision du 2026-10-14)."""
    r = _get_region(conn, portee, region_id)
    texte = r["ocr_texte"] or ""
    return {"region_id": region_id, "texte": texte, "mots": mots.decouper(texte)}
