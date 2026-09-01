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
    page.goto(moteurs["base"] + "/corpus", wait_until="networkidle")
    page.click("#btn-sante")
    corps = page.locator("#sante-body")
    corps.wait_for(state="visible")

    # 1. Ouvrir n'éprouve pas. Le premier import de torch coûte des secondes et des
    #    centaines de mégaoctets ; le payer pour afficher un écran rétablirait exactement
    #    ce que la séparation des deux profondeurs évite.
    assert moteurs["profonds"] == [], (
        "ouvrir le panneau a déclenché le contrôle profond : " + str(moteurs["profonds"]))

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
    gris = page.locator("#sel-info").evaluate("el => getComputedStyle(el).color")
    assert rouge != gris, (
        f"le bilan d'une panne s'affiche comme un message ordinaire ({rouge}) : "
        "la classe `erreur` n'est reçue par aucune règle CSS")


def test_le_panneau_ne_s_ouvre_pas_tout_seul(page, moteurs):
    """Charger la Bibliothèque ne doit rien demander à `/api/sante` : le contrôle, même
    rapide, appartient à un geste. Une page qui sonde d'elle-même finit par sonder
    profond « puisque c'est déjà branché »."""
    page.goto(moteurs["base"] + "/corpus", wait_until="networkidle")
    assert page.locator("#sante-modal").is_hidden()
    assert moteurs["tous"] == [], (
        "la Bibliothèque interroge `/api/sante` d'elle-même : " + str(moteurs["tous"]))


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


def test_rouvrir_pendant_une_epreuve_n_efface_pas_ce_qui_l_explique(page, moteurs_lents):
    """Fermer le panneau n'annule pas l'épreuve : le fetch continue et le bouton reste
    désarmé. Rouvrir remettait le message à zéro — on retrouvait un « Éprouver » grisé,
    sans un mot, pendant les quinze secondes que dure l'import de torch. Rien ne casse,
    aucune exception : ça se lit simplement comme une panne du panneau lui-même, au moment
    où il est en train de faire exactement son travail."""
    page.goto(moteurs_lents + "/corpus", wait_until="networkidle")
    page.click("#btn-sante")
    page.wait_for_selector("#sante-modal:not([hidden]) .sante-ligne", timeout=3000)
    page.click("#sante-eprouver")
    occupe = page.locator('#sante-eprouver[aria-disabled="true"]')
    assert occupe.count(), "l'épreuve devrait s'annoncer en cours"

    # Le cœur de l'affaire, et ce que ce test garde vraiment : le focus ne quitte pas la
    # modale. Un vrai `disabled` sur le bouton qui le PORTE le rend au <body> — Tab n'est
    # plus piégé, Échap ne ferme plus, et le panneau devient un cul-de-sac au clavier
    # pendant toute la durée de l'épreuve. Aucune exception, et l'audit axe n'y voit rien :
    # il photographie un écran, il n'appuie sur aucune touche.
    assert page.evaluate("() => document.activeElement.id") == "sante-eprouver", (
        "le focus a quitté le bouton pendant l'épreuve")

    page.keyboard.press("Escape")            # on ferme pendant que ça charge
    page.wait_for_selector("#sante-modal", state="hidden", timeout=3000)
    page.click("#btn-sante")                 # …et on rouvre aussitôt
    page.wait_for_selector("#sante-modal:not([hidden])", timeout=3000)

    assert occupe.count(), (
        "le bouton devrait rester occupé : l'épreuve n'est pas finie")
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
