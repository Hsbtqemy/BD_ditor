"""Tests E2E des deux correctifs d'AUDIT-2 que seul un navigateur peut constater.

`F1` (le thème traverse les onglets) et `D1/D2` (le nuage de tags n'est plus figé) étaient
des comportements de NAVIGATEUR : le premier repose sur l'événement `storage`, qui ne se
déclenche que dans les autres onglets ; le second reposait sur la reconstruction du nuage,
parti avec le basculement d'ANN-7 — à sa place, le lien d'hier filtré par tag, qui doit
dire qu'il ne filtre plus (I7). Un test serveur n'en voit rien, et un
test qui lirait le SOURCE pour y chercher `addEventListener("storage")` déclarerait la
règle couverte sans l'être — c'est exactement le défaut que SANTE-1 a mesuré.

Marqués `e2e` → hors du run par défaut (`pytest -m e2e`).
"""
# UX-10 — ce que cet audit COUVRE, et ce qu'il écarte avec sa raison.
#
# Cet audit suit deux CORRECTIFS nommés (AUDIT-2 F1 et D1/D2), pas un inventaire d'écrans :
# le thème qui traverse les onglets, et le nuage de tags qui se reconstruisait sans perdre
# sa sélection (parti avec le basculement d'ANN-7). Il va donc là où ces comportements
# vivent, et nulle part ailleurs.
SURFACES_AUDITEES = ("/recherche", "/corpus", "/exploration")
SURFACES_HORS_PERIMETRE = {
    "/annotation": (
        "les deux correctifs d'AUDIT-2 portent sur la Recherche, la Bibliothèque "
        "et l'Exploration ; la page Annotation n'existait pas"),
    "/": "la Visionneuse ne porte pas de nuage de tags ; l'onglet qui reçoit l'événement "
         "`storage` du correctif F1 est ouvert sur la Recherche et la Bibliothèque.",
    "/administration": "ni nuage de tags, ni second onglet dans le scénario du thème : les "
                       "deux correctifs d'AUDIT-2 n'ont rien à y observer. Le thème y est "
                       "appliqué comme partout par `theme.js`, et c'est `test_e2e_a11y` qui "
                       "l'éprouve sur les deux thèmes.",
}


import json

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e


@pytest.fixture
def corpus_tags(live_server):
    """Un album, une planche, une région transcrite."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "AUDIT-2"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        rid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 10, "y": 10, "w": 120, "h": 80}).json()["id"]
        c.put(f"/api/regions/{rid}", json={"ocr_texte": "POUVOIR ABSOLU"})
        return {"base": live_server, "album": aid, "planche": pid, "region": rid,
                "client": lambda: httpx.Client(base_url=live_server, trust_env=False,
                                               timeout=30, headers=ECRITURE)}
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

@pytest.mark.parametrize("surface,zone", [("/recherche", "#result-count"),
                                          ("/exploration", "#dist-info")])
def test_un_lien_d_hier_filtre_par_tag_dit_qu_il_ne_filtre_plus(page, corpus_tags, surface,
                                                                 zone):
    """ANN-7, I7 — un lien d'hier (`?tags=…`, un « drill » enregistré, un favori) : la page
    ne rend pas le corpus entier en ayant l'air filtrée. Elle envoie le paramètre au
    serveur, qui le refuse en le disant, et l'écran dit ce refus. Le geste suivant s'en
    passe : changer un filtre relance une recherche ordinaire."""
    page.goto(f"{corpus_tags['base']}{surface}?tags=dialogue", wait_until="networkidle")
    expect(page.locator(zone)).to_contain_text("n'existent plus")
    expect(page.locator(zone)).to_contain_text("« tags »")
    page.select_option("#f-album", str(corpus_tags["album"]))
    expect(page.locator(zone)).not_to_contain_text("n'existent plus")
    assert "tags=" not in page.url


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
    # `sans_terme` est arrivé avec C2, et le semis strict ci-dessous l'a réclamé dès
    # la première course : c'est la contrepartie de l'égalité exacte, et elle vaut
    # mieux qu'une inclusion qui laisserait le décor vieillir en silence.
    return {"q": "x", "count": n, "sans_terme": False,
            "results": [{"region_id": i, "type": "bulle", "x": 0, "y": 0, "w": 10, "h": 10,
                         "ocr_texte": f"texte {i}", "note": None,
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
    # Les clés attendues sont DÉRIVÉES du décor, jamais recopiées : une liste écrite en
    # dur ici serait un troisième endroit à tenir à jour, et c'est elle qui a divergé la
    # première fois — `sans_terme` était dans la réponse et dans le décor, mais pas dans
    # la liste.
    assert set(vrai) == set(_faux_resultats(1)), (set(vrai), set(_faux_resultats(1)))
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
    expect(info).to_contain_text("200 valeurs de")
    expect(info).to_contain_text("200 occurrences")   # une par ligne, jamais 201
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
    expect(info).to_contain_text("200 occurrences")
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


# --------------------------------------------------------------------------- #
# C2 — l'écran distingue « rien trouvé » de « rien cherché »
# --------------------------------------------------------------------------- #
def test_une_requete_de_ponctuation_seule_explique_son_zero(page, corpus_tags):
    """Les deux messages doivent DIFFÉRER, et c'est tout le chantier.

    « Aucun résultat » est vrai dans les deux cas et n'aide que dans l'un : sur une
    requête de ponctuation seule, il laisse croire que le corpus est muet alors que
    c'est la saisie qui n'a rien demandé. Le serveur tranche — la règle appartient au
    tokenizer — et l'écran se contente de le dire.
    """
    base = corpus_tags["base"]

    page.goto(f"{base}/recherche?q=%3F%3F%3F", wait_until="networkidle")
    expect(page.locator(".search-hint")).to_contain_text("aucun terme cherchable")
    expect(page.locator("#result-count")).to_have_text("0 résultat")

    # Une requête valide qui ne trouve rien garde le message d'origine : si les deux
    # phrases se confondaient à nouveau, ce test verdirait sans rien distinguer.
    page.goto(f"{base}/recherche?q=zzzintrouvable", wait_until="networkidle")
    hint = page.locator(".search-hint")
    expect(hint).to_contain_text("Aucun résultat")
    expect(hint).not_to_contain_text("aucun terme cherchable")
