"""COL-3, tranche 3c (commit 0) — la VRAIE base v37, avant la migration qui la lira.

`tests/bases/v37-f6f53ed.sql` est faite par le code v37 lui-même
(`tools/fabriquer_base_de_version.py f6f53ed tests/bases/v37-f6f53ed.sql` — `f6f53ed`, la
tête de `dev` au début de la 3c, est le dernier état de la v37 ; règle de Hugo du
2026-10-16, `CLAUDE.md` § Schéma & migrations). La v38 n'existe pas encore : ce test ne
migre RIEN. Il charge la base telle quelle et vérifie qu'elle porte ce que `_parcours_v37` a
semé — sans quoi le test de la v38 passerait sur une base qui n'a pas de quoi le tromper.
Les identifiants viennent de l'en-tête du fichier, que l'outil écrit.
"""
import json
import sqlite3
from pathlib import Path

import pytest

BASE_V37 = Path(__file__).resolve().parent / "bases" / "v37-f6f53ed.sql"


def _faits() -> dict:
    """L'en-tête du fichier : `--   clé : <json>`, une ligne par fait."""
    faits = {}
    for ligne in BASE_V37.read_text(encoding="utf-8").splitlines():
        if not ligne.startswith("--"):
            break
        if ligne.startswith("--   ") and " : " in ligne:
            cle, val = ligne[5:].split(" : ", 1)
            faits[cle] = json.loads(val)
    return faits


@pytest.fixture(scope="module")
def v37(tmp_path_factory):
    db = tmp_path_factory.mktemp("v37") / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V37.read_text(encoding="utf-8"))
    c.row_factory = sqlite3.Row
    yield c, _faits()
    c.close()


def _un(c, q, p=()):
    return c.execute(q, p).fetchone()[0]


def test_elle_est_en_v37_et_saine(v37):
    c, _ = v37
    assert _un(c, "PRAGMA user_version") == 37
    assert _un(c, "PRAGMA integrity_check") == "ok"
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []


def test_une_grille_publiee_activee_un_releve_une_passe_un_doute(v37):
    c, f = v37
    assert _un(c, "SELECT etat FROM grille_version WHERE grille_id = ? AND numero = 1",
               (f["grille"],)) == "publiee"
    assert _un(c, "SELECT COUNT(*) FROM projet_grille WHERE projet_id = ? AND grille_id = ?",
               (f["projet_etude"], f["grille"])) == 1
    assert _un(c, "SELECT COUNT(*) FROM releve WHERE id = ?", (f["releve"],)) == 1
    assert _un(c, "SELECT COUNT(*) FROM passe") >= 1
    assert _un(c, "SELECT COUNT(*) FROM doute WHERE id = ?", (f["doute"],)) == 1


# Le projet d'une collection : NULL se lit « le projet de repli » (`database.sql_projet_de`).
_PROJET_DE = "COALESCE(col.projet_id, (SELECT id FROM projet WHERE repli = 1))"


def test_des_acces_hors_projet_et_aucun_dans_un_bac_a_sable(v37):
    c, f = v37
    hors = {tuple(r) for r in c.execute(
        f"SELECT ca.collection_id, ca.genre, ca.principal FROM collection_acces ca "
        f"JOIN collection col ON col.id = ca.collection_id "
        f"WHERE NOT EXISTS (SELECT 1 FROM projet_acces pa WHERE pa.projet_id = {_PROJET_DE} "
        f"AND pa.genre = ca.genre AND pa.principal = ca.principal)")}
    attendus = {tuple(x) for x in f["acces_hors_projet"]}
    assert len(attendus) == 3 and attendus <= hors
    # Un sur une collection d'un projet ordinaire, un sur une collection du repli.
    projets = {_un(c, f"SELECT {_PROJET_DE} FROM collection col WHERE col.id = ?", (cid,))
               for cid, _, _ in attendus}
    assert projets == {f["projet_etude"], f["projet_repli"]}
    # Rien de tel dans un projet isolé (le test de la v38 l'y pose à la main).
    isoles = [tuple(r) for r in c.execute(
        f"SELECT ca.collection_id, ca.principal FROM collection_acces ca "
        f"JOIN collection col ON col.id = ca.collection_id "
        f"JOIN projet p ON p.id = {_PROJET_DE} "
        f"WHERE (p.bac_a_sable_de IS NOT NULL OR p.jeu = 1) AND NOT EXISTS ("
        f"SELECT 1 FROM projet_acces pa WHERE pa.projet_id = p.id "
        f"AND pa.genre = ca.genre AND pa.principal = ca.principal)")]
    assert isoles == []


def test_une_collection_que_la_responsable_ne_lit_pas_avec_un_album(v37):
    c, f = v37
    cid = f["collection_d_un_membre"]
    assert _un(c, "SELECT projet_id FROM collection WHERE id = ?", (cid,)) == f["projet_etude"]
    assert _un(c, "SELECT principal FROM collection_acces WHERE collection_id = ? "
                  "AND niveau = 'proprietaire'", (cid,)) == "sam"
    assert _un(c, "SELECT role FROM projet_acces WHERE projet_id = ? AND principal = 'sam'",
               (f["projet_etude"],)) == "membre"
    assert _un(c, "SELECT COUNT(*) FROM collection_acces WHERE collection_id = ? "
                  "AND principal = 'lea'", (cid,)) == 0
    assert _un(c, "SELECT collection_id FROM collection_album WHERE album_id = ?",
               (f["album_carnet_d_arrivant"],)) == cid


def test_des_copies_d_une_simple_ecrivaine_touchees_par_une_autre(v37):
    c, f = v37
    for album in f["copies_de_nora"]:
        assert _un(c, "SELECT creee_par FROM copie WHERE album_id = ?", (album,)) == "nora"
        assert {r[0] for r in c.execute(
            "SELECT agent FROM geste_sur_copie WHERE album_id = ?", (album,))} == {"nora", "lea"}
    assert _un(c, "SELECT niveau FROM collection_acces WHERE collection_id = ? "
                  "AND principal = 'nora'", (f["collection_b"],)) == "ecriture"


def test_des_demandes_d_effacement_en_attente_et_une_close(v37):
    c, f = v37
    d = f["demandes_v37"]

    def demande(i):
        return c.execute("SELECT d.genre, d.reponse, dd.album_id, dd.document_id FROM demande d "
                         "JOIN demande_document dd ON dd.demande_id = d.id WHERE d.id = ?",
                         (i,)).fetchone()

    def soeurs(document_id):
        return _un(c, "SELECT COUNT(*) FROM albums WHERE document_id = ?", (document_id,))

    attente = d["en_attente"]
    avec_soeur = demande(attente["suppression_avec_soeur"])
    assert (avec_soeur["genre"], avec_soeur["reponse"]) == ("suppression_document", None)
    assert soeurs(avec_soeur["document_id"]) > 1
    derniere = demande(attente["suppression_derniere_copie"])
    assert (derniere["genre"], derniere["reponse"]) == ("suppression_document", None)
    assert soeurs(derniere["document_id"]) == 1
    repartir = demande(attente["repartir"])
    assert (repartir["genre"], repartir["reponse"]) == ("repartir", None)
    assert _un(c, "SELECT cran FROM demande WHERE id = ?", (attente["repartir"],)) == "images"
    close = demande(d["close"])
    assert (close["genre"], close["reponse"]) == ("suppression_document", "refusee")


def test_un_compte_partage_responsable_d_un_projet(v37):
    c, f = v37
    login = f["compte_partage_responsable"]
    assert _un(c, "SELECT nature FROM utilisateur WHERE login = ?", (login,)) == "collectif"
    assert _un(c, "SELECT role FROM projet_acces WHERE projet_id = ? AND principal = ?",
               (f["projet_etude"], login)) == "responsable"
