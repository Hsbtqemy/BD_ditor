"""L'inventaire des routes de l'application, et le plancher qui l'empêche de rétrécir.

ARCH-2. Deux cliquets du dépôt tirent leur inventaire de `app.routes` — l'autorisation
(AUTH-2, « toute route consulte la portée ou figure sur `HORS_PERIMETRE` avec sa raison »)
et les sorties d'identité (AUTH-5, « toute surface qui laisse partir un login l'a
déclaré »). La forme de cet attribut a changé sous eux : FastAPI ≥ 0.137 n'aplatit plus les
routeurs inclus, il dépose des objets PARESSEUX qui délèguent à l'exécution. Les routes
répondent toujours — `/api/analyse/info` rend 200, une route inventée rend 404 — mais elles
ne sont plus énumérables.

Aucun des deux ne s'est mis à échouer. Ils ont continué de PASSER en ne regardant plus que
53 routes sur 122, et 23 GET sur 51. Une garde qui tombe est un incident ; une garde qui
approuve en n'ayant rien vu est un mensonge, et c'est celui-là qu'on a eu.

Ce module existe pour DEUX raisons, et la seconde est la plus importante.

1. **L'aplatissement vit à un seul endroit.** Le recopier dans quatre fichiers de test
   serait exactement la faute qu'il répare : une vérité écrite en plusieurs exemplaires,
   dont un seul finit par être corrigé. La marche transitive des dépendances était déjà
   dans cet état — deux versions récursives et une itérative, pour la même question.

2. **Un inventaire qui rétrécit doit ÉCHOUER, quelle qu'en soit la cause.** Aucune version
   de FastAPI ne promet la forme de `app.routes` : c'est un attribut interne qu'on lit
   parce qu'il n'y a rien d'autre, et la prochaine montée peut le changer encore. C'est
   pourquoi `plancher_source()` ne lui demande rien — il compte les décorateurs de route
   dans le SOURCE, par AST — et pourquoi chaque cliquet confronte ce qu'il a vu à ce
   nombre. Le seul test qui avait bronché, `test_decoupage_api`, est justement celui qui
   comparait une source à un inventaire au lieu de parcourir l'inventaire seul.

Ce qu'il ne fait PAS, et qu'il ne faut pas lui prêter : il ne rend visible que ce que
l'application SERT. Un `include_router` oublié reste invisible ici, et il le faut — sinon
`test_decoupage_api` deviendrait complaisant en même temps qu'il serait réparé.
"""
import ast
from pathlib import Path

from starlette.routing import Mount

import main

RACINE = Path(__file__).resolve().parent.parent

# Les verbes qui DÉCLARENT une route dans le source. `api_route` et `websocket` n'y servent
# pas aujourd'hui ; les compter coûte une ligne, et un plancher qui les ignorerait
# vieillirait dans le sens permissif le jour où l'un apparaît.
_VERBES = frozenset({"get", "post", "put", "patch", "delete", "head", "options",
                     "api_route", "websocket"})


# --------------------------------------------------------------------------- #
# L'aplatissement
# --------------------------------------------------------------------------- #
def aplatir(routes):
    """Les objets de routage, quelle que soit la forme de `app.routes`.

    Deux formes, et le balayage doit marcher sur les DEUX — corriger pour l'une en cassant
    l'autre remettrait la panne au prochain verrou, dans un sens ou dans l'autre.

    - FastAPI ≤ 0.133 aplatit `include_router` à l'inclusion : `app.routes` contient
      directement des `APIRoute` dont les dépendances de routeur sont déjà fusionnées.
    - FastAPI ≥ 0.137 y dépose un routeur PARESSEUX qui calcule ses candidats à la
      demande, et peut en contenir d'autres — d'où la récursion.

    On reconnaît la seconde forme par son COMPORTEMENT (`effective_candidates`) et non par
    son type : `_IncludedRouter` est un nom privé, et un nom privé qui change fait
    silencieusement rétrécir l'inventaire. C'est la panne d'ARCH-2 en entier.
    """
    for r in routes:
        candidats = getattr(r, "effective_candidates", None)
        if callable(candidats):
            yield from aplatir(candidats())
        else:
            yield r


def objets(app=None):
    """Tout ce que l'application sert, aplati : routes API, routes nues et montages."""
    return list(aplatir((app or main.app).routes))


def chemin_de(r):
    """Le chemin EFFECTIF d'un objet de routage aplati, ou None s'il n'en porte pas.

    Sous la forme paresseuse, une route non-FastAPI (un montage, la route nue de
    `/openapi.json`) arrive emballée dans un objet de contexte qui garde son chemin dans
    l'objet enveloppé — et c'est le chemin PRÉFIXÉ de l'enveloppe qui compte, pas celui
    que le module déclarait.
    """
    for cible in (r, getattr(r, "starlette_route", None),
                  getattr(r, "original_route", None)):
        chemin = getattr(cible, "path", None)
        if chemin:
            return chemin
    return None


def routes_api(app=None):
    """Les routes FastAPI de l'application, avec leurs dépendances EFFECTIVES.

    Le filtre porte sur `dependant` et non sur `isinstance(r, APIRoute)` : sous la forme
    paresseuse, la route effective est un objet de contexte qui porte le même contrat
    (`path`, `methods`, `dependant`, `endpoint`) sans hériter d'`APIRoute`. C'est ce
    `isinstance` qui écartait 69 routes en silence, dans les deux cliquets à la fois.

    Et c'est bien la route EFFECTIVE qu'il faut, jamais celle que le module déclare : les
    dépendances de niveau routeur — `_capter_agent`, entre autres — n'existent que sur
    elle. La route d'origine ne les a jamais vues, et un cliquet qui l'interrogerait
    conclurait que le journal de provenance n'attribue rien à personne.
    """
    return [r for r in aplatir((app or main.app).routes)
            if getattr(r, "dependant", None) is not None]


def montages(app=None):
    """Les montages de fichiers (`Mount`), à quelque profondeur qu'ils soient inclus.

    Un montage ne passe par AUCUNE dépendance : le cliquet des routes ne peut pas le voir,
    il lui faut sa propre porte. C'est là qu'était la plus large fuite du dépôt
    (`/derivatives`, trouvée en relisant le 2026-08-27).
    """
    vus = []
    for r in aplatir((app or main.app).routes):
        for cible in (r, getattr(r, "starlette_route", None),
                      getattr(r, "original_route", None)):
            if isinstance(cible, Mount):
                vus.append(cible)
                break
    return vus


def chemins(app=None):
    """L'ensemble des chemins servis, montages compris — l'inventaire vu côté URL."""
    return {c for c in (chemin_de(r) for r in aplatir((app or main.app).routes))
            if c is not None}


def dependances(route) -> set:
    """Toutes les fonctions de dépendance atteignables depuis une route (transitif).

    Écrit ici parce que trois tests le refaisaient, en deux versions récursives et une
    itérative : la même vérité en trois exemplaires, dont deux auraient survécu à une
    correction de la troisième.
    """
    vus, pile = set(), [route.dependant]
    while pile:
        d = pile.pop()
        for sous in d.dependencies:
            if sous.call is not None:
                vus.add(sous.call)
            pile.append(sous)
    return vus


# --------------------------------------------------------------------------- #
# Le plancher
# --------------------------------------------------------------------------- #
def plancher_source(methode: str | None = None) -> int:
    """Combien de routes le SOURCE déclare — le plancher que l'inventaire doit atteindre.

    Compté par AST sur `main.py` et `routes/*.py`, donc sans rien demander à FastAPI. Un
    plancher recopié à la main vieillirait, et il vieillirait dans le sens PERMISSIF :
    l'application grossit, le chiffre reste, et la marge silencieuse remplace la garde.

    C'est un PLANCHER et non une égalité, parce qu'une route peut aussi arriver par
    `add_api_route` sans décorateur : l'inventaire peut légitimement dépasser le compte des
    décorateurs, jamais tomber dessous. Au 2026-09-05 les deux coïncident exactement —
    122 routes déclarées, 122 vues ; 51 GET des deux côtés.

    `methode` restreint le compte à un verbe (le cliquet des sorties ne balaie que les
    GET). Une route déclarée par `api_route(methods=[...])` échapperait à ce filtre : il
    n'en existe aucune, et `test_inventaire_routes` dit quand cette phrase cesse d'être
    vraie.
    """
    n = 0
    for chemin in [RACINE / "main.py"] + sorted((RACINE / "routes").glob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in noeud.decorator_list:
                appel = deco.func if isinstance(deco, ast.Call) else deco
                if not isinstance(appel, ast.Attribute) or appel.attr not in _VERBES:
                    continue
                if methode is None or appel.attr == methode.lower():
                    n += 1
    return n


def exiger_plancher(vues: int, cliquet: str, methode: str | None = None) -> None:
    """Refuse un inventaire qui a rétréci, au nom du cliquet qui vient de l'employer.

    Écrit ici et appelé par les quatre tests qui ÉNUMÈRENT, parce que la protection ne
    vaut que posée devant chacun. Un plancher unique, ailleurs, rendrait bien la suite
    rouge — mais le cliquet concerné resterait vert, et quelqu'un qui ne lit que son
    résultat conclurait qu'il a fait son travail. C'est précisément la lecture qui a laissé
    passer le 2026-09-05.

    Les quatre ne se protègent pas mutuellement, et l'un d'eux ne se protège pas du tout
    tout seul : `test_toute_route_capte_l_agent_courant` cherche des routes NON conformes,
    donc un inventaire tronqué ne lui retire que des routes conformes — il devient plus
    vert à mesure qu'il voit moins. Mesuré en lui donnant l'ancien inventaire : les trois
    planchers ont tiré, lui n'a rien dit.
    """
    plancher = plancher_source(methode)
    quoi = f"routes {methode.upper()}" if methode else "routes"
    assert vues >= plancher, (
        f"{cliquet} n'a examiné que {vues} {quoi}, alors que le source en déclare "
        f"{plancher}. Il n'a donc rien garanti sur les {plancher - vues} autres — et sans "
        "ce contrôle il aurait passé au vert en le taisant.\n\n"
        "Cause probable : la forme de `app.routes` a changé et `inventaire_routes.aplatir` "
        "ne reconnaît pas la nouvelle (c'est la panne d'ARCH-2, le 2026-09-05, quand "
        "FastAPI 0.137 a cessé d'aplatir les routeurs inclus). Seconde cause possible : un "
        "`include_router` manquant, que `test_decoupage_api` nommera plus précisément.")
