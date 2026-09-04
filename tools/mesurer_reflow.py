"""Mesure le débordement horizontal des quatre surfaces — outil de constat pour UX-7.

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

  # sur une instance déjà lancée (base jetable de préférence)
  python tools/mesurer_reflow.py [URL]        # défaut : http://127.0.0.1:8000
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
SURFACES = [("Visionneuse", "/"), ("Recherche", "/recherche"),
            ("Bibliothèque", "/corpus"), ("Exploration", "/exploration")]
# Deux largeurs ne suffisent pas : elles ne disent rien de la BANDE entre les deux, et
# c'est là qu'un correctif à seuil laisse un trou. Mesuré le 2026-09-04 — la bande 1
# réparée à 320 px laissait sortir le menu « Aa » de 55 px à 480 px, juste au-dessus du
# seuil de sa media query, et les deux largeurs canoniques n'en disaient rien. C'est ce
# constat qui a déplacé le seuil de 400 à 560 px.
LARGEURS = [(320, "téléphone"), (400, "petit téléphone"), (480, "téléphone paysage"),
            (560, "seuil de la bande 1"), (768, "tablette")]

SONDE = """() => {
  const r = document.documentElement;
  const large = r.clientWidth;
  const coupables = [];
  for (const el of document.querySelectorAll('body *')) {
    const b = el.getBoundingClientRect();
    if (b.width === 0 || b.height === 0) continue;
    if (b.right <= large + 1 && b.left >= -1) continue;
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
    coupables.push({
      cadre,
      tag: el.tagName.toLowerCase(),
      id: el.id || null,
      cls: (el.className && typeof el.className === 'string')
             ? el.className.split(/\\s+/).slice(0, 2).join('.') : null,
      largeur: Math.round(b.width),
      depasse: Math.round(b.right - large),
    });
  }
  return { scrollWidth: r.scrollWidth, clientWidth: large, coupables: coupables.slice(0, 6) };
}"""

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
            r = page.evaluate(SONDE)
            perdus = [c for c in r["coupables"] if not c["cadre"]]
            encadres = [c for c in r["coupables"] if c["cadre"]]
            etat = "OK" if not perdus else f"{len(perdus)} élément(s) COUPÉ(s)"
            print(f"  {nom:14} → {etat}")
            for c in perdus:
                ident = c["id"] and f"#{c['id']}" or (c["cls"] and f".{c['cls']}") or ""
                print(f"       ✗ <{c['tag']}>{ident}  largeur {c['largeur']} px,"
                      f" dépasse de {c['depasse']} — INATTEIGNABLE")
            for c in encadres:
                ident = c["id"] and f"#{c['id']}" or (c["cls"] and f".{c['cls']}") or ""
                print(f"       · <{c['tag']}>{ident}  largeur {c['largeur']} px,"
                      f" défile dans {c['cadre']} — conforme 1.4.10")
        ctx.close()
    nav.close()
print("\nfin de la mesure")
