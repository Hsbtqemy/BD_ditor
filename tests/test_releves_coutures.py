"""Les coutures : ce que les relevés obligent à toucher ailleurs (ANN-7, tranche 1 ; cadrage
R6, R11 ; G6, G9, G18, G20 b).

Chacun de ces chemins ignorait les relevés, et la plupart échouaient OUVERT : un oubli ne
faisait tomber aucun test. Chaque test ci-dessous JOUE le chemin, sur un relevé posé par
l'API, et en vérifie l'effet.
"""
import sqlite3

import pytest

import database
import pipeline.segmentation as seg
from conftest import ADMIN, make_png
from grilles_decor import (BEA, IVAN, LEA, STAG, bac_de_bea, grille_active, importer, monter,
                           ok)


@pytest.fixture
def decor(client, db_path, derriere_proxy):
    d = monter(client, db_path)
    d.update(grille_active(client, d["p"]))
    return d


def _q(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, p)]
    finally:
        c.close()


def poser(client, d, qui=STAG, **champs):
    r = client.post("/api/releves", headers=qui,
                    json={"grille_id": d["grille_id"], "version": 1, **champs})
    assert r.status_code == 201, r.text
    return r.json()


def _etat(client, d, rid):
    lus = ok(client.get(f"/api/planches/{d['planche']}/releves", headers=LEA))["releves"]
    return next(x for x in lus if x["id"] == rid)


# --------------------------------------------------------------------------- #
# Le ré-ancrage (R6)
# --------------------------------------------------------------------------- #
def test_un_mot_deplace_suit_un_mot_change_met_a_revoir_et_ctrl_z_le_rend(client, decor):
    b = decor["zones"]["bulle"]
    r = poser(client, decor, region_id=b, entree_cle="cri", mots=[6])          # « VIENT »
    ok(client.put(f"/api/regions/{b}", headers=STAG,
                  json={"ocr_texte": "OH ! J'SAIS PAS, IL NE VIENT PAS !!!"}))
    x = _etat(client, decor, r["id"])
    assert x["etat"] == "normal" and x["mots"] == [{"position": 0, "rang": 8,
                                                     "forme": "VIENT"}]
    # La casse normalisée ne désancre rien.
    ok(client.put(f"/api/regions/{b}", headers=STAG,
                  json={"ocr_texte": "Oh ! J'sais pas, il ne vient pas !!!"}))
    x = _etat(client, decor, r["id"])
    assert x["etat"] == "normal" and x["mots"][0]["forme"] == "vient"
    # Le mot changé : à revoir, sa forme reste, sa place d'aujourd'hui est nulle.
    ok(client.put(f"/api/regions/{b}", headers=STAG,
                  json={"ocr_texte": "Oh ! J'sais pas, il ne viendra pas !!!"}))
    x = _etat(client, decor, r["id"])
    assert x["etat"] == "a_revoir" and x["causes"] == ["texte_change"]
    assert x["mots"] == [{"position": 0, "rang": 8, "forme": "vient", "rang_actuel": None}]
    # Ctrl+Z du texte : le relevé redevient normal, sans rien réécrire.
    ok(client.post("/api/undo", headers=STAG))
    x = _etat(client, decor, r["id"])
    assert x["etat"] == "normal" and x["mots"][0]["forme"] == "vient"


def test_redesigner_le_passage_le_reancre_sur_le_texte_d_aujourd_hui(client, decor):
    b = decor["zones"]["bulle"]
    r = poser(client, decor, region_id=b, entree_cle="cri", mots=[6])
    ok(client.put(f"/api/regions/{b}", headers=STAG, json={"ocr_texte": "IL VIENDRA"}))
    assert _etat(client, decor, r["id"])["etat"] == "a_revoir"
    x = ok(client.put(f"/api/releves/{r['id']}", headers=STAG, json={"mots": [1]}))
    assert x["etat"] == "normal" and x["mots"][0]["forme"] == "VIENDRA"


# --------------------------------------------------------------------------- #
# Repartir de zéro, le niveau de travail
# --------------------------------------------------------------------------- #
def test_repartir_de_zero_retire_releves_passes_et_doutes(client, decor, db_path):
    b = decor["zones"]["bulle"]
    r = poser(client, decor, region_id=b, entree_cle="cri", mots=[8])
    poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    ok(client.post(f"/api/releves/{r['id']}/doutes", headers=STAG, json={"texte": "?"}), 201)
    ok(client.put(f"/api/planches/{decor['planche']}/passes/{decor['grille_id']}",
                  headers=STAG, json={}))
    c = database.get_connection()
    try:
        assert database.niveau_de_travail(c, decor["album"]) == database.rang_du_cran(
            "annotations")
        apercu = database.compter_repartir(c, decor["album"], "grammaire")
        comptes = database.repartir_de_zero(c, decor["album"], "grammaire")
        c.commit()
    finally:
        c.close()
    assert comptes["releves"] == 2 and comptes["passes"] == 1
    assert {k: apercu[k] for k in ("releves", "passes")} == {"releves": 2, "passes": 1}
    for t in ("releve", "releve_mot", "doute", "doute_message", "passe"):
        assert _q(db_path, f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] == 0, t


def test_un_releve_seul_fait_le_niveau_annotations(client, decor):
    poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    c = database.get_connection()
    try:
        assert database.niveau_de_travail(c, decor["album"],
                                          decor["planche"]) == database.rang_du_cran(
            "annotations")
    finally:
        c.close()


# --------------------------------------------------------------------------- #
# Copier au cran `annotations`
# --------------------------------------------------------------------------- #
def _copie(conn, album, collection, cran="annotations", par="lea"):
    doc = database.document_d_album(conn, album)
    return database.creer_copie(conn, doc, collection, par=par, depuis=album, cran=cran)


def test_une_copie_dans_le_projet_emporte_releves_et_passes_pas_les_doutes(client, decor,
                                                                          db_path):
    b = decor["zones"]["bulle"]
    r = poser(client, decor, region_id=b, entree_cle="reponse-a",
              lien_region_id=decor["autre_bulle"])
    poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    ok(client.post(f"/api/releves/{r['id']}/doutes", headers=STAG, json={"texte": "?"}), 201)
    ok(client.put(f"/api/regions/{b}/passes/{decor['grille_id']}", headers=STAG, json={}))
    c = database.get_connection()
    try:
        apercu = database.compter_le_travail(c, decor["album"], "annotations", decor["c2"])
        copie = _copie(c, decor["album"], decor["c2"])
        c.commit()
    finally:
        c.close()
    assert apercu["copies"]["releves"] == 2 and apercu["laisses"]["releves"] == 0
    copies = _q(db_path, "SELECT r.* FROM releve r LEFT JOIN regions g ON g.id = r.region_id "
                         "JOIN planches p ON p.id = COALESCE(g.planche_id, r.planche_id) "
                         "WHERE p.album_id = ? ORDER BY r.id", (copie,))
    assert len(copies) == 2 and all(x["origine_id"] for x in copies)
    region = next(x for x in copies if x["region_id"])
    assert region["auteur"] == "stag"                       # dans un même projet
    nouvelle_autre = _q(db_path, "SELECT region_id FROM region_origine WHERE "
                                 "region_source_id = ?", (decor["autre_bulle"],))
    nouvelle_autre = [x["region_id"] for x in nouvelle_autre
                      if _q(db_path, "SELECT 1 AS x FROM regions g JOIN planches p ON "
                                     "p.id = g.planche_id WHERE g.id = ? AND p.album_id = ?",
                            (x["region_id"], copie))]
    assert region["lien_region_id"] == nouvelle_autre[0]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM doute d JOIN releve r ON r.id = d.releve_id "
                       "WHERE r.origine_id IS NOT NULL")[0]["n"] == 0
    assert _q(db_path, "SELECT COUNT(*) AS n FROM passe")[0]["n"] == 2


def test_entre_deux_projets_rien_ne_suit_encore_et_l_apercu_le_dit(client, decor, db_path):
    poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    c = database.get_connection()
    try:
        apercu = database.compter_le_travail(c, decor["album"], "annotations", decor["d"])
        copie = _copie(c, decor["album"], decor["d"], par="zoe")
        c.commit()
    finally:
        c.close()
    assert apercu["copies"]["releves"] == 0 and apercu["laisses"]["releves"] == 1
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve WHERE origine_id IS NOT NULL")[0][
        "n"] == 0
    assert copie


# --------------------------------------------------------------------------- #
# Détruire, supprimer une planche
# --------------------------------------------------------------------------- #
def test_supprimer_une_planche_ou_un_album_qui_porte_un_releve_de_surface(client, decor,
                                                                          db_path):
    poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    ok(client.delete(f"/api/planches/{decor['planche']}", headers=ADMIN), 204)
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0
    a = decor["album"]
    p2 = ok(client.post(f"/api/albums/{a}/import", headers=LEA,
                        files={"file": ("p.png", make_png(), "image/png")}), 201)["id"]
    poser(client, decor, planche_id=p2, entree_cle="ambiance")
    ok(client.delete(f"/api/albums/{a}", headers=ADMIN), 204)
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0


def test_une_planche_qui_porte_un_releve_de_surface_ne_s_efface_pas_en_silence(client,
                                                                               decor):
    """La clé SANS action (Q5) : un chemin qui oublierait les relevés de surface échoue
    bruyamment, il n'efface rien en silence."""
    poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    c = database.get_connection()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("DELETE FROM planches WHERE id = ?", (decor["planche"],))
    finally:
        c.rollback()
        c.close()


# --------------------------------------------------------------------------- #
# La re-segmentation (G20 b)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("porte", ["releve", "situation"])
def test_la_resegmentation_garde_une_case_qui_porte_un_releve_ou_une_situation(
        client, decor, monkeypatch, porte):
    monkeypatch.setattr("main.kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[0, 0, 50, 50]]})
    pl = decor["planche"]
    ok(client.post(f"/api/planches/{pl}/segmenter", headers=LEA))
    case = next(x for x in ok(client.get(f"/api/planches/{pl}/regions", headers=LEA))
                if x["type"] == "case" and x["source"] == "kumiko")
    if porte == "releve":
        poser(client, decor, region_id=case["id"], entree_cle="regard-camera")
    else:
        dim = ok(client.post("/api/attributs/dimensions", headers=LEA,
                             json={"cible": "case", "nom": "lieu"}), 201)["id"]
        val = ok(client.post(f"/api/attributs/dimensions/{dim}/valeurs", headers=LEA,
                             json={"valeur": "cuisine"}), 201)["id"]
        ok(client.put(f"/api/regions/{case['id']}/attributs", headers=LEA,
                      json={"valeur_id": val}))
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[300, 400, 50, 50]]})
    ok(client.post(f"/api/planches/{pl}/segmenter", headers=LEA))
    assert any(x["id"] == case["id"] for x in ok(client.get(f"/api/planches/{pl}/regions",
                                                            headers=LEA)))


# --------------------------------------------------------------------------- #
# Le bac à sable, le projet (G6, G18)
# --------------------------------------------------------------------------- #
def test_un_bac_a_sable_efface_emporte_ses_grilles(client, decor, db_path):
    bac = bac_de_bea(client)
    g = grille_active(client, bac["projet"], qui=BEA)
    r = client.post("/api/releves", headers=IVAN, json={
        "grille_id": g["grille_id"], "version": 1, "region_id": bac["bulle"],
        "entree_cle": "cri", "mots": [0]})
    assert r.status_code == 201, r.text
    ok(client.post("/api/bac-a-sable/remise-a-neuf", headers=BEA), 200, 201)
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille WHERE projet_id = ?",
              (bac["projet"],))[0]["n"] == 0
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0


def test_un_projet_qui_possede_une_grille_ne_se_supprime_pas(client, decor, db_path):
    projet = ok(client.post("/api/projets", headers=ADMIN, json={"nom": "Vide"}), 201)["id"]
    gid = importer(client, projet, ADMIN, nom="À elle")["grille_id"]
    r = client.delete(f"/api/projets/{projet}", headers=ADMIN)
    assert r.status_code == 409 and "grille" in r.json()["detail"]
    ok(client.delete(f"/api/grilles/{gid}/versions/1", headers=ADMIN), 204)
    ok(client.delete(f"/api/projets/{projet}", headers=ADMIN), 204)


# --------------------------------------------------------------------------- #
# « Personne d'autre n'y a travaillé », la trace d'un geste, le départ d'un compte
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("cible", ["region", "planche"])
def test_un_releve_d_un_autre_interdit_la_suppression_directe(client, decor, db_path, cible):
    """L'importatrice ne supprime pas SEULE un album où un autre a posé un relevé : la règle
    « travail d'autrui » lit les relevés (R11) — de la région comme de la surface."""
    # La créatrice SEULE : une portée qui écrit dans la collection de l'album, sans en être
    # propriétaire ni responsable du projet — le chemin 1 de `clause_suppression_directe`.
    c = database.get_connection()
    try:
        import autorisation
        p = autorisation.Portee(ecriture=frozenset({decor["c"]}), utilisateur="lea")
        ou, params = p.clause_suppression_directe("a.id")
        avant = c.execute(f"SELECT {ou} FROM albums a WHERE a.id = ?",
                          (*params, decor["album"])).fetchone()[0]
    finally:
        c.close()
    assert avant, "le décor laisse déjà quelqu'un d'autre travailler sur l'album"
    if cible == "region":
        poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    else:
        poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    c = database.get_connection()
    try:
        apres = c.execute(f"SELECT {ou} FROM albums a WHERE a.id = ?",
                          (*params, decor["album"])).fetchone()[0]
        n = c.execute("SELECT COUNT(*) FROM geste_sur_copie WHERE album_id = ? "
                      "AND agent = 'stag'", (decor["album"],)).fetchone()[0]
    finally:
        c.close()
    assert not apres
    assert n == 1                                    # la trace du geste, pour la dernière copie


@pytest.mark.parametrize("cible", ["region", "planche"])
def test_la_regle_du_travail_d_autrui_lit_le_releve_lui_meme(client, decor, cible):
    """La source de la règle, sans la trace du geste : sur la dernière copie, `geste_sur_copie`
    suffirait à refuser, et la lecture des relevés par le journal resterait sans témoin. Les
    actes `releve` (la région) et `releve_planche` (la planche) font la règle à eux seuls —
    celle que lisent aussi les suppressions d'une copie qui a une sœur."""
    import autorisation
    sql, params = autorisation._sql_travail_d_autrui("a.id", "lea")

    def autrui():
        c = database.get_connection()
        try:
            return c.execute(f"SELECT {sql} FROM albums a WHERE a.id = ?",
                             (*params, decor["album"])).fetchone()[0]
        finally:
            c.close()

    assert not autrui(), "le décor laisse déjà quelqu'un d'autre travailler sur l'album"
    if cible == "region":
        poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    else:
        poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    assert autrui()


def test_les_releves_d_un_bac_efface_ne_comptent_pas_dans_les_traces(client, decor):
    import comptes
    bac = bac_de_bea(client)
    g = grille_active(client, bac["projet"], qui=BEA)
    r = client.post("/api/releves", headers=IVAN, json={
        "grille_id": g["grille_id"], "version": 1, "region_id": bac["bulle"],
        "entree_cle": "cri", "mots": [0]})
    assert r.status_code == 201
    # Le témoin : le même geste HORS d'un bac à sable compte.
    poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[0])
    c = database.get_connection()
    try:
        actes = comptes.traces(c)[0]
        assert "ivan" not in actes and actes.get("stag", 0) >= 1
    finally:
        c.close()
