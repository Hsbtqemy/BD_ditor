"""Les relevés — poser, modifier, retirer, lire ; les gardes de la pose, la cardinalité, le 409
de CONC-3 sur les valeurs uniques, l'état dérivé (ANN-7, tranche 1 ; cadrage R5, R9, G1, G2,
G3, G4, G8, G14).

La grille est le modèle FICTIF (`tools/grille-modele.csv`), porté sur des mots. Le texte de la
bulle du décor, « J'SAIS PAS, IL NE VIENT PAS !!! », se découpe en : J' (0) · SAIS (1) ·
PAS (2) · , (3) · IL (4) · NE (5) · VIENT (6) · PAS (7) · !!! (8).
"""
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

import grilles
import main
from conftest import ADMIN
from grilles_decor import (ANA, LEA, MODELE, SAM, STAG, TP, ZOE, csv_de, grille_active,
                           importer, monter, ok)


@pytest.fixture
def decor(client, db_path, derriere_proxy):
    d = monter(client, db_path)
    d.update(grille_active(client, d["p"]))
    return d


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


def poser(client, d, qui=STAG, attendu=(201,), **champs):
    corps = {"grille_id": d["grille_id"], "version": d["numero"], **champs}
    r = client.post("/api/releves", headers=qui, json=corps)
    assert r.status_code in attendu, (r.status_code, r.text[:600])
    return r.json()


def bulle(d):
    return d["zones"]["bulle"]


# --------------------------------------------------------------------------- #
# Poser
# --------------------------------------------------------------------------- #
def test_poser_un_releve_sur_des_mots(client, decor, db_path):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[8])
    assert r["etat"] == "normal" and r["causes"] == []
    assert r["mots"] == [{"position": 0, "rang": 8, "forme": "!!!"}]
    assert r["auteur"] == "stag" and r["auteur_nom"] == "Stagiaire Une"
    assert r["modifiable"] is True and r["une"] is False
    (e,) = _q(db_path, "SELECT * FROM evenement WHERE cible_table = 'releve'")
    assert e["type"] == "creation" and e["cible_id"] == bulle(decor) and e["agent"] == "stag"
    assert f'"releve_id": {r["id"]}' in e["apres"]


def test_un_passage_peut_sauter_des_mots_et_suit_l_ordre_du_texte(client, decor):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[7, 5])
    assert [m["forme"] for m in r["mots"]] == ["NE", "PAS"]


def test_poser_demande_d_ecrire_dans_l_album(client, decor):
    poser(client, decor, qui=ANA, attendu=(404,), region_id=bulle(decor), entree_cle="cri",
          mots=[0])
    poser(client, decor, qui=ZOE, attendu=(404,), region_id=bulle(decor), entree_cle="cri",
          mots=[0])
    poser(client, decor, qui=SAM, attendu=(404,), region_id=bulle(decor), entree_cle="cri",
          mots=[0])                                    # membre d'une base protégée


def test_la_grille_doit_etre_active_dans_le_projet_de_l_album(client, decor):
    ok(client.delete(f"/api/projets/{decor['p']}/grilles/{decor['grille_id']}/activation",
                     headers=LEA), 204)
    poser(client, decor, attendu=(409,), region_id=bulle(decor), entree_cle="cri", mots=[0])
    # Ni dans un album d'un AUTRE projet, où elle n'est pas active.
    ok(client.put(f"/api/projets/{decor['p']}/grilles/{decor['grille_id']}/activation",
                  headers=LEA, json={"version": 1}))
    poser(client, decor, qui=ZOE, attendu=(409,), region_id=decor["bulle_q"],
          entree_cle="cri", mots=[0])


def test_la_version_doit_etre_celle_de_l_activation(client, decor):
    r = client.post("/api/releves", headers=STAG, json={
        "grille_id": decor["grille_id"], "version": 2, "region_id": bulle(decor),
        "entree_cle": "cri", "mots": [0]})
    assert r.status_code == 409 and "version 1" in r.json()["detail"]


def test_l_entree_doit_exister(client, decor):
    poser(client, decor, attendu=(422,), region_id=bulle(decor), entree_cle="inconnue",
          mots=[0])


@pytest.mark.parametrize("cas", [
    ("cri sur une case", "case", "cri", {"mots": [0]}),
    ("des mots sans mots", "bulle", "cri", {}),
    ("un mot hors du texte", "bulle", "cri", {"mots": [42]}),
    ("toute la zone, avec des mots", "bulle", "ton-de-voix",
     {"mots": [0], "variante_cle": "crie"}),
    ("une zone d'un type qu'elle ne vise pas", "case", "ton-de-voix",
     {"variante_cle": "crie"}),
    ("la case sur une bulle", "bulle", "regard-camera", {}),
    ("la planche sur une région", "bulle", "ambiance", {}),
], ids=lambda c: c[0])
def test_la_cible_doit_convenir_a_l_entree(client, decor, cas):
    _nom, zone, entree, extra = cas
    poser(client, decor, attendu=(422,), region_id=decor["zones"][zone], entree_cle=entree,
          **extra)


def test_chaque_sorte_de_cible_se_pose(client, decor):
    poser(client, decor, region_id=decor["zones"]["cartouche"], entree_cle="ton-de-voix",
          variante_cle="chuchote")
    poser(client, decor, region_id=decor["zones"]["case"], entree_cle="regard-camera")
    r = poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    assert r["planche_id"] == decor["planche"] and r["region_id"] is None
    poser(client, decor, attendu=(422,), planche_id=decor["planche"], entree_cle="cri")


def test_l_entite_attend_l_etage_de_projet_des_personnages(client, decor):
    """G3 : une entrée qui vise l'entité s'importe, aucun relevé ne s'y pose encore."""
    entete = ["cle", "forme", "libelle", "cible"]
    g = grille_active(client, decor["p"], entrees=csv_de([entete, ["profil", "simple",
                                                                   "profil", "entite"]]),
                      listes=None, nom="Profils")
    r = client.post("/api/releves", headers=STAG, json={
        "grille_id": g["grille_id"], "version": 1, "region_id": decor["zones"]["personnage"],
        "entree_cle": "profil"})
    assert r.status_code == 422 and "G3" in r.json()["detail"]


@pytest.mark.parametrize("cas", [
    ("une variante manquante", "onomatopee", {"mots": [8]}),
    ("une variante d'une autre entrée", "onomatopee", {"mots": [8], "variante_cle": "crie"}),
    ("une variante sur une simple", "cri", {"mots": [8], "variante_cle": "bang"}),
    ("un qualificatif d'une autre liste", "origine-du-son", {"mots": [8],
                                                            "qualificatifs": ["taille"]}),
    ("des qualificatifs sur une simple", "cri", {"mots": [8], "qualificatifs": ["objet"]}),
    ("une précision que l'entrée n'attend pas", "cri", {"mots": [8], "precision": "x"}),
], ids=lambda c: c[0])
def test_la_forme_doit_etre_respectee(client, decor, cas):
    _nom, entree, extra = cas
    poser(client, decor, attendu=(422,), region_id=bulle(decor), entree_cle=entree, **extra)


def test_la_variante_manquante_est_dite_en_mots(client, decor):
    r = client.post("/api/releves", headers=STAG, json={
        "grille_id": decor["grille_id"], "version": 1, "region_id": bulle(decor),
        "entree_cle": "onomatopee", "mots": [8]})
    assert r.status_code == 422 and "choisissez-en une" in r.json()["detail"]


def test_chaque_forme_se_pose(client, decor):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="onomatopee", mots=[8],
              variante_cle="bang")
    assert r["variante_cle"] == "bang"
    r = poser(client, decor, region_id=bulle(decor), entree_cle="origine-du-son", mots=[1],
              qualificatifs=["objet", "hors-champ"], precision="la cuisine")
    assert r["qualificatifs"] == ["hors-champ", "objet"] and r["precision"] == "la cuisine"
    r = poser(client, decor, region_id=bulle(decor), entree_cle="echo", mots=[2])
    assert r["qualificatifs"] == []                     # zéro qualificatif : permis


def test_le_lien_designe_une_region_du_meme_album(client, decor):
    """G4 : un lien vers une région d'un autre album est INTROUVABLE (404), comme une région
    qui n'existe pas — le lecteur du relevé ne lit peut-être pas l'autre album."""
    r = poser(client, decor, region_id=bulle(decor), entree_cle="reponse-a",
              lien_region_id=decor["autre_bulle"])
    assert r["lien"] == {"region_id": decor["autre_bulle"], "existe": True}
    poser(client, decor, attendu=(404,), region_id=bulle(decor), entree_cle="reponse-a",
          lien_region_id=decor["bulle_q"])
    poser(client, decor, attendu=(404,), region_id=bulle(decor), entree_cle="reponse-a",
          lien_region_id=999999)
    poser(client, decor, attendu=(422,), region_id=bulle(decor), entree_cle="reponse-a",
          lien_region_id=bulle(decor))
    poser(client, decor, attendu=(422,), region_id=bulle(decor), entree_cle="cri", mots=[0],
          lien_region_id=decor["autre_bulle"])


# --------------------------------------------------------------------------- #
# La cardinalité
# --------------------------------------------------------------------------- #
def test_un_second_releve_une_est_refuse_et_rend_l_existant(client, decor):
    premier = poser(client, decor, region_id=bulle(decor), entree_cle="ton-de-voix",
                    variante_cle="crie")
    r = client.post("/api/releves", headers=LEA, json={
        "grille_id": decor["grille_id"], "version": 1, "region_id": bulle(decor),
        "entree_cle": "ton-de-voix", "variante_cle": "chuchote"})
    assert r.status_code == 409
    existant = r.json()["detail"]["releve_existant"]
    assert existant["id"] == premier["id"] and existant["variante_cle"] == "crie"
    assert existant["auteur"] == "stag"
    # Sur une autre cible, oui ; et « plusieurs » sur des mots, deux fois la même entrée.
    poser(client, decor, region_id=decor["zones"]["texte"], entree_cle="ton-de-voix",
          variante_cle="crie")
    poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[0])
    poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[0])


def test_la_cardinalite_tient_aussi_sur_la_planche(client, decor):
    poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    poser(client, decor, attendu=(409,), planche_id=decor["planche"], entree_cle="ambiance")


def test_deux_poses_simultanees_n_en_font_qu_une(client, decor, db_path):
    """La course (R5) : deux personnes posent la même entrée `une` sur la même bulle au même
    instant. Le verrou d'écriture fait attendre la seconde, qui relit et reçoit le 409 ; et
    l'index unique partiel, dessous, tient même sans la relecture."""
    corps = {"grille_id": decor["grille_id"], "version": 1, "region_id": bulle(decor),
             "entree_cle": "ton-de-voix", "variante_cle": "crie"}
    barriere = threading.Barrier(2)
    codes = []

    def poser_en_meme_temps(qui):
        c = TestClient(main.app, headers={main.EN_TETE_REQUETE: "1"})
        barriere.wait()
        codes.append(c.post("/api/releves", headers=qui, json=corps).status_code)
    fils = [threading.Thread(target=poser_en_meme_temps, args=(q,)) for q in (STAG, LEA)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    assert sorted(codes) == [201, 409]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 1


# --------------------------------------------------------------------------- #
# Modifier : CONC-3 sur les valeurs uniques (R9, G1)
# --------------------------------------------------------------------------- #
def _modifier(client, rid, qui, attendu=(200,), **corps):
    r = client.put(f"/api/releves/{rid}", headers=qui, json=corps)
    assert r.status_code in attendu, (r.status_code, r.text[:600])
    return r.json()


@pytest.mark.parametrize("champ,entree,pose,valeur_a,valeur_b", [
    ("variante_cle", "onomatopee", {"mots": [8], "variante_cle": "bang"}, "crac", "splash"),
    ("qualificatifs", "origine-du-son", {"mots": [1], "qualificatifs": ["objet"]},
     ["personnage"], ["hors-champ"]),
    ("precision", "origine-du-son", {"mots": [1]}, "le salon", "la rue"),
    ("mots", "cri", {"mots": [8]}, [6], [4]),
])
def test_une_valeur_perimee_recoit_le_409_de_conc3(client, decor, champ, entree, pose,
                                                   valeur_a, valeur_b):
    r = poser(client, decor, region_id=bulle(decor), entree_cle=entree, **pose)
    vu = r[champ] if champ != "mots" else [m["rang"] for m in r["mots"]]
    _modifier(client, r["id"], LEA, **{champ: valeur_a, "vu": {champ: vu}})
    refus = _modifier(client, r["id"], STAG, attendu=(409,),
                      **{champ: valeur_b, "vu": {champ: vu}})["detail"]
    assert refus["conflit"]["champ"] == champ
    assert refus["conflit"]["auteur"]["login"] == "lea"
    assert "Lea Responsable" in refus["message"]
    # La même écriture que la valeur actuelle passe ; sans `vu`, la dernière gagne.
    _modifier(client, r["id"], STAG, **{champ: valeur_a, "vu": {champ: vu}})
    _modifier(client, r["id"], STAG, **{champ: valeur_b})


def test_le_lien_est_une_valeur_gardee(client, decor):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="reponse-a")
    assert r["etat"] == "a_completer" and r["causes"] == ["lien_manquant"]
    r = _modifier(client, r["id"], LEA, lien_region_id=decor["autre_bulle"],
                  vu={"lien_region_id": None})
    assert r["etat"] == "normal"
    _modifier(client, r["id"], STAG, attendu=(409,), lien_region_id=None,
              vu={"lien_region_id": None})


def test_l_auteur_d_un_conflit_est_celui_de_ce_releve_pas_d_un_voisin(client, decor):
    """Deux relevés sur la même bulle partagent la cible du journal (la région) : le 409 de
    l'un nomme l'auteur de SON changement, jamais celui de l'autre."""
    a = poser(client, decor, region_id=bulle(decor), entree_cle="onomatopee", mots=[8],
              variante_cle="bang")
    b = poser(client, decor, region_id=bulle(decor), entree_cle="onomatopee", mots=[2],
              variante_cle="bang")
    _modifier(client, a["id"], ADMIN, variante_cle="crac")          # « decor » sur a
    _modifier(client, b["id"], LEA, variante_cle="crac")            # Léa sur b
    refus = _modifier(client, a["id"], STAG, attendu=(409,), variante_cle="splash",
                      vu={"variante_cle": "bang"})["detail"]
    assert refus["conflit"]["auteur"]["login"] == "decor"


def test_vu_ne_porte_que_les_valeurs_gardees(client, decor):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[8])
    _modifier(client, r["id"], STAG, attendu=(422,), mots=[1], vu={"auteur": "x"})


def test_modifier_garde_les_gardes_de_la_pose(client, decor):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="onomatopee", mots=[8],
              variante_cle="bang")
    _modifier(client, r["id"], STAG, attendu=(422,), variante_cle="crie")
    _modifier(client, r["id"], STAG, attendu=(422,), precision="x")
    _modifier(client, r["id"], ANA, attendu=(404,), variante_cle="crac")


# --------------------------------------------------------------------------- #
# Retirer ; une grille désactivée
# --------------------------------------------------------------------------- #
def test_retirer_un_releve(client, decor, db_path):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[8])
    ok(client.delete(f"/api/releves/{r['id']}", headers=ANA), 404)
    ok(client.delete(f"/api/releves/{r['id']}", headers=LEA), 204)
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0
    e = _q(db_path, "SELECT * FROM evenement WHERE cible_table = 'releve' "
                    "AND type = 'suppression'")
    assert len(e) == 1 and '"formes": ["!!!"]' in e[0]["avant"]


def _retirer(client, rid, qui, attendu=(204,), **corps):
    r = client.request("DELETE", f"/api/releves/{rid}", headers=qui,
                       **({"json": corps} if corps else {}))
    assert r.status_code in attendu, (r.status_code, r.text[:600])
    return r.json() if r.content else None


@pytest.mark.parametrize("champ,entree,pose,valeur", [
    ("variante_cle", "onomatopee", {"mots": [8], "variante_cle": "bang"}, "crac"),
    ("qualificatifs", "origine-du-son", {"mots": [1], "qualificatifs": ["objet"]},
     ["personnage"]),
    ("mots", "cri", {"mots": [8]}, [6]),
])
def test_retirer_une_valeur_perimee_recoit_le_409_de_conc3(client, decor, db_path, champ,
                                                           entree, pose, valeur):
    """Tranche 2 : la page retire ce qu'elle MONTRE — si un autre a changé le relevé depuis,
    le retrait est refusé et nomme qui ; le relevé reste."""
    r = poser(client, decor, region_id=bulle(decor), entree_cle=entree, **pose)
    vu = r[champ] if champ != "mots" else [m["rang"] for m in r["mots"]]
    _modifier(client, r["id"], LEA, **{champ: valeur})
    refus = _retirer(client, r["id"], STAG, attendu=(409,), vu={champ: vu})["detail"]
    assert refus["conflit"]["champ"] == champ
    assert refus["conflit"]["auteur"]["login"] == "lea"
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 1
    # Ce que l'écran voit maintenant se retire.
    _retirer(client, r["id"], STAG, vu={champ: valeur})
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0


def test_retirer_sans_vu_le_dernier_gagne(client, decor, db_path):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="onomatopee", mots=[8],
              variante_cle="bang")
    _modifier(client, r["id"], LEA, variante_cle="crac")
    _retirer(client, r["id"], STAG)                    # aucun corps
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[8])
    _retirer(client, r["id"], STAG, vu={})             # un `vu` vide ne garde rien
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0


def test_retirer_lit_les_qualificatifs_comme_un_ensemble(client, decor):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="origine-du-son", mots=[1],
              qualificatifs=["personnage", "objet"])
    _retirer(client, r["id"], STAG, vu={"qualificatifs": ["personnage", "objet", "objet"]})


def test_retirer_vu_ne_porte_que_les_valeurs_gardees(client, decor, db_path):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[8])
    _retirer(client, r["id"], STAG, attendu=(422,), vu={"auteur": "stag"})
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 1


def test_la_vue_d_un_releve_dit_le_numero_de_sa_version(client, decor):
    """Tranche 2 : la route du plan prend le NUMÉRO ; la vue ne disait que `version_id`."""
    # Une version 2 publiée et active (aucun relevé encore : ce n'est pas une montée), pour
    # que le numéro ne se confonde ni avec 1 ni avec l'identifiant de la ligne (une autre
    # grille d'abord, qui prend un identifiant de version).
    importer(client, decor["p"], LEA, nom="Autre")
    importer(client, decor["p"], LEA, grille_id=decor["grille_id"],
             entrees=MODELE.replace("un cri poussé", "un cri lancé"))
    ok(client.post(f"/api/grilles/{decor['grille_id']}/versions/2/publication", headers=LEA))
    ok(client.put(f"/api/projets/{decor['p']}/grilles/{decor['grille_id']}/activation",
                  headers=LEA, json={"version": 2}))
    decor["numero"] = 2
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[8])
    assert r["version"] == 2 and r["version_id"] != 2
    lus = ok(client.get(f"/api/planches/{decor['planche']}/releves", headers=ANA))
    assert [x["version"] for x in lus["releves"]] == [2]
    ok(client.get(f"/api/grilles/{r['grille_id']}/versions/{lus['releves'][0]['version']}",
                  headers=STAG))


def test_une_grille_desactivee_laisse_ses_releves_en_lecture(client, decor):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[8])
    ok(client.delete(f"/api/projets/{decor['p']}/grilles/{decor['grille_id']}/activation",
                     headers=LEA), 204)
    _modifier(client, r["id"], STAG, attendu=(409,), mots=[1])
    ok(client.delete(f"/api/releves/{r['id']}", headers=STAG), 409)
    lus = ok(client.get(f"/api/planches/{decor['planche']}/releves", headers=STAG))
    assert [x["id"] for x in lus["releves"]] == [r["id"]]
    assert lus["releves"][0]["modifiable"] is False


# --------------------------------------------------------------------------- #
# Lire
# --------------------------------------------------------------------------- #
def test_les_releves_de_la_planche(client, decor):
    a = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[8])
    b = poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    tp = poser(client, decor, qui=TP, region_id=bulle(decor), entree_cle="cri", mots=[1])
    lus = ok(client.get(f"/api/planches/{decor['planche']}/releves", headers=ANA))
    assert [x["id"] for x in lus["releves"]] == [a["id"], b["id"], tp["id"]]
    assert all(x["modifiable"] is False for x in lus["releves"])     # Ana ne fait que lire
    assert [x["collectif"] for x in lus["releves"]] == [False, False, True]
    ok(client.get(f"/api/planches/{decor['planche']}/releves", headers=ZOE), 404)
    lus = ok(client.get(f"/api/planches/{decor['planche']}/releves", headers=STAG))
    assert all(x["modifiable"] for x in lus["releves"])


# --------------------------------------------------------------------------- #
# L'état DÉRIVÉ (G2)
# --------------------------------------------------------------------------- #
def _etat(client, d, rid):
    lus = ok(client.get(f"/api/planches/{d['planche']}/releves", headers=LEA))["releves"]
    x = next(r for r in lus if r["id"] == rid)
    return x["etat"], x["causes"]


def test_chaque_cause_produit_son_etat_et_disparait_avec_elle(client, decor, db_path):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[8])
    # Un mot du passage perdu.
    _x(db_path, "UPDATE releve_mot SET rang = NULL WHERE releve_id = ?", (r["id"],))
    assert _etat(client, decor, r["id"]) == ("a_revoir", ["mot_perdu"])
    _x(db_path, "UPDATE releve_mot SET rang = 8 WHERE releve_id = ?", (r["id"],))
    assert _etat(client, decor, r["id"]) == ("normal", [])
    # Le texte changé sans ré-ancrage (un écrivain qui aurait oublié `reindex_region`).
    _x(db_path, "UPDATE regions SET ocr_texte = 'AUTRE CHOSE' WHERE id = ?", (bulle(decor),))
    assert _etat(client, decor, r["id"]) == ("a_revoir", ["texte_change"])
    _x(db_path, "UPDATE regions SET ocr_texte = ? WHERE id = ?",
       ("J'SAIS PAS, IL NE VIENT PAS !!!", bulle(decor)))
    assert _etat(client, decor, r["id"]) == ("normal", [])
    # Une entrée absente de sa version.
    _x(db_path, "UPDATE grille_entree SET cle = 'cri-x' WHERE cle = 'cri'")
    assert _etat(client, decor, r["id"]) == ("a_revoir", ["entree_absente"])
    _x(db_path, "UPDATE grille_entree SET cle = 'cri' WHERE cle = 'cri-x'")
    assert _etat(client, decor, r["id"]) == ("normal", [])


def test_une_region_qui_change_de_type_met_ses_releves_a_revoir(client, decor):
    """G8 : rien n'est retiré ; repasser la région à son type rend le relevé normal."""
    r = poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[8])
    ok(client.put(f"/api/regions/{bulle(decor)}", headers=LEA, json={"type": "case"}))
    assert _etat(client, decor, r["id"]) == ("a_revoir", ["type_change"])
    ok(client.put(f"/api/regions/{bulle(decor)}", headers=LEA, json={"type": "bulle"}))
    assert _etat(client, decor, r["id"]) == ("normal", [])


def test_un_lien_dont_la_region_disparait_passe_a_revoir_et_garde_son_texte(client, decor):
    ok(client.put(f"/api/regions/{decor['autre_bulle']}", headers=LEA,
                  json={"ocr_texte": "MOI AUSSI"}))
    r = poser(client, decor, region_id=bulle(decor), entree_cle="reponse-a",
              lien_region_id=decor["autre_bulle"])
    ok(client.delete(f"/api/regions/{decor['autre_bulle']}", headers=LEA), 204)
    lus = ok(client.get(f"/api/planches/{decor['planche']}/releves", headers=LEA))["releves"]
    x = next(v for v in lus if v["id"] == r["id"])
    assert x["etat"] == "a_revoir" and x["causes"] == ["lien_perdu"]
    assert x["lien"] == {"region_id": decor["autre_bulle"], "existe": False,
                         "texte": "MOI AUSSI"}


def test_a_completer_une_precision_attendue_et_absente(client, decor):
    r = poser(client, decor, region_id=bulle(decor), entree_cle="origine-du-son", mots=[1])
    assert (r["etat"], r["causes"]) == ("a_completer", ["precision_manquante"])
    r = _modifier(client, r["id"], STAG, precision="dehors")
    assert r["etat"] == "normal"


def test_la_regle_du_type_est_la_meme_dans_la_vue_et_en_python(db_path, client, album,
                                                              planche):
    """La vue `releves_effectifs` écrit en SQL la règle de `grilles.type_convient` : les deux
    s'accordent sur chaque type de région et chaque sorte de cible."""
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        pid = c.execute("SELECT id FROM projet LIMIT 1").fetchone()[0]
        gid = c.execute("INSERT INTO grille (projet_id, nom) VALUES (?, 'x')",
                        (pid,)).lastrowid
        n = 0
        for cibles in (("mots",), ("case",), ("bulle", "cartouche", "texte"), ("planche",),
                       ("entite",), ("personnage", "case")):
            n += 1
            vid = c.execute("INSERT INTO grille_version (grille_id, numero, etat, cible) "
                            "VALUES (?, ?, 'publiee', ?)",
                            (gid, n, grilles.ecrire_cibles(cibles))).lastrowid
            c.execute("INSERT INTO grille_entree (version_id, cle, forme, libelle) "
                      "VALUES (?, 'e', 'simple', 'e')", (vid,))
            for type_ in ("case", "bulle", "cartouche", "texte", "personnage", "detail"):
                rg = c.execute("INSERT INTO regions (planche_id, type) VALUES (?, ?)",
                               (planche["id"], type_)).lastrowid
                rid = c.execute("INSERT INTO releve (region_id, grille_id, version_id, "
                                "entree_cle) VALUES (?, ?, ?, 'e')", (rg, gid, vid)).lastrowid
                vue = c.execute("SELECT type_change FROM releves_effectifs WHERE id = ?",
                                (rid,)).fetchone()[0]
                assert bool(vue) == (not grilles.type_convient(type_, cibles)), (type_, cibles)
    finally:
        c.rollback()
        c.close()


# --------------------------------------------------------------------------- #
# Une grille ouverte : une entrée naît en la posant (G14)
# --------------------------------------------------------------------------- #
def test_une_entree_nait_en_la_posant_dans_une_grille_ouverte(client, decor, db_path):
    entete = ["cle", "forme", "libelle"]
    g = grille_active(client, decor["p"], entrees=csv_de([entete, ["vu", "simple", "vu"]]),
                      listes=None, nom="Libre", ouverte=True)
    d = {**decor, **g}
    r = poser(client, d, region_id=bulle(d), nouvelle_entree={"libelle": "Rire Nerveux"},
              mots=[0])
    assert r["entree_cle"] == "rire nerveux"
    r2 = poser(client, d, region_id=bulle(d), nouvelle_entree={"libelle": "rire  nerveux"},
               mots=[1])
    assert r2["entree_cle"] == "rire nerveux"
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille_entree WHERE cle = 'rire nerveux'")[
        0]["n"] == 1
    assert _q(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table = 'grille' "
                       "AND apres LIKE '%entree_neuve%'")[0]["n"] == 1
    # Dans une grille fermée, non.
    poser(client, decor, attendu=(422,), region_id=bulle(decor),
          nouvelle_entree={"libelle": "nouveau"}, mots=[0])
    # Ni sans droit d'écrire l'album : c'est ce qui borne qui enrichit.
    poser(client, d, qui=ANA, attendu=(404,), region_id=bulle(d),
          nouvelle_entree={"libelle": "autre"}, mots=[0])


# --------------------------------------------------------------------------- #
# Le journal : retenu, mais dans les rangs (G10)
# --------------------------------------------------------------------------- #
def test_les_releves_sont_retenus_mais_comptent_dans_les_rangs():
    import sys
    from conftest import REPO_ROOT
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import _commun
    for cible in ("releve", "releve_planche"):
        assert cible in _commun.CIBLES_RETENUES and cible not in _commun.CIBLES_CORPUS
        assert cible not in _commun.CIBLES_SANS_RANG
    assert "grille" in _commun.CIBLES_SANS_RANG


def test_qui_ne_fait_que_poser_des_releves_a_un_pseudonyme(client, decor, db_path):
    import sys
    from conftest import REPO_ROOT
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import _commun
    poser(client, decor, region_id=bulle(decor), entree_cle="cri", mots=[8])
    c = sqlite3.connect(db_path)
    try:
        assert "stag" in _commun.pseudonymes(c)
    finally:
        c.close()
