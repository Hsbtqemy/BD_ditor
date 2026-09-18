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
// Ce que `avertissements` rend pour lui sur la description d'aujourd'hui : le texte, l'acte
// qui le porte, et le cran qui l'accorde (correctif du 2026-09-18).
const ATTENDU_STRUCTURER = {
  texte: AVERTISSEMENT,
  actes: [{ code: "structurer", libelle: "organiser les albums" }],
  niveaux: ["ecriture"],
};

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

test("rétrograder n'AFFIRME pas une case d'office — sinon elle est accordée au passage", () => {
  // Le défaut du 2026-09-18, dans sa forme la plus nue : la liste rend l'export EFFECTIF d'un
  // propriétaire (vrai d'office), et le renvoyer en le rétrogradant le STOCKE.
  const base = { genre: "groupe", principal: "cours" };
  const effectif = { exporter: true };
  const corps = D.corpsAcces(AUJOURDHUI, base, "ecriture", effectif, "proprietaire");
  assert.deepEqual(corps, { ...base, niveau: "ecriture" });
  assert.ok(!("exporter" in corps), "la case d'office est affirmée : elle sera stockée");
  // Sans le niveau courant, les valeurs sont des décisions : rien n'est omis (création).
  assert.deepEqual(D.corpsAcces(AUJOURDHUI, base, "ecriture", effectif),
                   { ...base, niveau: "ecriture", exporter: true });
});

test("une case COCHÉE à la main reste affirmée quand le niveau change", () => {
  // En lecture, « exporter » n'est pas d'office : cochée ou décochée, c'est une décision, et
  // une promotion ne doit pas la perdre.
  const base = { genre: "utilisateur", principal: "zoe" };
  assert.deepEqual(D.corpsAcces(AUJOURDHUI, base, "ecriture", { exporter: true }, "lecture"),
                   { ...base, niveau: "ecriture", exporter: true });
  assert.deepEqual(D.corpsAcces(AUJOURDHUI, base, "ecriture", { exporter: false }, "lecture"),
                   { ...base, niveau: "ecriture", exporter: false });
});

test("l'omission suit la DESCRIPTION, pas un nom de champ", () => {
  // Deux cases hors rang, une seule d'office : l'autre est affirmée depuis le même niveau.
  const d = { ...AUJOURDHUI,
              hors_rang: [...AUJOURDHUI.hors_rang,
                          { code: "publier", libelle: "publier", champ: "publier", d_office: null }] };
  assert.deepEqual(D.corpsAcces(d, {}, "ecriture", { exporter: true, publier: true }, "proprietaire"),
                   { niveau: "ecriture", publier: true });
  // Et une description où RIEN n'est d'office n'omet rien.
  const sans = { ...AUJOURDHUI,
                 hors_rang: [{ code: "exporter", libelle: "exporter", champ: "exporter",
                               d_office: null }] };
  assert.deepEqual(D.corpsAcces(sans, {}, "ecriture", { exporter: true }, "proprietaire"),
                   { niveau: "ecriture", exporter: true });
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
                   [ATTENDU_STRUCTURER]);
  assert.deepEqual(D.avertissements(AUJOURDHUI, ["proprietaire"]), [ATTENDU_STRUCTURER]);
  // Avec un cran de plus, la contribution n'atteint pas « structurer » : pas d'avertissement.
  assert.deepEqual(D.avertissements(CONTRIBUTION, ["contribution"]), []);
});

test("l'avertissement NOMME l'acte qu'il concerne, et le cran qui l'accorde", () => {
  // Le défaut du 2026-09-18 : rendu seul, il ne disait plus de quoi il parlait. L'acte et son
  // cran viennent d'ici — l'écran les affiche et décrit la case, il ne les devine pas.
  const [av] = D.avertissements(AUJOURDHUI, ["ecriture"]);
  assert.deepEqual(av.actes, [{ code: "structurer", libelle: "organiser les albums" }]);
  assert.deepEqual(av.niveaux, ["ecriture"]);
  assert.equal(av.texte, AVERTISSEMENT);
});

test("deux actes qui portent le MÊME avertissement le font dire une fois, en se nommant tous les deux", () => {
  // Le cas qui éprouve « une seule fois » : sans lui, un avertissement répété survivait à la
  // suite (mutant survivant, 2026-09-17) — aucune description n'en donnait deux pareils. Et
  // depuis le 2026-09-18 il éprouve l'autre moitié : taire l'un des deux actes serait un
  // mensonge par omission.
  const d = { ...AUJOURDHUI,
              actes: AUJOURDHUI.actes.map((a) => (a.code === "lots"
                ? { ...a, avertissement: AVERTISSEMENT } : { ...a })) };
  assert.deepEqual(D.avertissements(d, ["ecriture"]), [{
    texte: AVERTISSEMENT,
    actes: [{ code: "structurer", libelle: "organiser les albums" },
            { code: "lots", libelle: "lancer la reconnaissance automatique" }],
    niveaux: ["ecriture"],
  }]);
});

test("deux actes de CRANS différents portant le même avertissement décrivent les deux cases", () => {
  // Rien n'oblige deux actes de même avertissement à partager leur cran : `niveaux` est une
  // liste pour cela, et l'écran décrit alors chacune des cases concernées.
  const d = { ...CONTRIBUTION,
              actes: CONTRIBUTION.actes.map((a) => (a.code === "decider"
                ? { ...a, avertissement: AVERTISSEMENT } : { ...a })) };
  const [av] = D.avertissements(d, ["proprietaire"]);
  assert.deepEqual(av.actes.map((a) => a.code), ["structurer", "decider"]);
  assert.deepEqual(av.niveaux, ["ecriture", "proprietaire"]);
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
