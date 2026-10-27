"""UX-18 — « Tout valider » en UN geste, et un lot qui dit sur quoi il travaille.

`POST /api/albums/{id}/valider` remplace la rafale de `PATCH …/validation` que la
Bibliothèque envoyait, une par planche. Elle est la SOMME de la route unitaire : gardée
comme elle (écrire dans l'album), journalisée comme elle (un acte `validation` sous
`planches` par planche), et elle y ajoute ce qu'une rafale ne pouvait pas donner — tout, ou
rien.

`GET /api/jobs` nomme désormais les albums d'un lot. Ce qui se garde ici est que le nom ne
sorte que pour un lot qu'on voit : un lot dont une planche nous échappe reste invisible, et
son album avec lui.
"""
import sqlite3
import time

import pytest

import journal
import main
import pipeline.segmentation as seg
from conftest import du_projet
from conftest import ADMIN

LECTRICE = {"Remote-User": "lectrice"}      # lit la collection, n'y écrit pas
ECRIVAIN = {"Remote-User": "ecrivain"}      # écrit dans la collection
PERSONNE = {"Remote-User": "personne"}      # une identité, aucun accès


def _importer(client, album_id, png_bytes, n, headers=None):
    ids = []
    for i in range(n):
        r = client.post(f"/api/albums/{album_id}/import", headers=headers or {},
                        files={"file": (f"p{i}.png", png_bytes, "image/png")})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return ids


def _wait_done(client, jid, headers=None, timeout=5.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        snap = client.get(f"/api/jobs/{jid}", headers=headers or {}).json()
        if snap["status"] != "en_cours":
            return snap
        time.sleep(0.02)
    raise AssertionError(f"lot {jid} non terminé à temps")


def _validees(db_path, album_id):
    conn = sqlite3.connect(db_path)
    try:
        return dict(conn.execute("SELECT id, validee FROM planches WHERE album_id = ?",
                                 (album_id,)).fetchall())
    finally:
        conn.close()


def _actes_validation(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return [tuple(r) for r in conn.execute(
            "SELECT cible_id, agent, apres FROM evenement WHERE type = 'validation' "
            "AND cible_table = 'planches' ORDER BY id")]
    finally:
        conn.close()


# ── « Tout valider » ───────────────────────────────────────────────────────────────


def test_tout_valider_valide_ce_qui_ne_l_est_pas_et_journalise_planche_par_planche(
        client, album, png_bytes, db_path):
    p1, p2, p3 = _importer(client, album["id"], png_bytes, 3)
    # p1 validée AVANT : son horodatage et son acte unique ne doivent pas bouger.
    r = client.patch(f"/api/planches/{p1}/validation", json={"validee": True})
    assert r.status_code == 200, r.text
    avant = _validees(db_path, album["id"])[p1]
    assert len(_actes_validation(db_path)) == 1

    r = client.post(f"/api/albums/{album['id']}/valider")
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["album_id"] == album["id"]
    assert [v["id"] for v in corps["validees"]] == [p2, p3]
    assert all(v["validee"] for v in corps["validees"])
    assert corps["deja_validees"] == 1

    etat = _validees(db_path, album["id"])
    assert all(etat[p] for p in (p1, p2, p3))
    assert etat[p1] == avant, "une planche déjà validée garde sa date"
    # Un acte PAR planche nouvellement validée, sous `planches`, comme la route unitaire.
    actes = _actes_validation(db_path)
    assert [a[0] for a in actes] == [p1, p2, p3]
    assert actes[1][2] == actes[0][2] == '{"validee": true}'

    # Rejouée : rien à faire, rien d'écrit.
    r = client.post(f"/api/albums/{album['id']}/valider")
    assert r.json() == {"album_id": album["id"], "validees": [], "deja_validees": 3}
    assert len(_actes_validation(db_path)) == 3


def test_tout_valider_est_tout_ou_rien(client, album, png_bytes, db_path, monkeypatch):
    """Une panne au milieu ne laisse PAS l'album à moitié validé : c'est ce que la rafale
    de requêtes ne savait pas faire, et ce que l'écran annonce (« Aucune planche
    validée »)."""
    _importer(client, album["id"], png_bytes, 3)
    vrai = journal.journaliser
    appels = []

    def panne(conn, type_, *a, **k):
        appels.append(type_)
        if len(appels) == 2:
            raise RuntimeError("panne au milieu")
        return vrai(conn, type_, *a, **k)

    monkeypatch.setattr(journal, "journaliser", panne)
    with pytest.raises(RuntimeError):
        client.post(f"/api/albums/{album['id']}/valider")
    monkeypatch.setattr(journal, "journaliser", vrai)
    assert not any(_validees(db_path, album["id"]).values())
    assert _actes_validation(db_path) == []


def test_tout_valider_sur_un_album_inconnu_repond_404(client):
    assert client.post("/api/albums/99999/valider").status_code == 404


@pytest.fixture
def collection_partagee(client, derriere_proxy, png_bytes):
    r = client.post("/api/collections", json={"nom": "Étude V"}, headers=ADMIN)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for login, niveau in (("lectrice", "lecture"), ("ecrivain", "ecriture")):
        du_projet(client, cid, "utilisateur", login, headers=ADMIN)
        r = client.put(f"/api/collections/{cid}/acces", headers=ADMIN,
                       json={"genre": "utilisateur", "principal": login, "niveau": niveau})
        assert r.status_code == 200, r.text
    r = client.post("/api/albums", json={"titre": "Partagé", "collection_id": cid},
                    headers=ADMIN)
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    _importer(client, aid, png_bytes, 2, headers=ADMIN)
    return cid, aid


def test_tout_valider_est_garde_comme_la_route_unitaire(client, collection_partagee,
                                                        db_path):
    """Écrire dans l'album : qui ne fait que le lire reçoit le 404 de la route unitaire, et
    n'a rien validé ; qui n'en voit rien, le même 404 ; qui y écrit, valide — et l'acte est
    à son nom."""
    _, aid = collection_partagee
    pid = next(iter(_validees(db_path, aid)))
    for qui in (LECTRICE, PERSONNE):
        assert client.patch(f"/api/planches/{pid}/validation", headers=qui,
                            json={"validee": True}).status_code == 404
        assert client.post(f"/api/albums/{aid}/valider", headers=qui).status_code == 404
    assert not any(_validees(db_path, aid).values())

    r = client.post(f"/api/albums/{aid}/valider", headers=ECRIVAIN)
    assert r.status_code == 200, r.text
    assert len(r.json()["validees"]) == 2
    assert {a[1] for a in _actes_validation(db_path)} == {"ecrivain"}


def test_tout_valider_exige_la_preuve_d_origine(client, album, png_bytes):
    """SEC-2 : un POST sans `X-BD-Requete` ni `Sec-Fetch-Site` est refusé, comme toute
    écriture — un `<form>` d'un sous-domaine voisin ne valide pas un album."""
    _importer(client, album["id"], png_bytes, 1)
    nu = {main.EN_TETE_REQUETE: ""}
    r = client.post(f"/api/albums/{album['id']}/valider", headers=nu)
    assert r.status_code == 403, r.text


# ── Un lot dit sur quoi il travaille ───────────────────────────────────────────────


def test_un_lot_nomme_ses_albums_et_le_nombre_de_leurs_planches(
        client, album, png_bytes, monkeypatch):
    monkeypatch.setattr(main, "kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "segment_planche", lambda c, pid: None)
    _importer(client, album["id"], png_bytes, 2)
    autre = client.post("/api/albums", json={"titre": "Autre"}).json()
    (p_autre,) = _importer(client, autre["id"], png_bytes, 1)

    r = client.post("/api/jobs", json={"passes": ["segmenter"], "album_ids": [album["id"]],
                                       "planche_ids": [p_autre]})
    assert r.status_code == 201, r.text
    jid = r.json()["id"]
    _wait_done(client, jid)
    attendu = [{"id": album["id"], "titre": "Test", "nb_planches": 2},
               {"id": autre["id"], "titre": "Autre", "nb_planches": 1}]
    assert client.get(f"/api/jobs/{jid}").json()["albums"] == attendu
    (lot,) = [j for j in client.get("/api/jobs").json() if j["id"] == jid]
    assert lot["albums"] == attendu


def test_un_lot_ne_nomme_rien_a_qui_ne_lit_pas_toutes_ses_planches(
        client, collection_partagee, png_bytes, monkeypatch):
    """La lectrice voit le lot posé sur l'album qu'elle lit, NOMMÉ ; un lot à cheval sur un
    album qu'elle ne lit pas ne lui est pas listé — ni lui, ni le titre de l'album caché."""
    monkeypatch.setattr(main, "kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "segment_planche", lambda c, pid: None)
    _, aid = collection_partagee
    cache = client.post("/api/albums", json={"titre": "Zq caché"}, headers=ADMIN).json()
    _importer(client, cache["id"], png_bytes, 1, headers=ADMIN)

    a = client.post("/api/jobs", json={"passes": ["segmenter"], "album_ids": [aid]},
                    headers=ADMIN).json()["id"]
    _wait_done(client, a, ADMIN)
    b = client.post("/api/jobs", json={"passes": ["segmenter"],
                                       "album_ids": [aid, cache["id"]]},
                    headers=ADMIN).json()["id"]
    _wait_done(client, b, ADMIN)

    r = client.get("/api/jobs", headers=LECTRICE)
    assert r.status_code == 200
    lots = {j["id"]: j for j in r.json()}
    assert set(lots) == {a}
    assert lots[a]["albums"] == [{"id": aid, "titre": "Partagé", "nb_planches": 2}]
    assert "Zq caché" not in r.text
    assert client.get(f"/api/jobs/{b}", headers=LECTRICE).status_code == 404
    # L'administrateur, qui lit tout, voit les deux albums du second.
    assert [x["titre"] for x in client.get(f"/api/jobs/{b}", headers=ADMIN).json()["albums"]] \
        == ["Partagé", "Zq caché"]
