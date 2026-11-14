"""ANN-7 — tout CSV qui SORT est séparé par des points-virgules, en UTF-8 avec BOM.

Tranché par Hugo le 2026-11-11 : un Excel réglé en français prend la virgule pour le
séparateur décimal ; un CSV en virgules s'y ouvre au double-clic avec la ligne entière dans
une seule case (vu par Hugo). La règle vit dans `sortie_csv.py`, et ce fichier la garde de
deux côtés, parce qu'une seule lecture en rate.

1. **Le source** : aucun `csv.writer` ni `csv.DictWriter` construit ailleurs que dans
   `sortie_csv.py`, dans tout le code de l'application (racine, `routes/`, `pipeline/`,
   `tools/`). Une sortie neuve écrite à la main partirait en virgules — le défaut d'origine
   — sans qu'aucun test d'aujourd'hui la regarde. Et chaque module qui ÉCRIT du CSV est
   déclaré avec les sorties qu'on JOUE pour lui : un module neuf doit dire lesquelles.
2. **Les sorties, JOUÉES** : chaque route qui sort un fichier (l'inventaire de DROIT-2,
   `test_droit_export.PORTES`, qui exige déjà que toute porte soit déclarée) est appelée,
   et tout ce qui revient en CSV — un CSV nu ou les CSV d'une archive — doit commencer par
   le BOM et se lire au point-virgule, chaque ligne avec autant de cellules que l'en-tête.
   Les outils de `tools/` aussi, en sous-processus, comme on les lance.

3. **La virgule DÉCIMALE** (tranchée par Hugo ensuite : un Excel français lit « 0.8571 »
   comme du texte) : sur les sorties jouées, aucune cellule n'est un décimal à point, et
   celles qui doivent porter des décimales en portent bien à virgule — une garde qui ne
   voit aucun nombre approuve tout. Le texte libre garde son point (« 1.5 » dans une
   bulle).

Ce qu'il ne garde PAS : les LECTURES de CSV (l'import d'une grille lit déjà du
point-virgule), ni le texte qui MÊLE des nombres à des mots (« 12/30 (40.0%) » dans la
fiche de description) : c'est une cellule de texte.
"""
import ast
import csv
import io
import re
import sqlite3
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

import sortie_csv
from conftest import ADMIN
from test_autorisation import deux_albums  # noqa: F401  (fixture importée)
from test_droit_export import PORTES, _poser_export, _requete, sortie  # noqa: F401
from test_export_metadonnees import _run, corpus  # noqa: F401  (fixture importée)

RACINE = Path(__file__).resolve().parent.parent

# Le code de l'application. `tests/` n'est pas une sortie ; `spike/` est un banc d'essai
# des moteurs, hors couverture, dont le CSV de mesures ne quitte jamais le poste.
DOSSIERS_DU_CODE = ("", "routes", "pipeline", "tools")


# --------------------------------------------------------------------------- #
# 1. Le source
# --------------------------------------------------------------------------- #
def _fichiers_du_code():
    for dossier in DOSSIERS_DU_CODE:
        yield from sorted((RACINE / dossier).glob("*.py"))


def _ecrivains_construits(arbre) -> list:
    """Les `csv.writer(` / `csv.DictWriter(` — et leurs formes importées à part."""
    importes = {a.asname or a.name for n in ast.walk(arbre) if isinstance(n, ast.ImportFrom)
                and n.module == "csv" for a in n.names if a.name in ("writer", "DictWriter")}
    trouves = []
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if (isinstance(f, ast.Attribute) and f.attr in ("writer", "DictWriter")
                and isinstance(f.value, ast.Name) and f.value.id == "csv"):
            trouves.append(n.lineno)
        elif isinstance(f, ast.Name) and f.id in importes:
            trouves.append(n.lineno)
    return trouves


def _appels_a_l_ecrivain(arbre) -> list:
    """Les appels à `ecrivain_csv` / `ecrivain_csv_dict`, nus ou qualifiés."""
    noms = {"ecrivain_csv", "ecrivain_csv_dict"}
    return [n for n in ast.walk(arbre) if isinstance(n, ast.Call) and (
        (isinstance(n.func, ast.Name) and n.func.id in noms)
        or (isinstance(n.func, ast.Attribute) and n.func.attr in noms))]


def _arbre(chemin: Path):
    return ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))


def test_les_motifs_mordent():
    """Une garde qui cherche ce qui n'existe nulle part approuve tout : `sortie_csv.py`
    construit les deux écrivains, et le motif doit les y trouver ; un module qui l'appelle
    doit être vu comme tel."""
    assert _ecrivains_construits(_arbre(RACINE / "sortie_csv.py"))
    assert _ecrivains_construits(ast.parse(
        "from csv import writer as w\nw(f)\nimport csv\ncsv.DictWriter(f, [])")) == [2, 4]
    assert _appels_a_l_ecrivain(_arbre(RACINE / "routes" / "analyse.py"))


def test_aucun_ecrivain_csv_n_est_construit_hors_de_sortie_csv():
    """Le cliquet du source : le séparateur ne s'écrit qu'une fois."""
    fautes = {}
    for chemin in _fichiers_du_code():
        if chemin.name == "sortie_csv.py" and chemin.parent == RACINE:
            continue
        lignes = _ecrivains_construits(_arbre(chemin))
        if lignes:
            fautes[str(chemin.relative_to(RACINE))] = lignes
    assert not fautes, (
        f"écrivain(s) CSV construit(s) à la main : {fautes}. Une sortie CSV s'écrit par "
        "`sortie_csv.ecrivain_csv` / `ecrivain_csv_dict` (point-virgule, ANN-7) ; une "
        "LECTURE se fait par `csv.reader`, que ce cliquet ne regarde pas.")


def test_le_separateur_ne_se_passe_pas_a_l_appel():
    """Ni dans le source — un `delimiter=` passé à l'écrivain rouvrirait la porte qu'il
    ferme —, ni à l'exécution, où l'écrivain le refuse."""
    fautes = [f"{c.relative_to(RACINE)}:{n.lineno}" for c in _fichiers_du_code()
              for n in _appels_a_l_ecrivain(_arbre(c))
              if any(k.arg == "delimiter" for k in n.keywords)]
    assert not fautes, fautes
    with pytest.raises(TypeError):
        sortie_csv.ecrivain_csv(io.StringIO(), delimiter=",")
    with pytest.raises(TypeError):
        sortie_csv.ecrivain_csv_dict(io.StringIO(), ["a"], delimiter=",")
    assert sortie_csv.SEPARATEUR == ";"


# Chaque module qui ÉCRIT du CSV, et les sorties qu'on joue pour lui plus bas (une étiquette
# de `SORTIES_ROUTES` ou de `SORTIES_OUTILS`). Déclarer un module sans le jouer serait le
# déclarer couvert sans l'être.
MODULES_QUI_ECRIVENT = {
    "main.py": {"/api/export/csv"},
    "routes/recherche.py": {"/api/recherche/export.csv"},
    "routes/analyse.py": {"/api/analyse/frequences.csv", "/api/analyse/concordance.csv",
                          "/api/analyse/comparaison.csv", "/api/analyse/croisement.csv",
                          "/api/analyse/croisement.csv?forme=matrice",
                          "/api/analyse/accord.csv", "/api/analyse/accord-inter.csv"},
    "grille_import.py": {"/api/grilles/{grille_id}/versions/{numero}/tableur?format=csv"},
    "tools/metadonnees_collection.py": {
        "/api/collections/{collection_id}/depot/metadonnees?format=zip",
        "metadonnees_collection --csv-dir", "metadonnees_collection --zip"},
    "tools/description_collection.py": {
        "/api/collections/{collection_id}/depot/description?format=csv",
        "description_collection --csv fichier", "description_collection --csv -"},
    "tools/rapport_accord.py": {"rapport_accord --csv"},
    "tools/rapport_accord_inter.py": {"rapport_accord_inter --csv"},
}


def test_tout_module_qui_ecrit_du_csv_est_declare():
    trouves = {str(c.relative_to(RACINE)).replace("\\", "/") for c in _fichiers_du_code()
               if c.name != "sortie_csv.py" and _appels_a_l_ecrivain(_arbre(c))}
    assert trouves == set(MODULES_QUI_ECRIVENT), (
        f"non déclarés : {sorted(trouves - set(MODULES_QUI_ECRIVENT))} ; déclarés sans "
        f"écrire : {sorted(set(MODULES_QUI_ECRIVENT) - trouves)}")
    jouees = set(SORTIES_ROUTES) | set(SORTIES_OUTILS)
    for module, sorties in MODULES_QUI_ECRIVENT.items():
        assert sorties and sorties <= jouees, (module, sorted(sorties - jouees))


# --------------------------------------------------------------------------- #
# La forme d'un CSV qui sort
# --------------------------------------------------------------------------- #
DECIMAL_A_POINT = re.compile("^-?[0-9]+[.][0-9]+$")
DECIMAL_A_VIRGULE = re.compile("^-?[0-9]+,[0-9]+$")


def _exiger_forme(nom: str, texte: str, bom: bool = True) -> int:
    """BOM (sauf déclaré), point-virgule, et une forme RECTANGULAIRE : un fichier en
    virgules se lit au point-virgule comme une seule colonne, ce que l'en-tête trahit. Et
    aucun décimal à point. Rend le nombre de décimaux à virgule vus, pour que l'appelant
    exige d'en avoir vu là où il en attend."""
    if bom:
        assert texte.startswith(sortie_csv.BOM), f"{nom} : pas de BOM UTF-8 en tête"
        texte = texte[1:]
    else:
        assert not texte.startswith(sortie_csv.BOM), f"{nom} : BOM inattendu"
    lignes = list(csv.reader(io.StringIO(texte, newline=""), delimiter=";"))
    assert lignes, f"{nom} : vide"
    entete = lignes[0]
    assert len(entete) >= 2, f"{nom} : l'en-tête ne se lit pas au point-virgule : {entete}"
    larges = [i for i, l in enumerate(lignes) if l and len(l) != len(entete)]
    assert not larges, f"{nom} : lignes {larges[:5]} d'une autre largeur que l'en-tête"
    a_point = [c for l in lignes for c in l if DECIMAL_A_POINT.match(c)]
    assert not a_point, f"{nom} : décimaux à point {a_point[:5]} (virgule attendue)"
    return sum(1 for l in lignes for c in l if DECIMAL_A_VIRGULE.match(c))


def _csv_d_une_reponse(nom: str, rep) -> dict:
    """Les CSV que porte une réponse : elle-même, ou les membres `.csv` d'une archive."""
    type_ = rep.headers.get("content-type", "")
    if type_.startswith("text/csv"):
        return {nom: rep.content.decode("utf-8")}
    if type_.startswith("application/zip"):
        with zipfile.ZipFile(io.BytesIO(rep.content)) as z:
            return {f"{nom} › {m}": z.read(m).decode("utf-8") for m in z.namelist()
                    if m.endswith(".csv")}
    return {}


# --------------------------------------------------------------------------- #
# 2. Les routes, jouées
# --------------------------------------------------------------------------- #
# Ce que chaque porte reçoit EN PLUS de `test_droit_export._requete` pour rendre du CSV —
# une porte peut en avoir plusieurs formes (le croisement : à plat, en matrice).
VARIANTES = {
    "/api/analyse/croisement.csv": [{}, {"forme": "matrice"}],
    "/api/collections/{collection_id}/depot/description": [{"format": "csv"}],
    "/api/collections/{collection_id}/depot/metadonnees": [{"format": "zip"}],
}

# Les sorties qui DOIVENT porter des décimaux dans le décor ci-dessous : la mesure du
# cliquet de la virgule décimale ne vaut que là où il y a des nombres à voir.
DECIMALES_ROUTES = {
    "/api/analyse/comparaison.csv",                                  # rel_a, diff, ll
    "/api/analyse/accord.csv",                                       # taux
    "/api/collections/{collection_id}/depot/metadonnees?format=zip",  # largeur_cm
}

# Les sorties CSV des routes — ce que le balayage doit trouver, ni plus ni moins. Une
# porte NEUVE qui rend du CSV tombe ici comme non déclarée : on l'ajoute, et on la lit.
SORTIES_ROUTES = {
    "/api/export/csv", "/api/recherche/export.csv",
    "/api/analyse/frequences.csv", "/api/analyse/concordance.csv",
    "/api/analyse/comparaison.csv", "/api/analyse/croisement.csv",
    "/api/analyse/croisement.csv?forme=matrice",
    "/api/analyse/accord.csv", "/api/analyse/accord-inter.csv",
    "/api/collections/{collection_id}/depot/description?format=csv",
    "/api/collections/{collection_id}/depot/metadonnees?format=zip",
    # Hors des portes de DROIT-2 (`HORS_EXPORT`) : le tableur d'une grille, joué à part.
    "/api/grilles/{grille_id}/versions/{numero}/tableur?format=csv",
}


def _etiquette(chemin: str, extra: dict) -> str:
    return chemin + ("?" + "&".join(f"{k}={v}" for k, v in extra.items()) if extra else "")


def _semer_des_decimaux(db_path, region_id, planche_id):
    """Une résolution (les centimètres dérivés sont décimaux) et un mot relu (le taux
    d'accord l'est aussi)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE planches SET dpi_x = 300, dpi_y = 300 WHERE id = ?",
                     (planche_id,))
        if not conn.execute("SELECT 1 FROM tokens WHERE region_id = ? AND ordre = 0",
                            (region_id,)).fetchone():
            conn.execute("INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                         "VALUES (?, 0, 'DIS', 'dire', 'VERB', '')", (region_id,))
        forme = conn.execute("SELECT texte FROM tokens WHERE region_id = ? AND ordre = 0",
                             (region_id,)).fetchone()[0]
        conn.execute("INSERT INTO token_correction (region_id, ordre, forme, etat, obsolete) "
                     "VALUES (?, 0, ?, 'valide', 0)", (region_id, forme))
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _planche_de(db_path, region_id) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT planche_id FROM regions WHERE id = ?",
                            (region_id,)).fetchone()[0]
    finally:
        conn.close()


def test_toute_route_qui_sort_du_csv_le_sort_au_point_virgule(client, db_path, sortie):
    _poser_export(db_path, sortie["c1"], "bob")
    r1 = sortie["r1"]["id"]
    _semer_des_decimaux(db_path, r1, _planche_de(db_path, r1))
    vus = {}
    for porte in sorted(PORTES):
        methode, url, params, corps = _requete(porte, sortie)
        if methode != "GET":           # le dépôt ShareDocs et les figures : pas de CSV rendu
            continue
        for extra in VARIANTES.get(porte[1], [{}]):
            rep = client.get(url, params={**params, **extra}, headers=sortie["bob"])
            assert rep.status_code == 200, (porte, extra, rep.status_code, rep.text[:200])
            csvs = _csv_d_une_reponse(_etiquette(porte[1], extra), rep)
            if csvs:
                vus[_etiquette(porte[1], extra)] = csvs
    vus.update(_tableur_de_grille(client, db_path))
    assert set(vus) == SORTIES_ROUTES, (
        f"rendent du CSV sans être déclarées : {sorted(set(vus) - SORTIES_ROUTES)} ; "
        f"déclarées sans en rendre : {sorted(SORTIES_ROUTES - set(vus))}")
    for etiquette, csvs in vus.items():
        decimaux = sum(_exiger_forme(nom, texte) for nom, texte in csvs.items())
        if etiquette in DECIMALES_ROUTES:
            assert decimaux, f"{etiquette} : aucun décimal à voir, la garde ne mesure rien"


def _tableur_de_grille(client, db_path) -> dict:
    """Le réexport d'une grille (deux CSV dans une archive), lu par qui gère son projet."""
    from grilles_decor import LEA, grille_active, monter
    decor = monter(client, db_path)
    g = grille_active(client, decor["p"])
    rep = client.get(f"/api/grilles/{g['grille_id']}/versions/1/tableur",
                     params={"format": "csv"}, headers=LEA)
    assert rep.status_code == 200, rep.text[:200]
    etiquette = "/api/grilles/{grille_id}/versions/{numero}/tableur?format=csv"
    return {etiquette: _csv_d_une_reponse(etiquette, rep)}


def test_le_cliquet_des_routes_voit_une_sortie_en_virgules():
    """La contre-épreuve de `_exiger_forme` : le fichier d'avant la décision échoue."""
    d_avant = io.StringIO()
    csv.writer(d_avant).writerows([["album", "planche", "texte"], ["Tintin", "1", "OH !"]])
    with pytest.raises(AssertionError, match="point-virgule"):
        _exiger_forme("avant", sortie_csv.BOM + d_avant.getvalue())
    with pytest.raises(AssertionError, match="BOM"):
        _exiger_forme("sans BOM", "a;b\r\n1;2\r\n")
    with pytest.raises(AssertionError, match="décimaux à point"):
        _exiger_forme("à point", sortie_csv.BOM + "taux;n\r\n0.8571;3\r\n")
    assert _exiger_forme("à virgule",
                         sortie_csv.BOM + "taux;n\r\n0,8571;3\r\n") == 1


# --------------------------------------------------------------------------- #
# 3. Les outils, en sous-processus
# --------------------------------------------------------------------------- #
SORTIES_OUTILS = {
    "metadonnees_collection --csv-dir", "metadonnees_collection --zip",
    "description_collection --csv fichier", "description_collection --csv -",
    "rapport_accord --csv", "rapport_accord_inter --csv",
}


# Les sorties d'outil qui DOIVENT porter des décimaux dans le décor (`_semer_des_decimaux`).
DECIMALES_OUTILS = {"metadonnees_collection --csv-dir", "metadonnees_collection --zip",
                    "rapport_accord --csv"}


def test_les_outils_ecrivent_leurs_csv_au_point_virgule(corpus, region, tmp_path):
    db, data = corpus["db"], corpus["data"]
    _semer_des_decimaux(db, region["id"], region["planche_id"])
    vus = {}

    def lancer(etiquette, script, *args):
        r = _run(script, db, data, *args)
        assert r.returncode == 0, (etiquette, r.stderr)
        vus.setdefault(etiquette, {})
        return r

    dossier = tmp_path / "tables"
    lancer("metadonnees_collection --csv-dir", "metadonnees_collection.py",
           "--csv-dir", str(dossier))
    for f in sorted(dossier.glob("*.csv")):
        vus["metadonnees_collection --csv-dir"][f.name] = f.read_bytes().decode("utf-8")

    archive = tmp_path / "m.zip"
    lancer("metadonnees_collection --zip", "metadonnees_collection.py", "--zip", str(archive))
    with zipfile.ZipFile(archive) as z:
        for m in z.namelist():
            vus["metadonnees_collection --zip"][m] = z.read(m).decode("utf-8")

    fiche = tmp_path / "fiche.csv"
    lancer("description_collection --csv fichier", "description_collection.py",
           "--csv", str(fiche))
    vus["description_collection --csv fichier"]["fiche"] = fiche.read_bytes().decode("utf-8")

    # Sur la sortie standard, pas de BOM : elle se lit par une autre commande, pas par
    # Excel, et un BOM y collerait trois octets au premier nom de colonne.
    r = lancer("description_collection --csv -", "description_collection.py", "--csv")
    assert not r.stdout.startswith(sortie_csv.BOM)
    _exiger_forme("description_collection --csv -", r.stdout, bom=False)

    for outil in ("rapport_accord", "rapport_accord_inter"):
        chemin = tmp_path / f"{outil}.csv"
        lancer(f"{outil} --csv", f"{outil}.py", "--csv", str(chemin))
        vus[f"{outil} --csv"][outil] = chemin.read_bytes().decode("utf-8")

    assert set(vus) == SORTIES_OUTILS, sorted(set(vus) ^ SORTIES_OUTILS)
    for etiquette, fichiers in vus.items():
        if etiquette == "description_collection --csv -":
            continue
        assert fichiers, f"{etiquette} : aucun CSV écrit"
        decimaux = sum(_exiger_forme(f"{etiquette} › {nom}", texte)
                       for nom, texte in fichiers.items())
        if etiquette in DECIMALES_OUTILS:
            assert decimaux, f"{etiquette} : aucun décimal à voir, la garde ne mesure rien"


def test_l_anti_injection_survit_au_point_virgule(client, album, region):
    """`_csv_safe` n'a pas bougé : une note qui commence par `=` sort préfixée d'une
    apostrophe, et le point-virgule qu'elle contient reste DANS sa cellule."""
    a, rg = album, region
    assert client.put(f"/api/regions/{rg['id']}/annotation",
                      json={"note": "=SOMME(A1;A2)"}, headers=ADMIN).status_code == 200
    rep = client.get("/api/export/csv", params={"album_id": a["id"]}, headers=ADMIN)
    assert rep.status_code == 200, rep.text
    lignes = list(csv.DictReader(io.StringIO(rep.text.lstrip(sortie_csv.BOM)),
                                 delimiter=";"))
    assert [l["note"] for l in lignes] == ["'=SOMME(A1;A2)"]


# --------------------------------------------------------------------------- #
# 4. La virgule décimale, à la source
# --------------------------------------------------------------------------- #
def test_un_nombre_sort_avec_une_virgule_et_le_texte_tel_quel():
    """La règle porte sur le TYPE : un `float` et un `Decimal` prennent la virgule, une
    chaîne qui en a l'allure (« 1.5 » tapé dans une bulle, une date) reste telle quelle."""
    assert sortie_csv.nombre(0.857142, 4) == "0,8571"
    assert sortie_csv.nombre(1.5) == "1,5"
    assert sortie_csv.nombre(-0.25) == "-0,25"
    assert sortie_csv.nombre(Decimal("2.50")) == "2,50"
    assert sortie_csv.nombre(3) == "3"
    for pas_un_nombre in ("1.5", None, True):
        with pytest.raises(TypeError):
            sortie_csv.nombre(pas_un_nombre)
    tampon = io.StringIO()
    sortie_csv.ecrivain_csv(tampon).writerow(
        [1.5, "1.5", 3, None, Decimal("0.1"), True, "2026-11-14 10:30:00"])
    assert tampon.getvalue().strip() == "1,5;1.5;3;;0,1;True;2026-11-14 10:30:00"
    tampon = io.StringIO()
    e = sortie_csv.ecrivain_csv_dict(tampon, ["taux", "texte"])
    e.writeheader()
    e.writerows([{"taux": 0.5, "texte": "0.5"}])
    assert tampon.getvalue().splitlines() == ["taux;texte", "0,5;0.5"]


def test_le_texte_libre_garde_son_point(client, album, region, db_path):
    """« 1.5 » transcrit dans une zone sort tel qu'il est transcrit."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE regions SET ocr_texte = '1.5' WHERE id = ?", (region["id"],))
        conn.commit()
    finally:
        conn.close()
    rep = client.get("/api/export/csv", params={"album_id": album["id"]}, headers=ADMIN)
    assert rep.status_code == 200, rep.text
    lignes = list(csv.DictReader(io.StringIO(rep.text.lstrip(sortie_csv.BOM)),
                                 delimiter=";"))
    assert [l["ocr_texte"] for l in lignes] == ["1.5"]
