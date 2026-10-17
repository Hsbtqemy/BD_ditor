"""COL-3, tranche 3a — l'écran de l'Administration, tranché par Hugo sur maquette le
2026-10-17, dans un navigateur.

Le serveur est mesuré par `tests/test_prendre.py` et `tests/test_ecran_3a.py`. Ce fichier
mesure ce que l'ÉCRAN en fait, et que rien d'autre ne verrait :

- « À faire » rend CINQ genres de demandes, chacun avec SES mots et SES boutons, une couleur
  de tranche par genre — jamais « Détruire / Garder » hors d'une suppression de document ;
  l'entrée se répond document par document, « Tout accepter (n) », « Refuser le reste » ;
- la fiche d'un projet règle « Ce que la base ouvre aux membres » (une phrase AVANT
  d'appliquer), dit ses demandes au fonds et ses copies gardées, et « Demander à la
  rendre… » part comme un retour ;
- « + Nouveau projet » pose la question de la position, « ouverte » présélectionnée ;
- la fiche d'un document dit ses copies de travail, la notice divergente, et « Prendre
  dans… » fait la prise ; le filtre « Plusieurs copies » ;
- « Qui entre » d'une collection de base se lit en deux groupes, dans ses DEUX montages ;
- tout cela tient à 320 px sous une grande police.

Chaque geste est mesuré sur la requête PARTIE, pas seulement sur l'état final : le serveur
répondrait juste à un écran qui enverrait autre chose.
"""
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.parametrize("live_server", [True], indirect=True)]

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/administration", "/corpus")
SURFACES_HORS_PERIMETRE = {
    "/": "l'Atelier ne montre ni demande, ni projet, ni accès à régler",
    "/recherche": "la Recherche interroge le corpus ; rien de la 3a ne s'y montre",
    "/exploration": "l'Exploration mesure la langue du corpus ; rien de la 3a ne s'y montre",
}

EN_TETE = next(k for k in ECRITURE if k not in ("Remote-User", "Remote-Groups"))
ADMIN = {**ECRITURE}


def _comme(login, **plus):
    return {"Remote-User": login, EN_TETE: "1", **plus}


def _client(base, entetes=None):
    return httpx.Client(base_url=base, trust_env=False, timeout=60, headers=entetes or ADMIN)


def _ok(r, *codes):
    assert r.status_code in (codes or (200, 201)), r.text
    return r.json() if r.content else None


def _album(c, titre, cid):
    a = _ok(c.post("/api/albums", json={"titre": titre, "collection_id": cid}))["id"]
    _ok(c.post(f"/api/albums/{a}/import", files={"file": ("p.png", make_png(), "image/png")}))
    return a


def _document_de(c, album_id):
    return next(d["id"] for d in c.get("/api/fonds").json()["documents"]
                if any(x["album_id"] == album_id for x in d["copies"]))


@pytest.fixture
def decor(live_server):
    """« Séminaire » : `rui` responsable, `mia` membre, sa base OUVERTE ; « Lot A » que
    possède `ana` (`sam` la lit), « Lot B » où `sam` écrit. Dans le repli, « Archives ».
    Les cinq genres de demandes attendent, un de chaque."""
    base = live_server
    with _client(base) as c:
        p = _ok(c.post("/api/projets", json={"nom": "Séminaire"}))
        pid, bid = p["id"], p["base"]["id"]
        for qui, role in (("rui", "responsable"), ("mia", "membre")):
            _ok(c.put(f"/api/projets/{pid}/membres", json={"principal": qui, "role": role}))
        lot_a = _ok(c.post("/api/collections", json={"nom": "Lot A", "projet_id": pid}))["id"]
        lot_b = _ok(c.post("/api/collections", json={"nom": "Lot B", "projet_id": pid}))["id"]
        archives = _ok(c.post("/api/collections", json={"nom": "Archives"}))["id"]
        for cid, qui, niveau in ((lot_a, "ana", "proprietaire"), (lot_a, "sam", "lecture"),
                                 (lot_b, "sam", "ecriture")):
            _ok(c.put(f"/api/collections/{cid}/acces",
                      json={"genre": "utilisateur", "principal": qui, "niveau": niveau}))
        albums = {t: _album(c, t, lot_a) for t in ("Lotus", "Oreille", "Gardé")}
        albums["Hors"] = _album(c, "Hors", archives)
        albums["Ailleurs"] = _album(c, "Ailleurs", archives)
        _ok(c.delete(f"/api/albums/{albums['Gardé']}/collections/{lot_a}"), 204)
        docs = {t: _document_de(c, a) for t, a in albums.items()}
        # Une SŒUR de « Lotus » dans la base, dont la notice dit un autre titre (D7).
        r = _ok(c.post(f"/api/collections/{bid}/prendre",
                       json={"documents": [{"document_id": docs["Lotus"], "reponse": "zero"}]}))
        soeur = r["documents"][0]["copie_id"]
        _ok(c.put(f"/api/albums/{soeur}", json={"titre": "Lotus (réédition)"}))
        vide = _ok(c.post("/api/projets", json={"nom": "Vide"}))["id"]
        _ok(c.put(f"/api/projets/{vide}/membres", json={"principal": "zoe",
                                                       "role": "responsable"}))
    demandes = {}
    with _client(base, _comme("ana")) as c:
        demandes["document"] = _ok(c.post("/api/demandes", json={
            "genre": "suppression_document", "album_id": albums["Oreille"],
            "motif": "Doublon.", "certifie": True}))["id"]
    with _client(base, _comme("rui")) as c:
        r = _ok(c.post(f"/api/projets/{pid}/prendre", json={
            "documents": [{"document_id": docs["Hors"], "reponse": "zero"},
                          {"document_id": docs["Ailleurs"], "reponse": "zero"}],
            "motif": "Pour le séminaire."}))
        demandes["entree"] = r["documents"][0]["demande_id"]
        r = _ok(c.post(f"/api/collections/{bid}/prendre", json={"documents": [
            {"document_id": docs["Gardé"], "reponse": "reprendre",
             "album_id": albums["Gardé"]}]}))
        demandes["rendre"] = r["documents"][0]["demande_id"]
    with _client(base, _comme("sam")) as c:
        demandes["rejoindre"] = _ok(c.put(
            f"/api/albums/{albums['Lotus']}/collections/{lot_b}"), 202)["demande_id"]
    with _client(base, _comme("zoe")) as c:
        demandes["projet"] = _ok(c.post("/api/demandes", json={
            "genre": "suppression_projet", "projet_id": vide, "motif": "Fini."}))["id"]
    return {"base": base, "projet": pid, "base_id": bid, "lot_a": lot_a, "lot_b": lot_b,
            "albums": albums, "docs": docs, "soeur": soeur, "demandes": demandes}


def _ouvrir(page, base, entetes=None, chemin="/administration"):
    page.set_extra_http_headers({k: v for k, v in (entetes or ADMIN).items() if k != EN_TETE})
    page.goto(base + chemin, wait_until="networkidle")


def _ligne_af(page, demande_id):
    return page.locator(f"#fd-demande-{demande_id}")


def _deplier(page, demande_id):
    ligne = _ligne_af(page, demande_id)
    ligne.locator("[data-af-deplier]").click()
    expect(ligne.locator(".af-detail")).to_be_visible()
    return ligne


# ── « À faire » : cinq genres, chacun ses mots ──────────────────────────────────────────


def test_a_faire_rend_cinq_genres_chacun_avec_ses_mots(page, decor):
    d = decor
    _ouvrir(page, d["base"])
    lignes = page.locator("#af-demandes-liste > li")
    expect(lignes).to_have_count(5, timeout=5000)
    attendus = {
        "document": ("Supprimer un document", "af-genre-document", "Détruire", "Garder"),
        "projet": ("Supprimer un projet", "af-genre-projet", "Supprimer le projet", "Garder"),
        "entree": ("Entrée de documents", "af-genre-entree", "Tout accepter (2)",
                   "Refuser le reste"),
        "rejoindre": ("Rejoindre un travail", "af-genre-rejoindre",
                      "Accepter : ranger aussi dans « Lot B »", "Refuser"),
        "rendre": ("Rendre une copie gardée", "af-genre-rendre",
                   "Rendre à « Séminaire »", "Garder au fonds"),
    }
    couleurs = set()
    for genre, (libelle, classe, accepter, refuser) in attendus.items():
        ligne = _deplier(page, d["demandes"][genre])
        expect(ligne).to_have_class(re.compile(classe))
        expect(ligne.locator(".af-genre-nom")).to_have_text(libelle)
        expect(ligne.locator(".fd-gestes [data-fd-accepter]")).to_have_text(accepter)
        expect(ligne.locator(".fd-gestes [data-fd-refuser]")).to_have_text(refuser)
        if genre not in ("document", "projet"):
            expect(ligne.locator(".af-detail")).not_to_contain_text("Détruire")
            expect(ligne.locator(".fd-demande-texte")).not_to_contain_text("suppression")
        couleurs.add(page.evaluate(
            "(el) => getComputedStyle(el).borderLeftColor", ligne.element_handle()))
    assert len(couleurs) == 5, couleurs


def test_rendre_et_rejoindre_partent_avec_leur_reponse(page, decor):
    d = decor
    _ouvrir(page, d["base"])
    ligne = _deplier(page, d["demandes"]["rendre"])
    with page.expect_request(lambda r: r.method == "POST"
                             and r.url.endswith(f"/api/demandes/{d['demandes']['rendre']}/reponse")
                             ) as partie:
        ligne.locator("[data-fd-accepter]").click()
    assert partie.value.post_data_json == {"reponse": "acceptee"}
    expect(page.locator("#af-msg")).to_contain_text("« Gardé » est rendu à « Séminaire »")
    expect(_ligne_af(page, d["demandes"]["rendre"])).to_have_count(0)
    ligne = _deplier(page, d["demandes"]["rejoindre"])
    with page.expect_request(lambda r: r.method == "POST" and "/reponse" in r.url) as partie:
        ligne.locator("[data-fd-refuser]").click()
    assert partie.value.post_data_json == {"reponse": "refusee"}
    expect(page.locator("#af-msg")).to_contain_text("rien n'est rangé")
    with _client(d["base"]) as c:
        vues = {x["id"]: x for x in c.get("/api/demandes").json()}
    assert vues[d["demandes"]["rendre"]]["reponse"] == "acceptee"
    assert vues[d["demandes"]["rejoindre"]]["reponse"] == "refusee"


def test_une_entree_se_repond_document_par_document(page, decor):
    d = decor
    _ouvrir(page, d["base"])
    dem = d["demandes"]["entree"]
    ligne = _deplier(page, dem)
    docs = ligne.locator(".af-documents li")
    expect(docs).to_have_count(2)
    premier = docs.filter(has_text="Hors")
    with page.expect_request(lambda r: r.method == "POST" and "/reponse" in r.url) as partie:
        premier.locator("[data-fd-accepter]").click()
    assert partie.value.post_data_json == {"reponse": "acceptee",
                                           "document_id": d["docs"]["Hors"]}
    ligne = _ligne_af(page, dem)
    expect(ligne.locator(".af-documents li", has_text="Hors")).to_contain_text(
        "entré dans « Séminaire »")
    expect(ligne.locator(".fd-gestes [data-fd-accepter]")).to_have_text("Tout accepter (1)")
    expect(ligne.locator(f"#fd-demande-msg-{dem}")).to_contain_text("« Hors » entre dans")
    with page.expect_request(lambda r: r.method == "POST" and "/reponse" in r.url) as partie:
        ligne.locator(".fd-gestes [data-fd-refuser]").click()
    assert partie.value.post_data_json == {"reponse": "refusee"}
    expect(_ligne_af(page, dem)).to_have_count(0)
    with _client(d["base"]) as c:
        vue = {x["id"]: x for x in c.get("/api/demandes").json()}[dem]
    assert vue["reponse"] == "partielle"


def test_a_regarder_ne_dit_suppression_que_d_une_suppression(page, decor):
    d = decor
    _ouvrir(page, d["base"], chemin="/administration?vue=comptes")
    signaux = page.locator("#cg-signaux")
    expect(signaux.locator("button", has_text="demande à rendre")).to_have_count(1,
                                                                                 timeout=5000)
    texte = signaux.inner_text()
    assert texte.count("suppression") == 2, texte


# ── La fiche du projet ──────────────────────────────────────────────────────────────────


def _fiche_projet(page, d, entetes):
    _ouvrir(page, d["base"], entetes, f"/administration?vue=projets&projet={d['projet']}")
    expect(page.locator("#pj-fiche-titre")).to_have_text("Séminaire", timeout=5000)
    return page.locator("#pj-fiche")


def test_la_base_se_regle_avec_une_phrase_avant_d_appliquer(page, decor):
    d = decor
    fiche = _fiche_projet(page, d, _comme("rui"))
    zone = fiche.locator("#pj-base-zone")
    expect(zone.locator("input[value=ecriture]")).to_be_checked()
    expect(zone.locator(".pj-position")).to_have_count(3)
    zone.locator("label.pj-position", has_text="protégée").click()
    expect(zone.locator(".pj-position-confirme")).to_contain_text(
        "Resserrer n'efface aucun travail")
    with page.expect_request(lambda r: r.method == "PUT"
                             and r.url.endswith(f"/api/projets/{d['projet']}/acces-membres")
                             ) as partie:
        zone.locator("[data-pj-position-ok]").click()
    assert partie.value.post_data_json == {"acces_membres": None}
    expect(fiche.locator("#pj-position-msg")).to_contain_text("protégée")
    zone.locator("label.pj-position", has_text="ouverte").click()
    expect(zone.locator(".pj-position-confirme")).to_contain_text(
        "Ouvrir donne à 1 entrée du projet le droit d'annoter")
    zone.locator("[data-pj-position-annuler]").click()
    expect(zone.locator(".pj-position-confirme")).to_have_count(0)
    expect(zone.locator('input[value=""]')).to_be_checked()


def test_la_fiche_dit_les_demandes_au_fonds_et_rend_une_copie_gardee(page, decor):
    d = decor
    with _client(d["base"]) as c:            # le retour du décor reçoit d'abord sa réponse
        _ok(c.post(f"/api/demandes/{d['demandes']['rendre']}/reponse",
                   json={"reponse": "refusee"}))
    fiche = _fiche_projet(page, d, _comme("rui"))
    fonds = fiche.locator("#pj-fonds-zone")
    expect(fonds.locator("h4").first).to_have_text("Au fonds · 2 demandes", timeout=5000)
    entree = fonds.locator(".pj-demande", has_text="2 documents pour « Séminaire »")
    expect(entree.locator(".af-etat")).to_have_text("en attente")
    entree.locator("[data-pj-detail]").click()
    expect(fonds.locator(".pj-demande-docs li")).to_have_count(2)
    expect(fonds.locator(".pj-demande", has_text="Rendre « Gardé »").locator(".af-etat")
           ).to_have_text("refusée")
    expect(fonds.locator(".pj-gardees-titre")).to_have_text("Copies gardées au fonds · 1")
    fonds.locator("[data-pj-rendre]").click()
    choix = fonds.locator(f"#pj-rendre-{d['albums']['Gardé']}")
    expect(choix).to_be_focused()
    with page.expect_request(lambda r: r.method == "POST" and r.url.endswith(
            f"/api/collections/{d['base_id']}/prendre")) as partie:
        fonds.locator("[data-pj-rendre-ok]").click()
    assert partie.value.post_data_json == {"documents": [{
        "document_id": d["docs"]["Gardé"], "reponse": "reprendre",
        "album_id": d["albums"]["Gardé"]}]}
    expect(fiche.locator("#pj-fonds-msg")).to_contain_text("partie à un administrateur")
    expect(fonds.locator(".pj-gardee .af-etat")).to_contain_text("retour demandé")


def test_un_nouveau_projet_dit_ce_que_sa_base_ouvre(page, decor):
    d = decor
    _ouvrir(page, d["base"], chemin="/administration?vue=projets")
    page.locator("#pj-creer-ouvrir").click()
    expect(page.locator('input[name="pj-creer-position"][value=ecriture]')).to_be_checked()
    page.locator("#pj-nom").fill("Lecture seule")
    page.locator("label.pj-position", has_text="en lecture").click()
    with page.expect_request(lambda r: r.method == "POST"
                             and r.url.endswith("/api/projets")) as partie:
        page.locator("#pj-ajouter").click()
    assert partie.value.post_data_json == {"nom": "Lecture seule", "acces_membres": "lecture"}
    expect(page.locator("#pj-fiche-titre")).to_have_text("Lecture seule")
    expect(page.locator('#pj-base-zone input[value=lecture]')).to_be_checked()


# ── La fiche d'un document : ses copies, « Prendre dans… » ─────────────────────────────


def test_les_copies_d_un_document_et_prendre_dans(page, decor):
    d = decor
    _ouvrir(page, d["base"], chemin="/administration?vue=fonds")
    page.locator('#fd [data-fd-etat="soeurs"]').click()
    expect(page.locator('#fd [data-fd-etat="soeurs"]')).to_have_text("Plusieurs copies 1")
    objets = page.locator("#fd-objets .fd-objet")
    expect(objets).to_have_count(1)
    objets.first.click()
    fiche = page.locator("#fd-fiche")
    expect(fiche.locator(".fd-copies-section h4")).to_have_text("Copies de travail · 2")
    copies = fiche.locator(".fd-copie")
    expect(copies.filter(has_text="notice divergente")).to_have_count(1)
    expect(copies.filter(has_text="Lotus (réédition)")).to_contain_text(
        "copie vierge, images partagées")
    fiche.locator("[data-fd-prendre]").click()
    choix = fiche.locator("#fd-prendre-dest")
    expect(choix).to_be_focused()
    groupe = choix.locator('optgroup[label="Séminaire"] option')
    expect(groupe.first).to_have_text("Séminaire (base)")
    choix.select_option(str(d["lot_b"]))
    with page.expect_request(lambda r: r.method == "POST" and r.url.endswith(
            f"/api/collections/{d['lot_b']}/prendre")) as partie:
        fiche.locator("[data-fd-prendre-ok]").click()
    assert partie.value.post_data_json == {"documents": [
        {"document_id": d["docs"]["Lotus"], "reponse": "zero"}]}
    expect(page.locator(f"#fd-doc-msg-{d['docs']['Lotus']}")).to_contain_text(
        "Fait : une copie vierge")
    expect(fiche.locator(".fd-copies-section h4")).to_have_text("Copies de travail · 3")


# ── « Qui entre » d'une base : deux groupes, dans ses deux montages ────────────────────


def _qui_entre_admin(page, d):
    _ouvrir(page, d["base"], chemin=f"/administration?axe=collections&collection={d['base_id']}")
    qui = page.locator("#cg-fiche section[data-qui-entre]")
    qui.locator(".qe-choix").wait_for(timeout=5000)
    return qui


def test_qui_entre_dans_la_base_en_deux_groupes_dans_l_administration(page, decor):
    d = decor
    qui = _qui_entre_admin(page, d)
    titres = qui.locator("tr.qe-groupe-ligne th")
    expect(titres).to_have_text(["Par le projet · 2", "Entrés ici · 0"])
    derives = qui.locator("tr.qe-derive")
    expect(derives).to_have_count(2)
    expect(derives.locator("input")).to_have_count(0)
    expect(derives.locator(".qe-retirer")).to_have_count(0)
    regler = derives.first.locator("a.qe-regler")
    expect(regler).to_have_attribute("href", f"/administration?vue=projets&projet={d['projet']}")
    expect(derives.filter(has_text="rui")).to_contain_text("responsable du projet")
    expect(qui).to_contain_text("Personne encore")
    qui.locator(".qe-choix").select_option("autre")
    qui.locator(".qe-nom").fill("eva")
    qui.locator(".qe-genre").select_option("utilisateur")
    qui.locator(".qe-faire-entrer").click()
    expect(titres).to_have_text(["Par le projet · 2", "Entrés ici · 1"])
    page.set_viewport_size({"width": 375, "height": 900})
    expect(qui.locator(".qe-groupe-titre")).to_have_text(["Par le projet · 2",
                                                          "Entrés ici · 1"])
    expect(qui.locator(".qe-cartes-projet .qe-carte")).to_have_count(2)
    expect(qui.locator(".qe-cartes-projet input")).to_have_count(0)


def test_qui_entre_dans_la_base_en_deux_groupes_dans_la_bibliotheque(page, decor):
    d = decor
    _ouvrir(page, d["base"], _comme("rui"), f"/corpus?collection={d['base_id']}")
    item = page.locator(f'#col-body .col-item[data-id="{d["base_id"]}"]')
    item.locator(".qe-choix").wait_for(timeout=5000)
    expect(item.locator("tr.qe-groupe-ligne th")).to_have_text(
        ["Par le projet · 2", "Entrés ici · 0"])
    expect(item.locator("tr.qe-derive input")).to_have_count(0)
    # Une collection ordinaire : un seul groupe, sans titre — le rendu d'avant.
    _ouvrir(page, d["base"], _comme("ana"), f"/corpus?collection={d['lot_a']}")
    item = page.locator(f'#col-body .col-item[data-id="{d["lot_a"]}"]')
    item.locator(".qe-choix").wait_for(timeout=5000)
    expect(item.locator("tr.qe-groupe-ligne")).to_have_count(0)


# ── À l'étroit ──────────────────────────────────────────────────────────────────────────


_SONDE = """() => [document.documentElement, document.body,
    ...document.querySelectorAll('main, #header, #afaire-bloc, #projets-bloc, #fonds-bloc')]
    .filter(Boolean).filter((el) => el.scrollWidth > el.clientWidth + 1)
    .map((el) => `${el.tagName}#${el.id} ${el.clientWidth}/${el.scrollWidth}`)"""


@pytest.mark.parametrize("police", [16, 24])
def test_a_320_px_rien_ne_defile_de_cote(page, decor, police):
    d = decor
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": police, "fixed": police}})
    page.set_viewport_size({"width": 320, "height": 900})
    _ouvrir(page, d["base"])
    for genre in ("entree", "rendre", "rejoindre"):
        _deplier(page, d["demandes"][genre])
    assert not page.evaluate(_SONDE), page.evaluate(_SONDE)
    fiche = _fiche_projet(page, d, _comme("rui"))
    expect(fiche.locator("#pj-fonds-zone h4").first).to_contain_text("Au fonds", timeout=5000)
    fiche.locator("label.pj-position", has_text="protégée").click()
    expect(fiche.locator(".pj-position-confirme")).to_be_visible()
    assert not page.evaluate(_SONDE), page.evaluate(_SONDE)
    _ouvrir(page, d["base"],
            chemin=f"/administration?vue=fonds&document={d['docs']['Lotus']}")
    page.locator("#fd-fiche [data-fd-prendre]").click()
    expect(page.locator("#fd-prendre-dest")).to_be_visible()
    assert not page.evaluate(_SONDE), page.evaluate(_SONDE)


# ── Accessibilité (WCAG 2.1 AA, axe) ────────────────────────────────────────────────────


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_de_l_ecran_de_la_3a(page, decor, theme):
    """Les états que l'audit générique de `/administration` ne voit pas : « À faire » aux
    cinq genres, dépliés ; la fiche d'un projet, une position changée et « Demander à la
    rendre… » ouvert ; « Qui entre » d'une base en deux groupes ; la fiche d'un document à
    deux copies, « Prendre dans… » ouvert."""
    from test_e2e_a11y import _audit, _fmt, _theme
    d = decor
    _theme(page, theme)
    _ouvrir(page, d["base"])
    for genre in ("document", "projet", "entree", "rejoindre", "rendre"):
        _deplier(page, d["demandes"][genre])
    viol = _audit(page)
    assert not viol, f"À faire, cinq genres [{theme}] :\n{_fmt(viol)}"
    with _client(d["base"]) as c:            # le retour du décor reçoit sa réponse : la
        _ok(c.post(f"/api/demandes/{d['demandes']['rendre']}/reponse",   # copie se redemande
                   json={"reponse": "refusee"}))
    fiche = _fiche_projet(page, d, _comme("rui"))
    fiche.locator("label.pj-position", has_text="en lecture").click()
    fiche.locator("[data-pj-rendre]").click()
    expect(fiche.locator(".pj-rendre select")).to_be_visible()
    viol = _audit(page)
    assert not viol, f"Fiche d'un projet [{theme}] :\n{_fmt(viol)}"
    _qui_entre_admin(page, d)
    viol = _audit(page)
    assert not viol, f"Qui entre d'une base [{theme}] :\n{_fmt(viol)}"
    _ouvrir(page, d["base"], chemin=f"/administration?vue=fonds&document={d['docs']['Lotus']}")
    page.locator("#fd-fiche [data-fd-prendre]").click()
    expect(page.locator("#fd-prendre-dest")).to_be_visible()
    viol = _audit(page)
    assert not viol, f"Fiche d'un document à deux copies [{theme}] :\n{_fmt(viol)}"
