/* « Par où commencer » (UX-6) — ce que le wizard DÉCIDE, sans DOM.

   Chargé en <script> sur les SIX surfaces → expose `window.BDWizard` ; aussi require()-able
   par `tests/js/wizard.test.js`, qui le vérifie par tables de cas, et lu par
   `tests/test_wizard_marques.py`, qui confronte la visite aux gabarits. Rien n'est lu au
   chargement : ni le document, ni les stockages, ni l'heure.

   La forme a été tranchée par Hugo sur maquette le 2026-11-02 (`pilotage/UX-6.md`, zone
   « Tranché par Hugo sur maquette ») : une présentation (un ALBUM de pages), le choix d'un
   parcours, la visite des pages, puis les gestes. Ce module en tient :
     · les TEXTES de l'album, que Hugo a réécrits sur la maquette et qui se reprennent tels
       quels (`PAGES`, `FIN`) ;
     · les neuf ÉTAPES et le parcours rapide (`ETAPES`, `RAPIDE`, `etapes`) ;
     · la VISITE des sept pages et la marque stable de chacune de ses zones (`VISITE`,
       `marques`) — un attribut `data-parcours` sur la surface, que le test exige ;
     · la FENÊTRE sur la zone : les deux temps d'une page et le côté qui va avec, le compte
       de la visite, les repères qu'elle nomme, la page que rouvre le « ? », où mène une
       page de la visite, et sa position le temps qu'elle traverse les pages (`suivant`,
       `cote`, `reperes`, `pageDeLaSurface`, `adresseVisite`, `retenirVisite`) ;
     · le SOUVENIR (`lireSouvenir`, `retenirSouvenir`) : l'album déjà vu, le parcours choisi,
       l'étape. Tranché par Hugo le 2026-11-03 : dans le NAVIGATEUR, rangé par login comme
       `bd-bacs-a-sable`, et sous l'identifiant du bac à sable — aucune migration ;
     · quand l'album s'ouvre seul (`ouvreSeul`), et où mène chaque étape (`adresseEtape`) ;
     · le GUIDE, étape par étape (`faite`, `phraseGuide`, `bulleACorriger`, `cadreAutour`,
       `vueCadree`, `retenirGuide`) : ce qui compte comme une étape faite, la phrase qui
       suit la planche, et le cadrage de « Corriger le découpage ».

   CE QUI COMPTE COMME UNE ÉTAPE FAITE (`pilotage/UX-6.md` : « il le voit sur la planche,
   sans coche à déclarer », Hugo, 2026-11-02). Tout se lit sur la planche du parcours et sur
   son album, tels que le serveur les rend — `GET /api/planches/{id}/regions`,
   `GET /api/planches/{id}/releves`, `GET /api/albums` —, jamais sur ce que l'arrivant
   déclare. Les données d'un bac à sable repartent à neuf chaque lundi : chaque règle tient
   sur un bac à sable NEUF, où le jeu a posé ses régions (`source` « jeu », jamais
   retouchées) et rien d'autre.
     · Constituer le corpus — la fiche de l'album du parcours s'est ouverte dans la
       Bibliothèque (son adresse le nomme), pendant que le guide était sur l'étape ;
     · Décrire l'album — sa notice porte une source de numérisation ;
     · Pré-remplir — une zone de la planche est née d'un moteur (`activite_id`), ou une zone
       de texte que personne n'a tracée ni retouchée porte un texte : celui de l'OCR. Si le
       jeu posait lui-même des textes, l'étape se lirait faite d'emblée ;
     · Tracer une zone — une case ET une bulle tracées à la main (`source` « manuel ») ;
     · Corriger le découpage — le cadre d'une zone que le jeu ou un moteur a posée a été
       repris à la main (`source` « corrige », que l'Atelier pose au premier déplacement ou
       redimensionnement) ;
     · Transcrire et relire — une zone de texte (bulle, cartouche, texte) porte un texte
       qu'une main a écrit ou retouché (`touche`) ; au parcours complet, il faut en plus que
       TOUTES les zones de texte de la planche portent un texte ;
     · Annoter — un relevé est posé sur la planche, sur une zone ou sur la planche entière ;
     · Chercher et explorer, Exporter — des étapes DITES : faites dès que le guide les a
       montrées.
   Le guide marque l'étape faite (« ✓ Fait ») et fait de « Suivant » son geste principal ;
   il ne passe pas seul à la suivante.

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

  /* La marque d'une page de l'album : « optionnel ici » sur celle des moteurs quand aucun
     n'est installé (`pilotage/UX-6.md`, « Sans moteur, “Pré-remplir” se dit optionnel ») ;
     `null` sinon. */
  function marquePage(page, m) {
    return page && page.sansMoteur && m && m.aucun ? "optionnel ici" : null;
  }

  /* ── Les neuf étapes ───────────────────────────────────────────────────────────────
     Neuf et non huit (Hugo, 2026-11-02) : « Tracer une zone » s'ajoute entre
     « Pré-remplir » et « Corriger le découpage ». Chaque étape nomme une SURFACE et un
     GESTE ; `dite` : une étape qu'on lit sans geste à faire sur la planche. La phrase de
     « Constituer le corpus » nomme l'album du parcours tel que le jeu l'a posé. */
  const ETAPES = [
    { k: "corpus", titre: "Constituer le corpus", ou: "Bibliothèque", surface: "/corpus",
      zones: ["bibliotheque-catalogue", "bibliotheque-fiche"],
      phrase: "Un album rassemble des planches. Le vôtre est déjà là : ouvrez {album}." },
    { k: "decrire", titre: "Décrire l'album", ou: "Bibliothèque", surface: "/corpus",
      album: true, zones: ["bibliotheque-fiche"],
      phrase: "Une notice dit d'où vient l'album. Notez la source de numérisation." },
    { k: "preremplir", titre: "Pré-remplir", ou: "Atelier, Traitement", surface: "/",
      facultatif: true, zones: ["atelier-actions", "atelier-planche"],
      phrase: "Un moteur peut lire le texte des bulles à votre place : c'est l'OCR. "
        + "Lancez-le, puis regardez ce qu'il propose.",
      sansMoteur: "Aucun moteur n'est installé sur cette instance. Rien n'est cassé : le "
        + "découpage et le texte se font à la main." },
    { k: "tracer", titre: "Tracer une zone", ou: "Atelier, mode Édition", surface: "/",
      mode: "edition", zones: ["atelier-planche", "atelier-structure"],
      phrase: "Glissez sur le fond pour tracer une case. Dans une case, maintenez Maj et "
        + "glissez pour tracer une bulle." },
    { k: "decoupage", titre: "Corriger le découpage", ou: "Atelier, mode Édition",
      surface: "/", mode: "edition", zones: ["atelier-planche", "atelier-structure"],
      phrase: "Le cadre d'une bulle est trop petit. Agrandissez-le par une de ses poignées : "
        + "tout le texte doit tenir dedans." },
    { k: "transcrire", titre: "Transcrire et relire", ou: "Atelier, mode Transcription",
      surface: "/", mode: "transcription", zones: ["atelier-transcription"],
      phrase: "Recopiez le texte de la bulle, tel qu'il est écrit. La touche Tab passe à la "
        + "bulle suivante." },
    { k: "annoter", titre: "Annoter", ou: "Page Annotation", surface: "/annotation",
      zones: ["annotation-case", "annotation-mots", "annotation-grille"],
      phrase: "Cliquez un mot de la bulle, puis une entrée de la grille, à droite : c'est le "
        + "vocabulaire du projet." },
    { k: "chercher", titre: "Chercher et explorer", ou: "Recherche, Exploration",
      surface: "/recherche", dite: true, sansAlbum: true,
      zones: ["recherche-champ", "recherche-resultats"],
      phrase: "Ces deux pages portent sur le vrai corpus : votre bac à sable n'y paraît pas." },
    { k: "exporter", titre: "Exporter", ou: "Bibliothèque, Atelier", surface: "/corpus",
      album: true, dite: true, zones: ["bibliotheque-fiche"],
      // La phrase de la maquette promettait des sorties qu'un bac à sable refuse (le jeu de
      // production est en part serveur) ; celle-ci ne promet rien du bac à sable (Hugo,
      // 2026-11-03).
      phrase: "Ailleurs que dans un bac à sable, une collection sort en fiche, en "
        + "enregistrements et en manifeste IIIF, et un album en JSON, CSV ou TEI.",
      // Et elle dit, devant, ce qui sort VRAIMENT d'ici (`phraseExport`).
      ici: { rien: "Ici, rien ne sort : l'export d'un bac à sable est fermé.",
             un: "Ici, seul {titres} peut sortir, tant que vous n'y importez aucune planche.",
             plusieurs: "Ici, seuls {titres} peuvent sortir, tant que vous n'y importez "
               + "aucune planche." } },
  ];
  const RAPIDE = ["tracer", "decoupage", "transcrire", "annoter"];

  /* Le FOYER d'une étape (Hugo, sur la maquette du 2026-11-02, redit le 2026-11-04) : ce
     qu'elle éclaire, des éléments PRÉCIS de la page — la carte de l'album, la tête de sa
     fiche, « Traitement » et son menu ouvert, LA bulle à corriger et le panneau, la colonne
     du texte de la Transcription, la case agrandie et la grille, le champ de recherche. Le
     trou de l'assombri est leur rectangle commun, et la fenêtre se pose à côté
     (`placerFenetre`). Une marque `data-parcours` désigne chacun ; `@album` (la carte de
     l'album du parcours) et `@bulle` (la bulle à corriger) se résolvent à l'écran. Les
     ZONES d'une étape, plus larges, restent ce qui est jouable. */
  const FOYERS = {
    corpus: ["@album"],
    decrire: ["bibliotheque-notice"],
    preremplir: ["atelier-traitement", "atelier-traitement-menu"],
    tracer: ["atelier-planche", "atelier-structure"],
    decoupage: ["@bulle", "atelier-structure"],
    transcrire: ["atelier-transcription-texte"],
    annoter: ["annotation-case", "annotation-grille"],
    chercher: ["recherche-champ", "recherche-bac"],
    exporter: ["bibliotheque-actes"],
  };

  function foyer(e) { return (e && FOYERS[e.k]) || []; }

  /* Où poser la fenêtre du guide : à DROITE du foyer si elle y tient, sinon à GAUCHE,
     sinon DESSOUS, sinon DESSUS — bornée à l'écran, à `marge` du foyer ; `repli` si rien ne
     tient (l'écran la pose alors en feuille, en bas, et la page lui réserve sa hauteur).
     `f` et `ecran` : `{ l, t, r, b }` ; `taille` : `{ w, h }`. Sans foyer, au centre. */
  function placerFenetre(f, taille, ecran, marge) {
    const e = marge === undefined ? 14 : marge, w = taille.w, h = taille.h, v = ecran;
    const borne = (x, a, b) => Math.max(a, Math.min(x, Math.max(a, b)));
    if (!f) return { cote: "centre", x: (v.l + v.r - w) / 2, y: (v.t + v.b - h) / 2 };
    if (f.r + e + w <= v.r) return { cote: "droite", x: f.r + e, y: borne(f.t, v.t, v.b - h) };
    if (f.l - e - w >= v.l) return { cote: "gauche", x: f.l - e - w, y: borne(f.t, v.t, v.b - h) };
    if (f.b + e + h <= v.b) return { cote: "dessous", x: borne(f.l, v.l, v.r - w), y: f.b + e };
    if (f.t - e - h >= v.t) return { cote: "dessus", x: borne(f.l, v.l, v.r - w), y: f.t - e - h };
    return { cote: "repli", x: v.l, y: v.b - h };
  }

  /* Deux rectangles `{ l, t, r, b }` se recouvrent-ils ? */
  function recouvre(a, b) {
    return !!a && !!b && a.l < b.r && b.l < a.r && a.t < b.b && b.t < a.b;
  }

  /* La part de la scène que la fenêtre laisse libre, pour y cadrer « Corriger » : la plus
     grande des quatre bandes de `scene` à `marge` de `fen` (à sa gauche, à sa droite,
     au-dessus, au-dessous) ; la scène entière si la fenêtre ne la recouvre pas. */
  function zoneLibre(scene, fen, marge) {
    const m = marge === undefined ? 14 : marge;
    if (!recouvre(scene, fen)) return Object.assign({}, scene);
    const bandes = [
      { l: scene.l, t: scene.t, r: Math.min(scene.r, fen.l - m), b: scene.b },
      { l: Math.max(scene.l, fen.r + m), t: scene.t, r: scene.r, b: scene.b },
      { l: scene.l, t: scene.t, r: scene.r, b: Math.min(scene.b, fen.t - m) },
      { l: scene.l, t: Math.max(scene.t, fen.b + m), r: scene.r, b: scene.b },
    ].filter((z) => z.r - z.l > 0 && z.b - z.t > 0);
    if (!bandes.length) return Object.assign({}, scene);
    const aire = (z) => (z.r - z.l) * (z.b - z.t);
    return bandes.reduce((a, z) => (aire(z) > aire(a) ? z : a));
  }
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
    const p = e.phrase.replace("{album}", a && a.titre ? a.titre : "l'album du parcours");
    const ici = phraseExport(e, vue);
    return typo(ici ? `${ici} ${p}` : p);
  }

  /* Ce qui sort VRAIMENT du bac à sable (`pilotage/UX-6.md`, « “Exporter” dit ce qui sort
     vraiment d'un bac à sable ») : le serveur décide l'export d'un album de bac à sable
     DOCUMENT par document — seule une copie d'un document du jeu ouvert à l'export
     (`jeu[].exportable` de `GET /api/bac-a-sable`, la part du dépôt) sort, et pas si elle
     porte une planche importée ; le jeu de production est tout entier en part serveur, donc
     rien n'y sort. Sans la vue du bac à sable, on ne sait pas : rien n'est dit, la phrase de
     l'étape ne promettant rien d'ici. */
  function phraseExport(e, vue) {
    if (!e || !e.ici || !vue || typeof vue !== "object") return "";
    const jeu = Array.isArray(vue.jeu) ? vue.jeu : [];
    const titres = jeu.filter((j) => j && j.exportable === true && j.titre)
      .map((j) => `« ${j.titre} »`);
    if (!titres.length) return e.ici.rien;
    const liste = titres.length === 1 ? titres[0]
      : `${titres.slice(0, -1).join(", ")} et ${titres[titres.length - 1]}`;
    return (titres.length === 1 ? e.ici.un : e.ici.plusieurs).replace("{titres}", liste);
  }

  /* « facultatif », ou « optionnel ici » quand l'OCR n'est pas là ; `null` sinon. Sur la
     carte, la maquette dit pourquoi : « optionnel ici : moteur absent ». */
  function marqueEtape(e, m, surLaCarte) {
    if (!e || !e.facultatif) return null;
    if (!(m && !m.ocr)) return "facultatif";
    return surLaCarte ? "optionnel ici : moteur absent" : "optionnel ici";
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

     Les textes sont ceux de la maquette, le « ? » de la bande compris (« Revoir les repères
     de cette page », posé par `theme.js`). */
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
        ["bande-aide", "?", "Rouvre les repères de la page où vous êtes."],
        ["bande-bac", "Votre bac à sable", "Quand il s'efface, et ce qu'on y fait : rouvrir "
          + "ce guide, inviter, remettre à neuf."],
      ],
      // Chez un invité, la ligne n'offre que « Quitter… » : ni le guide, ni inviter, ni
      // remettre à neuf (`pilotage/UX-6.md`, choix de la tranche 2).
      invite: { zones: { "bande-bac": "Quand il s'efface, et ce qu'on y fait : le quitter." } } },
    { surface: "/", titre: "Atelier",
      phrase: "Le travail sur la planche : tracer, lancer les moteurs, transcrire.",
      // Hors d'un bac à sable, la phrase de la maquette ; dans un bac à sable, elle ne
      // promet pas d'en sortir un album, que le serveur y refuse (`phraseExport`).
      horsBac: { zones: { "atelier-actions": "Lancer les moteurs, ajouter des planches, "
        + "sortir un album." } },
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
          + "planches. Sortir un album, hors d'un bac à sable.", 1],
        // Ne se voit qu'en mode Transcription, qui recouvre la page : le guide y conduit.
        ["atelier-transcription", "Transcription", "La zone agrandie et son texte. Tab passe à "
          + "la zone suivante.", 1],
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
      horsBac: { phrase: "Retrouver un mot dans tout le corpus.",
                 zones: { "recherche-corpus": "Le corpus ouvert à votre compte." } },
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
      horsBac: { phrase: "Le corpus en chiffres." },
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

  /* ── La fenêtre sur la zone ────────────────────────────────────────────────────────
     Une position de la visite est `{ page, temps }` : la page de `VISITE`, et le temps où
     l'on est — 0, ou 1 pour la suite d'une page de plusieurs zones (Hugo, 2026-11-02). La
     fenêtre change de côté avec le temps, au bouton « Suivant », jamais au survol : à droite
     au premier temps, à gauche au second, que ses zones occupent la gauche ou la droite de
     la page (les zones de second temps sont la colonne de droite et les gestes rares). */
  function tempsDe(i) {
    const v = VISITE[i];
    if (!v) return [];
    return v.zones.some((z) => (z[3] || 0) === 1) ? [0, 1] : [0];
  }

  /* Une position lisible, ou `null` : une page hors de la visite, un temps que la page n'a
     pas. */
  function position(pos) {
    if (!pos || !Number.isInteger(pos.page) || !VISITE[pos.page]) return null;
    const t = pos.temps === undefined ? 0 : pos.temps;
    return tempsDe(pos.page).includes(t) ? { page: pos.page, temps: t } : null;
  }

  /* « Suivant » : le second temps de la page s'il existe, sinon la page suivante ; `null`
     au bout de la visite. « ← » : l'inverse, et la page précédente reprend à son DERNIER
     temps — on revient d'où l'on vient. */
  function suivant(pos) {
    const p = position(pos);
    if (!p) return null;
    if (p.temps === 0 && tempsDe(p.page).includes(1)) return { page: p.page, temps: 1 };
    return p.page + 1 < VISITE.length ? { page: p.page + 1, temps: 0 } : null;
  }

  function precedent(pos) {
    const p = position(pos);
    if (!p) return null;
    if (p.temps === 1) return { page: p.page, temps: 0 };
    if (p.page === 0) return null;
    const t = tempsDe(p.page - 1);
    return { page: p.page - 1, temps: t[t.length - 1] };
  }

  function estFin(pos) { return !!position(pos) && suivant(pos) === null; }

  /* Le compte dit la page ET le temps : « Visite n / 7 » ne reste pas figé entre les deux
     temps d'une page (`pilotage/UX-6.md`, « La maquette se mesure sur l'écran codé ») — la
     maquette le laissait à la même valeur. La forme « · 1 / 2 » est un choix à revoir sur
     l'écran codé. */
  function compteVisite(pos) {
    const p = position(pos);
    if (!p) return "";
    const t = tempsDe(p.page);
    const base = `Visite ${p.page + 1} / ${VISITE.length}`;
    return typo(t.length > 1 ? `${base} · ${p.temps + 1} / ${t.length}` : base);
  }

  function cote(pos) {
    const p = position(pos);
    return p && p.temps === 1 ? "gauche" : "droite";
  }

  /* Les repères d'un temps : `[{ marque, nom, phrase, n }]`. `visible(marque)` dit si la
     zone se voit sur la page à cet instant : la fenêtre ne nomme que ce que la page montre
     (Hugo, 2026-11-02, pour le « ? » ; la visite suit la même règle). Le numéro court sur
     les zones VISIBLES de toute la page, dans l'ordre de la visite : le second temps
     continue le premier, et un trou ne laisse pas de numéro sans zone. */
  function reperes(i, t, visible, bac) {
    const v = VISITE[i];
    if (!v) return [];
    const voit = typeof visible === "function" ? visible : () => true;
    const hors = (!bac && v.horsBac && v.horsBac.zones)
      || (bac === "autre" && v.invite && v.invite.zones) || {};
    const out = [];
    let n = 0;
    v.zones.forEach((z) => {
      if (!voit(z[0])) return;
      n += 1;
      if ((z[3] || 0) === t) {
        out.push({ marque: z[0], nom: typo(selonLeBac(z[1], bac)),
                   phrase: typo(hors[z[0]] || selonLeBac(z[2], bac)), n });
      }
    });
    return out;
  }

  /* Ce qu'une page dit du bac à sable dépend de celui où l'on est : `bac` vaut "mien",
     "autre" (un invité : « ce bac à sable », comme `BDBac.horsRecherche`) ou null. Le
     « ? » est offert hors d'un bac à sable (Hugo, 2026-11-04) : là, la Recherche et
     l'Exploration ne disent pas « votre bac à sable n'y paraît pas » à qui n'en a pas
     (`horsBac`). La visite, elle, ne se joue que dans son propre bac à sable. */
  function selonLeBac(texte, bac) {
    if (bac !== "autre") return texte;
    return texte.replace(/([Vv])otre bac à sable/g, (m, v) => `${v === "V" ? "C" : "c"}e bac à sable`);
  }

  function phrasePage(i, bac) {
    const v = VISITE[i];
    if (!v) return "";
    if (!bac && v.horsBac && v.horsBac.phrase) return typo(v.horsBac.phrase);
    return typo(selonLeBac(v.phrase, bac));
  }

  /* Le bac à sable du projet courant, au sens de `selonLeBac`. */
  function bacDuProjet(projet) {
    const b = projet && projet.bac_a_sable;
    return b ? (b.mien ? "mien" : "autre") : null;
  }

  /* Les temps d'une page où la page montre au moins une zone : le « ? » ne fait pas passer
     à un temps vide. Au moins le premier, pour que la fenêtre dise la page. */
  function tempsVisibles(i, visible) {
    const t = tempsDe(i).filter((x) => reperes(i, x, visible).length);
    return t.length ? t : tempsDe(i).slice(0, 1);
  }

  /* Le « ? » rouvre les repères de la page où l'on est : la page de la visite de cette
     SURFACE, jamais celle de la barre du haut (qui vit sur toutes). `-1` hors des six. */
  function pageDeLaSurface(chemin) {
    const c = String(chemin || "").replace(/\/+$/, "") || "/";
    return VISITE.findIndex((v) => !v.bande && v.surface === c);
  }

  /* Où mène une page de la visite : sa surface, sur la planche du parcours là où une
     planche se travaille, la fiche de l'album dans la Bibliothèque (sa zone « La fiche »),
     la vue Instance dans l'Administration (sa zone « Instance », que les autres vues
     masquent). Ni mode ni outil : la visite montre, elle ne fait rien faire. */
  function adresseVisite(i, vue) {
    const v = VISITE[i];
    if (!v) return "/";
    if (v.surface === "/administration") return "/administration?vue=instance";
    const a = albumDuParcours(vue);
    if (!a) return v.surface;
    const p = new URLSearchParams();
    p.set("album", String(a.album_id));
    if (v.surface === "/corpus") return `/corpus?${p}`;
    if (v.surface !== "/" && v.surface !== "/annotation") return v.surface;
    p.set("planche", String(a.planche_ids[0]));
    return `${v.surface}?${p}`;
  }

  /* La visite en cours traverse les pages : sa position vit dans le stockage de SESSION
     (un onglet, le temps de la visite), sous le login et le bac à sable qui l'ont
     commencée, toute lecture et écriture sous try/catch. Sans ce stockage, la visite
     s'arrête au changement de page : rien de plus. */
  const CLE_VISITE = "bd-wizard-visite";

  function stockageSession() {
    try { return root.sessionStorage || null; } catch (e) { return null; }
  }

  function retenirVisite(login, bac, pos, dans) {
    const p = position(pos);
    if (!login || !bac || !Number.isInteger(bac.id) || !p) return false;
    const s = dans === undefined ? stockageSession() : dans;
    try {
      if (!s) return false;
      s.setItem(CLE_VISITE, JSON.stringify({ login, bac: bac.id, efface_le: bac.efface_le || null,
                                             page: p.page, temps: p.temps }));
      return true;
    } catch (e) { return false; }
  }

  function lireVisite(login, bac, depuis) {
    if (!login || !bac || !Number.isInteger(bac.id)) return null;
    const s = depuis === undefined ? stockageSession() : depuis;
    try {
      const v = s ? JSON.parse(s.getItem(CLE_VISITE) || "null") : null;
      if (!v || v.login !== login || !memeBac(v, bac)) return null;
      return position(v);
    } catch (e) { return null; }
  }

  function oublierVisite(dans) {
    const s = dans === undefined ? stockageSession() : dans;
    try { if (s) s.removeItem(CLE_VISITE); } catch (e) { /* rien à oublier */ }
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
     (Hugo, 2026-11-03). */
  function bacASoi(projet) {
    const b = projet && projet.bac_a_sable;
    if (!b || !b.mien || !Number.isInteger(projet.id)) return null;
    return { id: projet.id, efface_le: b.efface_le || null };
  }

  /* L'album s'ouvre SEUL au chargement d'une page (décision E du 2026-11-02) : dans son
     propre bac à sable, sous une identité, tant que l'album n'a pas été vu — un parcours
     choisi, ou « Ne plus afficher » coché. Fermer sans cocher ne vaut pas renoncement :
     l'album revient au chargement suivant (le contrat écrit le 2026-08-27, confirmé par
     Hugo le 2026-11-03), sur les six surfaces. */
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

  /* ── Le guide, étape par étape ─────────────────────────────────────────────────────
     Ce qui compte comme une étape FAITE est écrit en tête de ce module. `d` porte ce qu'on
     a lu : `{ regions, releves, album, vues }` — les régions et les relevés de la planche
     du parcours, la ligne de son album dans `GET /api/albums`, les étapes vues (« corpus »,
     quand la fiche de l'album s'est ouverte, et les étapes dites que le guide a montrées).
     Une donnée absente vaut « pas encore » : rien ne se marque fait sur ce qu'on n'a pas
     lu. */
  const TYPES_TEXTE = ["bulle", "cartouche", "texte"];
  const aLaMain = (r) => !!r && r.source === "manuel";
  const texteDe = (r) => String((r && r.ocr_texte) || "").trim();

  function liste(x) { return Array.isArray(x) ? x : []; }

  function faite(e, d, parcours) {
    if (!e) return false;
    const D = d || {}, regions = liste(D.regions), vues = liste(D.vues);
    switch (e.k) {
      case "corpus": return vues.includes("corpus");
      case "decrire": return !!(D.album && String(D.album.source_numerisation || "").trim());
      case "preremplir":
        return regions.some((r) => r && r.activite_id != null)
          || regions.some((r) => r && TYPES_TEXTE.includes(r.type) && !aLaMain(r)
                          && !r.touche && !!texteDe(r));
      case "tracer":
        return regions.some((r) => aLaMain(r) && r.type === "case")
          && regions.some((r) => aLaMain(r) && r.type === "bulle");
      case "decoupage": return regions.some((r) => !!r && r.source === "corrige");
      case "transcrire": {
        const zones = regions.filter((r) => r && TYPES_TEXTE.includes(r.type));
        if (!zones.some((r) => !!texteDe(r) && !!r.touche)) return false;
        return parcours !== "complet" || zones.every((r) => !!texteDe(r));
      }
      case "annoter": return liste(D.releves).length > 0;
      default: return !!e.dite && vues.includes(e.k);
    }
  }

  /* Les phrases que Hugo a écrites pour une étape qui avance (maquette du 2026-11-02) :
     « Tracer une zone » dit ce qui reste à tracer, « Corriger » ce qu'on peut encore faire
     une fois le cadre repris. La première suppose le jeu de la maquette — la dernière
     rangée découpée, sa case du milieu retirée — : elle ne se dit que si le jeu a posé des
     régions sur la planche ; sans elles, la phrase de l'étape. */
  const PHRASES = {
    tracerJeu: "Seule la dernière rangée de cette planche est découpée, et sa case du milieu "
      + "n'a pas de cadre. Sur le fond de la planche, glissez pour la tracer.",
    tracerBulle: "Sa bulle non plus. Maintenez Maj et glissez autour d'elle : tracé dans une "
      + "case, un cadre devient une bulle. La molette rapproche la planche.",
    tracerFait: "Le type se change à droite : case, bulle, personnage, texte, cartouche. Un "
      + "détail d'image se trace dans la page Annotation.",
    decoupageFait: "Un cadre sélectionné se déplace en le glissant. Ses huit poignées le "
      + "redimensionnent, et Suppr le retire.",
  };

  function phraseGuide(e, vue, m, d, parcours) {
    if (!e) return "";
    const regions = liste(d && d.regions);
    if (e.k === "tracer") {
      if (faite(e, d, parcours)) return typo(PHRASES.tracerFait);
      if (regions.some((r) => aLaMain(r) && r.type === "case")) return typo(PHRASES.tracerBulle);
      if (regions.some((r) => !!r && r.source === "jeu")) return typo(PHRASES.tracerJeu);
    }
    if (e.k === "decoupage" && faite(e, d, parcours)) return typo(PHRASES.decoupageFait);
    return phraseEtape(e, vue, m);
  }

  /* Le bouton principal du guide : « Suivant → » quand l'étape est faite, dite, ou
     optionnelle ici ; « Passer → » sinon ; « Terminer » à la dernière (la maquette). */
  function boutonGuide(e, d, m, parcours, derniere) {
    if (derniere) return { texte: "Terminer", principal: true };
    const avance = faite(e, d, parcours) || !!(e && e.dite)
      || marqueEtape(e, m) === "optionnel ici";
    return { texte: avance ? "Suivant →" : "Passer →", principal: avance };
  }

  /* « Corriger » : l'Atelier cadre seul (Hugo, 2026-11-02). En entrant dans l'étape, la
     planche se rapproche de la bulle à corriger ; elle revient à la planche entière en
     sortant. La bulle : la PLUS PETITE de celles que le jeu ou un moteur a posées et que
     personne n'a encore reprises — le défaut du jeu est un cadre trop petit —, `null` s'il
     n'y en a pas (rien à cadrer). */
  function bulleACorriger(regions) {
    const c = liste(regions).filter((r) => r && r.type === "bulle" && r.w > 0 && r.h > 0
                                     && !aLaMain(r) && r.source !== "corrige");
    if (!c.length) return null;
    return c.reduce((a, b) => (b.w * b.h < a.w * a.h
      || (b.w * b.h === a.w * a.h && b.id < a.id) ? b : a));
  }

  /* Le cadre autour de la bulle, en pixels master : trois fois sa taille, et jamais moins
     d'un quart de la largeur ni d'un huitième de la hauteur de la planche, pour qu'on la
     voie dans sa case ; centré sur elle, ramené dans la planche. */
  function cadreAutour(r, W, H) {
    if (!r || !(W > 0) || !(H > 0)) return null;
    const w = Math.min(W, Math.max(3 * r.w, W / 4)), h = Math.min(H, Math.max(3 * r.h, H / 8));
    const x = Math.max(0, Math.min(W - w, r.x + r.w / 2 - w / 2));
    const y = Math.max(0, Math.min(H - h, r.y + r.h / 2 - h / 2));
    return { x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h) };
  }

  /* La vue de l'Atelier qui montre ce cadre au milieu de la scène : `{ zoom, tx, ty }` —
     le zoom porte sur le dérivé (`webScale` = sa largeur / la largeur master) —, bornée
     comme le zoom de l'Atelier. */
  function vueCadree(cadre, scene, webScale, zoomMax) {
    if (!cadre || !scene || !(scene.w > 0) || !(scene.h > 0) || !(webScale > 0)) return null;
    const z = Math.min(zoomMax || 8, Math.max(0.02, Math.min(scene.w / (cadre.w * webScale),
                                                             scene.h / (cadre.h * webScale))));
    return { zoom: z,
             tx: scene.w / 2 - (cadre.x + cadre.w / 2) * webScale * z,
             ty: scene.h / 2 - (cadre.y + cadre.h / 2) * webScale * z };
  }

  /* Le guide traverse les pages, comme la visite : qu'il est ouvert, et les étapes vues,
     vivent dans le stockage de SESSION, sous le login et le bac à sable qui l'ont ouvert.
     Un autre onglet, ou le lendemain, le rouvre par « Par où commencer ». */
  const CLE_GUIDE = "bd-wizard-guide";
  const VUES = ETAPES.filter((e) => e.dite || e.k === "corpus").map((e) => e.k);

  function guideNeuf() { return { actif: false, vues: [] }; }

  function normaliserGuide(g) {
    if (!g || typeof g !== "object") return guideNeuf();
    const vues = liste(g.vues).filter((k, i, t) => VUES.includes(k) && t.indexOf(k) === i);
    return { actif: g.actif === true, vues };
  }

  function lireGuide(login, bac, depuis) {
    if (!login || !bac || !Number.isInteger(bac.id)) return guideNeuf();
    const s = depuis === undefined ? stockageSession() : depuis;
    try {
      const g = s ? JSON.parse(s.getItem(CLE_GUIDE) || "null") : null;
      if (!g || g.login !== login || !memeBac(g, bac)) return guideNeuf();
      return normaliserGuide(g);
    } catch (e) { return guideNeuf(); }
  }

  function retenirGuide(login, bac, guide, dans) {
    if (!login || !bac || !Number.isInteger(bac.id)) return false;
    const s = dans === undefined ? stockageSession() : dans;
    try {
      if (!s) return false;
      const n = normaliserGuide(guide);
      s.setItem(CLE_GUIDE, JSON.stringify({ login, bac: bac.id, efface_le: bac.efface_le || null,
                                            actif: n.actif, vues: n.vues }));
      return true;
    } catch (e) { return false; }
  }

  /* Une étape vue, ajoutée sans doublon — un nouvel objet. */
  function marquerVue(guide, k) {
    const n = normaliserGuide(guide);
    return normaliserGuide({ actif: n.actif, vues: n.vues.concat([k]) });
  }

  /* Le guide s'ouvre sur la page de son étape : sa surface, et l'album et la planche que
     son adresse nomme (`recherche` : la chaîne de l'adresse où l'on est). Le mode n'en est
     pas : un mode changé à la main ne fait pas disparaître le guide. */
  function etapeIci(e, chemin, recherche, vue) {
    const c = String(chemin || "").replace(/\/+$/, "") || "/";
    if (!e || e.surface !== c) return false;
    const voulu = new URLSearchParams(adresseEtape(e, vue).split("?")[1] || "");
    const ici = new URLSearchParams(recherche || "");
    return ["album", "planche"].every((k) => !voulu.has(k) || ici.get(k) === voulu.get(k));
  }

  /* Les marques que les étapes nomment, `[{ etape, surface, marque }]` : le test vérifie
     que la visite les nomme aussi, sur la même surface — une marque n'existe que pour elle,
     et c'est sa liste que `tests/test_wizard_marques.py` confronte aux gabarits. */
  /* Les marques que les FOYERS nomment, `[{ etape, surface, marque }]` (sans `@album` ni
     `@bulle`, que l'écran résout) : `tests/test_wizard_marques.py` exige que chacune soit
     posée sur la surface de son étape. */
  function marquesDesFoyers() {
    const out = [];
    ETAPES.forEach((e) => foyer(e).filter((m) => m[0] !== "@").forEach((m) => out.push(
      { etape: e.k, surface: e.surface, marque: m })));
    return out;
  }

  function marquesDesEtapes() {
    const out = [];
    ETAPES.forEach((e) => liste(e.zones).forEach((m) => out.push(
      { etape: e.k, surface: e.surface, marque: m })));
    return out;
  }

  return { CLE, PAGES, FIN, TITRE_ALBUM, TITRE_CARTE, ETAPES, RAPIDE, PARCOURS, VISITE,
           typo, moteurs, textePage, etapes, albumDuParcours, phraseEtape, marqueEtape,
           adresseEtape, marques, neuf, lireSouvenir, retenirSouvenir, bacASoi, ouvreSeul,
           choisirParcours, allerA, neJamaisAfficher,
           CLE_VISITE, tempsDe, position, suivant, precedent, estFin, compteVisite, cote,
           reperes, phrasePage, bacDuProjet, tempsVisibles, pageDeLaSurface, adresseVisite, retenirVisite, lireVisite,
           oublierVisite, marquePage,
           faite, phraseGuide, boutonGuide, bulleACorriger, cadreAutour, vueCadree, PHRASES,
           CLE_GUIDE, guideNeuf, lireGuide, retenirGuide, marquerVue, etapeIci,
           marquesDesEtapes, FOYERS, foyer, placerFenetre, recouvre, zoneLibre, marquesDesFoyers };
});
