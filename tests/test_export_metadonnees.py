"""Smoke tests des scripts d'export de métadonnées (`tools/`).

`tools/` est hors couverture, mais ces tests verrouillent la **non-régression
fonctionnelle** des quatre outils : chacun tourne de bout en bout sur un corpus
réel (bâti par l'API) et produit une sortie exploitable. Exécution en
SOUS-PROCESSUS (comme le test `live`), avec `BD_DB_PATH` pointant la base de test.
"""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"


def _run(script, db_path, data_dir, *args):
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir)}
    return subprocess.run([sys.executable, str(TOOLS / script), *args],
                          cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)


@pytest.fixture
def corpus(client, region, db_path, data_dir):
    """Album + planche + région (via l'API), plus une annotation dont la note est une
    FORMULE Excel (pour le garde anti-injection du XLSX). Checkpoint WAL pour qu'un
    process lecteur séparé voie tout."""
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO annotations (region_id, note) VALUES (?, ?)",
                 (region["id"], "=1+1"))
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    return {"db": db_path, "data": data_dir}


def test_metadonnees_json(corpus):
    r = _run("metadonnees_collection.py", corpus["db"], corpus["data"], "--json", "-")
    assert r.returncode == 0, r.stderr
    mc = json.loads(r.stdout)["metadonnees_collection"]
    assert len(mc["albums"]) == 1
    assert mc["paradonnee"]["schema_version"]
    assert mc["paradonnee"]["outil"]["nom"] == "BéDéditeur"   # parité outil


def test_description_json(corpus):
    r = _run("description_collection.py", corpus["db"], corpus["data"], "--json", "-")
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)["description_collection"]
    assert doc["couverture"]["albums"] == 1
    assert doc["outil"]["nom"] == "BéDéditeur"                # même provenance que les enreg.


def test_csv_tables_bom(corpus, tmp_path):
    dossier = tmp_path / "tables"
    r = _run("metadonnees_collection.py", corpus["db"], corpus["data"],
             "--csv-dir", str(dossier))
    assert r.returncode == 0, r.stderr
    assert (dossier / "albums.csv").read_bytes()[:3] == b"\xef\xbb\xbf"   # BOM UTF-8
    assert (dossier / "paradonnee.csv").exists()


def test_xlsx_anti_injection(corpus, tmp_path):
    pytest.importorskip("openpyxl")
    from openpyxl import load_workbook
    xlsx = tmp_path / "meta.xlsx"
    r = _run("metadonnees_collection.py", corpus["db"], corpus["data"], "--xlsx", str(xlsx))
    assert r.returncode == 0, r.stderr
    wb = load_workbook(xlsx)
    assert {"fiche", "arbre", "paradonnee"} <= set(wb.sheetnames)
    # la note '=1+1' doit être du TEXTE, jamais une formule
    cells = [c for row in wb["annotations"].iter_rows() for c in row if c.value == "=1+1"]
    assert cells and all(c.data_type == "s" for c in cells)


def test_iiif_valide(corpus, tmp_path):
    out = tmp_path / "iiif"
    r = _run("iiif_manifest.py", corpus["db"], corpus["data"],
             "--base-url", "http://exemple/iiif", "--out-dir", str(out))
    assert r.returncode == 0, r.stderr
    assert (out / "collection.json").exists()
    v = _run("valider_iiif.py", corpus["db"], corpus["data"], str(out))
    assert v.returncode == 0, v.stdout + v.stderr   # manifests conformes


def test_iiif_conformance_stricte(corpus, tmp_path):
    """Conformité STRICTE via iiif-prezi3 (lib IIIF officielle) : le manifest généré se
    re-parse sans erreur dans ses modèles typés → validation INDÉPENDANTE de notre
    validateur maison. Skip propre si la lib n'est pas installée."""
    pytest.importorskip("iiif_prezi3")
    out = tmp_path / "iiif"
    r = _run("iiif_manifest.py", corpus["db"], corpus["data"],
             "--base-url", "http://exemple/iiif", "--out-dir", str(out))
    assert r.returncode == 0, r.stderr
    v = _run("valider_iiif.py", corpus["db"], corpus["data"], str(out))
    assert v.returncode == 0, v.stdout + v.stderr
    assert "Conformité stricte (iiif-prezi3) : exécutée" in v.stdout   # la passe a bien tourné
