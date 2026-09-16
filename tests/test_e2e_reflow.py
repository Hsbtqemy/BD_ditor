"""WCAG 2.1 AA — 1.4.10 « Reflow » : la garde qu'axe ne peut pas poser (UX-7).

Le dépôt revendique AA et l'audite avec axe (`test_e2e_a11y.py`). Or **axe ne teste pas
le 1.4.10**, qui n'est pas automatisable en général : il faut décider ce que « utilisable »
veut dire. La suite était donc verte sans rien dire à ce sujet — pas un échec signalé, un
silence pris pour un succès, ce qui est le pire des deux cas. Ce fichier comble ce
silence-là, et rien d'autre.

**Ce test ne regarde PAS `documentElement.scrollWidth`**, et c'est le point qui l'a fait
exister. La fiche UX-7 spécifiait au départ une garde écrite dessus ; elle aurait été
VACANTE. `static/style.css` pose `html, body { overflow: hidden }` — nécessaire à quatre
coques pleine hauteur —, si bien que le débordement est CLIPPÉ et que `scrollWidth` reste
égal à `clientWidth` pendant que 431 px de contenu sont hors champ. Mesuré le 2026-09-04 :
les quatre surfaces passaient cette garde-là au vert dans un état où un tiers de l'écran
de la Visionneuse était inatteignable. `test_la_garde_sur_scrollwidth_serait_vacante`
ci-dessous en fait une DÉMONSTRATION plutôt qu'une affirmation de docstring.

On compare donc le RECTANGLE de chaque élément à la largeur de la fenêtre, et on distingue
trois états que le rectangle seul confond :

- **encadré** — un ancêtre défile horizontalement et tient dans l'écran. Le 1.4.10 TOLÈRE
  explicitement ce cas pour un contenu à deux dimensions (un tableau). Conforme.
- **escamoté** — entièrement hors champ ET référencé par un `aria-controls`. C'est un
  tiroir fermé, et le contrôle EST le chemin de retour. Conforme.
- **perdu** — tout le reste. C'est ce que le test refuse.

La sonde est IMPORTÉE de `tools/mesurer_reflow.py` et non recopiée : c'est la même règle,
et deux exemplaires d'une même règle divergent au premier correctif — un seul serait
corrigé le jour où l'on apprend quelque chose. L'outil balaie sept largeurs pour
l'exploration ; le test en garde deux, les deux canoniques du critère.
"""
import sys
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import ECRITURE, make_png         # noqa: E402
from tools.mesurer_reflow import (DEPLIES, ECRASEMENT, INVENTAIRE, SONDE,  # noqa: E402
                                  decrire_ecrasement, deplier)

pytestmark = pytest.mark.e2e

# Les deux largeurs du critère. 320 px est celle qu'il NOMME (une fenêtre de 1280 px à
# 400 % de zoom) ; 768 px est la tablette, où le chantier avait cru n'avoir rien à faire
# — à tort, la Visionneuse n'y laissant que 228 px de canevas avant les tiroirs.
LARGEURS = [320, 768]

# La préférence de police du navigateur, second axe du contrôle strict ci-dessous. Elle
# n'a été ajoutée qu'au 2026-09-09, et l'omission avait un coût mesurable : à 16 px le
# poste ne voyait pas le débordement de `/administration`, l'IMAGE si — polices
# différentes, cinq pixels d'écart sur la même chaîne. Un contrôle de reflow qui ne dépend
# que de la police INSTALLÉE est vert par accident, et son vert se déplace d'une machine à
# l'autre. 20 px reproduit le défaut PARTOUT (350 px de contenu pour 320) : ce n'est pas
# un réglage exotique, c'est la valeur que `test_e2e_police.CAS` audite déjà à 320 px —
# cet audit-là visitait donc la bonne page au bon réglage, et posait l'AUTRE question
# (« le contenu est-il perdu ? »), à laquelle un `overflow-x` sur le corps de la page
# répond oui.
POLICES = [16, 20]


def _preference_police(page, police):
    """Le réglage de police PAR DÉFAUT du navigateur, posé par CDP.

    Même instrument qu'`test_e2e_police`, et pour la même raison : injecter
    `html{font-size:…}` écraserait la racine de l'application et mesurerait autre chose.

    Deux lignes RECOPIÉES plutôt qu'importées. Ses conditions de module sont aujourd'hui
    les mêmes qu'ici (`playwright`), donc l'importer marcherait — mais `test_e2e_a11y` a
    montré ce qui arrive ensuite : un module e2e finit par acquérir sa propre condition
    de saut (là-bas, la présence d'axe-core), et tout ce qu'on lui a emprunté disparaît
    avec lui, sans que rien ne le dise. C'est l'argument déjà écrit sur `decor`, quinze
    lignes plus bas. Ce qu'on ne duplique jamais reste la RÈGLE ; un instrument de deux
    lignes ne l'est pas.
    """
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": police, "fixed": police}})


# La sonde STRICTE, à un seul endroit : « le corps de la page ne défile pas de côté ».
# Elle est distincte de `SONDE` (importée de `tools/mesurer_reflow.py`), qui demande si le
# contenu est PERDU — deux questions complémentaires, cf. le long commentaire plus bas.
# Constante plutôt que recopiée, pour la raison qui vaut dans tout ce fichier : ce qu'on ne
# duplique jamais, c'est la RÈGLE ; les décors, eux, peuvent l'être.
_CORPS_QUI_DEFILE = """() => {
  const cands = [document.documentElement, document.body,
                 ...document.querySelectorAll("main")];
  return cands.filter(Boolean)
    .map((el) => ({ nom: el.tagName.toLowerCase() + (el.id ? "#" + el.id : ""),
                    clientW: el.clientWidth, scrollW: el.scrollWidth }))
    .filter((v) => v.scrollW > v.clientW + 1);
}"""


def _exiger_pas_de_defilement(page, quoi):
    debordants = page.evaluate(_CORPS_QUI_DEFILE)
    assert not debordants, (
        f"{quoi} — le corps de la page défile de côté :\n  "
        + "\n  ".join(f"{d['nom']} : {d['clientW']} px visibles pour {d['scrollW']} px "
                      "de contenu" for d in debordants)
        + "\n\nUn contenu large défile dans SON conteneur, pas en emportant la page.")


@pytest.fixture
def decor(live_server):
    """Album + planche + bulle annotée, pour que les surfaces aient quelque chose à rendre.

    Volontairement NON partagé avec `test_e2e_a11y.seeded`, qui lui ressemble : ce
    module-là se skippe entier quand axe est absent du dossier vendu, et en importer une
    fixture ferait dépendre la mesure du reflow de la présence d'axe-core — deux
    conditions sans aucun rapport. Ce qu'il ne fallait pas dupliquer, c'est la RÈGLE
    (`SONDE`), pas huit lignes de décor.
    """
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "Reflow", "auteur": "X"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        rid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 10, "y": 10, "w": 120, "h": 80}).json()["id"]
        # Même délai généreux que le décor d'a11y, et pour la même raison : écrire l'OCR
        # déclenche la réindexation, donc le chargement à froid de spaCy (~10 s).
        c.put(f"/api/regions/{rid}", json={"ocr_texte": "POUVOIR ABSOLU"}, timeout=180)
        c.put(f"/api/regions/{rid}/annotation", json={"note": "colère", "tags": ["emotion"]})
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid, "region": rid}


# La Recherche est visée AVEC une requête, et ce n'est pas un détail : au repos elle ne
# rend aucun résultat, donc ni `.r-thumb` ni `.result`. Trois largeurs figées ont vécu des
# mois sans être mesurées pour exactement cette raison — ce que la page ne rend pas,
# l'instrument ne le voit pas (UX-7, 2026-09-05).
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


# Une exemption NOMMÉE, sur le modèle de `HORS_PERIMETRE` (test_autorisation) et de
# `BLOCAGES_ADMIS` (test_csp) : ce qui sort du périmètre le fait par DÉCISION ÉCRITE, pas
# parce qu'une règle astucieuse l'a avalé au passage. Une règle générale « surface de
# pan » excuserait n'importe quel conteneur en `overflow: hidden`, c'est-à-dire les quatre
# coques de l'application.
EXEMPTIONS = {
    "canvas": (
        "surface de PAN/ZOOM de la Visionneuse. Le 1.4.10 exempte explicitement le contenu "
        "qui exige une disposition à deux dimensions — une image en fait partie, et un scan "
        "de planche est l'image même qu'on est venu regarder. Son atteignabilité ne vient "
        "pas d'un cadre défilant mais du GESTE : glisser dans `#stage`, plus quatre commandes "
        "de zoom dont « Ajuster ». `test_la_surface_de_pan_reste_bornee_et_commandee` "
        "vérifie que ces deux conditions tiennent, sans quoi l'exemption deviendrait "
        "une excuse."),
}

# Les commandes qui rendent le canevas atteignable sans souris. Le glisser ne suffirait
# pas — le 1.4.10 se lit avec le 2.1.1 (tout au clavier) —, et c'est `#zoom-fit`
# (« Ajuster ») qui porte la charge : les trois autres déplacent l'échelle, lui seul
# garantit que la planche ENTIÈRE rentre. On exige les quatre parce que retirer Ajuster
# en laissant les autres passerait autrement inaperçu.
COMMANDES_CANEVAS = ["#zoom-out", "#zoom-in", "#zoom-fit", "#zoom-reset"]


def _sonder(page, decor, surface, largeur):
    page.set_viewport_size({"width": largeur, "height": 900})
    page.goto(decor["base"] + SURFACES_AUDITEES[surface](decor), wait_until="networkidle")
    page.wait_for_timeout(400)          # les surfaces peuplent leur DOM après le chargement
    return page.evaluate(SONDE)


def _decrire(coupables):
    lignes = []
    for c in coupables:
        ident = (f"#{c['id']}" if c["id"] else (f".{c['cls']}" if c["cls"] else ""))
        lignes.append(f"  <{c['tag']}>{ident} — {c['largeur']} px, "
                      f"dépasse de {c['depasse']} px {c['sens']}")
    return "\n".join(lignes)


@pytest.mark.parametrize("largeur", LARGEURS)
@pytest.mark.parametrize("surface", list(SURFACES_AUDITEES))
def test_aucune_surface_ne_perd_de_contenu(page, decor, surface, largeur):
    """À 320 et 768 px, aucun élément n'est hors champ sans cadre ni bascule."""
    r = _sonder(page, decor, surface, largeur)
    perdus = [c for c in r["coupables"]
              if not c["cadre"] and c["id"] not in EXEMPTIONS]
    assert not perdus, (
        f"{surface} à {largeur} px — contenu INATTEIGNABLE (1.4.10) :\n{_decrire(perdus)}")


# ── Ce qui est replié n'existe pas pour la sonde (UX-14, 2026-09-13) ───────────────────
#
# `_sonder` redimensionne, charge et attend : aucun clic, donc aucun panneau ouvert, et un
# élément `hidden` n'a pas de rectangle. Le menu « Affichage » a vécu là. UX-7 l'avait
# rangé parmi les largeurs « mesurées, aucune ne déborde » — mesurées au repos —, et une
# fois ouvert il pendait hors du bord GAUCHE : son ancrage `right: 0` suivait un bouton
# que l'enroulement de la bande 1 avait posé en tête de rangée. Trouvé à l'œil, sur une
# capture d'écran, comme le formulaire d'accès plus bas et le débordement de barre d'UX-7
# avant lui. Trois fois le même scénario : c'est la cause qu'on traite ici.
#
# Deux choix de décor, et chacun vient d'une mesure du 2026-09-16 :
#
# - **375 px s'ajoute aux largeurs canoniques.** C'est celle où le défaut a été VU, et la
#   bande où la bande 1 enroule sans être encore à l'étroit : à 320 px et police par
#   défaut, le bouton tombait assez à droite pour que le panneau tienne, défaut compris.
# - **Le lien « ← Retour » est rendu** (`retour=`). Il coûte 80 px de bande et paraît dans
#   l'usage ordinaire du round-trip ; sans lui, le défaut ne se montrait à 375 px que sous
#   une police de 20. Le seuil de 28em a déjà été mal réglé une fois pour l'avoir mesuré
#   masqué — le commentaire du seuil, dans `static/style.css`, le raconte.
LARGEURS_DEPLIES = [320, 375, 768]
RETOUR = "retour=%2Frecherche"


@pytest.mark.parametrize("surface", list(SURFACES_AUDITEES))
def test_aucun_panneau_deplie_ne_perd_de_contenu(page, decor, surface):
    """Chaque contrôle repliable de la surface est DÉCLARÉ, puis mesuré OUVERT.

    L'inventaire passe d'abord, et il est la vraie protection : la liste `DEPLIES` seule
    ne ferait que déplacer l'oubli — un menu ajouté demain et non déclaré serait replié
    pour l'instrument exactement comme celui-ci l'a été, et le test resterait vert. On
    compte donc les `aria-expanded` de la page et on exige que chacun soit déclaré, dans
    les deux sens : un contrôle déclaré qui n'existe plus est une mesure qui ne se fait
    plus, et elle doit le dire aussi.

    Un seul serveur par surface, et les combinaisons dans la boucle : `decor` relance
    uvicorn et réécrit l'OCR — donc réindexe — à chaque test, et 54 paramètres auraient
    payé 54 fois ce décor. Les cinq surfaces tiennent en deux minutes (mesuré le
    2026-09-16). Les échecs sont RASSEMBLÉS avant l'assertion, parce que la carte des
    combinaisons qui cassent dit le mécanisme — un seul échec ne dit que le premier : la
    première passe a rapporté d'un coup le panneau « Aa » sur cinq surfaces ET les deux
    menus déroulants de l'Atelier, que personne n'avait vus sortir par la gauche.
    """
    url = decor["base"] + SURFACES_AUDITEES[surface](decor)
    url += ("&" if "?" in url else "?") + RETOUR

    page.set_viewport_size({"width": LARGEURS_DEPLIES[0], "height": 900})
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(400)
    inventaire = page.evaluate(INVENTAIRE, list(DEPLIES))
    non_declares = sorted({c["ident"] for c in inventaire if not c["declare"]})
    assert not non_declares, (
        f"{surface} — contrôle(s) repliable(s) absent(s) de `DEPLIES` "
        f"(tools/mesurer_reflow.py) : {non_declares}\n\nReplié pendant la mesure, son "
        "panneau n'a pas de rectangle et la sonde ne le verra jamais. Le déclarer, avec "
        "le panneau qu'il ouvre.")
    presents = {c["declare"] for c in inventaire}
    # Sans proxy : ce qui n'existe que derrière lui n'est pas attendu ici, et le test de la
    # bande 1 de production l'ouvre à sa place.
    attendus = {k for k, d in DEPLIES.items()
                if surface in d["surfaces"] and not d.get("proxy")}
    assert presents == attendus, (
        f"{surface} — `DEPLIES` ne décrit plus la page. Déclarés mais absents : "
        f"{sorted(attendus - presents)} ; présents mais déclarés pour d'autres surfaces : "
        f"{sorted(presents - attendus)}")

    echecs = []
    for police in POLICES:
        _preference_police(page, police)
        for largeur in LARGEURS_DEPLIES:
            page.set_viewport_size({"width": largeur, "height": 900})
            for controle in sorted(attendus):
                page.goto(url, wait_until="networkidle")
                page.wait_for_timeout(400)
                deplier(page, controle)
                r = page.evaluate(SONDE)
                perdus = [c for c in r["coupables"]
                          if not c["cadre"] and c["id"] not in EXEMPTIONS]
                if perdus:
                    echecs.append(f"{DEPLIES[controle]['nom']} ouvert, {largeur} px, "
                                  f"police {police} px :\n{_decrire(perdus)}")
                # Ce que la sonde ne voit pas : le panneau tient dans la fenêtre, mais son
                # contenu y est-il lisible ? Cf. `ECRASEMENT`.
                ecrase = decrire_ecrasement(
                    page.evaluate(ECRASEMENT, DEPLIES[controle]["panneau"]))
                if ecrase:
                    echecs.append(f"{DEPLIES[controle]['nom']} ouvert, {largeur} px, "
                                  f"police {police} px, ÉCRASÉ :\n" + "\n".join(ecrase))
    assert not echecs, (
        f"{surface} — contenu INATTEIGNABLE une fois un panneau ouvert (1.4.10) :\n"
        + "\n".join(echecs))


# ── Ce que `theme.js` n'injecte que derrière le proxy (UX-14) ──────────────────────────
#
# `decor` prend `live_server` SANS proxy, et c'est voulu (cf. la table des comptes, plus
# bas). Mais deux éléments de `theme.js` n'existent qu'avec lui : la pastille d'identité
# et le bandeau de portée vide. La pastille était déjà rendue, par ACCIDENT, par le test de
# la table des comptes — à 320 px seulement, où la bande enroule, et sans le lien
# « Déconnexion » que la production affiche : jamais aux largeurs où elle casse. Le
# bandeau, lui, ne l'était par aucun audit de reflow. Il est mesuré ici, et il est en outre
# un `<details>`, c'est-à-dire un repli que l'inventaire `aria-expanded` ci-dessus ne
# compte pas : il fallait le déplier à la main.
#
# 320 et 375 px, et pas 768 : le bandeau est un bloc qui suit la largeur de `<main>`, et
# la mesure à la main du 2026-09-16 le donnait sain aux trois largeurs. Ce sont les deux
# étroites qui peuvent casser.
LARGEURS_BANDEAU = [320, 375]
BANDEAU_IDENTITES = {
    # Sans identité, le bandeau naît DÉPLIÉ : c'est la seule panne certaine (AUTH-8).
    "anonyme": {},
    # Avec une identité et aucune collection, il naît replié et parle d'accès à demander.
    "identité sans accès": {"Remote-User": "sans-droits"},
}


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_le_bandeau_de_portee_vide_ne_perd_pas_de_contenu(page, live_server):
    """Le bandeau de portée vide tient à 320 et 375 px, replié comme déplié.

    Mesuré à la main le 2026-09-16 avant d'être écrit, et il tenait : ce test n'est pas un
    correctif, c'est le constat qui manquait — la même forme que la garde stricte de la
    table des comptes. On déplie par la propriété `open` et non par un clic, pour mesurer
    les deux états quel que soit celui dans lequel le bandeau naît.
    """
    echecs = []
    for nom, entetes in BANDEAU_IDENTITES.items():
        page.set_extra_http_headers(entetes)
        for police in POLICES:
            _preference_police(page, police)
            for largeur in LARGEURS_BANDEAU:
                page.set_viewport_size({"width": largeur, "height": 900})
                for surface in SURFACES_AUDITEES:
                    page.goto(live_server + surface, wait_until="networkidle")
                    page.wait_for_selector(".portee-vide details", timeout=5000)
                    for ouvert in (False, True):
                        page.evaluate("(o) => { document.querySelector("
                                      "'.portee-vide details').open = o; }", ouvert)
                        page.wait_for_timeout(100)
                        if ouvert:
                            # Le plancher : déplié, la ligne technique a un rectangle. Sans
                            # lui, un bandeau vidé passerait la sonde exactement comme un
                            # bandeau sain.
                            haut = page.evaluate(
                                "() => { const p = document.querySelector("
                                "'.portee-vide-technique'); return p ? "
                                "p.getBoundingClientRect().height : 0; }")
                            assert haut > 0, (
                                f"{surface}, {nom} : bandeau déplié sans ligne technique — "
                                "la mesure n'aurait pas d'objet")
                        r = page.evaluate(SONDE)
                        perdus = [c for c in r["coupables"]
                                  if not c["cadre"] and c["id"] not in EXEMPTIONS]
                        if perdus:
                            echecs.append(
                                f"{surface}, {nom}, {'déplié' if ouvert else 'replié'}, "
                                f"{largeur} px, police {police} px :\n{_decrire(perdus)}")
    assert not echecs, (
        "Le bandeau de portée vide perd du contenu (1.4.10) :\n" + "\n".join(echecs))


# ── La bande 1 TELLE QU'EN PRODUCTION (UX-14) ──────────────────────────────────────────
#
# La pastille au nom le plus long qu'elle affiche (`.user-who` coupe à 14ch), son lien de
# déconnexion (posé par `live_server`, comme le compose de production le pose) et
# « ← Retour ». Mesuré le 2026-09-16 : cette bande demande 672 px sur une ligne sous une
# préférence de 16, 1081 libellés affichés, et 836 / 1348 sous 20 ; les seuils de 28em et
# de 54em avaient été calibrés sans pastille. « Aa » sortait donc par la droite jusque sur
# un portable de 1024 px — le menu par lequel on règle la police.
#
# D'où un balayage et non deux largeurs canoniques : le défaut vivait ENTRE les seuils, et
# chaque seuil de cette bande a déjà été mal réglé une fois pour une largeur qu'on n'avait
# pas visitée. La bande est la même sur les cinq surfaces ; on les visite quand même,
# parce que la GRILLE qui l'accueille ne l'est pas — d'où le second contrôle, vertical.
NOM_LONG = "Camille Ferreira-Lopes"
LARGEURS_BANDE = [320, 375, 480, 560, 640, 720, 900, 1024, 1280]
# Les menus de la BANDE 1, c'est-à-dire ceux que la pastille déplace. Déclarés, et pas
# déduits de `DEPLIES` : les menus et tiroirs de l'Atelier y figurent aussi, et vivent
# ailleurs que dans la bande.
MENUS_BANDE_1 = [".display-menu > button", ".user-chip button.user-who"]

# Le bas du CONTENU de la bande, et non de sa boîte. Écrit d'abord sur la boîte, ce contrôle
# était aveugle au défaut même qu'il existait pour voir : dans la grille de l'Atelier, une
# rangée figée ÉTIRE la boîte de `#site-nav` à sa hauteur, et c'est la seconde rangée de
# liens qui déborde par-dessus la barre d'outils, hors de la boîte. Mesuré par mutation le
# 2026-09-16 : les trois rangées remises à `var(--nav-h)`, le test restait vert.
_CHEVAUCHEMENT = """() => {
  const n = document.getElementById('site-nav'), h = document.getElementById('header');
  if (!n || !h) return null;
  const bas = [...n.children].map((c) => c.getBoundingClientRect())
    .filter((b) => b.width > 0 && b.height > 0)
    .reduce((m, b) => Math.max(m, b.bottom), n.getBoundingClientRect().bottom);
  return { bas: Math.round(bas), haut: Math.round(h.getBoundingClientRect().top) };
}"""


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_la_bande_1_de_production_ne_perd_pas_de_contenu(page, live_server):
    """Au pire cas de production, ni « Aa » ni la pastille ne sortent, de 320 à 1280 px.

    Trois contrôles par page, et les deux derniers ne se voient pas en largeur. Une bande qui
    passe à la ligne GRANDIT, et dans la grille de l'Atelier sa rangée avait une hauteur
    figée (`var(--nav-h)`) : elle déborderait sur la barre d'outils sans qu'aucun rectangle
    ne sorte de la fenêtre. Et une bande qui tient dans la fenêtre peut être ÉCRASÉE — des
    liens qui se chevauchent, un texte qui déborde de sa boîte (cf. `ECRASEMENT`). La
    sonde resterait verte dans les deux cas, et une relecture par mutation l'a montré.
    """
    page.set_extra_http_headers({"Remote-User": "camille", "Remote-Name": NOM_LONG,
                                 "Remote-Groups": "bd-admins"})
    echecs = []
    for police in POLICES:
        _preference_police(page, police)
        for largeur in LARGEURS_BANDE:
            page.set_viewport_size({"width": largeur, "height": 900})
            for surface in SURFACES_AUDITEES:
                page.goto(f"{live_server}{surface}?{RETOUR}", wait_until="networkidle")
                page.wait_for_selector(".user-chip", timeout=5000)
                page.wait_for_timeout(250)
                # Le plancher : la pastille porte son lien, et « ← Retour » est rendu là où
                # la surface le gère. Sans eux, la bande mesurée serait celle du poste.
                decor = page.evaluate("""() => ({
                  logout: !!document.querySelector('.user-logout'),
                  retour: !document.getElementById('back-link').hidden })""")
                assert decor["logout"], "pastille sans lien de déconnexion : décor absent"
                if surface != "/administration":        # la seule sans lien de retour
                    assert decor["retour"], f"{surface} : « ← Retour » non rendu"

                # L'inventaire des repliables, DERRIÈRE le proxy : le test des surfaces le
                # fait sans lui, et un menu qui n'existe qu'ici lui échapperait.
                if largeur == LARGEURS_BANDE[0] and police == POLICES[0]:
                    oublies = sorted({c["ident"] for c in page.evaluate(
                        INVENTAIRE, list(DEPLIES)) if not c["declare"]})
                    assert not oublies, (
                        f"{surface}, derrière le proxy — contrôle(s) repliable(s) absent(s) "
                        f"de `DEPLIES` : {oublies}")

                cas = f"{surface}, {largeur} px, police {police} px"
                perdus = [c for c in page.evaluate(SONDE)["coupables"]
                          if not c["cadre"] and c["id"] not in EXEMPTIONS]
                if perdus:
                    echecs.append(f"{cas} :\n{_decrire(perdus)}")
                v = page.evaluate(_CHEVAUCHEMENT)
                if v and v["bas"] > v["haut"] + 1:
                    echecs.append(f"{cas} : la bande 1 recouvre la bande 2 de "
                                  f"{v['bas'] - v['haut']} px")
                ecrase = decrire_ecrasement(page.evaluate(ECRASEMENT, "#site-nav"))
                if ecrase:
                    echecs.append(f"{cas} : bande 1 ÉCRASÉE :\n" + "\n".join(ecrase))
                # Les menus de la bande, ouverts sur TOUTES les surfaces. Ils s'y ouvraient
                # d'abord sur deux, nommées à la main — une seconde liste de surfaces, que
                # `test_surfaces` refuse à raison : c'est ainsi qu'une surface finit par
                # sortir d'un audit sans que rien ne le dise. Ouvrir sans recharger ne
                # coûte qu'une évaluation.
                for controle in MENUS_BANDE_1:
                    deplier(page, controle)
                    perdus = [c for c in page.evaluate(SONDE)["coupables"]
                              if not c["cadre"] and c["id"] not in EXEMPTIONS]
                    if perdus:
                        echecs.append(f"{cas}, {DEPLIES[controle]['nom']} ouvert :\n"
                                      f"{_decrire(perdus)}")
                    ecrase = decrire_ecrasement(
                        page.evaluate(ECRASEMENT, DEPLIES[controle]["panneau"]))
                    if ecrase:
                        echecs.append(f"{cas}, {DEPLIES[controle]['nom']} ouvert, ÉCRASÉ :\n"
                                      + "\n".join(ecrase))
    assert not echecs, (
        "La bande 1 de production perd du contenu :\n" + "\n".join(echecs))


# ── Le CADRE peut être la page elle-même, et alors la garde ci-dessus s'aveugle ──
#
# Trouvé le 2026-09-08 à l'œil, sur une capture d'écran, comme le débordement de barre
# d'UX-7 avant lui. À 375 px, le formulaire « + Accorder » d'/administration sortait de
# 89 px (144 à 320), et `test_aucune_surface_ne_perd_de_contenu` restait VERT.
#
# Il avait raison dans son périmètre : ce contenu n'était pas perdu, on pouvait le
# rejoindre en défilant. Mais le cadre qui le rendait atteignable était `main#admin-body`,
# c'est-à-dire le corps de la page — et un `overflow-x: auto` posé là excuse TOUT ce que
# la surface contient. La sonde cherchait un cadre ; elle en trouvait un ; il était la
# page.
#
# CLAUDE.md tranche autrement, et c'est la règle qu'on garde ici : un contenu large
# défile « dans son propre conteneur », et « le corps de la page ne doit JAMAIS défiler
# horizontalement ». Les deux contrôles sont complémentaires — l'un demande si le contenu
# est atteignable, celui-ci demande à quel PRIX. Le second ne remplace pas le premier :
# un contenu clippé sans cadre du tout resterait invisible ici, puisque rien ne défile.
#
# Portée volontairement limitée à `/administration` : c'est la surface mesurée, et
# généraliser demanderait de vérifier que les quatre autres ne s'appuient pas sur ce
# défilement de page — l'Atelier en particulier, dont le canevas a déjà son exemption
# écrite. Élargir est un geste d'UX-7, pas un effet de bord de ce constat.
@pytest.mark.parametrize("police", POLICES)
@pytest.mark.parametrize("largeur", LARGEURS)
def test_l_administration_ne_defile_pas_de_cote(page, decor, largeur, police):
    """Le corps de la page ne défile jamais horizontalement (règle de CLAUDE.md).

    On déplie une collection avant de mesurer : le formulaire d'accès qui débordait vit
    dans le détail, et une page repliée ne montre pas ce qu'on cherche — c'est l'erreur
    qu'`AUTH-7` a déjà payée deux lignes plus bas, où un bloc vide passait tous les
    contrôles.

    **La préférence de police est un paramètre depuis le 2026-09-09.** Le panneau de
    version affiche l'empreinte COMPLÈTE du commit — 40 caractères sans un espace —, et à
    320 px elle emportait le corps de la page. Ce test était vert sur le poste et rouge
    dans l'image, pour la seule raison que les polices n'y ont pas la même chasse : un
    vert qui voyage mal est exactement ce que QA-5 existe pour supprimer. `POLICES` rend
    le défaut reproductible partout, sans dépendre de ce qui est installé.
    """
    _preference_police(page, police)
    page.set_viewport_size({"width": largeur, "height": 900})
    page.goto(decor["base"] + "/administration", wait_until="networkidle")
    page.wait_for_timeout(400)
    som = page.query_selector(".col-item summary")
    assert som, "aucune collection à déplier : le contrôle ne mesurerait rien"
    som.click()
    page.wait_for_timeout(600)

    _exiger_pas_de_defilement(
        page, f"/administration à {largeur} px (police par défaut {police} px)")


# ── COL-2 : le formulaire d'une collection a déménagé dans la Bibliothèque ─────────────
# Même question que pour l'Administration, sur le contenu NEUF de `/corpus` : trois groupes
# de champs, leurs notes et le bloc d'export, déplié — une page repliée ne montre pas ce
# qu'on cherche. La mesure porte sur la page entière, parce que c'est la règle ; si elle
# tombe ailleurs que dans ce bloc, le message nomme l'élément fautif.
@pytest.mark.parametrize("police", POLICES)
@pytest.mark.parametrize("largeur", LARGEURS)
def test_le_formulaire_de_collection_ne_defile_pas_de_cote(page, decor, largeur, police):
    """Le corps de la Bibliothèque ne défile pas de côté, collection dépliée sur son
    formulaire (règle de CLAUDE.md, critère Reflow WCAG 1.4.10)."""
    _preference_police(page, police)
    page.set_viewport_size({"width": largeur, "height": 900})
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(400)
    som = page.query_selector("#col-body .col-item summary")
    assert som, "aucune collection à déplier : le contrôle ne mesurerait rien"
    som.click()
    page.wait_for_selector("#col-body [data-enregistrer]", timeout=3000)

    _exiger_pas_de_defilement(
        page, f"/corpus, collection dépliée, à {largeur} px (police par défaut {police} px)")


# ── Le bloc que la page ne RENDAIT pas, donc que rien ne mesurait (UX-10, 2026-09-07) ──
#
# Ce fichier s'avertit lui-même vingt lignes plus haut, à propos de la Recherche : « ce que
# la page ne rend pas, l'instrument ne le voit pas ». C'est arrivé une seconde fois, et
# cette fois sur une surface parfaitement déclarée.
#
# `test_aucune_surface_ne_perd_de_contenu` visite bien `/administration` — la déclaration
# est juste, la garde d'UX-10 est verte à raison. Mais `decor` prend `live_server` SANS
# `BD_AUTH_PROXY` : aucune identité n'atteint l'UPSERT de `main.py`, `utilisateur` reste
# vide, `/api/comptes` répond `{"comptes": []}`, et `#comptes-bloc` s'affiche **sans une
# seule ligne**. La table à SIX colonnes n'a donc jamais été rendue à 320 px, ni mesurée.
# Trouvée à l'œil par une session voisine en rejouant la QA des petites largeurs.
#
# La garde d'UX-10 ne pouvait pas le dire : elle vérifie qu'une SURFACE est déclarée et
# visitée, jamais qu'un BLOC de cette surface ait quelque chose à montrer une fois qu'on y
# est. « Auditée » et « rendue » sont deux choses, et le vide passe tous les contrôles.
#
# Un test à PART plutôt qu'un décor commun, et c'est un arbitrage : ce bloc n'existe que
# derrière le proxy, or faire passer tout l'audit derrière changerait ce que les cinq
# surfaces mesurent — la portée, les bandeaux, les gardes d'écran. On paie un serveur de
# plus pour ne pas déplacer la mesure des autres.
COMPTES_DECOR = [("alice", "Alice Marchand"),
                 ("bruno", "Bruno Nguyen"),
                 ("camille", "Camille Ferreira-Lopes")]


@pytest.mark.parametrize("police", POLICES)
@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_la_table_des_comptes_ne_perd_pas_de_contenu(page, live_server, police):
    """La vue des comptes (AUTH-7) tient à 320 px, et on prouve d'abord qu'elle est LÀ.

    Le plancher sur le nombre de lignes n'est pas une précaution de style : sans lui, ce
    test rendrait exactement le même vert que celui qu'il complète, et pour la même
    raison — une table vide n'a aucun élément hors champ. C'est la leçon d'ARCH-2 appliquée
    au DÉCOR plutôt qu'à l'inventaire : un instrument qui ne peut rien voir ne dit pas
    « je ne vois rien », il dit « tout va bien ».
    """
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30)
    try:
        for login, nom in COMPTES_DECOR:
            r = c.get("/api/moi", headers={"Remote-User": login, "Remote-Name": nom,
                                           "Remote-Groups": "bd-admins"})
            assert r.status_code == 200, r.text
    finally:
        c.close()

    page.set_extra_http_headers({"Remote-User": "decor", "Remote-Name": "Décor Reflow",
                                 "Remote-Groups": "bd-admins"})
    _preference_police(page, police)
    page.set_viewport_size({"width": 320, "height": 900})
    page.goto(live_server + "/administration", wait_until="networkidle")
    # On attend la TABLE et non le bloc : le bloc existe `hidden` dans le gabarit, la table
    # n'est rendue que si la route a répondu avec des lignes. C'est elle qu'on vient
    # mesurer, donc c'est elle dont l'apparition prouve que la mesure aura un objet.
    page.wait_for_selector("#comptes-bloc table.comptes-table", timeout=5000)

    lignes = page.locator("#comptes-bloc table.comptes-table tbody tr").count()
    assert lignes >= len(COMPTES_DECOR), (
        f"{lignes} ligne(s) de comptes pour {len(COMPTES_DECOR)} identités semées : le "
        "décor ne peuple plus `utilisateur`, et l'assertion suivante mesurerait une table "
        "absente — le défaut même que ce test existe pour fermer")

    r = page.evaluate(SONDE)
    perdus = [x for x in r["coupables"] if not x["cadre"] and x["id"] not in EXEMPTIONS]
    assert not perdus, (
        "La vue des comptes perd du contenu à 320 px (1.4.10) :\n" + _decrire(perdus)
        + "\n\nLes tableaux larges du dépôt vivent dans un `.table-cadre` "
          "(`tabindex=\"0\" role=\"region\"`) : le 1.4.10 tolère le défilement horizontal "
          "d'un contenu à deux dimensions, à condition qu'il soit atteignable au clavier.")

    # Et la règle STRICTE sur la même page, ajoutée le 2026-09-09. Elle manquait ici, et
    # le trou avait la forme que ce fichier décrit vingt lignes plus haut : la garde
    # stricte de `/administration` s'exerce sur le décor SANS proxy, où `#comptes-bloc`
    # est vide — donc la table à six colonnes, la seule chose large de cet écran, n'était
    # jamais passée devant elle. Une tolérance de cadre (`.table-cadre`) et une fuite du
    # corps de la page se ressemblent beaucoup vues du dessus, et seule la seconde est un
    # défaut. Mesuré le 2026-09-09 : aucun débordement, à 16 comme à 20 px de préférence —
    # le cadre fait son travail. Le test n'est donc pas un correctif, c'est le constat qui
    # manquait.
    _exiger_pas_de_defilement(
        page, f"/administration à 320 px, table des comptes rendue "
              f"(police par défaut {police} px)")


def test_la_surface_de_pan_reste_bornee_et_commandee(page, decor):
    """Ce que l'exemption de `#canvas` doit continuer de mériter.

    Deux conditions, et elles ne se recouvrent pas. Le conteneur qui CLIPPE doit tenir
    dans la fenêtre — sinon ce n'est plus un cadre de pan, c'est la page qui déborde. Et
    le déplacement doit être COMMANDABLE, faute de quoi l'exemption reposerait sur un
    geste de souris que le 2.1.1 n'accepte pas.

    Trouvé en écrivant le test : le balayage de `tools/mesurer_reflow.py` charge `/` SANS
    album, donc sans image, donc avec un canevas minuscule — il n'a jamais vu ce cas. Le
    test, lui, charge une planche, et `#canvas` y fait 800 px pour 768 de fenêtre.
    """
    page.set_viewport_size({"width": 320, "height": 900})
    page.goto(decor["base"] + SURFACES_AUDITEES["/"](decor), wait_until="networkidle")
    page.wait_for_timeout(400)
    r = page.evaluate("""(commandes) => {
      const st = document.querySelector('#stage');
      const b = st.getBoundingClientRect(), large = document.documentElement.clientWidth;
      return {
        clippe: getComputedStyle(st).overflowX === 'hidden',
        borne: b.left >= -1 && b.right <= large + 1,
        rect: [Math.round(b.left), Math.round(b.right)], large,
        manquantes: commandes.filter(s => !document.querySelector(s)),
      };
    }""", COMMANDES_CANEVAS)
    assert r["clippe"], (
        "`#stage` ne clippe plus : `#canvas` n'est donc plus une surface de pan, et son "
        "exemption dans EXEMPTIONS ne décrit plus la réalité")
    assert r["borne"], (
        f"le conteneur de pan déborde lui-même ({r['rect']} pour {r['large']} px) : ce "
        "n'est plus le canevas qui dépasse dans son cadre, c'est le cadre qui dépasse")
    assert not r["manquantes"], (
        f"commandes de déplacement absentes : {r['manquantes']} — l'exemption de "
        "`#canvas` reposerait alors sur le seul glisser-déposer à la souris")


def test_la_garde_sur_scrollwidth_serait_vacante(page, decor):
    """La garde que la fiche spécifiait d'abord aurait approuvé une page amputée.

    Démonstration et non affirmation : on plante un bloc de 900 px dans une fenêtre de
    320, sous `overflow: hidden`. `scrollWidth` reste égal à `clientWidth` — la garde
    naïve passe — pendant que la sonde, elle, le signale comme perdu. Sans ce test, la
    docstring ci-dessus serait une croyance, et le jour où quelqu'un « simplifierait » la
    sonde en revenant à `scrollWidth`, la suite resterait verte.
    """
    page.set_viewport_size({"width": 320, "height": 900})
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.evaluate("""() => {
      const d = document.createElement('div');
      d.id = 'temoin-large';
      d.style.cssText = 'width:900px;height:40px;background:#f00';
      document.body.appendChild(d);
    }""")
    r = page.evaluate(SONDE)
    assert r["scrollWidth"] == r["clientWidth"], (
        "prémisse fausse : `overflow: hidden` ne clippe plus, et la garde naïve "
        "verrait peut-être quelque chose — ce test doit alors être repensé, pas supprimé")
    assert any(c["id"] == "temoin-large" for c in r["coupables"]), (
        "la sonde n'a pas vu un bloc de 900 px dans une fenêtre de 320 : elle ne mesure "
        f"plus ce qu'elle prétend.\n{_decrire(r['coupables'])}")


def test_un_panneau_escamote_n_est_pas_compte_comme_perdu(page, decor):
    """Contrôle POSITIF de l'exemption : un tiroir fermé est conforme.

    Sans lui, `test_aucune_surface_ne_perd_de_contenu` pourrait passer au vert parce que
    l'exemption avale TOUT, et non parce que les surfaces sont saines.
    """
    page.set_viewport_size({"width": 320, "height": 900})
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.evaluate("""() => {
      const d = document.createElement('div');
      d.id = 'faux-tiroir';
      d.style.cssText = 'position:fixed;top:0;left:-400px;width:300px;height:40px';
      document.body.appendChild(d);
      const b = document.createElement('button');
      b.setAttribute('aria-controls', 'faux-tiroir');
      document.body.appendChild(b);
    }""")
    r = page.evaluate(SONDE)
    assert not any(c["id"] == "faux-tiroir" for c in r["coupables"])


def test_un_panneau_hors_champ_sans_bascule_est_signale(page, decor):
    """Contrôle NÉGATIF, et c'est le vrai : l'exemption exige le CHEMIN DE RETOUR.

    Écrite sur la seule position — « entièrement hors de la fenêtre, donc escamoté » —,
    elle excusait n'importe quel panneau qu'aucun geste ne ramène, c'est-à-dire exactement
    la violation cherchée. Trouvé dans une passe de revue le 2026-09-05, sur l'instrument
    lui-même. Le même bloc que le test précédent, privé de son `aria-controls`, doit être
    SIGNALÉ.
    """
    page.set_viewport_size({"width": 320, "height": 900})
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.evaluate("""() => {
      const d = document.createElement('div');
      d.id = 'tiroir-sans-bascule';
      d.style.cssText = 'position:fixed;top:0;left:-400px;width:300px;height:40px';
      document.body.appendChild(d);
    }""")
    r = page.evaluate(SONDE)
    assert any(c["id"] == "tiroir-sans-bascule" for c in r["coupables"]), (
        "un panneau hors champ qu'aucun contrôle ne référence a été EXEMPTÉ : "
        "l'exemption est redevenue positionnelle")
