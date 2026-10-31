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

/* ── Le LIEU partagé entre l'Atelier et la page Annotation (ANN-7, tranche 2, commit 7) ── */

test("le lieu se retient : album, planche, zone ; rien sans album", () => {
  const s = stockage();
  Nav.retenirLieu(s, "album=3&planche=7&region=12&grille=2&retour=%2Fcorpus");
  assert.equal(s._m.get("bd-lieu"), "album=3&planche=7&region=12");
  Nav.retenirLieu(s, "?album=3&planche=8");
  assert.equal(s._m.get("bd-lieu"), "album=3&planche=8");
  Nav.retenirLieu(s, "grille=2");                         // sans album : le lieu reste
  assert.equal(s._m.get("bd-lieu"), "album=3&planche=8");
  Nav.retenirLieu(qui_leve, "album=1");                   // rien ne lève
  Nav.retenirLieu(null, "album=1");
});

test("une adresse nue reprend le lieu, par-dessus la mémoire de SA page", () => {
  const s = stockage({ "bd-etat:annotation": "collection=4&album=1&planche=2&region=9&grille=5",
                       "bd-lieu": "album=3&planche=7&region=12" });
  assert.deepEqual(Nav.etatAvecLieu("", s, "annotation"),
                   { qs: "?collection=4&album=3&planche=7&region=12&grille=5", source: "lieu" });
  // L'Atelier n'a pas de mémoire à lui : le lieu seul.
  assert.deepEqual(Nav.etatAvecLieu("", s, "atelier"),
                   { qs: "?album=3&planche=7&region=12", source: "lieu" });
});

test("un lieu sans zone retire la zone qu'une mémoire gardait d'une autre planche", () => {
  const s = stockage({ "bd-etat:annotation": "album=1&planche=2&region=9",
                       "bd-lieu": "album=1&planche=5" });
  assert.deepEqual(Nav.etatAvecLieu("", s, "annotation"), { qs: "?album=1&planche=5", source: "lieu" });
});

test("l'adresse l'emporte toujours ; `retour` seul ne l'emporte pas, et se garde", () => {
  const s = stockage({ "bd-lieu": "album=3&planche=7" });
  assert.deepEqual(Nav.etatAvecLieu("?album=1", s, "atelier"), { qs: "?album=1", source: "adresse" });
  assert.deepEqual(Nav.etatAvecLieu("?retour=%2Fcorpus", s, "atelier"),
                   { qs: "?retour=%2Fcorpus&album=3&planche=7", source: "lieu" });
});

test("« Annoter ↗ » : la même zone dans la page Annotation, et le retour vers l'Atelier", () => {
  const lien = Nav.lienAnnotation({ album: 7, planche: 12, region: 40, collection: 3 },
                                  "/?album=7&planche=12&region=40");
  const u = new URL(lien, "http://x");
  assert.equal(u.pathname, "/annotation");
  assert.equal(u.searchParams.get("album"), "7");
  assert.equal(u.searchParams.get("planche"), "12");
  assert.equal(u.searchParams.get("region"), "40");
  assert.equal(u.searchParams.get("collection"), "3");
  assert.equal(u.searchParams.get("retour"), "/?album=7&planche=12&region=40");
  // Rien de choisi : la page d'annotation nue, qui reprendra le lieu retenu.
  assert.equal(Nav.lienAnnotation({ album: null, planche: null, region: null }, null),
               "/annotation");
  assert.equal(Nav.lienAnnotation(null, null), "/annotation");
  // Sans zone, la planche ; la collection « toutes » passe telle quelle.
  const sans = new URL(Nav.lienAnnotation({ album: 7, planche: 12, region: null,
                                            collection: "toutes" }, "/"), "http://x");
  assert.equal(sans.searchParams.has("region"), false);
  assert.equal(sans.searchParams.get("collection"), "toutes");
  // Un retour qui sort de l'instance n'est pas porté.
  assert.equal(new URL(Nav.lienAnnotation({ album: 7 }, "//evil.com"), "http://x")
    .searchParams.has("retour"), false);
});

test("sans lieu, ou un stockage qui lève, l'état de départ ordinaire", () => {
  assert.deepEqual(Nav.etatAvecLieu("", stockage({ "bd-etat:annotation": "grille=5" }), "annotation"),
                   { qs: "?grille=5", source: "memoire" });
  assert.deepEqual(Nav.etatAvecLieu("", stockage({ "bd-lieu": "planche=7" }), "atelier"),
                   { qs: "", source: "vide" });
  assert.deepEqual(Nav.etatAvecLieu("", qui_leve, "atelier"), { qs: "", source: "vide" });
  assert.deepEqual(Nav.etatAvecLieu("", null, "atelier"), { qs: "", source: "vide" });
});
