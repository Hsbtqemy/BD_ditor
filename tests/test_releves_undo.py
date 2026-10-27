"""Ctrl+Z et les relevés (ANN-7, tranche 1 ; cadrage R10).

Ctrl+Z défait poser, modifier, retirer un relevé ; une suppression de région rend ses relevés
et ses passes. Les gardes sont celles des autres tables : hors de portée → passé (première
phrase) ; grille désactivée ou entrée disparue → passé (seconde phrase) ; valeur changée
depuis par un autre → le 409 de CONC-3, que « Passer ce geste » franchit. Un doute, une passe,
ne s'annulent pas : Ctrl+Z les saute.
"""
import sqlite3

import pytest

from conftest import ADMIN, du_projet

from grilles_decor import LEA, STAG, grille_active, monter, ok


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


def poser(client, d, qui=STAG, **champs):
    r = client.post("/api/releves", headers=qui,
                    json={"grille_id": d["grille_id"], "version": 1, **champs})
    assert r.status_code == 201, r.text
    return r.json()


def undo(client, qui=STAG, attendu=(200,)):
    r = client.post("/api/undo", headers=qui)
    assert r.status_code in attendu, (r.status_code, r.text[:500])
    return r.json()


def test_ctrl_z_defait_une_pose(client, decor, db_path):
    poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    assert ok(client.get("/api/undo/prochain", headers=STAG))["description"] == \
        "pose d'un relevé"
    res = undo(client)
    assert res["cible_table"] == "releve" and res["region_id"] == decor["zones"]["bulle"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0


def test_ctrl_z_defait_une_pose_de_surface(client, decor, db_path):
    poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    res = undo(client)
    assert res["planche_id"] == decor["planche"] and res["region_id"] is None
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0


def test_ctrl_z_d_un_releve_de_surface_demande_d_ecrire_sa_planche(client, decor, db_path):
    """Les lieux d'un acte `releve_planche` sont sa PLANCHE, pas une région du même numéro :
    c'est elle que la route éprouve en écriture sous la portée de la requête."""
    import undo
    poser(client, decor, planche_id=decor["planche"], entree_cle="ambiance")
    e = _q(db_path, "SELECT * FROM evenement WHERE cible_table = 'releve_planche' "
                    "ORDER BY id DESC LIMIT 1")[0]
    assert undo.lieux(None, e) == {"regions": [], "planches": [decor["planche"]],
                                   "personnages": []}


def test_ctrl_z_defait_une_modification_et_seulement_elle(client, decor, db_path):
    r = poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="origine-du-son",
              mots=[1], qualificatifs=["objet"])
    ok(client.put(f"/api/releves/{r['id']}", headers=STAG,
                  json={"qualificatifs": ["personnage"], "precision": "ici"}))
    undo(client)
    x = _q(db_path, "SELECT precision FROM releve")[0]
    assert x["precision"] is None
    assert [q["qualificatif_cle"] for q in _q(db_path, "SELECT qualificatif_cle FROM "
                                                     "releve_qualificatif")] == ["objet"]


def test_ctrl_z_rend_un_releve_retire_sous_son_identifiant_avec_son_doute(client, decor,
                                                                         db_path):
    r = poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[7, 5])
    ok(client.post(f"/api/releves/{r['id']}/doutes", headers=LEA, json={"texte": "Sûr ?"}),
       201)
    ok(client.delete(f"/api/releves/{r['id']}", headers=STAG), 204)
    undo(client)
    lus = ok(client.get(f"/api/planches/{decor['planche']}/releves", headers=LEA))["releves"]
    (x,) = lus
    assert x["id"] == r["id"] and [m["forme"] for m in x["mots"]] == ["NE", "PAS"]
    assert x["doute"]["messages"][0]["texte"] == "Sûr ?"


def test_un_doute_et_une_passe_ne_s_annulent_pas(client, decor, db_path):
    r = poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    ok(client.put(f"/api/regions/{decor['zones']['bulle']}/passes/{decor['grille_id']}",
                  headers=STAG, json={}))
    # Ctrl+Z saute la passe et défait la pose.
    assert ok(client.get("/api/undo/prochain", headers=STAG))["description"] == \
        "pose d'un relevé"
    assert r


def test_ctrl_z_ne_defait_pas_une_pose_qu_un_autre_a_changee(client, decor, db_path):
    r = poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="onomatopee",
              mots=[8], variante_cle="bang")
    ok(client.put(f"/api/releves/{r['id']}", headers=LEA, json={"variante_cle": "crac"}))
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "variante_cle"
    assert refus["conflit"]["auteur"]["login"] == "lea"
    assert refus["passable"]["evenement_id"]
    # « Passer ce geste » : l'acte sort de la pile, le relevé reste.
    ok(client.post("/api/undo/passer", headers=STAG,
                   json={"evenement_id": refus["passable"]["evenement_id"]}))
    assert _q(db_path, "SELECT variante_cle FROM releve")[0]["variante_cle"] == "crac"


def test_ctrl_z_ne_defait_pas_une_pose_sur_laquelle_un_autre_a_doute(client, decor):
    r = poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    ok(client.post(f"/api/releves/{r['id']}/doutes", headers=LEA, json={"texte": "?"}), 201)
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "doute"


def test_grille_desactivee_l_acte_est_passe(client, decor, db_path):
    poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    ok(client.delete(f"/api/projets/{decor['p']}/grilles/{decor['grille_id']}/activation",
                     headers=LEA), 204)
    refus = undo(client, attendu=(409,))["detail"]
    assert "ne peut plus être rétabli" in refus["message"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 1
    assert _q(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE type = 'abandon'")[0][
        "n"] == 1


def test_hors_de_portee_l_acte_est_passe(client, decor, db_path):
    poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="cri", mots=[8])
    ok(client.delete(f"/api/collections/{decor['c']}/acces/utilisateur/stag", headers=LEA), 204)
    du_projet(client, decor['c2'], "utilisateur", "stag", headers=ADMIN)
    ok(client.put(f"/api/collections/{decor['c2']}/acces", headers=LEA,
                  json={"genre": "utilisateur", "principal": "stag", "niveau": "ecriture"}))
    refus = undo(client, attendu=(409,))["detail"]
    assert "n'est plus à votre portée" in refus["message"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 1


def test_une_region_rendue_rend_ses_releves_et_ses_passes(client, decor, db_path):
    b = decor["zones"]["bulle"]
    r = poser(client, decor, region_id=b, entree_cle="cri", mots=[8])
    ok(client.put(f"/api/regions/{b}/passes/{decor['grille_id']}", headers=STAG, json={}))
    ok(client.delete(f"/api/regions/{b}", headers=STAG), 204)
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0
    res = undo(client)
    assert "releves_non_rendus" not in res
    assert [x["id"] for x in _q(db_path, "SELECT id FROM releve")] == [r["id"]]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM passe")[0]["n"] == 1


def test_une_region_rendue_ne_rend_pas_les_releves_d_une_grille_desactivee(client, decor,
                                                                         db_path):
    b = decor["zones"]["bulle"]
    poser(client, decor, region_id=b, entree_cle="cri", mots=[8])
    ok(client.delete(f"/api/regions/{b}", headers=STAG), 204)
    ok(client.delete(f"/api/projets/{decor['p']}/grilles/{decor['grille_id']}/activation",
                     headers=LEA), 204)
    res = undo(client)
    assert res["releves_non_rendus"] == 1
    assert _q(db_path, "SELECT COUNT(*) AS n FROM regions WHERE id = ?", (b,))[0]["n"] == 1
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve")[0]["n"] == 0


def test_un_lien_perdu_puis_rendu_redevient_normal(client, decor):
    """Le relevé dont la région LIÉE disparaît n'est pas touché ; Ctrl+Z de cette suppression
    le rattache sans rien écrire."""
    r = poser(client, decor, region_id=decor["zones"]["bulle"], entree_cle="reponse-a",
              lien_region_id=decor["autre_bulle"])
    ok(client.delete(f"/api/regions/{decor['autre_bulle']}", headers=STAG), 204)
    undo(client)
    lus = ok(client.get(f"/api/planches/{decor['planche']}/releves", headers=LEA))["releves"]
    assert next(x for x in lus if x["id"] == r["id"])["etat"] == "normal"


def test_ctrl_z_ne_defait_pas_une_modification_qu_un_autre_a_recouverte(client, decor,
                                                                        db_path):
    r = poser(client, decor, qui=LEA, region_id=decor["zones"]["bulle"],
              entree_cle="onomatopee", mots=[8], variante_cle="bang")
    ok(client.put(f"/api/releves/{r['id']}", headers=STAG, json={"variante_cle": "crac"}))
    ok(client.put(f"/api/releves/{r['id']}", headers=LEA, json={"variante_cle": "splash"}))
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "variante_cle"
    assert _q(db_path, "SELECT variante_cle FROM releve")[0]["variante_cle"] == "splash"


# --------------------------------------------------------------------------- #
# Ctrl+Z d'une CRÉATION de région et les relevés qui vivent dessus (relecture croisée,
# constat 1) — le CASCADE de `_supprimer_region` les emportait sans instantané, en 200.
# --------------------------------------------------------------------------- #
def _bulle_de_la_stagiaire(client, d):
    return ok(client.post(f"/api/planches/{d['planche']}/regions", headers=STAG,
                          json={"type": "bulle", "x": 50, "y": 50, "w": 9, "h": 9}), 201)["id"]


def test_ctrl_z_d_une_creation_ne_supprime_pas_le_releve_ni_la_passe_d_un_autre(client, decor,
                                                                                db_path):
    rid = _bulle_de_la_stagiaire(client, decor)
    poser(client, decor, qui=LEA, region_id=rid, entree_cle="ton-de-voix", variante_cle="crie")
    ok(client.put(f"/api/regions/{rid}/passes/{decor['grille_id']}", headers=LEA, json={}))
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "releve"
    assert refus["conflit"]["auteur"]["login"] == "lea"
    assert refus["message"].startswith("Conflit : le relevé a été modifié par Lea Responsable")
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve WHERE region_id = ?", (rid,))[0][
        "n"] == 1
    assert _q(db_path, "SELECT COUNT(*) AS n FROM passe WHERE region_id = ?", (rid,))[0][
        "n"] == 1
    # « Passer ce geste » : la création sort de la pile, la bulle et son travail restent.
    ok(client.post("/api/undo/passer", headers=STAG,
                   json={"evenement_id": refus["passable"]["evenement_id"]}))
    assert _q(db_path, "SELECT COUNT(*) AS n FROM regions WHERE id = ?", (rid,))[0]["n"] == 1
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve WHERE region_id = ?", (rid,))[0][
        "n"] == 1


def test_ctrl_z_d_une_creation_garde_une_passe_seule(client, decor, db_path):
    rid = _bulle_de_la_stagiaire(client, decor)
    ok(client.put(f"/api/regions/{rid}/passes/{decor['grille_id']}", headers=LEA, json={}))
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "passe" and refus["passable"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM passe WHERE region_id = ?", (rid,))[0][
        "n"] == 1


def test_ctrl_z_d_une_creation_n_est_pas_bloque_par_sa_propre_passe(client, decor, db_path):
    """RENVERSÉ par le pilotage le 2026-10-26 (contre-relecture, r5) : ce test exigeait que sa
    propre passe rende sa création inannulable (« quel qu'en soit l'auteur »). La doctrine de
    CONC-4 pour la situation l'emporte — la marquer sur sa propre zone ne doit pas rendre sa
    création inannulable : la passe part avec la région. Celle d'un autre bloque toujours."""
    rid = _bulle_de_la_stagiaire(client, decor)
    ok(client.put(f"/api/regions/{rid}/passes/{decor['grille_id']}", headers=STAG, json={}))
    undo(client)
    assert _q(db_path, "SELECT COUNT(*) AS n FROM regions WHERE id = ?", (rid,))[0]["n"] == 0
    assert _q(db_path, "SELECT COUNT(*) AS n FROM passe WHERE region_id = ?", (rid,))[0][
        "n"] == 0


def test_ctrl_z_d_une_creation_bloque_par_la_passe_d_un_autre_a_cote_de_la_sienne(
        client, decor, db_path):
    rid = _bulle_de_la_stagiaire(client, decor)
    ok(client.put(f"/api/regions/{rid}/passes/{decor['grille_id']}", headers=STAG, json={}))
    ok(client.put(f"/api/regions/{rid}/passes/{decor['grille_id']}", headers=LEA,
                  json={"rubrique_cle": "echanges"}))
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "passe"
    assert refus["conflit"]["auteur"]["login"] == "lea"


def test_le_409_d_une_creation_nomme_l_auteur_du_releve_et_non_le_dernier_acte(client, decor,
                                                                              db_path):
    """Contre-relecture, r1 : la stagiaire marque une passe APRÈS le relevé de Léa ; le refus
    nommait la stagiaire elle-même (le dernier acte sous la cible `releve`)."""
    rid = _bulle_de_la_stagiaire(client, decor)
    poser(client, decor, qui=LEA, region_id=rid, entree_cle="ton-de-voix", variante_cle="crie")
    ok(client.put(f"/api/regions/{rid}/passes/{decor['grille_id']}", headers=STAG, json={}))
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "releve"
    assert refus["conflit"]["auteur"]["login"] == "lea"
    assert refus["conflit"]["auteur"]["meme_compte"] is False


def test_le_409_d_une_creation_ne_nomme_pas_son_propre_releve_annule(client, decor, db_path):
    """Contre-relecture, r1b : son propre relevé, annulé d'abord, ne se nomme plus."""
    rid = _bulle_de_la_stagiaire(client, decor)
    poser(client, decor, qui=LEA, region_id=rid, entree_cle="ton-de-voix", variante_cle="crie")
    poser(client, decor, qui=STAG, region_id=rid, entree_cle="reponse-a",
          lien_region_id=decor["autre_bulle"])
    undo(client)                                   # défait son relevé
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["auteur"]["login"] == "lea"


def test_ctrl_z_d_une_creation_garde_le_lien_entrant_d_un_autre(client, decor, db_path):
    """Contre-relecture, r2 : Léa pose sur une AUTRE bulle un relevé qui désigne la bulle de la
    stagiaire par son lien ; annuler la création le laissait « à revoir », en 200."""
    rid = _bulle_de_la_stagiaire(client, decor)
    r = poser(client, decor, qui=LEA, region_id=decor["zones"]["bulle"],
              entree_cle="reponse-a", lien_region_id=rid)
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "lien_region_id"
    assert refus["conflit"]["auteur"]["login"] == "lea" and refus["passable"]
    assert refus["message"].startswith("Conflit : le lien a été modifié par Lea Responsable")
    assert _q(db_path, "SELECT COUNT(*) AS n FROM regions WHERE id = ?", (rid,))[0]["n"] == 1
    assert _q(db_path, "SELECT lien_region_id FROM releve WHERE id = ?", (r["id"],)) == [
        {"lien_region_id": rid}]


def test_ctrl_z_d_une_creation_garde_le_releve_d_un_descendant(client, decor, db_path):
    case = ok(client.post(f"/api/planches/{decor['planche']}/regions", headers=STAG,
                          json={"type": "case", "x": 40, "y": 40, "w": 50, "h": 50}),
              201)["id"]
    bulle = ok(client.post(f"/api/planches/{decor['planche']}/regions", headers=LEA,
                           json={"type": "bulle", "x": 45, "y": 45, "w": 9, "h": 9,
                                 "parent_id": case}), 201)["id"]
    poser(client, decor, qui=LEA, region_id=bulle, entree_cle="ton-de-voix",
          variante_cle="crie")
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "releve"
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve WHERE region_id = ?", (bulle,))[0][
        "n"] == 1


def test_ctrl_z_d_une_creation_garde_le_releve_d_une_grille_desactivee(client, decor,
                                                                       db_path):
    """« Désactiver ne supprime aucun relevé » : il se lit encore, et une annulation ne
    l'emporte pas davantage."""
    rid = _bulle_de_la_stagiaire(client, decor)
    poser(client, decor, qui=LEA, region_id=rid, entree_cle="ton-de-voix", variante_cle="crie")
    ok(client.delete(f"/api/projets/{decor['p']}/grilles/{decor['grille_id']}/activation",
                     headers=LEA), 204)
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "releve"
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve WHERE region_id = ?", (rid,))[0][
        "n"] == 1


def test_ctrl_z_d_une_creation_sans_releve_passe_toujours(client, decor, db_path):
    rid = _bulle_de_la_stagiaire(client, decor)
    undo(client)
    assert _q(db_path, "SELECT COUNT(*) AS n FROM regions WHERE id = ?", (rid,))[0]["n"] == 0


def test_le_409_d_un_autre_releve_une_se_lit_en_mots(client, decor, db_path):
    """Constat 6 — le champ `releve` a son libellé : le refus ne dit plus « releve »."""
    b = decor["zones"]["bulle"]
    r = poser(client, decor, region_id=b, entree_cle="ton-de-voix", variante_cle="crie")
    ok(client.delete(f"/api/releves/{r['id']}", headers=STAG), 204)
    poser(client, decor, qui=LEA, region_id=b, entree_cle="ton-de-voix",
          variante_cle="chuchote")
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "releve"
    assert refus["message"] == (
        "Conflit : le relevé a été modifié par Lea Responsable, le "
        f"{refus['conflit']['auteur']['le']} (UTC) depuis que vous l'avez vu. "
        "Votre modification n'est pas enregistrée.")


# --------------------------------------------------------------------------- #
# `regions.nom` (v37, G17 ; relecture croisée, constat 5) — Ctrl+Z le rend
# --------------------------------------------------------------------------- #
def test_ctrl_z_d_une_suppression_de_region_rend_son_nom(client, decor, db_path):
    """Le nom libre d'une zone (aucune route ne l'écrit encore : SQL) revient avec elle."""
    b = decor["autre_bulle"]
    c = sqlite3.connect(db_path)
    c.execute("UPDATE regions SET nom = 'le téléphone' WHERE id = ?", (b,))
    c.commit()
    c.close()
    ok(client.delete(f"/api/regions/{b}", headers=STAG), 204)
    e = _q(db_path, "SELECT avant FROM evenement WHERE cible_table = 'regions' "
                    "AND type = 'suppression' ORDER BY id DESC LIMIT 1")[0]
    assert '"nom": "le téléphone"' in e["avant"]
    undo(client)
    assert _q(db_path, "SELECT nom FROM regions WHERE id = ?", (b,)) == [
        {"nom": "le téléphone"}]


def test_ctrl_z_d_une_modification_de_region_garde_son_nom(client, decor, db_path):
    b = decor["autre_bulle"]
    c = sqlite3.connect(db_path)
    c.execute("UPDATE regions SET nom = 'l''affiche' WHERE id = ?", (b,))
    c.commit()
    c.close()
    ok(client.put(f"/api/regions/{b}", headers=STAG, json={"ocr_texte": "OH"}))
    undo(client)
    assert _q(db_path, "SELECT nom, ocr_texte FROM regions WHERE id = ?", (b,)) == [
        {"nom": "l'affiche", "ocr_texte": None}]


# --------------------------------------------------------------------------- #
# Contre-relecture n°2 — une retouche de soi ne fait pas passer le relevé d'un autre pour le
# sien (n1, n2)
# --------------------------------------------------------------------------- #
def test_ctrl_z_d_une_retouche_rend_qui_avait_modifie_le_releve(client, decor, db_path):
    """n2 — Léa pose, la stagiaire retouche puis annule : `modifie_par` revient à ce qu'il
    était, et le refus de la création nomme Léa, pas la stagiaire."""
    rid = _bulle_de_la_stagiaire(client, decor)
    r = poser(client, decor, qui=LEA, region_id=rid, entree_cle="ton-de-voix",
              variante_cle="crie")
    ok(client.put(f"/api/releves/{r['id']}", headers=STAG,
                  json={"variante_cle": "chuchote", "vu": {"variante_cle": "crie"}}))
    undo(client)
    assert _q(db_path, "SELECT variante_cle, modifie_par, modifie_le FROM releve WHERE id = ?",
              (r["id"],)) == [{"variante_cle": "crie", "modifie_par": None,
                               "modifie_le": None}]
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["auteur"]["login"] == "lea"


def test_le_lien_entrant_retouche_par_soi_bloque_encore(client, decor, db_path):
    """n1 — le relevé de Léa qui désigne la bulle, retouché par la stagiaire puis rétabli par
    Ctrl+Z, reste celui de Léa : la création ne s'annule pas."""
    rid = _bulle_de_la_stagiaire(client, decor)
    r = poser(client, decor, qui=LEA, region_id=decor["zones"]["bulle"],
              entree_cle="reponse-a", lien_region_id=rid)
    ok(client.put(f"/api/releves/{r['id']}", headers=STAG,
                  json={"lien_region_id": decor["autre_bulle"]}))
    undo(client)
    assert _q(db_path, "SELECT lien_region_id, modifie_par FROM releve WHERE id = ?",
              (r["id"],)) == [{"lien_region_id": rid, "modifie_par": None}]
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "lien_region_id"
    assert refus["conflit"]["auteur"]["login"] == "lea"
    assert _q(db_path, "SELECT COUNT(*) AS n FROM regions WHERE id = ?", (rid,))[0]["n"] == 1


def _retouche_restee(client, d, r, corps):
    """La stagiaire retouche le relevé de Léa, puis la grille est désactivée : son Ctrl+Z de
    la retouche est PASSÉ (seconde phrase), et `modifie_par` reste le sien."""
    ok(client.put(f"/api/releves/{r['id']}", headers=STAG, json=corps))
    ok(client.delete(f"/api/projets/{d['p']}/grilles/{d['grille_id']}/activation",
                     headers=LEA), 204)
    refus = undo(client, attendu=(409,))["detail"]
    assert "ne peut plus être rétabli" in refus["message"]


def test_un_lien_entrant_retouche_par_soi_reste_celui_d_un_autre(client, decor, db_path):
    """La garde lit l'AUTEUR du relevé, ou tout acte d'un autre à son journal — jamais le
    seul dernier retoucheur : la stagiaire a fait pointer le relevé de Léa sur sa bulle, et
    ce relevé reste celui de Léa."""
    rid = _bulle_de_la_stagiaire(client, decor)
    r = poser(client, decor, qui=LEA, region_id=decor["zones"]["bulle"],
              entree_cle="reponse-a", lien_region_id=decor["autre_bulle"])
    _retouche_restee(client, decor, r, {"lien_region_id": rid})
    assert _q(db_path, "SELECT modifie_par FROM releve WHERE id = ?", (r["id"],)) == [
        {"modifie_par": "stag"}]
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "lien_region_id"
    assert refus["conflit"]["auteur"]["login"] == "lea"


def test_le_409_nomme_l_auteur_et_non_le_dernier_retoucheur(client, decor, db_path):
    rid = _bulle_de_la_stagiaire(client, decor)
    r = poser(client, decor, qui=LEA, region_id=rid, entree_cle="ton-de-voix",
              variante_cle="crie")
    _retouche_restee(client, decor, r, {"variante_cle": "chuchote",
                                        "vu": {"variante_cle": "crie"}})
    refus = undo(client, attendu=(409,))["detail"]
    assert refus["conflit"]["champ"] == "releve"
    assert refus["conflit"]["auteur"]["login"] == "lea"
