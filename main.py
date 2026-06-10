"""BD Annotator — application FastAPI (routes albums, planches, régions,
annotations, recherche, export).

Lancer :  uvicorn main:app --reload
"""
from __future__ import annotations

import csv
import io
import sqlite3
import xml.etree.ElementTree as ET
from typing import Iterator, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import (DERIVATIVES_DIR, STATIC_DIR, STATUTS,
                    TEMPLATES_DIR, TYPES_REGION)
from database import get_connection, init_db, reindex_region, unindex_region
from pipeline.ingest import ingest_image, store_upload
from pipeline.segmentation import KumikoError, kumiko_available, segment_planche

app = FastAPI(title="BD Annotator", version="1.0")


# --------------------------------------------------------------------------- #
# Cycle de vie + dépendance connexion
# --------------------------------------------------------------------------- #
@app.on_event("startup")
def _startup() -> None:
    init_db()


def db() -> Iterator[sqlite3.Connection]:
    """Une connexion par requête : commit si succès, rollback sinon."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
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


class RegionIn(BaseModel):
    type: str
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    parent_id: Optional[int] = None
    ordre: Optional[int] = None
    ocr_texte: Optional[str] = None
    source: str = "manuel"


class RegionUpdate(BaseModel):
    type: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    w: Optional[int] = None
    h: Optional[int] = None
    parent_id: Optional[int] = None
    ordre: Optional[int] = None
    ocr_texte: Optional[str] = None
    source: Optional[str] = None


class StatutIn(BaseModel):
    statut: str


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


# =========================================================================== #
# Albums & planches
# =========================================================================== #
@app.get("/api/albums")
def list_albums(conn: sqlite3.Connection = Depends(db)):
    return _rows(conn.execute(
        """SELECT a.*,
                  (SELECT COUNT(*) FROM planches p WHERE p.album_id = a.id)
                      AS nb_planches
           FROM albums a
           ORDER BY a.serie IS NULL, a.serie, a.annee, a.titre"""
    ))


@app.post("/api/albums", status_code=201)
def create_album(album: AlbumIn, conn: sqlite3.Connection = Depends(db)):
    cur = conn.execute(
        "INSERT INTO albums (titre, auteur, annee, editeur, serie) "
        "VALUES (?, ?, ?, ?, ?)",
        (album.titre, album.auteur, album.annee, album.editeur, album.serie),
    )
    return _row(conn.execute("SELECT * FROM albums WHERE id = ?", (cur.lastrowid,)))


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


@app.post("/api/albums/{album_id}/import", status_code=201)
async def import_planche(
    album_id: int,
    file: UploadFile = File(...),
    numero: Optional[int] = Form(None),
    conn: sqlite3.Connection = Depends(db),
):
    if conn.execute("SELECT 1 FROM albums WHERE id = ?", (album_id,)).fetchone() is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
    data = await file.read()
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
        raise HTTPException(400, f"Échec de l'ingestion : {exc}")
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
        return segment_planche(conn, planche_id, use_master=use_master)
    except KumikoError as exc:
        raise HTTPException(500, str(exc))


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
    return _row(conn.execute("SELECT * FROM regions WHERE id = ?", (new_id,)))


@app.put("/api/regions/{region_id}")
def update_region(region_id: int, patch: RegionUpdate,
                  conn: sqlite3.Connection = Depends(db)):
    existing = _row(conn.execute("SELECT * FROM regions WHERE id = ?", (region_id,)))
    if existing is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    fields = patch.model_dump(exclude_unset=True)
    if "type" in fields and fields["type"] not in TYPES_REGION:
        raise HTTPException(422, f"Type invalide : {fields['type']}")
    if fields:
        cols = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE regions SET {cols} WHERE id = ?",
                     (*fields.values(), region_id))
        if "ocr_texte" in fields:
            reindex_region(conn, region_id)
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
               UNION ALL
               SELECT r.id FROM regions r JOIN d ON r.parent_id = d.id
           ) SELECT id FROM d""",
        (region_id,),
    ).fetchall()
    for r in descendants:
        unindex_region(conn, r["id"])
    conn.execute("DELETE FROM regions WHERE id = ?", (region_id,))
    return Response(status_code=204)


@app.patch("/api/planches/{planche_id}/statut")
def update_statut(planche_id: int, payload: StatutIn,
                  conn: sqlite3.Connection = Depends(db)):
    _get_planche(conn, planche_id)
    if payload.statut not in STATUTS:
        raise HTTPException(422, f"Statut invalide : {payload.statut}")
    conn.execute("UPDATE planches SET statut = ? WHERE id = ?",
                 (payload.statut, planche_id))
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
    tag_rows = _ensure_tags(conn, payload.tags)
    conn.execute("DELETE FROM annotation_tags WHERE annotation_id = ?", (ann_id,))
    for t in tag_rows:
        conn.execute(
            "INSERT OR IGNORE INTO annotation_tags (annotation_id, tag_id) "
            "VALUES (?, ?)", (ann_id, t["id"]),
        )

    reindex_region(conn, region_id)
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
    return _row(conn.execute("SELECT * FROM tags WHERE label = ?", (label,)))


# =========================================================================== #
# Recherche plein texte (FTS5)
# =========================================================================== #
@app.get("/api/recherche")
def recherche(q: str = "", album: Optional[int] = None,
              type: Optional[str] = None, tags: Optional[str] = None,
              limit: int = 100, conn: sqlite3.Connection = Depends(db)):
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
        # Échappe chaque token et les combine en ET implicite (préfixe sûr).
        match_expr = " ".join('"' + t.replace('"', '""') + '"'
                              for t in q.split())
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
        wanted = [_norm_tag(t) for t in tags.split(",") if _norm_tag(t)]
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
    _tei_el(title_stmt, "title").text = album["titre"]
    if album["auteur"]:
        _tei_el(title_stmt, "author").text = album["auteur"]
    pub = _tei_el(file_desc, "publicationStmt")
    _tei_el(pub, "publisher").text = album["editeur"] or "BD Annotator"
    src = _tei_el(file_desc, "sourceDesc")
    _tei_el(src, "p").text = (
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
                    _tei_el(zone, "line").text = r["ocr_texte"]
                ann = _annotation_for_region(conn, r["id"])
                if ann["note"] or ann["tags"]:
                    note = _tei_el(zone, "note")
                    if ann["tags"]:
                        note.set("type", "tags")
                        note.set("ana", " ".join(t["label"] for t in ann["tags"]))
                    note.text = ann["note"] or ""
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
    return {"kumiko": kumiko_available()}


# Fichiers statiques + images dérivées + shell HTML.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/derivatives", StaticFiles(directory=str(DERIVATIVES_DIR)),
          name="derivatives")


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(str(TEMPLATES_DIR / "index.html"))
