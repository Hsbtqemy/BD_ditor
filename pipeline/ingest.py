"""Ingestion d'une planche : scan reçu → copie de travail + dérivé web + métadonnées en base.

Étapes :
  1. Ouvrir le scan reçu avec Pillow, lire métadonnées (DPI, dimensions, mode), le décoder
     UNE fois — hors de toute transaction d'écriture (un JPEG 2000 sans perte y met ~5 s).
  2. Écrire la COPIE DE TRAVAIL (IMG-1) : JPEG qualité 80 à 300 dpi effectifs — réduite si
     le scan est plus fin, gardée à sa taille sinon ou sans résolution écrite.
  3. Générer le dérivé web : 25 % (WEB_SCALE) des dimensions du scan, JPEG qualité 82.
  4. Stocker chemins (relatifs, en POSIX), dimensions et matériel du SCAN en base, et ce
     que l'outil sait du master d'archive (`master_origine`).
  5. Retourner la ligne `planches` créée.

Le fichier reçu n'est PAS gardé sur le serveur (IMG-1, décidé par Hugo le 2026-10-21) : le
master d'archive vit où le projet le met. `chemin_tiff` désigne désormais la copie de
travail ; la colonne garde son nom d'avant, et les planches importées avant la v34 y
désignent encore leur master, jusqu'au rattrapage (`tools/convertir_en_copies_de_travail.py`).

Les coordonnées des régions sont toujours stockées en pixels du SCAN (« pixels master ») ;
c'est pourquoi `planches.largeur_px / hauteur_px` contiennent les dimensions du scan, ni
celles de la copie de travail ni celles du dérivé. Quiconque ouvre l'une des deux et la
croise avec des coordonnées applique l'échelle `largeur de l'image ouverte / largeur_px`
(le navigateur pour le dérivé, `ocr._open_image` pour la copie de travail).
"""
from __future__ import annotations

import io
import os
import re
import sqlite3
from pathlib import Path

from PIL import Image

from config import (CORPUS_DIR, DATA_DIR, DERIVATIVES_DIR, MAX_IMAGE_PIXELS,
                    PILLOW_FORMATS, TRAVAIL_DPI, TRAVAIL_JPEG_QUALITY,
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


def numero_occupe(conn: sqlite3.Connection, album_id: int, numero: int) -> bool:
    """Les fichiers d'une planche de ce numéro, dans cet album, sont-ils DÉJÀ pris ?
    COL-3, tranche 3 (D6, relecture croisée).

    Copie de travail et dérivé sont nommés d'après le numéro (`ingest_image`), et
    l'import écrit sur ces chemins sans regarder s'ils existent. Tant qu'un album avait ses
    propres fichiers, le numéro libre DANS L'ALBUM suffisait. Plus depuis qu'une copie sœur
    désigne les fichiers de la copie dont elle a été tirée : la planche de A supprimée, ses
    fichiers restent pour B, et le numéro est de nouveau libre dans A — un import y aurait
    réécrit l'image de B, puis, sur un échec, l'aurait effacée.

    La règle : on n'écrit JAMAIS sur un chemin qui existe déjà sur le disque, ni sur un
    chemin qu'une planche — de n'importe quel album — désigne. Un numéro est pris si l'un
    des deux est vrai, pour le master (quelle que soit son extension) ou pour le dérivé.
    D'où une garantie de plus : un fichier qu'un import efface sur un échec est forcément
    le sien."""
    souche = f"planche_{numero:04d}"
    corpus = CORPUS_DIR / f"album_{album_id}"
    derive = DERIVATIVES_DIR / f"album_{album_id}" / f"{souche}.jpg"
    if derive.exists() or (corpus.is_dir() and any(corpus.glob(f"{souche}.*"))):
        return True
    try:
        master_rel = _rel_posix(corpus) + f"/{souche}."
        derive_rel = _rel_posix(derive)
    except ValueError:                  # images hors de la racine de données : le disque seul
        return False
    return conn.execute(
        "SELECT 1 FROM planches WHERE chemin_web = ? OR substr(chemin_tiff, 1, ?) = ? "
        "OR substr(chemin_web, 1, ?) = ? LIMIT 1",
        (derive_rel, len(master_rel), master_rel, len(master_rel), master_rel)).fetchone() \
        is not None


def prochain_numero_libre(conn: sqlite3.Connection, album_id: int) -> int:
    """Le numéro d'une nouvelle planche : le premier après le plus grand de l'album dont
    les fichiers ne sont pas déjà pris (`numero_occupe`). Un numéro dont les images servent
    encore à une copie sœur est SAUTÉ — la numérotation garde un trou, l'image reste."""
    numero = _next_numero(conn, album_id)
    while numero_occupe(conn, album_id, numero):
        numero += 1
    return numero


# Sous ce seuil, une résolution lue dans le fichier n'est pas celle d'un scan (IMG-1,
# 2026-10-21). Mesuré sur Pillow 12.0.0 : un TIFF qui ne porte AUCUNE balise de résolution
# sort avec `dpi = (1, 1)` — la valeur par défaut de Pillow, pas celle du fichier —, et la
# planche recevait ~9 000 cm en comptant « avec résolution ». Aucun scanner ne capte sous
# 50 dpi : les plus bas réglages vont de 75 à 100, et une page A4 à 50 dpi ne fait que
# 413 × 585 pixels, illisible pour annoter. Le seuil laisse passer 72 et 96, valeurs
# d'écran qu'écrivent certains logiciels : fausses peut-être, mais pas manifestement, et
# les trancher n'est pas l'objet de cette garde.
DPI_MINIMUM = 50


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
        return _metadonnees(img)


def _metadonnees(img: Image.Image) -> dict:
    """Ce que `read_metadata` lit, sur une image déjà ouverte (l'ingest n'ouvre qu'une fois)."""
    dpi = img.info.get("dpi")
    # dpi peut être scalaire (300) ou non numérique selon l'encodeur :
    # normalise en paire d'entiers, ou None si illisible (image valide quand même).
    if dpi is not None and not isinstance(dpi, (tuple, list)):
        dpi = (dpi, dpi)
    try:
        dpi = tuple(round(d) for d in dpi) if dpi else None
    except (TypeError, ValueError):
        dpi = None
    # Une résolution EXPLOITABLE est une paire de valeurs d'au moins `DPI_MINIMUM`.
    # Toute autre forme (longueur ≠ 2, zéro/négatif d'un scanner aux métadonnées
    # cassées, le (1, 1) que Pillow pose sur un TIFF sans balise) est traitée comme
    # absente : dépaquetage sûr en aval + indicateur « avec résolution » exact.
    if dpi and (len(dpi) != 2 or not all(d >= DPI_MINIMUM for d in dpi)):
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

    **Le seul chemin, dans Pillow, d'un master vers 8 bits** (IMG-1) : le dérivé web et l'OCR
    l'appellent tous deux. Ces deux sites faisaient chacun `convert("RGB")`, qui ÉCRÊTE un
    gris 16 bits au lieu de le réduire — 0, 100 et 255 passent, tout ce qui dépasse sort à
    255. Un scan réel devenait une page presque blanche, sans erreur à l'import, et l'OCR
    lisait la même page blanche même quand le dérivé était juste. Corriger l'un sans l'autre
    laissait le défaut entier. Kumiko sur master (`use_master=True`) ne passe pas par ici : il
    lit le fichier avec OpenCV, qui réduit un TIFF 16 bits et refuse un 12 bits (mesuré).

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
                        quality: int = WEB_JPEG_QUALITY,
                        taille_scan: tuple[int, int] | None = None) -> tuple[int, int]:
    """Génère le dérivé web JPEG et retourne ses dimensions (largeur, hauteur).

    `taille_scan` : les dimensions du SCAN (`largeur_px`, `hauteur_px`), à passer quand la
    source n'est plus le scan mais sa copie de travail (IMG-1, `tools/regenerer_derives.py`) :
    le dérivé fait 25 % du scan, pas 25 % d'une copie déjà réduite. Omis, la source est le
    scan lui-même.

    Lève `ModeImageRefuse` AVANT d'écrire le dérivé si l'image n'a pas de réduction juste
    en 8 bits.
    """
    with Image.open(source, formats=PILLOW_FORMATS) as img:   # SEC-3, cf. read_metadata
        img = image_8_bits(img)
        return _ecrire_derive(img, dest, taille_scan or img.size, scale, quality)


def _ecrire_derive(img8: Image.Image, dest: Path, taille_scan: tuple[int, int],
                   scale: float = WEB_SCALE,
                   quality: int = WEB_JPEG_QUALITY) -> tuple[int, int]:
    """Le dérivé web d'une image déjà ramenée en 8 bits : `scale` des dimensions du scan."""
    w = max(1, round(taille_scan[0] * scale))
    h = max(1, round(taille_scan[1] * scale))
    web = img8.resize((w, h), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    web.save(dest, "JPEG", quality=quality, optimize=True)
    return w, h


# --------------------------------------------------------------------------- #
# La copie de travail (IMG-1, décidé par Hugo le 2026-10-21)
# --------------------------------------------------------------------------- #
def facteur_de_travail(dpi) -> float:
    """Le facteur qui ramène un scan à `TRAVAIL_DPI` (300) dpi effectifs.

    Sous 1 pour un scan plus fin (0,75 pour un 400 dpi) ; 1 pour un scan à 300 dpi ou moins
    — on n'agrandit jamais ; et 1 SANS résolution écrite (les JPEG 2000 de l'équipe) : on ne
    réduit pas ce qu'on ne sait pas mesurer, et rien n'est inventé.

    UN facteur pour les deux axes, tiré de la PLUS BASSE des deux résolutions : aucun axe ne
    descend sous 300 dpi, l'image garde ses proportions, et quiconque croise la copie avec
    des coordonnées n'a qu'une échelle à appliquer (`largeur ouverte / largeur_px`). Un scan
    aux deux résolutions différentes est rare ; c'est le seul cas où un axe reste au-dessus
    de 300."""
    if not dpi:
        return 1.0
    return min(1.0, TRAVAIL_DPI / min(dpi))


def taille_de_travail(largeur: int, hauteur: int, dpi) -> tuple[int, int]:
    """Les dimensions de la copie de travail d'un scan de `largeur` × `hauteur` pixels."""
    f = facteur_de_travail(dpi)
    if f >= 1:
        return largeur, hauteur
    return max(1, round(largeur * f)), max(1, round(hauteur * f))


def ecrire_copie_de_travail(img8: Image.Image, dest: Path, largeur: int, hauteur: int,
                            dpi, *, icc: bytes | None = None) -> tuple[int, int]:
    """Écrit la copie de travail d'un scan déjà décodé en 8 bits (`image_8_bits`) et rend ses
    dimensions. JPEG qualité `TRAVAIL_JPEG_QUALITY` (80), à `taille_de_travail`.

    `largeur`, `hauteur`, `dpi` sont ceux du SCAN — ce qui est écrit en base. La copie
    porte la résolution qu'elle a EFFECTIVEMENT (300 pour un 400 réduit) : un fichier qui
    dirait 400 à 75 % de sa taille mentirait à qui l'ouvre ailleurs ; aucune quand le scan
    n'en écrivait pas. Le profil ICC suit s'il décrit encore l'image (`icc`, que l'appelant
    ne passe que si le mode n'a pas changé).

    Écrite à côté puis substituée d'un coup : un échec ne laisse ni fichier tronqué à `dest`
    ni fichier provisoire."""
    w, h = taille_de_travail(largeur, hauteur, dpi)
    copie = img8 if (w, h) == img8.size else img8.resize((w, h), Image.LANCZOS)
    options: dict = {"quality": TRAVAIL_JPEG_QUALITY}
    if dpi:
        options["dpi"] = (round(dpi[0] * w / largeur), round(dpi[1] * h / hauteur))
    if icc:
        options["icc_profile"] = icc
    dest.parent.mkdir(parents=True, exist_ok=True)
    provisoire = dest.with_name(dest.name + ".provisoire")
    try:
        copie.save(provisoire, "JPEG", **options)
        os.replace(provisoire, dest)
    except BaseException:
        provisoire.unlink(missing_ok=True)
        raise
    return w, h


# Le préfixe de `planches.master_origine` quand le scan vient de ShareDocs : la suite est le
# chemin DISTANT, là où vit le master d'archive. Sans préfixe, c'est le NOM du fichier reçu
# par l'import de fichiers — le seul fait que l'outil sache alors de son master.
ORIGINE_SHAREDOCS = "sharedocs:"


def ingest_image(conn: sqlite3.Connection, album_id: int, source,
                 numero: int | None = None,
                 keep_master: bool = True,
                 origine: str | None = None) -> dict:
    """Ingère un scan reçu et crée la planche associée ; rend la ligne `planches` créée.

    `source` : le scan reçu — ses OCTETS (les routes d'import : il n'est jamais écrit tel
    quel sur le disque), ou un chemin. Ce fichier n'est NI gardé NI effacé par l'ingest :
    seule sa copie de travail est gardée (IMG-1), et un chemin passé appartient à
    l'appelant.

    `keep_master` : faux, aucune copie de travail n'est écrite (`chemin_tiff` NULL, le
    dérivé seul). `origine` : ce que l'outil sait du master d'archive, gardé dans
    `planches.master_origine` — le chemin distant d'un import ShareDocs, sinon le nom du
    fichier reçu ; à défaut, le nom d'un chemin passé.

    Le scan est décodé UNE fois, avant toute écriture en base : aucune transaction n'est
    ouverte par l'ingest pendant le décodage (un JPEG 2000 sans perte y met ~5 s, mesuré le
    2026-10-21) — la sienne ne commence qu'à l'`INSERT`. Tout échec retire les fichiers que
    l'ingest a écrits, et seulement eux : leurs chemins étaient libres (`numero_occupe`)."""
    if isinstance(source, (bytes, bytearray)):
        flux = io.BytesIO(source)
    else:
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(f"Scan introuvable : {source}")
        flux = source
        if origine is None:
            origine = source.name

    album = conn.execute("SELECT id FROM albums WHERE id = ?", (album_id,)).fetchone()
    if album is None:
        raise ValueError(f"Album {album_id} inexistant")

    if numero is None:
        numero = prochain_numero_libre(conn, album_id)

    souche = f"planche_{numero:04d}"
    web_path = DERIVATIVES_DIR / f"album_{album_id}" / f"{souche}.jpg"
    travail = CORPUS_DIR / f"album_{album_id}" / f"{souche}.jpg" if keep_master else None
    ecrits: list[Path] = []
    try:
        with Image.open(flux, formats=PILLOW_FORMATS) as img:   # SEC-3, cf. read_metadata
            meta = _metadonnees(img)
            icc = img.info.get("icc_profile")
            img8 = image_8_bits(img)        # ModeImageRefuse AVANT d'écrire quoi que ce soit
            if travail is not None:
                ecrire_copie_de_travail(img8, travail, meta["largeur"], meta["hauteur"],
                                        meta["dpi"],
                                        icc=icc if img8.mode == meta["mode"] else None)
                ecrits.append(travail)
            _ecrire_derive(img8, web_path, (meta["largeur"], meta["hauteur"]))
            ecrits.append(web_path)

        chemin_tiff = _rel_posix(travail) if travail is not None else None
        chemin_web = _rel_posix(web_path)

        # Matériel de numérisation (A6) : résolution + mode du SCAN, pas de la copie de
        # travail (IMG-1) — un fait du fichier numérisé. `dpi` est une paire ou None.
        dpi_x, dpi_y = meta["dpi"] if meta["dpi"] else (None, None)
        cur = conn.execute(
            """
            INSERT INTO planches
                (album_id, numero, chemin_tiff, chemin_web,
                 largeur_px, hauteur_px, dpi_x, dpi_y, mode, statut, master_origine)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'importee', ?)
            """,
            (album_id, numero, chemin_tiff, chemin_web,
             meta["largeur"], meta["hauteur"], dpi_x, dpi_y, meta["mode"], origine),
        )
    except BaseException:
        for f in ecrits:
            f.unlink(missing_ok=True)
        raise
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
        "master_origine": origine,
    }


def dossiers_d_album(album_id: int) -> tuple[str, str]:
    """Les deux dossiers d'images d'un album, sous la forme des chemins stockés en base
    (`planches.chemin_*` : relatifs à DATA_DIR, POSIX), barre finale comprise — de quoi
    reconnaître, par un préfixe exact, un fichier qui vit dans l'un d'eux."""
    return tuple(_rel_posix(racine / f"album_{album_id}") + "/"
                 for racine in (CORPUS_DIR, DERIVATIVES_DIR))


def remove_album_files(album_id: int, garder=frozenset()) -> None:
    """Supprime les dossiers corpus/derivatives d'un album (best-effort).

    `garder` (COL-3, tranche 3, D6) : les chemins — sous la forme de `planches.chemin_*` —
    qu'une AUTRE planche emploie encore. Une copie SŒUR pointe vers les fichiers de la copie
    dont elle a été tirée : les images appartiennent au document, et un fichier ne quitte le
    disque que lorsque plus aucune planche ne le désigne. Un dossier qui ne contient aucun
    fichier gardé part en entier, comme avant (y compris ce qu'aucune planche ne désigne, un
    master orphelin d'un import raté) ; sinon seuls ses autres fichiers partent, et il reste
    pour la sœur. C'est le risque irréversible de la tranche : une image effacée sous une
    sœur ne se rattrape pas."""
    import shutil
    garder = {(DATA_DIR / g).resolve() for g in garder if g}
    for racine in (CORPUS_DIR, DERIVATIVES_DIR):
        dossier = racine / f"album_{album_id}"
        if not dossier.is_dir():
            continue
        dedans = dossier.resolve()
        if not any(dedans in g.parents for g in garder):
            shutil.rmtree(dossier, ignore_errors=True)
            continue
        for f in sorted(dossier.rglob("*"), reverse=True):
            try:
                if f.is_file() and f.resolve() not in garder:
                    f.unlink()
                elif f.is_dir():
                    f.rmdir()                       # seulement s'il est vide
            except OSError:  # pragma: no cover - garde défensive (non vide, permissions…)
                pass


_CHEMIN_D_IMAGE = re.compile(r"(corpus|derivatives)/album_\d+/[^/]+")


def chemin_d_image_sur(chemin: str | None) -> bool:
    """Ce chemin, lu en base, désigne-t-il bien une image d'album — et RIEN d'autre ? COL-3,
    tranche 3 (relecture croisée). Un ménage qui efface d'après la base efface ce qu'elle
    désigne : une ligne retouchée à la main, un chemin absolu, un `..`, et l'effacement
    sortirait des dossiers d'images. Ne passe qu'un chemin RELATIF de la forme
    `corpus|derivatives/album_<N>/<fichier>`, qui se résout bien sous ces dossiers."""
    if not chemin or not _CHEMIN_D_IMAGE.fullmatch(chemin):
        return False
    try:
        racine = (DATA_DIR / chemin).resolve().parent.parent
    except (OSError, ValueError):       # pragma: no cover - garde défensive
        return False
    return racine in (CORPUS_DIR.resolve(), DERIVATIVES_DIR.resolve())


def elaguer_dossier_d_album(chemin: str | None) -> None:
    """Retire le dossier `album_<N>` qui contenait ce fichier s'il est désormais VIDE —
    celui d'une copie détruite avant la sœur qui employait ses images (D6, « les dossiers
    vides sont élagués à la destruction du document »). Ne touche qu'un dossier
    `album_<nombre>` posé directement sous `corpus/` ou `derivatives/` ; best-effort."""
    if not chemin:
        return
    dossier = (DATA_DIR / chemin).parent
    if not re.fullmatch(r"album_\d+", dossier.name):
        return
    if dossier.parent.resolve() not in (CORPUS_DIR.resolve(), DERIVATIVES_DIR.resolve()):
        return
    try:
        dossier.rmdir()                             # seulement s'il est vide
    except OSError:
        pass


def ecarter_dossiers_d_album(album_id: int) -> list[Path]:
    """Met de côté les dossiers `album_<id>` qui existent DÉJÀ, à la naissance d'un album
    (COL-3, relecture croisée de la tranche 2). Rend les chemins où ils sont partis.

    Un identifiant d'album pouvait revenir — d'avant la v30, ou rendu par une transaction
    défaite — et l'album neuf retrouvait alors les images de l'album détruit : ses
    planches se seraient rangées parmi elles, numéros compris. Un tel dossier n'est donc
    JAMAIS réutilisé tel quel : il est renommé `album_<id>.ecarte-<date>` à côté de lui,
    jamais effacé — ce qu'il contient n'est peut-être à personne, mais on ne le sait pas —,
    et le journal du serveur le dit."""
    import datetime
    import logging
    marque = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    ecartes = []
    for racine in (CORPUS_DIR, DERIVATIVES_DIR):
        dossier = racine / f"album_{album_id}"
        if not dossier.exists():
            continue
        cible, n = racine / f"album_{album_id}.ecarte-{marque}", 1
        while cible.exists():
            n += 1
            cible = racine / f"album_{album_id}.ecarte-{marque}-{n}"
        dossier.rename(cible)
        logging.getLogger("bd_annotator").warning(
            "Album %s : le dossier %s existait déjà à sa création ; il est mis de côté sous "
            "%s, rien n'est effacé.", album_id, dossier, cible)
        ecartes.append(cible)
    return ecartes


def remove_planche_files(chemin_tiff: str | None, chemin_web: str | None,
                         garder=frozenset()) -> None:
    """Supprime l'image de travail (`chemin_tiff` : la copie de travail depuis IMG-1, le
    master d'une planche d'avant la v34) et le dérivé web d'une planche (best-effort).
    `garder` : ceux des deux chemins qu'une AUTRE planche emploie encore — une copie sœur
    (D6) —, qui restent."""
    for rel in (chemin_tiff, chemin_web):
        if rel and rel not in garder:
            try:
                (DATA_DIR / rel).unlink(missing_ok=True)
            except OSError:  # pragma: no cover - garde défensive (permissions…)
                pass
