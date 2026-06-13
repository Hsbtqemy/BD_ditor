r"""Diagnostic PDF : couche texte (OCR) + rendu — pour décider de la stratégie d'import.

Pour CHAQUE page : présence d'une couche texte, nombre de mots, échantillon de
texte + coordonnées (converties en pixels MASTER au DPI choisi), dimensions de
rendu, couverture image, et un verdict scanné / born-digital / image-seule.

But : « au gré des scans », mesurer si la couche OCR existe et vaut la peine d'être
réutilisée (vs re-océriser avec EasyOCR).

Sources :
  - fichier local :
        python tools/pdf_check.py "C:\chemin\vers\doc.pdf"
  - ShareDocs (WebDAV ; identifiants via variables d'env BD_SHAREDOCS_URL/USER/PASS) :
        $env:BD_SHAREDOCS_URL="https://sharedocs.huma-num.fr/dav.php/"
        $env:BD_SHAREDOCS_USER="xxxxx@webdav"
        python tools/pdf_check.py --sharedocs "@Home/BD test/OCR....pdf"

Options :  --dpi 300 (défaut)   --pages 1-8 (sous-ensemble)   --max-words 6
"""
from __future__ import annotations

import io
import os
import sys
from getpass import getpass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Console Windows : éviter les UnicodeEncodeError (flèches, guillemets typographiques).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pdfplumber       # noqa: E402
import pypdfium2 as pdfium  # noqa: E402


def _arg(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else default
    return default


def _load_bytes() -> tuple[bytes, str]:
    via_sd = "--sharedocs" in sys.argv
    # chemin = dernier argument non-option
    positionals = [a for a in sys.argv[1:] if not a.startswith("--")
                   and a not in (_arg("--dpi"), _arg("--pages"), _arg("--max-words"))]
    if not positionals:
        print("✗ Donne un chemin de PDF (local ou ShareDocs avec --sharedocs).")
        raise SystemExit(2)
    path = positionals[-1]
    if via_sd:
        import pipeline.sharedocs as sd
        url = os.environ.get("BD_SHAREDOCS_URL", "").strip()
        user = os.environ.get("BD_SHAREDOCS_USER", "").strip()
        pwd = os.environ.get("BD_SHAREDOCS_PASS") or getpass("Mot de passe ShareDocs : ")
        if not url or not user:
            print("✗ Définis BD_SHAREDOCS_URL et BD_SHAREDOCS_USER.")
            raise SystemExit(2)
        sd.configure(url, user, pwd)
        print(f"→ Téléchargement ShareDocs : {path}")
        return sd.download(path), path
    with open(path, "rb") as f:
        return f.read(), path


def _page_range(n_pages: int):
    spec = _arg("--pages")
    if not spec:
        return range(n_pages)
    a, _, b = spec.partition("-")
    lo = max(1, int(a)) - 1
    hi = min(n_pages, int(b) if b else int(a))
    return range(lo, hi)


def main() -> int:
    data, path = _load_bytes()
    dpi = int(_arg("--dpi", "300"))
    max_words = int(_arg("--max-words", "6"))
    scale = dpi / 72.0
    size_mo = len(data) / 1e6
    print(f"\n=== {os.path.basename(path)} — {size_mo:.1f} Mo — rendu @ {dpi} dpi ===\n")

    pdoc = pdfium.PdfDocument(data)
    n = len(pdoc)
    print(f"{n} page(s).\n")

    avec_texte = sans_texte = 0
    for i in _page_range(n):
        with pdfplumber.open(io.BytesIO(data)) as pdf:   # rouvre : simple et robuste
            page = pdf.pages[i]
            pw, ph = page.width, page.height
            words = page.extract_words()
            imgs = page.images
        # rendu pixel via pypdfium2 (= dimensions du master si on rend à ce dpi)
        rpage = pdoc[i]
        rw, rh = (round(pw * scale), round(ph * scale))

        # couverture image (max aire image / aire page)
        cover = 0.0
        if imgs:
            page_area = pw * ph or 1
            cover = max((abs((im["x1"] - im["x0"]) * (im["bottom"] - im["top"]))
                         for im in imgs), default=0) / page_area

        if words:
            avec_texte += 1
            kind = "scanné+OCR" if cover > 0.6 else "born-digital/mixte"
        else:
            sans_texte += 1
            kind = "IMAGE SEULE (→ EasyOCR)"

        print(f"page {i+1:>3} | {kind:24s} | {len(words):4d} mots | "
              f"img~{cover*100:3.0f}% | rendu {rw}x{rh}px")

        # échantillon mots + coords master (px), pour vérifier le mapping
        for w in words[:max_words]:
            x0, y0 = round(w["x0"] * scale), round(w["top"] * scale)
            x1, y1 = round(w["x1"] * scale), round(w["bottom"] * scale)
            print(f"        “{w['text']}”  →  master px ({x0},{y0})-({x1},{y1})")

    print(f"\n--- bilan : {avec_texte} page(s) AVEC couche texte, "
          f"{sans_texte} sans (EasyOCR requis) ---")
    print("Note : qualité de la couche ≠ présence. Inspecte les échantillons :")
    print("       sur des bulles de BD, l'OCR embarqué peut être très approximatif.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
