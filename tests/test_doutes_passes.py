"""Le doute et la passe (ANN-7, tranche 1 ; cadrage R7, R9 ; G20 a ; Q7).

Le doute porte sur UN relevé, un seul ouvert à la fois, un fil signé ; il se lève en gardant,
en changeant ou en retirant le relevé, par quiconque écrit dans l'album. La passe est commune
et signée : marquée par l'un, elle reste ; « Rouvrir » la retire. Ni l'un ni l'autre ne
s'annule par Ctrl+Z.
"""
import sqlite3

import pytest

from grilles_decor import ANA, LEA, STAG, TP, ZOE, grille_active, monter, ok


@pytest.fixture
def decor(client, db_path, derriere_proxy):
    d = monter(client, db_path)
    d.update(grille_active(client, d["p"]))
    r = client.post("/api/releves", headers=STAG, json={
        "grille_id": d["grille_id"], "version": 1, "region_id": d["zones"]["bulle"],
        "entree_cle": "cri", "mots": [8]})
    assert r.status_code == 201, r.text
    d["releve"] = r.json()["id"]
    return d


def _q(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, p)]
    finally:
        c.close()


def _douter(client, d, qui, texte="Vraiment ?", attendu=(201,)):
    r = client.post(f"/api/releves/{d['releve']}/doutes", headers=qui, json={"texte": texte})
    assert r.status_code in attendu, (r.status_code, r.text[:400])
    return r.json()


def _lever(client, doute_id, qui, issue, attendu=(200,), **corps):
    r = client.post(f"/api/doutes/{doute_id}/levee", headers=qui,
                    json={"issue": issue, **corps})
    assert r.status_code in attendu, (r.status_code, r.text[:400])
    return r.json()


# --------------------------------------------------------------------------- #
# Le doute
# --------------------------------------------------------------------------- #
def test_un_doute_s_ouvre_avec_un_commentaire_et_un_second_s_ajoute_au_fil(client, decor,
                                                                          db_path):
    d = _douter(client, decor, STAG, "Est-ce bien un cri ?")
    assert d["ouvert_par"] == "stag" and [m["texte"] for m in d["messages"]] == [
        "Est-ce bien un cri ?"]
    d2 = _douter(client, decor, LEA, "Je crois.")
    assert d2["id"] == d["id"] and len(d2["messages"]) == 2
    assert _q(db_path, "SELECT COUNT(*) AS n FROM doute")[0]["n"] == 1
    _douter(client, decor, STAG, "   ", attendu=(422,))
    types = [e["type"] for e in _q(db_path, "SELECT type FROM evenement WHERE "
                                            "cible_table = 'releve' ORDER BY id")]
    assert types == ["creation", "doute", "doute_reponse"]


def test_douter_demande_d_ecrire_dans_l_album(client, decor):
    """G20 a : douter, répondre, lever — qui ÉCRIT dans l'album, pas un simple lecteur."""
    _douter(client, decor, ANA, attendu=(404,))
    _douter(client, decor, ZOE, attendu=(404,))
    d = _douter(client, decor, STAG)
    ok(client.post(f"/api/doutes/{d['id']}/messages", headers=ANA, json={"texte": "x"}), 404)
    _lever(client, d["id"], ANA, "garde", attendu=(404,))


def test_un_compte_partage_signe_ses_messages_comme_tel(client, decor):
    d = _douter(client, decor, STAG)
    d = ok(client.post(f"/api/doutes/{d['id']}/messages", headers=TP,
                       json={"texte": "Nous, on garde."}), 201)
    assert [m["collectif"] for m in d["messages"]] == [False, True]
    assert d["messages"][0]["auteur_nom"] == "Stagiaire Une"


def test_lever_en_gardant_puis_un_autre_ne_releve_pas_autrement(client, decor):
    d = _douter(client, decor, STAG)
    leve = _lever(client, d["id"], TP, "garde", vu={"doute": "ouvert"})
    assert leve["issue"] == "garde" and leve["leve_par"] == "groupe-tp"
    refus = _lever(client, d["id"], STAG, "retire", attendu=(409,),
                   vu={"doute": "ouvert"})["detail"]
    assert refus["conflit"]["champ"] == "doute"
    assert refus["conflit"]["auteur"]["login"] == "groupe-tp"
    # La même issue passe, sans rien écrire.
    assert _lever(client, d["id"], STAG, "garde")["leve_par"] == "groupe-tp"
    # On ne répond plus à un doute levé ; on en ouvre un autre.
    ok(client.post(f"/api/doutes/{d['id']}/messages", headers=STAG, json={"texte": "x"}), 409)
    assert _douter(client, decor, STAG)["id"] != d["id"]


def test_lever_en_retirant_retire_le_releve(client, decor, db_path):
    d = _douter(client, decor, STAG)
    leve = _lever(client, d["id"], LEA, "retire")
    assert leve["releve_retire"] is True
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0
    types = [e["type"] for e in _q(db_path, "SELECT type FROM evenement WHERE "
                                            "cible_table = 'releve' ORDER BY id")]
    assert types[-2:] == ["doute_levee", "suppression"]


def test_une_issue_inconnue_est_refusee(client, decor):
    d = _douter(client, decor, STAG)
    _lever(client, d["id"], STAG, "oublie", attendu=(422,))


def test_un_doute_sur_une_grille_desactivee_est_refuse(client, decor):
    ok(client.delete(f"/api/projets/{decor['p']}/grilles/{decor['grille_id']}/activation",
                     headers=LEA), 204)
    _douter(client, decor, STAG, attendu=(409,))


def test_la_planche_rend_le_doute_ouvert_et_son_fil(client, decor):
    d = _douter(client, decor, STAG, "Hmm")
    lus = ok(client.get(f"/api/planches/{decor['planche']}/releves", headers=ANA))
    (x,) = lus["releves"]
    assert x["doute"]["id"] == d["id"] and x["doute"]["messages"][0]["texte"] == "Hmm"
    _lever(client, d["id"], STAG, "garde")
    lus = ok(client.get(f"/api/planches/{decor['planche']}/releves", headers=ANA))
    assert lus["releves"][0]["doute"] is None


# --------------------------------------------------------------------------- #
# La passe
# --------------------------------------------------------------------------- #
def _marquer(client, d, qui, attendu=(200,), zone="region", **corps):
    url = (f"/api/regions/{d['zones']['bulle']}/passes/{d['grille_id']}" if zone == "region"
           else f"/api/planches/{d['planche']}/passes/{d['grille_id']}")
    r = client.put(url, headers=qui, json=corps)
    assert r.status_code in attendu, (r.status_code, r.text[:400])
    return r.json()


def test_une_passe_est_commune_et_signee(client, decor, db_path):
    p = _marquer(client, decor, STAG)
    assert p["par"] == "stag" and p["rubrique_cle"] == "" and p["par_nom"] == "Stagiaire Une"
    # Marquée par un autre : elle reste, signée de la première.
    assert _marquer(client, decor, LEA)["par"] == "stag"
    assert _q(db_path, "SELECT COUNT(*) AS n FROM passe")[0]["n"] == 1
    # Une rubrique a sa passe à elle ; une rubrique inconnue est refusée.
    assert _marquer(client, decor, LEA, rubrique_cle="sons")["rubrique_cle"] == "sons"
    _marquer(client, decor, LEA, attendu=(422,), rubrique_cle="nulle")
    types = [e["type"] for e in _q(db_path, "SELECT type FROM evenement WHERE "
                                            "cible_table = 'releve' AND type LIKE 'passe%'")]
    assert types == ["passe", "passe"]


def test_rouvrir_une_passe(client, decor, db_path):
    _marquer(client, decor, STAG)
    url = f"/api/regions/{decor['zones']['bulle']}/passes/{decor['grille_id']}"
    # L'écran l'avait vue NON marquée, et quelqu'un l'a marquée depuis : 409 qui le nomme.
    r = client.delete(url + "?vu_marquee=false", headers=LEA)
    assert r.status_code == 409 and r.json()["detail"]["conflit"]["auteur"]["login"] == "stag"
    ok(client.delete(url, headers=LEA), 204)
    assert _q(db_path, "SELECT COUNT(*) AS n FROM passe")[0]["n"] == 0
    ok(client.delete(url, headers=LEA), 204)                    # déjà rouverte : rien
    assert _q(db_path, "SELECT type FROM evenement WHERE cible_table = 'releve' "
                       "ORDER BY id DESC LIMIT 1")[0]["type"] == "passe_rouverte"


def test_la_passe_de_la_planche_et_ses_gardes(client, decor, db_path):
    p = _marquer(client, decor, STAG, zone="planche")
    assert p["planche_id"] == decor["planche"] and p["region_id"] is None
    _marquer(client, decor, ANA, attendu=(404,), zone="planche")
    _marquer(client, decor, ANA, attendu=(404,))
    ok(client.delete(f"/api/projets/{decor['p']}/grilles/{decor['grille_id']}/activation",
                     headers=LEA), 204)
    _marquer(client, decor, STAG, attendu=(409,))
    assert _q(db_path, "SELECT type FROM evenement WHERE cible_table = 'releve_planche'")[0][
        "type"] == "passe"


def test_la_planche_rend_ses_passes(client, decor):
    _marquer(client, decor, STAG)
    _marquer(client, decor, TP, zone="planche")
    lus = ok(client.get(f"/api/planches/{decor['planche']}/releves", headers=ANA))
    assert [(p["par"], p["collectif"]) for p in lus["passes"]] == [("stag", False),
                                                                   ("groupe-tp", True)]
