"""Tests unitaires du wrapper Kumiko (subprocess mocké, sans lancer Kumiko)."""
import json
import subprocess
import types
from pathlib import Path

import pytest

import database
import pipeline.segmentation as seg
from pipeline.segmentation import (KumikoError, _normalize_panel, run_kumiko,
                                   segment_planche)


def test_normalize_panel_liste():
    assert _normalize_panel([10.4, 20.6, 30, 40]) == (10, 21, 30, 40)


def test_normalize_panel_dict_xywh():
    assert _normalize_panel({"x": 1, "y": 2, "w": 3, "h": 4}) == (1, 2, 3, 4)


def test_normalize_panel_dict_coords():
    assert _normalize_panel({"coords": [5, 6, 7, 8]}) == (5, 6, 7, 8)


def test_normalize_panel_forme_invalide_leve_kumikoerror():
    with pytest.raises(KumikoError):
        _normalize_panel({"inattendu": True})
    with pytest.raises(KumikoError):
        _normalize_panel([1, 2])  # pas assez de valeurs


# ---- run_kumiko : chemins d'erreur, avec subprocess.run mocké ---- #
def _fake_run(write=None, returncode=0, stderr="", raises=None):
    def run(args, **kw):
        if raises is not None:
            raise raises
        if write is not None:
            Path(args[args.index("-o") + 1]).write_text(write, encoding="utf-8")
        return types.SimpleNamespace(returncode=returncode, stderr=stderr, stdout="")
    return run


@pytest.fixture
def kumiko_on(monkeypatch):
    monkeypatch.setattr(seg, "kumiko_available", lambda: True)


def test_run_kumiko_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(seg, "kumiko_available", lambda: False)
    with pytest.raises(KumikoError, match="introuvable"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_code_retour_non_nul(monkeypatch, kumiko_on, tmp_path):
    monkeypatch.setattr(seg.subprocess, "run", _fake_run(returncode=1, stderr="boom"))
    with pytest.raises(KumikoError, match="échoué"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_timeout(monkeypatch, kumiko_on, tmp_path):
    monkeypatch.setattr(
        seg.subprocess, "run",
        _fake_run(raises=subprocess.TimeoutExpired(cmd="kumiko", timeout=1)))
    with pytest.raises(KumikoError, match="délai"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_json_invalide(monkeypatch, kumiko_on, tmp_path):
    monkeypatch.setattr(seg.subprocess, "run", _fake_run(write="pas du json"))
    with pytest.raises(KumikoError, match="illisible"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_sans_clef_panels(monkeypatch, kumiko_on, tmp_path):
    monkeypatch.setattr(seg.subprocess, "run",
                        _fake_run(write=json.dumps([{"size": [1, 1]}])))
    with pytest.raises(KumikoError, match="panels"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_succes(monkeypatch, kumiko_on, tmp_path):
    page = [{"size": [10, 20], "panels": [[0, 0, 5, 5]]}]
    monkeypatch.setattr(seg.subprocess, "run", _fake_run(write=json.dumps(page)))
    assert run_kumiko(tmp_path / "x.png")["panels"] == [[0, 0, 5, 5]]


def test_segment_planche_inexistante(data_dir):
    conn = database.get_connection()
    try:
        with pytest.raises(ValueError):
            segment_planche(conn, 999)
    finally:
        conn.close()


# ---- préservation du travail humain à la re-segmentation ---- #
def test_reattach_orphans(data_dir):
    conn = database.get_connection()
    try:
        conn.execute("INSERT INTO albums (titre) VALUES ('A')")
        aid = conn.execute("SELECT id FROM albums").fetchone()["id"]
        conn.execute("INSERT INTO planches (album_id, numero, chemin_web, "
                     "largeur_px, hauteur_px) VALUES (?, 1, 'x.jpg', 400, 500)", (aid,))
        pid = conn.execute("SELECT id FROM planches").fetchone()["id"]
        conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h) "
                     "VALUES (?, 'case', 0, 0, 100, 100)", (pid,))
        cid = conn.execute("SELECT id FROM regions WHERE type='case'").fetchone()["id"]
        conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h, parent_id) "
                     "VALUES (?, 'bulle', 10, 10, 20, 20, NULL)", (pid,))   # dans la case
        conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h, parent_id) "
                     "VALUES (?, 'bulle', 300, 300, 20, 20, NULL)", (pid,))  # dehors
        assert seg._reattach_orphans(conn, pid) == 1
        dedans = conn.execute("SELECT parent_id FROM regions WHERE x=10").fetchone()["parent_id"]
        dehors = conn.execute("SELECT parent_id FROM regions WHERE x=300").fetchone()["parent_id"]
        assert dedans == cid and dehors is None
        conn.execute("DELETE FROM regions WHERE type='case'")
        assert seg._reattach_orphans(conn, pid) == 0          # aucune case → no-op
    finally:
        conn.close()


def test_transfer_case_annotations(data_dir):
    conn = database.get_connection()
    try:
        conn.execute("INSERT INTO albums (titre) VALUES ('A')")
        aid = conn.execute("SELECT id FROM albums").fetchone()["id"]
        conn.execute("INSERT INTO planches (album_id, numero, chemin_web, "
                     "largeur_px, hauteur_px) VALUES (?, 1, 'x.jpg', 400, 500)", (aid,))
        pid = conn.execute("SELECT id FROM planches").fetchone()["id"]

        def case(x, y, w, h):
            return conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h, source) "
                                "VALUES (?, 'case', ?, ?, ?, ?, 'kumiko')",
                                (pid, x, y, w, h)).lastrowid

        a1 = case(0, 0, 100, 100); conn.execute("INSERT INTO annotations (region_id, note) VALUES (?, 'ANN1')", (a1,))
        a2 = case(900, 900, 50, 50); conn.execute("INSERT INTO annotations (region_id, note) VALUES (?, 'ANN2')", (a2,))
        a3 = case(0, 0, 30, 30)            # pas d'annotation
        n1 = case(5, 5, 100, 100)          # nouvelle case (recouvre a1)
        olds = [{"id": a1, "x": 0, "y": 0, "w": 100, "h": 100},
                {"id": a2, "x": 900, "y": 900, "w": 50, "h": 50},   # aucune nouvelle ne recouvre
                {"id": a3, "x": 0, "y": 0, "w": 30, "h": 30}]
        news = [{"id": n1, "x": 5, "y": 5, "w": 100, "h": 100}]
        assert seg._transfer_case_annotations(conn, olds, news) == [a1]   # seul a1 transféré
        assert conn.execute("SELECT note FROM annotations WHERE region_id=?", (n1,)).fetchone()["note"] == "ANN1"
        assert conn.execute("SELECT 1 FROM annotations WHERE region_id=?", (a2,)).fetchone() is not None  # gardée (pas de cible)
        # cible déjà annotée → on ne transfère pas (UNIQUE) ; et _best_overlap sans recouvrement
        assert seg._transfer_case_annotations(
            conn, [{"id": a2, "x": 5, "y": 5, "w": 100, "h": 100}], news) == []
        assert seg._best_overlap({"x": 999, "y": 999, "w": 1, "h": 1}, news) is None
    finally:
        conn.close()


def test_resegmentation_transfere_annotation_case(client, planche, monkeypatch):
    monkeypatch.setattr("main.kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[0, 0, 400, 500]]})
    client.post(f"/api/planches/{planche['id']}/segmenter")
    case = next(x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["type"] == "case")
    client.put(f"/api/regions/{case['id']}/annotation",
               json={"note": "SCENENUIT", "tags": ["nuit"]})
    # re-segmentation : une nouvelle case recouvrant l'ancienne → annotation transférée
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[0, 0, 400, 480]]})
    res = client.post(f"/api/planches/{planche['id']}/segmenter").json()
    assert res["annotations_transferees"] == 1
    new_case = next(x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["type"] == "case")
    ann = client.get(f"/api/regions/{new_case['id']}/annotation").json()
    assert ann["note"] == "SCENENUIT" and "nuit" in [t["label"] for t in ann["tags"]]
    res2 = client.get("/api/recherche", params={"q": "nuit"}).json()["results"]
    assert any(r["region_id"] == new_case["id"] for r in res2)   # cherchable, sur la nouvelle case


def test_resegmentation_conserve_case_annotee_sans_recouvrement(client, planche, monkeypatch):
    """Une case annotée que la nouvelle segmentation NE recouvre PAS est
    CONSERVÉE (et non supprimée) : aucune perte d'annotation."""
    monkeypatch.setattr("main.kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[0, 0, 50, 50]]})
    client.post(f"/api/planches/{planche['id']}/segmenter")
    case = next(x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["type"] == "case")
    client.put(f"/api/regions/{case['id']}/annotation",
               json={"note": "ZONEORPHELINE", "tags": ["isole"]})
    # re-segmentation : la nouvelle case ne recouvre PAS l'ancienne case annotée
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[300, 400, 50, 50]]})
    res = client.post(f"/api/planches/{planche['id']}/segmenter").json()
    assert res["annotations_transferees"] == 0 and res["annotations_preservees"] == 1
    regions = client.get(f"/api/planches/{planche['id']}/regions").json()
    assert any(x["id"] == case["id"] for x in regions)          # ancienne case SURVIT
    res2 = client.get("/api/recherche", params={"q": "ZONEORPHELINE"}).json()["results"]
    assert any(r["region_id"] == case["id"] for r in res2)      # annotation cherchable, in situ


def test_resegmentation_preserve_ocr(client, planche, monkeypatch):
    monkeypatch.setattr("main.kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[0, 0, 400, 500]]})
    client.post(f"/api/planches/{planche['id']}/segmenter")
    case1 = next(x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["type"] == "case")
    bulle = client.post(f"/api/planches/{planche['id']}/regions",
                        json={"type": "bulle", "x": 50, "y": 60, "w": 80, "h": 40,
                              "parent_id": case1["id"], "ocr_texte": "DIALOGUE",
                              "source": "auto"}).json()
    # re-segmentation : 2 nouvelles cases → la bulle océrisée survit + se ré-rattache
    monkeypatch.setattr(seg, "run_kumiko", lambda path: {
        "size": [400, 500], "panels": [[0, 0, 200, 500], [200, 0, 200, 500]]})
    res = client.post(f"/api/planches/{planche['id']}/segmenter").json()
    regions = client.get(f"/api/planches/{planche['id']}/regions").json()
    surv = next((x for x in regions if x["id"] == bulle["id"]), None)
    assert surv is not None and surv["ocr_texte"] == "DIALOGUE"         # OCR préservé
    new_case = next(x for x in regions if x["type"] == "case" and x["x"] == 0)
    assert surv["parent_id"] == new_case["id"] and res["reattaches"] >= 1
