/* Tests purs de static/lib/signal-planche.js — le signal de la planche ouverte (CONC-4). */
const test = require("node:test");
const assert = require("node:assert/strict");
const S = require("../../static/lib/signal-planche.js");

const vide = () => ({ tout: false, ids: new Set() });
const touche = (...ids) => ({ tout: false, ids: new Set(ids) });

test("l'intervalle est raisonnable : ni une scrutation, ni une heure", () => {
  assert.ok(S.INTERVALLE_MS >= 10000 && S.INTERVALLE_MS <= 120000, S.INTERVALLE_MS);
});

test("une lecture ne touche rien", () => {
  assert.equal(S.regionsTouchees("GET", "/api/regions/4/annotation", null, 1), null);
});

test("une écriture sur une région la touche, elle seule ; sa suppression, son sous-arbre", () => {
  assert.deepEqual(S.regionsTouchees("PUT", "/api/regions/4", {}, 1), { ids: [4], sousArbre: false });
  assert.deepEqual(S.regionsTouchees("PUT", "/api/regions/4/annotation", {}, 1),
                   { ids: [4], sousArbre: false });
  assert.deepEqual(S.regionsTouchees("DELETE", "/api/regions/4/locuteur?personnage_vu=2", null, 1),
                   { ids: [4], sousArbre: false });
  assert.deepEqual(S.regionsTouchees("DELETE", "/api/regions/4", null, 1), { ids: [4], sousArbre: true });
});

test("une région créée sur la planche ouverte : son identifiant vient de la réponse", () => {
  assert.deepEqual(S.regionsTouchees("POST", "/api/planches/7/regions", { id: 41 }, 7),
                   { ids: [41], sousArbre: false });
  assert.deepEqual(S.regionsTouchees("POST", "/api/planches/7/regions", null, 7), { tout: true });
  assert.equal(S.regionsTouchees("POST", "/api/planches/8/regions", { id: 41 }, 7), null);
});

test("ce qui ne change l'empreinte d'aucune région ne touche rien", () => {
  for (const [m, c] of [["POST", "/api/personnages"], ["PUT", "/api/personnages/3"],
                        ["PUT", "/api/personnages/3/attributs"],
                        ["DELETE", "/api/personnages/3/alignements/2"],
                        ["PATCH", "/api/tags/5/lexique"],
                        ["POST", "/api/attributs/dimensions"],
                        ["POST", "/api/attributs/dimensions/2/valeurs"],
                        ["PATCH", "/api/planches/7/verrou"], ["PATCH", "/api/planches/7/validation"],
                        ["PUT", "/api/regions/4/tokens/2"], ["POST", "/api/regions/4/grammaire/valider"],
                        ["POST", "/api/albums/2/import"], ["POST", "/api/sharedocs/importer"],
                        ["POST", "/api/undo/passer"]]) {
    assert.equal(S.regionsTouchees(m, c, {}, 7), null, `${m} ${c}`);
  }
});

test("ce que le module ne sait pas placer a tout touché : jamais un signal faux", () => {
  for (const [m, c] of [["POST", "/api/undo"], ["POST", "/api/planches/7/segmenter"],
                        ["POST", "/api/regions/4/deplacer"],
                        ["POST", "/api/planches/7/reordonner"], ["DELETE", "/api/personnages/3"],
                        ["POST", "/api/personnages/3/fusion"], ["PUT", "/api/tags/5"],
                        ["POST", "/api/inconnue"]]) {
    assert.deepEqual(S.regionsTouchees(m, c, {}, 7), { tout: true }, `${m} ${c}`);
  }
});

test("une adresse absolue se lit comme son chemin", () => {
  assert.deepEqual(S.regionsTouchees("PUT", "http://127.0.0.1:8000/api/regions/9", {}, 1),
                   { ids: [9], sousArbre: false });
});

test("rien n'a changé : rien à signaler, la base reste", () => {
  const base = { 1: "a", 2: "b" };
  const r = S.comparer(base, { 1: "a", 2: "b" }, vide());
  assert.equal(S.nombre(r.autres), 0);
  assert.deepEqual(r.base, base);
});

test("créée, modifiée, supprimée ailleurs : chacune nommée, triée", () => {
  const r = S.comparer({ 1: "a", 2: "b", 3: "c" }, { 1: "a", 2: "B", 5: "e", 4: "d" }, vide());
  assert.deepEqual(r.autres, { creees: [4, 5], modifiees: [2], supprimees: [3] });
  assert.equal(S.nombre(r.autres), 4);
});

test("l'écart d'ailleurs RESTE dans la base : le signal dure jusqu'à Actualiser", () => {
  const r1 = S.comparer({ 1: "a", 2: "b" }, { 1: "a", 2: "B", 3: "c" }, vide());
  assert.deepEqual(r1.base, { 1: "a", 2: "b" });
  const r2 = S.comparer(r1.base, { 1: "a", 2: "B", 3: "c" }, vide());
  assert.deepEqual(r2.autres, { creees: [3], modifiees: [2], supprimees: [] });
  // L'autre revient exactement à ce qu'on voyait, et retire sa région : plus rien.
  const r3 = S.comparer(r2.base, { 1: "a", 2: "b" }, vide());
  assert.equal(S.nombre(r3.autres), 0);
});

test("ce que l'écran a touché est adopté, sans se signaler", () => {
  const r = S.comparer({ 1: "a", 2: "b" }, { 1: "A", 2: "B", 9: "z" }, touche(1, 9));
  assert.deepEqual(r.autres, { creees: [], modifiees: [2], supprimees: [] });
  assert.deepEqual(r.base, { 1: "A", 2: "b", 9: "z" });
  const sup = S.comparer({ 1: "a", 2: "b" }, { 2: "b" }, touche(1));
  assert.equal(S.nombre(sup.autres), 0);
  assert.deepEqual(sup.base, { 2: "b" });
});

test("tout touché : tout est adopté, rien n'est signalé", () => {
  const r = S.comparer({ 1: "a" }, { 1: "A", 2: "b" }, { tout: true, ids: new Set() });
  assert.equal(S.nombre(r.autres), 0);
  assert.deepEqual(r.base, { 1: "A", 2: "b" });
});

test("l'infobulle compte et accorde, et se tait quand il n'y a rien", () => {
  assert.equal(S.titre({ creees: [], modifiees: [], supprimees: [] }), "");
  assert.equal(S.titre({ creees: [4], modifiees: [2, 3], supprimees: [] }),
               "La planche a changé ailleurs : 2 régions modifiées, 1 créée. "
               + "Actualiser la recharge, sans perdre votre saisie.");
  assert.equal(S.titre({ creees: [], modifiees: [], supprimees: [7] }),
               "La planche a changé ailleurs : 1 région supprimée. "
               + "Actualiser la recharge, sans perdre votre saisie.");
  assert.equal(S.titre({ creees: [1, 2], modifiees: [], supprimees: [3, 4] }),
               "La planche a changé ailleurs : 2 régions créées, 2 supprimées. "
               + "Actualiser la recharge, sans perdre votre saisie.");
});

test("le module se charge sans document ni fenêtre", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(typeof window, "undefined");
});
