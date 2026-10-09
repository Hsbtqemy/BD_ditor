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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import ECRITURE, make_png         # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source. Les trois surfaces auditées
# sont celles qui chargent `dialog.js` ; les sept modales s'y répartissent (cf. `MODALES`).
SURFACES_AUDITEES = ("/", "/corpus", "/exploration")
SURFACES_HORS_PERIMETRE = {
    "/recherche": "aucune modale : la page ne charge pas `dialog.js`, ses deux panneaux "
                  "repliables sont des `<details>` de la page elle-même",
    "/administration": "aucune modale : la page ne charge pas `dialog.js`, ses blocs sont "
                       "des sections de la page et non des boîtes à piège",
}

DOMAINES = ("alpha", "beta", "gamma")


@pytest.fixture
def decor(live_server):
    """De quoi peupler les sept modales : un album et sa bulle annotée, trois domaines au
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
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid, "region": rid}


# ── Les sept modales, chacune dans un état peuplé ───────────────────────────────────────
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
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    page.locator('[data-act="edit"]').first.click()
    page.wait_for_selector("#album-modal:not([hidden])", timeout=5000)
    page.wait_for_load_state("networkidle")


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


MODALES = {
    "#lexique-modal":      {"boite": "#lexique-modal .modal-box", "ouvrir": _lexique},
    "#accord-modal":       {"boite": "#accord-modal .modal-box", "ouvrir": _accord},
    "#accord-inter-modal": {"boite": "#accord-inter-modal .modal-box", "ouvrir": _accord_inter},
    "#album-modal":        {"boite": "#album-modal .modal-box", "ouvrir": _album},
    "#sharedocs":          {"boite": "#sharedocs .sd-dialog", "ouvrir": _sharedocs},
    "#figure-modal":       {"boite": "#figure-modal .modal-box", "ouvrir": _figure},
    "#export-modal":       {"boite": "#export-modal .modal-box", "ouvrir": _export},
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
    """Les sept modales, telles que l'écran les ouvre : aucune n'a d'arrêt que Tab ne
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
