"""Banc d'essai OCR : compare les moteurs disponibles sur des planches BD.

    python spike/run_bench.py --images spike/samples --mode bulles --out spike/report.html

Modes :
  whole   -> OCR de la planche entière
  bulles  -> OCR par bulle (utilise les bbox du sidecar <image>.json si présent)
  both    -> les deux

Sortie : un rapport HTML auto-contenu (images en base64) + un CSV. Les moteurs
absents sont listés avec leur commande d'install. Pointe --images vers tes
vraies planches (ou celles téléchargées depuis ShareDocs) pour l'évaluation
réelle.
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import io
import json
from pathlib import Path

from PIL import Image

import ocr_engines

IMG_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def _data_uri(img: Image.Image, max_w: int = 360) -> str:
    if img.width > max_w:
        img = img.resize((max_w, round(img.height * max_w / img.width)))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _regions(image_path: Path, mode: str):
    """Renvoie [(label, PIL.Image, attendu|None)] selon le mode."""
    full = Image.open(image_path).convert("RGB")
    sidecar = image_path.with_suffix(".json")
    out = []
    if mode in ("whole", "both") or not sidecar.exists():
        out.append(("planche", full, None))
    if mode in ("bulles", "both") and sidecar.exists():
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        for i, b in enumerate(meta.get("bulles", []), 1):
            crop = full.crop((b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]))
            out.append((f"bulle {i}", crop, b.get("attendu")))
    return out


def run(images_dir: Path, mode: str, out_html: Path):
    engines = ocr_engines.available_engines()
    missing = [e for e in ocr_engines.ALL_ENGINES if e not in engines]
    imgs = sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMG_EXT)

    print(f"Moteurs disponibles : {[e.name for e in engines] or 'AUCUN'}")
    for e in missing:
        print(f"  (absent) {e.name:18} -> {e.install}")
    print(f"Images : {len(imgs)} dans {images_dir}")

    rows = []      # pour le CSV
    blocks = []    # pour le HTML
    for img_path in imgs:
        for label, region_img, attendu in _regions(img_path, mode):
            tmp = images_dir / f".__crop_{img_path.stem}_{label.replace(' ', '_')}.png"
            region_img.save(tmp)
            results = [ocr_engines.run(e, str(tmp)) for e in engines]
            tmp.unlink(missing_ok=True)
            for r in results:
                rows.append({"image": img_path.name, "region": label,
                             "engine": r["engine"], "seconds": r["seconds"],
                             "ok": r["ok"], "text": r["text"]})
            blocks.append(_html_block(img_path.name, label, region_img, attendu, results))

    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(_html_doc(blocks, engines, missing), encoding="utf-8")
    csv_path = out_html.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["image", "region", "engine", "seconds", "ok", "text"])
        w.writeheader(); w.writerows(rows)

    print(f"\nRapport : {out_html}")
    print(f"CSV     : {csv_path}")
    return rows


def _html_block(image, label, region_img, attendu, results):
    rows = "".join(
        f"<tr class='{'err' if not r['ok'] else ''}'>"
        f"<td class='eng'>{html.escape(r['engine'])}</td>"
        f"<td class='sec'>{r['seconds']}s</td>"
        f"<td class='txt'>{html.escape(r['text']) if r['ok'] else '⚠ ' + html.escape(r['error'])}</td>"
        f"</tr>"
        for r in results) or "<tr><td colspan=3 class='txt'>aucun moteur</td></tr>"
    exp = (f"<div class='exp'><b>attendu</b><pre>{html.escape(attendu)}</pre></div>"
           if attendu else "")
    return (f"<div class='block'><div class='hd'>{html.escape(image)} · "
            f"<span class='lbl'>{html.escape(label)}</span></div>"
            f"<div class='body'><img src='{_data_uri(region_img)}'>"
            f"<div class='res'>{exp}<table>{rows}</table></div></div></div>")


def _html_doc(blocks, engines, missing):
    miss = "".join(f"<li><code>{html.escape(e.name)}</code> — {html.escape(e.install)}</li>"
                   for e in missing)
    return f"""<!doctype html><html lang=fr><meta charset=utf-8>
<title>Banc OCR BD</title><style>
body{{font:14px system-ui;margin:24px;background:#1a1a2e;color:#e0e0e0}}
h1{{color:#a0c4ff}} code{{color:#f59e0b}}
.block{{border:1px solid #0f3460;border-radius:8px;margin:14px 0;overflow:hidden}}
.hd{{background:#16213e;padding:8px 12px;font-weight:600}}
.lbl{{color:#4ade80}}
.body{{display:flex;gap:16px;padding:12px}}
.body img{{border:1px solid #0f3460;border-radius:4px;max-height:260px;align-self:flex-start}}
.res{{flex:1;min-width:0}}
table{{width:100%;border-collapse:collapse}}
td{{border-top:1px solid #0f3460;padding:6px 8px;vertical-align:top}}
.eng{{color:#a0c4ff;white-space:nowrap;font-weight:600}} .sec{{color:#888;white-space:nowrap}}
.txt{{white-space:pre-wrap;font-family:Consolas,monospace}}
tr.err .txt{{color:#e94560}}
.exp{{background:#0f3460;border-radius:4px;padding:6px 8px;margin-bottom:8px}}
.exp pre{{margin:4px 0 0;white-space:pre-wrap;color:#4ade80}}
.miss{{color:#888}}</style>
<h1>Banc d'essai OCR — BD franco-belge</h1>
<p>Moteurs testés : {", ".join(f"<code>{html.escape(e.name)}</code>" for e in engines) or "<i>aucun installé</i>"}</p>
{"<p class=miss>Moteurs absents :</p><ul class=miss>" + miss + "</ul>" if miss else ""}
{"".join(blocks)}
</html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", default=str(Path(__file__).resolve().parent / "samples"))
    ap.add_argument("--mode", choices=["whole", "bulles", "both"], default="both")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "report.html"))
    a = ap.parse_args()
    run(Path(a.images), a.mode, Path(a.out))
