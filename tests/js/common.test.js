/* Tests unitaires de la logique pure de static/lib/common.js (escapeHtml,
   messageErreur).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).
   $ / apiGet / apiSend / toast touchent DOM/fetch à l'appel → non testés ici. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { escapeHtml, messageErreur } = require("../../static/lib/common.js");

test("escapeHtml échappe les métacaractères HTML", () => {
  assert.equal(escapeHtml("<b>&\"'"), "&lt;b&gt;&amp;&quot;&#39;");
  assert.equal(escapeHtml("a & b < c > d"), "a &amp; b &lt; c &gt; d");
  assert.equal(escapeHtml("D'Artagnan"), "D&#39;Artagnan");   // apostrophe (fréquent en fr)
  assert.equal(escapeHtml("rien à échapper"), "rien à échapper");
});

test("escapeHtml normalise null/undefined en chaîne vide (pas « null »/« undefined »)", () => {
  assert.equal(escapeHtml(null), "");
  assert.equal(escapeHtml(undefined), "");
  assert.equal(escapeHtml(""), "");
});

test("escapeHtml convertit les non-chaînes via String()", () => {
  assert.equal(escapeHtml(42), "42");
  assert.equal(escapeHtml(0), "0");          // 0 n'est pas null/undefined → « 0 »
  assert.equal(escapeHtml(true), "true");
});


/* ---- messageErreur : ce que l'utilisateur LIT quand l'API refuse ---------- */

test("un refus métier est affiché tel quel — il est déjà écrit pour être lu", () => {
  assert.equal(messageErreur({ detail: "Collection 7 introuvable." }, "Not Found"),
               "Collection 7 introuvable.");
});

test("un 422 de validation nomme le CHAMP et la borne, en français", () => {
  // Le détail d'un 422 FastAPI est une LISTE d'objets. `new Error(liste)` affichait
  // « [object Object] » : rien, précisément à qui vient de taper une valeur refusée.
  const borne = (type, ctx) => ({
    detail: [{ type: type, loc: ["body", "annee"], msg: "Input should be …", ctx: ctx }],
  });
  assert.equal(messageErreur(borne("less_than_equal", { le: 2200 }), "?"),
               "annee : doit valoir au plus 2200");
  assert.equal(messageErreur(borne("greater_than_equal", { ge: 1400 }), "?"),
               "annee : doit valoir au moins 1400");
  assert.equal(messageErreur({ detail: [{ type: "missing", loc: ["body", "titre"] }] }, "?"),
               "titre : champ obligatoire");
});

test("plusieurs erreurs sont toutes montrées, pas seulement la première", () => {
  const corps = { detail: [
    { type: "missing", loc: ["body", "titre"] },
    { type: "less_than_equal", loc: ["body", "annee"], ctx: { le: 2200 } },
  ] };
  assert.equal(messageErreur(corps, "?"), "titre : champ obligatoire · annee : doit valoir au plus 2200");
});

test("une contrainte INCONNUE retombe sur le texte de la bibliothèque", () => {
  // La table ne peut pas être exhaustive : une version future en ajoutera. Se taire
  // serait pire que d'afficher un texte anglais, qui reste lisible.
  const corps = { detail: [{ type: "regle_future", loc: ["body", "x"], msg: "Some new rule" }] };
  assert.equal(messageErreur(corps, "?"), "x : Some new rule");
  assert.equal(messageErreur({ detail: [{ type: "regle_future", loc: ["body", "x"] }] }, "?"),
               "x : valeur refusée");
});

test("sans corps exploitable, on retombe sur le statut HTTP", () => {
  for (const vide of [{}, null, undefined, { detail: "" }, { detail: [] }, { detail: 42 }]) {
    assert.equal(messageErreur(vide, "Service Unavailable"), "Service Unavailable");
  }
});
