"""NLP-4 — spaCy EN VEILLE (`BD_NLP=0`), et son rattrapage de nuit.

Dans l'image, charger spaCy fait importer torch par thinc : le processus passe de 70 à
498 Mo, et décharger le modèle ne rend pas ce que l'import a pris (mesuré le 2026-11-26).
La veille coupe le moteur DANS l'application ; un processus à part le rallume la nuit
(`deploy/reindex-nlp.sh`) pour rattraper ce que la journée a écrit.

Ce que ces tests tiennent, chacun contre une façon précise de perdre :
  · en veille, rien ne CHARGE spaCy — ni une écriture, ni l'épreuve de la page Santé ;
  · une écriture en veille ne touche à aucune correction humaine ;
  · les gestes de la grammaire refusent, au lieu d'être acceptés puis défaits ;
  · l'outil refuse en veille, faute de quoi il effacerait les tokens du corpus ;
  · le rattrapage refait ce que la veille a laissé, ré-ancre les corrections, et rien
    d'autre.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

import database
import sante
from pipeline import nlp

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "tools"))
import reindex_nlp as outil  # noqa: E402

pytestmark = pytest.mark.skipif(not nlp.nlp_available(),
                                reason="spaCy / modèle français non installé")


@pytest.fixture
def veille(monkeypatch):
    """La veille, et la preuve que rien ne charge le modèle pendant qu'elle dure."""
    monkeypatch.setenv("BD_NLP", "0")

    def interdit():
        raise AssertionError("spaCy chargé alors qu'il est en veille")
    monkeypatch.setattr(nlp, "_get_nlp", interdit)


def _conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _bulle(client, planche, texte):
    return client.post(f"/api/planches/{planche['id']}/regions",
                       json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                             "ocr_texte": texte}).json()["id"]


def _etat(db_path, rid):
    conn = _conn(db_path)
    try:
        toks = [dict(r) for r in conn.execute(
            "SELECT ordre, texte, lemme FROM tokens WHERE region_id = ? ORDER BY ordre",
            (rid,))]
        corr = [dict(r) for r in conn.execute(
            "SELECT ordre, forme, lemme, pos, morph, etat, obsolete, auteur "
            "FROM token_correction WHERE region_id = ? ORDER BY ordre", (rid,))]
        lemmes = conn.execute("SELECT lemmes FROM recherche WHERE region_id = ?",
                              (rid,)).fetchone()["lemmes"]
        return toks, corr, lemmes
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Le drapeau
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("valeur", ["0", "false", "NO", " non ", "Off"])
def test_ces_valeurs_mettent_en_veille(monkeypatch, valeur):
    monkeypatch.setenv("BD_NLP", valeur)
    assert nlp.en_veille() and not nlp.nlp_available()


@pytest.mark.parametrize("valeur", [None, "", "1", "oui", "zéro"])
def test_le_reste_laisse_le_moteur_allume(monkeypatch, valeur):
    """Une veille retire des lemmes à l'index : elle ne s'impose que DITE, et une faute de
    frappe n'éteint rien."""
    if valeur is None:
        monkeypatch.delenv("BD_NLP", raising=False)
    else:
        monkeypatch.setenv("BD_NLP", valeur)
    assert not nlp.en_veille() and nlp.nlp_available()


# --------------------------------------------------------------------------- #
# Dans l'application
# --------------------------------------------------------------------------- #
def test_une_ecriture_en_veille_garde_les_corrections(client, planche, db_path, monkeypatch):
    """La garde qui compte : en veille, une retouche du texte EFFACE les tokens de la région
    (la réindexation structurelle n'en produit aucun), mais aucune correction humaine ne
    bouge — ni réancrée, ni rendue obsolète, ni perdue."""
    rid = _bulle(client, planche, "LES OTAGES SONT PARTIS")
    assert client.put(f"/api/regions/{rid}/tokens/1",
                      json={"lemme": "otage", "pos": "NOUN"}).status_code == 200
    _, corr_avant, _ = _etat(db_path, rid)
    assert corr_avant

    monkeypatch.setenv("BD_NLP", "0")
    monkeypatch.setattr(nlp, "_get_nlp", lambda: (_ for _ in ()).throw(
        AssertionError("spaCy chargé alors qu'il est en veille")))
    assert client.put(f"/api/regions/{rid}",
                      json={"ocr_texte": "LES OTAGES SONT REVENUS"}).status_code == 200

    toks, corr, lemmes = _etat(db_path, rid)
    assert toks == []                 # ce que la veille coûte, et ce que la nuit rattrape
    assert corr == corr_avant         # ce qu'elle ne coûte pas
    assert "otage" in lemmes.split()  # la correction reste cherchable sans spaCy


def test_les_gestes_de_la_grammaire_refusent_en_veille(client, planche, db_path, veille):
    """Acceptés, ils réindexeraient la région sans moteur, donc effaceraient ses tokens :
    le geste se ferait, puis se déferait sous les yeux de qui vient de le faire."""
    rid = _bulle(client, planche, "LE GAULOIS")
    conn = _conn(db_path)
    try:                              # des tokens d'avant la veille, semés en direct
        conn.execute("INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                     "VALUES (?, 0, 'le', 'le', 'DET', '')", (rid,))
        conn.commit()
    finally:
        conn.close()
    for methode, chemin, corps in (
            ("PUT", f"/api/regions/{rid}/tokens/0", {"lemme": "la"}),
            ("POST", f"/api/regions/{rid}/grammaire/valider", None),
            ("DELETE", f"/api/regions/{rid}/tokens/0", None)):
        r = client.request(methode, chemin, json=corps)
        assert r.status_code == 503, (methode, chemin, r.text)
        assert "en veille" in r.json()["detail"]
    toks, corr, _ = _etat(db_path, rid)
    assert [t["lemme"] for t in toks] == ["le"] and corr == []


def test_la_veille_refuse_apres_l_autorisation(client, planche, veille):
    """Le 503 ne passe pas devant le 404 : une région qu'on ne voit pas reste introuvable."""
    assert client.put("/api/regions/999999/tokens/0",
                      json={"lemme": "x"}).status_code == 404


def test_la_sante_dit_la_veille_et_l_epreuve_ne_charge_rien(client, veille, monkeypatch):
    sante._reset()
    monkeypatch.setitem(sante._CONTROLES, "nlp", lambda: (_ for _ in ()).throw(
        AssertionError("l'épreuve a chargé spaCy dans l'application")))
    d = client.get("/api/sante").json()
    assert d["en_veille"] == ["nlp"] and d["lemmes"] is False
    p = client.get("/api/sante?profond=1").json()["profond"]["nlp"]
    assert p["ok"] is False and p["en_veille"] is True
    assert "nlp" not in sante._profond     # rien de mémorisé : la veille levée, on éprouve


def test_hors_veille_la_sante_ne_nomme_aucun_moteur_en_veille(client, monkeypatch):
    monkeypatch.delenv("BD_NLP", raising=False)
    assert client.get("/api/sante").json()["en_veille"] == []


# --------------------------------------------------------------------------- #
# La nuit
# --------------------------------------------------------------------------- #
def test_le_rattrapage_refait_ce_que_la_veille_a_laisse_et_rien_d_autre(
        client, planche, db_path, monkeypatch):
    intacte = _bulle(client, planche, "LE GAULOIS BUVAIT")
    # Deux régions jumelles, la même correction, la même retouche : l'une avec spaCy
    # allumé, l'autre en veille puis rattrapée. La nuit doit rendre ce que le jour aurait
    # rendu — rien de moins, rien d'autre.
    temoin, retouchee = (_bulle(client, planche, "LES OTAGES SONT PARTIS") for _ in range(2))
    for rid in (temoin, retouchee):
        assert client.put(f"/api/regions/{rid}/tokens/1",
                          json={"lemme": "otage", "pos": "NOUN"}).status_code == 200
    note = _bulle(client, planche, "")
    vide = _bulle(client, planche, "")
    client.put(f"/api/regions/{temoin}", json={"ocr_texte": "MES OTAGES SONT PARTIS"})

    monkeypatch.setenv("BD_NLP", "0")
    client.put(f"/api/regions/{retouchee}", json={"ocr_texte": "MES OTAGES SONT PARTIS"})
    client.put(f"/api/regions/{note}/annotation", json={"note": "Les chevaux galopaient"})
    monkeypatch.delenv("BD_NLP")

    conn = _conn(db_path)
    try:
        a_faire = database.regions_a_rattraper(conn)
        # La retouche, et la note — qui ne porte jamais de token, seulement des lemmes.
        assert retouchee in a_faire and note in a_faire
        assert intacte not in a_faire and vide not in a_faire and temoin not in a_faire
        assert database.reindex_all(conn, regions=a_faire) == len(a_faire)
        assert database.regions_a_rattraper(conn) == []      # une seconde nuit : rien
        meta = {r["cle"]: r["valeur"] for r in conn.execute("SELECT cle, valeur FROM meta")}
        # Le compteur d'une réindexation ENTIÈRE n'est pas réécrit par une nuit de rattrapage.
        assert meta.get("nlp_rattrape_count") == str(len(a_faire))
        assert "nlp_reindexed_count" not in meta
    finally:
        conn.close()

    toks, corr, lemmes = _etat(db_path, retouchee)
    assert toks and "otage" in lemmes.split()
    assert _etat(db_path, retouchee) == _etat(db_path, temoin)   # tokens, corrections, lemmes
    assert "cheval" in _etat(db_path, note)[2].split()


def test_l_outil_refuse_en_veille_sans_rien_toucher(client, planche, db_path, veille):
    """Sans moteur, `reindex_all` est une réindexation STRUCTURELLE : lancée sur le corpus,
    elle effacerait tous les tokens. En veille, l'outil ne la lance donc pas."""
    rid = _bulle(client, planche, "LE GAULOIS")
    conn = _conn(db_path)
    try:
        conn.execute("INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                     "VALUES (?, 0, 'le', 'le', 'DET', '')", (rid,))
        conn.commit()
    finally:
        conn.close()
    assert outil.main([]) == 1 and outil.main(["--a-rattraper"]) == 1
    assert [t["lemme"] for t in _etat(db_path, rid)[0]] == ["le"]


def test_l_outil_ne_fait_rien_quand_il_n_y_a_rien_a_rattraper(
        client, planche, db_path, monkeypatch, capsys):
    """Une nuit sans rien à faire ne charge pas le modèle et n'inscrit aucun passage : le
    journal ne compte pas une activité vide chaque nuit. On le lit au JOURNAL et non à un
    chargement interdit — `model_info` et `analyse_batch` avalent toute erreur du moteur,
    si bien qu'un chargement interdit ne ferait rien tomber (mutant qui a survécu)."""
    monkeypatch.delenv("BD_NLP", raising=False)
    _bulle(client, planche, "LE GAULOIS BUVAIT")

    def passages():
        conn = _conn(db_path)
        try:
            return conn.execute("SELECT COUNT(*) FROM activite WHERE type = 'reindex_nlp'"
                                ).fetchone()[0]
        finally:
            conn.close()
    avant = passages()
    assert outil.main(["--a-rattraper"]) == 0
    assert passages() == avant
    assert "Rien à rattraper" in capsys.readouterr().out


def test_les_unites_lancent_le_rattrapage_chaque_nuit_hors_de_l_application():
    racine = RACINE / "deploy" / "systemd"
    if not racine.exists():
        pytest.skip(
            "deploy/ est exclu du contexte de build (.dockerignore) : ce test ne tourne QUE "
            "sur la machine de développement. Son skip dans l'image N'EST PAS une couverture "
            "— cf. QA-6, « un skip se lit comme un succès »")
    service = (racine / "bd-reindex-nlp.service").read_text(encoding="utf-8")
    minuterie = (racine / "bd-reindex-nlp.timer").read_text(encoding="utf-8")
    script = (racine.parent / "reindex-nlp.sh").read_text(encoding="utf-8")
    assert "Type=oneshot" in service and "User=ubuntu" in service
    assert "ExecStart=/home/ubuntu/BD_ditor/deploy/reindex-nlp.sh" in service
    assert "Environment=PATH=" in service
    # Le moteur rallumé pour CE processus seul, et seulement ce qui reste à rattraper.
    assert "docker exec -e BD_NLP=1" in script
    assert "tools/reindex_nlp.py --a-rattraper" in script
    assert "OnCalendar=*-*-* 03:00:00 Europe/Paris" in minuterie
    assert "Persistent=true" in minuterie and "Unit=bd-reindex-nlp.service" in minuterie


def _rattraper(db_path):
    conn = _conn(db_path)
    try:
        database.reindex_all(conn, regions=database.regions_a_rattraper(conn))
    finally:
        conn.close()


def test_une_forme_ambigue_reste_a_revoir_plutot_que_de_suivre_le_mauvais_mot(
        client, planche, db_path, monkeypatch):
    """Sans l'ancienne tokenisation, l'alignement se fait sur la FORME : un mot qui a BOUGÉ
    et qui revient deux fois ne dit plus lequel des deux portait la correction. Elle reste
    orpheline — gardée, à revérifier —, jamais rattachée au hasard. C'est le prix connu de
    la veille : l'alignement complet l'aurait suivi. (Resté à sa place, le mot la garde.)"""
    rid = _bulle(client, planche, "IL VOIT CE QU'IL VOIT")
    toks = {t["ordre"]: t["texte"] for t in client.get(f"/api/regions/{rid}/tokens").json()}
    premier = min(o for o, t in toks.items() if t == "voit")
    assert client.put(f"/api/regions/{rid}/tokens/{premier}",
                      json={"pos": "AUX"}).status_code == 200
    monkeypatch.setenv("BD_NLP", "0")
    client.put(f"/api/regions/{rid}", json={"ocr_texte": "ALORS IL VOIT CE QU'IL VOIT"})
    monkeypatch.delenv("BD_NLP")
    _rattraper(db_path)
    (c,) = _etat(db_path, rid)[1]
    assert c["obsolete"] == 1 and c["ordre"] < 0 and c["pos"] == "AUX"


def test_une_correction_deja_orpheline_ne_se_rattache_pas_la_nuit(
        client, planche, db_path, monkeypatch):
    """Orpheline AVANT la veille — son mot avait réellement changé —, elle le reste : que
    la forme revienne dans la bulle ne dit pas que c'est le même mot."""
    rid = _bulle(client, planche, "LES OTAGES SONT PARTIS")
    assert client.put(f"/api/regions/{rid}/tokens/1",
                      json={"lemme": "otage"}).status_code == 200
    client.put(f"/api/regions/{rid}", json={"ocr_texte": "LES ENFANTS SONT PARTIS"})
    assert _etat(db_path, rid)[1][0]["obsolete"] == 1       # orpheline, spaCy allumé
    monkeypatch.setenv("BD_NLP", "0")
    client.put(f"/api/regions/{rid}", json={"ocr_texte": "LES OTAGES SONT PARTIS"})
    monkeypatch.delenv("BD_NLP")
    _rattraper(db_path)
    (c,) = _etat(db_path, rid)[1]
    assert c["obsolete"] == 1 and c["ordre"] < 0
