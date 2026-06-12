"""Tests de non-régression, un par bug réellement corrigé.

Chaque test nomme et reproduit le scénario du bug ; ils servent de filet
permanent contre la réintroduction de ces défauts.
"""
from conftest import KUMIKO_SAMPLE, direct_query, requires_kumiko


def test_ecriture_persistee_sur_disque(client, db_path):
    """commit explicite : la donnée écrite doit être committée (visible depuis
    une connexion SQLite séparée), pas seulement en mémoire de la requête."""
    aid = client.post("/api/albums", json={"titre": "Persist"}).json()["id"]
    rows = direct_query(db_path, "SELECT titre FROM albums WHERE id=?", (aid,))
    assert rows and rows[0]["titre"] == "Persist"


def test_tag_finissant_par_chiffre_conserve(client, region):
    """Un tag terminé par un chiffre (ex. 'tome1') ne doit pas être tronqué."""
    r = client.put(f"/api/regions/{region['id']}/annotation",
                   json={"note": "", "tags": ["tome1", "case2"]})
    labels = {t["label"] for t in r.json()["tags"]}
    assert labels == {"tome1", "case2"}
    res = client.get("/api/recherche", params={"q": "tome1"}).json()["results"]
    assert any(x["region_id"] == region["id"] for x in res)


def test_suppression_region_nettoie_fts(client, planche, db_path):
    """Supprimer une région (et sa descendance) retire ses lignes FTS."""
    parent = client.post(f"/api/planches/{planche['id']}/regions",
                         json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9,
                               "ocr_texte": "PARENTOCR"}).json()
    child = client.post(f"/api/planches/{planche['id']}/regions",
                        json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5,
                              "parent_id": parent["id"], "ocr_texte": "ENFANTOCR"}).json()
    client.delete(f"/api/regions/{parent['id']}")
    orphelins = direct_query(
        db_path,
        "SELECT COUNT(*) AS n FROM recherche "
        "WHERE region_id NOT IN (SELECT id FROM regions)")[0]["n"]
    assert orphelins == 0
    assert not client.get("/api/recherche", params={"q": "ENFANTOCR"}).json()["results"]


@requires_kumiko
def test_resegmentation_preserve_ocr_et_fts_propre(client, album, db_path):
    """Re-segmenter PRÉSERVE le travail humain (bulle océrisée conservée, et
    annotation de case TRANSFÉRÉE à la nouvelle case recouvrante) sans laisser
    de ligne FTS orpheline."""
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("s.png", KUMIKO_SAMPLE.read_bytes(), "image/png")}).json()
    client.post(f"/api/planches/{p['id']}/segmenter")
    case_id = client.get(f"/api/planches/{p['id']}/regions").json()[0]["id"]
    # une case annotée (FTS) + une bulle océrisée enfant (FTS)
    client.put(f"/api/regions/{case_id}/annotation", json={"note": "ANNOTCASE", "tags": []})
    child = client.post(f"/api/planches/{p['id']}/regions",
                        json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5,
                              "parent_id": case_id, "ocr_texte": "GARDE"}).json()
    assert client.get("/api/recherche", params={"q": "GARDE"}).json()["results"]

    client.post(f"/api/planches/{p['id']}/segmenter")  # re-segmentation

    # aucune ligne FTS orpheline
    orphelins = direct_query(
        db_path,
        "SELECT COUNT(*) AS n FROM recherche "
        "WHERE region_id NOT IN (SELECT id FROM regions)")[0]["n"]
    assert orphelins == 0
    # la bulle océrisée SURVIT et reste cherchable
    regions = client.get(f"/api/planches/{p['id']}/regions").json()
    surv = next((r for r in regions if r["id"] == child["id"]), None)
    assert surv is not None and surv["ocr_texte"] == "GARDE"
    assert client.get("/api/recherche", params={"q": "GARDE"}).json()["results"]
    # l'annotation de case est transférée à la nouvelle case recouvrante (cherchable)
    assert client.get("/api/recherche", params={"q": "ANNOTCASE"}).json()["results"]


def test_reimport_meme_album_numerote_correctement(client, album, png_bytes):
    """Régression nommage : 2e import -> numéro 2, dérivé planche_0002."""
    client.post(f"/api/albums/{album['id']}/import",
                files={"file": ("a.png", png_bytes, "image/png")})
    p2 = client.post(f"/api/albums/{album['id']}/import",
                     files={"file": ("b.png", png_bytes, "image/png")}).json()
    assert p2["numero"] == 2 and p2["chemin_web"].endswith("planche_0002.jpg")
