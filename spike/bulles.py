"""Détection de bulles (passe 2) — wrapper YOLOv8 comics, optionnel.

⚠️ NON TESTÉ ici (ultralytics non installé). Code prêt à l'emploi.

Modèle recommandé par la recherche : `ogkalu/comic-speech-bubble-detector-yolov8m`
(Apache-2.0, entraîné sur ~8k images incluant le style "Western Comic" ≈ BD
franco-belge). Sortie : boîtes de bulles, à utiliser comme crops pour l'OCR.

Usage typique sur une vraie planche (sans bbox connues) :
    from bulles import detect, write_sidecar
    boxes = detect("planche.png")          # télécharge les poids au 1er appel
    write_sidecar("planche.png", boxes)    # -> planche.json
    # puis : python run_bench.py --images <dir> --mode bulles

Installation :  pip install ultralytics huggingface_hub
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HF_REPO = "ogkalu/comic-speech-bubble-detector-yolov8m"
HF_FILE = "comic-speech-bubble-detector.pt"  # vérifier le nom exact sur la page HF


def available() -> bool:
    return importlib.util.find_spec("ultralytics") is not None


def download_weights(repo_id: str = HF_REPO, filename: str = HF_FILE) -> str:
    """Récupère les poids depuis le Hub (cache local huggingface)."""
    from huggingface_hub import hf_hub_download
    return hf_hub_download(repo_id=repo_id, filename=filename)


_model = None


def detect(image_path: str, weights: str | None = None, conf: float = 0.3) -> list[dict]:
    """Détecte les bulles ; renvoie [{x,y,w,h,conf}] en pixels image."""
    global _model
    from ultralytics import YOLO
    if _model is None:
        _model = YOLO(weights or download_weights())
    res = _model.predict(image_path, conf=conf, verbose=False)[0]
    boxes = []
    for b in res.boxes:
        x1, y1, x2, y2 = (float(v) for v in b.xyxy[0])
        boxes.append({"x": round(x1), "y": round(y1),
                      "w": round(x2 - x1), "h": round(y2 - y1),
                      "conf": round(float(b.conf[0]), 3)})
    # ordre de lecture grossier : haut->bas, gauche->droite
    boxes.sort(key=lambda d: (d["y"], d["x"]))
    return boxes


def write_sidecar(image_path: str, boxes: list[dict]) -> Path:
    """Écrit <image>.json (format lu par run_bench --mode bulles)."""
    p = Path(image_path)
    meta = {"image": p.name,
            "bulles": [{"x": b["x"], "y": b["y"], "w": b["w"], "h": b["h"],
                        "attendu": None} for b in boxes]}
    out = p.with_suffix(".json")
    out.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":  # pragma: no cover - utilitaire manuel
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+", help="planches à traiter")
    ap.add_argument("--weights", default=None)
    ap.add_argument("--conf", type=float, default=0.3)
    a = ap.parse_args()
    if not available():
        raise SystemExit("ultralytics absent : pip install ultralytics huggingface_hub")
    for img in a.images:
        boxes = detect(img, a.weights, a.conf)
        write_sidecar(img, boxes)
        print(f"{img}: {len(boxes)} bulles -> {Path(img).with_suffix('.json').name}")
