"""COL-3, tranche 3c — le responsable voit tout son projet, et le projet borne ses
collections (F1, F2, Q1, Q3, F6 ; Hugo, 2026-10-26 ; cadrage
`docs/col3-tranche3c-cadrage.md`).

- F1, la voie 1 : le RESPONSABLE d'un projet LIT toutes ses collections — une lecture
  DÉRIVÉE, jamais recopiée : qui cesse d'être responsable cesse de lire ; lire n'ouvre ni
  l'écriture, ni l'export, ni « Qui entre » ; rien dans un bac à sable.
- F2, la voie 2 : on n'entre dans une collection que si l'on est du projet — 409 nommé, la
  base comprise, par la route comme par l'outil ; la RÉFÉRENCE exacte (Q2 : le genre
  compte, un membre par un groupe n'entre pas par son login).
- Q1 : qui sort du projet perd ses accès de collection, journalisés ; 409 s'il est le
  dernier propriétaire de l'une d'elles.
- Q3 : le propriétaire d'une collection lit les NOMS des membres du projet, sans les rôles.

Chaque geste est joué sous l'identité qui compte, par la route.
"""
import pytest

import autorisation
from conftest import ADMIN, make_png
from test_projets import _collection, _membre, _projet, _sql

RESP = {"Remote-User": "resp"}
PROPRIO = {"Remote-User": "proprio"}
MEMBRE = {"Remote-User": "membre"}
ECRIVAIN = {"Remote-User": "ecrivain"}


def _ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.text)
    return r.json() if r.content else None


def _acces(client, cid, principal, niveau, genre="utilisateur", qui=ADMIN):
    return client.put(f"/api/collections/{cid}/acces", headers=qui,
                      json={"genre": genre, "principal": principal, "niveau": niveau})


@pytest.fixture
def projet(client, derriere_proxy, db_path):
    """« Séminaire » : `resp` en est responsable, `proprio` et `ecrivain` membres ; deux
    collections hors de la base — « Carnet » (`proprio` la possède, `ecrivain` y écrit, un
    album dedans) et « Vide » (personne). Et « Voisin », un autre projet, avec sa collection
    et son album."""
    pid = _projet(client, "Séminaire")
    for qui, role in (("resp", "responsable"), ("proprio", "membre"),
                      ("ecrivain", "membre")):
        assert _membre(client, pid, qui, role=role).status_code in (200, 201)
    carnet = _collection(client, "Carnet", projet_id=pid)
    vide = _collection(client, "Vide", projet_id=pid)
    _ok(_acces(client, carnet, "proprio", "proprietaire"))
    _ok(_acces(client, carnet, "ecrivain", "ecriture"))
    a = _ok(client.post("/api/albums", headers=PROPRIO,
                        json={"titre": "Carnet d'arrivant", "collection_id": carnet}), 201)["id"]
    voisin = _projet(client, "Voisin")
    c_voisin = _collection(client, "Ailleurs", projet_id=voisin)
    a_voisin = _ok(client.post("/api/albums", headers=ADMIN,
                               json={"titre": "D'ailleurs", "collection_id": c_voisin}),
                   201)["id"]
    base = _sql(db_path, "SELECT id FROM collection WHERE base = 1 AND projet_id = ?",
                (pid,))[0]["id"]
    return {"projet": pid, "carnet": carnet, "vide": vide, "album": a, "voisin": voisin,
            "c_voisin": c_voisin, "a_voisin": a_voisin, "base": base, "db": db_path}


def _collections(client, qui):
    return {c["id"]: c for c in client.get("/api/collections", headers=qui).json()}


def _albums(client, qui):
    return {a["id"]: a for a in client.get("/api/albums", headers=qui).json()}


# =========================================================================== #
# F1 — le responsable LIT toutes les collections de son projet
# =========================================================================== #
def test_le_responsable_lit_toutes_les_collections_de_son_projet(client, projet):
    """`resp` lit « Carnet » et « Vide », où aucun accès ne le nomme, au niveau `lecture` ;
    il lit l'album du Carnet. Rien du projet voisin."""
    cols = _collections(client, RESP)
    assert {projet["carnet"], projet["vide"], projet["base"]} <= set(cols)
    assert (cols[projet["carnet"]]["mon_niveau"], cols[projet["vide"]]["mon_niveau"]) == (
        "lecture", "lecture")
    assert projet["c_voisin"] not in cols
    assert projet["album"] in _albums(client, RESP)
    assert projet["a_voisin"] not in _albums(client, RESP)
    assert client.get(f"/api/albums/{projet['album']}/planches",
                      headers=RESP).status_code == 200
    # Un simple MEMBRE (`ecrivain`) ne lit que la base et ce que « Qui entre » lui ouvre.
    assert projet["vide"] not in _collections(client, ECRIVAIN)
    assert projet["carnet"] in _collections(client, ECRIVAIN)


def test_lire_n_ouvre_ni_l_ecriture_ni_l_export_ni_qui_entre(client, projet):
    """La lecture dérivée ne s'empile pas : `resp` n'écrit pas dans le Carnet (l'album n'y
    est pas `ecrivable`, une région se refuse), ne l'exporte pas (403 nommé, par la route
    et par `pour_export`), et ne règle pas son « Qui entre » (403)."""
    a = _albums(client, RESP)[projet["album"]]
    assert a["ecrivable"] is False
    col = _collections(client, RESP)[projet["carnet"]]
    assert (col["administrable"], col["exportable"]) == (False, False)
    pl = _ok(client.post(f"/api/albums/{projet['album']}/import", headers=PROPRIO,
                         files={"file": ("p.png", make_png(), "image/png")}), 201)["id"]
    r = client.post(f"/api/planches/{pl}/regions", headers=RESP,
                    json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9})
    assert r.status_code == 404, r.text
    r = client.get(f"/api/export/json?album_id={projet['album']}&collection_id={projet['carnet']}",
                   headers=RESP)
    assert r.status_code == 403, r.text
    assert _acces(client, projet["carnet"], "resp", "ecriture", qui=RESP).status_code == 403


def test_la_lecture_derivee_suit_le_role_et_ne_se_recopie_pas(client, projet):
    """Rétrogradé en simple membre, `resp` ne lit plus le Carnet — rien n'était écrit dans
    `collection_acces` ; sorti du projet, pas davantage. Promu, il le lit de nouveau."""
    assert projet["carnet"] in _collections(client, RESP)
    assert not _sql(projet["db"], "SELECT 1 FROM collection_acces WHERE principal = 'resp'")
    assert _membre(client, projet["projet"], "proprio", role="responsable").status_code == 200
    assert _membre(client, projet["projet"], "resp", role="membre").status_code == 200
    assert projet["carnet"] not in _collections(client, RESP)
    assert projet["carnet"] in _collections(client, PROPRIO)


def test_la_portee_du_responsable_porte_la_lecture_et_rien_d_autre(client, projet):
    """La règle, lue sur la `Portee` résolue : le Carnet en lecture, ni en écriture, ni en
    propriété, ni à l'export — et la portée réduite à l'export ne le garde pas."""
    from test_bac_a_sable import _portee
    p = _portee(projet["db"], RESP)
    assert projet["carnet"] in p.lecture and projet["vide"] in p.lecture
    assert projet["carnet"] not in p.ecriture | p.propriete | p.export
    assert projet["carnet"] not in p.pour_export().lecture
    assert projet["c_voisin"] not in p.lecture


def test_dans_un_bac_a_sable_la_lecture_derivee_ne_vaut_pas(client, projet):
    """Le propriétaire d'un bac à sable en est le responsable : il ne lit pas pour autant la
    collection qu'un invité y a créée, fermée — comme avant la tranche 3c."""
    from test_bac_a_sable import _portee
    lea, sam = {"Remote-User": "lea"}, {"Remote-User": "sam"}
    bac = client.post("/api/bac-a-sable", headers=lea)
    if bac.status_code == 409:                      # pas de jeu préparé : un bac à la main
        pytest.skip("le bac à sable demande le jeu (`tools/preparer_jeu.py`)")
    bac = _ok(bac, 201)
    _ok(client.put(f"/api/projets/{bac['id']}/membres", headers=lea,
                   json={"genre": "utilisateur", "principal": "sam", "role": "membre"}))
    c = _ok(client.post("/api/collections", headers=sam,
                        json={"nom": "À sam", "projet_id": bac["id"]}), 201)["id"]
    assert c not in _portee(projet["db"], lea).lecture
    assert c not in _collections(client, lea)


def test_les_acces_derives_disent_la_lecture_des_responsables(client, projet):
    """`GET …/acces-du-projet` d'une collection qui n'est pas la base : une ligne par
    responsable du projet, au niveau `lecture` ; la base garde les siennes."""
    v = _ok(client.get(f"/api/collections/{projet['carnet']}/acces-du-projet",
                       headers=PROPRIO))
    assert v["base"] is False
    assert v["lignes"] == [{"genre": "utilisateur", "principal": "resp", "niveau": "lecture",
                            "exporter": False, "role": "responsable"}]
    conn = __import__("database").get_connection()
    try:
        assert autorisation.proprietaires_de(conn, projet["carnet"]) == [
            {"genre": "utilisateur", "principal": "proprio"}]
    finally:
        conn.close()


# =========================================================================== #
# F2 — on n'entre dans une collection que si l'on est du projet
# =========================================================================== #
def test_un_principal_hors_du_projet_est_refuse_par_un_409_nomme(client, projet):
    r = _acces(client, projet["carnet"], "inconnu", "lecture")
    assert r.status_code == 409, r.text
    assert "inconnu" in r.json()["detail"] and "Séminaire" in r.json()["detail"]
    # La base comprise.
    assert _acces(client, projet["base"], "inconnu", "lecture").status_code == 409
    # Membre d'un AUTRE projet ne suffit pas : c'est le projet de la collection qui compte.
    assert _membre(client, projet["voisin"], "inconnu").status_code in (200, 201)
    assert _acces(client, projet["carnet"], "inconnu", "lecture").status_code == 409
    # Fait entrer dans le projet, il entre.
    assert _membre(client, projet["projet"], "inconnu").status_code in (200, 201)
    _ok(_acces(client, projet["carnet"], "inconnu", "lecture"))
    assert not _sql(projet["db"], "SELECT 1 FROM collection_acces WHERE collection_id = ? "
                                  "AND principal = 'x-jamais'", (projet["carnet"],))


def test_le_genre_compte_et_un_membre_par_un_groupe_n_entre_pas_par_son_login(client,
                                                                             projet):
    """Q2 — la RÉFÉRENCE exacte : le groupe `equipe` est du projet ; un login `equipe` n'en
    est pas, ni `mia`, membre seulement par ce groupe (l'application ne sait pas qui est
    dans un groupe hors de la requête de ce login)."""
    assert _membre(client, projet["projet"], "equipe", genre="groupe").status_code in (200, 201)
    _ok(_acces(client, projet["carnet"], "equipe", "lecture", genre="groupe"))
    r = _acces(client, projet["carnet"], "equipe", "lecture")
    assert r.status_code == 409, r.text
    r = _acces(client, projet["carnet"], "mia", "lecture")
    assert r.status_code == 409 and "groupe" in r.json()["detail"], r.text
    # Et l'inverse : un login du projet n'ouvre rien à un groupe du même nom.
    r = _acces(client, projet["carnet"], "proprio", "lecture", genre="groupe")
    assert r.status_code == 409, r.text


def test_le_refus_vient_apres_la_garde_d_administration(client, projet):
    """403 à qui lit sans posséder, 404 à qui ne lit pas : inchangés, et AVANT le 409."""
    assert _acces(client, projet["carnet"], "inconnu", "lecture",
                  qui=ECRIVAIN).status_code == 403
    assert _acces(client, projet["carnet"], "inconnu", "lecture",
                  qui=MEMBRE).status_code == 404
    # Le propriétaire, lui, reçoit le 409.
    assert _acces(client, projet["carnet"], "inconnu", "lecture",
                  qui=PROPRIO).status_code == 409


def test_le_repli_est_un_projet_comme_un_autre(client, projet, db_path):
    """Une collection du repli : on n'y entre que si l'on est du REPLI — y compris une
    collection SANS projet nommé (`sql_projet_de` : NULL se lit « le repli »)."""
    from test_projets import _repli
    repli = _repli(db_path)
    c = _collection(client, "Au repli")
    assert _acces(client, c, "nina", "lecture").status_code == 409
    _sql(db_path, "UPDATE collection SET projet_id = NULL WHERE id = ?", (c,))
    assert _acces(client, c, "nina", "lecture").status_code == 409
    assert _membre(client, repli, "nina").status_code in (200, 201)
    _ok(_acces(client, c, "nina", "lecture"))


def test_l_outil_refuse_un_proprietaire_hors_du_projet(client, projet, db_path):
    """`gerer_collections.py creer --proprietaire` : la même règle que la route, refusée
    AVANT toute écriture ; un membre du repli y est accepté."""
    from test_projets import _outil, _repli
    avant = _sql(db_path, "SELECT COUNT(*) AS n FROM collection")[0]["n"]
    code, out, err = _outil(db_path, "gerer_collections.py", "creer", "--nom", "Par l'outil",
                            "--proprietaire", "nina")
    assert code != 0 and "nina" in (err + out), (out, err)
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM collection")[0]["n"] == avant
    code, _, _ = _outil(db_path, "gerer_collections.py", "creer", "--nom", "Par l'outil",
                        "--proprietaire-groupe", "nina")
    assert code != 0
    assert _membre(client, _repli(db_path), "nina").status_code in (200, 201)
    code, out, err = _outil(db_path, "gerer_collections.py", "creer", "--nom", "Par l'outil",
                            "--proprietaire", "nina")
    assert code == 0, err
    cid = int(out.strip())
    assert _sql(db_path, "SELECT principal, niveau FROM collection_acces "
                         "WHERE collection_id = ?", (cid,)) == [
        {"principal": "nina", "niveau": "proprietaire"}]


# =========================================================================== #
# Q1 — qui sort du projet perd ses accès de collection
# =========================================================================== #
def test_qui_sort_du_projet_perd_ses_acces_de_collection(client, projet):
    """`ecrivain` sort du projet : son accès au Carnet part avec lui, journalisé (`delien`
    sous `collection_acces`) ; il ne lit plus l'album. L'accès d'un autre reste."""
    r = client.delete(f"/api/projets/{projet['projet']}/membres/utilisateur/ecrivain",
                      headers=ADMIN)
    assert r.status_code == 204, r.text
    assert not _sql(projet["db"], "SELECT 1 FROM collection_acces WHERE principal = 'ecrivain'")
    assert projet["album"] not in _albums(client, ECRIVAIN)
    actes = _sql(projet["db"], "SELECT type, cible_id, json_extract(avant, '$.principal') AS p, "
                               "json_extract(avant, '$.niveau') AS n FROM evenement "
                               "WHERE cible_table = 'collection_acces' AND type = 'delien'")
    assert actes == [{"type": "delien", "cible_id": projet["carnet"], "p": "ecrivain",
                      "n": "ecriture"}]
    assert _sql(projet["db"], "SELECT niveau FROM collection_acces WHERE principal = 'proprio'"
                ) == [{"niveau": "proprietaire"}]


def test_le_dernier_proprietaire_ne_sort_pas_du_projet(client, projet):
    """`proprio` est le seul propriétaire du Carnet : 409 nommé, rien n'a bougé ; un autre
    propriétaire désigné, il sort, et son accès avec lui."""
    url = f"/api/projets/{projet['projet']}/membres/utilisateur/proprio"
    r = client.delete(url, headers=ADMIN)
    assert r.status_code == 409 and "Carnet" in r.json()["detail"], r.text
    assert _sql(projet["db"], "SELECT 1 FROM projet_acces WHERE principal = 'proprio'")
    assert _sql(projet["db"], "SELECT 1 FROM collection_acces WHERE principal = 'proprio'")
    _ok(_acces(client, projet["carnet"], "ecrivain", "proprietaire"))
    assert client.delete(url, headers=ADMIN).status_code == 204
    assert not _sql(projet["db"], "SELECT 1 FROM collection_acces WHERE principal = 'proprio'")


def test_sortir_d_un_projet_ne_touche_pas_les_acces_d_un_autre_projet(client, projet):
    """Les accès retirés sont ceux des collections DE CE projet : `ecrivain`, membre aussi
    du Voisin où il écrit, y garde son accès."""
    assert _membre(client, projet["voisin"], "ecrivain").status_code in (200, 201)
    _ok(_acces(client, projet["c_voisin"], "ecrivain", "ecriture"))
    assert client.delete(f"/api/projets/{projet['projet']}/membres/utilisateur/ecrivain",
                         headers=ADMIN).status_code == 204
    assert _sql(projet["db"], "SELECT collection_id FROM collection_acces "
                              "WHERE principal = 'ecrivain'") == [
        {"collection_id": projet["c_voisin"]}]


# =========================================================================== #
# Q3 — le propriétaire lit les noms des membres du projet
# =========================================================================== #
def test_le_proprietaire_lit_les_membres_du_projet_sans_leurs_roles(client, projet):
    client.get("/api/moi", headers={**ECRIVAIN, "Remote-Name": "Eva Ecrivaine"})
    v = _ok(client.get(f"/api/collections/{projet['carnet']}/acces-du-projet",
                       headers=PROPRIO))
    membres = {(m["genre"], m["principal"]): m for m in v["membres"]}
    assert set(membres) == {("utilisateur", "resp"), ("utilisateur", "proprio"),
                            ("utilisateur", "ecrivain")}
    assert membres[("utilisateur", "ecrivain")]["nom"] == "Eva Ecrivaine"
    assert all(set(m) == {"genre", "principal", "nom"} for m in v["membres"])
    # Aux mêmes bornes que `…/acces` : 403 à qui lit sans posséder, 404 à qui ne lit pas.
    assert client.get(f"/api/collections/{projet['carnet']}/acces-du-projet",
                      headers=ECRIVAIN).status_code == 403
    assert client.get(f"/api/collections/{projet['carnet']}/acces-du-projet",
                      headers=MEMBRE).status_code == 404
