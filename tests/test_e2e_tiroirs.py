"""Les tiroirs de la Visionneuse : ce que le piège à focus doit tenir (UX-7).

Sous le seuil, l'arbre de structure et le panneau latéral s'escamotent derrière un voile.
Le voile bloque le CLIC sur le reste de l'application : l'écran se LIT donc comme modal.
Sans piège, la tabulation le traversait quand même — mesuré le 2026-09-05 à 320 px, le
focus sortait au quatrième Tab et visitait 19 cibles sur 25 hors du tiroir, dont plusieurs
SOUS le voile, c'est-à-dire des commandes qu'aucun doigt ne pouvait atteindre. Deux publics
recevaient deux applications, et axe ne dit rien de ce cas : rien n'est mal étiqueté, rien
n'est invisible ; c'est le PARCOURS qui ment.

Ce fichier ne dépend PAS d'axe, contrairement à `test_e2e_a11y.py` qui se skippe entier
quand le fichier vendu manque. Faire dépendre le piège à focus de la présence d'axe-core
lierait deux conditions sans rapport.

Le cas 3 est le moins évident et le plus important : le seuil appartient au CSS, et le JS
ne le connaît pas. Ouvrir un tiroir à 320 px puis élargir la fenêtre rend le panneau à sa
colonne — le piège doit alors se DÉSARMER seul, sans qu'aucun nombre soit recopié dans le
JS. Il le fait en demandant au DOM si la bascule est affichée.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from conftest import ADMIN, make_png            # noqa: E402

pytestmark = pytest.mark.e2e

# Sous les deux seuils (899 pour le panneau, 1079 pour l'arbre) : les deux tiroirs
# existent. La valeur elle-même n'est pas relue du CSS à dessein — le test doit ÉCHOUER si
# quelqu'un remonte les seuils sans y penser, pas s'adapter en silence.
ETROIT = {"width": 320, "height": 800}
LARGE = {"width": 1400, "height": 900}

OU_EST_LE_FOCUS = """(sel) => {
  const a = document.activeElement;
  if (!a || a === document.body) return {quoi: '(rien)', dedans: false};
  const id = a.id || '';
  return {quoi: id ? '#' + id : a.tagName,
          dedans: !!a.closest(sel) || id.startsWith('btn-tiroir')};
}"""


@pytest.fixture
def visionneuse(live_server, page):
    """Un album et une planche, pour que l'arbre de structure ait de quoi se peupler."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ADMIN)
    try:
        aid = c.post("/api/albums", json={"titre": "Tiroirs", "auteur": "X"}).json()["id"]
        c.post(f"/api/albums/{aid}/import",
               files={"file": ("p.png", make_png(), "image/png")})
    finally:
        c.close()
    page.set_viewport_size(ETROIT)
    page.goto(live_server + "/", wait_until="networkidle")
    page.wait_for_timeout(400)
    return page


def _sorties(page, sel, n, shift=False):
    """Les cibles atteintes hors du tiroir et hors de sa bascule, en n tabulations."""
    dehors = []
    for _ in range(n):
        r = page.evaluate(OU_EST_LE_FOCUS, sel)
        if not r["dedans"]:
            dehors.append(r["quoi"])
        page.keyboard.press("Shift+Tab" if shift else "Tab")
        page.wait_for_timeout(30)
    return dehors


@pytest.mark.parametrize("sens", ["Tab", "Shift+Tab"])
@pytest.mark.parametrize("bascule,panneau", [("#btn-tiroir-nav", "#sidebar"),
                                             ("#btn-tiroir-panneau", "#panel")])
def test_le_focus_ne_sort_pas_d_un_tiroir_ouvert(visionneuse, bascule, panneau, sens):
    page = visionneuse
    page.click(bascule)
    page.wait_for_timeout(300)
    dehors = _sorties(page, panneau, 20, shift=(sens == "Shift+Tab"))
    assert not dehors, (
        f"{sens} sort de {panneau} : {dehors[:6]}. Le voile bloque le clic sur ces "
        "cibles — elles seraient focalisables sans être actionnables au doigt")


@pytest.mark.parametrize("bascule,panneau", [("#btn-tiroir-nav", "#sidebar"),
                                             ("#btn-tiroir-panneau", "#panel")])
def test_le_cycle_boucle_dans_les_deux_sens(visionneuse, bascule, panneau):
    """La bascule EST la sortie à la souris : l'exclure du cycle enfermerait sans porte.

    Il a fallu TROIS formulations avant d'en trouver une qui échoue quand elle doit, et
    les deux premières illustrent le même piège — une case cochable pour une raison qui
    n'est pas la sienne.

    « La bascule apparaît dans les douze premières tabulations » passait le piège désarmé :
    la tabulation native l'atteint de toute façon. « Depuis le dernier élément du tiroir,
    Tab revient sur la bascule » aussi, et pour une raison qu'il fallait aller lire dans le
    gabarit : `#btn-tiroir-nav` SUIT immédiatement `</aside>`, si bien que les deux sens du
    cycle sont nativement corrects — pour CE tiroir-là.

    D'où le paramétrage. Le tiroir de PANNEAU n'a pas cette chance : sa bascule est le
    dernier enfant de `#toolbar`, précédée du fil d'Ariane et des commandes de zoom, et
    `#panel` vit après `#stage`. C'est lui qui fait tomber le test quand le piège est
    désarmé — vérifié dans les deux états.
    """
    page = visionneuse
    page.click(bascule)
    page.wait_for_timeout(300)
    dernier = page.evaluate("""([sel, cible]) => {
      const v = [...document.querySelectorAll(cible + ' ' + sel)]
                  .filter(e => !e.disabled && e.offsetParent !== null);
      return v.length ? (v[v.length - 1].id || v[v.length - 1].tagName) : null;
    }""", ['button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
           panneau])
    assert dernier, f"aucun élément focalisable dans {panneau} : le décor ne tient plus"

    page.evaluate("(b) => document.querySelector(b).focus()", bascule)
    page.keyboard.press("Shift+Tab")
    page.wait_for_timeout(60)
    arriere = page.evaluate("() => document.activeElement.id || document.activeElement.tagName")
    assert arriere == dernier, (
        f"Shift+Tab depuis {bascule} est allé sur « {arriere} » au lieu de « {dernier} », "
        f"le dernier élément de {panneau} — le cycle fuit par l'arrière")

    page.keyboard.press("Tab")
    page.wait_for_timeout(60)
    avant = page.evaluate("() => '#' + document.activeElement.id")
    assert avant == bascule, (
        f"et Tab depuis « {dernier} » est reparti sur « {avant} » : le cycle fuit aussi "
        "par l'avant")


def test_echap_referme_et_rend_le_focus_a_la_bascule(visionneuse):
    page = visionneuse
    page.click("#btn-tiroir-nav")
    page.wait_for_timeout(300)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    etat = page.evaluate("""() => ({
      ouvert: document.querySelector('#body').classList.contains('nav-ouverte'),
      focus: document.activeElement.id,
      annonce: document.querySelector('#btn-tiroir-nav').getAttribute('aria-expanded'),
    })""")
    assert not etat["ouvert"], "Échap n'a pas refermé le tiroir"
    assert etat["focus"] == "btn-tiroir-nav", (
        f"le focus est resté sur « {etat['focus']} » — dans un tiroir refermé il serait "
        "invisible ET inatteignable, l'état le plus déroutant qu'un clavier puisse subir")
    assert etat["annonce"] == "false", "`aria-expanded` ment sur l'état du tiroir"


def test_le_piege_se_desarme_quand_le_panneau_n_est_plus_un_tiroir(visionneuse):
    """Le seuil appartient au CSS, et le JS n'en connaît aucun nombre.

    Ouvrir à 320 px puis élargir : le panneau redevient une colonne ordinaire, et y
    enfermer le focus serait pire que de ne rien faire. Le désarmement se lit dans le DOM
    — la bascule est `display: none` au-dessus du seuil — plutôt que dans une largeur
    recopiée, qui se serait désaccordée au premier ajustement.
    """
    page = visionneuse
    page.click("#btn-tiroir-panneau")
    page.wait_for_timeout(300)
    page.set_viewport_size(LARGE)
    page.wait_for_timeout(400)
    assert page.evaluate(
        "() => getComputedStyle(document.querySelector('#btn-tiroir-panneau')).display"
    ) == "none", "prémisse fausse : la bascule est encore affichée à 1400 px"
    dehors = _sorties(page, "#panel", 12)
    assert dehors, (
        "le focus reste enfermé dans un panneau qui n'est plus un tiroir : le piège n'a "
        "pas vu que la fenêtre s'était élargie")
