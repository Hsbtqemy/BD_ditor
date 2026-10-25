"""COL-3, tranche 3b — la migration v32, sur une VRAIE base v31.

La règle de Hugo (2026-10-16, `CLAUDE.md` § Schéma & migrations) : une migration se vérifie
sur une base de la version précédente qui a VÉCU, faite par le code de cette version
(`tools/fabriquer_base_de_version.py 16c6127 tests/bases/v31-16c6127.sql`) — en plus de ce
que portait la v30 : la base d'un projet ouverte à ses membres, deux copies sœurs d'un même
document, un « rejoindre » accepté et un refusé, un retour qui attend.

Ce que la v32 apporte (`docs/col3-tranche3b-cadrage.md`, E2, tranché par Hugo le
2026-10-20), et rien d'autre :

- `region_origine` : ce qu'une région copiée doit à une région source — VIDE à la
  migration, aucune copie d'avant la v32 n'ayant recopié de région ;
- `demande.cran` : le cran d'une copie amorcée ou d'une remise à zéro demandée — NULL
  pour toute demande existante.
"""
import json
import re
import sqlite3
from pathlib import Path

import pytest

import database

BASE_V31 = Path(__file__).resolve().parent / "bases" / "v31-16c6127.sql"
TABLES_NEUVES = {"region_origine", "jeu_document"}
COLONNES_NEUVES = {"demande": ("cran",), "albums": ("tome", "lieu_masters"),
                   "planches": ("master_origine",), "projet": ("bac_a_sable_de", "efface_le", "jeu", "membres_creent_collections"),
                   "personnages": ("bac_a_sable_id",), "tags": ("espace",)}
LIGNES = ("albums", "planches", "regions", "annotations", "personnages", "projet",
          "projet_acces", "collection", "collection_acces", "collection_album", "document",
          "copie", "demande", "demande_document", "evenement", "activite")


def _sql(db, q, p=()):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        r = [dict(x) for x in c.execute(q, p)]
        c.commit()
        return r
    finally:
        c.close()


@pytest.fixture
def vraie_v31(tmp_path, monkeypatch):
    """`tests/bases/v31-16c6127.sql`, chargée dans une base du test. Les dossiers d'images
    sont ceux du test, vides."""
    from pipeline import ingest
    db = tmp_path / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V31.read_text(encoding="utf-8"))
    c.close()
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    return db


def _etat(db):
    tables = [r["name"] for r in _sql(
        db, "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE 'recherche_%' ORDER BY name")]
    lignes = {}
    for t in LIGNES:
        retire = COLONNES_NEUVES.get(t, ())
        lignes[t] = sorted(json.dumps({k: v for k, v in r.items() if k not in retire},
                                      sort_keys=True, ensure_ascii=False)
                           for r in _sql(db, f'SELECT * FROM "{t}"'))
    return {
        "comptes": {t: _sql(db, f'SELECT COUNT(*) AS n FROM "{t}"')[0]["n"] for t in tables},
        "lignes": lignes,
        "index": sorted(r["sql"] for r in _sql(
            db, "SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")),
        "sequence": _sql(db, "SELECT name, seq FROM sqlite_sequence ORDER BY name"),
        "recherche": sorted(r["region_id"] for r in _sql(
            db, "SELECT region_id FROM recherche WHERE recherche MATCH 'otage'")),
    }


def test_la_base_chargee_est_bien_une_v31_qui_a_vecu(vraie_v31):
    """Le décor d'abord : sans lui, les tests suivants passeraient sur une base vide."""
    assert _sql(vraie_v31, "PRAGMA user_version")[0]["user_version"] == 31
    assert "region_origine" not in {r["name"] for r in _sql(
        vraie_v31, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    # Deux copies sœurs : un document, deux albums, la seconde vierge.
    soeurs = _sql(vraie_v31, "SELECT document_id, COUNT(*) AS n FROM albums "
                             "GROUP BY document_id HAVING n > 1")
    assert len(soeurs) == 1 and soeurs[0]["n"] == 2
    assert _sql(vraie_v31, "SELECT cran FROM copie WHERE depuis_album_id IS NOT NULL") == [
        {"cran": "images"}]
    # Les genres de la 3a, et leurs états.
    genres = {(r["genre"], r["reponse"]) for r in _sql(
        vraie_v31, "SELECT genre, reponse FROM demande")}
    assert {("rejoindre", "acceptee"), ("rejoindre", "refusee"),
            ("rendre_copie", None)} <= genres, genres
    # Une base ouverte à ses membres.
    assert _sql(vraie_v31, "SELECT COUNT(*) AS n FROM collection "
                           "WHERE base = 1 AND acces_membres = 'ecriture'")[0]["n"] == 1


def test_une_vraie_base_v31_migre_sans_rien_perdre(vraie_v31):
    avant = _etat(vraie_v31)
    database.init_db()
    apres = _etat(vraie_v31)
    assert _sql(vraie_v31, "PRAGMA user_version")[0]["user_version"] == database.SCHEMA_VERSION
    assert {t: n for t, n in apres["comptes"].items() if t not in TABLES_NEUVES} \
        == avant["comptes"]
    assert apres["comptes"]["region_origine"] == 0
    assert apres["lignes"] == avant["lignes"]
    assert set(avant["index"]) <= set(apres["index"])
    # v35 (COL-4) : `collection` reçoit AUTOINCREMENT, donc une ligne de compteur.
    assert [s for s in apres["sequence"] if s["name"] != "collection"] == avant["sequence"]
    assert apres["recherche"] == avant["recherche"]
    assert _sql(vraie_v31, "SELECT COUNT(*) AS n FROM demande WHERE cran IS NOT NULL")[0][
        "n"] == 0
    assert _sql(vraie_v31, "PRAGMA foreign_key_check") == []
    assert _sql(vraie_v31, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"


def test_rejouee_la_migration_ne_change_rien(vraie_v31):
    database.init_db()
    etat = (_etat(vraie_v31),
            _sql(vraie_v31, "SELECT type, name, sql FROM sqlite_master ORDER BY name"))
    _sql(vraie_v31, "PRAGMA user_version = 31")
    database.init_db()
    assert (_etat(vraie_v31),
            _sql(vraie_v31, "SELECT type, name, sql FROM sqlite_master ORDER BY name")) == etat


def test_une_base_migree_porte_le_schema_d_une_base_neuve(vraie_v31, tmp_path, monkeypatch):
    """Les colonnes arrivent par `CREATE TABLE` sur une base neuve et par `ALTER` sur une
    base migrée : même nom, même type, même rang, mêmes clés étrangères."""
    database.init_db()
    neuve = tmp_path / "neuve.sqlite"
    monkeypatch.setattr(database, "DB_PATH", neuve)
    database.init_db()

    def forme(db):
        return {t: (_sql(db, f"PRAGMA table_info({t})"),
                    sorted((f["from"], f["table"], f["to"], f["on_delete"])
                           for f in _sql(db, f"PRAGMA foreign_key_list({t})")),
                    sorted(i["name"] for i in _sql(db, f"PRAGMA index_list({t})")))
                for t in ("demande", "region_origine")}
    assert forme(vraie_v31) == forme(neuve)


def test_une_region_copiee_part_avec_sa_region_mais_pas_avec_sa_source(vraie_v31):
    """La forme de `region_origine` : la ligne meurt avec la région COPIÉE (cascade), et
    survit à la région SOURCE (aucune clé) — le journal qui nomme la source lui survit
    aussi, et c'est par lui que le travail copié reste celui de ses auteurs (E3)."""
    database.init_db()
    c = sqlite3.connect(vraie_v31)
    c.execute("PRAGMA foreign_keys = ON")
    # Une bulle (sans enfant) pour source, une case d'une AUTRE planche pour copie : la
    # cascade de `parent_id` ne doit rien emporter de l'une avec l'autre.
    source, planche = c.execute("SELECT id, planche_id FROM regions "
                                "WHERE parent_id IS NOT NULL ORDER BY id LIMIT 1").fetchone()
    copiee = c.execute("SELECT id FROM regions WHERE parent_id IS NULL AND planche_id <> ? "
                       "ORDER BY id LIMIT 1", (planche,)).fetchone()[0]
    c.execute("INSERT INTO region_origine (region_id, region_source_id) VALUES (?, ?)",
              (copiee, source))
    c.execute("DELETE FROM regions WHERE id = ?", (source,))
    assert c.execute("SELECT region_source_id FROM region_origine WHERE region_id = ?",
                     (copiee,)).fetchone() == (source,)
    c.execute("DELETE FROM regions WHERE id = ?", (copiee,))
    assert c.execute("SELECT COUNT(*) FROM region_origine").fetchone() == (0,)
    c.rollback()
    c.close()


def test_le_commentaire_de_la_derniere_colonne_est_sous_elle():
    """`cran` est la dernière colonne de `demande` : son commentaire au-dessus d'elle
    ferait tronquer le schéma par un `DROP COLUMN` (v29, mesuré sur SQLite 3.49)."""
    bloc = re.search(r"CREATE TABLE IF NOT EXISTS demande \((.*?)\n\);", database.SCHEMA_SQL,
                     re.S).group(1)
    lignes = [x.strip() for x in bloc.splitlines() if x.strip()]
    derniere = [x for x in lignes if not x.startswith("--")][-1]
    assert derniere.startswith("cran ") and not derniere.endswith(",")
    avant = lignes[lignes.index(derniere) - 1]
    assert not avant.startswith("--"), avant
