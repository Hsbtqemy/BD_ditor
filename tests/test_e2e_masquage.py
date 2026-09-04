"""Ce qu'on déclare caché est vraiment caché — la garde de la famille `[hidden]`.

Les scripts de surface masquent par la PROPRIÉTÉ DOM (`el.hidden = true`), qui n'agit
qu'à travers la règle du navigateur `[hidden] { display: none }`. Toute règle de la
feuille qui pose un `display` sur le même élément l'emporte, par simple spécificité — et
l'élément reste à l'écran alors que le code le croit caché.

Le dépôt connaît le piège : dix règles `…[hidden] { display: none }` existent, l'une
avec le commentaire « sinon le display:flex écrase [hidden] ». Il en manquait QUATRE, tous
sur l'Exploration, trouvés le 2026-09-04 : `.dist` — la distribution restait affichée sous
le tableau de croisement après une bascule de vue — et les trois filtres `#wrap-champ`,
`#wrap-lemme`, `#wrap-kwic`, visibles dans des vues qui ne les emploient pas.

Le premier a été signalé par une passe de QA humaine ; les trois autres par le balayage
que ce test automatise. Le défaut dormait depuis longtemps : `overflow: hidden` clippait
ce qui dépassait, donc la distribution en trop était présente mais INATTEIGNABLE. Poser
un cadre de défilement l'a rendue visible le jour même.

**La liste des éléments est DÉRIVÉE des sources JS**, jamais recopiée : un test qui
citerait des identifiants en dur cesserait de couvrir le premier masquage ajouté après
lui, et ne le dirait pas.

Marqué `e2e` → hors du run par défaut (`pytest -m e2e`).
"""
import re
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

pytestmark = pytest.mark.e2e

RACINE = Path(__file__).resolve().parent.parent
SURFACES = [("/", "viewer.js"), ("/recherche", "recherche.js"),
            ("/corpus", "corpus.js"), ("/exploration", "exploration.js")]

# `$("#id").hidden = …` est la seule forme employée dans ce dépôt ; si une autre
# apparaît, le test le dira en ne trouvant plus rien à vérifier (cf. l'assertion).
MOTIF = re.compile(r'\$\("#([a-z0-9-]+)"\)\.hidden')

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


@pytest.mark.parametrize("chemin, script", SURFACES)
def test_un_element_declare_cache_l_est_vraiment(page, live_server, chemin, script):
    """Pour CHAQUE élément que la surface masque, poser `hidden` doit donner `display:none`.

    On demande au navigateur plutôt qu'à la feuille de style : la question est celle du
    style CALCULÉ, où se joue la spécificité, et une lecture du CSS ne saurait pas dire
    laquelle des deux règles gagne.
    """
    ids = sorted(set(MOTIF.findall((RACINE / "static" / script).read_text(encoding="utf-8"))))
    assert ids, (
        f"aucun `$(\"#…\").hidden` trouvé dans {script} : soit le masquage a changé de "
        "forme, soit ce test ne couvre plus rien — les deux demandent une relecture")

    page.goto(live_server + chemin, wait_until="networkidle")
    coupables = page.evaluate(SONDE, ids)
    assert not coupables, (
        f"Sur {chemin}, ces éléments restent AFFICHÉS malgré `hidden` — une règle de la "
        f"feuille écrase `[hidden] {{ display: none }}` : {', '.join(coupables)}. "
        "Ajouter le garde `<sélecteur>[hidden] { display: none; }` à côté de la règle "
        "fautive, comme les huit qui existent déjà.")
