/* Les CHAMPS À PROPOSITIONS du panneau d'annotation de l'Atelier — la logique pure, sans DOM.
   Chargé en <script> par l'Atelier → expose `window.BDPropositions` ; aussi require()-able
   par `tests/js/propositions.test.js`, qui la vérifie par tables de cas. Rien n'est lu au
   chargement : ni le document, ni le stockage, ni l'adresse.

   POURQUOI UN MODULE (ANN-8, recommandé par l'auteur du correctif du 2026-10-13). La règle
   d'Entrée du champ « dimension : valeur » vivait dans `viewer.js`, mêlée à l'horloge de la
   lecture différée : chaque variante coûtait un test navigateur de cinq à dix secondes. Ce
   qui DÉCIDE n'a pourtant besoin que de ce qui est tapé, de la proposition surlignée, de la
   liste et du vocabulaire lu : une table de vérité sous Node la couvre en millisecondes.
   L'écran garde ce qui dépend du temps — quand la liste se lit, à qui le geste revient — ;
   les e2e de `test_e2e_atelier_propositions.py` restent, et mesurent la requête partie.

   Trois règles y vivent :
   - `decisionEntree` : ce qu'Entrée fait dans un champ « dimension : valeur » ;
   - `fleche` : où la flèche mène dans une liste, ouverte OU fermée — la première ↓ après
     une validation surligne une proposition (ANN-8 : elle rouvrait la liste sans rien
     surligner, quand le DOM de la liste précédente était vide) ;
   - `cleTag` : la clé d'un libellé de tag, jumelle de `database.cle_tag` — leur accord se
     mesure sur `tests/cas-tags.json`, lue des deux côtés. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDPropositions = api;                                             // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Le nombre de propositions qu'une liste montre au plus. */
  const MAX_PROPOSITIONS = 10;

  /* « dimension : valeur » → { dim, val } tels que tapés ; nul hors de la forme complète. */
  function formeComplete(q) {
    const s = String(q ?? "");
    const i = s.indexOf(":");
    if (i <= 0) return null;
    const dim = s.slice(0, i).trim(), val = s.slice(i + 1).trim();
    return dim && val ? { dim, val } : null;
  }

  /* La valeur du vocabulaire CONNU que cette forme désigne, sans égard à la casse. Elle se
     cherche dans tout le vocabulaire, pas dans la liste : celle-ci est filtrée sur le texte
     tapé, et « lieu:falaise », sans espaces, n'y retrouvait pas « lieu : falaise ». */
  function connue(vocab, f) {
    if (!f) return null;
    const d = f.dim.toLowerCase(), v = f.val.toLowerCase();
    return (vocab || []).find((x) => x.dimension.toLowerCase() === d
                                  && x.valeur.toLowerCase() === v) || null;
  }

  /* La liste pour la saisie `q`, sur le vocabulaire lu (`vocab` nul : aucune lecture n'a
     abouti, aucune proposition). Les valeurs dont le libellé « dimension : valeur » contient
     la saisie, dix au plus ; puis, si la saisie est une forme complète inconnue, la
     proposition de la créer. */
  function propositionsAttributs(vocab, q) {
    if (!vocab) return [];
    const s = String(q ?? "").trim(), bas = s.toLowerCase();
    const items = vocab
      .map((v) => ({ create: false, id: v.id, dim: v.dimension, val: v.valeur,
                     label: `${v.dimension} : ${v.valeur}` }))
      .filter((it) => !bas || it.label.toLowerCase().includes(bas))
      .slice(0, MAX_PROPOSITIONS);
    const f = formeComplete(s);
    if (f && !connue(vocab, f)) items.push({ create: true, dim: f.dim, val: f.val,
                                             label: `➕ ${f.dim} : ${f.val}` });
    return items;
  }

  /* Ce qu'Entrée fait dans un champ « dimension : valeur ». Rend l'un de :
     - { geste: "choisir", item }       — une proposition surlignée, ou la seule qui reste ;
     - { geste: "affecter", id }        — la forme complète d'une valeur connue ;
     - { geste: "creer", dim, val }     — la forme complète d'une valeur inconnue (trouvée-ou-
                                          créée côté serveur : sans vocabulaire lu, c'est ce
                                          chemin qui prend la valeur existante) ;
     - { geste: "rien" }                — champ vide : Entrée n'affecte rien ;
     - { geste: "dire" }                — champ rempli et rien à faire : l'écran le dit.
     `actif` : le rang surligné (-1 : aucun) ; `items` : la liste à l'écran ; `vocab` : le
     vocabulaire lu. La forme complète ne consulte pas la liste : elle aboutit en UNE Entrée,
     même avant toute lecture. */
  function decisionEntree({ q, actif = -1, items = [], vocab = null }) {
    if (actif >= 0 && items[actif]) return { geste: "choisir", item: items[actif] };
    const s = String(q ?? "").trim();
    if (!s) return { geste: "rien" };
    const f = formeComplete(s);
    if (f) {
      const v = connue(vocab, f);
      return v ? { geste: "affecter", id: v.id } : { geste: "creer", dim: f.dim, val: f.val };
    }
    if (s.indexOf(":") <= 0 && items.length === 1) return { geste: "choisir", item: items[0] };
    return { geste: "dire" };
  }

  /* Le rang que surligne une flèche, dans une liste de `n` propositions, depuis `actif`
     (-1 : aucun). ↓ va au suivant sans dépasser le dernier — depuis « aucun », au PREMIER ;
     ↑ au précédent sans remonter sous le premier. Une liste vide ne surligne rien. Le
     nombre est celui de la liste qui VA s'afficher, jamais celui du DOM de la précédente :
     c'est ce qui laissait la première ↓ après une validation sans rien surligner. */
  function fleche(actif, n, sens) {
    if (!(n > 0)) return -1;
    if (sens === "bas") return Math.min(n - 1, actif + 1);
    return Math.max(0, actif - 1);
  }

  /* La clé d'un libellé de tag : forme composée (NFC), apostrophes ramenées à la droite,
     minuscules, espaces compactés. Jumelle de `database.cle_tag` : « c’est pluriel » et
     « c'est pluriel » désignent le même tag. */
  const APOSTROPHES = /[’‘ʼ‛′]/g;
  function cleTag(label) {
    const s = String(label ?? "").normalize("NFC").replace(APOSTROPHES, "'");
    return s.toLowerCase().split(/\s+/).filter(Boolean).join(" ").normalize("NFC");
  }

  return { MAX_PROPOSITIONS, formeComplete, connue, propositionsAttributs, decisionEntree,
           fleche, cleTag };
});
