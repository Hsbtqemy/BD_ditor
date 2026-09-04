"""Tests E2E des deux correctifs d'AUDIT-2 que seul un navigateur peut constater.

`F1` (le thème traverse les onglets) et `D1/D2` (le nuage de tags n'est plus figé) sont
des comportements de NAVIGATEUR : le premier repose sur l'événement `storage`, qui ne se
déclenche que dans les autres onglets ; le second sur la reconstruction du nuage et sur
la survie de la sélection à cette reconstruction. Un test serveur n'en voit rien, et un
test qui lirait le SOURCE pour y chercher `addEventListener("storage")` déclarerait la
règle couverte sans l'être — c'est exactement le défaut que SANTE-1 a mesuré.

Marqués `e2e` → hors du run par défaut (`pytest -m e2e`).
"""
import json

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


# --------------------------------------------------------------------------- #
# C1 — le CÂBLAGE, que le test Node ne peut pas voir
# --------------------------------------------------------------------------- #
# `static/lib/resultats.js` est éprouvé par table de vérité sous Node : la RÈGLE est
# juste. Rien ne dit pour autant que la surface l'emploie — et c'était exactement le
# défaut d'origine, une règle correcte dans un endroit et fausse là où elle sert. Trois
# choses doivent tenir ensemble : la requête demande LIMITE + 1, l'étiquette vient de
# la règle, et l'affichage s'arrête à LIMITE.
#
# Le décor est FABRIQUÉ (201 résultats coûteraient une minute à semer pour de vrai) ;
# `test_la_forme_du_decor_est_celle_du_vrai_serveur` en dessous est le semis qui empêche
# ce test de verdir sur une structure que `/api/recherche` n'a jamais servie.
def _faux_resultats(n):
    return {"q": "x", "count": n,
            "results": [{"region_id": i, "type": "bulle", "x": 0, "y": 0, "w": 10, "h": 10,
                         "ocr_texte": f"texte {i}", "note": None, "tags": [],
                         "album_id": 1, "album_titre": "Décor", "planche_id": 1,
                         "planche_numero": 1, "citation": None}
                        for i in range(1, n + 1)]}


def test_a_exactement_la_limite_l_ecran_n_annonce_pas_de_troncature(page, corpus_tags):
    """Le cas du bug : 200 correspondances, et rien à cacher.

    L'ancienne étiquette (`count >= 200`) promettait ici des résultats qui n'existaient
    pas. Elle est d'autant plus perverse qu'elle ne se trompe QUE sur cette valeur : à
    199 comme à 201, elle disait vrai.
    """
    vues = []
    page.route("**/api/recherche?*", lambda r: (
        vues.append(r.request.url),
        r.fulfill(status=200, content_type="application/json",
                  body=json.dumps(_faux_resultats(200)))))
    page.goto(f"{corpus_tags['base']}/recherche?q=x", wait_until="networkidle")

    expect(page.locator("#result-count")).to_have_text("200 résultats")
    expect(page.locator(".result")).to_have_count(200)
    # La requête demande UN de plus : sans ce décalage, 200 reçus resteraient
    # indiscernables de « 200 reçus, et d'autres derrière ».
    assert vues and "limit=201" in vues[0], vues


def test_au_dela_de_la_limite_l_ecran_le_dit_et_s_arrete_la(page, corpus_tags):
    """Le témoin surnuméraire fait son travail, et ne se montre jamais."""
    page.route("**/api/recherche?*", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(_faux_resultats(201))))
    page.goto(f"{corpus_tags['base']}/recherche?q=x", wait_until="networkidle")

    expect(page.locator("#result-count")).to_have_text("200 résultats (limité)")
    # 200, pas 201 : le résultat qui sert de témoin n'est pas affiché.
    expect(page.locator(".result")).to_have_count(200)


def test_la_forme_du_decor_est_celle_du_vrai_serveur(corpus_tags):
    """Les deux tests ci-dessus fabriquent leur réponse. Sans ce semis, ils pourraient
    verdir sur une structure que `/api/recherche` n'a jamais servie — le mode d'échec
    d'un décor est de rester juste pendant que le vrai change."""
    with corpus_tags["client"]() as c:
        vrai = c.get("/api/recherche", params={"q": "pouvoir", "limit": 5}).json()
    assert set(vrai) == {"q", "count", "results"}, set(vrai)
    assert vrai["results"], "le décor de la fixture devrait rendre au moins un résultat"
    faux = _faux_resultats(1)["results"][0]
    manquants = set(faux) - set(vrai["results"][0])
    assert not manquants, f"le décor invente des champs : {manquants}"


# --------------------------------------------------------------------------- #
# C1, suite — la même règle vivait DEUX fois de plus dans l'Exploration
# --------------------------------------------------------------------------- #
# Le constat d'audit ne citait que la Recherche. Trouvé en balayant la famille après
# coup : `exploration.js` portait le même seuil écrit en dur et le même `>=`, sur la
# distribution et sur la concordance. Le CROISEMENT, lui, ne s'est jamais trompé —
# le serveur y renvoie `x_tronque`/`y_tronque`, un drapeau explicite plutôt qu'une
# déduction depuis le compte. C'est la différence entre savoir et deviner.
def _faux_frequences(n):
    return {"champ": "lemme",
            "results": [{"lemme": f"mot{i}", "pos": "NOUN", "freq": 1} for i in range(1, n + 1)]}


def _faux_concordance(n):
    # Les colonnes sont celles du SELECT de `analyse_concordance` : le KWIC se
    # reconstruit CÔTÉ CLIENT à partir de `ocr_texte` et de `ordre`, il n'y a pas de
    # gauche/pivot/droite servis par le serveur. Le semis plus bas a refusé la
    # première version de ce décor, qui inventait ces trois champs-là.
    return {"count": n,
            "results": [{"region_id": i, "ordre": 0, "texte": "mot", "lemme": "mot",
                         "pos": "NOUN", "morph": None, "provenance": "auto",
                         "type": "bulle", "planche_id": 1, "planche_numero": 1,
                         "album_id": 1, "album_titre": "Décor",
                         "ocr_texte": "un mot ici", "locuteur": None, "citation": None}
                        for i in range(1, n + 1)]}


@pytest.mark.parametrize("recus, attendu", [(200, False), (201, True)])
def test_distribution_ne_ment_pas_a_la_limite_exacte(page, corpus_tags, recus, attendu):
    """Distribution : le total des occurrences se calculait sur TOUTES les lignes reçues.

    Le témoin surnuméraire y aurait été compté, gonflant de un un décompte présenté
    comme exact — d'où le retrait avant tout calcul, et pas seulement avant l'affichage.
    """
    page.route("**/api/analyse/frequences?*", lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(_faux_frequences(recus))))
    page.goto(f"{corpus_tags['base']}/exploration?vue=distribution&champ=lemme",
              wait_until="networkidle")

    info = page.locator("#dist-info")
    expect(info).to_contain_text("200 valeur(s)")
    expect(info).to_contain_text("200 occurrence(s)")   # une par ligne, jamais 201
    if attendu:
        expect(info).to_contain_text("limité aux 200 plus fréquentes")
    else:
        expect(info).not_to_contain_text("limité")


@pytest.mark.parametrize("recus, attendu", [(200, False), (201, True)])
def test_concordance_ne_ment_pas_a_la_limite_exacte(page, corpus_tags, recus, attendu):
    """Concordance : même règle, et les lignes affichées s'arrêtent à la limite."""
    page.route("**/api/analyse/concordance?*", lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(_faux_concordance(recus))))
    page.goto(f"{corpus_tags['base']}/exploration?vue=concordance&lemme=mot",
              wait_until="networkidle")

    info = page.locator("#dist-info")
    expect(info).to_contain_text("200 occurrence(s)")
    if attendu:
        expect(info).to_contain_text("limité à 200")
    else:
        expect(info).not_to_contain_text("limité")


def test_la_forme_des_decors_d_exploration_est_celle_du_vrai_serveur(corpus_tags):
    """Semis des deux tests ci-dessus — mêmes raisons que pour la Recherche."""
    with corpus_tags["client"]() as c:
        freq = c.get("/api/analyse/frequences", params={"champ": "lemme", "limit": 5}).json()
        kwic = c.get("/api/analyse/concordance", params={"lemme": "pouvoir", "limit": 5}).json()
    assert set(_faux_frequences(1)) <= set(freq), set(_faux_frequences(1)) - set(freq)
    assert set(_faux_concordance(1)) <= set(kwic), set(_faux_concordance(1)) - set(kwic)
    if freq.get("results"):
        manquants = set(_faux_frequences(1)["results"][0]) - set(freq["results"][0])
        assert not manquants, f"décor de fréquences : champs inventés {manquants}"
    if kwic.get("results"):
        manquants = set(_faux_concordance(1)["results"][0]) - set(kwic["results"][0])
        assert not manquants, f"décor de concordance : champs inventés {manquants}"
