/* Tests unitaires de la lecture des droits en actes (static/lib/droits.js).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Trois descriptions, et c'est le point. AUJOURD'HUI est celle que sert `GET /api/droits`
   (`autorisation.ACTES`, `HORS_RANG`), recopiée avec les libellés validés par Hugo le
   2026-09-17 — c'est sa FORME qui compte ici. Les deux autres sont HYPOTHÉTIQUES : les issues qu'AUTH-10 peut
   retenir, un cran `contribution` et une case hors rang pour le vocabulaire. Si l'écran
   connaissait un niveau en dur, l'une d'elles le ferait tomber — c'est la preuve mécanique
   de la case d'AUTH-12 « L'écran ne connaît aucun niveau en dur ». */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const D = require("../../static/lib/droits.js");

const AVERTISSEMENT = "Supprimer un album efface ses images et ne se rattrape pas.";

const AUJOURDHUI = {
  echelle: ["lecture", "ecriture", "proprietaire"],
  actes: [
    { code: "lire", libelle: "lire", niveau: "lecture", lies: null, avertissement: null },
    { code: "annoter", libelle: "annoter", niveau: "ecriture", lies: "ecriture", avertissement: null },
    { code: "structurer", libelle: "organiser les albums", niveau: "ecriture", lies: "ecriture",
      avertissement: AVERTISSEMENT },
    { code: "vocabulaire", libelle: "gérer le vocabulaire", niveau: "ecriture", lies: "ecriture",
      avertissement: null },
    { code: "lots", libelle: "lancer la reconnaissance automatique", niveau: "ecriture", lies: "ecriture", avertissement: null },
    { code: "decider", libelle: "décider qui entre", niveau: "proprietaire", lies: null,
      avertissement: null },
  ],
  hors_rang: [{ code: "exporter", libelle: "exporter", champ: "exporter", d_office: "proprietaire" }],
};

// AUTH-10, remède B : `annoter` se détache dans un cran à lui.
const CONTRIBUTION = {
  echelle: ["lecture", "contribution", "ecriture", "proprietaire"],
  actes: AUJOURDHUI.actes.map((a) => (a.code === "annoter"
    ? { ...a, niveau: "contribution", lies: null } : { ...a })),
  hors_rang: AUJOURDHUI.hors_rang.map((h) => ({ ...h })),
};

// AUTH-10 : le vocabulaire passe HORS RANG, sur le modèle d'« exporter ».
const VOCABULAIRE_HORS_RANG = {
  echelle: [...AUJOURDHUI.echelle],
  actes: AUJOURDHUI.actes.filter((a) => a.code !== "vocabulaire").map((a) => ({ ...a })),
  hors_rang: [...AUJOURDHUI.hors_rang.map((h) => ({ ...h })),
              { code: "vocabulaire", libelle: "gérer le vocabulaire", champ: "vocabulaire",
                d_office: "proprietaire" }],
};

/* ── La description elle-même ────────────────────────────────────────────────────── */

test("les trois descriptions sont lisibles", () => {
  for (const d of [AUJOURDHUI, CONTRIBUTION, VOCABULAIRE_HORS_RANG]) assert.ok(D.estValide(d));
});

const CAS_INVALIDES = [
  ["rien", null],
  ["échelle absente", { actes: [], hors_rang: [] }],
  ["échelle vide", { echelle: [], actes: [], hors_rang: [] }],
  ["niveau en double", { echelle: ["a", "a"], actes: [], hors_rang: [] }],
  ["acte sur un niveau inconnu", { echelle: ["a"], actes: [{ libelle: "x", niveau: "b" }], hors_rang: [] }],
  ["hors rang d'office sur un niveau inconnu",
   { echelle: ["a"], actes: [], hors_rang: [{ champ: "c", libelle: "c", d_office: "b" }] }],
  ["hors rang sans champ", { echelle: ["a"], actes: [], hors_rang: [{ libelle: "c" }] }],
];
for (const [nom, d] of CAS_INVALIDES) {
  test(`description refusée : ${nom}`, () => assert.equal(D.estValide(d), false));
}

/* ── Colonnes et crans ───────────────────────────────────────────────────────────── */

const forme = (cols) => cols.map((c) => (c.type === "cran" ? `${c.niveau}[${c.actes.map((a) => a.code)}]`
                                                          : `+${c.code}`));

test("aujourd'hui : l'échelle entière, puis le hors rang, et les quatre actes d'écriture en UN cran", () => {
  assert.deepEqual(forme(D.colonnes(AUJOURDHUI)),
                   ["lecture[lire]", "ecriture[annoter,structurer,vocabulaire,lots]",
                    "proprietaire[decider]", "+exporter"]);
  assert.equal(D.colonnes(AUJOURDHUI)[1].libelle,
               "annoter · organiser les albums · gérer le vocabulaire · lancer la reconnaissance automatique");
});

test("contribution : un cran de PLUS, et « annoter » y est seul", () => {
  assert.deepEqual(forme(D.colonnes(CONTRIBUTION)),
                   ["lecture[lire]", "contribution[annoter]",
                    "ecriture[structurer,vocabulaire,lots]", "proprietaire[decider]", "+exporter"]);
});

test("vocabulaire hors rang : une case À CÔTÉ de plus, et le cran d'écriture la perd", () => {
  assert.deepEqual(forme(D.colonnes(VOCABULAIRE_HORS_RANG)),
                   ["lecture[lire]", "ecriture[annoter,structurer,lots]",
                    "proprietaire[decider]", "+exporter", "+vocabulaire"]);
});

test("les crans suivent l'ÉCHELLE, même si les actes arrivent dans le désordre", () => {
  const d = { ...AUJOURDHUI, actes: [...AUJOURDHUI.actes].reverse() };
  assert.deepEqual(D.crans(d).map((c) => c.niveau), AUJOURDHUI.echelle);
  // Dans un cran, l'ordre servi est gardé : c'est l'ordre des colonnes.
  assert.deepEqual(D.crans(d)[1].actes.map((a) => a.code),
                   ["lots", "vocabulaire", "structurer", "annoter"]);
});

test("un cran sans acte reste un cran, nommé par son niveau", () => {
  const d = { echelle: ["lecture", "vide"], actes: [AUJOURDHUI.actes[0]], hors_rang: [] };
  assert.deepEqual(D.colonnes(d).map((c) => c.libelle), ["lire", "vide"]);
});

/* ── Cocher, décocher ────────────────────────────────────────────────────────────── */

const CAS_COCHES = [
  // [niveau de l'accès, crans cochés]
  ["lecture", ["lecture"]],
  ["ecriture", ["lecture", "ecriture"]],
  ["proprietaire", ["lecture", "ecriture", "proprietaire"]],
  // Un niveau inconnu ne coche RIEN : la case vide et le niveau dit tel quel valent mieux
  // qu'une case cochée à tort.
  ["contribution", []],
];
for (const [niveau, attendu] of CAS_COCHES) {
  test(`un accès « ${niveau} » coche ${JSON.stringify(attendu)}`, () => {
    assert.deepEqual(AUJOURDHUI.echelle.filter((c) => D.cranCoche(AUJOURDHUI, niveau, c)), attendu);
  });
}

test("le premier cran ne se décoche pas ; les autres, si", () => {
  assert.equal(D.cranModifiable(AUJOURDHUI, "lecture"), false);
  assert.equal(D.cranModifiable(AUJOURDHUI, "ecriture"), true);
  assert.equal(D.cranModifiable(AUJOURDHUI, "proprietaire"), true);
  assert.equal(D.cranModifiable(AUJOURDHUI, "inconnu"), false);
});

const CAS_GESTES = [
  // [description, cran, coché après le geste, niveau envoyé]
  [AUJOURDHUI, "ecriture", true, "ecriture"],
  [AUJOURDHUI, "proprietaire", true, "proprietaire"],
  [AUJOURDHUI, "ecriture", false, "lecture"],
  // Décocher « décider » rend l'écriture, pas la lecture : les actes du dessous restent.
  [AUJOURDHUI, "proprietaire", false, "ecriture"],
  // Rien à envoyer : le premier cran ne se décoche pas, un cran inconnu n'existe pas.
  [AUJOURDHUI, "lecture", false, null],
  [AUJOURDHUI, "inconnu", true, null],
  // Avec un cran de plus, décocher l'écriture rend la contribution — rien n'est écrit en dur.
  [CONTRIBUTION, "ecriture", false, "contribution"],
  [CONTRIBUTION, "contribution", false, "lecture"],
];
for (const [d, cran, coche, attendu] of CAS_GESTES) {
  test(`${d === AUJOURDHUI ? "aujourd'hui" : "contribution"} : ${coche ? "cocher" : "décocher"} « ${cran} » envoie ${attendu}`, () => {
    assert.equal(D.niveauApresGeste(d, cran, coche), attendu);
  });
}

/* ── Hors rang ───────────────────────────────────────────────────────────────────── */

const etat = (d, niveau, valeurs) => D.horsRang(d, niveau, valeurs)
  .map((h) => `${h.code}:${h.coche ? "coché" : "vide"}${h.d_office ? "(d'office)" : ""}`);

test("exporter vient d'office au propriétaire, même quand la valeur stockée est fausse", () => {
  assert.deepEqual(etat(AUJOURDHUI, "proprietaire", { exporter: false }), ["exporter:coché(d'office)"]);
  assert.deepEqual(etat(AUJOURDHUI, "ecriture", { exporter: false }), ["exporter:vide"]);
  assert.deepEqual(etat(AUJOURDHUI, "lecture", { exporter: true }), ["exporter:coché"]);
  assert.deepEqual(etat(AUJOURDHUI, "inconnu", { exporter: true }), ["exporter:coché"]);
});

test("vocabulaire hors rang : chaque case lit SON champ", () => {
  assert.deepEqual(etat(VOCABULAIRE_HORS_RANG, "ecriture", { exporter: false, vocabulaire: true }),
                   ["exporter:vide", "vocabulaire:coché"]);
});

test("le corps du PUT porte le niveau et CHAQUE champ hors rang, en booléen", () => {
  const base = { genre: "groupe", principal: "annotateurs" };
  assert.deepEqual(D.corpsAcces(AUJOURDHUI, base, "ecriture", { exporter: 1 }),
                   { genre: "groupe", principal: "annotateurs", niveau: "ecriture", exporter: true });
  assert.deepEqual(D.corpsAcces(VOCABULAIRE_HORS_RANG, base, "lecture", {}),
                   { genre: "groupe", principal: "annotateurs", niveau: "lecture",
                     exporter: false, vocabulaire: false });
});

/* ── Ce qu'un accès permet, en une phrase ────────────────────────────────────────── */

const CAS_LUS = [
  [AUJOURDHUI, "lecture", {}, "lire"],
  [AUJOURDHUI, "lecture", { exporter: true }, "lire, exporter"],
  [AUJOURDHUI, "ecriture", {},
   "lire, annoter · organiser les albums · gérer le vocabulaire · lancer la reconnaissance automatique"],
  [AUJOURDHUI, "ecriture", { exporter: true },
   "lire, annoter · organiser les albums · gérer le vocabulaire · lancer la reconnaissance automatique, exporter"],
  [AUJOURDHUI, "proprietaire", { exporter: false }, "tous les actes, dont décider qui entre"],
  // Un niveau inconnu se dit tel quel : il ne disparaît pas (règle de l'étape 2, gardée).
  [AUJOURDHUI, "contribution", {}, "contribution"],
  [CONTRIBUTION, "contribution", {}, "lire, annoter"],
  [CONTRIBUTION, "ecriture", {},
   "lire, annoter, organiser les albums · gérer le vocabulaire · lancer la reconnaissance automatique"],
  [VOCABULAIRE_HORS_RANG, "ecriture", { vocabulaire: true },
   "lire, annoter · organiser les albums · lancer la reconnaissance automatique, gérer le vocabulaire"],
];
for (const [d, niveau, valeurs, attendu] of CAS_LUS) {
  test(`actesLus ${niveau} ${JSON.stringify(valeurs)} → « ${attendu} »`, () => {
    assert.equal(D.actesLus(d, niveau, valeurs), attendu);
  });
}

test("« tous les actes » ne se promet pas quand une case hors rang ne vient pas d'office", () => {
  const d = { ...AUJOURDHUI,
              hors_rang: [...AUJOURDHUI.hors_rang,
                          { code: "publier", libelle: "publier", champ: "publier", d_office: null }] };
  assert.equal(D.actesLus(d, "proprietaire", {}), "tous les actes sauf publier, dont décider qui entre");
  assert.equal(D.actesLus(d, "proprietaire", { publier: true }), "tous les actes, dont décider qui entre");
});

/* ── Avertissements ──────────────────────────────────────────────────────────────── */

test("l'avertissement se dit dès qu'UN accès porte l'acte, et une seule fois", () => {
  assert.deepEqual(D.avertissements(AUJOURDHUI, ["lecture"]), []);
  assert.deepEqual(D.avertissements(AUJOURDHUI, ["lecture", "ecriture", "proprietaire"]),
                   [AVERTISSEMENT]);
  assert.deepEqual(D.avertissements(AUJOURDHUI, ["proprietaire"]), [AVERTISSEMENT]);
  // Avec un cran de plus, la contribution n'atteint pas « structurer » : pas d'avertissement.
  assert.deepEqual(D.avertissements(CONTRIBUTION, ["contribution"]), []);
});

test("deux actes qui portent le MÊME avertissement ne le font dire qu'une fois", () => {
  // Le cas qui éprouve « une seule fois » : sans lui, un avertissement répété survivait à la
  // suite (mutant survivant, 2026-09-17) — aucune description n'en donnait deux pareils.
  const d = { ...AUJOURDHUI,
              actes: AUJOURDHUI.actes.map((a) => (a.code === "lots"
                ? { ...a, avertissement: AVERTISSEMENT } : { ...a })) };
  assert.deepEqual(D.avertissements(d, ["ecriture"]), [AVERTISSEMENT]);
});

/* ── Aucun niveau en dur ─────────────────────────────────────────────────────────── */

test("le module n'écrit AUCUN code de niveau ni d'acte hors de ses commentaires", () => {
  const source = fs.readFileSync(path.join(__dirname, "../../static/lib/droits.js"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  for (const mot of ["lecture", "ecriture", "proprietaire", "lire", "annoter", "structurer",
                     "vocabulaire", "lots", "decider", "exporter", "contribution"]) {
    assert.doesNotMatch(source, new RegExp(`["'\`]${mot}["'\`]`),
                        `« ${mot} » écrit en dur dans static/lib/droits.js`);
  }
});
