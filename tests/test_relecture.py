"""Statut de relecture grammaticale par planche (ANN-4 / B5).

Vérifie le statut DÉRIVÉ des provenances de tokens (relus = corrigé|validé → a_faire / en_cours
/ faite), l'OVERRIDE humain (`planches.relecture`, forçable et libérable), la route
`PATCH /api/planches/{id}/relecture`, et la migration v21. Tokens/corrections semés en direct
(la couche spaCy est optionnelle).
"""
import sqlite3


def _region(client, planche_id, type="bulle"):
    return client.post(f"/api/planches/{planche_id}/regions",
                       json={"type": type, "x": 1, "y": 1, "w": 10, "h": 10}).json()["id"]


def _seed_tokens(db_path, region_id, tokens):
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) VALUES (?,?,?,?,?,?)",
        [(region_id, *t) for t in tokens])
    conn.commit()
    conn.close()


def _relire(db_path, region_id, ordres, etat="valide"):
    """Pose une correction ACTIVE (accepte l'auto) sur des positions → tokens « relus »."""
    conn = sqlite3.connect(db_path)
    for o in ordres:
        forme = conn.execute("SELECT texte FROM tokens WHERE region_id = ? AND ordre = ?",
                             (region_id, o)).fetchone()[0]
        conn.execute("INSERT INTO token_correction (region_id, ordre, forme, etat, obsolete) "
                     "VALUES (?, ?, ?, ?, 0)", (region_id, o, forme, etat))
    conn.commit()
    conn.close()


def _statut(client, album_id, planche_id):
    planches = client.get(f"/api/albums/{album_id}/planches").json()
    return next(p for p in planches if p["id"] == planche_id)["relecture_statut"]


# --------------------------------------------------------------------------- #
# Schéma
# --------------------------------------------------------------------------- #
def test_schema_a_jour_et_colonne_relecture(db_path):
    """Une base neuve est à la version COURANTE et porte `relecture` (ANN-4, posée en v21).

    On compare à `database.SCHEMA_VERSION` plutôt qu'au littéral 21 : épingler le nombre
    faisait échouer ce test à chaque migration ultérieure sans rien apprendre de plus —
    constaté au passage en v22 (AUTH-1). Ce qui compte ici est que la base soit migrée
    jusqu'au bout ET que la colonne d'ANN-4 y soit."""
    import database
    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    assert "relecture" in {r[1] for r in conn.execute("PRAGMA table_info(planches)")}
    conn.close()


def test_migration_v20_vers_v21_ajoute_relecture(tmp_path):
    """Chemin ADD de la migration : sur un schéma « v20 » (planches SANS `relecture`),
    `_migrate` pose la colonne par ALTER (gardé par présence). Le fresh DB, lui, la tient de
    SCHEMA_SQL. Schéma minimal (comme test_migration_v19_vers_v20) pour isoler l'étape."""
    import database
    db = tmp_path / "pre21.sqlite"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row                        # _migrate lit r["name"]
    conn.executescript(
        "CREATE TABLE albums (id INTEGER PRIMARY KEY, titre TEXT);"     # requis (_migrate v1→v2)
        "CREATE TABLE planches (id INTEGER PRIMARY KEY, album_id INTEGER);"
        "PRAGMA user_version = 20;")
    conn.commit()
    database._migrate(conn)
    assert "relecture" in {r[1] for r in conn.execute("PRAGMA table_info(planches)")}
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    conn.close()


# --------------------------------------------------------------------------- #
# Dérivation
# --------------------------------------------------------------------------- #
def test_relecture_derivee_des_provenances(client, album, planche, db_path):
    r = _region(client, planche["id"])
    # 0 token → à faire
    assert _statut(client, album["id"], planche["id"])["statut"] == "a_faire"

    _seed_tokens(db_path, r, [(0, "A", "a", "NOUN", ""), (1, "B", "b", "VERB", "")])
    st = _statut(client, album["id"], planche["id"])
    assert st["statut"] == "a_faire" and st["tokens"] == 2 and st["relus"] == 0

    _relire(db_path, r, [0])                       # 1/2 relu → en cours
    assert _statut(client, album["id"], planche["id"])["statut"] == "en_cours"

    _relire(db_path, r, [1])                       # 2/2 relus → faite
    st = _statut(client, album["id"], planche["id"])
    assert st == {"statut": "faite", "derive": "faite", "force": False, "tokens": 2, "relus": 2}


# --------------------------------------------------------------------------- #
# Override (forçable + libérable)
# --------------------------------------------------------------------------- #
def test_relecture_override(client, album, planche, db_path):
    pid = planche["id"]
    res = client.patch(f"/api/planches/{pid}/relecture", json={"relecture": "faite"})
    assert res.status_code == 200
    assert res.json()["relecture_statut"] == {
        "statut": "faite", "derive": "a_faire", "force": True, "tokens": 0, "relus": 0}
    # visible aussi dans la liste
    assert _statut(client, album["id"], pid) == res.json()["relecture_statut"]

    # libérer → revient au dérivé
    client.patch(f"/api/planches/{pid}/relecture", json={"relecture": None})
    st = _statut(client, album["id"], pid)
    assert st["force"] is False and st["statut"] == "a_faire"


def test_relecture_override_invalide_422(client, planche):
    assert client.patch(f"/api/planches/{planche['id']}/relecture",
                        json={"relecture": "bidon"}).status_code == 422


def test_relecture_planche_introuvable_404(client):
    assert client.patch("/api/planches/999999/relecture",
                        json={"relecture": "faite"}).status_code == 404
