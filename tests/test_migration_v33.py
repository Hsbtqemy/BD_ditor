"""META-1 — la migration v33, sur une VRAIE base v32.

La règle de Hugo (2026-10-16, `CLAUDE.md` § Schéma & migrations) : une migration se vérifie
sur une base de la version précédente qui a VÉCU, faite par le code de cette version
(`tools/fabriquer_base_de_version.py 0b4f1ef tests/bases/v32-0b4f1ef.sql` — `0b4f1ef`,
parent de `c9a783c`, est le dernier état de la v32). Elle porte ce que portait la v31, plus
les tokens que spaCy écrit quand il est installé là où on la fabrique.

Ce que la v33 apporte (`c9a783c`), et rien d'autre : `albums.tome`, le rang d'un album dans
sa série, en texte libre (« 1 », « HS », « Intégrale »), posé par `ALTER` — NULL pour tout
l'existant, aucune donnée à migrer. En particulier, aucun titre n'est relu pour en extraire
un tome (« pas d'outil de rattrapage des titres existants »).

Le parcours de l'outil ne pose ni série ni titre à tome : la base n'a que des « Album N ».
Le test en sème donc, APRÈS le chargement et AVANT la migration (`_semer_series`), pour
qu'une migration qui toucherait aux titres ou aux séries ait de quoi se trahir. Le fichier
`.sql` reste tel que l'outil l'a fait.
"""
import json
import sqlite3
from pathlib import Path

import pytest

import database

BASE_V32 = Path(__file__).resolve().parent / "bases" / "v32-0b4f1ef.sql"
COLONNES_NEUVES = {"albums": ("tome", "lieu_masters"), "planches": ("master_origine",),
                   "projet": ("bac_a_sable_de", "efface_le", "jeu", "membres_creent_collections"),
                   "personnages": ("bac_a_sable_id",), "tags": ("espace",)}
# La v36 marque les couches qu'une copie amorcée reprend (`recopiee`).
COLONNES_NEUVES.update({t: ("recopiee",) for t in database.COUCHES_RECOPIEES})
# Ce que la v35 ajoute (COL-4), que la migration traverse aussi.
TABLES_NEUVES = {"jeu_document", "retrait_vu", "geste_sur_copie"}  # les deux derniers : la v36
LIGNES = ("albums", "planches", "regions", "annotations", "personnages", "projet",
          "projet_acces", "collection", "collection_acces", "collection_album", "document",
          "copie", "demande", "demande_document", "region_origine", "contribution",
          "tokens", "evenement", "activite")

# Ce que le test sème avant de migrer : des titres qui portent leur tome, des séries.
SEMIS = {
    1: ("Tome 3 — Tintin en Amérique", "Les Aventures de Tintin"),
    2: ("Astérix, T. 12 : Astérix aux Jeux olympiques", "Astérix"),
    3: ("Hors-série", "Spirou et Fantasio"),
}


def _sql(db, q, p=()):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        r = [dict(x) for x in c.execute(q, p)]
        c.commit()
        return r
    finally:
        c.close()


def _semer_series(db):
    for album_id, (titre, serie) in SEMIS.items():
        _sql(db, "UPDATE albums SET titre = ?, serie = ? WHERE id = ?",
             (titre, serie, album_id))


@pytest.fixture
def vraie_v32(tmp_path, monkeypatch):
    """`tests/bases/v32-0b4f1ef.sql`, chargée dans une base du test, avec les séries du
    semis. Les dossiers d'images sont ceux du test, vides."""
    from pipeline import ingest
    db = tmp_path / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V32.read_text(encoding="utf-8"))
    c.close()
    _semer_series(db)
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
        "tables": tables,
        "comptes": {t: _sql(db, f'SELECT COUNT(*) AS n FROM "{t}"')[0]["n"] for t in tables},
        "lignes": lignes,
        "index": sorted(r["sql"] for r in _sql(
            db, "SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")),
        "sequence": _sql(db, "SELECT name, seq FROM sqlite_sequence ORDER BY name"),
        "recherche": sorted(r["region_id"] for r in _sql(
            db, "SELECT region_id FROM recherche WHERE recherche MATCH 'otage'")),
    }


def _colonnes(db, table):
    return {c["name"]: c for c in _sql(db, f"PRAGMA table_info({table})")}


def test_la_base_chargee_est_bien_une_v32_qui_a_vecu(vraie_v32):
    """Le décor d'abord : sans lui, les tests suivants passeraient sur une base vide."""
    assert _sql(vraie_v32, "PRAGMA user_version")[0]["user_version"] == 32
    assert "tome" not in _colonnes(vraie_v32, "albums")
    # Ce que la v32 a apporté est là : la table `region_origine`, `demande.cran`.
    assert "region_origine" in {r["name"] for r in _sql(
        vraie_v32, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "cran" in _colonnes(vraie_v32, "demande")
    # Les destructions en haut des tables : des identifiants que le journal nomme encore.
    assert _sql(vraie_v32, "SELECT id FROM albums WHERE id = 4") == []
    assert _sql(vraie_v32, "SELECT MAX(id) AS m FROM albums")[0]["m"] == 12
    assert {r["name"]: r["seq"] for r in _sql(
        vraie_v32, "SELECT name, seq FROM sqlite_sequence")}["albums"] >= 12
    # Un journal, trois comptes humains.
    assert _sql(vraie_v32, "SELECT COUNT(*) AS n FROM evenement")[0]["n"] > 100
    assert _sql(vraie_v32, "SELECT COUNT(DISTINCT agent) AS n FROM evenement "
                           "WHERE agent_type = 'humain'")[0]["n"] >= 3
    # Deux copies sœurs d'un même document, des demandes de quatre genres.
    soeurs = _sql(vraie_v32, "SELECT document_id, COUNT(*) AS n FROM albums "
                             "GROUP BY document_id HAVING n > 1")
    assert len(soeurs) == 1 and soeurs[0]["n"] == 2
    assert {r["genre"] for r in _sql(vraie_v32, "SELECT DISTINCT genre FROM demande")} == {
        "rejoindre", "rendre_copie", "suppression_document", "suppression_projet"}
    # Et le semis du test, que la migration ne doit pas toucher.
    assert {r["id"]: (r["titre"], r["serie"]) for r in _sql(
        vraie_v32, "SELECT id, titre, serie FROM albums WHERE serie IS NOT NULL")} == SEMIS


def test_une_vraie_base_v32_migre_sans_rien_perdre(vraie_v32):
    avant = _etat(vraie_v32)
    database.init_db()
    apres = _etat(vraie_v32)
    assert _sql(vraie_v32, "PRAGMA user_version")[0]["user_version"] == database.SCHEMA_VERSION
    # Aucune table de plus ni de moins, aucune ligne de plus ni de moins.
    assert [t for t in apres["tables"] if t not in TABLES_NEUVES] == avant["tables"]
    assert {t: n for t, n in apres["comptes"].items()
            if t not in TABLES_NEUVES} == avant["comptes"]
    # Les lignes, colonne neuve mise à part, sont celles d'avant — titres et séries compris.
    assert apres["lignes"] == avant["lignes"]
    assert set(avant["index"]) <= set(apres["index"])
    # Les compteurs AUTOINCREMENT ne bougent pas : un identifiant détruit ne revient pas.
    # v35 (COL-4) : `collection` reçoit AUTOINCREMENT, donc une ligne de compteur.
    assert [s for s in apres["sequence"] if s["name"] != "collection"] == avant["sequence"]
    assert apres["recherche"] == avant["recherche"]
    assert _sql(vraie_v32, "PRAGMA foreign_key_check") == []
    assert _sql(vraie_v32, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"


def test_le_tome_arrive_vide_et_aucun_titre_n_est_relu(vraie_v32):
    """La colonne existe, NULL partout : ni valeur par défaut, ni tome tiré d'un titre
    (« Tome 3 — … »), ni d'une série."""
    database.init_db()
    assert "tome" in _colonnes(vraie_v32, "albums")
    assert _sql(vraie_v32, "SELECT COUNT(*) AS n FROM albums WHERE tome IS NOT NULL")[0][
        "n"] == 0
    assert {r["id"]: (r["titre"], r["serie"]) for r in _sql(
        vraie_v32, "SELECT id, titre, serie FROM albums WHERE serie IS NOT NULL")} == SEMIS


def test_rejouee_la_migration_ne_change_rien(vraie_v32):
    database.init_db()
    _sql(vraie_v32, "UPDATE albums SET tome = 'HS' WHERE id = 3")
    etat = (_etat(vraie_v32), _sql(vraie_v32, "SELECT id, tome FROM albums ORDER BY id"),
            _sql(vraie_v32, "SELECT type, name, sql FROM sqlite_master ORDER BY name"))
    _sql(vraie_v32, "PRAGMA user_version = 32")
    database.init_db()
    assert (_etat(vraie_v32), _sql(vraie_v32, "SELECT id, tome FROM albums ORDER BY id"),
            _sql(vraie_v32, "SELECT type, name, sql FROM sqlite_master ORDER BY name")) == etat
    # Un second démarrage, à la version courante, ne rejoue rien non plus.
    database.init_db()
    assert _sql(vraie_v32, "SELECT tome FROM albums WHERE id = 3") == [{"tome": "HS"}]


def test_une_base_migree_porte_les_colonnes_d_une_base_neuve(vraie_v32, tmp_path,
                                                             monkeypatch):
    """La colonne arrive par `CREATE TABLE` sur une base neuve et par `ALTER` sur une base
    migrée : même nom, même type, même nullité, même défaut. PAS le même rang : le schéma
    neuf la pose après `serie`, `ALTER` la pose en dernier. Aucune lecture d'`albums` n'en
    dépend (toutes nomment leurs colonnes, `creer_copie` compris — éprouvé plus bas), d'où
    une comparaison par nom."""
    database.init_db()
    neuve = tmp_path / "neuve.sqlite"
    monkeypatch.setattr(database, "DB_PATH", neuve)
    database.init_db()

    def forme(db):
        return ({n: (c["type"], c["notnull"], c["dflt_value"], c["pk"])
                 for n, c in _colonnes(db, "albums").items()},
                sorted((f["from"], f["table"], f["to"], f["on_delete"])
                       for f in _sql(db, "PRAGMA foreign_key_list(albums)")),
                sorted(i["name"] for i in _sql(db, "PRAGMA index_list(albums)")))
    assert forme(vraie_v32) == forme(neuve)


def test_sur_une_base_migree_une_copie_recopie_le_tome(vraie_v32):
    """`creer_copie` recopie la notice par les NOMS de `PRAGMA table_info(albums)` : sur une
    base migrée, où `tome` n'est pas au rang du schéma neuf, le tome suit quand même la
    notice et ne glisse pas dans une autre colonne."""
    database.init_db()
    source = _sql(vraie_v32, "SELECT id, document_id FROM albums WHERE id = 1")[0]
    collection = _sql(vraie_v32, "SELECT collection_id FROM collection_album "
                                 "WHERE album_id = 1")[0]["collection_id"]
    _sql(vraie_v32, "UPDATE albums SET tome = '3' WHERE id = 1")
    c = sqlite3.connect(vraie_v32)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        copie = database.creer_copie(c, source["document_id"], collection, par=None,
                                     depuis=1, cran=database.CRAN_IMAGES)
        lus = {r["id"]: dict(r) for r in c.execute(
            "SELECT id, titre, serie, tome, description, date_edition FROM albums "
            "WHERE id IN (1, ?)", (copie,))}
    finally:
        c.rollback()
        c.close()
    attendu = {k: v for k, v in lus[1].items() if k != "id"}
    assert attendu["tome"] == "3" and attendu["serie"] == "Les Aventures de Tintin"
    assert {k: v for k, v in lus[copie].items() if k != "id"} == attendu
