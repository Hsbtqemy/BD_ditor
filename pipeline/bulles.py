"""Passe 2 — détection automatique des BULLES (régions de texte) dans les cases.

Modèle : `ogkalu/comic-speech-bubble-detector-yolov8m` (YOLOv8, Apache-2.0),
entraîné sur des comics occidentaux + manga (cf. recherche). Chaque bulle est
insérée comme région `type='bulle'`, `source='auto'`, rattachée par GÉOMÉTRIE à
la case qui la contient (parent_id) — sinon parent_id NULL.

Moteur OPTIONNEL (comme Kumiko) : si ultralytics n'est pas installé, la route
renvoie 503. Installation :  pip install -r requirements-ocr.txt
"""
from __future__ import annotations

import importlib.util
import sqlite3

from config import DATA_DIR
from database import unindex_region

HF_REPO = "ogkalu/comic-speech-bubble-detector-yolov8m"
HF_FILE = "comic-speech-bubble-detector.pt"

_model = None


class BullesError(RuntimeError):
    """Erreur de détection des bulles (moteur absent, modèle illisible…)."""


def bulles_available() -> bool:
    return (importlib.util.find_spec("ultralytics") is not None
            and importlib.util.find_spec("huggingface_hub") is not None)


def _load_model():
    global _model
    if _model is None:
        if not bulles_available():
            raise BullesError(
                "Détecteur de bulles indisponible : pip install ultralytics "
                "huggingface_hub (voir requirements-ocr.txt)."
            )
        from huggingface_hub import hf_hub_download
        from ultralytics import YOLO
        _model = YOLO(hf_hub_download(repo_id=HF_REPO, filename=HF_FILE))
    return _model


def _run(image_path, conf: float):
    """Renvoie (orig_w, orig_h, [(x, y, w, h), ...]) en pixels de l'image."""
    res = _load_model().predict(str(image_path), conf=conf, verbose=False)[0]
    oh, ow = res.orig_shape  # (hauteur, largeur)
    boxes = []
    for b in res.boxes:
        x1, y1, x2, y2 = (float(v) for v in b.xyxy[0])
        boxes.append((x1, y1, x2 - x1, y2 - y1))
    return ow, oh, boxes


def _parent_case(cases, cx, cy):
    """Case (la plus petite) contenant le point (cx, cy), sinon None."""
    candidates = [c for c in cases
                  if c["x"] <= cx <= c["x"] + c["w"]
                  and c["y"] <= cy <= c["y"] + c["h"]]
    if not candidates:
        return None
    return min(candidates, key=lambda c: (c["w"] or 0) * (c["h"] or 0))["id"]


def detect_bulles(conn: sqlite3.Connection, planche_id: int,
                  conf: float = 0.3, replace: bool = True) -> dict:
    """Détecte les bulles d'une planche et les insère (rattachées aux cases).

    Renvoie {'planche_id', 'nb_bulles', 'sans_case', 'regions'}. Remplace par
    défaut les bulles 'auto' précédentes (les bulles manuelles sont préservées).
    """
    planche = conn.execute(
        "SELECT id, chemin_web, chemin_tiff, largeur_px, hauteur_px "
        "FROM planches WHERE id = ?", (planche_id,)).fetchone()
    if planche is None:
        raise ValueError(f"Planche {planche_id} inexistante")

    master_w, master_h = planche["largeur_px"], planche["hauteur_px"]
    # On préfère le master (meilleure détection) ; sinon le dérivé web.
    if planche["chemin_tiff"] and (DATA_DIR / planche["chemin_tiff"]).is_file():
        image_path = DATA_DIR / planche["chemin_tiff"]
    else:
        image_path = DATA_DIR / planche["chemin_web"]

    ow, oh, boxes = _run(image_path, conf)
    scale_x = master_w / ow if ow else 1.0
    scale_y = master_h / oh if oh else 1.0

    # Cases existantes (pour le rattachement géométrique).
    cases = [dict(r) for r in conn.execute(
        "SELECT id, x, y, w, h FROM regions "
        "WHERE planche_id = ? AND type = 'case'", (planche_id,)).fetchall()]

    if replace:
        doomed = conn.execute(
            """WITH RECURSIVE doomed(id) AS (
                   SELECT id FROM regions
                   WHERE planche_id = ? AND type = 'bulle' AND source = 'auto'
                   UNION ALL
                   SELECT r.id FROM regions r JOIN doomed d ON r.parent_id = d.id
               ) SELECT id FROM doomed""", (planche_id,)).fetchall()
        for r in doomed:
            unindex_region(conn, r["id"])
        conn.execute(
            "DELETE FROM regions WHERE planche_id = ? AND type = 'bulle' "
            "AND source = 'auto'", (planche_id,))

    # Conversion master + tri en ordre de lecture (haut→bas, gauche→droite).
    converted = sorted(
        ((round(x * scale_x), round(y * scale_y), round(w * scale_x), round(h * scale_y))
         for x, y, w, h in boxes),
        key=lambda b: (b[1], b[0]))

    regions, sans_case = [], 0
    for ordre, (mx, my, mw, mh) in enumerate(converted, start=1):
        parent = _parent_case(cases, mx + mw / 2, my + mh / 2)
        if parent is None:
            sans_case += 1
        cur = conn.execute(
            """INSERT INTO regions
                  (planche_id, parent_id, type, x, y, w, h, ordre, source)
               VALUES (?, ?, 'bulle', ?, ?, ?, ?, ?, 'auto')""",
            (planche_id, parent, mx, my, mw, mh, ordre))
        regions.append({"id": cur.lastrowid, "type": "bulle", "parent_id": parent,
                        "x": mx, "y": my, "w": mw, "h": mh, "ordre": ordre})

    return {"planche_id": planche_id, "nb_bulles": len(regions),
            "sans_case": sans_case, "regions": regions}
