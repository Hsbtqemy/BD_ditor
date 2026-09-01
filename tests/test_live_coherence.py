"""Cohérence écriture→lecture, contre un VRAI serveur uvicorn.

RENOMMÉ le 2026-08-31 (constat T2, AUDIT-1) : le fichier s'appelait
`test_live_race.py` et promettait une CONCURRENCE qu'il ne joue pas. Il martèle le
serveur avec un client `httpx` unique et SÉQUENTIEL — l'ancienne docstring le
reconnaissait déjà, sans que le nom en tienne compte —, et c'est la bonne forme pour
le bug qu'il garde : un commit émis APRÈS la réponse se révèle en relisant tout de
suite, pas en écrivant à plusieurs. Un nom qui survend donne un faux sentiment de
sécurité, et c'est ce que l'audit a relevé.

La VRAIE concurrence reste non testée, et il vaut mieux que ce soit lisible ici que
masqué par un nom de fichier : ni deux jobs simultanés sur `_run_lock`, ni écriture
du worker ↔ lecture du serveur, ni `make_backup` pendant une écriture. C'est le
constat « concurrence sous-testée » d'AUDIT.md, distinct de celui-ci.

TestClient exécute le teardown des dépendances de façon synchrone et ne reproduit
donc pas le bug. Ce test lance un uvicorn isolé (base + data dans un tmp via
BD_DATA_DIR/BD_DB_PATH), martèle des écritures suivies de relectures immédiates,
et exige une cohérence parfaite.

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
    assert miss == 0, (
        f"{miss}/{N} relectures incohérentes : une écriture n'était pas visible de la "
        "requête suivante (commit émis après la réponse). Ce n'est pas une course entre "
        "clients — un seul client, séquentiel, suffit à le voir.")
