/* Le PROJET COURANT (COL-3, tranche 1) — sa logique pure, sans DOM.
   Chargé en <script> sur les CINQ surfaces → expose `window.BDProjet` ; aussi require()-able
   par `tests/js/projet.test.js`, qui la vérifie par tables de cas. Rien n'est lu au
   chargement : ni le document, ni le stockage, ni l'adresse.

   CE QUE C'EST. Une collection appartient à un projet, et l'on peut en voir plusieurs. Le
   projet COURANT est celui dans lequel on travaille : il se lit dans la bande du haut de
   chaque page (`theme.js`), et dans cette tranche il borne la BIBLIOTHÈQUE seule — la liste
   des collections, et le projet où « créer une collection » crée. L'Atelier, la Recherche et
   l'Exploration affichent son nom et traversent encore les projets.

   OÙ IL VIT : dans le NAVIGATEUR (stockage local, clé `bd-projet`), jamais au serveur ni
   dans l'adresse. Le serveur ne s'en sert pour rien autoriser — il ne le connaît pas — ; ce
   que chaque route rend reste borné par la portée de qui demande. Deux conséquences, écrites
   plutôt que découvertes : un lien envoyé à quelqu'un ne porte pas le projet, et deux onglets
   du même navigateur partagent le même.

   LE STOCKAGE PEUT MANQUER — navigation privée, réglage du navigateur, cadre isolé — et son
   seul accès peut lever. Toute lecture et toute écriture passent donc par ici, sous
   try/catch : sans lui, le projet courant est le projet de repli, et choisir ne tient que le
   temps de la page.

   DEUX VALEURS RECOPIÉES DU SERVEUR, et leur accord est MESURÉ. Aucune route ne publie le
   plafond d'un nom ni la liste des rôles (`database.LONGUEUR_NOM_PROJET`,
   `autorisation.ROLES_PROJET`) ; l'écran en a besoin, pour borner le champ de saisie et pour
   proposer un rôle. `tests/test_projet_ecran.py` fait tomber la suite si l'une des deux
   s'écarte de la sienne. Le serveur reste seul à trancher : un nom trop long ou un rôle
   inconnu lui arrivent quand même, et c'est lui qui refuse, en le disant. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDProjet = api;                                                   // navigateur
})(typeof self !== "undefined" ? self : this, function (root) {
  "use strict";

  const CLE = "bd-projet";
  /* Prévient la page que le projet courant a changé : `detail.id`. Écouté par la bande du
     haut, qui tient son sélecteur d'accord, et par la Bibliothèque, qui redessine sa liste. */
  const EVENEMENT = "bd:projet-change";

  const LONGUEUR_NOM = 21;
  const ROLES = ["membre", "responsable"];

  /* Le projet courant, parmi ceux qu'on peut NOMMER (`GET /api/projets`) : celui qu'on avait
     retenu s'il est encore visible, sinon le projet de repli, sinon le premier. `null` sans
     aucun projet — un compte qui n'a ni projet ni collection n'en a pas, et rien n'est à
     afficher. Un identifiant retenu qui n'est plus visible n'est PAS oublié pour autant : on
     a pu être sorti d'un projet puis y revenir. */
  function courant(projets, retenu) {
    const liste = Array.isArray(projets) ? projets : [];
    if (!liste.length) return null;
    const garde = liste.find((p) => p.id === retenu);
    if (garde) return garde.id;
    return (liste.find((p) => p.repli) || liste[0]).id;
  }

  /* Le stockage local, ou `null` : l'ACCESSEUR lui-même peut lever. Lu à l'appel. */
  function stockage() {
    try { return root.localStorage || null; } catch (e) { return null; }
  }

  /* L'identifiant retenu, ou `null` : rien d'écrit, une valeur qui n'est pas un identifiant,
     ou un stockage qui refuse. */
  function lire(depuis) {
    const s = depuis === undefined ? stockage() : depuis;
    try {
      const v = s ? s.getItem(CLE) : null;
      return typeof v === "string" && /^[1-9]\d*$/.test(v) ? Number(v) : null;
    } catch (e) { return null; }
  }

  /* Retient un choix. Rend `false` quand il n'a pas pu être écrit : il vaut alors pour la
     page, pas pour la suivante. */
  function retenir(id, dans) {
    const s = dans === undefined ? stockage() : dans;
    try {
      if (!s) return false;
      s.setItem(CLE, String(id));
      return true;
    } catch (e) { return false; }
  }

  /* CHOISIR : retenir, puis prévenir. Le seul geste qui touche le document, et à l'appel.
     Passe par ici tout ce qui change de projet — le sélecteur de la bande, et l'adresse
     `/corpus?collection=…` quand elle nomme une collection d'un autre projet. */
  function choisir(id) {
    retenir(id);
    if (root.document && typeof root.CustomEvent === "function") {
      root.document.dispatchEvent(new root.CustomEvent(EVENEMENT, { detail: { id } }));
    }
  }

  /* Les collections d'UN projet, parmi celles qu'on lit. Sans projet courant — la liste des
     projets n'a pas pu être lue — on ne retient rien et on ne cache rien : la liste est
     rendue entière, plutôt que vidée par une panne qui ne la concerne pas. */
  function duProjet(collections, projetId) {
    const liste = Array.isArray(collections) ? collections : [];
    if (projetId === null || projetId === undefined) return liste;
    return liste.filter((c) => c.projet_id === projetId);
  }

  /* Le rôle, dans les mots de la maquette validée. Un rôle inconnu se lit tel quel plutôt
     que d'être maquillé en « membre ». */
  function libelleRole(role) {
    if (role === "responsable") return "responsable du projet";
    if (role === "membre") return "membre";
    return String(role);
  }

  return { CLE, EVENEMENT, LONGUEUR_NOM, ROLES, courant, lire, retenir, choisir, duProjet,
           libelleRole };
});
