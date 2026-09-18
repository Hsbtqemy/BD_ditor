"""AUTH-12, étape 3 — qui entre, vu du PROPRIÉTAIRE : les groupes proposés, et la vérification
d'un nom dans l'annuaire.

Tranché par Hugo le 2026-09-17 : le propriétaire voit les NOMS des groupes, sans groupes de
rôle ni d'administration, et aucune liste des comptes ne lui est servie. « inconnu » ne veut
dire qu'« absent de l'annuaire ». Une panne ne bloque rien, et ne ralentit aucun geste
d'accès.

La vérification d'un nom TAPÉ avait sa route, `…/annuaire/verifier` ; elle est retirée le
2026-09-18, l'écran ne l'ayant jamais appelée — il pose l'accès, relit, et lit la marque dans
la liste. Ce qu'elle éprouvait et qui vaut encore est éprouvé ici sur `…/annuaire`.
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


# --------------------------------------------------------------------------- #
# La garde : le propriétaire de CETTE collection
# --------------------------------------------------------------------------- #
def test_seul_le_proprietaire_de_la_collection_y_accede(client, derriere_proxy, doublure):
    cid = _collection(client)
    _acces(client, cid, "utilisateur", "lectrice", "lecture")
    _acces(client, cid, "utilisateur", "redactrice", "ecriture")
    _acces(client, cid, "utilisateur", "proprio", "proprietaire")
    def code(login):
        return client.get(f"/api/collections/{cid}/annuaire",
                          headers={"Remote-User": login}).status_code
    assert code("etranger") == 404          # rien ne fuit à qui ne la lit pas
    assert code("lectrice") == 403          # lisible : un refus NOMMÉ
    assert code("redactrice") == 403        # écrire n'est pas décider qui entre
    assert code("proprio") == 200
    assert client.get(f"/api/collections/{cid}/annuaire",
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
# Ce qui est PROPOSÉ n'est pas ce qui EXISTE
# --------------------------------------------------------------------------- #
def test_un_groupe_exclu_de_la_liste_n_est_pas_dit_inconnu(client, derriere_proxy, doublure):
    """Exclure un groupe de la LISTE est une question de proposition, pas de vérité : un
    groupe de rôle ou d'administration existe, et un compte de service aussi. « inconnu » ne
    doit vouloir dire qu'ABSENT DE L'ANNUAIRE, sans quoi la marque enverrait corriger un nom
    juste.

    Éprouvé sur `…/annuaire` depuis le 2026-09-18 : `…/annuaire/verifier` le portait, et elle
    est retirée faute d'appelant — la règle, elle, vaut toujours."""
    cid = _collection(client)
    _acces(client, cid, "groupe", "lldap_admin")
    _acces(client, cid, "groupe", "bd-admins")
    _acces(client, cid, "utilisateur", "authelia")
    d = client.get(f"/api/collections/{cid}/annuaire", headers=ADMIN).json()
    assert {a["verification"] for a in d["acces"]} == {"trouve"}
    # Et ils restent hors de ce qu'on PROPOSE, ce qui est l'autre moitié de la règle.
    assert "lldap_admin" not in d["groupes"] and "bd-admins" not in d["groupes"]


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

    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", "")
    d = client.get(f"/api/collections/{cid}/annuaire", headers=ADMIN).json()
    assert (d["annuaire"]["etat"], d["groupes"]) == ("sans_annuaire", None)
    assert d["acces"][0]["verification"] == "sans_annuaire"


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
