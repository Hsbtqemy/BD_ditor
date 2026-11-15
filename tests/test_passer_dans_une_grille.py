"""« PASSER DANS UNE GRILLE… » — une étiquette du Mode libre passe, avec ses relevés, dans une
entrée d'une autre grille active du projet (ANN-7, J8 ; `docs/ann7-mode-libre-cadrage.md`,
« Structurer », et le §8 de `docs/ann7-montee-de-version-cadrage.md`).

Le décor : le projet P, sa grille de TRAVAIL (le Mode libre), et le modèle FICTIF
(`tools/grille-modele.csv`), « Signaux », FERMÉE, publié en v1 et actif. La stagiaire pose dans
le Mode libre ; la responsable de P (Léa) fait passer. Chaque relevé se relit en base.
"""
import json
import sqlite3

import grilles
import undo
from conftest import make_png
from grilles_decor import ANA, LEA, OLGA, SAM, STAG, ZOE, ok
from test_grille_de_travail import _travail
from test_releves import bulle, decor, poser  # noqa: F401


def _q(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, p)]
    finally:
        c.close()


def _releve(db_path, rid):
    return _q(db_path, "SELECT * FROM releve WHERE id = ?", (rid,))[0]


def _etiquettes(db_path, region_id):
    r = _q(db_path, "SELECT etiquettes FROM recherche WHERE region_id = ?", (region_id,))
    return r[0]["etiquettes"] if r else None


def url(t, cle):
    return f"/api/grilles/{t['grille_id']}/entrees/{cle}/passage"


def apercu(client, t, cle, qui=LEA, attendu=200, **params):
    if "variantes" in params:
        params["variantes"] = json.dumps(params["variantes"])
    r = client.get(url(t, cle), headers=qui, params=params)
    assert r.status_code == attendu, r.text[:800]
    return r.json()


def passer(client, t, cle, *, vers, dans, vu=None, variantes=None, qui=LEA, attendu=200):
    corps = {"vers": vers, "dans": dans}
    if vu is not None:
        corps["vu"] = vu
    if variantes is not None:
        corps["variantes"] = variantes
    r = client.post(url(t, cle), headers=qui, json=corps)
    assert r.status_code == attendu, r.text[:800]
    return r.json()


def _signaux(t):
    return t["signaux"]


def _decor_j8(client, decor, db_path):
    t = _travail(client, decor, db_path)
    return {**t, "signaux": decor["grille_id"]}


def _versions(db_path):
    return _q(db_path, "SELECT COUNT(*) AS n FROM grille_version")[0]["n"]


# --------------------------------------------------------------------------- #
# Qui, et où
# --------------------------------------------------------------------------- #
def test_seule_la_responsable_fait_passer(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    poser(client, t, region_id=bulle(t), nouvelle_entree={"libelle": "voix : crié"})
    a = apercu(client, t, "voix")
    assert a["verdict"]["etat"] == "choisir_grille"
    assert [g["nom"] for g in a["grilles"]] == ["Signaux"]
    for qui in (STAG, SAM, ANA, OLGA):                # ils lisent la grille, sans gérer P
        r = client.get(url(t, "voix"), headers=qui)
        assert r.status_code == 403, (qui, r.text)
        assert "responsables du projet" in r.json()["detail"]
        r = client.post(url(t, "voix"), headers=qui,
                        json={"vers": _signaux(t), "dans": "ton-de-voix"})
        assert r.status_code == 403, (qui, r.text)
    # Qui ne voit pas la grille : introuvable, comme une grille qui n'existe pas.
    assert client.get(url(t, "voix"), headers=ZOE).status_code == 404
    # Une étiquette qui n'existe pas.
    assert client.get(url(t, "nulle-part"), headers=LEA).status_code == 404


def test_on_ne_passe_qu_une_etiquette_du_mode_libre(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    r = client.get(f"/api/grilles/{_signaux(t)}/entrees/cri/passage", headers=LEA)
    assert r.status_code == 409 and "Mode libre" in r.json()["detail"], r.text


# --------------------------------------------------------------------------- #
# Le bilan, puis le passage
# --------------------------------------------------------------------------- #
def test_le_bilan_propose_puis_le_passage_deplace_les_releves(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    b = bulle(t)
    sur_bulle = poser(client, t, region_id=b, nouvelle_entree={"libelle": "voix : crié"})
    sur_case = poser(client, t, region_id=t["zones"]["case"], entree_cle="voix",
                     variante_cle=sur_bulle["variante_cle"])
    assert "crié" in (_etiquettes(db_path, b) or "")
    versions = _versions(db_path)
    passes_avant = _q(db_path, "SELECT * FROM passe ORDER BY id")

    a = apercu(client, t, "voix", vers=_signaux(t))
    assert a["verdict"]["etat"] == "choisir_entree"
    assert a["propose"] is None                      # aucune entrée « voix » dans Signaux
    assert "brouillon" in a["verdict"]["phrase"] and "montez la version" in a["verdict"]["phrase"]
    assert "ton-de-voix" in [e["cle"] for e in a["entrees"]]

    a = apercu(client, t, "voix", vers=_signaux(t), dans="ton-de-voix")
    # La valeur est proposée par son libellé : « crié » → « crie ».
    (ligne,) = a["correspondance"]
    assert ligne["de"]["libelle"] == "crié" and ligne["propose"] == ligne["vers"] == "crie"
    assert a["releves"] == {"total": 2, "passent": 1, "restent": 1, "a_completer": 0}
    (reste,) = a["restent"]
    assert reste["cause"] == "type_change" and reste["n"] == 1
    assert reste["zones"] == [{"album_id": t["album"], "planche_id": t["planche"],
                               "region_id": t["zones"]["case"]}]
    assert a["verdict"]["etat"] == "passable" and a["videe"] is False
    assert a["verdict"]["phrase"].startswith(
        "1 relevé passe dans « Signaux › ton de voix ». 1 reste dans le Mode libre.")
    texte = json.dumps(a)
    assert "lea" not in texte and "stag" not in texte          # aucun login

    # Sans `vu`, le passage attend qu'on ait lu le bilan.
    refus = passer(client, t, "voix", vers=_signaux(t), dans="ton-de-voix", attendu=409)
    assert "relisez" in refus["detail"]["message"] and refus["detail"]["vu"] == a["vu"]
    fait = passer(client, t, "voix", vers=_signaux(t), dans="ton-de-voix", vu=a["vu"])
    assert (fait["passes"], fait["restent"], fait["videe"]) == (1, 1, False)

    v1 = grilles.version(sqlite3.connect(db_path), _signaux(t), 1)
    passe = _releve(db_path, sur_bulle["id"])
    assert (passe["grille_id"], passe["version_id"], passe["entree_cle"], passe["variante_cle"],
            passe["une"]) == (_signaux(t), v1[0], "ton-de-voix", "crie", 1)
    assert passe["auteur"] == "stag" and passe["modifie_par"] is None    # toujours à elle
    reste = _releve(db_path, sur_case["id"])
    assert (reste["grille_id"], reste["entree_cle"]) == (t["grille_id"], "voix")
    # Aucune version ne naît, aucune passe ne bouge.
    assert _versions(db_path) == versions
    assert _q(db_path, "SELECT * FROM passe ORDER BY id") == passes_avant
    # Les étiquettes de la bulle quittent l'index : une grille fermée n'y entre pas.
    assert "crié" not in (_etiquettes(db_path, b) or "")
    # Le relevé se lit dans Signaux, normal.
    rs = ok(client.get(f"/api/planches/{t['planche']}/releves", headers=STAG))["releves"]
    vu = next(r for r in rs if r["id"] == sur_bulle["id"])
    assert (vu["grille_id"], vu["etat"], vu["version"]) == (_signaux(t), "normal", 1)


def test_le_journal_un_acte_fusion_par_releve_et_un_acte_qui_resume(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    b = bulle(t)
    r = poser(client, t, region_id=b, nouvelle_entree={"libelle": "voix : crié"})
    autrui_avant = ok(client.get(f"/api/albums/{t['album']}/travail-des-autres", headers=OLGA))
    a = apercu(client, t, "voix", vers=_signaux(t), dans="ton-de-voix")
    passer(client, t, "voix", vers=_signaux(t), dans="ton-de-voix", vu=a["vu"])
    (resume,) = _q(db_path, "SELECT * FROM evenement WHERE cible_table = 'grille' "
                            "AND cible_id = ? AND apres LIKE '%passee_dans%'", (t["grille_id"],))
    ap = json.loads(resume["apres"])["passee_dans"]
    assert ap["vers"] == {"grille_id": _signaux(t), "version": 1, "entree": "ton-de-voix"}
    assert ap["releve_ids"] == [r["id"]] and ap["variantes"] == {r["variante_cle"]: "crie"}
    (acte,) = _q(db_path, "SELECT * FROM evenement WHERE type = ?", (grilles.ACTE_FUSION,))
    assert (acte["cible_table"], acte["cible_id"], acte["agent"]) == ("releve", b, "lea")
    av, apres = json.loads(acte["avant"]), json.loads(acte["apres"])
    assert (av["grille_id"], apres["grille_id"]) == (t["grille_id"], _signaux(t))
    assert (av["entree_cle"], apres["entree_cle"]) == ("voix", "ton-de-voix")
    assert apres["fusion"]["acte"] == resume["id"]
    assert apres["fusion"]["vers"] == {"grille_id": _signaux(t), "version": 1}
    # Ni Ctrl+Z ne l'offre, ni « qui perd quoi » ne le compte.
    for qui in (LEA, STAG):
        p = client.get("/api/undo/prochain", headers=qui).json()
        assert p is None or p["evenement_id"] not in (acte["id"], resume["id"]), p
    autrui = ok(client.get(f"/api/albums/{t['album']}/travail-des-autres", headers=OLGA))
    assert autrui["travail_des_autres"] == autrui_avant["travail_des_autres"], autrui
    gestes = {x["agent"]: x["gestes"] for x in autrui["travail_des_autres"]}
    assert not {"releve", "releve_planche"} & set(gestes.get("lea", {})), gestes


def test_une_etiquette_videe_se_propose_au_retrait(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    poser(client, t, region_id=bulle(t), nouvelle_entree={"libelle": "voix : crié"})
    a = apercu(client, t, "voix", vers=_signaux(t), dans="ton-de-voix")
    assert a["videe"] is True and "sera vide" in a["verdict"]["phrase"]
    fait = passer(client, t, "voix", vers=_signaux(t), dans="ton-de-voix", vu=a["vu"])
    assert fait["videe"] is True
    # Elle n'est pas retirée d'office : elle se propose, et personne ne la pose plus.
    plan = ok(client.get(f"/api/grilles/{t['grille_id']}/versions/{t['numero']}?emplois=1",
                         headers=LEA))
    assert "voix" in [e["cle"] for e in plan["entrees"]]
    assert plan["emplois"]["entrees"].get("voix", 0) == 0
    a = apercu(client, t, "voix")
    assert a["verdict"]["etat"] == "rien_a_passer"


# --------------------------------------------------------------------------- #
# Ce qui reste, et pourquoi
# --------------------------------------------------------------------------- #
def test_une_entree_une_seule_fois_deja_posee_retient_le_releve(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    b = bulle(t)
    ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": _signaux(t), "version": 1, "region_id": b, "entree_cle": "ton-de-voix",
        "variante_cle": "chuchote"}), 201)
    r = poser(client, t, region_id=b, nouvelle_entree={"libelle": "voix : crié"})
    a = apercu(client, t, "voix", vers=_signaux(t), dans="ton-de-voix")
    assert [x["cause"] for x in a["restent"]] == ["deja_pose"]
    assert a["verdict"]["etat"] == "rien_a_passer"
    refus = passer(client, t, "voix", vers=_signaux(t), dans="ton-de-voix", vu=a.get("vu"),
                   attendu=409)
    assert "Rien ne passe" in refus["detail"]["message"]
    assert _releve(db_path, r["id"])["grille_id"] == t["grille_id"]


def test_deux_releves_vers_une_entree_une_seule_fois_restent_tous_les_deux(client, decor,
                                                                            db_path):
    t = _decor_j8(client, decor, db_path)
    b = bulle(t)
    poser(client, t, region_id=b, nouvelle_entree={"libelle": "voix : crié"})
    poser(client, t, region_id=b, nouvelle_entree={"libelle": "voix : chuchoté"})
    a = apercu(client, t, "voix", vers=_signaux(t), dans="ton-de-voix")
    assert [(x["cause"], x["n"]) for x in a["restent"]] == [("en_double", 2)]
    assert a["releves"]["passent"] == 0


def test_une_valeur_sans_equivalent_reste_et_la_table_la_corrige(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    r = poser(client, t, region_id=bulle(t), nouvelle_entree={"libelle": "voix : murmure"})
    a = apercu(client, t, "voix", vers=_signaux(t), dans="ton-de-voix")
    (ligne,) = a["correspondance"]
    assert ligne["propose"] is None and ligne["vers"] is None
    assert [x["cause"] for x in a["restent"]] == ["sans_equivalent"]
    table = {r["variante_cle"]: "chuchote"}
    a = apercu(client, t, "voix", vers=_signaux(t), dans="ton-de-voix", variantes=table)
    assert a["correspondance"][0]["vers"] == "chuchote" and a["releves"]["passent"] == 1
    passer(client, t, "voix", vers=_signaux(t), dans="ton-de-voix", vu=a["vu"],
           variantes=table)
    assert _releve(db_path, r["id"])["variante_cle"] == "chuchote"
    # Une valeur qui n'est pas de l'entrée d'arrivée : 422, rien ne passe.
    r2 = poser(client, t, region_id=t["zones"]["cartouche"],
               nouvelle_entree={"libelle": "voix : grave"})
    faux = {r2["variante_cle"]: "inexistante"}
    a = apercu(client, t, "voix", vers=_signaux(t), dans="ton-de-voix", variantes=faux)
    assert a["verdict"]["etat"] == "a_corriger"
    passer(client, t, "voix", vers=_signaux(t), dans="ton-de-voix", vu=a["vu"],
           variantes=faux, attendu=422)


def test_une_etiquette_sans_valeur_recoit_une_valeur_ou_reste(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    r = poser(client, t, region_id=bulle(t), nouvelle_entree={"libelle": "crié"})
    a = apercu(client, t, "crie", vers=_signaux(t), dans="ton-de-voix")
    (ligne,) = a["correspondance"]
    # Proposée par le nom de l'étiquette.
    assert ligne["de"] == {"cle": None, "libelle": None, "releves": 1}
    assert ligne["vers"] == "crie" and a["releves"]["passent"] == 1
    # Sans valeur choisie : « choisissez une valeur », il reste.
    a = apercu(client, t, "crie", vers=_signaux(t), dans="ton-de-voix", variantes={"": None})
    assert [x["cause"] for x in a["restent"]] == ["variante_manquante"]
    a = apercu(client, t, "crie", vers=_signaux(t), dans="ton-de-voix")
    passer(client, t, "crie", vers=_signaux(t), dans="ton-de-voix", vu=a["vu"])
    assert _releve(db_path, r["id"])["variante_cle"] == "crie"


def test_une_valeur_vers_une_entree_simple_reste(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    poser(client, t, region_id=t["zones"]["case"], nouvelle_entree={"libelle": "regard : direct"})
    a = apercu(client, t, "regard", vers=_signaux(t), dans="regard-camera")
    assert [x["cause"] for x in a["restent"]] == ["variante_sans_place"]


def test_des_mots_ne_passent_pas_dans_une_entree_de_toute_la_zone(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    # Une étiquette du Mode libre qui se pose sur des mots s'écrit au formulaire.
    ok(client.post(f"/api/grilles/{t['grille_id']}/entrees", headers=LEA,
                   json={"libelle": "voix", "forme": "variantes", "cible": "mots",
                         "variantes": [{"libelle": "crié"}]}), 201)
    poser(client, t, region_id=bulle(t), mots=[8], entree_cle="voix", variante_cle="crie")
    a = apercu(client, t, "voix", vers=_signaux(t), dans="ton-de-voix")
    (x,) = a["restent"]
    assert (x["cause"], x["designe"]) == ("pose_changee", "mots")


def test_la_planche_passe_dans_une_entree_de_la_planche(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    ok(client.post(f"/api/grilles/{t['grille_id']}/entrees", headers=LEA,
                   json={"libelle": "fond sonore", "forme": "simple", "cible": "planche"}), 201)
    r = poser(client, t, planche_id=t["planche"], entree_cle="fond-sonore")
    a = apercu(client, t, "fond-sonore", vers=_signaux(t), dans="ambiance")
    assert a["releves"]["passent"] == 1
    passer(client, t, "fond-sonore", vers=_signaux(t), dans="ambiance", vu=a["vu"])
    x = _releve(db_path, r["id"])
    assert (x["grille_id"], x["entree_cle"], x["planche_id"]) == (_signaux(t), "ambiance",
                                                                  t["planche"])


def test_un_lien_attendu_a_l_arrivee_passe_a_completer(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    r = poser(client, t, region_id=bulle(t), nouvelle_entree={"libelle": "répond"})
    a = apercu(client, t, "repond", vers=_signaux(t), dans="reponse-a")
    assert a["releves"] == {"total": 1, "passent": 1, "restent": 0, "a_completer": 1}
    assert [x["cause"] for x in a["a_completer"]] == ["lien_manquant"]
    passer(client, t, "repond", vers=_signaux(t), dans="reponse-a", vu=a["vu"])
    rs = ok(client.get(f"/api/planches/{t['planche']}/releves", headers=STAG))["releves"]
    vu = next(x for x in rs if x["id"] == r["id"])
    assert (vu["etat"], vu["causes"]) == ("a_completer", ["lien_manquant"])


def test_une_entree_absente_le_bilan_dit_de_monter(client, decor, db_path):
    """L'entrée d'arrivée n'est pas dans la version active : le bilan le dit, et rien ne
    naît. Une version publiée plus récente qui la porte : il ne reste qu'à monter."""
    t = _decor_j8(client, decor, db_path)
    poser(client, t, region_id=bulle(t), nouvelle_entree={"libelle": "voix : crié"})
    a = apercu(client, t, "voix", vers=_signaux(t), dans="inconnue")
    assert a["verdict"]["etat"] == "entree_absente"
    assert "écrivez-la dans le brouillon, publiez, montez la version" in a["verdict"]["phrase"]
    passer(client, t, "voix", vers=_signaux(t), dans="inconnue", vu="x", attendu=409)
    # Une v2 publiée qui porte « voix » : « montez la version, puis revenez ».
    import copy
    import grille_import
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        v1 = grilles.version(c, _signaux(t), 1)
        contenu = copy.deepcopy(grilles.contenu(c, v1["id"]))
        e = copy.deepcopy(contenu["entrees"]["cri"])
        e["libelle"], e["rang"] = "voix", 99
        contenu["entrees"]["voix"] = e
        grille_import.ecrire_version(c, _signaux(t), contenu, numero=2,
                                     etat=grilles.ETAT_PUBLIEE, note=None, par="lea")
        c.commit()
    finally:
        c.close()
    versions = _versions(db_path)
    a = apercu(client, t, "voix", vers=_signaux(t))
    assert "la version 2 la porte" in a["verdict"]["phrase"], a["verdict"]
    a = apercu(client, t, "voix", vers=_signaux(t), dans="voix")
    assert a["verdict"]["etat"] == "entree_absente"
    assert "la version 2 la porte" in a["verdict"]["phrase"]
    assert _versions(db_path) == versions


# --------------------------------------------------------------------------- #
# Deux écrans (CONC-3)
# --------------------------------------------------------------------------- #
def test_un_bilan_qui_a_change_se_relit(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    poser(client, t, region_id=bulle(t), nouvelle_entree={"libelle": "voix : crié"})
    a = apercu(client, t, "voix", vers=_signaux(t), dans="ton-de-voix")
    # Entre-temps, la stagiaire pose la même étiquette ailleurs.
    poser(client, t, region_id=t["zones"]["cartouche"], entree_cle="voix",
          variante_cle=_q(db_path, "SELECT variante_cle FROM releve "
                                   "WHERE entree_cle = 'voix'")[0]["variante_cle"])
    refus = passer(client, t, "voix", vers=_signaux(t), dans="ton-de-voix", vu=a["vu"],
                   attendu=409)
    assert refus["detail"]["releves"]["total"] == 2 and refus["detail"]["vu"] != a["vu"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM releve WHERE grille_id = ?",
              (_signaux(t),))[0]["n"] == 0


# --------------------------------------------------------------------------- #
# Ctrl+Z des gestes d'avant
# --------------------------------------------------------------------------- #
def test_defaire_la_pose_d_une_etiquette_passee_nomme_qui_l_a_passee(client, decor, db_path):
    """Même clé d'entrée à l'arrivée, même valeur : seule la GRILLE a changé — sans elle,
    défaire la pose retirait de Signaux, sans rien dire, le relevé qu'on y a passé."""
    t = _decor_j8(client, decor, db_path)
    r = poser(client, t, region_id=bulle(t), nouvelle_entree={"libelle": "ton de voix : crié"})
    assert (r["entree_cle"], r["variante_cle"]) == ("ton-de-voix", "crie")
    a = apercu(client, t, "ton-de-voix", vers=_signaux(t), dans="ton-de-voix")
    passer(client, t, "ton-de-voix", vers=_signaux(t), dans="ton-de-voix", vu=a["vu"])
    p = ok(client.get("/api/undo/prochain", headers=STAG))
    assert p["description"] == "pose d'un relevé", p
    r409 = client.post("/api/undo", headers=STAG, json={"evenement_id": p["evenement_id"]})
    assert r409.status_code == 409, r409.text
    detail = r409.json()["detail"]
    assert detail["conflit"]["champ"] == "grille_id" and "Lea Responsable" in detail["message"]
    assert "la grille a été modifiée" in detail["message"], detail
    assert _releve(db_path, r["id"])["grille_id"] == _signaux(t)      # rien n'est défait


def test_defaire_une_retouche_d_une_etiquette_passee_nomme_qui_l_a_passee(client, decor,
                                                                           db_path):
    """Même clé d'entrée à l'arrivée, même valeur : seule la GRILLE dit que le relevé a changé
    de mains — sans elle, Ctrl+Z défaisait dans Signaux une retouche faite dans le Mode
    libre."""
    t = _decor_j8(client, decor, db_path)
    b = bulle(t)
    # Dans le Mode libre, une étiquette « ton de voix » de même clé que celle de Signaux.
    r = poser(client, t, region_id=b, nouvelle_entree={"libelle": "ton de voix : crié"})
    assert r["entree_cle"] == "ton-de-voix"
    ok(client.post(f"/api/grilles/{t['grille_id']}/entrees/ton-de-voix/variantes",
                   headers=STAG, json={"libelle": "chuchoté"}), 201)
    ok(client.put(f"/api/releves/{r['id']}", headers=STAG,
                  json={"variante_cle": "chuchote", "vu": {"variante_cle": r["variante_cle"]}}))
    a = apercu(client, t, "ton-de-voix", vers=_signaux(t), dans="ton-de-voix")
    assert a["correspondance"][0]["vers"] == "chuchote"
    passer(client, t, "ton-de-voix", vers=_signaux(t), dans="ton-de-voix", vu=a["vu"])
    p = ok(client.get("/api/undo/prochain", headers=STAG))
    r409 = client.post("/api/undo", headers=STAG, json={"evenement_id": p["evenement_id"]})
    assert r409.status_code == 409, r409.text
    detail = r409.json()["detail"]
    assert detail["conflit"]["champ"] == "grille_id" and "Lea Responsable" in detail["message"]
    assert _releve(db_path, r["id"])["variante_cle"] == "chuchote"


def test_le_releve_reste_celui_de_qui_l_a_pose(client, decor, db_path):
    t = _decor_j8(client, decor, db_path)
    r = poser(client, t, region_id=bulle(t), nouvelle_entree={"libelle": "voix : crié"})
    a = apercu(client, t, "voix", vers=_signaux(t), dans="ton-de-voix")
    passer(client, t, "voix", vers=_signaux(t), dans="ton-de-voix", vu=a["vu"])
    c = sqlite3.connect(db_path)
    try:
        (d_un_autre,) = c.execute(f"SELECT {undo._SQL_RELEVE_D_UN_AUTRE} FROM releve r "
                                  "WHERE r.id = ?", ("stag", "stag", r["id"])).fetchone()
    finally:
        c.close()
    assert not d_un_autre


def test_les_releves_de_toutes_les_planches_passent(client, decor, db_path):
    """Le périmètre est le projet : les relevés de l'étiquette sur toutes ses planches."""
    t = _decor_j8(client, decor, db_path)
    pl2 = ok(client.post(f"/api/albums/{t['album']}/import", headers=LEA,
                         files={"file": ("q.png", make_png(), "image/png")}), 201)["id"]
    r1 = poser(client, t, region_id=bulle(t), nouvelle_entree={"libelle": "voix : crié"})
    b2 = ok(client.post(f"/api/planches/{pl2}/regions", headers=LEA,
                        json={"type": "bulle", "x": 1, "y": 1, "w": 5, "h": 5}), 201)["id"]
    r2 = poser(client, t, region_id=b2, entree_cle="voix", variante_cle=r1["variante_cle"])
    a = apercu(client, t, "voix", vers=_signaux(t), dans="ton-de-voix")
    assert a["releves"]["passent"] == 2
    passer(client, t, "voix", vers=_signaux(t), dans="ton-de-voix", vu=a["vu"])
    assert {_releve(db_path, x["id"])["grille_id"] for x in (r1, r2)} == {_signaux(t)}


def test_vers_une_grille_ouverte_les_etiquettes_suivent_dans_l_index(client, decor, db_path):
    """La grille d'arrivée OUVERTE est dans l'index : la région porte ses libellés après le
    passage, et plus ceux du Mode libre."""
    from grilles_decor import grille_active
    t = _decor_j8(client, decor, db_path)
    o = grille_active(client, t["p"], nom="Sons ouverts", ouverte=True, porte_sur="bulle")
    b = bulle(t)
    poser(client, t, region_id=b, nouvelle_entree={"libelle": "voix : crié"})
    assert _etiquettes(db_path, b) == "voix crié"
    a = apercu(client, t, "voix", vers=o["grille_id"], dans="ton-de-voix")
    assert a["vers"]["ouverte"] is True and a["releves"]["passent"] == 1
    passer(client, t, "voix", vers=o["grille_id"], dans="ton-de-voix", vu=a["vu"])
    assert _etiquettes(db_path, b) == "ton de voix crié"


def test_la_meme_valeur_deux_fois_sur_une_zone_reste(client, decor, db_path):
    """Vers une entrée « plusieurs » : deux valeurs du Mode libre qui iraient à la même valeur
    d'arrivée sur une même zone restent toutes deux (le doublon de J3) ; une valeur déjà posée
    à l'arrivée sur la zone retient la sienne."""
    from grilles_decor import grille_active
    t = _decor_j8(client, decor, db_path)
    o = grille_active(client, t["p"], nom="Sons ouverts", ouverte=True, porte_sur="bulle")
    ok(client.post(f"/api/grilles/{o['grille_id']}/entrees", headers=LEA,
                   json={"libelle": "bruit", "forme": "variantes", "cardinalite": "plusieurs",
                         "variantes": [{"libelle": "choc"}, {"libelle": "souffle"}]}), 201)
    b = bulle(t)
    bang = poser(client, t, region_id=b, nouvelle_entree={"libelle": "son : bang"})
    boum = poser(client, t, region_id=b, nouvelle_entree={"libelle": "son : boum"})
    table = {bang["variante_cle"]: "choc", boum["variante_cle"]: "choc"}
    a = apercu(client, t, "son", vers=o["grille_id"], dans="bruit", variantes=table)
    assert [(x["cause"], x["n"]) for x in a["restent"]] == [("meme_valeur", 2)]
    # À des valeurs distinctes, les deux passent.
    table = {bang["variante_cle"]: "choc", boum["variante_cle"]: "souffle"}
    a = apercu(client, t, "son", vers=o["grille_id"], dans="bruit", variantes=table)
    assert a["releves"]["passent"] == 2
    # « bruit : choc » déjà posé sur la bulle : celui qui y irait reste.
    ok(client.post("/api/releves", headers=STAG, json={
        "grille_id": o["grille_id"], "version": 1, "region_id": b, "entree_cle": "bruit",
        "variante_cle": "choc"}), 201)
    a = apercu(client, t, "son", vers=o["grille_id"], dans="bruit", variantes=table)
    assert [(x["cause"], x["n"]) for x in a["restent"]] == [("deja_pose", 1)]
    assert a["releves"]["passent"] == 1
