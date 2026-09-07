"""UX-10 — les surfaces de l'application, et ce que chaque audit déclare en couvrir.

Ce module existe AVANT la cinquième page, et c'est délibéré : écrit après, il serait né
en constatant l'omission qu'il devait empêcher.

**Le défaut qu'il ferme.** Huit fichiers énumèrent les quatre surfaces — les sept audits
E2E et `test_csp` —, et un seul est gardé contre l'oubli. Ajouter `/administration` sans
penser à `test_e2e_a11y.SURFACES` donne une page jamais auditée pour l'accessibilité : la
page marche, la suite est verte, l'audit approuve en ne regardant pas là. C'est la forme
que ce dépôt connaît par cœur, à ceci près qu'elle est ici PRÉVISIBLE — on sait où elle
frappera avant de frapper.

**Les deux modes d'échec sont opposés, et il faut les deux gardes.** Une ÉNUMÉRATION perd
ce qu'elle voyait (ARCH-2 : deux cliquets ont continué de passer en ne regardant plus que
53 routes sur 122). Une LISTE ÉCRITE À LA MAIN oublie ce qu'on ajoute. `inventaire_routes`
traite le premier ; celui-ci traite le second, et il ne peut pas s'en passer : on ne DEVINE
pas qu'un audit de défilement n'a rien à dire d'un canevas de pan/zoom. Cette intention
s'écrit, donc elle se déclare.

**Pourquoi les déclarations se lisent par AST et non par import.** Les modules d'audit
importent Playwright ; là où il n'est pas installé, les importer ferait tomber le contrôle
pour une raison étrangère à ce qu'il contrôle. Lire le source les atteint tous, partout, et
c'est aussi la doctrine d'`exiger_plancher` : dériver du SOURCE, parce qu'un chiffre — ou
une liste — recopié vieillit dans le sens permissif.

**Et la liste des modules se DÉRIVE elle aussi**, par `glob`. Une liste manuelle de listes
manuelles aurait exactement le défaut qu'on répare, une couche plus haut.
"""
import ast
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent

# Les deux noms qu'un module d'audit doit porter. `AUDITEES` dit ce qu'il regarde,
# `HORS_PERIMETRE` ce qu'il écarte AVEC SA RAISON — le patron de `test_autorisation` et de
# `test_sorties_identite`, où une exception se déclare plutôt qu'elle ne se constate.
NOM_AUDITEES = "SURFACES_AUDITEES"
NOM_HORS = "SURFACES_HORS_PERIMETRE"


def surfaces_servies(client):
    """Les chemins qui servent réellement du HTML, mesurés et non recopiés.

    Extrait de `test_csp.test_les_surfaces_html_suivent_l_application`, qui l'employait
    seul. Le partager plutôt que le recopier n'est pas du rangement : le 2026-09-07, deux
    copies d'une même procédure ont dérivé dans `docs/exploitation.md` sans que personne
    le voie, chacune finissant par porter ce qui manquait à l'autre. Deux détections de
    surfaces auraient fini par répondre deux choses.
    """
    import inventaire_routes

    servies = set()
    for r in inventaire_routes.routes_api():
        # Les gabarits paramétrés sont écartés : `/derivatives/{chemin:path}` sert des
        # IMAGES, pas du HTML, et aucune surface d'application n'est paramétrée.
        if "GET" not in r.methods or r.path.startswith("/api/") or "{" in r.path:
            continue
        if "text/html" in client.get(r.path).headers.get("content-type", ""):
            servies.add(r.path)
    return servies


def modules_d_audit():
    """Les fichiers d'audit E2E, DÉRIVÉS et non énumérés."""
    return sorted(DOSSIER.glob("test_e2e_*.py"))


def chemins_cites(fichier, servies):
    """Les surfaces qu'un module NOMME réellement dans son source.

    C'est ce qui rattache une déclaration à son module. Sans cela, `SURFACES_AUDITEES`
    est une seconde copie posée à côté de la vraie liste, et rien ne les relie : mesuré
    le 2026-09-07 en retirant `/corpus` du `SURFACES` de `test_e2e_a11y` sans toucher à
    la déclaration — la Bibliothèque cessait d'être auditée pour l'accessibilité, et la
    garde écrite le soir même pour empêcher exactement cela restait verte.

    On lit les CONSTANTES de chaînes, f-strings comprises : `ast.walk` traverse les
    `JoinedStr`, dont la partie littérale de `f"/?album={…}"` est bien `"/?album="`. Un
    chemin est cité s'il apparaît tel quel ou suivi de sa requête — `"/exploration?champ=
    lemme"` cite `/exploration`.

    Le sens de l'imprécision est choisi. Un faux POSITIF (une chaîne `"/"` incidente, un
    `split`) fait croire que le module va quelque part où il ne va pas : cela rend le
    contrôle plus permissif, jamais plus bruyant. Un faux NÉGATIF est impossible ici — un
    module qui atteint une page sans jamais nommer son chemin n'existe pas.
    """
    arbre = ast.parse(Path(fichier).read_text(encoding="utf-8"))
    textes = [n.value for n in ast.walk(arbre)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return {p for p in servies
            if any(s == p or s.startswith(p + "?") for s in textes)}


def listes_de_surfaces(fichier, servies):
    """Les littéraux qui ÉNUMÈRENT des surfaces ailleurs que dans la déclaration.

    Rend `[(ligne, [chemins])]`. Le seuil est DEUX : un littéral qui ne nomme qu'une
    surface désigne une cible précise — `page.goto(".../corpus")`, une exemption ciblée —
    et n'a rien d'une énumération. À partir de deux, le littéral fait ce que la
    déclaration fait déjà, et les deux vont diverger.

    **Le défaut est mesuré, et il a survécu à la première garde.** `test_e2e_a11y`
    déclarait correctement ses cinq surfaces le 2026-09-07 et portait, quatre cents lignes
    plus bas, un `@pytest.mark.parametrize("surface", ["/corpus", "/", "/recherche",
    "/exploration"])` écrit à la main. La déclaration était juste, les chemins étaient bien
    cités, et `/administration` n'entrait dans aucun des états que ce test-là visite —
    le bandeau de portée vide, injecté par `theme.js` sur TOUTES les surfaces. Rien ne
    signalait le trou : la garde d'à côté ferme « aucun audit ne mentionne cette surface »,
    pas « cet audit la mentionne ici et l'oublie là ».

    Les deux déclarations sont exclues, elles et tout ce qu'elles contiennent : ce sont les
    seules à avoir le droit d'énumérer. Tout le reste doit DÉRIVER d'elles.
    """
    arbre = ast.parse(Path(fichier).read_text(encoding="utf-8"))

    exclus = set()
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign) and any(
                isinstance(c, ast.Name) and c.id in (NOM_AUDITEES, NOM_HORS)
                for c in noeud.targets):
            # `id()` et non l'égalité : deux nœuds AST distincts peuvent être égaux, et on
            # veut exclure CES nœuds-là. L'arbre reste vivant tant que `arbre` l'est.
            exclus.update(id(sous) for sous in ast.walk(noeud.value))

    trouves = []
    for noeud in ast.walk(arbre):
        if id(noeud) in exclus:
            continue
        if isinstance(noeud, (ast.List, ast.Tuple, ast.Set)):
            elements = noeud.elts
        elif isinstance(noeud, ast.Dict):
            elements = [c for c in noeud.keys if c is not None]
        else:
            continue
        vus = {p for e in elements
               if isinstance(e, ast.Constant) and isinstance(e.value, str)
               for p in servies if e.value == p or e.value.startswith(p + "?")}
        if len(vus) >= 2:
            trouves.append((noeud.lineno, sorted(vus)))
    return trouves


def declarations(fichier):
    """`(auditees, hors_perimetre)` lus dans le source, ou `(None, None)` si absents.

    On accepte n'importe quel littéral pour `AUDITEES` — les audits stockent leurs
    surfaces tantôt en dict de lambdas, tantôt en liste de tuples —, seule compte la
    déclaration explicite. Une valeur non littérale (une compréhension, un appel) est
    traitée comme absente : ce qu'on ne peut pas lire, on ne le réputera pas déclaré.
    """
    arbre = ast.parse(Path(fichier).read_text(encoding="utf-8"))
    trouve = {}
    for noeud in arbre.body:
        if not isinstance(noeud, ast.Assign):
            continue
        for cible in noeud.targets:
            if isinstance(cible, ast.Name) and cible.id in (NOM_AUDITEES, NOM_HORS):
                try:
                    trouve[cible.id] = ast.literal_eval(noeud.value)
                except (ValueError, SyntaxError):
                    # Une structure dont les VALEURS ne sont pas littérales — un dict de
                    # lambdas, la forme naturelle d'un audit paramétré — reste une
                    # déclaration parfaitement lisible par ses CLÉS. C'est ce qui permet
                    # à la liste réelle d'un audit d'ÊTRE sa déclaration, au lieu d'en
                    # avoir une jumelle qui dérive.
                    if isinstance(noeud.value, ast.Dict):
                        try:
                            trouve[cible.id] = [ast.literal_eval(c)
                                                for c in noeud.value.keys]
                        except (ValueError, SyntaxError):
                            pass
    return trouve.get(NOM_AUDITEES), trouve.get(NOM_HORS)
