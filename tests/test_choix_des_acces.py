"""AUTH-12, étape 3 — qui entre, vu du PROPRIÉTAIRE : les groupes proposés, et la vérification
d'un nom dans l'annuaire.

Tranché par Hugo le 2026-09-17 : le propriétaire voit les NOMS des groupes, sans groupes de
rôle ni d'administration, et un login TAPÉ se vérifie sans qu'aucune liste des comptes lui
soit servie. « inconnu » ne veut dire qu'« absent de l'annuaire ». Une panne ne bloque rien,
et ne ralentit aucun geste d'accès.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import annuaire  # noqa: E402
import config  # noqa: E402

from conftest import ADMIN  # noqa: E402


@pytest.fixture
def doublure(monkeypatch):
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", "doublure:")


def _collection(client, nom="Étude"):
    r = client.post("/api/collections", json={"nom": nom}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _acces(client, cid, genre, principal, niveau="lecture"):
    r = client.put(f"/api/collections/{cid}/acces", headers=ADMIN,
                   json={"genre": genre, "principal": principal, "niveau": niveau})
    assert r.status_code in (200, 201), r.text


def _verifier(client, cid, genre, nom, headers=ADMIN):
    return client.get(f"/api/collections/{cid}/annuaire/verifier",
                      params={"genre": genre, "nom": nom}, headers=headers)


# --------------------------------------------------------------------------- #
# La garde : le propriétaire de CETTE collection
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("route", ["annuaire", "annuaire/verifier"])
def test_seul_le_proprietaire_de_la_collection_y_accede(client, derriere_proxy, doublure, route):
    cid = _collection(client)
    _acces(client, cid, "utilisateur", "lectrice", "lecture")
    _acces(client, cid, "utilisateur", "redactrice", "ecriture")
    _acces(client, cid, "utilisateur", "proprio", "proprietaire")
    params = {"genre": "groupe", "nom": "annotateurs"}

    def code(login):
        return client.get(f"/api/collections/{cid}/{route}", params=params,
                          headers={"Remote-User": login}).status_code
    assert code("etranger") == 404          # rien ne fuit à qui ne la lit pas
    assert code("lectrice") == 403          # lisible : un refus NOMMÉ
    assert code("redactrice") == 403        # écrire n'est pas décider qui entre
    assert code("proprio") == 200
    assert client.get(f"/api/collections/{cid}/{route}", params=params,
                      headers=ADMIN).status_code == 200


# --------------------------------------------------------------------------- #
# Ce qui est proposé
# --------------------------------------------------------------------------- #
def test_les_groupes_proposes_sont_des_noms_sans_roles_ni_administrateurs(
        client, derriere_proxy, doublure):
    cid = _collection(client)
    d = client.get(f"/api/collections/{cid}/annuaire", headers=ADMIN).json()
    assert d["annuaire"] == {"etat": "lu", "motif": None}
    assert d["groupes"] == ["annotateurs", "cours-vide", "etudiants-bd-2026"]
    # Des noms, rien d'autre : ni id, ni membres, ni nombre de comptes (UX-4).
    assert all(isinstance(g, str) for g in d["groupes"])
    assert "comptes" not in d


def test_les_acces_accordes_portent_leur_verification(client, derriere_proxy, doublure):
    cid = _collection(client)
    _acces(client, cid, "groupe", "ancien-cours")
    _acces(client, cid, "utilisateur", "proprio", "proprietaire")
    _acces(client, cid, "groupe", "annotateurs")
    _acces(client, cid, "utilisateur", "zoe")
    d = client.get(f"/api/collections/{cid}/annuaire", headers=ADMIN).json()
    assert [(a["par"], a["login"], a["groupe"], a["verification"]) for a in d["acces"]] == [
        ("compte", "proprio", None, "trouve"),
        ("compte", "zoe", None, "inconnu"),
        ("groupe", None, "ancien-cours", "inconnu"),
        ("groupe", None, "annotateurs", "trouve"),
    ]


# --------------------------------------------------------------------------- #
# La vérification d'un nom tapé
# --------------------------------------------------------------------------- #
def test_un_nom_tape_est_trouve_ou_inconnu(client, derriere_proxy, doublure):
    cid = _collection(client)
    assert _verifier(client, cid, "utilisateur", "proprio").json() == \
        {"genre": "utilisateur", "nom": "proprio", "verification": "trouve"}
    assert _verifier(client, cid, "utilisateur", "zoe").json()["verification"] == "inconnu"
    assert _verifier(client, cid, "groupe", "annotateurs").json()["verification"] == "trouve"
    # Un login n'est pas un groupe : le genre compte.
    assert _verifier(client, cid, "groupe", "proprio").json()["verification"] == "inconnu"
    # Le nom revient normalisé comme le PUT le normalise.
    assert _verifier(client, cid, "utilisateur", "  proprio ").json()["nom"] == "proprio"


def test_inconnu_ne_veut_dire_qu_absent_de_l_annuaire(client, derriere_proxy, doublure):
    """Exclure un groupe de la LISTE est une question de proposition, pas de vérité : tapé, un
    groupe de rôle ou d'administration existe, et un compte de service aussi."""
    cid = _collection(client)
    for genre, nom in (("groupe", "lldap_admin"), ("groupe", "bd-admins"),
                       ("utilisateur", "authelia")):
        assert _verifier(client, cid, genre, nom).json()["verification"] == "trouve", nom


def test_un_genre_ou_un_nom_manquant_est_refuse(client, derriere_proxy, doublure):
    cid = _collection(client)
    r = _verifier(client, cid, "personne", "proprio")
    assert r.status_code == 422 and "Genre invalide" in r.json()["detail"]
    assert _verifier(client, cid, "utilisateur", "   ").status_code == 422


# --------------------------------------------------------------------------- #
# Sans annuaire, et quand il ne répond pas
# --------------------------------------------------------------------------- #
def test_un_annuaire_muet_ne_se_confond_pas_avec_l_absence_d_annuaire(
        client, derriere_proxy, monkeypatch):
    cid = _collection(client)
    _acces(client, cid, "groupe", "annotateurs")

    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", "doublure:panne")
    d = client.get(f"/api/collections/{cid}/annuaire", headers=ADMIN).json()
    assert (d["annuaire"]["etat"], d["groupes"]) == ("non_verifie", None)
    assert d["acces"][0]["verification"] == "non_verifie"
    assert _verifier(client, cid, "groupe", "x").json()["verification"] == "non_verifie"

    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", "")
    d = client.get(f"/api/collections/{cid}/annuaire", headers=ADMIN).json()
    assert (d["annuaire"]["etat"], d["groupes"]) == ("sans_annuaire", None)
    assert d["acces"][0]["verification"] == "sans_annuaire"
    assert _verifier(client, cid, "groupe", "x").json()["verification"] == "sans_annuaire"


def test_les_gestes_d_acces_ne_lisent_pas_l_annuaire(client, derriere_proxy, monkeypatch):
    """La liste des accès est aussi la réponse du PUT et du DELETE : si elle lisait
    l'annuaire, chaque geste attendrait un annuaire en panne."""
    def interdit():
        raise AssertionError("un geste d'accès a lu l'annuaire")
    monkeypatch.setattr(annuaire, "lire", interdit)
    cid = _collection(client)
    _acces(client, cid, "groupe", "annotateurs")
    assert client.get(f"/api/collections/{cid}/acces", headers=ADMIN).status_code == 200
    assert client.delete(f"/api/collections/{cid}/acces/groupe/annotateurs",
                         headers=ADMIN).status_code == 204
