/* Le PROJET COURANT (COL-3, tranche 1) — sa logique pure, sans DOM.
   Chargé en <script> sur les SIX surfaces → expose `window.BDProjet` ; aussi require()-able
   par `tests/js/projet.test.js`, qui la vérifie par tables de cas. Rien n'est lu au
   chargement : ni le document, ni le stockage, ni l'adresse.

   CE QUE C'EST. Une collection appartient à un projet, et l'on peut en voir plusieurs. Le
   projet COURANT est celui dans lequel on travaille : il se lit dans la bande du haut de
   chaque page (`theme.js`). Il borne la BIBLIOTHÈQUE — la liste des collections, le projet
   où « créer une collection » crée, les collections proposées à un album qu'on crée, et
   depuis la tranche 3 la liste des albums, donc le lot — et la liste des albums de
   l'ATELIER (`albumsDuProjet`). La Recherche et l'Exploration affichent son nom et
   traversent encore les projets. (Un album qu'on RANGE suit une autre règle : son projet à
   lui, pas le courant — `pourRanger`.)

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
     quand elle vise un objet d'un autre projet (`basculeVers`). */
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

  /* Les albums de TRAVAIL d'un projet, parmi ceux qu'on lit (`GET /api/albums`) : la liste
     de la Bibliothèque — donc du lot, qui part de sa sélection — et celle de l'Atelier
     (COL-3, tranche 3). Deux filtres, réunis ici pour que les deux écrans ne les écrivent
     pas chacun :
       · une copie GARDÉE AU FONDS (`au_fonds`) n'est jamais un album de travail, projet
         courant ou non : elle se règle dans l'Administration ;
       · les autres sont celles du projet, lu par le serveur (`projet_id`, le projet
         EFFECTIF — celui de ses collections quand la copie n'en porte pas d'écrit).
     Sans projet courant — aucun projet à nommer, ou une liste illisible — rien d'autre ne
     disparaît : la règle de `duProjet`. Un album sans projet hors du fonds ne devrait pas
     exister ; sous un projet, il n'en est pas, et ne s'y montre pas. */
  function albumsDuProjet(albums, projetId) {
    const deTravail = (Array.isArray(albums) ? albums : []).filter((a) => !a.au_fonds);
    if (projetId === null || projetId === undefined) return deTravail;
    return deTravail.filter((a) => a.projet_id === projetId);
  }

  /* LA BASCULE PAR L'ADRESSE. Une adresse qui vise un objet d'un AUTRE projet que le
     courant — `/corpus?collection=<id>`, `/?album=<id>…` — fait passer dans le sien, sans
     quoi la liste filtrée ne le contiendrait pas et l'écran dirait « introuvable » d'un
     objet ouvert. Rend le projet où basculer, ou `null` : rien de visé, le projet visé est
     déjà le courant, ou il n'est pas parmi ceux qu'on peut NOMMER — on ne bascule pas vers
     un projet que la bande ne saurait afficher. L'appelant fait le geste (`choisir`). */
  function basculeVers(projets, courantId, viseId) {
    if (viseId === null || viseId === undefined || viseId === courantId) return null;
    return (Array.isArray(projets) ? projets : []).some((p) => p.id === viseId) ? viseId : null;
  }

  /* Où un ALBUM peut se ranger, parmi les collections candidates : celles du projet où il
     VIT déjà. Ce projet se lit dans SES collections (`siennes`, celles qu'on lit de lui),
     jamais dans le projet courant — une fiche d'album peut s'ouvrir d'ailleurs que de la
     liste bornée au projet courant. Le serveur refuse un rangement qui
     traverse deux projets ; l'écran cesse de le proposer, et le serveur reste seul à trancher.

     Rend `{ projets, collections, ecartees }` : les projets où l'album vit, ce qu'on peut
     lui proposer, et combien de candidates on a écartées — pour que l'écran DISE ce qu'il ne
     montre pas. Trois cas :
       · un projet       → les candidates de ce projet ;
       · aucun           → rien n'est su de l'album, rien n'est écarté ;
       · plusieurs       → aucune candidate. L'état ne devrait pas exister (une base
                           retouchée à la main), et dans cet état TOUT rangement est refusé :
                           quelle que soit la collection d'arrivée, l'album vit déjà dans un
                           autre projet que le sien. C'est à l'écran de le dire, avec le geste
                           qui en sort — la liste vide n'explique rien. */
  function pourRanger(siennes, candidates) {
    const cibles = Array.isArray(candidates) ? candidates : [];
    const projets = [...new Set((Array.isArray(siennes) ? siennes : [])
      .map((c) => c.projet_id).filter((id) => id !== null && id !== undefined))];
    if (!projets.length) return { projets, collections: cibles, ecartees: 0 };
    const collections = projets.length === 1
      ? cibles.filter((c) => c.projet_id === projets[0]) : [];
    return { projets, collections, ecartees: cibles.length - collections.length };
  }

  /* Le rôle, dans les mots de la maquette validée. Un rôle inconnu se lit tel quel plutôt
     que d'être maquillé en « membre ». `court` : « responsable » seul, la forme de « Qui y
     entre » d'un bac à sable (COL-4, maquette du 2026-10-24), où il n'y a qu'un projet. */
  function libelleRole(role, court) {
    if (role === "responsable") return court ? "responsable" : "responsable du projet";
    if (role === "membre") return "membre";
    return String(role);
  }

  /* CE QUE LA BASE OUVRE AUX MEMBRES (COL-3, D10 ; écran de la 3a, tranché par Hugo sur
     maquette le 2026-10-17) : trois positions, une phrase chacune, à la création d'un projet
     (« ouverte » présélectionnée) et dans sa fiche. `valeur` est ce que le serveur accepte
     pour `acces_membres` — `autorisation.ACCES_MEMBRES`, puis `null` pour la base protégée ;
     une troisième valeur recopiée, mesurée comme les deux autres par
     `tests/test_projet_ecran.py`, ordre compris. */
  const POSITIONS = [
    { valeur: "ecriture", libelle: "ouverte",
      phrase: "Les membres du projet y annotent et y organisent les albums, comme ses responsables." },
    { valeur: "lecture", libelle: "en lecture",
      phrase: "Les membres voient ses albums sans y écrire ; ils travaillent dans leurs propres collections." },
    { valeur: null, libelle: "protégée",
      phrase: "Personne d'autre que ses responsables — et ceux qu'ils font entrer par « Qui entre »." },
  ];

  function position(valeur) {
    return POSITIONS.find((p) => p.valeur === (valeur === undefined ? null : valeur))
      || POSITIONS[POSITIONS.length - 1];
  }

  /* La phrase dite AVANT d'appliquer un changement de position (Hugo, sur maquette) :
     resserrer n'efface rien ; ouvrir dit à combien d'entrées du projet cela s'ouvre.
     `avant`, `apres` : deux valeurs de `POSITIONS` ; `nMembres` : les entrées qui ne sont pas
     responsables ; `base` : le nom de la collection de base. Chaîne vide si rien ne change. */
  function phraseChangement(avant, apres, nMembres, base) {
    const rang = (v) => (v === "ecriture" ? 2 : v === "lecture" ? 1 : 0);
    const a = avant === undefined ? null : avant, b = apres === undefined ? null : apres;
    if (a === b) return "";
    const nom = `« ${base} »`;
    if (rang(b) < rang(a)) {
      return `Resserrer n'efface aucun travail : ce que les membres ont fait dans ${nom} y `
        + "reste. " + (b === null
          ? "Ils ne la verront plus, sauf à y être entrés par « Qui entre »."
          : "Ils la liront encore, sans plus y écrire.");
    }
    const n = nMembres || 0;
    const entrees = n === 0 ? "aucune entrée du projet pour l'instant"
      : `${n} entrée${n > 1 ? "s" : ""} du projet`;
    return `Ouvrir donne à ${entrees} le droit ${b === "ecriture"
      ? "d'annoter et d'organiser les albums" : "de lire"} dans ${nom}, dès maintenant.`;
  }

  /* Ce qu'ENTRER dans le projet vient d'ouvrir à qui y entre comme membre (« + Faire
     entrer ») : sa collection de base, selon la position — et elle seule (D10). Dire
     « aucune collection ne lui est ouverte » était faux depuis la base. `base` :
       - absent (`undefined`) : l'hôte ne dit rien de la base, la phrase ne dit que la règle ;
       - `null` : le projet n'a pas de base, rien ne s'ouvre ;
       - `{ nom, acces_membres }` : la base et sa position. */
  function phraseEntree(base) {
    if (base === undefined) {
      return "Sa collection de base lui est ouverte selon ce que le projet a choisi ; "
        + "aucune autre collection ne lui est ouverte pour autant.";
    }
    if (base === null) return "Aucune collection ne lui est ouverte pour autant.";
    const nom = `« ${base.nom} »`;
    const v = base.acces_membres === undefined ? null : base.acces_membres;
    if (v === null) {
      return `La collection de base ${nom} est protégée : aucune collection ne lui est `
        + "ouverte pour autant.";
    }
    return `Il entre dans la collection de base ${nom}, ${v === "ecriture"
      ? "pour y annoter" : "en lecture"} ; aucune autre collection ne lui est ouverte pour `
      + "autant.";
  }

  return { CLE, EVENEMENT, LONGUEUR_NOM, ROLES, POSITIONS, courant, lire, retenir, choisir,
           duProjet, albumsDuProjet, basculeVers, pourRanger, libelleRole, position,
           phraseChangement, phraseEntree };
});
