"""ANN-7, le basculement — la migration v39, sur une VRAIE base v38.

La règle de Hugo (2026-10-16, `CLAUDE.md` § Schéma & migrations) : une migration se vérifie
sur une base de la version précédente qui a VÉCU. `tests/bases/v38-22580fc.sql` est faite par
le code de la production qui précède le basculement (I9 ; `22580fc`, refaite le 2026-11-13),
ses routes sous trois comptes : elle porte
le vocabulaire que la v39 retire (cinq tags posés onze fois, dont un d'un bac à sable, un
domaine, deux dimensions, des situations, un profil, une annotation qui ne porte que des
tags), un relevé dans une grille FERMÉE, et des actes annulables en dernier.

Ce que la v39 fait (`docs/ann7-tranche3-cadrage.md`, « La migration v39 » ; I5, I6 ; J2, J4,
J6, Hugo, 2026-11-06) :
1. les annotations SANS NOTE partent ; les sept tables du vocabulaire d'hier et leurs index
   sont détruits ;
2. l'index plein texte est recréé, `etiquettes` à la place de `tags_concat` — les libellés
   des relevés des grilles OUVERTES —, ses lignes recopiées ;
3. le plancher de Ctrl+Z ;
4. l'état d'une entrée (`grille_entree.etat`) : défini, sauf ce que le journal dit né en
   posant ; le drapeau de la grille de travail (`grille.travail`), et la grille de travail
   de chaque projet qui ne l'a pas, jamais le jeu.
Rien d'autre ne change : identifiants, notes, locuteurs, présences, relevés, passes, doutes,
grilles.
"""
import json
import sqlite3
from pathlib import Path

import pytest

import database
import journal
import main
import migration_v40
import undo
from config import GRILLE_DE_TRAVAIL_NOM

BASE_V38 = Path(__file__).resolve().parent / "bases" / "v38-22580fc.sql"
# Écrites ICI À LA MAIN : le test qui tirerait son attendu de la constante qu'il éprouve en
# serait le miroir.
TABLES_PARTIES = {"tags", "annotation_tags", "domaine", "attribut_dimension",
                  "attribut_valeur", "personnage_attribut", "region_attribut"}
INDEX_PARTIS = {"idx_anntags_tag", "idx_attrval_dim", "idx_persoattr_val", "idx_regattr_val",
                "idx_domaine_collection", "idx_dim_domaine", "idx_dim_collection",
                "idx_val_collection", "idx_tags_collection", "idx_tags_espace_label"}
# Ce qui ne doit pas bouger, ligne pour ligne.
INTACTES = ("albums", "planches", "regions", "personnages", "bulle_locuteur",
            "personnage_presence", "releve", "releve_mot", "releve_qualificatif", "passe",
            "doute", "doute_message", "grille_entree", "grille_variante", "tokens",
            "token_correction", "collection", "collection_acces", "projet", "projet_acces",
            "document", "copie", "demande", "contribution", "activite")


def _sql(db, q, p=()):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        r = [dict(x) for x in c.execute(q, p)]
        c.commit()
        return r
    finally:
        c.close()


def _faits() -> dict:
    faits = {}
    for ligne in BASE_V38.read_text(encoding="utf-8").splitlines():
        if not ligne.startswith("--"):
            break
        if ligne.startswith("--   ") and " : " in ligne:
            cle, val = ligne[5:].split(" : ", 1)
            faits[cle] = json.loads(val)
    return faits


@pytest.fixture
def vraie_v38(tmp_path, monkeypatch):
    """`tests/bases/v38-22580fc.sql`, chargée dans une base du test ; les dossiers d'images
    sont ceux du test, vides."""
    from pipeline import ingest
    db = tmp_path / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V38.read_text(encoding="utf-8"))
    c.close()
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    return db


def _lignes(db, t, sans=()):
    return sorted(json.dumps({k: v for k, v in r.items() if k not in sans}, sort_keys=True,
                             ensure_ascii=False) for r in _sql(db, f'SELECT * FROM "{t}"'))


def _cherche(db, expr):
    return sorted(r["region_id"] for r in _sql(
        db, "SELECT region_id FROM recherche WHERE recherche MATCH ?", (expr,)))


def _tables(db):
    return {r["name"] for r in _sql(db, "SELECT name FROM sqlite_master WHERE type = 'table'")}


def _index(db):
    return {r["name"] for r in _sql(db, "SELECT name FROM sqlite_master WHERE type = 'index'")}


def _poser_une_grille_ouverte(db):
    """Une grille OUVERTE « Lieux » du projet d'étude, posée par SQL (la vraie base n'en porte
    aucune) : l'entrée « lieu » à variantes, sa variante « forêt », une case « nuit » d'une
    liste « moments » ; un relevé sur la CASE des cinq types (ni texte ni note : aucune ligne
    d'index), un sur la bulle. Et le journal d'une entrée née EN POSANT (« ironie »), à côté
    d'une écrite (« lieu »)."""
    f = _faits()
    case, bulle = f["regions_cinq_types"]["case"], f["regions_cinq_types"]["bulle"]
    c = sqlite3.connect(db)
    try:
        gid = c.execute("INSERT INTO grille (projet_id, nom, ouverte) VALUES (?, 'Lieux', 1)",
                        (f["projet_etude"],)).lastrowid
        vid = c.execute("INSERT INTO grille_version (grille_id, numero, etat, cible) "
                        "VALUES (?, 1, 'vivante', 'case|bulle')", (gid,)).lastrowid
        c.execute("INSERT INTO grille_entree (version_id, cle, rang, forme, libelle) "
                  "VALUES (?, 'lieu', 0, 'variantes', 'lieu'), "
                  "(?, 'ironie', 1, 'qualificatifs', 'ironie')", (vid, vid))
        c.execute("UPDATE grille_entree SET liste_cle = 'moments' WHERE version_id = ? "
                  "AND cle = 'ironie'", (vid,))
        c.execute("INSERT INTO grille_variante (version_id, entree_cle, cle, libelle) "
                  "VALUES (?, 'lieu', 'foret', 'forêt')", (vid,))
        c.execute("INSERT INTO grille_liste (version_id, cle, libelle) "
                  "VALUES (?, 'moments', 'Moments')", (vid,))
        c.execute("INSERT INTO grille_qualificatif (version_id, liste_cle, cle, libelle) "
                  "VALUES (?, 'moments', 'nuit', 'nocturne')", (vid,))
        c.execute("INSERT INTO projet_grille (projet_id, grille_id, version_id) "
                  "VALUES (?, ?, ?)", (f["projet_etude"], gid, vid))
        c.execute("INSERT INTO releve (region_id, grille_id, version_id, entree_cle, "
                  "variante_cle, auteur) VALUES (?, ?, ?, 'lieu', 'foret', 'lea')",
                  (case, gid, vid))
        rid = c.execute("INSERT INTO releve (region_id, grille_id, version_id, entree_cle, "
                        "auteur) VALUES (?, ?, ?, 'ironie', 'lea')", (bulle, gid, vid)).lastrowid
        c.execute("INSERT INTO releve_qualificatif (releve_id, qualificatif_cle) "
                  "VALUES (?, 'nuit')", (rid,))
        c.execute("INSERT INTO evenement (type, cible_table, cible_id, agent, agent_type, "
                  "apres) VALUES ('modification', 'grille', ?, 'lea', 'humain', ?)",
                  (gid, json.dumps({"entree_neuve": {"version": 1, "cle": "ironie",
                                                     "libelle": "ironie",
                                                     "forme": "simple"}})))
        c.commit()
    finally:
        c.close()
    return {"grille": gid, "version": vid, "case": case, "bulle": bulle}


def test_la_base_chargee_est_bien_une_v38_qui_a_vecu(vraie_v38):
    f = _faits()
    assert _sql(vraie_v38, "PRAGMA user_version")[0]["user_version"] == 38
    assert TABLES_PARTIES <= _tables(vraie_v38)
    assert INDEX_PARTIS <= _index(vraie_v38)
    assert {k: f["comptes"][k] for k in ("tags", "annotation_tags", "region_attribut",
                                         "personnage_attribut")} == {
        "tags": 5, "annotation_tags": 11, "region_attribut": 3, "personnage_attribut": 1}
    assert f["annotations_sans_note"] == 1
    # Un mot qui n'est qu'un tag se trouve encore, avant ; le relevé est dans une grille fermée.
    assert _cherche(vraie_v38, "onomatopee") == [f["region_annotee_de_tags_seuls"]]
    assert _sql(vraie_v38, "SELECT DISTINCT g.ouverte FROM releve r JOIN grille g "
                           "ON g.id = r.grille_id") == [{"ouverte": 0}]
    # Ctrl+Z offre encore des actes d'avant à deux comptes.
    conn = database.get_connection()
    try:
        assert undo.derniere_action_annulable(conn, "lea") is not None
        assert undo.derniere_action_annulable(conn, "sam") is not None
    finally:
        conn.close()


def test_une_vraie_base_v38_migre_sans_rien_perdre(vraie_v38):
    f = _faits()
    avant = {t: _lignes(vraie_v38, t, sans=("etat",)) for t in INTACTES}
    grilles_avant = {t: _lignes(vraie_v38, t) for t in ("grille", "grille_version",
                                                         "projet_grille")}
    annotations = _sql(vraie_v38, "SELECT * FROM annotations ORDER BY id")
    evenements = _lignes(vraie_v38, "evenement")
    seq = {r["name"]: r["seq"] for r in _sql(vraie_v38, "SELECT * FROM sqlite_sequence")}

    database.init_db()

    assert _sql(vraie_v38, "PRAGMA user_version")[0]["user_version"] == database.SCHEMA_VERSION
    assert database.SCHEMA_VERSION >= 39
    # 1. Les sept tables et leurs index sont partis.
    assert not TABLES_PARTIES & _tables(vraie_v38)
    assert not INDEX_PARTIS & _index(vraie_v38)
    # L'annotation qui ne portait que des tags est partie ; celles qui portent une note sont
    # là, telles quelles.
    apres = _sql(vraie_v38, "SELECT * FROM annotations ORDER BY id")
    assert apres == [a for a in annotations if (a["note"] or "").strip()]
    assert len(apres) == len(annotations) - 1
    assert f["region_annotee_de_tags_seuls"] not in {a["region_id"] for a in apres}
    # Le reste, ligne pour ligne : identifiants, locuteurs, présences, relevés, passes, doutes.
    assert {t: _lignes(vraie_v38, t, sans=("etat",)) for t in INTACTES} == avant
    # Les grilles d'avant sont là, sans drapeau ; seules les grilles de travail s'ajoutent,
    # avec leur version et leur activation.
    travail = {r["id"] for r in _sql(vraie_v38, "SELECT id FROM grille WHERE travail = 1")}
    for t, cle in (("grille", "id"), ("grille_version", "grille_id"),
                   ("projet_grille", "grille_id")):
        # La v40 pose l'identifiant et l'origine d'une grille (`migration_v40`).
        apres = _lignes(vraie_v38, t, sans=("travail", *migration_v40.COLONNES_V40.get(t, ())))
        assert set(grilles_avant[t]) <= set(apres), t
        assert {json.loads(l)[cle] for l in set(apres) - set(grilles_avant[t])} == travail, t
    # Le journal n'est pas touché : il ne gagne que la naissance des grilles de travail.
    assert set(evenements) <= set(_lignes(vraie_v38, "evenement"))
    nes = [e for e in _sql(vraie_v38, "SELECT * FROM evenement WHERE id > 250")]
    assert nes and all(e["cible_table"] == "grille" for e in nes), nes
    assert {t: n for t, n in ((r["name"], r["seq"]) for r in _sql(
        vraie_v38, "SELECT * FROM sqlite_sequence")) if t in seq and t not in (
        "grille", "grille_version")} == {t: n for t, n in seq.items()
                                         if t not in ("grille", "grille_version")}
    assert _sql(vraie_v38, "PRAGMA foreign_key_check") == []
    assert _sql(vraie_v38, "PRAGMA integrity_check")[0]["integrity_check"] == "ok"


def test_la_recherche_trouve_ce_qu_elle_trouvait_et_plus_les_tags(vraie_v38):
    f = _faits()
    texte = _cherche(vraie_v38, "otage")
    lemme = _cherche(vraie_v38, "lemmes : savoir")
    note = _cherche(vraie_v38, "note : source")
    assert texte and lemme and note, "prémisse : la vraie base est indexée"
    lignes = _sql(vraie_v38, "SELECT COUNT(*) AS n FROM recherche")[0]["n"]
    database.init_db()
    colonnes = [r["name"] for r in _sql(vraie_v38, "PRAGMA table_info(recherche)")]
    assert colonnes == ["region_id", "ocr_texte", "note", "etiquettes", "lemmes"]
    assert _cherche(vraie_v38, "otage") == texte
    assert _cherche(vraie_v38, "lemmes : savoir") == lemme
    assert _cherche(vraie_v38, "note : source") == note
    # Un mot qui n'était qu'un tag ne trouve plus rien — ni « cri », que porte aussi un relevé
    # d'une grille FERMÉE (hors des étiquettes).
    for ancien in ("onomatopee", "dialogue", "essai", "cri"):
        assert _cherche(vraie_v38, ancien) == [], ancien
    assert _sql(vraie_v38, "SELECT COUNT(*) AS n FROM recherche")[0]["n"] == lignes
    # La région aux seuls tags garde sa ligne pour son texte.
    assert f["region_annotee_de_tags_seuls"] in _cherche(vraie_v38, "traire")


def test_les_etiquettes_des_grilles_ouvertes_entrent_dans_l_index(vraie_v38):
    """J6 : la recopie remplit `etiquettes` en SQL — l'entrée, sa variante, ses
    qualificatifs —, y compris pour une case qui n'avait pas de ligne ; une grille fermée
    n'y entre pas."""
    d = _poser_une_grille_ouverte(vraie_v38)
    assert _cherche(vraie_v38, "otage") and d["case"] not in [
        r["region_id"] for r in _sql(vraie_v38, "SELECT region_id FROM recherche")]
    database.init_db()
    assert _cherche(vraie_v38, "etiquettes : foret") == [d["case"]]
    assert _cherche(vraie_v38, "etiquettes : lieu") == [d["case"]]
    assert _cherche(vraie_v38, "etiquettes : ironie") == [d["bulle"]]
    assert _cherche(vraie_v38, "etiquettes : nocturne") == [d["bulle"]]
    assert _cherche(vraie_v38, "cri") == []
    # La bulle garde son texte et sa note dans la même ligne.
    assert d["bulle"] in _cherche(vraie_v38, "note : relever")
    # Et la réindexation d'une région les recalcule à l'identique.
    conn = database.get_connection()
    try:
        assert database._region_index_payload(conn, d["case"])[2] == "lieu forêt"
        assert database._region_index_payload(conn, d["bulle"])[2] == "ironie nocturne"
        database.reindex_region(conn, d["case"])      # une case : ni texte, ni moteur de langue
        conn.commit()
    finally:
        conn.close()
    assert _cherche(vraie_v38, "etiquettes : foret") == [d["case"]]


def test_ctrl_z_ne_rend_aucun_acte_d_avant_et_rend_un_acte_d_apres(vraie_v38):
    database.init_db()
    plancher = _sql(vraie_v38, "SELECT valeur FROM meta WHERE cle = 'plancher_annulation'")
    assert plancher == [{"valeur": "250"}]
    conn = database.get_connection()
    try:
        for agent in ("lea", "sam", "hugo", undo.TOUS):
            assert undo.derniere_action_annulable(conn, agent) is None, agent
        region = _faits()["regions_cinq_types"]["bulle"]
        eid = journal.journaliser(conn, "modification", "annotations", region, agent="lea",
                                  avant={"note": "à relever, vu deux fois"},
                                  apres={"note": "après la v39"})
        conn.commit()
        assert undo.derniere_action_annulable(conn, "lea")["id"] == eid
        assert eid > 250
    finally:
        conn.close()


def test_rejouee_la_migration_ne_change_rien(vraie_v38):
    _poser_une_grille_ouverte(vraie_v38)
    database.init_db()

    def etat():
        return ({t: _lignes(vraie_v38, t) for t in (*INTACTES, "grille", "grille_entree",
                                                     "annotations", "evenement", "meta")},
                _sql(vraie_v38, "SELECT type, name, sql FROM sqlite_master ORDER BY name"),
                _sql(vraie_v38, "SELECT * FROM recherche ORDER BY region_id"))
    avant = etat()
    _sql(vraie_v38, "PRAGMA user_version = 38")
    database.init_db()
    assert etat() == avant


def test_chaque_projet_recoit_sa_grille_de_travail_sauf_le_jeu(vraie_v38):
    f = _faits()
    projets = {r["id"] for r in _sql(vraie_v38, "SELECT id FROM projet")}
    database.init_db()
    travail = _sql(vraie_v38, "SELECT g.projet_id, g.nom, g.ouverte, g.travail, g.cree_par, "
                              "pg.version_id IS NOT NULL AS active FROM grille g "
                              "LEFT JOIN projet_grille pg ON pg.grille_id = g.id "
                              "WHERE g.travail = 1 ORDER BY g.projet_id")
    assert {g["projet_id"] for g in travail} == projets - {f["projet_de_jeu"]}
    assert all((g["nom"], g["ouverte"], g["cree_par"], g["active"]) == (
        GRILLE_DE_TRAVAIL_NOM, 1, None, 1) for g in travail), travail
    assert f["projet_de_jeu"] not in {r["projet_id"] for r in _sql(
        vraie_v38, "SELECT projet_id FROM grille")}
    # Le journal les dit écrites par la MIGRATION, pas par un humain sans nom : leur
    # naissance et leur activation, deux actes par grille, sous le nom du logiciel.
    actes = _sql(vraie_v38, "SELECT type, agent, agent_type FROM evenement "
                            "WHERE cible_table = 'grille' AND id > (SELECT valeur FROM meta "
                            "WHERE cle = 'plancher_annulation') ORDER BY id")
    assert len(actes) == 2 * len(travail)
    assert {(a["agent"], a["agent_type"]) for a in actes} == {
        (database.AGENT_MIGRATION_V39, "moteur")}
    assert {a["type"] for a in actes} == {"creation", "lien"}
    # Au plus une par projet : la base le tient.
    c = sqlite3.connect(vraie_v38)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("UPDATE grille SET travail = 1 WHERE travail = 0 AND projet_id = ?",
                      (f["projet_etude"],))
    finally:
        c.close()


def test_une_grille_de_travail_deja_nee_recoit_le_drapeau_sans_doubler(vraie_v38):
    """Une grille de travail née avant la migration (le code du 2026-11-05 en faisait naître
    une, que le journal dit `travail`) reçoit le drapeau — même renommée — et le projet n'en
    reçoit pas une seconde. Une grille d'un AUTRE nom qui porterait celui de la grille de
    travail lui laisse le sien."""
    f = _faits()
    c = sqlite3.connect(vraie_v38)
    try:
        nee = c.execute("INSERT INTO grille (projet_id, nom, ouverte) "
                        "VALUES (?, 'Mes étiquettes', 1)", (f["projet_etude"],)).lastrowid
        c.execute("INSERT INTO grille_version (grille_id, numero, etat) "
                  "VALUES (?, 1, 'vivante')", (nee,))
        c.execute("INSERT INTO evenement (type, cible_table, cible_id, agent_type, apres) "
                  "VALUES ('creation', 'grille', ?, 'humain', ?)",
                  (nee, json.dumps({"nom": GRILLE_DE_TRAVAIL_NOM, "travail": True})))
        homonyme = c.execute("INSERT INTO grille (projet_id, nom, ouverte) VALUES (?, ?, 1)",
                             (f["projet_repli"], GRILLE_DE_TRAVAIL_NOM)).lastrowid
        c.commit()
    finally:
        c.close()
    database.init_db()
    etude = _sql(vraie_v38, "SELECT id, nom FROM grille WHERE projet_id = ? AND travail = 1",
                 (f["projet_etude"],))
    assert etude == [{"id": nee, "nom": "Mes étiquettes"}]
    repli = _sql(vraie_v38, "SELECT id, nom, travail FROM grille WHERE projet_id = ? "
                            "ORDER BY id", (f["projet_repli"],))
    assert {"id": homonyme, "nom": GRILLE_DE_TRAVAIL_NOM, "travail": 0} in repli
    assert [g["nom"] for g in repli if g["travail"]] == [f"{GRILLE_DE_TRAVAIL_NOM} 2"]


@pytest.mark.parametrize("note, posee", [
    (None, False), ("", False), ("   ", False), ("\n", False), (" \t\r\n\v\f ", False),
    ("\xa0 　", False), (" ironie ", True), ("\n?", True), ("\xa0?", True),
])
def test_une_note_posee_est_la_meme_en_sql_et_en_python(note, posee):
    """Une seule règle de la note VIDE, des deux côtés : `SQL_NOTE_POSEE` (la migration, la
    copie, Ctrl+Z, la re-segmentation) et `annotation_vide` (la route, Ctrl+Z). `TRIM` seul
    disait posée une note d'un saut de ligne, que `str.strip()` disait vide."""
    c = sqlite3.connect(":memory:")
    try:
        sql = bool(c.execute(f"SELECT {database.SQL_NOTE_POSEE} FROM (SELECT ? AS note)",
                             (note,)).fetchone()[0])
    finally:
        c.close()
    assert sql is posee
    assert database.annotation_vide(note) is not posee


def test_l_index_recopie_dit_ce_que_la_reindexation_ecrirait(vraie_v38):
    """La recopie de l'index (sans moteur de langue) écrit, région par région, ce que
    `reindex_region` écrirait hors lemmes : des étiquettes absentes à '', jamais NULL ; une
    note qui n'est pas posée — d'espaces, d'un saut de ligne —, partie avec son annotation,
    ne garde ni sa valeur ni sa ligne. Une grille ouverte porte des étiquettes."""
    _poser_une_grille_ouverte(vraie_v38)
    c = sqlite3.connect(vraie_v38)
    try:
        vides = [r[0] for r in c.execute(
            "SELECT id FROM regions WHERE ocr_texte IS NULL AND id NOT IN "
            "(SELECT region_id FROM annotations) AND id NOT IN (SELECT region_id FROM releve "
            "WHERE region_id IS NOT NULL) ORDER BY id LIMIT 2")]
        texte = c.execute("SELECT id FROM regions WHERE TRIM(COALESCE(ocr_texte, '')) <> '' "
                          "AND id NOT IN (SELECT region_id FROM annotations) "
                          "ORDER BY id LIMIT 1").fetchone()[0]
        for rid, note in ((vides[0], "   "), (vides[1], "\n"), (texte, " \r\n")):
            c.execute("INSERT INTO annotations (region_id, note) VALUES (?, ?)", (rid, note))
            c.execute("DELETE FROM recherche WHERE region_id = ?", (rid,))
            ocr = c.execute("SELECT COALESCE(ocr_texte, '') FROM regions WHERE id = ?",
                            (rid,)).fetchone()[0]
            c.execute("INSERT INTO recherche (region_id, ocr_texte, note, tags_concat, lemmes) "
                      "VALUES (?, ?, ?, 'un-tag', '')", (rid, ocr, note))
        c.commit()
    finally:
        c.close()
    database.init_db()
    assert _sql(vraie_v38, "SELECT COUNT(*) AS n FROM recherche WHERE etiquettes IS NULL") == [
        {"n": 0}]
    conn = database.get_connection()
    try:
        index = {r["region_id"]: (r["ocr_texte"] or "", r["note"] or "", r["etiquettes"])
                 for r in conn.execute("SELECT * FROM recherche")}
        ecarts = {}
        for (rid,) in conn.execute("SELECT id FROM regions ORDER BY id").fetchall():
            p = database._region_index_payload(conn, rid)
            attendu = p if any(p) else None
            if index.get(rid) != attendu:
                ecarts[rid] = (index.get(rid), attendu)
    finally:
        conn.close()
    assert not ecarts, ecarts
    assert vides[0] not in index and vides[1] not in index
    assert index[texte][1] == ""
    assert any(e for _, _, e in index.values())


def test_effacer_un_bac_a_sable_ne_passe_rien_sous_le_plancher(vraie_v38):
    """L'effacement d'un bac à sable PASSE les gestes encore annulables de ses régions (une
    trace `abandon` par acte) : ceux d'avant le plancher ne l'étaient plus, il n'y a rien à
    passer ni à compter. La vraie base porte des gestes dans ses deux bacs à sable, tous
    d'avant la migration ; un geste d'APRÈS, sur une région du premier, l'est encore."""
    import autorisation
    import socle
    f = _faits()
    database.init_db()
    conn = database.get_connection()
    try:
        plancher = undo.plancher(conn)
        premier, *autres = f["bacs_a_sable"]
        region = conn.execute(
            "SELECT r.id FROM regions r JOIN planches p ON p.id = r.planche_id "
            "JOIN albums a ON a.id = p.album_id "
            f"WHERE {database.sql_projet_d_album('a')} = ? ORDER BY r.id LIMIT 1",
            (premier,)).fetchone()[0]
        journal.journaliser(conn, "modification", "regions", region, agent="nora",
                            agent_type="humain", avant={"x": 0}, apres={"x": 1})
        conn.commit()
        bilans = []
        for bac in f["bacs_a_sable"]:
            bilans.append(socle._effacer_bac_a_sable(conn, autorisation.TOTALE, bac,
                                                     motif="test"))
            conn.commit()
        sous = conn.execute("SELECT COUNT(*) FROM evenement WHERE type = 'abandon' "
                            "AND cible_table = 'annulation' AND cible_id <= ?",
                            (plancher,)).fetchone()[0]
        apres = conn.execute("SELECT COUNT(*) FROM evenement WHERE type = 'abandon' "
                             "AND cible_table = 'annulation' AND cible_id > ?",
                             (plancher,)).fetchone()[0]
    finally:
        conn.close()
    assert sous == 0
    assert [b["gestes_passes"] for b in bilans] == [1] + [0] * len(autres), bilans
    assert apres == 1


class _Panne(Exception):
    pass


@pytest.mark.parametrize("colonne, ecriture", [
    ("etat", "UPDATE grille_entree"),
    ("travail", "UPDATE grille SET travail"),
])
def test_une_panne_entre_la_colonne_et_ses_marques_ne_les_perd_pas(vraie_v38, monkeypatch,
                                                                   colonne, ecriture):
    """La colonne naît d'un `ALTER`, que le module `sqlite3` valide seul s'il n'y a pas de
    transaction ouverte ; ses marques — l'état provisoire, le drapeau — d'un `UPDATE`. Une
    migration qui tombe entre les deux laisse la colonne sans ses marques : la relance doit
    les poser, et non les sauter parce que la colonne est là. La connexion de la panne VALIDE
    chaque `ALTER` dès qu'il passe — le pire cas, celui où rien d'autre n'était ouvert — puis
    lève sur l'`UPDATE` qui suit."""
    d = _poser_une_grille_ouverte(vraie_v38)
    f = _faits()
    c = sqlite3.connect(vraie_v38)
    try:
        nee = c.execute("INSERT INTO grille (projet_id, nom, ouverte) "
                        "VALUES (?, 'Mes étiquettes', 1)", (f["projet_etude"],)).lastrowid
        c.execute("INSERT INTO evenement (type, cible_table, cible_id, agent_type, apres) "
                  "VALUES ('creation', 'grille', ?, 'humain', ?)",
                  (nee, json.dumps({"nom": GRILLE_DE_TRAVAIL_NOM, "travail": True})))
        c.commit()
    finally:
        c.close()

    class Conn(sqlite3.Connection):
        def execute(self, sql, *a):
            if sql.lstrip().startswith(ecriture):
                raise _Panne(ecriture)
            r = super().execute(sql, *a)
            if f"ADD COLUMN {colonne}" in sql:
                self.commit()
            return r

    vraie = database.get_connection

    def en_panne():
        conn = sqlite3.connect(database.DB_PATH, check_same_thread=False, factory=Conn)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.create_function("cle_tag", 1, database.cle_tag, deterministic=True)
        return conn

    monkeypatch.setattr(database, "get_connection", en_panne)
    with pytest.raises(_Panne):
        database.init_db()
    monkeypatch.setattr(database, "get_connection", vraie)
    assert _sql(vraie_v38, "PRAGMA user_version")[0]["user_version"] == 38
    assert colonne in {r["name"] for r in _sql(
        vraie_v38, "PRAGMA table_info(grille_entree)" if colonne == "etat"
        else "PRAGMA table_info(grille)")}
    database.init_db()
    assert _sql(vraie_v38, "PRAGMA user_version")[0]["user_version"] == database.SCHEMA_VERSION
    assert _sql(vraie_v38, "SELECT etat FROM grille_entree WHERE version_id = ? "
                           "AND cle = 'ironie'", (d["version"],)) == [{"etat": "provisoire"}]
    assert _sql(vraie_v38, "SELECT id FROM grille WHERE projet_id = ? AND travail = 1",
                (f["projet_etude"],)) == [{"id": nee}]


def test_l_etat_des_entrees_existantes(vraie_v38):
    """J4 : défini pour tout l'existant — les grilles fermées comme une entrée ÉCRITE d'une
    grille ouverte —, provisoire pour la seule entrée que le journal dit née en posant."""
    d = _poser_une_grille_ouverte(vraie_v38)
    database.init_db()
    etats = {(r["grille_id"], r["cle"]): r["etat"] for r in _sql(
        vraie_v38, "SELECT v.grille_id, e.cle, e.etat FROM grille_entree e "
                   "JOIN grille_version v ON v.id = e.version_id")}
    assert etats.pop((d["grille"], "ironie")) == "provisoire"
    assert etats and set(etats.values()) == {"defini"}, etats


def test_une_base_neuve_s_initialise(tmp_path, monkeypatch):
    db = tmp_path / "neuve.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db)
    database.init_db()
    assert _sql(db, "PRAGMA user_version")[0]["user_version"] == database.SCHEMA_VERSION
    assert not TABLES_PARTIES & _tables(db)
    assert [r["name"] for r in _sql(db, "PRAGMA table_info(recherche)")] == [
        "region_id", "ocr_texte", "note", "etiquettes", "lemmes"]
    assert "idx_grille_travail" in _index(db)
    assert _sql(db, "SELECT g.travail FROM grille g JOIN projet p ON p.id = g.projet_id "
                    "WHERE p.repli = 1") == [{"travail": 1}]
    database.init_db()
    assert _sql(db, "SELECT COUNT(*) AS n FROM grille")[0]["n"] == 1


def test_la_base_migree_a_la_forme_d_une_base_neuve(vraie_v38, tmp_path):
    """`grille`, `grille_entree` et l'index plein texte, colonne par colonne : sur l'une les
    colonnes naissent de l'`ALTER` et de la recréation, sur l'autre du `CREATE`."""
    database.init_db()
    neuve = tmp_path / "neuve.sqlite"
    c = sqlite3.connect(neuve)
    c.executescript(database.SCHEMA_SQL)
    c.executescript(database._FTS_SQL)
    c.close()

    def forme(db):
        return {t: [(x["name"], x["type"], x["notnull"], x["dflt_value"])
                    for x in _sql(db, f"PRAGMA table_info({t})")]
                for t in ("grille", "grille_entree", "recherche", "annotations")}
    assert forme(vraie_v38) == forme(neuve)
