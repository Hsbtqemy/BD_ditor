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

Ce qu'il ne garde PAS : les LECTURES de CSV (l'import d'une grille lit déjà du
point-virgule), ni le séparateur décimal (les nombres gardent le point, `0.85` : à trancher
à part, cf. `docs/guide-utilisateur.md` § Exporter).
"""
import ast
import csv
import io
import zipfile
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
    assert len(_ecrivains_construits(_arbre(RACINE / "sortie_csv.py"))) == 2
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
def _exiger_forme(nom: str, texte: str, bom: bool = True):
    """BOM (sauf déclaré), point-virgule, et une forme RECTANGULAIRE : un fichier en
    virgules se lit au point-virgule comme une seule colonne, ce que l'en-tête trahit."""
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


def test_toute_route_qui_sort_du_csv_le_sort_au_point_virgule(client, db_path, sortie):
    _poser_export(db_path, sortie["c1"], "bob")
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
    for csvs in vus.values():
        for nom, texte in csvs.items():
            _exiger_forme(nom, texte)


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


# --------------------------------------------------------------------------- #
# 3. Les outils, en sous-processus
# --------------------------------------------------------------------------- #
SORTIES_OUTILS = {
    "metadonnees_collection --csv-dir", "metadonnees_collection --zip",
    "description_collection --csv fichier", "description_collection --csv -",
    "rapport_accord --csv", "rapport_accord_inter --csv",
}


def test_les_outils_ecrivent_leurs_csv_au_point_virgule(corpus, tmp_path):
    db, data = corpus["db"], corpus["data"]
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
        for nom, texte in fichiers.items():
            _exiger_forme(f"{etiquette} › {nom}", texte)


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
