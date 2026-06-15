"""Routes API : albums, planches, régions, annotations, tags, recherche, export."""
import csv
import io
import sqlite3
import xml.etree.ElementTree as ET

from fastapi.testclient import TestClient
from PIL import Image

import main
from pipeline.segmentation import KumikoError


# --------------------------- Albums & planches --------------------------- #
def test_create_et_list_albums(client):
    r = client.post("/api/albums", json={"titre": "Esther", "auteur": "Sattouf",
                                         "annee": 2016, "serie": "Esther"})
    assert r.status_code == 201
    a = r.json()
    assert a["titre"] == "Esther"
    lst = client.get("/api/albums").json()
    assert len(lst) == 1 and lst[0]["nb_planches"] == 0


def test_planches_album_inexistant_404(client):
    assert client.get("/api/albums/999/planches").status_code == 404


def test_import_planche(client, album, png_bytes):
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("p.png", png_bytes, "image/png")})
    assert r.status_code == 201
    p = r.json()
    assert p["statut"] == "importee"
    assert p["url_web"].startswith("/derivatives/")
    planches = client.get(f"/api/albums/{album['id']}/planches").json()
    assert len(planches) == 1 and planches[0]["nb_regions"] == 0


def test_import_album_inexistant_404(client, png_bytes):
    r = client.post("/api/albums/999/import",
                    files={"file": ("p.png", png_bytes, "image/png")})
    assert r.status_code == 404


def test_import_fichier_vide_400(client, album):
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("v.png", b"", "image/png")})
    assert r.status_code == 400


# --------------------------- Rôle éditorial ----------------------------- #
def test_role_par_defaut_et_numero_editorial(client, album, png_bytes):
    """Toute planche importée est 'recit' et reçoit un numéro éditorial 1..N."""
    for _ in range(2):
        client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("p.png", png_bytes, "image/png")})
    planches = client.get(f"/api/albums/{album['id']}/planches").json()
    assert [p["role"] for p in planches] == ["recit", "recit"]
    assert [p["numero_editorial"] for p in planches] == [1, 2]


def test_marquer_paratexte_renumerote(client, album, png_bytes):
    """Marquer la 1re planche 'paratexte' la sort de la numérotation (→ None) et la
    suivante devient « planche 1 »."""
    ids = [client.post(f"/api/albums/{album['id']}/import",
                       files={"file": ("p.png", png_bytes, "image/png")}).json()["id"]
           for _ in range(2)]
    r = client.patch(f"/api/planches/{ids[0]}/role", json={"role": "paratexte"})
    assert r.status_code == 200
    assert r.json()["role"] == "paratexte"
    assert r.json()["numero_editorial"] is None
    planches = {p["id"]: p
                for p in client.get(f"/api/albums/{album['id']}/planches").json()}
    assert planches[ids[0]]["numero_editorial"] is None
    assert planches[ids[1]]["numero_editorial"] == 1


def test_role_invalide_422(client, planche):
    assert client.patch(f"/api/planches/{planche['id']}/role",
                        json={"role": "n_importe_quoi"}).status_code == 422


def test_role_planche_inexistante_404(client):
    assert client.patch("/api/planches/999/role",
                        json={"role": "paratexte"}).status_code == 404


# --------------------------- Citation des régions ----------------------- #
def test_citation_dans_regions_et_recherche(client, album, planche):
    """Les régions et les résultats de recherche portent leur citation éditoriale :
    pl·c pour une case, pl·c·b pour une bulle."""
    c1 = client.post(f"/api/planches/{planche['id']}/regions",
                     json={"type": "case", "x": 0, "y": 0, "w": 50, "h": 50}).json()
    c2 = client.post(f"/api/planches/{planche['id']}/regions",
                     json={"type": "case", "x": 0, "y": 100, "w": 50, "h": 50}).json()
    b = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "bulle", "x": 5, "y": 105, "w": 20, "h": 20,
                          "parent_id": c2["id"], "ocr_texte": "BONJOUR"}).json()

    regions = {r["id"]: r
               for r in client.get(f"/api/planches/{planche['id']}/regions").json()}
    assert regions[c1["id"]]["citation"]["texte"] == "pl.1 · c1"
    assert regions[c2["id"]]["citation"]["texte"] == "pl.1 · c2"
    assert regions[b["id"]]["citation"]["texte"] == "pl.1 · c2 · b1"
    assert regions[c1["id"]]["citation"]["total"] == 2

    res = client.get(f"/api/recherche?album={album['id']}&type=case").json()["results"]
    assert {r["citation"]["texte"] for r in res} == {"pl.1 · c1", "pl.1 · c2"}


def test_citation_paratexte(client, album, planche):
    """Une région d'une planche paratexte est citée « Paratexte » (hors numérotation)."""
    c = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "case", "x": 0, "y": 0, "w": 50, "h": 50}).json()
    client.patch(f"/api/planches/{planche['id']}/role", json={"role": "paratexte"})
    regions = {r["id"]: r
               for r in client.get(f"/api/planches/{planche['id']}/regions").json()}
    assert regions[c["id"]]["citation"] == {"planche": None, "texte": "Paratexte"}


# ------------------------------- Régions -------------------------------- #
def test_create_region_ordre_auto(client, planche):
    r1 = client.post(f"/api/planches/{planche['id']}/regions",
                     json={"type": "case", "x": 0, "y": 0, "w": 10, "h": 10})
    r2 = client.post(f"/api/planches/{planche['id']}/regions",
                     json={"type": "case", "x": 0, "y": 0, "w": 10, "h": 10})
    assert r1.json()["ordre"] == 1 and r2.json()["ordre"] == 2
    assert r1.json()["source"] == "manuel"


def test_create_region_type_invalide_422(client, planche):
    r = client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "zorglub", "x": 0, "y": 0, "w": 1, "h": 1})
    assert r.status_code == 422


def test_list_regions_nb_enfants_et_annotee(client, planche, region):
    child = client.post(f"/api/planches/{planche['id']}/regions",
                        json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5,
                              "parent_id": region["id"]}).json()
    regions = client.get(f"/api/planches/{planche['id']}/regions").json()
    parent = next(x for x in regions if x["id"] == region["id"])
    assert parent["nb_enfants"] == 1
    assert next(x for x in regions if x["id"] == child["id"])["parent_id"] == region["id"]


def test_update_region_partiel(client, region):
    r = client.put(f"/api/regions/{region['id']}",
                   json={"w": 222, "type": "bulle"})
    assert r.status_code == 200
    body = r.json()
    assert body["w"] == 222 and body["type"] == "bulle"
    assert body["x"] == region["x"]  # inchangé


def test_update_region_type_invalide_422(client, region):
    assert client.put(f"/api/regions/{region['id']}",
                      json={"type": "xxx"}).status_code == 422


def test_update_region_inexistante_404(client):
    assert client.put("/api/regions/999", json={"w": 1}).status_code == 404


def test_delete_region_cascade(client, planche, region):
    child = client.post(f"/api/planches/{planche['id']}/regions",
                        json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5,
                              "parent_id": region["id"]}).json()
    assert client.delete(f"/api/regions/{region['id']}").status_code == 204
    ids = [x["id"] for x in client.get(f"/api/planches/{planche['id']}/regions").json()]
    assert region["id"] not in ids and child["id"] not in ids


# ------------------------------- Statut --------------------------------- #
def test_patch_statut(client, planche):
    r = client.patch(f"/api/planches/{planche['id']}/statut",
                     json={"statut": "corrigee"})
    assert r.status_code == 200 and r.json()["statut"] == "corrigee"


def test_patch_statut_invalide_422(client, planche):
    assert client.patch(f"/api/planches/{planche['id']}/statut",
                        json={"statut": "bidon"}).status_code == 422


# ---------------------------- Annotations ------------------------------- #
def test_put_annotation_et_tags_minuscules(client, region):
    r = client.put(f"/api/regions/{region['id']}/annotation",
                   json={"note": "Salutation", "tags": ["Dialogue", "  AMITIÉ  "]})
    assert r.status_code == 200
    labels = {t["label"] for t in r.json()["tags"]}
    assert labels == {"dialogue", "amitié"}  # normalisés en minuscules


def test_get_annotation_vide(client, region):
    a = client.get(f"/api/regions/{region['id']}/annotation").json()
    assert a["note"] is None and a["tags"] == []


def test_annotation_upsert_remplace_tags(client, region):
    client.put(f"/api/regions/{region['id']}/annotation",
               json={"note": "n1", "tags": ["a", "b"]})
    client.put(f"/api/regions/{region['id']}/annotation",
               json={"note": "n2", "tags": ["c"]})
    a = client.get(f"/api/regions/{region['id']}/annotation").json()
    assert a["note"] == "n2" and {t["label"] for t in a["tags"]} == {"c"}


def test_put_annotation_vide_supprime_la_ligne(client, region):
    """Vider une annotation (note blanche + tags blancs) SUPPRIME la ligne : pas
    de coquille vide (sinon fausse le compteur d'annotées, n'est pas cherchable,
    et ferait conserver à tort la case à la re-segmentation)."""
    rid = region["id"]
    base = client.get("/api/corpus").json()["annotees"]
    client.put(f"/api/regions/{rid}/annotation", json={"note": "temporaire", "tags": ["x"]})
    assert client.get("/api/corpus").json()["annotees"] == base + 1
    # note blanche + tags réduits à rien après normalisation -> suppression
    r = client.put(f"/api/regions/{rid}/annotation", json={"note": "  ", "tags": ["  ", ""]})
    assert r.status_code == 200 and not r.json()["note"] and r.json()["tags"] == []
    assert client.get("/api/corpus").json()["annotees"] == base       # ligne supprimée
    assert not client.get("/api/recherche", params={"q": "temporaire"}).json()["results"]


def test_tags_frequence(client, region):
    client.put(f"/api/regions/{region['id']}/annotation",
               json={"note": "", "tags": ["nuit"]})
    tags = {t["label"]: t["frequence"] for t in client.get("/api/tags").json()}
    assert tags.get("nuit") == 1


def test_create_tag_idempotent(client):
    client.post("/api/tags", json={"label": "PLUIE", "couleur": "#111"})
    client.post("/api/tags", json={"label": "pluie"})
    labels = [t["label"] for t in client.get("/api/tags").json()]
    assert labels.count("pluie") == 1


# ------------------------------ Recherche ------------------------------- #
def _region_avec_ocr_et_annotation(client, planche):
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5,
                            "ocr_texte": "Bonjour Esther"}).json()["id"]
    client.put(f"/api/regions/{rid}/annotation",
               json={"note": "salutation amicale", "tags": ["dialogue"]})
    return rid


def test_recherche_par_ocr(client, planche):
    rid = _region_avec_ocr_et_annotation(client, planche)
    res = client.get("/api/recherche", params={"q": "Esther"}).json()["results"]
    assert any(r["region_id"] == rid for r in res)


def test_recherche_par_note(client, planche):
    rid = _region_avec_ocr_et_annotation(client, planche)
    res = client.get("/api/recherche", params={"q": "amicale"}).json()["results"]
    assert any(r["region_id"] == rid for r in res)


def test_recherche_filtre_tag(client, planche):
    rid = _region_avec_ocr_et_annotation(client, planche)
    res = client.get("/api/recherche", params={"tags": "dialogue"}).json()["results"]
    assert any(r["region_id"] == rid for r in res)


def test_recherche_filtre_type(client, planche):
    rid = _region_avec_ocr_et_annotation(client, planche)
    res = client.get("/api/recherche",
                     params={"q": "Esther", "type": "bulle"}).json()["results"]
    assert any(r["region_id"] == rid for r in res)
    res2 = client.get("/api/recherche",
                      params={"q": "Esther", "type": "case"}).json()["results"]
    assert not any(r["region_id"] == rid for r in res2)


def test_recherche_requete_speciale_ne_casse_pas(client, planche):
    # caractères spéciaux FTS ne doivent pas provoquer 500
    r = client.get("/api/recherche", params={"q": '"('})
    assert r.status_code in (200, 400)


def test_recherche_export_csv_porte_la_citation(client, planche):
    """L'export CSV des résultats porte la colonne `citation` et le numéro ÉDITORIAL
    de planche (et non l'ordre d'import) — l'artefact que le chercheur emporte."""
    _region_avec_ocr_et_annotation(client, planche)
    txt = client.get("/api/recherche/export.csv", params={"q": "Esther"}).text
    header = txt.lstrip("﻿").splitlines()[0]
    assert header.startswith("album,planche,citation,region_id")
    assert "pl.1" in txt          # citation éditoriale présente


# ------------------------------- Export --------------------------------- #
def test_export_json_arbre(client, planche, region):
    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5,
                      "parent_id": region["id"], "ocr_texte": "txt"})
    j = client.get("/api/export/json",
                   params={"album_id": planche["album_id"]}).json()
    enfants = j["planches"][0]["regions"][0]["enfants"]
    assert enfants and enfants[0]["type"] == "bulle"


def test_export_csv(client, planche, region):
    txt = client.get("/api/export/csv",
                     params={"album_id": planche["album_id"]}).text
    assert "region_id" in txt and "case" in txt


def test_export_tei_facsimile(client, planche, region):
    xml = client.get("/api/export/tei",
                     params={"album_id": planche["album_id"]}).text
    assert "<facsimile" in xml and 'type="case"' in xml
    assert f'ulx="{region["x"]}"' in xml


def test_export_csv_album_porte_la_citation(client, album, planche):
    """Le CSV d'album cite le numéro ÉDITORIAL + la citation complète (Lot 3)."""
    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "case", "x": 0, "y": 0, "w": 50, "h": 50})
    txt = client.get("/api/export/csv", params={"album_id": album["id"]}).text
    assert "album,ordre_import,planche,citation,region_id" in txt
    assert "pl.1 · c1" in txt


def test_export_csv_album_paratexte(client, album, planche):
    """Une planche paratexte garde sa PAGE PHYSIQUE (ordre_import) mais n'a pas de
    numéro éditorial ; sa citation est « Paratexte »."""
    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "case", "x": 0, "y": 0, "w": 50, "h": 50})
    client.patch(f"/api/planches/{planche['id']}/role", json={"role": "paratexte"})
    txt = client.get("/api/export/csv", params={"album_id": album["id"]}).text
    row = list(csv.DictReader(io.StringIO(txt.lstrip("﻿"))))[0]
    assert row["ordre_import"] == "1"     # page physique conservée (groupable)
    assert row["planche"] == ""           # hors numérotation éditoriale
    assert row["citation"] == "Paratexte"


def test_export_json_numero_editorial_et_citation(client, album, planche):
    """Le JSON d'album porte numero_editorial + role par planche et la citation
    par région (Lot 3)."""
    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "case", "x": 0, "y": 0, "w": 50, "h": 50})
    j = client.get("/api/export/json", params={"album_id": album["id"]}).json()
    p0 = j["planches"][0]
    assert p0["numero_editorial"] == 1 and p0["role"] == "recit"
    assert p0["regions"][0]["citation"]["texte"] == "pl.1 · c1"


def test_export_tei_numero_editorial_et_paratexte(client, album, png_bytes):
    """TEI : @n = numéro éditorial sur les planches récit, marquage paratexte sur la
    couverture, et @n citable sur les zones (Lot 3)."""
    couv = client.post(f"/api/albums/{album['id']}/import",
                       files={"file": ("p.png", png_bytes, "image/png")}).json()
    p1 = client.post(f"/api/albums/{album['id']}/import",
                     files={"file": ("p.png", png_bytes, "image/png")}).json()
    client.patch(f"/api/planches/{couv['id']}/role", json={"role": "paratexte"})
    case = client.post(f"/api/planches/{p1['id']}/regions",
                       json={"type": "case", "x": 0, "y": 0, "w": 50, "h": 50}).json()
    client.post(f"/api/planches/{p1['id']}/regions",
                json={"type": "bulle", "x": 5, "y": 5, "w": 20, "h": 20,
                      "parent_id": case["id"]})
    resp = client.get("/api/export/tei", params={"album_id": album["id"]})
    ET.fromstring(resp.content)           # TEI bien formé (re-parsable) — sinon lève
    xml = resp.text
    assert 'type="paratexte"' in xml      # la couverture
    assert 'n="1"' in xml                 # 1re planche récit
    assert 'n="c1·b1"' in xml             # zone bulle citable (cas piège : « · » dans @n)


# ----------------------------- Navigation ------------------------------- #
def test_surfaces_exposent_le_bouton_retour(client):
    """Les trois surfaces servent le bouton « ← Retour » (round-trip, Lot 5)."""
    for route in ("/", "/recherche", "/exploration"):
        assert 'id="back-link"' in client.get(route).text, route


def test_nav_js_servi_et_charge_avant_le_script_de_page(client):
    """Garde-fou rapide du refacto : le module partagé static/lib/nav.js est servi et
    chargé AVANT le script de chaque page. Sinon `Nav.safeRetour` est indéfini et la
    surface plante au chargement (sans ce test, le run rapide resterait vert)."""
    js = client.get("/static/lib/nav.js")
    assert js.status_code == 200 and "safeRetour" in js.text
    for route, page_script in (("/", "/static/viewer.js"),
                               ("/recherche", "/static/recherche.js"),
                               ("/exploration", "/static/exploration.js")):
        html = client.get(route).text
        assert "/static/lib/nav.js" in html, route
        assert html.index("/static/lib/nav.js") < html.index(page_script), route


def test_export_album_inexistant_404(client):
    assert client.get("/api/export/json",
                      params={"album_id": 999}).status_code == 404
    assert client.get("/api/export/tei",
                      params={"album_id": 999}).status_code == 404


# --------------------------- Divers / santé ----------------------------- #
def test_index_sert_le_shell_html(client):
    r = client.get("/")
    assert r.status_code == 200 and "BD" in r.text


def test_sante_expose_kumiko(client):
    r = client.get("/api/sante")
    assert r.status_code == 200 and isinstance(r.json()["kumiko"], bool)


def test_corpus_stats(client, region):
    c = client.get("/api/corpus").json()
    assert set(c) >= {"albums", "planches", "regions", "annotees", "transcrites", "tags"}
    assert c["albums"] >= 1 and c["planches"] >= 1 and c["regions"] >= 1


def test_corpus_transcrites_compte_le_texte(client, planche):
    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5,
                      "ocr_texte": "Bonjour"})
    assert client.get("/api/corpus").json()["transcrites"] >= 1


def test_recherche_page_servie(client):
    r = client.get("/recherche")
    assert r.status_code == 200 and "Recherche" in r.text


def test_create_tag_label_vide_422(client):
    assert client.post("/api/tags", json={"label": "   "}).status_code == 422


def test_update_region_sans_champ_inchange(client, region):
    """PUT sans champ modifiable ne casse pas et renvoie la région inchangée."""
    r = client.put(f"/api/regions/{region['id']}", json={})
    assert r.status_code == 200 and r.json()["w"] == region["w"]


def test_segmenter_sans_kumiko_renvoie_503(client, planche, monkeypatch):
    """Dégradation gracieuse : Kumiko absent -> 503 explicite, pas un crash."""
    monkeypatch.setattr("main.kumiko_available", lambda: False)
    r = client.post(f"/api/planches/{planche['id']}/segmenter")
    assert r.status_code == 503 and "Kumiko" in r.json()["detail"]


# ----------------------- Chemins d'erreur / bords ----------------------- #
def test_lifespan_initialise_la_base(data_dir):
    """Le handler lifespan (startup) initialise la base via le context manager."""
    with TestClient(main.app) as c:
        assert c.get("/api/sante").status_code == 200


def test_planche_inexistante_404_sur_ses_routes(client):
    assert client.get("/api/planches/999/regions").status_code == 404
    assert client.post("/api/planches/999/regions",
                       json={"type": "case"}).status_code == 404
    assert client.patch("/api/planches/999/statut",
                        json={"statut": "corrigee"}).status_code == 404
    assert client.post("/api/planches/999/segmenter").status_code == 404


def test_delete_region_inexistante_404(client):
    assert client.delete("/api/regions/999").status_code == 404


def test_annotation_region_inexistante_404(client):
    assert client.get("/api/regions/999/annotation").status_code == 404
    assert client.put("/api/regions/999/annotation",
                      json={"note": "x", "tags": []}).status_code == 404


def test_annotation_tags_tous_vides(client, region):
    """Tags ne contenant que des espaces -> aucun tag (branche _ensure_tags vide)."""
    r = client.put(f"/api/regions/{region['id']}/annotation",
                   json={"note": "n", "tags": ["  ", ""]})
    assert r.status_code == 200 and r.json()["tags"] == []


def test_update_region_ocr_reindexe(client, region):
    """Modifier l'OCR via PUT réindexe la région (recherche)."""
    client.put(f"/api/regions/{region['id']}", json={"ocr_texte": "ZORGLUBESQUE"})
    res = client.get("/api/recherche", params={"q": "ZORGLUBESQUE"}).json()["results"]
    assert any(r["region_id"] == region["id"] for r in res)


def test_recherche_filtre_album(client, planche):
    rid = _region_avec_ocr_et_annotation(client, planche)
    res = client.get("/api/recherche",
                     params={"q": "Esther", "album": planche["album_id"]}).json()["results"]
    assert any(r["region_id"] == rid for r in res)
    other = client.post("/api/albums", json={"titre": "Autre"}).json()["id"]
    res2 = client.get("/api/recherche",
                      params={"q": "Esther", "album": other}).json()["results"]
    assert not res2


def test_recherche_erreur_sql_renvoie_400(client):
    """Couvre le garde-fou OperationalError via une connexion qui échoue."""
    class _Boom:
        def execute(self, *a, **k):
            raise sqlite3.OperationalError("boom")
        def commit(self): ...
        def rollback(self): ...
        def close(self): ...

    def boom_db():            # générateur : override correct d'une dépendance yield
        yield _Boom()

    main.app.dependency_overrides[main.db] = boom_db
    try:
        assert client.get("/api/recherche", params={"q": "x"}).status_code == 400
    finally:
        main.app.dependency_overrides.pop(main.db, None)


def test_db_locked_renvoie_409(client):
    """Contention SQLite (« database is locked ») sur une route d'écriture → 409."""
    class _Locked:
        def execute(self, *a, **k):
            raise sqlite3.OperationalError("database is locked")
        def commit(self): ...
        def rollback(self): ...
        def close(self): ...

    def locked_db():
        yield _Locked()

    main.app.dependency_overrides[main.db] = locked_db
    try:
        assert client.post("/api/albums", json={"titre": "x"}).status_code == 409
    finally:
        main.app.dependency_overrides.pop(main.db, None)


def test_export_csv_album_inexistant_404(client):
    assert client.get("/api/export/csv", params={"album_id": 999}).status_code == 404


def test_export_tei_complet(client):
    """Album avec auteur + région avec OCR + annotation note/tags : couvre les
    branches author / <line> OCR / <note> de l'export TEI."""
    aid = client.post("/api/albums",
                      json={"titre": "T", "auteur": "Sattouf"}).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (100, 120), "white").save(buf, "PNG")
    pid = client.post(f"/api/albums/{aid}/import",
                      files={"file": ("p.png", buf.getvalue(), "image/png")}).json()["id"]
    rid = client.post(f"/api/planches/{pid}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5,
                            "ocr_texte": "TEXTEOCR"}).json()["id"]
    client.put(f"/api/regions/{rid}/annotation",
               json={"note": "une note", "tags": ["nuit"]})
    xml = client.get("/api/export/tei", params={"album_id": aid}).text
    assert "Sattouf" in xml
    assert "TEXTEOCR" in xml
    assert "une note" in xml and 'ana="nuit"' in xml


def test_import_fichier_non_image_400(client, album):
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("bad.png", b"pas une image", "image/png")})
    assert r.status_code == 400


def test_segmenter_kumikoerror_renvoie_500(client, planche, monkeypatch):
    monkeypatch.setattr("main.kumiko_available", lambda: True)

    def boom(*a, **k):
        raise KumikoError("explosion")

    monkeypatch.setattr("main.segment_planche", boom)
    r = client.post(f"/api/planches/{planche['id']}/segmenter")
    assert r.status_code == 500 and "explosion" in r.json()["detail"]
