"""Le type de région `detail` (ANN-7, tranche 2, commit 9 ; G17).

Un DÉTAIL d'image se trace dans une case depuis la page Annotation : il porte un NOM
(`regions.nom`, v37), jamais de texte, ne contient rien et ne change pas de type. Qu'il ne
sorte d'aucun artefact se joue dans `tests/test_detail_sorties.py` ; ici, ce que les routes
d'écriture tiennent, ce que Ctrl+Z rend, et la re-segmentation qui le garde.
"""
import sqlite3

import pipeline.segmentation as seg


def _case(client, planche):
    return client.post(f"/api/planches/{planche['id']}/regions",
                       json={"type": "case", "x": 0, "y": 0, "w": 300, "h": 300}).json()["id"]


def _detail(client, planche, case_id, **plus):
    return client.post(f"/api/planches/{planche['id']}/regions",
                       json={"type": "detail", "x": 20, "y": 20, "w": 40, "h": 40,
                             "parent_id": case_id, **plus})


def test_un_detail_se_trace_dans_une_case_et_porte_un_nom(client, planche):
    case = _case(client, planche)
    r = _detail(client, planche, case, nom="  le téléphone  ")
    assert r.status_code == 201, r.text
    assert r.json()["type"] == "detail" and r.json()["nom"] == "le téléphone"
    # Sans nom aussi ; un nom vide n'est pas un nom.
    vide = _detail(client, planche, case, nom="   ").json()
    assert vide["nom"] is None
    # Lu avec les régions de la planche, comme les autres.
    lu = {x["id"]: x for x in client.get(f"/api/planches/{planche['id']}/regions").json()}
    assert lu[r.json()["id"]]["nom"] == "le téléphone"
    # Hors de toute case, il se range nulle part (la planche sans case).
    assert client.post(f"/api/planches/{planche['id']}/regions",
                       json={"type": "detail", "x": 1, "y": 1, "w": 5, "h": 5}).status_code == 201


def test_les_regles_d_un_detail_sont_dites_par_un_422(client, planche):
    case = _case(client, planche)
    bulle = client.post(f"/api/planches/{planche['id']}/regions",
                        json={"type": "bulle", "x": 5, "y": 5, "w": 50, "h": 50,
                              "parent_id": case}).json()["id"]
    # Un nom ne se pose que sur un détail.
    r = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5, "nom": "x"})
    assert r.status_code == 422 and "Seul un détail" in r.json()["detail"]
    r = client.put(f"/api/regions/{bulle}", json={"nom": "x"})
    assert r.status_code == 422 and "Seul un détail" in r.json()["detail"]
    # Un détail ne porte pas de texte.
    r = _detail(client, planche, case, ocr_texte="BANG")
    assert r.status_code == 422 and "pas de texte" in r.json()["detail"]
    d = _detail(client, planche, case).json()["id"]
    r = client.put(f"/api/regions/{d}", json={"ocr_texte": "BANG"})
    assert r.status_code == 422 and "pas de texte" in r.json()["detail"]
    # Il se range dans une case, pas dans une bulle.
    r = _detail(client, planche, bulle)
    assert r.status_code == 422 and "dans une case" in r.json()["detail"]
    r = client.put(f"/api/regions/{d}", json={"parent_id": bulle})
    assert r.status_code == 422 and "dans une case" in r.json()["detail"]
    # Rien ne se range sous un détail.
    r = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "bulle", "x": 21, "y": 21, "w": 5, "h": 5, "parent_id": d})
    assert r.status_code == 422 and "sous un détail" in r.json()["detail"]
    r = client.put(f"/api/regions/{bulle}", json={"parent_id": d})
    assert r.status_code == 422 and "sous un détail" in r.json()["detail"]
    # Un détail reste un détail, et rien ne le devient.
    r = client.put(f"/api/regions/{d}", json={"type": "bulle"})
    assert r.status_code == 422 and "reste un détail" in r.json()["detail"]
    r = client.put(f"/api/regions/{bulle}", json={"type": "detail"})
    assert r.status_code == 422 and "reste un détail" in r.json()["detail"]
    # Le même type, renvoyé, n'est pas un changement.
    assert client.put(f"/api/regions/{d}", json={"type": "detail"}).status_code == 200
    # Rien n'a été écrit par les refus.
    lu = {x["id"]: x for x in client.get(f"/api/planches/{planche['id']}/regions").json()}
    assert lu[d]["type"] == "detail" and lu[d]["ocr_texte"] is None and lu[d]["parent_id"] == case
    assert lu[bulle]["type"] == "bulle" and lu[bulle]["nom"] is None


def test_le_nom_se_garde_par_la_valeur_vue(client, planche):
    """CONC-3 : le nom se change avec la valeur que l'écran voyait ; périmée, un 409 nommé."""
    case = _case(client, planche)
    d = _detail(client, planche, case, nom="la lampe").json()["id"]
    assert client.put(f"/api/regions/{d}", json={"nom": "la lampe de poche",
                                                 "vu": {"nom": "la lampe"}}).status_code == 200
    r = client.put(f"/api/regions/{d}", json={"nom": "le phare", "vu": {"nom": "la lampe"}})
    assert r.status_code == 409, r.text
    c = r.json()["detail"]["conflit"]
    assert c["champ"] == "nom" and c["valeur_actuelle"] == "la lampe de poche"
    # L'identique passe ; vider le nom l'efface.
    assert client.put(f"/api/regions/{d}", json={"nom": "la lampe de poche",
                                                 "vu": {"nom": "la lampe"}}).status_code == 200
    r = client.put(f"/api/regions/{d}", json={"nom": "", "vu": {"nom": "la lampe de poche"}})
    assert r.status_code == 200 and r.json()["nom"] is None


def test_ctrl_z_defait_un_nom_puis_rend_un_detail_supprime(client, planche):
    case = _case(client, planche)
    d = _detail(client, planche, case, nom="la lampe").json()["id"]
    assert client.put(f"/api/regions/{d}", json={"nom": "le phare"}).status_code == 200
    assert client.post("/api/undo").status_code == 200
    lu = {x["id"]: x for x in client.get(f"/api/planches/{planche['id']}/regions").json()}
    assert lu[d]["nom"] == "la lampe"
    assert client.delete(f"/api/regions/{d}").status_code == 204
    assert client.post("/api/undo").status_code == 200
    lu = {x["id"]: x for x in client.get(f"/api/planches/{planche['id']}/regions").json()}
    assert lu[d]["type"] == "detail" and lu[d]["nom"] == "la lampe" and lu[d]["parent_id"] == case


def test_la_resegmentation_garde_le_detail(client, planche, monkeypatch):
    """Kumiko ne remplace que ses propres cases : un détail tracé à la main reste, avec son
    nom, et se range dans la nouvelle case qui contient son centre."""
    monkeypatch.setattr("main.kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[0, 0, 200, 250]]})
    client.post(f"/api/planches/{planche['id']}/segmenter")
    case = next(x for x in client.get(f"/api/planches/{planche['id']}/regions").json()
                if x["type"] == "case")
    d = _detail(client, planche, case["id"], nom="la lampe").json()["id"]
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[0, 0, 210, 260]]})
    assert client.post(f"/api/planches/{planche['id']}/segmenter").status_code == 200
    lu = {x["id"]: x for x in client.get(f"/api/planches/{planche['id']}/regions").json()}
    neuve = next(x for x in lu.values() if x["type"] == "case")
    assert neuve["id"] != case["id"] and case["id"] not in lu
    assert lu[d]["type"] == "detail" and lu[d]["nom"] == "la lampe"
    assert lu[d]["parent_id"] == neuve["id"]


def test_un_detail_ne_se_cherche_pas(client, planche):
    """La recherche — et son export — ne portent pas un détail (G17) : sa note n'y est pas."""
    case = _case(client, planche)
    d = _detail(client, planche, case).json()["id"]
    bulle = client.post(f"/api/planches/{planche['id']}/regions",
                        json={"type": "bulle", "x": 5, "y": 5, "w": 9, "h": 9,
                              "parent_id": case}).json()["id"]
    for rid in (d, bulle):
        assert client.put(f"/api/regions/{rid}/annotation",
                          json={"note": "ZZCHERCHE9"}).status_code == 200
    trouves = client.get("/api/recherche", params={"q": "ZZCHERCHE9"}).json()["results"]
    assert [r["region_id"] for r in trouves] == [bulle]


# --------------------------------------------------------------------------- #
# Relecture croisée du commit 9 (ANN-7, tranche 2, commit 10)
# --------------------------------------------------------------------------- #
def _lu(client, planche):
    return {x["id"]: x for x in client.get(f"/api/planches/{planche['id']}/regions").json()}


def _sql(db_path, sql, *params):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def test_une_case_qui_porte_un_detail_ne_change_pas_de_type(client, planche):
    """Constat 3 — un détail se range dans une case ou nulle part : la case qui en porte un
    devenait une bulle, et le détail restait sous elle."""
    case = _case(client, planche)
    d = _detail(client, planche, case).json()["id"]
    for autre in ("bulle", "texte", "personnage"):
        r = client.put(f"/api/regions/{case}", json={"type": autre})
        assert r.status_code == 422, r.text
        assert "porte un détail" in r.json()["detail"]
    assert _lu(client, planche)[case]["type"] == "case"
    # Le même type renvoyé passe ; une case sans détail change de type comme avant.
    assert client.put(f"/api/regions/{case}", json={"type": "case"}).status_code == 200
    vide = _case(client, planche)
    assert client.put(f"/api/regions/{vide}", json={"type": "bulle"}).status_code == 200
    # Une case qui ne porte qu'une bulle aussi : la règle porte sur le détail.
    autre = _case(client, planche)
    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "bulle", "x": 5, "y": 5, "w": 9, "h": 9, "parent_id": autre})
    assert client.put(f"/api/regions/{autre}", json={"type": "personnage"}).status_code == 200
    # Le détail sorti de la case, elle change de type.
    assert client.put(f"/api/regions/{d}", json={"parent_id": None}).status_code == 200
    assert client.put(f"/api/regions/{case}", json={"type": "bulle"}).status_code == 200


def _ctrl_z_refuse(client):
    r = client.post("/api/undo")
    assert r.status_code == 409, r.text
    assert "ne peut plus être rétabli" in r.json()["detail"]["message"], r.json()


def test_ctrl_z_ne_rend_pas_un_type_qui_laisserait_un_detail_sous_une_bulle(client, planche,
                                                                          db_path):
    """Constat 3 — une bulle devenue case reçoit un détail ; défaire le changement de type la
    rendrait bulle, avec le détail sous elle. Le détail est posé sans acte (une région
    recopiée) : l'acte en tête de la pile reste le changement de type."""
    b = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "bulle", "x": 0, "y": 0, "w": 300, "h": 300}).json()["id"]
    assert client.put(f"/api/regions/{b}", json={"type": "case"}).status_code == 200
    _sql(db_path, "INSERT INTO regions (planche_id, parent_id, type, x, y, w, h, ordre, source) "
                  "VALUES (?, ?, 'detail', 20, 20, 9, 9, 1, 'manuel')", planche["id"], b)
    _ctrl_z_refuse(client)
    assert _lu(client, planche)[b]["type"] == "case"


def test_ctrl_z_ne_rend_pas_un_detail_sous_une_case_devenue_bulle(client, planche, db_path):
    """Constat 3 — un détail supprimé, sa case devenue bulle depuis (ici par la base, comme
    par un autre écran) : Ctrl+Z ne le repose pas sous la bulle."""
    case = _case(client, planche)
    d = _detail(client, planche, case).json()["id"]
    assert client.delete(f"/api/regions/{d}").status_code == 204
    _sql(db_path, "UPDATE regions SET type = 'bulle' WHERE id = ?", case)
    _ctrl_z_refuse(client)
    assert d not in _lu(client, planche)


def test_ctrl_z_ne_ramene_pas_un_detail_dans_une_case_devenue_bulle(client, planche,
                                                                    db_path):
    """Constat 3 — un détail déplacé d'une case à une autre, la première devenue bulle
    depuis : Ctrl+Z ne l'y ramène pas (`undo._parent_valide`)."""
    a = _case(client, planche)
    b = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "case", "x": 300, "y": 0, "w": 100, "h": 100}).json()["id"]
    d = _detail(client, planche, a).json()["id"]
    assert client.put(f"/api/regions/{d}", json={"parent_id": b}).status_code == 200
    _sql(db_path, "UPDATE regions SET type = 'bulle' WHERE id = ?", a)
    _ctrl_z_refuse(client)
    assert _lu(client, planche)[d]["parent_id"] == b


def test_ctrl_z_ne_range_rien_sous_un_detail(client, planche, db_path):
    """Constat 3 — rien ne se range sous un détail, pas plus par Ctrl+Z : une bulle déplacée
    d'une région devenue détail depuis (par la base : aucune route ne le permet) n'y revient
    pas (`undo._parent_valide`)."""
    a = _case(client, planche)
    b = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "case", "x": 300, "y": 0, "w": 100, "h": 100}).json()["id"]
    bulle = client.post(f"/api/planches/{planche['id']}/regions",
                        json={"type": "bulle", "x": 5, "y": 5, "w": 9, "h": 9,
                              "parent_id": a}).json()["id"]
    assert client.put(f"/api/regions/{bulle}", json={"parent_id": b}).status_code == 200
    _sql(db_path, "UPDATE regions SET type = 'detail' WHERE id = ?", a)
    _ctrl_z_refuse(client)
    assert _lu(client, planche)[bulle]["parent_id"] == b


def test_l_ordre_stocke_suit_la_lecture_details_compris(client, planche):
    """Tranché par Hugo le 2026-10-30 (renverse le constat 5 du commit 10) : un détail se
    range à sa place de lecture parmi ses frères. L'export, lui, renumérote sans lui
    (`tests/test_detail_sorties.py`)."""
    case = _case(client, planche)
    pid = planche["id"]
    # Un détail en haut à gauche, AVANT la bulle en ordre de lecture.
    d = client.post(f"/api/planches/{pid}/regions",
                    json={"type": "detail", "x": 0, "y": 0, "w": 5, "h": 5,
                          "parent_id": case}).json()["id"]
    b1 = client.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 50, "y": 50, "w": 20, "h": 20,
                           "parent_id": case}).json()["id"]
    # Créée après le détail, la bulle a SON rang : elle ne partage pas le sien.
    lu = _lu(client, planche)
    assert (lu[d]["ordre"], lu[b1]["ordre"]) == (1, 2), (lu[d], lu[b1])
    b2 = client.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 2, "y": 200, "w": 20, "h": 20,
                           "parent_id": case}).json()["id"]
    d2 = client.post(f"/api/planches/{pid}/regions",
                     json={"type": "detail", "x": 100, "y": 200, "w": 5, "h": 5,
                           "parent_id": case}).json()["id"]
    assert client.post(f"/api/planches/{pid}/reordonner").status_code == 200
    lu = _lu(client, planche)
    assert [lu[i]["ordre"] for i in (d, b1, b2, d2)] == [1, 2, 3, 4]
    # « Descendre » passe une bulle après un détail, et « Monter » un détail avant une bulle.
    r = client.post(f"/api/regions/{b2}/deplacer", json={"sens": "bas"}).json()
    assert (r["moved"], r["ordre"]) == (True, 4), r
    r = client.post(f"/api/regions/{d}/deplacer", json={"sens": "bas"}).json()
    assert (r["moved"], r["ordre"]) == (True, 2), r
    lu = _lu(client, planche)
    assert [lu[i]["ordre"] for i in (b1, d, d2, b2)] == [1, 2, 3, 4]


def test_ctrl_z_defait_la_note_d_un_detail(client, planche):
    """Commit 10 — l'acte sur la note d'un détail porte le type de sa région dans sa charge
    (`journal.CLE_REGION_RETENUE`) : Ctrl+Z la lit comme avant, et la marque ne touche que
    les actes sur un détail."""
    import json
    import journal
    case = _case(client, planche)
    d = _detail(client, planche, case).json()["id"]
    for note in ("un", "deux"):
        for rid in (d, case):
            assert client.put(f"/api/regions/{rid}/annotation",
                              json={"note": note}).status_code == 200
    assert client.post("/api/undo").status_code == 200
    assert client.post("/api/undo").status_code == 200
    for rid in (d, case):
        assert client.get(f"/api/regions/{rid}/annotation").json()["note"] == "un"
    import database
    with database.get_connection() as conn:
        charges = {cid: (json.loads(av) if av else None, json.loads(ap))
                   for cid, av, ap in conn.execute(
                       "SELECT cible_id, avant, apres FROM evenement WHERE cible_table = "
                       "'annotations' AND type = 'modification'")}
    cle = journal.CLE_REGION_RETENUE
    assert charges[d][0][cle] == charges[d][1][cle] == "detail"
    assert cle not in charges[case][0] and cle not in charges[case][1]
