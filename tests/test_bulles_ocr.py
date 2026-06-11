"""Passe 2 (détection bulles) et passe 3 (OCR) — moteurs ML optionnels.

Les chemins « logique » sont testés en mockant l'appel moteur (rapide,
déterministe) ; un test d'intégration réel (gated) valide le bout-en-bout.
"""
import io

import pytest
from PIL import Image, ImageDraw, ImageFont

import database
import pipeline.bulles as bulles
import pipeline.ingest as ingest
import pipeline.ocr as ocr
from conftest import requires_bulles, requires_ocr


# ------------------------------ unités ---------------------------------- #
def test_parent_case_geometrie():
    cases = [{"id": 1, "x": 0, "y": 0, "w": 100, "h": 100},
             {"id": 2, "x": 200, "y": 0, "w": 50, "h": 50}]
    assert bulles._parent_case(cases, 50, 50) == 1     # dans la case 1
    assert bulles._parent_case(cases, 210, 10) == 2    # dans la case 2
    assert bulles._parent_case(cases, 500, 500) is None  # hors case


def test_parent_case_imbriquee_prend_la_plus_petite():
    cases = [{"id": 1, "x": 0, "y": 0, "w": 100, "h": 100},
             {"id": 2, "x": 10, "y": 10, "w": 20, "h": 20}]
    assert bulles._parent_case(cases, 15, 15) == 2  # la plus petite contenant


# ------------------------- détection bulles (mock) ---------------------- #
def _add_case(client, planche, x, y, w, h):
    return client.post(f"/api/planches/{planche['id']}/regions",
                       json={"type": "case", "x": x, "y": y, "w": w, "h": h}).json()


def test_detecter_bulles_mock(client, planche, monkeypatch):
    """_run mocké : une bulle dans une case -> rattachée par géométrie."""
    case = _add_case(client, planche, 0, 0, 400, 500)  # couvre le master 400x500
    # _run renvoie (orig_w, orig_h, [(x,y,w,h)]) en pixels image (= master ici)
    monkeypatch.setattr(bulles, "_run",
                        lambda path, conf: (400, 500, [(50, 60, 80, 40)]))
    r = client.post(f"/api/planches/{planche['id']}/detecter-bulles")
    assert r.status_code == 200
    body = r.json()
    assert body["nb_bulles"] == 1 and body["sans_case"] == 0
    regions = client.get(f"/api/planches/{planche['id']}/regions").json()
    bulle = next(x for x in regions if x["type"] == "bulle")
    assert bulle["parent_id"] == case["id"] and bulle["source"] == "auto"


def test_detecter_bulles_hors_case(client, planche, monkeypatch):
    monkeypatch.setattr(bulles, "_run",
                        lambda path, conf: (400, 500, [(5, 5, 10, 10)]))
    body = client.post(f"/api/planches/{planche['id']}/detecter-bulles").json()
    assert body["nb_bulles"] == 1 and body["sans_case"] == 1
    bulle = next(x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["type"] == "bulle")
    assert bulle["parent_id"] is None


def test_detecter_bulles_replace(client, planche, monkeypatch):
    monkeypatch.setattr(bulles, "_run", lambda path, conf: (400, 500, [(5, 5, 10, 10)]))
    client.post(f"/api/planches/{planche['id']}/detecter-bulles")
    client.post(f"/api/planches/{planche['id']}/detecter-bulles")  # relance
    bulles_n = [x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["type"] == "bulle"]
    assert len(bulles_n) == 1  # remplacées, pas accumulées


def test_detecter_bulles_503(client, planche, monkeypatch):
    monkeypatch.setattr("main.bulles_available", lambda: False)
    r = client.post(f"/api/planches/{planche['id']}/detecter-bulles")
    assert r.status_code == 503


def test_detecter_bulles_404(client):
    assert client.post("/api/planches/999/detecter-bulles").status_code == 404


def test_detecter_bulles_erreur_500(client, planche, monkeypatch):
    def boom(*a, **k):
        raise bulles.BullesError("explosion")
    monkeypatch.setattr("main.detect_bulles", boom)
    r = client.post(f"/api/planches/{planche['id']}/detecter-bulles")
    assert r.status_code == 500 and "explosion" in r.json()["detail"]


# ------------------------------- OCR (mock) ----------------------------- #
class _FakeReader:
    def __init__(self, text):
        self.text = text
    def readtext(self, img, detail=0, paragraph=True):
        return [self.text]


def _add_bulle(client, planche, x=10, y=10, w=80, h=40):
    return client.post(f"/api/planches/{planche['id']}/regions",
                       json={"type": "bulle", "x": x, "y": y, "w": w, "h": h}).json()


def test_ocr_mock_remplit_et_indexe(client, planche, monkeypatch):
    b = _add_bulle(client, planche)
    monkeypatch.setattr(ocr, "_get_reader", lambda langs: _FakeReader("BONJOUR ESTHER"))
    r = client.post(f"/api/planches/{planche['id']}/ocr")
    assert r.status_code == 200 and r.json()["ocr"] == 1
    # ocr_texte renseigné + recherchable
    reg = next(x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["id"] == b["id"])
    assert reg["ocr_texte"] == "BONJOUR ESTHER"
    res = client.get("/api/recherche", params={"q": "Esther"}).json()["results"]
    assert any(x["region_id"] == b["id"] for x in res)


def test_ocr_only_empty_preserve_corrections(client, planche, monkeypatch):
    b = _add_bulle(client, planche)
    client.put(f"/api/regions/{b['id']}", json={"ocr_texte": "TEXTE HUMAIN"})
    monkeypatch.setattr(ocr, "_get_reader", lambda langs: _FakeReader("ocr auto"))
    body = client.post(f"/api/planches/{planche['id']}/ocr").json()
    assert body["ocr"] == 0 and body["ignores"] == 1
    reg = next(x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["id"] == b["id"])
    assert reg["ocr_texte"] == "TEXTE HUMAIN"  # correction préservée


def test_ocr_503(client, planche, monkeypatch):
    monkeypatch.setattr("main.ocr_available", lambda: False)
    assert client.post(f"/api/planches/{planche['id']}/ocr").status_code == 503


def test_ocr_404(client):
    assert client.post("/api/planches/999/ocr").status_code == 404


def test_ocr_erreur_500(client, planche, monkeypatch):
    def boom(*a, **k):
        raise ocr.OCRError("explosion")
    monkeypatch.setattr("main.ocr_planche", boom)
    r = client.post(f"/api/planches/{planche['id']}/ocr")
    assert r.status_code == 500 and "explosion" in r.json()["detail"]


# --------------------- intégration réelle (gated) ----------------------- #
def _balloon_png() -> bytes:
    img = Image.new("RGB", (1000, 700), (230, 230, 220))
    d = ImageDraw.Draw(img)
    d.ellipse([100, 100, 700, 420], fill="white", outline="black", width=4)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except OSError:
        font = ImageFont.load_default()
    d.text((180, 230), "BONJOUR ESTHER", fill="black", font=font)
    buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()


@requires_bulles
def test_detecter_bulles_reel(client, album):
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("b.png", _balloon_png(), "image/png")}).json()
    res = client.post(f"/api/planches/{p['id']}/detecter-bulles").json()
    assert res["nb_bulles"] >= 1


# --------------------- couverture des bords ----------------------------- #
def test_bulles_load_model_indisponible(monkeypatch):
    monkeypatch.setattr(bulles, "_model", None)
    monkeypatch.setattr(bulles, "bulles_available", lambda: False)
    with pytest.raises(bulles.BullesError):
        bulles._load_model()


def test_bulles_planche_inexistante(data_dir):
    conn = database.get_connection()
    try:
        with pytest.raises(ValueError):
            bulles.detect_bulles(conn, 999)
    finally:
        conn.close()


def test_ocr_reader_indisponible(monkeypatch):
    monkeypatch.setattr(ocr, "_reader", None)
    monkeypatch.setattr(ocr, "ocr_available", lambda: False)
    with pytest.raises(ocr.OCRError):
        ocr._get_reader(("fr",))


def test_ocr_planche_inexistante(data_dir):
    conn = database.get_connection()
    try:
        with pytest.raises(ValueError):
            ocr.ocr_planche(conn, 999)
    finally:
        conn.close()


def test_ocr_min_size_et_crop_invalide(client, planche, monkeypatch):
    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "bulle", "x": 0, "y": 0, "w": 4, "h": 4})   # trop petite
    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "bulle", "x": 10, "y": 10, "w": 50, "h": 50})  # crop OK

    class _Boom:
        def readtext(self, *a, **k):
            raise RuntimeError("boom")

    monkeypatch.setattr(ocr, "_get_reader", lambda langs: _Boom())
    body = client.post(f"/api/planches/{planche['id']}/ocr").json()
    assert body["echecs"] == 2 and body["ocr"] == 0


def test_ocr_et_bulles_sans_master_et_palette(data_dir, album, monkeypatch):
    """Couvre : _open_image branche web (sans master) + conversion (palette)
    + detect_bulles sur image sans master."""
    conn = database.get_connection()
    try:
        # (a) master en palette -> _open_image ouvre le master et convertit en RGB
        pal = data_dir / "pal.png"
        Image.new("P", (200, 200)).save(pal)
        p1 = ingest.ingest_image(conn, album["id"], pal)            # garde le master
        conn.execute("INSERT INTO regions(planche_id,type,x,y,w,h) "
                     "VALUES(?,'bulle',10,10,50,50)", (p1["id"],))
        # (b) sans master -> _open_image branche web
        rgb = data_dir / "rgb.png"
        Image.new("RGB", (200, 200), "white").save(rgb)
        p2 = ingest.ingest_image(conn, album["id"], rgb, keep_master=False)
        conn.execute("INSERT INTO regions(planche_id,type,x,y,w,h) "
                     "VALUES(?,'bulle',5,5,40,40)", (p2["id"],))
        conn.commit()

        monkeypatch.setattr(ocr, "_get_reader", lambda langs: _FakeReader("x"))
        assert ocr.ocr_planche(conn, p1["id"])["ocr"] == 1   # palette -> convert
        assert ocr.ocr_planche(conn, p2["id"])["ocr"] == 1   # web fallback

        monkeypatch.setattr(bulles, "_run", lambda path, conf: (200, 200, [(5, 5, 10, 10)]))
        assert bulles.detect_bulles(conn, p2["id"])["nb_bulles"] == 1  # web fallback
    finally:
        conn.close()


@requires_ocr
def test_ocr_reel(client, album):
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("b.png", _balloon_png(), "image/png")}).json()
    client.post(f"/api/planches/{p['id']}/regions",
                json={"type": "bulle", "x": 120, "y": 120, "w": 560, "h": 280})
    res = client.post(f"/api/planches/{p['id']}/ocr").json()
    assert res["ocr"] == 1
    reg = next(x for x in client.get(f"/api/planches/{p['id']}/regions").json()
               if x["type"] == "bulle")
    assert (reg["ocr_texte"] or "").strip()  # un texte non vide a été pré-rempli
