"""Fixtures pytest : TestClient isolé sur une base + des dossiers data jetables.

Chaque test reçoit une base SQLite neuve et des répertoires corpus/derivatives
sous le tmp_path pytest (aucune pollution du dépôt). On patche les constantes
de chemin DÉJÀ importées dans les modules (database, pipeline.*), qui sont lues
au moment de l'appel.
"""
import io
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import config  # noqa: E402
import database  # noqa: E402
import main  # noqa: E402
import pipeline.ingest as ingest  # noqa: E402
import pipeline.segmentation as segmentation  # noqa: E402

# Page BD d'exemple fournie par Kumiko (grille régulière, 6 cases).
KUMIKO_SAMPLE = (REPO_ROOT
                 / "lib/kumiko/tests/images/000-common-page-templates/simple.png")

import pipeline.bulles as bulles_mod  # noqa: E402
import pipeline.ocr as ocr_mod  # noqa: E402

requires_kumiko = pytest.mark.skipif(
    not segmentation.kumiko_available(),
    reason="Kumiko non installé dans lib/kumiko",
)
requires_bulles = pytest.mark.skipif(
    not bulles_mod.bulles_available(), reason="ultralytics non installé")
requires_ocr = pytest.mark.skipif(
    not ocr_mod.ocr_available(), reason="easyocr non installé")


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Redirige base + dossiers data vers un tmp jetable et init la base."""
    db_file = tmp_path / "test.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    monkeypatch.setattr(ingest, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    monkeypatch.setattr(segmentation, "DATA_DIR", tmp_path)
    monkeypatch.setattr(bulles_mod, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ocr_mod, "DATA_DIR", tmp_path)
    database.init_db()
    return tmp_path


@pytest.fixture
def client(data_dir):
    return TestClient(main.app)


@pytest.fixture
def db_path(data_dir):
    """Chemin de la base de test (pour vérifier la persistance directement)."""
    return data_dir / "test.sqlite"


def make_png(width=400, height=500, color="white") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def png_bytes():
    """Petite image PNG en mémoire (dimensions connues : 400x500)."""
    return make_png()


@pytest.fixture
def album(client):
    return client.post("/api/albums",
                       json={"titre": "Test", "serie": "S", "annee": 2016}).json()


@pytest.fixture
def planche(client, album, png_bytes):
    return client.post(
        f"/api/albums/{album['id']}/import",
        files={"file": ("planche.png", png_bytes, "image/png")},
    ).json()


@pytest.fixture
def region(client, planche):
    """Une région 'case' simple sur la planche importée."""
    return client.post(
        f"/api/planches/{planche['id']}/regions",
        json={"type": "case", "x": 10, "y": 10, "w": 100, "h": 80},
    ).json()


def direct_query(db_file: Path, sql: str, params=()):
    """Ouvre une connexion SQLite SÉPARÉE (vérif de persistance sur disque)."""
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
