"""UX-16 — « Qui entre » monté une SECONDE fois : dans la fiche d'une collection de
l'Administration, bloc « 👥 Comptes et groupes ».

Le panneau est un module (`static/lib/qui-entre.js`). La Bibliothèque le monte dans chaque
collection dépliée, pour le propriétaire qui part de son corpus ; l'Administration le monte
ici, pour l'administrateur qui part d'une personne ou d'un groupe. Les gestes de la
Bibliothèque se jouent dans `tests/test_e2e_qui_entre.py`, et ce fichier ne les rejoue pas :
il mesure CE montage, là où il est.

**Chaque geste est mesuré sur la requête PARTIE.** Le module est le même des deux côtés : un
test qui relirait l'état final passerait grâce à l'autre montage, ou grâce au serveur seul
(leçon « deux moitiés, vert mutuel »). Ce qui appartient à cet écran-ci, et que rien d'autre
ne verrait :

- que ce qu'on peut régler se DEMANDE au serveur, collection par collection, au lieu de se
  déduire de ce que la vue est réservée aux administrateurs ;
- qu'après un geste l'hôte relit ce qui en dépend autour — « sans propriétaire », « À
  regarder » — SANS remonter le panneau, donc sans effacer son message ni lui reprendre le
  focus ;
- qu'un panneau quitté pendant un geste se tait, au lieu de faire taire la fiche qu'on lit ;
- que le message d'un geste ne touche pas la fiche du projet, dans le bloc voisin ;
- que les noms mènent aux fiches ICI, et restent du texte dans la Bibliothèque.

La console est écoutée : la régression de la première moitié (un geste en route pendant que
l'hôte redessine) ne se voyait que là.
"""
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/administration", "/corpus")
SURFACES_HORS_PERIMETRE = {
    "/": "l'Atelier annote une planche ; aucun accès ne s'y règle",
    "/recherche": "la Recherche interroge le corpus ; aucun accès ne s'y règle",
    "/exploration": "l'Exploration mesure la langue du corpus ; aucun accès ne s'y règle",
}

# L'administrateur de la doublure de l'annuaire (`tests/doublures/annuaire.json`).
ADMIN_BD = {"Remote-User": "admin-bd", "Remote-Groups": "bd-admins"}

_DOUBLONS = """() => {
  const vus = new Map();
  for (const el of document.querySelectorAll('[id]')) vus.set(el.id, (vus.get(el.id) || 0) + 1);
  return [...vus].filter(([, n]) => n > 1).map(([id]) => id);
}"""


def _client(base):
    return httpx.Client(base_url=base, trust_env=False, timeout=30, headers=ECRITURE)


def _collection(base, nom):
    with _client(base) as c:
        r = c.post("/api/collections", json={"nom": nom})
        assert r.status_code == 201, r.text
        return r.json()["id"]


def _accorder(base, cid, genre, principal, niveau):
    with _client(base) as c:
        r = c.put(f"/api/collections/{cid}/acces",
                  json={"genre": genre, "principal": principal, "niveau": niveau})
        assert r.status_code == 200, r.text


def _acces(base, cid):
    with _client(base) as c:
        return {(a["genre"], a["principal"]): a
                for a in c.get(f"/api/collections/{cid}/acces").json()}


@pytest.fixture
def etude(live_server):
    """Une collection neuve, créée par un administrateur : elle naît SANS propriétaire."""
    return {"base": live_server, "id": _collection(live_server, "Étude réglée ici")}


def _fiche(page, base, cid):
    """Ouvre la fiche de la collection dans « Comptes et groupes » et rend SA section « Qui
    entre », une fois le panneau dessiné (la ligne d'ajout vient avec les accès)."""
    page.goto(base + f"/administration?axe=collections&collection={cid}",
              wait_until="networkidle")
    qui = page.locator("#cg-fiche section[data-qui-entre]")
    qui.locator(".qe-choix").wait_for(timeout=5000)
    return qui


def _ligne(qui, principal):
    return qui.locator(".qe-table tbody tr", has=qui.page.locator("th", has_text=principal))


def _ecouter(page):
    """Ce qui LÈVE dans la page, et ce que la console dit en erreur — à part : un refus du
    serveur attendu (409) s'y inscrit aussi, une exception jamais."""
    exceptions, console = [], []
    page.on("pageerror", lambda e: exceptions.append(str(e)))
    page.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
    return exceptions, console


def _ecritures(page):
    """Les requêtes d'écriture PARTIES de la page : méthode, adresse, corps."""
    parties = []

    def noter(r):
        if r.method in ("PUT", "POST", "PATCH", "DELETE"):
            parties.append((r.method, r.url, r.post_data_json if r.post_data else None))
    page.on("request", noter)
    return parties


def _vue_relue(page):
    """L'attente de la relecture de la vue par l'HÔTE, que tout geste abouti déclenche."""
    return page.expect_response(lambda r: r.url.endswith("/api/comptes-et-groupes"))


# ── Les trois gestes, mesurés ici ──────────────────────────────────────────────────────


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_faire_entrer_cocher_et_faire_sortir_partent_de_l_administration(page, etude):
    """Les trois gestes du panneau, joués dans la fiche de l'Administration, et pour chacun la
    requête PARTIE : vers CETTE collection, avec ce qu'on a choisi.

    Et ce que l'hôte fait autour. La collection naît sans propriétaire : la fiche le dit, « À
    regarder » aussi. En désigner un dans le panneau doit l'effacer des DEUX — la vue se
    relit —, sans que le panneau soit remonté : sa section est la même, et le focus est
    resté sur la case qu'on vient de cocher. Un hôte qui redessinerait toute la fiche
    « pour être à jour » passerait tout le reste de ce test.

    Enfin un refus du serveur — on ne retire pas le dernier propriétaire — se LIT ici comme
    dans la Bibliothèque : la requête est partie, le 409 est rendu, la ligne reste."""
    base, cid = etude["base"], etude["id"]
    url = f"{base}/api/collections/{cid}/acces"
    _accorder(base, cid, "utilisateur", "lectrice", "lecture")
    page.set_extra_http_headers(ADMIN_BD)
    exceptions, console = _ecouter(page)
    qui = _fiche(page, base, cid)
    parties = _ecritures(page)

    sous, regarder = page.locator("#cg-fiche .cg-sous"), page.locator("#cg-signaux")
    expect(sous).to_contain_text("sans propriétaire")
    expect(regarder).to_contain_text("« Étude réglée ici » n'a pas de propriétaire")
    # Le témoin du montage : posé sur la section, il disparaît si la fiche est redessinée.
    qui.evaluate("el => { el.dataset.temoin = 'pose'; }")

    # 1. Faire entrer.
    qui.locator(".qe-choix").select_option("groupe:annotateurs")
    with _vue_relue(page):
        qui.locator(".qe-faire-entrer").click()
    page.wait_for_load_state("networkidle")
    assert len(parties) == 1 and parties[0][:2] == ("PUT", url), parties
    assert {k: parties[0][2][k] for k in ("genre", "principal", "niveau")} == {
        "genre": "groupe", "principal": "annotateurs", "niveau": "lecture"}
    # Le message a survécu à la relecture de la vue par l'hôte.
    expect(qui.locator(".qe-msg")).to_be_visible()
    expect(qui.locator(".qe-msg")).to_have_text(
        "Le groupe annotateurs entre dans « Étude réglée ici », en lecture. Cochez les "
        "autres actes.")
    expect(qui).to_have_attribute("data-temoin", "pose")
    expect(sous).to_contain_text("sans propriétaire")

    # 2. Cocher un cran — le dernier, qui fait un propriétaire.
    case = _ligne(qui, "annotateurs").locator('.qe-case[data-cran="proprietaire"]')
    with _vue_relue(page):
        case.check()
    page.wait_for_load_state("networkidle")
    assert len(parties) == 2 and parties[1][:2] == ("PUT", url), parties
    assert {k: parties[1][2][k] for k in ("genre", "principal", "niveau")} == {
        "genre": "groupe", "principal": "annotateurs", "niveau": "proprietaire"}
    # L'hôte a relu ce qui en dépend…
    expect(sous).not_to_contain_text("sans propriétaire")
    expect(regarder).not_to_contain_text("« Étude réglée ici » n'a pas de propriétaire")
    # … sans remonter le panneau : même section, et le focus là où le module l'a rendu.
    expect(qui).to_have_attribute("data-temoin", "pose")
    case = _ligne(qui, "annotateurs").locator('.qe-case[data-cran="proprietaire"]')
    expect(case).to_be_checked()
    expect(case).to_be_focused()
    assert _acces(base, cid)[("groupe", "annotateurs")]["niveau"] == "proprietaire"

    # 3. Faire sortir.
    with _vue_relue(page):
        _ligne(qui, "lectrice").locator(".qe-retirer").click()
    page.wait_for_load_state("networkidle")
    assert len(parties) == 3, parties
    assert parties[2][:2] == ("DELETE", f"{url}/utilisateur/lectrice"), parties[2]
    expect(qui.locator(".qe-table tbody tr")).to_have_count(1)
    expect(qui.locator(".qe-titre")).to_be_focused()
    expect(qui).to_have_attribute("data-temoin", "pose")
    assert ("utilisateur", "lectrice") not in _acces(base, cid)
    assert exceptions == [] and console == [], (exceptions, console)

    # Le refus : `annotateurs` est le dernier propriétaire.
    with page.expect_response(lambda r: r.request.method == "DELETE") as reponse:
        _ligne(qui, "annotateurs").locator(".qe-retirer").click()
    assert reponse.value.status == 409
    assert parties[3][:2] == ("DELETE", f"{url}/groupe/annotateurs"), parties[3]
    expect(qui.locator(".qe-msg.erreur")).to_be_visible()
    expect(qui.locator(".qe-msg.erreur")).to_contain_text("dernier propriétaire")
    expect(qui.locator(".qe-table tbody tr")).to_have_count(1)
    assert ("groupe", "annotateurs") in _acces(base, cid)
    assert exceptions == [], exceptions


def test_a_375_px_le_geste_part_d_une_carte_et_un_nom_ouvre_sa_fiche(page, etude):
    """Sous le seuil étroit, la fiche REMPLACE la liste, et le panneau y est en cartes : le
    même geste, la même requête. Un nom y est un lien comme au large, et la fiche qu'il ouvre
    reçoit le focus — la liste n'est plus à l'écran pour le garder."""
    base, cid = etude["base"], etude["id"]
    _accorder(base, cid, "groupe", "annotateurs", "lecture")
    _accorder(base, cid, "utilisateur", "proprio", "proprietaire")
    page.set_viewport_size({"width": 375, "height": 800})
    qui = _fiche(page, base, cid)
    expect(page.locator(".cg-liste")).to_be_hidden()
    expect(qui.locator(".qe-table")).to_have_count(0)
    expect(qui.locator(".qe-carte")).to_have_count(2)

    carte = qui.locator(".qe-carte", has=page.locator(".qe-qui", has_text="annotateurs"))
    with page.expect_request(lambda r: r.method == "PUT") as envoi:
        carte.locator('.qe-case[data-cran="ecriture"]').check()
    assert envoi.value.url == f"{base}/api/collections/{cid}/acces"
    assert envoi.value.post_data_json["niveau"] == "ecriture"
    expect(qui.locator(".qe-carte", has=page.locator(".qe-qui", has_text="annotateurs"))
           .locator('.qe-case[data-cran="ecriture"]')).to_be_checked()
    assert _acces(base, cid)[("groupe", "annotateurs")]["niveau"] == "ecriture"

    qui.locator(".qe-carte .qe-qui button", has_text="annotateurs").click()
    expect(page.locator("#cg-fiche-titre")).to_have_text("annotateurs")
    expect(page.locator("#cg-fiche-titre")).to_be_focused()


# ── La garde est celle de l'ACTE ───────────────────────────────────────────────────────


@pytest.mark.parametrize("cas", ["non_administrable", "absente", "illisible"])
def test_ce_qu_on_peut_regler_se_demande_au_serveur(page, etude, cas):
    """La vue est réservée aux administrateurs, et un administrateur règle toute collection :
    aujourd'hui, le serveur répond toujours « oui ». C'est justement pourquoi la question
    doit être POSÉE — un panneau qui se croirait réglable parce que son contenant est gardé
    hériterait de la garde de son contenant (leçon d'AUTH-4), et le jour où la vue s'ouvrira
    à un autre public, il offrirait ses cases à qui ne peut rien en faire.

    La réponse de `GET /api/collections` est donc interceptée pour dire autre chose, et
    l'écran doit la croire : pas de case, pas de ligne d'ajout, et AUCUNE lecture des accès
    — la liste des accès est une donnée sur des personnes. Trois réponses : la collection
    n'est pas administrable ; elle n'est pas dans la liste ; la liste est illisible. La
    troisième ne se confond pas avec les deux autres : ne pas savoir n'est pas « non »."""
    base, cid = etude["base"], etude["id"]
    _accorder(base, cid, "groupe", "annotateurs", "lecture")

    # La prémisse, sans rien intercepter : ici, on règle.
    qui = _fiche(page, base, cid)
    expect(qui.locator(".qe-case").first).to_be_visible()

    demandes, lectures = [], []

    def servir(route):
        if route.request.method != "GET":
            route.continue_()
            return
        demandes.append(route.request.url)
        if cas == "illisible":
            route.fulfill(status=500, content_type="application/json",
                          body='{"detail": "panne voulue par le test"}')
            return
        reponse = route.fetch()
        liste = reponse.json()
        assert any(c["id"] == cid and c["administrable"] for c in liste), (
            "prémisse : le serveur dit cette collection administrable")
        if cas == "absente":
            liste = [c for c in liste if c["id"] != cid]
        else:
            liste = [{**c, "administrable": False} if c["id"] == cid else c for c in liste]
        route.fulfill(response=reponse, json=liste)

    page.route("**/api/collections", servir)
    page.on("request", lambda r: lectures.append(r.url)
            if re.search(rf"/api/collections/{cid}/(acces|annuaire)$", r.url) else None)
    page.goto(base + f"/administration?axe=collections&collection={cid}",
              wait_until="networkidle")
    expect(page.locator("#cg-fiche-titre")).to_have_text("Étude réglée ici")
    assert demandes, "la question n'a pas été posée : `GET /api/collections` n'est pas parti"

    qui = page.locator("#cg-fiche section[data-qui-entre]")
    if cas == "illisible":
        expect(qui).to_contain_text(
            "La liste des collections n'a pas pu être lue (panne voulue par le test) : "
            "impossible de savoir si vous réglez qui entre dans celle-ci.")
        expect(qui).not_to_contain_text("Seul un propriétaire")
    else:
        expect(qui).to_be_visible()
        expect(qui).to_have_text(
            "Seul un propriétaire de la collection voit et règle qui y entre.")
    expect(qui.locator("input, select, button")).to_have_count(0)
    assert lectures == [], f"les accès ont été lus sans le droit de les régler : {lectures}"
    # Le reste de la fiche, lui, se lit toujours.
    expect(page.locator("#cg-fiche a.cg-decrire")).to_be_visible()


# ── Changer de fiche ───────────────────────────────────────────────────────────────────


def test_quitter_une_fiche_pendant_un_geste_ne_fait_taire_ni_ne_leve_rien(page, live_server):
    """Un « + Faire entrer » est en route dans la fiche de A ; on ouvre celle de B, où un
    refus s'affiche ; la réponse de A revient. Le panneau de A a été DÉMONTÉ avec sa fiche :
    il ne parle plus. L'accès est accordé — le serveur l'a reçu —, le message de B est
    toujours là, et rien ne lève.

    C'est ce que le démontage achète, et rien d'autre ne le montre. Sans lui, la page marche :
    le panneau de A, détaché du document, ne retient aucun identifiant (propriété du module),
    donc ni doublon ni dérive. Mais il écrit encore son message à la fin de son geste et
    prévient l'hôte, qui applique sa règle — un seul message à la fois — et efface celui que
    B vient d'afficher. Un refus qui disparaît tout seul une seconde après.

    Et il n'y a jamais qu'UN panneau dans la page : une fiche à la fois."""
    a = _collection(live_server, "Étude A quittée")
    b = _collection(live_server, "Étude B ouverte")
    exceptions, console = _ecouter(page)
    qui = _fiche(page, live_server, a)

    retenues = []
    page.route(f"**/api/collections/{a}/acces",
               lambda route: retenues.append(route) if route.request.method == "PUT"
               else route.continue_())
    qui.locator(".qe-choix").select_option("groupe:annotateurs")
    qui.locator(".qe-faire-entrer").click()
    for _ in range(50):
        if retenues:
            break
        page.wait_for_timeout(50)
    assert len(retenues) == 1, "prémisse : le PUT de A est parti, et il est retenu"

    page.locator("#cg-objets .cg-objet", has_text="Étude B ouverte").click()
    expect(page.locator("#cg-fiche-titre")).to_have_text("Étude B ouverte")
    qui_b = page.locator("#cg-fiche section[data-qui-entre]")
    qui_b.locator(".qe-choix").wait_for(timeout=5000)
    expect(qui_b).to_have_attribute("data-qe", str(b))
    qui_b.locator(".qe-faire-entrer").click()
    refus = qui_b.locator(".qe-msg.erreur")
    expect(refus).to_be_visible()
    expect(refus).to_contain_text("Choisissez un groupe")

    # La réponse de A revient : le geste a abouti, l'hôte relit la vue.
    with _vue_relue(page):
        retenues[0].continue_()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(300)
    assert exceptions == [] and console == [], (exceptions, console)
    assert _acces(live_server, a)[("groupe", "annotateurs")]["niveau"] == "lecture"
    expect(refus).to_be_visible()
    expect(refus).to_contain_text("Choisissez un groupe")

    assert page.locator(".qe").count() == 1, "deux panneaux « Qui entre » dans la page"
    assert page.evaluate(_DOUBLONS) == []
    # Le panneau de B est vivant, et sa requête part vers B.
    qui_b.locator(".qe-choix").select_option("groupe:annotateurs")
    with page.expect_request(lambda r: r.method == "PUT") as envoi:
        qui_b.locator(".qe-faire-entrer").click()
    assert envoi.value.url == f"{live_server}/api/collections/{b}/acces"

    # Revenir à A par la liste : le panneau y est remonté sous les MÊMES identifiants — un
    # montage mort ne retient rien —, et il montre l'accès accordé pendant qu'on était parti.
    page.locator("#cg-objets .cg-objet", has_text="Étude A quittée").click()
    qui_a = page.locator("#cg-fiche section[data-qui-entre]")
    expect(qui_a.locator(".qe-titre")).to_have_attribute("id", f"qe-titre-{a}")
    expect(_ligne(qui_a, "annotateurs")).to_have_count(1)
    assert page.locator(".qe").count() == 1
    assert page.evaluate(_DOUBLONS) == []


# ── Un seul message à la fois : une règle de CE bloc ───────────────────────────────────


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_message_de_qui_entre_ne_touche_pas_la_fiche_du_projet_voisin(page, etude):
    """« Un seul message à la fois » est une règle d'ÉCRAN, et sur cette page elle vaut bloc
    par bloc : « Projets » a la sienne, « Comptes et groupes » la sienne. Le module écrit sa
    ligne et prévient ; c'est l'hôte qui décide ce qu'il fait taire, et il s'arrête à son
    bloc. Un message affiché dans la fiche d'un projet survit donc à un refus puis à un geste
    abouti de « Qui entre » — et l'inverse.

    Au passage, ce qui a remplacé « Personne : seuls les administrateurs de l'instance la
    voient. » : la phrase du panneau, et sa note qui NOMME les groupes d'administration lus
    dans `/api/moi`."""
    base, cid = etude["base"], etude["id"]
    page.set_extra_http_headers(ADMIN_BD)
    qui = _fiche(page, base, cid)
    expect(qui.locator(".qe-tableau")).to_be_visible()
    expect(qui.locator(".qe-tableau")).to_have_text(
        "Aucun accès n'est accordé sur cette collection.")
    expect(qui.locator(".col-note-admin")).to_contain_text(
        "Les administrateurs de l'instance (bd-admins) lisent et écrivent toute collection")

    # Un message dans la fiche du projet, à côté : « Renommer » sans rien changer.
    voisin = page.locator("#pj-fiche-msg")
    page.locator("#pj-fiche [data-pj-renommer]").click()
    expect(voisin).to_be_visible()
    expect(voisin).to_have_text("Rien n'a changé.")

    qui.locator(".qe-faire-entrer").click()                    # un refus d'écran
    expect(qui.locator(".qe-msg.erreur")).to_be_visible()
    expect(qui.locator(".qe-msg.erreur")).to_contain_text("Choisissez un groupe")
    expect(voisin).to_have_text("Rien n'a changé.")

    qui.locator(".qe-choix").select_option("groupe:annotateurs")
    with _vue_relue(page):
        qui.locator(".qe-faire-entrer").click()                # un geste abouti
    page.wait_for_load_state("networkidle")
    message = qui.locator(".qe-msg")
    expect(message).to_contain_text("Le groupe annotateurs entre dans « Étude réglée ici »")
    expect(voisin).to_have_text("Rien n'a changé.")

    # Et dans l'autre sens : un geste du bloc voisin ne fait pas taire « Qui entre ».
    page.locator("#pj-nom").fill("")
    page.locator("#pj-ajouter").click()
    expect(page.locator("#pj-msg.erreur")).to_be_visible()
    expect(page.locator("#pj-msg.erreur")).to_have_text("Donnez un nom au projet.")
    expect(message).to_contain_text("Le groupe annotateurs entre dans « Étude réglée ici »")


# ── Les noms mènent aux fiches ICI, et pas dans la Bibliothèque ────────────────────────


def test_un_nom_ouvre_sa_fiche_ici_et_reste_du_texte_dans_la_bibliotheque(page, etude):
    """Dans l'Administration, chaque nom du panneau mène à la fiche du compte ou du groupe,
    comme la liste en lecture le faisait ; « Retour » ramène à la collection, son panneau
    remonté sous les mêmes identifiants. Dans la Bibliothèque, le MÊME panneau, sur la même
    collection, garde ses noms en texte : un propriétaire n'y a aucune fiche de compte à
    ouvrir, et son montage est le témoin de l'extraction — il ne change pas."""
    base, cid = etude["base"], etude["id"]
    _accorder(base, cid, "groupe", "annotateurs", "lecture")
    _accorder(base, cid, "utilisateur", "lectrice", "lecture")
    qui = _fiche(page, base, cid)
    noms = qui.locator(".qe-table tbody th[scope=row] button")
    expect(noms).to_have_count(2)
    # Le nom accessible d'une case nomme toujours sa ligne : le bouton n'a rien retiré.
    case = _ligne(qui, "annotateurs").locator('.qe-case[data-cran="lecture"]')
    nom = page.evaluate("""(el) => (el.getAttribute('aria-labelledby') || '').split(' ')
      .map((id) => document.getElementById(id)?.textContent.trim()).join(' | ')""",
                        case.element_handle())
    assert "groupe annotateurs" in " ".join(nom.split()), nom

    _ligne(qui, "lectrice").locator("th button").click()
    expect(page.locator('#cg [data-axe="comptes"]')).to_have_attribute("aria-pressed", "true")
    assert "compte=lectrice" in page.url, page.url
    expect(page.locator("#cg-fiche-titre")).to_be_focused()
    assert page.locator(".qe").count() == 0, "le panneau a survécu à sa fiche"

    page.go_back()
    qui = page.locator("#cg-fiche section[data-qui-entre]")
    qui.locator(".qe-choix").wait_for(timeout=5000)
    expect(qui.locator(".qe-titre")).to_have_attribute("id", f"qe-titre-{cid}")
    _ligne(qui, "annotateurs").locator("th button").click()
    expect(page.locator('#cg [data-axe="groupes"]')).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#cg-fiche-titre")).to_have_text("annotateurs")
    assert page.evaluate(_DOUBLONS) == []

    # Le témoin : la Bibliothèque, même collection.
    page.goto(base + f"/corpus?collection={cid}", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    item.locator(".qe-choix").wait_for(timeout=5000)
    lignes = item.locator(".qe-table tbody th[scope=row]")
    expect(lignes).to_have_count(2)
    expect(item.locator(".qe-table tbody th[scope=row] button")).to_have_count(0)
    assert item.locator("button.qe-ouvrir").count() == 0
    # Et son titre est resté au rang qu'il avait : l'option de rang est à l'Administration.
    assert item.locator(".qe-titre").evaluate("el => el.tagName") == "H3"


def test_ouvrir_une_fiche_pendant_la_relecture_de_la_vue_garde_le_clavier(page, etude):
    """Après un geste, l'hôte relit la vue. Si, PENDANT cette relecture, on ouvre la fiche
    d'un compte par son nom, cette fiche a été dessinée sur les données d'avant le geste :
    elle doit être redessinée quand la vue revient — et le clavier, qui était sur son titre,
    doit y rester au lieu de retomber sur la page.

    C'est l'autre moitié de « l'hôte ne remonte pas le panneau » : la fiche n'est gardée
    telle quelle que si elle montre encore la collection qu'on vient de régler."""
    base, cid = etude["base"], etude["id"]
    _accorder(base, cid, "utilisateur", "lectrice", "lecture")
    exceptions, console = _ecouter(page)
    qui = _fiche(page, base, cid)

    retenues = []
    page.route("**/api/comptes-et-groupes", lambda route: retenues.append(route))
    with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith("/acces")):
        _ligne(qui, "lectrice").locator('.qe-case[data-cran="ecriture"]').check()
    for _ in range(50):
        if retenues:
            break
        page.wait_for_timeout(50)
    assert len(retenues) == 1, "prémisse : la vue est en cours de relecture, et retenue"

    _ligne(qui, "lectrice").locator("th button").click()
    titre = page.locator("#cg-fiche-titre")
    expect(titre).to_be_focused()
    ligne = page.locator("#cg-fiche .cg-section", has_text="Collections").locator(
        "li", has_text="Étude réglée ici")
    expect(ligne).to_have_count(1)
    expect(ligne).not_to_contain_text("annoter")      # dessinée sur les données d'AVANT

    retenues[0].continue_()
    expect(ligne).to_contain_text("annoter")          # redessinée : le geste s'y lit
    expect(titre).to_be_focused()
    assert exceptions == [] and console == [], (exceptions, console)


# ── L'adresse que plus aucun lien n'écrit ──────────────────────────────────────────────


def test_l_adresse_de_la_bibliotheque_preselectionne_toujours_un_groupe(page, etude):
    """`/corpus?collection=<id>&groupe=<nom>` était la cible de « Ouvrir une collection à ce
    groupe… ». Ce geste mène désormais à la fiche de la collection, dans l'Administration, et
    plus aucun lien de l'application n'écrit cette adresse. Elle reste VALIDE — on l'a
    envoyée, on l'a gardée en signet — et rien d'autre ne la jouait que le test du geste qui
    vient de changer de destination : sans celui-ci, elle pourrait casser sans que rien ne
    tombe.

    Un groupe de l'annuaire est CHOISI dans la liste ; un nom que l'annuaire ne connaît pas
    est tapé, déclaré groupe. Rien n'est accordé par l'adresse."""
    base, cid = etude["base"], etude["id"]
    envois = []
    page.on("request", lambda r: envois.append((r.method, r.url)) if r.method != "GET" else None)

    page.goto(base + f"/corpus?collection={cid}&groupe=annotateurs", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    expect(item).to_have_attribute("open", "")
    expect(item.locator(".qe-choix")).to_have_value("groupe:annotateurs")
    expect(item.locator(".qe-libre")).to_be_hidden()

    page.goto(base + f"/corpus?collection={cid}&groupe=cours-inconnu", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    expect(item.locator(".qe-choix")).to_have_value("autre")
    expect(item.locator(".qe-libre")).to_be_visible()
    expect(item.locator(".qe-nom")).to_have_value("cours-inconnu")
    expect(item.locator(".qe-genre")).to_have_value("groupe")
    assert envois == [], f"une écriture est partie sans geste : {envois}"
