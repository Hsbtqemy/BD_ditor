"""ANN-8 — le miroir du locuteur : une région qui change de type perd ce que son nouveau type
ne montre pas, et UN Ctrl+Z le rend.

Décision de Hugo du 2026-10-21 (« c'est utile »). Une case devenue bulle gardait sa
situation (`region_attribut`), une boîte personnage devenue bulle son personnage montré
(`personnage_presence`) : ni l'un ni l'autre ne se voit sur une bulle, et tous deux
comptaient encore ailleurs. Le patron est celui du locuteur (`tests/test_undo.py`) :

1. **Seulement sur un VRAI changement de type**, et dans le MÊME acte : son `avant` porte
   `presence` et `attributs` — des IDENTIFIANTS —, aucun `delien` à part.
2. **Un seul Ctrl+Z rend tout**, par la porte des liens d'une suppression.
3. **L'annulation est GARDÉE** : 409 nommé si un autre a changé ces liens depuis, rien
   d'écrit (CONC-3). La situation, un ensemble, revient par différence, comme les tags.
4. **L'annulation ne repose pas un lien sur un type qui ne le montre pas.**
5. **L'écran le dit** : la réponse nomme le personnage montré, compte la situation.
"""
import json
import sqlite3

import undo
from conftest import ADMIN
from test_undo_liens import _liens, _ok, _perso, _region, _sql, _valeur

ALICE = {"Remote-User": "alice", "Remote-Groups": "bd-admins"}
BOB = {"Remote-User": "bob", "Remote-Groups": "bd-admins"}


def _type(db_path, rid):
    return _sql(db_path, "SELECT type FROM regions WHERE id = ?", (rid,))[0]["type"]


def _dernier_acte(db_path, rid):
    return _sql(db_path, "SELECT * FROM evenement WHERE cible_table = 'regions' "
                         "AND type = 'modification' AND cible_id = ? "
                         "ORDER BY id DESC LIMIT 1", (rid,))[0]


def _n(db_path, sql):
    return _sql(db_path, sql)[0]["n"]


def _case_situee(client, planche, headers=ADMIN):
    rid = _region(client, planche["id"], headers=ADMIN)
    lieu = _valeur(client, "case", "lieu", "falaise")
    _ok(client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": lieu},
                   headers=headers), 200)
    return rid, lieu


def _boite_montrant(client, planche, nom="Milou", headers=ADMIN):
    rid = _region(client, planche["id"], type="personnage")
    p = _perso(client, nom)
    _ok(client.put(f"/api/regions/{rid}/personnage", json={"personnage_id": p},
                   headers=headers), 200)
    return rid, p


# --------------------------------------------------------------------------- #
# Le retrait, dans l'acte
# --------------------------------------------------------------------------- #
def test_une_case_devenue_bulle_perd_sa_situation_dans_le_meme_acte(client, planche, db_path):
    rid, lieu = _case_situee(client, planche)
    rep = _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ADMIN), 200)
    assert rep.json()["situation_retiree"] == 1
    assert "locuteur_retire" not in rep.json() and "presence_retiree" not in rep.json()
    assert _liens(db_path, rid)["attributs"] == []
    avant = json.loads(_dernier_acte(db_path, rid)["avant"])
    assert avant["attributs"] == [lieu]
    assert avant["liens_vus"] == {"locuteur": None, "presence": None, "attributs": [lieu]}
    assert "attributs" not in json.loads(_dernier_acte(db_path, rid)["apres"])
    assert _n(db_path, "SELECT COUNT(*) n FROM evenement WHERE type = 'delien'") == 0


def test_une_boite_personnage_devenue_bulle_perd_son_personnage_montre(client, planche, db_path):
    rid, milou = _boite_montrant(client, planche)
    rep = _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ADMIN), 200)
    assert rep.json()["presence_retiree"] == {"id": milou, "nom": "Milou", "serie": None}
    assert _liens(db_path, rid)["presence"] is None
    assert json.loads(_dernier_acte(db_path, rid)["avant"])["presence"] == milou
    assert client.get(f"/api/regions/{rid}/personnage", headers=ADMIN).json()["personnage"] is None


def test_la_regle_vaut_pour_tout_type_qui_ne_montre_pas(client, planche, db_path):
    """« Ce que son nouveau type ne montre pas » : une case devenue boîte personnage perd sa
    situation, une boîte personnage devenue case son personnage montré."""
    case, _ = _case_situee(client, planche)
    _ok(client.put(f"/api/regions/{case}", json={"type": "personnage"}, headers=ADMIN), 200)
    assert _liens(db_path, case)["attributs"] == []
    boite, _ = _boite_montrant(client, planche)
    _ok(client.put(f"/api/regions/{boite}", json={"type": "case"}, headers=ADMIN), 200)
    assert _liens(db_path, boite)["presence"] is None


def test_un_geste_qui_ne_change_pas_le_type_ne_retire_rien(client, planche, db_path):
    case, lieu = _case_situee(client, planche)
    for corps in ({"x": 7}, {"type": "case"}):
        rep = _ok(client.put(f"/api/regions/{case}", json=corps, headers=ADMIN), 200)
        assert "situation_retiree" not in rep.json()
    assert _liens(db_path, case)["attributs"] == [lieu]
    boite, milou = _boite_montrant(client, planche)
    _ok(client.put(f"/api/regions/{boite}", json={"type": "personnage"}, headers=ADMIN), 200)
    assert _liens(db_path, boite)["presence"] == milou


# --------------------------------------------------------------------------- #
# Un seul Ctrl+Z rend tout
# --------------------------------------------------------------------------- #
def test_un_ctrl_z_rend_la_case_et_sa_situation(client, planche, db_path):
    rid, lieu = _case_situee(client, planche)
    _ok(client.put(f"/api/regions/{rid}", json={"type": "texte"}, headers=ADMIN), 200)
    assert client.get("/api/undo/prochain", headers=ADMIN).json()["description"] == \
        "modification d'une région et retrait de sa situation"
    n = _n(db_path, "SELECT COUNT(*) n FROM evenement WHERE type = 'annulation'")
    res = _ok(client.post("/api/undo", headers=ADMIN), 200).json()
    assert res["liens_non_rendus"] == 0
    assert (_type(db_path, rid), _liens(db_path, rid)["attributs"]) == ("case", [lieu])
    assert _n(db_path, "SELECT COUNT(*) n FROM evenement WHERE type = 'annulation'") == n + 1


def test_un_ctrl_z_rend_la_boite_et_son_personnage(client, planche, db_path):
    rid, milou = _boite_montrant(client, planche)
    _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ADMIN), 200)
    assert client.get("/api/undo/prochain", headers=ADMIN).json()["description"] == \
        "modification d'une région et retrait du personnage montré"
    res = _ok(client.post("/api/undo", headers=ADMIN), 200).json()
    assert res["liens_non_rendus"] == 0
    assert (_type(db_path, rid), _liens(db_path, rid)["presence"]) == ("personnage", milou)


def test_la_description_nomme_tout_ce_qui_est_parti(client, planche, db_path):
    """Une boîte personnage d'avant ANN-8 qui portait aussi un locuteur, devenue case : les
    deux partent dans le même acte, et la pile le dit."""
    rid, milou = _boite_montrant(client, planche)
    tintin = _perso(client, "Tintin")
    _sql(db_path, "INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?)",
         (rid, tintin))
    rep = _ok(client.put(f"/api/regions/{rid}", json={"type": "case"}, headers=ADMIN), 200)
    assert rep.json()["locuteur_retire"]["id"] == tintin
    assert rep.json()["presence_retiree"]["id"] == milou
    assert client.get("/api/undo/prochain", headers=ADMIN).json()["description"] == \
        "modification d'une région et retrait de son locuteur et du personnage montré"


def test_un_personnage_disparu_ne_revient_pas_mais_le_type_si(client, planche, db_path):
    rid, fantome = _boite_montrant(client, planche, nom="Fantome")
    _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ADMIN), 200)
    _ok(client.delete(f"/api/personnages/{fantome}", headers=ADMIN), 204)
    res = _ok(client.post("/api/undo", headers=ADMIN), 200).json()
    assert res["liens_non_rendus"] == 1
    assert (_type(db_path, rid), _liens(db_path, rid)["presence"]) == ("personnage", None)


# --------------------------------------------------------------------------- #
# L'annulation gardée (CONC-3)
# --------------------------------------------------------------------------- #
def test_le_personnage_montre_par_un_autre_n_est_pas_ecrase(client, planche, db_path,
                                                            derriere_proxy):
    """Alice passe en bulle la boîte qui montre Milou ; Bob la repasse en boîte et y montre
    Haddock ; le Ctrl+Z d'Alice remplacerait Haddock par Milou. 409 nommant Bob, rien
    d'écrit, l'acte reste en tête de la pile d'Alice."""
    rid, milou = _boite_montrant(client, planche, headers=ALICE)
    haddock = _perso(client, "Haddock")
    _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ALICE), 200)
    _ok(client.put(f"/api/regions/{rid}", json={"type": "personnage"}, headers=BOB), 200)
    _ok(client.put(f"/api/regions/{rid}/personnage", json={"personnage_id": haddock},
                   headers=BOB), 200)
    n = _n(db_path, "SELECT COUNT(*) n FROM evenement")
    res = client.post("/api/undo", headers=ALICE)
    assert res.status_code == 409, res.text
    conflit = res.json()["detail"]["conflit"]
    assert (conflit["cible"], conflit["champ"], conflit["valeur_actuelle"]) == \
        ("personnage_presence", "presence", haddock)
    assert conflit["auteur"]["login"] == "bob"
    assert "le personnage montré" in res.json()["detail"]["message"]
    assert _liens(db_path, rid)["presence"] == haddock
    assert _n(db_path, "SELECT COUNT(*) n FROM evenement") == n
    assert client.get("/api/undo/prochain", headers=ALICE).json()["description"] == \
        "modification d'une région et retrait du personnage montré"


def test_le_meme_personnage_remontre_par_un_autre_ne_bloque_pas(client, planche, db_path,
                                                               derriere_proxy):
    rid, milou = _boite_montrant(client, planche, headers=ALICE)
    _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ALICE), 200)
    _ok(client.put(f"/api/regions/{rid}", json={"type": "personnage"}, headers=BOB), 200)
    _ok(client.put(f"/api/regions/{rid}/personnage", json={"personnage_id": milou},
                   headers=BOB), 200)
    _ok(client.post("/api/undo", headers=ALICE), 200)
    assert _liens(db_path, rid)["presence"] == milou


def test_une_situation_posee_par_un_autre_ne_devient_pas_invisible(client, planche, db_path,
                                                                   derriere_proxy):
    """Le miroir de h2 : Alice passe une bulle en case ; Bob situe la case ; le Ctrl+Z
    d'Alice rendrait une bulle qui porte la situation de Bob, cachée. 409 nommant Bob."""
    rid = _region(client, planche["id"], type="bulle")
    lieu = _valeur(client, "case", "lieu", "falaise")
    _ok(client.put(f"/api/regions/{rid}", json={"type": "case"}, headers=ALICE), 200)
    _ok(client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": lieu}, headers=BOB), 200)
    n = _n(db_path, "SELECT COUNT(*) n FROM evenement")
    res = client.post("/api/undo", headers=ALICE)
    assert res.status_code == 409, res.text
    conflit = res.json()["detail"]["conflit"]
    assert (conflit["cible"], conflit["champ"], conflit["valeur_actuelle"]) == \
        ("region_attribut", "situation", [lieu])
    assert conflit["auteur"]["login"] == "bob"
    assert "la situation" in res.json()["detail"]["message"]
    assert (_type(db_path, rid), _liens(db_path, rid)["attributs"]) == ("case", [lieu])
    assert _n(db_path, "SELECT COUNT(*) n FROM evenement") == n


def test_une_situation_revient_par_difference_a_cote_de_celle_d_un_autre(
        client, planche, db_path, derriere_proxy):
    """Alice passe en bulle une case située « falaise » ; Bob la repasse en case et la situe
    « nuit » ; le Ctrl+Z d'Alice rend « falaise » à côté de « nuit » : un ensemble, comme
    les tags — rien n'est écrasé, pas de 409."""
    rid, falaise = _case_situee(client, planche, headers=ALICE)
    nuit = _valeur(client, "case", "moment", "nuit")
    _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ALICE), 200)
    _ok(client.put(f"/api/regions/{rid}", json={"type": "case"}, headers=BOB), 200)
    _ok(client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": nuit}, headers=BOB), 200)
    _ok(client.post("/api/undo", headers=ALICE), 200)
    assert _liens(db_path, rid)["attributs"] == sorted([falaise, nuit])


def test_une_situation_d_avant_ann8_ne_bloque_pas_son_auteure(client, planche, db_path):
    """Le c3 de la situation : une bulle d'avant ANN-8 qui porte encore la situation de la
    case qu'elle était ; seule, on la passe en case, puis Ctrl+Z. L'acte l'a vue : rien
    n'a changé depuis, l'état d'avant revient tel qu'il était."""
    rid = _region(client, planche["id"], type="bulle")
    lieu = _valeur(client, "case", "lieu", "falaise")
    _sql(db_path, "INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)", (rid, lieu))
    _ok(client.put(f"/api/regions/{rid}", json={"type": "case"}, headers=ADMIN), 200)
    _ok(client.post("/api/undo", headers=ADMIN), 200)
    assert (_type(db_path, rid), _liens(db_path, rid)["attributs"]) == ("bulle", [lieu])


def test_un_personnage_montre_d_avant_ann8_ne_bloque_pas_son_auteure(client, planche, db_path):
    """Le c3 du personnage montré : une bulle d'avant ANN-8 qui montre encore Milou ; seule,
    on la passe en boîte personnage, puis Ctrl+Z. L'acte l'a vu : l'annulation passe."""
    rid = _region(client, planche["id"], type="bulle")
    milou = _perso(client, "Milou")
    _sql(db_path, "INSERT INTO personnage_presence (region_id, personnage_id) VALUES (?, ?)",
         (rid, milou))
    _ok(client.put(f"/api/regions/{rid}", json={"type": "personnage"}, headers=ADMIN), 200)
    _ok(client.post("/api/undo", headers=ADMIN), 200)
    assert (_type(db_path, rid), _liens(db_path, rid)["presence"]) == ("bulle", milou)


def test_une_partie_de_la_situation_laissee_ne_bloque_pas(client, planche, db_path,
                                                          derriere_proxy):
    """Ce que la région porte doit être une PARTIE de ce que l'acte avait laissé : Bob retire
    l'une des deux valeurs qu'une bulle d'avant ANN-8 portait, rien n'est caché de neuf."""
    rid = _region(client, planche["id"], type="bulle")
    lieu = _valeur(client, "case", "lieu", "falaise")
    nuit = _valeur(client, "case", "moment", "nuit")
    for v in (lieu, nuit):
        _sql(db_path, "INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)", (rid, v))
    _ok(client.put(f"/api/regions/{rid}", json={"type": "case"}, headers=ALICE), 200)
    _ok(client.delete(f"/api/regions/{rid}/attributs/{nuit}", headers=BOB), 204)
    _ok(client.post("/api/undo", headers=ALICE), 200)
    assert (_type(db_path, rid), _liens(db_path, rid)["attributs"]) == ("bulle", [lieu])


# --------------------------------------------------------------------------- #
# L'annulation ne repose pas un lien sur un type qui ne le montre pas
# --------------------------------------------------------------------------- #
def test_l_annulation_ne_remontre_pas_un_personnage_sur_une_region_devenue_bulle(
        client, planche, db_path, derriere_proxy):
    """Alice montre Milou puis le retire ; Bob passe la boîte en bulle ; le Ctrl+Z d'Alice
    reposait Milou SUR LA BULLE. L'acte est passé, seconde phrase."""
    rid = _region(client, planche["id"], type="personnage")
    milou = _perso(client, "Milou")
    _ok(client.put(f"/api/regions/{rid}/personnage", json={"personnage_id": milou},
                   headers=ALICE), 200)
    _ok(client.delete(f"/api/regions/{rid}/personnage", headers=ALICE), 204)
    _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=BOB), 200)
    res = client.post("/api/undo", headers=ALICE)
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["message"] == undo.PHRASE_IRRETABLISSABLE.format(
        description="retrait d'une présence")
    assert _liens(db_path, rid)["presence"] is None


def test_une_suppression_retablie_ne_repose_pas_une_situation_sur_une_bulle(
        client, planche, db_path):
    """Une bulle d'avant ANN-8 qui porte une situation, supprimée puis rétablie : la bulle
    revient, la situation non, et la réponse la compte."""
    rid = _region(client, planche["id"], type="bulle")
    lieu = _valeur(client, "case", "lieu", "falaise")
    _sql(db_path, "INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)", (rid, lieu))
    _ok(client.delete(f"/api/regions/{rid}", headers=ADMIN), 204)
    res = _ok(client.post("/api/undo", headers=ADMIN), 200).json()
    assert res["liens_non_rendus"] == 1
    assert (_type(db_path, rid), _liens(db_path, rid)["attributs"]) == ("bulle", [])
