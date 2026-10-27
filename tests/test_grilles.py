"""Les grilles d'annotation — le tableur, l'import, le bilan, la publication, l'activation, le
masque, la lecture du plan, la coquille, le réexport (ANN-7, tranche 1 ; cadrage R2 à R4,
R8 ; décisions de Hugo du 2026-10-25).

La grille est FICTIVE (`tools/grille-modele.csv`), écrite pour les tests. Chaque garde se
joue sous l'identité qu'elle concerne : un geste de responsable sous la responsable, un refus
sous qui le reçoit.
"""
import io
import json
import sqlite3
import subprocess
import sys
import zipfile

import pytest

import grille_import
import grilles
from conftest import ADMIN
from grilles_decor import (ADM, ANA, BEA, IVAN, LEA, MODELE, MODELE_LISTES, OLGA, RACINE, SAM,
                           STAG, ZOE, bac_de_bea, csv_de, flux, grille_active, importer,
                           monter, ok)

ENTETE = ["cle", "rubrique", "rubrique_cle", "forme", "libelle", "variante_cle", "variante",
          "structure", "definition", "exemples", "piege", "liste", "precision", "lien", "cible",
          "cardinalite"]


def _ligne(**v):
    return [v.get(c, "") for c in ENTETE]


@pytest.fixture
def decor(client, db_path, derriere_proxy):
    return monter(client, db_path)


def _q(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, p)]
    finally:
        c.close()


# --------------------------------------------------------------------------- #
# Le tableur : lu entier, refusé entier
# --------------------------------------------------------------------------- #
def test_le_modele_fictif_se_lit_sans_anomalie_et_fait_jouer_les_trois_formes():
    lu = grille_import.lire(flux(MODELE), flux(MODELE_LISTES), porte_sur="mots")
    assert lu["anomalies"] == [] and lu["avertissements"] == []
    c = lu["contenu"]
    formes = {e["forme"] for e in c["entrees"].values()}
    assert formes == {"simple", "variantes", "qualificatifs"}
    assert {lc for lc in c["listes"]} == {"sources", "manieres"}
    # Deux listes PARTAGÉES : chacune nommée par deux entrées.
    for lc in ("sources", "manieres"):
        assert sum(e["liste_cle"] == lc for e in c["entrees"].values()) == 2
    assert c["entrees"]["ton-de-voix"]["cible"] == "bulle|cartouche|texte"
    assert c["entrees"]["ton-de-voix"]["cardinalite"] == "une"
    assert c["entrees"]["reponse-a"]["lien"] is True
    assert c["entrees"]["origine-du-son"]["precision"] == "lieu"
    # Trois étages de rubriques.
    assert grilles.chemin_de_rubrique(c["rubriques"], "chocs") == ["sons", "bruits", "chocs"]


ANOMALIES = {
    "cle vide": [_ligne(forme="simple", libelle="x")],
    "cle en double": [_ligne(cle="a", forme="simple", libelle="a"),
                      _ligne(cle="a", forme="simple", libelle="b")],
    "forme inconnue": [_ligne(cle="a", forme="libre", libelle="a")],
    "libellé vide": [_ligne(cle="a", forme="simple")],
    "variante sans entrée": [_ligne(cle="a", forme="simple", libelle="a"),
                             _ligne(cle="b", variante_cle="v", variante="v")],
    "variante sous une entrée simple": [_ligne(cle="a", forme="simple", libelle="a"),
                                        _ligne(cle="a", variante_cle="v", variante="v")],
    "entrée à variantes sans variante": [_ligne(cle="a", forme="variantes", libelle="a")],
    "variante en double": [_ligne(cle="a", forme="variantes", libelle="a"),
                           _ligne(cle="a", variante_cle="v", variante="v"),
                           _ligne(cle="a", variante_cle="v", variante="w")],
    "variante qui remplit autrement une colonne de l'entrée": [
        _ligne(cle="a", forme="variantes", libelle="a", rubrique="R", rubrique_cle="r"),
        _ligne(cle="a", rubrique="Autre", rubrique_cle="r", variante_cle="v", variante="v")],
    "liste inconnue": [_ligne(cle="a", forme="qualificatifs", libelle="a", liste="nulle")],
    "qualificatifs sans liste": [_ligne(cle="a", forme="qualificatifs", libelle="a")],
    "liste sur une entrée simple": [_ligne(cle="a", forme="simple", libelle="a",
                                           liste="sources")],
    "cible inconnue": [_ligne(cle="a", forme="simple", libelle="a", cible="ballon")],
    "cibles mêlées": [_ligne(cle="a", forme="simple", libelle="a", cible="mots | case")],
    "cardinalité inconnue": [_ligne(cle="a", forme="simple", libelle="a",
                                    cardinalite="souvent")],
    "lien invalide": [_ligne(cle="a", forme="simple", libelle="a", lien="peut-être")],
    "étages de rubrique incohérents": [_ligne(cle="a", forme="simple", libelle="a",
                                              rubrique="A > B", rubrique_cle="a")],
    "deux libellés pour une rubrique": [
        _ligne(cle="a", forme="simple", libelle="a", rubrique="Sons", rubrique_cle="s"),
        _ligne(cle="b", forme="simple", libelle="b", rubrique="Bruits", rubrique_cle="s")],
    "deux identifiants pour une rubrique": [
        _ligne(cle="a", forme="simple", libelle="a", rubrique="Sons", rubrique_cle="s"),
        _ligne(cle="b", forme="simple", libelle="b", rubrique="Sons", rubrique_cle="t")],
    "parent circulaire": [
        _ligne(cle="a", forme="simple", libelle="a", rubrique="A > B", rubrique_cle="x > y"),
        _ligne(cle="b", forme="simple", libelle="b", rubrique="B > A", rubrique_cle="y > x")],
}


@pytest.mark.parametrize("nom", sorted(ANOMALIES))
def test_une_anomalie_refuse_le_fichier_entier(nom):
    """G12 : une anomalie de structure refuse TOUT, et le dit — une ligne écartée se lirait,
    dans le bilan, comme une entrée disparue. Une bonne ligne à côté ne passe pas non plus."""
    bonne = _ligne(cle="bonne", forme="simple", libelle="bonne")
    lu = grille_import.lire(flux(csv_de([ENTETE, bonne, *ANOMALIES[nom]])),
                            flux(MODELE_LISTES), porte_sur="mots")
    assert lu["contenu"] is None
    assert lu["anomalies"], nom


def test_toutes_les_anomalies_sont_dites_d_un_coup():
    lignes = [ENTETE, *ANOMALIES["forme inconnue"], *ANOMALIES["cible inconnue"]]
    lignes[2][0] = "b"
    lu = grille_import.lire(flux(csv_de(lignes)), None, porte_sur="mots")
    assert len(lu["anomalies"]) == 2


def test_une_ligne_de_variante_peut_recopier_les_colonnes_de_son_entree():
    """Un tableur rempli en tirant la cellule vers le bas recopie la rubrique sur les lignes
    de variante : identique à l'entrée, ce n'est pas une anomalie (R3, tranché pour la
    personne qui remplit)."""
    lignes = [ENTETE,
              _ligne(cle="a", forme="variantes", libelle="a", rubrique="R", rubrique_cle="r"),
              _ligne(cle="a", forme="variantes", libelle="a", rubrique="R", rubrique_cle="r",
                     variante_cle="v", variante="v")]
    lu = grille_import.lire(flux(csv_de(lignes)), None, porte_sur="mots")
    assert lu["anomalies"] == [] and list(lu["contenu"]["entrees"]["a"]["variantes"]) == ["v"]


def test_porte_sur_est_exige_et_borne():
    lignes = [ENTETE, _ligne(cle="a", forme="simple", libelle="a")]
    assert grille_import.lire(flux(csv_de(lignes)), None, porte_sur=None)["anomalies"]
    assert grille_import.lire(flux(csv_de(lignes)), None, porte_sur="mots | planche")[
        "anomalies"]
    assert not grille_import.lire(flux(csv_de(lignes)), None,
                                  porte_sur="bulle | cartouche")["anomalies"]


def test_un_entete_sans_colonne_obligatoire_est_une_erreur_de_format():
    with pytest.raises(grille_import.FormatInvalide):
        grille_import.lire(flux("cle;libelle\r\na;b\r\n"), None, porte_sur="mots")


def test_les_avertissements_ne_refusent_rien():
    listes = MODELE_LISTES + "sources;autre libellé;bruit;bruit;\r\n"
    lu = grille_import.lire(flux(MODELE), flux(listes), porte_sur="mots")
    assert lu["anomalies"] == [] and any("deux libellés" in a for a in lu["avertissements"])
    lignes = [ENTETE, _ligne(cle="e", forme="simple", libelle="e", cible="entite")]
    lu = grille_import.lire(flux(csv_de(lignes)), None, porte_sur="mots")
    assert lu["contenu"] is not None and any("G3" in a for a in lu["avertissements"])


# --------------------------------------------------------------------------- #
# Importer, le bilan, publier
# --------------------------------------------------------------------------- #
def test_a_blanc_rend_le_bilan_sans_rien_ecrire(client, decor, db_path):
    res = importer(client, decor["p"], LEA, a_blanc=True)
    assert res["ecrit"] is False and res["grille_id"] is None
    assert {n["cle"] for n in res["bilan"]["nes"] if n["quoi"] == "entree"} >= {"cri", "echo"}
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille")[0]["n"] == 0


def test_importer_publier_reimporter_le_meme_fichier_ne_change_rien(client, decor, db_path):
    res = importer(client, decor["p"], LEA, note="première")
    gid = res["grille_id"]
    assert res["ecrit"] and res["version"] == {"numero": 1, "etat": "brouillon"}
    again = importer(client, decor["p"], LEA, grille_id=gid)
    assert again["aucun_changement"] and not again["ecrit"]
    ok(client.post(f"/api/grilles/{gid}/versions/1/publication", headers=LEA))
    assert importer(client, decor["p"], LEA, grille_id=gid)["aucun_changement"]
    # Réordonner les lignes ne fait pas une version (l'empreinte trie par `cle`).
    lignes = MODELE.strip("\r\n").split("\r\n")
    melange = "\r\n".join([lignes[0], *reversed(lignes[1:])]) + "\r\n"
    assert importer(client, decor["p"], LEA, grille_id=gid, entrees=melange)[
        "aucun_changement"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille_version")[0]["n"] == 1
    assert [e["type"] for e in _q(db_path, "SELECT type FROM evenement WHERE "
                                            "cible_table = 'grille' ORDER BY id")] == [
        "creation", "modification", "modification"]
    assert {e["agent"] for e in _q(db_path, "SELECT agent FROM evenement WHERE "
                                             "cible_table = 'grille'")} == {"lea"}


def test_une_version_suivante_est_un_brouillon_avec_son_bilan(client, decor, db_path):
    g = grille_active(client, decor["p"])
    modifie = (MODELE.replace(";simple;cri;", ";simple;cri perçant;")
               .replace("regard-camera;E. Image;image;simple;regard caméra;;;;le personnage "
                        "regarde le lecteur;;;;;;case;\r\n", "")
               + "souffle;A. Sons > Voix;sons > voix;simple;souffle;;;;un souffle;;;;;;;\r\n")
    res = importer(client, decor["p"], LEA, grille_id=g["grille_id"], entrees=modifie)
    assert res["version"] == {"numero": 2, "etat": "brouillon"}
    assert res["compare_a"] == 1
    b = res["bilan"]
    assert [r["cle"] for r in b["renommes"]] == ["cri"]
    assert [d["cle"] for d in b["disparus"]] == ["image", "regard-camera"]   # sa rubrique aussi
    assert [n["cle"] for n in b["nes"] if n["quoi"] == "entree"] == ["souffle"]
    # Réimporter un autre contenu REMPLACE le brouillon, au même numéro.
    res = importer(client, decor["p"], LEA, grille_id=g["grille_id"],
                   entrees=modifie.replace("un souffle", "un souffle court"))
    assert res["version"]["numero"] == 2 and res["version"].get("remplace")
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille_version")[0]["n"] == 2


def test_un_disparu_dit_le_nombre_de_releves_poses_sur_lui(client, decor, db_path):
    g = grille_active(client, decor["p"])
    vid = _q(db_path, "SELECT id FROM grille_version")[0]["id"]
    c = sqlite3.connect(db_path)
    c.execute("INSERT INTO releve (region_id, grille_id, version_id, entree_cle) "
              "VALUES (?, ?, ?, 'regard-camera')", (decor["zones"]["case"], g["grille_id"], vid))
    c.commit()
    c.close()
    sans = MODELE.replace("regard-camera;E. Image;image;simple;regard caméra;;;;le personnage "
                          "regarde le lecteur;;;;;;case;\r\n", "")
    res = importer(client, decor["p"], LEA, grille_id=g["grille_id"], entrees=sans,
                   a_blanc=True)
    assert [d for d in res["bilan"]["disparus"] if d["quoi"] == "entree"] == [
        {"quoi": "entree", "cle": "regard-camera", "libelle": "regard caméra", "releves": 1}]
    assert res["bilan"]["releves_touches"] == 1


def test_un_tableur_refuse_rend_ses_anomalies_et_n_ecrit_rien(client, decor, db_path):
    mauvais = MODELE + "orpheline;;;;;v;v;;;;;;;;;\r\n"
    res = importer(client, decor["p"], LEA, entrees=mauvais, attendu=(422,))
    assert res["detail"]["anomalies"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille")[0]["n"] == 0


def test_le_nom_est_unique_dans_son_projet_seulement(client, decor):
    importer(client, decor["p"], LEA, nom="Signaux")
    importer(client, decor["p"], LEA, nom="signaux", attendu=(409,))
    importer(client, decor["q"], ZOE, nom="Signaux")


def test_un_brouillon_supprime_emporte_la_grille_qui_n_avait_que_lui(client, decor, db_path):
    gid = importer(client, decor["p"], LEA)["grille_id"]
    ok(client.delete(f"/api/grilles/{gid}/versions/1", headers=LEA), 204)
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille")[0]["n"] == 0


def test_publier_ce_qui_n_est_pas_un_brouillon_est_refuse(client, decor):
    g = grille_active(client, decor["p"])
    ok(client.post(f"/api/grilles/{g['grille_id']}/versions/1/publication", headers=LEA), 409)


# --------------------------------------------------------------------------- #
# Qui gère, qui lit
# --------------------------------------------------------------------------- #
def test_importer_est_un_geste_de_responsable(client, decor):
    importer(client, decor["p"], SAM, attendu=(403,))          # membre, ne gère pas
    importer(client, decor["p"], ANA, attendu=(403,))          # lit le projet, ne gère pas
    importer(client, decor["p"], ZOE, attendu=(404,))          # ne voit pas le projet
    importer(client, decor["p"], ADMIN)                        # l'administrateur passe outre


def test_le_brouillon_reste_chez_ses_auteurs(client, decor):
    gid = importer(client, decor["p"], LEA)["grille_id"]
    ok(client.get(f"/api/grilles/{gid}/versions/1", headers=LEA))
    ok(client.get(f"/api/grilles/{gid}/versions/1", headers=SAM), 404)
    assert [v["etat"] for v in ok(client.get(f"/api/grilles/{gid}", headers=LEA))[
        "versions"]] == ["brouillon"]


def test_une_grille_qui_n_est_qu_un_brouillon_n_a_pas_de_nom_pour_un_membre(client, decor):
    """Relecture croisée, constat 4 — un simple membre du projet ne lit pas même le NOM d'une
    grille sans version publiée ni vivante : le même 404 qu'un identifiant qui n'existe pas,
    sur la fiche comme dans la liste. Publiée, la moitié (a) de `clause_grille` la lui ouvre."""
    gid = importer(client, decor["p"], LEA, nom="Étude secrète des jurons")["grille_id"]
    refus = client.get(f"/api/grilles/{gid}", headers=SAM)
    absente = client.get("/api/grilles/999999", headers=SAM)
    assert refus.status_code == absente.status_code == 404
    assert "jurons" not in refus.text
    assert refus.json()["detail"] == absente.json()["detail"].replace("999999", str(gid))
    lst = ok(client.get(f"/api/projets/{decor['p']}/grilles", headers=SAM))
    assert "jurons" not in json.dumps(lst, ensure_ascii=False)
    ok(client.get(f"/api/grilles/{gid}", headers=LEA))          # qui gère, oui
    ok(client.post(f"/api/grilles/{gid}/versions/1/publication", headers=LEA))
    assert ok(client.get(f"/api/grilles/{gid}", headers=SAM))["nom"] == \
        "Étude secrète des jurons"


def test_qui_lit_le_plan_publie(client, decor, db_path):
    """`clause_grille` (R8, G5) sous les quatre identités : (a) un membre du projet, même
    sans album lu ; (b) qui lit un album d'un projet où la grille est ACTIVE ; (c) qui lit un
    album portant un relevé de la grille, même désactivée ; et un lecteur d'un autre projet,
    jamais."""
    gid = importer(client, decor["p"], LEA)["grille_id"]
    ok(client.post(f"/api/grilles/{gid}/versions/1/publication", headers=LEA))
    url = f"/api/grilles/{gid}/versions/1"
    # (b) vise un accès de collection HORS du projet : depuis la tranche 3c (F2), seule une
    # base d'avant la v38 retouchée à la main en porte — `ana` n'est plus que lectrice.
    c = sqlite3.connect(db_path)
    c.execute("DELETE FROM projet_acces WHERE principal = 'ana'")
    c.commit()
    c.close()
    ok(client.get(url, headers=SAM))                           # (a)
    ok(client.get(url, headers=ANA), 404)                      # pas encore active
    ok(client.get(url, headers=ZOE), 404)
    ok(client.put(f"/api/projets/{decor['p']}/grilles/{gid}/activation", headers=LEA,
                  json={"version": 1}))
    ok(client.get(url, headers=ANA))                           # (b)
    ok(client.get(url, headers=ZOE), 404)
    ok(client.delete(f"/api/projets/{decor['p']}/grilles/{gid}/activation", headers=LEA), 204)
    ok(client.get(url, headers=ANA), 404)
    vid = _q(db_path, "SELECT id FROM grille_version")[0]["id"]
    c = sqlite3.connect(db_path)
    c.execute("INSERT INTO releve (region_id, grille_id, version_id, entree_cle) "
              "VALUES (?, ?, ?, 'cri')", (decor["zones"]["bulle"], gid, vid))
    c.commit()
    c.close()
    ok(client.get(url, headers=ANA))                           # (c)
    ok(client.get(url, headers=ZOE), 404)


def test_les_grilles_du_projet(client, decor):
    g = grille_active(client, decor["p"])
    importer(client, decor["p"], LEA, nom="Brouillonne")
    vue = ok(client.get(f"/api/projets/{decor['p']}/grilles", headers=LEA))
    assert vue["gerable"] and [a["id"] for a in vue["actives"]] == [g["grille_id"]]
    assert {x["nom"] for x in vue["grilles"]} == {"Signaux", "Brouillonne"}
    vue = ok(client.get(f"/api/projets/{decor['p']}/grilles", headers=ANA))
    assert not vue["gerable"] and "grilles" not in vue
    assert vue["actives"][0]["version"] == {"numero": 1, "etat": "publiee",
                                            "porte_sur": ["mots"]}
    ok(client.get(f"/api/projets/{decor['p']}/grilles", headers=ZOE), 404)


def test_le_plan_dit_cibles_et_cardinalites_effectives(client, decor):
    g = grille_active(client, decor["p"])
    plan = ok(client.get(f"/api/grilles/{g['grille_id']}/versions/1", headers=LEA))
    e = {x["cle"]: x for x in plan["entrees"]}
    assert e["cri"]["cibles"] == ["mots"] and e["cri"]["cardinalite"] == "plusieurs"
    assert e["ton-de-voix"]["cibles"] == ["bulle", "cartouche", "texte"]
    assert e["ton-de-voix"]["pose"] == "zone" and e["ton-de-voix"]["cardinalite"] == "une"
    assert e["ambiance"]["pose"] == "planche" and e["ambiance"]["cardinalite"] == "une"
    assert e["onomatopee"]["rubriques"] == ["sons", "bruits", "chocs"]
    assert [v["cle"] for v in e["onomatopee"]["variantes"]] == ["bang", "crac", "splash"]
    assert e["cri"]["exemples"] == ["AAAH !", "OUILLE"]


# --------------------------------------------------------------------------- #
# Activer, masquer
# --------------------------------------------------------------------------- #
def test_activer_une_version_publiee_seulement_et_par_le_responsable(client, decor):
    gid = importer(client, decor["p"], LEA)["grille_id"]
    url = f"/api/projets/{decor['p']}/grilles/{gid}/activation"
    ok(client.put(url, headers=LEA, json={"version": 1}), 409)      # un brouillon
    ok(client.post(f"/api/grilles/{gid}/versions/1/publication", headers=LEA))
    ok(client.put(url, headers=SAM, json={"version": 1}), 403)
    ok(client.put(url, headers=LEA, json={"version": 1}))
    ok(client.put(url, headers=LEA, json={"version": 1}))           # déjà : rien ne change


def test_un_projet_n_active_que_ses_grilles(client, decor):
    g = grille_active(client, decor["p"])
    # Zoé gère Q ; la grille de P ne lui est pas lisible : introuvable.
    ok(client.put(f"/api/projets/{decor['q']}/grilles/{g['grille_id']}/activation",
                  headers=ZOE, json={"version": 1}), 404)
    # L'administrateur la lit, mais le catalogue n'existe pas : 409 nommé.
    r = client.put(f"/api/projets/{decor['q']}/grilles/{g['grille_id']}/activation",
                   headers=ADMIN, json={"version": 1})
    assert r.status_code == 409 and "catalogue" in r.json()["detail"]


def test_changer_la_version_d_une_activation_qui_porte_des_releves_est_refuse(client, decor,
                                                                            db_path):
    g = grille_active(client, decor["p"])
    importer(client, decor["p"], LEA, grille_id=g["grille_id"],
             entrees=MODELE.replace("un cri poussé", "un cri lancé"))
    ok(client.post(f"/api/grilles/{g['grille_id']}/versions/2/publication", headers=LEA))
    vid = _q(db_path, "SELECT id FROM grille_version WHERE numero = 1")[0]["id"]
    c = sqlite3.connect(db_path)
    c.execute("INSERT INTO releve (region_id, grille_id, version_id, entree_cle) "
              "VALUES (?, ?, ?, 'cri')", (decor["zones"]["bulle"], g["grille_id"], vid))
    c.commit()
    c.close()
    r = client.put(f"/api/projets/{decor['p']}/grilles/{g['grille_id']}/activation",
                   headers=LEA, json={"version": 2})
    assert r.status_code == 409 and "montée de version" in r.json()["detail"]
    # Ni par la porte de derrière : désactiver, puis réactiver dans l'autre version.
    ok(client.delete(f"/api/projets/{decor['p']}/grilles/{g['grille_id']}/activation",
                     headers=LEA), 204)
    ok(client.put(f"/api/projets/{decor['p']}/grilles/{g['grille_id']}/activation",
                  headers=LEA, json={"version": 2}), 409)
    ok(client.put(f"/api/projets/{decor['p']}/grilles/{g['grille_id']}/activation",
                  headers=LEA, json={"version": 1}))


def test_masquer_est_un_geste_du_proprietaire_de_la_collection(client, decor):
    g = grille_active(client, decor["p"])
    url = f"/api/collections/{decor['c']}/grilles-masquees/{g['grille_id']}"
    ok(client.put(url, headers=STAG), 403)                    # écrit, ne possède pas
    ok(client.put(url, headers=OLGA))
    vue = ok(client.get(f"/api/projets/{decor['p']}/grilles", headers=OLGA))
    assert vue["actives"][0]["masquee_dans"] == [decor["c"]]
    ok(client.delete(url, headers=OLGA), 204)
    ok(client.delete(url, headers=OLGA), 404)


def test_on_ne_masque_que_ce_qui_est_actif(client, decor):
    gid = importer(client, decor["p"], LEA)["grille_id"]
    ok(client.post(f"/api/grilles/{gid}/versions/1/publication", headers=LEA))
    ok(client.put(f"/api/collections/{decor['c']}/grilles-masquees/{gid}", headers=LEA), 409)


# --------------------------------------------------------------------------- #
# Coquille, réexport, retraite, suppression
# --------------------------------------------------------------------------- #
def test_une_coquille_se_corrige_sans_nouvelle_version(client, decor, db_path):
    g = grille_active(client, decor["p"])
    url = f"/api/grilles/{g['grille_id']}/versions/1/coquille"
    ok(client.patch(url, headers=SAM, json={"entree_cle": "cri", "definition": "x"}), 403)
    plan = ok(client.patch(url, headers=LEA,
                           json={"entree_cle": "cri", "definition": "un cri, en lettres",
                                 "exemples": ["AÏE"]}))
    cri = next(e for e in plan["entrees"] if e["cle"] == "cri")
    assert cri["definition"] == "un cri, en lettres" and cri["exemples"] == ["AÏE"]
    ok(client.patch(url, headers=LEA, json={"entree_cle": "onomatopee", "variante_cle": "bang",
                                            "piege": "pas un tir"}))
    ok(client.patch(url, headers=LEA, json={"entree_cle": "cri", "libelle": "x"}), 422)
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille_version")[0]["n"] == 1
    # Le tableur qui porte la même correction se réimporte sans changement.
    corrige = (MODELE.replace("un cri poussé par un personnage, écrit en toutes lettres",
                              "un cri, en lettres").replace("AAAH ! | OUILLE", "AÏE")
               .replace("un choc sec, une détonation;BANG ! | PAN !;",
                        "un choc sec, une détonation;BANG ! | PAN !;pas un tir"))
    assert importer(client, decor["p"], LEA, grille_id=g["grille_id"], entrees=corrige)[
        "aucun_changement"]


def test_le_reexport_rend_le_tableur_qui_se_reimporte_a_l_identique(client, decor, db_path):
    g = grille_active(client, decor["p"])
    url = f"/api/grilles/{g['grille_id']}/versions/1/tableur"
    ok(client.get(url, headers=SAM), 403)
    r = client.get(url, headers=LEA)
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        entrees = z.read("grille-rubriques-entrees.csv").decode("utf-8-sig")
        listes = z.read("grille-listes-qualificatifs.csv").decode("utf-8-sig")
    # Dérivée dans l'autre projet : la même empreinte (les `cle` gardent la grille comparable).
    res = importer(client, decor["q"], ZOE, entrees=entrees, listes=listes, nom="Dérivée")
    emp = {r["empreinte"] for r in _q(db_path, "SELECT empreinte FROM grille_version")}
    assert len(emp) == 1, emp
    assert res["ecrit"]


def test_le_reexport_neutralise_une_formule_et_la_reimporte(client, decor, db_path):
    formule = MODELE.replace("AAAH ! | OUILLE", "=SOMME(A1) | -t-il")
    gid = importer(client, decor["p"], LEA, entrees=formule)["grille_id"]
    r = client.get(f"/api/grilles/{gid}/versions/1/tableur", headers=LEA)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        entrees = z.read("grille-rubriques-entrees.csv").decode("utf-8-sig")
    assert ";'=SOMME(A1) | -t-il;" in entrees
    assert importer(client, decor["p"], LEA, grille_id=gid, entrees=entrees)[
        "aucun_changement"]


def test_retirer_une_grille_active_est_refuse(client, decor):
    g = grille_active(client, decor["p"])
    ok(client.post(f"/api/grilles/{g['grille_id']}/retrait", headers=LEA), 409)
    ok(client.delete(f"/api/projets/{decor['p']}/grilles/{g['grille_id']}/activation",
                     headers=LEA), 204)
    vue = ok(client.post(f"/api/grilles/{g['grille_id']}/retrait", headers=LEA))
    assert vue["retiree_le"]
    ok(client.put(f"/api/projets/{decor['p']}/grilles/{g['grille_id']}/activation",
                  headers=LEA, json={"version": 1}), 409)
    importer(client, decor["p"], LEA, grille_id=g["grille_id"], attendu=(409,))


def test_une_grille_employee_ne_se_supprime_pas(client, decor, db_path):
    g = grille_active(client, decor["p"])
    ok(client.delete(f"/api/grilles/{g['grille_id']}", headers=LEA), 409)      # active
    ok(client.delete(f"/api/projets/{decor['p']}/grilles/{g['grille_id']}/activation",
                     headers=LEA), 204)
    vid = _q(db_path, "SELECT id FROM grille_version")[0]["id"]
    c = sqlite3.connect(db_path)
    c.execute("INSERT INTO releve (region_id, grille_id, version_id, entree_cle) "
              "VALUES (?, ?, ?, 'cri')", (decor["zones"]["bulle"], g["grille_id"], vid))
    c.commit()
    c.close()
    ok(client.delete(f"/api/grilles/{g['grille_id']}", headers=LEA), 409)      # un relevé
    c = sqlite3.connect(db_path)
    c.execute("DELETE FROM releve")
    c.commit()
    c.close()
    ok(client.delete(f"/api/grilles/{g['grille_id']}", headers=LEA), 204)


# --------------------------------------------------------------------------- #
# Une grille ouverte ; le bac à sable ; le jeu
# --------------------------------------------------------------------------- #
def test_une_grille_ouverte_n_a_qu_une_version_vivante(client, decor):
    res = importer(client, decor["p"], LEA, ouverte=True, nom="Libre")
    assert res["version"] == {"numero": 1, "etat": "vivante"}
    gid = res["grille_id"]
    assert importer(client, decor["p"], LEA, grille_id=gid)["aucun_changement"]
    importer(client, decor["p"], LEA, grille_id=gid,
             entrees=MODELE.replace("cri poussé", "cri lancé"), attendu=(409,))
    ok(client.put(f"/api/projets/{decor['p']}/grilles/{gid}/activation", headers=LEA,
                  json={"version": 1}))


def test_une_grille_dans_un_bac_a_sable_n_existe_que_la(client, decor):
    """G6 : le propriétaire du bac y importe et active ; ses invités la lisent ; personne
    d'autre — pas même un administrateur, dont la portée est bornée aux bacs des autres."""
    bac = bac_de_bea(client)
    g = grille_active(client, bac["projet"], qui=BEA)
    url = f"/api/grilles/{g['grille_id']}/versions/1"
    ok(client.get(url, headers=IVAN))
    ok(client.get(url, headers=ADM), 404)
    ok(client.get(url, headers=LEA), 404)
    importer(client, bac["projet"], IVAN, attendu=(403,))


def test_le_projet_de_jeu_ne_recoit_pas_de_grille(client, decor, db_path):
    c = sqlite3.connect(db_path)
    jeu = c.execute("INSERT INTO projet (nom, jeu) VALUES ('Jeu', 1)").lastrowid
    c.commit()
    c.close()
    importer(client, jeu, ADMIN, attendu=(409,))


# --------------------------------------------------------------------------- #
# L'outil en ligne de commande
# --------------------------------------------------------------------------- #
def test_l_outil_importe_a_blanc_puis_pour_de_bon_puis_publie(data_dir, db_path, tmp_path,
                                                              client):
    projet = client.get("/api/projets", headers=ADMIN).json()[0]["id"]
    env = {"BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir), "PYTHONIOENCODING": "utf-8"}
    import os
    env = {**os.environ, **env}
    outil = [sys.executable, str(RACINE / "tools" / "importer_grille.py")]
    base = [str(RACINE / "tools" / "grille-modele.csv"), "--listes",
            str(RACINE / "tools" / "grille-modele-listes-qualificatifs.csv"),
            "--projet", str(projet), "--nom", "Par l'outil", "--porte-sur", "mots"]
    p = subprocess.run([*outil, *base, "--a-blanc"], env=env, capture_output=True, text=True,
                       encoding="utf-8")
    assert p.returncode == 0, p.stderr
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille")[0]["n"] == 0
    p = subprocess.run([*outil, *base], env=env, capture_output=True, text=True,
                       encoding="utf-8")
    assert p.returncode == 0, p.stderr
    gid = _q(db_path, "SELECT id FROM grille")[0]["id"]
    assert _q(db_path, "SELECT agent FROM evenement WHERE cible_table = 'grille'")[0][
        "agent"] is None
    p = subprocess.run([*outil, "--publier", str(gid)], env=env, capture_output=True,
                       text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    assert _q(db_path, "SELECT etat FROM grille_version")[0]["etat"] == "publiee"
    mauvais = tmp_path / "mauvais.csv"
    mauvais.write_text(MODELE + "orpheline;;;;;v;v;;;;;;;;;\r\n", encoding="utf-8-sig")
    p = subprocess.run([*outil, str(mauvais), "--projet", str(projet), "--grille", str(gid)],
                       env=env, capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 1 and "orpheline" in p.stderr
