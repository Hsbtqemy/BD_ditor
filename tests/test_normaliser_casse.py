"""Passe de normalisation de casse en lot (`tools/normaliser_casse.py`, NLP-3).

`casse.py` est éprouvé ailleurs (`tests/test_casse.py`, table partagée avec le JS). Ce
fichier ne rejoue pas la règle : il éprouve ce que l'OUTIL promet en plus d'elle, et qui
ne se voit nulle part ailleurs.

Trois promesses, et les trois échouent en SILENCE si on les casse.

1. **La passe ne se fait pas passer pour un humain.** `regions.touche` dit « le
   pré-remplissage machine a été corrigé par quelqu'un » et les indicateurs de dérive la
   lisent. Un `marquer_touche` glissé ici ferait compter des milliers de corrections qui
   n'ont jamais eu lieu — sans erreur, sans test rouge, et le chiffre resterait faux pour
   toujours puisque le journal est append-only.
2. **Elle reste hors de Ctrl+Z.** `undo.py` ne remonte que `agent_type='humain'` : si les
   événements partaient en « humain », le premier Ctrl+Z d'un annotateur défairait une
   ligne de la passe au lieu de son propre geste — un undo qui annule le travail de
   quelqu'un d'autre.
3. **Elle est rejouable.** La garde `only_upper` vit dans le cœur, donc une seconde passe
   ne doit RIEN trouver — et surtout pas redescendre les noms propres qu'un humain vient
   de relever.

`tools/` est hors couverture (`.coveragerc`) : sans ce fichier, une divergence y donnerait
un outil cassé et une suite verte. C'est le précédent posé par `test_import_vocabulaire`.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT))

import database  # noqa: E402
import normaliser_casse as nc  # noqa: E402
import undo  # noqa: E402

CAPITALES = "ALORS TINTIN, LE F.B.I. T'ATTEND À NEW YORK ?"
NORMALISE = "Alors tintin, le F.B.I. t'attend à new york ?"


def _semer(conn, textes, *, album_titre="Album"):
    """Insère un album, une planche et une région par texte. Renvoie (album_id, [ids]).

    Insertion DIRECTE et non par l'API : `PUT /api/regions` pose `touche = 1`, ce qui
    détruirait d'avance la première promesse qu'on vient éprouver ici.
    """
    aid = conn.execute("INSERT INTO albums (titre) VALUES (?)", (album_titre,)).lastrowid
    pid = conn.execute(
        "INSERT INTO planches (album_id, numero, chemin_web) VALUES (?, 1, 'x.jpg')",
        (aid,)).lastrowid
    ids = []
    for i, t in enumerate(textes):
        ids.append(conn.execute(
            "INSERT INTO regions (planche_id, type, x, y, w, h, ordre, ocr_texte, source) "
            "VALUES (?, 'bulle', 0, 0, 10, 10, ?, ?, 'ocr')", (pid, i, t)).lastrowid)
    conn.commit()
    return aid, ids


@pytest.fixture
def conn(data_dir):
    database.init_db()
    c = database.get_connection()
    yield c
    c.close()


# --------------------------------------------------------------------------- #
# Ce que la passe écrit
# --------------------------------------------------------------------------- #
def test_la_passe_normalise_et_laisse_le_reste_tranquille(conn):
    _, (cap, mixte, bas) = _semer(conn, [CAPITALES, "Je suis là, Tintin.", "je suis là"])
    trouvees = nc.candidates(conn)
    assert [t[0] for t in trouvees] == [cap], "only_upper laisse passer une ligne mixte"

    nc.appliquer(conn, trouvees, portee={"corpus": True})
    lus = {r["id"]: r["ocr_texte"] for r in conn.execute("SELECT id, ocr_texte FROM regions")}
    assert lus[cap] == NORMALISE
    assert lus[mixte] == "Je suis là, Tintin."
    assert lus[bas] == "je suis là"


def test_le_texte_indexe_suit(conn):
    """Sans réindexation, la recherche et l'analyse porteraient encore sur l'ancienne
    casse — invisible tant qu'on ne cherche pas, puisque FTS5 plie la casse de toute façon."""
    _, (rid,) = _semer(conn, [CAPITALES])
    nc.appliquer(conn, nc.candidates(conn), portee={"corpus": True})
    indexe = conn.execute(
        "SELECT ocr_texte FROM recherche WHERE region_id = ?", (rid,)).fetchone()
    assert indexe is not None, "la région a disparu de l'index FTS"
    assert indexe["ocr_texte"] == NORMALISE


# --------------------------------------------------------------------------- #
# Les trois promesses
# --------------------------------------------------------------------------- #
def test_la_passe_ne_marque_aucune_region_comme_retouchee(conn):
    """`touche = 1` signifie « un humain a corrigé la machine ». Ici personne n'a corrigé
    quoi que ce soit : la poser fausserait les indicateurs de dérive, sans rien casser."""
    _, (rid,) = _semer(conn, [CAPITALES])
    nc.appliquer(conn, nc.candidates(conn), portee={"corpus": True})
    r = conn.execute("SELECT touche, date_modification FROM regions WHERE id = ?",
                     (rid,)).fetchone()
    assert r["touche"] == 0
    assert r["date_modification"] is None


def test_la_passe_est_journalisee_en_acte_machine(conn):
    _, (rid,) = _semer(conn, [CAPITALES])
    nc.appliquer(conn, nc.candidates(conn), portee={"corpus": True})

    act = conn.execute("SELECT * FROM activite WHERE type = 'normalisation_casse'").fetchone()
    assert act is not None, "aucune activité : la passe n'a laissé aucune trace"
    assert act["agent_type"] == "moteur"
    assert act["agent"] == "normalisation-casse"
    assert act["date_fin"] is not None, "activité laissée OUVERTE : lue comme un run en cours"

    ev = conn.execute("SELECT * FROM evenement WHERE cible_id = ? AND cible_table = 'regions'",
                      (rid,)).fetchone()
    assert ev["agent_type"] == "moteur"
    assert ev["activite_id"] == act["id"]
    # L'avant/après est ce qui rend la passe rattrapable en lisant le journal seul.
    assert CAPITALES in (ev["avant"] or "")
    assert NORMALISE in (ev["apres"] or "")


def test_la_passe_reste_hors_de_ctrl_z(conn):
    """Sinon le premier Ctrl+Z d'un annotateur défairait une ligne de la passe au lieu de
    son propre geste — un undo qui annule le travail d'un autre."""
    _semer(conn, [CAPITALES])
    nc.appliquer(conn, nc.candidates(conn), portee={"corpus": True})
    assert undo.derniere_action_annulable(conn) is None
    assert undo.apercu(conn) is None


def test_la_passe_est_rejouable_sans_degat(conn):
    """Deuxième passe : rien à faire. Et surtout, un nom propre relevé entre-temps par un
    humain n'est pas redescendu — c'est `only_upper` qui l'assure, dans le cœur."""
    _, (rid,) = _semer(conn, [CAPITALES])
    assert nc.appliquer(conn, nc.candidates(conn), portee={"corpus": True}) == 1
    conn.execute("UPDATE regions SET ocr_texte = ? WHERE id = ?",
                 ("Alors Tintin, le F.B.I. t'attend à New York ?", rid))
    conn.commit()

    assert nc.candidates(conn) == []
    assert conn.execute("SELECT ocr_texte FROM regions WHERE id = ?", (rid,)).fetchone()[0] \
        == "Alors Tintin, le F.B.I. t'attend à New York ?"


# --------------------------------------------------------------------------- #
# Le ciblage
# --------------------------------------------------------------------------- #
def test_le_ciblage_par_album_et_par_planche(conn):
    a1, (r1,) = _semer(conn, [CAPITALES], album_titre="Un")
    a2, (r2,) = _semer(conn, ["MILLE SABORDS !"], album_titre="Deux")
    p2 = conn.execute("SELECT planche_id FROM regions WHERE id = ?", (r2,)).fetchone()[0]

    assert [t[0] for t in nc.candidates(conn, album_id=a1)] == [r1]
    assert [t[0] for t in nc.candidates(conn, album_id=a2)] == [r2]
    assert [t[0] for t in nc.candidates(conn, planche_id=p2)] == [r2]
    assert sorted(t[0] for t in nc.candidates(conn)) == sorted([r1, r2])


def test_le_dry_run_n_ecrit_rien(conn):
    _, (rid,) = _semer(conn, [CAPITALES])
    assert nc.main(["--dry-run"]) == 0
    assert conn.execute("SELECT ocr_texte FROM regions WHERE id = ?",
                        (rid,)).fetchone()[0] == CAPITALES
    assert conn.execute("SELECT COUNT(*) FROM activite").fetchone()[0] == 0


def test_la_cli_bout_en_bout(conn):
    _, (rid,) = _semer(conn, [CAPITALES])
    assert nc.main([]) == 0
    assert conn.execute("SELECT ocr_texte FROM regions WHERE id = ?",
                        (rid,)).fetchone()[0] == NORMALISE
    assert nc.main([]) == 0            # rejouée : plus rien à faire, et pas d'activité de plus
    assert conn.execute("SELECT COUNT(*) FROM activite").fetchone()[0] == 1
