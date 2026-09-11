"""ANA-4 — la keyness par log-vraisemblance, verrouillée sur des comptes connus.

Les valeurs attendues sont écrites en forme close (2·f·ln 2 pour une valeur absente d'un
côté, 0 pour une répartition proportionnelle) ou calculées une fois et FIGÉES : un test
qui recalculerait la formule pour la comparer à elle-même ne verrouillerait rien.
"""
import math

import pytest

from vraisemblance import log_vraisemblance


@pytest.mark.parametrize("fa, fb, ta, tb, attendu", [
    (10, 0, 1000, 1000, 20 * math.log(2)),       # absente de B : 2·10·ln 2
    (0, 10, 1000, 1000, -20 * math.log(2)),      # le même en miroir : le signe dit le CÔTÉ
    (8, 0, 1000, 1000, 16 * math.log(2)),
    (300, 270, 1000, 1000, 1.5796771465813428),  # fréquent des deux côtés : peu de preuve
    (50, 50, 1000, 1000, 0.0),                   # également réparti
    (40, 10, 2000, 500, 0.0),                    # même fréquence RELATIVE, tailles inégales
    (0, 0, 1000, 1000, 0.0),                     # absent partout
    (0, 7, 0, 1000, 0.0),                        # un sous-corpus vide ne prouve rien
])
def test_log_vraisemblance_sur_des_comptes_connus(fa, fb, ta, tb, attendu):
    assert log_vraisemblance(fa, fb, ta, tb) == pytest.approx(attendu, abs=1e-9)


def test_la_keyness_fait_remonter_ce_que_l_ecart_enterrait():
    """Le cas qui justifie la mesure, sur deux sous-corpus de même taille : « le » est
    fréquent des deux côtés, « otage » rare et seulement en A. L'écart de fréquence
    relative met « le » devant ; la log-vraisemblance met « otage » devant, parce que huit
    occurrences contre zéro prouvent davantage que 300 contre 270."""
    ta = tb = 1000
    le, otage = (300, 270), (8, 0)

    def ecart(fa, fb):
        return fa / ta - fb / tb

    assert ecart(*le) > ecart(*otage)
    assert log_vraisemblance(*otage, ta, tb) > log_vraisemblance(*le, ta, tb)


def test_les_deux_mesures_s_accordent_sur_le_cote():
    """La route range une valeur parmi les « sur-représentés en A » ou « en B » selon le
    SIGNE de la mesure choisie : changer de mesure ne doit jamais faire changer une valeur
    de côté, seulement de rang."""
    ta, tb = 1200, 800
    for fa in range(0, 30, 3):
        for fb in range(0, 30, 4):
            ecart = fa / ta - fb / tb
            ll = log_vraisemblance(fa, fb, ta, tb)
            assert (ecart > 0) == (ll > 1e-12), (fa, fb)
            assert (ecart < 0) == (ll < -1e-12), (fa, fb)


# --------------------------------------------------------------------------- #
# La route : `metrique` choisit le classement de la comparaison A/B
# --------------------------------------------------------------------------- #
def _deux_sous_corpus(client, planche, db_path):
    """A et B, séparés par un tag, de même taille (32 tokens). « le » y est fréquent des
    deux côtés (30 contre 24), « otage » rare et seulement en A (2), « chat » seulement en
    B (8). L'écart relatif met « le » en tête de A (0,1875 contre 0,0625) ; la
    log-vraisemblance y met « otage » (2,77 contre 0,67). Semé en direct : la couche
    spaCy est optionnelle, et le classement doit se tester sans elle."""
    import sqlite3
    a, b = (client.post(f"/api/planches/{planche['id']}/regions",
                        json={"type": "bulle", "x": 10, "y": 10, "w": 50, "h": 40}).json()["id"]
            for _ in range(2))
    client.put(f"/api/regions/{a}/annotation", json={"note": "", "tags": ["colère"]})
    client.put(f"/api/regions/{b}/annotation", json={"note": "", "tags": ["joie"]})
    mots = {a: ["le"] * 30 + ["otage"] * 2, b: ["le"] * 24 + ["chat"] * 8}
    conn = sqlite3.connect(db_path)                  # APRÈS l'annotation : elle réindexe
    try:
        conn.executemany(
            "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
            "VALUES (?, ?, ?, ?, 'X', '')",
            [(rid, o, m.upper(), m) for rid, liste in mots.items()
             for o, m in enumerate(liste)])
        conn.commit()
    finally:
        conn.close()
    return {"champ": "lemme", "a_tags": "colère", "b_tags": "joie"}


def test_la_comparaison_classe_par_la_mesure_demandee(client, album, planche, db_path):
    """ANA-4 — `metrique=ll` classe par keyness, et le défaut ne change pas : une URL
    partagée avant ce chantier doit rendre le même écran. Les deux mesures s'accordent
    sur le côté, pas sur l'ordre. Une mesure inconnue est un 422, pas un repli muet."""
    base = _deux_sous_corpus(client, planche, db_path)

    def comparer(**extra):
        rep = client.get("/api/analyse/comparaison", params={**base, **extra})
        assert rep.status_code == 200, rep.text
        return rep.json()

    defaut, ecart, ll = comparer(), comparer(metrique="diff"), comparer(metrique="ll")
    assert defaut == ecart
    assert (defaut["metrique"], ll["metrique"]) == ("diff", "ll")
    assert [x["valeur"] for x in ecart["sur_a"]] == ["le", "otage"]
    assert [x["valeur"] for x in ll["sur_a"]] == ["otage", "le"]
    assert [x["valeur"] for x in ll["sur_b"]] == [x["valeur"] for x in ecart["sur_b"]] == ["chat"]
    otage = next(x for x in ll["sur_a"] if x["valeur"] == "otage")
    assert otage["ll"] == pytest.approx(4 * math.log(2), abs=1e-4)
    assert client.get("/api/analyse/comparaison",
                      params={**base, "metrique": "zzz"}).status_code == 422


def test_l_export_de_la_comparaison_trie_comme_l_ecran(client, album, planche, db_path):
    """Le fichier porte les deux mesures en colonnes, et suit l'ORDRE de celle qu'on a
    choisie : l'écran et le fichier partent du même cœur, ils ne doivent pas se
    contredire sur ce qui vient en tête."""
    import csv
    import io
    base = _deux_sous_corpus(client, planche, db_path)

    def lignes(**extra):
        rep = client.get("/api/analyse/comparaison.csv", params={**base, **extra})
        assert rep.status_code == 200, rep.text
        return list(csv.DictReader(io.StringIO(rep.text.lstrip("\ufeff"))))   # BOM Excel

    ecart, ll = lignes(), lignes(metrique="ll")
    assert "ll" in ll[0] and "diff" in ll[0]
    assert ecart[0]["valeur"] == "le"
    assert ll[0]["valeur"] == "otage"
