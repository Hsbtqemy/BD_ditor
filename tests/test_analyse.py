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


def test_recherche_tag_scope(client, album, planche, db_path):
    """Cohérence Recherche ↔ Analyse : un tag posé sur la CASE atteint sa bulle
    enfant en `herite` (drill depuis Exploration), pas en `propre` (défaut)."""
    case = _region(client, planche["id"], type="case")
    bulle = _region(client, planche["id"])
    _tags(client, case, ["scene1"])
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE regions SET parent_id = ? WHERE id = ?", (case, bulle))
    conn.commit(); conn.close()

    propre = client.get("/api/recherche", params={"tags": "scene1"}).json()
    assert {r["region_id"] for r in propre["results"]} == {case}   # la case seule

    herite = client.get("/api/recherche",
                        params={"tags": "scene1", "tag_scope": "herite"}).json()
    assert {r["region_id"] for r in herite["results"]} == {case, bulle}   # + la bulle enfant


# --------------------------------------------------------------------------- #
# ANN-2 (2c) : facette d'analyse par locuteur / attribut (profil + situation)
# --------------------------------------------------------------------------- #
def _perso(client, nom):
    return client.post("/api/personnages", json={"nom": nom}).json()["id"]


def test_frequences_par_locuteur(client, album, planche, db_path):
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    pa, pb = _perso(client, "A"), _perso(client, "B")
    client.put(f"/api/regions/{a}/locuteur", json={"personnage_id": pa})
    client.put(f"/api/regions/{b}/locuteur", json={"personnage_id": pb})
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    _seed(db_path, b, [(0, "RIT", "rire", "VERB", "")])
    res = client.get("/api/analyse/frequences", params={"champ": "lemme", "personnage": pa}).json()
    assert {r["lemme"] for r in res["results"]} == {"crier"}


def test_frequences_par_attribut_du_locuteur(client, album, planche, db_path):
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    pa, pb = _perso(client, "A"), _perso(client, "B")
    client.put(f"/api/regions/{a}/locuteur", json={"personnage_id": pa})
    client.put(f"/api/regions/{b}/locuteur", json={"personnage_id": pb})
    d = client.post("/api/attributs/dimensions", json={"cible": "personnage", "nom": "origine"}).json()["id"]
    v = client.post(f"/api/attributs/dimensions/{d}/valeurs", json={"valeur": "rural"}).json()["id"]
    client.put(f"/api/personnages/{pa}/attributs", json={"valeur_id": v})   # A est « rural »
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    _seed(db_path, b, [(0, "RIT", "rire", "VERB", "")])
    res = client.get("/api/analyse/frequences", params={"champ": "lemme", "attributs": v}).json()
    assert {r["lemme"] for r in res["results"]} == {"crier"}


def test_frequences_par_situation_de_case(client, album, planche, db_path):
    """L'attribut de SITUATION est posé sur la case ; la bulle enfant en hérite."""
    case = _region(client, planche["id"], type="case")
    bulle = _region(client, planche["id"])
    d = client.post("/api/attributs/dimensions", json={"cible": "case", "nom": "formalite"}).json()["id"]
    v = client.post(f"/api/attributs/dimensions/{d}/valeurs", json={"valeur": "soutenu"}).json()["id"]
    client.put(f"/api/regions/{case}/attributs", json={"valeur_id": v})
    _seed(db_path, bulle, [(0, "PARLE", "parler", "VERB", "")], parent_id=case)
    res = client.get("/api/analyse/frequences", params={"champ": "lemme", "attributs": v}).json()
    assert {r["lemme"] for r in res["results"]} == {"parler"}


def test_comparaison_par_locuteur(client, album, planche, db_path):
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    pa, pb = _perso(client, "A"), _perso(client, "B")
    client.put(f"/api/regions/{a}/locuteur", json={"personnage_id": pa})
    client.put(f"/api/regions/{b}/locuteur", json={"personnage_id": pb})
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    _seed(db_path, b, [(0, "RIT", "rire", "VERB", "")])
    res = client.get("/api/analyse/comparaison",
                     params={"champ": "lemme", "a_personnage": pa, "b_personnage": pb}).json()
    assert "crier" in {x["valeur"] for x in res["sur_a"]}
    assert "rire" in {x["valeur"] for x in res["sur_b"]}


def test_requete_these_rural_x_soutenu(client, album, planche, db_path):
    """LA requête-thèse : « lemmes des personnages RURAUX dans les scènes SOUTENUES ».
    Combine un attribut de LOCUTEUR et un attribut de SITUATION (ET). Deux contrôles
    (rural mais scène familière ; scène soutenue mais locuteur citadin) sont exclus."""
    do = client.post("/api/attributs/dimensions", json={"cible": "personnage", "nom": "origine"}).json()["id"]
    rural = client.post(f"/api/attributs/dimensions/{do}/valeurs", json={"valeur": "rural"}).json()["id"]
    df = client.post("/api/attributs/dimensions", json={"cible": "case", "nom": "formalite"}).json()["id"]
    soutenu = client.post(f"/api/attributs/dimensions/{df}/valeurs", json={"valeur": "soutenu"}).json()["id"]
    ru, ci = _perso(client, "Paysan"), _perso(client, "Citadin")
    client.put(f"/api/personnages/{ru}/attributs", json={"valeur_id": rural})

    c_sout = _region(client, planche["id"], type="case")     # scène soutenue
    client.put(f"/api/regions/{c_sout}/attributs", json={"valeur_id": soutenu})
    c_fam = _region(client, planche["id"], type="case")      # scène familière (non taguée)

    b_cible = _region(client, planche["id"])   # rural × soutenu  -> ATTENDU
    client.put(f"/api/regions/{b_cible}/locuteur", json={"personnage_id": ru})
    b_ctrl1 = _region(client, planche["id"])   # rural × familier -> exclu
    client.put(f"/api/regions/{b_ctrl1}/locuteur", json={"personnage_id": ru})
    b_ctrl2 = _region(client, planche["id"])   # citadin × soutenu -> exclu
    client.put(f"/api/regions/{b_ctrl2}/locuteur", json={"personnage_id": ci})

    _seed(db_path, b_cible, [(0, "ESPERE", "espérer", "VERB", "")], parent_id=c_sout)
    _seed(db_path, b_ctrl1, [(0, "GUEULE", "gueuler", "VERB", "")], parent_id=c_fam)
    _seed(db_path, b_ctrl2, [(0, "DEVISE", "deviser", "VERB", "")], parent_id=c_sout)

    res = client.get("/api/analyse/frequences",
                     params={"champ": "lemme", "attributs": [rural, soutenu]}).json()
    assert {r["lemme"] for r in res["results"]} == {"espérer"}


# --------------------------------------------------------------------------- #
# Revue ANN-2 : locuteur en concordance (#1), concordance sans pivot (#4),
# 404 sur id de facette inconnu (#6)
# --------------------------------------------------------------------------- #
def test_concordance_montre_le_locuteur(client, album, planche, db_path):
    a = _region(client, planche["id"])
    pid = _perso(client, "Tintin")
    client.put(f"/api/regions/{a}/locuteur", json={"personnage_id": pid})
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    res = client.get("/api/analyse/concordance", params={"lemme": "crier"}).json()
    assert res["count"] == 1 and res["results"][0]["locuteur"] == "Tintin"


def test_concordance_sans_pivot_grammatical(client, album, planche, db_path):
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    pa, pb = _perso(client, "A"), _perso(client, "B")
    client.put(f"/api/regions/{a}/locuteur", json={"personnage_id": pa})
    client.put(f"/api/regions/{b}/locuteur", json={"personnage_id": pb})
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", "")])
    _seed(db_path, b, [(0, "RIT", "rire", "VERB", "")])
    res = client.get("/api/analyse/concordance", params={"personnage": pa}).json()
    assert {r["lemme"] for r in res["results"]} == {"crier"}        # personnage seul, sans pivot
    assert client.get("/api/analyse/concordance").status_code == 422   # mais aucun critère -> 422


def test_facette_id_inconnu_404(client, album, planche):
    assert client.get("/api/analyse/frequences",
                      params={"champ": "lemme", "personnage": 9999}).status_code == 404
    assert client.get("/api/analyse/frequences",
                      params={"champ": "lemme", "attributs": 9999}).status_code == 404


def test_recherche_par_personnage_et_attribut(client, album, planche, db_path):
    """Cohérence du drill : Recherche filtre aussi par locuteur et par attribut."""
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    pa, pb = _perso(client, "A"), _perso(client, "B")
    client.put(f"/api/regions/{a}/locuteur", json={"personnage_id": pa})
    client.put(f"/api/regions/{b}/locuteur", json={"personnage_id": pb})
    r = client.get("/api/recherche", params={"personnage": pa}).json()
    assert {x["region_id"] for x in r["results"]} == {a}
    d = client.post("/api/attributs/dimensions", json={"cible": "personnage", "nom": "origine"}).json()["id"]
    v = client.post(f"/api/attributs/dimensions/{d}/valeurs", json={"valeur": "rural"}).json()["id"]
    client.put(f"/api/personnages/{pa}/attributs", json={"valeur_id": v})
    r = client.get("/api/recherche", params={"attributs": v}).json()
    assert {x["region_id"] for x in r["results"]} == {a}


def test_concordance_critere_vide_422(client, album, planche):
    """Régression : un tag vide passe le garde brut mais ne produit aucune clause →
    422 (et non un « WHERE » vide → 500)."""
    assert client.get("/api/analyse/concordance", params={"tags": " "}).status_code == 422
    assert client.get("/api/analyse/concordance", params={"tags": ""}).status_code == 422


def test_concordance_expose_le_contexte_kwic(client, album, planche, db_path):
    """Contrat de la vue KWIC (B2) : la concordance porte de quoi rendre une ligne
    « mot en contexte » — texte (pivot), ocr_texte (contexte de la bulle), locuteur et
    citation. `ocr_texte` est posé EN DIRECT (pas de reindex → pas de token auto), le token
    est semé APRÈS → occurrence unique déterministe (indépendant de la présence de spaCy)."""
    r = _region(client, planche["id"])
    p = _perso(client, "Haddock")
    client.put(f"/api/regions/{r}/locuteur", json={"personnage_id": p})
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE regions SET ocr_texte = ? WHERE id = ?", ("TU DOIS TE TAIRE", r))
    conn.commit()
    conn.close()
    _seed(db_path, r, [(3, "TAIRE", "taire", "VERB", "")])

    res = client.get("/api/analyse/concordance", params={"lemme": "taire"}).json()
    assert res["count"] == 1
    row = res["results"][0]
    assert row["texte"] == "TAIRE"                    # pivot
    assert row["ocr_texte"] == "TU DOIS TE TAIRE"     # contexte
    assert row["locuteur"] == "Haddock"               # méta
    assert row["citation"] and row["citation"]["texte"]   # citation dérivée


# --------------------------------------------------------------------------- #
# Croisements 2D (ANA-2 / B3)
# --------------------------------------------------------------------------- #
def test_croisement_tag_x_pos(client, album, planche, db_path):
    """Matrice tag × POS : marges = fréquences réelles, cellules = comptes, total cohérent."""
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    _tags(client, a, ["colère"])
    _tags(client, b, ["joie"])
    _seed(db_path, a, [(0, "CRIE", "crier", "VERB", ""), (1, "FORT", "fort", "ADJ", "")])
    _seed(db_path, b, [(0, "RIT", "rire", "VERB", "")])

    r = client.get("/api/analyse/croisement", params={"axe_x": "tag", "axe_y": "pos"}).json()
    assert r["filtre_x"] == "tags" and r["filtre_y"] == "pos"       # noms de drill
    marges = {x["libelle"]: x["total"] for x in r["x"]}
    assert marges["colère"] == 2 and marges["joie"] == 1
    xi = next(i for i, x in enumerate(r["x"]) if x["libelle"] == "colère")
    cellules = {r["y"][j]["libelle"]: r["grille"][xi][j] for j in range(len(r["y"]))}
    assert cellules.get("VERB") == 1 and cellules.get("ADJ") == 1
    assert r["total"] == 3


def test_croisement_axe_dimension_porte_la_cle_de_drill(client, album, planche, db_path):
    """Axe dimension (valeur via la CASE) : la clé de cellule est le valeur_id (pour drill
    par `attributs`), le libellé la valeur, et l'axe est nommé par la dimension."""
    a = _region(client, planche["id"], type="case")
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "valence"}).json()["id"]
    val = client.post(f"/api/attributs/dimensions/{dim}/valeurs",
                      json={"valeur": "positive"}).json()["id"]
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)", (a, val))
    conn.commit()
    conn.close()
    _seed(db_path, a, [(0, "MOT", "mot", "NOUN", "")])

    r = client.get("/api/analyse/croisement",
                   params={"axe_x": f"dim:{dim}", "axe_y": "pos"}).json()
    assert r["filtre_x"] == "attributs" and r["libelle_x"] == "valence"
    x0 = next(x for x in r["x"] if x["libelle"] == "positive")
    assert x0["cle"] == val and x0["total"] == 1


def test_croisement_dimension_sans_faux_vide(client, album, planche, db_path):
    """Régression : un locuteur portant des valeurs de DEUX dimensions ne doit pas produire
    une fausse ligne « (vide) » quand on croise par UNE dimension — le filtre de dimension
    porte sur l'affectation, pas seulement sur la valeur jointe."""
    a = _region(client, planche["id"])
    p = _perso(client, "Zorglub")
    client.put(f"/api/regions/{a}/locuteur", json={"personnage_id": p})
    d1 = client.post("/api/attributs/dimensions",
                     json={"cible": "personnage", "nom": "genre"}).json()["id"]
    v1 = client.post(f"/api/attributs/dimensions/{d1}/valeurs",
                     json={"valeur": "homme"}).json()["id"]
    d2 = client.post("/api/attributs/dimensions",
                     json={"cible": "personnage", "nom": "origine"}).json()["id"]
    v2 = client.post(f"/api/attributs/dimensions/{d2}/valeurs",
                     json={"valeur": "minorité"}).json()["id"]
    client.put(f"/api/personnages/{p}/attributs", json={"valeur_id": v1})
    client.put(f"/api/personnages/{p}/attributs", json={"valeur_id": v2})
    _seed(db_path, a, [(0, "MOT", "mot", "NOUN", "")])

    r = client.get("/api/analyse/croisement",
                   params={"axe_x": f"dim:{d1}", "axe_y": "pos"}).json()
    assert {x["libelle"]: x["total"] for x in r["x"]} == {"homme": 1}   # aucune « (vide) »
    assert r["total"] == 1


def test_croisement_axe_inconnu_422(client, album, planche):
    assert client.get("/api/analyse/croisement",
                      params={"axe_x": "farfelu", "axe_y": "pos"}).status_code == 422
    assert client.get("/api/analyse/croisement",
                      params={"axe_x": "dim:99999", "axe_y": "pos"}).status_code == 404
