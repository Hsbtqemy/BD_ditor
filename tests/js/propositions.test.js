/* Les champs à propositions du panneau d'annotation (ANN-8) — la logique pure.
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Ce que ces tables couvrent coûtait, chacune de leurs lignes, un test navigateur de cinq
   à dix secondes : ce qu'Entrée DÉCIDE dans un champ « dimension : valeur », où mène une
   flèche, et la clé d'un libellé de tag. Ce qui dépend du temps — la lecture tenue en vol,
   la cible du geste — reste aux e2e de `test_e2e_atelier_propositions.py`, qui mesurent la
   requête partie. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const P = require("../../static/lib/propositions.js");

const VOCAB = [
  { id: 1, dimension: "lieu", valeur: "falaise" },
  { id: 2, dimension: "lieu", valeur: "phare" },
  { id: 3, dimension: "moment", valeur: "nuit" },
];

test("le module ne lit rien du navigateur au chargement", () => {
  // Chargé sous Node : ni `document`, ni `window`, ni `localStorage` n'existent ici.
  assert.equal(typeof globalThis.document, "undefined");
  assert.equal(typeof P.decisionEntree, "function");
});

test("formeComplete : la forme « dimension : valeur », et elle seule", () => {
  const cas = [
    ["lieu : falaise", { dim: "lieu", val: "falaise" }],
    ["lieu:falaise", { dim: "lieu", val: "falaise" }],
    ["  Lieu  :  Bord de mer ", { dim: "Lieu", val: "Bord de mer" }],
    ["heure : 10:30", { dim: "heure", val: "10:30" }],   // la PREMIÈRE colonne sépare
    ["lieu :", null], ["lieu : ", null], [": falaise", null], ["falaise", null],
    ["", null], [null, null], [undefined, null],
  ];
  for (const [q, attendu] of cas) assert.deepEqual(P.formeComplete(q), attendu, String(q));
});

test("connue : sans égard à la casse, dans tout le vocabulaire", () => {
  assert.equal(P.connue(VOCAB, { dim: "LIEU", val: "Falaise" }).id, 1);
  assert.equal(P.connue(VOCAB, { dim: "lieu", val: "grotte" }), null);
  assert.equal(P.connue(null, { dim: "lieu", val: "falaise" }), null);
  assert.equal(P.connue(VOCAB, null), null);
});

test("propositionsAttributs : filtre, borne, et la création d'une forme inconnue", () => {
  assert.deepEqual(P.propositionsAttributs(null, "lieu"), []);           // rien de lu
  assert.deepEqual(P.propositionsAttributs(VOCAB, "").map((i) => i.id), [1, 2, 3]);
  assert.deepEqual(P.propositionsAttributs(VOCAB, "LIEU").map((i) => i.id), [1, 2]);
  assert.deepEqual(P.propositionsAttributs(VOCAB, "ph").map((i) => i.id), [2]);
  // La forme complète d'une valeur connue ne propose pas de la créer…
  assert.deepEqual(P.propositionsAttributs(VOCAB, "lieu : falaise").map((i) => i.create),
                   [false]);
  // … sans espaces non plus, même si le filtre ne la retrouve pas.
  assert.deepEqual(P.propositionsAttributs(VOCAB, "lieu:falaise"), []);
  const inconnue = P.propositionsAttributs(VOCAB, "lieu : grotte");
  assert.deepEqual(inconnue.map((i) => [i.create, i.dim, i.val]), [[true, "lieu", "grotte"]]);
  const beaucoup = Array.from({ length: 25 }, (_, k) => ({ id: k, dimension: "d", valeur: "v" + k }));
  assert.equal(P.propositionsAttributs(beaucoup, "").length, P.MAX_PROPOSITIONS);
});

/* LA table d'Entrée. Chaque ligne : ce qui est tapé, le rang surligné, le vocabulaire lu
   (nul : aucune lecture n'a abouti) → le geste. La liste est celle que l'écran montre, donc
   celle que `propositionsAttributs` calcule pour la même saisie. */
const ENTREE = [
  // La proposition surlignée part, quelle que soit la saisie.
  ["ph", 0, VOCAB, { geste: "choisir", id: 2 }],
  ["lieu", 1, VOCAB, { geste: "choisir", id: 2 }],
  ["", 2, VOCAB, { geste: "choisir", id: 3 }],
  // Champ vide, rien de surligné : Entrée n'affecte RIEN — elle posait la seule valeur.
  ["", -1, VOCAB, { geste: "rien" }],
  ["   ", -1, VOCAB, { geste: "rien" }],
  ["", -1, [VOCAB[0]], { geste: "rien" }],
  // La forme complète aboutit sans la liste : connue → affectée, inconnue → créée.
  ["lieu : falaise", -1, VOCAB, { geste: "affecter", id: 1 }],
  ["LIEU:FALAISE", -1, VOCAB, { geste: "affecter", id: 1 }],
  ["lieu : grotte", -1, VOCAB, { geste: "creer", dim: "lieu", val: "grotte" }],
  // … même avant toute lecture : trouvée-ou-créée côté serveur.
  ["lieu : falaise", -1, null, { geste: "creer", dim: "lieu", val: "falaise" }],
  // Un mot seul qui désigne UNE proposition la prend.
  ["ph", -1, VOCAB, { geste: "choisir", id: 2 }],
  ["nuit", -1, VOCAB, { geste: "choisir", id: 3 }],
  // Un mot seul qui en désigne plusieurs, aucune, ou rien de lu : le dire.
  ["lieu", -1, VOCAB, { geste: "dire" }],
  ["grotte", -1, VOCAB, { geste: "dire" }],
  ["grotte", -1, [VOCAB[0]], { geste: "dire" }],          // « grotte » ne pose pas « falaise »
  ["falaise", -1, null, { geste: "dire" }],
  // Une forme incomplète : le dire, même si une seule proposition reste.
  ["lieu :", -1, VOCAB, { geste: "dire" }],
  ["moment :", -1, VOCAB, { geste: "dire" }],
];

test("decisionEntree : la table de vérité d'Entrée", () => {
  for (const [q, actif, vocab, attendu] of ENTREE) {
    const items = P.propositionsAttributs(vocab, q);
    const d = P.decisionEntree({ q, actif, items, vocab });
    const lu = d.geste === "choisir" ? { geste: d.geste, id: d.item.id } : d;
    assert.deepEqual(lu, attendu, `« ${q} », surligné ${actif}, vocabulaire ${vocab ? vocab.length : "non lu"}`);
  }
});

test("decisionEntree : un rang surligné hors de la liste ne choisit rien", () => {
  const items = P.propositionsAttributs(VOCAB, "ph");
  assert.deepEqual(P.decisionEntree({ q: "ph", actif: 5, items, vocab: VOCAB }),
                   { geste: "choisir", item: items[0] });   // le seul résultat, pas le rang 5
  assert.deepEqual(P.decisionEntree({ q: "lieu", actif: 9, items: P.propositionsAttributs(VOCAB, "lieu"),
                                      vocab: VOCAB }), { geste: "dire" });
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

test("cleTag : la table partagée avec database.cle_tag", () => {
  const TABLE = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "cas-tags.json"), "utf8"));
  assert.ok(TABLE.length >= 15, "table de cas suspicieusement courte");
  for (const cas of TABLE) {
    assert.equal(P.cleTag(cas.entree), cas.attendu, cas.nom);
    assert.equal(P.cleTag(P.cleTag(cas.entree)), cas.attendu, `${cas.nom} (idempotence)`);
  }
  assert.equal(P.cleTag(null), "");
  assert.equal(P.cleTag(undefined), "");
});
