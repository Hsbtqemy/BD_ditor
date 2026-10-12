"""Le panneau d'annotation de l'Atelier, au plus près du geste (ANN-6).

Un retour d'usage de la production, rapporté le 2026-10-12, que rien n'aurait fait tomber :
la suite ne posait de locuteur que par l'API, et ne sélectionnait jamais autre chose qu'une
bulle en mode Annotation.

**Le locuteur.** « Une fois une nouvelle zone de texte créée, on ne peut pas lui attribuer
un locuteur (de même pour les cartouches). » Mesuré le même jour : le bloc « Locuteur » ne
s'affichait que pour une bulle, pendant que la route acceptait n'importe quelle région —
case et boîte personnage comprises. L'écran et le serveur ne tenaient pas la même règle, et
aucun des deux n'avait la bonne. Ils la tiennent maintenant ensemble : bulle, cartouche,
texte, et rien d'autre.

Ce que ce fichier mesure, et pourquoi de cette façon :

- **le bloc s'offre aux trois types et à eux seuls** — et « caché » ne s'affirme qu'APRÈS
  qu'un témoin a montré que le panneau s'est chargé : `#loc-section` naît `hidden` dans le
  gabarit, si bien qu'un `to_be_hidden()` posé trop tôt passe sur une page qui n'a encore
  rien décidé ;
- **le geste PART** — la requête d'attribution est attendue en tant que requête, avec son
  corps, et pas seulement l'état final : un écran qui afficherait la puce sans rien envoyer
  rendrait le même état final ;
- **l'écran et le serveur disent la même chose, type par type** — sans quoi l'un des deux
  peut changer d'avis sans que rien ne le dise, ce qui est exactement l'état d'où l'on vient.
"""
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, TYPES_MUETS, TYPES_PARLANTS, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source. Le panneau d'annotation ne
# vit que dans l'Atelier : aucune autre surface n'attribue un locuteur ni ne décrit une case.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/recherche": "aucun panneau d'annotation : la Recherche filtre par locuteur, elle n'en attribue pas",
    "/corpus": "aucun panneau d'annotation : la Bibliothèque range des albums et des planches",
    "/exploration": "aucun panneau d'annotation : l'Exploration compte par locuteur, elle n'en attribue pas",
    "/administration": "aucun panneau d'annotation : rien n'y porte sur une région d'une planche",
}

# Le bloc qui PROUVE que le panneau s'est chargé, pour les types où « Locuteur » doit
# rester caché. Chaque type muet a le sien : une case reçoit une situation, une boîte
# personnage une identité.
TEMOIN = {"case": "#situation-section", "personnage": "#perso-section"}

# Ce que le nom accessible du champ doit NOMMER, type par type. Le libellé entier n'est
# pas verrouillé — seulement la propriété qui manquait : il disait « à la bulle » devant
# un cartouche.
MOT = {"bulle": "bulle", "cartouche": "cartouche", "texte": "texte"}


@pytest.fixture
def atelier(live_server):
    """Une planche, une case, et sous elle une région de CHAQUE type — plus deux personnages
    déjà au registre, pour changer de locuteur sans en créer un second à la volée."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "E2E annotation"}).json()["id"]
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
                 "texte": region("texte", 400, 60, case),
                 "personnage": region("personnage", 400, 300, case),
                 "tintin": c.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]}
    finally:
        c.close()
    assert set(TYPES_PARLANTS) | set(TYPES_MUETS) <= set(decor), (
        "le décor ne porte pas une région de chaque type : un test paramétré sur un type "
        "absent lèverait un KeyError qui se lirait comme une panne de l'écran")
    return decor


def _ouvrir(page, decor, type_zone):
    """Ouvre l'Atelier sur la région du type demandé, en mode Annotation."""
    page.goto(f"{decor['base']}/?album={decor['album']}&planche={decor['planche']}"
              f"&region={decor[type_zone]}", wait_until="networkidle")
    # La région est bien celle qu'on croit, AVANT de juger ce que son panneau offre : une
    # sélection qui aurait échoué laisserait le panneau vide, donc « Locuteur » caché.
    expect(page.locator("#region-type")).to_have_value(type_zone, timeout=15000)
    page.locator('button[data-mode="annotation"]').click()
    expect(page.locator("#panel-annotation")).to_be_visible(timeout=15000)


def _locuteur(decor, rid):
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30) as c:
        return c.get(f"/api/regions/{rid}/locuteur").json()["locuteur"]


def _est(methode, chemin):
    """Prédicat de requête OU de réponse : cette méthode, sur ce chemin exact."""
    def predicat(objet):
        requete = getattr(objet, "request", objet)
        return requete.method == methode and requete.url.endswith(chemin)
    return predicat


@pytest.mark.parametrize("type_zone", TYPES_PARLANTS + TYPES_MUETS)
def test_le_bloc_locuteur_s_offre_aux_zones_de_texte_et_a_elles_seules(page, atelier, type_zone):
    """Le bloc s'affiche pour une bulle, un cartouche, une zone de texte — et le serveur
    accepte exactement ce que l'écran offre."""
    _ouvrir(page, atelier, type_zone)
    bloc, champ = page.locator("#loc-section"), page.locator("#loc-input")

    if type_zone in TYPES_PARLANTS:
        expect(bloc).to_be_visible(timeout=15000)
        expect(champ).to_be_visible()
        # Le champ se NOMME d'après la zone qu'on a sous les yeux, pas d'après une autre.
        expect(champ).to_have_accessible_name(re.compile(MOT[type_zone]))
        for autre in set(MOT.values()) - {MOT[type_zone]}:
            expect(champ).not_to_have_accessible_name(re.compile(autre))
    else:
        expect(page.locator(TEMOIN[type_zone])).to_be_visible(timeout=15000)
        expect(bloc).to_be_hidden()

    # L'accord, mesuré : ce que l'écran n'offre pas, le serveur le refuse — et l'inverse.
    with httpx.Client(base_url=atelier["base"], trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        rep = c.put(f"/api/regions/{atelier[type_zone]}/locuteur",
                    json={"personnage_id": atelier["tintin"]})
    assert (rep.status_code == 200) == bloc.is_visible(), (
        f"pour une région « {type_zone} », l'écran {'offre' if bloc.is_visible() else 'cache'} "
        f"le bloc Locuteur et le serveur répond {rep.status_code} : les deux ne tiennent "
        "plus la même règle")
    assert rep.status_code == (200 if type_zone in TYPES_PARLANTS else 422), rep.text


@pytest.mark.parametrize("type_zone", TYPES_PARLANTS)
def test_attribuer_changer_retirer_un_locuteur_puis_annuler(page, atelier, type_zone):
    """Le parcours d'une bulle, joué sur les trois types : créer le personnage à la volée,
    en changer, le retirer, et Ctrl+Z deux fois."""
    rid = atelier[type_zone]
    chemin = f"/api/regions/{rid}/locuteur"
    _ouvrir(page, atelier, type_zone)
    champ, puce = page.locator("#loc-input"), page.locator("#loc-current .tag-chip")
    expect(champ).to_be_visible(timeout=15000)
    expect(page.locator("#loc-current")).to_contain_text("Aucun locuteur")

    # ATTRIBUER, en créant le personnage à la volée. La requête est attendue EN TANT QUE
    # requête : l'état final seul ne dirait pas qu'elle est partie.
    champ.click()
    champ.press_sequentially("Narrateur", delay=20)
    expect(page.locator("#loc-suggest div", has_text="Créer")).to_be_visible(timeout=15000)
    with page.expect_request(_est("POST", "/api/personnages")), \
            page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    narrateur = envoi.value.post_data_json["personnage_id"]
    expect(puce).to_be_visible(timeout=15000)
    expect(puce).to_contain_text("Narrateur")
    assert _locuteur(atelier, rid) == {"id": narrateur, "nom": "Narrateur", "serie": None}
    # Comme pour une bulle : le profil du personnage s'offre dès qu'il y a un locuteur.
    expect(page.locator("#perso-attr-section")).to_be_visible()

    # CHANGER, pour un personnage déjà au registre — proposé, pas créé une seconde fois.
    champ.click()
    champ.press_sequentially("Tintin", delay=20)
    expect(page.locator("#loc-suggest div", has_text="Tintin").first).to_be_visible(timeout=15000)
    expect(page.locator("#loc-suggest div", has_text="Créer")).to_have_count(0)
    with page.expect_request(_est("PUT", chemin)) as envoi:
        champ.press("Enter")
    assert envoi.value.post_data_json == {"personnage_id": atelier["tintin"]}
    expect(puce).to_contain_text("Tintin", timeout=15000)
    assert _locuteur(atelier, rid)["id"] == atelier["tintin"]

    # RETIRER.
    with page.expect_response(_est("DELETE", chemin)) as reponse:
        puce.locator(".x").click()
    assert reponse.value.status == 204
    expect(page.locator("#loc-current")).to_contain_text("Aucun locuteur", timeout=15000)
    assert _locuteur(atelier, rid) is None

    # ANNULER, deux fois, hors champ de saisie : le retrait d'abord, le changement ensuite.
    # L'écran SUIT sans recharger — le bloc est rechargé par l'annulation, et il ne l'était
    # pas pour un cartouche, dont le bloc n'existait pas.
    #
    # La RÉPONSE est attendue, et longtemps. La première annulation d'un serveur neuf charge
    # spaCy à froid avant d'inverser quoi que ce soit (`nlp.ensure_loaded()` dans la route :
    # 8,6 et 9,7 s mesurés le 2026-10-12, 0,0 s pour la suivante), et chaque test a SON
    # serveur. Écrit d'abord « presser, puis attendre la puce 15 s », ce passage est tombé
    # neuf fois sur quinze pendant une passe de mutants — sous des mutants qui ne touchaient
    # ni au locuteur ni à l'annulation —, et pas une fois dans les trente-quatre autres
    # exécutions du jour : neuf secondes de chargement laissent peu de marge sur quinze, et
    # le poste était sans doute plus chargé ce quart d'heure-là (cela, c'est une hypothèse ;
    # le chargement à froid, lui, est mesuré). Attendre la réponse dit aussi ce qui a manqué,
    # le jour où quelque chose manque : la requête jamais partie, un refus, ou le mauvais
    # acte défait.
    with page.expect_response(_est("POST", "/api/undo"), timeout=180000) as annulation:
        page.locator("body").press("Control+z")
    assert annulation.value.status == 200, annulation.value.text()
    assert annulation.value.json()["acte"] == "delien", annulation.value.json()
    expect(puce).to_contain_text("Tintin", timeout=15000)
    assert _locuteur(atelier, rid)["id"] == atelier["tintin"]
    with page.expect_response(_est("POST", "/api/undo"), timeout=180000) as annulation:
        page.locator("body").press("Control+z")
    assert annulation.value.status == 200, annulation.value.text()
    assert annulation.value.json()["acte"] == "lien", annulation.value.json()
    expect(puce).to_contain_text("Narrateur", timeout=15000)
    assert _locuteur(atelier, rid)["id"] == narrateur


def test_le_bloc_suit_le_type_qu_on_change_sous_les_yeux(page, atelier):
    """Changer le type d'une région sélectionnée, en mode Annotation, change les blocs
    qu'on lui offre — sans avoir à la resélectionner.

    Le défaut existait avant ce chantier (une bulle passée en cartouche gardait son bloc),
    et il ne coûtait rien tant que la route acceptait tout. Depuis qu'elle refuse une case,
    un bloc resté affiché offrirait un geste que le serveur rejette.
    """
    rid = atelier["bulle"]
    _ouvrir(page, atelier, "bulle")
    bloc, liste = page.locator("#loc-section"), page.locator("#region-type")
    expect(bloc).to_be_visible(timeout=15000)

    with page.expect_response(_est("PUT", f"/api/regions/{rid}")) as reponse:
        liste.select_option("case")
    assert reponse.value.status == 200, reponse.value.text()
    # Le témoin d'abord : le panneau a bien suivi, il n'est pas seulement resté tel quel.
    expect(page.locator("#situation-section")).to_be_visible(timeout=15000)
    expect(bloc).to_be_hidden()

    with page.expect_response(_est("PUT", f"/api/regions/{rid}")):
        liste.select_option("cartouche")
    expect(bloc).to_be_visible(timeout=15000)
    expect(page.locator("#situation-section")).to_be_hidden()
    expect(page.locator("#loc-input")).to_have_accessible_name(re.compile("cartouche"))
