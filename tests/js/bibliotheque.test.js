/* Tests unitaires de la Bibliothèque en calque (static/lib/bibliotheque.js, UX-18).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Ce fichier garde les règles elles-mêmes, par tables de cas : quels albums un calque
   laisse, dans quel ordre se rangent les collections, ce qu'on peut faire d'un album (l'union
   de ses collections) et d'une collection (ses actes), ce que deux collections partagent, et
   ce que l'adresse ouvre. Que l'écran s'en serve se joue dans un navigateur
   (tests/test_e2e_bibliotheque.py). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

test("le module se charge sans document, sans fenêtre, sans adresse et sans stockage", () => {
  // Vérifiées absentes AVANT : un Node qui les fournirait un jour rendrait ce test vert sur
  // un module qui lit l'adresse au chargement.
  assert.equal(typeof document, "undefined");
  assert.equal(typeof window, "undefined");
  assert.equal(typeof location, "undefined");
  assert.equal(typeof localStorage, "undefined");
  const chemin = require.resolve("../../static/lib/bibliotheque.js");
  delete require.cache[chemin];
  const api = require(chemin);
  assert.equal(typeof api.filtrerAlbums, "function");
});

const B = require("../../static/lib/bibliotheque.js");

const A = { id: 1, nom: "Étude A" };
const C = { id: 2, nom: "Corpus" };
const D = { id: 3, nom: "Doublons" };
const ALBUMS = [
  { id: 10, titre: "Tintin au Congo", serie: "Tintin", auteur: "Hergé", collections: [A] },
  { id: 11, titre: "L'Île Noire", serie: "Tintin", auteur: "Hergé", collections: [A, C] },
  { id: 12, titre: "Gaston", serie: "Gaston", auteur: "Franquin", collections: [C] },
  { id: 13, titre: "Seul au fonds", serie: null, auteur: null, collections: [] },
  { id: 14, titre: "Sans clé", serie: "Vieux", auteur: "Avant" },     // réponse d'avant la clé
];
const titres = (l) => l.map((a) => a.id);

/* [cas, options, ids attendus] */
const CAS_CALQUE = [
  ["aucun calque : tout reste", {}, [10, 11, 12, 13, 14]],
  ["une collection : ses albums, et eux seuls", { calques: [1] }, [10, 11]],
  ["une autre collection", { calques: [2] }, [11, 12]],
  ["une collection vide de nos albums", { calques: [3] }, []],
  ["deux collections, dans l'une (le défaut) : l'union", { calques: [1, 2] }, [10, 11, 12]],
  ["deux collections, dans toutes : l'intersection", { calques: [1, 2], mode: "toutes" }, [11]],
  ["un Set fait aussi l'affaire", { calques: new Set([2]) }, [11, 12]],
  ["des identifiants en texte (une case lue au DOM)", { calques: ["1"] }, [10, 11]],
  ["le texte, sans accents ni casse", { texte: "ile noire" }, [11]],
  ["le texte cherche aussi la série et l'auteur", { texte: "FRANQUIN" }, [12]],
  ["le texte ET le calque", { texte: "tintin", calques: [2] }, [11]],
  ["un texte d'espaces ne filtre rien", { texte: "   " }, [10, 11, 12, 13, 14]],
];
for (const [cas, options, attendu] of CAS_CALQUE) {
  test(`calque — ${cas}`, () => {
    assert.deepEqual(titres(B.filtrerAlbums(ALBUMS, options)), attendu);
  });
}

test("calque — une collection cochée ne montre JAMAIS un album qui n'y est pas", () => {
  // Le mutant visé : un filtre qui laisserait passer un album d'une autre collection (ou un
  // album sans collection) dès qu'un calque est actif.
  for (const c of [A, C, D]) {
    for (const a of B.filtrerAlbums(ALBUMS, { calques: [c.id] })) {
      assert.ok((a.collections || []).some((x) => x.id === c.id), `${a.titre} sous ${c.nom}`);
    }
  }
});

test("calque — une liste absente ne lève pas", () => {
  assert.deepEqual(B.filtrerAlbums(null, { calques: [1] }), []);
  assert.deepEqual(B.filtrerAlbums(undefined), []);
});

const COLS = [
  { id: 5, nom: "zèbre", base: false, date_creation: "2026-10-01 10:00:00" },
  { id: 2, nom: "Étude", base: false, date_creation: "2026-10-03 10:00:00" },
  { id: 9, nom: "Projet X", base: true, date_creation: "2026-09-01 10:00:00" },
  { id: 7, nom: "alpha", base: false, date_creation: "2026-10-03 10:00:00" },
];
test("tri — la base d'abord, puis par nom, à la française", () => {
  assert.deepEqual(B.trierCollections(COLS, "alpha").map((c) => c.id), [9, 7, 2, 5]);
});
test("tri — la base d'abord, puis la plus récente ; à date égale, l'identifiant le plus grand", () => {
  assert.deepEqual(B.trierCollections(COLS, "recents").map((c) => c.id), [9, 7, 2, 5]);
  const l = B.trierCollections([{ id: 1, nom: "a", date_creation: "2026-01-01" },
                                { id: 3, nom: "b", date_creation: "2026-05-01" }], "recents");
  assert.deepEqual(l.map((c) => c.id), [3, 1]);
});
test("tri — un tri inconnu vaut par nom, et l'entrée n'est pas modifiée", () => {
  const copie = COLS.slice();
  assert.deepEqual(B.trierCollections(COLS, "n'importe").map((c) => c.id), [9, 7, 2, 5]);
  assert.deepEqual(COLS, copie);
});

/* Les droits d'un album : [cas, album, collections lues avec `ecrivable`, ecrire attendu,
   ids écrits attendus]. */
const LUE = { id: 1, ecrivable: false };
const ECRITE = { id: 2, ecrivable: true };
const AUTRE_ECRITE = { id: 3, ecrivable: true };
const CAS_DROITS = [
  ["rangé dans une collection lue seulement", { collections: [A] }, [LUE, ECRITE], false, []],
  ["rangé dans une collection écrite", { collections: [C] }, [LUE, ECRITE], true, [2]],
  ["rangé dans une lue ET une écrite : l'union écrit", { collections: [A, C] }, [LUE, ECRITE],
   true, [2]],
  ["rangé dans deux écrites", { collections: [C, D] }, [LUE, ECRITE, AUTRE_ECRITE], true, [2, 3]],
  ["une collection qu'on ne voit plus dans la liste ne donne rien", { collections: [D] },
   [LUE, ECRITE], false, []],
  ["sans collection lue, le serveur a dit oui (portée totale, copie au fonds)",
   { collections: [], ecrivable: true }, [LUE], true, []],
  ["sans collection lue, le serveur a dit non", { collections: [], ecrivable: false }, [LUE],
   false, []],
  ["sans collection lue, et le serveur n'a rien dit", { collections: [] }, [], false, []],
];
for (const [cas, album, cols, ecrire, ecrites] of CAS_DROITS) {
  test(`droits d'un album — ${cas}`, () => {
    const d = B.droitsAlbum(album, cols);
    assert.equal(d.ecrire, ecrire);
    assert.deepEqual(d.ecrites.map((c) => c.id), ecrites);
    assert.deepEqual(d.lues.map((c) => c.id), (album.collections || []).map((c) => c.id));
  });
}
test("droits d'un album — la collection d'où l'on vient n'y entre pas : ouvert par la LUE, il écrit", () => {
  // Le mutant visé : la fiche qui lirait le droit de la collection COURANTE. La fonction ne
  // prend pas de collection courante ; ce cas dit pourquoi, par l'exemple de la fiche.
  const d = B.droitsAlbum({ collections: [A, C] }, [LUE, ECRITE]);
  assert.equal(d.ecrire, true);
  assert.equal(B.actesCollection(LUE).find((x) => x.cle === "ecrire").oui, false,
               "« Vos droits ici » de la collection lue, lui, ne dit pas écrire");
});
test("droits d'un album — le serveur qui dit `ecrivable` ne prime pas sur ses collections", () => {
  // Une copie rangée dans une collection lue seulement n'écrit pas, quoi qu'en dise une clé
  // isolée : sinon la règle aurait deux sources, et le mutant « droit de la courante » serait
  // masqué par elle.
  assert.equal(B.droitsAlbum({ collections: [A], ecrivable: true }, [LUE]).ecrire, false);
});

test("actes d'une collection — quatre actes, lus dans ce que le serveur a calculé", () => {
  const actes = (c) => B.actesCollection(c).map((x) => `${x.libelle}:${x.oui}`);
  assert.deepEqual(actes({}), ["lire:true", "annoter et organiser:false", "exporter:false",
                               "décider qui entre:false"]);
  assert.deepEqual(actes({ ecrivable: true, exportable: false, administrable: false }),
                   ["lire:true", "annoter et organiser:true", "exporter:false",
                    "décider qui entre:false"]);
  assert.deepEqual(actes({ ecrivable: false, exportable: true }),
                   ["lire:true", "annoter et organiser:false", "exporter:true",
                    "décider qui entre:false"]);
  assert.deepEqual(actes({ ecrivable: true, exportable: true, administrable: true }),
                   ["lire:true", "annoter et organiser:true", "exporter:true",
                    "décider qui entre:true"]);
  // Aucun nom de niveau à l'écran.
  for (const x of B.actesCollection({ ecrivable: true })) {
    assert.ok(!/propri|ecriture|lecture/.test(x.libelle), x.libelle);
  }
});

test("aussi dans — les autres collections lues, jamais celle qu'on regarde", () => {
  assert.deepEqual(B.aussiDans(ALBUMS[1], 1), ["Corpus"]);
  assert.deepEqual(B.aussiDans(ALBUMS[1], "2"), ["Étude A"]);
  assert.deepEqual(B.aussiDans(ALBUMS[0], 1), []);
  assert.deepEqual(B.aussiDans(ALBUMS[4], 1), []);
});

test("libellés — le total ne se dit qu'à une portée totale", () => {
  assert.equal(B.libelleAlbums(3, { total: true }), "3 albums");
  assert.equal(B.libelleAlbums(1, { total: true }), "1 album");
  assert.equal(B.libelleAlbums(3, {}), "3 albums que vous lisez");
  assert.equal(B.libelleAlbums(2, { total: true, sur: 9 }), "2 albums sur 9");
  assert.equal(B.libelleAlbums(2, { sur: 9 }), "2 albums sur 9 que vous lisez");
  assert.equal(B.libelleAlbums(9, { total: true, sur: 9 }), "9 albums");
});

test("comparaison — par collection, et le recoupement de deux", () => {
  const albums = [
    { id: 1, nb_planches: 10, nb_validees: 5, collections: [A] },
    { id: 2, nb_planches: 4, nb_validees: 4, collections: [A, C] },
    { id: 3, nb_planches: 6, nb_validees: 0, collections: [C] },
  ];
  const r = B.comparer([{ ...A, statut_diffusion: "public" }, C], albums);
  assert.deepEqual(r.lignes, [
    { id: 1, nom: "Étude A", regime: "public", albums: 2, planches: 14, validees: 9 },
    { id: 2, nom: "Corpus", regime: null, albums: 2, planches: 10, validees: 4 },
  ]);
  assert.deepEqual(r.recoupement, { communs: 1, seulA: 1, seulB: 1 });
  assert.equal(B.comparer([A, C, D], albums).recoupement, null);
});

/* L'adresse : [cas, search, attendu]. Sans onglet nommé, « Qui entre » : ce qu'ouvre le nom
   d'une collection, et ce que l'adresse ouvrait depuis AUTH-12. */
const CAS_LIRE = [
  ["rien", "", { collection: null, album: null, onglet: "qui", groupe: null }],
  ["une collection : « Qui entre »", "?collection=5",
   { collection: 5, album: null, onglet: "qui", groupe: null }],
  ["une collection et son onglet", "?collection=5&onglet=diffusion",
   { collection: 5, album: null, onglet: "diffusion", groupe: null }],
  ["l'onglet Albums", "?collection=5&onglet=albums",
   { collection: 5, album: null, onglet: "albums", groupe: null }],
  ["un onglet inconnu vaut « Qui entre »", "?collection=5&onglet=pirate",
   { collection: 5, album: null, onglet: "qui", groupe: null }],
  ["un groupe, sur « Qui entre »", "?collection=5&groupe=annotateurs",
   { collection: 5, album: null, onglet: "qui", groupe: "annotateurs" }],
  ["un groupe sans collection ne vaut rien", "?groupe=annotateurs",
   { collection: null, album: null, onglet: "qui", groupe: null }],
  ["un album", "?album=12", { collection: null, album: 12, onglet: "qui", groupe: null }],
  ["un album ouvert depuis une collection", "?collection=5&album=12",
   { collection: 5, album: 12, onglet: "qui", groupe: null }],
  ["des identifiants illisibles valent absents", "?collection=0&album=abc",
   { collection: null, album: null, onglet: "qui", groupe: null }],
];
for (const [cas, search, attendu] of CAS_LIRE) {
  test(`adresse lue — ${cas}`, () => assert.deepEqual(B.lireAdresse(search), attendu));
}

test("adresse écrite — ce qui est ouvert, et les autres paramètres gardés", () => {
  assert.equal(B.ecrireAdresse({ collection: 5, onglet: "qui" }, "?retour=%2Frecherche"),
               "?retour=%2Frecherche&collection=5");
  assert.equal(B.ecrireAdresse({ collection: 5, onglet: "albums" }, ""),
               "?collection=5&onglet=albums");
  assert.equal(B.ecrireAdresse({ collection: 5, album: 12, onglet: "albums" },
                               "?collection=3&onglet=albums"), "?collection=5&album=12");
  assert.equal(B.ecrireAdresse({ album: 12 }, "?collection=3"), "?album=12");
  assert.equal(B.ecrireAdresse({}, "?collection=3&onglet=albums&groupe=x"), "");
  assert.equal(B.ecrireAdresse({ collection: 5, onglet: "qui", groupe: "annotateurs" }, ""),
               "?collection=5&groupe=annotateurs");
  assert.equal(B.ecrireAdresse({ collection: 5, onglet: "pirate" }, ""), "?collection=5");
});

test("adresse — l'aller-retour rend ce qu'on a ouvert", () => {
  for (const etat of [{ collection: 5, album: null, onglet: "diffusion", groupe: null },
                      { collection: 5, album: null, onglet: "albums", groupe: null },
                      { collection: 5, album: 12, onglet: "qui", groupe: null },
                      { collection: null, album: 12, onglet: "qui", groupe: null },
                      { collection: 7, album: null, onglet: "qui", groupe: "g" }]) {
    assert.deepEqual(B.lireAdresse(B.ecrireAdresse(etat, "")), etat);
  }
});

test("onglets — quatre, dans l'ordre tranché ; le nom ouvre « Qui entre »", () => {
  assert.deepEqual(B.ONGLETS.map((o) => o.libelle),
                   ["Albums", "Qui entre", "Description", "Diffusion et dépôt"]);
  assert.equal(B.ONGLET_PAR_LE_NOM, "qui");
});

/* ═══ COL-3, tranche 3a — les gestes de la prise ═══ */

test("« + Prendre du fonds… » au responsable et à l'administrateur seulement (D3)", () => {
  assert.equal(B.offrirPrendreDuFonds({ gerable: true }), true);
  assert.equal(B.offrirPrendreDuFonds({ gerable: false }), false, "un membre, un écrivain");
  assert.equal(B.offrirPrendreDuFonds({}), false, "sans la clé, on n'offre rien");
  assert.equal(B.offrirPrendreDuFonds(null), false);
  // Dans une collection, il faut aussi pouvoir y recevoir.
  assert.equal(B.offrirPrendreDuFonds({ gerable: true }, { ecrivable: true }), true);
  assert.equal(B.offrirPrendreDuFonds({ gerable: true }, { ecrivable: false }), false);
  assert.equal(B.offrirPrendreDuFonds({ gerable: false }, { ecrivable: true }), false);
});

test("les destinations d'une prise : celles du projet où l'on écrit, la base en tête", () => {
  const cols = [
    { id: 1, nom: "Zeta", projet_id: 7, ecrivable: true },
    { id: 2, nom: "Base P", projet_id: 7, ecrivable: true, base: true },
    { id: 3, nom: "Alpha", projet_id: 7, ecrivable: false },
    { id: 4, nom: "Ailleurs", projet_id: 8, ecrivable: true },
    { id: 5, nom: "Beta", projet_id: 7, ecrivable: true },
  ];
  assert.deepEqual(B.destinationsPrise(cols, 7).map((c) => c.id), [2, 5, 1]);
  assert.deepEqual(B.destinationsPrise(cols, null).map((c) => c.id), [2, 4, 5, 1]);
  assert.deepEqual(B.destinationsPrise(null, 7), []);
});

test("la destination par défaut : d'où l'on vient, sinon la base, sinon la seule", () => {
  const base = { id: 2, nom: "Base", base: true }, x = { id: 5, nom: "X" };
  assert.equal(B.destinationParDefaut([base, x], null), 2, "la base présélectionnée");
  assert.equal(B.destinationParDefaut([base, x], 5), 5, "sauf si l'on vient d'une collection");
  assert.equal(B.destinationParDefaut([base, x], "5"), 5);
  assert.equal(B.destinationParDefaut([base, x], 9), 2, "une collection qui ne reçoit pas");
  assert.equal(B.destinationParDefaut([x], null), 5);
  assert.equal(B.destinationParDefaut([x, { id: 6 }], null), null, "on choisit");
  assert.equal(B.destinationParDefaut([], null), null);
});

test("la réponse d'une ligne de prise : jamais « fait » sans que le serveur l'ait dit", () => {
  assert.deepEqual(B.reponsePrise({ etat: "fait" }), { classe: "fait", texte: "fait" });
  assert.deepEqual(B.reponsePrise({ etat: "demande" }),
                   { classe: "demande", texte: "demandé à un administrateur" });
  assert.deepEqual(B.reponsePrise({ etat: "demande", repondra: "proprietaire" }),
                   { classe: "demande", texte: "demandé à son propriétaire" });
  assert.deepEqual(B.reponsePrise({ etat: "demande", repondra: "administrateur" }),
                   { classe: "demande", texte: "demandé à un administrateur" });
  assert.deepEqual(B.reponsePrise({ etat: "refuse", motif: "Déjà demandé." }),
                   { classe: "refuse", texte: "refusé : Déjà demandé." });
  assert.equal(B.reponsePrise(undefined).classe, "refuse");
});

test("cocher « Sur les collections » : un 202 ne range rien, et la phrase le dit", () => {
  const fait = B.messageRejoindre("Lotus", "Lot B", [{ id: 1 }]);
  assert.equal(fait.fait, true);
  assert.ok(fait.texte.startsWith("Fait : « Lotus » est aussi rangé dans « Lot B »"));
  const dem = B.messageRejoindre("Lotus", "Lot B", { etat: "demande", repondra: "proprietaire" });
  assert.equal(dem.fait, false);
  assert.ok(!/^Fait/.test(dem.texte), dem.texte);
  assert.ok(dem.texte.includes("La demande est partie"));
  assert.ok(dem.texte.includes("propriétaire"));
  const adm = B.messageRejoindre("Lotus", "Lot B", { etat: "demande", repondra: "administrateur" });
  assert.equal(adm.fait, false);
  assert.ok(adm.texte.includes("un administrateur y répondra"));
});

test("les demandes reçues se comptent pour qui peut y répondre, jamais pour une portée totale", () => {
  const l = [{ id: 1, repondable: true }, { id: 2, repondable: false }, { id: 3 }];
  assert.deepEqual(B.demandesARepondre(l, false).map((d) => d.id), [1]);
  assert.deepEqual(B.demandesARepondre(l, true), [], "l'administrateur répond dans « À faire »");
  assert.deepEqual(B.demandesARepondre(null, false), []);
});
