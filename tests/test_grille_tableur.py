"""Le GABARIT d'une grille — tranché par Hugo sur maquette le 2026-11-03 (ANN-7).

Le bilan en DONNÉES ; les titres et les valeurs EN MOTS lus à côté des mots machine ;
l'identifiant d'une entrée FACULTATIF à la création ; la déclaration lue dans la feuille
« 1. La grille » ; le CLASSEUR `.xlsx` produit et relu sans danger ; et la grille OUVERTE qui
se réimporte, une entrée employée qui disparaît attendant « retirer » ou « fusionner dans… ».

La grille est FICTIVE (`tools/grille-modele.csv`), comme dans `test_grilles`. Chaque garde se
joue sous l'identité qu'elle concerne.
"""
import io
import json
import sqlite3
import zipfile

import openpyxl
import pytest

import grille_import
import grille_tableur
import grilles
from grilles_decor import (LEA, MODELE, MODELE_LISTES, SAM, STAG, ZOE, csv_de, flux, importer,
                           monter, ok)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

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


def _importer_classeur(client, projet_id, qui, data: bytes, attendu=(200,), **champs):
    """Un classeur envoyé SEUL — sa déclaration est dans sa feuille « 1. La grille »."""
    donnees = {k: (json.dumps(v) if isinstance(v, dict) else str(v).lower()
                   if isinstance(v, bool) else str(v)) for k, v in champs.items()}
    r = client.post(f"/api/projets/{projet_id}/grilles/import", headers=qui,
                    files={"fichier": ("grille.xlsx", data, XLSX)}, data=donnees)
    assert r.status_code in attendu, (r.status_code, r.text[:800])
    return r.json()


def _contenu_du_modele():
    return grille_import.lire(flux(MODELE), flux(MODELE_LISTES), porte_sur="mots")["contenu"]


def _classeur(contenu=None, **decl):
    c = contenu or _contenu_du_modele()
    return grille_tableur.ecrire_classeur(
        c, nom=decl.get("nom", "Signaux"), ouverte=decl.get("ouverte", False),
        porte_sur=decl.get("porte_sur", c["cible"]), note=decl.get("note"))


def _classeur_retouche(data: bytes, feuille: str, retouche) -> bytes:
    """Le classeur, une feuille retouchée par openpyxl (comme un tableur le ferait)."""
    wb = openpyxl.load_workbook(io.BytesIO(data))
    retouche(wb[feuille])
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()


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
    assert res["a_savoir"] == [] and res["a_repondre"] == []
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
    ws = openpyxl.load_workbook(io.BytesIO(r.content))["2. Les entrées"]
    titres = [c.value for c in ws[1]]
    ids = {ws.cell(row=n, column=titres.index("Identifiant") + 1).value
           for n in range(2, ws.max_row + 1)} - {None}
    assert ids == {"echo-lointain", "ton", "regard", "origine"}
    # Réimporté tel quel, il ne change rien, et ne dérive plus rien.
    res = _importer_classeur(client, decor["p"], LEA, r.content, grille_id=gid)
    assert res["aucun_changement"] and res["identifiants_deduits"] == []


# --------------------------------------------------------------------------- #
# 4. La déclaration se lit dans la feuille « 1. La grille »
# --------------------------------------------------------------------------- #
def test_la_declaration_se_lit_dans_la_feuille_la_grille(client, decor, db_path):
    data = _classeur(nom="Lue du classeur", ouverte=True, porte_sur="case")
    res = _importer_classeur(client, decor["p"], LEA, data)
    assert res["version"] == {"numero": 1, "etat": "vivante"}
    assert sorted(res["declaration"]["lus"]) == ["nom", "ouverte", "porte_sur"]
    (g,) = _q(db_path, "SELECT nom, ouverte FROM grille")
    assert g == {"nom": "Lue du classeur", "ouverte": 1}
    assert _q(db_path, "SELECT cible FROM grille_version")[0]["cible"] == "case"


def test_un_argument_l_emporte_sur_la_feuille_et_le_bilan_le_dit(client, decor, db_path):
    """Un argument DONNÉ l'emporte : on réimporte le classeur d'une grille sous un autre nom
    pour la dériver. Le bilan le dit, au lieu de changer en silence."""
    data = _classeur(nom="Lue du classeur", ouverte=True)
    res = _importer_classeur(client, decor["p"], LEA, data, ouverte=False,
                             porte_sur="planche", nom="Autre")
    assert sorted((a["code"], a["colonne"], a["fichier"]) for a in res["a_savoir"]) == [
        ("declaration_remplacee", "nom", "1. La grille"),
        ("declaration_remplacee", "ouverte", "1. La grille"),
        ("declaration_remplacee", "porte_sur", "1. La grille")]
    assert res["version"] == {"numero": 1, "etat": "brouillon"}
    assert _q(db_path, "SELECT nom, ouverte FROM grille") == [{"nom": "Autre", "ouverte": 0}]
    assert _q(db_path, "SELECT cible FROM grille_version")[0]["cible"] == "planche"


def test_une_feuille_qui_change_la_nature_d_une_grille_est_une_anomalie(client, decor):
    gid = importer(client, decor["p"], LEA, nom="Signaux")["grille_id"]
    res = _importer_classeur(client, decor["p"], LEA, _classeur(ouverte=True),
                             grille_id=gid, attendu=(422,))["detail"]
    assert [(a["code"], a["ligne"]) for a in res["anomalies"]] == [("nature_contredite", 5)]
    bizarre = _classeur_retouche(_classeur(), "1. La grille",
                                 lambda ws: ws.cell(row=5, column=2, value="à moitié"))
    res = _importer_classeur(client, decor["p"], LEA, bizarre, grille_id=gid,
                             attendu=(422,))["detail"]
    assert [a["code"] for a in res["anomalies"]] == ["nature_inconnue"]


def test_le_nom_d_une_version_suivante_ne_change_pas_par_le_classeur(client, decor, db_path):
    gid = importer(client, decor["p"], LEA, nom="Signaux")["grille_id"]
    res = _importer_classeur(client, decor["p"], LEA, _classeur(nom="Autre nom"),
                             grille_id=gid)
    assert res["aucun_changement"]
    assert [a["code"] for a in res["a_savoir"]] == ["nom_de_la_feuille"]
    assert _q(db_path, "SELECT nom FROM grille")[0]["nom"] == "Signaux"


# --------------------------------------------------------------------------- #
# 5. Le classeur se produit et se lit sans danger
# --------------------------------------------------------------------------- #
def test_le_classeur_porte_listes_aide_rouge_et_exemple(client, decor):
    gid = importer(client, decor["p"], LEA)["grille_id"]
    r = client.get(f"/api/grilles/{gid}/versions/1/tableur", headers=LEA)
    assert r.status_code == 200 and r.headers["content-type"] == XLSX
    assert "grille-" in r.headers["content-disposition"] and ".xlsx" in \
        r.headers["content-disposition"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["1. La grille", "2. Les entrées", "3. Listes à cocher",
                             "Exemple", "Choix"]
    assert wb["Choix"].sheet_state == "hidden"
    ws = wb["2. Les entrées"]
    titres = [c.value for c in ws[1]]
    assert titres[:6] == ["1. Rubrique", "Entrée", "Variante", "2. Se pose sur",
                          "3. Combien de fois", "4. Ce qu'on choisit"]
    assert all(c.comment is not None and c.comment.text for c in ws[1])      # l'aide
    validees = {str(r_).split(":")[0] for dv in ws.data_validations.dataValidation
                for r_ in dv.sqref.ranges}
    assert {"D2", "E2", "F2", "G2", "I2"} <= validees                         # déroulantes
    rouges = [str(cf.sqref) for cf in ws.conditional_formatting]
    assert any(x.startswith("F2:") for x in rouges)                           # la case fautive
    # En mots : « une variante », « bulle, cartouche ou texte hors bulle », « une seule ».
    valeurs = {c.value for ligne in ws.iter_rows(min_row=2) for c in ligne}
    assert {"une variante", "bulle, cartouche ou texte hors bulle", "une seule",
            "des cases d'une liste", "rien"} <= valeurs
    g = wb["1. La grille"]
    assert [(g.cell(row=n, column=1).value, g.cell(row=n, column=2).value)
            for n in range(4, 7)] == [("Nom de la grille", "Signaux"),
                                      ("Fermée ou ouverte", "fermée"),
                                      ("Porte d'ordinaire sur", "des mots")]


def test_le_classeur_se_lit_avec_le_plan_et_le_brouillon_reste_a_qui_gere(client, decor):
    gid = importer(client, decor["p"], LEA)["grille_id"]
    url = f"/api/grilles/{gid}/versions/1/tableur"
    ok(client.get(url, headers=LEA))
    ok(client.get(url, headers=SAM), 404)                       # un brouillon : pas pour lui
    ok(client.post(f"/api/grilles/{gid}/versions/1/publication", headers=LEA))
    assert ok(client.get(url, headers=SAM)).headers["content-type"] == XLSX
    ok(client.get(url, headers=ZOE), 404)                       # ne lit pas la grille
    ok(client.get(url + "?format=ods", headers=LEA), 422)


def test_le_classeur_se_reimporte_a_l_identique_ici_et_ailleurs(client, decor, db_path):
    gid = importer(client, decor["p"], LEA)["grille_id"]
    data = client.get(f"/api/grilles/{gid}/versions/1/tableur", headers=LEA).content
    assert _importer_classeur(client, decor["p"], LEA, data, grille_id=gid)[
        "aucun_changement"]
    res = _importer_classeur(client, decor["q"], ZOE, data, nom="Dérivée")
    assert res["ecrit"] and res["identifiants_deduits"] == []
    assert len({r["empreinte"] for r in _q(db_path, "SELECT empreinte FROM "
                                                    "grille_version")}) == 1


def test_une_cellule_qui_commence_par_egal_sort_en_texte(client, decor):
    formule = MODELE.replace("AAAH ! | OUILLE", "=SOMME(A1)").replace(
        "un cri poussé par un personnage", "+33 6 cri")
    gid = importer(client, decor["p"], LEA, entrees=formule)["grille_id"]
    data = client.get(f"/api/grilles/{gid}/versions/1/tableur", headers=LEA).content
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        feuilles = [n for n in z.namelist() if n.startswith("xl/worksheets/")]
        assert not any(b"<f>" in z.read(n) or b"<f " in z.read(n) for n in feuilles)
    ws = openpyxl.load_workbook(io.BytesIO(data))["2. Les entrées"]
    (cellule,) = [c for ligne in ws.iter_rows() for c in ligne if c.value == "=SOMME(A1)"]
    assert cellule.data_type == "s" and cellule.quotePrefix
    assert _importer_classeur(client, decor["p"], LEA, data, grille_id=gid)[
        "aucun_changement"]


def test_une_formule_recue_n_est_pas_evaluee_c_est_une_faute(client, decor, db_path):
    def retouche(ws):
        ws["B2"] = "=CONCATENER(\"c\";\"ri\")"
    data = _classeur_retouche(_classeur(), "2. Les entrées", retouche)
    res = _importer_classeur(client, decor["p"], LEA, data, attendu=(422,))["detail"]
    assert [(a["code"], a["fichier"], a["ligne"]) for a in res["anomalies"]] == [
        ("formule", "2. Les entrées", 2)]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille")[0]["n"] == 0


def test_un_nombre_ou_une_date_types_reviennent_en_texte_et_se_disent():
    import datetime

    def retouche(ws):
        ws["B2"] = 1789                       # un entier : en chiffres, sans rien dire
        ws["J2"] = 2.5                        # un nombre à virgule : en texte, et dit
        ws["M2"] = datetime.datetime(2026, 11, 3)
    tab = grille_tableur.lire_classeur(_classeur_retouche(_classeur(), "2. Les entrées",
                                                          retouche))
    lu = grille_import.lire_tableur(tab, porte_sur="mots")
    assert lu["anomalies"] == []
    e = lu["contenu"]["entrees"]["cri"]
    assert e["libelle"] == "1789" and e["definition"] == "2.5" and e["piege"] == "2026-11-03"
    assert sorted(a["code"] for a in lu["avertissements"]) == ["type_date", "type_nombre"]


def test_le_fichier_recu_est_borne(client, decor, monkeypatch):
    monkeypatch.setattr(grille_tableur, "TAILLE_MAX_RECUE", 1000)
    r = importer(client, decor["p"], LEA, attendu=(413,))
    assert "Mo" in r["detail"]


def _bombe(data: bytes, octets: int) -> bytes:
    """Le classeur, la feuille des entrées gonflée d'espaces — du XML valide qui se comprime
    en presque rien : ce qu'une bombe zip fait, à petite échelle."""
    sortie = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as z, \
            zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as w:
        for info in z.infolist():
            contenu = z.read(info.filename)
            if info.filename == "xl/worksheets/sheet2.xml":
                contenu = contenu.replace(b"</worksheet>", b" " * octets + b"</worksheet>")
            w.writestr(info.filename, contenu)
    return sortie.getvalue()


def test_un_classeur_trop_lourd_une_fois_deplie_est_refuse_avant_d_etre_ouvert(
        client, decor, monkeypatch):
    monkeypatch.setattr(grille_tableur, "TAILLE_MAX_DEPLIEE", 2 * 1024 * 1024)
    bombe = _bombe(_classeur(), 3 * 1024 * 1024)
    assert len(bombe) < grille_tableur.TAILLE_MAX_RECUE // 50
    with pytest.raises(grille_tableur.TropGros):
        grille_tableur.lire_classeur(bombe)
    r = _importer_classeur(client, decor["p"], LEA, bombe, attendu=(413,))
    assert "déplié" in r["detail"]
    # Sous la borne, le même classeur gonflé se lit : c'est bien la taille qui refuse.
    assert grille_tableur.lire_classeur(_bombe(_classeur(), 1024 * 1024))["entrees"]


def test_le_xml_se_lit_par_defusedxml(monkeypatch):
    """Une entité XML (le « milliard de rires ») est refusée : openpyxl lit par defusedxml.
    Sans defusedxml, on ne lit pas du tout."""
    assert openpyxl.DEFUSEDXML is True
    sortie = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(_classeur())) as z, \
            zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as w:
        for info in z.infolist():
            contenu = z.read(info.filename)
            if info.filename == "xl/workbook.xml":
                contenu = contenu.replace(
                    b"<workbook", b'<!DOCTYPE w [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
                                  b"<workbook", 1)
            w.writestr(info.filename, contenu)
    with pytest.raises(grille_tableur.FormatInvalide):
        grille_tableur.lire_classeur(sortie.getvalue())
    monkeypatch.setattr(openpyxl, "DEFUSEDXML", False)
    with pytest.raises(grille_tableur.FormatInvalide, match="defusedxml"):
        grille_tableur.lire_classeur(_classeur())


def test_ni_ods_ni_classeur_avec_un_second_fichier(client, decor):
    ods = io.BytesIO()
    with zipfile.ZipFile(ods, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        z.writestr("content.xml", "<office:document-content/>")
    r = _importer_classeur(client, decor["p"], LEA, ods.getvalue(), attendu=(400,))
    assert "xlsx" in r["detail"]
    r = client.post(f"/api/projets/{decor['p']}/grilles/import", headers=LEA,
                    files={"fichier": ("g.xlsx", _classeur(), XLSX),
                           "listes": ("l.csv", MODELE_LISTES.encode(), "text/csv")})
    assert r.status_code == 422 and "classeur" in r.json()["detail"]


# --------------------------------------------------------------------------- #
# 6. Réimporter une grille OUVERTE montre ce qui disparaît
# --------------------------------------------------------------------------- #
SANS_CRI = MODELE.replace(
    "cri;A. Sons > Voix;sons > voix;simple;cri;;;;un cri poussé par un personnage, écrit en "
    "toutes lettres;AAAH ! | OUILLE;un cri n'est pas une onomatopée de choc : on le pose sur "
    "le cri, pas sur le bruit;;;;;\r\n", "")
HURLEMENT = "hurlement;A. Sons > Voix;sons > voix;simple;hurlement;;;;un cri long;;;;;;;\r\n"


@pytest.fixture
def ouverte(client, decor):
    """Une grille OUVERTE, active, et un relevé de STAG sur « cri »."""
    gid = importer(client, decor["p"], LEA, ouverte=True, nom="Libre")["grille_id"]
    ok(client.put(f"/api/projets/{decor['p']}/grilles/{gid}/activation", headers=LEA,
                  json={"version": 1}))
    rel = ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": gid, "version": 1, "region_id": decor["zones"]["bulle"],
        "entree_cle": "cri", "mots": [8]}), 201)
    return {**decor, "grille_id": gid, "releve": rel["id"]}


def test_une_entree_employee_qui_disparait_attend_sa_reponse(client, ouverte, db_path):
    d = ouverte
    res = importer(client, d["p"], LEA, grille_id=d["grille_id"], entrees=SANS_CRI,
                   a_blanc=True)
    assert res["verdict"]["etat"] == "a_repondre"
    assert res["a_repondre"] == [{"cle": "cri", "libelle": "cri", "releves": 1,
                                  "choix": ["retirer", "fusionner"], "fusionner_dans": []}]
    assert [x["decision"] for x in res["bilan"]["disparus"] if x["quoi"] == "entree"] == [
        "a_repondre"]
    refus = importer(client, d["p"], LEA, grille_id=d["grille_id"], entrees=SANS_CRI,
                     attendu=(409,))["detail"]
    assert refus["verdict"]["etat"] == "a_repondre" and refus["a_repondre"][0]["cle"] == "cri"
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille_entree WHERE cle = 'cri'")[0]["n"] == 1
    assert _q(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table = 'grille' "
                       "AND type = 'modification'")[0]["n"] == 1      # l'import d'origine


def _importer_avec(client, d, entrees, reponses, attendu=(200,)):
    files = {"fichier": ("e.csv", entrees.encode("utf-8-sig"), "text/csv"),
             "listes": ("l.csv", MODELE_LISTES.encode("utf-8-sig"), "text/csv")}
    r = client.post(f"/api/projets/{d['p']}/grilles/import", headers=LEA, files=files,
                    data={"grille_id": str(d["grille_id"]), "reponses": json.dumps(reponses)})
    assert r.status_code in attendu, (r.status_code, r.text[:800])
    return r.json()


def test_retirer_garde_l_entree_et_ses_releves_a_revoir(client, ouverte, db_path):
    d = ouverte
    res = _importer_avec(client, d, SANS_CRI, {"cri": "retirer"})
    assert res["version"] == {"numero": 1, "etat": "vivante", "remplace": True}
    (e,) = _q(db_path, "SELECT retiree FROM grille_entree WHERE cle = 'cri'")
    assert e["retiree"] == 1
    (r,) = _q(db_path, "SELECT etat, entree_absente FROM releves_effectifs WHERE id = ?",
              (d["releve"],))
    assert r == {"etat": "a_revoir", "entree_absente": 1}
    # Elle ne se pose plus.
    ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": d["grille_id"], "version": 1, "region_id": d["zones"]["bulle"],
        "entree_cle": "cri", "mots": [7]}), 422)
    # Le même fichier ne redemande rien : l'entrée retirée le reste.
    assert importer(client, d["p"], LEA, grille_id=d["grille_id"], entrees=SANS_CRI)[
        "aucun_changement"]
    # Le classeur ne la porte plus ; réimporté, il la garde retirée.
    data = client.get(f"/api/grilles/{d['grille_id']}/versions/1/tableur", headers=LEA).content
    ws = openpyxl.load_workbook(io.BytesIO(data))["2. Les entrées"]
    assert "cri" not in {c.value for ligne in ws.iter_rows(min_row=2) for c in ligne}
    assert _importer_classeur(client, d["p"], LEA, data, grille_id=d["grille_id"])[
        "aucun_changement"]
    # La remettre dans le fichier la remet en usage : retirée, elle comptait dans l'empreinte.
    res = importer(client, d["p"], LEA, grille_id=d["grille_id"])
    assert res["ecrit"]
    assert _q(db_path, "SELECT retiree FROM grille_entree WHERE cle = 'cri'")[0]["retiree"] == 0


def test_fusionner_reporte_les_releves_et_se_trace(client, ouverte, db_path):
    d = ouverte
    avec = SANS_CRI + HURLEMENT
    res = _importer_avec(client, d, avec, {"cri": "regard-camera"}, attendu=(422,))
    assert "fusionner" in res["detail"]
    res = importer(client, d["p"], LEA, grille_id=d["grille_id"], entrees=avec, a_blanc=True)
    assert res["a_repondre"][0]["fusionner_dans"] == ["hurlement"]   # même forme, mêmes mots
    refus = _importer_avec(client, d, avec, {"cri": "fusionner:regard-camera"},
                           attendu=(409,))["detail"]
    assert [a["code"] for a in refus["anomalies"]] == ["fusion_impossible"]
    res = _importer_avec(client, d, avec, {"cri": "fusionner:hurlement"})
    assert res["ecrit"]
    assert [x["decision"] for x in res["bilan"]["disparus"] if x["quoi"] == "entree"] == [
        "fusionner:hurlement"]
    assert _q(db_path, "SELECT entree_cle FROM releve WHERE id = ?", (d["releve"],))[0][
        "entree_cle"] == "hurlement"
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille_entree WHERE cle = 'cri'")[0]["n"] == 0
    (ev,) = _q(db_path, "SELECT apres FROM evenement WHERE cible_table = 'grille' "
                        "ORDER BY id DESC LIMIT 1")
    assert json.loads(ev["apres"])["import"]["fusions"] == [
        {"de": "cri", "dans": "hurlement", "releve_ids": [d["releve"]]}]
    (r,) = _q(db_path, "SELECT etat FROM releves_effectifs WHERE id = ?", (d["releve"],))
    assert r["etat"] == "normal"


def test_une_entree_que_personne_n_emploie_part_sans_question(client, ouverte, db_path):
    d = ouverte
    sans = MODELE.replace("ambiance;D. Échanges;echanges;simple;ambiance sonore de la planche;"
                          ";;;le fond sonore de toute la planche;;;;;;planche;\r\n", "")
    res = importer(client, d["p"], LEA, grille_id=d["grille_id"], entrees=sans)
    assert res["ecrit"] and res["a_repondre"] == []
    assert [(x["cle"], x["decision"]) for x in res["bilan"]["disparus"]
            if x["quoi"] == "entree"] == [("ambiance", "part")]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille_entree WHERE cle = 'ambiance'")[0][
        "n"] == 0


def test_ce_qui_changerait_sous_des_releves_est_refuse(client, ouverte, db_path):
    d = ouverte
    forme = MODELE.replace(";sons > voix;simple;cri;", ";sons > voix;qualificatifs;cri;").replace(
        "pas sur le bruit;;", "pas sur le bruit;sources;")
    refus = importer(client, d["p"], LEA, grille_id=d["grille_id"], entrees=forme,
                     attendu=(409,))["detail"]
    assert [a["code"] for a in refus["anomalies"]] == ["change_sous_des_releves"] * 2
    reponse = _importer_avec(client, d, MODELE, {"echo": "retirer"}, attendu=(409,))
    assert [a["code"] for a in reponse["detail"]["anomalies"]] == ["reponse_sans_objet"]


def test_l_outil_demande_puis_retire(client, ouverte, db_path, data_dir, tmp_path):
    import os
    import subprocess
    import sys
    from grilles_decor import RACINE
    d = ouverte
    fichier = tmp_path / "sans-cri.csv"
    fichier.write_text(SANS_CRI, encoding="utf-8-sig", newline="")
    listes = tmp_path / "listes.csv"
    listes.write_text(MODELE_LISTES, encoding="utf-8-sig", newline="")
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir),
           "PYTHONIOENCODING": "utf-8"}
    base = [sys.executable, str(RACINE / "tools" / "importer_grille.py"), str(fichier),
            "--listes", str(listes), "--projet", str(d["p"]), "--grille", str(d["grille_id"])]
    p = subprocess.run(base, env=env, capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 1 and "--retirer cri" in p.stderr, p.stderr
    p = subprocess.run(base + ["--retirer", "cri"], env=env, capture_output=True, text=True,
                       encoding="utf-8")
    assert p.returncode == 0, p.stderr
    assert _q(db_path, "SELECT retiree FROM grille_entree WHERE cle = 'cri'")[0]["retiree"] == 1


def test_une_fusion_qui_doublerait_une_entree_posee_une_fois_est_refusee(client, ouverte,
                                                                          db_path):
    """« ton de voix » ne se pose qu'une fois par zone. Fusionner ses relevés dans une autre
    entrée « une seule fois » déjà posée sur la même zone en ferait deux : le bilan le dit,
    avant d'écrire, au lieu de tomber sur l'index de la cardinalité."""
    d = ouverte
    lignes = [l for l in MODELE.split("\r\n") if l.startswith("ton-de-voix;")]
    autre = "\r\n".join(l.replace("ton-de-voix;", "ton2;", 1).replace(
        ";ton de voix;", ";ton, autre;") for l in lignes) + "\r\n"
    sans = "\r\n".join(l for l in MODELE.split("\r\n")
                       if not l.startswith("ton-de-voix;")) + autre
    vid = _q(db_path, "SELECT id FROM grille_version")[0]["id"]
    c = sqlite3.connect(db_path)
    for cle_, v in (("ton-de-voix", "crie"), ("ton2", "chuchote")):
        c.execute("INSERT INTO releve (region_id, grille_id, version_id, entree_cle, "
                  "variante_cle, une) VALUES (?, ?, ?, ?, ?, 1)",
                  (d["zones"]["bulle"], d["grille_id"], vid, cle_, v))
    c.commit()
    c.close()
    refus = _importer_avec(client, d, sans, {"ton-de-voix": "fusionner:ton2"},
                           attendu=(409,))["detail"]
    assert [a["code"] for a in refus["anomalies"]] == ["fusion_en_double"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve WHERE entree_cle = 'ton-de-voix'")[
        0]["n"] == 1


def test_ctrl_z_ne_repose_pas_un_releve_sur_une_entree_retiree(client, ouverte, db_path):
    """Une entrée retirée ne se pose plus — pas même par Ctrl+Z : rétablir un relevé qu'on
    avait retiré la reposerait. L'acte est passé ; les relevés qui restent, restent."""
    d = ouverte
    second = ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": d["grille_id"], "version": 1, "region_id": d["zones"]["bulle"],
        "entree_cle": "cri", "mots": [7]}), 201)
    ok(client.delete(f"/api/releves/{second['id']}", headers=STAG), 204)
    _importer_avec(client, d, SANS_CRI, {"cri": "retirer"})
    refus = client.post("/api/undo", headers=STAG)
    assert refus.status_code == 409, refus.text[:300]
    assert "ne peut plus être rétabli" in refus.json()["detail"]["message"]
    assert [r["id"] for r in _q(db_path, "SELECT id FROM releve")] == [d["releve"]]


def test_une_entree_nee_en_posant_puis_retiree_ne_renait_pas_en_posant(client, ouverte,
                                                                        db_path):
    """Une entrée née EN POSANT que le fichier ne porte pas est une entrée employée qui
    disparaît : retirée, la reposer par son nom est refusé, au lieu de la rendre en silence."""
    d = ouverte
    corps = {"grille_id": d["grille_id"], "version": 1, "region_id": d["zones"]["bulle"],
             "mots": [0],
             "nouvelle_entree": {"libelle": "souffle"}}
    ok(client.post("/api/releves", headers=STAG, json=corps), 201)
    res = importer(client, d["p"], LEA, grille_id=d["grille_id"], a_blanc=True)
    assert [a["cle"] for a in res["a_repondre"]] == ["souffle"]
    _importer_avec(client, d, MODELE, {"souffle": "retirer"})
    r = client.post("/api/releves", headers=STAG, json=corps)
    assert r.status_code == 422 and "retirée" in r.json()["detail"], r.text[:300]
