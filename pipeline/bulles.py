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
from pipeline.ordering import reorder_planche

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


def est_charge() -> bool:
    """Le modèle YOLO est-il résident en mémoire ? (CONC-2 — visibilité/libération.)"""
    return _model is not None


def liberer() -> bool:
    """Décharge le modèle YOLO résident (libère la RAM) ; True si qqch a été libéré.
    Une inférence en cours garde sa propre référence locale (non cassée)."""
    global _model
    libere = _model is not None
    _model = None
    return libere


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
                  if (c["x"] or 0) <= cx <= (c["x"] or 0) + (c["w"] or 0)
                  and (c["y"] or 0) <= cy <= (c["y"] or 0) + (c["h"] or 0)]
    if not candidates:
        return None
    return min(candidates, key=lambda c: (c["w"] or 0) * (c["h"] or 0))["id"]


# Au-delà de ce recouvrement (IoU), une bulle nouvellement détectée est considérée
# comme un DOUBLON d'une bulle déjà présente (préservée) → ignorée (S4). Un simple test
# « centre du nouveau ∈ ancien » accumulait des doublons selon le décalage/la taille.
SEUIL_IOU_BULLE = 0.5


def _iou(a, b) -> float:
    """Intersection-over-union de deux boîtes {x, y, w, h}."""
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    ix = max(0, min(ax2, bx2) - max(a["x"], b["x"]))
    iy = max(0, min(ay2, by2) - max(a["y"], b["y"]))
    inter = ix * iy
    union = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / union if union > 0 else 0.0


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
    # Détection sur le dérivé WEB (RGB/JPEG, léger) : YOLOv8 redimensionne de
    # toute façon l'entrée à 640 px, donc le master n'apporte rien et exposerait
    # à des TIFF exotiques (CMYK/16 bits). Cohérent avec la segmentation Kumiko.
    image_path = DATA_DIR / planche["chemin_web"]

    try:
        ow, oh, boxes = _run(image_path, conf)
    except BullesError:
        raise
    except Exception as exc:  # lecture image / inférence -> message propre
        raise BullesError(f"Échec de la détection : {exc}") from exc
    scale_x = master_w / ow if ow else 1.0
    scale_y = master_h / oh if oh else 1.0

    # Cases existantes (pour le rattachement géométrique).
    cases = [dict(r) for r in conn.execute(
        "SELECT id, x, y, w, h FROM regions "
        "WHERE planche_id = ? AND type = 'case'", (planche_id,)).fetchall()]

    if replace:
        # Re-détecter NE DOIT PAS détruire le travail humain : on ne supprime
        # que les bulles 'auto' encore VIDES et NON annotées ; celles porteuses
        # de texte OCR ou d'une annotation sont préservées.
        doomed = conn.execute(
            """WITH RECURSIVE doomed(id) AS (
                   SELECT id FROM regions
                   WHERE planche_id = ? AND type = 'bulle' AND source = 'auto'
                     AND TRIM(COALESCE(ocr_texte, '')) = ''
                     AND NOT EXISTS (SELECT 1 FROM annotations a
                                     WHERE a.region_id = regions.id)
                   UNION ALL
                   SELECT r.id FROM regions r JOIN doomed d ON r.parent_id = d.id
               ) SELECT id FROM doomed""", (planche_id,)).fetchall()
        doomed_ids = [r["id"] for r in doomed]
        for rid in doomed_ids:
            unindex_region(conn, rid)
        if doomed_ids:
            ph = ",".join("?" * len(doomed_ids))
            conn.execute(f"DELETE FROM regions WHERE id IN ({ph})", tuple(doomed_ids))

    # Bulles encore présentes (préservées) : on ignorera une nouvelle détection
    # dont le centre tombe dans l'une d'elles (évite un doublon sur une bulle
    # océrisée conservée).
    existing = [dict(r) for r in conn.execute(
        "SELECT x, y, w, h FROM regions WHERE planche_id = ? AND type = 'bulle'",
        (planche_id,)).fetchall()]

    # Conversion master. L'`ordre` définitif (rang per-niveau, regroupé par case)
    # est recalculé par reorder_planche() ci-dessous ; ici un ordre provisoire.
    converted = [
        (round(x * scale_x), round(y * scale_y), round(w * scale_x), round(h * scale_y))
        for x, y, w, h in boxes]

    regions, sans_case, ignores = [], 0, 0
    for ordre, (mx, my, mw, mh) in enumerate(converted, start=1):
        cx, cy = mx + mw / 2, my + mh / 2
        box = {"x": mx, "y": my, "w": mw, "h": mh}
        if any(_iou(box, b) >= SEUIL_IOU_BULLE for b in existing):
            ignores += 1
            continue                       # doublon d'une bulle préservée (IoU — S4)
        parent = _parent_case(cases, cx, cy)
        if parent is None:
            sans_case += 1
        cur = conn.execute(
            """INSERT INTO regions
                  (planche_id, parent_id, type, x, y, w, h, ordre, source)
               VALUES (?, ?, 'bulle', ?, ?, ?, ?, ?, 'auto')""",
            (planche_id, parent, mx, my, mw, mh, ordre))
        regions.append({"id": cur.lastrowid, "type": "bulle", "parent_id": parent,
                        "x": mx, "y": my, "w": mw, "h": mh, "ordre": ordre})

    # Ordre de lecture : bulles regroupées par case (haut→bas, gauche→droite).
    reorder_planche(conn, planche_id)

    return {"planche_id": planche_id, "nb_bulles": len(regions),
            "sans_case": sans_case, "preservees": len(existing),
            "ignores": ignores, "regions": regions}
