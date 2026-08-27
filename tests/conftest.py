"""Fixtures pytest : TestClient isolé sur une base + des dossiers data jetables.

Chaque test reçoit une base SQLite neuve et des répertoires corpus/derivatives
sous le tmp_path pytest (aucune pollution du dépôt). On patche les constantes
de chemin DÉJÀ importées dans les modules (database, pipeline.*), qui sont lues
au moment de l'appel.
"""
import io
import os
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import config  # noqa: E402
import database  # noqa: E402
import autorisation  # noqa: E402
import main  # noqa: E402
import pipeline.ingest as ingest  # noqa: E402
import pipeline.segmentation as segmentation  # noqa: E402

# Page BD d'exemple fournie par Kumiko (grille régulière, 6 cases).
KUMIKO_SAMPLE = (REPO_ROOT
                 / "lib/kumiko/tests/images/000-common-page-templates/simple.png")

import pipeline.bulles as bulles_mod  # noqa: E402
import pipeline.jobs as jobs_mod  # noqa: E402
import pipeline.ocr as ocr_mod  # noqa: E402
import pipeline.sharedocs as sharedocs_mod  # noqa: E402
import sante as sante_mod  # noqa: E402

requires_kumiko = pytest.mark.skipif(
    not segmentation.kumiko_available(),
    reason="Kumiko indisponible (clone lib/kumiko absent ou OpenCV/cv2 non installé)",
)
requires_bulles = pytest.mark.skipif(
    not bulles_mod.bulles_available(), reason="ultralytics non installé")
requires_ocr = pytest.mark.skipif(
    not ocr_mod.ocr_available(), reason="easyocr non installé")


@pytest.fixture(autouse=True)
def _reset_global_state():
    """Réinitialise les singletons de module (registre de jobs + compteur, cache
    de crop, session ShareDocs) AVANT chaque test — sinon l'état fuit d'un test à
    l'autre. Centralisé ici pour couvrir TOUTE la suite, pas un seul fichier."""
    jobs_mod._jobs.clear()
    jobs_mod._counter = 0
    if ocr_mod._crop_cache.get("img") is not None:
        try:
            ocr_mod._crop_cache["img"].close()
        except Exception:
            pass
    ocr_mod._crop_cache.update(planche_id=None, img=None, scale=1.0)
    sharedocs_mod.disconnect()
    main._vus.clear()          # AUTH-1 : miroir des identités déjà écrites en base
    sante_mod._reset()         # SANTE-1 : mémoïsation des contrôles profonds
    yield


@pytest.fixture
def derriere_proxy(monkeypatch):
    """Place le test DERRIÈRE le proxy d'authentification (AUTH-1).

    Hors de ce contexte, `main.AUTH_PROXY` est faux et les en-têtes d'identité
    (`Remote-User`, `Remote-Groups`…) sont IGNORÉS — c'est la garde anti-usurpation :
    un client qui atteindrait l'app en direct pourrait sinon se déclarer qui il veut.
    Tout test qui envoie ces en-têtes doit donc déclarer ce contexte explicitement,
    plutôt qu'on n'active la confiance pour toute la suite : ce serait précisément
    perdre de vue ce que la garde protège."""
    monkeypatch.setattr(main, "AUTH_PROXY", True)
    monkeypatch.setattr(autorisation, "AUTH_PROXY", True)
    yield


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Redirige base + dossiers data vers un tmp jetable et init la base."""
    db_file = tmp_path / "test.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    # AUTH-2 : `main.DATA_DIR` sert désormais les images dérivées (route cloisonnée qui a
    # remplacé le montage StaticFiles). Sans ce patch, un test lisant une image la prendrait
    # dans le corpus RÉEL du dépôt — il passerait, mais sur les fichiers d'à côté.
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
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


# AUTH-2 : le DÉCOR d'un test est monté par un administrateur.
#
# Sans proxy d'auth ces en-têtes sont ignorés (garde AUTH-1) et rien ne change : c'est le
# cas de l'immense majorité de la suite. Mais un test qui déclare `derriere_proxy` place
# la requête sous cloisonnement, et son décor deviendrait alors impossible à monter — une
# personne inconnue n'a droit à rien, par construction (fermeture par défaut).
#
# On aurait pu compter sur l'ordre des fixtures (monter le décor AVANT `derriere_proxy`),
# mais faire dépendre la suite d'un ordre implicite est précisément le genre de garantie
# qui se casse sans bruit. Les en-têtes, eux, sont explicites et sans effet quand ils ne
# servent pas.
ADMIN = {"Remote-User": "decor", "Remote-Groups": "bd-admins"}


@pytest.fixture
def album(client):
    return client.post("/api/albums",
                       json={"titre": "Test", "serie": "S", "annee": 2016},
                       headers=ADMIN).json()


@pytest.fixture
def planche(client, album, png_bytes):
    return client.post(
        f"/api/albums/{album['id']}/import",
        files={"file": ("planche.png", png_bytes, "image/png")},
        headers=ADMIN,
    ).json()


@pytest.fixture
def region(client, planche):
    """Une région 'case' simple sur la planche importée."""
    return client.post(
        f"/api/planches/{planche['id']}/regions",
        json={"type": "case", "x": 10, "y": 10, "w": 100, "h": 80},
        headers=ADMIN,
    ).json()


def direct_query(db_file: Path, sql: str, params=()):
    """Ouvre une connexion SQLite SÉPARÉE (vérif de persistance sur disque)."""
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def live_server(request, tmp_path):
    """Lance un VRAI serveur uvicorn isolé (base + data dans un tmp via
    BD_DATA_DIR/BD_DB_PATH) et renvoie son URL de base. Utilisé par les tests
    d'intégration `live` (course écriture→lecture) et les E2E navigateur.

    Par DÉFAUT, le serveur n'est PAS déclaré derrière le proxy d'auth. Ce n'était pas le
    cas avant AUTH-2, et le changement est délibéré : depuis le cloisonnement, un serveur
    qui se croit derrière Authelia refuse tout à une requête sans en-tête d'identité
    (fermeture par défaut). Or un navigateur de test n'en envoie pas, et le corpus
    apparaîtrait vide aux quarante tests E2E — qui passeraient au vert en n'auditant plus
    rien. Le mode mono-poste est ce qu'ils ont toujours exercé.

    Les tests qui ont VRAIMENT besoin d'une identité l'exigent explicitement :

        @pytest.mark.parametrize("live_server", [True], indirect=True)

    et envoient alors `Remote-User` — plus `Remote-Groups: bd-admins` s'ils veulent aussi
    voir le corpus, faute d'entrée dans `collection_acces`.
    """
    derriere_proxy = getattr(request, "param", False)
    port = _free_port()
    env = {**os.environ,
           "BD_DATA_DIR": str(tmp_path),
           "BD_DB_PATH": str(tmp_path / "live.sqlite"),
           # Le drapeau doit entrer dans le SOUS-PROCESSUS : la fixture `derriere_proxy`
           # patche le processus de test, ce qui n'a aucun effet sur un serveur lancé à part.
           "BD_AUTH_PROXY": "1" if derriere_proxy else ""}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(REPO_ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    poll = httpx.Client(trust_env=False, timeout=1)  # trust_env=False : ignore le proxy
    try:
        deadline = time.time() + 25
        while time.time() < deadline:
            if proc.poll() is not None:
                pytest.fail("le serveur uvicorn s'est arrêté au démarrage")
            try:
                if poll.get(base + "/api/sante").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.3)
        else:
            pytest.fail("serveur uvicorn non disponible dans le délai")
        yield base
    finally:
        poll.close()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
