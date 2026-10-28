"""Le piège à focus des modales laisse-t-il atteindre TOUT ce qu'elles contiennent ?

`static/lib/dialog.js` retient Tab dans la boîte : c'est sa promesse, et `test_e2e_navigation`
la garde — Tab ne sort pas. Rien ne gardait l'autre moitié : que Tab PASSE partout. Les deux
ne se ressemblent pas. Un piège qui renvoie au premier champ dès qu'il ne reconnaît pas
l'élément focalisé ne laisse jamais sortir, donc il tient sa promesse, et il rend
inatteignable tout ce qui suit cet élément.

C'est ce que faisait la modale 📖 Lexique dès qu'elle portait un terme : chaque terme est un
`<details><summary>`, un `<summary>` est focalisable sans `tabindex`, et le sélecteur de
`dialog.js` ne le connaissait pas. Mesuré le 2026-10-09 avec trois domaines : Tab tournait
sur trois arrêts — le champ, « + Domaine », le premier terme — et ni les deux autres termes,
ni l'import, ni « Fermer » ne s'atteignaient au clavier. Trouvé à la main pendant une passe
de QA.

**La liste attendue ne vient PAS de `dialog.js`**, sans quoi ce test serait le miroir de ce
qu'il juge : un sélecteur qui oublie un élément l'oublierait des deux côtés, et le parcours
serait déclaré complet. On demande donc au NAVIGATEUR : est un arrêt tout élément de la boîte
qui prend réellement le focus quand on le lui donne (`.focus()`) et que Tab dessert
(`tabIndex >= 0`). Puis on presse Tab, et on compare.
"""
import sys
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import ECRITURE, make_png         # noqa: E402
from grilles_decor import grille_active_vivante  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source. Les trois surfaces auditées
# sont celles qui chargent `dialog.js` ; les neuf modales s'y répartissent (cf. `MODALES`) —
# la neuvième, le guide complet de la page Annotation (ANN-7, tranche 2).
SURFACES_AUDITEES = ("/", "/annotation", "/corpus", "/exploration")
SURFACES_HORS_PERIMETRE = {
    "/recherche": "aucune modale : la page ne charge pas `dialog.js`, ses deux panneaux "
                  "repliables sont des `<details>` de la page elle-même",
    "/administration": "aucune modale : la page ne charge pas `dialog.js`, ses blocs sont "
                       "des sections de la page et non des boîtes à piège",
}

DOMAINES = ("alpha", "beta", "gamma")


@pytest.fixture
def decor(live_server):
    """De quoi peupler les neuf modales : un album et sa bulle annotée, trois domaines au
    lexique, et une SECONDE collection portant l'album — sans elle, l'export part sans
    rien demander et sa modale ne s'ouvre jamais."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "Clavier", "auteur": "X"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        rid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 10, "y": 10, "w": 120, "h": 80}).json()["id"]
        c.put(f"/api/regions/{rid}", json={"ocr_texte": "POUVOIR ABSOLU"}, timeout=180)
        c.put(f"/api/regions/{rid}/annotation", json={"note": "colère", "tags": ["emotion"]})
        for nom in DOMAINES:
            c.post("/api/domaines", json={"nom": nom}).raise_for_status()
        cid = c.post("/api/collections", json={"nom": "Seconde étude"}).json()["id"]
        c.put(f"/api/albums/{aid}/collections/{cid}").raise_for_status()
        # La grille fictive, active : le guide complet de la page Annotation a de quoi
        # se peupler (ANN-7, tranche 2).
        grille_active_vivante(c)
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid, "region": rid}


# ── Les neuf modales, chacune dans un état peuplé ───────────────────────────────────────
#
# Clé : l'élément que `BDDialog.register` reçoit. `boite` est ce que le piège enferme,
# `ouvrir` le geste qui y mène — celui de l'écran, pas un `hidden = false` posé à la main,
# qui ouvrirait une boîte que son code n'a pas remplie.
def _atelier(d, region=False):
    url = f"/?album={d['album']}&planche={d['planche']}"
    return url + (f"&region={d['region']}" if region else "")


def _lexique(page, d):
    page.goto(d["base"] + "/exploration", wait_until="networkidle")
    page.click("#btn-lexique")
    page.locator("#lexique-modal:not([hidden]) details").first.wait_for(timeout=5000)


def _accord(page, d):
    page.goto(d["base"] + "/exploration", wait_until="networkidle")
    page.click("#btn-accord")
    page.wait_for_selector("#accord-modal:not([hidden])", timeout=5000)
    page.wait_for_load_state("networkidle")


def _accord_inter(page, d):
    page.goto(d["base"] + "/exploration", wait_until="networkidle")
    page.click("#btn-accord-inter")
    page.wait_for_selector("#accord-inter-modal:not([hidden])", timeout=5000)
    page.wait_for_load_state("networkidle")


def _album(page, d):
    """La modale d'édition, par « Modifier l'album » dans la fiche de l'album (UX-18)."""
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    page.locator("#albums-body .album-row").first.click()
    page.locator("#detail-edit").click()
    page.wait_for_selector("#album-modal:not([hidden])", timeout=5000)
    page.wait_for_load_state("networkidle")


def _supprimer(page, d):
    """COL-3, tranche 2 — « Supprimer… » et ses deux réponses, collections lues."""
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    page.locator("#albums-body .album-row").first.click()      # la fiche de l'album (UX-18)
    page.locator('#album-detail [data-act="supprimer"]').click()
    page.wait_for_selector("#suppr-modal:not([hidden]) #sp-retrait button[data-retirer]",
                           timeout=5000)


def _sharedocs(page, d):
    page.goto(d["base"] + _atelier(d), wait_until="networkidle")
    page.click("#btn-donnees")
    page.click("#btn-sharedocs")
    page.wait_for_selector("#sharedocs:not([hidden])", timeout=5000)
    page.wait_for_load_state("networkidle")


def _figure(page, d):
    page.goto(d["base"] + _atelier(d, region=True), wait_until="networkidle")
    page.click("#btn-fig-add")
    page.wait_for_selector("#btn-fig-open:not([hidden])", timeout=3000)
    page.click("#btn-fig-open")
    page.wait_for_selector("#fig-champs label", timeout=3000)


def _export(page, d):
    page.goto(d["base"] + _atelier(d), wait_until="networkidle")
    page.click("#btn-donnees")
    page.click('#donnees-menu [data-fmt="json"]')
    page.wait_for_selector("#export-modal:not([hidden]) input[type=radio]", timeout=5000)


def _guide_grille(page, d):
    """ANN-7, tranche 2 — le guide complet de la grille, sur la page Annotation."""
    page.goto(d["base"] + f"/annotation?album={d['album']}&planche={d['planche']}",
              wait_until="networkidle")
    page.locator("#an-onglets [role=tab]").first.wait_for(timeout=5000)
    page.click("#an-guide-complet")
    page.wait_for_selector("#an-guide-modal:not([hidden]) table", timeout=5000)


MODALES = {
    "#lexique-modal":      {"boite": "#lexique-modal .modal-box", "ouvrir": _lexique},
    "#accord-modal":       {"boite": "#accord-modal .modal-box", "ouvrir": _accord},
    "#accord-inter-modal": {"boite": "#accord-inter-modal .modal-box", "ouvrir": _accord_inter},
    "#album-modal":        {"boite": "#album-modal .modal-box", "ouvrir": _album},
    "#suppr-modal":        {"boite": "#suppr-modal .modal-box", "ouvrir": _supprimer},
    "#sharedocs":          {"boite": "#sharedocs .sd-dialog", "ouvrir": _sharedocs},
    "#figure-modal":       {"boite": "#figure-modal .modal-box", "ouvrir": _figure},
    "#export-modal":       {"boite": "#export-modal .modal-box", "ouvrir": _export},
    "#an-guide-modal":     {"boite": "#an-guide-modal .modal-box", "ouvrir": _guide_grille},
}

# Les arrêts de tabulation de la boîte, demandés au navigateur et rangés dans l'ordre du
# document. Trois précisions, toutes du côté de ce que Tab fait VRAIMENT :
#   — un groupe de boutons radio n'est qu'UN arrêt, celui du bouton coché (le premier si
#     aucun ne l'est) ; les flèches font le reste ;
#   — un hôte `contenteditable` est desservi par Tab alors que sa propriété `tabIndex`
#     vaut -1 (mesuré dans Chromium) : on le reconnaît donc à part ;
#   — le focus est rendu à qui l'avait, sans quoi la mesure commencerait ailleurs que là
#     où la modale l'a posé.
_ARRETS = """(sel) => {
  const boite = document.querySelector(sel);
  const depart = document.activeElement;
  const texte = (e) => (e.textContent || e.value || '').trim().replace(/\\s+/g, ' ').slice(0, 24);
  const decrire = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') +
    (e.tagName === 'SUMMARY' || !e.id ? ' « ' + texte(e) + ' »' : '');
  const radios = [...boite.querySelectorAll('input[type=radio]')];
  const arrets = [];
  for (const el of boite.querySelectorAll('*')) {
    el.focus({preventScroll: true});
    if (document.activeElement !== el) continue;
    const hote = el.isContentEditable && !(el.parentElement && el.parentElement.isContentEditable);
    if (el.tabIndex < 0 && !(hote && el.getAttribute('tabindex') === null)) continue;
    if (el.type === 'radio' && el.name) {
      const groupe = radios.filter((r) => r.name === el.name);
      if (el !== (groupe.find((r) => r.checked) || groupe[0])) continue;
    }
    arrets.push(el);
  }
  if (depart && depart.focus) depart.focus({preventScroll: true});
  window.__arrets = arrets;
  window.__decrire = decrire;
  return arrets.map(decrire);
}"""

_ALLER = "(i) => { window.__arrets[i].focus({preventScroll: true}); }"
_OU = """() => {
  const a = document.activeElement, i = window.__arrets.indexOf(a);
  return i !== -1 ? i : 'HORS LISTE : ' + (a ? window.__decrire(a) : 'rien');
}"""


def _marcher(page, touche, pas):
    out = []
    for _ in range(pas):
        page.keyboard.press(touche)
        out.append(page.evaluate(_OU))
    return out


def _lire(noms, suite):
    return " → ".join(noms[x] if isinstance(x, int) else x for x in suite)


def _exiger_le_tour(page, quoi, boite, minimum=2):
    """Tab visite TOUS les arrêts de `boite` dans l'ordre du document, puis boucle ; et
    Maj+Tab fait le même tour à l'envers. Rend la liste des arrêts.

    Un tour COMPLET : c'est le dernier pas, celui qui ramène au départ, qui prouve la
    boucle, et un tour plus court qui prouverait un cul-de-sac. Les deux sens sont joués
    parce qu'ils ne passent pas par le même bord du piège.
    """
    noms = page.evaluate(_ARRETS, boite)
    n = len(noms)
    assert n >= minimum, (
        f"{quoi} : {n} arrêt(s) de tabulation trouvé(s) — {noms}. La boîte n'est pas "
        "peuplée comme attendu, et un tour trop court ne prouverait rien.")

    page.evaluate(_ALLER, 0)
    avant = _marcher(page, "Tab", n)
    attendu = list(range(1, n)) + [0]
    assert avant == attendu, (
        f"{quoi} — Tab ne dessert pas tous les arrêts de la boîte.\n"
        f"  attendu : {_lire(noms, [0] + attendu)}\n"
        f"  obtenu  : {_lire(noms, [0] + avant)}\n"
        f"  jamais atteints : {[noms[i] for i in range(n) if i not in avant] or 'aucun'}")

    page.evaluate(_ALLER, 0)
    arriere = _marcher(page, "Shift+Tab", n)
    attendu = list(range(n - 1, -1, -1))
    assert arriere == attendu, (
        f"{quoi} — Maj+Tab ne fait pas le tour à l'envers.\n"
        f"  attendu : {_lire(noms, [0] + attendu)}\n"
        f"  obtenu  : {_lire(noms, [0] + arriere)}\n"
        f"  jamais atteints : {[noms[i] for i in range(n) if i not in arriere] or 'aucun'}")
    return noms


@pytest.mark.parametrize("modale", list(MODALES))
def test_tab_dessert_tous_les_arrets_de_la_modale(page, decor, modale):
    """Les neuf modales, telles que l'écran les ouvre : aucune n'a d'arrêt que Tab ne
    dessert pas. Celle du lexique est la seule à avoir échoué — elle est la seule à
    porter des `<summary>` —, et les six autres sont là pour le jour où une autre en
    gagnera un."""
    m = MODALES[modale]
    m["ouvrir"](page, decor)
    noms = _exiger_le_tour(page, modale, m["boite"])
    if modale == "#lexique-modal":
        termes = [x for x in noms if x.startswith("summary")]
        assert len(termes) >= len(DOMAINES), (
            f"le lexique ne montre que {len(termes)} terme(s) focalisable(s) — {termes} : "
            "le décor n'y a pas ses trois domaines, et c'est sur eux que le piège butait.")


# ── Ce que les modales d'aujourd'hui ne peuvent pas dire ────────────────────────────────
#
# Le correctif tient en deux lignes qui se COUVRENT l'une l'autre dans le lexique tel
# qu'il est : le sélecteur connaît désormais `<summary>`, et le piège ne renvoie plus au
# début un focus qu'il ne connaît pas. Chacune suffit à rendre le tour ci-dessus complet,
# donc aucune des deux ne tomberait seule — mesuré par mutation. On PLANTE donc les deux
# cas où une seule joue, par le DOM : une balise `<style>` serait refusée par la CSP,
# mais on n'en a pas besoin ici.

_PLANTER = """([sel, ou, html]) => {
  document.querySelector(sel).insertAdjacentHTML(ou, html);
}"""


def test_un_terme_en_bord_de_boite_est_un_bord(page, decor):
    """Un `<summary>` PREMIER ou DERNIER de sa boîte : c'est là que le sélecteur décide.

    Les bords du piège sont le premier et le dernier élément de SA liste. Un terme que la
    liste ignore, placé au bord, serait sauté dans un sens — Maj+Tab depuis le premier
    connu repartirait au dernier connu, par-dessus lui —, et l'ouverture de la modale ne
    pourrait pas lui donner le focus.
    """
    _lexique(page, decor)
    boite = MODALES["#lexique-modal"]["boite"]
    page.evaluate(_PLANTER, [boite, "afterbegin",
                             "<details><summary>terme de tête</summary><p>…</p></details>"])
    page.evaluate(_PLANTER, [boite, "beforeend",
                             "<details><summary>terme de queue</summary><p>…</p></details>"])
    noms = _exiger_le_tour(page, "lexique, un terme à chaque bord", boite, minimum=5)
    aux_bords = (noms[0].startswith("summary « terme de tête")
                 and noms[-1].startswith("summary « terme de queue"))
    assert aux_bords, (
        f"les deux termes plantés ne sont pas aux bords de la boîte — {noms[0]!r} … "
        f"{noms[-1]!r} : ce test ne mesure plus ce pour quoi il existe.")


def test_un_focalisable_inconnu_n_est_pas_un_cul_de_sac(page, decor):
    """Un élément focalisable que le sélecteur IGNORE, au milieu de la boîte.

    C'est la règle qui a fait d'un oubli de sélecteur un cul-de-sac : le focus arrivé
    sur un inconnu repartait au premier champ, et tout ce qui suivait devenait
    inatteignable. Un champ `contenteditable` tient ici le rôle du prochain oubli — le
    navigateur le dessert, `dialog.js` ne le connaît pas, et on ne l'y ajoute pas : aucune
    modale n'en porte. Tab doit le traverser dans les deux sens.
    """
    _lexique(page, decor)
    boite = MODALES["#lexique-modal"]["boite"]
    page.evaluate(_PLANTER, ["#lex-import-portee", "beforebegin",
                             '<span contenteditable="true" id="inconnu">inconnu</span>'])
    noms = _exiger_le_tour(page, "lexique, un focalisable inconnu au milieu", boite, minimum=5)
    assert "span#inconnu" in noms and noms[0] != "span#inconnu" != noms[-1], (
        f"le champ planté n'est pas un arrêt du MILIEU de la boîte — {noms} : ce test ne "
        "mesure plus ce pour quoi il existe.")


# ── Un groupe de boutons radio n'est qu'UN arrêt (AUTH-11) ──────────────────────────────
#
# Le tour des neuf modales ci-dessus ouvre celle de l'export telle qu'elle naît : la
# PREMIÈRE collection cochée. Dans cet état-là, le premier bouton radio de la liste du
# piège est aussi le premier arrêt du navigateur, et le tour est juste par coïncidence.
# Il suffit de choisir la seconde collection — le seul geste que la boîte propose — pour
# que les deux ne coïncident plus. Mesuré le 2026-10-11 : Maj+Tab depuis le bouton coché
# posait le focus sur `#lock-toggle`, derrière la boîte ; et Tab depuis « Annuler » le
# posait sur le bouton NON coché.

_DEDANS = """(sel) => {
  const a = document.activeElement;
  return document.querySelector(sel).contains(a) ? null
    : (a ? a.tagName.toLowerCase() + (a.id ? '#' + a.id : '') : 'rien');
}"""


def _cocher_la_seconde(page):
    """Par le geste du clavier : la boîte s'ouvre sur le premier bouton, la flèche coche
    le suivant et y porte le focus."""
    radios = page.locator("#export-choix input[type=radio]")
    assert radios.count() >= 2, "le décor ne donne pas deux collections à l'export"
    radios.nth(0).focus()
    page.keyboard.press("ArrowDown")
    assert radios.nth(1).is_checked() and not radios.nth(0).is_checked()
    assert radios.nth(1).evaluate("(e) => e === document.activeElement")


def test_la_seconde_collection_cochee_maj_tab_reste_dans_la_modale(page, decor):
    """Le défaut tel qu'il a été relevé, puis le tour entier dans cet état."""
    _export(page, decor)
    boite = MODALES["#export-modal"]["boite"]
    _cocher_la_seconde(page)
    page.keyboard.press("Shift+Tab")
    dehors = page.evaluate(_DEDANS, boite)
    assert dehors is None, (
        f"Maj+Tab depuis la seconde collection cochée sort de la modale d'export : le "
        f"focus est sur {dehors}, derrière la boîte.")
    assert page.evaluate("() => document.activeElement.id") == "export-close", (
        "Maj+Tab depuis le premier arrêt de la boîte doit boucler sur le dernier")
    noms = _exiger_le_tour(page, "export, la seconde collection cochée", boite, minimum=3)
    assert len(noms) == 3, (
        f"le groupe de boutons radio doit compter pour UN arrêt — {noms}")


def test_un_groupe_radio_en_queue_de_boite_ne_laisse_pas_sortir(page, decor):
    """L'autre bord. Aucune modale ne finit par un groupe de boutons radio : on le plante.

    Le PREMIER bouton coché, le second après lui : pour la liste d'avant, le coché n'était
    pas « le dernier », donc Tab suivait son cours — et pour le navigateur il n'y a plus
    rien après lui dans la boîte.
    """
    _export(page, decor)
    boite = MODALES["#export-modal"]["boite"]
    page.evaluate(_PLANTER, [boite, "beforeend",
                             '<label><input type="radio" name="queue" id="q1" checked>q1</label>'
                             '<label><input type="radio" name="queue" id="q2">q2</label>'])
    noms = _exiger_le_tour(page, "export, un groupe radio en queue", boite, minimum=4)
    assert noms[-1] == "input#q1", (
        f"le bouton coché planté n'est pas le dernier arrêt de la boîte — {noms} : ce "
        "test ne mesure plus ce pour quoi il existe.")


@pytest.mark.parametrize("touche", ["Tab", "Shift+Tab"])
def test_un_groupe_radio_sans_coche_ne_laisse_pas_sortir(page, decor, touche):
    """Un groupe où RIEN n'est coché, à chaque bord de la boîte : planté, lui aussi.

    Les navigateurs n'y entrent pas par le même bouton — en reculant, Chromium prend le
    dernier du groupe et Firefox le premier. Le piège ne devine pas lequel : quel que
    soit le bouton atteint, le pas suivant reste dans la boîte, et les autres arrêts
    restent tous desservis.
    """
    _export(page, decor)
    boite = MODALES["#export-modal"]["boite"]
    for ou, nom in (("afterbegin", "tete"), ("beforeend", "queue")):
        page.evaluate(_PLANTER, [boite, ou, "".join(
            f'<label><input type="radio" name="{nom}" id="{nom}{i}">{nom}{i}</label>'
            for i in (1, 2, 3))])
    page.locator("#export-go").focus()
    vus, pas = [], 12
    for _ in range(pas):
        page.keyboard.press(touche)
        dehors = page.evaluate(_DEDANS, boite)
        assert dehors is None, (
            f"{touche} sort de la boîte après {' → '.join(vus) or 'le départ'} : le focus "
            f"est sur {dehors}.")
        vus.append(page.evaluate(
            "() => document.activeElement.id || document.activeElement.name"))
    for attendu in ("export-go", "export-close", "export-col", "tete", "queue"):
        assert any(v.startswith(attendu) for v in vus), (
            f"{touche} ne dessert jamais « {attendu} » en {pas} pas — {' → '.join(vus)}")


# ── Un clic sur ce qui ne prend pas le focus ne le sort pas de la boîte ─────────────────
#
# Trouvé par Hugo à la QA du 2026-10-23, dans la fiche d'un album : un clic sur du vide, un
# titre ou un texte de la boîte retirait le focus au champ qui l'avait, et il retombait sur
# `body`. L'écouteur clavier de `dialog.js` vit sur la modale, et une touche partie de
# `body` ne la traverse pas : Échap ne fermait plus rien, et Tab repartait du début de la
# page, derrière le voile. Deux causes mènent le focus sur `body`, et deux remèdes y
# répondent : le clic (la boîte est focalisable par programme, elle le reçoit) et
# l'élément focalisé qui quitte le document (un rendu qui remplace un bouton : le filet du
# focus perdu rend la touche à la modale du dessus). Un test par cause — chacun tombe sans
# son remède, l'autre restant en place.

# Où ramène la fermeture : le geste d'ouverture de chaque modale. ShareDocs et l'export
# s'ouvrent depuis le menu « Données », replié avec la modale ouverte : leur déclencheur ne
# se voit plus, et l'hôte désigne le bouton du menu (`retour`).
RETOUR = {
    "#lexique-modal": "#btn-lexique",
    "#accord-modal": "#btn-accord",
    "#accord-inter-modal": "#btn-accord-inter",
    "#album-modal": "#detail-edit",
    "#suppr-modal": '#album-detail [data-act="supprimer"]',
    "#sharedocs": "#btn-donnees",
    "#figure-modal": "#btn-fig-open",
    "#export-modal": "#btn-donnees",
    "#an-guide-modal": "#an-guide-complet",
}

# Ce qui, dans chaque boîte, ne prend pas le focus : son titre (le nom de la boîte), et sa
# marge — un clic dans le coin haut-gauche, sur la boîte elle-même.
_TITRE = {
    "#lexique-modal": "#lexique-title", "#accord-modal": "#accord-title",
    "#accord-inter-modal": "#accord-inter-title", "#album-modal": "#modal-title",
    "#suppr-modal": "#sp-titre", "#sharedocs": "#sd-title",
    "#figure-modal": "#figure-title", "#export-modal": "#export-title",
    "#an-guide-modal": "#an-guide-titre",
}

_FOCUS = """(sel) => {
  const a = document.activeElement, b = document.querySelector(sel);
  return {dedans: b.contains(a), boite: a === b,
          nom: a ? a.tagName.toLowerCase() + (a.id ? '#' + a.id : '') : 'rien',
          anneau: b.matches(':focus-visible'),
          contour: getComputedStyle(b).outlineStyle};
}"""


def _cliquer_dans_le_vide(page, modale, endroit):
    boite = MODALES[modale]["boite"]
    if endroit == "titre":
        page.locator(_TITRE[modale]).click()
    else:
        page.locator(boite).click(position={"x": 8, "y": 8})
    etat = page.evaluate(_FOCUS, boite)
    assert etat["dedans"], (
        f"{modale} : un clic sur {endroit} sort le focus de la boîte — il est sur "
        f"{etat['nom']}, et le clavier n'atteint plus la modale.")
    assert not etat["anneau"] and etat["contour"] == "none", (
        f"{modale} : la boîte focalisée au clic porte un anneau de focus ({etat}) — "
        "`:focus-visible` ne doit s'allumer qu'au clavier.")
    return boite


def _exiger_la_fermeture(page, modale):
    page.keyboard.press("Escape")
    expect(page.locator(modale)).to_be_hidden(timeout=3000)
    retour = RETOUR[modale]
    if retour:
        expect(page.locator(retour)).to_be_focused()


@pytest.mark.parametrize("endroit", ["titre", "marge"])
@pytest.mark.parametrize("modale", list(MODALES))
def test_un_clic_dans_le_vide_garde_echap(page, decor, modale, endroit):
    """Le défaut tel que Hugo l'a relevé : un clic dans la boîte, puis Échap ferme, et le
    focus revient au déclencheur."""
    MODALES[modale]["ouvrir"](page, decor)
    _cliquer_dans_le_vide(page, modale, endroit)
    _exiger_la_fermeture(page, modale)


@pytest.mark.parametrize("touche", ["Tab", "Shift+Tab"])
@pytest.mark.parametrize("modale", ["#album-modal", "#lexique-modal"])
def test_un_clic_dans_le_vide_garde_tab_dans_la_boite(page, decor, modale, touche):
    """Après le même clic, Tab entre dans la boîte par son premier arrêt, Maj+Tab par son
    dernier : la boîte focalisée n'est pas un arrêt, et rien ne sort derrière le voile."""
    MODALES[modale]["ouvrir"](page, decor)
    boite = _cliquer_dans_le_vide(page, modale, "marge")
    noms = page.evaluate(_ARRETS, boite)
    page.keyboard.press(touche)
    attendu = 0 if touche == "Tab" else len(noms) - 1
    obtenu = page.evaluate(_OU)
    assert obtenu == attendu, (
        f"{modale} — {touche} après un clic dans le vide mène à "
        f"{noms[obtenu] if isinstance(obtenu, int) else obtenu}, et non à {noms[attendu]}.")


_PERDRE = """(sel) => {
  const b = document.createElement('button');
  b.textContent = 'éphémère';
  document.querySelector(sel).append(b);
  b.focus();
  b.remove();
  return document.activeElement === document.body;
}"""


@pytest.mark.parametrize("touche", ["Escape", "Tab", "Shift+Tab"])
@pytest.mark.parametrize("modale", ["#album-modal", "#lexique-modal"])
def test_un_focus_perdu_rend_le_clavier_a_la_modale(page, decor, modale, touche):
    """L'élément focalisé quitte le document — le sort d'un bouton qu'un rendu remplace :
    le focus retombe sur `body` sans aucun clic. Échap ferme toujours, Tab et Maj+Tab
    rentrent dans la boîte par ses extrémités."""
    MODALES[modale]["ouvrir"](page, decor)
    boite = MODALES[modale]["boite"]
    # Les arrêts AVANT de perdre le focus : `_ARRETS` focalise chaque élément, et rendre
    # le focus à `body` ne le retire pas au dernier qu'il a touché.
    noms = page.evaluate(_ARRETS, boite)
    assert page.evaluate(_PERDRE, boite), (
        "le bouton planté retiré, le focus n'est pas sur `body` : ce test ne mesure plus "
        "ce pour quoi il existe.")
    if touche == "Escape":
        _exiger_la_fermeture(page, modale)
        return
    page.keyboard.press(touche)
    attendu = 0 if touche == "Tab" else len(noms) - 1
    obtenu = page.evaluate(_OU)
    assert obtenu == attendu, (
        f"{modale} — {touche}, focus perdu, mène à "
        f"{noms[obtenu] if isinstance(obtenu, int) else obtenu}, et non à {noms[attendu]}.")


# ── Le déclencheur redessiné : le focus va à son REMPLAÇANT ──────────────────────────────
#
# Trouvé par Hugo avec Narrateur le 2026-10-23. « Modifier », puis Enregistrer : la fiche
# de l'album se relit au serveur APRÈS la fermeture et se redessine, le « Modifier » d'où
# l'on venait n'existe plus, et le focus que `dialog.js` venait de lui rendre tombait sur
# `body`. Narrateur relisait le haut de la page, et la bulle « Album enregistré » se
# perdait. On exige le NOUVEAU « Modifier », dans le document, et qu'il ait reçu le focus
# AVANT la bulle : l'annonce polie ne doit pas être couverte par un changement de focus.

_GUETTER = """([sel, texte]) => {
  window.__ancien = document.querySelector(sel);
  window.__focus_avant_bulle = null;
  document.addEventListener('focusin', (e) => {
    if (!e.target.matches(sel) || e.target === window.__ancien) return;
    const bulle = [...document.querySelectorAll('#toasts .toast')]
      .some((t) => t.textContent.includes(texte));
    if (window.__focus_avant_bulle === null) window.__focus_avant_bulle = !bulle;
  }, true);
}"""

_OU_EST = """(sel) => {
  const a = document.activeElement;
  return {nom: a ? a.tagName.toLowerCase() + (a.id ? '#' + a.id : '') : 'rien',
          bon: !!a && a.matches(sel), relie: !!a && a.isConnected,
          neuf: !!a && a !== window.__ancien,
          ancien_detache: !!window.__ancien && !window.__ancien.isConnected,
          avant_bulle: window.__focus_avant_bulle};
}"""


def test_enregistrer_un_album_rend_le_focus_au_nouveau_modifier(page, decor):
    _album(page, decor)
    page.evaluate(_GUETTER, ["#detail-edit", "Album enregistré"])
    page.fill("#m-desc", "Une description, pour enregistrer quelque chose.")
    page.click("#m-save")
    expect(page.locator("#album-modal")).to_be_hidden(timeout=5000)
    expect(page.locator("#toasts .toast", has_text="Album enregistré")).to_have_count(1)
    etat = page.evaluate(_OU_EST, "#detail-edit")
    assert etat["ancien_detache"], (
        f"la fiche n'a pas été redessinée ({etat}) : ce test ne mesure plus ce pour quoi "
        "il existe.")
    assert etat["bon"] and etat["relie"] and etat["neuf"], (
        f"après l'enregistrement, le focus est sur {etat['nom']} — et non sur le nouveau "
        f"« Modifier » de la fiche ({etat}).")
    assert etat["avant_bulle"] is True, (
        f"le nouveau « Modifier » a reçu le focus APRÈS la bulle ({etat}) : un changement "
        "de focus couvrirait son annonce.")


def test_enregistrer_la_description_d_une_collection_rend_le_focus_a_modifier(page, decor):
    """Le même défaut hors modale, dans la fiche d'une collection : le formulaire redessiné
    emportait « Enregistrer », et le focus avec lui. Il revient au « Modifier » du panneau,
    comme après « Annuler »."""
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        cid = next(x["id"] for x in c.get("/api/collections").json()
                   if x["nom"] == "Seconde étude")
    page.goto(f"{decor['base']}/corpus?collection={cid}&onglet=description",
              wait_until="networkidle")
    sel = '#panneau-description [data-modifier]'
    page.locator(sel).click()
    champ = page.locator("#panneau-description [data-champ]").first
    expect(champ).to_be_focused()
    champ.fill(champ.input_value() + " (revue)")
    page.locator("#panneau-description [data-enregistrer]").click()
    expect(page.locator(sel)).to_be_visible(timeout=5000)
    expect(page.locator(sel)).to_be_focused()
