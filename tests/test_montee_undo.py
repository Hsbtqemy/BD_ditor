"""Ctrl+Z après une MONTÉE DE VERSION (ANN-7 ; cadrage `docs/ann7-montee-de-version-cadrage.md`,
§7 et §9, commit 4).

La montée elle-même ne s'annule pas (M5) : un acte sous `grille`, hors de la pile. Ce qui
s'annule, ce sont les gestes d'AVANT elle, et ils lisent la version que la montée a changée :

- défaire une pose ou une retouche lit le relevé ACTUEL, passé dans la nouvelle version : il
  se défait — sauf quand la valeur qu'il rendrait n'existe plus dans cette version (passé) ;
- rendre un relevé retiré, ou ceux qu'emportait la suppression d'une région, lit l'instantané,
  dans l'ANCIENNE version : il se rend dans la version active s'il y convient
  (`grilles.convient`), et l'acte est passé sinon ; une passe se rend si la montée ne l'aurait
  pas rouverte ;
- une FUSION faite à la montée a changé l'entrée du relevé : défaire sa pose ne le retire pas
  sans rien dire — le 409 de CONC-3 nomme la fusion, et « Passer ce geste » le franchit.
"""
import copy
import sqlite3

import pytest

from grilles_decor import LEA, STAG, ok
from test_montee import _e, apercu, monter, publier_v2
from test_releves import bulle, decor, poser  # noqa: F401
from test_releves_undo import undo

pytestmark = pytest.mark.usefixtures("sans_grille_de_travail")


def _q(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, p)]
    finally:
        c.close()


def _v2_id(db_path):
    return _q(db_path, "SELECT id FROM grille_version WHERE numero = 2")[0]["id"]


def _monter(client, d, reponses=None):
    a = apercu(client, d)
    monter(client, d, vu=a["vu"], reponses=reponses)


def test_un_releve_retire_avant_la_montee_se_rend_dans_la_version_active(client, decor,
                                                                        db_path):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[0])
    poser(client, decor, region_id=decor["zones"]["texte"], entree_cle="cri", mots=[0])
    ok(client.delete(f"/api/releves/{r['id']}", headers=STAG), 204)
    publier_v2(db_path, decor, lambda c: _e(c, "cri").update(libelle="cri poussé"))
    _monter(client, decor)
    undo(client)
    (x,) = _q(db_path, "SELECT * FROM releve WHERE id = ?", (r["id"],))
    assert x["version_id"] == _v2_id(db_path) and x["entree_cle"] == "cri"


def test_un_releve_qui_ne_convient_plus_a_la_version_active_ne_se_rend_pas(client, decor,
                                                                          db_path):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="onomatopee",
              variante_cle="bang", mots=[8])
    poser(client, decor, region_id=decor["zones"]["texte"], entree_cle="cri", mots=[0])
    ok(client.delete(f"/api/releves/{r['id']}", headers=STAG), 204)
    publier_v2(db_path, decor, lambda c: _e(c, "onomatopee")["variantes"].pop("bang"))
    _monter(client, decor)
    refus = undo(client, attendu=(409,))["detail"]
    assert "ne peut plus être rétabli" in refus["message"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve WHERE id = ?", (r["id"],))[0]["n"] == 0


def test_une_region_rendue_apres_la_montee_rend_ce_qui_convient(client, decor, db_path):
    b = bulle(decor)
    garde = poser(client, decor, region_id=b, entree_cle="cri", mots=[0])
    perdu = poser(client, decor, region_id=b, entree_cle="onomatopee", variante_cle="bang",
                  mots=[8])
    ok(client.put(f"/api/regions/{b}/passes/{decor['grille_id']}", headers=STAG,
                  json={"rubrique_cle": "provenance"}))
    ok(client.put(f"/api/regions/{b}/passes/{decor['grille_id']}", headers=STAG,
                  json={"rubrique_cle": ""}))
    poser(client, decor, region_id=decor["zones"]["texte"], entree_cle="cri", mots=[0])
    ok(client.delete(f"/api/regions/{b}", headers=STAG), 204)

    def v2(c):
        _e(c, "onomatopee")["variantes"].pop("bang")
        neuve = copy.deepcopy(_e(c, "cri"))
        neuve["libelle"] = "soupir"
        c["entrees"]["soupir"] = neuve           # rouvrirait la passe de toute la grille
    publier_v2(db_path, decor, v2)
    _monter(client, decor)
    res = undo(client)
    # Le cri revient en v2 ; la variante disparue et la passe qu'une entrée neuve rouvrirait
    # ne reviennent pas — comptées.
    assert res["releves_non_rendus"] == 2
    rendus = _q(db_path, "SELECT id, version_id FROM releve WHERE region_id = ?", (b,))
    assert rendus == [{"id": garde["id"], "version_id": _v2_id(db_path)}]
    assert perdu["id"] not in [x["id"] for x in rendus]
    assert _q(db_path, "SELECT rubrique_cle, version_id FROM passe WHERE region_id = ?",
              (b,)) == [{"rubrique_cle": "provenance", "version_id": _v2_id(db_path)}]


def test_defaire_une_retouche_dont_la_valeur_a_disparu_est_passe(client, decor, db_path):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="onomatopee",
              variante_cle="bang", mots=[8])
    ok(client.put(f"/api/releves/{r['id']}", headers=STAG, json={"variante_cle": "crac"}))
    publier_v2(db_path, decor, lambda c: _e(c, "onomatopee")["variantes"].pop("bang"))
    _monter(client, decor)
    refus = undo(client, attendu=(409,))["detail"]
    assert "ne peut plus être rétabli" in refus["message"]
    (x,) = _q(db_path, "SELECT variante_cle, version_id FROM releve")
    assert (x["variante_cle"], x["version_id"]) == ("crac", _v2_id(db_path))
    # Le geste d'avant — la pose — se défait encore : le relevé est passé dans la v2.
    assert ok(client.get("/api/undo/prochain", headers=STAG))["description"] == \
        "pose d'un relevé"


def test_defaire_une_retouche_apres_la_montee_la_defait(client, decor, db_path):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="onomatopee",
              variante_cle="bang", mots=[8])
    ok(client.put(f"/api/releves/{r['id']}", headers=STAG, json={"variante_cle": "crac"}))
    publier_v2(db_path, decor, lambda c: _e(c, "onomatopee")["variantes"].pop("splash"))
    _monter(client, decor)
    undo(client)
    assert _q(db_path, "SELECT variante_cle FROM releve")[0]["variante_cle"] == "bang"


def test_defaire_la_pose_d_un_releve_fusionne_a_la_montee_nomme_la_fusion(client, decor,
                                                                         db_path):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="echo", mots=[0],
              qualificatifs=["objet"])
    publier_v2(db_path, decor, lambda c: _e(c, "echo").update(retiree=True))
    _monter(client, decor, {"echo": "fusionner:origine-du-son"})
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "entree_cle"
    assert refus["conflit"]["auteur"]["login"] == "lea"
    ok(client.post("/api/undo/passer", headers=STAG,
                   json={"evenement_id": refus["passable"]["evenement_id"]}))
    (x,) = _q(db_path, "SELECT id, entree_cle FROM releve")
    assert (x["id"], x["entree_cle"]) == (r["id"], "origine-du-son")


def test_la_montee_ne_s_annule_pas(client, decor, db_path):
    poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[0], qui=LEA)
    publier_v2(db_path, decor, lambda c: None)
    _monter(client, decor)
    # Le prochain geste de Léa est sa pose, pas la montée.
    assert ok(client.get("/api/undo/prochain", headers=LEA))["description"] == \
        "pose d'un relevé"
