"""Les personnages montrés par des régions qui ne les montrent pas
(`tools/retirer_liens_caches.py`, ANN-8).

Une base d'avant le miroir du locuteur peut porter des bulles qui ont gardé le personnage de
la boîte qu'elles étaient. L'outil le dit, à blanc par défaut, et le retire avec
`--appliquer`. Ce fichier éprouve ce qu'il promet, et qui échouerait en silence :

1. **À blanc, il n'écrit RIEN** — la base s'ouvre en lecture seule.
2. **Il ne touche qu'aux types qui ne montrent pas** : le personnage d'une boîte
   personnage reste.

ANN-7, le basculement : la situation d'une case, qu'il retirait aussi, ne se lit plus ; la
v39 a détruit sa table.
3. **Le retrait est un acte MACHINE**, journalisé, hors de Ctrl+Z.

`tools/` est hors couverture (`.coveragerc`) : sans ce fichier, une divergence y donnerait un
outil cassé et une suite verte.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT))

import database  # noqa: E402
import retirer_liens_caches as outil  # noqa: E402
import undo  # noqa: E402

TYPES = ("case", "bulle", "personnage", "texte", "cartouche")


@pytest.fixture
def conn(data_dir):
    database.init_db()
    c = database.get_connection()
    yield c
    c.close()


def _semer(conn):
    """Une planche ; une région de chaque type, chacune montrant Milou, posés à la main —
    comme une base d'avant les porte. Rend {type: region_id}, le personnage, et None (la
    valeur d'une situation, qui n'a plus de table depuis la v39)."""
    aid = conn.execute("INSERT INTO albums (titre) VALUES ('Album')").lastrowid
    pid = conn.execute("INSERT INTO planches (album_id, numero, chemin_web) "
                       "VALUES (?, 1, 'x.jpg')", (aid,)).lastrowid
    perso = conn.execute("INSERT INTO personnages (nom) VALUES ('Milou')").lastrowid
    val = None
    ids = {}
    for i, t in enumerate(TYPES):
        ids[t] = conn.execute(
            "INSERT INTO regions (planche_id, type, x, y, w, h, ordre, source) "
            "VALUES (?, ?, 0, 0, 10, 10, ?, 'manuel')", (pid, t, i)).lastrowid
        conn.execute("INSERT INTO personnage_presence (region_id, personnage_id) VALUES (?, ?)",
                     (ids[t], perso))
    conn.commit()
    return ids, perso, val


def _presences(conn):
    return {r["region_id"] for r in conn.execute("SELECT region_id FROM personnage_presence")}


def _evenements(conn):
    return conn.execute("SELECT COUNT(*) FROM evenement").fetchone()[0]


def test_la_liste_ne_porte_que_les_types_qui_ne_montrent_pas(conn):
    ids, perso, val = _semer(conn)
    pres = database.presences_cachees(conn)
    assert {r["region_id"] for r in pres} == {ids[t] for t in TYPES if t != "personnage"}
    assert all(r["personnage_id"] == perso and r["personnage_nom"] == "Milou" for r in pres)


def test_a_blanc_l_outil_dit_et_n_ecrit_rien(conn, capsys):
    ids, _, val = _semer(conn)
    avant = _evenements(conn)
    assert outil.main([]) == 0
    sortie = capsys.readouterr().err
    assert "4 lien(s)" in sortie
    assert f"région {ids['bulle']} (bulle)" in sortie
    assert "personnage montré « Milou »" in sortie
    assert "situation" not in sortie and "nuit" not in sortie and "moment" not in sortie
    assert "À BLANC" in sortie
    assert _presences(conn) == set(ids.values())
    assert _evenements(conn) == avant
    assert conn.execute("SELECT COUNT(*) FROM activite").fetchone()[0] == 0


def test_a_blanc_la_base_s_ouvre_en_lecture_seule(conn):
    _semer(conn)
    lecture = outil._ouvrir_la_base(False)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            lecture.execute("DELETE FROM personnage_presence")
    finally:
        lecture.close()
    assert len(_presences(conn)) == 5


def test_appliquer_retire_les_seuls_liens_caches_et_journalise_en_machine(conn, capsys):
    ids, perso, val = _semer(conn)
    assert outil.main(["--appliquer"]) == 0
    assert "4 personnage(s) montré(s) retiré(s)" in capsys.readouterr().err
    assert _presences(conn) == {ids["personnage"]}

    act = conn.execute("SELECT * FROM activite WHERE type = 'retrait_liens_caches'").fetchone()
    assert act is not None and act["agent_type"] == "moteur" and act["agent"] == outil.AGENT
    assert act["date_fin"] is not None, "activité laissée OUVERTE : lue comme un run en cours"
    evs = conn.execute("SELECT * FROM evenement WHERE activite_id = ? ORDER BY id",
                       (act["id"],)).fetchall()
    assert all((e["type"], e["agent_type"]) == ("delien", "moteur") for e in evs)
    assert {e["cible_table"] for e in evs} == {"personnage_presence"}
    assert sorted(e["cible_id"] for e in evs) == sorted(ids[t] for t in TYPES if t != "personnage")
    assert all(f'"personnage_id": {perso}' in e["avant"] for e in evs)


def test_le_retrait_reste_hors_de_ctrl_z(conn):
    _semer(conn)
    outil.appliquer(conn)
    assert undo.derniere_action_annulable(conn) is None


def test_appliquer_est_rejouable(conn, capsys):
    _semer(conn)
    assert outil.appliquer(conn) == {"presences": 4}
    assert database.presences_cachees(conn) == []
    assert outil.main(["--appliquer"]) == 0
    assert "Aucune région ne montre" in capsys.readouterr().err


def test_une_base_d_une_autre_version_est_refusee_par_son_nom(conn):
    conn.execute(f"PRAGMA user_version = {database.SCHEMA_VERSION - 1}")
    conn.commit()
    with pytest.raises(SystemExit, match="démarrez l'application"):
        outil.main([])
