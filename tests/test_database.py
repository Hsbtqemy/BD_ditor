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


def test_connect_rollback_sur_exception(data_dir, db_path):
    """Le context manager connect() doit rollback si le bloc lève."""
    import pytest
    aid = None
    with pytest.raises(RuntimeError):
        with database.connect() as conn:
            aid = conn.execute("INSERT INTO albums(titre) VALUES('Annulé')").lastrowid
            raise RuntimeError("boom")
    # L'insertion a été annulée.
    assert direct_query(db_path, "SELECT COUNT(*) AS n FROM albums")[0]["n"] == 0


def test_reindex_region_inexistante_ne_fait_rien(data_dir):
    """reindex_region sur une région absente ne crée pas de ligne FTS."""
    conn = database.get_connection()
    try:
        database.reindex_region(conn, 999999)
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM recherche").fetchone()[0] == 0
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


# ----------- Numérotation éditoriale (récit / paratexte) ----------- #
def test_role_planche_defaut_recit(data_dir):
    """La colonne planches.role existe et vaut 'recit' par défaut (migration v10)."""
    conn = database.get_connection()
    try:
        aid = conn.execute("INSERT INTO albums(titre) VALUES('A')").lastrowid
        pid = conn.execute(
            "INSERT INTO planches(album_id, numero, chemin_web) "
            "VALUES(?,1,'x.jpg')", (aid,)).lastrowid
        conn.commit()
        assert conn.execute(
            "SELECT role FROM planches WHERE id=?", (pid,)).fetchone()[0] == "recit"
    finally:
        conn.close()


def test_numeros_editoriaux_derive_du_recit(data_dir):
    """Numéro éditorial = rang parmi les planches 'recit', trié par numero. Paratexte
    → None ; robuste à une page intercalée et aux trous de numero."""
    conn = database.get_connection()
    try:
        aid = conn.execute("INSERT INTO albums(titre) VALUES('A')").lastrowid

        def add(numero, role):
            return conn.execute(
                "INSERT INTO planches(album_id, numero, chemin_web, role) "
                "VALUES(?,?,?,?)", (aid, numero, f"{numero}.jpg", role)).lastrowid

        couv = add(1, "paratexte")    # couverture
        p1 = add(2, "recit")
        pub = add(3, "paratexte")     # pub intercalée AU MILIEU du récit
        p2 = add(5, "recit")          # trou volontaire dans numero (ancienne pl.4 supprimée)
        conn.commit()

        nums = database.numeros_editoriaux(conn, aid)
        assert nums[couv] is None and nums[pub] is None
        assert nums[p1] == 1
        assert nums[p2] == 2          # malgré la pub intercalée et le trou de numero
    finally:
        conn.close()


def test_citations_regions_case_bulle_paratexte(data_dir):
    """Citation dérivée : pl·c (case), pl·c·b (bulle), hors-case, Paratexte, et le
    repère global idx/total calculé sur le récit seul."""
    conn = database.get_connection()
    try:
        aid = conn.execute("INSERT INTO albums(titre) VALUES('A')").lastrowid

        def planche(numero, role):
            return conn.execute(
                "INSERT INTO planches(album_id, numero, chemin_web, role) "
                "VALUES(?,?,?,?)", (aid, numero, f"{numero}.jpg", role)).lastrowid

        def region(pid, type, ordre, parent=None):
            return conn.execute(
                "INSERT INTO regions(planche_id, parent_id, type, ordre) "
                "VALUES(?,?,?,?)", (pid, parent, type, ordre)).lastrowid

        couv = planche(1, "paratexte")
        p1 = planche(2, "recit")
        p2 = planche(3, "recit")
        c_couv = region(couv, "case", 1)         # case sur la couverture (paratexte)
        c_a = region(p1, "case", 1)
        c_b = region(p1, "case", 2)
        b1 = region(p1, "bulle", 1, parent=c_b)  # bulle dans la 2e case
        orph = region(p1, "bulle", 3)            # bulle hors case (parent NULL)
        c_p2 = region(p2, "case", 1)
        conn.commit()

        cit = database.citations_regions(
            conn, [c_couv, c_a, c_b, b1, orph, c_p2])

        assert cit[c_couv] == {"planche": None, "texte": "Paratexte"}
        assert cit[c_a]["texte"] == "pl.1 · c1"
        assert (cit[c_a]["global"], cit[c_a]["total"]) == (1, 3)
        assert cit[c_b]["texte"] == "pl.1 · c2" and cit[c_b]["global"] == 2
        assert cit[b1]["texte"] == "pl.1 · c2 · b1"
        assert cit[orph]["texte"] == "pl.1 · hors-case"
        assert cit[c_p2]["texte"] == "pl.2 · c1"
        assert (cit[c_p2]["global"], cit[c_p2]["total"]) == (3, 3)
    finally:
        conn.close()


def test_citations_regions_multi_albums(data_dir):
    """Chemin batch multi-albums (recherche transverse) : numérotation, index global
    et total sont PROPRES à chaque album, sans contamination de l'un à l'autre."""
    conn = database.get_connection()
    try:
        def album(titre):
            return conn.execute("INSERT INTO albums(titre) VALUES(?)", (titre,)).lastrowid

        def case(aid, numero, ordre):
            pid = conn.execute(
                "INSERT INTO planches(album_id, numero, chemin_web, role) "
                "VALUES(?,?,?, 'recit')", (aid, numero, f"{aid}-{numero}.jpg")).lastrowid
            return conn.execute(
                "INSERT INTO regions(planche_id, type, ordre) VALUES(?, 'case', ?)",
                (pid, ordre)).lastrowid

        a1, a2 = album("A1"), album("A2")
        a1c1 = case(a1, 1, 1)
        a1c2 = case(a1, 2, 1)          # 2e planche récit d'A1
        a2c1 = case(a2, 1, 1)          # album distinct
        conn.commit()

        cit = database.citations_regions(conn, [a1c1, a1c2, a2c1])
        # A1 : deux cases sur deux planches → total 2, index 1 puis 2.
        assert cit[a1c1]["texte"] == "pl.1 · c1"
        assert (cit[a1c1]["global"], cit[a1c1]["total"]) == (1, 2)
        assert (cit[a1c2]["texte"], cit[a1c2]["global"]) == ("pl.2 · c1", 2)
        # A2 : numérotation et total INDÉPENDANTS (repart à pl.1, total 1).
        assert cit[a2c1]["texte"] == "pl.1 · c1"
        assert (cit[a2c1]["global"], cit[a2c1]["total"]) == (1, 1)
    finally:
        conn.close()
