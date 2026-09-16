"""Régénération des dérivés depuis les masters (`tools/regenerer_derives.py`, IMG-1).

Ce que l'outil promet, et qui échouerait en silence :

1. **Le dérivé régénéré suit le master** — c'est la raison d'être de l'outil : rattraper
   les planches dont le dérivé a été écrêté avant le correctif.
2. **La base n'est pas touchée.** `largeur_px` / `hauteur_px` sont les dimensions du MASTER
   et portent les coordonnées de toutes les régions : les réécrire d'après le dérivé
   déplacerait chaque case sans qu'aucune erreur ne le signale.
3. **Un échec laisse l'ancien dérivé en place.** Un master illisible ou refusé ne doit pas
   remplacer une image imparfaite par un fichier tronqué, ni par rien.

`tools/` est hors couverture (`.coveragerc`) : sans ce fichier, une divergence y donnerait
un outil cassé et une suite verte.
"""
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT))

import database  # noqa: E402
import regenerer_derives as rd  # noqa: E402
from conftest import ADMIN  # noqa: E402

LARGEUR, HAUTEUR = 1024, 16


def _degrade_16_bits() -> bytes:
    im = Image.new("I;16", (LARGEUR, HAUTEUR))
    im.putdata([x * 65535 // (LARGEUR - 1) for x in range(LARGEUR)] * HAUTEUR)
    buf = io.BytesIO()
    im.save(buf, "TIFF")
    return buf.getvalue()


def _importer(client, album_id, octets, nom="planche.tif"):
    r = client.post(f"/api/albums/{album_id}/import",
                    files={"file": (nom, octets, "image/tiff")}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()


def _blanchir(chemin: Path) -> None:
    """Remet le dérivé dans l'état que produisait le défaut : une page blanche."""
    with Image.open(chemin) as im:
        taille = im.size
    Image.new("L", taille, 255).save(chemin, "JPEG")


def _milieu(chemin: Path) -> int:
    with Image.open(chemin) as im:
        return im.convert("L").getpixel((im.width // 2, im.height // 2))


@pytest.fixture
def conn(data_dir, monkeypatch):
    monkeypatch.setattr(rd, "DATA_DIR", data_dir)
    c = database.get_connection()
    yield c
    c.close()


def test_la_regeneration_rattrape_un_derive_ecrete_sans_toucher_la_base(client, album,
                                                                         data_dir, conn):
    pl = _importer(client, album["id"], _degrade_16_bits())
    derive = data_dir / pl["chemin_web"]
    _blanchir(derive)
    assert _milieu(derive) == 255                          # le décor est bien le défaut

    r = client.post(f"/api/planches/{pl['id']}/regions",
                    json={"type": "case", "x": 10, "y": 2, "w": 500, "h": 12}, headers=ADMIN)
    assert r.status_code == 201, r.text
    avant = conn.execute("SELECT * FROM planches WHERE id = ?", (pl["id"],)).fetchone()
    regions_avant = conn.execute("SELECT x, y, w, h FROM regions WHERE planche_id = ?",
                                 (pl["id"],)).fetchall()

    assert rd.main(["--planche", str(pl["id"])]) == 0

    assert abs(_milieu(derive) - 128) <= 8, "le dérivé régénéré ne suit pas le master"
    apres = conn.execute("SELECT * FROM planches WHERE id = ?", (pl["id"],)).fetchone()
    assert dict(apres) == dict(avant)
    assert conn.execute("SELECT x, y, w, h FROM regions WHERE planche_id = ?",
                        (pl["id"],)).fetchall() == regions_avant
    assert list(derive.parent.glob("*.regeneration")) == []


def test_le_dry_run_n_ecrit_rien(client, album, data_dir, conn):
    pl = _importer(client, album["id"], _degrade_16_bits())
    derive = data_dir / pl["chemin_web"]
    _blanchir(derive)
    assert rd.main(["--toutes", "--dry-run"]) == 0
    assert _milieu(derive) == 255


def test_un_master_refuse_laisse_l_ancien_derive_en_place(client, album, data_dir, conn,
                                                          capsys):
    pl = _importer(client, album["id"], _degrade_16_bits())
    derive = data_dir / pl["chemin_web"]
    _blanchir(derive)
    octets_avant = derive.read_bytes()
    # Le master est remplacé APRÈS coup par un mode que la conversion refuse : c'est le cas
    # d'un fichier antérieur au refus, qu'aucun import ne laisserait plus entrer.
    flottant = Image.new("F", (LARGEUR, HAUTEUR), 0.5)
    flottant.save(data_dir / pl["chemin_tiff"], "TIFF")

    assert rd.main(["--planche", str(pl["id"])]) == 1
    assert derive.read_bytes() == octets_avant
    assert list(derive.parent.glob("*.regeneration")) == []
    assert "« F »" in capsys.readouterr().out


def test_le_ciblage(client, album, data_dir, conn):
    autre = client.post("/api/albums", json={"titre": "Autre"}, headers=ADMIN).json()
    p1 = _importer(client, album["id"], _degrade_16_bits())
    p2 = _importer(client, autre["id"], _degrade_16_bits())
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, "PNG")
    p3 = _importer(client, autre["id"], buf.getvalue(), nom="planche.png")

    ids = lambda **k: [p["id"] for p in rd.planches_selectionnees(conn, **k)]  # noqa: E731
    assert ids(planche=p2["id"]) == [p2["id"]]
    assert ids(album=autre["id"]) == [p2["id"], p3["id"]]
    assert ids() == [p1["id"], p2["id"], p3["id"]]
    assert ids(modes=("I;16",)) == [p1["id"], p2["id"]]


def test_les_regions_de_moteur_d_un_gris_16_bits_sont_signalees_jamais_effacees(
        client, album, data_dir, conn, capsys):
    """Posées avant le correctif, elles l'ont été sur du blanc : l'outil le dit. Mais il ne
    les touche pas — une région de moteur peut porter une retouche humaine."""
    pl = _importer(client, album["id"], _degrade_16_bits())
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, "PNG")
    rgb = _importer(client, album["id"], buf.getvalue(), nom="planche.png")
    for p, source in ((pl, "kumiko"), (pl, "auto"), (pl, "manuel"), (rgb, "kumiko")):
        r = client.post(f"/api/planches/{p['id']}/regions",
                        json={"type": "case", "x": 1, "y": 1, "w": 5, "h": 5,
                              "source": source}, headers=ADMIN)
        assert r.status_code == 201, r.text

    assert rd.main(["--toutes"]) == 0
    # Deux régions de moteur sur la planche 16 bits ; la manuelle et la planche RVB, non.
    assert f"planche {pl['id']} : 2 région(s)" in capsys.readouterr().out
    bilan = rd.regenerer(conn, rd.planches_selectionnees(conn))
    assert bilan["a_resegmenter"] == [(pl["id"], 2)]
    assert conn.execute("SELECT COUNT(*) FROM regions").fetchone()[0] == 4


def test_une_planche_sans_master_est_sautee(client, album, data_dir, conn):
    pl = _importer(client, album["id"], _degrade_16_bits())
    (data_dir / pl["chemin_tiff"]).unlink()
    bilan = rd.regenerer(conn, rd.planches_selectionnees(conn, planche=pl["id"]))
    assert bilan["sans_master"] == [pl["id"]] and bilan["regeneres"] == []


def test_une_cible_est_obligatoire():
    """Sans cible, l'outil refuse plutôt que de régénérer tout le corpus par défaut."""
    with pytest.raises(SystemExit):
        rd.main([])
