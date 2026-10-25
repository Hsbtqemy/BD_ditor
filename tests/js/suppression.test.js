/* Tests unitaires de « supprimer a deux réponses » (static/lib/suppression.js, COL-3,
   tranche 2). Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Ce module choisit les MOTS de ce que le serveur a décidé : ce que devient le travail
   quand on supprime un album d'une collection, ce que fait « Supprimer définitivement », ce
   que dit le fonds. Ces mots sont la raison d'être d'une confirmation — une phrase fausse
   ici fait faire un geste qu'on n'aurait pas fait. Que les deux écrans s'en servent se joue
   dans un navigateur (tests/test_e2e_collections.py, tests/test_e2e_fonds.py). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

test("le module se charge sans document, sans fenêtre et sans adresse", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(typeof window, "undefined");
  assert.equal(typeof location, "undefined");
  const chemin = require.resolve("../../static/lib/suppression.js");
  delete require.cache[chemin];
  const api = require(chemin);
  assert.equal(typeof api.retrait, "function");
});

const S = require("../../static/lib/suppression.js");

const INC = { id: 2, nom: "Incubateur" }, ARC = { id: 3, nom: "Archives" },
      PRI = { id: 1, nom: "Principale" };

/* ── Supprimer de la collection ─────────────────────────────────────────────────────── */

// [cas, entrée, reste, perdEcriture, perdVue, confirmer, morceaux attendus, morceaux exclus]
const RETRAITS = [
  ["sa dernière collection, compte ordinaire",
   { siennes: [INC], ecrites: [2], collectionId: 2, partage: false, total: false },
   "fonds", true, true, true,
   ["gardée au fonds", "Un administrateur peut la rendre", "ne le verrez plus"],
   ["depuis l'Administration", "continuerez de le lire"]],
  ["sa dernière collection, portée totale",
   { siennes: [INC], ecrites: [2], collectionId: 2, partage: false, total: true },
   "fonds", false, false, true,
   ["gardée au fonds", "Vous pourrez la rendre depuis l'Administration"],
   ["Un administrateur", "ne le verrez plus", "n'y écrirez plus"]],
  ["il vit aussi là où l'on ne lit pas : rien ne part au fonds",
   { siennes: [INC], ecrites: [2], collectionId: 2, partage: true, total: false },
   "cache", true, true, true,
   ["une collection que vous ne lisez pas", "ne le verrez plus"],
   ["fonds", "Principale"]],
  ["on écrit des deux côtés : rien à perdre, rien à confirmer",
   { siennes: [ARC, INC], ecrites: [2, 3], collectionId: 3, partage: false, total: false },
   "lu", false, false, false,
   ["« Incubateur », où rien ne change"], ["fonds", "écrirez", "verrez"]],
  ["on écrit d'un côté, on lit de l'autre : on perd l'écriture, pas la vue",
   { siennes: [ARC, INC], ecrites: [2], collectionId: 2, partage: true, total: false },
   "lu", true, false, true,
   ["« Archives »", "continuerez de le lire", "n'y écrirez plus"],
   ["ne le verrez plus", "fonds"]],
  ["la collection qu'on ne fait que lire : on ne perd rien",
   { siennes: [ARC, INC], ecrites: [2], collectionId: 3, partage: false, total: false },
   "lu", false, false, false, ["« Incubateur »"], ["écrirez", "fonds"]],
  ["trois collections lues : toutes nommées, dans l'ordre",
   { siennes: [ARC, INC, PRI], ecrites: [1, 2, 3], collectionId: 1, partage: false,
     total: true },
   "lu", false, false, false, ["« Archives » et « Incubateur », où"], ["fonds"]],
];

for (const [cas, entree, reste, perdEcr, perdVue, confirmer, dans, horsDe] of RETRAITS) {
  test(`retrait — ${cas}`, () => {
    const r = S.retrait(entree);
    assert.equal(r.reste, reste);
    assert.equal(r.perdEcriture, perdEcr);
    assert.equal(r.perdVue, perdVue);
    assert.equal(r.confirmer, confirmer);
    for (const m of dans) assert.ok(r.texte.includes(m), `« ${m} » absent de : ${r.texte}`);
    for (const m of horsDe) assert.ok(!r.texte.includes(m), `« ${m} » présent dans : ${r.texte}`);
  });
}

test("retrait — n'invente jamais le nom d'une collection qu'on ne lit pas", () => {
  const r = S.retrait({ siennes: [INC], ecrites: [2], collectionId: 2, partage: true });
  assert.deepEqual(r.autres, []);
  assert.ok(!/«/.test(r.texte), r.texte);
});

/* ── Supprimer définitivement ───────────────────────────────────────────────────────── */

const DEMANDE = { id: 9, demandeur: "sam", demandeur_nom: "Sam Diallo",
                  date_creation: "2026-10-14 12:00:00" };

const DEFINITIFS = [
  ["le créateur seul efface", { destructible: true, demande: null, pouvoir: "createur" },
   "direct", "Supprimer définitivement", ["cette copie, ses images", "Irréversible"]],
  ["la portée totale efface partout", { destructible: true, demande: null, pouvoir: "admin" },
   "direct", "Supprimer définitivement", ["cette copie, ses images et le travail", "Irréversible"]],
  ["la portée totale efface même si une demande attend",
   { destructible: true, demande: DEMANDE, total: true },
   "direct", "Supprimer définitivement", ["Efface tout de suite cette copie"]],
  ["sinon on demande", { destructible: false, demande: null, total: false },
   "demande", "Envoyer la demande", ["la demande part à un administrateur",
                                     "Rien n'est effacé d'ici là"]],
  ["une demande attend déjà : rien à envoyer, et on dit qui",
   { destructible: false, demande: DEMANDE, total: false },
   "attente", "", ["déjà demandée par Sam Diallo, le 14/10/2026", "un administrateur y répondra"]],
  ["une demande attend, sans nom rendu : on ne suppose rien",
   { destructible: false, demande: { id: 9, date_creation: "2026-10-14 12:00:00" } },
   "attente", "", ["Sa suppression est déjà demandée, le 14/10/2026"]],
  ["sa propre demande se dit « vous »",
   { destructible: false, demande: DEMANDE, moi: "sam" },
   "attente", "", ["déjà demandée par vous"]],
];

for (const [cas, entree, mode, bouton, dans] of DEFINITIFS) {
  test(`définitif — ${cas}`, () => {
    const r = S.definitif(entree);
    assert.equal(r.mode, mode);
    assert.equal(r.bouton, bouton);
    for (const m of dans) assert.ok(r.texte.includes(m), `« ${m} » absent de : ${r.texte}`);
  });
}

test("la pastille d'une demande : le nom lisible, sinon le login, sinon rien", () => {
  assert.equal(S.pastille(null), "");
  assert.equal(S.pastille(DEMANDE), "suppression demandée par Sam Diallo");
  assert.equal(S.pastille({ demandeur: "sam", demandeur_nom: null }), "suppression demandée par sam");
  assert.equal(S.pastille({ id: 3 }), "suppression demandée");
  assert.equal(S.pastille(DEMANDE, "sam"), "suppression demandée par vous");
  assert.equal(S.pastille(DEMANDE, "lia"), "suppression demandée par Sam Diallo");
});

test("« Supprimer… » ne s'offre qu'à qui écrit, et jamais sur une copie gardée", () => {
  assert.equal(S.offrir({ ecrivable: true }), true);
  assert.equal(S.offrir({ ecrivable: false, destructible: true }), false);
  assert.equal(S.offrir({ ecrivable: true, au_fonds: true }), false);
  assert.equal(S.offrir(null), false);
});

test("ce qu'on lit une fois le geste fait", () => {
  assert.equal(S.apresRetrait("Seul", "Incubateur", "fonds"),
               "« Seul » n'est plus dans « Incubateur ». Sa copie de travail est gardée au fonds.");
  assert.ok(S.apresRetrait("Triple", "Archives", "lu").endsWith("Le travail continue ailleurs."));
  assert.ok(S.apresDefinitif("Seul", "direct").startsWith("« Seul » est supprimé définitivement"));
  assert.ok(S.apresDefinitif("Seul", "demande").startsWith("Votre demande est partie"));
});

/* ── Le fonds ───────────────────────────────────────────────────────────────────────── */

test("l'origine d'un document dit ce qui est écrit, et n'invente pas le reste", () => {
  assert.equal(S.origine({ importe_par: "lea", importe_par_nom: "Léa Roux",
                           importe_le: "2026-10-14 12:00:00", projet_origine_nom: "Séminaire" }),
               "Importé par Léa Roux (lea), le 14/10/2026, dans « Séminaire ».");
  assert.equal(S.origine({ importe_par: "lea", importe_le: "2026-10-14" }),
               "Importé par lea, le 14/10/2026.");
  assert.equal(S.origine({ importe_par: null, importe_le: "2026-01-02 12:00:00",
                           projet_origine_nom: "Principal" }),
               "Importé le 02/01/2026, dans « Principal » ; qui l'a importé n'est pas écrit.");
  assert.equal(S.origine({ importe_par: null, importe_le: null }),
               "Ni la date ni l'auteur de l'import ne sont écrits.");
  assert.equal(S.origine({ importe_par: null, importe_le: null, projet_origine_nom: "P" }),
               "Ni la date ni l'auteur de l'import ne sont écrits ; projet d'origine « P ».");
});

test("les emplois : une ligne par copie rangée, aucune pour une copie gardée", () => {
  const doc = { copies: [
    { titre: "T", projet_nom: "Séminaire", collections: [{ id: 1, nom: "A" }, { id: 2, nom: "B" }] },
    { titre: "T", projet_nom: "Autre", collections: [] },
  ] };
  assert.deepEqual(S.emplois(doc), ["Séminaire : A, B"]);
  assert.deepEqual(S.emplois({ copies: [] }), []);
  assert.equal(S.titreDocument(doc), "T");
  assert.equal(S.titreDocument({ id: 4, copies: [] }), "Document 4, sans copie");
});

test("la phrase d'une demande, pour un document et pour un projet", () => {
  assert.equal(S.texteDemande({ genre: S.GENRE_DOCUMENT, demandeur: "sam", demandeur_nom: "Sam",
                                documents: [{ document_id: 3, titre: "Doublon" }] }),
               "Sam demande la suppression définitive de « Doublon »");
  assert.equal(S.texteDemande({ genre: S.GENRE_PROJET, demandeur: "rui", projet_id: 4,
                                projet_nom: "Séminaire" }),
               "rui demande la suppression du projet « Séminaire »");
  assert.equal(S.contexteDemande({ genre: S.GENRE_DOCUMENT, date_creation: "2026-10-14 1",
                                   projet_nom: "P", refus_anterieurs: 2 }),
               "le 14/10/2026 · depuis « P » · déjà refusée 2 fois");
  assert.equal(S.contexteDemande({ genre: S.GENRE_PROJET, date_creation: "2026-10-14",
                                   projet_nom: "P", refus_anterieurs: 1 }),
               "le 14/10/2026 · déjà refusée une fois");
});

test("une entrée de documents ou un rejoindre ne se dit jamais suppression (COL-3, 3a)", () => {
  const entree = { genre: "entree_documents", demandeur: "resp", collection_nom: "Base",
                   documents: [{ document_id: 1, titre: "Lotus" }] };
  const rejoindre = { genre: "rejoindre", demandeur: "eva", collection_nom: "Y",
                      documents: [{ document_id: 2, titre: "Oreille" }] };
  assert.equal(S.texteDemande(entree), "resp demande l'entrée de « Lotus » dans « Base »");
  assert.equal(S.texteDemande(rejoindre), "eva demande à ranger aussi « Oreille » dans « Y »");
  assert.ok(!S.texteDemande({ genre: "inconnu" }).includes("suppression"));
  assert.equal(S.estUneSuppression(entree), false);
  assert.equal(S.estUneSuppression(rejoindre), false);
  assert.equal(S.estUneSuppression({ genre: S.GENRE_DOCUMENT }), true);
  assert.equal(S.estUneSuppression({ genre: S.GENRE_PROJET }), true);
  assert.equal(S.estUneSuppression(null), false);
});

test("« Rendre à… » ne propose que les collections du projet de la copie", () => {
  const cols = [{ id: 1, nom: "A", projet_id: 1 }, { id: 2, nom: "B", projet_id: 2 },
                { id: 3, nom: "C", projet_id: 1, ecrivable: false }];
  assert.deepEqual(S.rendreA({ projet_id: 1 }, cols).map((c) => c.id), [1]);
  assert.deepEqual(S.rendreA({ projet_id: 2 }, cols).map((c) => c.id), [2]);
  // Importée au fonds, elle n'a jamais eu de projet : toutes, celle où l'on n'écrit pas exceptée.
  assert.deepEqual(S.rendreA({ projet_id: null }, cols).map((c) => c.id), [1, 2]);
});

test("une date illisible se rend telle quelle", () => {
  assert.equal(S.dateLue("hier"), "hier");
  assert.equal(S.dateLue(null), "");
});

/* La base écrit `datetime('now')`, en UTC et sans le dire ; l'écran la rend dans le fuseau
   du NAVIGATEUR. Le fuseau est imposé ici (Node relit `TZ` à chaud ; chaque fichier de
   tests tourne dans son processus), et rendu ensuite. */
test("une date de la base se lit dans le fuseau du navigateur, pas en UTC", () => {
  const avant = process.env.TZ;
  try {
    process.env.TZ = "Europe/Paris";
    assert.equal(S.dateLue("2026-10-14 22:58:00"), "15/10/2026");     // 0 h 58 à Paris
    assert.equal(S.dateLue("2026-10-14 21:59:59"), "14/10/2026");     // 23 h 59 à Paris
    assert.equal(S.dateLue("2026-10-14T22:58:00Z"), "15/10/2026");
    assert.equal(S.dateLue("2026-10-14T22:58:00+00:00"), "15/10/2026");
    assert.equal(S.dateLue("2026-10-14"), "14/10/2026");              // un jour, pas un instant
    process.env.TZ = "America/New_York";
    assert.equal(S.dateLue("2026-10-15 02:30:00"), "14/10/2026");     // 22 h 30 la veille
    process.env.TZ = "UTC";
    assert.equal(S.dateLue("2026-10-14 22:58:00"), "14/10/2026");
    // Partout où l'écran en affiche une : la demande, l'origine d'un document.
    process.env.TZ = "Europe/Paris";
    assert.ok(S.definitif({ destructible: false, demande: { date_creation: "2026-10-14 22:58:00" } })
      .texte.includes("le 15/10/2026"));
    assert.ok(S.contexteDemande({ date_creation: "2026-10-14 22:58:00" }).startsWith("le 15/10/2026"));
    assert.equal(S.origine({ importe_par: "lea", importe_le: "2026-10-14 22:58:00" }),
                 "Importé par lea, le 15/10/2026.");
  } finally {
    if (avant === undefined) delete process.env.TZ; else process.env.TZ = avant;
  }
});

/* La certification d'une demande (Hugo, 2026-10-15) : ses mots, puis ce que l'administrateur
   en lit. */
test("la certification dit ce que la suppression détruit, et pose la question", () => {
  const c = S.CERTIFICATION;
  for (const mot of ["découpage", "transcription", "annotations", "métadonnées",
                     "projet", "collections", "certifier", "pas importantes ?"]) {
    assert.ok(c.texte.includes(mot), mot);
  }
  assert.equal(c.caseACocher, "Je certifie que ces données ne sont pas importantes.");
  assert.ok(c.manque.startsWith("Cochez la certification"));
});

test("« certifié par … le … » se lit pour une demande certifiée, et rien sinon", () => {
  const avant = process.env.TZ;
  try {
    process.env.TZ = "Europe/Paris";
    assert.equal(S.certifiee({ demandeur: "sam", demandeur_nom: "Sam Diallo",
                               certifie_le: "2026-10-14 22:58:00" }),
                 "Certifié par Sam Diallo le 15/10/2026 : ces données ne sont pas importantes.");
    assert.equal(S.certifiee({ demandeur: "sam", certifie_le: "2026-10-14" }),
                 "Certifié par sam le 14/10/2026 : ces données ne sont pas importantes.");
    assert.equal(S.certifiee({ demandeur: "sam", certifie_le: null }), "");
    assert.equal(S.certifiee(null), "");
  } finally {
    if (avant === undefined) delete process.env.TZ; else process.env.TZ = avant;
  }
});

test("le travail des autres : qui, combien de chaque sorte, le dernier", () => {
  const avant = process.env.TZ;
  try {
    process.env.TZ = "Europe/Paris";
    const t = S.travailDesAutres({
      importe_par: "lea", importe_par_nom: "Léa Martin",
      travail_des_autres: [
        { agent: "sam", agent_nom: "Sam Diallo", dernier: "2026-10-14 22:58:00",
          gestes: { annotations: 1, regions: 3 } },
        { agent: "rui", agent_nom: "rui", dernier: "2026-10-01 08:00:00",
          gestes: { token_correction: 2 } },
        { agent: null, agent_nom: null, dernier: null, gestes: { region_attribut: 1 } },
      ] });
    assert.equal(t.origine, "Importé par Léa Martin (lea).");
    assert.deepEqual(t.lignes, [
      "Sam Diallo (sam) : 3 gestes sur des cases ou des bulles, 1 annotation — dernier le 15/10/2026",
      "rui : 2 corrections grammaticales — dernier le 01/10/2026",
      "Auteur non écrit : 1 attribut de case",
    ]);
    assert.equal(t.vide, false);
  } finally {
    if (avant === undefined) delete process.env.TZ; else process.env.TZ = avant;
  }
});

test("un document d'avant le fonds dit ce qu'on sait ; personne d'autre se dit ; rien rendu, rien dit", () => {
  const t = S.travailDesAutres({ importe_par: null, travail_des_autres: [] });
  assert.ok(t.origine.startsWith("Qui a créé cette copie n'est pas écrit"));
  assert.equal(t.vide, true);
  assert.equal(t.texteVide, "Personne d'autre que le demandeur n'y a laissé de geste.");
  assert.equal(S.travailDesAutres({ importe_par: "lea" }), undefined);
  assert.equal(S.travailDesAutres(null), undefined);
});

test("chaque sorte que la règle lit a ses mots ; une sorte inconnue se dit telle quelle", () => {
  for (const sorte of ["regions", "annotations", "bulle_locuteur", "personnage_presence",
                       "region_attribut", "token_correction", "planches", "document"]) {
    assert.ok(S.SORTES[sorte], sorte);
    assert.equal(S.gestes({ [sorte]: 2 }), `2 ${S.SORTES[sorte][1]}`, sorte);
    assert.equal(S.gestes({ [sorte]: 1 }), `1 ${S.SORTES[sorte][0]}`, sorte);
  }
  assert.equal(S.gestes({ neuve: 2 }), "2 neuve");
  assert.equal(S.gestes({ planches: 1, document: 1 }),
               "1 geste sur le document (import, scan, notice), 1 validation de planche");
});

/* Derrière un compte partagé, « personne d'autre » et « certifié par » ne désignent pas une
   personne (relecture croisée) ; et le détail compte des GESTES, défaits compris. */
test("un compte partagé se dit, et le détail dit qu'il compte des gestes", () => {
  const PARTAGE = "compte partagé : plusieurs personnes peuvent avoir travaillé sous ce login";
  const vide = S.travailDesAutres({ importe_par: "atelier", demandeur_collectif: true,
                                    travail_des_autres: [] });
  assert.ok(vide.texteVide.includes(PARTAGE), vide.texteVide);
  const seul = S.travailDesAutres({ importe_par: "lea", demandeur_collectif: false,
                                    travail_des_autres: [] });
  assert.ok(!seul.texteVide.includes("partagé"), seul.texteVide);
  const t = S.travailDesAutres({ importe_par: "lea", travail_des_autres: [
    { agent: "atelier", agent_nom: null, dernier: null, collectif: true, gestes: { regions: 2 } },
    { agent: "sam", agent_nom: null, dernier: null, collectif: false, gestes: { regions: 1 } }] });
  assert.ok(t.lignes[0].endsWith(`(${PARTAGE})`), t.lignes[0]);
  assert.ok(!t.lignes[1].includes("partagé"), t.lignes[1]);
  assert.ok(t.titre.toLowerCase().includes("gestes") && t.titre.includes("défait"), t.titre);
  assert.ok(S.certifiee({ demandeur: "atelier", certifie_le: "2026-10-14",
                          demandeur_collectif: true }).includes(PARTAGE));
  assert.ok(!S.certifiee({ demandeur: "sam", certifie_le: "2026-10-14",
                           demandeur_collectif: false }).includes("partagé"));
});


/* ── COL-3, écran de la 3a — cinq genres, chacun ses mots ─────────────────────────── */

const DEM = (genre, plus) => ({ id: 3, genre, demandeur: "resp", demandeur_nom: "Rémi",
  collection_nom: "Base P", collection_id: 7, projet_nom: "Étude P",
  documents: [{ document_id: 1, titre: "Lotus", reponse: null },
              { document_id: 2, titre: "Oreille", reponse: "acceptee" }], ...plus });

test("chaque genre a son nom, sa classe et ses deux réponses — Détruire n'est qu'à un document", () => {
  const cas = [
    [S.GENRE_DOCUMENT, "Supprimer un document", "document", "Détruire", "Garder"],
    [S.GENRE_PROJET, "Supprimer un projet", "projet", "Supprimer le projet", "Garder"],
    [S.GENRE_ENTREE, "Entrée de documents", "entree", "Accepter", "Refuser"],
    [S.GENRE_REJOINDRE, "Rejoindre un travail", "rejoindre",
     "Accepter : ranger aussi dans « Base P »", "Refuser"],
    [S.GENRE_RENDRE, "Rendre une copie gardée", "rendre", "Rendre à « Base P »",
     "Garder au fonds"],
  ];
  const classes = new Set();
  for (const [genre, libelle, classe, accepter, refuser] of cas) {
    const g = S.genreDemande(DEM(genre));
    assert.deepEqual([g.connu, g.libelle, g.classe, g.accepter, g.refuser],
                     [true, libelle, classe, accepter, refuser], genre);
    classes.add(g.classe);
    if (genre !== S.GENRE_DOCUMENT) {
      assert.ok(!/Détruire/.test(g.accepter + g.refuser), genre);
      if (genre !== S.GENRE_PROJET) assert.notEqual(g.refuser, "Garder", genre);
    }
  }
  assert.equal(classes.size, cas.length, "une couleur de tranche par genre");
});

test("un genre inconnu se lit « Demande », sans aucun bouton", () => {
  const g = S.genreDemande({ genre: "nouveau" });
  assert.deepEqual([g.connu, g.libelle, g.accepter, g.refuser], [false, "Demande", "", ""]);
  assert.equal(S.genreDemande(null).connu, false);
});

test("les réponses globales d'une entrée comptent ce qui attend encore", () => {
  assert.equal(S.toutAccepter(DEM(S.GENRE_ENTREE)), "Tout accepter (1)");
  assert.equal(S.REFUSER_LE_RESTE, "Refuser le reste");
});

test("l'état d'une demande, et celui d'une ligne, pour qui l'a déposée", () => {
  assert.deepEqual(S.etatDemande({ reponse: null }), { code: "attente", libelle: "en attente" });
  assert.equal(S.etatDemande({ reponse: "acceptee" }).libelle, "acceptée");
  assert.equal(S.etatDemande({ reponse: "refusee" }).libelle, "refusée");
  assert.equal(S.etatDemande({ reponse: "partielle" }).libelle, "acceptée en partie");
  const d = DEM(S.GENRE_ENTREE);
  assert.equal(S.etatLigne(d.documents[1], d).libelle, "entré dans « Base P »");
  assert.equal(S.etatLigne({ reponse: "refusee" }, d).libelle, "refusé");
  assert.equal(S.etatLigne(d.documents[0], d).libelle, "en attente");
});

test("la phrase d'un retour nomme la copie et sa collection d'arrivée, jamais une suppression", () => {
  const t = S.texteDemande(DEM(S.GENRE_RENDRE, { documents: [{ document_id: 1, titre: "Lotus" }] }));
  assert.equal(t, "Rémi demande à rendre « Lotus » à « Base P »");
  for (const genre of [S.GENRE_ENTREE, S.GENRE_REJOINDRE, S.GENRE_RENDRE]) {
    assert.ok(!/suppression/.test(S.texteDemande(DEM(genre))), genre);
    assert.ok(S.explicationDemande(DEM(genre)).length > 0, genre);
  }
  assert.equal(S.explicationDemande(DEM(S.GENRE_DOCUMENT)), "");
});

test("une copie qui a une sœur : ses images restent, sans dire où", () => {
  const r = S.definitif({ destructible: true, total: false, soeur: true });
  assert.ok(r.texte.includes(S.IMAGES_RESTENT), r.texte);
  assert.ok(!r.texte.includes("ses images et"), r.texte);
  assert.equal(S.IMAGES_RESTENT, "Ses images restent : une autre copie de ce document les emploie.");
  assert.ok(S.confirmationDetruire("Lotus", true).includes(S.IMAGES_RESTENT));
  assert.ok(S.confirmationDetruire("Lotus").includes("cette copie"));
  assert.ok(!S.confirmationDetruire("Lotus").includes("tous les projets"));
});

test("le travail des autres dit qui a créé CETTE copie", () => {
  const t = S.travailDesAutres({ creee_par: "sam", creee_par_nom: "Sam", importe_par: "lea",
                                 travail_des_autres: [] });
  assert.equal(t.origine, "Copie créée par Sam (sam) ; document importé par lea.");
});

test("un retour dit d'où la copie était sortie, quand le serveur le sait", () => {
  const avec = S.explicationDemande(DEM(S.GENRE_RENDRE, { sortie_de: "Lot fermé" }));
  assert.ok(avec.includes("Elle était sortie de « Lot fermé »"), avec);
  assert.ok(avec.includes("ouvre son travail"), avec);
  const meme = S.explicationDemande(DEM(S.GENRE_RENDRE, { sortie_de: "Base P" }));
  assert.ok(!meme.includes("ouvre son travail"), meme);
  assert.ok(!S.explicationDemande(DEM(S.GENRE_RENDRE)).includes("sortie"));
});

test("une copie qui a une sœur : la demande le dit aussi, sans dire où", () => {
  const r = S.definitif({ destructible: false, demande: null, total: false, soeur: true });
  assert.equal(r.mode, "demande");
  assert.ok(r.texte.includes(S.IMAGES_RESTENT), r.texte);
  assert.ok(r.texte.endsWith("Rien n'est effacé d'ici là."), r.texte);
  const sans = S.definitif({ destructible: false, demande: null, total: false });
  assert.ok(!sans.texte.includes(S.IMAGES_RESTENT), sans.texte);
});

test("retrait — on écrit des deux côtés sans les tenir : un aller simple, qui se confirme", () => {
  // Relecture croisée de t3a-c4, défaut 1 : D4 stricte — recocher est une DEMANDE.
  const base = { siennes: [ARC, INC], ecrites: [2, 3], collectionId: 3, partage: false,
                 total: false };
  const dem = S.retrait({ ...base, recocher: "demande" });
  assert.equal(dem.confirmer, true);
  assert.ok(dem.texte.includes(S.RECOCHER_SUR_DEMANDE), dem.texte);
  const soi = S.retrait({ ...base, recocher: "soi" });
  assert.equal(soi.confirmer, false, "qui tient tout le refait seul : rien à confirmer");
  assert.ok(!soi.texte.includes("sur demande"), soi.texte);
  const tout = S.retrait({ ...base, total: true, recocher: "demande" });
  assert.equal(tout.confirmer, false, "la portée totale range directement");
  // La dernière collection : la phrase du fonds, pas celle de la demande.
  const fonds = S.retrait({ siennes: [INC], ecrites: [2], collectionId: 2, partage: false,
                            total: false, recocher: "demande" });
  assert.ok(!fonds.texte.includes("sur demande"), fonds.texte);
});

test("après « Supprimer définitivement » d'une copie qui a une sœur : ses images restent", () => {
  // Le panneau venait de dire « Ses images restent » ; le message de fin disait « avec ses
  // images ». Il suit maintenant la même sœur que le panneau.
  const S = require("../../static/lib/suppression.js");
  assert.equal(S.apresDefinitif("Lotus", "direct", true),
    "« Lotus » : cette copie est supprimée définitivement, avec le travail fait dessus. "
    + S.IMAGES_RESTENT);
  assert.ok(!S.apresDefinitif("Lotus", "direct", true).includes("avec ses images"));
  assert.equal(S.apresDefinitif("Lotus", "direct", false),
    "« Lotus » est supprimé définitivement, avec ses images et le travail fait dessus.");
  assert.equal(S.apresDefinitif("Lotus", "direct"), S.apresDefinitif("Lotus", "direct", false));
  assert.ok(S.apresDefinitif("Lotus", "demande", true).startsWith("Votre demande est partie"));
});

/* ── COL-3, écran de la 3b — « Supprimer… » suit le chemin réel (Hugo, 2026-10-21/25) ── */

test("effacer sans demander dit PAR QUEL CHEMIN, et jamais « vous l'avez créée » à qui ne l'a pas créée", () => {
  const cas = [
    ["responsable", "Vous êtes responsable du projet : rien à demander."],
    ["proprietaire", "Vous tenez toutes ses collections : rien à demander."],
    ["createur", "Vous avez créé cette copie, et personne d'autre n'y a travaillé : rien à demander."],
    ["admin", "Vous administrez l'instance : rien à demander."],
    ["bac", "C'est votre bac à sable : rien à demander."],
  ];
  for (const [pouvoir, raison] of cas) {
    const r = S.definitif({ destructible: true, demande: null, pouvoir });
    assert.equal(r.mode, "direct", pouvoir);
    assert.equal(r.raison, raison, pouvoir);
    // La phrase d'avant disait au propriétaire et au responsable qu'ils l'avaient créée.
    assert.ok(!/l'avez créée/.test(r.texte), `${pouvoir} : ${r.texte}`);
    if (pouvoir !== "createur") assert.ok(!/créé/.test(r.texte + r.raison), pouvoir);
  }
  // Sans chemin connu, rien n'est supposé.
  assert.equal(S.definitif({ destructible: true, demande: null }).raison, "");
});

test("la DERNIÈRE copie se demande — et le panneau dit pourquoi à qui aurait pu l'effacer", () => {
  const r = S.definitif({ destructible: false, demande: null, derniere: true, pouvoir: "responsable" });
  assert.equal(r.mode, "demande");
  assert.equal(r.derniere, true);
  assert.equal(r.bouton, "Envoyer la demande");
  for (const m of ["C'est la dernière copie de ce document", "sortir du fonds, images comprises",
                   "Vous êtes responsable du projet, mais c'est un administrateur qui décide",
                   "Rien n'est effacé d'ici là"]) {
    assert.ok(r.texte.includes(m), `« ${m} » absent de : ${r.texte}`);
  }
  // Sans chemin (ni propriétaire, ni responsable, ni créateur seul) : la demande ordinaire.
  const sans = S.definitif({ destructible: false, demande: null, derniere: true, pouvoir: null });
  assert.notEqual(sans.derniere, true);
  assert.ok(sans.texte.startsWith("D'autres s'en servent"), sans.texte);
  // Un chemin sans la dernière copie (un compte partagé, que la règle arrête) : la demande
  // ordinaire — jamais « dernière copie » d'un document qui en a d'autres.
  const pasDerniere = S.definitif({ destructible: false, demande: null, derniere: false,
                                    pouvoir: "responsable" });
  assert.ok(!/dernière copie/.test(pasDerniere.texte), pasDerniere.texte);
  assert.notEqual(pasDerniere.derniere, true);
  // Une demande qui attend l'emporte : rien ne se redépose.
  assert.equal(S.definitif({ destructible: false, demande: DEMANDE, derniere: true,
                             pouvoir: "responsable" }).mode, "attente");
  // Une sœur dans un projet isolé : les images restent, la phrase ne dit pas « images comprises ».
  const soeur = S.definitif({ destructible: false, demande: null, derniere: true,
                              pouvoir: "proprietaire", soeur: true });
  assert.ok(!soeur.texte.includes("images comprises"), soeur.texte);
});

test("les trois genres de la 3b : leurs noms, leurs tranches, leurs réponses", () => {
  const am = S.genreDemande(DEM(S.GENRE_AMORCER, { cran: "transcription" }));
  assert.deepEqual([am.connu, am.libelle, am.classe, am.accepter, am.refuser],
                   [true, "En partir d'un travail", "amorcer", "Accepter : copier dans « Base P »",
                    "Refuser"]);
  const e7 = S.genreDemande(DEM(S.GENRE_AMORCER_ENTRE_PROJETS, { cran: "annotations" }));
  assert.equal(e7.classe, "amorcer", "en partir : une seule tranche, verte, pour les deux genres");
  assert.equal(e7.libelle, "En partir d'un travail");
  const rp = S.genreDemande(DEM(S.GENRE_REPARTIR, { cran: "decoupage" }));
  assert.deepEqual([rp.libelle, rp.classe, rp.accepter, rp.refuser],
                   ["Repartir de zéro", "repartir", "Repartir du découpage", "Garder"]);
  for (const g of [am, e7, rp]) assert.ok(!/Détruire/.test(g.accepter + g.refuser));
});

test("une demande d'en partir ou de repartir ne se dit jamais suppression, et explique sa réponse", () => {
  for (const genre of [S.GENRE_AMORCER, S.GENRE_AMORCER_ENTRE_PROJETS, S.GENRE_REPARTIR]) {
    const d = DEM(genre, { cran: "transcription" });
    assert.ok(!/suppression/.test(S.texteDemande(d)), genre);
    assert.ok(S.explicationDemande(d).length > 0, genre);
  }
  assert.equal(S.texteDemande(DEM(S.GENRE_AMORCER, { cran: "transcription",
                                                     documents: [{ titre: "Lotus" }] })),
               "Rémi demande d'en partir : « Lotus », jusqu'à la transcription, pour « Base P »");
  assert.equal(S.texteDemande(DEM(S.GENRE_REPARTIR, { cran: "images",
                                                      documents: [{ titre: "Lotus" }] })),
               "Rémi demande de repartir de zéro sur « Lotus » : revenir aux images seules");
  assert.ok(S.explicationDemande(DEM(S.GENRE_REPARTIR, { cran: "images" })).includes("Ne s'annule pas"));
  // Le demandeur entre deux projets ne lit jamais d'où vient la copie.
  assert.ok(S.explicationDemande(DEM(S.GENRE_AMORCER_ENTRE_PROJETS, { cran: "decoupage" }))
    .includes("ne lit jamais d'où elle vient"));
});

test("ce que lit le demandeur d'une demande entre deux projets : le document, le cran, l'arrivée", () => {
  const d = { genre: S.GENRE_AMORCER_ENTRE_PROJETS, cran: "annotations", collection_nom: "Base",
              documents: [{ document_id: 3, titre: "Le Voyageur" }] };
  assert.equal(S.quoiEnPartir(d), "En partir : « Le Voyageur », jusqu'aux annotations → « Base »");
  assert.ok(!/projet/.test(S.quoiEnPartir({ ...d, projet_nom: "Onomatopées" })),
            "jamais le projet qui tient le travail");
});
