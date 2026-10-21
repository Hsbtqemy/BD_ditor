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

/* ── Reprise d'état par la session (INFRA-5) ─────────────────────────────────────── */

const Nav = require("../../static/lib/nav.js");

function stockage(init = {}) {
  const m = new Map(Object.entries(init));
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)),
           _m: m };
}
const qui_leve = { getItem() { throw new Error("SecurityError"); },
                   setItem() { throw new Error("QuotaExceededError"); } };

test("une adresse NUE reprend l'état mémorisé de SA page", () => {
  const s = stockage({ "bd-etat:recherche": "q=otage&tags=cri", "bd-etat:exploration": "vue=croisement" });
  assert.deepEqual(Nav.etatDeDepart("", s, "recherche"), { qs: "?q=otage&tags=cri", source: "memoire" });
  assert.deepEqual(Nav.etatDeDepart("", s, "exploration"), { qs: "?vue=croisement", source: "memoire" });
});

test("une adresse qui porte un état l'emporte TOUJOURS sur la mémoire", () => {
  const s = stockage({ "bd-etat:recherche": "q=otage" });
  for (const qs of ["?q=autre", "?album=3", "?tags=x&retour=%2Fexploration", "?q="]) {
    assert.deepEqual(Nav.etatDeDepart(qs, s, "recherche"), { qs, source: "adresse" }, qs);
  }
});

test("`retour` seul n'est pas un état : la mémoire complète l'adresse et garde son retour", () => {
  const s = stockage({ "bd-etat:recherche": "q=otage" });
  assert.deepEqual(Nav.etatDeDepart("?retour=%2Fcorpus", s, "recherche"),
                   { qs: "?q=otage&retour=%2Fcorpus", source: "memoire" });
});

test("sans mémoire, ou une mémoire vide, l'état de départ est celui de l'adresse", () => {
  assert.deepEqual(Nav.etatDeDepart("", stockage(), "recherche"), { qs: "", source: "vide" });
  assert.deepEqual(Nav.etatDeDepart("", stockage({ "bd-etat:recherche": "" }), "recherche"),
                   { qs: "", source: "vide" });
  assert.deepEqual(Nav.etatDeDepart("", null, "recherche"), { qs: "", source: "vide" });
});

test("un stockage qui LÈVE dégrade vers l'état vide, sans rien faire tomber", () => {
  assert.deepEqual(Nav.etatDeDepart("", qui_leve, "recherche"), { qs: "", source: "vide" });
  assert.doesNotThrow(() => Nav.memoriser(qui_leve, "recherche", "?q=x"));
  assert.doesNotThrow(() => Nav.memoriser(null, "recherche", "?q=x"));
  assert.equal(Nav.stockageDeSession({ get sessionStorage() { throw new Error("SecurityError"); } }), null);
  assert.equal(Nav.stockageDeSession(undefined), null);
});

test("mémoriser retire le contexte d'arrivée et garde l'état, vide compris", () => {
  const s = stockage();
  Nav.memoriser(s, "recherche", "?q=otage&retour=%2Fexploration%3Fvue%3Dconcordance");
  assert.equal(s._m.get("bd-etat:recherche"), "q=otage");
  // Effacer sa recherche est aussi un état : revenu par le menu, on retrouve l'invite.
  Nav.memoriser(s, "recherche", "");
  assert.deepEqual(Nav.etatDeDepart("", s, "recherche"), { qs: "", source: "vide" });
});

test("une mémoire qui ne porterait que `retour` ne vaut rien", () => {
  const s = stockage({ "bd-etat:recherche": "retour=%2Fcorpus" });
  assert.deepEqual(Nav.etatDeDepart("", s, "recherche"), { qs: "", source: "vide" });
});
