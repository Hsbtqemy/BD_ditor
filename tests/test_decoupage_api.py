"""Le découpage de `main.py` en modules de routes tient-il debout ?  ARCH-1.

Ce fichier existe parce que la première extraction a produit **49 tests rouges** d'un
coup, tous par la même cause : trois noms — `citations_regions`, `STATUTS`, `nlp` — que le
bloc utilisait et que le nouveau module n'importait pas. Le module s'importe pourtant sans
broncher : un nom libre ne lève un `NameError` qu'à l'APPEL, donc le mal ne se voit qu'en
faisant tourner la route. J'avais dressé la liste des imports à l'œil plutôt que de la
calculer, ce qui est exactement le geste que ce test remplace.

QUATRE affirmations, et chacune couvre une manière différente de rater une extraction.
"""
import ast
import builtins
import io
import re
from pathlib import Path

import main

RACINE = Path(__file__).resolve().parent.parent
# `main.py` en fait partie : une coupe a deux côtés. Retirer un bloc peut emporter
# une définition que le RESTE utilisait encore, et cette panne-là est aussi muette
# que l'autre — le module s'importe, la route tombe à l'appel.
MODULES = ([RACINE / "main.py", RACINE / "socle.py"]
           + sorted((RACINE / "routes").glob("*.py")))


def _noms_libres(chemin: Path) -> list[str]:
    """Les noms qu'un module UTILISE sans les définir ni les importer.

    Analyse statique volontairement simple : elle ne suit pas les portées imbriquées, ce
    qui la rend un peu trop permissive (un nom défini dans une fonction compte comme
    défini partout). C'est le bon compromis ici — elle attrape ce qui manque à un module
    entier, qui est le mode d'échec d'un déménagement de code.
    """
    arbre = ast.parse(io.open(chemin, encoding="utf-8").read())
    definis, utilises = set(), set()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definis.add(n.name)
            # `ClassDef` n'a pas d'`args` : le distinguer n'est pas du zèle, c'est ce
            # qui empêche la garde de planter sur `AttributeError` au lieu de dire ce
            # qu'elle a trouvé. Aucun module de `routes/` n'a encore de classe ; les
            # prochains blocs sortis en portent (les modèles Pydantic).
            if not isinstance(n, ast.ClassDef):
                definis |= {a.arg for a in n.args.args + n.args.kwonlyargs
                            + n.args.posonlyargs}
                # `*args` / `**kwargs` ne sont pas dans ces listes-là. Les oublier
                # fabrique un FAUX positif — mesuré sur `main._tei_el(**attrs)` —,
                # et un faux positif dans un cliquet est pire qu'une lacune : on
                # apprend à passer outre, puis on passe outre le vrai.
                definis |= {a.arg for a in (n.args.vararg, n.args.kwarg) if a}
        elif isinstance(n, ast.Import):
            definis |= {(a.asname or a.name).split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            definis |= {a.asname or a.name for a in n.names}
        elif isinstance(n, ast.ExceptHandler) and n.name:
            definis.add(n.name)
        elif isinstance(n, ast.Name):
            (definis if isinstance(n.ctx, ast.Store) else utilises).add(n.id)
    return sorted(utilises - definis - set(dir(builtins)))


def test_aucun_module_de_routes_n_a_de_nom_libre():
    """Un bloc déménagé emporte son code, pas les imports de son ancien voisinage.

    Rien ne le signale : le module s'importe, l'application démarre, `/docs` liste la
    route. C'est seulement en l'APPELANT qu'un `NameError` sort. Une extraction se
    vérifie donc ici, pas au premier test rouge.
    """
    for chemin in MODULES:
        libres = _noms_libres(chemin)
        assert not libres, (
            f"{chemin.name} utilise des noms qu'il n'importe pas : {libres}. "
            "Le module s'importera quand même — la panne n'arrivera qu'à l'appel de la "
            "route, et ressemblera à un bug métier.")


def _imports_de(chemin: Path) -> set:
    """Les modules de premier niveau qu'un fichier importe."""
    arbre = ast.parse(io.open(chemin, encoding="utf-8").read())
    out = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module.split(".")[0])
    return out


def test_les_dependances_ne_remontent_jamais():
    """Le sens est unique : `routes/*` → `socle` → le reste, et `main` au-dessus de tout.

    Un `import main` dans le socle ou dans un module de routes fabrique un cycle — et un
    cycle d'imports ne casse pas toujours : il dépend de l'ordre de chargement, donc il
    marche sous pytest et tombe sous uvicorn, ou l'inverse. C'est la pire forme de panne
    à déboguer, et la moins chère à interdire.

    La première version de ce test ne regardait que `socle.py`. Un module de `routes/`
    remontant vers `main` aurait été le cas le PLUS probable — c'est là qu'on est tenté
    d'aller chercher un helper resté en arrière — et il n'était pas couvert.
    """
    # `main` est interdit à tous ; `routes` l'est en plus au socle, qui est SOUS eux.
    # Un module de routes important `socle` est au contraire le sens normal.
    for chemin in [RACINE / "socle.py"] + sorted((RACINE / "routes").glob("*.py")):
        defendus = {"main", "routes"} if chemin.name == "socle.py" else {"main"}
        interdits = sorted(_imports_de(chemin) & defendus)
        assert not interdits, (
            f"{chemin.name} importe {interdits} : cycle en préparation. Le helper qui "
            "manque doit DESCENDRE dans `socle.py`, pas être remonté depuis `main`.")


def test_tout_routeur_de_routes_est_reellement_inclus():
    """La condition écrite dans ARCH-1 : le découpage ne change ni les chemins ni le
    contrat d'API. Une route portée par un `APIRouter` doit se trouver dans `app.routes`
    comme les autres — c'est de là que les trois cliquets du dépôt (autorisation, sorties
    d'identité, CSP) tirent leur inventaire. Si elle n'y était pas, ils passeraient au
    vert en ne regardant plus rien.

    Le test DÉCOUVRE les modules au lieu de les nommer. Sa première version citait
    `recherche` en dur : elle serait restée verte en ne couvrant aucun des modules
    suivants, ce qui est le mode d'échec habituel d'un cliquet écrit pendant la première
    étape d'un chantier à étapes.

    Un `include_router` oublié ne casse RIEN au démarrage : l'application se lance, le
    module s'importe, et tout un domaine répond 404 comme s'il n'avait jamais existé.
    """
    import importlib

    modules = [f.stem for f in (RACINE / "routes").glob("*.py")
               if f.stem != "__init__"]
    assert modules, "aucun module dans routes/ — le découpage a disparu"
    chemins_app = {r.path for r in main.app.routes if hasattr(r, "path")}
    for nom in modules:
        mod = importlib.import_module(f"routes.{nom}")
        assert hasattr(mod, "router"), (
            f"routes/{nom}.py n'expose pas de `router` : `main.py` ne peut pas l'inclure")
        portes = {r.path for r in mod.router.routes if hasattr(r, "path")}
        assert portes, f"routes/{nom}.py ne porte aucune route"
        absentes = sorted(portes - chemins_app)
        assert not absentes, (
            f"routes/{nom}.py déclare des routes que l'application ne sert pas : "
            f"{absentes}. Un `app.include_router` manque — rien ne le signalera "
            "ailleurs, le domaine répondra simplement 404.")


def test_aucune_route_ne_depend_de_son_rang_dans_la_table():
    """Le découpage RÉORDONNE la table de routage — 96 routes ont changé de rang en
    sortant un seul bloc. C'est sans effet aujourd'hui, et il faut que ça le reste.

    FastAPI teste les routes dans l'ordre : une route LITTÉRALE placée après une route
    PARAMÉTRÉE qui pourrait la capter devient inatteignable. Tant que les deux vivent
    dans le même bloc, l'ordre relatif survit au déménagement ; le jour où quelqu'un
    ajoute `/api/x/{id}` dans un bloc et `/api/x/fusion` dans un autre, l'ordre cesse
    d'être un détail et devient une décision — que personne n'aura prise.

    Mesuré au moment d'écrire ceci : 127 routes, 71 paramétrées, ZÉRO paire sensible.
    Ce test dit quand cette phrase cesse d'être vraie.
    """
    routes = [(sorted(getattr(r, "methods", ["MOUNT"]))[0], r.path)
              for r in main.app.routes if hasattr(r, "path")]
    parametrees = [(m, p) for m, p in routes if "{" in p]
    litterales = [(m, p) for m, p in routes if "{" not in p]

    def capte(motif: str, chemin: str) -> bool:
        rx = "^" + re.sub(r"\\\{[^}]*\\\}", "[^/]+", re.escape(motif)) + "$"
        return re.match(rx, chemin) is not None

    collisions = [f"{pl} peut être captée par {pp}"
                  for mp, pp in parametrees for ml, pl in litterales
                  if mp == ml and capte(pp, pl)]
    assert not collisions, (
        "Ces routes dépendent de leur ORDRE dans la table :\n  "
        + "\n  ".join(collisions)
        + "\n\nLe découpage par domaine réordonne cette table. Il faut "
        "soit les rendre non ambiguës, soit garantir leur ordre relatif "
        "explicitement — pas s'en remettre au hasard du fichier dont elles "
        "sortent.")
