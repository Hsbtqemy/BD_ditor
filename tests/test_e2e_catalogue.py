"""UX-20 — le catalogue de la Bibliothèque, joué dans un navigateur SOUS L'IDENTITÉ concernée.

Tranché par Hugo sur maquette le 2026-11-02 : les collections en rail, les albums au centre,
l'album en volet. Le serveur est mesuré par `tests/test_couverture.py`,
`tests/test_miniature.py` et `tests/test_copie_dans_la_liste.py` ; les règles pures par
`tests/js/bibliotheque.test.js`. Ce fichier mesure ce que l'écran EN FAIT :

- la grille ne charge aucun dérivé, seulement des miniatures ;
- une carte garde sa taille quand le volet s'ouvre, et l'album ouvert reste en vue ;
- l'adresse mène aux mêmes objets, volet compris ;
- une copie se replie sous son original, et un original qu'on ne lit pas ne se situe pas ;
- les marques, le bloc Collections et le fil disent où l'on est et ce qu'on peut.
"""
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

from conftest import du_projet  # noqa: E402
from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.parametrize("live_server", [True], indirect=True)]

SURFACES_AUDITEES = ("/corpus",)
SURFACES_HORS_PERIMETRE = {
    "/annotation": "le catalogue vit dans la Bibliothèque seule",
    "/administration": "l'Administration garde le gabarit `lf-` ; rien du catalogue n'y vit",
    "/": "l'Atelier travaille une planche ; rien du catalogue n'y vit",
    "/recherche": "rien du catalogue n'y vit",
    "/exploration": "rien du catalogue n'y vit",
}

EN_TETE = next(k for k in ECRITURE if k not in ("Remote-User", "Remote-Groups"))
ADMIN = {**ECRITURE}


def _comme(login):
    return {"Remote-User": login, EN_TETE: "1"}


def _ok(r, *codes):
    assert r.status_code in (codes or (200, 201)), r.text
    return r.json() if r.content else None


def _album(c, titre, cid, planches=1):
    a = _ok(c.post("/api/albums", json={"titre": titre, "collection_id": cid}))["id"]
    for _ in range(planches):
        _ok(c.post(f"/api/albums/{a}/import",
                   files={"file": ("p.png", make_png(900, 1200), "image/png")}))
    return a


@pytest.fixture
def decor(live_server):
    """« Étude » (Léa y écrit, Lou la lit) et « Réserve » (Léa seule) : l'original vit dans
    Réserve, Lou n'en lit que la copie, rangée dans Étude."""
    with httpx.Client(base_url=live_server, trust_env=False, timeout=60, headers=ADMIN) as c:
        for login in ("lea", "lou"):
            c.get("/api/moi", headers=_comme(login))
        etude = _ok(c.post("/api/collections", json={"nom": "Étude"}))["id"]
        reserve = _ok(c.post("/api/collections", json={"nom": "Réserve"}))["id"]
        for cid, login, niveau in ((etude, "lea", "ecriture"), (reserve, "lea", "ecriture"),
                                   (etude, "lou", "lecture")):
            du_projet(c, cid, "utilisateur", login)
            _ok(c.put(f"/api/collections/{cid}/acces", json={
                "genre": "utilisateur", "principal": login, "niveau": niveau}))
        original = _album(c, "Le Lotus bleu", reserve, planches=2)
        seul = _album(c, "Les Cigares", etude)
        doc = next(a for a in c.get("/api/albums").json() if a["id"] == original)["document_id"]
    with httpx.Client(base_url=live_server, trust_env=False, timeout=60,
                      headers=_comme("lea")) as c:
        rep = _ok(c.post(f"/api/collections/{etude}/prendre", json={"documents": [
            {"document_id": doc, "reponse": "zero", "album_id": original}]}))
        assert rep["documents"][0]["etat"] == "fait", rep
        copie = rep["documents"][0]["copie_id"]
    return {"base": live_server, "etude": etude, "reserve": reserve, "original": original,
            "seul": seul, "copie": copie}


def _ouvrir(page, base, login, largeur=1280, suffixe=""):
    page.set_viewport_size({"width": largeur, "height": 800})
    page.set_extra_http_headers(_comme(login) if login != "admin" else ADMIN)
    page.goto(f"{base}/corpus{suffixe}")
    page.wait_for_selector("#albums-body .album-row")


def _carte(page, album_id):
    return page.locator(f'#albums-body .album-row[data-id="{album_id}"]')


def test_la_grille_ne_charge_aucun_derive(page, decor):
    """Le prérequis de la grille : un dérivé fait au moins 1 600 px de large."""
    demandes = []
    page.on("request", lambda r: demandes.append(r.url))
    _ouvrir(page, decor["base"], "lea")
    expect(page.locator(".couv-img").first).to_be_visible()
    page.wait_for_load_state("networkidle")
    assert any("/miniature" in u for u in demandes), "aucune miniature demandée"
    assert not [u for u in demandes if "/derivatives/" in u]


def test_une_couverture_absente_laisse_le_titre(page, decor):
    with httpx.Client(base_url=decor["base"], trust_env=False, headers=ADMIN) as c:
        _ok(c.post("/api/albums", json={"titre": "Sans planche", "collection_id": decor["etude"]}))
    _ouvrir(page, decor["base"], "lea")
    carte = page.locator(".album-row", has_text="Sans planche")
    expect(carte.locator(".couv-titre")).to_have_text("Sans planche")
    assert carte.locator(".couv-img").count() == 0


def test_une_miniature_qui_manque_rend_l_aplat(page, decor):
    """Une planche d'avant le rattrapage : la route répond 404, et rien de cassé à l'écran."""
    page.route("**/miniature", lambda route: route.fulfill(status=404, body=""))
    _ouvrir(page, decor["base"], "lea")
    expect(page.locator(".couv-img")).to_have_count(0)
    expect(page.locator(".couv-titre").first).to_be_visible()


def test_une_carte_garde_sa_taille_quand_le_volet_s_ouvre(page, decor):
    _ouvrir(page, decor["base"], "lea")
    carte = _carte(page, decor["seul"])
    avant = carte.bounding_box()
    carte.click()
    page.wait_for_selector("#album-detail")
    apres = _carte(page, decor["seul"]).bounding_box()
    assert apres["width"] == avant["width"]


def test_l_album_ouvert_reste_en_vue(page, decor):
    with httpx.Client(base_url=decor["base"], trust_env=False, headers=ADMIN) as c:
        for i in range(30):
            _ok(c.post("/api/albums", json={"titre": f"Z{i:02d}", "collection_id": decor["etude"]}))
    _ouvrir(page, decor["base"], "lea")
    derniere = page.locator("#albums-body .album-row").last
    derniere.scroll_into_view_if_needed()
    derniere.click()
    page.wait_for_selector("#album-detail")
    expect(page.locator('#albums-body .album-row[aria-current="true"]')).to_be_in_viewport()


def test_le_volet_ne_recouvre_pas_le_catalogue(page, decor):
    _ouvrir(page, decor["base"], "lea")
    _carte(page, decor["seul"]).click()
    page.wait_for_selector("#album-detail")
    vue = page.locator("#cat-vue").bounding_box()
    volet = page.locator("#biblio-volet").bounding_box()
    assert vue["x"] + vue["width"] <= volet["x"] + 1
    centre = page.locator("#biblio-fiche").bounding_box()
    assert abs(volet["width"] / centre["width"] - .52) < .02


def test_fermer_le_volet_rend_le_focus_a_la_carte(page, decor):
    _ouvrir(page, decor["base"], "lea")
    _carte(page, decor["seul"]).click()
    expect(page.locator("#album-titre")).to_be_focused()
    page.locator("[data-retour-album]").click()
    expect(page.locator("#biblio-volet")).to_be_hidden()
    expect(_carte(page, decor["seul"])).to_be_focused()


def test_l_adresse_mene_aux_memes_objets(page, decor):
    """Depuis une collection, puis un album : l'adresse porte les deux, un rechargement les
    rouvre, le retour arrière referme le volet et garde la collection."""
    _ouvrir(page, decor["base"], "lea")
    page.locator(".col-ouvrir", has_text="Étude").click()
    expect(page.locator("#panneau-albums")).to_be_visible()
    assert f"collection={decor['etude']}" in page.url and "onglet=albums" in page.url
    _carte(page, decor["seul"]).click()
    page.wait_for_selector("#album-detail")
    assert f"album={decor['seul']}" in page.url and f"collection={decor['etude']}" in page.url
    page.reload()
    page.wait_for_selector("#album-detail")
    expect(page.locator("#col-fiche-titre")).to_have_text("Étude")
    expect(page.locator("#panneau-albums")).to_be_visible()
    page.go_back()
    expect(page.locator("#biblio-volet")).to_be_hidden()
    expect(page.locator("#col-fiche-titre")).to_have_text("Étude")


def test_une_adresse_sans_onglet_ouvre_qui_entre(page, decor):
    """Les liens de l'Administration : l'adresse d'avant le catalogue ne change pas de sens."""
    page.set_viewport_size({"width": 1280, "height": 800})
    page.set_extra_http_headers(ADMIN)
    page.goto(f"{decor['base']}/corpus?collection={decor['etude']}")
    expect(page.locator("#panneau-qui")).to_be_visible()


def test_une_copie_se_replie_sous_son_original(page, decor):
    """Léa lit l'original : une pile, « ▸ 1 copie », et « Votre copie » sous elle, sans que le
    titre soit répété."""
    _ouvrir(page, decor["base"], "lea")
    pli = page.locator(f'[data-pli="{decor["original"]}"]')
    expect(pli).to_have_text("▸ 1 copie")
    expect(pli).to_have_attribute("aria-expanded", "false")
    expect(_carte(page, decor["copie"])).to_have_count(0)
    pli.click()
    expect(page.locator(f'[data-pli="{decor["original"]}"]')).to_have_text("▾ 1 copie")
    expect(_carte(page, decor["copie"]).locator(".titre")).to_have_text("Votre copie")


def test_l_original_hors_de_la_vue_revient_eteint(page, decor):
    """Dans « Étude », Léa ne voit que la copie : l'original lu y reste, grisé."""
    _ouvrir(page, decor["base"], "lea", suffixe=f"?collection={decor['etude']}&onglet=albums")
    carte = page.locator(f'[data-carte="{decor["original"]}"]')
    expect(carte).to_have_class(re.compile("eteinte"))
    expect(carte.locator(".det")).to_have_text("hors de cette collection")
    expect(carte.locator("input[type=checkbox]")).to_have_count(0)
    expect(_carte(page, decor["copie"])).to_be_visible()


def test_un_original_non_lu_ne_se_situe_pas(page, decor):
    """Lou lit la copie, pas l'original : ni son titre à part, ni carte éteinte, ni version."""
    _ouvrir(page, decor["base"], "lou", suffixe=f"?collection={decor['etude']}&onglet=albums")
    expect(_carte(page, decor["copie"]).locator(".det")).to_have_text(
        "Copie de travail · copie vierge")
    expect(page.locator(f'[data-carte="{decor["original"]}"]')).to_have_count(0)
    _carte(page, decor["copie"]).click()
    page.wait_for_selector("#album-detail")
    expect(page.locator("#ce-document-titre")).to_have_count(0)
    expect(page.locator("#album-detail .genre")).to_have_text("Album · copie de travail")


def test_les_marques_disent_ce_qu_on_peut(page, decor):
    _ouvrir(page, decor["base"], "lou", suffixe=f"?collection={decor['etude']}&onglet=albums")
    expect(_carte(page, decor["seul"]).locator(".marque-e")).to_have_text("lecture")
    _ouvrir(page, decor["base"], "lea", suffixe=f"?collection={decor['etude']}&onglet=albums")
    expect(_carte(page, decor["copie"]).locator(".marque-e")).to_have_text("à vous")
    expect(_carte(page, decor["seul"]).locator(".marque-e")).to_have_count(0)


def test_vit_dans_nomme_les_collections_celle_qu_on_regarde_en_gras(page, decor):
    _ouvrir(page, decor["base"], "lea", suffixe=f"?collection={decor['etude']}&onglet=albums")
    page.locator('[data-vue-albums="liste"]').click()
    ligne = page.locator(f'tr.col-album[data-id="{decor["seul"]}"]')
    expect(ligne.locator(".c-vit b")).to_have_text("Étude")


def test_la_liste_se_retient_sur_le_poste(page, decor):
    _ouvrir(page, decor["base"], "lea")
    expect(page.locator('[data-vue-albums="grille"]')).to_have_attribute("aria-pressed", "true")
    page.locator('[data-vue-albums="liste"]').click()
    expect(page.locator("#albums-body table")).to_be_visible()
    page.reload()
    expect(page.locator("#albums-body table")).to_be_visible()


def test_le_bloc_collections_filtre_et_range(page, decor):
    """Lou lit, Léa écrit : les sections suivent, et « Les miennes » est vide pour elles."""
    _ouvrir(page, decor["base"], "lou")
    expect(page.locator("#col-body .col-sec", has_text="Où vous lisez")).to_be_visible()
    expect(page.locator("#col-body .col-sec", has_text="Les vôtres")).to_have_count(0)
    page.locator('[data-espace="miennes"]').click()
    expect(page.locator("#col-body .col-item")).to_have_count(0)
    expect(page.locator("#col-body .col-note")).to_have_text("Aucune ici.")
    expect(page.locator('[data-espace="miennes"]')).to_be_focused()
    _ouvrir(page, decor["base"], "lea")
    page.locator('[data-espace="ecris"]').click()
    expect(page.locator("#col-body .col-sec")).to_have_count(0)
    expect(page.locator("#col-body .col-ouvrir", has_text="Étude")).to_be_visible()


def test_l_administrateur_n_a_ni_filtre_ni_sections(page, decor):
    _ouvrir(page, decor["base"], "admin")
    expect(page.locator("#col-espaces")).to_be_hidden()
    expect(page.locator("#col-body .col-sec")).to_have_count(0)
    expect(page.locator("#col-body .col-niveau").first).to_have_text("administrateur")


def test_le_fil_dit_ou_l_on_est(page, decor):
    _ouvrir(page, decor["base"], "lea", suffixe=f"?collection={decor['etude']}&onglet=albums")
    fil = page.locator("#bi-fil li")
    expect(fil).to_have_text(["Bibliothèque", "Étude"])
    _carte(page, decor["copie"]).click()
    page.wait_for_selector("#album-detail")
    expect(fil).to_have_text(["Bibliothèque", "Étude", "Le Lotus bleu", "Votre copie"])
    page.locator("#bi-fil button", has_text="Étude").click()
    expect(page.locator("#biblio-volet")).to_be_hidden()
    expect(fil).to_have_text(["Bibliothèque", "Étude"])


def test_les_chiffres_sont_en_tete_du_projet(page, decor):
    _ouvrir(page, decor["base"], "lea")
    expect(page.locator("#cat-vue #corpus-stats")).to_contain_text("planches")
    expect(page.locator("#header #corpus-stats")).to_have_count(0)


def test_ce_document_nomme_l_original_et_ses_copies(page, decor):
    _ouvrir(page, decor["base"], "lea")
    _carte(page, decor["original"]).click()
    page.wait_for_selector("#ce-document-titre")
    expect(page.locator("#ce-document-titre")).to_contain_text("2 versions lues")
    bloc = page.locator(".copies-l li")
    expect(bloc.first).to_contain_text("L'original (ici)")
    bloc.nth(1).locator("button").click()
    expect(page.locator("#album-detail .genre")).to_have_text("Album · copie de travail")


def test_les_gestes_rares_sont_sous_autres_gestes(page, decor):
    _ouvrir(page, decor["base"], "lea")
    _carte(page, decor["seul"]).click()
    page.wait_for_selector("#album-detail")
    expect(page.locator("#detail-edit")).to_be_visible()
    suppr = page.locator('#album-detail [data-act="supprimer"]')
    expect(suppr).to_be_hidden()
    page.locator(".autres > summary").click()
    expect(suppr).to_be_visible()


def test_cocher_un_album_ouvre_le_lot_depuis_le_projet(page, decor):
    _ouvrir(page, decor["base"], "lea")
    page.locator(f'[data-coche-album="{decor["seul"]}"]').check()
    expect(page.locator(".bi-lot")).to_contain_text("1 album sélectionné")


def test_a_l_etroit_le_volet_remplace_le_catalogue(page, decor):
    _ouvrir(page, decor["base"], "lea", largeur=800)
    _carte(page, decor["seul"]).click()
    page.wait_for_selector("#album-detail")
    expect(page.locator("#cat-vue")).to_be_hidden()
    page.locator("[data-retour-album]").click()
    expect(page.locator("#cat-vue")).to_be_visible()


def test_au_telephone_une_liste_remplace_le_rail(page, decor):
    _ouvrir(page, decor["base"], "lea", largeur=390)
    expect(page.locator("#cat-rail")).to_be_hidden()
    page.locator("#cat-select").select_option(label="Étude")
    expect(page.locator("#col-fiche-titre")).to_have_text("Étude")
    page.locator("#cat-rail-ouvrir").click()
    expect(page.locator("#col-creer-zone").locator("..")).to_be_visible()
    expect(page.locator("#cat-rail")).to_be_visible()
