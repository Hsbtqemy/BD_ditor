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

/* ── Quel fichier est devenu quelle planche (UX-11, 2026-10-22) ─────────────────────── */

test("libellePlanche : le numéro éditorial du récit, l'ordre d'import du paratexte", () => {
  assert.equal(I.libellePlanche({ numero: 5, role: "recit", numero_editorial: 3 }), "planche 3");
  assert.equal(I.libellePlanche({ numero: 5, role: "paratexte", numero_editorial: null }),
               "paratexte i.005");
});

test("correspondances : une ligne par fichier entré, la planche lue dans la liste ACTUELLE", () => {
  const bilan = { importes: [{ nom: "page-2.tif", planche: { id: 11, numero: 1 } },
                             { nom: "page-10.tif", planche: { id: 12, numero: 2 } },
                             { nom: "page-9.tif", planche: { id: 13, numero: 3 } }],
                  echecs: [{ nom: "page-3.tif", message: "refus" }] };
  // Depuis l'import : 12 est passée en tête, 13 est devenue un paratexte, 11 a été supprimée.
  const planches = [{ id: 12, numero: 1, role: "recit", numero_editorial: 1 },
                    { id: 13, numero: 3, role: "paratexte", numero_editorial: null }];
  assert.deepEqual(I.correspondances(bilan, planches), [
    { nom: "page-2.tif", planche: "planche supprimée depuis" },
    { nom: "page-10.tif", planche: "planche 1" },
    { nom: "page-9.tif", planche: "paratexte i.003" },
  ]);
  assert.deepEqual(I.correspondances(null, planches), []);
});

/* [cas, échec, { nom, suite }] */
const ECHECS = [
  ["le serveur nomme le fichier : pas de redite",
   { nom: "page-3.tif", message: "page-3.tif n'est pas une image lisible : son format n'est pas reconnu, ou le fichier est abîmé." },
   { nom: "page-3.tif", suite: " n'est pas une image lisible : son format n'est pas reconnu, ou le fichier est abîmé." }],
  ["un message qui ne le nomme pas", { nom: "p.tif", message: "Album 7 introuvable" },
   { nom: "p.tif", suite: " : Album 7 introuvable" }],
  ["un nom qui n'est qu'un préfixe d'un autre", { nom: "p1", message: "p10 refusé" },
   { nom: "p1", suite: " : p10 refusé" }],
];
for (const [cas, echec, attendu] of ECHECS) {
  test(`ligneEchec : ${cas}`, () => assert.deepEqual(I.ligneEchec(echec), attendu));
}

/* ── Changer l'ordre des planches ───────────────────────────────────────────────────── */

test("deplacer : un cran vers le haut, vers le bas, rien au bord", () => {
  const ids = [1, 2, 3];
  assert.deepEqual(I.deplacer(ids, 2, -1), [2, 1, 3]);
  assert.deepEqual(I.deplacer(ids, 2, 1), [1, 3, 2]);
  assert.equal(I.deplacer(ids, 1, -1), null);
  assert.equal(I.deplacer(ids, 3, 1), null);
  assert.equal(I.deplacer(ids, 9, 1), null);
  assert.equal(I.deplacer(ids, 2, 2), null);
  assert.deepEqual(ids, [1, 2, 3], "la liste reçue n'est pas touchée");
});

const pl = (id, nom) => ({ id, nom_fichier_origine: nom });

test("ordreParNom : l'ordre naturel des noms, comme l'import en lot", () => {
  const plan = I.ordreParNom([pl(1, "p10.tif"), pl(2, "P2.tif"), pl(3, "p1.tif"), pl(4, "été.tif")]);
  assert.deepEqual(plan.ordre, [4, 3, 2, 1]);
  assert.equal(plan.deplacees, 4);
  assert.equal(plan.sansNom, 0);
});

test("ordreParNom : les planches sans nom restent en tête, dans leur ordre", () => {
  const plan = I.ordreParNom([pl(1, "b.tif"), pl(2, null), pl(3, "a.tif"), pl(4, null)]);
  assert.deepEqual(plan.ordre, [2, 4, 3, 1]);
  assert.equal(plan.sansNom, 2);
  assert.equal(plan.avecNom, 2);
  assert.equal(plan.deplacees, 3, "« a.tif » garde son rang");
});

test("ordreParNom : à égalité de nom, l'ordre actuel ; déjà rangé, rien ne bouge", () => {
  assert.deepEqual(I.ordreParNom([pl(5, "a.tif"), pl(2, "a.tif"), pl(9, "b.tif")]).ordre, [5, 2, 9]);
  const plan = I.ordreParNom([pl(1, "p1.tif"), pl(2, "p2.tif"), pl(3, "p10.tif")]);
  assert.deepEqual(plan.ordre, [1, 2, 3]);
  assert.equal(plan.deplacees, 0);
});

test("phraseRangerParNom : la confirmation dit ce qui change, et le cas des planches sans nom", () => {
  const p = I.phraseRangerParNom({ ordre: [], deplacees: 3, sansNom: 2, avecNom: 5 });
  assert.equal(p.message, null);
  assert.match(p.confirmer, /^Ranger les planches dans l'ordre des noms de fichier \?/);
  assert.match(p.confirmer, /3 planches changent de place\./);
  assert.match(p.confirmer, /numéros éditoriaux et les citations « pl·c·b »/);
  assert.match(p.confirmer, /2 planches n'ont pas de nom de fichier noté \(importées avant que l'outil le note\) : elles restent en tête, dans leur ordre actuel\./);
  const un = I.phraseRangerParNom({ deplacees: 1, sansNom: 1, avecNom: 2 });
  assert.match(un.confirmer, /1 planche change de place\./);
  assert.match(un.confirmer, /1 planche n'a pas de nom de fichier noté \(importée avant que l'outil le note\) : elle reste en tête, dans son ordre actuel\./);
  assert.doesNotMatch(I.phraseRangerParNom({ deplacees: 2, sansNom: 0, avecNom: 2 }).confirmer,
                      /sans nom|pas de nom/);
});

test("phraseRangerParNom : rien à faire se dit, sans confirmation", () => {
  assert.deepEqual(I.phraseRangerParNom({ deplacees: 0, sansNom: 0, avecNom: 3 }),
                   { confirmer: null, message: "Les planches sont déjà dans l'ordre des noms de fichier." });
  const aucun = I.phraseRangerParNom({ deplacees: 0, sansNom: 3, avecNom: 0 });
  assert.equal(aucun.confirmer, null);
  assert.match(aucun.message, /^Aucune planche de cet album n'a de nom de fichier noté/);
});
