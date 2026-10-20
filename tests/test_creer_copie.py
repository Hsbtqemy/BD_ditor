"""COL-3, tranche 3a — une copie qui naît d'un document EXISTANT (`database.creer_copie`), et
les trois questions neuves de la `Portee` (`peut_lire_les_notices`,
`clause_rejoindre_directe`, `peut_repondre_a`).

`creer_copie` est éprouvée ici en direct, sous une connexion : les routes qui l'appellent
(la prise, l'acceptation d'une entrée) sont jouées dans `tests/test_prendre.py`. Ce qu'on
regarde : la copie VIERGE (D6, D7), son projet — celui de la collection qui la prend, jamais
celui de sa source —, sa provenance, et sa naissance au journal.

Les questions sont éprouvées par table de vérité, sur des portées construites à la main et
une base où les collections et les rangements sont posés par SQL : la règle, pas la route.
"""
import inspect
import json
import sqlite3

import pytest

import autorisation
import database
from autorisation import Portee
from conftest import ADMIN
from test_fonds import _accorder, _album, _collection, _planche
from test_projets import _sql

LEA = {"Remote-User": "lea"}


@pytest.fixture
def source(client, derriere_proxy, data_dir, db_path):
    """« Le Lotus bleu », importé par `lea` dans Principale (projet de repli), une planche,
    une contribution, une notice riche ; et « Étude » dans un second projet."""
    principale = _collection(client, "Principale")
    _accorder(client, principale, "lea", "ecriture")
    a = _album(client, "Le Lotus bleu", principale, LEA)
    assert client.put(f"/api/albums/{a}", headers=LEA,
                      json={"serie": "Tintin", "isbn": "978-2", "langue": "fr",
                            "source_numerisation": "scanner A3"}).status_code == 200
    assert client.post(f"/api/albums/{a}/contributions", headers=LEA,
                       json={"nom": "Hergé", "role": "scénariste"}).status_code == 201
    pl = _planche(client, a, LEA)
    _sql(db_path, "UPDATE planches SET statut = 'segmentee', validee = '2026-01-01', "
                  "verrouillee = '2026-01-01', verrou_par = 'lea', relecture = 'faite' "
                  "WHERE id = ?", (pl,))
    pid = client.post("/api/projets", json={"nom": "Étude B"}, headers=ADMIN).json()["id"]
    etude = _collection(client, "Étude", projet_id=pid)
    doc = _sql(db_path, "SELECT document_id FROM albums WHERE id = ?", (a,))[0]["document_id"]
    return {"a": a, "doc": doc, "principale": principale, "etude": etude, "projet": pid}


def _copier(db_path, s, *, par="sam", collection=None):
    conn = database.get_connection()
    try:
        b = database.creer_copie(conn, s["doc"], collection or s["etude"], par=par,
                                 depuis=s["a"], cran=database.CRAN_IMAGES)
        conn.commit()
        return b
    finally:
        conn.close()


def test_les_arguments_nommes_sont_obligatoires_et_sans_defaut():
    sig = inspect.signature(database.creer_copie)
    for nom in ("par", "depuis", "cran"):
        assert sig.parameters[nom].kind is inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters[nom].default is inspect.Parameter.empty, nom


def test_une_copie_vierge_reprend_la_notice_et_les_scans(client, db_path, source):
    b = _copier(db_path, source)
    lignes = {r["id"]: r for r in _sql(db_path, "SELECT * FROM albums WHERE id IN (?, ?)",
                                       (source["a"], b))}
    a_, b_ = lignes[source["a"]], lignes[b]
    for col in a_:
        if col in database.ALBUM_HORS_NOTICE:
            continue
        assert b_[col] == a_[col], col
    assert (b_["document_id"], b_["projet_id"]) == (source["doc"], source["projet"])
    # Les planches désignent les MÊMES fichiers (D6), et repartent vierges.
    pa = _sql(db_path, "SELECT * FROM planches WHERE album_id = ?", (source["a"],))
    pb = _sql(db_path, "SELECT * FROM planches WHERE album_id = ?", (b,))
    assert len(pa) == len(pb) == 1
    for col in database.PLANCHE_SCAN:
        assert pb[0][col] == pa[0][col], col
    assert (pb[0]["statut"], pb[0]["validee"], pb[0]["verrouillee"], pb[0]["verrou_par"],
            pb[0]["relecture"]) == ("importee", None, None, None, None)
    assert _sql(db_path, "SELECT nom FROM contribution WHERE album_id = ?", (b,)) \
        == [{"nom": "Hergé"}]


def test_toute_colonne_d_album_est_notice_ou_declaree_hors(db_path, source):
    """Une colonne neuve d'`albums` se recopie par défaut, comme notice. Ce test oblige à la
    relire : si elle n'est PAS descriptive, elle entre dans `ALBUM_HORS_NOTICE`."""
    colonnes = {r["name"] for r in _sql(db_path, "PRAGMA table_info(albums)")}
    descriptives = {"titre", "auteur", "annee", "editeur", "serie", "description",
                    "date_edition", "date_originale", "langue", "type_oeuvre",
                    "lieu_edition", "edition_tirage", "isbn", "format_physique",
                    "source_numerisation"}
    assert colonnes - database.ALBUM_HORS_NOTICE == descriptives
    assert database.ALBUM_HORS_NOTICE <= colonnes


def test_la_copie_nait_dans_le_projet_de_la_collection_qui_la_prend(db_path, source):
    """Jamais dans celui de sa source : `albums_hors_de_leur_projet` reste vide, et elle
    n'est rangée que dans la collection d'arrivée."""
    b = _copier(db_path, source)
    conn = database.get_connection()
    try:
        assert database.albums_hors_de_leur_projet(conn) == []
        assert database.projet_d_album(conn, b) == source["projet"]
        assert database.projet_d_album(conn, source["a"]) != source["projet"]
    finally:
        conn.close()
    assert _sql(db_path, "SELECT collection_id FROM collection_album WHERE album_id = ?",
                (b,)) == [{"collection_id": source["etude"]}]


def test_la_copie_dit_sa_provenance(db_path, source):
    b = _copier(db_path, source)
    repli = _sql(db_path, "SELECT nom FROM projet WHERE repli = 1")[0]["nom"]
    assert _sql(db_path, "SELECT creee_par, cran, depuis_album_id, depuis_projet_nom "
                         "FROM copie WHERE album_id = ?", (b,)) == [
        {"creee_par": "sam", "cran": "images", "depuis_album_id": source["a"],
         "depuis_projet_nom": repli}]


def test_la_naissance_s_ecrit_sous_le_document(db_path, source):
    b = _copier(db_path, source)
    actes = _sql(db_path, "SELECT type, cible_table, cible_id, avant, apres FROM evenement "
                          "ORDER BY id DESC LIMIT 2")
    emploi, naissance = actes
    assert (naissance["type"], naissance["cible_table"], naissance["cible_id"]) \
        == ("modification", "document", source["doc"])
    assert naissance["avant"] is None
    assert json.loads(naissance["apres"]) == {
        "album_id": b, "copie": {"cran": "images", "depuis_album_id": source["a"],
                                 "collection_id": source["etude"]}}
    assert (emploi["type"], emploi["cible_table"]) == ("lien", "collection_album")
    assert json.loads(emploi["apres"])["album_id"] == b


@pytest.mark.parametrize("erreur", ["cran", "source", "collection"])
def test_les_erreurs_de_l_appelant_levent(db_path, source, erreur):
    conn = database.get_connection()
    try:
        autre = conn.execute("INSERT INTO albums (titre) VALUES ('Autre')").lastrowid
        kw = {"par": "sam", "depuis": source["a"], "cran": database.CRAN_IMAGES}
        cid = source["etude"]
        if erreur == "cran":
            # `origine` n'est pas un cran de l'échelle : la copie d'origine naît avec son
            # document (`creer_document`), jamais tirée d'une autre. Les crans de l'échelle
            # sont joués dans `tests/test_amorcer.py` (COL-3, tranche 3b).
            kw["cran"] = database.CRAN_ORIGINE
        elif erreur == "source":
            kw["depuis"] = autre
        else:
            cid = 99999
        with pytest.raises(ValueError):
            database.creer_copie(conn, source["doc"], cid, **kw)
    finally:
        conn.close()


def test_ranger_copie_n_ecrit_un_emploi_qu_une_fois(db_path, source):
    conn = database.get_connection()
    try:
        assert database.ranger_copie(conn, source["a"], source["etude"]) is True
        assert database.ranger_copie(conn, source["a"], source["etude"]) is False
        conn.commit()
    finally:
        conn.close()
    assert len(_sql(db_path, "SELECT 1 FROM evenement WHERE cible_table = 'collection_album' "
                             "AND type = 'lien' AND json_extract(apres, '$.collection_id') = ?",
                    (source["etude"],))) == 1


# --------------------------------------------------------------------------- #
# Les trois questions neuves — par table de vérité
# --------------------------------------------------------------------------- #
def test_peut_lire_les_notices():
    assert autorisation.TOTALE.peut_lire_les_notices()
    assert Portee(projets_geres=frozenset({3})).peut_lire_les_notices()
    for p in (Portee(), Portee(projets=frozenset({3})),
              Portee(propriete=frozenset({1})), Portee(ecriture=frozenset({1})),
              Portee(lecture=frozenset({1}))):
        assert not p.peut_lire_les_notices(), p


@pytest.fixture
def rangements(db_path):
    """Trois collections — X, Y, W (W sans propriétaire) — et quatre copies : `x` dans X,
    `xy` dans X et Y, `w` dans W, `fonds` rangée nulle part."""
    conn = sqlite3.connect(db_path)
    try:
        c = {n: conn.execute("INSERT INTO collection (nom) VALUES (?)", (n,)).lastrowid
             for n in ("X", "Y", "W")}
        a = {n: conn.execute("INSERT INTO albums (titre) VALUES (?)", (n,)).lastrowid
             for n in ("x", "xy", "w", "fonds")}
        for album, cols in (("x", "X"), ("xy", "XY"), ("w", "W")):
            for col in cols:
                conn.execute("INSERT INTO collection_album (collection_id, album_id) "
                             "VALUES (?, ?)", (c[col], a[album]))
        conn.commit()
        return c, a
    finally:
        conn.close()


def _directes(db_path, portee, a) -> set:
    ou, params = portee.clause_rejoindre_directe("a.id")
    conn = sqlite3.connect(db_path)
    try:
        ids = {r[0] for r in conn.execute(f"SELECT a.id FROM albums a WHERE {ou}", params)}
    finally:
        conn.close()
    return {n for n, i in a.items() if i in ids}


def test_rejoindre_sans_demander_demande_d_administrer_chacune(db_path, rangements):
    c, a = rangements
    X, Y, W = c["X"], c["Y"], c["W"]
    # Le propriétaire de X rejoint ce qui ne vit que dans X ; pas ce qui vit aussi dans Y.
    assert _directes(db_path, Portee(propriete=frozenset({X})), a) == {"x"}
    assert _directes(db_path, Portee(propriete=frozenset({X, Y})), a) == {"x", "xy"}
    # Écrire partout ne suffit pas : administrer n'est pas écrire (D4 stricte).
    assert _directes(db_path, Portee(ecriture=frozenset({X, Y, W})), a) == set()
    # Une collection SANS propriétaire n'est tenue que par la portée totale : écrire dans
    # W, posséder tout le reste, ne rejoint pas `w`.
    assert _directes(db_path, Portee(ecriture=frozenset({W}),
                                     propriete=frozenset({X, Y})), a) == {"x", "xy"}
    # Une copie gardée au fonds ne se rejoint que par la portée totale.
    assert _directes(db_path, autorisation.TOTALE, a) == {"x", "xy", "w", "fonds"}
    assert _directes(db_path, Portee(), a) == set()


def test_la_base_d_un_projet_est_tenue_par_son_responsable(db_path, rangements):
    """Ses propriétaires DÉRIVÉS comptent : un responsable tient la collection de base."""
    c, a = rangements
    p = Portee(projets_geres=frozenset({7}), bases=((7, c["X"], None),))
    assert _directes(db_path, p, a) == {"x"}
    assert _directes(db_path, Portee(projets=frozenset({7}), bases=((7, c["X"], "ecriture"),)),
                     a) == set()


def test_peut_repondre_a():
    X, Y = 1, 2
    proprio_x = Portee(propriete=frozenset({X}))
    rejoindre = {"genre": database.DEMANDE_REJOINDRE, "collections": [X]}
    assert proprio_x.peut_repondre_a(rejoindre)
    assert not proprio_x.peut_repondre_a({**rejoindre, "collections": [X, Y]})
    assert Portee(propriete=frozenset({X, Y})).peut_repondre_a(
        {**rejoindre, "collections": [X, Y]})
    assert not Portee(propriete=frozenset({Y})).peut_repondre_a(rejoindre)
    assert not Portee(ecriture=frozenset({X})).peut_repondre_a(rejoindre)
    # Une copie rangée nulle part : personne d'autre que la portée totale n'y consent.
    assert not proprio_x.peut_repondre_a({**rejoindre, "collections": []})
    assert autorisation.TOTALE.peut_repondre_a({**rejoindre, "collections": []})
    for genre in (database.DEMANDE_SUPPRESSION_DOCUMENT, database.DEMANDE_SUPPRESSION_PROJET,
                  database.DEMANDE_ENTREE_DOCUMENTS):
        assert not proprio_x.peut_repondre_a({"genre": genre, "collections": [X]}), genre
        assert autorisation.TOTALE.peut_repondre_a({"genre": genre, "collections": None})


def test_etat_des_reponses():
    A, R = database.REPONSE_ACCEPTEE, database.REPONSE_REFUSEE
    assert database.etat_des_reponses([A, A]) == A
    assert database.etat_des_reponses([R]) == R
    assert database.etat_des_reponses([A, R]) == database.REPONSE_PARTIELLE
    assert database.etat_des_reponses([A, None]) is None
    assert database.etat_des_reponses([]) is None
