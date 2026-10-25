"""Ctrl+Z et les relevés (ANN-7, tranche 1 ; cadrage R10).

Ctrl+Z défait poser, modifier, retirer un relevé ; une suppression de région rend ses relevés
et ses passes. Les gardes sont celles des autres tables : hors de portée → passé (première
phrase) ; grille désactivée ou entrée disparue → passé (seconde phrase) ; valeur changée
depuis par un autre → le 409 de CONC-3, que « Passer ce geste » franchit. Un doute, une passe,
ne s'annulent pas : Ctrl+Z les saute.
"""
import sqlite3

import pytest

from grilles_decor import LEA, STAG, grille_active, monter, ok


@pytest.fixture
def decor(client, db_path, derriere_proxy):
    d = monter(client, db_path)
    d.update(grille_active(client, d["p"]))
    return d


def _q(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, p)]
    finally:
        c.close()


def poser(client, d, qui=STAG, **champs):
    r = client.post("/api/releves", headers=qui,
                    json={"grille_id": d["grille_id"], "version": 1, **champs})
    assert r.status_code == 201, r.text
    return r.json()


def undo(client, qui=STAG, attendu=(200,)):
    r = client.post("/api/undo", headers=qui)
    assert r.status_code in attendu, (r.status_code, r.text[:500])
    return r.json()


def test_ctrl_z_defait_une_pose(client, decor, db_path):
    poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    assert ok(client.get("/api/undo/prochain", headers=STAG))["description"] == \
        "pose d'un relevé"
    res = undo(client)
    assert res["cible_table"] == "releve" and res["region_id"] == decor["zones"]["bulle"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0


def test_ctrl_z_defait_une_pose_de_surface(client, decor, db_path):
    poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    res = undo(client)
    assert res["planche_id"] == decor["planche"] and res["region_id"] is None
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0


def test_ctrl_z_d_un_releve_de_surface_demande_d_ecrire_sa_planche(client, decor, db_path):
    """Les lieux d'un acte `releve_planche` sont sa PLANCHE, pas une région du même numéro :
    c'est elle que la route éprouve en écriture sous la portée de la requête."""
    import undo
    poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    e = _q(db_path, "SELECT * FROM evenement WHERE cible_table = 'releve_planche' "
                    "ORDER BY id DESC LIMIT 1")[0]
    assert undo.lieux(None, e) == {"regions": [], "planches": [decor["planche"]],
                                   "personnages": []}


def test_ctrl_z_defait_une_modification_et_seulement_elle(client, decor, db_path):
    r = poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="origine-du-son",
              mots=[1], qualificatifs=["objet"])
    ok(client.put(f"/api/releves/{r['id']}", headers=STAG,
                  json={"qualificatifs": ["personnage"], "precision": "ici"}))
    undo(client)
    x = _q(db_path, "SELECT precision FROM releve")[0]
    assert x["precision"] is None
    assert [q["qualificatif_cle"] for q in _q(db_path, "SELECT qualificatif_cle FROM "
                                                     "releve_qualificatif")] == ["objet"]


def test_ctrl_z_rend_un_releve_retire_sous_son_identifiant_avec_son_doute(client, decor,
                                                                         db_path):
    r = poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[7, 5])
    ok(client.post(f"/api/releves/{r['id']}/doutes", headers=LEA, json={"texte": "Sûr ?"}),
       201)
    ok(client.delete(f"/api/releves/{r['id']}", headers=STAG), 204)
    undo(client)
    lus = ok(client.get(f"/api/planches/{decor['planche']}/releves", headers=LEA))["releves"]
    (x,) = lus
    assert x["id"] == r["id"] and [m["forme"] for m in x["mots"]] == ["NE", "PAS"]
    assert x["doute"]["messages"][0]["texte"] == "Sûr ?"


def test_un_doute_et_une_passe_ne_s_annulent_pas(client, decor, db_path):
    r = poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    ok(client.put(f"/api/regions/{decor['zones']['bulle']}/passes/{decor['grille_id']}",
                  headers=STAG, json={}))
    # Ctrl+Z saute la passe et défait la pose.
    assert ok(client.get("/api/undo/prochain", headers=STAG))["description"] == \
        "pose d'un relevé"
    assert r


def test_ctrl_z_ne_defait_pas_une_pose_qu_un_autre_a_changee(client, decor, db_path):
    r = poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="onomatopee",
              mots=[8], variante_cle="bang")
    ok(client.put(f"/api/releves/{r['id']}", headers=LEA, json={"variante_cle": "crac"}))
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "variante_cle"
    assert refus["conflit"]["auteur"]["login"] == "lea"
    assert refus["passable"]["evenement_id"]
    # « Passer ce geste » : l'acte sort de la pile, le relevé reste.
    ok(client.post("/api/undo/passer", headers=STAG,
                   json={"evenement_id": refus["passable"]["evenement_id"]}))
    assert _q(db_path, "SELECT variante_cle FROM releve")[0]["variante_cle"] == "crac"


def test_ctrl_z_ne_defait_pas_une_pose_sur_laquelle_un_autre_a_doute(client, decor):
    r = poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    ok(client.post(f"/api/releves/{r['id']}/doutes", headers=LEA, json={"texte": "?"}), 201)
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "doute"


def test_grille_desactivee_l_acte_est_passe(client, decor, db_path):
    poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    ok(client.delete(f"/api/projets/{decor['p']}/grilles/{decor['grille_id']}/activation",
                     headers=LEA), 204)
    refus = undo(client, attendu=(409,))["detail"]
    assert "ne peut plus être rétabli" in refus["message"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 1
    assert _q(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE type = 'abandon'")[0][
        "n"] == 1


def test_hors_de_portee_l_acte_est_passe(client, decor, db_path):
    poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    ok(client.delete(f"/api/collections/{decor['c']}/acces/utilisateur/stag", headers=LEA), 204)
    ok(client.put(f"/api/collections/{decor['c2']}/acces", headers=LEA,
                  json={"genre": "utilisateur", "principal": "stag", "niveau": "ecriture"}))
    refus = undo(client, attendu=(409,))["detail"]
    assert "n'est plus à votre portée" in refus["message"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 1


def test_une_region_rendue_rend_ses_releves_et_ses_passes(client, decor, db_path):
    b = decor["zones"]["bulle"]
    r = poser(client, decor, region_id=b, entree_cle="cri", mots=[8])
    ok(client.put(f"/api/regions/{b}/passes/{decor['grille_id']}", headers=STAG, json={}))
    ok(client.delete(f"/api/regions/{b}", headers=STAG), 204)
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0
    res = undo(client)
    assert "releves_non_rendus" not in res
    assert [x["id"] for x in _q(db_path, "SELECT id FROM releve")] == [r["id"]]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM passe")[0]["n"] == 1


def test_une_region_rendue_ne_rend_pas_les_releves_d_une_grille_desactivee(client, decor,
                                                                         db_path):
    b = decor["zones"]["bulle"]
    poser(client, decor, region_id=b, entree_cle="cri", mots=[8])
    ok(client.delete(f"/api/regions/{b}", headers=STAG), 204)
    ok(client.delete(f"/api/projets/{decor['p']}/grilles/{decor['grille_id']}/activation",
                     headers=LEA), 204)
    res = undo(client)
    assert res["releves_non_rendus"] == 1
    assert _q(db_path, "SELECT COUNT(*) AS n FROM regions WHERE id = ?", (b,))[0]["n"] == 1
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0


def test_un_lien_perdu_puis_rendu_redevient_normal(client, decor):
    """Le relevé dont la région LIÉE disparaît n'est pas touché ; Ctrl+Z de cette suppression
    le rattache sans rien écrire."""
    r = poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="reponse-a",
              lien_region_id=decor["autre_bulle"])
    ok(client.delete(f"/api/regions/{decor['autre_bulle']}", headers=STAG), 204)
    undo(client)
    lus = ok(client.get(f"/api/planches/{decor['planche']}/releves", headers=LEA))["releves"]
    assert next(x for x in lus if x["id"] == r["id"])["etat"] == "normal"


def test_ctrl_z_ne_defait_pas_une_modification_qu_un_autre_a_recouverte(client, decor,
                                                                        db_path):
    r = poser(client, decor, qui=LEA, region_id=decor["zones"]["bulle"],
              entree_cle="onomatopee", mots=[8], variante_cle="bang")
    ok(client.put(f"/api/releves/{r['id']}", headers=STAG, json={"variante_cle": "crac"}))
    ok(client.put(f"/api/releves/{r['id']}", headers=LEA, json={"variante_cle": "splash"}))
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "variante_cle"
    assert _q(db_path, "SELECT variante_cle FROM releve")[0]["variante_cle"] == "splash"
