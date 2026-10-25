"""Annulation (undo, D1) — tests.

Vérifie l'inversion de chaque geste d'annotation depuis le journal A3 (région créer/modifier/
supprimer+cascade, annotation note+tags, locuteur, présence), la PILE (Ctrl+Z répété remonte
l'historique), l'intégrité APPEND-ONLY (un événement `annulation` est ajouté, rien n'est retiré
du journal), et le fait que les actes MACHINE ne sont pas annulables par l'utilisateur.
"""
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import conflit  # noqa: E402
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
# ANN-6 — joués sur `zone_de_texte`, donc une fois par type qui parle : l'annulation suit
# un cartouche et une zone de texte comme elle suivait une bulle. Ils posaient leur locuteur
# sur `region`, une CASE, ce que la route refuse désormais.
def test_undo_lien_locuteur(client, zone_de_texte, db_path):
    region = zone_de_texte
    p = client.post("/api/personnages", json={"nom": "Tintin"}).json()
    client.put(f"/api/regions/{region['id']}/locuteur", json={"personnage_id": p["id"]})
    res = client.post("/api/undo").json()               # annule le lien → locuteur retiré
    assert res["acte"] == "lien" and res["cible_table"] == "bulle_locuteur"
    assert _un(db_path, "SELECT 1 FROM bulle_locuteur WHERE region_id = ?", (region["id"],)) is None


def test_undo_delien_locuteur_retablit(client, zone_de_texte, db_path):
    region = zone_de_texte
    p = client.post("/api/personnages", json={"nom": "Milou"}).json()
    client.put(f"/api/regions/{region['id']}/locuteur", json={"personnage_id": p["id"]})
    client.delete(f"/api/regions/{region['id']}/locuteur")
    res = client.post("/api/undo").json()               # annule le délien → locuteur rétabli
    assert res["acte"] == "delien"
    assert _un(db_path, "SELECT personnage_id FROM bulle_locuteur WHERE region_id = ?",
               (region["id"],))["personnage_id"] == p["id"]


def test_undo_lien_personnage_disparu_409(client, zone_de_texte, db_path):
    """Rétablir un lien vers un personnage supprimé entre-temps → 409 explicite (pas 500),
    et aucun état partiel (transaction rollback)."""
    region = zone_de_texte
    p = client.post("/api/personnages", json={"nom": "Fantome"}).json()
    client.put(f"/api/regions/{region['id']}/locuteur", json={"personnage_id": p["id"]})
    client.delete(f"/api/regions/{region['id']}/locuteur")   # délien = dernière action
    client.delete(f"/api/personnages/{p['id']}")             # le personnage disparaît
    assert client.post("/api/undo").status_code == 409
    assert _un(db_path, "SELECT 1 FROM bulle_locuteur WHERE region_id = ?",
               (region["id"],)) is None                      # rien recréé


# --------------------------------------------------------------------------- #
# ANN-8 (Hugo, 2026-10-21) — un locuteur part avec le type, revient avec lui, et ne se
# repose jamais sur une région dont le type n'en porte pas.
#
# Ces tests DÉCRIVAIENT, jusqu'au 2026-10-21, l'inverse : une bulle devenue case gardait son
# locuteur, et l'annulation en reposait un sur une case là où la route répondait 422. Ils
# étaient écrits pour tomber le jour où la décision serait prise ; elle l'est, et ils ont
# changé de sens.
# --------------------------------------------------------------------------- #
def _type_et_locuteur(db_path, region_id):
    r = _un(db_path, "SELECT r.type, bl.personnage_id FROM regions r "
                     "LEFT JOIN bulle_locuteur bl ON bl.region_id = r.id WHERE r.id = ?",
            (region_id,))
    return r["type"], r["personnage_id"]


def _annulations(db_path):
    return direct_query(db_path, "SELECT COUNT(*) n FROM evenement WHERE type = 'annulation'")[0]["n"]


def test_un_locuteur_part_avec_le_type(client, planche, db_path):
    """Une bulle qui parle devient case : son locuteur part, le registre ne le compte plus,
    et le retrait est écrit DANS l'acte du changement de type — pas dans un `delien` à part."""
    rid = _creer_region(client, planche["id"], type="bulle")["id"]
    p = client.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]
    assert client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": p}).status_code == 200

    rep = client.put(f"/api/regions/{rid}", json={"type": "case"})
    assert rep.status_code == 200, rep.text
    assert rep.json()["type"] == "case"
    assert rep.json()["locuteur_retire"] == {"id": p, "nom": "Tintin", "serie": None}
    assert _type_et_locuteur(db_path, rid) == ("case", None)
    assert client.get(f"/api/regions/{rid}/locuteur").json()["locuteur"] is None
    assert [x for x in client.get("/api/personnages").json() if x["id"] == p][0]["nb_bulles"] == 0

    ev = direct_query(db_path, "SELECT * FROM evenement WHERE cible_table IN "
                               "('regions', 'bulle_locuteur') ORDER BY id DESC LIMIT 1")[0]
    assert (ev["type"], ev["cible_table"], ev["agent_type"]) == ("modification", "regions", "humain")
    assert json.loads(ev["avant"])["locuteur"] == p
    assert "locuteur" not in json.loads(ev["apres"])
    assert direct_query(db_path, "SELECT COUNT(*) n FROM evenement WHERE type = 'delien'")[0]["n"] == 0


def test_un_changement_de_type_entre_zones_de_texte_garde_le_locuteur(client, planche, db_path):
    """Une bulle qui devient cartouche parle toujours : rien ne part, la réponse ne dit rien."""
    rid = _creer_region(client, planche["id"], type="bulle")["id"]
    p = client.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": p})
    rep = client.put(f"/api/regions/{rid}", json={"type": "cartouche"})
    assert rep.status_code == 200 and "locuteur_retire" not in rep.json()
    assert _type_et_locuteur(db_path, rid) == ("cartouche", p)


def test_bouger_une_case_qui_porte_un_locuteur_d_avant_ne_le_retire_pas(client, planche, db_path):
    """Seul un changement de TYPE retire : un geste de géométrie sur une case d'avant ANN-8
    ne fait pas, en passant, le travail de l'outil de rattrapage."""
    rid = _creer_region(client, planche["id"], type="case")["id"]
    p = client.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]
    c = sqlite3.connect(db_path)
    c.execute("INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?)", (rid, p))
    c.commit()
    c.close()
    rep = client.put(f"/api/regions/{rid}", json={"x": 7})
    assert rep.status_code == 200 and "locuteur_retire" not in rep.json()
    assert _type_et_locuteur(db_path, rid) == ("case", p)


def test_un_ctrl_z_rend_le_type_et_le_locuteur(client, planche, db_path):
    """UN geste, UN Ctrl+Z : le type revient ET le locuteur — pas une bulle muette d'abord."""
    rid = _creer_region(client, planche["id"], type="bulle")["id"]
    p = client.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": p})
    client.put(f"/api/regions/{rid}", json={"type": "personnage"})
    assert _type_et_locuteur(db_path, rid) == ("personnage", None)
    assert client.get("/api/undo/prochain").json()["description"] == \
        "modification d'une région et retrait de son locuteur"

    n = _annulations(db_path)
    res = client.post("/api/undo")
    assert res.status_code == 200, res.text
    assert (res.json()["acte"], res.json()["cible_table"]) == ("modification", "regions")
    assert res.json()["liens_non_rendus"] == 0
    assert _type_et_locuteur(db_path, rid) == ("bulle", p)
    assert _annulations(db_path) == n + 1                 # un seul acte d'annulation
    # Le Ctrl+Z suivant défait l'attribution du locuteur : le changement de type n'a pas
    # laissé de second acte derrière lui.
    assert client.get("/api/undo/prochain").json()["description"] == "attribution d'un locuteur"


def test_un_locuteur_disparu_ne_revient_pas_mais_le_type_si(client, planche, db_path):
    """Le personnage a été supprimé depuis : le type revient, le locuteur non, et la réponse
    le compte — comme un lien d'une suppression défaite."""
    rid = _creer_region(client, planche["id"], type="bulle")["id"]
    p = client.post("/api/personnages", json={"nom": "Fantome"}).json()["id"]
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": p})
    client.put(f"/api/regions/{rid}", json={"type": "case"})
    assert client.delete(f"/api/personnages/{p}").status_code == 204

    res = client.post("/api/undo")
    assert res.status_code == 200, res.text
    assert res.json()["liens_non_rendus"] == 1
    assert _type_et_locuteur(db_path, rid) == ("bulle", None)


def test_l_annulation_ne_repose_pas_un_locuteur_sur_une_region_devenue_muette(
        client, planche, db_path, derriere_proxy):
    """Le scénario mesuré par la relecture du 2026-10-12 : A pose puis retire, B passe la
    région en case, A annule. L'annulation se filtre par AGENT : celle de A ne voit pas le
    changement de type de B. Elle reposait le locuteur SUR LA CASE ; elle passe désormais
    l'acte, avec la seconde phrase, et le Ctrl+Z suivant de A défait son geste d'avant."""
    alice = {"Remote-User": "alice", "Remote-Groups": "bd-admins"}
    bob = {"Remote-User": "bob", "Remote-Groups": "bd-admins"}
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    p = client.post("/api/personnages", json={"nom": "Milou"}, headers=ADMIN).json()["id"]
    assert client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": p},
                      headers=alice).status_code == 200
    assert client.delete(f"/api/regions/{rid}/locuteur", headers=alice).status_code == 204
    assert client.put(f"/api/regions/{rid}", json={"type": "case"},
                      headers=bob).status_code == 200
    assert client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": p},
                      headers=alice).status_code == 422       # ce que la route répond à A

    res = client.post("/api/undo", headers=alice)
    assert res.status_code == 409, res.text
    corps = res.json()["detail"]
    assert corps["message"] == undo.PHRASE_IRRETABLISSABLE.format(
        description="retrait d'un locuteur")
    assert corps["ecarte"]["description"] == "retrait d'un locuteur"
    assert _type_et_locuteur(db_path, rid) == ("case", None)   # rien n'est reposé
    assert _annulations(db_path) == 0
    assert direct_query(db_path, "SELECT COUNT(*) n FROM evenement WHERE type = 'abandon' "
                                 "AND cible_table = 'annulation'")[0]["n"] == 1
    # L'acte est passé : le Ctrl+Z suivant de A défait son attribution d'avant.
    assert client.get("/api/undo/prochain", headers=alice).json()["description"] == \
        "attribution d'un locuteur"


# --------------------------------------------------------------------------- #
# Relecture croisée de 50c70bc — le locuteur est un champ GARDÉ de l'annulation (CONC-3).
# Les trois scénarios (h1, h2, h3) sont repris de la relecture, qui les a reproduits.
# --------------------------------------------------------------------------- #
ALICE = {"Remote-User": "alice", "Remote-Groups": "bd-admins"}
BOB = {"Remote-User": "bob", "Remote-Groups": "bd-admins"}


def _ev_count(db_path):
    return direct_query(db_path, "SELECT COUNT(*) n FROM evenement")[0]["n"]


def test_h1_ctrl_z_n_ecrase_pas_le_locuteur_pose_par_un_autre(client, planche, db_path,
                                                             derriere_proxy):
    """Alice passe la bulle de Tintin en case (Tintin part) ; Bob la repasse en bulle et lui
    donne Haddock ; Alice fait Ctrl+Z. La garde du type passe — le type est déjà celui
    qu'elle rendrait —, et `_poser_lien` remplaçait Haddock par Tintin : 200, en silence.
    Désormais, 409 nommant Bob, et rien d'écrit."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    x = client.post("/api/personnages", json={"nom": "Tintin"}, headers=ADMIN).json()["id"]
    y = client.post("/api/personnages", json={"nom": "Haddock"}, headers=ADMIN).json()["id"]
    assert client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": x},
                      headers=ALICE).status_code == 200
    assert client.put(f"/api/regions/{rid}", json={"type": "case"}, headers=ALICE).status_code == 200
    assert client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=BOB).status_code == 200
    assert client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": y},
                      headers=BOB).status_code == 200
    assert _type_et_locuteur(db_path, rid) == ("bulle", y)
    n = _ev_count(db_path)

    res = client.post("/api/undo", headers=ALICE)
    assert res.status_code == 409, res.text
    conflit = res.json()["detail"]["conflit"]
    assert (conflit["cible"], conflit["id"], conflit["champ"]) == ("bulle_locuteur", rid, "locuteur")
    assert conflit["valeur_actuelle"] == y
    assert conflit["auteur"]["login"] == "bob"
    assert "le locuteur" in res.json()["detail"]["message"]
    assert _type_et_locuteur(db_path, rid) == ("bulle", y), "le locuteur de Bob a été écrasé"
    assert _ev_count(db_path) == n                        # ni annulation, ni abandon : rien
    # L'acte n'est pas passé : il reste en tête de la pile d'Alice, comme tout conflit.
    assert client.get("/api/undo/prochain", headers=ALICE).json()["description"] == \
        "modification d'une région et retrait de son locuteur"


def test_h1_le_meme_locuteur_repose_par_un_autre_ne_bloque_pas(client, planche, db_path,
                                                                derriere_proxy):
    """Bob a remis le MÊME locuteur : rien ne se perd, l'annulation passe (`nouveau ==
    actuel`, la règle de `conflit.verifier`)."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    x = client.post("/api/personnages", json={"nom": "Tintin"}, headers=ADMIN).json()["id"]
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": x}, headers=ALICE)
    client.put(f"/api/regions/{rid}", json={"type": "case"}, headers=ALICE)
    client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=BOB)
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": x}, headers=BOB)
    res = client.post("/api/undo", headers=ALICE)
    assert res.status_code == 200, res.text
    assert _type_et_locuteur(db_path, rid) == ("bulle", x)


def test_variante_un_locuteur_defait_entre_temps_revient_avec_le_type(client, planche, db_path,
                                                                     derriere_proxy):
    """Ce que le correctif fait de la variante, écrit tel quel : Alice attribue Haddock, Bob
    passe la bulle en case (Haddock part avec le type), Alice annule son attribution — sans
    effet, il n'y est plus —, puis Bob fait Ctrl+Z : la bulle ET Haddock reviennent. La garde
    compare des VALEURS : le locuteur n'a pas changé depuis l'acte de Bob (aucun, avant et
    après l'annulation d'Alice), donc rien n'est écrasé. L'intention d'Alice, elle, ne se lit
    dans aucune valeur — ce n'est pas tranché ici."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    y = client.post("/api/personnages", json={"nom": "Haddock"}, headers=ADMIN).json()["id"]
    assert client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": y},
                      headers=ALICE).status_code == 200
    assert client.put(f"/api/regions/{rid}", json={"type": "case"}, headers=BOB).status_code == 200
    assert client.post("/api/undo", headers=ALICE).status_code == 200
    assert _type_et_locuteur(db_path, rid) == ("case", None)
    res = client.post("/api/undo", headers=BOB)
    assert res.status_code == 200, res.text
    assert _type_et_locuteur(db_path, rid) == ("bulle", y)


def test_h2_ctrl_z_ne_rend_pas_une_case_qui_parle(client, planche, db_path, derriere_proxy):
    """Alice passe une case en bulle ; Bob donne un locuteur à la bulle ; Alice fait Ctrl+Z.
    Le type revenait à `case` et le locuteur de Bob y restait : une case qui parle. Le
    retirer en silence effacerait le geste de Bob : 409 nommant Bob, rien d'écrit."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="case")["id"]
    y = client.post("/api/personnages", json={"nom": "Haddock"}, headers=ADMIN).json()["id"]
    assert client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ALICE).status_code == 200
    assert client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": y},
                      headers=BOB).status_code == 200
    n = _ev_count(db_path)

    res = client.post("/api/undo", headers=ALICE)
    assert res.status_code == 409, res.text
    conflit = res.json()["detail"]["conflit"]
    assert (conflit["champ"], conflit["valeur_actuelle"]) == ("locuteur", y)
    assert conflit["auteur"]["login"] == "bob"
    assert _type_et_locuteur(db_path, rid) == ("bulle", y)
    assert _ev_count(db_path) == n


def test_apres_un_409_retirer_a_la_main_le_geste_de_l_autre_ramene_le_meme_409(
        client, planche, db_path, derriere_proxy):
    """Le piège écrit dans `docs/undo.md` (contre-relecture d'ANN-8, c4), tel qu'il est : le
    retrait à la main est un geste d'Alice PLUS RÉCENT, que le Ctrl+Z suivant défait d'abord —
    Haddock revient —, puis le même 409. Ce test décrit le comportement, il ne le juge pas :
    s'il tombe, c'est que la décision a changé, et `docs/undo.md` avec elle."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="case")["id"]
    y = client.post("/api/personnages", json={"nom": "Haddock"}, headers=ADMIN).json()["id"]
    client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ALICE)
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": y}, headers=BOB)
    assert client.post("/api/undo", headers=ALICE).status_code == 409
    assert client.delete(f"/api/regions/{rid}/locuteur", headers=ALICE).status_code == 204

    r2 = client.post("/api/undo", headers=ALICE)
    assert (r2.status_code, r2.json()["description"]) == (200, "retrait d'un locuteur")
    assert _type_et_locuteur(db_path, rid) == ("bulle", y)
    r3 = client.post("/api/undo", headers=ALICE)
    assert r3.status_code == 409
    assert r3.json()["detail"]["conflit"]["champ"] == "locuteur"


def test_apres_un_409_le_ctrl_z_de_l_autre_debloque_la_pile(client, planche, db_path,
                                                           derriere_proxy):
    """Ce qui en sort : que l'autre défasse son propre geste. Son Ctrl+Z n'est pas un acte
    d'Alice, et le Ctrl+Z suivant d'Alice passe — la case revient, muette."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="case")["id"]
    y = client.post("/api/personnages", json={"nom": "Haddock"}, headers=ADMIN).json()["id"]
    client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ALICE)
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": y}, headers=BOB)
    assert client.post("/api/undo", headers=ALICE).status_code == 409
    assert client.post("/api/undo", headers=BOB).status_code == 200
    assert client.post("/api/undo", headers=ALICE).status_code == 200
    assert _type_et_locuteur(db_path, rid) == ("case", None)


# --------------------------------------------------------------------------- #
# « Passer ce geste » (Hugo, 2026-10-22) — après un 409 de conflit, à la demande.
# --------------------------------------------------------------------------- #
def _h2_refuse(client, planche, avant_alice=True):
    """Alice crée une case (un geste d'avant), la passe en bulle ; Bob donne un locuteur à
    la bulle ; le Ctrl+Z d'Alice est refusé. Rend (rid, y, réponse du refus)."""
    rid = _creer_region(client, planche["id"], headers=ALICE, type="case")["id"]
    y = client.post("/api/personnages", json={"nom": "Haddock"}, headers=ADMIN).json()["id"]
    client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ALICE)
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": y}, headers=BOB)
    refus = client.post("/api/undo", headers=ALICE)
    assert refus.status_code == 409, refus.text
    return rid, y, refus


def _abandons(db_path):
    return direct_query(db_path, "SELECT COUNT(*) n FROM evenement WHERE type = 'abandon' "
                                 "AND cible_table = 'annulation'")[0]["n"]


def test_passer_un_geste_refuse_le_sort_de_la_pile(client, planche, db_path, derriere_proxy):
    """Le 409 dit quel acte reste en tête ; « Passer » pose la trace `abandon`, le travail de
    Bob reste, et le Ctrl+Z suivant d'Alice remonte à son geste d'avant (la création)."""
    rid, y, refus = _h2_refuse(client, planche)
    ev = refus.json()["detail"]["passable"]["evenement_id"]
    assert ev == client.get("/api/undo/prochain", headers=ALICE).json()["evenement_id"]

    rep = client.post("/api/undo/passer", json={"evenement_id": ev}, headers=ALICE)
    assert rep.status_code == 200, rep.text
    assert rep.json() == {"evenement_id": ev, "description": "modification d'une région"}
    assert _abandons(db_path) == 1
    assert _type_et_locuteur(db_path, rid) == ("bulle", y)          # le travail de Bob reste
    assert client.get("/api/undo/prochain", headers=ALICE).json()["description"] == \
        "création d'une région"


def test_passer_ne_passe_rien_si_le_conflit_ne_tient_plus(client, planche, db_path,
                                                          derriere_proxy):
    """Bob a défait son geste entre le refus et le clic : le geste d'Alice s'annule de
    nouveau. Rien n'est passé ni défait — « refaites Ctrl+Z »."""
    rid, y, refus = _h2_refuse(client, planche)
    ev = refus.json()["detail"]["passable"]["evenement_id"]
    assert client.post("/api/undo", headers=BOB).status_code == 200
    n = _ev_count(db_path)
    rep = client.post("/api/undo/passer", json={"evenement_id": ev}, headers=ALICE)
    assert rep.status_code == 409, rep.text
    assert "refaites Ctrl+Z" in rep.json()["detail"]
    assert _ev_count(db_path) == n
    assert _type_et_locuteur(db_path, rid) == ("bulle", None)
    assert client.post("/api/undo", headers=ALICE).status_code == 200


def test_on_ne_passe_que_son_prochain_geste(client, planche, db_path, derriere_proxy):
    """Ni le geste d'un autre, ni un geste enfoui sous un plus récent : 409, rien d'écrit."""
    rid, y, refus = _h2_refuse(client, planche)
    ev = refus.json()["detail"]["passable"]["evenement_id"]
    n = _ev_count(db_path)
    assert client.post("/api/undo/passer", json={"evenement_id": ev},
                       headers=BOB).status_code == 409
    creation = direct_query(db_path, "SELECT id FROM evenement WHERE type = 'creation' "
                                     "AND cible_table = 'regions' AND cible_id = ?", (rid,))[0]["id"]
    assert client.post("/api/undo/passer", json={"evenement_id": creation},
                       headers=ALICE).status_code == 409
    assert _ev_count(db_path) == n


def test_h2_seul_les_deux_ctrl_z_rendent_la_case_muette(client, planche, db_path):
    """Seul à son poste, le même enchaînement se défait sans conflit : le Ctrl+Z du
    locuteur passe d'abord, et la case revient sans rien."""
    rid = _creer_region(client, planche["id"], type="case")["id"]
    y = client.post("/api/personnages", json={"nom": "Haddock"}).json()["id"]
    client.put(f"/api/regions/{rid}", json={"type": "bulle"})
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": y})
    assert client.post("/api/undo").status_code == 200
    assert client.post("/api/undo").status_code == 200
    assert _type_et_locuteur(db_path, rid) == ("case", None)


def test_h3_un_put_qui_ne_change_pas_le_type_ne_retire_rien(client, planche, db_path):
    """PUT {type: 'case'} sur une case d'avant ANN-8 qui porte un locuteur : le type ne
    CHANGE pas, rien n'est retiré — le rattrapage est l'affaire de l'outil."""
    rid = _creer_region(client, planche["id"], type="case")["id"]
    p = client.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]
    c = sqlite3.connect(db_path)
    c.execute("INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?)", (rid, p))
    c.commit()
    c.close()
    rep = client.put(f"/api/regions/{rid}", json={"type": "case"})
    assert rep.status_code == 200
    assert "locuteur_retire" not in rep.json(), "un PUT qui ne change pas le type a retiré"
    assert _type_et_locuteur(db_path, rid) == ("case", p)


# --------------------------------------------------------------------------- #
# Le changement de type PHOTOGRAPHIE les liens vus (`liens_vus`), et l'annulation compare à
# cette photographie — non plus à « aucun ». Reproduit par la contre-relecture du 2026-10-21
# (c3, c5) : sur une base d'avant ANN-8, la seule auteure d'un passage case → bulle recevait
# un 409 faux à son propre Ctrl+Z.
# --------------------------------------------------------------------------- #
def _poser_a_la_main(db_path, region_id, personnage_id):
    """Un locuteur posé hors routes, comme une base d'avant ANN-8 le porte sur une case."""
    c = sqlite3.connect(db_path)
    c.execute("INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?)",
              (region_id, personnage_id))
    c.commit()
    c.close()


def _dernier_avant(db_path, region_id):
    ev = direct_query(db_path, "SELECT avant FROM evenement WHERE cible_table = 'regions' "
                               "AND type = 'modification' AND cible_id = ? "
                               "ORDER BY id DESC LIMIT 1", (region_id,))[0]
    return json.loads(ev["avant"])


def test_le_changement_de_type_photographie_les_liens_vus_sous_une_cle_a_part(
        client, planche, db_path):
    """`liens_vus` dit ce que la région portait ; `locuteur` ce que le changement a RETIRÉ.
    Deux clés, deux sens : une bulle qui devient cartouche voit Tintin et ne retire rien."""
    rid = _creer_region(client, planche["id"], type="bulle")["id"]
    p = client.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": p})

    client.put(f"/api/regions/{rid}", json={"type": "cartouche"})
    avant = _dernier_avant(db_path, rid)
    assert avant["liens_vus"]["locuteur"] == p
    assert "locuteur" not in avant

    client.put(f"/api/regions/{rid}", json={"type": "case"})
    avant = _dernier_avant(db_path, rid)
    assert (avant["liens_vus"]["locuteur"], avant["locuteur"]) == (p, p)

    client.put(f"/api/regions/{rid}", json={"type": "bulle"})
    assert _dernier_avant(db_path, rid)["liens_vus"]["locuteur"] is None


def test_un_geste_sans_changement_de_type_ne_photographie_rien(client, planche, db_path):
    rid = _creer_region(client, planche["id"], type="bulle")["id"]
    client.put(f"/api/regions/{rid}", json={"x": 7})
    client.put(f"/api/regions/{rid}", json={"type": "bulle"})
    assert "liens_vus" not in _dernier_avant(db_path, rid)


def test_c3_une_case_d_avant_qui_parlait_repassee_en_bulle_se_defait_sans_409(
        client, planche, db_path):
    """Une personne seule, une case d'avant ANN-8 qui porte déjà Zed ; elle la passe en
    bulle, puis Ctrl+Z. Personne n'a rien fait depuis : l'annulation passe, et rend l'état
    d'avant TEL QU'IL ÉTAIT — la case et Zed. Le nettoyage est l'affaire de l'outil."""
    rid = _creer_region(client, planche["id"], type="case")["id"]
    z = client.post("/api/personnages", json={"nom": "Zed"}).json()["id"]
    _poser_a_la_main(db_path, rid, z)
    assert client.put(f"/api/regions/{rid}", json={"type": "bulle"}).status_code == 200

    res = client.post("/api/undo")
    assert res.status_code == 200, res.text
    assert _type_et_locuteur(db_path, rid) == ("case", z)


def test_c5_le_locuteur_d_une_bulle_devenue_case_avant_ann8_ne_bloque_pas_son_auteure(
        client, planche, db_path):
    """Le cas réaliste : Zed posé par la route sur une bulle, la bulle devenue case AVANT
    ANN-8 (sans retrait, simulé en SQL). Le 409 disait « depuis un autre écran de ce même
    compte », avec une date antérieure à l'acte qu'on défaisait."""
    rid = _creer_region(client, planche["id"], type="bulle")["id"]
    z = client.post("/api/personnages", json={"nom": "Zed"}).json()["id"]
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": z})
    c = sqlite3.connect(db_path)
    c.execute("UPDATE regions SET type = 'case' WHERE id = ?", (rid,))
    c.commit()
    c.close()
    assert client.put(f"/api/regions/{rid}", json={"type": "bulle"}).status_code == 200

    res = client.post("/api/undo")
    assert res.status_code == 200, res.text
    assert _type_et_locuteur(db_path, rid) == ("case", z)


def test_un_locuteur_vu_puis_change_par_un_autre_bloque_encore(client, planche, db_path,
                                                               derriere_proxy):
    """La photographie n'ouvre pas la porte que h2 ferme : Alice passe en bulle une case qui
    portait Zed ; Bob remplace Zed par Haddock ; le Ctrl+Z d'Alice rendrait une case qui
    porte Haddock, caché. 409 nommant Bob, rien d'écrit."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="case")["id"]
    z = client.post("/api/personnages", json={"nom": "Zed"}, headers=ADMIN).json()["id"]
    y = client.post("/api/personnages", json={"nom": "Haddock"}, headers=ADMIN).json()["id"]
    _poser_a_la_main(db_path, rid, z)
    assert client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ALICE).status_code == 200
    assert client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": y},
                      headers=BOB).status_code == 200
    n = _ev_count(db_path)

    res = client.post("/api/undo", headers=ALICE)
    assert res.status_code == 409, res.text
    conflit = res.json()["detail"]["conflit"]
    assert (conflit["champ"], conflit["valeur_actuelle"], conflit["auteur"]["login"]) == \
        ("locuteur", y, "bob")
    assert _type_et_locuteur(db_path, rid) == ("bulle", y)
    assert _ev_count(db_path) == n


def test_un_locuteur_vu_puis_retire_par_un_autre_ne_bloque_pas(client, planche, db_path,
                                                               derriere_proxy):
    """Alice passe en bulle une case qui portait Zed ; Bob retire Zed ; Alice fait Ctrl+Z.
    La case revient sans locuteur : rien n'est écrasé, rien n'est caché — l'annulation ne
    repose rien sur une case. Elle passe."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="case")["id"]
    z = client.post("/api/personnages", json={"nom": "Zed"}, headers=ADMIN).json()["id"]
    _poser_a_la_main(db_path, rid, z)
    assert client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=ALICE).status_code == 200
    assert client.delete(f"/api/regions/{rid}/locuteur", headers=BOB).status_code == 204

    res = client.post("/api/undo", headers=ALICE)
    assert res.status_code == 200, res.text
    assert _type_et_locuteur(db_path, rid) == ("case", None)


def test_ce_que_l_acte_a_retire_n_est_pas_ce_qu_il_a_laisse(client, planche, db_path,
                                                             derriere_proxy):
    """Une boîte personnage d'avant ANN-8 porte Zed ; Alice la passe en case — Zed part,
    vu ET retiré. Bob repasse la case en bulle et lui donne Zed. Le Ctrl+Z d'Alice rendrait
    une boîte personnage qui porte Zed, caché : ce que l'acte avait LAISSÉ était « aucun »,
    pas la photographie. 409 sur le locuteur, avant même celui du type."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="personnage")["id"]
    z = client.post("/api/personnages", json={"nom": "Zed"}, headers=ADMIN).json()["id"]
    _poser_a_la_main(db_path, rid, z)
    assert client.put(f"/api/regions/{rid}", json={"type": "case"}, headers=ALICE).status_code == 200
    assert client.put(f"/api/regions/{rid}", json={"type": "bulle"}, headers=BOB).status_code == 200
    assert client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": z},
                      headers=BOB).status_code == 200
    res = client.post("/api/undo", headers=ALICE)
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["conflit"]["champ"] == "locuteur"
    assert _type_et_locuteur(db_path, rid) == ("bulle", z)


def test_un_acte_d_avant_la_photographie_garde_la_regle_d_alors(client, planche, db_path):
    """Un changement de type journalisé sans `liens_vus` — avant ce correctif : la garde y
    suppose qu'aucun locuteur n'était laissé, comme elle le faisait. Sur une case d'avant
    ANN-8, le 409 de c3 y reste : c'est écrit (`docs/undo.md`)."""
    rid = _creer_region(client, planche["id"], type="case")["id"]
    z = client.post("/api/personnages", json={"nom": "Zed"}).json()["id"]
    _poser_a_la_main(db_path, rid, z)
    client.put(f"/api/regions/{rid}", json={"type": "bulle"})
    c = sqlite3.connect(db_path)
    c.execute("UPDATE evenement SET avant = json_remove(avant, '$.liens_vus') "
              "WHERE cible_table = 'regions' AND type = 'modification' AND cible_id = ?", (rid,))
    c.commit()
    c.close()
    res = client.post("/api/undo")
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["conflit"]["champ"] == "locuteur"
    assert _type_et_locuteur(db_path, rid) == ("bulle", z)


# --------------------------------------------------------------------------- #
# ANN-8 — l'annulation d'un `lien` ou d'un `delien` est GARDÉE (trouvé par Hugo à la QA du
# lot 1, 2026-10-23, présent depuis D1) : `_inverser` retirait ou reposait le lien sans
# regarder ce que la région portait — le Ctrl+Z de Proprio retirait le locuteur que
# Stagiaire avait mis à la place du sien.
# --------------------------------------------------------------------------- #
PROPRIO = {"Remote-User": "proprio", "Remote-Groups": "bd-admins"}
STAGIAIRE = {"Remote-User": "stagiaire", "Remote-Groups": "bd-admins"}


def _lien(db_path, table, rid):
    r = _un(db_path, f"SELECT personnage_id FROM {table} WHERE region_id = ?", (rid,))
    return r["personnage_id"] if r else None


def _personnages(client, *noms):
    return [client.post("/api/personnages", json={"nom": n}, headers=ADMIN).json()["id"]
            for n in noms]


def _poser(client, rid, chemin, pid, qui):
    rep = client.put(f"/api/regions/{rid}/{chemin}", json={"personnage_id": pid}, headers=qui)
    assert rep.status_code == 200, rep.text


def _retirer(client, rid, chemin, qui):
    assert client.delete(f"/api/regions/{rid}/{chemin}", headers=qui).status_code == 204


def _refus_de_lien(res, rid, table, champ, valeur, login):
    """Le 409 de la garde des liens : nommé, avec le personnage présent et son auteur."""
    assert res.status_code == 409, res.text
    detail = res.json()["detail"]
    assert detail["conflit"]["cible"] == table and detail["conflit"]["id"] == rid
    assert (detail["conflit"]["champ"], detail["conflit"]["valeur_actuelle"]) == (champ, valeur)
    assert detail["conflit"]["auteur"]["login"] == login
    return detail


def test_le_ctrl_z_d_un_locuteur_ne_retire_pas_celui_qu_un_autre_a_mis_a_sa_place(
        client, planche, db_path, derriere_proxy):
    """Le cas de Hugo, tel quel. Proprio donne Zed à une bulle ; Stagiaire le remplace par
    Yann ; le Ctrl+Z de Proprio retirait Yann, et la bulle n'avait plus de locuteur. Désormais
    409 nommant Stagiaire, rien d'écrit, et le refus offre de passer le geste."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    zed, yann = _personnages(client, "Zed QA", "Yann QA")
    _poser(client, rid, "locuteur", zed, PROPRIO)
    acte = direct_query(db_path, "SELECT MAX(id) id FROM evenement")[0]["id"]
    _poser(client, rid, "locuteur", yann, STAGIAIRE)
    n = _ev_count(db_path)

    res = client.post("/api/undo", headers=PROPRIO)
    detail = _refus_de_lien(res, rid, "bulle_locuteur", "locuteur", yann, "stagiaire")
    assert detail["message"].startswith("Conflit : le locuteur a été modifié par stagiaire")
    assert detail["passable"] == {"evenement_id": acte}
    assert _lien(db_path, "bulle_locuteur", rid) == yann       # le geste de Stagiaire reste
    assert _ev_count(db_path) == n                              # ni annulation, ni abandon

    # « Passer ce geste » : le travail de Stagiaire reste, la pile de Proprio est vide.
    rep = client.post("/api/undo/passer", json={"evenement_id": acte}, headers=PROPRIO)
    assert rep.status_code == 200, rep.text
    assert rep.json() == {"evenement_id": acte, "description": "attribution d'un locuteur"}
    assert _lien(db_path, "bulle_locuteur", rid) == yann
    assert client.get("/api/undo/prochain", headers=PROPRIO).json() is None


def test_le_ctrl_z_d_un_retrait_ne_remplace_pas_le_locuteur_pose_depuis(
        client, planche, db_path, derriere_proxy):
    """Le `delien` : Proprio retire Zed ; Stagiaire donne Yann à la bulle muette ; le Ctrl+Z
    de Proprio remplaçait Yann par Zed. 409 nommant Stagiaire."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    zed, yann = _personnages(client, "Zed QA", "Yann QA")
    _poser(client, rid, "locuteur", zed, PROPRIO)
    _retirer(client, rid, "locuteur", PROPRIO)
    _poser(client, rid, "locuteur", yann, STAGIAIRE)
    n = _ev_count(db_path)
    _refus_de_lien(client.post("/api/undo", headers=PROPRIO), rid, "bulle_locuteur",
                   "locuteur", yann, "stagiaire")
    assert _lien(db_path, "bulle_locuteur", rid) == yann
    assert _ev_count(db_path) == n


def test_le_ctrl_z_d_un_remplacement_ne_remet_pas_l_ancien_par_dessus_un_autre(
        client, planche, db_path, derriere_proxy):
    """Un `lien` qui en remplaçait un : Proprio passe de Zed à Yann ; Stagiaire met Milou ;
    le Ctrl+Z de Proprio remettait Zed par-dessus Milou."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    zed, yann, milou = _personnages(client, "Zed QA", "Yann QA", "Milou")
    _poser(client, rid, "locuteur", zed, PROPRIO)
    _poser(client, rid, "locuteur", yann, PROPRIO)
    _poser(client, rid, "locuteur", milou, STAGIAIRE)
    _refus_de_lien(client.post("/api/undo", headers=PROPRIO), rid, "bulle_locuteur",
                   "locuteur", milou, "stagiaire")
    assert _lien(db_path, "bulle_locuteur", rid) == milou


def test_le_ctrl_z_d_un_personnage_montre_est_garde_comme_le_locuteur(
        client, planche, db_path, derriere_proxy):
    """Le même trou pour la présence, dans ses deux sens : le `lien`, puis le `delien`."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="personnage")["id"]
    zed, yann = _personnages(client, "Zed QA", "Yann QA")
    _poser(client, rid, "personnage", zed, PROPRIO)
    _poser(client, rid, "personnage", yann, STAGIAIRE)
    detail = _refus_de_lien(client.post("/api/undo", headers=PROPRIO), rid,
                            "personnage_presence", "presence", yann, "stagiaire")
    assert detail["message"].startswith("Conflit : le personnage montré a été modifié par "
                                        "stagiaire")
    assert "passable" in detail
    assert _lien(db_path, "personnage_presence", rid) == yann

    autre = _creer_region(client, planche["id"], headers=ADMIN, type="personnage")["id"]
    _poser(client, autre, "personnage", zed, STAGIAIRE)
    _retirer(client, autre, "personnage", STAGIAIRE)
    _poser(client, autre, "personnage", yann, PROPRIO)
    _refus_de_lien(client.post("/api/undo", headers=STAGIAIRE), autre,
                   "personnage_presence", "presence", yann, "proprio")
    assert _lien(db_path, "personnage_presence", autre) == yann


def test_le_meme_lien_qu_aujourd_hui_ne_bloque_rien(client, planche, db_path, derriere_proxy):
    """La garde compare des VALEURS : la région porte ce que l'acte avait laissé (Stagiaire
    est passée par Yann puis revenue à Zed), ou ce que l'annulation laissera (Stagiaire a
    déjà retiré le locuteur ; Zed déjà remis par une autre) — rien ne se perd."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    zed, yann = _personnages(client, "Zed QA", "Yann QA")
    _poser(client, rid, "locuteur", zed, PROPRIO)
    _poser(client, rid, "locuteur", yann, STAGIAIRE)
    _poser(client, rid, "locuteur", zed, STAGIAIRE)
    assert client.post("/api/undo", headers=PROPRIO).status_code == 200
    assert _lien(db_path, "bulle_locuteur", rid) is None        # le lien de l'acte part

    deux = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    _poser(client, deux, "locuteur", zed, PROPRIO)
    _retirer(client, deux, "locuteur", STAGIAIRE)
    assert client.post("/api/undo", headers=PROPRIO).status_code == 200
    assert _lien(db_path, "bulle_locuteur", deux) is None

    trois = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    _poser(client, trois, "locuteur", zed, PROPRIO)
    _retirer(client, trois, "locuteur", PROPRIO)
    _poser(client, trois, "locuteur", zed, STAGIAIRE)            # Zed, remis par une autre
    assert client.post("/api/undo", headers=PROPRIO).status_code == 200
    assert _lien(db_path, "bulle_locuteur", trois) == zed

    # Et seul, sans personne d'autre : le cas ordinaire n'a pas changé.
    quatre = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    _poser(client, quatre, "locuteur", zed, PROPRIO)
    _poser(client, quatre, "locuteur", yann, PROPRIO)
    assert client.post("/api/undo", headers=PROPRIO).status_code == 200
    assert _lien(db_path, "bulle_locuteur", quatre) == zed
    assert client.post("/api/undo", headers=PROPRIO).status_code == 200
    assert _lien(db_path, "bulle_locuteur", quatre) is None


def test_un_locuteur_ote_par_un_changement_de_type_nomme_qui_l_a_ote(
        client, planche, db_path, derriere_proxy):
    """Proprio passe de Zed à Yann ; Stagiaire passe la bulle en case (Yann part avec le
    type), puis la repasse en bulle. Le Ctrl+Z de Proprio remettrait Zed sur une bulle que
    Stagiaire a laissée muette : refusé, et le refus nomme Stagiaire — le retrait est écrit
    dans un acte sur `regions`, pas sur `bulle_locuteur` (`conflit.auteur_des_champs`)."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    zed, yann = _personnages(client, "Zed QA", "Yann QA")
    _poser(client, rid, "locuteur", zed, PROPRIO)
    _poser(client, rid, "locuteur", yann, PROPRIO)
    assert client.put(f"/api/regions/{rid}", json={"type": "case"},
                      headers=STAGIAIRE).status_code == 200
    assert client.put(f"/api/regions/{rid}", json={"type": "bulle"},
                      headers=STAGIAIRE).status_code == 200
    _refus_de_lien(client.post("/api/undo", headers=PROPRIO), rid, "bulle_locuteur",
                   "locuteur", None, "stagiaire")
    assert _type_et_locuteur(db_path, rid) == ("bulle", None)


def test_un_type_qui_ne_montre_plus_le_lien_passe_l_acte_avant_la_garde(
        client, planche, db_path, derriere_proxy):
    """L'ordre des gardes : la bulle de Proprio (Zed puis Yann) est passée en case par
    Stagiaire — Yann part. Le Ctrl+Z de Proprio ne peut plus reposer Zed sur une case : l'acte
    est PASSÉ (« l'état d'avant ne peut plus être rétabli »), et non refusé par un conflit
    qui lui demanderait de le passer à la main."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    zed, yann = _personnages(client, "Zed QA", "Yann QA")
    _poser(client, rid, "locuteur", zed, PROPRIO)
    _poser(client, rid, "locuteur", yann, PROPRIO)
    assert client.put(f"/api/regions/{rid}", json={"type": "case"},
                      headers=STAGIAIRE).status_code == 200
    res = client.post("/api/undo", headers=PROPRIO)
    assert res.status_code == 409, res.text
    detail = res.json()["detail"]
    assert set(detail) == {"message", "ecarte"}, detail
    assert detail["message"] == ("Ne s'annule plus : attribution d'un locuteur — "
                                 "l'état d'avant ne peut plus être rétabli.")
    assert _type_et_locuteur(db_path, rid) == ("case", None)


# Relecture croisée de la garde des liens (2026-10-23) — ses constats, devenus des tests.
def _effacer_personnage(client, pid, qui=ADMIN):
    assert client.delete(f"/api/personnages/{pid}", headers=qui).status_code == 204


def test_le_refus_ne_nomme_pas_un_geste_d_avant_l_acte(client, planche, db_path,
                                                      derriere_proxy):
    """R1 — l'auteur ne se cherche qu'APRÈS l'acte défait. Stagiaire a retiré un locuteur
    bien avant ; Proprio passe de Zed à Yann ; l'administrateur remplace Yann par W, puis
    supprime W (CASCADE, rien au journal). Le Ctrl+Z de Proprio est refusé — et le refus dit
    « modifié ailleurs », pas « par stagiaire », qui n'a rien fait depuis l'acte."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    x, zed, yann, w = _personnages(client, "X", "Zed QA", "Yann QA", "W")
    _poser(client, rid, "locuteur", x, STAGIAIRE)
    _retirer(client, rid, "locuteur", STAGIAIRE)
    _poser(client, rid, "locuteur", zed, PROPRIO)
    _poser(client, rid, "locuteur", yann, PROPRIO)
    _poser(client, rid, "locuteur", w, ADMIN)
    _effacer_personnage(client, w)
    res = client.post("/api/undo", headers=PROPRIO)
    assert res.status_code == 409, res.text
    conflit = res.json()["detail"]["conflit"]
    assert (conflit["champ"], conflit["valeur_actuelle"], conflit["auteur"]) == \
        ("locuteur", None, None)
    assert "stagiaire" not in res.text and "modifié ailleurs" in res.text
    assert _lien(db_path, "bulle_locuteur", rid) is None


def test_un_personnage_laisse_puis_supprime_ne_bloque_pas_le_ctrl_z(client, planche, db_path,
                                                                   derriere_proxy):
    """R2 — Proprio, seule : Zed, puis Yann, puis elle supprime le personnage Yann (CASCADE).
    La bulle ne porte plus rien, et ce n'est le geste de personne sur elle : « aucun » est
    admis, et Ctrl+Z rend Zed, comme avant la garde. Même chose quand l'historique de la
    région porte les gestes d'un autre, d'avant l'acte (le décor de R1)."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    zed, yann = _personnages(client, "Zed QA", "Yann QA")
    _poser(client, rid, "locuteur", zed, PROPRIO)
    _poser(client, rid, "locuteur", yann, PROPRIO)
    _effacer_personnage(client, yann, PROPRIO)
    res = client.post("/api/undo", headers=PROPRIO)
    assert res.status_code == 200, res.text
    assert _lien(db_path, "bulle_locuteur", rid) == zed

    autre = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    x, a, b = _personnages(client, "X", "A", "B")
    _poser(client, autre, "locuteur", x, STAGIAIRE)
    _retirer(client, autre, "locuteur", STAGIAIRE)
    _poser(client, autre, "locuteur", a, STAGIAIRE)
    _poser(client, autre, "locuteur", b, PROPRIO)
    _effacer_personnage(client, b, PROPRIO)
    res = client.post("/api/undo", headers=PROPRIO)
    assert res.status_code == 200, res.text
    assert _lien(db_path, "bulle_locuteur", autre) == a


def test_un_personnage_montre_laisse_puis_supprime_ne_bloque_pas_le_ctrl_z(
        client, planche, db_path, derriere_proxy):
    """R2, pour la présence : le personnage montré laissé par l'acte a été supprimé."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="personnage")["id"]
    zed, yann = _personnages(client, "Zed QA", "Yann QA")
    _poser(client, rid, "personnage", zed, PROPRIO)
    _poser(client, rid, "personnage", yann, PROPRIO)
    _effacer_personnage(client, yann, PROPRIO)
    assert client.post("/api/undo", headers=PROPRIO).status_code == 200
    assert _lien(db_path, "personnage_presence", rid) == zed


def test_une_fusion_faite_depuis_fait_refuser_l_annulation_du_lien(client, planche, db_path,
                                                                  derriere_proxy):
    """R3, ASSUMÉ (`docs/undo.md`) : la fusion de personnages réaffecte les locuteurs sans
    rien écrire sous `bulle_locuteur` — la journaliser rendrait chaque lien réaffecté
    annulable un par un par Ctrl+Z, ce qui serait pire. Une fusion faite depuis l'acte fait
    donc refuser l'annulation du lien qu'elle a réaffecté, « modifié ailleurs », même seule ;
    le geste se passe, et le locuteur fusionné reste."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    doublon, cible = _personnages(client, "Haddok", "Haddock")
    _poser(client, rid, "locuteur", doublon, PROPRIO)
    rep = client.post(f"/api/personnages/{doublon}/fusion", json={"cible_id": cible},
                      headers=PROPRIO)
    assert rep.status_code == 200, rep.text
    assert _lien(db_path, "bulle_locuteur", rid) == cible
    res = client.post("/api/undo", headers=PROPRIO)
    assert res.status_code == 409, res.text
    detail = res.json()["detail"]
    assert (detail["conflit"]["valeur_actuelle"], detail["conflit"]["auteur"]) == (cible, None)
    passe = client.post("/api/undo/passer", json=detail["passable"], headers=PROPRIO)
    assert passe.status_code == 200, passe.text
    assert _lien(db_path, "bulle_locuteur", rid) == cible


def test_apres_un_geste_passe_les_gestes_d_avant_s_annulent(client, planche, db_path,
                                                           derriere_proxy):
    """R4 — Proprio : A, puis B, puis C ; B est supprimé. Le Ctrl+Z de C est passé (B ne peut
    plus revenir). Les gestes d'avant se refusaient alors un à un, face à C — le travail de
    Proprio elle-même. Ce qu'a laissé un geste plus récent de la même personne, PASSÉ, et que
    rien n'a changé depuis, est admis : B ne revient pas (supprimé), A revient, puis rien."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    a, b, c = _personnages(client, "A", "B", "C")
    for pid in (a, b, c):
        _poser(client, rid, "locuteur", pid, PROPRIO)
    _effacer_personnage(client, b, PROPRIO)
    r3 = client.post("/api/undo", headers=PROPRIO)
    assert r3.status_code == 409 and "ecarte" in r3.json()["detail"], r3.text
    assert client.post("/api/undo", headers=PROPRIO).status_code == 200      # e2 : A revient
    assert _lien(db_path, "bulle_locuteur", rid) == a
    assert client.post("/api/undo", headers=PROPRIO).status_code == 200      # e1 : plus rien
    assert _lien(db_path, "bulle_locuteur", rid) is None
    assert client.get("/api/undo/prochain", headers=PROPRIO).json() is None


def test_passer_apres_le_conflit_d_un_autre_ne_debloque_pas_le_geste_d_avant(
        client, planche, db_path, derriere_proxy):
    """L'admission de R4 ne couvre pas le conflit d'un AUTRE : Proprio, Zed puis Yann ;
    Stagiaire met Milou ; Proprio passe le refus de son Yann. Son Ctrl+Z suivant (Zed) est
    refusé à son tour, et nomme Stagiaire : le dernier geste sur le lien est le sien."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    zed, yann, milou = _personnages(client, "Zed QA", "Yann QA", "Milou")
    _poser(client, rid, "locuteur", zed, PROPRIO)
    _poser(client, rid, "locuteur", yann, PROPRIO)
    _poser(client, rid, "locuteur", milou, STAGIAIRE)
    refus = client.post("/api/undo", headers=PROPRIO)
    assert refus.status_code == 409, refus.text
    assert client.post("/api/undo/passer", json=refus.json()["detail"]["passable"],
                       headers=PROPRIO).status_code == 200
    _refus_de_lien(client.post("/api/undo", headers=PROPRIO), rid, "bulle_locuteur",
                   "locuteur", milou, "stagiaire")
    assert _lien(db_path, "bulle_locuteur", rid) == milou


def test_la_valeur_d_un_geste_passe_remise_par_un_autre_n_est_pas_admise(
        client, planche, db_path, derriere_proxy):
    """L'admission de R4 exige que RIEN n'ait touché le lien depuis le geste passé : Proprio,
    Zed puis Yann ; Stagiaire met Milou, Proprio passe le refus de son Yann ; Stagiaire remet
    Yann. Le Ctrl+Z de Proprio (Zed) retirerait le Yann de Stagiaire : refusé, et le refus
    nomme Stagiaire, même si la valeur est celle du geste passé."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    zed, yann, milou = _personnages(client, "Zed QA", "Yann QA", "Milou")
    _poser(client, rid, "locuteur", zed, PROPRIO)
    _poser(client, rid, "locuteur", yann, PROPRIO)
    _poser(client, rid, "locuteur", milou, STAGIAIRE)
    refus = client.post("/api/undo", headers=PROPRIO)
    assert client.post("/api/undo/passer", json=refus.json()["detail"]["passable"],
                       headers=PROPRIO).status_code == 200
    _poser(client, rid, "locuteur", yann, STAGIAIRE)
    _refus_de_lien(client.post("/api/undo", headers=PROPRIO), rid, "bulle_locuteur",
                   "locuteur", yann, "stagiaire")
    assert _lien(db_path, "bulle_locuteur", rid) == yann


def test_un_geste_plus_recent_non_passe_n_est_pas_admis(client, planche, db_path,
                                                       derriere_proxy):
    """L'admission de R4 demande un geste PASSÉ (`abandon`), pas seulement un geste du même
    agent. Par les routes, un geste plus récent non passé est d'abord en tête de la pile, si
    bien que l'exigence ne se voit pas ; `annuler(evenement_id=…)`, qui nomme un acte, la
    rend visible : Proprio, Zed puis Yann ; viser l'acte de Zed retirerait Yann, que rien n'a
    passé — refusé, et rien n'est écrit."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    zed, yann = _personnages(client, "Zed QA", "Yann QA")
    _poser(client, rid, "locuteur", zed, PROPRIO)
    acte = direct_query(db_path, "SELECT MAX(id) id FROM evenement")[0]["id"]
    _poser(client, rid, "locuteur", yann, PROPRIO)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        try:
            undo.annuler(conn, evenement_id=acte, agent="proprio",
                         ecrivable=lambda lieux: True)
        except conflit.Perime as exc:
            assert (exc.champ, exc.valeur_actuelle) == ("locuteur", yann)
        else:
            raise AssertionError("l'annulation a retiré un geste plus récent, non passé")
    finally:
        conn.rollback()
        conn.close()
    assert _lien(db_path, "bulle_locuteur", rid) == yann


def test_le_geste_passe_d_un_autre_agent_n_est_pas_admis(client, planche, db_path,
                                                        derriere_proxy):
    """L'admission de R4 est celle du MÊME agent : Proprio donne Zed ; Stagiaire le remplace
    par Yann ; Zed est supprimé, et le Ctrl+Z de Stagiaire est passé (Zed ne revient pas).
    Le Ctrl+Z de Proprio retirerait Yann, que Stagiaire a laissé : refusé."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    zed, yann = _personnages(client, "Zed QA", "Yann QA")
    _poser(client, rid, "locuteur", zed, PROPRIO)
    _poser(client, rid, "locuteur", yann, STAGIAIRE)
    _effacer_personnage(client, zed)
    r = client.post("/api/undo", headers=STAGIAIRE)
    assert r.status_code == 409 and "ecarte" in r.json()["detail"], r.text
    _refus_de_lien(client.post("/api/undo", headers=PROPRIO), rid, "bulle_locuteur",
                   "locuteur", yann, "stagiaire")
    assert _lien(db_path, "bulle_locuteur", rid) == yann


def test_un_lien_rendu_par_une_suppression_retablie_nomme_qui_l_a_retablie(
        client, planche, db_path, derriere_proxy):
    """Contrôle de la relecture : Proprio retire Zed ; Stagiaire donne Yann, supprime la
    région, puis la rétablit (Ctrl+Z, qui rend Yann). Le Ctrl+Z de Proprio est refusé, et
    nomme Stagiaire — l'annulation d'une suppression compte parmi les gestes d'après."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    zed, yann = _personnages(client, "Zed QA", "Yann QA")
    _poser(client, rid, "locuteur", zed, PROPRIO)
    _retirer(client, rid, "locuteur", PROPRIO)
    _poser(client, rid, "locuteur", yann, STAGIAIRE)
    assert client.delete(f"/api/regions/{rid}", headers=STAGIAIRE).status_code == 204
    assert client.post("/api/undo", headers=STAGIAIRE).status_code == 200
    assert _lien(db_path, "bulle_locuteur", rid) == yann
    _refus_de_lien(client.post("/api/undo", headers=PROPRIO), rid, "bulle_locuteur",
                   "locuteur", yann, "stagiaire")


def test_passable_designe_l_acte_relu_sous_le_verrou(client, planche, db_path, derriere_proxy,
                                                    monkeypatch):
    """R6 — `passable` venait de l'acte lu AVANT le verrou d'écriture : un geste arrivé entre
    les deux aurait fait désigner le mauvais. La lecture d'avant le verrou est ici faussée
    (la première seulement) : le refus désigne l'acte que l'annulation a relu et refusé."""
    rid = _creer_region(client, planche["id"], headers=ADMIN, type="bulle")["id"]
    zed, yann = _personnages(client, "Zed QA", "Yann QA")
    _poser(client, rid, "locuteur", zed, PROPRIO)
    acte = direct_query(db_path, "SELECT MAX(id) id FROM evenement")[0]["id"]
    _poser(client, rid, "locuteur", yann, STAGIAIRE)
    vraie, appels = undo.derniere_action_annulable, []

    def faussee(conn, agent=undo.TOUS):
        appels.append(1)
        if len(appels) == 1:
            return {"id": acte + 1000, "type": "lien", "cible_table": "bulle_locuteur"}
        return vraie(conn, agent)
    monkeypatch.setattr(undo, "derniere_action_annulable", faussee)
    res = client.post("/api/undo", headers=PROPRIO)
    assert res.status_code == 409, res.text
    assert len(appels) >= 2
    assert res.json()["detail"]["passable"] == {"evenement_id": acte}


def test_undo_presence(client, planche, db_path):
    boite = _creer_region(client, planche["id"], type="personnage")
    p = client.post("/api/personnages", json={"nom": "Haddock"}).json()
    assert client.put(f"/api/regions/{boite['id']}/personnage",
                      json={"personnage_id": p["id"]}).status_code == 200
    res = client.post("/api/undo").json()
    assert res["acte"] == "lien" and res["cible_table"] == "personnage_presence"
    assert _un(db_path, "SELECT 1 FROM personnage_presence WHERE region_id = ?",
               (boite["id"],)) is None


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
    c'est la seule façon d'éprouver un délai sans attendre qu'il s'écoule.

    Les albums reculent AVEC lui (AUTH-14) : vieillir le journal seul fabrique un monde
    impossible, où l'on a agi sur une planche avant que son album soit importé — et
    l'annulation lit justement cela comme un identifiant repris (`undo._album_ne_apres`)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE evenement SET date = datetime(date, ?)", (f"-{minutes} minutes",))
        conn.execute("UPDATE albums SET date_import = datetime(date_import, ?)",
                     (f"-{minutes} minutes",))
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
    # `ecrivable` est obligatoire depuis AUTH-14 ; ce test éprouve le délai, pas l'accès,
    # et le second appel doit aboutir : on le dit d'un mot plutôt que de monter une portée.
    tout_ecrivable = lambda lieux: True  # noqa: E731
    try:
        assert undo.annuler(conn, evenement_id=eid, agent="decor",
                            ecrivable=tout_ecrivable) is None
        assert undo.annuler(conn, evenement_id=eid, agent=undo.TOUS,
                            ecrivable=tout_ecrivable) is not None
    finally:
        conn.rollback()
        conn.close()


def test_le_mono_poste_n_a_pas_de_delai(client, planche, db_path):
    """Sans proxy, un seul agent (anonyme) et aucune nature à lire : rien ne change."""
    ancien = _creer_region(client, planche["id"])
    _vieillir(db_path, 60)
    assert client.post("/api/undo").json()["region_id"] == ancien["id"]


# --------------------------------------------------------------------------- #
# CONC-4 — annuler la création d'une région n'emporte pas les liens qu'un autre lui a donnés
# --------------------------------------------------------------------------- #
# Trouvé par la relecture croisée d'ANN-8 le 2026-10-21 (`test_h5_…`, dans sa copie) :
# `_garder_creation` ne regardait que les colonnes, l'annotation et les enfants ; supprimer
# la région emportait le locuteur, le personnage montré et la situation par CASCADE, sans
# instantané pour les rendre. Les gestes de l'auteur de la création sont annulés AVANT elle
# (ou ne s'annulent pas : la situation) ; ce qui reste et vient d'un autre se garde.
def _situation(client, nom):
    d = client.post("/api/attributs/dimensions", headers=ADMIN,
                    json={"cible": "case", "nom": nom}).json()["id"]
    return client.post(f"/api/attributs/dimensions/{d}/valeurs", headers=ADMIN,
                       json={"valeur": "intérieur"}).json()["id"]


def _creation_refusee(client, rid, champ, login, db_path):
    n = _ev_count(db_path)
    res = client.post("/api/undo", headers=PROPRIO)
    assert res.status_code == 409, res.text
    conflit = res.json()["detail"]["conflit"]
    assert conflit["champ"] == champ
    assert (conflit["auteur"] or {}).get("login") == login
    assert rid in _regions(db_path), "la région de l'autre a été supprimée"
    assert _ev_count(db_path) == n
    return res.json()["detail"]


def test_annuler_la_creation_d_une_bulle_n_emporte_pas_le_locuteur_d_un_autre(
        client, planche, db_path, derriere_proxy):
    rid = _creer_region(client, planche["id"], headers=PROPRIO, type="bulle")["id"]
    (zed,) = _personnages(client, "Zed QA")
    _poser(client, rid, "locuteur", zed, STAGIAIRE)
    detail = _creation_refusee(client, rid, "locuteur", "stagiaire", db_path)
    assert detail["conflit"]["valeur_actuelle"] == zed
    assert "passable" in detail                     # « Passer ce geste », comme tout refus
    assert _lien(db_path, "bulle_locuteur", rid) == zed


def test_annuler_la_creation_d_une_boite_n_emporte_pas_le_personnage_montre_d_un_autre(
        client, planche, db_path, derriere_proxy):
    rid = _creer_region(client, planche["id"], headers=PROPRIO, type="personnage")["id"]
    (zed,) = _personnages(client, "Zed QA")
    _poser(client, rid, "personnage", zed, STAGIAIRE)
    _creation_refusee(client, rid, "presence", "stagiaire", db_path)
    assert _lien(db_path, "personnage_presence", rid) == zed


def test_annuler_la_creation_d_une_case_n_emporte_pas_la_situation_d_un_autre(
        client, planche, db_path, derriere_proxy):
    rid = _creer_region(client, planche["id"], headers=PROPRIO, type="case")["id"]
    v = _situation(client, "lieu")
    assert client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": v},
                      headers=STAGIAIRE).status_code == 200
    _creation_refusee(client, rid, "situation", "stagiaire", db_path)
    assert _un(db_path, "SELECT 1 x FROM region_attribut WHERE region_id = ?", (rid,))


def test_annuler_la_creation_d_une_case_qualifiee_par_son_auteur_passe(
        client, planche, db_path, derriere_proxy):
    """La situation ne s'annule pas (hors Ctrl+Z) : posée par l'auteur de la case lui-même,
    elle ne doit pas rendre sa création inannulable. Le Ctrl+Z la défait avec la case,
    comme avant."""
    rid = _creer_region(client, planche["id"], headers=PROPRIO, type="case")["id"]
    v = _situation(client, "lieu")
    assert client.put(f"/api/regions/{rid}/attributs", json={"valeur_id": v},
                      headers=PROPRIO).status_code == 200
    res = client.post("/api/undo", headers=PROPRIO)
    assert res.status_code == 200, res.text
    assert rid not in _regions(db_path)


def test_un_lien_pose_puis_retire_par_un_autre_ne_bloque_pas(
        client, planche, db_path, derriere_proxy):
    """Seul compte ce qui RESTE sur la région : rien ne se perd."""
    rid = _creer_region(client, planche["id"], headers=PROPRIO, type="bulle")["id"]
    (zed,) = _personnages(client, "Zed QA")
    _poser(client, rid, "locuteur", zed, STAGIAIRE)
    _retirer(client, rid, "locuteur", STAGIAIRE)
    assert client.post("/api/undo", headers=PROPRIO).status_code == 200
    assert rid not in _regions(db_path)


def test_un_lien_sans_trace_au_journal_bloque_aussi(client, planche, db_path, derriere_proxy):
    """Le journal NOMME, il ne décide pas (la règle de `conflit`) : un locuteur posé sans
    acte — outil, base retouchée — est refusé, « modifié ailleurs »."""
    rid = _creer_region(client, planche["id"], headers=PROPRIO, type="bulle")["id"]
    (zed,) = _personnages(client, "Zed QA")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?)",
                     (rid, zed))
        conn.commit()
    finally:
        conn.close()
    _creation_refusee(client, rid, "locuteur", None, db_path)
