/* Tests unitaires de la logique pure de static/lib/common.js (escapeHtml,
   messageErreur).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).
   $ / apiGet / apiSend / toast touchent DOM/fetch à l'appel → non testés ici. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { escapeHtml, messageErreur, identite } = require("../../static/lib/common.js");

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


/* --- identite() (UX-10) --------------------------------------------------------
   Elle est montée dans `common.js` parce que DEUX surfaces en dépendent depuis que
   l'administration a sa page : la Bibliothèque pour dire « verrouillé par vous », la
   page d'administration pour DÉCLARER le pouvoir des administrateurs (AUTH-4). La
   recopier d'un fichier à l'autre aurait laissé les deux dériver — la faute mesurée le
   2026-09-07 sur deux procédures d'ajout de compte.

   Ce qui se teste ici est une PROPRIÉTÉ, au sens où `static/lib/` l'entend : la fonction
   ne touche ni au DOM ni au réseau, elle transforme une promesse en un couple, et sa
   table de vérité tient en quatre lignes. */

test("identite lit le login et les groupes administrateurs", async () => {
  identite.oublier();
  const a = await identite(Promise.resolve(
    { utilisateur: "lea", acces: { groupes_admin: ["bd-admins"] } }));
  assert.deepEqual(a, { login: "lea", groupes_admin: ["bd-admins"] });
});

test("identite MÉMOÏSE : la seconde lecture n'interroge plus", async () => {
  identite.oublier();
  await identite(Promise.resolve({ utilisateur: "lea", acces: { groupes_admin: [] } }));
  // Une source qui rendrait autre chose : si le mémo ne tenait pas, on la verrait passer.
  const b = await identite(Promise.resolve({ utilisateur: "AUTRE" }));
  assert.equal(b.login, "lea",
    "sans mémo, `/api/moi` serait interrogé une fois par appelant — et le miroir "
    + "`utilisateur` réécrit à chaque fois pour rien");
});

test("sans identité, elle rend un couple VIDE et n'échoue pas", async () => {
  // Mono-poste, ou proxy muet : un écran qui ne sait pas qui vous êtes doit s'afficher
  // quand même. C'est la portée vide d'AUTH-2 qui parle de l'accès, pas ce helper.
  for (const rien of [null, undefined, {}, { acces: {} }]) {
    identite.oublier();
    assert.deepEqual(await identite(Promise.resolve(rien)),
                     { login: null, groupes_admin: [] });
  }
});

test("une source en ÉCHEC ne casse pas l'écran", async () => {
  identite.oublier();
  assert.deepEqual(await identite(Promise.reject(new Error("réseau"))),
                   { login: null, groupes_admin: [] });
});


/* --- etatExport / noteExport (DROIT-2) --------------------------------------------
   Ce que la Recherche et l'Exploration disent de leurs exports, d'après `/api/moi`. La
   propriété qui compte le plus est la seconde : sans réponse lisible, l'écran ne fabrique
   PAS de refus — la garde est au serveur, et une note fausse qui dirait « vous n'avez aucun
   droit » serait pire qu'un bouton qu'on refuse. */
const { etatExport, noteExport } = require("../../static/lib/common.js");

test("etatExport lit les trois états", () => {
  for (const e of ["tout", "partiel", "rien"])
    assert.equal(etatExport({ acces: { exporter: e } }), e);
});

test("sans réponse lisible, etatExport ne fabrique pas de refus", () => {
  for (const x of [null, undefined, {}, { acces: {} }, { acces: { exporter: "RIEN" } },
                   { acces: { exporter: "toString" } }])
    assert.equal(etatExport(x), "tout", JSON.stringify(x));
});

test("noteExport ne parle que d'un export partiel ou impossible", () => {
  assert.equal(noteExport("tout"), "");
  assert.match(noteExport("partiel"), /n'emporte que/);
  assert.match(noteExport("rien"), /aucune/);
  assert.equal(noteExport("constructor"), "");
});
