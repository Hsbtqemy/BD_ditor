"""CONC-4 — l'empreinte d'une planche ouverte (`GET /api/planches/{id}/empreinte`).

L'Atelier la compare de temps en temps pour proposer « Actualiser » quand la planche a changé
AILLEURS (Hugo, 2026-10-21 : un signal, pas de temps réel). Une empreinte PAR RÉGION, pour
que l'écran sache distinguer ce qu'il a touché lui-même (`static/lib/signal-planche.js`).
Ces tests tiennent ce que l'empreinte voit, ce qu'elle ne voit pas exprès, et sa borne.
"""
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import autorisation  # noqa: E402
import main  # noqa: E402
from conftest import ADMIN  # noqa: E402


def _empreinte(client, planche_id, headers=None):
    rep = client.get(f"/api/planches/{planche_id}/empreinte", headers=headers)
    assert rep.status_code == 200, rep.text
    return rep.json()["regions"]


def _region(client, planche_id, **champs):
    corps = {"type": "bulle", "x": 0, "y": 0, "w": 10, "h": 10, **champs}
    return client.post(f"/api/planches/{planche_id}/regions", json=corps).json()["id"]


def _seule_change(avant, apres, rid):
    """Seule la région `rid` a changé d'empreinte — les autres sont intactes."""
    assert set(avant) == set(apres)
    changees = {k for k in avant if avant[k] != apres[k]}
    assert changees == {str(rid)}, changees


def test_l_empreinte_couvre_chaque_region_et_ne_bouge_pas_seule(client, planche):
    a = _region(client, planche["id"])
    b = _region(client, planche["id"], type="case")
    e1 = _empreinte(client, planche["id"])
    assert set(e1) == {str(a), str(b)}
    assert all(len(v) == 12 for v in e1.values())
    assert _empreinte(client, planche["id"]) == e1


def test_chaque_geste_de_l_atelier_change_l_empreinte_de_sa_seule_region(client, planche):
    pid = planche["id"]
    case = _region(client, pid, type="case", w=200, h=200)
    bulle = _region(client, pid)
    boite = _region(client, pid, type="personnage")
    temoin = _region(client, pid, type="cartouche")
    zed = client.post("/api/personnages", json={"nom": "Zed"}).json()["id"]
    gestes = [
        (bulle, lambda: client.put(f"/api/regions/{bulle}", json={"ocr_texte": "BONJOUR"})),
        (bulle, lambda: client.put(f"/api/regions/{bulle}", json={"x": 5})),
        (bulle, lambda: client.put(f"/api/regions/{bulle}", json={"parent_id": case})),
        (bulle, lambda: client.put(f"/api/regions/{bulle}/annotation", json={"note": "n"})),
        (bulle, lambda: client.put(f"/api/regions/{bulle}/locuteur", json={"personnage_id": zed})),
        (boite, lambda: client.put(f"/api/regions/{boite}/personnage",
                                   json={"personnage_id": zed})),
        (temoin, lambda: client.put(f"/api/regions/{temoin}", json={"type": "texte"})),
    ]
    for rid, geste in gestes:
        avant = _empreinte(client, pid)
        assert geste().status_code == 200
        _seule_change(avant, _empreinte(client, pid), rid)


def test_monter_une_region_change_son_rang_et_celui_de_sa_soeur(client, planche):
    """« Monter / descendre » échange deux sœurs : l'arbre de structure d'un autre écran
    n'est plus le bon, et l'empreinte des DEUX le dit."""
    pid = planche["id"]
    case = _region(client, pid, type="case", w=300, h=300)
    a = _region(client, pid, parent_id=case)
    b = _region(client, pid, parent_id=case, x=50)
    avant = _empreinte(client, pid)
    assert client.post(f"/api/regions/{b}/deplacer", json={"sens": "haut"}).status_code == 200
    apres = _empreinte(client, pid)
    assert {k for k in avant if avant[k] != apres[k]} == {str(a), str(b)}


def test_une_region_creee_ou_supprimee_ailleurs_apparait_ou_disparait(client, planche):
    pid = planche["id"]
    a = _region(client, pid)
    avant = _empreinte(client, pid)
    b = _region(client, pid)
    apres = _empreinte(client, pid)
    assert set(apres) - set(avant) == {str(b)}
    # Créer ne change pas l'empreinte des voisines : la neuve prend le rang suivant.
    assert apres[str(a)] == avant[str(a)]
    assert client.delete(f"/api/regions/{b}").status_code == 204
    assert _empreinte(client, pid) == avant


def test_hors_portee_la_planche_est_introuvable(client, planche, monkeypatch):
    monkeypatch.setattr(main, "AUTH_PROXY", True)
    monkeypatch.setattr(autorisation, "AUTH_PROXY", True)
    rep = client.get(f"/api/planches/{planche['id']}/empreinte",
                     headers={"Remote-User": "inconnu"})
    assert rep.status_code == 404, rep.text
    assert client.get("/api/planches/999999/empreinte", headers=ADMIN).status_code == 404


def test_le_vocabulaire_d_hier_ne_change_l_empreinte_de_personne(client, planche, db_path):
    """ANN-7, le basculement : les tags et la situation d'une case ne se montrent plus nulle
    part, et l'empreinte ne les condense plus — un tag ou une valeur posés en base (une base
    d'avant la migration v39 les porte encore) ne font proposer « Actualiser » à personne,
    administrateur compris. (AUTH-11 les filtrait par la portée des termes : la question
    n'a plus d'objet.) Mutant tué : les tags ou la situation remis dans `empreinte.empreintes`."""
    pid = planche["id"]
    rid = _region(client, pid, type="case")
    avant = _empreinte(client, pid, ADMIN)
    conn = sqlite3.connect(db_path)
    try:
        tag = conn.execute("INSERT INTO tags (label) VALUES ('hier')").lastrowid
        ann = conn.execute("INSERT INTO annotations (region_id, note) VALUES (?, '')",
                           (rid,)).lastrowid
        conn.execute("INSERT INTO annotation_tags (annotation_id, tag_id) VALUES (?, ?)",
                     (ann, tag))
        dim = conn.execute("INSERT INTO attribut_dimension (cible, nom) "
                           "VALUES ('case', 'lieu')").lastrowid
        val = conn.execute("INSERT INTO attribut_valeur (dimension_id, valeur) "
                           "VALUES (?, 'forêt')", (dim,)).lastrowid
        conn.execute("INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)",
                     (rid, val))
        conn.commit()
    finally:
        conn.close()
    assert _empreinte(client, pid, ADMIN) == avant


# --------------------------------------------------------------------------- #
# ANN-7, tranche 2 (jalon 2, commit 6) — les relevés, les passes et les doutes
# --------------------------------------------------------------------------- #
# La page Annotation montre ce que l'Atelier ne montre pas. Leur empreinte est À PART
# (`releves`) : l'Atelier, qui ne lit que `regions`, ne voit pas « changé » une planche dont
# rien de ce qu'il montre n'a bougé.
def _tout(client, planche_id, headers):
    rep = client.get(f"/api/planches/{planche_id}/empreinte", headers=headers)
    assert rep.status_code == 200, rep.text
    return rep.json()


def _seule_cle(avant, apres, cle):
    changees = {k for k in set(avant) | set(apres) if avant.get(k) != apres.get(k)}
    assert changees == {cle}, changees


def test_un_releve_un_doute_une_passe_changent_leur_zone_et_jamais_les_regions(
        client, db_path, derriere_proxy):
    from grilles_decor import LEA, STAG, grille_active, monter
    d = monter(client, db_path)
    g = grille_active(client, d["p"])
    pl, bulle, case = d["planche"], d["zones"]["bulle"], d["zones"]["case"]
    e0 = _tout(client, pl, STAG)
    assert e0["releves"] == {}                       # rien de posé : aucune clé

    def pose(qui, **corps):
        r = client.post("/api/releves", headers=qui,
                        json={"grille_id": g["grille_id"], "version": 1, **corps})
        assert r.status_code == 201, r.text
        return r.json()

    cri = pose(STAG, region_id=bulle, entree_cle="cri", mots=[0])
    e1 = _tout(client, pl, STAG)
    assert set(e1["releves"]) == {str(bulle)} and e1["regions"] == e0["regions"]
    ton = pose(STAG, region_id=bulle, entree_cle="ton-de-voix", variante_cle="crie")
    gestes = [
        (str(bulle), lambda: client.put(f"/api/releves/{ton['id']}", headers=LEA,
                                        json={"variante_cle": "chuchote"})),
        (str(bulle), lambda: client.put(f"/api/releves/{cri['id']}", headers=LEA,
                                        json={"mots": [1]})),
        (str(bulle), lambda: client.post(f"/api/releves/{cri['id']}/doutes", headers=LEA,
                                         json={"texte": "Un cri ?"})),
        (str(case), lambda: client.post("/api/releves", headers=STAG, json={
            "grille_id": g["grille_id"], "version": 1, "region_id": case,
            "entree_cle": "regard-camera"})),
        ("planche", lambda: client.post("/api/releves", headers=STAG, json={
            "grille_id": g["grille_id"], "version": 1, "planche_id": pl,
            "entree_cle": "ambiance"})),
        (str(bulle), lambda: client.put(f"/api/regions/{bulle}/passes/{g['grille_id']}",
                                        headers=STAG, json={})),
        ("planche", lambda: client.put(f"/api/planches/{pl}/passes/{g['grille_id']}",
                                       headers=STAG, json={})),
    ]
    for cle, geste in gestes:
        avant = _tout(client, pl, STAG)
        assert geste().status_code in (200, 201), cle
        apres = _tout(client, pl, STAG)
        _seule_cle(avant["releves"], apres["releves"], cle)
        assert apres["regions"] == avant["regions"], cle
    # Le fil d'un doute qui s'allonge, sa levée, le retrait d'un relevé : la zone bouge.
    doute = next(r for r in client.get(f"/api/planches/{pl}/releves", headers=STAG)
                 .json()["releves"] if r["id"] == cri["id"])["doute"]
    for geste in (lambda: client.post(f"/api/doutes/{doute['id']}/messages", headers=STAG,
                                      json={"texte": "Oui."}),
                  lambda: client.post(f"/api/doutes/{doute['id']}/levee", headers=STAG,
                                      json={"issue": "garde"}),
                  lambda: client.delete(f"/api/releves/{ton['id']}", headers=STAG)):
        avant = _tout(client, pl, STAG)
        assert geste().status_code in (200, 201, 204)
        _seule_cle(avant["releves"], _tout(client, pl, STAG)["releves"], str(bulle))
    # Marquer une passe déjà marquée par un autre ne change rien : elle reste la sienne.
    avant = _tout(client, pl, STAG)
    assert client.put(f"/api/regions/{bulle}/passes/{g['grille_id']}", headers=LEA,
                      json={}).status_code == 200
    assert _tout(client, pl, STAG) == avant
    # La dernière chose d'une zone retirée, sa clé part.
    assert client.delete(f"/api/planches/{pl}/passes/{g['grille_id']}", headers=STAG,
                         params={"vu_marquee": "true"}).status_code == 204
    rel = [r for r in client.get(f"/api/planches/{pl}/releves", headers=STAG).json()["releves"]
           if r["planche_id"] == pl]
    for r in rel:
        assert client.delete(f"/api/releves/{r['id']}", headers=STAG).status_code == 204
    assert "planche" not in _tout(client, pl, STAG)["releves"]
