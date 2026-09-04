/* Tests unitaires du compteur de résultats (static/lib/resultats.js).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Le cas qui compte est EXACTEMENT à la limite : c'est là que la règle mentait, et
   c'est le seul endroit où un test vaut mieux qu'une relecture. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { LIMITE, etat } = require("../../static/lib/resultats.js");

test("en deçà de la limite, le compte est exact et rien n'est signalé", () => {
  assert.deepEqual(etat(0, 200), { n: 0, tronque: false, texte: "0 résultat" });
  assert.deepEqual(etat(1, 200), { n: 1, tronque: false, texte: "1 résultat" });
  assert.deepEqual(etat(2, 200), { n: 2, tronque: false, texte: "2 résultats" });
  assert.deepEqual(etat(199, 200), { n: 199, tronque: false, texte: "199 résultats" });
});

test("À EXACTEMENT la limite, rien n'est tronqué — c'est le bug C1", () => {
  // L'ancienne règle (`count >= 200`) affichait « (limité) » ici, promettant des
  // résultats qui n'existaient pas. Un corpus de 200 correspondances est complet.
  assert.deepEqual(etat(200, 200), { n: 200, tronque: false, texte: "200 résultats" });
});

test("au-delà, on affiche la limite et on le DIT", () => {
  // L'appelant demande LIMITE + 1 : le 201e n'est jamais affiché, il sert de témoin.
  assert.deepEqual(etat(201, 200), { n: 200, tronque: true, texte: "200 résultats (limité)" });
  // Robustesse : même conclusion si l'API en renvoyait davantage (limite plus haute).
  assert.deepEqual(etat(500, 200), { n: 200, tronque: true, texte: "200 résultats (limité)" });
});

test("la limite par défaut est celle que la requête doit employer", () => {
  assert.equal(LIMITE, 200);
  assert.deepEqual(etat(LIMITE), { n: 200, tronque: false, texte: "200 résultats" });
  assert.deepEqual(etat(LIMITE + 1), { n: 200, tronque: true, texte: "200 résultats (limité)" });
});

test("une réponse aberrante ne fabrique jamais un compte négatif ou fractionnaire", () => {
  for (const bizarre of [-1, -200, NaN, undefined, null]) {
    const r = etat(bizarre, 200);
    assert.equal(r.n, 0, `n devrait être 0 pour ${String(bizarre)}`);
    assert.equal(r.tronque, false);
    assert.equal(r.texte, "0 résultat");
  }
  assert.equal(etat(3.7, 200).n, 3);   // tronqué à l'entier, jamais « 3.7 résultats »
});
