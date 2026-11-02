"""La couverture d'un album (UX-20, Hugo, 2026-11-02) : la première planche marquée paratexte,
sinon la première planche, dérivée et sans geste. Jouée sur le JSON de `GET /api/albums`."""
import sqlite3

import database
from conftest import ADMIN, make_png


def _nouvel_album(client, titre="Album"):
    r = client.post("/api/albums", json={"titre": titre}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _planche(client, album_id):
    r = client.post(f"/api/albums/{album_id}/import",
                    files={"file": ("p.png", make_png(), "image/png")}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _marquer(client, planche_id, role="paratexte"):
    r = client.patch(f"/api/planches/{planche_id}/role", json={"role": role}, headers=ADMIN)
    assert r.status_code == 200, r.text


def _couverture(client, album_id):
    albums = client.get("/api/albums", headers=ADMIN).json()
    return next(a for a in albums if a["id"] == album_id)["couverture"]


def test_sans_paratexte_la_couverture_est_la_premiere_planche(client):
    a = _nouvel_album(client)
    p1, _p2 = _planche(client, a), _planche(client, a)
    assert _couverture(client, a) == p1


def test_un_paratexte_l_emporte_sur_ce_qui_le_precede(client):
    a = _nouvel_album(client)
    _p1, p2, _p3 = _planche(client, a), _planche(client, a), _planche(client, a)
    _marquer(client, p2)
    assert _couverture(client, a) == p2


def test_de_plusieurs_paratextes_le_premier_est_la_couverture(client):
    a = _nouvel_album(client)
    _p1, p2, p3 = _planche(client, a), _planche(client, a), _planche(client, a)
    _marquer(client, p3)
    _marquer(client, p2)
    assert _couverture(client, a) == p2


def test_l_ordre_est_celui_des_numeros_et_non_des_identifiants(client):
    a = _nouvel_album(client)
    p1, p2 = _planche(client, a), _planche(client, a)
    r = client.put(f"/api/albums/{a}/ordre-des-planches",
                   json={"ordre": [p2, p1], "vu": [p1, p2]}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert _couverture(client, a) == p2


def test_un_album_sans_planche_n_a_pas_de_couverture(client):
    a = _nouvel_album(client)
    albums = client.get("/api/albums", headers=ADMIN).json()
    album = next(x for x in albums if x["id"] == a)
    assert "couverture" in album and album["couverture"] is None


def test_retirer_la_couverture_passe_a_la_suivante(client):
    a = _nouvel_album(client)
    p1, p2 = _planche(client, a), _planche(client, a)
    _marquer(client, p1)
    assert client.delete(f"/api/planches/{p1}", headers=ADMIN).status_code == 204
    assert _couverture(client, a) == p2


def test_tout_role_autre_que_le_recit_est_un_paratexte(client, db_path):
    """Le vocabulaire des rôles est extensible (`config.ROLES_PLANCHE`)."""
    a = _nouvel_album(client)
    _p1, p2 = _planche(client, a), _planche(client, a)
    c = sqlite3.connect(db_path)
    c.execute("UPDATE planches SET role = 'liminaire' WHERE id = ?", (p2,))
    c.commit()
    c.close()
    assert _couverture(client, a) == p2


def test_la_couverture_ne_dit_aucun_chemin(client):
    a = _nouvel_album(client)
    p1 = _planche(client, a)
    assert isinstance(_couverture(client, a), int) and _couverture(client, a) == p1


def test_la_regle_est_une_sous_requete_sans_valeur_du_client():
    sql = database.sql_couverture_d_album("a")
    assert sql.startswith("(SELECT") and "?" not in sql
