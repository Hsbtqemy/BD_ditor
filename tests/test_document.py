"""COL-3, tranche 2, premier commit — le document existe, et rien d'autre ne change.

Tout album devient la COPIE DE TRAVAIL d'un DOCUMENT, qui appartient à l'instance : une
identité que rien ne réattribue, et une origine. Ces tests tiennent quatre choses.

1. La MIGRATION v30, sur une base v29 qui a vécu : chaque album d'hier reçoit son document,
   avec ce qu'on sait de son origine et rien de plus — personne n'a jamais écrit qui avait
   importé, donc elle n'en invente aucun. Elle ne se rejoue pas, et rejouée de force elle
   ne double rien.
2. Les ÉCRITURES : créer un album fait naître son document ; importer, ranger, retirer,
   détruire s'écrivent au journal, attribués, sous l'identifiant du document.
3. La règle de LECTURE du projet d'une copie, écrite une fois.
4. CE QUE LE COMMIT NE CHANGE PAS : rien de ce qui s'écrit ne sort de l'instance, ne
   s'annule par Ctrl+Z, ne compte comme du travail laissé, ni ne décale un pseudonyme.

Ce que ces tests ne tiennent PAS : la règle de qui détruit, les demandes et l'écran du
fonds n'existent pas encore. Les deux tables de demande naissent ici, vides.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

import comptes
import database
import journal
import pipeline.sharedocs as sd
from conftest import ADMIN, make_png
from test_projets import _fouillable, _outil, _repli, _sql

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

ALICE = {"Remote-User": "alice"}
BOB = {"Remote-User": "bob"}


# --------------------------------------------------------------------------- #
# Outils de décor
# --------------------------------------------------------------------------- #
def _conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _evenements(db_path, *tables):
    """Les actes du fonds, dans l'ordre, charges décodées."""
    marques = ", ".join("?" * len(tables))
    return [(e["cible_table"], e["type"], e["agent"], e["cible_id"],
             json.loads(e["avant"] or "null"), json.loads(e["apres"] or "null"))
            for e in _sql(db_path, "SELECT cible_table, type, agent, cible_id, avant, apres "
                                   f"FROM evenement WHERE cible_table IN ({marques}) "
                                   "ORDER BY id", tables)]


def _actes(db_path, document_id, type_=None):
    """Les actes du fonds écrits sous CE document — le décor en écrit d'autres, sous le
    sien."""
    return [a for a in _evenements(db_path, "document", "collection_album")
            if a[3] == document_id and type_ in (None, a[1])]


def _album_ligne(db_path, album_id):
    lignes = _sql(db_path, "SELECT document_id, projet_id FROM albums WHERE id = ?",
                  (album_id,))
    return lignes[0] if lignes else None


def _decaler_les_identifiants(client, headers=ADMIN):
    """Fait que l'id du prochain DOCUMENT ne soit plus celui du prochain ALBUM. Sans ce
    décalage, un journal qui écrirait l'album à la place du document passerait tous les
    contrôles de ce fichier.

    Un album créé puis détruit y suffisait tant que l'identifiant d'album se réattribuait.
    Depuis la v30 aucun des deux ne revient (AUTOINCREMENT) : les deux compteurs avancent
    ensemble, et c'est un document SEUL, né et retiré par SQL, qui les décale. L'album
    créé puis détruit reste, pour les actes qu'il laisse à `headers`."""
    r = client.post("/api/albums", json={"titre": "Décalage"}, headers=headers)
    assert r.status_code == 201, r.text
    assert client.delete(f"/api/albums/{r.json()['id']}", headers=headers).status_code == 204
    with database.connect() as c:
        seul = c.execute("INSERT INTO document (importe_par) VALUES (NULL)").lastrowid
        c.execute("DELETE FROM document WHERE id = ?", (seul,))


@pytest.fixture
def decor(client, db_path, derriere_proxy):
    """Derrière le proxy : le projet « Séminaire », où alice POSSÈDE la collection
    « Émotions » et bob y écrit ; et « Voisine », du même projet, où alice écrit aussi.
    Les identifiants d'album et de document sont décalés d'entrée."""
    _decaler_les_identifiants(client)
    pid = client.post("/api/projets", json={"nom": "Séminaire"}, headers=ADMIN).json()["id"]
    cols = {}
    for nom in ("Émotions", "Voisine"):
        r = client.post("/api/collections", json={"nom": nom, "projet_id": pid},
                        headers=ADMIN)
        assert r.status_code == 201, r.text
        cols[nom] = r.json()["id"]
        for principal, niveau in (("alice", "proprietaire"), ("bob", "ecriture")):
            if nom == "Voisine" and principal == "bob":
                continue
            assert client.put(
                f"/api/collections/{cols[nom]}/acces", headers=ADMIN,
                json={"genre": "utilisateur", "principal": principal,
                      "niveau": niveau}).status_code in (200, 201)
    return {"projet": pid, "repli": _repli(db_path), "emotions": cols["Émotions"],
            "voisine": cols["Voisine"]}


def _creer(client, titre, collection_id=None, headers=ALICE) -> int:
    charge = {"titre": titre} if collection_id is None else {
        "titre": titre, "collection_id": collection_id}
    r = client.post("/api/albums", json=charge, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# --------------------------------------------------------------------------- #
# La migration v29 → v30
# --------------------------------------------------------------------------- #
def _ramener_en_v29(db):
    """Défait la v30 sur une base neuve, pour rejouer un upgrade RÉEL (le patron de
    `test_projets._ramener_en_v28`). Les index d'abord : SQLite refuse de retirer une
    colonne qu'un index nomme. Puis la dernière colonne avant l'avant-dernière."""
    conn = sqlite3.connect(db)
    # La base du projet de repli, née avec la base neuve (v31, D10), n'existait pas en v29.
    conn.execute("DELETE FROM collection WHERE base = 1")
    conn.execute("DROP INDEX IF EXISTS idx_albums_projet")
    conn.execute("DROP INDEX IF EXISTS idx_albums_document")
    conn.execute("ALTER TABLE albums DROP COLUMN projet_id")
    conn.execute("ALTER TABLE albums DROP COLUMN document_id")
    conn.execute("DROP TABLE demande_document")
    conn.execute("DROP TABLE demande")
    conn.execute("DROP TABLE document")
    conn.execute("PRAGMA user_version = 29")
    conn.commit()
    conn.close()


@pytest.fixture
def base_v29(tmp_path, monkeypatch):
    """Une base au schéma v29 qui a VÉCU. Deux projets — le repli (1) et « Séminaire » (2).

    Six albums, chacun un cas :
      1  rangé dans une collection du repli, annoté par alice (trois actes au journal) ;
      2  rangé dans DEUX collections du repli ;
      3  rangé dans la collection du Séminaire ;
      4  rangé nulle part — une base retouchée à la main ;
      5  rangé dans une collection SANS projet nommé, et sans date d'import ;
      6  rangé dans DEUX PROJETS — l'état que la v29 interdit et qu'une base retouchée peut
         porter : la collection 3 (Séminaire) et la collection 5 (repli). Les identifiants
         sont choisis pour que « la collection de plus petit id » (3, donc le Séminaire) ne
         se confonde ni avec la plus grande, ni avec le projet de plus petit id.
    """
    db = tmp_path / "v29.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db)
    database.init_db()
    _ramener_en_v29(db)
    assert "document_id" not in {c["name"] for c in _sql(db, "PRAGMA table_info(albums)")}
    _sql(db, "INSERT INTO projet (id, nom, repli) VALUES (2, 'Séminaire', 0)")
    for cid, nom, projet in ((1, "Corpus colonial", 1), (2, "Incubateur", 1),
                             (3, "Émotions", 2), (4, "Posée à la main", None),
                             (5, "Du repli, créée plus tard", 1)):
        _sql(db, "INSERT INTO collection (id, nom, projet_id) VALUES (?, ?, ?)",
             (cid, nom, projet))
    for aid, titre, date in ((1, "Le Lotus bleu", "2026-07-20 09:00:00"),
                             (2, "Tintin au Tibet", "2026-08-02 10:30:00"),
                             (3, "L'Affaire Tournesol", "2026-09-14 16:45:00"),
                             (4, "Rangé nulle part", "2026-09-30 08:00:00"),
                             (5, "Sans date", None),
                             (6, "Dans deux projets", "2026-10-01 12:00:00")):
        _sql(db, "INSERT INTO albums (id, titre, auteur, serie, annee, date_import) "
                 "VALUES (?, ?, 'Hergé', 'Tintin', 1936, ?)", (aid, titre, date))
    for cid, aid in ((1, 1), (1, 2), (2, 2), (3, 3), (4, 5), (3, 6), (5, 6)):
        _sql(db, "INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
             (cid, aid))
    _sql(db, "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
             "VALUES (1, 'utilisateur', 'alice', 'ecriture')")
    _sql(db, "INSERT INTO planches (id, album_id, numero, chemin_web) VALUES (1, 1, 1, 'w')")
    _sql(db, "INSERT INTO regions (id, planche_id, type) VALUES (1, 1, 'bulle')")
    for type_ in ("creation", "modification", "modification"):
        _sql(db, "INSERT INTO evenement (type, agent, agent_type, cible_table, cible_id) "
                 "VALUES (?, 'alice', 'humain', 'regions', 1)", (type_,))
    return db


def _photographie(db):
    """Ce que la migration ne doit pas toucher : le travail, les rangements, le journal —
    et la NOTICE de chaque album, c'est-à-dire toutes ses colonnes sauf les deux qu'elle
    ajoute. Sans `albums` ici, une migration qui réécrirait le titre de chaque album
    passait la suite entière (mutant de la relecture croisée)."""
    photo = {t: _sql(db, f"SELECT * FROM {t} ORDER BY 1, 2")
             for t in ("planches", "regions", "collection_album",
                       "collection_acces", "projet", "projet_acces", "evenement")}
    # La v31 passe aussi (COL-3, tranche 3, D10) : elle donne sa collection de BASE à tout
    # projet qui n'en a pas — ici le Séminaire. La photographie ne compte que les autres.
    photo["collection"] = _sql(db, "SELECT * FROM collection WHERE base = 0 ORDER BY 1, 2")
    photo["albums"] = [{k: v for k, v in a.items() if k not in ("document_id", "projet_id")}
                       for a in _sql(db, "SELECT * FROM albums ORDER BY id")]
    assert all(len(a) >= 17 for a in photo["albums"]), "la notice n'est plus photographiée"
    return photo


def test_la_migration_fait_de_chaque_album_la_copie_d_un_document(base_v29):
    """Chaque album d'hier devient l'unique copie d'un document neuf, avec ce qu'on SAIT
    de son origine : la date de son import, et le projet où il vit. Rien d'autre ne bouge
    — ni le travail, ni les rangements, ni le journal, où la migration n'écrit rien."""
    avant = _photographie(base_v29)
    database.init_db()                                   # upgrade réel v29 → v30
    assert _sql(base_v29, "PRAGMA user_version")[0]["user_version"] == database.SCHEMA_VERSION

    albums = _sql(base_v29, "SELECT id, document_id, projet_id FROM albums ORDER BY id")
    documents = {d["id"]: d for d in _sql(base_v29, "SELECT * FROM document")}
    assert len(documents) == 6 and len({a["document_id"] for a in albums}) == 6
    assert database.albums_sans_document(_conn(base_v29)) == []

    # Le projet de chaque copie, ÉCRIT : lu dans ses collections, y compris par la règle
    # du repli pour une collection sans projet nommé. Rangé nulle part : aucun, et pas le
    # repli — la migration ne lui en invente pas. Rangé dans DEUX projets : celui de sa
    # collection de plus petit id (la 3, donc le Séminaire), ce qui est un choix et pas un
    # fait…
    assert [(a["id"], a["projet_id"]) for a in albums] \
        == [(1, 1), (2, 1), (3, 2), (4, None), (5, 1), (6, 2)]
    # …et c'est d'avoir ÉCRIT ce choix qui rend l'écart visible : la migration ne le
    # tait pas, la formulation exécutable le nomme dès le premier démarrage.
    assert database.albums_hors_de_leur_projet(_conn(base_v29)) == [6]
    origine = {a["id"]: documents[a["document_id"]] for a in albums}
    assert {aid: (d["importe_le"], d["projet_origine_id"]) for aid, d in origine.items()} == {
        1: ("2026-07-20 09:00:00", 1), 2: ("2026-08-02 10:30:00", 1),
        3: ("2026-09-14 16:45:00", 2), 4: ("2026-09-30 08:00:00", None),
        5: (None, 1),                # une date absente reste absente, pas « aujourd'hui »
        6: ("2026-10-01 12:00:00", 2)}

    index = {r["name"] for r in _sql(base_v29, "SELECT name FROM sqlite_master "
                                               "WHERE type = 'index'")}
    assert {"idx_albums_document", "idx_albums_projet"} <= index
    assert _photographie(base_v29) == avant
    assert _sql(base_v29, "SELECT 1 FROM demande") == []
    assert _sql(base_v29, "SELECT 1 FROM demande_document") == []


def test_la_migration_n_invente_aucun_importateur(base_v29):
    """« Inconnu veut dire demander » (tranché le 2026-10-11) : sur tout l'existant, qui a
    importé n'est écrit nulle part. Alice a pourtant posé les trois seuls actes du journal
    sur l'album 1, et elle seule y a un accès — c'est un indice, pas un fait, et la
    migration ne le lit pas."""
    database.init_db()
    assert _sql(base_v29, "SELECT DISTINCT importe_par FROM document") \
        == [{"importe_par": None}]


def test_la_migration_ne_se_rejoue_pas(base_v29, monkeypatch):
    """Une migration de DONNÉES est gatée par la version. Rejouée à l'upgrade suivant,
    elle donnerait un document « d'origine inconnue » à un album né APRÈS sans le sien :
    la faute d'un chemin d'écriture se lirait comme un album d'avant le fonds, et
    `albums_sans_document` ne la dirait plus. Les deux façons de la rejouer sont
    éprouvées — un redémarrage, et l'upgrade SUIVANT, que seul le `if version < 30`
    arrête."""
    database.init_db()
    _sql(base_v29, "INSERT INTO albums (id, titre) VALUES (60, 'Né après, sans document')")
    _sql(base_v29, "INSERT INTO collection_album (collection_id, album_id) VALUES (3, 60)")
    _sql(base_v29, "UPDATE document SET importe_par = 'alice' WHERE id = 1")   # un fait d'APRÈS

    def etat():
        return (_sql(base_v29, "SELECT id, importe_par FROM document ORDER BY id"),
                _sql(base_v29, "SELECT document_id, projet_id FROM albums WHERE id = 60"))
    attendu = ([{"id": 1, "importe_par": "alice"}]
               + [{"id": i, "importe_par": None} for i in (2, 3, 4, 5, 6)],
               [{"document_id": None, "projet_id": None}])

    database.init_db()                                   # redémarrage : rien ne bouge
    assert etat() == attendu
    monkeypatch.setattr(database, "SCHEMA_VERSION", database.SCHEMA_VERSION + 1)
    database.init_db()                                   # l'upgrade suivant non plus
    assert etat() == attendu
    assert database.albums_sans_document(_conn(base_v29)) == [60]


@pytest.mark.parametrize("version", [29, 26])
def test_la_migration_rejouee_de_force_ne_double_rien(base_v29, version):
    """Elle est IDEMPOTENTE en plus d'être gatée, et il le faut : plusieurs fichiers de
    test ramènent `user_version` en arrière sur une base au schéma courant, et l'étape
    repasse alors sur des albums qui ont déjà leur document. Elle ne touche que ce qui
    est NULL — ni un second document, ni une origine réécrite, ni un projet changé."""
    database.init_db()
    _sql(base_v29, "UPDATE document SET importe_par = 'alice' WHERE id = 1")
    # Un projet ÉCRIT qui ne se lit plus dans les collections : la copie 3 retirée de tout.
    _sql(base_v29, "DELETE FROM collection_album WHERE album_id = 3")

    def etat():
        return (_sql(base_v29, "SELECT * FROM document ORDER BY id"),
                _sql(base_v29, "SELECT id, document_id, projet_id FROM albums ORDER BY id"))
    avant = etat()
    _sql(base_v29, f"PRAGMA user_version = {version}")
    database.init_db()
    assert _sql(base_v29, "PRAGMA user_version")[0]["user_version"] == database.SCHEMA_VERSION
    assert etat() == avant


def test_la_migration_tient_sur_un_schema_minimal(tmp_path):
    """Neuf fichiers de test montent un `albums (id, titre)` réduit avant d'appeler
    `_migrate` : sans `document` autour, il ne reçoit ni colonne ni clé vers rien. Et
    avec les tables du fonds autour d'un album sans date d'import, la migration fait son
    document sans chercher la colonne qui manque."""
    conn = sqlite3.connect(tmp_path / "mini.sqlite")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE albums (id INTEGER PRIMARY KEY, titre TEXT);"
        "CREATE TABLE planches (id INTEGER PRIMARY KEY, album_id INT, numero INT);"
        "INSERT INTO albums (id, titre) VALUES (1, 'Seul');"
        "PRAGMA user_version = 16;")
    database._migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    assert "document_id" not in {r["name"] for r in conn.execute("PRAGMA table_info(albums)")}
    conn.close()

    conn = sqlite3.connect(tmp_path / "mini2.sqlite")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE albums (id INTEGER PRIMARY KEY, titre TEXT);"
        "CREATE TABLE planches (id INTEGER PRIMARY KEY, album_id INT, numero INT);"
        "CREATE TABLE projet (id INTEGER PRIMARY KEY, nom TEXT, repli INT);"
        "CREATE TABLE document (id INTEGER PRIMARY KEY AUTOINCREMENT, importe_par TEXT,"
        "  importe_le TEXT DEFAULT (datetime('now')), projet_origine_id INTEGER);"
        "INSERT INTO albums (id, titre) VALUES (7, 'Seul');"
        "PRAGMA user_version = 29;")
    database._migrate(conn)
    assert [tuple(r) for r in conn.execute(
        "SELECT a.id, d.importe_par, d.importe_le, d.projet_origine_id, a.projet_id "
        "FROM albums a JOIN document d ON d.id = a.document_id")] \
        == [(7, None, None, None, None)]
    conn.close()


def test_une_base_migree_porte_le_schema_d_une_base_neuve(base_v29, tmp_path, monkeypatch):
    """Les deux colonnes arrivent par `CREATE TABLE` sur une base neuve et par `ALTER` sur
    une base migrée : même nom, même type, même rang, mêmes clés étrangères, mêmes index.
    Deux schémas qui divergeraient ici ne se verraient qu'à la première requête qui compte
    sur l'un des deux."""
    database.init_db()

    def forme(db):
        return (_sql(db, "PRAGMA table_info(albums)"),
                sorted((f["from"], f["table"], f["to"], f["on_delete"])
                       for f in _sql(db, "PRAGMA foreign_key_list(albums)")),
                sorted(i["name"] for i in _sql(db, "PRAGMA index_list(albums)")),
                {t: _sql(db, f"PRAGMA table_info({t})")
                 for t in ("document", "demande", "demande_document")},
                {i["name"]: [c["name"] for c in _sql(db, f"PRAGMA index_info({i['name']})")]
                 for t in ("albums", "demande_document")
                 for i in _sql(db, f"PRAGMA index_list({t})") if i["origin"] == "c"})
    migree = forme(base_v29)
    neuve = tmp_path / "neuve.sqlite"
    monkeypatch.setattr(database, "DB_PATH", neuve)
    database.init_db()
    assert forme(neuve) == migree
    assert migree[1] == [("document_id", "document", "id", "NO ACTION"),
                         ("projet_id", "projet", "id", "NO ACTION")]
    assert [c["name"] for c in migree[0]][-2:] == ["document_id", "projet_id"]
    # Les index NOMMÉS, colonne comprise : comparer deux bases qui l'auraient toutes deux
    # perdu ne dirait rien. Celui de `demande_document` n'était tenu par aucun test.
    assert migree[4] == {"idx_albums_document": ["document_id"],
                         "idx_albums_projet": ["projet_id"],
                         "idx_demande_document_document": ["document_id"]}


def test_un_identifiant_de_document_ne_se_reattribue_pas(client, db_path):
    """Le journal survit à sa cible : un identifiant rendu au suivant mêlerait l'histoire
    de deux documents. Jusqu'à la v30 c'était le cas d'`albums.id` — le dernier album
    détruit rendait son numéro, donc son dossier d'images — et c'est pourquoi le document
    ne s'identifie pas par sa copie ; depuis la v30, l'album ne le rend plus non plus
    (`tests/test_identifiants_v30.py`). Même garantie pour une demande, qui survit à ce
    qu'elle a fait disparaître."""
    premier = _creer(client, "Premier", headers={})
    second = _creer(client, "Second", headers={})
    doc_second = _album_ligne(db_path, second)["document_id"]
    assert client.delete(f"/api/albums/{second}").status_code == 204
    troisieme = _creer(client, "Troisième", headers={})

    assert troisieme > second
    doc_troisieme = _album_ligne(db_path, troisieme)["document_id"]
    assert doc_troisieme > doc_second
    assert _album_ligne(db_path, premier)["document_id"] < doc_second

    conn = sqlite3.connect(db_path)
    try:
        un = conn.execute("INSERT INTO demande (genre) VALUES ('x')").lastrowid
        conn.execute("DELETE FROM demande WHERE id = ?", (un,))
        assert conn.execute("INSERT INTO demande (genre) VALUES ('x')").lastrowid > un
    finally:
        conn.close()                                     # rien n'est validé


def test_un_projet_et_une_collection_rendent_leur_identifiant(client):
    """Pourquoi une demande garde le NOM de son projet (`demande.projet_nom`) et un emploi
    celui de sa collection, à côté de l'identifiant : supprimée, une collection rend son
    numéro au suivant. Une demande répondue reste en base, le journal survit à sa cible —
    sans le nom, il désignerait l'étude créée ensuite.

    Si ce test tombe parce qu'un identifiant a cessé de se réattribuer, le nom gardé n'a
    plus cette raison-là d'exister : c'est à relire, pas à réparer. C'est arrivé au PROJET
    (v31, COL-3, tranche 3, D8) : son identifiant ne revient plus, et cette moitié du test a
    été relue. `demande.projet_nom` garde une raison, moindre : un projet supprimé ne se lit
    plus, et son nom est alors tout ce qui dit de quoi parlait la demande — comme
    `document.projet_origine_nom` pour l'origine d'un document. Puis à la COLLECTION (v35,
    COL-4) : les bacs à sable en font naître et mourir des dizaines par semaine, et son
    identifiant ne revient plus non plus ; `demande.collection_nom` et le nom d'un emploi
    gardent la même raison moindre que `demande.projet_nom`."""
    projets = []
    for nom in ("Éphémère", "Tout autre"):
        projets.append(client.post("/api/projets", json={"nom": nom}).json()["id"])
        if nom == "Éphémère":
            assert client.delete(f"/api/projets/{projets[0]}").status_code == 204
    assert projets[1] > projets[0]
    collections = []
    for nom in ("Une étude", "Une autre"):
        collections.append(client.post("/api/collections", json={"nom": nom}).json()["id"])
        if nom == "Une étude":
            assert client.delete(f"/api/collections/{collections[0]}").status_code == 204
    assert collections[1] > collections[0]


def test_les_tables_de_demande_naissent_vides_et_rien_ne_les_ecrit(client, db_path, decor,
                                                                    png_bytes):
    """Elles arrivent avec le document pour que le schéma ne change qu'une fois dans la
    tranche. Leurs colonnes sont dites ici — c'est ce sur quoi les routes de demande
    seront bâties — ; et un parcours entier n'y écrit aucune ligne."""
    colonnes = {t: [c["name"] for c in _sql(db_path, f"PRAGMA table_info({t})")]
                for t in ("document", "demande", "demande_document")}
    # La v31 (COL-3, tranche 3) ajoute le nom du projet d'origine, la collection d'arrivée
    # d'une demande et la copie née d'une acceptation ; la v32 (tranche 3b), le cran d'une
    # copie amorcée ou d'une remise à zéro demandée.
    assert colonnes == {
        "document": ["id", "importe_par", "importe_le", "projet_origine_id",
                     "projet_origine_nom"],
        "demande": ["id", "genre", "demandeur", "motif", "certifie_le", "projet_id",
                    "projet_nom",
                    "date_creation", "reponse", "repondu_par", "date_reponse",
                    "collection_id", "collection_nom", "cran"],
        "demande_document": ["demande_id", "document_id", "album_id", "titre", "reponse",
                             "copie_id"]}

    aid = _creer(client, "Parcours", decor["emotions"])
    pl = client.post(f"/api/albums/{aid}/import", headers=ALICE,
                     files={"file": ("p.png", png_bytes, "image/png")}).json()
    client.put(f"/api/albums/{aid}/collections/{decor['voisine']}", headers=ALICE)
    client.delete(f"/api/albums/{aid}/collections/{decor['voisine']}", headers=ALICE)
    client.delete(f"/api/planches/{pl['id']}", headers=ALICE)
    client.delete(f"/api/albums/{aid}", headers=ALICE)
    assert _sql(db_path, "SELECT 1 FROM demande") == []
    assert _sql(db_path, "SELECT 1 FROM demande_document") == []


# --------------------------------------------------------------------------- #
# Les écritures — naissance, scans, emplois, destruction
# --------------------------------------------------------------------------- #
def test_creer_un_album_fait_naitre_son_document(client, db_path, decor):
    """L'origine s'écrit à partir de ce jour : QUI a importé — le login de la requête —,
    QUAND, et dans QUEL projet d'abord, celui de la collection d'accueil. La copie porte
    son document et son projet ; le journal garde la naissance et le premier emploi, sous
    l'identifiant du DOCUMENT."""
    aid = _creer(client, "Le Lotus bleu", decor["emotions"])
    ligne = _album_ligne(db_path, aid)
    doc = ligne["document_id"]
    assert doc is not None and doc != aid, "le décor ne distingue plus album et document"
    assert ligne["projet_id"] == decor["projet"]
    origine = _sql(db_path, "SELECT * FROM document WHERE id = ?", (doc,))[0]
    assert (origine["importe_par"], origine["projet_origine_id"]) == ("alice", decor["projet"])
    assert origine["importe_le"]

    assert _actes(db_path, doc) == [
        ("document", "creation", "alice", doc, None,
         {"album_id": aid, "titre": "Le Lotus bleu"}),
        ("collection_album", "lien", "alice", doc, None,
         {"album_id": aid, "collection_id": decor["emotions"], "collection": "Émotions"})]


def test_un_album_cree_sans_collection_est_du_projet_de_repli(client, db_path, decor):
    """Sans collection nommée l'album tombe dans la collection de repli : son document
    entre donc par le projet de repli, et cela s'écrit comme le reste."""
    aid = _creer(client, "Sans collection", headers=ADMIN)
    ligne = _album_ligne(db_path, aid)
    assert ligne["projet_id"] == decor["repli"]
    assert _sql(db_path, "SELECT importe_par, projet_origine_id FROM document WHERE id = ?",
                (ligne["document_id"],)) == [{"importe_par": "decor",
                                              "projet_origine_id": decor["repli"]}]


def test_en_mono_poste_personne_n_a_importe(client, db_path):
    """Hors proxy personne ne s'annonce : le document naît, son importateur reste inconnu
    et l'agent de ses actes est vide — comme pour tout acte du mono-poste. Un en-tête
    d'identité envoyé là est ignoré, comme partout."""
    aid = _creer(client, "Seul devant sa machine", headers=ALICE)
    doc = _album_ligne(db_path, aid)["document_id"]
    assert _sql(db_path, "SELECT importe_par FROM document WHERE id = ?", (doc,)) \
        == [{"importe_par": None}]
    assert {a[2] for a in _evenements(db_path, "document", "collection_album")} == {None}


def test_le_client_ne_pose_ni_le_document_ni_le_projet(client, db_path, decor):
    """Les deux colonnes ne sont pas des champs de la notice : les envoyer à la création
    ou à la modification ne les pose pas. Sans quoi une requête rangerait sa copie dans le
    projet d'un autre, ou la ferait passer pour la copie d'un autre document."""
    autre = _creer(client, "Autre", decor["emotions"])
    doc_autre = _album_ligne(db_path, autre)["document_id"]
    r = client.post("/api/albums", headers=ALICE,
                    json={"titre": "Forcé", "collection_id": decor["emotions"],
                          "document_id": doc_autre, "projet_id": decor["repli"]})
    assert r.status_code == 201
    aid = r.json()["id"]
    attendu = _album_ligne(db_path, aid)
    assert attendu["document_id"] != doc_autre and attendu["projet_id"] == decor["projet"]
    r = client.put(f"/api/albums/{aid}", headers=ALICE,
                   json={"titre": "Forcé encore", "document_id": doc_autre,
                         "projet_id": decor["repli"]})
    assert r.status_code == 200 and r.json()["titre"] == "Forcé encore"
    assert _album_ligne(db_path, aid) == attendu


def test_importer_et_retirer_une_planche_s_ecrivent_sur_le_document(client, db_path, decor,
                                                                    png_bytes):
    """Un scan ajouté, un scan retiré : attribués à qui l'a fait — ici bob, qui n'a pas
    importé l'album —, sous l'identifiant du document. L'ajout porte son `apres`, le
    retrait son `avant`. Le retrait est fait par un administrateur : depuis que bob y a
    ajouté un scan, alice ne supprime plus de planche de cet album sans le demander
    (COL-3, tranche 2, décision B4)."""
    aid = _creer(client, "Le Lotus bleu", decor["emotions"])
    doc = _album_ligne(db_path, aid)["document_id"]
    r = client.post(f"/api/albums/{aid}/import", headers=BOB,
                    files={"file": ("p.png", png_bytes, "image/png")})
    assert r.status_code == 201, r.text
    pl = r.json()
    assert client.delete(f"/api/planches/{pl['id']}", headers=ALICE).status_code == 403
    assert client.delete(f"/api/planches/{pl['id']}", headers=ADMIN).status_code == 204

    charge = {"album_id": aid, "planche": {"id": pl["id"], "numero": pl["numero"]}}
    assert _actes(db_path, doc, "modification") == [
        ("document", "modification", "bob", doc, None, charge),
        ("document", "modification", ADMIN["Remote-User"], doc, charge, None)]
    # L'importateur du DOCUMENT, lui, n'a pas changé.
    assert _sql(db_path, "SELECT importe_par FROM document WHERE id = ?", (doc,)) \
        == [{"importe_par": "alice"}]


def test_les_emplois_s_ecrivent_et_un_rangement_repose_ne_s_ecrit_pas(client, db_path,
                                                                     decor):
    """Ranger (`lien`), retirer (`delien`) : datés et attribués. Re-poser un rangement
    existant n'écrit rien, un geste refusé non plus — le journal dit ce qui a eu lieu."""
    aid = _creer(client, "Le Lotus bleu", decor["emotions"])
    doc = _album_ligne(db_path, aid)["document_id"]
    chemin = f"/api/albums/{aid}/collections"
    assert client.put(f"{chemin}/{decor['voisine']}", headers=ALICE).status_code == 201
    assert client.put(f"{chemin}/{decor['voisine']}", headers=ALICE).status_code == 201
    assert client.delete(f"{chemin}/{decor['emotions']}", headers=ALICE).status_code == 204
    # Sortir de la dernière collection aboutit depuis le fonds (COL-3, tranche 2) et
    # s'écrit ; ranger la copie gardée dans une collection d'un autre projet est refusé.
    assert client.delete(f"{chemin}/{decor['voisine']}", headers=ALICE).status_code == 204
    ailleurs = client.post("/api/collections", json={"nom": "Du repli"},
                           headers=ADMIN).json()["id"]
    assert client.put(f"{chemin}/{ailleurs}", headers=ADMIN).status_code == 409
    # Et la fonction unique n'écrit que des emplois : tout autre type est une faute
    # d'appelant, qui lève au lieu d'entrer au journal sous la cible des emplois.
    with pytest.raises(ValueError):
        journal.journaliser_emploi(_conn(db_path), "creation", aid, decor["voisine"])

    # La charge porte le NOM de la collection à côté de son identifiant, qui se
    # réattribue : sans lui, l'acte désignerait un jour une autre étude.
    assert _actes(db_path, doc)[1:] == [
        ("collection_album", "lien", "alice", doc, None,
         {"album_id": aid, "collection_id": decor["emotions"], "collection": "Émotions"}),
        ("collection_album", "lien", "alice", doc, None,
         {"album_id": aid, "collection_id": decor["voisine"], "collection": "Voisine"}),
        ("collection_album", "delien", "alice", doc,
         {"album_id": aid, "collection_id": decor["emotions"], "collection": "Émotions"},
         None),
        ("collection_album", "delien", "alice", doc,
         {"album_id": aid, "collection_id": decor["voisine"], "collection": "Voisine"},
         None)]


def test_supprimer_une_collection_ecrit_le_retrait_de_chacun_de_ses_albums(client, db_path,
                                                                           decor):
    """La cascade défait les liens sans rien dire : chacun est un emploi qui cesse, et
    s'écrit comme si on avait retiré l'album à la main. Et RIEN pour un album qui n'était
    pas de la collection : « Ailleurs » n'a jamais été rangé dans Voisine, et le journal
    ne lui invente pas un retrait."""
    albums = [_creer(client, t, decor["emotions"]) for t in ("Un", "Deux")]
    ailleurs = _creer(client, "Ailleurs", decor["emotions"])
    for aid in albums:
        assert client.put(f"/api/albums/{aid}/collections/{decor['voisine']}",
                          headers=ALICE).status_code == 201
    assert client.delete(f"/api/collections/{decor['voisine']}",
                         headers=ALICE).status_code == 204
    docs = [_album_ligne(db_path, aid)["document_id"] for aid in albums]
    # Tous les retraits écrits au nom de Voisine, quel que soit le document : deux, pas un
    # de plus. (Le décor en a écrit un autre, celui de son album détruit, ailleurs.)
    assert [a for a in _evenements(db_path, "collection_album")
            if a[1] == "delien" and a[4]["collection_id"] == decor["voisine"]] == [
        ("collection_album", "delien", "alice", doc,
         {"album_id": aid, "collection_id": decor["voisine"], "collection": "Voisine"}, None)
        for aid, doc in zip(albums, docs)]
    assert _actes(db_path, _album_ligne(db_path, ailleurs)["document_id"], "delien") == []


def test_detruire_un_album_emporte_son_document_et_l_ecrit(client, db_path, decor,
                                                           png_bytes):
    """Un document n'a qu'une copie dans cette tranche : il part avec elle, et le journal
    est tout ce qui reste de lui. Détruire met aussi fin à chacun de ses emplois — la
    cascade défait les liens sans rien dire, et un rangement sans fin laisserait croire le
    document encore employé. Un refus de détruire, lui, ne retire ni n'écrit rien."""
    aid = _creer(client, "Importé par erreur", decor["emotions"])
    doc = _album_ligne(db_path, aid)["document_id"]
    client.post(f"/api/albums/{aid}/import", headers=ALICE,
                files={"file": ("p.png", png_bytes, "image/png")})
    client.put(f"/api/albums/{aid}/collections/{decor['voisine']}", headers=ALICE)
    # Une TROISIÈME collection porte un autre album : sans elle, « les collections de cet
    # album » et « toutes les collections qui ont un album » se confondent, et un retrait
    # écrit au nom d'une étude où l'album n'a jamais été passerait (mutant survivant).
    _creer(client, "D'une autre étude", headers=ADMIN)

    # bob n'écrit que dans l'une des deux collections : refusé, comme avant ce commit.
    assert client.delete(f"/api/albums/{aid}", headers=BOB).status_code == 403
    assert _sql(db_path, "SELECT 1 FROM document WHERE id = ?", (doc,)) != []
    assert _actes(db_path, doc, "suppression") == [] and _actes(db_path, doc, "delien") == []

    assert client.delete(f"/api/albums/{aid}", headers=ALICE).status_code == 204
    assert _sql(db_path, "SELECT 1 FROM document WHERE id = ?", (doc,)) == []
    # Les deux retraits d'abord, dans l'ordre des collections, puis la destruction — et
    # pas un retrait de plus : l'album n'a jamais été de la collection de repli du décor.
    assert [a for a in _actes(db_path, doc) if a[1] in ("delien", "suppression")] == [
        ("collection_album", "delien", "alice", doc,
         {"album_id": aid, "collection_id": decor["emotions"], "collection": "Émotions"},
         None),
        ("collection_album", "delien", "alice", doc,
         {"album_id": aid, "collection_id": decor["voisine"], "collection": "Voisine"},
         None),
        ("document", "suppression", "alice", doc,
         {"album_id": aid, "titre": "Importé par erreur", "planches": 1}, None)]


def test_detruire_un_album_sans_document_s_ecrit_aussi(client, db_path):
    """Un album posé par `INSERT` n'a pas de document. Y importer et le ranger s'écrivent
    déjà sous une cible vide ; le détruire aussi — la fin de son emploi, puis la
    destruction, l'album restant lisible dans la charge. Sans quoi le journal garderait
    le début d'une histoire dont il tairait la fin."""
    cid = client.post("/api/collections", json={"nom": "Étude"}).json()["id"]
    _sql(db_path, "INSERT INTO albums (id, titre) VALUES (90, 'Posé à la main')")
    _sql(db_path, "INSERT INTO collection_album (collection_id, album_id) VALUES (?, 90)",
         (cid,))
    assert client.delete("/api/albums/90").status_code == 204
    assert _evenements(db_path, "document", "collection_album") == [
        ("collection_album", "delien", None, None,
         {"album_id": 90, "collection_id": cid, "collection": "Étude"}, None),
        ("document", "suppression", None, None,
         {"album_id": 90, "titre": "Posé à la main", "planches": 0}, None)]


def test_un_document_ne_part_qu_avec_sa_derniere_copie(client, db_path):
    """Deux copies du même document n'existent pas encore, mais la condition est écrite
    là où elle se gardera : détruire l'une ne doit pas emporter l'identité de l'autre."""
    un = _creer(client, "Une copie", headers={})
    deux = _creer(client, "Sa sœur", headers={})
    doc = _album_ligne(db_path, un)["document_id"]
    orphelin = _album_ligne(db_path, deux)["document_id"]
    _sql(db_path, "UPDATE albums SET document_id = ? WHERE id = ?", (doc, deux))
    _sql(db_path, "DELETE FROM document WHERE id = ?", (orphelin,))

    assert client.delete(f"/api/albums/{un}").status_code == 204
    assert _sql(db_path, "SELECT 1 FROM document WHERE id = ?", (doc,)) != []
    # La copie détruite cesse d'être employée — cela s'écrit ; le document, lui, n'est
    # pas détruit, et aucune `suppression` ne le prétend.
    assert [(a[1], a[4]["album_id"]) for a in _actes(db_path, doc, "delien")] \
        == [("delien", un)]
    assert [a for a in _evenements(db_path, "document") if a[1] == "suppression"] == []
    assert client.delete(f"/api/albums/{deux}").status_code == 204
    assert _sql(db_path, "SELECT 1 FROM document") == []
    assert [(a[1], a[3]) for a in _evenements(db_path, "document")
            if a[1] == "suppression"] == [("suppression", doc)]


def test_importer_depuis_sharedocs_ecrit_ses_scans_sous_le_document(client, db_path, decor,
                                                                     monkeypatch):
    """L'import ShareDocs ne crée plus d'album (COL-3, Hugo, 2026-10-15) : un album naît
    dans la Bibliothèque, avec sa collection, et son origine s'y écrit. L'import y AJOUTE
    des scans, écrits sous le document à la suite de sa naissance — jamais une seconde
    naissance."""
    monkeypatch.setattr(sd, "download", lambda path, *, principal, compte=None: make_png())
    aid = _creer(client, "Astérix", decor["emotions"])
    doc = _album_ligne(db_path, aid)["document_id"]
    r = client.post("/api/sharedocs/importer", headers=ALICE, json={
        "chemins": ["BD/p1.png", "BD/p2.png", "BD/notes.txt"], "album_id": aid})
    assert r.status_code == 200 and len(r.json()["importes"]) == 2, r.text
    actes = _actes(db_path, doc)
    assert [(a[0], a[1], a[2]) for a in actes] == [
        ("document", "creation", "alice"), ("collection_album", "lien", "alice"),
        ("document", "modification", "alice"), ("document", "modification", "alice")]
    assert [a[5]["planche"]["numero"] for a in actes[2:]] == [1, 2]


def test_l_import_sharedocs_ne_fait_naitre_aucun_album(client, db_path, decor, monkeypatch):
    """`nouvel_album` est refusé, et rien ne s'écrit : ni album, ni document, ni trace."""
    monkeypatch.setattr(sd, "download", lambda path, *, principal, compte=None: make_png())
    avant = (_sql(db_path, "SELECT id FROM albums"), _sql(db_path, "SELECT id FROM document"),
             _evenements(db_path, "document", "collection_album"))
    r = client.post("/api/sharedocs/importer", headers=ADMIN,
                    json={"chemins": ["a.png"], "nouvel_album": "Rien"})
    assert r.status_code == 422, r.text
    assert (_sql(db_path, "SELECT id FROM albums"), _sql(db_path, "SELECT id FROM document"),
            _evenements(db_path, "document", "collection_album")) == avant


def test_l_outil_ecrit_les_memes_emplois_que_la_route(client, db_path, decor):
    """Deux portes vers les mêmes liens, un seul journal : `creer --albums`, `ajouter`,
    `retirer` et `supprimer` écrivent ce que la Bibliothèque écrit. Un shell n'a pas
    d'identité, donc l'agent est vide ; un refus n'écrit rien."""
    ici = client.post("/api/collections", json={"nom": "Du repli"},
                      headers=ADMIN).json()["id"]
    un, deux, trois = (_creer(client, t, ici, headers=ADMIN)
                       for t in ("Un", "Deux", "Trois"))
    docs = {aid: _album_ligne(db_path, aid)["document_id"] for aid in (un, deux)}
    deja = len(_evenements(db_path, "collection_album"))

    code, sortie, err = _outil(db_path, "gerer_collections.py", "creer", "--nom", "Par l'outil",
                               "--albums", f"{un},{deux}")
    assert code == 0, err
    cid = int(sortie.strip())
    assert _outil(db_path, "gerer_collections.py", "ajouter", str(cid),
                  "--albums", str(un))[0] == 0                     # déjà rangé : rien
    # « Trois » EXISTE et n'a jamais été de cette collection ; 9999 n'existe pas. Aucun
    # des deux n'en est retiré, et le journal ne l'invente pour aucun.
    assert _outil(db_path, "gerer_collections.py", "retirer", str(cid),
                  "--albums", f"{un},{trois},9999")[0] == 0
    # Un refus n'écrit rien : supprimer « ici », dernière collection de « Trois ».
    assert _outil(db_path, "gerer_collections.py", "supprimer", str(ici))[0] != 0
    assert _outil(db_path, "gerer_collections.py", "supprimer", str(cid))[0] == 0

    assert _evenements(db_path, "collection_album")[deja:] == [
        ("collection_album", "lien", None, docs[un], None,
         {"album_id": un, "collection_id": cid, "collection": "Par l'outil"}),
        ("collection_album", "lien", None, docs[deux], None,
         {"album_id": deux, "collection_id": cid, "collection": "Par l'outil"}),
        ("collection_album", "delien", None, docs[un],
         {"album_id": un, "collection_id": cid, "collection": "Par l'outil"}, None),
        ("collection_album", "delien", None, docs[deux],
         {"album_id": deux, "collection_id": cid, "collection": "Par l'outil"}, None)]


def test_les_chemins_d_ecriture_posent_tous_le_document(client, db_path, monkeypatch):
    """« Tout album appartient à l'instance », en formulation exécutable : la création et
    la création dans une collection nommée posent toutes deux le document et le projet de
    la copie — l'import ShareDocs n'en crée plus (COL-3, 2026-10-15). Et la formulation
    MORD : un album posé par `INSERT` s'y lit."""
    _creer(client, "Sans collection", headers={})
    cid = client.post("/api/collections", json={"nom": "Étude"}).json()["id"]
    _creer(client, "Dans une collection", cid, headers={})
    assert len(_sql(db_path, "SELECT 1 FROM albums")) == 2
    assert database.albums_sans_document(_conn(db_path)) == []
    assert database.albums_hors_de_leur_projet(_conn(db_path)) == []
    assert {a["projet_id"] for a in _sql(db_path, "SELECT projet_id FROM albums")} \
        == {_repli(db_path)}

    _sql(db_path, "INSERT INTO albums (id, titre) VALUES (80, 'Posé à la main')")
    assert database.albums_sans_document(_conn(db_path)) == [80]


# --------------------------------------------------------------------------- #
# La règle de lecture — de quel projet est une copie
# --------------------------------------------------------------------------- #
def test_le_projet_d_une_copie_se_lit_sur_elle_puis_dans_ses_collections(client, db_path,
                                                                        decor):
    """Table de vérité de `sql_projet_d_album`. Le projet ÉCRIT sur la copie d'abord —
    c'est lui qui tient quand elle n'est plus rangée nulle part. À défaut, celui de ses
    collections. Et NULL quand il n'y a ni l'un ni l'autre : la copie n'a jamais eu de
    projet, ce qui ne se lit PAS « le projet de repli »."""
    _sql(db_path, "INSERT INTO collection (id, nom) VALUES (70, 'Sans projet nommé')")
    for aid, titre, projet in ((81, "Écrit, rangé nulle part", decor["projet"]),
                               (82, "Non écrit, rangé au Séminaire", None),
                               (83, "Non écrit, collection sans projet", None),
                               (84, "Ni l'un ni l'autre", None),
                               (85, "Écrit ici, rangé ailleurs", decor["repli"]),
                               (86, "Non écrit, rangé dans deux projets", None)):
        _sql(db_path, "INSERT INTO albums (id, titre, projet_id) VALUES (?, ?, ?)",
             (aid, titre, projet))
    assert decor["emotions"] < 70, "le décor ne distingue plus la plus petite collection"
    for cid, aid in ((decor["emotions"], 82), (70, 83), (decor["emotions"], 85),
                     (70, 86), (decor["emotions"], 86)):
        _sql(db_path, "INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
             (cid, aid))

    conn = _conn(db_path)
    # 86 : deux projets à lire, et la règle en choisit un — celui de la collection de plus
    # petit id (Émotions, donc le Séminaire). C'est un choix, tenu ici pour qu'il ne
    # change pas en silence : la migration écrit ce qu'il rend.
    assert {aid: database.projet_d_album(conn, aid)
            for aid in (81, 82, 83, 84, 85, 86, 9999)} \
        == {81: decor["projet"], 82: decor["projet"], 83: decor["repli"], 84: None,
            85: decor["repli"], 86: decor["projet"], 9999: None}
    # La lecture en liste rend la même chose que la lecture à l'unité.
    assert {r[0]: r[1] for r in conn.execute(
        f"SELECT x.id, {database.sql_projet_d_album('x')} FROM albums x WHERE x.id > 80")} \
        == {81: decor["projet"], 82: decor["projet"], 83: decor["repli"], 84: None,
            85: decor["repli"], 86: decor["projet"]}
    # Et l'écart entre les deux lectures se DIT : seul l'album 85 porte un projet écrit
    # que ses collections démentent.
    assert database.albums_hors_de_leur_projet(conn) == [85]


def test_un_projet_qu_un_album_designe_encore_ne_se_supprime_pas(client, db_path, decor):
    """Le projet d'une copie est écrit sur elle, par une clé étrangère sans action. Un
    projet VIDE de collections mais qu'un album désigne encore répondait une erreur brute
    de la base. C'est un refus qui se NOMME, comme les deux autres ; il ne vient qu'après
    la question du droit, et ne dit donc rien à qui ne décide pas des projets. L'état se
    fabrique ici par une base retouchée ; depuis le fonds (tranche 2), c'est celui d'une
    copie gardée — `tests/test_fonds.py` le produit par les routes."""
    designe = client.post("/api/projets", json={"nom": "Désigné"}, headers=ADMIN).json()["id"]
    assert client.put(f"/api/projets/{designe}/membres", headers=ADMIN,
                      json={"genre": "utilisateur", "principal": "alice",
                            "role": "responsable"}).status_code == 200
    aid = _creer(client, "Copie retouchée", decor["emotions"])
    _sql(db_path, "UPDATE albums SET projet_id = ? WHERE id = ?", (designe, aid))
    assert database.albums_hors_de_leur_projet(_conn(db_path)) == [aid]

    # La responsable ne décide pas des projets : son refus est celui d'avant, sans compte.
    r = client.delete(f"/api/projets/{designe}", headers=ALICE)
    assert r.status_code == 403 and "album" not in r.json()["detail"]
    r = client.delete(f"/api/projets/{designe}", headers=ADMIN)
    assert r.status_code == 409, r.text
    assert "1 album(s) désignent ce projet en étant rangés dans la collection d'un "         "autre" in r.json()["detail"]
    assert _sql(db_path, "SELECT nom FROM projet WHERE id = ?", (designe,)) \
        == [{"nom": "Désigné"}]
    assert _sql(db_path, "SELECT 1 FROM evenement WHERE cible_table = 'projet' "
                         "AND type = 'suppression'") == []

    # L'écart réparé, le projet part.
    _sql(db_path, "UPDATE albums SET projet_id = ? WHERE id = ?", (decor["projet"], aid))
    assert client.delete(f"/api/projets/{designe}", headers=ADMIN).status_code == 204


# --------------------------------------------------------------------------- #
# Ce que le commit ne change pas
# --------------------------------------------------------------------------- #
def test_importer_ne_compte_ni_comme_du_travail_laisse_ni_comme_un_rang(client, db_path,
                                                                        decor, png_bytes):
    """Ces gestes n'étaient pas écrits la veille. Les écrire ne doit décaler ni le verdict
    de départ d'un compte, ni le pseudonyme de ceux qui annotent : alice a importé, rangé
    et retiré sans rien annoter ; bob pose la première annotation de l'instance."""
    import _commun

    rangs_avant = _commun.pseudonymes(_conn(db_path))
    actes_avant = comptes.traces(_conn(db_path))[0]
    aid = _creer(client, "Le Lotus bleu", decor["emotions"])
    pl = client.post(f"/api/albums/{aid}/import", headers=ALICE,
                     files={"file": ("p.png", png_bytes, "image/png")}).json()
    client.put(f"/api/albums/{aid}/collections/{decor['voisine']}", headers=ALICE)
    client.delete(f"/api/albums/{aid}/collections/{decor['voisine']}", headers=ALICE)
    doc = _album_ligne(db_path, aid)["document_id"]
    assert [(a[1], a[2]) for a in _actes(db_path, doc)] == [
        ("creation", "alice"), ("lien", "alice"), ("modification", "alice"),
        ("lien", "alice"), ("delien", "alice")], "le semis ne pose pas ce qu'on cherche"

    # Quatre gestes, cinq actes au journal — et ni un rang, ni un acte laissé de plus.
    assert _commun.pseudonymes(_conn(db_path)) == rangs_avant
    assert comptes.traces(_conn(db_path))[0] == actes_avant
    assert "alice" not in rangs_avant and "alice" not in actes_avant
    client.get("/api/moi", headers=ALICE)
    vue = client.get("/api/comptes-et-groupes", headers=ADMIN).json()
    fiche = next(c for c in vue["comptes"] if c["login"] == "alice")
    assert fiche["actes"] == 0 and fiche["verdict"] == "laisse des accès"

    # Le contrôle mord : le premier acte d'ANNOTATION, lui, donne un rang et se compte.
    r = client.post(f"/api/planches/{pl['id']}/regions", headers=BOB,
                    json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9})
    assert r.status_code == 201, r.text
    assert set(_commun.pseudonymes(_conn(db_path))) == set(rangs_avant) | {"bob"}
    assert comptes.traces(_conn(db_path))[0] == {**actes_avant, "bob": 1}


def test_une_cible_sans_rang_ne_peut_pas_etre_publiee():
    """La condition de `CIBLES_SANS_RANG`. Qui n'aurait d'actes que sous une de ces cibles
    n'a aucun pseudonyme ; si elle partait au dépôt, il y sortirait SOUS SON LOGIN —
    `pseudonymes(...).get(nom, nom)` laisse passer ce qu'il ne connaît pas."""
    import _commun

    assert _commun.CIBLES_SANS_RANG == {"document", "collection_album", "demande",
                                        "region_attribut", "tags", "grille"}
    assert _commun.CIBLES_SANS_RANG <= set(_commun.CIBLES_RETENUES)
    assert not _commun.CIBLES_SANS_RANG & _commun.CIBLES_CORPUS


def test_ctrl_z_ne_defait_aucun_acte_du_fonds(client, db_path, png_bytes):
    """Défaire un import ou un rangement par un raccourci clavier serait une surprise,
    comme pour un accès. Joué en mono-poste, où l'annulation ne filtre par aucun agent :
    s'il y avait quoi que ce soit d'annulable, elle le trouverait."""
    cid = client.post("/api/collections", json={"nom": "Étude"}).json()["id"]
    aid = _creer(client, "Le Lotus bleu", headers={})
    pl = client.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", png_bytes, "image/png")}).json()
    client.put(f"/api/albums/{aid}/collections/{cid}")
    client.delete(f"/api/planches/{pl['id']}")
    assert len(_evenements(db_path, "document", "collection_album")) == 5

    assert client.get("/api/undo/prochain").json() is None
    assert client.post("/api/undo").status_code == 404


def test_rien_du_fonds_ne_sort_d_aucun_artefact(client, db_path, tmp_path, png_bytes,
                                                derriere_proxy):
    """Ni l'identifiant du document, ni qui l'a importé, ni les actes qui l'écrivent ne
    partent par les exports d'album, la voie du dépôt ou les outils. Publier la date et
    l'auteur d'un import serait une décision à part ; d'ici là, rien. Le semis est son
    propre témoin : ce qu'on cherche par son absence est d'abord vu là où il doit être."""
    import _commun

    # DEUX comptes, et c'est le point. `zzpur7` n'a fait qu'IMPORTER et RANGER : aucun de
    # ses actes ne lui donne de rang, donc aucun pseudonyme — si un seul de ces actes
    # partait, son login sortirait EN CLAIR. `zzannot7` annote : elle a un pseudonyme, et
    # c'est par lui seul qu'elle sort. Avec une sentinelle unique qui annote aussi, le
    # contrôle ne mesurait pas l'importateur pur (relecture croisée).
    qui = {"Remote-User": "zzpur7", "Remote-Groups": "bd-admins"}
    annote = {"Remote-User": "zzannot7", "Remote-Groups": "bd-admins"}
    _decaler_les_identifiants(client, qui)
    cid = client.post("/api/collections", json={"nom": "Étude déposée"},
                      headers=annote).json()["id"]
    autre = client.post("/api/collections", json={"nom": "Seconde étude"},
                        headers=annote).json()["id"]
    client.patch(f"/api/collections/{cid}", json={"statut_diffusion": "public"},
                 headers=annote)
    aid = _creer(client, "Album", cid, headers=qui)
    pl = client.post(f"/api/albums/{aid}/import", headers=qui,
                     files={"file": ("p.png", png_bytes, "image/png")}).json()
    assert client.put(f"/api/albums/{aid}/collections/{autre}", headers=qui).status_code == 201
    assert client.delete(f"/api/albums/{aid}/collections/{autre}",
                         headers=qui).status_code == 204
    client.post(f"/api/planches/{pl['id']}/regions", headers=annote,
                json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9})

    assert _sql(db_path, "SELECT importe_par FROM document") == [{"importe_par": "zzpur7"}]
    assert {(a[0], a[1], a[2]) for a in _evenements(db_path, "document", "collection_album")
            if a[2] == "zzpur7"} >= {
        ("document", "creation", "zzpur7"), ("document", "modification", "zzpur7"),
        ("collection_album", "lien", "zzpur7"), ("collection_album", "delien", "zzpur7")}, \
        "le semis ne pose pas ce qu'on cherche"
    rangs = _commun.pseudonymes(_conn(db_path))
    assert "zzpur7" not in rangs and "zzannot7" in rangs, (
        "le décor ne sépare plus l'importateur pur de celle qui annote")
    qui = annote                    # les sorties se demandent sous un compte qui exporte

    sorties = {}
    for chemin in (f"/api/export/json?album_id={aid}", f"/api/export/csv?album_id={aid}",
                   f"/api/export/tei?album_id={aid}",
                   f"/api/collections/{cid}/depot/description",
                   f"/api/collections/{cid}/depot/description?format=csv",
                   f"/api/collections/{cid}/depot/metadonnees",
                   f"/api/collections/{cid}/depot/metadonnees?format=zip",
                   f"/api/collections/{cid}/depot/iiif?base_url=https://images.example.org"):
        r = client.get(chemin, headers=qui)
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
        for interdit in ("zzpur7", "zzannot7", "document_id", "importe_par", "importe_le",
                         "projet_origine", "Seconde étude"):
            assert interdit not in texte, f"{surface} laisse sortir « {interdit} »"
