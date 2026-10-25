"""COL-3, tranche 3b — qui EFFACE sans demander (Hugo, 2026-10-21).

Renversement daté de la règle des 2026-10-11 et 2026-10-15 (quatre conditions, sinon une
demande) : effacer — supprimer une copie, ou la ramener à un cran — se fait sans demande
par

1. le CRÉATEUR d'une copie que personne d'autre n'a touchée, même DERNIÈRE copie de son
   document (la règle d'avant ; Hugo, 2026-10-21, sur le cas où les deux se croisent) ;
2. le PROPRIÉTAIRE de toutes les collections où vit l'album, même si d'autres y ont
   travaillé ;
3. le RESPONSABLE du projet de l'album, aux mêmes conditions que le propriétaire ;

jamais par un compte PARTAGÉ (hors de son bac à sable), et la dernière copie d'un document
ne sort du fonds commun par (2) ou (3) que sur demande à un administrateur. La protection
du travail des membres passe de la PERMISSION à la VISIBILITÉ :
`GET /api/albums/{id}/travail-des-autres` dit, avant d'effacer, qui perd quoi.

Le décor reprend `test_prendre` — les sept identités de la 3a (`resp`, `membre`, `proprio`,
`ecrivain`, `lectrice`, `personne`, `importeur`) — et y ajoute `resp2`, RESPONSABLE du projet
de repli (un second projet), `proprio2`, propriétaire de Principale, et `atelier`, compte
PARTAGÉ propriétaire d'une collection. « Le Lotus bleu » (d1) a TROIS copies dans deux
projets : l'originale O dans Principale (repli), travaillée par `importeur` ; X1, amorcée
d'O jusqu'au texte par `ecrivain` dans la Collection X (Étude P) ; Y1, amorcée de X1 — une
copie de copie — par `proprio` dans la Collection Y.
"""
import pytest

import autorisation
import database
from conftest import ADMIN
from test_amorcer_entre_projets import _repli, _travailler
from test_bac_a_sable import _portee
from test_fonds import _accorder, _album, _collection, _demander, _planche
from test_prendre import (ECRIVAIN, IMPORTEUR, LECTRICE, MEMBRE, PERSONNE, PROPRIO, RESP,
                          prise)  # noqa: F401
from test_projets import _sql

RESP2 = {"Remote-User": "resp2"}
PROPRIO2 = {"Remote-User": "proprio2"}
ATELIER = {"Remote-User": "atelier"}
GARDIEN = {"Remote-User": "gardien"}        # propriétaire ordinaire de la même collection


def _ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.text)
    return r.json() if r.content else None


def _copier(doc, collection, par, depuis, cran):
    conn = database.get_connection()
    try:
        b = database.creer_copie(conn, doc, collection, par=par, depuis=depuis, cran=cran)
        conn.commit()
        return b
    finally:
        conn.close()


def _ranger(album_id, collection_id):
    conn = database.get_connection()
    try:
        database.ranger_copie(conn, album_id, collection_id)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def efface(client, prise, db_path):  # noqa: F811
    s = prise
    repli = _repli(client)
    _ok(client.put(f"/api/projets/{repli}/membres", headers=ADMIN,
                   json={"principal": "resp2", "role": "responsable"}))
    _accorder(client, s["principale"], "proprio2", "proprietaire")
    o = s["albums"]["d1"]
    _travailler(client, o, IMPORTEUR)
    x1 = _copier(s["docs"]["d1"], s["x"], "ecrivain", o, "transcription")
    y1 = _copier(s["docs"]["d1"], s["y"], "proprio", x1, "transcription")
    # B1 : une copie de L'Oreille cassée née dans la BASE d'Étude P (créée par `membre`),
    # puis rangée aussi dans X — le responsable écrit dans la base, le propriétaire de X ne
    # tient pas la base.
    b1 = _copier(s["docs"]["d2"], s["base"], "membre", s["albums"]["d2"], "images")
    _ranger(b1, s["x"])
    # X3 : une copie VIERGE d'Astérix prise par `ecrivain` dans X, que personne d'autre ne
    # touche.
    x3 = _copier(s["docs"]["d3"], s["x"], "ecrivain", s["albums"]["d3"], "images")
    # « Seul » : la seule copie de son document, importée par `importeur`, que personne
    # d'autre ne touche.
    seul = _album(client, "Seul", s["principale"], IMPORTEUR)
    _planche(client, seul, IMPORTEUR)
    # Le compte PARTAGÉ `atelier` et l'ordinaire `gardien` possèdent chacun une collection
    # du repli où vit une copie d'Astérix (qui a sa sœur dans Principale).
    client.get("/api/moi", headers=ATELIER)
    _ok(client.patch("/api/comptes/atelier/nature", headers=ADMIN,
                     json={"nature": "collectif"}))
    cols = {}
    for qui in ("atelier", "gardien"):
        cols[qui] = _collection(client, f"Collection de {qui}")
        _accorder(client, cols[qui], qui, "proprietaire")
    a_atelier = _copier(s["docs"]["d3"], cols["atelier"], "importeur", s["albums"]["d3"],
                        "images")
    a_gardien = _copier(s["docs"]["d3"], cols["gardien"], "importeur", s["albums"]["d3"],
                        "images")
    return {**s, "repli": repli, "o": o, "x1": x1, "y1": y1, "b1": b1, "x3": x3,
            "seul": seul, "a_atelier": a_atelier, "a_gardien": a_gardien, "db": db_path}


def _destructible(client, qui, album_id):
    """`destructible` de `GET /api/albums` — None si l'album n'y est pas (on ne le lit pas)."""
    a = next((x for x in client.get("/api/albums", headers=qui).json() if x["id"] == album_id),
             None)
    return None if a is None else a["destructible"]


def _clause(db, qui, album_id):
    """La règle elle-même, posée en SQL sur l'album, hors de toute route."""
    p = _portee(db, qui)
    ou, params = p.clause_suppression_directe("a.id")
    return bool(_sql(db, f"SELECT ({ou}) AS v FROM albums a WHERE a.id = ?",
                     (*params, album_id))[0]["v"])


# =========================================================================== #
# Les trois chemins, et la dernière copie
# =========================================================================== #
def test_le_proprietaire_de_toutes_les_collections_efface_meme_le_travail_d_autrui(
        client, efface):
    """X1 vit dans la Collection X seule, que `proprio` possède ; `ecrivain` l'a créée et
    `importeur` a travaillé sur sa source : `proprio` l'efface sans rien demander, et la
    suppression passe. `ecrivain`, qui l'a créée, ne le peut pas : le travail recopié
    d'`importeur` est le travail d'un autre (E3)."""
    assert _destructible(client, PROPRIO, efface["x1"]) is True
    assert _destructible(client, ECRIVAIN, efface["x1"]) is False
    r = client.delete(f"/api/albums/{efface['x1']}", headers=PROPRIO)
    assert r.status_code == 204, r.text
    assert not _sql(efface["db"], "SELECT 1 FROM albums WHERE id = ?", (efface["x1"],))
    # La copie de copie, et sa source d'origine, vivent : effacer une copie n'en touche
    # aucune autre.
    assert _sql(efface["db"], "SELECT COUNT(*) AS n FROM albums WHERE id IN (?, ?)",
                (efface["o"], efface["y1"]))[0]["n"] == 2


def test_posseder_une_seule_des_collections_ne_suffit_pas(client, efface):
    """B1 vit dans la base d'Étude P et dans X : `proprio` possède X, pas la base."""
    assert _destructible(client, PROPRIO, efface["b1"]) is False
    r = client.delete(f"/api/albums/{efface['b1']}", headers=PROPRIO)
    assert r.status_code == 403, r.text


def test_le_responsable_du_projet_efface_ce_qu_il_ne_possede_pas(client, efface):
    """`resp` gère Étude P, et B1 en est : il l'efface, alors que `proprio` tient X où B1
    vit aussi et que `membre` l'a créée. `membre`, qui l'a créée et écrit dans la base, ne
    le peut pas : il n'écrit pas dans X."""
    assert _destructible(client, RESP, efface["b1"]) is True
    assert _destructible(client, MEMBRE, efface["b1"]) is False
    assert client.delete(f"/api/albums/{efface['b1']}", headers=MEMBRE).status_code == 403
    assert client.delete(f"/api/albums/{efface['b1']}", headers=RESP).status_code == 204


def test_le_responsable_d_un_autre_projet_n_efface_rien_ici(client, efface, db_path):
    """`resp2` gère le repli, pas Étude P : X1, Y1, B1 lui restent hors de portée — la règle
    elle-même le dit, avant toute route."""
    for album in ("x1", "y1", "b1"):
        assert _clause(db_path, RESP2, efface[album]) is False, album


def test_le_responsable_efface_par_la_base_dans_son_propre_projet(client, efface, db_path):
    """O, l'originale, vit dans Principale (repli) : rangée aussi dans la base du repli, elle
    s'écrit par `resp2`, qui l'efface — alors que `proprio2` possède Principale et
    qu'`importeur` y a travaillé. Sans la base, il ne l'écrit pas : la route répond 404."""
    assert client.delete(f"/api/albums/{efface['o']}", headers=RESP2).status_code == 404
    assert _clause(db_path, RESP2, efface["o"]) is True
    base_repli = database.collection_de_base(database.get_connection(), efface["repli"])
    _ranger(efface["o"], base_repli)
    assert _destructible(client, RESP2, efface["o"]) is True
    assert client.delete(f"/api/albums/{efface['o']}", headers=RESP2).status_code == 204


def test_la_derniere_copie_se_demande_au_proprietaire_et_au_responsable(client, efface,
                                                                       db_path):
    """« Seul » est la seule copie de son document : `proprio2`, qui possède Principale, ne
    l'efface pas — il la DEMANDE à un administrateur (la demande part, elle n'est pas
    « à faire soi-même ») ; `importeur`, qui l'a importée et que personne n'a touchée,
    l'efface seul. O, qui a deux sœurs, s'efface par `proprio2`."""
    assert _destructible(client, PROPRIO2, efface["seul"]) is False
    assert _destructible(client, IMPORTEUR, efface["seul"]) is True
    assert _destructible(client, PROPRIO2, efface["o"]) is True
    assert client.delete(f"/api/albums/{efface['seul']}", headers=PROPRIO2).status_code == 403
    assert _demander(client, efface["seul"], PROPRIO2).status_code == 201
    r = _demander(client, efface["o"], PROPRIO2)
    assert r.status_code == 409 and "vous-même" in r.json()["detail"]
    assert client.delete(f"/api/albums/{efface['seul']}", headers=IMPORTEUR).status_code == 204


def test_une_soeur_isolee_ne_garde_pas_le_document_au_fonds_commun(client, efface, db_path):
    """Les sœurs d'O sont X1 et Y1, dans Étude P. Étude P déclarée projet isolé (le jeu), O
    redevient la dernière copie du fonds commun : `proprio2` ne l'efface plus seul."""
    assert _clause(db_path, PROPRIO2, efface["o"]) is True
    _sql(db_path, "UPDATE projet SET jeu = 1 WHERE id = ?", (efface["projet"],))
    assert _clause(db_path, PROPRIO2, efface["o"]) is False


def test_un_compte_partage_n_efface_jamais_seul(client, efface):
    """`atelier` (partagé) et `gardien` (ordinaire) possèdent chacun la collection de leur
    copie d'Astérix, qui a ses sœurs : le second l'efface, le premier jamais."""
    assert _destructible(client, GARDIEN, efface["a_gardien"]) is True
    assert _destructible(client, ATELIER, efface["a_atelier"]) is False
    assert client.delete(f"/api/albums/{efface['a_atelier']}", headers=ATELIER).status_code == 403


def test_le_createur_seul_efface_encore(client, efface):
    """X3, vierge, prise par `ecrivain`, que personne n'a touchée : la règle d'avant tient."""
    assert _destructible(client, ECRIVAIN, efface["x3"]) is True
    assert _destructible(client, PROPRIO, efface["x3"]) is True
    assert client.delete(f"/api/albums/{efface['x3']}", headers=ECRIVAIN).status_code == 204


@pytest.mark.parametrize("qui", [LECTRICE, PERSONNE])
def test_qui_n_ecrit_pas_n_efface_rien(client, efface, qui):
    for album in ("x1", "y1", "b1", "x3"):
        assert client.delete(f"/api/albums/{efface[album]}", headers=qui).status_code == 404


def test_une_planche_suit_la_regle_du_document(client, efface):
    """`proprio` supprime une planche de X1 où d'autres ont travaillé ; `ecrivain` non."""
    pl = _sql(efface["db"], "SELECT id FROM planches WHERE album_id = ?",
              (efface["x1"],))[0]["id"]
    assert client.delete(f"/api/planches/{pl}", headers=ECRIVAIN).status_code == 403
    assert client.delete(f"/api/planches/{pl}", headers=PROPRIO).status_code == 204


def test_le_bac_a_sable_garde_son_chemin_et_rien_d_autre(client, efface, db_path):
    """Dans un bac à sable, un invité qui y POSSÈDE une collection ne prend pas le chemin du
    propriétaire : la règle commune du créateur, seule. Posé en base — le décor d'un bac à
    sable n'a pas de sœur hors de lui."""
    conn = database.get_connection()
    try:
        bac = conn.execute("INSERT INTO projet (nom, bac_a_sable_de, efface_le) VALUES "
                           "('Bac à sable', 'lea', '2099-01-05 03:00:00')").lastrowid
        conn.execute("INSERT INTO projet_acces (projet_id, genre, principal, role) VALUES "
                     "(?, 'utilisateur', 'lea', 'responsable'), "
                     "(?, 'utilisateur', 'sam', 'membre')", (bac, bac))
        c = conn.execute("INSERT INTO collection (nom, projet_id) VALUES ('De sam', ?)",
                         (bac,)).lastrowid
        conn.execute("INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
                     "VALUES (?, 'utilisateur', 'sam', 'proprietaire')", (c,))
        conn.commit()
    finally:
        conn.close()
    a = _copier(efface["docs"]["d3"], c, "lea", efface["albums"]["d3"], "images")
    assert _clause(db_path, {"Remote-User": "sam"}, a) is False
    assert _clause(db_path, {"Remote-User": "lea"}, a) is True


# =========================================================================== #
# Qui perd quoi, avant d'effacer
# =========================================================================== #
def test_qui_perd_quoi_se_lit_par_qui_peut_effacer(client, efface):
    """`proprio` lit, sur X1, ce qu'`ecrivain` y a fait — rien ici, il n'y a touché que par
    la copie — et le travail RECOPIÉ d'`importeur`, compté sans nom : il ne part pas avec
    X1, et `importeur` a travaillé dans un autre projet. L'administrateur, lui, lit tout,
    noms compris."""
    _ok(client.put(f"/api/regions/{_bulle(efface['db'], efface['x1'])}/annotation",
                   headers=ECRIVAIN, json={"note": "à moi", "tags": []}))
    vue = _ok(client.get(f"/api/albums/{efface['x1']}/travail-des-autres", headers=PROPRIO))
    assert [e["agent"] for e in vue["travail_des_autres"]] == ["ecrivain"]
    assert vue["travail_des_autres"][0]["gestes"] == {"annotations": 1}
    assert vue["creee_par"] == "ecrivain"
    assert vue["travail_recopie"]["gestes"].get("regions", 0) >= 1
    assert "importeur" not in client.get(f"/api/albums/{efface['x1']}/travail-des-autres",
                                         headers=PROPRIO).text
    admin = _ok(client.get(f"/api/albums/{efface['x1']}/travail-des-autres", headers=ADMIN))
    assert {e["agent"] for e in admin["travail_des_autres"]} == {"ecrivain", "importeur"}
    assert "travail_recopie" not in admin


def test_qui_perd_quoi_est_borne_a_qui_peut_effacer(client, efface):
    """`ecrivain` écrit dans X1 sans pouvoir l'effacer : 403 nommé ; qui ne l'écrit pas :
    404, le même qu'un album absent."""
    r = client.get(f"/api/albums/{efface['x1']}/travail-des-autres", headers=ECRIVAIN)
    assert r.status_code == 403, r.text
    for qui in (LECTRICE, PERSONNE, RESP2):
        r = client.get(f"/api/albums/{efface['x1']}/travail-des-autres", headers=qui)
        absent = client.get("/api/albums/999999/travail-des-autres", headers=qui)
        assert (r.status_code, absent.status_code) == (404, 404), qui


def _bulle(db, album_id):
    return _sql(db, "SELECT r.id FROM regions r JOIN planches p ON p.id = r.planche_id "
                    "WHERE p.album_id = ? AND r.type = 'bulle'", (album_id,))[0]["id"]


def test_la_regle_et_la_liste_disent_pareil(client, efface, db_path):
    """`destructible` de `GET /api/albums` est la règle, album par album, sous chaque
    identité qui lit l'album."""
    for qui in (RESP, MEMBRE, PROPRIO, ECRIVAIN, LECTRICE, IMPORTEUR, RESP2, PROPRIO2,
                ATELIER, GARDIEN):
        for a in client.get("/api/albums", headers=qui).json():
            assert a["destructible"] is _clause(db_path, qui, a["id"]), (qui, a["id"])
    assert autorisation.TOTALE.clause_suppression_directe("a.id") == ("1", [])
