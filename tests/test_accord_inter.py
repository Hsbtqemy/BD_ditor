"""Accord inter-annotateurs (ANN-5 / B6).

Cœur `accord_inter.rapport` exposé par `GET /api/analyse/accord-inter` ET
`tools/rapport_accord_inter.py`. Vérifie l'accord de RÉVISION (un auteur re-touche le token
d'un autre : garde = accord, change = divergence), par champ + par paire, la résolution des
divergences en citation, et le cas « même auteur » (non compté). Événements du journal A3
semés EN DIRECT (agent nécessaire — rare hors multi-utilisateur).
"""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"


def _ev(db_path, cible_id, agent, apres, avant=None, typ="modification"):
    """Insère un événement humain de correction de token dans le journal A3."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO evenement (type, agent, agent_type, cible_table, cible_id, avant, apres) "
        "VALUES (?, ?, 'humain', 'token_correction', ?, ?, ?)",
        (typ, agent, cible_id,
         json.dumps(avant) if avant else None, json.dumps(apres)))
    conn.commit()
    conn.close()


def _run(db_path, data_dir, *args):
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir)}
    return subprocess.run([sys.executable, str(TOOLS / "rapport_accord_inter.py"), *args],
                          cwd=str(REPO_ROOT), env=env, capture_output=True,
                          text=True, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Cœur / route
# --------------------------------------------------------------------------- #
def test_accord_inter(client, db_path):
    # cible 1 : alice pose NOUN, bob change en VERB → divergence POS
    _ev(db_path, 1, "alice", {"lemme": "a", "pos": "NOUN", "morph": ""}, typ="creation")
    _ev(db_path, 1, "bob", {"lemme": "a", "pos": "VERB", "morph": ""},
        avant={"lemme": "a", "pos": "NOUN", "morph": ""})
    # cible 2 : alice pose ADJ, bob confirme à l'identique → accord
    _ev(db_path, 2, "alice", {"lemme": "x", "pos": "ADJ", "morph": ""}, typ="creation")
    _ev(db_path, 2, "bob", {"lemme": "x", "pos": "ADJ", "morph": ""},
        avant={"lemme": "x", "pos": "ADJ", "morph": ""})

    r = client.get("/api/analyse/accord-inter").json()
    assert r["retouches"] == 2 and r["auteurs"] == ["alice", "bob"]
    assert r["champs"]["pos"] == {"retouches": 2, "accords": 1, "taux": 0.5}
    assert r["champs"]["lemme"]["taux"] == 1.0 and r["champs"]["morph"]["taux"] == 1.0
    assert r["paires"] == [{"a": "alice", "b": "bob", "retouches": 2, "accords": 1, "taux": 0.5}]
    assert len(r["divergences"]) == 1
    d = r["divergences"][0]
    assert d["de"] == "alice" and d["a"] == "bob"
    assert d["diffs"] == [{"champ": "pos", "avant": "NOUN", "apres": "VERB"}]
    assert d["citation"] is None            # aucun token_correction → le journal survit


def test_accord_inter_meme_auteur_ignore(client, db_path):
    """Deux corrections successives du MÊME auteur ne sont pas une re-touche inter-annotateurs."""
    _ev(db_path, 5, "alice", {"pos": "NOUN"}, typ="creation")
    _ev(db_path, 5, "alice", {"pos": "VERB"}, avant={"pos": "NOUN"})
    assert client.get("/api/analyse/accord-inter").json()["retouches"] == 0


def test_accord_inter_chaine_collapse_le_meme_auteur(client, db_path):
    """Chaîne alice→alice→bob : UNE seule re-touche inter-auteurs, et bob est comparé à la
    DERNIÈRE valeur d'alice (ADJ), pas à la première (NOUN)."""
    _ev(db_path, 7, "alice", {"pos": "NOUN"}, typ="creation")
    _ev(db_path, 7, "alice", {"pos": "ADJ"}, avant={"pos": "NOUN"})     # alice se corrige
    _ev(db_path, 7, "bob", {"pos": "VERB"}, avant={"pos": "ADJ"})       # bob : ADJ → VERB
    r = client.get("/api/analyse/accord-inter").json()
    assert r["retouches"] == 1
    assert r["divergences"][0]["diffs"] == [{"champ": "pos", "avant": "ADJ", "apres": "VERB"}]
    assert r["paires"] == [{"a": "alice", "b": "bob", "retouches": 1, "accords": 0, "taux": 0.0}]


def test_accord_inter_divergence_citee(client, planche, db_path):
    """Une divergence se résout en citation (forme du token + repère éditorial)."""
    reg = client.post(f"/api/planches/{planche['id']}/regions",
                      json={"type": "case", "x": 1, "y": 1, "w": 9, "h": 9}).json()["id"]
    conn = sqlite3.connect(db_path)
    cur = conn.execute("INSERT INTO token_correction (region_id, ordre, forme, etat) "
                       "VALUES (?, 0, 'MOT', 'corrige')", (reg,))
    tcid = cur.lastrowid
    conn.commit()
    conn.close()
    _ev(db_path, tcid, "alice", {"pos": "NOUN"}, typ="creation")
    _ev(db_path, tcid, "bob", {"pos": "VERB"}, avant={"pos": "NOUN"})

    d = client.get("/api/analyse/accord-inter").json()["divergences"][0]
    assert d["forme"] == "MOT" and d["citation"] and d["citation"]["texte"]


def test_accord_inter_vide(client):
    r = client.get("/api/analyse/accord-inter").json()
    assert r["retouches"] == 0 and r["divergences"] == [] and r["paires"] == []


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_rapport_accord_inter(client, db_path, data_dir, tmp_path):
    _ev(db_path, 9, "alice", {"pos": "NOUN"}, typ="creation")
    _ev(db_path, 9, "bob", {"pos": "VERB"}, avant={"pos": "NOUN"})
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    out = tmp_path / "inter.json"
    res = _run(db_path, data_dir, "--json", str(out))
    assert res.returncode == 0, res.stderr
    assert "Accord inter-annotateurs" in res.stderr and "1 re-touche" in res.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["retouches"] == 1 and data["champs"]["pos"]["accords"] == 0


# --------------------------------------------------------------------------- #
# AUTH-6 — un agent COLLECTIF n'est pas mesurable, et le rapport le DIT
# --------------------------------------------------------------------------- #
def _collectif(db_path, login):
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO utilisateur (login, nature) VALUES (?, 'collectif') "
                 "ON CONFLICT(login) DO UPDATE SET nature = 'collectif'", (login,))
    conn.commit()
    conn.close()


def test_deux_relectures_sous_un_login_partage_sont_comptees_et_non_mesurees(
        client, db_path):
    """Le cas qui cassait DÉJÀ, sans que rien ne le dise.

    La condition de re-touche est `agent_précédent != agent` : deux personnes qui se
    relisent sous le même login ne produisent donc pas un faux accord, elles SORTENT de
    l'échantillon. Le taux affiché portait alors sur moins de travail qu'on ne croyait, et
    l'écart n'apparaissait nulle part — le mode d'échec d'ARCH-2, une mesure qui rétrécit
    en silence. Le seul remède est de COMPTER ce qu'on ne peut pas mesurer.
    """
    _collectif(db_path, "promo-l3")
    _ev(db_path, 21, "promo-l3", {"pos": "NOUN"}, typ="creation")
    _ev(db_path, 21, "promo-l3", {"pos": "VERB"}, avant={"pos": "NOUN"})

    r = client.get("/api/analyse/accord-inter").json()
    assert r["retouches"] == 0, "rien n'est mesurable sous un login partagé"
    assert r["non_attribuable"]["revisions_internes"] == 1
    assert r["non_attribuable"]["agents_collectifs"] == ["promo-l3"]


def test_une_paire_avec_un_agent_collectif_sort_des_taux(client, db_path):
    """Un taux (personne, groupe) aurait un sens statistique et aucun sens scientifique :
    on ne peut pas réunir « le groupe » pour arbitrer une divergence, ce qui est l'usage
    entier de ce rapport."""
    _collectif(db_path, "promo-l3")
    _ev(db_path, 22, "alice", {"pos": "NOUN"}, typ="creation")
    _ev(db_path, 22, "promo-l3", {"pos": "VERB"}, avant={"pos": "NOUN"})

    r = client.get("/api/analyse/accord-inter").json()
    assert r["retouches"] == 0 and r["paires"] == [] and r["divergences"] == []
    assert r["non_attribuable"]["revisions_avec_collectif"] == 1


def test_le_bloc_non_attribuable_est_toujours_la(client):
    """Présent même à zéro. Une clé qui n'apparaîtrait qu'en cas de problème ferait lire
    son absence comme une absence de problème, alors qu'elle signifierait « je n'ai pas
    regardé »."""
    r = client.get("/api/analyse/accord-inter").json()
    assert r["non_attribuable"] == {"agents_collectifs": [], "revisions_internes": 0,
                                    "revisions_avec_collectif": 0}


def test_un_compte_collectif_etranger_a_l_echantillon_n_est_pas_nomme(client, db_path):
    """Le rapport décrit SON échantillon, jamais l'instance — et c'est aussi une voie de
    sortie d'identité.

    Cette route est cloisonnable par `album_ids` (AUTH-2). Rendre tous les comptes
    collectifs de l'instance publierait des logins de GROUPES à quelqu'un qui ne lit que
    ses propres albums. Trouvé en relecture le 2026-09-09 : le cliquet d'AUTH-5 ne pouvait
    pas le voir, sa sentinelle n'étant pas déclarée collective.
    """
    _collectif(db_path, "promo-l3")          # déclaré, mais sans aucun acte
    _ev(db_path, 23, "alice", {"pos": "NOUN"}, typ="creation")
    _ev(db_path, 23, "bob", {"pos": "NOUN"}, avant={"pos": "NOUN"})

    r = client.get("/api/analyse/accord-inter").json()
    assert r["non_attribuable"]["agents_collectifs"] == [], (
        "un groupe absent de l'échantillon n'a pas à être nommé")
    assert r["retouches"] == 1, "la mesure entre nominatifs n'est pas affectée"
