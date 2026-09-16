"""COL-2 — les gestes d'une collection dans la Bibliothèque, joués dans un vrai navigateur.

Ce module ne parle pas d'accessibilité — `test_e2e_a11y.py` audite ces écrans. Il est À
PART pour une raison écrite dans `test_e2e_reflow.py` : un module e2e finit par acquérir
sa propre condition de saut (là-bas, la présence d'axe-core), et tout ce qu'on y a rangé
disparaît avec lui, sans que rien ne le dise. Des tests de COMPORTEMENT n'ont pas à
dépendre d'un outil d'audit.

Chaque test vise un défaut qui ne casse aucun test d'API : le serveur répond juste, et
c'est l'écran qui aurait menti, masqué, effacé ou avalé un refus — ou l'aurait affiché
LOIN du geste, là où personne ne le voit (cf. `_message_du_geste`).
"""
import io
import zipfile

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source. Les gestes d'une collection
# vivent dans la Bibliothèque depuis COL-2 ; l'Administration n'y entre que pour la PLACE
# d'un refus d'accès, le reste de ce panneau étant audité par `test_e2e_a11y`.
SURFACES_AUDITEES = ("/corpus", "/administration")
SURFACES_HORS_PERIMETRE = {
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


def _message_du_geste(page, item, motif):
    """Le message qui suit un geste, trouvé par son TEXTE puis SITUÉ à l'écran.

    Trouvé n'importe où dans la page, et non là où le code est censé l'écrire : un
    sélecteur `.col-item .col-msg` lirait encore une ADRESSE, et le défaut vu par la passe
    de recette du 2026-09-16 n'en était pas un. Le refus du nom réservé est arrivé rouge et
    lisible, sous TOUTE la liste — et n'a pas été vu. La suite ne pouvait pas le dire :
    elle lisait le texte et la classe de `#col-msg`, jamais sa place.

    Deux propriétés, qui sont l'attendu de la fiche : le message est DANS la collection
    dépliée (sa boîte est contenue dans celle du `<details>`), et il se voit SANS DÉFILER
    (dans la fenêtre, telle que le clic l'a laissée). `item` est un locator : après un
    enregistrement la collection est redessinée, et il se résout dans la nouvelle."""
    message = page.locator("[role=status]", has_text=motif)
    message.wait_for(timeout=5000)
    m, i = message.bounding_box(), item.bounding_box()
    assert m and i, "le message ou la collection n'est pas rendu"
    assert i["y"] <= m["y"] and m["y"] + m["height"] <= i["y"] + i["height"], (
        f"le message « {message.inner_text()} » s'affiche HORS de la collection dépliée "
        f"(message {m}, collection {i}) : loin du geste, là où la recette ne l'a pas vu")
    hauteur = page.viewport_size["height"]
    assert m["y"] >= 0 and m["y"] + m["height"] <= hauteur, (
        f"le message est hors de la fenêtre ({m}, hauteur {hauteur}) : il faut défiler "
        "pour le voir")
    return message.inner_text()


def _enregistrer(page, cid):
    """Clique *Enregistrer*, et rend la collection REDESSINÉE qui s'ensuit.

    Un enregistrement réussi recharge la liste : la collection est détruite, puis
    redessinée, et son message doit passer de l'une à l'autre. Le chercher sans attendre
    le second rendu le trouverait dans la version d'AVANT — et le test approuverait un
    report qui n'a peut-être pas lieu, selon qui, du navigateur ou du test, va le plus
    vite. On marque donc l'ancienne avant de cliquer, et on attend une collection du même
    id qui ne porte pas la marque, formulaire rendu."""
    sel = f'#col-body .col-item[data-id="{cid}"]'
    page.locator(sel).evaluate("d => { d.dataset.avant = '1'; }")
    page.locator(sel).locator("[data-enregistrer]").click()
    nouvelle = page.locator(f"{sel}:not([data-avant])")
    nouvelle.locator("[data-enregistrer]").wait_for(timeout=5000)
    return nouvelle


def test_nouvel_album_ne_masque_pas_la_creation_de_collection(page, decor):
    """Le piège qui aurait été muet. `openModal()` masquait `$(".contrib-add")` — la
    PREMIÈRE ligne de cette classe dans la page. Depuis COL-2, c'était le formulaire de
    création de collection, au-dessus de la table : caché à chaque « Nouvel album », et
    rien ne le rendait ensuite. Aucune erreur, aucun test d'API ; un bouton disparu."""
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_selector("#col-add", timeout=3000)
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
    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    item.locator("summary").click()
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
    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    item.locator("summary").click()
    item.locator('[data-champ="statut_diffusion"]').select_option("public")
    _message_du_geste(page, _enregistrer(page, cid), "enregistrée")

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
    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    item.locator("summary").click()
    item.locator("[data-supprimer]").click()
    message = _message_du_geste(page, item, "n'appartiennent qu'à cette collection")
    assert "1 album(s) n'appartiennent qu'à cette collection" in message, message

    with _client(decor["base"]) as c:
        assert cid in {x["id"] for x in c.get("/api/collections").json()}, (
            "la collection a disparu malgré le refus")


def test_prendre_le_nom_du_repli_est_refuse_la_ou_l_on_a_agi(page, decor):
    """Le nom de la collection de repli est RÉSERVÉ : se l'attribuer capturerait les albums
    créés sans collection explicite. La garde interdit de le PRENDRE, et le serveur répond
    en 422 ; l'écran rend ce refus lisible plutôt que de reproduire la règle — une seconde
    copie finirait par dire autre chose que la première.

    Et il le rend LÀ OÙ L'ON A AGI. C'est ce refus-là que la passe de recette du 2026-09-16
    a manqué : lisible, mais sous toute la liste. D'où le décor de la fiche — trois
    collections, et celle qu'on renomme en a une autre dessous. Sous une seule collection,
    « sous la liste » et « sous le bouton » se touchent presque, et rien ne distinguerait
    le défaut de sa réparation."""
    repli = _collection_du_decor(decor["base"], decor["album"])["nom"]
    with _client(decor["base"]) as c:
        crees = {c.post("/api/collections", json={"nom": n}).json()["id"]
                 for n in ("Un espace", "Un autre espace")}

    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    rendues = page.locator("#col-body .col-item")
    rendues.first.wait_for(timeout=3000)
    ordre = [int(rendues.nth(i).get_attribute("data-id")) for i in range(rendues.count())]
    assert len(ordre) == 3, ordre
    # La PREMIÈRE créée dans l'ordre d'affichage : quel que soit l'ordre que le serveur
    # donne à la liste, il en reste une dessous.
    cid = next(x for x in ordre if x in crees)
    assert ordre.index(cid) < 2, ordre

    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    item.locator("summary").click()
    item.locator('[data-champ="nom"]').fill(repli)
    item.locator("[data-enregistrer]").click()
    message = _message_du_geste(page, item, "réservé")
    assert "réserv" in message.lower(), message
    assert page.locator("#col-body .col-msg.erreur").count() == 1, (
        "le refus se lit, mais pas comme un refus : la classe `erreur` manque")

    with _client(decor["base"]) as c:
        nom = next(x["nom"] for x in c.get("/api/collections").json() if x["id"] == cid)
    assert nom == "Un espace", "le nom réservé a été pris malgré le refus"


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_creer_ne_demande_aucun_droit_mais_decrire_si(page, decor):
    """Trois questions dans un même bloc, et c'est la garde qu'on risquait de confondre.

    Carole n'a accès à RIEN. Elle ne voit donc pas la collection du décor — mais elle voit
    le bouton de création, et créer lui réussit : une identité suffit, refuser la création
    à qui n'a encore rien rendrait l'outil inutilisable au premier jour. Elle devient
    propriétaire de ce qu'elle a créé, et c'est son FORMULAIRE qui s'ouvre, pas un résumé.

    Une garde unique posée sur le bloc lui aurait masqué le bouton : l'erreur qui échoue
    en se FERMANT, sans casser aucun test d'API — mot pour mot AUTH-4."""
    page.set_extra_http_headers({"Remote-User": "carole", "Remote-Groups": "etudiants"})
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_selector("#col-body .col-note", timeout=3000)   # la liste est rendue… vide
    assert page.locator("#col-body .col-item").count() == 0, (
        "une collection qu'elle ne lit pas ne doit pas lui apparaître")
    assert page.locator("#col-add").is_visible(), "le bouton de création lui est masqué"

    page.fill("#col-nom", "Espace de Carole")
    page.click("#col-add")
    item = page.locator("#col-body .col-item", has_text="Espace de Carole")
    item.locator("[data-enregistrer]").wait_for(timeout=5000)
    assert page.locator("#col-body .col-item").count() == 1


def test_un_refus_d_acces_survit_au_rechargement_de_la_collection(page, decor):
    """Administration → Accès : le même défaut sur l'autre écran, avec un piège de plus.

    Changer un niveau RECHARGE la liste dans les deux cas, refus compris : l'écran doit
    montrer le niveau que le serveur a gardé, pas celui qu'on a choisi. La collection qui
    vient d'afficher le refus est donc détruite et redessinée dans la foulée. Un message
    écrit dans la collection sans être reporté partirait avec elle — le refus ne serait
    plus loin du geste, il ne serait plus nulle part.

    Le geste est le 409 du dernier propriétaire : le rétrograder laisserait une collection
    que plus personne n'administre (AUTH-3)."""
    with _client(decor["base"]) as c:
        cid = c.post("/api/collections", json={"nom": "Un espace"}).json()["id"]
        r = c.put(f"/api/collections/{cid}/acces", json={
            "genre": "utilisateur", "principal": "pilote", "niveau": "proprietaire"})
        assert r.status_code == 200, r.text

    page.goto(decor["base"] + "/administration", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    item.locator("summary").click()
    niveau = item.locator('select[data-principal="pilote"]')
    niveau.select_option("lecture")
    # Attendre la version REDESSINÉE avant de chercher le message : le sélecteur y revient
    # au niveau que le serveur a gardé. Chercher plus tôt trouverait le message dans la
    # collection d'avant, et approuverait un report qui n'a pas eu lieu.
    page.wait_for_function(
        """(cid) => {
          const s = document.querySelector(
            `#col-body .col-item[data-id="${cid}"] select[data-principal="pilote"]`);
          return s && s.value === "proprietaire";
        }""", arg=cid, timeout=5000)
    message = _message_du_geste(page, item, "dernier propriétaire")
    assert "désignez-en un autre" in message, message

    with _client(decor["base"]) as c:
        acces = c.get(f"/api/collections/{cid}/acces").json()
    assert ("pilote", "proprietaire") in {(a["principal"], a["niveau"]) for a in acces}
