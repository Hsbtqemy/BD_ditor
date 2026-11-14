"""Le locuteur dans le Contexte de la page Annotation, au plus près du geste (ANN-6, CONC-4).

Ces gardes vivaient dans le panneau d'annotation de l'Atelier (`test_e2e_atelier_annotation.py`
pour le locuteur, `test_e2e_conflit_a_deux.py` pour ses conflits, `test_e2e_planche_changee.py`
pour « Actualiser »). Le basculement d'ANN-7 a retiré ce panneau : le locuteur ne s'écrit plus
que dans la page Annotation, et ce qu'elles tenaient doit tenir là — un retour d'usage de la
production (« on ne peut pas attribuer un locuteur à un cartouche », 2026-10-12) ne doit pas
revenir par la porte qui reste.

- **Le champ s'offre aux trois zones de texte et à elles seules**, et le serveur accepte
  exactement ce que l'écran offre — « caché » ne s'affirme qu'après un témoin que le Contexte
  de la zone s'est lu.
- **Le geste PART** : la requête d'attribution est attendue en tant que requête, avec son
  corps et la valeur vue, et pas seulement l'état final.
- **Un retrait sur une valeur périmée** ouvre le bandeau, et « Garder l'autre » montre la
  version de l'autre ; **deux choix coup sur coup** partent l'un après l'autre, le second
  déclarant le premier ; **« Actualiser »** garde le nom à moitié tapé.

L'autre écran est simulé par l'API, comme dans `test_e2e_annotation_page.py` : ce qu'on juge
est ce que CET écran envoie et montre.
"""
import json
import re
import time

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, TYPES_MUETS, TYPES_PARLANTS, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/annotation",)
SURFACES_HORS_PERIMETRE = {
    "/": ("l'Atelier n'attribue plus de locuteur depuis le basculement d'ANN-7 : son mode "
          "Annotation est parti, et « Annoter ↗ » mène ici"),
    "/recherche": "la Recherche filtre par locuteur, elle n'en attribue pas",
    "/corpus": "la Bibliothèque range des albums et des planches",
    "/exploration": "l'Exploration compte par locuteur, elle n'en attribue pas",
    "/administration": "rien n'y porte sur une région d'une planche",
}

# Ce que le nom accessible du champ doit NOMMER, type par type. Le libellé entier n'est pas
# verrouillé — seulement la propriété qui manquait : il disait « à la bulle » devant un
# cartouche.
MOT = {"bulle": "bulle", "cartouche": "cartouche", "texte": "texte"}


@pytest.fixture
def decor(live_server):
    """Une planche, une case, et sous elle une région de CHAQUE type — plus deux personnages
    déjà au registre, pour changer de locuteur sans en créer un second à la volée."""
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        aid = c.post("/api/albums", json={"titre": "E2E locuteur"}).json()["id"]
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
        d = {"base": live_server, "album": aid, "planche": pid, "case": case,
             "bulle": region("bulle", 60, 60, case),
             "cartouche": region("cartouche", 60, 300, case),
             "texte": region("texte", 400, 60, case),
             "personnage": region("personnage", 400, 300, case),
             "detail": region("detail", 400, 520, case),
             "tintin": c.post("/api/personnages", json={"nom": "Tintin"}).json()["id"],
             "haddock": c.post("/api/personnages", json={"nom": "Haddock"}).json()["id"]}
    assert set(TYPES_PARLANTS) | set(TYPES_MUETS) <= set(d), (
        "le décor ne porte pas une région de chaque type : un test paramétré sur un type "
        "absent lèverait un KeyError qui se lirait comme une panne de l'écran")
    return d


def _http(d):
    return httpx.Client(base_url=d["base"], trust_env=False, timeout=30, headers=ECRITURE)


def _ouvrir(page, d, type_zone):
    page.goto(f"{d['base']}/annotation?album={d['album']}&planche={d['planche']}"
              f"&region={d[type_zone]}", wait_until="networkidle")
    # La zone est bien celle qu'on croit, et son Contexte s'est lu (la note se rend) : sans ce
    # témoin, « le locuteur est caché » passerait sur une page qui n'a encore rien décidé.
    # Le bouton de la case elle-même ne porte pas d'identifiant (`data-zone` vide).
    zone = "" if type_zone == "case" else d[type_zone]
    expect(page.locator(f'#an-zones .an-zone-btn[data-zone="{zone}"]')).to_have_attribute(
        "aria-pressed", "true", timeout=15000)
    expect(page.locator("#an-ctx-note")).to_be_visible(timeout=15000)
    page.wait_for_function("() => !document.querySelector('#an-note').disabled", timeout=15000)


def _locuteur(d, rid):
    with _http(d) as c:
        return c.get(f"/api/regions/{rid}/locuteur").json()["locuteur"]


def _est(methode, chemin):
    """Prédicat de requête OU de réponse : cette méthode, sur ce chemin exact."""
    def predicat(objet):
        requete = getattr(objet, "request", objet)
        return requete.method == methode and requete.url.endswith(chemin)
    return predicat


def _choisir(page, nom):
    champ = page.locator("#an-loc-input")
    champ.click()
    champ.fill(nom)
    expect(page.locator("#an-loc-liste")).to_contain_text(nom, timeout=15000)
    champ.press("Enter")


@pytest.mark.parametrize("type_zone", TYPES_PARLANTS + TYPES_MUETS)
def test_le_locuteur_s_offre_aux_zones_de_texte_et_a_elles_seules(page, decor, type_zone):
    """Le champ s'affiche pour une bulle, un cartouche, une zone de texte — et le serveur
    accepte exactement ce que l'écran offre."""
    _ouvrir(page, decor, type_zone)
    ligne, champ = page.locator("#an-ctx-loc"), page.locator("#an-loc-input")
    if type_zone in TYPES_PARLANTS:
        expect(ligne).to_be_visible()
        expect(champ).to_be_visible()
        # Le champ se NOMME d'après la zone qu'on a sous les yeux, pas d'après une autre.
        expect(champ).to_have_accessible_name(re.compile(MOT[type_zone]))
        for autre in set(MOT.values()) - {MOT[type_zone]}:
            expect(champ).not_to_have_accessible_name(re.compile(autre))
    else:
        expect(ligne).to_be_hidden()

    # L'accord, mesuré : ce que l'écran n'offre pas, le serveur le refuse — et l'inverse.
    with _http(decor) as c:
        rep = c.put(f"/api/regions/{decor[type_zone]}/locuteur",
                    json={"personnage_id": decor["tintin"]})
    assert (rep.status_code == 200) == ligne.is_visible(), (
        f"pour une région « {type_zone} », l'écran {'offre' if ligne.is_visible() else 'cache'} "
        f"le locuteur et le serveur répond {rep.status_code} : les deux ne tiennent plus la "
        "même règle")
    assert rep.status_code == (200 if type_zone in TYPES_PARLANTS else 422), rep.text


@pytest.mark.parametrize("type_zone", TYPES_PARLANTS)
def test_attribuer_changer_retirer_un_locuteur_puis_annuler(page, decor, type_zone):
    """Le parcours d'une bulle, joué sur les trois types : créer le personnage à la volée,
    en changer, le retirer, et Ctrl+Z deux fois."""
    rid = decor[type_zone]
    chemin = f"/api/regions/{rid}/locuteur"
    _ouvrir(page, decor, type_zone)
    champ, puce = page.locator("#an-loc-input"), page.locator("#an-loc-nom")
    expect(puce).to_have_text("")

    # ATTRIBUER, en créant le personnage à la volée.
    champ.click()
    champ.press_sequentially("Narrateur", delay=20)
    expect(page.locator("#an-loc-liste div", has_text="Créer")).to_be_visible(timeout=15000)
    with page.expect_request(_est("POST", "/api/personnages")), \
            page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    narrateur = envoi.value.post_data_json["personnage_id"]
    expect(puce).to_have_text("Narrateur", timeout=15000)
    assert _locuteur(decor, rid) == {"id": narrateur, "nom": "Narrateur", "serie": None}

    # CHANGER, pour un personnage déjà au registre — proposé, pas créé une seconde fois.
    champ.click()
    champ.press_sequentially("Tintin", delay=20)
    expect(page.locator("#an-loc-liste div", has_text="Tintin").first).to_be_visible(timeout=15000)
    expect(page.locator("#an-loc-liste div", has_text="Créer")).to_have_count(0)
    with page.expect_request(_est("PUT", chemin)) as envoi:
        champ.press("Enter")
    # CONC-4 : le changement déclare le locuteur que l'écran voyait — le Narrateur.
    assert envoi.value.post_data_json == {"personnage_id": decor["tintin"],
                                          "personnage_vu": narrateur}
    expect(puce).to_have_text("Tintin", timeout=15000)
    assert _locuteur(decor, rid)["id"] == decor["tintin"]

    # RETIRER — en déclarant le locuteur que l'écran voyait (CONC-4).
    with page.expect_response(_est("DELETE", f"{chemin}?personnage_vu={decor['tintin']}")) \
            as reponse:
        page.locator("#an-loc-retirer").click()
    assert reponse.value.status == 204
    expect(puce).to_have_text("", timeout=15000)
    assert _locuteur(decor, rid) is None

    # ANNULER, deux fois, hors champ de saisie : le retrait d'abord, le changement ensuite.
    # La première annulation d'un serveur neuf peut charger spaCy à froid : la RÉPONSE est
    # attendue, et longtemps (cf. l'historique de ce test dans l'Atelier).
    page.locator(f'#an-zones .an-zone-btn[data-zone="{rid}"]').focus()
    with page.expect_response(_est("POST", "/api/undo"), timeout=180000) as annulation:
        page.keyboard.press("Control+z")
    assert annulation.value.status == 200, annulation.value.text()
    assert annulation.value.json()["acte"] == "delien", annulation.value.json()
    expect(puce).to_have_text("Tintin", timeout=15000)
    assert _locuteur(decor, rid)["id"] == decor["tintin"]
    page.locator(f'#an-zones .an-zone-btn[data-zone="{rid}"]').focus()
    with page.expect_response(_est("POST", "/api/undo"), timeout=180000) as annulation:
        page.keyboard.press("Control+z")
    assert annulation.value.status == 200, annulation.value.text()
    assert annulation.value.json()["acte"] == "lien", annulation.value.json()
    expect(puce).to_have_text("Narrateur", timeout=15000)
    assert _locuteur(decor, rid)["id"] == narrateur


def test_un_retrait_perime_ouvre_le_bandeau_et_garder_l_autre_montre_sa_version(page, decor):
    """La moitié « retrait » de la mesure du 2026-10-25 : l'écran voit Tintin ; un autre écran
    pose Haddock ; le ✕ ne retire pas Haddock — il est refusé, déclare ce qu'il voyait, et
    « Garder l'autre » montre Haddock."""
    rid = decor["bulle"]
    with _http(decor) as c:
        assert c.put(f"/api/regions/{rid}/locuteur",
                     json={"personnage_id": decor["tintin"]}).status_code == 200
    _ouvrir(page, decor, "bulle")
    expect(page.locator("#an-loc-nom")).to_have_text("Tintin")
    with _http(decor) as c:                        # un autre écran
        assert c.put(f"/api/regions/{rid}/locuteur",
                     json={"personnage_id": decor["haddock"]}).status_code == 200
    with page.expect_response(lambda r: r.request.method == "DELETE"
                              and f"/regions/{rid}/locuteur" in r.url) as rep:
        page.locator("#an-loc-retirer").click()
    assert rep.value.status == 409
    assert rep.value.url.endswith(f"?personnage_vu={decor['tintin']}")
    expect(page.locator("#an-cf-titre")).to_contain_text("Locuteur modifié")
    expect(page.locator("#an-guide-contenu")).to_contain_text("Votre retrait n'est pas enregistré.")
    expect(page.locator("#an-guide-contenu")).to_contain_text("Haddock")
    assert _locuteur(decor, rid)["id"] == decor["haddock"], "le retrait a emporté Haddock"
    page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    expect(page.locator("#an-loc-nom")).to_have_text("Haddock")
    assert _locuteur(decor, rid)["id"] == decor["haddock"]


def test_deux_choix_coup_sur_coup_ne_se_contredisent_pas(page, decor):
    """Relecture de CONC-4 : deux choix faits avant que le premier soit revenu partaient
    tous deux avec la valeur vue d'AVANT, et le second recevait un 409 contre soi-même. Ils
    partent l'un après l'autre : le second déclare le personnage du premier."""
    rid = decor["bulle"]
    _ouvrir(page, decor, "bulle")
    corps, tenues, libre = [], [], []

    def tenir(route):
        if route.request.method == "PUT":
            corps.append(json.loads(route.request.post_data))
            if not libre:
                tenues.append(route)
                return
        route.continue_()
    page.route(f"**/api/regions/{rid}/locuteur", tenir)
    _choisir(page, "Tintin")
    for _ in range(100):
        if tenues:
            break
        page.wait_for_timeout(100)
    assert tenues, "le premier choix n'est pas parti"
    _choisir(page, "Haddock")
    page.wait_for_timeout(500)
    assert len(corps) == 1, f"le second choix est parti sans attendre le premier : {corps}"
    libre.append(True)
    tenues[0].continue_()
    expect(page.locator("#an-loc-nom")).to_have_text("Haddock", timeout=15000)
    for _ in range(50):
        if _locuteur(decor, rid) and _locuteur(decor, rid)["id"] == decor["haddock"]:
            break
        page.wait_for_timeout(100)
    assert _locuteur(decor, rid)["id"] == decor["haddock"]
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    assert corps == [{"personnage_id": decor["tintin"], "personnage_vu": None},
                     {"personnage_id": decor["haddock"], "personnage_vu": decor["tintin"]}], corps


def test_actualiser_garde_le_nom_a_moitie_tape(page, decor):
    """Relecture de CONC-4 : « Actualiser » vidait le champ du locuteur, où l'on avait commencé
    de taper un nom. La saisie s'y garde."""
    _ouvrir(page, decor, "bulle")
    with _http(decor) as c:                        # un autre écran, sur une autre zone
        assert c.put(f"/api/regions/{decor['cartouche']}",
                     json={"ocr_texte": "AILLEURS"}).status_code == 200
    with page.expect_response(lambda r: r.url.endswith("/empreinte")):
        page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    bouton = page.locator("#an-actualiser")
    expect(bouton).to_be_visible()
    page.locator("#an-loc-input").click()
    page.keyboard.type("Hadd")
    with page.expect_response(lambda r: r.url.endswith(f"/regions/{decor['bulle']}/locuteur")):
        bouton.click()
    expect(bouton).to_be_hidden(timeout=15000)
    expect(page.locator("#an-loc-input")).to_have_value("Hadd")


# --------------------------------------------------------------------------- #
# Vu par la session en jouant la passe du locuteur (2026-11-14) : deux écrans
# --------------------------------------------------------------------------- #
def _autre_ecran(page, d, type_zone):
    ctx = page.context.browser.new_context(extra_http_headers=ECRITURE)
    autre = ctx.new_page()
    _ouvrir(autre, d, type_zone)
    return ctx, autre


def _choisir_dans(pg, champ, liste, nom):
    c = pg.locator(champ)
    c.click()
    c.fill(nom)
    expect(pg.locator(liste)).to_contain_text(nom, timeout=15000)
    c.press("Enter")


LIEUX = {"bulle": ("#an-loc-input", "#an-loc-liste", "#an-loc-nom", "locuteur"),
         "personnage": ("#an-perso-input", "#an-perso-liste", "#an-perso-nom", "personnage")}


def _conflit_a_deux_ecrans(page, d, type_zone):
    """L'écran voit Tintin ; un AUTRE écran (un second contexte) pose Haddock ; l'écran choisit
    Milou : 409, le bandeau du conflit s'ouvre. Rend le contexte de l'autre écran."""
    champ, liste, puce, route = LIEUX[type_zone]
    rid = d[type_zone]
    with _http(d) as c:
        assert c.put(f"/api/regions/{rid}/{route}",
                     json={"personnage_id": d["tintin"]}).status_code == 200
        if not any(p["nom"] == "Milou" for p in c.get("/api/personnages?q=Milou").json()):
            c.post("/api/personnages", json={"nom": "Milou"})
    _ouvrir(page, d, type_zone)
    expect(page.locator(puce)).to_have_text("Tintin")
    ctx, autre = _autre_ecran(page, d, type_zone)
    with autre.expect_response(lambda r: r.request.method == "PUT"
                               and r.url.endswith(f"/regions/{rid}/{route}")) as rep:
        _choisir_dans(autre, champ, liste, "Haddock")
    assert rep.value.status == 200, rep.value.text()
    with page.expect_response(lambda r: r.request.method == "PUT"
                              and r.url.endswith(f"/regions/{rid}/{route}")) as rep:
        _choisir_dans(page, champ, liste, "Milou")
    assert rep.value.status == 409, rep.value.text()
    expect(page.locator("#an-cf-mienne")).to_be_visible()
    return ctx


def _se_chevauchent(a, b):
    return not (a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"]
                or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"])


def test_le_message_qui_renvoie_au_bandeau_ne_couvre_pas_ses_boutons(page, decor):
    """Un conflit du locuteur ouvert, un autre choix dans la liste *Planche* : « Réglez d'abord
    le conflit, en bas de la grille. » se lit, et ne couvre ni « Remplacer par la mienne » ni
    « Garder l'autre » (vu à 1 280 px : il se posait exactement dessus)."""
    page.set_viewport_size({"width": 1280, "height": 720})
    with _http(decor) as c:
        seconde = c.post(f"/api/albums/{decor['album']}/import",
                         files={"file": ("p2.png", make_png(800, 1000), "image/png")}).json()["id"]
    ctx = _conflit_a_deux_ecrans(page, decor, "bulle")
    try:
        page.locator("#an-planche-choix").select_option(str(seconde))
        message = page.locator("#toasts .toast", has_text="Réglez d'abord le conflit")
        expect(message).to_be_visible()
        expect(page.locator("#an-planche-choix")).not_to_have_value(str(seconde))
        boite = message.bounding_box()
        for bouton in ("#an-cf-mienne", "#an-cf-autre"):
            b = page.locator(bouton)
            expect(b).to_be_visible()
            assert not _se_chevauchent(boite, b.bounding_box()), (bouton, boite, b.bounding_box())
    finally:
        ctx.close()


@pytest.mark.parametrize("geste", ["#an-cf-mienne", "#an-cf-autre"])
@pytest.mark.parametrize("type_zone", ["bulle", "personnage"])
def test_apres_le_conflit_la_liste_des_personnages_ne_couvre_pas_la_note(page, decor, geste,
                                                                       type_zone):
    """« Remplacer par la mienne » ou « Garder l'autre », pour un locuteur comme pour le
    personnage d'une boîte : la puce dit le choix, le focus revient au champ, et sa liste reste
    FERMÉE — la note se lit et se clique sans Échap (passe du locuteur, 2026-11-14)."""
    champ, liste, puce, route = LIEUX[type_zone]
    ctx = _conflit_a_deux_ecrans(page, decor, type_zone)
    try:
        # Le registre répond LENTEMENT, comme sur la recette : rapide, la liste ouverte par le
        # focus se refermait sous le redessin du Contexte, et le défaut ne se voyait pas.
        def lent(route):
            time.sleep(0.6)
            route.continue_()
        page.route(re.compile(r"/api/personnages\?q="), lent)
        if geste == "#an-cf-mienne":                 # « Garder l'autre » n'écrit rien
            with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith(
                    f"/regions/{decor[type_zone]}/{route}")) as rep:
                page.locator(geste).click()
            assert rep.value.status == 200, rep.value.text()
        else:
            page.locator(geste).click()
        expect(page.locator("#an-cf-titre")).to_have_count(0)
        expect(page.locator(puce)).to_have_text("Milou" if geste == "#an-cf-mienne" else "Haddock")
        expect(page.locator(champ)).to_be_focused()
        page.wait_for_timeout(1500)                  # une lecture lente aurait eu le temps
        expect(page.locator(liste)).to_be_hidden()
        note = page.locator("#an-note")
        expect(note).to_be_visible()
        centre = note.bounding_box()
        dessus = page.evaluate("([x, y]) => document.elementFromPoint(x, y).id",
                               [centre["x"] + centre["width"] / 2, centre["y"] + centre["height"] / 2])
        assert dessus == "an-note", dessus
        note.click()
        expect(note).to_be_focused()
    finally:
        ctx.close()


def test_rien_ne_s_ecrit_a_cote_d_un_locuteur_vide_ni_sous_des_mots_absents(page, decor):
    """Hugo, 2026-11-14 : à côté de « Locuteur » d'une zone qui n'en a pas, et sous « Mots de la
    bulle » d'une zone sans transcription, rien ne s'écrit — « — » se lisait comme une valeur —,
    et la ligne garde la hauteur qu'elle avait avec lui."""
    _ouvrir(page, decor, "bulle")
    puce = page.locator("#an-loc-nom")
    expect(puce).to_have_text("")
    expect(page.locator("#an-ctx-loc")).not_to_contain_text("—")
    mots = page.locator("#an-mots")
    expect(page.locator("#an-texte-titre")).to_contain_text("Mots")
    expect(mots).to_have_text("")
    for selecteur in ("#an-loc-nom", "#an-mots"):
        hauteurs = page.locator(selecteur).evaluate("""(e) => {
          const ligne = e.closest('#an-ctx-loc') || e;
          const h = [e.getBoundingClientRect().height, ligne.getBoundingClientRect().height];
          const avant = e.textContent; e.textContent = '—';
          const h2 = [e.getBoundingClientRect().height, ligne.getBoundingClientRect().height];
          e.textContent = avant; return [h, h2]; }""")
        (vide, ligne), (avec, ligne2) = hauteurs
        assert vide > 0 and abs(vide - avec) < 0.5 and abs(ligne - ligne2) < 0.5, (selecteur, hauteurs)
