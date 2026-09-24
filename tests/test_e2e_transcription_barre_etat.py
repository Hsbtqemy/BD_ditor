"""La barre d'état décrit-elle encore le canevas qu'on ne voit plus ? (UX-15)

**Le constat, et il a d'abord été mal écrit.** Le mode Transcription pose un overlay qui
recouvre entièrement le canevas, et la barre d'état continuait d'afficher son zoom et les
coordonnées master sous le curseur. La fiche annonçait deux valeurs GELÉES ; la mesure du
2026-09-23 l'a réfutée. `#stat-zoom` ne bougeait plus, faute de nouveau zoom à dire — mais
`#stat-coords` SUIVAIT la souris, son écouteur vivant sur `window` et non sur le canevas,
et affichait les coordonnées master d'un point de la planche sans rapport avec ce qu'on
visait dans le panneau. Un chiffre faux qui bouge est plus crédible qu'un chiffre gelé, et
il était flanqué d'un « Mode : Transcription » parfaitement exact — c'est le voisinage qui
rend un indicateur croyable, et c'est ce que la fiche redoutait pour `#stat-mode`.

**La décision, prise par Hugo le 2026-09-24** : masquer les deux, arrêter le calcul, garder
`#stat-mode`, et REVENIR à jour en sortant.

**Ce que ce module mesure, et pourquoi il faut les deux moitiés.** Un test qui ne lirait
que l'affichage resterait vert si le calcul continuait derrière le masque : `textContent`
s'écrit aussi bien sur un élément masqué, et le coût — un `getScreenCTM()` par mouvement de
souris — resterait payé, prêt à faire revenir la valeur fausse le jour où l'on
réafficherait. La garde espionne donc `getScreenCTM` au niveau du prototype, et elle
commence par vérifier que l'espion VOIT quelque chose en mode Navigation : sans ce semis,
un compteur resté à zéro parce qu'on espionne le mauvais symbole rendrait le test vert en
ne mesurant rien. C'est la leçon du semis d'AUTH-5, transposée à un compteur.

**Et le retour se mesure sur une valeur qui a VRAIMENT changé sous l'overlay.** Le zoom du
canevas peut bouger pendant la Transcription sans qu'on le voie : `#tr-auto` enchaîne sur
la planche suivante, dont `selectPlanche` rappelle `fitView()`. Le décor donne donc aux
deux planches des tailles différentes, pour que « à jour » et « telle qu'avant l'entrée »
ne puissent pas être le même nombre. Sans cela, un retour qui recopierait une valeur mise
en cache à l'entrée passerait sans qu'on s'en aperçoive.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/recherche": "aucune barre d'état de canevas : la page n'a ni zoom ni coordonnées master",
    "/corpus": "aucune barre d'état de canevas : la page liste des albums, sans plan de travail",
    "/exploration": "aucune barre d'état de canevas : les panneaux d'analyse n'ont pas de canevas",
    "/administration": "aucune barre d'état de canevas : la page porte sur l'instance, pas sur une image",
}

# La marque neutre du gabarit : « rien n'a encore été mesuré » (`COORDS_NEUTRES` côté JS).
COORDS_NEUTRES = "—"
LARGEURS = [1280, 900]

# Deux planches de formats FRANCHEMENT différents, et l'écart est mesuré, pas espéré : à
# l'arrivée le lien profond centre sur la région et donne 407 %, tandis que la seconde
# planche s'AJUSTE à 117 %. Le premier essai prenait 600 × 700, dont l'ajustement tombe à
# 408 % — un point d'écart, que le moindre arrondi aurait effacé en rendant la mesure
# vacante. Un décor qui distingue de justesse ne distingue pas.
MASTERS = ((1200, 1600), (2400, 600))


@pytest.fixture
def album_deux_planches(live_server):
    """Deux planches d'une bulle chacune, de tailles différentes."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=60, headers=ECRITURE)
    out = {"base": live_server, "planches": []}
    try:
        aid = c.post("/api/albums", json={"titre": "E2E barre d'état"}).json()["id"]
        out["album"] = aid
        for i, (largeur, hauteur) in enumerate(MASTERS):
            pid = c.post(f"/api/albums/{aid}/import",
                         files={"file": (f"p{i}.png", make_png(largeur, hauteur),
                                         "image/png")}).json()["id"]
            cid = c.post(f"/api/planches/{pid}/regions",
                         json={"type": "case", "x": 0, "y": 0,
                               "w": largeur, "h": hauteur}).json()["id"]
            # `timeout` généreux : écrire l'OCR réindexe, donc charge spaCy à froid.
            rid = c.post(f"/api/planches/{pid}/regions",
                         json={"type": "bulle", "parent_id": cid, "ocr_texte": f"BULLE{i}",
                               "x": 20, "y": 20, "w": largeur // 3, "h": hauteur // 4},
                         timeout=180).json()["id"]
            out["planches"].append({"planche": pid, "region": rid})
    finally:
        c.close()
    return out


def _atelier(page, s, rang=0):
    p = s["planches"][rang]
    page.goto(f"{s['base']}/?album={s['album']}&planche={p['planche']}&region={p['region']}",
              wait_until="networkidle")
    page.wait_for_selector("#ocr-text", timeout=15000)


def _transcription(page):
    page.locator('button[data-mode="transcription"]').click()
    expect(page.locator("#transcription")).to_be_visible(timeout=15000)
    page.wait_for_function(
        "() => { const c = document.querySelector('#tr-crop');"
        " return c && c.complete && c.naturalWidth > 0; }", timeout=20000)


# L'espion, posé sur le PROTOTYPE : `clientToMaster` appelle `overlay.getScreenCTM()`, et
# c'est cet appel-là — un par mouvement de souris, mesuré — qui matérialise le calcul.
# Idempotent : le reposer ne remet pas le compteur à zéro et n'empile pas les enveloppes.
_ESPION = """() => {
  if (!window.__ctm) {
    const proto = SVGGraphicsElement.prototype, vrai = proto.getScreenCTM;
    window.__ctm = 0;
    proto.getScreenCTM = function () { window.__ctm++; return vrai.apply(this, arguments); };
  }
  return window.__ctm;
}"""

_ETAT = """() => {
  const e = (s) => { const el = document.querySelector(s);
    return el && {txt: el.textContent, rendu: el.getClientRects().length > 0}; };
  return {mode: e('#stat-mode'), zoom: e('#stat-zoom'), coords: e('#stat-coords'),
          niveau: e('#zoom-level'), ctm: window.__ctm};
}"""


def _promener(page, selecteur, fois=3):
    """Promène le pointeur DANS une boîte et rend le nombre de mouvements envoyés."""
    boite = page.locator(selecteur).bounding_box()
    for i in range(fois):
        k = 0.25 + 0.25 * i
        page.mouse.move(boite["x"] + boite["width"] * k, boite["y"] + boite["height"] * k)
        page.wait_for_timeout(100)
    return fois


@pytest.mark.parametrize("largeur", LARGEURS)
def test_le_zoom_et_les_coordonnees_disparaissent_en_transcription(
        page, album_deux_planches, largeur):
    """Les deux indicateurs du canevas quittent l'écran ; `#stat-mode` reste.

    `#stat-mode` n'est pas un détail de la décision : c'est lui qui rendait les deux autres
    croyables, et le laisser seul est ce qui fait de la barre une phrase vraie plutôt
    qu'une phrase vraie flanquée de deux chiffres d'un objet invisible.
    """
    page.set_viewport_size({"width": largeur, "height": 900})
    _atelier(page, album_deux_planches)
    avant = page.evaluate(_ETAT)
    assert avant["zoom"]["rendu"] and avant["coords"]["rendu"], (
        f"à {largeur} px, les indicateurs ne sont pas à l'écran AVANT d'entrer dans le "
        f"mode : {avant}. La garde ne mesurerait pas une disparition, mais une absence")

    _transcription(page)
    pendant = page.evaluate(_ETAT)
    for nom in ("zoom", "coords"):
        assert not pendant[nom]["rendu"], (
            f"à {largeur} px, « {nom} » est encore affiché pendant la Transcription : il "
            f"décrit le canevas que l'overlay recouvre — {pendant[nom]['txt']!r}")
    assert pendant["mode"]["rendu"] and pendant["mode"]["txt"] == "Mode : Transcription", (
        f"`#stat-mode` a disparu ou ment : {pendant['mode']}. C'est le seul des trois qui "
        "doit rester, et il doit rester JUSTE")


def test_aucune_coordonnee_n_est_calculee_pendant_la_transcription(
        page, album_deux_planches):
    """La seconde moitié : masquer ne suffit pas, le calcul doit s'arrêter.

    Mesuré au `getScreenCTM()` près et non au texte affiché. Avant la correction, trois
    mouvements de souris sur le panneau en déclenchaient exactement trois, et écrivaient
    dans `#stat-coords` — masqué, l'écriture aurait continué sans que l'écran la trahisse.
    """
    page.set_viewport_size({"width": 1280, "height": 900})
    _atelier(page, album_deux_planches)
    page.evaluate(_ESPION)

    # SEMIS : l'espion voit-il seulement quelque chose ? Un compteur qui reste à zéro
    # parce qu'on épie le mauvais symbole rendrait tout ce test vert en ne mesurant rien.
    depart = page.evaluate(_ETAT)
    mouvements = _promener(page, "#stage")
    navigation = page.evaluate(_ETAT)
    assert navigation["ctm"] - depart["ctm"] >= mouvements, (
        f"l'espion n'a vu que {navigation['ctm'] - depart['ctm']} appel(s) à "
        f"`getScreenCTM` pour {mouvements} mouvements en mode Navigation : il ne mesure "
        "plus le calcul qu'il est censé surveiller, et son silence en Transcription ne "
        "prouverait rien")
    assert navigation["coords"]["txt"] != depart["coords"]["txt"], (
        "les coordonnées n'ont pas bougé en mode Navigation : le décor ne produit pas "
        "l'écriture dont ce test doit constater l'ARRÊT")

    _transcription(page)
    entree = page.evaluate(_ETAT)
    _promener(page, "#tr-crop-wrap")
    pendant = page.evaluate(_ETAT)

    assert pendant["ctm"] == entree["ctm"], (
        f"{pendant['ctm'] - entree['ctm']} appel(s) à `getScreenCTM` pendant que la souris "
        "traverse le panneau : le calcul des coordonnées tourne encore sous le masque. Il "
        "coûte un appel par pixel parcouru, et il fera revenir la valeur fausse le jour où "
        "l'on réaffichera l'indicateur")
    assert pendant["coords"]["txt"] == entree["coords"]["txt"], (
        f"`#stat-coords` a été RÉÉCRIT pendant la Transcription — {entree['coords']['txt']!r} "
        f"puis {pendant['coords']['txt']!r} — alors qu'il est masqué")


def test_les_deux_reviennent_en_sortant_et_le_zoom_est_a_jour(page, album_deux_planches):
    """Ils reviennent, et pas tels qu'on les avait laissés.

    Le zoom a VRAIMENT changé entre-temps : `#tr-auto` fait passer à la planche suivante,
    de taille différente, et `selectPlanche` y rappelle `fitView()`. Un retour qui
    recopierait une valeur mise en cache à l'entrée afficherait le zoom de la planche 1.
    Les coordonnées, elles, repartent de leur marque neutre : rien n'a été mesuré depuis
    l'entrée, et réafficher la dernière lecture recréerait le gel dans l'autre sens.
    """
    s = album_deux_planches
    page.set_viewport_size({"width": 1280, "height": 900})
    _atelier(page, s)
    _promener(page, "#stage")           # des coordonnées bien à nous avant d'entrer
    avant = page.evaluate(_ETAT)
    assert avant["coords"]["txt"] != COORDS_NEUTRES, (
        "les coordonnées sont restées à leur marque neutre avant l'entrée : le test ne "
        "pourrait pas distinguer « remis à neuf » de « jamais écrit »")

    _transcription(page)
    page.locator("#tr-auto").check()
    # Dernière (et seule) bulle de la planche 1 : `Tab` enchaîne sur la planche 2.
    page.locator("#tr-text").focus()
    page.keyboard.press("Tab")
    expect(page.locator("#tr-text")).to_have_value("BULLE1", timeout=20000)
    pendant = page.evaluate(_ETAT)
    assert pendant["niveau"]["txt"] != avant["niveau"]["txt"], (
        f"le zoom du canevas n'a pas changé sous l'overlay ({avant['niveau']['txt']!r} → "
        f"{pendant['niveau']['txt']!r}) : les deux planches du décor donnent le même "
        "ajustement, et « à jour » ne se distingue plus de « telle qu'à l'entrée »")

    page.locator("#tr-exit").click()
    expect(page.locator("#transcription")).to_be_hidden(timeout=15000)
    apres = page.evaluate(_ETAT)

    assert apres["zoom"]["rendu"] and apres["coords"]["rendu"], (
        f"les indicateurs ne sont pas revenus en quittant le mode : {apres}")
    assert apres["zoom"]["txt"] == "Zoom " + apres["niveau"]["txt"], (
        f"le zoom affiché en sortant, {apres['zoom']['txt']!r}, ne correspond pas au zoom "
        f"courant du canevas, {apres['niveau']['txt']!r} : il a été restitué depuis une "
        "copie au lieu d'être re-dérivé par `applyTransform()`")
    assert apres["zoom"]["txt"] != avant["zoom"]["txt"], (
        f"le zoom affiché en sortant est celui d'AVANT l'entrée ({avant['zoom']['txt']!r}) "
        "alors que la planche a changé sous l'overlay")
    assert apres["coords"]["txt"] == COORDS_NEUTRES, (
        f"les coordonnées sont revenues sur leur dernière lecture, {apres['coords']['txt']!r}, "
        f"au lieu de leur marque neutre {COORDS_NEUTRES!r} : rien n'a été mesuré depuis "
        "l'entrée dans le mode, et l'afficher est le gel, simplement dans l'autre sens")
