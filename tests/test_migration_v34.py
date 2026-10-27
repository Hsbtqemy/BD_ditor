"""IMG-1 — la migration v34, sur une VRAIE base v33.

La règle de Hugo (2026-10-16, `CLAUDE.md` § Schéma & migrations) : une migration se vérifie
sur une base de la version précédente qui a VÉCU, faite par le code de cette version
(`tools/fabriquer_base_de_version.py e5d2e73 tests/bases/v33-e5d2e73.sql` — `e5d2e73`, la
tête de `dev` avant la v34, est le dernier état de la v33). Elle porte ce que portait la
v32 : des destructions en haut des tables, un journal sous trois comptes, deux copies sœurs
qui désignent le MÊME master (planches 11 et 12), des demandes de quatre genres.

Ce que la v34 apporte, et rien d'autre : deux colonnes, posées par `ALTER`, NULL pour tout
l'existant.
- `albums.lieu_masters` : où vivent les masters d'archive de l'album — un champ libre,
  facultatif, humain (le serveur ne garde plus le scan reçu, seulement sa copie de travail) ;
- `planches.master_origine` : ce que l'outil sait du master d'une planche — le chemin
  ShareDocs d'un import ShareDocs, sinon le nom du fichier reçu. NULL veut dire que la
  planche date d'avant la v34 : son fichier EST encore le scan.

En particulier, la migration ne CONVERTIT rien : `chemin_tiff` désigne toujours le master
de chaque planche existante, et seul l'outil de rattrapage, lancé exprès, le remplace par
une copie de travail (`tools/convertir_en_copies_de_travail.py`).
"""
import json
import sqlite3
from pathlib import Path

import pytest

import database
import migration_v38
from migration_v38 import COLONNES_V38

BASE_V33 = Path(__file__).resolve().parent / "bases" / "v33-e5d2e73.sql"
COLONNES_NEUVES = {"albums": ("lieu_masters",), "planches": ("master_origine",),
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
def vraie_v33(tmp_path, monkeypatch):
    """`tests/bases/v33-e5d2e73.sql`, chargée dans une base du test. Les dossiers d'images
    sont ceux du test, vides."""
    from pipeline import ingest
    db = tmp_path / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V33.read_text(encoding="utf-8"))
    c.close()
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    return db


# La v37 (ANN-7, tranche 1) aussi : seize tables neuves, vides, et `regions.nom`.
TABLES_NEUVES |= set(database.TABLES_DES_GRILLES)
COLONNES_NEUVES["regions"] = (*COLONNES_NEUVES.get("regions", ()), "nom")

# La v38 (COL-3, tranche 3c) : `geste_sur_copie` part, `demande` gagne deux colonnes, et des
# membres de projet naissent des accès hors projet (`migration_v38`, éprouvée par
# `tests/test_migration_v38.py`).
TABLES_NEUVES.discard("geste_sur_copie")
for _t, _c in COLONNES_V38.items():
    COLONNES_NEUVES[_t] = (*COLONNES_NEUVES.get(_t, ()), *_c)


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


def test_la_base_chargee_est_bien_une_v33_qui_a_vecu(vraie_v33):
    """Le décor d'abord : sans lui, les tests suivants passeraient sur une base vide."""
    assert _sql(vraie_v33, "PRAGMA user_version")[0]["user_version"] == 33
    assert "lieu_masters" not in _colonnes(vraie_v33, "albums")
    assert "master_origine" not in _colonnes(vraie_v33, "planches")
    # Ce que la v33 a apporté est là : le tome.
    assert "tome" in _colonnes(vraie_v33, "albums")
    # Les destructions en haut des tables : des identifiants que le journal nomme encore.
    assert _sql(vraie_v33, "SELECT id FROM albums WHERE id = 4") == []
    assert _sql(vraie_v33, "SELECT MAX(id) AS m FROM albums")[0]["m"] == 12
    assert {r["name"]: r["seq"] for r in _sql(
        vraie_v33, "SELECT name, seq FROM sqlite_sequence")}["albums"] >= 12
    # Un journal, trois comptes humains.
    assert _sql(vraie_v33, "SELECT COUNT(*) AS n FROM evenement")[0]["n"] > 100
    assert _sql(vraie_v33, "SELECT COUNT(DISTINCT agent) AS n FROM evenement "
                           "WHERE agent_type = 'humain'")[0]["n"] >= 3
    # Deux copies sœurs d'un même document, dont les planches désignent le MÊME master —
    # le cas que l'outil de rattrapage doit ne convertir qu'une fois.
    partages = _sql(vraie_v33, "SELECT chemin_tiff, COUNT(*) AS n FROM planches "
                               "GROUP BY chemin_tiff HAVING n > 1")
    assert len(partages) == 1 and partages[0]["n"] == 2
    # Des masters, à la taille du scan : rien n'y est encore une copie de travail.
    assert all(r["chemin_tiff"].endswith(".png") for r in _sql(
        vraie_v33, "SELECT chemin_tiff FROM planches"))
    assert {r["genre"] for r in _sql(vraie_v33, "SELECT DISTINCT genre FROM demande")} == {
        "rejoindre", "rendre_copie", "suppression_document", "suppression_projet"}


def test_une_vraie_base_v33_migre_sans_rien_perdre(vraie_v33):
    avant = _etat(vraie_v33)
    membres_avant = migration_v38.membres(vraie_v33)
    database.init_db()
    migration_v38.retirer_les_membres_de_la_v38(vraie_v33, membres_avant)
    apres = _etat(vraie_v33)
    assert _sql(vraie_v33, "PRAGMA user_version")[0]["user_version"] == database.SCHEMA_VERSION
    # Aucune table de plus ni de moins, aucune ligne de plus ni de moins.
    assert [t for t in apres["tables"] if t not in TABLES_NEUVES] == avant["tables"]
    assert {t: n for t, n in apres["comptes"].items()
            if t not in TABLES_NEUVES} == avant["comptes"]
    # Les lignes, colonnes neuves mises à part, sont celles d'avant — chemins compris.
    assert apres["lignes"] == avant["lignes"]
    assert set(avant["index"]) <= set(apres["index"])
    # Les compteurs AUTOINCREMENT ne bougent pas : un identifiant détruit ne revient pas.
    # v35 (COL-4) : `collection` reçoit AUTOINCREMENT, donc une ligne de compteur.
    assert [s for s in apres["sequence"] if s["name"] != "collection"] == avant["sequence"]
    assert apres["recherche"] == avant["recherche"]
    assert _sql(vraie_v33, "PRAGMA foreign_key_check") == []
    assert _sql(vraie_v33, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"


def test_les_deux_colonnes_arrivent_vides_et_rien_n_est_converti(vraie_v33):
    """NULL partout : ni lieu deviné, ni origine tirée du nom du master. Et chaque planche
    garde son master : `chemin_tiff` n'a pas bougé, `master_origine` NULL le dit."""
    chemins = _sql(vraie_v33, "SELECT id, chemin_tiff, largeur_px, dpi_x, mode FROM planches "
                              "ORDER BY id")
    database.init_db()
    assert "lieu_masters" in _colonnes(vraie_v33, "albums")
    assert "master_origine" in _colonnes(vraie_v33, "planches")
    assert _sql(vraie_v33, "SELECT COUNT(*) AS n FROM albums "
                           "WHERE lieu_masters IS NOT NULL")[0]["n"] == 0
    assert _sql(vraie_v33, "SELECT COUNT(*) AS n FROM planches "
                           "WHERE master_origine IS NOT NULL")[0]["n"] == 0
    assert _sql(vraie_v33, "SELECT id, chemin_tiff, largeur_px, dpi_x, mode FROM planches "
                           "ORDER BY id") == chemins


def test_rejouee_la_migration_ne_change_rien(vraie_v33):
    database.init_db()
    _sql(vraie_v33, "UPDATE albums SET lieu_masters = 'ShareDocs, Scans/A3' WHERE id = 3")
    _sql(vraie_v33, "UPDATE planches SET master_origine = 'p1.tif' WHERE id = 5")
    etat = (_etat(vraie_v33),
            _sql(vraie_v33, "SELECT id, lieu_masters FROM albums ORDER BY id"),
            _sql(vraie_v33, "SELECT id, master_origine FROM planches ORDER BY id"),
            _sql(vraie_v33, "SELECT type, name, sql FROM sqlite_master ORDER BY name"))
    _sql(vraie_v33, "PRAGMA user_version = 33")
    database.init_db()
    assert (_etat(vraie_v33),
            _sql(vraie_v33, "SELECT id, lieu_masters FROM albums ORDER BY id"),
            _sql(vraie_v33, "SELECT id, master_origine FROM planches ORDER BY id"),
            _sql(vraie_v33, "SELECT type, name, sql FROM sqlite_master ORDER BY name")) == etat
    # Un second démarrage, à la version courante, ne rejoue rien non plus.
    database.init_db()
    assert _sql(vraie_v33, "SELECT lieu_masters FROM albums WHERE id = 3") == [
        {"lieu_masters": "ShareDocs, Scans/A3"}]


def test_une_base_migree_porte_les_colonnes_d_une_base_neuve(vraie_v33, tmp_path,
                                                             monkeypatch):
    """Les colonnes arrivent par `CREATE TABLE` sur une base neuve et par `ALTER` sur une
    base migrée : même nom, même type, même nullité, même défaut. PAS le même rang — le
    schéma neuf les pose à côté de `source_numerisation` et de `mode`, `ALTER` en dernier ;
    toutes les lectures nomment leurs colonnes (éprouvé par `creer_copie`, plus bas)."""
    database.init_db()
    neuve = tmp_path / "neuve.sqlite"
    monkeypatch.setattr(database, "DB_PATH", neuve)
    database.init_db()

    def forme(db, table):
        return ({n: (c["type"], c["notnull"], c["dflt_value"], c["pk"])
                 for n, c in _colonnes(db, table).items()},
                sorted((f["from"], f["table"], f["to"], f["on_delete"])
                       for f in _sql(db, f"PRAGMA foreign_key_list({table})")),
                sorted(i["name"] for i in _sql(db, f"PRAGMA index_list({table})")))
    for table in ("albums", "planches"):
        assert forme(vraie_v33, table) == forme(neuve, table), table


def test_sur_une_base_migree_une_copie_soeur_suit_le_lieu_et_l_origine(vraie_v33):
    """Une copie sœur désigne les MÊMES fichiers (D6) : elle reprend ce qu'on sait de leur
    master (`master_origine`, dans `PLANCHE_SCAN`) et, avec la notice, où vivent les masters
    de l'album (`lieu_masters`) — par les NOMS des colonnes, sur une base où elles ne sont
    pas au rang du schéma neuf."""
    database.init_db()
    collection = _sql(vraie_v33, "SELECT collection_id FROM collection_album "
                                 "WHERE album_id = 1")[0]["collection_id"]
    document = _sql(vraie_v33, "SELECT document_id FROM albums WHERE id = 1")[0]["document_id"]
    _sql(vraie_v33, "UPDATE albums SET lieu_masters = 'Disque de l''équipe' WHERE id = 1")
    _sql(vraie_v33, "UPDATE planches SET master_origine = 'sharedocs:BD/p1.tif' "
                    "WHERE album_id = 1 AND numero = 1")
    c = sqlite3.connect(vraie_v33)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        copie = database.creer_copie(c, document, collection, par=None, depuis=1,
                                     cran=database.CRAN_IMAGES)
        album = dict(c.execute("SELECT lieu_masters, tome, titre FROM albums WHERE id = ?",
                               (copie,)).fetchone())
        planches = [dict(r) for r in c.execute(
            "SELECT numero, chemin_tiff, master_origine FROM planches WHERE album_id = ? "
            "ORDER BY numero", (copie,))]
        source = [dict(r) for r in c.execute(
            "SELECT numero, chemin_tiff, master_origine FROM planches WHERE album_id = 1 "
            "ORDER BY numero")]
    finally:
        c.rollback()
        c.close()
    assert album["lieu_masters"] == "Disque de l'équipe"
    assert planches == source
    assert planches[0]["master_origine"] == "sharedocs:BD/p1.tif"
