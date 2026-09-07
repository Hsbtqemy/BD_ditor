"""Le panneau des moteurs, dans un vrai navigateur (SANTE-1).

Ce fichier existe parce que la version lisant le SOURCE ne mordait pas. « Ouvrir le
panneau ne déclenche pas le contrôle profond » s'était écrit `"profond" not in openSante`,
qui reste vrai si `openSante` appelle `santeEprouver()` — mesuré, la mutation passait au
vert. Une affirmation sur ce que la page FAIT se vérifie en la faisant faire.

Le décor est fabriqué : `/api/sante` est interceptée pour répondre exactement la panne du
2026-08-27 — `bulles` présent, dont l'import lève `torchvision::nms` — qu'aucune machine
de test ne produira jamais spontanément. C'est le seul état qui compte, et donc le seul
qu'on ne pouvait pas observer.
"""
import json

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from conftest import SANTE_PROFOND, SANTE_RAPIDE  # noqa: E402

pytestmark = pytest.mark.e2e

# Serveur live MONO-POSTE (défaut de la fixture) : `/api/sante` répond sans identité
# de toute façon, et déclarer le proxy ferait paraître le corpus vide au navigateur,
# qui n'envoie aucun en-tête — un bandeau de portée vide en travers d'un test qui
# ne parle pas d'autorisation.


# UX-10 — ce que cet audit COUVRE, et ce qu'il écarte avec sa raison.
#
# Cet audit suit un PANNEAU, pas une page. Écrit le 2026-09-07 en annonçant : « le jour
# où il déménagera vers `/administration`, cette déclaration devra suivre ». Il a déménagé
# le jour même (UX-10), et la garde a bien forcé à le voir.
SURFACES_AUDITEES = ("/administration",)
SURFACES_HORS_PERIMETRE = {
    "/": "le panneau des moteurs n'y est pas rendu",
    "/corpus": "le panneau en est PARTI le 2026-09-07 ; la Bibliothèque ne doit même plus "
               "interroger `/api/sante`, ce que `test_la_bibliotheque_ne_sonde_plus_rien` "
               "affirme de son côté",
    "/recherche": "le panneau des moteurs n'y est pas rendu",
    "/exploration": "le panneau des moteurs n'y est pas rendu",
}


@pytest.fixture
def moteurs(live_server, page):
    """Détourne `/api/sante` et COMPTE les appels — tous, et les profonds à part. Le
    compteur est la moitié du test : ce qu'on veut prouver est autant ce que le panneau
    affiche que ce qu'il s'abstient de demander."""
    tous, profonds = [], []

    def repondre(route):
        url = route.request.url
        profond = "profond=1" in url
        tous.append(url)
        if profond:
            profonds.append(url)
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(SANTE_PROFOND if profond else SANTE_RAPIDE))

    page.route("**/api/sante*", repondre)
    return {"base": live_server, "tous": tous, "profonds": profonds}


def test_le_panneau_montre_la_panne_sans_confondre_avec_l_absence(page, moteurs):
    """Le chantier entier, de la réponse HTTP au texte à l'écran.

    Trois affirmations, et il faut les trois : ouvrir ne coûte rien ; le contrôle rapide
    ne fait jamais dire « opérationnel » ; et une fois éprouvé, le moteur CASSÉ crie
    pendant que les moteurs simplement ABSENTS se taisent. Confondre les deux derniers
    n'échoue nulle part — ça apprend seulement à ne plus lire le panneau.
    """
    page.goto(moteurs["base"] + "/administration", wait_until="networkidle")
    corps = page.locator("#sante-body")
    corps.wait_for(state="visible")

    # 1. AFFICHER n'éprouve pas. Depuis UX-10 le panneau n'est plus une modale qu'on ouvre :
    #    il est le contenu de la page, donc le contrôle RAPIDE part au chargement. Ce qui
    #    reste un geste — et doit le rester — c'est le contrôle PROFOND : le premier import
    #    de torch coûte des secondes et des centaines de mégaoctets, et le payer pour
    #    afficher un écran rétablirait exactement ce que la séparation des deux évite.
    assert moteurs["profonds"] == [], (
        "afficher la page a déclenché le contrôle profond : " + str(moteurs["profonds"]))

    # 2. La présence ne s'annonce pas comme un fonctionnement.
    texte = corps.inner_text()
    assert "présent, non éprouvé" in texte
    assert "opérationnel" not in texte
    assert "en panne" not in texte          # rien n'a encore été éprouvé : rien à dire

    page.click("#sante-eprouver")
    page.wait_for_function(
        "() => document.querySelector('#sante-body').innerText.includes('en panne')",
        timeout=15000)
    assert len(moteurs["profonds"]) == 1

    # 3. Le croisement. `bulles` était localisé et ne s'importe pas → panne, avec sa
    #    cause. `ocr` et spaCy manquent → « non installé », le mot juste : les moteurs
    #    sont OPTIONNELS, et trois postes sur quatre n'en ont aucun.
    lignes = corps.locator(".sante-ligne")
    par_nom = {lignes.nth(i).locator("b").inner_text(): lignes.nth(i).inner_text()
               for i in range(lignes.count())}
    assert "en panne" in par_nom["YOLOv8 (bulles)"]
    assert "torchvision::nms" in par_nom["YOLOv8 (bulles)"]
    assert "opérationnel" in par_nom["Kumiko"]
    for absent in ("EasyOCR", "spaCy"):
        assert "non installé" in par_nom[absent], par_nom[absent]
        assert "en panne" not in par_nom[absent], (
            f"{absent} n'est pas installé, ce n'est pas une panne : "
            "crier sur l'état normal d'un poste apprend à ignorer le panneau")

    # Le bilan nomme un nombre et renvoie quelque part : « en panne » sans « et alors ? »
    # laisse l'opérateur exactement où il était.
    msg = page.locator("#sante-msg")
    assert "1 moteur" in msg.inner_text() and "deploiement-docker" in msg.inner_text()

    # Et il se VOIT comme un échec. La classe `erreur` était posée par le JS sans qu'une
    # règle CSS la reçoive — `#col-msg.erreur` et `#fig-msg.erreur` étaient nommés un par
    # un — donc le bilan d'une panne s'affichait du même gris qu'un « tout va bien ».
    # Comparer les deux couleurs RENDUES est le seul moyen de le dire : la classe était
    # bien là, et le sélecteur qui lui donne sa teinte, ailleurs.
    rouge = msg.evaluate("el => getComputedStyle(el).color")
    # Le TÉMOIN de « message ordinaire ». C'était `#sel-info` tant que le panneau vivait
    # dans la Bibliothèque ; il n'existe pas sur `/administration` (UX-10), et le test s'y
    # est cassé — l'échec est venu d'un décor manquant, pas de la propriété gardée.
    # `#col-msg` est l'équivalent exact : mêmes classes (`muted small`) et même rôle, un
    # ÉTAT et non un contenu. On vérifie qu'il est bien neutre avant de s'en servir : un
    # témoin qui porterait lui-même `erreur` rendrait les deux couleurs égales, et le test
    # échouerait en accusant le CSS d'un défaut qui serait dans son propre décor.
    temoin = page.locator("#col-msg")
    assert "erreur" not in (temoin.get_attribute("class") or ""), (
        "le témoin porte la classe `erreur` : il ne peut pas servir de référence de "
        "message ordinaire, et la comparaison ci-dessous ne mesurerait plus rien")
    gris = temoin.evaluate("el => getComputedStyle(el).color")
    assert rouge != gris, (
        f"le bilan d'une panne s'affiche comme un message ordinaire ({rouge}) : "
        "la classe `erreur` n'est reçue par aucune règle CSS")


def test_la_bibliotheque_ne_sonde_plus_rien(page, moteurs):
    """La Bibliothèque ne demande RIEN à `/api/sante` — et l'affirmation s'est durcie.

    Elle disait avant « le panneau ne s'ouvre pas tout seul », le panneau y vivant derrière
    un bouton. Il en est PARTI le 2026-09-07 (UX-10), donc la Bibliothèque ne doit plus
    toucher cette route du tout. Garder le test en le pointant sur l'autre page aurait
    laissé un trou exactement là : un `santeCharger()` oublié dans `corpus.js` ne serait
    plus vu par personne.
    """
    page.goto(moteurs["base"] + "/corpus", wait_until="networkidle")
    assert page.locator("#sante-body").count() == 0, (
        "le panneau des moteurs est encore rendu en Bibliothèque : il a déménagé, et deux "
        "portes vers la même pièce se paient — l'une des deux vieillit")
    assert moteurs["tous"] == [], (
        "la Bibliothèque interroge `/api/sante` alors que le panneau n'y est plus : "
        + str(moteurs["tous"]))


def test_la_page_d_administration_ne_sonde_QUE_le_rapide(page, moteurs):
    """L'autre moitié de la propriété d'avant, déplacée avec le panneau.

    Le contrôle rapide part au chargement, puisqu'il EST le contenu. Le profond ne doit
    jamais partir avec lui : c'est la seule chose qui empêche « puisque c'est déjà
    branché » de devenir quinze secondes d'import à chaque ouverture de la page.
    """
    page.goto(moteurs["base"] + "/administration", wait_until="networkidle")
    page.locator("#sante-body").wait_for(state="visible")
    assert moteurs["tous"], "la page n'a même pas fait le contrôle rapide"
    assert moteurs["profonds"] == [], (
        "afficher la page a déclenché le contrôle PROFOND : " + str(moteurs["profonds"]))


# Retarder la réponse profonde, DANS LA PAGE. Le faire dans le gestionnaire `page.route`
# ne marche pas et c'est instructif : un `time.sleep` y bloque le pilote Playwright lui-
# même, donc l'assertion qui suit le clic n'est évaluée qu'APRÈS la réponse — l'épreuve
# était finie avant qu'on la regarde, et le test échouait en accusant le code. Envelopper
# `fetch` côté navigateur ne retient que la requête visée et laisse le pilote libre.
_FETCH_LENT = """
  const vrai = window.fetch;
  window.fetch = (...a) => String(a[0]).includes("profond=1")
    ? new Promise((r) => setTimeout(() => r(vrai(...a)), 1500))
    : vrai(...a);
"""


@pytest.fixture
def moteurs_lents(live_server, page):
    """Comme `moteurs`, mais le contrôle profond MET DU TEMPS — ce qu'il fait en vrai
    (16 s mesurées sur cette machine, tous moteurs installés). Sans cette lenteur, l'état
    « épreuve en cours » n'existe jamais assez longtemps pour qu'on le regarde."""
    page.add_init_script(_FETCH_LENT)
    page.route("**/api/sante*", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(SANTE_PROFOND if "profond=1" in r.request.url
                        else SANTE_RAPIDE)))
    return live_server


def test_le_focus_ne_quitte_pas_le_bouton_pendant_une_epreuve(page, moteurs_lents):
    """Ce qui SURVIT au déménagement du panneau, et ce qui a disparu avec lui.

    Ce test gardait deux choses. La première tenait à la MODALE : fermer pendant une
    épreuve n'annulait pas le fetch, et rouvrir remettait le message à zéro — on
    retrouvait un « Éprouver » grisé sans un mot, pendant les quinze secondes que dure
    l'import de torch, ce qui se lit comme une panne du panneau au moment précis où il
    travaille. Depuis UX-10 (2026-09-07) le panneau est une PAGE : il n'y a plus rien à
    fermer ni à rouvrir, donc plus de message à effacer. La propriété n'est pas devenue
    fausse, son objet a cessé d'exister — et c'est pour cela qu'elle est retirée ici
    plutôt que reformulée ailleurs, où elle n'aurait rien gardé.

    La seconde survit entière, et c'est le cœur : `aria-disabled` plutôt qu'un vrai
    `disabled`. Un `disabled` sur le bouton qui PORTE le focus le rend au `<body>` ; la
    tabulation repart du début de la page, et l'on perd sa place pour toute la durée de
    l'épreuve. Aucune exception, et l'audit axe n'y voit rien : il photographie un écran,
    il n'appuie sur aucune touche.
    """
    page.goto(moteurs_lents + "/administration", wait_until="networkidle")
    page.wait_for_selector("#sante-body .sante-ligne", timeout=3000)
    page.click("#sante-eprouver")
    occupe = page.locator('#sante-eprouver[aria-disabled="true"]')
    assert occupe.count(), "l'épreuve devrait s'annoncer en cours"

    assert page.evaluate("() => document.activeElement.id") == "sante-eprouver", (
        "le focus a quitté le bouton pendant l'épreuve : un `disabled` réel le rend au "
        "`<body>`, et la tabulation repart du début de la page")

    # Et l'épreuve reste EXPLIQUÉE tant qu'elle dure : un bouton désarmé sans un mot se
    # lit comme une panne. C'est ce qui restait vrai de la moitié perdue.
    assert page.locator("#sante-msg").inner_text().strip(), (
        "bouton grisé et message vide : le panneau paraît cassé alors qu'il travaille")


def test_le_serveur_repond_bien_ce_que_le_decor_simule(live_server):
    """Le décor ci-dessus est FABRIQUÉ : il ne prouve rien si sa forme diffère de celle du
    vrai serveur. Ce test-ci est le semis — sans lui, les deux précédents pourraient
    verdir sur une structure que `/api/sante` n'a jamais servie."""
    # 300 s, et ce n'est pas de la superstition : le contrôle profond importe torch,
    # ultralytics, easyocr et charge le modèle spaCy. Mesuré 16 s sur cette machine à
    # froid, sans rien d'autre qui tourne — or ce test s'exécute au milieu de la suite
    # E2E, Chromium et uvicorn compris. Un client à 30 s laissait moins d'un facteur 2,
    # et c'est exactement la marge qui a lâché ailleurs cette semaine (le chargement à
    # froid de spaCy dans la fixture `seeded`).
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=300)
    try:
        rapide = c.get("/api/sante").json()
        profond = c.get("/api/sante?profond=1").json()
    finally:
        c.close()
    assert set(rapide) == set(SANTE_RAPIDE), set(rapide) ^ set(SANTE_RAPIDE)
    assert set(profond) == set(SANTE_PROFOND), set(profond) ^ set(SANTE_PROFOND)
    assert set(profond["profond"]) == set(SANTE_PROFOND["profond"])
    for m, r in profond["profond"].items():
        assert set(r) == {"ok", "erreur"}, m
