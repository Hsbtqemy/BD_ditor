"""Génère une planche BD synthétique pour valider le banc OCR.

⚠️ C'est un PROXY de test (texte net, police standard), PAS une vraie planche
franco-belge. Le but est de prouver que le harnais tourne et produit du texte.
La vraie évaluation se fait sur les planches réelles (ShareDocs) — voir README.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Texte français majuscule, accents inclus (le lettrage BD est souvent tout-caps).
BULLES = [
    "BONJOUR ESTHER !\nON SE VOIT CE SOIR ?",
    "BIEN SÛR... À 20H,\nDEVANT LE CINÉMA.",
    "GÉNIAL ! N'OUBLIE PAS\nTON ÉCHARPE, IL GÈLE.",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_sample(dest: Path, width: int = 1200, height: int = 1600) -> dict:
    """Crée une planche 3 bulles et renvoie les bbox (px) des bulles."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), (235, 230, 220))
    draw = ImageDraw.Draw(img)
    font = _font(40)

    # 3 cases grossières (cadre noir) pour le réalisme visuel.
    margin, gap = 60, 30
    cw = width - 2 * margin
    ch = (height - 2 * margin - 2 * gap) // 3
    bulles_bbox = []
    for i, txt in enumerate(BULLES):
        cy = margin + i * (ch + gap)
        draw.rectangle([margin, cy, margin + cw, cy + ch], outline=(0, 0, 0), width=4)
        # bulle = ellipse blanche centrée dans la case
        bw, bh = int(cw * 0.7), int(ch * 0.55)
        bx = margin + (cw - bw) // 2
        by = cy + (ch - bh) // 2
        draw.ellipse([bx, by, bx + bw, by + bh], fill=(255, 255, 255), outline=(0, 0, 0), width=3)
        # texte centré
        lines = txt.split("\n")
        th = sum(draw.textbbox((0, 0), ln, font=font)[3] for ln in lines) + 8 * (len(lines) - 1)
        ty = by + (bh - th) // 2
        for ln in lines:
            w = draw.textbbox((0, 0), ln, font=font)[2]
            draw.text((bx + (bw - w) // 2, ty), ln, fill=(10, 10, 10), font=font)
            ty += draw.textbbox((0, 0), ln, font=font)[3] + 8
        bulles_bbox.append({"x": bx, "y": by, "w": bw, "h": bh, "attendu": txt})

    img.save(dest, "PNG")
    meta = {"image": dest.name, "width": width, "height": height, "bulles": bulles_bbox}
    (dest.with_suffix(".json")).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "samples" / "planche_synth.png"
    m = make_sample(out)
    print(f"Écrit {out} ({m['width']}x{m['height']}, {len(m['bulles'])} bulles)")
