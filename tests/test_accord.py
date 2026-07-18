"""Rapport d'accord modèle↔humain (NLP-1 / B4).

Cœur `accord.rapport` exposé par la route `GET /api/analyse/accord` ET l'outil
`tools/rapport_accord.py`. Vérifie l'accord par champ (auto accepté OU correction == auto),
la confusion POS, l'exclusion des corrections obsolètes, et le bout-en-bout CLI (+ JSON).
Tokens et corrections semés EN DIRECT (la couche spaCy est optionnelle).
"""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"


def _region(client, planche_id):
    return client.post(f"/api/planches/{planche_id}/regions",
                       json={"type": "bulle", "x": 1, "y": 1, "w": 10, "h": 10}).json()["id"]


def _seed_tokens(db_path, region_id, tokens):
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) VALUES (?,?,?,?,?,?)",
        [(region_id, *t) for t in tokens])
    conn.commit()
    conn.close()


def _seed_corr(db_path, region_id, corrs, obsolete=0):
    """corrs : (ordre, forme, lemme, pos, morph, etat). NULL = auto accepté."""
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT INTO token_correction (region_id, ordre, forme, lemme, pos, morph, etat, obsolete) "
        "VALUES (?,?,?,?,?,?,?,?)", [(region_id, *c, obsolete) for c in corrs])
    conn.commit()
    conn.close()


def _checkpoint(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()


def _run(db_path, data_dir, *args):
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir)}
    return subprocess.run([sys.executable, str(TOOLS / "rapport_accord.py"), *args],
                          cwd=str(REPO_ROOT), env=env, capture_output=True,
                          text=True, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Cœur / route
# --------------------------------------------------------------------------- #
def test_rapport_accord(client, album, planche, db_path):
    r = _region(client, planche["id"])
    _seed_tokens(db_path, r, [(0, "CHAT", "chat", "NOUN", ""),
                              (1, "COURT", "courir", "VERB", ""),
                              (2, "BELLE", "belle", "ADJ", "")])
    _seed_corr(db_path, r, [
        (0, "CHAT", None, None, None, "valide"),        # accepte l'auto → accord partout
        (1, "COURT", None, "NOUN", None, "corrige"),    # POS corrigé VERB→NOUN → désaccord POS
        (2, "BELLE", "beau", None, None, "corrige")])   # lemme belle→beau → désaccord lemme

    rep = client.get("/api/analyse/accord").json()
    assert rep["revus"] == 3 and rep["corriges"] == 2 and rep["valides"] == 1
    assert rep["champs"]["lemme"] == {"revus": 3, "accord": 2, "taux": 0.6667}
    assert rep["champs"]["pos"]["accord"] == 2                # seul token 1 en désaccord POS
    assert rep["champs"]["morph"]["accord"] == 3              # tous acceptés
    assert {"auto": "VERB", "humain": "NOUN", "n": 1} in rep["confusion_pos"]


def test_accord_ignore_les_corrections_obsoletes(client, album, planche, db_path):
    """Une correction obsolète (forme dérivée après reindex) ne compte pas — miroir de
    la vue tokens_effectifs (obsolete=0)."""
    r = _region(client, planche["id"])
    _seed_tokens(db_path, r, [(0, "CHAT", "chat", "NOUN", "")])
    _seed_corr(db_path, r, [(0, "CHIEN", None, "VERB", None, "corrige")], obsolete=1)
    rep = client.get("/api/analyse/accord").json()
    assert rep["revus"] == 0 and rep["confusion_pos"] == []
    assert rep["champs"]["pos"]["taux"] is None


def test_accord_vide(client):
    """Aucun token relu → tout à zéro, taux None (pas de division par zéro)."""
    rep = client.get("/api/analyse/accord").json()
    assert rep["revus"] == 0 and rep["champs"]["lemme"]["taux"] is None


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_rapport_accord(client, album, planche, db_path, data_dir, tmp_path):
    r = _region(client, planche["id"])
    _seed_tokens(db_path, r, [(0, "CHAT", "chat", "NOUN", "")])
    _seed_corr(db_path, r, [(0, "CHAT", None, "VERB", None, "corrige")])
    _checkpoint(db_path)

    out = tmp_path / "accord.json"
    res = _run(db_path, data_dir, "--json", str(out))
    assert res.returncode == 0, res.stderr
    assert "Accord modèle" in res.stderr and "Tokens relus : 1" in res.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["revus"] == 1 and data["champs"]["pos"]["accord"] == 0   # VERB≠NOUN
