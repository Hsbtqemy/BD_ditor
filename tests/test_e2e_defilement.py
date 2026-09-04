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
