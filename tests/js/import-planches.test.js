/* Tests unitaires de l'import en lot (static/lib/import-planches.js, UX-11).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Ce fichier garde les règles : l'ordre d'envoi (les noms, pas le sélecteur), un fichier à
   la fois, un échec qui se nomme sans arrêter les suivants, l'arrêt sur un refus qui porte
   sur l'album, l'arrêt demandé, et ce que disent la progression et le bilan. Que l'écran
   s'en serve se joue dans un navigateur (tests/test_e2e_import_lot.py). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

test("le module se charge sans document, sans fenêtre, sans fetch ni adresse", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(typeof window, "undefined");
  assert.equal(typeof location, "undefined");
  const chemin = require.resolve("../../static/lib/import-planches.js");
  delete require.cache[chemin];
  const api = require(chemin);
  assert.equal(typeof api.importerEnLot, "function");
});

const I = require("../../static/lib/import-planches.js");
const f = (name) => ({ name });
const noms = (l) => l.map((x) => x.name);

/* [cas, ordre reçu du sélecteur, ordre d'envoi attendu] */
const ORDRES = [
  ["alphabétique", ["c.tif", "a.tif", "b.tif"], ["a.tif", "b.tif", "c.tif"]],
  ["zéros en tête", ["p010.tif", "p002.tif", "p001.tif"], ["p001.tif", "p002.tif", "p010.tif"]],
  ["les nombres se lisent comme des nombres", ["p10.png", "p2.png", "p1.png"],
   ["p1.png", "p2.png", "p10.png"]],
  ["la casse ne range pas", ["B.jpg", "a.jpg", "C.jpg"], ["a.jpg", "B.jpg", "C.jpg"]],
  ["les accents ne rangent pas", ["été.png", "ete2.png", "eta.png"],
   ["eta.png", "été.png", "ete2.png"]],
  ["à égalité, l'ordre exact des caractères", ["a.PNG", "a.png"], ["a.PNG", "a.png"]],
];
for (const [cas, recu, attendu] of ORDRES) {
  test(`ordonner : ${cas}`, () => {
    const entree = recu.map(f);
    assert.deepEqual(noms(I.ordonner(entree)), attendu);
    assert.deepEqual(noms(entree), recu, "la sélection reçue n'est pas touchée");
  });
}

test("ordonner accepte une FileList (un objet itérable) et rien", () => {
  const liste = { 0: f("b"), 1: f("a"), length: 2 };
  assert.deepEqual(noms(I.ordonner(liste)), ["a", "b"]);
  assert.deepEqual(I.ordonner(null), []);
});

function erreur(statut, message) {
  const e = new Error(message);
  e.statut = statut;
  return e;
}

/* Un envoi simulé : il note l'ordre, vérifie qu'aucun envoi ne chevauche l'autre, et
   échoue sur les noms qu'on lui donne. */
function envoyeur(echecs = {}) {
  const envoyes = [];
  let enVol = 0, chevauchement = false;
  const envoyer = async (fichier) => {
    enVol++;
    if (enVol > 1) chevauchement = true;
    envoyes.push(fichier.name);
    await new Promise((r) => setTimeout(r, 1));
    enVol--;
    if (echecs[fichier.name]) throw echecs[fichier.name];
    return { id: envoyes.length, nom: fichier.name };
  };
  return { envoyer, envoyes, chevauche: () => chevauchement };
}

test("importerEnLot envoie tout, un fichier à la fois, dans l'ordre des noms", async () => {
  const e = envoyeur();
  const bilan = await I.importerEnLot(["p3.png", "p1.png", "p2.png"].map(f), e.envoyer);
  assert.deepEqual(e.envoyes, ["p1.png", "p2.png", "p3.png"]);
  assert.equal(e.chevauche(), false, "deux envois en même temps");
  assert.equal(bilan.total, 3);
  assert.deepEqual(bilan.importes.map((x) => x.nom), ["p1.png", "p2.png", "p3.png"]);
  assert.deepEqual(bilan.importes[0].planche, { id: 1, nom: "p1.png" });
  assert.deepEqual(bilan.echecs, []);
  assert.deepEqual(bilan.nonEnvoyes, []);
  assert.equal(bilan.arret, null);
});

test("un échec se nomme et n'arrête pas les suivants", async () => {
  const e = envoyeur({ "p2.png": erreur(400, "Échec de l'ingestion : image illisible") });
  const bilan = await I.importerEnLot(["p1.png", "p2.png", "p3.png", "p4.png"].map(f),
                                      e.envoyer);
  assert.deepEqual(e.envoyes, ["p1.png", "p2.png", "p3.png", "p4.png"]);
  assert.deepEqual(bilan.importes.map((x) => x.nom), ["p1.png", "p3.png", "p4.png"]);
  assert.deepEqual(bilan.echecs, [{ nom: "p2.png",
                                    message: "Échec de l'ingestion : image illisible" }]);
  assert.equal(bilan.arret, null);
});

for (const statut of [409, 413, 500, undefined]) {
  test(`un refus ${statut ?? "réseau"} porte sur le fichier : la série continue`, async () => {
    const e = envoyeur({ "a": erreur(statut, "non") });
    const bilan = await I.importerEnLot(["a", "b"].map(f), e.envoyer);
    assert.deepEqual(e.envoyes, ["a", "b"]);
    assert.equal(bilan.importes.length, 1);
  });
}

for (const statut of [401, 403, 404]) {
  test(`un refus ${statut} porte sur l'album : la série s'arrête, et le dit`, async () => {
    const e = envoyeur({ "b": erreur(statut, "Album 7 introuvable") });
    const bilan = await I.importerEnLot(["a", "b", "c", "d"].map(f), e.envoyer);
    assert.deepEqual(e.envoyes, ["a", "b"]);
    assert.deepEqual(bilan.importes.map((x) => x.nom), ["a"]);
    assert.deepEqual(bilan.echecs, [{ nom: "b", message: "Album 7 introuvable" }]);
    assert.deepEqual(bilan.nonEnvoyes, ["c", "d"]);
    assert.equal(bilan.arret, "album");
  });
}

test("l'arrêt demandé laisse finir l'envoi en cours, et rien d'autre ne part", async () => {
  const e = envoyeur();
  let arreter = false;
  const envoyer = async (x) => { const r = await e.envoyer(x); if (x.name === "b") arreter = true; return r; };
  const bilan = await I.importerEnLot(["a", "b", "c", "d"].map(f), envoyer,
                                      { doitArreter: () => arreter });
  assert.deepEqual(e.envoyes, ["a", "b"]);
  assert.deepEqual(bilan.nonEnvoyes, ["c", "d"]);
  assert.equal(bilan.arret, "demande");
});

test("la progression est dite AVANT chaque envoi, puis une fois à la fin", async () => {
  const etats = [];
  const e = envoyeur({ "b": erreur(400, "illisible") });
  await I.importerEnLot(["c", "a", "b"].map(f), e.envoyer, { surProgres: (s) => etats.push(s) });
  assert.deepEqual(etats, [
    { fait: 0, total: 3, nom: "a", echecs: 0 },
    { fait: 1, total: 3, nom: "b", echecs: 0 },
    { fait: 2, total: 3, nom: "c", echecs: 1 },
    { fait: 3, total: 3, nom: "", echecs: 1 },
  ]);
});

/* [état, libellé attendu] */
const PROGRESSIONS = [
  [{ fait: 0, total: 3, nom: "p1.png", echecs: 0 }, "1 sur 3 — p1.png"],
  [{ fait: 2, total: 50, nom: "p03.tif", echecs: 1 }, "3 sur 50 — p03.tif · 1 échec"],
  [{ fait: 4, total: 50, nom: "p05.tif", echecs: 2 }, "5 sur 50 — p05.tif · 2 échecs"],
];
for (const [etat, attendu] of PROGRESSIONS) {
  test(`libelleProgression : ${attendu}`, () => {
    assert.equal(I.libelleProgression(etat), attendu);
  });
}

/* [cas, bilan, libellé, ton] */
const BILANS = [
  ["tout est entré", { importes: [1, 2, 3], echecs: [], nonEnvoyes: [] },
   "3 planches importées", "succes"],
  ["une seule", { importes: [1], echecs: [], nonEnvoyes: [] }, "1 planche importée", "succes"],
  ["un échec", { importes: [1, 2], echecs: [{}], nonEnvoyes: [] },
   "2 planches importées, 1 échec", "partiel"],
  ["rien n'est entré", { importes: [], echecs: [{}, {}], nonEnvoyes: [] },
   "Aucune planche importée, 2 échecs", "erreur"],
  ["arrêté", { importes: [1], echecs: [], nonEnvoyes: ["c", "d"], arret: "demande" },
   "1 planche importée — 2 fichiers non envoyés : import arrêté", "partiel"],
  ["l'album refuse", { importes: [], echecs: [{}], nonEnvoyes: ["c"], arret: "album" },
   "Aucune planche importée, 1 échec — 1 fichier non envoyé : l'album n'accepte plus "
   + "d'import de votre part", "erreur"],
];
for (const [cas, bilan, libelle, ton] of BILANS) {
  test(`bilan : ${cas}`, () => {
    assert.equal(I.libelleBilan(bilan), libelle);
    assert.equal(I.tonBilan(bilan), ton);
  });
}

test("les refus qui arrêtent la série sont ceux de l'album, et eux seuls", () => {
  assert.deepEqual(I.STATUTS_D_ALBUM, [401, 403, 404]);
  for (const s of [400, 409, 413, 422, 500, 503, undefined]) assert.equal(I.arreteLaSerie(s), false);
});
