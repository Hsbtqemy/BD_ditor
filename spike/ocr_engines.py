"""Adaptateurs OCR pour le banc d'essai (spike).

Chaque moteur expose la même interface :
    e.name            -> identifiant court
    e.available()     -> bool (paquet + éventuel binaire présents)
    e.install         -> commande d'installation (affichée si absent)
    e.transcribe(img) -> str (texte reconnu)

Les moteurs sont en lazy-init : le modèle n'est construit (et téléchargé) qu'au
premier appel, puis mis en cache. `run(engine, image_path)` enrobe l'appel avec
chronométrage et capture d'erreur — un moteur qui plante n'arrête pas le banc.

But du spike : comparer la qualité OCR sur de VRAIES planches franco-belges.
Aucun chiffre franco-belge n'existe dans la littérature (cf. recherche) — ce
banc sert à produire ces chiffres sur ton corpus.
"""
from __future__ import annotations

import importlib.util
import time


def _has(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


class Engine:
    name = "base"
    install = ""
    note = ""

    def available(self) -> bool:  # pragma: no cover - surchargé
        return False

    def transcribe(self, image_path: str) -> str:  # pragma: no cover - surchargé
        raise NotImplementedError


class Tesseract(Engine):
    name = "tesseract(fra)"
    install = "pip install pytesseract  +  binaire Tesseract (lang fra)"
    note = "open-source, sans quota ; baseline. Nécessite le binaire système."

    def available(self) -> bool:
        if not _has("pytesseract"):
            return False
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def transcribe(self, image_path: str) -> str:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(image_path), lang="fra")


class EasyOCR(Engine):
    name = "easyocr(fr)"
    install = "pip install easyocr"
    note = "PyTorch, CPU/GPU ; français natif ; télécharge les modèles."
    _reader = None

    def available(self) -> bool:
        return _has("easyocr")

    def transcribe(self, image_path: str) -> str:
        import easyocr
        if EasyOCR._reader is None:
            EasyOCR._reader = easyocr.Reader(["fr"], gpu=False, verbose=False)
        lines = EasyOCR._reader.readtext(image_path, detail=0, paragraph=True)
        return "\n".join(lines)


class DocTR(Engine):
    name = "doctr"
    install = "pip install python-doctr[torch]"
    note = "Apache-2.0, PyTorch, CPU/GPU ; latin (français)."
    _model = None

    def available(self) -> bool:
        return _has("doctr")

    def transcribe(self, image_path: str) -> str:
        from doctr.io import DocumentFile
        from doctr.models import ocr_predictor
        if DocTR._model is None:
            DocTR._model = ocr_predictor(pretrained=True)
        doc = DocumentFile.from_images(image_path)
        return DocTR._model(doc).render()


class PaddleOCR(Engine):
    name = "paddleocr(french)"
    install = "pip install paddlepaddle paddleocr"
    note = "Apache-2.0, CPU/GPU ; modèle 'french'."
    _ocr = None

    def available(self) -> bool:
        return _has("paddleocr")

    def transcribe(self, image_path: str) -> str:
        from paddleocr import PaddleOCR as _P
        if PaddleOCR._ocr is None:
            PaddleOCR._ocr = _P(lang="french", use_angle_cls=True, show_log=False)
        res = PaddleOCR._ocr.ocr(image_path, cls=True)
        page = res[0] if res else []
        return "\n".join(line[1][0] for line in (page or []))


class RapidOCR(Engine):
    name = "rapidocr"
    install = "pip install rapidocr-onnxruntime"
    note = "ONNX (sans torch), léger, CPU ; latin."
    _engine = None

    def available(self) -> bool:
        return _has("rapidocr_onnxruntime")

    def transcribe(self, image_path: str) -> str:
        from rapidocr_onnxruntime import RapidOCR as _R
        if RapidOCR._engine is None:
            RapidOCR._engine = _R()
        result, _ = RapidOCR._engine(image_path)
        return "\n".join(r[1] for r in result) if result else ""


ALL_ENGINES = [Tesseract(), EasyOCR(), DocTR(), PaddleOCR(), RapidOCR()]


def available_engines() -> list[Engine]:
    return [e for e in ALL_ENGINES if e.available()]


def run(engine: Engine, image_path: str) -> dict:
    """Exécute un moteur sur une image ; renvoie texte + durée + statut."""
    t0 = time.perf_counter()
    try:
        text = engine.transcribe(image_path)
        return {"engine": engine.name, "ok": True, "error": None,
                "seconds": round(time.perf_counter() - t0, 2),
                "text": text.strip()}
    except Exception as exc:  # un moteur qui plante ne stoppe pas le banc
        return {"engine": engine.name, "ok": False, "error": f"{type(exc).__name__}: {exc}",
                "seconds": round(time.perf_counter() - t0, 2), "text": ""}
