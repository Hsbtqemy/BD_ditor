/* Tests unitaires de la logique de la page Annotation (static/lib/annotation.js, ANN-7,
   tranche 2). Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Ce fichier garde les RÈGLES du premier temps de la page : une planche rangée en cases
   dans l'ordre de lecture, les étiquettes, l'adresse et le lien vers l'Atelier, la taille
   d'une étiquette à l'écran, « Préparée » et le Contexte en lecture. Que la page s'en serve
   se joue dans un navigateur (tests/test_e2e_annotation_page.py). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

const A = require("../../static/lib/annotation.js");

test("le module se charge sans document, sans fenêtre, sans adresse et sans stockage", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(typeof window, "undefined");
  assert.equal(typeof location, "undefined");
  assert.equal(typeof localStorage, "undefined");
  const chemin = require.resolve("../../static/lib/annotation.js");
  delete require.cache[chemin];
  assert.equal(typeof require(chemin).casesDeLaPlanche, "function");
});

const R = (id, type, x, y, w, h, extra = {}) => ({ id, type, x, y, w, h, parent_id: null,
                                                   ordre: null, citation: null, ...extra });

test("une planche se range en cases, dans leur ordre de lecture, chacune avec ses zones", () => {
  const regions = [
    R(1, "case", 500, 0, 500, 500, { ordre: 2 }),
    R(2, "case", 0, 0, 500, 500, { ordre: 1 }),
    R(3, "bulle", 10, 10, 50, 50, { parent_id: 2, ordre: 2 }),
    R(4, "personnage", 100, 100, 50, 50, { parent_id: 2, ordre: 1 }),
    R(5, "cartouche", 510, 10, 50, 50, { parent_id: 1 }),
  ];
  const r = A.casesDeLaPlanche(regions, 1000, 1000);
  assert.deepEqual(r.map((e) => e.case.id), [2, 1]);
  assert.deepEqual(r[0].zones.map((z) => z.id), [4, 3]);
  assert.deepEqual(r[1].zones.map((z) => z.id), [5]);
});

test("les descendants d'une zone la suivent, à toute profondeur", () => {
  const regions = [
    R(1, "case", 0, 0, 100, 100, { ordre: 1 }),
    R(2, "personnage", 0, 0, 50, 50, { parent_id: 1, ordre: 1 }),
    R(3, "bulle", 0, 0, 10, 10, { parent_id: 2, ordre: 1 }),
    R(4, "bulle", 60, 60, 10, 10, { parent_id: 1, ordre: 2 }),
  ];
  assert.deepEqual(A.casesDeLaPlanche(regions, 100, 100)[0].zones.map((z) => z.id), [2, 3, 4]);
});

test("une région sans parent va à la case qui contient son centre", () => {
  const regions = [
    R(1, "case", 0, 0, 100, 100, { ordre: 1 }),
    R(2, "case", 100, 0, 100, 100, { ordre: 2 }),
    R(3, "bulle", 150, 40, 20, 20),
  ];
  const r = A.casesDeLaPlanche(regions, 200, 100);
  assert.equal(r.length, 2);
  assert.deepEqual(r[1].zones.map((z) => z.id), [3]);
  assert.deepEqual(r[0].zones, []);
});

test("ce qui ne tombe dans aucune case va à une case PSEUDO, la planche, en dernier", () => {
  const regions = [R(1, "case", 0, 0, 100, 100, { ordre: 1 }), R(2, "bulle", 300, 300, 20, 20)];
  const r = A.casesDeLaPlanche(regions, 400, 400);
  assert.equal(r.length, 2);
  assert.equal(r[1].case.pseudo, true);
  assert.equal(r[1].case.id, null);
  assert.deepEqual([r[1].case.w, r[1].case.h], [400, 400]);
  assert.deepEqual(r[1].zones.map((z) => z.id), [2]);
  // Une planche sans case : la case pseudo seule, et toutes les régions dedans.
  const seule = A.casesDeLaPlanche([R(7, "bulle", 1, 1, 5, 5)], 50, 60);
  assert.equal(seule.length, 1);
  assert.equal(seule[0].case.pseudo, true);
  assert.deepEqual(seule[0].zones.map((z) => z.id), [7]);
  // Une planche vide : une case pseudo, vide — jamais un rangement sans case.
  assert.equal(A.casesDeLaPlanche([], 50, 60).length, 1);
  // Des cases et rien hors d'elles : pas de case pseudo.
  assert.equal(A.casesDeLaPlanche([R(1, "case", 0, 0, 10, 10)], 10, 10).length, 1);
});

test("une case rangée sous une autre case reste une case, jamais une zone", () => {
  const regions = [R(1, "case", 0, 0, 100, 100, { ordre: 1 }),
                   R(2, "case", 10, 10, 20, 20, { parent_id: 1, ordre: 2 })];
  const r = A.casesDeLaPlanche(regions, 100, 100);
  assert.deepEqual(r.map((e) => e.case.id), [1, 2]);
  assert.deepEqual(r[0].zones, []);
});

test("une région ne se range qu'une fois", () => {
  const regions = [R(1, "case", 0, 0, 100, 100, { ordre: 1 }),
                   R(2, "bulle", 10, 10, 10, 10, { parent_id: 1 }),
                   R(3, "bulle", 20, 20, 10, 10, { parent_id: 99 })];   // parent absent
  const r = A.casesDeLaPlanche(regions, 100, 100);
  const toutes = r.flatMap((e) => e.zones.map((z) => z.id));
  assert.deepEqual(toutes.sort(), [2, 3]);
});

test("l'étiquette suit la citation, puis l'initiale et le rang par sorte", () => {
  assert.equal(A.etiquette(R(1, "case", 0, 0, 1, 1, { citation: { case: 3 } })), "c3");
  assert.equal(A.etiquette(R(2, "bulle", 0, 0, 1, 1, { citation: { case: 3, bulle: 2 } })), "b2");
  assert.equal(A.etiquette(R(3, "personnage", 0, 0, 1, 1), 2), "p2");
  assert.equal(A.etiquette({ pseudo: true, type: "case" }), "planche");
  const entree = { case: R(1, "case", 0, 0, 9, 9),
                   zones: [R(5, "personnage", 0, 0, 1, 1), R(6, "bulle", 0, 0, 1, 1),
                           R(7, "personnage", 0, 0, 1, 1)] };
  const e = A.etiquettesDeLaCase(entree);
  assert.deepEqual([e.get(5), e.get(6), e.get(7)], ["p1", "b1", "p2"]);
});

test("situer une région : sa case, et la zone (nulle pour la case elle-même)", () => {
  const r = A.casesDeLaPlanche([R(1, "case", 0, 0, 10, 10, { ordre: 1 }),
                                R(2, "bulle", 1, 1, 2, 2, { parent_id: 1 })], 10, 10);
  assert.deepEqual(A.situer(r, 1), { caseIx: 0, zoneId: null });
  assert.deepEqual(A.situer(r, "2"), { caseIx: 0, zoneId: 2 });
  assert.equal(A.situer(r, 99), null);
  assert.equal(A.situer(r, null), null);
});

test("le libellé d'une planche : son numéro éditorial, ou « paratexte »", () => {
  assert.equal(A.libellePlanche({ role: "recit", numero_editorial: 4, numero: 6 }), "planche 4");
  assert.equal(A.libellePlanche({ role: "couverture", numero_editorial: null, numero: 1 }),
               "paratexte · 1");
});

test("« Préparée » compte les zones de texte et dit la relecture", () => {
  const regions = [R(1, "case", 0, 0, 1, 1), R(2, "bulle", 0, 0, 1, 1),
                   R(3, "cartouche", 0, 0, 1, 1), R(4, "personnage", 0, 0, 1, 1)];
  assert.equal(A.preparation(regions, { statut: "faite" }), "2 zones de texte · relecture faite");
  assert.equal(A.preparation([R(2, "texte", 0, 0, 1, 1)], null), "1 zone de texte");
  assert.equal(A.preparation([], { statut: "a_faire" }), "0 zone de texte · relecture à faire");
  assert.equal(A.preparation([], { statut: "en_cours" }), "0 zone de texte · relecture en cours");
  assert.equal(A.preparation([], { statut: "autre" }), "0 zone de texte · relecture autre");
});

test("l'adresse de la page, aller et retour", () => {
  const qs = A.adresse({ collection: 3, album: 7, planche: 12, region: null });
  assert.equal(qs, "?collection=3&album=7&planche=12");
  assert.deepEqual(A.lireAdresse(qs), { collection: 3, album: 7, planche: 12, region: null });
  assert.equal(A.adresse({}), "");
  assert.deepEqual(A.lireAdresse("?collection=toutes&album=x&region=-2"),
                   { collection: "toutes", album: null, planche: null, region: null });
  assert.equal(A.adresse({ collection: "toutes", album: 2 }), "?collection=toutes&album=2");
});

test("le lien vers l'Atelier porte la zone, la collection et le retour", () => {
  const lien = A.lienAtelier({ collection: 3, album: 7, planche: 12, region: 40 },
                             "/annotation?album=7");
  const u = new URL(lien, "http://x");
  assert.equal(u.pathname, "/");
  assert.equal(u.searchParams.get("album"), "7");
  assert.equal(u.searchParams.get("planche"), "12");
  assert.equal(u.searchParams.get("region"), "40");
  assert.equal(u.searchParams.get("collection"), "3");
  assert.equal(u.searchParams.get("retour"), "/annotation?album=7");
  assert.equal(A.lienAtelier({}, null), "/");
});

test("une étiquette garde sa taille d'écran quelle que soit la case", () => {
  // Une case large dans une boîte de 600 × 300 : l'échelle est bornée par la largeur.
  const k = A.echelle({ w: 1200, h: 300 }, 600, 300);
  assert.equal(k, 0.5);
  assert.equal(A.taillePourEcran(12, k), 24);
  // Une case haute : bornée par la hauteur.
  assert.equal(A.echelle({ w: 100, h: 600 }, 600, 300), 0.5);
  // Une boîte pas encore mesurée : pas d'étiquette plutôt qu'une taille absurde.
  assert.equal(A.echelle({ w: 100, h: 100 }, 0, 300), 0);
  assert.equal(A.taillePourEcran(12, 0), null);
});

test("le recadrage d'une case dans le dérivé, en fond", () => {
  // Une case de 200 × 100 en (300, 50), sur une planche de 1000 × 500.
  assert.deepEqual(A.recadrage({ x: 300, y: 50, w: 200, h: 100 }, 1000, 500),
                   { taille: [500, 500], position: [37.5, 12.5] });
  // La planche entière (la case pseudo) : aucun décalage, aucune division par zéro.
  assert.deepEqual(A.recadrage({ x: 0, y: 0, w: 1000, h: 500 }, 1000, 500),
                   { taille: [100, 100], position: [0, 0] });
  assert.equal(A.recadrage({ x: 0, y: 0, w: 0, h: 10 }, 100, 100), null);
});

test("une zone est bornée à sa case", () => {
  const c = { x: 100, y: 100, w: 100, h: 100 };
  assert.deepEqual(A.dansLaCase({ x: 150, y: 150, w: 100, h: 20 }, c),
                   { x: 150, y: 150, w: 50, h: 20 });
  assert.deepEqual(A.dansLaCase({ x: 110, y: 110, w: 10, h: 10 }, c),
                   { x: 110, y: 110, w: 10, h: 10 });
  assert.equal(A.dansLaCase({ x: 300, y: 300, w: 10, h: 10 }, c), null);
});

test("le Contexte, en lecture : ce qui n'est pas du vocabulaire", () => {
  const bulle = R(2, "bulle", 0, 0, 1, 1);
  assert.deepEqual(A.contexte(bulle, { locuteur: { nom: "Tintin" }, note: "ironique" }),
                   [{ cle: "locuteur", libelle: "Locuteur", valeur: "Tintin" },
                    { cle: "note", libelle: "Note", valeur: "ironique" }]);
  assert.deepEqual(A.contexte(bulle, {}).map((l) => l.valeur), ["…", "…"]);
  assert.deepEqual(A.contexte(bulle, { locuteur: null, note: "" }).map((l) => l.valeur),
                   ["—", "—"]);
  const boite = R(3, "personnage", 0, 0, 1, 1);
  assert.deepEqual(A.contexte(boite, { personnage: { nom: "Milou" }, note: null })
    .map((l) => [l.cle, l.valeur]), [["personnage", "Milou"], ["note", "—"]]);
  assert.deepEqual(A.contexte(R(1, "case", 0, 0, 1, 1), { note: "nuit" }).map((l) => l.cle),
                   ["note"]);
  assert.deepEqual(A.contexte({ pseudo: true, type: "case" }, {}), []);
  assert.deepEqual(A.contexte(null, {}), []);
});

test("les mots d'une sorte : son nom et son article", () => {
  assert.equal(A.nomType("personnage"), "boîte personnage");
  assert.equal(A.deLa("bulle"), "de la bulle");
  assert.equal(A.deLa("cartouche"), "du cartouche");
  assert.equal(A.deLa("personnage"), "de la boîte personnage");
  assert.ok(A.estTexte("texte") && !A.estTexte("case"));
});
