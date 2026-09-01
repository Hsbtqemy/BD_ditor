"""Tests de la sauvegarde de travail (snapshot SQLite zippé)."""
import io
import re
import sqlite3
import zipfile
from datetime import datetime

import pipeline.backup as backup


def _open_snapshot(zip_bytes, tmp_path):
    """Extrait la base du zip et l'ouvre pour vérifier qu'elle est valide."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert zf.namelist() == ["bd_annotator.sqlite"]
        raw = zf.read("bd_annotator.sqlite")
    f = tmp_path / "snap.sqlite"
    f.write_bytes(raw)
    conn = sqlite3.connect(f)
    conn.row_factory = sqlite3.Row
    return conn


def test_make_backup_contenu(client, album, tmp_path):
    name, data = backup.make_backup(stamp="20260101_120000")
    assert name == "bd_annotator_20260101_120000.zip"
    conn = _open_snapshot(data, tmp_path)
    try:
        titres = [r["titre"] for r in conn.execute("SELECT titre FROM albums")]
        assert album["titre"] in titres        # le snapshot contient bien les données
    finally:
        conn.close()


def test_make_backup_horodatage_auto(client, tmp_path):
    """Le FORMAT de l'horodatage, et qu'il désigne bien MAINTENANT.

    Le test vérifiait un préfixe et un suffixe : `bd_annotator_.zip` l'aurait satisfait,
    et `bd_annotator_XX.zip` aussi. Or c'est précisément l'horodatage qui distingue deux
    sauvegardes du même corpus — sans lui, la seconde écrase la première.

    `len(data) > 0` était de la même farine : un seul octet passait. Ce qu'on veut savoir,
    c'est que le zip s'ouvre et porte la base — `_open_snapshot` le dit, et il est déjà là.
    """
    avant = datetime.now().replace(microsecond=0)
    name, data = backup.make_backup()
    apres = datetime.now()

    m = re.fullmatch("bd_annotator_([0-9]{8}_[0-9]{6})[.]zip", name)
    assert m, f"nom hors format bd_annotator_AAAAMMJJ_HHMMSS.zip : {name}"
    quand = datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
    assert avant <= quand <= apres, (
        f"horodatage {quand} hors de l'intervalle d'exécution [{avant}, {apres}] — "
        "une constante ou une date figée passerait le contrôle de format")

    _open_snapshot(data, tmp_path).close()   # zip valide, portant une base ouvrable


def test_route_sauvegarde(client, album, tmp_path):
    r = client.get("/api/sauvegarde")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers["content-disposition"]
    assert ".zip" in r.headers["content-disposition"]
    conn = _open_snapshot(r.content, tmp_path)
    conn.close()   # s'ouvre sans erreur → base valide


def test_backup_pendant_ecriture_est_coherent(client, album, db_path, tmp_path):
    """QA-3 (concurrence) : un backup pris PENDANT une écriture NON committée (connexion
    séparée) reste cohérent — `VACUUM INTO` lit un snapshot WAL committé. La base copiée
    est valide ET EXCLUT la ligne en cours (isolation), sans 'database is locked'."""
    writer = sqlite3.connect(db_path, timeout=2)
    writer.execute("BEGIN IMMEDIATE")                      # prend le verrou d'écriture
    writer.execute("INSERT INTO albums (titre) VALUES ('EN_COURS_NON_COMMIT')")
    try:
        _, data = backup.make_backup(stamp="20260101_000000")   # snapshot pendant l'écriture
    finally:
        writer.rollback(); writer.close()
    conn = _open_snapshot(data, tmp_path)
    try:
        titres = [r["titre"] for r in conn.execute("SELECT titre FROM albums")]
    finally:
        conn.close()
    assert album["titre"] in titres                        # données committées : présentes
    assert "EN_COURS_NON_COMMIT" not in titres             # écriture en cours : exclue
