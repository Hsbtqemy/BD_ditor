"""Gestion de corpus : CRUD albums/planches, migration, jobs par lot."""
import sqlite3
import threading
import time

import database
import main
import pipeline.bulles as bul
import pipeline.ocr as ocrm
import pipeline.segmentation as seg


def _wait_done(client, jid, timeout=5.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        snap = client.get(f"/api/jobs/{jid}").json()
        if snap["status"] != "en_cours":
            return snap
        time.sleep(0.02)
    raise AssertionError(f"job {jid} non terminé à temps")


def _second_planche(client, album, png_bytes):
    return client.post(f"/api/albums/{album['id']}/import",
                       files={"file": ("b.png", png_bytes, "image/png")}).json()


def test_corpus_page_servie(client):
    r = client.get("/corpus")
    assert r.status_code == 200 and "Biblioth" in r.text


# ------------------------------ Migration ------------------------------- #
def test_migration_ajoute_description(tmp_path):
    db = tmp_path / "old.sqlite"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE albums (id INTEGER PRIMARY KEY, titre TEXT)")  # v1
    database._migrate(conn)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(albums)")}
    assert "description" in cols
    conn.close()


# --------------------------- CRUD albums -------------------------------- #
def test_album_create_avec_description(client):
    a = client.post("/api/albums", json={"titre": "T", "description": "un récit"}).json()
    assert a["description"] == "un récit"


def test_album_update(client, album):
    u = client.put(f"/api/albums/{album['id']}",
                   json={"serie": "S", "annee": 2020, "description": "d"}).json()
    assert u["serie"] == "S" and u["annee"] == 2020 and u["description"] == "d"
    assert u["titre"] == album["titre"]                      # champ non touché inchangé
    assert client.put(f"/api/albums/{album['id']}", json={}).status_code == 200  # vide
    assert client.put("/api/albums/9999", json={"titre": "x"}).status_code == 404


def test_album_delete_cascade(client, planche):
    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5, "ocr_texte": "x"})
    aid = planche["album_id"]
    assert client.delete(f"/api/albums/{aid}").status_code == 204
    assert client.get(f"/api/albums/{aid}/planches").status_code == 404
    assert client.delete("/api/albums/9999").status_code == 404


def test_planche_delete(client, planche):
    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5, "ocr_texte": "x"})
    assert client.delete(f"/api/planches/{planche['id']}").status_code == 204
    assert client.get(f"/api/planches/{planche['id']}/regions").status_code == 404
    assert client.delete("/api/planches/9999").status_code == 404


# ------------------------------- Jobs ----------------------------------- #
def test_job_multi_albums(client, album, planche, png_bytes, monkeypatch):
    p2 = _second_planche(client, album, png_bytes)
    a2 = client.post("/api/albums", json={"titre": "A2"}).json()
    p3 = client.post(f"/api/albums/{a2['id']}/import",
                     files={"file": ("c.png", png_bytes, "image/png")}).json()
    monkeypatch.setattr(main, "kumiko_available", lambda: True)
    calls = []
    monkeypatch.setattr(seg, "segment_planche", lambda c, pid: calls.append(pid))

    r = client.post("/api/jobs", json={"passes": ["segmenter"],
                                       "album_ids": [album["id"], a2["id"]]})
    assert r.status_code == 201 and r.json()["total"] == 3
    snap = _wait_done(client, r.json()["id"])
    assert snap["status"] == "termine" and snap["done"] == 3 and snap["errors"] == []
    assert sorted(calls) == sorted([planche["id"], p2["id"], p3["id"]])


def test_job_trois_passes_ordre_canonique(client, planche, monkeypatch):
    for fn in ("kumiko_available", "bulles_available", "ocr_available"):
        monkeypatch.setattr(main, fn, lambda: True)
    calls = []
    monkeypatch.setattr(seg, "segment_planche", lambda c, pid: calls.append("seg"))
    monkeypatch.setattr(bul, "detect_bulles", lambda c, pid: calls.append("bul"))
    monkeypatch.setattr(ocrm, "ocr_planche", lambda c, pid: calls.append("ocr"))
    # envoyées dans le désordre → exécutées seg, bul, ocr
    r = client.post("/api/jobs", json={"passes": ["ocr", "segmenter", "bulles"],
                                       "planche_ids": [planche["id"]]})
    snap = _wait_done(client, r.json()["id"])
    assert snap["status"] == "termine" and snap["done"] == 1
    assert calls == ["seg", "bul", "ocr"]


def test_job_erreur_collectee(client, planche, monkeypatch):
    monkeypatch.setattr(main, "kumiko_available", lambda: True)

    def boom(conn, pid):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(seg, "segment_planche", boom)
    r = client.post("/api/jobs", json={"passes": ["segmenter"],
                                       "planche_ids": [planche["id"]]})
    snap = _wait_done(client, r.json()["id"])
    assert snap["status"] == "termine" and snap["done"] == 1
    assert len(snap["errors"]) == 1 and snap["errors"][0]["passe"] == "segmenter"


def test_job_annulation_saute_le_reste(client, album, planche, png_bytes, monkeypatch):
    _second_planche(client, album, png_bytes)             # 2 planches
    monkeypatch.setattr(main, "kumiko_available", lambda: True)
    monkeypatch.setattr(main, "bulles_available", lambda: True)
    gate = threading.Event()
    seg_calls, bul_calls = [], []
    monkeypatch.setattr(seg, "segment_planche",
                        lambda c, pid: (seg_calls.append(pid), gate.wait(timeout=2)))
    monkeypatch.setattr(bul, "detect_bulles", lambda c, pid: bul_calls.append(pid))

    r = client.post("/api/jobs", json={"passes": ["segmenter", "bulles"],
                                       "album_ids": [album["id"]]})
    jid = r.json()["id"]
    t0 = time.monotonic()
    while not seg_calls and time.monotonic() - t0 < 2:     # attendre le worker dans la 1re passe
        time.sleep(0.01)
    assert seg_calls
    assert client.post(f"/api/jobs/{jid}/annuler").status_code == 200
    gate.set()
    snap = _wait_done(client, jid)
    assert snap["status"] == "annule" and snap["done"] < snap["total"]
    assert bul_calls == []                                 # passe bulles sautée


def test_job_annuler_termine_ne_change_rien(client, planche, monkeypatch):
    monkeypatch.setattr(main, "kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "segment_planche", lambda c, pid: None)
    r = client.post("/api/jobs", json={"passes": ["segmenter"],
                                       "planche_ids": [planche["id"]]})
    jid = r.json()["id"]
    _wait_done(client, jid)
    # annuler un job déjà terminé : 200, statut inchangé
    assert client.post(f"/api/jobs/{jid}/annuler").json()["status"] == "termine"


def test_job_passe_invalide_422(client, planche):
    assert client.post("/api/jobs", json={"passes": ["zzz"],
                                          "planche_ids": [planche["id"]]}).status_code == 422


def test_job_moteur_indisponible_503(client, planche, monkeypatch):
    monkeypatch.setattr(main, "kumiko_available", lambda: False)
    assert client.post("/api/jobs", json={"passes": ["segmenter"],
                                          "planche_ids": [planche["id"]]}).status_code == 503


def test_job_aucune_planche_422(client, monkeypatch):
    monkeypatch.setattr(main, "kumiko_available", lambda: True)
    assert client.post("/api/jobs", json={"passes": ["segmenter"],
                                          "album_ids": [9999]}).status_code == 422


def test_job_etat_et_liste(client, planche, monkeypatch):
    monkeypatch.setattr(main, "kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "segment_planche", lambda c, pid: None)
    r = client.post("/api/jobs", json={"passes": ["segmenter"],
                                       "planche_ids": [planche["id"]]})
    jid = r.json()["id"]
    _wait_done(client, jid)
    assert any(j["id"] == jid for j in client.get("/api/jobs").json())
    assert client.get("/api/jobs/9999").status_code == 404
    assert client.post("/api/jobs/9999/annuler").status_code == 404
