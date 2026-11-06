"""L'annotation d'une région : la NOTE, et elle seule (CONC-3 ; ANN-7, le basculement).

CONC-3 — mesuré le 2026-09-16 à deux navigateurs sur la même bulle : l'Atelier renvoyait la
note ET les tags chargés à la sélection, si bien que la note de A effaçait en silence le tag
que B venait de poser. Les tags sont partis avec le basculement d'ANN-7 : l'annotation ne
porte plus que la note, et `PUT …/annotation` refuse par un 422 nommé les champs d'hier
(`tags`, `tags_ajoutes`, `tags_retires`, I7) au lieu de les ignorer — un écran d'hier
croirait avoir posé ses tags. Ce que les tables du vocabulaire portent encore jusqu'à la
migration (posé ici en base, `conftest.poser_tags`) n'est ni montré ni réécrit.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from conftest import direct_query, poser_tags  # noqa: E402


def _bulle(client, planche_id):
    rep = client.post(f"/api/planches/{planche_id}/regions",
                      json={"type": "bulle", "x": 0, "y": 0, "w": 10, "h": 10})
    assert rep.status_code in (200, 201), rep.text
    return rep.json()["id"]


def _nb_actes(db_path, rid):
    return direct_query(db_path, "SELECT COUNT(*) AS n FROM evenement "
                                 "WHERE cible_table = 'annotations' AND cible_id = ?",
                        (rid,))[0]["n"]


def test_l_annotation_ne_rend_plus_que_la_note(client, planche, db_path):
    rid = _bulle(client, planche["id"])
    poser_tags(db_path, rid, ["d-hier"])
    rep = client.put(f"/api/regions/{rid}/annotation", json={"note": "une note"})
    assert rep.status_code == 200, rep.text
    assert "tags" not in rep.json()
    lue = client.get(f"/api/regions/{rid}/annotation").json()
    assert lue["note"] == "une note" and "tags" not in lue


@pytest.mark.parametrize("champ", ["tags", "tags_ajoutes", "tags_retires"])
def test_les_champs_d_hier_sont_refuses_en_le_disant(client, planche, db_path, champ):
    """I7 (Hugo, 2026-11-05) — refusés par un 422 qui dit que les tags n'existent plus, et
    rien n'est écrit, la note envoyée avec eux non plus."""
    rid = _bulle(client, planche["id"])
    rep = client.put(f"/api/regions/{rid}/annotation", json={"note": "n", champ: ["x"]})
    assert rep.status_code == 422, rep.text
    assert "n'existent plus" in rep.json()["detail"] and champ in rep.json()["detail"]
    assert not direct_query(db_path, "SELECT id FROM annotations WHERE region_id = ?", (rid,))
    assert _nb_actes(db_path, rid) == 0


def test_une_liste_vide_d_hier_est_refusee_aussi(client, planche):
    """`tags: []` est un champ d'hier comme un autre : l'accepter dirait à l'écran qui
    l'envoie qu'il a vidé des tags."""
    rid = _bulle(client, planche["id"])
    rep = client.put(f"/api/regions/{rid}/annotation", json={"note": "n", "tags": []})
    assert rep.status_code == 422, rep.text


def test_vider_la_note_supprime_l_annotation(client, planche, db_path):
    """Une annotation sans note n'a plus rien à porter : elle part, et ce qu'elle portait
    d'hier avec elle (la suppression est journalisée, son instantané garde tout)."""
    rid = _bulle(client, planche["id"])
    poser_tags(db_path, rid, ["seul"], note="une note")
    rep = client.put(f"/api/regions/{rid}/annotation", json={"note": "   "})
    assert rep.status_code == 200, rep.text
    assert rep.json()["note"] is None
    assert not direct_query(db_path, "SELECT id FROM annotations WHERE region_id = ?", (rid,))
    assert _nb_actes(db_path, rid) == 1


def test_une_requete_vide_ne_change_rien(client, planche, db_path):
    rid = _bulle(client, planche["id"])
    client.put(f"/api/regions/{rid}/annotation", json={"note": "garder"})
    actes = _nb_actes(db_path, rid)
    rep = client.put(f"/api/regions/{rid}/annotation", json={})
    assert rep.status_code == 200, rep.text
    assert rep.json()["note"] == "garder"
    assert _nb_actes(db_path, rid) == actes


def test_la_meme_note_ne_se_journalise_pas(client, planche, db_path):
    """Un enregistrement qui ne change rien ne devient pas un Ctrl+Z qui ne défait rien."""
    rid = _bulle(client, planche["id"])
    client.put(f"/api/regions/{rid}/annotation", json={"note": "même"})
    actes = _nb_actes(db_path, rid)
    client.put(f"/api/regions/{rid}/annotation", json={"note": "même"})
    assert _nb_actes(db_path, rid) == actes


def test_vider_une_note_absente_ne_fait_rien(client, planche, db_path):
    rid = _bulle(client, planche["id"])
    rep = client.put(f"/api/regions/{rid}/annotation", json={"note": ""})
    assert rep.status_code == 200, rep.text
    assert _nb_actes(db_path, rid) == 0
