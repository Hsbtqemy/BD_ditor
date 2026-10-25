"""ANN-7, tranche 1 — la migration v37, sur une VRAIE base v36.

La règle de Hugo (2026-10-16, `CLAUDE.md` § Schéma & migrations) : une migration se vérifie
sur une base de la version précédente qui a VÉCU, faite par le code de cette version
(`tools/fabriquer_base_de_version.py b9183c0 tests/bases/v36-b9183c0.sql` — `b9183c0`, la
tête de la copie d'intégration de la 3b de COL-3, est le dernier état de la v36). Elle porte
ce que portaient les précédentes, et ce que la v37 doit traverser : des régions des cinq
types, des textes à apostrophes et à tirets, une copie sœur amorcée au cran `annotations`,
un album retiré du projet, deux bacs à sable, une planche et une région détruites en haut de
leur table.

Ce que la v37 apporte (cadrage R1, tranché par Hugo le 2026-10-25) : seize tables NEUVES,
toutes vides, et une colonne, `regions.nom`, NULL pour tout l'existant. Et rien d'autre : les
lignes, les index d'avant, les vues, l'index plein texte, les compteurs, sont ceux d'avant.
Les gardes que le SCHÉMA porte — la planche sans action, la région en cascade, la
cardinalité `une`, un seul doute ouvert — se jouent ici, sur la base migrée.
"""
import json
import sqlite3
from pathlib import Path

import pytest

import database
import main

BASE_V36 = Path(__file__).resolve().parent / "bases" / "v36-b9183c0.sql"
# Écrites ICI À LA MAIN, et non lues dans `database.TABLES_DES_GRILLES` : le test qui tirerait
# son attendu de la constante qu'il éprouve en serait le miroir.
TABLES_V37 = {"grille", "grille_version", "grille_rubrique", "grille_entree",
              "grille_variante", "grille_liste", "grille_qualificatif", "grille_exemple",
              "projet_grille", "collection_grille_masquee", "releve", "releve_mot",
              "releve_qualificatif", "doute", "doute_message", "passe"}
LIGNES = ("albums", "planches", "regions", "annotations", "personnages", "projet",
          "projet_acces", "collection", "collection_acces", "collection_album", "document",
          "copie", "demande", "demande_document", "region_origine", "contribution",
          "tokens", "token_correction", "tags", "domaine", "attribut_dimension",
          "attribut_valeur", "evenement", "activite", "jeu_document", "geste_sur_copie",
          "region_attribut", "bulle_locuteur", "personnage_presence")


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


@pytest.fixture
def vraie_v36(tmp_path, monkeypatch):
    """`tests/bases/v36-b9183c0.sql`, chargée dans une base du test. Les dossiers d'images
    sont ceux du test, vides."""
    from pipeline import ingest
    db = tmp_path / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V36.read_text(encoding="utf-8"))
    c.close()
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    return db


def _etat(db, *, sans=frozenset()):
    tables = [r["name"] for r in _sql(
        db, "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE 'recherche_%' ORDER BY name") if r["name"] not in sans]
    lignes = {}
    for t in LIGNES:
        lignes[t] = sorted(json.dumps({k: v for k, v in r.items()
                                       if not (t == "regions" and k == "nom")},
                                      sort_keys=True, ensure_ascii=False)
                           for r in _sql(db, f'SELECT * FROM "{t}"'))
    return {
        "tables": tables,
        "comptes": {t: _sql(db, f'SELECT COUNT(*) AS n FROM "{t}"')[0]["n"] for t in tables},
        "lignes": lignes,
        "index": sorted(r["sql"] for r in _sql(
            db, "SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")
            if r["sql"] and not any(f" ON {t}(" in r["sql"] or f" ON {t} (" in r["sql"]
                                    or f"\n    ON {t}(" in r["sql"] for t in sans)),
        # `releves_effectifs` naît de la v37 (ANN-7) : une vue se recrée à chaque démarrage,
        # sans données, et la base d'avant ne la porte pas.
        "vues": sorted(r["name"] for r in _sql(
            db, "SELECT name FROM sqlite_master WHERE type = 'view'")
            if r["name"] != "releves_effectifs"),
        "recherche": sorted(r["region_id"] for r in _sql(
            db, "SELECT region_id FROM recherche WHERE recherche MATCH 'otage'")),
    }


def test_la_base_chargee_est_bien_une_v36_qui_a_vecu(vraie_v36):
    """Le décor d'abord : sans lui, les tests suivants passeraient sur une base vide."""
    assert _sql(vraie_v36, "PRAGMA user_version")[0]["user_version"] == 36
    tables = {r["name"] for r in _sql(vraie_v36, "SELECT name FROM sqlite_master "
                                                 "WHERE type = 'table'")}
    assert not (TABLES_V37 & tables)
    assert "nom" not in {c["name"] for c in _sql(vraie_v36, "PRAGMA table_info(regions)")}
    # Les cinq types d'aujourd'hui, des textes à apostrophes (droite et typographique) et à
    # tirets, une copie sœur amorcée au cran `annotations`, un retrait du projet.
    assert {r["type"] for r in _sql(vraie_v36, "SELECT DISTINCT type FROM regions")} == {
        "case", "bulle", "cartouche", "texte", "personnage"}
    textes = [r["ocr_texte"] for r in _sql(vraie_v36, "SELECT ocr_texte FROM regions "
                                                      "WHERE ocr_texte IS NOT NULL")]
    assert any("'" in t for t in textes) and any("’" in t for t in textes)
    assert any("-" in t for t in textes)
    assert _sql(vraie_v36, "SELECT COUNT(*) AS n FROM copie WHERE cran = 'annotations'")[0][
        "n"] == 1
    assert _sql(vraie_v36, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table = 'document' "
                           "AND json_extract(apres, '$.retire_du_projet') IS NOT NULL")[0][
        "n"] == 1
    # Une planche et une région détruites EN HAUT de leur table : le journal seul les nomme.
    assert _sql(vraie_v36, "SELECT MAX(id) AS m FROM planches")[0]["m"] < 24
    assert _sql(vraie_v36, "SELECT MAX(id) AS m FROM regions")[0]["m"] < 41
    assert _seq(vraie_v36)["planches"] >= 24 and _seq(vraie_v36)["regions"] >= 41


def test_une_vraie_base_v36_migre_sans_rien_perdre(vraie_v36):
    avant = _etat(vraie_v36)
    seq_avant = _seq(vraie_v36)
    database.init_db()
    assert _sql(vraie_v36, "PRAGMA user_version")[0]["user_version"] == database.SCHEMA_VERSION
    assert database.SCHEMA_VERSION == 37
    apres = _etat(vraie_v36, sans=TABLES_V37)
    tables = {r["name"] for r in _sql(vraie_v36, "SELECT name FROM sqlite_master "
                                                 "WHERE type = 'table'")}
    assert TABLES_V37 <= tables
    for t in TABLES_V37:
        assert _sql(vraie_v36, f'SELECT COUNT(*) AS n FROM "{t}"')[0]["n"] == 0, t
    assert apres == avant
    # La vue de l'état dérivé est née, et elle se lit sur la base migrée (vide).
    assert _sql(vraie_v36, "SELECT COUNT(*) AS n FROM releves_effectifs")[0]["n"] == 0
    # La colonne neuve : NULL partout.
    assert _sql(vraie_v36, "SELECT COUNT(*) AS n FROM regions WHERE nom IS NOT NULL")[0][
        "n"] == 0
    # Les compteurs d'avant ne bougent pas, et aucune table neuve n'en a encore.
    assert _seq(vraie_v36) == seq_avant
    assert _sql(vraie_v36, "PRAGMA foreign_key_check") == []
    assert _sql(vraie_v36, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"


def test_la_constante_des_tables_dit_ce_que_la_migration_cree(vraie_v36):
    database.init_db()
    assert set(database.TABLES_DES_GRILLES) == TABLES_V37


def test_la_base_migree_a_la_forme_d_une_base_neuve(vraie_v36, tmp_path):
    """Le schéma d'une base MIGRÉE et celui d'une base NEUVE ne doivent pas diverger : les
    tables neuves et leurs index, à l'octet ; `regions`, colonne par colonne (sur l'une la
    colonne naît de l'`ALTER`, sur l'autre du `CREATE`)."""
    database.init_db()
    neuve = tmp_path / "neuve.sqlite"
    c = sqlite3.connect(neuve)
    c.executescript(database.SCHEMA_SQL)
    c.close()

    def forme(db):
        objets = {r["name"]: r["sql"] for r in _sql(
            db, "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL")}
        neufs = {n: s for n, s in objets.items()
                 if n in TABLES_V37 or any(f" ON {t}" in s for t in TABLES_V37)}
        regions = [(c["name"], c["type"], c["notnull"], c["dflt_value"])
                   for c in _sql(db, "PRAGMA table_info(regions)")]
        return neufs, regions
    assert forme(vraie_v36) == forme(neuve)
    # Toutes portent AUTOINCREMENT, sauf les tables de liaison sans identifiant propre.
    sans_id = {"projet_grille", "collection_grille_masquee", "releve_mot",
               "releve_qualificatif"}
    for t in TABLES_V37 - sans_id:
        sql = _sql(vraie_v36, "SELECT sql FROM sqlite_master WHERE name = ?", (t,))[0]["sql"]
        assert "AUTOINCREMENT" in sql.upper(), t


def test_rejouee_la_migration_ne_change_rien(vraie_v36):
    database.init_db()
    etat = (_etat(vraie_v36), _seq(vraie_v36),
            _sql(vraie_v36, "SELECT type, name, sql FROM sqlite_master ORDER BY name"))
    _sql(vraie_v36, "PRAGMA user_version = 36")
    database.init_db()
    assert (_etat(vraie_v36), _seq(vraie_v36),
            _sql(vraie_v36, "SELECT type, name, sql FROM sqlite_master ORDER BY name")) == etat


def _poser_une_grille(c, projet_id=2):
    gid = c.execute("INSERT INTO grille (projet_id, nom) VALUES (?, 'Fictive')",
                    (projet_id,)).lastrowid
    vid = c.execute("INSERT INTO grille_version (grille_id, numero, etat, cible) "
                    "VALUES (?, 1, 'publiee', 'mots')", (gid,)).lastrowid
    return gid, vid


def test_sur_la_base_migree_le_schema_tient_ses_gardes(vraie_v36):
    """Les gardes que porte le SCHÉMA, jouées sur la vraie base migrée (R1) :
    - une planche qui porte un relevé de SURFACE ne se supprime pas (clé sans action, Q5) —
      bruyamment, pour qu'un chemin qui les oublierait échoue au lieu d'effacer ;
    - une région qui porte un relevé l'emporte en se supprimant (CASCADE) ;
    - deux relevés `une` de la même entrée sur la même cible : refusés par l'index ;
    - deux doutes OUVERTS sur un relevé : refusés par l'index."""
    database.init_db()
    c = sqlite3.connect(vraie_v36)
    c.execute("PRAGMA foreign_keys = ON")
    try:
        gid, vid = _poser_une_grille(c)
        planche, region = 21, 32                     # « Cinq types » : sa planche, sa bulle
        c.execute("INSERT INTO releve (planche_id, grille_id, version_id, entree_cle, une) "
                  "VALUES (?, ?, ?, 'registre', 1)", (planche, gid, vid))
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("DELETE FROM planches WHERE id = ?", (planche,))
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("INSERT INTO releve (planche_id, grille_id, version_id, entree_cle, une) "
                      "VALUES (?, ?, ?, 'registre', 1)", (planche, gid, vid))
        rid = c.execute("INSERT INTO releve (region_id, grille_id, version_id, entree_cle) "
                        "VALUES (?, ?, ?, 'elision')", (region, gid, vid)).lastrowid
        c.execute("INSERT INTO releve_mot (releve_id, position, rang, forme) "
                  "VALUES (?, 0, 0, 'J''')", (rid,))
        did = c.execute("INSERT INTO doute (releve_id, ouvert_par) VALUES (?, 'lea')",
                        (rid,)).lastrowid
        c.execute("INSERT INTO doute_message (doute_id, auteur, texte) VALUES (?, 'lea', "
                  "'Vraiment ?')", (did,))
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("INSERT INTO doute (releve_id, ouvert_par) VALUES (?, 'sam')", (rid,))
        c.execute("DELETE FROM regions WHERE id = ?", (region,))
        for t in ("releve", "releve_mot", "doute", "doute_message"):
            assert c.execute(f"SELECT COUNT(*) FROM {t} WHERE "
                             + ("region_id IS NOT NULL" if t == "releve" else "1")
                             ).fetchone()[0] == 0, t
        # Les identifiants des tables neuves partent au-dessus de rien : aucune n'a encore
        # nommé personne, la v37 n'a rien à amorcer.
        assert c.execute("SELECT seq FROM sqlite_sequence WHERE name = 'releve'").fetchone()[
            0] == rid
    finally:
        c.rollback()
        c.close()
