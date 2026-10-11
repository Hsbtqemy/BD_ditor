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

/* Un groupe de boutons radio n'est qu'UN arrêt de tabulation (AUTH-11). Les éléments
   fictifs portent ce que le piège lit : `type`, `name`, `form`, `checked`. */
const { _stop, _stops } = require("../../static/lib/dialog.js");
const radio = (name, checked, form) => ({ type: "radio", name, checked: !!checked, form: form || null });
const bouton = () => ({ type: "submit", name: "", form: null });

test("un groupe radio se réduit à son bouton COCHÉ, où qu'il soit dans le groupe", () => {
  const r1 = radio("col"), r2 = radio("col", true), r3 = radio("col"), go = bouton();
  assert.deepEqual(_stops([r1, r2, r3, go]), [r2, go]);
  assert.equal(_stop([r1, r2, r3, go], r1), r2);
  assert.equal(_stop([r1, r2, r3, go], r3), r2);
  assert.equal(_stop([r1, r2, r3, go], r2), r2);
});

test("sans bouton coché, l'arrêt du groupe est son premier bouton", () => {
  const r1 = radio("col"), r2 = radio("col"), go = bouton();
  assert.deepEqual(_stops([go, r1, r2]), [go, r1]);
  assert.equal(_stop([go, r1, r2], r2), r1);
});

test("deux groupes, deux arrêts : le nom et le formulaire les séparent", () => {
  const f1 = { id: "f1" }, f2 = { id: "f2" };
  const a1 = radio("x", true, f1), a2 = radio("x", false, f1);
  const b1 = radio("x", false, f2), b2 = radio("x", true, f2);
  const c1 = radio("y", false, f1), c2 = radio("y", false, f1);
  assert.deepEqual(_stops([a1, a2, b1, b2, c1, c2]), [a1, b2, c1]);
});

test("un bouton radio sans nom est son propre arrêt", () => {
  const r1 = radio(""), r2 = radio("");
  assert.deepEqual(_stops([r1, r2]), [r1, r2]);
});

test("ce qui n'est pas un bouton radio, ou n'est pas dans la liste, est rendu tel quel", () => {
  const r1 = radio("col", true), go = bouton(), dehors = radio("col");
  assert.equal(_stop([r1, go], go), go);
  assert.equal(_stop([r1, go], dehors), dehors);   // hors de la boîte : on ne le déplace pas
  assert.equal(_stop([r1, go], null), null);
});

test("le défaut d'origine : le second coché, Maj+Tab depuis lui boucle au dernier", () => {
  const r1 = radio("col"), r2 = radio("col", true), go = bouton(), annuler = bouton();
  const tous = [r1, r2, go, annuler];
  // Avant : r2 n'était pas le premier de la liste, le piège laissait faire (null).
  assert.equal(_trapTarget(tous, r2, true), null);
  assert.equal(_trapTarget(_stops(tous), _stop(tous, r2), true), annuler);
  // Et Tab depuis le dernier revient au COCHÉ, pas au premier bouton du groupe.
  assert.equal(_trapTarget(_stops(tous), _stop(tous, annuler), false), r2);
});

test("groupe sans coché : le focus posé sur n'importe lequel de ses boutons est un bord", () => {
  const t1 = radio("tete"), t2 = radio("tete"), go = bouton(), q1 = radio("queue"), q2 = radio("queue");
  const tous = [t1, t2, go, q1, q2];
  assert.equal(_trapTarget(_stops(tous), _stop(tous, t2), true), q1);   // Chromium à reculons
  assert.equal(_trapTarget(_stops(tous), _stop(tous, q2), false), t1);
});
