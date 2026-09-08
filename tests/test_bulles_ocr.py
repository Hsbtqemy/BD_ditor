"""Passe 2 (détection bulles) et passe 3 (OCR) — moteurs ML optionnels.

Les chemins « logique » sont testés en mockant l'appel moteur (rapide,
déterministe) ; un test d'intégration réel (gated) valide le bout-en-bout.
"""
import io
import time

import pytest
from PIL import Image, ImageDraw, ImageFont

import database
import pipeline.bulles as bulles
import pipeline.ingest as ingest
import pipeline.ocr as ocr
from pipeline import interruption
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


@requires_bulles
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


@requires_bulles
def test_detecter_bulles_hors_case(client, planche, monkeypatch):
    monkeypatch.setattr(bulles, "_run",
                        lambda path, conf: (400, 500, [(5, 5, 10, 10)]))
    body = client.post(f"/api/planches/{planche['id']}/detecter-bulles").json()
    assert body["nb_bulles"] == 1 and body["sans_case"] == 1
    bulle = next(x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["type"] == "bulle")
    assert bulle["parent_id"] is None


@requires_bulles
def test_detecter_bulles_replace(client, planche, monkeypatch):
    monkeypatch.setattr(bulles, "_run", lambda path, conf: (400, 500, [(5, 5, 10, 10)]))
    client.post(f"/api/planches/{planche['id']}/detecter-bulles")
    client.post(f"/api/planches/{planche['id']}/detecter-bulles")  # relance
    bulles_n = [x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["type"] == "bulle"]
    assert len(bulles_n) == 1  # remplacées, pas accumulées


@requires_bulles
def test_redetecter_bulles_preserve_ocr(client, planche, monkeypatch):
    """Re-détecter préserve les bulles océrisées et ignore une détection qui les recouvre."""
    _add_case(client, planche, 0, 0, 400, 500)
    monkeypatch.setattr(bulles, "_run", lambda path, conf: (400, 500, [(50, 60, 80, 40)]))
    client.post(f"/api/planches/{planche['id']}/detecter-bulles")
    bulle = next(r for r in client.get(
        f"/api/planches/{planche['id']}/regions").json() if r["type"] == "bulle")
    client.put(f"/api/regions/{bulle['id']}", json={"ocr_texte": "SALUT"})
    # re-détection : une box recouvrant la bulle océrisée + une nouvelle ailleurs
    monkeypatch.setattr(bulles, "_run",
                        lambda path, conf: (400, 500, [(52, 62, 80, 40), (200, 200, 60, 30)]))
    body = client.post(f"/api/planches/{planche['id']}/detecter-bulles").json()
    regions = client.get(f"/api/planches/{planche['id']}/regions").json()
    surv = next((r for r in regions if r["id"] == bulle["id"]), None)
    assert surv is not None and surv["ocr_texte"] == "SALUT"            # OCR préservé
    assert len([r for r in regions if r["type"] == "bulle"]) == 2       # océrisée + nouvelle
    assert body["preservees"] == 1 and body["ignores"] == 1 and body["nb_bulles"] == 1


@requires_bulles
def test_redetecter_bulles_preserve_annotation(client, planche, monkeypatch):
    """Une bulle annotée SANS OCR est préservée à la re-détection (branche
    'NOT EXISTS annotations' du tri)."""
    _add_case(client, planche, 0, 0, 400, 500)
    monkeypatch.setattr(bulles, "_run", lambda path, conf: (400, 500, [(50, 60, 80, 40)]))
    client.post(f"/api/planches/{planche['id']}/detecter-bulles")
    b = next(r for r in client.get(
        f"/api/planches/{planche['id']}/regions").json() if r["type"] == "bulle")
    client.put(f"/api/regions/{b['id']}/annotation", json={"note": "", "tags": ["cri"]})
    # re-détection à un autre endroit (ne recouvre pas) → la bulle annotée survit
    monkeypatch.setattr(bulles, "_run", lambda path, conf: (400, 500, [(200, 200, 60, 30)]))
    body = client.post(f"/api/planches/{planche['id']}/detecter-bulles").json()
    regions = client.get(f"/api/planches/{planche['id']}/regions").json()
    assert any(r["id"] == b["id"] for r in regions)   # bulle annotée préservée
    assert body["preservees"] == 1


def test_iou_unitaire():
    """IoU : identiques = 1, disjointes = 0, petite incluse dans grande = faible."""
    assert bulles._iou({"x": 0, "y": 0, "w": 10, "h": 10}, {"x": 0, "y": 0, "w": 10, "h": 10}) == 1.0
    assert bulles._iou({"x": 0, "y": 0, "w": 10, "h": 10}, {"x": 99, "y": 99, "w": 10, "h": 10}) == 0.0
    petit = bulles._iou({"x": 90, "y": 90, "w": 20, "h": 20}, {"x": 0, "y": 0, "w": 200, "h": 200})
    assert petit < 0.05               # petite bulle DANS une grande → IoU faible (≠ doublon)


@requires_bulles
def test_redetecter_bulles_dedup_iou(client, planche, monkeypatch):
    """S4 : dédup par IoU. Une petite bulle DISTINCTE dont le centre tombe dans une
    grosse bulle préservée n'est PAS un doublon (IoU faible) → ajoutée ; un quasi-doublon
    (IoU élevé) reste ignoré. (Le test « centre ∈ ancien » l'aurait à tort écartée.)"""
    _add_case(client, planche, 0, 0, 400, 500)
    monkeypatch.setattr(bulles, "_run", lambda path, conf: (400, 500, [(0, 0, 200, 200)]))
    client.post(f"/api/planches/{planche['id']}/detecter-bulles")
    grosse = next(r for r in client.get(
        f"/api/planches/{planche['id']}/regions").json() if r["type"] == "bulle")
    client.put(f"/api/regions/{grosse['id']}", json={"ocr_texte": "GROSSE"})   # préservée
    monkeypatch.setattr(bulles, "_run",
                        lambda path, conf: (400, 500, [(90, 90, 20, 20), (3, 3, 200, 200)]))
    body = client.post(f"/api/planches/{planche['id']}/detecter-bulles").json()
    apres = [r for r in client.get(
        f"/api/planches/{planche['id']}/regions").json() if r["type"] == "bulle"]
    assert body["preservees"] == 1 and body["ignores"] == 1 and body["nb_bulles"] == 1
    assert len(apres) == 2            # grosse préservée + petite distincte ajoutée


def test_detecter_bulles_503(client, planche, monkeypatch):
    monkeypatch.setattr("main.bulles_available", lambda: False)
    r = client.post(f"/api/planches/{planche['id']}/detecter-bulles")
    assert r.status_code == 503


def test_detecter_bulles_404(client):
    assert client.post("/api/planches/999/detecter-bulles").status_code == 404


@requires_bulles
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


@requires_ocr
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


@requires_ocr
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


@requires_ocr
def test_ocr_erreur_500(client, planche, monkeypatch):
    def boom(*a, **k):
        raise ocr.OCRError("explosion")
    monkeypatch.setattr("main.ocr_planche", boom)
    r = client.post(f"/api/planches/{planche['id']}/ocr")
    assert r.status_code == 500 and "explosion" in r.json()["detail"]


# --------------------- intégration réelle (gated) ----------------------- #
def _balloon_png() -> bytes:
    # Grand : la détection tourne sur le dérivé web (25 %), il faut donc une
    # taille raisonnable côté web (ici 500x350).
    img = Image.new("RGB", (2000, 1400), (230, 230, 220))
    d = ImageDraw.Draw(img)
    d.ellipse([200, 200, 1400, 840], fill="white", outline="black", width=6)
    try:
        font = ImageFont.truetype("arial.ttf", 90)
    except OSError:
        font = ImageFont.load_default()
    d.text((360, 460), "BONJOUR ESTHER", fill="black", font=font)
    buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()


@requires_bulles
def test_detecter_bulles_reel(client, album):
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("b.png", _balloon_png(), "image/png")}).json()
    res = client.post(f"/api/planches/{p['id']}/detecter-bulles").json()
    assert res["nb_bulles"] >= 1


# ------------------- crop net (mode Transcription) ---------------------- #
def test_crop_route_png(client, region):
    r = client.get(f"/api/regions/{region['id']}/crop")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_crop_route_404(client):
    assert client.get("/api/regions/999/crop").status_code == 404


def test_crop_route_taille(client, region):
    """`taille` redimensionne la vignette ; borné en bas à 40."""
    import io
    from PIL import Image
    r = client.get(f"/api/regions/{region['id']}/crop", params={"taille": 40})
    assert r.status_code == 200
    assert Image.open(io.BytesIO(r.content)).width == 40
    r2 = client.get(f"/api/regions/{region['id']}/crop", params={"taille": 5})
    assert Image.open(io.BytesIO(r2.content)).width == 40   # clamp bas


def test_crop_cache_plusieurs_planches(client, album, png_bytes):
    """Couvre cache: miss (ouvre) -> hit (même planche) -> miss (ferme+ouvre autre)."""
    p1 = client.post(f"/api/albums/{album['id']}/import",
                     files={"file": ("a.png", png_bytes, "image/png")}).json()
    p2 = client.post(f"/api/albums/{album['id']}/import",
                     files={"file": ("b.png", png_bytes, "image/png")}).json()
    r1 = client.post(f"/api/planches/{p1['id']}/regions",
                     json={"type": "bulle", "x": 5, "y": 5, "w": 50, "h": 40}).json()
    r1b = client.post(f"/api/planches/{p1['id']}/regions",
                      json={"type": "bulle", "x": 60, "y": 5, "w": 50, "h": 40}).json()
    r2 = client.post(f"/api/planches/{p2['id']}/regions",
                     json={"type": "bulle", "x": 5, "y": 5, "w": 50, "h": 40}).json()
    assert client.get(f"/api/regions/{r1['id']}/crop").status_code == 200    # miss
    assert client.get(f"/api/regions/{r1b['id']}/crop").status_code == 200   # hit
    assert client.get(f"/api/regions/{r2['id']}/crop").status_code == 200    # miss + close


def test_crop_close_robuste(client, region):
    """Si le close() de l'image cachée lève, le crop suivant marche quand même."""
    class _Bad:
        def close(self):
            raise RuntimeError("boom")
    ocr._crop_cache.update(planche_id=-999, img=_Bad(), scale=1.0)
    assert client.get(f"/api/regions/{region['id']}/crop").status_code == 200


def test_crop_reduit_a_max_dim(client, album):
    buf = io.BytesIO()
    Image.new("RGB", (2000, 800), "white").save(buf, "PNG")
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("w.png", buf.getvalue(), "image/png")}).json()
    r = client.post(f"/api/planches/{p['id']}/regions",
                    json={"type": "bulle", "x": 10, "y": 10, "w": 1800, "h": 200}).json()
    resp = client.get(f"/api/regions/{r['id']}/crop")
    assert resp.status_code == 200
    assert Image.open(io.BytesIO(resp.content)).width == 1600  # réduit


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


@requires_bulles
def test_bulles_erreur_moteur_500(client, planche, monkeypatch):
    """Une erreur d'inférence/lecture image -> BullesError -> 500 propre."""
    def boom(path, conf):
        raise RuntimeError("cv2 boom")
    monkeypatch.setattr(bulles, "_run", boom)
    r = client.post(f"/api/planches/{planche['id']}/detecter-bulles")
    assert r.status_code == 500


@requires_bulles
def test_bulles_reraise_bulleserror(client, planche, monkeypatch):
    """Un BullesError de _run remonte tel quel (pas de double-emballage)."""
    def boom(path, conf):
        raise bulles.BullesError("déjà propre")
    monkeypatch.setattr(bulles, "_run", boom)
    r = client.post(f"/api/planches/{planche['id']}/detecter-bulles")
    assert r.status_code == 500 and "déjà propre" in r.json()["detail"]


@requires_ocr
def test_ocr_reader_init_erreur(monkeypatch):
    """Échec de chargement du modèle EasyOCR -> OCRError."""
    monkeypatch.setattr(ocr, "_reader", None)
    monkeypatch.setattr(ocr, "_reader_langs", None)

    def boom(*a, **k):
        raise RuntimeError("dl boom")

    monkeypatch.setattr("easyocr.Reader", boom)
    with pytest.raises(ocr.OCRError):
        ocr._get_reader(("fr",))


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


@requires_ocr
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

        # détection à un autre endroit que la bulle préexistante (sinon ignorée)
        monkeypatch.setattr(bulles, "_run", lambda path, conf: (200, 200, [(100, 100, 10, 10)]))
        assert bulles.detect_bulles(conn, p2["id"])["nb_bulles"] == 1  # web fallback
    finally:
        conn.close()


@requires_ocr
def test_ocr_reel(client, album):
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("b.png", _balloon_png(), "image/png")}).json()
    client.post(f"/api/planches/{p['id']}/regions",
                json={"type": "bulle", "x": 240, "y": 240, "w": 1120, "h": 560})
    res = client.post(f"/api/planches/{p['id']}/ocr").json()
    assert res["ocr"] == 1
    reg = next(x for x in client.get(f"/api/planches/{p['id']}/regions").json()
               if x["type"] == "bulle")
    assert (reg["ocr_texte"] or "").strip()  # un texte non vide a été pré-rempli


def test_le_crop_ne_serialise_plus_le_resize_ni_l_encodage(client, album, monkeypatch):
    """CONC-1 — le verrou du cache enveloppait TOUT le corps de `region_crop_png`.

    Ouverture du master, crop, resize et encodage PNG étaient sérialisés ensemble, alors
    que les deux derniers travaillent sur un objet neuf que plus rien ne partage. Mesuré le
    2026-09-08 : resize 19-31 % du temps de l'appel, PNG 59-75 % — 85 à 94 % qui n'avaient
    aucune raison d'attendre.

    **Les DEUX assertions sont nécessaires, et la seconde est celle qu'on oublie.** Un test
    qui vérifie seulement que le verrou est LÂCHÉ pendant l'encodage passerait aussi si l'on
    avait purement supprimé le verrou — ce qui rouvrirait la course que CONC-1 décrit. La
    première exige donc qu'il soit TENU pendant `_open_image`, qui remplace l'image
    partagée.
    """
    vu = {}

    ouvrir_reel = ocr._open_image

    def ouvrir_espion(planche):
        vu["verrou_pendant_ouverture"] = ocr._crop_lock.locked()
        return ouvrir_reel(planche)

    save_reel = Image.Image.save

    def save_espion(self, fp, *a, **kw):
        vu.setdefault("verrou_pendant_png", ocr._crop_lock.locked())
        return save_reel(self, fp, *a, **kw)

    monkeypatch.setattr(ocr, "_open_image", ouvrir_espion)
    monkeypatch.setattr(Image.Image, "save", save_espion)

    buf = io.BytesIO()
    Image.new("RGB", (2000, 800), "white").save(buf, "PNG")
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("w.png", buf.getvalue(), "image/png")}).json()
    r = client.post(f"/api/planches/{p['id']}/regions",
                    json={"type": "bulle", "x": 10, "y": 10, "w": 1800, "h": 200}).json()

    ocr._crop_cache.update(planche_id=None, img=None, scale=1.0)   # force le MISS
    vu.clear()
    assert client.get(f"/api/regions/{r['id']}/crop").status_code == 200

    assert vu["verrou_pendant_ouverture"] is True, (
        "l'ouverture du master REMPLACE l'image partagée : elle doit rester sous le verrou")
    assert vu["verrou_pendant_png"] is False, (
        "l'encodage PNG travaille sur un objet local au thread : il n'a rien à sérialiser")


def test_le_master_resident_est_ferme_apres_son_echeance(client, album, monkeypatch):
    """CONC-1 — le master n'était fermé qu'à l'ouverture d'une AUTRE planche.

    Une session de transcription terminée laissait donc 53 Mo résidents pour toujours
    (mesuré le 2026-09-08 sur un master réel). Le porteur retenu est une minuterie
    d'INACTIVITÉ et non un fil de fond : elle n'existe que tant que le cache tient
    quelque chose.

    Ce test attend une VRAIE minuterie plutôt que d'appeler son corps à la main : c'est
    précisément l'armement qui est en cause, et un test qui invoquerait `_echoir_master`
    directement passerait alors même que rien ne l'appellerait jamais — le défaut d'un
    contrôle paresseux, celui que ce choix écarte.
    """
    monkeypatch.setattr(ocr, "TTL_MASTER_CROP", 0.05)

    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buf, "PNG")
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("m.png", buf.getvalue(), "image/png")}).json()
    r = client.post(f"/api/planches/{p['id']}/regions",
                    json={"type": "bulle", "x": 10, "y": 10, "w": 200, "h": 100}).json()

    assert client.get(f"/api/regions/{r['id']}/crop").status_code == 200
    assert ocr._crop_cache["img"] is not None, "le crop doit avoir mis le master en cache"

    fin = time.monotonic() + 3.0
    while ocr._crop_cache["img"] is not None and time.monotonic() < fin:
        time.sleep(0.02)
    assert ocr._crop_cache["img"] is None, (
        "l'échéance passée, le master doit être fermé sans que personne n'appelle")
    assert ocr._crop_cache["planche_id"] is None


def test_une_minuterie_deja_partie_ne_ferme_pas_un_master_reutilise(client, album):
    """CONC-1 — `Timer.cancel()` ne rattrape pas une minuterie DÉJÀ partie.

    Elle peut attendre `_crop_lock` pendant qu'un crop tout neuf s'en sert : le
    réarmement n'annule alors plus rien, et elle fermerait en sortant du verrou une image
    qui vient de servir. Le contrôle d'âge dans `_echoir_master` est ce qui la neutralise
    — d'où ce test, qui joue exactement cette séquence en appelant le corps de la
    minuterie APRÈS un accès.
    """
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buf, "PNG")
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("m2.png", buf.getvalue(), "image/png")}).json()
    r = client.post(f"/api/planches/{p['id']}/regions",
                    json={"type": "bulle", "x": 10, "y": 10, "w": 200, "h": 100}).json()

    assert client.get(f"/api/regions/{r['id']}/crop").status_code == 200
    garde = ocr._crop_cache["img"]
    assert garde is not None

    # On efface la minuterie AVANT d'appeler son corps, et ce détail porte la seconde
    # assertion : c'est l'état du réveil ANTICIPÉ, où le fil qui s'exécute est le seul
    # armé et va mourir en sortant. Sans cet effacement, la minuterie du crop resterait
    # vivante et « un fil est armé » serait vrai sans que personne l'ait réarmé — une
    # assertion increvable, mesurée telle quelle : la mutation qui supprime le
    # réarmement passait au vert.
    ocr._minuterie = None
    ocr._echoir_master()          # la minuterie partie AVANT ce dernier accès

    assert ocr._crop_cache["img"] is garde, (
        "une minuterie doublée par un accès plus récent ne doit rien fermer : sinon "
        "l'échéance ne mesure plus l'inactivité, mais l'ancienneté de la minuterie")
    assert ocr._minuterie is not None and ocr._minuterie.is_alive(), (
        "et elle doit se RÉARMER sur le temps qui reste : renoncer laisserait le master "
        "résident pour de bon, plus rien ne pouvant le fermer qu'un changement de planche")


def test_a_ttl_nul_aucune_minuterie_n_est_armee(client, album, monkeypatch):
    """CONC-1 — la porte de sortie, pour qui préfère la RAM au fil.

    `BD_TTL_MASTER_CROP=0` doit rendre au cache son comportement d'avant, fermé au seul
    changement de planche — et surtout ne créer AUCUN fil. Un réglage qui armerait quand
    même une minuterie sans échéance utile serait le pire des deux.
    """
    monkeypatch.setattr(ocr, "TTL_MASTER_CROP", 0)

    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buf, "PNG")
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("m3.png", buf.getvalue(), "image/png")}).json()
    r = client.post(f"/api/planches/{p['id']}/regions",
                    json={"type": "bulle", "x": 10, "y": 10, "w": 200, "h": 100}).json()

    assert client.get(f"/api/regions/{r['id']}/crop").status_code == 200
    assert ocr._crop_cache["img"] is not None, "le cache doit fonctionner comme avant"
    assert ocr._minuterie is None, "à TTL nul, aucun fil ne doit être créé"


def test_l_ocr_est_interruptible_entre_deux_regions(client, album, monkeypatch):
    """CONC-1 — une passe OCR entière ignorait l'annulation, du début à la fin.

    Une planche chargée porte plusieurs dizaines de régions, chacune un appel à EasyOCR :
    la passe pouvait durer des minutes sans jamais regarder si on lui avait demandé de
    s'arrêter. Le grain est la RÉGION, et c'est le seul disponible — `readtext` est un
    appel opaque qu'on ne peut pas découper.

    Le lecteur est remplacé par un objet nu : le moteur n'a rien à voir avec ce qui est
    éprouvé, et le test doit tourner là où EasyOCR n'est pas installé — sans quoi il ne
    vaudrait que sur les machines qui l'ont, c'est-à-dire nulle part en intégration.
    """
    monkeypatch.setattr(ocr, "_get_reader", lambda langs: object())

    buf = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buf, "PNG")
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("i.png", buf.getvalue(), "image/png")}).json()
    for y in (10, 120):
        client.post(f"/api/planches/{p['id']}/regions",
                    json={"type": "bulle", "x": 10, "y": y, "w": 200, "h": 80})

    interruption.poser(lambda: True)
    conn = database.get_connection()
    try:
        with pytest.raises(interruption.PasseInterrompue):
            ocr.ocr_planche(conn, p["id"])
    finally:
        conn.close()
