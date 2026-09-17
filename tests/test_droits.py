"""AUTH-12, étape 3 — la description des droits en ACTES, et ce qui l'empêche de mentir.

L'écran d'attribution ne connaît aucun niveau en dur : il lit `GET /api/droits`. Une
description fausse y serait pire qu'absente — l'écran promettrait ce que le serveur refuse.
Elle est donc confrontée à `Portee`, par table de vérité : ce qu'elle dit d'un niveau, le
cumul doit le faire.

Ce que ces tests ne prouvent PAS, et c'est écrit dans `autorisation.py` : qu'une route donnée
exige le niveau de l'acte qu'on lui associe. Le périmètre route par route (AUTH-10) n'existe
pas encore.
"""
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import autorisation  # noqa: E402

from autorisation import (ACTES, ECRITURE, HORS_RANG, LECTURE, NIVEAUX,  # noqa: E402
                          PROPRIETAIRE, Portee)

C = 7   # une collection quelconque

# La question que `Portee` pose pour chaque niveau.
QUESTION = {LECTURE: "peut_lire", ECRITURE: "peut_ecrire", PROPRIETAIRE: "peut_administrer"}


def _portee(niveau, export=False):
    ensembles = {LECTURE: "lecture", ECRITURE: "ecriture", PROPRIETAIRE: "propriete"}
    kw = {ensembles[niveau]: frozenset({C})}
    if export:
        kw["export"] = frozenset({C})
    return Portee(**kw)


def test_l_echelle_est_celle_des_niveaux():
    assert autorisation.description_des_droits()["echelle"] == list(NIVEAUX)
    assert set(QUESTION) == set(NIVEAUX), "un niveau sans question de Portee à confronter"


def test_chaque_acte_dit_ce_que_le_cumul_fait():
    """Accordé au niveau L, un acte de niveau N est permis si et seulement si L est au-dessus
    ou au niveau de N — et c'est `Portee`, non la description, qui répond."""
    for acte in ACTES:
        rang_acte = NIVEAUX.index(acte["niveau"])
        for accorde in NIVEAUX:
            permis = getattr(_portee(accorde), QUESTION[acte["niveau"]])(C)
            assert permis == (NIVEAUX.index(accorde) >= rang_acte), (acte["code"], accorde)


def test_exporter_est_hors_rang_et_d_office_au_proprietaire():
    (exporter,) = HORS_RANG
    assert (exporter["code"], exporter["champ"], exporter["d_office"]) == \
        ("exporter", "exporter", PROPRIETAIRE)
    assert _portee(PROPRIETAIRE).peut_exporter(C) is True          # d'office
    assert _portee(ECRITURE).peut_exporter(C) is False             # écrire n'y suffit pas
    assert _portee(LECTURE, export=True).peut_exporter(C) is True  # la case y suffit
    assert _portee(LECTURE).peut_exporter(C) is False


def test_des_actes_lies_ont_le_meme_niveau_et_la_table_est_saine():
    codes = [a["code"] for a in ACTES] + [h["code"] for h in HORS_RANG]
    assert len(codes) == len(set(codes)), codes
    for a in ACTES:
        assert a["niveau"] in NIVEAUX, a
        assert set(a) == {"code", "libelle", "niveau", "lies", "avertissement"}, a
        assert a["libelle"], a
    liaisons = {}
    for a in ACTES:
        if a["lies"] is not None:
            liaisons.setdefault(a["lies"], set()).add(a["niveau"])
    # Une barre dessinée entre deux actes qui n'ont pas le même niveau serait fausse.
    assert all(len(niveaux) == 1 for niveaux in liaisons.values()), liaisons
    # Aujourd'hui, les quatre actes d'écriture sont inséparables.
    assert {a["code"] for a in ACTES if a["lies"] == ECRITURE} == \
        {"annoter", "structurer", "vocabulaire", "lots"}


def test_aucune_garde_ne_lit_la_description():
    """Des données, jamais une garde : dans `autorisation.py`, seule la fonction qui la met en
    forme nomme `ACTES` et `HORS_RANG`, et aucun autre module de l'application ne les lit."""
    arbre = ast.parse((REPO_ROOT / "autorisation.py").read_text(encoding="utf-8"))
    lecteurs = {f.name for f in ast.walk(arbre) if isinstance(f, ast.FunctionDef)
                and any(isinstance(n, ast.Name) and n.id in ("ACTES", "HORS_RANG")
                        for n in ast.walk(f))}
    assert lecteurs == {"description_des_droits"}, lecteurs
    for fichier in [*REPO_ROOT.glob("*.py"), *REPO_ROOT.glob("routes/*.py")]:
        if fichier.name == "autorisation.py":
            continue
        # Par l'arbre syntaxique et non par le texte : le mot figure dans des docstrings.
        noms = {n.id if isinstance(n, ast.Name) else n.attr
                for n in ast.walk(ast.parse(fichier.read_text(encoding="utf-8")))
                if isinstance(n, (ast.Name, ast.Attribute))}
        assert not noms & {"ACTES", "HORS_RANG"}, fichier.name


def test_la_route_sert_la_description_a_tous(client, derriere_proxy):
    """Sans aucune donnée du corpus : une personne qui ne possède rien la lit aussi."""
    for headers in ({"Remote-User": "personne"}, {}):
        r = client.get("/api/droits", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json() == autorisation.description_des_droits()
    corps = client.get("/api/droits").json()
    assert [a["code"] for a in corps["actes"]] == [a["code"] for a in ACTES]
    structurer = next(a for a in corps["actes"] if a["code"] == "structurer")
    assert structurer["avertissement"]
