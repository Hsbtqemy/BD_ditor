"""Routes d'analyse linguistique — filtre par tag (ANA-1) et scope hiérarchique.

Les tokens sont semés EN DIRECT dans la table `tokens` (via une connexion SQLite
séparée) plutôt que par le NLP : la couche spaCy est optionnelle et souvent absente
en CI, alors que la logique de FILTRE (SQL) doit être testée inconditionnellement.
À semer APRÈS les écritures d'annotation : `reindex_region` régénère `tokens` (donc
les efface quand spaCy est absent). Couvre aussi la dette QA-3 (cf. docs/backlog.md).
"""
import sqlite3


def _region(client, planche_id, type="bulle"):
    return client.post(f"/api/planches/{planche_id}/regions",
                       json={"type": type, "x": 10, "y": 10, "w": 50, "h": 40}).json()["id"]


def _tags(client, region_id, tags):
    client.put(f"/api/regions/{region_id}/annotation", json={"note": "", "tags": tags})


def _seed(db_path, region_id, tokens, parent_id=None):
    """Insère des tokens (ordre, texte, lemme, pos, morph) ; pose éventuellement le parent."""
    conn = sqlite3.connect(db_path)
    try:
        if parent_id is not None:
            conn.execute("UPDATE regions SET parent_id = ? WHERE id = ?", (parent_id, region_id))
        conn.executemany(
            "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) VALUES (?,?,?,?,?,?)",
            [(region_id, o, t, l, p, m) for (o, t, l, p, m) in tokens])
        conn.commit()
    finally:
        conn.close()


def test_frequences_filtre_par_tag(client, album, planche, db_path):
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    _tags(client, a, ["colère"])
    _tags(client, b, ["joie"])
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    _seed(db_path, b, [(0, "RIT", "rire", "VERB", "")])

    tout = client.get("/api/analyse/frequences", params={"champ": "lemme"}).json()
    assert {"crier", "rire"} <= {r["lemme"] for r in tout["results"]}

    filtre = client.get("/api/analyse/frequences",
                        params={"champ": "lemme", "tags": "colère"}).json()
    assert {r["lemme"] for r in filtre["results"]} == {"crier"}


def test_concordance_filtre_par_tag(client, album, planche, db_path):
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    _tags(client, a, ["colère"])
    _tags(client, b, ["joie"])
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    _seed(db_path, b, [(0, "CRIE", "crier", "VERB", "")])

    assert client.get("/api/analyse/concordance",
                      params={"lemme": "crier"}).json()["count"] == 2
    r = client.get("/api/analyse/concordance",
                   params={"lemme": "crier", "tags": "colère"}).json()
    assert r["count"] == 1 and r["results"][0]["region_id"] == a


def test_comparaison_par_tags(client, album, planche, db_path):
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    _tags(client, a, ["colère"])
    _tags(client, b, ["joie"])
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    _seed(db_path, b, [(0, "RIT", "rire", "VERB", "")])

    res = client.get("/api/analyse/comparaison",
                     params={"champ": "lemme", "a_tags": "colère", "b_tags": "joie"}).json()
    assert "crier" in {x["valeur"] for x in res["sur_a"]}
    assert "rire" in {x["valeur"] for x in res["sur_b"]}


def test_tag_scope_herite_vs_propre(client, album, planche, db_path):
    """Un tag posé sur la CASE doit (hérité) ou non (propre) atteindre les tokens
    de sa bulle enfant."""
    case = _region(client, planche["id"], type="case")
    bulle = _region(client, planche["id"])
    _tags(client, case, ["scene1"])
    _seed(db_path, bulle, [(0, "PARLE", "parler", "VERB", "")], parent_id=case)

    herite = client.get("/api/analyse/frequences",
                        params={"champ": "lemme", "tags": "scene1"}).json()
    assert {r["lemme"] for r in herite["results"]} == {"parler"}

    propre = client.get("/api/analyse/frequences",
                        params={"champ": "lemme", "tags": "scene1", "tag_scope": "propre"}).json()
    assert propre["results"] == []
