"""COL-3, tranche 3b (v36) — qui CRÉE une collection : un réglage du projet.

La décision (Hugo, 2026-10-21), RENVERSEMENT daté d'AUTH-3 (« créer une collection exige une
IDENTITÉ, pas un droit ») : les RESPONSABLES d'un projet et les administrateurs créent
toujours ; ses MEMBRES seulement si le projet le leur ouvre (`membres_creent_collections`,
NON par défaut) ; personne d'autre — le projet de repli compris, où une identité suffisait.
Un bac à sable n'est pas touché : son propriétaire en est responsable, ses invités y créent.
Le réglage se lit et se règle par qui gère le projet.

Le décor est celui de `test_prendre` (les sept identités de la 3a) : Étude P, dont `resp`
est responsable et `membre` membre ; `proprio` possède la Collection X sans être du projet.
"""
import pytest

from conftest import ADMIN
from test_amorcer_entre_projets import _repli
from test_prendre import (ECRIVAIN, LECTRICE, MEMBRE, PERSONNE, PROPRIO, RESP,
                          prise)  # noqa: F401
from test_projets import _sql

RESP2 = {"Remote-User": "resp2"}
ATELIER = {"Remote-User": "atelier"}


def _creer(client, qui, projet_id=None, nom="Nouvelle"):
    corps = {"nom": nom} if projet_id is None else {"nom": nom, "projet_id": projet_id}
    return client.post("/api/collections", json=corps, headers=qui)


def _regler(client, projet_id, membres, qui):
    return client.put(f"/api/projets/{projet_id}/creation-de-collections", headers=qui,
                      json={"membres": membres})


def _vue(client, qui, projet_id):
    return next((p for p in client.get("/api/projets", headers=qui).json()
                 if p["id"] == projet_id), None)


def test_le_responsable_et_l_administrateur_creent_les_autres_non(client, prise, db_path):
    p = prise["projet"]
    r = _creer(client, RESP, p, "Par la responsable")
    assert r.status_code == 201, r.text
    assert r.json()["acces"][0] == {**r.json()["acces"][0], "principal": "resp",
                                    "niveau": "proprietaire"}
    assert _creer(client, ADMIN, p, "Par l'administrateur").status_code == 201
    for qui in (MEMBRE, PROPRIO, ECRIVAIN, LECTRICE):
        r = _creer(client, qui, p)
        assert r.status_code == 403 and "responsables" in r.json()["detail"], (qui, r.text)
    # Qui ne voit pas le projet : 404, le même qu'un projet absent.
    assert (_creer(client, PERSONNE, p).status_code,
            _creer(client, PERSONNE, 99999).status_code) == (404, 404)
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM collection WHERE nom = 'Nouvelle'") == [
        {"n": 0}]


def test_le_reglage_ouvre_la_creation_aux_membres_et_a_eux_seuls(client, prise):
    p = prise["projet"]
    assert _vue(client, RESP, p)["membres_creent_collections"] is False
    assert _vue(client, MEMBRE, p)["collection_creable"] is False
    _ok = _regler(client, p, True, RESP)
    assert _ok.status_code == 200 and _ok.json()["membres_creent_collections"] is True
    assert _vue(client, MEMBRE, p)["collection_creable"] is True
    assert _creer(client, MEMBRE, p, "Par un membre").status_code == 201
    # Posséder une collection du projet sans en être membre n'y suffit pas.
    assert _creer(client, PROPRIO, p).status_code == 403
    # Refermé : rien n'est retiré, mais le geste l'est.
    assert _regler(client, p, False, RESP).status_code == 200
    assert _creer(client, MEMBRE, p, "Encore").status_code == 403
    assert any(c["nom"] == "Par un membre" for c in client.get("/api/collections",
                                                               headers=MEMBRE).json())


def test_le_reglage_se_regle_par_qui_gere_le_projet(client, prise):
    p = prise["projet"]
    for qui in (MEMBRE, LECTRICE):
        r = _regler(client, p, True, qui)
        assert r.status_code in (403, 404), (qui, r.text)
    r = _regler(client, p, True, MEMBRE)
    assert r.status_code == 403
    assert (_regler(client, p, True, PERSONNE).status_code,
            _regler(client, 99999, True, PERSONNE).status_code) == (404, 404)
    assert _regler(client, p, True, ADMIN).status_code == 200
    # Le réglage n'est rendu qu'à qui le règle.
    assert "membres_creent_collections" not in _vue(client, MEMBRE, p)


def test_le_reglage_s_ecrit_au_journal(client, prise, db_path):
    p = prise["projet"]
    _regler(client, p, True, RESP)
    _regler(client, p, True, RESP)                       # rien ne change : rien ne s'écrit
    actes = _sql(db_path, "SELECT agent, json_extract(apres, '$.membres_creent_collections') "
                          "AS v FROM evenement WHERE cible_table = 'projet' AND cible_id = ? "
                          "AND type = 'modification'", (p,))
    assert actes == [{"agent": "resp", "v": 1}]


def test_le_projet_de_repli_ne_laisse_plus_creer_qu_un_administrateur(client, prise):
    """Une identité y suffisait ; sans responsable, seul un administrateur y crée. Son
    responsable, quand il en a un, crée ; ses membres si le réglage le leur ouvre."""
    repli = _repli(client)
    for qui in (PROPRIO, ECRIVAIN, RESP, {"Remote-User": "nouvelle"}):
        assert _creer(client, qui).status_code == 403, qui
        assert _creer(client, qui, repli).status_code == 403, qui
    assert _creer(client, ADMIN, nom="Par l'administrateur").status_code == 201
    client.put(f"/api/projets/{repli}/membres", headers=ADMIN,
               json={"principal": "resp2", "role": "responsable"})
    assert _creer(client, RESP2, nom="Par la responsable du repli").status_code == 201


def test_la_nature_d_un_compte_n_y_change_rien(client, prise):
    """Un compte PARTAGÉ membre du projet crée si le projet l'ouvre à ses membres : la règle
    lit le rôle et le réglage, jamais la nature."""
    client.get("/api/moi", headers=ATELIER)
    client.patch("/api/comptes/atelier/nature", headers=ADMIN, json={"nature": "collectif"})
    p = prise["projet"]
    client.put(f"/api/projets/{p}/membres", headers=ADMIN,
               json={"principal": "atelier", "role": "membre"})
    assert _creer(client, ATELIER, p).status_code == 403
    _regler(client, p, True, RESP)
    assert _creer(client, ATELIER, p, "Par l'atelier").status_code == 201


def test_un_bac_a_sable_n_est_pas_touche(client, prise):
    """Son propriétaire en est responsable ; ses invités y créent comme avant ; le réglage
    ne s'y règle pas (409)."""
    lea, sam = {"Remote-User": "lea"}, {"Remote-User": "sam"}
    bac = client.post("/api/bac-a-sable", headers=lea).json()
    client.put(f"/api/projets/{bac['id']}/membres", headers=lea,
               json={"genre": "utilisateur", "principal": "sam", "role": "membre"})
    assert _creer(client, lea, bac["id"], "Chez Léa").status_code == 201
    assert _creer(client, sam, bac["id"], "Chez Sam").status_code == 201
    assert _vue(client, sam, bac["id"])["collection_creable"] is True
    assert _regler(client, bac["id"], False, lea).status_code == 409
    # L'administrateur n'y est rien : le bac d'un autre lui reste introuvable.
    assert _creer(client, ADMIN, bac["id"]).status_code == 404


@pytest.mark.parametrize("qui, attendu", [(RESP, True), (MEMBRE, False), (PROPRIO, False),
                                          (ADMIN, True)])
def test_la_cle_dit_la_regle(client, prise, qui, attendu):
    """`collection_creable` de `GET /api/projets` est ce que la route répond."""
    p = prise["projet"]
    v = _vue(client, qui, p)
    assert v["collection_creable"] is attendu
    assert (_creer(client, qui, p, f"Essai {qui['Remote-User']}").status_code == 201) is attendu
