"""Mesure le débordement horizontal des cinq surfaces — outil de constat pour UX-7.

Répond à une question que la suite ne pose pas : à une largeur donnée, du contenu
sort-il de l'écran, et lequel ? Le critère WCAG 2.1 AA **1.4.10 « Reflow »** demande un
contenu utilisable à 320 px sans défilement bidimensionnel, et **axe ne le teste pas** —
il n'est pas automatisable en général. Celui-ci l'est, à condition de mesurer la bonne
chose.

**Ne PAS se fier à `documentElement.scrollWidth`.** `static/style.css` pose
`html, body { overflow: hidden }` — nécessaire à la Visionneuse, qui est une coque pleine
hauteur. Le débordement est donc CLIPPÉ, et `scrollWidth` reste égal à `clientWidth`
pendant que 431 px de contenu sont hors champ. Une garde écrite sur `scrollWidth` passe
au vert sur une application dont un tiers de l'écran est inatteignable ; c'est
exactement ce qu'a montré la mesure du 2026-09-04.

On compare donc le RECTANGLE de chaque élément à la largeur de la fenêtre, et on remonte
le coupable le plus PROCHE de la racine : un parent qui déborde fait déborder tous ses
enfants, et lister les enfants noierait la cause dans ses conséquences.

**Et on distingue DÉFILABLE de COUPÉ**, sans quoi la mesure ne peut pas dire si un
correctif a marché. Le 1.4.10 TOLÈRE explicitement qu'un contenu à deux dimensions — un
tableau — défile dans son propre cadre ; ce qu'il interdit, c'est que la PAGE défile en
deux dimensions, ou que le contenu soit inatteignable. Un tableau de 693 px dans un cadre
de 280 px qui défile est conforme ; le même tableau sans cadre, sous `overflow: hidden`,
perd 413 px. Les deux se ressemblent exactement si l'on ne regarde que le rectangle, et
c'est ce que faisait cet outil jusqu'au 2026-09-04.

**Cet outil mesure l'état AU REPOS, et c'est sa limite** : il charge les cinq surfaces
sans paramètres, donc sans planche ouverte, sans résultat de recherche, sans toast et sans
token relu. Ce que la page ne rend pas, il ne le voit pas — quatre défauts ont vécu là
(la vignette de résultat, `.accord-table`, le toast, et `#canvas` qui fait 800 px dès
qu'une planche est chargée). La GARDE est `tests/test_e2e_reflow.py`, qui monte un décor
et vise des URL peuplées ; celui-ci reste l'instrument d'exploration, celui qu'on lance à
la main pour balayer sept largeurs et LIRE ce qui sort. Les deux partagent `SONDE`.

Le repos a cessé d'être le SEUL état mesuré avec UX-14 : chaque surface est aussi mesurée
une fois par panneau déclaré dans `DEPLIES`, ouvert. Un cinquième défaut vivait là — le
menu « Affichage », déclaré sain par UX-7 parce qu'il était replié pendant la mesure.
L'outil et le test partagent cette liste comme ils partagent `SONDE`.

  # sur une instance déjà lancée (base jetable de préférence)
  python tools/mesurer_reflow.py [URL]        # défaut : http://127.0.0.1:8000
"""
import sys

# Rien au niveau MODULE : `tests/test_e2e_reflow.py` importe `SONDE` d'ici, et recopier la
# sonde ferait exactement la faute qu'elle répare — deux versions d'une même règle, dont
# une seule serait corrigée le jour où l'on apprend quelque chose. Lire `sys.argv` ou
# reconfigurer `stdout` à l'import agirait donc sur une course de pytest.
# UX-10 a ajouté `/administration` le 2026-09-07, et cette liste ne l'a pas suivi : elle
# a exploré QUATRE surfaces sur cinq jusqu'au 2026-09-07. `test_e2e_reflow.py` l'avait,
# lui — d'où le piège, une liste juste à côté d'une liste périmée, sans que rien ne les
# confronte. Le nom de la première suit la barre de navigation (« Atelier » depuis
# `1cc3a41`) et non le vocabulaire du code, parce que ce nom-là s'imprime dans un rapport
# qu'on lit à côté de l'écran.
SURFACES = [("Atelier", "/"), ("Recherche", "/recherche"),
            ("Bibliothèque", "/corpus"), ("Exploration", "/exploration"),
            ("Administration", "/administration")]
# Deux largeurs ne suffisent pas : elles ne disent rien de la BANDE entre les deux, et
# c'est là qu'un correctif à seuil laisse un trou. Mesuré le 2026-09-04 — la bande 1
# réparée à 320 px laissait sortir le menu « Aa » de 55 px à 480 px, juste au-dessus du
# seuil de sa media query, et les deux largeurs canoniques n'en disaient rien. C'est ce
# constat qui a déplacé le seuil de 400 à 560 px.
LARGEURS = [(320, "téléphone"), (400, "petit téléphone"), (480, "téléphone paysage"),
            (560, "seuil de la bande 1"), (600, "entre les deux seuils"),
            (660, "seuil de la bande 4"), (768, "tablette")]

SONDE = """() => {
  const r = document.documentElement;
  const large = r.clientWidth;
  const coupables = [];
  for (const el of document.querySelectorAll('body *')) {
    const b = el.getBoundingClientRect();
    if (b.width === 0 || b.height === 0) continue;
    if (b.right <= large + 1 && b.left >= -1) continue;
    // ENTIÈREMENT hors champ ET commandé par un contrôle : c'est un panneau
    // ESCAMOTÉ — un tiroir fermé —, pas du contenu perdu. Un contenu clippé, lui,
    // est à sa place naturelle et ne fait que dépasser le bord : son rectangle
    // CHEVAUCHE la fenêtre.
    //
    // L'exemption exige les DEUX conditions, et la seconde est la vraie. Écrite sur
    // la seule position, elle excusait n'importe quoi qui se trouve au-delà du bord,
    // y compris un panneau qu'aucun geste ne ramène — c'est-à-dire exactement la
    // violation qu'on cherche. `aria-controls` est la preuve du chemin de retour, et
    // c'est ce que le 1.4.10 mesure : non pas où est le contenu, mais s'il est
    // ATTEIGNABLE. Un tiroir sans bascule reste donc signalé, et il le mérite.
    if ((b.right <= 0 || b.left >= large) && el.id &&
        document.querySelector('[aria-controls~="' + el.id + '"]')) continue;
    // on ne garde que le plus proche de la racine
    let parentDeborde = false;
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const pb = p.getBoundingClientRect();
      if (pb.right > large + 1 || pb.left < -1) { parentDeborde = true; break; }
    }
    if (parentDeborde) continue;
    // Un ancêtre qui DÉFILE horizontalement et tient dans l'écran rend le débordement
    // atteignable : c'est un cadre, pas une perte. On le nomme au lieu de le taire —
    // l'outil doit rester capable de dire « il y a un cadre là, est-ce le bon endroit ? ».
    let cadre = null;
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const st = getComputedStyle(p);
      if (!/(auto|scroll)/.test(st.overflowX)) continue;
      if (p.scrollWidth <= p.clientWidth + 1) continue;      // déclaré, mais ne défile pas
      const pb = p.getBoundingClientRect();
      if (pb.right <= large + 1 && pb.left >= -1) {
        cadre = (p.id ? '#' + p.id : '') ||
                (typeof p.className === 'string' && p.className
                   ? '.' + p.className.split(/\\s+/)[0] : p.tagName.toLowerCase());
        break;
      }
    }
    // Le CÔTÉ par lequel il sort, et pas seulement de combien (UX-14). `depasse` valait
    // `right - large`, si bien qu'un panneau qui pendait hors du bord GAUCHE se rapportait
    // en nombre NÉGATIF — « dépasse de -69 px » —, ce qui se lit comme « tient ». Les deux
    // sens ne relèvent pas du même correctif : à droite, quelque chose est trop large ; à
    // gauche, un ancrage `right: 0` a suivi un contrôle que l'enroulement a déplacé.
    // Les seuils sont ceux du filtre ci-dessus, et non les valeurs arrondies : un bord à
    // -1,3 px s'arrondit à 1, et le côté se serait nommé « à droite ».
    const aGauche = b.left < -1, aDroite = b.right > large + 1;
    coupables.push({
      cadre,
      tag: el.tagName.toLowerCase(),
      id: el.id || null,
      cls: (el.className && typeof el.className === 'string')
             ? el.className.split(/\\s+/).slice(0, 2).join('.') : null,
      largeur: Math.round(b.width),
      depasse: Math.max(Math.round(-b.left), Math.round(b.right - large)),
      sens: aGauche && aDroite ? 'des deux côtés' : (aGauche ? 'à gauche' : 'à droite'),
    });
  }
  return { scrollWidth: r.scrollWidth, clientWidth: large, coupables: coupables.slice(0, 6) };
}"""

# ── Ce qui doit être OUVERT pendant la mesure (UX-14) ───────────────────────────────────
#
# La sonde lit des rectangles, et un élément `hidden` n'en a pas : ce qui est replié
# n'existe pas pour elle. Le menu « Affichage » a vécu là. UX-7 l'avait mesuré et déclaré
# sain — au REPOS, donc panneau fermé —, et il sortait de 115 px par la gauche dès qu'on
# l'ouvrait à 375 px avec le lien « ← Retour ». Trouvé à l'œil sur une capture d'écran, le
# 2026-09-13, pour la troisième fois de ce dépôt dans les mêmes circonstances.
#
# D'où une liste DÉCLARÉE, sur le modèle d'`EXEMPTIONS` dans `tests/test_e2e_reflow.py`,
# et PARTAGÉE avec lui pour la raison qui vaut déjà pour `SONDE` : ce qui s'ouvre doit
# s'ouvrir des deux côtés, ou d'aucun. Le test ajoute ce qu'une liste seule ne ferait pas —
# il inventorie les contrôles `aria-expanded` de chaque page et échoue sur celui qui n'y
# figure pas. Sans cet inventaire, un menu ajouté demain serait replié pour l'instrument
# exactement comme celui-ci l'a été, et rien ne le dirait.
#
# Clé : le sélecteur du CONTRÔLE, que l'inventaire compare aux éléments de la page.
#   panneau  — ce qui doit avoir un rectangle une fois ouvert : la preuve que la mesure a
#              un objet. Le menu « Aa » ne porte pas d'`aria-controls`, d'où la déclaration.
#   surfaces — les chemins où il existe. Un contrôle déclaré et ABSENT échoue lui aussi :
#              une déclaration périmée est une mesure qui ne se fait plus.
DEPLIES = {
    # `theme.js` l'injecte partout : le corriger une fois le corrige partout, et le mesurer
    # sur une seule surface laisserait les quatre autres à la merci de leur propre bande 1.
    ".display-menu > button": {
        "nom": "menu Affichage",
        "panneau": ".display-panel",
        "surfaces": ["/", "/recherche", "/corpus", "/exploration", "/administration"],
    },
    # Les deux menus de la bande 2 de l'Atelier, et ses deux tiroirs (UX-7). Les tiroirs
    # étaient déjà ESCAMOTÉS pour la sonde — hors champ et commandés, donc conformes —, ce
    # qui dit qu'ils sont atteignables et rien de ce qu'on trouve une fois arrivé dedans.
    "#btn-traitement": {
        "nom": "menu Traitement", "panneau": "#traitement-menu", "surfaces": ["/"]},
    "#btn-donnees": {
        "nom": "menu Import / Export", "panneau": "#donnees-menu", "surfaces": ["/"]},
    "#btn-tiroir-nav": {
        "nom": "tiroir des planches", "panneau": "#sidebar", "surfaces": ["/"]},
    "#btn-tiroir-panneau": {
        "nom": "tiroir d'annotation", "panneau": "#panel", "surfaces": ["/"]},
}

# Les contrôles repliables présents dans la page, pour l'inventaire. `aria-expanded` est
# le contrat ARIA d'un bouton qui déplie quelque chose : c'est donc lui qu'on compte, et ce
# qu'il ne couvre pas est écrit — un `<details>` natif n'en porte pas, ni une boîte de
# dialogue ouverte par un bouton ordinaire. Ceux-là restent hors de l'inventaire.
INVENTAIRE = """(cles) => [...document.querySelectorAll('[aria-expanded]')].map((el) => ({
  declare: cles.find((c) => el.matches(c)) || null,
  ident: el.id ? '#' + el.id : el.tagName.toLowerCase() + '.' + el.className,
}))"""

# Un contrôle DÉJÀ ouvert n'est pas recliqué : ce serait le refermer, et l'attente qui suit
# échouerait en accusant le panneau.
_OUVRIR = """(sel) => {
  const c = document.querySelector(sel);
  if (!c) return false;
  if (c.getAttribute('aria-expanded') !== 'true') c.click();
  return true;
}"""

# Ouvert, et FINI de s'ouvrir : les tiroirs glissent (`transform` en transition), et un
# rectangle pris en plein vol se lirait comme un contenu à moitié hors champ. On n'attend
# que les animations du PANNEAU — lui, ses ancêtres, ses descendants —, pas celles du
# document : un indicateur de chargement qui tourne en boucle bloquerait sinon toute
# ouverture, et accuserait le panneau d'un délai qui n'est pas le sien.
_OUVERT = """(d) => {
  const c = document.querySelector(d.controle), p = document.querySelector(d.panneau);
  if (!c || !p || c.getAttribute('aria-expanded') !== 'true') return false;
  const b = p.getBoundingClientRect();
  const siennes = document.getAnimations().filter((a) => {
    const t = a.effect && a.effect.target;
    return t && (t.contains(p) || p.contains(t));
  });
  return b.width > 0 && b.height > 0 && siennes.every((a) => a.playState !== 'running');
}"""


def deplier(page, controle):
    """Ouvre le contrôle déclaré et attend que son panneau ait un rectangle.

    Le clic est DOM (`element.click()`) et non celui de Playwright, et c'est mesuré :
    Playwright fait défiler l'élément dans la vue avant de cliquer, y compris dans un corps
    en `overflow: hidden` — à 480 px derrière le proxy, il a décalé `body` de 19 px, et la
    mesure prise ensuite portait sur une page qu'aucun utilisateur ne peut obtenir. Un
    contrôle hors champ reste l'affaire de la mesure au repos, qui le verra.

    Lève si rien ne s'ouvre : un panneau qui reste replié donnerait une mesure verte sans
    objet, c'est-à-dire le défaut même que la liste existe pour fermer.
    """
    d = DEPLIES[controle]
    if not page.evaluate(_OUVRIR, controle):
        raise AssertionError(f"{d['nom']} : contrôle `{controle}` absent de la page")
    try:
        page.wait_for_function(_OUVERT, arg={"controle": controle, "panneau": d["panneau"]},
                               timeout=3000)
    except Exception as e:
        raise AssertionError(
            f"{d['nom']} : `{controle}` cliqué, mais `{d['panneau']}` n'a pas de rectangle "
            "ou le contrôle ne se dit pas ouvert (`aria-expanded`) — la mesure n'aurait "
            "aucun objet") from e


def _rapporter(libelle, r):
    perdus = [c for c in r["coupables"] if not c["cadre"]]
    encadres = [c for c in r["coupables"] if c["cadre"]]
    etat = "OK" if not perdus else f"{len(perdus)} élément(s) COUPÉ(s)"
    print(f"  {libelle:38} → {etat}")
    for c in perdus:
        ident = c["id"] and f"#{c['id']}" or (c["cls"] and f".{c['cls']}") or ""
        print(f"       ✗ <{c['tag']}>{ident}  largeur {c['largeur']} px,"
              f" dépasse de {c['depasse']} {c['sens']} — INATTEIGNABLE")
    for c in encadres:
        ident = c["id"] and f"#{c['id']}" or (c["cls"] and f".{c['cls']}") or ""
        print(f"       · <{c['tag']}>{ident}  largeur {c['largeur']} px,"
              f" défile dans {c['cadre']} — conforme 1.4.10")


def main(base):
    from playwright.sync_api import sync_playwright
    BASE = base
    with sync_playwright() as pw:
        nav = pw.chromium.launch()
        for largeur, nom_l in LARGEURS:
            print(f"\n{'=' * 62}\n  {largeur} px ({nom_l})\n{'=' * 62}")
            ctx = nav.new_context(viewport={"width": largeur, "height": 900})
            page = ctx.new_page()
            for nom, chemin in SURFACES:
                try:
                    page.goto(BASE + chemin, wait_until="networkidle", timeout=30000)
                except Exception as e:
                    print(f"  {nom:14} — inatteignable ({type(e).__name__})")
                    continue
                _rapporter(nom, page.evaluate(SONDE))
                # Chaque panneau sur une page RECHARGÉE : les menus se ferment l'un
                # l'autre, et un état hérité du précédent fausserait la mesure du suivant.
                for controle, d in DEPLIES.items():
                    if chemin not in d["surfaces"]:
                        continue
                    page.goto(BASE + chemin, wait_until="networkidle", timeout=30000)
                    try:
                        deplier(page, controle)
                    except AssertionError as e:
                        print(f"  {nom + ', ' + d['nom']:38} — ne s'ouvre pas : {e}")
                        continue
                    _rapporter(f"{nom}, {d['nom']} ouvert", page.evaluate(SONDE))
            ctx.close()
        nav.close()
    print("\nfin de la mesure")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000")
