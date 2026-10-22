"""Les personnages montrés et les situations que portent des régions qui ne les montrent pas
(`tools/retirer_liens_caches.py`, ANN-8).

Une base d'avant le miroir du locuteur peut porter des bulles qui ont gardé la situation de
la case qu'elles étaient, ou le personnage de la boîte qu'elles étaient. L'outil le dit, à
blanc par défaut, et le retire avec `--appliquer`. Ce fichier éprouve ce qu'il promet, et
qui échouerait en silence :

1. **À blanc, il n'écrit RIEN** — la base s'ouvre en lecture seule.
2. **Il ne touche qu'aux types qui ne montrent pas** : le personnage d'une boîte
   personnage et la situation d'une case restent.
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
    """Une planche ; une région de chaque type, chacune montrant Milou et située « nuit »,
    posés à la main — comme une base d'avant les porte. Rend {type: region_id}, le
    personnage et la valeur."""
    aid = conn.execute("INSERT INTO albums (titre) VALUES ('Album')").lastrowid
    pid = conn.execute("INSERT INTO planches (album_id, numero, chemin_web) "
                       "VALUES (?, 1, 'x.jpg')", (aid,)).lastrowid
    perso = conn.execute("INSERT INTO personnages (nom) VALUES ('Milou')").lastrowid
    dim = conn.execute("INSERT INTO attribut_dimension (cible, nom) "
                       "VALUES ('case', 'moment')").lastrowid
    val = conn.execute("INSERT INTO attribut_valeur (dimension_id, valeur) "
                       "VALUES (?, 'nuit')", (dim,)).lastrowid
    ids = {}
    for i, t in enumerate(TYPES):
        ids[t] = conn.execute(
            "INSERT INTO regions (planche_id, type, x, y, w, h, ordre, source) "
            "VALUES (?, ?, 0, 0, 10, 10, ?, 'manuel')", (pid, t, i)).lastrowid
        conn.execute("INSERT INTO personnage_presence (region_id, personnage_id) VALUES (?, ?)",
                     (ids[t], perso))
        conn.execute("INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)",
                     (ids[t], val))
    conn.commit()
    return ids, perso, val


def _presences(conn):
    return {r["region_id"] for r in conn.execute("SELECT region_id FROM personnage_presence")}


def _situees(conn):
    return {r["region_id"] for r in conn.execute("SELECT region_id FROM region_attribut")}


def _evenements(conn):
    return conn.execute("SELECT COUNT(*) FROM evenement").fetchone()[0]


def test_les_listes_ne_portent_que_les_types_qui_ne_montrent_pas(conn):
    ids, perso, val = _semer(conn)
    pres = database.presences_cachees(conn)
    assert {r["region_id"] for r in pres} == {ids[t] for t in TYPES if t != "personnage"}
    assert all(r["personnage_id"] == perso and r["personnage_nom"] == "Milou" for r in pres)
    sit = database.situations_cachees(conn)
    assert {r["region_id"] for r in sit} == {ids[t] for t in TYPES if t != "case"}
    assert all(r["valeur_id"] == val for r in sit)


def test_a_blanc_l_outil_dit_et_n_ecrit_rien(conn, capsys):
    ids, _, val = _semer(conn)
    avant = _evenements(conn)
    assert outil.main([]) == 0
    sortie = capsys.readouterr().err
    assert "8 lien(s)" in sortie
    assert f"région {ids['bulle']} (bulle)" in sortie
    assert "personnage montré « Milou »" in sortie
    assert f"situation, valeur {val}" in sortie
    assert "nuit" not in sortie and "moment" not in sortie   # aucun terme nommé
    assert "À BLANC" in sortie
    assert _presences(conn) == set(ids.values()) and _situees(conn) == set(ids.values())
    assert _evenements(conn) == avant
    assert conn.execute("SELECT COUNT(*) FROM activite").fetchone()[0] == 0


def test_a_blanc_la_base_s_ouvre_en_lecture_seule(conn):
    _semer(conn)
    lecture = outil._ouvrir_la_base(False)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            lecture.execute("DELETE FROM region_attribut")
    finally:
        lecture.close()
    assert len(_situees(conn)) == 5


def test_appliquer_retire_les_seuls_liens_caches_et_journalise_en_machine(conn, capsys):
    ids, perso, val = _semer(conn)
    assert outil.main(["--appliquer"]) == 0
    assert "4 personnage(s) montré(s) et 4 valeur(s)" in capsys.readouterr().err
    assert _presences(conn) == {ids["personnage"]}
    assert _situees(conn) == {ids["case"]}

    act = conn.execute("SELECT * FROM activite WHERE type = 'retrait_liens_caches'").fetchone()
    assert act is not None and act["agent_type"] == "moteur" and act["agent"] == outil.AGENT
    assert act["date_fin"] is not None, "activité laissée OUVERTE : lue comme un run en cours"
    evs = conn.execute("SELECT * FROM evenement WHERE activite_id = ? ORDER BY id",
                       (act["id"],)).fetchall()
    assert all((e["type"], e["agent_type"]) == ("delien", "moteur") for e in evs)
    pres = [e for e in evs if e["cible_table"] == "personnage_presence"]
    sit = [e for e in evs if e["cible_table"] == "region_attribut"]
    assert sorted(e["cible_id"] for e in pres) == sorted(ids[t] for t in TYPES if t != "personnage")
    assert sorted(e["cible_id"] for e in sit) == sorted(ids[t] for t in TYPES if t != "case")
    assert all(f'"personnage_id": {perso}' in e["avant"] for e in pres)
    assert all(f'"valeur_id": {val}' in e["avant"] for e in sit)


def test_le_retrait_reste_hors_de_ctrl_z(conn):
    _semer(conn)
    outil.appliquer(conn)
    assert undo.derniere_action_annulable(conn) is None


def test_appliquer_est_rejouable(conn, capsys):
    _semer(conn)
    assert outil.appliquer(conn) == {"presences": 4, "situations": 4}
    assert database.presences_cachees(conn) == [] and database.situations_cachees(conn) == []
    assert outil.main(["--appliquer"]) == 0
    assert "Aucune région ne montre" in capsys.readouterr().err


def test_une_base_d_une_autre_version_est_refusee_par_son_nom(conn):
    conn.execute(f"PRAGMA user_version = {database.SCHEMA_VERSION - 1}")
    conn.commit()
    with pytest.raises(SystemExit, match="démarrez l'application"):
        outil.main([])
