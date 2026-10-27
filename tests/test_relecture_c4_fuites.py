"""Relecture croisée COL-3 3a (t3a-c4) — `soeur` et `rejoindre_demande` sous six identités,
avec une copie sœur dans un SECOND projet. Jetable."""
import json

import pytest

from conftest import ADMIN
from test_fonds import _accorder, _collection
from test_prendre import (ECRIVAIN, LECTRICE, PROPRIO, RESP, _copie_dans,  # noqa: F401
                          prise)

AUTRE = {"Remote-User": "autre"}           # responsable de P2, propriétaire de Z
LECT2 = {"Remote-User": "lect2"}           # lit Z
ECR2 = {"Remote-User": "ecr2"}             # écrit dans Z seule
SENTINELLES = ("Collection X", "Collection Y", "Principale", "Étude P", "SENTINELLE-P1")


def _vus(client, qui):
    r = client.get("/api/albums", headers=qui)
    assert r.status_code == 200, r.text
    return {a["id"]: a for a in r.json()}


@pytest.fixture
def deux_projets(client, prise):
    # Une demande en attente dans P1 — un rejoindre de cx vers Y, motif sentinelle.
    cx = _copie_dans(client, prise, "d1", prise["x"])
    r = client.put(f"/api/albums/{cx}/collections/{prise['y']}", headers=ECRIVAIN)
    assert r.status_code == 202, r.text
    r = client.post("/api/projets", json={"nom": "P2 autre"}, headers=ADMIN)
    assert r.status_code == 201, r.text
    p2 = r.json()["id"]
    assert client.put(f"/api/projets/{p2}/membres", headers=ADMIN,
                      json={"principal": "autre", "role": "responsable"}).status_code == 200
    z = _collection(client, "Zed", projet_id=p2)
    _accorder(client, z, "autre", "proprietaire")
    _accorder(client, z, "lect2", "lecture")
    _accorder(client, z, "ecr2", "ecriture")
    cz = _copie_dans(client, prise, "d1", z)
    return {**prise, "cx": cx, "z": z, "cz": cz, "p2": p2}


@pytest.mark.parametrize("qui,soeur", [(AUTRE, True), (ECR2, True), (LECT2, False)])
def test_le_second_projet_n_apprend_rien_du_premier(client, deux_projets, qui, soeur):
    vus = _vus(client, qui)
    cz = deux_projets["cz"]
    assert set(vus) == {cz}, "le second projet ne voit que sa copie"
    a = vus[cz]
    assert a["soeur"] is soeur
    assert a["rejoindre_demande"] == []
    brut = json.dumps(list(vus.values()), ensure_ascii=False)
    for s in SENTINELLES:
        assert s not in brut, s
    assert [c["id"] for c in a["collections"]] == [deux_projets["z"]]


def test_rejoindre_demande_ne_nomme_que_ou_l_on_ecrit(client, deux_projets):
    cx, y = deux_projets["cx"], deux_projets["y"]
    assert _vus(client, ECRIVAIN)[cx]["rejoindre_demande"] == [y]
    assert _vus(client, PROPRIO)[cx]["rejoindre_demande"] == [y]
    assert _vus(client, LECTRICE)[cx]["rejoindre_demande"] == []
    assert _vus(client, LECTRICE)[cx]["soeur"] is False
    # Le responsable de P1 LIT toutes ses collections depuis la tranche 3c (F1) : il voit la
    # copie, mais n'y écrit pas — `rejoindre_demande` ne nomme rien pour lui.
    assert _vus(client, RESP)[cx]["rejoindre_demande"] == []
    # Un écrivain de Y SEULE ne lit pas cx : rien.
    _accorder(client, y, "ecry", "ecriture")
    assert cx not in _vus(client, {"Remote-User": "ecry"})
    # La sœur de P2 ne porte pas la demande de P1, même pour l'administrateur.
    admin = _vus(client, ADMIN)
    assert admin[deux_projets["cz"]]["rejoindre_demande"] == []
    assert admin[cx]["rejoindre_demande"] == [y]
    assert admin[cx]["soeur"] is True and admin[deux_projets["cz"]]["soeur"] is True
