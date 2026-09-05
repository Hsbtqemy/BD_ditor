"""ARCH-2 — le module qui porte l'inventaire est devenu load-bearing : on le teste.

Trois cliquets lisent désormais `inventaire_routes` au lieu de parcourir `app.routes`
eux-mêmes. Une erreur ici ne casse rien de visible : elle rend simplement l'inventaire plus
petit, et les trois passent au vert en regardant moins. C'est la panne d'ARCH-2, déplacée
d'un cran — et la seule protection contre sa répétition est de tester l'aplatissement sur
les DEUX formes de `app.routes`, alors qu'un environnement donné n'en installe qu'une.

D'où les doublures ci-dessous. Elles ne reproduisent pas `_IncludedRouter` : elles
reproduisent le CONTRAT qu'on lit chez lui — « un objet de routage sait rendre ses
candidats ». Le jour où FastAPI renomme sa classe privée, ces tests continuent de décrire
ce que le dépôt attend, au lieu de disparaître avec le nom.
"""
import pytest
from fastapi import APIRouter, FastAPI

import inventaire_routes
import main


class _RouteFactice:
    """Une route ordinaire : rien à déplier, elle est déjà l'objet final."""

    def __init__(self, chemin, api=True):
        self.path = chemin
        self.methods = {"GET"}
        if api:
            self.dependant = object()


class _RouteurParesseux:
    """La forme de FastAPI ≥ 0.137 : un objet qui ne rend ses routes qu'à la demande.

    Il n'a VOLONTAIREMENT ni `path`, ni `methods`, ni `dependant` — c'est cette absence
    qui rendait les cliquets aveugles, chacun filtrant sur l'un des trois.
    """

    def __init__(self, *candidats):
        self._candidats = list(candidats)

    def effective_candidates(self):
        return self._candidats


# --------------------------------------------------------------------------- #
# Les deux formes
# --------------------------------------------------------------------------- #
def test_la_forme_deja_aplatie_passe_telle_quelle():
    """FastAPI ≤ 0.133 : `app.routes` contient déjà les routes finales."""
    routes = [_RouteFactice("/a"), _RouteFactice("/b")]
    assert [r.path for r in inventaire_routes.aplatir(routes)] == ["/a", "/b"]


def test_la_forme_paresseuse_est_depliee():
    """FastAPI ≥ 0.137 : un routeur inclus se déplie au lieu d'être compté pour un."""
    routes = [_RouteFactice("/a"),
              _RouteurParesseux(_RouteFactice("/b"), _RouteFactice("/c"))]
    assert [r.path for r in inventaire_routes.aplatir(routes)] == ["/a", "/b", "/c"]


def test_un_routeur_paresseux_imbrique_est_deplie_aussi():
    """`include_router` se cascade, et la forme paresseuse cascade avec lui.

    Sans récursion, l'inventaire s'arrêterait à la première couche — et il s'arrêterait en
    silence, en rendant un objet qui n'est ni une route ni une erreur.
    """
    routes = [_RouteurParesseux(
        _RouteFactice("/a"),
        _RouteurParesseux(_RouteFactice("/b"), _RouteurParesseux(_RouteFactice("/c"))))]
    assert [r.path for r in inventaire_routes.aplatir(routes)] == ["/a", "/b", "/c"]


def test_aucun_objet_paresseux_ne_survit_a_l_aplatissement():
    """Sur l'application RÉELLE, et quelle que soit la version installée.

    C'est le seul contrôle de ce fichier qui ne dépend d'aucune doublure : si un objet
    sachant rendre des candidats traverse l'aplatissement, c'est qu'une forme nouvelle est
    apparue et que l'inventaire vient de rétrécir sans le dire.
    """
    restants = [r for r in inventaire_routes.objets()
                if callable(getattr(r, "effective_candidates", None))]
    assert not restants, (
        f"{len(restants)} objets de routage n'ont pas été dépliés : la forme de "
        "`app.routes` a encore changé. L'inventaire est incomplet, et les cliquets qui le "
        "lisent passeront au vert en regardant moins.")


def test_une_route_non_api_reste_dans_l_inventaire_sans_entrer_chez_les_routes_api():
    """`/openapi.json` et `/docs` sont des routes NUES : aucune dépendance à interroger.

    Deux exigences opposées, et il faut les deux. Elles doivent rester dans l'inventaire
    des CHEMINS — le cliquet du découpage compare des chemins, et un chemin servi qui
    manquerait à cet ensemble ferait échouer la comparaison à tort. Et elles doivent rester
    HORS de l'inventaire des routes API : le plancher ne compte que ce que le dépôt
    déclare, donc les compter le ferait dépasser sans qu'aucune route ait été écrite.
    """
    faux = FastAPI()
    faux.router.routes = [_RouteFactice("/api/vraie"),
                          _RouteFactice("/openapi.json", api=False)]
    assert inventaire_routes.chemins(faux) == {"/api/vraie", "/openapi.json"}
    assert [r.path for r in inventaire_routes.routes_api(faux)] == ["/api/vraie"]


# --------------------------------------------------------------------------- #
# Ce que l'aplatissement ne doit PAS rendre visible
# --------------------------------------------------------------------------- #
def test_un_routeur_non_inclus_reste_invisible():
    """L'inventaire ne montre que ce que l'application SERT.

    C'est la condition pour que `test_decoupage_api` reste vert pour la BONNE raison : il
    compare les routes qu'un module DÉCLARE aux chemins que l'app sert, et il n'attrape un
    `include_router` oublié que si le second ensemble reste honnête. Un aplatissement qui
    irait chercher les routeurs importés plutôt que ceux montés le réparerait en le rendant
    complaisant — et un domaine entier pourrait répondre 404 sous une suite verte.

    Ce test tourne sur le VRAI FastAPI installé, donc il vérifie aussi que l'aplatissement
    voit la forme réelle de cette version-ci, dans les deux états.
    """
    app = FastAPI()
    routeur = APIRouter()

    @routeur.get("/api/oubliee")
    async def _oubliee():                                   # pragma: no cover
        return {}

    assert "/api/oubliee" not in inventaire_routes.chemins(app), (
        "un routeur jamais inclus apparaît dans l'inventaire : le cliquet du découpage "
        "cesserait de voir un `include_router` manquant")
    app.include_router(routeur)
    assert "/api/oubliee" in inventaire_routes.chemins(app), (
        "un routeur inclus reste invisible : c'est la panne d'ARCH-2 elle-même")


# --------------------------------------------------------------------------- #
# Le plancher
# --------------------------------------------------------------------------- #
def test_le_plancher_compte_les_routes_declarees_dans_le_source():
    """Le plancher se DÉRIVE, il ne se recopie pas — reste à vérifier qu'il compte.

    Un plancher nul serait le pire des résultats : il rendrait vraie toute comparaison
    « j'en ai vu au moins autant », et remplacerait la garde par un rituel.
    """
    total = inventaire_routes.plancher_source()
    assert total > 100, (
        f"le plancher dérivé du source est de {total} routes, ce qui ne ressemble pas à ce "
        "dépôt : la lecture AST de `main.py` / `routes/*.py` a échoué, et toute comparaison "
        "à ce plancher est désormais vacante")
    assert inventaire_routes.plancher_source("get") > 40


def test_le_plancher_par_verbe_ne_perd_aucune_route():
    """Somme des verbes = total. Ce test dit quand cette phrase cesse d'être vraie.

    Le cliquet des sorties d'identité ne balaie que les GET : son plancher est donc
    `plancher_source("get")`. Une route déclarée par `@app.api_route(methods=["GET"])`
    entrerait dans le total sans entrer dans aucun verbe — le plancher des GET la
    manquerait, et le manquerait en silence. Il n'en existe aucune aujourd'hui ; si celui-ci
    tombe, c'est qu'il en existe une, et `plancher_source` doit apprendre à la lire.
    """
    verbes = ("get", "post", "put", "patch", "delete", "head", "options")
    par_verbe = sum(inventaire_routes.plancher_source(v) for v in verbes)
    assert par_verbe == inventaire_routes.plancher_source(), (
        f"{inventaire_routes.plancher_source() - par_verbe} route(s) sont déclarées "
        "autrement que par un verbe HTTP (`api_route` ou `websocket`). Le plancher par "
        "verbe les manque : enseignez-lui la forme employée avant de le croire.")


def test_l_inventaire_reel_atteint_le_plancher():
    """Le rapprochement qui manquait le 2026-09-05, à sa place la plus générale.

    Les deux cliquets portent chacun le leur, sur leur propre découpe. Celui-ci le fait sur
    l'inventaire brut : si l'application sert moins de routes qu'elle n'en déclare, tout ce
    qui se mesure en aval mesure autre chose.
    """
    inventaire_routes.exiger_plancher(len(inventaire_routes.routes_api()),
                                      "l'inventaire brut")


def test_l_exigence_de_plancher_mord():
    """Les QUATRE tests qui énumèrent passent par `exiger_plancher`. Elle doit refuser.

    C'est le point unique dont le silence rendrait les quatre muets d'un coup — la même
    forme de risque que celle qu'ARCH-2 vient de fermer, un cran plus haut. Une exigence
    partagée qu'on n'a jamais vue échouer n'est pas une exigence, c'est une ligne.

    Mesuré en donnant aux quatre cliquets l'ancien inventaire (celui qui filtrait sur
    `isinstance(r, APIRoute)`) : trois ont tiré — 53/122, 23/51, 53/122 — et la garde de
    `_capter_agent` n'a rien dit, parce qu'un inventaire tronqué ne lui retire que des
    routes conformes. C'est pourquoi elle appelle l'exigence explicitement.
    """
    plancher = inventaire_routes.plancher_source()
    with pytest.raises(AssertionError, match=r"n'a examiné que 1 routes"):
        inventaire_routes.exiger_plancher(1, "un cliquet de démonstration")
    with pytest.raises(AssertionError, match=r"routes GET"):
        inventaire_routes.exiger_plancher(0, "idem", methode="get")
    # Et elle laisse passer ce qui atteint le plancher, sinon elle serait inutilisable.
    inventaire_routes.exiger_plancher(plancher, "un cliquet complet")


def test_le_montage_des_assets_est_vu():
    """Un montage n'a pas de `dependant` : il sort de l'inventaire des routes API, et il
    doit rester joignable par sa propre porte — celle du cliquet d'autorisation."""
    assert "/static" in [m.path for m in inventaire_routes.montages()]


def test_les_dependances_sont_transitives():
    """La marche des dépendances descend, sinon `_capter_agent` posé sur le routeur
    passerait pour absent de chaque route qu'il couvre."""
    for r in inventaire_routes.routes_api():
        if r.path == "/api/sante":
            assert main._capter_agent in inventaire_routes.dependances(r)
            return
    pytest.fail("/api/sante a disparu de l'inventaire : le décor de ce test n'existe plus")
