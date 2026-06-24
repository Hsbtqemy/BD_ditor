"""BD Annotator — application FastAPI (routes albums, planches, régions,
annotations, recherche, export).

Lancer :  uvicorn main:app --reload
"""
from __future__ import annotations

import csv
import io
import logging
import os
import sqlite3
import time
import unicodedata
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from typing import Iterator, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import (CIBLES_ATTRIBUT, DERIVATIVES_DIR, ROLES_PLANCHE, STATIC_DIR,
                    STATUTS, TEMPLATES_DIR, TYPES_REGION, UPOS_TAGS)
from database import (citations_regions, get_connection, init_db,
                      numeros_editoriaux, reindex_region, unindex_region)
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


app = FastAPI(title="BD Annotator", version="1.0", lifespan=lifespan)


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


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _row(cur) -> Optional[dict]:
    r = cur.fetchone()
    return dict(r) if r else None


# --------------------------------------------------------------------------- #
# Modèles Pydantic
# --------------------------------------------------------------------------- #
class AlbumIn(BaseModel):
    titre: str
    auteur: Optional[str] = None
    annee: Optional[int] = None
    editeur: Optional[str] = None
    serie: Optional[str] = None
    description: Optional[str] = None


class AlbumUpdate(BaseModel):
    titre: Optional[str] = None
    auteur: Optional[str] = None
    annee: Optional[int] = None
    editeur: Optional[str] = None
    serie: Optional[str] = None
    description: Optional[str] = None


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


class SharedocsImportIn(BaseModel):
    chemins: list[str] = Field(default_factory=list)
    album_id: Optional[int] = None
    nouvel_album: Optional[str] = None
    segmenter: bool = False


class DeposerIn(BaseModel):
    dossier: str = ""   # dossier ShareDocs cible (vide = racine)


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


class DimensionIn(BaseModel):
    cible: str      # 'personnage' | 'case'
    nom: str


class ValeurIn(BaseModel):
    valeur: str


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


def _get_planche(conn, planche_id: int) -> dict:
    p = _row(conn.execute("SELECT * FROM planches WHERE id = ?", (planche_id,)))
    if p is None:
        raise HTTPException(404, f"Planche {planche_id} introuvable")
    return p


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
def list_albums(conn: sqlite3.Connection = Depends(db)):
    return _rows(conn.execute(
        """SELECT a.*,
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
           ORDER BY a.serie IS NULL, a.serie, a.annee, a.titre"""
    ))


@app.post("/api/albums", status_code=201)
def create_album(album: AlbumIn, conn: sqlite3.Connection = Depends(db)):
    cur = conn.execute(
        "INSERT INTO albums (titre, auteur, annee, editeur, serie, description) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (album.titre, album.auteur, album.annee, album.editeur, album.serie,
         album.description),
    )
    conn.commit()
    return _row(conn.execute("SELECT * FROM albums WHERE id = ?", (cur.lastrowid,)))


@app.put("/api/albums/{album_id}")
def update_album(album_id: int, patch: AlbumUpdate,
                 conn: sqlite3.Connection = Depends(db)):
    if conn.execute("SELECT 1 FROM albums WHERE id = ?", (album_id,)).fetchone() is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
    fields = patch.model_dump(exclude_unset=True)
    if fields:
        cols = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE albums SET {cols} WHERE id = ?",
                     (*fields.values(), album_id))
        conn.commit()
    return _row(conn.execute("SELECT * FROM albums WHERE id = ?", (album_id,)))


@app.delete("/api/albums/{album_id}", status_code=204)
def delete_album(album_id: int, conn: sqlite3.Connection = Depends(db)):
    if conn.execute("SELECT 1 FROM albums WHERE id = ?", (album_id,)).fetchone() is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
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
def delete_planche(planche_id: int, conn: sqlite3.Connection = Depends(db)):
    p = _row(conn.execute(
        "SELECT id, chemin_tiff, chemin_web FROM planches WHERE id = ?", (planche_id,)))
    if p is None:
        raise HTTPException(404, f"Planche {planche_id} introuvable")
    for r in conn.execute(
        "SELECT id FROM regions WHERE planche_id = ?", (planche_id,)).fetchall():
        unindex_region(conn, r["id"])
    conn.execute("DELETE FROM planches WHERE id = ?", (planche_id,))   # CASCADE regions
    conn.commit()
    remove_planche_files(p["chemin_tiff"], p["chemin_web"])
    return Response(status_code=204)


@app.get("/api/albums/{album_id}/planches")
def album_planches(album_id: int, conn: sqlite3.Connection = Depends(db)):
    if conn.execute("SELECT 1 FROM albums WHERE id = ?", (album_id,)).fetchone() is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
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
    for p in planches:
        p["url_web"] = "/" + p["chemin_web"] if p["chemin_web"] else None
        p["numero_editorial"] = nums.get(p["id"])   # None si paratexte (cf. role)
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
):
    if conn.execute("SELECT 1 FROM albums WHERE id = ?", (album_id,)).fetchone() is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
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
              conn: sqlite3.Connection = Depends(db)):
    _refuser_si_verrouillee(_get_planche(conn, planche_id))
    if not kumiko_available():
        raise HTTPException(
            503,
            "Kumiko n'est pas installé. Clonez-le dans lib/kumiko "
            "(git clone https://github.com/njean42/kumiko.git lib/kumiko).",
        )
    try:
        with jobs.ML_LOCK:                       # pas d'inférence ML concurrente (mémoire)
            res = segment_planche(conn, planche_id, use_master=use_master)
    except KumikoError as exc:
        raise HTTPException(500, str(exc))
    conn.commit()
    return res


@app.post("/api/planches/{planche_id}/detecter-bulles")
def detecter_bulles(planche_id: int, conf: float = 0.3,
                    conn: sqlite3.Connection = Depends(db)):
    _refuser_si_verrouillee(_get_planche(conn, planche_id))
    if not bulles_available():
        raise HTTPException(
            503,
            "Détecteur de bulles indisponible. "
            "pip install -r requirements-ocr.txt (ultralytics + huggingface_hub).",
        )
    try:
        with jobs.ML_LOCK:                       # pas d'inférence ML concurrente (mémoire)
            res = detect_bulles(conn, planche_id, conf=conf)
    except BullesError as exc:
        raise HTTPException(500, str(exc))
    conn.commit()
    return res


@app.post("/api/planches/{planche_id}/ocr")
def ocr_route(planche_id: int, only_empty: bool = True,
              conn: sqlite3.Connection = Depends(db)):
    _refuser_si_verrouillee(_get_planche(conn, planche_id))
    if not ocr_available():
        raise HTTPException(
            503,
            "OCR indisponible. pip install -r requirements-ocr.txt (easyocr).",
        )
    try:
        with jobs.ML_LOCK:                       # pas d'inférence ML concurrente (mémoire)
            res = ocr_planche(conn, planche_id, only_empty=only_empty)
    except OCRError as exc:
        raise HTTPException(500, str(exc))
    conn.commit()
    return res


@app.get("/api/planches/{planche_id}/regions")
def planche_regions(planche_id: int, conn: sqlite3.Connection = Depends(db)):
    _get_planche(conn, planche_id)
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
                  conn: sqlite3.Connection = Depends(db)):
    _get_planche(conn, planche_id)
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
    conn.commit()
    return _row(conn.execute("SELECT * FROM regions WHERE id = ?", (new_id,)))


@app.get("/api/regions/{region_id}/crop")
def region_crop(region_id: int, taille: int = 1600,
                conn: sqlite3.Connection = Depends(db)):
    """PNG net de la région recadré dans le master.

    `taille` borne la largeur (vignettes de recherche : ~240 ; transcription :
    1600 par défaut). Bornée à [40, 2000].
    """
    png = region_crop_png(conn, region_id, max_dim=max(40, min(taille, 2000)))
    if png is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    return Response(png, media_type="image/png")


@app.put("/api/regions/{region_id}")
def update_region(region_id: int, patch: RegionUpdate,
                  conn: sqlite3.Connection = Depends(db)):
    existing = _row(conn.execute("SELECT * FROM regions WHERE id = ?", (region_id,)))
    if existing is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    fields = patch.model_dump(exclude_unset=True)
    if "type" in fields and fields["type"] not in TYPES_REGION:
        raise HTTPException(422, f"Type invalide : {fields['type']}")
    if "parent_id" in fields:
        _validate_parent(conn, existing["planche_id"], fields["parent_id"], region_id)
    if fields:
        cols = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE regions SET {cols} WHERE id = ?",
                     (*fields.values(), region_id))
        if "ocr_texte" in fields:
            reindex_region(conn, region_id)
        conn.commit()
    return _row(conn.execute("SELECT * FROM regions WHERE id = ?", (region_id,)))


@app.delete("/api/regions/{region_id}", status_code=204)
def delete_region(region_id: int, conn: sqlite3.Connection = Depends(db)):
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
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
    for r in descendants:
        unindex_region(conn, r["id"])
    conn.execute("DELETE FROM regions WHERE id = ?", (region_id,))
    conn.commit()
    return Response(status_code=204)


@app.post("/api/planches/{planche_id}/reordonner")
def reordonner(planche_id: int, conn: sqlite3.Connection = Depends(db)):
    """Recalcule l'ordre de lecture (rang per-niveau) de toute la planche."""
    _get_planche(conn, planche_id)
    res = reorder_planche(conn, planche_id)
    conn.commit()
    return res


@app.post("/api/regions/{region_id}/deplacer")
def deplacer_region(region_id: int, payload: MoveIn,
                    conn: sqlite3.Connection = Depends(db)):
    """Déplace une région d'un cran parmi ses frères ('haut' ou 'bas')."""
    try:
        res = move_region(conn, region_id, payload.sens)
    except ValueError as exc:
        raise HTTPException(404 if "introuvable" in str(exc) else 422, str(exc))
    conn.commit()
    return res


# =========================================================================== #
# ShareDocs (WebDAV Huma-Num) — explorateur & import
# =========================================================================== #
@app.get("/api/sharedocs/etat")
def sharedocs_etat():
    """État de connexion (sans mot de passe) + pré-remplissage depuis l'env."""
    return sharedocs.status()


@app.post("/api/sharedocs/connexion")
def sharedocs_connexion(payload: SharedocsConnIn):
    pwd = payload.password or os.environ.get("BD_SHAREDOCS_PASS", "")
    try:
        return sharedocs.configure(payload.url, payload.user, pwd)
    except ShareDocsError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/sharedocs/deconnexion")
def sharedocs_deconnexion():
    sharedocs.disconnect()
    return {"connecte": False}


@app.get("/api/sharedocs/liste")
def sharedocs_liste(chemin: str = ""):
    try:
        return sharedocs.list_dir(chemin)
    except ShareDocsError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/sharedocs/importer")
def sharedocs_importer(payload: SharedocsImportIn,
                       conn: sqlite3.Connection = Depends(db)):
    """Télécharge des fichiers ShareDocs et les ingère comme planches.

    Album cible : `album_id` (existant) OU `nouvel_album` (créé). Les fichiers
    non-image sont ignorés (collectés dans `erreurs`) ; un échec sur un fichier
    n'interrompt pas le lot.
    """
    if not payload.chemins:
        raise HTTPException(422, "Aucun fichier sélectionné.")
    created_album = False
    if payload.album_id is not None:
        if conn.execute("SELECT 1 FROM albums WHERE id = ?",
                        (payload.album_id,)).fetchone() is None:
            raise HTTPException(404, f"Album {payload.album_id} introuvable")
        album_id = payload.album_id
    elif payload.nouvel_album and payload.nouvel_album.strip():
        cur = conn.execute("INSERT INTO albums (titre) VALUES (?)",
                           (payload.nouvel_album.strip(),))
        album_id = cur.lastrowid
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
            data = sharedocs.download(chemin)
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
                        segment_planche(conn, planche["id"])
                    planche["statut"] = "segmentee"
                except Exception:
                    pass
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
@app.get("/api/sauvegarde")
def telecharger_sauvegarde():
    """Télécharge un snapshot cohérent de la base (zip horodaté)."""
    name, data = make_backup()
    return Response(
        data, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/sharedocs/deposer-sauvegarde")
def deposer_sauvegarde(payload: DeposerIn):
    """Dépose une sauvegarde de la base dans un dossier ShareDocs (PUT WebDAV)."""
    name, data = make_backup()
    folder = payload.dossier.strip("/")
    chemin = f"{folder}/{name}" if folder else name
    try:
        sharedocs.upload(chemin, data)
    except ShareDocsError as exc:
        raise HTTPException(400, str(exc))
    return {"depose": chemin, "taille": len(data)}


@app.patch("/api/planches/{planche_id}/statut")
def update_statut(planche_id: int, payload: StatutIn,
                  conn: sqlite3.Connection = Depends(db)):
    _get_planche(conn, planche_id)
    if payload.statut not in STATUTS:
        raise HTTPException(422, f"Statut invalide : {payload.statut}")
    conn.execute("UPDATE planches SET statut = ? WHERE id = ?",
                 (payload.statut, planche_id))
    conn.commit()
    return _get_planche(conn, planche_id)


@app.patch("/api/planches/{planche_id}/validation")
def update_validation(planche_id: int, payload: ValidationIn,
                      conn: sqlite3.Connection = Depends(db)):
    """Marque une planche comme validée (relue/finalisée) ou retire la validation.
    Drapeau humain orthogonal au `statut` du pipeline ; `validee` = horodatage."""
    _get_planche(conn, planche_id)
    if payload.validee:
        conn.execute("UPDATE planches SET validee = datetime('now') WHERE id = ?",
                     (planche_id,))
    else:
        conn.execute("UPDATE planches SET validee = NULL WHERE id = ?", (planche_id,))
    conn.commit()
    return _get_planche(conn, planche_id)


@app.patch("/api/planches/{planche_id}/verrou")
def update_verrou(planche_id: int, payload: VerrouIn,
                  conn: sqlite3.Connection = Depends(db)):
    """Verrouille une planche (la protège des passes automatiques en lot) ou la
    déverrouille. Distinct de `validee` (verrou = protection ≠ validation = qualité) ;
    `verrouillee` = horodatage. Cf. docs/correction-grammaticale.md §6."""
    _get_planche(conn, planche_id)
    if payload.verrouillee:
        conn.execute("UPDATE planches SET verrouillee = datetime('now') WHERE id = ?",
                     (planche_id,))
    else:
        conn.execute("UPDATE planches SET verrouillee = NULL WHERE id = ?", (planche_id,))
    conn.commit()
    return _get_planche(conn, planche_id)


@app.patch("/api/planches/{planche_id}/role")
def update_role(planche_id: int, payload: RoleIn,
                conn: sqlite3.Connection = Depends(db)):
    """Définit le rôle éditorial d'une planche : 'recit' (narrative, numérotée) ou
    'paratexte' (couverture, liminaire, pub… — écartée de la numérotation et du
    décompte de cases citables). Le numéro éditorial est DÉRIVÉ, jamais stocké ;
    on le renvoie ici (recalculé sur tout l'album) car basculer une planche décale
    les suivantes. Cf. docs/numerotation-et-citation.md."""
    planche = _get_planche(conn, planche_id)
    if payload.role not in ROLES_PLANCHE:
        raise HTTPException(422, f"Rôle invalide : {payload.role}")
    conn.execute("UPDATE planches SET role = ? WHERE id = ?", (payload.role, planche_id))
    conn.commit()
    out = _get_planche(conn, planche_id)
    out["numero_editorial"] = numeros_editoriaux(conn, planche["album_id"]).get(planche_id)
    return out


# =========================================================================== #
# Annotations & tags
# =========================================================================== #
@app.get("/api/regions/{region_id}/annotation")
def get_annotation(region_id: int, conn: sqlite3.Connection = Depends(db)):
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    return _annotation_for_region(conn, region_id)


@app.put("/api/regions/{region_id}/annotation")
def put_annotation(region_id: int, payload: AnnotationIn,
                   conn: sqlite3.Connection = Depends(db)):
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")

    tag_rows = _ensure_tags(conn, payload.tags)
    # Vider une annotation (note vide ET aucun tag) = SUPPRIMER la ligne, pas
    # laisser une coquille vide : sinon elle fausserait le compteur d'annotées,
    # ne serait pas cherchable, et ferait conserver à tort la case à la
    # re-segmentation (préservation du travail humain).
    if not (payload.note or "").strip() and not tag_rows:
        conn.execute("DELETE FROM annotations WHERE region_id = ?", (region_id,))
        reindex_region(conn, region_id)
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

    reindex_region(conn, region_id)
    conn.commit()
    return _annotation_for_region(conn, region_id)


@app.get("/api/tags")
def list_tags(conn: sqlite3.Connection = Depends(db)):
    return _rows(conn.execute(
        """SELECT t.id, t.label, t.couleur, t.description,
                  COUNT(at.annotation_id) AS frequence
           FROM tags t LEFT JOIN annotation_tags at ON at.tag_id = t.id
           GROUP BY t.id
           ORDER BY frequence DESC, t.label"""
    ))


@app.post("/api/tags", status_code=201)
def create_tag(tag: TagIn, conn: sqlite3.Connection = Depends(db)):
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
# Personnages & attribution (ANN-2) — entité canonique + lien locuteur
# =========================================================================== #
def _get_personnage(conn, personnage_id):
    p = _row(conn.execute("SELECT * FROM personnages WHERE id = ?", (personnage_id,)))
    if p is None:
        raise HTTPException(404, f"Personnage {personnage_id} introuvable")
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
def list_personnages(q: Optional[str] = None, conn: sqlite3.Connection = Depends(db)):
    """Registre des personnages (niveau corpus) + nombre de bulles attribuées.
    `q` filtre par nom (autocomplétion à la saisie / canonicalisation à la volée)."""
    rows = _rows(conn.execute(
        "SELECT p.id, p.nom, p.serie, p.notes, "
        "       (SELECT COUNT(*) FROM bulle_locuteur bl WHERE bl.personnage_id = p.id) AS nb_bulles "
        "FROM personnages p ORDER BY p.nom, p.serie"))
    if q and q.strip():
        cible = _sans_accents(q)   # autocomplétion insensible à la casse ET aux accents
        rows = [r for r in rows if cible in _sans_accents(r["nom"])]
    return rows


@app.post("/api/personnages", status_code=201)
def create_personnage(payload: PersonnageIn, conn: sqlite3.Connection = Depends(db)):
    nom = (payload.nom or "").strip()
    if not nom:
        raise HTTPException(422, "Nom de personnage vide")
    pid = conn.execute(
        "INSERT INTO personnages (nom, serie, notes) VALUES (?, ?, ?)",
        (nom, (payload.serie or "").strip() or None, payload.notes)).lastrowid
    conn.commit()
    return _get_personnage(conn, pid)


@app.put("/api/personnages/{personnage_id}")
def update_personnage(personnage_id: int, payload: PersonnageUpdate,
                      conn: sqlite3.Connection = Depends(db)):
    _get_personnage(conn, personnage_id)
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
    return _get_personnage(conn, personnage_id)


@app.delete("/api/personnages/{personnage_id}", status_code=204)
def delete_personnage(personnage_id: int, conn: sqlite3.Connection = Depends(db)):
    _get_personnage(conn, personnage_id)
    conn.execute("DELETE FROM personnages WHERE id = ?", (personnage_id,))   # CASCADE : détache liens/attributs
    conn.commit()


@app.post("/api/personnages/{personnage_id}/fusion")
def fusionner_personnage(personnage_id: int, payload: FusionIn,
                         conn: sqlite3.Connection = Depends(db)):
    """Fusionne `personnage_id` (doublon) DANS `cible_id` (canonique) : réaffecte les
    liens locuteur et les attributs, puis supprime le doublon. Idempotent sur les
    affectations (INSERT OR IGNORE). Soupape du modèle mentions→entités (curation)."""
    if payload.cible_id == personnage_id:
        raise HTTPException(422, "Un personnage ne peut être fusionné avec lui-même")
    _get_personnage(conn, personnage_id)
    _get_personnage(conn, payload.cible_id)
    # locuteur : une bulle a au plus un locuteur (region_id PK) → réaffectation directe.
    conn.execute("UPDATE bulle_locuteur SET personnage_id = ? WHERE personnage_id = ?",
                 (payload.cible_id, personnage_id))
    # attributs : éviter le doublon (personnage_id, valeur_id) → OR IGNORE ; le reste du
    # doublon part au DELETE (CASCADE).
    conn.execute("INSERT OR IGNORE INTO personnage_attribut (personnage_id, valeur_id) "
                 "SELECT ?, valeur_id FROM personnage_attribut WHERE personnage_id = ?",
                 (payload.cible_id, personnage_id))
    conn.execute("DELETE FROM personnages WHERE id = ?", (personnage_id,))
    conn.commit()
    return _get_personnage(conn, payload.cible_id)


@app.get("/api/regions/{region_id}/locuteur")
def get_locuteur(region_id: int, conn: sqlite3.Connection = Depends(db)):
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    return _locuteur_for(conn, region_id)


@app.put("/api/regions/{region_id}/locuteur")
def set_locuteur(region_id: int, payload: LocuteurIn, conn: sqlite3.Connection = Depends(db)):
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    _get_personnage(conn, payload.personnage_id)
    conn.execute("INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?) "
                 "ON CONFLICT(region_id) DO UPDATE SET personnage_id = excluded.personnage_id",
                 (region_id, payload.personnage_id))
    conn.commit()
    return _locuteur_for(conn, region_id)


@app.delete("/api/regions/{region_id}/locuteur", status_code=204)
def clear_locuteur(region_id: int, conn: sqlite3.Connection = Depends(db)):
    conn.execute("DELETE FROM bulle_locuteur WHERE region_id = ?", (region_id,))
    conn.commit()


# --- Présence : quelle entité est MONTRÉE dans une boîte personnage (§14, brique (a)).
#     Strict miroir du locuteur, mais pour l'image — la boîte porte l'identité, et le
#     profil de l'entité devient atteignable depuis l'image (muets compris). La cohérence
#     de type (region.type = 'personnage') est assurée côté UI, comme pour le locuteur.
@app.get("/api/regions/{region_id}/personnage")
def get_presence(region_id: int, conn: sqlite3.Connection = Depends(db)):
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    return _personnage_for(conn, region_id)


@app.put("/api/regions/{region_id}/personnage")
def set_presence(region_id: int, payload: PresenceIn, conn: sqlite3.Connection = Depends(db)):
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    _get_personnage(conn, payload.personnage_id)
    conn.execute("INSERT INTO personnage_presence (region_id, personnage_id) VALUES (?, ?) "
                 "ON CONFLICT(region_id) DO UPDATE SET personnage_id = excluded.personnage_id",
                 (region_id, payload.personnage_id))
    conn.commit()
    return _personnage_for(conn, region_id)


@app.delete("/api/regions/{region_id}/personnage", status_code=204)
def clear_presence(region_id: int, conn: sqlite3.Connection = Depends(db)):
    conn.execute("DELETE FROM personnage_presence WHERE region_id = ?", (region_id,))
    conn.commit()


# --- Attributs FACETTÉS & ÉMERGENTS : dimensions (axes) / valeurs canoniques /
#     affectations. Vocabulaire NON figé — créé au fil de l'eau. Valeurs et noms de
#     dimension normalisés (comme les tags) → agrégeables. Cf. docs/personnages-et-attribution.md.
def _get_dimension(conn, dim_id):
    d = _row(conn.execute("SELECT * FROM attribut_dimension WHERE id = ?", (dim_id,)))
    if d is None:
        raise HTTPException(404, f"Dimension {dim_id} introuvable")
    return d


def _get_valeur(conn, val_id):
    v = _row(conn.execute("SELECT * FROM attribut_valeur WHERE id = ?", (val_id,)))
    if v is None:
        raise HTTPException(404, f"Valeur d'attribut {val_id} introuvable")
    return v


def _attributs_de(conn, table, col, oid):
    """Valeurs (avec leur dimension) affectées à une cible (personnage | région)."""
    return _rows(conn.execute(
        f"SELECT v.id AS valeur_id, v.valeur, d.id AS dimension_id, d.nom AS dimension, d.cible "
        f"FROM {table} x JOIN attribut_valeur v ON v.id = x.valeur_id "
        f"JOIN attribut_dimension d ON d.id = v.dimension_id "
        f"WHERE x.{col} = ? ORDER BY d.nom, v.valeur", (oid,)))


@app.get("/api/attributs/dimensions")
def list_dimensions(cible: Optional[str] = None, conn: sqlite3.Connection = Depends(db)):
    """Dimensions (axes émergents) + nombre de valeurs. `cible` filtre 'personnage' | 'case'."""
    sql = ("SELECT d.id, d.cible, d.nom, "
           "       (SELECT COUNT(*) FROM attribut_valeur v WHERE v.dimension_id = d.id) AS nb_valeurs "
           "FROM attribut_dimension d ")
    params = []
    if cible:
        sql += "WHERE d.cible = ? "
        params.append(cible)
    sql += "ORDER BY d.cible, d.nom"
    return _rows(conn.execute(sql, params))


@app.post("/api/attributs/dimensions", status_code=201)
def create_dimension(payload: DimensionIn, conn: sqlite3.Connection = Depends(db)):
    if payload.cible not in CIBLES_ATTRIBUT:
        raise HTTPException(422, f"Cible invalide : {payload.cible} (personnage | case).")
    nom = _norm_tag(payload.nom)
    if not nom:
        raise HTTPException(422, "Nom de dimension vide")
    conn.execute("INSERT INTO attribut_dimension (cible, nom) VALUES (?, ?) "
                 "ON CONFLICT(cible, nom) DO NOTHING", (payload.cible, nom))
    conn.commit()
    return _row(conn.execute("SELECT * FROM attribut_dimension WHERE cible = ? AND nom = ?",
                             (payload.cible, nom)))


@app.delete("/api/attributs/dimensions/{dim_id}", status_code=204)
def delete_dimension(dim_id: int, conn: sqlite3.Connection = Depends(db)):
    _get_dimension(conn, dim_id)
    conn.execute("DELETE FROM attribut_dimension WHERE id = ?", (dim_id,))   # CASCADE : valeurs + affectations
    conn.commit()


@app.get("/api/attributs/dimensions/{dim_id}/valeurs")
def list_valeurs(dim_id: int, conn: sqlite3.Connection = Depends(db)):
    _get_dimension(conn, dim_id)
    return _rows(conn.execute(
        "SELECT v.id, v.dimension_id, v.valeur, "
        "       (SELECT COUNT(*) FROM personnage_attribut pa WHERE pa.valeur_id = v.id) "
        "       + (SELECT COUNT(*) FROM region_attribut ra WHERE ra.valeur_id = v.id) AS nb_usages "
        "FROM attribut_valeur v WHERE v.dimension_id = ? ORDER BY v.valeur", (dim_id,)))


@app.post("/api/attributs/dimensions/{dim_id}/valeurs", status_code=201)
def create_valeur(dim_id: int, payload: ValeurIn, conn: sqlite3.Connection = Depends(db)):
    _get_dimension(conn, dim_id)
    valeur = _norm_tag(payload.valeur)
    if not valeur:
        raise HTTPException(422, "Valeur vide")
    conn.execute("INSERT INTO attribut_valeur (dimension_id, valeur) VALUES (?, ?) "
                 "ON CONFLICT(dimension_id, valeur) DO NOTHING", (dim_id, valeur))
    conn.commit()
    return _row(conn.execute("SELECT * FROM attribut_valeur WHERE dimension_id = ? AND valeur = ?",
                             (dim_id, valeur)))


@app.delete("/api/attributs/valeurs/{val_id}", status_code=204)
def delete_valeur(val_id: int, conn: sqlite3.Connection = Depends(db)):
    _get_valeur(conn, val_id)
    conn.execute("DELETE FROM attribut_valeur WHERE id = ?", (val_id,))   # CASCADE : affectations
    conn.commit()


@app.get("/api/attributs/valeurs")
def list_valeurs_plat(cible: Optional[str] = None, conn: sqlite3.Connection = Depends(db)):
    """Toutes les valeurs (avec leur dimension), à plat — sert les facettes d'analyse
    (évite un N+1 dimensions→valeurs). `cible` filtre 'personnage' | 'case'."""
    sql = ("SELECT v.id, v.valeur, d.id AS dimension_id, d.nom AS dimension, d.cible, "
           "       (SELECT COUNT(*) FROM personnage_attribut pa WHERE pa.valeur_id = v.id) "
           "       + (SELECT COUNT(*) FROM region_attribut ra WHERE ra.valeur_id = v.id) AS nb_usages "
           "FROM attribut_valeur v JOIN attribut_dimension d ON d.id = v.dimension_id ")
    params = []
    if cible:
        sql += "WHERE d.cible = ? "
        params.append(cible)
    sql += "ORDER BY d.cible, d.nom, v.valeur"
    return _rows(conn.execute(sql, params))


@app.put("/api/attributs/valeurs/{val_id}")
def rename_valeur(val_id: int, payload: ValeurIn, conn: sqlite3.Connection = Depends(db)):
    """Renomme une valeur (curation). Conflit avec une valeur existante de la même
    dimension → 409 (utiliser la fusion à la place)."""
    v = _get_valeur(conn, val_id)
    valeur = _norm_tag(payload.valeur)
    if not valeur:
        raise HTTPException(422, "Valeur vide")
    if _row(conn.execute("SELECT id FROM attribut_valeur "
                         "WHERE dimension_id = ? AND valeur = ? AND id <> ?",
                         (v["dimension_id"], valeur, val_id))):
        raise HTTPException(409, "Cette valeur existe déjà dans la dimension — fusionnez-les.")
    conn.execute("UPDATE attribut_valeur SET valeur = ? WHERE id = ?", (valeur, val_id))
    conn.commit()
    return _get_valeur(conn, val_id)


@app.post("/api/attributs/valeurs/{val_id}/fusion")
def fusionner_valeur(val_id: int, payload: FusionIn, conn: sqlite3.Connection = Depends(db)):
    """Fusionne la valeur `val_id` DANS `cible_id` (même dimension) : réaffecte les
    affectations (personnages + cases) en INSERT OR IGNORE, puis supprime le doublon."""
    if payload.cible_id == val_id:
        raise HTTPException(422, "Une valeur ne peut être fusionnée avec elle-même")
    v = _get_valeur(conn, val_id)
    cible = _get_valeur(conn, payload.cible_id)
    if v["dimension_id"] != cible["dimension_id"]:
        raise HTTPException(422, "On ne fusionne que deux valeurs d'une même dimension.")
    for table, col in (("personnage_attribut", "personnage_id"), ("region_attribut", "region_id")):
        conn.execute(f"INSERT OR IGNORE INTO {table} ({col}, valeur_id) "
                     f"SELECT {col}, ? FROM {table} WHERE valeur_id = ?", (payload.cible_id, val_id))
    conn.execute("DELETE FROM attribut_valeur WHERE id = ?", (val_id,))   # CASCADE purge le reste
    conn.commit()
    return _get_valeur(conn, payload.cible_id)


def _affecter(conn, table, col, oid, valeur_id, cible_attendue):
    """Affecte une valeur à une cible, après contrôle de cohérence de la dimension."""
    v = _get_valeur(conn, valeur_id)
    if _get_dimension(conn, v["dimension_id"])["cible"] != cible_attendue:
        raise HTTPException(422, f"Cette valeur n'appartient pas à une dimension de {cible_attendue}.")
    conn.execute(f"INSERT OR IGNORE INTO {table} ({col}, valeur_id) VALUES (?, ?)", (oid, valeur_id))
    conn.commit()


@app.get("/api/personnages/{personnage_id}/attributs")
def list_personnage_attributs(personnage_id: int, conn: sqlite3.Connection = Depends(db)):
    _get_personnage(conn, personnage_id)
    return _attributs_de(conn, "personnage_attribut", "personnage_id", personnage_id)


@app.put("/api/personnages/{personnage_id}/attributs")
def add_personnage_attribut(personnage_id: int, payload: AttributIn,
                            conn: sqlite3.Connection = Depends(db)):
    _get_personnage(conn, personnage_id)
    _affecter(conn, "personnage_attribut", "personnage_id", personnage_id, payload.valeur_id, "personnage")
    return _attributs_de(conn, "personnage_attribut", "personnage_id", personnage_id)


@app.delete("/api/personnages/{personnage_id}/attributs/{valeur_id}", status_code=204)
def remove_personnage_attribut(personnage_id: int, valeur_id: int,
                               conn: sqlite3.Connection = Depends(db)):
    conn.execute("DELETE FROM personnage_attribut WHERE personnage_id = ? AND valeur_id = ?",
                 (personnage_id, valeur_id))
    conn.commit()


@app.get("/api/regions/{region_id}/attributs")
def list_region_attributs(region_id: int, conn: sqlite3.Connection = Depends(db)):
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    return _attributs_de(conn, "region_attribut", "region_id", region_id)


@app.put("/api/regions/{region_id}/attributs")
def add_region_attribut(region_id: int, payload: AttributIn,
                        conn: sqlite3.Connection = Depends(db)):
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    _affecter(conn, "region_attribut", "region_id", region_id, payload.valeur_id, "case")
    return _attributs_de(conn, "region_attribut", "region_id", region_id)


@app.delete("/api/regions/{region_id}/attributs/{valeur_id}", status_code=204)
def remove_region_attribut(region_id: int, valeur_id: int,
                           conn: sqlite3.Connection = Depends(db)):
    conn.execute("DELETE FROM region_attribut WHERE region_id = ? AND valeur_id = ?",
                 (region_id, valeur_id))
    conn.commit()


# =========================================================================== #
# Recherche plein texte (FTS5)
# =========================================================================== #
def _recherche_rows(conn, q, album, type, tags, pos, lemme, morph, provenance, limit, tag_scope="propre",
                    personnage=None, attributs=None):
    """Construit et exécute la requête de recherche (régions + contexte, tags joints).
    Partagé par /api/recherche (JSON) et l'export CSV — une seule logique de requête."""
    where, params = [], []

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
              limit: int = 100, conn: sqlite3.Connection = Depends(db)):
    limit = max(1, min(limit, 500))   # borne : évite LIMIT -1 (= tout le corpus) / DoS
    results = _recherche_rows(conn, q, album, type, tags, pos, lemme, morph, provenance, limit, tag_scope,
                              personnage, attributs)
    return {"q": q, "count": len(results), "results": results}


_BOM = chr(0xFEFF)   # BOM UTF-8 : permet à Excel (Windows) de lire les accents correctement


def _csv_response(contenu: str, filename: str) -> Response:
    """Réponse CSV téléchargeable, préfixée d'un BOM UTF-8 pour qu'Excel (Windows) lise
    correctement les accents français. (R/pandas : lire en `utf-8-sig`.)"""
    return Response(content=_BOM + contenu, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/recherche/export.csv")
def recherche_export(q: str = "", album: Optional[int] = None,
                     type: Optional[str] = None, tags: Optional[list[str]] = Query(None),
                     pos: Optional[str] = None, lemme: Optional[str] = None,
                     morph: Optional[str] = None, provenance: Optional[str] = None,
                     tag_scope: str = "propre",
                     personnage: Optional[int] = None, attributs: Optional[list[int]] = Query(None),
                     conn: sqlite3.Connection = Depends(db)):
    """Export CSV du jeu de résultats courant (mêmes critères que /api/recherche).
    Borne haute relevée (5000) : on exporte le jeu trouvé, pas seulement l'aperçu."""
    results = _recherche_rows(conn, q, album, type, tags, pos, lemme, morph, provenance, 5000, tag_scope,
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
        w.writerow({"album": r["album_titre"],
                    "planche": planche if planche is not None else "",
                    "citation": cit.get("texte", ""),
                    "region_id": r["region_id"], "type": r["type"],
                    "ocr_texte": r["ocr_texte"] or "", "note": r["note"] or "",
                    "tags": "|".join(r["tags"])})
    return _csv_response(buf.getvalue(), "recherche.csv")


@app.get("/api/corpus")
def corpus_stats(conn: sqlite3.Connection = Depends(db)):
    """Compteurs globaux du corpus (pour l'aperçu de la page de recherche)."""
    row = conn.execute(
        """SELECT
             (SELECT COUNT(*) FROM albums)   AS albums,
             (SELECT COUNT(*) FROM planches) AS planches,
             (SELECT COUNT(*) FROM regions)  AS regions,
             (SELECT COUNT(*) FROM annotations) AS annotees,
             (SELECT COUNT(*) FROM regions
                WHERE TRIM(COALESCE(ocr_texte, '')) <> '') AS transcrites,
             (SELECT COUNT(*) FROM tags) AS tags,
             (SELECT COUNT(*) FROM planches WHERE validee IS NOT NULL) AS validees"""
    ).fetchone()
    res = dict(row)
    # Distribution des planches par statut (pour la barre d'avancement du corpus).
    res["statuts"] = {s: 0 for s in STATUTS}
    for r in conn.execute("SELECT statut, COUNT(*) AS n FROM planches GROUP BY statut"):
        if r["statut"] in res["statuts"]:
            res["statuts"][r["statut"]] = r["n"]
    return res


# =========================================================================== #
# Analyse grammaticale (Palier B) — fréquences lexicales + tokens par région
# =========================================================================== #
def _analyse_filtres(album, type, pos, lemme, morph, provenance, tags=None, tag_scope="herite",
                     personnage=None, attributs=None):
    """Clauses WHERE communes aux requêtes par token (sur la vue `tokens_effectifs` te,
    jointe à regions r / planches p). Valeurs EFFECTIVES (correction humaine ⊕ auto)."""
    where, params = [], []
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
    return where, params


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
                       provenance: Optional[str] = None,
                       tags: Optional[list[str]] = Query(None), tag_scope: str = "herite",
                       personnage: Optional[int] = None, attributs: Optional[list[int]] = Query(None),
                       limit: int = 100,
                       conn: sqlite3.Connection = Depends(db)):
    """Distributions de fréquence sur les valeurs EFFECTIVES. `champ` : `lemme`
    (défaut, groupé avec son POS) | `pos` | `morph`. Filtres : album, type de région,
    pos, lemme, morph (sous-chaîne UD), provenance. Base des champs lexicaux et
    distributions (Exploration)."""
    if champ not in ("lemme", "pos", "morph"):
        raise HTTPException(422, "champ invalide (lemme | pos | morph).")
    limit = max(1, min(limit, 1000))
    _valider_facette(conn, personnage, attributs)
    where, params = _analyse_filtres(album, type, pos, lemme, morph, provenance, tags, tag_scope,
                                     personnage, attributs)
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
                        album: Optional[int] = None, type: Optional[str] = None,
                        tags: Optional[list[str]] = Query(None), tag_scope: str = "herite",
                        personnage: Optional[int] = None, attributs: Optional[list[int]] = Query(None),
                        limit: int = 200, conn: sqlite3.Connection = Depends(db)):
    """Concordance grammaticale : occurrences de tokens (valeurs EFFECTIVES) répondant
    aux critères, AVEC leur contexte (région, planche, album, texte OCR) — pour montrer
    chaque emploi en contexte multimodal (socle de Recherche+++). Au moins un critère
    grammatical (lemme / pos / morph) est requis."""
    if not (lemme or pos or morph or tags or personnage or attributs):
        raise HTTPException(422, "Préciser au moins un critère (grammatical, tag, personnage ou attribut).")
    limit = max(1, min(limit, 500))
    _valider_facette(conn, personnage, attributs)
    where, params = _analyse_filtres(album, type, pos, lemme, morph, provenance, tags, tag_scope,
                                     personnage, attributs)
    if not where:   # critères fournis mais aucun effectif (p.ex. tag vide) → évite un « WHERE » vide
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


def _distribution(conn, champ, album, type, pos, morph, provenance, tags=None, tag_scope="herite",
                  personnage=None, attributs=None):
    """Compte {valeur: fréquence} d'un champ (lemme|pos|morph) sur un sous-corpus, et
    le total. Sur les valeurs EFFECTIVES. `champ` doit être validé par l'appelant."""
    where, params = _analyse_filtres(album, type, pos, None, morph, provenance, tags, tag_scope,
                                     personnage, attributs)
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
                        a_provenance: Optional[str] = None, a_tags: Optional[list[str]] = Query(None),
                        b_album: Optional[int] = None, b_type: Optional[str] = None,
                        b_pos: Optional[str] = None, b_morph: Optional[str] = None,
                        a_personnage: Optional[int] = None, a_attributs: Optional[list[int]] = Query(None),
                        b_provenance: Optional[str] = None, b_tags: Optional[list[str]] = Query(None),
                        b_personnage: Optional[int] = None, b_attributs: Optional[list[int]] = Query(None),
                        tag_scope: str = "herite",
                        limit: int = 50, conn: sqlite3.Connection = Depends(db)):
    """Compare deux sous-corpus A et B : valeurs (lemme|pos|morph) les plus
    SUR-représentées dans chacun, par différence de fréquence RELATIVE (rel = freq /
    total du sous-corpus → comparable malgré des tailles différentes)."""
    if champ not in ("lemme", "pos", "morph"):
        raise HTTPException(422, "champ invalide (lemme | pos | morph).")
    limit = max(1, min(limit, 200))
    _valider_facette(conn, a_personnage, a_attributs)
    _valider_facette(conn, b_personnage, b_attributs)
    da, ta = _distribution(conn, champ, a_album, a_type, a_pos, a_morph, a_provenance, a_tags, tag_scope,
                           a_personnage, a_attributs)
    db_, tb = _distribution(conn, champ, b_album, b_type, b_pos, b_morph, b_provenance, b_tags, tag_scope,
                            b_personnage, b_attributs)
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


@app.get("/api/regions/{region_id}/tokens")
def region_tokens(region_id: int, conn: sqlite3.Connection = Depends(db)):
    """Analyse grammaticale d'une région : ses mots avec lemme / POS / morphologie."""
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    return _tokens_effectifs(conn, region_id)


def _tokens_effectifs(conn, region_id: int) -> list:
    """Tokens EFFECTIFS d'une région (correction humaine ⊕ auto) + provenance —
    jamais `tokens` brut (invariant projet)."""
    return _rows(conn.execute(
        "SELECT ordre, texte, lemme, pos, morph, provenance, a_revoir, "
        "       corr_lemme, corr_pos, corr_morph "
        "FROM tokens_effectifs WHERE region_id = ? ORDER BY ordre", (region_id,)))


def _norm_corr(v: Optional[str]) -> Optional[str]:
    """'' / espaces → None : un champ non corrigé doit être NULL (sinon la vue
    interpréterait '' comme un override « valeur vide »)."""
    v = (v or "").strip()
    return v or None


@app.put("/api/regions/{region_id}/tokens/{ordre}")
def corriger_token(region_id: int, ordre: int, payload: TokenCorrectionIn,
                   conn: sqlite3.Connection = Depends(db)):
    """Corrige (ou valide) UN token : impose lemme/POS/morph et/ou marque l'état.
    Champ absent/vide = NULL = auto accepté. POS contrôlé (UPOS). La correction est
    ancrée sur la FORME actuelle du token (anti-dérive ; cf. docs/correction-grammaticale.md)."""
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
    conn.execute(
        "INSERT INTO token_correction "
        "  (region_id, ordre, forme, lemme, pos, morph, etat, obsolete, date_modif) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 0, datetime('now')) "
        "ON CONFLICT(region_id, ordre) DO UPDATE SET "
        "  forme=excluded.forme, lemme=excluded.lemme, pos=excluded.pos, "
        "  morph=excluded.morph, etat=excluded.etat, obsolete=0, date_modif=datetime('now')",
        (region_id, ordre, tok["texte"], lemme, pos, morph, payload.etat))
    reindex_region(conn, region_id)      # FTS reflète la correction ; ancrage re-vérifié
    conn.commit()
    return _tokens_effectifs(conn, region_id)


@app.post("/api/regions/{region_id}/grammaire/valider")
def valider_grammaire(region_id: int, conn: sqlite3.Connection = Depends(db)):
    """Valide tous les tokens de la région (etat='valide') — geste courant des
    linguistes. Garde les corrections existantes (non obsolètes) et accepte l'auto
    ailleurs ; ne touche pas aux corrections « à revérifier ». NON bloquant : c'est
    une assertion de qualité, jamais un prérequis."""
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    nlp.ensure_loaded()          # spaCy hors transaction (cf. corriger_token)
    reindex_region(conn, region_id)   # ré-ancre (aligne) d'abord → nettoie toute dérive du texte
    # 1) corrections cohérentes existantes → validées
    conn.execute("UPDATE token_correction SET etat='valide', date_modif=datetime('now') "
                 "WHERE region_id = ? AND obsolete = 0", (region_id,))
    # 2) tokens sans correction → ligne 'valide' (accepte l'auto, valeurs NULL)
    conn.execute(
        "INSERT INTO token_correction (region_id, ordre, forme, etat, obsolete) "
        "SELECT t.region_id, t.ordre, t.texte, 'valide', 0 FROM tokens t "
        "WHERE t.region_id = ? AND NOT EXISTS "
        "  (SELECT 1 FROM token_correction c WHERE c.region_id=t.region_id AND c.ordre=t.ordre)",
        (region_id,))
    conn.commit()
    return _tokens_effectifs(conn, region_id)


@app.delete("/api/regions/{region_id}/tokens/{ordre}")
def annuler_correction(region_id: int, ordre: int,
                       conn: sqlite3.Connection = Depends(db)):
    """Annule la correction d'un token → retour à l'auto pur (retire aussi le lemme
    corrigé du FTS)."""
    nlp.ensure_loaded()   # charge spaCy HORS transaction (le reindex qui suit ne tiendra pas le verrou pendant le cold-load)
    cur = conn.execute("DELETE FROM token_correction WHERE region_id = ? AND ordre = ?",
                       (region_id, ordre))
    if cur.rowcount:
        reindex_region(conn, region_id)
    conn.commit()
    return _tokens_effectifs(conn, region_id)


@app.get("/api/analyse/info")
def analyse_info(conn: sqlite3.Connection = Depends(db)):
    """État de l'index linguistique : modèle NLP utilisé (reproductibilité),
    date de réindexation, et volumétrie. La réindexation en lot se lance via
    `tools/reindex_nlp.py` (modèle configurable BD_SPACY_MODEL)."""
    meta = {r["cle"]: r["valeur"] for r in conn.execute("SELECT cle, valeur FROM meta")}
    nb_tokens = conn.execute("SELECT COUNT(*) AS n FROM tokens").fetchone()["n"]
    nb_lemmes = conn.execute(
        "SELECT COUNT(*) AS n FROM recherche WHERE lemmes <> ''").fetchone()["n"]
    return {"moteur_disponible": nlp.nlp_available(),
            "modele_configure": nlp.configured_model(),   # léger : pas de chargement du modèle
            "meta": meta, "tokens": nb_tokens, "regions_lemmatisees": nb_lemmes}


# =========================================================================== #
# Jobs : traitement par lot en arrière-plan (segmentation / bulles / OCR)
# =========================================================================== #
@app.post("/api/jobs", status_code=201)
def creer_job(payload: JobIn, conn: sqlite3.Connection = Depends(db)):
    """Lance un lot sur l'ensemble des planches d'albums et/ou planches données."""
    passes = [p for p in jobs.PASSES if p in payload.passes]   # ordre canonique
    if not passes:
        raise HTTPException(422, "Aucune passe valide (segmenter / bulles / ocr).")
    avail = {"segmenter": kumiko_available(), "bulles": bulles_available(),
             "ocr": ocr_available()}
    manquants = [p for p in passes if not avail[p]]
    if manquants:
        raise HTTPException(503, f"Moteur(s) indisponible(s) : {', '.join(manquants)}.")

    pids = set(payload.planche_ids)
    for aid in payload.album_ids:
        pids.update(r["id"] for r in conn.execute(
            "SELECT id FROM planches WHERE album_id = ?", (aid,)).fetchall())
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


@app.get("/api/jobs")
def lister_jobs():
    return jobs.all_jobs()


@app.get("/api/jobs/{job_id}")
def etat_job(job_id: int):
    snap = jobs.snapshot(job_id)
    if snap is None:
        raise HTTPException(404, f"Job {job_id} introuvable")
    return snap


@app.post("/api/jobs/{job_id}/annuler")
def annuler_job(job_id: int):
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


def _album_payload(conn: sqlite3.Connection, album_id: int) -> dict:
    album = _row(conn.execute("SELECT * FROM albums WHERE id = ?", (album_id,)))
    if album is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
    planches = _rows(conn.execute(
        "SELECT * FROM planches WHERE album_id = ? ORDER BY numero", (album_id,)))
    nums = numeros_editoriaux(conn, album_id)
    for p in planches:
        p["numero_editorial"] = nums.get(p["id"])   # None si paratexte ; `role` déjà présent
        regions = _rows(conn.execute(
            "SELECT * FROM regions WHERE planche_id = ?", (p["id"],)))
        p["regions"] = _region_tree(regions, conn)
    album["planches"] = planches
    return album


@app.get("/api/export/json")
def export_json(album_id: int, conn: sqlite3.Connection = Depends(db)):
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
def export_csv(album_id: int, conn: sqlite3.Connection = Depends(db)):
    if conn.execute("SELECT 1 FROM albums WHERE id = ?", (album_id,)).fetchone() is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
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
def export_tei(album_id: int, conn: sqlite3.Connection = Depends(db)):
    album = _row(conn.execute("SELECT * FROM albums WHERE id = ?", (album_id,)))
    if album is None:
        raise HTTPException(404, f"Album {album_id} introuvable")

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
    _tei_el(pub, "publisher").text = _xml_safe(album["editeur"] or "BD Annotator")
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
def sante():
    return {"kumiko": kumiko_available(),
            "bulles": bulles_available(),
            "ocr": ocr_available(),
            "lemmes": nlp.nlp_available()}


# Fichiers statiques + images dérivées + shell HTML.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/derivatives", StaticFiles(directory=str(DERIVATIVES_DIR)),
          name="derivatives")


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
