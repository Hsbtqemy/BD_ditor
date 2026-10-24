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
    # Le dérivé est tiré du SCAN, pas de la copie réduite : sous le plancher de 1 600 px, il
    # garde la taille du scan (IMG-1, 2026-10-24).
    with Image.open(data_dir / p["chemin_web"]) as web:
        assert web.size == (800, 1000)
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
    du SCAN — 1 750 × 200 pour un scan de 7 000 px —, pas se mesurer à une copie déjà réduite
    (5 250 px à 300 dpi effectifs), où le plancher de 1 600 px l'aurait relevé à 1 600 × 183.
    Le scan est une bande, pour rester léger."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    import regenerer_derives as rd
    p = _importer(client, album["id"], _scan(taille=(7000, 800), dpi=(400, 400))[0])
    web = data_dir / p["chemin_web"]
    web.unlink()
    conn = database.get_connection()
    try:
        rd_data = rd.DATA_DIR
        rd.DATA_DIR = data_dir
        try:
            bilan = rd.regenerer(conn, rd.planches_selectionnees(conn, planche=p["id"]),
                                 appliquer=True)
        finally:
            rd.DATA_DIR = rd_data
    finally:
        conn.close()
    assert bilan["regeneres"] == [p["id"]]
    with Image.open(web) as im:
        assert im.size == (1750, 200)


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


# --------------------------------------------------------------------------- #
# Relecture croisée : ce qu'un import efface sur un échec est forcément le sien
# --------------------------------------------------------------------------- #
def _fichiers(data_dir) -> dict:
    return {f.relative_to(data_dir).as_posix(): f.read_bytes()
            for racine in ("corpus", "derivatives") if (data_dir / racine).is_dir()
            for f in sorted((data_dir / racine).rglob("*")) if f.is_file()}


def test_un_second_import_au_meme_numero_ne_touche_pas_aux_fichiers_du_premier(
        client, album, data_dir, db_path):
    """Reproduit par la relecture croisée : le second import d'un même numéro écrivait sur
    les fichiers du premier, puis, refusé par l'index unique, les EFFAÇAIT en partant — la
    planche validée n'avait plus d'image. Il est refusé avant d'écrire quoi que ce soit."""
    c1, c2 = database.get_connection(), database.get_connection()
    try:
        p1 = ingest.ingest_image(c1, album["id"], _scan(dpi=(400, 400))[0], numero=1,
                                 origine="a.tif")
        c1.commit()
        avant = _fichiers(data_dir)
        with pytest.raises(ingest.NumeroPris):
            ingest.ingest_image(c2, album["id"], _scan(dpi=None)[0], numero=1,
                                origine="b.tif")
        c2.rollback()
    finally:
        c1.close()
        c2.close()
    assert _fichiers(data_dir) == avant
    assert set(avant) == {p1["chemin_tiff"], p1["chemin_web"]}


def test_deux_imports_simultanes_recoivent_deux_numeros(client, album, data_dir,
                                                        monkeypatch):
    """Deux imports lisent le MÊME numéro libre avant que l'un ou l'autre ait réservé quoi
    que ce soit (une barrière les y force) : la réservation exclusive fait passer le second
    au suivant, et chacune des deux planches garde SES fichiers."""
    import threading
    vrai = ingest.prochain_numero_libre
    barriere = threading.Barrier(2, timeout=20)
    premiers = set()

    def lent(conn, album_id):
        n = vrai(conn, album_id)
        if threading.get_ident() not in premiers:     # le premier appel de chaque fil
            premiers.add(threading.get_ident())
            barriere.wait()
        return n

    monkeypatch.setattr(ingest, "prochain_numero_libre", lent)
    rendus, erreurs = {}, []

    def importer(couleur):
        conn = database.get_connection()
        try:
            img = Image.new("RGB", (400, 500), couleur)
            buf = io.BytesIO()
            img.save(buf, "TIFF")
            rendus[couleur] = ingest.ingest_image(conn, album["id"], buf.getvalue(),
                                                  origine=f"{couleur}.tif")
            conn.commit()
        except Exception as exc:                     # pragma: no cover - dit par l'assert
            erreurs.append(exc)
        finally:
            conn.close()

    fils = [threading.Thread(target=importer, args=(c,)) for c in ("red", "blue")]
    for f in fils:
        f.start()
    for f in fils:
        f.join(30)
    assert erreurs == []
    assert sorted(p["numero"] for p in rendus.values()) == [1, 2]
    for couleur, p in rendus.items():
        for chemin in (p["chemin_tiff"], p["chemin_web"]):
            with Image.open(data_dir / chemin) as im:
                r, g, b = im.convert("RGB").getpixel((10, 10))
            assert (r > 200 and b < 60) if couleur == "red" else (b > 200 and r < 60), (
                couleur, chemin, (r, g, b))


def test_un_echec_apres_l_ecriture_de_la_copie_ne_laisse_aucun_fichier(
        client, album, data_dir, monkeypatch):
    """Le dérivé échoue APRÈS que la copie de travail est écrite : la copie part aussi, et
    les témoins de réservation avec elle."""
    def panne(*a, **k):
        raise OSError("disque plein")
    monkeypatch.setattr(ingest, "_ecrire_derive", panne)
    conn = database.get_connection()
    try:
        with pytest.raises(OSError, match="disque plein"):
            ingest.ingest_image(conn, album["id"], _scan()[0], origine="s.tif")
    finally:
        conn.close()
    assert _fichiers(data_dir) == {}


def test_un_insert_refuse_ne_laisse_aucun_fichier(client, album, data_dir, db_path):
    """L'index unique refuse l'`INSERT` — une planche de ce numéro existe dans l'album, ses
    fichiers ailleurs (une copie sœur désigne ceux de sa source) : les fichiers écrits pour
    rien partent, et seulement eux."""
    c = sqlite3.connect(db_path)
    c.execute("INSERT INTO planches (album_id, numero, chemin_web) VALUES (?, 5, ?)",
              (album["id"], "derivatives/album_999/planche_0001.jpg"))
    c.commit()
    c.close()
    conn = database.get_connection()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            ingest.ingest_image(conn, album["id"], _scan()[0], numero=5, origine="s.tif")
        conn.rollback()
    finally:
        conn.close()
    assert _fichiers(data_dir) == {}


def test_un_fichier_source_au_chemin_vise_n_est_ni_reecrit_ni_efface(client, album,
                                                                      data_dir):
    """`source` est un chemin qui appartient à l'appelant : posé là où l'ingest écrirait la
    copie de la planche 1, il n'est pas touché — le numéro 1 est sauté."""
    source = data_dir / "corpus" / f"album_{album['id']}" / "planche_0001.jpg"
    source.parent.mkdir(parents=True, exist_ok=True)
    _, img = _scan(dpi=None)
    img.save(source, "JPEG", quality=95)
    octets = source.read_bytes()
    conn = database.get_connection()
    try:
        p = ingest.ingest_image(conn, album["id"], source)
        conn.commit()
    finally:
        conn.close()
    assert p["numero"] == 2 and p["master_origine"] == "planche_0001.jpg"
    assert source.read_bytes() == octets


# `master_origine` ne sort d'aucune route : `tests/test_master_origine_tue.py` le BALAIE sur
# l'inventaire (la liste écrite ici à la main en avait oublié une, `PATCH …/role`).


# --------------------------------------------------------------------------- #
# Contre-relecture : un import tué, un dossier occupé par un fichier
# --------------------------------------------------------------------------- #
def test_un_numero_reserve_par_un_import_interrompu_est_dit_par_le_409(client, album,
                                                                       data_dir):
    """Un import tué après sa réservation laisse deux fichiers VIDES, que rien ne retire :
    le numéro est sauté par les imports suivants, et un import qui l'impose reçoit un 409
    qui nomme cette cause possible — rien n'est effacé."""
    ingest._reserver([data_dir / "corpus" / f"album_{album['id']}" / "planche_0001.jpg",
                      data_dir / "derivatives" / f"album_{album['id']}" / "planche_0001.jpg"])
    assert _importer(client, album["id"], _scan()[0])["numero"] == 2
    r = client.post(f"/api/albums/{album['id']}/import", data={"numero": "1"},
                    files={"file": ("s.tif", _scan()[0], "image/tiff")})
    assert r.status_code == 409, r.text
    assert "import interrompu" in r.json()["detail"]
    vides = [k for k, v in _fichiers(data_dir).items() if not v]
    assert sorted(vides) == [f"corpus/album_{album['id']}/planche_0001.jpg",
                             f"derivatives/album_{album['id']}/planche_0001.jpg"]


def test_un_fichier_a_la_place_du_dossier_de_l_album_est_nomme_sans_cinquante_essais(
        client, album, data_dir, monkeypatch):
    """Un FICHIER occupe `corpus/album_N` : ce n'est pas une course, et l'erreur le dit au
    premier essai au lieu d'essayer cinquante numéros pour la même cause."""
    (data_dir / "corpus").mkdir(exist_ok=True)
    (data_dir / "corpus" / f"album_{album['id']}").write_bytes(b"")
    vrai, appels = ingest.prochain_numero_libre, []
    monkeypatch.setattr(ingest, "prochain_numero_libre",
                        lambda c, a: appels.append(1) or vrai(c, a))
    conn = database.get_connection()
    try:
        with pytest.raises(OSError, match=r"album_\d+ ne peut pas être créé") as exc:
            ingest.ingest_image(conn, album["id"], _scan()[0])
    finally:
        conn.close()
    assert not isinstance(exc.value, FileExistsError)
    assert len(appels) == 1


def test_un_numero_qui_revient_refuse_arrete_la_boucle_en_le_nommant(client, album,
                                                                     data_dir, monkeypatch,
                                                                     caplog):
    """Ce qui occupe un chemin sans que `numero_occupe` le voie (un lien cassé, par exemple)
    faisait rendre le même numéro cinquante fois : au second retour, l'ingest s'arrête et
    nomme le chemin — au JOURNAL DU SERVEUR et dans `chemin`, plus dans le message, qui sort
    par la réponse de l'import (contre-relecture d'UX-11)."""
    bloque = data_dir / "derivatives" / f"album_{album['id']}" / "planche_0001.jpg"
    bloque.parent.mkdir(parents=True)
    bloque.write_bytes(b"x")
    monkeypatch.setattr(ingest, "numero_occupe", lambda conn, a, n: False)
    appels = []
    vrai = ingest.prochain_numero_libre
    monkeypatch.setattr(ingest, "prochain_numero_libre",
                        lambda c, a: appels.append(1) or vrai(c, a))
    conn = database.get_connection()
    try:
        with pytest.raises(RuntimeError, match="numéro 1 est refusé") as exc:
            ingest.ingest_image(conn, album["id"], _scan()[0])
    finally:
        conn.close()
    assert "planche_0001.jpg" not in str(exc.value) and len(appels) == 2
    assert str(exc.value.chemin).endswith("planche_0001.jpg")
    assert "planche_0001.jpg" in caplog.text
    assert bloque.read_bytes() == b"x"

    # Par la route : un 400 qui ne dit aucun chemin du serveur.
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("page.png", _scan()[0], "image/png")})
    assert r.status_code == 400, r.text
    assert "planche_0001" not in r.text and "derivatives" not in r.text, r.text
