"""La Recherche avec les relevés — les étiquettes libres comme les grilles établies (ANN-7, le
mode libre ; J6, J7, et la case « La Recherche fonctionne avec les étiquettes libres comme avec
les grilles », demandée par Hugo le 2026-11-06).

Joué sur une grille OUVERTE (la grille de travail du projet) ET une grille FERMÉE (le modèle
fictif, publié) :
(a) un mot d'une étiquette d'une grille ouverte, tapé dans le champ, trouve sa zone — une
    grille fermée, non (J6 : ses libellés ne sont pas dans l'index) ;
(b) chaque résultat rend les relevés de sa zone, des deux sortes, de quoi les lire en ligne et
    les isoler (`porte`) ;
(c) le filtre `porte=` : une entrée, une entrée et ses variantes, une rubrique, un
    qualificatif, de n'importe quelle grille ; « ou » entre les valeurs d'un filtre, « et »
    entre deux filtres ; une entrée reconnue par sa clé quelle que soit la version du relevé.
"""
import csv
import io
import sqlite3

from conftest import ADMIN
from grilles_decor import STAG, ZOE
from test_grille_de_travail import _travail
from test_releves import decor, poser  # noqa: F401


def _x(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    try:
        r = c.execute(sql, p).fetchall()
        c.commit()
        return r
    finally:
        c.close()


def _chercher(client, qui=STAG, attendu=200, **params):
    r = client.get("/api/recherche", headers=qui, params=params)
    assert r.status_code == attendu, (r.status_code, r.text[:500])
    return r.json()


def _ids(res):
    return sorted(x["region_id"] for x in res["results"])


def _monter(client, decor, db_path):
    """Les relevés des deux sortes, sur les zones du décor."""
    t = _travail(client, decor, db_path)
    z = decor["zones"]
    poser(client, t, region_id=z["case"], nouvelle_entree={"libelle": "lieu : forêt"})
    poser(client, t, region_id=z["bulle"], nouvelle_entree={"libelle": "sentiment : perte"})
    poser(client, t, region_id=z["bulle"], nouvelle_entree={"libelle": "sentiment : tristesse"})
    poser(client, t, region_id=z["cartouche"], nouvelle_entree={"libelle": "sentiment : joie"})
    poser(client, decor, region_id=z["bulle"], entree_cle="cri", mots=[8])
    poser(client, decor, region_id=z["cartouche"], entree_cle="ton-de-voix",
          variante_cle="chuchote")
    poser(client, decor, region_id=z["texte"], entree_cle="onomatopee", variante_cle="bang",
          mots=[0])
    poser(client, decor, region_id=z["texte"], entree_cle="echo", qualificatifs=["hors-champ"],
          mots=[2])
    poser(client, decor, region_id=z["bulle"], entree_cle="echo", qualificatifs=["objet"],
          mots=[0])
    return t, z


# --------------------------------------------------------------------------- #
# (a) le champ cherche les étiquettes des grilles ouvertes
# --------------------------------------------------------------------------- #
def test_un_mot_d_une_etiquette_trouve_sa_zone(client, decor, db_path):
    t, z = _monter(client, decor, db_path)
    assert _ids(_chercher(client, q="tristesse")) == [z["bulle"]]
    assert _ids(_chercher(client, q="foret")) == [z["case"]]           # sans accents
    assert _ids(_chercher(client, q="sentiment")) == sorted([z["bulle"], z["cartouche"]])
    # Le texte se cherche toujours ; une grille FERMÉE n'entre pas dans le champ.
    assert _ids(_chercher(client, q="VIENT")) == [z["bulle"]]
    assert _chercher(client, q="chuchoté")["results"] == []


# --------------------------------------------------------------------------- #
# (b) les relevés de chaque résultat
# --------------------------------------------------------------------------- #
def test_chaque_resultat_rend_les_releves_de_sa_zone_des_deux_sortes(client, decor, db_path):
    t, z = _monter(client, decor, db_path)
    (bulle,) = [x for x in _chercher(client, q="VIENT")["results"]]
    lus = [(x["grille"], x["entree"], x["variante"], [q["libelle"] for q in x["qualificatifs"]])
           for x in bulle["releves"]]
    # La grille de travail d'abord, puis les autres par leur nom.
    assert lus == [("Travail en cours", "sentiment", "perte", []),
                   ("Travail en cours", "sentiment", "tristesse", []),
                   ("Signaux", "cri", None, []),
                   ("Signaux", "écho", None, ["objet"])], lus
    perte = bulle["releves"][0]
    assert perte["travail"] is True and perte["ouverte"] is True
    assert perte["porte"] == f"{t['grille_id']}/variante/sentiment/perte"
    cri = bulle["releves"][2]
    assert cri["travail"] is False and cri["ouverte"] is False
    assert cri["porte"] == f"{decor['grille_id']}/entree/cri"
    assert bulle["releves"][3]["qualificatifs"][0]["porte"] == (
        f"{decor['grille_id']}/qualificatif/sources/objet")
    # Rien de qui les a posés : la Recherche ne nomme personne.
    assert not {"auteur", "auteur_nom", "modifie_par"} & set(perte)
    # La case, sans texte ni note, se trouve par son étiquette et la rend.
    (case,) = _chercher(client, q="lieu")["results"]
    assert [(x["entree"], x["variante"]) for x in case["releves"]] == [("lieu", "forêt")]
    # Une zone sans relevé : une liste vide.
    sans = [x for x in _chercher(client, type="personnage")["results"]]
    assert sans and all(x["releves"] == [] for x in sans)


def test_qui_ne_lit_pas_l_album_n_en_voit_rien(client, decor, db_path):
    _monter(client, decor, db_path)
    assert _chercher(client, qui=ZOE, q="tristesse")["results"] == []
    assert _chercher(client, qui=ZOE, q="VIENT")["results"] == []
    # Filtrer par une grille qu'elle ne lit pas : introuvable (cf. plus bas).


# --------------------------------------------------------------------------- #
# (c) le filtre « porte… »
# --------------------------------------------------------------------------- #
def test_porte_une_entree_d_une_grille_ouverte_ou_fermee(client, decor, db_path):
    t, z = _monter(client, decor, db_path)
    g, s = t["grille_id"], decor["grille_id"]
    assert _ids(_chercher(client, porte=f"{g}/entree/sentiment")) == sorted(
        [z["bulle"], z["cartouche"]])
    assert _ids(_chercher(client, porte=f"{s}/entree/cri")) == [z["bulle"]]
    # « ou » entre les valeurs d'un même filtre.
    assert _ids(_chercher(client, porte=f"{s}/entree/cri/ton-de-voix")) == sorted(
        [z["bulle"], z["cartouche"]])


def test_porte_une_entree_et_ses_variantes(client, decor, db_path):
    t, z = _monter(client, decor, db_path)
    g, s = t["grille_id"], decor["grille_id"]
    assert _ids(_chercher(client, porte=f"{g}/variante/sentiment/perte")) == [z["bulle"]]
    assert _ids(_chercher(client, porte=f"{g}/variante/sentiment/perte/joie")) == sorted(
        [z["bulle"], z["cartouche"]])
    assert _ids(_chercher(client, porte=f"{s}/variante/ton-de-voix/chuchote")) == [
        z["cartouche"]]
    assert _chercher(client, porte=f"{s}/variante/ton-de-voix/crie")["results"] == []


def test_porte_une_rubrique_entiere_avec_ses_sous_rubriques(client, decor, db_path):
    """« sons » range « voix » (cri, ton de voix) et « bruits », qui range « chocs »
    (l'onomatopée) ; « provenance » range l'écho. Une rubrique se nomme par son identifiant
    d'étage."""
    t, z = _monter(client, decor, db_path)
    s = decor["grille_id"]
    assert _ids(_chercher(client, porte=f"{s}/rubrique/sons")) == sorted(
        [z["bulle"], z["cartouche"], z["texte"]])
    assert _ids(_chercher(client, porte=f"{s}/rubrique/chocs")) == [z["texte"]]
    assert _ids(_chercher(client, porte=f"{s}/rubrique/bruits")) == [z["texte"]]
    assert _ids(_chercher(client, porte=f"{s}/rubrique/chocs/voix")) == sorted(
        [z["bulle"], z["cartouche"], z["texte"]])
    assert _ids(_chercher(client, porte=f"{s}/rubrique/provenance")) == sorted(
        [z["bulle"], z["texte"]])


def test_porte_un_qualificatif(client, decor, db_path):
    t, z = _monter(client, decor, db_path)
    s = decor["grille_id"]
    assert _ids(_chercher(client, porte=f"{s}/qualificatif/sources/hors-champ")) == [z["texte"]]
    assert _ids(_chercher(client, porte=f"{s}/qualificatif/sources/hors-champ/objet")) == sorted(
        [z["bulle"], z["texte"]])
    assert _chercher(client, porte=f"{s}/qualificatif/manieres/taille")["results"] == []


def test_et_entre_deux_filtres_avec_le_texte_et_le_type(client, decor, db_path):
    t, z = _monter(client, decor, db_path)
    g, s = t["grille_id"], decor["grille_id"]
    assert _ids(_chercher(client, porte=[f"{g}/entree/sentiment", f"{s}/entree/cri"])) == [
        z["bulle"]]
    assert _ids(_chercher(client, porte=[f"{g}/entree/sentiment",
                                         f"{s}/variante/ton-de-voix/chuchote"])) == [
        z["cartouche"]]
    assert _ids(_chercher(client, q="PENDANT", porte=f"{g}/entree/sentiment")) == [
        z["cartouche"]]
    assert _ids(_chercher(client, type="bulle", porte=f"{g}/entree/sentiment")) == [z["bulle"]]


def test_une_entree_se_reconnait_par_sa_cle_quelle_que_soit_la_version(client, decor, db_path):
    """Une version 2 publiée de la grille fermée ; un relevé posé dans la version 1 et un autre
    rattaché à la version 2 (par SQL : deux versions sous une même grille, ce que la montée
    de version ne laisse jamais, n'en est que plus exigeant pour le filtre) : le filtre
    les trouve tous deux, par l'entrée comme par la rubrique."""
    t, z = _monter(client, decor, db_path)
    s = decor["grille_id"]
    r = client.patch(f"/api/grilles/{s}/entrees/cri", headers=ADMIN,
                     json={"definition": "un cri, version 2"})
    assert r.status_code == 200, r.text
    assert client.post(f"/api/grilles/{s}/versions/2/publication",
                       headers=ADMIN).status_code == 200
    v2 = _x(db_path, "SELECT id FROM grille_version WHERE grille_id = ? AND numero = 2", (s,))
    _x(db_path, "INSERT INTO releve (region_id, grille_id, version_id, entree_cle, une, auteur) "
                "VALUES (?, ?, ?, 'cri', 0, 'stag')", (z["case"], s, v2[0][0]))
    assert _ids(_chercher(client, porte=f"{s}/entree/cri")) == sorted([z["bulle"], z["case"]])
    assert z["case"] in _ids(_chercher(client, porte=f"{s}/rubrique/sons"))


def test_l_export_csv_porte_les_memes_lignes_sans_les_releves(client, decor, db_path):
    """L'export suit le filtre (le même cœur) ; il ne porte pas les relevés (tranche 4)."""
    t, z = _monter(client, decor, db_path)
    r = client.get("/api/recherche/export.csv", headers=ADMIN,
                   params={"porte": f"{t['grille_id']}/entree/sentiment"})
    assert r.status_code == 200, r.text
    lignes = list(csv.DictReader(io.StringIO(r.text.lstrip("﻿")), delimiter=";"))
    assert sorted(int(x["region_id"]) for x in lignes) == sorted([z["bulle"], z["cartouche"]])
    assert set(lignes[0]) == {"album", "planche", "citation", "region_id", "type", "ocr_texte",
                              "note"}
    assert "sentiment" not in r.text and "tristesse" not in r.text


def test_un_filtre_mal_forme_ou_une_grille_illisible(client, decor, db_path):
    t, z = _monter(client, decor, db_path)
    s = decor["grille_id"]
    for mauvais in ("cri", f"{s}/entree", f"{s}/variante/cri", f"{s}/mot/cri", "x/entree/cri",
                    f"{s}/qualificatif/sources"):
        r = _chercher(client, attendu=422, porte=mauvais)
        assert "porte" in r["detail"], (mauvais, r)
    # Une grille qu'on ne lit pas : introuvable, comme sa fiche.
    _chercher(client, qui=ZOE, attendu=404, porte=f"{s}/entree/cri")
    _chercher(client, attendu=404, porte="999999/entree/cri")
    # Le nom ne heurte pas les paramètres du vocabulaire d'hier, toujours refusés.
    assert client.get("/api/recherche", headers=STAG,
                      params={"tags": "x"}).status_code == 422
