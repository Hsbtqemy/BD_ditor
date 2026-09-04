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

from conftest import ADMIN, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# La Visionneuse est absente à dessein : sa coque distribue le défilement entre plusieurs
# bandes (arbre, canevas, panneau), et il n'existe pas UN cadre à désigner. Elle a sa
# propre question, ouverte dans UX-7.
SURFACES = [("/recherche", "#search-body"),
            ("/corpus", "#corpus-body"),
            ("/exploration", "#explo-body")]

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
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=180, headers=ADMIN)
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


@pytest.mark.parametrize("chemin, cadre", SURFACES)
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
    """
    page.set_viewport_size({"width": 1100, "height": 400})
    page.goto(corpus_dense + "/exploration", wait_until="networkidle")

    r = page.evaluate("""() => {
      const e = document.getElementById('explo-body');
      if (e.scrollHeight <= e.clientHeight + 1) return { deborde: false };
      e.scrollTop = 99999;
      return { deborde: true, atteint: Math.round(e.scrollTop),
               attendu: Math.round(e.scrollHeight - e.clientHeight) };
    }""")
    assert r["deborde"], "la fenêtre de 400 px devrait forcer un débordement"
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
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=60, headers=ADMIN)
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
