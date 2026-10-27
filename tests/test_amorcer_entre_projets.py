"""COL-3, tranche 3b, E7 — EN PARTIR d'un travail d'un AUTRE projet.

La décision (Hugo, 2026-10-20, forme (c) du cadrage) : le responsable du projet d'arrivée
demande un DOCUMENT et un CRAN, jamais une copie source. Le serveur adresse la demande aux
responsables des projets qui tiennent ce travail — une copie rangée, travaillée au moins
jusqu'au cran —, et à un administrateur sinon. Le demandeur ne lit que « demandé », au bit
près : la réponse de la prise et la vue de ses demandes sont les MÊMES octets, qu'un autre
projet tienne ce travail ou non. Le premier responsable qui accepte choisit SA copie source ;
la copie neuve est au demandeur.

Le décor reprend celui de `test_prendre` (le projet de repli porte « Principale », où
`importeur` a importé trois documents ; le projet « Étude P » a `resp` pour responsable) et
lui ajoute `resp2`, RESPONSABLE du projet de repli — un second projet, d'où l'on part —,
`membre2`, simple membre du repli, et `proprio2`, propriétaire de Principale sans rien gérer.
`resp2` LIT Principale : gérer un projet n'en ouvre pas les collections, et un responsable ne
consent qu'avec une copie qu'il lit (relecture croisée de la 3b, constat 2).
La copie d'origine de « Le Lotus bleu » (d1) est TRAVAILLÉE dans Principale : une case et sa
bulle, avec du texte ; celle de « L'Oreille cassée » (d2) n'a que ses images.
"""
import json

import pytest

import database
import main
from conftest import du_projet
from conftest import ADMIN
from pipeline import ingest
from test_fonds import _accorder, _album, _collection, _planche
from test_prendre import (ECRIVAIN, IMPORTEUR, LECTRICE, RESP, _prendre,
                          prise)  # noqa: F401
from test_projets import _sql

RESP2 = {"Remote-User": "resp2"}
MEMBRE2 = {"Remote-User": "membre2"}
PROPRIO2 = {"Remote-User": "proprio2"}


def _ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.text)
    return r.json() if r.content else None


def _travailler(client, album_id, qui, texte="TINTIN ET LES OTAGES"):
    """Une case et sa bulle sur la première planche de l'album, avec du texte : la copie
    tient alors son travail jusqu'au cran `transcription`."""
    pl = client.get(f"/api/albums/{album_id}/planches", headers=qui).json()[0]["id"]
    case = _ok(client.post(f"/api/planches/{pl}/regions", headers=qui,
                           json={"type": "case", "x": 0, "y": 0, "w": 300, "h": 200}), 201)
    bulle = _ok(client.post(f"/api/planches/{pl}/regions", headers=qui,
                            json={"type": "bulle", "x": 10, "y": 10, "w": 90, "h": 90,
                                  "parent_id": case["id"]}), 201)
    if texte:
        _ok(client.put(f"/api/regions/{bulle['id']}", headers=qui, json={"ocr_texte": texte}))
    return bulle["id"]


def _repli(client):
    return next(p["id"] for p in client.get("/api/projets", headers=ADMIN).json()
                if p["repli"])


@pytest.fixture
def ailleurs(client, prise):  # noqa: F811
    repli = _repli(client)
    for principal, role in (("resp2", "responsable"), ("membre2", "membre")):
        _ok(client.put(f"/api/projets/{repli}/membres", headers=ADMIN,
                       json={"principal": principal, "role": role}))
    _accorder(client, prise["principale"], "proprio2", "proprietaire")
    # F6 (COL-3, tranche 3c) — E7 ne part que des collections où le responsable ÉCRIT.
    _accorder(client, prise["principale"], "resp2", "ecriture")
    _travailler(client, prise["albums"]["d1"], IMPORTEUR)
    return {**prise, "repli": repli}


def _amorcer(doc, cran="transcription", album_id=None):
    ligne = {"document_id": doc, "reponse": "amorcer", "cran": cran}
    if album_id is not None:
        ligne["album_id"] = album_id
    return ligne


def _demander_ailleurs(client, s, doc_cle="d1", cran="transcription", qui=RESP,
                       motif="Pour l'étude des onomatopées."):
    r = _prendre(client, s["base"], [_amorcer(s["docs"][doc_cle], cran)], qui, motif=motif)
    (ligne,) = _ok(r)["documents"]
    return ligne


def _repondre(client, demande_id, reponse, qui, album_id=None):
    corps = {"reponse": reponse}
    if album_id is not None:
        corps["album_id"] = album_id
    return client.post(f"/api/demandes/{demande_id}/reponse", json=corps, headers=qui)


# =========================================================================== #
# Le demandeur ne lit que « demandé », au bit près
# =========================================================================== #
def _instance(tmp_path, monkeypatch, nom):
    """Une instance NEUVE dans le même test : sa base et ses dossiers à elle. Les deux
    instances du test suivant sont montées par les MÊMES gestes, dans le même ordre : leurs
    identifiants coïncident, et seule diffère ce qu'un autre projet tient."""
    d = tmp_path / nom
    d.mkdir()
    monkeypatch.setattr(database, "DB_PATH", d / "test.sqlite")
    monkeypatch.setattr(main, "DATA_DIR", d)
    monkeypatch.setattr(ingest, "DATA_DIR", d)
    monkeypatch.setattr(ingest, "CORPUS_DIR", d / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", d / "derivatives")
    database.init_db()
    main._vus.clear()
    return d / "test.sqlite"


def _monter(client, *, travail: bool) -> dict:
    """Principale (repli, `resp2` responsable), « Le Lotus bleu » importé par `importeur` —
    travaillé jusqu'au texte, ou non —, et le projet « Étude P » de `resp`."""
    principale = _collection(client, "Principale")
    _accorder(client, principale, "importeur", "ecriture")
    a = _album(client, "Le Lotus bleu", principale, IMPORTEUR)
    _planche(client, a, IMPORTEUR)
    _travailler(client, a, IMPORTEUR, texte="TINTIN" if travail else None)
    repli = _repli(client)
    _ok(client.put(f"/api/projets/{repli}/membres", headers=ADMIN,
                   json={"principal": "resp2", "role": "responsable"}))
    p = _ok(client.post("/api/projets", json={"nom": "Étude P"}, headers=ADMIN), 201)["id"]
    _ok(client.put(f"/api/projets/{p}/membres", headers=ADMIN,
                   json={"principal": "resp", "role": "responsable"}))
    base = next(c["id"] for c in client.get("/api/collections", headers=ADMIN).json()
                if c["base"] and c["projet_id"] == p)
    doc = client.get("/api/albums", headers=ADMIN).json()
    doc = next(x["document_id"] for x in doc if x["id"] == a)
    return {"a": a, "projet": p, "base": base, "doc": doc}


def _vue_du_demandeur(client, db, projet) -> str:
    # Les dates sont celles de l'horloge : posées à la même valeur dans les deux instances,
    # pour que la comparaison porte sur tout le reste, octet par octet.
    _sql(db, "UPDATE demande SET date_creation = '2026-10-25 10:00:00', "
             "date_reponse = CASE WHEN date_reponse IS NULL THEN NULL "
             "ELSE '2026-10-25 11:00:00' END")
    r = client.get(f"/api/projets/{projet}/demandes", headers=RESP)
    assert r.status_code == 200, r.text
    return r.text


def test_le_demandeur_lit_demande_au_bit_pres(client, derriere_proxy, tmp_path, monkeypatch):
    """La prise, la vue des demandes, puis la vue après un refus — par le responsable qui
    tient le travail dans un cas, par l'administrateur seul dans l'autre : les mêmes octets.
    Le cas « avec » est vérifié adressé (sans quoi l'égalité serait celle de deux mondes où
    personne ne tient rien)."""
    rendus = {}
    for travail in (True, False):
        db = _instance(tmp_path, monkeypatch, f"avec_{travail}")
        s = _monter(client, travail=travail)
        r = _prendre(client, s["base"], [_amorcer(s["doc"])], RESP, motif="Pour voir.")
        assert r.status_code == 200, r.text
        prise_brute = r.text
        demande_id = r.json()["documents"][0]["demande_id"]
        vue = _vue_du_demandeur(client, db, s["projet"])
        recues = _ok(client.get(f"/api/projets/{_repli(client)}/demandes-recues",
                                headers=RESP2))
        assert [d["id"] for d in recues] == ([demande_id] if travail else [])
        qui = RESP2 if travail else ADMIN
        _ok(_repondre(client, demande_id, "refusee", qui))
        rendus[travail] = (prise_brute, vue, _vue_du_demandeur(client, db, s["projet"]))
    assert rendus[True] == rendus[False]
    ligne = json.loads(rendus[True][0])["documents"][0]
    assert set(ligne) == {"document_id", "reponse", "cran", "etat", "demande_id"}
    assert ligne["etat"] == "demande"
    assert json.loads(rendus[True][2])[0]["reponse"] == "refusee"


def test_seul_un_responsable_demande_sans_nommer_de_copie(client, ailleurs):
    """Un écrivain du projet d'arrivée qui ne le gère pas doit nommer sa copie : 422, le
    même que sans cran. L'administrateur aussi — il prend directement."""
    r = _prendre(client, ailleurs["x"], [_amorcer(ailleurs["docs"]["d1"])], ECRIVAIN,
                 motif="m")
    assert r.status_code in (404, 422), r.text
    r = _prendre(client, ailleurs["x"], [_amorcer(ailleurs["docs"]["d1"])], ADMIN, motif="m")
    assert r.status_code == 422 and "album_id" in r.text


def test_une_demande_entre_deux_projets_exige_un_motif(client, ailleurs):
    r = _prendre(client, ailleurs["base"], [_amorcer(ailleurs["docs"]["d1"])], RESP)
    assert r.status_code == 422, r.text
    assert _sql(database.DB_PATH, "SELECT COUNT(*) AS n FROM demande")[0]["n"] == 0


# =========================================================================== #
# À qui elle s'adresse
# =========================================================================== #
def test_elle_s_adresse_au_responsable_du_projet_qui_tient_le_travail(client, ailleurs):
    ligne = _demander_ailleurs(client, ailleurs)
    recues = _ok(client.get(f"/api/projets/{ailleurs['repli']}/demandes-recues",
                            headers=RESP2))
    (d,) = recues
    assert d["id"] == ligne["demande_id"]
    assert (d["demandeur"], d["projet_nom"], d["cran"]) == ("resp", "Étude P", "transcription")
    assert d["titre"] == "Le Lotus bleu" and d["repondable"] is True
    assert [c["album_id"] for c in d["copies"]] == [ailleurs["albums"]["d1"]]
    assert d["copies"][0]["niveau"] == "transcription"
    assert "collection_id" not in d and "collection_nom" not in d
    # Le projet d'arrivée ne la reçoit pas : il ne tient rien.
    assert _ok(client.get(f"/api/projets/{ailleurs['projet']}/demandes-recues",
                          headers=RESP)) == []


def test_un_cran_que_personne_ne_tient_va_a_l_administrateur(client, ailleurs):
    """Le Lotus bleu n'a ni correction ni annotation : jusqu'aux annotations, personne ne
    tient ce travail — le responsable source ne la voit pas, l'administrateur seul répond,
    et il lit que la liste des sources est vide. L'Oreille cassée n'a que ses images."""
    for doc, cran in (("d1", "annotations"), ("d2", "decoupage")):
        ligne = _demander_ailleurs(client, ailleurs, doc, cran)
        assert ligne["etat"] == "demande"
        assert _ok(client.get(f"/api/projets/{ailleurs['repli']}/demandes-recues",
                              headers=RESP2)) == []
        d = next(x for x in _ok(client.get("/api/demandes", headers=ADMIN))
                 if x["id"] == ligne["demande_id"])
        assert d["sources"] == []
        assert _repondre(client, ligne["demande_id"], "refusee", RESP2).status_code == 404


def test_l_adressage_suit_le_travail_tel_qu_il_est(client, ailleurs):
    """Rien n'est écrit sur la demande : une copie travaillée DEPUIS la fait apparaître chez
    son responsable, et l'administrateur lit la source."""
    ligne = _demander_ailleurs(client, ailleurs, "d2", "transcription")
    assert _ok(client.get(f"/api/projets/{ailleurs['repli']}/demandes-recues",
                          headers=RESP2)) == []
    _travailler(client, ailleurs["albums"]["d2"], IMPORTEUR)
    (d,) = _ok(client.get(f"/api/projets/{ailleurs['repli']}/demandes-recues", headers=RESP2))
    assert d["id"] == ligne["demande_id"]
    admin = next(x for x in _ok(client.get("/api/demandes", headers=ADMIN))
                 if x["id"] == ligne["demande_id"])
    assert [(s["album_id"], s["projet_id"]) for s in admin["sources"]] == [
        (ailleurs["albums"]["d2"], ailleurs["repli"])]


def test_une_copie_gardee_au_fonds_ou_d_un_bac_a_sable_ne_tient_rien(client, ailleurs, db_path):
    """Une copie qui n'est rangée nulle part n'est tenue que par qui tient le fonds ; une
    copie d'un projet ISOLÉ n'est la source de rien. Mesuré sur la fonction elle-même."""
    d1, doc = ailleurs["albums"]["d1"], ailleurs["docs"]["d1"]
    conn = database.get_connection()
    try:
        assert set(database.projets_qui_tiennent(conn, doc, "transcription", sauf=None)) == {
            ailleurs["repli"]}
        conn.execute("UPDATE projet SET bac_a_sable_de = 'quelquun' WHERE id = ?",
                     (ailleurs["repli"],))
        assert database.projets_qui_tiennent(conn, doc, "transcription", sauf=None) == {}
        conn.rollback()
        conn.execute("DELETE FROM collection_album WHERE album_id = ?", (d1,))
        conn.execute("UPDATE albums SET projet_id = ? WHERE id = ?", (ailleurs["repli"], d1))
        assert database.projets_qui_tiennent(conn, doc, "transcription", sauf=None) == {}
        conn.rollback()
        assert database.projets_qui_tiennent(conn, doc, "transcription",
                                             sauf=ailleurs["repli"]) == {}
    finally:
        conn.close()


@pytest.mark.parametrize("qui", [MEMBRE2, PROPRIO2, IMPORTEUR, RESP, ECRIVAIN])
def test_qui_ne_gere_pas_le_projet_source_ne_la_connait_pas(client, ailleurs, qui):
    """Être MEMBRE du projet source, POSSÉDER la collection où vit la copie, l'avoir
    IMPORTÉE, l'avoir DEMANDÉE : rien de cela ne fait répondre. Un 404, le même que pour une
    demande qui n'existe pas ; ou le 403 du droit, avant l'objet, à qui ne possède ni ne
    gère rien."""
    ligne = _demander_ailleurs(client, ailleurs)
    for reponse in ("acceptee", "refusee"):
        r = _repondre(client, ligne["demande_id"], reponse, qui,
                      album_id=ailleurs["albums"]["d1"] if reponse == "acceptee" else None)
        absente = _repondre(client, 999999, reponse, qui)
        assert r.status_code in (403, 404), (qui, r.text)
        assert (r.status_code, r.json()["detail"].replace(str(ligne["demande_id"]), "N")) == (
            absente.status_code, absente.json()["detail"].replace("999999", "N"))
    assert _sql(database.DB_PATH, "SELECT reponse FROM demande WHERE id = ?",
                (ligne["demande_id"],))[0]["reponse"] is None


def test_les_demandes_recues_se_lisent_par_qui_gere(client, ailleurs):
    _demander_ailleurs(client, ailleurs)
    for qui in (MEMBRE2, PROPRIO2, IMPORTEUR):
        r = client.get(f"/api/projets/{ailleurs['repli']}/demandes-recues", headers=qui)
        assert r.status_code == 403, (qui, r.text)
    assert client.get(f"/api/projets/{ailleurs['repli']}/demandes-recues",
                      headers=LECTRICE).status_code in (403, 404)
    assert len(_ok(client.get(f"/api/projets/{ailleurs['repli']}/demandes-recues",
                              headers=ADMIN))) == 1


# =========================================================================== #
# La réponse du responsable source
# =========================================================================== #
def test_le_responsable_source_accepte_en_choisissant_sa_copie(client, ailleurs, db_path):
    ligne = _demander_ailleurs(client, ailleurs)
    r = _repondre(client, ligne["demande_id"], "acceptee", RESP2,
                  album_id=ailleurs["albums"]["d1"])
    vue = _ok(r)
    assert vue["reponse"] == "acceptee"
    copie = vue["documents"][0]["copie_id"]
    assert copie and copie != ailleurs["albums"]["d1"]
    rangee = _sql(db_path, "SELECT collection_id FROM collection_album WHERE album_id = ?",
                  (copie,))
    assert [x["collection_id"] for x in rangee] == [ailleurs["base"]]
    prov = _sql(db_path, "SELECT creee_par, cran, depuis_album_id FROM copie "
                         "WHERE album_id = ?", (copie,))[0]
    assert prov == {"creee_par": "resp", "cran": "transcription",
                    "depuis_album_id": ailleurs["albums"]["d1"]}
    textes = _sql(db_path, "SELECT r.ocr_texte FROM regions r JOIN planches p "
                           "ON p.id = r.planche_id WHERE p.album_id = ? "
                           "AND r.ocr_texte IS NOT NULL", (copie,))
    assert [t["ocr_texte"] for t in textes] == ["TINTIN ET LES OTAGES"]
    # Le demandeur lit sa copie, dans sa base ; la demande n'attend plus chez personne.
    (dem,) = [d for d in _ok(client.get(f"/api/projets/{ailleurs['projet']}/demandes",
                                        headers=RESP)) if d["id"] == ligne["demande_id"]]
    assert dem["documents"][0]["copie_id"] == copie and "repondu_par" not in dem
    assert _ok(client.get(f"/api/projets/{ailleurs['repli']}/demandes-recues",
                          headers=RESP2)) == []
    assert _ok(client.get(f"/api/albums/{copie}/planches", headers=RESP))


def test_accepter_exige_une_copie_du_projet_qu_on_gere(client, ailleurs):
    """Sans copie : 422 nommé. Une copie d'un AUTRE projet, une copie qui n'existe pas : le
    même 404. Seules les copies du projet qu'on gère, et qui tiennent le travail."""
    ligne = _demander_ailleurs(client, ailleurs)
    assert _repondre(client, ligne["demande_id"], "acceptee", RESP2).status_code == 422
    x = _prendre(client, ailleurs["x"], [{"document_id": ailleurs["docs"]["d1"],
                                          "reponse": "zero"}], ADMIN).json()
    copie_x = x["documents"][0]["copie_id"]
    reponses = [_repondre(client, ligne["demande_id"], "acceptee", RESP2, album_id=a)
                for a in (copie_x, 999999)]
    assert [r.status_code for r in reponses] == [404, 404]
    assert {r.json()["detail"].split()[0] for r in reponses} == {"Album"}
    assert _sql(database.DB_PATH, "SELECT reponse FROM demande WHERE id = ?",
                (ligne["demande_id"],))[0]["reponse"] is None


def test_le_responsable_source_ne_consent_qu_avec_une_copie_ou_il_ecrit(client, ailleurs,
                                                                       db_path):
    """F6 (tranche 3c) — RÉÉCRIT sur l'écriture (c'était la lecture : relecture croisée de
    la 3b, constat 2). `resp2` gère le repli : il LIT Principale, où vit la copie travaillée
    de Le Lotus bleu (F1), sans y écrire ; nommé aussi responsable d'Étude P, il en demande
    le texte pour la base d'Étude P. La demande lui parvient — il peut la refuser —, mais
    sans copie à nommer ni aperçu : une copie qu'il LIT par la voie 1 sans y écrire n'est pas
    offerte. Accepter en la nommant lui répond le même 404 qu'une copie absente : le texte de
    Principale ne passe pas dans sa base sur sa seule réponse."""
    s = ailleurs
    o = s["albums"]["d1"]
    _sql(db_path, "DELETE FROM collection_acces WHERE principal = 'resp2'")
    assert client.get(f"/api/albums/{o}/planches", headers=RESP2).status_code == 200
    _ok(client.put(f"/api/projets/{s['projet']}/membres", headers=ADMIN,
                   json={"principal": "resp2", "role": "responsable"}))
    ligne = _demander_ailleurs(client, s, qui=RESP2)
    assert ligne["etat"] == "demande", ligne
    (d,) = _ok(client.get(f"/api/projets/{s['repli']}/demandes-recues", headers=RESP2))
    assert d["id"] == ligne["demande_id"] and d["copies"] == [], d
    reponses = [_repondre(client, d["id"], "acceptee", RESP2, album_id=a) for a in (o, 999999)]
    assert [r.status_code for r in reponses] == [404, 404]
    assert {r.json()["detail"].split()[0] for r in reponses} == {"Album"}
    assert _sql(db_path, "SELECT reponse FROM demande WHERE id = ?",
                (d["id"],))[0]["reponse"] is None
    assert not _sql(db_path, "SELECT 1 FROM regions r JOIN planches p ON p.id = r.planche_id "
                             "JOIN albums a ON a.id = p.album_id WHERE a.document_id = ? "
                             "AND a.id <> ?", (s["docs"]["d1"], o))
    # L'écriture rendue : la copie se nomme, son aperçu se lit, et l'accepter passe.
    _accorder(client, s["principale"], "resp2", "ecriture")
    (d,) = _ok(client.get(f"/api/projets/{s['repli']}/demandes-recues", headers=RESP2))
    assert [c["album_id"] for c in d["copies"]] == [o] and d["copies"][0]["apercu"]
    _ok(_repondre(client, d["id"], "acceptee", RESP2, album_id=o))


def test_entre_deux_projets_une_correction_recopiee_arrive_sans_auteur(client, ailleurs,
                                                                       db_path):
    """Relecture croisée de la 3b, constat 3, et la décision de Hugo du 2026-10-25 : ENTRE
    deux projets, une correction grammaticale recopiée arrive SANS auteur, et se lit
    « recopiée ». Ni l'analyse du mot, ni la concordance par auteur, ni « qui perd quoi »
    ne nomment le correcteur du projet source dans la copie ; la source, elle, le garde."""
    s = ailleurs
    o = s["albums"]["d1"]
    pl = client.get(f"/api/albums/{o}/planches", headers=IMPORTEUR).json()[0]["id"]
    bulle = [x for x in client.get(f"/api/planches/{pl}/regions", headers=IMPORTEUR).json()
             if x["type"] == "bulle"][0]["id"]
    _sql(db_path, "DELETE FROM tokens WHERE region_id = ?", (bulle,))
    _sql(db_path, "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                  "VALUES (?, 0, 'TINTIN', 'tintin', 'PROPN', '')", (bulle,))
    _sql(db_path, "INSERT INTO token_correction (region_id, ordre, forme, lemme, pos, etat, "
                  "auteur) VALUES (?, 0, 'TINTIN', 'Tintin', 'PROPN', 'corrige', "
                  "'importeur')", (bulle,))
    ligne = _demander_ailleurs(client, s, cran="grammaire")
    vue = _ok(_repondre(client, ligne["demande_id"], "acceptee", RESP2, album_id=o))
    neuve = vue["documents"][0]["copie_id"]
    copiee = _sql(db_path, "SELECT region_id FROM region_origine WHERE region_source_id = ?",
                  (bulle,))[0]["region_id"]
    assert _sql(db_path, "SELECT auteur FROM token_correction WHERE region_id = ?",
                (copiee,)) == [{"auteur": None}]
    toks = _ok(client.get(f"/api/regions/{copiee}/tokens", headers=RESP))
    assert [(t["corr_auteur"], t["corr_recopiee"], t["provenance"]) for t in toks] == [
        (None, True, "corrige")], toks
    conc = client.get("/api/analyse/concordance", headers=RESP,
                      params={"auteur": "importeur", "album": neuve})
    assert conc.status_code == 200 and "importeur" not in conc.text, conc.text
    qui = client.get(f"/api/albums/{neuve}/travail-des-autres", headers=RESP)
    assert qui.status_code == 200 and "importeur" not in qui.text, qui.text
    assert qui.json()["travail_recopie"]["gestes"]["token_correction"] == 1
    # La source garde son correcteur.
    assert _sql(db_path, "SELECT auteur FROM token_correction WHERE region_id = ?",
                (bulle,)) == [{"auteur": "importeur"}]


def _copie_au_cran_grammaire(client, s, db_path):
    """La bulle de Le Lotus bleu porte une correction d'`importeur` ; `resp` en demande la
    grammaire pour la base d'Étude P, `resp2` accepte. Rend la bulle copiée."""
    o = s["albums"]["d1"]
    pl = client.get(f"/api/albums/{o}/planches", headers=IMPORTEUR).json()[0]["id"]
    bulle = [x for x in client.get(f"/api/planches/{pl}/regions", headers=IMPORTEUR).json()
             if x["type"] == "bulle"][0]["id"]
    _sql(db_path, "DELETE FROM tokens WHERE region_id = ?", (bulle,))
    # La forme que le moteur rend (il minuscule le lettrage) : la validation réindexe, et une
    # correction dont la forme ne se retrouve plus partirait à revérifier.
    _sql(db_path, "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                  "VALUES (?, 0, 'tintin', 'tintin', 'PROPN', '')", (bulle,))
    _sql(db_path, "INSERT INTO token_correction (region_id, ordre, forme, lemme, pos, etat, "
                  "auteur) VALUES (?, 0, 'tintin', 'Tintin', 'PROPN', 'corrige', "
                  "'importeur')", (bulle,))
    ligne = _demander_ailleurs(client, s, cran="grammaire")
    _ok(_repondre(client, ligne["demande_id"], "acceptee", RESP2, album_id=o))
    return _sql(db_path, "SELECT region_id FROM region_origine WHERE region_source_id = ?",
                (bulle,))[0]["region_id"]


def test_une_correction_de_la_seconde_de_la_copie_n_est_pas_recopiee(client, ailleurs,
                                                                     db_path):
    """Contre-relecture de la 3b : la marque est EXPLICITE (décision du pilotage,
    2026-10-25). Une correction posée sur la copie dans la seconde même de sa naissance n'est
    pas recopiée — la date la confondait."""
    copiee = _copie_au_cran_grammaire(client, ailleurs, db_path)
    _sql(db_path, "INSERT INTO token_correction (region_id, ordre, forme, lemme, etat, "
                  "auteur, date_modif) VALUES (?, 1, 'ET', 'et', 'corrige', 'resp', "
                  "(SELECT c.creee_le FROM copie c JOIN planches p ON p.album_id = c.album_id "
                  " JOIN regions r ON r.planche_id = p.id WHERE r.id = ?))", (copiee, copiee))
    assert _sql(db_path, "SELECT ordre, recopiee FROM token_correction WHERE region_id = ? "
                         "ORDER BY ordre", (copiee,)) == [{"ordre": 0, "recopiee": 1},
                                                          {"ordre": 1, "recopiee": 0}]


def test_valider_une_correction_recopiee_n_en_fait_pas_l_auteur(client, ailleurs, db_path):
    """Décision du pilotage (2026-10-25) : la marque survit à la validation, et valider une
    correction recopiée n'en fait pas l'auteur — entre deux projets, elle reste sans auteur
    (le `COALESCE` de la route l'aurait donnée au validateur), passe `valide`, et qui l'a
    validée se lit au journal. La corriger, en revanche, la fait sienne et ôte la marque."""
    from pipeline import nlp
    if not nlp.nlp_available():
        pytest.skip("la validation réindexe la région : sans moteur, ses tokens partent")
    copiee = _copie_au_cran_grammaire(client, ailleurs, db_path)
    toks = _ok(client.post(f"/api/regions/{copiee}/grammaire/valider", headers=RESP))
    t0 = next(t for t in toks if t["ordre"] == 0)
    assert (t0["corr_auteur"], t0["corr_recopiee"], t0["provenance"]) == (None, True, "valide")
    assert _sql(db_path, "SELECT auteur, recopiee, etat FROM token_correction "
                         "WHERE region_id = ? AND ordre = 0", (copiee,)) == [
        {"auteur": None, "recopiee": 1, "etat": "valide"}]
    assert _sql(db_path, "SELECT agent FROM evenement WHERE cible_table = 'regions' "
                         "AND type = 'validation' AND cible_id = ?", (copiee,)) == [
        {"agent": "resp"}]
    toks = _ok(client.put(f"/api/regions/{copiee}/tokens/0", headers=RESP,
                          json={"lemme": "Tintin", "etat": "corrige"}))
    t0 = next(t for t in toks if t["ordre"] == 0)
    assert (t0["corr_auteur"], t0["corr_recopiee"]) == ("resp", False)


def test_la_lecture_se_relit_a_la_reponse(client, prise):
    """Contre-relecture de la 3b : `resp2` ÉCRIT dans la copie source par un GROUPE (F6,
    tranche 3c : c'était la lecture), retiré entre la demande et la réponse. La copie quitte
    ses `copies`, accepter en la nommant répond 404 ; il peut encore refuser."""
    repli = _repli(client)
    _ok(client.put(f"/api/projets/{repli}/membres", headers=ADMIN,
                   json={"principal": "resp2", "role": "responsable"}))
    du_projet(client, prise['principale'], "groupe", "lecteurs", headers=ADMIN)
    _ok(client.put(f"/api/collections/{prise['principale']}/acces", headers=ADMIN,
                   json={"genre": "groupe", "principal": "lecteurs", "niveau": "ecriture"}))
    r2 = {"Remote-User": "resp2", "Remote-Groups": "lecteurs"}
    o = prise["albums"]["d1"]
    _travailler(client, o, IMPORTEUR)
    ligne = _demander_ailleurs(client, prise)
    (d,) = _ok(client.get(f"/api/projets/{repli}/demandes-recues", headers=r2))
    assert [c["album_id"] for c in d["copies"]] == [o]
    _ok(client.delete(f"/api/collections/{prise['principale']}/acces/groupe/lecteurs",
                      headers=ADMIN), 204)
    (d,) = _ok(client.get(f"/api/projets/{repli}/demandes-recues", headers=r2))
    assert d["copies"] == []
    assert _repondre(client, ligne["demande_id"], "acceptee", r2,
                     album_id=o).status_code == 404
    assert _ok(_repondre(client, ligne["demande_id"], "refusee", r2))["reponse"] == "refusee"


def test_un_refus_la_ferme_pour_tous(client, ailleurs):
    ligne = _demander_ailleurs(client, ailleurs)
    _ok(_repondre(client, ligne["demande_id"], "refusee", RESP2))
    assert _repondre(client, ligne["demande_id"], "acceptee", ADMIN,
                     album_id=ailleurs["albums"]["d1"]).status_code == 409
    assert _ok(client.get(f"/api/projets/{ailleurs['repli']}/demandes-recues",
                          headers=RESP2)) == []


def test_l_administrateur_accepte_quand_personne_ne_tient(client, ailleurs, db_path):
    """Le recours : aucune copie ne tient le découpage de L'Oreille cassée ; l'administrateur
    nomme une copie du document hors du projet d'arrivée, et la copie neuve est au
    demandeur. Il ne peut pas nommer une copie du projet d'arrivée lui-même (409)."""
    ligne = _demander_ailleurs(client, ailleurs, "d2", "decoupage")
    vue = _ok(_repondre(client, ligne["demande_id"], "acceptee", ADMIN,
                        album_id=ailleurs["albums"]["d2"]))
    copie = vue["documents"][0]["copie_id"]
    assert _sql(db_path, "SELECT creee_par FROM copie WHERE album_id = ?",
                (copie,))[0]["creee_par"] == "resp"
    autre = _demander_ailleurs(client, ailleurs, "d2", "decoupage")
    assert _repondre(client, autre["demande_id"], "acceptee", ADMIN,
                     album_id=copie).status_code == 409


def test_le_meme_geste_ne_se_demande_pas_deux_fois(client, ailleurs):
    _demander_ailleurs(client, ailleurs)
    seconde = _demander_ailleurs(client, ailleurs)
    assert seconde["etat"] == "refuse" and "Déjà demandé" in seconde["motif"]


def test_les_genres_qui_naissent_d_un_geste_ne_se_deposent_pas_a_la_main(client, ailleurs):
    r = client.post("/api/demandes", headers=RESP,
                    json={"genre": "amorcer_entre_projets", "album_id": ailleurs["albums"]["d1"],
                          "motif": "m"})
    assert r.status_code == 422, r.text


# =========================================================================== #
# Trois projets : chacun ne répond que de SON travail
# =========================================================================== #
RESP3 = {"Remote-User": "resp3"}


@pytest.fixture
def trois(client, ailleurs):
    """Un troisième projet, « Autre », dont `resp3` est responsable, où l'administrateur a
    amorcé une copie de Le Lotus bleu jusqu'au texte (collection Z) : trois copies du même
    document dans trois projets, dont l'une tirée de l'autre."""
    p3 = _ok(client.post("/api/projets", json={"nom": "Autre"}, headers=ADMIN), 201)["id"]
    _ok(client.put(f"/api/projets/{p3}/membres", headers=ADMIN,
                   json={"principal": "resp3", "role": "responsable"}))
    z = _collection(client, "Collection Z", projet_id=p3)
    _accorder(client, z, "resp3", "ecriture")             # F6 : il y écrit
    r = _prendre(client, z, [_amorcer(ailleurs["docs"]["d1"], "transcription",
                                      ailleurs["albums"]["d1"])], ADMIN)
    copie_z = _ok(r)["documents"][0]["copie_id"]
    assert copie_z
    return {**ailleurs, "p3": p3, "z": z, "copie_z": copie_z}


def test_chaque_responsable_ne_lit_que_ses_copies(client, trois):
    ligne = _demander_ailleurs(client, trois)
    (d2,) = _ok(client.get(f"/api/projets/{trois['repli']}/demandes-recues", headers=RESP2))
    (d3,) = _ok(client.get(f"/api/projets/{trois['p3']}/demandes-recues", headers=RESP3))
    assert d2["id"] == d3["id"] == ligne["demande_id"]
    assert [c["album_id"] for c in d2["copies"]] == [trois["albums"]["d1"]]
    assert [c["album_id"] for c in d3["copies"]] == [trois["copie_z"]]
    # resp2 ne prend pas la copie d'Autre comme source, même en la LISANT — il ne gère pas
    # Autre : le même 404 qu'une copie absente.
    _accorder(client, trois["z"], "resp2", "lecture")
    reponses = [_repondre(client, ligne["demande_id"], "acceptee", RESP2, album_id=a)
                for a in (trois["copie_z"], 999999)]
    assert [r.status_code for r in reponses] == [404, 404]
    # resp3 accepte avec la sienne : la copie neuve en est tirée.
    vue = _ok(_repondre(client, ligne["demande_id"], "acceptee", RESP3,
                        album_id=trois["copie_z"]))
    copie = vue["documents"][0]["copie_id"]
    assert _sql(database.DB_PATH, "SELECT depuis_album_id FROM copie WHERE album_id = ?",
                (copie,))[0]["depuis_album_id"] == trois["copie_z"]


def test_une_demande_que_seul_un_autre_projet_tient_ne_se_lit_pas_ici(client, trois):
    """La copie d'Autre porte une annotation, celle du repli non : jusqu'aux annotations,
    seul Autre tient ce travail — resp2 ne lit pas la demande, et n'y répond pas (404)."""
    pl = _sql(database.DB_PATH, "SELECT id FROM planches WHERE album_id = ?",
              (trois["copie_z"],))[0]["id"]
    bulle = _sql(database.DB_PATH, "SELECT id FROM regions WHERE planche_id = ? "
                                   "AND type = 'bulle'", (pl,))[0]["id"]
    _ok(client.put(f"/api/regions/{bulle}/annotation", headers=ADMIN,
                   json={"note": "à part", "tags": []}))
    ligne = _demander_ailleurs(client, trois, "d1", "annotations")
    assert _ok(client.get(f"/api/projets/{trois['repli']}/demandes-recues",
                          headers=RESP2)) == []
    assert [d["id"] for d in _ok(client.get(f"/api/projets/{trois['p3']}/demandes-recues",
                                            headers=RESP3))] == [ligne["demande_id"]]
    assert _repondre(client, ligne["demande_id"], "refusee", RESP2).status_code == 404


def test_l_administrateur_ne_prend_pas_une_copie_isolee(client, ailleurs):
    """Le recours de l'administrateur ne fait pas sortir une copie d'un projet isolé (bac à
    sable, jeu) : le même 404 qu'une copie absente."""
    ligne = _demander_ailleurs(client, ailleurs, "d2", "decoupage")
    _sql(database.DB_PATH, "UPDATE projet SET jeu = 1 WHERE id = ?", (ailleurs["repli"],))
    r = _repondre(client, ligne["demande_id"], "acceptee", ADMIN,
                  album_id=ailleurs["albums"]["d2"])
    assert r.status_code == 404, r.text


def test_la_regle_sur_la_portee_meme(client, ailleurs, db_path):
    """`Portee.peut_repondre_a` et `peut_nommer_le_demandeur`, posées sans la route : le
    responsable d'un projet qui tient répond et lit le nom ; un membre, un propriétaire de la
    collection source, non ; la portée totale, toujours."""
    import autorisation
    from test_bac_a_sable import _portee
    demande = {"genre": database.DEMANDE_AMORCER_ENTRE_PROJETS,
               "projets": [ailleurs["repli"]]}
    attendu = {"resp2": True, "membre2": False, "proprio2": False, "importeur": False,
               "resp": False}
    for login, oui in attendu.items():
        p = _portee(db_path, {"Remote-User": login})
        assert p.peut_repondre_a(demande) is oui, login
        assert p.peut_nommer_le_demandeur("quelquun", consentement=demande) is oui, login
    assert autorisation.TOTALE.peut_repondre_a(demande) is True
    assert _portee(db_path, RESP2).peut_repondre_a({**demande, "projets": []}) is False
