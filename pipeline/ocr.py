"""Passe 3 — OCR par région de texte (pré-remplissage de `ocr_texte`).

Pour chaque région porteuse de texte (bulle / cartouche / texte), on recadre la
zone dans l'image MASTER (meilleure résolution) et on l'OCR avec EasyOCR. Le
texte reconnu n'est qu'un PRÉ-REMPLISSAGE éditable : l'humain le corrige dans le
mode Annotation. Par défaut on ne traite que les régions encore vides
(`only_empty=True`) pour ne JAMAIS écraser une correction humaine.

Moteur OPTIONNEL : si easyocr n'est pas installé, la route renvoie 503.
Installation :  pip install -r requirements-ocr.txt
"""
from __future__ import annotations

import importlib.util
import sqlite3
import threading

from config import DATA_DIR, MAX_IMAGE_PIXELS
from database import reindex_region

# Types de régions porteuses de texte.
TEXT_TYPES = ("bulle", "cartouche", "texte")

_reader = None
_reader_langs: tuple | None = None


class OCRError(RuntimeError):
    """Erreur d'OCR (moteur absent, image illisible…)."""


def ocr_available() -> bool:
    return importlib.util.find_spec("easyocr") is not None


def _get_reader(langs):
    global _reader, _reader_langs
    if not ocr_available():
        raise OCRError("OCR indisponible : pip install easyocr "
                       "(voir requirements-ocr.txt).")
    if _reader is None or _reader_langs != tuple(langs):
        import easyocr
        try:
            _reader = easyocr.Reader(list(langs), gpu=False, verbose=False)
        except Exception as exc:  # téléchargement / chargement du modèle
            raise OCRError(f"Chargement du modèle OCR échoué : {exc}") from exc
        _reader_langs = tuple(langs)
    return _reader


def _open_image(planche):
    """Ouvre le master si possible (sinon le dérivé web) ; renvoie (img, scale)
    où scale convertit des pixels MASTER vers les pixels de l'image ouverte."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS   # garde anti-bombe (jamais None)
    if planche["chemin_tiff"] and (DATA_DIR / planche["chemin_tiff"]).is_file():
        img = Image.open(DATA_DIR / planche["chemin_tiff"])
        scale = 1.0
    else:
        img = Image.open(DATA_DIR / planche["chemin_web"])
        scale = img.width / planche["largeur_px"] if planche["largeur_px"] else 1.0
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img, scale


def ocr_planche(conn: sqlite3.Connection, planche_id: int,
                types=TEXT_TYPES, only_empty: bool = True,
                langs=("fr",), min_size: int = 8) -> dict:
    """OCR les régions de texte d'une planche ; renseigne `ocr_texte`.

    Renvoie {'planche_id', 'ocr', 'ignores', 'echecs'}. `only_empty` (défaut)
    saute les régions déjà renseignées — ne jamais écraser une correction.
    """
    planche = conn.execute(
        "SELECT * FROM planches WHERE id = ?", (planche_id,)).fetchone()
    if planche is None:
        raise ValueError(f"Planche {planche_id} inexistante")

    import numpy as np
    reader = _get_reader(langs)
    img, scale = _open_image(planche)

    placeholders = ",".join("?" * len(types))
    rows = conn.execute(
        f"SELECT id, x, y, w, h, ocr_texte FROM regions "
        f"WHERE planche_id = ? AND type IN ({placeholders}) ORDER BY ordre, id",
        (planche_id, *types)).fetchall()

    done = skipped = failed = 0
    try:
        for r in rows:
            if only_empty and (r["ocr_texte"] or "").strip():
                skipped += 1
                continue
            x, y, w, h = (round((r[k] or 0) * scale) for k in ("x", "y", "w", "h"))
            if w < min_size or h < min_size:
                failed += 1
                continue
            crop = img.crop((x, y, x + w, y + h))
            try:  # un crop dégénéré ne doit pas stopper la planche
                lines = reader.readtext(np.array(crop), detail=0, paragraph=True)
                text = "\n".join(lines).strip()
            except Exception:
                failed += 1
                continue
            conn.execute("UPDATE regions SET ocr_texte = ? WHERE id = ?",
                         (text, r["id"]))
            reindex_region(conn, r["id"])
            done += 1
    finally:
        img.close()

    return {"planche_id": planche_id, "ocr": done,
            "ignores": skipped, "echecs": failed}


# --------------------------------------------------------------------------- #
# Crop net d'une région (pour l'affichage en mode Transcription)
# --------------------------------------------------------------------------- #
# Cache 1 image : on garde le master de la dernière planche ouvert, pour que la
# navigation bulle-à-bulle ne ré-ouvre pas un TIFF de 50 Mo à chaque crop.
_crop_cache: dict = {"planche_id": None, "img": None, "scale": 1.0}
_crop_lock = threading.Lock()  # le cache est partagé entre threads du pool


def region_crop_png(conn: sqlite3.Connection, region_id: int,
                    max_dim: int = 1600) -> bytes | None:
    """PNG net de la région recadrée dans le MASTER (sinon le dérivé web).

    Renvoie None si la région est introuvable. Réduit à `max_dim` de large pour
    borner la charge. Cache le master de la planche courante.
    """
    import io
    from PIL import Image

    r = conn.execute(
        "SELECT x, y, w, h, planche_id FROM regions WHERE id = ?", (region_id,)
    ).fetchone()
    if r is None:
        return None

    pid = r["planche_id"]
    with _crop_lock:
        if _crop_cache["planche_id"] != pid:
            planche = conn.execute(
                "SELECT * FROM planches WHERE id = ?", (pid,)).fetchone()
            if planche is None:  # pragma: no cover - une région implique sa planche (FK)
                return None
            if _crop_cache["img"] is not None:
                try:
                    _crop_cache["img"].close()
                except Exception:
                    pass
            img, scale = _open_image(planche)
            _crop_cache.update(planche_id=pid, img=img, scale=scale)

        img, scale = _crop_cache["img"], _crop_cache["scale"]
        x, y, w, h = (round((r[k] or 0) * scale) for k in ("x", "y", "w", "h"))
        crop = img.crop((x, y, x + max(1, w), y + max(1, h)))
        if crop.width > max_dim:
            crop = crop.resize(
                (max_dim, max(1, round(crop.height * max_dim / crop.width))),
                Image.LANCZOS)
        buf = io.BytesIO()
        crop.convert("RGB").save(buf, "PNG")
        return buf.getvalue()
