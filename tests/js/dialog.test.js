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

/* Un focus que la liste ne CONNAÎT pas — un `<summary>` oublié du sélecteur, le défaut
   du 2026-10-09 — se situe par sa place dans le document. Les éléments fictifs portent
   un rang ; `avant` est la doublure de `compareDocumentPosition`. */
const rang = (n) => ({ rang: n });
const avant = (a, b) => a.rang < b.rang;
const P = rang(10), Q = rang(20), R = rang(30);
const connus = [P, Q, R];

test("focus inconnu AU MILIEU : Tab suit son cours dans les deux sens", () => {
  const X = rang(25);                          // entre Q et R
  assert.equal(_trapTarget(connus, X, false, avant), null);
  assert.equal(_trapTarget(connus, X, true, avant), null);
});

test("focus inconnu APRÈS le dernier connu : Tab boucle, Maj+Tab recule seul", () => {
  const X = rang(35);
  assert.equal(_trapTarget(connus, X, false, avant), P);   // rien devant → premier
  assert.equal(_trapTarget(connus, X, true, avant), null); // R est derrière lui
});

test("focus inconnu AVANT le premier connu : Maj+Tab boucle, Tab avance seul", () => {
  const X = rang(5);
  assert.equal(_trapTarget(connus, X, true, avant), R);    // rien derrière → dernier
  assert.equal(_trapTarget(connus, X, false, avant), null);
});

test("un focus CONNU ne consulte jamais l'ordre : les bords décident seuls", () => {
  const jamais = () => { throw new Error("`precede` appelé pour un élément connu"); };
  assert.equal(_trapTarget(connus, R, false, jamais), P);
  assert.equal(_trapTarget(connus, P, true, jamais), R);
  assert.equal(_trapTarget(connus, Q, false, jamais), null);
  assert.equal(_trapTarget(connus, Q, true, jamais), null);
});

test("liste vide → null (le handler empêchera Tab de s'échapper)", () => {
  assert.equal(_trapTarget([], A, false), null);
  assert.equal(_trapTarget([], A, true), null);
});

test("un seul focusable : le focus reste dessus dans les deux sens", () => {
  assert.equal(_trapTarget([A], A, false), A);
  assert.equal(_trapTarget([A], A, true), A);
});
