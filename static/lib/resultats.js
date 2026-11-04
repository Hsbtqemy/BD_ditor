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

  /* UX-6 — un nombre et son nom, ACCORDÉS : « 0 album », « 1 album », « 2 albums ». La règle
     française met 0 et 1 au singulier, comme `etat` ci-dessus. `pluriel` par défaut : le
     singulier suivi d'un « s ». `accord` rend le mot seul, pour qui écrit le nombre à part
     (en gras, dans un lien) ; `nombre` le nombre et le mot. */
  function accord(n, singulier, pluriel) {
    return (Number(n) || 0) > 1 ? (pluriel || singulier + "s") : singulier;
  }
  function nombre(n, singulier, pluriel) {
    return (Number(n) || 0) + " " + accord(n, singulier, pluriel);
  }

  /* Les chiffres du corpus (`GET /api/corpus`), tels que la Recherche, l'Exploration et la
     Bibliothèque les montrent : chacun accordé à son nombre. Ils s'écrivaient en trois copies
     au pluriel fixe — « 1 albums », « 1 planches » dans un bac à sable tout neuf. Un nombre
     absent de la réponse se lit 0, jamais « undefined ». */
  const CHIFFRES_CORPUS = [
    ["albums", "album"], ["planches", "planche"], ["regions", "région"],
    ["transcrites", "transcrite"], ["annotees", "annotée"], ["tags", "tag"],
  ];
  function chiffresCorpus(c) {
    return CHIFFRES_CORPUS.map(([cle, mot]) => {
      const n = Number(c && c[cle]) || 0;
      return `<span class="stat"><b>${n}</b> ${accord(n, mot)}</span>`;
    }).join("");
  }

  return { LIMITE: LIMITE, etat: etat, accord: accord, nombre: nombre,
           chiffresCorpus: chiffresCorpus };
});
