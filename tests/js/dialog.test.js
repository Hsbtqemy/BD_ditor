/* Tests unitaires de la logique pure du piège à focus (static/lib/dialog.js).
   Le comportement DOM complet (role=dialog, Échap, retour du focus) est couvert
   en E2E Playwright ; ici on verrouille le calcul de bouclage Tab/Maj+Tab.
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { _trapTarget } = require("../../static/lib/dialog.js");

// Focusables fictifs : seule l'identité (référence) compte pour le calcul.
const A = { id: "a" }, B = { id: "b" }, C = { id: "c" };
const list = [A, B, C];

test("Tab depuis le dernier focusable boucle vers le premier", () => {
  assert.equal(_trapTarget(list, C, false), A);
});

test("Tab au milieu suit son cours normal (pas de bouclage)", () => {
  assert.equal(_trapTarget(list, A, false), null);
  assert.equal(_trapTarget(list, B, false), null);
});

test("Maj+Tab depuis le premier boucle vers le dernier", () => {
  assert.equal(_trapTarget(list, A, true), C);
});

test("Maj+Tab au milieu suit son cours normal", () => {
  assert.equal(_trapTarget(list, C, true), null);
  assert.equal(_trapTarget(list, B, true), null);
});

test("focus hors de la boîte est ramené à l'extrémité d'entrée", () => {
  const X = { id: "x" };                       // p.ex. focus échappé sur <body>
  assert.equal(_trapTarget(list, X, false), A); // Tab → premier
  assert.equal(_trapTarget(list, X, true), C);  // Maj+Tab → dernier
});

test("liste vide → null (le handler empêchera Tab de s'échapper)", () => {
  assert.equal(_trapTarget([], A, false), null);
  assert.equal(_trapTarget([], A, true), null);
});

test("un seul focusable : le focus reste dessus dans les deux sens", () => {
  assert.equal(_trapTarget([A], A, false), A);
  assert.equal(_trapTarget([A], A, true), A);
});
