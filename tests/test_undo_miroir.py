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
    dim = _sql(db_path, "SELECT dimension_id FROM attribut_valeur WHERE id = ?", (lieu,))[0]
    assert avant["liens_vus"] == {"locuteur": None, "presence": None, "attributs": [lieu],
                                  "attributs_dimensions": [[lieu, dim["dimension_id"]]]}
    assert avant["attributs_dimensions"] == [[lieu, dim["dimension_id"]]]
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
# Une situation LOCALE à une collection qu'on ne lit pas (relecture de la suite, S1–S3)
# --------------------------------------------------------------------------- #
LETTREUSE = {"Remote-User": "alice", "Remote-Groups": "lettrage"}


def _decor_cache(client, planche, db_path):
    """L'album vit dans C1 (Alice y écrit) et C2 (Alice ne la lit pas). Une valeur de case
    GLOBALE (visible), une valeur LOCALE à C2 (cachée à Alice)."""
    c = sqlite3.connect(db_path)
    c1 = c.execute("SELECT collection_id FROM collection_album WHERE album_id = ?",
                   (planche["album_id"],)).fetchone()[0]
    c2 = c.execute("INSERT INTO collection (nom) VALUES ('Incubateur')").lastrowid
    c.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
              (c2, planche["album_id"]))
    c.execute("INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
              "VALUES (?, 'utilisateur', 'alice', 'ecriture')", (c1,))
    d = c.execute("INSERT INTO attribut_dimension (cible, nom, collection_id) "
                  "VALUES ('case', 'grille-secrete', ?)", (c2,)).lastrowid
    cachee = c.execute("INSERT INTO attribut_valeur (dimension_id, valeur, collection_id) "
                       "VALUES (?, 'hypothese-confidentielle', ?)", (d, c2)).lastrowid
    c.commit()
    c.close()
    return _valeur(client, "case", "lieu", "falaise"), cachee


def test_s1_ctrl_z_rend_la_situation_cachee_que_le_changement_de_type_a_retiree(
        client, planche, db_path, derriere_proxy):
    """« Cacher n'est pas saisir » : passer en bulle la case retire aussi la valeur de C2,
    qu'Alice ne voit pas ; son Ctrl+Z la rend avec la sienne. Sans quoi le travail de C2
    était perdu, effacé par un geste qui ne le voyait pas."""
    visible, cachee = _decor_cache(client, planche, db_path)
    rid = _region(client, planche["id"], type="case")
    _ok(client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": visible},
                   headers=LETTREUSE), 200)
    _ok(client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": cachee}, headers=BOB), 200)
    _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=LETTREUSE), 200)
    assert _liens(db_path, rid)["attributs"] == []
    res = _ok(client.post("/api/undo", headers=LETTREUSE), 200).json()
    assert res["liens_non_rendus"] == 0
    assert _liens(db_path, rid)["attributs"] == sorted([visible, cachee])


def _reprendre_l_identifiant(db_path, vid, dimension_de_c3=True):
    """Supprime la valeur `vid` et en crée une neuve qui reprend son identifiant, DANS LA
    MÊME SECONDE (aucun témoin de date ne la voit) : d'une autre grille, locale à une
    collection fermée, ou de la même dimension. Rend l'identifiant repris."""
    c = sqlite3.connect(db_path)
    c.execute("PRAGMA foreign_keys = ON")
    dim = c.execute("SELECT dimension_id FROM attribut_valeur WHERE id = ?", (vid,)).fetchone()[0]
    c.execute("DELETE FROM attribut_valeur WHERE id = ?", (vid,))
    if dimension_de_c3:
        c3 = c.execute("INSERT INTO collection (nom) VALUES ('Fermee')").lastrowid
        dim = c.execute("INSERT INTO attribut_dimension (cible, nom, collection_id) "
                        "VALUES ('case', 'autre-grille', ?)", (c3,)).lastrowid
    neuve = c.execute("INSERT INTO attribut_valeur (id, dimension_id, valeur, date_creation) "
                      "VALUES (?, ?, 'mot-repris', (SELECT date FROM evenement "
                      "ORDER BY id DESC LIMIT 1))", (vid, dim)).lastrowid
    c.commit()
    c.close()
    return neuve


def test_r1_une_valeur_reprise_dans_la_meme_seconde_d_une_autre_grille_ne_revient_pas(
        client, planche, db_path, derriere_proxy):
    """La valeur cachée retirée avec le type a été supprimée, et son identifiant repris dans
    la même seconde par un terme d'une autre grille, d'une collection fermée : Ctrl+Z ne
    pose pas ce terme sur la région ; le lien se compte parmi les non rendus."""
    visible, cachee = _decor_cache(client, planche, db_path)
    rid = _region(client, planche["id"], type="case")
    _ok(client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": cachee}, headers=BOB), 200)
    _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=LETTREUSE), 200)
    reprise = _reprendre_l_identifiant(db_path, cachee)
    res = _ok(client.post("/api/undo", headers=LETTREUSE), 200).json()
    assert reprise not in _liens(db_path, rid)["attributs"]
    assert res["liens_non_rendus"] == 1


def test_r1_ce_qui_reste_ouvert_la_meme_dimension_dans_la_meme_seconde(
        client, planche, db_path, derriere_proxy):
    """La limite écrite dans `docs/undo.md`, décrite telle qu'elle est : repris dans la
    même seconde par une valeur de la MÊME dimension, l'identifiant revient."""
    visible, cachee = _decor_cache(client, planche, db_path)
    rid = _region(client, planche["id"], type="case")
    _ok(client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": cachee}, headers=BOB), 200)
    _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=LETTREUSE), 200)
    reprise = _reprendre_l_identifiant(db_path, cachee, dimension_de_c3=False)
    _ok(client.post("/api/undo", headers=LETTREUSE), 200)
    assert reprise in _liens(db_path, rid)["attributs"]


def test_s2_le_retrait_ne_compte_que_ce_qu_on_voit(client, planche, db_path, derriere_proxy):
    """La réponse du PUT et la pile ne disent rien d'une valeur cachée : une seule valeur
    comptée ; et si seule la cachée part, ni compte ni « retrait de sa situation »."""
    visible, cachee = _decor_cache(client, planche, db_path)
    rid = _region(client, planche["id"], type="case")
    for v, qui in ((visible, LETTREUSE), (cachee, BOB)):
        _ok(client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": v}, headers=qui), 200)
    rep = _ok(client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=LETTREUSE), 200)
    assert rep.json()["situation_retiree"] == 1

    seule = _region(client, planche["id"], type="case")
    _ok(client.put(f"/api/regions/{seule}/attributs", json={"valeur_id": cachee}, headers=BOB), 200)
    rep = _ok(client.put(f"/api/regions/{seule}", json={"type": "bulle"}, headers=LETTREUSE), 200)
    assert "situation_retiree" not in rep.json()
    assert client.get("/api/undo/prochain", headers=LETTREUSE).json()["description"] == \
        "modification d'une région"


def test_s2_le_409_ne_nomme_ni_la_valeur_cachee_ni_son_auteur(client, planche, db_path,
                                                             derriere_proxy):
    """Alice passe une bulle en case ; Bob la situe d'une valeur de C2 ; le Ctrl+Z d'Alice
    est refusé — la valeur serait cachée par la bulle —, mais le refus n'en dit rien :
    aucune valeur, aucun auteur, « modifiée ailleurs »."""
    visible, cachee = _decor_cache(client, planche, db_path)
    rid = _region(client, planche["id"], type="bulle")
    _ok(client.put(f"/api/regions/{rid}", json={"type": "case"}, headers=LETTREUSE), 200)
    _ok(client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": cachee}, headers=BOB), 200)
    res = client.post("/api/undo", headers=LETTREUSE)
    assert res.status_code == 409, res.text
    conflit = res.json()["detail"]["conflit"]
    assert (conflit["champ"], conflit["valeur_actuelle"], conflit["auteur"]) == \
        ("situation", [], None)
    assert "bob" not in res.text.lower()
    assert "modifiée ailleurs" in res.json()["detail"]["message"]


def test_s3_retirer_une_valeur_demande_de_la_voir(client, planche, db_path, derriere_proxy):
    """Son identifiant ne suffit plus à effacer la situation de C2 : 404, rien de retiré."""
    visible, cachee = _decor_cache(client, planche, db_path)
    rid = _region(client, planche["id"], type="case")
    _ok(client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": cachee}, headers=BOB), 200)
    r = client.delete(f"/api/regions/{rid}/attributs/{cachee}", headers=LETTREUSE)
    assert r.status_code == 404, r.text
    assert _liens(db_path, rid)["attributs"] == [cachee]


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


def test_seule_une_case_recoit_une_situation(client, planche, db_path):
    lieu = _valeur(client, "case", "lieu", "falaise")
    for t in ("bulle", "personnage", "cartouche", "texte"):
        rid = _region(client, planche["id"], type=t)
        r = client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": lieu}, headers=ADMIN)
        assert r.status_code == 422, (t, r.text)
        assert "case" in r.json()["detail"]
        assert _liens(db_path, rid)["attributs"] == []


def test_retirer_reste_ouvert_a_tout_type(client, planche, db_path):
    """Lire et retirer restent ouverts, pour nettoyer ce qu'une base d'avant porte."""
    rid = _region(client, planche["id"], type="bulle")
    milou = _perso(client, "Milou")
    lieu = _valeur(client, "case", "lieu", "falaise")
    _sql(db_path, "INSERT INTO personnage_presence (region_id, personnage_id) VALUES (?, ?)",
         (rid, milou))
    _sql(db_path, "INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)", (rid, lieu))
    _ok(client.delete(f"/api/regions/{rid}/personnage", headers=ADMIN), 204)
    _ok(client.delete(f"/api/regions/{rid}/attributs/{lieu}", headers=ADMIN), 204)
    assert _liens(db_path, rid) == {"locuteur": None, "presence": None, "attributs": []}


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


# --------------------------------------------------------------------------- #
# CONC-4, relecture — la garde des liens d'une création
# --------------------------------------------------------------------------- #
def test_creation_annulee_ne_rend_pas_la_valeur_cachee_ni_son_auteur(
        client, planche, db_path, derriere_proxy):
    """La doctrine S2 d'ANN-8 (`_garder_liens_du_type`) vaut pour la garde d'une création :
    une situation qu'un autre a posée, locale à une collection que l'agent ne lit pas, refuse
    l'annulation — mais le refus ne rend ni son identifiant ni son auteur, et dit « ailleurs »."""
    visible, cachee = _decor_cache(client, planche, db_path)
    rid = _region(client, planche["id"], type="case", headers=LETTREUSE)
    _ok(client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": cachee}, headers=BOB), 200)
    res = client.post("/api/undo", headers=LETTREUSE)
    assert res.status_code == 409, res.text
    detail = res.json()["detail"]
    assert detail["conflit"]["champ"] == "situation"
    assert cachee not in (detail["conflit"]["valeur_actuelle"] or []), "valeur cachée rendue"
    assert detail["conflit"]["auteur"] is None, "auteur d'une valeur cachée nommé"
    assert "modifiée ailleurs" in detail["message"] and "bob" not in detail["message"]
    assert _liens(db_path, rid)["attributs"] == [cachee]


def test_creation_annulee_nomme_l_auteur_d_une_valeur_vue_et_tait_la_cachee(
        client, planche, db_path, derriere_proxy):
    """Une valeur VUE et une cachée, toutes deux de Bob : le refus nomme Bob (il a posé la
    vue) et ne rend que la vue."""
    visible, cachee = _decor_cache(client, planche, db_path)
    rid = _region(client, planche["id"], type="case", headers=LETTREUSE)
    for v in (visible, cachee):
        _ok(client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": v}, headers=BOB), 200)
    res = client.post("/api/undo", headers=LETTREUSE)
    assert res.status_code == 409, res.text
    conflit = res.json()["detail"]["conflit"]
    assert conflit["valeur_actuelle"] == [visible]
    assert conflit["auteur"]["login"] == "bob"


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
