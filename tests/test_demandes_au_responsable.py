"""COL-3, tranche 3c — les demandes d'effacement vont au RESPONSABLE du projet, et une
planche se demande aussi (F4, F5 ; Q5, Q7, Q8, Q10, Q12, Q14 ; Hugo, 2026-10-26).

- Le destinataire se DÉRIVE de `demande.projet_id` au moment de répondre (Q10) : les
  responsables non partagés du projet ; l'administrateur seul pour la DERNIÈRE copie d'un
  document (suppression d'album), une copie gardée au fonds (Q12), un projet sans
  responsable, un responsable compte partagé (Q14). L'administrateur répond toujours, en
  recours. Le propriétaire de toutes les collections n'est pas destinataire (Q8).
- `repondable` = à qui elle s'adresse ET la clause d'effacement de qui répond.
- Déposer : qui écrit dans l'album, ou qui gère son projet (Q7) ; une lectrice, non.
- Une planche : `suppression_planche`, ou `repartir` avec `planche_id` — la règle de repartir
  de zéro (Q5) ; la planche relue sur son album ; les clôtures.

Le décor : « Séminaire », `resp` responsable, `proprio` propriétaire du « Carnet » où
`ecrivain` écrit. Dans le Carnet, « Seul » (la seule copie de son document) et « Doublé »
(qui a une sœur dans la base) ; une planche chacun.
"""
import pytest

from conftest import ADMIN, make_png
from test_fonds import _accorder
from test_projets import _collection, _membre, _projet, _sql

RESP = {"Remote-User": "resp"}
PROPRIO = {"Remote-User": "proprio"}
ECRIVAIN = {"Remote-User": "ecrivain"}
LECTRICE = {"Remote-User": "lectrice"}
AUTRE = {"Remote-User": "autre-resp"}


def _ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.text)
    return r.json() if r.content else None


def _planche(client, album_id, qui):
    return _ok(client.post(f"/api/albums/{album_id}/import", headers=qui,
                           files={"file": ("p.png", make_png(), "image/png")}), 201)["id"]


def _demander(client, qui, genre="suppression_document", **champs):
    corps = {"genre": genre, "motif": "Fausse piste", "certifie": True, **champs}
    return client.post("/api/demandes", headers=qui, json=corps)


def _repondre(client, demande_id, reponse, qui):
    return client.post(f"/api/demandes/{demande_id}/reponse", headers=qui,
                       json={"reponse": reponse})


@pytest.fixture
def d(client, derriere_proxy, db_path):
    pid = _projet(client, "Séminaire")
    assert _membre(client, pid, "resp", role="responsable").status_code in (200, 201)
    carnet = _collection(client, "Carnet", projet_id=pid)
    _accorder(client, carnet, "proprio", "proprietaire")
    _accorder(client, carnet, "ecrivain", "ecriture")
    _accorder(client, carnet, "lectrice", "lecture")
    seul = _ok(client.post("/api/albums", headers=ECRIVAIN,
                           json={"titre": "Seul", "collection_id": carnet}), 201)["id"]
    double = _ok(client.post("/api/albums", headers=ECRIVAIN,
                             json={"titre": "Doublé", "collection_id": carnet}), 201)["id"]
    pl_seul, pl_double = _planche(client, seul, ECRIVAIN), _planche(client, double, ECRIVAIN)
    base = _sql(db_path, "SELECT id FROM collection WHERE base = 1 AND projet_id = ?",
                (pid,))[0]["id"]
    doc = _sql(db_path, "SELECT document_id FROM albums WHERE id = ?", (double,))[0][
        "document_id"]
    r = _ok(client.post(f"/api/collections/{base}/prendre", headers=ADMIN,
                        json={"documents": [{"document_id": doc, "reponse": "zero",
                                             "album_id": double}]}))
    assert r["documents"][0]["etat"] == "fait", r
    autre = _projet(client, "Voisin")
    assert _membre(client, autre, "autre-resp", role="responsable").status_code in (200, 201)
    return {"projet": pid, "carnet": carnet, "seul": seul, "double": double,
            "pl_seul": pl_seul, "pl_double": pl_double, "base": base, "autre": autre,
            "db": db_path}


def _recues(client, d, qui=RESP):
    return {x["id"]: x for x in _ok(client.get(
        f"/api/projets/{d['projet']}/demandes-d-effacement", headers=qui))}


# =========================================================================== #
# F4 — au responsable du projet
# =========================================================================== #
def test_le_responsable_lit_la_demande_et_l_accepte(client, d):
    did = _ok(_demander(client, ECRIVAIN, album_id=d["double"]), 201)["id"]
    x = _recues(client, d)[did]
    assert (x["demandeur"], x["titre"], x["album_id"], x["derniere_copie"], x["repondable"]) \
        == ("ecrivain", "Doublé", d["double"], False, True)
    assert x["motif"] and x["certifie_le"]
    assert "travail_des_autres" in x
    vue = _ok(_repondre(client, did, "acceptee", RESP))
    assert vue["reponse"] == "acceptee"
    assert not _sql(d["db"], "SELECT 1 FROM albums WHERE id = ?", (d["double"],))


def test_la_derniere_copie_va_a_l_administrateur(client, d):
    """« Seul » est la dernière copie de son document : `resp` lit la demande, ne peut ni
    l'accepter ni la refuser (403 nommé) ; l'administrateur, si — et `attend` le lui dit."""
    did = _ok(_demander(client, ECRIVAIN, album_id=d["seul"]), 201)["id"]
    x = _recues(client, d)[did]
    assert (x["derniere_copie"], x["repondable"]) == (True, False)
    for reponse in ("acceptee", "refusee"):
        r = _repondre(client, did, reponse, RESP)
        assert r.status_code == 403 and "dernière copie" in r.json()["detail"], r.text
    vues = {v["id"]: v for v in _ok(client.get("/api/demandes", headers=ADMIN))}
    assert vues[did]["attend"] == []
    double = _ok(_demander(client, ECRIVAIN, album_id=d["double"]), 201)["id"]
    vues = {v["id"]: v for v in _ok(client.get("/api/demandes", headers=ADMIN))}
    assert vues[double]["attend"] == ["resp"]
    _ok(_repondre(client, did, "acceptee", ADMIN))
    assert not _sql(d["db"], "SELECT 1 FROM albums WHERE id = ?", (d["seul"],))


def test_repartir_de_la_derniere_copie_revient_au_responsable(client, d):
    """Q6 : repartir de zéro ne connaît pas la règle de la dernière copie — `resp` y répond."""
    _ok(client.post(f"/api/planches/{d['pl_seul']}/regions", headers=ECRIVAIN,
                    json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9}), 201)
    did = _ok(_demander(client, ECRIVAIN, genre="repartir", album_id=d["seul"],
                        cran="images"), 201)["id"]
    assert _recues(client, d)[did]["repondable"] is True
    _ok(_repondre(client, did, "acceptee", RESP))
    assert not _sql(d["db"], "SELECT 1 FROM regions WHERE planche_id = ?", (d["pl_seul"],))


def test_qui_n_est_pas_destinataire_ne_connait_pas_la_demande(client, d):
    """Le responsable d'un AUTRE projet : 404 sur la demande, 404 ou 403 sur la liste ; le
    propriétaire du Carnet, qui efface lui-même, n'est pas destinataire (Q8)."""
    did = _ok(_demander(client, ECRIVAIN, album_id=d["double"]), 201)["id"]
    assert _repondre(client, did, "refusee", AUTRE).status_code in (403, 404)
    assert client.get(f"/api/projets/{d['projet']}/demandes-d-effacement",
                      headers=AUTRE).status_code == 404
    assert _repondre(client, did, "refusee", PROPRIO).status_code == 404
    assert client.get(f"/api/projets/{d['projet']}/demandes-d-effacement",
                      headers=PROPRIO).status_code in (403, 404)
    assert _sql(d["db"], "SELECT reponse FROM demande WHERE id = ?", (did,)) == [
        {"reponse": None}]


def test_un_responsable_compte_partage_n_est_jamais_destinataire(client, d):
    """Q14 — déclaré partagé, `resp` ne répond plus (403), et `attend` ne le nomme pas : la
    demande va à l'administrateur."""
    did = _ok(_demander(client, ECRIVAIN, album_id=d["double"]), 201)["id"]
    client.get("/api/moi", headers=RESP)
    _ok(client.patch("/api/comptes/resp/nature", headers=ADMIN, json={"nature": "collectif"}))
    assert _recues(client, d)[did]["repondable"] is False
    assert _repondre(client, did, "acceptee", RESP).status_code == 403
    vues = {v["id"]: v for v in _ok(client.get("/api/demandes", headers=ADMIN))}
    assert vues[did]["attend"] == []


def test_le_responsable_lit_qui_demande_sur_la_liste_des_albums(client, d):
    _ok(_demander(client, ECRIVAIN, album_id=d["double"]), 201)
    vu = next(a for a in _ok(client.get("/api/albums", headers=RESP)) if a["id"] == d["double"])
    assert vu["demande"]["demandeur"] == "ecrivain"
    vu = next(a for a in _ok(client.get("/api/albums", headers=LECTRICE))
              if a["id"] == d["double"])
    assert set(vu["demande"]) == {"id", "date_creation"}


# =========================================================================== #
# Q7 — qui dépose
# =========================================================================== #
def test_qui_depose_une_demande(client, d):
    """Qui écrit, ou qui GÈRE le projet — `resp` lit « Seul » sans y écrire, et demande au
    administrateur la dernière copie ; une lectrice, non (404)."""
    assert _demander(client, LECTRICE, album_id=d["seul"]).status_code == 404
    did = _ok(_demander(client, RESP, album_id=d["seul"]), 201)["id"]
    assert _sql(d["db"], "SELECT demandeur, projet_id FROM demande WHERE id = ?", (did,)) == [
        {"demandeur": "resp", "projet_id": d["projet"]}]
    r = _demander(client, ECRIVAIN, album_id=d["seul"])
    assert r.status_code == 409 and "administrateur" in r.json()["detail"]
    r = _demander(client, LECTRICE, album_id=d["double"])
    assert r.status_code == 404
    _ok(_demander(client, ECRIVAIN, album_id=d["double"]), 201)
    r = _demander(client, ECRIVAIN, album_id=d["double"])
    assert r.status_code == 409 and "responsable du projet" in r.json()["detail"]


# =========================================================================== #
# F5 — une planche se demande
# =========================================================================== #
def test_une_planche_se_demande_et_le_responsable_la_supprime(client, d):
    """La certification exigée (422) ; une seule en attente (409) ; acceptée par `resp`, la
    planche part — même d'une dernière copie (Q5) — et la demande se clôt ; la ligne de la
    planche disait « demandée »."""
    pl = d["pl_seul"]
    r = _demander(client, ECRIVAIN, genre="suppression_planche", planche_id=pl,
                  certifie=False)
    assert r.status_code == 422
    did = _ok(_demander(client, ECRIVAIN, genre="suppression_planche", planche_id=pl), 201)["id"]
    assert _sql(d["db"], "SELECT planche_id, planche_numero FROM demande WHERE id = ?",
                (did,)) == [{"planche_id": pl, "planche_numero": 1}]
    assert _demander(client, ECRIVAIN, genre="suppression_planche",
                     planche_id=pl).status_code == 409
    planches = _ok(client.get(f"/api/albums/{d['seul']}/planches", headers=ECRIVAIN))
    assert planches[0]["demande"]["genre"] == "suppression_planche"
    assert planches[0]["demande"]["demandeur"] == "ecrivain"
    lue = _ok(client.get(f"/api/albums/{d['seul']}/planches", headers=LECTRICE))[0]["demande"]
    assert "demandeur" not in lue
    x = _recues(client, d)[did]
    assert (x["planche_id"], x["planche_numero"], x["repondable"]) == (pl, 1, True)
    _ok(_repondre(client, did, "acceptee", RESP))
    assert not _sql(d["db"], "SELECT 1 FROM planches WHERE id = ?", (pl,))
    assert _sql(d["db"], "SELECT reponse FROM demande WHERE id = ?", (did,)) == [
        {"reponse": "acceptee"}]


def test_qui_peut_le_faire_lui_meme_ne_demande_pas_une_planche(client, d):
    r = _demander(client, PROPRIO, genre="suppression_planche", planche_id=d["pl_seul"])
    assert r.status_code == 409 and "vous-même" in r.json()["detail"]
    assert _demander(client, LECTRICE, genre="suppression_planche",
                     planche_id=d["pl_seul"]).status_code == 404


def test_une_planche_d_un_autre_album_ne_se_supprime_pas_par_la_demande(client, d):
    """La planche relue sur SON album : une demande qui nommerait la planche d'un autre album
    (base retouchée) se refuse (409), sans rien supprimer."""
    did = _ok(_demander(client, ECRIVAIN, genre="suppression_planche",
                        planche_id=d["pl_seul"]), 201)["id"]
    _sql(d["db"], "UPDATE demande SET planche_id = ? WHERE id = ?", (d["pl_double"], did))
    r = _repondre(client, did, "acceptee", ADMIN)
    assert r.status_code == 409 and "refusez" in r.json()["detail"], r.text
    assert _sql(d["db"], "SELECT 1 FROM planches WHERE id = ?", (d["pl_double"],))


def test_une_planche_se_remet_a_zero_sur_demande(client, d):
    pl = d["pl_seul"]
    _ok(client.post(f"/api/planches/{pl}/regions", headers=ECRIVAIN,
                    json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9}), 201)
    r = client.post(f"/api/planches/{pl}/repartir", headers=ECRIVAIN, json={"cran": "images"})
    assert r.status_code == 403 and "demander" in r.json()["detail"]
    did = _ok(_demander(client, ECRIVAIN, genre="repartir", planche_id=pl, cran="images"),
              201)["id"]
    _ok(_repondre(client, did, "acceptee", RESP))
    assert not _sql(d["db"], "SELECT 1 FROM regions WHERE planche_id = ?", (pl,))


def test_les_demandes_d_une_planche_se_closent(client, d):
    """Supprimer la planche par un autre chemin clôt ses demandes (acceptées) ; une
    suppression de l'ALBUM qui attend refuse qu'on demande une de ses planches (409) ;
    détruire l'album clôt la suppression d'une planche (acceptée) et sa remise à zéro
    (refusée)."""
    pl = d["pl_double"]
    did = _ok(_demander(client, ECRIVAIN, genre="suppression_planche", planche_id=pl), 201)["id"]
    _ok(client.delete(f"/api/planches/{pl}", headers=PROPRIO), 204)
    assert _sql(d["db"], "SELECT reponse FROM demande WHERE id = ?", (did,)) == [
        {"reponse": "acceptee"}]
    pl2 = _planche(client, d["seul"], ECRIVAIN)
    _ok(client.post(f"/api/planches/{pl2}/regions", headers=ECRIVAIN,
                    json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9}), 201)
    sup = _ok(_demander(client, ECRIVAIN, genre="suppression_planche", planche_id=d["pl_seul"]),
              201)["id"]
    rep = _ok(_demander(client, ECRIVAIN, genre="repartir", planche_id=pl2, cran="images"),
              201)["id"]
    _ok(_demander(client, ECRIVAIN, album_id=d["seul"]), 201)
    assert _demander(client, ECRIVAIN, genre="suppression_planche",
                     planche_id=pl2).status_code == 409
    _ok(client.delete(f"/api/albums/{d['seul']}", headers=ADMIN), 204)
    assert {r["id"]: r["reponse"] for r in _sql(
        d["db"], "SELECT id, reponse FROM demande WHERE id IN (?, ?)", (sup, rep))} == {
        sup: "acceptee", rep: "refusee"}


def test_la_liste_ne_lit_que_son_projet(client, d):
    """Une demande d'un AUTRE projet n'apparaît pas dans la liste de `resp` — il y lirait
    des noms, des motifs et « qui perd quoi » d'un projet qu'il ne gère pas — même s'il en
    lit la copie."""
    ailleurs = _collection(client, "Ailleurs", projet_id=d["autre"])
    _accorder(client, ailleurs, "ecrivain", "ecriture")
    _accorder(client, ailleurs, "resp", "lecture")
    a = _ok(client.post("/api/albums", headers=ECRIVAIN,
                        json={"titre": "Voisin", "collection_id": ailleurs}), 201)["id"]
    did = _ok(_demander(client, ECRIVAIN, album_id=a), 201)["id"]
    ici = _ok(_demander(client, ECRIVAIN, album_id=d["double"]), 201)["id"]
    recues = _recues(client, d)
    assert ici in recues and did not in recues
    assert did in {x["id"] for x in _ok(client.get(
        f"/api/projets/{d['autre']}/demandes-d-effacement", headers=AUTRE))}


def test_peut_repondre_a_une_demande_d_effacement_aux_extremites():
    """La question, lue seule : le RESPONSABLE du projet de la demande (`projet`), et la
    portée totale ; un simple membre, non — ni le responsable d'un autre projet."""
    import autorisation
    P = autorisation.Portee
    for genre in ("suppression_document", "suppression_planche", "repartir"):
        d = {"genre": genre, "projet": 7}
        assert P(projets_geres=frozenset({7}), utilisateur="r").peut_repondre_a(d) is True
        assert P(projets=frozenset({7}), utilisateur="m").peut_repondre_a(d) is False
        assert P(projets_geres=frozenset({8}), utilisateur="a").peut_repondre_a(d) is False
        assert autorisation.TOTALE.peut_repondre_a(d) is True
        assert P(projets_geres=frozenset({7}), utilisateur="r").peut_repondre_a(
            {"genre": genre, "projet": None}) is False
