"""Régression course écriture→lecture, contre un VRAI serveur uvicorn.

TestClient exécute le teardown des dépendances de façon synchrone et ne
reproduit donc pas le bug (commit après envoi de la réponse). Seul un serveur
réel, frappé par un client séquentiel, le révèle. Ce test lance un uvicorn
isolé (base + data dans un tmp via BD_DATA_DIR/BD_DB_PATH), martèle des
écritures suivies de relectures immédiates, et exige une cohérence parfaite.

Marqué `live` : désélectionnable avec `-m "not live"`.
"""
import io

import httpx
import pytest
from PIL import Image

# `live_server` est fourni par conftest.py (partagé avec les tests E2E).
pytestmark = pytest.mark.live


def test_ecriture_puis_lecture_immediate_coherentes(live_server):
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=10)
    aid = c.post("/api/albums", json={"titre": "Live"}).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (200, 250), "white").save(buf, "PNG")
    pid = c.post(f"/api/albums/{aid}/import",
                 files={"file": ("p.png", buf.getvalue(), "image/png")}).json()["id"]
    reg = c.post(f"/api/planches/{pid}/regions",
                 json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5}).json()["id"]

    # Réchauffe le NLP HORS mesure : la 1re écriture déclenche le chargement à froid
    # de spaCy (~10 s) — ici on teste la course écriture→lecture, pas cette latence.
    c.put(f"/api/regions/{reg}/annotation",
          json={"note": "WARMUP", "tags": []}, timeout=120)

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
