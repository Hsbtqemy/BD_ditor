"""Le rattrapage des masters déjà gardés (`tools/convertir_en_copies_de_travail.py`, IMG-1).

Ce que l'outil promet, et qui échouerait en silence :

1. **À blanc, rien ne bouge** — ni la base, ni un octet du disque des images.
2. **La région reste au même endroit** : `largeur_px` / `hauteur_px` (les coordonnées) et
   le matériel ne changent pas, et le crop d'une région depuis la copie est celui qu'elle
   donnait depuis le master, à la réduction près.
3. **Un fichier partagé ne se convertit qu'une fois** (D6) : toutes les planches qui le
   désignent suivent, et le master ne part que lorsque plus aucune ne le désigne.
4. **Idempotent** : un second passage ne fait rien.

Le master est l'objet scientifique : convertir l'EFFACE du serveur, et l'outil le dit avant
toute chose. `tools/` est hors couverture (`.coveragerc`) : sans ce fichier, une divergence
y donnerait un outil cassé et une suite verte.
"""
import hashlib
import io
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT))

import convertir_en_copies_de_travail as cv  # noqa: E402
import database  # noqa: E402
from pipeline import ocr as ocr_mod  # noqa: E402

ROUGE = (220, 20, 20)
CARRE = (200, 300, 200, 200)
BASE_V33 = REPO_ROOT / "tests" / "bases" / "v33-e5d2e73.sql"


@pytest.fixture(autouse=True)
def _outil_sur_les_donnees_du_test(data_dir, monkeypatch):
    monkeypatch.setattr(cv, "DATA_DIR", data_dir)


def _scan(fmt="TIFF", taille=(800, 1000), dpi=(400, 400)) -> bytes:
    img = Image.new("RGB", taille, "white")
    d = ImageDraw.Draw(img)
    x, y, w, h = CARRE
    d.rectangle((x, y, x + w - 1, y + h - 1), fill=ROUGE)
    d.rectangle((420, 520, 619, 719), fill=(20, 20, 220))
    buf = io.BytesIO()
    img.save(buf, fmt, **({"dpi": dpi} if dpi else {}))
    return buf.getvalue()


def _sql(db, q, p=()):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        r = [dict(x) for x in c.execute(q, p)]
        c.commit()
        return r
    finally:
        c.close()


def _planche_d_avant(client, album_id, db_path, data_dir, *, fmt="TIFF", ext="tif",
                     dpi=(400, 400)) -> dict:
    """Une planche comme l'import les faisait AVANT la v34 : le fichier reçu gardé tel quel
    dans `corpus/`, `master_origine` NULL. Importée par la route d'aujourd'hui, puis remise
    dans l'état d'hier."""
    data = _scan(fmt=fmt, dpi=dpi)
    p = client.post(f"/api/albums/{album_id}/import",
                    files={"file": (f"s.{ext}", data, "image/tiff")}).json()
    copie = data_dir / p["chemin_tiff"]
    master_rel = f"corpus/album_{album_id}/planche_{p['numero']:04d}.{ext}"
    copie.unlink()
    (data_dir / master_rel).write_bytes(data)
    _sql(db_path, "UPDATE planches SET chemin_tiff = ?, master_origine = NULL WHERE id = ?",
         (master_rel, p["id"]))
    return {**p, "chemin_tiff": master_rel}


def _region(client, planche_id):
    x, y, w, h = CARRE
    r = client.post(f"/api/planches/{planche_id}/regions",
                    json={"type": "bulle", "x": x, "y": y, "w": w, "h": h})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _crop(client, region_id) -> Image.Image:
    with ocr_mod._crop_lock:              # le cache garde l'image d'avant : on le vide
        ocr_mod._fermer_master()
    r = client.get(f"/api/regions/{region_id}/crop", params={"taille": 2000})
    assert r.status_code == 200, r.text
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def _empreinte(data_dir) -> dict:
    return {f.relative_to(data_dir).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted((data_dir / "corpus").rglob("*"))
            + sorted((data_dir / "derivatives").rglob("*")) if f.is_file()}


def _convertir(**kw):
    conn = database.get_connection()
    try:
        return cv.convertir(conn, **kw)
    finally:
        conn.close()


def test_a_blanc_rien_ne_bouge_et_l_outil_dit_ce_qu_il_libererait(client, album, db_path,
                                                                    data_dir):
    p = _planche_d_avant(client, album["id"], db_path, data_dir)
    avant = (_empreinte(data_dir), _sql(db_path, "SELECT * FROM planches ORDER BY id"))
    bilan = _convertir(appliquer=False)
    assert (_empreinte(data_dir), _sql(db_path, "SELECT * FROM planches ORDER BY id")) == avant
    ((chemin, ids, octets_avant, octets_apres),) = bilan["convertis"]
    assert (chemin, ids) == (p["chemin_tiff"], [p["id"]])
    assert octets_avant == (data_dir / p["chemin_tiff"]).stat().st_size
    assert 0 < octets_apres < octets_avant
    assert bilan["sautes"] == [] and bilan["echecs"] == []


def test_appliquer_convertit_et_la_region_reste_au_meme_endroit(client, album, db_path,
                                                                 data_dir):
    p = _planche_d_avant(client, album["id"], db_path, data_dir)
    region = _region(client, p["id"])
    avant_crop = _crop(client, region["id"])
    assert avant_crop.size == (200, 200)               # depuis le master, à la taille du scan
    avant = _sql(db_path, "SELECT largeur_px, hauteur_px, dpi_x, dpi_y, mode, chemin_web "
                          "FROM planches WHERE id = ?", (p["id"],))
    regions = _sql(db_path, "SELECT id, x, y, w, h FROM regions ORDER BY id")

    bilan = _convertir(appliquer=True)
    assert [c[:2] for c in bilan["convertis"]] == [(p["chemin_tiff"], [p["id"]])]

    ligne = _sql(db_path, "SELECT * FROM planches WHERE id = ?", (p["id"],))[0]
    assert ligne["chemin_tiff"] == f"corpus/album_{album['id']}/planche_0001.jpg"
    assert ligne["master_origine"] == "planche_0001.tif"
    # Ni la géométrie, ni le matériel, ni le dérivé, ni les régions ne bougent.
    assert _sql(db_path, "SELECT largeur_px, hauteur_px, dpi_x, dpi_y, mode, chemin_web "
                         "FROM planches WHERE id = ?", (p["id"],)) == avant
    assert _sql(db_path, "SELECT id, x, y, w, h FROM regions ORDER BY id") == regions
    # L'ancien master est parti ; la copie est un JPEG à 300 dpi effectifs.
    assert not (data_dir / p["chemin_tiff"]).exists()
    with Image.open(data_dir / ligne["chemin_tiff"]) as copie:
        assert copie.format == "JPEG" and copie.size == (600, 750)
    # La région recadre le même carré, à la réduction près.
    apres_crop = _crop(client, region["id"])
    assert apres_crop.size == (150, 150)
    ecart = np.abs(np.asarray(apres_crop, dtype=np.int16)
                   - np.asarray(avant_crop.resize((150, 150), Image.LANCZOS), dtype=np.int16))
    assert ecart.mean() < 6


def test_un_fichier_partage_par_une_copie_soeur_ne_se_convertit_qu_une_fois(
        client, album, db_path, data_dir):
    p = _planche_d_avant(client, album["id"], db_path, data_dir)
    document = _sql(db_path, "SELECT document_id FROM albums WHERE id = ?",
                    (album["id"],))[0]["document_id"]
    collection = _sql(db_path, "SELECT collection_id FROM collection_album WHERE album_id = ?",
                      (album["id"],))[0]["collection_id"]
    c = database.get_connection()
    try:
        soeur = database.creer_copie(c, document, collection, par=None, depuis=album["id"],
                                     cran=database.CRAN_IMAGES)
        c.commit()
    finally:
        c.close()
    ids = [r["id"] for r in _sql(db_path, "SELECT id FROM planches WHERE chemin_tiff = ? "
                                          "ORDER BY id", (p["chemin_tiff"],))]
    assert len(ids) == 2 and soeur

    bilan = _convertir(appliquer=True)
    assert [c[:2] for c in bilan["convertis"]] == [(p["chemin_tiff"], ids)]
    assert bilan["sautes"] == [] and bilan["planches"] == 2
    lignes = _sql(db_path, "SELECT chemin_tiff, master_origine FROM planches ORDER BY id")
    assert lignes == [{"chemin_tiff": f"corpus/album_{album['id']}/planche_0001.jpg",
                       "master_origine": "planche_0001.tif"}] * 2
    assert not (data_dir / p["chemin_tiff"]).exists()
    assert sorted(f.name for f in (data_dir / "corpus").rglob("*") if f.is_file()) == [
        "planche_0001.jpg"]


def test_un_second_passage_ne_fait_rien(client, album, db_path, data_dir):
    _planche_d_avant(client, album["id"], db_path, data_dir)
    _convertir(appliquer=True)
    etat = (_empreinte(data_dir), _sql(db_path, "SELECT * FROM planches ORDER BY id"))
    bilan = _convertir(appliquer=True)
    assert bilan["convertis"] == [] and bilan["sautes"] == [] and bilan["echecs"] == []
    assert (_empreinte(data_dir), _sql(db_path, "SELECT * FROM planches ORDER BY id")) == etat


def test_un_master_deja_jpeg_ne_s_ecrit_pas_sur_lui_meme(client, album, db_path, data_dir):
    """Un master JPEG porte déjà le nom que la copie prendrait : elle s'écrit à côté
    (`.travail.jpg`), jamais par-dessus — puis le master part."""
    p = _planche_d_avant(client, album["id"], db_path, data_dir, fmt="JPEG", ext="jpg",
                         dpi=(300, 300))
    _convertir(appliquer=True)
    ligne = _sql(db_path, "SELECT chemin_tiff, master_origine FROM planches")[0]
    assert ligne == {"chemin_tiff": f"corpus/album_{album['id']}/planche_0001.travail.jpg",
                     "master_origine": "planche_0001.jpg"}
    assert not (data_dir / p["chemin_tiff"]).exists()
    assert (data_dir / ligne["chemin_tiff"]).is_file()


def test_un_master_absent_est_saute_et_dit(client, album, db_path, data_dir):
    p = _planche_d_avant(client, album["id"], db_path, data_dir)
    (data_dir / p["chemin_tiff"]).unlink()
    bilan = _convertir(appliquer=True)
    assert bilan["convertis"] == []
    assert bilan["sautes"] == [(p["chemin_tiff"], [p["id"]], "master absent du disque")]
    assert _sql(db_path, "SELECT master_origine FROM planches")[0]["master_origine"] is None


def test_un_arret_demande_ne_touche_pas_au_fichier_suivant(client, album, db_path, data_dir):
    _planche_d_avant(client, album["id"], db_path, data_dir)
    arret = cv._Arret()
    arret.demande = True
    avant = _empreinte(data_dir)
    bilan = _convertir(appliquer=True, arret=arret)
    assert bilan["interrompu"] and bilan["convertis"] == []
    assert _empreinte(data_dir) == avant


def test_la_sortie_dit_que_convertir_efface_le_master(client, album, db_path, data_dir):
    """Le premier mot de l'outil, à blanc comme appliqué : convertir efface le master."""
    _planche_d_avant(client, album["id"], db_path, data_dir)
    sqlite3.connect(db_path).execute("PRAGMA wal_checkpoint(TRUNCATE)").close()
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir)}
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / cv.__name__) + ".py"],
                       cwd=str(REPO_ROOT), env=env, capture_output=True, text=True,
                       encoding="utf-8")
    assert r.returncode == 0, r.stderr
    premiere = r.stdout.splitlines()[0]
    assert "EFFACE le master du serveur" in premiere
    assert "À blanc : 1 fichier(s) à convertir, 1 planche(s)" in r.stdout
    assert "Rien n'a été écrit" in r.stdout


def test_sur_une_vraie_base_v33_tout_se_convertit_et_les_soeurs_suivent(tmp_path,
                                                                          monkeypatch):
    """La base faite par le code de la v33 (`tests/bases/v33-e5d2e73.sql`), migrée, ses
    masters posés sur le disque à leur chemin et à leurs dimensions : neuf planches, huit
    fichiers — les planches 11 et 12, copies sœurs, désignent le même."""
    from pipeline import ingest
    db = tmp_path / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V33.read_text(encoding="utf-8"))
    c.close()
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(ingest, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    monkeypatch.setattr(cv, "DATA_DIR", tmp_path)
    database.init_db()
    planches = _sql(db, "SELECT id, chemin_tiff, largeur_px, hauteur_px FROM planches")
    for p in planches:
        f = tmp_path / p["chemin_tiff"]
        f.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (p["largeur_px"], p["hauteur_px"]), "white").save(f, "PNG")
    regions = _sql(db, "SELECT * FROM regions ORDER BY id")
    geometrie = _sql(db, "SELECT id, largeur_px, hauteur_px, dpi_x, dpi_y, mode, chemin_web "
                         "FROM planches ORDER BY id")

    bilan = _convertir(appliquer=True)
    assert len(bilan["convertis"]) == 8 and bilan["planches"] == 9
    assert ("corpus/album_10/planche_0001.png", [11, 12], ) in [
        c[:2] for c in bilan["convertis"]]
    assert bilan["sautes"] == [] and bilan["echecs"] == []
    assert _sql(db, "SELECT COUNT(*) AS n FROM planches WHERE master_origine IS NULL "
                    "OR chemin_tiff NOT LIKE '%.jpg'")[0]["n"] == 0
    assert not list((tmp_path / "corpus").rglob("*.png"))
    assert _sql(db, "SELECT * FROM regions ORDER BY id") == regions
    assert _sql(db, "SELECT id, largeur_px, hauteur_px, dpi_x, dpi_y, mode, chemin_web "
                    "FROM planches ORDER BY id") == geometrie
    assert _convertir(appliquer=True)["convertis"] == []


# --------------------------------------------------------------------------- #
# Relecture croisée
# --------------------------------------------------------------------------- #
def _lancer(db_path, data_dir, *args):
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir)}
    return subprocess.run([sys.executable, str(REPO_ROOT / "tools" / cv.__name__) + ".py",
                           *args], cwd=str(REPO_ROOT), env=env, capture_output=True,
                          text=True, encoding="utf-8")


def _figer(db_path):
    """La base posée sur le disque, journal WAL replié : ce qu'un octet changé trahirait."""
    c = sqlite3.connect(db_path)
    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    c.close()
    return (hashlib.sha256(Path(db_path).read_bytes()).hexdigest(),
            _sql(db_path, "SELECT type, name, sql FROM sqlite_master ORDER BY name"),
            _sql(db_path, "PRAGMA user_version"))


def test_a_blanc_ni_la_base_ni_son_schema_ne_bougent(client, album, db_path, data_dir):
    """À blanc, l'outil ouvre la base en lecture seule et sans `init_db`, qui referait les
    vues : pas un octet de la base ne change."""
    _planche_d_avant(client, album["id"], db_path, data_dir)
    avant = (_figer(db_path), _empreinte(data_dir))
    r = _lancer(db_path, data_dir)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "À blanc : 1 fichier(s)" in r.stdout
    assert (_figer(db_path), _empreinte(data_dir)) == avant


def test_une_base_d_une_autre_version_est_refusee_par_son_nom(client, album, db_path,
                                                                data_dir):
    _planche_d_avant(client, album["id"], db_path, data_dir)
    _sql(db_path, f"PRAGMA user_version = {database.SCHEMA_VERSION - 1}")
    avant = _figer(db_path)
    for args in ((), ("--appliquer",)):
        r = _lancer(db_path, data_dir, *args)
        assert r.returncode == 2, r.stdout + r.stderr
        assert f"v{database.SCHEMA_VERSION - 1}" in r.stdout and "démarrez l'application" \
            in r.stdout
    assert _figer(db_path) == avant


def test_deux_passages_appliques_ne_se_chevauchent_pas(client, album, db_path, data_dir):
    """Le verrou de l'outil pris par un autre passage : refus nommé, rien ne bouge, et le
    verrou de l'autre reste."""
    _planche_d_avant(client, album["id"], db_path, data_dir)
    verrou = data_dir / cv.NOM_DU_VERROU
    verrou.write_text("pid 4242, depuis tout à l'heure", encoding="utf-8")
    avant = (_empreinte(data_dir), _sql(db_path, "SELECT * FROM planches"))
    with pytest.raises(cv.PassageEnCours, match="pid 4242"):
        _convertir(appliquer=True)
    assert (_empreinte(data_dir), _sql(db_path, "SELECT * FROM planches")) == avant
    assert verrou.is_file()
    verrou.unlink()
    _convertir(appliquer=True)
    assert not verrou.exists()                       # rendu à la sortie


def test_une_bascule_qui_ne_touche_aucune_planche_reprend_sa_copie(client, album, db_path,
                                                                     data_dir, monkeypatch):
    """Converti entre l'écriture de la copie et la bascule (un autre chemin) : l'`UPDATE` ne
    touche rien, la copie écrite repart, le fichier compte comme sauté — pas « converti »."""
    p = _planche_d_avant(client, album["id"], db_path, data_dir)
    vrai = cv._basculer

    def entre_temps(conn, *a, **k):
        conn.execute("UPDATE planches SET master_origine = 'converti ailleurs'")
        conn.commit()
        return vrai(conn, *a, **k)

    monkeypatch.setattr(cv, "_basculer", entre_temps)
    bilan = _convertir(appliquer=True)
    assert bilan["convertis"] == []
    assert [s[:2] for s in bilan["sautes"]] == [(p["chemin_tiff"], [p["id"]])]
    assert sorted(f.name for f in (data_dir / "corpus").rglob("*") if f.is_file()) == [
        "planche_0001.tif"]
    assert bilan["orphelins"] == []


def test_un_effacement_refuse_est_dit_et_le_master_reste_liste(client, album, db_path,
                                                                 data_dir, monkeypatch):
    """Un fichier ouvert sous Windows refuse de partir : la conversion est validée, l'outil
    ne tombe pas, il dit le master resté, et le liste parmi les fichiers qu'aucune planche ne
    désigne."""
    p = _planche_d_avant(client, album["id"], db_path, data_dir)
    vrai = Path.unlink

    def refuse(self, missing_ok=False):
        if self.suffix == ".tif":
            raise PermissionError(13, "Le fichier est utilisé par un autre processus")
        return vrai(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", refuse)
    bilan = _convertir(appliquer=True)
    assert [c[:2] for c in bilan["convertis"]] == [(p["chemin_tiff"], [p["id"]])]
    ((chemin, raison),) = bilan["laisses"]
    assert chemin == p["chemin_tiff"] and "effacement refusé" in raison
    assert [o[0] for o in bilan["orphelins"]] == [p["chemin_tiff"]]
    assert _sql(db_path, "SELECT master_origine FROM planches")[0]["master_origine"] == \
        "planche_0001.tif"


def test_a_blanc_les_fichiers_que_rien_ne_designe_sont_listes_jamais_effaces(
        client, album, db_path, data_dir):
    _planche_d_avant(client, album["id"], db_path, data_dir)
    reste = data_dir / "corpus" / f"album_{album['id']}" / "vieux_master.tif"
    reste.write_bytes(b"RESTE")
    for appliquer in (False, True):
        bilan = _convertir(appliquer=appliquer)
        assert [o[0] for o in bilan["orphelins"]] == [
            f"corpus/album_{album['id']}/vieux_master.tif"]
    assert reste.read_bytes() == b"RESTE"


def test_un_fichier_deja_au_nom_de_la_copie_n_est_pas_ecrase(client, album, db_path,
                                                              data_dir):
    """`planche_0001.jpg` existe déjà à côté du master `.tif` sans qu'aucune planche le
    désigne : la copie prend un autre nom, et ce fichier n'est pas touché."""
    p = _planche_d_avant(client, album["id"], db_path, data_dir)
    intrus = data_dir / "corpus" / f"album_{album['id']}" / "planche_0001.jpg"
    intrus.write_bytes(b"PAS A MOI")
    _convertir(appliquer=True)
    assert intrus.read_bytes() == b"PAS A MOI"
    assert _sql(db_path, "SELECT chemin_tiff FROM planches WHERE id = ?", (p["id"],))[0][
        "chemin_tiff"] == f"corpus/album_{album['id']}/planche_0001.travail.jpg"


def test_un_master_aux_dimensions_d_une_autre_planche_est_saute(client, album, db_path,
                                                               data_dir):
    p = _planche_d_avant(client, album["id"], db_path, data_dir)
    master = data_dir / p["chemin_tiff"]
    Image.new("RGB", (640, 800), "white").save(master, "TIFF", dpi=(400, 400))
    avant = (_empreinte(data_dir), _sql(db_path, "SELECT * FROM planches"))
    bilan = _convertir(appliquer=True)
    ((chemin, ids, raison),) = bilan["sautes"]
    assert (chemin, ids) == (p["chemin_tiff"], [p["id"]]) and "640 × 800" in raison
    assert (_empreinte(data_dir), _sql(db_path, "SELECT * FROM planches")) == avant


def test_une_planche_sans_dimensions_est_sautee(client, album, db_path, data_dir):
    """Sans `largeur_px`, la copie réduite s'ouvrirait à l'échelle 1 et ses régions se
    décaleraient : la planche est sautée, et le dit."""
    p = _planche_d_avant(client, album["id"], db_path, data_dir)
    _sql(db_path, "UPDATE planches SET largeur_px = NULL, hauteur_px = NULL")
    avant = _empreinte(data_dir)
    bilan = _convertir(appliquer=True)
    ((chemin, ids, raison),) = bilan["sautes"]
    assert chemin == p["chemin_tiff"] and "sans dimensions" in raison
    assert bilan["convertis"] == [] and _empreinte(data_dir) == avant


def test_la_reservation_d_un_import_interrompu_est_listee_dans_les_deux_dossiers(
        client, album, db_path, data_dir):
    """Un import tué après `ingest._reserver` laisse deux fichiers VIDES, l'un dans
    `corpus/`, l'autre dans `derivatives/` : listés tous deux, vides, jamais effacés."""
    from pipeline import ingest
    reserves = ingest._reserver([
        data_dir / "corpus" / f"album_{album['id']}" / "planche_0007.jpg",
        data_dir / "derivatives" / f"album_{album['id']}" / "planche_0007.jpg"])
    bilan = _convertir(appliquer=False)
    assert sorted(bilan["orphelins"]) == [
        (f"corpus/album_{album['id']}/planche_0007.jpg", 0),
        (f"derivatives/album_{album['id']}/planche_0007.jpg", 0)]
    assert all(f.is_file() for f in reserves)
    r = _lancer(db_path, data_dir)
    assert "réservation d'un import interrompu" in r.stdout, r.stdout


# --------------------------------------------------------------------------- #
# La progression : une ligne par fichier, AU MOMENT où il est traité
# --------------------------------------------------------------------------- #
# En production, l'outil tourne des heures sous `nohup … > conversion.log` : sa sortie est
# un FICHIER, que Python remplit par blocs de plusieurs Ko. Les lignes par fichier n'étaient
# écrites qu'au bilan, et le journal ne montrait que l'avertissement pendant des dizaines de
# minutes. L'espion lit ce fichier pendant le passage, au moment où le fichier SUIVANT
# commence : ce qu'il y trouve est ce qu'un exploitant aurait lu.
_ESPION = r'''
import os, sys
from pathlib import Path
sys.path.insert(0, os.environ["DEPOT"])
sys.path.insert(0, os.path.join(os.environ["DEPOT"], "tools"))
import convertir_en_copies_de_travail as cv

vrai = cv._metadonnees
appels = []


def espion(img):
    appels.append(1)
    if len(appels) == 2:
        Path(os.environ["VU"]).write_text(
            Path(os.environ["SORTIE"]).read_text(encoding="utf-8"), encoding="utf-8")
    return vrai(img)


cv._metadonnees = espion
raise SystemExit(cv.main(sys.argv[1:]))
'''


@pytest.mark.parametrize("args, marque, verbe", [((), "·", "à convertir"),
                                                 (("--appliquer",), "✓", "converti")])
def test_la_ligne_d_un_fichier_sort_avant_que_le_suivant_soit_traite(
        client, album, db_path, data_dir, tmp_path, args, marque, verbe):
    p1 = _planche_d_avant(client, album["id"], db_path, data_dir)
    p2 = _planche_d_avant(client, album["id"], db_path, data_dir)
    sqlite3.connect(db_path).execute("PRAGMA wal_checkpoint(TRUNCATE)").close()
    espion = tmp_path / "espion.py"
    espion.write_text(_ESPION, encoding="utf-8")
    sortie, vu = tmp_path / "sortie.log", tmp_path / "vu.log"
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir),
           "DEPOT": str(REPO_ROOT), "SORTIE": str(sortie), "VU": str(vu)}
    with open(sortie, "w", encoding="utf-8") as f:            # un fichier, comme `> log`
        r = subprocess.run([sys.executable, str(espion), *args], cwd=str(REPO_ROOT), env=env,
                           stdout=f, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    final = sortie.read_text(encoding="utf-8")
    assert r.returncode == 0, final + r.stderr

    # Au moment où le deuxième fichier commence : l'avertissement, le compte, la ligne du
    # premier — et rien du deuxième.
    pendant = vu.read_text(encoding="utf-8").splitlines()
    assert "EFFACE le master du serveur" in pendant[0]
    assert pendant[1].startswith("2 fichier(s) à traiter, 2 planche(s)")
    assert pendant[2].startswith(f"  1 sur 2 {marque} {p1['chemin_tiff']} — {verbe}, "
                                 f"planche(s) {p1['id']} : "), pendant
    assert len(pendant) == 3, pendant

    # À la fin, la ligne du deuxième, et le bilan ne redit aucun fichier.
    lignes = final.splitlines()
    assert lignes[:3] == pendant
    assert lignes[3].startswith(f"  2 sur 2 {marque} {p2['chemin_tiff']} — {verbe}, ")
    assert sum(p1["chemin_tiff"] in ligne for ligne in lignes) == 1
    assert sum(p2["chemin_tiff"] in ligne for ligne in lignes) == 1


def test_chaque_issue_a_sa_ligne_au_fil_du_passage(client, album, db_path, data_dir):
    """Converti, sauté, échec : chacun sa ligne, numérotée dans l'ordre, sur le total
    compté AVANT le premier fichier."""
    p1 = _planche_d_avant(client, album["id"], db_path, data_dir)
    p2 = _planche_d_avant(client, album["id"], db_path, data_dir)
    p3 = _planche_d_avant(client, album["id"], db_path, data_dir)
    (data_dir / p2["chemin_tiff"]).unlink()
    (data_dir / p3["chemin_tiff"]).write_bytes(b"PAS UNE IMAGE")
    dit = []
    bilan = _convertir(appliquer=True, dire=dit.append)
    assert dit[0].startswith("3 fichier(s) à traiter, 3 planche(s)")
    assert dit[1].startswith(f"  1 sur 3 ✓ {p1['chemin_tiff']} — converti, planche(s) "
                             f"{p1['id']} : ")
    assert dit[2] == (f"  2 sur 3 – {p2['chemin_tiff']} — sauté, planche(s) {p2['id']} : "
                      "master absent du disque")
    assert dit[3].startswith(f"  3 sur 3 ✗ {p3['chemin_tiff']} — échec, planche(s) "
                             f"{p3['id']} : ")
    assert len(dit) == 4 and bilan["total"] == 3


def test_un_master_reste_sur_le_disque_se_dit_sur_la_ligne_du_fichier(
        client, album, db_path, data_dir, monkeypatch):
    p = _planche_d_avant(client, album["id"], db_path, data_dir)
    monkeypatch.setattr(cv, "_effacer_si_libre", lambda conn, rel: "effacement refusé (test)")
    dit = []
    _convertir(appliquer=True, dire=dit.append)
    assert dit[1].startswith(f"  1 sur 1 ✓ {p['chemin_tiff']} — converti, ")
    assert dit[1].endswith("; ⚠ le master reste sur le disque — effacement refusé (test)")
