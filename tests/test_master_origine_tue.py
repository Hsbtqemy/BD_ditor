"""`planches.master_origine` ne sort d'aucune route, hors la réponse de l'import (IMG-1) —
et son NOM seul, d'une seule (UX-11, 2026-10-22).

La colonne dit où vit le master d'archive : un chemin ShareDocs — parfois celui d'un espace
PERSONNEL — ou un nom de fichier, recopié sur les planches d'une copie sœur d'un autre
projet (D6). Rien à l'écran ne la lit. La première correction tenait la règle route par
route, dans une liste écrite à la main, et en avait oublié une (`PATCH …/role`, relecture
croisée) : elle se tient désormais À LA SOURCE (`socle._get_planche`, `_planche_rendue`),
et ce fichier BALAIE l'inventaire des routes au lieu d'en nommer quelques-unes, un jeton
semé dans la colonne, à la manière de `test_sorties_identite`.

Ce que le balayage couvre, et ce qu'il ne couvre pas, est écrit :
- toutes les routes GET dont le décor sait remplir les paramètres, sous l'exigence du
  plancher (`inventaire_routes.exiger_plancher`) ;
- toutes les routes qui ÉCRIVENT sur une planche (`{planche_id}` dans le chemin), chacune
  sur un décor neuf, avec le corps de `CORPS` ; leur liste est comparée à celle que le
  SOURCE déclare, pour qu'une route neuve ne quitte pas le balayage en silence ;
- pas les autres routes d'écriture : elles n'atteignent une planche que par
  `_get_planche`, qui la tait.

UX-11 (Hugo, 2026-10-22) — la liste des planches d'un album rend le NOM du fichier
d'origine, sans dossier ni préfixe, sous une clé à lui (`nom_fichier_origine`) : la fiche
d'un album de la Bibliothèque le montre au survol et range un album par noms de fichier.
D'où DEUX jetons dans la valeur semée : `JETON` est dans le DOSSIER, et ne doit sortir de
nulle part, cette route comprise ; `NOM` est le nom du fichier, et ne sort que de la route
déclarée dans `NOM_SEUL`, sous sa clé et nulle part ailleurs dans la réponse. Les exports
d'album, des routes GET, sont balayés comme les autres : le nom n'y sort pas.
"""
import ast
import json
import re
import sqlite3
from pathlib import Path

import pytest

import inventaire_routes

REPO_ROOT = Path(__file__).resolve().parent.parent
JETON = "zzorigine7jeton"
NOM = "zznom7fichier.tif"
SEMIS = f"sharedocs:BD/{JETON}/{NOM}"

# La réponse de l'import la rend EXPRÈS : à qui vient de donner le fichier, le nom qu'il a
# donné. C'est la seule.
EXCEPTIONS = {("POST", "/api/albums/{album_id}/import"):
              "rend à qui importe le nom du fichier qu'il vient d'envoyer"}

# Les routes qui rendent le NOM seul du fichier d'origine, dérivé de la colonne — jamais son
# dossier —, et la clé sous laquelle elles le rendent (UX-11). C'est la seule.
NOM_SEUL = {"/api/albums/{album_id}/planches": (
    "nom_fichier_origine",
    "la fiche d'un album de la Bibliothèque le montre au survol d'une planche (« Fichier : "
    "page-10.tif ») et range l'album par noms de fichier ; le dossier reste tu")}

# Les corps des routes d'écriture sur une planche. Une route absente d'ici est appelée sans
# corps.
CORPS = {
    ("PATCH", "/api/planches/{planche_id}/role"): {"role": "paratexte"},
    ("PATCH", "/api/planches/{planche_id}/statut"): {"statut": "importee"},
    ("PATCH", "/api/planches/{planche_id}/validation"): {"validee": True},
    ("PATCH", "/api/planches/{planche_id}/verrou"): {"verrouillee": True},
    ("PATCH", "/api/planches/{planche_id}/relecture"): {"relecture": "faite"},
    ("POST", "/api/planches/{planche_id}/regions"):
        {"type": "case", "x": 0, "y": 0, "w": 5, "h": 5},
}

# Celles qu'un décor de test peut ne pas atteindre, et pourquoi. Atteintes, elles sont
# vérifiées comme les autres.
PEUVENT_MANQUER = {
    ("POST", "/api/planches/{planche_id}/segmenter"): "moteur optionnel (Kumiko) : 503 sans lui",
    ("POST", "/api/planches/{planche_id}/detecter-bulles"): "moteur optionnel : 503 sans lui",
    ("POST", "/api/planches/{planche_id}/ocr"): "moteur optionnel (EasyOCR) : 503 sans lui",
}


def _decor(client, png_bytes, db_path) -> dict:
    a = client.post("/api/albums", json={"titre": "Origine"}).json()
    p = client.post(f"/api/albums/{a['id']}/import",
                    files={"file": ("Mon Scan.png", png_bytes, "image/png")}).json()
    r = client.post(f"/api/planches/{p['id']}/regions",
                    json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}).json()
    c = sqlite3.connect(db_path)
    c.execute("UPDATE planches SET master_origine = ?", (SEMIS,))
    c.commit()
    ligne = c.execute("SELECT document_id, projet_id FROM albums WHERE id = ?",
                      (a["id"],)).fetchone()
    c.close()
    col = client.get(f"/api/albums/{a['id']}/collections").json()[0]
    return {"album_id": a["id"], "planche_id": p["id"], "region_id": r["id"],
            "collection_id": col["id"], "document_id": ligne[0],
            "projet_id": ligne[1] or col.get("projet_id") or 1, "import": p}


def _concret(gabarit: str, decor: dict):
    manque = []

    def sub(m):
        nom = m.group(1).split(":")[0]
        if nom not in decor:
            manque.append(nom)
            return ""
        return str(decor[nom])
    chemin = re.sub(r"{([^}]+)}", sub, gabarit)
    return None if manque else chemin


def _fuite(texte: str) -> bool:
    return JETON in texte or "master_origine" in texte


def _nom_hors_de_sa_cle(gabarit: str, texte: str) -> bool:
    """Le NOM sort-il là où il ne doit pas ? Partout, sauf dans la route de `NOM_SEUL`, où
    il ne se lit que sous sa clé, une fois par planche, et nulle part ailleurs."""
    if NOM not in texte:
        return False
    if gabarit not in NOM_SEUL:
        return True
    cle, _ = NOM_SEUL[gabarit]
    planches = json.loads(texte)
    return not (planches and all(p.get(cle) == NOM for p in planches)
                and texte.count(NOM) == len(planches))


def _ecritures_de_planche_du_source() -> set:
    """Les routes d'écriture dont le chemin porte `{planche_id}`, comptées dans le SOURCE
    (décorateurs de `main.py` et `routes/*.py`) — le plancher de ce balayage."""
    vues = set()
    for f in [REPO_ROOT / "main.py"] + sorted((REPO_ROOT / "routes").glob("*.py")):
        for noeud in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in noeud.decorator_list:
                if (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)
                        and deco.func.attr in {"post", "put", "patch", "delete"}
                        and deco.args and isinstance(deco.args[0], ast.Constant)
                        and "{planche_id}" in str(deco.args[0].value)):
                    vues.add((deco.func.attr.upper(), deco.args[0].value))
    return vues


def test_aucune_route_get_ne_rend_master_origine(client, png_bytes, db_path):
    from test_sorties_identite import QUETES
    decor = _decor(client, png_bytes, db_path)
    gets = [r for r in inventaire_routes.routes_api() if "GET" in r.methods]
    inventaire_routes.exiger_plancher(len(gets), "le balayage de master_origine", "GET")
    atteintes, fuites = [], []
    for r in sorted(gets, key=lambda r: r.path):
        chemin = _concret(r.path, decor)
        if chemin is None:
            continue
        if r.path in QUETES:
            chemin += "?" + QUETES[r.path].format(**decor)
        rep = client.get(chemin)
        if rep.status_code >= 400:
            continue
        atteintes.append(r.path)
        texte = rep.content.decode("utf-8", "replace")
        if _fuite(texte) or _nom_hors_de_sa_cle(r.path, texte):
            fuites.append(r.path)
    assert not fuites, f"ces routes rendent master_origine, ou son nom hors de sa clé : {fuites}"
    # Non-vacuité : la liste des planches, qui lit `SELECT p.*`, est bien balayée — et y rend
    # le nom ; les exports d'album aussi, où il ne doit pas sortir.
    assert "/api/albums/{album_id}/planches" in atteintes and len(atteintes) >= 30, atteintes
    assert len([a for a in atteintes if a.startswith("/api/export/")]) >= 3, atteintes
    planches = client.get(f"/api/albums/{decor['album_id']}/planches").json()
    assert [p["nom_fichier_origine"] for p in planches] == [NOM]


def test_aucune_ecriture_sur_une_planche_ne_rend_master_origine(client, png_bytes, db_path):
    inventaire = {(m, r.path) for r in inventaire_routes.routes_api()
                  for m in r.methods if m != "GET" and "{planche_id}" in r.path}
    assert inventaire == _ecritures_de_planche_du_source() and len(inventaire) >= 10, (
        "l'inventaire des routes d'écriture sur une planche ne coïncide plus avec le source")
    for cle in list(CORPS) + list(PEUVENT_MANQUER):
        assert cle in inventaire, f"{cle} n'est plus une route : retire-la d'ici"
    fuites, manquees = [], []
    for methode, gabarit in sorted(inventaire):
        decor = _decor(client, png_bytes, db_path)
        rep = client.request(methode, _concret(gabarit, decor),
                             json=CORPS.get((methode, gabarit)))
        if rep.status_code >= 400:
            if (methode, gabarit) not in PEUVENT_MANQUER:
                manquees.append((methode, gabarit, rep.status_code, rep.text[:120]))
            continue
        if _fuite(rep.text) or NOM in rep.text:
            fuites.append((methode, gabarit))
    assert not manquees, f"routes non atteintes, ni déclarées : {manquees}"
    assert not fuites, f"ces routes rendent master_origine : {fuites}"


def test_la_seule_exception_est_la_reponse_de_l_import(client, png_bytes, db_path):
    """L'exception déclarée l'est encore : l'import rend le nom qu'on vient de donner."""
    (methode, gabarit), = EXCEPTIONS
    decor = _decor(client, png_bytes, db_path)
    assert decor["import"]["master_origine"] == "Mon Scan.png"
    assert (methode, gabarit) in {(m, r.path) for r in inventaire_routes.routes_api()
                                  for m in r.methods}
    for gabarit in NOM_SEUL:
        assert gabarit in {r.path for r in inventaire_routes.routes_api() if "GET" in r.methods}
