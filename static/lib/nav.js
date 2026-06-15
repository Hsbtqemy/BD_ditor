/* Helpers de navigation partagés par les trois surfaces (Visionneuse / Recherche /
   Exploration). Chargé en <script> AVANT le script de page → expose `window.Nav` ;
   aussi require()-able par les tests Node (UMD minimal, pas de build).
   Cf. docs/navigation-round-trip.md. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.Nav = api;                                                        // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* `retour` ne doit viser qu'une page INTERNE (chemin relatif) : on rejette les URL
     absolues, protocol-relative (//evil) et les schémas dangereux (javascript:/data:)
     → pas d'open-redirect ni d'XSS via le href du bouton « ← Retour ». Accepte un
     chemin commençant par « / » non suivi de « / » ni « \ ». */
  const safeRetour = (v) =>
    (typeof v === "string" && /^\/(?![/\\])/.test(v)) ? v : null;

  return { safeRetour };
});
