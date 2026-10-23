"""COL-4 — la migration v35, sur une VRAIE base v34.

La règle de Hugo (2026-10-16, `CLAUDE.md` § Schéma & migrations) : une migration se vérifie
sur une base de la version précédente qui a VÉCU, faite par le code de cette version
(`tools/fabriquer_base_de_version.py 35cc4a3 tests/bases/v34-35cc4a3.sql` — `35cc4a3`, la
tête de `main` avant la v35, est le dernier état de la v34). Elle porte ce que portaient les
précédentes — des destructions en haut des tables, un journal sous trois comptes, des copies
sœurs, des demandes de quatre genres — et ce que la v35 doit traverser : une copie AMORCÉE
(`region_origine`), des planches qui notent leur `master_origine`, et deux COLLECTIONS
détruites au-dessus de la plus haute qui vit — la 9, nommée encore par une demande de
« rejoindre » refusée, la 10 par le seul journal.

Ce que la v35 apporte :
- trois colonnes sur `projet` (`bac_a_sable_de`, `efface_le`, `jeu`), NULL ou 0 pour tout
  l'existant — aucun projet ne devient un bac à sable ni le projet de jeu ;
- la table `jeu_document`, vide ;
- `AUTOINCREMENT` sur `collection`, par la reconstruction de la v30 : les lignes et leurs
  identifiants intacts, et le compteur au-dessus de tout identifiant de collection que le
  journal ou une demande a jamais nommé.
"""
import json
import re
import sqlite3
from pathlib import Path

import pytest

import database

BASE_V34 = Path(__file__).resolve().parent / "bases" / "v34-35cc4a3.sql"
COLONNES_NEUVES = {"projet": ("bac_a_sable_de", "efface_le", "jeu")}
TABLES_NEUVES = {"jeu_document"}
LIGNES = ("albums", "planches", "regions", "annotations", "personnages", "projet",
          "projet_acces", "collection", "collection_acces", "collection_album", "document",
          "copie", "demande", "demande_document", "region_origine", "contribution",
          "tokens", "token_correction", "tags", "domaine", "attribut_dimension",
          "attribut_valeur", "evenement", "activite")


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
def vraie_v34(tmp_path, monkeypatch):
    """`tests/bases/v34-35cc4a3.sql`, chargée dans une base du test. Les dossiers d'images
    sont ceux du test, vides."""
    from pipeline import ingest
    db = tmp_path / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V34.read_text(encoding="utf-8"))
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
        "tables": tables,
        "comptes": {t: _sql(db, f'SELECT COUNT(*) AS n FROM "{t}"')[0]["n"] for t in tables},
        "lignes": lignes,
        "index": sorted(r["sql"] for r in _sql(
            db, "SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")),
        "vues": sorted(r["name"] for r in _sql(
            db, "SELECT name FROM sqlite_master WHERE type = 'view'")),
        "recherche": sorted(r["region_id"] for r in _sql(
            db, "SELECT region_id FROM recherche WHERE recherche MATCH 'otage'")),
    }


def _colonnes(db, table):
    return {c["name"]: c for c in _sql(db, f"PRAGMA table_info({table})")}


def _sql_de(db, table):
    return _sql(db, "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,))[0]["sql"]


def test_la_base_chargee_est_bien_une_v34_qui_a_vecu(vraie_v34):
    """Le décor d'abord : sans lui, les tests suivants passeraient sur une base vide."""
    assert _sql(vraie_v34, "PRAGMA user_version")[0]["user_version"] == 34
    assert not {"bac_a_sable_de", "efface_le", "jeu"} & set(_colonnes(vraie_v34, "projet"))
    assert "jeu_document" not in {r["name"] for r in _sql(
        vraie_v34, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "AUTOINCREMENT" not in _sql_de(vraie_v34, "collection").upper()
    # Ce que la v34 a apporté est là, rempli : les planches notent le fichier reçu.
    assert _sql(vraie_v34, "SELECT COUNT(*) AS n FROM planches "
                           "WHERE master_origine IS NOT NULL")[0]["n"] == 10
    # Une copie amorcée : des régions recopiées, leur source dite.
    assert _sql(vraie_v34, "SELECT COUNT(*) AS n FROM region_origine")[0]["n"] == 2
    # Les deux collections détruites en haut de la table, que seuls le journal et une
    # demande nomment encore.
    assert _sql(vraie_v34, "SELECT MAX(id) AS m FROM collection")[0]["m"] == 8
    assert _sql(vraie_v34, "SELECT id FROM collection WHERE id IN (9, 10)") == []
    assert _sql(vraie_v34, "SELECT reponse FROM demande WHERE collection_id = 9") == [
        {"reponse": "refusee"}]
    assert _sql(vraie_v34, "SELECT type FROM evenement WHERE cible_table = 'collection' "
                           "AND cible_id = 10 ORDER BY id") == [
        {"type": "creation"}, {"type": "suppression"}]
    assert "collection" not in _seq(vraie_v34)
    # Un journal, trois comptes humains.
    assert _sql(vraie_v34, "SELECT COUNT(DISTINCT agent) AS n FROM evenement "
                           "WHERE agent_type = 'humain'")[0]["n"] >= 3


def test_une_vraie_base_v34_migre_sans_rien_perdre(vraie_v34):
    avant = _etat(vraie_v34)
    seq_avant = _seq(vraie_v34)
    database.init_db()
    apres = _etat(vraie_v34)
    assert _sql(vraie_v34, "PRAGMA user_version")[0]["user_version"] == database.SCHEMA_VERSION
    assert [t for t in apres["tables"] if t not in TABLES_NEUVES] == avant["tables"]
    assert {t: n for t, n in apres["comptes"].items()
            if t not in TABLES_NEUVES} == avant["comptes"]
    assert apres["comptes"]["jeu_document"] == 0
    # Les lignes, colonnes neuves mises à part, sont celles d'avant — identifiants des
    # collections compris : la reconstruction recopie, elle ne renumérote pas.
    assert apres["lignes"] == avant["lignes"]
    assert set(avant["index"]) <= set(apres["index"])
    assert (apres["vues"], apres["recherche"]) == (avant["vues"], avant["recherche"])
    # Les compteurs des autres tables ne bougent pas.
    assert {t: n for t, n in _seq(vraie_v34).items() if t != "collection"} == seq_avant
    assert _sql(vraie_v34, "PRAGMA foreign_key_check") == []
    assert _sql(vraie_v34, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"


def test_les_colonnes_arrivent_vides_aucun_projet_ne_change_de_nature(vraie_v34):
    database.init_db()
    assert {"bac_a_sable_de", "efface_le", "jeu"} <= set(_colonnes(vraie_v34, "projet"))
    assert _sql(vraie_v34, "SELECT COUNT(*) AS n FROM projet WHERE bac_a_sable_de IS NOT NULL "
                           "OR efface_le IS NOT NULL OR jeu <> 0")[0]["n"] == 0
    # `jeu` est NOT NULL DEFAULT 0 : un projet créé ensuite sans le dire n'est pas le jeu.
    c = sqlite3.connect(vraie_v34)
    pid = c.execute("INSERT INTO projet (nom) VALUES ('Après')").lastrowid
    assert c.execute("SELECT jeu, bac_a_sable_de FROM projet WHERE id = ?",
                     (pid,)).fetchone() == (0, None)
    c.rollback()
    c.close()


def test_le_compteur_des_collections_passe_au_dessus_de_ce_qui_a_ete_nomme(vraie_v34):
    """La 10 n'est plus nommée que par le journal, la 9 par une demande et le journal : ni
    l'une ni l'autre ne revient. Le compteur part de 10, au-dessus de la plus haute qui vit
    (8)."""
    database.init_db()
    assert re.search(r"id\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
                     _sql_de(vraie_v34, "collection"))
    assert _seq(vraie_v34)["collection"] == 10
    c = sqlite3.connect(vraie_v34)
    assert c.execute("INSERT INTO collection (nom) VALUES ('Neuve')").lastrowid == 11
    c.rollback()
    c.close()


def test_la_demande_seule_suffit_a_retenir_un_identifiant(vraie_v34):
    """`_HORS_JOURNAL` mord : effacée du journal, la 10 pourrait revenir — pas la 9, que
    `demande.collection_id` nomme encore. Sans la ligne de `_HORS_JOURNAL`, le compteur
    retomberait à 8 et rendrait la 9 à la collection suivante."""
    _sql(vraie_v34, "DELETE FROM evenement WHERE (cible_table IN ('collection', "
                    "'collection_acces') AND cible_id IN (9, 10)) "
                    "OR json_extract(avant, '$.collection_id') IN (9, 10) "
                    "OR json_extract(apres, '$.collection_id') IN (9, 10)")
    database.init_db()
    assert _seq(vraie_v34)["collection"] == 9


def test_une_charge_seule_suffit_a_retenir_un_identifiant(vraie_v34):
    """La clé `collection_id` des charges mord : sans cible ni demande qui la nomme, la 9
    reste retenue par la charge de la demande déposée vers elle (`apres.collection_id`) et
    par celle de son emploi."""
    _sql(vraie_v34, "DELETE FROM evenement WHERE cible_table IN ('collection', "
                    "'collection_acces') AND cible_id IN (9, 10)")
    _sql(vraie_v34, "UPDATE demande SET collection_id = NULL WHERE collection_id IN (9, 10)")
    assert _sql(vraie_v34, "SELECT COUNT(*) AS n FROM evenement "
                           "WHERE json_extract(apres, '$.collection_id') = 9")[0]["n"] >= 1
    database.init_db()
    assert _seq(vraie_v34)["collection"] == 9


def test_rejouee_la_migration_ne_change_rien(vraie_v34):
    database.init_db()
    etat = (_etat(vraie_v34), _seq(vraie_v34),
            _sql(vraie_v34, "SELECT type, name, sql FROM sqlite_master ORDER BY name"))
    _sql(vraie_v34, "PRAGMA user_version = 34")
    database.init_db()
    assert (_etat(vraie_v34), _seq(vraie_v34),
            _sql(vraie_v34, "SELECT type, name, sql FROM sqlite_master ORDER BY name")) == etat


def test_la_base_migree_sert_toujours(vraie_v34, monkeypatch):
    """Les clés étrangères pointent sur la table reconstruite : supprimer une collection
    emporte ses accès et ses emplois par cascade, comme avant."""
    database.init_db()
    c = database.get_connection()
    try:
        cid = c.execute("SELECT collection_id FROM collection_acces LIMIT 1").fetchone()[0]
        assert c.execute("SELECT COUNT(*) FROM collection_acces WHERE collection_id = ?",
                         (cid,)).fetchone()[0] >= 1
        c.execute("DELETE FROM collection_album WHERE collection_id = ?", (cid,))
        c.execute("DELETE FROM collection WHERE id = ?", (cid,))
        assert c.execute("SELECT COUNT(*) FROM collection_acces WHERE collection_id = ?",
                         (cid,)).fetchone()[0] == 0
        c.rollback()
    finally:
        c.close()
