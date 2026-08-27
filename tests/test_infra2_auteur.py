"""INFRA-2 — l'auteur connecté (en-tête Remote-User) est enregistré sur les
corrections grammaticales, exposé (vue/API) et filtrable (routes d'analyse).

On vérifie l'auteur via `token_correction` en base directe : `reindex_region`
régénère `tokens` (donc l'efface quand spaCy est absent) mais ne touche JAMAIS la
couche overlay `token_correction`. Les tests sont donc robustes sans spaCy.
"""
import sqlite3

from conftest import ADMIN   # AUTH-2 : le décor est monté par un administrateur


def _region(client, planche_id, type="bulle"):
    return client.post(f"/api/planches/{planche_id}/regions",
                       json={"type": type, "x": 10, "y": 10, "w": 50, "h": 40},
                       headers=ADMIN).json()["id"]


def _seed(db_path, region_id, tokens):
    """Insère des tokens (ordre, texte, lemme, pos, morph) en direct (cf. test_analyse)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(
            "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) VALUES (?,?,?,?,?,?)",
            [(region_id, o, t, l, p, m) for (o, t, l, p, m) in tokens])
        conn.commit()
    finally:
        conn.close()


def _seed_corr(db_path, region_id, ordre, forme, auteur, etat="valide",
               lemme=None, pos=None, morph=None):
    """Pose une correction overlay directement (sans passer par la route → pas de
    reindex qui effacerait `tokens` sans spaCy)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO token_correction "
            "  (region_id, ordre, forme, lemme, pos, morph, etat, auteur, obsolete) "
            "VALUES (?,?,?,?,?,?,?,?,0)",
            (region_id, ordre, forme, lemme, pos, morph, etat, auteur))
        conn.commit()
    finally:
        conn.close()


def _auteurs(db_path, region_id):
    """Ensemble des auteurs des corrections d'une région, QUEL QUE SOIT l'ordre :
    reindex (spaCy présent) peut parquer une correction sans ancre à un ordre négatif,
    mais préserve l'auteur. On teste donc la valeur, pas la position."""
    conn = sqlite3.connect(db_path)
    try:
        return {r[0] for r in conn.execute(
            "SELECT auteur FROM token_correction WHERE region_id=?", (region_id,)).fetchall()}
    finally:
        conn.close()


# --------------------------- Enregistrement --------------------------- #
def test_correction_enregistre_auteur_connecte(client, derriere_proxy, album, planche, db_path):
    a = _region(client, planche["id"])
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    r = client.put(f"/api/regions/{a}/tokens/0",
                   json={"lemme": "crier", "pos": "VERB", "etat": "corrige"},
                   headers={"Remote-User": "jeanne"})
    assert r.status_code == 200
    assert _auteurs(db_path, a) == {"jeanne"}


def test_correction_sans_proxy_reste_anonyme(client, derriere_proxy, album, planche, db_path):
    """En local (pas d'en-tête Remote-User), l'auteur reste NULL — comme avant."""
    a = _region(client, planche["id"])
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    client.put(f"/api/regions/{a}/tokens/0", json={"lemme": "crier", "etat": "corrige"})
    assert _auteurs(db_path, a) == {None}


def test_validation_ne_clobbe_pas_le_correcteur(client, derriere_proxy, album, planche, db_path):
    """Valider (geste de marc) ne doit PAS écraser qui a corrigé (jeanne) : valider
    n'est pas corriger. Robuste sans spaCy (la correction obsolète est ignorée par le
    WHERE obsolete=0) comme avec (COALESCE préserve l'auteur existant)."""
    a = _region(client, planche["id"])
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    client.put(f"/api/regions/{a}/tokens/0", json={"lemme": "crier", "etat": "corrige"},
               headers={"Remote-User": "jeanne"})
    client.post(f"/api/regions/{a}/grammaire/valider", headers={"Remote-User": "marc"})
    assert _auteurs(db_path, a) == {"jeanne"}   # marc valide, mais jeanne reste le correcteur


# --------------------------- Exposition --------------------------- #
def test_tokens_exposent_corr_auteur(client, derriere_proxy, album, planche, db_path):
    a = _region(client, planche["id"])
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    _seed_corr(db_path, a, 0, "CRIE", "jeanne", etat="valide")
    tok = client.get(f"/api/regions/{a}/tokens", headers=ADMIN).json()[0]
    assert tok["corr_auteur"] == "jeanne"
    assert tok["provenance"] == "valide"


# --------------------------- Filtrage (API) --------------------------- #
def test_frequences_filtre_par_auteur(client, derriere_proxy, album, planche, db_path):
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    _seed(db_path, b, [(0, "RIT", "rire", "VERB", "")])
    _seed_corr(db_path, a, 0, "CRIE", "jeanne")
    _seed_corr(db_path, b, 0, "RIT", "marc")
    res = client.get("/api/analyse/frequences", headers=ADMIN,
                     params={"champ": "lemme", "auteur": "jeanne"}).json()
    assert {r["lemme"] for r in res["results"]} == {"crier"}


def test_concordance_filtre_par_auteur_seul(client, derriere_proxy, album, planche, db_path):
    """L'auteur seul est un critère de concordance valide (« montre ce que X a corrigé »)."""
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    _seed(db_path, b, [(0, "CRIE", "crier", "VERB", "")])
    _seed_corr(db_path, a, 0, "CRIE", "jeanne")
    _seed_corr(db_path, b, 0, "CRIE", "marc")
    r = client.get("/api/analyse/concordance", params={"auteur": "jeanne"},
                   headers=ADMIN).json()
    assert r["count"] == 1 and r["results"][0]["region_id"] == a


def test_comparaison_par_auteur(client, derriere_proxy, album, planche, db_path):
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    _seed(db_path, b, [(0, "RIT", "rire", "VERB", "")])
    _seed_corr(db_path, a, 0, "CRIE", "jeanne")
    _seed_corr(db_path, b, 0, "RIT", "marc")
    res = client.get("/api/analyse/comparaison", headers=ADMIN,
                     params={"champ": "lemme", "a_auteur": "jeanne", "b_auteur": "marc"}).json()
    assert "crier" in {x["valeur"] for x in res["sur_a"]}
    assert "rire" in {x["valeur"] for x in res["sur_b"]}
