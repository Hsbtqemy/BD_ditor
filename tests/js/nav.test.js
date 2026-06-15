/* Tests unitaires de la logique de navigation pure (static/lib/nav.js).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { safeRetour } = require("../../static/lib/nav.js");

test("safeRetour accepte les chemins internes relatifs", () => {
  assert.equal(safeRetour("/recherche?q=x&tags=dialogue"), "/recherche?q=x&tags=dialogue");
  assert.equal(safeRetour("/?album=1&planche=5&region=42"), "/?album=1&planche=5&region=42");
  assert.equal(safeRetour("/"), "/");
  assert.equal(safeRetour("/exploration?champ=lemme&compare=1"), "/exploration?champ=lemme&compare=1");
});

test("safeRetour rejette tout ce qui n'est pas une page interne", () => {
  for (const bad of [
    "//evil.com",            // protocol-relative
    "/\\evil.com",           // backslash (traité comme // par certains navigateurs)
    "javascript:alert(1)",   // XSS
    "data:text/html,x",      // schéma dangereux
    "https://evil.com",      // open-redirect absolu
    "http://x",
    "evil.com",              // sans schéma ni /
    "",                      // vide
    null, undefined, 42, {}, // types non-chaîne
  ]) {
    assert.equal(safeRetour(bad), null, `devrait rejeter ${JSON.stringify(bad)}`);
  }
});
