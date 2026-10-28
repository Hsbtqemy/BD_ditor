"""Audit d'accessibilité automatisé (axe-core) — non-régression des 5 surfaces.

Injecte axe-core (vendu dans `tests/js/vendor/axe.min.js`) dans un vrai Chromium
piloté par Playwright et ÉCHOUE si une violation WCAG 2.1 A/AA **sérieuse ou
critique** apparaît. Couvre le chargement des 5 surfaces en thèmes sombre + clair,
plus des états interactifs (modes Édition/Annotation, modale album) où
l'accessibilité régresse le plus souvent (focus, labels, rôles).

Marqué `e2e` → hors run par défaut (`pytest -m e2e`). Skippé proprement si
Playwright ou le fichier axe vendu sont absents.

**Ce que l'audit garantit, et ce qu'il laisse** (A11Y-3, 2026-10-21). axe range à part, en
« incomplete », ce qu'il ne sait pas trancher ; `_audit` n'en lisait rien, et deux sortes de
défauts y passaient en silence. Il en lit désormais deux, et deux seulement :

- un contraste EXACTEMENT 1:1 — un texte de la couleur de son fond (`equalRatio`) — compte
  comme une violation sérieuse : c'est le mutant M8 d'UX-14, qui passait vert ;
- un texte qu'un conteneur défilant repousse hors de sa zone visible (`elmPartiallyObscured`,
  ou `outsideViewport` pour la page) est AMENÉ dans le champ, jugé, puis les conteneurs
  reprennent leur position. Mesuré le 2026-10-21 sur la Bibliothèque et sur les vues
  Comptes et groupes, Projets et Fonds de l'Administration (`SURFACES_DEFILANTES`), qui
  ont chacune leur test ; la Recherche et l'Exploration défilent avec la page, et l'Atelier
  du décor ne déborde pas.

Tout autre « incomplete » — un fond en image ou en dégradé, un texte recouvert pour de bon
par un autre élément, un texte trop court pour qu'axe le juge — reste ignoré, et c'est voulu :
crier sur ce qu'axe ne sait pas mesurer rendrait l'audit inutilisable. Ce que l'audit ne
voit toujours pas, donc : le contraste sous un fond qu'axe ne sait pas échantillonner. Les
tests `test_a11y3_…` gardent l'instrument lui-même, chacun en vérifiant d'abord sur une
lecture BRUTE d'axe que le défaut posé est bien rangé là où on le croit.
"""
import json
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

# AUTH-2 : `ADMIN` monte le décor avec les droits qu'il faut (sans effet hors proxy).
from conftest import du_projet
from conftest import (ADMIN, ECRITURE, SANTE_PROFOND, SANTE_RAPIDE,  # noqa: E402
                      make_png, requires_kumiko)
from playwright.sync_api import expect  # noqa: E402

pytestmark = pytest.mark.e2e

_AXE = Path(__file__).parent / "js" / "vendor" / "axe.min.js"
if not _AXE.exists():
    pytest.skip("axe-core absent (cf. tests/js/vendor/README.md)", allow_module_level=True)
_AXE_SRC = _AXE.read_text(encoding="utf-8")

# axe.run sur le DOM courant, limité aux règles WCAG 2.1 A/AA, ne renvoyant que le
# sérieux/critique (le « moderate/minor » est du raffinement, pas une régression) — et
# DEUX sortes d'« incomplete » de `color-contrast` qu'axe range à part et que l'audit
# lisait comme un succès (A11Y-3, cf. l'en-tête « Ce que l'audit garantit » ci-dessous) :
#
#   · `equalRatio` — un contraste EXACTEMENT 1:1, un texte de la couleur de son fond. axe
#     ne le tient pas pour une violation ; un jeton qui pointe sur le fond au lieu de
#     l'encre le produit très bien. Compté comme une violation sérieuse.
#   · `elmPartiallyObscured` et `outsideViewport` — un texte qu'un conteneur défilant (ou
#     la page) repousse hors de sa zone visible : axe ne peut pas en échantillonner le
#     fond. Mesuré le 2026-10-21 dans une fenêtre de 260 px de haut : c'est la PREMIÈRE
#     raison qu'axe donne pour les lignes de la liste de « Comptes et groupes », des
#     projets, du fonds et de la Bibliothèque, pas la seconde. On AMÈNE chacun dans le
#     champ (`scrollIntoView`), on le juge, et l'on rend aux conteneurs leur position. Ce
#     qui reste masqué une fois amené — un vrai recouvrement — reste ce qu'axe en dit.
#     Par écrans et non élément par élément : chaque tour juge d'un coup tout ce que le
#     défilement a amené, et un élément qui reste hors champ après le sien sort de la
#     liste — sans quoi un texte rogné par `overflow: hidden` tournerait sans fin.
#
# Les autres natures (`bgImage`, `bgGradient`, `bgOverlap`, `elmPartiallyObscured`…) ne
# font PAS échouer : axe ne sait pas les mesurer, et crier dessus rendrait l'audit inutile.
_RUN = """async () => {
  const TAGS = {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa']},
                elementRef: true};
  const CC = {runOnly: {type: 'rule', values: ['color-contrast']}, elementRef: true};
  const raisons = (n) => [].concat(n.any || [], n.all || [], n.none || [])
    .map(c => c.data && c.data.messageKey).filter(Boolean);
  const egal = (n) => raisons(n).includes('equalRatio');
  const horsChamp = (n) => raisons(n).some(k => k === 'outsideViewport' || k === 'elmPartiallyObscured');
  const incompletsCC = (r) => (r.incomplete.find(v => v.id === 'color-contrast') || {nodes: []}).nodes;
  const sortie = [];
  const rendre = (id, impact, help, nodes) => { if (nodes.length) sortie.push({id, impact, help,
    targets: nodes.slice(0, 5).map(n => n.target.join(' '))}); };

  const r = await axe.run(document, TAGS);
  r.violations.filter(v => v.impact === 'serious' || v.impact === 'critical')
    .forEach(v => rendre(v.id, v.impact, v.help, v.nodes));
  const egaux = incompletsCC(r).filter(egal);
  let reste = incompletsCC(r).filter(horsChamp).map(n => n.element).filter(Boolean);

  const insuffisants = [];
  if (reste.length) {
    const positions = [...document.querySelectorAll('*')]
      .filter(e => e.scrollTop || e.scrollLeft
                   || e.scrollHeight > e.clientHeight || e.scrollWidth > e.clientWidth)
      .map(e => [e, e.scrollTop, e.scrollLeft]);
    const fenetre = [window.scrollX, window.scrollY];
    try {
      while (reste.length) {
        const vise = reste[0];
        vise.scrollIntoView({block: 'center', inline: 'center'});
        const enJeu = new Set(reste);
        const r2 = await axe.run({include: reste}, CC);
        const encoreHors = new Set();
        r2.violations.forEach(v => v.nodes.forEach(n => { if (enJeu.has(n.element)) insuffisants.push(n); }));
        incompletsCC(r2).forEach(n => {
          if (!enJeu.has(n.element)) return;
          if (egal(n)) egaux.push(n);
          else if (horsChamp(n)) encoreHors.add(n.element);
        });
        encoreHors.delete(vise);
        reste = reste.filter(e => encoreHors.has(e));
      }
    } finally {
      positions.forEach(([e, t, l]) => { e.scrollTop = t; e.scrollLeft = l; });
      window.scrollTo(fenetre[0], fenetre[1]);
    }
  }
  rendre('color-contrast', 'serious',
         'Texte de la couleur exacte de son fond (1:1), rangé « incomplete » par axe — A11Y-3', egaux);
  rendre('color-contrast', 'serious',
         'Contraste insuffisant hors de la zone visible, jugé une fois amené dans le champ — A11Y-3',
         insuffisants);
  return sortie; }"""


def _audit(page):
    """Injecte axe (idempotent) et renvoie les violations sérieuses/critiques.

    `evaluate` et NON `add_script_tag` depuis SEC-2 : `add_script_tag` fabrique un
    `<script>` inline dans la page, que la CSP (`script-src 'self'`) bloque net — l'audit
    serait mort le jour où la politique est posée, et pour la bonne raison. `evaluate`
    passe par le protocole de débogage, hors du modèle de sécurité de la page : c'est
    exactement ce qu'on veut d'un instrument de mesure, qu'il n'ait pas besoin qu'on
    desserre ce qu'il vient vérifier.
    """
    page.evaluate(_AXE_SRC)
    return page.evaluate(_RUN)


def _fmt(viol):
    lines = []
    for v in viol:
        lines.append(f"  [{v['impact']}] {v['id']} — {v['help']}")
        lines += [f"      {t}" for t in v["targets"]]
    return "\n".join(lines)


def _theme(page, name):
    """Pose le thème AVANT navigation (theme.js lit localStorage au chargement)."""
    page.add_init_script(f"localStorage.setItem('bd-theme','{name}')")


@pytest.fixture
def seeded(live_server):
    """Album + planche + une bulle (avec OCR + annotation) pour peupler les 4
    surfaces, via l'API sur le serveur live."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "A11y", "auteur": "X"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        rid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 10, "y": 10, "w": 120, "h": 80}).json()["id"]
        # `timeout` généreux ICI et nulle part ailleurs : écrire l'OCR déclenche la
        # réindexation, donc le chargement À FROID de spaCy (~10 s, cf. CLAUDE.md), et le
        # décor est le premier à le payer. Les 30 s du client ont suffi des mois puis
        # lâché le 2026-08-31 sous une machine chargée — une `ReadTimeout` au MONTAGE,
        # qui fait passer les huit paramétrages d'un test pour cassés alors que rien ne
        # l'était. `test_live_coherence.py` avait déjà rencontré le même mur et le
        # contourne pareillement.
        #
        # Cette parade a lâché À SON TOUR le 2026-09-04, sur une course de 1 h 23 au lieu
        # de 14 min — six fois la normale. Relancé seul, le test passe en 20 s. On ne
        # remonte donc PAS le chiffre : ce n'est pas la marge qui manque, c'est la machine
        # qui était mangée par autre chose, et poursuivre une cible mobile allongerait
        # surtout le délai avant de voir un vrai échec.
        c.put(f"/api/regions/{rid}", json={"ocr_texte": "POUVOIR ABSOLU"}, timeout=180)
        c.put(f"/api/regions/{rid}/annotation", json={"note": "colère", "tags": ["emotion"]})
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid, "region": rid}


# UX-10 — LA liste de cet audit, et elle sert de déclaration : `tests/test_surfaces.py`
# la confronte aux surfaces réellement servies. C'est la MÊME structure que le test
# parcourt, pas une copie posée à côté — une déclaration jumelle dériverait de sa liste
# sans que rien ne le dise, ce qui a été mesuré le 2026-09-07 sur un premier jet.
SURFACES_AUDITEES = {
    "/":            lambda s: f"/?album={s['album']}&planche={s['planche']}&region={s['region']}",
    "/annotation":  lambda s: f"/annotation?album={s['album']}&planche={s['planche']}&region={s['region']}",
    "/recherche":   lambda s: "/recherche?q=pouvoir",
    "/corpus":      lambda s: "/corpus",
    "/exploration": lambda s: "/exploration?champ=lemme",
    "/administration": lambda s: "/administration",
}
SURFACES_HORS_PERIMETRE = {}


# COL-3 — l'Administration est UNE surface à cinq vues adressables : le chargement générique
# n'en audite qu'une, celle sur laquelle la page s'ouvre. Chacune l'est donc aussi.
VUES_ADMINISTRATION = ("afaire", "fonds", "projets", "comptes", "instance")


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("vue", VUES_ADMINISTRATION)
def test_a11y_chaque_vue_de_l_administration(page, seeded, vue, theme):
    """Chaque vue de l'Administration, ouverte par son adresse : elle est bien la vue
    courante, et aucune violation sérieuse/critique."""
    _theme(page, theme)
    page.goto(seeded["base"] + f"/administration?vue={vue}", wait_until="networkidle")
    page.wait_for_timeout(600)
    assert page.locator(f"#vue-lien-{vue}").get_attribute("aria-current") == "page"
    viol = _audit(page)
    assert not viol, f"/administration?vue={vue} [{theme}] :\n{_fmt(viol)}"


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("surface", list(SURFACES_AUDITEES))
def test_a11y_chargement(page, seeded, surface, theme):
    """Chargement de chaque surface : aucune violation sérieuse/critique."""
    _theme(page, theme)
    page.goto(seeded["base"] + SURFACES_AUDITEES[surface](seeded), wait_until="networkidle")
    page.wait_for_timeout(600)
    viol = _audit(page)
    assert not viol, f"{surface} [{theme}] :\n{_fmt(viol)}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_visionneuse_modes(page, seeded, theme):
    """États interactifs de la Visionneuse (Édition → poignées, Annotation →
    panneau grammaire)."""
    _theme(page, theme)
    page.goto(seeded["base"] + SURFACES_AUDITEES["/"](seeded), wait_until="networkidle")
    page.wait_for_timeout(700)
    for sel, label in (('.mode-btn[data-mode="edition"]', "édition"),
                       ('.mode-btn[data-mode="annotation"]', "annotation")):
        page.click(sel)
        page.wait_for_timeout(300)
        viol = _audit(page)
        assert not viol, f"Visionneuse/{label} [{theme}] :\n{_fmt(viol)}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_visionneuse_situation(page, seeded, theme):
    """ANN-6 — une CASE en mode Annotation : le bloc « Situation » et sa phrase d'aide.

    L'audit des modes, juste au-dessus, sélectionne la BULLE du décor : le bloc Situation y
    reste caché, et axe ne juge que ce qui s'affiche. La phrase — du petit texte, donc le
    seuil de 4.5:1 — et le lien `aria-describedby` qui la rattache au champ n'étaient donc
    devant aucun audit. On attend qu'elle soit VISIBLE avant d'auditer : sur une section
    encore cachée, axe rendrait zéro violation pour la même raison.
    """
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        case = c.post(f"/api/planches/{seeded['planche']}/regions",
                      json={"type": "case", "x": 150, "y": 150, "w": 200, "h": 200}).json()["id"]
    finally:
        c.close()
    _theme(page, theme)
    page.goto(seeded["base"] + SURFACES_AUDITEES["/"]({**seeded, "region": case}),
              wait_until="networkidle")
    page.wait_for_timeout(700)
    page.click('.mode-btn[data-mode="annotation"]')
    page.wait_for_selector("#sit-aide", state="visible", timeout=5000)
    viol = _audit(page)
    assert not viol, f"Visionneuse/situation [{theme}] :\n{_fmt(viol)}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_visionneuse_profil(page, seeded, theme):
    """ANN-6 — les deux champs de PROFIL d'un personnage et leur phrase d'aide.

    Même angle mort que pour « Situation », un cran plus loin : la bulle du décor n'a pas
    de locuteur, donc le bloc de profil reste caché pendant l'audit des modes ; et aucune
    boîte personnage n'y est. Les deux phrases — du petit texte, chacune reliée à SON
    champ par `aria-describedby` — n'étaient donc devant aucun audit. On désigne le
    personnage des deux côtés, et on attend chaque phrase VISIBLE avant d'auditer.
    """
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        perso = c.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]
        boite = c.post(f"/api/planches/{seeded['planche']}/regions",
                       json={"type": "personnage", "x": 150, "y": 150, "w": 200,
                             "h": 200}).json()["id"]
        for lien in (f"/api/regions/{seeded['region']}/locuteur",
                     f"/api/regions/{boite}/personnage"):
            assert c.put(lien, json={"personnage_id": perso}).status_code == 200
    finally:
        c.close()
    _theme(page, theme)
    for region, aide in ((seeded["region"], "#perso-attr-aide"), (boite, "#perso-profil-aide")):
        page.goto(seeded["base"] + SURFACES_AUDITEES["/"]({**seeded, "region": region}),
                  wait_until="networkidle")
        page.wait_for_timeout(700)
        page.click('.mode-btn[data-mode="annotation"]')
        page.wait_for_selector(aide, state="visible", timeout=5000)
        viol = _audit(page)
        assert not viol, f"Visionneuse/profil {aide} [{theme}] :\n{_fmt(viol)}"


@pytest.mark.parametrize("live_server", [True], indirect=True)   # AUTH-1 : proxy déclaré
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_pastille_utilisateur(page, seeded, theme):
    """Pastille « utilisateur connecté · déconnexion » (INFRA-1). Elle n'apparaît
    que derrière le proxy d'auth (en-tête `Remote-User`) → on le simule sur toutes
    les requêtes de la page (la pastille est alors rendue par theme.js depuis
    /api/moi), puis on vérifie qu'elle est bien là ET sans violation de contraste."""
    _theme(page, theme)
    # `Remote-Groups` en plus : sans entrée dans `collection_acces`, Camille ne verrait
    # aucun album (AUTH-2) et l'audit porterait sur une page vide.
    page.set_extra_http_headers({"Remote-User": "Camille Roy",
                                 "Remote-Groups": "bd-admins"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_selector(".user-chip .user-who", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Pastille utilisateur [{theme}] :\n{_fmt(viol)}"

    # UX-14 — « Déconnexion » est passé dans le menu du compte. Fermé, le menu n'a pas de
    # rectangle et axe ne l'audite pas : l'audit ci-dessus approuverait un lien qu'il n'a
    # jamais rendu. On l'ouvre, on vérifie que la sortie est À L'ÉCRAN, puis on audite.
    page.click(".user-chip button.user-who")
    page.wait_for_selector(".compte-panel .user-logout", state="visible", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Menu du compte ouvert [{theme}] :\n{_fmt(viol)}"


# ── A11Y-3 — l'INSTRUMENT : ce que `_audit` voit, et ce qu'il laisse ─────────────────────
# Ces tests ne gardent aucune surface : ils gardent l'audit lui-même. Chacun pose sur une
# page saine le défaut qu'axe range en « incomplete », et vérifie d'abord, sur une lecture
# BRUTE d'axe, que le défaut est bien rangé là — sans quoi un test vert dirait seulement
# qu'axe a changé d'avis, et l'audit approuverait sans avoir rien vu.

_RAISONS_BRUTES = """async (sel) => {
  const r = await axe.run(document, {runOnly: {type: 'rule', values: ['color-contrast']},
                                     elementRef: true});
  const e = document.querySelector(sel);
  const ou = (liste) => liste.flatMap(v => v.nodes).filter(n => n.element === e)
    .flatMap(n => [].concat(n.any || [], n.all || [], n.none || []))
    .map(c => (c.data && c.data.messageKey) || 'violation');
  return {violation: ou(r.violations).length > 0, incomplete: ou(r.incomplete)}; }"""

# La couleur de FOND sous un élément : la première non transparente en remontant.
_POSER_COULEUR_DU_FOND = r"""(sel) => {
  const e = document.querySelector(sel);
  let a = e;
  while (a) {
    const c = getComputedStyle(a).backgroundColor;
    if (c && !/^rgba\(.*,\s*0\)$/.test(c) && c !== 'transparent') break;
    a = a.parentElement;
  }
  e.style.color = a ? getComputedStyle(a).backgroundColor : getComputedStyle(document.body).backgroundColor;
  return e.style.color; }"""


def _raisons_brutes(page, sel):
    page.evaluate(_AXE_SRC)
    return page.evaluate(_RAISONS_BRUTES, sel)


def _menu_du_compte_ouvert(page, seeded, theme):
    """Le menu du compte ouvert sur la Bibliothèque — la surface du mutant M8 d'UX-14 —,
    et la prémisse : tel quel, il passe l'audit."""
    _theme(page, theme)
    page.set_extra_http_headers({"Remote-User": "Camille Roy", "Remote-Groups": "bd-admins"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_selector(".user-chip .user-who", timeout=3000)
    page.click(".user-chip button.user-who")
    page.wait_for_selector(".compte-panel .user-logout", state="visible", timeout=3000)
    viol = _audit(page)
    assert not viol, f"prémisse : le menu du compte passe l'audit [{theme}] :\n{_fmt(viol)}"


_ENTREE_DU_MENU = ".compte-panel .user-logout"


@pytest.mark.parametrize("live_server", [True], indirect=True)   # la pastille : proxy
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y3_un_texte_de_la_couleur_de_son_fond_fait_echouer_l_audit(page, seeded, theme):
    """M8 d'UX-14, joué à demeure : l'entrée du menu du compte écrite de la couleur exacte
    de son panneau. axe la range en « incomplete » (`equalRatio`) ; l'audit la compte."""
    _menu_du_compte_ouvert(page, seeded, theme)
    page.evaluate(_POSER_COULEUR_DU_FOND, _ENTREE_DU_MENU)
    brut = _raisons_brutes(page, _ENTREE_DU_MENU)
    assert not brut["violation"] and "equalRatio" in brut["incomplete"], brut
    viol = _audit(page)
    assert any(v["id"] == "color-contrast" and "1:1" in v["help"] for v in viol), _fmt(viol)


@pytest.mark.parametrize("live_server", [True], indirect=True)   # la pastille : proxy
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y3_un_contraste_insuffisant_non_nul_reste_une_violation(page, seeded, theme):
    """Le contrôle inverse : `#777` (3,6:1 en sombre, 4,48:1 en clair) est une VIOLATION
    `color-contrast` d'axe lui-même, pas un « incomplete » que l'audit rattraperait."""
    _menu_du_compte_ouvert(page, seeded, theme)
    page.evaluate("(sel) => { document.querySelector(sel).style.color = '#777'; }",
                  _ENTREE_DU_MENU)
    assert _raisons_brutes(page, _ENTREE_DU_MENU)["violation"]
    viol = _audit(page)
    assert any(v["id"] == "color-contrast" and "A11Y-3" not in v["help"] for v in viol), \
        _fmt(viol)


@pytest.mark.parametrize("live_server", [True], indirect=True)   # la pastille : proxy
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y3_un_fond_que_axe_ne_sait_pas_mesurer_ne_fait_pas_echouer(page, seeded, theme):
    """Un « incomplete » d'une AUTRE nature — un fond en dégradé, qu'axe ne sait pas
    échantillonner — ne fait pas échouer l'audit : crier sur ce qu'axe ne mesure pas
    rendrait l'audit inutilisable."""
    _menu_du_compte_ouvert(page, seeded, theme)
    page.evaluate("(sel) => { document.querySelector(sel).style.backgroundImage = "
                  "'linear-gradient(90deg, #000, #fff)'; }", _ENTREE_DU_MENU)
    brut = _raisons_brutes(page, _ENTREE_DU_MENU)
    assert not brut["violation"] and "bgGradient" in brut["incomplete"], brut
    viol = _audit(page)
    assert not viol, _fmt(viol)


# Un texte que son conteneur défilant repousse hors de la zone visible reçoit une encre
# à ~2:1 de son fond : de quoi échouer partout, petit texte comme grand.
_ABIMER_UN_TEXTE_HORS_CHAMP = r"""async () => {
  const r = await axe.run(document, {runOnly: {type: 'rule', values: ['color-contrast']},
                                     elementRef: true});
  const raisons = (n) => [].concat(n.any || [], n.all || [], n.none || [])
    .map(c => c.data && c.data.messageKey);
  const hors = (r.incomplete.find(v => v.id === 'color-contrast') || {nodes: []}).nodes
    .filter(n => raisons(n).some(k => k === 'outsideViewport' || k === 'elmPartiallyObscured'));
  if (!hors.length) return null;
  const e = hors[hors.length - 1].element;
  let a = e;
  while (a) {
    const c = getComputedStyle(a).backgroundColor;
    if (c && c !== 'transparent' && !/^rgba\(.*,\s*0\)$/.test(c)) break;
    a = a.parentElement;
  }
  const [rr, gg, bb] = (a ? getComputedStyle(a).backgroundColor : 'rgb(255, 255, 255)')
    .match(/\d+/g).map(Number);
  e.style.color = (0.299 * rr + 0.587 * gg + 0.114 * bb) > 128 ? '#b4b4b4' : '#4a4a4a';
  e.setAttribute('data-a11y3', '');
  return e.textContent.trim().slice(0, 40); }"""

# Les surfaces dont le contenu vit dans un conteneur défilant, MESURÉES le 2026-10-21 sur
# le décor `seeded` dans une fenêtre de 260 px : la Bibliothèque (ses deux colonnes) et
# les vues de l'Administration qui en ont une (`#admin-body`, la liste et la fiche). Les
# autres n'y repoussaient rien : la Recherche et l'Exploration défilent avec la PAGE, ce
# qu'axe juge seul, et l'Atelier du décor n'a pas assez de contenu pour déborder.
# DÉRIVÉE de la déclaration et des vues, jamais énumérée à côté d'elles
# (`tests/test_surfaces.py`, « aucune seconde liste de surfaces »).
_VUES_DEFILANTES = ("comptes", "projets", "fonds")
SURFACES_DEFILANTES = tuple(
    [s for s in SURFACES_AUDITEES if s == "/corpus"]
    + [f"/administration?vue={v}" for v in VUES_ADMINISTRATION if v in _VUES_DEFILANTES])


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("surface", SURFACES_DEFILANTES)
def test_a11y3_un_texte_hors_de_la_zone_visible_n_echappe_plus(page, seeded, surface, theme):
    """Une fenêtre BASSE repousse du texte hors de la zone visible du conteneur qui
    défile ; on l'écrit à ~2:1 de son fond. axe, seul, ne le juge pas (« incomplete ») —
    la prémisse le vérifie —, l'audit l'amène dans le champ et le juge."""
    _theme(page, theme)
    page.set_viewport_size({"width": 1280, "height": 260})
    page.goto(seeded["base"] + surface, wait_until="networkidle")
    page.wait_for_timeout(600)
    page.evaluate(_AXE_SRC)
    abime = page.evaluate(_ABIMER_UN_TEXTE_HORS_CHAMP)
    assert abime is not None, f"{surface} : plus rien hors de la zone visible — la liste a vieilli"
    brut = _raisons_brutes(page, "[data-a11y3]")
    assert not brut["violation"], f"prémisse : axe seul juge déjà « {abime} » ({brut})"
    viol = _audit(page)
    assert any("hors de la zone visible" in v["help"] for v in viol), \
        f"{surface} [{theme}] « {abime} » :\n{_fmt(viol)}"
    # L'audit rend aux conteneurs leur position : rien n'a défilé pour de bon.
    assert page.evaluate("() => [...document.querySelectorAll('*')].every(e => !e.scrollTop)")


def _ouvrir_album(page, titre="A11y"):
    """La fiche d'un album, depuis la liste de gauche (UX-18)."""
    page.locator("#albums-body .album-row", has_text=titre).click()
    page.wait_for_selector("#album-detail .planches-table", timeout=3000)


def _ouvrir_collection(page, cid, onglet):
    """La fiche d'une collection par son nom, puis l'onglet voulu (UX-18)."""
    page.locator(f'#col-body .col-item[data-id="{cid}"] .col-ouvrir').click()
    fiche = page.locator(f'#col-fiche[data-id="{cid}"]')
    fiche.wait_for(timeout=3000)
    fiche.locator(f'[role="tab"][data-onglet="{onglet}"]').click()
    page.wait_for_selector(f"#col-fiche #panneau-{onglet}:not([hidden])", timeout=3000)
    return fiche


def test_a11y_corpus_modale(page, seeded):
    """Modale d'édition d'album (piège à focus + labels de formulaire), ouverte depuis la
    fiche de l'album (UX-18)."""
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(500)
    _ouvrir_album(page)
    page.click("#detail-edit")
    page.wait_for_timeout(300)
    viol = _audit(page)
    assert not viol, f"Corpus/modale :\n{_fmt(viol)}"


# Les quatre états d'un moteur, forcés (décor partagé, cf. `conftest.SANTE_RAPIDE`).
# Sans lui, une machine de test les rend presque tous « non installé » (gris) : le vert
# et le rouge — les deux seules teintes dont le contraste puisse échouer — ne seraient
# jamais À L'ÉCRAN pendant l'audit, qui passerait au vert sans avoir rien mesuré. Même
# piège que le semis d'AUTH-5.


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_administration_sante(page, seeded, theme):
    """Panneau des moteurs (SANTE-1) : les quatre états d'un moteur, dans les deux thèmes.

    Le panneau a quitté la modale de la Bibliothèque pour une SECTION de `/administration`
    le 2026-09-07 (UX-10). Ce que ce test auditait du piège à focus et du titre lié part
    donc avec elle — `dialog.js` n'est plus chargé sur cette page —, et ce qui reste est
    ce qui portait le vrai enjeu.

    Le contraste est l'enjeu : « en panne » est du PETIT texte coloré, là où l'accent
    rouge plein échoue le 4.5:1 — d'où `--ink-red` et un `--accent-green` assombri en
    thème clair. Un audit qui n'aurait sous les yeux que des lignes grises approuverait
    une palette qu'il n'a pas regardée."""
    page.route("**/api/sante*", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(SANTE_PROFOND if "profond=1" in r.request.url
                        else SANTE_RAPIDE)))
    _theme(page, theme)
    page.goto(seeded["base"] + "/administration?vue=instance", wait_until="networkidle")
    page.wait_for_selector("#sante-body .sante-ligne", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Administration/moteurs [{theme}] :\n{_fmt(viol)}"

    page.click("#sante-eprouver")
    page.wait_for_selector(".sante-panne", timeout=5000)
    # Les quatre états sont bien à l'écran : sinon l'audit qui suit ne mesure rien.
    for classe in (".sante-ok", ".sante-panne", ".sante-absent"):
        assert page.locator(classe).count(), f"état {classe} absent du rendu"
    viol = _audit(page)
    assert not viol, f"Administration/moteurs éprouvés [{theme}] :\n{_fmt(viol)}"

def test_a11y_corpus_materiel(page, seeded):
    """Matériel de numérisation (A6) : détail d'album ouvert (table planches + ligne matériel
    par planche) audité, puis round-trip de la source de numérisation (saisie modale →
    persistée)."""
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(500)
    _ouvrir_album(page)                                      # la fiche de l'album
    viol = _audit(page)
    assert not viol, f"Corpus/détail matériel :\n{_fmt(viol)}"
    # Round-trip : renseigner la source de numérisation via la modale → persistée.
    page.click("#detail-edit")
    page.wait_for_selector("#m-source-num", timeout=3000)
    page.fill("#m-source-num", "Epson V850, 600 dpi")
    page.click("#m-save")
    page.wait_for_timeout(500)
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        alb = c.get("/api/albums").json()
    finally:
        c.close()
    assert any(a.get("source_numerisation") == "Epson V850, 600 dpi" for a in alb)


def test_a11y_corpus_relecture(page, seeded):
    """Relecture par planche (ANN-4 / B5) : ouvrir le détail d'album, auditer la colonne
    (pastille de statut + sélecteur d'override), puis forcer « faite » → override persisté."""
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(500)
    _ouvrir_album(page)                                      # la fiche de l'album
    page.wait_for_selector("#album-detail .rel-sel", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Corpus/relecture :\n{_fmt(viol)}"
    # Round-trip : forcer le statut via le sélecteur → override persisté.
    page.select_option(".rel-sel", "faite")
    page.wait_for_timeout(500)
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        planches = c.get(f"/api/albums/{seeded['album']}/planches").json()
    finally:
        c.close()
    st = planches[0]["relecture_statut"]
    assert st["force"] is True and st["statut"] == "faite"


def test_deep_link_introuvable_diagnostique(page, seeded):
    """F5 : un deep-link vers une planche/région inexistante AFFICHE un diagnostic (toast) au
    lieu d'échouer en silence."""
    page.goto(seeded["base"] + f"/?album={seeded['album']}&planche=999999",
              wait_until="networkidle")
    page.wait_for_selector("#toasts .toast", timeout=4000)
    assert "introuvable" in page.locator("#toasts .toast").first.inner_text().lower()


def test_a11y_visionneuse_undo(page, seeded):
    """Undo (D1) : une action d'annotation (locuteur) posée via l'API est annulée par Ctrl+Z
    dans la Visionneuse (round-trip UI → serveur → rafraîchissement) ; le toast d'annulation
    reste accessible."""
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        p = c.post("/api/personnages", json={"nom": "Tournesol"}).json()
        c.put(f"/api/regions/{seeded['region']}/locuteur", json={"personnage_id": p["id"]})
        assert c.get(f"/api/regions/{seeded['region']}/locuteur").json()["locuteur"]  # bien posé
    finally:
        c.close()
    page.goto(seeded["base"] + SURFACES_AUDITEES["/"](seeded), wait_until="networkidle")
    page.wait_for_timeout(700)
    page.locator("body").press("Control+z")                  # hors champ de saisie
    page.wait_for_timeout(500)
    viol = _audit(page)
    assert not viol, f"Visionneuse/undo :\n{_fmt(viol)}"
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        assert c.get(f"/api/regions/{seeded['region']}/locuteur").json()["locuteur"] is None
    finally:
        c.close()


def test_a11y_exploration_domaines(page, seeded):
    """Domaines (piste B) : créer un domaine dans la modale Lexique (a11y audité), puis
    rattacher une dimension via le sélecteur → persisté (round-trip UI → serveur)."""
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        c.post("/api/attributs/dimensions", json={"cible": "case", "nom": "valence"})
    finally:
        c.close()
    page.goto(seeded["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-lexique")
    page.wait_for_selector("#lex-dom-nom", timeout=3000)
    page.fill("#lex-dom-nom", "émotions")
    page.click("#lex-dom-add")
    page.wait_for_selector("#lexique-modal .lex-domaine", timeout=3000)   # domaine rendu
    viol = _audit(page)
    assert not viol, f"Exploration/domaines :\n{_fmt(viol)}"
    # Rattacher la dimension au domaine via le sélecteur → PATCH .../domaine (déplier d'abord :
    # les champs vivent dans un <details>).
    page.locator('.lex-term:not(.lex-domaine) > summary').first.click()
    page.locator('.lex-term select[data-f="domaine_id"]').first.select_option(label="émotions")
    page.wait_for_timeout(400)
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        dims = c.get("/api/attributs/dimensions").json()
    finally:
        c.close()
    assert any(d["nom"] == "valence" and d["domaine"] == "émotions" for d in dims)


def test_a11y_exploration_lexique(page, seeded):
    """Modale « Lexique situé » (A4) : audite l'a11y du panneau ouvert (piège à focus +
    labels de formulaire, badge d'état) ET vérifie le round-trip d'édition (une définition
    saisie dans l'UI est bien persistée via PATCH)."""
    # Peuple le vocabulaire facetté (dimension + valeur) en plus du tag semé.
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        dim = c.post("/api/attributs/dimensions",
                     json={"cible": "case", "nom": "registre"}).json()
        c.post(f"/api/attributs/dimensions/{dim['id']}/valeurs", json={"valeur": "argot"})
    finally:
        c.close()

    page.goto(seeded["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-lexique")
    page.wait_for_selector("#lexique-modal .lex-term", timeout=3000)
    page.click("#lexique-modal .lex-term > summary")          # déplie le 1er terme
    page.wait_for_timeout(200)
    viol = _audit(page)
    assert not viol, f"Exploration/lexique :\n{_fmt(viol)}"

    # Round-trip : documenter la 1re dimension via l'UI → persisté.
    ta = page.locator('#lexique-modal .lex-term textarea[data-f="definition"]').first
    ta.fill("niveau de langue")
    ta.blur()
    page.wait_for_timeout(400)
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        lex = c.get("/api/lexique").json()
    finally:
        c.close()
    defs = ([d["definition"] for d in lex["dimensions"]]
            + [v["definition"] for d in lex["dimensions"] for v in d["valeurs"]])
    assert "niveau de langue" in defs


def test_a11y_visionneuse_alignement(page, seeded):
    """Panneau Personnage → alignement d'autorité (A5) : audite l'a11y de la section ouverte
    (puce-lien + champ) ET vérifie le round-trip (URI saisie dans l'UI → persistée)."""
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        p = c.post("/api/personnages", json={"nom": "Tournesol"}).json()
        c.put(f"/api/regions/{seeded['region']}/locuteur", json={"personnage_id": p["id"]})
    finally:
        c.close()
    page.goto(seeded["base"] + SURFACES_AUDITEES["/"](seeded), wait_until="networkidle")
    page.wait_for_timeout(700)
    page.click('.mode-btn[data-mode="annotation"]')
    page.wait_for_selector("#loc-align-section:not([hidden])", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Visionneuse/alignement :\n{_fmt(viol)}"
    # Round-trip : saisir une URI dans l'UI → alignement persisté (source auto-détectée).
    inp = page.locator("#loc-align-input")
    inp.fill("https://www.wikidata.org/wiki/Q42")
    inp.press("Enter")
    page.wait_for_timeout(400)
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        al = c.get(f"/api/personnages/{p['id']}/alignements").json()
    finally:
        c.close()
    assert any(a["uri"] == "https://www.wikidata.org/wiki/Q42" and a["source"] == "wikidata"
               for a in al)


def test_a11y_exploration_concordance(page, seeded):
    """Concordance (KWIC, B2) : passer en vue Concordance, chercher un lemme du corpus, puis
    auditer l'a11y des DEUX rendus (aligné + liste) et vérifier le deep-link Visionneuse.
    Skippé proprement si le corpus n'a pas de tokens (spaCy absent → concordance vide)."""
    page.goto(seeded["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.select_option("#f-vue", "concordance")
    page.fill("#f-lemme", "pouvoir")                 # « POUVOIR ABSOLU » du corpus semé
    try:
        page.wait_for_selector("#kwic .kwic-row", timeout=5000)      # rendu aligné (défaut)
    except Exception:
        pytest.skip("Aucun token de concordance (NLP/spaCy absent) — rendu KWIC non exerçable")
    viol = _audit(page)
    assert not viol, f"Exploration/concordance aligné :\n{_fmt(viol)}"

    page.select_option("#f-kwic-style", "liste")
    page.wait_for_selector("#kwic .kwic-item", timeout=5000)
    viol = _audit(page)
    assert not viol, f"Exploration/concordance liste :\n{_fmt(viol)}"

    href = page.locator("#kwic a").first.get_attribute("href")       # chaque ligne mène à la case
    assert "region=" in href and "planche=" in href


def test_a11y_exploration_croisement(page, seeded):
    """Croisement 2D (ANA-2 / B3) : passer en vue Croisement (POS × type par défaut), auditer
    l'a11y du tableau (en-têtes, heatmap, cellules-boutons), puis vérifier qu'un clic de
    cellule descend aux preuves (bascule en Concordance pré-filtrée). Skippé si aucun token."""
    page.goto(seeded["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.select_option("#f-vue", "croisement")
    try:
        page.wait_for_selector("#croise .croise-hit", timeout=5000)      # ≥ 1 cellule cliquable
    except Exception:
        pytest.skip("Aucun token de croisement (NLP/spaCy absent) — tableau non exerçable")
    viol = _audit(page)
    assert not viol, f"Exploration/croisement :\n{_fmt(viol)}"

    page.click("#croise .croise-hit")                                   # drill → preuves
    page.wait_for_function("document.getElementById('f-vue').value === 'concordance'", timeout=3000)
    page.wait_for_selector("#kwic .kwic-row, #kwic .kwic-item", timeout=5000)


def test_a11y_exploration_accord(page, seeded):
    """Accord modèle↔humain (NLP-1 / B4) : ouvrir la modale, auditer son a11y (piège à focus,
    table, barres). Si le corpus a des tokens (spaCy), on valide un token d'abord pour exercer
    aussi le rendu du tableau (sinon on audite l'état « aucun token relu »)."""
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        toks = c.get(f"/api/regions/{seeded['region']}/tokens").json()
        if toks:                                     # valider le 1er token → 1 token relu
            c.put(f"/api/regions/{seeded['region']}/tokens/{toks[0]['ordre']}",
                  json={"etat": "valide"})
    finally:
        c.close()
    page.goto(seeded["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-accord")
    page.wait_for_selector("#accord-modal:not([hidden]) #accord-body", timeout=3000)
    page.wait_for_timeout(300)                       # laisse le fetch + rendu se faire
    viol = _audit(page)
    assert not viol, f"Exploration/accord :\n{_fmt(viol)}"


@pytest.mark.parametrize("live_server", [True], indirect=True)   # attribution alice/bob
def test_a11y_exploration_accord_inter(page, seeded):
    """Accord inter-annotateurs (ANN-5) : créer une divergence, puis auditer la modale
    PEUPLÉE — table d'accord et liste de divergences.

    Il auditait une modale qu'il croyait avoir remplie, sans jamais vérifier qu'elle
    l'était. Le décor était correct — le marqueur `live_server(True)` est là, donc alice et
    bob existent vraiment — mais RIEN ne le contrôlait : sa fragilité se démontre en
    retirant `BD_AUTH_PROXY` du sous-processus, auquel cas les deux auteurs deviennent NULL,
    aucune divergence n'est créée, la modale affiche « Aucune re-touche entre auteurs
    distincts »... et le test passe. Mesuré le 2026-08-27 (constat T8). Axe ne juge que
    l'accessibilité, et une modale vide est parfaitement accessible.

    Le défaut n'est donc pas dans le décor mais dans ce que le test AFFIRME : il ne dit rien
    de son propre montage, si bien que n'importe quelle régression d'authentification, de
    route ou de contrat de token le viderait sans le faire échouer. C'est la vacuité par
    l'amont, plus discrète que l'assertion molle : elle ne s'attrape pas en lisant
    l'assertion, seulement en se demandant ce qui la précède.

    Trois gardes désormais, et elles sont l'essentiel : la divergence est CONFIRMÉE côté
    serveur avant qu'on regarde l'écran, les deux auteurs sont NOMMÉS (ce que la seule
    présence de re-touches ne garantit pas), et l'écran doit montrer la TABLE — que le rendu
    ne produit que si `retouches` est non nul. Enfin, l'absence de tokens devient un skip
    EXPLICITE : ne rien pouvoir mesurer et mesurer zéro ne sont pas le même résultat.
    """
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ECRITURE)
    try:
        toks = c.get(f"/api/regions/{seeded['region']}/tokens").json()
        if not toks:
            pytest.skip("aucun token (spaCy absent) : sans divergence constructible, "
                        "auditer la modale ne mesurerait que son état vide")
        o = toks[0]["ordre"]
        for qui, pos in (("alice", "NOUN"), ("bob", "VERB")):
            c.put(f"/api/regions/{seeded['region']}/tokens/{o}",
                  json={"etat": "corrige", "pos": pos},
                  headers={"Remote-User": qui, "Remote-Groups": "bd-admins"})
        rapport = c.get("/api/analyse/accord-inter").json()
    finally:
        c.close()
    assert rapport.get("retouches"), (
        f"aucune re-touche inter-auteurs construite : {rapport} — le décor a échoué, "
        "et auditer la modale ne dirait rien de ce que ce test prétend couvrir")
    assert set(rapport["auteurs"]) == {"alice", "bob"}, rapport["auteurs"]

    page.set_extra_http_headers(ADMIN)          # le serveur exige une identité
    page.goto(seeded["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-accord-inter")
    # `.accord-table` et non `#accord-inter-body` : le corps existe TOUJOURS, la table
    # seulement quand le rapport porte des re-touches. C'est là toute la différence.
    page.wait_for_selector("#accord-inter-modal:not([hidden]) .accord-table", timeout=5000)
    viol = _audit(page)
    assert not viol, f"Exploration/accord-inter :\n{_fmt(viol)}"


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("surface", list(SURFACES_AUDITEES))
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_portee_vide(page, seeded, theme, surface):
    """Bandeau « aucune collection ne vous est ouverte » (AUTH-2).

    Il n'apparaît que dans un état qu'aucun autre test ne visite : derrière le proxy, avec
    une identité à qui rien n'a été accordé. Sans ce test, le seul écran que verra une
    personne mal configurée serait aussi le seul que l'audit n'aurait jamais regardé.

    TOUTES les surfaces, et la liste se DÉRIVE de `SURFACES_AUDITEES` : `theme.js`
    injecte le bandeau en tête de `<main>` partout, donc toute surface neuve hérite de
    cet état sans que personne y pense. Elle était écrite à la main jusqu'au 2026-09-07,
    dans le fichier même dont la déclaration venait de passer à cinq — la garde d'UX-10
    ne pouvait pas la voir : elle interdit une liste de surfaces posée À CÔTÉ de la
    déclaration, pas une seconde liste plus bas dans le même module. La Visionneuse reste
    celle dont la mise en page souffre le plus d'un bloc inattendu.
    """
    _theme(page, theme)
    page.set_extra_http_headers({"Remote-User": "sans-droits"})   # aucun groupe
    page.goto(seeded["base"] + surface, wait_until="networkidle")
    page.wait_for_selector(".portee-vide", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Portée vide [{surface} · {theme}] :\n{_fmt(viol)}"


def _deplier_bandeau(page):
    """Ouvre le bandeau de portée vide s'il est replié, et rend son `<details>`.

    Depuis le repli, tout ce qui n'est pas le titre vit derrière un `<details>` fermé,
    donc INVISIBLE : `wait_for()` et `inner_text()` de Playwright attendent la visibilité,
    pas la présence. Les tests qui parlent du CONTENU (référent, groupes) l'ouvrent donc
    d'abord — ce qu'une personne fait aussi. Celui qui parle du PLI lui-même ne l'appelle
    pas : c'est son objet.
    """
    pli = page.locator(".portee-vide details")
    pli.wait_for(timeout=3000)
    if not pli.evaluate("e => e.open"):
        page.click(".portee-vide summary")
    # On attend l'ÉTAT, pas le geste. Sans cette ligne le helper cliquait et repartait
    # sans jamais vérifier que le clic avait porté : un clic avalé — le bandeau naît
    # après la réponse d'`/api/moi`, donc pendant un rendu — laissait le test suivant
    # attendre trois secondes une visibilité qui ne viendrait pas, puis échouer en
    # accusant le RÉFÉRENT d'être absent alors que le pli était resté fermé. Cinq
    # tests passent par ici : un helper sans postcondition déplace l'erreur au lieu
    # de la dire, et c'est le plus cher des silences.
    page.wait_for_function(
        "() => { const d = document.querySelector('.portee-vide details');"
        "        return d && d.open; }", timeout=3000)
    return pli


def _geo(page, sel):
    """Rectangle rendu d'un élément, en pixels CSS entiers. `None` s'il n'existe pas."""
    return page.evaluate(
        """s => { const e = document.querySelector(s); if (!e) return null;
                  const r = e.getBoundingClientRect();
                  return {x: Math.round(r.x), y: Math.round(r.y),
                          w: Math.round(r.width), h: Math.round(r.height)}; }""", sel)


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("largeur", [1440, 1024, 820])
def test_portee_vide_ne_decale_pas_la_grille_de_la_visionneuse(page, seeded, largeur):
    """Le bandeau de portée vide s'injecte en tête de `<main>` sur les QUATRE surfaces.
    Sur trois, `<main>` est un bloc qui défile et il s'y pose sans rien déranger. Sur la
    Visionneuse, `<main id="body">` est une grille de TROIS colonnes taillées pour TROIS
    panneaux : le bandeau y devient un QUATRIÈME item auto-placé, prend la colonne de la
    navigation, et décale tout le reste d'un cran — la navigation dans la colonne du
    canevas, le canevas dans les 300 px du panneau, le panneau rejeté à la rangée
    suivante.

    `test_a11y_portee_vide` visite pourtant cet écran, et sa docstring annonce que « la
    Visionneuse est celle dont la mise en page souffre le plus d'un bloc inattendu ». Il
    ne l'a jamais vu : axe-core audite l'ACCESSIBILITÉ, et une grille décalée reste
    parfaitement accessible. La garde ne s'est pas trompée, elle regardait ailleurs — et
    c'est la forme d'échec la plus coûteuse, puisqu'elle rend un vert sincère.

    Trois largeurs, une par régime de colonnes (3 · 2 · 1). Le défaut EMPIRE en
    descendant : sous 900 px il ne reste qu'un bandeau et un canevas, qui se partagent
    alors la hauteur en deux — `align-content: stretch` répartit le reste également
    entre deux rangées `auto`, et le bandeau grossit d'autant.
    """
    page.set_viewport_size({"width": largeur, "height": 900})
    page.set_extra_http_headers({"Remote-User": "sans-droits"})   # aucun groupe
    page.goto(seeded["base"] + "/", wait_until="networkidle")
    page.wait_for_selector(".portee-vide", timeout=3000)

    body = _geo(page, "#body")
    bandeau = _geo(page, ".portee-vide")
    canevas = _geo(page, "#viewer")
    etat = f"[{largeur} px] body={body} bandeau={bandeau} canevas={canevas}"

    # 1. Le bandeau tient une RANGÉE et non une colonne : il occupe toute la largeur.
    assert abs(bandeau["w"] - body["w"]) <= 1, \
        "le bandeau occupe une colonne au lieu de la rangée — " + etat

    # 2. Et il se dimensionne sur son CONTENU : le canevas garde le gros de la hauteur.
    #    C'est ce que la colonne unique perd en premier, et le seul contrôle qui morde
    #    à 820 px, où la largeur est déjà pleine des deux côtés du correctif.
    #    Cette assertion a d'abord été seule, et elle mordait — le bandeau faisait alors
    #    212 px. Le repli l'a ramené à 44, et elle a cessé de voir : sans la règle des
    #    rangées, `align-content: stretch` répartit le reste également entre deux rangées
    #    `auto`. Mesuré sous mutation le 2026-09-06 : à 1440 px le bandeau monte à 339 et
    #    le canevas à 429, si bien que « le canevas est plus haut » reste VRAI et que la
    #    garde approuve le défaut entier. À 1024 et 820 px elle l'attrapait encore (382
    #    contre 386) — l'angle mort n'était donc pas total, il était pile sur la largeur
    #    de bureau. Une garde qui ne voit plus qu'aux tailles où l'on ne travaille pas
    #    est le mode d'échec d'ARCH-2, et il aura suffi d'ALLÉGER l'écran pour l'ouvrir.
    #
    #    On mesure donc l'ÉTIREMENT lui-même. `<details>` est en `display: block` : sa
    #    hauteur suit son contenu et ne s'étire jamais. L'écart entre l'enveloppe et lui
    #    vaut exactement le rembourrage (.9231rem × 2 = 24 px) tant que la grille ne tire
    #    pas dessus, et vaut 321 à 368 px dès qu'elle le fait — un ordre de grandeur au-
    #    dessus du seuil, aux TROIS largeurs. Vrai que le bandeau soit replié ou ouvert,
    #    ce que l'ancienne formulation ne pouvait pas être.
    #    COL-4 — le bandeau porte aussi, à droite, « En attendant : Mon bac à sable » : son
    #    contenu est le PLUS HAUT de ses enfants, pli ou geste, et c'est à lui qu'on mesure
    #    l'écart (sans quoi un bouton plus haut qu'une ligne passerait pour un étirement).
    pli = _geo(page, ".portee-vide > details")
    contenu = page.evaluate("""() => Math.max(...[...document.querySelectorAll(
      '.portee-vide > *')].map((e) => e.getBoundingClientRect().height))""")
    assert contenu >= pli["h"]
    assert bandeau["h"] - contenu <= 30, (
        f"le bandeau est ÉTIRÉ par la grille au lieu de suivre son contenu — pli={pli} "
        + etat)
    assert canevas["h"] > bandeau["h"], \
        "le bandeau prend autant de hauteur que le canevas — " + etat

    # 3. Là où les trois colonnes existent, elles sont dans le bon ordre : les trois
    #    panneaux sur UNE rangée, et le canevas tenant la colonne souple.
    #
    #    Le seuil qui les fait tomber en tiroirs vit dans `style.css` et NULLE PART
    #    ailleurs — c'est écrit en toutes lettres dans le bloc des tiroirs, et un nombre
    #    recopié ici en ferait une seconde vérité à tenir d'accord. On ne le recopie donc
    #    pas : on DEMANDE à la page si la navigation est encore une colonne. Sa règle de
    #    base ne déclare aucun `position` ; le seuil la passe en `absolute`.
    if page.evaluate("() => getComputedStyle("
                     "document.querySelector('#sidebar')).position === 'static'"):
        nav, panneau = _geo(page, "#sidebar"), _geo(page, "#panel")
        assert nav["y"] == canevas["y"] == panneau["y"], \
            f"les panneaux ne sont pas sur la même rangée — nav={nav} panneau={panneau} {etat}"
        assert canevas["w"] > nav["w"] + panneau["w"], \
            f"le canevas n'a pas la colonne souple — nav={nav} panneau={panneau} {etat}"


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_a11y_proxy_sans_identite(page, seeded):
    """L'autre portée vide : l'application se croit derrière un proxy d'auth et ne reçoit
    AUCUN en-tête. Elle ferme tout, délibérément — mais sans message, l'écran est celui
    d'un corpus vide et l'opérateur cherche une panne de base de données.

    Aucune pastille utilisateur ici (il n'y a pas d'identité), donc c'est bien le bandeau
    seul qui porte l'explication.
    """
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")   # sans en-têtes
    page.wait_for_selector(".portee-vide", timeout=3000)
    assert page.locator(".user-chip").count() == 0
    # Le titre est dans le `<summary>` depuis le repli. Le sélecteur reste précis pour
    # la même raison : le bandeau porte un second `strong` depuis AUTH-4, le nom du
    # référent au milieu d'une phrase. Ce cas-ci est le SEUL ouvert d'office, donc son
    # titre se lit sans rien déplier.
    assert "ne vous reconnaît pas" in page.locator(".portee-vide summary > strong").inner_text()
    viol = _audit(page)
    assert not viol, f"Proxy sans identité :\n{_fmt(viol)}"


# --------------------------------------------------------------------------- #
# Collections (AUTH-3) — l'écran qui remplace `tools/gerer_collections.py`, et « Qui entre »
# qui a rejoint la Bibliothèque avec l'étape 3 d'AUTH-12
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_qui_entre(page, seeded, theme):
    """« Qui entre » : déplier, refuser, faire entrer, cocher un cran — audité à chaque étape.

    C'est l'écran où l'on décide QUI entre. Une régression d'accessibilité y coûterait plus
    cher qu'ailleurs : on n'administre pas des droits à l'aveugle. Il vivait dans
    l'Administration (« 👥 Accès aux collections ») jusqu'à l'étape 3 d'AUTH-12 ; il vit en
    tête de la collection dépliée, dans la Bibliothèque, et se règle en ACTES.

    Chaque état est attendu avant d'être audité : le tableau (et non « Chargement… »), le
    refus rouge, puis la marque ambre « inconnu de l'annuaire » — du petit texte coloré, la
    catégorie qui échoue le 4.5:1. `bd-lettrage` n'est pas dans la doublure de l'annuaire
    que charge `live_server` : c'est ce qui allume la marque.
    """
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=ECRITURE)
    try:
        r = c.post("/api/collections", json={"nom": "Corpus colonial"})
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        du_projet(c, cid, "groupe", "annotateurs", headers=ECRITURE)
        du_projet(c, cid, "groupe", "bd-lettrage", headers=ECRITURE)   # COL-3, tranche 3c (F2) — on n'entre dans
        r = c.put(f"/api/collections/{cid}/acces", json={
            "genre": "groupe", "principal": "annotateurs", "niveau": "ecriture"})
        assert r.status_code == 200, r.text
    finally:
        c.close()

    _theme(page, theme)
    # Une fenêtre HAUTE : la collection dépliée est longue. Ce n'est plus une protection —
    # `_audit` amène dans le champ ce qu'un conteneur défilant repousse (A11Y-3) —, mais
    # l'audit y juge tout d'un seul tour.
    page.set_viewport_size({"width": 1280, "height": 2400})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    item = _ouvrir_collection(page, cid, "qui")
    item.locator(".qe-qui, .qe-table th[scope=row]", has_text="annotateurs").first.wait_for(
        timeout=5000)
    item.locator(".qe-choix optgroup").wait_for(state="attached", timeout=5000)
    viol = _audit(page)
    assert not viol, f"Qui entre [{theme}] :\n{_fmt(viol)}"

    # Un refus AFFICHÉ, dans la collection dépliée : l'encre rouge en petit texte.
    item.locator(".qe-faire-entrer").click()
    item.locator(".qe-msg.erreur").wait_for(timeout=3000)
    viol = _audit(page)
    assert not viol, f"Qui entre/refus affiché [{theme}] :\n{_fmt(viol)}"

    item.locator(".qe-choix").select_option("autre")
    item.locator(".qe-nom").fill("bd-lettrage")
    item.locator(".qe-genre").select_option("groupe")
    item.locator(".qe-faire-entrer").click()
    item.locator(".qe-marque", has_text="inconnu de l'annuaire").wait_for(timeout=5000)
    item.locator(".qe-msg.alerte").wait_for(timeout=5000)
    viol = _audit(page)
    assert not viol, f"Qui entre/nom inconnu de l'annuaire [{theme}] :\n{_fmt(viol)}"

    # Le cran d'écriture, coché d'un geste : les actes liés ne se cochent pas séparément.
    with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith("/acces")):
        item.locator('.qe-case[data-cran="ecriture"][data-principal="bd-lettrage"]').check()
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=ECRITURE)
    try:
        acces = c.get(f"/api/collections/{cid}/acces").json()
    finally:
        c.close()
    assert ("bd-lettrage", "groupe", "ecriture") in {
        (a["principal"], a["genre"], a["niveau"]) for a in acces}

    # Déménagé, pas dupliqué (UX-10) : l'Administration n'a plus de panneau d'accès.
    page.goto(seeded["base"] + "/administration", wait_until="networkidle")
    assert page.locator("#col-body").count() == 0, "le panneau des accès subsiste en Administration"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_bibliotheque_collections(page, seeded, theme):
    """COL-2 — créer une collection et la décrire, dans la Bibliothèque, audité à chaque
    étape.

    L'état qui compte est le FORMULAIRE ouvert : des groupes de champs et des notes en petit
    texte, c'est-à-dire la catégorie qui échoue le 4.5:1. La lecture n'en montre rien, et un
    audit qui s'arrêterait là approuverait sans avoir vu. UX-18 : le formulaire s'ouvre au
    geste (« Modifier »), onglet par onglet — les deux sont audités.
    """
    _theme(page, theme)
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.wait_for_selector("#col-body .col-item", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Bibliothèque/collections [{theme}] :\n{_fmt(viol)}"

    page.click("#col-creer")
    page.fill("#col-nom", "Corpus colonial")
    page.click("#col-add")
    # La collection créée s'ouvre sur « Qui entre » : c'est le geste suivant de qui crée.
    item = page.locator("#col-fiche", has_text="Corpus colonial")
    item.locator(".qe-titre").wait_for(timeout=3000)
    # Le message dit où faire entrer quelqu'un : « Qui entre », dans la fiche qui vient de
    # s'ouvrir (AUTH-12, étape 3). Sous le geste de création, et non sous la liste (COL-2).
    assert "Qui entre" in page.locator("#col-creer-msg").inner_text(), (
        page.locator("#col-creer-msg").inner_text())
    viol = _audit(page)
    assert not viol, f"Bibliothèque/fiche, Qui entre [{theme}] :\n{_fmt(viol)}"
    item.locator('[role="tab"][data-onglet="diffusion"]').click()
    item.locator('[data-modifier="diffusion"]').click()
    item.locator('[data-champ="statut_diffusion"]').wait_for(timeout=3000)
    viol = _audit(page)
    assert not viol, f"Bibliothèque/formulaire de diffusion [{theme}] :\n{_fmt(viol)}"
    item.locator("[data-annuler-edition]").click()
    item.locator('[role="tab"][data-onglet="description"]').click()
    item.locator('[data-modifier="description"]').click()

    # Un refus AFFICHÉ, dans la fiche. Il vivait sous la liste jusqu'à COL-2 ; son encre
    # rouge est du petit texte, la catégorie qui échoue le 4.5:1, et aucun audit ne l'avait
    # jamais photographiée allumée — ni avant le déménagement, ni après.
    item.locator('[data-champ="nom"]').fill("Collection par défaut")
    item.locator("[data-enregistrer]").click()
    item.locator(".col-msg.erreur").wait_for(timeout=3000)
    viol = _audit(page)
    assert not viol, f"Bibliothèque/refus affiché [{theme}] :\n{_fmt(viol)}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_bibliotheque_en_calque(page, seeded, theme):
    """UX-18 — chaque état que la refonte donne à la Bibliothèque, audité dans les deux
    thèmes : une collection cochée (sa fiche, onglet Albums, la barre du lot allumée par un
    album coché), deux collections comparées, la fiche d'un album (une planche cochée, son
    lot), et, à 375 px, les CARTES sous la fiche étroite. L'audit générique ne voit que la
    fiche du projet, au chargement : il approuverait des onglets, des actes et des cartes
    qu'il n'a jamais rendus."""
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=ECRITURE)
    try:
        cid = c.get(f"/api/albums/{seeded['album']}/collections").json()[0]["id"]
        autre = c.post("/api/collections", json={"nom": "Étude B"}).json()["id"]
        r = c.put(f"/api/albums/{seeded['album']}/collections/{autre}")
        assert r.status_code == 201, r.text
    finally:
        c.close()
    _theme(page, theme)
    page.set_viewport_size({"width": 1280, "height": 1400})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_selector("#col-body .col-item", timeout=3000)

    page.locator(f'#col-body [data-calque="{cid}"]').check()
    fiche = page.locator(f'#col-fiche[data-id="{cid}"]')
    fiche.locator(f'[data-coche-album="{seeded["album"]}"]').check()
    page.wait_for_selector("#panneau-albums .bi-lot", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Bibliothèque/collection cochée, lot [{theme}] :\n{_fmt(viol)}"

    page.locator(f'#col-body [data-calque="{autre}"]').check()
    page.wait_for_selector(".bi-comparaison", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Bibliothèque/comparaison [{theme}] :\n{_fmt(viol)}"

    _ouvrir_album(page)
    page.locator(f'#album-detail input[data-pid="{seeded["planche"]}"]').check()
    page.wait_for_selector("#album-detail .bi-lot", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Bibliothèque/fiche d'album, lot [{theme}] :\n{_fmt(viol)}"

    page.set_viewport_size({"width": 375, "height": 1400})
    page.goto(seeded["base"] + f"/corpus?album={seeded['album']}", wait_until="networkidle")
    page.wait_for_selector("#album-detail .planches-table", timeout=3000)
    assert page.locator("#album-detail .planches-table thead").is_hidden(), (
        "à 375 px, la fiche d'album n'est pas passée en cartes")
    viol = _audit(page)
    assert not viol, f"Bibliothèque/fiche d'album en cartes, 375 px [{theme}] :\n{_fmt(viol)}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_import_en_lot(page, seeded, theme):
    """UX-11 — l'import en lot de la fiche d'un album, audité dans ses deux états : PENDANT
    (la barre, « n sur N », « Arrêter ») et APRÈS (le bilan au ton d'un import partiel, et
    la liste des fichiers refusés). La requête d'import du second fichier est tenue tant que
    l'audit de l'état « pendant » n'est pas fini."""
    _theme(page, theme)
    page.set_viewport_size({"width": 1280, "height": 1400})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    _ouvrir_album(page)
    vues = []

    def tenir_la_seconde(route):
        vues.append(route)
        if len(vues) != 2:
            route.continue_()
    page.route("**/api/albums/*/import", tenir_la_seconde)
    with page.expect_file_chooser() as choix:
        page.click("#bi-importer")
    choix.value.set_files([
        {"name": "b.png", "mimeType": "image/png", "buffer": make_png(300, 300)},
        {"name": "a.png", "mimeType": "image/png", "buffer": b"pas une image"},
    ])
    page.wait_for_selector("#bi-import-barre", timeout=5000)
    expect(page.locator("#bi-import-etat")).to_have_text("Import : 2 sur 2 — b.png · 1 échec",
                                                         timeout=5000)
    viol = _audit(page)
    assert not viol, f"Bibliothèque/import en cours [{theme}] :\n{_fmt(viol)}"
    vues[1].continue_()
    expect(page.locator("#bi-import-etat")).to_have_text("1 planche importée, 1 échec",
                                                         timeout=15000)
    expect(page.locator(".bi-import-echecs li")).to_have_count(1)
    viol = _audit(page)
    assert not viol, f"Bibliothèque/bilan d'import [{theme}] :\n{_fmt(viol)}"


def test_corpus_appartenance_album(page, seeded):
    """L'appartenance N-N depuis l'UI — la case qu'AUTH-2 avait laissée ouverte, faute de
    propriétaire pour dire qui a le droit de déplacer quoi.

    COL-3, tranche 2 — supprimer un album de sa DERNIÈRE collection n'est plus refusé : la
    copie est gardée au fonds. Le geste se CONFIRME, et la confirmation dit où va le travail ;
    refusée, rien ne bouge. Rangé dans une seconde collection, l'album se supprime de l'une
    sans rien demander : le travail reste dans l'autre.
    """
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=ECRITURE)
    try:
        autre = c.post("/api/collections", json={"nom": "Représentations"}).json()["id"]
    finally:
        c.close()
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(400)
    _ouvrir_album(page)                    # « Sur les collections », dans la fiche
    page.wait_for_selector("#album-range[data-pret]", timeout=3000)
    # Une seule collection au départ : la quitter envoie la copie au fonds, et le dire.
    dialogues = []

    def refuser(d):
        dialogues.append(d.message)
        d.dismiss()
    page.once("dialog", refuser)
    page.locator("#album-range-cases input[data-ranger]:checked").first.click()
    page.wait_for_function("() => document.querySelectorAll("
                           "'#album-range-cases input[data-ranger]:checked').length === 1",
                           timeout=3000)
    assert len(dialogues) == 1, dialogues
    assert "gardée au fonds" in dialogues[0], dialogues
    assert "pourrez la rendre depuis l'Administration" in dialogues[0], dialogues

    # Rangé ailleurs, l'album vit dans deux collections — et la sortie ne demande plus rien.
    page.locator(f'#album-range-cases input[data-ranger="{autre}"]').click()
    page.wait_for_function("() => document.querySelectorAll("
                           "'#album-range-cases input[data-ranger]:checked').length === 2",
                           timeout=3000)
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=ECRITURE)
    try:
        vues = c.get(f"/api/albums/{seeded['album']}/collections").json()
    finally:
        c.close()
    assert autre in {x["id"] for x in vues} and len(vues) == 2
    page.locator(f'#album-range-cases input[data-ranger="{autre}"]').click()
    page.wait_for_function("() => document.querySelectorAll("
                           "'#album-range-cases input[data-ranger]:checked').length === 1",
                           timeout=3000)
    assert len(dialogues) == 1


@pytest.mark.parametrize("live_server", [True], indirect=True)
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_supprimer_deux_reponses(page, live_server, theme):
    """COL-3, tranche 2 — le panneau « Supprimer… » audité, dans les deux thèmes, sous un
    compte qui n'a pas importé l'album : la seconde réponse y est une DEMANDE, donc le
    champ du motif est là. Puis la ligne qui porte la pastille d'une demande, encre rouge
    sur le fond de la table, auditée elle aussi."""
    admin = {**ECRITURE}
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=admin) as c:
        cid = c.post("/api/collections", json={"nom": "Étude"}).json()["id"]
        aid = c.post("/api/albums", json={"titre": "Doublon", "collection_id": cid}).json()["id"]
        du_projet(c, cid, "utilisateur", "sam", headers=ECRITURE)
        r = c.put(f"/api/collections/{cid}/acces",
                  json={"genre": "utilisateur", "principal": "sam", "niveau": "ecriture"})
        assert r.status_code == 200, r.text
    _theme(page, theme)
    page.set_extra_http_headers({"Remote-User": "sam"})
    page.goto(live_server + "/corpus", wait_until="networkidle")
    _ouvrir_album(page, "Doublon")
    page.locator('#album-detail [data-act="supprimer"]').click()
    page.wait_for_selector("#suppr-modal:not([hidden]) #sp-retrait button[data-retirer]",
                           timeout=5000)
    assert page.locator("#sp-motif").is_visible()
    viol = _audit(page)
    assert not viol, f"Supprimer… [{theme}] :\n{_fmt(viol)}"
    page.fill("#sp-motif", "Importé par erreur.")
    page.check("#sp-certif")
    page.click("#sp-def")
    page.wait_for_selector("#suppr-modal", state="hidden", timeout=5000)
    page.wait_for_selector(".sp-pastille", timeout=5000)
    viol = _audit(page)
    assert not viol, f"Bibliothèque avec une demande [{theme}] :\n{_fmt(viol)}"
    assert aid


@pytest.mark.parametrize("live_server", [True], indirect=True)
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_le_fonds_et_ses_demandes(page, live_server, theme):
    """COL-3, tranche 2 — le bloc « Le fonds » de l'Administration, PEUPLÉ : une demande de
    suppression en tête (motif, « Détruire », « Garder »), une copie gardée et son « Rendre
    à… », un document appelé par personne et sa pastille ; puis le responsable d'un projet
    devant « Demander sa suppression… », motif ouvert. L'audit générique de `/administration` ne voit le
    fonds que vide de tout cela."""
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE) as c:
        cid = c.post("/api/collections", json={"nom": "Étude"}).json()["id"]
        a1 = c.post("/api/albums", json={"titre": "Doublon", "collection_id": cid}).json()["id"]
        a2 = c.post("/api/albums", json={"titre": "Gardé", "collection_id": cid}).json()["id"]
        assert c.delete(f"/api/albums/{a2}/collections/{cid}").status_code == 204
        du_projet(c, cid, "utilisateur", "sam", headers=ECRITURE)
        r = c.put(f"/api/collections/{cid}/acces",
                  json={"genre": "utilisateur", "principal": "sam", "niveau": "ecriture"})
        assert r.status_code == 200, r.text
        pid = c.post("/api/projets", json={"nom": "Séminaire"}).json()["id"]
        r = c.put(f"/api/projets/{pid}/membres",
                  json={"genre": "utilisateur", "principal": "rui", "role": "responsable"})
        assert r.status_code in (200, 201), r.text
    entete = {k: v for k, v in ECRITURE.items() if k not in ("Remote-User", "Remote-Groups")}
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                      headers={"Remote-User": "sam", **entete}) as c:
        r = c.post("/api/demandes", json={"genre": "suppression_document", "album_id": a1,
                                          "motif": "Importé deux fois.", "certifie": True})
        assert r.status_code == 201, r.text
    _theme(page, theme)
    page.set_extra_http_headers({"Remote-User": "decor", "Remote-Groups": "bd-admins"})
    # COL-3 — la demande se répond dans « À faire », où la page s'ouvre : dépliée, elle
    # montre son motif, « Détruire » et « Garder ».
    page.goto(live_server + "/administration", wait_until="networkidle")
    page.wait_for_selector("#afaire-bloc:not([hidden]) .fd-demande", timeout=5000)
    page.click(".fd-demande [data-af-deplier]")
    page.wait_for_selector(".fd-demande [data-fd-accepter]", timeout=5000)
    viol = _audit(page)
    assert not viol, f"À faire, une demande dépliée [{theme}] :\n{_fmt(viol)}"
    # Puis la liste du fonds et la fiche de la copie gardée, avec son « Rendre à… ».
    page.goto(live_server + "/administration?vue=fonds", wait_until="networkidle")
    page.locator("#fd-objets .fd-objet", has_text="Gardé").click()
    page.wait_for_selector(".fd-gardee select", timeout=5000)
    viol = _audit(page)
    assert not viol, f"Le fonds [{theme}] :\n{_fmt(viol)}"

    page.set_extra_http_headers({"Remote-User": "rui"})
    page.goto(live_server + "/administration?vue=projets", wait_until="networkidle")
    page.click("[data-pj-demander-ouvrir]")
    page.wait_for_selector("#pj-demander-motif", timeout=5000)
    viol = _audit(page)
    assert not viol, f"Demander la suppression d'un projet [{theme}] :\n{_fmt(viol)}"


# --------------------------------------------------------------------------- #
# Figures citables (DROIT-1) — citer se décide sur la région
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_figure_citable(page, seeded, theme):
    """Le panier de figures et sa modale, audités.

    Le bouton d'export ne s'affiche QUE quand le panier est garni : un bouton permanent
    sur un panier vide promet une action qui n'aboutit pas.
    """
    _theme(page, theme)
    page.goto(seeded["base"] + SURFACES_AUDITEES["/"](seeded), wait_until="networkidle")
    page.wait_for_timeout(600)
    assert page.locator("#btn-fig-open").is_hidden()      # panier vide → pas de promesse
    page.click("#btn-fig-add")
    page.wait_for_selector("#btn-fig-open:not([hidden])", timeout=3000)
    assert "1" in page.locator("#btn-fig-open").inner_text()
    page.click("#btn-fig-open")
    page.wait_for_selector("#fig-champs label", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Figures [{theme}] :\n{_fmt(viol)}"
    # Vider REMASQUE le bouton. Sans ce second temps, le test ne lirait que
    # l'attribut `hidden` du HTML statique — il passerait même si le code
    # cessait de le piloter.
    page.click("#fig-vider")
    # `state="hidden"` : par défaut `wait_for_selector` attend un élément VISIBLE, donc
    # attendre un `[hidden]` expire toujours — que le code marche ou non.
    page.wait_for_selector("#btn-fig-open", state="hidden", timeout=3000)


def test_les_mentions_viennent_du_serveur(page, seeded):
    """La liste des mentions n'est pas recopiée dans le JS : deux listes qui divergent
    produiraient une légende amputée sans rien signaler. L'écran doit donc afficher
    exactement ce que `GET /api/figure/champs` annonce."""
    attendus = httpx.get(seeded["base"] + "/api/figure/champs", trust_env=False,
                         timeout=30).json()
    page.goto(seeded["base"] + SURFACES_AUDITEES["/"](seeded), wait_until="networkidle")
    page.wait_for_timeout(600)
    page.click("#btn-fig-add")
    page.click("#btn-fig-open")
    page.wait_for_selector("#fig-champs label", timeout=3000)
    values = page.locator("#fig-champs input").evaluate_all(
        "els => els.map(e => e.value)")
    assert values == [c["champ"] for c in attendus]


def test_export_de_figure_telecharge_un_zip(page, seeded):
    """Le bout de la chaîne : le zip arrive vraiment dans le navigateur, et il porte le
    nom composé par le SERVEUR — le recomposer côté client ferait diverger deux
    horodatages pour un seul export."""
    page.goto(seeded["base"] + SURFACES_AUDITEES["/"](seeded), wait_until="networkidle")
    page.wait_for_timeout(600)
    page.click("#btn-fig-add")
    page.click("#btn-fig-open")
    page.wait_for_selector("#fig-champs label", timeout=3000)
    with page.expect_download(timeout=10000) as dl:
        page.click("#fig-export")
    fichier = dl.value
    assert fichier.suggested_filename.startswith("figures_")
    assert fichier.suggested_filename.endswith(".zip")


# --------------------------------------------------------------------------- #
# DROIT-1 — l'embargo cesse d'être muet sur l'écran Collections
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_collections_embargo_echu(page, seeded, theme):
    """L'application ne lève jamais un embargo toute seule, mais elle cesse de se taire :
    un embargo échu que personne ne remarque garde un corpus fermé par INERTIE.

    Audité dans les deux thèmes parce que la pastille est du PETIT TEXTE coloré — la
    catégorie qui échoue le 4.5:1 quand on y met un accent brut au lieu d'un token d'encre.

    COL-2 — la pastille a suivi la date dans la Bibliothèque : l'échéance se signale là où
    elle se modifie. UX-18 — dans l'en-tête de la fiche de la collection ET dans l'onglet
    Diffusion et dépôt, dérivée au même endroit (`colEmbargo`).
    """
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=ECRITURE)
    try:
        cid = c.post("/api/collections", json={"nom": "Fonds sous embargo"}).json()["id"]
        r = c.patch(f"/api/collections/{cid}",
                    json={"statut_diffusion": "embargo", "date_embargo": "2020-01-01"})
        assert r.status_code == 200, r.text
    finally:
        c.close()

    _theme(page, theme)
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.wait_for_selector("#col-body .col-item", timeout=3000)
    fiche = _ouvrir_collection(page, cid, "diffusion")
    # La pastille est RENDUE, et son libellé porte le sens — pas la seule couleur.
    pastille = fiche.locator(".lf-sous .col-embargo")
    pastille.wait_for(timeout=3000)
    assert "échu" in pastille.inner_text().lower()
    assert "2020-01-01" in (pastille.get_attribute("title") or "")
    # Et l'onglet de la diffusion le dit en clair, sous le régime.
    expect(fiche.locator("#panneau-diffusion .col-embargo-note")).to_contain_text("échu depuis")

    viol = _audit(page)
    assert not viol, f"Collections/embargo [{theme}] :\n{_fmt(viol)}"


# --------------------------------------------------------------------------- #
# AUTH-4 — nommer l'administrateur plutôt que le taire
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_comptes_et_groupes(page, seeded, theme):
    """« 👥 Comptes et groupes » (AUTH-12) audité AVEC du contenu, sur la vraie route.

    Le bloc remplace la vue des comptes d'AUTH-7, et hérite de sa leçon : cette vue-là
    s'auditait sans proxy, donc VIDE, et l'audit approuvait un tableau qui n'existait pas.
    Ici la liste, les fiches et « À regarder » ne naissent qu'une fois la route répondue,
    et la moitié de ce qu'ils montrent se déplie — un repli fermé n'est jamais passé devant
    axe (leçon d'AUTH-6). On attend donc chaque ÉTAT, et on déplie avant d'auditer.

    Le décor : la doublure de l'annuaire (chargée par `live_server`), un compte de
    l'annuaire VENU, et un login hors annuaire qui a changé d'identité — pour que les
    marques en `--ink-red` et en ambre, du petit texte coloré, aient quelque chose à rendre.
    Trois fiches, parce que chacune a ses propres marques : un compte, un groupe de douze
    comptes dont des jamais venus, une collection.

    La fiche d'une collection porte le panneau « Qui entre » depuis UX-16, sur le fond de
    CE bloc et non sur celui de la Bibliothèque. Elle s'audite donc avec des accès : un
    compte jamais venu, un groupe de l'annuaire et un groupe qu'il ne connaît pas — ses deux
    marques, un lien par nom, et la note des administrateurs. Sans eux le panneau dirait
    « Aucun accès n'est accordé », et l'audit approuverait un tableau qui n'existe pas.
    """
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30)
    try:
        # Sans `Remote-Name` : un en-tête HTTP ne porte pas d'accent, et le nom lisible vient
        # de toute façon de l'annuaire.
        c.get("/api/moi", headers={"Remote-User": "proprio"})
        c.get("/api/moi", headers={"Remote-User": "ancien", "Remote-Name": "Nom Un"})
        c.get("/api/moi", headers={"Remote-User": "ancien", "Remote-Name": "Nom Deux"})
        collection = c.get("/api/collections", headers=ADMIN).json()[0]["id"]
        for genre, nom, niveau in (("utilisateur", "arrivant", "proprietaire"),
                                   ("groupe", "annotateurs", "ecriture"),
                                   ("groupe", "ancien-cours", "lecture")):
            du_projet(c, collection, genre, nom, headers=ECRITURE)
            r = c.put(f"/api/collections/{collection}/acces", headers=ECRITURE,
                      json={"genre": genre, "principal": nom, "niveau": niveau})
            assert r.status_code == 200, r.text
    finally:
        c.close()

    _theme(page, theme)
    # Une fenêtre HAUTE : la liste défile dans sa colonne, la page dans `#admin-body`, et axe
    # ne juge pas le contraste d'un texte qu'un conteneur défilant cache. Mesuré par mutation
    # le 2026-09-17 : l'ambre BRUT sur les lignes de la liste passait l'audit dès que « À
    # regarder » déplié les poussait hors de la colonne visible. Depuis A11Y-3, `_audit` les
    # amène dans le champ lui-même ; la fenêtre haute reste, et juge tout d'un seul tour.
    page.set_viewport_size({"width": 1280, "height": 2400})
    page.set_extra_http_headers(ADMIN)
    page.goto(seeded["base"] + "/administration?compte=ancien", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.wait_for_selector("#cg-fiche-titre", timeout=5000)
    # La liste porte bien les comptes de la doublure, et l'annuaire est LU : sans quoi
    # l'audit porterait sur l'état « sans annuaire », qui n'a ni signaux ni membres.
    assert page.locator("#cg-objets .cg-objet").count() >= 10
    assert "Annuaire lu" in page.locator("#cg-annuaire").inner_text()
    assert page.locator("#cg-fiche .cg-puce.rouge", has_text="identité changée").count() == 1
    page.locator("#cg-signaux details.cg-replie > summary").first.click()
    page.locator("#cg-fiche .cg-depart > summary").click()
    page.locator("#cg-fiche .cg-aide > summary").click()
    viol = _audit(page)
    assert not viol, f"Comptes et groupes, fiche d'un compte [{theme}] :\n{_fmt(viol)}"

    page.goto(seeded["base"] + "/administration?axe=groupes&groupe=etudiants-bd-2026",
              wait_until="networkidle")
    page.wait_for_selector("#cg-fiche .cg-puce.alerte", timeout=5000)
    page.locator("#cg-objets details.cg-a-parte > summary").click()
    viol = _audit(page)
    assert not viol, f"Comptes et groupes, fiche d'un groupe [{theme}] :\n{_fmt(viol)}"

    page.goto(seeded["base"] + f"/administration?axe=collections&collection={collection}",
              wait_until="networkidle")
    page.wait_for_selector("#cg-fiche a.cg-decrire", timeout=5000)
    # Le panneau est RENDU, avec ses marques : le tableau, puis l'annuaire qui les pose.
    panneau = page.locator("#cg-fiche section[data-qui-entre]")
    panneau.locator(".qe-marque").wait_for(timeout=5000)
    # Les lignes d'ACCÈS, et non les titres de groupe : la collection 1 est la base du projet
    # de repli (v31), dont « Qui entre » se lit en deux groupes (COL-3, écran de la 3a).
    assert panneau.locator(".qe-table tbody tr[data-principal]").count() == 3
    assert panneau.locator(".acces-jamais-vu").count() == 1
    assert panneau.locator(".col-note-admin").count() == 1
    viol = _audit(page)
    assert not viol, f"Comptes et groupes, fiche d'une collection [{theme}] :\n{_fmt(viol)}"


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_portee_vide_nomme_un_destinataire(page, seeded, theme):
    """Le bandeau envoyait une personne BLOQUÉE « demander un accès à un administrateur »
    sans lui dire à qui. Or elle ne lit AUCUNE collection, donc aucun référent de
    collection : seul un référent d'instance peut l'aider. C'est le seul endroit où ce
    chantier sert quelqu'un que quelque chose empêche."""
    _theme(page, theme)
    page.set_extra_http_headers({"Remote-User": "sans-droits"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    _deplier_bandeau(page)          # « sans-droits » n'est pas une panne → replié
    ligne = page.locator(".portee-vide-referent")
    ligne.wait_for(timeout=3000)
    assert "Ana Ruiz" in ligne.inner_text()
    # Le contact est CLIQUABLE : une adresse qu'il faut recopier à la main n'en est pas
    # tout à fait une.
    assert ligne.locator('a[href="mailto:ana@labo.fr"]').count() == 1
    # La réserve est dite, pas laissée à découvrir — raccourcie le 2026-09-06 d'une
    # phrase à une parenthèse, parce qu'elle s'adressait à un lecteur qui n'en peut rien.
    # Elle n'a pas DISPARU : le référent vient de la configuration, l'application ne sait
    # pas s'il est encore là, et taire cette limite serait pire que la dire brièvement.
    assert "déclaré à la configuration" in ligne.inner_text()
    viol = _audit(page)
    assert not viol, f"Portée vide + référent [{theme}] :\n{_fmt(viol)}"


def _referent_remplace(page, referent):
    """Laisse `/api/moi` répondre pour de vrai, et n'en remplace QUE `acces.referent`.

    Le serveur live porte un référent complet (`conftest`) ; en relancer un par état
    coûterait un serveur pour trois lignes de texte. Tout le reste de la réponse — portée
    vide, identité, groupes — reste celui du serveur. La forme remplacée est celle de
    `main._referent_instance()`, verrouillée côté serveur par `test_referent_instance`."""
    def servir(route):
        rep = route.fetch()
        corps = rep.json()
        corps["acces"]["referent"] = referent
        route.fulfill(status=rep.status, json=corps)
    page.route("**/api/moi", servir)


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("entetes, amorce", [
    ({"Remote-User": "sans-droits"}, "Demandez un accès à "),     # identité, rien d'ouvert
    ({}, "Prévenez "),                                            # aucune identité reçue
], ids=["identifie", "anonyme"])
def test_le_bandeau_rapporte_un_referent_PARTIEL(page, seeded, entetes, amorce):
    """`_referent_instance()` rend un dict dès qu'UNE des deux variables est posée : deux
    états partiels sont donc atteignables, et la ligne du référent en disait faux sur les
    deux (AUTH-4, observé à l'écran le 2026-09-29).

    NOM SEUL — la réserve « (contact déclaré à la configuration) » était ajoutée sans
    condition : un nom, aucune adresse, et l'affirmation qu'une adresse existe. C'est une
    phrase qui CONCLUT au lieu de rapporter (AUTH-8), et elle ment à la seule personne pour
    qui joindre le référent est la seule action possible. On exige qu'elle DISE l'absence
    et ne dise plus « contact déclaré ».

    CONTACT SEUL — `nom || contact` retombait sur le contact, que la branche du contact
    ajoutait une seconde fois. On exige une seule occurrence, et en lien.

    Les deux amorces sont jouées, parce que la ligne se compose derrière chacune."""
    page.set_extra_http_headers(entetes)

    # --- nom seul ---
    _referent_remplace(page, {"nom": "Ana Ruiz", "contact": None})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    _deplier_bandeau(page)
    ligne = page.locator(".portee-vide-referent")
    texte = ligne.inner_text()
    assert texte.startswith(amorce + "Ana Ruiz"), texte
    assert "contact déclaré" not in texte, \
        f"la ligne affirme un contact qui n'existe pas : {texte!r}"
    assert "aucun contact" in texte, f"l'absence de contact n'est pas dite : {texte!r}"
    assert ligne.locator("a").count() == 0, "aucun lien : il n'y a rien à joindre"
    page.unroute("**/api/moi")

    # --- contact seul ---
    _referent_remplace(page, {"nom": None, "contact": "ana@labo.fr"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    _deplier_bandeau(page)
    texte = ligne.inner_text()
    assert texte.startswith(amorce + "ana@labo.fr"), texte
    assert texte.count("ana@labo.fr") == 1, f"le contact est répété : {texte!r}"
    assert ligne.locator('a[href="mailto:ana@labo.fr"]').count() == 1, \
        "le contact seul doit rester cliquable"
    assert "(contact déclaré à la configuration)" in texte    # vraie, ici : elle reste
    viol = _audit(page)
    assert not viol, f"Portée vide + référent sans nom :\n{_fmt(viol)}"
    page.unroute("**/api/moi")

    # --- nom ET contact : inchangé ---
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    _deplier_bandeau(page)
    assert ligne.inner_text() == (amorce + "Ana Ruiz — ana@labo.fr "
                                  "(contact déclaré à la configuration).")

    # --- aucun référent : pas de ligne du tout ---
    _referent_remplace(page, None)
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    _deplier_bandeau(page)
    assert ligne.count() == 0, "sans référent, le bandeau ne doit nommer personne"


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_qui_entre_declare_les_administrateurs(page, seeded):
    """`_acces_de()` ne lit que `collection_acces`, où un administrateur ne figure sur
    AUCUNE ligne — sa portée court-circuite la table en amont. La liste affichait donc
    trois noms là où quatre personnes lisent, sur un écran qui protège soigneusement cette
    liste au motif qu'elle parle de personnes. Défaut de DÉCLARATION, pas d'autorisation.

    La note a suivi les accès dans la Bibliothèque (AUTH-12, étape 3), sous « Qui entre ».
    Ce test, lui, est passé au travers du déménagement : il visait `/administration`, où
    plus aucune collection ne s'affiche. C'est la passe e2e ENTIÈRE qui l'a trouvé — ni la
    passe ciblée ni le harnais de mutation ne le jouaient, et la relecture des tests
    retargetés ne l'a pas vu non plus, faute de le chercher là où il n'était pas attendu.
    """
    page.set_extra_http_headers({"Remote-User": "alice", "Remote-Groups": "bd-admins"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.wait_for_selector("#col-body .col-item", timeout=3000)
    page.locator("#col-body .col-item .col-ouvrir").first.click()    # sur « Qui entre »
    note = page.locator(".col-note-admin")
    # Plus tard qu'avant : la note vit sous « Qui entre », qui attend la description des
    # droits, les accès, puis l'annuaire.
    note.wait_for(timeout=5000)
    txt = note.inner_text()
    assert "bd-admins" in txt and "toute" in txt


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_le_referent_d_une_collection_s_enregistre(page, seeded):
    """Une ADRESSE, pas un droit : la nommer n'accorde rien. DÉSIGNER reste au
    propriétaire — choisir l'interlocuteur d'un espace engage l'espace entier.

    COL-2 — le référent a suivi les descripteurs dans la Bibliothèque, et se saisit dans le
    même formulaire qu'eux."""
    page.set_extra_http_headers({"Remote-User": "alice", "Remote-Groups": "bd-admins"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.wait_for_selector("#col-body .col-item", timeout=3000)
    page.locator("#col-body .col-item .col-ouvrir").first.click()
    page.locator('#col-fiche [role="tab"][data-onglet="description"]').click()
    page.locator('#col-fiche [data-modifier="description"]').click()
    page.wait_for_selector('#col-fiche [data-champ="referent_nom"]', timeout=3000)
    page.locator('#col-fiche [data-champ="referent_nom"]').fill("Ana Ruiz")
    page.locator('#col-fiche [data-champ="referent_contact"]').fill("ana@labo.fr")
    page.locator("#col-fiche [data-enregistrer]").click()
    page.locator("#col-fiche .col-msg", has_text="enregistrée").wait_for(timeout=3000)

    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers={"Remote-User": "alice", "Remote-Groups": "bd-admins"})
    try:
        cols = c.get("/api/collections").json()
    finally:
        c.close()
    assert any(x["referent_nom"] == "Ana Ruiz"
               and x["referent_contact"] == "ana@labo.fr" for x in cols)


@pytest.mark.parametrize("live_server", [True], indirect=True)
@pytest.mark.parametrize("niveau", ["lecture", "ecriture"])
def test_le_participant_non_proprietaire_voit_le_referent(page, seeded, niveau):
    """Le premier jet mettait le référent ET la déclaration d'administration sous le
    `return` du panneau réservé au propriétaire — donc visibles de la seule personne qui
    les avait écrits. Or c'est le participant SANS pouvoir qui a besoin de savoir à qui
    écrire, et qu'un administrateur d'instance lit sans figurer dans les accès. Désigner
    engage la collection et reste au propriétaire ; lire est le geste de quelqu'un qui a
    une question.

    COL-2 puis AUTH-12 (étape 3) — les deux vivent dans la Bibliothèque, dans la fiche de la
    collection : le référent avec la description, la déclaration avec « Qui entre », que le
    participant ne voit pas. Et le formulaire reste invisible en ÉCRITURE comme en lecture :
    annoter n'est pas décrire. UX-18 — chacun dans son onglet, que le participant OUVRE :
    aucun onglet ne porte de garde, chaque bloc pose sa question."""
    admin = {"Remote-User": "alice", "Remote-Groups": "bd-admins",
             "X-BD-Requete": "1"}
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=admin)
    try:
        cid = c.get("/api/collections").json()[0]["id"]
        assert c.patch(f"/api/collections/{cid}",
                       json={"referent_nom": "Ana Ruiz",
                             "referent_contact": "ana@labo.fr"}).status_code == 200
        du_projet(c, cid, "utilisateur", "bob", headers=ECRITURE)
        assert c.put(f"/api/collections/{cid}/acces",
                      json={"principal": "bob", "genre": "utilisateur",
                            "niveau": niveau}).status_code in (200, 201)
    finally:
        c.close()

    # bob participe sans posséder : `administrable` est faux pour lui.
    page.set_extra_http_headers({"Remote-User": "bob", "Remote-Groups": "chercheurs"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.wait_for_selector("#col-body .col-item", timeout=3000)
    page.locator(f'#col-body .col-item[data-id="{cid}"] .col-ouvrir').click()
    page.locator('#col-fiche [role="tab"][data-onglet="description"]').click()
    page.wait_for_selector(".col-note-referent", timeout=3000)
    assert "Ana Ruiz" in page.locator(".col-note-referent").inner_text()
    # Il LIT la description ; il ne la modifie pas, et ne désigne personne.
    assert page.locator("#biblio-fiche [data-champ]").count() == 0, "il ne doit pas pouvoir DÉSIGNER"
    assert page.locator("#biblio-fiche [data-enregistrer]").count() == 0
    assert page.locator("#biblio-fiche [data-modifier]").count() == 0

    # Il apprend, dans « Qui entre », qu'un administrateur lit sans figurer dans les accès —
    # sans voir la liste, qui est une donnée sur des personnes.
    page.locator('#col-fiche [role="tab"][data-onglet="qui"]').click()
    page.locator(".col-note-admin").wait_for(timeout=3000)
    assert page.locator("#biblio-fiche .qe").count() == 0, "il ne doit pas voir qui entre"
    assert page.locator("#biblio-fiche .qe-case").count() == 0
    assert "bd-admins" in page.locator(".col-note-admin").inner_text()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_le_verrou_dit_par_qui(page, seeded):
    """`planches.verrou_par` est consigné depuis la v22 et aucun écran ne le montrait :
    on lisait « verrouillée le … » sans savoir à qui demander la levée — la seule chose
    qu'on ait besoin de savoir devant un verrou purement informatif.

    « par vous » se décide sur le LOGIN et non sur le nom affiché : deux personnes peuvent
    porter le même nom, et se voir attribuer le verrou d'un homonyme serait pire que de ne
    rien dire."""
    alice = {"Remote-User": "alice", "Remote-Name": "Alice Renard",
             "Remote-Groups": "bd-admins", "X-BD-Requete": "1"}
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=alice)
    try:
        c.get("/api/moi")                       # alimente le miroir `utilisateur`
        pl = c.get(f"/api/albums/{seeded['album']}/planches").json()[0]
        assert c.patch(f"/api/planches/{pl['id']}/verrou",
                       json={"verrouillee": True}).status_code == 200
    finally:
        c.close()

    # Bob voit le NOM d'alice, pas son login.
    page.set_extra_http_headers({"Remote-User": "bob", "Remote-Groups": "bd-admins"})
    page.goto(seeded["base"] + f"/?album={seeded['album']}&planche={seeded['planche']}",
              wait_until="networkidle")
    page.wait_for_timeout(600)
    titre = page.locator("#lock-toggle").get_attribute("title")
    assert "Alice Renard" in titre, titre
    assert "alice" not in page.locator("#lock-toggle").inner_text()

    # Alice, elle, lit « par vous » — la comparaison porte sur le login.
    page.set_extra_http_headers(alice)
    page.goto(seeded["base"] + f"/?album={seeded['album']}&planche={seeded['planche']}",
              wait_until="networkidle")
    page.wait_for_timeout(600)
    assert "par vous" in page.locator("#lock-toggle").inner_text()


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_le_bandeau_ne_se_deplie_d_office_que_pour_une_vraie_panne(page, seeded):
    """Le bandeau faisait 212 px sur les quatre surfaces, quel que soit l'état décrit.

    Il se replie désormais derrière son titre — sauf dans le seul cas qu'on SACHE être
    une panne : aucune identité ne parvient alors que `BD_AUTH_PROXY` est déclaré. Là il
    n'existe pas de lecture bénigne, et celui qui doit réparer le `forward_auth` ne sait
    pas qu'il faudrait déplier.

    Les autres restent repliés, « aucun groupe » COMPRIS — et ce cas-là est le vrai
    arbitrage. AUTH-8 l'a rendu plus fin : l'application distingue désormais l'en-tête
    ABSENT de l'en-tête VIDE, et la ligne technique le dit (cf. le test des quatre
    situations). Le dépliage d'office ne suit PAS, et c'est délibéré : que « absent »
    signifie une panne de recopie est DÉDUIT des sources d'Authelia, pas mesuré sur ce
    déploiement, et cette mesure est une case encore ouverte. On ne déplie d'office que
    pour une panne qu'on sait établir.

    Distinguer à l'écran et déplier d'office sont donc deux décisions séparées, prises sur
    deux degrés de certitude différents. Le jour où la case se ferme, c'est ici que le
    second cas s'ajoutera — et ce test est l'endroit qui l'exige.

    Le test vérifie enfin que replier n'est pas PERDRE : le référent d'AUTH-4 est toujours
    dans le document, à un clic. C'est la seule chose qui distingue un repli d'une
    suppression, et rien d'autre ne la garderait.
    """
    def etat(entetes):
        page.set_extra_http_headers(entetes)
        page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
        page.wait_for_selector(".portee-vide", timeout=3000)
        return page.locator(".portee-vide details").evaluate("e => e.open")

    # Identité + groupes reçus, aucun accès accordé — rien n'est cassé.
    assert etat({"Remote-User": "carol", "Remote-Groups": "linguistes,stage"}) is False, \
        "le cas bénin ne devrait pas se déplier d'office"

    # Identité, en-tête des groupes absent — nommé à l'écran depuis AUTH-8, mais pas
    # établi comme panne SUR CE DÉPLOIEMENT : reste replié.
    assert etat({"Remote-User": "dave"}) is False, \
        "l'en-tête absent se NOMME sans se déplier : la déduction n'est pas une mesure"

    # Identité, en-tête des groupes reçu vide — bénin, et le seul des deux à l'être.
    assert etat({"Remote-User": "erin", "Remote-Groups": ""}) is False, \
        "« aucun groupe déclaré » n'est pas une panne du tout"

    # Aucune identité derrière un proxy déclaré — la seule panne certaine.
    assert etat({}) is True, "la panne de forward_auth doit se lire sans cliquer"

    # Replier n'est pas perdre : le contenu est là, invisible, à un clic.
    page.set_extra_http_headers({"Remote-User": "sans-droits"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_selector(".portee-vide", timeout=3000)
    ref = page.locator(".portee-vide-referent")
    assert ref.count() == 1, "le référent doit être dans le document, même replié"
    assert not ref.is_visible(), "…et masqué tant qu'on n'a pas déplié"
    _deplier_bandeau(page)
    assert ref.is_visible(), "un clic sur le résumé doit le rendre"
    assert "Ana Ruiz" in ref.inner_text()

    viol = _audit(page)
    assert not viol, f"Bandeau replié :\n{_fmt(viol)}"


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_la_ligne_technique_distingue_quatre_situations(page, seeded):
    """La ligne technique du bandeau distingue quatre situations que le même écran vide
    confondait : aucun en-tête d'identité ; l'en-tête des groupes NON REÇU ; reçu mais
    VIDE ; les groupes, nommés. C'est là que servent les `groupes` que `/api/moi` renvoie
    depuis INFRA-2 sans qu'aucune surface les lise.

    Elle en distinguait TROIS (AUTH-1) : « aucun groupe » recouvrait les deux du milieu.
    `groupes()` fait `headers.get("Remote-Groups") or ""`, si bien qu'un en-tête absent et
    un en-tête vide y arrivaient identiques — correct pour une LISTE, insuffisant pour un
    diagnostic, puisque l'un rend tous les accès par groupe inopérants et l'autre
    n'appelle aucune réparation. AUTH-8 fait voyager la différence à part
    (`acces.entete_groupes`).

    Elle RAPPORTE toujours, elle n'explique pas — et ce test a VERROUILLÉ DEUX FOIS une
    formule qui expliquait. D'abord « le proxy pose Remote-User sans Remote-Groups »,
    affirmée quand le code ne pouvait pas l'établir. Puis, après AUTH-8, « à vérifier côté
    proxy : les accès par groupe sont sans effet » — cette fois le code POUVAIT établir
    l'état de l'en-tête, mais pas ce qu'il signifie. La mesure du 2026-09-09 l'a tranché
    dans l'autre sens : un compte sans aucun groupe ne reçoit pas l'en-tête VIDE, il ne le
    reçoit pas du tout ; et un compte AVEC groupe rend l'en-tête, donc la recopie
    fonctionne, donc l'absence ne peut pas être une panne. La ligne accusait un proxy qui
    va bien.

    CE QUE CE TEST GARDE DÉSORMAIS, et il fallait le choisir plutôt que le subir : une
    garde réécrite d'après le texte qu'elle juge devient un MIROIR — elle affirmera
    toujours ce que le code dit, donc plus jamais rien. Il ne verrouille donc AUCUNE
    formulation. Il exige deux PROPRIÉTÉS, vraies quel que soit le libellé : que la ligne
    ne tire aucune CONCLUSION de l'absence de l'en-tête, et que les deux états du fil
    restent DISTINCTS à l'écran. Le second compte autant que le premier — la distinction
    `None` / `""` survit dans le code, un déploiement configuré autrement peut produire le
    vide, et la faire disparaître de l'écran remplacerait une fausse alerte par une
    confusion.

    MESURÉ AVANT D'ÊTRE ÉCRIT, parce que tout ce test en dépend : Playwright transmet bien
    un en-tête de valeur VIDE (`Remote-Groups: `), il ne le supprime pas. S'il l'avait
    supprimé, le cas « reçu vide » aurait en réalité rejoué le cas « absent », et le test
    serait resté vert sans avoir jamais vu l'état qu'il prétend couvrir."""
    # Identité + groupes, mais aucun accès accordé → rien n'est cassé.
    page.set_extra_http_headers({"Remote-User": "carol", "Remote-Groups": "linguistes,stage"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    _deplier_bandeau(page)
    txt = page.locator(".portee-vide-technique").inner_text()
    assert "linguistes" in txt and "stage" in txt

    # Identité, en-tête des groupes ABSENT. Le FAIT est dicible ; la conclusion ne l'est
    # plus, et c'est la mesure du 2026-09-09 qui l'a retirée.
    page.set_extra_http_headers({"Remote-User": "dave"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    _deplier_bandeau(page)
    txt_absent = page.locator(".portee-vide-technique").inner_text()
    assert "non reçu" in txt_absent.lower(), txt_absent
    for conclusion in ("sans effet", "côté proxy"):
        assert conclusion not in txt_absent, (
            "l'absence de l'en-tête n'autorise AUCUNE conclusion sur ce déploiement : "
            "mesuré le 2026-09-09, c'est aussi ce que rend un compte sans groupe, et un "
            "compte avec groupe prouve que la recopie fonctionne. Une ligne qui accuse "
            f"envoie chercher une panne qui n'existe pas : {txt_absent!r}")

    # Identité, en-tête des groupes REÇU VIDE → un autre état du fil, donc un autre
    # message. Ce déploiement ne le produit pas ; un autre le peut, et le code le sait.
    page.set_extra_http_headers({"Remote-User": "erin", "Remote-Groups": ""})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    _deplier_bandeau(page)
    txt_vide = page.locator(".portee-vide-technique").inner_text()
    assert "VIDE" in txt_vide and "aucun groupe déclaré" in txt_vide, txt_vide
    assert txt_vide != txt_absent, (
        "les deux états d'en-tête doivent rester DISTINCTS à l'écran : la différence "
        "survit dans le code (None vs \"\"), elle a coûté un chantier, et la faire "
        f"disparaître de l'écran la rendrait invisible là où elle sert : {txt_vide!r}")

    # Aucune identité → les groupes ne disent rien, la ligne ne paraît pas.
    page.set_extra_http_headers({})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_selector(".portee-vide", timeout=3000)
    _deplier_bandeau(page)
    assert "Aucun en-tête d'identité reçu" in page.locator(
        ".portee-vide-technique").inner_text()


@requires_kumiko
@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_segmenter_depuis_la_visionneuse_ne_fait_pas_regresser_l_ecran(page, seeded):
    """B6 (AUDIT-1) — l'ÉCRAN ne doit pas montrer la régression que la base a refusée.

    Le correctif serveur ne suffisait pas : `viewer.js` posait `state.planche.statut =
    "segmentee"` en dur après le clic, et ce champ alimente le bandeau et la pastille. Une
    planche `annotee` re-segmentée paraissait donc retomber — jusqu'au prochain
    rechargement, où elle se corrigeait seule. Un défaut qui se répare en rafraîchissant
    est un défaut que personne ne signale.

    Écrit APRÈS coup, et il aura fallu DEUX corrections pour dire vrai de cette seule ligne.
    Le commit qui la réparait affirmait le cas non testable, « faute de Kumiko dans le
    serveur live » : faux, `lib/kumiko` est là. Puis ce test, écrit dans la foulée, s'est
    révélé VACANT — il passait avec la constante en dur, parce que `segmenter()` ne
    redessine pas le bandeau. Le défaut est réel mais DIFFÉRÉ : il attend le premier
    réaffichage depuis la mémoire, d'où la re-sélection ci-dessous. Deux affirmations
    confiantes et non mesurées sur trois lignes de code.

    Le test tourne avec le vrai moteur et se skippe là où le clone est absent.
    """
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=60, headers=ECRITURE)
    try:
        assert c.patch(f"/api/planches/{seeded['planche']}/statut",
                       json={"statut": "annotee"}).status_code == 200
    finally:
        c.close()

    page.set_extra_http_headers(ADMIN)
    page.goto(seeded["base"] + f"/?album={seeded['album']}&planche={seeded['planche']}",
              wait_until="networkidle")
    page.wait_for_timeout(500)
    assert "annotee" in page.locator("#planche-info").inner_text()

    page.click("#btn-traitement")            # « Segmenter » vit dans un menu déroulant
    page.wait_for_selector("#btn-segmenter", state="visible", timeout=3000)
    page.click("#btn-segmenter")
    # Kumiko tourne en sous-processus : on attend la fin, pas une durée. La FIN, c'est le
    # toast de succès ou d'erreur. `.toast` seul prenait « Segmentation en cours… », posé
    # AVANT l'appel, et le test ne tenait que par la vitesse du moteur, dans les 1,5 s
    # d'attente qui suivaient. Seul, il passait ; le 2026-09-16, dans l'ordre de son module,
    # la segmentation n'était pas finie et la dernière assertion tombait.
    page.wait_for_selector(".toast.success, .toast.error", timeout=120000)
    erreurs = page.locator(".toast.error").all_inner_texts()
    assert not erreurs, f"la segmentation a échoué à l'écran : {erreurs}"
    page.wait_for_timeout(1500)

    # RE-SÉLECTION, et c'est tout le test. `segmenter()` ne redessine pas le bandeau —
    # écrire une constante dans `state.planche.statut` n'a donc aucun effet IMMÉDIAT, et
    # une assertion posée ici passerait quoi qu'il arrive. Mais `selectPlanche()` lit
    # `state.planches` EN MÉMOIRE, sans refetch, et `state.planche` en est le même objet :
    # la valeur faussée ressort au premier réaffichage. Sans ce clic, le test est vacant —
    # vérifié par mutation le 2026-08-31, il passait avec la constante en dur.
    page.click("#planche-list li")
    page.wait_for_timeout(800)

    info = page.locator("#planche-info").inner_text()
    assert "annotee" in info, f"l'écran a fait régresser le statut : {info!r}"
    assert "segmentee" not in info, f"l'écran affiche la régression refusée par la base : {info!r}"

    # Et la base est d'accord — sans quoi le test ne dirait rien de l'écran, seulement
    # que rien ne s'est passé.
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=ECRITURE)
    try:
        pl = [p for p in c.get(f"/api/albums/{seeded['album']}/planches").json()
              if p["id"] == seeded["planche"]][0]
    finally:
        c.close()
    assert pl["statut"] == "annotee"
    assert pl["date_segmentation"], "la segmentation n'a pas eu lieu : le test ne prouve rien"


# --------------------------------------------------------------------------- #
# AUTH-6 — le panneau des ACCÈS, et il n'était jamais audité AVEC du contenu
#
# (Il vit dans la Bibliothèque, sous « Qui entre », depuis l'étape 3 d'AUTH-12.)
# `test_a11y_chargement` visite bien la page, mais la liste des accès vit dans un
# `<details>` que rien n'ouvre : elle ne se charge qu'au dépliage. Aucun des éléments de ce
# panneau — ni le marqueur « n'a pas encore ouvert l'application » (AUTH-6), ni les
# libellés de genre — n'était donc passé devant axe. C'est le même piège que le décor des
# moteurs quarante lignes plus haut : un audit qui n'a rien sous les yeux approuve une
# palette qu'il n'a pas regardée.
#
# Décor DERRIÈRE LE PROXY, et c'est ce qui coûte le serveur en plus : sans identité, créer
# une collection est refusé (403), donc `collection_acces` reste vide et le panneau se
# rendrait sans une seule ligne. Le décor d'`a11y` ordinaire ne peut pas servir ici.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_a11y_qui_entre_signaux_et_cartes(page, live_server, theme):
    """« Qui entre » déplié, avec ses deux marques, en tableau puis en cartes, dans les deux thèmes.

    Le contraste est l'enjeu : le marqueur d'AUTH-6 (« n'a pas encore ouvert l'application »)
    est du PETIT texte en `--text-muted` italique, et « inconnu de l'annuaire » du petit texte
    ambre. `arrivant` est dans la doublure de l'annuaire et n'est jamais venu ; `bd-etudiants`
    n'y est pas. Les cartes, sous 48em, ont leur propre mise en page : un audit du seul
    tableau ne les verrait jamais.
    """
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                     headers={"Remote-User": "decor", "Remote-Groups": "bd-admins",
                              **{k: v for k, v in ECRITURE.items()
                                 if k not in ("Remote-User", "Remote-Groups")}})
    try:
        cid = c.post("/api/collections", json={"nom": "Corpus a11y"}).json()["id"]
        du_projet(c, cid, "utilisateur", "arrivant", headers=ECRITURE)
        c.put(f"/api/collections/{cid}/acces",
              json={"genre": "utilisateur", "principal": "arrivant", "niveau": "lecture"})
        du_projet(c, cid, "groupe", "bd-etudiants", headers=ECRITURE)
        c.put(f"/api/collections/{cid}/acces",
              json={"genre": "groupe", "principal": "bd-etudiants", "niveau": "ecriture"})
    finally:
        c.close()

    _theme(page, theme)
    page.set_extra_http_headers({"Remote-User": "decor", "Remote-Groups": "bd-admins"})
    page.set_viewport_size({"width": 1280, "height": 2400})
    page.goto(live_server + f"/corpus?collection={cid}", wait_until="networkidle")
    # On attend les MARQUES et non le bloc : c'est elles qu'on vient auditer.
    page.wait_for_selector(".acces-jamais-vu", timeout=5000)
    page.wait_for_selector(".qe-marque", timeout=5000)
    viol = _audit(page)
    assert not viol, f"Qui entre, tableau [{theme}] :\n{_fmt(viol)}"

    page.set_viewport_size({"width": 375, "height": 2400})
    page.wait_for_selector(".qe-carte .acces-jamais-vu", timeout=5000)
    viol = _audit(page)
    assert not viol, f"Qui entre, cartes [{theme}] :\n{_fmt(viol)}"


