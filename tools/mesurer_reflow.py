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

  # sur une instance déjà lancée (base jetable de préférence)
  python tools/mesurer_reflow.py [URL]        # défaut : http://127.0.0.1:8000
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
SURFACES = [("Visionneuse", "/"), ("Recherche", "/recherche"),
            ("Bibliothèque", "/corpus"), ("Exploration", "/exploration")]
LARGEURS = [(320, "téléphone"), (768, "tablette")]

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
    coupables.push({
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
            deborde = r["scrollWidth"] - r["clientWidth"]
            etat = "OK" if deborde <= 1 else f"DÉBORDE de {deborde} px"
            print(f"  {nom:14} {r['scrollWidth']:>5} / {r['clientWidth']:<5} → {etat}")
            for c in r["coupables"]:
                ident = c["id"] and f"#{c['id']}" or (c["cls"] and f".{c['cls']}") or ""
                print(f"       · <{c['tag']}>{ident}  largeur {c['largeur']} px,"
                      f" dépasse de {c['depasse']}")
        ctx.close()
    nav.close()
print("\nfin de la mesure")
