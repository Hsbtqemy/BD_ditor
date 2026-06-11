"""Pipeline : ingestion (dérivé web, métadonnées, nommage) et segmentation."""
import io

from PIL import Image

from conftest import KUMIKO_SAMPLE, requires_kumiko


def test_derive_web_est_au_quart(client, data_dir, album):
    # master 800x1000 -> web 200x250
    buf = io.BytesIO()
    Image.new("RGB", (800, 1000), "white").save(buf, "TIFF", dpi=(300, 300))
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("m.tif", buf.getvalue(), "image/tiff")})
    p = r.json()
    assert (p["largeur_px"], p["hauteur_px"]) == (800, 1000)  # dims master
    web = Image.open(data_dir / p["chemin_web"])
    assert web.size == (200, 250)  # 25 %


def test_metadonnees_master(client, album):
    buf = io.BytesIO()
    Image.new("RGB", (600, 400), "white").save(buf, "TIFF", dpi=(400, 400))
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("m.tif", buf.getvalue(), "image/tiff")}).json()
    assert p["dpi"] == [400, 400] and p["mode"] == "RGB"


def test_noms_master_et_web_alignes(client, album, png_bytes):
    """Sans numéro fourni, master et dérivé portent le même numéro (régression)."""
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("nom_original.png", png_bytes, "image/png")}).json()
    assert p["chemin_tiff"].endswith("planche_0001.png")
    assert p["chemin_web"].endswith("planche_0001.jpg")


def test_numero_auto_increment(client, album, png_bytes):
    ids = []
    for _ in range(3):
        r = client.post(f"/api/albums/{album['id']}/import",
                        files={"file": ("p.png", png_bytes, "image/png")})
        ids.append(r.json()["numero"])
    assert ids == [1, 2, 3]


# ---------------- Segmentation (nécessite Kumiko) ---------------- #
@requires_kumiko
def test_segmentation_detecte_des_cases(client, album):
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("s.png", KUMIKO_SAMPLE.read_bytes(), "image/png")}).json()
    res = client.post(f"/api/planches/{p['id']}/segmenter").json()
    assert res["nb_cases"] >= 1
    regions = client.get(f"/api/planches/{p['id']}/regions").json()
    assert len(regions) == res["nb_cases"]
    mw, mh = p["largeur_px"], p["hauteur_px"]
    for r in regions:
        assert r["type"] == "case" and r["source"] == "kumiko"
        assert 0 <= r["x"] and 0 <= r["y"]
        assert r["x"] + r["w"] <= mw + 2 and r["y"] + r["h"] <= mh + 2


@requires_kumiko
def test_segmentation_passe_statut_a_segmentee(client, album):
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("s.png", KUMIKO_SAMPLE.read_bytes(), "image/png")}).json()
    client.post(f"/api/planches/{p['id']}/segmenter")
    planches = client.get(f"/api/albums/{album['id']}/planches").json()
    assert planches[0]["statut"] == "segmentee"
