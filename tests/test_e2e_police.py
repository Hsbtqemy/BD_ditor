"""WCAG 2.1 AA — 1.4.4 « Redimensionnement du texte », versant PRÉFÉRENCE (A11Y-2).

Le dépôt mesurait déjà le reflow (`test_e2e_reflow.py`, 1.4.10) et l'audit axe. Aucun des
deux ne change la taille de police, et c'est un angle mort entier : le zoom navigateur
agrandit les `px` comme le reste, si bien qu'une feuille de style entièrement figée en
pixels passe ces deux gardes sans broncher. Ce que personne ne mesurait, c'est le lecteur
qui règle la police PAR DÉFAUT de son navigateur — le seul réglage que `px` ignore.

**L'instrument est le protocole CCP, pas une feuille injectée.** `Page.setFontSizes`
change la taille initiale du navigateur, exactement comme le réglage de l'utilisateur ;
injecter `html{font-size:24px}` écraserait au contraire la racine de l'application et
mesurerait autre chose. Mesuré le 2026-09-06 sur une page témoin : à 24 px de préférence,
`html { font-size: 81.25% }` calcule 19,5 px, `1rem` suit, `font-size: 12px` ne bouge pas,
et `@media (max-width: 45em)` bascule à 1080 px au lieu de 720.

La RÈGLE est importée de `tools/mesurer_reflow.py` — la même sonde que le reflow, pour la
même raison qu'elle n'y est pas recopiée. Le DÉCOR, lui, est propre à ce module : c'est
huit lignes, et les partager ferait dépendre cette mesure de conditions sans rapport.
"""
import sys
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import ECRITURE, make_png         # noqa: E402
from tools.mesurer_reflow import SONDE          # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — LA liste de cet audit, et elle sert de déclaration : `tests/test_surfaces.py`
# la confronte aux surfaces réellement servies. C'est la MÊME structure que le test
# parcourt, pas une copie posée à côté — une déclaration jumelle dériverait de sa liste
# sans que rien ne le dise, ce qui a été mesuré le 2026-09-07 sur un premier jet.
SURFACES_AUDITEES = {
    "/":            lambda d: f"/?album={d['album']}&planche={d['planche']}&region={d['region']}",
    "/recherche":   lambda d: "/recherche?q=pouvoir",
    "/corpus":      lambda d: "/corpus",
    "/exploration": lambda d: "/exploration?champ=lemme",
    "/administration": lambda d: "/administration",
}
SURFACES_HORS_PERIMETRE = {}

# Reprise à l'identique de `test_e2e_reflow.EXEMPTIONS` : le canevas de la Visionneuse est
# une surface de pan/zoom, exemptée par le 1.4.10 lui-même et gardée là-bas.
EXEMPTIONS = {"canvas"}

CAS = [(1280, 24), (1280, 20), (768, 20), (320, 20)]


@pytest.fixture
def decor(live_server):
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "Police", "auteur": "X"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        rid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 10, "y": 10, "w": 120, "h": 80}).json()["id"]
        c.put(f"/api/regions/{rid}", json={"ocr_texte": "POUVOIR ABSOLU"}, timeout=180)
        c.put(f"/api/regions/{rid}/annotation", json={"note": "colère", "tags": ["emotion"]})
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid, "region": rid}


# Ce que la sonde ne rend pas, et qui décide si elle a mesuré quelque chose. Elle
# parcourt `body *` : sur une page qui n'a pas rendu, `coupables` est VIDE et le test
# passe au vert en n'ayant rien vu. C'est le mode d'échec d'ARCH-2 — une garde qui
# approuve en ne regardant plus rien — et il se ferme ici même.
_PLANCHER = """() => {
  let n = 0;
  for (const el of document.querySelectorAll('body *')) {
    const b = el.getBoundingClientRect();
    if (b.width > 0 && b.height > 0) n++;
  }
  return {n, racine: getComputedStyle(document.documentElement).fontSize};
}"""

# La racine vaut 81,25 % de la préférence — c'est la règle du fichier, et la vérifier à
# CHAQUE cas est la garde la plus tranchante du module : si `Page.setFontSizes` cessait
# d'agir (changement de Chromium) ou si la racine repassait en px, les seize cas
# resteraient VERTS en mesurant la police par défaut.
_RACINE = 0.8125

# Le rendu peut légitimement perdre des éléments quand la police grossit, et c'est même le
# but : les seuils étant en em, une grande police fait basculer la disposition étroite plus
# tôt — ce qui masque exprès la légende de la barre d'état (41.1875em) et escamote la barre
# latérale (67.4375em) sur un écran de 1280 px. Mesuré le 2026-09-06, la plus forte baisse
# LÉGITIME est de 3,1 % : Visionneuse à 768 px sous une préférence de 20, 154 éléments
# contre 159. Une page qui n'a pas rendu, elle, est à près de zéro. Le plancher sépare deux
# populations distantes d'un ordre de grandeur, et il se calibre sur la page ELLE-MÊME
# plutôt que sur un chiffre recopié, qui vieillirait dans le sens permissif.
_BAISSE_TOLEREE = 0.80


def _charger(page, decor, surface, largeur, police):
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": police, "fixed": police}})
    page.set_viewport_size({"width": largeur, "height": 900})
    page.goto(decor["base"] + SURFACES_AUDITEES[surface](decor), wait_until="networkidle")
    page.wait_for_timeout(400)
    return page.evaluate(SONDE), page.evaluate(_PLANCHER)


def _sonder(page, decor, surface, largeur, police):
    """Charge DEUX fois : à la police par défaut pour se calibrer, puis à `police`."""
    _, temoin = _charger(page, decor, surface, largeur, 16)
    r, mesure = _charger(page, decor, surface, largeur, police)
    return r, temoin, mesure


def _decrire(coupables):
    lignes = []
    for c in coupables:
        ident = (f"#{c['id']}" if c["id"] else (f".{c['cls']}" if c["cls"] else ""))
        lignes.append(f"  <{c['tag']}>{ident} — {c['largeur']} px, dépasse de {c['depasse']} px")
    return "\n".join(lignes)


@pytest.mark.parametrize("largeur,police", CAS)
@pytest.mark.parametrize("surface", list(SURFACES_AUDITEES))
def test_la_preference_de_police_ne_perd_pas_de_contenu(page, decor, surface, largeur, police):
    """Police par défaut portée à `police` px : rien ne sort de l'écran sans recours.

    Trois assertions et non une : ce que la sonde a vu ne vaut que si elle a regardé
    quelque chose, et si la police a réellement changé. Les deux gardes d'AMONT sont
    écrites avant celle qui porte le critère — un rouge sur la troisième doit vouloir dire
    « le contenu déborde », jamais « la page était blanche ».
    """
    r, temoin, mesure = _sonder(page, decor, surface, largeur, police)

    attendue = f"{police * _RACINE:g}px"
    assert mesure["racine"] == attendue, (
        f"racine à {mesure['racine']} pour une préférence de {police} px, attendu "
        f"{attendue}. La préférence n'a pas été appliquée, ou la racine est repassée en "
        "px — dans les deux cas l'assertion du bas ne mesurerait plus rien.")

    assert mesure["n"] >= temoin["n"] * _BAISSE_TOLEREE, (
        f"{surface} à {largeur} px : {mesure['n']} éléments visibles sous une préférence "
        f"de {police} px contre {temoin['n']} à la police par défaut. Une baisse de cette "
        "ampleur n'est pas un seuil qui masque, c'est un rendu qui a échoué.")

    perdus = [c for c in r["coupables"] if not c["cadre"] and c["id"] not in EXEMPTIONS]
    assert not perdus, (
        f"{surface} à {largeur} px avec une police par défaut de {police} px — "
        f"contenu INATTEIGNABLE :\n{_decrire(perdus)}")


def test_la_racine_suit_la_preference(page, decor):
    """Le cœur du chantier, et il se vérifie en un point : si la racine cessait d'être
    proportionnelle — un `font-size` en px sur `html`, la faute d'origine —, tout le
    reste de ce fichier deviendrait vert en ne mesurant plus rien."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": 24, "fixed": 24}})
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    racine = page.evaluate("getComputedStyle(document.documentElement).fontSize")
    assert racine == "19.5px", (
        f"racine à {racine} pour une préférence de 24 px — attendu 19.5px (81.25 %). "
        "Une racine figée en px rendrait VACANTES toutes les mesures de ce module.")


def test_le_zoom_ui_compose_avec_la_conversion(page, decor):
    """Le zoom UI (propriété `zoom`, persisté) continue de fonctionner — et il COMPOSE.

    Il agit au RENDU, pas sur les valeurs calculées : mesuré le 2026-09-06, à `zoom: 1.5`
    `getComputedStyle` rend les mêmes 13 px et la même largeur qu'à 100 %, pendant que le
    rectangle, lui, a grandi de moitié. Une garde écrite sur `getComputedStyle` serait
    donc VACANTE — verte quel que soit le zoom. C'est le rectangle qu'on lit.

    Et il scinde ce que la conversion sépare : `zoom` multiplie px et rem indifféremment
    (130 → 195 et 120 → 180 dans la même mesure), là où la préférence de police ne touche
    que les rem. Les deux réglages ne mesurent donc pas la même chose, et c'est pourquoi
    ce module les éprouve tous les deux.
    """
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    haut = "() => Math.round(document.querySelector('#site-nav').getBoundingClientRect().height)"
    avant = page.evaluate(haut)

    page.click(".display-menu > button")
    for _ in range(2):
        page.click('[aria-label="Augmenter le zoom"]')
    page.wait_for_timeout(150)
    apres = page.evaluate(haut)
    assert apres >= round(avant * 1.15), (
        f"la bande 1 fait {apres} px après deux crans de zoom contre {avant} avant — "
        "attendu au moins +15 %. Le zoom UI ne porte plus sur une hauteur en rem.")

    page.reload(wait_until="networkidle")
    etat = page.evaluate("""() => ({
        stocke: localStorage.getItem('bd-zoom'),
        applique: document.documentElement.style.zoom,
        haut: Math.round(document.querySelector('#site-nav').getBoundingClientRect().height),
    })""")
    assert etat["stocke"] == "1.2" and etat["applique"] == "1.2", (
        f"zoom non persisté après rechargement : {etat}")
    assert etat["haut"] == apres, (
        f"la hauteur retombe à {etat['haut']} après rechargement (attendu {apres}) : "
        "le zoom est relu mais ne s'applique plus.")


# ── Les bandes de l'Atelier ne se PLIENT pas (UX-7, 2026-10-09) ─────────────────────────
#
# Tout ce qui précède cherche du contenu INATTEIGNABLE : un rectangle qui sort de la
# fenêtre. Un élément qui se plie n'en sort pas — il rétrécit, son texte passe sur deux ou
# trois lignes, et il déborde de SA bande par le haut et par le bas. Deux bandes ont vécu
# là le même jour : les menus de la bande 2 (« ⚙ / Traitement / ▾ »), entre le seuil où
# leurs libellés reparaissaient et la largeur où ils tenaient, et la barre d'état
# (« Mode : / Navigation », « Zoom / 58 % »), rognée dans sa rangée de hauteur fixe. Vingt
# cas verts ici pendant ce temps. Trouvé à l'œil pendant une passe de QA, comme la bande 1
# avant elles (cf. `.surf-link` dans style.css).
#
# D'où un BALAYAGE et non quatre couples : le défaut tenait dans quatre-vingts pixels, et
# sa place dépend de la préférence. Et des propriétés, pas des seuils : à chaque largeur,
# chaque élément fait la hauteur de son témoin d'une ligne et reste dans la boîte de sa
# bande ; et la légende de la barre d'état ne s'affiche que là où la barre tient sur une
# rangée — c'est ce que « elle part la première » veut dire. Enroulée, la barre fait la
# hauteur de ses rangées et rien de plus : elle en a fait le double, un `gap` de la règle
# de base écrasant le `row-gap` du bloc étroit, et c'est le canevas qui payait.
#
# **Ce que ce test ne garde PAS, et c'est mesuré** : la valeur du seuil des libellés de la
# bande 2. Depuis que ses boutons sont en `nowrap` et le nom en ellipse à toutes les
# largeurs, rien ne s'y plie quel que soit ce seuil ; il ne décide plus que de la place
# laissée au nom. Une garde là-dessus dépendrait de la police — sous DejaVu Sans, celle de
# l'image, le nom de référence est déjà rogné au seuil —, donc rouge dans l'image et verte
# sur le poste. Le seuil de la légende, lui, est gardé : il est calibré sur DejaVu.

# Un titre que rien ne borne, c'est le pire cas réel du nom de planche : il porte le titre
# de l'album. Quatre-vingt-six caractères — 637 px sous une préférence de 16, soit une
# bande de 90em. Avec « Police », la bande ne manquait de place que sur quatre-vingts
# pixels ; avec lui, jusqu'au bout du balayage.
TITRE_LONG = ("Les Aventures extraordinaires d'Adèle Blanc-Sec — intégrale, tome 10 "
              "(édition de 1976)")
# La barre d'état porte des COMPTEURS : vide, elle affiche « 0 régions » et tient partout
# où elle tenait. Cent cases font « 100 régions · 100 cases/album » : une barre de 871 px
# avec sa légende sous une préférence de 16, à vingt-huit pixels du pire cas (899) sur
# lequel le seuil de la légende est calibré.
CASES_DU_DECOR = 100

POLICES_BANDE = (16, 20, 24)
# Pas de 10 px : la plus étroite des plages fautives mesurées en faisait vingt (320–340 px
# sous une préférence de 24), et le balayage entier coûte une dizaine de secondes.
# Jusqu'à 1920, parce que sous une préférence de 24 les libellés ne reparaissent qu'à
# 1536 px — un balayage arrêté à 1280 n'y aurait vu que des libellés clipés.
LARGEURS_BALAYEES = range(320, 1921, 10)
COMMANDES_BANDE = {"navigation", "edition", "annotation", "transcription",
                   "#btn-traitement", "#btn-donnees"}
INDICATEURS_BARRE = {"#stat-cases", "#stat-annotees", "#stat-mode", "#stat-zoom",
                     "#stat-coords"}


@pytest.fixture
def decor_bande(live_server):
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": TITRE_LONG, "auteur": "X"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        for i in range(CASES_DU_DECOR):
            c.post(f"/api/planches/{pid}/regions",
                   json={"type": "case", "x": 10 + 38 * (i % 10), "y": 10 + 48 * (i // 10),
                         "w": 30, "h": 40}).raise_for_status()
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid}


# Le TÉMOIN est mesuré, pas recopié : un clone de l'élément, hors flux et forcé sur une
# ligne, posé dans le même parent pour recevoir les mêmes règles. « 29 px » serait faux dès
# la préférence suivante, et faux d'un bouton à l'autre — les deux menus ne font pas la
# même hauteur entre eux (leur glyphe de tête ne vient pas de la même police).
#
# La LIGNE aussi est mesurée — la hauteur du témoin moins ses marges intérieures et ses
# bordures —, parce que c'est elle qui donne l'échelle : un pli ajoute une ligne entière,
# donc « plié » se lit à un QUART de ligne près (`_PLI`). Un pixel suffisait à chaque
# passe jouée ici, mais sous une préférence de 24 le même bouton fait 45 ou 47 px d'un
# chargement à l'autre, selon la police de repli que le navigateur donne à son glyphe
# (Segoe UI Symbol ou Cambria Math, mesuré le 2026-10-09). Deux pixels ne sont pas un pli,
# et une garde qui le croirait un jour sur dix serait retirée avant d'avoir servi.
_BANDES = """() => {
  const R = (e) => e.getBoundingClientRect();
  const visible = (e) => { const r = R(e); return r.width > 0 && r.height > 0; };
  const horsFlux = (e) => {
    const c = e.cloneNode(true);
    c.removeAttribute('id');
    c.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;' +
                      'width:max-content;max-width:none;overflow:visible';
    e.parentNode.appendChild(c);
    const r = R(c);
    c.remove();
    return {l: r.width, h: r.height};
  };
  const ligne = (e, h) => { const s = getComputedStyle(e);
    return h - parseFloat(s.paddingTop) - parseFloat(s.paddingBottom)
             - parseFloat(s.borderTopWidth) - parseFloat(s.borderBottomWidth); };
  const boite = (e) => { const r = R(e);
    return {haut: r.top, bas: r.bottom, gauche: r.left, droite: r.right, h: r.height, l: r.width}; };
  const element = (e, nom) => { const f = horsFlux(e), t = f.h;
    return {nom, ...boite(e), temoin: t, ligne: ligne(e, t), naturel: f.l}; };

  const bande = document.querySelector('#header');
  const nom = bande.querySelector('#planche-info');
  const libelles = [...bande.querySelectorAll('.mode-label')];
  const barre = document.querySelector('#statusbar'), sb = getComputedStyle(barre);
  const legende = barre.querySelector('.legend');
  return {
    racine: getComputedStyle(document.documentElement).fontSize,
    fenetre: window.innerHeight,
    bande: {
      boite: boite(bande),
      elements: [...bande.querySelectorAll('button')].filter(visible).map((b) =>
        element(b, b.id ? '#' + b.id : (b.dataset.mode || b.textContent.trim()))),
      nom: {nom: 'le nom de planche', texte: nom.textContent, ...boite(nom),
            naturel: horsFlux(nom).l},
      // Un libellé clipé garde un rectangle d'un pixel : c'est sa LARGEUR qui dit s'il se lit.
      libelles: {total: libelles.length, visibles: libelles.filter((l) => R(l).width > 1).length},
    },
    barre: {
      boite: boite(barre),
      elements: [...barre.children].filter(visible).map((e) =>
        element(e, e.id ? '#' + e.id : '.' + e.className.split(/\\s+/)[0])),
      legende: visible(legende),
      compteur: barre.querySelector('#stat-cases').textContent,
      plancher: parseFloat(sb.minHeight) || 0,
      marges: parseFloat(sb.paddingTop) + parseFloat(sb.paddingBottom)
              + parseFloat(sb.borderTopWidth) + parseFloat(sb.borderBottomWidth),
    },
  };
}"""

# Sur les BORDS, un pixel absorbe les arrondis sans rien excuser : c'est celui de `SONDE`
# sur les bords de la fenêtre.
_TOLERANCE = 1
_PLI = 1 / 4


def _defauts(zone, ou):
    """Ce qu'une zone mesurée par `_BANDES` a de fautif — vide si elle est saine.

    Chaque faute est un couple (quoi, combien) : le balayage regroupe par le premier
    pour rendre des PLAGES, et cite le second une fois.
    """
    b, out = zone["boite"], []

    def dehors(x):
        cotes = [("par le haut", b["haut"] - x["haut"]), ("par le bas", x["bas"] - b["bas"]),
                 ("par la gauche", b["gauche"] - x["gauche"]),
                 ("par la droite", x["droite"] - b["droite"])]
        return [(c, f"{round(px)} px") for c, px in cotes if px > _TOLERANCE]

    for x in zone["elements"]:
        if x["h"] > x["temoin"] + x["ligne"] * _PLI:
            out.append((f"{x['nom']} PLIÉ",
                        f"{round(x['h'])} px de haut pour {round(x['temoin'])} sur une ligne"))
        out += [(f"{x['nom']} sort de {ou} {c}", px) for c, px in dehors(x)]
    if "nom" in zone:
        out += [(f"{zone['nom']['nom']} sort de {ou} {c}", px) for c, px in dehors(zone["nom"])]
    return out


def _rangees(zone):
    """Sur combien de rangées la zone pose ses éléments : un élément ouvre une rangée
    quand il commence sous le bas de la précédente."""
    n, bas = 0, None
    for x in sorted(zone["elements"], key=lambda x: x["haut"]):
        if bas is None or x["haut"] >= bas - _TOLERANCE:
            n, bas = n + 1, x["bas"]
        else:
            bas = max(bas, x["bas"])
    return n


def _hauteur_due(barre):
    """Ce qu'une barre ENROULÉE a le droit de mesurer : ses rangées, ses marges, et une
    gouttière d'un quart de ligne au plus par rangée — ou son plancher, s'il est plus
    haut. La gouttière n'est PAS lue dans la page : la règle fautive la portait à plus
    d'une ligne, et une borne calculée d'après elle l'aurait approuvée."""
    ligne = max(x["temoin"] for x in barre["elements"])
    return max(barre["plancher"],
               _rangees(barre) * ligne * (1 + _PLI) + barre["marges"]) + _TOLERANCE


def _defauts_atelier(m):
    """Les deux bandes d'un coup, plus les deux règles propres à la barre d'état."""
    barre = m["barre"]
    out = _defauts(m["bande"], "la bande 2") + _defauts(barre, "la barre d'état")
    n = _rangees(barre)
    if barre["legende"] and n > 1:
        out.append(("la barre d'état s'enroule AVEC sa légende", f"{n} rangées"))
    # Sur UNE rangée la barre a la hauteur qu'on lui donne, et ce n'est pas la question.
    if n > 1 and barre["boite"]["h"] > _hauteur_due(barre):
        out.append(("la barre d'état est plus haute que ses rangées",
                    f"{round(barre['boite']['h'])} px pour {n} rangée(s), "
                    f"{round(_hauteur_due(barre))} au plus"))
    # Une barre enroulée dans une rangée de grille FIGÉE garde ses éléments dans sa
    # boîte — c'est la boîte qui passe sous la fenêtre, et rien d'autre ne le dirait.
    if barre["boite"]["bas"] > m["fenetre"] + _TOLERANCE:
        out.append(("la barre d'état passe sous la fenêtre",
                    f"{round(barre['boite']['bas'] - m['fenetre'])} px"))
    return out


def _plages(largeurs, pas):
    """[900, 920, 940, 1000] → « 900–940, 1000 » : un balayage se lit en plages."""
    out, debut, fin = [], None, None
    for x in sorted(largeurs):
        if debut is not None and x == fin + pas:
            fin = x
            continue
        if debut is not None:
            out.append(f"{debut}–{fin}" if fin != debut else str(debut))
        debut = fin = x
    if debut is not None:
        out.append(f"{debut}–{fin}" if fin != debut else str(debut))
    return ", ".join(out)


def _ouvrir_bande(page, decor, police, largeur):
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": police, "fixed": police}})
    page.set_viewport_size({"width": largeur, "height": 900})
    page.goto(decor["base"] + f"/?album={decor['album']}&planche={decor['planche']}",
              wait_until="networkidle")
    # Le nom et les compteurs ne sont écrits qu'une fois la planche choisie et ses régions
    # reçues : mesurer avant, c'est mesurer « — » et « 0 régions ».
    page.wait_for_function(
        "() => document.querySelector('#planche-info').textContent.includes('planche')"
        " && document.querySelector('#stat-cases').textContent.includes('cases/album')")


def _mesurer(page, largeur):
    page.set_viewport_size({"width": largeur, "height": 900})
    page.wait_for_function("(l) => window.innerWidth === l", arg=largeur)
    return page.evaluate(_BANDES)


def test_les_bandes_de_l_atelier_ne_se_plient_pas(page, decor_bande):
    """À toute largeur et sous trois préférences, les commandes de la bande 2 et les
    indicateurs de la barre d'état tiennent sur UNE ligne et DANS leur bande.

    La page n'est chargée qu'une fois par préférence, puis redimensionnée : 483 mesures
    pour trois chargements. Les fautes sont rassemblées avant d'échouer — un balayage qui
    s'arrête à la première largeur ne dit pas où le défaut finit, et c'est sa plage qui
    désigne la règle fautive.

    Des gardes d'AMONT à chaque préférence, parce que ce test devient plus vert à mesure
    qu'il voit moins : la préférence a agi ; les six commandes et les cinq indicateurs
    sont là ; le décor PRESSE — un nom plus large que sa place, des compteurs à trois
    chiffres — ; et le balayage a vu les DEUX états de ce qui cède, les libellés comme la
    légende. Qu'une seule manque, et les 483 mesures approuvent une bande qu'elles n'ont
    pas éprouvée.
    """
    pas = LARGEURS_BALAYEES.step
    compteur = f"{CASES_DU_DECOR} régions · {CASES_DU_DECOR} cases/album"
    fautes = []
    for police in POLICES_BANDE:
        _ouvrir_bande(page, decor_bande, police, LARGEURS_BALAYEES[-1])
        libelles, legende, pressee, vus = set(), set(), [], {}
        for largeur in LARGEURS_BALAYEES:
            m = _mesurer(page, largeur)
            bande, barre = m["bande"], m["barre"]

            attendue = f"{police * _RACINE:g}px"
            assert m["racine"] == attendue, (
                f"racine à {m['racine']} pour une préférence de {police} px, attendu "
                f"{attendue} : la préférence n'a pas été appliquée, et le balayage "
                "rejouerait trois fois la police par défaut.")
            presentes = {x["nom"] for x in bande["elements"]}
            assert COMMANDES_BANDE <= presentes, (
                f"à {largeur} px sous {police}, la bande 2 ne montre plus "
                f"{sorted(COMMANDES_BANDE - presentes)} : la mesure ne porte pas sur les "
                "six commandes, et ce qu'elle approuverait n'est pas la bande.")
            presents = {x["nom"] for x in barre["elements"]}
            assert INDICATEURS_BARRE <= presents, (
                f"à {largeur} px sous {police}, la barre d'état ne montre plus "
                f"{sorted(INDICATEURS_BARRE - presents)} : ce qu'elle approuverait n'est "
                "pas la barre du mode Navigation, la plus chargée.")
            assert TITRE_LONG in bande["nom"]["texte"], (
                f"le nom de planche vaut « {bande['nom']['texte']} » : la planche du "
                "décor n'est pas ouverte, donc rien ne presse les commandes.")
            assert barre["compteur"] == compteur, (
                f"la barre d'état compte « {barre['compteur']} » et non « {compteur} » : "
                "le décor ne porte plus ses cases, et une barre presque vide tient "
                "partout où elle tenait avant le correctif.")

            lib = bande["libelles"]
            if lib["visibles"] == lib["total"]:
                libelles.add("visibles")
                if bande["nom"]["naturel"] > bande["nom"]["l"] + _TOLERANCE:
                    pressee.append(largeur)
            elif lib["visibles"] == 0:
                libelles.add("clipés")
            else:
                vus.setdefault("libellés ni tous clipés ni tous affichés", []).append(
                    (largeur, f"{lib['visibles']} visibles sur {lib['total']}"))
            legende.add("affichée" if barre["legende"] else "retirée")
            for quoi, combien in _defauts_atelier(m):
                vus.setdefault(quoi, []).append((largeur, combien))

        assert libelles == {"clipés", "visibles"}, (
            f"sous une préférence de {police}, le balayage n'a vu que des libellés "
            f"{sorted(libelles)} : il lui manque un des deux états, donc une moitié de la "
            "bande 2 n'a pas été éprouvée. Élargir `LARGEURS_BALAYEES`.")
        assert legende == {"affichée", "retirée"}, (
            f"sous une préférence de {police}, le balayage n'a vu la légende que "
            f"{sorted(legende)} : une moitié de la barre d'état n'a pas été éprouvée. "
            "Élargir `LARGEURS_BALAYEES`.")
        assert pressee, (
            f"sous une préférence de {police}, le nom de planche tient en entier partout "
            "où les libellés sont visibles : le décor ne presse plus la bande, et un "
            "bouton qui se plierait faute de place n'en manquerait jamais ici.")
        fautes += [f"préférence {police} — {quoi}, à {_plages([l for l, _ in ou], pas)} px "
                   f"({ou[0][1]} à {ou[0][0]} px)" for quoi, ou in vus.items()]

    assert not fautes, (
        "une bande de l'Atelier ne tient pas sur une ligne dans sa boîte :\n  "
        + "\n  ".join(fautes))


def test_la_garde_des_bandes_voit_un_pli(page, decor_bande):
    """Démonstration et non affirmation : on plante les fautes, et la garde doit les
    nommer. Sans cela, un témoin mal mesuré rendrait le balayage vert sur n'importe
    quelle bande, et il a deux façons de l'être, qu'on ferme séparément.

    Trop SERVILE — l'élément comparé à lui-même, ou un clone qui se plie avec lui : il
    suit le pli, et c'est la faute plantée qui le dénonce. Trop LARGE — une hauteur de
    trois lignes : il approuve un pli de deux, et la faute plantée ne le voit pas, parce
    qu'elle en fait cinq. D'où l'égalité au repos : sur une bande saine, le témoin d'un
    élément vaut SA hauteur, pas seulement un majorant.

    Les styles sont posés par le CSSOM, sur l'élément : une balise `<style>` serait
    refusée par la CSP (`style-src-elem 'self'`), et rien ne serait planté.
    """
    _ouvrir_bande(page, decor_bande, 16, 1280)
    repos = page.evaluate(_BANDES)
    assert _defauts_atelier(repos) == [], (
        "une bande est déjà fautive à 1280 px avant qu'on y plante quoi que ce soit : "
        "cette démonstration ne prouverait rien, voir le balayage.")
    for x in repos["bande"]["elements"] + repos["barre"]["elements"]:
        assert x["ligne"] > 0 and abs(x["h"] - x["temoin"]) <= x["ligne"] * _PLI, (
            f"au repos, {x['nom']} fait {x['h']:g} px de haut, son témoin {x['temoin']:g} "
            f"et sa ligne {x['ligne']:g} : le témoin ne mesure pas une ligne de CET "
            "élément, donc il excuserait un pli ou en inventerait un.")

    planter = "([sel, css]) => { document.querySelector(sel).style.cssText = css; }"
    cas = [
        ("#btn-donnees", "white-space: normal; width: 4em", "#btn-donnees PLIÉ"),
        (".mode-btn[data-mode=edition]", "transform: translateY(4rem)",
         "edition sort de la bande 2 par le bas"),
        ("#planche-info", "white-space: normal; overflow: visible; width: 4em",
         "le nom de planche sort de la bande 2 par le bas"),
        ("#stat-mode", "white-space: normal; width: 3em", "#stat-mode PLIÉ"),
        ("#stat-zoom", "transform: translateY(-3rem)",
         "#stat-zoom sort de la barre d'état par le haut"),
    ]
    for sel, css, attendu in cas:
        page.evaluate(planter, [sel, css])
        vus = [quoi for quoi, _ in _defauts_atelier(page.evaluate(_BANDES))]
        assert attendu in vus, (
            f"`{sel}` forcé en `{css}`, et la garde ne dit pas « {attendu} » — elle "
            f"dit {vus or 'que tout va bien'}. Elle approuverait donc le défaut qu'elle "
            "existe pour voir.")
        page.evaluate(planter, [sel, ""])

    assert _defauts_atelier(page.evaluate(_BANDES)) == [], (
        "une bande reste fautive une fois les fautes retirées : la mesure garde "
        "quelque chose d'un passage à l'autre.")


def test_une_bande_pressee_s_enroule_sans_se_plier(page, decor_bande):
    """Au-delà de ce pour quoi ses seuils sont calibrés, une bande cède dans l'ORDRE.

    Le balayage ne peut pas le voir : son décor tient dans la mesure, par construction.
    Or c'est hors de la mesure que ces règles servent — des compteurs plus longs que
    prévu, une police plus large, un indicateur de plus. On écrit donc dans `#stat-cases`
    ce que le décor ne peut pas produire, et on demande deux choses à la barre d'état,
    puis une troisième à la rangée des modes.

    Un contenu qui ne tient plus sur une rangée ENROULE la barre : rien n'en sort. Sans
    `flex-wrap`, `#stat-coords` quitterait la fenêtre par la droite.

    Un contenu plus large que la barre entière ne se PLIE pas : il déborde, ce que la
    sonde de reflow sait voir. Sans `nowrap`, il passerait sur plusieurs lignes dans
    une barre qui n'en attend qu'une — en silence, c'est le défaut d'origine.

    Des boutons de mode plus larges que la fenêtre s'ENROULENT : à 320 px, quatre boutons
    élargis ne tiennent plus sur une rangée, et aucun ne doit sortir de la bande. Sans le
    `flex-wrap` de `.modes`, le quatrième est coupé au bord droit — ce que la capture du
    2026-10-09 montrait sous une préférence de 24, avant que les boutons soient resserrés.
    """
    _ouvrir_bande(page, decor_bande, 16, 1280)
    ecrire = "(t) => { document.querySelector('#stat-cases').textContent = t; }"

    page.evaluate(ecrire, "régions " * 20)
    m = page.evaluate(_BANDES)
    vus = [quoi for quoi, _ in _defauts(m["barre"], "la barre d'état")]
    assert _rangees(m["barre"]) > 1 and vus == [], (
        f"`#stat-cases` allongé jusqu'à ne plus tenir sur une rangée : la barre en fait "
        f"{_rangees(m['barre'])} et la garde dit {vus or 'que rien ne sort'}. Elle "
        "devait s'enrouler, et garder tous ses indicateurs dans sa boîte.")

    page.evaluate(ecrire, "régions " * 400)
    m = page.evaluate(_BANDES)
    cases = next(x for x in m["barre"]["elements"] if x["nom"] == "#stat-cases")
    assert cases["naturel"] > m["barre"]["boite"]["l"], (
        f"`#stat-cases` demande {cases['naturel']:g} px sur une ligne dans une barre de "
        f"{m['barre']['boite']['l']:g} : il n'est pas plus large qu'elle, donc rien ne "
        "le forçait à choisir entre se plier et déborder.")
    assert cases["h"] <= cases["temoin"] + cases["ligne"] * _PLI, (
        f"`#stat-cases` plus large que la barre s'est PLIÉ : {cases['h']:g} px de haut "
        f"pour {cases['temoin']:g} sur une ligne. Il devait déborder — ce qu'un audit "
        "voit — et non se replier dans une rangée d'une ligne, ce qu'aucun ne voit.")

    page.evaluate(ecrire, "")
    m = _mesurer(page, 320)
    page.evaluate("""() => { for (const b of document.querySelectorAll('.mode-btn'))
                               b.style.minWidth = '6rem'; }""")
    m = page.evaluate(_BANDES)
    modes = {"elements": [x for x in m["bande"]["elements"]
                          if x["nom"] in COMMANDES_BANDE and not x["nom"].startswith("#")]}
    vus = [quoi for quoi, _ in _defauts(m["bande"], "la bande 2")]
    assert _rangees(modes) > 1 and vus == [], (
        f"quatre boutons de mode élargis à 6rem dans 320 px : ils tiennent sur "
        f"{_rangees(modes)} rangée(s) et la garde dit {vus or 'que rien ne sort'}. Ils "
        "devaient s'enrouler, et rester tous dans la bande.")
