"""Matériel de numérisation (A6, niveau 1) — tests.

Vérifie la couche matérielle des planches : schéma v19 + migration (ADD COLUMN), capture
à l'ingest de la résolution (`dpi_x`/`dpi_y`) et du `mode` colorimétrique, dérivation des
dimensions physiques (cm), champ album `source_numerisation`, outil de backfill (re-lecture
des masters), et propagation dans les exports (records + tables CSV + roll-up + dictionnaire).
"""
import io
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TOOLS))

import database  # noqa: E402
from conftest import direct_query, make_png  # noqa: E402


def _png_dpi(dpi=(300, 300), size=(600, 900)) -> bytes:
    """PNG en mémoire PORTANT une résolution (pHYs) — pour exercer la capture du dpi."""
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, "PNG", dpi=dpi)
    return buf.getvalue()


def _importer(client, album_id, data, nom="scan.png") -> dict:
    return client.post(f"/api/albums/{album_id}/import",
                       files={"file": (nom, data, "image/png")}).json()


def _planches(client, album_id):
    return client.get(f"/api/albums/{album_id}/planches").json()


def _run(script, db_path, data_dir, *args):
    """Lance un outil en sous-processus (BD_DB_PATH/BD_DATA_DIR), décodage UTF-8."""
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir)}
    return subprocess.run([sys.executable, str(TOOLS / script), *args],
                          cwd=str(REPO_ROOT), env=env, capture_output=True,
                          text=True, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Schéma & migration
# --------------------------------------------------------------------------- #
def test_schema_v19(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    pcols = {r["name"] for r in conn.execute("PRAGMA table_info(planches)")}
    assert {"dpi_x", "dpi_y", "mode"} <= pcols
    acols = {r["name"] for r in conn.execute("PRAGMA table_info(albums)")}
    assert "source_numerisation" in acols
    conn.close()


def test_migration_v18_vers_v19_ajoute_colonnes(tmp_path):
    """Depuis un schéma minimal « v18 » (planches sans matériel, albums sans source), `_migrate`
    pose les colonnes par ALTER (gardé par présence) et porte la base au schéma courant."""
    db = tmp_path / "pre19.sqlite"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE albums (id INTEGER PRIMARY KEY, titre TEXT);"
        "CREATE TABLE planches (id INTEGER PRIMARY KEY, album_id INTEGER, numero INTEGER,"
        " largeur_px INTEGER, hauteur_px INTEGER);"
        "PRAGMA user_version = 18;")
    conn.commit()
    database._migrate(conn)
    pcols = {r["name"] for r in conn.execute("PRAGMA table_info(planches)")}
    acols = {r["name"] for r in conn.execute("PRAGMA table_info(albums)")}
    assert {"dpi_x", "dpi_y", "mode"} <= pcols
    assert "source_numerisation" in acols
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    conn.close()


# --------------------------------------------------------------------------- #
# Dérivation
# --------------------------------------------------------------------------- #
def test_dimensions_cm_derivees():
    assert database.dimensions_cm(600, 900, 300, 300) == {"largeur": 5.1, "hauteur": 7.6}
    assert database.dimensions_cm(600, 900, None, None) is None   # sans résolution : indérivable
    assert database.dimensions_cm(None, None, 300, 300) is None
    assert database.dimensions_cm(600, 900, 0, 0) is None         # dpi absurde : pas de division


# --------------------------------------------------------------------------- #
# Capture à l'ingest
# --------------------------------------------------------------------------- #
def test_ingest_capte_dpi_mode_et_derive_cm(client, album):
    _importer(client, album["id"], _png_dpi(dpi=(300, 300), size=(600, 900)))
    p = _planches(client, album["id"])[0]
    assert p["dpi_x"] == 300 and p["dpi_y"] == 300 and p["mode"] == "RGB"
    assert p["dimensions_cm"] == {"largeur": 5.1, "hauteur": 7.6}


def test_ingest_sans_resolution(client, album):
    """Un fichier sans dpi (PNG nu) : mode capté, dpi None, dimensions cm indérivables."""
    _importer(client, album["id"], make_png(400, 500))
    p = _planches(client, album["id"])[0]
    assert p["dpi_x"] is None and p["dpi_y"] is None
    assert p["mode"] == "RGB" and p["dimensions_cm"] is None


def test_read_metadata_normalise_resolution_cassee():
    """Une résolution nulle / incomplète (métadonnées scanner cassées) est traitée comme
    absente — pas de `dpi_y=0` stocké, pas d'indicateur « avec résolution » faussé."""
    from pipeline.ingest import read_metadata
    buf = io.BytesIO()
    Image.new("RGB", (600, 900), "white").save(buf, "PNG", dpi=(300, 0))   # Y à zéro
    buf.seek(0)
    assert read_metadata(buf)["dpi"] is None


# --------------------------------------------------------------------------- #
# Source de numérisation (album)
# --------------------------------------------------------------------------- #
def test_source_numerisation_album(client, album, db_path):
    r = client.put(f"/api/albums/{album['id']}",
                   json={"source_numerisation": "Epson V850, 600 dpi"}).json()
    assert r["source_numerisation"] == "Epson V850, 600 dpi"
    row = direct_query(db_path, "SELECT source_numerisation FROM albums WHERE id = ?",
                       (album["id"],))
    assert row[0]["source_numerisation"] == "Epson V850, 600 dpi"


# --------------------------------------------------------------------------- #
# Backfill (outil)
# --------------------------------------------------------------------------- #
def test_backfill_relit_les_masters(client, album, db_path, data_dir):
    pl = _importer(client, album["id"], _png_dpi(dpi=(300, 300), size=(600, 900)))
    # Simule une planche importée AVANT la v19 : matériel non renseigné en base.
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE planches SET dpi_x = NULL, dpi_y = NULL, mode = NULL WHERE id = ?",
                 (pl["id"],))
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")   # visible par le sous-processus
    conn.close()
    r = _run("reindex_materiel.py", db_path, data_dir)
    assert r.returncode == 0, r.stderr
    row = direct_query(db_path, "SELECT dpi_x, dpi_y, mode FROM planches WHERE id = ?",
                       (pl["id"],))
    assert row[0]["dpi_x"] == 300 and row[0]["dpi_y"] == 300 and row[0]["mode"] == "RGB"


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def test_export_porte_le_materiel(client, album, db_path):
    _importer(client, album["id"], _png_dpi(dpi=(300, 300), size=(600, 900)))
    client.put(f"/api/albums/{album['id']}", json={"source_numerisation": "Epson V850"})
    import metadonnees_collection as mc
    import description_collection as dc
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    doc = mc.collecter(conn)["metadonnees_collection"]
    alb = doc["albums"][0]
    assert alb["source_numerisation"] == "Epson V850"
    plr = alb["planches"][0]
    assert plr["dpi_x"] == 300 and plr["mode"] == "RGB"
    assert plr["dimensions_cm"] == {"largeur": 5.1, "hauteur": 7.6}

    cols, rows = mc.tables(conn)["planches"]
    assert {"dpi_x", "dpi_y", "mode", "largeur_cm", "hauteur_cm"} <= set(cols)
    i = cols.index("largeur_cm")
    assert rows[0][i] == 5.1
    acols, _ = mc.tables(conn)["albums"]
    assert "source_numerisation" in acols

    fiche = dc.collecter(conn)[0]["description_collection"]["couverture"]["planches"]
    conn.close()
    assert fiche["materiel"]["avec_resolution"] == 1
    assert fiche["materiel"]["pct_avec_resolution"] == 100.0
    assert fiche["materiel"]["par_mode"] == {"RGB": 1}
