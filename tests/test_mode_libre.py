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


# --------------------------------------------------------------------------- #
# J5 (c) : qui remanie une étiquette, et la clé `remaniable` du plan
# --------------------------------------------------------------------------- #
def _patch(client, qui, url, corps):
    return client.patch(url, headers=qui, json=corps)


def test_un_annotateur_renomme_une_etiquette_provisoire_et_ses_valeurs(client, decor, db_path):
    t = _travail(client, decor, db_path)
    g = t["grille_id"]
    poser(client, t, region_id=t["zones"]["case"], nouvelle_entree={"libelle": "lieu : forêt"})
    r = _patch(client, STAG, f"/api/grilles/{g}/entrees/lieu",
               {"libelle": "endroit", "vu": {"libelle": "lieu"}})
    assert r.status_code == 200, r.text
    assert "emplois" not in r.json()                 # les comptes restent aux responsables
    r = _patch(client, STAG, f"/api/grilles/{g}/entrees/lieu/variantes/foret",
               {"libelle": "bois"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/grilles/{g}/entrees/lieu/variantes", headers=STAG,
                    json={"libelle": "grotte"})
    assert r.status_code == 201, r.text
    r = _patch(client, STAG, f"/api/grilles/{g}/entrees/lieu",
               {"variantes": [{"libelle": "plage"}]})
    assert r.status_code == 200, r.text
    plan = _plan(client, t)
    assert plan["lieu"]["libelle"] == "endroit"
    assert [v["libelle"] for v in plan["lieu"]["variantes"]] == ["bois", "grotte", "plage"]
    # Au journal, sous son nom.
    assert _q(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table = 'grille' "
                       "AND agent = 'stag' AND apres LIKE '%\"objet\"%'")[0]["n"] == 4
    # Deux renommages croisés : la valeur vue (CONC-3) nomme l'autre.
    r = _patch(client, ADMIN, f"/api/grilles/{g}/entrees/lieu",
               {"libelle": "site", "vu": {"libelle": "lieu"}})
    assert r.status_code == 409 and "conflit" in r.json()["detail"], r.text


def test_un_annotateur_ne_fait_que_renommer_et_ajouter(client, decor, db_path):
    t = _travail(client, decor, db_path)
    g = t["grille_id"]
    poser(client, t, region_id=t["zones"]["case"], nouvelle_entree={"libelle": "ironie"})
    poser(client, t, region_id=t["zones"]["bulle"], nouvelle_entree={"libelle": "humour"})
    url = f"/api/grilles/{g}/entrees/ironie"
    r = _patch(client, STAG, url, {"etat": "defini"})
    assert r.status_code == 403 and "changer son état" in r.text, r.text
    r = _patch(client, STAG, url, {"definition": "un sens second"})
    assert r.status_code == 403, r.text
    r = _patch(client, STAG, url, {"libelle": "ironie mordante", "cardinalite": "plusieurs"})
    assert r.status_code == 403, r.text
    r = client.post(f"{url}/fusion", headers=STAG, json={"dans": "humour"})
    assert r.status_code == 403, r.text
    r = client.post(f"{url}/retrait", headers=STAG)
    assert r.status_code == 403, r.text
    assert _plan(client, t)["ironie"]["libelle"] == "ironie"


def test_une_etiquette_definie_ne_se_renomme_que_par_les_responsables(client, decor, db_path):
    t = _travail(client, decor, db_path)
    g = t["grille_id"]
    r = client.post(f"/api/grilles/{g}/entrees", headers=ADMIN,
                    json={"libelle": "sentiment", "forme": "variantes",
                          "variantes": [{"libelle": "perte"}]})
    assert r.status_code == 201, r.text
    r = _patch(client, STAG, f"/api/grilles/{g}/entrees/sentiment", {"libelle": "émotion"})
    assert r.status_code == 403 and "est définie" in r.text, r.text
    r = client.post(f"/api/grilles/{g}/entrees/sentiment/variantes", headers=STAG,
                    json={"libelle": "joie"})
    assert r.status_code == 403 and "est définie" in r.text, r.text
    r = _patch(client, STAG, f"/api/grilles/{g}/entrees/sentiment/variantes/perte",
               {"libelle": "deuil"})
    assert r.status_code == 403 and "est définie" in r.text, r.text


def test_qui_n_annote_pas_le_projet_ne_renomme_rien(client, decor, db_path):
    from grilles_decor import ANA, SAM, ZOE
    t = _travail(client, decor, db_path)
    g = t["grille_id"]
    poser(client, t, region_id=t["zones"]["case"], nouvelle_entree={"libelle": "ironie"})
    url = f"/api/grilles/{g}/entrees/ironie"
    for qui in (SAM, ANA):                 # membre d'une base protégée ; lectrice de C
        r = _patch(client, qui, url, {"libelle": "x"})
        assert r.status_code == 403, (qui, r.text)
    assert _patch(client, ZOE, url, {"libelle": "x"}).status_code == 404
    # Une grille FERMÉE se remanie au formulaire : 403, et aucun brouillon ne naît.
    r = _patch(client, STAG, f"/api/grilles/{decor['grille_id']}/entrees/cri",
               {"libelle": "hurlement"})
    assert r.status_code == 403, r.text
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille_version WHERE grille_id = ?",
              (decor["grille_id"],))[0]["n"] == 1
    # Même une entrée PROVISOIRE d'une grille fermée : le mode libre est celui des grilles
    # ouvertes. (Un responsable l'a rendue provisoire, dans le brouillon où écrirait le geste.)
    s = decor["grille_id"]
    assert _patch(client, ADMIN, f"/api/grilles/{s}/entrees/cri",
                  {"etat": "provisoire"}).status_code == 200
    r = _patch(client, STAG, f"/api/grilles/{s}/entrees/cri", {"libelle": "hurlement"})
    assert r.status_code == 403, r.text


def test_le_plan_dit_ce_que_l_appelant_peut_remanier(client, decor, db_path):
    from grilles_decor import LEA
    t = _travail(client, decor, db_path)
    g = t["grille_id"]
    poser(client, t, region_id=t["zones"]["case"], nouvelle_entree={"libelle": "ironie"})
    client.post(f"/api/grilles/{g}/entrees", headers=ADMIN, json={"libelle": "écrite"})

    def remaniable(qui, grille=g):
        plan = client.get(f"/api/grilles/{grille}/versions/1", headers=qui).json()
        return {e["cle"]: e["remaniable"] for e in plan["entrees"]}
    tout = {"renommer": True, "ajouter_valeur": True, "ranger": True, "fusionner": True,
            "retirer": True, "etat": True}
    rien = {k: False for k in tout}
    assert remaniable(STAG) == {
        "ironie": {**rien, "renommer": True, "ajouter_valeur": True, "ranger": True},
        "ecrite": {**rien, "ranger": True}}
    assert remaniable(LEA) == {"ironie": tout, "ecrite": tout}
    # Une grille fermée : rien sur place, même pour un responsable.
    assert set(map(lambda x: tuple(x.values()), remaniable(LEA, decor["grille_id"]).values())
               ) == {tuple(rien.values())}
    # La réponse d'un geste porte la même clé.
    r = _patch(client, STAG, f"/api/grilles/{g}/entrees/ironie", {"libelle": "ironie fine"})
    assert {e["cle"]: e["remaniable"] for e in r.json()["plan"]["entrees"]}["ironie"][
        "renommer"] is True


# --------------------------------------------------------------------------- #
# « ↕ Ranger » : l'ordre de la grille de travail, commun au projet, et Ctrl+Z
# --------------------------------------------------------------------------- #
def _ordre(client, t):
    return [e["cle"] for e in client.get(f"/api/grilles/{t['grille_id']}/versions/1",
                                         headers=ADMIN).json()["entrees"]]


def _ranger(client, t, cle, place, qui=STAG, vu=None):
    corps = {"quoi": "entree", "cle": cle, "place": place}
    if vu is not None:
        corps["vu"] = vu
    return client.put(f"/api/grilles/{t['grille_id']}/ordre", headers=qui, json=corps)


def _trois(client, t):
    for zone, libelle in (("case", "ironie"), ("bulle", "humour"), ("cartouche", "colère")):
        poser(client, t, region_id=t["zones"][zone], nouvelle_entree={"libelle": libelle})


def test_un_annotateur_range_les_etiquettes_et_une_neuve_nait_en_bas(client, decor, db_path):
    t = _travail(client, decor, db_path)
    _trois(client, t)
    # Une entrée DÉFINIE se range aussi (« toutes les entrées de la grille de travail »).
    assert client.post(f"/api/grilles/{t['grille_id']}/entrees", headers=ADMIN,
                       json={"libelle": "écrite"}).status_code == 201
    assert _ordre(client, t) == ["ironie", "humour", "colere", "ecrite"]
    r = _ranger(client, t, "ecrite", 0, vu=["ironie", "humour", "colere", "ecrite"])
    assert r.status_code == 200, r.text
    assert _ordre(client, t) == ["ecrite", "ironie", "humour", "colere"]
    poser(client, t, region_id=t["zones"]["texte"], nouvelle_entree={"libelle": "lieu : ici"})
    assert _ordre(client, t)[-1] == "lieu"
    # Au journal, sous son nom ; la valeur vue périmée reçoit le 409 de CONC-3.
    assert _q(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table = 'grille' "
                       "AND agent = 'stag' AND apres LIKE '%ordre:entree:%'")[0]["n"] == 1
    r = _ranger(client, t, "humour", 0, vu=["ironie", "humour", "colere", "ecrite", "lieu"])
    assert r.status_code == 409 and "conflit" in r.json()["detail"], r.text


def test_ranger_ailleurs_reste_aux_responsables(client, decor, db_path):
    from grilles_decor import SAM
    t = _travail(client, decor, db_path)
    _trois(client, t)
    assert _ranger(client, t, "humour", 0, qui=SAM).status_code == 403
    # Une autre grille ouverte : le formulaire, à ses responsables.
    entete = ["cle", "forme", "libelle"]
    from grilles_decor import csv_de, grille_active
    g = grille_active(client, decor["p"], entrees=csv_de([entete, ["a", "simple", "a"],
                                                          ["b", "simple", "b"]]),
                      listes=None, nom="Libre", ouverte=True, porte_sur="case")
    r = _ranger(client, {**t, **g}, "b", 0)
    assert r.status_code == 403 and "mode libre" in r.text, r.text
    # Une rubrique, une variante : au formulaire.
    r = client.put(f"/api/grilles/{t['grille_id']}/ordre", headers=STAG,
                   json={"quoi": "variante", "entree_cle": "x", "cle": "y", "place": 0})
    assert r.status_code == 403, r.text


def test_ctrl_z_defait_un_deplacement(client, decor, db_path):
    t = _travail(client, decor, db_path)
    _trois(client, t)
    assert _ranger(client, t, "colere", 0).status_code == 200
    assert client.get("/api/undo/prochain", headers=STAG).json()["description"] == (
        "déplacement d'une étiquette")
    # Une étiquette née depuis, en bas, ne bloque rien.
    poser(client, t, region_id=t["zones"]["texte"], nouvelle_entree={"libelle": "lieu : ici"})
    r = client.post("/api/undo", headers=STAG)               # la pose de « lieu »
    assert r.status_code == 200, r.text
    r = client.post("/api/undo", headers=STAG)               # le déplacement
    assert r.status_code == 200, r.text
    assert r.json()["description"] == "déplacement d'une étiquette"
    assert r.json()["planche_id"] is None and r.json()["region_id"] is None
    assert _ordre(client, t)[:3] == ["ironie", "humour", "colere"]


def test_ctrl_z_d_un_deplacement_recouvert_par_un_autre_est_refuse(client, decor, db_path):
    t = _travail(client, decor, db_path)
    _trois(client, t)
    assert _ranger(client, t, "colere", 0).status_code == 200
    assert _ranger(client, t, "ironie", 0, qui=ADMIN).status_code == 200
    r = client.post("/api/undo", headers=STAG)
    assert r.status_code == 409 and "conflit" in r.json()["detail"], r.text
    assert _ordre(client, t) == ["ironie", "colere", "humour"]


def test_ctrl_z_d_un_deplacement_demande_de_pouvoir_encore_ranger(client, decor, db_path):
    """Qui n'écrit plus dans le projet — il écrit encore ailleurs, dans un autre projet : l'acte
    est PASSÉ (AUTH-14), sans rien défaire."""
    from conftest import du_projet
    from grilles_decor import LEA, ZOE
    t = _travail(client, decor, db_path)
    _trois(client, t)
    assert _ranger(client, t, "colere", 0).status_code == 200
    du_projet(client, decor["d"], "utilisateur", "stag")
    assert client.put(f"/api/collections/{decor['d']}/acces", headers=ZOE,
                      json={"genre": "utilisateur", "principal": "stag",
                            "niveau": "ecriture"}).status_code == 200
    assert client.delete(f"/api/collections/{decor['c']}/acces/utilisateur/stag",
                         headers=LEA).status_code in (200, 204)
    assert client.delete(f"/api/collections/{decor['c2']}/acces/utilisateur/stag",
                         headers=LEA).status_code in (200, 204)
    r = client.post("/api/undo", headers=STAG)
    assert r.status_code == 409 and "ecarte" in r.json()["detail"], r.text
    assert _ordre(client, t) == ["colere", "ironie", "humour"]


def test_le_formulaire_d_une_autre_grille_ne_s_annule_pas(client, decor, db_path):
    from grilles_decor import csv_de, grille_active
    entete = ["cle", "forme", "libelle"]
    g = grille_active(client, decor["p"], entrees=csv_de([entete, ["a", "simple", "a"],
                                                          ["b", "simple", "b"]]),
                      listes=None, nom="Libre", ouverte=True, porte_sur="case")
    r = client.put(f"/api/grilles/{g['grille_id']}/ordre", headers=ADMIN,
                   json={"quoi": "entree", "cle": "b", "place": 0})
    assert r.status_code == 200, r.text
    assert client.get("/api/undo/prochain", headers=ADMIN).json() is None


# --------------------------------------------------------------------------- #
# « ⟳ Actualiser » : l'empreinte du plan d'une grille ouverte
# --------------------------------------------------------------------------- #
def _plans(client, decor, qui=STAG):
    r = client.get(f"/api/planches/{decor['planche']}/empreinte", headers=qui)
    assert r.status_code == 200, r.text
    return r.json()["plans"]


def test_l_empreinte_couvre_le_plan_des_grilles_ouvertes(client, decor, db_path):
    t = _travail(client, decor, db_path)
    g = str(t["grille_id"])
    e0 = _plans(client, decor)
    assert set(e0) == {g}                      # la grille fermée du décor n'y est pas
    # Une étiquette née en posant, ailleurs : le plan change.
    poser(client, t, region_id=t["zones"]["case"], nouvelle_entree={"libelle": "ironie"})
    e1 = _plans(client, decor)
    assert e1[g] != e0[g]
    # Une pose qui ne fait rien naître : le plan ne bouge pas (les relevés ont leur empreinte).
    poser(client, t, region_id=t["zones"]["bulle"], entree_cle="ironie")
    assert _plans(client, decor)[g] == e1[g]
    # Renommée, puis rangée : il change à chaque fois.
    assert client.patch(f"/api/grilles/{g}/entrees/ironie", headers=STAG,
                        json={"libelle": "ironie fine"}).status_code == 200
    e2 = _plans(client, decor)
    assert e2[g] != e1[g]
    poser(client, t, region_id=t["zones"]["cartouche"], nouvelle_entree={"libelle": "humour"})
    e3 = _plans(client, decor)
    assert client.put(f"/api/grilles/{g}/ordre", headers=STAG,
                      json={"quoi": "entree", "cle": "humour", "place": 0}).status_code == 200
    assert _plans(client, decor)[g] != e3[g]
