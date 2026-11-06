/* Les CHAMPS À PROPOSITIONS de personnage — la logique pure, sans DOM. Nés dans le panneau
   d'annotation de l'Atelier ; depuis le basculement d'ANN-7, seul le champ « personnage » de
   la page Annotation (`champ-personnage.js`) lit ce module : sa liste, ses homonymes.
   Chargé en <script> par la page Annotation → expose `window.BDPropositions` ; aussi require()-able
   par `tests/js/propositions.test.js`, qui la vérifie par tables de cas. Rien n'est lu au
   chargement : ni le document, ni le stockage, ni l'adresse.

   POURQUOI UN MODULE (ANN-8, recommandé par l'auteur du correctif du 2026-10-13). La règle
   d'Entrée vivait dans `viewer.js`, mêlée à l'horloge de la lecture différée : chaque
   variante coûtait un test navigateur de cinq à dix secondes. Ce qui DÉCIDE n'a pourtant
   besoin que de ce qui est tapé, de la proposition surlignée et de la liste : une table de
   vérité sous Node la couvre en millisecondes.
   L'écran garde ce qui dépend du temps — quand la liste se lit, à qui le geste revient — ;
   les e2e de `test_e2e_annotation_propositions.py` (le champ « personnage », joué sur la page
   Annotation depuis le basculement) mesurent la requête partie.

   Les règles qui y vivent :
   - `entreePersonnage` et `decisionNom` : ce qu'Entrée fait dans un champ de personnage
     (le locuteur, la boîte personnage) — la proposition surlignée ne part que si elle répond
     encore à la saisie, et des homonymes se départagent à l'écran (ANN-8, Hugo, 2026-10-21) ;
   - `fleche` : où la flèche mène dans une liste, ouverte OU fermée — la première ↓ après
     une validation surligne une proposition (ANN-8 : elle rouvrait la liste sans rien
     surligner, quand le DOM de la liste précédente était vide) ;
   - `sansAccents` : jumelle de `socle._sans_accents`, le filtre du registre des
     personnages — leur accord se mesure sur `tests/cas-sans-accents.json`. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDPropositions = api;                                             // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Le nombre de propositions qu'une liste montre au plus. */
  const MAX_PROPOSITIONS = 10;

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

  /* Minuscules sans diacritiques — jumelle de `socle._sans_accents`, par laquelle le serveur
     filtre le registre des personnages (`GET /api/personnages?q=`) : « etienne » trouve
     « Étienne ». Décomposition compatible (NFKD), marques combinantes retirées, puis
     minuscules, dans l'ordre du serveur. */
  function sansAccents(s) {
    return String(s ?? "").normalize("NFKD").replace(/\p{Mn}/gu, "").toLowerCase();
  }

  /* La proposition `it` d'un champ de personnage RÉPOND-elle à la saisie `q` ? Celle d'un
     personnage, si son nom contient la saisie sans égard à la casse ni aux accents — ce
     que le serveur aurait rendu pour elle ; saisie vide, toutes. Celle de créer, si elle
     crée exactement ce qui est tapé : « Créer « Ze » » ne répond pas à « Zed ». */
  function repond(it, q) {
    if (!it) return false;
    const s = String(q ?? "").trim();
    if (it.create) return it.nom === s;
    return !s || sansAccents(it.nom).includes(sansAccents(s));
  }

  /* Les personnages qui portent le nom tapé, sans égard à la casse NI AUX ACCENTS — ceux
     que la série départage. ANN-8 (Hugo, 2026-10-21) : l'accent ne distingue pas deux
     personnages ; « etienne » tapé quand « Étienne » existe désigne Étienne, et Entrée
     proposait de créer un quasi-doublon. La comparaison est celle du filtre du serveur
     (`sansAccents`), et celle par laquelle `POST /api/personnages` retrouve un homonyme au
     lieu d'en créer un second. Saisie vide : aucun. */
  function homonymes(persos, q) {
    const s = sansAccents(String(q ?? "").trim());
    return s ? (persos || []).filter((p) => sansAccents(String(p.nom ?? "").trim()) === s) : [];
  }

  /* Ce qu'Entrée fait dans un champ de personnage, sur la liste À L'ÉCRAN. Rend l'un de :
     - { geste: "choisir", item } — la proposition surlignée, si elle répond encore à ce qui
                                    est tapé ;
     - { geste: "relire" }        — la surlignée ne répond plus : c'est une ligne de la liste
                                    d'une saisie d'AVANT, la nouvelle n'est pas revenue
                                    (ANN-8, Hugo, 2026-10-21). Rien n'est pris ; la liste se
                                    relit pour ce qui est tapé, et l'on choisit dedans ;
     - { geste: "valider" }       — rien de surligné, une saisie : le registre décide
                                    (`decisionNom`) ;
     - { geste: "rien" }          — rien de surligné, champ vide.
     La surlignée qui répond encore part, même d'une liste d'avant : elle est à l'écran, elle
     correspond à ce qui est tapé, et le geste est explicite — fermer la liste pendant la
     lecture rendait les flèches inertes. */
  function entreePersonnage({ q, actif = -1, items = [] }) {
    const s = String(q ?? "").trim();
    const it = actif >= 0 ? items[actif] : null;
    if (it) return repond(it, s) ? { geste: "choisir", item: it } : { geste: "relire" };
    return s ? { geste: "valider" } : { geste: "rien" };
  }

  /* Ce que décide le registre LU pour la saisie `q`, quand Entrée n'a rien de surligné :
     - un seul personnage porte ce nom (sans casse ni accents, `homonymes`) → { geste:
       "choisir", item } ;
     - plusieurs → { geste: "departager", homonymes } : Entrée ne décide pas — prendre le
       premier dans l'ordre du registre, c'était choisir à la place de la personne, sans le
       lui dire (ANN-8, Hugo, 2026-10-21). La liste se réduit aux homonymes, chacun avec sa
       série, et l'on choisit ;
     - aucun → { geste: "creer", nom }. */
  function decisionNom(persos, q) {
    const s = String(q ?? "").trim();
    const h = homonymes(persos, s);
    if (h.length === 1) return { geste: "choisir", item: h[0] };
    if (h.length > 1) return { geste: "departager", homonymes: h };
    return { geste: "creer", nom: s };
  }

  return { MAX_PROPOSITIONS, fleche, sansAccents, repond, homonymes, entreePersonnage,
           decisionNom };
});
