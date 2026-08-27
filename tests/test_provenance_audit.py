"""Journal de provenance / audit (A3, niveau 8) — tests.

Vérifie la boucle complète : schéma v16 + migration, journal APPEND-ONLY qui survit à la
suppression de sa cible (substrat undo/D1), enregistrement des runs ML (`journal.passe_ml`),
événements humains avant/après avec agent capté depuis l'auth, surface dénormalisée
`touche` + indicateur de dérive, et export PROV-O / TEI (`tools/provenance_export.py`).
Les tests humains passent par l'API (TestClient) ; les assertions relisent la base.
"""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import database  # noqa: E402
import journal  # noqa: E402

# Utilisateur « connecté » (en-tête d'auth, INFRA-2). Le groupe vient d'AUTH-2 : hugo
# annote, donc il lui faut le droit d'écrire — sans quoi ces tests ne mesureraient
# plus la provenance mais le refus d'accès.
H = {"Remote-User": "hugo", "Remote-Groups": "bd-admins"}


def _lire(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _planche(conn, album_id):
    conn.execute("INSERT INTO planches (album_id, numero, chemin_web, largeur_px, hauteur_px) "
                 "VALUES (?, 1, 'w', 400, 500)", (album_id,))
    pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    return pid


# --------------------------------------------------------------------------- #
# Schéma & migration
# --------------------------------------------------------------------------- #
def test_schema_journal(db_path):
    conn = _lire(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"activite", "evenement"} <= tables
    rcols = {r["name"] for r in conn.execute("PRAGMA table_info(regions)")}
    assert {"activite_id", "touche", "date_modification"} <= rcols


def test_migration_ajoute_le_journal(tmp_path):
    """Depuis un schéma pré-v16 (regions SANS les colonnes A3, `activite` présente),
    `_migrate` gaté par user_version ajoute `activite_id`/`touche`/`date_modification` et
    porte la base au schéma courant — idempotent (relancer ne rejoue rien)."""
    db = tmp_path / "v15.sqlite"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row                       # _migrate lit r["name"]
    conn.executescript(
        "CREATE TABLE albums (id INTEGER PRIMARY KEY, titre TEXT);"
        "CREATE TABLE planches (id INTEGER PRIMARY KEY, album_id INT);"
        "CREATE TABLE regions (id INTEGER PRIMARY KEY, planche_id INT, type TEXT);"
        "CREATE TABLE activite (id INTEGER PRIMARY KEY);"
        "PRAGMA user_version = 15;")
    database._migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    rcols = {r["name"] for r in conn.execute("PRAGMA table_info(regions)")}
    assert {"activite_id", "touche", "date_modification"} <= rcols
    database._migrate(conn)                              # idempotent : court-circuit (déjà à jour)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    conn.close()


# --------------------------------------------------------------------------- #
# Journal append-only + actes humains
# --------------------------------------------------------------------------- #
def test_journal_survit_a_la_suppression(client, derriere_proxy, album, db_path):
    """Créer une région + son annotation, puis SUPPRIMER la région : le CASCADE efface tout,
    mais l'événement `suppression` PERSISTE avec un instantané PROFOND (substrat undo/D1)."""
    conn = _lire(db_path)
    pid = _planche(conn, album["id"])
    conn.close()
    r = client.post(f"/api/planches/{pid}/regions",
                    json={"type": "case", "x": 1, "y": 2, "w": 3, "h": 4}, headers=H).json()
    client.put(f"/api/regions/{r['id']}/annotation",
               json={"note": "à revoir", "tags": ["colere"]}, headers=H)
    client.delete(f"/api/regions/{r['id']}", headers=H)

    conn = _lire(db_path)
    assert conn.execute("SELECT COUNT(*) FROM regions").fetchone()[0] == 0   # cascade
    sup = conn.execute(
        "SELECT agent, avant FROM evenement WHERE type='suppression' AND cible_table='regions'"
    ).fetchone()
    assert sup is not None and sup["agent"] == "hugo"          # agent capté depuis l'auth
    avant = json.loads(sup["avant"])
    assert avant["type"] == "case" and avant["annotation"]["note"] == "à revoir"
    assert avant["annotation"]["tags"] == ["colere"]           # snapshot profond complet


def test_evenements_humains_avant_apres(client, derriere_proxy, album, db_path):
    """Création puis modification d'une région → deux événements, agent capté, avant/après
    reflétant le changement d'OCR ; l'annotation crée aussi son événement."""
    conn = _lire(db_path)
    pid = _planche(conn, album["id"])
    conn.close()
    r = client.post(f"/api/planches/{pid}/regions",
                    json={"type": "bulle", "x": 5, "y": 6, "w": 7, "h": 8}, headers=H).json()
    client.put(f"/api/regions/{r['id']}", json={"ocr_texte": "bonjour"}, headers=H)

    conn = _lire(db_path)
    evs = conn.execute(
        "SELECT type, agent, avant, apres FROM evenement WHERE cible_table='regions' "
        "ORDER BY id").fetchall()
    types = [e["type"] for e in evs]
    assert types == ["creation", "modification"]
    assert all(e["agent"] == "hugo" for e in evs)
    modif = evs[1]
    assert json.loads(modif["avant"])["ocr_texte"] is None
    assert json.loads(modif["apres"])["ocr_texte"] == "bonjour"
    # touche dénormalisé posé par la retouche humaine.
    assert conn.execute("SELECT touche FROM regions WHERE id = ?", (r["id"],)).fetchone()["touche"] == 1
    # l'annotation a son propre événement.
    client.put(f"/api/regions/{r['id']}/annotation", json={"note": "x", "tags": []}, headers=H)
    conn = _lire(db_path)
    assert conn.execute(
        "SELECT COUNT(*) FROM evenement WHERE cible_table='annotations' AND type='creation'"
    ).fetchone()[0] == 1


def test_agent_null_hors_auth(client, album, db_path):
    """Sans en-tête d'auth (usage local mono-utilisateur), l'agent est NULL — honnête.

    Ce test ne déclare volontairement PAS `derriere_proxy` : il décrit le mono-poste, et
    l'y placer était une contradiction que le cloisonnement (AUTH-2) a révélée — derrière
    le proxy, une requête sans identité ne crée plus rien du tout."""
    conn = _lire(db_path)
    pid = _planche(conn, album["id"])
    conn.close()
    client.post(f"/api/planches/{pid}/regions",
                json={"type": "case", "x": 1, "y": 1, "w": 1, "h": 1})   # pas de header
    conn = _lire(db_path)
    ev = conn.execute("SELECT agent, agent_type FROM evenement ORDER BY id DESC LIMIT 1").fetchone()
    assert ev["agent"] is None and ev["agent_type"] == "humain"


# --------------------------------------------------------------------------- #
# Runs ML (journal.passe_ml)
# --------------------------------------------------------------------------- #
def test_passe_ml_journalise_le_run(client, derriere_proxy, album, db_path):
    """`journal.passe_ml` (utilisé par les 3 routes ML + le worker de lot) : ouvre une
    activité, rattache les régions CRÉÉES à leur run (wasGeneratedBy = activite_id), émet un
    événement `creation` (agent=moteur), et clôt avec le bilan. Testé SANS moteur ML (on
    insère une région dans le bloc, comme le ferait Kumiko)."""
    conn = database.get_connection()
    pid = _planche(conn, album["id"])
    with journal.passe_ml(conn, "segmentation", pid, agent="kumiko",
                          params={"use_master": False}):
        conn.execute("INSERT INTO regions (planche_id, type, source) VALUES (?, 'case', 'kumiko')",
                     (pid,))
    conn.commit()
    rid = conn.execute("SELECT id, activite_id FROM regions WHERE planche_id = ?", (pid,)).fetchone()
    act = conn.execute("SELECT type, agent, agent_type, comptes FROM activite").fetchone()
    ev = conn.execute("SELECT type, agent_type, activite_id FROM evenement "
                      "WHERE cible_table='regions'").fetchone()
    conn.close()
    assert rid["activite_id"] is not None      # wasGeneratedBy : rattaché à son run
    assert act["type"] == "segmentation" and act["agent"] == "kumiko" and act["agent_type"] == "moteur"
    assert json.loads(act["comptes"])["crees"] == 1
    assert ev["type"] == "creation" and ev["agent_type"] == "moteur"
    assert ev["activite_id"] is not None       # l'acte procède du run (wasInformedBy)


# --------------------------------------------------------------------------- #
# Indicateurs dérivés
# --------------------------------------------------------------------------- #
def test_indicateur_derive(client, derriere_proxy, album, db_path):
    """Dérive = pré-remplissage MACHINE retouché par un humain. On génère une région par un
    run (activite_id), puis on la retouche via l'API (touche=1) → derive=1, taux=1.0."""
    conn = database.get_connection()
    pid = _planche(conn, album["id"])
    with journal.passe_ml(conn, "segmentation", pid, agent="kumiko"):
        conn.execute("INSERT INTO regions (planche_id, type, source) VALUES (?, 'case', 'kumiko')",
                     (pid,))
    conn.commit()
    rid = conn.execute("SELECT id FROM regions WHERE planche_id = ?", (pid,)).fetchone()["id"]
    conn.close()

    ind = journal.indicateurs_provenance(_lire(db_path))
    assert ind["regions"]["machine"] == 1 and ind["regions"]["derive"] == 0

    client.put(f"/api/regions/{rid}", json={"x": 42}, headers=H)   # retouche humaine
    ind = journal.indicateurs_provenance(_lire(db_path))
    assert ind["regions"]["derive"] == 1 and ind["regions"]["taux_derive"] == 1.0
    assert ind["activites"]["par_type"]["segmentation"] == 1
    assert ind["evenements"]["par_agent"]["humain"] >= 1
    assert ind["evenements"]["par_agent"]["moteur"] >= 1


def test_indicateur_scope_collection(client, derriere_proxy, album, db_path):
    """Le bloc `regions` est SCOPÉ par album ; hors périmètre, il ne compte pas."""
    conn = database.get_connection()
    pid = _planche(conn, album["id"])
    conn.execute("INSERT INTO regions (planche_id, type) VALUES (?, 'case')", (pid,))
    conn.commit()
    conn.close()
    ind_global = journal.indicateurs_provenance(_lire(db_path))
    ind_vide = journal.indicateurs_provenance(_lire(db_path), album_ids=[999999])
    assert ind_global["regions"]["total"] == 1
    assert ind_vide["regions"]["total"] == 0 and ind_vide["portee_regions"] == "collection"


# --------------------------------------------------------------------------- #
# Export PROV-O / TEI
# --------------------------------------------------------------------------- #
def test_prov_export_construire(client, derriere_proxy, album, db_path):
    """`tools/provenance_export.construire` : PROV-JSON (agents typés, wasGeneratedBy pour la
    création, wasInvalidatedBy pour la suppression) + fragment TEI revisionDesc."""
    import provenance_export
    conn = _lire(db_path)
    pid = _planche(conn, album["id"])
    conn.close()
    r = client.post(f"/api/planches/{pid}/regions",
                    json={"type": "case", "x": 1, "y": 2, "w": 3, "h": 4}, headers=H).json()
    client.delete(f"/api/regions/{r['id']}", headers=H)

    doc = provenance_export.construire(_lire(db_path))["provenance_export"]
    prov = doc["prov"]
    assert doc["resume"]["evenements"] >= 2
    # Agent humain typé Person.
    assert prov["agent"]["bd:agent/hugo"]["prov:type"] == "prov:Person"
    # Création → wasGeneratedBy ; suppression → wasInvalidatedBy.
    assert any(g["prov:entity"] == f"bd:regions/{r['id']}"
               for g in prov["wasGeneratedBy"].values())
    assert any(i["prov:entity"] == f"bd:regions/{r['id']}"
               for i in prov["wasInvalidatedBy"].values())
    # TEI : un <change> par acte, attribué.
    tei = doc["tei_revision_desc"]
    assert tei.startswith("<?xml") and "<revisionDesc>" in tei
    assert 'who="#hugo"' in tei and 'type="suppression"' in tei


def _run_tool(script, db_path, data_dir, *args):
    # Décodage UTF-8 sans PYTHONUTF8 : les tools forcent leur stdout en UTF-8 eux-mêmes
    # (_commun.forcer_utf8) → ce test exerce le garde de portabilité Windows.
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir)}
    return subprocess.run([sys.executable, str(REPO_ROOT / "tools" / script), *args],
                          cwd=str(REPO_ROOT), env=env, capture_output=True,
                          text=True, encoding="utf-8")


def test_prov_export_cli(client, derriere_proxy, album, db_path, data_dir):
    """CLI headless (sous-processus, UTF-8) : produit un PROV-JSON valide sur stdout."""
    conn = _lire(db_path)
    pid = _planche(conn, album["id"])
    conn.close()
    client.post(f"/api/planches/{pid}/regions",
                json={"type": "case", "x": 1, "y": 1, "w": 1, "h": 1}, headers=H)
    sqlite3.connect(db_path).execute("PRAGMA wal_checkpoint(TRUNCATE)")   # visible au lecteur RO

    r = _run_tool("provenance_export.py", db_path, data_dir)
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)["provenance_export"]
    assert doc["resume"]["evenements"] >= 1
    assert "prov" in doc and doc["prov"]["prefix"]["prov"].startswith("http://www.w3.org/ns/prov")
