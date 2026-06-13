"""Ingestion d'une planche : master (TIFF) → dérivé web + métadonnées en base.

Étapes :
  1. Ouvrir le master avec Pillow, lire métadonnées (DPI, dimensions, mode).
  2. Générer le dérivé web : resize à WEB_SCALE (25 %), JPEG qualité 82.
  3. Stocker chemins (relatifs, en POSIX) et dimensions MASTER en base.
  4. Retourner la ligne `planches` créée.

Les coordonnées des régions sont toujours stockées en pixels MASTER ; c'est
pourquoi `planches.largeur_px / hauteur_px` contiennent les dimensions du
master, pas du dérivé. Le frontend recalcule `web_scale` à partir de la
largeur naturelle de l'image web chargée.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from PIL import Image

from config import (CORPUS_DIR, DATA_DIR, DERIVATIVES_DIR, MAX_IMAGE_PIXELS,
                    WEB_JPEG_QUALITY, WEB_SCALE)

# Garde anti-bombe de décompression : on relève la limite Pillow à une valeur
# large (couvre les scans 400-600 dpi) mais bornée — surtout pas None, qui
# désactiverait la protection et exposerait à un OOM sur image-bombe.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def _rel_posix(path: Path) -> str:
    """Chemin relatif à DATA_DIR, en séparateurs POSIX (sûr pour les URL)."""
    return path.resolve().relative_to(DATA_DIR).as_posix()


def _next_numero(conn: sqlite3.Connection, album_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(numero), 0) + 1 AS n FROM planches WHERE album_id = ?",
        (album_id,),
    ).fetchone()
    return int(row["n"])


def read_metadata(source: Path) -> dict:
    """Lit dimensions, mode couleur et DPI d'une image sans la convertir."""
    with Image.open(source) as img:
        dpi = img.info.get("dpi")
        # dpi peut être scalaire (300) ou non numérique selon l'encodeur :
        # normalise en paire d'entiers, ou None si illisible (image valide quand même).
        if dpi is not None and not isinstance(dpi, (tuple, list)):
            dpi = (dpi, dpi)
        try:
            dpi = tuple(round(d) for d in dpi) if dpi else None
        except (TypeError, ValueError):
            dpi = None
        return {
            "largeur": img.width,
            "hauteur": img.height,
            "mode": img.mode,
            "dpi": dpi,
        }


def make_web_derivative(source: Path, dest: Path,
                        scale: float = WEB_SCALE,
                        quality: int = WEB_JPEG_QUALITY) -> tuple[int, int]:
    """Génère le dérivé web JPEG et retourne ses dimensions (largeur, hauteur)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as img:
        # JPEG ne gère que RGB / L : on convertit CMYK, 16 bits, palette, etc.
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        w = max(1, round(img.width * scale))
        h = max(1, round(img.height * scale))
        web = img.resize((w, h), Image.LANCZOS)
        web.save(dest, "JPEG", quality=quality, optimize=True)
        return w, h


def ingest_image(conn: sqlite3.Connection, album_id: int, source: Path,
                 numero: int | None = None,
                 keep_master: bool = True) -> dict:
    """Ingère un fichier image (master) et crée la planche associée.

    `source` doit être un fichier déjà présent sur le disque (typiquement
    déposé dans corpus/ par la route d'import). Retourne un dict représentant
    la ligne `planches` créée.
    """
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"Master introuvable : {source}")

    album = conn.execute("SELECT id FROM albums WHERE id = ?", (album_id,)).fetchone()
    if album is None:
        raise ValueError(f"Album {album_id} inexistant")

    if numero is None:
        numero = _next_numero(conn, album_id)

    meta = read_metadata(source)

    # Dérivé web : derivatives/album_<id>/planche_<numero>.jpg
    web_path = DERIVATIVES_DIR / f"album_{album_id}" / f"planche_{numero:04d}.jpg"
    make_web_derivative(source, web_path)

    # Master : conservé tel quel (déjà dans corpus/) ou référencé.
    chemin_tiff = _rel_posix(source) if keep_master else None
    chemin_web = _rel_posix(web_path)

    cur = conn.execute(
        """
        INSERT INTO planches
            (album_id, numero, chemin_tiff, chemin_web,
             largeur_px, hauteur_px, statut)
        VALUES (?, ?, ?, ?, ?, ?, 'importee')
        """,
        (album_id, numero, chemin_tiff, chemin_web,
         meta["largeur"], meta["hauteur"]),
    )
    planche_id = cur.lastrowid

    return {
        "id": planche_id,
        "album_id": album_id,
        "numero": numero,
        "chemin_tiff": chemin_tiff,
        "chemin_web": chemin_web,
        "largeur_px": meta["largeur"],
        "hauteur_px": meta["hauteur"],
        "statut": "importee",
        "dpi": meta["dpi"],
        "mode": meta["mode"],
    }


def remove_album_files(album_id: int) -> None:
    """Supprime les dossiers corpus/derivatives d'un album (best-effort)."""
    import shutil
    shutil.rmtree(CORPUS_DIR / f"album_{album_id}", ignore_errors=True)
    shutil.rmtree(DERIVATIVES_DIR / f"album_{album_id}", ignore_errors=True)


def remove_planche_files(chemin_tiff: str | None, chemin_web: str | None) -> None:
    """Supprime le master et le dérivé web d'une planche (best-effort)."""
    for rel in (chemin_tiff, chemin_web):
        if rel:
            try:
                (DATA_DIR / rel).unlink(missing_ok=True)
            except OSError:  # pragma: no cover - garde défensive (permissions…)
                pass


def store_upload(album_id: int, filename: str, data: bytes,
                 numero: int | None = None) -> Path:
    """Écrit un fichier importé dans corpus/album_<id>/ et retourne son chemin."""
    suffix = Path(filename).suffix or ".tif"
    folder = CORPUS_DIR / f"album_{album_id}"
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"planche_{numero:04d}" if numero is not None else Path(filename).stem
    dest = folder / f"{stem}{suffix}"
    dest.write_bytes(data)
    return dest
