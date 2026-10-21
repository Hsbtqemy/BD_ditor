"""UX-18 — la Bibliothèque refaite, jouée dans un vrai navigateur.

Ce module garde ce que la refonte AJOUTE à la Bibliothèque ; les gestes d'une collection
qu'elle porte depuis COL-2 restent dans `test_e2e_collections.py`, ceux de « Qui entre »
dans `test_e2e_qui_entre.py`. À part de l'audit d'accessibilité pour la raison écrite en
tête de `test_e2e_collections.py` : un module e2e finit par acquérir sa propre condition
de saut, et des tests de COMPORTEMENT n'ont pas à dépendre d'un outil d'audit.
"""
import json
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from conftest import ECRITURE, make_png  # noqa: E402
from playwright.sync_api import expect  # noqa: E402

pytestmark = pytest.mark.e2e

SURFACES_AUDITEES = ("/corpus",)
SURFACES_HORS_PERIMETRE = {
    "/administration": "la refonte d'UX-18 ne touche que la Bibliothèque ; l'Administration "
                       "a ses propres tests de liste et de fiche",
    "/": "l'Atelier travaille une planche ; rien de la Bibliothèque n'y vit",
    "/recherche": "rien de la Bibliothèque n'y vit",
    "/exploration": "rien de la Bibliothèque n'y vit",
}


def _client(base):
    return httpx.Client(base_url=base, trust_env=False, timeout=60, headers=ECRITURE)


@pytest.fixture
def decor(live_server):
    """Un album d'une planche, dans la collection de repli."""
    with _client(live_server) as c:
        aid = c.post("/api/albums", json={"titre": "Validable", "auteur": "X"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
    return {"base": live_server, "album": aid, "planche": pid}


def _ouvrir_album(page, titre):
    """Ouvre la fiche d'un album depuis la liste de la Bibliothèque."""
    page.locator(".album-row", has_text=titre).first.click()
    page.wait_for_selector("#album-detail button[data-val]", timeout=5000)


def _validee(base, album, planche):
    with _client(base) as c:
        return next(p for p in c.get(f"/api/albums/{album}/planches").json()
                    if p["id"] == planche)["validee"]


def test_valider_est_un_bouton_qui_porte_son_etat(page, decor):
    """Valider une planche est UN bouton (tranché par Hugo le 2026-10-17) : ✔ non enfoncé
    tant qu'elle ne l'est pas, enfoncé quand elle l'est, et le même clic dans les deux sens.
    Le badge ✔ et le ↺ d'avant ont disparu : un seul contrôle par ligne, qui dit l'état.

    Ce que le test garde, c'est la BASCULE : un bouton qui enverrait toujours `true` (ou
    lirait son état à l'envers) laisserait la planche validée au second clic, et l'écran
    afficherait encore un bouton enfoncé — le serveur est donc interrogé après chaque clic,
    pas seulement l'écran."""
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    _ouvrir_album(page, "Validable")
    bouton = page.locator(f'button[data-val="{decor["planche"]}"]')
    expect(bouton).to_be_visible()
    expect(bouton).to_have_attribute("aria-pressed", "false")
    expect(bouton).to_have_text("✔")
    # Plus de badge à côté du bouton, ni de ↺ : un seul contrôle dit l'état.
    expect(page.locator("#album-detail .val-badge")).to_have_count(0)
    assert "↺" not in page.locator("#album-detail").inner_text()

    bouton.click()
    bouton = page.locator(f'button[data-val="{decor["planche"]}"]')
    expect(bouton).to_have_attribute("aria-pressed", "true", timeout=5000)
    assert _validee(decor["base"], decor["album"], decor["planche"]), (
        "le bouton s'est enfoncé sans que la planche soit validée au serveur")
    assert "↺" not in page.locator("#album-detail").inner_text()

    bouton.click()
    bouton = page.locator(f'button[data-val="{decor["planche"]}"]')
    expect(bouton).to_have_attribute("aria-pressed", "false", timeout=5000)
    assert not _validee(decor["base"], decor["album"], decor["planche"]), (
        "le second clic n'a pas retiré la validation : le bouton ne bascule pas")


@pytest.fixture
def trois_planches(live_server):
    """Un album de trois planches, la première déjà validée."""
    with _client(live_server) as c:
        aid = c.post("/api/albums", json={"titre": "Trois"}).json()["id"]
        pids = [c.post(f"/api/albums/{aid}/import",
                       files={"file": (f"p{i}.png", make_png(), "image/png")}).json()["id"]
                for i in range(3)]
        assert c.patch(f"/api/planches/{pids[0]}/validation",
                       json={"validee": True}).status_code == 200
    return {"base": live_server, "album": aid, "planches": pids}


def test_tout_valider_part_en_une_seule_requete(page, trois_planches):
    """« Tout valider » est UN geste (UX-18) : une requête `POST …/valider`, aucun `PATCH`
    par planche, et le nombre annoncé est celui que le serveur a validé. Les requêtes
    PARTIES sont comptées, pas seulement l'état final : une rafale de `PATCH` arriverait au
    même album validé."""
    d = trois_planches
    parties = []
    page.on("request", lambda r: parties.append((r.method, r.url))
            if "/valid" in r.url or r.url.endswith("/valider") else None)
    page.on("dialog", lambda dlg: dlg.accept())
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    _ouvrir_album(page, "Trois")
    page.locator("#detail-validate-all").click()
    msg = page.locator("#detail-valider-msg")
    expect(msg).to_have_text("2 planches validées.", timeout=5000)
    assert parties == [("POST", d["base"] + f"/api/albums/{d['album']}/valider")], parties
    assert all(_validee(d["base"], d["album"], p) for p in d["planches"])
    for p in d["planches"]:
        expect(page.locator(f'button[data-val="{p}"]')).to_have_attribute("aria-pressed", "true")


def test_tout_valider_qui_echoue_dit_qu_il_n_a_rien_valide(page, trois_planches):
    """Le serveur valide tout ou rien : un échec ne se lit plus « N validées avant
    l'échec », mais « aucune », et l'écran le dit là où l'on a agi."""
    d = trois_planches
    page.route(f"**/api/albums/{d['album']}/valider", lambda route: route.fulfill(
        status=409, content_type="application/json",
        body='{"detail": "base occupée (joué)"}'))
    page.on("dialog", lambda dlg: dlg.accept())
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    _ouvrir_album(page, "Trois")
    page.locator("#detail-validate-all").click()
    msg = page.locator("#detail-valider-msg")
    expect(msg).to_have_text("Aucune planche validée : base occupée (joué)", timeout=5000)
    expect(msg).to_have_class(re.compile(r"\berreur\b"))


def test_un_lot_nomme_ses_albums_et_ses_erreurs_se_lisent(page, calques):
    """Chaque lot dit SUR QUOI il travaille — ses albums, ou « N planches de « Titre » » —,
    lu dans `albums` que `GET /api/jobs` rend ; et ses erreurs s'ouvrent sur place. Le
    serveur est remplacé : ce test garde ce que l'écran fait de la réponse ; ce que la
    route rend, et à qui, se garde dans `tests/test_validation_lot.py`."""
    d = calques
    lots = [
        {"id": 7, "passes": ["segmenter", "bulles"], "total": 2, "done": 2, "current": None,
         "status": "termine", "errors": [{"planche_id": 31, "passe": "bulles",
                                          "erreur": "moteur en panne (joué)"}],
         "albums": [{"id": 1, "titre": "Tintin", "nb_planches": 2}]},
        {"id": 6, "passes": ["ocr"], "total": 3, "done": 3, "current": None,
         "status": "termine", "errors": [],
         "albums": [{"id": 1, "titre": "Tintin", "nb_planches": 1},
                    {"id": 2, "titre": "Île", "nb_planches": 2}]},
    ]
    page.route("**/api/jobs", lambda route: route.fulfill(
        status=200, content_type="application/json", body=json.dumps(lots))
        if route.request.method == "GET" else route.continue_())
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    jobs = page.locator("#jobs .job")
    expect(jobs).to_have_count(2)
    expect(jobs.nth(0).locator(".job-sujet")).to_have_text("2 planches de « Tintin »")
    expect(jobs.nth(1).locator(".job-sujet")).to_have_text("« Tintin » et « Île » — 3 planches")
    erreurs = jobs.nth(0).locator("details.job-erreurs")
    expect(erreurs).to_be_visible()
    erreurs.locator("summary").click()
    expect(erreurs.locator("li")).to_have_text("Planche 31 · bulles : moteur en panne (joué)")


# ── La collection en CALQUE (Hugo, 2026-10-16) ─────────────────────────────────────────

@pytest.fixture
def calques(live_server):
    """Mono-poste. Trois albums sur deux collections : « Tintin » dans A, « Île » dans A et
    B, « Gaston » dans B seule."""
    with _client(live_server) as c:
        a = c.post("/api/collections", json={"nom": "Étude A"}).json()["id"]
        b = c.post("/api/collections", json={"nom": "Étude B"}).json()["id"]
        ids = {}
        for titre, cols in (("Tintin", [a]), ("Île", [a, b]), ("Gaston", [b])):
            ids[titre] = c.post("/api/albums", json={"titre": titre,
                                                     "collection_id": cols[0]}).json()["id"]
            for x in cols[1:]:
                assert c.put(f"/api/albums/{ids[titre]}/collections/{x}").status_code == 201
            c.post(f"/api/albums/{ids[titre]}/import",
                   files={"file": ("p.png", make_png(), "image/png")})
    return {"base": live_server, "a": a, "b": b, "albums": ids}


def _albums(page):
    return page.locator("#albums-body .album-row .c-titre").all_inner_texts()


def _noms_des_collections(page):
    return page.locator("#col-body .col-item .col-nom").all_inner_texts()


def test_cocher_une_collection_filtre_les_albums_sur_les_siens(page, calques):
    """La case FILTRE : une collection cochée ne montre que ses albums, chacun nommant ses
    collections ; deux cochées, l'une OU l'autre — et « dans toutes » l'intersection — ; et
    la fiche suit : la collection seule, puis la comparaison. « Tout ce que vous lisez »
    défait le calque."""
    d = calques
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    expect(page.locator("#albums-body .album-row")).to_have_count(3)
    expect(page.locator("#albums-body .album-row", has_text="Île").locator(".lf-detail")) \
        .to_have_text("Étude A · Étude B")

    page.locator(f'#col-body [data-calque="{d["a"]}"]').check()
    expect(page.locator("#albums-body .album-row")).to_have_count(2)
    assert sorted(_albums(page)) == ["Tintin", "Île"]
    expect(page.locator("#bi-compte")).to_have_text("2 albums sur 3")
    # La fiche est celle de la collection cochée, sur ses albums.
    fiche = page.locator(f'#col-fiche[data-id="{d["a"]}"]')
    expect(fiche.locator('[role="tab"][data-onglet="albums"]')).to_have_attribute(
        "aria-selected", "true")
    expect(fiche.locator("#panneau-albums .col-album")).to_have_count(2)
    expect(fiche.locator(".col-album", has_text="Île").locator(".c-aussi")).to_have_text("Étude B")

    page.locator(f'#col-body [data-calque="{d["b"]}"]').check()
    expect(page.locator("#albums-body .album-row")).to_have_count(3)
    expect(page.locator(".bi-comparaison")).to_be_visible()
    expect(page.locator(".lf-puce", has_text="dans les deux")).to_have_text("dans les deux : 1")
    # Accordé au nombre : « les 1 en commun » se lisait.
    expect(page.locator('#biblio-fiche [data-mode-fiche="toutes"]')).to_have_text(
        "Ne montrer que le seul en commun")
    page.locator('#calques-mode [data-mode="toutes"]').click()
    expect(page.locator("#albums-body .album-row")).to_have_count(1)
    assert _albums(page) == ["Île"]

    page.locator("#calques-tout").click()
    expect(page.locator("#albums-body .album-row")).to_have_count(3)
    expect(page.locator("#bi-accueil-titre")).to_be_visible()
    expect(page.locator("#col-body .col-calque:checked")).to_have_count(0)


def test_le_nom_ouvre_la_fiche_et_le_tri_se_choisit(page, calques):
    """Le NOM ouvre la fiche, sur « Qui entre », sans filtrer ; le tri est le contrôle de
    « Comptes et groupes » — par nom, ou la plus récente d'abord, la base du projet en tête."""
    d = calques
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    page.locator("#col-body .col-item").first.wait_for(timeout=5000)
    assert _noms_des_collections(page)[1:] == ["Étude A", "Étude B"], _noms_des_collections(page)
    page.locator('#collections-bloc [data-tri="recents"]').click()
    expect(page.locator('#collections-bloc [data-tri="recents"]')).to_have_attribute(
        "aria-pressed", "true")
    assert _noms_des_collections(page)[1:] == ["Étude B", "Étude A"], _noms_des_collections(page)

    page.locator(f'#col-body .col-item[data-id="{d["b"]}"] .col-ouvrir').click()
    fiche = page.locator(f'#col-fiche[data-id="{d["b"]}"]')
    expect(fiche.locator('[role="tab"][data-onglet="qui"]')).to_have_attribute(
        "aria-selected", "true")
    expect(page.locator("#albums-body .album-row")).to_have_count(3)   # rien n'est filtré
    expect(page.locator(f'#col-body .col-item[data-id="{d["b"]}"] .col-ouvrir')) \
        .to_have_attribute("aria-current", "true")


def test_la_fiche_d_une_collection_a_quatre_onglets(page, calques):
    """Quatre onglets, un seul panneau visible à la fois, les flèches passent de l'un à
    l'autre, et l'onglet ouvert vit dans l'adresse : il revient au rechargement."""
    d = calques
    page.goto(d["base"] + f"/corpus?collection={d['a']}", wait_until="networkidle")
    fiche = page.locator(f'#col-fiche[data-id="{d["a"]}"]')
    expect(fiche.locator('[role="tab"]')).to_have_text(
        ["Albums", "Qui entre", "Description", "Diffusion et dépôt"])
    expect(fiche.locator('[role="tabpanel"]:visible')).to_have_count(1)
    fiche.locator('[role="tab"][data-onglet="qui"]').focus()
    page.keyboard.press("ArrowRight")
    expect(fiche.locator('[role="tab"][data-onglet="description"]')).to_be_focused()
    expect(fiche.locator("#panneau-description")).to_be_visible()
    expect(fiche.locator('[role="tabpanel"]:visible')).to_have_count(1)
    assert "onglet=description" in page.url, page.url
    page.reload(wait_until="networkidle")
    expect(page.locator(f'#col-fiche[data-id="{d["a"]}"] #panneau-description')).to_be_visible()
    # Les droits en ACTES, chacun présent : le mono-poste peut tout.
    expect(page.locator("#col-fiche .droits li")).to_have_text(
        ["lire : oui", "annoter et organiser : oui", "exporter : oui", "décider qui entre : oui"])


def test_l_album_ouvert_vit_dans_l_adresse_et_le_retour_le_defait(page, calques):
    """La fiche d'un album s'ouvre À LA PLACE de celle de la collection, avec le retour vers
    elle ; l'adresse le dit, le rechargement le rouvre, « Précédent » revient à la collection."""
    d = calques
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    page.locator(f'#col-body [data-calque="{d["b"]}"]').check()
    page.locator(f'#col-fiche [data-ouvrir-album="{d["albums"]["Gaston"]}"]').click()
    expect(page.locator("#album-titre")).to_contain_text("Gaston")
    expect(page.locator("#col-fiche")).to_have_count(0)
    expect(page.locator("[data-retour-album]")).to_have_text("← Étude B")
    expect(page.locator("#album-range-cases label:has(input[data-ranger]:checked) .col-nom")
           ).to_have_text(["Étude B"])
    assert f"album={d['albums']['Gaston']}" in page.url, page.url
    expect(page.locator(f'#albums-body .album-row[data-id="{d["albums"]["Gaston"]}"]')) \
        .to_have_attribute("aria-current", "true")

    page.reload(wait_until="networkidle")
    expect(page.locator("#album-titre")).to_contain_text("Gaston")
    page.locator("[data-retour-album]").click()
    expect(page.locator(f'#col-fiche[data-id="{d["b"]}"]')).to_be_visible()
    page.go_back()
    expect(page.locator("#album-titre")).to_contain_text("Gaston")


# ── Les droits d'un album : l'union de ses collections ─────────────────────────────────

@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_les_droits_d_un_album_sont_l_union_de_ses_collections(page, live_server):
    """Zoé LIT « Lue » et ÉCRIT dans « Écrite » ; l'album y est rangé des deux côtés. Ouvert
    par la collection qu'elle ne fait que LIRE, la fiche de l'album lui propose ses gestes
    d'écriture : écrire dans UNE collection de l'album suffit (le serveur le tranche ainsi).
    « Vos droits ici » de « Lue », lui, ne dit pas « annoter » : il ne parle que d'elle."""
    with _client(live_server) as c:
        lue = c.post("/api/collections", json={"nom": "Lue"}).json()["id"]
        ecrite = c.post("/api/collections", json={"nom": "Écrite"}).json()["id"]
        aid = c.post("/api/albums", json={"titre": "Partagé", "collection_id": lue}).json()["id"]
        assert c.put(f"/api/albums/{aid}/collections/{ecrite}").status_code == 201
        c.post(f"/api/albums/{aid}/import", files={"file": ("p.png", make_png(), "image/png")})
        for cid, niveau in ((lue, "lecture"), (ecrite, "ecriture")):
            assert c.put(f"/api/collections/{cid}/acces", json={
                "genre": "utilisateur", "principal": "zoe", "niveau": niveau}).status_code == 200
    page.set_extra_http_headers({"Remote-User": "zoe"})
    page.goto(live_server + "/corpus", wait_until="networkidle")
    page.locator(f'#col-body [data-calque="{lue}"]').check()
    fiche = page.locator(f'#col-fiche[data-id="{lue}"]')
    expect(fiche.locator('.droits [data-acte="ecrire"]')).to_have_class("non")
    # Dans l'onglet de la collection lue, la ligne de l'album porte quand même ses gestes.
    expect(fiche.locator(f'.col-album[data-id="{aid}"] [data-act="supprimer"]')).to_be_visible()
    fiche.locator(f'[data-ouvrir-album="{aid}"]').click()
    expect(page.locator("[data-retour-album]")).to_have_text("← Lue")
    expect(page.locator('#album-detail [data-act="supprimer"]')).to_be_visible()
    expect(page.locator("#detail-edit")).to_be_visible()
    expect(page.locator("#album-detail button[data-val]")).to_have_count(1)
    # « Sur les collections » : la case de la collection où elle écrit s'offre, pas l'autre.
    page.locator("#album-range[data-pret]").wait_for(timeout=5000)
    expect(page.locator(f'#album-range-cases input[data-ranger="{ecrite}"]')).to_be_enabled()
    expect(page.locator(f'#album-range-cases input[data-ranger="{lue}"]')).to_be_disabled()


# ── Le lot, au-dessus de sa sélection ──────────────────────────────────────────────────

def test_le_lot_n_apparait_qu_au_dessus_d_une_selection(page, calques):
    """Sans sélection, une phrase dit comment en faire une ; un album coché fait paraître
    les passes et « Lancer », et le lot part sur les albums cochés DE CETTE collection, sans
    planche — un lot porte sur des albums OU sur les planches d'un album."""
    d = calques
    page.goto(d["base"] + f"/corpus?collection={d['a']}&onglet=albums", wait_until="networkidle")
    panneau = page.locator("#panneau-albums")
    expect(panneau.locator(".bi-lot")).to_have_count(0)
    expect(panneau.locator(".bi-lot-aide")).to_contain_text("Cochez des albums")
    panneau.locator(f'[data-coche-album="{d["albums"]["Tintin"]}"]').check()
    lot = panneau.locator(".bi-lot")
    expect(lot).to_contain_text("1 album sélectionné")
    expect(lot.locator("[data-lancer]")).to_be_disabled()
    lot.locator('[data-passe="segmenter"]').check()
    expect(lot.locator("[data-lancer]")).to_be_enabled()
    corps = []

    def intercepter(route):
        if route.request.method != "POST":
            route.continue_()
            return
        corps.append(route.request.post_data_json)
        route.fulfill(status=503, content_type="application/json",
                      body='{"detail": "moteur absent (joué)"}')

    page.route("**/api/jobs", intercepter)
    lot.locator("[data-lancer]").click()
    page.wait_for_timeout(300)
    assert corps == [{"passes": ["segmenter"], "album_ids": [d["albums"]["Tintin"]],
                      "planche_ids": []}], corps
    lot.locator("[data-vider]").click()
    expect(panneau.locator(".bi-lot")).to_have_count(0)


# ── Sous le seuil étroit : des CARTES, et la corbeille reste visible ───────────────────

@pytest.mark.parametrize("largeur", [320, 375])
@pytest.mark.parametrize("police", [16, 24])
def test_la_corbeille_d_une_planche_reste_dans_le_champ(page, calques, largeur, police):
    """Tranché par Hugo le 2026-10-16 : sous une fiche étroite, des cartes ; les gestes d'une
    planche suivent son NOM. La corbeille — dernière colonne d'un tableau qui défilait —
    tombait hors champ ; elle doit se VOIR, à 320 et 375 px, en police normale et grande :
    le point en son centre la désigne elle-même, dans la fenêtre."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": police, "fixed": police}})
    page.set_viewport_size({"width": largeur, "height": 900})
    aid = calques["albums"]["Tintin"]
    page.goto(calques["base"] + f"/corpus?album={aid}", wait_until="networkidle")
    corbeille = page.locator("#album-detail button[data-delp]").first
    corbeille.wait_for(timeout=5000)
    corbeille.scroll_into_view_if_needed()
    vu = corbeille.evaluate("""el => {
      const r = el.getBoundingClientRect();
      const x = r.left + r.width / 2, y = r.top + r.height / 2;
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return false;
      const t = document.elementFromPoint(x, y);
      return !!t && (t === el || el.contains(t));
    }""")
    assert vu, f"la corbeille d'une planche est hors champ à {largeur} px, police {police}"
    assert page.locator("#album-detail .planches-table thead").is_hidden(), (
        "la fiche étroite n'est pas passée en cartes")


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_la_corbeille_d_une_planche_se_voit_au_repos(page, calques, theme):
    """Relevé par Hugo le 2026-10-19, en passe de QA : en thème clair, la corbeille ne se
    voyait qu'au survol. Elle héritait du blanc de `.danger` sur un fond transparent, et 🗑
    se dessine sous Windows en glyphe d'une couleur, celle du texte : blanc sur blanc.
    Au REPOS, la couleur de son glyphe doit trancher sur le fond qu'elle laisse voir (3:1, le
    seuil d'un élément graphique) — une mesure, pas la règle CSS, qu'un autre sélecteur
    pourrait battre."""
    page.add_init_script(f"localStorage.setItem('bd-theme','{theme}')")
    aid = calques["albums"]["Tintin"]
    page.goto(calques["base"] + f"/corpus?album={aid}", wait_until="networkidle")
    corbeille = page.locator("#album-detail button[data-delp]").first
    corbeille.wait_for(timeout=5000)
    page.mouse.move(0, 0)
    contraste = corbeille.evaluate("""el => {
      const rgb = s => (s.match(/[\\d.]+/g) || []).map(Number);
      const lum = ([r, g, b]) => {
        const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; };
        return .2126 * f(r) + .7152 * f(g) + .0722 * f(b);
      };
      let fond = el, c;
      while (fond) {
        c = rgb(getComputedStyle(fond).backgroundColor);
        if (c.length >= 3 && (c.length < 4 || c[3] > 0)) break;
        fond = fond.parentElement;
      }
      const a = lum(rgb(getComputedStyle(el).color)), b = lum(c);
      return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
    }""")
    assert contraste >= 3, (
        f"thème {theme} : la corbeille au repos ne tranche pas sur son fond "
        f"({contraste:.2f}:1) — elle ne se voit qu'au survol")
