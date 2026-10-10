/* Tests unitaires du module « Qui y entre » d'un projet (static/lib/membres-projet.js, COL-3).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Ce fichier ne joue AUCUN geste : les gestes se jouent dans un navigateur
   (tests/test_e2e_projets.py), qui mesure les requêtes parties. Il garde ce qui fait de la
   partie un MODULE : qu'il se charge sans document, qu'il refuse une cible hors du document
   au lieu de se taire, et que deux montages ne se partagent jamais un identifiant. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

test("le module se charge sans document, sans fenêtre et sans adresse", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(typeof window, "undefined");
  assert.equal(typeof location, "undefined");
  const chemin = require.resolve("../../static/lib/membres-projet.js");
  delete require.cache[chemin];
  const api = require(chemin);
  assert.equal(typeof api.monter, "function");
  assert.equal(typeof api.noteAdmin, "function");
});

const { monter, noteAdmin, _suffixes } = require("../../static/lib/membres-projet.js");

test("monter LÈVE sur une cible absente ou hors du document", () => {
  // Hors du document, le montage passerait pour mort dès sa naissance : il resterait sur
  // « Chargement… » sans un mot. Une erreur le dit tout de suite.
  assert.throws(() => monter(null, {}), /dans le document/);
  assert.throws(() => monter({ isConnected: false }, { projet: { id: 1, gerable: true } }),
                /dans le document/);
});

test("la note des administrateurs nomme les groupes reçus, et se tait sans eux", () => {
  // Mono-poste : aucun groupe n'est lu, donc rien à déclarer.
  assert.equal(noteAdmin([]), "");
  assert.equal(noteAdmin(null), "");
  assert.equal(noteAdmin(undefined), "");
  const note = noteAdmin(["bd-admins", "direction"]);
  assert.match(note, /bd-admins, direction/);
  assert.match(note, /sans figurer dans la\s+liste de ses membres/);
});

test("un nom de groupe ne s'injecte pas dans la note", () => {
  const note = noteAdmin(['<img src=x onerror="alert(1)">']);
  assert.ok(!note.includes("<img"), note);
  assert.match(note, /&lt;img/);
});

/* Le registre est unique par page, comme dans le navigateur : chaque test prend un id de
   projet qui n'appartient qu'à lui. */
function banc() {
  const vivants = new Set();
  return {
    naitre: () => { const m = {}; vivants.add(m); return m; },
    mourir: (m) => vivants.delete(m),
    prendre: (id, m) => _suffixes.prendre(id, m, (x) => vivants.has(x)),
  };
}

test("le premier montage d'un projet garde le suffixe nu", () => {
  const b = banc();
  assert.equal(b.prendre(201, b.naitre()), "201");
});

test("deux montages VIVANTS du même projet n'ont pas le même suffixe", () => {
  const b = banc();
  const s1 = b.prendre(202, b.naitre());
  const s2 = b.prendre(202, b.naitre());
  const s3 = b.prendre(202, b.naitre());
  assert.equal(new Set([s1, s2, s3]).size, 3, [s1, s2, s3].join(" "));
  assert.equal(s1, "202");
});

test("deux projets ne se disputent rien", () => {
  const b = banc();
  assert.equal(b.prendre(203, b.naitre()), "203");
  assert.equal(b.prendre(204, b.naitre()), "204");
});

test("un montage mort ne retient pas son suffixe : redessiner ne le fait pas dériver", () => {
  // La fiche d'un projet est redessinée à chaque choix dans la liste : le projet ne doit pas
  // passer de `205` à `205m2`, puis `205m3`.
  const b = banc();
  for (let i = 0; i < 4; i++) {
    const m = b.naitre();
    assert.equal(b.prendre(205, m), "205", `au tour ${i}`);
    b.mourir(m);
  }
});

test("un mort qui se démonte après coup ne retire pas le suffixe d'un vivant", () => {
  const b = banc();
  const mort = b.naitre();
  assert.equal(b.prendre(206, mort), "206");
  b.mourir(mort);
  const vivant = b.naitre();
  assert.equal(b.prendre(206, vivant), "206");
  _suffixes.rendre("206", mort);                    // démontage tardif du mort
  assert.notEqual(b.prendre(206, b.naitre()), "206");
});

test("un suffixe rendu par celui qui le tient redevient libre", () => {
  const b = banc();
  const m = b.naitre();
  assert.equal(b.prendre(207, m), "207");
  _suffixes.rendre("207", m);
  assert.equal(b.prendre(207, b.naitre()), "207");
});
