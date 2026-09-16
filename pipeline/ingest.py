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
                    PILLOW_FORMATS,
                    WEB_JPEG_QUALITY, WEB_SCALE)

# Garde anti-bombe de décompression : on relève la limite Pillow à une valeur
# large (couvre les scans 400-600 dpi) mais bornée — surtout pas None, qui
# désactiverait la protection et exposerait à un OOM sur image-bombe.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def _rel_posix(path: Path) -> str:
    """Chemin relatif à DATA_DIR, en séparateurs POSIX (sûr pour les URL).

    Un chemin HORS de `DATA_DIR` n'a pas de forme relative : `relative_to` lève alors
    un `ValueError` nu, dont le message ne nomme ni le rôle des deux chemins ni la
    règle enfreinte. Le cas est latent — aucune route ne laisse choisir la source —
    mais il cesserait de l'être le jour où l'on importerait depuis un dossier fourni,
    et c'est précisément le jour où le message compte (G5).
    """
    resolu = path.resolve()
    try:
        return resolu.relative_to(DATA_DIR).as_posix()
    except ValueError as exc:
        raise ValueError(
            f"Chemin hors de DATA_DIR : {resolu} n'est pas sous {DATA_DIR}. "
            "Les chemins stockés en base sont RELATIFS à la racine de données, pour "
            "qu'une instance reste déplaçable ; un chemin extérieur n'en a aucune."
        ) from exc


def _next_numero(conn: sqlite3.Connection, album_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(numero), 0) + 1 AS n FROM planches WHERE album_id = ?",
        (album_id,),
    ).fetchone()
    return int(row["n"])


def read_metadata(source: Path) -> dict:
    """Lit dimensions, mode couleur et DPI d'une image sans la convertir.

    `formats=` borne ce que Pillow a le droit de DÉCODER (SEC-3). Le filtre d'extension
    de l'API ne suffit pas : `Image.open` ne regarde pas le nom du fichier, il renifle
    l'en-tête — un PSD renommé `.tif` passe le premier et arrive au décodeur PSD, qui est
    le vecteur de `CVE-2026-25990`. Le paramètre est le contournement que l'avis propose
    lui-même, et il vaut quelle que soit la version de Pillow, donc il ne dépend pas du
    plafond que nous impose `iiif-prezi3`.
    """
    with Image.open(source, formats=PILLOW_FORMATS) as img:
        dpi = img.info.get("dpi")
        # dpi peut être scalaire (300) ou non numérique selon l'encodeur :
        # normalise en paire d'entiers, ou None si illisible (image valide quand même).
        if dpi is not None and not isinstance(dpi, (tuple, list)):
            dpi = (dpi, dpi)
        try:
            dpi = tuple(round(d) for d in dpi) if dpi else None
        except (TypeError, ValueError):
            dpi = None
        # Une résolution EXPLOITABLE est une paire de valeurs > 0. Toute autre forme
        # (longueur ≠ 2, zéro/négatif d'un scanner aux métadonnées cassées) est traitée
        # comme absente : dépaquetage sûr en aval + indicateur « avec résolution » exact.
        if dpi and (len(dpi) != 2 or not all(d > 0 for d in dpi)):
            dpi = None
        return {
            "largeur": img.width,
            "hauteur": img.height,
            "mode": img.mode,
            "dpi": dpi,
        }


# Gris de plus de 8 bits que Pillow range en `I;16*` et que la conversion sait réduire (IMG-1).
MODES_GRIS_16_BITS = ("I;16", "I;16B", "I;16L")


class ModeImageRefuse(ValueError):
    """Mode d'image qu'aucune réduction en 8 bits ne rendrait juste (IMG-1)."""


def _bits_portes(img: Image.Image) -> int:
    """Nombre de bits réellement portés par un gris rangé en `I;16`.

    Pillow range un TIFF 12 bits en `I;16` SANS étendre ses valeurs : 4095 y reste 4095
    (mesuré le 2026-09-16 sur un TIFF forgé). Son décodeur JPEG 2000, lui, étend toute
    précision à 16 bits (`shift = 16 - prec`, lu dans `Jpeg2KDecode.c` au tag 12.0.0, non
    mesuré faute d'encodeur 12 bits), et le PNG n'a pas d'autre profondeur que 16. Seul le
    TIFF peut donc porter moins que son mode, et il le dit dans `BitsPerSample` (balise 258).
    """
    balises = getattr(img, "tag_v2", None)
    bits = balises.get(258) if balises is not None else None
    if isinstance(bits, (tuple, list)):
        bits = bits[0] if bits else None
    return bits if isinstance(bits, int) and 8 < bits <= 16 else 16


def image_8_bits(img: Image.Image) -> Image.Image:
    """Ramène une image décodée en `L` ou `RGB`, les deux modes que JPEG et l'OCR reçoivent.

    **Le seul chemin d'un master vers 8 bits** (IMG-1) : le dérivé web et l'OCR l'appellent
    tous deux. Ils faisaient chacun `convert("RGB")`, qui ÉCRÊTE un gris 16 bits au lieu de
    le réduire — 0, 100 et 255 passent, tout ce qui dépasse sort à 255. Un scan réel devenait
    une page presque blanche, sans erreur à l'import, et l'OCR lisait la même page blanche
    même quand le dérivé était juste. Corriger l'un sans l'autre laissait le défaut entier.

    Ce que la conversion fait, et rien de plus :
    - gris 12 ou 16 bits (`I;16`, `I;16B`, `I;16L`) : réduit à 8 bits en gardant ses tons
      (65535 → 255, 32768 → 128) ;
    - `I` et `F` : REFUSÉS, en nommant le mode. `I` ne dit pas sa profondeur — Pillow y range
      le 16 bits signé comme le 32 bits, et relit 4294967295 en -1 (mesuré) ; un flottant n'a
      pas d'échelle, 1,0 est le blanc d'une convention et le noir d'une autre. Toute
      réduction serait devinée, et une page fausse qui s'affiche coûte plus qu'un refus ;
    - tout autre mode : `convert("RGB")`. Pour la palette et le 1 bit, c'est juste. Pour le
      CMYK c'est NAÏF, sans profil ICC ; et l'alpha est abandonné. Le RVB 16 bits par canal
      n'arrive jamais ici : Pillow le réduit lui-même à la lecture et l'ouvre en `RGB`.
    """
    if img.mode in ("RGB", "L"):
        return img
    if img.mode in MODES_GRIS_16_BITS:
        diviseur = 2 ** (_bits_portes(img) - 8)
        # `convert("I")` préserve les valeurs, y compris en gros-boutiste (mesuré) ; la
        # division tronque, donc elle vaut `>> 8` sur 16 bits et ne sort jamais de 0-255.
        return img.convert("I").point(lambda v: v / diviseur).convert("L")
    if img.mode == "F" or img.mode.startswith("I"):
        nature = {"I": "entiers dont la profondeur n'est pas connue",
                  "F": "nombres flottants sans échelle"}.get(img.mode, "profondeur inconnue")
        raise ModeImageRefuse(
            f"mode d'image « {img.mode} » ({nature}) : aucune réduction en 8 bits ne serait "
            "juste. Exportez le scan en 8 ou 16 bits entiers non signés, puis réimportez.")
    return img.convert("RGB")


def make_web_derivative(source: Path, dest: Path,
                        scale: float = WEB_SCALE,
                        quality: int = WEB_JPEG_QUALITY) -> tuple[int, int]:
    """Génère le dérivé web JPEG et retourne ses dimensions (largeur, hauteur).

    Lève `ModeImageRefuse` AVANT d'écrire quoi que ce soit si le master n'a pas de
    réduction juste en 8 bits : l'import le rend en 400 et retire le master.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source, formats=PILLOW_FORMATS) as img:   # SEC-3, cf. read_metadata
        img = image_8_bits(img)
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

    # Matériel de numérisation (A6) : on PERSISTE désormais résolution + mode (lus par
    # read_metadata, jetés jusqu'ici). `dpi` est une paire (x, y) ou None → on éclate.
    dpi_x, dpi_y = meta["dpi"] if meta["dpi"] else (None, None)
    cur = conn.execute(
        """
        INSERT INTO planches
            (album_id, numero, chemin_tiff, chemin_web,
             largeur_px, hauteur_px, dpi_x, dpi_y, mode, statut)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'importee')
        """,
        (album_id, numero, chemin_tiff, chemin_web,
         meta["largeur"], meta["hauteur"], dpi_x, dpi_y, meta["mode"]),
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
