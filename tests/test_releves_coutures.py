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
from grilles_decor import (BEA, IVAN, LEA, OLGA, STAG, bac_de_bea, csv_de, grille_active,
                           importer, monter, ok)


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
def test_un_releve_d_un_autre_se_lit_avant_d_effacer(client, decor, cible):
    """Tranche 3c (F3) — RÉÉCRIT sur « qui perd quoi » : le travail d'autrui ne décide plus
    rien, il se LIT avant d'effacer. Un relevé posé par un autre que l'importatrice — sur la
    région comme sur la surface (R11) — apparaît sous `GET /api/albums/{id}/travail-des-autres`
    lu par l'administrateur."""
    def agents():
        r = client.get(f"/api/albums/{decor['album']}/travail-des-autres", headers=ADMIN)
        assert r.status_code == 200, r.text
        return {e["agent"] for e in r.json()["travail_des_autres"]}

    assert "stag" not in agents(), "le décor laisse déjà la stagiaire travailler sur l'album"
    if cible == "region":
        poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    else:
        poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    assert "stag" in agents()


@pytest.mark.parametrize("cible", ["region", "planche"])
def test_qui_perd_quoi_lit_le_releve_lui_meme(client, decor, cible):
    """La source, lue seule (`autorisation.sql_actes_sur_album`) : les actes `releve` (la
    région) et `releve_planche` (la planche) suffisent à faire compter le travail d'un autre
    (tranche 3c : `geste_sur_copie` ne se lit plus, la mesure est la seule lecture)."""
    assert not _autrui(decor["album"], "lea"),         "le décor laisse déjà quelqu'un d'autre travailler sur l'album"
    if cible == "region":
        poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    else:
        poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    assert _autrui(decor["album"], "lea")


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


# --------------------------------------------------------------------------- #
# Le travail RECOPIÉ sur la surface d'une planche (relecture croisée, constats 2 et 3)
# --------------------------------------------------------------------------- #
def _autrui(album, login):
    """Un autre que `login` a-t-il travaillé sur `album`, selon les dix sources de « qui
    perd quoi » (`autorisation.sql_actes_sur_album`) ? La question que posait la règle de
    suppression jusqu'à la tranche 3c (F3), et qui ne sert plus qu'à MONTRER."""
    import autorisation
    c = database.get_connection()
    try:
        return bool(c.execute(
            f"SELECT EXISTS (SELECT 1 FROM ({autorisation.sql_actes_sur_album(str(int(album)))}) "
            "WHERE agent IS NULL OR agent IS NOT ?)", (login,)).fetchone()[0])
    finally:
        c.close()


def _copie_par(album, collection, par):
    c = database.get_connection()
    try:
        cid = _copie(c, album, collection, par=par)
        c.commit()
        return cid
    finally:
        c.close()


def _album_de_la_stagiaire(client, d):
    a = ok(client.post("/api/albums", headers=STAG,
                       json={"titre": "Album S", "collection_id": d["c"]}), 201)["id"]
    pl = ok(client.post(f"/api/albums/{a}/import", headers=STAG,
                        files={"file": ("p.png", make_png(), "image/png")}), 201)["id"]
    return a, pl


def test_une_passe_de_surface_recopiee_compte_meme_apres_une_autre_passe(client, decor,
                                                                        db_path):
    """Constat 2 — la passe qu'Olga a marquée à la source, recopiée sur la planche de la copie,
    reste le travail d'Olga quand la stagiaire en marque une AUTRE sur la même planche. La
    huitième source la lisait par l'absence d'un acte `passe` sur la planche."""
    g = decor["grille_id"]
    a, pl = _album_de_la_stagiaire(client, decor)
    ok(client.put(f"/api/planches/{pl}/passes/{g}", headers=OLGA, json={}))
    copie = _copie_par(a, decor["c2"], "stag")
    (pl_copie,) = [x["id"] for x in _q(db_path, "SELECT id FROM planches WHERE album_id = ?",
                                       (copie,))]
    assert _q(db_path, "SELECT par, recopiee FROM passe WHERE planche_id = ?", (pl_copie,)) \
        == [{"par": "olga", "recopiee": 1}]
    assert _autrui(copie, "stag")
    ok(client.put(f"/api/planches/{pl_copie}/passes/{g}", headers=STAG,
                  json={"rubrique_cle": "echanges"}))
    assert _autrui(copie, "stag")
    # La marquer de nouveau, telle quelle, n'en fait pas la passe de la stagiaire.
    ok(client.put(f"/api/planches/{pl_copie}/passes/{g}", headers=STAG, json={}))
    assert _q(db_path, "SELECT par, recopiee FROM passe WHERE planche_id = ? "
                       "AND rubrique_cle = ''", (pl_copie,)) == [{"par": "olga", "recopiee": 1}]
    assert _autrui(copie, "stag")
    # Rouverte puis marquée : une ligne neuve, à elle, sans la marque.
    ok(client.delete(f"/api/planches/{pl_copie}/passes/{g}", headers=STAG), 204)
    ok(client.put(f"/api/planches/{pl_copie}/passes/{g}", headers=STAG, json={}))
    assert _q(db_path, "SELECT par, recopiee FROM passe WHERE planche_id = ? "
                       "AND rubrique_cle = ''", (pl_copie,)) == [{"par": "stag", "recopiee": 0}]


def test_une_passe_de_region_recopiee_porte_la_marque_et_ctrl_z_la_rend(client, decor,
                                                                       db_path):
    """La marque suit la passe d'une région recopiée, et la suppression de cette région
    rétablie par Ctrl+Z la rend avec sa marque."""
    b = decor["zones"]["bulle"]
    ok(client.put(f"/api/regions/{b}/passes/{decor['grille_id']}", headers=OLGA, json={}))
    copie = _copie_par(decor["album"], decor["c2"], "stag")
    (passe,) = _q(db_path, "SELECT s.* FROM passe s JOIN regions g ON g.id = s.region_id "
                           "JOIN planches p ON p.id = g.planche_id WHERE p.album_id = ?",
                  (copie,))
    assert passe["recopiee"] == 1 and passe["par"] == "olga"
    ok(client.delete(f"/api/regions/{passe['region_id']}", headers=STAG), 204)
    ok(client.post("/api/undo", headers=STAG))
    assert _q(db_path, "SELECT par, recopiee FROM passe WHERE id = ?", (passe["id"],)) == [
        {"par": "olga", "recopiee": 1}]


ENTETE_GRILLE = ["cle", "rubrique", "rubrique_cle", "forme", "libelle", "variante_cle",
                 "variante", "structure", "definition", "exemples", "piege", "liste",
                 "precision", "lien", "cible", "cardinalite"]


def _grille_de_planche(client, d):
    lignes = [ENTETE_GRILLE,
              ["climat", "A", "a", "variantes", "climat", "", "", "", "", "", "", "", "", "",
               "planche", ""],
              ["climat", "", "", "", "", "calme", "calme", "", "", "", "", "", "", "", "", ""],
              ["climat", "", "", "", "", "tendu", "tendu", "", "", "", "", "", "", "", "", ""]]
    gid = importer(client, d["p"], LEA, entrees=csv_de(lignes), listes=None, nom="Climats",
                   porte_sur="planche")["grille_id"]
    ok(client.post(f"/api/grilles/{gid}/versions/1/publication", headers=LEA))
    ok(client.put(f"/api/projets/{d['p']}/grilles/{gid}/activation", headers=LEA,
                  json={"version": 1}))
    return gid


@pytest.mark.parametrize("qui, attendu", [(OLGA, True), (STAG, False)])
def test_un_releve_de_surface_recopie_porte_ce_qu_un_autre_y_a_fait_a_la_source(
        client, decor, db_path, qui, attendu):
    """Constat 3 — la stagiaire pose un relevé sur la surface ; Olga change sa variante à la
    SOURCE ; la copie emporte la variante d'Olga. Le relevé copié ne compte plus par son seul
    `auteur` : les actes sur sa source, antérieurs à la copie, sont du travail d'autrui —
    sauf ceux de la stagiaire elle-même (le témoin)."""
    gid = _grille_de_planche(client, decor)
    a, pl = _album_de_la_stagiaire(client, decor)
    r = ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": gid, "version": 1, "planche_id": pl, "entree_cle": "climat",
        "variante_cle": "calme"}), 201)
    ok(client.put(f"/api/releves/{r['id']}", headers=qui,
                  json={"variante_cle": "tendu", "vu": {"variante_cle": "calme"}}))
    copie = _copie_par(a, decor["c2"], "stag")
    (rec,) = _q(db_path, "SELECT r.* FROM releve r JOIN planches p ON p.id = r.planche_id "
                         "WHERE p.album_id = ?", (copie,))
    assert rec["variante_cle"] == "tendu" and rec["origine_id"] == r["id"]
    assert _autrui(copie, "stag") is attendu


def test_un_acte_a_la_source_apres_la_copie_ne_compte_pas(client, decor, db_path):
    """La borne : ce qu'Olga fait sur la source APRÈS la copie n'est pas dans la copie."""
    gid = _grille_de_planche(client, decor)
    a, pl = _album_de_la_stagiaire(client, decor)
    r = ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": gid, "version": 1, "planche_id": pl, "entree_cle": "climat",
        "variante_cle": "calme"}), 201)
    copie = _copie_par(a, decor["c2"], "stag")
    # La copie est datée à la seconde : l'acte d'Olga doit lui être postérieur.
    c = database.get_connection()
    try:
        c.execute("UPDATE copie SET creee_le = datetime('now', '-1 minute') "
                  "WHERE album_id = ?", (copie,))
        c.commit()
    finally:
        c.close()
    ok(client.put(f"/api/releves/{r['id']}", headers=OLGA,
                  json={"variante_cle": "tendu", "vu": {"variante_cle": "calme"}}))
    assert not _autrui(copie, "stag")


@pytest.mark.parametrize("olga_modifie", [False, True])
def test_un_releve_de_region_recopie_compte_ce_qu_un_autre_y_a_fait(client, decor, db_path,
                                                                    olga_modifie):
    """Le témoin de la sixième source, qui reste tel quel : sur une RÉGION, la modification
    d'Olga à la source compte, et sans elle rien ne compte."""
    a, pl = _album_de_la_stagiaire(client, decor)
    b = ok(client.post(f"/api/planches/{pl}/regions", headers=STAG,
                       json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9}), 201)["id"]
    r = poser(client, decor, qui=STAG, region_id=b, entree_cle="ton-de-voix",
              variante_cle="chuchote")
    if olga_modifie:
        ok(client.put(f"/api/releves/{r['id']}", headers=OLGA,
                      json={"variante_cle": "crie", "vu": {"variante_cle": "chuchote"}}))
    copie = _copie_par(a, decor["c2"], "stag")
    assert _autrui(copie, "stag") == olga_modifie


def test_une_passe_posee_ensuite_sur_la_copie_ne_ranime_pas_la_passe_source(client, decor,
                                                                           db_path):
    """La doctrine de la 3b sur une RÉGION (décision du pilotage, 2026-10-26) : la passe
    d'Olga, recopiée sur la bulle de la copie, compte tant qu'elle vit ; rouverte puis marquée
    par la stagiaire, la passe neuve (à 0) ne fait plus compter l'acte d'Olga à la source."""
    g = decor["grille_id"]
    a, pl = _album_de_la_stagiaire(client, decor)
    b = ok(client.post(f"/api/planches/{pl}/regions", headers=STAG,
                       json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9}), 201)["id"]
    ok(client.put(f"/api/regions/{b}/passes/{g}", headers=OLGA, json={}))
    copie = _copie_par(a, decor["c2"], "stag")
    (b_copie,) = [x["region_id"] for x in _q(
        db_path, "SELECT o.region_id FROM region_origine o JOIN regions g ON g.id = o.region_id "
                 "JOIN planches p ON p.id = g.planche_id WHERE o.region_source_id = ? "
                 "AND p.album_id = ?", (b, copie))]
    assert _autrui(copie, "stag")
    ok(client.delete(f"/api/regions/{b_copie}/passes/{g}", headers=STAG), 204)
    ok(client.put(f"/api/regions/{b_copie}/passes/{g}", headers=STAG, json={}))
    assert _q(db_path, "SELECT par, recopiee FROM passe WHERE region_id = ?", (b_copie,)) == [
        {"par": "stag", "recopiee": 0}]
    assert not _autrui(copie, "stag")


# --------------------------------------------------------------------------- #
# Contre-relecture (2026-10-26) — la chaîne d'`origine_id`, `modifie_par`, les doutes, et
# les deux couches de la cible `releve`
# --------------------------------------------------------------------------- #
def _releve_de_surface_modifie_par_olga(client, d, db_path):
    gid = _grille_de_planche(client, d)
    a, pl = _album_de_la_stagiaire(client, d)
    r = ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": gid, "version": 1, "planche_id": pl, "entree_cle": "climat",
        "variante_cle": "calme"}), 201)
    ok(client.put(f"/api/releves/{r['id']}", headers=OLGA,
                  json={"variante_cle": "tendu", "vu": {"variante_cle": "calme"}}))
    copie = _copie_par(a, d["c2"], "stag")
    return a, pl, r, copie


def test_un_releve_source_retire_n_arrete_pas_la_chaine(client, decor, db_path):
    """Contre-relecture, r3 — la modification d'Olga vit dans la copie ; la stagiaire retire
    le relevé SOURCE : ses actes, écrits sous la planche source, comptent encore. Le patron de
    la sixième source, qui survit à la suppression de la région source."""
    gid = _grille_de_planche(client, decor)
    a, pl = _album_de_la_stagiaire(client, decor)
    r = ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": gid, "version": 1, "planche_id": pl, "entree_cle": "climat",
        "variante_cle": "calme"}), 201)
    ok(client.put(f"/api/releves/{r['id']}", headers=OLGA,
                  json={"variante_cle": "tendu", "vu": {"variante_cle": "calme"}}))
    # La stagiaire y revient ensuite à la source : `modifie_par` ne nomme plus Olga, seul le
    # journal de la source dit ce qu'elle y a fait.
    ok(client.put(f"/api/releves/{r['id']}", headers=STAG,
                  json={"variante_cle": "calme", "vu": {"variante_cle": "tendu"}}))
    copie = _copie_par(a, decor["c2"], "stag")
    assert _q(db_path, "SELECT r.modifie_par FROM releve r JOIN planches p ON "
                       "p.id = r.planche_id WHERE p.album_id = ?", (copie,)) == [
        {"modifie_par": "stag"}]
    assert _autrui(copie, "stag")
    ok(client.delete(f"/api/releves/{r['id']}", headers=STAG), 204)
    assert _autrui(copie, "stag")


def test_le_dernier_modificateur_a_la_source_se_lit_sur_la_copie(client, decor, db_path):
    """`modifie_par`, que la copie emporte, compte même quand le journal de la source ne dit
    plus rien (simulé : ses actes ne désignent plus aucune planche) ; une modification faite
    ensuite DANS la copie par la stagiaire le remplace."""
    _a, pl, _r, copie = _releve_de_surface_modifie_par_olga(client, decor, db_path)
    c = database.get_connection()
    try:
        c.execute("UPDATE evenement SET cible_id = -1 WHERE cible_table = 'releve_planche' "
                  "AND cible_id = ?", (pl,))
        c.commit()
    finally:
        c.close()
    assert _autrui(copie, "stag")
    (rec,) = _q(db_path, "SELECT r.id FROM releve r JOIN planches p ON p.id = r.planche_id "
                         "WHERE p.album_id = ?", (copie,))
    c = database.get_connection()
    try:
        c.execute("UPDATE copie SET creee_le = datetime('now', '-1 minute') "
                  "WHERE album_id = ?", (copie,))
        c.commit()
    finally:
        c.close()
    ok(client.put(f"/api/releves/{rec['id']}", headers=STAG,
                  json={"variante_cle": "calme", "vu": {"variante_cle": "tendu"}}))
    assert not _autrui(copie, "stag")


def test_la_suppression_de_la_region_source_ne_change_rien_a_la_sixieme(client, decor,
                                                                       db_path):
    """Le témoin (r3bis) : sur une région, la sixième source survit à la région source."""
    a, pl = _album_de_la_stagiaire(client, decor)
    b = ok(client.post(f"/api/planches/{pl}/regions", headers=STAG,
                       json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9}), 201)["id"]
    r = poser(client, decor, qui=STAG, region_id=b, entree_cle="ton-de-voix",
              variante_cle="chuchote")
    ok(client.put(f"/api/releves/{r['id']}", headers=OLGA,
                  json={"variante_cle": "crie", "vu": {"variante_cle": "chuchote"}}))
    copie = _copie_par(a, decor["c2"], "stag")
    ok(client.delete(f"/api/releves/{r['id']}", headers=STAG), 204)
    ok(client.delete(f"/api/regions/{b}", headers=STAG), 204)
    assert _autrui(copie, "stag")


def test_un_doute_a_la_source_ne_compte_pas_sur_la_copie(client, decor, db_path):
    """Contre-relecture, r4 — les doutes ne suivent pas une copie (« À la copie, les passes
    suivent, les doutes non ») : celui qu'Olga a ouvert sur le relevé source n'est pas un
    travail sur la copie (décision du pilotage, 2026-10-26)."""
    a, pl = _album_de_la_stagiaire(client, decor)
    r = poser(client, decor, qui=STAG, planche_id=pl, entree_cle="ambiance")
    ok(client.post(f"/api/releves/{r['id']}/doutes", headers=OLGA, json={"texte": "?"}), 201)
    copie = _copie_par(a, decor["c2"], "stag")
    assert not _autrui(copie, "stag")


def test_un_releve_recopie_ne_ranime_pas_la_passe_source(client, decor, db_path):
    """Contre-relecture, r6 — la passe d'Olga sur la région source, rouverte puis remarquée
    dans la copie, ne compte plus, même quand un relevé RECOPIÉ (celui de la stagiaire) vit
    sur la région : l'acte dit sa couche, et chaque couche vit à part."""
    g = decor["grille_id"]
    a, pl = _album_de_la_stagiaire(client, decor)
    b = ok(client.post(f"/api/planches/{pl}/regions", headers=STAG,
                       json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9}), 201)["id"]
    poser(client, decor, qui=STAG, region_id=b, entree_cle="ton-de-voix",
          variante_cle="chuchote")
    ok(client.put(f"/api/regions/{b}/passes/{g}", headers=OLGA, json={}))
    copie = _copie_par(a, decor["c2"], "stag")
    (b_copie,) = [x["region_id"] for x in _q(
        db_path, "SELECT o.region_id FROM region_origine o JOIN regions g ON g.id = o.region_id "
                 "JOIN planches p ON p.id = g.planche_id WHERE o.region_source_id = ? "
                 "AND p.album_id = ?", (b, copie))]
    assert _autrui(copie, "stag")
    ok(client.delete(f"/api/regions/{b_copie}/passes/{g}", headers=STAG), 204)
    ok(client.put(f"/api/regions/{b_copie}/passes/{g}", headers=STAG, json={}))
    assert not _autrui(copie, "stag")


def test_le_releve_d_un_autre_a_la_source_vit_par_sa_copie(client, decor, db_path):
    """Le pendant : un relevé d'Olga sur la région source compte tant que SA copie vit sur la
    région de la copie — et plus quand on la retire, même si un autre relevé recopié y vit."""
    a, pl = _album_de_la_stagiaire(client, decor)
    b = ok(client.post(f"/api/planches/{pl}/regions", headers=STAG,
                       json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9}), 201)["id"]
    ok(client.put(f"/api/regions/{b}", headers=STAG, json={"ocr_texte": "AAAH !"}))
    poser(client, decor, qui=STAG, region_id=b, entree_cle="ton-de-voix",
          variante_cle="chuchote")
    poser(client, decor, qui=OLGA, region_id=b, entree_cle="cri", mots=[0])
    copie = _copie_par(a, decor["c2"], "stag")
    assert _autrui(copie, "stag")
    (olga_copie,) = _q(db_path, "SELECT r.id FROM releve r JOIN regions g ON g.id = r.region_id "
                                "JOIN planches p ON p.id = g.planche_id WHERE p.album_id = ? "
                                "AND r.entree_cle = 'cri'", (copie,))
    ok(client.delete(f"/api/releves/{olga_copie['id']}", headers=STAG), 204)
    assert not _autrui(copie, "stag")


@pytest.mark.parametrize("olga_pose", [False, True])
def test_un_doute_d_un_autre_sur_la_region_source_ne_compte_pas_sur_la_copie(
        client, decor, db_path, olga_pose):
    """Les doutes ne suivent pas une copie, donc ils ne comptent nulle part comme travail
    recopié (décision du pilotage, 2026-10-26) : le doute d'Olga sur un relevé de la région
    source n'est pas un travail sur la copie, même tant que la copie de ce relevé y vit — son
    RELEVÉ, s'il est d'elle, si."""
    a, pl = _album_de_la_stagiaire(client, decor)
    b = ok(client.post(f"/api/planches/{pl}/regions", headers=STAG,
                       json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9}), 201)["id"]
    r = poser(client, decor, qui=OLGA if olga_pose else STAG, region_id=b,
              entree_cle="ton-de-voix", variante_cle="chuchote")
    ok(client.post(f"/api/releves/{r['id']}/doutes", headers=OLGA, json={"texte": "?"}), 201)
    copie = _copie_par(a, decor["c2"], "stag")
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve r JOIN regions g ON g.id = "
                       "r.region_id JOIN planches p ON p.id = g.planche_id "
                       "WHERE p.album_id = ? AND r.origine_id = ?", (copie, r["id"]))[0][
        "n"] == 1
    assert _autrui(copie, "stag") is olga_pose


# --------------------------------------------------------------------------- #
# Contre-relecture n°2 — copie de copie (n3, n3bis)
# --------------------------------------------------------------------------- #
def test_copie_de_copie_la_modification_d_olga_sur_une_region_compte(client, decor, db_path):
    """n3 — Olga modifie le relevé de la stagiaire à la PREMIÈRE source ; la copie de la copie
    emporte sa variante. Au-delà du premier maillon, la forme fermée — un relevé recopié vit
    sur la région — compte trop plutôt que trop peu (consigne du pilotage)."""
    a, pl = _album_de_la_stagiaire(client, decor)
    b = ok(client.post(f"/api/planches/{pl}/regions", headers=STAG,
                       json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9}), 201)["id"]
    r = poser(client, decor, qui=STAG, region_id=b, entree_cle="ton-de-voix",
              variante_cle="chuchote")
    ok(client.put(f"/api/releves/{r['id']}", headers=OLGA,
                  json={"variante_cle": "crie", "vu": {"variante_cle": "chuchote"}}))
    c1 = _copie_par(a, decor["c2"], "stag")
    assert _autrui(c1, "stag")
    c2 = _copie_par(c1, decor["c"], "stag")
    (rec,) = _q(db_path, "SELECT r.variante_cle FROM releve r JOIN regions g "
                         "ON g.id = r.region_id JOIN planches p ON p.id = g.planche_id "
                         "WHERE p.album_id = ?", (c2,))
    assert rec["variante_cle"] == "crie"
    assert _autrui(c2, "stag")


def test_copie_de_copie_la_modification_d_olga_en_surface_compte(client, decor, db_path):
    """n3bis, le témoin : en surface, la neuvième source remonte la chaîne."""
    gid = _grille_de_planche(client, decor)
    a, pl = _album_de_la_stagiaire(client, decor)
    r = ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": gid, "version": 1, "planche_id": pl, "entree_cle": "climat",
        "variante_cle": "calme"}), 201)
    ok(client.put(f"/api/releves/{r['id']}", headers=OLGA,
                  json={"variante_cle": "tendu", "vu": {"variante_cle": "calme"}}))
    c1 = _copie_par(a, decor["c2"], "stag")
    c2 = _copie_par(c1, decor["c"], "stag")
    assert _autrui(c2, "stag")
