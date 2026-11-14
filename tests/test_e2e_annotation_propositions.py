"""Le champ « personnage » de la page Annotation : ce qu'Entrée décide (ANN-6, ANN-8).

Né dans le panneau d'annotation de l'Atelier, sous le nom `test_e2e_atelier_propositions.py`.
Le basculement d'ANN-7 a retiré ce panneau (le mode Annotation n'est plus), et avec lui les
champs « dimension : valeur » de la Situation et du profil, que ce fichier éprouvait aussi :
le vocabulaire qu'ils posaient devient des grilles. Reste le champ « personnage » — le
locuteur d'une zone de texte, l'identité d'une boîte personnage —, qui vit dans
`static/lib/champ-personnage.js` et que la page Annotation monte dans son Contexte. Les
gardes de ce fichier y sont rejouées telles quelles : le module est le même, l'hôte a
changé, et c'est l'hôte que l'on mesure ici (la zone du geste, la valeur vue, la puce).

La liste vient du registre, qui dépend de la saisie CÔTÉ SERVEUR (`?q=`), 200 ms après la
dernière frappe, puis le temps d'une lecture. Entrée y cherchait l'homonyme exact telle
qu'elle était, et créait faute de l'y trouver : « Zed » existant, tapé vite, devenait un
SECOND « Zed » (reproduit le 2026-10-12).

**La course est rendue DÉTERMINISTE, elle n'est pas rejouée au chronomètre.** Aucun test
ne compte sur une vitesse de frappe : la lecture qui ferait arriver la liste est TENUE en
vol (`page.route`), et relâchée quand le test le décide. « Vite » veut donc dire ici
« avant que la réponse n'arrive », ce qui est exactement la condition du défaut.

**Ce qui est mesuré est la requête PARTIE** — méthode, chemin, corps —, pas seulement
l'état final : un écran qui afficherait la bonne puce sans rien envoyer, ou qui enverrait
trois requêtes là où une suffit, rendrait le même état final. Et « rien n'est parti » ne
s'affirme qu'après un TÉMOIN que l'écran a bien traité le geste : sans lui, l'assertion
passerait sur une page qui n'a encore rien fait.
"""
import json
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source. Le champ « personnage » ne
# vit plus que dans le Contexte de la page Annotation.
SURFACES_AUDITEES = ("/annotation",)
SURFACES_HORS_PERIMETRE = {
    "/": ("l'Atelier n'a plus de champ à propositions depuis le basculement d'ANN-7 : son "
          "mode Annotation, qui portait le locuteur et l'identité d'une boîte, est parti"),
    "/recherche": "aucun champ à propositions qui écrive : la Recherche filtre, elle n'attribue rien",
    "/corpus": "aucun champ de personnage : la Bibliothèque range des albums",
    "/exploration": "le vocabulaire s'y édite dans le Lexique, par des formulaires sans liste de propositions",
    "/administration": "aucun Contexte : rien n'y porte sur une région d'une planche",
}


# --------------------------------------------------------------------------- #
# Le décor et les gestes
# --------------------------------------------------------------------------- #
@pytest.fixture
def atelier(live_server):
    """Une planche, une case, et sous elle une bulle, un cartouche et une boîte
    personnage. « Tintin » est au registre : il parle dans la bulle et il est montré dans
    la boîte."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "E2E propositions"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(800, 1000), "image/png")}).json()["id"]

        def region(type_zone, x, y, parent=None):
            corps = {"type": type_zone, "x": x, "y": y, "w": 700, "h": 900}
            if parent is not None:
                corps.update(parent_id=parent, w=280, h=180)
            rep = c.post(f"/api/planches/{pid}/regions", json=corps)
            assert rep.status_code in (200, 201), rep.text
            return rep.json()["id"]

        case = region("case", 40, 40)
        decor = {"base": live_server, "album": aid, "planche": pid, "case": case,
                 "bulle": region("bulle", 60, 60, case),
                 "cartouche": region("cartouche", 60, 300, case),
                 "personnage": region("personnage", 400, 300, case),
                 "tintin": c.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]}
        for lien in (f"/api/regions/{decor['bulle']}/locuteur",
                     f"/api/regions/{decor['personnage']}/personnage"):
            rep = c.put(lien, json={"personnage_id": decor["tintin"]})
            assert rep.status_code == 200, rep.text
    finally:
        c.close()
    return decor


def _api(decor, ecriture=False):
    return httpx.Client(base_url=decor["base"], trust_env=False, timeout=30,
                        headers=ECRITURE if ecriture else {})


def _ouvrir(page, decor, type_zone):
    """Ouvre la page Annotation sur la région du type demandé."""
    page.goto(f"{decor['base']}/annotation?album={decor['album']}&planche={decor['planche']}"
              f"&region={decor[type_zone]}", wait_until="networkidle")
    _sur_la_zone(page, decor[type_zone])


def _sur_la_zone(page, rid):
    """La zone est bien celle qu'on croit : son bouton de la rangée des zones est pressé, et
    son Contexte a fini de se lire (la note, désactivée le temps de la lecture, se rend)."""
    expect(page.locator(f'#an-zones .an-zone-btn[data-zone="{rid}"]')).to_have_attribute(
        "aria-pressed", "true", timeout=15000)
    expect(page.locator("#an-ctx-note")).to_be_visible(timeout=15000)
    page.wait_for_function("() => !document.querySelector('#an-note').disabled", timeout=15000)


def _zone(page, rid):
    """Choisir une autre zone de la case, par sa rangée (le chemin au clavier)."""
    page.locator(f'#an-zones .an-zone-btn[data-zone="{rid}"]').click()
    _sur_la_zone(page, rid)


def _est(methode, chemin):
    """Prédicat de requête OU de réponse : cette méthode, sur ce chemin exact."""
    def predicat(objet):
        requete = getattr(objet, "request", objet)
        return requete.method == methode and requete.url.endswith(chemin)
    return predicat


def _ecritures(page):
    """Le journal de ce qui PART et qui écrit : « MÉTHODE chemin corps », dans l'ordre."""
    parties = []

    def noter(requete):
        if requete.method != "GET" and "/api/" in requete.url:
            chemin = re.sub(r"^https?://[^/]+", "", requete.url)
            parties.append(f"{requete.method} {chemin} {requete.post_data or ''}".strip())
    page.on("request", noter)
    return parties


class Retenue:
    """Tient en vol les requêtes d'un motif, jusqu'à ce que le test les relâche.

    C'est ce qui rend la course déterministe : tant que la lecture est tenue, la liste
    que l'écran a sous la main est celle d'AVANT, quelle que soit la vitesse du poste.
    """

    def __init__(self, page, motif, methode="GET"):
        self.page, self.tenues, self.ouverte = page, [], False

        def tenir(route):
            if not self.ouverte and route.request.method == methode:
                self.tenues.append(route)
            else:
                route.continue_()
        page.route(motif, tenir)

    def attendre(self, n=1):
        """Au moins `n` requêtes tenues. Les gestionnaires de route ne tournent que
        PENDANT un appel à la page : on patiente par elle."""
        for _ in range(150):
            if len(self.tenues) >= n:
                return self.tenues
            self.page.wait_for_timeout(100)
        raise AssertionError(
            f"{len(self.tenues)} requête(s) tenue(s), {n} attendue(s) : "
            f"{[r.request.url for r in self.tenues]}")

    def relacher(self):
        """Laisse tout passer, ce qui est tenu comme ce qui viendra."""
        self.ouverte = True
        for route in self.tenues:
            route.continue_()
        self.tenues = []


def _repondre(page, route, corps):
    """Répond SOI-MÊME à une requête tenue, et attend que la page ait reçu la réponse."""
    with page.expect_response(lambda r: r.request is route.request):
        route.fulfill(status=200, content_type="application/json", body=json.dumps(corps))


# --------------------------------------------------------------------------- #
# Le champ de personnage — Entrée prend l'homonyme exact avant de créer
# --------------------------------------------------------------------------- #
# Le locuteur d'une zone et l'identité d'une boîte se choisissent dans le registre, dont la liste dépend de la saisie CÔTÉ SERVEUR (`?q=`).
# Entrée y cherchait l'homonyme exact telle qu'elle était, et créait faute de l'y trouver :
# « Zed » existant, tapé vite, devenait un SECOND « Zed », aussitôt attribué (reproduit le
# 2026-10-12, quatorze personnages au registre). La série distingue des homonymes
# légitimes ; depuis ANN-8, le serveur retrouve un homonyme qu'on voit au lieu d'en créer un
# second (même nom sans casse ni accents, même série), mais les tests ci-dessous mesurent ce
# que l'ÉCRAN décide : ils exigent qu'aucune création ne parte.
#
# La lecture du registre est tenue en vol (`Retenue`). Là où il faut qu'Entrée précède
# jusqu'à la lecture différée elle-même, la frappe et Entrée sont émises dans la même
# tâche du navigateur (`_taper_et_valider_d_un_trait`) : les 200 ms ne peuvent pas
# s'écouler entre les deux.

# Les deux montages du champ de personnage.
CHAMPS_PERSONNAGE = {
    "locuteur": {"zone": "bulle", "champ": "#an-loc-input", "liste": "#an-loc-liste",
                 "lien": "locuteur", "puce": "#an-loc-nom"},
    "boite-personnage": {"zone": "personnage", "champ": "#an-perso-input", "liste": "#an-perso-liste",
                         "lien": "personnage", "puce": "#an-perso-nom"},
}

LECTURE_REGISTRE = re.compile(r"/api/personnages\?q=")


def _registre(decor):
    with _api(decor) as c:
        return c.get("/api/personnages").json()


def _lie(decor, rid, lien):
    with _api(decor) as c:
        return c.get(f"/api/regions/{rid}/{lien}").json()[lien]


_D_UN_TRAIT = """([selecteur, texte]) => {
  const champ = document.querySelector(selecteur);
  champ.value = texte;
  champ.dispatchEvent(new Event('input', { bubbles: true }));
  champ.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
}"""


def _taper_et_valider_d_un_trait(page, selecteur, texte):
    """La frappe et Entrée dans la MÊME tâche du navigateur.

    Le champ arme une lecture 200 ms après la frappe. Pour éprouver ce qu'Entrée décide
    AVANT qu'elle parte, il ne suffit pas de taper vite : rien ne garantit qu'un poste
    chargé enchaîne deux appels en moins de 200 ms. Ici les deux évènements que le champ
    écoute (`input`, puis `keydown`) sont émis l'un derrière l'autre, sans rendre la main.
    Le champ doit avoir le focus : on y a cliqué avant.
    """
    page.evaluate(_D_UN_TRAIT, [selecteur, texte])


def _peupler(decor, *noms):
    """Ajoute des personnages au registre ; rend {nom: id}."""
    with _api(decor, ecriture=True) as c:
        return {n: c.post("/api/personnages", json={"nom": n}).json()["id"] for n in noms}


def _creations(parties):
    return [p for p in parties if p.startswith("POST /api/personnages ")]


FIGURANTS = [f"Figurant {k:02d}" for k in range(12)]


@pytest.mark.parametrize("champ_de", list(CHAMPS_PERSONNAGE))
@pytest.mark.parametrize("moment", ["lecture en vol", "avant la lecture"])
def test_un_nom_existant_tape_avant_la_liste_prend_l_homonyme(page, atelier, champ_de, moment):
    """Quatorze personnages au registre, « Zed » le dernier : la liste du champ vide en
    montre dix, pas lui. On tape « Zed » et Entrée avant que SA liste ne revienne : c'est
    le « Zed » existant qui est pris. Avant, un SECOND « Zed » était créé, puis attribué.

    Deux moments, parce que l'écran ne fait pas la même chose : la lecture différée déjà
    partie, Entrée attend CELLE-LÀ (aucune lecture de plus) ; Entrée avant elle, l'écran
    relit lui-même le registre pour ce nom.
    """
    c = CHAMPS_PERSONNAGE[champ_de]
    zed = _peupler(atelier, *FIGURANTS, "Zed")["Zed"]
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    expect(liste).to_have_count(10, timeout=15000)   # la liste du champ vide : dix, sans « Zed »
    expect(liste.filter(has_text="Zed")).to_have_count(0)

    lectures = Retenue(page, LECTURE_REGISTRE)
    if moment == "lecture en vol":
        champ.press_sequentially("Zed", delay=0)
        lectures.attendre(1)                         # la lecture différée de « Zed », tenue
        champ.press("Enter")
    else:
        _taper_et_valider_d_un_trait(page, c["champ"], "Zed")
        lectures.attendre(1)                         # la relecture d'Entrée, tenue
    page.wait_for_timeout(500)
    # UNE lecture pour ce nom, pas deux. (Entrée pressée avant la lecture différée, celle-ci
    # ne part plus du tout depuis ANN-8 : Entrée décide sur sa propre lecture, et la liste
    # différée aurait rouvert par-dessus celle des homonymes.)
    pour_ce_nom = [r.request.url for r in lectures.tenues if r.request.url.endswith("?q=Zed")]
    assert len(pour_ce_nom) == 1, [r.request.url for r in lectures.tenues]
    assert parties == [], f"l'écran a écrit sans attendre de savoir : {parties}"
    expect(champ).to_have_value("")                  # une seconde Entrée ne repartirait pas

    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        lectures.relacher()
    assert reponse.value.status == 200, reponse.value.text()
    # CONC-4 : le corps porte aussi `personnage_vu` (ce que l'écran voyait) ; ces tests
    # éprouvent QUEL personnage part, la valeur vue a ses gardes (`test_e2e_conflit_a_deux`).
    assert envoi.value.post_data_json["personnage_id"] == zed
    expect(page.locator(c["puce"])).to_contain_text("Zed", timeout=15000)
    assert _creations(parties) == [], f"un homonyme a été créé : {parties}"
    assert [p["nom"] for p in _registre(atelier)].count("Zed") == 1
    assert _lie(atelier, rid, c["lien"])["id"] == zed
    if moment == "lecture en vol":
        # La liste de « Zed », revenue après le geste, ne se rouvre pas sur un champ vidé.
        page.wait_for_timeout(300)
        expect(page.locator(c["liste"])).to_be_hidden()


@pytest.mark.parametrize("champ_de", list(CHAMPS_PERSONNAGE))
def test_un_nom_tape_sans_ses_accents_prend_l_homonyme_accentue(page, atelier, champ_de):
    """ANN-8 (Hugo, 2026-10-21) — l'accent ne distingue pas deux personnages. « Étienne » au
    registre ; on tape « etienne » LENTEMENT : la liste le montre, sans « Créer », et Entrée
    sans rien surligner le prend. Avant, Entrée proposait « Créer « etienne » », un
    quasi-doublon : les homonymes se comparaient en minuscules, AVEC les accents."""
    c = CHAMPS_PERSONNAGE[champ_de]
    etienne = _peupler(atelier, "Étienne")["Étienne"]
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    champ.press_sequentially("etienne", delay=20)
    expect(liste.filter(has_text="Étienne")).to_have_count(1, timeout=15000)
    expect(liste.filter(has_text="Créer")).to_have_count(0)
    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    assert envoi.value.post_data_json["personnage_id"] == etienne
    expect(page.locator(c["puce"])).to_contain_text("Étienne", timeout=15000)
    assert _creations(parties) == [], f"un quasi-doublon a été créé : {parties}"
    assert [p["nom"] for p in _registre(atelier)].count("Étienne") == 1
    assert "etienne" not in [p["nom"] for p in _registre(atelier)]


def test_l_homonyme_au_dela_des_dix_propositions_est_pris_meme_tape_lentement(page, atelier):
    """Douze personnages dont le nom contient « zed » : la liste en montre dix, et « Zed »,
    le dernier dans l'ordre du registre, n'en est pas — ni lui, ni « Créer », puisqu'il
    existe. Entrée, tapé LENTEMENT, le prend. Avant, l'homonyme se cherchait dans les dix
    propositions affichées : Entrée en créait un second."""
    c = CHAMPS_PERSONNAGE["locuteur"]
    ids = _peupler(atelier, *[f"Azed {k:02d}" for k in range(11)], "Zed")
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=zed")):
        champ.press_sequentially("zed", delay=20)
    expect(liste).to_have_count(10, timeout=15000)
    expect(liste.filter(has_text=re.compile(r"^Zed$"))).to_have_count(0)
    expect(liste.filter(has_text="Créer")).to_have_count(0)

    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    assert envoi.value.post_data_json["personnage_id"] == ids["Zed"]
    assert _creations(parties) == [], parties
    assert len(_registre(atelier)) == 13             # Tintin, onze « Azed », « Zed »


def test_une_lecture_du_registre_en_echec_ne_cree_personne(page, atelier):
    """Le registre ne répond pas pour ce nom : l'écran ne sait pas s'il existe. Il ne
    propose pas de le créer, et Entrée ne le crée pas — la saisie revient, avec un message.
    Avant, une lecture en échec valait un registre vide : Entrée créait."""
    c = CHAMPS_PERSONNAGE["locuteur"]
    _peupler(atelier, "Zed")
    _ouvrir(page, atelier, c["zone"])
    champ = page.locator(c["champ"])
    parties = _ecritures(page)

    champ.click()
    expect(page.locator(f"{c['liste']} div")).to_have_count(2, timeout=15000)   # Tintin, Zed

    def en_panne(route):
        route.fulfill(status=500, content_type="application/json",
                      body=json.dumps({"detail": "Registre en panne pour le test."}))
    page.route(re.compile(r"/api/personnages\?q=Zed$"), en_panne)
    with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=Zed")) as lecture:
        champ.press_sequentially("Zed", delay=20)
    assert lecture.value.status == 500
    expect(page.locator(c["liste"])).to_be_hidden(timeout=15000)   # rien n'est proposé, pas même « Créer »

    champ.press("Enter")
    expect(page.locator("#toasts .toast.error", has_text="Registre en panne pour le test")
           ).to_be_visible(timeout=15000)
    expect(champ).to_have_value("Zed")
    assert parties == [], f"l'écran a écrit sans avoir pu lire le registre : {parties}"
    assert [p["nom"] for p in _registre(atelier)].count("Zed") == 1


def test_une_lecture_du_registre_arrivee_en_retard_n_ecrase_pas_la_plus_recente(page, atelier):
    """Deux lectures du registre en vol pour la MÊME saisie ; la seconde répond d'abord,
    la première ensuite, avec un registre plus ANCIEN — où « Zed » n'existait pas encore.
    La liste reste celle de la plus récente, et Entrée prend « Zed » au lieu d'en créer un.

    La seconde lecture est celle du focus : on quitte le champ et on y revient, la saisie
    intacte. Les deux réponses sont façonnées par le test à partir de la vraie.
    """
    c = CHAMPS_PERSONNAGE["locuteur"]
    zed = _peupler(atelier, "Zed")["Zed"]
    with _api(atelier) as client:
        vrai = client.get("/api/personnages?q=Zed").json()
    assert [p["id"] for p in vrai] == [zed]
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    expect(liste).to_have_count(2, timeout=15000)                  # Tintin, Zed
    lectures = Retenue(page, LECTURE_REGISTRE)
    champ.press_sequentially("Zed", delay=0)
    lectures.attendre(1)                                           # la lecture différée
    page.locator("#an-note").focus()       # on quitte le champ (sa liste couvre la note)…
    champ.click()                                                  # … et on y revient
    premiere, seconde = lectures.attendre(2)
    assert all(r.request.url.endswith("?q=Zed") for r in (premiere, seconde))
    expect(champ).to_have_value("Zed")

    _repondre(page, seconde, vrai)
    expect(liste).to_have_count(1, timeout=15000)
    expect(liste).to_have_text("Zed")
    _repondre(page, premiere, [])                                  # la plus lente, plus ancienne
    page.wait_for_timeout(400)                                     # l'écran a eu le temps de la traiter
    expect(liste).to_have_count(1)
    expect(liste).to_have_text("Zed")                              # pas « ➕ Créer « Zed » »

    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)):
        champ.press("Enter")
    assert envoi.value.post_data_json["personnage_id"] == zed
    assert _creations(parties) == [], parties


def test_un_nom_qu_on_vient_de_creer_retape_aussitot_n_est_pas_cree_deux_fois(page, atelier):
    """On crée « Zed » à la volée (geste lent : la liste propose « Créer »), puis on le
    retape aussitôt, Entrée avant toute nouvelle lecture. Ce que l'écran savait de « Zed »
    date d'AVANT sa création : il relit le registre, et prend celui qu'il vient de créer."""
    c = CHAMPS_PERSONNAGE["locuteur"]
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    champ.press_sequentially("Zed", delay=20)
    expect(liste.filter(has_text="Créer")).to_be_visible(timeout=15000)
    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)):
        champ.press("Enter")
    zed = envoi.value.post_data_json["personnage_id"]
    expect(page.locator(c["puce"])).to_contain_text("Zed", timeout=15000)
    assert len(_creations(parties)) == 1

    lectures = Retenue(page, LECTURE_REGISTRE)
    _taper_et_valider_d_un_trait(page, c["champ"], "Zed")
    lectures.attendre(1)                             # l'écran RELIT : il ne se fie pas à l'ancien savoir
    assert lectures.tenues[0].request.url.endswith("?q=Zed"), (
        "l'écran n'a pas relu le registre pour « Zed » avant de décider — lectures tenues : "
        f"{[r.request.url for r in lectures.tenues]}, écritures : {parties}")
    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        lectures.relacher()
    assert reponse.value.status == 200, reponse.value.text()
    assert envoi.value.post_data_json["personnage_id"] == zed
    assert len(_creations(parties)) == 1, f"« Zed » a été créé deux fois : {parties}"
    assert [p["nom"] for p in _registre(atelier)].count("Zed") == 1


def test_le_locuteur_va_a_la_zone_du_geste_meme_si_l_on_en_change(page, atelier):
    """Relire le registre prend du temps : si l'on sélectionne une autre zone entre-temps,
    le locuteur revient à la bulle où Entrée a été pressée — pas au cartouche où l'on est
    arrivé."""
    c = CHAMPS_PERSONNAGE["locuteur"]
    zed = _peupler(atelier, *FIGURANTS, "Zed")["Zed"]
    bulle, cartouche = atelier["bulle"], atelier["cartouche"]
    chemin = f"/api/regions/{bulle}/locuteur"
    _ouvrir(page, atelier, "bulle")
    champ = page.locator(c["champ"])
    parties = _ecritures(page)

    champ.click()
    expect(page.locator(f"{c['liste']} div")).to_have_count(10, timeout=15000)
    lectures = Retenue(page, LECTURE_REGISTRE)
    champ.press_sequentially("Zed", delay=0)
    lectures.attendre(1)
    champ.press("Enter")

    _zone(page, cartouche)                           # on part sur le cartouche
    expect(champ).to_have_accessible_name(re.compile("cartouche"))

    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        lectures.relacher()
    assert reponse.value.status == 200, reponse.value.text()
    assert envoi.value.post_data_json == {"personnage_id": zed}
    page.wait_for_timeout(300)
    assert [p for p in parties if p.startswith("PUT ")] == [
        f"PUT {chemin} " + json.dumps({"personnage_id": zed}, separators=(",", ":"))], parties
    assert _lie(atelier, bulle, "locuteur")["id"] == zed
    assert _lie(atelier, cartouche, "locuteur") is None
    # L'écran, lui, montre toujours le cartouche — sans locuteur.
    expect(page.locator("#an-loc-nom")).to_have_text("")


# --------------------------------------------------------------------------- #
# ANN-8 — après une validation, UNE flèche surligne une proposition
# --------------------------------------------------------------------------- #
# La première ↓ rouvrait la liste sans rien surligner, et il en fallait une seconde : la
# flèche comptait les lignes restées dans le DOM de la liste PRÉCÉDENTE — vide quand elle
# n'avait rien proposé. Chaque test valide d'abord une saisie qui ne laissait AUCUNE ligne,
# puis presse ↓ une seule fois.
def test_apres_une_creation_de_personnage_une_fleche_surligne_le_registre(page, atelier):
    """Le champ du locuteur vient de créer « Zed » : la première ↓ relit le registre pour
    le champ vide et en surligne la première entrée — jamais « Créer « Zed » », la ligne
    restée de la liste d'avant, qui aurait créé un second « Zed »."""
    c = CHAMPS_PERSONNAGE["locuteur"]
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    champ.press_sequentially("Zed", delay=20)
    expect(liste.filter(has_text="Créer")).to_be_visible(timeout=15000)
    with page.expect_response(_est("PUT", chemin)):
        champ.press("Enter")
    expect(champ).to_have_value("")

    champ.press("ArrowDown")
    actif = page.locator(f"{c['liste']} div.active")
    expect(actif).to_have_count(1, timeout=15000)
    expect(actif).not_to_contain_text("Créer")
    expect(liste).to_have_count(2)                   # Tintin, Zed : le registre du champ vide
    assert len(_creations(parties)) == 1, parties


# --------------------------------------------------------------------------- #
# ANN-8 — les deux champs de personnage savent ce que l'autre vient de créer
# --------------------------------------------------------------------------- #
def test_un_nom_cree_par_l_autre_champ_n_est_pas_cree_deux_fois(page, atelier):
    """Rapporté par l'auteur du correctif du 2026-10-13, rejoué ici : « Zed » est cherché
    dans le champ du locuteur (sa liste dit « Créer »), puis créé par la boîte personnage ;
    de retour sur la bulle, « Zed » tapé d'un trait se décidait sur la liste du locuteur —
    celle d'AVANT la création — et en créait un second. Le registre est tenu en vol au
    retour sur la bulle : rien d'autre que ce que le champ savait ne peut décider."""
    loc, boite = CHAMPS_PERSONNAGE["locuteur"], CHAMPS_PERSONNAGE["boite-personnage"]
    bulle = atelier["bulle"]
    chemin = f"/api/regions/{bulle}/locuteur"
    _ouvrir(page, atelier, "bulle")
    parties = _ecritures(page)

    champ = page.locator(loc["champ"])
    champ.click()
    champ.press_sequentially("Zed", delay=20)
    expect(page.locator(f"{loc['liste']} div").filter(has_text="Créer")).to_be_visible(timeout=15000)

    # La boîte personnage crée « Zed ».
    _zone(page, atelier["personnage"])
    autre = page.locator(boite["champ"])
    autre.click()
    autre.press_sequentially("Zed", delay=20)
    expect(page.locator(f"{boite['liste']} div").filter(has_text="Créer")).to_be_visible(timeout=15000)
    with page.expect_response(_est("PUT", f"/api/regions/{atelier['personnage']}/personnage")):
        autre.press("Enter")
    assert len(_creations(parties)) == 1, parties
    zed = [p for p in _registre(atelier) if p["nom"] == "Zed"][0]["id"]

    # Retour sur la bulle : le registre ne répond plus tant que le test ne le relâche pas.
    _zone(page, bulle)
    lectures = Retenue(page, LECTURE_REGISTRE)
    champ.click()
    _taper_et_valider_d_un_trait(page, loc["champ"], "Zed")
    page.wait_for_timeout(500)
    assert len(_creations(parties)) == 1, f"« Zed » recréé d'après la liste d'avant : {parties}"
    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        lectures.relacher()
    assert reponse.value.status == 200, reponse.value.text()
    assert envoi.value.post_data_json["personnage_id"] == zed
    assert len(_creations(parties)) == 1, parties
    assert [p["nom"] for p in _registre(atelier)].count("Zed") == 1


# --------------------------------------------------------------------------- #
# ANN-8 (Hugo, 2026-10-21) — ↓ puis Entrée pendant que la liste se recharge
# --------------------------------------------------------------------------- #
# Entre une frappe et le retour de sa liste, la liste à l'écran est celle de la saisie
# d'AVANT. ↓ y surligne une ligne ; Entrée la prenait. Elle la revérifie désormais contre
# ce qui est tapé : la surlignée part si elle y répond encore, et sinon rien ne part — la
# liste de la saisie arrive, rien de surligné. La lecture est TENUE en vol : « pendant le
# rechargement » ne dépend d'aucune vitesse.
@pytest.mark.parametrize("fleches,part", [(1, "Zed"), (2, None)],
                         ids=["la-surlignee-repond-encore", "la-surlignee-ne-repond-plus"])
def test_pendant_le_rechargement_entree_reverifie_la_surlignee(page, atelier, fleches, part):
    c = CHAMPS_PERSONNAGE["locuteur"]
    ids = _peupler(atelier, "Zed", "Zelda")
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=Ze")):
        champ.press_sequentially("Ze", delay=20)
    expect(liste).to_have_count(3, timeout=15000)          # Zed, Zelda, Créer « Ze »

    lectures = Retenue(page, LECTURE_REGISTRE)
    champ.press("d")
    lectures.attendre(1)                                   # la liste de « Zed », tenue
    assert lectures.tenues[0].request.url.endswith("?q=Zed")
    expect(liste).to_have_count(3)                         # à l'écran : celle de « Ze »
    for _ in range(fleches):
        champ.press("ArrowDown")
    surlignee = page.locator(f"{c['liste']} div.active")
    expect(surlignee).to_have_text(re.compile(r"^Zed$" if fleches == 1 else r"^Zelda$"))

    if part:
        with page.expect_request(_est("PUT", chemin)) as envoi, \
                page.expect_response(_est("PUT", chemin)) as reponse:
            champ.press("Enter")
        assert reponse.value.status == 200, reponse.value.text()
        assert envoi.value.post_data_json["personnage_id"] == ids[part]
        lectures.relacher()
        return

    champ.press("Enter")
    # Le témoin : l'écran a traité Entrée — plus rien n'est surligné, la saisie reste.
    expect(surlignee).to_have_count(0, timeout=15000)
    expect(champ).to_have_value("Zed")
    page.wait_for_timeout(400)
    assert parties == [], f"Entrée a pris une ligne de la liste d'avant : {parties}"
    # Une seule lecture pour « Zed » : celle déjà en vol suffit.
    assert [r.request.url for r in lectures.tenues if r.request.url.endswith("?q=Zed")] == [
        lectures.tenues[0].request.url], [r.request.url for r in lectures.tenues]

    with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=Zed")):
        lectures.relacher()
    expect(liste).to_have_count(1, timeout=15000)          # la liste de « Zed » : lui seul
    expect(liste).to_have_text("Zed")
    expect(surlignee).to_have_count(0)
    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)):
        champ.press("Enter")
    assert envoi.value.post_data_json["personnage_id"] == ids["Zed"]
    assert _creations(parties) == [], parties


# --------------------------------------------------------------------------- #
# ANN-8 (Hugo, 2026-10-21) — plusieurs personnages du même nom se départagent à l'écran
# --------------------------------------------------------------------------- #
def _deux_zed(decor):
    """Deux « Zed » au registre : l'un sans série, l'autre d'une série. Rend {série: id}."""
    with _api(decor, ecriture=True) as c:
        return {serie: c.post("/api/personnages", json={"nom": "Zed", "serie": serie}).json()["id"]
                for serie in (None, "Les Aventures")}


@pytest.mark.parametrize("champ_de", list(CHAMPS_PERSONNAGE))
@pytest.mark.parametrize("moment", ["liste revenue", "avant la liste"])
def test_des_homonymes_entree_ne_decide_pas_la_liste_se_reduit_a_eux(page, atelier, champ_de, moment):
    """Deux « Zed » : Entrée ne prend plus le premier dans l'ordre du registre. Rien ne part ;
    la liste se réduit aux deux, chacun avec sa série, et l'on choisit — ici le second, aux
    flèches. Deux moments, deux chemins de l'écran : la liste de « Zed » déjà revenue, ou
    Entrée pressée avant elle (l'écran relit le registre lui-même)."""
    c = CHAMPS_PERSONNAGE[champ_de]
    zed = _deux_zed(atelier)
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    expect(liste).to_have_count(3, timeout=15000)          # Tintin, Zed, Zed
    lues = []                                              # les lectures du registre, dès ici
    page.on("request", lambda r: lues.append(r.url) if LECTURE_REGISTRE.search(r.url) else None)
    if moment == "liste revenue":
        with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=Zed")):
            champ.press_sequentially("Zed", delay=20)
        expect(liste).to_have_count(2, timeout=15000)
        champ.press("Enter")
    else:
        with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=Zed")):
            _taper_et_valider_d_un_trait(page, c["champ"], "Zed")

    # Le témoin : la liste réduite, chaque ligne avec sa série — « sans série » comprise.
    expect(liste).to_have_count(2, timeout=15000)
    expect(liste.nth(0)).to_have_text(re.compile(r"^Zed\s*sans série$"))
    expect(liste.nth(1)).to_have_text(re.compile(r"^Zed\s*Les Aventures$"))
    expect(page.locator(f"{c['liste']} div.active")).to_have_count(0)
    expect(champ).to_have_value("Zed")
    page.wait_for_timeout(400)
    assert parties == [], f"Entrée a décidé entre deux homonymes : {parties}"
    # Et la liste réduite RESTE : aucune lecture de plus ne la recouvre de la liste entière.
    # Entrée d'un trait, la lecture différée de la frappe était encore armée — partie après
    # Entrée, elle rouvrait toute la liste par-dessus celle des homonymes.
    assert len(lues) == 1 and lues[0].endswith("?q=Zed"), lues
    expect(liste.nth(0)).to_have_text(re.compile(r"^Zed\s*sans série$"))

    # Une seconde Entrée sans rien surligner ne décide pas davantage.
    champ.press("Enter")
    page.wait_for_timeout(300)
    assert parties == [], parties
    expect(liste).to_have_count(2)

    champ.press("ArrowDown")
    champ.press("ArrowDown")
    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    assert envoi.value.post_data_json["personnage_id"] == zed["Les Aventures"]
    expect(page.locator(c["puce"])).to_contain_text("Les Aventures", timeout=15000)
    assert _creations(parties) == [], parties


def test_un_homonyme_se_choisit_aussi_d_un_clic(page, atelier):
    c = CHAMPS_PERSONNAGE["locuteur"]
    zed = _deux_zed(atelier)
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")

    champ.click()
    with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=Zed")):
        champ.press_sequentially("Zed", delay=20)
    expect(liste).to_have_count(2, timeout=15000)
    champ.press("Enter")
    expect(liste.nth(0)).to_have_text(re.compile(r"sans série$"), timeout=15000)
    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)):
        liste.nth(0).click()
    assert envoi.value.post_data_json["personnage_id"] == zed[None]
