"""Alignement d'autorité (A5, niveau 6) — tests.

Vérifie la couche d'interopérabilité des entités personnages : schéma v18 + migration,
API (ajout avec auto-détection de source, URI validée, dédup, suppression), fusion qui
recolle les alignements, et propagation dans les exports (records `alignements[]`, table
CSV, indicateur `% aligné`). L'UI (panneau Personnage) est auditée à part (e2e/axe).
"""
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import database  # noqa: E402


def _lire(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------- #
# Schéma & migration
# --------------------------------------------------------------------------- #
def test_schema_alignement(db_path):
    conn = _lire(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(personnage_alignement)")}
    assert {"id", "personnage_id", "source", "uri"} <= cols


def test_migration_v17_vers_v18(tmp_path, monkeypatch):
    """Depuis une base « v17 » (table `personnage_alignement` retirée), init_db la recrée
    (SCHEMA_SQL) et porte la base au schéma courant."""
    db = tmp_path / "v17.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db)
    database.init_db()
    conn = sqlite3.connect(db)
    conn.executescript("DROP TABLE personnage_alignement; PRAGMA user_version = 17;")
    conn.commit()
    conn.close()
    database.init_db()
    conn = _lire(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='personnage_alignement'").fetchone()
    conn.close()


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
def test_ajout_detection_source(client):
    p = client.post("/api/personnages", json={"nom": "Tintin"}).json()
    r = client.post(f"/api/personnages/{p['id']}/alignements",
                    json={"uri": "https://www.wikidata.org/wiki/Q535"})
    assert r.status_code == 201 and r.json()["source"] == "wikidata"     # auto-détecté
    assert client.post(f"/api/personnages/{p['id']}/alignements",
                       json={"uri": "https://viaf.org/viaf/12"}).json()["source"] == "viaf"
    # hôte inconnu → source None (l'alignement reste valide)
    assert client.post(f"/api/personnages/{p['id']}/alignements",
                       json={"uri": "https://exemple.org/x"}).json()["source"] is None
    # source explicite respectée
    assert client.post(f"/api/personnages/{p['id']}/alignements",
                       json={"uri": "https://idref.fr/9", "source": "idref-perso"}
                       ).json()["source"] == "idref-perso"
    # URI non http(s) → 422
    assert client.post(f"/api/personnages/{p['id']}/alignements",
                       json={"uri": "pas une uri"}).status_code == 422


def test_dedup_et_suppression(client):
    p = client.post("/api/personnages", json={"nom": "Milou"}).json()
    u = "https://www.wikidata.org/wiki/Q1"
    client.post(f"/api/personnages/{p['id']}/alignements", json={"uri": u})
    client.post(f"/api/personnages/{p['id']}/alignements", json={"uri": u, "source": "wd"})  # re-post
    al = client.get(f"/api/personnages/{p['id']}/alignements").json()
    assert len(al) == 1 and al[0]["source"] == "wd"          # dédup + source mise à jour
    assert client.delete(f"/api/personnages/{p['id']}/alignements/{al[0]['id']}").status_code == 204
    assert client.get(f"/api/personnages/{p['id']}/alignements").json() == []
    # suppression d'un alignement absent → 404
    assert client.delete(f"/api/personnages/{p['id']}/alignements/99999").status_code == 404


def test_fusion_recolle_les_alignements(client):
    a = client.post("/api/personnages", json={"nom": "Tintin"}).json()
    b = client.post("/api/personnages", json={"nom": "tintin"}).json()   # doublon
    client.post(f"/api/personnages/{a['id']}/alignements",
                json={"uri": "https://www.wikidata.org/wiki/Q535"})
    client.post(f"/api/personnages/{b['id']}/alignements", json={"uri": "https://idref.fr/9"})
    client.post(f"/api/personnages/{b['id']}/fusion", json={"cible_id": a["id"]})
    uris = sorted(x["uri"] for x in client.get(f"/api/personnages/{a['id']}/alignements").json())
    assert uris == ["https://idref.fr/9", "https://www.wikidata.org/wiki/Q535"]


def test_cascade_suppression_personnage(client, db_path):
    p = client.post("/api/personnages", json={"nom": "Éphémère"}).json()
    client.post(f"/api/personnages/{p['id']}/alignements", json={"uri": "https://viaf.org/1"})
    client.delete(f"/api/personnages/{p['id']}")
    conn = _lire(db_path)
    assert conn.execute("SELECT COUNT(*) FROM personnage_alignement").fetchone()[0] == 0
    conn.close()


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def test_export_porte_les_alignements(client, db_path):
    p = client.post("/api/personnages", json={"nom": "Tintin"}).json()
    client.post("/api/personnages", json={"nom": "Milou"})           # non aligné
    client.post(f"/api/personnages/{p['id']}/alignements",
                json={"uri": "https://www.wikidata.org/wiki/Q535"})
    import metadonnees_collection as mc
    import description_collection as dc
    conn = _lire(db_path)
    doc = mc.collecter(conn)["metadonnees_collection"]
    tin = next(x for x in doc["personnages"] if x["nom"] == "Tintin")
    assert tin["alignements"] == [{"source": "wikidata",
                                   "uri": "https://www.wikidata.org/wiki/Q535"}]
    cols, rows = mc.tables(conn)["personnage_alignements"]
    assert cols == ["personnage_id", "source", "uri"] and len(rows) == 1
    perso = dc.collecter(conn)[0]["description_collection"]["couverture"]["personnages"]
    conn.close()
    assert perso["avec_alignement_autorite"] == 1 and perso["pct_aligne"] == 50.0
