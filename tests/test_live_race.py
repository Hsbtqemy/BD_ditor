"""Régression course écriture→lecture, contre un VRAI serveur uvicorn.

TestClient exécute le teardown des dépendances de façon synchrone et ne
reproduit donc pas le bug (commit après envoi de la réponse). Seul un serveur
réel, frappé par un client séquentiel, le révèle. Ce test lance un uvicorn
isolé (base + data dans un tmp via BD_DATA_DIR/BD_DB_PATH), martèle des
écritures suivies de relectures immédiates, et exige une cohérence parfaite.

Marqué `live` : désélectionnable avec `-m "not live"`.
"""
import io
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.live


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def live_server(tmp_path):
    port = _free_port()
    env = {**os.environ,
           "BD_DATA_DIR": str(tmp_path),
           "BD_DB_PATH": str(tmp_path / "live.sqlite")}
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


def test_ecriture_puis_lecture_immediate_coherentes(live_server):
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=10)
    aid = c.post("/api/albums", json={"titre": "Live"}).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (200, 250), "white").save(buf, "PNG")
    pid = c.post(f"/api/albums/{aid}/import",
                 files={"file": ("p.png", buf.getvalue(), "image/png")}).json()["id"]
    reg = c.post(f"/api/planches/{pid}/regions",
                 json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5}).json()["id"]

    N = 30
    miss = 0
    for i in range(N):
        note = f"NOTE-{i}-UNIQUE"
        c.put(f"/api/regions/{reg}/annotation", json={"note": note, "tags": [f"t{i}"]})
        got = c.get(f"/api/regions/{reg}/annotation").json()
        if got.get("note") != note:
            miss += 1
    c.close()
    assert miss == 0, f"{miss}/{N} relectures incohérentes (course écriture→lecture)"
