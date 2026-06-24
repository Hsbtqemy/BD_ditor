/* Tests unitaires de la logique pure de static/lib/common.js (escapeHtml).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).
   $ / apiGet / apiSend / toast touchent DOM/fetch à l'appel → non testés ici. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { escapeHtml } = require("../../static/lib/common.js");

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
