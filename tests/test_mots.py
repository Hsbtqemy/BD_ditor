"""Le découpage en mots de l'outil (ANN-7, tranche 1 ; cadrage R6, G11).

La table `tests/cas-mots.json` est ÉCRITE À LA MAIN, cas par cas, et non générée depuis
`mots.py` : c'est la mesure de la règle, pas son miroir. Les cas que la note laissait
ouverts y portent `a_trancher` — la règle les tranche, provisoirement, et c'est avec les
linguistes qu'elle se confirmera (G11). Au-dessous, des PROPRIÉTÉS que tout découpage doit
tenir, quel que soit le cas : chaque forme est le texte verbatim de sa place, les rangs se
suivent, rien ne se perd ni ne se recouvre.
"""
import json
from pathlib import Path

import pytest

import mots
from conftest import ADMIN

TABLE = json.loads((Path(__file__).parent / "cas-mots.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("cas", TABLE, ids=[c["nom"] for c in TABLE])
def test_table_des_cas(cas):
    assert [m["forme"] for m in mots.decouper(cas["texte"])] == cas["mots"]


def test_la_table_dit_ce_qui_reste_a_trancher():
    """Les cas que la note du 2026-10-14 ne tranchait pas sont dans la table, marqués : la
    règle les a tranchés, provisoirement, et le marquage dit à qui revient le dernier mot."""
    marques = [c["texte"].lower() for c in TABLE if c.get("a_trancher")]
    for attendu in ("aujourd'hui", "peut-être", "-t-il", "-\n", "!!!", "...", "s.n.c.f.",
                    "3,50"):
        assert any(attendu in texte for texte in marques), attendu


@pytest.mark.parametrize("cas", TABLE, ids=[c["nom"] for c in TABLE])
def test_chaque_forme_est_le_texte_de_sa_place(cas):
    """`texte[debut:fin] == forme`, les rangs se suivent, les places ne se recouvrent pas,
    et ce qui reste entre deux mots n'est que de l'espace : rien ne se perd."""
    texte = cas["texte"]
    decoupe = mots.decouper(texte)
    assert [m["rang"] for m in decoupe] == list(range(len(decoupe)))
    fin = 0
    for m in decoupe:
        assert texte[m["debut"]:m["fin"]] == m["forme"] and m["forme"]
        assert m["debut"] >= fin
        assert texte[fin:m["debut"]].strip() == ""
        fin = m["fin"]
    assert texte[fin:].strip() == ""


def test_un_texte_nul_n_a_aucun_mot():
    assert mots.decouper(None) == []


def test_la_cle_confond_apostrophes_traits_et_casse_mais_pas_les_lettres():
    assert mots.cle("C’EST") == mots.cle("c'est")
    assert mots.cle("PEUT‑ÊTRE") == mots.cle("peut-être")
    assert mots.cle("é") == mots.cle("é")           # composé ou décomposé
    assert mots.cle("POR-\nTRAIT") == mots.cle("por-trait")
    assert mots.cle("otage") != mots.cle("otages")


def test_l_alignement_suit_un_mot_deplace_et_perd_un_mot_change():
    """Le substrat du ré-ancrage : un mot retrouvé — même clé, même ordre relatif — suit
    sa nouvelle place ; un mot changé n'a pas de correspondant."""
    assert mots.aligner("IL NE SAIT PAS", "Il ne sait vraiment pas") == {0: 0, 1: 1, 2: 2,
                                                                       3: 4}
    correspondance = mots.aligner("IL NE SAIT PAS", "IL NE SAVAIT PAS")
    assert 2 not in correspondance and correspondance[3] == 3


def test_la_route_rend_le_decoupage_de_l_outil(client, region):
    rid = region["id"]
    texte = "J'SAIS PAS… AUJOURD’HUI !!!"
    assert client.put(f"/api/regions/{rid}", json={"ocr_texte": texte},
                      headers=ADMIN).status_code == 200
    r = client.get(f"/api/regions/{rid}/mots", headers=ADMIN)
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["texte"] == texte
    assert corps["mots"] == mots.decouper(texte)
    assert [m["forme"] for m in corps["mots"]] == ["J'", "SAIS", "PAS", "…", "AUJOURD’HUI",
                                                   "!!!"]


def test_la_route_est_cloisonnee(client, region, derriere_proxy):
    """À qui ne lit pas la région : 404, comme toute donnée du corpus (« 404, jamais 403 »)."""
    r = client.get(f"/api/regions/{region['id']}/mots", headers={"Remote-User": "inconnu"})
    assert r.status_code == 404
    assert client.get(f"/api/regions/{region['id']}/mots", headers=ADMIN).status_code == 200


def test_une_region_sans_texte_n_a_aucun_mot(client, region):
    r = client.get(f"/api/regions/{region['id']}/mots", headers=ADMIN)
    assert r.json() == {"region_id": region["id"], "texte": "", "mots": []}
