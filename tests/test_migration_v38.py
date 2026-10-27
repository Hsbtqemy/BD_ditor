"""COL-3, tranche 3c — la migration v38, sur une VRAIE base v37.

La règle de Hugo (2026-10-16, `CLAUDE.md` § Schéma & migrations) : une migration se vérifie
sur une base de la version précédente qui a VÉCU, faite par le code de cette version
(`tools/fabriquer_base_de_version.py f6f53ed tests/bases/v37-f6f53ed.sql` — `f6f53ed`, la
tête de `dev` au début de la 3c, est le dernier état de la v37 ; `tests/test_base_v37.py`
dit ce qu'elle porte).

Ce que la v38 apporte (cadrage de la 3c, § La migration v38 ; F2, F5, Q11, Hugo,
2026-10-26) :
1. `demande.planche_id` et `demande.planche_numero`, NULL pour tout l'existant ;
2. chaque accès de collection HORS projet fait entrer son principal dans le projet de la
   collection, au rôle `membre` — la référence exacte, ni bac à sable ni jeu ; le repli
   compris (une collection sans `projet_id` y est) ;
3. `geste_sur_copie` disparaît.
Et rien d'autre : les lignes, les compteurs, les demandes en attente sont ceux d'avant.
"""
import json
import sqlite3
from pathlib import Path

import pytest

import database
import main

BASE_V37 = Path(__file__).resolve().parent / "bases" / "v37-f6f53ed.sql"
# Toutes les tables qui portent des lignes, sauf celles que la v38 change : écrites ICI À LA
# MAIN, pour que le test ne soit pas le miroir d'une constante.
LIGNES = ("albums", "planches", "regions", "annotations", "personnages", "projet",
          "collection", "collection_acces", "collection_album", "document", "copie",
          "demande_document", "region_origine", "contribution", "tokens",
          "token_correction", "tags", "domaine", "attribut_dimension", "attribut_valeur",
          "evenement", "activite", "jeu_document", "region_attribut", "bulle_locuteur",
          "personnage_presence", "grille", "grille_version", "projet_grille", "releve",
          "passe", "doute", "doute_message", "retrait_vu", "utilisateur")
# Le projet d'une collection : NULL se lit « le projet de repli » (`database.sql_projet_de`),
# écrit ici à la main pour la même raison.
_PROJET_DE = "COALESCE(col.projet_id, (SELECT id FROM projet WHERE repli = 1))"
_ISOLE = "(p.bac_a_sable_de IS NOT NULL OR p.jeu = 1)"


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
    for ligne in BASE_V37.read_text(encoding="utf-8").splitlines():
        if not ligne.startswith("--"):
            break
        if ligne.startswith("--   ") and " : " in ligne:
            cle, val = ligne[5:].split(" : ", 1)
            faits[cle] = json.loads(val)
    return faits


@pytest.fixture
def vraie_v37(tmp_path, monkeypatch):
    """`tests/bases/v37-f6f53ed.sql`, chargée dans une base du test ; les dossiers d'images
    sont ceux du test, vides."""
    from pipeline import ingest
    db = tmp_path / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V37.read_text(encoding="utf-8"))
    c.close()
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    return db


def _hors_projet(db):
    """Les accès de collection dont le principal n'est pas du projet de la collection, hors
    projets isolés : `{(projet, genre, principal)}` — TOUS ceux de la base, et non les seuls
    que le parcours a semés (le repli en portait déjà : note du commit 0)."""
    return {(r["projet"], r["genre"], r["principal"]) for r in _sql(
        db, f"SELECT DISTINCT {_PROJET_DE} AS projet, ca.genre, ca.principal "
            f"FROM collection_acces ca JOIN collection col ON col.id = ca.collection_id "
            f"JOIN projet p ON p.id = {_PROJET_DE} WHERE NOT {_ISOLE} AND NOT EXISTS ("
            f"SELECT 1 FROM projet_acces pa WHERE pa.projet_id = {_PROJET_DE} "
            f"AND pa.genre = ca.genre AND pa.principal = ca.principal)")}


def _membres(db):
    return {(r["projet_id"], r["genre"], r["principal"]): r["role"]
            for r in _sql(db, "SELECT projet_id, genre, principal, role FROM projet_acces")}


def _lignes(db, t, sans=()):
    return sorted(json.dumps({k: v for k, v in r.items() if k not in sans}, sort_keys=True,
                             ensure_ascii=False) for r in _sql(db, f'SELECT * FROM "{t}"'))


def _seq(db):
    return {r["name"]: r["seq"] for r in _sql(db, "SELECT name, seq FROM sqlite_sequence")}


def _poser_dans_un_bac(db, f):
    """Un accès HORS projet dans un bac à sable — impossible par les routes, posé à la main
    pour éprouver l'exclusion des projets isolés (cadrage, § La migration v38)."""
    cid = _sql(db, "SELECT c.id FROM collection c JOIN projet p ON p.id = c.projet_id "
                   "WHERE p.id = ? LIMIT 1", (f["bacs_a_sable"][0],))[0]["id"]
    _sql(db, "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
             "VALUES (?, 'utilisateur', 'intrus-du-bac', 'lecture')", (cid,))
    return cid


def test_la_base_chargee_est_bien_une_v37_qui_a_vecu(vraie_v37):
    f = _faits()
    assert _sql(vraie_v37, "PRAGMA user_version")[0]["user_version"] == 37
    tables = {r["name"] for r in _sql(vraie_v37, "SELECT name FROM sqlite_master "
                                                 "WHERE type = 'table'")}
    assert "geste_sur_copie" in tables
    assert not {"planche_id", "planche_numero"} & {
        c["name"] for c in _sql(vraie_v37, "PRAGMA table_info(demande)")}
    hors = _hors_projet(vraie_v37)
    semes = {(None, g, p) for _, g, p in f["acces_hors_projet"]}
    assert {(None, g, p) for _, g, p in hors} >= semes and len(hors) >= 3
    assert {g for _, g, _ in hors} == {"utilisateur", "groupe"}
    assert {pr for pr, _, _ in hors} >= {f["projet_etude"], f["projet_repli"]}


def test_une_vraie_base_v37_migre_sans_rien_perdre(vraie_v37):
    f = _faits()
    bac = _poser_dans_un_bac(vraie_v37, f)
    # Une collection du repli SANS projet nommé (une base retouchée à la main) qui porte un
    # accès hors projet : son principal entre dans le REPLI (`sql_projet_de`), pas nulle part.
    repli = f["projet_repli"]
    sans_projet = _sql(vraie_v37, "INSERT INTO collection (nom, projet_id) "
                                  "VALUES ('Sans projet nommé', NULL) RETURNING id")[0]["id"]
    _sql(vraie_v37, "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
                    "VALUES (?, 'utilisateur', 'venue-par-le-repli', 'ecriture')",
         (sans_projet,))
    hors = _hors_projet(vraie_v37)
    assert (repli, "utilisateur", "venue-par-le-repli") in hors
    membres_avant = _membres(vraie_v37)
    lignes_avant = {t: _lignes(vraie_v37, t) for t in LIGNES}
    demandes_avant = _lignes(vraie_v37, "demande")
    seq_avant = _seq(vraie_v37)

    database.init_db()

    assert _sql(vraie_v37, "PRAGMA user_version")[0]["user_version"] == 38
    assert database.SCHEMA_VERSION == 38
    # 1. Les colonnes de la planche : NULL partout.
    cols = {c["name"] for c in _sql(vraie_v37, "PRAGMA table_info(demande)")}
    assert {"planche_id", "planche_numero"} <= cols
    assert _sql(vraie_v37, "SELECT COUNT(*) AS n FROM demande WHERE planche_id IS NOT NULL "
                           "OR planche_numero IS NOT NULL")[0]["n"] == 0
    # … et les demandes, en attente comme closes, inchangées en nombre et en contenu.
    assert _lignes(vraie_v37, "demande", sans=("planche_id", "planche_numero")) \
        == demandes_avant
    en_attente = _faits()["demandes_v37"]["en_attente"]
    for i in en_attente.values():
        assert _sql(vraie_v37, "SELECT reponse FROM demande WHERE id = ?", (i,)) == [
            {"reponse": None}]
    # 2. Les accès hors projet sont devenus des membres — eux seuls, au rôle `membre`.
    membres_apres = _membres(vraie_v37)
    assert set(membres_apres) == set(membres_avant) | hors
    assert len(membres_apres) == len(membres_avant) + len(hors)
    assert all(membres_apres[k] == "membre" for k in hors)
    assert all(membres_apres[k] == r for k, r in membres_avant.items())
    assert _hors_projet(vraie_v37) == set()
    # Rien dans un projet isolé : l'intrus posé à la main dans un bac à sable n'y entre pas.
    assert not any(p == "intrus-du-bac" for _, _, p in membres_apres)
    assert _sql(vraie_v37, "SELECT COUNT(*) AS n FROM collection_acces WHERE collection_id = ? "
                           "AND principal = 'intrus-du-bac'", (bac,))[0]["n"] == 1
    # 3. `geste_sur_copie` est partie.
    tables = {r["name"] for r in _sql(vraie_v37, "SELECT name FROM sqlite_master "
                                                 "WHERE type = 'table'")}
    assert "geste_sur_copie" not in tables
    # Et rien d'autre : chaque autre table, ligne à ligne ; les compteurs.
    assert {t: _lignes(vraie_v37, t) for t in LIGNES} == lignes_avant
    assert _seq(vraie_v37) == seq_avant
    assert _sql(vraie_v37, "PRAGMA foreign_key_check") == []
    assert _sql(vraie_v37, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"


def test_rejouee_la_migration_ne_change_rien(vraie_v37):
    database.init_db()
    etat = (_membres(vraie_v37), {t: _lignes(vraie_v37, t) for t in (*LIGNES, "demande")},
            _sql(vraie_v37, "SELECT type, name, sql FROM sqlite_master ORDER BY name"))
    _sql(vraie_v37, "PRAGMA user_version = 37")
    database.init_db()
    assert (_membres(vraie_v37), {t: _lignes(vraie_v37, t) for t in (*LIGNES, "demande")},
            _sql(vraie_v37, "SELECT type, name, sql FROM sqlite_master ORDER BY name")) == etat


def test_la_base_migree_a_la_forme_d_une_base_neuve(vraie_v37, tmp_path):
    """`demande` colonne par colonne (sur l'une les deux colonnes naissent de l'`ALTER`, sur
    l'autre du `CREATE`), et `geste_sur_copie` absente des deux."""
    database.init_db()
    neuve = tmp_path / "neuve.sqlite"
    c = sqlite3.connect(neuve)
    c.executescript(database.SCHEMA_SQL)
    c.close()

    def forme(db):
        demande = [(x["name"], x["type"], x["notnull"], x["dflt_value"])
                   for x in _sql(db, "PRAGMA table_info(demande)")]
        tables = {r["name"] for r in _sql(db, "SELECT name FROM sqlite_master "
                                              "WHERE type = 'table'")}
        return demande, "geste_sur_copie" in tables
    assert forme(vraie_v37) == forme(neuve)
    assert forme(neuve)[1] is False


class _Requete:
    def __init__(self, login, groupes=""):
        self.headers = {"Remote-User": login, "Remote-Groups": groupes}


def test_ce_que_la_migration_ouvre_se_lit_sur_une_portee_resolue(vraie_v37, monkeypatch):
    """Relecture croisée de la 3c, constat 2, et la décision du pilotage (2026-10-27) : faire
    membre un principal hors projet le fait entrer dans la BASE du projet au niveau
    `acces_membres` (D10) — voulu (F2, « les faire entrer »). Mesuré sur une PORTÉE résolue,
    principal par principal : avant, après ; ce qui s'ajoute est la base de son projet, au
    niveau du projet, et rien d'autre."""
    import autorisation
    monkeypatch.setattr(autorisation, "AUTH_PROXY", True)
    hors = sorted(_hors_projet(vraie_v37))
    bases = {r["projet"]: (r["id"], r["acces_membres"]) for r in _sql(
        vraie_v37, "SELECT projet_id AS projet, id, acces_membres FROM collection "
                   "WHERE base = 1")}

    def portee(genre, principal):
        req = (_Requete(principal) if genre == "utilisateur"
               else _Requete("compte-du-groupe", principal))
        conn = database.get_connection()
        try:
            return autorisation.resoudre(conn, req)
        finally:
            conn.close()

    avant = {(g, p): portee(g, p) for _, g, p in hors}
    database.init_db()
    ouvert = []
    for projet, genre, principal in hors:
        apres = portee(genre, principal)
        base, niveau = bases[projet]
        lu = apres.lecture - avant[genre, principal].lecture
        ecrit = apres.ecriture - avant[genre, principal].ecriture
        assert lu <= {base} and ecrit <= {base}, (principal, lu, ecrit)
        assert (base in lu or base in avant[genre, principal].lecture) == (niveau is not None)
        assert (base in ecrit or base in avant[genre, principal].ecriture) == (
            niveau == "ecriture")
        assert not (apres.propriete - avant[genre, principal].propriete)
        if ecrit:
            ouvert.append(principal)
    # Le décor de la vraie base l'éprouve : au moins un principal ÉCRIT désormais dans une base.
    assert ouvert, "prémisse : la base porte un projet à base ouverte et un accès hors projet"
