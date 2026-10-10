"""COL-3, tranche 1 — le projet se VOIT : la bande du haut, la Bibliothèque, l'Administration.

Le projet existe depuis le schéma v29 ; ce module joue ce que l'écran en fait, dans un vrai
navigateur, sur la vraie route. Chaque test vise ce qu'un test d'API ne verrait pas :

- un nom de projet dessiné seulement quand il y a une pastille d'identité — donc jamais en
  mono-poste, où il n'y a personne à nommer et quand même un projet ;
- un sélecteur qui ne change que le nom affiché, la Bibliothèque listant toujours tout ;
- une collection créée dans le projet de repli alors que l'écran en montre un autre ;
- « faire entrer » qui nommerait responsable ;
- un nom rogné, replié, ou sorti de la fenêtre à 320 px sous une grande police.

**Les requêtes PARTIES sont mesurées, pas seulement l'état final.** Relire la base après un
geste prouve qu'il a abouti, jamais par quel chemin : une collection rangée dans le bon
projet par le repli du serveur, un rôle posé par son défaut, passeraient ces relectures-là.

La préférence de police se règle par CDP, donc sous Chromium seulement : sous un autre
navigateur, les tests qui la font varier jouent celle avec laquelle il a été lancé (cf.
`_polices`), et c'est à qui le lance de la faire varier.
"""
import sqlite3
import sys
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import database  # noqa: E402
from conftest import ECRITURE  # noqa: E402
from tools.mesurer_reflow import ECRASEMENT, SONDE, decrire_ecrasement  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — LA liste de cet audit, et elle sert de déclaration : `tests/test_surfaces.py` la
# confronte aux surfaces réellement servies. La bande du haut est la même sur les cinq, et
# c'est justement ce qu'on vérifie : chaque boucle ci-dessous en dérive.
SURFACES_AUDITEES = {
    "/": "Atelier",
    "/recherche": "Recherche",
    "/corpus": "Bibliothèque",
    "/exploration": "Exploration",
    "/administration": "Administration",
}
SURFACES_HORS_PERIMETRE = {}

# Les identités de la doublure de l'annuaire (`tests/doublures/annuaire.json`).
ADMIN_BD = {"Remote-User": "admin-bd", "Remote-Name": "Camille Admin",
            "Remote-Groups": "bd-admins"}
PROPRIO = {"Remote-User": "proprio", "Remote-Name": "Paule Propriétaire",
           "Remote-Groups": "annotateurs"}
LECTRICE = {"Remote-User": "lectrice", "Remote-Name": "Léa Lectrice"}
# La pastille au nom le plus long qu'elle affiche : la bande de production, pas celle du poste.
IDENTITE_LONGUE = {"Remote-User": "camille", "Remote-Name": "Camille Ferreira-Lopes",
                   "Remote-Groups": "bd-admins"}
RETOUR = "retour=%2Frecherche"

# Le nom le plus long qu'un projet puisse porter, deux fois : en capitales — le plus LARGE
# des noms ordinaires — et en minuscules. Ils font exactement le plafond, et c'est vérifié
# ici plutôt que supposé : qui change le plafond doit choisir d'autres témoins, et REMESURER
# la bande (la valeur vient d'une mesure, cf. `database.LONGUEUR_NOM_PROJET`).
NOM_CAPITALES = "CORPUS FRANCO-BELGE 2"
NOM_MINUSCULES = "Séminaire émotions 26"
for _nom in (NOM_CAPITALES, NOM_MINUSCULES):
    assert len(_nom) == database.LONGUEUR_NOM_PROJET, (
        f"« {_nom} » fait {len(_nom)} caractères pour un plafond de "
        f"{database.LONGUEUR_NOM_PROJET} : le témoin ne mesure plus le nom le plus long")

POLICES = (16, 20, 24)
# La police de l'image de production, plus large que celle du poste : forcée sur `body`, dont
# les contrôles de la bande héritent. Absente de la machine, le navigateur retombe sur sa
# police sans empattement, et la mesure reste celle du poste — elle ne s'en trouve pas faussée.
FONTES = (None, '"DejaVu Sans", sans-serif')


# ── Outils ─────────────────────────────────────────────────────────────────────────────

def _api(base, methode, chemin, corps=None, entetes=None):
    """Le décor et la relecture, par l'API, sous l'identité qui monte les décors."""
    with httpx.Client(base_url=base, trust_env=False, timeout=30,
                      headers=entetes or ECRITURE) as c:
        r = c.request(methode, chemin, json=corps)
        assert r.status_code < 300, f"{methode} {chemin} → {r.status_code} {r.text}"
        return r.json() if r.content else None


def _repli(base):
    return next(p for p in _api(base, "GET", "/api/projets") if p["repli"])["id"]


def _projet(base, nom, **champs):
    return _api(base, "POST", "/api/projets", {"nom": nom, **champs})["id"]


def _collection(base, nom, projet_id=None):
    corps = {"nom": nom} if projet_id is None else {"nom": nom, "projet_id": projet_id}
    return _api(base, "POST", "/api/collections", corps)["id"]


def _membre(base, projet_id, principal, role="membre", genre="utilisateur"):
    _api(base, "PUT", f"/api/projets/{projet_id}/membres",
         {"genre": genre, "principal": principal, "role": role})


def _acces(base, collection_id, principal, niveau="lecture", genre="utilisateur"):
    _api(base, "PUT", f"/api/collections/{collection_id}/acces",
         {"genre": genre, "principal": principal, "niveau": niveau})


def _membres(base, projet_id):
    return {(m["genre"], m["principal"]): m["role"]
            for m in _api(base, "GET", f"/api/projets/{projet_id}/membres")}


def _chromium(page):
    return page.context.browser.browser_type.name == "chromium"


def _polices(page):
    """Les préférences de police à jouer : les trois sous Chromium, où CDP les pose ; celle
    du lancement ailleurs (`None` : on ne touche à rien)."""
    return POLICES if _chromium(page) else (None,)


def _preference_police(page, police):
    """Le réglage de police PAR DÉFAUT du navigateur, posé par CDP — le même instrument que
    `test_e2e_police`, recopié pour la raison écrite dans `test_e2e_reflow`."""
    if police is None:
        return
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": police, "fixed": police}})


def _exceptions(page):
    """Les exceptions non rattrapées de la page. Pas ses lignes de console : un 403 attendu
    (la version servie, pour qui n'administre pas) y écrit une erreur de ressource."""
    vues = []
    page.on("pageerror", lambda e: vues.append(str(e)))
    return vues


def _collections_listees(page):
    return page.locator("#col-body details.col-item > summary .col-nom").all_inner_texts()


# Ce que la bande contient, et dans quel ordre.
_BANDE = """() => {
  const nav = document.getElementById('site-nav');
  const enfants = [...nav.children];
  const p = nav.querySelector('.projet-courant');
  const rang = (sel) => enfants.indexOf(nav.querySelector(sel));
  return {
    present: !!p,
    enfantDirect: !!p && p.parentNode === nav,
    texte: p ? p.textContent : null,
    nom: (document.getElementById('projet-nom') || {}).textContent || null,
    choix: !!document.getElementById('projet-choix'),
    pastille: !!nav.querySelector('.user-chip'),
    rangs: { projet: rang('.projet-courant'), pastille: rang('.user-chip'),
             affichage: rang('.display-menu') },
    dansLaNav: !!p && !!p.closest('.surf-nav'),
    estUnLien: !!p && (p.classList.contains('surf-link') || !!p.querySelector('.surf-link')),
    repliable: !!p && (p.hasAttribute('aria-expanded') || !!p.querySelector('[aria-expanded]')),
  };
}"""


# ── La bande du haut, sur les cinq surfaces ────────────────────────────────────────────


@pytest.mark.parametrize("surface", list(SURFACES_AUDITEES))
def test_le_projet_se_lit_sans_identite(page, live_server, surface):
    """En mono-poste il n'y a pas de pastille d'identité, et il y a un projet : son nom se
    lit quand même, sur chaque surface. Un seul projet — donc le nom SEUL, sans sélecteur.

    L'élément est un enfant direct de la bande, hors de la barre de navigation et sans
    `aria-expanded` : des tests comptent les liens de la barre, et un contrôle repliable
    devrait se déclarer à la mesure de reflow."""
    erreurs = _exceptions(page)
    page.goto(live_server + surface, wait_until="networkidle")
    page.locator(".projet-courant").wait_for(timeout=5000)
    b = page.evaluate(_BANDE)
    assert not b["pastille"], "une pastille d'identité en mono-poste : le décor a changé"
    assert b["enfantDirect"] and not b["dansLaNav"] and not b["estUnLien"], b
    assert not b["repliable"], "le projet courant porte un `aria-expanded`"
    assert b["nom"] == database.NOM_PROJET_DEFAUT, b
    assert not b["choix"], "un sélecteur pour un seul projet : il ne choisirait rien"
    assert b["texte"] == "Projet" + database.NOM_PROJET_DEFAUT, b["texte"]
    assert b["rangs"]["projet"] < b["rangs"]["affichage"], b["rangs"]
    assert not erreurs, erreurs


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("surface", list(SURFACES_AUDITEES))
def test_le_projet_se_lit_a_qui_n_y_lit_qu_une_collection(page, live_server, surface):
    """Derrière le proxy, à qui lit une collection SANS être du projet : il en lit le nom,
    à gauche de sa pastille. C'est le seul projet qu'il puisse nommer — celui de repli, où
    il ne lit rien, ne lui est pas montré."""
    pid = _projet(live_server, "Séminaire 2026")
    _acces(live_server, _collection(live_server, "Étude", pid), "lectrice")
    page.set_extra_http_headers(LECTRICE)
    page.goto(live_server + surface, wait_until="networkidle")
    page.locator(".projet-courant").wait_for(timeout=5000)
    page.locator(".user-chip").wait_for(timeout=5000)
    b = page.evaluate(_BANDE)
    assert b["nom"] == "Séminaire 2026" and not b["choix"], b
    r = b["rangs"]
    assert 0 <= r["projet"] < r["pastille"] < r["affichage"], (
        f"ordre de la bande : {r} — le projet se lit avant la pastille, « Aa » en dernier")


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("tardive", ["/api/projets", "/api/moi"])
def test_l_ordre_de_la_bande_ne_depend_pas_de_la_premiere_reponse(page, live_server, tardive):
    """Le projet et la pastille naissent de deux lectures, et rien n'ordonne leurs réponses.
    Quelle que soit la première arrivée, le projet se range AVANT la pastille, et « Aa »
    reste le dernier. Le test du dessus le constate aussi, mais au gré d'une course : ici
    une des deux réponses est RETENUE jusqu'à ce que l'autre ait dessiné."""
    tenues = []
    page.route("**" + tardive, lambda route: tenues.append(route))
    page.set_extra_http_headers(ADMIN_BD)
    page.goto(live_server + "/recherche", wait_until="domcontentloaded")
    premier, second = ((".user-chip", ".projet-courant") if tardive == "/api/projets"
                       else (".projet-courant", ".user-chip"))
    page.locator(premier).wait_for(timeout=5000)
    assert page.locator(second).count() == 0, f"{second} est dessiné avant sa réponse"
    assert tenues, f"aucune lecture de {tardive} n'a été retenue : le test ne mesure rien"
    for route in tenues:
        route.continue_()
    page.locator(second).wait_for(timeout=5000)
    r = page.evaluate(_BANDE)["rangs"]
    assert 0 <= r["projet"] < r["pastille"] < r["affichage"], (
        f"{tardive} arrivée la dernière — ordre de la bande : {r}")


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("surface", list(SURFACES_AUDITEES))
def test_sans_aucun_projet_la_bande_ne_dessine_rien(page, live_server, surface):
    """Un compte identifié qui n'a ni projet ni collection : `GET /api/projets` rend une
    liste VIDE. La bande ne dessine alors ni nom, ni libellé orphelin, ni sélecteur vide —
    et rien ne lève."""
    erreurs = _exceptions(page)
    page.set_extra_http_headers({"Remote-User": "nadia"})
    page.goto(live_server + surface, wait_until="networkidle")
    page.locator(".user-chip").wait_for(timeout=5000)
    # La promesse est celle que la bande attend : une fois rendue ici, la bande a dessiné —
    # son écoute est posée avant celle de cette évaluation.
    assert page.evaluate("() => window.BDProjets") == []
    assert page.locator(".projet-courant, .projet-lbl, #projet-choix, #projet-nom").count() == 0
    assert not erreurs, erreurs


def test_deux_projets_un_selecteur_et_le_choix_tient(page, live_server):
    """Dès deux projets visibles, un `<select>` natif, libellé « Projet ». Ce qu'on y choisit
    est retenu par le NAVIGATEUR : il tient d'une surface à l'autre, et au rechargement."""
    repli = _repli(live_server)
    second = _projet(live_server, "Séminaire 2026")
    premiere = next(iter(SURFACES_AUDITEES))
    page.goto(live_server + premiere, wait_until="networkidle")
    choix = page.locator("#projet-choix")
    choix.wait_for(timeout=5000)
    assert page.locator("#projet-nom").count() == 0
    expect(page.locator('label[for="projet-choix"]')).to_have_text("Projet")
    assert choix.locator("option").all_inner_texts() == [database.NOM_PROJET_DEFAUT,
                                                         "Séminaire 2026"]
    expect(choix).to_have_value(str(repli))           # rien de retenu : le projet de repli
    assert page.evaluate("() => localStorage.getItem('bd-projet')") is None

    choix.select_option(str(second))
    assert page.evaluate("() => localStorage.getItem('bd-projet')") == str(second)
    for surface in SURFACES_AUDITEES:
        page.goto(live_server + surface, wait_until="networkidle")
        expect(page.locator("#projet-choix")).to_have_value(str(second), timeout=5000)
    page.reload(wait_until="networkidle")
    expect(page.locator("#projet-choix")).to_have_value(str(second), timeout=5000)


def test_un_projet_retenu_qui_n_est_plus_visible_rend_la_main_au_repli(page, live_server):
    """Le navigateur a retenu un projet qui n'existe plus : la bande ne s'accroche pas à un
    identifiant mort, elle retombe sur le projet de repli."""
    repli = _repli(live_server)
    _projet(live_server, "Séminaire 2026")
    page.add_init_script("localStorage.setItem('bd-projet', '987654')")
    page.goto(live_server + "/corpus", wait_until="networkidle")
    expect(page.locator("#projet-choix")).to_have_value(str(repli), timeout=5000)
    expect(page.locator("#collections-projet")).to_have_text(
        f"Dans le projet « {database.NOM_PROJET_DEFAUT} »")


# ── La Bibliothèque : le projet courant borne la liste des collections ─────────────────
#
# (La fixture `deux_projets` est définie juste dessous ; le test qui suit s'en passe.)


def test_sans_stockage_le_choix_vaut_pour_la_page_et_rien_ne_leve(page, live_server):
    """Le stockage local refuse tout — navigation privée, réglage du navigateur : lire et
    écrire LÈVENT. Rien n'échoue pour autant : le projet courant est celui de repli, en
    choisir un autre vaut pour la page — la liste de la Bibliothèque suit —, et le choix
    n'est simplement pas retenu au rechargement."""
    repli = _repli(live_server)
    second = _projet(live_server, "Séminaire 2026")
    _collection(live_server, "Corpus de départ")
    _collection(live_server, "Étude des émotions", second)
    erreurs = _exceptions(page)
    page.add_init_script("""
      Storage.prototype.getItem = () => { throw new Error('stockage refusé'); };
      Storage.prototype.setItem = () => { throw new Error('stockage refusé'); };
    """)
    page.goto(live_server + "/corpus", wait_until="networkidle")
    page.locator("#col-body details.col-item").first.wait_for(timeout=5000)
    expect(page.locator("#projet-choix")).to_have_value(str(repli))
    assert _collections_listees(page) == ["Corpus de départ"]

    page.locator("#projet-choix").select_option(str(second))
    expect(page.locator("#collections-projet")).to_have_text(
        "Dans le projet « Séminaire 2026 »")
    expect(page.locator("#col-body details.col-item > summary .col-nom")).to_have_text(
        ["Étude des émotions"])

    page.reload(wait_until="networkidle")
    expect(page.locator("#projet-choix")).to_have_value(str(repli), timeout=5000)
    assert not erreurs, erreurs


@pytest.fixture
def deux_projets(live_server):
    """Mono-poste. Deux collections dans le projet de repli, une dans « Séminaire 2026 »,
    et un troisième projet vide."""
    repli = _repli(live_server)
    second = _projet(live_server, "Séminaire 2026")
    return {"base": live_server, "repli": repli, "second": second,
            "vide": _projet(live_server, "Projet sans rien"),
            "a1": _collection(live_server, "Corpus de départ"),
            "a2": _collection(live_server, "Incubateur", repli),
            "b1": _collection(live_server, "Étude des émotions", second)}


def test_la_bibliotheque_ne_liste_que_les_collections_du_projet_courant(page, deux_projets):
    """La liste est celle du projet courant, et une ligne au-dessus du bloc le nomme. Changer
    de projet dans la bande la redessine SANS recharger la page — une saisie en cours
    ailleurs n'a pas à s'y perdre."""
    d = deux_projets
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    page.locator("#col-body details.col-item").first.wait_for(timeout=5000)
    assert _collections_listees(page) == ["Corpus de départ", "Incubateur"]
    expect(page.locator("#collections-projet")).to_be_visible()
    expect(page.locator("#collections-projet")).to_have_text(
        f"Dans le projet « {database.NOM_PROJET_DEFAUT} »")

    page.evaluate("() => { window.__temoin = 'même page'; }")
    page.locator("#projet-choix").select_option(str(d["second"]))
    expect(page.locator("#collections-projet")).to_have_text(
        "Dans le projet « Séminaire 2026 »")
    expect(page.locator("#col-body details.col-item")).to_have_count(1)
    assert _collections_listees(page) == ["Étude des émotions"]
    assert page.evaluate("() => window.__temoin") == "même page", "la page a été rechargée"

    # Un projet où l'on ne lit rien : la liste le DIT, en le nommant — on lit des
    # collections ailleurs, et l'écran ne doit pas faire croire qu'on a tout perdu.
    page.locator("#projet-choix").select_option(str(d["vide"]))
    note = page.locator("#col-body .col-note")
    expect(note).to_contain_text("Aucune collection ouverte pour vous dans le projet "
                                 "« Projet sans rien »")
    assert _collections_listees(page) == []


def test_creer_une_collection_la_range_dans_le_projet_courant(page, deux_projets):
    """« + Créer » crée dans le projet que la liste montre. C'est la requête PARTIE qu'on
    lit : sans `projet_id`, le serveur rangerait la collection dans le projet de repli, et
    relire la liste d'un projet de repli courant ne verrait rien."""
    d = deux_projets
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    page.locator("#col-body details.col-item").first.wait_for(timeout=5000)

    def creer(nom):
        page.locator("#col-nom").fill(nom)
        with page.expect_request(lambda r: r.method == "POST"
                                 and r.url.endswith("/api/collections")) as partie:
            page.locator("#col-add").click()
        expect(page.locator("#col-creer-msg")).to_contain_text("créée")
        return partie.value.post_data_json

    assert creer("Née dans le repli") == {"nom": "Née dans le repli", "projet_id": d["repli"]}

    page.locator("#projet-choix").select_option(str(d["second"]))
    expect(page.locator("#col-body details.col-item")).to_have_count(1)
    assert creer("Née au séminaire") == {"nom": "Née au séminaire", "projet_id": d["second"]}
    expect(page.locator("#col-body details.col-item")).to_have_count(2)
    assert _collections_listees(page) == ["Étude des émotions", "Née au séminaire"]

    par_nom = {c["nom"]: c["projet_id"] for c in _api(d["base"], "GET", "/api/collections")}
    assert par_nom["Née dans le repli"] == d["repli"]
    assert par_nom["Née au séminaire"] == d["second"]


def test_l_adresse_d_une_collection_fait_basculer_le_projet(page, deux_projets):
    """`/corpus?collection=<id>` nomme une collection d'un AUTRE projet que le courant :
    l'adresse gagne. Le projet bascule — dans la bande, dans la ligne du bloc, dans le
    stockage —, la collection s'ouvre, et la liste est celle de SON projet. Sans la bascule,
    l'écran dirait « elle ne vous est pas ouverte, ou elle n'existe pas » d'une collection
    ouverte."""
    d = deux_projets
    page.goto(d["base"] + f"/corpus?collection={d['b1']}", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{d["b1"]}"]')
    item.wait_for(timeout=5000)
    expect(item).to_have_attribute("open", "")
    expect(page.locator("#projet-choix")).to_have_value(str(d["second"]))
    expect(page.locator("#collections-projet")).to_have_text(
        "Dans le projet « Séminaire 2026 »")
    assert page.evaluate("() => localStorage.getItem('bd-projet')") == str(d["second"])
    assert _collections_listees(page) == ["Étude des émotions"]
    assert page.locator("#col-body .col-msg.erreur").count() == 0

    # Dans l'autre sens, et le choix retenu ne résiste pas à l'adresse non plus.
    page.goto(d["base"] + f"/corpus?collection={d['a2']}", wait_until="networkidle")
    page.locator(f'#col-body .col-item[data-id="{d["a2"]}"][open]').wait_for(timeout=5000)
    expect(page.locator("#projet-choix")).to_have_value(str(d["repli"]))
    assert page.evaluate("() => localStorage.getItem('bd-projet')") == str(d["repli"])

    # Une collection qui n'existe pas ne fait basculer rien, et la ligne le dit comme avant.
    page.goto(d["base"] + "/corpus?collection=987654", wait_until="networkidle")
    expect(page.locator("#col-body .col-msg.erreur")).to_contain_text("n'est pas dans la liste")
    expect(page.locator("#projet-choix")).to_have_value(str(d["repli"]))


def test_un_autre_onglet_qui_change_de_projet_previent_celui_ci(page, deux_projets):
    """Deux onglets partagent le projet courant : c'est écrit, et ce qui en découle se voit.
    Choisir dans l'un redessine la liste de l'autre, sans rechargement."""
    d = deux_projets
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    page.locator("#col-body details.col-item").first.wait_for(timeout=5000)
    autre = page.context.new_page()
    autre.goto(d["base"] + "/recherche", wait_until="networkidle")
    autre.locator("#projet-choix").select_option(str(d["second"]))
    expect(page.locator("#projet-choix")).to_have_value(str(d["second"]), timeout=5000)
    expect(page.locator("#collections-projet")).to_have_text(
        "Dans le projet « Séminaire 2026 »")
    assert _collections_listees(page) == ["Étude des émotions"]
    autre.close()


def test_sans_liste_de_projets_la_bibliotheque_reste_celle_d_avant(page, deux_projets):
    """`GET /api/projets` en panne : la bande ne dessine rien, et la Bibliothèque ne filtre
    rien — elle liste TOUT ce que le serveur rend, ne nomme aucun projet, et crée sans en
    nommer. Une panne de cette route-là ne doit pas vider une liste qui ne lui doit rien."""
    d = deux_projets
    erreurs = _exceptions(page)
    page.route("**/api/projets", lambda route: route.fulfill(
        status=500, content_type="application/json", body='{"detail": "panne jouée"}'))
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    page.locator("#col-body details.col-item").first.wait_for(timeout=5000)
    assert page.evaluate("() => window.BDProjets") is None
    assert _collections_listees(page) == ["Corpus de départ", "Incubateur", "Étude des émotions"]
    expect(page.locator("#collections-projet")).to_be_hidden()
    assert page.locator(".projet-courant").count() == 0

    page.locator("#col-nom").fill("Sans projet nommé")
    with page.expect_request(lambda r: r.method == "POST"
                             and r.url.endswith("/api/collections")) as partie:
        page.locator("#col-add").click()
    assert partie.value.post_data_json == {"nom": "Sans projet nommé"}
    expect(page.locator("#col-body details.col-item")).to_have_count(4)
    assert not erreurs, erreurs


def test_un_decompte_qui_bouge_ne_redessine_pas_la_liste_du_projet(page, deux_projets):
    """Après un geste sur les albums, seul le décompte d'une collection change : la liste
    n'est pas redessinée, et ce qu'on tapait dans une collection dépliée reste. Avec DEUX
    projets, la liste affichée n'est plus celle du serveur : comparée à elle sans le filtre
    du projet courant, elle paraîtrait toujours changée — et chaque album créé effacerait
    une saisie en cours."""
    d = deux_projets
    page.goto(d["base"] + f"/corpus?collection={d['a1']}", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{d["a1"]}"]')
    champ = item.locator('[data-champ="description"]')
    champ.wait_for(timeout=5000)
    champ.fill("une saisie en cours")
    champ.evaluate("(el) => { el.dataset.temoin = '1'; }")

    _api(d["base"], "POST", "/api/albums", {"titre": "Arrivé entre-temps",
                                            "collection_id": d["a1"]})
    page.evaluate("() => loadAlbums()")
    expect(item.locator(".col-nb")).to_have_text("1 album(s)", timeout=5000)
    page.wait_for_timeout(300)                     # le temps qu'un redessin fautif ait lieu
    assert champ.input_value() == "une saisie en cours"
    assert champ.get_attribute("data-temoin") == "1", "la collection dépliée a été redessinée"


# ── La Bibliothèque : les deux listes d'un album suivent le projet ─────────────────────
#
# « Collection », quand on CRÉE un album : les collections du projet COURANT. « + Ranger
# ici », dans la fiche d'un album : celles du projet où l'ALBUM vit — qui peut ne pas être le
# courant, la liste des albums n'étant pas bornée par le projet. Aucune des deux n'est une
# garde : le serveur refuse lui-même un rangement qui traverse deux projets.

NOTE_FILTRE = ("Seules les collections du projet « {} » sont proposées : pour créer l'album "
               "dans un autre projet, choisissez-le en haut de la page.")
NOTE_AUCUNE_ICI = ("Vous n'écrivez dans aucune collection du projet « {} » : l'album ne peut "
                   "pas y être créé. Créez-y d'abord une collection, ou choisissez un autre "
                   "projet en haut de la page.")
NOTE_REPLI = ("Aucune collection : l'album entrera dans une collection par défaut, créée à "
              "cette occasion")
LIGNE_PROJET_DE_L_ALBUM = ("Cet album vit dans le projet « {} » : seules les collections de ce "
                           "projet sont proposées, un album ne se rangeant pas d'un projet à "
                           "l'autre.")
LIGNE_PLUSIEURS_PROJETS = (
    "Cet album est rangé dans des collections de plusieurs projets ({}), ce qui ne devrait pas "
    "arriver : il ne se range nulle part ailleurs tant que c'est le cas. Sortez-le d'abord, "
    "par leur ✕, des collections qui ne sont pas de son projet.")


def _album(base, titre, collection_id):
    return _api(base, "POST", "/api/albums", {"titre": titre, "collection_id": collection_id})["id"]


def _un_album(base):
    albums = _api(base, "GET", "/api/albums")
    assert len(albums) == 1, albums
    return albums[0]["id"]


def _bibliotheque(page, base):
    page.goto(base + "/corpus", wait_until="networkidle")
    page.locator("#col-body details.col-item, #col-body .col-note").first.wait_for(timeout=5000)


def _nouvel_album(page):
    page.locator("#btn-new").click()
    expect(page.locator("#album-modal")).to_be_visible()


def _fiche_de_l_album(page, titre):
    page.locator("#albums-body tr.album-row", has_text=titre).locator('[data-act="edit"]').click()
    expect(page.locator("#m-appartenance")).to_be_visible()


def _proposees(page, selecteur):
    return page.locator(f"{selecteur} option").all_inner_texts()


def _changer_de_projet(page, projet_id, nom):
    page.locator("#projet-choix").select_option(str(projet_id))
    expect(page.locator("#collections-projet")).to_have_text(f"Dans le projet « {nom} »")


def test_un_nouvel_album_ne_se_voit_proposer_que_les_collections_du_projet_courant(
        page, deux_projets):
    """« Collection », dans « + Nouvel album » : celles du projet courant, parmi celles où
    l'on écrit — et une ligne dit ce qui n'est pas proposé, et où en changer. Changer de
    projet change la liste ; la requête PARTIE porte la collection du projet qu'on lit en
    haut de la page."""
    d = deux_projets
    _bibliotheque(page, d["base"])
    _nouvel_album(page)
    expect(page.locator("#m-collection-wrap")).to_be_visible()
    assert _proposees(page, "#m-collection") == ["— choisir —", "Corpus de départ", "Incubateur"]
    expect(page.locator("#m-collection-note")).to_be_visible()
    expect(page.locator("#m-collection-note")).to_have_text(
        NOTE_FILTRE.format(database.NOM_PROJET_DEFAUT))
    page.locator("#m-cancel").click()

    _changer_de_projet(page, d["second"], "Séminaire 2026")
    _nouvel_album(page)
    assert _proposees(page, "#m-collection") == ["Étude des émotions"]
    expect(page.locator("#m-collection")).to_have_value(str(d["b1"]))     # une seule : choisie
    expect(page.locator("#m-collection-note")).to_be_visible()
    expect(page.locator("#m-collection-note")).to_have_text(NOTE_FILTRE.format("Séminaire 2026"))
    page.locator("#m-titre").fill("Né au séminaire")
    with page.expect_request(lambda r: r.method == "POST"
                             and r.url.endswith("/api/albums")) as partie:
        page.locator("#m-save").click()
    assert partie.value.post_data_json["collection_id"] == d["b1"]
    expect(page.locator("#album-modal")).to_be_hidden()
    assert [c["id"] for c in _api(d["base"], "GET", f"/api/albums/{_un_album(d['base'])}"
                                  "/collections")] == [d["b1"]]


def test_la_liste_d_un_nouvel_album_suit_un_changement_de_projet(page, deux_projets):
    """La modale « Nouvel album » est ouverte, et le projet courant change — un autre onglet
    vient d'en choisir un : sa liste est celle du nouveau, pas celle d'un projet qu'on ne
    lit plus en haut de la page."""
    d = deux_projets
    _bibliotheque(page, d["base"])
    _nouvel_album(page)
    assert _proposees(page, "#m-collection") == ["— choisir —", "Corpus de départ", "Incubateur"]
    page.evaluate("(id) => BDProjet.choisir(id)", d["second"])
    expect(page.locator("#m-collection option")).to_have_text(["Étude des émotions"])
    expect(page.locator("#m-collection-note")).to_have_text(NOTE_FILTRE.format("Séminaire 2026"))
    expect(page.locator("#album-modal")).to_be_visible()


def test_sans_collection_ou_ecrire_dans_le_projet_l_ecran_le_dit_et_rien_ne_part(
        page, deux_projets):
    """On écrit dans des collections, mais dans aucune du projet courant : pas de liste vide,
    une phrase qui NOMME le projet et donne les deux sorties. Et « Enregistrer » ne part pas :
    sans collection, le serveur rangerait l'album dans la collection de repli — dans un autre
    projet que celui qu'on lit en haut de la page."""
    d = deux_projets
    _bibliotheque(page, d["base"])
    _changer_de_projet(page, d["vide"], "Projet sans rien")
    parties = []
    page.on("request", lambda r: parties.append(r.url) if r.method == "POST" else None)
    _nouvel_album(page)
    expect(page.locator("#m-collection-wrap")).to_be_hidden()
    assert _proposees(page, "#m-collection") == []
    expect(page.locator("#m-collection-note")).to_be_visible()
    expect(page.locator("#m-collection-note")).to_have_text(
        NOTE_AUCUNE_ICI.format("Projet sans rien"))

    page.locator("#m-titre").fill("Sans collection où entrer")
    page.locator("#m-save").click()
    expect(page.locator("#m-msg")).to_have_text(
        "Aucune collection ne peut accueillir cet album dans le projet « Projet sans rien ».")
    expect(page.locator("#album-modal")).to_be_visible()
    page.wait_for_timeout(300)                     # le temps qu'une requête fautive parte
    assert not parties, f"une requête est partie sans collection : {parties}"
    assert _api(d["base"], "GET", "/api/albums") == []

    # Revenu dans un projet où l'on écrit, le même formulaire enregistre : l'arrêt ne colle pas.
    page.locator("#m-cancel").click()
    _changer_de_projet(page, d["second"], "Séminaire 2026")
    _nouvel_album(page)
    page.locator("#m-titre").fill("Né au séminaire")
    with page.expect_response(lambda r: r.request.method == "POST"
                              and r.url.endswith("/api/albums")) as reponse:
        page.locator("#m-save").click()
    assert reponse.value.status == 201


def test_la_collection_de_repli_dit_dans_quel_projet_elle_naitra(page, live_server):
    """Aucune collection nulle part, et l'on écrit partout : l'album entrera dans la
    collection par défaut, qui naît dans le projet de REPLI. Quand c'est celui où l'on
    travaille, la note est celle d'avant ; sinon elle le nomme — l'album ne sera pas là où
    l'on regarde. Et c'est bien là que le serveur le range."""
    repli = _repli(live_server)
    second = _projet(live_server, "Séminaire 2026")
    _bibliotheque(page, live_server)
    _nouvel_album(page)
    expect(page.locator("#m-collection-note")).to_be_visible()
    expect(page.locator("#m-collection-note")).to_have_text(NOTE_REPLI + ".")
    page.locator("#m-cancel").click()

    page.locator("#projet-choix").select_option(str(second))
    expect(page.locator("#projet-choix")).to_have_value(str(second))
    _nouvel_album(page)
    expect(page.locator("#m-collection-note")).to_be_visible()
    expect(page.locator("#m-collection-note")).to_have_text(
        NOTE_REPLI + f", dans le projet « {database.NOM_PROJET_DEFAUT} ».")
    page.locator("#m-titre").fill("Premier album")
    with page.expect_request(lambda r: r.method == "POST"
                             and r.url.endswith("/api/albums")) as partie:
        page.locator("#m-save").click()
    assert "collection_id" not in partie.value.post_data_json
    expect(page.locator("#album-modal")).to_be_hidden()
    assert [(c["nom"], c["projet_id"]) for c in _api(live_server, "GET", "/api/collections")] == [
        (database.NOM_COLLECTION_DEFAUT, repli)]


def test_ranger_ici_ne_propose_que_les_collections_du_projet_de_l_album(page, deux_projets):
    """« + Ranger ici » suit le projet de l'ALBUM, pas le projet courant. Un album du
    séminaire ouvert depuis le projet de repli ne se voit proposer que les collections du
    séminaire ; un album du repli ouvert depuis le séminaire, que celles du repli. Une ligne
    dit ce qui n'est pas proposé, et la requête partie range dans le projet de l'album."""
    d = deux_projets
    b2 = _collection(d["base"], "Atelier lettrage", d["second"])
    seminaire = _album(d["base"], "Album du séminaire", d["b1"])
    _album(d["base"], "Album du repli", d["a1"])
    _bibliotheque(page, d["base"])
    expect(page.locator("#projet-choix")).to_have_value(str(d["repli"]))  # le courant : le repli
    _nouvel_album(page)                            # la note de la création est écrite…
    expect(page.locator("#m-collection-note")).to_be_visible()
    page.locator("#m-cancel").click()

    _fiche_de_l_album(page, "Album du séminaire")
    # … et ne suit pas dans la fiche d'un album : la liste qu'elle décrit n'y est pas.
    expect(page.locator("#m-collection-note")).to_be_hidden()
    assert page.locator("#m-collection-note").text_content() == ""
    assert _proposees(page, "#m-appartenance-cible") == ["Atelier lettrage"]
    ligne = page.locator("#m-appartenance-projet")
    expect(ligne).to_be_visible()
    expect(ligne).to_have_text(LIGNE_PROJET_DE_L_ALBUM.format("Séminaire 2026"))
    with page.expect_response(lambda r: r.request.method == "PUT") as reponse:
        page.locator("#m-appartenance-add").click()
    assert reponse.value.url.endswith(f"/api/albums/{seminaire}/collections/{b2}")
    assert reponse.value.status == 201
    expect(page.locator("#m-appartenance-liste li")).to_have_count(2)
    # Plus rien à proposer dans son projet : la liste est vide, et la ligne dit toujours pourquoi.
    expect(page.locator("#m-appartenance-cible")).to_be_disabled()
    expect(page.locator("#m-appartenance-add")).to_be_disabled()
    expect(ligne).to_be_visible()
    expect(ligne).to_have_text(LIGNE_PROJET_DE_L_ALBUM.format("Séminaire 2026"))
    page.locator("#m-cancel").click()

    # Dans l'autre sens : le projet courant est le séminaire, l'album vit dans le repli.
    _changer_de_projet(page, d["second"], "Séminaire 2026")
    _fiche_de_l_album(page, "Album du repli")
    assert _proposees(page, "#m-appartenance-cible") == ["Incubateur"]
    expect(ligne).to_be_visible()
    expect(ligne).to_have_text(LIGNE_PROJET_DE_L_ALBUM.format(database.NOM_PROJET_DEFAUT))
    assert "alerte" not in (ligne.get_attribute("class") or "")


def test_ce_qu_on_disait_d_un_album_ne_suit_pas_dans_la_fiche_du_suivant(page, deux_projets):
    """La ligne qui nomme le projet d'un album est à demeure dans SA fiche. Si la fiche du
    suivant ne peut pas lire ses collections, elle le dit — et ne garde pas, sous une liste
    vide, la phrase écrite pour un autre album."""
    d = deux_projets
    _album(d["base"], "Album du séminaire", d["b1"])
    _album(d["base"], "Album illisible", d["a1"])
    _bibliotheque(page, d["base"])
    _fiche_de_l_album(page, "Album du séminaire")
    ligne = page.locator("#m-appartenance-projet")
    expect(ligne).to_be_visible()
    page.locator("#m-cancel").click()

    page.route("**/api/albums/*/collections", lambda route: route.fulfill(
        status=500, content_type="application/json", body='{"detail": "panne jouée"}'))
    _fiche_de_l_album(page, "Album illisible")
    expect(page.locator("#m-appartenance-msg.erreur")).to_have_text("panne jouée")
    expect(ligne).to_be_hidden()
    assert ligne.text_content() == ""


def test_les_listes_d_un_album_n_attendent_pas_le_bloc_des_collections(page, deux_projets):
    """Le projet courant est lu par le bloc des collections, qui se dessine tard — après
    l'état ShareDocs. Une modale ouverte AVANT lui ne doit pas trouver « aucun projet » et
    en conclure qu'il n'y a rien à filtrer : chacune des deux listes lit le projet elle-même.
    La réponse qui fait attendre le bloc est RETENUE, sans quoi le test dépendrait d'une
    course."""
    d = deux_projets
    _collection(d["base"], "Atelier lettrage", d["second"])
    _album(d["base"], "Album du séminaire", d["b1"])
    tenues = []
    page.route("**/api/sharedocs/etat", lambda route: tenues.append(route))
    page.goto(d["base"] + "/corpus", wait_until="domcontentloaded")
    page.locator("#projet-choix").wait_for(timeout=5000)           # la liste des projets est lue
    page.locator("#albums-body tr.album-row").first.wait_for(timeout=5000)
    assert tenues, "l'état ShareDocs n'a pas été retenu : le test ne mesure rien"
    assert page.locator("#col-body details.col-item").count() == 0, (
        "le bloc des collections est déjà dessiné")
    expect(page.locator("#collections-projet")).to_be_hidden()     # le bloc n'a rien lu encore

    _nouvel_album(page)
    assert _proposees(page, "#m-collection") == ["— choisir —", "Corpus de départ", "Incubateur"]
    page.locator("#m-cancel").click()
    assert page.locator("#col-body details.col-item").count() == 0
    for route in tenues:
        route.continue_()
    page.locator("#col-body details.col-item").first.wait_for(timeout=5000)


def test_ranger_ici_n_attend_pas_le_bloc_des_collections(page, deux_projets):
    """Le même défaut, pour « + Ranger ici » : la fiche d'un album ouverte avant que le bloc
    des collections ait lu le projet ne propose pas pour autant les collections de tous."""
    d = deux_projets
    _collection(d["base"], "Atelier lettrage", d["second"])
    _album(d["base"], "Album du séminaire", d["b1"])
    tenues = []
    page.route("**/api/sharedocs/etat", lambda route: tenues.append(route))
    page.goto(d["base"] + "/corpus", wait_until="domcontentloaded")
    page.locator("#projet-choix").wait_for(timeout=5000)
    page.locator("#albums-body tr.album-row").first.wait_for(timeout=5000)
    assert tenues, "l'état ShareDocs n'a pas été retenu : le test ne mesure rien"
    expect(page.locator("#collections-projet")).to_be_hidden()

    _fiche_de_l_album(page, "Album du séminaire")
    assert _proposees(page, "#m-appartenance-cible") == ["Atelier lettrage"]
    expect(page.locator("#m-appartenance-projet")).to_be_visible()
    for route in tenues:
        route.continue_()


def test_avec_un_seul_projet_la_fiche_d_un_album_est_celle_d_avant(page, live_server):
    """Un seul projet : rien n'est écarté, donc rien n'est dit. Ni la modale « Nouvel album »
    ni la fiche d'un album ne gagnent une ligne à qui n'a rien à en apprendre."""
    a1 = _collection(live_server, "Corpus de départ")
    _collection(live_server, "Incubateur")
    _album(live_server, "Seul album", a1)
    _bibliotheque(page, live_server)
    _nouvel_album(page)
    assert _proposees(page, "#m-collection") == ["— choisir —", "Corpus de départ", "Incubateur"]
    expect(page.locator("#m-collection-note")).to_be_hidden()
    assert page.locator("#m-collection-note").text_content() == ""
    page.locator("#m-cancel").click()
    _fiche_de_l_album(page, "Seul album")
    assert _proposees(page, "#m-appartenance-cible") == ["Incubateur"]
    expect(page.locator("#m-appartenance-projet")).to_be_hidden()
    assert page.locator("#m-appartenance-projet").text_content() == ""


def test_un_album_range_dans_deux_projets_se_dit_et_se_repare(page, deux_projets, tmp_path):
    """Un état que l'application ne produit pas — la base est retouchée à la main : un album
    rangé dans des collections de DEUX projets. Le serveur refuse alors tout rangement, où
    que ce soit ; l'écran n'en propose aucun, et le DIT au lieu de montrer une liste vide —
    en nommant les deux projets, et le geste qui en sort. Les ✕ restent : sorti des
    collections d'un projet, l'album retrouve sa liste."""
    d = deux_projets
    b2 = _collection(d["base"], "Atelier lettrage", d["second"])
    album = _album(d["base"], "Album à cheval", d["b1"])
    base = sqlite3.connect(tmp_path / "live.sqlite", timeout=10)
    with base:
        base.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                     (d["a1"], album))
    base.close()
    # Ce que l'écran affirme du serveur, mesuré : aucune collection d'arrivée n'est acceptée.
    with httpx.Client(base_url=d["base"], trust_env=False, timeout=30, headers=ECRITURE) as c:
        for cible in (d["a2"], b2):
            r = c.put(f"/api/albums/{album}/collections/{cible}")
            assert r.status_code == 409 and "traverse pas les projets" in r.text, r.text

    _bibliotheque(page, d["base"])
    _fiche_de_l_album(page, "Album à cheval")
    expect(page.locator("#m-appartenance-liste [data-sortir]")).to_have_count(2)
    assert _proposees(page, "#m-appartenance-cible") == []
    expect(page.locator("#m-appartenance-cible")).to_be_disabled()
    expect(page.locator("#m-appartenance-add")).to_be_disabled()
    ligne = page.locator("#m-appartenance-projet")
    expect(ligne).to_be_visible()
    expect(ligne).to_have_text(LIGNE_PLUSIEURS_PROJETS.format(
        f"« {database.NOM_PROJET_DEFAUT} », « Séminaire 2026 »"))
    assert "alerte" in ligne.get_attribute("class")

    with page.expect_response(lambda r: r.request.method == "DELETE") as reponse:
        page.locator(f'#m-appartenance-liste [data-sortir="{d["a1"]}"]').click()
    assert reponse.value.status == 204
    expect(page.locator("#m-appartenance-liste li")).to_have_count(1)
    expect(page.locator("#m-appartenance-cible option")).to_have_text(["Atelier lettrage"])
    expect(ligne).to_have_text(LIGNE_PROJET_DE_L_ALBUM.format("Séminaire 2026"))
    assert "alerte" not in (ligne.get_attribute("class") or "")


def test_sans_liste_de_projets_les_deux_listes_d_un_album_restent_celles_d_avant(
        page, deux_projets):
    """`GET /api/projets` en panne : aucune des deux listes n'est filtrée, et aucune ligne ne
    parle d'un projet qu'on ne sait pas nommer. « Nouvel album » propose toutes les
    collections où l'on écrit, « + Ranger ici » toutes celles où l'album n'est pas — une
    panne de cette route-là ne vide pas des listes qui ne lui doivent rien."""
    d = deux_projets
    _album(d["base"], "Album du séminaire", d["b1"])
    erreurs = _exceptions(page)
    page.route("**/api/projets", lambda route: route.fulfill(
        status=500, content_type="application/json", body='{"detail": "panne jouée"}'))
    _bibliotheque(page, d["base"])
    assert page.evaluate("() => window.BDProjets") is None
    _nouvel_album(page)
    assert _proposees(page, "#m-collection") == [
        "— choisir —", "Corpus de départ", "Incubateur", "Étude des émotions"]
    expect(page.locator("#m-collection-note")).to_be_hidden()
    page.locator("#m-cancel").click()

    _fiche_de_l_album(page, "Album du séminaire")
    assert _proposees(page, "#m-appartenance-cible") == ["Corpus de départ", "Incubateur"]
    expect(page.locator("#m-appartenance-projet")).to_be_hidden()
    assert not erreurs, erreurs


# ── L'Administration : le bloc « Projets » ──────────────────────────────────────────────


def _ouvrir_les_projets(page, base, identite):
    page.set_extra_http_headers(identite)
    page.goto(base + "/administration", wait_until="networkidle")


def _fiche(page):
    return page.locator("#pj-fiche")


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_administrateur_cree_un_projet_avec_sa_justification(page, live_server):
    """L'administrateur crée un projet et dit POURQUOI. La requête partie porte le nom et la
    justification ; le projet créé s'ouvre en fiche, où elle se lit ; et la bande du haut —
    sur la même page — gagne son sélecteur sans attendre un rechargement."""
    _ouvrir_les_projets(page, live_server, ADMIN_BD)
    page.locator("#pj-objets .pj-objet").first.wait_for(timeout=5000)
    expect(page.locator("#projets-bloc")).to_be_visible()
    expect(page.locator("#projets-ferme")).to_be_hidden()
    expect(page.locator("#pj-nom-aide")).to_contain_text(
        f"{database.LONGUEUR_NOM_PROJET} caractères au plus")
    assert page.locator("#projet-choix").count() == 0          # un seul projet : le nom seul

    page.locator("#pj-ajouter").click()                        # sans nom : rien ne part
    expect(page.locator("#pj-msg.erreur")).to_have_text("Donnez un nom au projet.")

    page.locator("#pj-nom").fill("Séminaire 2026")
    page.locator("#pj-justification").fill("Comparer le lettrage de deux éditions.")
    with page.expect_request(lambda r: r.method == "POST"
                             and r.url.endswith("/api/projets")) as partie:
        page.locator("#pj-ajouter").click()
    assert partie.value.post_data_json == {
        "nom": "Séminaire 2026", "justification": "Comparer le lettrage de deux éditions."}

    expect(page.locator("#pj-msg")).to_contain_text("« Séminaire 2026 » créé")
    expect(page.locator("#pj-fiche-titre")).to_have_text("Séminaire 2026")
    expect(page.locator("#pj-fiche-titre")).to_be_focused()
    expect(_fiche(page).locator(".pj-justification")).to_have_text(
        "Comparer le lettrage de deux éditions.")
    assert page.locator("#pj-objets .pj-objet .pj-nom").all_inner_texts() == [
        database.NOM_PROJET_DEFAUT, "Séminaire 2026"]
    expect(page.locator("#projet-choix option")).to_have_count(2)
    assert page.locator("#pj-nom").input_value() == ""

    # Un nom trop long : le refus est celui du SERVEUR, rendu tel quel sous le champ.
    page.locator("#pj-nom").fill("x" * (database.LONGUEUR_NOM_PROJET + 1))
    page.locator("#pj-ajouter").click()
    expect(page.locator("#pj-msg.erreur")).to_contain_text(
        f"tient en {database.LONGUEUR_NOM_PROJET} caractères au plus")


@pytest.fixture
def seminaire(live_server):
    """Derrière le proxy : « Séminaire 2026 », justifié, avec une collection, et rien d'autre."""
    pid = _projet(live_server, "Séminaire 2026", justification="Comparer deux éditions.")
    return {"base": live_server, "repli": _repli(live_server), "projet": pid,
            "collection": _collection(live_server, "Étude des émotions", pid)}


def _ouvrir_la_fiche(page, d, identite=ADMIN_BD):
    _ouvrir_les_projets(page, d["base"], identite)
    ligne = page.locator(f'#pj-objets .pj-objet[data-pj="{d["projet"]}"]')
    ligne.wait_for(timeout=5000)
    if ligne.get_attribute("aria-current") != "true":
        ligne.click()
    expect(page.locator("#pj-fiche-titre")).to_have_text("Séminaire 2026")
    partie = _fiche(page).locator("section.mp")
    partie.locator(".mp-choix").wait_for(timeout=5000)
    return partie


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_faire_entrer_un_groupe_part_avec_le_role_de_membre(page, seminaire):
    """On ENTRE membre : la requête de « + Faire entrer » porte le premier rôle, jamais
    celui de responsable — nommer un responsable est un second geste. Le groupe est choisi
    dans la liste de l'annuaire, et la saisie libre reste CACHÉE tant qu'on ne la demande pas."""
    d = seminaire
    partie = _ouvrir_la_fiche(page, d)
    expect(partie.locator(".mp-titre")).to_have_text("Qui y entre")
    expect(partie.locator(".mp-membres")).to_contain_text("Personne n'est encore entré")
    expect(partie.locator(".mp-n-ouvre-rien")).to_contain_text(
        "Entrer dans le projet n'ouvre pas ses collections : chacune garde son « Qui entre ».")
    expect(partie.locator(".mp-libre")).to_be_hidden()

    partie.locator(".mp-choix").select_option("groupe:annotateurs")
    with page.expect_request(lambda r: r.method == "PUT"
                             and r.url.endswith(f"/api/projets/{d['projet']}/membres")) as partie_req:
        partie.locator(".mp-faire-entrer").click()
    assert partie_req.value.post_data_json == {
        "genre": "groupe", "principal": "annotateurs", "role": "membre"}
    expect(partie.locator(".mp-msg")).to_contain_text(
        "Le groupe annotateurs entre dans le projet « Séminaire 2026 », comme membre. "
        "Aucune collection ne lui est ouverte pour autant.")
    assert _membres(d["base"], d["projet"]) == {("groupe", "annotateurs"): "membre"}
    expect(partie.locator(".mp-ligne")).to_have_count(1)
    expect(partie.locator(".mp-role")).to_have_value("membre")

    # Le faire entrer une seconde fois le rétrograderait s'il était responsable : l'écran
    # le refuse avant d'envoyer.
    partie.locator(".mp-choix").select_option("groupe:annotateurs")
    partie.locator(".mp-faire-entrer").click()
    expect(partie.locator(".mp-msg.erreur")).to_contain_text("est déjà du projet")


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_faire_entrer_un_compte_demande_de_dire_ce_qu_il_est(page, seminaire):
    """La saisie libre — VISIBLE une fois demandée — exige « Compte » ou « Groupe », sans
    valeur par défaut. Un nom que l'annuaire ne connaît pas entre quand même, et l'écran le
    dit ; un compte connu entre comme membre."""
    d = seminaire
    partie = _ouvrir_la_fiche(page, d)
    partie.locator(".mp-choix").select_option("autre")
    expect(partie.locator(".mp-libre")).to_be_visible()
    expect(partie.locator(".mp-nom")).to_be_focused()
    partie.locator(".mp-nom").fill("lectrice")
    partie.locator(".mp-faire-entrer").click()
    expect(partie.locator(".mp-msg.erreur")).to_contain_text(
        "Dites si « lectrice » est un compte ou un groupe")
    assert _membres(d["base"], d["projet"]) == {}

    partie.locator(".mp-genre").select_option("utilisateur")
    with page.expect_request(lambda r: r.method == "PUT"
                             and r.url.endswith("/membres")) as partie_req:
        partie.locator(".mp-faire-entrer").click()
    assert partie_req.value.post_data_json == {
        "genre": "utilisateur", "principal": "lectrice", "role": "membre"}
    expect(partie.locator(".mp-msg")).to_contain_text("Le compte lectrice entre dans le projet")

    partie.locator(".mp-choix").select_option("autre")
    partie.locator(".mp-nom").fill("ancien-cours")
    partie.locator(".mp-genre").select_option("groupe")
    partie.locator(".mp-nom").press("Enter")
    expect(partie.locator(".mp-msg.alerte")).to_contain_text(
        "Le groupe ancien-cours n'est pas dans l'annuaire")
    expect(partie.locator('.mp-ligne[data-principal="ancien-cours"] .mp-marque')).to_have_text(
        "inconnu de l'annuaire")
    assert _membres(d["base"], d["projet"]) == {
        ("utilisateur", "lectrice"): "membre", ("groupe", "ancien-cours"): "membre"}


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_nommer_un_responsable_puis_le_faire_sortir(page, seminaire):
    """Sur la ligne d'un membre : le nommer responsable part avec CE rôle ; le dernier
    responsable ne se rétrograde ni ne sort — le refus du serveur se lit, et la ligne
    revient à ce qu'il a gardé — ; un membre sort par une requête qui le nomme."""
    d = seminaire
    _membre(d["base"], d["projet"], "proprio")
    _membre(d["base"], d["projet"], "lectrice")
    partie = _ouvrir_la_fiche(page, d)
    ligne = partie.locator('.mp-ligne[data-principal="proprio"]')
    # Aucun des deux n'a encore ouvert l'application : l'écran le RAPPORTE, sans dire pourquoi.
    expect(ligne.locator(".acces-jamais-vu")).to_have_text("n'a pas encore ouvert l'application")
    role = ligne.locator(".mp-role")
    assert role.locator("option").all_inner_texts() == ["membre", "responsable du projet"]

    with page.expect_request(lambda r: r.method == "PUT"
                             and r.url.endswith("/membres")) as partie_req:
        role.select_option("responsable")
    assert partie_req.value.post_data_json == {
        "genre": "utilisateur", "principal": "proprio", "role": "responsable"}
    expect(partie.locator('.mp-ligne[data-principal="proprio"] .mp-role')).to_have_value(
        "responsable")
    assert _membres(d["base"], d["projet"])[("utilisateur", "proprio")] == "responsable"
    # Les responsables d'abord : c'est l'ordre du serveur, et la liste le suit.
    assert partie.locator(".mp-ligne").first.get_attribute("data-principal") == "proprio"

    partie.locator('.mp-ligne[data-principal="proprio"] .mp-role').select_option("membre")
    expect(partie.locator(".mp-msg.erreur")).to_contain_text(
        "dernier responsable de ce projet : désignez-en un autre avant de le rétrograder")
    expect(partie.locator('.mp-ligne[data-principal="proprio"] .mp-role')).to_have_value(
        "responsable")
    partie.locator('.mp-ligne[data-principal="proprio"] .mp-sortir').click()
    expect(partie.locator(".mp-msg.erreur")).to_contain_text(
        "dernier responsable de ce projet : désignez-en un autre avant de le retirer")
    expect(partie.locator(".mp-ligne")).to_have_count(2)

    with page.expect_request(lambda r: r.method == "DELETE") as partie_req:
        partie.locator('.mp-ligne[data-principal="lectrice"] .mp-sortir').click()
    assert partie_req.value.url.endswith(
        f"/api/projets/{d['projet']}/membres/utilisateur/lectrice")
    expect(partie.locator(".mp-ligne")).to_have_count(1)
    expect(partie.locator(".mp-titre")).to_be_focused()
    assert _membres(d["base"], d["projet"]) == {("utilisateur", "proprio"): "responsable"}


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_renommer_et_supprimer_un_projet(page, seminaire):
    """Deux gestes de l'administrateur. Renommer : la requête porte le nom, et la bande du
    haut le dit aussitôt. Supprimer : refusé tant qu'une collection lui appartient — le 409
    du serveur se lit dans la fiche — ; le projet de repli n'a pas de bouton, il ne se
    supprime pas ; un projet vide part, et la bande revient au nom seul."""
    d = seminaire
    _ouvrir_la_fiche(page, d)
    page.locator("[data-pj-renommer]").click()                 # le nom qu'il porte déjà
    expect(page.locator("#pj-fiche-msg")).to_have_text("Rien n'a changé.")
    page.locator("#pj-renommer-nom").fill(database.NOM_PROJET_DEFAUT.upper())
    page.locator("#pj-renommer-nom").press("Enter")            # celui d'un autre, à la casse près
    expect(page.locator("#pj-fiche-msg.erreur")).to_have_text(
        f"Un projet s'appelle déjà « {database.NOM_PROJET_DEFAUT} ».")
    expect(page.locator("#pj-fiche-titre")).to_have_text("Séminaire 2026")

    page.locator("#pj-renommer-nom").fill("Séminaire d'hiver")
    with page.expect_request(lambda r: r.method == "PATCH") as partie:
        page.locator("[data-pj-renommer]").click()
    assert partie.value.url.endswith(f"/api/projets/{d['projet']}")
    assert partie.value.post_data_json == {"nom": "Séminaire d'hiver"}
    expect(page.locator("#pj-fiche-msg")).to_contain_text("s'appelle désormais « Séminaire d'hiver »")
    expect(page.locator("#pj-fiche-titre")).to_have_text("Séminaire d'hiver")
    expect(page.locator("#projet-choix")).to_contain_text("Séminaire d'hiver")
    expect(page.locator("#projet-choix")).not_to_contain_text("Séminaire 2026")

    page.on("dialog", lambda dlg: dlg.accept())
    page.locator("[data-pj-supprimer]").click()
    expect(page.locator("#pj-fiche-msg.erreur")).to_contain_text(
        "1 collection(s) appartiennent à ce projet")
    expect(page.locator("#pj-objets .pj-objet")).to_have_count(2)

    page.locator(f'#pj-objets .pj-objet[data-pj="{d["repli"]}"]').click()
    expect(page.locator("#pj-fiche-titre")).to_have_text(database.NOM_PROJET_DEFAUT)
    assert page.locator("[data-pj-supprimer]").count() == 0
    expect(_fiche(page)).to_contain_text("Il se renomme, il ne se supprime pas.")

    vide = _projet(d["base"], "Projet sans rien")
    page.reload(wait_until="networkidle")
    page.locator(f'#pj-objets .pj-objet[data-pj="{vide}"]').click()
    expect(page.locator("#pj-fiche-titre")).to_have_text("Projet sans rien")
    with page.expect_request(lambda r: r.method == "DELETE") as partie:
        page.locator("[data-pj-supprimer]").click()
    assert partie.value.url.endswith(f"/api/projets/{vide}")
    expect(page.locator("#pj-msg")).to_contain_text("« Projet sans rien » supprimé")
    expect(page.locator("#pj-objets .pj-objet")).to_have_count(2)
    expect(page.locator("#projet-choix")).not_to_contain_text("Projet sans rien")


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_responsable_regle_son_projet_et_lui_seul(page, seminaire):
    """Le responsable voit le bloc, pour LE projet qu'il gère : il en lit la justification,
    règle qui y entre, ne nomme que les collections qu'il lit — et la fiche lui dit à qui
    demander de le renommer ou de le supprimer. Il ne décide pas des projets : ni création,
    ni renommage, ni suppression ne lui sont offerts. Le projet de repli, où il lit une
    collection, se nomme dans la bande et n'entre pas dans le bloc."""
    d = seminaire
    _membre(d["base"], d["projet"], "proprio", "responsable")
    _acces(d["base"], _collection(d["base"], "Corpus de départ"), "proprio")
    _collection(d["base"], "Fermée au responsable", d["projet"])
    partie = _ouvrir_la_fiche(page, d, PROPRIO)

    expect(page.locator("#projet-choix option")).to_have_count(2)
    assert page.locator("#pj-objets .pj-objet .pj-nom").all_inner_texts() == ["Séminaire 2026"]
    expect(page.locator("#pj-creer")).to_be_hidden()
    assert page.locator("[data-pj-renommer], [data-pj-supprimer], #pj-renommer-nom").count() == 0
    expect(_fiche(page).locator(".pj-a-demander")).to_have_text(
        "Vous réglez qui entre dans ce projet. Le renommer ou le supprimer se demande à un "
        "administrateur de l'instance.")
    expect(_fiche(page).locator(".pj-justification")).to_have_text("Comparer deux éditions.")
    # Il ne lit aucune collection de son projet : aucune n'est nommée, et la fiche dit pourquoi.
    assert _fiche(page).locator(".pj-collections a").count() == 0
    expect(_fiche(page)).to_contain_text("Seules les collections que vous lisez sont nommées ici.")
    assert "Fermée au responsable" not in page.content()

    # Et il RÈGLE : faire entrer part sous son identité, et le serveur l'accepte.
    partie.locator(".mp-choix").select_option("groupe:etudiants-bd-2026")
    with page.expect_response(lambda r: r.request.method == "PUT"
                              and r.url.endswith("/membres")) as reponse:
        partie.locator(".mp-faire-entrer").click()
    assert reponse.value.status == 200
    assert _membres(d["base"], d["projet"])[("groupe", "etudiants-bd-2026")] == "membre"


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_administrateur_corrige_la_description_et_la_justification(page, seminaire):
    """« Ce projet », pour qui décide des projets : deux champs à côté de « Renommer », la
    description et pourquoi le projet existe. La requête PARTIE ne porte que ce qui a
    changé — jamais le champ qu'on n'a pas touché, et jamais l'un sous le nom de l'autre — ;
    un champ vidé part à `null`. La fiche montre le nouveau texte sans rechargement, sa
    ligne le confirme, le focus reste sur le bouton, et rien ne part quand rien n'a changé."""
    d = seminaire
    _ouvrir_la_fiche(page, d)
    description = page.locator("#pj-decrire-description")
    justification = page.locator("#pj-decrire-justification")
    bouton = page.locator("#pj-fiche [data-pj-decrire]")
    message = page.locator("#pj-fiche-msg")
    expect(page.locator('label[for="pj-decrire-description"]')).to_have_text("Description")
    expect(page.locator('label[for="pj-decrire-justification"]')).to_contain_text(
        "Pourquoi ce projet existe")
    expect(bouton).to_have_text("Enregistrer")
    expect(description).to_have_value("")
    expect(justification).to_have_value("Comparer deux éditions.")
    assert _fiche(page).locator(".pj-description").count() == 0
    page.evaluate("() => { window.__temoin = 'même page'; }")
    parties = []
    page.on("request", lambda r: parties.append(r.post_data_json) if r.method == "PATCH" else None)

    bouton.click()                                             # rien n'a été touché
    expect(message).to_be_visible()
    expect(message).to_have_text("Rien n'a changé.")
    assert not parties, f"une requête est partie sans rien à changer : {parties}"

    nouvelle = "Comparer le lettrage de deux éditions,\nplanche à planche."
    justification.fill(nouvelle)
    with page.expect_request(lambda r: r.method == "PATCH") as partie:
        bouton.click()
    assert partie.value.url.endswith(f"/api/projets/{d['projet']}")
    assert partie.value.post_data_json == {"justification": nouvelle}
    expect(message).to_be_visible()
    expect(message).to_have_text("Justification enregistrée.")
    assert "erreur" not in (message.get_attribute("class") or "")
    expect(_fiche(page).locator(".pj-justification")).to_have_text(
        "Comparer le lettrage de deux éditions, planche à planche.")
    expect(justification).to_have_value(nouvelle)
    expect(bouton).to_be_focused()
    assert _fiche(page).locator(".pj-description").count() == 0

    description.fill("  Le séminaire de l'hiver 2026.  ")         # les blancs de bord ne partent pas
    with page.expect_request(lambda r: r.method == "PATCH") as partie:
        bouton.click()
    assert partie.value.post_data_json == {"description": "Le séminaire de l'hiver 2026."}
    expect(message).to_have_text("Description enregistrée.")
    expect(_fiche(page).locator(".pj-description")).to_have_text("Le séminaire de l'hiver 2026.")
    expect(_fiche(page).locator(".pj-justification")).to_have_text(
        "Comparer le lettrage de deux éditions, planche à planche.")
    expect(bouton).to_be_focused()

    description.fill("Autre description.")                     # les deux à la fois, dont un vidé
    justification.fill("")
    with page.expect_request(lambda r: r.method == "PATCH") as partie:
        bouton.click()
    assert partie.value.post_data_json == {"description": "Autre description.",
                                           "justification": None}
    expect(message).to_have_text("Description et justification enregistrées.")
    expect(_fiche(page).locator(".pj-description")).to_have_text("Autre description.")
    assert _fiche(page).locator(".pj-justification").count() == 0
    expect(_fiche(page)).to_contain_text("Aucune justification n'a été saisie.")
    expect(justification).to_have_value("")

    assert page.evaluate("() => window.__temoin") == "même page", "la page a été rechargée"
    assert len(parties) == 3, parties
    lu = next(p for p in _api(d["base"], "GET", "/api/projets") if p["id"] == d["projet"])
    assert (lu["nom"], lu["description"], lu["justification"]) == (
        "Séminaire 2026", "Autre description.", None)


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_refus_d_enregistrer_se_lit_et_la_saisie_reste(page, seminaire):
    """Le serveur refuse l'enregistrement : son message se lit dans la ligne de la fiche, en
    erreur, et ce qu'on a tapé n'est pas perdu — la fiche n'est pas redessinée sur un échec."""
    d = seminaire
    _ouvrir_la_fiche(page, d)
    page.route(f"**/api/projets/{d['projet']}", lambda route: route.fulfill(
        status=403, content_type="application/json", body='{"detail": "refus joué"}')
        if route.request.method == "PATCH" else route.continue_())
    page.locator("#pj-decrire-justification").fill("Une saisie que le refus ne doit pas perdre.")
    page.locator("#pj-fiche [data-pj-decrire]").click()
    expect(page.locator("#pj-fiche-msg.erreur")).to_be_visible()
    expect(page.locator("#pj-fiche-msg.erreur")).to_have_text("refus joué")
    expect(page.locator("#pj-decrire-justification")).to_have_value(
        "Une saisie que le refus ne doit pas perdre.")
    expect(_fiche(page).locator(".pj-justification")).to_have_text("Comparer deux éditions.")


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_responsable_ne_recoit_aucun_champ_pour_decrire_son_projet(page, seminaire):
    """Décrire un projet et dire pourquoi il existe se DÉCIDE : le responsable, qui règle qui
    entre, lit la justification et n'obtient ni champ ni bouton dans « Ce projet » — la
    phrase qui lui dit à qui s'adresser y est seule. Le serveur le refuserait de toute façon,
    et c'est mesuré (`tests/test_projet_ecran.py`)."""
    d = seminaire
    _api(d["base"], "PATCH", f"/api/projets/{d['projet']}", {"description": "Une description."})
    _membre(d["base"], d["projet"], "proprio", "responsable")
    _ouvrir_la_fiche(page, d, PROPRIO)
    # Le titre EXACT : « Pourquoi ce projet existe » contient lui aussi « ce projet ».
    ce_projet = _fiche(page).locator("section.pj-section").filter(
        has=page.locator('h4:text-is("Ce projet")'))
    expect(ce_projet).to_have_count(1)
    expect(ce_projet.locator(".pj-a-demander")).to_be_visible()
    assert ce_projet.locator("input, textarea, select, button").count() == 0
    assert page.locator(".pj-decrire, [data-pj-decrire], #pj-decrire-description, "
                        "#pj-decrire-justification").count() == 0
    # Il LIT les deux textes, là où la fiche les montre.
    expect(_fiche(page).locator(".pj-description")).to_have_text("Une description.")
    expect(_fiche(page).locator(".pj-justification")).to_have_text("Comparer deux éditions.")


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_simple_membre_lit_pourquoi_la_page_ne_lui_montre_rien(page, seminaire):
    """Un simple membre n'a rien à régler : le bloc ne lui est pas montré, et une phrase dit
    pourquoi, en nommant son projet. La page ne lui apprend ni la justification du projet,
    ni qui en est : elle ne demande même pas la liste des membres."""
    d = seminaire
    _membre(d["base"], d["projet"], "lectrice")
    _membre(d["base"], d["projet"], "proprio", "responsable")
    demandes = []
    page.on("request", lambda r: demandes.append(r.url))
    _ouvrir_les_projets(page, d["base"], LECTRICE)
    ferme = page.locator("#projets-ferme")
    ferme.wait_for(timeout=5000)
    expect(page.locator("#projets-ferme-texte")).to_be_visible()
    expect(page.locator("#projets-ferme-texte")).to_have_text(
        "Les projets se règlent par leur responsable. Vous êtes membre du projet "
        "« Séminaire 2026 » : vous n'y réglez rien.")
    expect(page.locator("#projets-bloc")).to_be_hidden()
    assert page.locator("#pj-objets .pj-objet, #pj-fiche *").count() == 0
    assert "Comparer deux éditions." not in page.content(), (
        "la justification s'affiche à un membre")
    assert "proprio" not in page.locator("#admin-app").inner_text(), (
        "la page nomme le responsable à un simple membre")
    assert not [u for u in demandes if "/api/" in u and "/membres" in u], (
        "la page demande les membres d'un projet à qui ne le gère pas")
    # Dans la bande, en revanche, son projet se lit comme partout.
    expect(page.locator("#projet-nom")).to_have_text("Séminaire 2026")


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_ce_que_lit_qui_ne_regle_aucun_projet_suit_ce_qu_il_est(page, seminaire):
    """La phrase dit ce que la personne EST, pas une formule : membre de plusieurs projets,
    elle les nomme tous ; lectrice d'une collection sans être d'aucun projet, elle ne lui
    prête aucune appartenance ; et qui ne voit aucun projet ne lit RIEN ici — le bandeau de
    portée vide lui parle déjà, d'accès."""
    d = seminaire
    autre = _projet(d["base"], "Atelier lettrage")
    for pid in (d["projet"], autre):
        _membre(d["base"], pid, "lectrice")
    _acces(d["base"], d["collection"], "arrivant")

    # `to_have_text` lit aussi un élément caché : la phrase doit d'abord être À L'ÉCRAN.
    _ouvrir_les_projets(page, d["base"], LECTRICE)
    expect(page.locator("#projets-ferme-texte")).to_be_visible()
    expect(page.locator("#projets-ferme-texte")).to_have_text(
        "Les projets se règlent par leur responsable. Vous êtes membre des projets "
        "« Atelier lettrage » et « Séminaire 2026 » : vous n'y réglez rien.")

    _ouvrir_les_projets(page, d["base"], {"Remote-User": "arrivant"})
    expect(page.locator("#projets-ferme-texte")).to_be_visible()
    expect(page.locator("#projets-ferme-texte")).to_have_text(
        "Les projets se règlent par leur responsable. Vous n'en réglez aucun.")
    expect(page.locator("#projets-bloc")).to_be_hidden()

    _ouvrir_les_projets(page, d["base"], {"Remote-User": "nadia"})
    page.locator("#sante-body .sante-ligne").first.wait_for(timeout=5000)
    assert page.evaluate("() => window.BDProjets") == []
    expect(page.locator("#projets-ferme")).to_be_hidden()
    expect(page.locator("#projets-bloc")).to_be_hidden()


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_responsable_qui_se_fait_sortir_ne_regle_plus_rien(page, seminaire):
    """Un responsable se fait sortir de son projet — il en reste un autre, le serveur
    l'accepte. À l'instant, il n'en règle plus aucun et n'en voit plus aucun : le bloc se
    retire, la bande du haut ne nomme plus de projet, et rien ne lève. Le bloc ne reste pas
    ouvert sur une fiche que le serveur ne rend plus."""
    d = seminaire
    _membre(d["base"], d["projet"], "proprio", "responsable")
    _membre(d["base"], d["projet"], "lectrice", "responsable")
    erreurs = _exceptions(page)
    partie = _ouvrir_la_fiche(page, d, PROPRIO)
    expect(page.locator("#projet-nom")).to_have_text("Séminaire 2026")
    with page.expect_response(lambda r: r.request.method == "DELETE") as reponse:
        partie.locator('.mp-ligne[data-principal="proprio"] .mp-sortir').click()
    assert reponse.value.status == 204
    expect(page.locator("#projets-bloc")).to_be_hidden()
    expect(page.locator("#projets-ferme")).to_be_hidden()
    expect(page.locator(".projet-courant")).to_have_count(0)
    assert page.locator("#pj-fiche *").count() == 0
    assert _membres(d["base"], d["projet"]) == {("utilisateur", "lectrice"): "responsable"}
    assert not erreurs, erreurs


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_annuaire_en_panne_n_empeche_pas_de_faire_entrer(page, seminaire):
    """La lecture de l'annuaire échoue : la liste des membres est là quand même, la saisie
    libre s'offre d'emblée — il n'y a aucun groupe à proposer —, et l'on fait entrer par un
    nom, que l'écran marque « non vérifié » au lieu de le refuser."""
    d = seminaire
    page.route("**/membres/choix", lambda route: route.fulfill(
        status=500, content_type="application/json", body='{"detail": "annuaire injoignable"}'))
    partie = _ouvrir_la_fiche(page, d)
    expect(partie.locator(".mp-notes")).to_contain_text(
        "La lecture de l'annuaire a échoué (annuaire injoignable)")
    expect(partie.locator(".mp-libre")).to_be_visible()
    assert partie.locator(".mp-choix optgroup").count() == 0
    partie.locator(".mp-nom").fill("arrivant")
    partie.locator(".mp-genre").select_option("utilisateur")
    with page.expect_request(lambda r: r.method == "PUT"
                             and r.url.endswith("/membres")) as partie_req:
        partie.locator(".mp-faire-entrer").click()
    assert partie_req.value.post_data_json == {
        "genre": "utilisateur", "principal": "arrivant", "role": "membre"}
    expect(partie.locator(".mp-msg.alerte")).to_have_text(
        "Le compte arrivant entre dans le projet « Séminaire 2026 » — non vérifié : "
        "l'annuaire ne répondait pas.")
    assert _membres(d["base"], d["projet"]) == {("utilisateur", "arrivant"): "membre"}


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_la_saisie_en_cours_survit_a_l_arrivee_de_l_annuaire(page, seminaire):
    """L'annuaire répond APRÈS l'ouverture de la fiche, et la ligne d'ajout se redessine à
    son arrivée pour proposer ses groupes : le nom qu'on a commencé à taper entre-temps ne
    part pas avec l'ancienne ligne."""
    d = seminaire
    _ouvrir_la_fiche(page, d)
    tenues = []
    page.route("**/membres/choix", lambda route: tenues.append(route))
    # Une fiche rouverte : son module est monté à neuf, et sa lecture de l'annuaire attend.
    page.locator(f'#pj-objets .pj-objet[data-pj="{d["repli"]}"]').click()
    page.locator(f'#pj-objets .pj-objet[data-pj="{d["projet"]}"]').click()
    expect(page.locator("#pj-fiche-titre")).to_have_text("Séminaire 2026")
    partie = _fiche(page).locator("section.mp")
    partie.locator(".mp-nom").fill("arrivant")
    partie.locator(".mp-genre").select_option("utilisateur")
    assert partie.locator(".mp-choix optgroup").count() == 0, "l'annuaire a déjà répondu"
    assert tenues, "aucune lecture de l'annuaire n'a été retenue : le test ne mesure rien"
    for route in tenues:
        route.continue_()
    expect(partie.locator(".mp-choix optgroup")).to_have_count(1)
    expect(partie.locator(".mp-nom")).to_have_value("arrivant")
    expect(partie.locator(".mp-genre")).to_have_value("utilisateur")
    expect(partie.locator(".mp-choix")).to_have_value("autre")
    expect(partie.locator(".mp-libre")).to_be_visible()


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_le_bloc_dit_ce_qu_il_n_a_pas_pu_lire(page, seminaire):
    """Deux pannes, et aucune n'est un silence. Les COLLECTIONS illisibles : la fiche le
    dit à leur place, et tout le reste se règle — elles ne servent qu'à être nommées. La
    liste des PROJETS illisible : rien à régler, et une phrase dit pourquoi, au lieu d'un
    bloc qui disparaîtrait en faisant chercher un droit qu'on a déjà."""
    d = seminaire

    def panne(route):
        route.fulfill(status=500, content_type="application/json",
                      body='{"detail": "panne jouée"}')

    page.route("**/api/collections", panne)
    partie = _ouvrir_la_fiche(page, d)
    expect(_fiche(page)).to_contain_text("Les collections n'ont pas pu être lues.")
    assert _fiche(page).locator(".pj-collections").count() == 0
    expect(partie.locator(".mp-faire-entrer")).to_be_visible()
    page.unroute("**/api/collections")

    page.route("**/api/projets", panne)
    page.goto(d["base"] + "/administration", wait_until="networkidle")
    expect(page.locator("#projets-ferme-texte")).to_be_visible()
    expect(page.locator("#projets-ferme-texte")).to_have_text(
        "La liste des projets n'a pas pu être lue : panne jouée")
    expect(page.locator("#projets-bloc")).to_be_hidden()
    assert page.locator(".projet-courant").count() == 0


# Le module, monté à la main dans la page de l'Administration : son contrat, hors de l'hôte.
_MONTER = """(projet) => {
  const hote = document.getElementById('admin-body');
  const s1 = window.__s1 = document.createElement('section');
  const s2 = window.__s2 = document.createElement('section');
  hote.append(s1, s2);
  window.__messages = 0;
  const surMessage = () => { window.__messages += 1; };
  window.__a = BDMembresProjet.monter(s1, { projet, surMessage });
  const investie = { classe: s1.classList.contains('mp'), nomme: s1.getAttribute('aria-labelledby'),
                     titres: s1.querySelectorAll('.mp-titre').length };
  BDMembresProjet.monter(s1, { projet, surMessage });         // au même endroit : remplace
  window.__b = BDMembresProjet.monter(s2, { projet });        // ailleurs : un second montage
  return { investie, remplacee: s1.querySelectorAll('.mp-titre').length };
}"""

_DEMONTER = """(projet) => {
  const s1 = window.__s1, s2 = window.__s2;
  const ids = [...document.querySelectorAll('[id]')].map((e) => e.id);
  const ensemble = { titres: [s1, s2].map((s) => s.querySelector('.mp-titre').id),
                     choix: [s1, s2].map((s) => s.querySelector('.mp-choix').id),
                     doublons: ids.filter((x, i) => ids.indexOf(x) !== i) };
  // UN geste, UNE réponse : un montage remplacé mais resté branché répondrait lui aussi.
  s1.querySelector('.mp-faire-entrer').click();
  const reponses = window.__messages;
  const focus = window.__b.focaliser() && document.activeElement === s2.querySelector('.mp-titre');
  window.__a.demonter();                                      // un montage REMPLACÉ : sans effet
  const intacte = s1.querySelectorAll('.mp-titre').length;
  window.__b.demonter();
  const rendue = { vide: s2.innerHTML === '', classe: s2.className,
                   nomme: s2.getAttribute('aria-labelledby'), projet: s2.dataset.mp || null };
  let hors = null;
  try { BDMembresProjet.monter(document.createElement('section'), { projet }); }
  catch (e) { hors = e.message; }
  s1.remove(); s2.remove();
  return { ensemble, reponses, focus, intacte, rendue, hors };
}"""


def test_le_module_tient_son_contrat_de_montage(page, live_server):
    """Les règles d'un module montable, jouées sur celui des membres : il INVESTIT la cible ;
    monter deux fois au même endroit REMPLACE — le montage d'avant rend son identifiant et
    ne répond plus aux gestes — ; trois montages vivants du même projet — la fiche de l'hôte
    et deux autres — ne partagent aucun identifiant ; `demonter` rend la cible vide et sans
    ce qu'il y a posé ; le démontage d'un montage déjà remplacé ne vide pas son successeur ;
    et une cible hors du document lève au lieu de se taire."""
    repli = _repli(live_server)
    projet = {"id": repli, "nom": "Le projet", "gerable": True}
    page.goto(live_server + "/administration", wait_until="networkidle")
    page.locator("#pj-fiche .mp-choix").wait_for(timeout=5000)
    r = page.evaluate(_MONTER, projet)
    # La fiche de l'hôte tient le suffixe nu : le premier montage vivant du projet.
    assert r["investie"] == {"classe": True, "nomme": f"mp-titre-{repli}m2", "titres": 1}, r
    assert r["remplacee"] == 1, "monter deux fois au même endroit a empilé deux parties"
    page.wait_for_function("() => window.__s1.querySelector('.mp-choix')"
                           " && window.__s2.querySelector('.mp-choix')")
    r = page.evaluate(_DEMONTER, projet)
    # Le montage remplacé a RENDU son suffixe : son successeur le reprend, il ne dérive pas.
    assert r["ensemble"]["titres"] == [f"mp-titre-{repli}m2", f"mp-titre-{repli}m3"], r
    assert r["ensemble"]["choix"] == [f"mp-choix-{repli}m2", f"mp-choix-{repli}m3"], r
    assert not r["ensemble"]["doublons"], f"identifiants en double : {r['ensemble']['doublons']}"
    assert r["reponses"] == 1, (
        f"un seul clic sur « + Faire entrer » a écrit {r['reponses']} messages : le montage "
        "remplacé est resté branché sur la section")
    assert r["focus"], "`focaliser` ne mène pas au titre de la partie"
    assert r["intacte"] == 1, "un montage remplacé a vidé son successeur en se démontant"
    assert r["rendue"] == {"vide": True, "classe": "", "nomme": None, "projet": None}, r["rendue"]
    assert r["hors"] and "dans le document" in r["hors"], r["hors"]
    assert page.locator(f"#pj-fiche #mp-titre-{repli}").count() == 1


def test_sans_le_droit_de_regler_le_module_le_dit_et_ne_lit_rien(page, live_server):
    """La garde est celle de l'ACTE : monté pour un projet qu'on ne gère pas, le module le
    DIT — et ne demande pas la liste des membres, que le serveur lui refuserait. Aucun hôte
    ne le monte ainsi aujourd'hui ; le prochain le pourra, et c'est le module qui répond."""
    repli = _repli(live_server)
    page.goto(live_server + "/administration", wait_until="networkidle")
    page.locator("#pj-fiche .mp-titre").wait_for(timeout=5000)
    demandes = []
    page.on("request", lambda q: demandes.append(q.url))
    r = page.evaluate("""(projet) => {
      const s = document.createElement('section');
      document.getElementById('admin-body').appendChild(s);
      const p = BDMembresProjet.monter(s, { projet, groupesAdmin: ['bd-admins'] });
      const vu = { texte: s.textContent.replace(/\\s+/g, ' ').trim(), focus: p.focaliser(),
                   ajout: s.querySelectorAll('.mp-faire-entrer, .mp-choix').length };
      p.demonter();
      vu.vide = s.innerHTML === '';
      s.remove();
      return vu;
    }""", {"id": repli, "nom": "Le projet", "gerable": False})
    page.wait_for_timeout(300)
    assert r["texte"].startswith("Seul un responsable du projet voit et règle qui y entre."), r
    assert "bd-admins" in r["texte"], r["texte"]
    assert r["ajout"] == 0 and r["focus"] is False and r["vide"] is True, r
    assert not [u for u in demandes if "/api/" in u and "/membres" in u], demandes


# ── À l'étroit et à grande police ───────────────────────────────────────────────────────

# Le nom tel qu'il est dessiné : entier, sur une ligne, dans la fenêtre et dans la bande.
# Le TÉMOIN d'une ligne est mesuré, pas recopié — un clone hors flux, forcé sur une ligne
# (le procédé de `test_e2e_police._BANDES`).
_NOM = """(fonte) => {
  if (fonte) document.body.style.fontFamily = fonte;
  const R = (e) => e.getBoundingClientRect();
  const nav = document.getElementById('site-nav'), w = nav.querySelector('.projet-courant');
  const c = w.querySelector('#projet-nom, #projet-choix');
  const st = getComputedStyle(c), n = R(nav), b = R(c), h = document.getElementById('header');
  const clone = c.cloneNode(true);
  clone.removeAttribute('id');
  clone.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;' +
                        'width:max-content;max-width:none;overflow:visible';
  c.parentNode.appendChild(clone);
  const temoin = R(clone);
  clone.remove();
  const bas = [...nav.children].map(R).filter((x) => x.width > 0 && x.height > 0)
    .reduce((m, x) => Math.max(m, x.bottom), n.bottom);
  return {
    texte: c.tagName === 'SELECT' ? c.options[c.selectedIndex].textContent : c.textContent,
    options: c.tagName === 'SELECT' ? [...c.options].map((o) => o.textContent) : null,
    // Un `<select>` a le débordement que son navigateur lui donne : on ne le lit que du nom.
    ellipse: st.textOverflow, blanc: st.whiteSpace,
    debordement: c.tagName === 'SELECT' ? 'visible' : st.overflowX,
    rogne: [c, w].filter((e) => e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 0).length,
    largeur: b.width, naturel: temoin.width, haut: b.height, ligne: temoin.height,
    gauche: b.left, droite: b.right, fenetre: document.documentElement.clientWidth,
    dansLaBande: b.left >= n.left - 1 && b.right <= n.right + 1
                 && b.top >= n.top - 1 && b.bottom <= n.bottom + 1,
    recouvre: h ? Math.round(bas - R(h).top) : 0,
    racine: getComputedStyle(document.documentElement).fontSize,
  };
}"""


def _defauts_du_nom(m, attendu):
    """Ce qu'une mesure de `_NOM` a de fautif — vide si le nom est dessiné entier."""
    out = []
    if m["texte"] != attendu:
        out.append(f"le nom affiché est « {m['texte']} », pas « {attendu} »")
    if m["ellipse"] == "ellipsis" or m["debordement"] not in ("visible", "clip") or m["rogne"]:
        out.append(f"le nom est ROGNÉ (text-overflow {m['ellipse']}, overflow "
                   f"{m['debordement']}, {m['rogne']} boîte(s) plus étroite(s) que son contenu)")
    if m["largeur"] < m["naturel"] - 1:
        out.append(f"le nom est RÉTRÉCI : {m['largeur']:.0f} px pour {m['naturel']:.0f} "
                   "sur une ligne")
    if m["haut"] > m["ligne"] * 1.25:
        out.append(f"le nom est PLIÉ : {m['haut']:.0f} px de haut pour {m['ligne']:.0f} "
                   "sur une ligne")
    if m["gauche"] < -1 or m["droite"] > m["fenetre"] + 1:
        out.append(f"le nom sort de la fenêtre : de {m['gauche']:.0f} à {m['droite']:.0f} px "
                   f"pour {m['fenetre']}")
    if not m["dansLaBande"]:
        out.append("le nom sort de la bande du haut")
    if m["recouvre"] > 1:
        out.append(f"la bande 1 recouvre la bande 2 de {m['recouvre']} px")
    return out


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("forme", ["le nom seul", "le sélecteur"])
def test_le_nom_le_plus_long_ne_se_coupe_pas_a_320_px(page, live_server, forme):
    """Le nom le plus long qu'un projet puisse porter, en capitales, à 320 px de large, sous
    trois préférences de police, dans la police du poste puis dans celle de l'image : entier,
    sur une ligne, dans la fenêtre — et rien ne se chevauche ni ne sort dans la bande, sur
    les cinq surfaces. La bande est celle de PRODUCTION : la pastille à son nom le plus long,
    son menu, et « ← Retour ».

    Les deux formes : le nom seul, puis le sélecteur dès qu'un second projet existe — qui
    porte, lui, le nom le plus long en minuscules. Le sélecteur prend la largeur de sa plus
    longue option, et c'est la forme qui a le moins de place : elle a fixé le plafond.

    Les fautes sont rassemblées avant d'échouer : la carte de ce qui casse dit le mécanisme.
    """
    repli = _repli(live_server)
    _api(live_server, "PATCH", f"/api/projets/{repli}", {"nom": NOM_CAPITALES})
    if forme == "le sélecteur":
        _projet(live_server, NOM_MINUSCULES)
    page.set_extra_http_headers(IDENTITE_LONGUE)
    echecs = []
    for police in _polices(page):
        _preference_police(page, police)
        page.set_viewport_size({"width": 320, "height": 900})
        for surface in SURFACES_AUDITEES:
            page.goto(f"{live_server}{surface}?{RETOUR}", wait_until="networkidle")
            page.locator(".user-chip .user-logout").wait_for(state="attached", timeout=5000)
            page.locator(".projet-courant").wait_for(timeout=5000)
            assert (page.locator("#projet-choix").count() == 1) == (forme == "le sélecteur")
            for fonte in FONTES:
                cas = (f"{surface}, {forme}, police {police or 'du lancement'}, "
                       f"{fonte or 'police du poste'}")
                m = page.evaluate(_NOM, fonte)
                page.wait_for_timeout(50)
                m = page.evaluate(_NOM, fonte)
                fautes = _defauts_du_nom(m, NOM_CAPITALES)
                if m["options"] is not None and m["options"] != [NOM_CAPITALES, NOM_MINUSCULES]:
                    fautes.append(f"le sélecteur propose {m['options']}")
                perdus = [c for c in page.evaluate(SONDE)["coupables"]
                          if not c["cadre"] and c["id"] != "canvas"]
                fautes += [f"<{c['tag']}>#{c['id']}.{c['cls']} sort de la fenêtre de "
                           f"{c['depasse']} px {c['sens']}" for c in perdus]
                fautes += decrire_ecrasement(page.evaluate(ECRASEMENT, "#site-nav"))
                echecs += [f"{cas} : {f}" for f in fautes]
    assert not echecs, "Le nom du projet, à 320 px :\n" + "\n".join(echecs)


# Les largeurs de `test_e2e_reflow.LARGEURS_BANDE` : la bande a déjà cassé ENTRE ses seuils,
# à des largeurs que personne n'avait visitées.
LARGEURS_BANDE = (320, 375, 480, 560, 640, 720, 900, 1024, 1280)


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("forme", ["le nom seul", "le sélecteur"])
def test_le_nom_le_plus_long_tient_de_320_a_1280_px(page, live_server, forme):
    """Le même nom, le même décor de production, mais ENTRE les largeurs : c'est à 320 px que
    la place manque le plus, et c'est entre deux seuils qu'une bande se casse sans prévenir.
    De 320 à 1280 px, sous trois préférences et dans les deux polices, le nom reste entier et
    sur une ligne, rien ne sort de la fenêtre, et rien ne se chevauche dans la bande.

    La page n'est chargée qu'une fois par préférence et par surface, puis redimensionnée :
    cinq cent quarante mesures pour trente chargements."""
    repli = _repli(live_server)
    _api(live_server, "PATCH", f"/api/projets/{repli}", {"nom": NOM_CAPITALES})
    if forme == "le sélecteur":
        _projet(live_server, NOM_MINUSCULES)
    page.set_extra_http_headers(IDENTITE_LONGUE)
    echecs = []
    for police in _polices(page):
        _preference_police(page, police)
        for surface in SURFACES_AUDITEES:
            page.set_viewport_size({"width": LARGEURS_BANDE[-1], "height": 900})
            page.goto(f"{live_server}{surface}?{RETOUR}", wait_until="networkidle")
            page.locator(".user-chip .user-logout").wait_for(state="attached", timeout=5000)
            page.locator(".projet-courant").wait_for(timeout=5000)
            for fonte in FONTES:
                for largeur in LARGEURS_BANDE:
                    page.set_viewport_size({"width": largeur, "height": 900})
                    # Redimensionné, et FINI de bouger : les tiroirs de l'Atelier glissent en
                    # franchissant leur seuil, et un rectangle pris en plein vol se lirait
                    # comme un panneau à moitié sorti de la fenêtre.
                    page.wait_for_function(
                        "(l) => window.innerWidth === l && document.getAnimations()"
                        ".every((a) => a.playState !== 'running')", arg=largeur)
                    cas = (f"{surface}, {forme}, {largeur} px, police "
                           f"{police or 'du lancement'}, {fonte or 'police du poste'}")
                    fautes = _defauts_du_nom(page.evaluate(_NOM, fonte), NOM_CAPITALES)
                    perdus = [c for c in page.evaluate(SONDE)["coupables"]
                              if not c["cadre"] and c["id"] != "canvas"]
                    fautes += [f"<{c['tag']}>#{c['id']}.{c['cls']} sort de la fenêtre de "
                               f"{c['depasse']} px {c['sens']}" for c in perdus]
                    fautes += decrire_ecrasement(page.evaluate(ECRASEMENT, "#site-nav"))
                    echecs += [f"{cas} : {f}" for f in fautes]
    assert not echecs, "Le nom du projet, de 320 à 1280 px :\n" + "\n".join(echecs)


def test_un_nom_trop_large_deborde_et_ne_se_plie_pas(page, live_server):
    """Ce que la feuille promet d'un nom que la bande ne peut PAS contenir — il n'en existe
    pas sous le plafond, on l'écrit donc dans la page : il reste sur UNE ligne, et l'audit de
    reflow le VOIT sortir. Replié sur deux lignes, il tiendrait dans la fenêtre et aucune
    sonde ne dirait rien : c'est le défaut de `.surf-link`, que le `nowrap` existe pour
    interdire."""
    page.set_viewport_size({"width": 320, "height": 900})
    page.goto(live_server + "/corpus", wait_until="networkidle")
    page.locator("#projet-nom").wait_for(timeout=5000)
    page.evaluate("() => { document.getElementById('projet-nom').textContent = "
                  "'Un nom que rien ne borne et qui ne tient dans aucune bande'; }")
    m = page.evaluate(_NOM, None)
    assert m["blanc"] == "nowrap", f"le nom n'est plus en `nowrap` : {m['blanc']}"
    assert m["haut"] <= m["ligne"] * 1.25, (
        f"le nom trop large se PLIE ({m['haut']:.0f} px pour {m['ligne']:.0f} sur une ligne) "
        "au lieu de déborder : plus aucun audit ne le verrait")
    vu = ([c for c in page.evaluate(SONDE)["coupables"] if not c["cadre"]]
          or decrire_ecrasement(page.evaluate(ECRASEMENT, "#site-nav")))
    assert vu, "un nom plus large que la bande n'est signalé par aucune des deux sondes"


_CORPS_QUI_DEFILE = """() => [document.documentElement, document.body,
                              ...document.querySelectorAll('main')]
  .map((el) => ({ nom: el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''),
                  clientW: el.clientWidth, scrollW: el.scrollWidth }))
  .filter((v) => v.scrollW > v.clientW + 1)"""


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_le_bloc_des_projets_tient_a_320_px(page, seminaire):
    """Le bloc de l'Administration, PEUPLÉ, à 320 px : une fiche avec ses membres — un nom
    long, un inconnu de l'annuaire —, sa justification, la saisie libre ouverte. Aucun
    élément ne sort, rien ne tient par un cadre qui défile, et le corps de la page ne défile
    pas de côté. Les audits de reflow visitent cette page ; ils n'y trouvent qu'un bloc vide."""
    d = seminaire
    _api(d["base"], "PATCH", f"/api/projets/{d['projet']}", {
        "nom": NOM_MINUSCULES,
        "justification": "Comparer le lettrage de deux éditions, planche à planche : "
                         "https://exemple.invalid/une/adresse/tres/longue/sans/aucun/espace"})
    _membre(d["base"], d["projet"], "proprio", "responsable")
    _membre(d["base"], d["projet"], "ancien-cours-de-bande-dessinee-2025", genre="groupe")
    _membre(d["base"], d["projet"], "etudiants-bd-2026", genre="groupe")
    page.set_extra_http_headers(ADMIN_BD)
    echecs = []
    for police in _polices(page):
        _preference_police(page, police)
        page.set_viewport_size({"width": 320, "height": 900})
        page.goto(d["base"] + "/administration", wait_until="networkidle")
        page.locator(f'#pj-objets .pj-objet[data-pj="{d["projet"]}"]').click()
        partie = _fiche(page).locator("section.mp")
        partie.locator(".mp-ligne").nth(2).wait_for(timeout=5000)
        partie.locator(".mp-marque").first.wait_for(timeout=5000)
        partie.locator(".mp-choix").select_option("autre")
        page.wait_for_timeout(150)
        r = page.evaluate(SONDE)
        cas = f"police {police or 'du lancement'}"
        # Perdu, ou tenu par un cadre du BLOC : les deux sont des fautes ici. Un cadre d'un
        # autre bloc de la page n'est pas l'affaire de ce test.
        echecs += [f"{cas} : <{c['tag']}>#{c['id']}.{c['cls']} — {c['largeur']} px, dépasse de "
                   f"{c['depasse']} px {c['sens']}" + (f" (dans {c['cadre']})" if c["cadre"] else "")
                   for c in r["coupables"]
                   if not c["cadre"] or str(c["cadre"]).startswith((".pj", "#pj", ".mp"))]
        echecs += [f"{cas} : {x['nom']} défile de côté ({x['clientW']} px visibles pour "
                   f"{x['scrollW']})" for x in page.evaluate(_CORPS_QUI_DEFILE)]
        echecs += [f"{cas} : {x}" for x in decrire_ecrasement(
            page.evaluate(ECRASEMENT, "#projets-bloc"))]
    assert not echecs, "Le bloc des projets, à 320 px :\n" + "\n".join(echecs)


# ── Accessibilité : ce que les audits des surfaces ne rendent pas ───────────────────────

_AXE = Path(__file__).parent / "js" / "vendor" / "axe.min.js"
_AXE_RUN = """async () => {
  const r = await axe.run(document, {runOnly:{type:'tag',
    values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}});
  return r.violations
    .filter(v => v.impact === 'serious' || v.impact === 'critical')
    .map(v => v.id + ' — ' + v.help + ' : ' + v.nodes.slice(0, 5).map(n => n.target.join(' ')).join(' | ')); }"""


@pytest.mark.skipif(not _AXE.exists(), reason="axe-core absent (cf. tests/js/vendor/README.md)")
@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_le_selecteur_et_le_bloc_peuple(page, seminaire, theme):
    """axe sur ce que `test_e2e_a11y` ne rend pas : la bande avec son SÉLECTEUR (il n'existe
    qu'à deux projets), et le bloc des projets avec une fiche peuplée, un refus affiché et la
    saisie libre ouverte. Aucune violation sérieuse ou critique, dans les deux thèmes."""
    d = seminaire
    _membre(d["base"], d["projet"], "proprio", "responsable")
    _membre(d["base"], d["projet"], "ancien-cours", genre="groupe")
    page.add_init_script(f"localStorage.setItem('bd-theme','{theme}')")
    partie = _ouvrir_la_fiche(page, d)
    page.locator("#projet-choix").wait_for(timeout=5000)
    partie.locator(".mp-marque").first.wait_for(timeout=5000)
    partie.locator(".mp-choix").select_option("autre")
    partie.locator(".mp-faire-entrer").click()
    partie.locator(".mp-msg.erreur").wait_for(timeout=3000)
    page.evaluate(_AXE.read_text(encoding="utf-8"))
    violations = page.evaluate(_AXE_RUN)
    assert not violations, f"/administration, bloc des projets [{theme}] :\n" + "\n".join(violations)

    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    page.locator("#collections-projet").wait_for(timeout=5000)
    page.evaluate(_AXE.read_text(encoding="utf-8"))
    violations = page.evaluate(_AXE_RUN)
    assert not violations, f"/corpus, deux projets [{theme}] :\n" + "\n".join(violations)


@pytest.mark.skipif(not _AXE.exists(), reason="axe-core absent (cf. tests/js/vendor/README.md)")
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_les_listes_d_un_album_et_ce_qu_elles_disent(page, deux_projets, tmp_path, theme):
    """axe sur la modale d'album dans les états que cette tranche lui donne, et qu'aucun autre
    audit ne rend : la fiche d'un album rangé dans deux projets — sa ligne en ALERTE —, la
    liste d'un nouvel album avec sa note, et le projet où l'on n'écrit nulle part. Aucune
    violation sérieuse ou critique, dans les deux thèmes."""
    d = deux_projets
    album = _album(d["base"], "Album à cheval", d["b1"])
    base = sqlite3.connect(tmp_path / "live.sqlite", timeout=10)
    with base:
        base.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                     (d["a1"], album))
    base.close()
    page.add_init_script(f"localStorage.setItem('bd-theme','{theme}')")
    _bibliotheque(page, d["base"])
    axe = _AXE.read_text(encoding="utf-8")
    page.evaluate(axe)

    def auditer(etat):
        violations = page.evaluate(_AXE_RUN)
        assert not violations, f"/corpus, {etat} [{theme}] :\n" + "\n".join(violations)

    _fiche_de_l_album(page, "Album à cheval")
    expect(page.locator("#m-appartenance-projet.alerte")).to_be_visible()
    auditer("la fiche d'un album de deux projets")
    page.locator("#m-cancel").click()

    _nouvel_album(page)
    expect(page.locator("#m-collection-note")).to_be_visible()
    auditer("un nouvel album, liste bornée au projet")
    page.locator("#m-cancel").click()

    _changer_de_projet(page, d["vide"], "Projet sans rien")
    _nouvel_album(page)
    expect(page.locator("#m-collection-wrap")).to_be_hidden()
    page.locator("#m-titre").fill("Sans collection")
    page.locator("#m-save").click()
    expect(page.locator("#m-msg")).to_contain_text("Aucune collection ne peut accueillir")
    auditer("un nouvel album, aucune collection où écrire dans le projet")
