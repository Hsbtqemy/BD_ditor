"""COL-3, v30 — des identifiants qui ne reviennent jamais (Hugo, 2026-10-15).

`albums`, `planches`, `regions` et `personnages` portent `AUTOINCREMENT`. Sans lui, SQLite
rendait au suivant l'identifiant du dernier détruit, n'importe où : le journal, qui
survit à sa cible et la désigne par son identifiant, mêlait deux objets — la règle de
suppression lisait l'acte d'un ancien album comme un travail sur une région neuve, et
Ctrl+Z écrivait à travers le cloisonnement.

Une base d'avant la v30 est RECONSTRUITE (`database._reconstruire_avec_autoincrement`),
et son compteur amorcé au-dessus de tout identifiant que le journal a jamais nommé, par
sa cible ou dans ses charges. C'est une migration à sens unique : chaque source du
journal est jouée seule, pour qu'en oublier une fasse tomber un test ; puis ce que la
reconstruction ne doit pas toucher — lignes, index, vues, recherche, tokens, clés.
"""
import json
import re
import sqlite3
from pathlib import Path

import pytest

import database
import main

TABLES = ("albums", "planches", "regions", "personnages")


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


def _sans_autoincrement(db, version=29):
    """Défait la v30 sur ces quatre tables : la forme d'une base v29, identifiants rendus
    par SQLite. Reconstruction inverse, clés étrangères coupées (connexion brute), vues
    retirées puis remises — `ALTER TABLE … RENAME` refuse un schéma dont une vue désigne
    une table absente. `version=None` laisse `user_version` tel quel : la numérotation
    d'avant, sur une base qui ne sera pas migrée de nouveau (`test_undo_cloisonnement`)."""
    c = sqlite3.connect(db)
    for (vue,) in c.execute("SELECT name FROM sqlite_master WHERE type = 'view'").fetchall():
        c.execute(f'DROP VIEW "{vue}"')
    for t in TABLES:
        sql = c.execute("SELECT sql FROM sqlite_master WHERE name = ?", (t,)).fetchone()[0]
        index = [s for (s,) in c.execute("SELECT sql FROM sqlite_master WHERE type = 'index' "
                                         "AND tbl_name = ? AND sql IS NOT NULL", (t,))]
        vieux = re.sub(r"PRIMARY KEY AUTOINCREMENT", "PRIMARY KEY", sql, count=1)
        vieux = re.sub(r"^CREATE TABLE\s+(IF NOT EXISTS\s+)?\"?" + t + r"\"?\s*\(",
                       f"CREATE TABLE {t}__v29 (", vieux, count=1)
        cols = ", ".join(f'"{x[1]}"' for x in c.execute(f"PRAGMA table_info({t})"))
        c.execute(vieux)
        c.execute(f"INSERT INTO {t}__v29 ({cols}) SELECT {cols} FROM {t}")
        c.execute(f"DROP TABLE {t}")
        c.execute(f"ALTER TABLE {t}__v29 RENAME TO {t}")
        for s in index:
            c.execute(s)
        c.execute("DELETE FROM sqlite_sequence WHERE name = ?", (t,))
    c.executescript(database._VIEWS_SQL)
    if version is not None:
        c.execute(f"PRAGMA user_version = {version}")
    c.commit()
    c.close()
    for t in TABLES:
        assert "AUTOINCREMENT" not in _sql(db, "SELECT sql FROM sqlite_master WHERE name = ?",
                                           (t,))[0]["sql"].upper()


@pytest.fixture
def base_v29(tmp_path, monkeypatch):
    """Une base v29 qui a vécu un peu : un album, une planche, une case et sa bulle, un
    personnage, un token et sa ligne de recherche. Rien au journal : chaque test y pose
    ce qu'il mesure.

    Les dossiers d'images sont ceux du test, VIDES : la migration lit `album_N` sur le
    disque, et ceux du dépôt — où l'on a peut-être importé pour de vrai — ne sont pas les
    siens."""
    from pipeline import ingest
    db = tmp_path / "v29.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    database.init_db()
    _sans_autoincrement(db)
    for q in ("INSERT INTO albums (id, titre) VALUES (1, 'Un')",
              "INSERT INTO planches (id, album_id, numero, chemin_web) VALUES (1, 1, 1, 'x')",
              "INSERT INTO regions (id, planche_id, type) VALUES (1, 1, 'case')",
              "INSERT INTO regions (id, planche_id, parent_id, type, ocr_texte) "
              "VALUES (2, 1, 1, 'bulle', 'OTAGE')",
              "INSERT INTO personnages (id, nom) VALUES (1, 'Tintin')",
              "INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (2, 1)",
              "INSERT INTO tokens (region_id, ordre, texte, lemme) VALUES (2, 0, 'OTAGE', 'otage')",
              "INSERT INTO recherche (region_id, ocr_texte) VALUES (2, 'OTAGE')"):
        _sql(db, q)
    return db


def _acte(db, type_, cible_table, cible_id, avant=None, apres=None):
    _sql(db, "INSERT INTO evenement (type, agent, agent_type, cible_table, cible_id, avant, "
             "apres) VALUES (?, 'quelqu', 'humain', ?, ?, ?, ?)",
         (type_, cible_table, cible_id, None if avant is None else json.dumps(avant),
          None if apres is None else json.dumps(apres)))


# Chaque façon dont le journal nomme un identifiant, seule, et le nombre qu'elle nomme :
# au-dessus des survivants (1 ou 2), et distinct des autres pour qu'aucune ne passe grâce
# à sa voisine.
SOURCES = {
    "la cible d'un acte sur une région": (
        "regions", 50, ("suppression", "regions", 50, None, None)),
    "un enfant dans l'instantané d'une région supprimée": (
        "regions", 60, ("suppression", "regions", 2, {"id": 2, "enfants": [{"id": 60}]},
                        None)),
    "region_id dans une charge": (
        "regions", 70, ("modification", "token_correction", 1, None, {"region_id": 70})),
    "parent_id dans une charge": (
        "regions", 75, ("creation", "regions", 2, None, {"parent_id": 75})),
    "la cible d'un locuteur": (
        "regions", 80, ("lien", "bulle_locuteur", 80, None, {"personnage_id": 1})),
    "la cible d'une validation de planche": (
        "planches", 40, ("validation", "planches", 40, None, {"validee": True})),
    "planche_id dans l'instantané d'une région": (
        "planches", 45, ("suppression", "regions", 2, {"id": 2, "planche_id": 45}, None)),
    "l'objet planche d'un scan retiré": (
        "planches", 47, ("modification", "document", 1, {"album_id": 1,
                                                         "planche": {"id": 47, "numero": 3}},
                         None)),
    "album_id dans une charge": (
        "albums", 30, ("lien", "collection_album", 1, None, {"album_id": 30})),
    "personnage_id dans une charge": (
        "personnages", 20, ("delien", "bulle_locuteur", 2, {"personnage_id": 20}, None)),
}


# Le journal A3, c'est `activite` ET `evenement` (relecture croisée) : une passe
# automatique dont rien n'a changé — un OCR sans texte à poser — ne laisse aucun événement,
# et sa planche n'est nommée que par la PORTÉE de son activité. Les paramètres sont lus
# aussi, par prudence.
SOURCES_ACTIVITE = {
    "planche_id dans la portée d'une activité": ("planches", 52, "portee",
                                                 {"planche_id": 52}),
    "album_id dans la portée d'une activité": ("albums", 33, "portee", {"album_id": 33}),
    "region_id dans les paramètres d'une activité": ("regions", 85, "params",
                                                     {"region_id": 85}),
}


@pytest.mark.parametrize("source", sorted(SOURCES_ACTIVITE))
def test_le_compteur_part_au_dessus_de_ce_que_nomme_une_activite(base_v29, source):
    table, haut, colonne, charge = SOURCES_ACTIVITE[source]
    _sql(base_v29, f"INSERT INTO activite (type, agent, agent_type, {colonne}) "
                   "VALUES ('ocr', 'easyocr', 'moteur', ?)", (json.dumps(charge),))
    database.init_db()
    assert _seq(base_v29)[table] == haut, _seq(base_v29)


def test_le_compteur_des_albums_part_au_dessus_de_leurs_dossiers(base_v29, tmp_path):
    """Relecture croisée : une base v29 ne nomme aucun album dans son journal, et l'album
    détruit en haut revenait — dans `corpus/album_N` qu'il avait laissé. Le compteur part
    donc AU-DESSUS du plus grand `album_N` présent dans les deux dossiers d'images ; un nom
    qui n'est pas exactement `album_<nombre>`, ou un fichier, n'y compte pas."""
    (tmp_path / "corpus" / "album_9").mkdir(parents=True)
    (tmp_path / "derivatives" / "album_12").mkdir(parents=True)
    (tmp_path / "corpus" / "album_40.zip").write_bytes(b"x")
    (tmp_path / "corpus" / "album_50.ancien").mkdir()
    (tmp_path / "corpus" / "album_x").mkdir()
    database.init_db()
    assert _seq(base_v29)["albums"] == 12, _seq(base_v29)


def test_sans_dossier_d_images_la_migration_passe(base_v29, tmp_path):
    """Une instance qui n'a encore rien importé n'a pas de `corpus/` : rien à lire."""
    assert not (tmp_path / "corpus").exists()
    database.init_db()
    assert _seq(base_v29)["albums"] == 1


def test_une_activite_illisible_ne_fait_pas_echouer_la_migration(base_v29):
    _sql(base_v29, "INSERT INTO activite (type, agent_type, portee, params) "
                   "VALUES ('ocr', 'moteur', '{pas du json', 'non plus')")
    database.init_db()
    assert _sql(base_v29, "PRAGMA user_version")[0]["user_version"] \
        == database.SCHEMA_VERSION


@pytest.mark.parametrize("source", sorted(SOURCES))
def test_le_compteur_part_au_dessus_de_ce_que_le_journal_nomme(base_v29, source):
    table, haut, acte = SOURCES[source]
    _acte(base_v29, *acte)
    database.init_db()                                    # upgrade réel v29 → v30
    assert _sql(base_v29, "PRAGMA user_version")[0]["user_version"] \
        == database.SCHEMA_VERSION
    assert _seq(base_v29)[table] == haut, _seq(base_v29)
    # Et l'identifiant suivant le dépasse : rendu par SQLite, pas par le test.
    c = sqlite3.connect(base_v29)
    neuf = {"albums": "INSERT INTO albums (titre) VALUES ('n')",
            "planches": "INSERT INTO planches (album_id, numero, chemin_web) VALUES (1, 9, 'x')",
            "regions": "INSERT INTO regions (planche_id, type) VALUES (1, 'case')",
            "personnages": "INSERT INTO personnages (nom) VALUES ('n')"}[table]
    assert c.execute(neuf).lastrowid == haut + 1
    c.rollback()
    c.close()


def test_sans_journal_le_compteur_suit_les_survivants(base_v29):
    database.init_db()
    assert {t: _seq(base_v29)[t] for t in TABLES} == {"albums": 1, "planches": 1,
                                                       "regions": 2, "personnages": 1}


def test_une_charge_illisible_ne_fait_pas_echouer_la_migration(base_v29):
    """Une charge qui n'est pas du JSON est sautée : un acte mal écrit hier ne doit pas
    fermer l'instance au démarrage."""
    _sql(base_v29, "INSERT INTO evenement (type, agent_type, cible_table, cible_id, avant) "
                   "VALUES ('modification', 'humain', 'regions', 9, '{pas du json')")
    database.init_db()
    assert _seq(base_v29)["regions"] == 9


def test_la_reconstruction_ne_perd_rien(base_v29):
    avant_index = sorted(r["sql"] for r in _sql(
        base_v29, "SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL"))
    avant_vues = sorted(r["name"] for r in _sql(
        base_v29, "SELECT name FROM sqlite_master WHERE type = 'view'"))
    database.init_db()
    for t in TABLES:
        assert "AUTOINCREMENT" in _sql(base_v29, "SELECT sql FROM sqlite_master WHERE name = ?",
                                       (t,))[0]["sql"].upper()
    assert [r["id"] for r in _sql(base_v29, "SELECT id FROM regions ORDER BY id")] == [1, 2]
    assert _sql(base_v29, "SELECT parent_id FROM regions WHERE id = 2")[0]["parent_id"] == 1
    assert _sql(base_v29, "SELECT personnage_id FROM bulle_locuteur") == [{"personnage_id": 1}]
    assert len(_sql(base_v29, "SELECT 1 FROM tokens_effectifs")) == 1
    assert _sql(base_v29, "SELECT region_id FROM recherche WHERE recherche MATCH 'otage'") \
        == [{"region_id": 2}]
    assert _sql(base_v29, "PRAGMA foreign_key_check") == []
    assert _sql(base_v29, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"
    apres_index = sorted(r["sql"] for r in _sql(
        base_v29, "SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL"))
    assert apres_index == avant_index
    assert sorted(r["name"] for r in _sql(
        base_v29, "SELECT name FROM sqlite_master WHERE type = 'view'")) == avant_vues
    assert not _sql(base_v29, "SELECT name FROM sqlite_master WHERE name LIKE '%__v30'")
    assert not [n for n in _seq(base_v29) if "__v30" in n]
    # Les clés étrangères sont rendues actives : la cascade vit encore.
    with database.connect() as c:
        c.execute("DELETE FROM albums WHERE id = 1")
    assert _sql(base_v29, "SELECT COUNT(*) AS n FROM regions")[0]["n"] == 0


def test_rejouee_elle_ne_change_rien(base_v29):
    """Des tests ramènent `user_version` en arrière sur une base déjà migrée : la
    reconstruction ne repasse pas sur une table qui porte déjà AUTOINCREMENT, et le
    compteur ne bouge pas."""
    _acte(base_v29, "suppression", "regions", 50)
    database.init_db()
    schema = _sql(base_v29, "SELECT type, name, sql FROM sqlite_master ORDER BY name")
    seq = _seq(base_v29)
    _sql(base_v29, "PRAGMA user_version = 29")
    database.init_db()
    assert _sql(base_v29, "SELECT type, name, sql FROM sqlite_master ORDER BY name") == schema
    assert _seq(base_v29) == seq
    assert _sql(base_v29, "PRAGMA user_version")[0]["user_version"] \
        == database.SCHEMA_VERSION


def test_une_faute_de_cle_deja_la_ne_ferme_pas_l_instance(base_v29):
    """Une ligne orpheline écrite clés coupées, AVANT la migration, n'est pas une faute de
    la reconstruction : la base migre, et la faute reste ce qu'elle était."""
    _sql(base_v29, "INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (1, 999)")
    avant = _sql(base_v29, "PRAGMA foreign_key_check")
    assert avant
    database.init_db()
    assert _sql(base_v29, "PRAGMA user_version")[0]["user_version"] \
        == database.SCHEMA_VERSION
    assert _sql(base_v29, "PRAGMA foreign_key_check") == avant


def test_une_copie_qui_perdrait_une_ligne_defait_tout(base_v29, monkeypatch):
    """Le contrôle des fautes de clé NEUVES (relecture croisée, mutant M17 qui survivait) :
    si la copie d'une table perdait une ligne — ici la planche 1, dont dépendent deux
    régions —, la reconstruction lève et défait TOUT. La base reste en v29, sans
    AUTOINCREMENT, ses lignes intactes ; aucune table intermédiaire ne reste."""
    copier = database._copier_lignes

    def copie_qui_perd(conn, table, colonnes):
        copier(conn, table, colonnes)
        if table == "planches":
            conn.execute("DELETE FROM planches__v30 WHERE id = 1")
    monkeypatch.setattr(database, "_copier_lignes", copie_qui_perd)
    with pytest.raises(RuntimeError, match="orphelines"):
        database.init_db()
    assert _sql(base_v29, "PRAGMA user_version")[0]["user_version"] == 29
    for t in TABLES:
        assert "AUTOINCREMENT" not in _sql(
            base_v29, "SELECT sql FROM sqlite_master WHERE name = ?", (t,))[0]["sql"].upper()
    assert _sql(base_v29, "SELECT id FROM planches") == [{"id": 1}]
    assert not _sql(base_v29, "SELECT name FROM sqlite_master WHERE name LIKE '%__v30'")


# --------------------------------------------------------------------------- #
# Une VRAIE base v29, faite par le code de 10a3a90 (relecture croisée)
# --------------------------------------------------------------------------- #
BASE_V29 = Path(__file__).resolve().parent / "bases" / "v29-10a3a90.sql"


@pytest.fixture
def vraie_v29(tmp_path, monkeypatch):
    """`tests/bases/v29-10a3a90.sql` : trois comptes, quatre albums dont le dernier
    détruit, des planches, des cases et des bulles, du texte et ses tokens, une
    annotation, un locuteur, une présence, un attribut, une validation, un Ctrl+Z, une
    passe automatique sans effet — et en haut de chaque table, une destruction. Chargée
    dans une base du test, rouverte (la table plein texte se recrée à la lecture)."""
    from pipeline import ingest
    db = tmp_path / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V29.read_text(encoding="utf-8"))
    c.close()
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    return db


def _etat(db):
    tables = [r["name"] for r in _sql(
        db, "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE 'recherche_%' ORDER BY name")]
    return {
        "comptes": {t: _sql(db, f'SELECT COUNT(*) AS n FROM "{t}"')[0]["n"] for t in tables},
        "lignes": {t: _sql(db, f"SELECT * FROM {t} ORDER BY id") for t in TABLES},
        "index": sorted(r["sql"] for r in _sql(
            db, "SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")),
        # `releves_effectifs` naît de la v37 (ANN-7) : une vue se recrée à chaque démarrage,
        # sans données, et la base d'avant ne la porte pas.
        "vues": sorted(r["name"] for r in _sql(
            db, "SELECT name FROM sqlite_master WHERE type = 'view'")
            if r["name"] != "releves_effectifs"),
        "recherche": sorted(r["region_id"] for r in _sql(
            db, "SELECT region_id FROM recherche WHERE recherche MATCH 'otage'")),
        "tokens": _sql(db, "SELECT COUNT(*) AS n FROM tokens_effectifs")[0]["n"],
    }


def test_une_vraie_base_v29_migre_sans_rien_perdre(vraie_v29, tmp_path):
    """L'album 4 a été détruit en v29 ; son dossier d'images est laissé là (une
    destruction dont le ménage a échoué). La planche 8 n'est nommée, en dehors des
    instantanés, que par la portée d'une activité ; la région 16 et le personnage 3 par
    le journal. Rien de ce qui vit ne bouge, et aucun de ces identifiants ne revient."""
    assert _sql(vraie_v29, "PRAGMA user_version")[0]["user_version"] == 29
    (tmp_path / "corpus" / "album_4").mkdir(parents=True)
    (tmp_path / "corpus" / "album_4" / "planche_0001.png").write_bytes(b"ANCIEN")
    avant = _etat(vraie_v29)
    assert avant["recherche"] and avant["tokens"], "la base chargée n'a rien à comparer"
    database.init_db()
    apres = _etat(vraie_v29)
    # La v31 (COL-3, tranche 3) passe aussi, et pose la provenance de chaque copie.
    neuves = {"document", "demande", "demande_document", "copie"}
    # La v32 (COL-3, tranche 3b) aussi : `region_origine`, vide.
    neuves |= {"region_origine"}
    # La v35 (COL-4) aussi : `jeu_document`, vide.
    neuves |= {"jeu_document"}
    # La v36 (COL-3, tranche 3b) aussi : `retrait_vu` et `geste_sur_copie`, vides.
    neuves |= {"retrait_vu", "geste_sur_copie"}
    # La v37 (ANN-7, tranche 1) aussi : seize tables neuves, vides, et `regions.nom`.
    neuves |= set(database.TABLES_DES_GRILLES)
    # Et la base NEUVE du projet de repli (D10 ; Hugo, 2026-10-17) : une collection de plus.
    assert apres["comptes"]["collection"] == avant["comptes"]["collection"] + 1
    neuves |= {"collection"}
    assert {t: n for t, n in apres["comptes"].items() if t not in neuves} \
        == {t: n for t, n in avant["comptes"].items() if t not in neuves}
    assert apres["comptes"]["document"] == avant["comptes"]["albums"]
    for t in TABLES:
        retire = {"albums": ("document_id", "projet_id", "tome", "lieu_masters"),
                  "planches": ("master_origine",),
                  "personnages": ("bac_a_sable_id",), "tags": ("espace",),
                  "regions": ("nom",)}.get(t, ())
        assert [{k: v for k, v in r.items() if k not in retire} for r in apres["lignes"][t]] \
            == avant["lignes"][t], t
    assert set(avant["index"]) <= set(apres["index"])
    assert (apres["vues"], apres["recherche"], apres["tokens"]) == \
        (avant["vues"], avant["recherche"], avant["tokens"])
    assert _sql(vraie_v29, "PRAGMA foreign_key_check") == []
    assert _sql(vraie_v29, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"
    assert _sql(vraie_v29, "PRAGMA user_version")[0]["user_version"] \
        == database.SCHEMA_VERSION
    assert {t: _seq(vraie_v29)[t] for t in TABLES} == \
        {"albums": 4, "planches": 8, "regions": 16, "personnages": 3}


def test_une_table_de_forme_inattendue_arrete_tout_avant_de_toucher(base_v29):
    """Une table sans `id INTEGER PRIMARY KEY` ne peut pas recevoir AUTOINCREMENT : la
    migration s'arrête en le disant, AVANT d'avoir reconstruit quoi que ce soit."""
    c = sqlite3.connect(base_v29)
    for (vue,) in c.execute("SELECT name FROM sqlite_master WHERE type = 'view'").fetchall():
        c.execute(f'DROP VIEW "{vue}"')
    c.execute("DROP TABLE personnages")
    c.execute("CREATE TABLE personnages (ident INTEGER PRIMARY KEY, nom TEXT)")
    c.commit()
    c.close()
    with pytest.raises(RuntimeError, match="personnages"):
        database.init_db()
    assert _sql(base_v29, "PRAGMA user_version")[0]["user_version"] == 29
    for t in ("albums", "planches", "regions"):
        assert "AUTOINCREMENT" not in _sql(
            base_v29, "SELECT sql FROM sqlite_master WHERE name = ?", (t,))[0]["sql"].upper()


# --------------------------------------------------------------------------- #
# Un dossier d'images déjà là n'est jamais repris par un album neuf (relecture croisée)
# --------------------------------------------------------------------------- #
def test_un_album_neuf_ne_reprend_jamais_le_dossier_d_un_autre(client, data_dir, db_path,
                                                                png_bytes, caplog):
    """Un identifiant d'album pouvait revenir — d'avant la v30, ou rendu par une
    transaction défaite — et retrouver `corpus/album_N` et `derivatives/album_N` laissés par
    l'album détruit : ses planches se mêlaient aux images d'un autre. À la naissance d'un
    album, un tel dossier est MIS DE CÔTÉ — renommé, daté, à côté, jamais effacé — et le
    journal du serveur le dit."""
    suivant = (_sql(db_path, "SELECT seq FROM sqlite_sequence WHERE name = 'albums'")
               or [{"seq": 0}])[0]["seq"] + 1
    for racine in ("corpus", "derivatives"):
        d = data_dir / racine / f"album_{suivant}"
        d.mkdir(parents=True)
        (d / "planche_0001.png").write_bytes(b"IMAGE D'UN AUTRE ALBUM")
    with caplog.at_level("WARNING", logger="bd_annotator"):
        aid = client.post("/api/albums", json={"titre": "Neuf"}).json()["id"]
    assert aid == suivant
    for racine in ("corpus", "derivatives"):
        assert not (data_dir / racine / f"album_{aid}").exists(), racine
        ecartes = sorted((data_dir / racine).glob(f"album_{aid}.ecarte-*"))
        assert len(ecartes) == 1, (racine, ecartes)
        assert (ecartes[0] / "planche_0001.png").read_bytes() == b"IMAGE D'UN AUTRE ALBUM"
    assert sum(f"album_{aid}" in r.getMessage() and "mis de côté" in r.getMessage()
               for r in caplog.records) == 2
    # L'album neuf écrit dans un dossier neuf.
    r = client.post(f"/api/albums/{aid}/import",
                    files={"file": ("p.png", png_bytes, "image/png")})
    assert r.status_code == 201, r.text
    assert [f.name for f in (data_dir / "corpus" / f"album_{aid}").iterdir()] \
        == ["planche_0001.jpg"]                 # la copie de travail (IMG-1)
    assert (data_dir / "corpus" / f"album_{aid}" / "planche_0001.jpg").read_bytes() \
        != b"IMAGE D'UN AUTRE ALBUM"


def test_un_dossier_qui_ne_se_met_pas_de_cote_fait_sauter_le_numero(client, data_dir, db_path,
                                                                    png_bytes, monkeypatch,
                                                                    caplog):
    """Vérification de la relecture : si le dossier trouvé ne peut PAS être mis de côté —
    un fichier verrouillé sous Windows, des droits sur `corpus/` —, la création répondait
    500, le compteur revenait en arrière, et chaque essai retombait sur le même numéro :
    plus aucun album ne naissait. Le numéro est désormais SAUTÉ : l'album naît au suivant,
    dans un dossier vide, le dossier resté n'est pas touché, et le journal du serveur le dit
    avec son chemin. Le compteur a avancé pour de bon : la création suivante ne retombe pas
    dessus."""
    import pathlib
    suivant = (_sql(db_path, "SELECT seq FROM sqlite_sequence WHERE name = 'albums'")
               or [{"seq": 0}])[0]["seq"] + 1
    reste = data_dir / "corpus" / f"album_{suivant}"
    reste.mkdir(parents=True)
    (reste / "planche_0001.png").write_bytes(b"IMAGE D'UN AUTRE ALBUM")
    renommer = pathlib.Path.rename

    def rename_verrouille(self, cible):
        if self.name == f"album_{suivant}":
            raise PermissionError(13, "Le fichier est utilisé par un autre processus",
                                  str(self))
        return renommer(self, cible)
    monkeypatch.setattr(pathlib.Path, "rename", rename_verrouille)

    with caplog.at_level("WARNING", logger="bd_annotator"):
        r = client.post("/api/albums", json={"titre": "Neuf"})
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    assert aid == suivant + 1
    assert _sql(db_path, "SELECT 1 FROM albums WHERE id = ?", (suivant,)) == []
    assert (reste / "planche_0001.png").read_bytes() == b"IMAGE D'UN AUTRE ALBUM"
    assert not (data_dir / "corpus" / f"album_{aid}").exists()
    messages = [x.getMessage() for x in caplog.records if x.levelname == "WARNING"]
    assert any(str(reste) in m and "sauté" in m for m in messages), messages
    # L'album neuf écrit dans un dossier à lui ; la création suivante passe au-delà.
    r = client.post(f"/api/albums/{aid}/import",
                    files={"file": ("p.png", png_bytes, "image/png")})
    assert r.status_code == 201, r.text
    assert [f.name for f in (data_dir / "corpus" / f"album_{aid}").iterdir()] \
        == ["planche_0001.jpg"]                 # la copie de travail (IMG-1)
    assert client.post("/api/albums", json={"titre": "Encore"}).json()["id"] == aid + 1


def test_le_numero_saute_le_reste_meme_si_la_creation_echoue_ensuite(client, data_dir,
                                                                     db_path, monkeypatch):
    """L'avance du compteur est validée AVANT la suite de la requête : une création qui
    échoue plus loin (ici en écrivant la naissance du document) ne la défait pas, et l'essai
    suivant ne retente pas le dossier verrouillé — il n'est essayé qu'une fois."""
    import pathlib

    from fastapi.testclient import TestClient
    suivant = (_sql(db_path, "SELECT seq FROM sqlite_sequence WHERE name = 'albums'")
               or [{"seq": 0}])[0]["seq"] + 1
    (data_dir / "corpus" / f"album_{suivant}").mkdir(parents=True)
    renommer, essais = pathlib.Path.rename, []

    def rename_verrouille(self, cible):
        if self.name == f"album_{suivant}":
            essais.append(self)
            raise PermissionError(13, "verrouillé", str(self))
        return renommer(self, cible)
    monkeypatch.setattr(pathlib.Path, "rename", rename_verrouille)
    naissance = main._journaliser_naissance

    def panne(*a, **k):
        raise RuntimeError("panne après le saut")
    monkeypatch.setattr(main, "_journaliser_naissance", panne)
    sans_relance = TestClient(main.app, headers={main.EN_TETE_REQUETE: "1"},
                              raise_server_exceptions=False)
    assert sans_relance.post("/api/albums", json={"titre": "Raté"}).status_code == 500
    monkeypatch.setattr(main, "_journaliser_naissance", naissance)
    r = client.post("/api/albums", json={"titre": "Neuf"})
    assert r.status_code == 201, r.text
    assert r.json()["id"] == suivant + 1
    assert len(essais) == 1, essais


def test_un_dossier_deja_mis_de_cote_ne_l_est_pas_par_dessus(data_dir, monkeypatch):
    """Deux mises de côté la même seconde ne s'écrasent pas : la seconde prend un suffixe."""
    from pipeline import ingest
    for _ in range(2):
        d = data_dir / "corpus" / "album_7"
        d.mkdir(parents=True)
        (d / "x").write_text("x")
        ingest.ecarter_dossiers_d_album(7)
    assert len(list((data_dir / "corpus").glob("album_7.ecarte-*"))) == 2


# --------------------------------------------------------------------------- #
# Sur une base neuve, par les routes : un identifiant détruit ne revient pas
# --------------------------------------------------------------------------- #
def test_une_base_neuve_ne_rend_aucun_identifiant(client, png_bytes):
    album = client.post("/api/albums", json={"titre": "A"}).json()["id"]
    planche = client.post(f"/api/albums/{album}/import",
                          files={"file": ("p.png", png_bytes, "image/png")}).json()["id"]

    def region():
        r = client.post(f"/api/planches/{planche}/regions",
                        json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    r1 = region()
    assert client.delete(f"/api/regions/{r1}").status_code == 204
    assert region() > r1

    p2 = client.post(f"/api/albums/{album}/import",
                     files={"file": ("q.png", png_bytes, "image/png")}).json()["id"]
    assert client.delete(f"/api/planches/{p2}").status_code == 204
    assert client.post(f"/api/albums/{album}/import",
                       files={"file": ("r.png", png_bytes, "image/png")}).json()["id"] > p2

    a2 = client.post("/api/albums", json={"titre": "B"}).json()["id"]
    assert client.delete(f"/api/albums/{a2}").status_code == 204
    assert client.post("/api/albums", json={"titre": "C"}).json()["id"] > a2

    h = client.post("/api/personnages", json={"nom": "Haddock"}).json()["id"]
    assert client.delete(f"/api/personnages/{h}").status_code == 204
    assert client.post("/api/personnages", json={"nom": "Milou"}).json()["id"] > h
