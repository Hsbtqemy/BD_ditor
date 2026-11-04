"""Une grille s'écrit SANS IMPORT — les routes du formulaire (ANN-7 ; l'option HYBRIDE,
tranchée par Hugo sur maquette le 2026-11-03).

Chaque route est jouée sous l'identité qu'elle concerne : la responsable du projet fait ; un
simple membre et une lectrice reçoivent un 403 nommé quand ils lisent la grille, un 404 quand
ils ne la lisent pas. Une grille fermée s'écrit dans son brouillon (la version publiée ne
bouge pas), une ouverte en place ; une valeur vue périmée reçoit le 409 de CONC-3 ; une entrée
employée ne se supprime jamais — retirer et fusionner font ce que fait le réimport ; tout
s'écrit au journal sous `grille`. La grille est FICTIVE (`tools/grille-modele.csv`).
"""
import io
import json
import sqlite3
import zipfile

import pytest

from conftest import ADMIN
from grilles_decor import (ANA, LEA, MODELE, MODELE_LISTES, SAM, STAG, ZOE, grille_active,
                           importer, monter, ok)


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


def _n(db_path, sql, p=()):
    return list(_q(db_path, sql, p)[0].values())[0]


def _actes(db_path, depuis=0):
    return [{**r, "avant": json.loads(r["avant"]) if r["avant"] else None,
             "apres": json.loads(r["apres"]) if r["apres"] else None}
            for r in _q(db_path, "SELECT id, type, agent, avant, apres FROM evenement "
                                 "WHERE cible_table = 'grille' AND id > ? ORDER BY id",
                        (depuis,))]


def _dernier_acte(db_path):
    return _n(db_path, "SELECT COALESCE(MAX(id), 0) FROM evenement")


def _codes(r):
    return [a["code"] for a in r.json()["detail"]["anomalies"]]


def _entree(plan, cle):
    return next(e for e in plan["entrees"] if e["cle"] == cle)


# --------------------------------------------------------------------------- #
# Construire une grille au formulaire, de rien
# --------------------------------------------------------------------------- #
def test_une_grille_se_construit_sans_import_et_se_reexporte_a_l_identique(client, decor,
                                                                           db_path):
    """Créer une grille fermée (vide, son brouillon 1), y ranger une rubrique, des entrées des
    trois formes, une liste et ses cases — les identifiants reçus du nom —, la publier ; son
    tableur réexporté se réimporte SANS CHANGEMENT : ce que le formulaire écrit, le tableur le
    porte."""
    p = decor["p"]
    g = ok(client.post(f"/api/projets/{p}/grilles", headers=LEA,
                       json={"nom": "Lieux", "porte_sur": "la case"}), 201)
    gid = g["grille_id"]
    assert g["version"] == {"numero": 1, "etat": "brouillon"}
    assert g["plan"]["porte_sur"] == ["case"] and g["plan"]["entrees"] == []
    # Une grille vide ne se publie pas.
    r = client.post(f"/api/grilles/{gid}/versions/1/publication", headers=LEA)
    assert r.status_code == 409 and "aucune entrée" in r.json()["detail"]
    r = ok(client.post(f"/api/grilles/{gid}/rubriques", headers=LEA,
                       json={"libelle": "Intérieur"}), 201)
    assert r["cle"] == "interieur"
    sous = ok(client.post(f"/api/grilles/{gid}/rubriques", headers=LEA,
                          json={"libelle": "Pièces", "parent_cle": "interieur"}), 201)["cle"]
    assert sous == "pieces"
    r = ok(client.post(f"/api/grilles/{gid}/entrees", headers=LEA,
                       json={"libelle": "Écho lointain", "rubrique_cle": sous,
                             "definition": "un lieu qu'on entend", "exemples": ["OH…", "AH"]}),
           201)
    assert r["cle"] == "echo-lointain" and r["version"]["etat"] == "brouillon"
    deux = ok(client.post(f"/api/grilles/{gid}/entrees", headers=LEA,
                          json={"libelle": "Écho lointain"}), 201)
    assert deux["cle"] == "echo-lointain-2"
    liste = ok(client.post(f"/api/grilles/{gid}/listes", headers=LEA,
                           json={"libelle": "Moment", "cases": [{"libelle": "jour"},
                                                                {"libelle": "nuit"}]}), 201)
    assert liste["cle"] == "moment"
    ok(client.post(f"/api/grilles/{gid}/entrees", headers=LEA, json={
        "libelle": "rue", "forme": "des cases d'une liste", "liste_cle": "moment"}), 201)
    ok(client.post(f"/api/grilles/{gid}/entrees", headers=LEA, json={
        "libelle": "porte", "forme": "variantes", "cible": ["bulle", "cartouche"],
        "cardinalite": "une seule", "lien": True, "precision": "laquelle",
        "variantes": [{"libelle": "ouverte"}, {"libelle": "fermée", "exemples": ["CLAC"]}]}),
        201)
    plan = ok(client.get(f"/api/grilles/{gid}/versions/1", headers=LEA))
    porte = _entree(plan, "porte")
    assert porte["cibles"] == ["bulle", "cartouche"] and porte["cardinalite"] == "une"
    assert [x["cle"] for x in porte["variantes"]] == ["ouverte", "fermee"]
    assert _entree(plan, "echo-lointain")["rubriques"] == ["interieur", "pieces"]
    ok(client.post(f"/api/grilles/{gid}/versions/1/publication", headers=LEA))
    # Le tableur, réexporté et réimporté : rien ne change.
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/grilles/{gid}/versions/1/tableur",
                                              params={"format": "csv"}, headers=LEA).content))
    entrees, listes = (z.read(n).decode("utf-8-sig") for n in z.namelist())
    res = importer(client, p, LEA, grille_id=gid, entrees=entrees, listes=listes,
                   porte_sur=None)
    assert res["aucun_changement"], res["bilan"]


def test_creer_une_grille_porte_les_refus_de_l_import(client, decor, db_path):
    p = decor["p"]
    importer(client, p, LEA, nom="Signaux")
    r = client.post(f"/api/projets/{p}/grilles", headers=LEA,
                    json={"nom": "  signaux ", "porte_sur": "mots"})
    assert r.status_code == 409 and "s'appelle déjà" in r.json()["detail"]
    r = client.post(f"/api/projets/{p}/grilles", headers=LEA, json={"nom": "Autre"})
    assert r.status_code == 422 and _codes(r) == ["porte_sur_manque"]
    r = client.post(f"/api/projets/{p}/grilles", headers=LEA,
                    json={"nom": "Autre", "porte_sur": "mots | case"})
    assert r.status_code == 422 and _codes(r) == ["porte_sur_inconnu"]
    assert _n(db_path, "SELECT COUNT(*) FROM grille") == 1


def test_une_grille_ouverte_nait_vivante(client, decor, db_path):
    g = ok(client.post(f"/api/projets/{decor['p']}/grilles", headers=LEA,
                       json={"nom": "Libre", "ouverte": True, "porte_sur": ["mots"]}), 201)
    assert g["version"] == {"numero": 1, "etat": "vivante"}
    ok(client.put(f"/api/projets/{decor['p']}/grilles/{g['grille_id']}/activation",
                  headers=LEA, json={"version": 1}))
    r = ok(client.post(f"/api/grilles/{g['grille_id']}/entrees", headers=LEA,
                       json={"libelle": "souffle"}), 201)
    assert r["version"] == {"numero": 1, "etat": "vivante"} and not r["brouillon_cree"]
    assert _n(db_path, "SELECT COUNT(*) FROM grille_version") == 1


# --------------------------------------------------------------------------- #
# Où l'on écrit : le brouillon d'une fermée, en place pour une ouverte
# --------------------------------------------------------------------------- #
def test_une_grille_fermee_s_ecrit_dans_un_brouillon_ne_de_sa_version_publiee(client, decor,
                                                                              db_path):
    g = grille_active(client, decor["p"])
    gid = g["grille_id"]
    depuis = _dernier_acte(db_path)
    r = ok(client.patch(f"/api/grilles/{gid}/entrees/cri", headers=LEA,
                        json={"definition": "un cri, écrit en toutes lettres"}))
    assert r["version"] == {"numero": 2, "etat": "brouillon"} and r["brouillon_cree"]
    assert _entree(r["plan"], "cri")["definition"] == "un cri, écrit en toutes lettres"
    # La version publiée ne bouge pas, et reste active.
    assert _q(db_path, "SELECT e.definition FROM grille_entree e JOIN grille_version v "
                       "ON v.id = e.version_id WHERE v.numero = 1 AND e.cle = 'cri'")[0][
        "definition"] == "un cri poussé par un personnage, écrit en toutes lettres"
    assert ok(client.get(f"/api/grilles/{gid}", headers=LEA))["active"] == {
        "numero": 1, "etat": "publiee"}
    # Le brouillon est la copie entière de la version publiée.
    assert _n(db_path, "SELECT COUNT(*) FROM grille_entree e JOIN grille_version v ON "
                       "v.id = e.version_id WHERE v.numero = 2") == _n(
        db_path, "SELECT COUNT(*) FROM grille_entree e JOIN grille_version v ON "
                 "v.id = e.version_id WHERE v.numero = 1")
    actes = _actes(db_path, depuis)
    assert actes[0]["type"] == "creation" and actes[0]["apres"] == {
        "brouillon": {"numero": 2, "depuis": 1}}
    assert actes[1]["apres"] == {"objet": "entree:cri", "version": 2,
                                 "definition": "un cri, écrit en toutes lettres"}
    assert actes[1]["agent"] == "lea"
    # Le geste suivant écrit dans le même brouillon.
    r = ok(client.patch(f"/api/grilles/{gid}/entrees/cri", headers=LEA,
                        json={"piege": "pas un bruit"}))
    assert r["version"]["numero"] == 2 and not r["brouillon_cree"]
    assert _n(db_path, "SELECT COUNT(*) FROM grille_version") == 2
    # L'empreinte du brouillon est celle de ce qu'il porte.
    import grilles
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    c.create_function("cle_tag", 1, lambda x: x)
    vid = c.execute("SELECT id, empreinte FROM grille_version WHERE numero = 2").fetchone()
    assert vid["empreinte"] == grilles.empreinte(grilles.contenu(c, vid["id"]))
    c.close()


def test_un_geste_qui_ne_change_rien_ne_fait_pas_naitre_de_brouillon(client, decor, db_path):
    g = grille_active(client, decor["p"])
    depuis = _dernier_acte(db_path)
    r = ok(client.patch(f"/api/grilles/{g['grille_id']}/entrees/cri", headers=LEA,
                        json={"libelle": "cri"}))
    assert r["version"] == {"numero": 1, "etat": "publiee"} and not r["brouillon_cree"]
    assert _n(db_path, "SELECT COUNT(*) FROM grille_version") == 1
    assert _actes(db_path, depuis) == []


def test_un_refus_ne_laisse_pas_de_brouillon(client, decor, db_path):
    g = grille_active(client, decor["p"])
    r = client.patch(f"/api/grilles/{g['grille_id']}/entrees/cri", headers=LEA,
                     json={"forme": "variantes"})
    assert r.status_code == 422 and _codes(r) == ["variantes_absentes"]
    assert _n(db_path, "SELECT COUNT(*) FROM grille_version") == 1


def test_renommer_une_grille_ne_fait_pas_naitre_de_version(client, decor, db_path):
    g = grille_active(client, decor["p"])
    gid = g["grille_id"]
    importer(client, decor["p"], LEA, nom="Autre")
    r = client.patch(f"/api/grilles/{gid}", headers=LEA, json={"nom": "autre"})
    assert r.status_code == 409 and "s'appelle déjà" in r.json()["detail"]
    r = ok(client.patch(f"/api/grilles/{gid}", headers=LEA,
                        json={"nom": "Signaux sonores", "vu": {"nom": "Signaux"}}))
    assert r["version"]["numero"] == 1
    assert ok(client.get(f"/api/grilles/{gid}", headers=LEA))["nom"] == "Signaux sonores"
    assert _n(db_path, "SELECT COUNT(*) FROM grille_version WHERE grille_id = ?", (gid,)) == 1
    # La nature ne change pas : le corps la refuse.
    assert client.patch(f"/api/grilles/{gid}", headers=LEA,
                        json={"ouverte": True}).status_code == 422
    # « Porte sur » et la note, eux, s'écrivent dans le brouillon.
    r = ok(client.patch(f"/api/grilles/{gid}", headers=LEA,
                        json={"porte_sur": "bulle | cartouche | texte", "note": "élargie"}))
    assert r["version"] == {"numero": 2, "etat": "brouillon"}
    assert r["plan"]["porte_sur"] == ["bulle", "cartouche", "texte"]
    assert r["plan"]["note"] == "élargie"


def test_une_grille_retiree_ne_s_ecrit_plus(client, decor):
    gid = importer(client, decor["p"], LEA)["grille_id"]
    ok(client.post(f"/api/grilles/{gid}/versions/1/publication", headers=LEA))
    ok(client.post(f"/api/grilles/{gid}/retrait", headers=LEA))
    r = client.patch(f"/api/grilles/{gid}/entrees/cri", headers=LEA, json={"piege": "x"})
    assert r.status_code == 409 and "retirée" in r.json()["detail"]


# --------------------------------------------------------------------------- #
# Qui écrit
# --------------------------------------------------------------------------- #
GESTES = [
    ("post", "/api/grilles/{g}/rubriques", {"libelle": "R"}),
    ("patch", "/api/grilles/{g}/rubriques/provenance", {"libelle": "R"}),
    ("delete", "/api/grilles/{g}/rubriques/provenance", None),
    ("post", "/api/grilles/{g}/entrees", {"libelle": "E"}),
    ("patch", "/api/grilles/{g}/entrees/cri", {"piege": "x"}),
    ("delete", "/api/grilles/{g}/entrees/ambiance", None),
    ("post", "/api/grilles/{g}/entrees/cri/retrait", None),
    ("delete", "/api/grilles/{g}/entrees/cri/retrait", None),
    ("post", "/api/grilles/{g}/entrees/cri/fusion", {"dans": "echo"}),
    ("post", "/api/grilles/{g}/entrees/onomatopee/variantes", {"libelle": "V"}),
    ("patch", "/api/grilles/{g}/entrees/onomatopee/variantes/bang", {"libelle": "V"}),
    ("delete", "/api/grilles/{g}/entrees/onomatopee/variantes/crac", None),
    ("post", "/api/grilles/{g}/listes", {"libelle": "L"}),
    ("patch", "/api/grilles/{g}/listes/sources", {"libelle": "L"}),
    ("delete", "/api/grilles/{g}/listes/sources", None),
    ("post", "/api/grilles/{g}/listes/sources/cases", {"libelle": "C"}),
    ("patch", "/api/grilles/{g}/listes/sources/cases/objet", {"libelle": "C"}),
    ("delete", "/api/grilles/{g}/listes/sources/cases/objet", None),
    ("patch", "/api/grilles/{g}", {"note": "n"}),
]


def _jouer(client, methode, chemin, corps, qui, gid):
    url = chemin.format(g=gid)
    if corps is None:
        return getattr(client, methode)(url, headers=qui)
    return client.request(methode.upper(), url, headers=qui, json=corps)


@pytest.mark.parametrize("methode,chemin,corps", GESTES)
def test_seul_qui_gere_le_projet_ecrit(client, decor, db_path, methode, chemin, corps):
    """Une grille active (lue par le membre et la lectrice) : 403 nommé ; un brouillon seul
    (qu'ils ne lisent pas) : 404 ; un responsable d'un autre projet : 404. Rien n'est écrit."""
    active = grille_active(client, decor["p"])["grille_id"]
    brouillon = importer(client, decor["p"], LEA, nom="En chantier")["grille_id"]
    avant = _n(db_path, "SELECT COUNT(*) FROM evenement WHERE cible_table = 'grille'")
    for qui in (SAM, ANA):
        r = _jouer(client, methode, chemin, corps, qui, active)
        assert r.status_code == 403 and "responsables" in r.json()["detail"], (qui, r.text)
        assert _jouer(client, methode, chemin, corps, qui, brouillon).status_code == 404
    assert _jouer(client, methode, chemin, corps, ZOE, active).status_code == 404
    assert _n(db_path, "SELECT COUNT(*) FROM evenement WHERE cible_table = 'grille'") == avant
    assert _n(db_path, "SELECT COUNT(*) FROM grille_version") == 2


def test_creer_une_grille_est_un_geste_de_responsable(client, decor):
    corps = {"nom": "N", "porte_sur": "mots"}
    assert client.post(f"/api/projets/{decor['p']}/grilles", headers=SAM,
                       json=corps).status_code == 403
    assert client.post(f"/api/projets/{decor['p']}/grilles", headers=ZOE,
                       json=corps).status_code == 404
    ok(client.post(f"/api/projets/{decor['p']}/grilles", headers=ADMIN, json=corps), 201)


# --------------------------------------------------------------------------- #
# La valeur vue (CONC-3)
# --------------------------------------------------------------------------- #
def test_une_valeur_vue_perimee_est_refusee_et_nomme_qui_l_a_changee(client, decor, db_path):
    g = grille_active(client, decor["p"], ouverte=True, nom="Libre")
    gid = g["grille_id"]
    vue = "un cri poussé par un personnage, écrit en toutes lettres"
    ok(client.patch(f"/api/grilles/{gid}/entrees/cri", headers=ADMIN,
                    json={"definition": "un cri", "vu": {"definition": vue}}))
    r = client.patch(f"/api/grilles/{gid}/entrees/cri", headers=LEA,
                     json={"definition": "un hurlement", "vu": {"definition": vue}})
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert d["conflit"]["champ"] == "definition" and d["conflit"]["valeur_actuelle"] == "un cri"
    assert d["conflit"]["auteur"]["login"] == "decor"
    assert "la définition a été modifiée" in d["message"]
    # La même chose sur une variante, une rubrique, une liste, une case.
    for url, champ, ancien in (
            (f"/api/grilles/{gid}/entrees/onomatopee/variantes/bang", "libelle", "bang"),
            (f"/api/grilles/{gid}/rubriques/provenance", "libelle", "B. Provenance"),
            (f"/api/grilles/{gid}/listes/sources", "libelle", "source du son"),
            (f"/api/grilles/{gid}/listes/sources/cases/objet", "libelle", "objet")):
        ok(client.patch(url, headers=ADMIN, json={champ: "autre"}))
        r = client.patch(url, headers=LEA, json={champ: "mien", "vu": {champ: ancien}})
        assert r.status_code == 409 and r.json()["detail"]["conflit"]["auteur"][
            "login"] == "decor", (url, r.text)
        # Sans valeur vue, le dernier gagne (Q8).
        ok(client.patch(url, headers=LEA, json={champ: "mien"}))
    # Une valeur vue qui n'est pas un champ de l'objet : 422.
    assert client.patch(f"/api/grilles/{gid}/entrees/cri", headers=LEA,
                        json={"piege": "x", "vu": {"nom": "y"}}).status_code == 422


def test_une_valeur_vue_juste_passe(client, decor):
    g = grille_active(client, decor["p"])
    r = ok(client.patch(f"/api/grilles/{g['grille_id']}/entrees/ton-de-voix", headers=LEA,
                        json={"cible": ["bulle"], "vu": {"cible": "bulle | cartouche | texte"}}))
    assert _entree(r["plan"], "ton-de-voix")["cibles"] == ["bulle"]


# --------------------------------------------------------------------------- #
# Les refus de l'import
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("corps,code", [
    ({"libelle": "x", "forme": "variantes"}, "variantes_absentes"),
    ({"libelle": "x", "forme": "qualificatifs"}, "liste_manque"),
    ({"libelle": "x", "forme": "qualificatifs", "liste_cle": "nulle"}, "liste_inconnue"),
    ({"libelle": "x", "liste_cle": "sources"}, "liste_hors_qualificatifs"),
    ({"libelle": "x", "cible": "mots | case"}, "cible_inconnue"),
    ({"libelle": "x", "forme": "libre"}, "forme_inconnue"),
    ({"libelle": "x", "cardinalite": "souvent"}, "cardinalite_inconnue"),
    ({"libelle": "x", "rubrique_cle": "nulle-part"}, "rubrique_inconnue"),
    ({"libelle": "x", "exemples": ["AH | OH"]}, "exemple_separateur"),
    ({"libelle": "x", "variantes": [{"libelle": "v"}]}, "variante_sous_autre_forme"),
    ({"libelle": "  "}, "libelle_vide"),
    ({"cle": "cri", "libelle": "x"}, "cle_en_double"),
    ({"libelle": "x", "forme": "variantes", "variantes": [{"libelle": ""}]},
     "variante_sans_nom"),
])
def test_une_entree_porte_les_refus_de_l_import(client, decor, db_path, corps, code):
    gid = importer(client, decor["p"], LEA)["grille_id"]
    avant = _n(db_path, "SELECT COUNT(*) FROM evenement WHERE cible_table = 'grille'")
    r = client.post(f"/api/grilles/{gid}/entrees", headers=LEA, json=corps)
    assert r.status_code == 422 and _codes(r) == [code], r.text
    assert _n(db_path, "SELECT COUNT(*) FROM evenement WHERE cible_table = 'grille'") == avant
    assert _n(db_path, "SELECT COUNT(*) FROM grille_entree WHERE libelle = 'x'") == 0


def test_les_refus_des_rubriques_listes_et_cases(client, decor):
    gid = importer(client, decor["p"], LEA)["grille_id"]
    r = client.post(f"/api/grilles/{gid}/rubriques", headers=LEA,
                    json={"libelle": "Sons > Cris"})
    assert r.status_code == 422 and _codes(r) == ["rubrique_separateur"]
    r = client.post(f"/api/grilles/{gid}/rubriques", headers=LEA,
                    json={"libelle": "B. Provenance"})
    assert r.status_code == 422 and _codes(r) == ["rubrique_deux_identifiants"]
    r = client.patch(f"/api/grilles/{gid}/rubriques/sons", headers=LEA,
                     json={"parent_cle": "chocs"})
    assert r.status_code == 422 and _codes(r) == ["rubrique_circulaire"]
    r = client.post(f"/api/grilles/{gid}/rubriques", headers=LEA,
                    json={"libelle": "X", "parent_cle": "nulle"})
    assert r.status_code == 422 and _codes(r) == ["rubrique_parent_inconnu"]
    assert client.post(f"/api/grilles/{gid}/rubriques", headers=LEA,
                       json={"cle": "a > b", "libelle": "Y"}).status_code == 422
    # Une liste vide ne se nomme pas ; la dernière case d'une liste nommée ne part pas.
    ok(client.post(f"/api/grilles/{gid}/listes", headers=LEA, json={"libelle": "Vide"}), 201)
    r = client.patch(f"/api/grilles/{gid}/entrees/echo", headers=LEA, json={"liste_cle": "vide"})
    assert r.status_code == 422 and _codes(r) == ["liste_vide"]
    ok(client.post(f"/api/grilles/{gid}/listes", headers=LEA,
                   json={"libelle": "Une", "cases": [{"libelle": "seule"}]}), 201)
    ok(client.patch(f"/api/grilles/{gid}/entrees/echo", headers=LEA, json={"liste_cle": "une"}))
    r = client.delete(f"/api/grilles/{gid}/listes/une/cases/seule", headers=LEA)
    assert r.status_code == 422 and _codes(r) == ["liste_vide"]
    r = client.post(f"/api/grilles/{gid}/listes/une/cases", headers=LEA,
                    json={"cle": "seule", "libelle": "encore"})
    assert r.status_code == 422 and _codes(r) == ["qualificatif_en_double"]
    # La dernière variante d'une entrée à variantes non plus.
    for vc in ("bang", "crac"):
        ok(client.delete(f"/api/grilles/{gid}/entrees/onomatopee/variantes/{vc}", headers=LEA))
    r = client.delete(f"/api/grilles/{gid}/entrees/onomatopee/variantes/splash", headers=LEA)
    assert r.status_code == 422 and _codes(r) == ["variantes_absentes"]


def test_quitter_une_forme(client, decor):
    """Quitter « des cases d'une liste » délie la liste ; quitter « une variante » demande
    d'avoir retiré ses variantes ; devenir « à variantes » se fait avec ses variantes."""
    gid = importer(client, decor["p"], LEA)["grille_id"]
    r = ok(client.patch(f"/api/grilles/{gid}/entrees/echo", headers=LEA,
                        json={"forme": "simple"}))
    assert _entree(r["plan"], "echo")["liste_cle"] is None
    r = client.patch(f"/api/grilles/{gid}/entrees/onomatopee", headers=LEA,
                     json={"forme": "simple"})
    assert r.status_code == 422 and _codes(r) == ["variante_sous_autre_forme"]
    r = ok(client.patch(f"/api/grilles/{gid}/entrees/cri", headers=LEA, json={
        "forme": "variantes", "variantes": [{"libelle": "aigu"}, {"libelle": "grave"}]}))
    assert [x["cle"] for x in _entree(r["plan"], "cri")["variantes"]] == ["aigu", "grave"]


def test_les_rubriques_listes_et_cases_se_suppriment_vides_ou_libres(client, decor, db_path):
    gid = importer(client, decor["p"], LEA)["grille_id"]
    r = client.delete(f"/api/grilles/{gid}/rubriques/sons", headers=LEA)
    assert r.status_code == 409 and "que vide" in r.json()["detail"]
    r = client.delete(f"/api/grilles/{gid}/listes/sources", headers=LEA)
    assert r.status_code == 409 and "sert à 2 entrée(s)" in r.json()["detail"]
    ok(client.patch(f"/api/grilles/{gid}/entrees/regard-camera", headers=LEA,
                    json={"rubrique_cle": None}))
    r = ok(client.delete(f"/api/grilles/{gid}/rubriques/image", headers=LEA))
    assert "image" not in [x["cle"] for x in r["plan"]["rubriques"]]
    ok(client.delete(f"/api/grilles/{gid}/listes/sources/cases/hors-champ", headers=LEA))
    for cle in ("intensite", "geste-graphique"):
        ok(client.delete(f"/api/grilles/{gid}/entrees/{cle}", headers=LEA))
    ok(client.delete(f"/api/grilles/{gid}/listes/manieres", headers=LEA))
    plan = ok(client.get(f"/api/grilles/{gid}/versions/1", headers=LEA))
    assert [x["cle"] for x in plan["listes"]] == ["sources"]
    assert [q["cle"] for q in plan["listes"][0]["qualificatifs"]] == ["personnage", "objet"]


def test_un_identifiant_disparu_se_reprend_par_son_nom(client, decor):
    """La dérivation de l'import : une entrée recréée sous le nom d'une entrée de la version
    publiée que le brouillon ne porte plus reprend son identifiant ; sinon il est dérivé, hors
    de tout identifiant pris."""
    g = grille_active(client, decor["p"])
    gid = g["grille_id"]
    ok(client.delete(f"/api/grilles/{gid}/entrees/ambiance", headers=LEA))
    r = ok(client.post(f"/api/grilles/{gid}/entrees", headers=LEA,
                       json={"libelle": "ambiance sonore de la planche"}), 201)
    assert r["cle"] == "ambiance" and r["version"]["numero"] == 2
    r = ok(client.post(f"/api/grilles/{gid}/entrees", headers=LEA, json={"libelle": "Cri"}),
           201)
    assert r["cle"] == "cri-2"


# --------------------------------------------------------------------------- #
# Une entrée employée ne se supprime jamais
# --------------------------------------------------------------------------- #
@pytest.fixture
def ouverte(client, decor):
    """Une grille OUVERTE, active, et un relevé de STAG sur « cri », un sur la variante
    « bang » d'« onomatopée », un qui coche « objet » sur « écho »."""
    g = grille_active(client, decor["p"], ouverte=True, nom="Libre")
    gid = g["grille_id"]
    poser = lambda **kw: ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": gid, "version": 1, "region_id": decor["zones"]["bulle"], **kw}), 201)
    return {**decor, "grille_id": gid, "releve": poser(entree_cle="cri", mots=[8])["id"],
            "bang": poser(entree_cle="onomatopee", variante_cle="bang", mots=[0])["id"],
            "objet": poser(entree_cle="echo", qualificatifs=["objet"], mots=[1])["id"]}


def test_une_entree_employee_ne_se_supprime_pas_elle_se_retire(client, ouverte, db_path):
    d = ouverte
    gid = d["grille_id"]
    r = client.delete(f"/api/grilles/{gid}/entrees/cri", headers=LEA)
    assert r.status_code == 409, r.text
    det = r.json()["detail"]
    assert det["a_repondre"] == [{"cle": "cri", "libelle": "cri", "releves": 1,
                                  "choix": ["retirer", "fusionner"], "fusionner_dans": []}]
    assert _n(db_path, "SELECT COUNT(*) FROM grille_entree WHERE cle = 'cri'") == 1
    depuis = _dernier_acte(db_path)
    r = ok(client.post(f"/api/grilles/{gid}/entrees/cri/retrait", headers=LEA))
    assert r["version"] == {"numero": 1, "etat": "vivante"}
    assert _entree(r["plan"], "cri")["retiree"] is True
    (rel,) = _q(db_path, "SELECT etat, entree_absente FROM releves_effectifs WHERE id = ?",
                (d["releve"],))
    assert rel == {"etat": "a_revoir", "entree_absente": 1}
    # Elle ne se pose plus.
    ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": gid, "version": 1, "region_id": d["zones"]["bulle"],
        "entree_cle": "cri", "mots": [7]}), 422)
    (acte,) = _actes(db_path, depuis)
    assert acte["avant"] == {"objet": "entree:cri", "version": 1, "retiree": False}
    assert acte["apres"] == {"objet": "entree:cri", "version": 1, "retiree": True}
    # Toujours employée, retirée, elle ne se supprime pas davantage.
    assert client.delete(f"/api/grilles/{gid}/entrees/cri", headers=LEA).status_code == 409
    # La remettre en usage : son relevé redevient normal.
    ok(client.delete(f"/api/grilles/{gid}/entrees/cri/retrait", headers=LEA))
    assert _q(db_path, "SELECT etat FROM releves_effectifs WHERE id = ?", (d["releve"],))[0][
        "etat"] == "normal"
    # Une entrée que personne n'emploie, elle, se supprime.
    r = ok(client.delete(f"/api/grilles/{gid}/entrees/ambiance", headers=LEA))
    assert "ambiance" not in [e["cle"] for e in r["plan"]["entrees"]]
    assert _n(db_path, "SELECT COUNT(*) FROM releve") == 3


def test_fusionner_fait_ce_que_fait_le_reimport(client, ouverte, db_path):
    d = ouverte
    gid = d["grille_id"]
    ok(client.post(f"/api/grilles/{gid}/entrees", headers=LEA, json={
        "libelle": "hurlement", "rubrique_cle": "voix", "definition": "un cri long"}), 201)
    r = client.delete(f"/api/grilles/{gid}/entrees/cri", headers=LEA)
    assert r.json()["detail"]["a_repondre"][0]["fusionner_dans"] == ["hurlement"]
    r = client.post(f"/api/grilles/{gid}/entrees/cri/fusion", headers=LEA,
                    json={"dans": "regard-camera"})
    assert r.status_code == 409 and _codes(r) == ["fusion_impossible"]
    assert _q(db_path, "SELECT entree_cle FROM releve WHERE id = ?", (d["releve"],))[0][
        "entree_cle"] == "cri"
    r = client.post(f"/api/grilles/{gid}/entrees/ambiance/fusion", headers=LEA,
                    json={"dans": "hurlement"})
    assert r.status_code == 409 and "rien à fusionner" in r.json()["detail"]
    depuis = _dernier_acte(db_path)
    r = ok(client.post(f"/api/grilles/{gid}/entrees/cri/fusion", headers=LEA,
                       json={"dans": "hurlement"}))
    assert r["fusions"] == [{"de": "cri", "dans": "hurlement", "releve_ids": [d["releve"]]}]
    assert "cri" not in [e["cle"] for e in r["plan"]["entrees"]]
    assert _q(db_path, "SELECT entree_cle FROM releve WHERE id = ?", (d["releve"],))[0][
        "entree_cle"] == "hurlement"
    assert _q(db_path, "SELECT etat FROM releves_effectifs WHERE id = ?", (d["releve"],))[0][
        "etat"] == "normal"
    (acte,) = _actes(db_path, depuis)
    assert acte["type"] == "suppression" and acte["avant"]["objet"] == "entree:cri"
    assert acte["apres"] == {"objet": "entree:cri", "version": 1,
                             "fusionnee_dans": "hurlement", "releve_ids": [d["releve"]]}


def test_le_formulaire_lit_ce_que_les_releves_emploient(client, ouverte, decor):
    """Le formulaire n'offre que les gestes que le serveur accepte : il lit, avec le plan, ce
    que les relevés emploient (`emplois`) — par entrée, par variante, par case, et où une
    entrée employée d'une grille ouverte se fusionnerait —, aux comptes des refus. À qui
    gère le projet seulement : la clé est absente pour un membre, et du plan qu'on lit sans
    la demander."""
    gid = ouverte["grille_id"]
    ok(client.post(f"/api/grilles/{gid}/entrees", headers=LEA, json={
        "libelle": "hurlement", "rubrique_cle": "voix"}), 201)
    plan = ok(client.get(f"/api/grilles/{gid}/versions/1", params={"emplois": "1"},
                         headers=LEA))
    em = plan["emplois"]
    assert em["entrees"] == {"cri": 1, "onomatopee": 1, "echo": 1}
    assert em["variantes"] == {"onomatopee": {"bang": 1}}
    assert em["cases"] == {"objet": 1}
    # Les cibles de la fusion sont celles que le refus de « Supprimer » nommerait.
    refus = client.delete(f"/api/grilles/{gid}/entrees/cri", headers=LEA).json()["detail"]
    assert em["fusionner_dans"]["cri"] == refus["a_repondre"][0]["fusionner_dans"]         == ["hurlement"]
    assert set(em["fusionner_dans"]) == {"cri", "onomatopee", "echo"}
    # La réponse d'un geste les porte aussi.
    r = ok(client.patch(f"/api/grilles/{gid}/entrees/cri", headers=LEA,
                        json={"definition": "un cri"}))
    assert r["emplois"]["entrees"]["cri"] == 1
    # Sans la demander, ou sans gérer le projet : la clé est absente.
    assert "emplois" not in ok(client.get(f"/api/grilles/{gid}/versions/1", headers=LEA))
    lu = client.get(f"/api/grilles/{gid}/versions/1", params={"emplois": "1"}, headers=STAG)
    assert lu.status_code == 200 and "emplois" not in lu.json()
    # Le plan dit la cardinalité DÉCLARÉE à côté de l'effective : « comme d'ordinaire ».
    cri = _entree(plan, "cri")
    assert cri["cardinalite_declaree"] is None and cri["cardinalite"] == "plusieurs"


def test_dans_une_fermee_aucune_fusion_ne_s_offre(client, decor):
    g = grille_active(client, decor["p"])
    gid = g["grille_id"]
    ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": gid, "version": 1, "region_id": decor["zones"]["bulle"],
        "entree_cle": "cri", "mots": [8]}), 201)
    em = ok(client.get(f"/api/grilles/{gid}/versions/1", params={"emplois": "1"},
                       headers=LEA))["emplois"]
    assert em["entrees"] == {"cri": 1} and em["fusionner_dans"] == {}


def test_une_entree_retiree_que_personne_n_emploie_se_supprime(client, ouverte, db_path):
    """Le réimport garde retirée, sans question, une entrée retirée que le fichier ne porte
    pas ; le formulaire, qui la nomme pour la supprimer, la supprime."""
    gid = ouverte["grille_id"]
    ok(client.post(f"/api/grilles/{gid}/entrees/ambiance/retrait", headers=LEA))
    r = ok(client.delete(f"/api/grilles/{gid}/entrees/ambiance", headers=LEA))
    assert "ambiance" not in [e["cle"] for e in r["plan"]["entrees"]]
    assert _n(db_path, "SELECT COUNT(*) FROM grille_entree WHERE cle = 'ambiance'") == 0


def test_une_entree_retiree_se_fusionne_aussi(client, ouverte, db_path):
    d = ouverte
    gid = d["grille_id"]
    ok(client.post(f"/api/grilles/{gid}/entrees", headers=LEA,
                   json={"libelle": "hurlement"}), 201)
    ok(client.post(f"/api/grilles/{gid}/entrees/cri/retrait", headers=LEA))
    r = ok(client.post(f"/api/grilles/{gid}/entrees/cri/fusion", headers=LEA,
                       json={"dans": "hurlement"}))
    assert r["fusions"][0]["releve_ids"] == [d["releve"]]
    assert _n(db_path, "SELECT COUNT(*) FROM grille_entree WHERE cle = 'cri'") == 0


def test_sous_des_releves_une_entree_ne_change_ni_de_forme_ni_de_liste(client, ouverte,
                                                                       db_path):
    gid = ouverte["grille_id"]
    r = client.patch(f"/api/grilles/{gid}/entrees/cri", headers=LEA,
                     json={"forme": "qualificatifs", "liste_cle": "sources"})
    assert r.status_code == 409 and _codes(r) == ["change_sous_des_releves"] * 2
    r = client.patch(f"/api/grilles/{gid}/entrees/echo", headers=LEA,
                     json={"liste_cle": "manieres"})
    assert r.status_code == 409 and _codes(r) == ["change_sous_des_releves"]
    # Une variante ou une case employée ne disparaît pas.
    r = client.delete(f"/api/grilles/{gid}/entrees/onomatopee/variantes/bang", headers=LEA)
    assert r.status_code == 409 and "1 relevé(s)" in r.json()["detail"]
    ok(client.delete(f"/api/grilles/{gid}/entrees/onomatopee/variantes/crac", headers=LEA))
    r = client.delete(f"/api/grilles/{gid}/listes/sources/cases/objet", headers=LEA)
    assert r.status_code == 409 and "cochent" in r.json()["detail"]
    # Ce qui ne touche pas un relevé s'écrit en place.
    r = ok(client.patch(f"/api/grilles/{gid}/entrees/cri", headers=LEA,
                        json={"libelle": "cri perçant"}))
    assert _entree(r["plan"], "cri")["libelle"] == "cri perçant"
    assert _n(db_path, "SELECT COUNT(*) FROM releve") == 3


def test_dans_le_brouillon_d_une_fermee_une_entree_employee_se_retire_et_ne_fusionne_pas(
        client, decor, db_path):
    g = grille_active(client, decor["p"])
    gid = g["grille_id"]
    rel = ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": gid, "version": 1, "region_id": decor["zones"]["bulle"],
        "entree_cle": "cri", "mots": [8]}), 201)["id"]
    r = client.delete(f"/api/grilles/{gid}/entrees/cri", headers=LEA)
    assert r.status_code == 409
    assert r.json()["detail"]["a_repondre"][0]["choix"] == ["retirer"]
    r = client.post(f"/api/grilles/{gid}/entrees/cri/fusion", headers=LEA,
                    json={"dans": "echo"})
    assert r.status_code == 409 and "fermée" in r.json()["detail"]
    assert _n(db_path, "SELECT COUNT(*) FROM grille_version") == 1     # rien n'est né
    r = ok(client.post(f"/api/grilles/{gid}/entrees/cri/retrait", headers=LEA))
    assert r["version"] == {"numero": 2, "etat": "brouillon"}
    assert _entree(r["plan"], "cri")["retiree"] is True
    # Le relevé vit dans la version 1, où l'entrée n'est pas retirée.
    assert _q(db_path, "SELECT etat FROM releves_effectifs WHERE id = ?", (rel,))[0][
        "etat"] == "normal"
    assert _q(db_path, "SELECT e.retiree FROM grille_entree e JOIN grille_version v ON "
                       "v.id = e.version_id WHERE v.numero = 1 AND e.cle = 'cri'")[0][
        "retiree"] == 0
    # Une variante employée dans la version publiée ne se supprime pas du brouillon.
    ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": gid, "version": 1, "region_id": decor["zones"]["bulle"],
        "entree_cle": "onomatopee", "variante_cle": "bang", "mots": [0]}), 201)
    assert client.delete(f"/api/grilles/{gid}/entrees/onomatopee/variantes/bang",
                         headers=LEA).status_code == 409


def test_le_reimport_d_une_fermee_tient_la_regle_du_formulaire_sur_une_variante_ou_une_case(
        client, decor, db_path):
    """Une variante ou une case qu'un relevé emploie ne se supprime pas du brouillon d'une
    grille fermée (choix 3, tranché par Hugo le 2026-11-04) — au formulaire comme au
    réimport du tableur, qui la laissait disparaître. Ce que personne n'emploie part, par
    l'un comme par l'autre."""
    g = grille_active(client, decor["p"])
    gid = g["grille_id"]
    for corps in ({"entree_cle": "onomatopee", "variante_cle": "bang", "mots": [0]},
                  {"entree_cle": "echo", "qualificatifs": ["objet"], "mots": [1]}):
        ok(client.post("/api/releves", headers=STAG, json={
            "grille_id": gid, "version": 1, "region_id": decor["zones"]["bulle"], **corps}), 201)
    sans_bang = MODELE.replace(
        "onomatopee;;;;;bang;bang;;un choc sec, une détonation;BANG ! | PAN !;;;;;;\r\n", "")
    sans_objet = MODELE_LISTES.replace("sources;source du son;objet;objet;un objet de la case\r\n",
                                       "")
    assert sans_bang != MODELE and sans_objet != MODELE_LISTES
    # Le formulaire : 409.
    r = client.delete(f"/api/grilles/{gid}/entrees/onomatopee/variantes/bang", headers=LEA)
    assert r.status_code == 409 and "1 relevé(s)" in r.json()["detail"]
    r = client.delete(f"/api/grilles/{gid}/listes/sources/cases/objet", headers=LEA)
    assert r.status_code == 409 and "cochent" in r.json()["detail"]
    # Le réimport : 409 aussi, à blanc comme pour de bon, la faute en données.
    for a_blanc in (True, False):
        refus = importer(client, decor["p"], LEA, grille_id=gid, entrees=sans_bang,
                         a_blanc=a_blanc, attendu=(409,))["detail"]
        assert [(a["code"], a["cle"]) for a in refus["anomalies"]] == [
            ("variante_employee_disparait", "onomatopee")]
        assert refus["verdict"]["etat"] == "refuse"
    refus = importer(client, decor["p"], LEA, grille_id=gid, listes=sans_objet,
                     attendu=(409,))["detail"]
    assert [a["code"] for a in refus["anomalies"]] == ["case_employee_disparait"]
    assert _n(db_path, "SELECT COUNT(*) FROM grille_version") == 1      # rien n'est né
    # Un brouillon déjà né ne change pas la règle : la variante est connue par lui aussi.
    ok(client.patch(f"/api/grilles/{gid}/entrees/cri", headers=LEA, json={"piege": "x"}))
    importer(client, decor["p"], LEA, grille_id=gid, entrees=sans_bang, attendu=(409,))
    # Ce que personne n'emploie part, au réimport comme au formulaire.
    sans_crac = MODELE.replace("onomatopee;;;;;crac;crac;;une rupture, un craquement;CRAC;;;;;;\r\n",
                               "")
    assert sans_crac != MODELE
    res = importer(client, decor["p"], LEA, grille_id=gid, entrees=sans_crac)
    assert res["ecrit"] and res["version"]["etat"] == "brouillon"
    assert [x["cle"] for x in res["bilan"]["disparus"]] == ["onomatopee/crac"]
    ok(client.delete(f"/api/grilles/{gid}/listes/sources/cases/hors-champ", headers=LEA))


def test_le_journal_nomme_chaque_objet(client, decor, db_path):
    gid = importer(client, decor["p"], LEA)["grille_id"]
    depuis = _dernier_acte(db_path)
    ok(client.post(f"/api/grilles/{gid}/listes/sources/cases", headers=LEA,
                   json={"libelle": "foule", "definition": "plusieurs voix"}), 201)
    ok(client.post(f"/api/grilles/{gid}/entrees/onomatopee/variantes", headers=LEA,
                   json={"libelle": "boum"}), 201)
    ok(client.delete(f"/api/grilles/{gid}/entrees/regard-camera", headers=LEA))
    objets = [(a["type"], (a["apres"] or a["avant"])["objet"]) for a in _actes(db_path, depuis)]
    assert objets == [("creation", "case:sources/foule"),
                      ("creation", "variante:onomatopee/boum"),
                      ("suppression", "entree:regard-camera")]
    # Ctrl+Z ne défait pas un geste sur une grille.
    r = client.get("/api/undo/prochain", headers=LEA)
    assert r.status_code == 404 or "grille" not in r.text


# --------------------------------------------------------------------------- #
# L'ordre, et le brouillon qui ne change rien
# --------------------------------------------------------------------------- #
def _cles(objets):
    return [x["cle"] for x in objets]


def test_les_objets_d_une_grille_se_reordonnent(client, decor, db_path):
    """Une rubrique, une entrée, une variante, une case se rangent à une place parmi leurs
    frères ; sur une grille fermée, dans le brouillon ; les autres ne bougent pas ; `vu`
    garde l'ordre vu ; au journal, un acte qui nomme les frères."""
    g = grille_active(client, decor["p"])
    gid = g["grille_id"]
    url = f"/api/grilles/{gid}/ordre"
    v1 = ok(client.get(f"/api/grilles/{gid}/versions/1", headers=LEA))
    depuis = _dernier_acte(db_path)
    r = ok(client.put(url, headers=LEA, json={"quoi": "entree", "cle": "ton-de-voix",
                                              "place": 0, "vu": ["cri", "ton-de-voix"]}))
    assert r["version"] == {"numero": 2, "etat": "brouillon"} and r["brouillon_cree"]
    entrees = _cles(r["plan"]["entrees"])
    assert entrees.index("ton-de-voix") < entrees.index("cri")
    autres = [k for k in _cles(v1["entrees"]) if k not in ("cri", "ton-de-voix")]
    assert [k for k in entrees if k not in ("cri", "ton-de-voix")] == autres
    # La version publiée ne bouge pas.
    assert _cles(ok(client.get(f"/api/grilles/{gid}/versions/1", headers=LEA))["entrees"]) \
        == _cles(v1["entrees"])
    acte = _actes(db_path, depuis)[-1]
    assert acte["avant"] == {"objet": "ordre:entree:voix", "version": 2,
                             "ordre": ["cri", "ton-de-voix"]}
    assert acte["apres"] == {"objet": "ordre:entree:voix", "version": 2,
                             "ordre": ["ton-de-voix", "cri"], "deplace": "ton-de-voix"}
    # Une rubrique parmi celles de son étage.
    r = ok(client.put(url, headers=LEA, json={"quoi": "rubrique", "cle": "image", "place": 0}))
    assert _cles(x for x in r["plan"]["rubriques"] if x["parent_cle"] is None) == [
        "image", "sons", "provenance", "graphisme", "echanges"]
    # Une variante parmi celles de son entrée, une case parmi celles de sa liste.
    r = ok(client.put(url, headers=LEA, json={"quoi": "variante", "entree_cle": "onomatopee",
                                              "cle": "splash", "place": 1}))
    assert _cles(_entree(r["plan"], "onomatopee")["variantes"]) == ["bang", "splash", "crac"]
    r = ok(client.put(url, headers=LEA, json={"quoi": "case", "liste_cle": "sources",
                                              "cle": "hors-champ", "place": 0}))
    (sources,) = [x for x in r["plan"]["listes"] if x["cle"] == "sources"]
    assert _cles(sources["qualificatifs"]) == ["hors-champ", "personnage", "objet"]
    # À sa place : rien ne s'écrit.
    depuis = _dernier_acte(db_path)
    ok(client.put(url, headers=LEA, json={"quoi": "entree", "cle": "cri", "place": 1}))
    assert _actes(db_path, depuis) == []
    # Une place hors des frères, une sorte inconnue : 422 ; un objet absent : 404.
    for corps, code in (({"quoi": "entree", "cle": "cri", "place": 2}, 422),
                        ({"quoi": "entree", "cle": "cri", "place": -1}, 422),
                        ({"quoi": "liste", "cle": "sources", "place": 0}, 422),
                        ({"quoi": "variante", "entree_cle": "cri", "cle": "bang",
                          "place": 0}, 404),
                        ({"quoi": "case", "liste_cle": "sources", "cle": "rien",
                          "place": 0}, 404)):
        assert client.put(url, headers=LEA, json=corps).status_code == code, corps
    # Un ordre vu périmé : le 409 de CONC-3, qui nomme qui l'a changé.
    ok(client.put(url, headers=ADMIN, json={"quoi": "entree", "cle": "cri", "place": 0}))
    r = client.put(url, headers=LEA, json={"quoi": "entree", "cle": "cri", "place": 1,
                                           "vu": ["ton-de-voix", "cri"]})
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert d["conflit"]["champ"] == "ordre" and d["conflit"]["auteur"]["login"] == "decor"
    assert "l'ordre a été modifié" in d["message"]
    # Qui ne gère pas le projet : 403 nommé.
    assert client.put(url, headers=SAM, json={"quoi": "entree", "cle": "cri",
                                              "place": 1}).status_code == 403


def test_un_brouillon_identique_a_la_version_publiee_ne_se_publie_pas(client, decor, db_path):
    """Un brouillon qui porte exactement la dernière version publiée ne se publie pas (409
    nommé) : il donnerait deux numéros au même plan. Changer l'ordre suffit à en faire une
    version — c'est ce que l'annotateur voit, même si l'empreinte l'écarte."""
    g = grille_active(client, decor["p"])
    gid = g["grille_id"]
    piege = "un cri n'est pas une onomatopée de choc : on le pose sur le cri, pas sur le bruit"
    ok(client.patch(f"/api/grilles/{gid}/entrees/cri", headers=LEA, json={"piege": "x"}))
    ok(client.patch(f"/api/grilles/{gid}/entrees/cri", headers=LEA, json={"piege": piege}))
    r = client.post(f"/api/grilles/{gid}/versions/2/publication", headers=LEA)
    assert r.status_code == 409 and "rien à publier" in r.json()["detail"], r.text
    assert _q(db_path, "SELECT numero, etat FROM grille_version ORDER BY numero") == [
        {"numero": 1, "etat": "publiee"}, {"numero": 2, "etat": "brouillon"}]
    ok(client.put(f"/api/grilles/{gid}/ordre", headers=LEA,
                  json={"quoi": "entree", "cle": "ton-de-voix", "place": 0}))
    ok(client.post(f"/api/grilles/{gid}/versions/2/publication", headers=LEA))
    entrees = _cles(ok(client.get(f"/api/grilles/{gid}/versions/2", headers=LEA))["entrees"])
    assert entrees.index("ton-de-voix") < entrees.index("cri")
