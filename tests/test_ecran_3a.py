"""COL-3, tranche 3a — ce que le serveur ajoute pour l'écran de la 3a (Hugo, sur maquette,
2026-10-17).

- RENDRE une copie gardée au fonds se DEMANDE par le responsable du projet de la copie (un
  genre à lui, `rendre_copie`, une demande par copie) ; un administrateur répond « Rendre à
  … » ou « Garder au fonds ». Le droit avant l'objet, 404 hors de portée, une seule demande
  en attente par copie, close quand la copie est détruite ou rendue par un autre chemin.
- La fiche d'un projet montre ses copies gardées (`GET /api/projets/{id}/copies-gardees`)
  et ses demandes, retours compris ; la vue d'un projet dit, à qui le gère, sa base et le
  nombre de ses membres.
- « Qui entre » d'une collection de BASE lit les accès que le PROJET y tient
  (`GET /api/collections/{id}/acces-du-projet`), réservé à qui administre la collection ; le
  409 « dernier propriétaire » compte les responsables du projet ; « Comptes et groupes » les
  montre « par le projet ».
- « À regarder » ne filtre plus les demandes par genre : chacune voyage avec le sien.

Le décor est celui de `test_prendre.py` (`prise`) : le projet « Étude P », `resp` responsable,
`membre` membre, sa base OUVERTE ; X (`proprio` propriétaire, `ecrivain`, `lectrice`) et Y.
"""
from conftest import ADMIN
from test_fonds import _accorder, _collection
from test_prendre import (ECRIVAIN, LECTRICE, MEMBRE, PERSONNE, PROPRIO, RESP, _copie_dans,
                          _collections_de, _prendre, _repondre, prise)  # noqa: F401
from test_projets import _sql

RESP_Q = {"Remote-User": "resp_q"}


def _gardee(client, prise, doc="d3"):
    """Une copie de `doc` prise pour X, puis retirée de X : gardée au fonds du projet P."""
    cx = _copie_dans(client, prise, doc, prise["x"])
    assert client.delete(f"/api/albums/{cx}/collections/{prise['x']}",
                         headers=PROPRIO).status_code == 204
    return cx


def _rendre(client, prise, cx, cid, qui=RESP, doc="d3"):
    return _prendre(client, cid, [{"document_id": prise["docs"][doc], "reponse": "reprendre",
                                   "album_id": cx}], qui)


def _second_projet(client):
    """Q, dont `resp_q` est responsable, avec une collection Z qu'il possède."""
    r = client.post("/api/projets", json={"nom": "Projet Q"}, headers=ADMIN)
    q = r.json()["id"]
    assert client.put(f"/api/projets/{q}/membres", headers=ADMIN,
                      json={"principal": "resp_q", "role": "responsable"}).status_code == 200
    z = _collection(client, "Collection Z", projet_id=q)
    _accorder(client, z, "resp_q", "proprietaire")
    return q, z


# =========================================================================== #
# Rendre une copie gardée au fonds
# =========================================================================== #
def test_le_responsable_demande_a_rendre_et_l_administrateur_rend(client, prise, db_path):
    cx = _gardee(client, prise)
    r = _rendre(client, prise, cx, prise["base"])
    assert r.status_code == 200, r.text
    (ligne,) = r.json()["documents"]
    assert ligne["etat"] == "demande", ligne
    d = {x["id"]: x for x in client.get("/api/demandes", headers=ADMIN).json()}[
        ligne["demande_id"]]
    assert (d["genre"], d["collection_id"], d["en_attente"]) == (
        "rendre_copie", prise["base"], True)
    assert [x["album_id"] for x in d["documents"]] == [cx]
    assert _collections_de(db_path, cx) == set(), "demander ne range rien"
    # La demande s'écrit au journal, sous la cible `demande`.
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table = 'demande' "
                         "AND cible_id = ? AND type = 'creation'",
                (ligne["demande_id"],))[0]["n"] == 1
    r = _repondre(client, ligne["demande_id"], "acceptee")
    assert r.status_code == 200, r.text
    assert (r.json()["reponse"], r.json()["documents"][0]["copie_id"]) == ("acceptee", cx)
    assert _collections_de(db_path, cx) == {prise["base"]}, "rendue, avec son travail"


def test_garder_au_fonds_laisse_la_copie_et_la_demande_se_redepose(client, prise, db_path):
    cx = _gardee(client, prise)
    demande = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]["demande_id"]
    r = _repondre(client, demande, "refusee")
    assert (r.status_code, r.json()["reponse"]) == (200, "refusee")
    assert _collections_de(db_path, cx) == set()
    again = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]
    assert again["etat"] == "demande" and again["demande_id"] != demande


def test_un_retour_ne_s_attend_qu_une_fois_par_copie(client, prise):
    """Le doublon se lit par COPIE : la même copie demandée pour une AUTRE collection du
    projet est refusée tant que la première attend."""
    cx = _gardee(client, prise)
    _accorder(client, prise["y"], "resp", "ecriture")
    assert _rendre(client, prise, cx, prise["base"]).json()["documents"][0]["etat"] == "demande"
    second = _rendre(client, prise, cx, prise["y"]).json()["documents"][0]
    assert second["etat"] == "refuse" and "déjà demandé" in second["motif"], second


def test_le_responsable_d_un_autre_projet_n_atteint_rien(client, prise, db_path):
    """Le droit avant l'objet : `resp_q` ne voit ni le projet P (404 sur ses copies gardées),
    ni sa collection (404 sur la prise) ; depuis sa propre collection, la copie gardée de P
    n'est pas une copie de SON projet — le même refus qu'une copie qui n'existe pas."""
    cx = _gardee(client, prise)
    _q, z = _second_projet(client)
    assert client.get(f"/api/projets/{prise['projet']}/copies-gardees",
                      headers=RESP_Q).status_code == 404
    assert _rendre(client, prise, cx, prise["base"], RESP_Q).status_code == 404
    r = _rendre(client, prise, cx, z, RESP_Q)
    assert r.status_code == 200, r.text
    assert r.json()["documents"][0]["etat"] == "refuse", r.json()
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM demande WHERE genre = 'rendre_copie'"
                )[0]["n"] == 0


def test_seul_qui_tient_le_fonds_repond_a_un_retour(client, prise):
    """Le responsable possède la base (dérivé) sans tenir le fonds : un retour lui est
    INTROUVABLE, comme toute demande qu'il ne peut pas connaître."""
    cx = _gardee(client, prise)
    demande = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]["demande_id"]
    for qui in (RESP, PROPRIO):
        assert _repondre(client, demande, "acceptee", qui=qui).status_code == 404
    assert _repondre(client, demande, "acceptee", qui=PERSONNE).status_code == 403


def test_un_retour_ne_se_depose_pas_par_les_demandes(client, prise):
    cx = _gardee(client, prise)
    r = client.post("/api/demandes", headers=RESP,
                    json={"genre": "rendre_copie", "album_id": cx, "motif": "x"})
    assert r.status_code == 422 and "prendre" in r.json()["detail"], r.text


def test_detruire_la_copie_clot_son_retour(client, prise, db_path):
    cx = _gardee(client, prise)
    demande = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]["demande_id"]
    assert client.delete(f"/api/albums/{cx}", headers=ADMIN).status_code == 204
    assert _sql(db_path, "SELECT reponse FROM demande WHERE id = ?", (demande,)) \
        == [{"reponse": "refusee"}]


def test_rendue_depuis_le_fonds_la_copie_clot_son_retour(client, prise, db_path):
    """L'administrateur rend la copie depuis la fiche du document (« Rendre ») : le retour
    demandé a reçu ce qu'il demandait, et ne reste pas dans « À faire »."""
    cx = _gardee(client, prise)
    demande = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]["demande_id"]
    assert client.put(f"/api/albums/{cx}/collections/{prise['x']}",
                      headers=ADMIN).status_code == 201
    vue = {x["id"]: x for x in client.get("/api/demandes", headers=ADMIN).json()}[demande]
    assert (vue["reponse"], vue["documents"][0]["copie_id"]) == ("acceptee", cx)


def test_l_administrateur_reprend_et_clot_le_retour(client, prise, db_path):
    cx = _gardee(client, prise)
    demande = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]["demande_id"]
    r = _rendre(client, prise, cx, prise["y"], ADMIN)
    assert r.json()["documents"][0]["etat"] == "fait"
    # Close acceptée, et la demande dit où la copie est RÉELLEMENT revenue — Y, pas la base
    # demandée (relecture croisée, défaut 2) ; qui l'a rangée y répond.
    assert _sql(db_path, "SELECT reponse, collection_id, collection_nom, repondu_par "
                         "FROM demande WHERE id = ?", (demande,)) \
        == [{"reponse": "acceptee", "collection_id": prise["y"],
             "collection_nom": "Collection Y", "repondu_par": "decor"}]


# =========================================================================== #
# La fiche du projet : copies gardées, demandes, base
# =========================================================================== #
def test_les_copies_gardees_se_lisent_par_le_responsable(client, prise):
    cx = _gardee(client, prise)
    r = client.get(f"/api/projets/{prise['projet']}/copies-gardees", headers=RESP)
    assert r.status_code == 200, r.text
    (c,) = r.json()
    assert set(c) == {"album_id", "document_id", "titre", "serie", "auteur", "garde_depuis",
                      "retour"}
    assert (c["album_id"], c["retour"]) == (cx, None) and c["garde_depuis"]
    demande = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]["demande_id"]
    (c,) = client.get(f"/api/projets/{prise['projet']}/copies-gardees", headers=RESP).json()
    assert (c["retour"]["id"], c["retour"]["collection_id"]) == (demande, prise["base"])
    assert client.get(f"/api/projets/{prise['projet']}/copies-gardees",
                      headers=MEMBRE).status_code == 403
    assert client.get(f"/api/projets/{prise['projet']}/copies-gardees",
                      headers=PERSONNE).status_code == 404


def test_les_demandes_du_projet_disent_aussi_les_retours(client, prise):
    cx = _gardee(client, prise)
    demande = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]["demande_id"]
    vues = {d["id"]: d for d in client.get(f"/api/projets/{prise['projet']}/demandes",
                                           headers=RESP).json()}
    assert vues[demande]["genre"] == "rendre_copie"
    assert vues[demande]["documents"][0]["reprise"] is True


def test_la_vue_d_un_projet_dit_sa_base_a_qui_le_gere(client, prise):
    vues = {p["id"]: p for p in client.get("/api/projets", headers=RESP).json()}
    p = vues[prise["projet"]]
    assert p["base"] == {"id": prise["base"], "nom": "Étude P", "acces_membres": "ecriture"}
    assert p["nb_membres"] == 1
    simple = {p["id"]: p for p in client.get("/api/projets", headers=MEMBRE).json()}[
        prise["projet"]]
    assert "base" not in simple and "nb_membres" not in simple


def test_la_creation_d_un_projet_pose_la_position_demandee(client, prise, db_path):
    r = client.post("/api/projets", json={"nom": "Projet R", "acces_membres": "lecture"},
                    headers=ADMIN)
    assert r.status_code == 201, r.text
    assert r.json()["base"]["acces_membres"] == "lecture"
    r = client.post("/api/projets", json={"nom": "Projet S", "acces_membres": None},
                    headers=ADMIN)
    assert r.json()["base"]["acces_membres"] is None


# =========================================================================== #
# « Qui entre » : l'accès tenu par le projet
# =========================================================================== #
def test_qui_entre_dans_la_base_par_le_projet(client, prise):
    r = client.get(f"/api/collections/{prise['base']}/acces-du-projet", headers=RESP)
    assert r.status_code == 200, r.text
    corps = r.json()
    assert (corps["base"], corps["projet_id"], corps["gerable"], corps["acces_membres"]) == (
        True, prise["projet"], True, "ecriture")
    assert corps["lignes"] == [
        {"genre": "utilisateur", "principal": "resp", "niveau": "proprietaire",
         "exporter": True, "role": "responsable"},
        {"genre": "utilisateur", "principal": "membre", "niveau": "ecriture",
         "exporter": False, "role": "membre"}]
    # La liste explicite, elle, ne change pas : la base n'a aucune ligne d'accès.
    assert client.get(f"/api/collections/{prise['base']}/acces", headers=RESP).json() == []


def test_l_acces_du_projet_suit_la_position(client, prise):
    assert client.put(f"/api/projets/{prise['projet']}/acces-membres", headers=RESP,
                      json={"acces_membres": None}).status_code == 200
    lignes = client.get(f"/api/collections/{prise['base']}/acces-du-projet",
                        headers=RESP).json()["lignes"]
    assert [x["principal"] for x in lignes] == ["resp"], "protégée : le membre n'entre pas"


def test_l_acces_du_projet_se_lit_par_qui_administre_la_collection(client, prise):
    """Une donnée sur des PERSONNES : les bornes de `…/acces`. Le membre écrit dans la base
    sans la posséder (403 nommé) ; qui ne la lit pas reçoit un 404."""
    assert client.get(f"/api/collections/{prise['base']}/acces-du-projet",
                      headers=MEMBRE).status_code == 403
    for qui in (PERSONNE, PROPRIO, LECTRICE):
        assert client.get(f"/api/collections/{prise['base']}/acces-du-projet",
                          headers=qui).status_code == 404, qui
    autre = client.get(f"/api/collections/{prise['x']}/acces-du-projet", headers=PROPRIO)
    assert autre.status_code == 200
    assert (autre.json()["base"], autre.json()["lignes"], autre.json()["gerable"]) == (
        False, [], False)


def test_le_dernier_proprietaire_explicite_d_une_base_se_retire_si_un_responsable_la_tient(
        client, prise):
    _accorder(client, prise["base"], "proprio", "proprietaire")
    r = client.delete(f"/api/collections/{prise['base']}/acces/utilisateur/proprio",
                      headers=RESP)
    assert r.status_code == 204, r.text
    # Un projet SANS responsable : la ligne explicite est la dernière, le 409 tient.
    t = client.post("/api/projets", json={"nom": "Projet T"}, headers=ADMIN).json()
    _accorder(client, t["base"]["id"], "proprio", "proprietaire")
    r = client.delete(f"/api/collections/{t['base']['id']}/acces/utilisateur/proprio",
                      headers=PROPRIO)
    assert r.status_code == 409 and "dernier propriétaire" in r.json()["detail"], r.text
    # Une collection ordinaire n'a personne par le projet : son dernier propriétaire reste.
    r = client.delete(f"/api/collections/{prise['x']}/acces/utilisateur/proprio",
                      headers=PROPRIO)
    assert r.status_code == 409 and "dernier propriétaire" in r.json()["detail"], r.text


def test_comptes_et_groupes_montre_l_entree_par_le_projet(client, prise):
    vue = client.get("/api/comptes-et-groupes", headers=ADMIN).json()
    membre = next(c for c in vue["comptes"] if c["login"] == "membre")
    (ligne,) = [x for x in membre["collections"] if x["id"] == prise["base"]]
    assert (ligne["par"], ligne["par_projet"], ligne["niveau"]) == ("projet", "Étude P",
                                                                    "ecriture")
    base = next(c for c in vue["collections"] if c["id"] == prise["base"])
    assert [p["login"] for p in base["proprietaires"]] == ["resp"]
    assert base["proprietaires"][0]["par_projet"] == "Étude P"
    assert "sans_proprietaire" not in base["signaux"]
    # Les accès explicites ne se comptent pas avec eux.
    assert base["nb_acces"] == 0


# =========================================================================== #
# Le fonds : la provenance de chaque copie ; « À regarder » de tous les genres
# =========================================================================== #
def test_le_fonds_dit_qui_a_cree_chaque_copie(client, prise):
    cx = _copie_dans(client, prise, "d1", prise["x"])
    doc = next(d for d in client.get("/api/fonds", headers=ADMIN).json()["documents"]
               if d["id"] == prise["docs"]["d1"])
    copies = {c["album_id"]: c for c in doc["copies"]}
    assert (copies[cx]["cran"], copies[cx]["creee_par"]) == ("images", "decor")
    assert copies[prise["albums"]["d1"]]["cran"] == "origine"
    assert copies[prise["albums"]["d1"]]["creee_par"] == "importeur"


def test_le_fonds_dit_le_retour_qui_attend_sur_une_copie(client, prise):
    cx = _gardee(client, prise)
    demande = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]["demande_id"]
    doc = next(d for d in client.get("/api/fonds", headers=ADMIN).json()["documents"]
               if d["id"] == prise["docs"]["d3"])
    (c,) = [c for c in doc["copies"] if c["album_id"] == cx]
    assert c["retour"]["id"] == demande


def test_a_regarder_porte_toute_demande_avec_son_genre(client, prise):
    cx = _gardee(client, prise)
    demande = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]["demande_id"]
    signaux = client.get("/api/comptes-et-groupes", headers=ADMIN).json()["a_regarder"]
    assert {"signal": "demande_en_attente", "demande": demande, "genre": "rendre_copie"} \
        in signaux


# =========================================================================== #
# Les corrections de la relecture croisée (2026-10-17)
# =========================================================================== #
def test_un_rejoindre_se_clot_quand_sa_copie_part_au_fonds(client, prise, db_path):
    """Accepter un `rejoindre` sur une copie gardée la rendrait sans son responsable, sous
    les mots « ranger aussi » : partie au fonds, la copie clôt les `rejoindre` qui la
    visaient — refusés, au nom de qui l'a retirée. La reprendre relève du retour."""
    cx = _copie_dans(client, prise, "d3", prise["x"])
    r = _prendre(client, prise["y"], [{"document_id": prise["docs"]["d3"],
                                       "reponse": "rejoindre", "album_id": cx}], ECRIVAIN)
    rejoindre = r.json()["documents"][0]["demande_id"]
    assert client.delete(f"/api/albums/{cx}/collections/{prise['x']}",
                         headers=PROPRIO).status_code == 204
    assert _sql(db_path, "SELECT reponse, repondu_par FROM demande WHERE id = ?",
                (rejoindre,)) == [{"reponse": "refusee", "repondu_par": "proprio"}]
    assert _repondre(client, rejoindre, "acceptee").status_code == 409
    assert _collections_de(db_path, cx) == set()


def test_un_rejoindre_ne_se_clot_pas_quand_la_copie_reste_rangee(client, prise, db_path):
    """Sortir la copie d'UNE collection sans qu'elle parte au fonds ne clôt rien."""
    cx = _copie_dans(client, prise, "d3", prise["x"])
    assert client.put(f"/api/albums/{cx}/collections/{prise['base']}",
                      headers=ADMIN).status_code == 201
    autre = _collection(client, "Collection W", projet_id=prise["projet"])
    _accorder(client, autre, "ecrivain", "ecriture")
    r = _prendre(client, autre, [{"document_id": prise["docs"]["d3"],
                                  "reponse": "rejoindre", "album_id": cx}], ECRIVAIN)
    rejoindre = r.json()["documents"][0]["demande_id"]
    assert client.delete(f"/api/albums/{cx}/collections/{prise['x']}",
                         headers=ADMIN).status_code == 204
    assert _sql(db_path, "SELECT reponse FROM demande WHERE id = ?", (rejoindre,)) \
        == [{"reponse": None}]


def test_l_outil_qui_retire_au_fonds_clot_aussi_les_rejoindre(client, prise, db_path):
    from test_projets import _outil
    cx = _copie_dans(client, prise, "d3", prise["x"])
    r = _prendre(client, prise["y"], [{"document_id": prise["docs"]["d3"],
                                       "reponse": "rejoindre", "album_id": cx}], ECRIVAIN)
    rejoindre = r.json()["documents"][0]["demande_id"]
    code, _, err = _outil(db_path, "gerer_collections.py", "retirer", str(prise["x"]),
                          "--albums", str(cx))
    assert code == 0, err
    assert _sql(db_path, "SELECT reponse FROM demande WHERE id = ?", (rejoindre,)) \
        == [{"reponse": "refusee"}]


def test_rendre_une_copie_qui_n_est_plus_gardee_se_refuse_en_le_disant(client, prise, db_path):
    """La garde de « Rendre à … » : une copie rangée entre-temps hors de tout chemin
    d'écriture (base retouchée à la main) n'est plus gardée — 409 nommé, la demande reste."""
    cx = _gardee(client, prise)
    demande = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]["demande_id"]
    _sql(db_path, "INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
         (prise["y"], cx))
    r = _repondre(client, demande, "acceptee")
    assert r.status_code == 409 and "plus gardé au fonds" in r.json()["detail"], r.text
    assert _sql(db_path, "SELECT reponse FROM demande WHERE id = ?", (demande,)) \
        == [{"reponse": None}]


def test_le_retour_dit_a_l_administrateur_d_ou_la_copie_etait_sortie(client, prise):
    cx = _gardee(client, prise)                    # sortie de « Collection X »
    demande = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]["demande_id"]
    vue = {d["id"]: d for d in client.get("/api/demandes", headers=ADMIN).json()}[demande]
    assert vue["sortie_de"] == "Collection X"


def test_le_depart_d_un_compte_compte_ses_entrees_de_projet(client, prise):
    vue = client.get("/api/comptes-et-groupes", headers=ADMIN).json()
    membre = next(c for c in vue["comptes"] if c["login"] == "membre")
    assert (membre["entrees_projet"], membre["verdict"]) == (1, "laisse des entrées de projet")
    resp = next(c for c in vue["comptes"] if c["login"] == "resp")
    assert resp["verdict"] == ("laisse des entrées de projet et une collection de base sans "
                               "autre propriétaire")


def test_un_compte_absent_qui_n_a_qu_une_entree_de_projet_est_signale(
        client, prise, monkeypatch):
    """Avec l'annuaire de la doublure, où ni `membre` ni `resp` n'existent : leur seule
    trace est une entrée de projet, et le signal « compte absent » le dit."""
    import config
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", "doublure:")
    vue = client.get("/api/comptes-et-groupes", headers=ADMIN).json()
    assert vue["annuaire"]["etat"] == "lu", vue["annuaire"]
    membre = next(c for c in vue["comptes"] if c["login"] == "membre")
    assert "compte_absent" in membre["signaux"]
    assert {"signal": "compte_absent", "login": "membre", "collection": prise["base"]} \
        in vue["a_regarder"]
