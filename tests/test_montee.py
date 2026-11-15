"""La MONTÉE DE VERSION d'une grille fermée (ANN-7 ; cadrage
`docs/ann7-montee-de-version-cadrage.md`, §2 à §7 ; tranché par Hugo le 2026-11-15).

La grille est le modèle FICTIF (`tools/grille-modele.csv`), publié en v1 et actif dans le
projet P. Une v2 s'écrit au plus court — le contenu de la v1 retouché, écrit publié en base —,
sauf là où c'est le chemin de l'écran qu'on éprouve (le réimport, la publication). Chaque
geste se joue sous qui le fait : la responsable de P (Léa) monte, la stagiaire pose.
"""
import copy
import json
import os
import sqlite3
import subprocess
import sys

import pytest

import grille_import
import grilles
from conftest import ADMIN
from grilles_decor import LEA, MODELE, OLGA, RACINE, SAM, STAG, ZOE, importer, ok
from test_releves import bulle, decor, poser  # noqa: F401

pytestmark = pytest.mark.usefixtures("sans_grille_de_travail")


def _q(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, p)]
    finally:
        c.close()


def _x(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    try:
        c.execute(sql, p)
        c.commit()
    finally:
        c.close()


def publier_v2(db_path, d, retouche) -> int:
    """La v2 de la grille : le contenu de la v1, retouché par `retouche(c)`, écrit PUBLIÉ.
    Rend l'identifiant de la version."""
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        v1 = grilles.version(c, d["grille_id"], 1)
        contenu = copy.deepcopy(grilles.contenu(c, v1["id"]))
        retouche(contenu)
        vid = grille_import.ecrire_version(c, d["grille_id"], contenu, numero=2,
                                           etat=grilles.ETAT_PUBLIEE, note=None, par="lea")
        c.commit()
        return vid
    finally:
        c.close()


def url(d, quoi="activation"):
    return f"/api/projets/{d['p']}/grilles/{d['grille_id']}/{quoi}"


def apercu(client, d, version=2, qui=LEA, attendu=200):
    r = client.get(url(d, "montee"), params={"version": version}, headers=qui)
    assert r.status_code == attendu, r.text[:800]
    return r.json()


def monter(client, d, *, vu=None, reponses=None, version=2, qui=LEA, attendu=200):
    corps = {"version": version}
    if vu is not None:
        corps["vu"] = vu
    if reponses is not None:
        corps["reponses"] = reponses
    r = client.put(url(d), headers=qui, json=corps)
    assert r.status_code == attendu, r.text[:800]
    return r.json()


def vue(client, d, rid, qui=STAG):
    rs = ok(client.get(f"/api/planches/{d['planche']}/releves", headers=qui))["releves"]
    return next(r for r in rs if r["id"] == rid)


def _e(c, cle):
    return c["entrees"][cle]


# --------------------------------------------------------------------------- #
# Sans relevé : l'activation d'aujourd'hui
# --------------------------------------------------------------------------- #
def test_sans_releve_activer_une_autre_version_reste_une_activation(client, decor, db_path):
    publier_v2(db_path, decor, lambda c: None)
    a = apercu(client, decor)
    assert a["montee"] is False and a["verdict"]["etat"] == "activable"
    monter(client, decor)                           # ni `vu`, ni bilan
    assert apercu(client, decor)["verdict"]["etat"] == "deja_active"


# --------------------------------------------------------------------------- #
# Le bilan, puis la montée
# --------------------------------------------------------------------------- #
def test_le_bilan_dit_ce_qui_passe_et_la_montee_reporte_les_releves(client, decor, db_path):
    b = bulle(decor)
    cri = poser(client, decor, region_id=b, entree_cle="cri", mots=[0])
    bang = poser(client, decor, region_id=b, entree_cle="onomatopee", variante_cle="bang",
                 mots=[8])
    crac = poser(client, decor, region_id=decor["zones"]["texte"], entree_cle="onomatopee",
                 variante_cle="crac", mots=[2])

    def v2(c):
        _e(c, "cri")["libelle"] = "cri poussé"                 # renommée : passe
        _e(c, "onomatopee")["variantes"].pop("bang")            # une valeur disparue
        _e(c, "origine-du-son")["precision"] = None
    publier_v2(db_path, decor, v2)

    a = apercu(client, decor)
    assert a["montee"] is True and (a["de"], a["vers"]) == (1, 2)
    assert a["verdict"]["etat"] == "montable"
    assert a["releves"] == {"total": 3, "normal": 2, "a_revoir": 1, "a_completer": 0}
    assert a["verdict"]["phrase"].startswith("3 relevés passent en version 2. 1 sera à revoir.")
    (cause,) = a["causes"]
    assert cause["cause"] == "variante_absente" and cause["n"] == 1
    assert cause["zones"] == [{"album_id": decor["album"], "planche_id": decor["planche"],
                               "region_id": b}]
    assert {x["cle"] for x in a["plan"]["renommes"]} == {"cri"}
    assert a["a_repondre"] == [] and a["refus"] == []
    assert "lea" not in json.dumps(a) and "stag" not in json.dumps(a)   # aucun login

    # Sans `vu`, la montée attend qu'on ait lu le bilan : 409, et le bilan à relire.
    refus = monter(client, decor, attendu=409)["detail"]
    assert "relisez" in refus["message"] and refus["vu"] == a["vu"]
    monter(client, decor, vu=a["vu"])

    v2_id = _q(db_path, "SELECT id FROM grille_version WHERE numero = 2")[0]["id"]
    for r in (cri, bang, crac):
        apres = vue(client, decor, r["id"])
        assert apres["version_id"] == v2_id and apres["version"] == 2
        # Ses valeurs ne bougent pas : variante, passage, auteur.
        assert (apres["variante_cle"], apres["mots"], apres["auteur"]) == (
            r["variante_cle"], r["mots"], r["auteur"])
        assert apres["modifiable"] is True
    assert vue(client, decor, bang["id"])["causes"] == ["variante_absente"]
    assert vue(client, decor, crac["id"])["etat"] == "normal"
    (acte,) = _q(db_path, "SELECT * FROM evenement WHERE cible_table = 'grille' "
                          "AND type = 'lien' AND json_extract(apres, '$.montee') IS NOT NULL")
    m = json.loads(acte["apres"])["montee"]
    assert (m["de"], m["vers"], m["releves"]["total"]) == (1, 2, 3) and acte["agent"] == "lea"
    # Aucun acte par relevé qui change seulement de version.
    assert _q(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table IN "
                       "('releve', 'releve_planche') AND type NOT IN ('creation')")[0]["n"] == 0
    # Une retouche d'un relevé passé réussit : ses valeurs n'ont pas bougé.
    ok(client.put(f"/api/releves/{crac['id']}", headers=STAG,
                  json={"variante_cle": "splash", "vu": {"variante_cle": "crac"}}))


def test_un_releve_pose_entre_temps_change_le_bilan(client, decor, db_path):
    poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[0])
    publier_v2(db_path, decor, lambda c: None)
    a = apercu(client, decor)
    poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[1])
    refus = monter(client, decor, vu=a["vu"], attendu=409)["detail"]
    assert "relisez" in refus["message"] and refus["releves"]["total"] == 2
    monter(client, decor, vu=refus["vu"])
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve r JOIN grille_version v "
                       "ON v.id = r.version_id WHERE v.numero = 2")[0]["n"] == 2


def test_la_montee_est_a_qui_gere_le_projet(client, decor, db_path):
    poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[0])
    publier_v2(db_path, decor, lambda c: None)
    apercu(client, decor, qui=STAG, attendu=403)    # écrit dans l'album, ne gère pas
    apercu(client, decor, qui=SAM, attendu=403)     # membre du projet
    apercu(client, decor, qui=ZOE, attendu=404)     # un autre projet
    a = apercu(client, decor, qui=ADMIN)            # l'administrateur passe outre
    monter(client, decor, qui=STAG, vu=a["vu"], attendu=403)
    monter(client, decor, qui=ADMIN, vu=a["vu"])


# --------------------------------------------------------------------------- #
# Une entrée retirée : laisser, ou fusionner dans… (M2)
# --------------------------------------------------------------------------- #
def test_une_entree_retiree_attend_sa_reponse_et_se_laisse(client, decor, db_path):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[0])
    publier_v2(db_path, decor, lambda c: _e(c, "cri").update(retiree=True))
    a = apercu(client, decor)
    assert a["verdict"]["etat"] == "a_repondre"
    assert "1 entrée retirée attend votre réponse." in a["verdict"]["phrase"]
    (x,) = a["a_repondre"]
    assert (x["cle"], x["releves"], x["choix"]) == ("cri", 1, ["laisser", "fusionner"])
    assert x["fusionner_dans"] == []         # aucune autre entrée simple posée sur des mots
    detail = monter(client, decor, vu=a["vu"], attendu=409)["detail"]
    assert "laisser" in detail["message"]
    monter(client, decor, vu=a["vu"], reponses={"cri": "mauvais"}, attendu=422)
    monter(client, decor, vu=a["vu"], reponses={"cri": "fusionner:echo"}, attendu=409)
    monter(client, decor, vu=a["vu"], reponses={"cri": "laisser"})
    apres = vue(client, decor, r["id"])
    assert (apres["etat"], apres["causes"], apres["entree_cle"]) == (
        "a_revoir", ["entree_absente"], "cri")


def test_une_entree_retiree_se_fusionne_et_le_journal_le_dit(client, decor, db_path):
    b = bulle(decor)
    r = poser(client, decor, region_id=b, entree_cle="echo", mots=[0],
              qualificatifs=["objet"])
    publier_v2(db_path, decor, lambda c: _e(c, "echo").update(retiree=True))
    a = apercu(client, decor)
    (x,) = a["a_repondre"]
    assert x["fusionner_dans"] == ["origine-du-son"]
    traces_avant = _q(db_path, "SELECT COUNT(*) AS n FROM evenement")[0]["n"]
    monter(client, decor, vu=a["vu"], reponses={"echo": "fusionner:origine-du-son"})
    apres = vue(client, decor, r["id"])
    assert apres["entree_cle"] == "origine-du-son" and apres["qualificatifs"] == ["objet"]
    assert apres["causes"] == ["precision_manquante"]          # l'arrivée attend un lieu
    (f,) = _q(db_path, "SELECT * FROM evenement WHERE type = ?", (grilles.ACTE_FUSION,))
    charge = json.loads(f["apres"])
    assert (f["cible_table"], f["cible_id"], charge["entree_cle"], charge["version_id"]) == (
        "releve", b, "origine-du-son", apres["version_id"])
    assert json.loads(f["avant"])["entree_cle"] == "echo"
    (acte,) = _q(db_path, "SELECT * FROM evenement WHERE cible_table = 'grille' AND id > 0 "
                          "AND json_extract(apres, '$.montee') IS NOT NULL")
    assert charge["fusion"]["acte"] == acte["id"]
    assert json.loads(acte["apres"])["montee"]["fusions"] == [
        {"de": "echo", "dans": "origine-du-son", "releve_ids": [r["id"]]}]
    assert traces_avant < _q(db_path, "SELECT COUNT(*) AS n FROM evenement")[0]["n"]


# --------------------------------------------------------------------------- #
# M1 : deux relevés d'une entrée qui ne se pose plus qu'une fois
# --------------------------------------------------------------------------- #
def test_une_cible_qui_se_contredirait_refuse_la_montee(client, decor, db_path):
    b = bulle(decor)
    r1 = poser(client, decor, region_id=b, entree_cle="cri", mots=[0])
    poser(client, decor, region_id=b, entree_cle="cri", mots=[1])
    poser(client, decor, region_id=decor["zones"]["texte"], entree_cle="cri", mots=[0])
    publier_v2(db_path, decor, lambda c: _e(c, "cri").update(cardinalite="une"))
    a = apercu(client, decor)
    assert a["verdict"]["etat"] == "refuse"
    (x,) = a["refus"]
    assert (x["code"], x["cle"], x["zone"]["region_id"]) == ("cardinalite_contredite", "cri", b)
    assert "1 cible porte deux relevés" in a["verdict"]["phrase"]
    monter(client, decor, vu=a["vu"], attendu=409)
    ok(client.delete(f"/api/releves/{r1['id']}", headers=STAG), 204)
    a = apercu(client, decor)
    assert a["verdict"]["etat"] == "montable"
    monter(client, decor, vu=a["vu"])
    assert {r["une"] for r in _q(db_path, "SELECT une FROM releve")} == {1}


# --------------------------------------------------------------------------- #
# M5 : seulement vers une version plus récente
# --------------------------------------------------------------------------- #
def test_on_ne_redescend_pas(client, decor, db_path):
    poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[0])
    publier_v2(db_path, decor, lambda c: None)
    monter(client, decor, vu=apercu(client, decor)["vu"])
    a = apercu(client, decor, version=1)
    assert a["verdict"]["etat"] == "refuse"
    assert [x["code"] for x in a["refus"]] == ["plus_ancienne"]
    detail = monter(client, decor, version=1, vu=a["vu"], attendu=409)["detail"]
    assert "plus récente" in detail["message"]


def test_une_version_brouillon_ne_se_monte_pas(client, decor, db_path):
    poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[0])
    importer(client, decor["p"], LEA, grille_id=decor["grille_id"],
             entrees=MODELE.replace("un cri poussé", "un cri lancé"))
    a = apercu(client, decor)
    assert [x["code"] for x in a["refus"]] == ["pas_publiee"]
    monter(client, decor, vu=a["vu"], attendu=409)


# --------------------------------------------------------------------------- #
# Le chemin de l'écran : réimporter, publier, monter
# --------------------------------------------------------------------------- #
def test_reimporter_publier_puis_monter(client, decor, db_path):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[0])
    importer(client, decor["p"], LEA, grille_id=decor["grille_id"],
             entrees=MODELE.replace(";cri;", ";cri crié;", 1))
    ok(client.post(f"/api/grilles/{decor['grille_id']}/versions/2/publication", headers=LEA))
    a = apercu(client, decor)
    assert a["verdict"]["etat"] == "montable" and a["releves"]["normal"] == 1
    monter(client, decor, vu=a["vu"])
    assert vue(client, decor, r["id"])["version"] == 2
    # La porte de derrière : désactiver puis réactiver l'ancienne version se refuse (M5).
    ok(client.delete(url(decor), headers=LEA), 204)
    monter(client, decor, version=1, attendu=409)
    monter(client, decor, version=2)                 # rien ne change de version : réactivée


def test_une_version_publiee_qui_perd_ce_qu_emploient_des_releves_le_dit_a_la_montee(
        client, decor, db_path):
    """L'hypothèse du cadrage (« Vu en passant », et §3 : « l'entrée a disparu de la vM ») :
    le brouillon de la v2 naît pendant que la v1 ne porte rien sur « cri », « bang » ni la
    case « hors champ » — leur suppression y est permise —, puis des relevés se posent en v1
    sur eux, puis le brouillon se publie. La publication ne le revérifie pas (elle publie) ;
    la MONTÉE le dit : ce qui disparaît, avec ses relevés, chaque cause, et l'entrée à
    décider comme une entrée retirée. Laissés, les relevés passent en v2, à revoir, et se
    retirent comme les autres."""
    gid = decor["grille_id"]
    for chemin in ("entrees/cri", "entrees/onomatopee/variantes/bang",
                   "listes/sources/cases/hors-champ"):
        ok(client.delete(f"/api/grilles/{gid}/{chemin}", headers=LEA))
    b = bulle(decor)
    cri = poser(client, decor, region_id=b, entree_cle="cri", mots=[0])
    bang = poser(client, decor, region_id=b, entree_cle="onomatopee", variante_cle="bang",
                 mots=[8])
    echo = poser(client, decor, region_id=b, entree_cle="echo", qualificatifs=["hors-champ"],
                 mots=[2])
    # Une autre valeur de l'entrée, qui reste : elle passe, et ne compte pas sous « bang ».
    crac = poser(client, decor, region_id=decor["zones"]["texte"], entree_cle="onomatopee",
                 variante_cle="crac", mots=[2])
    ok(client.post(f"/api/grilles/{gid}/versions/2/publication", headers=LEA))

    a = apercu(client, decor)
    assert a["verdict"]["etat"] == "a_repondre"
    assert a["releves"] == {"total": 4, "normal": 1, "a_revoir": 3, "a_completer": 0}
    assert sorted((x["quoi"], x["cle"], x["releves"]) for x in a["plan"]["disparus"]) == [
        ("entree", "cri", 1), ("qualificatif", "sources/hors-champ", 1),
        ("variante", "onomatopee/bang", 1)]
    assert sorted((c["cause"], c["n"]) for c in a["causes"]) == [
        ("case_absente", 1), ("entree_absente", 1), ("variante_absente", 1)]
    assert [(x["cle"], x["releves"], x["choix"], x["absente"]) for x in a["a_repondre"]] == [
        ("cri", 1, ["laisser", "fusionner"], True)]
    # Perdue sans être retirée : la phrase ne la dit pas « retirée » (vu le 2026-11-15).
    assert "1 entrée absente de la version 2 attend votre réponse." in a["verdict"]["phrase"]
    assert "retirée" not in a["verdict"]["phrase"]
    refus = monter(client, decor, vu=a["vu"], attendu=409)["detail"]["message"]
    assert refus.startswith("1 entrée(s) retirée(s) ou absente(s) de la version 2"), refus
    monter(client, decor, vu=a["vu"], reponses={"cri": "laisser"})
    for r, cause in ((cri, "entree_absente"), (bang, "variante_absente"),
                     (echo, "case_absente")):
        apres = vue(client, decor, r["id"])
        assert (apres["version"], apres["etat"], apres["causes"]) == (2, "a_revoir", [cause])
    assert (lambda v: (v["version"], v["etat"]))(vue(client, decor, crac["id"])) == (2, "normal")
    for r in (cri, bang, echo):
        assert client.delete(f"/api/releves/{r['id']}", headers=STAG).status_code == 204


# --------------------------------------------------------------------------- #
# Le périmètre : le projet, jamais la grille entière (le jour du catalogue)
# --------------------------------------------------------------------------- #
def test_la_montee_ne_touche_que_les_releves_du_projet(client, decor, db_path):
    poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[0])
    v1 = _q(db_path, "SELECT id FROM grille_version WHERE numero = 1")[0]["id"]
    # Le catalogue n'existe pas : un relevé de la même grille sur l'album d'un AUTRE projet,
    # posé par SQL, est ce que deux projets tiendront le jour où il existera.
    _x(db_path, "INSERT INTO releve (region_id, grille_id, version_id, entree_cle) "
                "VALUES (?, ?, ?, 'regard-camera')",
       (decor["bulle_q"], decor["grille_id"], v1))
    _x(db_path, "INSERT INTO passe (region_id, grille_id, version_id, rubrique_cle) "
                "VALUES (?, ?, ?, '')", (decor["bulle_q"], decor["grille_id"], v1))
    publier_v2(db_path, decor, lambda c: c["entrees"].update(
        neuve=copy.deepcopy(_e(c, "cri"))))
    a = apercu(client, decor)
    assert a["releves"]["total"] == 1 and a["passes_rouvertes"]["n"] == 0
    monter(client, decor, vu=a["vu"])
    (autre,) = _q(db_path, "SELECT version_id FROM releve WHERE region_id = ?",
                  (decor["bulle_q"],))
    assert autre["version_id"] == v1
    (passe,) = _q(db_path, "SELECT version_id FROM passe WHERE region_id = ?",
                  (decor["bulle_q"],))
    assert passe["version_id"] == v1


# --------------------------------------------------------------------------- #
# Les passes « terminée » (M4 c)
# --------------------------------------------------------------------------- #
def _marquer(client, region_id, d, rubrique="", qui=STAG):
    ok(client.put(f"/api/regions/{region_id}/passes/{d['grille_id']}", headers=qui,
                  json={"rubrique_cle": rubrique}))


def test_seules_se_rouvrent_les_passes_ou_la_version_ajoute_a_regarder(client, decor, db_path):
    b, case = bulle(decor), decor["zones"]["case"]
    poser(client, decor, region_id=b, entree_cle="cri", mots=[0])
    _marquer(client, b, decor)                      # toute la grille, sur la bulle
    _marquer(client, b, decor, "sons")              # la rubrique où une entrée naît
    _marquer(client, b, decor, "provenance")        # une rubrique où rien ne naît
    _marquer(client, case, decor)                   # toute la grille, sur une case
    _marquer(client, b, decor, "image")             # une rubrique qui disparaît
    autrui_avant = ok(client.get(f"/api/albums/{decor['album']}/travail-des-autres",
                                 headers=OLGA))

    def v2(c):
        neuve = copy.deepcopy(_e(c, "cri"))
        neuve.update(libelle="soupir", rubrique_cle="voix")
        c["entrees"]["soupir"] = neuve               # sur des mots : pas sur une case
        c["entrees"].pop("regard-camera")
        c["rubriques"].pop("image")
    publier_v2(db_path, decor, v2)
    a = apercu(client, decor)
    assert a["passes_rouvertes"]["n"] == 3
    assert "3 passes « terminée » se rouvrent." in a["verdict"]["phrase"]
    monter(client, decor, vu=a["vu"], qui=ADMIN)
    restent = {(p["region_id"], p["rubrique_cle"]) for p in _q(
        db_path, "SELECT p.* FROM passe p JOIN grille_version v ON v.id = p.version_id "
                 "WHERE v.numero = 2")}
    assert restent == {(b, "provenance"), (case, "")}
    assert _q(db_path, "SELECT COUNT(*) AS n FROM passe")[0]["n"] == 2
    actes = _q(db_path, "SELECT * FROM evenement WHERE type = 'passe_rouverte' ORDER BY id")
    assert len(actes) == 3 and {x["agent"] for x in actes} == {"decor"}
    assert all(json.loads(x["apres"])["montee"]["vers"] == 2 for x in actes)
    # Ni « qui perd quoi » ni les traces d'un compte ne comptent ce qu'une montée rouvre.
    assert ok(client.get(f"/api/albums/{decor['album']}/travail-des-autres",
                         headers=OLGA)) == autrui_avant
    # La passe rouverte se re-marque ; un écran qui la voyait encore marquée reçoit le 409
    # de CONC-3, qui nomme qui l'a rouverte.
    r = client.put(f"/api/regions/{b}/passes/{decor['grille_id']}", headers=STAG,
                   json={"rubrique_cle": "", "vu": {"passe": True}})
    assert r.status_code == 409, r.text


def test_un_rouvrir_ordinaire_compte_encore(db_path, client, decor):
    """Le pendant du test précédent : `sql_acte_qui_range` n'écarte QUE la passe rouverte
    par une montée — un « Rouvrir » à la main est un travail."""
    b = bulle(decor)
    _marquer(client, b, decor)
    ok(client.delete(f"/api/regions/{b}/passes/{decor['grille_id']}", headers=STAG), 204)
    c = sqlite3.connect(db_path)
    try:
        n = c.execute(f"SELECT COUNT(*) FROM evenement e WHERE type = 'passe_rouverte' "
                      f"AND NOT {grilles.sql_acte_qui_range('e')}").fetchone()[0]
    finally:
        c.close()
    assert n == 1


# --------------------------------------------------------------------------- #
# Deux écrans pendant la montée (CONC-3) et le signal « ⟳ Actualiser »
# --------------------------------------------------------------------------- #
def test_une_pose_dans_l_ancienne_version_apres_la_montee_dit_d_actualiser(client, decor,
                                                                          db_path):
    poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[0])
    publier_v2(db_path, decor, lambda c: None)
    avant = ok(client.get(f"/api/planches/{decor['planche_q']}/empreinte", headers=ZOE))
    plans_avant = ok(client.get(f"/api/planches/{decor['planche']}/empreinte",
                                headers=STAG))["plans"]
    assert str(decor["grille_id"]) in plans_avant          # une grille fermée y est aussi
    monter(client, decor, vu=apercu(client, decor)["vu"])
    plans_apres = ok(client.get(f"/api/planches/{decor['planche']}/empreinte",
                                headers=STAG))["plans"]
    assert plans_apres[str(decor["grille_id"])] != plans_avant[str(decor["grille_id"])]
    # Une planche d'un autre projet ne voit rien bouger.
    assert ok(client.get(f"/api/planches/{decor['planche_q']}/empreinte",
                         headers=ZOE))["plans"] == avant["plans"]
    r = poser(client, decor, attendu=(409,), region_id=bulle(decor), entree_cle="cri",
              mots=[2])
    assert "Actualiser" in r["detail"]


# --------------------------------------------------------------------------- #
# L'outil
# --------------------------------------------------------------------------- #
def _outil(db_path, *args):
    env = {**os.environ, "BD_DB_PATH": str(db_path), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, str(RACINE / "tools" / "importer_grille.py"),
                           *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", env=env)


def test_l_outil_rend_le_bilan_a_blanc_puis_monte_avec_ses_reponses(client, decor, db_path):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[0])
    publier_v2(db_path, decor, lambda c: _e(c, "cri").update(retiree=True))
    p = _outil(db_path, "--grille", decor["grille_id"], "--activer", "--a-blanc")
    assert p.returncode == 0, p.stderr
    assert "1 entrée retirée attend votre réponse" in p.stderr and "--laisser cri" in p.stderr
    assert vue(client, decor, r["id"])["version"] == 1          # rien n'est écrit
    p = _outil(db_path, "--grille", decor["grille_id"], "--activer")
    assert p.returncode == 1 and "laisser" in p.stderr
    p = _outil(db_path, "--grille", decor["grille_id"], "--activer", "--laisser", "cri")
    assert p.returncode == 0, p.stderr
    assert vue(client, decor, r["id"])["version"] == 2


def test_un_doublon_ne_refuse_la_montee_que_s_il_est_fabrique_par_une_fusion():
    """La même variante deux fois sur une zone entière, d'une entrée « plusieurs » : un doublon
    d'avant J3 que rien ne fusionne n'est pas l'affaire de la montée ; une fusion qui le
    fabriquerait, si. Deux relevés d'une entrée « une seule fois » refusent toujours (M1)."""
    import montee
    arrivee = {"cible": "bulle", "rubriques": {}, "listes": {}, "entrees": {
        "x": {"forme": "variantes", "cible": None, "cardinalite": "plusieurs",
              "variantes": {"a": {}}},
        "u": {"forme": "simple", "cible": None, "cardinalite": None, "variantes": {}}}}
    rs = [{"id": i, "region_id": 9, "planche_id": 1, "mots": False, "variante_cle": "a"}
          for i in (1, 2)]
    assert montee._en_double(rs, {1: "x", 2: "x"}, arrivee) == {}
    assert montee._en_double(rs, {1: "x", 2: "x"}, arrivee, {1}) == {
        (("r", 9), "x"): ("fusion_en_double", [1, 2])}
    assert montee._en_double(rs, {1: "u", 2: "u"}, arrivee) == {
        (("r", 9), "u"): ("cardinalite_contredite", [1, 2])}
