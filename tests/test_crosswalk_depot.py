"""Smoke tests du crosswalk de dépôt (`tools/crosswalk_depot.py`).

Vérifie la non-régression fonctionnelle : le crosswalk tourne de bout en bout sur un
corpus réel (bâti par l'API) et produit des notices Dublin Core + DataCite exploitables,
fidèles au cadrage éditorial « à la Zotero » (cf. docs/crosswalk-depot.md). Exécution en
SOUS-PROCESSUS (comme les autres tests d'export), `BD_DB_PATH` → base de test.
"""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"


def _run(script, db_path, data_dir, *args):
    # PYTHONUTF8=1 force TOUT sous-processus (y compris gerer_collections) à émettre de
    # l'UTF-8, décodé en UTF-8 → aller-retour robuste sur Windows (console cp1252 sinon),
    # tout caractère compris (emoji, CJK…).
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir),
           "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, str(TOOLS / script), *args],
                          cwd=str(REPO_ROOT), env=env, capture_output=True,
                          text=True, encoding="utf-8")


def _checkpoint(db_path):
    """WAL checkpoint : le lecteur RO (sous-process) voit toutes les écritures de l'API."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()


def test_crosswalk_collection(client, album, db_path, data_dir):
    """Notice de collection : paternité Zotero (auteur BD = creator ; coloriste =
    contributor Other ; annotateur = DataCurator), droits SPDX, rôle fin en DC (relators
    MARC), DataCite XML kernel-4, champs obligatoires complets."""
    r0 = client.put(f"/api/albums/{album['id']}", json={"date_edition": "1960", "langue": "fr"})
    assert r0.status_code == 200, r0.text
    for nom, role in (("Hergé", "scénariste"), ("Studio", "coloriste")):
        rc = client.post(f"/api/albums/{album['id']}/contributions",
                         json={"nom": nom, "role": role})
        assert rc.status_code in (200, 201), rc.text
    _checkpoint(db_path)

    creer = _run("gerer_collections.py", db_path, data_dir, "creer",
                 "--nom", "Corpus test", "--licence", "CC-BY-4.0", "--statut", "public",
                 "--responsable", "Hugo;annotateur;0000-0002-1825-0097",
                 "--albums", str(album["id"]))
    assert creer.returncode == 0, creer.stderr
    cid = creer.stdout.strip()
    _checkpoint(db_path)

    r = _run("crosswalk_depot.py", db_path, data_dir, "--collection", cid)
    assert r.returncode == 0, r.stderr
    cw = json.loads(r.stdout)["crosswalk_depot"]

    col = cw["collection"]
    assert col is not None
    dcite = col["datacite"]
    assert dcite["types"]["resourceTypeGeneral"] == "Collection"
    assert dcite["publisher"] == "BéDéditeur" and dcite["publicationYear"]
    assert col["champs_obligatoires_manquants"] == []

    # Zotero : Hergé = creator ; coloriste = contributor Other ; annotateur = DataCurator.
    assert "Hergé" in [c["name"] for c in dcite["creators"]]
    types = {c["name"]: c["contributorType"] for c in dcite.get("contributors", [])}
    assert types.get("Studio") == "Other"
    assert types.get("Hugo") == "DataCurator"
    hugo = next(c for c in dcite["contributors"] if c["name"] == "Hugo")
    assert hugo["nameIdentifiers"][0]["nameIdentifier"] == "0000-0002-1825-0097"

    # Droits : licence + URI SPDX ; accès (statut de diffusion) porté aussi.
    rights = {x["rights"]: x.get("rightsUri") for x in dcite["rightsList"]}
    assert rights.get("CC-BY-4.0") == "https://creativecommons.org/licenses/by/4.0/"
    assert "public" in rights

    # Dublin Core : rôle fin conservé via relators MARC (scénariste → aut).
    assert "Hergé" in col["dublin_core"].get("marcrel:aut", [])

    # DataCite XML conforme (namespace kernel-4) + contenu.
    xml = col["datacite_xml"]
    assert xml.startswith("<?xml") and "datacite.org/schema/kernel-4" in xml
    assert "<resourceType" in xml and "Hergé" in xml

    # Portée : une seule notice album, la bonne, avec Hergé en creator.
    assert [a["id"] for a in cw["albums"]] == [album["id"]]
    assert "Hergé" in [c["name"] for c in cw["albums"][0]["datacite"]["creators"]]


def test_crosswalk_corpus_entier(client, album, db_path, data_dir):
    """Sans `--collection` : des notices album, aucune notice collection."""
    rc = client.post(f"/api/albums/{album['id']}/contributions",
                     json={"nom": "Franquin", "role": "dessinateur"})
    assert rc.status_code in (200, 201), rc.text
    _checkpoint(db_path)

    r = _run("crosswalk_depot.py", db_path, data_dir)
    assert r.returncode == 0, r.stderr
    cw = json.loads(r.stdout)["crosswalk_depot"]
    assert cw["collection"] is None
    assert cw["albums"], "au moins une notice album"
    noms = [c["name"] for a in cw["albums"] for c in a["datacite"]["creators"]]
    assert "Franquin" in noms
