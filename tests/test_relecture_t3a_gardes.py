"""COL-3, tranche 3a — relecture croisée : quatre gardes de la prise qui TIENNENT, mais
qu'aucun test de la suite ne tenait. Chacune a été retirée par un mutant, et la suite des
fichiers de la tranche (test_prendre, test_creer_copie, test_copies_soeurs, test_fonds,
test_destruction, test_projets…) restait verte. Ces tests passent sur `16bf291` et
tombent sous le mutant qu'ils nomment.

- `prendre` : écrire dans la collection d'ARRIVÉE. Le seul test (`LECTRICE` sur X) mourait
  avant la garde, sur le document qu'elle ne pouvait pas nommer ; une lectrice qui LIT une
  copie du document dans le projet créait sinon une copie dans une collection qu'elle ne
  fait que lire. Mutant : `if collection is None:`.
- `zero` : la copie SOURCE nommée doit être lue. Sans la garde, un écrivain de P2 nommait la
  copie de P1 comme source : la notice de P1 (description, éditeur, paternité, telles que
  P1 les a retouchées) et ses scans entraient dans P2. Mutant : `), None)`.
- `rejoindre` par la prise : la copie visée doit être lue. Sans la garde, la réponse
  distinguait une copie d'un autre projet (« vit dans un autre projet ») d'un identifiant
  qui n'existe pas : un oracle sur les copies de P1, depuis P2. Mutant : `c["id"] in lues`
  retiré.
- D3 : un écrivain ne nomme que ce qu'il lit dans CE projet. Sans la garde, qui lit une
  copie dans un autre projet faisait entrer le document dans le sien sans que personne y
  consente. Mutant : `and c["projet_id"] == projet_id` retiré.
"""
from conftest import ADMIN
from test_fonds import _accorder, _collection
from test_prendre import (LECTRICE, _copie_dans, _prendre, _rejoindre, _zero,
                          prise)  # noqa: F401

AUTRE = {"Remote-User": "autre_ecrivain"}


def _autre_projet(client, prise):
    """Un second projet, sa collection Q (où `autre_ecrivain` écrit), et le document d1 qui
    vit, dans le premier, dans Principale seule (projet de repli) — `autre_ecrivain` l'y lit."""
    r = client.post("/api/projets", json={"nom": "Autre projet"}, headers=ADMIN)
    assert r.status_code == 201, r.text
    q = _collection(client, "Q", projet_id=r.json()["id"])
    _accorder(client, q, "autre_ecrivain", "ecriture")
    _accorder(client, prise["principale"], "autre_ecrivain", "lecture")
    return q


def test_prendre_exige_d_ecrire_dans_la_collection_d_arrivee(client, prise, db_path):
    _copie_dans(client, prise, "d1", prise["x"])        # LECTRICE lit cette copie, dans X
    r = _prendre(client, prise["x"], [_zero(prise["docs"]["d1"])], LECTRICE)
    assert r.status_code == 404, r.text


def test_la_source_d_une_copie_vierge_doit_etre_lue(client, prise):
    q = _autre_projet(client, prise)
    # Le projet de Q a déjà le document (une copie que `autre_ecrivain` lit) : il peut partir
    # de zéro — mais pas en nommant comme source la copie de Principale, qu'il cesse de lire.
    cq = _copie_dans(client, prise, "d1", q)
    client.delete(f"/api/collections/{prise['principale']}/acces/utilisateur/autre_ecrivain",
                  headers=ADMIN)
    source_illisible = prise["albums"]["d1"]
    reponses = [_prendre(client, q, [_zero(prise["docs"]["d1"], a)], AUTRE)
                for a in (source_illisible, 999999)]
    assert [r.status_code for r in reponses] == [404, 404], [r.text for r in reponses]
    assert cq


def test_rejoindre_par_la_prise_une_copie_non_lue_est_introuvable(client, prise):
    q = _autre_projet(client, prise)
    _copie_dans(client, prise, "d1", q)                  # il lit une copie dans son projet
    client.delete(f"/api/collections/{prise['principale']}/acces/utilisateur/autre_ecrivain",
                  headers=ADMIN)
    cx = _copie_dans(client, prise, "d1", prise["x"])   # une copie d'Étude P, qu'il ne lit pas
    reponses = [_prendre(client, q, [_rejoindre(prise["docs"]["d1"], a)], AUTRE)
                for a in (cx, 999999)]
    assert [r.status_code for r in reponses] == [404, 404], [r.text for r in reponses]


def test_un_ecrivain_ne_nomme_pas_ce_qu_il_lit_dans_un_autre_projet(client, prise):
    q = _autre_projet(client, prise)                     # il lit d1 dans le projet de repli
    reponses = [_prendre(client, q, [_zero(d)], AUTRE) for d in (prise["docs"]["d1"], 999999)]
    assert [r.status_code for r in reponses] == [404, 404], [r.text for r in reponses]
