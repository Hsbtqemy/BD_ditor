"""Tests de non-régression, un par bug réellement corrigé.

Chaque test nomme et reproduit le scénario du bug ; ils servent de filet
permanent contre la réintroduction de ces défauts.
"""
import pytest
from conftest import KUMIKO_SAMPLE, direct_query, requires_kumiko
from pipeline.nlp import nlp_available


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


def test_garde_anti_bombe_reactivee():
    """Bug : `Image.MAX_IMAGE_PIXELS = None` désactivait la protection anti-bombe
    de décompression (risque OOM). Elle doit rester bornée (jamais None)."""
    import pipeline.ingest  # noqa: F401  (fixe la limite à l'import)
    import pipeline.ocr as ocrm
    from PIL import Image
    assert Image.MAX_IMAGE_PIXELS is not None
    # le module OCR la repositionne aussi à l'ouverture d'image (jamais None)
    assert ocrm.MAX_IMAGE_PIXELS is not None and ocrm.MAX_IMAGE_PIXELS > 0


def test_recherche_prefixe_et_accents(client, planche):
    """Bug : « otage » ne trouvait pas « Otages », « eloignez » pas « éloignez ».
    Correctif : requêtes FTS en PRÉFIXE + tokenizer insensible aux accents."""
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                            "ocr_texte": "Les Otages ÉLOIGNEZ-vous"}).json()["id"]
    # pluriel / casse (préfixe) : « otage » → « Otages »
    res = client.get("/api/recherche", params={"q": "otage"}).json()["results"]
    assert any(x["region_id"] == rid for x in res)
    # accents : « eloignez » → « ÉLOIGNEZ »
    res2 = client.get("/api/recherche", params={"q": "eloignez"}).json()["results"]
    assert any(x["region_id"] == rid for x in res2)


@pytest.mark.skipif(not nlp_available(), reason="spaCy / modèle français non installé")
def test_recherche_par_lemme(client, planche):
    """Palier A : la recherche par LEMME attrape ce que le préfixe ne peut pas —
    « cheval »→« chevaux », « galoper »→« galopaient » (aucune relation de préfixe)."""
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                            "ocr_texte": "LES CHEVAUX GALOPAIENT"}).json()["id"]
    for q in ("cheval", "galoper"):
        res = client.get("/api/recherche", params={"q": q}).json()["results"]
        assert any(x["region_id"] == rid for x in res), f"« {q} » devrait matcher par lemme"


@pytest.mark.skipif(not nlp_available(), reason="spaCy / modèle français non installé")
def test_analyse_grammaticale(client, planche):
    """Palier B : tokens (lemme/POS/morph) par région + fréquences lexicales."""
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                            "ocr_texte": "LE GAULOIS BUVAIT LA POTION"}).json()["id"]
    toks = client.get(f"/api/regions/{rid}/tokens").json()
    assert toks, "des tokens doivent être produits"
    assert "boire" in {t["lemme"] for t in toks}        # BUVAIT → boire (lemme)
    assert any(t["pos"] == "VERB" for t in toks)        # catégorie grammaticale présente
    # fréquences lexicales, filtrées sur les verbes
    verbes = client.get("/api/analyse/lemmes", params={"pos": "VERB"}).json()["results"]
    assert any(v["lemme"] == "boire" and v["pos"] == "VERB" for v in verbes)
    assert client.get("/api/regions/999999/tokens").status_code == 404


@pytest.mark.skipif(not nlp_available(), reason="spaCy / modèle français non installé")
def test_reindex_all_repeuple(client, planche, db_path):
    """`reindex_all()` (re)peuple lemmes + tokens en lot et enregistre le modèle
    (repro) — l'outil de réindexation explicite (post-migration structurelle,
    changement de modèle, ou index définitif)."""
    import sqlite3
    import database
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                            "ocr_texte": "LES CHEVAUX GALOPAIENT"}).json()["id"]
    # Simule l'état post-migration STRUCTURELLE : enrichissement NLP vidé.
    raw = sqlite3.connect(db_path)
    raw.execute("UPDATE recherche SET lemmes = ''")
    raw.execute("DELETE FROM tokens")
    raw.commit(); raw.close()
    assert not client.get(f"/api/regions/{rid}/tokens").json()        # tokens vidés

    conn = database.get_connection()
    try:
        assert database.reindex_all(conn) >= 1
    finally:
        conn.close()

    # lemmes + tokens repeuplés ; recherche par lemme de nouveau opérante
    assert any(t["lemme"] == "cheval" for t in client.get(f"/api/regions/{rid}/tokens").json())
    assert any(x["region_id"] == rid for x in
               client.get("/api/recherche", params={"q": "cheval"}).json()["results"])
    # métadonnée de reproductibilité enregistrée
    info = client.get("/api/analyse/info").json()
    assert info["meta"].get("nlp_model") and info["tokens"] >= 1


def test_tokens_effectifs_vue(client, planche, db_path):
    """Vue `tokens_effectifs` : correction humaine vivante prioritaire, sinon auto ;
    une correction `obsolete` retombe sur l'auto. (Indépendant de spaCy.)"""
    import sqlite3
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                            "ocr_texte": "LE CHAT"}).json()["id"]
    raw = sqlite3.connect(db_path)
    raw.row_factory = sqlite3.Row
    # purge les tokens auto que la création de région a pu produire (spaCy dispo) :
    # on veut un cas contrôlé, un seul token à l'ordre 0.
    raw.execute("DELETE FROM tokens WHERE region_id=?", (rid,))
    raw.execute("INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                "VALUES (?, 0, 'chat', 'chat', 'NOUN', '')", (rid,))
    raw.execute("INSERT INTO token_correction (region_id, ordre, forme, pos, etat) "
                "VALUES (?, 0, 'chat', 'PROPN', 'corrige')", (rid,))
    raw.commit()
    eff = raw.execute("SELECT pos, provenance FROM tokens_effectifs WHERE region_id=?",
                      (rid,)).fetchone()
    assert eff["pos"] == "PROPN" and eff["provenance"] == "corrige"   # correction vivante
    raw.execute("UPDATE token_correction SET obsolete=1 WHERE region_id=?", (rid,))
    raw.commit()
    eff = raw.execute("SELECT pos, provenance FROM tokens_effectifs WHERE region_id=?",
                      (rid,)).fetchone()
    assert eff["pos"] == "NOUN" and eff["provenance"] == "auto"       # retombe sur l'auto
    # l'endpoint d'affichage expose bien la valeur effective + la provenance
    api = client.get(f"/api/regions/{rid}/tokens").json()
    assert api and api[0]["provenance"] == "auto" and "pos" in api[0]
    raw.close()


def test_reindex_sans_spacy_preserve_corrections(client, planche, db_path, monkeypatch):
    """Si l'auto ne peut pas être recalculé (spaCy absent → 0 token) sur un texte
    NON vide, on NE re-ancre PAS : la correction humaine garde son état (jamais
    invalidée par la seule absence du moteur)."""
    import sqlite3
    import database
    import pipeline.nlp as nlpmod
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                            "ocr_texte": "LE CHAT"}).json()["id"]
    raw = sqlite3.connect(db_path)
    raw.execute("INSERT INTO token_correction (region_id, ordre, forme, pos, etat, obsolete) "
                "VALUES (?, 0, 'chat', 'PROPN', 'valide', 0)", (rid,))
    raw.commit(); raw.close()
    # simule spaCy indisponible : analyse renvoie ("", []) malgré un texte non vide
    monkeypatch.setattr(nlpmod, "analyse", lambda t: ("", []))
    monkeypatch.setattr(nlpmod, "lemmatise", lambda t: "")
    conn = database.get_connection()
    try:
        database.reindex_region(conn, rid); conn.commit()
        o = conn.execute("SELECT obsolete FROM token_correction WHERE region_id=?",
                         (rid,)).fetchone()["obsolete"]
        assert o == 0   # correction préservée, pas de re-ancrage sur tokenisation absente
    finally:
        conn.close()


@pytest.mark.skipif(not nlp_available(), reason="spaCy / modèle français non installé")
def test_reindex_preserve_et_reancre_corrections(client, planche, db_path):
    """Le reindex NE détruit PAS les corrections, re-ancre `obsolete` selon le texte,
    et le lemme corrigé vivant devient cherchable (FTS enrichi)."""
    import sqlite3
    import database
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                            "ocr_texte": "LES CHATS DORMENT"}).json()["id"]
    conn = database.get_connection()
    try:
        database.reindex_region(conn, rid); conn.commit()
        tok = conn.execute("SELECT ordre, texte FROM tokens WHERE region_id=? "
                           "ORDER BY ordre", (rid,)).fetchone()
        conn.execute("INSERT INTO token_correction (region_id, ordre, forme, lemme, etat) "
                     "VALUES (?, ?, ?, 'zzzunique', 'corrige')",
                     (rid, tok["ordre"], tok["texte"]))
        conn.commit()
        # texte inchangé → correction vivante après reindex
        database.reindex_region(conn, rid); conn.commit()
        assert conn.execute("SELECT obsolete FROM token_correction WHERE region_id=?",
                            (rid,)).fetchone()["obsolete"] == 0
        # FTS enrichi : le lemme corrigé est cherchable
        assert any(x["region_id"] == rid for x in
                   client.get("/api/recherche", params={"q": "zzzunique"}).json()["results"])
        # le texte change → re-ancrage : la correction passe « à revérifier »
        conn.execute("UPDATE regions SET ocr_texte='AUTRE CHOSE ICI' WHERE id=?", (rid,))
        database.reindex_region(conn, rid); conn.commit()
        assert conn.execute("SELECT obsolete FROM token_correction WHERE region_id=?",
                            (rid,)).fetchone()["obsolete"] == 1
    finally:
        conn.close()


def test_lemmatise_resiliente(monkeypatch):
    """Moteur optionnel : une panne spaCy (chargement modèle KO) ne doit jamais
    casser l'indexation/migration/recherche → lemmatise() renvoie "" au lieu de lever."""
    import pipeline.nlp as nlpmod
    if not nlpmod.nlp_available():
        return                                     # rien à éprouver sans spaCy

    def boom():
        raise RuntimeError("chargement spaCy KO")
    monkeypatch.setattr(nlpmod, "_get_nlp", boom)
    assert nlpmod.lemmatise("les chevaux galopaient") == ""


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
