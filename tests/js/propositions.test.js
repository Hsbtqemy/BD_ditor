/* Les champs à propositions de personnage (ANN-8) — la logique pure.
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Ce que ces tables couvrent coûtait, chacune de leurs lignes, un test navigateur de cinq
   à dix secondes : ce qu'Entrée DÉCIDE, où mène une flèche. Ce qui dépend du temps — la
   lecture tenue en vol, la cible du geste — reste aux e2e de
   `test_e2e_annotation_propositions.py`, qui mesurent la requête partie sur le champ
   « personnage » de la page Annotation. Les champs « dimension : valeur » et leurs tables
   sont partis avec le basculement d'ANN-7, comme la clé de tag (`cleTag`), dont la jumelle
   Python `database.cle_tag` garde sa table (`tests/test_cle_tag.py`). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const P = require("../../static/lib/propositions.js");

test("le module ne lit rien du navigateur au chargement", () => {
  // Chargé sous Node : ni `document`, ni `window`, ni `localStorage` n'existent ici.
  assert.equal(typeof globalThis.document, "undefined");
  assert.equal(typeof P.entreePersonnage, "function");
});

test("fleche : depuis « aucun », la première ↓ surligne la PREMIÈRE", () => {
  const cas = [
    [-1, 3, "bas", 0], [0, 3, "bas", 1], [2, 3, "bas", 2],
    [-1, 3, "haut", 0], [2, 3, "haut", 1], [0, 3, "haut", 0],
    [-1, 0, "bas", -1], [1, 0, "bas", -1], [-1, 0, "haut", -1],
    [-1, 1, "bas", 0],
  ];
  for (const [actif, n, sens, attendu] of cas) {
    assert.equal(P.fleche(actif, n, sens), attendu, `${sens} depuis ${actif} sur ${n}`);
  }
});

/* ANN-8 — les champs de PERSONNAGE (le locuteur, la boîte personnage). Les listes ont la
   forme que l'écran leur donne : un personnage { create: false, id, nom, serie }, la
   proposition de créer { create: true, nom }. */
const PERSOS = [
  { id: 1, nom: "Zed", serie: null },
  { id: 2, nom: "Zed", serie: "Les Aventures" },
  { id: 3, nom: "Zelda", serie: null },
  { id: 4, nom: "Étienne", serie: null },
  { id: 5, nom: "Tintin", serie: null },
];
const item = (p) => ({ create: false, id: p.id, nom: p.nom, serie: p.serie });
const creer = (nom) => ({ create: true, nom });

test("sansAccents : la table partagée avec socle._sans_accents", () => {
  const TABLE = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "cas-sans-accents.json"), "utf8"));
  assert.ok(TABLE.length >= 12, "table de cas suspicieusement courte");
  for (const cas of TABLE) assert.equal(P.sansAccents(cas.entree), cas.attendu, cas.nom);
  assert.equal(P.sansAccents(null), "");
});

test("repond : ce que le serveur aurait rendu pour la saisie, et la création exacte", () => {
  const cas = [
    [item(PERSOS[0]), "Ze", true], [item(PERSOS[0]), "zed", true], [item(PERSOS[2]), "Zed", false],
    [item(PERSOS[3]), "etien", true], [item(PERSOS[3]), "ÉTIEN", true],   // sans casse ni accents
    [item(PERSOS[4]), "nti", true],                                     // contient, pas seulement commence
    [item(PERSOS[4]), "", true], [item(PERSOS[4]), "   ", true],        // champ vide : tout répond
    [creer("Ze"), "Ze", true], [creer("Ze"), "Zed", false], [creer("Ze"), "ze", false],
    [creer("Ze"), " Ze ", true], [creer("Ze"), "", false],
    [null, "Ze", false], [undefined, "", false],
  ];
  for (const [it, q, attendu] of cas) {
    assert.equal(P.repond(it, q), attendu, `${JSON.stringify(it)} pour « ${q} »`);
  }
});

/* ANN-8 (Hugo, 2026-10-21) — l'accent ne distingue pas deux personnages : « etienne »
   tapé désigne « Étienne ». La comparaison est `sansAccents`, celle du serveur. */
test("homonymes : le nom exact, sans égard à la casse ni aux accents", () => {
  assert.deepEqual(P.homonymes(PERSOS, "zed").map((p) => p.id), [1, 2]);
  assert.deepEqual(P.homonymes(PERSOS, " Zed ").map((p) => p.id), [1, 2]);
  assert.deepEqual(P.homonymes(PERSOS, "Zeld").map((p) => p.id), []);   // contenir n'est pas porter
  assert.deepEqual(P.homonymes(PERSOS, "etienne").map((p) => p.id), [4]); // l'accent ne distingue pas
  assert.deepEqual(P.homonymes(PERSOS, "ETIENNE").map((p) => p.id), [4]);
  assert.deepEqual(P.homonymes(PERSOS, "e\u0301tienne").map((p) => p.id), [4]); // accent décomposé
  assert.deepEqual(P.homonymes(PERSOS, "étiennette").map((p) => p.id), []);
  assert.deepEqual(P.homonymes(PERSOS, "").map((p) => p.id), []);
  assert.deepEqual(P.homonymes(null, "Zed"), []);
  // Un nom accentué au registre, tapé sans accents, et l'inverse.
  const reg = [{ id: 7, nom: "Zoe", serie: null }, { id: 8, nom: "Zoë", serie: "Les Aventures" }];
  assert.deepEqual(P.homonymes(reg, "zoë").map((p) => p.id), [7, 8]);
});

/* LA table d'Entrée d'un champ de personnage (ANN-8, Hugo, 2026-10-21). Chaque ligne : ce
   qui est tapé MAINTENANT, la liste à l'écran (peut-être celle d'une saisie d'avant), le
   rang surligné → le geste. */
const LISTE_ZE = [item(PERSOS[0]), item(PERSOS[1]), item(PERSOS[2])];       // lue pour « Ze »
const LISTE_Z = [item(PERSOS[0]), item(PERSOS[1]), item(PERSOS[2]), creer("Z")]; // fictive
const ENTREE_PERSO = [
  // La surlignée qui répond à la saisie part, de la liste d'avant comme de la fraîche.
  ["Ze", LISTE_ZE, 2, { geste: "choisir", id: 3 }],
  ["Zel", LISTE_ZE, 2, { geste: "choisir", id: 3 }],        // liste de « Ze », « Zelda » répond
  ["Zed", LISTE_ZE, 0, { geste: "choisir", id: 1 }],
  ["", LISTE_ZE, 1, { geste: "choisir", id: 2 }],
  // ↓ puis Entrée pendant le rechargement : la surlignée de la liste d'avant NE répond PLUS.
  ["Zed", LISTE_ZE, 2, { geste: "relire" }],                // « Zelda » ne contient pas « zed »
  ["Zeld", LISTE_ZE, 0, { geste: "relire" }],
  ["Zed", LISTE_Z, 3, { geste: "relire" }],                 // « Créer « Z » » ne crée pas « Zed »
  ["", LISTE_Z, 3, { geste: "relire" }],
  ["Z", LISTE_Z, 3, { geste: "choisir", create: "Z" }],
  // Rien de surligné : le registre décide ; champ vide, rien.
  ["Zed", LISTE_ZE, -1, { geste: "valider" }],
  ["Zed", [], -1, { geste: "valider" }],
  ["", LISTE_ZE, -1, { geste: "rien" }],
  ["   ", [], -1, { geste: "rien" }],
  // Un rang hors de la liste ne surligne rien.
  ["Zed", LISTE_ZE, 7, { geste: "valider" }],
];

test("entreePersonnage : la proposition surlignée ne part que si elle répond encore", () => {
  for (const [q, items, actif, attendu] of ENTREE_PERSO) {
    const d = P.entreePersonnage({ q, actif, items });
    const lu = d.geste !== "choisir" ? d
      : d.item.create ? { geste: d.geste, create: d.item.nom } : { geste: d.geste, id: d.item.id };
    assert.deepEqual(lu, attendu, `« ${q} », surligné ${actif} sur ${items.length}`);
  }
});

test("decisionNom : un homonyme est pris, plusieurs se départagent, aucun se crée", () => {
  assert.deepEqual(P.decisionNom(PERSOS, "Tintin"), { geste: "choisir", item: PERSOS[4] });
  assert.deepEqual(P.decisionNom(PERSOS, "tintin "), { geste: "choisir", item: PERSOS[4] });
  const d = P.decisionNom(PERSOS, "Zed");
  assert.equal(d.geste, "departager");
  assert.deepEqual(d.homonymes.map((p) => [p.id, p.serie]), [[1, null], [2, "Les Aventures"]]);
  assert.deepEqual(P.decisionNom(PERSOS, "Zeld"), { geste: "creer", nom: "Zeld" });
  assert.deepEqual(P.decisionNom([], " Milou "), { geste: "creer", nom: "Milou" });
  // ANN-8 : « etienne » prend « Étienne », au lieu d'en créer un second.
  assert.deepEqual(P.decisionNom(PERSOS, "etienne"), { geste: "choisir", item: PERSOS[3] });
  // Deux séries, un même nom à l'accent près : Entrée ne décide pas.
  const reg = [{ id: 7, nom: "Zoe", serie: null }, { id: 8, nom: "Zoë", serie: "Les Aventures" }];
  assert.equal(P.decisionNom(reg, "ZOE").geste, "departager");
});
