"""COL-3, tranche 1 — le projet existe, se règle, et ne change rien d'autre.

Un PROJET est l'étage au-dessus des collections. Ces tests tiennent trois choses, et la
troisième est celle qui compte.

1. Le MODÈLE : la migration v29 range tout l'existant dans un premier projet, désigné par
   un drapeau et non par son nom ; une collection appartient à UN projet, et celle qui n'en
   nomme aucun se LIT dans le projet de repli.
2. Les ROUTES : décider quels projets existent revient à une portée totale, régler qui est
   d'un projet à son responsable, et trois refus se nomment.
3. CE QUE LE PROJET NE FAIT PAS : être d'un projet n'ouvre aucune de ses collections, et un
   accès de collection se passe d'être du projet. C'est la promesse de la tranche — « rien
   d'autre ne change » —, et elle se vérifie dans les DEUX sens.
"""
import io
import json
import os
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import autorisation
import config
import database
from conftest import ADMIN

REPO_ROOT = Path(__file__).resolve().parent.parent

ALICE = {"Remote-User": "alice"}
BOB = {"Remote-User": "bob"}
CAROL = {"Remote-User": "carol"}


# --------------------------------------------------------------------------- #
# Outils de décor
# --------------------------------------------------------------------------- #
def _sql(db_path, sql, params=()):
    """Lit ou écrit directement en base — le décor et la relecture, jamais le geste testé."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        lignes = [dict(r) for r in conn.execute(sql, params).fetchall()]
        conn.commit()
        return lignes
    finally:
        conn.close()


def _repli(db_path) -> int:
    """L'id du projet de repli, relu en base par son DRAPEAU."""
    lignes = _sql(db_path, "SELECT id FROM projet WHERE repli = 1")
    assert len(lignes) == 1, f"un seul projet de repli attendu, lu : {lignes}"
    return lignes[0]["id"]


def _projet(client, nom, **champs) -> int:
    r = client.post("/api/projets", json={"nom": nom, **champs}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _collection(client, nom, projet_id=None, headers=ADMIN) -> int:
    charge = {"nom": nom} if projet_id is None else {"nom": nom, "projet_id": projet_id}
    r = client.post("/api/collections", json=charge, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _album(client, titre, collection_id) -> int:
    r = client.post("/api/albums", json={"titre": titre, "collection_id": collection_id},
                    headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _membre(client, projet_id, principal, role="membre", genre="utilisateur",
            headers=ADMIN):
    return client.put(f"/api/projets/{projet_id}/membres", headers=headers,
                      json={"genre": genre, "principal": principal, "role": role})


def _acces(client, collection_id, principal, niveau="lecture", genre="utilisateur"):
    r = client.put(f"/api/collections/{collection_id}/acces", headers=ADMIN,
                   json={"genre": genre, "principal": principal, "niveau": niveau})
    assert r.status_code in (200, 201), r.text


def _evenements(db_path, table):
    return _sql(db_path, "SELECT type, agent, cible_id, avant, apres FROM evenement "
                         "WHERE cible_table = ? ORDER BY id", (table,))


@pytest.fixture
def decor(client, db_path, derriere_proxy):
    """Deux projets : le repli, et « Séminaire » qui porte une collection et un album.

    Monté par un administrateur, donc aucun accès de collection ni aucun membre n'existe
    au départ : chaque test pose exactement ce qu'il éprouve."""
    pid = _projet(client, "Séminaire")
    cid = _collection(client, "Étude des émotions", projet_id=pid)
    aid = _album(client, "Le Lotus bleu", cid)
    return {"repli": _repli(db_path), "projet": pid, "collection": cid, "album": aid}


# --------------------------------------------------------------------------- #
# Le modèle — migration, repli, règle de lecture
# --------------------------------------------------------------------------- #
def _ramener_en_v28(db):
    """Défait la v29 sur une base neuve, pour rejouer un upgrade RÉEL (le patron de
    `test_domaines.test_upgrade_reel_recree_les_index_de_migration`). Clés étrangères
    coupées par défaut sur une connexion brute : la chirurgie ne déclenche rien."""
    conn = sqlite3.connect(db)
    conn.execute("DROP INDEX IF EXISTS idx_collection_projet")
    conn.execute("ALTER TABLE collection DROP COLUMN projet_id")
    conn.execute("DROP TABLE projet_acces")
    conn.execute("DROP TABLE projet")
    conn.execute("PRAGMA user_version = 28")
    conn.commit()
    conn.close()


@pytest.fixture
def base_v28(tmp_path, monkeypatch):
    """Une base au schéma v28 qui a VÉCU : deux collections, et trois accès tenus par deux
    principaux — alice (deux fois, à deux niveaux) et le groupe `etudiants`."""
    db = tmp_path / "v28.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db)
    database.init_db()
    _ramener_en_v28(db)
    _sql(db, "INSERT INTO collection (id, nom) VALUES (1, 'Corpus colonial')")
    _sql(db, "INSERT INTO collection (id, nom) VALUES (2, 'Incubateur')")
    for cid, genre, principal, niveau in ((1, "utilisateur", "alice", "lecture"),
                                          (2, "utilisateur", "alice", "proprietaire"),
                                          (2, "groupe", "etudiants", "ecriture")):
        _sql(db, "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
                 "VALUES (?, ?, ?, ?)", (cid, genre, principal, niveau))
    return db


def test_la_migration_range_tout_l_existant_dans_le_premier_projet(base_v28):
    """« L'instance d'hier est, sans rien y changer, le premier projet. » Un seul projet
    naît, sous le nom porté par la constante et avec le drapeau `repli` ; toutes les
    collections y sont rangées DANS LA COLONNE (pas seulement par la règle de lecture) ;
    et l'index de la colonne migrée existe — il ne peut être créé qu'après l'ALTER."""
    database.init_db()                                   # upgrade réel v28 → v29
    assert _sql(base_v28, "PRAGMA user_version")[0]["user_version"] == database.SCHEMA_VERSION
    projets = _sql(base_v28, "SELECT id, nom, repli, justification FROM projet")
    assert projets == [{"id": projets[0]["id"], "nom": database.NOM_PROJET_DEFAUT,
                        "repli": 1, "justification": None}]
    assert {c["projet_id"] for c in _sql(base_v28, "SELECT projet_id FROM collection")} \
        == {projets[0]["id"]}
    assert database.collections_sans_projet(sqlite3.connect(base_v28)) == []
    index = {r["name"] for r in _sql(base_v28, "SELECT name FROM sqlite_master "
                                               "WHERE type = 'index'")}
    assert "idx_collection_projet" in index


def test_la_migration_fait_membres_ceux_qui_avaient_un_acces(base_v28):
    """Tout compte ou groupe qui tenait un accès de collection devient MEMBRE du premier
    projet — une fois chacun, quel que soit le nombre de ses accès et leur niveau. Aucun
    responsable n'est désigné : la migration ne devine pas qui répond du projet, et une
    propriétaire de collection n'en devient pas responsable par ricochet."""
    database.init_db()
    membres = _sql(base_v28, "SELECT genre, principal, role FROM projet_acces "
                             "ORDER BY genre, principal")
    assert membres == [{"genre": "groupe", "principal": "etudiants", "role": "membre"},
                       {"genre": "utilisateur", "principal": "alice", "role": "membre"}]


def test_la_migration_ne_se_rejoue_pas(base_v28, monkeypatch):
    """Une migration de DONNÉES est gatée par la version : rejouée, elle referait membre du
    premier projet quiconque en a été sorti. Deux façons de la rejouer, et les deux sont
    éprouvées — un redémarrage ordinaire, et l'upgrade SUIVANT (v29 → v30), qui retraverse
    `_migrate` en entier et que seul le `if version < 29` arrête."""
    database.init_db()
    pid = _repli(base_v28)
    _sql(base_v28, "UPDATE projet SET nom = 'Corpus franco-belge' WHERE id = ?", (pid,))
    _sql(base_v28, "DELETE FROM projet_acces WHERE principal = 'alice'")
    _sql(base_v28, "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
                   "VALUES (1, 'utilisateur', 'bob', 'lecture')")      # accès d'APRÈS

    def etat():
        return (_sql(base_v28, "SELECT id, nom, repli FROM projet"),
                _sql(base_v28, "SELECT principal FROM projet_acces ORDER BY principal"))
    attendu = ([{"id": pid, "nom": "Corpus franco-belge", "repli": 1}],
               [{"principal": "etudiants"}])

    database.init_db()                                   # redémarrage : rien ne bouge
    assert etat() == attendu
    monkeypatch.setattr(database, "SCHEMA_VERSION", database.SCHEMA_VERSION + 1)
    database.init_db()                                   # l'upgrade suivant non plus
    assert etat() == attendu


def test_la_migration_tient_sur_un_schema_minimal(tmp_path):
    """Les tests de migration montent des schémas réduits à quelques tables : `collection`
    sans `projet` autour ne doit ni lever, ni recevoir une clé étrangère vers rien — y
    compris quand la v23 y crée la collection de repli, pour un album orphelin."""
    conn = sqlite3.connect(tmp_path / "mini.sqlite")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE albums (id INTEGER PRIMARY KEY, titre TEXT);"
        "CREATE TABLE planches (id INTEGER PRIMARY KEY, album_id INT, numero INT);"
        "CREATE TABLE collection (id INTEGER PRIMARY KEY, nom TEXT, description TEXT);"
        "CREATE TABLE collection_album (collection_id INT, album_id INT);"
        "INSERT INTO albums (id, titre) VALUES (1, 'Orphelin');"
        "PRAGMA user_version = 16;")
    database._migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    assert "projet_id" not in {r["name"] for r in
                               conn.execute("PRAGMA table_info(collection)")}
    assert [r["nom"] for r in conn.execute("SELECT nom FROM collection")] \
        == [database.NOM_COLLECTION_DEFAUT]
    conn.close()


def test_une_base_neuve_nait_avec_son_projet(client, db_path):
    """Mono-poste compris : le projet existe dès l'`init_db`, et il se lit. La portée
    totale le gère sans y tenir de rôle — `mon_role` est `None`, pas « responsable »."""
    pid = _repli(db_path)
    assert client.get("/api/projets").json() == [{
        "id": pid, "nom": database.NOM_PROJET_DEFAUT, "repli": True,
        "description": client.get("/api/projets").json()[0]["description"],
        "date_creation": client.get("/api/projets").json()[0]["date_creation"],
        "mon_role": None, "gerable": True, "nb_collections": 0, "justification": None}]


def test_le_repli_se_designe_par_son_drapeau_jamais_par_son_nom(client, db_path):
    """Renommé, le premier projet reste le repli : une collection créée sans projet y
    tombe, et aucun second projet ne renaît sous l'ancien nom. C'est ce qui permet de le
    renommer à l'écran — là où la collection de repli, elle, tient à son nom réservé."""
    pid = _repli(db_path)
    r = client.patch(f"/api/projets/{pid}", json={"nom": "Corpus franco-belge"})
    assert r.status_code == 200 and r.json()["repli"] is True
    cid = _collection(client, "Après le renommage")
    assert _sql(db_path, "SELECT projet_id FROM collection WHERE id = ?", (cid,)) \
        == [{"projet_id": pid}]
    assert _sql(db_path, "SELECT nom FROM projet") == [{"nom": "Corpus franco-belge"}]


def test_une_collection_sans_projet_nomme_se_lit_dans_le_repli(client, db_path,
                                                             derriere_proxy):
    """La colonne est nullable, et NULL se lit « projet de repli » — partout de la même
    façon. Une collection posée par `INSERT` (vingt décors de test le font, et une base
    retouchée à la main aussi) est donc du repli dans la liste des collections, dans celle
    des projets, et pour qui ne voit le projet que par elle."""
    pid = _repli(db_path)
    _sql(db_path, "INSERT INTO collection (id, nom) VALUES (70, 'Posée à la main')")
    assert database.collections_sans_projet(sqlite3.connect(db_path)) == [70]
    _acces(client, 70, "carol")

    vue = client.get("/api/collections", headers=CAROL).json()
    assert [(c["id"], c["projet_id"], c["projet_nom"]) for c in vue] \
        == [(70, pid, database.NOM_PROJET_DEFAUT)]
    projets = client.get("/api/projets", headers=CAROL).json()
    assert [(p["id"], p["nb_collections"]) for p in projets] == [(pid, 1)]
    # …et la route qui la modifie rend le même projet que la liste.
    r = client.patch("/api/collections/70", json={"description": "x"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["projet_id"] == pid


def test_les_chemins_d_ecriture_posent_tous_le_projet(client, db_path):
    """« Une collection appartient à UN projet », en formulation exécutable : la route, la
    collection de repli (née du premier album sans collection) et l'outil en ligne de
    commande écrivent tous la colonne — la règle de lecture ne rattrape que le reste."""
    _collection(client, "Par la route")
    assert client.post("/api/albums", json={"titre": "Sans collection"}).status_code == 201
    code, _, err = _outil(db_path, "gerer_collections.py", "creer", "--nom", "Par l'outil")
    assert code == 0, err
    noms = {c["nom"] for c in _sql(db_path, "SELECT nom FROM collection")}
    assert noms == {"Par la route", database.NOM_COLLECTION_DEFAUT, "Par l'outil"}
    assert database.collections_sans_projet(sqlite3.connect(db_path)) == []
    assert {c["projet_id"] for c in _sql(db_path, "SELECT projet_id FROM collection")} \
        == {_repli(db_path)}


# --------------------------------------------------------------------------- #
# La règle — ce que la Portee sait des projets
# --------------------------------------------------------------------------- #
def test_le_responsable_est_membre_et_le_membre_ne_gere_pas():
    """Table de vérité. Le cumul responsable ⊂ membre est fait DANS `Portee`, une fois ;
    gérer se lit dans `projets_geres` et nulle part ailleurs ; décider des projets ne
    revient qu'à une portée totale."""
    membre = autorisation.Portee(projets=frozenset({1}), utilisateur="m")
    responsable = autorisation.Portee(projets_geres=frozenset({2}), utilisateur="r")
    vide = autorisation.Portee()
    admin = autorisation.Portee(tout=True, admin=True, utilisateur="a")

    table = {  # (est_du_projet, peut_gerer_projet) pour les projets 1 et 2
        "membre": [(membre.est_du_projet(p), membre.peut_gerer_projet(p)) for p in (1, 2)],
        "responsable": [(responsable.est_du_projet(p), responsable.peut_gerer_projet(p))
                        for p in (1, 2)],
        "vide": [(vide.est_du_projet(p), vide.peut_gerer_projet(p)) for p in (1, 2)],
        "admin": [(admin.est_du_projet(p), admin.peut_gerer_projet(p)) for p in (1, 2)],
        "mono-poste": [(autorisation.TOTALE.est_du_projet(p),
                        autorisation.TOTALE.peut_gerer_projet(p)) for p in (1, 2)],
    }
    assert table == {
        "membre": [(True, False), (False, False)],
        "responsable": [(False, False), (True, True)],
        "vide": [(False, False), (False, False)],
        "admin": [(True, True), (True, True)],
        "mono-poste": [(True, True), (True, True)],
    }
    assert [p.peut_decider_des_projets() for p in
            (membre, responsable, vide, admin, autorisation.TOTALE)] \
        == [False, False, False, True, True]


def test_etre_d_un_projet_ne_touche_aucun_ensemble_de_collections():
    """Les deux ensembles de projets ne nourrissent ni la lecture, ni l'écriture, ni la
    propriété, ni l'export — et la portée réduite à l'export les garde tels quels."""
    p = autorisation.Portee(projets=frozenset({1}), projets_geres=frozenset({2}),
                            lecture=frozenset({9}), utilisateur="x")
    assert (p.lecture, p.ecriture, p.propriete, p.export) \
        == (frozenset({9}), frozenset(), frozenset(), frozenset())
    assert p.clause_album("a.id") == (
        "EXISTS (SELECT 1 FROM collection_album ca WHERE ca.album_id = a.id "
        "AND ca.collection_id IN (?))", [9])
    e = p.pour_export()
    assert (e.projets, e.projets_geres) == (frozenset({1, 2}), frozenset({2}))


def test_clause_projet_ne_lie_que_des_parametres():
    """Le fragment des LISTES : tout pour une portée totale, rien pour une portée vide, et
    deux moitiés sinon — les projets dont on est, ceux d'une collection qu'on lit. Aucun
    identifiant n'est écrit dans le SQL."""
    P = autorisation.Portee
    assert P(tout=True).clause_projet() == ("1", [])
    assert P().clause_projet() == ("0", [])
    sql, params = P(projets=frozenset({3, 1})).clause_projet("p.id")
    assert (sql, params) == ("(p.id IN (?, ?))", [1, 3])
    sql, params = P(lecture=frozenset({5})).clause_projet("x.id")
    assert params == [5] and sql.startswith("(EXISTS (SELECT 1 FROM collection c WHERE ")
    assert "= x.id AND c.id IN (?))" in sql and "5" not in sql
    sql, params = P(projets=frozenset({1}), lecture=frozenset({5, 6})).clause_projet()
    assert params == [1, 5, 6] and " OR " in sql


def test_la_portee_lit_les_projets_par_login_et_par_groupe(client, db_path, decor):
    """`resoudre` lit `projet_acces` pour un compte ordinaire : par son login, et par les
    groupes que le portail transmet — jamais par un groupe qu'il ne transmet pas. Un rôle
    inconnu en base se lit `membre` : dégrader est la seule erreur qui ne s'aggrave pas."""
    pid = decor["projet"]
    assert _membre(client, pid, "alice").status_code == 200
    assert _membre(client, pid, "labo", role="responsable", genre="groupe").status_code == 200
    _sql(db_path, "INSERT INTO projet_acces (projet_id, genre, principal, role) "
                  "VALUES (?, 'utilisateur', 'carol', 'chef')", (pid,))

    def vu_par(headers):
        return [(p["id"], p["mon_role"], p["gerable"])
                for p in client.get("/api/projets", headers=headers).json()]

    assert vu_par(ALICE) == [(pid, "membre", False)]
    assert vu_par({"Remote-User": "bob", "Remote-Groups": "labo"}) \
        == [(pid, "responsable", True)]
    assert vu_par(BOB) == []                       # bob sans son groupe : rien
    assert vu_par(CAROL) == [(pid, "membre", False)]
    assert vu_par({}) == []                        # sans identité : portée vide


# --------------------------------------------------------------------------- #
# LE test de la tranche — dans les deux sens
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("role", ["membre", "responsable"])
def test_etre_du_projet_n_ouvre_aucune_de_ses_collections(client, decor, role):
    """Entrer dans un projet n'ouvre RIEN. Membre ou responsable de « Séminaire », sans
    aucun accès de collection, alice ne liste ni la collection ni l'album, et l'album
    comme ses planches lui répondent « introuvable ». Elle voit le NOM du projet, et le
    compte de ses collections lui dit zéro — celles qu'elle lit, pas celles qui existent."""
    assert _membre(client, decor["projet"], "alice", role=role).status_code == 200
    assert client.get("/api/collections", headers=ALICE).json() == []
    assert client.get("/api/albums", headers=ALICE).json() == []
    assert client.get(f"/api/albums/{decor['album']}/planches",
                      headers=ALICE).status_code == 404
    assert client.get(f"/api/albums/{decor['album']}/collections",
                      headers=ALICE).status_code == 404
    assert client.get(f"/api/collections/{decor['collection']}/acces",
                      headers=ALICE).status_code == 404
    r = client.post("/api/albums", headers=ALICE,
                    json={"titre": "Glissé", "collection_id": decor["collection"]})
    assert r.status_code == 404
    projets = client.get("/api/projets", headers=ALICE).json()
    assert [(p["id"], p["nb_collections"]) for p in projets] == [(decor["projet"], 0)]


def test_un_acces_de_collection_se_passe_d_etre_du_projet(client, decor):
    """L'autre sens : bob lit la collection sans être du projet, et rien ne lui est
    retiré. Il lit le nom du projet PAR sa collection — sans rôle, sans le gérer, sans sa
    justification, sans la liste de ses membres — et aucun autre projet ne lui apparaît."""
    autre = _projet(client, "Projet voisin")
    _collection(client, "Fermée à bob", projet_id=decor["projet"])
    _acces(client, decor["collection"], "bob")

    vue = client.get("/api/collections", headers=BOB).json()
    assert [(c["id"], c["projet_id"], c["projet_nom"]) for c in vue] \
        == [(decor["collection"], decor["projet"], "Séminaire")]
    assert client.get(f"/api/albums/{decor['album']}/planches",
                      headers=BOB).status_code == 200
    assert client.get(f"/api/albums/{decor['album']}/collections", headers=BOB).json() \
        == [{"id": decor["collection"], "nom": "Étude des émotions",
             "projet_id": decor["projet"], "mon_niveau": "lecture",
             "administrable": False, "exportable": False}]

    projets = client.get("/api/projets", headers=BOB).json()
    assert len(projets) == 1 and "justification" not in projets[0]
    assert {k: projets[0][k] for k in ("id", "nom", "mon_role", "gerable",
                                       "nb_collections")} \
        == {"id": decor["projet"], "nom": "Séminaire", "mon_role": None,
            "gerable": False, "nb_collections": 1}      # 1 lue, sur 2 qui existent
    admin = {p["id"]: p["nb_collections"]
             for p in client.get("/api/projets", headers=ADMIN).json()}
    assert admin[decor["projet"]] == 2

    # 403 NOMMÉ sur le projet qu'il voit, 404 sur celui qu'il ne voit pas.
    r = client.get(f"/api/projets/{decor['projet']}/membres", headers=BOB)
    assert r.status_code == 403 and "responsable" in r.json()["detail"]
    assert client.get(f"/api/projets/{autre}/membres", headers=BOB).status_code == 404
    assert client.get(f"/api/projets/{decor['repli']}/membres", headers=BOB).status_code == 404


def test_moi_ne_dit_rien_des_projets(client, decor):
    """`GET /api/moi` ne gagne rien : l'écran lit les projets par leur route. Un test y
    compare déjà la réponse entière en mono-poste ; celui-ci le dit d'un responsable."""
    assert _membre(client, decor["projet"], "alice", role="responsable").status_code == 200
    moi = client.get("/api/moi", headers=ALICE).json()
    assert "projet" not in json.dumps(moi).lower()
    assert moi["acces"]["collections"] == 0


# --------------------------------------------------------------------------- #
# Décider quels projets existent — créer, renommer, supprimer
# --------------------------------------------------------------------------- #
def test_creer_un_projet_revient_a_une_portee_totale(client, db_path, derriere_proxy):
    """L'administrateur crée ; un compte ordinaire, même responsable d'un autre projet, et
    une requête sans identité reçoivent un 403 qui dit à qui c'est réservé. Le projet naît
    VIDE : qui le crée n'y entre pas."""
    r = client.post("/api/projets", headers=ADMIN,
                    json={"nom": "  Séminaire  ", "description": "d", "justification": "j"})
    assert r.status_code == 201
    p = r.json()
    assert {k: p[k] for k in ("nom", "description", "justification", "repli",
                              "mon_role", "gerable", "nb_collections")} \
        == {"nom": "Séminaire", "description": "d", "justification": "j", "repli": False,
            "mon_role": None, "gerable": True, "nb_collections": 0}
    assert _sql(db_path, "SELECT 1 FROM projet_acces WHERE projet_id = ?", (p["id"],)) == []

    assert _membre(client, p["id"], "alice", role="responsable").status_code == 200
    for headers in (ALICE, BOB, {}):
        r = client.post("/api/projets", json={"nom": "Le mien"}, headers=headers)
        assert r.status_code == 403 and "administrateurs" in r.json()["detail"], r.text
    assert len(_sql(db_path, "SELECT 1 FROM projet")) == 2


def test_le_mono_poste_cree_un_projet(client):
    """Sans proxy, la portée est totale : on décide de ses projets comme du reste."""
    assert client.post("/api/projets", json={"nom": "Second"}).status_code == 201
    assert [p["nom"] for p in client.get("/api/projets").json()] \
        == [database.NOM_PROJET_DEFAUT, "Second"]          # le repli d'abord


def test_le_nom_d_un_projet_est_requis_borne_et_unique(client, derriere_proxy):
    """Trois refus de nom. Le plafond est celui de la constante, au caractère près ; et
    l'unicité ne regarde ni la casse ni les espaces, accents compris."""
    for nom in ("", "   "):
        assert client.post("/api/projets", json={"nom": nom},
                           headers=ADMIN).status_code == 422
    juste = "é" * database.LONGUEUR_NOM_PROJET
    assert client.post("/api/projets", json={"nom": juste}, headers=ADMIN).status_code == 201
    r = client.post("/api/projets", json={"nom": juste + "x"}, headers=ADMIN)
    assert r.status_code == 422 and str(database.LONGUEUR_NOM_PROJET) in r.json()["detail"]

    _projet(client, "Émotions")
    r = client.post("/api/projets", json={"nom": " émotions "}, headers=ADMIN)
    assert r.status_code == 409 and "Émotions" in r.json()["detail"]
    r = client.post("/api/projets", json={"nom": database.NOM_PROJET_DEFAUT.upper()},
                    headers=ADMIN)
    assert r.status_code == 409


def test_renommer_un_projet_n_est_pas_au_responsable(client, db_path, decor):
    """Gérer un projet n'est pas l'instituer. Sa responsable règle qui y entre ; le
    renommer lui répond 403, un simple membre aussi, et qui ne le voit pas 404. L'état en
    base n'a pas bougé."""
    pid = decor["projet"]
    assert _membre(client, pid, "alice", role="responsable").status_code == 200
    assert _membre(client, pid, "bob").status_code == 200
    for headers in (ALICE, BOB):
        r = client.patch(f"/api/projets/{pid}", json={"nom": "Pris"}, headers=headers)
        assert r.status_code == 403 and "administrateurs" in r.json()["detail"], r.text
    assert client.patch(f"/api/projets/{pid}", json={"nom": "Pris"},
                        headers=CAROL).status_code == 404
    assert client.patch("/api/projets/9999", json={"nom": "Pris"},
                        headers=ADMIN).status_code == 404
    assert _sql(db_path, "SELECT nom FROM projet WHERE id = ?", (pid,)) == [{"nom": "Séminaire"}]


def test_modifier_un_projet_trace_ce_qui_change_et_rien_d_autre(client, db_path, decor):
    """L'administrateur renomme, décrit, justifie. Le journal garde l'avant et l'après de
    ce qui a CHANGÉ ; renvoyer les mêmes valeurs n'y écrit rien. Un nom pris par un autre
    projet est refusé, le sien se garde."""
    pid = decor["projet"]
    r = client.patch(f"/api/projets/{pid}", headers=ADMIN,
                     json={"nom": "Séminaire 2026", "justification": "Thèse en cours"})
    assert r.status_code == 200
    assert (r.json()["nom"], r.json()["justification"]) == ("Séminaire 2026", "Thèse en cours")
    r = client.patch(f"/api/projets/{pid}", headers=ADMIN,
                     json={"nom": " Séminaire 2026 ", "justification": "Thèse en cours"})
    assert r.status_code == 200 and r.json()["nom"] == "Séminaire 2026"

    modifs = [e for e in _evenements(db_path, "projet") if e["type"] == "modification"]
    assert [(e["agent"], e["cible_id"], json.loads(e["avant"]), json.loads(e["apres"]))
            for e in modifs] == [
        ("decor", pid, {"nom": "Séminaire", "justification": None},
         {"nom": "Séminaire 2026", "justification": "Thèse en cours"})]

    r = client.patch(f"/api/projets/{pid}", headers=ADMIN,
                     json={"nom": database.NOM_PROJET_DEFAUT.lower()})
    assert r.status_code == 409
    assert client.patch(f"/api/projets/{pid}", json={"nom": ""},
                        headers=ADMIN).status_code == 422


def test_supprimer_un_projet_a_deux_refus_qui_se_nomment(client, db_path, decor):
    """Le projet de repli ne se supprime pas, et un projet qui porte une collection non
    plus. Vide, il part avec ses membres, et le journal le dit."""
    r = client.delete(f"/api/projets/{decor['repli']}", headers=ADMIN)
    assert r.status_code == 409 and "repli" in r.json()["detail"]
    r = client.delete(f"/api/projets/{decor['projet']}", headers=ADMIN)
    assert r.status_code == 409 and "1 collection(s)" in r.json()["detail"]
    assert len(_sql(db_path, "SELECT 1 FROM projet")) == 2

    vide = _projet(client, "À retirer")
    assert _membre(client, vide, "alice", role="responsable").status_code == 200
    assert client.delete(f"/api/projets/{vide}", headers=ALICE).status_code == 403
    assert client.delete(f"/api/projets/{vide}", headers=CAROL).status_code == 404
    assert client.delete(f"/api/projets/{vide}", headers=ADMIN).status_code == 204
    assert _sql(db_path, "SELECT 1 FROM projet WHERE id = ?", (vide,)) == []
    assert _sql(db_path, "SELECT 1 FROM projet_acces WHERE projet_id = ?", (vide,)) == []
    suppressions = [e for e in _evenements(db_path, "projet") if e["type"] == "suppression"]
    assert [(e["agent"], e["cible_id"], json.loads(e["avant"])) for e in suppressions] \
        == [("decor", vide, {"nom": "À retirer"})]


def test_le_repli_ne_se_supprime_pas_meme_vide(client, db_path):
    """Le refus du repli tient à son DRAPEAU, pas aux collections qu'il porte : vide — une
    instance neuve —, il se refuse encore."""
    pid = _repli(db_path)
    assert _sql(db_path, "SELECT 1 FROM collection") == []
    assert client.delete(f"/api/projets/{pid}").status_code == 409
    assert _repli(db_path) == pid


def test_la_justification_ne_se_rend_qu_a_qui_gere(client, decor):
    """Elle dit pourquoi le projet existe, à ceux qui en répondent : l'administrateur et la
    responsable la lisent. Un simple membre, et qui ne voit le projet que par une
    collection, ne reçoivent pas la clé — ni dans la liste, ni nulle part ailleurs."""
    pid = decor["projet"]
    client.patch(f"/api/projets/{pid}", json={"justification": "ZZJUSTIF7"}, headers=ADMIN)
    assert _membre(client, pid, "alice", role="responsable").status_code == 200
    assert _membre(client, pid, "bob").status_code == 200
    _acces(client, decor["collection"], "carol")

    def lue_par(headers):
        (p,) = [p for p in client.get("/api/projets", headers=headers).json()
                if p["id"] == pid]
        return p.get("justification", "clé absente")

    assert lue_par(ADMIN) == "ZZJUSTIF7"
    assert lue_par(ALICE) == "ZZJUSTIF7"
    assert lue_par(BOB) == "clé absente"
    assert lue_par(CAROL) == "clé absente"
    for headers in (BOB, CAROL):
        for chemin in ("/api/projets", "/api/collections", "/api/moi",
                       f"/api/albums/{decor['album']}/collections"):
            assert "ZZJUSTIF7" not in client.get(chemin, headers=headers).text, chemin


# --------------------------------------------------------------------------- #
# Régler qui est d'un projet
# --------------------------------------------------------------------------- #
def test_un_administrateur_fait_entrer_un_compte_et_un_groupe(client, db_path, decor):
    """Le geste de l'attendu : un compte, un groupe, chacun sous son rôle ; les
    responsables d'abord. `jamais_vu` rapporte ce que le miroir sait — vrai d'un login qui
    n'a ouvert aucune page, `None` d'un groupe, dont l'application ne sait rien."""
    pid = decor["projet"]
    client.get("/api/moi", headers=BOB)                    # bob a ouvert une page
    assert _membre(client, pid, "alice").status_code == 200
    assert _membre(client, pid, "bob").status_code == 200
    r = _membre(client, pid, " etudiants-bd-2026 ", role="responsable", genre="groupe")
    assert r.status_code == 200
    assert [(m["genre"], m["principal"], m["role"], m["jamais_vu"]) for m in r.json()] == [
        ("groupe", "etudiants-bd-2026", "responsable", None),
        ("utilisateur", "alice", "membre", True),
        ("utilisateur", "bob", "membre", False)]
    assert client.get(f"/api/projets/{pid}/membres", headers=ADMIN).json() == r.json()
    # Idempotent, et « nommer responsable » est le même geste.
    assert _membre(client, pid, "alice").status_code == 200
    assert _membre(client, pid, "alice", role="responsable").status_code == 200
    assert _sql(db_path, "SELECT role FROM projet_acces WHERE principal = 'alice'") \
        == [{"role": "responsable"}]


def test_la_responsable_regle_qui_entre_dans_son_projet(client, db_path, decor):
    """Faire entrer, faire sortir, nommer un autre responsable : dans SON projet, et là
    seulement. Par un groupe aussi — un labo répond d'un projet mieux qu'une personne."""
    pid, autre = decor["projet"], _projet(client, "Projet voisin")
    assert _membre(client, pid, "labo", role="responsable", genre="groupe").status_code == 200
    labo = {"Remote-User": "alice", "Remote-Groups": "labo"}

    assert _membre(client, pid, "bob", headers=labo).status_code == 200
    assert _membre(client, pid, "carol", role="responsable", headers=labo).status_code == 200
    assert client.delete(f"/api/projets/{pid}/membres/utilisateur/bob",
                         headers=labo).status_code == 204
    assert [m["principal"] for m in client.get(f"/api/projets/{pid}/membres",
                                               headers=CAROL).json()] == ["labo", "carol"]
    # Hors de son projet : celui qu'elle ne voit pas est introuvable.
    assert _membre(client, autre, "bob", headers=labo).status_code == 404
    assert _sql(db_path, "SELECT 1 FROM projet_acces WHERE projet_id = ?", (autre,)) == []


def test_un_simple_membre_ne_regle_ni_ne_lit_les_membres(client, db_path, decor):
    """Membre n'est pas responsable : la liste, l'ajout et le retrait lui répondent 403 en
    nommant qui le peut. Il n'apprend ni qui d'autre est du projet, ni qui en répond."""
    pid = decor["projet"]
    assert _membre(client, pid, "alice", role="responsable").status_code == 200
    assert _membre(client, pid, "bob").status_code == 200
    for r in (client.get(f"/api/projets/{pid}/membres", headers=BOB),
              client.get(f"/api/projets/{pid}/membres/choix", headers=BOB),
              _membre(client, pid, "carol", headers=BOB),
              _membre(client, pid, "bob", role="responsable", headers=BOB),
              client.delete(f"/api/projets/{pid}/membres/utilisateur/alice", headers=BOB)):
        assert r.status_code == 403 and "responsable" in r.json()["detail"], r.text
        assert "alice" not in r.text
    assert _sql(db_path, "SELECT principal, role FROM projet_acces ORDER BY principal") \
        == [{"principal": "alice", "role": "responsable"},
            {"principal": "bob", "role": "membre"}]


def test_un_membre_mal_forme_est_refuse(client, db_path, decor):
    pid = decor["projet"]
    for charge in ({"genre": "robot", "principal": "x", "role": "membre"},
                   {"genre": "utilisateur", "principal": "x", "role": "proprietaire"},
                   {"genre": "utilisateur", "principal": "   ", "role": "membre"}):
        r = client.put(f"/api/projets/{pid}/membres", json=charge, headers=ADMIN)
        assert r.status_code == 422, r.text
    assert client.delete(f"/api/projets/{pid}/membres/utilisateur/personne",
                         headers=ADMIN).status_code == 404
    assert _sql(db_path, "SELECT 1 FROM projet_acces") == []


def test_le_dernier_responsable_ne_part_pas(client, db_path, decor):
    """Un projet peut NAÎTRE sans responsable ; il ne perd pas son dernier. Rétrograder et
    retirer sont refusés par un 409 qui le dit, administrateur compris ; dès qu'un second
    existe, les deux gestes passent."""
    pid = decor["projet"]
    assert _membre(client, pid, "alice", role="responsable").status_code == 200
    for headers in (ALICE, ADMIN):
        r = _membre(client, pid, "alice", role="membre", headers=headers)
        assert r.status_code == 409 and "dernier responsable" in r.json()["detail"]
        r = client.delete(f"/api/projets/{pid}/membres/utilisateur/alice", headers=headers)
        assert r.status_code == 409 and "dernier responsable" in r.json()["detail"]
    assert _sql(db_path, "SELECT role FROM projet_acces WHERE principal = 'alice'") \
        == [{"role": "responsable"}]

    assert _membre(client, pid, "labo", role="responsable", genre="groupe").status_code == 200
    assert _membre(client, pid, "alice", role="membre").status_code == 200
    assert _membre(client, pid, "alice", role="responsable").status_code == 200
    assert client.delete(f"/api/projets/{pid}/membres/groupe/labo",
                         headers=ADMIN).status_code == 204


def test_les_gestes_sur_les_membres_sont_traces_et_ne_s_annulent_pas(client, db_path):
    """Qui a fait entrer qui : `lien` et `delien`, attribués, avec l'avant et l'après.
    Et Ctrl+Z n'y touche pas — défaire une entrée dans un projet par un raccourci clavier
    serait une surprise, comme pour un accès. Joué en mono-poste, où l'annulation ne filtre
    par aucun agent : s'il y avait quoi que ce soit d'annulable, elle le trouverait."""
    pid = _projet(client, "Séminaire")
    assert _membre(client, pid, "alice").status_code == 200
    assert _membre(client, pid, "alice", role="responsable").status_code == 200
    assert _membre(client, pid, "bob", role="responsable").status_code == 200
    assert client.delete(f"/api/projets/{pid}/membres/utilisateur/alice").status_code == 204

    assert [(e["type"], e["cible_id"], json.loads(e["avant"] or "null"),
             json.loads(e["apres"] or "null")) for e in _evenements(db_path, "projet_acces")] == [
        ("lien", pid, None,
         {"genre": "utilisateur", "principal": "alice", "role": "membre"}),
        ("lien", pid, {"genre": "utilisateur", "principal": "alice", "role": "membre"},
         {"genre": "utilisateur", "principal": "alice", "role": "responsable"}),
        ("lien", pid, None,
         {"genre": "utilisateur", "principal": "bob", "role": "responsable"}),
        ("delien", pid, {"genre": "utilisateur", "principal": "alice", "role": "responsable"},
         None)]
    creations = [e for e in _evenements(db_path, "projet") if e["type"] == "creation"]
    assert [(e["cible_id"], json.loads(e["apres"])) for e in creations] \
        == [(pid, {"nom": "Séminaire"})]

    assert client.get("/api/undo/prochain").json() is None
    assert client.post("/api/undo").status_code == 404
    assert _sql(db_path, "SELECT principal FROM projet_acces") == [{"principal": "bob"}]
    assert len(_sql(db_path, "SELECT 1 FROM projet")) == 2


def test_la_fiche_propose_les_groupes_et_verifie_les_membres(client, decor, monkeypatch):
    """`…/membres/choix` lit l'annuaire pour COMPOSER : des noms de groupe à proposer —
    sans les groupes de rôle ni d'administration — et l'état de chaque membre déjà posé.
    La pose, elle, n'a rien vérifié : un nom inconnu est entré, et c'est ici qu'il se
    signale."""
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", "doublure:")
    pid = decor["projet"]
    assert _membre(client, pid, "lectrice", role="responsable").status_code == 200
    assert _membre(client, pid, "fautedefrappe").status_code == 200
    assert _membre(client, pid, "annotateurs", genre="groupe").status_code == 200

    for headers in (ADMIN, {"Remote-User": "lectrice"}):
        vue = client.get(f"/api/projets/{pid}/membres/choix", headers=headers).json()
        assert vue["annuaire"]["etat"] == "lu"
        assert vue["groupes"] == ["annotateurs", "cours-vide", "etudiants-bd-2026"]
        assert vue["membres"] == [
            {"par": "compte", "login": "fautedefrappe", "groupe": None,
             "verification": "inconnu"},
            {"par": "compte", "login": "lectrice", "groupe": None, "verification": "trouve"},
            {"par": "groupe", "login": None, "groupe": "annotateurs",
             "verification": "trouve"}]
    assert client.get(f"/api/projets/{pid}/membres/choix", headers=CAROL).status_code == 404


# --------------------------------------------------------------------------- #
# Une collection naît dans UN projet
# --------------------------------------------------------------------------- #
def test_creer_une_collection_sans_projet_n_a_pas_change(client, db_path, derriere_proxy):
    """Sans `projet_id`, ou en nommant le repli : une identité suffit, comme avant la v29.
    Alice n'est membre de rien, et crée dans le premier projet — l'écran, qui enverra
    toujours le projet courant, ne ferme donc pas ce que l'API laisse ouvert."""
    repli = _repli(db_path)
    r = client.post("/api/collections", json={"nom": "Sans rien dire"}, headers=ALICE)
    assert r.status_code == 201 and r.json()["projet_id"] == repli
    r = client.post("/api/collections", json={"nom": "En nommant le repli",
                                              "projet_id": repli}, headers=ALICE)
    assert r.status_code == 201 and r.json()["projet_id"] == repli
    assert r.json()["acces"][0]["niveau"] == "proprietaire"
    assert client.post("/api/collections", json={"nom": "Anonyme", "projet_id": repli},
                       headers={}).status_code == 403


def test_creer_une_collection_dans_un_autre_projet_demande_d_en_etre(client, db_path,
                                                                    decor):
    """Dans un projet qui n'est pas le repli, il faut en être MEMBRE. 404 à qui ne le voit
    pas — et à un projet qui n'existe pas, la même réponse ; 403 nommé à qui en lit le nom
    par une collection sans en être. La membre crée, devient propriétaire de SA collection,
    et celle-ci est du projet."""
    pid = decor["projet"]
    _acces(client, decor["collection"], "bob")
    assert _membre(client, pid, "alice").status_code == 200

    assert client.post("/api/collections", json={"nom": "X", "projet_id": pid},
                       headers=CAROL).status_code == 404
    assert client.post("/api/collections", json={"nom": "X", "projet_id": 9999},
                       headers=ADMIN).status_code == 404
    r = client.post("/api/collections", json={"nom": "X", "projet_id": pid}, headers=BOB)
    assert r.status_code == 403 and "membre" in r.json()["detail"]
    assert _sql(db_path, "SELECT 1 FROM collection WHERE nom = 'X'") == []

    r = client.post("/api/collections", json={"nom": "La mienne", "projet_id": pid},
                    headers=ALICE)
    assert r.status_code == 201 and r.json()["projet_id"] == pid
    assert [(a["principal"], a["niveau"]) for a in r.json()["acces"]] \
        == [("alice", "proprietaire")]
    assert _sql(db_path, "SELECT projet_id FROM collection WHERE nom = 'La mienne'") \
        == [{"projet_id": pid}]
    vue = client.get("/api/collections", headers=ALICE).json()
    assert [(c["nom"], c["projet_nom"]) for c in vue] == [("La mienne", "Séminaire")]


def test_aucune_route_ne_deplace_une_collection(client, db_path, decor):
    """Une collection naît dans un projet et y reste : la modifier en nommant un autre
    projet ne la déplace pas — le champ n'existe pas dans ce qu'on peut modifier."""
    r = client.patch(f"/api/collections/{decor['collection']}", headers=ADMIN,
                     json={"description": "d", "projet_id": decor["repli"]})
    assert r.status_code == 200 and r.json()["projet_id"] == decor["projet"]
    assert _sql(db_path, "SELECT projet_id FROM collection WHERE id = ?",
                (decor["collection"],)) == [{"projet_id": decor["projet"]}]


# --------------------------------------------------------------------------- #
# Un rangement ne traverse pas les projets
# --------------------------------------------------------------------------- #
def test_ranger_un_album_dans_un_autre_projet_est_refuse(client, db_path, decor):
    """Dans les deux sens, par un 409 qui le nomme, à l'administrateur comme aux autres :
    un album du Séminaire ne se range pas dans le repli, ni l'inverse. À l'intérieur d'un
    projet, ranger reste ce qu'il était — et re-poser un rangement existant ne coûte rien."""
    ici = _collection(client, "Du repli")
    voisine = _collection(client, "Voisine du séminaire", projet_id=decor["projet"])
    du_repli = _album(client, "Tintin au Tibet", ici)

    for album, collection in ((decor["album"], ici), (du_repli, decor["collection"])):
        r = client.put(f"/api/albums/{album}/collections/{collection}", headers=ADMIN)
        assert r.status_code == 409 and "ne traverse pas les projets" in r.json()["detail"]
    assert client.put(f"/api/albums/{decor['album']}/collections/{voisine}",
                      headers=ADMIN).status_code == 201
    assert client.put(f"/api/albums/{decor['album']}/collections/{decor['collection']}",
                      headers=ADMIN).status_code == 201
    assert _sql(db_path, "SELECT album_id, collection_id FROM collection_album "
                         "ORDER BY album_id, collection_id") == [
        {"album_id": decor["album"], "collection_id": decor["collection"]},
        {"album_id": decor["album"], "collection_id": voisine},
        {"album_id": du_repli, "collection_id": ici}]


def test_une_collection_sans_projet_nomme_est_du_repli_pour_le_rangement(client, db_path,
                                                                        decor):
    """La règle de lecture vaut pour ce refus : une collection posée par `INSERT`, sans
    projet nommé, accueille un album du repli et refuse un album du Séminaire."""
    _sql(db_path, "INSERT INTO collection (id, nom) VALUES (70, 'Posée à la main')")
    du_repli = _album(client, "Tintin au Tibet", _collection(client, "Du repli"))
    assert client.put(f"/api/albums/{du_repli}/collections/70",
                      headers=ADMIN).status_code == 201
    assert client.put(f"/api/albums/{decor['album']}/collections/70",
                      headers=ADMIN).status_code == 409


def test_l_outil_refuse_aussi_un_rangement_qui_traverse(client, db_path, decor):
    """Deux portes vers les mêmes lignes, dont une seule gardée, ce n'est pas une garde :
    `ajouter` et `creer --albums` refusent ce que la route refuse, et rien n'est écrit."""
    avant = _sql(db_path, "SELECT album_id, collection_id FROM collection_album")
    code, _, err = _outil(db_path, "gerer_collections.py", "creer", "--nom", "Du repli",
                          "--albums", str(decor["album"]))
    assert code != 0 and "ne traverse pas les projets" in err
    ici = _collection(client, "Du repli, par la route")
    du_repli = _album(client, "Tintin au Tibet", ici)
    code, _, err = _outil(db_path, "gerer_collections.py", "ajouter",
                          str(decor["collection"]), "--albums", str(du_repli))
    assert code != 0 and "ne traverse pas les projets" in err
    assert _sql(db_path, "SELECT nom FROM collection WHERE nom = 'Du repli'") == []
    assert _sql(db_path, "SELECT album_id, collection_id FROM collection_album") \
        == avant + [{"album_id": du_repli, "collection_id": ici}]


# --------------------------------------------------------------------------- #
# Le projet ne sort de l'instance par aucun artefact
# --------------------------------------------------------------------------- #
def _outil(db_path, outil, *args):
    """Lance un outil de `tools/` en sous-processus, sur la base de test."""
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(db_path.parent)}
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")    # le sous-processus voit tout
    finally:
        conn.close()
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / outil), *args],
                       cwd=str(REPO_ROOT), env=env, capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def _fouillable(blob: bytes) -> str:
    """Le contenu d'une sortie, archives dépliées : un zip lu en octets ne prouve rien."""
    if blob[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            return "\n".join(z.read(n).decode("utf-8", "replace") for n in z.namelist())
    return blob.decode("utf-8", "replace")


def test_le_projet_ne_sort_d_aucun_artefact(client, db_path, tmp_path, png_bytes):
    """La collection reste l'unité de dépôt et le titre d'un export ; le projet n'en est
    pas un. Son nom, sa description, sa justification et sa colonne ne partent ni par les
    exports d'album, ni par la voie du dépôt, ni par les outils — et les actes qui le
    règlent ne sortent pas du journal. Le semis est son propre témoin : ce qu'on cherche
    par son absence est d'abord vu là où il doit être."""
    marques = ("ZZPROJET7", "ZZDESCR7", "ZZJUSTIF7", "zzmembre7")
    pid = client.post("/api/projets", json={
        "nom": "ZZPROJET7", "description": "ZZDESCR7", "justification": "ZZJUSTIF7"}
    ).json()["id"]
    assert _membre(client, pid, "zzmembre7", role="responsable", headers={}).status_code == 200
    cid = _collection(client, "Étude déposée", projet_id=pid, headers={})
    client.patch(f"/api/collections/{cid}", json={"statut_diffusion": "public"})
    aid = client.post("/api/albums", json={"titre": "Album", "collection_id": cid}).json()["id"]
    pl = client.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", png_bytes, "image/png")}).json()
    client.post(f"/api/planches/{pl['id']}/regions",
                json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9})

    temoin = client.get("/api/projets").text + client.get(
        f"/api/projets/{pid}/membres").text + json.dumps(_evenements(db_path, "projet"))
    assert all(m in temoin for m in marques), "le semis ne pose pas ce qu'on cherche"

    sorties = {}
    for chemin in (f"/api/export/json?album_id={aid}", f"/api/export/csv?album_id={aid}",
                   f"/api/export/tei?album_id={aid}",
                   f"/api/collections/{cid}/depot/description",
                   f"/api/collections/{cid}/depot/description?format=csv",
                   f"/api/collections/{cid}/depot/metadonnees",
                   f"/api/collections/{cid}/depot/metadonnees?format=zip",
                   f"/api/collections/{cid}/depot/iiif?base_url=https://images.example.org"):
        r = client.get(chemin)
        assert r.status_code == 200, (chemin, r.text[:300])
        sorties[chemin] = _fouillable(r.content)
    for outil, args, produits in (
            ("description_collection.py", ["--json", "-"], []),
            ("metadonnees_collection.py", ["--json", "-"], []),
            ("metadonnees_collection.py", ["--csv-dir", str(tmp_path / "csv")],
             [tmp_path / "csv"]),
            ("crosswalk_depot.py", ["--out-dir", str(tmp_path / "cw")], [tmp_path / "cw"]),
            ("provenance_export.py", ["--out-dir", str(tmp_path / "prov")],
             [tmp_path / "prov"]),
            ("iiif_manifest.py", ["--base-url", "http://exemple/iiif", "--out-dir",
                                  str(tmp_path / "iiif")], [tmp_path / "iiif"])):
        code, out, err = _outil(db_path, outil, *args)
        assert code == 0, (outil, err[-600:])
        fichiers = [f for d in produits for f in Path(d).glob("**/*") if f.is_file()]
        sorties[f"{outil} {args[0]}"] = out + err + "\n".join(
            _fouillable(f.read_bytes()) for f in fichiers)

    for surface, texte in sorties.items():
        assert len(texte) > 40, f"{surface} : sortie vide, le contrôle ne mesure rien"
        for interdit in (*marques, "projet_id", "justification"):
            assert interdit not in texte, f"{surface} laisse sortir « {interdit} »"
