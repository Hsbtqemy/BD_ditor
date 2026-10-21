"""Les locuteurs que portent des régions qui n'en portent pas (`tools/retirer_locuteurs_muets.py`,
ANN-8).

Une base d'avant ANN-8 peut porter des cases et des boîtes personnage qui ont gardé le
locuteur de la bulle qu'elles étaient. L'outil le dit, à blanc par défaut, et le retire avec
`--appliquer`. Ce fichier éprouve ce qu'il promet, et qui échouerait en silence :

1. **À blanc, il n'écrit RIEN** — ni retrait, ni journal, ni migration : la base s'ouvre en
   lecture seule.
2. **Il ne touche qu'aux types muets** : le locuteur d'une bulle, d'un cartouche ou d'une
   zone de texte reste.
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
import retirer_locuteurs_muets as outil  # noqa: E402
import undo  # noqa: E402


@pytest.fixture
def conn(data_dir):
    database.init_db()
    c = database.get_connection()
    yield c
    c.close()


def _semer(conn):
    """Une planche ; une région de chaque type, chacune avec un locuteur posé à la main —
    comme une base d'avant le porte. Rend {type: region_id} et l'id du personnage."""
    aid = conn.execute("INSERT INTO albums (titre) VALUES ('Album')").lastrowid
    pid = conn.execute("INSERT INTO planches (album_id, numero, chemin_web) "
                       "VALUES (?, 1, 'x.jpg')", (aid,)).lastrowid
    perso = conn.execute("INSERT INTO personnages (nom) VALUES ('Tintin')").lastrowid
    ids = {}
    for i, t in enumerate(("case", "bulle", "personnage", "texte", "cartouche")):
        ids[t] = conn.execute(
            "INSERT INTO regions (planche_id, type, x, y, w, h, ordre, source) "
            "VALUES (?, ?, 0, 0, 10, 10, ?, 'manuel')", (pid, t, i)).lastrowid
        conn.execute("INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?)",
                     (ids[t], perso))
    conn.commit()
    return ids, perso


def _porteurs(conn):
    return {r["region_id"] for r in conn.execute("SELECT region_id FROM bulle_locuteur")}


def _evenements(conn):
    return conn.execute("SELECT COUNT(*) FROM evenement").fetchone()[0]


def test_la_liste_ne_porte_que_les_types_muets(conn):
    ids, perso = _semer(conn)
    lignes = database.locuteurs_muets(conn)
    assert {r["region_id"] for r in lignes} == {ids["case"], ids["personnage"]}
    assert {r["type"] for r in lignes} == {"case", "personnage"}
    assert all(r["personnage_id"] == perso and r["personnage_nom"] == "Tintin" for r in lignes)


def test_a_blanc_l_outil_dit_et_n_ecrit_rien(conn, capsys):
    ids, _ = _semer(conn)
    avant = _evenements(conn)
    assert outil.main([]) == 0
    sortie = capsys.readouterr().err
    assert "2 région(s)" in sortie
    assert f"région {ids['case']} (case)" in sortie
    assert f"région {ids['personnage']} (personnage)" in sortie
    assert "À BLANC" in sortie
    assert _porteurs(conn) == set(ids.values())          # rien n'est retiré
    assert _evenements(conn) == avant                     # rien n'est journalisé
    assert conn.execute("SELECT COUNT(*) FROM activite").fetchone()[0] == 0


def test_a_blanc_la_base_s_ouvre_en_lecture_seule(conn):
    """La garde qui compte : à blanc, une écriture par mégarde ÉCHOUE au lieu de passer."""
    _semer(conn)
    lecture = outil._ouvrir_la_base(False)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            lecture.execute("DELETE FROM bulle_locuteur")
    finally:
        lecture.close()
    assert len(_porteurs(conn)) == 5


def test_appliquer_retire_les_seuls_types_muets_et_journalise_en_machine(conn, capsys):
    ids, perso = _semer(conn)
    assert outil.main(["--appliquer"]) == 0
    assert "2 locuteur(s) retiré(s)" in capsys.readouterr().err
    assert _porteurs(conn) == {ids["bulle"], ids["texte"], ids["cartouche"]}

    act = conn.execute("SELECT * FROM activite WHERE type = 'retrait_locuteurs_muets'").fetchone()
    assert act is not None and act["agent_type"] == "moteur"
    assert act["agent"] == outil.AGENT
    assert act["date_fin"] is not None, "activité laissée OUVERTE : lue comme un run en cours"
    evs = conn.execute("SELECT * FROM evenement WHERE activite_id = ? ORDER BY cible_id",
                       (act["id"],)).fetchall()
    assert [(e["type"], e["cible_table"], e["cible_id"], e["agent_type"]) for e in evs] == [
        ("delien", "bulle_locuteur", ids["case"], "moteur"),
        ("delien", "bulle_locuteur", ids["personnage"], "moteur")]
    assert all(f'"personnage_id": {perso}' in e["avant"] for e in evs)


def test_le_retrait_reste_hors_de_ctrl_z(conn):
    _semer(conn)
    outil.appliquer(conn)
    assert undo.derniere_action_annulable(conn) is None


def test_appliquer_est_rejouable(conn, capsys):
    _semer(conn)
    assert outil.appliquer(conn) == 2
    assert database.locuteurs_muets(conn) == []
    assert outil.main(["--appliquer"]) == 0
    assert "Aucune case ni boîte personnage" in capsys.readouterr().err


def test_une_base_d_une_autre_version_est_refusee_par_son_nom(conn):
    conn.execute(f"PRAGMA user_version = {database.SCHEMA_VERSION - 1}")
    conn.commit()
    with pytest.raises(SystemExit, match="démarrez l'application"):
        outil.main([])
