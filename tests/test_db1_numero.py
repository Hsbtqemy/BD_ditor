"""DB-1 : unicité (album_id, numero) des planches + gestion de collision.

Couvre la contrainte (index unique), le dédoublonnage en migration (base existante
avec doublons → cohérente avant la contrainte) et le refus propre (409) d'un numéro
explicite déjà pris, sans écraser la planche existante.
"""
import sqlite3

import pytest

import database


def test_index_unique_existe(data_dir):
    with database.connect() as conn:
        idx = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_planches_album_numero" in idx


def test_contrainte_rejette_doublon(client, album):
    """Deux planches d'un même album avec le même numéro → IntegrityError (le perdant
    d'une course échoue au lieu d'écraser silencieusement)."""
    aid = album["id"]
    with database.connect() as conn:
        conn.execute("INSERT INTO planches (album_id, numero, chemin_web) VALUES (?, 1, 'a.jpg')", (aid,))
    with database.connect() as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO planches (album_id, numero, chemin_web) VALUES (?, 1, 'b.jpg')", (aid,))
    # même numéro dans un AUTRE album = OK (l'unicité est PAR album)
    aid2 = client.post("/api/albums", json={"titre": "B"}).json()["id"]
    with database.connect() as conn:
        conn.execute("INSERT INTO planches (album_id, numero, chemin_web) VALUES (?, 1, 'c.jpg')", (aid2,))


def test_migration_dedoublonne(client, album, db_path):
    """Base « v12 » avec des numéros en double → dédoublonnée puis contrainte à v13
    (ce que fait le lifespan au démarrage via init_db)."""
    aid = album["id"]
    raw = sqlite3.connect(db_path)
    raw.execute("DROP INDEX IF EXISTS idx_planches_album_numero")     # simule l'avant-DB-1
    raw.execute("INSERT INTO planches (album_id, numero, chemin_web) VALUES (?, 5, 'x.jpg')", (aid,))
    raw.execute("INSERT INTO planches (album_id, numero, chemin_web) VALUES (?, 5, 'y.jpg')", (aid,))
    raw.execute("PRAGMA user_version = 12")
    raw.commit(); raw.close()

    database.init_db()   # rejoue la migration (dédoublonnage + index)

    check = sqlite3.connect(db_path); check.row_factory = sqlite3.Row
    nums = sorted(r["numero"] for r in
                  check.execute("SELECT numero FROM planches WHERE album_id = ?", (aid,)))
    version = check.execute("PRAGMA user_version").fetchone()[0]
    check.close()
    assert version == 13
    assert len(nums) == 2 and len(set(nums)) == 2   # plus aucun doublon
    assert 5 in nums                                # la première garde son numéro


def test_route_import_numero_pris(client, album, png_bytes):
    """Import avec un numéro explicite déjà pris → 409, sans écraser la planche existante."""
    aid = album["id"]
    r1 = client.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", png_bytes, "image/png")}, data={"numero": "1"})
    assert r1.status_code == 201
    r2 = client.post(f"/api/albums/{aid}/import",
                     files={"file": ("q.png", png_bytes, "image/png")}, data={"numero": "1"})
    assert r2.status_code == 409
    # la planche d'origine est intacte (toujours une seule planche numéro 1)
    planches = client.get(f"/api/albums/{aid}/planches").json()
    assert len(planches) == 1 and planches[0]["numero"] == 1


def test_route_import_auto_incremente(client, album, png_bytes):
    """Sans numéro explicite : MAX+1 — deux imports successifs → 1 puis 2 (pas de collision)."""
    aid = album["id"]
    n1 = client.post(f"/api/albums/{aid}/import",
                     files={"file": ("a.png", png_bytes, "image/png")}).json()["numero"]
    n2 = client.post(f"/api/albums/{aid}/import",
                     files={"file": ("b.png", png_bytes, "image/png")}).json()["numero"]
    assert (n1, n2) == (1, 2)
