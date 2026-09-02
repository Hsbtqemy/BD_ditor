// L'inventaire de CE dépôt. Rien d'autre : pas de grammaire de fiche, pas de réglage
// de lecture. Ce que l'outil ne peut pas deviner — où sont les fichiers, comment
// s'appellent les branches — et rien de plus.
//
// Le fichier est FACULTATIF : sans lui on garde les chantiers, les passes et le
// contrôleur, et on perd les masses par aire, la veille à seuil et les liens
// code → document.

export default {
  // Refs d'intégration. `origin/main` D'ABORD, exprès : `main` est un ancêtre de
  // `dev`, donc tout ce qui est sur `main` est aussi sur `dev`. Le premier match
  // l'emportant, mettre `dev` en tête ferait répondre « dev » y compris pour du
  // travail publié — la distinction serait perdue. Dans cet ordre, une fiche dit
  // `origin/main` quand elle est publiée, `origin/dev` quand elle n'est que poussée,
  // et la branche courante quand elle n'est nulle part.
  //
  // État au 2026-08-27 : `main` est 146 commits derrière `dev`. Presque tout le
  // dépôt vit donc « hors de origin/main », et c'est exact — pas un défaut de réglage.
  refs: ["origin/main", "origin/dev"],

  // Une aire = un préfixe de chemin ; le PREMIER qui matche l'emporte, d'où les
  // fichiers nommés avant les dossiers qui les contiennent. Plusieurs préfixes
  // peuvent porter le même nom d'aire : ils s'additionnent.
  aires: [
    ["front/visionneuse", "static/viewer.js"],
    ["front/exploration", "static/exploration.js"],
    ["front/style",       "static/style.css"],
    ["front/autres",      "static/"],
    ["gabarits",          "templates/"],
    ["api",               "main.py"],
    ["api",               "socle.py"],
    ["api",               "routes/"],
    ["données",           "database.py"],
    ["noyau",             "journal.py"],
    ["noyau",             "undo.py"],
    ["noyau",             "accord.py"],
    ["noyau",             "accord_inter.py"],
    ["noyau",             "lexique_import.py"],
    ["noyau",             "config.py"],
    ["pipeline",          "pipeline/"],
    ["outils",            "tools/"],
    ["tests",             "tests/"],
    ["déploiement",       "deploy/"],
    ["docs",              "docs/"],
    ["docs",              "AUDIT.md"],
    ["dossier",           "pilotage/"]
  ],

  // Le seul chiffre qui ait une limite réelle ici, et le dépôt n'a aucune étape de
  // build pour amortir un gros fichier : on l'ouvre, on le lit. `chantier` nomme la
  // fiche où la décision se prend quand le seuil approche ; sans elle le chiffre
  // serait un cul-de-sac — on verrait qu'il monte, pas où agir.
  //
  // Le seuil A ÉTÉ FRANCHI, et la décision est prise (ARCH-1, 2026-09-02) : découpage
  // par domaine, `routes/` + `socle.py`, par étapes. `main.py` était à 4 483 lignes ;
  // la veille continue de le surveiller LUI, parce que c'est là que revient le code
  // qu'on ne sait pas où mettre.
  veille: { fichier: "main.py", seuil: 3200, jours: 90, chantier: "ARCH-1" },

  // `dossier` sert à distinguer un commit de cadrage d'un commit de code : sans lui,
  // une note de conception compterait comme du code et démentirait un `à venir` qui
  // était juste. C'est la seule moitié utile ici.
  //
  // `sources` (liens code → document) est déclaré VIDE, et c'est une décision, pas un
  // oubli. La règle est « première source qui cite un code l'emporte » : elle suppose
  // qu'un document POSSÈDE les codes qu'il cite. Dans ce dépôt, les notes de conception
  // se citent constamment entre elles — `ANN-4` apparaît dans quatre documents — si
  // bien que le gagnant est décidé par l'ordre alphabétique du dossier, pas par la
  // pertinence. Mesuré le 2026-08-27 avec un motif large : `ANN-4` renvoyait à
  // `export-metadonnees.md` plutôt qu'à `relecture.md`, `ANN-2` à `domaines.md`
  // plutôt qu'à `personnages-et-attribution.md`, et un faux code `BY-4` était fabriqué
  // à partir de `CC-BY-4` dans la ligne de licence du crosswalk. Un lien qui envoie
  // vers le mauvais document est pire que pas de lien : à l'écran, chaque fiche
  // renvoie alors vers elle-même, ce qui est exact.
  documentation: {
    dossier: "docs",
    sources: []
  }
};
