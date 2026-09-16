"""IMG-1 — un master de plus de 8 bits par pixel garde ses tons jusqu'au dérivé.

Le défaut que ce module ferme était silencieux de bout en bout : `convert("RGB")` ÉCRÊTE un
gris 16 bits au lieu de le réduire — 0, 100, 255 passent, et tout ce qui dépasse sort à 255.
L'import répondait 201 avec les bonnes dimensions, la planche apparaissait dans la
Bibliothèque, et c'est à l'écran seulement qu'on voyait une page blanche. L'OCR, qui ouvre
le master, lui appliquait la même conversion : il lisait du blanc même quand le dérivé était
juste.

**Un test de dérivé passe sur n'importe quel dérivé**, et c'est le piège dont ce module se
garde. Chaque fichier forgé est d'abord ROUVERT pour établir qu'il porte bien des valeurs
au-delà de 255 dans le mode attendu ; sans ce contrôle, un encodeur qui aurait réduit en
8 bits à l'écriture rendrait tous les tests suivants verts sur le code fautif. Et on n'exige
pas « pas trop blanc », qui passerait sur une image grise uniforme : on exige que le dérivé
SUIVE le dégradé, colonne par colonne.
"""
import io
import struct
from pathlib import Path

import pytest
from PIL import Image, features

from conftest import ADMIN

# Le dégradé : 1024 colonnes de 0 à la valeur maximale. Au quart (`WEB_SCALE`), le dérivé en
# garde 256 — la colonne j du dérivé vaut alors j, à la compression JPEG près.
LARGEUR, HAUTEUR = 1024, 16
TOLERANCE = 8          # bruit JPEG sur un dégradé lisse, très en deçà de l'écart mesuré
COLONNES = (16, 64, 128, 192, 240)


def _degrade(maximum: int) -> list[int]:
    ligne = [x * maximum // (LARGEUR - 1) for x in range(LARGEUR)]
    return ligne * HAUTEUR


def _degrade_16_bits(format_: str, mode: str, **options) -> bytes:
    im = Image.new(mode, (LARGEUR, HAUTEUR))
    im.putdata(_degrade(65535))
    buf = io.BytesIO()
    im.save(buf, format_, **options)
    return buf.getvalue()


def _tiff_gris(largeur: int, hauteur: int, bits: int, donnees: bytes,
               format_echantillon: int = 1) -> bytes:
    """TIFF petit-boutiste non compressé, une bande. Pillow n'ÉCRIT ni le 12 bits ni le
    16 bits signé : il faut poser l'en-tête à la main."""
    entrees = [
        (256, 3, largeur), (257, 3, hauteur), (258, 3, bits), (259, 3, 1),
        (262, 3, 1), (273, 4, None), (277, 3, 1), (278, 3, hauteur),
        (279, 4, len(donnees)), (339, 3, format_echantillon),
    ]
    debut_donnees = 8 + 2 + len(entrees) * 12 + 4
    b = b"II" + struct.pack("<HI", 42, 8) + struct.pack("<H", len(entrees))
    for balise, type_, valeur in entrees:
        if balise == 273:
            valeur = debut_donnees
        b += (struct.pack("<HHIHH", balise, type_, 1, valeur, 0) if type_ == 3
              else struct.pack("<HHII", balise, type_, 1, valeur))
    return b + struct.pack("<I", 0) + donnees


def _degrade_12_bits() -> bytes:
    bits = "".join(f"{v:012b}" for v in _degrade(4095))
    bits += "0" * (-len(bits) % 8)
    return _tiff_gris(LARGEUR, HAUTEUR, 12, int(bits, 2).to_bytes(len(bits) // 8, "big"))


_JP2 = pytest.mark.skipif(not features.check("jpg_2000"),
                          reason="Pillow compilé sans OpenJPEG")

# (nom de fichier, octets, mode attendu à la relecture, valeur maximale portée)
CAS = [
    pytest.param("planche.tif", lambda: _degrade_16_bits("TIFF", "I;16"), "I;16", 65535,
                 id="tiff-I;16"),
    pytest.param("planche.tif", lambda: _degrade_16_bits("TIFF", "I;16B"), "I;16B", 65535,
                 id="tiff-I;16B"),
    # Un scan réel est presque toujours compressé, et passe alors par libtiff : un autre
    # décodeur que le TIFF brut ci-dessus.
    pytest.param("planche.tif",
                 lambda: _degrade_16_bits("TIFF", "I;16", compression="tiff_lzw"),
                 "I;16", 65535, id="tiff-I;16-lzw"),
    pytest.param("planche.png", lambda: _degrade_16_bits("PNG", "I;16"), "I;16", 65535,
                 id="png-I;16"),
    pytest.param("planche.jp2", lambda: _degrade_16_bits("JPEG2000", "I;16"), "I;16", 65535,
                 id="jp2-I;16", marks=_JP2),
    # Pillow range un TIFF 12 bits en `I;16` SANS étendre ses valeurs : 4095 y reste 4095.
    # Diviser tout `I;16` par 256 corrigerait le blanc en fabriquant du noir.
    pytest.param("planche.tif", _degrade_12_bits, "I;16", 4095, id="tiff-12-bits"),
]


def _colonnes(img: Image.Image, echelle: float) -> dict[int, int]:
    """Valeur, dans l'image fournie, de chaque colonne témoin du dérivé (ligne médiane)."""
    gris = img.convert("L")
    return {j: gris.getpixel((round(j / echelle), gris.height // 2)) for j in COLONNES}


# --------------------------------------------------------------------------- #
# D'abord : le fichier forgé porte bien ce qu'on croit
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("nom, fabrique, mode, maximum", CAS)
def test_le_fichier_forge_porte_bien_plus_de_8_bits(nom, fabrique, mode, maximum):
    im = Image.open(io.BytesIO(fabrique()))
    assert im.mode == mode
    # `getextrema` refuse `I;16B` ; `convert("I")`, lui, préserve les valeurs (mesuré).
    assert im.convert("I").getextrema() == (0, maximum), (
        "le fichier forgé n'a pas la dynamique annoncée : les tests suivants passeraient "
        "sur un dérivé quelconque")


# --------------------------------------------------------------------------- #
# Le dérivé, par la route d'import
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("nom, fabrique, mode, maximum", CAS)
def test_l_import_donne_un_derive_qui_suit_les_tons_du_master(client, album, data_dir,
                                                              nom, fabrique, mode, maximum):
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": (nom, fabrique(), "application/octet-stream")},
                    headers=ADMIN)
    assert r.status_code == 201, r.text
    assert r.json()["mode"] == mode              # le matériel décrit le MASTER, pas le dérivé

    with Image.open(data_dir / r.json()["chemin_web"]) as derive:
        assert derive.width == LARGEUR // 4
        valeurs = _colonnes(derive, 1.0)
    ecarts = {j: v for j, v in valeurs.items() if abs(v - j) > TOLERANCE}
    assert not ecarts, (
        f"dérivé qui ne suit pas le dégradé (colonne → valeur, attendu ≈ colonne) : "
        f"{valeurs}")


# --------------------------------------------------------------------------- #
# L'OCR, qui ouvre le master et non le dérivé
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("nom, fabrique, mode, maximum", CAS)
def test_l_OCR_lit_le_master_sans_l_ecreter(tmp_path, monkeypatch,
                                            nom, fabrique, mode, maximum):
    """Corriger le dérivé seul laissait l'OCR lire une page blanche sur le même master."""
    import pipeline.ocr as ocr
    monkeypatch.setattr(ocr, "DATA_DIR", tmp_path)
    (tmp_path / nom).write_bytes(fabrique())

    img, echelle = ocr._open_image({"chemin_tiff": nom, "chemin_web": "absent.jpg",
                                    "largeur_px": LARGEUR})
    try:
        assert echelle == 1.0                    # c'est bien le MASTER qui a été ouvert
        assert img.mode in ("L", "RGB")          # ce que le lecteur OCR sait recevoir
        valeurs = _colonnes(img, 0.25)
    finally:
        img.close()
    ecarts = {j: v for j, v in valeurs.items() if abs(v - j) > TOLERANCE}
    assert not ecarts, f"master lu écrêté par l'OCR : {valeurs}"


# --------------------------------------------------------------------------- #
# Ce qu'on ne sait pas convertir juste est refusé, en le nommant
# --------------------------------------------------------------------------- #
def _tiff_mode(mode: str, valeurs) -> bytes:
    im = Image.new(mode, (len(valeurs), 1))
    im.putdata(list(valeurs))
    buf = io.BytesIO()
    im.save(buf, "TIFF")
    return buf.getvalue()


REFUSES = [
    # Le mode `I` ne dit pas sa profondeur : Pillow y range le 16 bits SIGNÉ comme le
    # 32 bits, et relit un 32 bits non signé à 4294967295 comme -1. Aucune réduction n'est
    # juste pour tous.
    pytest.param("I", lambda: _tiff_mode("I", (0, 255, 65535, 1 << 20)), id="I-32-bits"),
    pytest.param("I", lambda: _tiff_gris(4, 1, 16, struct.pack("<4h", -32768, 0, 100, 32767),
                                         format_echantillon=2), id="I-16-bits-signe"),
    # Le flottant n'a pas d'échelle : 1,0 est le blanc d'une convention et le noir d'une
    # autre.
    pytest.param("F", lambda: _tiff_mode("F", (0.0, 0.5, 1.0, 255.0)), id="F"),
]


@pytest.mark.parametrize("mode, fabrique", REFUSES)
def test_un_mode_sans_echelle_connue_est_refuse_a_l_import(client, album, data_dir,
                                                           mode, fabrique):
    im = Image.open(io.BytesIO(fabrique()))
    assert im.mode == mode                       # le leurre en est bien un

    fichiers = lambda: {p for p in Path(data_dir).rglob("*")    # noqa: E731
                        if p.is_file() and p.parent.name.startswith("album_")}
    avant = fichiers()
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("planche.tif", fabrique(), "image/tiff")},
                    headers=ADMIN)
    assert r.status_code == 400, r.text
    assert f"« {mode} »" in r.json()["detail"], (
        f"le refus ne nomme pas le mode : {r.json()['detail']}")
    assert fichiers() == avant, f"fichier(s) laissé(s) : {sorted(fichiers() - avant)}"


@pytest.mark.parametrize("mode, fabrique", REFUSES)
def test_l_OCR_refuse_aussi_en_nommant_le_mode(tmp_path, monkeypatch, mode, fabrique):
    """Un master antérieur au refus est relu à chaque passe : il doit échouer en le disant,
    et non rendre une page blanche."""
    import pipeline.ocr as ocr
    monkeypatch.setattr(ocr, "DATA_DIR", tmp_path)
    (tmp_path / "master.tif").write_bytes(fabrique())
    with pytest.raises(ocr.OCRError, match=f"« {mode} »"):
        ocr._open_image({"chemin_tiff": "master.tif", "chemin_web": "absent.jpg",
                         "largeur_px": 4})
