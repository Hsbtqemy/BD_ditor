"""La copie de travail à l'import (IMG-1, décidé par Hugo le 2026-10-21).

Le serveur ne garde plus le fichier reçu mais une COPIE DE TRAVAIL : un JPEG qualité 80 à
300 dpi effectifs. Un scan plus fin est réduit jusque-là (un 400 dpi → 75 %) ; un scan à 300
ou moins, ou sans résolution écrite, est gardé à sa taille. La planche garde la géométrie
et le matériel du SCAN (`largeur_px`, `dpi_x`, `mode`), et ce que l'outil sait du master
d'archive (`master_origine`).

Ce qui échouerait en silence, et que ce fichier tient :

1. **Les coordonnées restent en pixels du scan.** Une région tracée sur la copie de travail
   doit recadrer le MÊME endroit qu'elle recadrait sur le master : la Transcription, les
   figures et l'OCR lisent `chemin_tiff`, qui désignait le master à la taille du scan et
   s'ouvrait avec une échelle de 1 en dur. Oublier l'échelle décalerait chaque bulle de
   4/3, sans erreur — d'où une image fabriquée dont on connaît le contenu : un carré rouge
   à une place connue, un carré bleu à côté.
2. **On ne réduit pas ce qu'on ne sait pas mesurer** : un fichier sans résolution est gardé
   à sa taille, et aucune résolution n'est inventée.
3. **Le décodage se fait hors de toute transaction d'écriture** : un JPEG 2000 sans perte
   y met ~5 s, pendant lesquelles toute autre écriture attendrait puis recevrait un 409.
"""
import io
import sqlite3

import httpx
import numpy as np
import pytest
from PIL import Image, ImageDraw

import database
from pipeline import ingest
from pipeline import ocr as ocr_mod
from pipeline import segmentation as seg

ROUGE = (220, 20, 20)
BLEU = (20, 20, 220)
# Le carré rouge, en pixels du SCAN (800 × 1000) : x, y, w, h.
CARRE = (200, 300, 200, 200)


def _scan(fmt="TIFF", taille=(800, 1000), dpi=(400, 400)) -> tuple[bytes, Image.Image]:
    """Un scan fabriqué : fond blanc, le carré rouge à `CARRE`, un carré bleu tout près —
    une région recadrée au mauvais endroit y prend du blanc ou du bleu."""
    img = Image.new("RGB", taille, "white")
    d = ImageDraw.Draw(img)
    x, y, w, h = CARRE
    d.rectangle((x, y, x + w - 1, y + h - 1), fill=ROUGE)
    d.rectangle((420, 520, 619, 719), fill=BLEU)
    buf = io.BytesIO()
    img.save(buf, fmt, **({"dpi": dpi} if dpi else {}))
    return buf.getvalue(), img


def _importer(client, album_id, data, nom="scan.tif", mime="image/tiff"):
    r = client.post(f"/api/albums/{album_id}/import", files={"file": (nom, data, mime)})
    assert r.status_code == 201, r.text
    return r.json()


def _part_rouge(arr: np.ndarray) -> float:
    """La part des pixels franchement rouges d'une image RVB."""
    rouge = (arr[..., 0] > 150) & (arr[..., 1] < 90) & (arr[..., 2] < 90)
    return float(rouge.mean())


# --------------------------------------------------------------------------- #
# Ce que l'import écrit
# --------------------------------------------------------------------------- #
def test_un_tiff_a_400_dpi_devient_un_jpeg_a_300_dpi_effectifs(client, album, data_dir,
                                                                db_path):
    data, _ = _scan(dpi=(400, 400))
    p = _importer(client, album["id"], data, nom="Scan 0042.tif")
    # La copie de travail : un JPEG aux trois quarts du scan, à 300 dpi effectifs.
    assert p["chemin_tiff"] == f"corpus/album_{album['id']}/planche_0001.jpg"
    with Image.open(data_dir / p["chemin_tiff"]) as copie:
        assert copie.format == "JPEG"
        assert copie.size == (600, 750)
        assert tuple(round(d) for d in copie.info["dpi"]) == (300, 300)
    # La planche, elle, garde la géométrie et le matériel du SCAN.
    ligne = database_ligne(db_path, p["id"])
    assert (ligne["largeur_px"], ligne["hauteur_px"]) == (800, 1000)
    assert (ligne["dpi_x"], ligne["dpi_y"], ligne["mode"]) == (400, 400, "RGB")
    assert ligne["master_origine"] == "Scan 0042.tif"
    # Le dérivé reste ce qu'il est : 25 % du SCAN.
    with Image.open(data_dir / p["chemin_web"]) as web:
        assert web.size == (200, 250)
    # Et le fichier reçu n'est nulle part sur le serveur.
    assert sorted(f.name for f in (data_dir / "corpus").rglob("*") if f.is_file()) == [
        "planche_0001.jpg"]
    # Les centimètres ne changent pas : 800 px à 400 dpi.
    planche = client.get(f"/api/albums/{album['id']}/planches").json()[0]
    assert planche["dimensions_cm"] == database.dimensions_cm(800, 1000, 400, 400)
    assert planche["dimensions_cm"]["largeur"] == 5.1


def database_ligne(db_path, planche_id) -> dict:
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return dict(c.execute("SELECT * FROM planches WHERE id = ?", (planche_id,)).fetchone())
    finally:
        c.close()


@pytest.mark.parametrize("dpi", [(300, 300), (200, 200), None],
                         ids=["300 dpi", "200 dpi", "sans résolution"])
def test_a_300_dpi_ou_moins_et_sans_resolution_la_taille_est_gardee(client, album, data_dir,
                                                                    db_path, dpi):
    data, _ = _scan(dpi=dpi)
    p = _importer(client, album["id"], data)
    with Image.open(data_dir / p["chemin_tiff"]) as copie:
        assert copie.format == "JPEG" and copie.size == (800, 1000)
        # Aucune résolution inventée : le fichier n'en dit que si le scan en disait.
        assert ("dpi" in copie.info) is (dpi is not None)
    ligne = database_ligne(db_path, p["id"])
    assert (ligne["largeur_px"], ligne["hauteur_px"]) == (800, 1000)
    assert (ligne["dpi_x"], ligne["dpi_y"]) == (dpi or (None, None))


def test_un_jp2_sans_resolution_donne_un_jpeg_a_sa_taille(client, album, data_dir, db_path):
    """Les JPEG 2000 de l'équipe n'écrivent aucune résolution (mesuré le 2026-10-21) : gardés
    à 100 %, sans centimètres."""
    data, _ = _scan(fmt="JPEG2000", dpi=None)
    p = _importer(client, album["id"], data, nom="P0001.jp2", mime="image/jp2")
    with Image.open(data_dir / p["chemin_tiff"]) as copie:
        assert copie.format == "JPEG" and copie.size == (800, 1000)
    ligne = database_ligne(db_path, p["id"])
    assert (ligne["dpi_x"], ligne["mode"], ligne["master_origine"]) == (None, "RGB",
                                                                        "P0001.jp2")
    assert not list((data_dir / "corpus").rglob("*.jp2"))


def test_un_scan_refuse_n_ecrit_rien(client, album, data_dir):
    """Un mode sans réduction juste en 8 bits est refusé AVANT toute écriture : ni copie,
    ni dérivé, ni fichier reçu."""
    buf = io.BytesIO()
    Image.new("F", (50, 60), 0.5).save(buf, "TIFF")
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("f.tif", buf.getvalue(), "image/tiff")})
    assert r.status_code == 400, r.text
    assert [f for f in data_dir.rglob("*") if f.is_file() and f.suffix != ".sqlite"
            and "sqlite" not in f.name] == []


def test_le_decodage_ne_tient_pas_le_verrou_d_ecriture(client, album, db_path, monkeypatch):
    """Pendant que l'ingest décode le scan, une AUTRE connexion doit pouvoir écrire tout de
    suite (`BEGIN IMMEDIATE` sans attendre) : aucune transaction d'écriture n'est ouverte."""
    vrai = ingest.image_8_bits
    libres = []

    def guetteur(img):
        autre = sqlite3.connect(db_path, timeout=0)
        try:
            autre.execute("BEGIN IMMEDIATE")
            autre.rollback()
            libres.append(True)
        except sqlite3.OperationalError:
            libres.append(False)
        finally:
            autre.close()
        return vrai(img)

    monkeypatch.setattr(ingest, "image_8_bits", guetteur)
    _importer(client, album["id"], _scan()[0])
    _importer(client, album["id"], _scan()[0])
    assert libres == [True, True]


# --------------------------------------------------------------------------- #
# ShareDocs : le chemin distant est noté
# --------------------------------------------------------------------------- #
BASE = "https://sharedocs.huma-num.fr/remote.php/dav/files/u"   # hôte autorisé (anti-SSRF)


def test_un_import_sharedocs_note_son_chemin_distant(client, album, data_dir, db_path,
                                                     monkeypatch):
    from pipeline import sharedocs as sd
    scan, _ = _scan(dpi=(400, 400))
    demandes = []

    def serveur(request: httpx.Request) -> httpx.Response:
        demandes.append((request.method, request.url.path))
        if request.method == "PROPFIND":
            return httpx.Response(207, text='<?xml version="1.0"?>'
                                             '<d:multistatus xmlns:d="DAV:"></d:multistatus>')
        return httpx.Response(200, content=scan)

    monkeypatch.setattr(sd, "_client", lambda user, password: httpx.Client(
        transport=httpx.MockTransport(serveur), auth=(user, password)))
    r = client.post("/api/sharedocs/connexion", json={"url": BASE, "user": "u",
                                                      "password": "p"})
    assert r.status_code == 200, r.text
    libres = []
    vrai = ingest.image_8_bits

    def guetteur(img):
        autre = sqlite3.connect(db_path, timeout=0)
        try:
            autre.execute("BEGIN IMMEDIATE")
            autre.rollback()
            libres.append(True)
        except sqlite3.OperationalError:
            libres.append(False)
        finally:
            autre.close()
        return vrai(img)

    monkeypatch.setattr(ingest, "image_8_bits", guetteur)
    r = client.post("/api/sharedocs/importer", json={
        "chemins": ["Projet/Scans/P0001.tif", "Projet/Scans/P0002.tif"],
        "album_id": album["id"]})
    assert r.status_code == 200, r.text
    importes = r.json()["importes"]
    assert [p["master_origine"] for p in importes] == [
        "sharedocs:Projet/Scans/P0001.tif", "sharedocs:Projet/Scans/P0002.tif"]
    assert any(m == "GET" and p.endswith("/Projet/Scans/P0002.tif") for m, p in demandes)
    for p in importes:
        ligne = database_ligne(db_path, p["id"])
        assert ligne["master_origine"] == p["master_origine"]
        assert (ligne["largeur_px"], ligne["dpi_x"]) == (800, 400)
        with Image.open(data_dir / ligne["chemin_tiff"]) as copie:
            assert copie.format == "JPEG" and copie.size == (600, 750)
    # La seconde planche se décode après le commit de la première : rien ne tient le verrou.
    assert libres == [True, True]
    assert not list((data_dir / "corpus").rglob("*.tif"))


# --------------------------------------------------------------------------- #
# La preuve qui compte : la région recadre le même endroit
# --------------------------------------------------------------------------- #
def _region(client, planche_id, type_="bulle"):
    x, y, w, h = CARRE
    r = client.post(f"/api/planches/{planche_id}/regions",
                    json={"type": type_, "x": x, "y": y, "w": w, "h": h})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _crop_du_master(master: Image.Image, taille) -> np.ndarray:
    x, y, w, h = CARRE
    return np.asarray(master.crop((x, y, x + w, y + h)).resize(taille, Image.LANCZOS),
                      dtype=np.int16)


def test_le_crop_d_une_region_est_le_meme_depuis_la_copie_de_travail(client, album):
    """`region_crop_png` (Transcription, vignettes, figures) : la région, en pixels du scan,
    recadre le carré rouge dans la copie de travail réduite — le même que dans le master, à
    la réduction près."""
    data, master = _scan(dpi=(400, 400))
    p = _importer(client, album["id"], data)
    region = _region(client, p["id"])
    r = client.get(f"/api/regions/{region['id']}/crop", params={"taille": 2000})
    assert r.status_code == 200, r.text
    crop = Image.open(io.BytesIO(r.content)).convert("RGB")
    assert crop.size == (150, 150)                     # 200 px du scan × 0,75
    arr = np.asarray(crop, dtype=np.int16)
    assert _part_rouge(arr) > 0.95
    assert np.abs(arr - _crop_du_master(master, crop.size)).mean() < 6


def test_l_ocr_recadre_la_meme_bulle_depuis_la_copie_de_travail(client, album, db_path,
                                                                monkeypatch):
    """Le chemin de l'OCR (`ocr_planche` → `_open_image`) : le moteur reçoit le carré rouge,
    à la taille de la copie — le cadre que le master lui aurait donné, réduit."""
    data, master = _scan(dpi=(400, 400))
    p = _importer(client, album["id"], data)
    _region(client, p["id"])
    vus = []

    class Lecteur:
        def readtext(self, arr, detail=0, paragraph=True):
            vus.append(np.asarray(arr, dtype=np.int16))
            return ["ROUGE"]

    monkeypatch.setattr(ocr_mod, "_get_reader", lambda langs: Lecteur())
    conn = database.get_connection()
    try:
        res = ocr_mod.ocr_planche(conn, p["id"])
        conn.commit()
    finally:
        conn.close()
    assert res["ocr"] == 1 and len(vus) == 1
    assert vus[0].shape == (150, 150, 3)
    assert _part_rouge(vus[0]) > 0.95
    assert np.abs(vus[0] - _crop_du_master(master, (150, 150))).mean() < 6


def test_kumiko_sur_la_copie_de_travail_pose_ses_cases_en_pixels_du_scan(client, album,
                                                                          monkeypatch):
    """`use_master=True` lit la copie de travail : un détecteur qui trouve le carré rouge
    dans l'image qu'on lui donne rend des coordonnées de CETTE image, que la segmentation
    ramène aux pixels du scan."""
    data, _ = _scan(dpi=(400, 400))
    p = _importer(client, album["id"], data)
    lus = []

    def detecteur(chemin):
        with Image.open(chemin) as im:
            arr = np.asarray(im.convert("RGB"))
        lus.append(arr.shape[:2])
        ys, xs = np.where((arr[..., 0] > 150) & (arr[..., 1] < 90) & (arr[..., 2] < 90))
        return {"size": [arr.shape[1], arr.shape[0]],
                "panels": [[int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1),
                            int(ys.max() - ys.min() + 1)]]}

    monkeypatch.setattr(seg, "run_kumiko", detecteur)
    conn = database.get_connection()
    try:
        res = seg.segment_planche(conn, p["id"], use_master=True)
        conn.commit()
    finally:
        conn.close()
    assert lus == [(750, 600)]                         # la copie de travail, pas le scan
    (case,) = res["regions"]
    assert all(abs(a - b) <= 2 for a, b in zip((case["x"], case["y"], case["w"], case["h"]),
                                               CARRE)), case


def test_regenerer_le_derive_depuis_la_copie_de_travail_garde_25_pourcent_du_scan(
        client, album, data_dir):
    """`tools/regenerer_derives.py` lit la copie de travail : le dérivé doit rester à 25 %
    du SCAN (200 × 250), pas tomber à 25 % d'une copie déjà réduite (150 × 188)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    import regenerer_derives as rd
    p = _importer(client, album["id"], _scan(dpi=(400, 400))[0])
    web = data_dir / p["chemin_web"]
    web.unlink()
    conn = database.get_connection()
    try:
        rd_data = rd.DATA_DIR
        rd.DATA_DIR = data_dir
        try:
            bilan = rd.regenerer(conn, rd.planches_selectionnees(conn, planche=p["id"]))
        finally:
            rd.DATA_DIR = rd_data
    finally:
        conn.close()
    assert bilan["regeneres"] == [p["id"]]
    with Image.open(web) as im:
        assert im.size == (200, 250)


def test_la_regle_de_reduction():
    """La règle, sans image : 300 dpi effectifs, jamais d'agrandissement, rien sans
    résolution, un seul facteur tiré de la plus basse des deux résolutions."""
    assert ingest.facteur_de_travail((400, 400)) == 0.75
    assert ingest.facteur_de_travail((600, 600)) == 0.5
    assert ingest.facteur_de_travail((300, 300)) == 1.0
    assert ingest.facteur_de_travail((150, 150)) == 1.0
    assert ingest.facteur_de_travail(None) == 1.0
    assert ingest.facteur_de_travail((400, 300)) == 1.0      # aucun axe sous 300
    assert ingest.taille_de_travail(3748, 4710, (400, 400)) == (2811, 3532)
    assert ingest.taille_de_travail(3748, 4710, None) == (3748, 4710)
