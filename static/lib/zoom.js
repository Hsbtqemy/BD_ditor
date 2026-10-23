/* Le zoom d'interface du menu « Aa », borné par la largeur de la fenêtre (UX-7) — logique
   PURE, sans DOM. Chargé en <script> dans le <head>, AVANT `theme.js`, qui l'applique avant
   le rendu → expose `window.BDZoom` ; aussi require()-able par `tests/js/zoom.test.js`.

   La règle (Hugo, 2026-10-23) : le zoom s'arrête TOUJOURS avant que la page casse.

   Le zoom d'interface multiplie tout ce qu'il touche, donc il DIVISE la largeur utile : à
   320 px, 200 % n'en laissait que 160, et aucune page n'y tenait. Le zoom APPLIQUÉ garde
   donc la largeur utile au-dessus d'un PLANCHER, et ne dépasse jamais 200 %.

   1. Le plancher de base est 320 px CSS, la base des règles de reflow (WCAG 1.4.10) : la
      plus petite largeur pour laquelle chaque page est faite. D'où, sur quatre surfaces :
      aucun zoom d'interface à 320 px, 117 % à 375, 200 % dès 640.

   2. L'ATELIER en demande plus au-dessus de ses seuils, et c'est mesuré, pas deviné. Les
      seuils de la feuille sont des `@media` en `em` de FENÊTRE, que le zoom ne change pas :
      une fenêtre de 640 px sous 200 % prend sa disposition de 640 px dans 320 px CSS. Au-
      dessus de 34.9375em la bande 2 cesse de s'enrouler, et au-dessus de 63.9375em elle
      affiche ses libellés : elle déborde alors de la fenêtre, menus « Traitement » et
      « Import / Export » hors d'atteinte (vu à 640 px sous 2 : 34 px CSS dehors). Les
      planchers de `PALIERS_ATELIER` sont la plus petite largeur utile où rien n'est perdu
      (la sonde de `tools/mesurer_reflow.py`), mesurée le 2026-10-23 par dichotomie sur le
      zoom, sous les préférences de police 16, 20 et 24, sur le poste (Segoe UI) ET dans
      l'image (DejaVu Sans, plus large) — c'est l'image qui borne, arrondie vers le haut :
        de 28em à 34.9375em    poste 17,9–18,9em   image 18,8–19,7em   → 20em
        de 34.9375em à 63.94em poste 20,9–21,6em   image 21,3–22,0em   → 22,5em
        au-delà de 63.9375em   poste 49,5em        image 52,3em        → 53em
      En `em` parce que tout y suit la préférence de police : seuils et contenu ensemble
      (les trois préférences rendent les mêmes valeurs à 2 % près). Les quatre autres
      surfaces tiennent leurs bandes à 200 % dès que la largeur utile atteint 320 px, à
      toutes les largeurs mesurées (540 à 1 920 px) : la règle de base leur suffit.

   3. Le zoom maximal NE BAISSE PAS quand la fenêtre s'élargit au passage d'un seuil de la
      disposition étroite : il plafonne un peu avant (un PALIER), à la valeur que le seuil
      admettra juste au-dessus. À 16 px : 155 % de 497 à 559 px, au lieu de 175 %. Au seuil
      des LIBELLÉS (63.9375em), un palier coûterait le zoom de toutes les fenêtres plus
      étroites — 121 % dès 387 px — : le SAUT y est assumé (`saut`), et c'est le seul. À
      16 px : 200 % à 1 023 px, 121 % à 1 024, 200 % de nouveau à 1 696. Ce qui le
      supprimerait est dans la feuille : des seuils qui lisent la largeur UTILE (requêtes de
      conteneur), et non la fenêtre.

   Le plafond ne descend pas sous 100 % : sous le plancher la fenêtre est déjà plus étroite
   que ce que la page demande, et RÉDUIRE d'office ce que la personne lit serait une autre
   décision, non prise. A− reste libre (jusqu'à 80 %).

   La PRÉFÉRENCE n'est pas le zoom appliqué. Une préférence de 200 % gardée en stockage
   s'applique à 100 % dans une fenêtre de 320 px et revient entière en élargissant la
   fenêtre : la borne lit la largeur, elle n'écrit rien. Le zoom du navigateur n'est pas
   concerné — c'est lui qui réduit la largeur CSS et fait basculer la page dans sa mise en
   page étroite. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDZoom = api;                                                     // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const MIN = 0.8;
  const MAX = 2.0;
  const PAS = 0.1;
  const LARGEUR_BASE = 320;           // px CSS : la largeur utile ne tombe jamais en dessous

  /* Au-dessus de `depuis` (em de fenêtre, exclu : `max-width` est inclusif), la largeur
     utile ne descend pas sous `plancher` (em). Les seuils sont ceux de `static/style.css`. */
  const PALIERS_ATELIER = Object.freeze([
    Object.freeze({ depuis: 28, plancher: 20 }),
    Object.freeze({ depuis: 34.9375, plancher: 22.5 }),
    Object.freeze({ depuis: 63.9375, plancher: 53, saut: true }),
  ]);

  /* La fenêtre : un nombre (sa largeur, police de 16 px, règle de base), ou
     `{ largeur, em, paliers }`. */
  function fenetre(f) {
    if (typeof f === "number" || f == null) return { largeur: f, em: 16, paliers: [] };
    return { largeur: f.largeur, em: f.em > 0 ? f.em : 16, paliers: f.paliers || [] };
  }

  /* La préférence stockée (une chaîne, ou rien) : hors de [MIN, MAX], 100 %. */
  function preference(brut) {
    const z = parseFloat(brut);
    return (z >= MIN && z <= MAX) ? z : 1;
  }

  /* La plus petite largeur utile (px CSS) que demande une fenêtre de `largeur` px. */
  function plancher(f) {
    const w = fenetre(f);
    let p = LARGEUR_BASE;
    w.paliers.forEach((pal) => {
      if (w.largeur > pal.depuis * w.em) p = Math.max(LARGEUR_BASE, pal.plancher * w.em);
    });
    return p;
  }

  /* Le plus fort zoom qu'une fenêtre admet. Une largeur illisible (0, absente) ne borne
     rien : on ne réduit pas ce qu'on ne sait pas mesurer. */
  function plafond(f) {
    const w = fenetre(f);
    if (!(w.largeur > 0)) return MAX;
    let z = w.largeur / plancher(w);
    // Les paliers : chaque seuil à venir, jusqu'au premier SAUT exclu, borne déjà ce qu'on
    // admet en dessous de lui à ce qu'il admettra juste au-dessus.
    for (const pal of w.paliers) {
      const seuil = pal.depuis * w.em;
      if (seuil < w.largeur) continue;
      if (pal.saut) break;
      z = Math.min(z, seuil / Math.max(LARGEUR_BASE, pal.plancher * w.em));
    }
    return Math.min(MAX, Math.max(1, z));
  }

  /* Ce qui s'applique : la préférence, sans dépasser le plafond de la fenêtre. */
  function applique(pref, f) {
    return Math.min(pref, plafond(f));
  }

  /* A+ s'éteint quand le zoom appliqué a atteint le plafond. */
  function auMaximum(pref, f) {
    return applique(pref, f) >= plafond(f) - 1e-9;
  }

  /* Pourquoi A+ est éteint — `null` s'il ne l'est pas. La largeur d'abord : 200 % n'est
     le plafond que d'une fenêtre assez large pour lui. */
  function raisonMaximum(pref, f) {
    if (!auMaximum(pref, f)) return null;
    if (plafond(f) < MAX) {
      return "Zoom maximal pour cette largeur de fenêtre. "
        + "Le zoom du navigateur, lui, réagence la page.";
    }
    return "Zoom maximal (200 %)";
  }

  /* La préférence après un cran de A+ (sens 1) ou de A− (sens −1). Le cran part du zoom
     APPLIQUÉ : sous une préférence bornée, A− doit réduire ce qu'on voit, pas une valeur
     que la fenêtre cache. Arrondi au dixième, borné à [MIN, MAX], comme avant la borne. */
  function cran(pref, f, sens) {
    const z = Math.round((applique(pref, f) + sens * PAS) * 10) / 10;
    return Math.min(MAX, Math.max(MIN, z));
  }

  return { MIN, MAX, PAS, LARGEUR_BASE, PALIERS_ATELIER, preference, plancher, plafond,
           applique, auMaximum, raisonMaximum, cran };
});
