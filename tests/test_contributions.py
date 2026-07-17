"""Enrichissement descriptif N0 (v15) — contributions Zotero-like + vocabulaire de rôles
contrôlé-ouvert + champs d'édition sur l'album. Cf. docs/dictionnaire-metadonnees.md (N0)."""


def test_champs_edition_persistes(client):
    """Les 8 champs d'édition (v15) sont acceptés à la création et relus."""
    a = client.post("/api/albums", json={
        "titre": "Tintin au Tibet", "date_edition": "1960", "date_originale": "1958",
        "langue": "fr", "type_oeuvre": "BD", "lieu_edition": "Tournai",
        "edition_tirage": "1re éd.", "isbn": "978-2-203-00117-6",
        "format_physique": "30 cm, cartonné"}).json()
    assert a["date_edition"] == "1960" and a["langue"] == "fr"
    assert a["isbn"].startswith("978") and a["format_physique"].startswith("30")
    # relecture via la liste (list_albums renvoie a.*)
    lst = {x["id"]: x for x in client.get("/api/albums").json()}
    assert lst[a["id"]]["type_oeuvre"] == "BD" and lst[a["id"]]["lieu_edition"] == "Tournai"


def test_edition_via_put_dynamique(client, album):
    """Un champ d'édition se met à jour via le PUT dynamique (exclude_unset)."""
    client.put(f"/api/albums/{album['id']}", json={"langue": "en"})
    lst = {x["id"]: x for x in client.get("/api/albums").json()}
    assert lst[album["id"]]["langue"] == "en"
    assert lst[album["id"]]["titre"] == album["titre"]      # le reste intact


def test_vocabulaire_roles_seede(client):
    """Le vocabulaire de rôles est semé à la migration (contrôlé-ouvert)."""
    labels = {r["label"] for r in client.get("/api/contribution-roles").json()}
    assert {"scénariste", "dessinateur", "coloriste", "traducteur"} <= labels


def test_contribution_crud_et_vocab_ouvert(client, album):
    """Ajout/liste/suppression + rôle résolu (bucket) + création d'un rôle INÉDIT (ouvert)."""
    aid = album["id"]
    c1 = client.post(f"/api/albums/{aid}/contributions",
                     json={"nom": "Hergé", "role": "scénariste"}).json()
    assert c1["role"] == "scénariste" and c1["bucket"] == "creator" and c1["rang"] == 1
    c2 = client.post(f"/api/albums/{aid}/contributions",
                     json={"nom": "Jacobs", "role": "décors"}).json()   # rôle inédit
    assert c2["rang"] == 2 and c2["bucket"] == "contributor"            # défaut vocab ouvert
    assert "décors" in {r["label"] for r in client.get("/api/contribution-roles").json()}

    lst = client.get(f"/api/albums/{aid}/contributions").json()
    assert [c["nom"] for c in lst] == ["Hergé", "Jacobs"]              # ordre de rang

    r = client.delete(f"/api/contributions/{c2['id']}")
    assert r.status_code == 204
    assert [c["nom"] for c in client.get(f"/api/albums/{aid}/contributions").json()] == ["Hergé"]


def test_contribution_role_null_autorise(client, album):
    """Une contribution sans rôle est acceptée (role NULL)."""
    c = client.post(f"/api/albums/{album['id']}/contributions", json={"nom": "Anonyme"}).json()
    assert c["nom"] == "Anonyme" and c["role"] is None


def test_contribution_erreurs(client, album):
    """Album absent → 404 ; nom vide → 422."""
    assert client.post("/api/albums/999999/contributions",
                       json={"nom": "X"}).status_code == 404
    assert client.post(f"/api/albums/{album['id']}/contributions",
                       json={"nom": "   "}).status_code == 422
    assert client.delete("/api/contributions/999999").status_code == 404


def test_suppression_album_cascade_contributions(client, album, db_path):
    """Supprimer l'album efface ses contributions (CASCADE), pas le vocabulaire de rôles."""
    import sqlite3
    aid = album["id"]
    client.post(f"/api/albums/{aid}/contributions", json={"nom": "X", "role": "scénariste"})
    client.delete(f"/api/albums/{aid}")
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM contribution WHERE album_id=?",
                            (aid,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM contribution_role "
                            "WHERE label='scénariste'").fetchone()[0] == 1   # rôle conservé
    finally:
        conn.close()
