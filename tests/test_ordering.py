"""Tests de l'ordre de lecture : reading_order (unitaire), reorder_planche et
les routes /reordonner et /deplacer (rang per-niveau, regroupement par case,
déplacement manuel)."""
from pipeline.ordering import reading_order


def _mk(client, planche_id, **kw):
    body = {"type": "case", "x": 0, "y": 0, "w": 50, "h": 50}
    body.update(kw)
    return client.post(f"/api/planches/{planche_id}/regions", json=body).json()


def _ordres(client, planche_id):
    return {r["id"]: r["ordre"]
            for r in client.get(f"/api/planches/{planche_id}/regions").json()}


# ------------------------------ reading_order ------------------------------ #
def test_reading_order_vide():
    assert reading_order([]) == []


def test_reading_order_grille():
    boxes = [
        {"n": "tl", "x": 0,   "y": 0,   "w": 100, "h": 100},
        {"n": "tr", "x": 200, "y": 0,   "w": 100, "h": 100},
        {"n": "bl", "x": 0,   "y": 200, "w": 100, "h": 100},
        {"n": "br", "x": 200, "y": 200, "w": 100, "h": 100},
    ]
    assert [b["n"] for b in reading_order(boxes)] == ["tl", "tr", "bl", "br"]


def test_reading_order_cases_hautes_laterales():
    """Cas réel : de grandes cases latérales enjambent deux rangées. Le tri par
    bord HAUT garde la rangée du haut groupée (A,B,C) avant la suivante."""
    boxes = [
        {"n": "A", "x": 96,   "y": 620,  "w": 424,  "h": 966},
        {"n": "B", "x": 524,  "y": 620,  "w": 1024, "h": 324},
        {"n": "C", "x": 1552, "y": 620,  "w": 404,  "h": 966},
        {"n": "D", "x": 524,  "y": 943,  "w": 508,  "h": 644},
        {"n": "E", "x": 1036, "y": 943,  "w": 512,  "h": 644},
        {"n": "F", "x": 96,   "y": 1587, "w": 1860, "h": 520},
    ]
    assert [b["n"] for b in reading_order(boxes)] == ["A", "B", "C", "D", "E", "F"]


# ------------------------------ /reordonner -------------------------------- #
def test_reordonner_cases_en_ordre_de_lecture(client, planche):
    pid = planche["id"]
    bas = _mk(client, pid, x=0,   y=300, w=50, h=50)
    haut_g = _mk(client, pid, x=0, y=0,  w=50, h=50)
    haut_d = _mk(client, pid, x=200, y=0, w=50, h=50)
    # créées bas, haut-gauche, haut-droite → ordre 1,2,3 (≠ position)
    assert client.post(f"/api/planches/{pid}/reordonner").status_code == 200
    o = _ordres(client, pid)
    assert o[haut_g["id"]] == 1
    assert o[haut_d["id"]] == 2
    assert o[bas["id"]] == 3


def test_reordonner_groupe_bulles_par_case(client, planche):
    pid = planche["id"]
    c1 = _mk(client, pid, x=0, y=0,   w=100, h=100)
    c2 = _mk(client, pid, x=0, y=200, w=100, h=100)
    b1 = _mk(client, pid, type="bulle", parent_id=c1["id"], x=10, y=10, w=20, h=20)
    b2 = _mk(client, pid, type="bulle", parent_id=c1["id"], x=10, y=50, w=20, h=20)
    b3 = _mk(client, pid, type="bulle", parent_id=c2["id"], x=10, y=210, w=20, h=20)
    client.post(f"/api/planches/{pid}/reordonner")
    o = _ordres(client, pid)
    assert o[c1["id"]] == 1 and o[c2["id"]] == 2
    assert o[b1["id"]] == 1 and o[b2["id"]] == 2   # rang RELATIF à la case
    assert o[b3["id"]] == 1


def test_reordonner_planche_inexistante(client):
    assert client.post("/api/planches/999/reordonner").status_code == 404


# ------------------------------- /deplacer --------------------------------- #
def test_deplacer_haut_bas(client, planche):
    pid = planche["id"]
    c1 = _mk(client, pid); c2 = _mk(client, pid); _mk(client, pid)
    r = client.post(f"/api/regions/{c1['id']}/deplacer", json={"sens": "bas"})
    assert r.status_code == 200 and r.json()["moved"] is True
    o = _ordres(client, pid)
    assert o[c1["id"]] == 2 and o[c2["id"]] == 1
    client.post(f"/api/regions/{c1['id']}/deplacer", json={"sens": "haut"})
    o = _ordres(client, pid)
    assert o[c1["id"]] == 1 and o[c2["id"]] == 2


def test_deplacer_en_bout_de_fratrie(client, planche):
    pid = planche["id"]
    c1 = _mk(client, pid); c2 = _mk(client, pid)
    assert client.post(f"/api/regions/{c1['id']}/deplacer",
                       json={"sens": "haut"}).json()["moved"] is False
    assert client.post(f"/api/regions/{c2['id']}/deplacer",
                       json={"sens": "bas"}).json()["moved"] is False


def test_deplacer_region_inexistante(client):
    assert client.post("/api/regions/999/deplacer",
                       json={"sens": "haut"}).status_code == 404


def test_deplacer_sens_invalide(client, planche):
    c1 = _mk(client, planche["id"])
    assert client.post(f"/api/regions/{c1['id']}/deplacer",
                       json={"sens": "gauche"}).status_code == 422
