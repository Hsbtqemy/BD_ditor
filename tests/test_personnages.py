"""ANN-2 (lot mince) — schéma personnages / locuteur / attributs facettés.

Teste la STRUCTURE et les contraintes (cascade, canonicité des valeurs) ; l'API et
l'UI viennent dans les incréments suivants. Cf. docs/personnages-et-attribution.md §13.
"""
import sqlite3

import database
from conftest import direct_query


def test_schema_version_11(data_dir, db_path):
    assert database.SCHEMA_VERSION == 11
    assert direct_query(db_path, "PRAGMA user_version")[0]["user_version"] == 11


def test_tables_ann2_existent(data_dir):
    with database.connect() as conn:
        noms = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"personnages", "bulle_locuteur", "attribut_dimension",
            "attribut_valeur", "personnage_attribut", "region_attribut"} <= noms


def test_locuteur_cascade(region):
    """Supprimer un personnage détache la liaison (CASCADE) mais NE supprime PAS la région."""
    rid = region["id"]
    with database.connect() as conn:
        pid = conn.execute("INSERT INTO personnages (nom) VALUES ('Haddock')").lastrowid
        conn.execute("INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?)", (rid, pid))
    with database.connect() as conn:
        assert conn.execute("SELECT COUNT(*) n FROM bulle_locuteur").fetchone()["n"] == 1
        conn.execute("DELETE FROM personnages WHERE id = ?", (pid,))
    with database.connect() as conn:
        assert conn.execute("SELECT COUNT(*) n FROM bulle_locuteur").fetchone()["n"] == 0
        assert conn.execute("SELECT COUNT(*) n FROM regions WHERE id = ?", (rid,)).fetchone()["n"] == 1


def test_valeur_attribut_canonique(data_dir):
    """Une valeur est CANONIQUE par dimension : un doublon est rejeté (agrégabilité)."""
    with database.connect() as conn:
        d = conn.execute(
            "INSERT INTO attribut_dimension (cible, nom) VALUES ('personnage', 'origine')").lastrowid
        conn.execute("INSERT INTO attribut_valeur (dimension_id, valeur) VALUES (?, 'rural')", (d,))
    with database.connect() as conn:
        rejete = False
        try:
            conn.execute("INSERT INTO attribut_valeur (dimension_id, valeur) VALUES (?, 'rural')", (d,))
        except sqlite3.IntegrityError:
            rejete = True
        assert rejete


def test_affectation_attribut(region):
    """Affecter une valeur à un personnage ET à une région-case ; supprimer la valeur
    détache les affectations (CASCADE)."""
    with database.connect() as conn:
        d = conn.execute(
            "INSERT INTO attribut_dimension (cible, nom) VALUES ('case', 'formalite')").lastrowid
        v = conn.execute("INSERT INTO attribut_valeur (dimension_id, valeur) VALUES (?, 'soutenu')", (d,)).lastrowid
        p = conn.execute("INSERT INTO personnages (nom) VALUES ('X')").lastrowid
        conn.execute("INSERT INTO personnage_attribut (personnage_id, valeur_id) VALUES (?, ?)", (p, v))
        conn.execute("INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)", (region["id"], v))
    with database.connect() as conn:
        assert conn.execute("SELECT COUNT(*) n FROM personnage_attribut").fetchone()["n"] == 1
        assert conn.execute("SELECT COUNT(*) n FROM region_attribut").fetchone()["n"] == 1
        conn.execute("DELETE FROM attribut_valeur WHERE id = ?", (v,))
    with database.connect() as conn:
        assert conn.execute("SELECT COUNT(*) n FROM personnage_attribut").fetchone()["n"] == 0
        assert conn.execute("SELECT COUNT(*) n FROM region_attribut").fetchone()["n"] == 0
