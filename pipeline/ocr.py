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
import time

from config import DATA_DIR, MAX_IMAGE_PIXELS, PILLOW_FORMATS, TTL_MASTER_CROP
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


def est_charge() -> bool:
    """Le lecteur EasyOCR est-il résident en mémoire ? (CONC-2.)"""
    return _reader is not None


def liberer() -> bool:
    """Décharge le lecteur EasyOCR résident (libère la RAM) ; True si qqch a été libéré."""
    global _reader, _reader_langs
    libere = _reader is not None
    _reader = None
    _reader_langs = None
    return libere


def _open_image(planche):
    """Ouvre le master si possible (sinon le dérivé web) ; renvoie (img, scale)
    où scale convertit des pixels MASTER vers les pixels de l'image ouverte."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS   # garde anti-bombe (jamais None)
    if planche["chemin_tiff"] and (DATA_DIR / planche["chemin_tiff"]).is_file():
        # SEC-3 — même borne qu'à l'ingest, et elle sert ici PLUS qu'ailleurs : ce
        # fichier a été écrit sur disque à l'import, donc un master forgé qui aurait
        # franchi l'ingest serait redécodé à chaque passe OCR. Borner aux deux endroits
        # coûte un paramètre ; n'en borner qu'un laisse le second faire le travail.
        img = Image.open(DATA_DIR / planche["chemin_tiff"], formats=PILLOW_FORMATS)
        scale = 1.0
    else:
        img = Image.open(DATA_DIR / planche["chemin_web"], formats=PILLOW_FORMATS)
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
_crop_cache: dict = {"planche_id": None, "img": None, "scale": 1.0,
                     "dernier_acces": 0.0}
_crop_lock = threading.Lock()  # le cache est partagé entre threads du pool

# CONC-1 — le master n'était fermé qu'à l'ouverture d'une AUTRE planche : une session de
# transcription terminée laissait 53 Mo résidents pour toujours (mesuré le 2026-09-08 sur
# un master réel de 17,7 Mpx).
#
# LE PORTEUR EST UNE MINUTERIE D'INACTIVITÉ, ET NON UN FIL DE FOND. La fiche supposait
# qu'il en faudrait un, parce qu'un contrôle paresseux ne ferme rien quand plus personne
# n'appelle — ce qui est exactement le cas visé, et reste vrai. Mais un `threading.Timer`
# réarmé n'existe QUE tant que le cache tient quelque chose : armé au premier crop, il
# meurt avec l'image qu'il ferme, et le module n'a aucun objet vivant quand le cache est
# vide. C'est le fil de fond sans sa permanence.
_minuterie: threading.Timer | None = None


def _fermer_master() -> bool:
    """Ferme le master caché et vide l'entrée. **À appeler SOUS `_crop_lock`.**"""
    img = _crop_cache["img"]
    if img is None:
        return False
    try:
        img.close()
    except Exception:                       # pragma: no cover - fermeture best-effort
        pass
    _crop_cache.update(planche_id=None, img=None, scale=1.0)
    return True


def _echoir_master() -> None:
    """Corps de la minuterie : ferme le master si personne ne l'a redemandé depuis.

    **Le contrôle d'âge n'est pas une ceinture, c'est la correction d'une course.**
    `Timer.cancel()` ne rattrape pas une minuterie DÉJÀ partie : celle-ci peut être en
    attente de `_crop_lock` pendant qu'un crop tout neuf s'en sert, le réarmement
    n'annulant plus rien. Sans ce contrôle elle fermerait, en sortant du verrou, une image
    qui vient d'être utilisée — la refermeture serait correcte du point de vue du cache,
    mais l'échéance ne voudrait plus rien dire.

    **Et trop tôt, elle SE RÉARME au lieu de renoncer.** Écrit d'abord avec un simple
    `return`, ce corps laissait le master résident pour de bon dès que la minuterie se
    réveillait un cheveu avant l'heure — `Event.wait()` le fait, la granularité d'horloge
    y suffit. Le fil mourait, personne ne le remplaçait, et la seule chose qui pouvait
    encore fermer l'image était le changement de planche : exactement l'état qu'on
    voulait quitter. Le test de l'échéance l'a attrapé au premier lancement.
    """
    with _crop_lock:
        if _crop_cache["img"] is None:
            return                          # rien à fermer : on ne réarme pas dans le vide
        reste = TTL_MASTER_CROP - (time.monotonic() - _crop_cache["dernier_acces"])
        if reste > 0:
            _armer_echeance(reste)          # réveil anticipé, ou accès plus récent
            return
        _fermer_master()


def _armer_echeance(delai: float | None = None) -> None:
    """(Ré)arme la minuterie. **À appeler SOUS `_crop_lock`.**

    `delai` sert au réarmement depuis `_echoir_master`, pour ne compter que le temps qui
    RESTE ; par défaut l'échéance repart entière, depuis l'accès qui vient d'avoir lieu.

    À `TTL_MASTER_CROP <= 0` aucun fil n'est créé : le cache retrouve exactement son
    comportement d'avant, fermé au seul changement de planche.
    """
    global _minuterie
    if _minuterie is not None:
        _minuterie.cancel()
        _minuterie = None
    if TTL_MASTER_CROP <= 0:
        return
    _minuterie = threading.Timer(TTL_MASTER_CROP if delai is None else delai,
                                 _echoir_master)
    _minuterie.daemon = True                # ne retient jamais l'arrêt du process
    _minuterie.start()


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
        # Le décodage est FORCÉ sous le verrou, et c'est ce qui rend la sortie sûre :
        # Pillow est paresseux, et un `crop` non matérialisé relirait l'image PARTAGÉE
        # plus tard — c'est-à-dire potentiellement après qu'un autre thread a changé de
        # planche et fermé cette image-là. Les versions récentes matérialisent déjà, mais
        # s'en remettre à un détail d'implémentation ferait reposer une propriété de
        # sûreté sur un accident : ici elle est écrite.
        crop.load()

        # Le master vient de servir : l'échéance repart de maintenant (CONC-1).
        _crop_cache["dernier_acces"] = time.monotonic()
        _armer_echeance()

    # --- Hors verrou (CONC-1). `crop` est un objet NEUF, local à ce thread, que plus
    # rien ne partage : le redimensionner et l'encoder ne touche plus au cache ni au
    # master. Mesuré le 2026-09-08 sur trois régions d'un vrai master TIFF — resize
    # 19-31 % du temps de l'appel, encodage PNG 59-75 %, soit 85 à 94 % qui sortent de
    # la sérialisation. Et davantage en régime réel : le master étant caché, l'ouverture
    # ne se paie qu'au changement de planche, si bien qu'une navigation bulle-à-bulle ne
    # garde plus sous le verrou que le crop lui-même, ~2 %.
    #
    # L'attendu d'origine de CONC-1 — « le verrou ne couvre plus que la manipulation du
    # dictionnaire de cache » — était FAUX : le `crop` lit l'image partagée, et
    # `_open_image` la remplace. Les sortir aurait produit un accès après fermeture.
    #
    # Ce que la coupe COÛTE, parce qu'un gain qu'on annonce sans son prix se paie plus
    # tard : le verrou large bornait AUSSI la mémoire — un seul crop décodé à la fois,
    # quelle que soit la charge. Chaque thread tient désormais le sien pendant le resize
    # et l'encodage. En régime réel c'est négligeable (un crop de bulle pèse quelques
    # centaines de Ko, et un navigateur n'ouvre qu'une poignée de connexions) ; le cas
    # extrême ne l'est pas — une région couvrant une planche entière sur un master au
    # plafond de `MAX_IMAGE_PIXELS` se compte en centaines de Mo, par thread. Ce n'est
    # PAS mesuré, donc ce n'est pas borné ici : re-sérialiser coûterait tout le gain, et
    # poser un sémaphore sur une hypothèse serait exactement ce que ce chantier refuse.
    if crop.width > max_dim:
        crop = crop.resize(
            (max_dim, max(1, round(crop.height * max_dim / crop.width))),
            Image.LANCZOS)
    buf = io.BytesIO()
    crop.convert("RGB").save(buf, "PNG")
    return buf.getvalue()
