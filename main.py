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
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from typing import Iterator, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import DERIVATIVES_DIR, STATIC_DIR, STATUTS, TEMPLATES_DIR, TYPES_REGION
from database import get_connection, init_db, reindex_region, unindex_region
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
    yield


app = FastAPI(title="BD Annotator", version="1.0", lifespan=lifespan)


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


# --------------------------------------------------------------------------- #
# Helpers métier
# --------------------------------------------------------------------------- #
def _norm_tag(label: str) -> str:
    """Tags insensibles à la casse, stockés en minuscules, espaces compactés."""
    return " ".join(label.strip().lower().split())


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
    for p in planches:
        p["url_web"] = "/" + p["chemin_web"] if p["chemin_web"] else None
    return planches


# Route synchrone (def) : FastAPI l'exécute dans un threadpool, ce qui évite
# de bloquer la boucle d'événements pendant le redimensionnement PIL (lourd
# sur un TIFF 400 dpi). On lit donc l'upload via file.file (API synchrone).
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
    # Numéro fixé en amont pour aligner les noms master/dérivé web.
    if numero is None:
        numero = conn.execute(
            "SELECT COALESCE(MAX(numero), 0) + 1 AS n FROM planches "
            "WHERE album_id = ?", (album_id,),
        ).fetchone()["n"]
    master = store_upload(album_id, file.filename or "planche.tif", data, numero)
    try:
        planche = ingest_image(conn, album_id, master, numero=numero)
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
    _get_planche(conn, planche_id)
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
    _get_planche(conn, planche_id)
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
    _get_planche(conn, planche_id)
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
            numero = conn.execute(
                "SELECT COALESCE(MAX(numero), 0) + 1 AS n FROM planches "
                "WHERE album_id = ?", (album_id,)).fetchone()["n"]
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
# Recherche plein texte (FTS5)
# =========================================================================== #
@app.get("/api/recherche")
def recherche(q: str = "", album: Optional[int] = None,
              type: Optional[str] = None, tags: Optional[list[str]] = Query(None),
              limit: int = 100, conn: sqlite3.Connection = Depends(db)):
    limit = max(1, min(limit, 500))   # borne : évite LIMIT -1 (= tout le corpus) / DoS
    where, params = [], []

    base = (
        "SELECT r.id AS region_id, r.type, r.x, r.y, r.w, r.h, r.ocr_texte, "
        "       p.id AS planche_id, p.numero AS planche_numero, "
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
        # un paramètre `tags` par tag (robuste aux virgules dans les labels)
        wanted = [_norm_tag(t) for t in tags if _norm_tag(t)]
        for label in wanted:
            where.append(
                "EXISTS (SELECT 1 FROM annotation_tags at "
                "        JOIN tags tg ON tg.id = at.tag_id "
                "        JOIN annotations a2 ON a2.id = at.annotation_id "
                "        WHERE a2.region_id = r.id AND tg.label = ?)"
            )
            params.append(label)

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
    return {"q": q, "count": len(results), "results": results}


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
@app.get("/api/analyse/lemmes")
def analyse_lemmes(album: Optional[int] = None, type: Optional[str] = None,
                   pos: Optional[str] = None, limit: int = 100,
                   conn: sqlite3.Connection = Depends(db)):
    """Fréquences lexicales : lemmes les plus fréquents (sur les `tokens` spaCy).
    Filtres : `album`, `type` de région, catégorie grammaticale `pos`
    (NOUN/VERB/ADJ/…). Base des champs lexicaux et études de fréquence."""
    limit = max(1, min(limit, 1000))
    where, params = [], []
    if album is not None:
        where.append("p.album_id = ?"); params.append(album)
    if type:
        where.append("r.type = ?"); params.append(type)
    if pos:
        where.append("t.pos = ?"); params.append(pos.upper())
    sql = ("SELECT t.lemme, t.pos, COUNT(*) AS freq "
           "FROM tokens t JOIN regions r ON r.id = t.region_id "
           "JOIN planches p ON p.id = r.planche_id ")
    if where:
        sql += "WHERE " + " AND ".join(where) + " "
    sql += "GROUP BY t.lemme, t.pos ORDER BY freq DESC, t.lemme LIMIT ?"
    params.append(limit)
    return {"results": _rows(conn.execute(sql, params))}


@app.get("/api/regions/{region_id}/tokens")
def region_tokens(region_id: int, conn: sqlite3.Connection = Depends(db)):
    """Analyse grammaticale d'une région : ses mots avec lemme / POS / morphologie."""
    if conn.execute("SELECT 1 FROM regions WHERE id = ?", (region_id,)).fetchone() is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    return _rows(conn.execute(
        "SELECT ordre, texte, lemme, pos, morph FROM tokens "
        "WHERE region_id = ? ORDER BY ordre", (region_id,)))


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
    valid = []
    if pids:
        ph = ",".join("?" * len(pids))
        valid = [r["id"] for r in conn.execute(
            f"SELECT id FROM planches WHERE id IN ({ph}) ORDER BY album_id, numero",
            tuple(pids)).fetchall()]
    if not valid:
        raise HTTPException(422, "Aucune planche à traiter.")
    return jobs.start_job(passes, valid)


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

    def build(parent_id):
        nodes = []
        for r in sorted(by_parent.get(parent_id, []),
                        key=lambda x: (x["ordre"] or 0, x["id"])):
            ann = _annotation_for_region(conn, r["id"])
            nodes.append({
                "id": r["id"], "type": r["type"],
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
    for p in planches:
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
        """SELECT a.titre AS album, p.numero AS planche, r.id AS region_id,
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
    buf = io.StringIO()
    cols = ["album", "planche", "region_id", "type", "parent_id",
            "x", "y", "w", "h", "ordre", "source", "ocr_texte", "note", "tags"]
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        buf.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":
                 f'attachment; filename="album_{album_id}.csv"'},
    )


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

    for p in planches:
        surface = _tei_el(facsimile, "surface", ulx="0", uly="0",
                          lrx=p["largeur_px"], lry=p["hauteur_px"])
        surface.set(f"{{{XML_NS}}}id", f"planche_{p['id']}")
        surface.set("n", str(p["numero"]))
        if p["chemin_web"]:
            _tei_el(surface, "graphic", url="/" + p["chemin_web"])

        regions = _rows(conn.execute(
            "SELECT * FROM regions WHERE planche_id = ?", (p["id"],)))
        by_parent: dict = {}
        for r in regions:
            by_parent.setdefault(r["parent_id"], []).append(r)

        def add_zones(container, parent_id):
            for r in sorted(by_parent.get(parent_id, []),
                            key=lambda x: (x["ordre"] or 0, x["id"])):
                zone = _tei_el(container, "zone",
                               ulx=r["x"], uly=r["y"],
                               lrx=(r["x"] or 0) + (r["w"] or 0),
                               lry=(r["y"] or 0) + (r["h"] or 0))
                zone.set(f"{{{XML_NS}}}id", f"zone_{r['id']}")
                zone.set("type", r["type"])
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
