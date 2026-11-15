"""ANN-7, « Une grille dérivée dit d'où elle vient » — la migration v40, sur une VRAIE base
v39.

La règle de Hugo (2026-10-16, `CLAUDE.md` § Schéma & migrations) : une migration se vérifie
sur une base de la version précédente qui a VÉCU. `tests/bases/v39-2cd0d01.sql` est faite par
le code de la production (`2cd0d01`, la tête de `main` avant la v40), ses routes sous trois
comptes : elle porte des grilles de toutes les naissances — importée (Signaux, avec un
brouillon v2), construite au formulaire, la grille de TRAVAIL de chaque projet, celle de
chaque BAC À SABLE —, une grille née du classeur d'une autre AVANT la v40 (« Signaux du
repli » : le classeur ne portait rien), et une grille supprimée en haut de sa table.

Ce que la v40 fait : quatre colonnes sur `grille` — `identifiant`, un UUID pour CHAQUE grille,
et l'origine (`derivee_de_identifiant`, `derivee_de_nom`, `derivee_de_version`), NULL pour
toutes : aucune ne vient d'une autre que la base sache dire —, et l'index unique de
l'identifiant. Rien d'autre ne change.
"""
import json
import sqlite3
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import autorisation
import database
import main
import migration_v40

BASE_V39 = Path(__file__).resolve().parent / "bases" / "v39-2cd0d01.sql"
# Écrites ICI À LA MAIN : le test qui tirerait son attendu de la constante qu'il éprouve en
# serait le miroir.
COLONNES_NEUVES = ["identifiant", "derivee_de_identifiant", "derivee_de_nom",
                   "derivee_de_version"]
ORIGINE = ("derivee_de_identifiant", "derivee_de_nom", "derivee_de_version")
ADMIN = {"Remote-User": "hugo", "Remote-Name": "Hugo", "Remote-Groups": "bd-admins"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _sql(db, q, p=()):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        r = [dict(x) for x in c.execute(q, p)]
        c.commit()
        return r
    finally:
        c.close()


def _faits() -> dict:
    faits = {}
    for ligne in BASE_V39.read_text(encoding="utf-8").splitlines():
        if not ligne.startswith("--"):
            break
        if ligne.startswith("--   ") and " : " in ligne:
            cle, val = ligne[5:].split(" : ", 1)
            faits[cle] = json.loads(val)
    return faits


@pytest.fixture
def vraie_v39(tmp_path, monkeypatch):
    """`tests/bases/v39-2cd0d01.sql`, chargée dans une base du test ; les dossiers d'images
    sont ceux du test, vides."""
    from pipeline import ingest
    db = tmp_path / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V39.read_text(encoding="utf-8"))
    c.close()
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    return db


def _tables(db):
    return [r["name"] for r in _sql(db, "SELECT name FROM sqlite_master WHERE type = 'table' "
                                        "AND name NOT LIKE 'sqlite_%' "
                                        "AND name NOT LIKE 'recherche_%' ORDER BY name")]


def _lignes(db, t):
    return sorted(json.dumps(migration_v40.sans_la_v40(t, r), sort_keys=True,
                             ensure_ascii=False) for r in _sql(db, f'SELECT * FROM "{t}"'))


def _etat(db):
    return {"lignes": {t: _lignes(db, t) for t in _tables(db)},
            "seq": _sql(db, "SELECT name, seq FROM sqlite_sequence ORDER BY name"),
            "index": sorted(r["name"] for r in _sql(
                db, "SELECT name FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")
                if r["name"] not in migration_v40.INDEX_V40)}


def test_la_base_chargee_est_bien_une_v39_qui_a_vecu(vraie_v39):
    """Le décor d'abord : sans lui, les tests suivants passeraient sur une base vide."""
    f = _faits()
    assert _sql(vraie_v39, "PRAGMA user_version")[0]["user_version"] == 39
    cols = [c["name"] for c in _sql(vraie_v39, "PRAGMA table_info(grille)")]
    assert not set(COLONNES_NEUVES) & set(cols)
    # Des grilles de chaque naissance, et une supprimée en haut de sa table.
    assert f["grilles_par_nature"] == {"autre": 3, "bac à sable": 2, "travail": 4}
    assert {"brouillon", "publiee", "vivante"} <= set(f["versions_par_etat"])
    noms = {r["id"]: r["nom"] for r in _sql(vraie_v39, "SELECT id, nom FROM grille")}
    assert noms[f["grille_derivee_avant_v40"]] == "Signaux du repli"
    assert f["grille_supprimee"] not in noms
    assert f["grille_supprimee"] > max(noms)


def test_une_vraie_base_v39_migre_sans_rien_perdre(vraie_v39):
    avant = _etat(vraie_v39)
    grilles = {r["id"] for r in _sql(vraie_v39, "SELECT id FROM grille")}

    database.init_db()

    assert _sql(vraie_v39, "PRAGMA user_version")[0]["user_version"] == 40
    assert database.SCHEMA_VERSION == 40
    # 1. Les quatre colonnes, à la suite de celles d'avant.
    cols = [c["name"] for c in _sql(vraie_v39, "PRAGMA table_info(grille)")]
    assert cols[-4:] == COLONNES_NEUVES
    # 2. Chaque grille a son identifiant, un UUID canonique, unique ; aucune origine —
    #    « Signaux du repli », née du classeur d'une autre avant la v40, comprise.
    lignes = _sql(vraie_v39, "SELECT * FROM grille")
    assert {l["id"] for l in lignes} == grilles
    assert all(str(uuid.UUID(l["identifiant"])) == l["identifiant"] for l in lignes)
    assert len({l["identifiant"] for l in lignes}) == len(lignes)
    assert all(l[c] is None for l in lignes for c in ORIGINE)
    # 3. L'index unique, posé par `_migrate`.
    index = {r["name"]: r["sql"] for r in _sql(
        vraie_v39, "SELECT name, sql FROM sqlite_master WHERE type = 'index'")}
    assert "UNIQUE" in index["idx_grille_identifiant"].upper()
    # 4. Rien d'autre : chaque table, ligne à ligne ; les compteurs ; les autres index.
    assert _etat(vraie_v39) == avant
    assert _sql(vraie_v39, "PRAGMA foreign_key_check") == []
    assert _sql(vraie_v39, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"


def test_rejouee_la_migration_ne_change_aucun_identifiant(vraie_v39):
    database.init_db()
    avant = _sql(vraie_v39, "SELECT id, identifiant FROM grille ORDER BY id")
    _sql(vraie_v39, "PRAGMA user_version = 39")
    database.init_db()
    assert _sql(vraie_v39, "SELECT id, identifiant FROM grille ORDER BY id") == avant


class _Panne(Exception):
    pass


def test_une_panne_entre_les_colonnes_et_les_identifiants_ne_les_perd_pas(vraie_v39,
                                                                        monkeypatch):
    """Les colonnes naissent d'`ALTER`, que le module `sqlite3` valide seul s'il n'y a pas de
    transaction ouverte ; les identifiants d'`UPDATE`. Une migration qui tombe entre les deux
    laisse les colonnes sans identifiants : la relance doit les poser, et non les sauter
    parce que la colonne est là. La connexion de la panne VALIDE chaque `ALTER` dès qu'il
    passe, puis lève sur le premier identifiant posé."""
    class Conn(sqlite3.Connection):
        def execute(self, sql, *a):
            if sql.lstrip().startswith("UPDATE grille SET identifiant"):
                raise _Panne(sql)
            r = super().execute(sql, *a)
            if "ALTER TABLE grille ADD COLUMN" in sql:
                self.commit()
            return r

    vraie = database.get_connection

    def en_panne():
        conn = sqlite3.connect(database.DB_PATH, check_same_thread=False, factory=Conn)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.create_function("cle_tag", 1, database.cle_tag, deterministic=True)
        return conn

    monkeypatch.setattr(database, "get_connection", en_panne)
    with pytest.raises(_Panne):
        database.init_db()
    monkeypatch.setattr(database, "get_connection", vraie)
    assert _sql(vraie_v39, "PRAGMA user_version")[0]["user_version"] == 39
    assert set(COLONNES_NEUVES) <= {c["name"] for c in _sql(vraie_v39,
                                                            "PRAGMA table_info(grille)")}
    database.init_db()
    assert _sql(vraie_v39, "PRAGMA user_version")[0]["user_version"] == 40
    assert _sql(vraie_v39, "SELECT COUNT(*) AS n FROM grille "
                           "WHERE identifiant IS NULL")[0]["n"] == 0


def test_la_base_migree_a_la_forme_d_une_base_neuve(vraie_v39, tmp_path, monkeypatch):
    """`grille`, colonne par colonne : sur l'une les colonnes naissent de l'`ALTER`, sur
    l'autre du `CREATE`. Et une base neuve a son index unique, comme la migrée."""
    database.init_db()
    neuve = tmp_path / "neuve.sqlite"
    c = sqlite3.connect(neuve)
    c.executescript(database.SCHEMA_SQL)
    c.close()

    def forme(db):
        return [(x["name"], x["type"], x["notnull"], x["dflt_value"])
                for x in _sql(db, "PRAGMA table_info(grille)")]
    assert forme(vraie_v39) == forme(neuve)
    initialisee = tmp_path / "initialisee.sqlite"
    monkeypatch.setattr(database, "DB_PATH", initialisee)
    database.init_db()
    assert "idx_grille_identifiant" in {r["name"] for r in _sql(
        initialisee, "SELECT name FROM sqlite_master WHERE type = 'index'")}
    # Le projet de repli d'une base neuve a sa grille de travail, et elle a son identifiant.
    assert _sql(initialisee, "SELECT COUNT(*) AS n FROM grille "
                             "WHERE identifiant IS NULL")[0]["n"] == 0


def test_apres_la_migration_une_grille_d_avant_se_derive(vraie_v39, monkeypatch):
    """Ce que la v40 ouvre, sur la vraie base : le classeur d'une grille d'AVANT porte
    désormais son identifiant, et réimporté dans un autre projet il fait une dérivée."""
    f = _faits()
    database.init_db()
    monkeypatch.setattr(main, "AUTH_PROXY", True)
    monkeypatch.setattr(autorisation, "AUTH_PROXY", True)
    signaux = f["grille"]
    source = _sql(vraie_v39, "SELECT identifiant FROM grille WHERE id = ?",
                  (signaux,))[0]["identifiant"]
    with TestClient(main.app, headers={main.EN_TETE_REQUETE: "1"}) as c:
        r = c.get(f"/api/grilles/{signaux}/versions/1/tableur", headers=ADMIN)
        assert r.status_code == 200, r.text[:300]
        res = c.post(f"/api/projets/{f['projet_repli']}/grilles/import", headers=ADMIN,
                     files={"fichier": ("signaux.xlsx", r.content, XLSX)},
                     data={"nom": "Signaux, après la v40"})
        assert res.status_code == 200, res.text[:500]
        gid = res.json()["grille_id"]
        plan = c.get(f"/api/grilles/{gid}/versions/1", headers=ADMIN).json()
    assert plan["grille"]["derivee_de"] == {"nom": "Signaux", "version": 1}
    ligne = _sql(vraie_v39, "SELECT * FROM grille WHERE id = ?", (gid,))[0]
    assert ligne["derivee_de_identifiant"] == source != ligne["identifiant"]
    # « Signaux du repli », née avant, ne gagne rien.
    assert _sql(vraie_v39, "SELECT derivee_de_identifiant AS o FROM grille WHERE id = ?",
                (f["grille_derivee_avant_v40"],)) == [{"o": None}]
