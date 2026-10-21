"""Le panneau d'annotation de l'Atelier, au plus près du geste (ANN-6).

Deux retours d'usage de la production, rapportés le 2026-10-12, que rien n'aurait fait
tomber : la suite ne posait de locuteur que par l'API, et ne sélectionnait jamais autre chose
qu'une bulle en mode Annotation — donc jamais une case, ni son bloc « Situation ».

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

**La situation.** « J'ai l'impression que je peux, au niveau de la case, ajouter une
situation qui correspondrait au lieu. Mais finalement ça ne s'enregistre pas. » Rejoué le
même jour : le champ attend « dimension : valeur » ; « falaise » tapé seul puis Entrée ne
part pas, ne dit rien, et reste dans le champ. La décision est une PHRASE sous le champ, et
rien d'autre : la saisie ne change pas. Elle se mesure donc comme une phrase —

- **visible**, avant qu'on lise son texte : la section naît cachée, et lire le texte d'un
  élément caché réussit ;
- **reliée au champ**, par sa description accessible et non par la présence d'un attribut ;
- **vraie** : son exemple, tapé tel qu'on le lit, s'enregistre ;
- **logée** : dans le tiroir à 320 px sous une police de 24, entre ses marges, repliée et
  non rognée. La passe de l'image rend une autre police que le poste (DejaVu Sans contre
  Segoe UI), et c'est là qu'une phrase qui « tenait » ne tient plus.

**Le profil.** Les deux champs de profil d'un personnage — atteint par le locuteur d'une
zone, ou par une boîte personnage — attendent la même syntaxe, et s'y tromper coûte plus
cher : un profil vaut pour tout le corpus. Ils portent la même phrase, avec leur exemple,
et elle se mesure de la même façon, sur chacun des deux : ce sont deux blocs du gabarit.
"""
import json
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


def test_une_bulle_devenue_case_perd_son_locuteur_et_un_ctrl_z_rend_les_deux(page, atelier):
    """ANN-8 (Hugo, 2026-10-21) — la bulle de Tintin passe en case : l'écran DIT que le
    locuteur part, le serveur l'a retiré, et UN Ctrl+Z rend la bulle avec Tintin — sans
    bulle muette entre les deux."""
    rid = atelier["bulle"]
    with httpx.Client(base_url=atelier["base"], trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        rep = c.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": atelier["tintin"]})
        assert rep.status_code == 200, rep.text
    _ouvrir(page, atelier, "bulle")
    expect(page.locator("#loc-current")).to_contain_text("Tintin", timeout=15000)

    with page.expect_response(_est("PUT", f"/api/regions/{rid}")) as reponse:
        page.locator("#region-type").select_option("case")
    assert reponse.value.status == 200, reponse.value.text()
    expect(page.locator("#toasts .toast", has_text=re.compile(r"Locuteur « Tintin » retiré"))
           ).to_be_visible(timeout=15000)
    expect(page.locator("#situation-section")).to_be_visible(timeout=15000)
    assert _locuteur(atelier, rid) is None

    with page.expect_response(lambda r: r.url.endswith("/api/undo")
                              and r.request.method == "POST") as annulation:
        page.locator("body").press("Control+z")
    assert annulation.value.status == 200, annulation.value.text()
    expect(page.locator("#region-type")).to_have_value("bulle", timeout=15000)
    expect(page.locator("#loc-section")).to_be_visible(timeout=15000)
    expect(page.locator("#loc-current")).to_contain_text("Tintin", timeout=15000)
    assert _locuteur(atelier, rid)["id"] == atelier["tintin"]

# --------------------------------------------------------------------------- #
# Le changement de type, quand il ne se passe pas comme prévu
# --------------------------------------------------------------------------- #
# `$("#region-type").onchange` porte trois gardes, et le test ci-dessus n'en tenait
# aucune : il joue le cas où l'écriture réussit, sur la région qu'on n'a pas quittée, en
# mode Annotation. La relecture croisée les a retirées une à une sans rien faire tomber
# (2026-10-12), puis a rejoué ce que l'écran devient :
#
#   - sans « resté sur la région » : l'écriture du type encore en vol, on sélectionne un
#     cartouche, la réponse arrive — et c'est le bloc « Situation » de l'AUTRE région qui
#     s'affiche sous le cartouche ;
#   - les blocs relus dans la liste déroulante et non dans l'état : après une écriture
#     refusée, « Situation » s'affiche sur une région restée bulle ;
#   - sans la garde du mode : rien ne change à l'écran, des lectures partent pour un
#     panneau qu'on ne voit pas.
#
# Les deux premiers s'éprouvent par la VISIBILITÉ des blocs, après un témoin qui dit que
# l'écran a bien reçu la réponse — sans lui, « rien n'a bougé » passerait sur un écran qui
# n'a encore rien traité.
def _noeud(page, rid):
    """Le nœud de l'arbre de structure qui porte cette région."""
    return page.locator(".tnode", has=page.locator(".tn-id", has_text=re.compile(rf"^#{rid}$")))


def _type_en_base(decor, rid):
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30) as c:
        regions = c.get(f"/api/planches/{decor['planche']}/regions").json()
    return next(r["type"] for r in regions if r["id"] == rid)


def test_une_ecriture_du_type_en_vol_ne_derange_pas_la_region_ou_l_on_est_parti(page, atelier):
    """On change le type d'une bulle, on part sur un cartouche AVANT la réponse : quand elle
    arrive, le panneau montre toujours les blocs du cartouche."""
    bulle, cartouche = atelier["bulle"], atelier["cartouche"]
    _ouvrir(page, atelier, "bulle")
    bloc, situation = page.locator("#loc-section"), page.locator("#situation-section")
    liste = page.locator("#region-type")
    expect(bloc).to_be_visible(timeout=15000)

    # L'écriture du type est TENUE : le serveur « ne répond pas » tant qu'on ne la relâche pas.
    tenues = []

    def tenir(route):
        if route.request.method == "PUT":
            tenues.append(route)
        else:
            route.continue_()
    page.route(re.compile(rf"/api/regions/{bulle}$"), tenir)
    liste.select_option("case")
    for _ in range(150):                 # les gestionnaires ne tournent que PENDANT un appel
        if tenues:
            break
        page.wait_for_timeout(100)
    assert len(tenues) == 1, "l'écriture du type n'est pas partie : rien à tenir en vol"

    # On part sur le cartouche, la requête toujours en vol.
    _noeud(page, cartouche).click()
    expect(liste).to_have_value("cartouche", timeout=15000)
    expect(bloc).to_be_visible(timeout=15000)
    expect(page.locator("#loc-input")).to_have_accessible_name(re.compile("cartouche"))
    expect(situation).to_be_hidden()

    with page.expect_response(_est("PUT", f"/api/regions/{bulle}")) as reponse:
        tenues[0].continue_()
    assert reponse.value.status == 200, reponse.value.text()
    # Le témoin : l'écran a REÇU la réponse — l'arbre range désormais la région en case.
    expect(_noeud(page, bulle)).to_have_class(re.compile(r"\btnode-case\b"), timeout=15000)
    assert _type_en_base(atelier, bulle) == "case"

    # La région où l'on est garde SES blocs : ceux d'un cartouche, pas ceux de la case.
    expect(liste).to_have_value("cartouche")
    expect(bloc).to_be_visible()
    expect(situation).to_be_hidden()


def test_une_ecriture_du_type_refusee_laisse_a_la_region_les_blocs_de_son_type(page, atelier):
    """Le serveur refuse le changement de type : la région est restée une bulle, et c'est le
    bloc « Locuteur » qu'on lui offre — pas « Situation », que la liste déroulante annonce.

    La liste, elle, reste sur le type demandé : c'est antérieur à ce chantier et ce test ne
    l'affirme pas. Il affirme ce qui est neuf — les blocs se relisent dans l'état.
    """
    bulle = atelier["bulle"]
    _ouvrir(page, atelier, "bulle")
    bloc, situation = page.locator("#loc-section"), page.locator("#situation-section")
    expect(bloc).to_be_visible(timeout=15000)

    def refuser(route):
        if route.request.method == "PUT":
            route.fulfill(status=403, content_type="application/json",
                          body=json.dumps({"detail": "Refusé pour le test."}))
        else:
            route.continue_()
    page.route(re.compile(rf"/api/regions/{bulle}$"), refuser)
    with page.expect_response(_est("PUT", f"/api/regions/{bulle}")) as reponse:
        page.locator("#region-type").select_option("case")
    assert reponse.value.status == 403
    # Le témoin : l'écran a TRAITÉ le refus — il le dit.
    expect(page.locator("#toasts .toast", has_text="Refusé pour le test")).to_be_visible(timeout=15000)
    assert _type_en_base(atelier, bulle) == "bulle"

    expect(bloc).to_be_visible()
    expect(situation).to_be_hidden()
    expect(page.locator("#loc-input")).to_have_accessible_name(re.compile("bulle"))


def test_hors_du_mode_annotation_changer_le_type_ne_lit_aucun_bloc(page, atelier):
    """La troisième garde ne se voit pas : en mode Édition le panneau d'annotation est
    caché, donc relire ses blocs ne change rien à l'écran. Ce qu'on peut mesurer, c'est ce
    qui PART — aucune lecture de locuteur, de présence ni de situation —, et que le bon bloc
    attend quand on entre en Annotation."""
    bulle = atelier["bulle"]
    page.goto(f"{atelier['base']}/?album={atelier['album']}&planche={atelier['planche']}"
              f"&region={bulle}", wait_until="networkidle")
    expect(page.locator("#region-type")).to_have_value("bulle", timeout=15000)
    page.locator('button[data-mode="edition"]').click()
    expect(page.locator("#panel-edition")).to_be_visible(timeout=15000)
    expect(page.locator("#panel-annotation")).to_be_hidden()

    lues = []
    motif = re.compile(r"/api/regions/\d+/(locuteur|personnage|attributs)$")
    page.on("request", lambda r: lues.append(r.url) if r.method == "GET" and motif.search(r.url) else None)
    with page.expect_response(_est("PUT", f"/api/regions/{bulle}")) as reponse:
        page.locator("#region-type").select_option("cartouche")
    assert reponse.value.status == 200, reponse.value.text()
    expect(_noeud(page, bulle)).to_have_class(re.compile(r"\btnode-cartouche\b"), timeout=15000)
    page.wait_for_timeout(300)
    assert lues == [], f"des blocs d'annotation ont été lus hors du mode Annotation : {lues}"

    page.locator('button[data-mode="annotation"]').click()
    expect(page.locator("#loc-section")).to_be_visible(timeout=15000)
    expect(page.locator("#loc-input")).to_have_accessible_name(re.compile("cartouche"))


# --------------------------------------------------------------------------- #
# La Situation d'une case : la phrase qui dit la syntaxe attendue
# --------------------------------------------------------------------------- #
# Ce que la sonde de reflow ne dit pas : elle demande si un élément SORT de la fenêtre.
# La phrase doit tenir dans SON tiroir — entre les marges du panneau —, et ne pas être
# rognée par sa propre boîte.
_OU_EST_LA_PHRASE = """([selecteurAide, selecteurChamp]) => {
  const aide = document.querySelector(selecteurAide);
  const panneau = document.querySelector('#panel');
  const st = getComputedStyle(panneau);
  const a = aide.getBoundingClientRect(), p = panneau.getBoundingClientRect();
  const champ = document.querySelector(selecteurChamp).getBoundingClientRect();
  return {
    fenetre: document.documentElement.clientWidth,
    racine: getComputedStyle(document.documentElement).fontSize,
    gauche: a.left, droite: a.right, haut: a.top, hauteur: a.height,
    // La boîte de CONTENU du tiroir : sa bordure gauche (`clientLeft`) et ses marges
    // intérieures retirées ; `clientWidth` a déjà retiré une éventuelle barre de défilement.
    interieurGauche: p.left + panneau.clientLeft + parseFloat(st.paddingLeft),
    interieurDroit: p.left + panneau.clientLeft + panneau.clientWidth - parseFloat(st.paddingRight),
    rognee: aide.scrollWidth > aide.clientWidth + 1,
    basDuChamp: champ.bottom,
    lignes: Math.round(a.height / parseFloat(getComputedStyle(aide).lineHeight)),
  };
}"""


def _attributs(decor, rid):
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30) as c:
        return [(a["dimension"], a["valeur"]) for a in c.get(f"/api/regions/{rid}/attributs").json()]


def test_la_phrase_de_situation_se_lit_sous_le_champ_d_une_case(page, atelier):
    """Sur une case, en mode Annotation, la phrase est VISIBLE sous le champ « Situation »,
    et un lecteur d'écran la reçoit comme la description du champ.

    La visibilité s'éprouve AVANT le texte : `to_have_text()` et `to_contain_text()` lisent
    aussi un élément caché, et la section entière naît `hidden` — un test du seul texte
    passerait sur une phrase qu'on ne voit jamais.
    """
    _ouvrir(page, atelier, "case")
    champ, aide = page.locator("#sit-input"), page.locator("#sit-aide")
    expect(champ).to_be_visible(timeout=15000)
    expect(aide).to_be_visible()
    # Les deux moitiés de la consigne : la forme attendue, et un exemple qui la suit.
    expect(aide).to_contain_text(re.compile(r"dimension\s:\svaleur"))
    expect(aide.locator(".attr-exemple")).to_be_visible()
    expect(aide.locator(".attr-exemple")).to_have_text(re.compile(r"^\S+\s:\s\S+$"))
    # Reliée au champ : c'est ce qu'un lecteur d'écran annonce après son nom.
    expect(champ).to_have_accessible_description(re.compile(r"dimension\s:\svaleur"))
    m = page.evaluate(_OU_EST_LA_PHRASE, ["#sit-aide", "#sit-input"])
    assert m["haut"] >= m["basDuChamp"] - 1, f"la phrase n'est pas SOUS le champ : {m}"


@pytest.mark.parametrize("type_zone", ["bulle", "personnage"])
def test_la_phrase_de_situation_ne_se_montre_que_pour_une_case(page, atelier, type_zone):
    """Elle appartient au bloc « Situation » : hors d'une case, elle disparaît avec lui —
    et le témoin de chargement passe d'abord, comme pour le bloc Locuteur."""
    _ouvrir(page, atelier, type_zone)
    temoin = "#loc-section" if type_zone == "bulle" else TEMOIN[type_zone]
    expect(page.locator(temoin)).to_be_visible(timeout=15000)
    expect(page.locator("#sit-aide")).to_be_hidden()


def test_l_exemple_de_la_phrase_tape_tel_quel_s_enregistre(page, atelier):
    """La phrase ne vaut que si son exemple MARCHE. Il est lu à l'écran, tapé comme on le
    lit, et le geste est attendu en tant que requête : créer l'axe, créer la valeur, la
    poser sur la case."""
    rid = atelier["case"]
    _ouvrir(page, atelier, "case")
    champ = page.locator("#sit-input")
    expect(page.locator("#sit-aide")).to_be_visible(timeout=15000)
    # Ce qu'on tape au clavier : l'exemple, avec des espaces ordinaires.
    exemple = " ".join(page.locator("#sit-aide .attr-exemple").inner_text().split())
    dimension, _, valeur = (morceau.strip() for morceau in exemple.partition(":"))
    assert dimension and valeur, f"l'exemple « {exemple} » ne suit pas la syntaxe qu'il illustre"

    champ.click()
    champ.press_sequentially(exemple, delay=20)
    expect(page.locator("#sit-suggest div", has_text=valeur)).to_be_visible(timeout=15000)
    with page.expect_request(_est("POST", "/api/attributs/dimensions")) as axe, \
            page.expect_request(_est("PUT", f"/api/regions/{rid}/attributs")), \
            page.expect_response(_est("PUT", f"/api/regions/{rid}/attributs")) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    assert axe.value.post_data_json == {"cible": "case", "nom": dimension}
    puce = page.locator("#sit-current .tag-chip")
    expect(puce).to_be_visible(timeout=15000)
    expect(puce).to_contain_text(valeur)
    assert _attributs(atelier, rid) == [(dimension, valeur)]
    # La phrase reste sous le champ une fois la valeur posée : elle sert à la suivante.
    expect(page.locator("#sit-aide")).to_be_visible()


def test_la_phrase_tient_dans_le_tiroir_a_320_px_sous_une_police_de_24(page, atelier):
    """Le cas le plus étroit que le dépôt mesure : 320 px de large, police par défaut du
    navigateur portée à 24. Le panneau est alors un tiroir, et la phrase doit s'y replier
    sans en sortir ni être rognée.

    Même garde d'amont que `test_e2e_police` : la racine doit avoir suivi la préférence,
    sans quoi l'assertion du bas mesurerait la police ordinaire.
    """
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": 24, "fixed": 24}})
    page.set_viewport_size({"width": 320, "height": 900})
    _ouvrir(page, atelier, "case")
    bascule = page.locator("#btn-tiroir-panneau")
    expect(bascule).to_be_visible(timeout=15000)       # sous le seuil : le panneau est un tiroir
    if bascule.get_attribute("aria-expanded") != "true":
        bascule.click()
    expect(bascule).to_have_attribute("aria-expanded", "true")
    aide = page.locator("#sit-aide")
    aide.scroll_into_view_if_needed()
    expect(aide).to_be_visible()
    expect(aide).to_be_in_viewport(ratio=1)             # entière à l'écran, pas seulement posée
    page.wait_for_timeout(400)                          # la glissière du tiroir a fini

    m = page.evaluate(_OU_EST_LA_PHRASE, ["#sit-aide", "#sit-input"])
    assert m["fenetre"] == 320 and m["racine"] == "19.5px", (
        f"fenêtre de {m['fenetre']} px, racine à {m['racine']} : la préférence de police "
        "n'a pas été appliquée, et ce qui suit ne mesurerait pas le cas annoncé")
    assert m["gauche"] >= m["interieurGauche"] - 1 and m["droite"] <= m["interieurDroit"] + 1, (
        f"la phrase sort des marges du tiroir : elle va de {m['gauche']:.1f} à "
        f"{m['droite']:.1f} px, le tiroir offre {m['interieurGauche']:.1f} à "
        f"{m['interieurDroit']:.1f}")
    assert not m["rognee"], f"la phrase est rognée par sa propre boîte : {m}"
    # Elle s'est REPLIÉE : sur une seule ligne, c'est qu'elle n'a pas été mesurée à l'étroit.
    assert m["lignes"] >= 2, f"la phrase tient en {m['lignes']} ligne à 320 px sous police 24 ?"


# --------------------------------------------------------------------------- #
# Le profil d'un personnage : la même phrase, sous ses deux champs
# --------------------------------------------------------------------------- #
# Deux blocs du gabarit pour un même profil : `#perso-attr-*` s'offre sous le locuteur
# d'une zone de texte, `#perso-profil-*` sous l'identité d'une boîte personnage. Chacun a
# SA phrase, sous un identifiant à lui — un identifiant partagé ne décrirait qu'un des
# deux champs, et l'autre resterait muet pour un lecteur d'écran.
PROFILS = {
    "par-le-locuteur": {"zone": "bulle", "lien": "locuteur", "bloc": "#loc-section",
                        "aide": "#perso-attr-aide", "champ": "#perso-attr-input",
                        "liste": "#perso-attr-suggest", "courant": "#perso-attr-current"},
    "par-la-boite": {"zone": "personnage", "lien": "personnage", "bloc": "#perso-section",
                     "aide": "#perso-profil-aide", "champ": "#perso-profil-input",
                     "liste": "#perso-profil-suggest", "courant": "#perso-profil-current"},
}


def _identifier(decor, p):
    """Tintin parle dans la bulle, ou est montré dans la boîte : le champ de profil ne
    s'offre qu'à un personnage désigné."""
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        rep = c.put(f"/api/regions/{decor[p['zone']]}/{p['lien']}",
                    json={"personnage_id": decor["tintin"]})
    assert rep.status_code == 200, rep.text


def _profil(decor):
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30) as c:
        return [(a["dimension"], a["valeur"])
                for a in c.get(f"/api/personnages/{decor['tintin']}/attributs").json()]


@pytest.mark.parametrize("profil", list(PROFILS))
def test_la_phrase_de_profil_se_lit_sous_le_champ(page, atelier, profil):
    """Sous chacun des deux champs de profil, la phrase est VISIBLE, et un lecteur d'écran
    la reçoit comme la description de CE champ. Visibilité avant texte, comme pour
    « Situation » : le bloc naît caché."""
    p = PROFILS[profil]
    _identifier(atelier, p)
    _ouvrir(page, atelier, p["zone"])
    champ, aide = page.locator(p["champ"]), page.locator(p["aide"])
    expect(champ).to_be_visible(timeout=15000)
    expect(aide).to_be_visible()
    expect(aide).to_contain_text(re.compile(r"dimension\s:\svaleur"))
    expect(aide.locator(".attr-exemple")).to_be_visible()
    expect(aide.locator(".attr-exemple")).to_have_text(re.compile(r"^\S+\s:\s\S+$"))
    expect(champ).to_have_accessible_description(re.compile(r"dimension\s:\svaleur"))
    # L'exemple est celui d'un PROFIL : la description du champ ne cite pas un lieu.
    expect(champ).not_to_have_accessible_description(re.compile("falaise"))
    m = page.evaluate(_OU_EST_LA_PHRASE, [p["aide"], p["champ"]])
    assert m["haut"] >= m["basDuChamp"] - 1, f"la phrase n'est pas SOUS le champ : {m}"
    # L'autre bloc de profil n'est pas à l'écran : sa phrase non plus.
    autre = next(q for nom, q in PROFILS.items() if nom != profil)
    expect(page.locator(autre["aide"])).to_be_hidden()


@pytest.mark.parametrize("profil", list(PROFILS))
def test_la_phrase_de_profil_ne_se_montre_qu_avec_son_champ(page, atelier, profil):
    """Sans personnage désigné, pas de champ de profil — et pas de phrase. Le témoin de
    chargement passe d'abord : le bloc qui porterait le profil est là, et il dit qu'il n'y
    a personne."""
    p = PROFILS[profil]
    _ouvrir(page, atelier, p["zone"])
    expect(page.locator(p["bloc"])).to_be_visible(timeout=15000)
    expect(page.locator(p["bloc"])).to_contain_text(
        "Aucun locuteur" if p["lien"] == "locuteur" else "Non identifié", timeout=15000)
    expect(page.locator(p["champ"])).to_be_hidden()
    expect(page.locator(p["aide"])).to_be_hidden()


@pytest.mark.parametrize("profil", list(PROFILS))
def test_l_exemple_de_la_phrase_de_profil_tape_tel_quel_s_enregistre(page, atelier, profil):
    """L'exemple de la phrase, lu à l'écran et tapé comme on le lit, s'enregistre au
    profil du personnage : créer l'axe (de cible « personnage »), créer la valeur, la poser."""
    p = PROFILS[profil]
    chemin = f"/api/personnages/{atelier['tintin']}/attributs"
    _identifier(atelier, p)
    _ouvrir(page, atelier, p["zone"])
    champ = page.locator(p["champ"])
    expect(page.locator(p["aide"])).to_be_visible(timeout=15000)
    exemple = " ".join(page.locator(f"{p['aide']} .attr-exemple").inner_text().split())
    dimension, _, valeur = (morceau.strip() for morceau in exemple.partition(":"))
    assert dimension and valeur, f"l'exemple « {exemple} » ne suit pas la syntaxe qu'il illustre"

    champ.click()
    champ.press_sequentially(exemple, delay=20)
    expect(page.locator(f"{p['liste']} div", has_text=valeur)).to_be_visible(timeout=15000)
    with page.expect_request(_est("POST", "/api/attributs/dimensions")) as axe, \
            page.expect_request(_est("PUT", chemin)), \
            page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    assert axe.value.post_data_json == {"cible": "personnage", "nom": dimension}
    puce = page.locator(f"{p['courant']} .tag-chip")
    expect(puce).to_be_visible(timeout=15000)
    expect(puce).to_contain_text(valeur)
    assert _profil(atelier) == [(dimension, valeur)]
    expect(page.locator(p["aide"])).to_be_visible()


@pytest.mark.parametrize("profil", list(PROFILS))
def test_la_phrase_de_profil_tient_dans_le_tiroir_a_320_px_sous_une_police_de_24(
        page, atelier, profil):
    """Le même cas étroit que pour « Situation », sur chacune des deux phrases : elles ne
    sont pas dans le même bloc, et celle du locuteur est un cran plus bas dans le tiroir."""
    p = PROFILS[profil]
    _identifier(atelier, p)
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": 24, "fixed": 24}})
    page.set_viewport_size({"width": 320, "height": 900})
    _ouvrir(page, atelier, p["zone"])
    bascule = page.locator("#btn-tiroir-panneau")
    expect(bascule).to_be_visible(timeout=15000)
    if bascule.get_attribute("aria-expanded") != "true":
        bascule.click()
    expect(bascule).to_have_attribute("aria-expanded", "true")
    aide = page.locator(p["aide"])
    aide.scroll_into_view_if_needed()
    expect(aide).to_be_visible()
    expect(aide).to_be_in_viewport(ratio=1)
    page.wait_for_timeout(400)                          # la glissière du tiroir a fini

    m = page.evaluate(_OU_EST_LA_PHRASE, [p["aide"], p["champ"]])
    assert m["fenetre"] == 320 and m["racine"] == "19.5px", (
        f"fenêtre de {m['fenetre']} px, racine à {m['racine']} : la préférence de police "
        "n'a pas été appliquée, et ce qui suit ne mesurerait pas le cas annoncé")
    assert m["gauche"] >= m["interieurGauche"] - 1 and m["droite"] <= m["interieurDroit"] + 1, (
        f"la phrase sort des marges du tiroir : elle va de {m['gauche']:.1f} à "
        f"{m['droite']:.1f} px, le tiroir offre {m['interieurGauche']:.1f} à "
        f"{m['interieurDroit']:.1f}")
    assert not m["rognee"], f"la phrase est rognée par sa propre boîte : {m}"
    assert m["lignes"] >= 2, f"la phrase tient en {m['lignes']} ligne à 320 px sous police 24 ?"
    # L'exemple ne se coupe pas : il tient sur UNE ligne, entre les mêmes marges.
    e = page.evaluate("""(s) => { const b = document.querySelector(s).getBoundingClientRect();
        return { gauche: b.left, droite: b.right, hauteur: b.height,
                 ligne: parseFloat(getComputedStyle(document.querySelector(s)).lineHeight) }; }""",
                      f"{p['aide']} .attr-exemple")
    assert e["gauche"] >= m["interieurGauche"] - 1 and e["droite"] <= m["interieurDroit"] + 1, e
    assert e["hauteur"] < 1.5 * e["ligne"], f"l'exemple « registre : familier » s'est coupé : {e}"


# --------------------------------------------------------------------------- #
# ANN-8 — à 320 px sous une police de 24, aucun champ ne dépasse du tiroir
# --------------------------------------------------------------------------- #
# Mesuré dans l'image avant le correctif : le champ « dimension : valeur » allait jusqu'à
# 326,6 px et le tiroir défilait en largeur ; sur le poste il s'arrêtait à 318,6 px. Ces
# champs n'avaient aucune largeur écrite : un champ texte prend celle de vingt caractères
# de SA police, et la police de l'image est plus large. Le test se joue donc deux fois —
# sous la police du navigateur, puis sous une chasse FORCÉE plus large que toutes celles
# qu'on connaît —, pour que la borne se mesure là où on la lance, et pas seulement là où
# la police a de la marge.
_CHAMPS_DU_TIROIR = """() => {
  const panneau = document.querySelector('#panel');
  const st = getComputedStyle(panneau), p = panneau.getBoundingClientRect();
  const droit = p.left + panneau.clientLeft + panneau.clientWidth - parseFloat(st.paddingRight);
  const champs = [...panneau.querySelectorAll('.tag-input-wrap > input')]
    .filter((c) => c.getClientRects().length)
    .map((c) => ({ id: c.id, droite: c.getBoundingClientRect().right }));
  return { fenetre: document.documentElement.clientWidth,
           racine: getComputedStyle(document.documentElement).fontSize,
           interieurDroit: droit, champs,
           defile: panneau.scrollWidth > panneau.clientWidth + 1 };
}"""

# Posée par le CSSOM, élément par élément : une feuille `<style>` injectée serait refusée
# par la CSP (`style-src-elem 'self'`), et le test mesurerait la police d'origine.
_CHASSE_LARGE = """() => document.querySelectorAll('#panel .tag-input-wrap > input')
  .forEach((c) => { c.style.font = "22px 'Courier New', monospace"; })"""


@pytest.mark.parametrize("chasse", ["navigateur", "large"])
@pytest.mark.parametrize("type_zone", ["case", "bulle", "personnage"])
def test_aucun_champ_ne_depasse_du_tiroir_a_320_px_sous_une_police_de_24(
        page, atelier, type_zone, chasse):
    with httpx.Client(base_url=atelier["base"], trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        for zone, lien in (("bulle", "locuteur"), ("personnage", "personnage")):
            rep = c.put(f"/api/regions/{atelier[zone]}/{lien}",
                        json={"personnage_id": atelier["tintin"]})
            assert rep.status_code == 200, rep.text
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": 24, "fixed": 24}})
    page.set_viewport_size({"width": 320, "height": 900})
    _ouvrir(page, atelier, type_zone)
    bascule = page.locator("#btn-tiroir-panneau")
    expect(bascule).to_be_visible(timeout=15000)
    if bascule.get_attribute("aria-expanded") != "true":
        bascule.click()
    expect(bascule).to_have_attribute("aria-expanded", "true")
    # Le profil du personnage n'est offert qu'une fois le lien lu : on l'attend.
    temoin = {"case": "#sit-input", "bulle": "#perso-attr-input",
              "personnage": "#perso-profil-input"}[type_zone]
    expect(page.locator(temoin)).to_be_visible(timeout=15000)
    if chasse == "large":
        page.evaluate(_CHASSE_LARGE)
    page.wait_for_timeout(400)                          # la glissière du tiroir a fini

    m = page.evaluate(_CHAMPS_DU_TIROIR)
    assert m["fenetre"] == 320 and m["racine"] == "19.5px", (
        f"fenêtre de {m['fenetre']} px, racine à {m['racine']} : la préférence de police "
        "n'a pas été appliquée, et ce qui suit ne mesurerait pas le cas annoncé")
    assert temoin.lstrip("#") in [ch["id"] for ch in m["champs"]], m
    trop = [ch for ch in m["champs"] if ch["droite"] > m["interieurDroit"] + 1]
    assert not trop, (f"champ(s) hors du tiroir ({chasse}) : {trop}, le tiroir s'arrête à "
                      f"{m['interieurDroit']:.1f} px")
    assert not m["defile"], f"le tiroir défile en largeur ({chasse}) : {m}"
