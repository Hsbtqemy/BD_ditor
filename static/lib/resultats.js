/* Ce que dit le compteur de résultats de la Recherche — la RÈGLE, pas le rendu.
   Chargé en <script> AVANT recherche.js → expose `window.Resultats` ; aussi
   require()-able par les tests Node (UMD minimal, pas de build).

   Ce module existe parce que la règle était FAUSSE et intestable (constat C1 de
   l'audit). Le seuil 200 était écrit deux fois — une fois dans la requête, une fois
   dans l'étiquette — sans que rien ne lie les deux, et l'application demandait
   exactement 200 résultats puis annonçait « (limité) » dès qu'elle en recevait 200.
   À exactement 200 correspondances dans le corpus, l'étiquette mentait : elle promettait
   qu'il en existait d'autres.

   La correction tient à un décalage d'un : on DEMANDE `LIMITE + 1` et on n'en AFFICHE
   que `LIMITE`. Le résultat surnuméraire ne se voit jamais ; il ne sert qu'à répondre
   « il y en a d'autres », ce qu'un décompte plafonné ne peut pas dire tout seul. C'est
   moins cher qu'un COUNT(*) séparé, qui compterait tout le corpus pour n'en afficher
   que la première page. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.Resultats = api;                                                  // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Un seul endroit, pour que la requête et l'étiquette ne puissent plus diverger. */
  const LIMITE = 200;

  /* `count` est le nombre de résultats RENVOYÉS par l'API (`len(results)`), jamais le
     total du corpus — c'est la confusion d'origine, et elle vaut d'être rappelée ici :
     le serveur ne sait pas combien il y en a, il sait seulement combien il en a donné. */
  function etat(count, limite) {
    const max = typeof limite === "number" ? limite : LIMITE;
    const n = Math.max(0, Math.min(count | 0, max));
    const tronque = (count | 0) > max;
    return {
      n: n,
      tronque: tronque,
      // « 0 résultat » et « 1 résultat » au singulier : la règle française.
      texte: n + " résultat" + (n > 1 ? "s" : "") + (tronque ? " (limité)" : ""),
    };
  }

  return { LIMITE: LIMITE, etat: etat };
});
