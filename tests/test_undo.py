"""Annulation (undo, D1) — tests.

Vérifie l'inversion de chaque geste d'annotation depuis le journal A3 (région créer/modifier/
supprimer+cascade, annotation note+tags, locuteur, présence), la PILE (Ctrl+Z répété remonte
l'historique), l'intégrité APPEND-ONLY (un événement `annulation` est ajouté, rien n'est retiré
du journal), et le fait que les actes MACHINE ne sont pas annulables par l'utilisateur.
"""
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import undo  # noqa: E402
from conftest import ADMIN, direct_query  # noqa: E402


def _regions(db_path):
    return {r["id"] for r in direct_query(db_path, "SELECT id FROM regions")}


def _creer_region(client, planche_id, headers=None, **kw):
    body = {"type": "case", "x": 0, "y": 0, "w": 10, "h": 10, **kw}
    return client.post(f"/api/planches/{planche_id}/regions", json=body,
                       headers=headers).json()


def _un(db_path, sql, params=()):
    rows = direct_query(db_path, sql, params)
    return rows[0] if rows else None


# --------------------------------------------------------------------------- #
# Régions
# --------------------------------------------------------------------------- #
def test_undo_creation_region(client, planche, db_path):
    r = _creer_region(client, planche["id"])
    assert r["id"] in _regions(db_path)
    res = client.post("/api/undo").json()
    assert res["acte"] == "creation" and res["cible_table"] == "regions"
    assert res["region_id"] == r["id"] and res["planche_id"] == planche["id"]
    assert r["id"] not in _regions(db_path)             # région supprimée


def test_undo_modification_region(client, planche, db_path):
    r = _creer_region(client, planche["id"], x=5, y=5, w=20, h=20)
    client.put(f"/api/regions/{r['id']}", json={"x": 99, "y": 88})
    res = client.post("/api/undo").json()               # annule la modification
    assert res["acte"] == "modification"
    row = _un(db_path, "SELECT x, y FROM regions WHERE id = ?", (r["id"],))
    assert row["x"] == 5 and row["y"] == 5              # géométrie restaurée
    client.post("/api/undo")                            # annule la création (pile)
    assert r["id"] not in _regions(db_path)


def test_undo_suppression_region_cascade(client, planche, db_path):
    """Le geste le plus dangereux : la suppression cascade est restaurée à l'identique
    (sous-arbre + annotation + tags, mêmes id)."""
    case = _creer_region(client, planche["id"], type="case")
    bulle = _creer_region(client, planche["id"], type="bulle", parent_id=case["id"],
                          ocr_texte="SALUT")
    client.put(f"/api/regions/{bulle['id']}/annotation", json={"note": "cri", "tags": ["emotion"]})
    client.delete(f"/api/regions/{case['id']}")
    assert case["id"] not in _regions(db_path) and bulle["id"] not in _regions(db_path)

    res = client.post("/api/undo").json()
    assert res["acte"] == "suppression"
    regs = _regions(db_path)
    assert case["id"] in regs and bulle["id"] in regs   # sous-arbre restauré, mêmes id
    ann = _un(db_path, "SELECT note FROM annotations WHERE region_id = ?", (bulle["id"],))
    assert ann["note"] == "cri"
    tags = direct_query(db_path,
        "SELECT t.label FROM annotation_tags at JOIN tags t ON t.id = at.tag_id "
        "JOIN annotations a ON a.id = at.annotation_id WHERE a.region_id = ?", (bulle["id"],))
    assert [t["label"] for t in tags] == ["emotion"]


# --------------------------------------------------------------------------- #
# Annotations
# --------------------------------------------------------------------------- #
def test_undo_annotation_modif_puis_creation(client, region, db_path):
    client.put(f"/api/regions/{region['id']}/annotation", json={"note": "A", "tags": ["x"]})
    client.put(f"/api/regions/{region['id']}/annotation", json={"note": "B", "tags": ["y"]})
    res = client.post("/api/undo").json()               # annule la modification → A/x
    assert res["acte"] == "modification" and res["cible_table"] == "annotations"
    assert _un(db_path, "SELECT note FROM annotations WHERE region_id = ?",
               (region["id"],))["note"] == "A"
    res = client.post("/api/undo").json()               # annule la création → plus d'annotation
    assert res["acte"] == "creation"
    assert _un(db_path, "SELECT 1 FROM annotations WHERE region_id = ?", (region["id"],)) is None


def test_undo_suppression_annotation(client, region, db_path):
    client.put(f"/api/regions/{region['id']}/annotation", json={"note": "garder", "tags": ["t"]})
    client.put(f"/api/regions/{region['id']}/annotation", json={"note": "", "tags": []})  # vidée → supprimée
    assert _un(db_path, "SELECT 1 FROM annotations WHERE region_id = ?", (region["id"],)) is None
    res = client.post("/api/undo").json()               # annule la suppression → restaurée
    assert res["acte"] == "suppression"
    assert _un(db_path, "SELECT note FROM annotations WHERE region_id = ?",
               (region["id"],))["note"] == "garder"


# --------------------------------------------------------------------------- #
# Locuteur / présence
# --------------------------------------------------------------------------- #
def test_undo_lien_locuteur(client, region, db_path):
    p = client.post("/api/personnages", json={"nom": "Tintin"}).json()
    client.put(f"/api/regions/{region['id']}/locuteur", json={"personnage_id": p["id"]})
    res = client.post("/api/undo").json()               # annule le lien → locuteur retiré
    assert res["acte"] == "lien" and res["cible_table"] == "bulle_locuteur"
    assert _un(db_path, "SELECT 1 FROM bulle_locuteur WHERE region_id = ?", (region["id"],)) is None


def test_undo_delien_locuteur_retablit(client, region, db_path):
    p = client.post("/api/personnages", json={"nom": "Milou"}).json()
    client.put(f"/api/regions/{region['id']}/locuteur", json={"personnage_id": p["id"]})
    client.delete(f"/api/regions/{region['id']}/locuteur")
    res = client.post("/api/undo").json()               # annule le délien → locuteur rétabli
    assert res["acte"] == "delien"
    assert _un(db_path, "SELECT personnage_id FROM bulle_locuteur WHERE region_id = ?",
               (region["id"],))["personnage_id"] == p["id"]


def test_undo_lien_personnage_disparu_409(client, region, db_path):
    """Rétablir un lien vers un personnage supprimé entre-temps → 409 explicite (pas 500),
    et aucun état partiel (transaction rollback)."""
    p = client.post("/api/personnages", json={"nom": "Fantome"}).json()
    client.put(f"/api/regions/{region['id']}/locuteur", json={"personnage_id": p["id"]})
    client.delete(f"/api/regions/{region['id']}/locuteur")   # délien = dernière action
    client.delete(f"/api/personnages/{p['id']}")             # le personnage disparaît
    assert client.post("/api/undo").status_code == 409
    assert _un(db_path, "SELECT 1 FROM bulle_locuteur WHERE region_id = ?",
               (region["id"],)) is None                      # rien recréé


def test_undo_presence(client, region, db_path):
    p = client.post("/api/personnages", json={"nom": "Haddock"}).json()
    client.put(f"/api/regions/{region['id']}/personnage", json={"personnage_id": p["id"]})
    res = client.post("/api/undo").json()
    assert res["acte"] == "lien" and res["cible_table"] == "personnage_presence"
    assert _un(db_path, "SELECT 1 FROM personnage_presence WHERE region_id = ?",
               (region["id"],)) is None


# --------------------------------------------------------------------------- #
# Pile, aperçu, garde-fous
# --------------------------------------------------------------------------- #
def test_undo_pile_append_only(client, planche, db_path):
    r1 = _creer_region(client, planche["id"])
    r2 = _creer_region(client, planche["id"])
    n = _un(db_path, "SELECT COUNT(*) c FROM evenement")["c"]
    client.post("/api/undo")                            # annule r2
    assert r2["id"] not in _regions(db_path) and r1["id"] in _regions(db_path)
    # Append-only : un événement `annulation` AJOUTÉ, rien retiré du journal.
    assert _un(db_path, "SELECT COUNT(*) c FROM evenement")["c"] == n + 1
    assert _un(db_path, "SELECT COUNT(*) c FROM evenement WHERE type = 'annulation'")["c"] == 1
    client.post("/api/undo")                            # annule r1 (la pile remonte)
    assert r1["id"] not in _regions(db_path)
    assert client.post("/api/undo").status_code == 404  # plus rien à annuler


def test_undo_apercu(client, region):
    ap = client.get("/api/undo/prochain").json()
    assert ap and ap["description"] == "création d'une région"
    client.post("/api/undo")
    assert client.get("/api/undo/prochain").json() is None


def test_undo_rien_a_annuler(client):
    assert client.post("/api/undo").status_code == 404


def test_undo_ignore_actes_machine(client, db_path):
    """Un acte MOTEUR (passe ML) n'est pas annulable par l'utilisateur."""
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO evenement (type, agent_type, cible_table, cible_id) "
                 "VALUES ('creation', 'moteur', 'regions', 999)")
    conn.commit()
    conn.close()
    assert client.post("/api/undo").status_code == 404


# --------------------------------------------------------------------------- #
# Compte COLLECTIF : Ctrl+Z borné dans le temps (AUTH-6)
# --------------------------------------------------------------------------- #
def _vieillir(db_path, minutes):
    """Recule la date de TOUS les événements. Le journal ne se réécrit jamais en vrai ;
    c'est la seule façon d'éprouver un délai sans attendre qu'il s'écoule."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE evenement SET date = datetime(date, ?)", (f"-{minutes} minutes",))
        conn.commit()
    finally:
        conn.close()


def _declarer(client, login, nature):
    """Par la VRAIE route (réservée aux administrateurs), pas en SQL : c'est ainsi qu'un
    compte devient collectif, et c'est ce chemin que la règle doit lire. Le login doit
    d'abord avoir été VU — `utilisateur` n'est alimentée que par `GET /api/moi`, que toute
    page appelle à l'ouverture."""
    client.get("/api/moi", headers={"Remote-User": login})
    r = client.patch(f"/api/comptes/{login}/nature", json={"nature": nature}, headers=ADMIN)
    assert r.status_code == 200, r.text


def test_un_compte_collectif_n_annule_que_ses_actes_recents(client, planche, db_path,
                                                            derriere_proxy):
    """Sous un login PARTAGÉ, le filtre par agent ne sépare plus mes actes de ceux du
    collègue : Ctrl+Z ne remonte que les cinq dernières minutes, et le refus le DIT — un
    simple « rien à annuler » laisserait croire l'historique vide."""
    ancien = _creer_region(client, planche["id"], headers=ADMIN)
    _declarer(client, "decor", "collectif")
    _vieillir(db_path, 10)
    assert client.get("/api/undo/prochain", headers=ADMIN).json() is None
    r = client.post("/api/undo", headers=ADMIN)
    assert r.status_code == 404
    assert r.json()["detail"].startswith("Rien à annuler")      # l'Atelier le lit comme une info
    assert f"{undo.DELAI_COLLECTIF_MINUTES} dernières minutes" in r.json()["detail"]
    assert ancien["id"] in _regions(db_path)                     # l'acte ancien est intact
    recent = _creer_region(client, planche["id"], headers=ADMIN)
    assert client.post("/api/undo", headers=ADMIN).json()["region_id"] == recent["id"]


def test_un_compte_nominatif_annule_sans_limite_de_temps(client, planche, db_path,
                                                         derriere_proxy):
    """La borne ne vise QUE le compte collectif : une personne nommée garde tout son
    historique, et le refus ordinaire ne parle pas de délai. Le compte est DÉCLARÉ
    nominatif — donc CONNU de `utilisateur` : un login jamais vu n'a pas de ligne, et une
    règle qui bornerait tout compte connu passerait inaperçue (mutation survivante du
    premier jet)."""
    ancien = _creer_region(client, planche["id"], headers=ADMIN)
    _declarer(client, "decor", "nominatif")
    _vieillir(db_path, 60 * 24)
    assert client.post("/api/undo", headers=ADMIN).json()["region_id"] == ancien["id"]
    assert client.post("/api/undo", headers=ADMIN).json()["detail"] == "Rien à annuler."


def test_viser_un_vieil_acte_par_son_id_ne_contourne_pas_le_delai(client, planche, db_path,
                                                                  derriere_proxy):
    """`annuler(evenement_id=…)` revérifie l'agent ; il doit revérifier le délai aussi —
    nommer un acte ne le rajeunit pas. Le second appel prouve que le refus vient du
    délai, et non d'un identifiant qui ne désignerait rien."""
    ancien = _creer_region(client, planche["id"], headers=ADMIN)
    _declarer(client, "decor", "collectif")
    _vieillir(db_path, 10)
    eid = _un(db_path, "SELECT id FROM evenement WHERE cible_table = 'regions' "
                       "AND cible_id = ?", (ancien["id"],))["id"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        assert undo.annuler(conn, evenement_id=eid, agent="decor") is None
        assert undo.annuler(conn, evenement_id=eid, agent=undo.TOUS) is not None
    finally:
        conn.rollback()
        conn.close()


def test_le_mono_poste_n_a_pas_de_delai(client, planche, db_path):
    """Sans proxy, un seul agent (anonyme) et aucune nature à lire : rien ne change."""
    ancien = _creer_region(client, planche["id"])
    _vieillir(db_path, 60)
    assert client.post("/api/undo").json()["region_id"] == ancien["id"]
