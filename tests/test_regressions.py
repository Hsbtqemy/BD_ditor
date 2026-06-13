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


# --------------------------------------------------------------------------- #
# Validation de parent_id (sans elle : régions omises de l'export + DELETE
# récursif non borné sur cycle). Une FK seule ne garantit pas ces invariants.
# --------------------------------------------------------------------------- #
def test_parent_introuvable_rejete(client, planche):
    """Un parent_id inexistant est refusé (422), pas inséré tel quel."""
    r = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "bulle", "parent_id": 999999,
                          "x": 1, "y": 1, "w": 5, "h": 5})
    assert r.status_code == 422


def test_parent_cross_planche_rejete(client, album, png_bytes):
    """Un parent_id appartenant à une AUTRE planche est refusé (422) — sinon
    la région est silencieusement omise de l'export (arbre cassé)."""
    p1 = client.post(f"/api/albums/{album['id']}/import",
                     files={"file": ("a.png", png_bytes, "image/png")}).json()
    p2 = client.post(f"/api/albums/{album['id']}/import",
                     files={"file": ("b.png", png_bytes, "image/png")}).json()
    parent = client.post(f"/api/planches/{p2['id']}/regions",
                         json={"type": "case", "x": 0, "y": 0, "w": 50, "h": 50}).json()
    r = client.post(f"/api/planches/{p1['id']}/regions",
                    json={"type": "bulle", "parent_id": parent["id"],
                          "x": 1, "y": 1, "w": 5, "h": 5})
    assert r.status_code == 422


def test_auto_parent_rejete(client, region):
    """Une région ne peut pas être son propre parent (sinon DELETE récursif)."""
    r = client.put(f"/api/regions/{region['id']}", json={"parent_id": region["id"]})
    assert r.status_code == 422


def test_cycle_parent_rejete(client, planche):
    """Un cycle (faire de son descendant son parent) est refusé (422)."""
    a = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "case", "x": 0, "y": 0, "w": 80, "h": 80}).json()
    b = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "bulle", "parent_id": a["id"],
                          "x": 1, "y": 1, "w": 5, "h": 5}).json()
    # b est descendant de a -> donner b comme parent de a créerait un cycle
    r = client.put(f"/api/regions/{a['id']}", json={"parent_id": b["id"]})
    assert r.status_code == 422


def test_detacher_parent_autorise(client, planche):
    """parent_id = null (détacher) reste autorisé (200) — la validation ne doit
    pas bloquer ce cas légitime."""
    a = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "case", "x": 0, "y": 0, "w": 80, "h": 80}).json()
    b = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "bulle", "parent_id": a["id"],
                          "x": 1, "y": 1, "w": 5, "h": 5}).json()
    r = client.put(f"/api/regions/{b['id']}", json={"parent_id": None})
    assert r.status_code == 200 and r.json()["parent_id"] is None


def test_coords_negatives_rejetees(client, planche):
    """Des coordonnées négatives sont refusées (422), en création et en MAJ."""
    r = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "case", "x": -5, "y": 0, "w": 10, "h": 10})
    assert r.status_code == 422
    reg = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "case", "x": 0, "y": 0, "w": 10, "h": 10}).json()
    assert client.put(f"/api/regions/{reg['id']}", json={"w": -3}).status_code == 422


def test_recherche_limit_borne(client, planche):
    """limit=-1 ne doit PAS renvoyer tout le corpus (LIMIT -1 SQLite = illimité) :
    la borne le ramène à 1."""
    for i in range(3):
        client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "bulle", "x": i, "y": 0, "w": 5, "h": 5,
                          "ocr_texte": "COMMUN"})
    res = client.get("/api/recherche", params={"q": "COMMUN", "limit": -1}).json()
    assert res["count"] == 1


def test_recherche_tags_repetes_et_virgule(client, planche):
    """Tags transmis en paramètres RÉPÉTÉS (pas join ',') : un label contenant
    une virgule n'est plus scindé, et plusieurs tags = ET logique."""
    r1 = client.post(f"/api/planches/{planche['id']}/regions",
                     json={"type": "bulle", "x": 0, "y": 0, "w": 5, "h": 5}).json()
    r2 = client.post(f"/api/planches/{planche['id']}/regions",
                     json={"type": "bulle", "x": 6, "y": 0, "w": 5, "h": 5}).json()
    client.put(f"/api/regions/{r1['id']}/annotation",
               json={"note": "", "tags": ["paris, france", "jour"]})
    client.put(f"/api/regions/{r2['id']}/annotation",
               json={"note": "", "tags": ["jour"]})
    # le label à virgule n'est pas scindé : seule r1 le porte
    res = client.get("/api/recherche", params={"tags": ["paris, france"]}).json()["results"]
    assert [x["region_id"] for x in res] == [r1["id"]]
    # deux tags répétés = ET : seule r1 a les deux
    res2 = client.get("/api/recherche",
                      params={"tags": ["paris, france", "jour"]}).json()["results"]
    assert [x["region_id"] for x in res2] == [r1["id"]]


def test_export_tei_filtre_caracteres_non_xml(client, planche):
    """G1 : des caractères de contrôle non-XML dans l'OCR ne doivent PAS produire
    un TEI corrompu — l'export reste un XML bien formé (re-parsable)."""
    import xml.etree.ElementTree as ET
    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "bulle", "x": 0, "y": 0, "w": 5, "h": 5,
                      "ocr_texte": "AVANT\x0bMILIEU\x1fAPRES"})
    r = client.get("/api/export/tei", params={"album_id": planche["album_id"]})
    assert r.status_code == 200
    ET.fromstring(r.content)        # ne doit pas lever ParseError (XML bien formé)
    assert "\x0b" not in r.text and "\x1f" not in r.text
    assert "AVANTMILIEUAPRES" in r.text


def test_import_numero_inferieur_a_un_rejete(client, album, png_bytes):
    """G6 : un numéro de planche < 1 est refusé (422) — 0 (falsy) désalignait les
    noms master/dérivé, les négatifs produisaient des noms aberrants."""
    for bad in ("0", "-3"):
        r = client.post(f"/api/albums/{album['id']}/import",
                        files={"file": ("p.png", png_bytes, "image/png")},
                        data={"numero": bad})
        assert r.status_code == 422
