"""CONC-3 — un enregistrement d'annotation ne réécrit que ce qu'il change.

Mesuré le 2026-09-16 à deux navigateurs sur la même bulle : l'Atelier renvoyait la note ET
les tags chargés à la sélection, si bien que la note de A effaçait en silence le tag que B
venait de poser, et que le tag suivant de B effaçait la note de A. Ces tests tiennent la
route (`main.put_annotation`) et l'annulation (`undo._inverser_annotation`) ; la garde à
deux navigateurs vit dans `tests/test_e2e_annotation_a_deux.py`.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import autorisation  # noqa: E402
import main  # noqa: E402
from conftest import direct_query  # noqa: E402


def _bulle(client, planche_id):
    rep = client.post(f"/api/planches/{planche_id}/regions",
                      json={"type": "bulle", "x": 0, "y": 0, "w": 10, "h": 10})
    assert rep.status_code in (200, 201), rep.text
    return rep.json()["id"]


def _etat(client, rid, headers=None):
    a = client.get(f"/api/regions/{rid}/annotation", headers=headers).json()
    return a["note"], {t["label"] for t in a["tags"]}


def _nb_actes(db_path, rid):
    return direct_query(db_path, "SELECT COUNT(*) AS n FROM evenement "
                                 "WHERE cible_table = 'annotations' AND cible_id = ?",
                        (rid,))[0]["n"]


def test_la_note_seule_ne_touche_pas_aux_tags_poses_entre_temps(client, planche):
    """La mesure 1 de CONC-3, au niveau de la route : B ajoute un tag, A n'envoie que sa note."""
    rid = _bulle(client, planche["id"])
    client.put(f"/api/regions/{rid}/annotation", json={"note": "", "tags": ["depart"]})

    rep = client.put(f"/api/regions/{rid}/annotation", json={"tags_ajoutes": ["tag-de-b"]})
    assert rep.status_code == 200, rep.text
    rep = client.put(f"/api/regions/{rid}/annotation", json={"note": "note de A"})
    assert rep.status_code == 200, rep.text

    assert _etat(client, rid) == ("note de A", {"depart", "tag-de-b"}), (
        "la note seule a réécrit la liste des tags")


def test_un_tag_ajoute_ne_touche_pas_a_la_note(client, planche):
    """Le sens inverse, mesuré aussi : le tag de B effaçait la note de A."""
    rid = _bulle(client, planche["id"])
    client.put(f"/api/regions/{rid}/annotation", json={"note": "note de A"})
    rep = client.put(f"/api/regions/{rid}/annotation", json={"tags_ajoutes": ["tag-de-b"]})
    assert rep.status_code == 200, rep.text
    assert _etat(client, rid) == ("note de A", {"tag-de-b"})


def test_retirer_ne_retire_que_le_tag_nomme(client, planche, db_path):
    rid = _bulle(client, planche["id"])
    client.put(f"/api/regions/{rid}/annotation", json={"note": "n", "tags": ["x", "y"]})
    rep = client.put(f"/api/regions/{rid}/annotation", json={"tags_retires": ["X"]})
    assert rep.status_code == 200, rep.text
    assert _etat(client, rid) == ("n", {"y"}), "le libellé se normalise comme à l'ajout"

    actes = _nb_actes(db_path, rid)
    rep = client.put(f"/api/regions/{rid}/annotation", json={"tags_retires": ["absent"]})
    assert rep.status_code == 200, rep.text
    assert _nb_actes(db_path, rid) == actes, (
        "un enregistrement qui ne change rien a été journalisé : Ctrl+Z ne déferait rien de visible")


def test_une_requete_vide_ne_change_rien(client, planche, db_path):
    rid = _bulle(client, planche["id"])
    client.put(f"/api/regions/{rid}/annotation", json={"note": "garder", "tags": ["t"]})
    actes = _nb_actes(db_path, rid)
    rep = client.put(f"/api/regions/{rid}/annotation", json={})
    assert rep.status_code == 200, rep.text
    assert _etat(client, rid) == ("garder", {"t"})
    assert _nb_actes(db_path, rid) == actes


def test_la_liste_entiere_et_les_differences_ensemble_sont_refusees(client, planche):
    rid = _bulle(client, planche["id"])
    rep = client.put(f"/api/regions/{rid}/annotation",
                     json={"tags": ["a"], "tags_ajoutes": ["b"]})
    assert rep.status_code == 422, rep.text
    assert "tags_ajoutes" in rep.json()["detail"]


def test_la_liste_entiere_remplace_toujours(client, planche):
    """Les appelants qui envoient `note` et `tags` ensemble gardent leur sens d'avant."""
    rid = _bulle(client, planche["id"])
    client.put(f"/api/regions/{rid}/annotation", json={"note": "a", "tags": ["x", "y"]})
    client.put(f"/api/regions/{rid}/annotation", json={"note": "b", "tags": ["z"]})
    assert _etat(client, rid) == ("b", {"z"})


def test_retirer_le_dernier_tag_d_une_annotation_sans_note_la_supprime(client, planche, db_path):
    """La règle « vide = supprimée » vaut aussi quand on y arrive par différence."""
    rid = _bulle(client, planche["id"])
    client.put(f"/api/regions/{rid}/annotation", json={"tags_ajoutes": ["seul"]})
    # Sans ce témoin, le test passait sur l'ancienne route, qui ignorait `tags_ajoutes` et
    # ne créait donc jamais l'annotation dont il vérifie la disparition.
    assert direct_query(db_path, "SELECT id FROM annotations WHERE region_id = ?", (rid,))
    client.put(f"/api/regions/{rid}/annotation", json={"tags_retires": ["seul"]})
    assert not direct_query(db_path, "SELECT id FROM annotations WHERE region_id = ?", (rid,))


def test_annuler_sa_note_ne_defait_pas_le_tag_de_l_autre(client, planche, db_path, monkeypatch):
    """L'annulation restaurait l'instantané AVANT entier : annuler la note de A rendait la
    liste de tags d'avant, donc effaçait le tag posé par B entre-temps. Elle défait
    désormais ce que l'acte a changé, et rien d'autre — dans les deux sens."""
    rid = _bulle(client, planche["id"])
    client.put(f"/api/regions/{rid}/annotation", json={"note": "avant", "tags": ["depart"]})

    monkeypatch.setattr(main, "AUTH_PROXY", True)
    monkeypatch.setattr(autorisation, "AUTH_PROXY", True)
    a = {"Remote-User": "personne-a", "Remote-Groups": "bd-admins"}
    b = {"Remote-User": "personne-b", "Remote-Groups": "bd-admins"}

    assert client.put(f"/api/regions/{rid}/annotation", json={"note": "note de A"},
                      headers=a).status_code == 200
    assert client.put(f"/api/regions/{rid}/annotation", json={"tags_ajoutes": ["tag-de-b"]},
                      headers=b).status_code == 200

    rep = client.post("/api/undo", headers=a)
    assert rep.status_code == 200, rep.text
    assert _etat(client, rid, a) == ("avant", {"depart", "tag-de-b"}), (
        "annuler la note de A a emporté le tag de B")

    rep = client.post("/api/undo", headers=b)
    assert rep.status_code == 200, rep.text
    assert _etat(client, rid, b) == ("avant", {"depart"}), (
        "annuler le tag de B n'a pas rendu exactement l'état d'avant son geste")
