"""COL-3, tranche 3a — les gestes de la 3a dans la Bibliothèque, tranchés par Hugo sur
maquette le 2026-10-17, joués dans un navigateur SOUS L'IDENTITÉ concernée.

Le serveur est mesuré par `tests/test_prendre.py`, `tests/test_ecran_3a.py` et
`tests/test_bibliotheque_3a.py` ; l'Administration par `tests/test_e2e_ecran_3a.py`. Ce
fichier mesure ce que la BIBLIOTHÈQUE en fait :

- « + Prendre du fonds… » au responsable et à l'administrateur SEULEMENT (D3), en tête du
  corpus (vers la base) et dans l'onglet Albums d'une collection (vers elle) ; les notices
  cherchées au serveur, cochées, la destination choisie, la réponse document par document ;
- « + Prendre dans le projet… » à qui écrit dans la collection : « Rejoindre » et « Copie
  vierge » (« Copie… » depuis l'écran de la 3b, « Images seules » cochée), la réponse écrite
  sur place ;
- « Sur les collections », dans la fiche d'un album : cocher = rejoindre (fait, ou case
  indéterminée « demandé »), décocher = supprimer de la collection ;
- les demandes de rejoindre reçues par le propriétaire : la marque ⚑ sur la collection, le
  compteur dans la bande d'outils, la pastille sur l'onglet, le bloc ⚑ et « Accepter /
  Refuser » ; le rappel des demandes du responsable ;
- « + Nouvel album » présélectionne la base ; « Supprimer… » d'une copie qui a une sœur dit
  que ses images restent.

La lectrice ne voit AUCUN de ces gestes ; l'écrivain ne voit pas « + Prendre du fonds… ».
Chaque geste se mesure sur la requête PARTIE, pas seulement sur l'état final : le serveur
répondrait juste à un écran qui enverrait autre chose.
"""
import json

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

from conftest import du_projet
from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.parametrize("live_server", [True], indirect=True)]

SURFACES_AUDITEES = ("/corpus",)
SURFACES_HORS_PERIMETRE = {
    "/annotation": "les gestes de la tranche 3a vivent dans la Bibliothèque seule",
    "/administration": "l'écran de la 3a dans l'Administration est mesuré par "
                       "test_e2e_ecran_3a.py ; ici, les seuls gestes de la Bibliothèque",
    "/": "l'Atelier ne prend rien au fonds et ne montre aucune demande",
    "/recherche": "la Recherche interroge le corpus ; rien de la 3a ne s'y montre",
    "/exploration": "l'Exploration mesure la langue du corpus ; rien de la 3a ne s'y montre",
}

EN_TETE = next(k for k in ECRITURE if k not in ("Remote-User", "Remote-Groups"))
ADMIN = {**ECRITURE}


def _comme(login):
    return {"Remote-User": login, EN_TETE: "1"}


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
    """« Séminaire » : `rui` responsable, `mia` membre (sa base OUVERTE : elle y écrit).
    « Lot A » que possède `ana` (`sam` et `lia` la lisent), « Lot B » où `sam` écrit. Dans
    le repli, « Archives » et l'album « Hors », qu'aucune collection du projet n'a."""
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
                                 (lot_a, "lia", "lecture"), (lot_b, "sam", "ecriture")):
            du_projet(c, cid, "utilisateur", qui, headers=ECRITURE)
            _ok(c.put(f"/api/collections/{cid}/acces",
                      json={"genre": "utilisateur", "principal": qui, "niveau": niveau}))
        albums = {t: _album(c, t, lot_a) for t in ("Lotus", "Oreille")}
        albums["Hors"] = _album(c, "Hors", archives)
        docs = {t: _document_de(c, a) for t, a in albums.items()}
    return {"base": base, "projet": pid, "base_id": bid, "lot_a": lot_a, "lot_b": lot_b,
            "archives": archives, "albums": albums, "docs": docs}


def _ouvrir(page, base, entetes=None, chemin="/corpus"):
    page.set_extra_http_headers({k: v for k, v in (entetes or ADMIN).items() if k != EN_TETE})
    page.goto(base + chemin, wait_until="networkidle")


def _choisir_projet(page, decor):
    """Le projet courant est retenu par le navigateur : on le pose avant de charger."""
    page.add_init_script(f"try {{ localStorage.setItem('bd-projet', '{decor['projet']}') }} "
                         "catch (e) {}")


def _requetes(page, morceau):
    """Les corps des requêtes POST/PUT qui partent vers une adresse contenant `morceau`."""
    vues = []
    page.on("request", lambda r: vues.append((r.method, r.url, r.post_data))
            if morceau in r.url and r.method in ("POST", "PUT") else None)
    return vues


# =========================================================================== #
# « + Prendre du fonds… » — le responsable, l'administrateur, et eux seuls
# =========================================================================== #
def test_le_responsable_prend_du_fonds_en_tete_du_corpus(page, decor):
    _choisir_projet(page, decor)
    vues = _requetes(page, "/prendre")
    _ouvrir(page, decor["base"], _comme("rui"))
    bouton = page.locator("#bi-prendre-fonds")
    expect(bouton).to_be_visible(timeout=5000)
    expect(bouton).to_have_text("+ Prendre du fonds…")
    bouton.click()
    panneau = page.locator("#bi-prise")
    expect(panneau).to_be_visible()
    # La destination : la BASE présélectionnée (D10), et seules les collections où il écrit.
    expect(page.locator("#bi-prise-dest")).to_have_value(str(decor["base_id"]))
    expect(page.locator("#bi-prise-dest option")).to_have_count(1)
    # Les notices, cherchées AU SERVEUR : « déjà dans ce projet » reste cochable.
    page.locator("#bi-prise-q").fill("lotus")
    ligne = page.locator(f'#bi-prise-notices li[data-notice="{decor["docs"]["Lotus"]}"]')
    expect(ligne).to_be_visible(timeout=5000)
    expect(ligne.locator(".bi-deja")).to_have_text("déjà dans ce projet")
    expect(ligne.locator("input[type=checkbox]")).to_be_enabled()
    expect(page.locator("#bi-prise-notices li")).to_have_count(1)
    page.locator("#bi-prise-q").fill("Hors")
    ligne = page.locator(f'#bi-prise-notices li[data-notice="{decor["docs"]["Hors"]}"]')
    expect(ligne).to_be_visible(timeout=5000)
    expect(ligne.locator(".bi-deja")).to_have_count(0)
    ligne.locator("input[type=checkbox]").check()
    expect(page.locator("#bi-prise-ok")).to_have_text("Demander 1 document")
    # Sans motif, le serveur refuse : le refus se dit sur place.
    page.locator("#bi-prise-ok").click()
    expect(page.locator("#bi-prise-msg.erreur")).to_contain_text("motif", timeout=5000)
    page.locator("#bi-prise-motif").fill("Pour le séminaire.")
    page.locator("#bi-prise-ok").click()
    expect(ligne.locator(".reponse.demande")).to_have_text("demandé à un administrateur",
                                                            timeout=5000)
    corps = [json.loads(d) for (m, u, d) in vues if u.endswith(f"/api/collections/{decor['base_id']}/prendre")]
    assert corps[-1] == {"documents": [{"document_id": decor["docs"]["Hors"], "reponse": "zero"}],
                         "motif": "Pour le séminaire."}, corps
    # Le rappel de la bande d'outils mène à la fiche du projet (Administration).
    rappel = page.locator("#bi-mes-demandes")
    expect(rappel).to_have_text("1 demande au fonds, en attente", timeout=5000)
    expect(rappel).to_have_attribute("href", f"/administration?vue=projets&projet={decor['projet']}")
    # Rien n'est rangé : la base reste vide.
    with _client(decor["base"]) as c:
        assert not any(decor["base_id"] in [x["id"] for x in a["collections"]]
                       for a in c.get("/api/albums").json())


def test_l_administrateur_prend_du_fonds_depuis_une_collection(page, decor):
    _choisir_projet(page, decor)
    vues = _requetes(page, "/prendre")
    _ouvrir(page, decor["base"], chemin=f"/corpus?collection={decor['lot_b']}&onglet=albums")
    bouton = page.locator("#panneau-albums #bi-prendre-fonds")
    expect(bouton).to_be_visible(timeout=5000)
    bouton.click()
    # La destination : CETTE collection, la base en tête de la liste.
    expect(page.locator("#bi-prise-dest")).to_have_value(str(decor["lot_b"]))
    assert page.locator("#bi-prise-dest option").first.get_attribute("value") == str(decor["base_id"])
    expect(page.locator("#bi-prise-motif")).to_have_count(0)
    page.locator("#bi-prise-q").fill("Hors")
    ligne = page.locator(f'#bi-prise-notices li[data-notice="{decor["docs"]["Hors"]}"]')
    ligne.locator("input[type=checkbox]").check()
    expect(page.locator("#bi-prise-ok")).to_have_text("Prendre 1 document")
    page.locator("#bi-prise-ok").click()
    expect(page.locator(f'#bi-prise-notices li[data-notice="{decor["docs"]["Hors"]}"] .reponse.fait')
           ).to_have_text("fait", timeout=5000)
    assert [u for (m, u, d) in vues] == [decor["base"] + f"/api/collections/{decor['lot_b']}/prendre"]
    # La copie vierge est dans la collection.
    expect(page.locator("#panneau-albums tr.col-album", has_text="Hors")).to_be_visible(timeout=5000)


def test_ni_l_ecrivain_ni_la_lectrice_ne_puisent_au_fonds(page, decor):
    """D3 : la maquette v8 montrait « + Prendre du fonds… » à tout écrivain ; corrigé. Mia
    est membre et écrit dans la base ouverte, Sam écrit dans Lot B : ni l'un ni l'autre ne
    voit le geste, nulle part. Lia ne fait que lire : aucun des gestes de la 3a."""
    _choisir_projet(page, decor)
    for qui, cid in (("mia", decor["base_id"]), ("sam", decor["lot_b"])):
        _ouvrir(page, decor["base"], _comme(qui))
        expect(page.locator("#biblio-fiche h3")).to_be_visible(timeout=5000)
        expect(page.locator("#bi-prendre-fonds")).to_have_count(0)
        _ouvrir(page, decor["base"], _comme(qui), f"/corpus?collection={cid}&onglet=albums")
        expect(page.locator("#panneau-albums #bi-dans-projet")).to_be_visible(timeout=5000)
        expect(page.locator("#bi-prendre-fonds")).to_have_count(0)
    _ouvrir(page, decor["base"], _comme("lia"))
    expect(page.locator("#biblio-fiche h3")).to_be_visible(timeout=5000)
    expect(page.locator("#bi-prendre-fonds")).to_have_count(0)
    _ouvrir(page, decor["base"], _comme("lia"), f"/corpus?collection={decor['lot_a']}&onglet=albums")
    expect(page.locator("#panneau-albums tr.col-album").first).to_be_visible(timeout=5000)
    expect(page.locator("#bi-prendre-fonds, #bi-dans-projet, #bi-recues-bloc")).to_have_count(0)
    expect(page.locator("#bi-rappels")).to_be_hidden()
    # Dans la fiche d'un album : les cases se lisent ; aucune ne s'offre, hors la base —
    # Lia, entrée dans le projet pour lire Lot A (COL-3, tranche 3c, F2), y écrit par sa
    # position ouverte.
    page.locator('[data-ouvrir-album]', has_text="Lotus").click()
    page.locator("#album-range[data-pret]").wait_for(timeout=5000)
    cases = page.locator("#album-range-cases input[data-ranger]")
    expect(cases.first).to_be_visible()
    for i in range(cases.count()):
        if cases.nth(i).get_attribute("data-nom") == "Séminaire":
            expect(cases.nth(i)).to_be_enabled()
        else:
            expect(cases.nth(i)).to_be_disabled()


# =========================================================================== #
# « + Prendre dans le projet… » — l'écrivain, sur ce qu'il lit
# =========================================================================== #
def test_l_ecrivain_prend_dans_le_projet(page, decor):
    _choisir_projet(page, decor)
    vues = _requetes(page, "/prendre")
    _ouvrir(page, decor["base"], _comme("sam"), f"/corpus?collection={decor['lot_b']}&onglet=albums")
    page.locator("#bi-dans-projet").click()
    panneau = page.locator("#bi-dans-projet-panneau")
    expect(panneau).to_be_visible()
    lotus = panneau.locator(f'li[data-dp-album="{decor["albums"]["Lotus"]}"]')
    oreille = panneau.locator(f'li[data-dp-album="{decor["albums"]["Oreille"]}"]')
    expect(lotus).to_contain_text("dans « Lot A »")
    expect(lotus.locator('[data-dp="rejoindre"]')).to_have_attribute(
        "title", "Ranger aussi ici cette copie : qui tient toutes ses collections doit "
                 "l'accepter. Le travail sera partagé.")
    # Copie vierge — « Copie… » depuis l'écran de la 3b, « Images seules » cochée : immédiate,
    # à son nom.
    oreille.locator('[data-dp="copie"]').click()
    expect(oreille.locator('.echelle-zone input[value="images"]')).to_be_checked()
    oreille.locator("[data-dp-copier]").click()
    expect(oreille.locator(".reponse.fait")).to_have_text("fait", timeout=5000)
    # Rejoindre : Ana tient Lot A, la demande lui part.
    lotus.locator('[data-dp="rejoindre"]').click()
    expect(lotus.locator(".reponse.demande")).to_have_text("demandé à son propriétaire",
                                                            timeout=5000)
    expect(page.locator("#bi-dp-msg")).to_contain_text("Rien ne change d'ici là")
    corps = [json.loads(d) for (m, u, d) in vues]
    assert corps == [
        {"documents": [{"document_id": decor["docs"]["Oreille"], "reponse": "zero",
                        "album_id": decor["albums"]["Oreille"]}]},
        {"documents": [{"document_id": decor["docs"]["Lotus"], "reponse": "rejoindre",
                        "album_id": decor["albums"]["Lotus"]}]}], corps
    # Lotus n'est PAS dans Lot B ; une copie vierge d'Oreille, si.
    lignes = page.locator("#panneau-albums tr.col-album")
    expect(lignes).to_have_count(1)
    expect(lignes.first).to_contain_text("Oreille")


# =========================================================================== #
# « Sur les collections » — cocher = rejoindre, décocher = supprimer de la collection
# =========================================================================== #
def test_cocher_une_collection_demande_et_le_dit(page, decor):
    """Sam lit Lotus par Lot A et écrit dans Lot B. Cocher Lot B se DEMANDE à Ana : la case
    passe indéterminée, « demandé », et la phrase ne dit jamais « Fait ». Rechargée, la page
    le redit (le serveur publie `rejoindre_demande`)."""
    _choisir_projet(page, decor)
    _ouvrir(page, decor["base"], _comme("sam"), f"/corpus?album={decor['albums']['Lotus']}")
    page.locator("#album-range[data-pret]").wait_for(timeout=5000)
    expect(page.locator("#album-range-cases legend")).to_have_text("Sur les collections")
    lot_a = page.locator(f'#album-range-cases input[data-ranger="{decor["lot_a"]}"]')
    lot_b = page.locator(f'#album-range-cases input[data-ranger="{decor["lot_b"]}"]')
    expect(lot_a).to_be_checked()
    expect(lot_a).to_be_disabled()            # il ne fait que la lire
    expect(lot_b).not_to_be_checked()
    expect(lot_b).to_be_enabled()
    with page.expect_response(lambda r: r.request.method == "PUT"
                              and r.url.endswith(f"/collections/{decor['lot_b']}")) as rep:
        lot_b.click()
    assert rep.value.status == 202
    msg = page.locator("#album-range-msg")
    expect(msg).to_contain_text("La demande est partie", timeout=5000)
    assert not msg.inner_text().startswith("Fait")
    lot_b = page.locator(f'#album-range-cases input[data-ranger="{decor["lot_b"]}"]')
    expect(lot_b).to_be_disabled()
    assert lot_b.evaluate("(x) => x.indeterminate") is True
    expect(page.locator(f'#album-range-cases label:has(input[data-ranger="{decor["lot_b"]}"]) '
                        ".reponse.demande")).to_have_text("demandé")
    page.reload(wait_until="networkidle")
    page.locator("#album-range[data-pret]").wait_for(timeout=5000)
    lot_b = page.locator(f'#album-range-cases input[data-ranger="{decor["lot_b"]}"]')
    assert lot_b.evaluate("(x) => x.indeterminate") is True
    expect(lot_b).to_be_disabled()


def test_cocher_puis_decocher_quand_on_tient_tout(page, decor):
    """L'administrateur tient tout : cocher range tout de suite (« Fait »), décocher supprime
    de la collection — sans rien à confirmer, le travail restant dans Lot A."""
    _choisir_projet(page, decor)
    _ouvrir(page, decor["base"], chemin=f"/corpus?album={decor['albums']['Oreille']}")
    page.locator("#album-range[data-pret]").wait_for(timeout=5000)
    lot_b = page.locator(f'#album-range-cases input[data-ranger="{decor["lot_b"]}"]')
    lot_b.click()
    expect(page.locator("#album-range-msg")).to_contain_text(
        "Fait : « Oreille » est aussi rangé dans « Lot B »", timeout=5000)
    lot_b = page.locator(f'#album-range-cases input[data-ranger="{decor["lot_b"]}"]')
    expect(lot_b).to_be_checked()
    with _client(decor["base"]) as c:
        assert {x["id"] for x in c.get(f"/api/albums/{decor['albums']['Oreille']}/collections").json()} \
            == {decor["lot_a"], decor["lot_b"]}
    lot_b.click()
    expect(page.locator("#album-range-msg")).to_contain_text("n'est plus dans « Lot B »",
                                                              timeout=5000)
    with _client(decor["base"]) as c:
        assert {x["id"] for x in c.get(f"/api/albums/{decor['albums']['Oreille']}/collections").json()} \
            == {decor["lot_a"]}


# =========================================================================== #
# Les demandes reçues — le propriétaire, et lui seul
# =========================================================================== #
def test_le_proprietaire_lit_et_accepte_une_demande(page, decor):
    with _client(decor["base"], _comme("sam")) as c:
        demande = _ok(c.put(f"/api/albums/{decor['albums']['Lotus']}/collections/{decor['lot_b']}"),
                      202)["demande_id"]
    _choisir_projet(page, decor)
    # Ni Sam (qui l'a déposée), ni Lia, ni l'administrateur — qui y répond dans « À faire »,
    # en recours : aucune marque, aucun compteur.
    for entetes in (_comme("sam"), _comme("lia"), ADMIN):
        _ouvrir(page, decor["base"], entetes)
        expect(page.locator("#col-body .col-item").first).to_be_visible(timeout=5000)
        page.wait_for_timeout(300)
        expect(page.locator(".col-marque")).to_have_count(0)
        expect(page.locator("#bi-recues-compteur")).to_have_count(0)
    vues = _requetes(page, "/reponse")
    _ouvrir(page, decor["base"], _comme("ana"))
    compteur = page.locator("#bi-recues-compteur")
    expect(compteur).to_have_text("1 demande à répondre", timeout=5000)
    marque = page.locator(f'#col-body .col-item[data-id="{decor["lot_a"]}"] .col-marque')
    expect(marque).to_contain_text("⚑ 1")
    expect(page.locator("#site-nav .col-marque, #site-nav .bi-onglet-pastille")).to_have_count(0)
    compteur.click()
    onglet = page.locator('#col-fiche [role="tab"][data-onglet="albums"]')
    expect(onglet).to_have_attribute("aria-selected", "true", timeout=5000)
    expect(onglet.locator(".bi-onglet-pastille")).to_be_visible()
    bloc = page.locator("#bi-recues-bloc")
    expect(bloc).to_be_visible()
    expect(bloc).to_contain_text("sam")
    expect(bloc).to_contain_text("« Lotus » soit aussi rangé dans « Lot B »")
    bloc.locator(f'[data-repondre="{demande}"][data-reponse="acceptee"]').click()
    expect(page.locator("#bi-recues-msg")).to_contain_text("le travail est partagé", timeout=5000)
    assert [json.loads(d) for (m, u, d) in vues] == [{"reponse": "acceptee"}]
    expect(page.locator("#bi-recues-bloc")).to_have_count(0)
    expect(page.locator(".col-marque")).to_have_count(0)
    expect(page.locator("#bi-recues-compteur")).to_have_count(0)
    expect(onglet.locator(".bi-onglet-pastille")).to_be_hidden()


# =========================================================================== #
# « + Nouvel album » et « Supprimer… » d'une copie qui a une sœur
# =========================================================================== #
def test_nouvel_album_preselectionne_la_base_sauf_depuis_une_collection(page, decor):
    _choisir_projet(page, decor)
    _ouvrir(page, decor["base"])
    expect(page.locator("#biblio-fiche h3")).to_be_visible(timeout=5000)
    page.locator("#btn-new").click()
    expect(page.locator("#m-collection")).to_have_value(str(decor["base_id"]), timeout=5000)
    # La note qui annonçait « une collection par défaut, créée à cette occasion » est partie.
    expect(page.locator("#m-collection-note")).not_to_contain_text("par défaut")
    page.locator("#m-cancel").click()
    page.locator(f'#col-body [data-ouvrir-col="{decor["lot_b"]}"]').click()
    expect(page.locator(f'#col-fiche[data-id="{decor["lot_b"]}"]')).to_be_visible()
    page.locator("#btn-new").click()
    expect(page.locator("#m-collection")).to_have_value(str(decor["lot_b"]), timeout=5000)
    assert "collection par défaut" not in page.locator("#album-modal").inner_text()


def test_supprimer_une_copie_qui_a_une_soeur_dit_que_ses_images_restent(page, decor):
    with _client(decor["base"]) as c:
        r = _ok(c.post(f"/api/collections/{decor['base_id']}/prendre", json={
            "documents": [{"document_id": decor["docs"]["Lotus"], "reponse": "zero"}]}))
        soeur = r["documents"][0]["copie_id"]
    _choisir_projet(page, decor)
    _ouvrir(page, decor["base"], chemin=f"/corpus?album={soeur}")
    page.locator('#album-detail [data-act="supprimer"]').click()
    texte = page.locator("#sp-def-texte")
    expect(texte).to_contain_text("Ses images restent : une autre copie de ce document les emploie.",
                                  timeout=5000)
    assert "Lot A" not in texte.inner_text()
    # Le message de fin ne contredit pas le panneau : la copie part, ses images restent.
    expect(page.locator("#sp-def")).to_have_text("Supprimer définitivement")
    page.locator("#sp-def").click()
    expect(page.locator(".toast", has_text="cette copie est supprimée définitivement"))         .to_have_text("« Lotus » : cette copie est supprimée définitivement, avec le travail "
                      "fait dessus. Ses images restent : une autre copie de ce document les "
                      "emploie.", timeout=5000)
    # Oreille n'a pas de sœur : la phrase ne s'y dit pas.
    _ouvrir(page, decor["base"], chemin=f"/corpus?album={decor['albums']['Oreille']}")
    page.locator('#album-detail [data-act="supprimer"]').click()
    expect(page.locator("#sp-def-texte")).not_to_contain_text("Ses images restent", timeout=5000)


# =========================================================================== #
# Relecture croisée de t3a-c4 — ce que l'écran disait de trop, ou pas assez
# =========================================================================== #
def test_une_copie_gardee_au_fonds_se_dit_sur_sa_notice(page, decor):
    """`garde_au_fonds`, publié par les notices, se lit : la ligne dit qu'une copie du projet
    est gardée au fonds, et mène à la fiche du projet où son responsable demande à la
    rendre. Le motif est marqué obligatoire AVANT le clic."""
    with _client(decor["base"]) as c:
        _ok(c.delete(f"/api/albums/{decor['albums']['Oreille']}/collections/{decor['lot_a']}"), 204)
    _choisir_projet(page, decor)
    _ouvrir(page, decor["base"], _comme("rui"))
    page.locator("#bi-prendre-fonds").click()
    expect(page.locator("#bi-prise-motif")).to_have_attribute("aria-required", "true")
    expect(page.locator("#bi-prise-motif")).to_have_attribute("required", "")
    page.locator("#bi-prise-q").fill("Oreille")
    ligne = page.locator(f'#bi-prise-notices li[data-notice="{decor["docs"]["Oreille"]}"]')
    garde = ligne.locator("a.bi-garde")
    expect(garde).to_have_text("une copie de ce projet est gardée au fonds — la demander à rendre ↗",
                               timeout=5000)
    expect(garde).to_have_attribute("href", f"/administration?vue=projets&projet={decor['projet']}")
    expect(ligne.locator(".bi-deja")).to_have_count(0)
    # Le pied ne promet rien que le serveur ne tiendrait pas.
    assert "ce que le projet a déjà" not in page.locator(".bi-prise-actions").inner_text()


def test_un_rejoindre_deja_demande_ne_se_redemande_pas(page, decor):
    """Dans « + Prendre dans le projet… », un album dont le rejoindre vers CETTE collection
    attend dit « rejoindre demandé » au lieu d'offrir un geste que le serveur refuserait."""
    with _client(decor["base"], _comme("sam")) as c:
        _ok(c.put(f"/api/albums/{decor['albums']['Lotus']}/collections/{decor['lot_b']}"), 202)
    _choisir_projet(page, decor)
    _ouvrir(page, decor["base"], _comme("sam"), f"/corpus?collection={decor['lot_b']}&onglet=albums")
    page.locator("#bi-dans-projet").click()
    lotus = page.locator(f'#bi-dans-projet-panneau li[data-dp-album="{decor["albums"]["Lotus"]}"]')
    expect(lotus.locator(".reponse.demande")).to_have_text("rejoindre demandé", timeout=5000)
    expect(lotus.locator('[data-dp="rejoindre"]')).to_have_count(0)
    expect(lotus.locator('[data-dp="copie"]')).to_be_visible()


def test_sous_une_portee_totale_la_case_demandee_reste_un_geste(page, decor):
    """Un rejoindre attend ; l'administrateur coche lui-même : c'est fait, et la demande est
    close au serveur — elle ne reste pas offerte au propriétaire."""
    with _client(decor["base"], _comme("sam")) as c:
        demande = _ok(c.put(f"/api/albums/{decor['albums']['Lotus']}/collections/{decor['lot_b']}"),
                      202)["demande_id"]
    _choisir_projet(page, decor)
    _ouvrir(page, decor["base"], chemin=f"/corpus?album={decor['albums']['Lotus']}")
    page.locator("#album-range[data-pret]").wait_for(timeout=5000)
    case = page.locator(f'#album-range-cases input[data-ranger="{decor["lot_b"]}"]')
    expect(case).to_be_enabled()
    case.click()
    expect(page.locator("#album-range-msg")).to_contain_text("Fait :", timeout=5000)
    with _client(decor["base"]) as c:
        d = {x["id"]: x for x in c.get("/api/demandes").json()}[demande]
        assert (d["en_attente"], d["reponse"]) == (False, "acceptee"), d
    with _client(decor["base"], _comme("ana")) as c:
        assert c.get(f"/api/collections/{decor['lot_a']}/demandes").json() == []


# =========================================================================== #
# 320 px, grande police
# =========================================================================== #
_CORPS_QUI_DEFILE = """() => {
  const cands = [document.documentElement, document.body, ...document.querySelectorAll("main")];
  return cands.filter(Boolean).filter((el) => el.scrollWidth > el.clientWidth + 1)
    .map((el) => el.tagName + (el.id ? "#" + el.id : "") + " " + el.clientWidth + "/" + el.scrollWidth);
}"""


@pytest.mark.parametrize("police", [16, 24])
def test_les_panneaux_de_la_3a_tiennent_a_320_px(page, decor, police):
    """Les deux panneaux de la prise, le bloc ⚑ et les cases tiennent dans 320 px sous une
    grande police : le corps de la page ne défile pas de côté. L'instrument est recopié de
    `test_e2e_reflow.py` (deux lignes), pour la raison qui y est écrite."""
    with _client(decor["base"], _comme("sam")) as c:
        _ok(c.put(f"/api/albums/{decor['albums']['Lotus']}/collections/{decor['lot_b']}"), 202)
    page.set_viewport_size({"width": 320, "height": 800})
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": police, "fixed": police}})
    _choisir_projet(page, decor)

    _ouvrir(page, decor["base"], _comme("rui"))
    page.locator("#bi-prendre-fonds").click()
    page.locator("#bi-prise-q").fill("Hors")
    page.locator("#bi-prise-notices li[data-notice]").first.wait_for(timeout=5000)
    assert page.evaluate(_CORPS_QUI_DEFILE) == [], "prendre du fonds, en tête du corpus"

    _ouvrir(page, decor["base"], _comme("ana"), f"/corpus?collection={decor['lot_a']}&onglet=albums")
    page.locator("#bi-recues-bloc").wait_for(timeout=5000)
    assert page.evaluate(_CORPS_QUI_DEFILE) == [], "le bloc ⚑ des demandes reçues"

    _ouvrir(page, decor["base"], _comme("sam"), f"/corpus?collection={decor['lot_b']}&onglet=albums")
    page.locator("#bi-dans-projet").click()
    page.locator("#bi-dp-liste li").first.wait_for(timeout=5000)
    assert page.evaluate(_CORPS_QUI_DEFILE) == [], "prendre dans le projet"

    _ouvrir(page, decor["base"], _comme("sam"), f"/corpus?album={decor['albums']['Lotus']}")
    page.locator("#album-range[data-pret]").wait_for(timeout=5000)
    assert page.evaluate(_CORPS_QUI_DEFILE) == [], "« Sur les collections »"
