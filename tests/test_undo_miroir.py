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
5. **L'écran le dit** : la réponse nomme le personnage montré.

ANN-7, le basculement : la situation d'une case ne se lit plus. Un changement de type ne la
retire plus ni ne la photographie, Ctrl+Z ne la rend plus, et un acte d'avant qui l'avait
retirée se défait sans elle (la ligne d'hier reste en base jusqu'à la migration v39).
"""
import json

import undo
from conftest import ADMIN
from test_undo_liens import _liens, _ok, _perso, _region, _situer, _sql, _valeur

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


def _case_situee(client, planche):
    """Une case et sa situation d'HIER, posée en base (ANN-7 : aucune route ne la pose plus,
    ni ne la lit)."""
    rid = _region(client, planche["id"], headers=ADMIN)
    lieu = _valeur(client, "case", "lieu", "falaise")
    _situer(rid, lieu)
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
def test_une_case_devenue_bulle_ne_lit_plus_sa_situation_d_hier(client, planche, db_path):
    """ANN-7, le basculement : la situation ne se retire plus avec le type, ne se
    photographie plus et ne se dit plus — la ligne d'hier reste, invisible, jusqu'à la
    migration. Mutant tué : la part situation remise dans `database.retirer_liens_caches`."""
    rid, lieu = _case_situee(client, planche)
    rep = _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ADMIN), 200)
    assert "situation_retiree" not in rep.json()
    assert "locuteur_retire" not in rep.json() and "presence_retiree" not in rep.json()
    assert _liens(db_path, rid)["attributs"] == [lieu]
    avant = json.loads(_dernier_acte(db_path, rid)["avant"])
    assert "attributs" not in avant and "attributs_dimensions" not in avant
    assert avant["liens_vus"] == {"locuteur": None, "presence": None}
    assert _n(db_path, "SELECT COUNT(*) n FROM evenement WHERE type = 'delien'") == 0


def test_une_boite_personnage_devenue_bulle_perd_son_personnage_montre(client, planche, db_path):
    rid, milou = _boite_montrant(client, planche)
    rep = _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ADMIN), 200)
    assert rep.json()["presence_retiree"] == {"id": milou, "nom": "Milou", "serie": None}
    assert _liens(db_path, rid)["presence"] is None
    assert json.loads(_dernier_acte(db_path, rid)["avant"])["presence"] == milou
    assert client.get(f"/api/regions/{rid}/personnage", headers=ADMIN).json()["personnage"] is None


def test_la_regle_vaut_pour_tout_type_qui_ne_montre_pas(client, planche, db_path):
    """« Ce que son nouveau type ne montre pas » : une boîte personnage devenue case perd
    son personnage montré."""
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
def test_un_ctrl_z_d_avant_le_basculement_rend_la_case_sans_sa_situation(client, planche,
                                                                          db_path):
    """Un changement de type d'AVANT le basculement avait retiré la situation et la portait
    dans son `avant` (`attributs`, `attributs_dimensions`, `liens_vus`). Son Ctrl+Z rend le
    type — et rien de la situation, qu'il ne nomme plus. Mutant tué : `attributs` remis dans
    `undo._RETRAITS`."""
    rid, lieu = _case_situee(client, planche)
    _ok(client.put(f"/api/regions/{rid}", json={"type": "texte"}, headers=ADMIN), 200)
    # L'acte, tel que la route d'hier l'écrivait, et la ligne qu'elle retirait.
    _sql(db_path, "UPDATE evenement SET avant = json_set(avant, '$.attributs', json(?), "
                  "'$.attributs_dimensions', json('[]'), '$.liens_vus.attributs', json(?)) "
                  "WHERE id = ?", (f"[{lieu}]", f"[{lieu}]", _dernier_acte(db_path, rid)["id"]))
    _sql(db_path, "DELETE FROM region_attribut WHERE region_id = ?", (rid,))
    assert client.get("/api/undo/prochain", headers=ADMIN).json()["description"] == \
        "modification d'une région"
    n = _n(db_path, "SELECT COUNT(*) n FROM evenement WHERE type = 'annulation'")
    res = _ok(client.post("/api/undo", headers=ADMIN), 200).json()
    assert res["description"] == "modification d'une région"
    assert "liens_non_rendus" not in res
    assert (_type(db_path, rid), _liens(db_path, rid)["attributs"]) == ("case", [])
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


# --------------------------------------------------------------------------- #
# Les routes de la présence et de la situation gardent le type (2026-10-22)
# --------------------------------------------------------------------------- #
def test_seule_une_boite_personnage_montre_un_personnage(client, planche, db_path):
    milou = _perso(client, "Milou")
    for t in ("case", "bulle", "cartouche", "texte"):
        rid = _region(client, planche["id"], type=t)
        r = client.put(f"/api/regions/{rid}/personnage", json={"personnage_id": milou},
                       headers=ADMIN)
        assert r.status_code == 422, (t, r.text)
        assert "boîte personnage" in r.json()["detail"]
        assert _liens(db_path, rid)["presence"] is None
    boite = _region(client, planche["id"], type="personnage")
    _ok(client.put(f"/api/regions/{boite}/personnage", json={"personnage_id": milou},
                   headers=ADMIN), 200)


def test_retirer_reste_ouvert_a_tout_type(client, planche, db_path):
    """Lire et retirer restent ouverts, pour nettoyer ce qu'une base d'avant porte. (La
    situation ne se retire plus par une route : ANN-7.)"""
    rid = _region(client, planche["id"], type="bulle")
    milou = _perso(client, "Milou")
    _sql(db_path, "INSERT INTO personnage_presence (region_id, personnage_id) VALUES (?, ?)",
         (rid, milou))
    _ok(client.delete(f"/api/regions/{rid}/personnage", headers=ADMIN), 204)
    assert _liens(db_path, rid)["presence"] is None


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


def test_une_suppression_retablie_ne_rend_plus_la_situation(client, planche, db_path):
    """ANN-7, le basculement : une case qui porte une situation d'hier, supprimée puis
    rétablie — la case revient, la situation non (l'instantané ne la porte plus), et rien ne
    la compte : elle ne se lit plus nulle part."""
    rid, lieu = _case_situee(client, planche)
    _ok(client.delete(f"/api/regions/{rid}", headers=ADMIN), 204)
    instantane = json.loads(_sql(db_path, "SELECT avant FROM evenement WHERE cible_table = "
                                          "'regions' AND type = 'suppression' AND cible_id = ?",
                                 (rid,))[0]["avant"])
    assert "attributs" not in instantane
    res = _ok(client.post("/api/undo", headers=ADMIN), 200).json()
    assert res["liens_non_rendus"] == 0
    assert (_type(db_path, rid), _liens(db_path, rid)["attributs"]) == ("case", [])


def _bulle_de_bob(client, planche, chemin, type_):
    rid = _region(client, planche["id"], type=type_, headers=ALICE)
    zed = _perso(client, "Zed QA")
    _ok(client.put(f"/api/regions/{rid}/{chemin}", json={"personnage_id": zed}, headers=BOB), 200)
    return rid, zed


def test_l_annulation_de_son_changement_de_type_ne_s_approprie_pas_le_locuteur_de_bob(
        client, planche, db_path, derriere_proxy):
    """Alice crée une bulle ; Bob lui donne Zed ; Alice la passe en case (Zed part avec le
    type), Ctrl+Z (Zed revient), Ctrl+Z encore : la création. L'annulation qui a reposé Zed
    ne fait pas d'Alice celle qui l'a posé — 409, et Zed reste."""
    rid, zed = _bulle_de_bob(client, planche, "locuteur", "bulle")
    _ok(client.put(f"/api/regions/{rid}", json={"type": "case"}, headers=ALICE), 200)
    _ok(client.post("/api/undo", headers=ALICE), 200)
    assert _liens(db_path, rid)["locuteur"] == zed
    res = client.post("/api/undo", headers=ALICE)
    assert res.status_code == 409, "la création annulée a emporté le locuteur de Bob"
    assert res.json()["detail"]["conflit"]["auteur"]["login"] == "bob"
    assert _liens(db_path, rid)["locuteur"] == zed


def test_l_annulation_de_sa_suppression_ne_s_approprie_pas_le_locuteur_de_bob(
        client, planche, db_path, derriere_proxy):
    rid, zed = _bulle_de_bob(client, planche, "locuteur", "bulle")
    _ok(client.delete(f"/api/regions/{rid}", headers=ALICE), 204)
    _ok(client.post("/api/undo", headers=ALICE), 200)
    assert _liens(db_path, rid)["locuteur"] == zed
    res = client.post("/api/undo", headers=ALICE)
    assert res.status_code == 409, "la création annulée a emporté le locuteur de Bob"
    assert _liens(db_path, rid)["locuteur"] == zed


def test_l_annulation_de_son_changement_de_type_ne_s_approprie_pas_le_personnage_de_bob(
        client, planche, db_path, derriere_proxy):
    """Le même pour le personnage montré d'une boîte (mêmes sources, mêmes gardes)."""
    rid, zed = _bulle_de_bob(client, planche, "personnage", "personnage")
    _ok(client.put(f"/api/regions/{rid}", json={"type": "case"}, headers=ALICE), 200)
    _ok(client.post("/api/undo", headers=ALICE), 200)
    assert _liens(db_path, rid)["presence"] == zed
    res = client.post("/api/undo", headers=ALICE)
    assert res.status_code == 409, "la création annulée a emporté le personnage de Bob"
    assert _liens(db_path, rid)["presence"] == zed


def test_l_annulation_de_sa_suppression_ne_s_approprie_pas_le_personnage_de_bob(
        client, planche, db_path, derriere_proxy):
    rid, zed = _bulle_de_bob(client, planche, "personnage", "personnage")
    _ok(client.delete(f"/api/regions/{rid}", headers=ALICE), 204)
    _ok(client.post("/api/undo", headers=ALICE), 200)
    res = client.post("/api/undo", headers=ALICE)
    assert res.status_code == 409, "la création annulée a emporté le personnage de Bob"
    assert _liens(db_path, rid)["presence"] == zed


def test_son_propre_locuteur_repose_par_son_ctrl_z_ne_bloque_pas_sa_creation(
        client, planche, db_path, derriere_proxy):
    """Le contre-cas : Alice pose elle-même Zed, passe la bulle en case, Ctrl+Z, Ctrl+Z
    (son lien), Ctrl+Z (la création) — tout passe, rien d'autre que son travail ne part."""
    rid = _region(client, planche["id"], type="bulle", headers=ALICE)
    zed = _perso(client, "Zed QA")
    _ok(client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": zed}, headers=ALICE), 200)
    _ok(client.put(f"/api/regions/{rid}", json={"type": "case"}, headers=ALICE), 200)
    for _ in range(3):
        _ok(client.post("/api/undo", headers=ALICE), 200)
    assert not _sql(db_path, "SELECT 1 FROM regions WHERE id = ?", (rid,))
