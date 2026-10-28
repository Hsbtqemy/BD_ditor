"""Aucune surface ne CLIPPE son contenu — le défaut trouvé le 2026-09-04.

`static/style.css` pose `html, body { overflow: hidden }`, ce dont la Visionneuse a
besoin : c'est une coque pleine hauteur, dont chaque bande gère son propre défilement.
La contrepartie est brutale et silencieuse — toute surface qui n'installe pas son propre
cadre de défilement voit son contenu COUPÉ. Pas repoussé, pas défilable : absent.

C'est ce qui est arrivé à l'Exploration. `#explo-app` n'avait ni hauteur ni cadre, là où
`#search-app` et `#corpus-app` en ont un depuis toujours. Résultat mesuré sur un écran de
1080 px, en usage parfaitement ordinaire : **1 285 px de contenu inatteignables**, sans
barre de défilement, la molette sans effet. Aucun test ne l'a vu — Playwright considère
« visible » un élément qui a une boîte, quand bien même un ancêtre le clippe, et axe ne
mesure rien de tel.

Ce fichier garde la PROPRIÉTÉ plutôt que le symptôme : chaque surface-document doit
posséder un cadre qui défile. Un test qui se contenterait de vérifier « ça défile avec le
corpus de démonstration » verdirait le jour où le décor rétrécit.

Marqué `e2e` → hors du run par défaut (`pytest -m e2e`).
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# La Visionneuse est absente à dessein : sa coque distribue le défilement entre plusieurs
# bandes (arbre, canevas, panneau), et il n'existe pas UN cadre à désigner. Elle a sa
# propre question, ouverte dans UX-7.
# UX-10 — LA liste de cet audit, et elle sert de déclaration : `tests/test_surfaces.py`
# la confronte aux surfaces réellement servies. C'est la MÊME structure que le test
# parcourt, pas une copie posée à côté — une déclaration jumelle dériverait de sa liste
# sans que rien ne le dise, ce qui a été mesuré le 2026-09-07 sur un premier jet.
SURFACES_AUDITEES = {"/recherche": "#search-body",
                     "/corpus": "#corpus-body",
                     "/exploration": "#explo-body",
                     "/administration": "#admin-body"}
SURFACES_HORS_PERIMETRE = {
    "/annotation": (
        "comme l'Atelier, une coque à colonnes de hauteur stable et non un corps "
        "qui défile : chaque colonne porte son propre cadre, et ce qui reste "
        "atteignable à 320 px est ce que mesurent `test_e2e_reflow` et "
        "`test_e2e_police`, qui l'auditent"),
    "/": "la Visionneuse est un canevas de pan/zoom : son cadre ne DOIT pas défiler, et "
         "l'y soumettre inventerait un défaut. Même exemption que `test_e2e_reflow`, et "
         "elle vient du 1.4.10 lui-même.",
}

SONDE = """(sel) => {
  const el = document.querySelector(sel);
  if (!el) return { absent: true };
  const st = getComputedStyle(el);
  return {
    absent: false,
    defilable: /(auto|scroll)/.test(st.overflowY),
    trop_long: el.scrollHeight > el.clientHeight + 1,
    hauteur: el.clientHeight,
    contenu: el.scrollHeight,
    // Un cadre qui ne défile pas et dont un ancêtre clippe : le pire cas, celui qu'on
    // vient de corriger. On le calcule ici plutôt que de le déduire à la lecture.
    racine_clippe: getComputedStyle(document.body).overflowY === "hidden",
  };
}"""


@pytest.fixture
def corpus_dense(live_server):
    """Assez de contenu pour dépasser une fenêtre courte — sinon rien ne déborderait et
    le test mesurerait le vide."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=180, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "Défilement"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        for i in range(12):
            rid = c.post(f"/api/planches/{pid}/regions",
                         json={"type": "bulle", "x": 10 * i, "y": 10 * i,
                               "w": 40, "h": 30}).json()["id"]
            c.put(f"/api/regions/{rid}", json={"ocr_texte": f"REPLIQUE NUMERO {i} POUVOIR"})
    finally:
        c.close()
    return live_server


@pytest.mark.parametrize("chemin, cadre", SURFACES_AUDITEES.items())
def test_chaque_surface_document_possede_un_cadre_qui_defile(page, corpus_dense,
                                                             chemin, cadre):
    """La propriété, indépendamment du décor : le cadre EXISTE et il défile.

    Affirmée sans condition — c'est ce qui distingue ce test d'une observation. Un cadre
    dont `overflow-y` est `visible` sous un `body` clippé perd son contenu dès qu'il y en
    a, et la quantité de contenu ne doit pas décider si le test passe.
    """
    page.goto(corpus_dense + chemin, wait_until="networkidle")
    r = page.evaluate(SONDE, cadre)
    assert not r["absent"], f"{cadre} n'existe pas sur {chemin}"
    assert r["racine_clippe"], (
        "le `body` ne clippe plus : ce test garde une contrainte qui n'existe plus, "
        "et il faut le relire plutôt que le laisser passer au vert pour rien")
    assert r["defilable"], (
        f"{cadre} n'a pas de défilement propre alors que le `body` clippe : tout ce qui "
        f"dépasse la fenêtre sur {chemin} est INATTEIGNABLE, sans barre ni molette. "
        "C'est le défaut mesuré le 2026-09-04 sur l'Exploration.")


def test_le_contenu_du_bas_est_vraiment_atteignable(page, corpus_dense):
    """Et pas seulement « un cadre est déclaré défilable » : on va CHERCHER le bas.

    Une fenêtre courte force le débordement quel que soit le corpus. Sans ce test, une
    règle CSS qui déclare `overflow-y: auto` sur un conteneur de hauteur libre — donc qui
    ne défile jamais — passerait la garde précédente.

    440 px de haut et non plus 400 (2026-10-15) : sous 27em, c'est la PAGE qui défile, et
    ce test garde le CADRE (cf. `test_les_bandes_du_haut_ne_mangent_pas_l_ecran`). 440 px
    font 27,5em, juste au-dessus du seuil de hauteur, et forcent encore le débordement.
    """
    page.set_viewport_size({"width": 1100, "height": 440})
    page.goto(corpus_dense + "/exploration", wait_until="networkidle")

    r = page.evaluate("""() => {
      const e = document.getElementById('explo-body');
      if (e.scrollHeight <= e.clientHeight + 1) return { deborde: false };
      e.scrollTop = 99999;
      return { deborde: true, atteint: Math.round(e.scrollTop),
               attendu: Math.round(e.scrollHeight - e.clientHeight) };
    }""")
    assert r["deborde"], "la fenêtre de 440 px devrait forcer un débordement"
    assert r["atteint"] >= r["attendu"] - 2, (
        f"le bas du contenu reste hors de portée : {r['atteint']} sur {r['attendu']} px")


# ── Les bandes COLLANTES que ce cadre vient d'activer ────────────────────────────────
#
# `position: sticky` se cale sur l'ancêtre DÉFILANT le plus proche — et `.croise` porte
# `overflow-x: auto`, ce qui en fait un conteneur de défilement pour les DEUX axes. C'est
# donc lui l'ancêtre, pas le cadre de page. Conséquence mesurée le 2026-09-04, et elle
# coupe le tableau croisé en deux : le collage HORIZONTAL marche (`.croise` défile bien de
# ce côté), le collage VERTICAL est inerte et l'a toujours été (`.croise` a la hauteur de
# son contenu, donc il ne défile jamais verticalement — un thead à `top: 0` n'a rien à
# quoi se caler). Ce fichier ne garde que le premier ; le second est un constat ouvert de
# UX-7, parce que le réparer demande d'arbitrer un cadre de défilement imbriqué.
#
# Ce que la QA du 2026-09-04 a trouvé, c'est que le COIN était RECOUVERT quand on défile
# vers la droite : il déclarait `z-index: 3` et en recevait 2, `.croise-table thead th`
# (spécificité 0-1-2) l'emportant sur `.croise-corner` (0-1-0). Il collait au bon pixel,
# mais à égalité avec les en-têtes de colonnes, qui le SUIVENT dans le DOM et passaient
# donc par-dessus.
#
# Le décor est FABRIQUÉ — le vrai tableau demande des tokens spaCy, moteur optionnel, et
# une garde de CSS n'a pas à se taire quand un moteur manque. Il est donc épinglé sur la
# réponse réelle (test suivant), et RENDU par `renderCroise` elle-même : le balisage vient
# du code de production, pas de moi.

FAUX_CROISEMENT = {
    "axe_x": "pos", "axe_y": "morph", "filtre_x": "pos", "filtre_y": "morph",
    "libelle_x": "catégorie (POS)", "libelle_y": "morphologie",
    "x": [{"cle": f"POS{i}", "libelle": f"POS{i}", "total": 10 - i} for i in range(8)],
    "y": [{"cle": f"M{j}", "libelle": f"Morphologie tres longue numero {j}",
           "total": 20 - j} for j in range(20)],
    "grille": [[(i + j) % 7 for j in range(20)] for i in range(8)],
    "total": 400, "x_tronque": False, "y_tronque": True,
}


def test_le_decor_du_croisement_a_la_forme_de_la_vraie_reponse(live_server):
    """Le semis est épinglé, sinon la garde suivante mesurerait une page imaginaire.

    Égalité STRICTE des clés, dans les deux sens : une clé que la route ajouterait sans
    que le décor la porte ferait diverger le rendu en silence, et une clé que le décor
    invente ferait croire à une couverture qui n'existe pas. C'est le mode d'échec du
    semis, celui que `test_sorties_identite` nomme déjà.
    """
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=60, headers=ECRITURE)
    try:
        r = c.get("/api/analyse/croisement", params={"axe_x": "pos", "axe_y": "morph"})
    finally:
        c.close()
    assert r.status_code == 200, r.text
    assert set(r.json()) == set(FAUX_CROISEMENT), (
        "la réponse de /api/analyse/croisement n'a plus la forme du décor : "
        f"en trop {set(r.json()) - set(FAUX_CROISEMENT)}, "
        f"manquantes {set(FAUX_CROISEMENT) - set(r.json())}")


def test_le_coin_du_tableau_croise_passe_au_dessus_des_deux_bandes(page, live_server):
    """Le coin rejoint DEUX bandes collantes : il doit passer au-dessus des deux.

    On mesure ce qui se voit — `elementFromPoint` en son centre — et non la feuille : à
    z-index égal c'est l'ordre du DOM qui tranche, et une lecture du CSS ne le dit pas.
    """
    page.set_viewport_size({"width": 700, "height": 500})
    page.goto(live_server + "/exploration", wait_until="networkidle")
    page.evaluate("(res) => { document.getElementById('croise').hidden = false; "
                  "renderCroise(res); }", FAUX_CROISEMENT)
    page.wait_for_selector(".croise-table")

    r = page.evaluate("""() => {
      const cadre = document.querySelector('.croise');
      const page_ = document.getElementById('explo-body');
      cadre.scrollLeft = 99999;          // les 20 colonnes du décor forcent le débordement
      page_.scrollTop = 99999;
      const coin = document.querySelector('.croise-corner');
      const b = coin.getBoundingClientRect();
      const dessus = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2);
      const z = (sel) => getComputedStyle(document.querySelector(sel)).zIndex;
      return {
        deborde: cadre.scrollLeft > 0,
        recouvert: !(dessus === coin || coin.contains(dessus)),
        intrus: dessus ? (dessus.className || dessus.tagName) + ' « '
                       + dessus.textContent.slice(0, 40) + ' »' : 'rien',
        z_coin: z('.croise-corner'),
        z_colonne: getComputedStyle(
          document.querySelectorAll('.croise-table thead th')[1]).zIndex,
        z_ligne: z('.croise-table tbody th[scope="row"]'),
      };
    }""")
    assert r["deborde"], (
        "le décor ne déborde plus horizontalement : la garde ne mesure alors rien, "
        "car le coin ne quitte jamais sa place")
    assert not r["recouvert"], (
        f"le coin du tableau croisé est RECOUVERT (z={r['z_coin']}, colonnes "
        f"{r['z_colonne']}, lignes {r['z_ligne']}) — au point où il devrait être, c'est "
        f"{r['intrus']} qu'on voit. Le libellé des deux axes disparaît dès qu'on défile.")


# ── Les bandes du haut ne doivent pas MANGER l'écran (A11Y-2, 2026-10-15) ────────────────
#
# Vu par Hugo sous Firefox, à 320 × 700 et une police portée à 24 : la navigation, enroulée
# sur plusieurs rangées, et l'en-tête de page prenaient presque toute la hauteur ; le cadre
# défilait dans une fente au bas de l'écran. Rien ici ne le voyait : les gardes ci-dessus
# demandent si le cadre EXISTE et si son bas s'ATTEINT, et il s'atteignait — dans la fente.
# La garde suivante mesure donc ce que l'œil voit : après qu'une main a fait défiler la
# page, quelle part de la fenêtre le contenu occupe.
#
# Le décor est celui de la production, où le défaut a été vu : derrière le proxy, la
# pastille du compte et deux projets — la liste prend la largeur de son nom le plus long,
# `CORPUS FRANCO-BELGE 2` (le nom ordinaire le plus large, cf. la passe de police).
#
# **Les deux navigateurs, et pas par symétrie** : c'est sous Firefox que le défaut a été
# vu, et la police s'y règle par une préférence de LANCEMENT — le protocole CDP qui la règle
# sous Chromium n'y existe pas. Le test lance donc lui-même chaque navigateur, une fois par
# police. Firefox absent (l'image n'installe que Chromium), son cas est sauté en le disant.

IDENTITE = {"Remote-User": "camille", "Remote-Name": "Camille Ferreira-Lopes",
            "Remote-Groups": "bd-admins"}
URL_DE = {"/recherche": "/recherche?q=pouvoir"}

# (largeur, hauteur, police) — la fenêtre de Hugo, et une fenêtre BASSE assez large pour
# que la navigation n'y prenne que deux rangées : c'est l'autre moitié du seuil, celle qu'on
# atteint sans téléphone. À 720 × 380 sous 20 — 36em de large, au-dessus du seuil de largeur,
# 19em de haut —, l'Administration n'y laissait que 38 % de la fenêtre au contenu.
FENETRES_ETROITES = [(320, 700, 24), (720, 380, 20)]
# Au large, RIEN ne change : les bandes restent sous la main, et c'est le cadre qui défile.
# 450 px de haut et non 900 : il faut que le cadre ait de quoi défiler, et à 600 encore
# l'Exploration du décor tient dans le sien. 28em de haut, 90em de large : au-dessus des
# deux seuils, et assez près de celui de hauteur pour qu'un seuil relevé s'y voie.
FENETRE_LARGE = (1440, 450, 16)

_MESURE_BANDES = """(cadre) => {
  const m = document.querySelector(cadre);
  const nav = document.getElementById('site-nav');
  if (!m || !nav) return null;
  const b = m.getBoundingClientRect(), vh = window.innerHeight;
  return {
    visible: Math.max(0, Math.min(b.bottom, vh) - Math.max(b.top, 0)),
    fenetre: vh,
    contenu: m.scrollHeight,
    haut_nav: nav.getBoundingClientRect().top,
    page: Math.round(scrollY),
    cadre: Math.round(m.scrollTop),
    racine: getComputedStyle(document.documentElement).fontSize,
    decor: !!document.querySelector('.user-chip') && !!document.querySelector('.projet-choix'),
  };
}"""


@pytest.fixture
def corpus_derriere_proxy(live_server):
    """Assez de contenu pour remplir plusieurs fenêtres, et un SECOND projet : avec un seul,
    la bande ne porte qu'un nom, et elle n'aurait pas la hauteur qu'elle a en production."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=180, headers=ECRITURE)
    try:
        for t in range(6):
            aid = c.post("/api/albums", json={"titre": f"Bandes {t}"}).json()["id"]
            pid = c.post(f"/api/albums/{aid}/import",
                         files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
            for i in range(4):
                rid = c.post(f"/api/planches/{pid}/regions",
                             json={"type": "bulle", "x": 10 + 30 * i, "y": 10 + 30 * i,
                                   "w": 40, "h": 30}).json()["id"]
                c.put(f"/api/regions/{rid}", json={"ocr_texte": f"POUVOIR NUMERO {i}"})
        assert c.post("/api/projets", json={"nom": "CORPUS FRANCO-BELGE 2"}).status_code == 201
    finally:
        c.close()
    return live_server


def _navigateur(playwright, nom, police):
    """Le navigateur, la police par défaut déjà portée à `police` — le réglage du lecteur,
    pas une feuille injectée (cf. `test_e2e_police`)."""
    if nom == "firefox":
        try:
            b = playwright.firefox.launch(firefox_user_prefs={
                "network.proxy.type": 0,       # le proxy du campus casserait le chargement
                "general.smoothScroll": False,  # la molette agit d'un coup, sans animation
                "font.size.variable.x-western": police,
                "font.size.monospace.x-western": police})
        except Exception as e:                 # pragma: no cover — dépend du poste
            pytest.skip(f"Firefox de Playwright absent : {str(e).splitlines()[0]}")
        return b, b.new_context(extra_http_headers=IDENTITE).new_page()
    b = playwright.chromium.launch()
    page = b.new_context(extra_http_headers=IDENTITE).new_page()
    page.context.new_cdp_session(page).send(
        "Page.setFontSizes", {"fontSizes": {"standard": police, "fixed": police}})
    return b, page


def _defiler_a_la_main(page, base, chemin, cadre, largeur, hauteur):
    """La molette, posée au bas de la fenêtre, plusieurs crans : ce que fait une main. Pas
    de `scrollIntoView` — sous Chromium il fait défiler `html` même en `overflow: hidden`,
    un état qu'aucune main n'obtient (cf. `test_e2e_comptes_groupes`)."""
    page.set_viewport_size({"width": largeur, "height": hauteur})
    page.goto(base + URL_DE.get(chemin, chemin), wait_until="networkidle")
    page.wait_for_timeout(300)
    page.mouse.move(largeur / 2, hauteur - 20)
    for _ in range(8):
        page.mouse.wheel(0, 300)
        page.wait_for_timeout(60)
    page.wait_for_timeout(400)
    return page.evaluate(_MESURE_BANDES, cadre)


@pytest.mark.parametrize("live_server", [True], indirect=True)
@pytest.mark.parametrize("navigateur", ["chromium", "firefox"])
def test_les_bandes_du_haut_ne_mangent_pas_l_ecran(playwright, corpus_derriere_proxy,
                                                    navigateur):
    """Fenêtre étroite ou basse : la page défilée, le contenu occupe au moins la MOITIÉ de
    la fenêtre. La moitié n'est pas un goût : c'est ce que le seuil de hauteur promet (cf.
    « Quand les bandes du haut mangent l'écran » dans `static/style.css`), et sous elle,
    les bandes prennent plus de place que ce qu'on est venu lire.

    Trois gardes d'amont avant le critère, pour qu'un rouge veuille dire « fente » et
    jamais « rien mesuré » : la police a pris, le décor de production est là, et le contenu
    est plus haut que la fenêtre — sans quoi un cadre court aurait le droit d'être court."""
    base = corpus_derriere_proxy
    echecs = []
    for largeur, hauteur, police in FENETRES_ETROITES:
        b, page = _navigateur(playwright, navigateur, police)
        try:
            for chemin, cadre in SURFACES_AUDITEES.items():
                cas = f"{navigateur}, {chemin}, {largeur} × {hauteur}, police {police}"
                m = _defiler_a_la_main(page, base, chemin, cadre, largeur, hauteur)
                assert m is not None, f"{cas} : {cadre} ou la navigation est absent"
                assert m["racine"] == f"{police * 0.8125:g}px", (
                    f"{cas} : racine à {m['racine']} — la préférence de police n'a pas pris")
                assert m["decor"], f"{cas} : pastille ou liste des projets absente"
                assert m["contenu"] > m["fenetre"], (
                    f"{cas} : {m['contenu']} px de contenu pour une fenêtre de "
                    f"{m['fenetre']} — le décor ne remplit plus la page, rien n'est mesuré")
                if m["visible"] < m["fenetre"] / 2:
                    echecs.append(
                        f"{cas} : le contenu n'occupe que {m['visible']:.0f} px sur "
                        f"{m['fenetre']} une fois la page défilée (navigation à "
                        f"y={m['haut_nav']:.0f}, page défilée de {m['page']} px)")
        finally:
            b.close()
    assert not echecs, ("Les bandes du haut mangent l'écran :\n  " + "\n  ".join(echecs))


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_au_large_les_bandes_restent_et_le_cadre_defile(playwright, corpus_derriere_proxy):
    """Le revers : au large, rien n'a changé. La molette fait défiler le CADRE, la page ne
    bouge pas, et la navigation reste en haut de la fenêtre. Sans ce test, un seuil qui
    basculerait partout passerait le précédent au vert."""
    largeur, hauteur, police = FENETRE_LARGE
    b, page = _navigateur(playwright, "chromium", police)
    try:
        for chemin, cadre in SURFACES_AUDITEES.items():
            m = _defiler_a_la_main(page, corpus_derriere_proxy, chemin, cadre,
                                   largeur, hauteur)
            cas = f"{chemin}, {largeur} × {hauteur}, police {police}"
            assert m["contenu"] > m["visible"] + 1, (
                f"{cas} : le contenu tient dans son cadre ({m}) — rien n'aurait défilé")
            assert m["page"] == 0 and m["haut_nav"] == 0, (
                f"{cas} : la PAGE a défilé ({m}) — au large, les bandes restent")
            assert m["cadre"] > 0, f"{cas} : le cadre n'a pas défilé sous la molette ({m})"
    finally:
        b.close()
