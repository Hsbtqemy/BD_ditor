"""ANN-7, tranche 2 (commit 1) — la page Annotation, jouée dans un vrai navigateur.

La page, sans grille ni pose : on y choisit une planche du projet courant, une CASE sur la
minicarte, une zone DANS la case agrandie (ou le fond, la case elle-même), et l'on lit le
Contexte — locuteur, personnage, note — sans geste. La logique (le rangement en cases, les
étiquettes, l'adresse) est verrouillée sous Node (`tests/js/annotation.test.js`) ; ce fichier
vérifie que la page s'en sert, et qu'elle tient ce que la note de cadrage lui demande dès ce
commit :

- l'ADRESSE ouvre la planche et la zone qu'elle nomme, et suit chaque choix ;
- la disposition NE BOUGE PAS quand on passe d'une case ou d'une zone à l'autre (Hugo,
  2026-10-14) — mesurée sur la boîte de la case, la rangée des zones et le bloc du texte ;
- chaque choix a son chemin au CLAVIER ;
- « Ouvrir dans l'Atelier ↗ » mène à la même zone, et l'Atelier y revient.

Les audits transverses (axe dans les deux thèmes, contraste élevé, reflow à 320 px, grande
police, zoom, masquage, CSP, bande du projet, bac à sable) déclarent la page dans leurs
propres modules.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

SURFACES_AUDITEES = ("/annotation",)
SURFACES_HORS_PERIMETRE = {
    "/": "l'Atelier n'est visité que par le lien « Ouvrir dans l'Atelier ↗ », pour son retour",
    "/recherche": "la Recherche n'a rien de la page Annotation : elle lit le corpus",
    "/corpus": "la Bibliothèque range des albums ; elle ne mène pas encore à cette page",
    "/exploration": "l'Exploration compte le corpus ; les relevés y viendront en tranche 4",
    "/administration": "rien n'y porte sur une planche ; les grilles s'y régleront plus tard",
}


@pytest.fixture
def decor(live_server):
    """Une planche à deux cases : la première porte une bulle (texte, locuteur, note) et une
    boîte personnage ; la seconde, un cartouche."""
    with httpx.Client(base_url=live_server, trust_env=False, timeout=180,
                      headers=ECRITURE) as c:
        aid = c.post("/api/albums", json={"titre": "E2E annotation"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(800, 1000), "image/png")}).json()["id"]

        def region(**corps):
            rep = c.post(f"/api/planches/{pid}/regions", json=corps)
            assert rep.status_code in (200, 201), rep.text
            return rep.json()["id"]

        c1 = region(type="case", x=20, y=20, w=360, h=900)
        c2 = region(type="case", x=420, y=20, w=360, h=500)
        bulle = region(type="bulle", x=60, y=60, w=200, h=120, parent_id=c1)
        boite = region(type="personnage", x=80, y=400, w=150, h=300, parent_id=c1)
        cartouche = region(type="cartouche", x=440, y=40, w=300, h=80, parent_id=c2)
        c.put(f"/api/regions/{bulle}", json={"ocr_texte": "MILLE SABORDS !"})
        c.put(f"/api/regions/{cartouche}", json={"ocr_texte": "PENDANT CE TEMPS…"})
        perso = c.post("/api/personnages", json={"nom": "Haddock"}).json()["id"]
        assert c.put(f"/api/regions/{bulle}/locuteur",
                     json={"personnage_id": perso}).status_code == 200
        assert c.put(f"/api/regions/{boite}/personnage",
                     json={"personnage_id": perso}).status_code == 200
        c.put(f"/api/regions/{bulle}/annotation", json={"note": "il jure"})
    return {"base": live_server, "album": aid, "planche": pid, "c1": c1, "c2": c2,
            "bulle": bulle, "boite": boite, "cartouche": cartouche}


def _ouvrir(page, d, region=None):
    qs = f"album={d['album']}&planche={d['planche']}"
    if region is not None:
        qs += f"&region={region}"
    page.goto(f"{d['base']}/annotation?{qs}", wait_until="networkidle")
    expect(page.locator("#an-mini .an-mz")).to_have_count(2, timeout=15000)


def _boites(page):
    """Les boîtes dont la hauteur ne doit pas bouger pendant le travail."""
    return page.evaluate("""() => ['#an-vue-case', '#an-zones', '#an-texte', '.an-tete']
      .map((s) => Math.round(document.querySelector(s).getBoundingClientRect().height))""")


def test_l_adresse_ouvre_la_zone_et_le_contexte_se_lit(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-album")).to_have_value(str(decor["album"]))
    expect(page.locator("#an-planche-choix")).to_have_value(str(decor["planche"]))
    expect(page.locator("#an-tete-case")).to_have_text("Case c1")
    expect(page.locator("#an-tete-zone")).to_have_text("bulle b1")
    expect(page.locator("#an-texte")).to_have_text("MILLE SABORDS !")
    expect(page.locator('#an-ctx-corps dd[data-ctx="locuteur"]')).to_have_text("Haddock")
    expect(page.locator('#an-ctx-corps dd[data-ctx="note"]')).to_have_text("il jure")
    # Aucun champ dans le Contexte : il se lit ici, il s'écrit dans l'Atelier.
    expect(page.locator(".an-ctx input, .an-ctx textarea, .an-ctx select")).to_have_count(0)
    expect(page.locator("#an-preparee")).to_contain_text("2 zones de texte")


def test_choisir_une_case_puis_une_zone_ne_change_la_taille_de_rien(page, decor):
    _ouvrir(page, decor)
    expect(page.locator("#an-tete-case")).to_have_text("Case c1")
    avant = _boites(page)
    # La seconde case, sur la minicarte : sa zone se lit, l'adresse suit.
    page.locator('#an-mini .an-mz[data-case="1"]').click()
    expect(page.locator("#an-tete-case")).to_have_text("Case c2")
    expect(page.locator('#an-mini .an-mz[data-case="1"]')).to_have_attribute("aria-pressed",
                                                                            "true")
    assert _boites(page) == avant
    # Le cartouche, dans la case agrandie.
    page.locator(f'#an-vue-case rect[data-zone="{decor["cartouche"]}"]').click()
    expect(page.locator("#an-tete-zone")).to_have_text("cartouche b1")
    expect(page.locator("#an-texte")).to_have_text("PENDANT CE TEMPS…")
    assert _boites(page) == avant
    assert f"region={decor['cartouche']}" in page.url
    # Le fond de la case : la case elle-même, et l'adresse nomme la case.
    page.locator("#an-vue-case rect.an-fond").click(position={"x": 5, "y": 300})
    expect(page.locator("#an-tete-zone")).to_have_text("")
    expect(page.locator("#an-texte")).to_have_text("—")
    assert f"region={decor['c2']}" in page.url
    assert _boites(page) == avant


def test_la_boite_personnage_dit_son_personnage_sur_l_image(page, decor):
    _ouvrir(page, decor, decor["boite"])
    expect(page.locator("#an-vue-case text.an-vz-lbl", has_text="Haddock")).to_have_count(1)
    expect(page.locator('#an-ctx-corps dd[data-ctx="personnage"]')).to_have_text("Haddock")
    # Une étiquette lue à taille d'ÉCRAN constante, quelle que soit la case.
    taille = page.evaluate("""() => {
      const t = [...document.querySelectorAll('#an-vue-case text.an-vz-lbl')]
        .find((x) => x.textContent === 'Haddock');
      return t.getBoundingClientRect().height; }""")
    assert 8 <= taille <= 22, taille


def test_chaque_choix_a_son_chemin_au_clavier(page, decor):
    _ouvrir(page, decor)
    case2 = page.locator('#an-mini .an-mz[data-case="1"]')
    case2.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#an-tete-case")).to_have_text("Case c2")
    # Les zones de la case, une rangée de boutons.
    bouton = page.locator("#an-zones .an-zone-btn", has_text="cartouche")
    bouton.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#an-tete-zone")).to_have_text("cartouche b1")
    expect(bouton).to_have_attribute("aria-pressed", "true")


def test_ouvrir_dans_l_atelier_mene_a_la_meme_zone_et_en_revient(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    lien = page.locator("#an-atelier")
    href = lien.get_attribute("href")
    assert f"region={decor['bulle']}" in href and f"planche={decor['planche']}" in href
    assert "retour=" in href
    lien.click()
    page.wait_for_url("**/?*", timeout=15000)
    expect(page.locator("#region-type")).to_be_visible(timeout=15000)
    retour = page.locator("#back-link")
    expect(retour).to_be_visible()
    retour.click()
    page.wait_for_url("**/annotation?*", timeout=15000)
    expect(page.locator("#an-tete-zone")).to_have_text("bulle b1", timeout=15000)


def test_la_page_est_dans_la_navigation_entre_l_atelier_et_la_bibliotheque(page, decor):
    _ouvrir(page, decor)
    liens = page.locator("#site-nav .surf-nav a.surf-link")
    noms = [liens.nth(i).get_attribute("href") for i in range(liens.count())]
    assert noms.index("/annotation") == noms.index("/") + 1
    assert noms.index("/corpus") == noms.index("/annotation") + 1
    expect(page.locator('#site-nav a[href="/annotation"]')).to_have_attribute("aria-current",
                                                                             "page")


def test_sans_planche_la_page_s_ouvre_vide_sans_erreur(page, live_server):
    erreurs = []
    page.on("pageerror", lambda e: erreurs.append(str(e)))
    page.goto(f"{live_server}/annotation", wait_until="networkidle")
    expect(page.locator("#an-album option")).to_have_count(1)
    expect(page.locator("#an-tete-case")).to_have_text("—")
    assert not erreurs, erreurs
