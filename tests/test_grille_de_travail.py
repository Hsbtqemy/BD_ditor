"""La grille de TRAVAIL de chaque projet, et les variables posées en les tapant (ANN-7, le
basculement, commit 2 bis ; « Les étiquettes de travail » et « Les variables aussi », Hugo,
2026-11-05).

Tout projet qui NAÎT — par la route, en bac à sable, le projet de repli d'une base neuve —
reçoit une grille OUVERTE « Travail en cours », VIDE, sur toute zone, active dans sa version
vivante, à personne. Le projet de jeu, non. Vide, elle part avec son projet ; portant un
relevé, elle le retient (G18). Dans une grille ouverte, « nom : valeur » fait naître ou
retrouve l'entrée « nom » à variantes et sa variante.
"""
import sqlite3

import pytest

import database
import grilles
from config import GRILLE_DE_TRAVAIL_NOM
from conftest import ADMIN
from grilles_decor import LEA, STAG, csv_de, grille_active, importer
from test_releves import bulle, decor, poser  # noqa: F401


def _q(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, p)]
    finally:
        c.close()


def _grille_de_travail(db_path, projet_id):
    """La grille de travail du projet, avec sa version et son activation ; None sinon."""
    lignes = _q(db_path,
                "SELECT g.id, g.ouverte, g.cree_par, g.identifiant, g.derivee_de_identifiant, "
                "       v.numero, v.etat, v.cible, "
                "       v.importee_par AS par, "
                "       (SELECT COUNT(*) FROM grille_entree e WHERE e.version_id = v.id) AS n, "
                "       pg.version_id IS NOT NULL AS active "
                "FROM grille g JOIN grille_version v ON v.grille_id = g.id "
                "LEFT JOIN projet_grille pg ON pg.grille_id = g.id AND pg.projet_id = g.projet_id "
                "WHERE g.projet_id = ? AND g.nom = ?", (projet_id, GRILLE_DE_TRAVAIL_NOM))
    assert len(lignes) <= 1, lignes
    return lignes[0] if lignes else None


def _attendue(g):
    """Ouverte, vide, sur toute zone, active dans sa version vivante 1, à personne."""
    assert g is not None, "le projet est né sans sa grille de travail"
    assert (g["ouverte"], g["numero"], g["etat"], g["n"], g["active"]) == (
        1, 1, grilles.ETAT_VIVANTE, 0, 1), g
    assert set(grilles.cibles_de(g["cible"])) == set(grilles.CIBLES_ZONE), g["cible"]
    assert g["cree_par"] is None and g["par"] is None, g
    # Son identifiant, qui survit à l'instance (v40), et aucune origine.
    assert grilles.identifiant_lu(g["identifiant"]) == g["identifiant"], g
    assert g["derivee_de_identifiant"] is None, g


def test_un_projet_cree_par_la_route_nait_avec_sa_grille_de_travail(client, db_path):
    p = client.post("/api/projets", headers=ADMIN, json={"nom": "Neuf"})
    assert p.status_code == 201, p.text
    _attendue(_grille_de_travail(db_path, p.json()["id"]))
    # Elle se lit comme toute grille active du projet.
    actives = client.get(f"/api/projets/{p.json()['id']}/grilles", headers=ADMIN).json()[
        "actives"]
    assert [(a["nom"], a["ouverte"]) for a in actives] == [(GRILLE_DE_TRAVAIL_NOM, True)]
    # Le journal garde sa naissance, sous la grille.
    gid = _grille_de_travail(db_path, p.json()["id"])["id"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table = 'grille' "
                       "AND cible_id = ? AND type = 'creation' "
                       "AND apres LIKE '%\"travail\": true%'", (gid,))[0]["n"] == 1


def test_le_projet_de_repli_d_une_base_neuve_a_sa_grille_de_travail_et_le_jeu_non(db_path):
    repli = _q(db_path, "SELECT id FROM projet WHERE repli = 1")[0]["id"]
    _attendue(_grille_de_travail(db_path, repli))
    conn = database.get_connection()
    try:
        import grille_import
        # Rejouée, l'installation ne double rien.
        assert grille_import.installer_grille_de_travail(conn, repli) is None
        jeu = conn.execute("INSERT INTO projet (nom, jeu) VALUES ('Jeu témoin', 1)").lastrowid
        assert grille_import.installer_grille_de_travail(conn, jeu) is None
        conn.rollback()
    finally:
        conn.close()
    assert len(_q(db_path, "SELECT id FROM grille WHERE projet_id = ? AND nom = ?",
                  (repli, GRILLE_DE_TRAVAIL_NOM))) == 1


def test_un_bac_a_sable_nait_avec_sa_grille_de_travail(client, db_path, derriere_proxy):
    client.get("/api/moi", headers=LEA)
    bac = client.post("/api/bac-a-sable", headers=LEA)
    assert bac.status_code in (200, 201), bac.text
    _attendue(_grille_de_travail(db_path, bac.json()["id"]))


def test_un_projet_vide_se_supprime_avec_sa_grille_de_travail(client, db_path):
    pid = client.post("/api/projets", headers=ADMIN, json={"nom": "Éphémère"}).json()["id"]
    gid = _grille_de_travail(db_path, pid)["id"]
    r = client.delete(f"/api/projets/{pid}", headers=ADMIN)
    assert r.status_code in (200, 204), r.text
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille WHERE id = ?", (gid,))[0]["n"] == 0
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille_version WHERE grille_id = ?",
              (gid,))[0]["n"] == 0
    assert _q(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table = 'grille' "
                       "AND cible_id = ? AND type = 'suppression'", (gid,))[0]["n"] == 1


def _travail(client, d, db_path):
    """Le décor des relevés, posé dans la grille de TRAVAIL du projet."""
    g = _grille_de_travail(db_path, d["p"])
    return {**d, "grille_id": g["id"], "numero": g["numero"]}


def test_une_grille_de_travail_qui_porte_quelque_chose_retient_son_projet(client, db_path):
    """Une entrée suffit (une étiquette née en la posant, dont le relevé a été retiré) : la
    grille n'est plus vide, et le refus de G18 la nomme."""
    pid = client.post("/api/projets", headers=ADMIN, json={"nom": "Habité"}).json()["id"]
    g = _grille_de_travail(db_path, pid)
    c = sqlite3.connect(db_path)
    try:
        c.execute("INSERT INTO grille_entree (version_id, cle, rang, forme, libelle) "
                  "SELECT id, 'a-reprendre', 0, 'simple', 'à reprendre' FROM grille_version "
                  "WHERE grille_id = ?", (g["id"],))
        c.commit()
    finally:
        c.close()
    r = client.delete(f"/api/projets/{pid}", headers=ADMIN)
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    # La phrase dit le geste qui VIDE la grille de travail, jamais « supprimez-la », que J2
    # refuse ; et l'étiquette retirée, le projet se supprime.
    assert "Mode libre" in detail and "Retirer" in detail, detail
    assert "supprimer" not in detail, detail
    r = client.delete(f"/api/grilles/{g['id']}/entrees/a-reprendre", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert client.delete(f"/api/projets/{pid}", headers=ADMIN).status_code == 204


def test_nom_valeur_fait_naitre_l_entree_a_variantes_et_sa_variante(client, decor, db_path):
    t = _travail(client, decor, db_path)
    case = t["zones"]["case"]
    r = poser(client, t, region_id=case, nouvelle_entree={"libelle": "lieu : forêt"})
    assert (r["entree_cle"], r["variante_cle"]) == ("lieu", "foret"), r
    entree = _q(db_path, "SELECT e.forme, e.libelle FROM grille_entree e JOIN grille_version v "
                         "ON v.id = e.version_id WHERE v.grille_id = ?", (t["grille_id"],))
    assert entree == [{"forme": "variantes", "libelle": "lieu"}]
    # Une valeur nouvelle sur l'entrée qui existe s'y ajoute ; une valeur connue (casse,
    # espaces) est reprise, sans rien faire naître.
    autre = t["zones"]["cartouche"]
    r2 = poser(client, t, region_id=autre, nouvelle_entree={"libelle": "Lieu :  grotte "})
    assert (r2["entree_cle"], r2["variante_cle"]) == ("lieu", "grotte"), r2
    r3 = poser(client, t, region_id=t["zones"]["personnage"],
               nouvelle_entree={"libelle": "LIEU : Forêt"})
    assert (r3["entree_cle"], r3["variante_cle"]) == ("lieu", "foret"), r3
    variantes = _q(db_path, "SELECT x.cle, x.libelle FROM grille_variante x JOIN grille_version v "
                            "ON v.id = x.version_id WHERE v.grille_id = ? ORDER BY x.rang",
                   (t["grille_id"],))
    assert variantes == [{"cle": "foret", "libelle": "forêt"},
                         {"cle": "grotte", "libelle": "grotte"}]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table = 'grille' "
                       "AND cible_id = ? AND apres LIKE '%variante_neuve%'",
              (t["grille_id"],))[0]["n"] == 2
    # Les deux-points séparent au PREMIER : « heure : 10:30 ».
    r4 = poser(client, t, region_id=case, nouvelle_entree={"libelle": "heure : 10:30"})
    assert r4["entree_cle"] == "heure", r4
    assert _q(db_path, "SELECT libelle FROM grille_variante WHERE cle = ?",
              (r4["variante_cle"],)) == [{"libelle": "10:30"}]


@pytest.mark.parametrize("libelle", ["lieu :", ": forêt", " : "])
def test_nom_valeur_demande_ses_deux_cotes(client, decor, db_path, libelle):
    t = _travail(client, decor, db_path)
    r = poser(client, t, attendu=(422,), region_id=t["zones"]["case"],
              nouvelle_entree={"libelle": libelle})
    assert "nom : valeur" in r["detail"], r
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille_entree e JOIN grille_version v "
                       "ON v.id = e.version_id WHERE v.grille_id = ?",
              (t["grille_id"],))[0]["n"] == 0


def test_une_entree_sans_variantes_ne_recoit_pas_de_valeur(client, decor, db_path):
    t = _travail(client, decor, db_path)
    case = t["zones"]["case"]
    poser(client, t, region_id=case, nouvelle_entree={"libelle": "ironie"})
    r = poser(client, t, attendu=(422,), region_id=t["zones"]["cartouche"],
              nouvelle_entree={"libelle": "Ironie : mordante"})
    assert "sans variantes" in r["detail"], r
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille_variante x JOIN grille_version v "
                       "ON v.id = x.version_id WHERE v.grille_id = ?",
              (t["grille_id"],))[0]["n"] == 0


def test_la_variante_se_dit_une_fois(client, decor, db_path):
    t = _travail(client, decor, db_path)
    poser(client, t, region_id=t["zones"]["case"], nouvelle_entree={"libelle": "lieu : forêt"})
    r = poser(client, t, attendu=(422,), region_id=t["zones"]["cartouche"],
              nouvelle_entree={"libelle": "lieu : grotte"}, variante_cle="foret")
    assert "une fois" in r["detail"], r


def test_dans_une_grille_fermee_nom_valeur_ne_cree_rien(client, decor, db_path):
    """La grille du décor est fermée : « Créer » n'y existe pas, deux-points ou non."""
    r = poser(client, decor, attendu=(422,), region_id=bulle(decor),
              nouvelle_entree={"libelle": "lieu : forêt"}, mots=[0])
    assert "lieu" not in {e["cle"] for e in _q(
        db_path, "SELECT e.cle FROM grille_entree e JOIN grille_version v ON v.id = e.version_id "
                 "WHERE v.grille_id = ?", (decor["grille_id"],))}, r


def test_une_grille_ouverte_importee_recoit_aussi_ses_variables(client, decor, db_path):
    """Pas seulement la grille de travail : toute grille OUVERTE (G14)."""
    g = grille_active(client, decor["p"], entrees=csv_de([["cle", "forme", "libelle"],
                                                          ["vu", "simple", "vu"]]),
                      listes=None, nom="Libre", ouverte=True)
    d = {**decor, **g}
    r = poser(client, d, region_id=bulle(d), nouvelle_entree={"libelle": "ton : ironique"},
              mots=[0])
    assert r["entree_cle"] == "ton" and r["variante_cle"] == "ironique", r


# --------------------------------------------------------------------------- #
# L'ÉTAT d'une entrée (v39 ; J4, Hugo, 2026-11-06) et le drapeau de la grille de travail (J2)
# --------------------------------------------------------------------------- #
def _etats(db_path, grille_id):
    return {r["cle"]: r["etat"] for r in _q(
        db_path, "SELECT e.cle, e.etat FROM grille_entree e JOIN grille_version v "
                 "ON v.id = e.version_id WHERE v.grille_id = ?", (grille_id,))}


def test_une_entree_nee_en_posant_est_provisoire_une_entree_ecrite_definie(client, decor,
                                                                           db_path):
    """J4 : provisoire SEULEMENT pour ce qu'on a tapé en posant (« nom : valeur » compris) ;
    ce qu'on importe ou écrit au formulaire est défini, même dans une grille OUVERTE."""
    t = _travail(client, decor, db_path)
    poser(client, t, region_id=t["zones"]["case"], nouvelle_entree={"libelle": "ironie"})
    poser(client, t, region_id=t["zones"]["cartouche"],
          nouvelle_entree={"libelle": "lieu : forêt"})
    r = client.post(f"/api/grilles/{t['grille_id']}/entrees", headers=ADMIN,
                    json={"libelle": "écrite au formulaire"})
    assert r.status_code == 201, r.text
    assert _etats(db_path, t["grille_id"]) == {
        "ironie": "provisoire", "lieu": "provisoire", "ecrite-au-formulaire": "defini"}
    # Importée dans une grille ouverte : définie.
    g = grille_active(client, decor["p"], entrees=csv_de([["cle", "forme", "libelle"],
                                                          ["vu", "simple", "vu"]]),
                      listes=None, nom="Libre", ouverte=True)
    assert _etats(db_path, g["grille_id"]) == {"vu": "defini"}
    # Le plan le rend.
    plan = client.get(f"/api/grilles/{t['grille_id']}/versions/1", headers=ADMIN).json()
    assert {e["cle"]: e["etat"] for e in plan["entrees"]}["ironie"] == "provisoire"


def test_les_responsables_changent_l_etat_avec_la_valeur_vue(client, decor, db_path):
    t = _travail(client, decor, db_path)
    poser(client, t, region_id=t["zones"]["case"], nouvelle_entree={"libelle": "ironie"})
    url = f"/api/grilles/{t['grille_id']}/entrees/ironie"
    r = client.patch(url, headers=ADMIN, json={"etat": "fini"})
    assert r.status_code == 422 and "état" in r.text, r.text
    r = client.patch(url, headers=ADMIN, json={"etat": "defini", "vu": {"etat": "provisoire"}})
    assert r.status_code == 200, r.text
    assert _etats(db_path, t["grille_id"]) == {"ironie": "defini"}
    # Une valeur vue périmée : le 409 de CONC-3.
    r = client.patch(url, headers=ADMIN, json={"etat": "provisoire",
                                               "vu": {"etat": "provisoire"}})
    assert r.status_code == 409, r.text
    assert _etats(db_path, t["grille_id"]) == {"ironie": "defini"}
    r = client.patch(url, headers=ADMIN, json={"etat": "provisoire", "vu": {"etat": "defini"}})
    assert r.status_code == 200, r.text
    # Réimporter la grille ne change pas l'état d'une entrée qu'elle porte déjà — provisoire,
    # quand l'import écrit DÉFINI —, et une entrée neuve du fichier naît définie.
    importer(client, decor["p"], LEA, grille_id=t["grille_id"], ouverte=True, porte_sur=None,
             listes=None, entrees=csv_de([["cle", "forme", "libelle"],
                                          ["ironie", "simple", "ironie"],
                                          ["neuve", "simple", "neuve"]]))
    assert _etats(db_path, t["grille_id"]) == {"ironie": "provisoire", "neuve": "defini"}


def test_la_grille_de_travail_se_designe_par_son_drapeau(client, db_path):
    """J2 : renommée, elle reste LA grille de travail — rejouée, l'installation ne double
    rien —, et part encore avec son projet vide ; une AUTRE grille vide retient son projet."""
    pid = client.post("/api/projets", headers=ADMIN, json={"nom": "Drapeau"}).json()["id"]
    g = _grille_de_travail(db_path, pid)
    r = client.patch(f"/api/grilles/{g['id']}", headers=ADMIN, json={"nom": "Mes étiquettes"})
    assert r.status_code == 200, r.text
    actives = client.get(f"/api/projets/{pid}/grilles", headers=ADMIN).json()["actives"]
    assert [(a["nom"], a["travail"]) for a in actives] == [("Mes étiquettes", True)]
    conn = database.get_connection()
    try:
        import grille_import
        assert grille_import.installer_grille_de_travail(conn, pid) is None
    finally:
        conn.close()
    autre = client.post(f"/api/projets/{pid}/grilles", headers=ADMIN,
                        json={"nom": "Vide", "ouverte": True, "porte_sur": "case"})
    assert autre.status_code == 201, autre.text
    r = client.delete(f"/api/projets/{pid}", headers=ADMIN)
    assert r.status_code == 409 and "grille" in r.json()["detail"], r.text
    assert client.delete(f"/api/grilles/{autre.json()['grille_id']}",
                         headers=ADMIN).status_code == 204
    r = client.delete(f"/api/projets/{pid}", headers=ADMIN)
    assert r.status_code in (200, 204), r.text
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille WHERE id = ?", (g["id"],))[0]["n"] == 0


# --------------------------------------------------------------------------- #
# J2 : la grille de travail ne se désactive, ne se retire ni ne se supprime
# --------------------------------------------------------------------------- #
# Repris du test de reproduction de la relecture croisée de la v39 (Q4) : désactivée, une
# grille de travail qui portait une étiquette se SUPPRIMAIT, et celle qui portait un relevé
# se RETIRAIT ; rien ne rend ensuite une grille de travail au projet.
def _sql(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    try:
        r = c.execute(sql, p).fetchall()
        c.commit()
        return r
    finally:
        c.close()


def test_la_grille_de_travail_ne_se_desactive_pas(client, decor, db_path):
    from grilles_decor import LEA
    t = _travail(client, decor, db_path)
    r = client.delete(f"/api/projets/{decor['p']}/grilles/{t['grille_id']}/activation",
                      headers=LEA)
    assert r.status_code == 409 and "grille de travail" in r.json()["detail"], r.text
    assert _sql(db_path, "SELECT COUNT(*) FROM projet_grille WHERE grille_id = ?",
                (t["grille_id"],))[0][0] == 1
    # Une autre grille, oui.
    r = client.delete(f"/api/projets/{decor['p']}/grilles/{decor['grille_id']}/activation",
                      headers=LEA)
    assert r.status_code == 204, r.text


def test_la_grille_de_travail_porteuse_d_une_etiquette_ne_se_supprime_pas(client, decor,
                                                                           db_path):
    """Désactivée par une base d'avant (la route le refuse désormais) : elle ne se supprime
    pas pour autant, vide de relevés mais portant « ironie »."""
    from grilles_decor import LEA
    t = _travail(client, decor, db_path)
    r = poser(client, t, region_id=t["zones"]["case"], nouvelle_entree={"libelle": "ironie"})
    assert client.delete(f"/api/releves/{r['id']}", headers=LEA).status_code in (200, 204)
    gid, p = t["grille_id"], decor["p"]
    _sql(db_path, "DELETE FROM projet_grille WHERE grille_id = ?", (gid,))
    r = client.delete(f"/api/grilles/{gid}", headers=LEA)
    assert r.status_code == 409 and "grille de travail" in r.json()["detail"], r.text
    assert _sql(db_path, "SELECT COUNT(*) FROM grille WHERE projet_id = ? AND travail = 1",
                (p,))[0][0] == 1


def test_la_grille_de_travail_porteuse_de_releves_ne_se_retire_pas(client, decor, db_path):
    from grilles_decor import LEA
    t = _travail(client, decor, db_path)
    poser(client, t, region_id=t["zones"]["case"], nouvelle_entree={"libelle": "ironie"})
    gid = t["grille_id"]
    _sql(db_path, "DELETE FROM projet_grille WHERE grille_id = ?", (gid,))
    r = client.post(f"/api/grilles/{gid}/retrait", headers=LEA)
    assert r.status_code == 409 and "grille de travail" in r.json()["detail"], r.text
    assert _sql(db_path, "SELECT retiree_le FROM grille WHERE id = ?", (gid,))[0][0] is None


def test_une_grille_de_travail_vide_ne_se_supprime_pas_non_plus(client, db_path):
    """Le plus prudent : vide aussi — rien ne la rendrait au projet. Elle part avec lui."""
    pid = client.post("/api/projets", headers=ADMIN, json={"nom": "Vide"}).json()["id"]
    gid = _sql(db_path, "SELECT id FROM grille WHERE projet_id = ? AND travail = 1",
               (pid,))[0][0]
    _sql(db_path, "DELETE FROM projet_grille WHERE grille_id = ?", (gid,))
    assert client.delete(f"/api/grilles/{gid}", headers=ADMIN).status_code == 409
    assert client.post(f"/api/grilles/{gid}/retrait", headers=ADMIN).status_code == 409
    assert client.delete(f"/api/projets/{pid}", headers=ADMIN).status_code in (200, 204)
    assert _sql(db_path, "SELECT COUNT(*) FROM grille WHERE id = ?", (gid,))[0][0] == 0
