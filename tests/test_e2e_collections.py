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
    dépliée (sa boîte est contenue dans celle du `<details>`), et il se VOIT sans défiler,
    telle que le clic a laissé l'écran. `item` est un locator : après un enregistrement la
    collection est redessinée, et il se résout dans la nouvelle.

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
        f"le message « {message.inner_text()} » s'affiche HORS de la collection dépliée "
        f"(message {m}, collection {i}) : loin du geste, là où la recette ne l'a pas vu")
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


def test_supprimer_laisse_sa_confirmation_a_la_place_de_la_collection(page, decor):
    """Une suppression RÉUSSIE ne peut pas parler dans la collection : elle disparaît, et sa
    ligne de message avec elle. Sa confirmation prend donc la PLACE qu'occupait la
    collection dans la liste, entre sa voisine d'avant et celle d'après — là où l'œil est
    resté. La fiche et le code l'affirmaient ; aucun test ne le vérifiait avant la passe de
    revue du 2026-09-16."""
    with _client(decor["base"]) as c:
        crees = {c.post("/api/collections", json={"nom": n}).json()["id"]
                 for n in ("Espace A", "Espace B", "Espace C")}
    page.on("dialog", lambda d: d.accept())      # le confirm() de la suppression
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    rendues = page.locator("#col-body .col-item")
    rendues.first.wait_for(timeout=3000)
    ordre = [int(rendues.nth(i).get_attribute("data-id")) for i in range(rendues.count())]
    assert len(ordre) == 4, ordre
    # Une collection vide, qu'on peut donc supprimer, et qui a une voisine de chaque côté.
    rang = next(k for k in range(1, len(ordre) - 1) if ordre[k] in crees)
    avant, cid, apres = ordre[rang - 1], ordre[rang], ordre[rang + 1]

    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    item.locator("summary").click()
    item.locator("[data-supprimer]").click()
    item.wait_for(state="detached", timeout=5000)
    trace = page.locator("#col-body p", has_text="supprimée")
    trace.wait_for(timeout=5000)
    places = page.evaluate("""([avant, apres]) => {
      const k = [...document.querySelector('#col-body').children];
      return [k.findIndex((e) => e.dataset.id === String(avant)),
              k.findIndex((e) => e.tagName === 'P' && e.textContent.includes('supprimée')),
              k.findIndex((e) => e.dataset.id === String(apres))];
    }""", [avant, apres])
    assert places[0] + 1 == places[1] and places[1] + 1 == places[2], (
        f"la confirmation n'est pas à la place de la collection supprimée : {places} "
        "(rangs de la voisine d'avant, de la confirmation, de la voisine d'après)")
    assert _se_voit(trace), "la confirmation de suppression n'est pas visible à l'écran"
    with _client(decor["base"]) as c:
        assert cid not in {x["id"] for x in c.get("/api/collections").json()}


def test_prendre_le_nom_du_repli_est_refuse_la_ou_l_on_a_agi(page, decor):
    """Le nom de la collection de repli est RÉSERVÉ : se l'attribuer capturerait les albums
    créés sans collection explicite. La garde interdit de le PRENDRE, et le serveur répond
    en 422 ; l'écran rend ce refus lisible plutôt que de reproduire la règle — une seconde
    copie finirait par dire autre chose que la première.

    Et il le rend LÀ OÙ L'ON A AGI. C'est ce refus-là que la passe de recette du 2026-09-16
    a manqué : lisible, mais sous toute la liste. Le décor est celui de la fiche — trois
    collections, et celle qu'on renomme en a une autre dessous —, parce que c'est la
    situation où la recette l'a manqué. Il n'est pas ce qui fait mordre le test : la boîte
    du message doit tenir dans celle de la collection, ce qu'un message posé sous la liste
    ne fait pas, même sous une seule collection (le mutant l'a montré sur le 409, dont le
    décor n'en a qu'une)."""
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


def test_accorder_demande_de_choisir_utilisateur_ou_groupe(page, decor):
    """AUCUN genre par défaut pour un nouvel accès — tranché le 2026-09-16.

    « Utilisateur » était présélectionné, et la passe de recette a accordé `annotateurs` et
    `etudiants` comme des logins : deux fois sur deux. L'erreur ne se voit pas après coup —
    un groupe accordé en utilisateur n'ouvre rien à personne, et l'écran n'a pour le dire
    que « n'a pas encore ouvert l'application », qui vaut aussi pour un arrivant. Faute de
    pouvoir la signaler, l'écran l'empêche : *+ Accorder* refuse tant que le genre n'est
    pas choisi, et le dit dans la collection. Puis, le genre choisi, l'accès part tel quel."""
    with _client(decor["base"]) as c:
        cid = c.post("/api/collections", json={"nom": "Un espace"}).json()["id"]

    page.goto(decor["base"] + "/administration", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    item.locator("summary").click()
    item.locator(".col-principal").fill("annotateurs")
    assert item.locator(".col-genre").input_value() == "", (
        "un genre est présélectionné : l'erreur de la recette redevient possible par inertie")
    # Ce qui prouve la garde est qu'AUCUNE requête ne part, pas qu'aucun accès n'est créé :
    # le serveur refuse lui-même un genre vide (422), donc « rien de créé » serait vrai sans
    # la garde. La première version de ce test vérifiait la liste des accès, et ne pouvait
    # tomber que par le texte du message (passe de revue, 2026-09-16).
    envois = []
    page.on("request", lambda r: envois.append(r.url)
            if r.method == "PUT" and "/acces" in r.url else None)
    item.locator("[data-accorder]").click()
    message = _message_du_geste(page, item, "utilisateur ou un groupe")
    assert "annotateurs" in message, message
    assert envois == [], f"la demande est partie au serveur sans genre choisi : {envois}"

    item.locator(".col-genre").select_option("groupe")
    item.locator("[data-accorder]").click()
    item.locator(".acces-principal", has_text="annotateurs").wait_for(timeout=5000)
    with _client(decor["base"]) as c:
        acces = c.get(f"/api/collections/{cid}/acces").json()
    assert [(a["principal"], a["genre"], a["niveau"]) for a in acces] == [
        ("annotateurs", "groupe", "lecture")], acces


def _message_sous_le_champ(page, motif):
    """Le message de création, trouvé par son texte puis situé : entre le champ de création
    et la liste des collections, et visible."""
    message = page.locator("#collections-bloc [role=status]", has_text=motif)
    message.wait_for(timeout=5000)
    champ = page.locator("#col-nom").bounding_box()
    liste = page.locator("#col-body").bounding_box()
    m = message.bounding_box()
    assert champ["y"] + champ["height"] <= m["y"] and m["y"] + m["height"] <= liste["y"], (
        f"le message « {message.inner_text()} » n'est pas entre le champ de création "
        f"({champ}) et la liste ({liste}) : {m}")
    assert _se_voit(message), f"le message de création n'est pas visible ({m})"
    return message.inner_text()


def test_la_creation_parle_sous_son_champ(page, decor):
    """Le message de création — refus comme succès — s'affiche sous le champ, en haut du
    bloc, et non sous la liste. Situé à l'écran et plus seulement cherché à son adresse :
    `#col-creer-msg` déplacé sous la liste garderait `test_a11y_bibliotheque_collections`
    vert, qui ne lit que l'adresse — relevé par la passe de revue du 2026-09-16."""
    with _client(decor["base"]) as c:
        for n in ("Un espace", "Un autre espace"):
            c.post("/api/collections", json={"nom": n})
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.locator("#col-body .col-item").first.wait_for(timeout=3000)
    page.click("#col-add")                       # sans nom
    assert "Donnez un nom" in _message_sous_le_champ(page, "Donnez un nom")
    page.fill("#col-nom", "Espace neuf")
    page.click("#col-add")
    assert "Espace neuf" in _message_sous_le_champ(page, "créée")


def test_un_geste_efface_le_message_d_une_autre_collection(page, decor):
    """UN message à la fois, comme au temps de la ligne unique. Les lignes vivent chacune
    dans leur collection : sans cette règle, un refus restait affiché — et reposé à chaque
    rechargement — après un geste réussi ailleurs, à côté d'un formulaire qui ne contenait
    plus le nom refusé ; et « créée » restait en tête du bloc après la suppression de la
    collection créée. Trouvé par la passe de revue du 2026-09-16."""
    repli = _collection_du_decor(decor["base"], decor["album"])["nom"]
    with _client(decor["base"]) as c:
        a = c.post("/api/collections", json={"nom": "Espace A"}).json()["id"]
        b = c.post("/api/collections", json={"nom": "Espace B"}).json()["id"]
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.fill("#col-nom", "Espace C")
    page.click("#col-add")
    _message_sous_le_champ(page, "créée")

    item_a = page.locator(f'#col-body .col-item[data-id="{a}"]')
    item_a.locator("summary").click()
    item_a.locator('[data-champ="nom"]').fill(repli)
    item_a.locator("[data-enregistrer]").click()
    _message_du_geste(page, item_a, "réservé")
    assert page.locator("#collections-bloc .col-msg", has_text="créée").count() == 0, (
        "« créée » reste affiché après un geste dans une autre collection")

    item_b = page.locator(f'#col-body .col-item[data-id="{b}"]')
    item_b.locator("summary").click()
    item_b.locator('[data-champ="licence_defaut"]').fill("CC-BY-4.0")
    _message_du_geste(page, _enregistrer(page, b), "enregistrée")
    assert page.locator("#collections-bloc .col-msg", has_text="réservé").count() == 0, (
        "le refus d'« Espace A » est reposé après l'enregistrement d'« Espace B » : il "
        "parle d'un nom que le formulaire redessiné ne contient plus")


def test_une_relecture_ratee_ne_cache_pas_l_enregistrement(page, decor):
    """Enregistrer réussit, puis la relecture de la liste échoue : l'erreur remplace la
    liste, et la confirmation — qui vivait dans la collection — partait avec. On croyait
    raté un enregistrement qui avait eu lieu. La ligne unique d'avant COL-2, hors de la
    liste, y survivait ; trouvé par la passe de revue du 2026-09-16."""
    with _client(decor["base"]) as c:
        cid = c.post("/api/collections", json={"nom": "Un espace"}).json()["id"]
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    item.locator("summary").click()
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
    confirmation = page.locator("#col-body .col-msg", has_text="enregistrée")
    confirmation.wait_for(timeout=3000)
    assert _se_voit(confirmation), "la confirmation survit, mais ne se voit pas"
    with _client(decor["base"]) as c:
        col = next(x for x in c.get("/api/collections").json() if x["id"] == cid)
    assert col["licence_defaut"] == "CC-BY-4.0"


def test_un_geste_d_acces_efface_le_refus_d_une_autre_collection(page, decor):
    """Administration : même règle d'un message à la fois. Un refus dans A, puis un accès
    accordé dans B, qui recharge la liste : le refus d'A, qui nommait « annotateurs », ne
    doit pas être reposé sous un champ que le rechargement a vidé."""
    with _client(decor["base"]) as c:
        a = c.post("/api/collections", json={"nom": "Espace A"}).json()["id"]
        b = c.post("/api/collections", json={"nom": "Espace B"}).json()["id"]
    page.goto(decor["base"] + "/administration", wait_until="networkidle")
    item_a = page.locator(f'#col-body .col-item[data-id="{a}"]')
    item_a.locator("summary").click()
    item_a.locator(".col-principal").fill("annotateurs")
    item_a.locator("[data-accorder]").click()
    _message_du_geste(page, item_a, "utilisateur ou un groupe")

    item_b = page.locator(f'#col-body .col-item[data-id="{b}"]')
    item_b.locator("summary").click()
    item_b.locator(".col-principal").fill("annotateurs")
    item_b.locator(".col-genre").select_option("groupe")
    item_b.locator("[data-accorder]").click()
    item_b.locator(".acces-principal", has_text="annotateurs").wait_for(timeout=5000)
    # Attendre le rendu COMPLET d'A redessinée : sans cela, on regarderait une collection
    # encore « Chargement… », où aucun message ne peut être — le test passerait sans voir.
    item_a.locator(".col-principal").wait_for(timeout=5000)
    assert page.locator("#col-body .col-msg", has_text="utilisateur ou un groupe").count() == 0, (
        "le refus d'« Espace A » est reposé après un accès accordé dans « Espace B »")


@pytest.mark.parametrize("relecture", ["**/api/collections", "**/api/collections/*/acces"],
                         ids=["liste", "acces"])
def test_un_refus_d_acces_survit_a_une_relecture_ratee(page, decor, relecture):
    """Administration : un refus de niveau recharge la liste, et ce rechargement peut
    échouer — sur la liste elle-même, ou sur les accès de la collection rouverte. L'erreur
    remplace alors ce qui portait le 409, qui partait avec : on ne saurait plus que le
    niveau a été refusé. Le dernier message survit à l'erreur, dans les deux cas. Relevé
    par la passe de revue du 2026-09-16 ; éprouvé ici parce que le commentaire du code
    l'affirmait sans qu'aucun test ne le lise."""
    with _client(decor["base"]) as c:
        cid = c.post("/api/collections", json={"nom": "Un espace"}).json()["id"]
        r = c.put(f"/api/collections/{cid}/acces", json={
            "genre": "utilisateur", "principal": "pilote", "niveau": "proprietaire"})
        assert r.status_code == 200, r.text

    page.goto(decor["base"] + "/administration", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    item.locator("summary").click()
    niveau = item.locator('select[data-principal="pilote"]')
    niveau.wait_for(timeout=5000)

    def panne(route):
        if route.request.method == "GET":
            route.fulfill(status=500, content_type="application/json",
                          body='{"detail": "Relecture impossible (panne simulée)."}')
        else:
            route.continue_()
    page.route(relecture, panne)          # armé APRÈS l'ouverture, qui doit réussir
    niveau.select_option("lecture")
    page.locator("#col-body", has_text="Relecture impossible").wait_for(timeout=5000)
    refus = page.locator("#col-body .col-msg", has_text="dernier propriétaire")
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

    page.locator('.album-row [data-act="edit"]').first.click()
    page.locator("#m-appartenance:not([hidden])").wait_for(timeout=5000)
    cibles = page.locator("#m-appartenance-cible option").all_inner_texts()
    assert cibles == ["Autre écrite"], cibles
    page.click("#m-cancel")

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
    page.fill("#col-nom", "Espace de l'administrateur")
    page.click("#col-add")
    message = _message_sous_le_champ(page, "créée")
    assert "sans en être propriétaire" in message, message
    assert "vous en êtes propriétaire" not in message, message

    page.set_extra_http_headers({"Remote-User": "ines"})
    page.goto(live_server + "/corpus", wait_until="networkidle")
    page.fill("#col-nom", "Espace d'Inès")
    page.click("#col-add")
    message = _message_sous_le_champ(page, "créée")
    assert "vous en êtes propriétaire" in message, message


@pytest.mark.parametrize("live_server", [False, True], indirect=True, ids=["mono", "proxy"])
def test_une_liste_vide_ne_promet_la_propriete_qu_a_qui_la_recevra(page, live_server, request):
    """AUTH-12, option B — les deux listes vides disaient « vous en serez propriétaire »
    (Bibliothèque) et « l'on en devient propriétaire » (Administration) à tout le monde.
    C'est faux pour qui écrit PARTOUT : en mono-poste et pour un administrateur, créer une
    collection ne pose aucun propriétaire. Le serveur de test est neuf, donc SANS aucune
    collection : en mono-poste, aucune promesse ; derrière le proxy, une personne sans accès
    la reçoit, et c'est alors vrai."""
    derriere_proxy = request.node.callspec.params["live_server"]
    if derriere_proxy:
        page.set_extra_http_headers({"Remote-User": "nadia"})
    for chemin, promesse in (("/corpus", "vous en serez propriétaire"),
                             ("/administration", "l'on en devient propriétaire")):
        page.goto(live_server + chemin, wait_until="networkidle")
        note = page.locator("#col-body .col-note", has_text="Aucune collection ouverte")
        note.wait_for(timeout=5000)
        texte = note.inner_text()
        if derriere_proxy:
            assert promesse in texte, (chemin, texte)
        else:
            assert "propriétaire" not in texte, (chemin, texte)
