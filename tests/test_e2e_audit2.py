"""Tests E2E des deux correctifs d'AUDIT-2 que seul un navigateur peut constater.

`F1` (le thème traverse les onglets) et `D1/D2` (le nuage de tags n'est plus figé) sont
des comportements de NAVIGATEUR : le premier repose sur l'événement `storage`, qui ne se
déclenche que dans les autres onglets ; le second sur la reconstruction du nuage et sur
la survie de la sélection à cette reconstruction. Un test serveur n'en voit rien, et un
test qui lirait le SOURCE pour y chercher `addEventListener("storage")` déclarerait la
règle couverte sans l'être — c'est exactement le défaut que SANTE-1 a mesuré.

Marqués `e2e` → hors du run par défaut (`pytest -m e2e`).
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ADMIN, make_png  # noqa: E402

pytestmark = pytest.mark.e2e


@pytest.fixture
def corpus_tags(live_server):
    """Un album, une planche, une région ANNOTÉE — un tag n'entre dans le nuage que
    s'il a au moins une occurrence (`loadTags` filtre sur `frequence > 0`)."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ADMIN)
    try:
        aid = c.post("/api/albums", json={"titre": "AUDIT-2"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        rid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 10, "y": 10, "w": 120, "h": 80}).json()["id"]
        c.put(f"/api/regions/{rid}", json={"ocr_texte": "POUVOIR ABSOLU"})
        c.put(f"/api/regions/{rid}/annotation",
              json={"note": "", "tags": ["dialogue"]})
        return {"base": live_server, "album": aid, "planche": pid, "region": rid,
                "client": lambda: httpx.Client(base_url=live_server, trust_env=False,
                                               timeout=30, headers=ADMIN)}
    finally:
        c.close()


def test_le_theme_traverse_les_onglets_deja_ouverts(context, corpus_tags):
    """F1 — deux onglets ouverts côte à côte affichaient deux thèmes différents.

    `theme.js` mémorise le choix dans `localStorage` mais n'écoutait pas l'événement
    `storage` : l'onglet qui n'avait pas cliqué gardait l'ancien thème jusqu'à son
    rechargement. Les deux pages partagent ici le même contexte, donc le même
    `localStorage` — exactement la situation de deux onglets d'un même navigateur.
    """
    a = context.new_page()
    b = context.new_page()
    a.goto(f"{corpus_tags['base']}/recherche", wait_until="networkidle")
    b.goto(f"{corpus_tags['base']}/corpus", wait_until="networkidle")

    # On écrit la clé depuis l'AUTRE onglet, ce qui EST le contrat de `storage` : la
    # spécification dit que l'événement se déclenche chez les autres documents de la
    # même origine, jamais chez celui qui écrit. Piloter le menu « Aa » aurait été plus
    # réaliste, mais il teste alors deux choses à la fois et échoue pour la mauvaise.
    #
    # Ce que ce test NE couvre PAS, et qui ne relève pas de F1 : que le bouton du menu
    # mémorise bien son choix. C'était vrai avant ce correctif et ça l'est resté.
    def poser(p, valeur):
        p.evaluate("(v) => localStorage.setItem('bd-theme', v)", valeur)

    poser(a, "light")
    expect(b.locator("html")).to_have_attribute("data-theme", "light")

    poser(a, "dark")
    expect(b.locator("html")).to_have_attribute("data-theme", "dark")

    # Et dans l'autre sens : l'écoute n'est pas à sens unique.
    poser(b, "light")
    expect(a.locator("html")).to_have_attribute("data-theme", "light")

    # Un `clear()` arrive avec une clé NULLE — « tout a changé » — et doit être relu,
    # sinon l'onglet garderait un thème dont plus rien ne porte la trace. Sans choix
    # mémorisé, `theme.js` retombe sur la préférence système : on la FIXE, faute de quoi
    # l'attendu dépendrait de la machine, et le test serait vert sans rien observer si
    # elle se trouvait déjà sur la valeur d'arrivée.
    a.emulate_media(color_scheme="light")
    poser(b, "dark")
    expect(a.locator("html")).to_have_attribute("data-theme", "dark")
    b.evaluate("() => localStorage.clear()")
    expect(a.locator("html")).to_have_attribute("data-theme", "light")

def test_le_nuage_de_tags_reflete_un_tag_cree_depuis(page, corpus_tags):
    """D1/D2 — le nuage était bâti une fois, au démarrage, et jamais relu.

    Les tags naissent dans la VISIONNEUSE, souvent dans un autre onglet : celui de la
    Recherche restait figé sur l'état du chargement. Le revoir se fait en revenant sur
    l'onglet, ce que `visibilitychange` signale — et c'est le moment exact où il a pu
    changer.
    """
    page.goto(f"{corpus_tags['base']}/recherche", wait_until="networkidle")
    expect(page.locator(".cloud-tag", has_text="dialogue")).to_have_count(1)
    expect(page.locator(".cloud-tag", has_text="onomatopée")).to_have_count(0)

    # Un tag naît ailleurs — ici par l'API, ce que fait la Visionneuse d'un autre onglet.
    with corpus_tags["client"]() as c:
        c.put(f"/api/regions/{corpus_tags['region']}/annotation",
              json={"note": "", "tags": ["dialogue", "onomatopée"]})

    # Tant qu'on ne revient pas sur l'onglet, rien ne bouge : la page ne sonde pas.
    expect(page.locator(".cloud-tag", has_text="onomatopée")).to_have_count(0)

    # Le retour sur l'onglet est le signal. En headless, `bring_to_front` ne rend pas
    # l'autre page CACHÉE — `document.hidden` y reste faux et l'événement ne part
    # jamais : mesuré, la première version de ce test échouait pour cette raison et non
    # pour un défaut du correctif. On émet donc l'événement, ce qui teste le HANDLER et
    # laisse au navigateur ce qui est son travail. Limite assumée : brancher l'écoute
    # sur `focus` plutôt que sur `visibilitychange` ferait rougir ce test, mais le
    # brancher sur les DEUX le laisserait vert sans qu'on l'ait voulu.
    page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
    expect(page.locator(".cloud-tag", has_text="onomatopée")).to_have_count(1)


def test_un_tag_deep_linke_reste_surligne_dans_le_nuage(page, corpus_tags):
    """D1/D2, l'autre moitié : la sélection SURVIT à la reconstruction du nuage.

    `loadTags()` n'est pas attendu au démarrage. Arrivé après `restoreFromUrl()`, il
    reconstruisait les boutons sans leur marque `.active` : le filtre restait actif et
    invisible, et le tag deep-linké n'apparaissait surligné qu'une fois sur deux, selon
    laquelle des deux requêtes répondait en premier. Course latente, jamais signalée.
    """
    page.goto(f"{corpus_tags['base']}/recherche?tags=dialogue", wait_until="networkidle")

    # La puce du filtre actif ET le bouton du nuage doivent tous deux le montrer :
    # c'est leur DÉSACCORD qui était le défaut, pas l'absence de l'un des deux.
    expect(page.locator(".active-tag", has_text="dialogue")).to_have_count(1)
    expect(page.locator(".cloud-tag.active", has_text="dialogue")).to_have_count(1)
