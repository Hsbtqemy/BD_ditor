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

/* ---- L'Atelier : les planchers mesurés de ses seuils ---- */
const atelier = (largeur, em = 16) => ({ largeur, em, paliers: Z.PALIERS_ATELIER });

test("l'Atelier : 200 % à 640 px faisait déborder sa bande 2 ; plus maintenant", () => {
  proche(Z.plafond(atelier(640)), 640 / 360);           // ≈ 1,78 : 22,5em utiles
  assert.ok(640 / Z.plafond(atelier(640)) >= 22.5 * 16 - 1e-9);
  // Les quatre autres surfaces gardent la règle de base.
  proche(Z.plafond(640), 2);
});

test("l'Atelier : sous 28em, la règle de base ; aucune largeur utile sous son plancher", () => {
  for (const em of [16, 20, 24]) {
    proche(Z.plafond(atelier(320, em)), 1);
    for (let l = 320; l <= 2600; l++) {
      const z = Z.plafond(atelier(l, em));
      if (z > 1) {
        assert.ok(l / z >= Z.plancher(atelier(l, em)) - 1e-9, `${l} px, police ${em}`);
      }
    }
  }
  proche(Z.plancher(atelier(448)), 320);                 // 28em inclus : encore étroit
  proche(Z.plancher(atelier(559)), 320);                 // 34.9375em inclus
  proche(Z.plancher(atelier(560)), 360);
  proche(Z.plancher(atelier(1023)), 360);
  proche(Z.plancher(atelier(1024)), 53 * 16);
  // La préférence de police déplace seuils et planchers ensemble.
  proche(Z.plancher(atelier(700, 24)), 20 * 24);        // 28em = 672 px sous 24
  proche(Z.plancher(atelier(839, 24)), 22.5 * 24);
});

test("l'Atelier : le zoom maximal ne baisse pas aux seuils étroits ; un seul saut, assumé", () => {
  for (const em of [16, 20, 24]) {
    const sauts = [];
    let avant = Z.plafond(atelier(320, em));
    for (let l = 321; l <= 2600; l++) {
      const z = Z.plafond(atelier(l, em));
      if (z < avant - 1e-9) sauts.push(l);
      avant = z;
    }
    // Le seul : le premier pixel au-dessus de 63.9375em, où paraissent les libellés.
    assert.deepEqual(sauts, [Math.floor(63.9375 * em) + 1], `police ${em}`);
  }
  // Le palier avant 34.9375em, à 16 px : 559 / 360 de 497 à 559 px.
  proche(Z.plafond(atelier(496)), 496 / 320);
  proche(Z.plafond(atelier(500)), 559 / 360);
  proche(Z.plafond(atelier(559)), 559 / 360);
  proche(Z.plafond(atelier(560)), 560 / 360);
  // Continu au seuil : rien ne se perd d'un pixel à l'autre.
  assert.ok(Z.plafond(atelier(560)) - Z.plafond(atelier(559)) < 0.01);
  // Le saut, à 16 px : 200 % à 1 023, 121 % à 1 024, 200 % de nouveau à 1 696.
  proche(Z.plafond(atelier(1023)), 2);
  proche(Z.plafond(atelier(1024)), 1024 / 848);
  proche(Z.plafond(atelier(1696)), 2);
});

test("la raison et le cran suivent la fenêtre complète", () => {
  assert.match(Z.raisonMaximum(2, atelier(640)), /largeur de fenêtre/);
  assert.equal(Z.raisonMaximum(1.7, atelier(640)), null);
  proche(Z.cran(2, atelier(640), -1), 1.7);
  proche(Z.applique(2, atelier(1280)), 1280 / 848);
});
