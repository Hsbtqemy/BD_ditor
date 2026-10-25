"""COL-3, tranche 3 — la migration v31, sur une VRAIE base v30.

La règle de Hugo (2026-10-16, `CLAUDE.md` § Schéma & migrations) : une migration se vérifie
sur une base de la version précédente qui a VÉCU, faite par le code de cette version
(`tools/fabriquer_base_de_version.py 5e7f56b tests/bases/v30-5e7f56b.sql`) — deux projets,
des membres et un groupe, la collection de repli, une copie gardée au fonds, un album
importé au fonds puis rendu, des demandes en attente, refusée et acceptée, une demande de
suppression de projet, et un projet supprimé dont l'identifiant n'est plus nommé que par le
journal et par une demande.

Ce que la v31 apporte, et ce que ces tests tiennent :

- `copie` : la provenance de chaque copie de travail, une ligne par album — `cran =
  'origine'`, `creee_par` = l'importateur du document (NULL pour l'existant d'avant la v30,
  qui reste « inconnu veut dire demander ») ;
- `document.projet_origine_nom` : le nom du projet d'origine, photographié à la migration ;
- `AUTOINCREMENT` sur `projet`, le compteur au-dessus de tout identifiant de projet que le
  journal, une demande ou un document ait jamais nommé (D8) ;
- des colonnes sans comportement encore (`demande.collection_id`, `collection_nom`,
  `demande_document.copie_id`), et celles de la collection de base (D10).
"""
import json
import re
import sqlite3
from pathlib import Path

import pytest

import database

BASE_V30 = Path(__file__).resolve().parent / "bases" / "v30-5e7f56b.sql"
# `region_origine` est celle de la v32 (COL-3, tranche 3b), que la migration traverse aussi.
# `jeu_document` est celle de la v35 (COL-4).
TABLES_NEUVES = {"copie", "region_origine", "jeu_document", "retrait_vu"}


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
def vraie_v30(tmp_path, monkeypatch):
    """`tests/bases/v30-5e7f56b.sql`, chargée dans une base du test. Les dossiers d'images
    sont ceux du test, vides."""
    from pipeline import ingest
    db = tmp_path / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V30.read_text(encoding="utf-8"))
    c.close()
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    return db


# Les colonnes que la v31 ajoute, table par table : retirées des lignes d'APRÈS pour les
# comparer à celles d'avant.
COLONNES_NEUVES = {"albums": ("tome", "lieu_masters"), "planches": ("master_origine",),
                   "collection": ("base", "acces_membres"),
                   "document": ("projet_origine_nom",),
                   "demande": ("collection_id", "collection_nom", "cran"),
                   "demande_document": ("copie_id",),
                   "projet": ("bac_a_sable_de", "efface_le", "jeu", "membres_creent_collections"),
                   "personnages": ("bac_a_sable_id",), "tags": ("espace",)}
LIGNES = ("albums", "planches", "regions", "personnages", "projet", "projet_acces",
          "collection", "collection_acces", "collection_album", "document", "demande",
          "demande_document", "evenement", "activite")


def _etat(db):
    tables = [r["name"] for r in _sql(
        db, "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE 'recherche_%' ORDER BY name")]
    lignes = {}
    for t in LIGNES:
        retire = COLONNES_NEUVES.get(t, ())
        lignes[t] = sorted((json.dumps({k: v for k, v in r.items() if k not in retire},
                                       sort_keys=True, ensure_ascii=False)
                            for r in _sql(db, f'SELECT * FROM "{t}"')))
    return {
        "comptes": {t: _sql(db, f'SELECT COUNT(*) AS n FROM "{t}"')[0]["n"] for t in tables},
        "lignes": lignes,
        "index": sorted(r["sql"] for r in _sql(
            db, "SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")),
        "recherche": sorted(r["region_id"] for r in _sql(
            db, "SELECT region_id FROM recherche WHERE recherche MATCH 'otage'")),
    }


def test_la_base_chargee_est_bien_une_v30_qui_a_vecu(vraie_v30):
    """Le décor d'abord : sans lui, les tests suivants passeraient sur une base vide."""
    assert _sql(vraie_v30, "PRAGMA user_version")[0]["user_version"] == 30
    assert "AUTOINCREMENT" not in _sql(
        vraie_v30, "SELECT sql FROM sqlite_master WHERE name = 'projet'")[0]["sql"].upper()
    assert _sql(vraie_v30, "SELECT COUNT(*) AS n FROM projet WHERE repli = 0")[0]["n"] == 1
    assert _sql(vraie_v30, "SELECT DISTINCT genre FROM demande ORDER BY genre") == [
        {"genre": "suppression_document"}, {"genre": "suppression_projet"}]
    assert _sql(vraie_v30, "SELECT MAX(id) AS m FROM projet")[0]["m"] == 2
    assert _sql(vraie_v30, "SELECT MAX(projet_id) AS m FROM demande")[0]["m"] == 3
    assert _sql(vraie_v30, "SELECT COUNT(*) AS n FROM document WHERE importe_par IS NULL")[0][
        "n"] == 0


def test_une_vraie_base_v30_migre_sans_rien_perdre(vraie_v30):
    avant = _etat(vraie_v30)
    database.init_db()
    apres = _etat(vraie_v30)
    assert _sql(vraie_v30, "PRAGMA user_version")[0]["user_version"] \
        == database.SCHEMA_VERSION
    # Deux collections naissent, une base NEUVE par projet (D10) — le projet de repli
    # compris ; aucune collection existante ne change (Hugo, 2026-10-17).
    assert apres["comptes"]["collection"] == avant["comptes"]["collection"] + 2
    assert {t: n for t, n in apres["comptes"].items()
            if t not in TABLES_NEUVES | {"collection"}} \
        == {t: n for t, n in avant["comptes"].items() if t != "collection"}
    nees = sorted(set(apres["lignes"]["collection"]) - set(avant["lignes"]["collection"]))
    assert set(avant["lignes"]["collection"]) <= set(apres["lignes"]["collection"])
    assert len(nees) == 2 and {'"nom": "Étude B"' in n for n in nees} == {True, False}, nees
    assert any(f'"nom": "{database.NOM_PROJET_DEFAUT}"' in n for n in nees), nees
    assert {t: v for t, v in apres["lignes"].items() if t != "collection"} \
        == {t: v for t, v in avant["lignes"].items() if t != "collection"}
    assert set(avant["index"]) <= set(apres["index"])
    assert apres["recherche"] == avant["recherche"]
    assert _sql(vraie_v30, "PRAGMA foreign_key_check") == []
    assert _sql(vraie_v30, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"


def test_chaque_album_recoit_sa_copie_d_origine(vraie_v30):
    """Une ligne `copie` par album : la copie d'origine de son document, créée par qui l'a
    importé, quand il l'a importé. Rien n'est inventé pour ce que la v30 ne savait pas."""
    database.init_db()
    copies = _sql(vraie_v30, "SELECT * FROM copie ORDER BY album_id")
    attendu = _sql(vraie_v30, "SELECT a.id AS album_id, d.importe_par AS creee_par, "
                              "d.importe_le AS creee_le, NULL AS depuis_album_id, "
                              "'origine' AS cran, NULL AS depuis_projet_nom "
                              "FROM albums a JOIN document d ON d.id = a.document_id "
                              "ORDER BY a.id")
    assert copies == attendu
    assert len(copies) == _sql(vraie_v30, "SELECT COUNT(*) AS n FROM albums")[0]["n"]
    assert database.albums_sans_copie(sqlite3.connect(vraie_v30)) == []


def test_le_projet_d_origine_garde_son_nom(vraie_v30):
    """Photographié à la migration : le nom ACTUEL du projet d'origine. Un document entré
    sans projet (importé au fonds) n'en a pas."""
    database.init_db()
    lignes = _sql(vraie_v30, "SELECT d.projet_origine_id, d.projet_origine_nom, p.nom "
                             "FROM document d LEFT JOIN projet p ON p.id = d.projet_origine_id "
                             "ORDER BY d.id")
    assert lignes and all(x["projet_origine_nom"] == x["nom"] for x in lignes)
    assert {x["projet_origine_nom"] for x in lignes} == {"Projet principal", "Étude B", None}


def test_le_compteur_des_projets_passe_au_dessus_de_ce_qui_a_ete_nomme(vraie_v30):
    """Le projet 3 a vécu deux fois (rendu par SQLite en v30) et n'existe plus : seuls le
    journal et une demande le nomment. Il ne revient pas."""
    database.init_db()
    assert "AUTOINCREMENT" in _sql(
        vraie_v30, "SELECT sql FROM sqlite_master WHERE name = 'projet'")[0]["sql"].upper()
    assert _seq(vraie_v30)["projet"] == 3
    c = sqlite3.connect(vraie_v30)
    assert c.execute("INSERT INTO projet (nom) VALUES ('Neuf')").lastrowid == 4
    c.rollback()
    c.close()


def test_rejouee_la_migration_ne_change_rien(vraie_v30):
    database.init_db()
    etat = (_etat(vraie_v30), _seq(vraie_v30),
            _sql(vraie_v30, "SELECT * FROM copie ORDER BY album_id"),
            _sql(vraie_v30, "SELECT type, name, sql FROM sqlite_master ORDER BY name"))
    _sql(vraie_v30, "PRAGMA user_version = 30")
    database.init_db()
    assert (_etat(vraie_v30), _seq(vraie_v30),
            _sql(vraie_v30, "SELECT * FROM copie ORDER BY album_id"),
            _sql(vraie_v30, "SELECT type, name, sql FROM sqlite_master ORDER BY name")) == etat


def test_une_base_migree_porte_le_schema_d_une_base_neuve(vraie_v30, tmp_path, monkeypatch):
    """Les colonnes arrivent par `CREATE TABLE` sur une base neuve et par `ALTER` sur une
    base migrée : même nom, même type, même rang, mêmes clés étrangères."""
    database.init_db()
    neuve = tmp_path / "neuve.sqlite"
    monkeypatch.setattr(database, "DB_PATH", neuve)
    database.init_db()

    def forme(db):
        return {t: (_sql(db, f"PRAGMA table_info({t})"),
                    sorted((f["from"], f["table"], f["to"], f["on_delete"])
                           for f in _sql(db, f"PRAGMA foreign_key_list({t})")))
                for t in ("collection", "document", "demande", "demande_document", "copie",
                          "projet")}
    assert forme(vraie_v30) == forme(neuve)
    assert re.search(r"id\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", _sql(
        vraie_v30, "SELECT sql FROM sqlite_master WHERE name = 'projet'")[0]["sql"])


# --------------------------------------------------------------------------- #
# Chaque source qui nomme un projet, seule (le patron de `test_identifiants_v30`)
# --------------------------------------------------------------------------- #
@pytest.fixture
def base_v30(tmp_path, monkeypatch):
    """Une base neuve ramenée à la forme v30 sur ce qui compte ici : `projet` sans
    AUTOINCREMENT, `user_version = 30`. Le reste de la v31 est déjà là, et la migration le
    traverse sans rien y changer (elle est idempotente)."""
    from pipeline import ingest
    db = tmp_path / "v30.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    database.init_db()
    c = sqlite3.connect(db)
    sql = c.execute("SELECT sql FROM sqlite_master WHERE name = 'projet'").fetchone()[0]
    vieux = re.sub(r"PRIMARY KEY AUTOINCREMENT", "PRIMARY KEY", sql, count=1)
    vieux = re.sub(r"^CREATE TABLE\s+(IF NOT EXISTS\s+)?\"?projet\"?\s*\(",
                   "CREATE TABLE projet__v30 (", vieux, count=1)
    c.execute(vieux)
    c.execute("INSERT INTO projet__v30 SELECT * FROM projet")
    c.execute("DROP TABLE projet")
    c.execute("ALTER TABLE projet__v30 RENAME TO projet")
    c.execute("DELETE FROM sqlite_sequence WHERE name = 'projet'")
    c.execute("PRAGMA user_version = 30")
    c.commit()
    c.close()
    assert "AUTOINCREMENT" not in _sql(db, "SELECT sql FROM sqlite_master "
                                           "WHERE name = 'projet'")[0]["sql"].upper()
    return db


SOURCES_PROJET = {
    "la cible d'un acte sur un projet": (
        50, "INSERT INTO evenement (type, agent_type, cible_table, cible_id) "
            "VALUES ('suppression', 'humain', 'projet', 50)"),
    "la cible d'un membre de projet": (
        55, "INSERT INTO evenement (type, agent_type, cible_table, cible_id) "
            "VALUES ('delien', 'humain', 'projet_acces', 55)"),
    "projet_id dans une charge": (
        60, "INSERT INTO evenement (type, agent_type, cible_table, cible_id, apres) "
            "VALUES ('creation', 'humain', 'demande', 1, '{\"projet_id\": 60}')"),
    "le projet d'une demande": (
        65, "INSERT INTO demande (genre, projet_id, projet_nom) "
            "VALUES ('suppression_projet', 65, 'Parti')"),
    "le projet d'origine d'un document": (
        70, "INSERT INTO document (importe_par, projet_origine_id) VALUES (NULL, 70)"),
}


@pytest.mark.parametrize("source", sorted(SOURCES_PROJET))
def test_le_compteur_des_projets_part_au_dessus_de_chaque_source(base_v30, source):
    haut, insertion = SOURCES_PROJET[source]
    _sql(base_v30, insertion)
    database.init_db()
    assert _sql(base_v30, "PRAGMA user_version")[0]["user_version"] \
        == database.SCHEMA_VERSION
    assert _seq(base_v30)["projet"] == haut, _seq(base_v30)


def test_sans_source_le_compteur_suit_les_projets_vivants(base_v30):
    database.init_db()
    vivants = _sql(base_v30, "SELECT MAX(id) AS m FROM projet")[0]["m"]
    assert _seq(base_v30)["projet"] == vivants
