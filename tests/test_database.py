"""Schéma SQLite, FTS5 et helpers d'indexation."""
import database
from conftest import direct_query


TABLES = {"albums", "planches", "regions", "tags", "annotations",
          "annotation_tags", "recherche"}


def test_schema_cree_toutes_les_tables(data_dir, db_path):
    rows = direct_query(
        db_path, "SELECT name FROM sqlite_master WHERE type IN ('table')")
    names = {r["name"] for r in rows}
    assert TABLES <= names, f"tables manquantes : {TABLES - names}"


def test_user_version_est_positionnee(data_dir, db_path):
    v = direct_query(db_path, "PRAGMA user_version")[0]["user_version"]
    assert v == database.SCHEMA_VERSION


def test_foreign_keys_actives(data_dir):
    conn = database.get_connection()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_reindex_et_unindex_region(data_dir):
    conn = database.get_connection()
    try:
        aid = conn.execute("INSERT INTO albums(titre) VALUES('A')").lastrowid
        pid = conn.execute(
            "INSERT INTO planches(album_id, numero, chemin_web) "
            "VALUES(?,1,'x.jpg')", (aid,)).lastrowid
        rid = conn.execute(
            "INSERT INTO regions(planche_id, type, ocr_texte) "
            "VALUES(?, 'bulle', 'BONJOUR')", (pid,)).lastrowid
        database.reindex_region(conn, rid)
        conn.commit()
        hits = conn.execute(
            "SELECT region_id FROM recherche WHERE recherche MATCH 'bonjour'"
        ).fetchall()
        assert [h[0] for h in hits] == [rid]

        database.unindex_region(conn, rid)
        conn.commit()
        assert conn.execute(
            "SELECT COUNT(*) FROM recherche WHERE region_id=?", (rid,)
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_reindex_vide_ne_cree_pas_de_ligne(data_dir):
    """Une région sans OCR/note/tags ne doit pas polluer l'index FTS."""
    conn = database.get_connection()
    try:
        aid = conn.execute("INSERT INTO albums(titre) VALUES('A')").lastrowid
        pid = conn.execute(
            "INSERT INTO planches(album_id, numero, chemin_web) "
            "VALUES(?,1,'x.jpg')", (aid,)).lastrowid
        rid = conn.execute(
            "INSERT INTO regions(planche_id, type) VALUES(?, 'case')", (pid,)
        ).lastrowid
        database.reindex_region(conn, rid)
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM recherche").fetchone()[0] == 0
    finally:
        conn.close()
