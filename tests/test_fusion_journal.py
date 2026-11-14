"""Une FUSION d'entrées écrit au journal chaque relevé qu'elle déplace (ANN-7, le mode libre ;
la case du cadrage du 2026-11-06 : « aucun acte par relevé »).

Un acte par relevé, sous sa cible ordinaire — la RÉGION (`releve`), la PLANCHE
(`releve_planche`) —, d'un type à lui (`grilles.ACTE_FUSION`) qui nomme l'acte de grille qu'il
prolonge. Ni Ctrl+Z ne l'offre (l'entrée de départ n'existe plus), ni « qui perd quoi », ni le
verdict de départ d'un compte ne le comptent : la fusion range un vocabulaire, et le relevé
reste à qui l'a posé. Par la route du formulaire comme par le réimport d'une grille ouverte.
"""
import json
import sqlite3

import comptes
from conftest import make_png
import grilles
import undo
from grilles_decor import LEA, OLGA, STAG, ok
from test_grille_de_travail import _travail
from test_grille_tableur import HURLEMENT, SANS_CRI, _importer_avec, ouverte  # noqa: F401
from test_releves import bulle, decor, poser  # noqa: F401


def _q(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, p)]
    finally:
        c.close()


def _fusions(db_path):
    return _q(db_path, "SELECT * FROM evenement WHERE type = ? ORDER BY id",
              (grilles.ACTE_FUSION,))


def _traces(db_path):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return comptes.traces(c)[0]
    finally:
        c.close()


def test_une_fusion_ecrit_un_acte_par_releve_deplace(client, decor, db_path):
    t = _travail(client, decor, db_path)
    g, b, pl = t["grille_id"], bulle(t), t["planche"]
    # Une seconde planche : une entrée de la planche ne se pose qu'une fois sur chacune.
    pl2 = ok(client.post(f"/api/albums/{t['album']}/import", headers=LEA,
                         files={"file": ("q.png", make_png(), "image/png")}), 201)["id"]
    r_bulle = poser(client, t, region_id=b, nouvelle_entree={"libelle": "ironie"})
    r_case = poser(client, t, region_id=t["zones"]["case"], entree_cle="ironie")
    poser(client, t, region_id=t["zones"]["cartouche"], nouvelle_entree={"libelle": "humour"})
    # La grille de travail porte sur les zones : deux entrées de la planche, au formulaire.
    for nom in ("rythme", "tempo"):
        ok(client.post(f"/api/grilles/{g}/entrees", headers=LEA,
                       json={"libelle": nom, "forme": "simple", "cible": "planche"}), 201)
    r_surface = poser(client, t, planche_id=pl, entree_cle="rythme")
    poser(client, t, planche_id=pl2, entree_cle="tempo")
    traces_avant = _traces(db_path)
    autrui_avant = ok(client.get(f"/api/albums/{t['album']}/travail-des-autres",
                                 headers=OLGA))

    for de, dans in (("ironie", "humour"), ("rythme", "tempo")):
        r = client.post(f"/api/grilles/{g}/entrees/{de}/fusion", headers=LEA,
                        json={"dans": dans})
        assert r.status_code == 200, r.text

    # Les actes de grille des deux fusions, tels qu'ils étaient : ils nomment leurs relevés.
    actes_grille = _q(db_path, "SELECT * FROM evenement WHERE cible_table = 'grille' "
                               "AND type = 'suppression' AND agent = 'lea' ORDER BY id")
    assert [sorted(json.loads(x["apres"])["releve_ids"]) for x in actes_grille] == [
        sorted([r_bulle["id"], r_case["id"]]), [r_surface["id"]]]

    # Un acte par relevé déplacé, sous sa cible, après l'acte de grille qu'il nomme.
    actes = _fusions(db_path)
    assert [(e["cible_table"], e["cible_id"], e["agent"]) for e in actes] == [
        ("releve", b, "lea"), ("releve", t["zones"]["case"], "lea"),
        ("releve_planche", pl, "lea")]
    attendus = ((r_bulle, actes_grille[0], "ironie", "humour"),
                (r_case, actes_grille[0], "ironie", "humour"),
                (r_surface, actes_grille[1], "rythme", "tempo"))
    for e, (rel, acte_grille, de, dans) in zip(actes, attendus):
        av, ap = json.loads(e["avant"]), json.loads(e["apres"])
        assert e["id"] > acte_grille["id"]
        assert av["releve_id"] == ap["releve_id"] == rel["id"]
        assert (av["entree_cle"], ap["entree_cle"]) == (de, dans)
        assert av["variante_cle"] == ap["variante_cle"] is None
        assert (av["region_id"], av["planche_id"]) == (ap["region_id"], ap["planche_id"])
        assert av["grille_id"] == ap["grille_id"] == g
        assert ap["fusion"] == {"acte": acte_grille["id"], "grille_id": g,
                                "version": t["numero"], "de": de, "dans": dans}

    # Ctrl+Z ne les offre pas : ni à qui a fusionné, ni à qui a posé.
    ids = {e["id"] for e in actes}
    for qui in (LEA, STAG):
        p = client.get("/api/undo/prochain", headers=qui).json()
        assert p is None or p["evenement_id"] not in ids, p
    assert ok(client.get("/api/undo/prochain", headers=STAG))["description"] == \
        "pose d'un relevé"

    # « Qui perd quoi » : la fusion n'est pas un travail sur l'album — rien de plus pour
    # personne, les poses de la stagiaire comptées comme avant.
    autrui = ok(client.get(f"/api/albums/{t['album']}/travail-des-autres", headers=OLGA))
    assert autrui["travail_des_autres"] == autrui_avant["travail_des_autres"], autrui
    gestes = {x["agent"]: x["gestes"] for x in autrui["travail_des_autres"]}
    assert gestes["stag"].get("releve") == 3 and gestes["stag"].get("releve_planche") == 2
    assert not {"releve", "releve_planche"} & set(gestes.get("lea", {})), gestes

    # Le verdict de départ d'un compte ne les compte pas.
    assert _traces(db_path).get("lea") == traces_avant.get("lea")

    # Le relevé reste à qui l'a posé (la garde de Ctrl+Z d'une création de région).
    c = sqlite3.connect(db_path)
    try:
        (d_un_autre,) = c.execute(f"SELECT {undo._SQL_RELEVE_D_UN_AUTRE} FROM releve r "
                                  "WHERE r.id = ?", ("stag", "stag", r_bulle["id"])).fetchone()
    finally:
        c.close()
    assert not d_un_autre


def test_le_reimport_qui_fusionne_ecrit_aussi_un_acte_par_releve(client, ouverte, db_path):
    d = ouverte
    res = _importer_avec(client, d, SANS_CRI + HURLEMENT, {"cri": "fusionner:hurlement"})
    assert res["ecrit"]
    (acte_import,) = _q(db_path, "SELECT * FROM evenement WHERE cible_table = 'grille' "
                                 "ORDER BY id DESC LIMIT 1")
    (e,) = _fusions(db_path)
    assert (e["cible_table"], e["cible_id"], e["agent"]) == (
        "releve", d["zones"]["bulle"], "lea")
    av, ap = json.loads(e["avant"]), json.loads(e["apres"])
    assert av["releve_id"] == ap["releve_id"] == d["releve"]
    assert (av["entree_cle"], ap["entree_cle"]) == ("cri", "hurlement")
    assert ap["fusion"] == {"acte": acte_import["id"], "grille_id": d["grille_id"],
                            "version": 1, "de": "cri", "dans": "hurlement"}
    assert ok(client.get("/api/undo/prochain", headers=STAG))["evenement_id"] != e["id"]
