/* Tests unitaires des gestes sur un tag (static/lib/gestes-tag.js, ANN-8).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Ce que l'écran OFFRE se décide ici : un geste offert à tort se découvre par un 403, un
   geste retenu à tort ne se découvre pas du tout. Chaque test vise une façon de rouvrir
   l'un ou l'autre — et les phrases, que personne ne relit, disent le nombre que le serveur
   a rendu. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const G = require("../../static/lib/gestes-tag.js");

const COLS = [{ id: 1, ecrivable: true }, { id: 2, ecrivable: false }];

test("modifier un terme : local, il faut écrire dans SA collection ; global, quelque part", () => {
  assert.equal(G.modifiable({ collection_id: 1 }, COLS), true);
  assert.equal(G.modifiable({ collection_id: 2 }, COLS), false);
  assert.equal(G.modifiable({ collection_id: 3 }, COLS), false);   // collection non listée
  assert.equal(G.modifiable({ collection_id: null }, COLS), true);
  assert.equal(G.modifiable({ collection_id: null }, [{ id: 2, ecrivable: false }]), false);
  assert.equal(G.modifiable({ collection_id: null }, undefined), false);
});

test("remaniable : renommer, fusionner, supprimer — tout ou rien", () => {
  assert.deepEqual(G.gestesOfferts({ remaniable: true, frequence: 5 }, false),
                   { renommer: true, fusionner: true, supprimer: true });
  assert.deepEqual(G.gestesOfferts({ remaniable: false, frequence: 5 }, true),
                   { renommer: false, fusionner: false, supprimer: false });
});

test("un tag inutilisé se supprime par qui le modifie, sans être remaniable", () => {
  assert.deepEqual(G.gestesOfferts({ remaniable: false, frequence: 0 }, true),
                   { renommer: false, fusionner: false, supprimer: true });
  assert.equal(G.gestesOfferts({ remaniable: false, frequence: 0 }, false).supprimer, false);
  assert.equal(G.gestesOfferts({ remaniable: false, frequence: 1 }, true).supprimer, false);
});

test("une clé absente ou d'une autre forme n'offre rien", () => {
  for (const r of [undefined, null, "true", 1]) {
    const g = G.gestesOfferts({ remaniable: r, frequence: 3 }, true);
    assert.deepEqual(g, { renommer: false, fusionner: false, supprimer: false }, String(r));
  }
});

test("la fusion ne propose que des cibles au moins aussi visibles, sans le tag lui-même", () => {
  const tags = [
    { id: 1, label: "zèbre", collection_id: null },
    { id: 2, label: "âne", collection_id: 7 },
    { id: 3, label: "bœuf", collection_id: 8 },
    { id: 4, label: "chat", collection_id: 7 },
    { id: 5, label: "abeille", collection_id: null },
  ];
  assert.deepEqual(G.ciblesDeFusion(tags[3], tags).map((t) => t.id), [5, 2, 1]);
  assert.deepEqual(G.ciblesDeFusion(tags[0], tags).map((t) => t.id), [5]);
  assert.deepEqual(G.ciblesDeFusion(tags[2], tags).map((t) => t.id), [5, 1]);
});

test("la confirmation dit le nombre rendu par le serveur", () => {
  assert.equal(G.confirmerSuppression({ label: "x", regions: 0 }),
               "Supprimer le tag « x » ? Aucune région ne le porte.");
  assert.equal(G.confirmerSuppression({ label: "x", regions: 1 }),
               "Supprimer le tag « x » ? Il sera retiré de 1 région.");
  assert.equal(G.confirmerSuppression({ label: "x", regions: 12 }),
               "Supprimer le tag « x » ? Il sera retiré de 12 régions.");
  const cible = { id: 2, label: "y" };
  assert.equal(G.confirmerFusion({ label: "x", cible, regions: 3, deja: 1 }),
               "Fusionner « x » dans « y » ? 3 régions passeront à « y » (1 le porte déjà), " +
               "et « x » disparaîtra.");
  assert.equal(G.confirmerFusion({ label: "x", cible, regions: 1, deja: 0 }),
               "Fusionner « x » dans « y » ? 1 région passera à « y », et « x » disparaîtra.");
  assert.equal(G.confirmerFusion({ label: "x", cible, regions: 0, deja: 0 }),
               "Fusionner « x » dans « y » ? Aucune région ne porte « x » : il disparaîtra.");
});

test("la réussite dit ce qui a été fait", () => {
  assert.equal(G.reussiteSuppression({ label: "x", regions: 0 }), "Tag « x » supprimé.");
  assert.equal(G.reussiteSuppression({ label: "x", regions: 2 }),
               "Tag « x » supprimé et retiré de 2 régions.");
  assert.equal(G.reussiteFusion({ label: "x", cible: { label: "y" }, regions: 1 }),
               "« x » fusionné dans « y » (1 région).");
  assert.equal(G.reussiteRenommage("colere", { label: "colère" }),
               "Tag « colere » renommé « colère ».");
});

test("chaque geste a son infobulle", () => {
  for (const g of ["renommer", "fusionner", "supprimer"]) assert.ok(G.INFOBULLES[g], g);
});
