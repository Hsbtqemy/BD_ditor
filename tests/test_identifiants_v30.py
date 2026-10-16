"""COL-3, v30 — des identifiants qui ne reviennent jamais (Hugo, 2026-10-15).

`albums`, `planches`, `regions` et `personnages` portent `AUTOINCREMENT`. Sans lui, SQLite
rendait au suivant l'identifiant du dernier détruit, n'importe où : le journal, qui
survit à sa cible et la désigne par son identifiant, mêlait deux objets — la règle de
suppression lisait l'acte d'un ancien album comme un travail sur une région neuve, et
Ctrl+Z écrivait à travers le cloisonnement.

Une base d'avant la v30 est RECONSTRUITE (`database._reconstruire_avec_autoincrement`),
et son compteur amorcé au-dessus de tout identifiant que le journal a jamais nommé, par
sa cible ou dans ses charges. C'est une migration à sens unique : chaque source du
journal est jouée seule, pour qu'en oublier une fasse tomber un test ; puis ce que la
reconstruction ne doit pas toucher — lignes, index, vues, recherche, tokens, clés.
"""
import json
import re
import sqlite3

import pytest

import database

TABLES = ("albums", "planches", "regions", "personnages")


def _sql(db, q, p=()):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        r = [dict(x) for x in c.execute(q, p)]
        c.commit()
        return r
    finally:
        c.close()


def _seq(db):
    return {r["name"]: r["seq"] for r in _sql(db, "SELECT name, seq FROM sqlite_sequence")}


def _sans_autoincrement(db, version=29):
    """Défait la v30 sur ces quatre tables : la forme d'une base v29, identifiants rendus
    par SQLite. Reconstruction inverse, clés étrangères coupées (connexion brute), vues
    retirées puis remises — `ALTER TABLE … RENAME` refuse un schéma dont une vue désigne
    une table absente. `version=None` laisse `user_version` tel quel : la numérotation
    d'avant, sur une base qui ne sera pas migrée de nouveau (`test_undo_cloisonnement`)."""
    c = sqlite3.connect(db)
    for (vue,) in c.execute("SELECT name FROM sqlite_master WHERE type = 'view'").fetchall():
        c.execute(f'DROP VIEW "{vue}"')
    for t in TABLES:
        sql = c.execute("SELECT sql FROM sqlite_master WHERE name = ?", (t,)).fetchone()[0]
        index = [s for (s,) in c.execute("SELECT sql FROM sqlite_master WHERE type = 'index' "
                                         "AND tbl_name = ? AND sql IS NOT NULL", (t,))]
        vieux = re.sub(r"PRIMARY KEY AUTOINCREMENT", "PRIMARY KEY", sql, count=1)
        vieux = re.sub(r"^CREATE TABLE\s+(IF NOT EXISTS\s+)?\"?" + t + r"\"?\s*\(",
                       f"CREATE TABLE {t}__v29 (", vieux, count=1)
        cols = ", ".join(f'"{x[1]}"' for x in c.execute(f"PRAGMA table_info({t})"))
        c.execute(vieux)
        c.execute(f"INSERT INTO {t}__v29 ({cols}) SELECT {cols} FROM {t}")
        c.execute(f"DROP TABLE {t}")
        c.execute(f"ALTER TABLE {t}__v29 RENAME TO {t}")
        for s in index:
            c.execute(s)
        c.execute("DELETE FROM sqlite_sequence WHERE name = ?", (t,))
    c.executescript(database._VIEWS_SQL)
    if version is not None:
        c.execute(f"PRAGMA user_version = {version}")
    c.commit()
    c.close()
    for t in TABLES:
        assert "AUTOINCREMENT" not in _sql(db, "SELECT sql FROM sqlite_master WHERE name = ?",
                                           (t,))[0]["sql"].upper()


@pytest.fixture
def base_v29(tmp_path, monkeypatch):
    """Une base v29 qui a vécu un peu : un album, une planche, une case et sa bulle, un
    personnage, un token et sa ligne de recherche. Rien au journal : chaque test y pose
    ce qu'il mesure."""
    db = tmp_path / "v29.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db)
    database.init_db()
    _sans_autoincrement(db)
    for q in ("INSERT INTO albums (id, titre) VALUES (1, 'Un')",
              "INSERT INTO planches (id, album_id, numero, chemin_web) VALUES (1, 1, 1, 'x')",
              "INSERT INTO regions (id, planche_id, type) VALUES (1, 1, 'case')",
              "INSERT INTO regions (id, planche_id, parent_id, type, ocr_texte) "
              "VALUES (2, 1, 1, 'bulle', 'OTAGE')",
              "INSERT INTO personnages (id, nom) VALUES (1, 'Tintin')",
              "INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (2, 1)",
              "INSERT INTO tokens (region_id, ordre, texte, lemme) VALUES (2, 0, 'OTAGE', 'otage')",
              "INSERT INTO recherche (region_id, ocr_texte) VALUES (2, 'OTAGE')"):
        _sql(db, q)
    return db


def _acte(db, type_, cible_table, cible_id, avant=None, apres=None):
    _sql(db, "INSERT INTO evenement (type, agent, agent_type, cible_table, cible_id, avant, "
             "apres) VALUES (?, 'quelqu', 'humain', ?, ?, ?, ?)",
         (type_, cible_table, cible_id, None if avant is None else json.dumps(avant),
          None if apres is None else json.dumps(apres)))


# Chaque façon dont le journal nomme un identifiant, seule, et le nombre qu'elle nomme :
# au-dessus des survivants (1 ou 2), et distinct des autres pour qu'aucune ne passe grâce
# à sa voisine.
SOURCES = {
    "la cible d'un acte sur une région": (
        "regions", 50, ("suppression", "regions", 50, None, None)),
    "un enfant dans l'instantané d'une région supprimée": (
        "regions", 60, ("suppression", "regions", 2, {"id": 2, "enfants": [{"id": 60}]},
                        None)),
    "region_id dans une charge": (
        "regions", 70, ("modification", "token_correction", 1, None, {"region_id": 70})),
    "parent_id dans une charge": (
        "regions", 75, ("creation", "regions", 2, None, {"parent_id": 75})),
    "la cible d'un locuteur": (
        "regions", 80, ("lien", "bulle_locuteur", 80, None, {"personnage_id": 1})),
    "la cible d'une validation de planche": (
        "planches", 40, ("validation", "planches", 40, None, {"validee": True})),
    "planche_id dans l'instantané d'une région": (
        "planches", 45, ("suppression", "regions", 2, {"id": 2, "planche_id": 45}, None)),
    "l'objet planche d'un scan retiré": (
        "planches", 47, ("modification", "document", 1, {"album_id": 1,
                                                         "planche": {"id": 47, "numero": 3}},
                         None)),
    "album_id dans une charge": (
        "albums", 30, ("lien", "collection_album", 1, None, {"album_id": 30})),
    "personnage_id dans une charge": (
        "personnages", 20, ("delien", "bulle_locuteur", 2, {"personnage_id": 20}, None)),
}


@pytest.mark.parametrize("source", sorted(SOURCES))
def test_le_compteur_part_au_dessus_de_ce_que_le_journal_nomme(base_v29, source):
    table, haut, acte = SOURCES[source]
    _acte(base_v29, *acte)
    database.init_db()                                    # upgrade réel v29 → v30
    assert _sql(base_v29, "PRAGMA user_version")[0]["user_version"] == 30
    assert _seq(base_v29)[table] == haut, _seq(base_v29)
    # Et l'identifiant suivant le dépasse : rendu par SQLite, pas par le test.
    c = sqlite3.connect(base_v29)
    neuf = {"albums": "INSERT INTO albums (titre) VALUES ('n')",
            "planches": "INSERT INTO planches (album_id, numero, chemin_web) VALUES (1, 9, 'x')",
            "regions": "INSERT INTO regions (planche_id, type) VALUES (1, 'case')",
            "personnages": "INSERT INTO personnages (nom) VALUES ('n')"}[table]
    assert c.execute(neuf).lastrowid == haut + 1
    c.rollback()
    c.close()


def test_sans_journal_le_compteur_suit_les_survivants(base_v29):
    database.init_db()
    assert {t: _seq(base_v29)[t] for t in TABLES} == {"albums": 1, "planches": 1,
                                                       "regions": 2, "personnages": 1}


def test_une_charge_illisible_ne_fait_pas_echouer_la_migration(base_v29):
    """Une charge qui n'est pas du JSON est sautée : un acte mal écrit hier ne doit pas
    fermer l'instance au démarrage."""
    _sql(base_v29, "INSERT INTO evenement (type, agent_type, cible_table, cible_id, avant) "
                   "VALUES ('modification', 'humain', 'regions', 9, '{pas du json')")
    database.init_db()
    assert _seq(base_v29)["regions"] == 9


def test_la_reconstruction_ne_perd_rien(base_v29):
    avant_index = sorted(r["sql"] for r in _sql(
        base_v29, "SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL"))
    avant_vues = sorted(r["name"] for r in _sql(
        base_v29, "SELECT name FROM sqlite_master WHERE type = 'view'"))
    database.init_db()
    for t in TABLES:
        assert "AUTOINCREMENT" in _sql(base_v29, "SELECT sql FROM sqlite_master WHERE name = ?",
                                       (t,))[0]["sql"].upper()
    assert [r["id"] for r in _sql(base_v29, "SELECT id FROM regions ORDER BY id")] == [1, 2]
    assert _sql(base_v29, "SELECT parent_id FROM regions WHERE id = 2")[0]["parent_id"] == 1
    assert _sql(base_v29, "SELECT personnage_id FROM bulle_locuteur") == [{"personnage_id": 1}]
    assert len(_sql(base_v29, "SELECT 1 FROM tokens_effectifs")) == 1
    assert _sql(base_v29, "SELECT region_id FROM recherche WHERE recherche MATCH 'otage'") \
        == [{"region_id": 2}]
    assert _sql(base_v29, "PRAGMA foreign_key_check") == []
    assert _sql(base_v29, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"
    apres_index = sorted(r["sql"] for r in _sql(
        base_v29, "SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL"))
    assert apres_index == avant_index
    assert sorted(r["name"] for r in _sql(
        base_v29, "SELECT name FROM sqlite_master WHERE type = 'view'")) == avant_vues
    assert not _sql(base_v29, "SELECT name FROM sqlite_master WHERE name LIKE '%__v30'")
    assert not [n for n in _seq(base_v29) if "__v30" in n]
    # Les clés étrangères sont rendues actives : la cascade vit encore.
    with database.connect() as c:
        c.execute("DELETE FROM albums WHERE id = 1")
    assert _sql(base_v29, "SELECT COUNT(*) AS n FROM regions")[0]["n"] == 0


def test_rejouee_elle_ne_change_rien(base_v29):
    """Des tests ramènent `user_version` en arrière sur une base déjà migrée : la
    reconstruction ne repasse pas sur une table qui porte déjà AUTOINCREMENT, et le
    compteur ne bouge pas."""
    _acte(base_v29, "suppression", "regions", 50)
    database.init_db()
    schema = _sql(base_v29, "SELECT type, name, sql FROM sqlite_master ORDER BY name")
    seq = _seq(base_v29)
    _sql(base_v29, "PRAGMA user_version = 29")
    database.init_db()
    assert _sql(base_v29, "SELECT type, name, sql FROM sqlite_master ORDER BY name") == schema
    assert _seq(base_v29) == seq
    assert _sql(base_v29, "PRAGMA user_version")[0]["user_version"] == 30


def test_une_faute_de_cle_deja_la_ne_ferme_pas_l_instance(base_v29):
    """Une ligne orpheline écrite clés coupées, AVANT la migration, n'est pas une faute de
    la reconstruction : la base migre, et la faute reste ce qu'elle était."""
    _sql(base_v29, "INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (1, 999)")
    avant = _sql(base_v29, "PRAGMA foreign_key_check")
    assert avant
    database.init_db()
    assert _sql(base_v29, "PRAGMA user_version")[0]["user_version"] == 30
    assert _sql(base_v29, "PRAGMA foreign_key_check") == avant


def test_une_table_de_forme_inattendue_arrete_tout_avant_de_toucher(base_v29):
    """Une table sans `id INTEGER PRIMARY KEY` ne peut pas recevoir AUTOINCREMENT : la
    migration s'arrête en le disant, AVANT d'avoir reconstruit quoi que ce soit."""
    c = sqlite3.connect(base_v29)
    for (vue,) in c.execute("SELECT name FROM sqlite_master WHERE type = 'view'").fetchall():
        c.execute(f'DROP VIEW "{vue}"')
    c.execute("DROP TABLE personnages")
    c.execute("CREATE TABLE personnages (ident INTEGER PRIMARY KEY, nom TEXT)")
    c.commit()
    c.close()
    with pytest.raises(RuntimeError, match="personnages"):
        database.init_db()
    assert _sql(base_v29, "PRAGMA user_version")[0]["user_version"] == 29
    for t in ("albums", "planches", "regions"):
        assert "AUTOINCREMENT" not in _sql(
            base_v29, "SELECT sql FROM sqlite_master WHERE name = ?", (t,))[0]["sql"].upper()


# --------------------------------------------------------------------------- #
# Sur une base neuve, par les routes : un identifiant détruit ne revient pas
# --------------------------------------------------------------------------- #
def test_une_base_neuve_ne_rend_aucun_identifiant(client, png_bytes):
    album = client.post("/api/albums", json={"titre": "A"}).json()["id"]
    planche = client.post(f"/api/albums/{album}/import",
                          files={"file": ("p.png", png_bytes, "image/png")}).json()["id"]

    def region():
        r = client.post(f"/api/planches/{planche}/regions",
                        json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    r1 = region()
    assert client.delete(f"/api/regions/{r1}").status_code == 204
    assert region() > r1

    p2 = client.post(f"/api/albums/{album}/import",
                     files={"file": ("q.png", png_bytes, "image/png")}).json()["id"]
    assert client.delete(f"/api/planches/{p2}").status_code == 204
    assert client.post(f"/api/albums/{album}/import",
                       files={"file": ("r.png", png_bytes, "image/png")}).json()["id"] > p2

    a2 = client.post("/api/albums", json={"titre": "B"}).json()["id"]
    assert client.delete(f"/api/albums/{a2}").status_code == 204
    assert client.post("/api/albums", json={"titre": "C"}).json()["id"] > a2

    h = client.post("/api/personnages", json={"nom": "Haddock"}).json()["id"]
    assert client.delete(f"/api/personnages/{h}").status_code == 204
    assert client.post("/api/personnages", json={"nom": "Milou"}).json()["id"] > h
