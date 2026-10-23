/* Le zoom d'interface du menu « Aa », borné par la largeur de la fenêtre (UX-7) — logique
   PURE, sans DOM. Chargé en <script> dans le <head>, AVANT `theme.js`, qui l'applique avant
   le rendu → expose `window.BDZoom` ; aussi require()-able par `tests/js/zoom.test.js`.

   La règle (Hugo, 2026-10-23) : le zoom APPLIQUÉ ne dépasse jamais largeur ÷ 320, ni 200 %.
   Le zoom d'interface multiplie tout ce qu'il touche, donc il DIVISE la largeur utile : à
   320 px, 200 % n'en laissait que 160, et aucune page n'y tenait. 320 px CSS est la base
   des règles de reflow (WCAG 1.4.10) : c'est la plus petite largeur pour laquelle chaque
   page est faite, et le zoom ne doit pas en fabriquer une plus petite. D'où : aucun zoom
   d'interface à 320 px, 117 % à 375, 200 % dès 640.

   Le plafond ne descend pas sous 100 % : sous 320 px la fenêtre est déjà plus étroite que
   la base, et RÉDUIRE d'office ce que la personne lit serait une autre décision, non prise.
   A− reste libre (jusqu'à 80 %) : ce que la personne choisit en dessous s'applique.

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

  /* La préférence stockée (une chaîne, ou rien) : hors de [MIN, MAX], 100 %. */
  function preference(brut) {
    const z = parseFloat(brut);
    return (z >= MIN && z <= MAX) ? z : 1;
  }

  /* Le plus fort zoom qu'une fenêtre de `largeur` px CSS admet. Une largeur illisible
     (0, absente) ne borne rien : on ne réduit pas ce qu'on ne sait pas mesurer. */
  function plafond(largeur) {
    if (!(largeur > 0)) return MAX;
    return Math.min(MAX, Math.max(1, largeur / LARGEUR_BASE));
  }

  /* Ce qui s'applique : la préférence, sans dépasser le plafond de la fenêtre. */
  function applique(pref, largeur) {
    return Math.min(pref, plafond(largeur));
  }

  /* A+ s'éteint quand le zoom appliqué a atteint le plafond. */
  function auMaximum(pref, largeur) {
    return applique(pref, largeur) >= plafond(largeur) - 1e-9;
  }

  /* Pourquoi A+ est éteint — `null` s'il ne l'est pas. La largeur d'abord : 200 % n'est
     le plafond que d'une fenêtre assez large pour lui. */
  function raisonMaximum(pref, largeur) {
    if (!auMaximum(pref, largeur)) return null;
    if (plafond(largeur) < MAX) {
      return "Zoom maximal pour cette largeur de fenêtre. "
        + "Le zoom du navigateur, lui, réagence la page.";
    }
    return "Zoom maximal (200 %)";
  }

  /* La préférence après un cran de A+ (sens 1) ou de A− (sens −1). Le cran part du zoom
     APPLIQUÉ : sous une préférence bornée, A− doit réduire ce qu'on voit, pas une valeur
     que la fenêtre cache. Arrondi au dixième, borné à [MIN, MAX], comme avant la borne. */
  function cran(pref, largeur, sens) {
    const z = Math.round((applique(pref, largeur) + sens * PAS) * 10) / 10;
    return Math.min(MAX, Math.max(MIN, z));
  }

  return { MIN, MAX, PAS, LARGEUR_BASE, preference, plafond, applique, auMaximum,
           raisonMaximum, cran };
});
