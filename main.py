"""BéDéditeur — application FastAPI (routes albums, planches, régions,
annotations, recherche, export).

Lancer :  uvicorn main:app --reload
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import sqlite3
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Iterator, Optional

from fastapi import (Depends, FastAPI, File, Form, HTTPException, Query, Request,
                     UploadFile)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import (AUTH_ADMIN_GROUPS, AUTH_LOGOUT_URL, AUTH_PROXY, CIBLES_ATTRIBUT,
                    DATA_DIR, REFERENT_CONTACT, REFERENT_NOM, RELECTURE, ROLES_PLANCHE,
                    STATIC_DIR, STATUTS, STATUTS_DIFFUSION, TEMPLATES_DIR, TYPES_REGION,
                    UPOS_TAGS)
from database import (citations_regions, collection_par_defaut, collection_row,
                      collections, contributions_album, dimensions_cm, etat_embargo,
                      nom_reserve, get_connection, init_db, lexique_resume, noms_lisibles,
                      numeros_editoriaux, relecture_planches, reindex_region,
                      unindex_region)
import accord
import accord_inter
import autorisation
import figure as figure_citable
import journal
import lexique_import
import sante as sante_moteurs
import undo
from pipeline.backup import make_backup
from pipeline import jobs
from pipeline import nlp
from pipeline.bulles import BullesError, bulles_available, detect_bulles
from pipeline.ingest import (ingest_image, remove_album_files,
                             remove_planche_files, store_upload)
from pipeline.ocr import OCRError, ocr_available, ocr_planche, region_crop_png
from pipeline.ordering import move_region, reorder_planche
from pipeline.segmentation import KumikoError, kumiko_available, segment_planche
from pipeline import sharedocs
from pipeline.sharedocs import ShareDocsError

# Extensions image acceptées à l'import (Pillow ; PDF non géré pour l'instant).
IMG_EXTS = (".tif", ".tiff", ".jpg", ".jpeg",
            ".jp2", ".j2k", ".jpf", ".jpx", ".jpc", ".j2c",   # JPEG2000 (Pillow/OpenJPEG)
            ".png", ".bmp", ".gif", ".webp")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Pré-chauffage NLP optionnel (déconseillé en consultation pure) : évite le
    # gel de la 1re écriture/recherche sur le chargement à froid de spaCy.
    if os.environ.get("BD_NLP_PREWARM", "").lower() in ("1", "true", "yes", "on"):
        nlp.prewarm()
    yield


app = FastAPI(title="BéDéditeur", version="1.0", lifespan=lifespan)


async def _capter_agent(request: Request) -> None:
    """Dépendance GLOBALE (une par requête) : capte l'utilisateur connecté dans le
    contextvar du journal, pour attribuer les actes humains SANS threader `request` dans
    chaque route. ASYNC → s'exécute dans la tâche de la requête, dont le contexte est copié
    vers l'endpoint sync (threadpool) → la valeur y est visible. Cf. journal.agent_courant,
    INFRA-2 (`_auteur`)."""
    journal.agent_courant.set(_auteur(request))


# Appliquée à toutes les routes du routeur principal (les montages StaticFiles sont hors
# routeur → non concernés, ce qui est voulu). `_auteur` est résolu à l'appel (défini plus bas).
app.router.dependencies.append(Depends(_capter_agent))


# --------------------------------------------------------------------------- #
# Content-Security-Policy (SEC-2)
# --------------------------------------------------------------------------- #
# DEUX politiques, et c'est une décision : une garde se pose sur la SURFACE qu'elle
# protège, pas sur le serveur entier. Les quatre pages de l'application n'ont aucun script
# inline, aucun `<style>`, aucun `onclick=`, aucune ressource externe — elles peuvent donc
# porter une politique stricte SANS qu'on touche une ligne d'application. `/docs` et
# `/redoc` sont engendrés par FastAPI depuis un CDN : leur imposer la même politique ne les
# sécuriserait pas, ça les casserait. Leur donner la leur, ÉCRITE, vaut mieux que les
# exempter — un chemin sans politique est un chemin qu'il faut se rappeler d'avoir exempté.
#
# `style-src` garde `'unsafe-inline'` pour une raison unique et bornée : dix attributs
# `style="width:…%"` portent des valeurs CALCULÉES (barres, heatmap, jauges d'accord) qui
# ne peuvent pas rejoindre la feuille de style. `style-src-elem` reprend d'une main ce que
# `style-src` donne de l'autre : aucun `<style>` n'existe, donc le canal ÉLÉMENT devient
# strict gratuitement, et seul l'attribut reste ouvert. Un navigateur qui ignore `-elem`
# retombe sur `style-src` : plus permissif, jamais cassé.
#
# `data:` est indispensable dans `img-src` — les gabarits posent `<link rel="icon"
# href="data:,">` pour éviter un 404 sur /favicon.ico.
_CSP_APP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "style-src-elem 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

# Relevé sur les pages ENGENDRÉES, pas supposé (2026-08-31) : Swagger charge son bundle et
# sa CSS depuis jsdelivr plus un `<script>` inline d'amorçage ; ReDoc charge son bundle,
# un `<style>` inline et Google Fonts ; les deux prennent leur favicon sur
# fastapi.tiangolo.com. Ce qui NE bouge pas d'une politique à l'autre est ce qui compte :
# `object-src`, `base-uri` et `frame-ancestors` restent fermés — on relâche ce qu'il faut
# pour que la page vive, pas le principe.
_CSP_DOCS = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    # MESURÉ, pas supposé : sans lui, `worker-src bloque blob:` depuis
    # redoc.standalone.js:8 — ReDoc rend son schéma dans un worker construit à partir d'un
    # blob. Il a d'abord été posé par intuition ; le retirer pour voir est ce qui l'a
    # justifié. Une directive qu'on ne sait pas justifier n'a rien à faire dans une
    # politique de sécurité, fût-elle inoffensive.
    "worker-src 'self' blob:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

# DÉRIVÉ de l'application, jamais recopié : ces quatre chemins sont configurables au
# constructeur de FastAPI. Une liste en dur ne casserait rien le jour où l'un change —
# `/docs` recevrait simplement la politique stricte et cesserait de s'afficher, sans que
# personne relie la panne à cette ligne. C'est le défaut qu'AUTH-4 avait corrigé ailleurs
# en lisant les groupes d'administration depuis `/api/moi` plutôt qu'une constante jumelle.
_CHEMINS_DOCS = frozenset(
    c for c in (app.docs_url, app.redoc_url, app.openapi_url,
                app.swagger_ui_oauth2_redirect_url) if c)


@app.middleware("http")
async def _csp(request, call_next):
    """Pose la CSP sur TOUTE réponse, pas seulement sur les pages HTML.

    Un en-tête posé partout ne coûte rien sur du JSON et ferme la question de savoir
    quelles réponses sont « des documents » : une route qui renverrait un jour du HTML
    hériterait de la politique par DÉFAUT, au lieu d'en être exemptée par oubli. C'est le
    même raisonnement que l'export qui NOMME ses colonnes (AUTH-1) : ce qu'on ajoute doit
    être couvert par décision, jamais par défaut.
    """
    response = await call_next(request)
    docs = request.url.path in _CHEMINS_DOCS
    response.headers["Content-Security-Policy"] = _CSP_DOCS if docs else _CSP_APP
    return response


@app.middleware("http")
async def _no_cache_assets(request, call_next):
    """Force la revalidation des assets (CSS/JS) et des pages HTML. Sans ça, le
    navigateur intégré d'un IDE (Cursor/VS Code, basé Chromium) peut servir un
    style.css / theme.js PÉRIMÉ tout en chargeant le HTML neuf → bandes non stylées,
    layout cassé, alors que le disque est à jour. ETag/Last-Modified de StaticFiles
    restent honorés (réponse 304 si rien n'a changé) : coût négligeable."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static") or path in ("/", "/recherche", "/corpus", "/exploration"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.exception_handler(sqlite3.OperationalError)
async def _sqlite_operational_handler(request, exc: sqlite3.OperationalError):
    """Contention SQLite (« database is locked », p.ex. une écriture pendant un
    lot ML) → 409 explicite plutôt qu'un 500 brut, pour inviter à réessayer.
    Les autres OperationalError → 500 générique (message interne non divulgué)."""
    msg = str(exc).lower()
    if "lock" in msg or "busy" in msg:
        return JSONResponse(
            status_code=409,
            content={"detail": "Base de données momentanément occupée, réessayez."})
    # Inattendue (ex. SQL malformé) : on masque le détail au client mais on la
    # TRACE côté serveur (sinon ce handler la rendrait silencieuse → indébogable).
    logging.getLogger("bd_annotator").error(
        "OperationalError SQLite inattendue", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Erreur base de données."})


# --------------------------------------------------------------------------- #
# Dépendance connexion
# --------------------------------------------------------------------------- #


def db() -> Iterator[sqlite3.Connection]:
    """Une connexion par requête. Le commit est fait EXPLICITEMENT dans chaque
    route d'écriture (et non après le yield) : le code post-yield d'une
    dépendance FastAPI s'exécute APRÈS l'envoi de la réponse, ce qui rendait
    une écriture invisible à une lecture immédiate (course écriture→lecture).
    Ici la dépendance ne gère que le rollback en cas d'erreur et la fermeture.
    """
    conn = get_connection()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def portee_courante(request: Request,
                    conn: sqlite3.Connection = Depends(db)) -> autorisation.Portee:
    """Dépendance FastAPI : la portée d'autorisation de la requête courante (AUTH-2).

    Enveloppe minuscule autour de `autorisation.resoudre` — la logique vit dans le module,
    pas ici. Toute route qui touche aux données du corpus déclare CETTE dépendance ; c'est
    ce que vérifie `tests/test_autorisation.py`, qui échoue si une route l'oublie.
    """
    return autorisation.resoudre(conn, request)


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _row(cur) -> Optional[dict]:
    r = cur.fetchone()
    return dict(r) if r else None


# --------------------------------------------------------------------------- #
# Modèles Pydantic
# --------------------------------------------------------------------------- #
class AlbumIn(BaseModel):
    # AUTH-2 : collection d'accueil. N'est PAS une colonne d'`albums` —
    # l'appartenance vit dans `collection_album` (N-N) et le champ est
    # retiré avant l'INSERT. Omis => collection de repli.
    collection_id: Optional[int] = None
    titre: str
    auteur: Optional[str] = None                # legacy → voir contributions
    annee: Optional[int] = None                 # legacy → précisé par date_edition
    editeur: Optional[str] = None
    serie: Optional[str] = None
    description: Optional[str] = None
    # Enrichissement descriptif N0 (v15) — édition détenue.
    date_edition: Optional[str] = None
    date_originale: Optional[str] = None
    langue: Optional[str] = None
    type_oeuvre: Optional[str] = None
    lieu_edition: Optional[str] = None
    edition_tirage: Optional[str] = None
    isbn: Optional[str] = None
    format_physique: Optional[str] = None
    source_numerisation: Optional[str] = None   # matériel N1 (A6) : appareil / conditions de scan


class AlbumUpdate(BaseModel):
    titre: Optional[str] = None
    auteur: Optional[str] = None
    annee: Optional[int] = None
    editeur: Optional[str] = None
    serie: Optional[str] = None
    description: Optional[str] = None
    date_edition: Optional[str] = None
    date_originale: Optional[str] = None
    langue: Optional[str] = None
    type_oeuvre: Optional[str] = None
    lieu_edition: Optional[str] = None
    edition_tirage: Optional[str] = None
    isbn: Optional[str] = None
    format_physique: Optional[str] = None
    source_numerisation: Optional[str] = None   # matériel N1 (A6)


class ContributionIn(BaseModel):
    nom: str
    role: Optional[str] = None                  # label du rôle (contrôlé-ouvert : créé au besoin)


class ContributionRoleIn(BaseModel):            # ≠ `RoleIn` (rôle de planche, plus bas)
    label: str
    bucket: Optional[str] = None                # 'creator' | 'contributor' (défaut : contributor)
    marc: Optional[str] = None


class RegionIn(BaseModel):
    type: str
    x: int = Field(0, ge=0)
    y: int = Field(0, ge=0)
    w: int = Field(0, ge=0)
    h: int = Field(0, ge=0)
    parent_id: Optional[int] = None
    ordre: Optional[int] = None
    ocr_texte: Optional[str] = None
    source: str = "manuel"


class RegionUpdate(BaseModel):
    type: Optional[str] = None
    x: Optional[int] = Field(None, ge=0)
    y: Optional[int] = Field(None, ge=0)
    w: Optional[int] = Field(None, ge=0)
    h: Optional[int] = Field(None, ge=0)
    parent_id: Optional[int] = None
    ordre: Optional[int] = None
    ocr_texte: Optional[str] = None
    source: Optional[str] = None


class StatutIn(BaseModel):
    statut: str


class ValidationIn(BaseModel):
    validee: bool


class VerrouIn(BaseModel):
    verrouillee: bool


class RoleIn(BaseModel):
    role: str


class RelectureIn(BaseModel):
    relecture: Optional[str] = None      # 'a_faire'|'en_cours'|'faite' ; null = auto (dérivé)


class TokenCorrectionIn(BaseModel):
    lemme: Optional[str] = None
    pos: Optional[str] = None
    morph: Optional[str] = None
    etat: str = "corrige"          # 'corrige' | 'valide'


class MoveIn(BaseModel):
    sens: str   # "haut" | "bas"


class SharedocsConnIn(BaseModel):
    url: str
    user: str
    password: Optional[str] = None   # vide => repli sur BD_SHAREDOCS_PASS
    # SHARE-1 — 'instance' remplace le compte de l'instance (administrateurs seuls) ;
    # sinon on ouvre SA propre session.
    compte: Optional[str] = None


class SharedocsImportIn(BaseModel):
    chemins: list[str] = Field(default_factory=list)
    album_id: Optional[int] = None
    nouvel_album: Optional[str] = None
    segmenter: bool = False
    compte: Optional[str] = None            # SHARE-1 : 'perso' | 'instance' | None (auto)


class DeposerIn(BaseModel):
    dossier: str = ""   # dossier ShareDocs cible (vide = racine)
    # SHARE-1 — le compte se CHOISIT à chaque dépôt (décision du 2026-08-28). Une
    # sauvegarde déposée sous un compte personnel atterrit dans un espace qui s'en va
    # avec la personne ; mais l'imposer priverait d'un dépôt de dépannage. None = la
    # règle par défaut (la mienne si j'en ai une, celle de l'instance sinon).
    compte: Optional[str] = None


class JobIn(BaseModel):
    passes: list[str] = Field(default_factory=list)        # segmenter / bulles / ocr
    album_ids: list[int] = Field(default_factory=list)
    planche_ids: list[int] = Field(default_factory=list)


class AnnotationIn(BaseModel):
    note: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class TagIn(BaseModel):
    label: str
    couleur: Optional[str] = None
    description: Optional[str] = None


class PersonnageIn(BaseModel):
    nom: str
    serie: Optional[str] = None
    notes: Optional[str] = None


class PersonnageUpdate(BaseModel):
    nom: Optional[str] = None
    serie: Optional[str] = None
    notes: Optional[str] = None


class LocuteurIn(BaseModel):
    personnage_id: int


class PresenceIn(BaseModel):
    personnage_id: int   # entité montrée dans une boîte personnage (§14, brique (a))


class FusionIn(BaseModel):
    cible_id: int   # personnage canonique dans lequel fusionner le doublon


class AlignementIn(BaseModel):
    """Alignement d'autorité (A5) : URI d'un référentiel externe (skos:exactMatch)."""
    uri: str
    source: Optional[str] = None   # 'wikidata'|'viaf'|'idref'… ; auto-détecté si absent


class DomaineIn(BaseModel):
    """Domaine analytique (piste B) — champ émergent qui regroupe des dimensions."""
    nom: str


class FigureIn(BaseModel):
    """Demande d'export de figure(s) citable(s) — DROIT-1.

    `champs` choisit les MENTIONS qui composeront la légende : une légende d'article, une
    légende de diapositive et une notice de catalogue n'ont pas les mêmes besoins, et
    imposer un gabarit obligerait à le retailler à la main, donc hors de l'outil, donc en
    perdant le lien entre l'image et sa référence. Défaut = tout, faute d'en savoir plus.

    `collection_id` dit AU NOM DE QUELLE ÉTUDE on cite : un album vit dans plusieurs
    collections depuis AUTH-3, et le corpus crédité n'est pas déductible.
    """
    regions: list[int]
    champs: Optional[list[str]] = None
    collection_id: Optional[int] = None
    taille: int = 1600


class CollectionIn(BaseModel):
    """Création d'une collection (AUTH-3). Volontairement minimale : un espace de travail
    s'ouvre avec un nom, et les descripteurs de DÉPÔT (licence, base légale, embargo…) se
    remplissent ensuite, quand la collection sert vraiment à quelque chose."""
    nom: str
    description: Optional[str] = None


class CollectionUpdate(BaseModel):
    """Édition partielle des descripteurs. Champ omis = inchangé."""
    nom: Optional[str] = None
    description: Optional[str] = None
    licence_defaut: Optional[str] = None
    base_legale: Optional[str] = None
    statut_diffusion: Optional[str] = None
    date_embargo: Optional[str] = None
    date_debut: Optional[str] = None
    date_fin: Optional[str] = None
    # AUTH-4 — le référent d'EXPLOITATION, désigné par le propriétaire. Distinct de
    # `responsables`, qui est scientifique et part au dépôt.
    referent_nom: Optional[str] = None
    referent_contact: Optional[str] = None


class AccesIn(BaseModel):
    """Un accès accordé : QUI (genre + principal) et à quel NIVEAU.

    `principal` est un nom, pas une référence vérifiée — l'application n'a aucun annuaire
    (invariant AUTH-1) et lit les groupes dans `Remote-Groups` à chaque requête."""
    genre: str = autorisation.UTILISATEUR      # 'utilisateur' | 'groupe'
    principal: str
    niveau: str = autorisation.LECTURE         # 'lecture' | 'ecriture' | 'proprietaire'


class DimensionDomaineIn(BaseModel):
    domaine_id: Optional[int] = None   # null = retirer la dimension de son domaine


class DimensionIn(BaseModel):
    cible: str      # 'personnage' | 'case'
    nom: str
    domaine_id: Optional[int] = None   # champ analytique de rattachement (v20 ; optionnel)


class ValeurIn(BaseModel):
    valeur: str


class LexiqueIn(BaseModel):
    """Couche définitionnelle SKOS (A4) — mise à jour PARTIELLE (patch). Champ omis = laissé
    tel quel ; `collection_id: null` explicite = promotion en GLOBAL (patron mentions→entités)."""
    definition: Optional[str] = None      # SKOS definition (→ tags.description)
    note_portee: Optional[str] = None     # SKOS scopeNote — le « situé »
    etat: Optional[str] = None            # 'provisoire' | 'defini'
    collection_id: Optional[int] = None   # portée d'appartenance ; null = global


class AttributIn(BaseModel):
    valeur_id: int


# --------------------------------------------------------------------------- #
# Helpers métier
# --------------------------------------------------------------------------- #
def _norm_tag(label: str) -> str:
    """Tags insensibles à la casse, stockés en minuscules, espaces compactés."""
    return " ".join(label.strip().lower().split())


def _sans_accents(s: str) -> str:
    """Minuscule sans diacritiques — pour une autocomplétion insensible aux accents
    (« etienne » trouve « Étienne »)."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _ensure_tags(conn: sqlite3.Connection, labels: list[str]) -> list[dict]:
    """Crée les tags manquants et renvoie les lignes correspondantes."""
    normalized = sorted({_norm_tag(l) for l in labels if _norm_tag(l)})
    for label in normalized:
        conn.execute(
            "INSERT INTO tags (label) VALUES (?) ON CONFLICT(label) DO NOTHING",
            (label,),
        )
    if not normalized:
        return []
    placeholders = ",".join("?" * len(normalized))
    return _rows(conn.execute(
        f"SELECT id, label, couleur FROM tags WHERE label IN ({placeholders})",
        normalized,
    ))


def _annotation_for_region(conn: sqlite3.Connection, region_id: int) -> dict:
    """Représentation d'annotation (note + tags) ; structure vide si absente."""
    ann = conn.execute(
        "SELECT id, note, date_creation, date_modification "
        "FROM annotations WHERE region_id = ?", (region_id,)
    ).fetchone()
    if ann is None:
        return {"region_id": region_id, "note": None, "tags": [],
                "date_modification": None}
    tags = _rows(conn.execute(
        """SELECT t.id, t.label, t.couleur
           FROM annotation_tags at JOIN tags t ON t.id = at.tag_id
           WHERE at.annotation_id = ? ORDER BY t.label""",
        (ann["id"],),
    ))
    return {"region_id": region_id, "note": ann["note"], "tags": tags,
            "date_modification": ann["date_modification"]}


# --------------------------------------------------------------------------- #
# Accesseurs GARDÉS (AUTH-2) — la seule façon d'atteindre un objet du corpus
# --------------------------------------------------------------------------- #
# Chacun exige une `Portee` et renvoie 404 quand l'objet existe mais sort d'elle. Le 404
# n'est pas une approximation du 403 : dire « cet album existe, mais pas pour vous »
# révélerait la composition du corpus — combien d'albums, quelles études voisines. La
# contrepartie est à connaître : qui perd un droit ne verra pas d'erreur, ses objets
# auront simplement disparu.
#
# La `Portee` est un paramètre OBLIGATOIRE, sans valeur par défaut. Une valeur par défaut
# qui sauterait le contrôle rendrait l'oubli invisible — c'est exactement le motif que
# SANTE-1 vient de corriger ailleurs dans ce dépôt.

def _get_album(conn, portee: autorisation.Portee, album_id: int, *,
               ecriture: bool = False) -> dict:
    ou, params = portee.clause_album("albums.id", ecriture=ecriture)
    a = _row(conn.execute(f"SELECT * FROM albums WHERE id = ? AND {ou}",
                          (album_id, *params)))
    if a is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
    return a


def _get_planche(conn, portee: autorisation.Portee, planche_id: int, *,
                 ecriture: bool = False) -> dict:
    ou, params = portee.clause_album("planches.album_id", ecriture=ecriture)
    p = _row(conn.execute(f"SELECT * FROM planches WHERE id = ? AND {ou}",
                          (planche_id, *params)))
    if p is None:
        raise HTTPException(404, f"Planche {planche_id} introuvable")
    return p


def _get_region(conn, portee: autorisation.Portee, region_id: int, *,
                ecriture: bool = False) -> dict:
    """Une région s'autorise par sa planche, qui s'autorise par son album."""
    ou, params = portee.clause_album("pl.album_id", ecriture=ecriture)
    r = _row(conn.execute(
        f"SELECT r.* FROM regions r JOIN planches pl ON pl.id = r.planche_id "
        f"WHERE r.id = ? AND {ou}", (region_id, *params)))
    if r is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    return r


def _refuser_si_verrouillee(planche: dict) -> dict:
    """Une planche verrouillée est protégée des passes AUTOMATIQUES (segmentation /
    détection de bulles / OCR) : il faut la déverrouiller explicitement. L'édition
    manuelle (texte, tags, régions) reste libre. Renvoie la planche pour chaînage."""
    if planche.get("verrouillee"):
        raise HTTPException(409, "Planche verrouillée 🔒 : déverrouillez-la pour "
                            "relancer un traitement automatique "
                            "(l'édition manuelle reste possible).")
    return planche


def _validate_parent(conn: sqlite3.Connection, planche_id: int,
                     parent_id: Optional[int], region_id: Optional[int] = None) -> None:
    """Valide un parent_id : il doit exister, être sur LA MÊME planche, et ne pas
    créer de cycle (ni s'auto-référencer). Lève HTTPException 422 sinon. Une FK
    seule ne garantit pas ces invariants — sans quoi une région cross-planche ou
    un cycle casse l'export (région omise) et fait boucler le DELETE récursif."""
    if parent_id is None:
        return
    parent = _row(conn.execute(
        "SELECT planche_id FROM regions WHERE id = ?", (parent_id,)))
    if parent is None:
        raise HTTPException(422, f"parent_id {parent_id} introuvable")
    if parent["planche_id"] != planche_id:
        raise HTTPException(422, "parent_id appartient à une autre planche")
    if region_id is not None:
        if parent_id == region_id:
            raise HTTPException(422, "Une région ne peut pas être son propre parent")
        # parent_id ne doit pas être un descendant de region_id (UNION → termine
        # même si la base contient déjà un cycle).
        descendants = {r["id"] for r in conn.execute(
            """WITH RECURSIVE d(id) AS (
                   SELECT id FROM regions WHERE id = ?
                   UNION
                   SELECT r.id FROM regions r JOIN d ON r.parent_id = d.id
               ) SELECT id FROM d""", (region_id,))}
        if parent_id in descendants:
            raise HTTPException(422, "parent_id créerait un cycle")


# =========================================================================== #
# Albums & planches
# =========================================================================== #
@app.get("/api/albums")
def list_albums(conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    ou, params = portee.clause_album("a.id")
    return _rows(conn.execute(
        f"""SELECT a.*,
                  (SELECT COUNT(*) FROM planches p WHERE p.album_id = a.id)
                      AS nb_planches,
                  (SELECT COUNT(*) FROM regions r JOIN planches p ON p.id = r.planche_id
                     WHERE p.album_id = a.id) AS nb_regions,
                  (SELECT COUNT(*) FROM regions r JOIN planches p ON p.id = r.planche_id
                     WHERE p.album_id = a.id
                       AND TRIM(COALESCE(r.ocr_texte, '')) <> '') AS nb_transcrites,
                  (SELECT COUNT(*) FROM planches p
                     WHERE p.album_id = a.id AND p.validee IS NOT NULL) AS nb_validees
           FROM albums a
           WHERE {ou}
           ORDER BY a.serie IS NULL, a.serie, a.annee, a.titre""", params
    ))


@app.post("/api/albums", status_code=201)
def create_album(album: AlbumIn, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    data = album.model_dump()                       # toutes les colonnes descriptives (dont N0)
    data["titre"] = (data.get("titre") or "").strip()   # B9 : titre requis (comme un tag)
    if not data["titre"]:
        raise HTTPException(422, "Le titre de l'album est requis.")
    # AUTH-2 — un album appartient TOUJOURS à une collection : c'est elle qui porte les
    # droits. Un orphelin ne correspondrait à aucune règle, et il faudrait alors inventer
    # une politique dans le code. Le champ est facultatif à l'API (32 appels existants
    # l'ignorent, et une instance neuve n'a pas encore de collection) mais l'appartenance,
    # elle, n'est jamais facultative : à défaut, la collection de repli.
    cid = data.pop("collection_id", None)
    if cid is not None:
        # Introuvable ET interdite donnent la MÊME réponse : dire « elle existe mais pas
        # pour vous » révélerait l'existence d'études voisines.
        if not portee.peut_ecrire(cid) or conn.execute(
                "SELECT 1 FROM collection WHERE id = ?", (cid,)).fetchone() is None:
            raise HTTPException(404, f"Collection {cid} introuvable")
    else:
        cid = collection_par_defaut(conn)
        # Ici un 403 ne fuit rien : il parle des droits de l'appelant, pas du corpus.
        if not portee.peut_ecrire(cid):
            raise HTTPException(
                403, "Aucune collection ouverte en écriture : précisez `collection_id`, "
                     "ou demandez un accès en écriture.")
    cols = list(data)
    cur = conn.execute(
        f"INSERT INTO albums ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        tuple(data.values()),
    )
    conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                 (cid, cur.lastrowid))
    conn.commit()
    return _row(conn.execute("SELECT * FROM albums WHERE id = ?", (cur.lastrowid,)))


@app.put("/api/albums/{album_id}")
def update_album(album_id: int, patch: AlbumUpdate,
                 conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    _get_album(conn, portee, album_id, ecriture=True)
    fields = patch.model_dump(exclude_unset=True)
    if "titre" in fields:                               # B9 : ne pas vider un titre par édition
        fields["titre"] = (fields["titre"] or "").strip()
        if not fields["titre"]:
            raise HTTPException(422, "Le titre de l'album est requis.")
    if fields:
        cols = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE albums SET {cols} WHERE id = ?",
                     (*fields.values(), album_id))
        conn.commit()
    return _row(conn.execute("SELECT * FROM albums WHERE id = ?", (album_id,)))


@app.delete("/api/albums/{album_id}", status_code=204)
def delete_album(album_id: int, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    _get_album(conn, portee, album_id, ecriture=True)
    # Désindexe les régions du FTS (le CASCADE SQL ne touche pas la table FTS).
    for r in conn.execute(
        "SELECT r.id FROM regions r JOIN planches p ON p.id = r.planche_id "
        "WHERE p.album_id = ?", (album_id,)).fetchall():
        unindex_region(conn, r["id"])
    conn.execute("DELETE FROM albums WHERE id = ?", (album_id,))   # CASCADE planches/regions
    conn.commit()
    remove_album_files(album_id)
    return Response(status_code=204)


@app.delete("/api/planches/{planche_id}", status_code=204)
def delete_planche(planche_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    p = _get_planche(conn, portee, planche_id, ecriture=True)
    for r in conn.execute(
        "SELECT id FROM regions WHERE planche_id = ?", (planche_id,)).fetchall():
        unindex_region(conn, r["id"])
    conn.execute("DELETE FROM planches WHERE id = ?", (planche_id,))   # CASCADE regions
    conn.commit()
    remove_planche_files(p["chemin_tiff"], p["chemin_web"])
    return Response(status_code=204)


@app.get("/api/albums/{album_id}/planches")
def album_planches(album_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    _get_album(conn, portee, album_id)
    planches = _rows(conn.execute(
        """SELECT p.*,
                  (SELECT COUNT(*) FROM regions r WHERE r.planche_id = p.id)
                      AS nb_regions,
                  (SELECT COUNT(*) FROM regions r
                     JOIN annotations an ON an.region_id = r.id
                   WHERE r.planche_id = p.id) AS nb_annotees
           FROM planches p WHERE p.album_id = ? ORDER BY p.numero""",
        (album_id,),
    ))
    nums = numeros_editoriaux(conn, album_id)
    rel = relecture_planches(conn, [p["id"] for p in planches])   # ANN-4 : statut dérivé/forcé
    # AUTH-1 — le NOM de qui détient un verrou. `verrou_par` est consigné depuis la v22 et
    # aucun écran ne le lisait : on voyait « verrouillée le … » sans savoir à qui demander
    # la levée, ce qui est précisément l'information dont on a besoin. Le login reste dans
    # la charge utile : il est stable, et lui seul permet à l'écran de dire « par vous ».
    noms = noms_lisibles(conn, [p["verrou_par"] for p in planches])
    for p in planches:
        p["verrou_par_nom"] = noms.get(p["verrou_par"])
        p["url_web"] = "/" + p["chemin_web"] if p["chemin_web"] else None
        p["numero_editorial"] = nums.get(p["id"])   # None si paratexte (cf. role)
        # Matériel (A6) : dimensions physiques dérivées (px÷dpi), None si résolution absente.
        p["dimensions_cm"] = dimensions_cm(p["largeur_px"], p["hauteur_px"],
                                           p["dpi_x"], p["dpi_y"])
        p["relecture_statut"] = rel.get(p["id"])     # {statut, derive, force, tokens, relus}
    return planches


# Route synchrone (def) : FastAPI l'exécute dans un threadpool, ce qui évite
# de bloquer la boucle d'événements pendant le redimensionnement PIL (lourd
# sur un TIFF 400 dpi). On lit donc l'upload via file.file (API synchrone).
def _allouer_numero(conn, album_id: int, numero: Optional[int]) -> int:
    """Alloue le numéro d'une nouvelle planche AVANT toute écriture de fichier (DB-1).
    Les fichiers master/dérivé sont nommés d'après le numéro : on vérifie donc l'unicité
    en amont, sinon l'écriture écraserait SILENCIEUSEMENT la planche existante de même
    numéro. `numero` explicite déjà pris → 409 ; absent → MAX+1 de l'album. L'index unique
    (album_id, numero) reste le filet en cas de course concurrente résiduelle."""
    if numero is None:
        return conn.execute(
            "SELECT COALESCE(MAX(numero), 0) + 1 AS n FROM planches WHERE album_id = ?",
            (album_id,)).fetchone()["n"]
    if conn.execute("SELECT 1 FROM planches WHERE album_id = ? AND numero = ?",
                    (album_id, numero)).fetchone():
        raise HTTPException(409, f"Le numéro {numero} est déjà pris dans cet album.")
    return numero


@app.post("/api/albums/{album_id}/import", status_code=201)
def import_planche(
    album_id: int,
    file: UploadFile = File(...),
    numero: Optional[int] = Form(None, ge=1),
    conn: sqlite3.Connection = Depends(db),
    portee: autorisation.Portee = Depends(portee_courante),
):
    _get_album(conn, portee, album_id, ecriture=True)
    data = file.file.read()
    if not data:
        raise HTTPException(400, "Fichier vide")
    # Numéro alloué AVANT écriture (DB-1) : un numéro explicite déjà pris → 409, sans
    # écraser les fichiers (master/dérivé nommés d'après lui) de la planche existante.
    numero = _allouer_numero(conn, album_id, numero)
    master = store_upload(album_id, file.filename or "planche.tif", data, numero)
    try:
        planche = ingest_image(conn, album_id, master, numero=numero)
    except sqlite3.IntegrityError:
        master.unlink(missing_ok=True)   # course rare : un concurrent a pris ce numéro
        raise HTTPException(409, f"Numéro {numero} déjà pris (course d'import) — réessayez.")
    except Exception as exc:
        # Pas de master orphelin sur disque si l'ingestion échoue après écriture.
        master.unlink(missing_ok=True)
        raise HTTPException(400, f"Échec de l'ingestion : {exc}")
    conn.commit()
    planche["url_web"] = "/" + planche["chemin_web"]
    return planche


# =========================================================================== #
# Segmentation & régions
# =========================================================================== #
@app.post("/api/planches/{planche_id}/segmenter")
def segmenter(planche_id: int, use_master: bool = False,
              conn: sqlite3.Connection = Depends(db),
              portee: autorisation.Portee = Depends(portee_courante)):
    _refuser_si_verrouillee(_get_planche(conn, portee, planche_id, ecriture=True))
    if not kumiko_available():
        raise HTTPException(
            503,
            "Kumiko n'est pas installé. Clonez-le dans lib/kumiko "
            "(git clone https://github.com/njean42/kumiko.git lib/kumiko).",
        )
    try:
        with jobs.ML_LOCK:                       # pas d'inférence ML concurrente (mémoire)
            with journal.passe_ml(conn, "segmentation", planche_id, agent="kumiko",
                                  params={"use_master": use_master}):
                res = segment_planche(conn, planche_id, use_master=use_master)
    except KumikoError as exc:
        raise HTTPException(500, str(exc))
    conn.commit()
    return res


@app.post("/api/planches/{planche_id}/detecter-bulles")
def detecter_bulles(planche_id: int, conf: float = 0.3,
                    conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    _refuser_si_verrouillee(_get_planche(conn, portee, planche_id, ecriture=True))
    if not bulles_available():
        raise HTTPException(
            503,
            "Détecteur de bulles indisponible. "
            "pip install -r requirements-ocr.txt (ultralytics + huggingface_hub).",
        )
    try:
        with jobs.ML_LOCK:                       # pas d'inférence ML concurrente (mémoire)
            from pipeline.modeles import liberer_modeles_ml
            liberer_modeles_ml(sauf=("bulles", "nlp"))   # CONC-2 : libère l'autre modèle torch (OCR)
            with journal.passe_ml(conn, "bulles", planche_id, agent="yolov8-bulles",
                                  version=journal.version_moteur("ultralytics"),
                                  params={"conf": conf}):
                res = detect_bulles(conn, planche_id, conf=conf)
    except BullesError as exc:
        raise HTTPException(500, str(exc))
    conn.commit()
    return res


@app.post("/api/planches/{planche_id}/ocr")
def ocr_route(planche_id: int, only_empty: bool = True,
              conn: sqlite3.Connection = Depends(db),
              portee: autorisation.Portee = Depends(portee_courante)):
    _refuser_si_verrouillee(_get_planche(conn, portee, planche_id, ecriture=True))
    if not ocr_available():
        raise HTTPException(
            503,
            "OCR indisponible. pip install -r requirements-ocr.txt (easyocr).",
        )
    try:
        with jobs.ML_LOCK:                       # pas d'inférence ML concurrente (mémoire)
            from pipeline.modeles import liberer_modeles_ml
            liberer_modeles_ml(sauf=("ocr", "nlp"))      # CONC-2 : libère l'autre modèle torch (bulles)
            with journal.passe_ml(conn, "ocr", planche_id, agent="easyocr",
                                  version=journal.version_moteur("easyocr"),
                                  params={"only_empty": only_empty}):
                res = ocr_planche(conn, planche_id, only_empty=only_empty)
    except OCRError as exc:
        raise HTTPException(500, str(exc))
    conn.commit()
    return res


@app.post("/api/ml/liberer")
def liberer_ml(portee: autorisation.Portee = Depends(portee_courante)):
    """Décharge les modèles ML résidents (rend la RAM) — CONC-2. Utile entre deux
    grosses passes sur machine contrainte. Sérialisé par ML_LOCK (jamais pendant une
    inférence). Renvoie la liste des moteurs libérés.

    AUTH-2 — réservé aux ADMINISTRATEURS : le verrou et les modèles sont globaux, et
    décharger pendant qu'une autre équipe travaille rallonge sa passe suivante de plusieurs
    secondes. Ici un 403 ne fuit rien : il parle des droits de l'appelant, pas du corpus.
    En mono-poste (`BD_AUTH_PROXY` absent), la portée est totale — rien ne change.
    """
    if not portee.admin:
        raise HTTPException(403, "Décharger les modèles est un acte d'exploitation, "
                                 "réservé aux administrateurs.")
    from pipeline.modeles import etat_modeles, liberer_modeles_ml
    with jobs.ML_LOCK:
        liberes = liberer_modeles_ml()
    return {"liberes": liberes, "modeles_charges": etat_modeles()}


@app.get("/api/planches/{planche_id}/regions")
def planche_regions(planche_id: int, conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    _get_planche(conn, portee, planche_id)
    regions = _rows(conn.execute(
        """SELECT r.*,
                  EXISTS(SELECT 1 FROM annotations a WHERE a.region_id = r.id)
                      AS annotee,
                  (SELECT COUNT(*) FROM regions c WHERE c.parent_id = r.id)
                      AS nb_enfants
           FROM regions r WHERE r.planche_id = ?
           ORDER BY r.parent_id IS NOT NULL, r.ordre, r.id""",
        (planche_id,),
    ))
    cits = citations_regions(conn, [r["id"] for r in regions])
    for r in regions:
        r["citation"] = cits.get(r["id"])   # {texte, planche, case[, bulle], global, total}
    return regions


@app.post("/api/planches/{planche_id}/regions", status_code=201)
def create_region(planche_id: int, region: RegionIn,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    _get_planche(conn, portee, planche_id, ecriture=True)
    if region.type not in TYPES_REGION:
        raise HTTPException(422, f"Type invalide : {region.type}")
    _validate_parent(conn, planche_id, region.parent_id)
    ordre = region.ordre
    if ordre is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(ordre), 0) + 1 AS n FROM regions "
            "WHERE planche_id = ? AND parent_id IS ?",
            (planche_id, region.parent_id),
        ).fetchone()
        ordre = row["n"]
    cur = conn.execute(
        """INSERT INTO regions
              (planche_id, parent_id, type, x, y, w, h, ordre, ocr_texte, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (planche_id, region.parent_id, region.type, region.x, region.y,
         region.w, region.h, ordre, region.ocr_texte, region.source),
    )
    new_id = cur.lastrowid
    if region.ocr_texte:
        reindex_region(conn, new_id)
    journal.journaliser(conn, "creation", "regions", new_id,
                        apres=journal.snapshot_region(conn, new_id))
    conn.commit()
    return _row(conn.execute("SELECT * FROM regions WHERE id = ?", (new_id,)))


@app.get("/api/regions/{region_id}/crop")
def region_crop(region_id: int, taille: int = 1600,
                conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    """PNG net de la région recadré dans le master.

    `taille` borne la largeur (vignettes de recherche : ~240 ; transcription :
    1600 par défaut). Bornée à [40, 2000].
    """
    _get_region(conn, portee, region_id)
    png = region_crop_png(conn, region_id, max_dim=max(40, min(taille, 2000)))
    if png is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    return Response(png, media_type="image/png")


@app.put("/api/regions/{region_id}")
def update_region(region_id: int, patch: RegionUpdate,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    existing = _get_region(conn, portee, region_id, ecriture=True)
    fields = patch.model_dump(exclude_unset=True)
    if "type" in fields and fields["type"] not in TYPES_REGION:
        raise HTTPException(422, f"Type invalide : {fields['type']}")
    if "parent_id" in fields:
        _validate_parent(conn, existing["planche_id"], fields["parent_id"], region_id)
    if fields:
        avant = journal.snapshot_region(conn, region_id)
        cols = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE regions SET {cols} WHERE id = ?",
                     (*fields.values(), region_id))
        if "ocr_texte" in fields:
            reindex_region(conn, region_id)
        # Retouche humaine d'une zone (souvent un pré-remplissage machine) : événement +
        # surface dénormalisée `touche` (lue par l'indicateur de dérive). marquer_touche
        # après le snapshot `apres` (touche n'est pas une colonne métier → hors instantané).
        journal.journaliser(conn, "modification", "regions", region_id,
                            avant=avant, apres=journal.snapshot_region(conn, region_id))
        journal.marquer_touche(conn, region_id)
        conn.commit()
    return _row(conn.execute("SELECT * FROM regions WHERE id = ?", (region_id,)))


@app.delete("/api/regions/{region_id}", status_code=204)
def delete_region(region_id: int, conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    # Désindexe la région ET tous ses descendants (le CASCADE SQL les supprime,
    # mais l'index FTS, lui, doit être nettoyé explicitement).
    descendants = conn.execute(
        """WITH RECURSIVE d(id) AS (
               SELECT id FROM regions WHERE id = ?
               UNION
               SELECT r.id FROM regions r JOIN d ON r.parent_id = d.id
           ) SELECT id FROM d""",
        (region_id,),
    ).fetchall()
    # Instantané PROFOND avant destruction (le CASCADE emporte annotation + sous-arbre) :
    # c'est le substrat de l'undo (D1). Le journal survit à la suppression (cible non-FK).
    avant = journal.snapshot_region_profond(conn, region_id)
    for r in descendants:
        unindex_region(conn, r["id"])
    conn.execute("DELETE FROM regions WHERE id = ?", (region_id,))
    journal.journaliser(conn, "suppression", "regions", region_id, avant=avant)
    conn.commit()
    return Response(status_code=204)


@app.post("/api/planches/{planche_id}/reordonner")
def reordonner(planche_id: int, conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    """Recalcule l'ordre de lecture (rang per-niveau) de toute la planche."""
    _get_planche(conn, portee, planche_id, ecriture=True)
    res = reorder_planche(conn, planche_id)
    conn.commit()
    return res


@app.post("/api/regions/{region_id}/deplacer")
def deplacer_region(region_id: int, payload: MoveIn,
                    conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Déplace une région d'un cran parmi ses frères ('haut' ou 'bas')."""
    _get_region(conn, portee, region_id, ecriture=True)
    avant = journal.snapshot_region(conn, region_id)
    try:
        res = move_region(conn, region_id, payload.sens)
    except ValueError as exc:
        raise HTTPException(404 if "introuvable" in str(exc) else 422, str(exc))
    journal.journaliser(conn, "modification", "regions", region_id,
                        avant=avant, apres=journal.snapshot_region(conn, region_id))
    conn.commit()
    return res


# =========================================================================== #
# ShareDocs (WebDAV Huma-Num) — explorateur & import
# =========================================================================== #
# Emplacement unique du mono-poste (SHARE-1). Une chaîne VIDE ne peut jamais être un
# login : `autorisation.auteur` strip et rend None sur vide.
_MONO = ""


def _principal_sharedocs(portee: autorisation.Portee) -> Optional[str]:
    """Sous quelle clé ranger la session ShareDocs de cette requête (SHARE-1).

    · **Mono-poste** (`BD_AUTH_PROXY` faux) : un emplacement unique. Il n'y a qu'une
      personne devant la machine, et le comportement d'avant SHARE-1 est conservé à
      l'identique — c'est une case du chantier, prouvée par un test.
    · **Derrière le proxy** : le login.
    · **Derrière le proxy SANS identité** : `None`, donc AUCUNE session personnelle
      possible. Les ranger toutes sous une même clé y ferait partager un compte Huma-Num
      entre inconnus — précisément le défaut que ce chantier corrige. Il reste le compte
      de l'instance, ou rien : fermeture par défaut, comme la portée vide d'AUTH-2.

    Ce module tranche la question ; `pipeline/sharedocs.py` ne sait rien du proxy et range
    ce qu'on lui donne. Deux implémentations de « qui est là » finiraient par diverger.
    """
    return _MONO if not AUTH_PROXY else portee.utilisateur


def _exiger_admin_instance(portee: autorisation.Portee, geste: str) -> None:
    """Le compte de l'instance n'appartient à personne en particulier (SHARE-1).

    Sans cette garde, la première personne qui clique « déconnexion » en prive tout le
    monde — le même défaut qu'AUTH-2 avait trouvé ailleurs : une action personnelle aux
    effets collectifs, qui marche parfaitement et casse pour les autres.
    """
    if not portee.admin:
        raise HTTPException(
            403, f"{geste} le compte ShareDocs de l'instance est réservé aux "
                 "administrateurs : il sert de repli à tout le monde.")


def _compte_demande(compte: Optional[str]) -> Optional[str]:
    """Valide le compte demandé, ou 422 qui le nomme (SHARE-1).

    Trouvé en relisant : les routes d'écriture testaient `== INSTANCE` et retombaient
    SILENCIEUSEMENT sur le compte personnel pour tout le reste. Un administrateur qui
    écrivait « instace » n'obtenait pas un refus — il ouvrait sa propre session, et
    recevait `{"connecte": true}`, ce qui se lit comme un succès. Il croyait avoir remplacé
    le compte de l'instance, le repli de tout le monde restait inchangé, et rien ne le
    disait. C'était en outre incohérent avec la LECTURE, où `resoudre` refuse déjà un
    compte inconnu : la même faute de frappe donnait un message clair sur `liste` et un
    effet silencieux sur `connexion`.
    """
    if compte is not None and compte not in sharedocs.COMPTES:
        raise HTTPException(
            422, f"Compte ShareDocs inconnu : {compte} "
                 f"({' | '.join(sharedocs.COMPTES)}).")
    return compte


@app.get("/api/sharedocs/etat")
def sharedocs_etat(portee: autorisation.Portee = Depends(portee_courante)):
    """État des sessions (jamais de mot de passe) + pré-remplissage depuis l'env.

    Dit LEQUEL des deux comptes répondrait (`actif`) : sans cela on dépose sans savoir où,
    et la question n'a plus de réponse évidente dès que les deux existent.
    """
    return sharedocs.status(principal=_principal_sharedocs(portee))


@app.post("/api/sharedocs/connexion")
def sharedocs_connexion(payload: SharedocsConnIn,
                        portee: autorisation.Portee = Depends(portee_courante)):
    """Ouvre MA session ShareDocs — ou remplace celle de l'instance (administrateurs)."""
    pwd = payload.password or os.environ.get("BD_SHAREDOCS_PASS", "")
    if _compte_demande(payload.compte) == sharedocs.INSTANCE:
        _exiger_admin_instance(portee, "Remplacer")
        try:
            return {"connecte": True, "compte": sharedocs.INSTANCE,
                    **sharedocs.configurer_instance(payload.url, payload.user, pwd)}
        except ShareDocsError as exc:
            raise HTTPException(400, str(exc))
    try:
        return sharedocs.configurer(payload.url, payload.user, pwd,
                                    principal=_principal_sharedocs(portee))
    except ShareDocsError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/sharedocs/deconnexion")
def sharedocs_deconnexion(compte: Optional[str] = None,
                          portee: autorisation.Portee = Depends(portee_courante)):
    """Ferme MA session. `compte=instance` coupe celle de l'instance (administrateurs)."""
    if _compte_demande(compte) == sharedocs.INSTANCE:
        _exiger_admin_instance(portee, "Couper")
        sharedocs.couper_instance()
        return {"connecte": False, "compte": sharedocs.INSTANCE}
    sharedocs.deconnecter(principal=_principal_sharedocs(portee))
    return {"connecte": False, "compte": sharedocs.PERSO}


@app.get("/api/sharedocs/liste")
def sharedocs_liste(chemin: str = "", compte: Optional[str] = None,
                    portee: autorisation.Portee = Depends(portee_courante)):
    _compte_demande(compte)          # 422 nommé, plutôt que le 400 générique de `resoudre`
    try:
        return sharedocs.list_dir(chemin, principal=_principal_sharedocs(portee),
                                  compte=compte)
    except ShareDocsError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/sharedocs/importer")
def sharedocs_importer(payload: SharedocsImportIn,
                       conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """Télécharge des fichiers ShareDocs et les ingère comme planches.

    Album cible : `album_id` (existant) OU `nouvel_album` (créé). Les fichiers
    non-image sont ignorés (collectés dans `erreurs`) ; un échec sur un fichier
    n'interrompt pas le lot.
    """
    if not payload.chemins:
        raise HTTPException(422, "Aucun fichier sélectionné.")
    # Avant de créer quoi que ce soit : un compte inconnu échouerait sinon FICHIER PAR
    # FICHIER, en autant d'erreurs de téléchargement qu'il y a de chemins — et la vraie
    # cause, un mot mal orthographié, ne paraîtrait nulle part.
    _compte_demande(payload.compte)
    created_album = False
    if payload.album_id is not None:
        # AUTH-2 : importer des planches, c'est écrire dans l'album.
        _get_album(conn, portee, payload.album_id, ecriture=True)
        album_id = payload.album_id
    elif payload.nouvel_album and payload.nouvel_album.strip():
        # Même invariant qu'à la création d'album : jamais d'orphelin, et il faut le droit
        # d'écrire dans la collection qui l'accueille.
        cid = collection_par_defaut(conn)
        if not portee.peut_ecrire(cid):
            raise HTTPException(
                403, "Aucune collection ouverte en écriture : créez l'album depuis la "
                     "Bibliothèque en précisant sa collection, puis importez dedans.")
        cur = conn.execute("INSERT INTO albums (titre) VALUES (?)",
                           (payload.nouvel_album.strip(),))
        album_id = cur.lastrowid
        conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                     (cid, album_id))
        created_album = True
    else:
        raise HTTPException(422, "Album cible manquant (album_id ou nouvel_album).")

    importes, erreurs = [], []
    for chemin in payload.chemins:
        nom = chemin.rsplit("/", 1)[-1]
        if os.path.splitext(nom)[1].lower() not in IMG_EXTS:
            erreurs.append({"chemin": chemin, "erreur": "type non géré (image attendue)"})
            continue
        master = None
        try:
            t0 = time.perf_counter()
            data = sharedocs.download(
                chemin, principal=_principal_sharedocs(portee), compte=payload.compte)
            if not data:
                raise ShareDocsError("fichier vide")
            t_dl = time.perf_counter() - t0
            numero = _allouer_numero(conn, album_id, None)   # auto (MAX+1) ; index unique = filet
            master = store_upload(album_id, nom, data, numero)
            t1 = time.perf_counter()
            planche = ingest_image(conn, album_id, master, numero=numero)
            t_ing = time.perf_counter() - t1
            planche["url_web"] = "/" + planche["chemin_web"]
            importes.append(planche)
            # Segmentation best-effort : un échec ici ne doit JAMAIS invalider
            # un import déjà réussi (la planche est déjà ingérée et comptée).
            t_seg = 0.0
            if payload.segmenter and kumiko_available():
                t2 = time.perf_counter()
                try:
                    with jobs.ML_LOCK:               # cohérent : pas de ML concurrent
                        res_seg = segment_planche(conn, planche["id"])
                    # L'EFFECTIF, pas « segmentee » en dur : depuis B6 la segmentation ne
                    # fait plus reculer le statut, si bien qu'écrire la constante ferait
                    # mentir la réponse d'import sur une planche déjà avancée. Le mensonge
                    # serait invisible — la base, elle, aurait raison.
                    planche["statut"] = res_seg["statut"]
                except Exception as exc:
                    # Best-effort, mais PAS muet. Ce `pass` a avalé, le 2026-08-31, un
                    # `TypeError` introduit par ce commit même : la seule trace était un
                    # statut resté `importee`, qu'on attribue naturellement à la
                    # segmentation plutôt qu'à un bug. Un import qui perd sa segmentation
                    # sans rien dire est la même faute que le lot qui s'annonçait terminé
                    # (CONC-2) — se taire n'est pas être robuste.
                    print(f"[import] segmentation ignorée pour {nom} : "
                          f"{type(exc).__name__}: {exc}")
                t_seg = time.perf_counter() - t2
            # Chronométrage par phase (diagnostic de la vitesse d'import).
            print(f"[import-timing] {nom} : download={t_dl:.2f}s "
                  f"derive={t_ing:.2f}s segment={t_seg:.2f}s "
                  f"total={t_dl + t_ing + t_seg:.2f}s "
                  f"taille={len(data) / 1e6:.1f}Mo", flush=True)
        except Exception as exc:   # un fichier en échec ne stoppe pas le lot
            # Pas de master orphelin sur disque si l'ingestion a échoué après écriture.
            if master is not None:
                master.unlink(missing_ok=True)
            erreurs.append({"chemin": chemin, "erreur": str(exc)})
    if created_album and not importes:
        # rien d'importé : ne pas laisser un album vide orphelin
        conn.execute("DELETE FROM albums WHERE id = ?", (album_id,))
    conn.commit()
    return {"album_id": album_id, "importes": importes, "erreurs": erreurs}


# =========================================================================== #
# Sauvegarde / archivage de la base
# =========================================================================== #
def _faire_sauvegarde():
    """`make_backup` avec garde (B8) : une OperationalError (base occupée) file au handler
    global (→ 409 « réessayez ») ; toute autre erreur (disque plein, chemin…) → 503 propre
    + trace serveur, au lieu d'un 500 brut."""
    try:
        return make_backup()
    except sqlite3.OperationalError:
        raise                                        # handler global : 409 si « locked/busy »
    except Exception as exc:
        logging.getLogger("bd_annotator").error("Échec de sauvegarde", exc_info=exc)
        raise HTTPException(503, "Sauvegarde impossible pour le moment (réessayez).")


def _exiger_admin_sauvegarde(portee: autorisation.Portee) -> None:
    """La sauvegarde déverse la base ENTIÈRE — tout le texte, toutes collections
    confondues. Elle est réservée aux administrateurs depuis DROIT-1.

    L'arbitrage du 2026-08-27 la laissait ouverte à tout compte, et portait sa propre
    CONDITION DE RÉOUVERTURE : « dès que l'instance accueille quelqu'un qui n'a pas le
    droit de tout voir — un partenaire extérieur, un tiering de droits effectif (DROIT-1),
    un corpus sous embargo — cette décision se rejoue. » Elle vient de se déclencher.

    L'argument d'origine tient toujours : une sauvegarde partielle ne restaure pas une
    instance, et le nom deviendrait trompeur. On ne la scope donc PAS — elle reste
    entière, et change de public. Sauvegarder est un geste d'exploitation, pas de
    recherche : le restreindre ne retire rien à personne qui en avait l'usage.

    Le mono-poste garde la sienne (`portee.tout`) : sans proxy, il n'y a personne à qui
    la refuser.
    """
    if not portee.admin:
        raise HTTPException(403, "La sauvegarde déverse la base entière, toutes "
                                 "collections confondues : elle est réservée aux "
                                 "administrateurs de l'instance.")


@app.get("/api/sauvegarde")
def telecharger_sauvegarde(portee: autorisation.Portee = Depends(portee_courante)):
    """Télécharge un snapshot cohérent de la base (zip horodaté). Administrateurs seuls."""
    _exiger_admin_sauvegarde(portee)
    name, data = _faire_sauvegarde()
    return Response(
        data, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/sharedocs/deposer-sauvegarde")
def deposer_sauvegarde(payload: DeposerIn,
                       conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """Dépose une sauvegarde de la base dans un dossier ShareDocs (PUT WebDAV).

    Même garde que le téléchargement, et pour une raison de plus : l'application ne
    contrôle pas le partage du dossier d'arrivée.

    Ce n'est PAS le régime de diffusion qui l'impose (précision du 2026-08-28) : ShareDocs
    est du stockage, pas une audience — les ressources y vivent sans question de droits, et
    y déposer n'est pas publier. La frontière de DROIT-1 passe entre l'instance et le
    DÉPÔT (Nakala), pas entre l'instance et son disque distant. La garde reste, mais elle
    tient à ce que sauvegarder est un geste d'exploitation, et à qui peut lire le dossier
    d'arrivée."""
    _exiger_admin_sauvegarde(portee)
    name, data = _faire_sauvegarde()
    folder = payload.dossier.strip("/")
    chemin = f"{folder}/{name}" if folder else name
    try:
        depot = sharedocs.upload(chemin, data,
                                 principal=_principal_sharedocs(portee),
                                 compte=payload.compte)
    except ShareDocsError as exc:
        raise HTTPException(400, str(exc))

    # SHARE-1 — le dépôt est un ACTE, et il ne laissait aucune trace : rien ne disait qui
    # avait déposé quoi, ni sous quel compte. L'événement distingue les DEUX faits — la
    # personne qui a cliqué (l'agent, capté par la dépendance globale) et le compte
    # Huma-Num employé — parce qu'ils cessent d'être le même dès qu'il y a deux comptes
    # possibles. `cible_table='sharedocs'` n'est pas une table du schéma, et c'est déjà le
    # contrat du journal (`cible_id` n'est pas une FK) ; l'undo ne le voit pas, sa liste
    # blanche de tables ne le contient pas.
    journal.journaliser(conn, "creation", "sharedocs", None,
                        apres={"chemin": chemin, "taille": len(data),
                               "compte": depot["compte"], "compte_user": depot["user"]})
    conn.commit()
    return {"depose": chemin, "taille": len(data),
            "compte": depot["compte"], "compte_user": depot["user"]}


@app.patch("/api/planches/{planche_id}/statut")
def update_statut(planche_id: int, payload: StatutIn,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    _get_planche(conn, portee, planche_id, ecriture=True)
    # AUCUN ordre de transition n'est validé ici, et c'est une DÉCISION (B6, AUDIT-1) :
    # la machine ne recule jamais (`database.avancer_statut`), l'humain le peut. Une passe
    # automatique n'a pas d'intention ; quelqu'un qui appelle cette route en a une, y
    # compris pour réparer une erreur — et `statut` ne commande RIEN dans l'application,
    # il nourrit la barre d'avancement. Interdire le retour coincerait une planche mal
    # marquée sans rien protéger. On ne valide donc que l'APPARTENANCE à `STATUTS`.
    if payload.statut not in STATUTS:
        raise HTTPException(422, f"Statut invalide : {payload.statut}")
    conn.execute("UPDATE planches SET statut = ? WHERE id = ?",
                 (payload.statut, planche_id))
    conn.commit()
    return _get_planche(conn, portee, planche_id, ecriture=True)


@app.patch("/api/planches/{planche_id}/relecture")
def update_relecture(planche_id: int, payload: RelectureIn,
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Force (ou libère) le statut de RELECTURE grammaticale d'une planche (ANN-4).
    `relecture=null` → revient au DÉRIVÉ (provenances de tokens) ; sinon override contrôlé.
    Cf. database.relecture_planches / docs/relecture.md."""
    _get_planche(conn, portee, planche_id, ecriture=True)
    if payload.relecture is not None and payload.relecture not in RELECTURE:
        raise HTTPException(422, f"Statut de relecture invalide : {payload.relecture} "
                                 f"({' | '.join(RELECTURE)} | null).")
    conn.execute("UPDATE planches SET relecture = ? WHERE id = ?",
                 (payload.relecture, planche_id))
    conn.commit()
    return {"id": planche_id, "relecture": payload.relecture,
            "relecture_statut": relecture_planches(conn, [planche_id])[planche_id]}


@app.patch("/api/planches/{planche_id}/validation")
def update_validation(planche_id: int, payload: ValidationIn,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Marque une planche comme validée (relue/finalisée) ou retire la validation.
    Drapeau humain orthogonal au `statut` du pipeline ; `validee` = horodatage."""
    _get_planche(conn, portee, planche_id, ecriture=True)
    if payload.validee:
        conn.execute("UPDATE planches SET validee = datetime('now') WHERE id = ?",
                     (planche_id,))
    else:
        conn.execute("UPDATE planches SET validee = NULL WHERE id = ?", (planche_id,))
    journal.journaliser(conn, "validation", "planches", planche_id,
                        apres={"validee": bool(payload.validee)})
    conn.commit()
    return _get_planche(conn, portee, planche_id, ecriture=True)


@app.patch("/api/planches/{planche_id}/verrou")
def update_verrou(planche_id: int, payload: VerrouIn, request: Request,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Verrouille une planche (la protège des passes automatiques en lot) ou la
    déverrouille. Distinct de `validee` (verrou = protection ≠ validation = qualité) ;
    `verrouillee` = horodatage. Cf. docs/correction-grammaticale.md §6."""
    _get_planche(conn, portee, planche_id, ecriture=True)
    if payload.verrouillee:
        # AUTH-1 : on consigne QUI verrouille. À un seul utilisateur la question ne se
        # posait pas ; à plusieurs, un verrou anonyme n'est pas levable en connaissance
        # de cause. Purement informatif — n'importe qui peut toujours déverrouiller.
        conn.execute("UPDATE planches SET verrouillee = datetime('now'), verrou_par = ? "
                     "WHERE id = ?", (_auteur(request), planche_id))
    else:
        conn.execute("UPDATE planches SET verrouillee = NULL, verrou_par = NULL "
                     "WHERE id = ?", (planche_id,))
    conn.commit()
    p = _get_planche(conn, portee, planche_id, ecriture=True)
    # Le nom accompagne le retour, sinon l'écran qui vient de poser le verrou afficherait
    # un login jusqu'au prochain rechargement — une incohérence d'une seconde, mais qui
    # ferait douter du reste.
    p["verrou_par_nom"] = noms_lisibles(conn, [p["verrou_par"]]).get(p["verrou_par"])
    return p


@app.patch("/api/planches/{planche_id}/role")
def update_role(planche_id: int, payload: RoleIn,
                conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    """Définit le rôle éditorial d'une planche : 'recit' (narrative, numérotée) ou
    'paratexte' (couverture, liminaire, pub… — écartée de la numérotation et du
    décompte de cases citables). Le numéro éditorial est DÉRIVÉ, jamais stocké ;
    on le renvoie ici (recalculé sur tout l'album) car basculer une planche décale
    les suivantes. Cf. docs/numerotation-et-citation.md."""
    planche = _get_planche(conn, portee, planche_id, ecriture=True)
    if payload.role not in ROLES_PLANCHE:
        raise HTTPException(422, f"Rôle invalide : {payload.role}")
    conn.execute("UPDATE planches SET role = ? WHERE id = ?", (payload.role, planche_id))
    conn.commit()
    out = _get_planche(conn, portee, planche_id, ecriture=True)
    out["numero_editorial"] = numeros_editoriaux(conn, planche["album_id"]).get(planche_id)
    return out


# =========================================================================== #
# Annotations & tags
# =========================================================================== #
@app.get("/api/regions/{region_id}/annotation")
def get_annotation(region_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id)
    return _annotation_for_region(conn, region_id)


@app.put("/api/regions/{region_id}/annotation")
def put_annotation(region_id: int, payload: AnnotationIn,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)

    # État avant (note + tags) pour journaliser création / modification / suppression.
    avant_annot = journal.snapshot_annotation(conn, region_id)

    tag_rows = _ensure_tags(conn, payload.tags)
    # Vider une annotation (note vide ET aucun tag) = SUPPRIMER la ligne, pas
    # laisser une coquille vide : sinon elle fausserait le compteur d'annotées,
    # ne serait pas cherchable, et ferait conserver à tort la case à la
    # re-segmentation (préservation du travail humain).
    if not (payload.note or "").strip() and not tag_rows:
        conn.execute("DELETE FROM annotations WHERE region_id = ?", (region_id,))
        reindex_region(conn, region_id)
        if avant_annot is not None:
            # Cible = region_id (STABLE), pas l'id d'annotation (détruit ici) : une annotation
            # supprimée doit rester restaurable par l'undo (D1), comme locuteur/présence.
            journal.journaliser(conn, "suppression", "annotations", region_id,
                                avant=avant_annot)
        conn.commit()
        return _annotation_for_region(conn, region_id)

    # Upsert de l'annotation (region_id est UNIQUE).
    conn.execute(
        """INSERT INTO annotations (region_id, note) VALUES (?, ?)
           ON CONFLICT(region_id) DO UPDATE SET
               note = excluded.note,
               date_modification = datetime('now')""",
        (region_id, payload.note),
    )
    ann_id = conn.execute(
        "SELECT id FROM annotations WHERE region_id = ?", (region_id,)
    ).fetchone()["id"]

    # Remplace l'ensemble des tags.
    conn.execute("DELETE FROM annotation_tags WHERE annotation_id = ?", (ann_id,))
    for t in tag_rows:
        conn.execute(
            "INSERT OR IGNORE INTO annotation_tags (annotation_id, tag_id) "
            "VALUES (?, ?)", (ann_id, t["id"]),
        )

    # Cible = region_id (stable), pas ann_id (éphémère) → undo (D1) uniforme avec locuteur/présence.
    journal.journaliser(conn, "creation" if avant_annot is None else "modification",
                        "annotations", region_id, avant=avant_annot,
                        apres=journal.snapshot_annotation(conn, region_id))
    reindex_region(conn, region_id)
    conn.commit()
    return _annotation_for_region(conn, region_id)


@app.get("/api/tags")
def list_tags(conn: sqlite3.Connection = Depends(db),
              portee: autorisation.Portee = Depends(portee_courante)):
    """Le vocabulaire de tags, avec sa fréquence d'emploi.

    AUTH-2 — deux filtres, pas un. Le premier borne les TERMES visibles (global, ou
    appartenant à une collection qu'on lit : cf. `clause_terme`). Le second borne le
    COMPTE : `frequence` était calculée sur tout le corpus, si bien que le nuage de tags
    disait le volume de travail des autres. Le compter sur les seules régions lisibles est
    du même coup plus JUSTE analytiquement — un nuage doit refléter le sous-corpus qu'on
    regarde, pas la base entière.
    """
    ou_terme, p_terme = portee.clause_terme("t.collection_id")
    ou_album, p_album = portee.clause_album("pl.album_id")
    return _rows(conn.execute(
        f"""SELECT t.id, t.label, t.couleur, t.description,
                  (SELECT COUNT(*)
                     FROM annotation_tags at
                     JOIN annotations an ON an.id = at.annotation_id
                     JOIN regions r      ON r.id = an.region_id
                     JOIN planches pl    ON pl.id = r.planche_id
                    WHERE at.tag_id = t.id AND {ou_album}) AS frequence
           FROM tags t
           WHERE {ou_terme}
           ORDER BY frequence DESC, t.label""", [*p_album, *p_terme]
    ))


@app.post("/api/tags", status_code=201)
def create_tag(tag: TagIn, conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    """AUTH-2 — enrichir le vocabulaire suppose de pouvoir écrire QUELQUE PART. Le tag
    créé reste global (`collection_id` NULL, comme avant) : c'est le comportement
    historique, et le rattacher d'office à une collection demanderait de choisir laquelle,
    question sans réponse quand on écrit dans plusieurs. Sans cette garde, une personne en
    lecture seule pourrait polluer un vocabulaire que tout le monde partage."""
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Créer un terme du vocabulaire demande un droit "
                                 "d'écriture sur au moins une collection.")
    label = _norm_tag(tag.label)
    if not label:
        raise HTTPException(422, "Label de tag vide")
    conn.execute(
        """INSERT INTO tags (label, couleur, description) VALUES (?, ?, ?)
           ON CONFLICT(label) DO UPDATE SET
               couleur = COALESCE(excluded.couleur, tags.couleur),
               description = COALESCE(excluded.description, tags.description)""",
        (label, tag.couleur, tag.description),
    )
    conn.commit()
    return _row(conn.execute("SELECT * FROM tags WHERE label = ?", (label,)))


# =========================================================================== #
# Contributions & vocabulaire de rôles (N0, v15) — paternité Zotero-like
# =========================================================================== #
_CONTRIB_SQL = ("SELECT c.id, c.nom, c.rang, c.role_id, r.label AS role, "
                "r.bucket, r.marc FROM contribution c "
                "LEFT JOIN contribution_role r ON r.id = c.role_id WHERE c.id = ?")


def _album_existe(conn, portee: autorisation.Portee, album_id, *, ecriture=False):
    """Existence + VISIBILITÉ. Le nom reste, mais depuis AUTH-2 « existe » veut dire
    « existe pour cet appelant » — un album hors portée est introuvable, pas interdit."""
    _get_album(conn, portee, album_id, ecriture=ecriture)


def _role_id(conn, label):
    """Résout un label de rôle → id, en le CRÉANT au besoin (vocabulaire contrôlé-ouvert,
    bucket défaut 'contributor'). None si label vide."""
    label = (label or "").strip()
    if not label:
        return None
    conn.execute("INSERT OR IGNORE INTO contribution_role (label) VALUES (?)", (label,))
    return conn.execute(
        "SELECT id FROM contribution_role WHERE label = ?", (label,)).fetchone()["id"]


@app.get("/api/contribution-roles")
def list_contribution_roles(conn: sqlite3.Connection = Depends(db),
                            portee: autorisation.Portee = Depends(portee_courante)):
    """Vocabulaire de rôles (avec fréquence d'emploi), pour la datalist de saisie.

    AUTH-2 — les LABELS restent visibles de tous : ce vocabulaire est curé depuis les MARC
    Relators (« scénariste », « coloriste »…), il ne dit rien du corpus. La `frequence`,
    elle, compte des contributions d'albums : elle est donc filtrée, sinon elle trahirait
    le volume de catalogage des autres."""
    ou, params = portee.clause_album("c.album_id")
    return _rows(conn.execute(
        f"""SELECT r.id, r.label, r.bucket, r.marc,
                  (SELECT COUNT(*) FROM contribution c
                    WHERE c.role_id = r.id AND {ou}) AS frequence
           FROM contribution_role r
           ORDER BY frequence DESC, r.label""", params))


@app.post("/api/contribution-roles", status_code=201)
def create_contribution_role(role: ContributionRoleIn,
                             conn: sqlite3.Connection = Depends(db),
                             portee: autorisation.Portee = Depends(portee_courante)):
    """AUTH-2 — même garde que les tags et les domaines : enrichir un vocabulaire que tout
    le monde partage suppose de pouvoir écrire quelque part."""
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Créer un rôle demande un droit d'écriture sur au moins "
                                 "une collection.")
    label = role.label.strip()
    if not label:
        raise HTTPException(422, "Label de rôle vide")
    # bucket None si non/ mal fourni → défaut 'contributor' à la CRÉATION seulement ;
    # sur conflit, on ne clobbe PAS un bucket existant (COALESCE), symétrique de `marc`.
    bucket = role.bucket if role.bucket in ("creator", "contributor") else None
    conn.execute(
        """INSERT INTO contribution_role (label, bucket, marc)
           VALUES (?, COALESCE(?, 'contributor'), ?)
           ON CONFLICT(label) DO UPDATE SET
               bucket = COALESCE(?, contribution_role.bucket),
               marc = COALESCE(excluded.marc, contribution_role.marc)""",
        (label, bucket, role.marc, bucket))
    conn.commit()
    return _row(conn.execute("SELECT * FROM contribution_role WHERE label = ?", (label,)))


@app.get("/api/albums/{album_id}/contributions")
def list_contributions(album_id: int, conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    _album_existe(conn, portee, album_id)
    return contributions_album(conn, album_id)


@app.post("/api/albums/{album_id}/contributions", status_code=201)
def add_contribution(album_id: int, contrib: ContributionIn,
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    _album_existe(conn, portee, album_id, ecriture=True)
    nom = contrib.nom.strip()
    if not nom:
        raise HTTPException(422, "Nom de contributeur vide")
    role_id = _role_id(conn, contrib.role)
    rang = conn.execute("SELECT COALESCE(MAX(rang), 0) + 1 AS n FROM contribution "
                        "WHERE album_id = ?", (album_id,)).fetchone()["n"]
    cur = conn.execute(
        "INSERT INTO contribution (album_id, nom, role_id, rang) VALUES (?, ?, ?, ?)",
        (album_id, nom, role_id, rang))
    conn.commit()
    return _row(conn.execute(_CONTRIB_SQL, (cur.lastrowid,)))


@app.delete("/api/contributions/{contribution_id}", status_code=204)
def delete_contribution(contribution_id: int, conn: sqlite3.Connection = Depends(db),
                        portee: autorisation.Portee = Depends(portee_courante)):
    """AUTH-2 — une contribution est la paternité d'un ALBUM : elle s'autorise par lui.
    La route ne recevant que l'id de la contribution, on remonte à son album."""
    ou, params = portee.clause_album("c.album_id", ecriture=True)
    if conn.execute(f"SELECT 1 FROM contribution c WHERE c.id = ? AND {ou}",
                    (contribution_id, *params)).fetchone() is None:
        raise HTTPException(404, f"Contribution {contribution_id} introuvable")
    conn.execute("DELETE FROM contribution WHERE id = ?", (contribution_id,))
    conn.commit()
    return Response(status_code=204)


# =========================================================================== #
# Personnages & attribution (ANN-2) — entité canonique + lien locuteur
# =========================================================================== #
def _clause_personnage(portee: autorisation.Portee) -> tuple[str, list]:
    """Visibilité d'un personnage (`p.id`), DÉRIVÉE de ses apparitions.  AUTH-2.

    `personnages` est un registre posé à côté du corpus : la table ne porte aucune
    collection, et lui en ajouter une reviendrait à demander, à la création, à quelle
    collection appartient un personnage — question sans bonne réponse pour une série qui
    traverse plusieurs albums. La portée se dérive donc de l'usage : on voit un personnage
    qui apparaît quelque part où l'on peut lire.

    Avec une exception nécessaire : le personnage qui n'apparaît NULLE PART reste visible.
    Sans elle, le geste courant — créer le personnage, puis lui attribuer une bulle —
    serait cassé, l'entité disparaissant à l'instant même de sa création, y compris pour
    la personne qui vient de la créer.

    Ce n'est pas une mesure de confidentialité : quiconque accède à l'instance peut déjà
    télécharger la base entière (décision du 2026-08-27, cf. docs/hebergement-securite.md
    §6). C'est une mesure d'USAGE — sans elle, l'autocomplétion de locuteur grossit avec
    l'instance entière au lieu de rester à la taille de l'étude en cours.
    """
    ou, pp = portee.clause_album("pl.album_id")
    if ou == "1":
        return "1", []
    apparait = (
        "EXISTS (SELECT 1 FROM {table} x "
        "          JOIN regions r   ON r.id = x.region_id "
        "          JOIN planches pl ON pl.id = r.planche_id "
        f"        WHERE x.personnage_id = p.id AND {ou})")
    jamais = ("NOT EXISTS (SELECT 1 FROM bulle_locuteur b WHERE b.personnage_id = p.id) "
              "AND NOT EXISTS (SELECT 1 FROM personnage_presence q "
              "                WHERE q.personnage_id = p.id)")
    return (f"(({jamais}) "
            f" OR {apparait.format(table='bulle_locuteur')} "
            f" OR {apparait.format(table='personnage_presence')})",
            [*pp, *pp])


def _get_personnage(conn, portee: autorisation.Portee, personnage_id, *,
                    ecriture: bool = False):
    """Personnage VISIBLE (404 sinon) et, si `ecriture`, modifiable.

    Un personnage n'appartient à aucune collection (sa portée se DÉRIVE de ses
    apparitions) : il n'y a donc pas de collection sur laquelle vérifier le droit
    d'écrire. La règle est celle du vocabulaire global — écrire quelque part suffit,
    personne ne possède le registre."""
    ou, params = _clause_personnage(portee)
    p = _row(conn.execute(
        f"SELECT p.* FROM personnages p WHERE p.id = ? AND {ou}",
        (personnage_id, *params)))
    if p is None:
        raise HTTPException(404, f"Personnage {personnage_id} introuvable")
    if ecriture and not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Le registre des personnages est en lecture seule "
                                 "pour vous.")
    return p


def _locuteur_for(conn, region_id):
    """Locuteur attribué à une bulle (ou None) → {locuteur: {id, nom, serie} | None}."""
    return {"locuteur": _row(conn.execute(
        "SELECT p.id, p.nom, p.serie FROM bulle_locuteur bl "
        "JOIN personnages p ON p.id = bl.personnage_id WHERE bl.region_id = ?", (region_id,)))}


def _personnage_for(conn, region_id):
    """Personnage MONTRÉ dans une boîte (ou None) → {personnage: {id, nom, serie} | None}.
    Miroir de _locuteur_for, côté image (§14, brique (a))."""
    return {"personnage": _row(conn.execute(
        "SELECT p.id, p.nom, p.serie FROM personnage_presence pp "
        "JOIN personnages p ON p.id = pp.personnage_id WHERE pp.region_id = ?", (region_id,)))}


@app.get("/api/personnages")
def list_personnages(q: Optional[str] = None, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Registre des personnages + nombre de bulles attribuées.
    `q` filtre par nom (autocomplétion à la saisie / canonicalisation à la volée).

    AUTH-2 — la portée d'un personnage se DÉRIVE de ses apparitions (cf.
    `_clause_personnage`), et `nb_bulles` ne compte que les bulles lisibles : un compteur
    global dirait le volume de travail des autres, et fausserait la lecture du registre."""
    ou, params = _clause_personnage(portee)
    ou_album, p_album = portee.clause_album("pl.album_id")
    rows = _rows(conn.execute(
        f"SELECT p.id, p.nom, p.serie, p.notes, "
        f"       (SELECT COUNT(*) FROM bulle_locuteur bl "
        f"          JOIN regions r   ON r.id = bl.region_id "
        f"          JOIN planches pl ON pl.id = r.planche_id "
        f"        WHERE bl.personnage_id = p.id AND {ou_album}) AS nb_bulles "
        f"FROM personnages p WHERE {ou} ORDER BY p.nom, p.serie",
        [*p_album, *params]))
    if q and q.strip():
        cible = _sans_accents(q)   # autocomplétion insensible à la casse ET aux accents
        rows = [r for r in rows if cible in _sans_accents(r["nom"])]
    return rows


@app.post("/api/personnages", status_code=201)
def create_personnage(payload: PersonnageIn, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """AUTH-2 — le registre des personnages n'appartient à aucune collection : y écrire
    demande le droit d'écrire quelque part, comme pour le vocabulaire global."""
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Le registre des personnages est en lecture seule "
                                 "pour vous.")
    nom = (payload.nom or "").strip()
    if not nom:
        raise HTTPException(422, "Nom de personnage vide")
    pid = conn.execute(
        "INSERT INTO personnages (nom, serie, notes) VALUES (?, ?, ?)",
        (nom, (payload.serie or "").strip() or None, payload.notes)).lastrowid
    conn.commit()
    return _get_personnage(conn, portee, pid)


@app.put("/api/personnages/{personnage_id}")
def update_personnage(personnage_id: int, payload: PersonnageUpdate,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    sets, params = [], []
    if payload.nom is not None:
        nom = payload.nom.strip()
        if not nom:
            raise HTTPException(422, "Nom de personnage vide")
        sets.append("nom = ?"); params.append(nom)
    if payload.serie is not None:
        sets.append("serie = ?"); params.append(payload.serie.strip() or None)
    if payload.notes is not None:
        sets.append("notes = ?"); params.append(payload.notes)
    if sets:
        params.append(personnage_id)
        conn.execute(f"UPDATE personnages SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
    return _get_personnage(conn, portee, personnage_id, ecriture=True)


@app.delete("/api/personnages/{personnage_id}", status_code=204)
def delete_personnage(personnage_id: int, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    conn.execute("DELETE FROM personnages WHERE id = ?", (personnage_id,))   # CASCADE : détache liens/attributs
    conn.commit()


@app.post("/api/personnages/{personnage_id}/fusion")
def fusionner_personnage(personnage_id: int, payload: FusionIn,
                         conn: sqlite3.Connection = Depends(db),
                         portee: autorisation.Portee = Depends(portee_courante)):
    """Fusionne `personnage_id` (doublon) DANS `cible_id` (canonique) : réaffecte les
    liens locuteur et les attributs, puis supprime le doublon. Idempotent sur les
    affectations (INSERT OR IGNORE). Soupape du modèle mentions→entités (curation)."""
    if payload.cible_id == personnage_id:
        raise HTTPException(422, "Un personnage ne peut être fusionné avec lui-même")
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    _get_personnage(conn, portee, payload.cible_id, ecriture=True)
    # locuteur : une bulle a au plus un locuteur (region_id PK) → réaffectation directe.
    conn.execute("UPDATE bulle_locuteur SET personnage_id = ? WHERE personnage_id = ?",
                 (payload.cible_id, personnage_id))
    # attributs : éviter le doublon (personnage_id, valeur_id) → OR IGNORE ; le reste du
    # doublon part au DELETE (CASCADE).
    conn.execute("INSERT OR IGNORE INTO personnage_attribut (personnage_id, valeur_id) "
                 "SELECT ?, valeur_id FROM personnage_attribut WHERE personnage_id = ?",
                 (payload.cible_id, personnage_id))
    # alignements d'autorité (A5) : mêmes règles — dédupliqués par (personnage_id, uri).
    conn.execute("INSERT OR IGNORE INTO personnage_alignement (personnage_id, source, uri) "
                 "SELECT ?, source, uri FROM personnage_alignement WHERE personnage_id = ?",
                 (payload.cible_id, personnage_id))
    conn.execute("DELETE FROM personnages WHERE id = ?", (personnage_id,))
    conn.commit()
    return _get_personnage(conn, portee, payload.cible_id, ecriture=True)


# --- Alignement d'autorité (A5, N6) : personnage → référentiel externe (skos:exactMatch) ---
_AUTORITES = {                       # hôte → étiquette de source (auto-détection)
    "wikidata.org": "wikidata", "viaf.org": "viaf", "idref.fr": "idref",
    "isni.org": "isni", "data.bnf.fr": "bnf", "id.loc.gov": "loc", "d-nb.info": "gnd",
}


def _source_autorite(uri: str) -> Optional[str]:
    """Devine l'autorité depuis l'hôte de l'URI (Wikidata/VIAF/IdRef…) ; None si inconnu
    (l'alignement reste valide, `source` non renseignée)."""
    from urllib.parse import urlparse
    host = (urlparse(uri).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    for cle, src in _AUTORITES.items():
        if host == cle or host.endswith("." + cle):
            return src
    return None


def _alignements_de(conn, personnage_id):
    return _rows(conn.execute(
        "SELECT id, source, uri, date_creation FROM personnage_alignement "
        "WHERE personnage_id = ? ORDER BY id", (personnage_id,)))


@app.get("/api/personnages/{personnage_id}/alignements")
def list_alignements(personnage_id: int, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Alignements d'autorité d'un personnage (skos:exactMatch vers Wikidata/VIAF/IdRef…)."""
    _get_personnage(conn, portee, personnage_id)
    return _alignements_de(conn, personnage_id)


@app.post("/api/personnages/{personnage_id}/alignements", status_code=201)
def add_alignement(personnage_id: int, payload: AlignementIn,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Aligne un personnage sur une URI d'autorité. `source` auto-détectée depuis l'URI si
    absente. Idempotent : re-poster la même URI met à jour la source, sans doublon."""
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    uri = (payload.uri or "").strip()
    if not (uri.startswith("http://") or uri.startswith("https://")):
        raise HTTPException(422, "L'alignement doit être une URI http(s).")
    source = (payload.source or "").strip() or _source_autorite(uri)
    conn.execute(
        "INSERT INTO personnage_alignement (personnage_id, source, uri) VALUES (?, ?, ?) "
        "ON CONFLICT(personnage_id, uri) DO UPDATE SET source = excluded.source",
        (personnage_id, source, uri))
    conn.commit()
    return _row(conn.execute(
        "SELECT id, source, uri, date_creation FROM personnage_alignement "
        "WHERE personnage_id = ? AND uri = ?", (personnage_id, uri)))


@app.delete("/api/personnages/{personnage_id}/alignements/{alignement_id}", status_code=204)
def delete_alignement(personnage_id: int, alignement_id: int,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    cur = conn.execute("DELETE FROM personnage_alignement WHERE id = ? AND personnage_id = ?",
                       (alignement_id, personnage_id))
    if not cur.rowcount:
        raise HTTPException(404, f"Alignement {alignement_id} introuvable")
    conn.commit()


@app.get("/api/regions/{region_id}/locuteur")
def get_locuteur(region_id: int, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id)
    return _locuteur_for(conn, region_id)


@app.put("/api/regions/{region_id}/locuteur")
def set_locuteur(region_id: int, payload: LocuteurIn, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    _get_personnage(conn, portee, payload.personnage_id)
    ancien = conn.execute("SELECT personnage_id FROM bulle_locuteur WHERE region_id = ?",
                          (region_id,)).fetchone()
    conn.execute("INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?) "
                 "ON CONFLICT(region_id) DO UPDATE SET personnage_id = excluded.personnage_id",
                 (region_id, payload.personnage_id))
    journal.journaliser(conn, "lien", "bulle_locuteur", region_id,
                        avant=({"personnage_id": ancien["personnage_id"]} if ancien else None),
                        apres={"personnage_id": payload.personnage_id})
    conn.commit()
    return _locuteur_for(conn, region_id)


@app.delete("/api/regions/{region_id}/locuteur", status_code=204)
def clear_locuteur(region_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    ancien = conn.execute("SELECT personnage_id FROM bulle_locuteur WHERE region_id = ?",
                          (region_id,)).fetchone()
    conn.execute("DELETE FROM bulle_locuteur WHERE region_id = ?", (region_id,))
    if ancien:
        journal.journaliser(conn, "delien", "bulle_locuteur", region_id,
                            avant={"personnage_id": ancien["personnage_id"]})
    conn.commit()


# --- Présence : quelle entité est MONTRÉE dans une boîte personnage (§14, brique (a)).
#     Strict miroir du locuteur, mais pour l'image — la boîte porte l'identité, et le
#     profil de l'entité devient atteignable depuis l'image (muets compris). La cohérence
#     de type (region.type = 'personnage') est assurée côté UI, comme pour le locuteur.
@app.get("/api/regions/{region_id}/personnage")
def get_presence(region_id: int, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id)
    return _personnage_for(conn, region_id)


@app.put("/api/regions/{region_id}/personnage")
def set_presence(region_id: int, payload: PresenceIn, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    _get_personnage(conn, portee, payload.personnage_id)
    ancien = conn.execute("SELECT personnage_id FROM personnage_presence WHERE region_id = ?",
                          (region_id,)).fetchone()
    conn.execute("INSERT INTO personnage_presence (region_id, personnage_id) VALUES (?, ?) "
                 "ON CONFLICT(region_id) DO UPDATE SET personnage_id = excluded.personnage_id",
                 (region_id, payload.personnage_id))
    journal.journaliser(conn, "lien", "personnage_presence", region_id,
                        avant=({"personnage_id": ancien["personnage_id"]} if ancien else None),
                        apres={"personnage_id": payload.personnage_id})
    conn.commit()
    return _personnage_for(conn, region_id)


@app.delete("/api/regions/{region_id}/personnage", status_code=204)
def clear_presence(region_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    ancien = conn.execute("SELECT personnage_id FROM personnage_presence WHERE region_id = ?",
                          (region_id,)).fetchone()
    conn.execute("DELETE FROM personnage_presence WHERE region_id = ?", (region_id,))
    if ancien:
        journal.journaliser(conn, "delien", "personnage_presence", region_id,
                            avant={"personnage_id": ancien["personnage_id"]})
    conn.commit()


# --- Annulation (undo, D1) : rejoue l'INVERSE de la dernière action depuis le journal A3 ---
def _agent_undo(portee: autorisation.Portee):
    """Quels actes cette requête peut-elle annuler ?  AUTH-2.

    En mono-poste (portée totale ET aucune identité), on ne filtre pas : c'est le
    comportement d'avant AUTH-2, et il n'y a qu'une personne devant la machine. Dès qu'il
    y a une identité, chacun n'annule que ses propres actes — administrateur compris :
    Ctrl+Z est un geste personnel, pas un outil de modération.
    """
    if portee.tout and portee.utilisateur is None:
        return undo.TOUS
    return portee.utilisateur


@app.get("/api/undo/prochain")
def undo_prochain(conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Aperçu : ce que ferait la prochaine annulation (ou `null` s'il n'y a rien à annuler)."""
    return undo.apercu(conn, agent=_agent_undo(portee))


@app.post("/api/undo")
def undo_dernier(conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Annule la dernière action d'annotation (Ctrl+Z). Renvoie un descripteur de l'acte
    annulé (description + planche/région touchée) pour le rafraîchissement de l'UI, ou 404
    s'il n'y a rien à annuler. Inversion + journal `annulation` atomiques (rollback si échec)."""
    # Annuler REJOUE une écriture : il faut en avoir le droit quelque part. Le filtre par
    # agent ne suffit pas — quelqu'un rétrogradé en lecture seule pourrait sinon défaire
    # ses anciens actes. Résiduel assumé : ce plancher ne dit pas SUR QUELLE collection
    # portait l'acte (la cible d'une suppression n'existe plus), donc un droit d'écriture
    # ailleurs suffit encore. Cf. docs/undo.md.
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Annuler demande un droit d'écriture.")
    try:
        res = undo.annuler(conn, agent=_agent_undo(portee))
    except undo.UndoImpossible as exc:
        raise HTTPException(409, f"Annulation impossible : {exc}")
    if res is None:
        raise HTTPException(404, "Rien à annuler.")
    conn.commit()
    return res


# --- DOMAINES (piste B) : champ analytique émergent qui REGROUPE des dimensions (émotions,
#     représentation…). Orthogonal à `cible`. Même patron contrôlé-ouvert + lexique SKOS que
#     les dimensions. Cf. docs/domaines.md.
def _get_domaine(conn, portee: autorisation.Portee, dom_id, *, ecriture: bool = False):
    """Terme du vocabulaire, VISIBLE (404 sinon) et, si `ecriture`, MODIFIABLE.

    Le refus d'écriture est un 403 et non un 404, contrairement aux données : le
    terme vient d'être listé, prétendre qu'il n'existe pas serait incohérent — et
    le refus ne parle que des droits de l'appelant, il ne fuit rien.
    """
    ou, params = portee.clause_terme("t.collection_id")
    d = _row(conn.execute(
        f"SELECT t.* FROM domaine t WHERE t.id = ? AND {ou}", (dom_id, *params)))
    if d is None:
        raise HTTPException(404, f"Domaine {dom_id} introuvable")
    if ecriture and not portee.peut_ecrire_terme(d.get("collection_id")):
        raise HTTPException(403, "Ce terme du vocabulaire est en lecture seule "
                                 "pour vous.")
    return d


@app.get("/api/domaines")
def list_domaines(conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Domaines + nombre de dimensions rattachées + couche lexique (pour l'organisation/l'analyse).

    AUTH-2 — un domaine est un terme du vocabulaire : visible s'il est global
    (`collection_id` NULL) ou s'il appartient à une collection qu'on lit. Le compte de
    dimensions suit la même règle, sinon il dirait combien d'axes existent ailleurs."""
    ou, params = portee.clause_terme("d.collection_id")
    ou_dim, p_dim = portee.clause_terme("x.collection_id")
    return _rows(conn.execute(
        f"SELECT d.id, d.nom, d.definition, d.note_portee, d.etat, d.collection_id, "
        f"       (SELECT COUNT(*) FROM attribut_dimension x "
        f"         WHERE x.domaine_id = d.id AND {ou_dim}) AS nb_dimensions "
        f"FROM domaine d WHERE {ou} ORDER BY d.nom", [*p_dim, *params]))


@app.post("/api/domaines", status_code=201)
def create_domaine(payload: DomaineIn, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """AUTH-2 — même garde que la création de tag : enrichir un vocabulaire partagé
    suppose de pouvoir écrire quelque part."""
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Créer un domaine demande un droit d'écriture sur au "
                                 "moins une collection.")
    nom = _norm_tag(payload.nom)
    if not nom:
        raise HTTPException(422, "Nom de domaine vide")
    conn.execute("INSERT INTO domaine (nom) VALUES (?) ON CONFLICT(nom) DO NOTHING", (nom,))
    conn.commit()
    return _row(conn.execute("SELECT * FROM domaine WHERE nom = ?", (nom,)))


@app.patch("/api/domaines/{dom_id}")
def rename_domaine(dom_id: int, payload: DomaineIn, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Renomme un domaine (préserve son regroupement de dimensions, contrairement à un
    supprimer/recréer). Le nom reste normalisé et UNIQUE."""
    _get_domaine(conn, portee, dom_id, ecriture=True)
    nom = _norm_tag(payload.nom)
    if not nom:
        raise HTTPException(422, "Nom de domaine vide")
    if conn.execute("SELECT 1 FROM domaine WHERE nom = ? AND id <> ?", (nom, dom_id)).fetchone():
        raise HTTPException(409, f"Domaine « {nom} » déjà existant.")
    conn.execute("UPDATE domaine SET nom = ? WHERE id = ?", (nom, dom_id))
    conn.commit()
    return _row(conn.execute("SELECT * FROM domaine WHERE id = ?", (dom_id,)))


@app.delete("/api/domaines/{dom_id}", status_code=204)
def delete_domaine(dom_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime un domaine. Ses dimensions ne sont PAS détruites : `domaine_id` repasse à NULL
    (ON DELETE SET NULL) — elles redeviennent « hors domaine » (soupape *promotion*)."""
    _get_domaine(conn, portee, dom_id, ecriture=True)
    conn.execute("DELETE FROM domaine WHERE id = ?", (dom_id,))
    conn.commit()


@app.patch("/api/domaines/{dom_id}/lexique")
def patch_domaine_lexique(dom_id: int, payload: LexiqueIn, conn: sqlite3.Connection = Depends(db),
                          portee: autorisation.Portee = Depends(portee_courante)):
    """Documente un domaine (même couche SKOS que dimensions/valeurs/tags)."""
    _get_domaine(conn, portee, dom_id, ecriture=True)
    _patch_lexique(conn, "domaine", dom_id, payload, portee)
    return _row(conn.execute("SELECT * FROM domaine WHERE id = ?", (dom_id,)))


# --- Attributs FACETTÉS & ÉMERGENTS : dimensions (axes) / valeurs canoniques /
#     affectations. Vocabulaire NON figé — créé au fil de l'eau. Valeurs et noms de
#     dimension normalisés (comme les tags) → agrégeables. Cf. docs/personnages-et-attribution.md.
def _get_dimension(conn, portee: autorisation.Portee, dim_id, *, ecriture: bool = False):
    """Terme du vocabulaire, VISIBLE (404 sinon) et, si `ecriture`, MODIFIABLE.

    Le refus d'écriture est un 403 et non un 404, contrairement aux données : le
    terme vient d'être listé, prétendre qu'il n'existe pas serait incohérent — et
    le refus ne parle que des droits de l'appelant, il ne fuit rien.
    """
    ou, params = portee.clause_terme("t.collection_id")
    d = _row(conn.execute(
        f"SELECT t.* FROM attribut_dimension t WHERE t.id = ? AND {ou}", (dim_id, *params)))
    if d is None:
        raise HTTPException(404, f"Dimension {dim_id} introuvable")
    if ecriture and not portee.peut_ecrire_terme(d.get("collection_id")):
        raise HTTPException(403, "Ce terme du vocabulaire est en lecture seule "
                                 "pour vous.")
    return d


def _get_valeur(conn, portee: autorisation.Portee, val_id, *, ecriture: bool = False):
    """Terme du vocabulaire, VISIBLE (404 sinon) et, si `ecriture`, MODIFIABLE.

    Le refus d'écriture est un 403 et non un 404, contrairement aux données : le
    terme vient d'être listé, prétendre qu'il n'existe pas serait incohérent — et
    le refus ne parle que des droits de l'appelant, il ne fuit rien.
    """
    ou, params = portee.clause_terme("t.collection_id")
    v = _row(conn.execute(
        f"SELECT t.* FROM attribut_valeur t WHERE t.id = ? AND {ou}", (val_id, *params)))
    if v is None:
        raise HTTPException(404, f"Valeur d'attribut {val_id} introuvable")
    if ecriture and not portee.peut_ecrire_terme(v.get("collection_id")):
        raise HTTPException(403, "Ce terme du vocabulaire est en lecture seule "
                                 "pour vous.")
    return v


def _attributs_de(conn, portee, table, col, oid):
    """Valeurs (avec leur dimension) affectées à une cible (personnage | région).

    AUTH-2 — les valeurs sont filtrées comme des TERMES : sans cela, un objet partagé
    (typiquement un personnage, qui traverse les albums) exposerait le vocabulaire privé
    d'une autre étude — sa grille d'analyse, pas seulement un mot. Écart trouvé en
    relisant : `GET /api/attributs/valeurs` masquait déjà ces termes, mais on les
    retrouvait ici par la bande.

    Conséquence assumée : la liste d'attributs d'un objet peut être PARTIELLE. C'est le
    bon compromis — un objet peut légitimement porter les annotations d'études auxquelles
    on ne participe pas, et il vaut mieux ne pas les montrer que de montrer un vocabulaire
    qu'on ne peut ni comprendre ni situer.

    La DIMENSION est filtrée à son tour (relecture du 2026-08-28). Les routes de création
    ne posaient aucun `collection_id` : toute base antérieure à v24 contient des valeurs
    globales sous des axes privés, et c'est le NOM de l'axe qui fuit, pas le mot. Les
    créations héritent désormais de leur parent, et la migration v24 recolle l'existant ;
    ce filtre-ci reste la ceinture.
    """
    ou, params = portee.clause_terme("v.collection_id")
    ou_dim, p_dim = portee.clause_terme("d.collection_id")
    return _rows(conn.execute(
        f"SELECT v.id AS valeur_id, v.valeur, d.id AS dimension_id, d.nom AS dimension, d.cible "
        f"FROM {table} x JOIN attribut_valeur v ON v.id = x.valeur_id "
        f"JOIN attribut_dimension d ON d.id = v.dimension_id "
        f"WHERE x.{col} = ? AND {ou} AND {ou_dim} ORDER BY d.nom, v.valeur",
        (oid, *params, *p_dim)))


@app.get("/api/attributs/dimensions")
def list_dimensions(cible: Optional[str] = None, conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Dimensions (axes émergents) + nombre de valeurs + domaine de rattachement (v20).
    `cible` filtre 'personnage' | 'case'.

    AUTH-2 — mêmes règles que les domaines : le terme est visible s'il est global ou
    local à une collection qu'on lit, et le compte de valeurs est filtré pareillement.
    Le NOM du domaine de rattachement est un terme lui aussi : il se filtre, sinon une
    dimension globale nommerait le domaine privé auquel on l'a rattachée. Il revient donc
    à `null` quand le domaine n'est pas visible — la dimension, elle, reste."""
    ou, p_dim = portee.clause_terme("d.collection_id")
    ou_val, p_val = portee.clause_terme("v.collection_id")
    ou_dom, p_dom = portee.clause_terme("dom.collection_id")
    sql = (f"SELECT d.id, d.cible, d.nom, d.domaine_id, "
           f"       (SELECT nom FROM domaine dom WHERE dom.id = d.domaine_id "
           f"          AND {ou_dom}) AS domaine, "
           f"       (SELECT COUNT(*) FROM attribut_valeur v "
           f"         WHERE v.dimension_id = d.id AND {ou_val}) AS nb_valeurs "
           f"FROM attribut_dimension d WHERE {ou} ")
    params = [*p_dom, *p_val, *p_dim]
    if cible:
        sql += "AND d.cible = ? "
        params.append(cible)
    sql += "ORDER BY d.cible, d.nom"
    return _rows(conn.execute(sql, params))


@app.post("/api/attributs/dimensions", status_code=201)
def create_dimension(payload: DimensionIn, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Créer une dimension demande un droit d'écriture sur au "
                                 "moins une collection.")
    if payload.cible not in CIBLES_ATTRIBUT:
        raise HTTPException(422, f"Cible invalide : {payload.cible} (personnage | case).")
    nom = _norm_tag(payload.nom)
    if not nom:
        raise HTTPException(422, "Nom de dimension vide")
    # AUTH-2 — la dimension HÉRITE de la portée de son domaine. Un terme ne peut pas être
    # plus global que celui dont il dépend : une dimension globale rattachée à un domaine
    # privé se montrait à tout le monde, et nommait le domaine au passage. Sans domaine,
    # la dimension reste globale, comme avant.
    cid = None
    if payload.domaine_id is not None:
        dom = _get_domaine(conn, portee, payload.domaine_id, ecriture=True)    # 404 si le domaine n'existe pas
        cid = dom["collection_id"]
    conn.execute("INSERT INTO attribut_dimension (cible, nom, domaine_id, collection_id) "
                 "VALUES (?, ?, ?, ?) ON CONFLICT(cible, nom) DO NOTHING",
                 (payload.cible, nom, payload.domaine_id, cid))
    conn.commit()
    return _row(conn.execute("SELECT * FROM attribut_dimension WHERE cible = ? AND nom = ?",
                             (payload.cible, nom)))


@app.patch("/api/attributs/dimensions/{dim_id}/domaine")
def patch_dimension_domaine(dim_id: int, payload: DimensionDomaineIn,
                            conn: sqlite3.Connection = Depends(db),
                            portee: autorisation.Portee = Depends(portee_courante)):
    """Rattache une dimension à un domaine (ou l'en détache avec `domaine_id: null`)."""
    _get_dimension(conn, portee, dim_id, ecriture=True)
    if payload.domaine_id is not None:
        _get_domaine(conn, portee, payload.domaine_id, ecriture=True)
    conn.execute("UPDATE attribut_dimension SET domaine_id = ? WHERE id = ?",
                 (payload.domaine_id, dim_id))
    conn.commit()
    return _row(conn.execute("SELECT * FROM attribut_dimension WHERE id = ?", (dim_id,)))


@app.delete("/api/attributs/dimensions/{dim_id}", status_code=204)
def delete_dimension(dim_id: int, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    _get_dimension(conn, portee, dim_id, ecriture=True)
    conn.execute("DELETE FROM attribut_dimension WHERE id = ?", (dim_id,))   # CASCADE : valeurs + affectations
    conn.commit()


@app.get("/api/attributs/dimensions/{dim_id}/valeurs")
def list_valeurs(dim_id: int, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """AUTH-2 — `nb_usages` comptait TOUS les emplois du corpus. Il ne compte plus que
    les régions lisibles (côté case) et les personnages visibles (côté locuteur) : sinon
    la fréquence d'une valeur trahit le volume d'annotation des autres."""
    _get_dimension(conn, portee, dim_id)
    ou_terme, p_terme = portee.clause_terme("v.collection_id")
    ou_album, p_album = portee.clause_album("pl.album_id")
    ou_perso, p_perso = _clause_personnage(portee)
    return _rows(conn.execute(
        f"SELECT v.id, v.dimension_id, v.valeur, "
        f"       ((SELECT COUNT(*) FROM personnage_attribut pa JOIN personnages p "
        f"           ON p.id = pa.personnage_id "
        f"         WHERE pa.valeur_id = v.id AND {ou_perso}) "
        f"      + (SELECT COUNT(*) FROM region_attribut ra "
        f"           JOIN regions r   ON r.id = ra.region_id "
        f"           JOIN planches pl ON pl.id = r.planche_id "
        f"         WHERE ra.valeur_id = v.id AND {ou_album})) AS nb_usages "
        f"FROM attribut_valeur v WHERE v.dimension_id = ? AND {ou_terme} ORDER BY v.valeur",
        [*p_perso, *p_album, dim_id, *p_terme]))


@app.post("/api/attributs/dimensions/{dim_id}/valeurs", status_code=201)
def create_valeur(dim_id: int, payload: ValeurIn, conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    dim = _get_dimension(conn, portee, dim_id, ecriture=True)
    valeur = _norm_tag(payload.valeur)
    if not valeur:
        raise HTTPException(422, "Valeur vide")
    # AUTH-2 — même héritage qu'un cran plus haut : la valeur prend la portée de sa
    # dimension. La route ne posait aucun `collection_id`, si bien que toute valeur
    # naissait GLOBALE — y compris sous un axe d'analyse local à une étude. Le dommage
    # n'est pas le mot (« palpable » ne dit rien) mais ce qu'il traîne : les routes à plat
    # renvoient le NOM de sa dimension.
    conn.execute("INSERT INTO attribut_valeur (dimension_id, valeur, collection_id) "
                 "VALUES (?, ?, ?) ON CONFLICT(dimension_id, valeur) DO NOTHING",
                 (dim_id, valeur, dim["collection_id"]))
    conn.commit()
    return _row(conn.execute("SELECT * FROM attribut_valeur WHERE dimension_id = ? AND valeur = ?",
                             (dim_id, valeur)))


@app.delete("/api/attributs/valeurs/{val_id}", status_code=204)
def delete_valeur(val_id: int, conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    _get_valeur(conn, portee, val_id, ecriture=True)
    conn.execute("DELETE FROM attribut_valeur WHERE id = ?", (val_id,))   # CASCADE : affectations
    conn.commit()


@app.get("/api/attributs/valeurs")
def list_valeurs_plat(cible: Optional[str] = None, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Toutes les valeurs (avec leur dimension), à plat — sert les facettes d'analyse
    (évite un N+1 dimensions→valeurs). `cible` filtre 'personnage' | 'case'.

    AUTH-2 — mêmes deux filtres qu'ailleurs : les TERMES visibles, et des `nb_usages`
    comptés sur le seul sous-corpus lisible. La dimension jointe est filtrée elle aussi :
    c'est elle qui porte le nom, donc la fuite (cf. `_attributs_de`)."""
    ou_terme, p_terme = portee.clause_terme("v.collection_id")
    ou_dim, p_dim = portee.clause_terme("d.collection_id")
    ou_album, p_album = portee.clause_album("pl.album_id")
    ou_perso, p_perso = _clause_personnage(portee)
    sql = (f"SELECT v.id, v.valeur, d.id AS dimension_id, d.nom AS dimension, d.cible, "
           f"       ((SELECT COUNT(*) FROM personnage_attribut pa JOIN personnages p "
           f"           ON p.id = pa.personnage_id "
           f"         WHERE pa.valeur_id = v.id AND {ou_perso}) "
           f"      + (SELECT COUNT(*) FROM region_attribut ra "
           f"           JOIN regions r   ON r.id = ra.region_id "
           f"           JOIN planches pl ON pl.id = r.planche_id "
           f"         WHERE ra.valeur_id = v.id AND {ou_album})) AS nb_usages "
           f"FROM attribut_valeur v JOIN attribut_dimension d ON d.id = v.dimension_id "
           f"WHERE {ou_terme} AND {ou_dim} ")
    params = [*p_perso, *p_album, *p_terme, *p_dim]
    if cible:
        sql += "AND d.cible = ? "
        params.append(cible)
    sql += "ORDER BY d.cible, d.nom, v.valeur"
    return _rows(conn.execute(sql, params))


@app.put("/api/attributs/valeurs/{val_id}")
def rename_valeur(val_id: int, payload: ValeurIn, conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Renomme une valeur (curation). Conflit avec une valeur existante de la même
    dimension → 409 (utiliser la fusion à la place)."""
    v = _get_valeur(conn, portee, val_id, ecriture=True)
    valeur = _norm_tag(payload.valeur)
    if not valeur:
        raise HTTPException(422, "Valeur vide")
    if _row(conn.execute("SELECT id FROM attribut_valeur "
                         "WHERE dimension_id = ? AND valeur = ? AND id <> ?",
                         (v["dimension_id"], valeur, val_id))):
        raise HTTPException(409, "Cette valeur existe déjà dans la dimension — fusionnez-les.")
    conn.execute("UPDATE attribut_valeur SET valeur = ? WHERE id = ?", (valeur, val_id))
    conn.commit()
    return _get_valeur(conn, portee, val_id, ecriture=True)


@app.post("/api/attributs/valeurs/{val_id}/fusion")
def fusionner_valeur(val_id: int, payload: FusionIn, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Fusionne la valeur `val_id` DANS `cible_id` (même dimension) : réaffecte les
    affectations (personnages + cases) en INSERT OR IGNORE, puis supprime le doublon."""
    if payload.cible_id == val_id:
        raise HTTPException(422, "Une valeur ne peut être fusionnée avec elle-même")
    v = _get_valeur(conn, portee, val_id, ecriture=True)
    cible = _get_valeur(conn, portee, payload.cible_id, ecriture=True)
    if v["dimension_id"] != cible["dimension_id"]:
        raise HTTPException(422, "On ne fusionne que deux valeurs d'une même dimension.")
    for table, col in (("personnage_attribut", "personnage_id"), ("region_attribut", "region_id")):
        conn.execute(f"INSERT OR IGNORE INTO {table} ({col}, valeur_id) "
                     f"SELECT {col}, ? FROM {table} WHERE valeur_id = ?", (payload.cible_id, val_id))
    conn.execute("DELETE FROM attribut_valeur WHERE id = ?", (val_id,))   # CASCADE purge le reste
    conn.commit()
    return _get_valeur(conn, portee, payload.cible_id, ecriture=True)


# =========================================================================== #
# Lexique situé (A4, N7) — couche définitionnelle SKOS sur le vocabulaire émergent
# =========================================================================== #
_ETATS_LEXIQUE = ("provisoire", "defini")


# =========================================================================== #
# Figure citable (DROIT-1) — CITER n'est pas PUBLIER
#
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


@app.get("/api/figure/champs")
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


@app.post("/api/figures")
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

# =========================================================================== #
# Collections — espaces de travail (AUTH-3)
#
# Le conteneur existe depuis la v14 (unité de DÉPÔT), le cloisonnement depuis AUTH-2
# (`collection_acces`). Il manquait de quoi l'ADMINISTRER autrement qu'en SQL à la main :
# créer, partager, retirer, ranger un album. C'est tout ce chantier.
#
# Trois paliers, et le troisième est la nouveauté : lire · écrire · POSSÉDER. Écrire, c'est
# annoter ; posséder, c'est décider qui d'autre entrera. Le second ne découle pas du premier.
# =========================================================================== #
def _get_collection(conn, portee: autorisation.Portee, collection_id: int, *,
                    administrer: bool = False):
    """Collection VISIBLE (404 sinon) et, si `administrer`, qu'on a le droit de partager.

    Le refus d'administration est un **403** et non un 404 : la collection vient d'être
    listée, on connaît son nom, un « introuvable » mentirait. C'est la distinction
    qu'AUTH-2 fait déjà entre un terme (403, déjà listé) et une donnée (404, l'absence ne
    fuit rien) — ici, la collection est déjà connue de l'appelant.
    """
    c = collection_row(conn, collection_id)
    if c is None or not portee.peut_lire(collection_id):
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    if administrer and not portee.peut_administrer(collection_id):
        raise HTTPException(403, "Seul un propriétaire de cette collection peut la "
                                 "partager ou la modifier.")
    return c


def _niveau_dans(portee: autorisation.Portee, collection_id: int):
    """Le niveau de l'APPELANT sur cette collection, pour que l'UI sache quoi proposer.

    `None` hors proxy et pour l'administrateur : ils peuvent tout, mais ne « possèdent »
    rien — afficher « propriétaire » à un administrateur lui ferait croire à un lien
    personnel avec une collection qui ne lui appartient pas.
    """
    if portee.tout:
        return None
    if collection_id in portee.propriete:
        return autorisation.PROPRIETAIRE
    if collection_id in portee.ecriture:
        return autorisation.ECRITURE
    return autorisation.LECTURE if collection_id in portee.lecture else None


def _acces_de(conn, collection_id: int) -> list[dict]:
    """Les accès accordés sur une collection, propriétaires d'abord."""
    return _rows(conn.execute(
        "SELECT genre, principal, niveau, date_creation FROM collection_acces "
        "WHERE collection_id = ? "
        "ORDER BY CASE niveau WHEN 'proprietaire' THEN 0 WHEN 'ecriture' THEN 1 ELSE 2 END, "
        "         genre, principal", (collection_id,)))


def _compte_proprietaires(conn, collection_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM collection_acces WHERE collection_id = ? AND niveau = ?",
        (collection_id, autorisation.PROPRIETAIRE)).fetchone()[0]


def _refuser_nom_reserve(nom: str) -> None:
    """Le nom du repli ne se prend pas. Cf. `database.nom_reserve` pour la raison — en
    résumé : `collection_par_defaut` désigne le repli par son NOM, et se l'attribuer capture
    les albums créés sans collection explicite."""
    if nom_reserve(nom):
        raise HTTPException(
            422, f"« {nom} » est réservé à la collection de repli : les albums créés sans "
                 "collection explicite y sont rangés. Choisissez un autre nom.")


def _journaliser_acces(conn, collection_id: int, type: str, *, avant=None, apres=None):
    """Trace un changement d'ACCÈS dans le journal A3 (append-only).

    Le journal servait jusqu'ici la provenance du CORPUS — qui a annoté quoi. Un changement
    d'accès n'est pas une annotation, mais il relève de la même exigence : `peut_administrer`
    se justifie par le fait qu'un accès accordé par erreur doit rester traçable, et sans
    trace cet argument ne tenait pas. Écart relevé en relisant ma propre justification.

    Ces événements ne sont PAS annulables : `undo._TABLES` est une liste blanche, et
    `collection_acces` n'y figure pas. Défaire un partage par Ctrl+Z serait une surprise.
    """
    journal.journaliser(conn, type, "collection_acces", collection_id,
                        avant=avant, apres=apres)


@app.get("/api/collections")
def list_collections(conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Collections (espace de travail ET unité de dépôt) + nombre d'albums + le niveau de
    l'appelant. Sert le menu « portée » du lexique, le sélecteur de la Bibliothèque et
    l'écran Collections.

    AUTH-2 — on ne liste que les siennes. C'est la route la plus directement révélatrice
    du dépôt : les noms de collections DISENT quelles études existent, et le menu de portée
    du lexique proposerait sinon de ranger un terme chez quelqu'un d'autre."""
    vues = collections(conn) if portee.tout else [
        c for c in collections(conn) if c["id"] in portee.lecture]
    for c in vues:
        c["mon_niveau"] = _niveau_dans(portee, c["id"])
        c["administrable"] = portee.peut_administrer(c["id"])
        # DROIT-1 — l'état de la date d'embargo, DÉRIVÉ ici comme il l'est à la sortie :
        # `tools/iiif_manifest.py` lit la MÊME fonction, sans quoi l'écran et l'export
        # finiraient par ne plus dire la même chose du même champ. Un embargo échu que
        # personne ne remarque garde un corpus fermé par inertie ; l'outil ne le lève pas
        # tout seul (une date qui passe ne dit pas que les droits sont acquis), mais il
        # cesse de se taire.
        c["embargo"] = etat_embargo(c)
    return vues


@app.post("/api/collections", status_code=201)
def create_collection(payload: CollectionIn, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Crée une collection ; son créateur en devient PROPRIÉTAIRE.

    AUTH-3 — cette route remplace `tools/gerer_collections.py creer`, qui exigeait un accès
    shell : ouvrir un espace de travail ne peut pas demander d'être administrateur système.
    Aucun droit préalable n'est requis, et c'est délibéré — refuser la création à qui n'a
    encore rien rendrait l'application inutilisable au premier jour de chacun.

    Hors proxy (mono-poste), il n'y a PERSONNE à inscrire comme propriétaire : la collection
    naît sans accès, et la portée totale rend la question sans objet. Idem pour un
    administrateur, qui possède déjà tout : lui inventer un lien personnel avec chaque
    collection qu'il crée fausserait la notion — s'il veut la posséder, il se l'accorde.

    « Aucun droit préalable » ne veut PAS dire « aucune identité », et la première version
    confondait les deux : derrière le proxy, une requête sans en-tête d'identité — donc qui
    n'a jamais traversé Authelia — créait des collections. C'était la seule écriture
    ouverte du dépôt, et elle contredisait la fermeture par défaut d'AUTH-2 (drapeau posé,
    identité absente ⇒ portée VIDE). Trouvé en relisant, sur une suite verte.
    """
    # Mono-poste : personne à identifier. Derrière le proxy : il FAUT une identité, sinon
    # la collection créée n'aurait aucun propriétaire possible — et l'écrire serait déjà
    # une écriture accordée à qui n'est pas passé par l'authentification.
    if not portee.tout and not portee.utilisateur:
        raise HTTPException(403, "Aucune identité ne parvient à l'application : votre "
                                 "requête n'est pas passée par l'authentification.")
    nom = (payload.nom or "").strip()
    if not nom:
        raise HTTPException(422, "Le nom de la collection est requis.")
    _refuser_nom_reserve(nom)
    cur = conn.execute("INSERT INTO collection (nom, description) VALUES (?, ?)",
                       (nom, payload.description))
    cid = cur.lastrowid
    if portee.utilisateur and not portee.admin:
        conn.execute(
            "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
            "VALUES (?, ?, ?, ?)",
            (cid, autorisation.UTILISATEUR, portee.utilisateur, autorisation.PROPRIETAIRE))
    journal.journaliser(conn, "creation", "collection", cid,
                        apres={"nom": nom, "proprietaire": portee.utilisateur})
    conn.commit()
    return {**collection_row(conn, cid), "acces": _acces_de(conn, cid)}


@app.patch("/api/collections/{collection_id}")
def update_collection(collection_id: int, payload: CollectionUpdate,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Modifie les descripteurs d'une collection (nom, description, licence, diffusion…).

    Réservé au propriétaire : ces champs sont de la métadonnée de DÉPÔT — licence, base
    légale, embargo — et les changer engage la collection entière, pas seulement le travail
    qu'on y fait.

    Deux valeurs sont contraintes : le nom de la collection de REPLI est réservé (s'y
    attribuer capturerait les albums créés sans collection explicite), et `statut_diffusion`
    est un vocabulaire contrôlé — il ne l'était que du côté de l'outil headless.
    """
    c = _get_collection(conn, portee, collection_id, administrer=True)
    fields = payload.model_dump(exclude_unset=True)
    if "nom" in fields:
        fields["nom"] = (fields["nom"] or "").strip()
        if not fields["nom"]:
            raise HTTPException(422, "Le nom de la collection est requis.")
        # Le repli, LUI, garde son nom : la garde interdit de PRENDRE ce nom, pas de le
        # conserver — sinon la collection de repli ne serait plus éditable du tout.
        if not nom_reserve(c["nom"]):
            _refuser_nom_reserve(fields["nom"])
    # `statut_diffusion` est un vocabulaire CONTRÔLÉ, et il ne l'était qu'à moitié :
    # `gerer_collections.py` le validait, cette route non. Un champ à deux portes dont une
    # seule contrôle n'est pas contrôlé — la liste est désormais partagée (config.py).
    if fields.get("statut_diffusion") and fields["statut_diffusion"] not in STATUTS_DIFFUSION:
        raise HTTPException(
            422, f"Statut de diffusion inconnu : {fields['statut_diffusion']} "
                 f"({' | '.join(STATUTS_DIFFUSION)}).")
    if fields:
        cols = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE collection SET {cols} WHERE id = ?",
                     (*fields.values(), collection_id))
        conn.commit()
    return collection_row(conn, collection_id)


@app.delete("/api/collections/{collection_id}", status_code=204)
def delete_collection(collection_id: int, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime une collection. Ses ALBUMS survivent (l'appartenance est N-N : le lien se
    défait, l'œuvre reste), et ses termes de vocabulaire sont PROMUS en global
    (`ON DELETE SET NULL`) plutôt que perdus.

    Refus si un album n'appartiendrait alors plus à aucune collection : l'invariant d'AUTH-2
    est qu'un album a toujours une règle d'accès. Le supprimer par ricochet fabriquerait
    exactement l'orphelin que le chantier précédent a retiré du modèle.
    """
    _get_collection(conn, portee, collection_id, administrer=True)
    isoles = [r[0] for r in conn.execute(
        "SELECT ca.album_id FROM collection_album ca WHERE ca.collection_id = ? "
        "AND NOT EXISTS (SELECT 1 FROM collection_album x WHERE x.album_id = ca.album_id "
        "                AND x.collection_id <> ca.collection_id)", (collection_id,))]
    if isoles:
        raise HTTPException(
            409, f"{len(isoles)} album(s) n'appartiennent qu'à cette collection et se "
                 "retrouveraient sans aucune règle d'accès. Rangez-les ailleurs d'abord.")
    c = collection_row(conn, collection_id)
    conn.execute("DELETE FROM collection WHERE id = ?", (collection_id,))
    journal.journaliser(conn, "suppression", "collection", collection_id,
                        avant={"nom": c["nom"]})
    conn.commit()
    return Response(status_code=204)


@app.get("/api/collections/{collection_id}/acces")
def list_acces(collection_id: int, conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    """Qui a accès à cette collection, et à quel niveau. Réservé au propriétaire : la liste
    des membres d'une étude est une donnée sur des PERSONNES, pas sur le corpus."""
    _get_collection(conn, portee, collection_id, administrer=True)
    return _acces_de(conn, collection_id)


@app.put("/api/collections/{collection_id}/acces")
def accorder_acces(collection_id: int, payload: AccesIn,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Accorde (ou change) un accès. Idempotent : re-poser le même principal met à jour son
    niveau, ce qui fait de « promouvoir » et « rétrograder » le même geste.

    `principal` est un NOM — un login, ou un nom de groupe tel qu'Authelia le pose dans
    `Remote-Groups`. On n'accorde donc rien à une personne qu'on aurait vérifiée : on
    déclare qu'un nom ouvre une collection. L'application n'a aucun annuaire (invariant
    AUTH-1), et un nom mal orthographié n'ouvre simplement rien.
    """
    _get_collection(conn, portee, collection_id, administrer=True)
    if payload.genre not in autorisation.GENRES:
        raise HTTPException(422, f"Genre invalide : {payload.genre} (utilisateur | groupe).")
    if payload.niveau not in autorisation.NIVEAUX:
        raise HTTPException(
            422, f"Niveau invalide : {payload.niveau} ({' | '.join(autorisation.NIVEAUX)}).")
    principal = (payload.principal or "").strip()
    if not principal:
        raise HTTPException(422, "Le principal (login ou nom de groupe) est requis.")
    # Rétrograder le DERNIER propriétaire laisserait une collection que plus personne ne
    # peut administrer — sauf un administrateur, mais compter là-dessus est précisément le
    # SQL à la main qu'AUTH-3 supprime.
    if (payload.niveau != autorisation.PROPRIETAIRE
            and _compte_proprietaires(conn, collection_id) == 1
            and conn.execute(
                "SELECT 1 FROM collection_acces WHERE collection_id = ? AND genre = ? "
                "AND principal = ? AND niveau = ?",
                (collection_id, payload.genre, principal,
                 autorisation.PROPRIETAIRE)).fetchone()):
        raise HTTPException(409, "C'est le dernier propriétaire de cette collection : "
                                 "désignez-en un autre avant de le rétrograder.")
    avant = conn.execute(
        "SELECT niveau FROM collection_acces WHERE collection_id = ? AND genre = ? "
        "AND principal = ?", (collection_id, payload.genre, principal)).fetchone()
    conn.execute(
        "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(collection_id, genre, principal) "
        "DO UPDATE SET niveau = excluded.niveau",
        (collection_id, payload.genre, principal, payload.niveau))
    # Qui a ouvert quoi à qui, et quand. La séparation « écrire ≠ partager » se justifie
    # par la TRAÇABILITÉ d'un accès accordé par erreur — sans trace, l'argument ne tenait
    # pas. `cible_id` est la collection : `collection_acces` a une clé composite et pas
    # d'id, et c'est bien la collection dont la liste d'accès change.
    _journaliser_acces(conn, collection_id, "lien",
                       avant={"genre": payload.genre, "principal": principal,
                              "niveau": avant["niveau"]} if avant else None,
                       apres={"genre": payload.genre, "principal": principal,
                              "niveau": payload.niveau})
    conn.commit()
    return _acces_de(conn, collection_id)


@app.delete("/api/collections/{collection_id}/acces/{genre}/{principal}", status_code=204)
def retirer_acces(collection_id: int, genre: str, principal: str,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Retire un accès. Ne détruit AUCUNE donnée : les annotations faites par la personne
    restent, et le journal A3 continue de les lui attribuer — retirer un droit d'entrée
    n'efface pas ce qui a été fait, sinon le corpus perdrait sa provenance à chaque départ.

    Refus sur le dernier propriétaire : une collection sans propriétaire n'est plus
    administrable que par un administrateur, et ce chantier existe pour ne plus en dépendre.
    """
    _get_collection(conn, portee, collection_id, administrer=True)
    ligne = conn.execute(
        "SELECT niveau FROM collection_acces WHERE collection_id = ? AND genre = ? "
        "AND principal = ?", (collection_id, genre, principal)).fetchone()
    if ligne is None:
        raise HTTPException(404, "Cet accès n'existe pas.")
    if (ligne["niveau"] == autorisation.PROPRIETAIRE
            and _compte_proprietaires(conn, collection_id) == 1):
        raise HTTPException(409, "C'est le dernier propriétaire de cette collection : "
                                 "désignez-en un autre avant de le retirer.")
    conn.execute("DELETE FROM collection_acces WHERE collection_id = ? AND genre = ? "
                 "AND principal = ?", (collection_id, genre, principal))
    _journaliser_acces(conn, collection_id, "delien",
                       avant={"genre": genre, "principal": principal,
                              "niveau": ligne["niveau"]})
    conn.commit()
    return Response(status_code=204)


@app.get("/api/albums/{album_id}/collections")
def list_collections_album(album_id: int, conn: sqlite3.Connection = Depends(db),
                           portee: autorisation.Portee = Depends(portee_courante)):
    """Les collections auxquelles cet album appartient — celles qu'on VOIT seulement.

    L'appartenance est N-N depuis la v14, et c'est porteur de sens : un même album peut
    nourrir deux études. La liste est donc PARTIELLE quand l'album est partagé avec une
    étude à laquelle on ne participe pas — même compromis que les attributs d'un objet
    partagé (cf. `_attributs_de`) : mieux vaut ne pas montrer que révéler l'existence
    d'une étude voisine.
    """
    _get_album(conn, portee, album_id)
    rows = _rows(conn.execute(
        "SELECT c.id, c.nom FROM collection_album ca "
        "JOIN collection c ON c.id = ca.collection_id "
        "WHERE ca.album_id = ? ORDER BY c.nom", (album_id,)))
    return [{**c, "mon_niveau": _niveau_dans(portee, c["id"]),
             "administrable": portee.peut_administrer(c["id"])}
            for c in rows if portee.peut_lire(c["id"])]


@app.put("/api/albums/{album_id}/collections/{collection_id}", status_code=201)
def ranger_album(album_id: int, collection_id: int,
                 conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Range un album DANS une collection. Idempotent.

    Deux droits, pas un : écrire sur l'album (donc sur une collection qui le contient déjà)
    ET écrire sur la collection d'arrivée. Sans le second, on déposerait son travail dans
    l'étude de quelqu'un d'autre ; sans le premier, on s'approprierait le travail d'un
    autre en le rangeant chez soi.
    """
    _get_album(conn, portee, album_id, ecriture=True)
    if not portee.peut_ecrire(collection_id) or collection_row(conn, collection_id) is None:
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    conn.execute("INSERT OR IGNORE INTO collection_album (collection_id, album_id) "
                 "VALUES (?, ?)", (collection_id, album_id))
    conn.commit()
    return list_collections_album(album_id, conn, portee)


@app.delete("/api/albums/{album_id}/collections/{collection_id}", status_code=204)
def sortir_album(album_id: int, collection_id: int,
                 conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Sort un album d'une collection. Refus si c'était la DERNIÈRE : un album hors de
    toute collection ne correspondrait à aucune règle d'accès (invariant AUTH-2).

    Le refus est un 409 qui NOMME la contrainte, plutôt qu'un repli silencieux vers la
    collection par défaut : déplacer, c'est ranger ailleurs PUIS sortir, et l'ordre inverse
    doit se voir refuser au lieu de déverser le travail dans un seau commun.
    """
    _get_album(conn, portee, album_id, ecriture=True)
    if not portee.peut_ecrire(collection_id):
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    # L'APPARTENANCE d'abord, la contrainte ensuite. Sans ce test, sortir un album d'une
    # collection dont il ne fait pas partie déclenchait le garde-fou du dessous et
    # répondait « c'est la dernière collection de cet album » — une phrase fausse, sur une
    # opération qui n'avait de toute façon rien à défaire.
    if conn.execute("SELECT 1 FROM collection_album WHERE album_id = ? AND collection_id = ?",
                    (album_id, collection_id)).fetchone() is None:
        raise HTTPException(404, "Cet album n'appartient pas à cette collection.")
    if conn.execute("SELECT COUNT(*) FROM collection_album WHERE album_id = ?",
                    (album_id,)).fetchone()[0] <= 1:
        raise HTTPException(409, "C'est la dernière collection de cet album : rangez-le "
                                 "ailleurs d'abord, un album ne peut rester sans règle "
                                 "d'accès.")
    conn.execute("DELETE FROM collection_album WHERE collection_id = ? AND album_id = ?",
                 (collection_id, album_id))
    conn.commit()
    return Response(status_code=204)


def _patch_lexique(conn, table, oid, payload, portee, *, col_definition="definition"):
    """Mise à jour PARTIELLE de la couche définitionnelle (definition/note_portee/etat/
    collection_id) d'un terme. `col_definition='description'` pour les tags (leur glose EST
    la définition). Valide l'état et l'existence de la collection de portée. Champ omis =
    inchangé ; `collection_id: null` explicite = promotion en global."""
    fields = payload.model_dump(exclude_unset=True)
    updates = {}
    if "definition" in fields:
        updates[col_definition] = fields["definition"]
    for k in ("note_portee", "etat", "collection_id"):
        if k in fields:
            updates[k] = fields[k]
    if "etat" in updates and updates["etat"] not in _ETATS_LEXIQUE:
        raise HTTPException(422, f"État invalide : {updates['etat']} (provisoire | defini).")
    # AUTH-2 — changer la PORTÉE d'un terme, c'est le déplacer chez quelqu'un (ou l'en
    # sortir). Il faut donc écrire dans la collection VISÉE, pas seulement dans celle
    # d'origine : sans cela, on rangerait son vocabulaire dans l'étude d'un autre.
    if "collection_id" in updates:
        cible = updates["collection_id"]
        if cible is None:
            if not portee.peut_ecrire_quelque_part():
                raise HTTPException(403, "Promouvoir un terme en global demande un droit "
                                         "d'écriture.")
        elif not portee.peut_ecrire(cible):
            raise HTTPException(404, f"Collection {cible} introuvable.")
        elif conn.execute("SELECT 1 FROM collection WHERE id = ?",
                          (cible,)).fetchone() is None:
            raise HTTPException(404, f"Collection {cible} introuvable.")
    if updates:
        cols = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE {table} SET {cols} WHERE id = ?", (*updates.values(), oid))
        conn.commit()


@app.get("/api/lexique")
def get_lexique(conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    """Tout le lexique situé pour l'édition : domaines + dimensions (→ valeurs) + tags, avec
    leur couche définitionnelle (definition/note_portee/etat/portée) et le nombre d'usages ;
    plus le résumé « % défini ». Read model du panneau Lexique.

    AUTH-2 — c'est le read model qui agrège TOUT le vocabulaire : quatre requêtes, quatre
    filtres, et l'oubli d'un seul rendrait vain le cloisonnement des routes unitaires
    ci-dessus, puisque le panneau Lexique passe par ici et non par elles."""
    ou_dom, p_dom = portee.clause_terme("domaine.collection_id")
    ou_dimx, p_dimx = portee.clause_terme("x.collection_id")
    ou_dim, p_dim = portee.clause_terme("d.collection_id")
    ou_val, p_val = portee.clause_terme("v.collection_id")
    ou_tag, p_tag = portee.clause_terme("t.collection_id")
    ou_album, p_album = portee.clause_album("pl.album_id")
    ou_perso, p_perso = _clause_personnage(portee)
    domaines = _rows(conn.execute(
        f"SELECT id, nom, definition, note_portee, etat, collection_id, "
        f"       (SELECT COUNT(*) FROM attribut_dimension x "
        f"         WHERE x.domaine_id = domaine.id AND {ou_dimx}) AS nb_dimensions "
        f"FROM domaine WHERE {ou_dom} ORDER BY nom", [*p_dimx, *p_dom]))
    dims = _rows(conn.execute(
        f"SELECT d.id, d.cible, d.nom, d.domaine_id, d.definition, d.note_portee, d.etat, "
        f"       d.collection_id "
        f"FROM attribut_dimension d WHERE {ou_dim} ORDER BY d.cible, d.nom", p_dim))
    vals = _rows(conn.execute(
        f"SELECT v.id, v.dimension_id, v.valeur, v.definition, v.note_portee, v.etat, "
        f"       v.collection_id, "
        f"       ((SELECT COUNT(*) FROM personnage_attribut pa JOIN personnages p "
        f"           ON p.id = pa.personnage_id "
        f"         WHERE pa.valeur_id = v.id AND {ou_perso}) "
        f"      + (SELECT COUNT(*) FROM region_attribut ra "
        f"           JOIN regions r   ON r.id = ra.region_id "
        f"           JOIN planches pl ON pl.id = r.planche_id "
        f"         WHERE ra.valeur_id = v.id AND {ou_album})) AS nb_usages "
        f"FROM attribut_valeur v WHERE {ou_val} ORDER BY v.valeur",
        [*p_perso, *p_album, *p_val]))
    par_dim = {}
    for v in vals:
        par_dim.setdefault(v["dimension_id"], []).append(v)
    for d in dims:
        d["valeurs"] = par_dim.get(d["id"], [])
    tags = _rows(conn.execute(
        f"SELECT t.id, t.label, t.description, t.note_portee, t.etat, t.collection_id, "
        f"       (SELECT COUNT(*) FROM annotation_tags at "
        f"          JOIN annotations an ON an.id = at.annotation_id "
        f"          JOIN regions r      ON r.id = an.region_id "
        f"          JOIN planches pl    ON pl.id = r.planche_id "
        f"        WHERE at.tag_id = t.id AND {ou_album}) AS frequence "
        f"FROM tags t WHERE {ou_tag} ORDER BY t.label", [*p_album, *p_tag]))
    # AUTH-2 — le résumé se filtre COMME les quatre listes ci-dessus. Il ne montrait aucun
    # terme, mais les COMPTAIT tous : « 3 définis sur 41 » à qui n'en voit que trois dit le
    # volume de vocabulaire des autres, et rend le pourcentage faux pour qui le lit.
    return {"domaines": domaines, "dimensions": dims, "tags": tags,
            "resume": lexique_resume(conn, clause=portee.clause_terme("collection_id"))}


@app.post("/api/lexique/importer")
def importer_lexique(file: UploadFile = File(...),
                     collection_id: Optional[int] = Form(None, ge=1),
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Amorçage EN LOT du vocabulaire depuis un tableur CSV (point-virgule) — bouton
    « Importer » du panneau 📖 Lexique. Même cœur et même doctrine que l'outil headless
    (pré-remplir sans écraser, idempotent ; cf. lexique_import + docs/import-vocabulaire.md).
    `collection_id` = portée d'appartenance (absent = global)."""
    # AUTH-2 — amorcer le vocabulaire est une écriture, et une écriture de PORTÉE :
    # `collection_id` range les termes chez quelqu'un. On exige donc le droit d'écrire
    # sur CETTE collection, et un simple droit d'écriture quelque part pour du global.
    if collection_id is None:
        if not portee.peut_ecrire_quelque_part():
            raise HTTPException(403, "Importer du vocabulaire demande un droit d'écriture "
                                     "sur au moins une collection.")
    elif not portee.peut_ecrire(collection_id):
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    if collection_id is not None and conn.execute(
            "SELECT 1 FROM collection WHERE id = ?", (collection_id,)).fetchone() is None:
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    data = file.file.read()
    if not data:
        raise HTTPException(400, "Fichier vide")
    try:
        texte = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "Le fichier doit être encodé en UTF-8.")
    try:
        lignes, anomalies = lexique_import.lire(io.StringIO(texte))
    except lexique_import.FormatInvalide as e:
        raise HTTPException(400, str(e))
    res, avert = lexique_import.importer(conn, lignes, collection_id)
    conn.commit()
    return {"resume": res, "lignes": len(lignes),
            "anomalies": anomalies, "avertissements": avert}


@app.patch("/api/attributs/dimensions/{dim_id}/lexique")
def patch_dimension_lexique(dim_id: int, payload: LexiqueIn,
                            conn: sqlite3.Connection = Depends(db),
                            portee: autorisation.Portee = Depends(portee_courante)):
    """Documente une dimension : définition + note de portée + état + portée d'appartenance."""
    _get_dimension(conn, portee, dim_id, ecriture=True)
    _patch_lexique(conn, "attribut_dimension", dim_id, payload, portee)
    return _row(conn.execute("SELECT * FROM attribut_dimension WHERE id = ?", (dim_id,)))


@app.patch("/api/attributs/valeurs/{val_id}/lexique")
def patch_valeur_lexique(val_id: int, payload: LexiqueIn,
                         conn: sqlite3.Connection = Depends(db),
                         portee: autorisation.Portee = Depends(portee_courante)):
    """Documente une valeur canonique (même couche définitionnelle)."""
    _get_valeur(conn, portee, val_id, ecriture=True)
    _patch_lexique(conn, "attribut_valeur", val_id, payload, portee)
    return _row(conn.execute("SELECT * FROM attribut_valeur WHERE id = ?", (val_id,)))


@app.patch("/api/tags/{tag_id}/lexique")
def patch_tag_lexique(tag_id: int, payload: LexiqueIn,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Documente un tag : sa `description` EST la définition SKOS ; + note de portée, état,
    portée d'appartenance (même patron que le vocabulaire facetté)."""
    ou, params = portee.clause_terme("t.collection_id")
    tag = _row(conn.execute(f"SELECT * FROM tags t WHERE t.id = ? AND {ou}",
                            (tag_id, *params)))
    if tag is None:
        raise HTTPException(404, f"Tag {tag_id} introuvable")
    if not portee.peut_ecrire_terme(tag.get("collection_id")):
        raise HTTPException(403, "Ce tag est en lecture seule pour vous.")
    _patch_lexique(conn, "tags", tag_id, payload, portee, col_definition="description")
    return _row(conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)))


def _affecter(conn, portee, table, col, oid, valeur_id, cible_attendue):
    """Affecte une valeur à une cible, après contrôle de cohérence de la dimension."""
    v = _get_valeur(conn, portee, valeur_id)
    if _get_dimension(conn, portee, v["dimension_id"])["cible"] != cible_attendue:
        raise HTTPException(422, f"Cette valeur n'appartient pas à une dimension de {cible_attendue}.")
    conn.execute(f"INSERT OR IGNORE INTO {table} ({col}, valeur_id) VALUES (?, ?)", (oid, valeur_id))
    conn.commit()


@app.get("/api/personnages/{personnage_id}/attributs")
def list_personnage_attributs(personnage_id: int, conn: sqlite3.Connection = Depends(db),
                              portee: autorisation.Portee = Depends(portee_courante)):
    _get_personnage(conn, portee, personnage_id)
    return _attributs_de(conn, portee, "personnage_attribut", "personnage_id", personnage_id)


@app.put("/api/personnages/{personnage_id}/attributs")
def add_personnage_attribut(personnage_id: int, payload: AttributIn,
                            conn: sqlite3.Connection = Depends(db),
                            portee: autorisation.Portee = Depends(portee_courante)):
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    _affecter(conn, portee, "personnage_attribut", "personnage_id", personnage_id, payload.valeur_id, "personnage")
    return _attributs_de(conn, portee, "personnage_attribut", "personnage_id", personnage_id)


@app.delete("/api/personnages/{personnage_id}/attributs/{valeur_id}", status_code=204)
def remove_personnage_attribut(personnage_id: int, valeur_id: int,
                               conn: sqlite3.Connection = Depends(db),
                               portee: autorisation.Portee = Depends(portee_courante)):
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    conn.execute("DELETE FROM personnage_attribut WHERE personnage_id = ? AND valeur_id = ?",
                 (personnage_id, valeur_id))
    conn.commit()


@app.get("/api/regions/{region_id}/attributs")
def list_region_attributs(region_id: int, conn: sqlite3.Connection = Depends(db),
                          portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id)
    return _attributs_de(conn, portee, "region_attribut", "region_id", region_id)


@app.put("/api/regions/{region_id}/attributs")
def add_region_attribut(region_id: int, payload: AttributIn,
                        conn: sqlite3.Connection = Depends(db),
                        portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    _affecter(conn, portee, "region_attribut", "region_id", region_id, payload.valeur_id, "case")
    return _attributs_de(conn, portee, "region_attribut", "region_id", region_id)


@app.delete("/api/regions/{region_id}/attributs/{valeur_id}", status_code=204)
def remove_region_attribut(region_id: int, valeur_id: int,
                           conn: sqlite3.Connection = Depends(db),
                           portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    conn.execute("DELETE FROM region_attribut WHERE region_id = ? AND valeur_id = ?",
                 (region_id, valeur_id))
    conn.commit()


# =========================================================================== #
# Recherche plein texte (FTS5)
# =========================================================================== #
def _recherche_rows(conn, portee, q, album, type, tags, pos, lemme, morph, provenance, limit,
                    tag_scope="propre", personnage=None, attributs=None):
    """Construit et exécute la requête de recherche (régions + contexte, tags joints).
    Partagé par /api/recherche (JSON) et l'export CSV — une seule logique de requête.

    AUTH-2 — la portée est un paramètre OBLIGATOIRE, et c'est ici que se referme le piège
    le plus vicieux du dépôt : la table FTS `recherche` est DÉNORMALISÉE et globale (elle
    agrège OCR + note + tags + lemmes) et ne porte aucune trace d'album ni de collection.
    Une requête plein texte non filtrée renverrait donc le contenu de tout le corpus,
    quelle que soit la rigueur des routes de lecture par identifiant. Le filtre passe par
    la jointure `albums a` déjà présente, pas par la table FTS.
    """
    where, params = [], []
    ou, params_portee = portee.clause_album("a.id")
    where.append(ou)
    params.extend(params_portee)

    base = (
        "SELECT r.id AS region_id, r.type, r.x, r.y, r.w, r.h, r.ocr_texte, "
        "       p.id AS planche_id, p.numero AS planche_numero, "
        "       p.chemin_web, p.largeur_px, p.hauteur_px, "       # pour l'aperçu en place
        "       a.id AS album_id, a.titre AS album_titre, "
        "       an.note AS note "
        "FROM regions r "
        "JOIN planches p ON p.id = r.planche_id "
        "JOIN albums a ON a.id = p.album_id "
        "LEFT JOIN annotations an ON an.region_id = r.id "
    )

    if q.strip():
        # (1) PRÉFIXE échappé sur le texte brut (ET implicite) : « otage » → « otages ».
        #     Insensible aux accents (tokenizer FTS remove_diacritics).
        raw = " ".join('"' + t.replace('"', '""') + '"*' for t in q.split())
        # (2) LEMMES : on lemmatise aussi la requête et on la matche sur la colonne
        #     `lemmes` → attrape ce que le préfixe rate (cheval↔chevaux, conjugaisons,
        #     élisions). Moteur optionnel : si spaCy absent, lemmatise() renvoie ""
        #     → on garde seulement (1) (repli propre).
        lemmes = nlp.lemmatise(q).split()
        if lemmes:
            lemma_expr = " ".join('"' + l.replace('"', '""') + '"' for l in lemmes)
            match_expr = f"({raw}) OR (lemmes : ({lemma_expr}))"
        else:
            match_expr = raw
        base += "JOIN recherche rch ON rch.region_id = r.id "
        where.append("recherche MATCH ?")
        params.append(match_expr)

    if album is not None:
        where.append("a.id = ?")
        params.append(album)
    if type:
        where.append("r.type = ?")
        params.append(type)
    if tags:
        # un paramètre `tags` par tag (robuste aux virgules dans les labels).
        # tag_scope : 'propre' = la région porte le tag ; 'herite' = la région OU sa
        # case parente — aligné sur /api/analyse/* pour que la descente aux preuves
        # (drill Exploration → Recherche) ne perde pas les tokens tagués au niveau case.
        cible = ("a2.region_id = r.id" if tag_scope == "propre"
                 else "a2.region_id IN (r.id, r.parent_id)")
        wanted = [_norm_tag(t) for t in tags if _norm_tag(t)]
        for label in wanted:
            where.append(
                "EXISTS (SELECT 1 FROM annotation_tags at "
                "        JOIN tags tg ON tg.id = at.tag_id "
                "        JOIN annotations a2 ON a2.id = at.annotation_id "
                f"       WHERE {cible} AND tg.label = ?)"
            )
            params.append(label)

    # Facettes GRAMMATICALES (lot 3) : la région contient-elle un token (valeur
    # EFFECTIVE) répondant aux critères ? EXISTS sur tokens_effectifs, scopé à la région.
    if pos or lemme or morph or provenance:
        tw, tp = [], []
        if pos:
            tw.append("te.pos = ?"); tp.append(pos.upper())
        if lemme:
            tw.append("te.lemme = ?"); tp.append(lemme.lower())
        if morph:
            tw.append("te.morph LIKE ?"); tp.append(f"%{morph}%")
        if provenance:
            tw.append("te.provenance = ?"); tp.append(provenance)
        where.append("EXISTS (SELECT 1 FROM tokens_effectifs te "
                     "WHERE te.region_id = r.id AND " + " AND ".join(tw) + ")")
        params.extend(tp)

    # Facettes ANN-2 : locuteur de la bulle, et attribut (profil du locuteur OU situation
    # de la case) — alignées sur /api/analyse/* pour que le drill Exploration→Recherche colle.
    if personnage is not None:
        where.append("EXISTS (SELECT 1 FROM bulle_locuteur bl "
                     "WHERE bl.region_id = r.id AND bl.personnage_id = ?)")
        params.append(personnage)
    for vid in (attributs or []):
        where.append(
            "(EXISTS (SELECT 1 FROM bulle_locuteur bl JOIN personnage_attribut pa "
            "         ON pa.personnage_id = bl.personnage_id "
            "         WHERE bl.region_id = r.id AND pa.valeur_id = ?) "
            " OR EXISTS (SELECT 1 FROM region_attribut ra "
            "            WHERE ra.region_id IN (r.id, r.parent_id) AND ra.valeur_id = ?))")
        params.extend([vid, vid])

    sql = base
    if where:
        sql += "WHERE " + " AND ".join(where) + " "
    sql += "ORDER BY p.numero, r.ordre LIMIT ?"
    params.append(limit)

    try:
        results = _rows(conn.execute(sql, params))
    except sqlite3.OperationalError as exc:
        raise HTTPException(400, f"Requête de recherche invalide : {exc}")

    # Joint les tags de chaque résultat.
    for row in results:
        row["tags"] = [t["label"] for t in _rows(conn.execute(
            """SELECT tg.label FROM annotation_tags at
               JOIN tags tg ON tg.id = at.tag_id
               JOIN annotations an ON an.id = at.annotation_id
               WHERE an.region_id = ? ORDER BY tg.label""",
            (row["region_id"],),
        ))]
        row["url_web"] = "/" + row["chemin_web"] if row["chemin_web"] else None
    cits = citations_regions(conn, [row["region_id"] for row in results])
    for row in results:
        row["citation"] = cits.get(row["region_id"])
    return results


@app.get("/api/recherche")
def recherche(q: str = "", album: Optional[int] = None,
              type: Optional[str] = None, tags: Optional[list[str]] = Query(None),
              pos: Optional[str] = None, lemme: Optional[str] = None,
              morph: Optional[str] = None, provenance: Optional[str] = None,
              tag_scope: str = "propre",
              personnage: Optional[int] = None, attributs: Optional[list[int]] = Query(None),
              limit: int = 100, conn: sqlite3.Connection = Depends(db),
              portee: autorisation.Portee = Depends(portee_courante)):
    limit = max(1, min(limit, 500))   # borne : évite LIMIT -1 (= tout le corpus) / DoS
    results = _recherche_rows(conn, portee, q, album, type, tags, pos, lemme, morph,
                              provenance, limit, tag_scope, personnage, attributs)
    return {"q": q, "count": len(results), "results": results}


_BOM = chr(0xFEFF)   # BOM UTF-8 : permet à Excel (Windows) de lire les accents correctement


def _csv_response(contenu: str, filename: str) -> Response:
    """Réponse CSV téléchargeable, préfixée d'un BOM UTF-8 pour qu'Excel (Windows) lise
    correctement les accents français. (R/pandas : lire en `utf-8-sig`.)"""
    return Response(content=_BOM + contenu, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _csv_safe(v):
    """Neutralise l'injection de FORMULE (CSV → tableur) : une cellule TEXTE débutant par
    `= + - @` (ou tab/CR) est préfixée d'une apostrophe → un tableur l'affiche littéralement
    au lieu de l'exécuter. À n'appliquer qu'au texte libre (pas aux nombres : « -5 » reste un
    nombre). Cf. OWASP « CSV Injection »."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


@app.get("/api/recherche/export.csv")
def recherche_export(q: str = "", album: Optional[int] = None,
                     type: Optional[str] = None, tags: Optional[list[str]] = Query(None),
                     pos: Optional[str] = None, lemme: Optional[str] = None,
                     morph: Optional[str] = None, provenance: Optional[str] = None,
                     tag_scope: str = "propre",
                     personnage: Optional[int] = None, attributs: Optional[list[int]] = Query(None),
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Export CSV du jeu de résultats courant (mêmes critères que /api/recherche).
    Borne haute relevée (5000) : on exporte le jeu trouvé, pas seulement l'aperçu."""
    results = _recherche_rows(conn, portee, q, album, type, tags, pos, lemme, morph,
                              provenance, 5000, tag_scope,
                              personnage, attributs)
    buf = io.StringIO()
    # `planche` = numéro ÉDITORIAL (cité), `citation` = repère complet « pl·c(·b) » ;
    # le CSV est l'artefact que le chercheur emporte pour citer. Cf.
    # docs/numerotation-et-citation.md.
    cols = ["album", "planche", "citation", "region_id", "type",
            "ocr_texte", "note", "tags"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in results:
        cit = r.get("citation") or {}
        planche = cit.get("planche")
        w.writerow({"album": _csv_safe(r["album_titre"]),
                    "planche": planche if planche is not None else "",
                    "citation": cit.get("texte", ""),
                    "region_id": r["region_id"], "type": r["type"],
                    "ocr_texte": _csv_safe(r["ocr_texte"] or ""),
                    "note": _csv_safe(r["note"] or ""),
                    "tags": _csv_safe("|".join(r["tags"]))})
    return _csv_response(buf.getvalue(), "recherche.csv")


@app.get("/api/corpus")
def corpus_stats(conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Compteurs globaux du corpus (pour l'aperçu de la page de recherche)."""
    # AUTH-2 : des compteurs GLOBAUX diraient combien d'albums et de planches existent
    # ailleurs — la composition du corpus fuit par les nombres aussi bien que par les
    # titres. Chaque sous-requête est donc rattachée à son album, puis filtrée.
    ou, pp = portee.clause_album("alb.id")
    oup, _ = portee.clause_album("pl.album_id")
    our, _ = portee.clause_album("plr.album_id")
    ou_tag, p_tag = portee.clause_terme("t.collection_id")
    row = conn.execute(
        f"""SELECT
             (SELECT COUNT(*) FROM albums alb WHERE {ou})   AS albums,
             (SELECT COUNT(*) FROM planches pl WHERE {oup}) AS planches,
             (SELECT COUNT(*) FROM regions r
                JOIN planches plr ON plr.id = r.planche_id WHERE {our})  AS regions,
             (SELECT COUNT(*) FROM annotations an JOIN regions r ON r.id = an.region_id
                JOIN planches plr ON plr.id = r.planche_id WHERE {our}) AS annotees,
             (SELECT COUNT(*) FROM regions r
                JOIN planches plr ON plr.id = r.planche_id
                WHERE {our} AND TRIM(COALESCE(r.ocr_texte, '')) <> '') AS transcrites,
             -- `tags` suit la règle du VOCABULAIRE et non celle des données : visible
             -- s'il est global ou local à une collection qu'on lit (cf. clause_terme).
             (SELECT COUNT(*) FROM tags t WHERE {ou_tag}) AS tags,
             (SELECT COUNT(*) FROM planches pl
                WHERE {oup} AND pl.validee IS NOT NULL) AS validees""",
        # 5 clauses d'album, puis celle des tags, puis la 6e d'album — dans l'ORDRE
        # d'apparition dans le SQL ci-dessus.
        [*pp * 5, *p_tag, *pp],
    ).fetchone()
    res = dict(row)
    # Distribution des planches par statut (pour la barre d'avancement du corpus).
    res["statuts"] = {s: 0 for s in STATUTS}
    for r in conn.execute(
            f"SELECT pl.statut, COUNT(*) AS n FROM planches pl WHERE {oup} "
            "GROUP BY pl.statut", pp):
        if r["statut"] in res["statuts"]:
            res["statuts"][r["statut"]] = r["n"]
    return res


# =========================================================================== #
# Analyse grammaticale (Palier B) — fréquences lexicales + tokens par région
# =========================================================================== #
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
    if lemme:
        where.append("te.lemme = ?"); params.append(lemme.lower())       # lemmes minusculés
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
        for label in (_norm_tag(t) for t in tags):
            if not label:
                continue
            where.append(
                "EXISTS (SELECT 1 FROM annotation_tags at2 "
                "        JOIN tags tg ON tg.id = at2.tag_id "
                "        JOIN annotations a2 ON a2.id = at2.annotation_id "
                f"       WHERE {cible} AND tg.label = ?)")
            params.append(label)
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


def _valider_facette(conn, personnage=None, attributs=None):
    """404 si un id de facette (personnage / valeur d'attribut) n'existe pas — évite
    un résultat vide silencieux sur un id erroné (revue ANN-2 #6)."""
    if personnage is not None and conn.execute(
            "SELECT 1 FROM personnages WHERE id = ?", (personnage,)).fetchone() is None:
        raise HTTPException(404, f"Personnage {personnage} introuvable")
    for vid in (attributs or []):
        if conn.execute("SELECT 1 FROM attribut_valeur WHERE id = ?", (vid,)).fetchone() is None:
            raise HTTPException(404, f"Valeur d'attribut {vid} introuvable")


@app.get("/api/analyse/frequences")
@app.get("/api/analyse/lemmes")          # alias rétro-compat (champ=lemme)
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
    if champ not in ("lemme", "pos", "morph"):
        raise HTTPException(422, "champ invalide (lemme | pos | morph).")
    limit = max(1, min(limit, 1000))
    _valider_facette(conn, personnage, attributs)
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
    return {"champ": champ, "results": _rows(conn.execute(sql, params))}


@app.get("/api/analyse/concordance")
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
    if not (lemme or pos or morph or tags or personnage or attributs or auteur):
        raise HTTPException(422, "Préciser au moins un critère (grammatical, tag, personnage, attribut ou auteur).")
    limit = max(1, min(limit, 500))
    _valider_facette(conn, personnage, attributs)
    where, params, _n = _analyse_filtres(portee, album, type, pos, lemme, morph, provenance, tags, tag_scope,
                                     personnage, attributs, auteur)
    if not _n:      # critères fournis mais aucun effectif (p.ex. tag vide) → évite un
        # sous-corpus « tout ce qui est visible », qui n'est pas ce qu'on a demandé
        raise HTTPException(422, "Aucun critère de recherche effectif.")
    sql = ("SELECT te.region_id, te.ordre, te.texte, te.lemme, te.pos, te.morph, "
           "       te.provenance, r.type, p.id AS planche_id, p.numero AS planche_numero, "
           "       a.id AS album_id, a.titre AS album_titre, r.ocr_texte, "
           "       loc.nom AS locuteur "
           "FROM tokens_effectifs te "
           "JOIN regions r ON r.id = te.region_id "
           "JOIN planches p ON p.id = r.planche_id "
           "JOIN albums a ON a.id = p.album_id "
           "LEFT JOIN bulle_locuteur blc ON blc.region_id = r.id "
           "LEFT JOIN personnages loc ON loc.id = blc.personnage_id "
           "WHERE " + " AND ".join(where) + " "
           "ORDER BY a.id, p.numero, r.ordre, te.ordre LIMIT ?")
    params.append(limit)
    results = _rows(conn.execute(sql, params))
    cits = citations_regions(conn, [r["region_id"] for r in results])
    for r in results:
        r["citation"] = cits.get(r["region_id"])   # chaque ligne KWIC se cite
    return {"count": len(results), "results": results}


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


@app.get("/api/analyse/comparaison")
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
                        tag_scope: str = "herite",
                        limit: int = 50, conn: sqlite3.Connection = Depends(db),
                        portee: autorisation.Portee = Depends(portee_courante)):
    """Compare deux sous-corpus A et B : valeurs (lemme|pos|morph) les plus
    SUR-représentées dans chacun, par différence de fréquence RELATIVE (rel = freq /
    total du sous-corpus → comparable malgré des tailles différentes)."""
    if champ not in ("lemme", "pos", "morph"):
        raise HTTPException(422, "champ invalide (lemme | pos | morph).")
    limit = max(1, min(limit, 200))
    _valider_facette(conn, a_personnage, a_attributs)
    _valider_facette(conn, b_personnage, b_attributs)
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
                    "diff": round(ra - rb, 6)})
    out.sort(key=lambda x: x["diff"], reverse=True)
    return {"champ": champ, "total_a": ta, "total_b": tb,
            "sur_a": [x for x in out[:limit] if x["diff"] > 0],
            "sur_b": [x for x in reversed(out[-limit:]) if x["diff"] < 0]}


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


def _axe_croisement(kind, sfx, tag_scope, conn):
    """Un axe → (joins, expr_valeur, expr_cle, params, filtre_concordance, libellé). `sfx`
    (x|y) désambiguïse les alias entre les deux axes. `expr_cle` = clé de drill (id pour
    locuteur/dimension, sinon = la valeur)."""
    if kind in _AXES_SIMPLES:
        expr, filtre, lib = _AXES_SIMPLES[kind]
        return "", expr, expr, [], filtre, lib
    if kind == "locuteur":
        bl, lo = f"blx_{sfx}", f"lox_{sfx}"
        joins = (f"LEFT JOIN bulle_locuteur {bl} ON {bl}.region_id = r.id "
                 f"LEFT JOIN personnages {lo} ON {lo}.id = {bl}.personnage_id")
        return joins, f"{lo}.nom", f"{lo}.id", [], "personnage", "locuteur"
    if kind == "tag":
        an, at, tg = f"anx_{sfx}", f"atx_{sfx}", f"tgx_{sfx}"
        cible = (f"{an}.region_id = r.id" if tag_scope == "propre"
                 else f"{an}.region_id IN (r.id, r.parent_id)")
        joins = (f"LEFT JOIN annotations {an} ON {cible} "
                 f"LEFT JOIN annotation_tags {at} ON {at}.annotation_id = {an}.id "
                 f"LEFT JOIN tags {tg} ON {tg}.id = {at}.tag_id")
        return joins, f"{tg}.label", f"{tg}.label", [], "tags", "tag"
    if kind.startswith("dim:"):
        try:
            dim_id = int(kind[4:])
        except ValueError:
            raise HTTPException(422, f"Axe dimension invalide : {kind}")
        d = conn.execute("SELECT nom, cible FROM attribut_dimension WHERE id = ?",
                         (dim_id,)).fetchone()
        if d is None:
            raise HTTPException(404, f"Dimension {dim_id} introuvable")
        # Le filtre de dimension porte sur l'AFFECTATION (valeur_id d'un attribut de cette
        # dimension), pas sur la valeur jointe : sinon un locuteur/case portant AUSSI d'autres
        # dimensions produirait une fausse ligne « (vide) » (fan-out sur toutes les dimensions).
        av = f"avx_{sfx}"
        sous = f"{{}}.valeur_id IN (SELECT id FROM attribut_valeur WHERE dimension_id = ?)"
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
        return joins, f"{av}.valeur", f"{av}.id", [dim_id], "attributs", d["nom"]
    raise HTTPException(422, f"Axe inconnu : {kind} (pos|morph|type|provenance|auteur|"
                             "locuteur|tag|dim:<id>)")


@app.get("/api/analyse/croisement")
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
    limit = max(1, min(limit, 50))
    _valider_facette(conn, personnage, attributs)
    jx, ex, cx, px, fx, lx = _axe_croisement(axe_x, "x", tag_scope, conn)
    jy, ey, cy, py, fy, ly = _axe_croisement(axe_y, "y", tag_scope, conn)
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


@app.get("/api/analyse/accord")
def analyse_accord(conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Rapport d'accord modèle↔humain (NLP-1) : part des tokens RELUS où le modèle NLP avait
    déjà la valeur finale (par champ lemme/POS/morpho) + confusion POS + modèle évalué. Étalon
    de qualité de l'index (transition Phase 1→2). Cf. accord.rapport / docs/rapport-accord.md.

    AUTH-2 — le rapport porte sur le sous-corpus lisible. Un taux d'accord global ne
    montrerait aucun contenu, mais dirait combien de tokens ont été relus ailleurs, donc
    l'ampleur du travail des autres."""
    return accord.rapport(conn, album_ids=_albums_lisibles(conn, portee))


@app.get("/api/analyse/accord-inter")
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


@app.get("/api/regions/{region_id}/tokens")
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


@app.put("/api/regions/{region_id}/tokens/{ordre}")
def corriger_token(region_id: int, ordre: int, payload: TokenCorrectionIn,
                   request: Request, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Corrige (ou valide) UN token : impose lemme/POS/morph et/ou marque l'état.
    Champ absent/vide = NULL = auto accepté. POS contrôlé (UPOS). La correction est
    ancrée sur la FORME actuelle du token (anti-dérive ; cf. docs/correction-grammaticale.md).
    L'auteur connecté (en-tête Remote-User, INFRA-2) est enregistré sur la correction."""
    # AUTH-2 — corriger la grammaire, c'est écrire sur la région.
    _get_region(conn, portee, region_id, ecriture=True)
    tok = conn.execute("SELECT texte FROM tokens WHERE region_id = ? AND ordre = ?",
                       (region_id, ordre)).fetchone()
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
    _corr_cols = ("ordre", "forme", "lemme", "pos", "morph", "etat")
    avant_corr = conn.execute(
        f"SELECT {', '.join(_corr_cols)} FROM token_correction "
        "WHERE region_id = ? AND ordre = ?", (region_id, ordre)).fetchone()
    conn.execute(
        "INSERT INTO token_correction "
        "  (region_id, ordre, forme, lemme, pos, morph, etat, auteur, obsolete, date_modif) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now')) "
        "ON CONFLICT(region_id, ordre) DO UPDATE SET "
        "  forme=excluded.forme, lemme=excluded.lemme, pos=excluded.pos, "
        "  morph=excluded.morph, etat=excluded.etat, auteur=excluded.auteur, "
        "  obsolete=0, date_modif=datetime('now')",
        (region_id, ordre, tok["texte"], lemme, pos, morph, payload.etat, auteur))
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


@app.post("/api/regions/{region_id}/grammaire/valider")
def valider_grammaire(region_id: int, request: Request,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Valide tous les tokens de la région (etat='valide') — geste courant des
    linguistes. Garde les corrections existantes (non obsolètes) et accepte l'auto
    ailleurs ; ne touche pas aux corrections « à revérifier ». NON bloquant : c'est
    une assertion de qualité, jamais un prérequis. L'auteur connecté (INFRA-2) est
    posé sur les tokens auto-acceptés, et REMPLIT l'auteur d'une correction qui n'en
    avait pas — sans jamais écraser le correcteur d'origine (COALESCE)."""
    # AUTH-2 — corriger la grammaire, c'est écrire sur la région.
    _get_region(conn, portee, region_id, ecriture=True)
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    nlp.ensure_loaded()          # spaCy hors transaction (cf. corriger_token)
    auteur = _auteur(request)
    reindex_region(conn, region_id)   # ré-ancre (aligne) d'abord → nettoie toute dérive du texte
    # 1) corrections cohérentes existantes → validées (auteur préservé : valider ≠ corriger)
    conn.execute("UPDATE token_correction "
                 "SET etat='valide', auteur=COALESCE(auteur, ?), date_modif=datetime('now') "
                 "WHERE region_id = ? AND obsolete = 0", (auteur, region_id))
    # 2) tokens sans correction → ligne 'valide' (accepte l'auto ; auteur = le validateur)
    conn.execute(
        "INSERT INTO token_correction (region_id, ordre, forme, etat, auteur, obsolete) "
        "SELECT t.region_id, t.ordre, t.texte, 'valide', ?, 0 FROM tokens t "
        "WHERE t.region_id = ? AND NOT EXISTS "
        "  (SELECT 1 FROM token_correction c WHERE c.region_id=t.region_id AND c.ordre=t.ordre)",
        (auteur, region_id))
    journal.journaliser(conn, "validation", "regions", region_id,
                        apres={"grammaire": "validee"})
    conn.commit()
    return _tokens_effectifs(conn, region_id)


@app.delete("/api/regions/{region_id}/tokens/{ordre}")
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


@app.get("/api/analyse/info")
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


# =========================================================================== #
# Jobs : traitement par lot en arrière-plan (segmentation / bulles / OCR)
# =========================================================================== #
@app.post("/api/jobs", status_code=201)
def creer_job(payload: JobIn, conn: sqlite3.Connection = Depends(db),
              portee: autorisation.Portee = Depends(portee_courante)):
    """Lance un lot sur l'ensemble des planches d'albums et/ou planches données."""
    passes = [p for p in jobs.PASSES if p in payload.passes]   # ordre canonique
    if not passes:
        raise HTTPException(422, "Aucune passe valide (segmenter / bulles / ocr).")
    avail = {"segmenter": kumiko_available(), "bulles": bulles_available(),
             "ocr": ocr_available()}
    manquants = [p for p in passes if not avail[p]]
    if manquants:
        raise HTTPException(503, f"Moteur(s) indisponible(s) : {', '.join(manquants)}.")

    # AUTH-2 — un lot MODIFIE les régions : il faut le droit d'écrire sur chaque planche.
    # On filtre plutôt que de refuser en bloc : demander « tout l'album 3 » quand on n'en
    # voit qu'une partie doit traiter cette partie, pas échouer en révélant le reste.
    ou, pparams = portee.clause_album("planches.album_id", ecriture=True)
    pids = set()
    if payload.planche_ids:
        inscriptibles = {r[0] for r in conn.execute(
            f"SELECT id FROM planches WHERE {ou}", pparams)}
        pids = inscriptibles & set(payload.planche_ids)
    for aid in payload.album_ids:
        pids.update(r["id"] for r in conn.execute(
            f"SELECT id FROM planches WHERE album_id = ? AND {ou}",
            (aid, *pparams)).fetchall())
    valid, verrouillees = [], 0
    if pids:
        ph = ",".join("?" * len(pids))
        rows = conn.execute(
            f"SELECT id, verrouillee FROM planches WHERE id IN ({ph}) "
            f"ORDER BY album_id, numero", tuple(pids)).fetchall()
        valid = [r["id"] for r in rows if not r["verrouillee"]]      # 🔒 ignorées
        verrouillees = sum(1 for r in rows if r["verrouillee"])
    if not valid:
        raise HTTPException(422, "Aucune planche à traiter"
                            + (f" ({verrouillees} verrouillée(s))." if verrouillees else "."))
    job = jobs.start_job(passes, valid)
    job["verrouillees_ignorees"] = verrouillees   # signalé, jamais en silence
    return job


def _planches_autorisees(conn, portee: autorisation.Portee,
                         *, ecriture: bool = False) -> Optional[set]:
    """Ids des planches visibles (ou modifiables si `ecriture`). None = toutes (portée
    totale), pour ne pas matérialiser un corpus entier à chaque appel."""
    if portee.tout:
        return None
    ou, params = portee.clause_album("p.album_id", ecriture=ecriture)
    return {r[0] for r in conn.execute(f"SELECT p.id FROM planches p WHERE {ou}", params)}


def _job_visible(conn, portee: autorisation.Portee, job_id: int,
                 *, ecriture: bool = False) -> bool:
    """Un job n'est visible que si TOUTES ses planches le sont.

    Le sous-ensemble strict, et pas l'intersection : un lot à cheval sur une collection
    autorisée et une autre révélerait, par son total et sa progression, qu'un travail
    existe ailleurs. Conséquence assumée : un lot lancé par un administrateur sur tout
    le corpus n'apparaît qu'à lui.
    """
    autorisees = _planches_autorisees(conn, portee, ecriture=ecriture)
    if autorisees is None:
        return True
    return set(jobs.planches_du_job(job_id)) <= autorisees


@app.get("/api/jobs")
def lister_jobs(conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    """Les lots en cours — filtrés : la progression d'un lot cite des planches, donc
    des albums, donc l'existence d'études qu'on ne devrait pas connaître."""
    return [s for s in jobs.all_jobs() if _job_visible(conn, portee, s["id"])]


@app.get("/api/jobs/{job_id}")
def etat_job(job_id: int, conn: sqlite3.Connection = Depends(db),
             portee: autorisation.Portee = Depends(portee_courante)):
    snap = jobs.snapshot(job_id)
    if snap is None or not _job_visible(conn, portee, job_id):
        raise HTTPException(404, f"Job {job_id} introuvable")
    return snap


@app.post("/api/jobs/{job_id}/annuler")
def annuler_job(job_id: int, conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    # Annuler un lot INTERROMPT un traitement : c'est une écriture, pas une lecture.
    # Un droit de lecture seule permettrait sinon de saborder la passe d'un collègue.
    if not _job_visible(conn, portee, job_id, ecriture=True):
        raise HTTPException(404, f"Job {job_id} introuvable")
    if not jobs.cancel_job(job_id):
        raise HTTPException(404, f"Job {job_id} introuvable")
    return jobs.snapshot(job_id)


# =========================================================================== #
# Export
# =========================================================================== #
def _region_tree(regions: list[dict], conn: sqlite3.Connection) -> list[dict]:
    """Reconstruit l'arbre des régions (par parent_id) avec annotations."""
    by_parent: dict = {}
    for r in regions:
        by_parent.setdefault(r["parent_id"], []).append(r)

    cits = citations_regions(conn, [r["id"] for r in regions])

    def build(parent_id):
        nodes = []
        for r in sorted(by_parent.get(parent_id, []),
                        key=lambda x: (x["ordre"] or 0, x["id"])):
            ann = _annotation_for_region(conn, r["id"])
            nodes.append({
                "id": r["id"], "type": r["type"],
                "citation": cits.get(r["id"]),
                "x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"],
                "ordre": r["ordre"], "source": r["source"],
                "ocr_texte": r["ocr_texte"],
                "annotation": {
                    "note": ann["note"],
                    "tags": [t["label"] for t in ann["tags"]],
                } if (ann["note"] or ann["tags"]) else None,
                "enfants": build(r["id"]),
            })
        return nodes

    return build(None)


# Ce que l'export JSON publie, NOMMÉ colonne par colonne (AUTH-1, 2026-08-31).
#
# Il faisait `SELECT *` sur `albums` et `planches`, donc 34 colonnes dont personne n'avait
# décidé la publication : `verrou_par` (qui tient un verrou d'édition, un état de travail
# transitoire, dans un artefact destiné à un entrepôt qui garde ses versions),
# `verrouillee`, et les chemins de fichiers du SERVEUR. Le défaut n'est pas la fuite mais
# le MÉCANISME : une colonne ajoutée à `planches` se publiait toute seule — par défaut et
# non par décision, comme la garde d'interface d'AUTH-4.
#
# `regions` n'y figure pas : `_region_tree` nomme déjà ses champs un à un.
_EXPORT_ALBUM_COLS = (
    "id", "titre", "auteur", "annee", "editeur", "serie", "description", "date_edition",
    "date_originale", "langue", "type_oeuvre", "lieu_edition", "edition_tirage", "isbn",
    "format_physique", "source_numerisation", "date_import")
_EXPORT_PLANCHE_COLS = (
    "id", "album_id", "numero", "role", "largeur_px", "hauteur_px", "dpi_x", "dpi_y",
    "mode", "statut", "date_segmentation", "validee", "relecture")
# Retenues, et pourquoi — le test `test_toute_colonne_exportable_est_classee` exige que
# toute colonne de la table figure ici OU dans la liste publiée : une colonne neuve fait
# échouer la suite au lieu de partir au dépôt.
_EXPORT_PLANCHE_RETENUES = {
    "chemin_tiff": "chemin de fichier sur le SERVEUR — interne, sans valeur descriptive",
    "chemin_web": "idem ; le dérivé se publie par IIIF, pas par un chemin de disque",
    "verrouillee": "état de travail TRANSITOIRE, faux dès la seconde suivante",
    "verrou_par": "qui tient le verrou : une identité, et transitoire de surcroît",
}


def _album_payload(conn: sqlite3.Connection, album_id: int) -> dict:
    album = _row(conn.execute(
        f"SELECT {', '.join(_EXPORT_ALBUM_COLS)} FROM albums WHERE id = ?", (album_id,)))
    if album is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
    planches = _rows(conn.execute(
        f"SELECT {', '.join(_EXPORT_PLANCHE_COLS)} FROM planches "
        "WHERE album_id = ? ORDER BY numero", (album_id,)))
    nums = numeros_editoriaux(conn, album_id)
    for p in planches:
        p["numero_editorial"] = nums.get(p["id"])   # None si paratexte ; `role` déjà présent
        p["dimensions_cm"] = dimensions_cm(p["largeur_px"], p["hauteur_px"],   # matériel (A6)
                                           p["dpi_x"], p["dpi_y"])
        regions = _rows(conn.execute(
            "SELECT * FROM regions WHERE planche_id = ?", (p["id"],)))
        p["regions"] = _region_tree(regions, conn)
    album["planches"] = planches
    return album


@app.get("/api/export/json")
def export_json(album_id: int, conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    _get_album(conn, portee, album_id)
    album = _album_payload(conn, album_id)
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "regions": "hasPart",
            "enfants": "hasPart",
            "ocr_texte": "text",
            "annotation": "comment",
        },
        "@type": "Book",
        "@id": f"album:{album['id']}",
        **album,
    }


@app.get("/api/export/csv")
def export_csv(album_id: int, conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    _get_album(conn, portee, album_id)
    rows = _rows(conn.execute(
        """SELECT a.titre AS album, p.numero AS ordre_import, r.id AS region_id,
                  r.type, r.parent_id, r.x, r.y, r.w, r.h, r.ordre, r.source,
                  r.ocr_texte,
                  an.note,
                  (SELECT GROUP_CONCAT(tg.label, '|')
                     FROM annotation_tags at JOIN tags tg ON tg.id = at.tag_id
                    WHERE at.annotation_id = an.id) AS tags
           FROM regions r
           JOIN planches p ON p.id = r.planche_id
           JOIN albums a ON a.id = p.album_id
           LEFT JOIN annotations an ON an.region_id = r.id
           WHERE a.id = ?
           ORDER BY p.numero, r.parent_id IS NOT NULL, r.ordre, r.id""",
        (album_id,),
    ))
    # Deux rôles distincts : `ordre_import` = page PHYSIQUE (position d'import, garde
    # le paratexte groupable) ; `planche` = numéro ÉDITORIAL cité (vide pour le
    # paratexte) ; `citation` = repère « pl·c(·b) ». Cf. docs/numerotation-et-citation.md.
    cits = citations_regions(conn, [r["region_id"] for r in rows])
    for r in rows:
        c = cits.get(r["region_id"]) or {}
        r["planche"] = c["planche"] if c.get("planche") is not None else ""
        r["citation"] = c.get("texte", "")
        for k in ("album", "ocr_texte", "note", "tags"):      # B7 : anti-injection de formule
            r[k] = _csv_safe(r.get(k))
    buf = io.StringIO()
    cols = ["album", "ordre_import", "planche", "citation", "region_id", "type",
            "parent_id", "x", "y", "w", "h", "ordre", "source", "ocr_texte",
            "note", "tags"]
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return _csv_response(buf.getvalue(), f"album_{album_id}.csv")


TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def _tei_el(parent, tag, **attrs):
    el = ET.SubElement(parent, f"{{{TEI_NS}}}{tag}")
    for k, v in attrs.items():
        if v is not None:
            el.set(k, str(v))
    return el


# Caractères interdits par XML 1.0 (hors \t \n \r) : ElementTree les émet bruts,
# produisant un fichier non re-parsable. On les retire du texte libre (OCR / note
# / métadonnées) avant insertion — sinon l'export TEI est silencieusement corrompu.
def _xml_safe(text) -> str:
    """Retire les caracteres interdits par XML 1.0 (garde tab/LF/CR) du
    texte libre : sinon ElementTree produit un export TEI non re-parsable."""
    if not text:
        return ""
    return "".join(
        c for c in text
        if ord(c) in (0x09, 0x0A, 0x0D)
        or 0x20 <= ord(c) <= 0xD7FF
        or 0xE000 <= ord(c) <= 0xFFFD
        or ord(c) >= 0x10000)


@app.get("/api/export/tei")
def export_tei(album_id: int, conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    album = _get_album(conn, portee, album_id)

    ET.register_namespace("", TEI_NS)
    root = ET.Element(f"{{{TEI_NS}}}TEI")

    # teiHeader minimal
    header = _tei_el(root, "teiHeader")
    file_desc = _tei_el(header, "fileDesc")
    title_stmt = _tei_el(file_desc, "titleStmt")
    _tei_el(title_stmt, "title").text = _xml_safe(album["titre"])
    if album["auteur"]:
        _tei_el(title_stmt, "author").text = _xml_safe(album["auteur"])
    pub = _tei_el(file_desc, "publicationStmt")
    _tei_el(pub, "publisher").text = _xml_safe(album["editeur"] or "BéDéditeur")
    src = _tei_el(file_desc, "sourceDesc")
    _tei_el(src, "p").text = _xml_safe(
        f"{album['titre']}"
        + (f", {album['serie']}" if album["serie"] else "")
        + (f" ({album['annee']})" if album["annee"] else "")
    )

    facsimile = _tei_el(root, "facsimile")
    planches = _rows(conn.execute(
        "SELECT * FROM planches WHERE album_id = ? ORDER BY numero", (album_id,)))
    nums = numeros_editoriaux(conn, album_id)

    for p in planches:
        surface = _tei_el(facsimile, "surface", ulx="0", uly="0",
                          lrx=p["largeur_px"], lry=p["hauteur_px"])
        surface.set(f"{{{XML_NS}}}id", f"planche_{p['id']}")   # ancre technique stable
        ed = nums.get(p["id"])
        if ed is not None:                 # planche de récit → @n = numéro éditorial cité
            surface.set("n", str(ed))
        else:                              # paratexte (couverture, liminaire…) : hors numérotation
            surface.set("type", "paratexte")
        if p["chemin_web"]:
            _tei_el(surface, "graphic", url="/" + p["chemin_web"])

        regions = _rows(conn.execute(
            "SELECT * FROM regions WHERE planche_id = ?", (p["id"],)))
        by_parent: dict = {}
        for r in regions:
            by_parent.setdefault(r["parent_id"], []).append(r)
        zone_cits = citations_regions(conn, [r["id"] for r in regions])

        def add_zones(container, parent_id):
            for r in sorted(by_parent.get(parent_id, []),
                            key=lambda x: (x["ordre"] or 0, x["id"])):
                zone = _tei_el(container, "zone",
                               ulx=r["x"], uly=r["y"],
                               lrx=(r["x"] or 0) + (r["w"] or 0),
                               lry=(r["y"] or 0) + (r["h"] or 0))
                zone.set(f"{{{XML_NS}}}id", f"zone_{r['id']}")
                zone.set("type", r["type"])
                _c = zone_cits.get(r["id"]) or {}
                if _c.get("bulle") is not None:        # zone citable : c2·b1
                    zone.set("n", f"c{_c['case']}·b{_c['bulle']}")
                elif _c.get("case") is not None:
                    zone.set("n", f"c{_c['case']}")
                if r["ocr_texte"]:
                    _tei_el(zone, "line").text = _xml_safe(r["ocr_texte"])
                ann = _annotation_for_region(conn, r["id"])
                if ann["note"] or ann["tags"]:
                    note = _tei_el(zone, "note")
                    if ann["tags"]:
                        note.set("type", "tags")
                        note.set("ana", _xml_safe(" ".join(t["label"] for t in ann["tags"])))
                    note.text = _xml_safe(ann["note"])
                add_zones(zone, r["id"])

        add_zones(surface, None)

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(
        xml_bytes, media_type="application/xml; charset=utf-8",
        headers={"Content-Disposition":
                 f'attachment; filename="album_{album_id}_tei.xml"'},
    )


# =========================================================================== #
# Statut Kumiko + frontend
# =========================================================================== #
@app.get("/api/sante")
def sante(profond: bool = False):
    """État des moteurs. RAPIDE par défaut, PROFOND sur demande (SANTE-1).

    Sans `?profond=1`, on répond comme avant : présence des modules, sans rien importer.
    C'est la voie des SONDES — celle d'un conteneur, celle d'une supervision — et celle
    qu'appelle le panneau 🩺 Moteurs à son ouverture. Elle doit rester instantanée. (Ce
    docstring a longtemps dit « ce que l'UI appelle à chaque chargement de page » : c'était
    faux depuis longtemps, aucun fichier de `static/` ne l'appelait.)

    Avec `?profond=1`, chaque moteur est RÉELLEMENT importé et le rapport dit pourquoi
    quand ça échoue. Coûteux au premier appel (torch se charge, plusieurs secondes et
    quelques centaines de Mo), puis mémorisé. À utiliser pour diagnostiquer une instance
    déployée, où l'on n'a plus d'accès shell — c'est précisément là que le contrôle rapide
    ment : le 2026-08-27 il a annoncé `bulles: true` sur une pile dont le premier
    `import ultralytics` levait une exception. Cf. `sante.py`."""
    from pipeline.modeles import etat_modeles
    rep = dict(sante_moteurs.rapide())
    rep["modeles_charges"] = etat_modeles()          # CONC-2 : modèles résidents en RAM
    if profond:
        rep["profond"] = sante_moteurs.rapport()
    return rep


def _auteur(request: Request) -> Optional[str]:
    """Login de la personne connectée — délégué à `autorisation.auteur` (AUTH-2).

    La lecture des en-têtes d'identité a migré dans `autorisation.py` : la portée
    d'autorisation en dépend, et deux implémentations de « qui est là » finiraient par
    diverger. Le nom local reste, il a des appelants dans tout le fichier.
    """
    return autorisation.auteur(request)


def _groupes(request: Request) -> list[str]:
    """Groupes de la personne connectée — délégué à `autorisation.groupes` (AUTH-2)."""
    return autorisation.groupes(request)


# Miroir des identités déjà écrites : évite une écriture SQLite à CHAQUE requête, ce qui
# sérialiserait tout le trafic derrière l'unique verrou d'écriture du WAL.
#
# On réécrit dans DEUX cas : le nom ou l'email a changé (Authelia fait foi), ou la
# dernière écriture date de plus d'une heure. Ce second cas n'est pas du zèle : sans lui,
# `derniere_vue` ne bougerait qu'au changement de nom, et la colonne mentirait sur ce
# qu'elle prétend mesurer. Une écriture par personne et par heure reste négligeable.
_VUS_TTL = 3600.0
_vus: dict = {}


def _enregistrer_utilisateur(conn: sqlite3.Connection, request: Request) -> Optional[str]:
    """Crée ou rafraîchit la ligne `utilisateur` de la personne connectée (AUTH-1).

    Renvoie son login, ou None hors proxy. Appelé depuis `/api/moi`, que l'UI sollicite à
    chaque chargement de page : la ligne apparaît donc dès la première visite. Un client
    purement API qui n'appellerait jamais `/api/moi` ne serait pas enregistré — assumé,
    et sans conséquence tant que rien n'exige la ligne."""
    login = _auteur(request)
    if not login:
        return None
    nom = (request.headers.get("Remote-Name") or "").strip() or None
    email = (request.headers.get("Remote-Email") or "").strip() or None
    connu = _vus.get(login)
    if connu is None or connu[:2] != (nom, email) or time.monotonic() - connu[2] > _VUS_TTL:
        conn.execute(
            "INSERT INTO utilisateur (login, nom, email, derniere_vue) "
            "VALUES (?, ?, ?, datetime('now')) "
            "ON CONFLICT(login) DO UPDATE SET nom = excluded.nom, email = excluded.email, "
            "derniere_vue = datetime('now')",
            (login, nom, email))
        conn.commit()
        _vus[login] = (nom, email, time.monotonic())
    return login


def _referent_instance():
    """Le référent d'instance (AUTH-4), ou None s'il n'est pas déclaré.

    DÉCLARATIF, et c'est écrit plutôt que laissé à découvrir : l'application ne connaît les
    groupes que de la personne qui frappe, à l'instant de sa requête (AUTH-1). Que ce nom
    appartienne encore à `bd-admins` lui est structurellement invérifiable — un référent
    qui a quitté l'équipe reste donc affiché. Le savoir vaut mieux que le constater.
    """
    if not (REFERENT_NOM or REFERENT_CONTACT):
        return None
    return {"nom": REFERENT_NOM or None, "contact": REFERENT_CONTACT or None}


@app.get("/api/moi")
def moi(request: Request, conn: sqlite3.Connection = Depends(db),
        portee: autorisation.Portee = Depends(portee_courante)):
    """Identité de l'utilisateur connecté, sa PORTÉE, et l'URL de déconnexion.

    En local, sans proxy, l'en-tête est absent → `utilisateur` vaut None et l'UI
    n'affiche ni nom ni déconnexion.

    AUTH-2 — le bloc `acces` existe pour une raison d'ergonomie, pas de sécurité : une
    portée vide rend l'application VISUELLEMENT indistinguable d'un corpus vide, et c'est
    la bonne réponse de sécurité (404 partout, rien ne fuit) mais la pire réponse d'usage.
    La personne se croit devant un outil cassé alors qu'il lui manque un droit. On ne
    révèle rien en le disant : le compte est le SIEN, pas celui du corpus.

    Cette route ne consultait pas la portée jusqu'au 2026-08-28, et sa raison écrite était
    qu'elle serait « circulaire » — elle ne l'est pas : `portee_courante` ne dépend que de
    la requête et de la base. Rapporter sa propre portée n'est pas se soumettre à elle.
    """
    utilisateur = _enregistrer_utilisateur(conn, request)
    nom = (request.headers.get("Remote-Name") or "").strip() or utilisateur
    return {"utilisateur": utilisateur, "nom": nom,
            "groupes": _groupes(request),
            "acces": {"total": portee.tout, "admin": portee.admin,
                      "collections": None if portee.tout else len(portee.lecture),
                      "ecriture": None if portee.tout else len(portee.ecriture),
                      # AUTH-4 — les noms des groupes d'administration. Ce ne sont pas des
                      # secrets : ils sont en clair dans `deploy/docker-compose.yml`. Mais
                      # aucune route ne les disait, si bien qu'une personne admise ne
                      # pouvait pas même déduire que le groupe existe — et le savoir ne le
                      # donne pas, l'appartenance venant d'Authelia.
                      #
                      # VIDE en mono-poste, et ce n'est pas une pudeur : sans proxy, aucun
                      # groupe n'est lu (AUTH-1) et personne ne peut appartenir à
                      # `bd-admins`. Le nommer ferait dire à l'écran des accès que « les
                      # administrateurs de l'instance lisent toute collection, sans y
                      # figurer » — en distinguant deux rôles là où il n'y a qu'une
                      # personne, qui a déjà tout. Un nom exact au service d'une phrase
                      # fausse.
                      "groupes_admin": sorted(AUTH_ADMIN_GROUPS) if AUTH_PROXY else [],
                      # Le référent d'INSTANCE : le seul lisible par une portée VIDE, donc
                      # le seul qui serve la personne que le bandeau envoie « demander un
                      # accès » sans dire à qui.
                      "referent": _referent_instance()},
            "deconnexion_url": AUTH_LOGOUT_URL or None}


# Fichiers statiques + images dérivées + shell HTML.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/derivatives/{chemin:path}")
def derivative(chemin: str, conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    """Image web d'une planche, CLOISONNÉE (AUTH-2).

    C'était un `app.mount("/derivatives", StaticFiles(...))` — et la plus large fuite du
    dépôt, trouvée en relisant plutôt que par un test : un montage n'est pas une route,
    le cliquet de `tests/test_autorisation.py` ne le voyait donc pas. Les chemins sont
    parfaitement devinables (`/derivatives/album_2/planche_0001.jpg`), si bien que tout le
    corpus restait lisible en image quelle que soit la rigueur des routes JSON. Le test
    regarde désormais aussi les montages.

    La base sert d'ALLOWLIST : on ne sert que des fichiers dont le chemin figure dans
    `planches.chemin_web`. Cela autorise et, du même coup, rend toute traversée de
    répertoire impossible — un `..` ne correspond à aucune ligne.
    """
    ou, params = portee.clause_album("planches.album_id")
    row = _row(conn.execute(
        f"SELECT chemin_web FROM planches WHERE chemin_web = ? AND {ou}",
        (f"derivatives/{chemin}", *params)))
    if row is None:
        raise HTTPException(404, "Image introuvable")
    fichier = DATA_DIR / row["chemin_web"]
    if not fichier.is_file():
        raise HTTPException(404, "Image introuvable")
    return FileResponse(str(fichier))


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(str(TEMPLATES_DIR / "index.html"))


@app.get("/recherche", response_class=HTMLResponse)
def recherche_page():
    return FileResponse(str(TEMPLATES_DIR / "recherche.html"))


@app.get("/corpus", response_class=HTMLResponse)
def corpus_page():
    return FileResponse(str(TEMPLATES_DIR / "corpus.html"))


@app.get("/exploration", response_class=HTMLResponse)
def exploration_page():
    return FileResponse(str(TEMPLATES_DIR / "exploration.html"))
