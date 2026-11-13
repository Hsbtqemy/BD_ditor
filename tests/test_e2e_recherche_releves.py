"""La Recherche avec les relevés, dans un vrai navigateur (ANN-7, le mode libre ; J7, et la
case « La Recherche fonctionne avec les étiquettes libres comme avec les grilles », tranchée
sur maquette par Hugo le 2026-11-06).

Les trois recherches de la séance — un mot dans le texte ET dans une étiquette, un mot dans
une étiquette seule, une case sans texte —, la ligne des relevés de chaque résultat (« Mode
libre : … · Signaux : … »), le clic sur un relevé qui l'isole, la liste « Porte… » sur une
grille OUVERTE (la grille de travail, « Mode libre ») et une grille FERMÉE (le modèle fictif,
publié), deux puces et leur ✕, l'adresse et l'export CSV qui suivent les filtres.

Le serveur est éprouvé par `tests/test_recherche_releves.py` ; la logique pure de l'écran par
`tests/js/porte.test.js`. Ici, ce que l'écran DIT et ce que ses gestes DEMANDENT.
"""
import re
import urllib.parse

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from config import GRILLE_DE_TRAVAIL_NOM  # noqa: E402
from conftest import ECRITURE, make_png  # noqa: E402
from grilles_decor import grille_active_vivante  # noqa: E402
from test_e2e_a11y import _audit, _fmt, _theme  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/recherche",)
SURFACES_HORS_PERIMETRE = {
    "/": "l'Atelier ne lit pas les relevés en ligne ; il ne mène qu'à la page Annotation",
    "/annotation": "la page Annotation pose les relevés ; leur recherche vit dans /recherche",
    "/corpus": "la Bibliothèque range des albums ; elle ne cherche aucun relevé",
    "/exploration": "l'Exploration compte le corpus ; les relevés y viendront en tranche 4",
    "/administration": "l'Administration règle les grilles d'un projet, sans rien y chercher",
}


@pytest.fixture
def decor(live_server):
    """Une planche à deux cases, sans texte. Dans la première, une bulle « QUEL SILENCE
    ICI » ; dans la seconde, un cartouche « PENDANT CE TEMPS… ». Les relevés :
      · c1        Mode libre « lieu : forêt »
      · bulle     Mode libre « sentiment : surprise » ; Signaux « ton de voix : crié »
      · c2        Mode libre « silence »
      · cartouche Mode libre « silence » ; Signaux « ton de voix : chuchoté »
    « Mode libre » est la grille de travail du projet (OUVERTE) ; « Signaux », le modèle
    fictif publié (FERMÉE)."""
    with httpx.Client(base_url=live_server, trust_env=False, timeout=180,
                      headers=ECRITURE) as c:
        aid = c.post("/api/albums", json={"titre": "E2E relevés"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(800, 1000), "image/png")}).json()["id"]

        def region(**corps):
            rep = c.post(f"/api/planches/{pid}/regions", json=corps)
            assert rep.status_code in (200, 201), rep.text
            return rep.json()["id"]

        c1 = region(type="case", x=20, y=20, w=360, h=900)
        c2 = region(type="case", x=420, y=20, w=360, h=500)
        bulle = region(type="bulle", x=60, y=60, w=200, h=120, parent_id=c1)
        cartouche = region(type="cartouche", x=440, y=40, w=300, h=80, parent_id=c2)
        c.put(f"/api/regions/{bulle}", json={"ocr_texte": "QUEL SILENCE ICI"})
        c.put(f"/api/regions/{cartouche}", json={"ocr_texte": "PENDANT CE TEMPS…"})

        signaux = grille_active_vivante(c)
        projet = signaux["projet_id"]
        actives = c.get(f"/api/projets/{projet}/grilles").json()["actives"]
        (travail,) = [g for g in actives if g["travail"]]
        assert travail["nom"] == GRILLE_DE_TRAVAIL_NOM

        def libre(region_id, libelle):
            r = c.post("/api/releves", json={
                "region_id": region_id, "grille_id": travail["id"],
                "version": travail["version"]["numero"],
                "nouvelle_entree": {"libelle": libelle}})
            assert r.status_code == 201, r.text

        def ferme(region_id, entree, variante):
            r = c.post("/api/releves", json={
                "region_id": region_id, "grille_id": signaux["grille_id"], "version": 1,
                "entree_cle": entree, "variante_cle": variante})
            assert r.status_code == 201, r.text

        libre(c1, "lieu : forêt")
        libre(bulle, "sentiment : surprise")
        ferme(bulle, "ton-de-voix", "crie")
        libre(c2, "silence")
        libre(cartouche, "silence")
        ferme(cartouche, "ton-de-voix", "chuchote")
    return {"base": live_server, "album": aid, "c1": c1, "c2": c2, "bulle": bulle,
            "cartouche": cartouche, "travail": travail["id"],
            "travail_version": travail["version"]["numero"], "signaux": signaux["grille_id"]}


def _chercher(page, d, qs=""):
    with page.expect_response(lambda r: "/api/recherche?" in r.url):
        page.goto(f"{d['base']}/recherche{qs}")


def _carte(page, texte):
    """La carte d'un résultat, par ce qu'elle dit."""
    return page.locator(".result").filter(has_text=texte)


def _adresse_porte(page):
    return urllib.parse.parse_qs(urllib.parse.urlsplit(page.url).query).get("porte", [])


# --------------------------------------------------------------------------- #
# Les trois recherches de la séance
# --------------------------------------------------------------------------- #
def test_un_mot_dans_le_texte_et_dans_une_etiquette(page, decor):
    """« silence » : la bulle par son texte, la case c2 et le cartouche par leur étiquette ;
    le mot surligné dans le texte comme dans l'étiquette, la ligne « Mode libre : silence ·
    Signaux : ton de voix : chuchoté » sur le cartouche, la grille de travail d'abord."""
    _chercher(page, decor, "?q=silence")
    expect(page.locator("#q")).to_have_attribute(
        "placeholder", "Rechercher dans les dialogues, notes, étiquettes…")
    expect(page.locator(".result")).to_have_count(3, timeout=15000)
    bulle = _carte(page, "QUEL SILENCE ICI")
    expect(bulle.locator(".r-text mark")).to_have_text("SILENCE")
    cartouche = _carte(page, "PENDANT CE TEMPS")
    expect(cartouche.locator(".r-releves")).to_have_text(
        "Mode libre : silence · Signaux : ton de voix : chuchoté")
    expect(cartouche.locator(".r-releves .r-gr").first).to_have_text("Mode libre :")
    expect(cartouche.locator(".r-releve mark")).to_have_text("silence")
    case = _carte(page, "Case c2, sans texte")
    expect(case.locator(".r-releves")).to_have_text("Mode libre : silence")
    expect(case.locator(".r-releve mark")).to_have_text("silence")
    # Le nom d'une grille n'est pas une étiquette : rien n'y est surligné.
    expect(page.locator(".r-gr mark")).to_have_count(0)


def test_un_mot_dans_une_etiquette_seule(page, decor):
    """« surprise » n'est que dans une étiquette : la bulle se trouve, son texte n'a rien de
    surligné, sa ligne dit les deux grilles et surligne l'étiquette."""
    _chercher(page, decor, "?q=surprise")
    expect(page.locator(".result")).to_have_count(1, timeout=15000)
    carte = page.locator(".result")
    expect(carte.locator(".r-text")).to_have_text("QUEL SILENCE ICI")
    expect(carte.locator(".r-text mark")).to_have_count(0)
    expect(carte.locator(".r-releves")).to_have_text(
        "Mode libre : sentiment : surprise · Signaux : ton de voix : crié")
    expect(carte.locator(".r-releve mark")).to_have_text("surprise")


def test_une_case_sans_texte(page, decor):
    """« foret », sans accent : la case c1, qui n'a ni texte ni note, se trouve par « lieu :
    forêt » et se dit « Case c1, sans texte » ; « forêt » est surligné."""
    _chercher(page, decor, "?q=foret")
    expect(page.locator(".result")).to_have_count(1, timeout=15000)
    carte = page.locator(".result")
    expect(carte.locator(".r-text")).to_have_text("Case c1, sans texte")
    expect(carte.locator(".r-releves")).to_have_text("Mode libre : lieu : forêt")
    expect(carte.locator(".r-releve mark")).to_have_text("forêt")


# --------------------------------------------------------------------------- #
# Isoler
# --------------------------------------------------------------------------- #
def test_un_clic_sur_un_releve_l_isole(page, decor):
    """Un clic sur « ton de voix : crié » (grille fermée) dans la carte de la bulle ajoute son
    filtre : une puce, l'adresse, la requête ; l'aperçu ne s'ouvre pas, le focus va à la
    puce. Puis un clic sur une étiquette du Mode libre d'un autre résultat combine (« et »)."""
    _chercher(page, decor, "?q=silence")
    expect(page.locator(".result")).to_have_count(3, timeout=15000)
    releve = _carte(page, "QUEL SILENCE ICI").locator(".r-releve", has_text="ton de voix : crié")
    with page.expect_request(lambda r: "/api/recherche?" in r.url and "porte=" in r.url) as req:
        releve.click()
    attendu = f"{decor['signaux']}/variante/ton-de-voix/crie"
    assert urllib.parse.parse_qs(urllib.parse.urlsplit(req.value.url).query)["porte"] == [attendu]
    expect(page.locator(".result")).to_have_count(1)
    expect(page.locator("#preview")).to_be_hidden()
    puces = page.locator("#filtres-porte .porte-puce")
    expect(puces).to_have_count(1)
    expect(puces.first).to_contain_text("porte Signaux › ton de voix : crié")
    expect(page.locator("#filtres-porte .porte-retirer")).to_be_focused()
    assert _adresse_porte(page) == [attendu]
    # Un relevé déjà posé ne se double pas.
    page.locator(".result .r-releve", has_text="ton de voix : crié").click()
    expect(puces).to_have_count(1)
    # Un clic ailleurs sur la carte ouvre toujours l'aperçu.
    page.locator(".result .r-ouvrir").click()
    expect(page.locator("#preview")).to_be_visible()


def test_la_liste_porte_les_puces_et_leur_croix(page, decor):
    """« Porte… » : le Mode libre d'abord, puis « Signaux » avec ses rubriques. Une étiquette
    du Mode libre (grille OUVERTE) puis une entrée de Signaux (grille FERMÉE) : deux puces,
    « et » entre elles, chacune son ✕ ; l'adresse et l'export CSV suivent ; ✕ en retire une,
    le focus passe à la suivante ; la dernière retirée rend l'invite."""
    page.goto(f"{decor['base']}/recherche")       # sans critère, aucune requête ne part
    sel = page.locator("#f-porte")
    expect(sel).to_be_visible(timeout=15000)
    groupes = sel.locator("optgroup")
    expect(groupes).to_have_count(2)
    expect(groupes.nth(0)).to_have_attribute("label", "Mode libre")
    expect(groupes.nth(1)).to_have_attribute("label", "Signaux")
    expect(groupes.nth(0).locator("option", has_text="Rubrique :")).to_have_count(0)
    expect(groupes.nth(1).locator("option", has_text="Rubrique :").first).to_be_attached()
    expect(groupes.nth(1).locator("option", has_text="ton de voix : chuchoté")).to_have_count(1)

    silence = f"{decor['travail']}/entree/silence"
    with page.expect_response(lambda r: "/api/recherche?" in r.url and "porte=" in r.url):
        sel.select_option(silence)
    expect(sel).to_have_value("")
    expect(page.locator(".result")).to_have_count(2)      # c2 et le cartouche
    ton = f"{decor['signaux']}/entree/ton-de-voix"
    with page.expect_response(lambda r: "/api/recherche?" in r.url and r.url.count("porte=") == 2):
        sel.select_option(ton)
    expect(page.locator(".result")).to_have_count(1)      # le cartouche seul
    expect(_carte(page, "PENDANT CE TEMPS")).to_have_count(1)
    puces = page.locator("#filtres-porte .porte-puce")
    expect(puces).to_have_count(2)
    expect(puces.nth(0)).to_contain_text("porte Mode libre › silence")
    expect(puces.nth(1)).to_contain_text("porte Signaux › ton de voix")
    expect(page.locator("#filtres-porte .porte-et")).to_have_text("et")
    assert _adresse_porte(page) == [silence, ton]

    # L'export CSV suit les filtres.
    with page.expect_download() as tele:
        page.locator("#btn-export").click()
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(tele.value.url).query)
    assert tele.value.url.split("?")[0].endswith("/api/recherche/export.csv")
    assert q["porte"] == [silence, ton]

    # ✕ sur la première : le focus passe à la suivante, l'adresse et les résultats suivent.
    with page.expect_response(lambda r: "/api/recherche?" in r.url):
        puces.nth(0).locator(".porte-retirer").click()
    expect(puces).to_have_count(1)
    expect(page.locator("#filtres-porte .porte-et")).to_have_count(0)
    expect(page.locator("#filtres-porte .porte-retirer")).to_be_focused()
    expect(page.locator(".result")).to_have_count(2)      # la bulle et le cartouche
    assert _adresse_porte(page) == [ton]
    # ✕ sur la dernière : plus de filtre, l'invite, et le focus revient à la liste.
    page.locator("#filtres-porte .porte-retirer").click()
    expect(page.locator("#filtres-porte")).to_be_hidden()
    expect(page.locator(".result")).to_have_count(0)
    expect(page.locator("#results .search-hint")).to_contain_text("Tapez un mot-clé")
    expect(sel).to_be_focused()
    assert _adresse_porte(page) == []


def test_un_lien_porte_ses_filtres_et_les_nomme(page, decor):
    """Une adresse qui porte `porte=` rejoue le filtre et la Recherche n'en rend que les
    zones. Un filtre de RUBRIQUE se dit d'abord par sa clé (la grille, par les résultats), puis par le plan une fois lu
    (« rubrique Voix ») — et la puce redessinée garde le focus de son ✕."""
    cle = next(o for o in _rubriques(decor) if o["libelle"] == "Voix")["cle"]
    assert cle != "Voix"
    voix = f"{decor['signaux']}/rubrique/{cle}"
    retenues = []
    page.route("**/api/grilles/*/versions/*", lambda route: retenues.append(route))
    qs = "?" + urllib.parse.urlencode([("porte", voix)])
    _chercher(page, decor, qs)
    expect(page.locator(".result")).to_have_count(2, timeout=15000)   # la bulle, le cartouche
    puce = page.locator("#filtres-porte .porte-puce")
    expect(puce).to_contain_text(f"rubrique {cle}")                  # le plan n'est pas lu
    page.locator("#filtres-porte .porte-retirer").focus()
    for _ in range(100):                    # les plans demandés, et retenus
        if len(retenues) >= 2:
            break
        page.wait_for_timeout(100)
    assert len(retenues) >= 2, "les plans des deux grilles n'ont pas été demandés"
    for route in retenues:
        route.continue_()
    page.unroute("**/api/grilles/*/versions/*")
    expect(puce).to_contain_text("porte Signaux › rubrique Voix")
    expect(page.locator("#filtres-porte .porte-retirer")).to_be_focused()


def _rubriques(d):
    with httpx.Client(base_url=d["base"], trust_env=False, timeout=30, headers=ECRITURE) as c:
        return c.get(f"/api/grilles/{d['signaux']}/versions/1").json()["rubriques"]


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_les_releves_et_les_puces_passent_l_audit(page, decor, theme):
    """axe (WCAG 2.1 AA, sérieux et critique) sur ce que la Recherche ajoute : la liste
    « Porte… » remplie, deux puces, et des résultats qui portent leur ligne de relevés — des
    boutons à côté du bouton de la carte, jamais dedans."""
    _theme(page, theme)
    qs = "?" + urllib.parse.urlencode([
        ("q", "silence"), ("porte", f"{decor['travail']}/entree/silence"),
        ("porte", f"{decor['signaux']}/entree/ton-de-voix")])
    _chercher(page, decor, qs)
    expect(page.locator(".result .r-releve").first).to_be_visible(timeout=15000)
    expect(page.locator("#filtres-porte .porte-puce")).to_have_count(2)
    expect(page.locator("#f-porte")).to_be_visible()
    viol = _audit(page)
    assert not viol, f"thème {theme}\n{_fmt(viol)}"


def test_a_320_px_rien_ne_pousse_la_page_de_cote(page, decor):
    """La liste « Porte… » prend la largeur de sa plus longue option, une puce et une ligne de
    relevés peuvent être longues : à 320 px, elles passent à la ligne, et la page ne défile
    pas de côté (la sonde de reflow ne lit pas de relevés). Une étiquette au libellé long
    naît dans le Mode libre, son relevé aussitôt retiré : l'entrée reste dans le plan, donc
    dans la liste, sans rien changer aux autres résultats."""
    long = "une étiquette au libellé volontairement long, plus large qu'un téléphone"
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        r = c.post("/api/releves", json={
            "region_id": decor["c1"], "grille_id": decor["travail"],
            "version": decor["travail_version"],
            "nouvelle_entree": {"libelle": long + " : et sa valeur, longue elle aussi"}})
        assert r.status_code == 201, r.text
        assert c.delete(f"/api/releves/{r.json()['id']}").status_code == 204
    page.set_viewport_size({"width": 320, "height": 700})
    qs = "?" + urllib.parse.urlencode([
        ("q", "silence"), ("porte", f"{decor['signaux']}/variante/ton-de-voix/chuchote")])
    _chercher(page, decor, qs)
    expect(page.locator(".result .r-releve").first).to_be_visible(timeout=15000)
    expect(page.locator("#f-porte")).to_be_visible()
    expect(page.locator("#f-porte option", has_text="sa valeur, longue")).to_have_count(1)
    debord = page.evaluate("""() => [...document.querySelectorAll(
        '#f-porte, #filtres-porte .porte-puce, .result .r-releves')]
      .filter((el) => el.getBoundingClientRect().right > document.documentElement.clientWidth + 0.5)
      .map((el) => el.id || el.className)""")
    assert debord == [], debord
    assert page.evaluate("document.documentElement.scrollWidth <= "
                         "document.documentElement.clientWidth")
