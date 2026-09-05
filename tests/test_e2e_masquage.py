"""Ce qu'on déclare caché est vraiment caché — la garde de la famille `[hidden]`.

Les scripts de surface masquent par la PROPRIÉTÉ DOM (`el.hidden = true`), qui n'agit
qu'à travers la règle du navigateur `[hidden] { display: none }`. Toute règle de la
feuille qui pose un `display` sur le même élément l'emporte, par simple spécificité — et
l'élément reste à l'écran alors que le code le croit caché.

Le dépôt connaît le piège et le garde par une dizaine de règles, l'une avec le commentaire
« sinon le display:flex écrase [hidden] ». Il en manquait CINQ, trouvées le 2026-09-04 :
`.dist` — la distribution restait affichée sous le tableau de croisement après une bascule
de vue —, les trois filtres `#wrap-champ`, `#wrap-lemme`, `#wrap-kwic`, visibles dans des
vues qui ne les emploient pas, et `.corpus-synthese`, dont le cadre bordé s'affichait vide.

**Le cinquième a été trouvé par la RELECTURE de ce test, pas par ce test.** Sa première
version ne captait que la forme `$("#id").hidden` et affirmait dans son en-tête que c'était
la seule employée dans le dépôt. Mesuré : 35 des 88 affectations `.hidden` des quatre
scripts passaient par une variable, et lui échappaient — dont `.corpus-synthese`. Pire, la
garde censée détecter ce cas (« aucune cible trouvée ») ne pouvait jamais se déclencher,
puisqu'il restait toujours des formes directes. Une garde écrite pour surveiller un angle
mort en avait un.

**La résolution des variables est POSITIONNELLE**, et ce n'est pas un raffinement : une
résolution globale associait `box` à sa dernière définition du fichier, alors que
`corpus.js` s'en sert pour TROIS éléments différents selon la fonction. Elle désignait donc
`#jobs`, jamais masqué, et manquait `#album-detail`, qui l'est.

**Ce que le test ne sait pas lire, il le DIT** : toute affectation `.hidden` dont la
variable ne remonte à aucun `$("#…")` doit figurer dans `NON_RESOLUS` avec sa raison. C'est
le patron de `test_autorisation.py` et de `test_sorties_identite.py` — soit c'est couvert,
soit c'est déclaré. Sans cette liste, une forme nouvelle sortirait du périmètre en silence,
et le vert deviendrait un mensonge.

Le défaut dormait depuis longtemps sur l'Exploration : `overflow: hidden` clippait ce qui
dépassait, donc la distribution en trop était présente mais INATTEIGNABLE. Poser un cadre
de défilement l'a rendue visible, et une passe de QA l'a vue le jour même.

Le marqueur `e2e` est posé PAR TEST : celui qui ouvre un navigateur en est, la garde
du périmètre non — elle ne lit que des sources et tourne dans la suite par défaut.
"""
import re
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

# Le marqueur `e2e` se pose PAR TEST et non sur le module : la garde du périmètre ne lit
# que des sources et n'ouvre aucun navigateur. La marquer `e2e` la sortait de la suite par
# défaut, donc de la boucle courte — or c'est elle qui dit quand le balayage cesse de
# couvrir quelque chose, et cette information n'a aucune raison d'attendre un run long.

RACINE = Path(__file__).resolve().parent.parent
SURFACES = [("/", "viewer.js"), ("/recherche", "recherche.js"),
            ("/corpus", "corpus.js"), ("/exploration", "exploration.js")]

DIRECT = re.compile(r'\$\(\s*"#([a-z0-9-]+)"\s*\)\.hidden\s*=')
AFFECT = re.compile(r'(\w+)\s*=\s*(?:\$\(\s*"#([a-z0-9-]+)"\s*\)'
                    r'|document\.getElementById\(\s*"([a-z0-9-]+)"\s*\))')
VAR = re.compile(r'(?<![.\w])(\w+)\.hidden\s*=')

# Les affectations dont la cible ne remonte à aucun `$("#…")`, avec la raison de les
# laisser hors du balayage. Une entrée par (fichier, nom de variable).
NON_RESOLUS = {
    ("exploration.js", "el"): (
        "Le paramètre d'un `forEach` sur `.sub-title` : la cible est une CLASSE, pas un "
        "identifiant, donc `getElementById` ne l'atteint pas. Vérifié à la main le "
        "2026-09-04 — `.sub-title` ne pose aucun `display`, l'attribut agit. Le jour où "
        "le balayage saura viser un sélecteur, cette entrée disparaît."),
}


def cibles(source: str):
    """Les identifiants dont le script bascule le `hidden`, et ce qu'il n'a pas su lire.

    Chaque `X.hidden` remonte à la définition de `X` la plus proche EN AMONT — la portée
    réelle du code, et non la dernière définition du fichier.
    """
    defs = [(m.start(), m.group(1), m.group(2) or m.group(3))
            for m in AFFECT.finditer(source)]
    ids, orphelins = set(DIRECT.findall(source)), []
    for m in VAR.finditer(source):
        amont = [i for (pos, nom, i) in defs if nom == m.group(1) and pos < m.start()]
        if amont:
            ids.add(amont[-1])
        else:
            orphelins.append((source[:m.start()].count("\n") + 1, m.group(1)))
    return sorted(ids), orphelins


SONDE = """(ids) => {
  const out = [];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;                       // injecté à la demande : rien à mesurer
    const avant = el.hidden;
    el.hidden = true;
    const d = getComputedStyle(el).display;
    el.hidden = avant;
    if (d !== 'none') out.push(`#${id} → display:${d}`);
  }
  return out;
}"""


@pytest.mark.e2e
@pytest.mark.parametrize("chemin, script", SURFACES)
def test_un_element_declare_cache_l_est_vraiment(page, live_server, chemin, script):
    """Pour CHAQUE élément que la surface masque, poser `hidden` doit donner `display:none`.

    On demande au navigateur plutôt qu'à la feuille de style : la question est celle du
    style CALCULÉ, où se joue la spécificité, et une lecture du CSS ne saurait pas dire
    laquelle des deux règles gagne.
    """
    ids, _ = cibles((RACINE / "static" / script).read_text(encoding="utf-8"))
    assert ids, (
        f"aucune cible `.hidden` trouvée dans {script} : soit le masquage a changé de "
        "forme, soit ce test ne couvre plus rien — les deux demandent une relecture")

    page.goto(live_server + chemin, wait_until="networkidle")
    coupables = page.evaluate(SONDE, ids)
    assert not coupables, (
        f"Sur {chemin}, ces éléments restent AFFICHÉS malgré `hidden` — une règle de la "
        f"feuille écrase `[hidden] {{ display: none }}` : {', '.join(coupables)}. "
        "Ajouter le garde `<sélecteur>[hidden] { display: none; }` à côté de la règle "
        "fautive, comme la dizaine qui existent déjà.")


@pytest.mark.parametrize("chemin, script", SURFACES)
def test_toute_cible_illisible_est_declaree(chemin, script):
    """Le périmètre du balayage ne rétrécit pas en silence.

    C'est la garde qui manquait à la première version, et son absence a coûté un défaut :
    une affectation que l'extraction ne sait pas résoudre sortait du test sans que rien
    ne le dise. Elle doit maintenant être déclarée avec sa raison, ou faire échouer.
    """
    _, orphelins = cibles((RACINE / "static" / script).read_text(encoding="utf-8"))
    non_declares = [(ligne, nom) for ligne, nom in orphelins
                    if (script, nom) not in NON_RESOLUS]
    assert not non_declares, (
        f"{script} : ces affectations `.hidden` ne remontent à aucun `$(\"#…\")`, donc le "
        "balayage ne les couvre pas — "
        + ", ".join(f"`{nom}.hidden` ligne {ligne}" for ligne, nom in non_declares)
        + ". Soit la cible reçoit un identifiant, soit l'entrée rejoint `NON_RESOLUS` "
          "avec la raison de l'y laisser ET la vérification faite à la main.")
