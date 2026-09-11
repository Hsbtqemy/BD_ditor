"""NLP-2 — ce que l'annotateur a VU : le modèle, et sa proposition (v28).

Un champ de correction NULL veut dire « j'accepte la proposition du modèle ». Tant que la
proposition n'était pas gardée, le rapport d'accord la relisait dans `tokens`, que chaque
réindexation régénère : après un passage à `lg`, un mot validé sous `sm` comptait comme un
accord avec `lg`, dont personne n'avait vu la proposition.

Ces tests éprouvent les colonnes là où elles peuvent se perdre (migration, ré-ancrage), puis
ce que le rapport en fait. Tokens et corrections semés EN DIRECT, comme dans
`test_accord.py` : la couche spaCy est optionnelle.
"""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import accord
import database
from pipeline import nlp

REPO_ROOT = Path(__file__).resolve().parent.parent

SM, LG = "fr_core_news_sm-3.8.0", "fr_core_news_lg-3.8.0"


def _region(client, planche_id):
    return client.post(f"/api/planches/{planche_id}/regions",
                       json={"type": "bulle", "x": 1, "y": 1, "w": 10, "h": 10}).json()["id"]


def _conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _tokens(db_path, region_id, tokens):
    """tokens : (ordre, texte, lemme, pos, morph) — ce que dit l'index d'AUJOURD'HUI."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(
            "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
            "VALUES (?,?,?,?,?,?)", [(region_id, *t) for t in tokens])
        conn.commit()
    finally:
        conn.close()


def _correction(db_path, region_id, ordre, forme, etat="valide", lemme=None, pos=None,
                morph=None, modele=None, vu=None):
    """Une correction, et ce que l'annotateur a vu : `vu` = (lemme, pos, morph) proposés
    par `modele`. Sans `vu` : une correction antérieure à la v28, qui n'a rien gardé."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO token_correction (region_id, ordre, forme, lemme, pos, morph, etat, "
            " obsolete, modele_auto, auto_lemme, auto_pos, auto_morph) "
            "VALUES (?,?,?,?,?,?,?,0,?,?,?,?)",
            (region_id, ordre, forme, lemme, pos, morph, etat, modele,
             *(vu or (None, None, None))))
        conn.commit()
    finally:
        conn.close()


def _rapport(db_path, **kw):
    conn = _conn(db_path)
    try:
        return accord.rapport(conn, **kw)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Là où les colonnes peuvent se perdre
# --------------------------------------------------------------------------- #
def test_la_migration_v28_laisse_les_corrections_anterieures_a_null(client, album, planche,
                                                                     db_path):
    """AUCUN rattrapage : relire `tokens` aujourd'hui serait deviner ce qui s'affichait hier.
    Une correction antérieure arrive à NULL, et le rapport la lit comme avant la v28."""
    r = _region(client, planche["id"])
    _tokens(db_path, r, [(0, "CHAT", "chat", "NOUN", "")])
    conn = sqlite3.connect(db_path)
    try:
        for col in database.COLONNES_VU:
            conn.execute(f"ALTER TABLE token_correction DROP COLUMN {col}")
        conn.execute("INSERT INTO token_correction (region_id, ordre, forme, etat) "
                     "VALUES (?, 0, 'CHAT', 'valide')", (r,))
        conn.execute("PRAGMA user_version = 27")
        conn.commit()
    finally:
        conn.close()
    database.init_db()
    conn = _conn(db_path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
        ligne = conn.execute("SELECT * FROM token_correction WHERE region_id = ?",
                             (r,)).fetchone()
    finally:
        conn.close()
    assert all(ligne[k] is None for k in database.COLONNES_VU)
    rep = _rapport(db_path)
    assert rep["champs"]["pos"]["accord"] == 1
    assert rep["par_modele"] == [{"modele": None, "revus": 1}]


def test_le_reancrage_garde_ce_qui_a_ete_vu(client, album, planche, db_path):
    """Le ré-ancrage réécrit ses lignes colonne par colonne : une colonne qu'il oublierait
    repartirait à NULL à chaque réindexation — y compris celle que la route de correction
    lance juste après avoir écrit. Une survivante qui a bougé, et une orpheline."""
    r = _region(client, planche["id"])
    _tokens(db_path, r, [(0, "UN", "un", "DET", ""), (1, "CHAT", "chat", "NOUN", "")])
    _correction(db_path, r, 0, "UN", modele=SM, vu=("un", "DET", "Definite=Ind"))
    _correction(db_path, r, 1, "CHAT", "corrige", pos="PROPN", modele=SM,
                vu=("chat", "NOUN", ""))
    conn = _conn(db_path)
    try:
        database._reancrer_corrections(conn, r, [
            {"ordre": 0, "texte": "LE"}, {"ordre": 1, "texte": "GROS"},
            {"ordre": 2, "texte": "CHAT"}])
        conn.commit()
        lignes = {x["forme"]: x for x in conn.execute(
            "SELECT * FROM token_correction WHERE region_id = ?", (r,))}
    finally:
        conn.close()
    assert (lignes["CHAT"]["ordre"], lignes["CHAT"]["obsolete"]) == (2, 0)
    assert lignes["UN"]["obsolete"] == 1
    assert tuple(lignes["CHAT"][k] for k in database.COLONNES_VU) == (SM, "chat", "NOUN", "")
    assert tuple(lignes["UN"][k] for k in database.COLONNES_VU) == (
        SM, "un", "DET", "Definite=Ind")


# --------------------------------------------------------------------------- #
# Ce que le rapport en fait
# --------------------------------------------------------------------------- #
def test_un_mot_valide_sous_sm_ne_vaut_pas_accord_avec_lg(client, album, planche, db_path):
    """Le cas qui a décidé la v28. L'annotateur a validé CHAT tel que `sm` le proposait
    (NOUN) ; on réindexe avec `lg`, qui dit VERB. Relue contre `tokens`, la case vide
    comptait comme un accord de `lg` — avec une proposition que personne n'a vue."""
    r = _region(client, planche["id"])
    _tokens(db_path, r, [(0, "CHAT", "chat", "VERB", "")])             # ce que dit lg
    _correction(db_path, r, 0, "CHAT", modele=SM, vu=("chat", "NOUN", ""))
    rep = _rapport(db_path)
    assert rep["champs"]["pos"] == {"revus": 1, "accord": 0, "taux": 0.0}
    assert rep["champs"]["lemme"]["accord"] == 1 and rep["champs"]["morph"]["accord"] == 1
    assert rep["confusion_pos"] == [{"auto": "VERB", "humain": "NOUN", "n": 1}]
    assert rep["a_la_relecture"] is None and rep["filtre_modele"] is None


def test_sans_changement_de_modele_le_chiffre_est_celui_d_avant(client, album, planche,
                                                                 db_path):
    """Tant que l'index n'a pas changé, garder la proposition ne change AUCUN chiffre : la
    même région, relue avant la v28 puis après, compte exactement autant."""
    toks = [(0, "CHAT", "chat", "NOUN", ""), (1, "COURT", "courir", "VERB", ""),
            (2, "BELLE", "belle", "ADJ", "")]
    corrs = [(0, "CHAT", "valide", None, None, None),
             (1, "COURT", "corrige", None, "NOUN", None),
             (2, "BELLE", "corrige", "beau", None, None)]
    avant = _region(client, planche["id"])
    _tokens(db_path, avant, toks)
    for c in corrs:
        _correction(db_path, avant, *c)
    seul = _rapport(db_path)

    apres = _region(client, planche["id"])
    _tokens(db_path, apres, toks)
    for c, t in zip(corrs, toks):
        _correction(db_path, apres, *c, modele=SM, vu=t[2:])
    double = _rapport(db_path)

    assert double["revus"] == 2 * seul["revus"] == 6
    for ch in accord.CHAMPS:
        assert double["champs"][ch]["accord"] == 2 * seul["champs"][ch]["accord"]
    assert double["confusion_pos"] == [{"auto": "VERB", "humain": "NOUN", "n": 2}]


def test_rien_vaut_rien(client, album, planche, db_path):
    """« Pas de valeur » s'écrit NULL dans un token semé ou importé, '' dans un relevé ou
    une morpho spaCy vide. Accepter l'absence est un accord, quelle que soit la graphie —
    c'est ce que comptait la lecture d'avant la v28 (`c.pos IS NULL`), et une égalité SQL
    nue le perdrait : NULL = NULL n'est pas vrai."""
    avant, apres = _region(client, planche["id"]), _region(client, planche["id"])
    _tokens(db_path, avant, [(0, "HEIN", "hein", None, None)])
    _tokens(db_path, apres, [(0, "HEIN", "hein", None, None)])
    _correction(db_path, avant, 0, "HEIN")                               # avant la v28
    _correction(db_path, apres, 0, "HEIN", modele=SM, vu=("hein", "", ""))
    rep = _rapport(db_path, modele=SM)
    assert rep["a_la_relecture"]["champs"]["pos"]["accord"] == 1
    tout = _rapport(db_path)
    assert tout["champs"]["pos"]["accord"] == tout["champs"]["morph"]["accord"] == 2


def test_restreint_a_sm_le_rapport_met_sm_et_lg_face_aux_memes_relectures(client, album,
                                                                          planche, db_path):
    """Après le passage à `lg` : restreint aux relectures faites sous `sm`, le rapport met
    côte à côte l'index actuel (`lg`) et `sm` au moment de la relecture. La relecture faite
    sous `lg` sort de l'échantillon."""
    r = _region(client, planche["id"])
    _tokens(db_path, r, [(0, "CHAT", "chat", "VERB", ""), (1, "RIT", "rire", "VERB", ""),
                         (2, "BOF", "bof", "INTJ", "")])                 # ce que dit lg
    _correction(db_path, r, 0, "CHAT", modele=SM, vu=("chat", "NOUN", ""))   # sm juste
    _correction(db_path, r, 1, "RIT", "corrige", pos="VERB", modele=SM,
                vu=("rire", "NOUN", ""))                                     # sm faux
    _correction(db_path, r, 2, "BOF", modele=LG, vu=("bof", "INTJ", ""))
    rep = _rapport(db_path, modele=SM)
    assert rep["filtre_modele"] == SM and rep["revus"] == 2
    assert rep["champs"]["pos"]["accord"] == 1                      # lg : RIT oui, CHAT non
    assert rep["confusion_pos"] == [{"auto": "VERB", "humain": "NOUN", "n": 1}]
    rel = rep["a_la_relecture"]
    assert rel["modele"] == SM and rel["champs"]["pos"]["accord"] == 1   # sm : l'inverse
    assert rel["confusion_pos"] == [{"auto": "NOUN", "humain": "VERB", "n": 1}]


def test_la_repartition_par_modele_decrit_tout_l_echantillon(client, album, planche, db_path):
    """Le filtre restreint la mesure, jamais la répartition : on doit voir de quoi
    l'échantillon est mêlé, y compris la part d'avant la v28."""
    r = _region(client, planche["id"])
    _tokens(db_path, r, [(o, f"M{o}", f"m{o}", "NOUN", "") for o in range(4)])
    _correction(db_path, r, 0, "M0", modele=SM, vu=("m0", "NOUN", ""))
    _correction(db_path, r, 1, "M1", modele=LG, vu=("m1", "NOUN", ""))
    _correction(db_path, r, 2, "M2", modele=LG, vu=("m2", "NOUN", ""))
    _correction(db_path, r, 3, "M3")
    rep = _rapport(db_path, modele=LG)
    assert rep["revus"] == 2
    assert rep["par_modele"] == [{"modele": LG, "revus": 2}, {"modele": None, "revus": 1},
                                 {"modele": SM, "revus": 1}]


# --------------------------------------------------------------------------- #
# Les routes qui écrivent
# --------------------------------------------------------------------------- #
@pytest.fixture
def modele_charge(monkeypatch):
    """Un modèle factice et déterministe, dont on change le nom et l'étiquette qu'il donne à
    tout mot : c'est tout ce qu'il faut pour jouer un passage de `sm` à `lg` sans spaCy, et
    garder des tokens qui survivent aux réindexations que lancent les routes."""
    etat = {"modele": SM, "pos": "NOUN"}

    def analyse(texte):
        toks = [{"ordre": i, "texte": mot, "lemme": mot.lower(), "pos": etat["pos"],
                 "morph": ""} for i, mot in enumerate((texte or "").split())]
        return " ".join(t["lemme"] for t in toks), toks

    monkeypatch.setattr(nlp, "analyse", analyse)
    monkeypatch.setattr(nlp, "model_info", lambda: {"model": etat["modele"], "spacy": "t"})
    return etat


def _bulle(client, planche_id, db_path, texte):
    """Une bulle au texte donné, indexée par le modèle chargé."""
    r = _region(client, planche_id)
    conn = _conn(db_path)
    try:
        conn.execute("UPDATE regions SET ocr_texte = ? WHERE id = ?", (texte, r))
        database.reindex_region(conn, r)
        conn.commit()
    finally:
        conn.close()
    return r


def _reindexer(db_path, region_id):
    """Ce que fait `tools/reindex_nlp.py` à une région, après le changement de modèle."""
    conn = _conn(db_path)
    try:
        database.reindex_region(conn, region_id)
        conn.commit()
    finally:
        conn.close()


def _vu(db_path, region_id, ordre):
    conn = _conn(db_path)
    try:
        ligne = conn.execute("SELECT * FROM token_correction WHERE region_id = ? AND ordre = ?",
                             (region_id, ordre)).fetchone()
    finally:
        conn.close()
    return tuple(ligne[k] for k in database.COLONNES_VU)


def test_corriger_garde_ce_qui_s_affichait_et_le_remplace_a_la_retouche(
        client, album, planche, db_path, modele_charge):
    """La route garde la proposition d'AVANT la correction, et ce relevé survit à la
    réindexation qu'elle lance elle-même puis au passage à `lg`. Retoucher sous `lg`
    remplace le relevé : c'est `lg` qu'on a regardé cette fois-là."""
    r = _bulle(client, planche["id"], db_path, "LE CHAT")
    assert client.put(f"/api/regions/{r}/tokens/1",
                      json={"lemme": "matou", "etat": "corrige"}).status_code == 200
    assert _vu(db_path, r, 1) == (SM, "chat", "NOUN", "")

    modele_charge.update(modele=LG, pos="VERB")
    _reindexer(db_path, r)
    assert _vu(db_path, r, 1) == (SM, "chat", "NOUN", "")
    assert client.get("/api/analyse/accord").json()["champs"]["pos"]["accord"] == 0

    client.put(f"/api/regions/{r}/tokens/1", json={"lemme": "matou", "etat": "corrige"})
    assert _vu(db_path, r, 1) == (LG, "chat", "VERB", "")


def test_valider_garde_la_proposition_sur_chaque_ligne(client, album, planche, db_path,
                                                      modele_charge):
    """Les deux chemins de la validation : la correction qui existait (sa case vide se porte
    désormais garante de ce que dit `lg`), et le token qu'on accepte tel quel."""
    r = _bulle(client, planche["id"], db_path, "LE CHAT")
    client.put(f"/api/regions/{r}/tokens/1", json={"lemme": "matou", "etat": "corrige"})
    modele_charge.update(modele=LG, pos="VERB")
    _reindexer(db_path, r)
    assert client.post(f"/api/regions/{r}/grammaire/valider").status_code == 200
    assert _vu(db_path, r, 1) == (LG, "chat", "VERB", "")
    assert _vu(db_path, r, 0) == (LG, "le", "VERB", "")


def test_valider_sans_moteur_ne_perd_pas_ce_qui_a_ete_vu(client, album, planche, db_path,
                                                         modele_charge, monkeypatch):
    """Sans moteur, la validation commence par une réindexation qui vide `tokens` sans
    ré-ancrer. Relever à ce moment-là remettrait à NULL ce que l'annotateur avait vu."""
    r = _bulle(client, planche["id"], db_path, "LE CHAT")
    client.put(f"/api/regions/{r}/tokens/1", json={"lemme": "matou", "etat": "corrige"})
    monkeypatch.setattr(nlp, "analyse", lambda texte: ("", []))      # moteur absent
    monkeypatch.setattr(nlp, "model_info", lambda: {})
    assert client.post(f"/api/regions/{r}/grammaire/valider").status_code == 200
    assert _vu(db_path, r, 1) == (SM, "chat", "NOUN", "")


def test_la_route_restreint_a_un_modele(client, album, planche, db_path):
    r = _region(client, planche["id"])
    _tokens(db_path, r, [(0, "CHAT", "chat", "VERB", "")])
    _correction(db_path, r, 0, "CHAT", modele=SM, vu=("chat", "NOUN", ""))
    rep = client.get("/api/analyse/accord", params={"modele": SM}).json()
    assert rep["filtre_modele"] == SM
    assert rep["a_la_relecture"]["champs"]["pos"]["accord"] == 1
    assert client.get("/api/analyse/accord",
                      params={"modele": ""}).json()["a_la_relecture"] is None


def test_le_csv_restreint_le_dit(client, album, planche, db_path):
    """Deux fichiers de taux, l'un sur tout le corpus relu, l'autre sur les seules relectures
    faites sous `sm`, ne doivent pas pouvoir se confondre."""
    r = _region(client, planche["id"])
    _tokens(db_path, r, [(0, "CHAT", "chat", "VERB", "")])
    _correction(db_path, r, 0, "CHAT", modele=SM, vu=("chat", "NOUN", ""))
    lignes = client.get("/api/analyse/accord.csv", params={"modele": SM}).text.splitlines()
    assert lignes[0].split(",")[-1] == "releve_sur"
    assert all(l.split(",")[-1] == SM for l in lignes[1:]) and len(lignes) == 4
    tout = client.get("/api/analyse/accord.csv").text.splitlines()
    assert all(l.split(",")[-1] == "" for l in tout[1:])


# --------------------------------------------------------------------------- #
# L'outil
# --------------------------------------------------------------------------- #
def test_cli_modele(client, album, planche, db_path, data_dir, tmp_path):
    r = _region(client, planche["id"])
    _tokens(db_path, r, [(0, "CHAT", "chat", "VERB", "")])
    _correction(db_path, r, 0, "CHAT", modele=SM, vu=("chat", "NOUN", ""))
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    out, tab = tmp_path / "accord.json", tmp_path / "accord.csv"
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir)}
    res = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "rapport_accord.py"),
         "--modele", SM, "--json", str(out), "--csv", str(tab)],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0, res.stderr
    assert f"Restreint aux relectures faites sur : {SM}" in res.stderr
    assert f"{SM}, au moment de la relecture" in res.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["champs"]["pos"]["accord"] == 0
    assert data["a_la_relecture"]["champs"]["pos"]["accord"] == 1
    lignes = tab.read_text(encoding="utf-8").splitlines()
    assert lignes[0].endswith(";releve_sur") and all(l.endswith(";" + SM) for l in lignes[1:])
