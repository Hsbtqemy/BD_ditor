"""Tests de non-régression, un par bug réellement corrigé.

Chaque test nomme et reproduit le scénario du bug ; ils servent de filet
permanent contre la réintroduction de ces défauts.
"""
import pytest
from conftest import ADMIN, KUMIKO_SAMPLE, direct_query, requires_kumiko
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
def test_lot2_concordance_et_distributions(client, planche):
    """Lot 2 (socle) : concordance grammaticale (occurrences + contexte) et
    distributions par champ, sur les valeurs EFFECTIVES."""
    alb = planche["album_id"]
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                            "ocr_texte": "le gaulois buvait la potion"}).json()["id"]
    # concordance : les VERBES en contexte (« buvait » → boire)
    c = client.get("/api/analyse/concordance", params={"pos": "VERB", "album": alb}).json()
    assert c["count"] >= 1 and all(o["pos"] == "VERB" for o in c["results"])
    o0 = c["results"][0]
    assert o0["region_id"] == rid and o0["lemme"] == "boire"      # valeur effective
    assert o0["ocr_texte"] and o0["album_titre"]                  # contexte multimodal présent
    # au moins un critère requis
    assert client.get("/api/analyse/concordance").status_code == 422
    # filtre par lemme (valeur effective)
    assert client.get("/api/analyse/concordance",
                      params={"lemme": "boire", "album": alb}).json()["count"] >= 1
    # distribution par POS (valeurs effectives)
    f = client.get("/api/analyse/frequences", params={"champ": "pos", "album": alb}).json()
    assert f["champ"] == "pos" and any(r["pos"] == "VERB" for r in f["results"])
    # distribution par morph (ne doit pas planter ; signature UD complète)
    assert "results" in client.get("/api/analyse/frequences",
                                   params={"champ": "morph", "album": alb}).json()
    # champ invalide → 422
    assert client.get("/api/analyse/frequences", params={"champ": "zzz"}).status_code == 422


@pytest.mark.skipif(not nlp_available(), reason="spaCy / modèle français non installé")
def test_lot3_recherche_facette_grammaticale(client, planche):
    """Lot 3 : /api/recherche filtre les régions par critère grammatical (token effectif),
    combinable avec le texte."""
    alb = planche["album_id"]
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                            "ocr_texte": "le gaulois buvait la potion"}).json()["id"]
    # région contenant un VERBE
    r = client.get("/api/recherche", params={"pos": "VERB", "album": alb}).json()
    assert any(x["region_id"] == rid for x in r["results"])
    # critère absent du corpus → la région n'apparaît pas
    r2 = client.get("/api/recherche", params={"pos": "NUM", "album": alb}).json()
    assert all(x["region_id"] != rid for x in r2["results"])
    # combiné avec le texte (FTS + grammaire)
    r3 = client.get("/api/recherche", params={"q": "potion", "pos": "VERB", "album": alb}).json()
    assert any(x["region_id"] == rid for x in r3["results"])

    # --- lot 4.2 : comparaison de deux sous-corpus (bulle vs cartouche) ---
    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "cartouche", "x": 6, "y": 6, "w": 5, "h": 5,
                      "ocr_texte": "le romain parlait"})
    c = client.get("/api/analyse/comparaison",
                   params={"champ": "lemme", "a_album": alb, "b_album": alb,
                           "a_type": "bulle", "b_type": "cartouche"}).json()
    sa = {x["valeur"] for x in c["sur_a"]}
    sb = {x["valeur"] for x in c["sur_b"]}
    assert "boire" in sa and "parler" in sb            # sur-représentés de chaque côté
    assert c["total_a"] >= 1 and c["total_b"] >= 1
    assert client.get("/api/analyse/comparaison", params={"champ": "zzz"}).status_code == 422

    # export CSV du jeu de résultats (mêmes critères)
    exp = client.get("/api/recherche/export.csv", params={"pos": "VERB", "album": alb})
    assert exp.status_code == 200 and "text/csv" in exp.headers["content-type"]
    assert exp.text.startswith("﻿")                                     # BOM (Excel/Windows)
    lignes = exp.text.lstrip("﻿").strip().splitlines()
    # en-tête (la colonne `citation` a été ajoutée par la numérotation éditoriale)
    assert lignes[0] == "album,planche,citation,region_id,type,ocr_texte,note,tags"
    assert any(str(rid) in l for l in lignes[1:])                            # la région exportée


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
    # l'endpoint expose effectif + provenance + drapeau « à revérifier » + override brut
    api = client.get(f"/api/regions/{rid}/tokens").json()
    assert api and api[0]["provenance"] == "auto" and api[0]["pos"] == "NOUN"
    assert api[0]["a_revoir"] == 1 and api[0]["corr_pos"] == "PROPN"   # override (stale) visible
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


@pytest.mark.skipif(not nlp_available(), reason="spaCy / modèle français non installé")
def test_reancrage_par_alignement_pas_de_cascade(client, planche, db_path):
    """Éditer le texte ne casse QUE les corrections des mots réellement changés : un mot
    inchangé qui se DÉCALE garde sa correction (ré-ancrage par alignement, anti-cascade)."""
    import database
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                            "ocr_texte": "le grand chat dort"}).json()["id"]
    conn = database.get_connection()
    try:
        database.reindex_region(conn, rid); conn.commit()
        conn.execute("INSERT INTO token_correction (region_id, ordre, forme, etat, obsolete) "
                     "SELECT region_id, ordre, texte, 'valide', 0 FROM tokens WHERE region_id=?",
                     (rid,))
        conn.commit()
        # insère un mot TÔT → décale tout ce qui suit
        conn.execute("UPDATE regions SET ocr_texte='le tres grand chat dort' WHERE id=?", (rid,))
        database.reindex_region(conn, rid); conn.commit()
    finally:
        conn.close()
    prov = {t["texte"]: t["provenance"]
            for t in client.get(f"/api/regions/{rid}/tokens").json()}
    # mots inchangés (même décalés) → validés conservés ; nouveau mot → auto
    assert prov.get("grand") == "valide" and prov.get("chat") == "valide"
    assert prov.get("dort") == "valide" and prov.get("tres") == "auto"


def test_corriger_token_validation(client, planche, db_path):
    """Garde-fous d'édition : POS hors UPOS → 422 ; position inexistante → 404."""
    import sqlite3
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9}).json()["id"]
    raw = sqlite3.connect(db_path)
    raw.execute("INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                "VALUES (?, 0, 'chat', 'chat', 'NOUN', '')", (rid,))
    raw.commit(); raw.close()
    assert client.put(f"/api/regions/{rid}/tokens/0",
                      json={"pos": "ZZZ"}).status_code == 422      # hors UPOS
    assert client.put(f"/api/regions/{rid}/tokens/9",
                      json={"pos": "VERB"}).status_code == 404      # aucune position 9
    assert client.put(f"/api/regions/{rid}/tokens/0",
                      json={}).status_code == 422                   # correction vide


@pytest.mark.skipif(not nlp_available(), reason="spaCy / modèle français non installé")
def test_corriger_valider_annuler_token(client, planche):
    """Cycle complet : corriger un POS → valider la région → annuler → retour auto."""
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                            "ocr_texte": "LE CHAT"}).json()["id"]
    chat = next(t for t in client.get(f"/api/regions/{rid}/tokens").json()
                if t["texte"] == "chat")
    o = chat["ordre"]
    # corrige le POS en PROPN
    res = client.put(f"/api/regions/{rid}/tokens/{o}", json={"pos": "PROPN"}).json()
    tok = next(t for t in res if t["ordre"] == o)
    assert tok["pos"] == "PROPN" and tok["provenance"] == "corrige"
    # re-corriger le même token (chemin ON CONFLICT) : la valeur est remplacée
    res = client.put(f"/api/regions/{rid}/tokens/{o}", json={"pos": "VERB"}).json()
    assert next(t for t in res if t["ordre"] == o)["pos"] == "VERB"
    # valider la région → tout 'valide', POS corrigé (VERB) conservé
    res = client.post(f"/api/regions/{rid}/grammaire/valider").json()
    assert res and all(t["provenance"] == "valide" for t in res)
    assert next(t for t in res if t["ordre"] == o)["pos"] == "VERB"
    # annuler → ce token repasse en auto
    res = client.delete(f"/api/regions/{rid}/tokens/{o}").json()
    tok = next(t for t in res if t["ordre"] == o)
    assert tok["provenance"] == "auto" and tok["pos"] != "VERB"   # plus d'override


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


@requires_kumiko
def test_resegmentation_preserve_correction_grammaticale(client, album, db_path):
    """Re-segmenter CONSERVE une case portant une correction grammaticale, même sans
    annotation (cf. docs/correction-grammaticale.md §7 — le travail humain n'est pas
    perdu, branche `token_correction` du tri de préservation)."""
    import sqlite3
    p = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("s.png", KUMIKO_SAMPLE.read_bytes(), "image/png")}).json()
    client.post(f"/api/planches/{p['id']}/segmenter")
    case_id = client.get(f"/api/planches/{p['id']}/regions").json()[0]["id"]
    # correction grammaticale sur la case, SANS aucune annotation
    raw = sqlite3.connect(db_path)
    raw.execute("INSERT INTO token_correction (region_id, ordre, forme, pos, etat) "
                "VALUES (?, 0, 'x', 'NOUN', 'corrige')", (case_id,))
    raw.commit(); raw.close()

    client.post(f"/api/planches/{p['id']}/segmenter")  # re-segmentation

    regions = client.get(f"/api/planches/{p['id']}/regions").json()
    assert any(r["id"] == case_id for r in regions)   # préservée par sa seule correction


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


def test_export_csv_neutralise_injection_de_formule(client, album, planche):
    """B7 : une note / OCR commençant par un caractère de formule (= + - @) est préfixée d'une
    apostrophe à l'export CSV (anti-injection tableur), sur les deux exports de l'app."""
    reg = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5,
                            "ocr_texte": "=SUM(1+1)"}).json()
    client.put(f"/api/regions/{reg['id']}/annotation", json={"note": "@evil", "tags": []})
    for url, params in ((f"/api/export/csv", {"album_id": album["id"]}),
                        ("/api/recherche/export.csv", {"q": "SUM"})):
        txt = client.get(url, params=params).text
        assert "'=SUM(1+1)" in txt and "'@evil" in txt          # cellule neutralisée
        assert ",=SUM(1+1)" not in txt and ",@evil" not in txt  # jamais brute en tête de cellule


def test_sauvegarde_echec_inattendu_503(client, monkeypatch):
    """B8 : un échec de make_backup hors contention (disque plein…) → 503 propre, pas 500 brut."""
    import main
    monkeypatch.setattr(main, "make_backup",
                        lambda: (_ for _ in ()).throw(RuntimeError("disque plein")))
    assert client.get("/api/sauvegarde").status_code == 503


def test_sauvegarde_base_occupee_409(client, monkeypatch):
    """B8 : une OperationalError « locked » file au handler global → 409 (réessayez), pas 503."""
    import sqlite3
    import main
    monkeypatch.setattr(main, "make_backup",
                        lambda: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
    assert client.get("/api/sauvegarde").status_code == 409


def test_album_titre_vide_refuse_422(client):
    """B9 : créer OU éditer un album avec un titre vide / blanc → 422 ; un titre est nettoyé."""
    assert client.post("/api/albums", json={"titre": ""}).status_code == 422
    assert client.post("/api/albums", json={"titre": "   "}).status_code == 422
    a = client.post("/api/albums", json={"titre": "  Tintin  "}).json()
    assert a["titre"] == "Tintin"                               # strip appliqué
    assert client.put(f"/api/albums/{a['id']}", json={"titre": " "}).status_code == 422


def test_upgrade_pre_v16_ne_casse_pas_sur_index_activite(tmp_path, monkeypatch):
    """Bug : `init_db()` posait `idx_regions_activite ON regions(activite_id)` dans
    SCHEMA_SQL, exécuté AVANT `_migrate`. Sur toute base pré-v16 (colonne pas encore
    ajoutée), le démarrage plantait sur « no such column: activite_id ». Correctif :
    l'index est créé DANS `_migrate`, après l'ALTER. On reconstitue une base v15 avec
    une table `regions` d'ancienne forme et on vérifie que l'upgrade complet passe."""
    import sqlite3
    import database

    vieille = tmp_path / "pre_v16.sqlite"
    conn = sqlite3.connect(vieille)
    conn.executescript(
        "CREATE TABLE regions ("           # forme pré-v16 : PAS de colonne activite_id
        "  id INTEGER PRIMARY KEY, planche_id INTEGER, parent_id INTEGER, type TEXT,"
        "  x INTEGER, y INTEGER, w INTEGER, h INTEGER, ordre INTEGER,"
        "  ocr_texte TEXT, source TEXT, date_creation TEXT);"
        "PRAGMA user_version = 15;")
    conn.commit()
    conn.close()

    monkeypatch.setattr(database, "DB_PATH", vieille)
    database.init_db()                                          # ne doit PAS lever

    check = sqlite3.connect(vieille)
    try:
        cols = {r[1] for r in check.execute("PRAGMA table_info(regions)")}
        assert "activite_id" in cols                            # colonne posée par migration
        assert check.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' "
            "AND name='idx_regions_activite'").fetchone()       # index créé APRÈS l'ALTER
        assert check.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    finally:
        check.close()


def test_lot_mort_ne_se_declare_pas_termine(monkeypatch):
    """Un lot tué hors du `try` par passe s'annonçait « terminé », 0/0, sans erreur.

    Deux lectures SQLite échappent à ce `try` — l'ouverture de la connexion et la
    relecture du verrou — donc deux « database is locked » possibles, exactement ce que
    le WAL et le 409 d'`OperationalError` gèrent partout ailleurs. Le `finally` posait
    alors un succès AFFIRMÉ sur un lot qui n'avait rien fait. Un statut bloqué se
    remarque ; un succès faux ne se remarque jamais.

    Mesuré le 2026-08-31 : `statut=termine done=0/3 erreurs=[]`.
    """
    import sqlite3
    import time
    from pipeline import jobs

    def verrou_casse(conn, planche_id):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(jobs, "_est_verrouillee", verrou_casse)
    jid = jobs.start_job(["segmenter"], [1, 2, 3])["id"]
    for _ in range(100):
        time.sleep(0.05)
        snap = jobs.snapshot(jid)
        if snap["status"] != "en_cours":
            break

    assert snap["status"] == "echec", snap          # et surtout PAS « termine »
    assert snap["done"] == 0                        # rien n'a été traité, le compte le dit
    assert len(snap["errors"]) == 1                 # la panne est NOMMÉE, pas seulement comptée
    assert "locked" in snap["errors"][0]["erreur"]


# --------------------------------------------------------------------------- #
# B6 (AUDIT-1) — une passe automatique n'a pas d'intention
# --------------------------------------------------------------------------- #
def test_avancer_statut_ne_recule_jamais(client, planche):
    """`database.avancer_statut` avance ou ne fait rien ; il ne redescend pas.

    La règle vit à UN endroit et tire son ordre de `STATUTS` : un `CASE WHEN` en SQL
    recopierait cet ordre, et deux copies finissent par diverger.
    """
    import database
    from config import STATUTS

    pid = planche["id"]
    with database.get_connection() as conn:
        assert database.avancer_statut(conn, pid, "segmentee") == "segmentee"   # importee →
        assert database.avancer_statut(conn, pid, "segmentee") == "segmentee"   # idempotent
        conn.execute("UPDATE planches SET statut = 'annotee' WHERE id = ?", (pid,))
        assert database.avancer_statut(conn, pid, "segmentee") == "annotee"     # PAS de recul
        assert conn.execute("SELECT statut FROM planches WHERE id = ?",
                            (pid,)).fetchone()["statut"] == "annotee"
        # Une cible hors vocabulaire est une erreur de programmation, pas un no-op.
        with pytest.raises(ValueError):
            database.avancer_statut(conn, pid, "inconnu")
        # Une planche absente aussi : sans cette garde l'UPDATE serait vide et la fonction
        # renverrait `cible`, annonçant un avancement qui n'a pas eu lieu.
        with pytest.raises(ValueError):
            database.avancer_statut(conn, 10**9, "segmentee")
        # Un statut COURANT inconnu (valeur héritée) est traité comme le plus bas : on
        # avance, ce qui est le comportement d'avant le correctif — pas de surprise.
        conn.execute("UPDATE planches SET statut = 'zzz' WHERE id = ?", (pid,))
        assert database.avancer_statut(conn, pid, STATUTS[0]) == STATUTS[0]
        conn.commit()


def test_resegmenter_une_planche_annotee_ne_la_fait_pas_regresser(client, planche, monkeypatch):
    """Re-segmenter une planche `annotee` la faisait retomber à `segmentee`.

    Le travail humain restait en base — seule sa DÉCLARATION d'avancement était effacée, et
    rien ne le signalait : `statut` ne commande rien dans l'application, il ne nourrit que
    la barre d'avancement du corpus. Le seul symptôme était donc un tableau de bord qui
    régressait tout seul, ce qu'on attribue à n'importe quoi sauf à la segmentation.

    `run_kumiko` est simulé : le moteur n'a rien à voir avec le défaut, et le test doit
    tourner partout — sans quoi la non-régression ne vaudrait que sur les machines qui ont
    Kumiko, c'est-à-dire nulle part en intégration.
    """
    import database
    import pipeline.segmentation as seg

    monkeypatch.setattr(seg, "run_kumiko",
                        lambda p: {"size": [100, 100],
                                   "panels": [[10, 10, 40, 40], [60, 10, 30, 30]]})
    pid = planche["id"]
    with database.get_connection() as conn:
        conn.execute("UPDATE planches SET statut = 'annotee' WHERE id = ?", (pid,))
        conn.commit()

    with database.get_connection() as conn:
        res = seg.segment_planche(conn, pid)
        conn.commit()
        row = conn.execute("SELECT statut, date_segmentation FROM planches WHERE id = ?",
                           (pid,)).fetchone()

    assert res["nb_cases"] == 2                      # la segmentation a bien eu lieu...
    assert row["statut"] == "annotee", row["statut"]  # ...sans effacer l'avancement déclaré
    assert res["statut"] == "annotee"                 # et la réponse dit l'EFFECTIF
    # La DATE, elle, est un fait : la planche vient d'être segmentée, donc elle est posée.
    # Les écrire ensemble était tout le défaut.
    assert row["date_segmentation"]


def test_resegmenter_une_planche_importee_l_avance_bien(client, planche, monkeypatch):
    """Le pendant du précédent, sans lequel il ne prouverait rien.

    Un correctif qui n'écrirait plus JAMAIS le statut passerait le test de non-régression
    ci-dessus avec brio. Il faut donc vérifier aussi que l'avancement normal a toujours lieu.
    """
    import database
    import pipeline.segmentation as seg

    monkeypatch.setattr(seg, "run_kumiko",
                        lambda p: {"size": [100, 100], "panels": [[10, 10, 40, 40]]})
    with database.get_connection() as conn:
        assert conn.execute("SELECT statut FROM planches WHERE id = ?",
                            (planche["id"],)).fetchone()["statut"] == "importee"
        res = seg.segment_planche(conn, planche["id"])
        conn.commit()
        assert conn.execute("SELECT statut FROM planches WHERE id = ?",
                            (planche["id"],)).fetchone()["statut"] == "segmentee"
    assert res["statut"] == "segmentee"


def test_ordre_de_lecture_pas_d_agglomeration_transitive():
    """O1 (AUDIT-1) — les rangées ne dérivent PAS de proche en proche.

    Le constat annonçait qu'un escalier de cases s'agglomérerait transitivement, la boucle
    élargissant `row["top"]` par `min()` à chaque ajout. Mesuré le 2026-09-01 : c'est faux,
    et structurellement. Les items sont triés par `y` CROISSANT, donc `_y(b) >= row["top"]`
    toujours — le `min()` ne peut jamais abaisser `top`, il est sans effet. La fenêtre
    d'acceptation reste figée sur le premier item de la rangée.

    Ce test verrouille la sémantique plutôt que le constat : il échouerait si quelqu'un
    remplaçait ce `min()` par une moyenne ou un `max()`, ou retirait le tri préalable —
    trois façons d'introduire pour de bon la dérive que l'audit redoutait.

    `x` DÉCROÎT quand `y` croît, à dessein : avec `x` croissant, « une seule rangée » et
    « une rangée par case » donnent le MÊME ordre, et le test ne prouverait rien. C'est
    l'erreur commise à la première mesure.
    """
    from pipeline.ordering import reading_order

    def escalier(pas):
        return [{"id": i, "x": (5 - i) * 200, "y": i * pas, "w": 100, "h": 100}
                for i in range(6)]

    # L'INVARIANT d'abord, indépendant de la valeur de la tolérance : un escalier dont
    # chaque marche tient dans la tolérance, mais dont l'amplitude totale la dépasse
    # largement, ne doit JAMAIS former une rangée unique. C'est lui qui casse le jour où
    # `top` suivrait le dernier item au lieu de rester l'ancre — et il survit à un simple
    # réglage du seuil, contrairement aux ordres exacts ci-dessous.
    assert [b["id"] for b in reading_order(escalier(36))] != [5, 4, 3, 2, 1, 0], (
        "l'escalier s'est agglomeré en une seule rangée : la fenêtre d'acceptation dérive")

    # Puis les ordres EXACTS, qui documentent le comportement actuel avec tol = 0,4 ×
    # hauteur médiane = 40. Pas de 36 : chaque case est dans la tolérance de la précédente,
    # mais pas de celle qui OUVRE la rangée → des paires. Ces trois-là bougeront si l'on
    # règle le seuil, et c'est voulu : un changement de seuil est un changement de rendu.
    assert [b["id"] for b in reading_order(escalier(36))] == [1, 0, 3, 2, 5, 4]
    # Au-delà de la tolérance : une rangée par case, ordre descendant.
    assert [b["id"] for b in reading_order(escalier(41))] == [0, 1, 2, 3, 4, 5]
    # Bien en deçà : une seule rangée, donc triée de gauche à droite.
    assert [b["id"] for b in reading_order(escalier(3))] == [5, 4, 3, 2, 1, 0]


def test_resegmentation_est_un_point_fixe(client, planche, monkeypatch):
    """S6 (AUDIT-1) — re-segmenter N fois ne dégrade rien après la première passe.

    La propriété TIENT (mesurée le 2026-09-01 sur cinq passages) ; elle n'était simplement
    jamais vérifiée, et c'est le genre d'invariant qui casse en silence — on ne relance pas
    une segmentation pour regarder ce qui a disparu.

    Quatre dimensions, et il faut les quatre : l'annotation humaine survit ; la région
    enfant océrisée survit SANS se dupliquer (le transfert par géométrie pourrait aussi
    bien en fabriquer une par passe) ; l'index FTS ne laisse aucune ligne orpheline ; et la
    géométrie se stabilise dès la deuxième passe.

    Ce que le test n'assère pas, à dessein : les IDENTIFIANTS changent à chaque passage —
    la case annotée n'est pas conservée, son annotation est transférée à la nouvelle case
    par recouvrement, puis l'ancienne est supprimée. C'est inhérent au « supprimer puis
    recréer » et ça n'entame aucune des quatre dimensions ci-dessus. Conséquence réelle en
    revanche, et non traitée : un deep-link `?region=N` partagé ne survit pas à une
    re-segmentation de sa planche.
    """
    import database
    import pipeline.segmentation as seg

    monkeypatch.setattr(seg, "run_kumiko", lambda p: {
        "size": [1000, 1000], "panels": [[10, 10, 400, 400], [500, 10, 400, 400]]})
    pid = planche["id"]

    def photo(conn):
        """L'état qui doit se stabiliser — tout sauf les id, qui tournent par construction."""
        return {
            "cases": [(r["x"], r["y"], r["w"], r["h"], r["ordre"]) for r in conn.execute(
                "SELECT x,y,w,h,ordre FROM regions WHERE planche_id=? AND type='case' "
                "ORDER BY ordre", (pid,))],
            "notes": sorted(r[0] for r in conn.execute(
                "SELECT a.note FROM annotations a JOIN regions r ON r.id = a.region_id "
                "WHERE r.planche_id=?", (pid,))),
            "textes": sorted(r[0] for r in conn.execute(
                "SELECT ocr_texte FROM regions WHERE planche_id=? AND ocr_texte IS NOT NULL",
                (pid,))),
            "fts_orphelines": conn.execute(
                "SELECT COUNT(*) FROM recherche "
                "WHERE region_id NOT IN (SELECT id FROM regions)").fetchone()[0],
        }

    with database.get_connection() as conn:
        seg.segment_planche(conn, pid)
        case = conn.execute("SELECT id FROM regions WHERE planche_id=? AND type='case' "
                            "ORDER BY x", (pid,)).fetchone()["id"]
        conn.execute("INSERT INTO annotations(region_id, note) VALUES(?, 'NOTE HUMAINE')",
                     (case,))
        cur = conn.execute("INSERT INTO regions(planche_id,parent_id,type,x,y,w,h,ordre,"
                           "source,ocr_texte) VALUES(?,?,'bulle',30,30,50,50,1,'manuel',"
                           "'TEXTE OCR')", (pid, case))
        # INDEXER pour de bon, sinon l'assertion sur les lignes FTS orphelines ne mesure
        # rien : une insertion SQL brute ne peuple pas `recherche`, et « 0 orpheline »
        # serait alors vrai d'un index VIDE. Vérifié par mutation le 2026-09-01 — sans ces
        # deux appels, retirer `unindex_region` de la segmentation ne fait pas rougir le
        # test.
        database.reindex_region(conn, cur.lastrowid)
        database.reindex_region(conn, case)
        # La SECONDE case porte du texte SANS annotation : indexée, donc, mais non
        # préservée. C'est le seul chemin qui atteigne le `unindex_region` de la
        # suppression — l'autre, dans le transfert d'annotations, désindexe déjà la case
        # dont la note s'en va. Sans cette case-ci, « 0 ligne orpheline » est vrai d'un
        # index que la segmentation n'a jamais eu à nettoyer, et retirer la désindexation
        # ne fait rougir personne. Vérifié par mutation le 2026-09-01.
        autre = conn.execute("SELECT id FROM regions WHERE planche_id=? AND type='case' "
                             "AND id != ?", (pid, case)).fetchone()["id"]
        conn.execute("UPDATE regions SET ocr_texte = 'TEXTE SUR LA CASE' WHERE id = ?",
                     (autre,))
        database.reindex_region(conn, autre)
        conn.commit()

        seg.segment_planche(conn, pid)          # 2e passage : le point de référence
        conn.commit()
        reference = photo(conn)
        assert reference["notes"] == ["NOTE HUMAINE"], reference
        assert reference["textes"] == ["TEXTE OCR"], reference
        assert len(reference["cases"]) == 2, reference

        # Quatre passages de plus. Cette boucle ÉNONCE la propriété demandée — le point
        # fixe — mais il faut dire ce qu'elle vaut : aucune mutation d'une seule ligne
        # essayée le 2026-09-01 ne l'a fait rougir SEULE, les défauts introduits étant
        # tous rattrapés par les assertions ci-dessus dès la deuxième passe. Elle garde un
        # sens propre — une dégradation PROGRESSIVE, qui n'apparaîtrait qu'au troisième
        # ou quatrième passage — mais ce n'est pas elle qui tient le filet aujourd'hui,
        # et prétendre le contraire serait le genre d'affirmation non mesurée que ce
        # chantier passe son temps à corriger.
        for passage in range(3, 7):
            seg.segment_planche(conn, pid)
            conn.commit()
            assert photo(conn) == reference, f"dérive au passage {passage}"
        assert reference["fts_orphelines"] == 0


# --------------------------------------------------------------------------- #
# AUDIT-2 — constats mineurs, corrigés le 2026-09-04
# --------------------------------------------------------------------------- #
def test_annee_aberrante_est_refusee(client):
    """E3 — `annee` acceptait n'importe quel entier, donc 999999.

    Le champ est *legacy* (la date précise vit dans `date_edition`), ce qui le rend
    d'autant plus facile à saisir de travers : personne ne le relit. Les bornes sont
    larges à dessein — il ne s'agit pas de policer l'histoire de l'édition, mais
    d'écarter l'absurde avant qu'il n'entre en base, où il resterait.
    """
    for aberrante in (999999, 0, -1, 1399, 2201):
        r = client.post("/api/albums", json={"titre": "Borne", "annee": aberrante})
        assert r.status_code == 422, f"{aberrante} aurait dû être refusée"

    ok = client.post("/api/albums", json={"titre": "Borne", "annee": 2019})
    assert ok.status_code == 201 and ok.json()["annee"] == 2019
    aid = ok.json()["id"]

    # La modification est bornée comme la création : une seule des deux portes
    # gardée laisserait l'autre grande ouverte.
    assert client.put(f"/api/albums/{aid}", json={"annee": 999999}).status_code == 422
    assert client.put(f"/api/albums/{aid}", json={"annee": 2020}).status_code == 200

    # Et l'absence reste permise : le champ est facultatif, pas obligatoire.
    assert client.post("/api/albums", json={"titre": "Sans année"}).status_code == 201


def test_chemin_hors_data_dir_est_nomme(tmp_path):
    """G5 — `_rel_posix` laissait remonter le `ValueError` nu de `relative_to`.

    Latent : aucune route ne laisse choisir la source d'un import. Mais le message de
    `relative_to` ne nomme ni le rôle des deux chemins ni la règle enfreinte, et c'est
    le jour où l'import depuis un dossier fourni existera que ce message comptera.
    """
    from config import DATA_DIR
    from pipeline.ingest import _rel_posix

    dedans = DATA_DIR / "corpus" / "album_1" / "planche.tif"
    assert _rel_posix(dedans) == "corpus/album_1/planche.tif"

    dehors = tmp_path / "ailleurs" / "planche.tif"
    with pytest.raises(ValueError) as exc:
        _rel_posix(dehors)
    message = str(exc.value)
    assert "DATA_DIR" in message
    assert str(DATA_DIR) in message, "le message doit nommer la racine attendue"
    assert "RELATIFS" in message, "il doit dire POURQUOI, pas seulement que c'est faux"


# `_sans_terme_cherchable` est une APPROXIMATION du tokenizer `unicode61` : elle lit les
# catégories Unicode L*/N* via `isalnum()`, là où la vérité vit dans SQLite. La lire au
# lieu de la mesurer serait exactement la faute que ce chantier corrige — dire à quelqu'un
# « votre requête ne cherche rien » alors qu'elle cherchait quelque chose.
PONCTUATION_SEULE = ["???", "...", "++", "!!!", "«»", "— —", "()", "@#$", "  ?  ", "…"]


def test_ce_qui_est_declare_incherchable_ne_trouve_vraiment_rien(client, planche):
    """C2 — le corpus contient les caractères À LA LETTRE, et pourtant rien ne sort.

    C'est la moitié du test qui compte : si l'une de ces requêtes trouvait quelque chose,
    l'écran annoncerait « aucun terme cherchable » à quelqu'un qui vient d'en chercher un.
    Le semis est donc hostile — on cherche la ponctuation dans un texte qui la contient.
    """
    from routes.recherche import _sans_terme_cherchable

    texte = "Pourquoi ??? Mais... « oui » — non (peut-être) @#$ ++ !!!"
    rid = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "bulle", "x": 0, "y": 0, "w": 10, "h": 10,
                            "ocr_texte": texte}, headers=ADMIN).json()["id"]
    assert rid

    # Le décor est cherchable : sans cette assertion, un index vide rendrait tout le
    # reste vrai pour la mauvaise raison.
    amorce = client.get("/api/recherche", params={"q": "pourquoi"}, headers=ADMIN).json()
    assert amorce["count"] >= 1, "le semis n'est pas indexé — le test ne mesurerait rien"
    assert amorce["sans_terme"] is False

    for q in PONCTUATION_SEULE:
        assert _sans_terme_cherchable(q), f"{q!r} devrait être déclaré incherchable"
        r = client.get("/api/recherche", params={"q": q}, headers=ADMIN).json()
        assert r["sans_terme"] is True, q
        assert r["count"] == 0, (
            f"{q!r} est annoncé incherchable mais le moteur trouve {r['count']} "
            "résultat(s) : l'explication affichée serait un mensonge")

    # Et avec un FILTRE par-dessus, qui lui trouverait quelque chose. L'écran ne montre
    # son explication que sur un résultat VIDE : si la clause plein texte n'était pas
    # combinée en ET, la personne recevrait des résultats sans jamais apprendre que son
    # texte a été ignoré. C'est le cas de bord que la relecture a soulevé, et il tient
    # parce que `_recherche_rows` ajoute `recherche MATCH ?` aux autres conditions.
    avec_filtre = client.get("/api/recherche",
                             params={"q": "???", "album": planche["album_id"]},
                             headers=ADMIN).json()
    assert avec_filtre["sans_terme"] is True
    assert avec_filtre["count"] == 0, (
        "un filtre ne doit pas rattraper une requête sans terme cherchable : sinon "
        "l'explication ne s'affiche jamais et le texte saisi est ignoré en silence")


def test_une_requete_ordinaire_n_est_jamais_declaree_incherchable(client, planche):
    """L'autre moitié, et elle est épinglée au moteur elle aussi.

    Une règle trop LARGE — « contient de la ponctuation » au lieu de « n'en contient
    que » — est parfaitement plausible et dirait « aucun terme cherchable » à qui vient
    d'en chercher un. Comparer à une liste attendue l'attrape ; le faire confirmer par
    le moteur l'attrape pour la BONNE raison, en montrant ce que la personne aurait
    trouvé pendant qu'on lui expliquait qu'il n'y avait rien à trouver.
    """
    from routes.recherche import _sans_terme_cherchable

    texte = "Pourquoi ??? Mais... « oui » — non (peut-être) l'homme 1984"
    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "bulle", "x": 0, "y": 0, "w": 10, "h": 10,
                      "ocr_texte": texte}, headers=ADMIN)

    # Ces requêtes-là portent un terme, et le corpus le contient : le moteur DOIT
    # rendre quelque chose, sans quoi l'assertion « pas incherchable » ne pèse rien.
    for q in ["pourquoi", "oui", "non", "peut-être", "l'homme", "1984", "?pourquoi?"]:
        assert not _sans_terme_cherchable(q), f"{q!r} porte un terme cherchable"
        r = client.get("/api/recherche", params={"q": q}, headers=ADMIN).json()
        assert r["sans_terme"] is False, q
        assert r["count"] >= 1, (
            f"{q!r} est cherchable et présent dans le corpus, mais le moteur ne trouve "
            "rien : l'un des deux se trompe, et le test ne saurait pas lequel")

    # Accents et casse : c'est du français, et le tokenizer les traite comme des lettres.
    for q in ["ÉTÉ", "à", "c3po"]:
        assert not _sans_terme_cherchable(q), f"{q!r} porte un terme cherchable"

    # Requête VIDE : ce n'est pas « incherchable », c'est « rien demandé ». L'écran a
    # déjà son invite pour ce cas, et la confondre avec un refus serait un contresens.
    for q in ["", "   "]:
        assert not _sans_terme_cherchable(q), f"{q!r} : requête vide, pas requête refusée"


def test_un_env_hors_de_deploy_reste_ignore_par_git():
    """`.gitignore` n'ignorait `.env` que sous `deploy/`, et ce dépôt est PUBLIC.

    Le 2026-09-05, une commande destinée à `deploy/.env` a été lancée depuis la racine
    du dépôt : les identifiants SMTP se sont écrits dans `./.env`. Rien ne l'a signalé.
    Git le voyait comme un fichier neuf ordinaire — donc candidat à un `git add -A` — et
    la pile a simplement démarré sans SMTP, si bien que l'erreur s'est manifestée comme
    une panne de courriel et non comme une fuite de secret.

    Le motif est maintenant `.env` SANS chemin, ce qui l'attrape à toute profondeur. Ce
    test épingle la forme du motif plutôt que d'appeler `git check-ignore` : la suite
    tourne aussi dans l'image Docker (QA-5), où git n'est pas installé — un test qui s'y
    skipperait ne garderait rien là où la garde compte le plus.
    """
    from pathlib import Path

    lignes = [l.strip() for l in
              (Path(__file__).resolve().parent.parent / ".gitignore")
              .read_text(encoding="utf-8").splitlines()]

    assert ".env" in lignes, (
        "`.gitignore` doit porter le motif nu `.env` : avec un chemin devant, un "
        "fichier de secrets écrit ailleurs que là où on l'attendait devient "
        "committable, et rien ne le dit")
    assert "deploy/.env.example" not in lignes, (
        "le gabarit doit rester VERSIONNÉ : c'est lui qui documente les clés à "
        "remplir, et l'ignorer priverait le déploiement de sa seule référence")


def _ignore_par_gitignore(chemin, lignes):
    """Le verdict de `.gitignore` sur un chemin, sans appeler git.

    On applique les motifs DANS L'ORDRE, le dernier qui correspond l'emporte, et `!`
    nie — c'est la règle de git, et c'est tout ce qu'emploient les motifs concernés.
    Un motif contenant une barre est ancré au dépôt ; un motif nu vaut à toute
    profondeur, d'où la comparaison sur le nom de fichier seul.

    C'est une APPROXIMATION assumée (ni `**`, ni motifs de dossier), et elle est
    préférée à `git check-ignore` pour la raison écrite au-dessus : la suite tourne
    aussi dans l'image Docker (QA-5), où git n'est pas installé. Un test qui s'y
    skipperait ne garderait rien là où la garde compte le plus.
    """
    import fnmatch

    verdict = False
    for ligne in lignes:
        if not ligne or ligne.startswith("#"):
            continue
        nie = ligne.startswith("!")
        motif = ligne[1:] if nie else ligne
        cibles = [chemin] if "/" in motif.rstrip("/") else [chemin, chemin.split("/")[-1]]
        if any(fnmatch.fnmatchcase(c, motif) for c in cibles):
            verdict = not nie
    return verdict


def test_les_copies_de_retour_arriere_des_fichiers_de_secrets_sont_ignorees():
    """Une copie suffixée d'un fichier de secrets atterrissait dans l'arbre d'un dépôt PUBLIC.

    La procédure d'exploitation fait créer une copie AVANT toute édition — « d'abord,
    toujours » —, et c'est elle qui a rétabli le service le 2026-09-06. Mais les motifs
    de `.gitignore` visaient des noms EXACTS (`users_database.yml`, `.env`), si bien que
    `users_database.yml.avant` ou `.env.avec-smtp` passaient au travers.

    Deux conséquences, et la seconde est la plus coûteuse. `deployer.sh` refuse un arbre
    sale : trois de ces fichiers ont bloqué un déploiement le 2026-09-06 au soir, un
    quatrième le 2026-09-07 — et le refus accuse « quelqu'un a modifié des fichiers en
    place », ce qui envoie chercher une édition sauvage qui n'existe pas. Surtout, un
    `git add -A` les aurait committés : des condensés de mots de passe dans un dépôt
    public.

    Le remède écrit le 2026-09-06 était une étape 5 — penser à supprimer la copie. Or on
    crée ces copies exactement les soirs où l'on ne pense plus à rien : celui-là, le
    portail était tombé depuis six minutes. Une discipline n'est pas une garde.
    """
    from pathlib import Path

    lignes = [l.strip() for l in
              (Path(__file__).resolve().parent.parent / ".gitignore")
              .read_text(encoding="utf-8").splitlines()]

    for chemin in ["deploy/authelia/users_database.yml",
                   "deploy/authelia/users_database.yml.avant",
                   "deploy/authelia/users_database.avant.yml",
                   "deploy/authelia/configuration.yml.avant",
                   ".env", "deploy/.env", ".env.avec-smtp", "deploy/.env.avant"]:
        assert _ignore_par_gitignore(chemin, lignes), (
            f"{chemin} doit être ignoré : il porte des secrets, ce dépôt est PUBLIC, "
            f"et tant qu'il traîne dans l'arbre il bloque aussi tout déploiement")

    # L'exception est explicite, et elle doit le RESTER : un motif large sans négation
    # emporterait les gabarits, qui sont la seule documentation des clés à remplir.
    for chemin in ["deploy/authelia/users_database.example.yml",
                   "deploy/.env.example",
                   "deploy/authelia/configuration.yml"]:
        assert not _ignore_par_gitignore(chemin, lignes), (
            f"{chemin} doit rester VERSIONNÉ : c'est un gabarit ou une configuration "
            f"sans secret, et l'ignorer priverait le déploiement de sa référence")


def test_un_fichier_de_comptes_illisible_est_signale_et_non_fatal(tmp_path, monkeypatch):
    """`verifier_deploiement.py` s'écrasait sur un `users_database.yml` durci en 600.

    Le 2026-09-06, durcir ce fichier — qui porte un hash de mot de passe — a fait
    remonter une `PermissionError` non rattrapée depuis `controle_config`. Le contrôle
    ne s'est pas contenté d'échouer : il a tué la course entière, donc les vérifications
    suivantes ET le déploiement. Un durcissement légitime ne doit pas ressembler à une
    panne, et surtout pas se comporter en interrupteur placé en amont des autres gardes
    (même famille que l'échec `openpyxl` d'ARCH-2, et que QA-6).

    Authelia lit le fichier parce que son conteneur tourne en root ; ce script, non — il
    s'exécute sous le compte de l'opérateur. Les deux lecteurs n'ont pas les mêmes droits,
    et c'est ce qui avait été oublié.
    """
    import importlib.util
    from pathlib import Path

    source = Path(__file__).resolve().parent.parent / "deploy" / "verifier_deploiement.py"
    if not source.exists():
        pytest.skip(
            "deploy/ est exclu du contexte de build (.dockerignore) : ce test ne tourne "
            "QUE sur la machine de développement. Son skip dans l'image N'EST PAS une "
            "couverture — cf. QA-6, « un skip se lit comme un succès »")

    spec = importlib.util.spec_from_file_location("vd_regression", source)
    vd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vd)

    env = tmp_path / ".env"
    env.write_text("BD_DOMAINE=bd.exemple.fr\nAUTH_DOMAINE=auth.exemple.fr\n"
                   "COOKIE_DOMAINE=exemple.fr\n", encoding="utf-8")

    # `ici` vaut le dossier du script, pas celui de `--config` : on substitue donc les
    # accès au fichier des comptes plutôt que d'en fabriquer un, ce qui rend le test
    # indépendant de ce que contient la machine.
    vrai_exists, vrai_read = Path.exists, Path.read_text

    def exists(self):
        return True if self.name == "users_database.yml" else vrai_exists(self)

    def read_text(self, *a, **k):
        if self.name == "users_database.yml":
            raise PermissionError(13, "Permission denied", str(self))
        return vrai_read(self, *a, **k)

    monkeypatch.setattr(Path, "exists", exists)
    monkeypatch.setattr(Path, "read_text", read_text)

    problemes = vd.controle_config(str(env))       # ne doit pas lever
    assert problemes == [], (
        "un fichier de comptes illisible n'est pas un défaut de configuration : "
        f"le contrôle l'a pourtant compté comme tel ({problemes})")


def test_le_referent_manquant_avertit_sans_bloquer(tmp_path, monkeypatch):
    """Le référent absent est SIGNALÉ, jamais compté comme un problème.

    AUTH-4 pose un référent d'instance pour que le bandeau de portée vide nomme quelqu'un.
    Constaté en production le 2026-09-06 : la fonctionnalité était livrée depuis des jours
    et jamais configurée, si bien que le premier arrivant lisait « demandez à un
    administrateur » sans savoir à qui écrire. Rien ne le signalait au moment où c'était
    devenu vrai — c'est-à-dire à l'arrivée du deuxième compte.

    La propriété que ce test verrouille n'est PAS l'avertissement, c'est son caractère non
    bloquant. `deployer.sh` appelle ce contrôle avant chaque mise en service, sous `set -e`
    : le compter comme un problème refuserait un déploiement pour un nom manquant, alors
    qu'un déploiement est justement ce qui permet de le poser. C'est aussi la famille de
    défauts qu'ARCH-2 et QA-6 ont nommée — un échec dur sur une condition légitime.
    """
    import contextlib
    import importlib.util
    import io
    from pathlib import Path

    source = Path(__file__).resolve().parent.parent / "deploy" / "verifier_deploiement.py"
    if not source.exists():
        pytest.skip(
            "deploy/ est exclu du contexte de build (.dockerignore) : ce test ne tourne "
            "QUE sur la machine de développement. Son skip dans l'image N'EST PAS une "
            "couverture — cf. QA-6, « un skip se lit comme un succès »")

    spec = importlib.util.spec_from_file_location("vd_referent", source)
    vd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vd)

    env = tmp_path / ".env"
    env.write_text("BD_DOMAINE=bd.exemple.fr\nAUTH_DOMAINE=auth.exemple.fr\n"
                   "COOKIE_DOMAINE=exemple.fr\n", encoding="utf-8")

    deux_comptes = ("users:\n  a:\n    password: $argon2id$un\n"
                    "  b:\n    password: $argon2id$deux\n")
    vrai_exists, vrai_read = Path.exists, Path.read_text
    monkeypatch.setattr(Path, "exists",
                        lambda self: True if self.name == "users_database.yml"
                        else vrai_exists(self))
    monkeypatch.setattr(Path, "read_text",
                        lambda self, *a, **k: deux_comptes
                        if self.name == "users_database.yml" else vrai_read(self, *a, **k))

    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        problemes = vd.controle_config(str(env))
    sortie = tampon.getvalue()

    assert "référent" in sortie and "non déclaré" in sortie, (
        f"deux comptes sans référent : rien n'a été signalé.\n{sortie}")
    assert problemes == [], (
        "l'absence de référent a été comptée comme un PROBLÈME : le contrôle rendra "
        f"non nul et `deployer.sh` refusera de déployer ({problemes})")


def _fichiers_documentaires():
    """Les fichiers versionnés où une commande peut être RECOPIÉE par quelqu'un.

    `deploy/` est absent de l'image de test (`.dockerignore` l'exclut entier, parce que
    `users_database.yml` y porte un condensé). La garde ne s'en trouve pas creuse : elle
    compare les mentions ENTRE ELLES plutôt qu'à une référence unique, donc elle garde
    `docs/` là-bas et tout le reste ici.
    """
    from pathlib import Path

    racine = Path(__file__).resolve().parent.parent
    vus = []
    for motif in ("*.md", "docs/*.md", "deploy/docker-compose.yml",
                  "deploy/.env.example", "deploy/authelia/*.example.yml"):
        vus.extend(sorted(racine.glob(motif)))
    return vus


def test_une_seule_version_d_authelia_est_documentee():
    """Quatre fichiers nommaient `authelia:4.38` alors que l'instance sert `4.39.22`.

    `INFRA-9` a épinglé la version EXACTE le 2026-09-06, et la raison est écrite dans le
    compose : la flottante avait laissé l'instance vieillir en silence, donc monter devient
    un GESTE et « l'écart doit se voir plutôt que se creuser ». L'écart s'est creusé
    ailleurs — dans les documents, qui ont continué de nommer la version quittée. Épingler
    rend la version décidée à UN endroit ; rien n'obligeait les quatre autres à suivre.

    Ce que ça coûte n'est pas cosmétique : `docs/exploitation.md` portait DEUX procédures
    d'ajout de compte, et celle qui nommait `4.38` était aussi celle qui taisait le préfixe
    `Digest: ` — la faute exacte qui a coupé le portail six minutes le 2026-09-06. Un
    aide-mémoire périmé est pire que pas d'aide-mémoire : on ne le relit pas.
    """
    import re

    mentions = {}
    for f in _fichiers_documentaires():
        for v in re.findall(r"authelia/authelia:([0-9][\w.\-]*)", f.read_text(encoding="utf-8")):
            mentions.setdefault(v, []).append(f.name)

    assert mentions, (
        "aucune mention d'image Authelia trouvée : la garde ne garde plus rien. Si les "
        "motifs de `_fichiers_documentaires` ont bougé, c'est ICI qu'il faut regarder — "
        "une garde qui n'inspecte rien passe au vert")
    assert len(mentions) == 1, (
        "deux versions d'Authelia documentées à la fois : "
        + " ; ".join("%s dans %s" % (v, sorted(set(f))) for v, f in sorted(mentions.items()))
        + ". Une seule est servie (`deploy/docker-compose.yml`), et celle qu'on recopie "
          "depuis un document périmé ne rend pas l'erreur visible : elle rend une réponse")


def test_aucune_commande_documentee_ne_pose_un_secret_sur_la_ligne():
    """Trois procédures faisaient écrire le mot de passe dans l'historique du shell.

    `authelia crypto hash generate argon2 --password '…'` marche, et c'est le problème :
    le secret survit à la session dans `~/.bash_history`, se relit sans droit particulier,
    et part dans toute sauvegarde du compte. La forme `-it` le fait DEMANDER à l'invite.

    Le plus instructif est d'où venait la bonne version. `docs/exploitation.md` portait
    deux blocs pour le même geste ; celui qu'on tenait pour l'aide-mémoire périmé — image
    plus ancienne, contrôle plus faible — était le SEUL à faire demander le mot de passe,
    et il l'expliquait en commentaire. Deux copies ne divergent pas dans le même sens :
    chacune finit par porter ce qui manque à l'autre, si bien que « la plus récente fait
    foi » est une règle qui perd quelque chose à chaque fois.
    """
    fautifs, inspectees = [], []
    for f in _fichiers_documentaires():
        # Ce qu'on garde, ce sont les lignes qu'on COPIE-COLLE, et la marque en est le bloc
        # de code. Une prose qui NOMME la forme fautive pour en avertir en contient
        # forcément les mots — le premier jet de cette garde s'est déclenché sur le
        # paragraphe de remédiation écrit pour l'éteindre. Distinguer par le vocabulaire
        # revenait à interdire d'écrire ce dont on met en garde.
        markdown = f.suffix == ".md"
        dans_bloc = not markdown          # hors markdown, tout le fichier est du copiable
        for n, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if markdown and ligne.lstrip().startswith("```"):
                dans_bloc = not dans_bloc
                continue
            if not dans_bloc:
                continue
            if "crypto hash generate" in ligne:
                inspectees.append("%s:%d" % (f.name, n))
                if "--password" in ligne:
                    fautifs.append("%s:%d" % (f.name, n))
            elif "--password" in ligne and "docker run" in ligne:
                fautifs.append("%s:%d" % (f.name, n))

    # Sans ceci, la garde passe au VERT en n'inspectant RIEN : `assert not fautifs` est
    # trivialement vrai sur une liste vide. Mesuré le 2026-09-07 en vidant les motifs de
    # `_fichiers_documentaires` — elle a approuvé. C'est le défaut d'ARCH-2 (une garde plus
    # verte à mesure qu'elle voit moins) reproduit dans la garde écrite le jour même pour
    # une faute de la même famille. La garde voisine s'en défendait ; celle-ci non, et rien
    # ne le disait — les deux se lisaient pareil.
    assert inspectees, (
        "aucune commande `crypto hash generate` inspectée : la garde ne garde plus rien. "
        "Soit les motifs de `_fichiers_documentaires` ont cessé d'atteindre la procédure, "
        "soit la procédure a disparu — dans les deux cas c'est ICI qu'il faut regarder, "
        "et surtout pas conclure du vert que rien ne pose de secret sur la ligne")
    assert not fautifs, (
        "commande documentée posant un secret sur la ligne : " + ", ".join(fautifs)
        + ". Employer `docker run --rm -it …` sans `--password` : l'invite ne laisse "
          "rien dans l'historique du shell")


# --------------------------------------------------------------------------- #
# CONC-1 — le registre des lots ne perdait jamais rien
# --------------------------------------------------------------------------- #
def test_le_registre_des_lots_ne_croit_plus_indefiniment(monkeypatch):
    """`_jobs` vit en RAM et gardait chaque lot lancé, pour toujours.

    Invisible en session courte, sensible sur une instance qui tourne des jours
    (INFRA-1). On borne le NOMBRE et non l'ÂGE : c'est le seul des deux qui tienne
    « sa taille ne croît plus indéfiniment », une purge par ancienneté laissant grossir
    une rafale de lots lancés coup sur coup.

    Trois propriétés, et la deuxième est celle qui casserait un écran : le plafond est
    tenu, un lot NON terminé survit quel que soit son rang, et ce sont les PLUS ANCIENS
    qui partent — purger au hasard tiendrait le plafond tout aussi bien.
    """
    from pipeline import jobs

    monkeypatch.setattr(jobs, "_run", lambda job_id: None)   # pas de worker : on teste le registre
    monkeypatch.setattr(jobs, "_jobs", {})                   # registre neuf, restauré par monkeypatch
    monkeypatch.setattr(jobs, "_counter", 10_000)            # sinon le jid tiré du compteur GLOBAL
                                                             # peut percuter un id injecté ci-dessous,
                                                             # selon les tests joués avant celui-ci

    for i in range(1, jobs.JOBS_CONSERVES + 51):             # 50 de trop, exprès
        jobs._jobs[i] = {"id": i, "passes": ["ocr"], "planche_ids": [i], "total": 1,
                         "done": 1, "current": None, "errors": [], "status": "termine",
                         "cancel": False}
    vieux_mais_vivant = 1
    jobs._jobs[vieux_mais_vivant]["status"] = "en_cours"     # le PLUS ancien, et il tourne

    neuf = jobs.start_job(["ocr"], [42])["id"]

    finis = [j for j in jobs._jobs.values() if j["status"] in jobs._STATUTS_TERMINAUX]
    # L'ordre des assertions COMPTE : le plafond en premier masquait celle-ci, qui est
    # la seule à casser un écran. Mesuré — une purge ignorant le statut faisait rougir
    # « plafond non tenu : 99 », un motif qui n'a rien à voir avec ce qu'elle démentait.
    assert vieux_mais_vivant in jobs._jobs, "un lot EN COURS a été purgé"
    assert len(finis) == jobs.JOBS_CONSERVES, f"plafond non tenu : {len(finis)}"
    assert neuf in jobs._jobs, "le lot qu'on vient de lancer a été purgé"
    assert 2 not in jobs._jobs and 50 not in jobs._jobs, "les PLUS ANCIENS doivent partir"
    assert 150 in jobs._jobs, "et les plus récents rester — purger au hasard tiendrait le plafond aussi"


def test_l_enumeration_des_lots_ne_peut_plus_croiser_une_purge(monkeypatch):
    """CONC-1 — la purge a ouvert un mode de panne que le registre sans retrait n'avait pas.

    `all_jobs` listait les identifiants puis demandait leur instantané un par un, sans
    verrou. Un lot purgé entre les deux rend `snapshot(...) is None`, et `GET /api/jobs`
    déréférence `s["id"]` dessus : 500. La Bibliothèque interroge cette route chaque
    seconde pendant un lot, et c'est le lancement d'un AUTRE lot, depuis le même écran,
    qui purge — le poll avale ses erreurs, donc la progression se figerait sans un mot.

    **Les DEUX assertions font l'argument, et aucune ne suffit.** Le retrait concurrent
    n'est impossible que si les deux côtés tiennent LE MÊME verrou : l'énumération ici,
    la purge dans `start_job`. Vérifier un seul côté laisserait passer la mutation qui
    déverrouille l'autre.

    Elles portent sur le MÉCANISME, faute de mieux et non par facilité : un fil qui
    purgerait pendant l'énumération se bloque désormais sur `_lock`, si bien qu'un test
    de la propriété — « aucune entrée nulle » — passerait au vert dans un registre
    monofil quoi qu'on fasse au code. Une assertion increvable ne vaut pas mieux que pas
    d'assertion du tout.

    **La doublure porte sur `_snapshot_nu` et non sur `snapshot`**, depuis que ce dernier
    prend `_lock` lui-même : `all_jobs` ne peut pas l'appeler sans s'auto-bloquer, et
    espionner un nom que l'énumération n'emprunte plus rendrait ce test vert sans rien
    voir. C'est la forme d'échec d'ARCH-1 — un test qui remplace un nom PAR le module
    cesse d'agir en silence dès que le nom déménage.
    """
    from pipeline import jobs

    monkeypatch.setattr(jobs, "_run", lambda job_id: None)   # pas de worker : on teste le registre
    monkeypatch.setattr(jobs, "_jobs", {})
    monkeypatch.setattr(jobs, "_counter", 10_000)

    vu = {"enumeration": [], "purge": None}

    snapshot_reel, purge_reelle = jobs._snapshot_nu, jobs._purger_registre

    def snapshot_espion(jid):
        vu["enumeration"].append(jobs._lock.locked())
        return snapshot_reel(jid)

    def purge_espionne():
        vu["purge"] = jobs._lock.locked()
        return purge_reelle()

    monkeypatch.setattr(jobs, "_snapshot_nu", snapshot_espion)
    monkeypatch.setattr(jobs, "_purger_registre", purge_espionne)

    for i in range(1, 4):
        jobs._jobs[i] = {"id": i, "passes": ["ocr"], "planche_ids": [i], "total": 1,
                         "done": 1, "current": None, "errors": [], "status": "termine",
                         "cancel": False}
    jobs.start_job(["ocr"], [42])
    vu["enumeration"].clear()        # `start_job` finit par un snapshot, qui prend le sien

    assert jobs.all_jobs(), "l'énumération doit rendre les lots, pas seulement tenir un verrou"
    assert vu["purge"] is True, (
        "la purge RETIRE du registre : elle doit tenir `_lock`, sans quoi le verrou pris "
        "à l'énumération ne protège de rien")
    assert vu["enumeration"] and all(vu["enumeration"]), (
        "l'énumération lit le registre entrée par entrée : sans `_lock`, une purge "
        "concurrente lui fait rendre un `None` que `GET /api/jobs` déréférence")


# --------------------------------------------------------------------------- #
# `Cache-Control: no-cache` — la liste de chemins avait oublié la cinquième page
# --------------------------------------------------------------------------- #
def test_administration_n_est_pas_cachable(client):
    """`/administration` (UX-10) manquait à la liste du middleware `_no_cache_assets`.

    Conséquence, sur un poste de développement seulement : le navigateur intégré d'un
    IDE peut servir une page périmée alors que le disque est à jour — le défaut même que
    ce middleware existe pour empêcher, actif sur quatre surfaces et pas sur la cinquième.
    Rien dans la suite ne regardait cet en-tête, donc rien ne pouvait le dire.
    """
    assert client.get("/administration").headers.get("cache-control") == "no-cache"


def test_toute_surface_html_est_revalidee(client):
    """Le cliquet, et il ne connaît AUCUNE liste de surfaces.

    Une liste écrite à la main oublie ce qu'on ajoute : c'est ainsi que la cinquième page
    est passée à travers. `surfaces_servies` demande à l'application ce qu'elle sert
    réellement en `text/html`, si bien qu'une sixième surface est couverte le jour où elle
    naît, sans que personne y pense.

    Le plancher n'est pas décoratif : l'énumération pourrait rétrécir (leçon d'ARCH-2, où
    deux cliquets ont continué de PASSER en ne regardant plus que 53 routes sur 122), et
    ce test-ci deviendrait vert en ne mesurant rien.
    """
    import surfaces

    servies = surfaces.surfaces_servies(client)
    assert len(servies) >= 5, (
        f"seulement {len(servies)} surface(s) HTML détectée(s) : le balayage ne voit plus "
        f"ce qu'il garde")
    manquantes = sorted(c for c in servies
                        if client.get(c).headers.get("cache-control") != "no-cache")
    assert not manquantes, (
        f"{manquantes} servent du HTML sans `Cache-Control: no-cache` : un navigateur "
        f"intégré d'IDE peut en servir une version périmée")


# --------------------------------------------------------------------------- #
# AUDIT P2 — l'état d'un lot se lit et s'écrit sous `_lock`
# --------------------------------------------------------------------------- #
class _LotEspion(dict):
    """Un lot qui note, à chaque écriture d'un champ, si `_lock` était tenu."""

    def __init__(self, source, vu):
        super().__init__(source)
        self._vu = vu
        self["errors"] = _ErreursEspionnes(self.get("errors") or [], vu)

    def __setitem__(self, cle, valeur):
        from pipeline import jobs
        if cle in jobs._CHAMPS_SNAPSHOT and hasattr(self, "_vu"):
            self._vu.append((cle, jobs._lock.locked()))
        super().__setitem__(cle, valeur)


class _ErreursEspionnes(list):
    """`errors` est mutée par `append`, jamais réaffectée : elle a son propre espion."""

    def __init__(self, source, vu):
        super().__init__(source)
        self._vu = vu

    def append(self, item):
        from pipeline import jobs
        self._vu.append(("errors", jobs._lock.locked()))
        super().append(item)


def test_l_etat_d_un_lot_s_ecrit_toujours_sous_le_verrou(client, monkeypatch):
    """Le worker écrivait `current`/`done`/`errors`/`status` pendant que `snapshot` les
    lisait, **sans `_lock`** — constat P2 d'`AUDIT.md`, la moitié que CONC-1 avait laissée.

    Ce qui manquait n'était pas l'atomicité : le GIL rend chaque champ atomique pris
    séparément, et c'est pourquoi « ça marche ». C'est la COMPOSITION qui manquait —
    `snapshot` lit sept champs à la suite, et le worker pouvait écrire entre deux. Un
    lecteur pouvait donc voir « terminé » avec une planche encore en cours.

    Le test mesure la propriété directement plutôt que par ses effets : un lot espion note
    à chaque écriture si le verrou était tenu. Une course, elle, ne se reproduit pas à la
    demande — c'est la raison pour laquelle ce constat a survécu à deux passes.
    """
    import time
    from pipeline import jobs

    vu: list = []
    registre = {}

    class _Registre(dict):
        def __setitem__(self, jid, job):
            super().__setitem__(jid, _LotEspion(job, vu))

    monkeypatch.setattr(jobs, "_jobs", _Registre(registre))
    monkeypatch.setattr(jobs, "_apply_pass", lambda conn, passe, pid: None)
    monkeypatch.setattr(jobs, "_est_verrouillee", lambda conn, pid: False)

    jid = jobs.start_job(["segmenter"], [1, 2])["id"]
    for _ in range(100):
        time.sleep(0.05)
        if jobs.snapshot(jid)["status"] != "en_cours":
            break

    # Anti-aveuglement : sans écriture observée, « toutes sous verrou » est vrai du vide.
    assert len(vu) >= 4, (
        f"seulement {len(vu)} écriture(s) observée(s) : le lot n'a rien fait, et "
        f"l'assertion suivante serait vraie de rien")
    nues = [cle for cle, verrouille in vu if not verrouille]
    assert not nues, (
        f"{sorted(set(nues))} sont écrits hors `_lock` : un `snapshot` concurrent peut "
        f"les voir dans un état composite incohérent")


def test_l_instantane_d_un_lot_ne_partage_plus_sa_liste_d_erreurs(client, monkeypatch):
    """`snapshot` rendait la liste VIVANTE du lot, pas une copie.

    L'appelant sérialisait donc un objet que le worker pouvait allonger sous lui, et le
    gardait ensuite comme une vue là où il croyait tenir une mesure. C'est un défaut
    d'aliasing avant d'être un défaut de concurrence : il vaut sur un seul fil, et c'est
    pourquoi il se teste sans course.
    """
    from pipeline import jobs

    monkeypatch.setattr(jobs, "_run", lambda job_id: None)      # pas de worker
    monkeypatch.setattr(jobs, "_jobs", {})
    jid = jobs.start_job(["segmenter"], [1])["id"]

    instantane = jobs.snapshot(jid)
    jobs._jobs[jid]["errors"].append({"planche_id": 1, "passe": "ocr", "erreur": "après"})

    assert instantane["errors"] == [], (
        "l'instantané a suivi le lot : il rend la liste vivante et non une copie")
    assert len(jobs.snapshot(jid)["errors"]) == 1, (
        "l'instantané SUIVANT doit bien voir l'erreur — sinon on ne copie pas, on perd")


# --------------------------------------------------------------------------- #
# A3 — une réindexation qui échoue laisse une trace, elle aussi
# --------------------------------------------------------------------------- #
def _activites_reindex(db_path):
    import sqlite3
    raw = sqlite3.connect(db_path)
    raw.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in raw.execute(
            "SELECT id, date_fin, comptes FROM activite WHERE type = 'reindex_nlp' "
            "ORDER BY id")]
    finally:
        raw.close()


@pytest.mark.parametrize("rang_qui_leve, quand", [(1, "avant le premier lot"),
                                                  (3, "après un lot validé")])
def test_une_reindexation_ratee_laisse_sa_trace(client, planche, db_path, monkeypatch,
                                                rang_qui_leve, quand):
    """`reindex_all` ouvrait son activité SANS la valider : elle n'était persistée qu'avec
    le premier lot, et une panne avant lui l'emportait avec le `rollback` de l'appelant.

    Le journal ne gardait alors que les réindexations qui avaient MARCHÉ — une passe ratée
    et une passe jamais lancée devenaient indistinguables, dans une couche append-only où
    cela ne se corrige plus. C'est la panne réparée le 2026-09-08 dans `journal.passe_ml`,
    sur l'autre chemin de la même famille.

    Les deux rangs éprouvent les deux côtés du seul commit qui séparait les cas, et le
    second garde une chose que le premier ne peut pas voir : qu'on n'inscrit pas une
    SECONDE activité quand la première est déjà persistée. Compter deux runs là où il y en
    a eu un serait l'autre façon de mentir.
    """
    import database
    import pipeline.nlp

    for i in range(2):
        client.post(f"/api/planches/{planche['id']}/regions",
                    json={"type": "bulle", "x": i, "y": 1, "w": 9, "h": 9,
                          "ocr_texte": f"REPLIQUE {i}"})
    avant = len(_activites_reindex(db_path))

    appels = {"n": 0}

    def analyse_qui_leve(textes):
        appels["n"] += 1
        if appels["n"] >= rang_qui_leve:
            raise RuntimeError("le modèle a lâché")
        return [("", []) for _ in textes]

    monkeypatch.setattr(pipeline.nlp, "analyse_batch", analyse_qui_leve)

    conn = database.get_connection()
    try:
        with pytest.raises(RuntimeError):
            database.reindex_all(conn, chunk=1)
        conn.rollback()          # ce que fait l'appelant réel (la dépendance `db`, le CLI)
    finally:
        conn.close()

    runs = _activites_reindex(db_path)
    assert len(runs) == avant + 1, (
        f"{quand} : {len(runs) - avant} activité(s) au lieu d'une — soit la trace est "
        f"partie avec le rollback, soit elle a été inscrite deux fois")
    dernier = runs[-1]
    assert dernier["date_fin"], f"{quand} : l'activité reste OUVERTE, sans fin ni bilan"
    assert '"echec": true' in (dernier["comptes"] or "").lower(), (
        f"{quand} : le bilan ne dit pas que le run a échoué — {dernier['comptes']!r}")
    assert "le modèle a lâché" not in (dernier["comptes"] or ""), (
        "le message de l'exception ne doit PAS entrer dans `comptes` : cette colonne SORT "
        "de l'instance, elle emporterait des chemins serveur au dépôt (AUTH-1)")


def test_une_reindexation_interrompue_au_clavier_se_distingue_d_une_panne(
        client, planche, db_path, monkeypatch):
    """Ctrl+C sur `tools/reindex_nlp.py` — l'interruption RÉALISTE de cette fonction.

    C'est une CLI qui tourne des minutes sur le FIL PRINCIPAL, donc `KeyboardInterrupt`
    y arrive vraiment ; et il n'est pas une `Exception`. Un `except Exception` laissait
    donc l'activité ouverte pour toujours, et tout consommateur du journal la lisait
    comme un run encore en cours — précisément le mensonge que ce chantier ferme.

    `journal.passe_ml` s'en tient à `Exception` sans avoir ce défaut : il vit dans un fil
    de travail, où Ctrl+C n'arrive jamais. L'asymétrie est justifiée, pas subie.

    Et l'arrêt DEMANDÉ se distingue de la panne SUBIE, comme dans `passe_ml` : dans une
    couche append-only, une annulation entrée au journal comme une panne ne se corrige
    plus.
    """
    import database
    import pipeline.nlp

    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                      "ocr_texte": "REPLIQUE"})
    avant = len(_activites_reindex(db_path))

    def analyse_interrompue(textes):
        raise KeyboardInterrupt()

    monkeypatch.setattr(pipeline.nlp, "analyse_batch", analyse_interrompue)

    conn = database.get_connection()
    try:
        with pytest.raises(KeyboardInterrupt):
            database.reindex_all(conn, chunk=1)
        conn.rollback()
    finally:
        conn.close()

    runs = _activites_reindex(db_path)
    assert len(runs) == avant + 1, "l'activité est partie avec le rollback"
    assert runs[-1]["date_fin"], "Ctrl+C laisse l'activité OUVERTE, sans fin ni bilan"
    comptes = (runs[-1]["comptes"] or "").lower()
    assert '"interrompu": true' in comptes, (
        f"un arrêt demandé doit se lire comme tel, pas comme une panne — {comptes!r}")
    assert '"echec"' not in comptes, (
        "une interruption n'est pas un échec : la confondre est irréversible dans une "
        "couche append-only")


def test_une_panne_dans_l_epilogue_ferme_quand_meme_l_activite(client, planche, db_path,
                                                               monkeypatch):
    """Le travail est FAIT, et c'est la dernière ligne qui lâche.

    L'épilogue de `reindex_all` — les deux écritures de `meta`, puis la clôture — est
    fait de requêtes SQLite comme les autres : un « database is locked » y est aussi
    possible qu'ailleurs, et c'est précisément ce que le WAL et le 409 gèrent partout.
    Laissé HORS du `try`, il produisait le même mensonge que la panne du milieu — une
    activité restée ouverte —, à la dernière ligne près.

    La doublure fait échouer la PREMIÈRE clôture seulement : la seconde, celle du
    rattrapage, doit aboutir. Un test où toutes échouent ne distinguerait pas « on ne
    rattrape pas » de « on ne peut pas rattraper ».
    """
    import sqlite3

    import database
    import journal

    client.post(f"/api/planches/{planche['id']}/regions",
                json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                      "ocr_texte": "REPLIQUE"})
    avant = len(_activites_reindex(db_path))

    reelle = journal.cloturer_activite
    appels = {"n": 0}

    def cloture_qui_lache(conn, activite_id, *, comptes=None):
        appels["n"] += 1
        if appels["n"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return reelle(conn, activite_id, comptes=comptes)

    monkeypatch.setattr(journal, "cloturer_activite", cloture_qui_lache)

    conn = database.get_connection()
    try:
        with pytest.raises(sqlite3.OperationalError):
            database.reindex_all(conn, chunk=1)
        conn.rollback()
    finally:
        conn.close()

    assert appels["n"] == 2, (
        "la clôture de rattrapage n'a pas été tentée : l'épilogue est resté hors du `try`")
    runs = _activites_reindex(db_path)
    assert len(runs) == avant + 1
    assert runs[-1]["date_fin"], (
        "une panne d'épilogue laisse l'activité OUVERTE alors que tout le travail est fait")
