"""ANN-8 — une apostrophe ou un accent ne font pas deux tags.

Lu le 2026-10-12 : `socle._norm_tag` ne normalisait que la casse et les espaces, et le
libellé d'un tag est unique à l'octet. Le guide des linguistes écrit ses tags avec
l'apostrophe typographique (« c’est pluriel »), un clavier tape la droite ; un accent arrive
composé ou décomposé selon le système. Chaque variante faisait un tag de plus — donc un
compteur de plus, ce que le guide redoute en toutes lettres.

La CLÉ d'un libellé (`database.cle_tag`) les confond, et c'est par elle qu'un libellé saisi
cherche son tag : à l'annotation, au retrait, à la création directe, dans les filtres de la
Recherche et de l'Exploration. Un tag d'avant garde sa graphie et se retrouve par sa clé.

Ce fichier et `tests/js/propositions.test.js` lisent LA MÊME table, `tests/cas-tags.json` :
la règle vit en double — l'écran compare les libellés avant d'envoyer, le serveur les
résout —, et c'est la table qui dit qu'elles ne se sont pas séparées.
"""
import json
import sqlite3
from pathlib import Path

import pytest

import database
from conftest import ADMIN, ECRITURE

TABLE = json.loads((Path(__file__).parent / "cas-tags.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("cas", TABLE, ids=[c["nom"] for c in TABLE])
def test_table_partagee(cas):
    assert database.cle_tag(cas["entree"]) == cas["attendu"]


def test_la_cle_est_idempotente():
    for cas in TABLE:
        assert database.cle_tag(database.cle_tag(cas["entree"])) == cas["attendu"], cas["nom"]


def _tags(db_path):
    c = sqlite3.connect(db_path)
    try:
        return sorted(r[0] for r in c.execute("SELECT label FROM tags"))
    finally:
        c.close()


def _ancien(db_path, label):
    """Un tag d'AVANT la clé, posé sous sa graphie telle qu'elle était stockée."""
    c = sqlite3.connect(db_path)
    try:
        tid = c.execute("INSERT INTO tags (label) VALUES (?)", (label,)).lastrowid
        c.commit()
        return tid
    finally:
        c.close()


def _poser(client, rid, **corps):
    r = client.put(f"/api/regions/{rid}/annotation", json=corps, headers=ECRITURE)
    assert r.status_code == 200, r.text
    return r.json()


def _ids(annotation):
    return sorted(t["id"] for t in annotation["tags"])


def _bulles(client, planche, n):
    out = []
    for k in range(n):
        r = client.post(f"/api/planches/{planche['id']}/regions", headers=ECRITURE,
                        json={"type": "bulle", "x": 10 * k, "y": 0, "w": 9, "h": 9})
        assert r.status_code == 201, r.text
        out.append(r.json()["id"])
    return out


def test_apostrophe_typographique_et_droite_designent_le_meme_tag(client, planche, db_path):
    a, b = _bulles(client, planche, 2)
    ta = _poser(client, a, tags=["c’est pluriel"])
    tb = _poser(client, b, tags_ajoutes=["C'est  Pluriel"])
    assert _ids(ta) == _ids(tb)
    assert _tags(db_path) == ["c'est pluriel"]


def test_un_accent_decompose_designe_le_tag_compose(client, planche, db_path):
    a, b = _bulles(client, planche, 2)
    ta = _poser(client, a, tags=["récit"])
    tb = _poser(client, b, tags=["récit"])
    assert _ids(ta) == _ids(tb)
    assert _tags(db_path) == ["récit"]


def test_un_tag_d_avant_garde_sa_graphie_et_se_retrouve_par_sa_cle(client, planche, db_path):
    """Les tags créés avant la clé ne sont pas réécrits : « c’est pluriel » reste tel quel
    en base, et c'est LUI que désigne la frappe au clavier."""
    ancien = _ancien(db_path, "c’est pluriel")
    (a,) = _bulles(client, planche, 1)
    rendu = _poser(client, a, tags_ajoutes=["c'est pluriel"])
    assert _ids(rendu) == [ancien]
    assert _tags(db_path) == ["c’est pluriel"]
    # Le retirer par l'autre graphie le retire.
    rendu = _poser(client, a, tags_retires=["C'EST PLURIEL"])
    assert rendu["tags"] == []


def test_deux_tags_d_avant_de_meme_cle_n_en_attachent_qu_un(client, planche, db_path):
    """Deux variantes déjà en base : on en prend UNE, celle dont le libellé est la clé."""
    _ancien(db_path, "c’est pluriel")
    droit = _ancien(db_path, "c'est pluriel")
    (a,) = _bulles(client, planche, 1)
    assert _ids(_poser(client, a, tags=["c‘est pluriel"])) == [droit]


def test_creer_un_tag_par_son_autre_graphie_rend_celui_d_avant(client, db_path):
    ancien = _ancien(db_path, "c’est pluriel")
    r = client.post("/api/tags", json={"label": "C'est pluriel", "description": "accord"},
                    headers=ECRITURE)
    assert r.status_code in (200, 201), r.text
    assert r.json()["id"] == ancien
    assert r.json()["description"] == "accord"
    assert _tags(db_path) == ["c’est pluriel"]


def test_un_tag_neuf_nait_sous_sa_cle(client, db_path):
    r = client.post("/api/tags", json={"label": "  C’EST  Plériel "},
                    headers=ECRITURE)
    assert r.status_code in (200, 201), r.text
    assert r.json()["label"] == "c'est plériel"


def test_la_recherche_filtre_par_la_cle(client, planche, db_path):
    ancien = _ancien(db_path, "c’est pluriel")
    (a,) = _bulles(client, planche, 1)
    assert _ids(_poser(client, a, note="x", tags=["c’est pluriel"])) == [ancien]
    r = client.get("/api/recherche", params={"tags": "c'est pluriel"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert [x["region_id"] for x in r.json()["results"]] == [a]
