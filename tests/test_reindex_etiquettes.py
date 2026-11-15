"""Les ÉTIQUETTES dans l'index plein texte, maintenues par chaque geste (ANN-7, le mode libre ;
`docs/ann7-mode-libre-cadrage.md`, « Maintenu par quels appels » ; J6, Hugo, 2026-11-06).

La v39 a posé la colonne `etiquettes` et l'a remplie une fois ; ce fichier vérifie qu'elle
reste juste : poser, modifier, retirer un relevé d'une grille OUVERTE, Ctrl+Z, renommer une
entrée, une variante, une case, fusionner, réimporter. Les grilles FERMÉES n'y entrent pas.

Et le CLIQUET : toute écriture de `releve` — et de ce qui change un libellé indexé : une
entrée, une variante, une case de liste — vit dans une fonction qui appelle
`reindex_etiquettes`, ou est DÉCLARÉE ici avec sa raison. Sans lui, une étiquette posée par un
chemin neuf serait introuvable sans que rien ne tombe. Il vérifie d'abord que ses motifs
mordent. Sa limite, écrite : il lit les LITTÉRAUX SQL ; une table nommée par une variable
(`f"DELETE FROM {t}"` d'`effacer_plan`, `retirer("releve")` de `repartir_de_zero`) lui échappe
— les deux sont tenus par leurs appelants, et le second est déclaré par son autre littéral.
"""
import ast
import pathlib
import re
import sqlite3

import database
from conftest import ADMIN
from grilles_decor import LEA, STAG, csv_de, grille_active
from test_grille_de_travail import _travail
from test_releves import bulle, decor, poser  # noqa: F401

RACINE = pathlib.Path(__file__).resolve().parent.parent


def _trouve(db_path, mot, colonne="etiquettes"):
    """Les régions que trouve `mot` (préfixe) dans une colonne de l'index."""
    c = sqlite3.connect(db_path)
    try:
        return sorted(r[0] for r in c.execute(
            "SELECT region_id FROM recherche WHERE recherche MATCH ?",
            (f'{colonne} : "{mot}"*',)))
    finally:
        c.close()


def _ligne(db_path, region_id):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        r = c.execute("SELECT * FROM recherche WHERE region_id = ?", (region_id,)).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


# --------------------------------------------------------------------------- #
# Poser, modifier, retirer, Ctrl+Z
# --------------------------------------------------------------------------- #
def test_poser_modifier_retirer_suivent_l_index(client, decor, db_path):
    t = _travail(client, decor, db_path)
    case = t["zones"]["case"]                    # une case : ni texte, ni note
    assert _ligne(db_path, case) is None
    r = poser(client, t, region_id=case, nouvelle_entree={"libelle": "lieu : forêt"})
    assert _trouve(db_path, "foret") == [case]   # sans accents, comme le texte
    assert _trouve(db_path, "lieu") == [case]
    assert _ligne(db_path, case)["lemmes"] == ""
    assert client.put(f"/api/releves/{r['id']}", headers=STAG,
                      json={"nouvelle_variante": "grotte"}).status_code == 200
    assert _trouve(db_path, "grotte") == [case] and _trouve(db_path, "foret") == []
    assert client.delete(f"/api/releves/{r['id']}", headers=STAG).status_code == 204
    assert _trouve(db_path, "lieu") == [] and _ligne(db_path, case) is None


def test_la_ligne_d_une_bulle_garde_son_texte_et_ses_lemmes(client, decor, db_path):
    t = _travail(client, decor, db_path)
    b = bulle(t)
    avant = _ligne(db_path, b)
    poser(client, t, region_id=b, nouvelle_entree={"libelle": "ironie"})
    apres = _ligne(db_path, b)
    assert apres["etiquettes"] == "ironie"
    assert {k: apres[k] for k in ("ocr_texte", "note", "lemmes")} == {
        k: avant[k] for k in ("ocr_texte", "note", "lemmes")}
    assert _trouve(db_path, "VIENT", "ocr_texte") == [b]


def test_la_levee_d_un_doute_qui_retire_desindexe(client, decor, db_path):
    t = _travail(client, decor, db_path)
    case = t["zones"]["case"]
    r = poser(client, t, region_id=case, nouvelle_entree={"libelle": "ironie"})
    d = client.post(f"/api/releves/{r['id']}/doutes", headers=STAG, json={"texte": "?"}).json()
    assert client.post(f"/api/doutes/{d['id']}/levee", headers=STAG,
                       json={"issue": "retire"}).status_code == 200
    assert _trouve(db_path, "ironie") == []


def test_ctrl_z_suit_l_index(client, decor, db_path):
    t = _travail(client, decor, db_path)
    case = t["zones"]["case"]
    r = poser(client, t, region_id=case, nouvelle_entree={"libelle": "lieu : forêt"})
    client.put(f"/api/releves/{r['id']}", headers=STAG, json={"nouvelle_variante": "grotte"})
    assert client.post("/api/undo", headers=STAG).status_code == 200      # la modification
    assert _trouve(db_path, "foret") == [case] and _trouve(db_path, "grotte") == []
    assert client.delete(f"/api/releves/{r['id']}", headers=STAG).status_code == 204
    assert client.post("/api/undo", headers=STAG).status_code == 200      # le retrait
    assert _trouve(db_path, "foret") == [case]
    # La pose — sa variante y était déjà : on remonte le retrait, puis la pose.
    assert client.post("/api/undo", headers=STAG).status_code == 200
    assert _trouve(db_path, "foret") == []


def test_ctrl_z_d_une_region_supprimee_rend_ses_etiquettes(client, decor, db_path):
    t = _travail(client, decor, db_path)
    case = t["zones"]["case"]
    poser(client, t, region_id=case, nouvelle_entree={"libelle": "ironie"})
    assert client.delete(f"/api/regions/{case}", headers=LEA).status_code in (200, 204)
    assert _trouve(db_path, "ironie") == []
    assert client.post("/api/undo", headers=LEA).status_code == 200
    assert _trouve(db_path, "ironie") == [case]


def test_une_grille_fermee_n_entre_pas_dans_l_index(client, decor, db_path):
    poser(client, decor, region_id=decor["zones"]["cartouche"], entree_cle="ton-de-voix",
          variante_cle="chuchote")
    assert _trouve(db_path, "chuchote") == [] and _trouve(db_path, "ton") == []


# --------------------------------------------------------------------------- #
# Un libellé qui change : renommer, fusionner, réimporter
# --------------------------------------------------------------------------- #
def test_renommer_une_entree_et_une_valeur_reecrit_les_etiquettes(client, decor, db_path):
    t = _travail(client, decor, db_path)
    case, b = t["zones"]["case"], bulle(t)
    poser(client, t, region_id=case, nouvelle_entree={"libelle": "lieu : forêt"})
    poser(client, t, region_id=b, nouvelle_entree={"libelle": "lieu : forêt"})
    g = t["grille_id"]
    assert client.patch(f"/api/grilles/{g}/entrees/lieu", headers=ADMIN,
                        json={"libelle": "endroit"}).status_code == 200
    assert _trouve(db_path, "endroit") == sorted([case, b]) and _trouve(db_path, "lieu") == []
    assert client.patch(f"/api/grilles/{g}/entrees/lieu/variantes/foret", headers=ADMIN,
                        json={"libelle": "bois"}).status_code == 200
    assert _trouve(db_path, "bois") == sorted([case, b]) and _trouve(db_path, "foret") == []


def test_renommer_une_case_de_liste_reecrit_les_etiquettes(client, decor, db_path):
    """Une grille OUVERTE importée (le modèle fictif, sur la bulle) : « écho » coché « hors
    champ » ; la case renommée se cherche sous son nom neuf."""
    g = grille_active(client, decor["p"], nom="Libre", ouverte=True, porte_sur="bulle")
    d = {**decor, **g}
    plan = client.get(f"/api/grilles/{g['grille_id']}/versions/1", headers=ADMIN).json()
    sources = next(l for l in plan["listes"] if l["cle"] == "sources")
    q = sources["qualificatifs"][0]
    poser(client, d, region_id=bulle(d), entree_cle="echo", qualificatifs=[q["cle"]])
    assert _trouve(db_path, "echo") == [bulle(d)]
    assert client.patch(f"/api/grilles/{g['grille_id']}/listes/sources/cases/{q['cle']}",
                        headers=ADMIN, json={"libelle": "lointain"}).status_code == 200
    assert _trouve(db_path, "lointain") == [bulle(d)]


def test_fusionner_reecrit_les_etiquettes_des_releves_passes(client, decor, db_path):
    t = _travail(client, decor, db_path)
    case = t["zones"]["case"]
    poser(client, t, region_id=case, nouvelle_entree={"libelle": "ironie"})
    poser(client, t, region_id=bulle(t), nouvelle_entree={"libelle": "humour"})
    r = client.post(f"/api/grilles/{t['grille_id']}/entrees/ironie/fusion", headers=ADMIN,
                    json={"dans": "humour"})
    assert r.status_code == 200, r.text
    assert _trouve(db_path, "ironie") == []
    assert _trouve(db_path, "humour") == sorted([case, bulle(t)])


def test_reimporter_une_grille_ouverte_reecrit_un_libelle_change(client, decor, db_path):
    from grilles_decor import importer
    entete = ["cle", "forme", "libelle"]
    g = grille_active(client, decor["p"], entrees=csv_de([entete, ["vu", "simple", "vu"]]),
                      listes=None, nom="Regards", ouverte=True, porte_sur="case")
    d = {**decor, **g}
    case = decor["zones"]["case"]
    poser(client, d, region_id=case, entree_cle="vu")
    importer(client, decor["p"], LEA, entrees=csv_de([entete, ["vu", "simple", "aperçu"]]),
             listes=None, grille_id=g["grille_id"], ouverte=True, porte_sur="case")
    assert _trouve(db_path, "apercu") == [case]


# --------------------------------------------------------------------------- #
# reindex_etiquettes, seule
# --------------------------------------------------------------------------- #
def test_reindex_etiquettes_ignore_une_region_disparue_et_ne_touche_rien_d_autre(db_path):
    conn = database.get_connection()
    try:
        database.reindex_etiquettes(conn, [987654, None])          # ni lève, ni écrit
        assert conn.execute("SELECT COUNT(*) FROM recherche WHERE region_id = 987654"
                            ).fetchone()[0] == 0
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Le CLIQUET
# --------------------------------------------------------------------------- #
_TABLES = ("releve", "releve_qualificatif", "grille_entree", "grille_variante",
           "grille_qualificatif")
_ECRITURE = re.compile(r"\b(?:INSERT\s+(?:OR\s+\w+\s+)?INTO|UPDATE|DELETE\s+FROM)\s+("
                       + "|".join(_TABLES) + r")\b", re.IGNORECASE)
_RELAIS = "reindex_etiquettes"

# Les écritures qui n'appellent pas `reindex_etiquettes`, chacune avec sa raison.
DECLAREES = {
    ("database.py", "_migrate"):
        "la migration v39 : l'état d'une entrée (`etat`) n'est pas un libellé, et la colonne "
        "est remplie par la recopie de la même migration",
    ("database.py", "_copier_les_releves"):
        "une copie amorcée : `copier_le_travail` indexe chaque région copiée par "
        "`_region_index_payload` APRÈS avoir recopié ses relevés (`_indexer_une_region_copiee`)",
    ("database.py", "repartir_de_zero"):
        "repartir de zéro réindexe chaque région touchée par `_region_index_payload` APRÈS "
        "avoir retiré ses relevés",
    ("releves.py", "reancrer_releves"):
        "le ré-ancrage d'un passage ne change aucun libellé ; il est appelé par "
        "`reindex_region`, qui réécrit la ligne entière",
    ("socle.py", "retirer_la_surface"):
        "les relevés de la PLANCHE : l'index est par région, ils n'y entrent pas",
    ("routes/releves.py", "_entree_par_nom"):
        "une entrée qui naît en posant n'a encore aucun relevé ; la pose qui suit réindexe",
    ("routes/releves.py", "_variante_par_nom"):
        "une variante qui naît n'a encore aucun relevé ; la pose (ou la modification) qui "
        "suit réindexe",
    ("grille_import.py", "ecrire_plan"):
        "écrit le plan d'une version ; sur une version VIVANTE, ses deux appelants "
        "(`importer`, `grille_ecriture.ecrire`) appellent ensuite `reindexer_libelles` — "
        "vérifié plus bas ; une version fermée n'est pas indexée",
    ("grille_import.py", "_fusionner"):
        "ses deux appelants réindexent les relevés fusionnés APRÈS avoir écrit le plan neuf "
        "(`reindexer_libelles(…, fusions)`) : réindexer ici lirait l'ancien plan",
    ("undo.py", "_inverser_ordre"):
        "Ctrl+Z d'un déplacement d'étiquette ne change que des rangs, pas un libellé",
    ("grille_import.py", "reporter_cardinalites"):
        "`une`, la cardinalité figée d'un relevé, n'est pas un libellé",
    ("montee.py", "ecrire"):
        "la montée de version ne concerne qu'une grille FERMÉE, dont les libellés n'entrent "
        "pas dans l'index plein texte (J6) : changer la version, l'entrée ou `une` d'un relevé "
        "n'y change rien",
}


def _sources():
    dossiers = [RACINE, RACINE / "routes", RACINE / "pipeline", RACINE / "tools"]
    for d in dossiers:
        for f in sorted(d.glob("*.py")):
            yield f.relative_to(RACINE).as_posix(), f.read_text(encoding="utf-8")


def _texte(noeud) -> str:
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    if isinstance(noeud, ast.JoinedStr):
        return "".join(v.value for v in noeud.values
                       if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return ""


def _appelle(fonction, nom: str) -> bool:
    for n in ast.walk(fonction):
        if isinstance(n, ast.Call):
            f = n.func
            if (isinstance(f, ast.Name) and f.id == nom) or (
                    isinstance(f, ast.Attribute) and f.attr == nom):
                return True
    return False


def _ecritures(fichier: str, source: str) -> dict:
    """{(fichier, fonction): appelle le relais ?} pour chaque fonction qui porte un littéral
    SQL d'écriture sur une des tables. Une écriture hors de toute fonction : « <module> »."""
    arbre = ast.parse(source)
    trouve = {}

    def visiter(noeud, fonction):
        for enfant in ast.iter_child_nodes(noeud):
            if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Une fonction imbriquée appartient à celle qui la contient (un geste).
                visiter(enfant, fonction or enfant)
                continue
            if _ECRITURE.search(_texte(enfant)):
                cle = (fichier, fonction.name if fonction else "<module>")
                trouve[cle] = trouve.get(cle, False) or (
                    fonction is not None and _appelle(fonction, _RELAIS))
            visiter(enfant, fonction)
    visiter(arbre, None)
    return trouve


def test_le_cliquet_mord():
    """Ses motifs mordent : une écriture sans le relais est vue, une autre avec ne l'est pas,
    une table nommée par une f-string aussi ; et le vrai code donne ses écritures connues."""
    faux = ('def a(conn):\n    conn.execute("DELETE FROM releve WHERE id = ?", (1,))\n'
            'def b(conn):\n    conn.execute(f"UPDATE grille_variante SET libelle = {x}")\n'
            '    reindex_etiquettes(conn, [1])\n'
            'def c(conn):\n    conn.execute("INSERT INTO releve_mot (releve_id) VALUES (1)")\n')
    assert _ecritures("faux.py", faux) == {("faux.py", "a"): False, ("faux.py", "b"): True}
    vu = {}
    for fichier, source in _sources():
        vu.update(_ecritures(fichier, source))
    for attendu in (("routes/releves.py", "poser_releve"), ("routes/releves.py", "retirer"),
                    ("routes/releves.py", "modifier_releve"), ("undo.py", "_inverser_releve"),
                    ("releves.py", "rendre")):
        assert vu.get(attendu) is True, (attendu, vu.get(attendu))


def test_toute_ecriture_des_etiquettes_reindexe_ou_est_declaree():
    vu = {}
    for fichier, source in _sources():
        vu.update(_ecritures(fichier, source))
    sans = sorted(k for k, appelle in vu.items() if not appelle)
    assert [k for k in sans if k not in DECLAREES] == [], (
        "une écriture de `releve` ou d'un libellé indexé n'appelle pas `reindex_etiquettes` : "
        "appelez-le, ou déclarez-la ici avec sa raison")
    # Une déclaration morte ne doit pas rester : elle couvrirait la prochaine écriture du nom.
    assert [k for k in DECLAREES if k not in vu] == [], "déclaration sans écriture"
    assert [k for k in DECLAREES if vu.get(k)] == [], "déclarée alors qu'elle réindexe"


def test_les_appelants_d_ecrire_plan_sur_une_version_vivante_reindexent():
    """La déclaration d'`ecrire_plan` tient par ses appelants : `importer` et
    `grille_ecriture.ecrire` appellent `reindexer_libelles`, qui appelle le relais."""
    arbres = {f: ast.parse(s) for f, s in _sources()}

    def fonction(fichier, nom):
        return next(n for n in ast.walk(arbres[fichier])
                    if isinstance(n, ast.FunctionDef) and n.name == nom)
    assert _appelle(fonction("grille_import.py", "reindexer_libelles"), _RELAIS)
    assert _appelle(fonction("grille_import.py", "importer"), "reindexer_libelles")
    assert _appelle(fonction("grille_ecriture.py", "ecrire"), "reindexer_libelles")
