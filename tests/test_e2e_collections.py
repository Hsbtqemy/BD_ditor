"""COL-2 — les gestes d'une collection dans la Bibliothèque, joués dans un vrai navigateur.

Ce module ne parle pas d'accessibilité — `test_e2e_a11y.py` audite ces écrans. Il est À
PART pour une raison écrite dans `test_e2e_reflow.py` : un module e2e finit par acquérir
sa propre condition de saut (là-bas, la présence d'axe-core), et tout ce qu'on y a rangé
disparaît avec lui, sans que rien ne le dise. Des tests de COMPORTEMENT n'ont pas à
dépendre d'un outil d'audit.

Chaque test vise un défaut qui ne casse aucun test d'API : le serveur répond juste, et
c'est l'écran qui aurait menti, masqué, effacé ou avalé un refus — ou l'aurait affiché
LOIN du geste, là où personne ne le voit (cf. `_message_du_geste`).

UX-18 (2026-10-17) — la collection n'est plus une section dépliée dans une liste : son NOM,
dans le bloc « Collections », ouvre sa FICHE à droite, en quatre onglets (Albums · Qui entre
· Description · Diffusion et dépôt), et le formulaire s'ouvre au geste (« Modifier »). Les
gestes sont les mêmes ; « dans la collection dépliée » se lit désormais « dans sa fiche ».
"""
import io
import zipfile

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from conftest import ECRITURE, make_png  # noqa: E402
from playwright.sync_api import expect  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source. Les gestes d'une collection
# vivent dans la Bibliothèque depuis COL-2, et ses accès l'ont rejointe avec l'étape 3
# d'AUTH-12 : l'Administration n'a plus de geste de collection à éprouver ici.
SURFACES_AUDITEES = ("/corpus",)
SURFACES_HORS_PERIMETRE = {
    "/administration": "les accès d'une collection se règlent dans la Bibliothèque depuis "
                       "l'étape 3 d'AUTH-12 ; l'Administration ne les montre qu'en lecture",
    "/": "l'Atelier travaille une planche ; aucun geste de collection n'y vit",
    "/recherche": "aucun geste de collection n'y vit",
    "/exploration": "aucun geste de collection n'y vit — le lexique situé y range des "
                    "termes PAR collection, mais ne crée ni ne décrit aucune collection",
}

# L'adresse publique des images d'un manifeste : sans elle, il sort en APERÇU et porte
# un `AVERTISSEMENTS.txt` qui le dit, quel que soit le régime.
BASE_IMAGES = "https://images.example.org/iiif"


@pytest.fixture
def decor(live_server):
    """Un album et une planche importée. La planche compte : un Canvas IIIF exige des
    dimensions master, et un manifeste sans Canvas ne dirait rien des images qu'il porte
    ou retient. Pas d'OCR : écrire un texte réindexerait, donc chargerait spaCy à froid,
    pour rien ici. L'album, créé sans collection, entre dans celle de repli."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=60, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "Collections", "auteur": "X"}).json()["id"]
        c.post(f"/api/albums/{aid}/import",
               files={"file": ("p.png", make_png(), "image/png")})
    finally:
        c.close()
    return {"base": live_server, "album": aid}


def _client(base):
    return httpx.Client(base_url=base, trust_env=False, timeout=60, headers=ECRITURE)


def _collection_du_decor(base, album):
    with _client(base) as c:
        return c.get(f"/api/albums/{album}/collections").json()[0]


def _fiche(page, cid):
    """La fiche de la collection `cid` — un locator, qui se résout dans la fiche REDESSINÉE
    après un enregistrement."""
    return page.locator(f'#col-fiche[data-id="{cid}"]')


def _ouvrir(page, cid, onglet="qui"):
    """Ouvre la fiche d'une collection par son NOM dans la liste, puis l'onglet voulu."""
    page.locator(f'#col-body .col-item[data-id="{cid}"] .col-ouvrir').click()
    fiche = _fiche(page, cid)
    fiche.wait_for(timeout=5000)
    if onglet != "qui":
        fiche.locator(f'[role="tab"][data-onglet="{onglet}"]').click()
    expect(fiche.locator(f"#panneau-{onglet}")).to_be_visible()
    return fiche


def _modifier(page, cid, onglet):
    """Ouvre la collection sur `onglet` et son formulaire (« Modifier »)."""
    fiche = _ouvrir(page, cid, onglet)
    fiche.locator(f'[data-modifier="{onglet}"]').click()
    fiche.locator(f"#panneau-{onglet} [data-enregistrer]").wait_for(timeout=3000)
    return fiche


def _creer(page, nom=None):
    """« + Créer une collection » : le champ n'apparaît qu'au geste (UX-18)."""
    if page.locator("#col-creer-zone").is_hidden():
        page.click("#col-creer")
    expect(page.locator("#col-nom")).to_be_visible()
    if nom is not None:
        page.fill("#col-nom", nom)
    page.click("#col-add")


def _message_du_geste(page, item, motif):
    """Le message qui suit un geste, trouvé par son TEXTE puis SITUÉ à l'écran.

    Trouvé n'importe où dans la page, et non là où le code est censé l'écrire : un
    sélecteur `.col-item .col-msg` lirait encore une ADRESSE, et le défaut vu par la passe
    de recette du 2026-09-16 n'en était pas un. Le refus du nom réservé est arrivé rouge et
    lisible, sous TOUTE la liste — et n'a pas été vu. La suite ne pouvait pas le dire :
    elle lisait le texte et la classe de `#col-msg`, jamais sa place.

    Deux propriétés, qui sont l'attendu de la fiche : le message est DANS la fiche de la
    collection (sa boîte est contenue dans celle de `#col-fiche`), et il se VOIT sans
    défiler, telle que le clic a laissé l'écran. `item` est un locator : après un
    enregistrement la fiche est redessinée, et il se résout dans la nouvelle.

    « Se voit » ne veut pas dire « tombe dans les 720 px du viewport », et la première
    version de ce test confondait les deux. La page défile dans `main`, SOUS un en-tête :
    une boîte peut être dans le viewport tout en étant rognée par le débordement de `main`,
    ou recouverte. Le critère est donc celui d'un œil — le point au début de sa première
    ligne désigne-t-il le message lui-même (`elementFromPoint`) ?"""
    message = page.locator("[role=status]", has_text=motif)
    message.wait_for(timeout=5000)
    m, i = message.bounding_box(), item.bounding_box()
    assert m and i, "le message ou la collection n'est pas rendu"
    assert i["y"] <= m["y"] and m["y"] + m["height"] <= i["y"] + i["height"], (
        f"le message « {message.inner_text()} » s'affiche HORS de la fiche de la collection "
        f"(message {m}, fiche {i}) : loin du geste, là où la recette ne l'a pas vu")
    assert _se_voit(message), (
        f"le message n'est pas visible à l'écran ({m}) : hors de la fenêtre, rogné par la "
        "zone qui défile ou recouvert — il faut défiler pour le lire")
    return message.inner_text()


def _se_voit(locator):
    """Vrai si le point au début de la première ligne de l'élément désigne l'élément
    lui-même : ni hors de la fenêtre (`elementFromPoint` rend `null`), ni rogné par un
    conteneur qui défile, ni recouvert (il rend alors ce qui est par-dessus)."""
    return locator.evaluate("""el => {
      const r = el.getBoundingClientRect();
      const vu = document.elementFromPoint(r.left + Math.min(r.width, 24) / 2,
                                           r.top + Math.min(r.height, 16) / 2);
      return !!vu && (vu === el || el.contains(vu));
    }""")


def _enregistrer(page, cid):
    """Clique *Enregistrer*, et rend la fiche REDESSINÉE qui s'ensuit.

    Un enregistrement réussi recharge la liste et redessine la fiche, revenue en lecture :
    son message doit passer de l'une à l'autre. Le chercher sans attendre le second rendu le
    trouverait dans la version d'AVANT — et le test approuverait un report qui n'a peut-être
    pas lieu, selon qui, du navigateur ou du test, va le plus vite. On marque donc
    l'ancienne avant de cliquer, et on attend une fiche du même id qui ne porte pas la
    marque, onglets rendus."""
    sel = f'#col-fiche[data-id="{cid}"]'
    page.locator(sel).evaluate("d => { d.dataset.avant = '1'; }")
    page.locator(sel).locator("[data-enregistrer]").click()
    nouvelle = page.locator(f"{sel}:not([data-avant])")
    nouvelle.locator('[role="tab"]').first.wait_for(timeout=5000)
    return nouvelle


def test_nouvel_album_ne_masque_pas_la_creation_de_collection(page, decor):
    """Le piège qui aurait été muet. `openModal()` masquait `$(".contrib-add")` — la
    PREMIÈRE ligne de cette classe dans la page. Depuis COL-2, c'était le formulaire de
    création de collection, au-dessus de la table : caché à chaque « Nouvel album », et
    rien ne le rendait ensuite. Aucune erreur, aucun test d'API ; un bouton disparu."""
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.click("#col-creer")                     # le champ n'apparaît qu'au geste (UX-18)
    page.wait_for_selector("#col-add", state="visible", timeout=3000)
    page.click("#btn-new")
    page.wait_for_selector("#album-modal:not([hidden])", timeout=3000)
    # La ligne visée existe bien, et c'est ELLE qui se masque pour un album neuf.
    assert not page.locator("#m-contrib-ligne").is_visible()
    page.click("#m-cancel")
    assert page.locator("#col-add").is_visible(), "la création de collection a été masquée"
    assert page.locator("#col-nom").is_visible()


def test_le_formulaire_n_envoie_que_ce_qui_a_change(page, decor):
    """Le piège de l'embargo, qui ne se voit qu'en jouant le geste. Une date ILLISIBLE
    retient les scans (DROIT-1). Un champ `type=date` l'afficherait VIDE, et le premier
    enregistrement l'effacerait : une levée d'embargo déguisée en faute de frappe. On
    modifie la licence — et la date doit rester ce qu'elle était, affichée telle quelle."""
    with _client(decor["base"]) as c:
        cid = c.post("/api/collections", json={"nom": "Fonds mal daté"}).json()["id"]
        r = c.patch(f"/api/collections/{cid}",
                    json={"statut_diffusion": "embargo", "date_embargo": "31/12/2027"})
        assert r.status_code == 200, r.text

    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    item = _ouvrir(page, cid, "diffusion")
    # En lecture d'abord : la date illisible s'y lit telle quelle.
    expect(item.locator("#panneau-diffusion .bi-lecture")).to_contain_text("31/12/2027")
    item.locator('[data-modifier="diffusion"]').click()
    champ = item.locator('[data-champ="date_embargo"]')
    champ.wait_for(timeout=3000)
    assert champ.input_value() == "31/12/2027", "la date illisible n'est pas réaffichée"
    item.locator('[data-champ="licence_defaut"]').fill("CC-BY-4.0")
    _message_du_geste(page, _enregistrer(page, cid), "enregistrée")

    with _client(decor["base"]) as c:
        col = next(x for x in c.get("/api/collections").json() if x["id"] == cid)
    assert col["licence_defaut"] == "CC-BY-4.0"
    assert col["date_embargo"] == "31/12/2027", "l'embargo illisible a été réécrit"
    assert col["embargo"] == "illisible"


def test_passer_public_a_l_ecran_libere_le_manifeste(page, decor):
    """La recette même de COL-2, et le geste qui a manqué le 2026-09-10 en pleine QA
    d'EXP-1 — il avait fallu `tools/gerer_collections.py`, donc un terminal. Un
    propriétaire pose le régime « public » depuis la Bibliothèque, et le manifeste IIIF de
    la collection cesse d'emporter son `AVERTISSEMENTS.txt`."""
    cid = _collection_du_decor(decor["base"], decor["album"])["id"]
    with _client(decor["base"]) as c:
        avant = c.get(f"/api/collections/{cid}/depot/iiif", params={"base_url": BASE_IMAGES})
    assert avant.status_code == 200, avant.text
    assert "AVERTISSEMENTS.txt" in zipfile.ZipFile(io.BytesIO(avant.content)).namelist(), (
        "le décor devait partir d'une collection NON publique")

    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    item = _modifier(page, cid, "diffusion")
    item.locator('[data-champ="statut_diffusion"]').select_option("public")
    _message_du_geste(page, _enregistrer(page, cid), "enregistrée")
    # Revenue en lecture, la fiche dit le régime enregistré, dans l'en-tête et dans l'onglet.
    expect(_fiche(page, cid).locator(".lf-sous .col-regime")).to_have_text("public")

    with _client(decor["base"]) as c:
        apres = c.get(f"/api/collections/{cid}/depot/iiif", params={"base_url": BASE_IMAGES})
    assert apres.status_code == 200, apres.text
    archive = zipfile.ZipFile(io.BytesIO(apres.content))
    assert "AVERTISSEMENTS.txt" not in archive.namelist(), archive.read("AVERTISSEMENTS.txt")


def test_supprimer_rend_le_409_et_son_compte_d_albums(page, decor):
    """Supprimer une collection est refusé si un album se retrouvait sans aucune — c'est
    l'invariant d'AUTH-2, un album a toujours une règle d'accès. Le serveur le dit dans un
    409 ; l'écran doit RENDRE ce refus, et non le reproduire ni le remplacer par un
    « échec » qui ferait croire à un bug. L'album du décor ne vit que dans la collection de
    repli : la supprimer l'isolerait.

    Le 409 COMPTE les albums isolés, il ne les NOMME pas — la fiche le supposait, et le
    premier jet de ce test ne vérifiait que la présence du mot « album », donc aurait passé
    sur l'affirmation fausse. On vérifie le compte, qui est ce que l'écran rend."""
    cid = _collection_du_decor(decor["base"], decor["album"])["id"]
    page.on("dialog", lambda d: d.accept())      # le confirm() de la suppression
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    item = _ouvrir(page, cid, "description")
    item.locator("[data-supprimer]").click()
    message = _message_du_geste(page, item, "n'appartiennent qu'à cette collection")
    assert "1 album(s) n'appartiennent qu'à cette collection" in message, message

    with _client(decor["base"]) as c:
        assert cid in {x["id"] for x in c.get("/api/collections").json()}, (
            "la collection a disparu malgré le refus")


def test_supprimer_laisse_sa_confirmation_a_la_place_de_la_fiche(page, decor):
    """Une suppression RÉUSSIE ne peut pas parler dans la collection : sa fiche disparaît, et
    sa ligne de message avec elle. Sa confirmation prend donc la PLACE de la fiche — en tête
    de celle du projet, qui la remplace —, là où l'œil est resté ; et la collection quitte
    la liste. Gardé depuis la passe de revue du 2026-09-16, qui avait vu la confirmation
    affirmée et jamais vérifiée ; la place a suivi la refonte (UX-18)."""
    with _client(decor["base"]) as c:
        cid = c.post("/api/collections", json={"nom": "Espace B"}).json()["id"]
    page.on("dialog", lambda d: d.accept())      # le confirm() de la suppression
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    item = _ouvrir(page, cid, "description")
    item.locator("[data-supprimer]").click()
    item.wait_for(state="detached", timeout=5000)
    trace = page.locator("#biblio-fiche [role=status]", has_text="« Espace B » supprimée.")
    trace.wait_for(timeout=5000)
    assert _se_voit(trace), "la confirmation de suppression n'est pas visible à l'écran"
    expect(page.locator("#bi-accueil-titre")).to_be_visible()
    expect(page.locator(f'#col-body .col-item[data-id="{cid}"]')).to_have_count(0)
    with _client(decor["base"]) as c:
        assert cid not in {x["id"] for x in c.get("/api/collections").json()}


def test_prendre_le_nom_du_repli_est_refuse_la_ou_l_on_a_agi(page, decor):
    """Le nom de la collection de repli est RÉSERVÉ : se l'attribuer capturerait les albums
    créés sans collection explicite. La garde interdit de le PRENDRE, et le serveur répond
    en 422 ; l'écran rend ce refus lisible plutôt que de reproduire la règle — une seconde
    copie finirait par dire autre chose que la première.

    Et il le rend LÀ OÙ L'ON A AGI. C'est ce refus-là que la passe de recette du 2026-09-16
    a manqué : lisible, mais sous toute la liste. La boîte du message doit tenir dans celle
    de la fiche de la collection, ce qu'un message posé sous la liste ne fait pas."""
    repli = _collection_du_decor(decor["base"], decor["album"])["nom"]
    with _client(decor["base"]) as c:
        cid = c.post("/api/collections", json={"nom": "Un espace"}).json()["id"]
        c.post("/api/collections", json={"nom": "Un autre espace"})

    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    item = _modifier(page, cid, "description")
    item.locator('[data-champ="nom"]').fill(repli)
    item.locator("[data-enregistrer]").click()
    message = _message_du_geste(page, item, "réservé")
    assert "réserv" in message.lower(), message
    # Une ATTENTE, pas un compte immédiat : la fiche se redessine après le geste.
    expect(page.locator("#biblio .col-msg.erreur"),
           "le refus se lit, mais pas comme un refus : la classe `erreur` manque"
           ).to_have_count(1)

    with _client(decor["base"]) as c:
        nom = next(x["nom"] for x in c.get("/api/collections").json() if x["id"] == cid)
    assert nom == "Un espace", "le nom réservé a été pris malgré le refus"


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_creer_ne_demande_aucun_droit_mais_decrire_si(page, decor):
    """Trois questions dans un même bloc, et c'est la garde qu'on risquait de confondre.

    Carole n'a accès à RIEN. Elle ne voit donc pas la collection du décor — mais elle voit
    le bouton de création, et créer lui réussit : une identité suffit, refuser la création
    à qui n'a encore rien rendrait l'outil inutilisable au premier jour. Elle devient
    propriétaire de ce qu'elle a créé : sa fiche s'ouvre, dit « décider qui entre » parmi
    ses droits, et lui offre de MODIFIER la description, pas seulement de la lire.

    Une garde unique posée sur le bloc lui aurait masqué le bouton : l'erreur qui échoue
    en se FERMANT, sans casser aucun test d'API — mot pour mot AUTH-4."""
    page.set_extra_http_headers({"Remote-User": "carole", "Remote-Groups": "etudiants"})
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_selector("#col-body .col-note", timeout=3000)   # la liste est rendue… vide
    expect(page.locator("#col-body .col-item"),
           "une collection qu'elle ne lit pas ne doit pas lui apparaître").to_have_count(0)
    assert page.locator("#col-creer").is_visible(), "le bouton de création lui est masqué"

    _creer(page, "Espace de Carole")
    fiche = page.locator("#col-fiche", has_text="Espace de Carole")
    fiche.wait_for(timeout=5000)
    expect(fiche.locator('.droits [data-acte="administrer"]')).to_have_class("oui")
    fiche.locator('[role="tab"][data-onglet="description"]').click()
    expect(fiche.locator('[data-modifier="description"]')).to_be_visible()
    expect(page.locator("#col-body .col-item")).to_have_count(1)


def test_un_refus_d_acces_survit_au_rechargement_de_la_collection(page, decor):
    """Bibliothèque → « Qui entre » : un refus s'affiche là où l'on a agi, et y RESTE.

    Décocher un cran RECHARGE les accès dans les deux cas, refus compris : l'écran doit
    montrer le niveau que le serveur a gardé, pas la case qu'on a décochée. Le tableau qui
    vient d'afficher le refus est donc redessiné dans la foulée ; le message, qui ne vit pas
    dans le tableau, doit lui survivre. Le panneau vivait dans l'Administration jusqu'à
    l'étape 3 d'AUTH-12 ; le piège a déménagé avec lui.

    Le geste est le 409 du dernier propriétaire : décocher « décider qui entre » laisserait une
    collection que plus personne n'administre (AUTH-3)."""
    with _client(decor["base"]) as c:
        cid = c.post("/api/collections", json={"nom": "Un espace"}).json()["id"]
        r = c.put(f"/api/collections/{cid}/acces", json={
            "genre": "utilisateur", "principal": "pilote", "niveau": "proprietaire"})
        assert r.status_code == 200, r.text

    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    item = _ouvrir(page, cid, "qui")
    decider = item.locator('.qe-case[data-cran="proprietaire"][data-principal="pilote"]')
    decider.uncheck()
    # Attendre la version REDESSINÉE : la case y revient cochée, ce que le serveur a gardé.
    # Chercher le message plus tôt le trouverait avant le rechargement, et approuverait un
    # report qui n'a pas eu lieu.
    page.wait_for_function(
        """(cid) => {
          const s = document.querySelector(`#col-fiche[data-id="${cid}"] `
            + `.qe-case[data-cran="proprietaire"][data-principal="pilote"]`);
          return s && s.checked;
        }""", arg=cid, timeout=5000)
    message = _message_du_geste(page, item, "dernier propriétaire")
    assert "désignez-en un autre" in message, message

    with _client(decor["base"]) as c:
        acces = c.get(f"/api/collections/{cid}/acces").json()
    assert ("pilote", "proprietaire") in {(a["principal"], a["niveau"]) for a in acces}


def test_faire_entrer_demande_de_dire_compte_ou_groupe(page, decor):
    """AUCUN défaut pour un nom tapé — tranché le 2026-09-16, gardé par l'étape 3 d'AUTH-12.

    « Utilisateur » était présélectionné, et la passe de recette a accordé `annotateurs` et
    `etudiants` comme des logins : deux fois sur deux. Un groupe accordé comme compte n'ouvre
    rien à personne. « + Faire entrer » refuse donc tant que « Compte ou groupe ? » n'est pas
    choisi, et le dit dans la collection. Et rien n'est présélectionné dans la liste non plus :
    « + Faire entrer » sans choix accorderait sinon le premier groupe par inertie."""
    with _client(decor["base"]) as c:
        cid = c.post("/api/collections", json={"nom": "Un espace"}).json()["id"]

    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    item = _ouvrir(page, cid, "qui")
    # Ce qui prouve la garde est qu'AUCUNE requête ne part, pas qu'aucun accès n'est créé : le
    # serveur refuse lui-même un genre vide (422), donc « rien de créé » serait vrai sans elle.
    envois = []
    page.on("request", lambda r: envois.append(r.url)
            if r.method == "PUT" and "/acces" in r.url else None)
    choix = item.locator(".qe-choix")
    choix.wait_for(timeout=5000)
    assert choix.input_value() == "", "un choix est présélectionné : l'inertie accorderait"
    item.locator(".qe-faire-entrer").click()
    _message_du_geste(page, item, "Choisissez un groupe")

    choix.select_option("autre")
    item.locator(".qe-nom").fill("annotateurs")
    assert item.locator(".qe-genre").input_value() == "", (
        "un genre est présélectionné : l'erreur de la recette redevient possible par inertie")
    item.locator(".qe-faire-entrer").click()
    message = _message_du_geste(page, item, "compte ou un groupe")
    assert "annotateurs" in message, message
    assert envois == [], f"la demande est partie au serveur sans genre choisi : {envois}"

    item.locator(".qe-genre").select_option("groupe")
    item.locator(".qe-faire-entrer").click()
    message = _message_du_geste(page, item, "entre dans")
    assert "Cochez les autres actes" in message, message
    with _client(decor["base"]) as c:
        acces = c.get(f"/api/collections/{cid}/acces").json()
    assert [(a["principal"], a["genre"], a["niveau"]) for a in acces] == [
        ("annotateurs", "groupe", "lecture")], acces


def _message_sous_le_champ(page, motif):
    """Le message de création, trouvé par son texte puis situé : sous le geste de création
    — le bouton « + Créer une collection », et son champ quand il est ouvert — et au-dessus
    de la liste des collections, et visible. Le champ se referme une fois la collection
    créée (UX-18) : c'est le bouton qui reste le lieu du geste."""
    message = page.locator("#biblio [role=status]", has_text=motif)
    message.wait_for(timeout=5000)
    zone = page.locator("#col-creer-zone")
    champ = (zone if zone.is_visible() else page.locator("#col-creer")).bounding_box()
    liste = page.locator("#col-body").bounding_box()
    m = message.bounding_box()
    assert champ["y"] + champ["height"] <= m["y"] and m["y"] + m["height"] <= liste["y"], (
        f"le message « {message.inner_text()} » n'est pas entre le geste de création "
        f"({champ}) et la liste ({liste}) : {m}")
    assert _se_voit(message), f"le message de création n'est pas visible ({m})"
    return message.inner_text()


def test_la_creation_parle_sous_son_champ(page, decor):
    """Le message de création — refus comme succès — s'affiche sous le geste, en haut de la
    liste, et non sous elle. Situé à l'écran et plus seulement cherché à son adresse :
    `#col-creer-msg` déplacé sous la liste garderait `test_a11y_bibliotheque_collections`
    vert, qui ne lit que l'adresse — relevé par la passe de revue du 2026-09-16."""
    with _client(decor["base"]) as c:
        for n in ("Un espace", "Un autre espace"):
            c.post("/api/collections", json={"nom": n})
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.locator("#col-body .col-item").first.wait_for(timeout=3000)
    _creer(page)                                 # sans nom
    assert "Donnez un nom" in _message_sous_le_champ(page, "Donnez un nom")
    _creer(page, "Espace neuf")
    assert "Espace neuf" in _message_sous_le_champ(page, "créée")


def test_un_geste_efface_le_message_d_une_autre_collection(page, decor):
    """UN message à la fois, comme au temps de la ligne unique. Les lignes vivent chacune
    près de leur geste : sans cette règle, un refus restait affiché — et reposé à chaque
    rechargement — après un geste réussi ailleurs, à côté d'un formulaire qui ne contenait
    plus le nom refusé ; et « créée » restait en tête de la liste après un geste dans une
    autre collection. Trouvé par la passe de revue du 2026-09-16."""
    repli = _collection_du_decor(decor["base"], decor["album"])["nom"]
    with _client(decor["base"]) as c:
        a = c.post("/api/collections", json={"nom": "Espace A"}).json()["id"]
        b = c.post("/api/collections", json={"nom": "Espace B"}).json()["id"]
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    _creer(page, "Espace C")
    _message_sous_le_champ(page, "créée")

    item_a = _modifier(page, a, "description")
    item_a.locator('[data-champ="nom"]').fill(repli)
    item_a.locator("[data-enregistrer]").click()
    _message_du_geste(page, item_a, "réservé")
    expect(page.locator("#biblio .col-msg", has_text="créée"),
           "« créée » reste affiché après un geste dans une autre collection").to_have_count(0)

    item_b = _modifier(page, b, "diffusion")
    item_b.locator('[data-champ="licence_defaut"]').fill("CC-BY-4.0")
    _message_du_geste(page, _enregistrer(page, b), "enregistrée")
    expect(page.locator("#biblio .col-msg", has_text="réservé"),
           "le refus d'« Espace A » est reposé après l'enregistrement d'« Espace B » : il "
           "parle d'un nom que le formulaire redessiné ne contient plus").to_have_count(0)


def test_une_relecture_ratee_ne_cache_pas_l_enregistrement(page, decor):
    """Enregistrer réussit, puis la relecture de la liste échoue : l'erreur remplace la
    liste, et la confirmation partait avec. On croyait raté un enregistrement qui avait eu
    lieu. La ligne unique d'avant COL-2, hors de la liste, y survivait ; trouvé par la passe
    de revue du 2026-09-16. Depuis UX-18, la fiche reste telle qu'elle est, message compris."""
    with _client(decor["base"]) as c:
        cid = c.post("/api/collections", json={"nom": "Un espace"}).json()["id"]
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    item = _modifier(page, cid, "diffusion")
    item.locator('[data-champ="licence_defaut"]').fill("CC-BY-4.0")

    def panne(route):
        if route.request.method == "GET":
            route.fulfill(status=500, content_type="application/json",
                          body='{"detail": "Relecture impossible (panne simulée)."}')
        else:
            route.continue_()
    page.route("**/api/collections", panne)
    item.locator("[data-enregistrer]").click()
    page.get_by_text("Relecture impossible").wait_for(timeout=5000)
    confirmation = page.locator("#biblio .col-msg", has_text="enregistrée")
    confirmation.wait_for(timeout=3000)
    assert _se_voit(confirmation), "la confirmation survit, mais ne se voit pas"
    with _client(decor["base"]) as c:
        col = next(x for x in c.get("/api/collections").json() if x["id"] == cid)
    assert col["licence_defaut"] == "CC-BY-4.0"


def test_un_geste_d_acces_efface_le_refus_d_une_autre_collection(page, decor):
    """Bibliothèque : la règle d'un message à la fois vaut pour « Qui entre ». Un refus dans
    A, puis un accès accordé dans B : le refus d'A, qui nommait « annotateurs », ne doit plus
    s'afficher sous un geste qui a réussi ailleurs."""
    with _client(decor["base"]) as c:
        a = c.post("/api/collections", json={"nom": "Espace A"}).json()["id"]
        b = c.post("/api/collections", json={"nom": "Espace B"}).json()["id"]
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    item_a = _ouvrir(page, a, "qui")
    item_a.locator(".qe-choix").select_option("autre")
    item_a.locator(".qe-nom").fill("annotateurs")
    item_a.locator(".qe-faire-entrer").click()
    _message_du_geste(page, item_a, "compte ou un groupe")

    item_b = _ouvrir(page, b, "qui")
    item_b.locator(".qe-choix").select_option("groupe:annotateurs")
    item_b.locator(".qe-faire-entrer").click()
    item_b.locator(".qe-qui, .qe-table th[scope=row]", has_text="annotateurs").first.wait_for(
        timeout=5000)
    item_b.locator(".qe-msg", has_text="entre dans").wait_for(timeout=5000)
    expect(page.locator("#biblio .col-msg", has_text="compte ou un groupe"),
           "le refus d'« Espace A » est resté affiché après un accès accordé dans « Espace B »"
           ).to_have_count(0)


def test_un_refus_d_acces_survit_a_une_relecture_ratee(page, decor):
    """Bibliothèque : un refus de cran recharge les accès, et ce rechargement peut échouer.
    L'erreur remplace alors le tableau ; le 409 ne doit pas partir avec, sans quoi on ne
    saurait plus que le niveau a été refusé. Relevé par la passe de revue du 2026-09-16 sur
    l'Administration, et gardé quand le panneau a déménagé (AUTH-12, étape 3). La relecture
    de la LISTE des collections n'est plus en jeu : un geste d'accès ne la relit pas."""
    with _client(decor["base"]) as c:
        cid = c.post("/api/collections", json={"nom": "Un espace"}).json()["id"]
        r = c.put(f"/api/collections/{cid}/acces", json={
            "genre": "utilisateur", "principal": "pilote", "niveau": "proprietaire"})
        assert r.status_code == 200, r.text

    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    item = _ouvrir(page, cid, "qui")
    decider = item.locator('.qe-case[data-cran="proprietaire"][data-principal="pilote"]')
    decider.wait_for(timeout=5000)

    def panne(route):
        if route.request.method == "GET":
            route.fulfill(status=500, content_type="application/json",
                          body='{"detail": "Relecture impossible (panne simulée)."}')
        else:
            route.continue_()
    page.route("**/api/collections/*/acces", panne)   # armé APRÈS l'ouverture, qui doit réussir
    decider.uncheck()
    page.locator("#col-fiche", has_text="Relecture impossible").wait_for(timeout=5000)
    refus = page.locator("#col-fiche .col-msg", has_text="dernier propriétaire")
    refus.wait_for(timeout=3000)
    assert _se_voit(refus), "le refus survit à la relecture ratée, mais ne se voit pas"


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_la_modale_d_album_ne_propose_que_ou_l_on_ecrit(page, live_server):
    """AUTH-12 — la modale proposait toutes les collections LUES, et ranger un album dans
    une collection qu'on ne fait que lire répondait « Collection N introuvable ». Zoé lit
    « Lue » et écrit dans « Écrite » et « Autre écrite » : à la création, « Lue » n'est
    pas proposée ; à l'édition d'un album d'« Écrite », non plus. Et Yann, qui ne fait que
    lire, apprend AVANT de remplir le formulaire qu'il ne pourra pas créer d'album."""
    admin = {"Remote-User": "decor", "Remote-Groups": "bd-admins",
             **{k: v for k, v in ECRITURE.items() if k not in ("Remote-User", "Remote-Groups")}}
    with httpx.Client(base_url=live_server, trust_env=False, timeout=60, headers=admin) as c:
        ids = {n: c.post("/api/collections", json={"nom": n}).json()["id"]
               for n in ("Lue", "Écrite", "Autre écrite")}
        for n, niveau in (("Lue", "lecture"), ("Écrite", "ecriture"), ("Autre écrite", "ecriture")):
            r = c.put(f"/api/collections/{ids[n]}/acces",
                      json={"genre": "utilisateur", "principal": "zoe", "niveau": niveau})
            assert r.status_code == 200, r.text
        c.put(f"/api/collections/{ids['Lue']}/acces",
              json={"genre": "utilisateur", "principal": "yann", "niveau": "lecture"})
        album = c.post("/api/albums", json={"titre": "Rangé dans Écrite",
                                            "collection_id": ids["Écrite"]}).json()["id"]

    page.set_extra_http_headers({"Remote-User": "zoe"})
    page.goto(live_server + "/corpus", wait_until="networkidle")
    page.click("#btn-new")
    page.locator("#m-collection-wrap").wait_for(state="visible", timeout=5000)
    proposees = page.locator("#m-collection option").all_inner_texts()
    assert "Lue" not in proposees and {"Écrite", "Autre écrite"} <= set(proposees), proposees
    page.click("#m-cancel")

    # « Sur les collections », dans la fiche de l'album (COL-3, tranche 3a) : là aussi, une
    # case ne s'offre que là où l'on écrit ; « Lue » se lit, éteinte.
    page.locator(".album-row", has_text="Rangé dans Écrite").click()
    expect(page.locator(OFFERTES)).to_have_text(["Autre écrite"], timeout=5000)
    expect(page.locator(f'#album-range-cases input[data-ranger="{ids['Lue']}"]')).to_be_disabled()

    page.set_extra_http_headers({"Remote-User": "yann"})
    page.goto(live_server + "/corpus", wait_until="networkidle")
    page.click("#btn-new")
    note = page.locator("#m-collection-note")
    note.wait_for(state="visible", timeout=5000)
    assert "n'écrivez dans aucune collection" in note.inner_text(), note.inner_text()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_la_creation_ne_dit_proprietaire_qu_a_qui_l_est(page, live_server):
    """AUTH-12, option B tranchée le 2026-09-16 — un administrateur crée une collection SANS
    propriétaire (AUTH-3), et la Bibliothèque lui disait « vous en êtes propriétaire ».
    Le message lit désormais la réponse du serveur : à l'administrateur, qu'il administre
    sans posséder et où désigner un propriétaire ; à une personne, qu'elle possède."""
    page.set_extra_http_headers({"Remote-User": "chef", "Remote-Groups": "bd-admins"})
    page.goto(live_server + "/corpus", wait_until="networkidle")
    _creer(page, "Espace de l'administrateur")
    message = _message_sous_le_champ(page, "créée")
    assert "sans en être propriétaire" in message, message
    assert "vous en êtes propriétaire" not in message, message

    page.set_extra_http_headers({"Remote-User": "ines"})
    page.goto(live_server + "/corpus", wait_until="networkidle")
    _creer(page, "Espace d'Inès")
    message = _message_sous_le_champ(page, "créée")
    assert "vous en êtes propriétaire" in message, message


@pytest.mark.parametrize("live_server", [False, True], indirect=True, ids=["mono", "proxy"])
def test_une_liste_vide_ne_promet_la_propriete_qu_a_qui_la_recevra(page, live_server, request):
    """AUTH-12, option B — la liste vide disait « vous en serez propriétaire » à tout le
    monde. C'est faux pour qui écrit PARTOUT : en mono-poste et pour un administrateur, créer
    une collection ne pose aucun propriétaire. Le serveur de test est neuf, donc SANS aucune
    collection : en mono-poste, aucune promesse ; derrière le proxy, une personne sans accès
    la reçoit, et c'est alors vrai. L'Administration avait la même liste ; elle l'a perdue
    avec le panneau des accès (AUTH-12, étape 3).

    Depuis la tranche 3 (D10 ; Hugo, 2026-10-17), le projet de repli naît avec sa base : un
    serveur neuf porte UNE collection, que le mono-poste lit. La liste n'y est plus vide, et
    la note n'a rien à promettre ; elle se joue toujours derrière le proxy.

    UX-18 — Nadia n'a aucune collection : c'est une portée VIDE, que le bandeau de
    `theme.js` dit déjà (« Aucune collection ne vous est ouverte »). La liste ne le double
    pas d'un second « rien » ; elle dit seulement ce qu'on peut faire, et la promesse."""
    derriere_proxy = request.node.callspec.params["live_server"]
    if not derriere_proxy:
        page.goto(live_server + "/corpus", wait_until="networkidle")
        page.locator("#col-body .col-item").first.wait_for(timeout=5000)
        expect(page.locator("#col-body .col-note")).to_have_count(0)
        return
    page.set_extra_http_headers({"Remote-User": "nadia"})
    page.goto(live_server + "/corpus", wait_until="networkidle")
    note = page.locator("#col-body .col-note")
    note.wait_for(timeout=5000)
    texte = note.inner_text()
    assert "vous en serez propriétaire" in texte, texte
    assert "Aucune collection" not in texte, (
        f"la liste double le bandeau de portée vide : {texte!r}")
    expect(page.locator(".portee-vide")).to_be_visible()


# --------------------------------------------------------------------------- #
# « Supprimer… » a deux réponses (COL-3, tranche 2)
# --------------------------------------------------------------------------- #
def _decor_suppression(live_server):
    """Trois collections, quatre albums, cinq comptes. Tout est importé par l'administrateur
    `decor` — donc par personne d'autre —, sauf « Erreur », que `sam` importe lui-même dans
    « Incubateur » : c'est le seul album qu'un compte ordinaire supprime sans demander.

    - lia LIT « Incubateur » ;
    - noa ÉCRIT « Incubateur » et LIT « Archives » ;
    - paz ÉCRIT « Incubateur » et « Archives » ;
    - sam ÉCRIT « Incubateur », et ne lit rien d'autre.
    """
    admin = {"Remote-User": "decor", "Remote-Groups": "bd-admins",
             **{k: v for k, v in ECRITURE.items() if k not in ("Remote-User", "Remote-Groups")}}
    with httpx.Client(base_url=live_server, trust_env=False, timeout=60, headers=admin) as c:
        ids = {n: c.post("/api/collections", json={"nom": n}).json()["id"]
               for n in ("Principale", "Incubateur", "Archives")}
        albums = {}
        for titre, rangs in (("Partagé", ("Principale", "Incubateur")),
                             ("Triple", ("Principale", "Incubateur", "Archives")),
                             ("Seul", ("Incubateur",))):
            albums[titre] = c.post("/api/albums", json={
                "titre": titre, "collection_id": ids[rangs[0]]}).json()["id"]
            r = c.post(f"/api/albums/{albums[titre]}/import",
                       files={"file": ("p.png", make_png(), "image/png")})
            assert r.status_code == 201, r.text
            for autre in rangs[1:]:
                r = c.put(f"/api/albums/{albums[titre]}/collections/{ids[autre]}")
                assert r.status_code == 201, r.text
        for ou, qui, niveau in (("Incubateur", "sam", "ecriture"), ("Incubateur", "lia", "lecture"),
                                ("Incubateur", "noa", "ecriture"), ("Archives", "noa", "lecture"),
                                ("Incubateur", "paz", "ecriture"), ("Archives", "paz", "ecriture")):
            r = c.put(f"/api/collections/{ids[ou]}/acces",
                      json={"genre": "utilisateur", "principal": qui, "niveau": niveau})
            assert r.status_code == 200, r.text
    sam = {"Remote-User": "sam", main_en_tete(): "1"}
    with httpx.Client(base_url=live_server, trust_env=False, timeout=60, headers=sam) as c:
        r = c.post("/api/albums", json={"titre": "Erreur", "collection_id": ids["Incubateur"]})
        assert r.status_code == 201, r.text
        albums["Erreur"] = r.json()["id"]
        r = c.post(f"/api/albums/{albums['Erreur']}/import",
                   files={"file": ("p.png", make_png(), "image/png")})
        assert r.status_code == 201, r.text
    return admin, ids, albums


def main_en_tete():
    """L'en-tête anti-CSRF, lu dans `ECRITURE` plutôt que recopié."""
    return next(k for k in ECRITURE if k not in ("Remote-User", "Remote-Groups"))


# « Sur les collections » (COL-3, tranche 3a) : les cases cochées, et celles qui s'offrent.
COCHEES = "#album-range-cases input[data-ranger]:checked"
OFFERTES = "#album-range-cases label:has(input[data-ranger]:not(:checked):enabled) .col-nom"


def _ligne(page, titre):
    return page.locator(".album-row", has=page.locator(".c-titre", has_text=titre))


def _ouvrir_detail(page, titre):
    """La fiche de CET album, et non celle du précédent restée affichée. L'attente est une
    FONCTION : en expression, elle passe par `eval` dès qu'elle doit patienter, et la CSP
    (`script-src 'self'`) la refuse — vert seul, rouge dans la passe entière."""
    _ligne(page, titre).locator(".c-titre").click()
    page.wait_for_function(
        "t => { const d = document.querySelector('#album-detail');"
        "       return !!d && d.querySelector('#album-titre').textContent.includes(t)"
        "              && !!d.querySelector('.pl-thumb'); }",
        arg=titre, timeout=5000)


def _gestes_de_l_album(page, titre):
    """« Supprimer… » et ✎, dans la fiche de CET album (UX-18 : la liste de gauche ne porte
    que des boutons qui ouvrent ; les gestes vivent dans la fiche et dans l'onglet Albums
    d'une collection)."""
    _ouvrir_detail(page, titre)
    return page.locator('#album-detail [data-act="supprimer"], #album-detail #detail-edit')


def _ouvrir_suppression(page, titre):
    """« Supprimer… » dans la fiche de CET album, puis le panneau, ses collections lues."""
    _ouvrir_detail(page, titre)
    page.locator('#album-detail [data-act="supprimer"]').click()
    expect(page.locator("#suppr-modal")).to_be_visible(timeout=5000)
    expect(page.locator("#sp-titre")).to_have_text(f"Supprimer « {titre} »")
    page.wait_for_function(
        "() => !document.querySelector('#sp-retrait').textContent.includes('Lecture')",
        timeout=5000)


# Le contraste du CONTOUR d'un élément sur le premier fond opaque qui le porte (WCAG 1.4.11).
_CONTRASTE_CONTOUR = r"""(el) => {
  const rgb = (c) => (c.match(/[\d.]+/g) || []).map(Number);
  const lum = ([r, g, b]) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  let fond = el.parentElement;
  while (fond && (rgb(getComputedStyle(fond).backgroundColor)[3] === 0
                  || getComputedStyle(fond).backgroundColor === "transparent")) {
    fond = fond.parentElement;
  }
  const a = lum(rgb(getComputedStyle(el).borderTopColor));
  const b = lum(rgb(getComputedStyle(fond || document.body).backgroundColor));
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}"""


def _comme(page, live_server, login):
    page.set_extra_http_headers({"Remote-User": login})
    page.goto(live_server + "/corpus", wait_until="networkidle")


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_supprimer_n_est_offert_que_la_ou_il_aboutira(page, live_server):
    """COL-3, tranche 2 — « Supprimer… » n'est offert qu'à qui ÉCRIT dans l'album, et ce que
    le panneau annonce dépend de ce qu'on y perd. Trois identités, parce que « supprimer de
    la collection » a plusieurs visages.

    - **Lia ne fait que LIRE** « Incubateur » : ni « Supprimer… », ni corbeille de planche,
      ni corbeille éteinte, nulle part. C'est le mutant 16 du cadrage : un bouton offert à
      qui ne fait que lire mènerait à deux réponses dont aucune n'aboutit.
    - **Paz écrit dans « Incubateur » ET dans « Archives »** : décocher « Archives » dans
      « Sur les collections » ne lui retire ni la vue ni l'écriture — mais elle ne le défait
      plus elle-même (COL-3, tranche 3a, D4 stricte) : ranger est REJOINDRE, elle ne possède
      pas les collections de l'album. Le geste est donc un aller simple, qui se CONFIRME et
      le dit (relecture croisée de t3a-c4) ; recocher dit que la demande est partie, et un
      administrateur le range de nouveau.
    - **Noa écrit dans « Incubateur » et lit « Archives »**, où « Triple » est aussi rangé :
      le panneau ne propose QUE la collection où elle écrit, nomme celle où le travail
      reste, et dit qu'elle continuera de lire sans plus écrire. Le ✕ de « Rangé dans » dit
      la même chose, et se confirme ; il n'est offert que sur la collection où elle écrit
      (UX-18 a corrigé le ✕ offert sur une collection qu'on ne fait que lire). Et nulle part
      l'écran ne NOMME une collection qu'elle ne lit pas."""
    admin, ids, albums = _decor_suppression(live_server)
    demandes = []

    def repondre(accepter):
        def _(dialogue):
            demandes.append(dialogue.message)
            dialogue.accept() if accepter else dialogue.dismiss()
        return _

    # ── qui ne fait que lire : aucun geste qui n'aboutirait ──────────────────────────────
    _comme(page, live_server, "lia")
    _ligne(page, "Seul").wait_for(timeout=5000)
    for titre in ("Partagé", "Triple", "Seul", "Erreur"):
        expect(_ligne(page, titre)).to_be_visible()
        # Des ATTENTES, pas des comptes immédiats : la fiche se redessine à l'ouverture, et
        # « Sur les collections » se remplit après elle (un compte tombé une fois, dans une
        # passe chargée, sur des cases de l'entre-deux).
        expect(_gestes_de_l_album(page, titre), titre).to_have_count(0)
        # « Sur les collections » se lit, et aucune case ne s'offre : elle n'écrit nulle part.
        expect(page.locator("#album-range-cases input[data-ranger]").first).to_be_visible()
        expect(page.locator("#album-range-cases input[data-ranger]:enabled"), titre
               ).to_have_count(0)
    expect(page.locator("#album-detail [data-delp], #album-detail [data-delp-refus]")
           ).to_have_count(0)
    expect(page.locator("#album-detail button[data-val]"),
           "un bouton de validation offert à qui ne fait que lire").to_have_count(0)

    # ── qui écrit dans DEUX de ses collections sans les tenir : un aller simple ──────────
    _comme(page, live_server, "paz")
    _ligne(page, "Triple").wait_for(timeout=5000)
    expect(_gestes_de_l_album(page, "Triple").first).to_be_visible()
    # Elle écrit encore dans l'album par « Incubateur », et le voit : seul le retour lui
    # échappe, et la confirmation le dit.
    page.once("dialog", repondre(True))
    page.locator(f'#album-range-cases input[data-ranger="{ids["Archives"]}"]').click()
    expect(page.locator(COCHEES)).to_have_count(1, timeout=5000)
    assert len(demandes) == 1, demandes
    assert "que sur demande" in demandes[0], demandes
    assert "n'y écrirez plus" not in demandes[0] and "ne le verrez plus" not in demandes[0]
    demandes.clear()
    page.locator(f'#album-range-cases input[data-ranger="{ids["Archives"]}"]').click()
    expect(page.locator("#album-range-msg")).to_contain_text("La demande est partie",
                                                             timeout=5000)
    # La fiche se relit après le geste : on attend les cases redessinées, pas un instant de
    # l'entre-deux où elles sont encore à lire.
    expect(page.locator(COCHEES)).to_have_count(1)
    expect(page.locator(f'#album-range-cases input[data-ranger="{ids["Archives"]}"]')
           ).to_be_disabled()
    assert demandes == []
    with httpx.Client(base_url=live_server, trust_env=False, timeout=60, headers=admin) as c:
        r = c.put(f"/api/albums/{albums['Triple']}/collections/{ids['Archives']}")
        assert r.status_code == 201, r.text

    # ── qui écrit d'un côté et LIT de l'autre ────────────────────────────────────────────
    _comme(page, live_server, "noa")
    _ligne(page, "Triple").wait_for(timeout=5000)
    _ouvrir_suppression(page, "Triple")
    boutons = page.locator("#sp-retrait button[data-retirer]")
    expect(boutons).to_have_count(1)
    expect(boutons).to_have_text("Supprimer de « Incubateur »")
    texte = page.locator(f"#sp-r-{ids['Incubateur']}")
    expect(texte).to_be_visible()
    expect(texte).to_contain_text("Le travail reste dans « Archives », où rien ne change.")
    expect(texte).to_contain_text("Vous continuerez de le lire, mais vous n'y écrirez plus")
    # Importé par un autre : la seconde réponse est une DEMANDE, motif à l'appui.
    expect(page.locator("#sp-def")).to_have_text("Envoyer la demande")
    expect(page.locator("#sp-motif")).to_be_visible()
    assert "Principale" not in page.inner_text("#suppr-modal")
    page.click("#sp-annuler")
    expect(page.locator("#suppr-modal")).to_be_hidden()

    # Décocher dans « Sur les collections » dit la même chose, et se confirme. Refusé, rien
    # ne bouge, et la case se recoche.
    page.once("dialog", repondre(False))
    page.locator(f'#album-range-cases input[data-ranger="{ids["Incubateur"]}"]').click()
    page.wait_for_function("() => document.querySelectorAll("
                           "'#album-range-cases input[data-ranger]:checked').length === 2",
                           timeout=5000)
    assert len(demandes) == 1, demandes
    assert "continuerez de le lire" in demandes[0] and "n'y écrirez plus" in demandes[0], demandes
    assert "ne le verrez plus" not in demandes[0] and "Principale" not in demandes[0]
    # Sur la collection qu'elle ne fait que LIRE, la case est éteinte : décocher n'aboutirait
    # pas (le serveur répondait « introuvable »). La collection se nomme toujours.
    archives = page.locator(f'#album-range-cases input[data-ranger="{ids["Archives"]}"]')
    expect(archives).to_be_checked()
    expect(archives).to_be_disabled()
    page.once("dialog", repondre(True))
    page.locator(f'#album-range-cases input[data-ranger="{ids["Incubateur"]}"]').click()
    page.wait_for_function("() => document.querySelectorAll("
                           "'#album-range-cases input[data-ranger]:checked').length === 1",
                           timeout=5000)
    assert len(demandes) == 2
    # Redevenue lectrice de cet album : plus rien ne lui est offert dessus.
    expect(page.locator('#album-detail [data-act="supprimer"]')).to_have_count(0)
    expect(page.locator("#album-range-cases input[data-ranger]:enabled")).to_have_count(0)

    with httpx.Client(base_url=live_server, trust_env=False, timeout=60, headers=admin) as c:
        rangs = [x["nom"] for x in c.get(f"/api/albums/{albums['Triple']}/collections").json()]
        assert rangs == ["Archives", "Principale"], rangs


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_supprimer_a_deux_reponses_et_chacune_dit_ce_qu_elle_fait(page, live_server):
    """COL-3, tranche 2 — sous Sam, qui n'écrit que dans « Incubateur ».

    - « Erreur », qu'il a importé et où personne d'autre n'a travaillé : « Supprimer
      définitivement » efface tout de suite, et la corbeille de sa planche est active.
    - « Seul », importé par un autre et rangé là seulement : supprimer de la collection
      l'enverrait AU FONDS — le panneau le dit ; supprimer définitivement se DEMANDE. Une
      demande sans motif ne part pas ; avec, la requête PORTE le motif (mutant 17), la
      pastille paraît sur la ligne, et le panneau ne propose plus d'envoyer la même. Sa
      planche garde une corbeille ÉTEINTE, qui dit à qui s'adresser (décision B4).
    - « Partagé », rangé aussi dans une collection qu'il ne lit pas : le travail y reste, et
      l'écran le dit sans la nommer. Supprimé de « Incubateur », l'album quitte son écran
      et reste entier chez les autres.
    Puis Lia, qui lit « Incubateur », voit la pastille de la demande de Sam."""
    admin, ids, albums = _decor_suppression(live_server)
    _comme(page, live_server, "sam")
    _ligne(page, "Erreur").wait_for(timeout=5000)

    # Les planches suivent la règle du document.
    _ouvrir_detail(page, "Erreur")
    expect(page.locator("#album-detail button[data-delp]")).to_have_count(1)
    _ouvrir_detail(page, "Seul")
    expect(page.locator("#album-detail button[data-delp]")).to_have_count(0)
    eteinte = page.locator("#album-detail button[data-delp-refus]")
    expect(eteinte).to_have_count(1)
    assert eteinte.get_attribute("aria-disabled") == "true"
    # Éteinte mais atteignable : au clavier, elle dit à qui s'adresser. (Playwright tient un
    # `aria-disabled` pour non cliquable ; le clavier, lui, l'atteint.)
    eteinte.focus()
    page.keyboard.press("Enter")
    # Le message se lit CONTRE elle, dans la ligne de sa planche — pas dans un toast, qui
    # tombait sur la colonne d'actions et couvrait le bouton touché.
    message = page.locator("#album-detail .pl-refus-msg")
    expect(message).to_be_visible()
    expect(message).to_contain_text("Adressez-vous à un administrateur")
    expect(page.locator(".toast", has_text="Adressez-vous")).to_have_count(0)
    b, m = eteinte.bounding_box(), message.bounding_box()
    assert 0 <= m["y"] - (b["y"] + b["height"]) <= 12, (b, m)
    assert m["x"] < b["x"] + b["width"] and m["x"] + m["width"] > b["x"], (b, m)
    # Éteinte, elle se distingue d'un bouton ABSENT : son contour tient 3:1 sur le fond où
    # elle repose, dans les deux thèmes.
    for theme in ("light", "dark"):
        page.evaluate("t => localStorage.setItem('bd-theme', t)", theme)
        page.reload(wait_until="networkidle")
        _ouvrir_detail(page, "Seul")
        rapport = page.locator("#album-detail button[data-delp-refus]").evaluate(_CONTRASTE_CONTOUR)
        assert rapport >= 3, f"contour de la corbeille éteinte, thème {theme} : {rapport:.2f}:1"

    # ── « Seul » : au fonds, ou par demande ──────────────────────────────────────────────
    _ouvrir_suppression(page, "Seul")
    texte = page.locator(f"#sp-r-{ids['Incubateur']}")
    expect(texte).to_contain_text("C'est sa dernière collection : la copie de travail est "
                                  "gardée au fonds")
    expect(texte).to_contain_text("Un administrateur peut la rendre.")
    expect(texte).to_contain_text("Vous ne le verrez plus")
    expect(page.locator("#sp-def-texte")).to_contain_text("ce n'est pas vous qui avez créé cette copie")
    envoyees = []
    page.on("request", lambda r: envoyees.append(r) if r.url.endswith("/api/demandes")
            and r.method == "POST" else None)
    # Sans motif, rien ne part.
    page.click("#sp-def")
    expect(page.locator("#sp-msg.erreur")).to_contain_text("Dites pourquoi")
    assert envoyees == []
    assert page.evaluate("() => document.activeElement.id") == "sp-motif"
    page.fill("#sp-motif", "Doublon de « Triple ».")
    # Sans la certification, rien ne part non plus (Hugo, 2026-10-15) — et la case se lit.
    expect(page.locator("#sp-certif-texte")).to_be_visible()
    expect(page.locator("#sp-certif-texte")).to_contain_text(
        "Pouvez-vous certifier que ces données ne sont pas importantes ?")
    expect(page.locator("#sp-certif-wrap label")).to_have_text(
        "Je certifie que ces données ne sont pas importantes.")
    page.click("#sp-def")
    expect(page.locator("#sp-msg.erreur")).to_have_text(
        "Cochez la certification : la demande ne part pas sans elle.")
    assert envoyees == []
    assert page.evaluate("() => document.activeElement.id") == "sp-certif"
    page.check("#sp-certif")
    page.click("#sp-def")
    expect(page.locator("#suppr-modal")).to_be_hidden(timeout=5000)
    expect(page.locator(".toast", has_text="Votre demande est partie")).to_be_visible()
    assert len(envoyees) == 1
    corps = envoyees[0].post_data_json
    assert corps == {"genre": "suppression_document", "album_id": albums["Seul"],
                     "motif": "Doublon de « Triple ».", "certifie": True}, corps
    pastille = _ligne(page, "Seul").locator(".sp-pastille")
    expect(pastille).to_be_visible()
    expect(pastille).to_have_text("suppression demandée par vous")
    # Rien n'est effacé, et la même demande ne se propose plus.
    _ouvrir_suppression(page, "Seul")
    expect(page.locator("#sp-def-texte")).to_contain_text("Sa suppression est déjà demandée par vous")
    expect(page.locator("#sp-def")).to_be_hidden()
    expect(page.locator("#sp-motif")).to_be_hidden()
    expect(page.locator("#sp-certif")).to_be_hidden()
    page.keyboard.press("Escape")
    expect(page.locator("#suppr-modal")).to_be_hidden()

    # ── « Partagé » : le travail reste là où il ne lit pas ───────────────────────────────
    _ouvrir_suppression(page, "Partagé")
    texte = page.locator(f"#sp-r-{ids['Incubateur']}")
    expect(texte).to_contain_text("Le travail reste dans une collection que vous ne lisez pas")
    expect(texte).not_to_contain_text("fonds")
    assert "Principale" not in page.inner_text("body")
    page.locator("#sp-retrait button[data-retirer]").click()
    expect(page.locator("#suppr-modal")).to_be_hidden(timeout=5000)
    expect(page.locator(".toast", has_text="« Partagé » n'est plus dans « Incubateur ». "
                                           "Le travail continue ailleurs.")).to_be_visible()
    _ligne(page, "Partagé").wait_for(state="detached", timeout=5000)

    # ── « Erreur » : il l'a importé, il l'efface ─────────────────────────────────────────
    _ouvrir_suppression(page, "Erreur")
    expect(page.locator("#sp-def-texte")).to_contain_text("vous l'avez créée")
    expect(page.locator("#sp-motif")).to_be_hidden()
    expect(page.locator("#sp-certif")).to_be_hidden()
    expect(page.locator("#sp-def")).to_have_text("Supprimer définitivement")
    page.click("#sp-def")
    expect(page.locator(".toast", has_text="« Erreur » est supprimé définitivement")).to_be_visible(
        timeout=5000)
    _ligne(page, "Erreur").wait_for(state="detached", timeout=5000)

    # ── Lia lit la pastille, sans le nom de qui a demandé (Hugo, 2026-10-15) ─────────────
    _comme(page, live_server, "lia")
    expect(_ligne(page, "Seul").locator(".sp-pastille")).to_be_visible()
    expect(_ligne(page, "Seul").locator(".sp-pastille")).to_have_text("suppression demandée")

    with httpx.Client(base_url=live_server, trust_env=False, timeout=60, headers=admin) as c:
        reste = {a["id"]: a for a in c.get("/api/albums").json()}
        assert albums["Erreur"] not in reste
        assert reste[albums["Partagé"]]["nb_planches"] == 1
        assert reste[albums["Seul"]]["nb_planches"] == 1          # demandé, pas effacé
        rangs = [x["nom"] for x in c.get(f"/api/albums/{albums['Partagé']}/collections").json()]
        assert rangs == ["Principale"], rangs
