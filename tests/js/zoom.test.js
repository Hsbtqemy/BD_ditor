/* Tests unitaires de la borne du zoom d'interface (static/lib/zoom.js, UX-7).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   La règle : le zoom appliqué ne dépasse ni largeur ÷ 320, ni 200 % ; la préférence
   stockée n'est jamais réécrite par la borne. Le module ne touche à aucune globale du
   navigateur : il se charge sous Node, où `document` et `window` n'existent pas. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

assert.equal(typeof document, "undefined");
assert.equal(typeof window, "undefined");
const Z = require("../../static/lib/zoom.js");

const proche = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} ≠ ${b}`);

test("le plafond vaut largeur ÷ 320, entre 100 % et 200 %", () => {
  proche(Z.plafond(320), 1);
  proche(Z.plafond(375), 375 / 320);          // ≈ 1,17
  proche(Z.plafond(448), 1.4);
  proche(Z.plafond(640), 2);
  proche(Z.plafond(1280), 2);
  // Sous 320 px, on ne RÉDUIT pas d'office : le plafond reste 100 %.
  proche(Z.plafond(280), 1);
});

test("une largeur illisible ne borne rien", () => {
  proche(Z.plafond(0), Z.MAX);
  proche(Z.plafond(undefined), Z.MAX);
  proche(Z.plafond(NaN), Z.MAX);
});

test("la largeur utile ne tombe jamais sous 320 px CSS", () => {
  for (let l = 320; l <= 2000; l += 7) {
    for (const pref of [1, 1.4, 1.8, 2]) {
      assert.ok(l / Z.applique(pref, l) >= 320 - 1e-9, `${l} px sous ${pref}`);
    }
  }
});

test("le zoom appliqué est le minimum de la préférence et du plafond", () => {
  proche(Z.applique(2, 320), 1);
  proche(Z.applique(2, 375), 375 / 320);
  proche(Z.applique(2, 800), 2);
  proche(Z.applique(1.2, 800), 1.2);
  // Une préférence sous 100 % s'applique telle quelle, même à 320 px.
  proche(Z.applique(0.8, 320), 0.8);
});

test("la préférence lue du stockage n'est pas bornée par la largeur", () => {
  proche(Z.preference("2"), 2);
  proche(Z.preference("0.8"), 0.8);
  proche(Z.preference("2.5"), 1);
  proche(Z.preference("0.5"), 1);
  proche(Z.preference(null), 1);
  proche(Z.preference("n'importe quoi"), 1);
});

test("A+ s'éteint au plafond, et dit pourquoi", () => {
  assert.equal(Z.auMaximum(1, 320), true);
  assert.equal(Z.auMaximum(0.9, 320), false);
  assert.equal(Z.auMaximum(1.2, 375), true);
  assert.equal(Z.auMaximum(1.1, 375), false);
  assert.equal(Z.auMaximum(2, 800), true);
  assert.equal(Z.auMaximum(1.9, 800), false);
  assert.equal(Z.raisonMaximum(1.1, 375), null);
  assert.match(Z.raisonMaximum(1, 320), /largeur de fenêtre/);
  assert.match(Z.raisonMaximum(2, 375), /largeur de fenêtre/);
  // À 200 %, la fenêtre n'y est pour rien : la raison ne l'accuse pas.
  assert.doesNotMatch(Z.raisonMaximum(2, 800), /largeur/);
  assert.match(Z.raisonMaximum(2, 800), /200 %/);
});

test("un cran part du zoom APPLIQUÉ, au dixième, entre 80 % et 200 %", () => {
  proche(Z.cran(1, 800, 1), 1.1);
  proche(Z.cran(1.1, 375, 1), 1.2);          // la préférence 1,2 s'appliquera à ≈ 1,17
  // Sous une préférence de 200 % bornée à ≈ 117 %, A− réduit ce qu'on VOIT.
  proche(Z.cran(2, 375, -1), 1.1);
  proche(Z.cran(0.8, 800, -1), 0.8);
  proche(Z.cran(2, 800, 1), 2);
});
