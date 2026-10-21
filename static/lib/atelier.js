/* L'ATELIER choisit sa COLLECTION avant son album (UX-19) — la logique pure, sans DOM.
   Chargé en <script> par l'Atelier → expose `window.BDAtelier` ; aussi require()-able par
   `tests/js/atelier.test.js`, qui la vérifie par tables de cas. Rien n'est lu au
   chargement : ni le document, ni le stockage, ni l'adresse.

   CE QUE C'EST (Hugo, 2026-10-21). Avec cent cinquante albums dans un projet, et autant de
   collections qui se recoupent, la liste *Album* de l'Atelier ne disait plus à un arrivant
   ni où il est ni ce qu'on attend de lui. Une liste *Collection* la précède désormais : la
   liste *Album* ne montre que les albums rangés dans la collection choisie — un album
   rangé dans deux collections paraît dans chacune —, et « Toutes les collections du
   projet » rend la liste d'avant.

   UN FILTRE DE L'ATELIER, PAS UNE COLLECTION COURANTE. Le projet courant est partagé par
   les cinq surfaces (`lib/projet.js`) ; la collection choisie ici ne l'est avec personne
   (première réponse de Hugo). Elle est retenue par l'Atelier seul, PROJET PAR PROJET, dans
   le stockage local (clé `bd-atelier-collection`, un objet `{ projet: choix }`) ; la
   Bibliothèque ne la lit pas et ne l'écrit pas. Venir d'une collection de la Bibliothèque
   la pose par l'ADRESSE (`/?collection=<id>…`).

   RIEN DE CHOISI : LA BASE (deuxième réponse de Hugo) — la collection où les membres du
   projet entrent ; si on ne la lit pas, la première collection qu'on lit, dans l'ordre de
   la liste. Mais une base qui ne contient AUCUN album qu'on lit ouvre « Toutes les
   collections du projet » (Hugo, 2026-10-21) : la migration v31 a donné à chaque projet
   existant une base neuve et vide, et l'Atelier se serait ouvert vide pour tous ceux qui
   la lisent. Dès qu'elle contient un album lu, c'est elle. Une valeur DÉDUITE n'est jamais
   retenue : celui qui ne lit pas la base aujourd'hui — ou qui la lit vide — retombera sur
   elle le jour où il la lira remplie.

   JAMAIS UN ALBUM OUVERT HORS DE LA LISTE. Un lien `/?album=<id>…` vers un album absent de
   la collection choisie la change pour une collection qui le contient — la première dans
   l'ordre de la liste, donc la base si elle en est —, et ce changement est retenu comme un
   choix : ce que l'on voit est ce que l'on retrouve.

   CE N'EST PAS UNE GARDE. Tout ce qui suit lit ce que le serveur a déjà décidé : les
   collections qu'on lit (`GET /api/collections`, `base`, `projet_id`), celles d'un album
   qu'on lit (`GET /api/albums`, `collections`, bornée par `peut_lire`). L'ORDRE des
   collections n'est pas écrit ici : c'est celui de la Bibliothèque, la base en tête puis
   A → Z (`BDBiblio.trierCollections`), que l'Atelier applique avant d'appeler ce module.

   LE STOCKAGE PEUT MANQUER, et son accès peut lever : tout passe sous try/catch, et sans
   lui l'Atelier s'ouvre sur la base, sans erreur — le choix ne tient que le temps de la
   page. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDAtelier = api;                                                  // navigateur
})(typeof self !== "undefined" ? self : this, function (root) {
  "use strict";

  const CLE = "bd-atelier-collection";
  /* La valeur du choix « Toutes les collections du projet » : la liste d'avant UX-19. Une
     chaîne et non un identifiant, pour qu'aucune collection ne puisse la porter. */
  const TOUTES = "toutes";
  const LIBELLE_TOUTES = "Toutes les collections du projet";

  function stockage() {
    try { return root.localStorage || null; } catch (e) { return null; }
  }

  function entier(v) {
    if (typeof v === "number") return Number.isInteger(v) && v > 0 ? v : null;
    return typeof v === "string" && /^[1-9]\d*$/.test(v) ? Number(v) : null;
  }

  /* Un choix lisible : un identifiant de collection, ou `TOUTES` ; `null` sinon. */
  function choixLu(v) {
    return v === TOUTES ? TOUTES : entier(v);
  }

  /* La clé d'un projet dans l'objet retenu. Sans projet courant — la liste des projets n'a
     pas pu être lue —, une clé à part : le choix vaut alors pour cet état-là seulement. */
  function cleProjet(projetId) {
    return projetId === null || projetId === undefined ? "-" : String(projetId);
  }

  function lireTout(s) {
    try {
      const brut = s ? s.getItem(CLE) : null;
      const v = brut ? JSON.parse(brut) : null;
      return v && typeof v === "object" && !Array.isArray(v) ? v : {};
    } catch (e) { return {}; }
  }

  /* Le choix retenu pour un projet, ou `null` : rien d'écrit, une valeur illisible, ou un
     stockage qui refuse. */
  function lire(projetId, depuis) {
    const s = depuis === undefined ? stockage() : depuis;
    return choixLu(lireTout(s)[cleProjet(projetId)]);
  }

  /* Retient un choix pour un projet, sans toucher à ceux des autres. Rend `false` quand il
     n'a pas pu être écrit : il vaut alors pour la page, pas pour la suivante. */
  function retenir(projetId, choix, dans) {
    const s = dans === undefined ? stockage() : dans;
    const v = choixLu(choix);
    if (v === null) return false;
    try {
      if (!s) return false;
      const tout = lireTout(s);
      tout[cleProjet(projetId)] = v;
      s.setItem(CLE, JSON.stringify(tout));
      return true;
    } catch (e) { return false; }
  }

  /* La collection qu'ouvre l'Atelier quand rien n'est choisi : la BASE du projet, si on la
     lit et qu'elle contient au moins un des `albums` (ceux du projet qu'on lit) ; une base
     lue mais vide ouvre `TOUTES` (Hugo, 2026-10-21) ; une base qu'on ne lit pas, la
     première collection de la liste. Sans aucune collection lue — la liste n'a pas pu être
     lue —, `TOUTES` : une panne qui ne concerne pas les albums ne les cache pas. */
  function parDefaut(collections, albums) {
    const liste = Array.isArray(collections) ? collections : [];
    const base = liste.find((c) => c.base);
    if (base) {
      const lus = Array.isArray(albums) ? albums : [];
      return lus.some((a) => range(a, base.id)) ? base.id : TOUTES;
    }
    return liste.length ? liste[0].id : TOUTES;
  }

  /* Le choix, s'il vaut encore parmi les collections proposées ; `null` sinon. `TOUTES`
     vaut toujours. */
  function valide(choix, collections) {
    const v = choixLu(choix);
    if (v === TOUTES) return TOUTES;
    if (v === null) return null;
    return (Array.isArray(collections) ? collections : []).some((c) => c.id === v) ? v : null;
  }

  /* L'album est-il rangé dans cette collection, parmi celles qu'on lit de lui ? */
  function range(album, collectionId) {
    return !!album && (Array.isArray(album.collections) ? album.collections : [])
      .some((c) => c.id === collectionId);
  }

  /* Les albums qu'affiche la liste *Album* sous un choix — ceux du projet, déjà bornés par
     l'appelant (`BDProjet.albumsDuProjet`). `TOUTES` les rend tous. */
  function filtrer(albums, choix) {
    const liste = Array.isArray(albums) ? albums : [];
    const v = choixLu(choix);
    if (v === TOUTES || v === null) return liste;
    return liste.filter((a) => range(a, v));
  }

  /* LE CHOIX À APPLIQUER, et pourquoi. Entrées :
       · `collections` — celles du projet qu'on lit, DANS L'ORDRE de la liste ;
       · `albums`      — ceux du projet qu'on lit (la liste « Toutes ») ;
       · `adresse`     — la collection que pose l'adresse (`?collection=`), ou `null` ;
       · `retenu`      — le choix retenu pour ce projet, ou `null` ;
       · `albumVise`   — l'album qui DOIT être dans la liste (un lien, l'album importé), ou
                         `null`.
     L'adresse l'emporte sur ce qui est retenu, et ce qui est retenu sur le défaut — tant
     qu'ils valent parmi les collections proposées. Puis l'album visé : s'il est du projet
     et absent de la collection retenue, on passe à la première collection qui le contient,
     ou à `TOUTES` si aucune ne le contient.
     Rend `{ choix, raison }`, la raison disant à l'appelant s'il faut RETENIR : `adresse` et
     `album` sont des choix — on les retient — ; `retenu` l'est déjà ; `defaut` ne l'est
     jamais. */
  function resoudre(entrees) {
    const e = entrees || {};
    const collections = Array.isArray(e.collections) ? e.collections : [];
    const albums = Array.isArray(e.albums) ? e.albums : [];
    let choix = valide(e.adresse, collections), raison = "adresse";
    if (choix === null) { choix = valide(e.retenu, collections); raison = "retenu"; }
    if (choix === null) { choix = parDefaut(collections, albums); raison = "defaut"; }
    const vise = entier(e.albumVise);
    const album = vise === null ? null : albums.find((a) => a.id === vise);
    if (album && choix !== TOUTES && !range(album, choix)) {
      const hote = collections.find((c) => range(album, c.id));
      choix = hote ? hote.id : TOUTES;
      raison = "album";
    }
    return { choix, raison };
  }

  /* L'album à ouvrir dans la liste filtrée : celui qu'on voulait s'il y est, sinon celui
     qui est ouvert s'il y est encore, sinon le premier ; `null` sur une liste vide. */
  function albumAOuvrir(liste, voulu, ouvert) {
    const l = Array.isArray(liste) ? liste : [];
    for (const id of [entier(voulu), entier(ouvert)]) {
      if (id !== null && l.some((a) => a.id === id)) return id;
    }
    return l.length ? l[0].id : null;
  }

  /* La collection que pose l'adresse, ou `null`. `search` : `location.search`, passé par
     l'appelant. */
  function collectionDeLAdresse(search) {
    try {
      return entier(new URLSearchParams(search || "").get("collection"));
    } catch (e) { return null; }
  }

  /* La seule option d'une liste *Album* vide : sous une collection, elle DIT que la
     collection est vide de ce qu'on lit ; sous « Toutes », que le projet l'est. */
  function libelleVide(choix) {
    return choixLu(choix) === TOUTES || choixLu(choix) === null
      ? "— aucun album —" : "— aucun album dans cette collection —";
  }

  return { CLE, TOUTES, LIBELLE_TOUTES, lire, retenir, parDefaut, valide, filtrer, resoudre,
           albumAOuvrir, collectionDeLAdresse, libelleVide };
});
