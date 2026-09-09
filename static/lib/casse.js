/* Normalisation de casse d'une transcription (NLP-3) — logique PURE, sans DOM.
   Chargé en <script> AVANT viewer.js → expose `window.BDCasse` ; aussi require()-able
   par `tests/js/casse.test.js`.

   JUMEAU DE `casse.py`, ET C'EST DÉLIBÉRÉ. Une seule implémentation aurait supposé une
   route pour un pur calcul de chaîne : elle n'aurait touché aucune donnée, il aurait
   fallu la déclarer HORS_PERIMETRE dans le cliquet d'autorisation, et le bouton aurait
   payé un aller-retour réseau par clic. Deux implémentations coûtent moins — à condition
   que leur accord soit MESURÉ et non supposé, et il l'est : `tests/cas-casse.json` est
   la table de cas, lue par les DEUX suites. Une divergence rend l'une des deux rouge.

   Les cinq règles et leurs raisons sont écrites une seule fois, dans `casse.py` — ici
   ne vivent que les écarts de langage. Il y en a deux, et les deux viennent du même
   défaut de JavaScript : son `\w` est resté ASCII. D'où `\p{L}` (avec le drapeau `u`)
   là où Python écrit `[^\W\d_]`, et un test de chiffre borné à `0-9` des deux côtés
   plutôt que `isdigit()` contre `\p{Nd}`, qui ne s'accordent pas sur les exposants. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDCasse = api;                                                    // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const SIGLE = /(?<!\p{L})(?:\p{L}\.){2,}/gu;
  const FINALES = ".!?";
  const LETTRE = /\p{L}/u;

  const estLettre = (c) => LETTRE.test(c);
  const estChiffre = (c) => c >= "0" && c <= "9";

  /* Au moins une lettre, toutes en capitales (règle `only_upper`). Un texte sans lettre
     répond false : il n'y a rien à normaliser, et le dire évite d'offrir un geste inerte. */
  function estToutCapitales(texte) {
    const t = texte || "";
    return [...t].some(estLettre) && t === t.toUpperCase();
  }

  /* Proposition de casse normalisée ; texte INCHANGÉ s'il n'est pas tout en capitales. */
  function normaliser(texte) {
    const t = texte || "";
    if (!estToutCapitales(t)) return t;

    const sigles = new Map();
    SIGLE.lastIndex = 0;                       // le drapeau `g` garde un curseur d'état
    for (let m; (m = SIGLE.exec(t)) !== null; ) sigles.set(m.index, m.index + m[0].length);

    const sortie = [];
    const n = t.length;
    let i = 0, majuscule = true;               // début de texte
    while (i < n) {
      if (sigles.has(i)) {                     // recopié tel quel ; ses points ne closent rien
        const fin = sigles.get(i);
        sortie.push(t.slice(i, fin));
        majuscule = false;
        i = fin;
        continue;
      }
      const c = t[i];
      if (FINALES.includes(c)) {
        let j = i;
        while (j < n && t[j] === c) j++;
        majuscule = !(c === "." && j - i >= 2);  // une suite de points est une suspension
        sortie.push(t.slice(i, j));
        i = j;
        continue;
      }
      if (c === "…") {                    // même raison, en un seul signe
        sortie.push(c);
        i++;
        continue;
      }
      if (estLettre(c) || estChiffre(c)) {
        // La source étant tout en capitales, la forme majuscule EST le caractère lu.
        sortie.push(majuscule ? c : c.toLowerCase());
        majuscule = false;
        i++;
        continue;
      }
      sortie.push(c);                          // ponctuation, espaces, guillemets… : neutres
      i++;
    }
    return sortie.join("");
  }

  return { estToutCapitales, normaliser };
});
