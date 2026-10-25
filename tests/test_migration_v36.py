"""COL-3, tranche 3b — la migration v36, sur une VRAIE base v35.

La règle de Hugo (2026-10-16, `CLAUDE.md` § Schéma & migrations) : une migration se vérifie
sur une base de la version précédente qui a VÉCU, faite par le code de cette version
(`tools/fabriquer_base_de_version.py f8dfa5c tests/bases/v35-f8dfa5c.sql` — `f8dfa5c`, la
tête de `main` avant la v36, est le dernier état de la v35). Elle porte ce que portaient les
précédentes, et ce que la v36 doit traverser : le JEU des bacs à sable (préparé par son
outil), deux BACS À SABLE — dans celui de Léa, Sam est invité, y a créé une collection et
importé un album —, et une collection créée par un simple MEMBRE d'un projet ordinaire
(Sam, dans Étude B), ce que la v35 laissait faire.

Ce que la v36 apporte (Hugo, 2026-10-21) : `projet.membres_creent_collections`, à 0 —
« non » — pour tout l'existant, bacs à sable et jeu compris. Et rien d'autre : les lignes,
les index, les vues, l'index plein texte, les compteurs, sont ceux d'avant. Ce qui change
est le geste : le membre qui créait ne crée plus, ses collections restent les siennes.
"""
import json
import sqlite3
from pathlib import Path

import pytest

import database
import main
from conftest import ADMIN

BASE_V35 = Path(__file__).resolve().parent / "bases" / "v35-f8dfa5c.sql"
LIGNES = ("albums", "planches", "regions", "annotations", "personnages", "projet",
          "projet_acces", "collection", "collection_acces", "collection_album", "document",
          "copie", "demande", "demande_document", "region_origine", "contribution",
          "tokens", "token_correction", "tags", "domaine", "attribut_dimension",
          "attribut_valeur", "evenement", "activite", "jeu_document")
LEA = {"Remote-User": "lea"}
SAM = {"Remote-User": "sam"}
HUGO = {"Remote-User": "hugo", "Remote-Groups": "bd-admins"}


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
def vraie_v35(tmp_path, monkeypatch):
    """`tests/bases/v35-f8dfa5c.sql`, chargée dans une base du test. Les dossiers d'images
    sont ceux du test, vides."""
    from pipeline import ingest
    db = tmp_path / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V35.read_text(encoding="utf-8"))
    c.close()
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    return db


def _etat(db):
    tables = [r["name"] for r in _sql(
        db, "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE 'recherche_%' ORDER BY name")]
    lignes = {}
    for t in LIGNES:
        lignes[t] = sorted(json.dumps({k: v for k, v in r.items()
                                       if not (t == "projet"
                                               and k == "membres_creent_collections")},
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


def test_la_base_chargee_est_bien_une_v35_qui_a_vecu(vraie_v35):
    """Le décor d'abord : sans lui, les tests suivants passeraient sur une base vide."""
    assert _sql(vraie_v35, "PRAGMA user_version")[0]["user_version"] == 35
    assert "membres_creent_collections" not in {
        c["name"] for c in _sql(vraie_v35, "PRAGMA table_info(projet)")}
    natures = {r["n"]: r["c"] for r in _sql(
        vraie_v35, "SELECT CASE WHEN jeu = 1 THEN 'jeu' WHEN bac_a_sable_de IS NOT NULL "
                   "THEN 'bac' WHEN repli = 1 THEN 'repli' ELSE 'ordinaire' END AS n, "
                   "COUNT(*) AS c FROM projet GROUP BY n")}
    assert natures == {"bac": 2, "jeu": 1, "ordinaire": 1, "repli": 1}
    assert _sql(vraie_v35, "SELECT COUNT(*) AS n FROM jeu_document")[0]["n"] == 2
    # Sam, invité du bac à sable de Léa, y a créé une collection, qu'il possède.
    assert _sql(vraie_v35, "SELECT niveau FROM collection_acces WHERE collection_id = 15 "
                           "AND principal = 'sam'") == [{"niveau": "proprietaire"}]
    # Et Sam, simple MEMBRE d'Étude B, y a créé « Par un membre ».
    assert _sql(vraie_v35, "SELECT role FROM projet_acces WHERE projet_id = 2 "
                           "AND principal = 'sam'") == [{"role": "membre"}]
    assert _sql(vraie_v35, "SELECT nom, projet_id FROM collection WHERE id = 17") == [
        {"nom": "Par un membre", "projet_id": 2}]


def test_une_vraie_base_v35_migre_sans_rien_perdre(vraie_v35):
    avant = _etat(vraie_v35)
    seq_avant = _seq(vraie_v35)
    database.init_db()
    apres = _etat(vraie_v35)
    assert _sql(vraie_v35, "PRAGMA user_version")[0]["user_version"] == database.SCHEMA_VERSION
    assert database.SCHEMA_VERSION == 36
    assert apres == avant
    assert _seq(vraie_v35) == seq_avant
    assert _sql(vraie_v35, "PRAGMA foreign_key_check") == []
    assert _sql(vraie_v35, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"


def test_tout_l_existant_passe_a_non_bacs_a_sable_et_jeu_compris(vraie_v35):
    database.init_db()
    assert _sql(vraie_v35, "SELECT DISTINCT membres_creent_collections AS v FROM projet") == [
        {"v": 0}]
    c = sqlite3.connect(vraie_v35)
    pid = c.execute("INSERT INTO projet (nom) VALUES ('Après')").lastrowid
    assert c.execute("SELECT membres_creent_collections FROM projet WHERE id = ?",
                     (pid,)).fetchone() == (0,)
    c.rollback()
    c.close()


def test_rejouee_la_migration_ne_change_rien(vraie_v35):
    database.init_db()
    etat = (_etat(vraie_v35), _seq(vraie_v35),
            _sql(vraie_v35, "SELECT type, name, sql FROM sqlite_master ORDER BY name"))
    _sql(vraie_v35, "PRAGMA user_version = 35")
    database.init_db()
    assert (_etat(vraie_v35), _seq(vraie_v35),
            _sql(vraie_v35, "SELECT type, name, sql FROM sqlite_master ORDER BY name")) == etat


def test_sur_la_base_migree_le_geste_suit_le_reglage(vraie_v35, monkeypatch):
    """Sam, simple membre d'Étude B, ne crée plus de collection — « Par un membre » reste la
    sienne, il la possède encore. Léa, responsable d'Étude B, crée ; l'administrateur aussi.
    Dans le bac à sable de Léa, Sam, invité, crée comme avant. Léa ouvre le réglage : Sam
    crée."""
    from fastapi.testclient import TestClient
    import autorisation
    monkeypatch.setattr(main, "AUTH_PROXY", True)
    monkeypatch.setattr(autorisation, "AUTH_PROXY", True)
    database.init_db()
    client = TestClient(main.app, headers={main.EN_TETE_REQUETE: "1"})

    def creer(qui, projet, nom):
        return client.post("/api/collections", headers=qui,
                           json={"nom": nom, "projet_id": projet})
    assert creer(SAM, 2, "Encore une").status_code == 403
    assert _sql(vraie_v35, "SELECT niveau FROM collection_acces WHERE collection_id = 17 "
                           "AND principal = 'sam'") == [{"niveau": "proprietaire"}]
    assert creer(LEA, 2, "Par la responsable").status_code == 201
    assert creer(HUGO, 2, "Par l'administrateur").status_code == 201
    assert creer(SAM, 6, "Dans le bac de Léa").status_code == 201
    r = client.put("/api/projets/2/creation-de-collections", headers=LEA,
                   json={"membres": True})
    assert r.status_code == 200, r.text
    assert creer(SAM, 2, "Ouvert par Léa").status_code == 201
