"""COL-3, tranche 2 — le fonds et ses demandes, vus de l'Administration, dans un navigateur.

Le serveur est mesuré par `tests/test_fonds.py` : qui voit le fonds, qui répond, ce qu'une
réponse détruit. Ce fichier mesure ce que l'ÉCRAN en fait, et que rien d'autre ne verrait :

- le bloc « Le fonds » se lève pour qui le tient, et reste fermé — sans un mot — aux autres ;
- la page s'ouvre sur « À faire » quand une demande attend, la plus ancienne en tête ; une
  demande est aussi dans « À regarder », NOMMÉE, et son signal mène à la demande dans
  « À faire », jamais à la fiche d'un compte (mutant 18 du cadrage) ;
- la liste du fonds se cherche par titre, série ou auteur, par état, projet et importateur ;
- « Garder » et « Détruire » partent avec la bonne réponse, et « À regarder » se relit ;
- une copie gardée se REND à une collection de son projet, et un document que personne
  n'appelle se détruit ;
- « Importer au fonds » fait naître un album appelé par personne, ses planches avec lui, et
  l'Atelier, la Recherche et l'Exploration ne le proposent pas tant qu'il n'est pas rendu ;
- le responsable d'un projet en DEMANDE la suppression, motif à l'appui (décision B5) ;
- « À faire » et la fiche du fonds tiennent à 320 px sous une grande police.

Chaque geste est mesuré sur la requête PARTIE, pas sur l'état final seul : le serveur
répondrait juste à un écran qui enverrait autre chose.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

import database  # noqa: E402
from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.parametrize("live_server", [True], indirect=True)]

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/administration", "/", "/recherche", "/exploration")
SURFACES_HORS_PERIMETRE = {
    "/corpus": "la Bibliothèque a ses deux réponses à « supprimer », jouées dans "
               "test_e2e_collections.py ; le fonds ne s'y montre pas",
}

EN_TETE = next(k for k in ECRITURE if k not in ("Remote-User", "Remote-Groups"))
ADMIN = {**ECRITURE}


def _comme(login, **groupes):
    return {"Remote-User": login, EN_TETE: "1", **groupes}


def _client(base, entetes=None):
    return httpx.Client(base_url=base, trust_env=False, timeout=60, headers=entetes or ADMIN)


def _decor(base):
    """Une collection « Étude » dans le projet de repli, où `sam` écrit ; deux albums
    importés par l'administrateur, « Seul » et « Doublon » ; une demande de `sam` sur chacun.
    Un second projet, « Séminaire », vide, dont `rui` est responsable."""
    with _client(base) as c:
        cid = c.post("/api/collections", json={"nom": "Étude"}).json()["id"]
        autre = c.post("/api/collections", json={"nom": "Archives"}).json()["id"]
        albums = {}
        for titre in ("Seul", "Doublon", "Gardé"):
            albums[titre] = c.post("/api/albums", json={"titre": titre,
                                                        "collection_id": cid}).json()["id"]
            r = c.post(f"/api/albums/{albums[titre]}/import",
                       files={"file": ("p.png", make_png(), "image/png")})
            assert r.status_code == 201, r.text
        r = c.put(f"/api/collections/{cid}/acces",
                  json={"genre": "utilisateur", "principal": "sam", "niveau": "ecriture"})
        assert r.status_code == 200, r.text
        projet = c.post("/api/projets", json={"nom": "Séminaire"}).json()["id"]
        r = c.put(f"/api/projets/{projet}/membres",
                  json={"genre": "utilisateur", "principal": "rui", "role": "responsable"})
        assert r.status_code in (200, 201), r.text
        # « Gardé » quitte sa dernière collection : sa copie est gardée au fonds.
        r = c.delete(f"/api/albums/{albums['Gardé']}/collections/{cid}")
        assert r.status_code == 204, r.text
    demandes = {}
    with _client(base, _comme("sam")) as c:
        for titre, motif in (("Seul", "Importé dans la mauvaise étude."),
                             ("Doublon", "Doublon de « Seul ».")):
            r = c.post("/api/demandes", json={"genre": "suppression_document",
                                              "album_id": albums[titre], "motif": motif,
                                              "certifie": True})
            assert r.status_code == 201, r.text
            demandes[titre] = r.json()["id"]
    return {"collection": cid, "archives": autre, "albums": albums, "demandes": demandes,
            "projet": projet}


def _ouvrir_admin(page, base, entetes=None, chemin="/administration"):
    page.set_extra_http_headers({k: v for k, v in (entetes or ADMIN).items() if k != EN_TETE})
    page.goto(base + chemin, wait_until="networkidle")


def _requetes(page, chemin):
    parties = []
    page.on("request", lambda r: parties.append(r) if chemin in r.url
            and r.method != "GET" else None)
    return parties


def _document_de(base, album_id):
    with _client(base) as c:
        return next(d["id"] for d in c.get("/api/fonds").json()["documents"]
                    if any(x["album_id"] == album_id for x in d["copies"]))


def _choisir(page, titre):
    """Ouvre la fiche d'un document depuis la liste du fonds."""
    page.locator("#fd-objets .fd-objet", has_text=titre).first.click()
    expect(page.locator("#fd-fiche-titre")).to_have_text(titre)


def test_le_fonds_ne_se_montre_qu_a_qui_le_tient(page, live_server):
    """Sam écrit dans « Étude » et a déposé deux demandes : le fonds ne lui est pas montré,
    ni ses demandes, ni « À regarder », ni « À faire » — ni leurs liens de vue, même quand
    l'adresse nomme la vue. L'administrateur voit les trois."""
    _decor(live_server)
    _ouvrir_admin(page, live_server, _comme("sam"), "/administration?vue=fonds")
    page.wait_for_timeout(300)
    expect(page.locator("#fonds-bloc")).to_be_hidden()
    expect(page.locator("#cg-bloc")).to_be_hidden()
    expect(page.locator("#afaire-bloc")).to_be_hidden()
    for vue in ("afaire", "fonds", "comptes"):
        expect(page.locator(f"#vue-lien-{vue}")).to_be_hidden()
    assert "Importé dans la mauvaise étude" not in page.inner_text("body")

    _ouvrir_admin(page, live_server, chemin="/administration?vue=fonds")
    expect(page.locator("#fonds-bloc")).to_be_visible()
    expect(page.locator("#vue-lien-fonds")).to_have_attribute("aria-current", "page")
    expect(page.locator("#fd-compte")).to_have_text(
        "3 documents · 1 appelé par personne · 2 suppressions demandées")


def test_une_demande_se_repond_sur_place_dans_a_faire(page, live_server):
    """Deux demandes attendent : la page s'OUVRE sur « À faire », la plus ancienne en tête.
    « À regarder » nomme la demande et y MÈNE — dépliée, jamais la fiche du compte qui l'a
    déposée. On répond sur place : « Garder » la clôt, « Détruire » efface le document —
    chacun parti avec SA réponse — et « À regarder » se relit."""
    d = _decor(live_server)
    parties = _requetes(page, "/api/demandes/")
    _ouvrir_admin(page, live_server)
    # L'ouverture : quelque chose attend, donc « À faire » (Hugo, 2026-10-16).
    expect(page.locator("#vue-lien-afaire")).to_have_attribute("aria-current", "page")
    expect(page.locator("#afaire-bloc")).to_be_visible()
    expect(page.locator("#fonds-bloc")).to_be_hidden()
    lignes = page.locator("#af-demandes-liste > li")
    expect(lignes).to_have_count(2)
    # La plus ancienne d'abord : « Seul » a été demandé avant « Doublon ».
    expect(lignes.nth(0)).to_contain_text("« Seul »")
    expect(lignes.nth(1)).to_contain_text("« Doublon »")

    # « À regarder », dans « Comptes et groupes », mène à la demande dans « À faire ».
    page.click("#vue-lien-comptes")
    signaux = page.locator("#cg-signaux")
    lien = signaux.locator("button.cg-lien",
                           has_text="sam demande la suppression définitive de « Seul »")
    expect(lien).to_be_visible(timeout=5000)
    lien.click()
    # Mutant 18 : le signal mène à la DEMANDE, pas à la fiche du compte qui l'a déposée.
    cible = f"fd-demande-{d['demandes']['Seul']}"
    page.wait_for_function("id => document.activeElement && document.activeElement.id === id",
                           arg=cible, timeout=5000)
    assert "vue=afaire" in page.url, page.url
    expect(page.locator("#cg-fiche")).not_to_contain_text("sam")
    demande = page.locator(f"#{cible}")
    expect(demande.locator("[data-af-deplier]")).to_have_attribute("aria-expanded", "true")
    expect(demande).to_contain_text("Importé dans la mauvaise étude.")
    expect(demande).to_contain_text("depuis « Projet principal »")
    # La certification, et ce que d'autres que sam y ont fait (Hugo, 2026-10-15) : ici
    # l'administrateur qui a importé — la naissance du document et son scan.
    certif = demande.locator(".fd-certif")
    expect(certif).to_be_visible()
    expect(certif).to_contain_text("Certifié par sam le ")
    expect(certif).to_contain_text(" : ces données ne sont pas importantes.")
    autres = demande.locator(".fd-autres")
    expect(autres).to_be_visible()
    expect(autres).to_contain_text("Copie créée par decor.")
    expect(autres).to_contain_text("Gestes d'autres personnes, lus au journal — un geste "
                                   "défait depuis compte encore :")
    expect(autres).not_to_contain_text("compte partagé")
    expect(autres.locator("li")).to_have_count(1)
    expect(autres.locator("li")).to_contain_text(
        "decor : 2 gestes sur le document (import, scans, notice) — dernier le ")

    # Garder : la demande se clôt, rien n'est effacé.
    titre_regarder = page.locator("#cg-regarder-titre")
    avant = int(titre_regarder.text_content().split("(")[1].rstrip(")"))
    demande.locator("[data-fd-refuser]").click()
    expect(page.locator("#af-msg")).to_have_text("« Seul » : gardé. La demande de sam est close.")
    expect(page.locator(f"#{cible}")).to_have_count(0)
    assert parties[-1].post_data_json == {"reponse": "refusee"}
    expect(lien).to_have_count(0)
    # « À regarder » s'est relu : une ligne de moins, celle de la demande close.
    expect(titre_regarder).to_contain_text(f"À regarder ({avant - 1})")

    # Détruire : la ligne se déplie, confirmé, puis le document quitte le fonds.
    doublon = page.locator(f"#fd-demande-{d['demandes']['Doublon']}")
    expect(doublon.locator("[data-fd-accepter]")).to_have_count(0)
    doublon.locator("[data-af-deplier]").click()
    confirmations = []
    page.once("dialog", lambda dl: (confirmations.append(dl.message), dl.accept()))
    doublon.locator("[data-fd-accepter]").click()
    expect(page.locator("#af-msg")).to_contain_text("« Doublon » : détruit")
    assert "Irréversible" in confirmations[0], confirmations
    assert parties[-1].post_data_json == {"reponse": "acceptee"}
    expect(page.locator("#af-demandes")).to_be_hidden()
    expect(titre_regarder).to_contain_text(f"À regarder ({avant - 2})")
    expect(signaux).not_to_contain_text("demande la suppression")
    expect(page.locator("#fd-objets")).not_to_contain_text("Doublon")
    with _client(live_server) as c:
        titres = {a["titre"] for a in c.get("/api/albums").json()}
    assert "Doublon" not in titres and "Seul" in titres


def test_le_fonds_se_cherche_par_titre_projet_importateur_et_etat(page, live_server):
    """La liste du fonds se filtre par les quatre entrées nommées par Hugo : le texte (titre,
    série, auteur), l'état, le projet, qui l'a importé. La fiche d'un document demandé MÈNE à
    « À faire », et l'adresse nomme le document ouvert."""
    d = _decor(live_server)
    _ouvrir_admin(page, live_server, chemin="/administration?vue=fonds")
    objets = page.locator("#fd-objets .fd-objet")
    expect(objets).to_have_count(3)
    page.fill("#fd-filtre", "doub")
    expect(objets).to_have_count(1)
    expect(objets.first).to_contain_text("Doublon")
    page.fill("#fd-filtre", "")
    page.click("[data-fd-etat='demande']")
    expect(objets).to_have_count(2)
    page.click("[data-fd-etat='gardee']")
    expect(objets).to_have_count(1)
    expect(objets.first).to_contain_text("Gardé")
    page.click("[data-fd-etat='tous']")
    page.select_option("#fd-importeur", "decor")
    expect(objets).to_have_count(3)
    # Tous trois sont du projet de repli : « Sans projet » n'est pas proposé, faute de document.
    assert page.locator("#fd-projet option").all_inner_texts() == ["Tous", "Projet principal"]
    page.select_option("#fd-projet", label="Projet principal")
    expect(objets).to_have_count(3)
    page.fill("#fd-filtre", "introuvable")
    expect(objets).to_have_count(0)
    expect(page.locator("#fd-objets")).to_contain_text("Aucun document ne répond à ces filtres.")
    page.fill("#fd-filtre", "")
    _choisir(page, "Seul")
    assert f"document={_document_de(live_server, d['albums']['Seul'])}" in page.url, page.url
    page.click("[data-fd-repondre]")
    expect(page.locator("#vue-lien-afaire")).to_have_attribute("aria-current", "page")
    expect(page.locator(f"#fd-demande-{d['demandes']['Seul']}")).to_be_focused()


def test_rendre_une_copie_gardee_et_detruire_ce_que_personne_n_appelle(page, live_server):
    """« Gardé » a quitté sa dernière collection : sa fiche le dit, propose de le rendre à une
    collection de son projet, et le rend avec sa planche. Puis, retiré de nouveau, il se
    détruit d'ici."""
    d = _decor(live_server)
    parties = _requetes(page, "/api/albums/")
    _ouvrir_admin(page, live_server, chemin="/administration?vue=fonds")
    _choisir(page, "Gardé")
    carte = page.locator("#fd-fiche")
    expect(carte).to_contain_text("copie gardée")
    expect(carte).to_contain_text("Copie gardée ici (projet « Projet principal »).")
    choix = carte.locator(".fd-gardee select")
    expect(choix.locator("option")).to_have_count(3)
    # Les collections de SON projet, dans l'ordre où le serveur les rend — sa collection de
    # base comprise, née avec le projet de repli (D10).
    assert sorted(choix.locator("option").all_inner_texts()) == [
        "Archives", database.NOM_PROJET_DEFAUT, "Étude"]
    choix.select_option(str(d["archives"]))
    carte.locator("[data-fd-rendre]").click()
    expect(carte.locator(".fd-ligne-msg")).to_have_text(
        "Copie rendue à « Archives », avec tout son travail.")
    assert parties[-1].method == "PUT"
    assert parties[-1].url.endswith(f"/api/albums/{d['albums']['Gardé']}/collections/{d['archives']}")
    expect(carte).to_contain_text("Employé par Projet principal : Archives")
    expect(carte.locator("[data-fd-detruire]")).to_have_count(0)

    with _client(live_server) as c:
        r = c.delete(f"/api/albums/{d['albums']['Gardé']}/collections/{d['archives']}")
        assert r.status_code == 204, r.text
    # L'adresse nomme le document : recharger rouvre sa fiche.
    page.reload(wait_until="networkidle")
    expect(page.locator("#fd-fiche-titre")).to_have_text("Gardé")
    confirmations = []
    page.once("dialog", lambda dl: (confirmations.append(dl.message), dl.accept()))
    carte.locator("[data-fd-detruire]").click()
    expect(page.locator("#fd-msg")).to_contain_text("« Gardé » : détruit")
    assert "Détruire « Gardé »" in confirmations[0], confirmations
    assert parties[-1].method == "DELETE"
    assert parties[-1].url.endswith(f"/api/albums/{d['albums']['Gardé']}")
    expect(page.locator("#fd-objets .fd-objet", has_text="Gardé")).to_have_count(0)


def test_importer_au_fonds_puis_le_distribuer(page, live_server):
    """Un album importé au fonds naît appelé par personne, sa planche avec lui ; l'Atelier,
    la Recherche et l'Exploration ne le proposent pas. Rendu à une collection, il y entre."""
    d = _decor(live_server)
    parties = _requetes(page, "/api/albums")
    _ouvrir_admin(page, live_server, chemin="/administration?vue=fonds")
    page.click("#fd-importer-ouvrir")
    expect(page.locator("#fd-titre")).to_be_focused()
    page.fill("#fd-titre", "Corpus à venir")
    page.set_input_files("#fd-fichiers", files=[
        {"name": "p1.png", "mimeType": "image/png", "buffer": make_png()}])
    # À 1 440 px, le bouton reste près de son champ (relevé sur capture : il partait au bord
    # droit de la page).
    page.set_viewport_size({"width": 1440, "height": 900})
    champ, bouton = page.locator("#fd-fichiers").bounding_box(), page.locator("#fd-importer").bounding_box()
    assert 0 <= bouton["x"] - (champ["x"] + champ["width"]) <= 24, (champ, bouton)
    page.click("#fd-importer")
    carte = page.locator("#fd-fiche")
    expect(carte.locator(".fd-ligne-msg")).to_have_text(
        "« Corpus à venir » est au fonds, appelé par personne : 1 planche importée.", timeout=10000)
    creation = [r for r in parties if r.method == "POST" and r.url.endswith("/api/albums")]
    assert creation and creation[0].post_data_json == {"titre": "Corpus à venir", "au_fonds": True}
    expect(page.locator("#fd-fiche-titre")).to_have_text("Corpus à venir")
    expect(carte).to_contain_text("appelé par personne")
    expect(carte).to_contain_text("1 planche")
    expect(carte).to_contain_text("Copie gardée ici (sans projet).")

    # Les surfaces de travail, dérivées de la déclaration : l'Atelier a son sélecteur
    # d'album, la Recherche et l'Exploration leur filtre.
    for chemin in (s for s in SURFACES_AUDITEES if s != "/administration"):
        selecteur = "#album-select" if chemin == "/" else "#f-album"
        page.goto(live_server + chemin, wait_until="networkidle")
        options = page.locator(f"{selecteur} option").all_inner_texts()
        assert options and not any("Corpus à venir" in o for o in options), (chemin, options)

    page.goto(live_server + "/administration?vue=fonds", wait_until="networkidle")
    _choisir(page, "Corpus à venir")
    carte.locator(".fd-gardee select").select_option(str(d["collection"]))
    carte.locator("[data-fd-rendre]").click()
    expect(carte.locator(".fd-ligne-msg")).to_have_text(
        "Copie rendue à « Étude », avec tout son travail.")
    page.goto(live_server + "/recherche", wait_until="networkidle")
    assert any("Corpus à venir" in o for o in page.locator("#f-album option").all_inner_texts())


def test_le_responsable_demande_la_suppression_de_son_projet(page, live_server):
    """Rui règle « Séminaire » sans en décider : il en DEMANDE la suppression. Le motif ne
    s'ouvre qu'au clic sur « Demander sa suppression… » — un geste rare n'a pas de champ à
    demeure — et « Annuler » le referme. Sans motif rien ne part ; avec, la requête le porte,
    la fiche dit que la demande attend, et le message se lit CONTRE ce qui a changé, sans
    rien pousser au-dessus. L'administrateur y répond depuis « À faire » : le projet, vide,
    est supprimé."""
    d = _decor(live_server)
    parties = _requetes(page, "/api/demandes")
    _ouvrir_admin(page, live_server, _comme("rui"))
    # Rui ne tient ni le fonds ni les comptes : la page s'ouvre sur les projets.
    expect(page.locator("#vue-lien-projets")).to_have_attribute("aria-current", "page")
    titre = page.locator("#pj-fiche-titre")
    expect(titre).to_have_text("Séminaire", timeout=5000)
    expect(page.locator("#pj-demander-motif")).to_have_count(0)
    ouvrir = page.locator("[data-pj-demander-ouvrir]")
    expect(ouvrir).to_have_text("Demander sa suppression…")
    ouvrir.click()
    expect(page.locator("#pj-demander-motif")).to_be_focused()
    page.click("[data-pj-demander-annuler]")
    expect(page.locator("#pj-demander-motif")).to_have_count(0)
    expect(ouvrir).to_be_focused()
    ouvrir.click()
    # Où la fiche commence DANS son bloc : la page défile (le focus suit le geste), le bloc ne
    # doit pas, lui, s'allonger au-dessus d'elle. La fiche défile seule dans son cadre (le
    # gabarit liste-et-fiche) : ce défilement-là, dû au focus, se rajoute — il ne déplace
    # rien DANS le bloc.
    decalage = """() => document.querySelector('#pj-fiche-titre').getBoundingClientRect().top
                       + document.querySelector('#pj-fiche').scrollTop
                       - document.querySelector('#projets-bloc').getBoundingClientRect().top"""
    haut = page.evaluate(decalage)
    page.click("[data-pj-demander]")
    message = page.locator("#pj-demander-msg")
    expect(message).to_be_visible()
    expect(message).to_contain_text("Dites pourquoi")
    assert not parties
    page.fill("#pj-demander-motif", "Le séminaire est annulé.")
    page.click("[data-pj-demander]")
    etat = page.locator(".pj-demande-etat")
    expect(etat).to_contain_text("suppression demandée le")
    assert parties[-1].post_data_json == {"genre": "suppression_projet", "projet_id": d["projet"],
                                          "motif": "Le séminaire est annulé."}
    expect(page.locator("[data-pj-demander], [data-pj-demander-ouvrir]")).to_have_count(0)
    # Le message contre la puce qui remplace le geste ; rien ne s'est écrit en tête du bloc,
    # et la fiche n'a pas bougé.
    expect(message).to_be_visible()
    expect(message).to_contain_text("Votre demande est partie à un administrateur")
    e, m = etat.bounding_box(), message.bounding_box()
    assert 0 <= m["y"] - (e["y"] + e["height"]) <= 16, (e, m)
    expect(page.locator("#pj-msg")).to_have_text("")
    assert abs(page.evaluate(decalage) - haut) < 1, (haut, page.evaluate(decalage))

    _ouvrir_admin(page, live_server)
    demande = page.locator(".fd-demande", has_text="rui demande la suppression du projet « Séminaire »")
    expect(demande).to_be_visible(timeout=5000)
    demande.locator("[data-af-deplier]").click()
    expect(demande).to_contain_text("Le séminaire est annulé.")
    page.once("dialog", lambda dl: dl.accept())
    demande.locator("[data-fd-accepter]").click()
    expect(page.locator("#af-msg")).to_have_text("Le projet « Séminaire » est supprimé.")
    with _client(live_server) as c:
        assert "Séminaire" not in {p["nom"] for p in c.get("/api/projets").json()}


@pytest.mark.parametrize("police", [16, 24])
def test_le_fonds_ne_fait_pas_defiler_la_page_de_cote(page, live_server, police):
    """À 320 px, « À faire » — une demande dépliée — et la fiche d'une copie gardée tiennent
    dans la page : le corps ne défile pas de côté (règle de CLAUDE.md), sous la police par
    défaut et sous une préférence de 24. Le titre d'un document est long et sans espace."""
    d = _decor(live_server)
    with _client(live_server) as c:
        r = c.put(f"/api/albums/{d['albums']['Gardé']}",
                    json={"titre": "Gardé-" + "x" * 60, "serie": "Une série au nom très long"})
        assert r.status_code == 200, r.text
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": police, "fixed": police}})
    page.set_viewport_size({"width": 320, "height": 900})
    sonde = """() => [document.documentElement, document.body,
        ...document.querySelectorAll('main, #header, #afaire-bloc, #fonds-bloc')].filter(Boolean)
        .filter((el) => el.scrollWidth > el.clientWidth + 1)
        .map((el) => `${el.tagName}#${el.id} ${el.clientWidth}/${el.scrollWidth}`)"""
    _ouvrir_admin(page, live_server)
    expect(page.locator(".fd-demande").first).to_be_visible(timeout=5000)
    page.locator(".fd-demande [data-af-deplier]").first.click()
    expect(page.locator(".fd-demande .fd-autres").first).to_be_visible()
    assert not page.evaluate(sonde), page.evaluate(sonde)
    doc = _document_de(live_server, d["albums"]["Gardé"])
    _ouvrir_admin(page, live_server, chemin=f"/administration?vue=fonds&document={doc}")
    expect(page.locator(".fd-gardee select").first).to_be_visible()
    assert not page.evaluate(sonde), page.evaluate(sonde)
    # Sous le seuil étroit, la fiche REMPLACE la liste, et « ← Liste » y ramène.
    page.click("[data-fd-retour]")
    expect(page.locator("#fd-objets .fd-objet").first).to_be_visible()
    assert not page.evaluate(sonde), page.evaluate(sonde)


def test_a_faire_ne_dit_suppression_que_d_une_suppression(page, live_server):
    """COL-3, tranche 3a — une ENTRÉE de documents et un REJOINDRE attendent, à côté des deux
    suppressions du décor. La relecture croisée du serveur de la prise avait trouvé ces deux
    genres présentés en suppression, et ACCEPTÉS par « Détruire » (défaut 1) ; l'écran de la
    3a les rend avec leurs mots : « À faire » les montre, ne les dit jamais « suppression »,
    ne leur offre jamais « Détruire », et le compte du fonds ne compte que les
    suppressions."""
    d = _decor(live_server)
    with _client(live_server, _comme("rui")) as c:
        r = c.post(f"/api/projets/{d['projet']}/prendre",
                   json={"documents": [{"document_id": _document_de(live_server,
                                                                    d["albums"]["Seul"]),
                                        "reponse": "zero"}],
                         "motif": "Pour le séminaire"})
        assert r.status_code == 200 and r.json()["documents"][0]["etat"] == "demande", r.text
    with _client(live_server) as c:
        r = c.put(f"/api/collections/{d['archives']}/acces",
                  json={"genre": "utilisateur", "principal": "sam", "niveau": "ecriture"})
        assert r.status_code == 200, r.text
    with _client(live_server, _comme("sam")) as c:
        r = c.put(f"/api/albums/{d['albums']['Doublon']}/collections/{d['archives']}")
        assert r.status_code == 202, r.text
    _ouvrir_admin(page, live_server)
    lignes = page.locator("#af-demandes-liste > li")
    expect(lignes).to_have_count(4)
    suppressions = page.locator("#af-demandes-liste > li[data-genre=suppression_document]")
    expect(suppressions).to_have_count(2)
    for genre in ("entree_documents", "rejoindre"):
        ligne = page.locator(f"#af-demandes-liste > li[data-genre={genre}]")
        expect(ligne).not_to_contain_text("suppression")
        ligne.locator("[data-af-deplier]").click()
        expect(ligne.locator(".af-detail")).to_be_visible()
        expect(ligne.locator(".af-detail")).not_to_contain_text("Détruire")
        expect(ligne.locator(".af-detail button.danger")).to_have_count(0)
    page.click("#vue-lien-fonds")
    expect(page.locator("#fd-compte")).to_contain_text("2 suppressions demandées")
    page.click("#vue-lien-comptes")
    expect(page.locator("#cg-signaux button.cg-lien",
                        has_text="suppression définitive")).to_have_count(2, timeout=5000)
    signaux = page.inner_text("#cg-signaux")
    assert signaux.count("suppression") == 2, signaux
