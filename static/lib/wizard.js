/* « Par où commencer » (UX-6) — ce que le wizard DÉCIDE, sans DOM.

   Chargé en <script> sur les SIX surfaces → expose `window.BDWizard` ; aussi require()-able
   par `tests/js/wizard.test.js`, qui le vérifie par tables de cas, et lu par
   `tests/test_wizard_marques.py`, qui confronte la visite aux gabarits. Rien n'est lu au
   chargement : ni le document, ni le stockage, ni l'heure.

   La forme a été tranchée par Hugo sur maquette le 2026-11-02 (`pilotage/UX-6.md`, zone
   « Tranché par Hugo sur maquette ») : une présentation (un ALBUM de pages), le choix d'un
   parcours, la visite des pages, puis les gestes. Ce module en tient :
     · les TEXTES de l'album, que Hugo a réécrits sur la maquette et qui se reprennent tels
       quels (`PAGES`, `FIN`) ;
     · les neuf ÉTAPES et le parcours rapide (`ETAPES`, `RAPIDE`, `etapes`) ;
     · la VISITE des sept pages et la marque stable de chacune de ses zones (`VISITE`,
       `marques`) — un attribut `data-parcours` sur la surface, que le test exige ;
     · le SOUVENIR (`lireSouvenir`, `retenirSouvenir`) : l'album déjà vu, le parcours choisi,
       l'étape. Tranché par Hugo le 2026-11-03 : dans le NAVIGATEUR, rangé par login comme
       `bd-bacs-a-sable`, et sous l'identifiant du bac à sable — aucune migration ;
     · quand l'album s'ouvre seul (`ouvreSeul`), et où mène chaque étape (`adresseEtape`).

   Le serveur reste seul à trancher les droits : ce module ne lit que la ligne du projet
   courant (`GET /api/projets`), la vue de son bac à sable (`GET /api/bac-a-sable`) et la
   présence des moteurs (`GET /api/sante`). */
(function (root, factory) {
  const api = factory(root);
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDWizard = api;                                                   // navigateur
})(typeof self !== "undefined" ? self : this, function (root) {
  "use strict";

  /* ── La typographie ────────────────────────────────────────────────────────────────
     Les espaces insécables du français, posées à un seul endroit : devant « : ; ! ? » et
     après « « », entre un nombre et ce qu'il compte, et le trait d'union de « -ils », qui
     ne doit pas laisser « répondent- » en fin de ligne. */
  function typo(s) {
    return String(s == null ? "" : s)
      .replace(/ ([:;!?»])/g, " $1")
      .replace(/« /g, "« ")
      .replace(/-(les|ils)\b/g, "‑$1")
      .replace(/\b(planche|case|bulle) (\d)/g, "$1 $2")
      .replace(/(\d) (gestes|étapes|minutes|cases|bulles|planches)/g, "$1 $2");
  }

  /* ── L'album de présentation ───────────────────────────────────────────────────────
     Les pages, dans l'ordre retenu (la page sur le corpus en 2e, le travail à plusieurs
     sur une carte à lui). Le TEXTE est celui de Hugo, repris tel quel de la maquette ; la
     page des moteurs a deux textes, selon ce que `GET /api/sante` dit de l'instance. */
  const PAGES = [
    { k: "outil", titre: "Interrogez le texte et l'image",
      texte: "Comment le texte et l'image se répondent-ils ? BéDéditeur sert à l'analyser, "
        + "notamment dans les bandes dessinées numérisées. Page par page, étudiez ce qui est "
        + "écrit, qui parle, comment c'est dessiné, quelle couleur est utilisée, commentez "
        + "chaque détail. Le travail d'analyse est le vôtre ; l'outil le met en forme, le "
        + "garde et vous permet d'exploiter vos résultats." },
    { k: "corpus", titre: "Constituez votre corpus",
      texte: "Vous importez les pages, vous décrivez chaque album (auteur, édition, date, "
        + "etc.) et vous pouvez les ranger en collections, selon ce que vous étudiez. "
        + "L'ensemble forme votre corpus." },
    { k: "zones", titre: "Repérez, segmentez, organisez",
      texte: "Dans un album, chaque planche, case ou bulle peut devenir une zone à annoter, "
        + "commenter et exporter. Tracez des cadres où vous le souhaitez et qualifiez-les. "
        + "Ce découpage permet ensuite de transcrire une bulle précise, ou de la citer : "
        + "« planche 3, case 2, bulle 1 »." },
    { k: "moteurs", titre: "Automatisez la reconnaissance",
      texte: "Réalisez une première reconnaissance de votre corpus : les moteurs intégrés "
        + "découpent les cases et les bulles et transcrivent le texte automatiquement. Vous "
        + "n'avez plus qu'à corriger, et votre correction n'est jamais écrasée.",
      sansMoteur: "Une instance équipée découpe les cases et les bulles et transcrit le texte "
        + "automatiquement. Ici, les moteurs ne sont pas installés : vous tracez et vous "
        + "transcrivez à la main." },
    { k: "analyse", titre: "Analysez et annotez",
      texte: "Annotez votre corpus à partir d'un vocabulaire que vous choisissez. Vous lisez, "
        + "et vous notez ce que vous voyez, selon vos propres termes." },
    { k: "collab", titre: "Travaillez à plusieurs",
      texte: "Invitez vos collègues dans un projet et choisissez qui peut lire, annoter ou "
        + "exporter. Chaque annotation garde son auteur, et un doute se discute directement "
        + "sur la zone concernée." },
    { k: "sortir", titre: "Recherchez, exportez et partagez",
      texte: "Cherchez un mot dans tout le corpus, comparez ses emplois, puis sortez vos "
        + "données dans les formats de la recherche pour les publier ou les déposer." },
  ];

  /* La dernière page : le choix d'un parcours. */
  const FIN = {
    titre: "Essayez sur une vraie planche",
    texte: "Vous êtes dans votre bac à sable : un espace d'essai rien qu'à vous. Ce que vous y "
      + "faites ne touche aucun vrai corpus, et tout s'efface chaque lundi.",
    parcours: [
      { k: "rapide", titre: "Parcours rapide",
        detail: "4 gestes, 5 minutes : tracer, corriger, transcrire, annoter" },
      { k: "complet", titre: "Parcours complet",
        detail: "Les 9 étapes, 15 minutes : du corpus à l'export" },
    ],
    jamais: "Ne plus afficher",
  };

  const TITRE_ALBUM = "Bienvenue dans BéDéditeur";
  const TITRE_CARTE = "Par où commencer";

  /* Ce que dit l'album d'une instance : la page des moteurs change de texte quand AUCUN des
     trois moteurs de reconnaissance n'est là. Une réponse illisible ne dit rien : le texte
     de l'instance équipée, qui est celui de Hugo. */
  function moteurs(sante) {
    if (!sante || typeof sante !== "object") return { aucun: false, ocr: true };
    const k = !!sante.kumiko, b = !!sante.bulles, o = !!sante.ocr;
    return { aucun: !k && !b && !o, ocr: o };
  }

  function textePage(page, m) {
    if (!page) return "";
    return typo(page.sansMoteur && m && m.aucun ? page.sansMoteur : page.texte);
  }

  /* ── Les neuf étapes ───────────────────────────────────────────────────────────────
     Neuf et non huit (Hugo, 2026-11-02) : « Tracer une zone » s'ajoute entre
     « Pré-remplir » et « Corriger le découpage ». Chaque étape nomme une SURFACE et un
     GESTE ; `dite` : une étape qu'on lit sans geste à faire sur la planche. La phrase de
     « Constituer le corpus » nomme l'album du parcours tel que le jeu l'a posé. */
  const ETAPES = [
    { k: "corpus", titre: "Constituer le corpus", ou: "Bibliothèque", surface: "/corpus",
      phrase: "Un album rassemble des planches. Le vôtre est déjà là : ouvrez {album}." },
    { k: "decrire", titre: "Décrire l'album", ou: "Bibliothèque", surface: "/corpus",
      album: true,
      phrase: "Une notice dit d'où vient l'album. Notez la source de numérisation." },
    { k: "preremplir", titre: "Pré-remplir", ou: "Atelier, Traitement", surface: "/",
      facultatif: true,
      phrase: "Un moteur peut lire le texte des bulles à votre place : c'est l'OCR. "
        + "Lancez-le, puis regardez ce qu'il propose.",
      sansMoteur: "Aucun moteur n'est installé sur cette instance. Rien n'est cassé : le "
        + "découpage et le texte se font à la main." },
    { k: "tracer", titre: "Tracer une zone", ou: "Atelier, mode Édition", surface: "/",
      mode: "edition",
      phrase: "Glissez sur le fond pour tracer une case. Dans une case, maintenez Maj et "
        + "glissez pour tracer une bulle." },
    { k: "decoupage", titre: "Corriger le découpage", ou: "Atelier, mode Édition",
      surface: "/", mode: "edition",
      phrase: "Le cadre d'une bulle est trop petit. Agrandissez-le par une de ses poignées : "
        + "tout le texte doit tenir dedans." },
    { k: "transcrire", titre: "Transcrire et relire", ou: "Atelier, mode Transcription",
      surface: "/", mode: "transcription",
      phrase: "Recopiez le texte de la bulle, tel qu'il est écrit. La touche Tab passe à la "
        + "bulle suivante." },
    { k: "annoter", titre: "Annoter", ou: "Page Annotation", surface: "/annotation",
      phrase: "Cliquez un mot de la bulle, puis une entrée de la grille, à droite : c'est le "
        + "vocabulaire du projet." },
    { k: "chercher", titre: "Chercher et explorer", ou: "Recherche, Exploration",
      surface: "/recherche", dite: true, sansAlbum: true,
      phrase: "Ces deux pages portent sur le vrai corpus : votre bac à sable n'y paraît pas." },
    { k: "exporter", titre: "Exporter", ou: "Bibliothèque, Atelier", surface: "/corpus",
      album: true, dite: true,
      // À trancher par Hugo : la phrase de la maquette promettait des sorties qu'un bac à
      // sable refuse (le jeu de production est en part serveur) ; celle-ci ne promet rien
      // du bac à sable.
      phrase: "Ailleurs que dans un bac à sable, une collection sort en fiche, en "
        + "enregistrements et en manifeste IIIF, et un album en JSON, CSV ou TEI." },
  ];
  const RAPIDE = ["tracer", "decoupage", "transcrire", "annoter"];
  const PARCOURS = ["rapide", "complet"];

  function etapes(parcours) {
    if (parcours === "rapide") return ETAPES.filter((e) => RAPIDE.includes(e.k));
    if (parcours === "complet") return ETAPES.slice();
    return [];
  }

  /* L'album du parcours : la copie du rôle `pas-a-pas` que le jeu a posée dans le bac à
     sable, avec ses planches ; sinon la première copie qui en a une ; `null` sinon. */
  function albumDuParcours(vue) {
    const jeu = Array.isArray(vue && vue.jeu) ? vue.jeu : [];
    const avec = jeu.filter((j) => j && Array.isArray(j.planche_ids) && j.planche_ids.length);
    return avec.find((j) => j.role === "pas-a-pas") || avec[0] || null;
  }

  function phraseEtape(e, vue, m) {
    if (!e) return "";
    if (e.sansMoteur && m && !m.ocr) return typo(e.sansMoteur);
    const a = albumDuParcours(vue);
    return typo(e.phrase.replace("{album}", a && a.titre ? a.titre : "l'album du parcours"));
  }

  /* « facultatif », ou « optionnel ici » quand l'OCR n'est pas là ; `null` sinon. */
  function marqueEtape(e, m) {
    if (!e || !e.facultatif) return null;
    return m && !m.ocr ? "optionnel ici" : "facultatif";
  }

  /* Où mène une étape : sa surface, l'outil qu'elle décrit — le mode de l'Atelier — et la
     planche du parcours (`docs/navigation-round-trip.md`). Sans album du parcours, la
     surface seule. */
  function adresseEtape(e, vue) {
    if (!e) return "/";
    const a = albumDuParcours(vue);
    if (!a || e.sansAlbum) return e.surface;
    const p = new URLSearchParams();
    if (e.surface === "/corpus") {
      if (!e.album) return "/corpus";
      p.set("album", String(a.album_id));
      return `/corpus?${p}`;
    }
    p.set("album", String(a.album_id));
    p.set("planche", String(a.planche_ids[0]));
    if (e.mode) p.set("mode", e.mode);
    return `${e.surface}?${p}`;
  }

  /* ── La visite des pages ───────────────────────────────────────────────────────────
     Sept pages : la barre du haut, puis les six surfaces. Chaque zone porte une MARQUE
     stable, `data-parcours="<marque>"`, posée sur un ou plusieurs éléments de sa surface
     (la zone est leur rectangle commun). `temps` : une page de plusieurs zones se joue en
     deux temps, la fenêtre changeant de côté au bouton « Suivant » (Hugo, 2026-11-02).
     `bande` : la page de la barre du haut, dont les marques vivent sur les six surfaces.

     Les textes sont ceux de la maquette. Le « ? » de la bande (« Revoir les repères de
     cette page ») n'a pas encore sa marque : il naîtra avec la fenêtre sur la zone. */
  const VISITE = [
    { surface: "/", bande: true, titre: "La barre du haut",
      phrase: "Elle est la même partout. Elle dit où vous êtes, et mène d'une page à l'autre.",
      zones: [
        ["bande-pages", "Les six pages", "Atelier et Annotation pour travailler une planche. "
          + "Bibliothèque, Recherche et Exploration pour le corpus. Administration pour "
          + "l'instance."],
        ["bande-projet", "Le projet", "Celui où vous travaillez. Si vous en avez plusieurs, "
          + "il se change ici."],
        ["bande-compte", "Votre compte", "Le compte connecté, et la déconnexion."],
        ["bande-affichage", "Aa", "Le thème, le contraste et la taille du texte."],
        ["bande-bac", "Votre bac à sable", "Quand il s'efface, et ce qu'on y fait : rouvrir "
          + "ce guide, inviter, remettre à neuf."],
      ] },
    { surface: "/", titre: "Atelier",
      phrase: "Le travail sur la planche : tracer, lancer les moteurs, transcrire.",
      zones: [
        ["atelier-planches", "Album et planches", "Choisissez la collection, l'album, puis "
          + "la planche."],
        ["atelier-modes", "Quatre modes", "Navigation pour parcourir les planches, Édition "
          + "pour tracer des zones et les modifier, Annotation pour poser des tags et une "
          + "note (les grilles sont dans la page Annotation), Transcription pour travailler "
          + "le texte."],
        ["atelier-planche", "La planche", "Zoom à la molette, glissé pour la déplacer. "
          + "Chaque cadre est une zone."],
        ["atelier-structure", "Structure", "L'arbre des zones, et le détail de celle qui est "
          + "choisie.", 1],
        ["atelier-actions", "Traitement, Import / Export", "Lancer les moteurs, ajouter des "
          + "planches, sortir un album.", 1],
      ] },
    { surface: "/annotation", titre: "Annotation",
      phrase: "L'analyse, case par case, avec le vocabulaire du projet.",
      zones: [
        ["annotation-lieu", "Où vous êtes", "La collection, l'album, la planche, et le "
          + "retour vers l'Atelier."],
        ["annotation-contexte", "Planche et contexte", "Choisissez une case. Locuteur et "
          + "note s'écrivent ici. L'onglet Synthèse reprend le travail de la planche."],
        ["annotation-case", "La case agrandie", "Choisissez une zone, ou glissez pour tracer "
          + "un détail d'image."],
        ["annotation-mots", "Les mots", "Désignez des mots, et dites sur quoi porte ce que "
          + "vous notez."],
        ["annotation-parcours", "Le parcours", "D'une zone à la suivante, et « terminée » "
          + "quand vous avez fini."],
        ["annotation-grille", "La grille", "Le vocabulaire du projet, ce qui est déjà posé, "
          + "et un guide pour chaque entrée.", 1],
      ] },
    { surface: "/corpus", titre: "Bibliothèque",
      phrase: "Votre corpus : ce qu'il contient, et qui peut y entrer.",
      zones: [
        ["bibliotheque-collections", "Collections", "Filtrez le catalogue, ouvrez une "
          + "collection, créez-en une."],
        ["bibliotheque-catalogue", "Le catalogue", "Les albums du projet. Un clic ouvre la "
          + "fiche."],
        ["bibliotheque-fiche", "La fiche", "La notice, les planches, ce qui se fait sur un "
          + "album.", 1],
        ["bibliotheque-nouvel-album", "Nouvel album", "C'est ici qu'un album se crée, puis "
          + "reçoit ses planches.", 1],
      ] },
    { surface: "/recherche", titre: "Recherche",
      phrase: "Retrouver un mot dans tout le corpus. Votre bac à sable n'y paraît pas.",
      zones: [
        ["recherche-corpus", "Ce que vous lisez", "Le corpus ouvert à votre compte, sans "
          + "votre bac à sable."],
        ["recherche-champ", "Le champ et ses filtres", "Dialogues, notes et tags ; par album, "
          + "par type de zone."],
        ["recherche-facettes", "Facettes grammaticales", "Par catégorie, lemme ou trait."],
        ["recherche-tags", "Le nuage de tags", "Un clic filtre par tag."],
        ["recherche-resultats", "Les résultats", "Un clic ouvre l'aperçu, qui mène à la zone "
          + "dans l'Atelier."],
      ] },
    { surface: "/exploration", titre: "Exploration",
      phrase: "Le corpus en chiffres. Elle ne lit pas non plus votre bac à sable.",
      zones: [
        ["exploration-vues", "Les vues", "Distribution, concordance, croisement, "
          + "comparaison."],
        ["exploration-sous-corpus", "Le sous-corpus", "Ce que la vue regarde : album, type, "
          + "catégorie, tag, locuteur."],
        ["exploration-lexique", "Lexique et accords", "Les définitions du vocabulaire, et les "
          + "mesures d'accord."],
        ["exploration-resultat", "Le résultat", "Les valeurs et leurs fréquences. Un clic "
          + "mène aux emplois en contexte."],
      ] },
    { surface: "/administration", titre: "Administration",
      phrase: "Ce qui porte sur toute l'instance. Vous n'y voyez que ce que votre rôle permet.",
      zones: [
        ["administration-vues", "Les vues", "À faire, Fonds, Projets, Comptes et groupes, "
          + "Instance : selon vos droits."],
        ["administration-instance", "Instance", "Ouvert à tous : l'état des moteurs."],
      ] },
  ];

  /* Les marques que la visite NOMME, page par page : `[{ surface, bande, marque }]`. C'est
     ce que le test confronte aux gabarits et aux scripts qu'ils chargent. */
  function marques() {
    const out = [];
    VISITE.forEach((v) => v.zones.forEach((z) => out.push(
      { surface: v.surface, bande: !!v.bande, marque: z[0] })));
    return out;
  }

  /* ── Le souvenir ───────────────────────────────────────────────────────────────────
     `{ <login>: { bac, efface_le, album_vu, parcours, etape } }`, dans le stockage local,
     toute lecture et toute écriture sous try/catch. UN souvenir par login : on n'a qu'un
     bac à sable à soi. Il ne vaut que pour le bac à sable sous lequel il a été écrit — son
     IDENTIFIANT et sa date d'effacement. La remise à neuf fait naître un projet NEUF, et
     l'effacement du lundi aussi (`routes/bac_a_sable.py`) ; les identifiants de projet ne
     reviennent jamais (v31). L'identifiant suffit donc à reconnaître un bac à sable effacé ;
     la date s'y ajoute pour le cas où il serait repris malgré tout (une base restaurée) :
     un souvenir qui ne correspond pas aux deux n'est pas lu, et le wizard repart du début.
     Sans login, rien n'est ni lu ni écrit. */
  const CLE = "bd-wizard";

  function neuf() { return { album_vu: false, parcours: null, etape: 0 }; }

  function stockage() {
    try { return root.localStorage || null; } catch (e) { return null; }
  }

  function tous(s) {
    const v = s ? JSON.parse(s.getItem(CLE) || "{}") : {};
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  }

  /* Lecture TOLÉRANTE : ce qui manque, ce qui est d'une autre forme ou hors bornes reprend
     sa valeur de départ, champ par champ. */
  function normaliser(v) {
    const n = neuf();
    if (!v || typeof v !== "object") return n;
    const parcours = PARCOURS.includes(v.parcours) ? v.parcours : null;
    const total = etapes(parcours).length;
    const etape = Number.isInteger(v.etape) && v.etape >= 0 && v.etape < total ? v.etape : 0;
    // Un parcours choisi suppose l'album vu : on n'y revient pas sans qu'on le demande.
    return { album_vu: v.album_vu === true || parcours !== null, parcours, etape };
  }

  function memeBac(v, bac) {
    return !!(v && bac && v.bac === bac.id && (v.efface_le || null) === (bac.efface_le || null));
  }

  /* `bac` : `{ id, efface_le }` — la ligne du projet courant (`bac_a_sable.efface_le`) ou la
     vue de `GET /api/bac-a-sable`. */
  function lireSouvenir(login, bac, depuis) {
    if (!login || !bac || !Number.isInteger(bac.id)) return neuf();
    const s = depuis === undefined ? stockage() : depuis;
    try {
      const v = tous(s)[login];
      return memeBac(v, bac) ? normaliser(v) : neuf();
    } catch (e) { return neuf(); }
  }

  function retenirSouvenir(login, bac, souvenir, dans) {
    if (!login || !bac || !Number.isInteger(bac.id)) return false;
    const s = dans === undefined ? stockage() : dans;
    try {
      if (!s) return false;
      let t;
      try { t = tous(s); } catch (e) { t = {}; }
      const n = normaliser(souvenir);
      t[login] = { bac: bac.id, efface_le: bac.efface_le || null,
                   album_vu: n.album_vu, parcours: n.parcours, etape: n.etape };
      s.setItem(CLE, JSON.stringify(t));
      return true;
    } catch (e) { return false; }
  }

  /* Le bac à sable courant, s'il est LE SIEN : `{ id, efface_le }`, `null` sinon. Le wizard
     vit dans le bac à sable de chacun ; chez un autre, où l'on est invité, il ne s'ouvre pas
     (à trancher par Hugo). */
  function bacASoi(projet) {
    const b = projet && projet.bac_a_sable;
    if (!b || !b.mien || !Number.isInteger(projet.id)) return null;
    return { id: projet.id, efface_le: b.efface_le || null };
  }

  /* L'album s'ouvre SEUL au chargement d'une page (décision E du 2026-11-02) : dans son
     propre bac à sable, sous une identité, tant que l'album n'a pas été vu — un parcours
     choisi, ou « Ne plus afficher » coché. Fermer sans cocher ne vaut pas renoncement :
     l'album revient au chargement suivant (le contrat écrit le 2026-08-27, à confirmer
     par Hugo sur l'écran codé). */
  function ouvreSeul(login, projet, souvenir) {
    if (!login || !bacASoi(projet)) return false;
    return !normaliser(souvenir).album_vu;
  }

  /* Les gestes sur le souvenir — de nouveaux objets, jamais une mutation. */
  function choisirParcours(souvenir, parcours) {
    if (!PARCOURS.includes(parcours)) return normaliser(souvenir);
    const avant = normaliser(souvenir);
    // Passer d'un parcours à l'autre garde l'étape où l'on est, si elle y figure.
    const ici = etapes(avant.parcours)[avant.etape];
    const i = ici ? etapes(parcours).findIndex((e) => e.k === ici.k) : -1;
    return { album_vu: true, parcours, etape: i >= 0 ? i : 0 };
  }

  function allerA(souvenir, i) {
    const n = normaliser(souvenir);
    const total = etapes(n.parcours).length;
    if (!Number.isInteger(i) || i < 0 || i >= total) return n;
    return Object.assign({}, n, { etape: i });
  }

  function neJamaisAfficher(souvenir, oui) {
    const n = normaliser(souvenir);
    return Object.assign({}, n, { album_vu: !!oui || n.parcours !== null });
  }

  return { CLE, PAGES, FIN, TITRE_ALBUM, TITRE_CARTE, ETAPES, RAPIDE, PARCOURS, VISITE,
           typo, moteurs, textePage, etapes, albumDuParcours, phraseEtape, marqueEtape,
           adresseEtape, marques, neuf, lireSouvenir, retenirSouvenir, bacASoi, ouvreSeul,
           choisirParcours, allerA, neJamaisAfficher };
});
