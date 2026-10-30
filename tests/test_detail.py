"""Le type de région `detail` (ANN-7, tranche 2, commit 9 ; G17).

Un DÉTAIL d'image se trace dans une case depuis la page Annotation : il porte un NOM
(`regions.nom`, v37), jamais de texte, ne contient rien et ne change pas de type. Qu'il ne
sorte d'aucun artefact se joue dans `tests/test_detail_sorties.py` ; ici, ce que les routes
d'écriture tiennent, ce que Ctrl+Z rend, et la re-segmentation qui le garde.
"""
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
