"""Le découpage de `main.py` en modules de routes tient-il debout ?  ARCH-1.

Ce fichier existe parce que la première extraction a produit **49 tests rouges** d'un
coup, tous par la même cause : trois noms — `citations_regions`, `STATUTS`, `nlp` — que le
bloc utilisait et que le nouveau module n'importait pas. Le module s'importe pourtant sans
broncher : un nom libre ne lève un `NameError` qu'à l'APPEL, donc le mal ne se voit qu'en
faisant tourner la route. J'avais dressé la liste des imports à l'œil plutôt que de la
calculer, ce qui est exactement le geste que ce test remplace.

SEPT affirmations, et chacune couvre une manière différente de rater une extraction.
"""
import ast
import builtins
import io
import re
from pathlib import Path

import inventaire_routes
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
        # Tout ce qui LIE un nom : def, lambda, class, import, `except … as`, affectation.
        # Trois oublis successifs ont été mesurés ici, tous produisant un FAUX positif —
        # `ClassDef` (qui n'a pas d'`args` et faisait planter la garde), `*args`/`**kwargs`
        # (`main._tei_el(**attrs)`), et les paramètres de `lambda` (`key=lambda x: …`).
        # Un faux positif dans un cliquet coûte plus qu'une lacune : on apprend à passer
        # outre, puis on passe outre le vrai.
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if not isinstance(n, ast.Lambda):
                definis.add(n.name)
            definis |= {a.arg for a in n.args.args + n.args.kwonlyargs
                        + n.args.posonlyargs}
            definis |= {a.arg for a in (n.args.vararg, n.args.kwarg) if a}
        elif isinstance(n, ast.ClassDef):
            definis.add(n.name)
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


def test_aucun_import_mort_de_part_et_d_autre_de_la_coupe():
    """Sortir un bloc laisse derrière lui les imports qui ne servaient qu'à lui.

    Ce n'est pas cosmétique : ces lignes affirment qu'un fichier dépend de choses dont il
    ne dépend plus. Le découpage en a tué TREIZE dans `main.py` — `accord`, `accord_inter`,
    `figure`, `undo`, `zipfile`, `json`, `re`, `datetime`, `BaseModel`, `Field`, `Query`,
    `UPOS_TAGS`, `CIBLES_ATTRIBUT` — dont onze le même jour, sans qu'aucun soit signalé.
    Le dépôt n'installe pas de linter : rien d'autre ne le dira.

    Le ré-export du socle est l'exception, et elle se DÉCLARE : sa ligne porte déjà
    `# noqa: F401`, et ses noms sont inutilisés par construction — c'est leur raison
    d'être. Le test lit cette marque au lieu de connaître le cas par cœur, pour qu'une
    autre exception légitime s'écrive de la même façon.
    """
    coupables = []
    for chemin in MODULES:
        src = io.open(chemin, encoding="utf-8").read()
        lignes = src.splitlines()
        arbre = ast.parse(src)
        utilises = set()
        for n in ast.walk(arbre):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                utilises.add(n.id)
            elif isinstance(n, ast.Attribute):
                racine = n
                while isinstance(racine, ast.Attribute):
                    racine = racine.value
                if isinstance(racine, ast.Name):
                    utilises.add(racine.id)
        for n in arbre.body:
            if not isinstance(n, (ast.Import, ast.ImportFrom)):
                continue
            # `from __future__ import annotations` est une directive, pas un nom
            if isinstance(n, ast.ImportFrom) and n.module == "__future__":
                continue
            bloc = " ".join(lignes[n.lineno - 1:n.end_lineno])
            if "noqa: F401" in bloc:
                continue
            for a in n.names:
                nom = a.asname or a.name.split(".")[0]
                if nom not in utilises:
                    coupables.append(f"{chemin.name}:{n.lineno} {nom}")
    assert not coupables, (
        "Ces imports ne servent plus a rien — vestiges d'un bloc parti ailleurs : "
        + ", ".join(coupables)
        + ". Un import mort ment sur les dependances du module. Si l'un est voulu, "
        "marquer sa ligne `# noqa: F401` avec la raison.")


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
    comme les autres — c'est de là que DEUX cliquets du dépôt tirent leur inventaire :
    l'autorisation et les sorties d'identité. Si elle n'y était pas, ils passeraient au
    vert en ne regardant plus rien.

    Cette phrase disait « les TROIS cliquets, CSP comprise » : c'était faux, et corrigé le
    2026-09-05 (ARCH-2) en vérifiant. `test_csp` n'énumère rien — ses surfaces sont des
    listes écrites à la main — donc rien ne pouvait le rétrécir. Son mode d'échec est
    l'autre : il oublie ce qu'on ajoute au lieu de perdre ce qu'il voyait, et il a
    désormais son propre contrôle contre celui-là.

    Le 2026-09-05, ce test a été le SEUL des sept à broncher quand FastAPI 0.137 a cessé
    d'aplatir les routeurs inclus. Pas par chance : parce qu'il compare une SOURCE à un
    inventaire au lieu de parcourir l'inventaire seul. C'est l'argument entier du plancher
    dérivé que portent maintenant les deux autres cliquets.

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
    chemins_app = inventaire_routes.chemins()
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


def test_main_reexporte_tout_ce_que_le_socle_definit():
    """`main.py` ré-exporte le socle pour que `main.X` reste un nom valide : deux cliquets
    interrogent ces noms SUR `main`, et ARCH-1 pose comme condition de ne réécrire aucun
    test.

    La liste était dérivée de ce que `main.py` UTILISE, alors que la promesse porte sur ce
    qui a DÉMÉNAGÉ. Deux ensembles différents, qui coïncidaient par chance : chaque bloc
    extrait retire des usages, donc la liste rétrécit d'elle-même, et un nom cesse d'être
    joignable le jour où sa dernière route d'ici s'en va. Trois manquaient déjà (`FigureIn`,
    `TokenCorrectionIn`, `_BOM`) sans qu'aucun test ne bronche — parce qu'aucun ne le
    demandait encore. C'est une panne à retardement : muette au moment où on la crée,
    bruyante des mois plus tard, dans un test qu'on n'aura pas touché.

    Le test lit `socle.py` en SOURCE et non par `dir(socle)` : ce dernier renvoie aussi ce
    que le socle importe (`sqlite3`, `autorisation`…), qui n'a jamais déménagé et n'a pas à
    être ré-exporté.
    """
    arbre = ast.parse(io.open(RACINE / "socle.py", encoding="utf-8").read())
    definis = set()
    for n in arbre.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definis.add(n.name)
        elif isinstance(n, ast.Assign):
            definis |= {c.id for c in n.targets if isinstance(c, ast.Name)}
    assert definis, "socle.py ne définit rien — la lecture du source a échoué"

    absents = sorted(n for n in definis if not hasattr(main, n))
    assert not absents, (
        f"le socle définit {absents}, que `main` ne ré-exporte pas. Tant qu'aucun test ne "
        "les demande sur `main`, la suite reste verte : c'est précisément ce qui rend "
        "l'oubli durable.")

    # Et dans l'autre sens : un nom ré-exporté doit être CELUI du socle, pas un homonyme
    # redéfini plus bas dans `main.py`, qui écraserait l'import sans un mot.
    import socle
    for n in sorted(definis):
        assert getattr(main, n) is getattr(socle, n), (
            f"`main.{n}` n'est pas l'objet du socle : une définition de `main.py` le "
            "masque, et les deux versions vivront côte à côte.")

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

    Il a passé trois jours à mesurer 58 routes et 12 paramétrées sans que la phrase
    change : son `hasattr(r, "path")` écartait les sept routeurs paresseux de FastAPI 0.137
    (ARCH-2). Un test qui compte et qui n'annonce pas ce qu'il a compté ne peut pas dire
    qu'il a cessé de compter — d'où l'inventaire partagé, et le plancher dérivé qui garde
    les deux cliquets voisins.
    """
    inventaire_routes.exiger_plancher(len(inventaire_routes.routes_api()),
                                      "le contrôle de l'ordre de la table")
    routes = [(sorted(getattr(r, "methods", ["MOUNT"]))[0], inventaire_routes.chemin_de(r))
              for r in inventaire_routes.objets()]
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


def test_toute_route_capte_l_agent_courant():
    """La dépendance globale `_capter_agent` doit atteindre TOUTES les routes, y compris
    celles qui arrivent par un `include_router`.

    Ce test existe parce que le découpage l'a cassé. `include_router` FIGE les dépendances
    de chaque route au moment de l'inclusion : les trois routeurs étaient inclus quelques
    lignes AVANT `app.router.dependencies.append(Depends(_capter_agent))`, donc ils ne
    l'ont jamais reçue. Conséquence — le journal de provenance (A3) attribuait `NULL` à
    tout acte passant par ces domaines : les corrections de tokens, les figures citées, la
    recherche. L'attribution disparaissait, pas les fonctionnalités.

    Aucun test unitaire n'a bronché : 646 verts. C'est un audit E2E qui l'a vu, et
    indirectement — alice et bob devenaient tous deux anonymes, donc zéro re-touche entre
    auteurs distincts. Le prochain bloc extrait peut refaire exactement la même chose ;
    celui-ci le dira tout de suite, et en nommant la cause.

    ARCH-2, et c'est le plus inquiétant du lot : ce test-CI était aveugle aux mêmes
    69 routes. Il sautait tout objet sans `dependant` — commentaire à l'appui, « montages
    StaticFiles, non concernés » — et le routeur paresseux de FastAPI 0.137 n'en a pas. Il
    gardait donc exactement les sept routeurs inclus dont il est né, en ne regardant que
    les routes restées dans `main.py`. La panne du 2026-09-02 pouvait revenir à
    l'identique sous une suite verte.
    """
    inventaire_routes.exiger_plancher(len(inventaire_routes.routes_api()),
                                      "la garde de `_capter_agent`")
    orphelines = []
    for r in inventaire_routes.routes_api():
        if main._capter_agent not in inventaire_routes.dependances(r):
            orphelines.append(f"{sorted(r.methods)[0]} {r.path}")
    assert not orphelines, (
        "Ces routes ne captent pas l'agent courant, donc le journal de provenance leur "
        "attribuera `NULL` :\n  " + "\n  ".join(sorted(orphelines))
        + "\n\nCause probable : un `app.include_router(...)` placé AVANT "
        "`app.router.dependencies.append(Depends(_capter_agent))`. L'ordre compte, "
        "`include_router` fige les dépendances au moment de l'inclusion.")
