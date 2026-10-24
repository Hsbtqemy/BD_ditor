"""Le PLANCHER du dérivé web (IMG-1, décision de Hugo du 2026-10-24).

Le constat : une planche de 975 × 1385 px s'affichait floue dans l'Atelier. Le dérivé
faisait toujours 25 % du scan (`WEB_SCALE`), soit 244 × 346 px — correct pour un scan de
4 000 px, illisible pour une petite image (le jeu des bacs à sable, un JPEG ordinaire).

La règle, écrite une fois (`ingest.taille_du_derive`) : 25 % du scan, mais jamais moins de
1 600 px de large (`WEB_LARGEUR_PLANCHER`), et jamais plus que l'image qu'on a — on
n'agrandit pas. Le rapport d'aspect est gardé.

Ce qui échouerait en silence, et que ce fichier tient :

1. **La règle elle-même**, aux quatre bords : une grande image à 25 %, une moyenne relevée
   à 1 600 px, une petite à sa taille, et le passage exact de l'une à l'autre.
2. **L'import réel** suit la règle — c'est lui qui écrit les dérivés.
3. **Le manifeste IIIF déclare la taille du FICHIER** : il calculait `WEB_SCALE` × le scan,
   faux dès qu'un dérivé est relevé par le plancher, et faux autrement pour un dérivé
   d'avant la règle.
4. **L'outil de rattrapage** (`tools/regenerer_derives.py`) ne refait par défaut que les
   dérivés trop petits, à blanc d'abord, dit le poids ajouté, n'ouvre la base qu'en lecture
   et ne laisse jamais un dérivé tronqué.
"""
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import database  # noqa: E402
import iiif_manifest  # noqa: E402
import regenerer_derives as rd  # noqa: E402
from config import WEB_LARGEUR_PLANCHER, WEB_SCALE  # noqa: E402
from conftest import ADMIN  # noqa: E402
from pipeline import ingest  # noqa: E402
from pipeline.ingest import taille_du_derive  # noqa: E402


# --------------------------------------------------------------------------- #
# 1. La règle, sans image
# --------------------------------------------------------------------------- #
def test_les_constantes_sont_celles_de_la_decision():
    assert (WEB_SCALE, WEB_LARGEUR_PLANCHER) == (0.25, 1600)


@pytest.mark.parametrize("scan, attendu", [
    # Grande : 25 % l'emporte sur le plancher.
    ((8000, 10000), (2000, 2500)),
    ((12000, 9000), (3000, 2250)),
    # Le passage : à 6 400 px, 25 % vaut exactement le plancher.
    ((6400, 9000), (1600, 2250)),
    ((6404, 9000), (1601, 2250)),
    # Moyenne : relevée au plancher (un vrai scan de la recette fait ~3 000 px).
    ((3000, 4260), (1600, 2272)),
    ((1601, 2000), (1600, 1999)),
    # Petite : à sa taille, jamais agrandie — le cas du constat.
    ((1600, 2000), (1600, 2000)),
    ((975, 1385), (975, 1385)),
    ((400, 500), (400, 500)),
    ((1, 1), (1, 1)),
])
def test_la_regle(scan, attendu):
    assert taille_du_derive(*scan) == attendu


@pytest.mark.parametrize("largeur", [1, 40, 975, 1599, 1600, 1601, 2000, 3001, 6399,
                                     6400, 6401, 7777, 20000])
def test_le_rapport_d_aspect_est_garde(largeur):
    """Un facteur pour les deux axes : la hauteur suit la largeur, à l'arrondi près."""
    hauteur = round(largeur * 1.42)
    w, h = taille_du_derive(largeur, hauteur)
    assert w <= largeur and h <= hauteur                       # jamais agrandi
    assert abs(h - hauteur * w / largeur) <= 1                 # même proportion
    assert w == min(largeur, max(round(largeur * WEB_SCALE), WEB_LARGEUR_PLANCHER))


def test_une_source_plus_petite_que_le_scan_borne_le_derive():
    """Depuis une copie de travail réduite (400 dpi → 75 %), le dérivé se mesure au SCAN
    sans dépasser l'image qu'on a : on n'agrandit pas la copie."""
    assert taille_du_derive(3000, 4000, 1500) == (1500, 2000)   # plancher borné par la copie
    assert taille_du_derive(3000, 4000, 2250) == (1600, 2133)   # la copie suffit
    assert taille_du_derive(8000, 10000, 6000) == (2000, 2500)  # 25 % du SCAN, pas de la copie
    assert taille_du_derive(800, 1000, 600) == (600, 750)
    assert taille_du_derive(800, 1000, 5000) == (800, 1000)     # le scan borne aussi


# --------------------------------------------------------------------------- #
# 2. L'import réel
# --------------------------------------------------------------------------- #
def _png(taille, couleur="white") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", taille, couleur).save(buf, "PNG")
    return buf.getvalue()


def _importer(client, album_id, octets, nom="planche.png"):
    r = client.post(f"/api/albums/{album_id}/import",
                    files={"file": (nom, octets, "image/png")}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()


def test_l_import_d_une_petite_image_garde_sa_taille(client, album, data_dir):
    """Le constat de Hugo, rejoué : 975 × 1385 donnait 244 × 346."""
    p = _importer(client, album["id"], _png((975, 1385)))
    assert (p["largeur_px"], p["hauteur_px"]) == (975, 1385)
    with Image.open(data_dir / p["chemin_web"]) as web:
        assert web.size == (975, 1385)
        assert web.format == "JPEG"


def test_l_import_d_une_image_moyenne_est_releve_au_plancher(client, album, data_dir):
    p = _importer(client, album["id"], _png((2000, 2800)))
    assert (p["largeur_px"], p["hauteur_px"]) == (2000, 2800)   # la géométrie reste le scan
    with Image.open(data_dir / p["chemin_web"]) as web:
        assert web.size == (1600, 2240)


def test_l_echelle_de_l_ecran_se_lit_sur_le_fichier():
    """L'Atelier calcule `webScale = largeur du dérivé / largeur_px` (`static/viewer.js`) :
    rien n'y suppose 25 %. Ce test garde que l'écran ne le réintroduise pas."""
    source = (REPO_ROOT / "static" / "viewer.js").read_text(encoding="utf-8")
    assert "state.webScale = state.webW / p.largeur_px;" in source
    assert "0.25" not in source


# --------------------------------------------------------------------------- #
# 3. Le manifeste IIIF
# --------------------------------------------------------------------------- #
def _planche_iiif(chemin_web, largeur, hauteur):
    return {"id": 7, "numero": 1, "numero_editorial": 1, "largeur_px": largeur,
            "hauteur_px": hauteur, "chemin_web": chemin_web, "regions": []}


def _corps(canvas):
    return canvas["items"][0]["items"][0]["body"]


def test_le_manifeste_declare_la_taille_du_fichier(client, album, data_dir):
    p = _importer(client, album["id"], _png((975, 1385)))
    canvas = iiif_manifest._canvas(_planche_iiif(p["chemin_web"], 975, 1385), album["id"],
                                   "http://exemple/iiif", verbatim=False)
    assert (canvas["width"], canvas["height"]) == (975, 1385)       # le Canvas : le scan
    assert (_corps(canvas)["width"], _corps(canvas)["height"]) == (975, 1385)


def test_un_derive_d_avant_la_regle_est_declare_a_sa_taille_reelle(data_dir):
    """Un dérivé écrit à 25 % avant le plancher, pas encore refait : le manifeste dit ce que
    le fichier EST, pas ce que la règle d'aujourd'hui en ferait."""
    chemin = "derivatives/album_9/planche_0001.jpg"
    (data_dir / chemin).parent.mkdir(parents=True)
    Image.new("RGB", (750, 1065), "white").save(data_dir / chemin, "JPEG")
    canvas = iiif_manifest._canvas(_planche_iiif(chemin, 3000, 4260), 9,
                                   "http://exemple/iiif", verbatim=False)
    assert (_corps(canvas)["width"], _corps(canvas)["height"]) == (750, 1065)


def test_un_derive_illisible_est_declare_selon_la_regle(data_dir):
    canvas = iiif_manifest._canvas(
        _planche_iiif("derivatives/album_9/absent.jpg", 3000, 4260), 9,
        "http://exemple/iiif", verbatim=False)
    assert (_corps(canvas)["width"], _corps(canvas)["height"]) == (1600, 2272)


# --------------------------------------------------------------------------- #
# 4. L'outil de rattrapage
# --------------------------------------------------------------------------- #
@pytest.fixture
def outil(data_dir, monkeypatch):
    """L'outil sur la base de test, et la preuve qu'il ne la prépare pas : `init_db` refait
    les vues, donc écrit — à côté de l'application qui tourne, il ne doit pas l'appeler."""
    monkeypatch.setattr(rd, "DATA_DIR", data_dir)

    def interdit():
        raise AssertionError("l'outil a appelé database.init_db()")
    monkeypatch.setattr(database, "init_db", interdit)
    return rd


def _au_quart(data_dir, p) -> bytes:
    """Remet le dérivé d'une planche dans l'état d'avant le plancher : 25 % du scan."""
    chemin = data_dir / p["chemin_web"]
    with Image.open(data_dir / p["chemin_tiff"]) as copie:
        copie.resize((round(p["largeur_px"] * 0.25), round(p["hauteur_px"] * 0.25))).save(
            chemin, "JPEG", quality=82)
    return chemin.read_bytes()


def test_l_outil_a_blanc_puis_applique(client, album, data_dir, outil, capsys):
    trop_petit = _importer(client, album["id"], _png((2000, 2800), "gray"))
    juste = _importer(client, album["id"], _png((975, 1385), "gray"), nom="petite.png")
    octets_trop_petit = _au_quart(data_dir, trop_petit)
    octets_juste = (data_dir / juste["chemin_web"]).read_bytes()

    # À blanc (le défaut) : il dit ce qu'il referait, combien et le poids — et n'écrit rien.
    assert outil.main(["--toutes"]) == 0
    sortie = capsys.readouterr().out
    assert "À BLANC" in sortie
    assert f"planche {trop_petit['id']} : · 500 × 700 → 1600 × 2240" in sortie
    assert "1 dérivé(s) à refaire sur 2 planche(s)" in sortie
    assert "1 déjà à la taille de la règle" in sortie
    assert "sur le disque" in sortie and "+" in sortie
    assert (data_dir / trop_petit["chemin_web"]).read_bytes() == octets_trop_petit
    assert (data_dir / juste["chemin_web"]).read_bytes() == octets_juste

    conn = database.get_connection()
    try:
        bilan = outil.regenerer(conn, outil.planches_selectionnees(conn), appliquer=False)
    finally:
        conn.close()
    assert bilan["regeneres"] == [trop_petit["id"]]
    assert bilan["a_la_bonne_taille"] == [juste["id"]]
    assert bilan["octets_avant"] == len(octets_trop_petit)
    assert bilan["octets_apres"] > bilan["octets_avant"]

    # Appliqué : seul le trop petit est refait, à la règle ; l'autre n'est pas touché.
    assert outil.main(["--toutes", "--appliquer"]) == 0
    assert "1 dérivé(s) refait(s) sur 2 planche(s)" in capsys.readouterr().out
    with Image.open(data_dir / trop_petit["chemin_web"]) as web:
        assert web.size == (1600, 2240)
    assert (data_dir / juste["chemin_web"]).read_bytes() == octets_juste
    assert list((data_dir / "derivatives").rglob("*.regeneration")) == []

    # Relancé, il ne trouve plus rien à faire.
    assert outil.main(["--toutes", "--appliquer"]) == 0
    assert "0 dérivé(s) refait(s) sur 2 planche(s)" in capsys.readouterr().out


def test_l_outil_ouvre_la_base_en_lecture_seule(client, album, data_dir, outil):
    _importer(client, album["id"], _png((975, 1385)))
    conn = outil._ouvrir_en_lecture()
    try:
        with pytest.raises(Exception, match="readonly"):
            conn.execute("UPDATE planches SET numero = numero")
    finally:
        conn.close()


def test_l_outil_ne_part_jamais_d_autre_chose_que_la_copie_de_travail(client, album,
                                                                     data_dir, outil):
    p = _importer(client, album["id"], _png((2000, 2800)))
    octets = _au_quart(data_dir, p)
    (data_dir / p["chemin_tiff"]).unlink()
    assert outil.main(["--toutes", "--appliquer"]) == 0
    assert (data_dir / p["chemin_web"]).read_bytes() == octets


def test_une_interruption_ne_laisse_aucun_derive_tronque(client, album, data_dir, outil,
                                                        monkeypatch):
    """Ctrl+C pendant l'écriture : l'ancien dérivé reste entier, et rien ne traîne à côté."""
    p = _importer(client, album["id"], _png((2000, 2800)))
    octets = _au_quart(data_dir, p)

    def coupe(source, dest, **_):
        Path(dest).write_bytes(b"\xff\xd8 tronque")
        raise KeyboardInterrupt
    monkeypatch.setattr(outil, "make_web_derivative", coupe)
    with pytest.raises(KeyboardInterrupt):
        outil.main(["--toutes", "--appliquer"])
    assert (data_dir / p["chemin_web"]).read_bytes() == octets
    assert list((data_dir / "derivatives").rglob("*.regeneration")) == []
