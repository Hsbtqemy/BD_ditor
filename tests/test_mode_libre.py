"""Le MODE LIBRE — le serveur après la migration v39 (ANN-7 ; `docs/ann7-mode-libre-cadrage.md`,
J3 et « se tranchent en route », tranchés par Hugo le 2026-11-06).

J3 : une entrée née « nom : valeur » en posant naît `plusieurs` — « sentiment : perte » et
« sentiment : tristesse » font deux relevés sur une même bulle —, une entrée née simple garde
`une` ; une même valeur ne se pose pas deux fois sur une même cible entière ; passer une
entrée de `plusieurs` à `une` est refusé quand deux de ses relevés vivent sur une même cible.
Et « Remplacer par la mienne » sur une entrée `une` pose la valeur TAPÉE, née au besoin.
"""
import sqlite3

from conftest import ADMIN
from grilles_decor import STAG
from test_grille_de_travail import _travail
from test_releves import bulle, decor, poser  # noqa: F401


def _q(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, p)]
    finally:
        c.close()


def _releves(db_path, grille_id, region_id=None):
    sql = "SELECT * FROM releve WHERE grille_id = ?" + (" AND region_id = ?" if region_id else "")
    return _q(db_path, sql + " ORDER BY id",
              (grille_id, region_id) if region_id else (grille_id,))


def _plan(client, t):
    return {e["cle"]: e for e in client.get(f"/api/grilles/{t['grille_id']}/versions/1",
                                            headers=ADMIN).json()["entrees"]}


# --------------------------------------------------------------------------- #
# J3 : la cardinalité d'une étiquette née en posant
# --------------------------------------------------------------------------- #
def test_nom_valeur_nait_plusieurs_et_une_seconde_valeur_s_ajoute(client, decor, db_path):
    t = _travail(client, decor, db_path)
    b = bulle(t)
    poser(client, t, region_id=b, nouvelle_entree={"libelle": "sentiment : perte"})
    r2 = poser(client, t, region_id=b, nouvelle_entree={"libelle": "sentiment : tristesse"})
    assert r2["une"] is False, r2
    assert sorted(x["variante_cle"] for x in _releves(db_path, t["grille_id"], b)) == [
        "perte", "tristesse"]
    plan = _plan(client, t)
    assert (plan["sentiment"]["cardinalite"], plan["sentiment"]["cardinalite_declaree"]) == (
        "plusieurs", "plusieurs")
    # Le journal de sa naissance le dit.
    assert _q(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table = 'grille' "
                       "AND apres LIKE '%\"cardinalite\": \"plusieurs\"%'")[0]["n"] == 1


def test_une_etiquette_simple_garde_une(client, decor, db_path):
    t = _travail(client, decor, db_path)
    b = bulle(t)
    poser(client, t, region_id=b, nouvelle_entree={"libelle": "ironie"})
    r = poser(client, t, attendu=(409,), region_id=b, nouvelle_entree={"libelle": "ironie"})
    assert "releve_existant" in r["detail"], r
    plan = _plan(client, t)
    assert (plan["ironie"]["cardinalite"], plan["ironie"]["cardinalite_declaree"]) == (
        "une", None)


# --------------------------------------------------------------------------- #
# Le doublon : une même valeur ne se pose pas deux fois sur une même cible entière
# --------------------------------------------------------------------------- #
def test_la_meme_valeur_ne_se_pose_pas_deux_fois_sur_une_zone(client, decor, db_path):
    t = _travail(client, decor, db_path)
    b = bulle(t)
    r1 = poser(client, t, region_id=b, nouvelle_entree={"libelle": "sentiment : perte"})
    # Retapée (casse, espaces) : la même valeur.
    r = poser(client, t, attendu=(409,), region_id=b,
              nouvelle_entree={"libelle": "Sentiment :  PERTE"})
    assert r["detail"]["releve_doublon"]["id"] == r1["id"], r
    assert "sentiment · perte" in r["detail"]["message"], r
    # Nommée par sa clé : la même.
    r = poser(client, t, attendu=(409,), region_id=b, entree_cle="sentiment",
              variante_cle="perte")
    assert r["detail"]["releve_doublon"]["id"] == r1["id"], r
    assert len(_releves(db_path, t["grille_id"], b)) == 1
    # Sur une AUTRE zone, elle se pose.
    poser(client, t, region_id=t["zones"]["case"], entree_cle="sentiment", variante_cle="perte")


def test_modifier_vers_une_valeur_deja_posee_est_refuse(client, decor, db_path):
    t = _travail(client, decor, db_path)
    b = bulle(t)
    poser(client, t, region_id=b, nouvelle_entree={"libelle": "sentiment : perte"})
    r2 = poser(client, t, region_id=b, nouvelle_entree={"libelle": "sentiment : tristesse"})
    r = client.put(f"/api/releves/{r2['id']}", headers=STAG,
                   json={"variante_cle": "perte", "vu": {"variante_cle": "tristesse"}})
    assert r.status_code == 409 and "releve_doublon" in r.json()["detail"], r.text
    assert sorted(x["variante_cle"] for x in _releves(db_path, t["grille_id"], b)) == [
        "perte", "tristesse"]


def test_une_fusion_ne_fabrique_pas_de_doublon(client, decor, db_path):
    """Fusionner « humeur » dans « sentiment » poserait deux fois « perte » sur la bulle : la
    fusion est refusée, comme celle qui doublerait une entrée « une seule fois »."""
    t = _travail(client, decor, db_path)
    b = bulle(t)
    poser(client, t, region_id=b, nouvelle_entree={"libelle": "sentiment : perte"})
    poser(client, t, region_id=b, nouvelle_entree={"libelle": "humeur : perte"})
    r = client.post(f"/api/grilles/{t['grille_id']}/entrees/humeur/fusion", headers=ADMIN,
                    json={"dans": "sentiment"})
    assert r.status_code == 409, r.text
    assert len(_releves(db_path, t["grille_id"], b)) == 2


# --------------------------------------------------------------------------- #
# « plusieurs » → « une » : refusé sur des relevés qui se contredisent ; sinon ils suivent
# --------------------------------------------------------------------------- #
def test_plusieurs_vers_une_refuse_sur_deux_releves_d_une_meme_zone(client, decor, db_path):
    t = _travail(client, decor, db_path)
    b = bulle(t)
    poser(client, t, region_id=b, nouvelle_entree={"libelle": "sentiment : perte"})
    r2 = poser(client, t, region_id=b, nouvelle_entree={"libelle": "sentiment : tristesse"})
    url = f"/api/grilles/{t['grille_id']}/entrees/sentiment"
    r = client.patch(url, headers=ADMIN, json={"cardinalite": "une"})
    assert r.status_code == 409, r.text
    assert "cardinalite_contredite" in {a["code"] for a in r.json()["detail"]["anomalies"]}
    assert _plan(client, t)["sentiment"]["cardinalite"] == "plusieurs"
    # Un relevé retiré : plus de contradiction, le passage se fait, et le relevé qui reste
    # devient « une » — une nouvelle valeur sur la bulle reçoit alors le 409 de la cardinalité.
    assert client.delete(f"/api/releves/{r2['id']}", headers=STAG).status_code == 204
    r = client.patch(url, headers=ADMIN, json={"cardinalite": "une"})
    assert r.status_code == 200, r.text
    assert [x["une"] for x in _releves(db_path, t["grille_id"], b)] == [1]
    r = poser(client, t, attendu=(409,), region_id=b, entree_cle="sentiment",
              variante_cle="tristesse")
    assert "releve_existant" in r["detail"], r
    # Et de retour à « plusieurs » : les relevés suivent encore.
    r = client.patch(url, headers=ADMIN, json={"cardinalite": "plusieurs"})
    assert r.status_code == 200, r.text
    assert [x["une"] for x in _releves(db_path, t["grille_id"], b)] == [0]
    poser(client, t, region_id=b, entree_cle="sentiment", variante_cle="tristesse")


# --------------------------------------------------------------------------- #
# « Remplacer par la mienne » pose la valeur TAPÉE (vu sur la recette le 2026-11-06)
# --------------------------------------------------------------------------- #
def _sentiment_une(client, t, b):
    """« sentiment : perte » posé sur la bulle, puis « sentiment » passé à « une »."""
    r1 = poser(client, t, region_id=b, nouvelle_entree={"libelle": "sentiment : perte"})
    r = client.patch(f"/api/grilles/{t['grille_id']}/entrees/sentiment", headers=ADMIN,
                     json={"cardinalite": "une"})
    assert r.status_code == 200, r.text
    return r1


def test_remplacer_pose_la_valeur_tapee_et_la_fait_naitre(client, decor, db_path):
    t = _travail(client, decor, db_path)
    b = bulle(t)
    r1 = _sentiment_une(client, t, b)
    refus = poser(client, t, attendu=(409,), region_id=b,
                  nouvelle_entree={"libelle": "sentiment : tristesse"})
    ex = refus["detail"]["releve_existant"]
    assert ex["id"] == r1["id"] and ex["variante_cle"] == "perte"
    # Ce qu'envoie « Remplacer par la mienne » (`BDAnnotation.remplacementCardinalite`).
    r = client.put(f"/api/releves/{ex['id']}", headers=STAG,
                   json={"nouvelle_variante": "tristesse", "vu": {"variante_cle": "perte"}})
    assert r.status_code == 200, r.text
    assert r.json()["variante_cle"] == "tristesse", r.json()
    assert [(x["id"], x["variante_cle"]) for x in _releves(db_path, t["grille_id"], b)] == [
        (r1["id"], "tristesse")]
    assert [v["libelle"] for v in _plan(client, t)["sentiment"]["variantes"]] == [
        "perte", "tristesse"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table = 'grille' "
                       "AND apres LIKE '%variante_neuve%tristesse%'")[0]["n"] == 1
    # Une valeur qui existe déjà est reprise par son libellé, sans rien faire naître.
    r = client.put(f"/api/releves/{ex['id']}", headers=STAG,
                   json={"nouvelle_variante": "PERTE", "vu": {"variante_cle": "tristesse"}})
    assert r.status_code == 200 and r.json()["variante_cle"] == "perte", r.text
    assert len(_plan(client, t)["sentiment"]["variantes"]) == 2


def test_remplacer_par_un_libelle_garde_la_valeur_vue(client, decor, db_path):
    """La valeur vue tient comme pour une variante nommée par sa clé (CONC-3) : périmée, 409,
    et la variante tapée ne naît pas."""
    t = _travail(client, decor, db_path)
    b = bulle(t)
    r1 = _sentiment_une(client, t, b)
    r = client.put(f"/api/releves/{r1['id']}", headers=STAG,
                   json={"nouvelle_variante": "colère", "vu": {"variante_cle": "joie"}})
    assert r.status_code == 409 and "conflit" in r.json()["detail"], r.text
    assert [v["libelle"] for v in _plan(client, t)["sentiment"]["variantes"]] == ["perte"]


def test_nouvelle_variante_se_dit_seule_et_seulement_dans_une_grille_ouverte(client, decor,
                                                                             db_path):
    t = _travail(client, decor, db_path)
    r1 = poser(client, t, region_id=bulle(t), nouvelle_entree={"libelle": "sentiment : perte"})
    r = client.put(f"/api/releves/{r1['id']}", headers=STAG,
                   json={"nouvelle_variante": "x", "variante_cle": "perte"})
    assert r.status_code == 422 and "une fois" in r.text, r.text
    # La grille du décor est FERMÉE : une valeur n'y naît pas.
    f = poser(client, decor, region_id=decor["zones"]["cartouche"], entree_cle="ton-de-voix",
              variante_cle="chuchote")
    r = client.put(f"/api/releves/{f['id']}", headers=STAG,
                   json={"nouvelle_variante": "susurré"})
    assert r.status_code == 422 and "grille ouverte" in r.text, r.text
    # Sous une entrée sans variantes : 422.
    s = poser(client, t, region_id=t["zones"]["case"], nouvelle_entree={"libelle": "ironie"})
    r = client.put(f"/api/releves/{s['id']}", headers=STAG, json={"nouvelle_variante": "x"})
    assert r.status_code == 422 and "pas de variantes" in r.text, r.text
