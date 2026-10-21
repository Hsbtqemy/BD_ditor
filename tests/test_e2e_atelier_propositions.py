"""Les champs à propositions du panneau d'annotation : ce qu'Entrée décide (ANN-6).

Les champs du panneau qui proposent une liste sous la saisie — « dimension : valeur » sur
trois montages (la Situation d'une case, le profil d'un personnage atteint par le
locuteur, le même profil atteint par la boîte personnage) — la recevaient 200 ms après la
dernière frappe, puis le temps d'une lecture. Et Entrée la consultait telle qu'elle était.
Reproduit par la relecture croisée du 2026-10-12 :

- une seule valeur au vocabulaire, « grotte » tapé vite : c'est « lieu : falaise » qui
  part, et Entrée dans le champ VIDE la pose aussi ;
- « lieu : phare » tapé vite : rien ne part, il faut une seconde Entrée ;
- sur un profil, « argot » pose « registre : soutenu » — pour tout le corpus.

**La course est rendue DÉTERMINISTE, elle n'est pas rejouée au chronomètre.** Aucun test
ne compte sur une vitesse de frappe : la lecture qui ferait arriver la liste est TENUE en
vol (`page.route`), et relâchée quand le test le décide. « Vite » veut donc dire ici
« avant que la réponse n'arrive », ce qui est exactement la condition du défaut.

**Ce qui est mesuré est la requête PARTIE** — méthode, chemin, corps —, pas seulement
l'état final : un écran qui afficherait la bonne puce sans rien envoyer, ou qui enverrait
trois requêtes là où une suffit, rendrait le même état final. Et « rien n'est parti » ne
s'affirme qu'après un TÉMOIN que l'écran a bien traité le geste : sans lui, l'assertion
passerait sur une page qui n'a encore rien fait.
"""
import json
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source. Ces champs ne vivent que
# dans le panneau d'annotation de l'Atelier.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/recherche": "aucun champ à propositions qui écrive : la Recherche filtre, elle n'attribue rien",
    "/corpus": "aucun champ « dimension : valeur » ni de personnage : la Bibliothèque range des albums",
    "/exploration": "le vocabulaire s'y édite dans le Lexique, par des formulaires sans liste de propositions",
    "/administration": "aucun panneau d'annotation : rien n'y porte sur une région d'une planche",
}

# Les trois montages du champ « dimension : valeur ». Ils partagent leur code, pas leur
# conséquence : une situation décrit UNE case, un profil vaut pour TOUT le corpus.
MONTAGES = {
    "situation": {
        "zone": "case", "champ": "#sit-input", "liste": "#sit-suggest",
        "cible": "case", "dimension": "lieu",
        "connue": "falaise", "autre": "phare", "debut_autre": "ph", "inconnue": "grotte"},
    "profil-par-le-locuteur": {
        "zone": "bulle", "champ": "#perso-attr-input", "liste": "#perso-attr-suggest",
        "cible": "personnage", "dimension": "registre",
        "connue": "soutenu", "autre": "familier", "debut_autre": "fam", "inconnue": "argot"},
    "profil-par-la-boite": {
        "zone": "personnage", "champ": "#perso-profil-input", "liste": "#perso-profil-suggest",
        "cible": "personnage", "dimension": "registre",
        "connue": "soutenu", "autre": "familier", "debut_autre": "fam", "inconnue": "argot"},
}

LECTURE_VALEURS = re.compile(r"/api/attributs/valeurs\?")


# --------------------------------------------------------------------------- #
# Le décor et les gestes
# --------------------------------------------------------------------------- #
@pytest.fixture
def atelier(live_server):
    """Une planche, une case, et sous elle une bulle, un cartouche et une boîte
    personnage. « Tintin » est au registre : il parle dans la bulle et il est montré dans
    la boîte, si bien que les deux champs de profil s'offrent — sur le MÊME personnage."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "E2E propositions"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(800, 1000), "image/png")}).json()["id"]

        def region(type_zone, x, y, parent=None):
            corps = {"type": type_zone, "x": x, "y": y, "w": 700, "h": 900}
            if parent is not None:
                corps.update(parent_id=parent, w=280, h=180)
            rep = c.post(f"/api/planches/{pid}/regions", json=corps)
            assert rep.status_code in (200, 201), rep.text
            return rep.json()["id"]

        case = region("case", 40, 40)
        decor = {"base": live_server, "album": aid, "planche": pid, "case": case,
                 "bulle": region("bulle", 60, 60, case),
                 "cartouche": region("cartouche", 60, 300, case),
                 "personnage": region("personnage", 400, 300, case),
                 "tintin": c.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]}
        for lien in (f"/api/regions/{decor['bulle']}/locuteur",
                     f"/api/regions/{decor['personnage']}/personnage"):
            rep = c.put(lien, json={"personnage_id": decor["tintin"]})
            assert rep.status_code == 200, rep.text
    finally:
        c.close()
    return decor


def _api(decor, ecriture=False):
    return httpx.Client(base_url=decor["base"], trust_env=False, timeout=30,
                        headers=ECRITURE if ecriture else {})


def _semer(decor, m, *valeurs):
    """Pose des valeurs au vocabulaire du montage ; rend {valeur: id}."""
    with _api(decor, ecriture=True) as c:
        dim = c.post("/api/attributs/dimensions",
                     json={"cible": m["cible"], "nom": m["dimension"]}).json()["id"]
        return {v: c.post(f"/api/attributs/dimensions/{dim}/valeurs",
                          json={"valeur": v}).json()["id"] for v in valeurs}


def _chemin_des_attributs(decor, m):
    """Là où le montage affecte : la case, ou le personnage (commun aux deux profils)."""
    if m["cible"] == "case":
        return f"/api/regions/{decor['case']}/attributs"
    return f"/api/personnages/{decor['tintin']}/attributs"


def _poses(decor, m):
    with _api(decor) as c:
        return [(a["dimension"], a["valeur"])
                for a in c.get(_chemin_des_attributs(decor, m)).json()]


def _vocabulaire(decor, m):
    with _api(decor) as c:
        return [(v["dimension"], v["valeur"])
                for v in c.get(f"/api/attributs/valeurs?cible={m['cible']}").json()]


def _ouvrir(page, decor, type_zone):
    """Ouvre l'Atelier sur la région du type demandé, en mode Annotation."""
    page.goto(f"{decor['base']}/?album={decor['album']}&planche={decor['planche']}"
              f"&region={decor[type_zone]}", wait_until="networkidle")
    expect(page.locator("#region-type")).to_have_value(type_zone, timeout=15000)
    page.locator('button[data-mode="annotation"]').click()
    expect(page.locator("#panel-annotation")).to_be_visible(timeout=15000)


def _noeud(page, rid):
    """Le nœud de l'arbre de structure qui porte cette région."""
    return page.locator(".tnode", has=page.locator(".tn-id", has_text=re.compile(rf"^#{rid}$")))


def _est(methode, chemin):
    """Prédicat de requête OU de réponse : cette méthode, sur ce chemin exact."""
    def predicat(objet):
        requete = getattr(objet, "request", objet)
        return requete.method == methode and requete.url.endswith(chemin)
    return predicat


def _ecritures(page):
    """Le journal de ce qui PART et qui écrit : « MÉTHODE chemin corps », dans l'ordre."""
    parties = []

    def noter(requete):
        if requete.method != "GET" and "/api/" in requete.url:
            chemin = re.sub(r"^https?://[^/]+", "", requete.url)
            parties.append(f"{requete.method} {chemin} {requete.post_data or ''}".strip())
    page.on("request", noter)
    return parties


class Retenue:
    """Tient en vol les requêtes d'un motif, jusqu'à ce que le test les relâche.

    C'est ce qui rend la course déterministe : tant que la lecture est tenue, la liste
    que l'écran a sous la main est celle d'AVANT, quelle que soit la vitesse du poste.
    """

    def __init__(self, page, motif, methode="GET"):
        self.page, self.tenues, self.ouverte = page, [], False

        def tenir(route):
            if not self.ouverte and route.request.method == methode:
                self.tenues.append(route)
            else:
                route.continue_()
        page.route(motif, tenir)

    def attendre(self, n=1):
        """Au moins `n` requêtes tenues. Les gestionnaires de route ne tournent que
        PENDANT un appel à la page : on patiente par elle."""
        for _ in range(150):
            if len(self.tenues) >= n:
                return self.tenues
            self.page.wait_for_timeout(100)
        raise AssertionError(
            f"{len(self.tenues)} requête(s) tenue(s), {n} attendue(s) : "
            f"{[r.request.url for r in self.tenues]}")

    def relacher(self):
        """Laisse tout passer, ce qui est tenu comme ce qui viendra."""
        self.ouverte = True
        for route in self.tenues:
            route.continue_()
        self.tenues = []


def _repondre(page, route, corps):
    """Répond SOI-MÊME à une requête tenue, et attend que la page ait reçu la réponse."""
    with page.expect_response(lambda r: r.request is route.request):
        route.fulfill(status=200, content_type="application/json", body=json.dumps(corps))


def _message(page):
    """Le message de l'écran quand Entrée ne fait rien. Sa formulation n'est pas
    verrouillée — seulement ce qu'il doit porter : la forme attendue."""
    return page.locator("#toasts .toast", has_text=re.compile(r"dimension\s:\svaleur"))


def _entree_traitee(page, parties):
    """Attend que l'écran ait RÉPONDU à Entrée, d'une façon ou de l'autre : une écriture
    partie, ou le message. L'appelant juge ensuite — les écritures d'abord : si le défaut
    revient, c'est « Entrée a écrit ceci » qu'il faut lire, pas « le message manque »."""
    for _ in range(150):
        if parties or _message(page).count():
            return
        page.wait_for_timeout(100)
    raise AssertionError("ni écriture ni message : l'écran n'a pas répondu à Entrée")


# --------------------------------------------------------------------------- #
# « dimension : valeur » — Entrée agit sur ce qui est tapé
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("montage", list(MONTAGES))
def test_un_mot_tape_avant_la_liste_ne_pose_pas_la_seule_valeur_connue(page, atelier, montage):
    """Une seule valeur au vocabulaire ; on tape un AUTRE mot et Entrée, la liste de ce mot
    n'étant pas revenue : rien n'est affecté. Avant, la seule valeur connue partait —
    « grotte » posait « lieu : falaise », « argot » posait « registre : soutenu »."""
    m = MONTAGES[montage]
    _semer(atelier, m, m["connue"])
    _ouvrir(page, atelier, m["zone"])
    champ, liste = page.locator(m["champ"]), page.locator(f"{m['liste']} div")
    parties = _ecritures(page)

    champ.click()
    # Le témoin d'amont : la liste du champ VIDE est là, avec son unique proposition —
    # c'est elle qu'Entrée consultait.
    expect(liste).to_have_count(1, timeout=15000)
    expect(liste).to_contain_text(m["connue"])

    lectures = Retenue(page, LECTURE_VALEURS)        # la liste du mot tapé n'arrivera pas
    champ.press_sequentially(m["inconnue"], delay=0)
    champ.press("Enter")

    # Le témoin d'aval : l'écran a TRAITÉ Entrée — il dit que rien n'est ajouté.
    _entree_traitee(page, parties)
    assert parties == [], f"Entrée a écrit d'après une liste faite pour une autre saisie : {parties}"
    expect(_message(page)).to_be_visible()
    assert _poses(atelier, m) == []
    expect(champ).to_have_value(m["inconnue"])       # la saisie reste, pour être complétée

    # Et la lecture, relâchée, n'y change rien après coup.
    lectures.attendre(1)
    with page.expect_response(lambda r: LECTURE_VALEURS.search(r.url) is not None):
        lectures.relacher()
    page.wait_for_timeout(300)
    assert parties == [] and _poses(atelier, m) == []


@pytest.mark.parametrize("montage", list(MONTAGES))
def test_entree_dans_le_champ_vide_n_affecte_rien(page, atelier, montage):
    """Champ vide, une seule proposition affichée : Entrée ne la prend pas. « Un seul
    résultat, Entrée le prend » ne vaut que pour une saisie."""
    m = MONTAGES[montage]
    _semer(atelier, m, m["connue"])
    _ouvrir(page, atelier, m["zone"])
    champ, liste = page.locator(m["champ"]), page.locator(f"{m['liste']} div")
    parties = _ecritures(page)

    champ.click()
    expect(liste).to_have_count(1, timeout=15000)
    champ.press("Enter")
    # Le témoin : des frappes POSTÉRIEURES à Entrée sont traitées — la liste se referme
    # sur une saisie qui ne désigne rien. Entrée a donc été traitée avant elles.
    champ.press_sequentially("zz", delay=0)
    expect(page.locator(m["liste"])).to_be_hidden(timeout=15000)

    assert parties == [], f"Entrée dans le champ vide a écrit : {parties}"
    assert _poses(atelier, m) == []
    expect(page.locator("#toasts .toast")).to_have_count(0)   # champ vide : rien à dire non plus


@pytest.mark.parametrize("montage", list(MONTAGES))
def test_la_forme_complete_tapee_avant_la_liste_aboutit_en_une_entree(page, atelier, montage):
    """« dimension : valeur » d'une valeur NEUVE, Entrée avant que la liste ne revienne :
    la dimension et la valeur sont créées, la valeur affectée — en UNE Entrée. Avant, rien
    ne partait : il fallait attendre la proposition « ➕ », ou presser Entrée deux fois."""
    m = MONTAGES[montage]
    _semer(atelier, m, m["connue"])
    _ouvrir(page, atelier, m["zone"])
    champ, liste = page.locator(m["champ"]), page.locator(f"{m['liste']} div")
    chemin = _chemin_des_attributs(atelier, m)
    parties = _ecritures(page)

    champ.click()
    expect(liste).to_have_count(1, timeout=15000)    # le vocabulaire est lu : une valeur, pas celle-ci
    Retenue(page, LECTURE_VALEURS)                   # la proposition « ➕ » n'arrivera pas par le réseau
    saisie = f"{m['dimension']} : {m['autre']}"
    champ.press_sequentially(saisie, delay=0)
    with page.expect_request(_est("POST", "/api/attributs/dimensions")) as axe, \
            page.expect_request(lambda r: r.method == "POST" and r.url.endswith("/valeurs")) as valeur, \
            page.expect_request(_est("PUT", chemin)) as pose, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    assert axe.value.post_data_json == {"cible": m["cible"], "nom": m["dimension"]}
    assert valeur.value.post_data_json == {"valeur": m["autre"]}
    cree = next(i for d, v, i in _valeurs_avec_id(atelier, m) if v == m["autre"])
    assert pose.value.post_data_json == {"valeur_id": cree}
    assert len(parties) == 3, f"une Entrée, trois écritures attendues : {parties}"
    assert _poses(atelier, m) == [(m["dimension"], m["autre"])]
    expect(champ).to_have_value("")


def _valeurs_avec_id(decor, m):
    with _api(decor) as c:
        return [(v["dimension"], v["valeur"], v["id"])
                for v in c.get(f"/api/attributs/valeurs?cible={m['cible']}").json()]


@pytest.mark.parametrize("montage", list(MONTAGES))
def test_la_forme_complete_d_une_valeur_connue_la_prend_sans_rien_creer(page, atelier, montage):
    """La valeur existe : la forme complète, tapée avant le retour de la liste et sans
    égard à la casse, AFFECTE la valeur existante — une écriture, la même que le geste
    lent. Deux valeurs sont au vocabulaire, pour que « un seul résultat » n'explique rien."""
    m = MONTAGES[montage]
    ids = _semer(atelier, m, m["connue"], m["autre"])
    _ouvrir(page, atelier, m["zone"])
    champ, liste = page.locator(m["champ"]), page.locator(f"{m['liste']} div")
    chemin = _chemin_des_attributs(atelier, m)
    parties = _ecritures(page)

    champ.click()
    expect(liste).to_have_count(2, timeout=15000)
    Retenue(page, LECTURE_VALEURS)
    champ.press_sequentially(f"{m['dimension'].capitalize()} : {m['connue'].upper()}", delay=0)
    with page.expect_request(_est("PUT", chemin)) as pose, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    assert pose.value.post_data_json == {"valeur_id": ids[m["connue"]]}
    assert len(parties) == 1, f"la valeur existait : une seule écriture attendue, pas {parties}"
    assert _poses(atelier, m) == [(m["dimension"], m["connue"])]
    assert len(_vocabulaire(atelier, m)) == 2        # rien n'a été créé à côté


def test_la_forme_complete_sans_espaces_prend_la_valeur_connue(page, atelier):
    """« lieu:falaise », sans espaces autour des deux-points, désigne « lieu : falaise ».

    Trouvé en écrivant le correctif, et antérieur à lui : la valeur exacte se cherchait
    dans la LISTE, qui est filtrée sur le texte tapé — « lieu : falaise » ne contient pas
    « lieu:falaise » —, et la création n'était pas proposée puisque la valeur existe.
    Entrée ne faisait donc rien, même tapé lentement. Geste lent, aucune retenue."""
    m = MONTAGES["situation"]
    ids = _semer(atelier, m, m["connue"], m["autre"])
    _ouvrir(page, atelier, m["zone"])
    champ = page.locator(m["champ"])
    chemin = _chemin_des_attributs(atelier, m)
    parties = _ecritures(page)

    champ.click()
    expect(page.locator(f"{m['liste']} div")).to_have_count(2, timeout=15000)
    with page.expect_response(lambda r: LECTURE_VALEURS.search(r.url) is not None):
        champ.press_sequentially(f"{m['dimension']}:{m['connue']}", delay=20)   # la lecture différée revient
    page.wait_for_timeout(200)
    with page.expect_request(_est("PUT", chemin)) as pose, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    assert pose.value.post_data_json == {"valeur_id": ids[m["connue"]]}
    assert len(parties) == 1, parties
    assert _poses(atelier, m) == [(m["dimension"], m["connue"])]


@pytest.mark.parametrize("montage", ["situation", "profil-par-le-locuteur"])
def test_avant_toute_lecture_la_forme_complete_prend_quand_meme_la_valeur_existante(
        page, atelier, montage):
    """AUCUNE lecture du vocabulaire n'est encore revenue — pas même celle du focus — et
    l'on tape la forme complète d'une valeur qui existe : l'écran ne peut pas le savoir,
    il passe par la création, et c'est le serveur qui retrouve la valeur. Elle est
    affectée, rien n'est dédoublé."""
    m = MONTAGES[montage]
    ids = _semer(atelier, m, m["connue"])
    _ouvrir(page, atelier, m["zone"])
    champ = page.locator(m["champ"])
    chemin = _chemin_des_attributs(atelier, m)
    parties = _ecritures(page)

    lectures = Retenue(page, LECTURE_VALEURS)        # posée AVANT le focus
    champ.click()
    lectures.attendre(1)                             # la lecture du focus est partie, et tenue
    champ.press_sequentially(f"{m['dimension']} : {m['connue']}", delay=0)
    with page.expect_request(_est("PUT", chemin)) as pose, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    assert pose.value.post_data_json == {"valeur_id": ids[m["connue"]]}
    assert [p.split(" ")[0] for p in parties] == ["POST", "POST", "PUT"], parties
    assert _poses(atelier, m) == [(m["dimension"], m["connue"])]
    assert _vocabulaire(atelier, m) == [(m["dimension"], m["connue"])]


@pytest.mark.parametrize("montage", ["situation", "profil-par-la-boite"])
def test_un_seul_resultat_pour_ce_qui_est_tape_entree_le_prend(page, atelier, montage):
    """« Un seul résultat, Entrée le prend » reste — pour CETTE saisie. Deux valeurs au
    vocabulaire ; on tape le début de la seconde, la lecture différée tenue : la liste
    n'attend pas le réseau pour se réduire à elle, et Entrée la prend."""
    m = MONTAGES[montage]
    ids = _semer(atelier, m, m["connue"], m["autre"])
    _ouvrir(page, atelier, m["zone"])
    champ, liste = page.locator(m["champ"]), page.locator(f"{m['liste']} div")
    chemin = _chemin_des_attributs(atelier, m)
    parties = _ecritures(page)

    champ.click()
    expect(liste).to_have_count(2, timeout=15000)
    lectures = Retenue(page, LECTURE_VALEURS)
    champ.press_sequentially(m["debut_autre"], delay=0)
    lectures.attendre(1)                             # la lecture différée est partie : elle est tenue
    # Ce qui s'affiche vaut pour ce qui est tapé, la lecture toujours en vol.
    expect(liste).to_have_count(1)
    expect(liste).to_contain_text(m["autre"])
    with page.expect_request(_est("PUT", chemin)) as pose, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    assert pose.value.post_data_json == {"valeur_id": ids[m["autre"]]}
    assert len(parties) == 1, parties
    assert _poses(atelier, m) == [(m["dimension"], m["autre"])]


def test_une_lecture_arrivee_en_retard_n_ecrase_pas_la_plus_recente(page, atelier):
    """Deux lectures en vol ; la seconde répond d'abord, la première ensuite, avec un
    vocabulaire plus ANCIEN. La liste reste celle de la plus récente, et Entrée décide
    d'après elle.

    Les deux réponses sont FAÇONNÉES par le test, à partir de la vraie : la plus récente
    connaît « phare », la plus ancienne ne le connaît pas encore.
    """
    m = MONTAGES["situation"]
    ids = _semer(atelier, m, m["connue"], m["autre"])
    with _api(atelier) as c:
        vrai = c.get(f"/api/attributs/valeurs?cible={m['cible']}").json()
    ancien = [v for v in vrai if v["valeur"] == m["connue"]]
    assert len(vrai) == 2 and len(ancien) == 1
    _ouvrir(page, atelier, m["zone"])
    champ, liste = page.locator(m["champ"]), page.locator(f"{m['liste']} div")
    chemin = _chemin_des_attributs(atelier, m)

    lectures = Retenue(page, LECTURE_VALEURS)
    champ.click()
    lectures.attendre(1)                                           # la lecture du focus
    champ.press_sequentially(m["debut_autre"], delay=0)
    premiere, seconde = lectures.attendre(2)                       # + la lecture différée

    _repondre(page, seconde, vrai)
    expect(liste).to_have_count(1, timeout=15000)
    expect(liste).to_contain_text(m["autre"])
    _repondre(page, premiere, ancien)                              # la plus lente, plus ancienne
    page.wait_for_timeout(400)                                     # l'écran a eu le temps de la traiter
    expect(liste).to_have_count(1)
    expect(liste).to_contain_text(m["autre"])

    with page.expect_request(_est("PUT", chemin)) as pose:
        champ.press("Enter")
    assert pose.value.post_data_json == {"valeur_id": ids[m["autre"]]}


@pytest.mark.parametrize("montage,saisie,vocabulaire", [
    ("situation", "falaise", ()),                    # le retour d'usage : un mot seul
    ("profil-par-le-locuteur", "soutenu", ()),
    ("profil-par-la-boite", "soutenu", ()),
    ("situation", "lieu :", ("falaise",)),           # la forme, incomplète
    ("situation", "l", ("falaise", "phare")),        # plusieurs propositions, aucune choisie
])
def test_entree_sans_effet_dit_ce_qui_manque(page, atelier, montage, saisie, vocabulaire):
    """Champ rempli, Entrée ne fait rien : l'écran le DIT, là où un lecteur d'écran
    l'entend. Avant, « falaise » tapé seul restait dans le champ sans requête ni message.
    Geste LENT : la liste est revenue, ce n'est pas une affaire de course."""
    m = MONTAGES[montage]
    if vocabulaire:
        _semer(atelier, m, *vocabulaire)
    _ouvrir(page, atelier, m["zone"])
    champ = page.locator(m["champ"])
    parties = _ecritures(page)

    champ.click()
    with page.expect_response(lambda r: LECTURE_VALEURS.search(r.url) is not None):
        champ.press_sequentially(saisie, delay=20)
    page.wait_for_timeout(200)
    expect(page.locator("#toasts .toast")).to_have_count(0)        # rien n'est dit avant Entrée
    champ.press("Enter")

    _entree_traitee(page, parties)
    assert parties == [], f"Entrée devait ne rien faire, et le dire : elle a écrit {parties}"
    message = _message(page)
    expect(message).to_be_visible()
    # Reçu par un lecteur d'écran : le message vit dans une région d'annonce.
    region = page.locator('[role="status"][aria-live="polite"]', has=page.locator(
        ".toast", has_text=re.compile(r"dimension\s:\svaleur")))
    expect(region).to_have_count(1)
    assert parties == [], parties
    assert _poses(atelier, m) == []
    expect(champ).to_have_value(saisie)


def test_apres_un_choix_la_fleche_ne_rouvre_pas_la_liste_de_la_saisie_d_avant(page, atelier):
    """Une valeur vient d'être posée, le champ est vide : ↓ propose ce qui vaut pour un
    champ vide — tout le vocabulaire —, pas la liste de la saisie qu'on vient de valider."""
    m = MONTAGES["situation"]
    ids = _semer(atelier, m, m["connue"], m["autre"])
    _ouvrir(page, atelier, m["zone"])
    champ, liste = page.locator(m["champ"]), page.locator(f"{m['liste']} div")
    chemin = _chemin_des_attributs(atelier, m)

    champ.click()
    expect(liste).to_have_count(2, timeout=15000)
    # Plus aucune lecture ne reviendra : ce que ↓ montrera, l'écran l'aura calculé LUI-MÊME
    # en vidant le champ. Sans cela la lecture différée de « ph », revenue après le choix,
    # refait la liste pour le champ vide, et le test passe sans rien avoir éprouvé (mesuré :
    # le mutant qui retire ce calcul lui survivait).
    Retenue(page, LECTURE_VALEURS)
    champ.press_sequentially(m["debut_autre"], delay=20)
    expect(liste).to_have_count(1, timeout=15000)
    with page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    expect(page.locator("#sit-current .tag-chip")).to_have_count(1, timeout=15000)
    expect(page.locator(m["liste"])).to_be_hidden()

    champ.press("ArrowDown")
    expect(page.locator(m["liste"])).to_be_visible()
    expect(liste).to_have_count(2)
    expect(page.locator(f"{m['liste']} div.active")).to_contain_text(m["connue"])
    with page.expect_request(_est("PUT", chemin)) as pose:
        champ.press("Enter")
    assert pose.value.post_data_json == {"valeur_id": ids[m["connue"]]}


def test_les_fleches_le_clic_et_echap_font_ce_qu_ils_faisaient(page, atelier):
    """Ce qui ne devait PAS changer : la sélection aux flèches puis Entrée, le clic sur une
    proposition, Échap. Gestes lents, la liste revenue."""
    m = MONTAGES["situation"]
    ids = _semer(atelier, m, m["connue"], m["autre"])
    _ouvrir(page, atelier, m["zone"])
    champ, liste = page.locator(m["champ"]), page.locator(f"{m['liste']} div")
    chemin = _chemin_des_attributs(atelier, m)
    parties = _ecritures(page)

    # Les flèches, puis Entrée : la proposition MONTRÉE comme active part, pas la saisie.
    champ.click()
    expect(liste).to_have_count(2, timeout=15000)
    with page.expect_response(lambda r: LECTURE_VALEURS.search(r.url) is not None):
        champ.press_sequentially(m["dimension"], delay=20)
    expect(liste).to_have_count(2)
    champ.press("ArrowDown")
    champ.press("ArrowDown")
    expect(page.locator(f"{m['liste']} div.active")).to_contain_text(m["autre"])
    with page.expect_request(_est("PUT", chemin)) as pose, \
            page.expect_response(_est("PUT", chemin)):
        champ.press("Enter")
    assert pose.value.post_data_json == {"valeur_id": ids[m["autre"]]}
    expect(champ).to_have_value("")

    # Le clic sur une proposition.
    champ.press_sequentially(m["dimension"], delay=20)
    expect(liste).to_have_count(2, timeout=15000)
    with page.expect_request(_est("PUT", chemin)) as pose, \
            page.expect_response(_est("PUT", chemin)):
        liste.filter(has_text=m["connue"]).click()
    assert pose.value.post_data_json == {"valeur_id": ids[m["connue"]]}
    expect(page.locator("#sit-current .tag-chip")).to_have_count(2, timeout=15000)

    # Échap : la liste se ferme, la saisie reste, rien ne part.
    avant = list(parties)
    champ.press_sequentially("li", delay=20)
    expect(page.locator(m["liste"])).to_be_visible(timeout=15000)
    champ.press("Escape")
    expect(page.locator(m["liste"])).to_be_hidden()
    expect(champ).to_have_value("li")
    assert parties == avant and len(avant) == 2, parties


def test_l_attribut_va_a_la_cible_du_geste_meme_si_l_on_en_change(page, atelier):
    """Créer la dimension puis la valeur prend deux écritures : si l'on sélectionne une
    autre région entre-temps, l'affectation revient quand même à la case où Entrée a été
    pressée. Elle partait vers la cible du MOMENT — ici une bulle, qui n'a pas de
    situation : « PUT null/attributs »."""
    m = MONTAGES["situation"]
    _ouvrir(page, atelier, m["zone"])
    champ = page.locator(m["champ"])
    chemin = _chemin_des_attributs(atelier, m)
    vues = []
    page.on("request", lambda r: vues.append(f"{r.method} {r.url}"))

    champ.click()
    creations = Retenue(page, re.compile(r"/api/attributs/dimensions$"), methode="POST")
    champ.press_sequentially(f"{m['dimension']} : {m['autre']}", delay=0)
    champ.press("Enter")
    creations.attendre(1)                            # la création est en vol

    _noeud(page, atelier["bulle"]).click()           # on part sur une bulle
    expect(page.locator("#region-type")).to_have_value("bulle", timeout=15000)
    expect(page.locator("#situation-section")).to_be_hidden()

    with page.expect_request(_est("PUT", chemin)), \
            page.expect_response(_est("PUT", chemin)) as reponse:
        creations.relacher()
    assert reponse.value.status == 200, reponse.value.text()
    page.wait_for_timeout(300)
    assert not [v for v in vues if "null" in v], vues
    assert _poses(atelier, m) == [(m["dimension"], m["autre"])]


# --------------------------------------------------------------------------- #
# Le champ de personnage — Entrée prend l'homonyme exact avant de créer
# --------------------------------------------------------------------------- #
# Même cause, autre conséquence. Le locuteur d'une zone et l'identité d'une boîte se
# choisissent dans le registre, dont la liste dépend de la saisie CÔTÉ SERVEUR (`?q=`).
# Entrée y cherchait l'homonyme exact telle qu'elle était, et créait faute de l'y trouver :
# « Zed » existant, tapé vite, devenait un SECOND « Zed », aussitôt attribué (reproduit le
# 2026-10-12, quatorze personnages au registre). Le serveur ne pose aucune unicité — la
# série distingue des homonymes légitimes —, donc rien ne rattrape l'écran.
#
# La lecture du registre est tenue en vol comme plus haut. Là où il faut qu'Entrée précède
# jusqu'à la lecture différée elle-même, la frappe et Entrée sont émises dans la même
# tâche du navigateur (`_taper_et_valider_d_un_trait`) : les 200 ms ne peuvent pas
# s'écouler entre les deux.

# Les deux montages du champ de personnage.
CHAMPS_PERSONNAGE = {
    "locuteur": {"zone": "bulle", "champ": "#loc-input", "liste": "#loc-suggest",
                 "lien": "locuteur", "puce": "#loc-current .tag-chip"},
    "boite-personnage": {"zone": "personnage", "champ": "#perso-input", "liste": "#perso-suggest",
                         "lien": "personnage", "puce": "#perso-current .tag-chip"},
}

LECTURE_REGISTRE = re.compile(r"/api/personnages\?q=")


def _registre(decor):
    with _api(decor) as c:
        return c.get("/api/personnages").json()


def _lie(decor, rid, lien):
    with _api(decor) as c:
        return c.get(f"/api/regions/{rid}/{lien}").json()[lien]


_D_UN_TRAIT = """([selecteur, texte]) => {
  const champ = document.querySelector(selecteur);
  champ.value = texte;
  champ.dispatchEvent(new Event('input', { bubbles: true }));
  champ.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
}"""


def _taper_et_valider_d_un_trait(page, selecteur, texte):
    """La frappe et Entrée dans la MÊME tâche du navigateur.

    Le champ arme une lecture 200 ms après la frappe. Pour éprouver ce qu'Entrée décide
    AVANT qu'elle parte, il ne suffit pas de taper vite : rien ne garantit qu'un poste
    chargé enchaîne deux appels en moins de 200 ms. Ici les deux évènements que le champ
    écoute (`input`, puis `keydown`) sont émis l'un derrière l'autre, sans rendre la main.
    Le champ doit avoir le focus : on y a cliqué avant.
    """
    page.evaluate(_D_UN_TRAIT, [selecteur, texte])


def _peupler(decor, *noms):
    """Ajoute des personnages au registre ; rend {nom: id}."""
    with _api(decor, ecriture=True) as c:
        return {n: c.post("/api/personnages", json={"nom": n}).json()["id"] for n in noms}


def _creations(parties):
    return [p for p in parties if p.startswith("POST /api/personnages ")]


FIGURANTS = [f"Figurant {k:02d}" for k in range(12)]


@pytest.mark.parametrize("champ_de", list(CHAMPS_PERSONNAGE))
@pytest.mark.parametrize("moment", ["lecture en vol", "avant la lecture"])
def test_un_nom_existant_tape_avant_la_liste_prend_l_homonyme(page, atelier, champ_de, moment):
    """Quatorze personnages au registre, « Zed » le dernier : la liste du champ vide en
    montre dix, pas lui. On tape « Zed » et Entrée avant que SA liste ne revienne : c'est
    le « Zed » existant qui est pris. Avant, un SECOND « Zed » était créé, puis attribué.

    Deux moments, parce que l'écran ne fait pas la même chose : la lecture différée déjà
    partie, Entrée attend CELLE-LÀ (aucune lecture de plus) ; Entrée avant elle, l'écran
    relit lui-même le registre pour ce nom.
    """
    c = CHAMPS_PERSONNAGE[champ_de]
    zed = _peupler(atelier, *FIGURANTS, "Zed")["Zed"]
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    expect(liste).to_have_count(10, timeout=15000)   # la liste du champ vide : dix, sans « Zed »
    expect(liste.filter(has_text="Zed")).to_have_count(0)

    lectures = Retenue(page, LECTURE_REGISTRE)
    if moment == "lecture en vol":
        champ.press_sequentially("Zed", delay=0)
        lectures.attendre(1)                         # la lecture différée de « Zed », tenue
        champ.press("Enter")
    else:
        _taper_et_valider_d_un_trait(page, c["champ"], "Zed")
        lectures.attendre(1)                         # la relecture d'Entrée, tenue
    page.wait_for_timeout(500)
    # UNE lecture pour ce nom, pas deux. (Entrée pressée avant la lecture différée, celle-ci
    # ne part plus du tout depuis ANN-8 : Entrée décide sur sa propre lecture, et la liste
    # différée aurait rouvert par-dessus celle des homonymes.)
    pour_ce_nom = [r.request.url for r in lectures.tenues if r.request.url.endswith("?q=Zed")]
    assert len(pour_ce_nom) == 1, [r.request.url for r in lectures.tenues]
    assert parties == [], f"l'écran a écrit sans attendre de savoir : {parties}"
    expect(champ).to_have_value("")                  # une seconde Entrée ne repartirait pas

    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        lectures.relacher()
    assert reponse.value.status == 200, reponse.value.text()
    assert envoi.value.post_data_json == {"personnage_id": zed}
    expect(page.locator(c["puce"])).to_contain_text("Zed", timeout=15000)
    assert _creations(parties) == [], f"un homonyme a été créé : {parties}"
    assert [p["nom"] for p in _registre(atelier)].count("Zed") == 1
    assert _lie(atelier, rid, c["lien"])["id"] == zed
    if moment == "lecture en vol":
        # La liste de « Zed », revenue après le geste, ne se rouvre pas sur un champ vidé.
        page.wait_for_timeout(300)
        expect(page.locator(c["liste"])).to_be_hidden()


def test_l_homonyme_au_dela_des_dix_propositions_est_pris_meme_tape_lentement(page, atelier):
    """Douze personnages dont le nom contient « zed » : la liste en montre dix, et « Zed »,
    le dernier dans l'ordre du registre, n'en est pas — ni lui, ni « Créer », puisqu'il
    existe. Entrée, tapé LENTEMENT, le prend. Avant, l'homonyme se cherchait dans les dix
    propositions affichées : Entrée en créait un second."""
    c = CHAMPS_PERSONNAGE["locuteur"]
    ids = _peupler(atelier, *[f"Azed {k:02d}" for k in range(11)], "Zed")
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=zed")):
        champ.press_sequentially("zed", delay=20)
    expect(liste).to_have_count(10, timeout=15000)
    expect(liste.filter(has_text=re.compile(r"^Zed$"))).to_have_count(0)
    expect(liste.filter(has_text="Créer")).to_have_count(0)

    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    assert envoi.value.post_data_json == {"personnage_id": ids["Zed"]}
    assert _creations(parties) == [], parties
    assert len(_registre(atelier)) == 13             # Tintin, onze « Azed », « Zed »


def test_une_lecture_du_registre_en_echec_ne_cree_personne(page, atelier):
    """Le registre ne répond pas pour ce nom : l'écran ne sait pas s'il existe. Il ne
    propose pas de le créer, et Entrée ne le crée pas — la saisie revient, avec un message.
    Avant, une lecture en échec valait un registre vide : Entrée créait."""
    c = CHAMPS_PERSONNAGE["locuteur"]
    _peupler(atelier, "Zed")
    _ouvrir(page, atelier, c["zone"])
    champ = page.locator(c["champ"])
    parties = _ecritures(page)

    champ.click()
    expect(page.locator(f"{c['liste']} div")).to_have_count(2, timeout=15000)   # Tintin, Zed

    def en_panne(route):
        route.fulfill(status=500, content_type="application/json",
                      body=json.dumps({"detail": "Registre en panne pour le test."}))
    page.route(re.compile(r"/api/personnages\?q=Zed$"), en_panne)
    with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=Zed")) as lecture:
        champ.press_sequentially("Zed", delay=20)
    assert lecture.value.status == 500
    expect(page.locator(c["liste"])).to_be_hidden(timeout=15000)   # rien n'est proposé, pas même « Créer »

    champ.press("Enter")
    expect(page.locator("#toasts .toast.error", has_text="Registre en panne pour le test")
           ).to_be_visible(timeout=15000)
    expect(champ).to_have_value("Zed")
    assert parties == [], f"l'écran a écrit sans avoir pu lire le registre : {parties}"
    assert [p["nom"] for p in _registre(atelier)].count("Zed") == 1


def test_une_lecture_du_registre_arrivee_en_retard_n_ecrase_pas_la_plus_recente(page, atelier):
    """Deux lectures du registre en vol pour la MÊME saisie ; la seconde répond d'abord,
    la première ensuite, avec un registre plus ANCIEN — où « Zed » n'existait pas encore.
    La liste reste celle de la plus récente, et Entrée prend « Zed » au lieu d'en créer un.

    La seconde lecture est celle du focus : on quitte le champ et on y revient, la saisie
    intacte. Les deux réponses sont façonnées par le test à partir de la vraie.
    """
    c = CHAMPS_PERSONNAGE["locuteur"]
    zed = _peupler(atelier, "Zed")["Zed"]
    with _api(atelier) as client:
        vrai = client.get("/api/personnages?q=Zed").json()
    assert [p["id"] for p in vrai] == [zed]
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    expect(liste).to_have_count(2, timeout=15000)                  # Tintin, Zed
    lectures = Retenue(page, LECTURE_REGISTRE)
    champ.press_sequentially("Zed", delay=0)
    lectures.attendre(1)                                           # la lecture différée
    page.locator("#note-input").click()                            # on quitte le champ…
    champ.click()                                                  # … et on y revient
    premiere, seconde = lectures.attendre(2)
    assert all(r.request.url.endswith("?q=Zed") for r in (premiere, seconde))
    expect(champ).to_have_value("Zed")

    _repondre(page, seconde, vrai)
    expect(liste).to_have_count(1, timeout=15000)
    expect(liste).to_have_text("Zed")
    _repondre(page, premiere, [])                                  # la plus lente, plus ancienne
    page.wait_for_timeout(400)                                     # l'écran a eu le temps de la traiter
    expect(liste).to_have_count(1)
    expect(liste).to_have_text("Zed")                              # pas « ➕ Créer « Zed » »

    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)):
        champ.press("Enter")
    assert envoi.value.post_data_json == {"personnage_id": zed}
    assert _creations(parties) == [], parties


def test_un_nom_qu_on_vient_de_creer_retape_aussitot_n_est_pas_cree_deux_fois(page, atelier):
    """On crée « Zed » à la volée (geste lent : la liste propose « Créer »), puis on le
    retape aussitôt, Entrée avant toute nouvelle lecture. Ce que l'écran savait de « Zed »
    date d'AVANT sa création : il relit le registre, et prend celui qu'il vient de créer."""
    c = CHAMPS_PERSONNAGE["locuteur"]
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    champ.press_sequentially("Zed", delay=20)
    expect(liste.filter(has_text="Créer")).to_be_visible(timeout=15000)
    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)):
        champ.press("Enter")
    zed = envoi.value.post_data_json["personnage_id"]
    expect(page.locator(c["puce"])).to_contain_text("Zed", timeout=15000)
    assert len(_creations(parties)) == 1

    lectures = Retenue(page, LECTURE_REGISTRE)
    _taper_et_valider_d_un_trait(page, c["champ"], "Zed")
    lectures.attendre(1)                             # l'écran RELIT : il ne se fie pas à l'ancien savoir
    assert lectures.tenues[0].request.url.endswith("?q=Zed"), (
        "l'écran n'a pas relu le registre pour « Zed » avant de décider — lectures tenues : "
        f"{[r.request.url for r in lectures.tenues]}, écritures : {parties}")
    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        lectures.relacher()
    assert reponse.value.status == 200, reponse.value.text()
    assert envoi.value.post_data_json == {"personnage_id": zed}
    assert len(_creations(parties)) == 1, f"« Zed » a été créé deux fois : {parties}"
    assert [p["nom"] for p in _registre(atelier)].count("Zed") == 1


def test_le_locuteur_va_a_la_zone_du_geste_meme_si_l_on_en_change(page, atelier):
    """Relire le registre prend du temps : si l'on sélectionne une autre zone entre-temps,
    le locuteur revient à la bulle où Entrée a été pressée — pas au cartouche où l'on est
    arrivé."""
    c = CHAMPS_PERSONNAGE["locuteur"]
    zed = _peupler(atelier, *FIGURANTS, "Zed")["Zed"]
    bulle, cartouche = atelier["bulle"], atelier["cartouche"]
    chemin = f"/api/regions/{bulle}/locuteur"
    _ouvrir(page, atelier, "bulle")
    champ = page.locator(c["champ"])
    parties = _ecritures(page)

    champ.click()
    expect(page.locator(f"{c['liste']} div")).to_have_count(10, timeout=15000)
    lectures = Retenue(page, LECTURE_REGISTRE)
    champ.press_sequentially("Zed", delay=0)
    lectures.attendre(1)
    champ.press("Enter")

    _noeud(page, cartouche).click()                  # on part sur le cartouche
    expect(page.locator("#region-type")).to_have_value("cartouche", timeout=15000)
    expect(champ).to_have_accessible_name(re.compile("cartouche"))

    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        lectures.relacher()
    assert reponse.value.status == 200, reponse.value.text()
    assert envoi.value.post_data_json == {"personnage_id": zed}
    page.wait_for_timeout(300)
    assert [p for p in parties if p.startswith("PUT ")] == [
        f"PUT {chemin} " + json.dumps({"personnage_id": zed}, separators=(",", ":"))], parties
    assert _lie(atelier, bulle, "locuteur")["id"] == zed
    assert _lie(atelier, cartouche, "locuteur") is None
    # L'écran, lui, montre toujours le cartouche — sans locuteur.
    expect(page.locator("#loc-current")).to_contain_text("Aucun locuteur")


# --------------------------------------------------------------------------- #
# ANN-8 — après une validation, UNE flèche surligne une proposition
# --------------------------------------------------------------------------- #
# La première ↓ rouvrait la liste sans rien surligner, et il en fallait une seconde : la
# flèche comptait les lignes restées dans le DOM de la liste PRÉCÉDENTE — vide quand elle
# n'avait rien proposé. Chaque test valide d'abord une saisie qui ne laissait AUCUNE ligne,
# puis presse ↓ une seule fois.
def test_apres_une_forme_complete_sans_espaces_une_fleche_surligne(page, atelier):
    m = MONTAGES["situation"]
    _semer(atelier, m, m["connue"], m["autre"])
    _ouvrir(page, atelier, m["zone"])
    champ, liste = page.locator(m["champ"]), page.locator(f"{m['liste']} div")
    chemin = _chemin_des_attributs(atelier, m)

    champ.click()
    expect(liste).to_have_count(2, timeout=15000)
    # « lieu:falaise » : la liste filtrée sur le texte n'a rien, la forme complète aboutit.
    champ.press_sequentially(f"{m['dimension']}:{m['connue']}", delay=20)
    expect(page.locator(m["liste"])).to_be_hidden()
    with page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    expect(champ).to_have_value("")

    champ.press("ArrowDown")
    expect(page.locator(m["liste"])).to_be_visible()
    expect(page.locator(f"{m['liste']} div.active")).to_have_count(1)
    expect(page.locator(f"{m['liste']} div.active")).to_contain_text(m["connue"])


def test_apres_un_tag_neuf_une_fleche_surligne(page, atelier):
    with _api(atelier, ecriture=True) as c:
        rep = c.put(f"/api/regions/{atelier['cartouche']}/annotation",
                    json={"tags": ["emotion", "colere"]})
        assert rep.status_code == 200, rep.text
    _ouvrir(page, atelier, "bulle")
    champ, liste = page.locator("#tag-input"), page.locator("#tag-suggest div")
    champ.click()
    expect(liste).to_have_count(2, timeout=15000)
    champ.press_sequentially("inedit", delay=20)       # aucune proposition : la liste se vide
    expect(page.locator("#tag-suggest")).to_be_hidden()
    champ.press("Enter")
    expect(page.locator("#tag-chips .tag-chip", has_text="inedit")).to_be_visible()
    expect(champ).to_have_value("")

    champ.press("ArrowDown")
    expect(page.locator("#tag-suggest")).to_be_visible()
    expect(page.locator("#tag-suggest div.active")).to_have_count(1)


def test_apres_une_creation_de_personnage_une_fleche_surligne_le_registre(page, atelier):
    """Le champ du locuteur vient de créer « Zed » : la première ↓ relit le registre pour
    le champ vide et en surligne la première entrée — jamais « Créer « Zed » », la ligne
    restée de la liste d'avant, qui aurait créé un second « Zed »."""
    c = CHAMPS_PERSONNAGE["locuteur"]
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    champ.press_sequentially("Zed", delay=20)
    expect(liste.filter(has_text="Créer")).to_be_visible(timeout=15000)
    with page.expect_response(_est("PUT", chemin)):
        champ.press("Enter")
    expect(champ).to_have_value("")

    champ.press("ArrowDown")
    actif = page.locator(f"{c['liste']} div.active")
    expect(actif).to_have_count(1, timeout=15000)
    expect(actif).not_to_contain_text("Créer")
    expect(liste).to_have_count(2)                   # Tintin, Zed : le registre du champ vide
    assert len(_creations(parties)) == 1, parties


# --------------------------------------------------------------------------- #
# ANN-8 — les deux champs de personnage savent ce que l'autre vient de créer
# --------------------------------------------------------------------------- #
def test_un_nom_cree_par_l_autre_champ_n_est_pas_cree_deux_fois(page, atelier):
    """Rapporté par l'auteur du correctif du 2026-10-13, rejoué ici : « Zed » est cherché
    dans le champ du locuteur (sa liste dit « Créer »), puis créé par la boîte personnage ;
    de retour sur la bulle, « Zed » tapé d'un trait se décidait sur la liste du locuteur —
    celle d'AVANT la création — et en créait un second. Le registre est tenu en vol au
    retour sur la bulle : rien d'autre que ce que le champ savait ne peut décider."""
    loc, boite = CHAMPS_PERSONNAGE["locuteur"], CHAMPS_PERSONNAGE["boite-personnage"]
    bulle = atelier["bulle"]
    chemin = f"/api/regions/{bulle}/locuteur"
    _ouvrir(page, atelier, "bulle")
    parties = _ecritures(page)

    champ = page.locator(loc["champ"])
    champ.click()
    champ.press_sequentially("Zed", delay=20)
    expect(page.locator(f"{loc['liste']} div").filter(has_text="Créer")).to_be_visible(timeout=15000)

    # La boîte personnage crée « Zed ».
    _noeud(page, atelier["personnage"]).click()
    expect(page.locator("#region-type")).to_have_value("personnage", timeout=15000)
    autre = page.locator(boite["champ"])
    autre.click()
    autre.press_sequentially("Zed", delay=20)
    expect(page.locator(f"{boite['liste']} div").filter(has_text="Créer")).to_be_visible(timeout=15000)
    with page.expect_response(_est("PUT", f"/api/regions/{atelier['personnage']}/personnage")):
        autre.press("Enter")
    assert len(_creations(parties)) == 1, parties
    zed = [p for p in _registre(atelier) if p["nom"] == "Zed"][0]["id"]

    # Retour sur la bulle : le registre ne répond plus tant que le test ne le relâche pas.
    _noeud(page, bulle).click()
    expect(page.locator("#region-type")).to_have_value("bulle", timeout=15000)
    lectures = Retenue(page, LECTURE_REGISTRE)
    champ.click()
    _taper_et_valider_d_un_trait(page, loc["champ"], "Zed")
    page.wait_for_timeout(500)
    assert len(_creations(parties)) == 1, f"« Zed » recréé d'après la liste d'avant : {parties}"
    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        lectures.relacher()
    assert reponse.value.status == 200, reponse.value.text()
    assert envoi.value.post_data_json == {"personnage_id": zed}
    assert len(_creations(parties)) == 1, parties
    assert [p["nom"] for p in _registre(atelier)].count("Zed") == 1


# --------------------------------------------------------------------------- #
# ANN-8 (Hugo, 2026-10-21) — ↓ puis Entrée pendant que la liste se recharge
# --------------------------------------------------------------------------- #
# Entre une frappe et le retour de sa liste, la liste à l'écran est celle de la saisie
# d'AVANT. ↓ y surligne une ligne ; Entrée la prenait. Elle la revérifie désormais contre
# ce qui est tapé : la surlignée part si elle y répond encore, et sinon rien ne part — la
# liste de la saisie arrive, rien de surligné. La lecture est TENUE en vol : « pendant le
# rechargement » ne dépend d'aucune vitesse.
@pytest.mark.parametrize("fleches,part", [(1, "Zed"), (2, None)],
                         ids=["la-surlignee-repond-encore", "la-surlignee-ne-repond-plus"])
def test_pendant_le_rechargement_entree_reverifie_la_surlignee(page, atelier, fleches, part):
    c = CHAMPS_PERSONNAGE["locuteur"]
    ids = _peupler(atelier, "Zed", "Zelda")
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=Ze")):
        champ.press_sequentially("Ze", delay=20)
    expect(liste).to_have_count(3, timeout=15000)          # Zed, Zelda, Créer « Ze »

    lectures = Retenue(page, LECTURE_REGISTRE)
    champ.press("d")
    lectures.attendre(1)                                   # la liste de « Zed », tenue
    assert lectures.tenues[0].request.url.endswith("?q=Zed")
    expect(liste).to_have_count(3)                         # à l'écran : celle de « Ze »
    for _ in range(fleches):
        champ.press("ArrowDown")
    surlignee = page.locator(f"{c['liste']} div.active")
    expect(surlignee).to_have_text(re.compile(r"^Zed$" if fleches == 1 else r"^Zelda$"))

    if part:
        with page.expect_request(_est("PUT", chemin)) as envoi, \
                page.expect_response(_est("PUT", chemin)) as reponse:
            champ.press("Enter")
        assert reponse.value.status == 200, reponse.value.text()
        assert envoi.value.post_data_json == {"personnage_id": ids[part]}
        lectures.relacher()
        return

    champ.press("Enter")
    # Le témoin : l'écran a traité Entrée — plus rien n'est surligné, la saisie reste.
    expect(surlignee).to_have_count(0, timeout=15000)
    expect(champ).to_have_value("Zed")
    page.wait_for_timeout(400)
    assert parties == [], f"Entrée a pris une ligne de la liste d'avant : {parties}"
    # Une seule lecture pour « Zed » : celle déjà en vol suffit.
    assert [r.request.url for r in lectures.tenues if r.request.url.endswith("?q=Zed")] == [
        lectures.tenues[0].request.url], [r.request.url for r in lectures.tenues]

    with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=Zed")):
        lectures.relacher()
    expect(liste).to_have_count(1, timeout=15000)          # la liste de « Zed » : lui seul
    expect(liste).to_have_text("Zed")
    expect(surlignee).to_have_count(0)
    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)):
        champ.press("Enter")
    assert envoi.value.post_data_json == {"personnage_id": ids["Zed"]}
    assert _creations(parties) == [], parties


# --------------------------------------------------------------------------- #
# ANN-8 (Hugo, 2026-10-21) — plusieurs personnages du même nom se départagent à l'écran
# --------------------------------------------------------------------------- #
def _deux_zed(decor):
    """Deux « Zed » au registre : l'un sans série, l'autre d'une série. Rend {série: id}."""
    with _api(decor, ecriture=True) as c:
        return {serie: c.post("/api/personnages", json={"nom": "Zed", "serie": serie}).json()["id"]
                for serie in (None, "Les Aventures")}


@pytest.mark.parametrize("champ_de", list(CHAMPS_PERSONNAGE))
@pytest.mark.parametrize("moment", ["liste revenue", "avant la liste"])
def test_des_homonymes_entree_ne_decide_pas_la_liste_se_reduit_a_eux(page, atelier, champ_de, moment):
    """Deux « Zed » : Entrée ne prend plus le premier dans l'ordre du registre. Rien ne part ;
    la liste se réduit aux deux, chacun avec sa série, et l'on choisit — ici le second, aux
    flèches. Deux moments, deux chemins de l'écran : la liste de « Zed » déjà revenue, ou
    Entrée pressée avant elle (l'écran relit le registre lui-même)."""
    c = CHAMPS_PERSONNAGE[champ_de]
    zed = _deux_zed(atelier)
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")
    parties = _ecritures(page)

    champ.click()
    expect(liste).to_have_count(3, timeout=15000)          # Tintin, Zed, Zed
    lues = []                                              # les lectures du registre, dès ici
    page.on("request", lambda r: lues.append(r.url) if LECTURE_REGISTRE.search(r.url) else None)
    if moment == "liste revenue":
        with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=Zed")):
            champ.press_sequentially("Zed", delay=20)
        expect(liste).to_have_count(2, timeout=15000)
        champ.press("Enter")
    else:
        with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=Zed")):
            _taper_et_valider_d_un_trait(page, c["champ"], "Zed")

    # Le témoin : la liste réduite, chaque ligne avec sa série — « sans série » comprise.
    expect(liste).to_have_count(2, timeout=15000)
    expect(liste.nth(0)).to_have_text(re.compile(r"^Zed\s*sans série$"))
    expect(liste.nth(1)).to_have_text(re.compile(r"^Zed\s*Les Aventures$"))
    expect(page.locator(f"{c['liste']} div.active")).to_have_count(0)
    expect(champ).to_have_value("Zed")
    page.wait_for_timeout(400)
    assert parties == [], f"Entrée a décidé entre deux homonymes : {parties}"
    # Et la liste réduite RESTE : aucune lecture de plus ne la recouvre de la liste entière.
    # Entrée d'un trait, la lecture différée de la frappe était encore armée — partie après
    # Entrée, elle rouvrait toute la liste par-dessus celle des homonymes.
    assert len(lues) == 1 and lues[0].endswith("?q=Zed"), lues
    expect(liste.nth(0)).to_have_text(re.compile(r"^Zed\s*sans série$"))

    # Une seconde Entrée sans rien surligner ne décide pas davantage.
    champ.press("Enter")
    page.wait_for_timeout(300)
    assert parties == [], parties
    expect(liste).to_have_count(2)

    champ.press("ArrowDown")
    champ.press("ArrowDown")
    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)) as reponse:
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    assert envoi.value.post_data_json == {"personnage_id": zed["Les Aventures"]}
    expect(page.locator(c["puce"])).to_contain_text("Les Aventures", timeout=15000)
    assert _creations(parties) == [], parties


def test_un_homonyme_se_choisit_aussi_d_un_clic(page, atelier):
    c = CHAMPS_PERSONNAGE["locuteur"]
    zed = _deux_zed(atelier)
    rid = atelier[c["zone"]]
    chemin = f"/api/regions/{rid}/{c['lien']}"
    _ouvrir(page, atelier, c["zone"])
    champ, liste = page.locator(c["champ"]), page.locator(f"{c['liste']} div")

    champ.click()
    with page.expect_response(lambda r: r.url.endswith("/api/personnages?q=Zed")):
        champ.press_sequentially("Zed", delay=20)
    expect(liste).to_have_count(2, timeout=15000)
    champ.press("Enter")
    expect(liste.nth(0)).to_have_text(re.compile(r"sans série$"), timeout=15000)
    with page.expect_request(_est("PUT", chemin)) as envoi, \
            page.expect_response(_est("PUT", chemin)):
        liste.nth(0).click()
    assert envoi.value.post_data_json == {"personnage_id": zed[None]}
