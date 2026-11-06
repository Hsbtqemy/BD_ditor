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
from grilles_decor import LEA, STAG, csv_de, grille_active
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
                "SELECT g.id, g.ouverte, g.cree_par, v.numero, v.etat, v.cible, "
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
    assert "grille" in r.json()["detail"], r.json()


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
