"""ANN-8 — le filtre du registre des personnages vit en double, et la table dit qu'ils
s'accordent.

`GET /api/personnages?q=` garde les personnages dont le nom CONTIENT la saisie, sans égard à
la casse ni aux accents (`socle._sans_accents`). L'écran se pose la même question à Entrée :
la proposition qu'on a surlignée dans la liste d'une saisie d'AVANT répond-elle encore à ce
qui est tapé (`BDPropositions.repond`, décision de Hugo du 2026-10-21) ? Il la pose avec sa
jumelle, `BDPropositions.sansAccents`.

Ce fichier et `tests/js/propositions.test.js` lisent LA MÊME table,
`tests/cas-sans-accents.json`, écrite depuis Python : c'est côté JS qu'elle mord.
"""
import json
from pathlib import Path

import pytest

from conftest import ADMIN, direct_query
from socle import _sans_accents

TABLE = json.loads((Path(__file__).parent / "cas-sans-accents.json").read_text(encoding="utf-8"))


def test_la_table_n_est_pas_vide():
    assert len(TABLE) >= 12, "table de cas suspicieusement courte"


@pytest.mark.parametrize("cas", TABLE, ids=[c["nom"] for c in TABLE])
def test_table_partagee(cas):
    assert _sans_accents(cas["entree"]) == cas["attendu"]


def test_creer_un_nom_sans_ses_accents_rend_l_homonyme_accentue(client, db_path):
    """ANN-8 (Hugo, 2026-10-21) — dans une même série, l'accent ne distingue pas deux
    personnages : « etienne » demandé quand « Étienne » existe RENDU Étienne, 200 au lieu de
    201, rien d'écrit. Le filet de la règle de l'Atelier, pour une liste lue trop tôt."""
    pid = client.post("/api/personnages", json={"nom": "Étienne"}).json()["id"]
    for saisie in ("etienne", " ETIENNE ", "e\u0301tienne"):
        rep = client.post("/api/personnages", json={"nom": saisie})
        assert rep.status_code == 200, rep.text
        assert (rep.json()["id"], rep.json()["nom"]) == (pid, "Étienne")
    assert direct_query(db_path, "SELECT COUNT(*) n FROM personnages")[0]["n"] == 1


def test_une_autre_serie_n_est_pas_un_homonyme(client, db_path):
    """« Dans une même série » : la série distingue des homonymes légitimes, à l'accent près
    comme au mot près — et « sans série » n'est l'homonyme d'aucune série nommée."""
    pid = client.post("/api/personnages", json={"nom": "Étienne"}).json()["id"]
    autre = client.post("/api/personnages", json={"nom": "etienne", "serie": "Les Aventures"})
    assert autre.status_code == 201 and autre.json()["id"] != pid
    meme = client.post("/api/personnages", json={"nom": "ÉTIENNE", "serie": "les aventures"})
    assert (meme.status_code, meme.json()["id"]) == (200, autre.json()["id"])
    assert client.post("/api/personnages", json={"nom": "Zed"}).status_code == 201
    assert direct_query(db_path, "SELECT COUNT(*) n FROM personnages")[0]["n"] == 3


def test_un_homonyme_qu_on_ne_voit_pas_n_est_pas_rendu(client, planche, db_path,
                                                       derriere_proxy):
    """Un personnage qu'on ne voit pas — il ne parle que dans une collection qu'on ne lit
    pas — n'est pas retrouvé : le rendre dirait qu'il existe, et l'attacherait hors de sa
    portée. On en crée un, comme avant."""
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 0, "y": 0, "w": 10, "h": 10},
                      headers=ADMIN).json()["id"]
    cache = client.post("/api/personnages", json={"nom": "Étienne"}, headers=ADMIN).json()["id"]
    assert client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": cache},
                      headers=ADMIN).status_code == 200
    ailleurs = _ecrivain_d_une_autre_collection(client)
    assert all(p["id"] != cache for p in client.get("/api/personnages", headers=ailleurs).json())
    rep = client.post("/api/personnages", json={"nom": "etienne"}, headers=ailleurs)
    assert rep.status_code == 201, rep.text
    assert rep.json()["id"] != cache


def _ecrivain_d_une_autre_collection(client):
    """Un compte qui écrit dans une collection neuve, et ne lit rien d'autre."""
    cid = client.post("/api/collections", json={"nom": "Ailleurs"}, headers=ADMIN).json()["id"]
    assert client.put(f"/api/collections/{cid}/acces",
                      json={"genre": "utilisateur", "principal": "zoe", "niveau": "ecriture"},
                      headers=ADMIN).status_code == 200
    return {"Remote-User": "zoe"}


def test_le_registre_filtre_par_cette_regle(client):
    """La règle de la table est bien celle du filtre : « etien » trouve « Étienne »."""
    pid = client.post("/api/personnages", json={"nom": "Étienne"}).json()["id"]
    assert [p["id"] for p in client.get("/api/personnages?q=ETIEN").json()] == [pid]
