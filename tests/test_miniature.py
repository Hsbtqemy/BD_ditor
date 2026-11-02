"""La miniature d'une planche (UX-20, `docs/ux20-miniature-cadrage.md`).

Une seule règle, **la miniature suit son dérivé**, et ce qui la rompt ne se voit pas : aucune
planche ne désigne la miniature. Le piège est `remove_album_files`, où ce que `garder` ne
nomme pas part avec le dossier : détruire une copie effacerait la miniature de sa sœur.
"""
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import convertir_en_copies_de_travail as cct  # noqa: E402
import database  # noqa: E402
import faire_miniatures as fm  # noqa: E402
import regenerer_derives as rd  # noqa: E402
from config import MINIATURE_LARGEUR  # noqa: E402
from conftest import ADMIN, make_png  # noqa: E402
from pipeline import ingest  # noqa: E402
from test_copies_soeurs import LEA, SAM, _chemins, soeurs  # noqa: E402,F401
from test_fonds import _fichiers  # noqa: E402

AUTRE = {"Remote-User": "personne"}


def _miniature(data, chemin_web) -> Path:
    return data / ingest.chemin_de_miniature(chemin_web)


def _importer(client, album_id, octets):
    r = client.post(f"/api/albums/{album_id}/import",
                    files={"file": ("planche.png", octets, "image/png")}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------------------- #
# La règle
# --------------------------------------------------------------------------- #
def test_le_chemin_se_deduit_du_derive():
    assert ingest.chemin_de_miniature("derivatives/album_2/planche_0001.jpg") == \
        "derivatives/album_2/planche_0001.miniature.jpg"


def test_l_import_ecrit_la_miniature_a_la_bonne_largeur(client, album, data_dir):
    p = _importer(client, album["id"], make_png(1000, 1400))
    with Image.open(_miniature(data_dir, p["chemin_web"])) as im:
        assert im.format == "JPEG" and im.width == MINIATURE_LARGEUR
        assert im.height == round(1400 * MINIATURE_LARGEUR / 1000)


def test_une_petite_image_n_est_pas_agrandie(client, album, data_dir):
    p = _importer(client, album["id"], make_png(200, 300))
    with Image.open(_miniature(data_dir, p["chemin_web"])) as im:
        assert im.size == (200, 300)


def test_un_import_qui_echoue_ne_laisse_pas_de_miniature(client, album, data_dir,
                                                         monkeypatch):
    """L'échec vient APRÈS l'écriture de la miniature : c'est ce qui l'oblige à être retirée."""
    ecrire = ingest.ecrire_miniature

    def panne(*a, **k):
        ecrire(*a, **k)
        raise OSError(28, "plus de place")
    monkeypatch.setattr(ingest, "ecrire_miniature", panne)
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("planche.png", make_png(), "image/png")}, headers=ADMIN)
    assert r.status_code == 507, r.text
    assert list((data_dir / "derivatives" / f"album_{album['id']}").glob("*")) == []


# --------------------------------------------------------------------------- #
# Le service
# --------------------------------------------------------------------------- #
def test_la_route_sert_la_miniature_et_son_304(client, planche):
    r = client.get(f"/api/planches/{planche['id']}/miniature", headers=ADMIN)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"] == "no-cache"
    r2 = client.get(f"/api/planches/{planche['id']}/miniature",
                    headers={**ADMIN, "If-None-Match": r.headers["etag"]})
    assert r2.status_code == 304 and r2.content == b""


def test_hors_de_portee_le_304_n_est_pas_rendu(client, derriere_proxy, db_path, soeurs):
    """Un 404, ETag connu ou non : « inchangé » dirait que l'image existe."""
    url = f"/api/planches/{soeurs['pa']}/miniature"
    etag = client.get(url, headers=ADMIN).headers["etag"]
    assert client.get(url, headers=LEA).status_code == 200
    assert client.get(url, headers=SAM).status_code == 404
    assert client.get(url, headers={**AUTRE, "If-None-Match": etag}).status_code == 404


def test_le_fichier_n_est_pas_servi_par_les_derives(client, planche):
    """L'allowlist de `/derivatives` ne connaît que `planches.chemin_web`."""
    chemin = ingest.chemin_de_miniature(planche["chemin_web"])
    assert client.get("/" + chemin, headers=ADMIN).status_code == 404


def test_un_fichier_absent_repond_404(client, planche, data_dir):
    _miniature(data_dir, planche["chemin_web"]).unlink()
    assert client.get(f"/api/planches/{planche['id']}/miniature",
                      headers=ADMIN).status_code == 404


def test_aucun_chemin_ne_sort_de_la_route(client, planche):
    r = client.get(f"/api/planches/{planche['id']}/miniature", headers=ADMIN)
    assert "derivatives" not in " ".join(r.headers.values())


# --------------------------------------------------------------------------- #
# Les sœurs et l'effacement
# --------------------------------------------------------------------------- #
def test_deux_soeurs_partagent_la_miniature(client, soeurs):
    a = client.get(f"/api/planches/{soeurs['pa']}/miniature", headers=LEA)
    b = client.get(f"/api/planches/{soeurs['pb']}/miniature", headers=SAM)
    assert a.status_code == b.status_code == 200 and a.content == b.content


def test_detruire_une_copie_garde_la_miniature_de_sa_soeur(client, db_path, soeurs):
    """LE test du piège : un fichier qu'aucune planche ne désigne et que la sœur emploie."""
    a, b, data = soeurs["a"], soeurs["b"], soeurs["data"]
    web = _chemins(db_path, b)[0][1]
    assert client.delete(f"/api/albums/{a}", headers=ADMIN).status_code == 204
    assert _miniature(data, web).exists(), "la miniature de la sœur a été effacée"
    assert client.get(f"/api/planches/{soeurs['pb']}/miniature",
                      headers=SAM).status_code == 200

    assert client.delete(f"/api/albums/{b}", headers=ADMIN).status_code == 204
    assert not _miniature(data, web).exists()
    assert _fichiers(data, a) == [] and _fichiers(data, b) == []


def test_detruire_la_copie_tiree_d_une_autre_efface_la_miniature_ailleurs(client, db_path,
                                                                         soeurs):
    """B est détruite la dernière : ses fichiers vivent dans le dossier de A. C'est la voie
    « ailleurs » de `_effacer_les_images_d_une_copie`, où un dérivé arrive en première
    position de `remove_planche_files`."""
    a, b, data = soeurs["a"], soeurs["b"], soeurs["data"]
    web = _chemins(db_path, b)[0][1]
    assert client.delete(f"/api/albums/{a}", headers=ADMIN).status_code == 204
    assert client.delete(f"/api/albums/{b}", headers=ADMIN).status_code == 204
    assert not (data / web).exists() and not _miniature(data, web).exists()
    assert not (data / web).parent.exists()


def test_supprimer_une_planche_garde_la_miniature_de_la_soeur(client, db_path, soeurs):
    a, data = soeurs["a"], soeurs["data"]
    web = _chemins(db_path, a)[0][1]
    assert client.delete(f"/api/planches/{soeurs['pa']}", headers=ADMIN).status_code == 204
    assert (data / web).exists() and _miniature(data, web).exists()


def test_supprimer_la_derniere_planche_efface_la_miniature(client, album, data_dir):
    p = _importer(client, album["id"], make_png())
    assert client.delete(f"/api/planches/{p['id']}", headers=ADMIN).status_code == 204
    assert not _miniature(data_dir, p["chemin_web"]).exists()


# --------------------------------------------------------------------------- #
# Les outils
# --------------------------------------------------------------------------- #
@pytest.fixture
def conn(data_dir, monkeypatch):
    monkeypatch.setattr(rd, "DATA_DIR", data_dir)
    monkeypatch.setattr(cct, "DATA_DIR", data_dir)
    c = database.get_connection()
    yield c
    c.close()


def test_l_outil_est_a_blanc_par_defaut(client, planche, data_dir, conn):
    mini = _miniature(data_dir, planche["chemin_web"])
    mini.unlink()
    chemins = fm.derives_selectionnes(conn)
    bilan = fm.faire(chemins, appliquer=False)
    assert bilan["faites"] == chemins and bilan["octets"] > 0
    assert not mini.exists()


def test_l_outil_fait_ce_qui_manque_et_laisse_le_reste(client, planche, data_dir, conn):
    mini = _miniature(data_dir, planche["chemin_web"])
    mini.unlink()
    chemins = fm.derives_selectionnes(conn)
    assert fm.faire(chemins, appliquer=True)["faites"] == chemins
    with Image.open(mini) as im:
        assert im.width == min(MINIATURE_LARGEUR, 400)
    bilan = fm.faire(chemins, appliquer=True)
    assert bilan["faites"] == [] and bilan["existantes"] == chemins
    assert fm.faire(chemins, appliquer=True, meme_existantes=True)["faites"] == chemins


def test_l_outil_passe_une_fois_par_derive(client, db_path, soeurs, conn):
    assert fm.derives_selectionnes(conn) == [_chemins(db_path, soeurs["a"])[0][1]]


def test_un_derive_absent_est_saute_et_compte(client, planche, data_dir, conn):
    (data_dir / planche["chemin_web"]).unlink()
    bilan = fm.faire([planche["chemin_web"]], appliquer=True)
    assert bilan["sans_derive"] == [planche["chemin_web"]] and bilan["faites"] == []


def test_un_chemin_retouche_ne_fait_rien_ecrire(client, data_dir, conn):
    (data_dir / "ailleurs.jpg").write_bytes(make_png())
    assert fm.faire(["ailleurs.jpg"], appliquer=True)["sans_derive"] == ["ailleurs.jpg"]
    assert not (data_dir / "ailleurs.miniature.jpg").exists()


def test_regenerer_un_derive_refait_sa_miniature(client, album, data_dir, conn):
    """Sinon un dérivé corrigé garderait une miniature blanche."""
    p = _importer(client, album["id"], make_png(800, 1000, "black"))
    mini = _miniature(data_dir, p["chemin_web"])
    Image.new("L", (10, 10), 255).save(mini, "JPEG")
    planches = rd.planches_selectionnees(conn, planche=p["id"])
    rd.regenerer(conn, planches, appliquer=True, meme_a_la_bonne_taille=True)
    with Image.open(mini) as im:
        assert im.width == MINIATURE_LARGEUR and im.convert("L").getpixel((5, 5)) < 40


def test_regenerer_a_blanc_ne_touche_pas_la_miniature(client, album, data_dir, conn):
    p = _importer(client, album["id"], make_png(800, 1000))
    mini = _miniature(data_dir, p["chemin_web"])
    avant = mini.read_bytes()
    planches = rd.planches_selectionnees(conn, planche=p["id"])
    rd.regenerer(conn, planches, appliquer=False, meme_a_la_bonne_taille=True)
    assert mini.read_bytes() == avant


def test_la_miniature_d_un_derive_designe_n_est_pas_orpheline(client, planche, conn):
    assert cct.orphelins(conn) == []


def test_la_miniature_d_un_derive_disparu_est_orpheline(client, planche, data_dir, conn):
    reste = data_dir / "derivatives" / f"album_{planche['album_id']}" / \
        "planche_0099.miniature.jpg"
    reste.write_bytes(b"x")
    assert [r for r, _ in cct.orphelins(conn)] == [reste.relative_to(data_dir).as_posix()]
