"""Le GABARIT d'une grille — tranché par Hugo sur maquette le 2026-11-03 (ANN-7).

Le bilan en DONNÉES ; les titres et les valeurs EN MOTS lus à côté des mots machine ;
l'identifiant d'une entrée FACULTATIF à la création.

La grille est FICTIVE (`tools/grille-modele.csv`), comme dans `test_grilles`. Chaque garde se
joue sous l'identité qu'elle concerne.
"""
import io
import sqlite3
import zipfile

import pytest

import grille_import
import grilles
from grilles_decor import LEA, MODELE, flux, importer, monter

# Le gabarit EN MOTS : les questions pour titres, les réponses en mots, une ligne de
# variante sans identifiant sous son entrée, des commentaires `#`.
EN_MOTS = (
    "# Une grille écrite à la main, sans identifiant\r\n"
    "1. Rubrique;Entrée;Variante;2. Se pose sur;3. Combien de fois;4. Ce qu'on choisit;"
    "Liste à cocher;5. Champ à écrire;6. Autre zone;Définition;Exemples;Piège;Identifiant\r\n"
    "# 4 : rien, une variante, des cases d'une liste\r\n"
    "Sons > Voix;Écho lointain;;;;rien;;;;un son répété;\"OH…\nOH…\";;\r\n"
    "Sons > Voix;ton;;bulle, cartouche ou texte hors bulle;une seule;une variante;;;;;;;\r\n"
    ";;chuchoté;;;;;;;à voix basse;;;\r\n"
    ";;crié;;;;;;;à pleine voix;;;\r\n"
    "Image;regard;;la case;;rien;;;oui;;;;\r\n"
    "Image;origine;;;;des cases d'une liste;Sources du son;lieu;;;;;\r\n")
LISTES_EN_MOTS = ("Liste;Case;Définition (au survol)\r\n"
                  "Sources du son;dans le champ;\r\n"
                  "Sources du son;hors champ;le son vient d'ailleurs\r\n")


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
# 1. Le bilan est en DONNÉES
# --------------------------------------------------------------------------- #
def test_une_anomalie_est_une_donnee_qui_dit_ou_quoi_et_que_faire():
    entete = "cle;forme;libelle\r\n"
    lu = grille_import.lire(flux(entete + "a;libre;a\r\n"), None, porte_sur="mots")
    (a,) = lu["anomalies"]
    assert a == {"code": "forme_inconnue", "fichier": "entrées", "ligne": 2, "cle": "a",
                 "colonne": "forme", "question": "4. Ce qu'on choisit",
                 "probleme": a["probleme"], "a_faire": a["a_faire"]}
    assert "libre" in a["probleme"] and "une variante" in a["a_faire"]
    texte = grille_import.en_mots(a)
    assert texte.startswith("entrées, ligne 2 · « a » · 4. Ce qu'on choisit : ")
    assert " → répondez" in texte


def test_un_refus_rend_le_verdict_les_fautes_et_a_savoir(client, decor, db_path):
    mauvais = MODELE + "orpheline;;;;;v;v;;;;;;;;;\r\n"
    res = importer(client, decor["p"], LEA, entrees=mauvais, attendu=(422,))["detail"]
    assert res["verdict"]["etat"] == "refuse" and res["verdict"]["n"] == 1
    (a,) = res["anomalies"]
    assert a["code"] == "variante_entree_inconnue" and a["fichier"] == \
        "grille-rubriques-entrees.csv" and a["ligne"] == 17 and a["cle"] == "orpheline"
    assert res["a_savoir"] == []
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille")[0]["n"] == 0


def test_le_bilan_a_blanc_dit_son_verdict_et_ce_qui_va_naitre(client, decor):
    res = importer(client, decor["p"], LEA, a_blanc=True)
    assert res["verdict"]["etat"] == "importable"
    assert res["va_naitre"] == {"rubriques": 8, "entrees": 10, "variantes": 5, "listes": 2,
                                "qualificatifs": 6}
    assert res["a_savoir"] == []
    assert res["declaration"]["nom"] == "Signaux" and res["declaration"]["porte_sur"] == "mots"


# --------------------------------------------------------------------------- #
# 2. Les titres et les valeurs en mots
# --------------------------------------------------------------------------- #
def test_le_gabarit_en_mots_se_lit_comme_les_mots_machine():
    lu = grille_import.lire(flux(EN_MOTS), flux(LISTES_EN_MOTS), porte_sur="la case")
    assert lu["anomalies"] == [], [grille_import.en_mots(a) for a in lu["anomalies"]]
    c = lu["contenu"]
    assert c["cible"] == "case"
    e = c["entrees"]
    assert set(e) == {"echo-lointain", "ton", "regard", "origine"}
    assert e["echo-lointain"]["forme"] == "simple"
    assert e["echo-lointain"]["exemples"] == ["OH…", "OH…"]       # un par ligne de cellule
    assert e["ton"]["forme"] == "variantes" and e["ton"]["cardinalite"] == "une"
    assert e["ton"]["cible"] == "bulle|cartouche|texte"
    # Les lignes de variante sans identifiant appartiennent à l'entrée du DESSUS.
    assert [(k, v["libelle"]) for k, v in e["ton"]["variantes"].items()] == [
        ("chuchote", "chuchoté"), ("crie", "crié")]
    assert e["regard"]["cible"] == "case" and e["regard"]["lien"] is True
    assert e["origine"]["forme"] == "qualificatifs" and e["origine"]["precision"] == "lieu"
    # La liste nommée par son NOM reçoit un identifiant ; ses cases aussi.
    assert e["origine"]["liste_cle"] == "sources-du-son"
    assert set(c["listes"]["sources-du-son"]["qualificatifs"]) == {"dans-le-champ",
                                                                    "hors-champ"}
    assert grilles.chemin_de_rubrique(c["rubriques"], e["ton"]["rubrique_cle"]) == [
        "sons", "voix"]


def test_les_lignes_diese_sont_ignorees_partout():
    texte = "# avant l'en-tête\r\ncle;forme;libelle\r\n# entre deux\r\na;simple;a\r\n#b;x;y\r\n"
    lu = grille_import.lire(flux(texte), None, porte_sur="mots")
    assert lu["anomalies"] == [] and list(lu["contenu"]["entrees"]) == ["a"]


def test_une_valeur_en_mots_inconnue_se_dit_dans_la_question():
    texte = "Entrée;4. Ce qu'on choisit;2. Se pose sur\r\na;parfois;\r\nb;rien;des mots, la case\r\n"
    lu = grille_import.lire(flux(texte), None, porte_sur="mots")
    assert [(a["code"], a["question"]) for a in lu["anomalies"]] == [
        ("forme_inconnue", "4. Ce qu'on choisit"), ("cible_inconnue", "2. Se pose sur")]


# --------------------------------------------------------------------------- #
# 3. L'identifiant d'une entrée est facultatif à la création
# --------------------------------------------------------------------------- #
def test_un_identifiant_manquant_se_derive_du_nom_sans_collision():
    texte = ("cle;forme;libelle\r\n"
             ";simple;Écho lointain\r\n"
             ";simple;écho  LOINTAIN\r\n"         # même dérivation : suffixé
             "echo-lointain-2;simple;pris\r\n"     # un identifiant ÉCRIT n'est jamais pris
             ";simple;cœur\r\n"
             ";simple;!!!\r\n")
    lu = grille_import.lire(flux(texte), None, porte_sur="mots")
    assert lu["anomalies"] == []
    assert list(lu["contenu"]["entrees"]) == ["echo-lointain", "echo-lointain-3",
                                              "echo-lointain-2", "coeur", "entree"]
    assert [a["code"] for a in lu["avertissements"]] == ["identifiants_deduits"]
    assert [(d["ligne"], d["cle"], d["repris"]) for d in lu["identifiants_deduits"]] == [
        (2, "echo-lointain", False), (3, "echo-lointain-3", False), (5, "coeur", False),
        (6, "entree", False)]


def test_un_identifiant_manquant_reprend_celui_de_l_objet_de_meme_nom():
    """Dans un réimport, un fichier écrit à la main garde les identifiants de la version à
    laquelle on compare : même nom, même identifiant — sinon un fichier sans identifiants
    ferait disparaître et renaître chaque entrée. Un nouveau nom ne prend jamais l'identifiant
    d'un autre."""
    reference = grille_import.lire(flux(EN_MOTS), flux(LISTES_EN_MOTS),
                                   porte_sur="la case")["contenu"]
    renomme = {**reference["entrees"]["regard"], "rang": 9}
    reference["entrees"] = {"regarde-camera": renomme,
                            **{k: v for k, v in reference["entrees"].items() if k != "regard"}}
    relu = grille_import.lire(flux(EN_MOTS), flux(LISTES_EN_MOTS), porte_sur="la case",
                              reference=reference)
    assert relu["anomalies"] == []
    assert set(relu["contenu"]["entrees"]) == {"echo-lointain", "ton", "regarde-camera",
                                               "origine"}
    assert all(d["repris"] for d in relu["identifiants_deduits"])
    neuf = EN_MOTS.replace(";regard;", ";regard sur nous;")
    relu = grille_import.lire(flux(neuf), flux(LISTES_EN_MOTS), porte_sur="la case",
                              reference=reference)
    assert "regard-sur-nous" in relu["contenu"]["entrees"]


def test_le_reexport_rend_les_identifiants_derives(client, decor, db_path):
    res = importer(client, decor["p"], LEA, entrees=EN_MOTS, listes=LISTES_EN_MOTS,
                   porte_sur="la case")
    gid = res["grille_id"]
    assert {d["cle"] for d in res["identifiants_deduits"] if d["quoi"] == "entree"} == {
        "echo-lointain", "ton", "regard", "origine"}
    r = client.get(f"/api/grilles/{gid}/versions/1/tableur", headers=LEA)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        entrees = z.read("grille-rubriques-entrees.csv").decode("utf-8-sig")
        listes = z.read("grille-listes-qualificatifs.csv").decode("utf-8-sig")
    assert {l.split(";")[0] for l in entrees.splitlines()[1:]} == {
        "echo-lointain", "ton", "regard", "origine"}
    # Réimporté tel quel, il ne change rien, et ne dérive plus rien.
    res = importer(client, decor["p"], LEA, grille_id=gid, entrees=entrees, listes=listes,
                   porte_sur=None)
    assert res["aucun_changement"] and res["identifiants_deduits"] == []
