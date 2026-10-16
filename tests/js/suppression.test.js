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
                  date_creation: "2026-10-14 18:20:00" };

const DEFINITIFS = [
  ["l'importateur seul efface", { destructible: true, demande: null, total: false },
   "direct", "Supprimer définitivement", ["vous l'avez importé", "Irréversible"]],
  ["la portée totale efface partout", { destructible: true, demande: null, total: true },
   "direct", "Supprimer définitivement", ["dans tous les projets", "Irréversible"]],
  ["la portée totale efface même si une demande attend",
   { destructible: true, demande: DEMANDE, total: true },
   "direct", "Supprimer définitivement", ["dans tous les projets"]],
  ["sinon on demande", { destructible: false, demande: null, total: false },
   "demande", "Envoyer la demande", ["la demande part à un administrateur",
                                     "Rien n'est effacé d'ici là"]],
  ["une demande attend déjà : rien à envoyer, et on dit qui",
   { destructible: false, demande: DEMANDE, total: false },
   "attente", "", ["déjà demandée par Sam Diallo, le 14/10/2026", "un administrateur y répondra"]],
  ["une demande attend, sans nom rendu : on ne suppose rien",
   { destructible: false, demande: { id: 9, date_creation: "2026-10-14 18:20:00" } },
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
                           importe_le: "2026-10-14 09:00:00", projet_origine_nom: "Séminaire" }),
               "Importé par Léa Roux (lea), le 14/10/2026, dans « Séminaire ».");
  assert.equal(S.origine({ importe_par: "lea", importe_le: "2026-10-14" }),
               "Importé par lea, le 14/10/2026.");
  assert.equal(S.origine({ importe_par: null, importe_le: "2026-01-02 00:00:00",
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
