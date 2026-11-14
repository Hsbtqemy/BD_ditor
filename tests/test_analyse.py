"""Routes d'analyse linguistique — filtres, concordance, croisement, exports.

Les filtres par tag (ANA-1), par attribut et la portée héritée de la case sont partis avec
le basculement d'ANN-7 ; leurs anciens paramètres sont refusés par un 422 nommé (I7).

Les tokens sont semés EN DIRECT dans la table `tokens` (via une connexion SQLite
séparée) plutôt que par le NLP : la couche spaCy est optionnelle et souvent absente
en CI, alors que la logique de FILTRE (SQL) doit être testée inconditionnellement.
À semer APRÈS les écritures d'annotation : `reindex_region` régénère `tokens` (donc
les efface quand spaCy est absent). Couvre aussi la dette QA-3 (cf. docs/backlog.md).
"""
import sqlite3

import pytest


def _region(client, planche_id, type="bulle"):
    return client.post(f"/api/planches/{planche_id}/regions",
                       json={"type": type, "x": 10, "y": 10, "w": 50, "h": 40}).json()["id"]


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


def test_recherche_par_personnage(client, album, planche, db_path):
    """Cohérence du drill : la Recherche filtre aussi par locuteur."""
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    pa, pb = _perso(client, "A"), _perso(client, "B")
    client.put(f"/api/regions/{a}/locuteur", json={"personnage_id": pa})
    client.put(f"/api/regions/{b}/locuteur", json={"personnage_id": pb})
    r = client.get("/api/recherche", params={"personnage": pa}).json()
    assert {x["region_id"] for x in r["results"]} == {a}


def test_concordance_critere_vide_422(client, album, planche):
    """Régression : un critère qui passe le garde brut mais ne produit aucune clause (un
    lemme réduit à « * ») → 422, et non un « WHERE » vide → 500. Le cas d'origine était un
    tag vide."""
    rep = client.get("/api/analyse/concordance", params={"lemme": "*"})
    assert rep.status_code == 422, rep.text


# --------------------------------------------------------------------------- #
# ANN-7, I7 — les anciens paramètres du vocabulaire, refusés en le disant
# --------------------------------------------------------------------------- #
# FastAPI ignore un paramètre inconnu : un lien d'hier filtré par tag rendrait le corpus
# entier en ayant l'air filtré. Chaque route qui les acceptait les refuse par un 422 nommé.
_ROUTES_FILTREES = [
    ("/api/analyse/frequences", {"champ": "lemme"}),
    ("/api/analyse/lemmes", {}),
    ("/api/analyse/frequences.csv", {"champ": "lemme"}),
    ("/api/analyse/concordance", {"lemme": "crier"}),
    ("/api/analyse/concordance.csv", {"lemme": "crier"}),
    ("/api/analyse/comparaison", {"champ": "lemme"}),
    ("/api/analyse/comparaison.csv", {"champ": "lemme"}),
    ("/api/analyse/croisement", {"axe_x": "pos", "axe_y": "type"}),
    ("/api/analyse/croisement.csv", {"axe_x": "pos", "axe_y": "type"}),
    ("/api/recherche", {"q": "x"}),
    ("/api/recherche/export.csv", {"q": "x"}),
]


@pytest.mark.parametrize("route,base", _ROUTES_FILTREES, ids=[r for r, _ in _ROUTES_FILTREES])
@pytest.mark.parametrize("ancien", ["tags", "tag_scope", "attributs", "a_tags", "b_tags",
                                    "a_attributs", "b_attributs"])
def test_un_ancien_parametre_du_vocabulaire_est_refuse_en_le_disant(client, album, route,
                                                                      base, ancien):
    rep = client.get(route, params={**base, ancien: "1"})
    assert rep.status_code == 422, rep.text
    assert "n'existent plus" in rep.json()["detail"] and ancien in rep.json()["detail"]


def test_deux_anciens_parametres_sont_nommes_tous_deux(client, album):
    rep = client.get("/api/recherche", params={"q": "x", "tags": "1", "attributs": "2"})
    assert rep.status_code == 422, rep.text
    assert rep.json()["detail"].startswith(
        "Les tags et les attributs n'existent plus : « attributs », « tags » ne sont plus "
        "acceptés."), rep.json()["detail"]


@pytest.mark.parametrize("route,base", _ROUTES_FILTREES, ids=[r for r, _ in _ROUTES_FILTREES])
def test_sans_ancien_parametre_la_route_repond(client, album, route, base):
    """Le témoin : sans paramètre d'hier, aucune de ces routes ne refuse par le 422 des
    tags — sans quoi le test ci-dessus passerait sur une route qui refuse tout."""
    rep = client.get(route, params=base)
    assert "n'existent plus" not in rep.text


@pytest.mark.parametrize("axe", ["tag", "dim:3"])
def test_un_axe_d_hier_du_croisement_est_refuse_en_le_disant(client, album, axe):
    rep = client.get("/api/analyse/croisement", params={"axe_x": axe, "axe_y": "pos"})
    assert rep.status_code == 422, rep.text
    assert "n'existent plus" in rep.json()["detail"]


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


def test_croisement_axe_inconnu_422(client, album, planche):
    rep = client.get("/api/analyse/croisement", params={"axe_x": "farfelu", "axe_y": "pos"})
    assert rep.status_code == 422 and "Axe inconnu" in rep.json()["detail"]


# --------------------------------------------------------------------------- #
# ANA-7 — les exports CSV des vues d'analyse
# --------------------------------------------------------------------------- #
def test_l_export_de_distribution_dit_la_meme_chose_que_sa_route_json(client, album,
                                                                     planche, db_path):
    """ANA-7 — le CSV et le JSON partagent leur cœur, donc ils ne peuvent pas diverger.

    C'est la propriété que la case du chantier demande. Deux chemins de calcul finiraient
    par se séparer sur un filtre, et la divergence serait invisible : les deux réponses
    resteraient plausibles. On la vérifie sur le CONTENU, pas sur la structure du code —
    un test qui lirait le source dirait que la règle est couverte sans l'être.
    """
    r = _region(client, planche["id"])
    _seed(db_path, r, [(0, "chat", "chat", "NOUN", ""), (1, "chat", "chat", "NOUN", ""),
                       (2, "dort", "dormir", "VERB", "")])

    js = client.get("/api/analyse/frequences?champ=lemme").json()["results"]
    csv_txt = client.get("/api/analyse/frequences.csv?champ=lemme").text
    lignes = [l for l in csv_txt.lstrip("﻿").strip().split("\n")]

    assert lignes[0] == "lemme;pos;frequence"
    assert len(lignes) - 1 == len(js), "le CSV et le JSON ne comptent pas les mêmes lignes"
    for attendu, ligne in zip(js, lignes[1:]):
        assert ligne == f'{attendu["lemme"]};{attendu["pos"]};{attendu["freq"]}'


def test_un_export_d_analyse_neutralise_l_injection_de_formule(client, album, planche,
                                                              db_path):
    """ANA-7 — `_csv_safe` sur tout texte libre, comme les deux exports qui existaient.

    Le lemme vient de l'OCR puis de corrections humaines : c'est du texte libre, et un
    tableur exécute une cellule qui commence par `=`. La case du chantier l'exige, et elle
    a raison de l'exiger explicitement — un `csv.writer` nu est exactement ce qu'on écrit
    quand on ne se pose pas la question.
    """
    r = _region(client, planche["id"])
    _seed(db_path, r, [(0, "=CMD()", "=CMD()", "NOUN", "")])
    txt = client.get("/api/analyse/frequences.csv?champ=lemme").text
    assert "'=CMD()" in txt, f"formule non neutralisée : {txt!r}"


def test_le_croisement_s_exporte_dans_les_deux_formes(client, album, planche, db_path):
    """ANA-7 — arbitrage du 2026-09-08 : les deux, au choix.

    La matrice se cite dans un article, les lignes plates se retraitent dans R ou pandas,
    et une matrice se reconstruit d'un pivot quand l'inverse perd de l'information. Les
    deux partent du MÊME cœur : ce sont deux mises en forme, pas deux calculs.
    """
    r = _region(client, planche["id"])
    _seed(db_path, r, [(0, "chat", "chat", "NOUN", ""), (1, "dort", "dormir", "VERB", "")])

    plat = client.get("/api/analyse/croisement.csv?axe_x=pos&axe_y=provenance").text
    plat = plat.lstrip("﻿").strip().split("\n")
    assert plat[0] == "catégorie (POS);provenance;n;marge_x;marge_y"
    assert any(l.startswith("NOUN;auto;1") for l in plat[1:]), plat

    mat = client.get(
        "/api/analyse/croisement.csv?axe_x=pos&axe_y=provenance&forme=matrice").text
    mat = mat.lstrip("﻿").strip().split("\n")
    assert mat[0].startswith("catégorie (POS) × provenance;")
    assert mat[0].endswith(";Total"), mat[0]
    assert mat[-1].startswith("Total;"), mat[-1]

    assert client.get(
        "/api/analyse/croisement.csv?axe_x=pos&axe_y=provenance&forme=zzz"
    ).status_code == 422


def test_le_nom_du_fichier_porte_la_troncature(client, album, planche, db_path,
                                               monkeypatch):
    """ANA-7 — le fichier doit DIRE qu'il est amputé, et le nom est la seule place gratuite.

    Une ligne de commentaire en tête décale l'en-tête pour un tableur ; une ligne en pied
    entre dans les données pour pandas ; un en-tête HTTP ne survit pas au premier
    déplacement du fichier. Le nom voyage avec lui et ne touche pas son contenu.
    """
    import routes.analyse as ra
    r = _region(client, planche["id"])
    _seed(db_path, r, [(0, "chat", "chat", "NOUN", ""), (1, "dort", "dormir", "VERB", "")])

    entier = client.get("/api/analyse/frequences.csv")
    assert 'filename="distribution-lemme.csv"' in entier.headers["content-disposition"]

    monkeypatch.setattr(ra, "PLAFOND_EXPORT", 1)         # le plafond mord
    coupe = client.get("/api/analyse/frequences.csv")
    assert 'filename="distribution-lemme-tronque-1.csv"' in coupe.headers["content-disposition"]


def test_un_export_d_analyse_est_lisible_par_un_tableur(client, album, planche, db_path):
    """ANA-7 — BOM UTF-8 et `Content-Disposition`, par `_csv_response` et non à la main.

    Sans le BOM, Excel sous Windows rend les accents illisibles ; sans l'en-tête de
    disposition, le fichier s'affiche dans l'onglet au lieu de se télécharger. Les deux
    exports qui existaient passaient déjà par ce helper : la case du chantier demande que
    les six neufs en fassent autant, plutôt qu'un `Response` monté sur place.
    """
    r = _region(client, planche["id"])
    _seed(db_path, r, [(0, "été", "été", "NOUN", "")])
    rep = client.get("/api/analyse/frequences.csv")
    assert rep.content.startswith("﻿".encode("utf-8")), "BOM absent : Excel lira mal les accents"
    assert rep.headers["content-type"].startswith("text/csv")
    assert "attachment;" in rep.headers["content-disposition"]


# --------------------------------------------------------------------------- #
# ANA-6 — le préfixe de lemme, par joker EXPLICITE
# --------------------------------------------------------------------------- #
def _lemmes_trouves(client, saisie):
    rep = client.get("/api/analyse/concordance", params={"lemme": saisie})
    assert rep.status_code == 200, rep.text
    return sorted(x["lemme"] for x in rep.json()["results"])


def test_le_joker_cherche_par_prefixe_et_l_exact_reste_exact(client, album, planche, db_path):
    """`otage*` trouve « otages » ; `otage` ne trouve QUE « otage ».

    L'exact n'est pas un détail : la cellule d'un croisement ouvre sa concordance par la
    valeur exacte. Un préfixe implicite y ferait compter à `pas` les « passer » et les
    « passage » — des nombres plausibles, et faux.
    """
    r = _region(client, planche["id"])
    _seed(db_path, r, [(0, "OTAGE", "otage", "NOUN", ""), (1, "OTAGES", "otages", "NOUN", ""),
                       (2, "PAS", "pas", "ADV", ""), (3, "PASSER", "passer", "VERB", "")])
    assert _lemmes_trouves(client, "otage") == ["otage"]
    assert _lemmes_trouves(client, "otage*") == ["otage", "otages"]
    assert _lemmes_trouves(client, "OTAGE*") == ["otage", "otages"]   # minusculé comme l'exact
    assert _lemmes_trouves(client, "pas") == ["pas"]
    assert _lemmes_trouves(client, "pas*") == ["pas", "passer"]
    # Les quatre surfaces partagent `_analyse_filtres` : la distribution lit le joker aussi.
    freq = client.get("/api/analyse/frequences", params={"lemme": "otage*"}).json()
    assert {x["lemme"] for x in freq["results"]} == {"otage", "otages"}


def test_le_joker_echappe_les_jokers_de_like(client, album, planche, db_path):
    """`%` et `_` sont les jokers de LIKE, pas ceux de l'utilisateur : `a_*` ne doit pas
    lire « a, un caractère quelconque, puis n'importe quoi »."""
    r = _region(client, planche["id"])
    _seed(db_path, r, [(0, "x", "a_b", "X", ""), (1, "x", "axb", "X", ""),
                       (2, "x", "c%d", "X", ""), (3, "x", "cxd", "X", "")])
    assert _lemmes_trouves(client, "a_*") == ["a_b"]
    assert _lemmes_trouves(client, "c%*") == ["c%d"]


def test_un_asterisque_seul_n_est_pas_un_critere(client, album, planche, db_path):
    """« * » ne doit pas rendre tout le corpus : il ne reste rien à chercher, donc la
    concordance répond son 422 ordinaire, comme pour un critère vide."""
    r = _region(client, planche["id"])
    _seed(db_path, r, [(0, "OTAGE", "otage", "NOUN", "")])
    assert client.get("/api/analyse/concordance", params={"lemme": "*"}).status_code == 422


def test_la_recherche_lit_le_joker_comme_l_analyse(client, album, planche, db_path):
    """Même contrat pour `lemme=` sur les deux surfaces : une descente de l'Exploration vers
    la Recherche ne doit pas changer de sens en chemin. Et « * » seul n'y fabrique plus une
    clause vide — la requête finissait en `AND )`."""
    a, b = _region(client, planche["id"]), _region(client, planche["id"])
    _seed(db_path, a, [(0, "OTAGES", "otages", "NOUN", "")])
    _seed(db_path, b, [(0, "OTAGE", "otage", "NOUN", "")])
    ids = lambda q: {x["region_id"] for x in
                     client.get("/api/recherche", params={"lemme": q}).json()["results"]}
    assert ids("otage*") == {a, b}
    assert ids("otage") == {b}
    assert client.get("/api/recherche", params={"lemme": "*"}).status_code == 200


def test_le_nom_du_fichier_dit_le_prefixe(client, album, planche, db_path):
    """Le joker se LIT dans le nom : laissé tel quel, il serait devenu un `_` muet — Windows
    refuse `*` dans un nom de fichier."""
    rep = client.get("/api/analyse/concordance.csv", params={"lemme": "otage*"})
    assert 'filename="concordance-otage-prefixe.csv"' in rep.headers["content-disposition"]


# --------------------------------------------------------------------------- #
# ANA-6 — une ligne de concordance porte sa note (ses tags sont partis : ANN-7)
# --------------------------------------------------------------------------- #
def test_une_ligne_porte_sa_note_et_plus_de_tags(client, album, planche, db_path):
    """La note d'une ligne, et rien d'autre : les tags d'hier (posés en base) n'y sont plus,
    ni ceux de la ligne ni ceux de sa case."""
    from conftest import poser_tags
    case = _region(client, planche["id"], type="case")
    bulle, nue = _region(client, planche["id"]), _region(client, planche["id"])
    poser_tags(db_path, case, ["colère"])
    client.put(f"/api/regions/{bulle}/annotation", json={"note": "Premier ultimatum."})
    poser_tags(db_path, bulle, ["refus"])
    _seed(db_path, bulle, [(0, "DIS", "dire", "VERB", "")], parent_id=case)
    _seed(db_path, nue, [(0, "DIT", "dire", "VERB", "")])

    lignes = {r["region_id"]: r for r in
              client.get("/api/analyse/concordance", params={"lemme": "dire"}).json()["results"]}
    assert lignes[bulle]["note"] == "Premier ultimatum."
    assert lignes[nue]["note"] == ""                                 # rien, et pas None
    assert "tags" not in lignes[bulle] and "parent_id" not in lignes[bulle]


def test_l_export_de_concordance_porte_la_note_en_fin_de_ligne(client, album, planche,
                                                               db_path):
    """La note en dernière colonne ; la colonne `tags` est RETIRÉE, et non laissée vide
    (cadrage d'ANN-7, « se tranchent en route »)."""
    import csv
    import io
    bulle = _region(client, planche["id"])
    client.put(f"/api/regions/{bulle}/annotation", json={"note": "=CMD()"})
    _seed(db_path, bulle, [(0, "DIS", "dire", "VERB", "")])

    texte = client.get("/api/analyse/concordance.csv", params={"lemme": "dire"}).text
    tete, ligne = list(csv.reader(io.StringIO(texte.lstrip("﻿")), delimiter=";"))[:2]
    assert tete[-1] == "note" and "tags" not in tete and len(tete) == 13
    assert ligne[-1] == "'=CMD()"             # une note est du texte libre : `_csv_safe`
