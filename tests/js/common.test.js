/* Tests unitaires de la logique pure de static/lib/common.js (escapeHtml,
   messageErreur).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).
   $ / apiGet / apiSend / toast touchent DOM/fetch à l'appel → non testés ici. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { escapeHtml, messageErreur, identite, serieTome } = require("../../static/lib/common.js");

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
  for (const vide of [{}, null, undefined, { detail: "" }, { detail: [] }, { detail: 42 },
                      { detail: {} }, { detail: { message: "" } }, { detail: { message: 7 } }]) {
    assert.equal(messageErreur(vide, "Service Unavailable"), "Service Unavailable");
  }
});

test("un refus STRUCTURÉ montre son message, pas le statut HTTP", () => {
  // CONC-3 : le 409 d'une version périmée et le 410 d'une région supprimée portent un
  // OBJET. Lu comme une chaîne, il affichait « Conflict » ou « Gone » — rien d'utile.
  const conflit = { detail: { message: "Conflit : la note a été modifiée par Bob Martin.",
                              conflit: { champ: "note" } } };
  assert.equal(messageErreur(conflit, "Conflict"),
               "Conflit : la note a été modifiée par Bob Martin.");
  const supprimee = { detail: { message: "Cette région a été supprimée par Alice.",
                                suppression: { id: 4 } } };
  assert.equal(messageErreur(supprimee, "Gone"), "Cette région a été supprimée par Alice.");
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


test("serieTome : la série et son rang, tels qu'on les lit devant le titre", () => {
  assert.equal(serieTome({ serie: "Tintin", tome: "3" }), "Tintin · T3");
  assert.equal(serieTome({ serie: "Tintin", tome: "HS" }), "Tintin · HS");        // texte libre : tel quel
  assert.equal(serieTome({ serie: "Tintin", tome: "Intégrale" }), "Tintin · Intégrale");
  assert.equal(serieTome({ serie: "Tintin", tome: null }), "Tintin");
  assert.equal(serieTome({ serie: null, tome: "3" }), "T3");                      // le tome reste seul
  assert.equal(serieTome({ serie: " Tintin ", tome: " 3 " }), "Tintin · T3");     // espaces ignorés
  assert.equal(serieTome({ serie: "", tome: "" }), "");
  assert.equal(serieTome({}), "");
  assert.equal(serieTome(null), "");
});


/* ---- pendantEnvoi : un envoi se voit sur son bouton (COL-3, tranche 3b) ---- */
const { pendantEnvoi } = require("../../static/lib/common.js");

/* Une doublure de bouton : ce que la fonction lit et écrit, rien de plus. */
function doublureBouton(texte, { largeur = 120, desactive = false } = {}) {
  const attrs = new Map();
  return {
    textContent: texte,
    disabled: desactive,
    style: { width: "" },
    getBoundingClientRect: () => ({ width: largeur }),
    getAttribute: (n) => (attrs.has(n) ? attrs.get(n) : null),
    setAttribute: (n, v) => attrs.set(n, String(v)),
    removeAttribute: (n) => attrs.delete(n),
  };
}

test("pendantEnvoi : « Envoi… », aria-busy et la largeur gardée PENDANT la requête", async () => {
  const b = doublureBouton("Accepter", { largeur: 137.5 });
  let vu = null;
  const r = await pendantEnvoi(b, async () => {
    vu = { texte: b.textContent, busy: b.getAttribute("aria-busy"),
           desactive: b.disabled, largeur: b.style.width };
    return 42;
  });
  assert.deepEqual(vu, { texte: "Envoi…", busy: "true", desactive: true, largeur: "137.5px" });
  assert.equal(r, 42);                                    // ce que rend l'envoi ressort tel quel
  assert.equal(b.textContent, "Accepter");
  assert.equal(b.getAttribute("aria-busy"), null);
  assert.equal(b.disabled, false);
  assert.equal(b.style.width, "");
});

test("pendantEnvoi : le libellé revient aussi quand la requête ÉCHOUE, et l'erreur ressort", async () => {
  const b = doublureBouton("Envoyer la demande");
  await assert.rejects(pendantEnvoi(b, async () => { throw new Error("refusé"); }), /refusé/);
  assert.equal(b.textContent, "Envoyer la demande");
  assert.equal(b.getAttribute("aria-busy"), null);
  assert.equal(b.disabled, false);
  assert.equal(b.style.width, "");
});

test("pendantEnvoi : un bouton déjà occupé ne relance rien (double clic)", async () => {
  const b = doublureBouton("Refuser");
  let appels = 0;
  let liberer;
  const premier = pendantEnvoi(b, () => { appels++; return new Promise((ok) => { liberer = ok; }); });
  const second = await pendantEnvoi(b, async () => { appels++; });
  assert.equal(second, undefined);
  assert.equal(appels, 1);
  assert.equal(b.textContent, "Envoi…");                 // le second n'a rien rendu trop tôt
  liberer("fait");
  assert.equal(await premier, "fait");
  assert.equal(b.textContent, "Refuser");
});

test("pendantEnvoi rend l'état d'avant : un bouton désactivé le reste, une largeur posée revient", async () => {
  const b = doublureBouton("Copier", { desactive: true });
  b.style.width = "9em";
  await pendantEnvoi(b, () => "x");                       // une valeur, pas une promesse
  assert.equal(b.disabled, true);
  assert.equal(b.style.width, "9em");
});

test("pendantEnvoi sans bouton envoie quand même", async () => {
  assert.equal(await pendantEnvoi(null, async () => "seul"), "seul");
});

test("pendantEnvoi : un bouton qu'on ne sait pas mesurer ne reçoit pas de largeur", async () => {
  const b = doublureBouton("Vu", { largeur: 0 });
  let largeur = null;
  await pendantEnvoi(b, () => { largeur = b.style.width; });
  assert.equal(largeur, "");
});
