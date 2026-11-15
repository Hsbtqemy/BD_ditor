"""La règle d'un relevé dans une version (ANN-7, la montée de version ; cadrage
`docs/ann7-montee-de-version-cadrage.md`, §3 et §9, commit 1).

`grilles.causes_dans_la_version` dit, en Python, ce que la vue `releves_effectifs` dit en SQL :
les causes qu'une VERSION donne à un relevé. Les deux s'accordent ici, cas par cas — chaque
ligne de la table du §3 qui touche un relevé —, et chaque cas dit aussi l'issue que la table
attend : sans quoi deux écritures fausses de la même façon s'accorderaient encore.

Chaque cas écrit une version « d'arrivée » en base (`grille_import.ecrire_version`) et y pose
un relevé tel qu'il arriverait d'une version d'avant : la règle lit ce plan relu
(`grilles.contenu`), la vue la même ligne.
"""
import copy
import sqlite3

import pytest

import grille_import
import grilles


def _entree(forme="simple", **kw):
    e = {"rubrique_cle": "r", "rang": 0, "forme": forme, "libelle": kw.pop("libelle", "e"),
         "definition": None, "structure": None, "piege": None, "precision": None,
         "lien": False, "cible": None, "cardinalite": None, "liste_cle": None,
         "retiree": False, "exemples": [], "variantes": {}}
    e.update(kw)
    return e


def _variante(libelle):
    return {"libelle": libelle, "definition": None, "structure": None, "piege": None,
            "rang": 0, "exemples": []}


def _case(libelle):
    return {"libelle": libelle, "definition": None, "rang": 0}


# La version d'AVANT : une entrée de chaque forme, et de chaque sorte de pose.
AVANT = {
    "cible": "mots",
    "rubriques": {"r": {"libelle": "R", "parent_cle": None, "rang": 0}},
    "entrees": {
        "simple": _entree(),
        "var": _entree("variantes", variantes={"a": _variante("a"), "b": _variante("b")}),
        "qual": _entree("qualificatifs", liste_cle="l"),
        "zone": _entree(cible="bulle|cartouche|texte"),
        "surface": _entree(cible="planche"),
        "case": _entree(cible="case"),
    },
    "listes": {"l": {"libelle": "L", "qualificatifs": {"x": _case("x"), "y": _case("y")}}},
}

# Un relevé de chaque sorte, tel qu'il est posé dans AVANT.
MOTS = {"entree_cle": "simple", "planche": False, "type_region": "bulle", "mots": True}
ZONE = {"entree_cle": "zone", "planche": False, "type_region": "bulle", "mots": False}
SURFACE = {"entree_cle": "surface", "planche": True, "type_region": None, "mots": False}
CASE = {"entree_cle": "case", "planche": False, "type_region": "case", "mots": False}
VAR = {**MOTS, "entree_cle": "var", "variante_cle": "a"}
QUAL = {**MOTS, "entree_cle": "qual", "qualificatifs": ["x"]}


def _e(c, cle):
    return c["entrees"][cle]


def _cas():
    """(nom, ce qui change de AVANT à l'arrivée, le relevé, les causes attendues)."""
    def ch(f):
        def appliquer():
            c = copy.deepcopy(AVANT)
            f(c)
            return c
        return appliquer

    return [
        ("rien ne change", ch(lambda c: None), VAR, []),
        ("une coquille", ch(lambda c: _e(c, "simple").update(definition="mieux")), MOTS, []),
        ("l'entrée renommée", ch(lambda c: _e(c, "simple").update(libelle="autre")), MOTS, []),
        ("l'entrée change de rubrique", ch(lambda c: (
            c["rubriques"].update(s={"libelle": "S", "parent_cle": None, "rang": 1}),
            _e(c, "simple").update(rubrique_cle="s"))), MOTS, []),
        ("une variante renommée", ch(lambda c: _e(c, "var")["variantes"]["a"].update(
            libelle="A")), VAR, []),
        ("une variante ajoutée", ch(lambda c: _e(c, "var")["variantes"].update(
            c=_variante("c"))), VAR, []),
        ("une case renommée", ch(lambda c: c["listes"]["l"]["qualificatifs"]["x"].update(
            libelle="X")), QUAL, []),
        ("une case ajoutée", ch(lambda c: c["listes"]["l"]["qualificatifs"].update(
            z=_case("z"))), QUAL, []),
        ("l'entrée retirée", ch(lambda c: _e(c, "simple").update(retiree=True)), MOTS,
         ["entree_absente"]),
        ("l'entrée disparue de la version", ch(lambda c: c["entrees"].pop("simple")), MOTS,
         ["entree_absente"]),
        ("une variante employée disparue", ch(lambda c: _e(c, "var")["variantes"].pop("a")),
         VAR, ["variante_absente"]),
        ("une case cochée disparue", ch(lambda c: c["listes"]["l"]["qualificatifs"].pop("x")),
         QUAL, ["case_absente"]),
        ("simple → à variantes", ch(lambda c: _e(c, "simple").update(
            forme="variantes", variantes={"a": _variante("a")})), MOTS,
         ["variante_manquante"]),
        ("à variantes → simple, sous une variante", ch(lambda c: _e(c, "var").update(
            forme="simple", variantes={})), VAR, ["variante_sans_place"]),
        ("à qualificatifs → simple", ch(lambda c: _e(c, "qual").update(
            forme="simple", liste_cle=None)), QUAL, ["case_sans_place"]),
        ("à qualificatifs → à variantes", ch(lambda c: _e(c, "qual").update(
            forme="variantes", liste_cle=None, variantes={"a": _variante("a")})), QUAL,
         ["case_sans_place", "variante_manquante"]),
        ("simple → à qualificatifs", ch(lambda c: _e(c, "simple").update(
            forme="qualificatifs", liste_cle="l")), MOTS, []),
        ("la liste de l'entrée change, la case cochée y est", ch(lambda c: (
            c["listes"].update(m={"libelle": "M", "qualificatifs": {"x": _case("x")}}),
            _e(c, "qual").update(liste_cle="m"))), QUAL, []),
        ("la liste de l'entrée change, la case cochée n'y est pas", ch(lambda c: (
            c["listes"].update(m={"libelle": "M", "qualificatifs": {"z": _case("z")}}),
            _e(c, "qual").update(liste_cle="m"))), QUAL, ["case_absente"]),
        ("« une » → « plusieurs »", ch(lambda c: _e(c, "zone").update(cardinalite="plusieurs")),
         ZONE, []),
        ("« Porte sur » : le type ne convient plus", ch(lambda c: _e(c, "case").update(
            cible="personnage")), CASE, ["type_change"]),
        ("« Porte sur » : la version change, le type convient encore", ch(lambda c: c.update(
            cible="bulle|cartouche|texte")), {**MOTS, "entree_cle": "simple"}, ["pose_changee"]),
        ("« Porte sur » : des mots → toute la zone", ch(lambda c: _e(c, "simple").update(
            cible="bulle")), MOTS, ["pose_changee"]),
        ("« Porte sur » : toute la zone → des mots", ch(lambda c: _e(c, "zone").update(
            cible="mots")), ZONE, ["pose_changee"]),
        ("« Porte sur » : la planche → une zone", ch(lambda c: _e(c, "surface").update(
            cible="case")), SURFACE, ["pose_changee"]),
        ("« Porte sur » : une zone → la planche", ch(lambda c: _e(c, "case").update(
            cible="planche")), CASE, ["type_change"]),
        ("« Porte sur » : des mots → une case", ch(lambda c: _e(c, "simple").update(
            cible="case")), MOTS, ["type_change", "pose_changee"]),
        ("une précision devient attendue", ch(lambda c: _e(c, "simple").update(
            precision="où")), MOTS, ["precision_manquante"]),
        ("un lien devient attendu", ch(lambda c: _e(c, "simple").update(lien=True)), MOTS,
         ["lien_manquant"]),
        ("la précision n'est plus demandée", ch(lambda c: None),
         {**MOTS, "precision": "reste"}, []),
        ("une entrée retirée garde ses autres causes", ch(lambda c: _e(c, "simple").update(
            retiree=True, precision="où")), MOTS, ["entree_absente", "precision_manquante"]),
        ("une entrée naît", ch(lambda c: c["entrees"].update(neuve=_entree())), MOTS, []),
    ]


CAS = _cas()


@pytest.mark.parametrize("cas", CAS, ids=[c[0] for c in CAS])
def test_la_regle_et_la_vue_disent_la_meme_chose(db_path, client, planche, cas):
    _nom, arrivee, releve, attendues = cas
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        pid = c.execute("SELECT id FROM projet LIMIT 1").fetchone()[0]
        gid = c.execute("INSERT INTO grille (projet_id, nom, identifiant) VALUES (?, 'x', "
                        "'00000000-0000-4000-8000-000000000001')", (pid,)).lastrowid
        vid = grille_import.ecrire_version(c, gid, arrivee(), numero=2, etat="publiee",
                                           note=None, par=None)
        texte = "UN DEUX TROIS"
        rg = None
        if not releve["planche"]:
            rg = c.execute("INSERT INTO regions (planche_id, type, ocr_texte) VALUES (?, ?, ?)",
                           (planche["id"], releve["type_region"], texte)).lastrowid
        rid = c.execute(
            "INSERT INTO releve (region_id, planche_id, grille_id, version_id, entree_cle, "
            "variante_cle, precision, texte_ancre) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (rg, planche["id"] if releve["planche"] else None, gid, vid, releve["entree_cle"],
             releve.get("variante_cle"), releve.get("precision"),
             texte if releve["mots"] else None)).lastrowid
        if releve["mots"]:
            c.execute("INSERT INTO releve_mot (releve_id, position, rang, forme) "
                      "VALUES (?, 0, 0, 'UN')", (rid,))
        for q in releve.get("qualificatifs") or []:
            c.execute("INSERT INTO releve_qualificatif (releve_id, qualificatif_cle) "
                      "VALUES (?, ?)", (rid, q))
        vue = c.execute("SELECT * FROM releves_effectifs WHERE id = ?", (rid,)).fetchone()
        selon_la_vue = [x for x in grilles.CAUSES_A_REVOIR_DE_VERSION
                        + grilles.CAUSES_A_COMPLETER_DE_VERSION if vue[x]]
        selon_la_regle = grilles.causes_dans_la_version(grilles.contenu(c, vid), releve)
        assert selon_la_regle == attendues
        assert selon_la_vue == selon_la_regle
        assert vue["etat"] == grilles.etat_des_causes(selon_la_regle)
    finally:
        c.rollback()
        c.close()


def test_chaque_cause_de_version_est_jouee():
    """Aucune cause qui dépend de la version n'échappe aux cas : une cause neuve sans cas
    s'accorderait par son absence des deux côtés."""
    jouees = {x for cas in CAS for x in cas[3]}
    assert jouees == set(grilles.CAUSES_A_REVOIR_DE_VERSION
                         + grilles.CAUSES_A_COMPLETER_DE_VERSION)


def test_l_etat_suit_les_causes():
    assert grilles.etat_des_causes([]) == "normal"
    assert grilles.etat_des_causes(["precision_manquante"]) == "a_completer"
    assert grilles.etat_des_causes(["variante_manquante"]) == "a_completer"
    assert grilles.etat_des_causes(["variante_manquante", "case_absente"]) == "a_revoir"
    assert grilles.etat_des_causes(["mot_perdu"]) == "a_revoir"


def test_convient_ce_qui_se_rendrait_dans_la_version():
    """Ce que Ctrl+Z lit pour rendre un relevé dans la version active : une précision qui
    manque ne l'empêche pas ; une valeur qui n'a plus sa place, si."""
    c = copy.deepcopy(AVANT)
    assert grilles.convient(c, VAR)
    _e(c, "simple")["precision"] = "où"
    assert grilles.convient(c, MOTS)
    c["entrees"]["var"]["variantes"].pop("a")
    assert not grilles.convient(c, VAR)
    _e(c, "simple")["retiree"] = True
    assert not grilles.convient(c, MOTS)
    _e(c, "zone")["cible"] = "mots"
    assert not grilles.convient(c, ZONE)
    _e(c, "qual")["forme"] = "variantes"
    assert not grilles.convient(c, {**MOTS, "entree_cle": "qual"})   # une valeur manque
