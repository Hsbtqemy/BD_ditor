"""COL-3, tranche 3b — l'écran tranché par Hugo sur maquette le 2026-10-25, dans un
navigateur, chaque geste joué SOUS L'IDENTITÉ qui le voit, et ce que les autres NE voient pas.

Le serveur est mesuré par ses tests (`test_amorcer*.py`, `test_repartir.py`,
`test_retirer_du_projet.py`, `test_qui_efface.py`, `test_creer_collection.py`,
`test_ecran_3b_serveur.py`, `test_ecran_3b_complements.py`) ; les mots par
`tests/js/echelle.test.js` et `tests/js/suppression.test.js`. Ce fichier mesure ce que
l'ÉCRAN en fait :

- qui crée une collection : la case de la fiche du projet (Administration), et
  « + Créer une collection » éteint pour un membre, la raison qui nomme les responsables ;
- « Copie… » déplie l'échelle des crans en tableau, avec ce que chaque cran ajoute ; « Images
  seules » copie tout de suite, un cran au-dessus se demande à la propriétaire ;
- la propriétaire répond dans le bloc ⚑ ; la copie née le dit sur sa ligne ;
- entre deux projets : un cran PAR notice, « demandé » au bit près ; le responsable source
  répond dans la fiche du projet (Administration) et le lit dans la Bibliothèque ; le
  demandeur lit l'état, jamais le projet source ;
- « Repartir de zéro… » et ↺, leur panneau, « qui perd quoi », la puce de la copie remise à
  zéro ; une planche ne se demande pas ;
- « Supprimer… » dit le chemin réel (le responsable n'est jamais dit créateur), la dernière
  copie se demande ; « Retirer du projet… » et l'avis chez la propriétaire, jusqu'à « Vu » ;
- « À faire » : les deux tranches neuves, « attend … » ;
- un envoi se voit sur son bouton : « Envoi… », de la même largeur, puis le libellé, même
  en erreur ;
- la lectrice ne voit aucun de ces gestes ; tout tient à 320 px sous une grande police.

Chaque geste est mesuré sur la requête PARTIE, pas seulement sur l'état final : le serveur
répondrait juste à un écran qui enverrait autre chose.
"""
import json
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.parametrize("live_server", [True], indirect=True)]

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/corpus", "/administration")
SURFACES_HORS_PERIMETRE = {
    "/": "l'Atelier ne prend rien, ne repart de rien et ne retire rien",
    "/recherche": "la Recherche interroge le corpus ; rien de la 3b ne s'y montre",
    "/exploration": "l'Exploration mesure la langue du corpus ; rien de la 3b ne s'y montre",
}

EN_TETE = next(k for k in ECRITURE if k not in ("Remote-User", "Remote-Groups"))
ADMIN = {**ECRITURE}
NOMS = {"paule": "Paule Prop", "helene": "Helene Brunet", "noe": "Noe Stagiaire",
        "nico": "Nico Gauthier", "marion": "Marion Dumas", "lea": "Lea Lectrice"}


def _comme(login, **plus):
    """Le login, et son nom lisible : le miroir `utilisateur` suit le dernier en-tête reçu,
    et une requête sans `Remote-Name` effacerait le nom qu'une autre identité doit lire."""
    nom = {"Remote-Name": NOMS[login]} if login in NOMS else {}
    return {"Remote-User": login, EN_TETE: "1", **nom, **plus}


def _client(base, entetes=None):
    return httpx.Client(base_url=base, trust_env=False, timeout=60, headers=entetes or ADMIN)


def _ok(r, *codes):
    assert r.status_code in (codes or (200, 201)), r.text
    return r.json() if r.content else None


def _album(c, titre, cid):
    a = _ok(c.post("/api/albums", json={"titre": titre, "collection_id": cid}))["id"]
    pl = _ok(c.post(f"/api/albums/{a}/import",
                    files={"file": ("p.png", make_png(), "image/png")}))["id"]
    return a, pl


def _travailler(c, planche, texte=None):
    """Une région, et son texte : le découpage et la transcription."""
    r = _ok(c.post(f"/api/planches/{planche}/regions",
                   json={"type": "bulle", "x": 1, "y": 1, "w": 20, "h": 20}))["id"]
    if texte:
        _ok(c.put(f"/api/regions/{r}", json={"ocr_texte": texte}))
    return r


def _doc(c, album_id):
    return next(a["document_id"] for a in c.get("/api/albums").json() if a["id"] == album_id)


@pytest.fixture
def decor(live_server):
    """« Oralité » : `paule` responsable, `noe` membre. Corpus (Paule la possède, `nico` y
    écrit, `lea` la lit), Témoins (`helene` la possède, `noe` la lit), Exercices (Paule la
    possède, `noe` y écrit). « Onomatopées » : `marion` responsable, Inventaire qu'elle possède.

    Albums : « Gorille » dans Corpus ET Témoins, travaillé par Paule et Hélène — la DERNIÈRE
    copie de son document ; « QRN » dans Corpus, travaillé par Nico, avec une SŒUR dans
    Exercices ; « Zorglub » et « Spip » dans Témoins (Zorglub travaillé jusqu'à la
    transcription) ; « Pirates » dans Exercices, créé par Paule, découpé par Noé ;
    « Voyageur » (travaillé) et « Vierge » (rien) dans Inventaire."""
    base = live_server
    for login in NOMS:
        with _client(base, _comme(login)) as c:
            _ok(c.get("/api/moi"))
    with _client(base) as c:
        p = _ok(c.post("/api/projets", json={"nom": "Oralité"}))
        pid, bid = p["id"], p["base"]["id"]
        for qui, role in (("paule", "responsable"), ("noe", "membre")):
            _ok(c.put(f"/api/projets/{pid}/membres", json={"principal": qui, "role": role}))
        cols = {n: _ok(c.post("/api/collections", json={"nom": n, "projet_id": pid}))["id"]
                for n in ("Corpus", "Témoins", "Exercices")}
        o = _ok(c.post("/api/projets", json={"nom": "Onomatopées"}))
        oid = o["id"]
        _ok(c.put(f"/api/projets/{oid}/membres", json={"principal": "marion",
                                                      "role": "responsable"}))
        cols["Inventaire"] = _ok(c.post("/api/collections",
                                        json={"nom": "Inventaire", "projet_id": oid}))["id"]
        for nom, qui, niveau in (("Corpus", "paule", "proprietaire"), ("Corpus", "nico", "ecriture"),
                                 ("Corpus", "lea", "lecture"), ("Témoins", "helene", "proprietaire"),
                                 ("Témoins", "noe", "lecture"), ("Exercices", "paule", "proprietaire"),
                                 ("Exercices", "noe", "ecriture"),
                                 ("Inventaire", "marion", "proprietaire")):
            _ok(c.put(f"/api/collections/{cols[nom]}/acces",
                      json={"genre": "utilisateur", "principal": qui, "niveau": niveau}))
    albums, planches = {}, {}
    with _client(base, _comme("paule")) as c:
        for titre, col in (("Gorille", "Corpus"), ("QRN", "Corpus"), ("Pirates", "Exercices")):
            albums[titre], planches[titre] = _album(c, titre, cols[col])
        _travailler(c, planches["Gorille"], "BONJOUR")
    with _client(base) as c:
        _ok(c.put(f"/api/albums/{albums['Gorille']}/collections/{cols['Témoins']}"))
    with _client(base, _comme("helene")) as c:
        for titre in ("Zorglub", "Spip"):
            albums[titre], planches[titre] = _album(c, titre, cols["Témoins"])
        _travailler(c, planches["Gorille"], "SALUT")
        _travailler(c, planches["Zorglub"], "ZORGLONDE")
    with _client(base, _comme("nico")) as c:
        _travailler(c, planches["QRN"], "QRN")
    with _client(base, _comme("noe")) as c:
        _travailler(c, planches["Pirates"])
    with _client(base, _comme("marion")) as c:
        for titre in ("Voyageur", "Vierge"):
            albums[titre], planches[titre] = _album(c, titre, cols["Inventaire"])
        _travailler(c, planches["Voyageur"], "BOING")
    with _client(base) as c:
        docs = {t: _doc(c, a) for t, a in albums.items()}
    with _client(base, _comme("paule")) as c:
        r = _ok(c.post(f"/api/collections/{cols['Exercices']}/prendre", json={"documents": [
            {"document_id": docs["QRN"], "reponse": "zero", "album_id": albums["QRN"]}]}))
        soeur = r["documents"][0]["copie_id"]
    return {"base": base, "projet": pid, "base_id": bid, "ono": oid, "cols": cols,
            "albums": albums, "planches": planches, "docs": docs, "soeur": soeur}


def _ouvrir(page, d, login, chemin="/corpus", projet=None):
    if projet is not None:
        page.add_init_script(f"try {{ localStorage.setItem('bd-projet', '{projet}') }} catch (e) {{}}")
    entetes = ADMIN if login == "admin" else _comme(login)
    page.set_extra_http_headers({k: v for k, v in entetes.items() if k != EN_TETE})
    page.goto(d["base"] + chemin, wait_until="networkidle")


def _requetes(page, morceau, methodes=("POST", "PUT")):
    vues = []
    page.on("request", lambda r: vues.append((r.method, r.url, r.post_data))
            if morceau in r.url and r.method in methodes else None)
    return vues


def _fiche_album(page, d, login, titre, collection):
    _ouvrir(page, d, login, f"/corpus?collection={d['cols'][collection]}&album={d['albums'][titre]}",
            projet=d["projet"])
    expect(page.locator("#album-titre")).to_contain_text(titre, timeout=5000)
    return page.locator("#album-detail")


# =========================================================================== #
# Qui crée une collection
# =========================================================================== #
def test_qui_cree_une_collection(page, decor):
    d = decor
    vues = _requetes(page, "/creation-de-collections")
    # Le membre : le bouton reste à sa place, ÉTEINT, focalisable, et nomme la responsable.
    _ouvrir(page, d, "noe", projet=d["projet"])
    creer = page.locator("#col-creer")
    expect(creer).to_be_visible(timeout=5000)
    # Sous la liste des collections, la place de la maquette (Hugo, 2026-10-25).
    expect(page.locator("#collections-bloc #col-creer")).to_have_count(1)
    expect(creer).to_have_attribute("aria-disabled", "true")
    expect(creer).to_have_attribute(
        "title", "Dans « Oralité », seuls les responsables créent des collections : demandez-le à Paule Prop.")
    expect(page.locator("#col-creer-raison")).to_have_text(
        "Dans « Oralité », seuls les responsables créent des collections : demandez-le à Paule Prop.")
    creer.focus()
    assert page.evaluate("() => document.activeElement.id") == "col-creer"
    page.keyboard.press("Enter")    # éteint mais atteignable : au clavier, il dit pourquoi
    expect(page.locator("#col-creer-zone")).to_be_hidden()
    expect(page.locator("#col-creer-msg")).to_contain_text("demandez-le à Paule Prop")
    # La lectrice n'est pas du projet : le bouton n'est pas là.
    _ouvrir(page, d, "lea", projet=d["projet"])
    expect(page.locator("#bi-compte")).to_be_visible(timeout=5000)
    expect(page.locator("#col-creer")).to_be_hidden()
    # La responsable : la case, décochée par défaut, sous la liste des collections.
    _ouvrir(page, d, "paule", f"/administration?vue=projets&projet={d['projet']}")
    case = page.locator("#pj-membres-creent")
    expect(case).to_be_visible(timeout=5000)
    expect(case).not_to_be_checked()
    expect(page.locator(".pj-reglage")).to_contain_text("Les membres peuvent créer des collections")
    expect(page.locator(".pj-reglage-phrase")).to_have_text(
        "Les responsables et les administrateurs en créent toujours.")
    case.check()
    expect(page.locator("#pj-reglage-msg")).to_contain_text("créent désormais des collections")
    assert [json.loads(x) for (_, _, x) in vues] == [{"membres": True}]
    # Le membre : le bouton s'allume.
    _ouvrir(page, d, "noe", projet=d["projet"])
    expect(page.locator("#col-creer")).to_be_visible(timeout=5000)
    expect(page.locator("#col-creer")).not_to_have_attribute("aria-disabled", "true")
    page.locator("#col-creer").click()
    expect(page.locator("#col-nom")).to_be_visible()


# =========================================================================== #
# « Copie… » dans le projet : l'échelle en tableau
# =========================================================================== #
def test_copie_deplie_l_echelle_et_se_demande_au_dessus_des_images(page, decor):
    d = decor
    vues = _requetes(page, "/prendre")
    _ouvrir(page, d, "noe", f"/corpus?collection={d['cols']['Exercices']}&onglet=albums",
            projet=d["projet"])
    page.locator("#bi-dans-projet").click()
    zorglub = page.locator(f'#bi-dans-projet-panneau li[data-dp-album="{d["albums"]["Zorglub"]}"]')
    copie = zorglub.locator('button[data-dp="copie"]')
    expect(copie).to_have_text("Copie…")
    expect(zorglub.locator('[data-dp="zero"]')).to_have_count(0)
    copie.click()
    expect(copie).to_have_attribute("aria-expanded", "true")
    echelle = zorglub.locator(".echelle-zone")
    expect(echelle).to_be_visible()
    lignes = echelle.locator("tbody tr")
    expect(lignes).to_have_count(5)
    expect(echelle.locator('input[value="images"]')).to_be_checked()
    # Ce que chaque cran AJOUTE, en nombres ; la grammaire, que la source n'a pas, en gris.
    expect(lignes.nth(1)).to_contain_text("1 région", timeout=5000)
    expect(lignes.nth(2)).to_contain_text("1 texte")
    expect(lignes.nth(3)).to_contain_text("rien : la source n'a pas ce travail")
    expect(lignes.nth(3)).to_have_class(re.compile(r"\bvide\b"))
    expect(echelle.locator(".reponse-attendue")).to_contain_text("Immédiat : une copie vierge")
    expect(echelle.locator("[data-dp-copier]")).to_have_text("Copier les images")
    # Un cran au-dessus : la propriétaire de Témoins doit l'accepter.
    echelle.locator('input[value="transcription"]').check()
    expect(echelle.locator(".reponse-attendue")).to_contain_text(
        "Son propriétaire doit l'accepter : copier ce travail le fait lire dans « Exercices ».")
    expect(echelle.locator("[data-dp-copier]")).to_have_text("Demander")
    echelle.locator("[data-dp-copier]").click()
    expect(zorglub.locator(".reponse.demande")).to_have_text("copie demandée à son propriétaire",
                                                             timeout=5000)
    # « Images seules » sur Spip : tout de suite.
    spip = page.locator(f'#bi-dans-projet-panneau li[data-dp-album="{d["albums"]["Spip"]}"]')
    spip.locator('button[data-dp="copie"]').click()
    expect(spip.locator('input[value="images"]')).to_be_checked()
    spip.locator("[data-dp-copier]").click()
    expect(page.locator("#bi-dp-msg")).to_contain_text("a une seconde copie, vierge", timeout=5000)
    corps = [json.loads(x) for (_, _, x) in vues]
    assert corps == [
        {"documents": [{"document_id": d["docs"]["Zorglub"], "reponse": "amorcer",
                        "album_id": d["albums"]["Zorglub"], "cran": "transcription"}]},
        {"documents": [{"document_id": d["docs"]["Spip"], "reponse": "zero",
                        "album_id": d["albums"]["Spip"]}]}], corps
    # La copie vierge est dans Exercices, et sa ligne le dit.
    ligne = page.locator("#panneau-albums tr.col-album", has_text="Spip")
    expect(ligne.locator(".cran-puce")).to_have_text("copie vierge")


# =========================================================================== #
# La propriétaire répond, dans le bloc ⚑
# =========================================================================== #
def test_la_proprietaire_repond_a_une_demande_d_en_partir(page, decor):
    d = decor
    with _client(d["base"], _comme("noe")) as c:
        _ok(c.post(f"/api/collections/{d['cols']['Exercices']}/prendre", json={
            "documents": [{"document_id": d["docs"]["Zorglub"], "reponse": "amorcer",
                           "album_id": d["albums"]["Zorglub"], "cran": "transcription"}],
            "motif": "Pour l'exercice 3."}))
    vues = _requetes(page, "/reponse")
    _ouvrir(page, d, "helene", projet=d["projet"])
    marque = page.locator(f'#col-body .col-item[data-id="{d["cols"]["Témoins"]}"] .col-marque')
    expect(marque).to_be_visible(timeout=5000)
    page.locator("#bi-recues-compteur").click()
    bloc = page.locator("#bi-recues-bloc")
    expect(bloc).to_be_visible(timeout=5000)
    ligne = bloc.locator("li.recue-amorcer")
    expect(ligne).to_contain_text("Noe Stagiaire")
    expect(ligne).to_contain_text("demande d'en partir")
    expect(ligne).to_contain_text("« Zorglub »")
    expect(ligne).to_contain_text("jusqu'à la transcription, pour « Exercices »")
    expect(ligne.locator(".recue-motif")).to_have_text("Pour l'exercice 3.")
    expect(ligne.locator(".apercu")).to_contain_text("1 région")
    expect(ligne.locator(".apercu")).to_contain_text("1 texte")
    accepter = ligne.locator(f'button[data-reponse="acceptee"]')
    expect(accepter).to_have_text("Accepter : copier dans « Exercices »")
    accepter.click()
    expect(page.locator("#bi-recues-msg")).to_contain_text("a sa copie de « Zorglub »", timeout=5000)
    assert [json.loads(x) for (_, _, x) in vues] == [{"reponse": "acceptee"}]
    # Le demandeur : la copie est dans sa collection, et sa ligne dit le cran.
    _ouvrir(page, d, "noe", f"/corpus?collection={d['cols']['Exercices']}&onglet=albums",
            projet=d["projet"])
    ligne = page.locator("#panneau-albums tr.col-album", has_text="Zorglub")
    expect(ligne.locator(".cran-puce")).to_have_text("copie · jusqu'à la transcription",
                                                     timeout=5000)


# =========================================================================== #
# Entre deux projets (E7)
# =========================================================================== #
def test_entre_deux_projets_un_cran_par_notice_et_demande_au_bit_pres(page, decor):
    d = decor
    vues = _requetes(page, "/prendre")
    _ouvrir(page, d, "paule", projet=d["projet"])
    page.locator("#bi-prendre-fonds").click()
    for titre, cran in (("Voyageur", "decoupage"), ("Vierge", "transcription")):
        page.locator("#bi-prise-q").fill(titre)
        ligne = page.locator(f'#bi-prise-notices li[data-notice="{d["docs"][titre]}"]')
        expect(ligne).to_be_visible(timeout=5000)
        choix = ligne.locator("select[data-notice-cran]")
        expect(choix).to_be_disabled()
        ligne.locator("input[type=checkbox]").check()
        expect(choix).to_be_enabled()
        expect(choix.locator("option")).to_have_count(5)
        choix.select_option(cran)
    page.locator("#bi-prise-motif").fill("Comparer avec notre grille.")
    page.locator("#bi-prise-ok").click()
    expect(page.locator("#bi-prise-msg")).to_contain_text("vous en suivrez la réponse", timeout=5000)
    # Qu'un projet tienne ce travail (Voyageur) ou non (Vierge), la ligne dit « demandé ».
    for titre in ("Voyageur", "Vierge"):
        page.locator("#bi-prise-q").fill(titre)
        ligne = page.locator(f'#bi-prise-notices li[data-notice="{d["docs"][titre]}"]')
        expect(ligne.locator(".reponse")).to_have_text("demandé", timeout=5000)
    corps = json.loads(vues[0][2])
    assert sorted(corps["documents"], key=lambda x: x["document_id"]) == sorted([
        {"document_id": d["docs"]["Voyageur"], "reponse": "amorcer", "cran": "decoupage"},
        {"document_id": d["docs"]["Vierge"], "reponse": "amorcer", "cran": "transcription"}],
        key=lambda x: x["document_id"]), corps
    # Le responsable source, dans la Bibliothèque : le rappel, puis le bloc en tête du projet.
    _ouvrir(page, d, "marion", projet=d["ono"])
    rappel = page.locator("#bi-e7-compteur")
    expect(rappel).to_have_text("1 demande d'en partir", timeout=5000)
    rappel.click()
    bloc = page.locator("#bi-e7-bloc")
    expect(bloc).to_be_visible()
    expect(bloc).to_contain_text("« Oralité » demande d'en partir")
    expect(bloc.locator("[data-e7-source]")).to_have_count(1)
    expect(bloc.locator("[data-e7-accepter]")).to_have_text("Accepter : copier depuis « Inventaire »")
    # … et dans l'Administration, où il répond.
    reponses = _requetes(page, "/reponse")
    _ouvrir(page, d, "marion", f"/administration?vue=projets&projet={d['ono']}")
    ligne = page.locator(f'#pj-objets [data-pj="{d["ono"]}"]')
    expect(ligne.locator(".pj-alerte-e7")).to_have_text("⚑ 1 demande d'en partir", timeout=5000)
    zone = page.locator("#pj-e7-zone")
    expect(zone).to_be_visible()
    expect(zone.locator("h4")).to_have_text("Demandes d'en partir · 1")
    expect(zone).to_contain_text("Demandée par Paule Prop")
    expect(zone.locator(".apercu")).to_contain_text("1 région")
    zone.locator("[data-pj-e7-accepter]").click()
    expect(page.locator("#pj-e7-msg, #pj-msg").first).to_contain_text("a sa copie de « Voyageur »",
                                                                      timeout=5000)
    corps = [json.loads(x) for (_, _, x) in reponses]
    assert len(corps) == 1 and corps[0]["reponse"] == "acceptee"
    assert corps[0]["album_id"] == d["albums"]["Voyageur"]
    # Le demandeur lit l'état, jamais le projet qui tient le travail.
    _ouvrir(page, d, "paule", f"/administration?vue=projets&projet={d['projet']}")
    lignes = page.locator("#pj-fonds-zone li.pj-demande[data-genre='amorcer_entre_projets']")
    expect(lignes).to_have_count(2, timeout=5000)
    voyageur = lignes.filter(has_text="Voyageur")
    expect(voyageur).to_contain_text("En partir : « Voyageur », jusqu'au découpage → « Oralité »")
    expect(voyageur.locator(".af-etat")).to_have_text("acceptée")
    expect(lignes.filter(has_text="Vierge").locator(".af-etat")).to_have_text("en attente")
    assert "Onomatopées" not in page.locator("#pj-fonds-zone").inner_text()
    assert "Inventaire" not in page.locator("#pj-fonds-zone").inner_text()


# =========================================================================== #
# Repartir de zéro
# =========================================================================== #
def test_repartir_de_zero_sur_un_album_dit_qui_perd_quoi(page, decor):
    d = decor
    vues = _requetes(page, "/repartir")
    fiche = _fiche_album(page, d, "paule", "Gorille", "Corpus")
    fiche.locator('[data-act="repartir"]').click()
    panneau = page.locator("#repartir-modal")
    expect(panneau).to_be_visible()
    expect(page.locator("#rp-titre")).to_have_text("Repartir de zéro : « Gorille »")
    expect(page.locator("#rp-restent")).to_contain_text("Restent : les images, la notice, les planches et leur verrou.")
    radios = page.locator("#rp-crans input[name=rp-cran]")
    expect(radios).to_have_count(4, timeout=5000)
    # Le travail va jusqu'à la transcription : on n'y revient pas, ni au-dessus.
    expect(page.locator('#rp-crans input[value="transcription"]')).to_be_disabled()
    expect(page.locator('#rp-crans input[value="grammaire"]')).to_be_disabled()
    expect(page.locator('#rp-crans input[value="decoupage"]')).to_be_checked()
    expect(page.locator("#rp-part-liste")).to_contain_text("2 textes")
    table = page.locator("#rp-perd .perd")
    expect(table).to_be_visible()
    expect(table.locator(".perd-titre")).to_have_text("Ce qu'une autre personne perd")
    expect(table.locator("tbody th")).to_have_text(["Helene Brunet (helene)"])
    expect(page.locator("#rp-raison")).to_have_text("Vous êtes responsable du projet : rien à demander.")
    expect(page.locator("#rp-irreversible")).to_have_text("Ne s'annule pas, Ctrl+Z compris.")
    page.locator('#rp-crans input[value="images"]').check()
    expect(page.locator("#rp-part-liste")).to_contain_text("2 régions")
    ok = page.locator("#rp-ok")
    expect(ok).to_have_text("Repartir des images seules")
    page.locator('#rp-crans input[value="decoupage"]').check()
    expect(ok).to_have_text("Repartir du découpage")
    ok.click()
    expect(panneau).to_be_hidden(timeout=5000)
    expect(page.locator(".toast", has_text="repart au découpage")).to_be_visible()
    assert [(m, json.loads(x)) for (m, u, x) in vues if u.endswith("/repartir")] == [
        ("POST", {"cran": "decoupage"})]
    # La puce, dans la tête de la fiche : le cran et la date ; qui, en infobulle.
    puce = page.locator("#album-detail .puce-repartie")
    expect(puce).to_contain_text("repartie du découpage le", timeout=5000)
    expect(puce).to_have_attribute("title", "Par Paule Prop. Ce qui était au-dessus a été effacé ; le journal garde l'acte.")


def test_une_planche_ne_se_demande_pas_et_un_album_se_demande(page, decor):
    d = decor
    vues = _requetes(page, "/api/demandes", ("POST",))
    fiche = _fiche_album(page, d, "noe", "Pirates", "Exercices")
    # ↺ sur la planche : Noé n'a pas créé cet album — une planche n'a pas de demande à elle.
    fiche.locator(f'[data-repartir-planche="{d["planches"]["Pirates"]}"]').click()
    expect(page.locator("#repartir-modal")).to_be_visible()
    expect(page.locator("#rp-raison")).to_contain_text("ne se demande pas", timeout=5000)
    expect(page.locator("#rp-raison")).to_contain_text(
        "Demandez-le pour l'album entier, ou adressez-vous à un administrateur de l'instance.")
    expect(page.locator("#rp-ok")).to_be_hidden()
    expect(page.locator("#rp-motif-wrap")).to_be_hidden()
    page.keyboard.press("Escape")
    expect(page.locator("#repartir-modal")).to_be_hidden()
    # L'album entier : motif et certification exigés, puis la demande.
    fiche.locator('[data-act="repartir"]').click()
    expect(page.locator("#rp-motif-wrap")).to_be_visible(timeout=5000)
    expect(page.locator("#rp-certif-texte")).to_contain_text("Repartir de zéro détruit ce qui a été posé")
    ok = page.locator("#rp-ok")
    expect(ok).to_have_text("Envoyer la demande")
    ok.click()
    expect(page.locator("#rp-msg")).to_contain_text("Dites pourquoi")
    page.locator("#rp-motif").fill("Découpé à l'envers.")
    ok.click()
    expect(page.locator("#rp-msg")).to_contain_text("Cochez la certification")
    assert vues == []
    page.locator("#rp-certif").check()
    ok.click()
    expect(page.locator("#repartir-modal")).to_be_hidden(timeout=5000)
    corps = json.loads(vues[0][2])
    assert corps == {"genre": "repartir", "album_id": d["albums"]["Pirates"], "cran": "images",
                     "motif": "Découpé à l'envers.", "certifie": True}, corps
    # « À faire », chez l'administratrice : la tranche rose, ce qui part, « Garder ».
    _ouvrir(page, d, "admin", "/administration?vue=afaire")
    ligne = page.locator(".af-ligne.af-genre-repartir")
    expect(ligne).to_have_count(1, timeout=5000)
    expect(ligne.locator(".af-genre-nom")).to_have_text("Repartir de zéro")
    ligne.locator("[data-af-deplier]").click()
    expect(ligne.locator(".rp-part-liste")).to_contain_text("1 région", timeout=5000)
    expect(ligne.locator("[data-fd-accepter]")).to_have_text("Repartir des images seules")
    expect(ligne.locator("[data-fd-refuser]")).to_have_text("Garder")
    expect(ligne.locator(".irreversible")).to_have_text("Ne s'annule pas.")
    ligne.locator("[data-fd-refuser]").click()
    expect(page.locator("#af-msg")).to_contain_text("gardé", timeout=5000)


# =========================================================================== #
# Supprimer et retirer
# =========================================================================== #
def test_supprimer_dit_le_chemin_reel_et_la_derniere_copie_se_demande(page, decor):
    d = decor
    fiche = _fiche_album(page, d, "paule", "QRN", "Corpus")
    fiche.locator('[data-act="supprimer"]').click()
    expect(page.locator("#suppr-modal")).to_be_visible()
    expect(page.locator("#sp-def-raison")).to_have_text(
        "Vous êtes responsable du projet : rien à demander.", timeout=5000)
    texte = page.locator("#sp-def-texte")
    expect(texte).to_contain_text("Ses images restent")
    expect(texte).not_to_contain_text("l'avez créée")
    perd = page.locator("#sp-perd .perd")
    expect(perd.locator("tbody th")).to_have_text(["Nico Gauthier (nico)"])
    expect(perd.locator(".perd-note")).to_have_attribute(
        "title", "Ce sont des gestes, défaits compris, pas ce qui reste sur les planches.")
    expect(page.locator("#sp-def")).to_have_text("Supprimer définitivement")
    expect(page.locator("#sp-motif-wrap")).to_be_hidden()
    page.keyboard.press("Escape")
    # La dernière copie : même la responsable la demande.
    page.goto(d["base"] + f"/corpus?collection={d['cols']['Corpus']}&album={d['albums']['Gorille']}",
              wait_until="networkidle")
    page.locator('#album-detail [data-act="supprimer"]').click()
    expect(page.locator("#sp-def-texte")).to_contain_text("C'est la dernière copie de ce document",
                                                          timeout=5000)
    expect(page.locator("#sp-def-texte")).to_contain_text(
        "Vous êtes responsable du projet, mais c'est un administrateur qui décide")
    expect(page.locator("#sp-perd .perd tbody th")).to_have_text(["Helene Brunet (helene)"])
    expect(page.locator("#sp-motif-wrap")).to_be_visible()
    expect(page.locator("#sp-def")).to_have_text("Envoyer la demande")


def test_retirer_du_projet_et_l_avis_chez_la_proprietaire(page, decor):
    d = decor
    vues = _requetes(page, "/retirer-du-projet", ("POST",))
    fiche = _fiche_album(page, d, "paule", "Gorille", "Corpus")
    fiche.locator('[data-act="retirer"]').click()
    expect(page.locator("#retirer-modal")).to_be_visible()
    expect(page.locator("#rt-texte")).to_have_text(
        "Il quitte toutes les collections de « Oralité » : « Corpus » et « Témoins ». Il part "
        "au fonds avec son travail ; un administrateur peut le rendre.", timeout=5000)
    expect(page.locator("#rt-proprios")).to_have_text(
        "Helene Brunet le verra disparaître, avec votre nom et la date.")
    expect(page.locator("#rt-perd .perd-titre")).to_have_text("Qui y a travaillé (rien n'est effacé)")
    page.locator("#rt-motif").fill("Entré par erreur.")
    page.locator("#rt-ok").click()
    expect(page.locator("#retirer-modal")).to_be_hidden(timeout=5000)
    expect(page.locator(".toast", has_text="a quitté « Oralité »")).to_be_visible()
    assert [json.loads(x) for (_, _, x) in vues] == [{"motif": "Entré par erreur."}]
    # La propriétaire de Témoins le lit en tête de l'onglet Albums, jusqu'à « Vu ».
    _ouvrir(page, d, "helene", f"/corpus?collection={d['cols']['Témoins']}&onglet=albums",
            projet=d["projet"])
    trace = page.locator("#bi-retraits-zone .trace")
    expect(trace).to_be_visible(timeout=5000)
    expect(trace).to_contain_text("« Gorille » a été retiré du projet par Paule Prop le")
    expect(trace).to_contain_text("il est gardé au fonds, avec son travail. Motif : Entré par erreur.")
    trace.locator("[data-retrait-vu]").click()
    expect(page.locator("#bi-retraits-zone .trace")).to_have_count(0, timeout=5000)
    page.reload(wait_until="networkidle")
    expect(page.locator("#panneau-albums")).to_be_visible(timeout=5000)
    expect(page.locator("#bi-retraits-zone .trace")).to_have_count(0)
    # La fiche du projet le dit dans « Copies gardées au fonds ».
    _ouvrir(page, d, "paule", f"/administration?vue=projets&projet={d['projet']}")
    gardee = page.locator("#pj-fonds-zone li.pj-gardee", has_text="Gorille")
    expect(gardee).to_contain_text("retiré du projet par vous", timeout=5000)


# =========================================================================== #
# Ce que la lectrice ne voit pas
# =========================================================================== #
def test_la_lectrice_ne_voit_aucun_geste_de_la_3b(page, decor):
    d = decor
    fiche = _fiche_album(page, d, "lea", "QRN", "Corpus")
    expect(fiche.locator("#album-range[data-pret]")).to_be_attached(timeout=5000)
    for geste in ("repartir", "retirer", "supprimer"):
        expect(fiche.locator(f'[data-act="{geste}"]')).to_have_count(0)
    expect(fiche.locator("[data-repartir-planche]")).to_have_count(0)
    expect(page.locator("#col-creer")).to_be_hidden()
    # Le membre qui écrit ne voit pas « Retirer du projet… », le geste du responsable.
    fiche = _fiche_album(page, d, "noe", "Pirates", "Exercices")
    expect(fiche.locator('[data-act="repartir"]')).to_be_visible()
    expect(fiche.locator('[data-act="retirer"]')).to_have_count(0)


# =========================================================================== #
# « À faire » : les deux tranches neuves, « attend … »
# =========================================================================== #
def test_a_faire_en_partir_attend_et_repond_a_la_place(page, decor):
    d = decor
    with _client(d["base"], _comme("noe")) as c:
        _ok(c.post(f"/api/collections/{d['cols']['Exercices']}/prendre", json={
            "documents": [{"document_id": d["docs"]["Zorglub"], "reponse": "amorcer",
                           "album_id": d["albums"]["Zorglub"], "cran": "decoupage"}]}))
    with _client(d["base"], _comme("paule")) as c:
        _ok(c.post(f"/api/projets/{d['projet']}/prendre", json={
            "documents": [{"document_id": d["docs"]["Vierge"], "reponse": "amorcer",
                           "cran": "decoupage"},
                          {"document_id": d["docs"]["Voyageur"], "reponse": "amorcer",
                           "cran": "decoupage"}],
            "motif": "Comparer."}))
    _ouvrir(page, d, "admin", "/administration?vue=afaire")
    lignes = page.locator(".af-ligne.af-genre-amorcer")
    expect(lignes).to_have_count(3, timeout=5000)
    interne = lignes.filter(has_text="Zorglub")
    expect(interne.locator(".af-genre-nom")).to_have_text("En partir d'un travail")
    expect(interne.locator(".fd-demande-contexte")).to_contain_text("attend Helene Brunet")
    vierge = lignes.filter(has_text="Vierge")
    expect(vierge.locator(".fd-demande-contexte")).to_contain_text(
        "aucun responsable ne tient ce travail : à vous")
    voyageur = lignes.filter(has_text="Voyageur")
    expect(voyageur.locator(".fd-demande-contexte")).to_contain_text("attend Marion Dumas")
    reponses = _requetes(page, "/reponse")
    voyageur.locator("[data-af-deplier]").click()
    expect(voyageur.locator("[data-e7-source]")).to_have_count(1, timeout=5000)
    accepter = voyageur.locator("[data-fd-accepter]")
    expect(accepter).to_have_text("Accepter : copier depuis « Inventaire »", timeout=5000)
    accepter.click()
    expect(page.locator("#af-msg")).to_contain_text("a sa copie dans", timeout=5000)
    corps = [json.loads(x) for (_, _, x) in reponses]
    assert corps == [{"reponse": "acceptee", "album_id": d["albums"]["Voyageur"]}], corps
    # La demande que personne ne tient : rien à cocher, seulement « Refuser ».
    vierge.locator("[data-af-deplier]").click()
    expect(vierge.locator(".e7-aucune")).to_be_visible(timeout=5000)
    expect(vierge.locator("[data-fd-accepter]")).to_have_count(0)
    expect(vierge.locator("[data-fd-refuser]")).to_have_text("Refuser")


# =========================================================================== #
# Un envoi se voit sur son bouton (Hugo, 2026-10-26)
# =========================================================================== #
def _tenir(page, motif):
    """La requête est TENUE tant que le test ne la rend pas : l'état « pendant » se lit
    sans course contre le serveur."""
    tenues = []
    page.route(motif, lambda route: tenues.append(route))
    return tenues


def _attendre_tenue(page, tenues):
    for _ in range(50):
        if tenues:
            return tenues[0]
        page.wait_for_timeout(100)
    raise AssertionError("la requête n'est jamais partie")


def _largeur(bouton):
    return bouton.bounding_box()["width"]


def test_un_envoi_se_voit_sur_son_bouton(page, decor):
    """Pendant la requête, le bouton qui envoie dit « Envoi… » et porte `aria-busy`, sans
    changer de largeur ; il reprend son libellé quand la réponse arrive, y compris en
    ERREUR. Mesuré sur deux panneaux : « Retirer du projet… » dans la Bibliothèque, et une
    réponse de « À faire » dans l'Administration."""
    d = decor
    # --- La Bibliothèque : « Retirer du projet… », refusé par le serveur.
    fiche = _fiche_album(page, d, "paule", "Gorille", "Corpus")
    fiche.locator('[data-act="retirer"]').click()
    ok = page.locator("#rt-ok")
    expect(ok).to_be_visible(timeout=5000)
    expect(ok).to_have_text("Retirer du projet")
    avant = _largeur(ok)
    tenues = _tenir(page, "**/api/albums/*/retirer-du-projet")
    ok.click()
    route = _attendre_tenue(page, tenues)
    expect(ok).to_have_text("Envoi…")
    expect(ok).to_have_attribute("aria-busy", "true")
    expect(ok).to_be_disabled()
    assert abs(_largeur(ok) - avant) < 0.5, (avant, _largeur(ok))
    route.fulfill(status=409, json={"detail": "Refus de test : rien n'a bougé."})
    expect(page.locator("#rt-msg")).to_have_text("Refus de test : rien n'a bougé.", timeout=5000)
    expect(ok).to_have_text("Retirer du projet")
    expect(ok).not_to_have_attribute("aria-busy", "true")
    expect(ok).to_be_enabled()
    assert abs(_largeur(ok) - avant) < 0.5
    page.unroute("**/api/albums/*/retirer-du-projet")

    # --- L'Administration : une réponse de « À faire », en erreur puis pour de bon.
    with _client(d["base"], _comme("noe")) as c:
        _ok(c.post(f"/api/collections/{d['cols']['Exercices']}/prendre", json={
            "documents": [{"document_id": d["docs"]["Zorglub"], "reponse": "amorcer",
                           "album_id": d["albums"]["Zorglub"], "cran": "decoupage"}]}))
    _ouvrir(page, d, "admin", "/administration?vue=afaire")
    ligne = page.locator(".af-ligne.af-genre-amorcer", has_text="Zorglub")
    expect(ligne).to_be_visible(timeout=5000)
    ligne.locator("[data-af-deplier]").click()
    accepter = ligne.locator("[data-fd-accepter]")
    expect(accepter).to_be_visible(timeout=5000)
    libelle = accepter.inner_text()
    assert libelle and libelle != "Envoi…"
    avant = _largeur(accepter)
    tenues = _tenir(page, "**/api/demandes/*/reponse")
    accepter.click()
    route = _attendre_tenue(page, tenues)
    expect(accepter).to_have_text("Envoi…")
    expect(accepter).to_have_attribute("aria-busy", "true")
    assert abs(_largeur(accepter) - avant) < 0.5, (avant, _largeur(accepter))
    route.fulfill(status=409, json={"detail": "Réponse refusée pour le test."})
    expect(ligne.locator(".fd-ligne-msg")).to_have_text("Réponse refusée pour le test.",
                                                        timeout=5000)
    expect(accepter).to_have_text(libelle)
    expect(accepter).not_to_have_attribute("aria-busy", "true")
    expect(accepter).to_be_enabled()
    page.unroute("**/api/demandes/*/reponse")
    # Le second essai passe : le bouton rendu marche encore.
    accepter.click()
    expect(page.locator("#af-msg")).to_contain_text("a sa copie dans", timeout=5000)


# =========================================================================== #
# À l'étroit, et l'accessibilité
# =========================================================================== #
_SONDE = """() => [document.documentElement, document.body,
    ...document.querySelectorAll('main, #header, #afaire-bloc, #projets-bloc, .modal-box')]
    .filter(Boolean).filter((el) => el.scrollWidth > el.clientWidth + 1)
    .map((el) => `${el.tagName}#${el.id}.${el.className} ${el.clientWidth}/${el.scrollWidth}`)"""


@pytest.mark.parametrize("police", [16, 24])
def test_a_320_px_rien_ne_defile_de_cote(page, decor, police):
    d = decor
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": police, "fixed": police}})
    page.set_viewport_size({"width": 320, "height": 900})
    # L'échelle de « Copie… », dépliée.
    _ouvrir(page, d, "noe", f"/corpus?collection={d['cols']['Exercices']}&onglet=albums",
            projet=d["projet"])
    page.locator("#bi-dans-projet").click()
    zorglub = page.locator(f'#bi-dans-projet-panneau li[data-dp-album="{d["albums"]["Zorglub"]}"]')
    zorglub.locator('button[data-dp="copie"]').click()
    zorglub.locator('input[value="annotations"]').check()
    expect(zorglub.locator(".tab-echelle tbody tr").nth(1)).to_contain_text("1 région", timeout=5000)
    assert not page.evaluate(_SONDE), page.evaluate(_SONDE)
    # « Repartir de zéro », avec « qui perd quoi ».
    fiche = _fiche_album(page, d, "paule", "Gorille", "Corpus")
    fiche.locator('[data-act="repartir"]').click()
    expect(page.locator("#rp-perd .perd")).to_be_visible(timeout=5000)
    assert not page.evaluate(_SONDE), page.evaluate(_SONDE)
    page.keyboard.press("Escape")
    # « Retirer du projet ».
    page.locator('#album-detail [data-act="retirer"]').click()
    expect(page.locator("#rt-ok")).to_be_visible(timeout=5000)
    assert not page.evaluate(_SONDE), page.evaluate(_SONDE)
    page.keyboard.press("Escape")
    # « Supprimer… » de la dernière copie, avec son tableau.
    page.locator('#album-detail [data-act="supprimer"]').click()
    expect(page.locator("#sp-perd .perd")).to_be_visible(timeout=5000)
    assert not page.evaluate(_SONDE), page.evaluate(_SONDE)
    page.keyboard.press("Escape")
    # « + Prendre du fonds… » avec un cran par notice.
    _ouvrir(page, d, "paule", projet=d["projet"])
    page.locator("#bi-prendre-fonds").click()
    page.locator("#bi-prise-q").fill("Voyageur")
    ligne = page.locator(f'#bi-prise-notices li[data-notice="{d["docs"]["Voyageur"]}"]')
    ligne.locator("input[type=checkbox]").check()
    expect(ligne.locator("select[data-notice-cran]")).to_be_enabled()
    assert not page.evaluate(_SONDE), page.evaluate(_SONDE)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_de_l_ecran_de_la_3b(page, decor, theme):
    """Les états que l'audit générique ne voit pas : l'échelle de « Copie… » ; les panneaux
    « Repartir de zéro », « Retirer du projet » et « Supprimer… » avec « qui perd quoi » ;
    « + Créer une collection » éteint ; le bloc des demandes d'en partir ; « À faire » aux
    deux tranches neuves, dépliées."""
    from test_e2e_a11y import _audit, _fmt, _theme
    d = decor
    with _client(d["base"], _comme("paule")) as c:
        _ok(c.post(f"/api/projets/{d['projet']}/prendre", json={
            "documents": [{"document_id": d["docs"]["Voyageur"], "reponse": "amorcer",
                           "cran": "decoupage"}], "motif": "Comparer."}))
    with _client(d["base"], _comme("noe")) as c:
        _ok(c.post("/api/demandes", json={"genre": "repartir", "album_id": d["albums"]["Pirates"],
                                          "cran": "images", "motif": "Envers.", "certifie": True}))
    _theme(page, theme)
    _ouvrir(page, d, "noe", f"/corpus?collection={d['cols']['Exercices']}&onglet=albums",
            projet=d["projet"])
    expect(page.locator("#col-creer")).to_have_attribute("aria-disabled", "true", timeout=5000)
    page.locator("#bi-dans-projet").click()
    zorglub = page.locator(f'#bi-dans-projet-panneau li[data-dp-album="{d["albums"]["Zorglub"]}"]')
    zorglub.locator('button[data-dp="copie"]').click()
    expect(zorglub.locator(".tab-echelle tbody tr").nth(1)).to_contain_text("1 région", timeout=5000)
    viol = _audit(page)
    assert not viol, f"« Copie… » [{theme}] :\n{_fmt(viol)}"
    fiche = _fiche_album(page, d, "paule", "Gorille", "Corpus")
    for geste, attendu in (("repartir", "#rp-perd .perd"), ("retirer", "#rt-ok"),
                           ("supprimer", "#sp-perd .perd")):
        page.locator(f'#album-detail [data-act="{geste}"]').click()
        expect(page.locator(attendu)).to_be_visible(timeout=5000)
        viol = _audit(page)
        assert not viol, f"panneau « {geste} » [{theme}] :\n{_fmt(viol)}"
        page.keyboard.press("Escape")
    _ouvrir(page, d, "marion", f"/administration?vue=projets&projet={d['ono']}")
    expect(page.locator("#pj-e7-zone")).to_be_visible(timeout=5000)
    viol = _audit(page)
    assert not viol, f"Demandes d'en partir [{theme}] :\n{_fmt(viol)}"
    _ouvrir(page, d, "admin", "/administration?vue=afaire")
    for genre in ("amorcer", "repartir"):
        ligne = page.locator(f".af-ligne.af-genre-{genre}").first
        ligne.locator("[data-af-deplier]").click()
        expect(ligne.locator(".af-detail")).to_be_visible(timeout=5000)
    expect(page.locator(".af-ligne.af-genre-repartir .rp-part-liste")).to_be_visible(timeout=5000)
    viol = _audit(page)
    assert not viol, f"À faire, deux tranches neuves [{theme}] :\n{_fmt(viol)}"
