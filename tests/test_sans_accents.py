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

from socle import _sans_accents

TABLE = json.loads((Path(__file__).parent / "cas-sans-accents.json").read_text(encoding="utf-8"))


def test_la_table_n_est_pas_vide():
    assert len(TABLE) >= 12, "table de cas suspicieusement courte"


@pytest.mark.parametrize("cas", TABLE, ids=[c["nom"] for c in TABLE])
def test_table_partagee(cas):
    assert _sans_accents(cas["entree"]) == cas["attendu"]


def test_le_registre_filtre_par_cette_regle(client):
    """La règle de la table est bien celle du filtre : « etien » trouve « Étienne »."""
    pid = client.post("/api/personnages", json={"nom": "Étienne"}).json()["id"]
    assert [p["id"] for p in client.get("/api/personnages?q=ETIEN").json()] == [pid]
