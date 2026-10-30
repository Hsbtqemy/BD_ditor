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
  assert.deepEqual(A.lireAdresse(qs),
                   { collection: 3, album: 7, planche: 12, region: null, grille: null });
  assert.equal(A.adresse({}), "");
  assert.deepEqual(A.lireAdresse("?collection=toutes&album=x&region=-2"),
                   { collection: "toutes", album: null, planche: null, region: null,
                     grille: null });
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

test("le Contexte modifiable : le locuteur d'une zone de texte, la note de toute zone", () => {
  const g = (z, e) => [...A.gestesDuContexte(z, e)].sort();
  assert.deepEqual(g(R(2, "bulle", 0, 0, 1, 1), true), ["locuteur", "note"]);
  assert.deepEqual(g(R(2, "cartouche", 0, 0, 1, 1), true), ["locuteur", "note"]);
  assert.deepEqual(g(R(2, "texte", 0, 0, 1, 1), true), ["locuteur", "note"]);
  // Le personnage d'une boîte reste en lecture ; la case n'a qu'une note.
  assert.deepEqual(g(R(3, "personnage", 0, 0, 1, 1), true), ["note"]);
  assert.deepEqual(g(R(1, "case", 0, 0, 1, 1), true), ["note"]);
  // Rien en lecture, ni sur la case pseudo, ni sans zone.
  assert.deepEqual(g(R(2, "bulle", 0, 0, 1, 1), false), []);
  assert.deepEqual(g({ pseudo: true, type: "case" }, true), []);
  assert.deepEqual(g(null, true), []);
});

test("une note ne part que si elle change ce que l'écran a vu", () => {
  assert.equal(A.noteAEnvoyer("il jure", "il jure"), null);
  assert.equal(A.noteAEnvoyer("il jure  ", "il jure"), null);
  assert.equal(A.noteAEnvoyer("il jure", "il jure \n"), null);
  assert.equal(A.noteAEnvoyer("il jure fort ", "il jure"), "il jure fort");
  assert.equal(A.noteAEnvoyer("", "il jure"), "");
  assert.equal(A.noteAEnvoyer("", null), null);
  assert.equal(A.noteAEnvoyer(null, ""), null);
  assert.equal(A.noteAEnvoyer("x", undefined), "x");
  // Les espaces de TÊTE comptent : seule la fin est rognée.
  assert.equal(A.noteAEnvoyer(" il jure", "il jure"), " il jure");
});

test("les mots d'une sorte : son nom et son article", () => {
  assert.equal(A.nomType("personnage"), "boîte personnage");
  assert.equal(A.deLa("bulle"), "de la bulle");
  assert.equal(A.deLa("cartouche"), "du cartouche");
  assert.equal(A.deLa("personnage"), "de la boîte personnage");
  assert.ok(A.estTexte("texte") && !A.estTexte("case"));
});

/* ───────────── La grille, en lecture (commit 2) ─────────────
   Un plan à la forme de `grilles.plan`, FICTIF — le modèle du dépôt, réduit. */
const PLAN = {
  numero: 2, etat: "publiee", porte_sur: ["mots"], note: "deuxième jet",
  rubriques: [
    { cle: "sons", libelle: "A. Sons", parent_cle: null, chemin: ["sons"] },
    { cle: "sons > voix", libelle: "Voix", parent_cle: "sons", chemin: ["sons", "sons > voix"] },
    { cle: "provenance", libelle: "B. Provenance", parent_cle: null, chemin: ["provenance"] },
    { cle: "image", libelle: "E. Image", parent_cle: null, chemin: ["image"] },
  ],
  entrees: [
    { cle: "cri", libelle: "cri", forme: "simple", rubrique_cle: "sons > voix",
      rubriques: ["sons", "sons > voix"], definition: "un cri poussé par un personnage",
      structure: null, piege: "un cri n'est pas une onomatopée", exemples: ["AAAH !", "OUILLE"],
      cible_declaree: [], cibles: ["mots"], pose: "mots", cardinalite: "plusieurs",
      liste_cle: null, retiree: false, variantes: [] },
    { cle: "ton", libelle: "ton de voix", forme: "variantes", rubrique_cle: "sons > voix",
      rubriques: ["sons", "sons > voix"], definition: "le ton de toute la zone",
      structure: null, piege: null, exemples: [],
      cible_declaree: ["bulle", "cartouche", "texte"], cibles: ["bulle", "cartouche", "texte"],
      pose: "zone", cardinalite: "une", liste_cle: null, retiree: false,
      variantes: [{ cle: "chuchote", libelle: "chuchoté", definition: "à voix basse",
                    structure: null, piege: null, exemples: ["psst"] },
                  { cle: "crie", libelle: "crié", definition: "à pleine voix",
                    structure: "[majuscules]", piege: "pas un cri", exemples: [] }] },
    { cle: "origine", libelle: "origine du son", forme: "qualificatifs", rubrique_cle: "provenance",
      rubriques: ["provenance"], definition: "d'où vient le son", structure: null, piege: null,
      exemples: [], cible_declaree: [], cibles: ["mots"], pose: "mots", cardinalite: "plusieurs",
      liste_cle: "sources", retiree: false, variantes: [] },
    { cle: "regard", libelle: "regard caméra", forme: "simple", rubrique_cle: "image",
      rubriques: ["image"], definition: "le personnage regarde le lecteur", structure: null,
      piege: null, exemples: [], cible_declaree: ["case"], cibles: ["case"], pose: "zone",
      cardinalite: "plusieurs", liste_cle: null, retiree: false, variantes: [] },
    { cle: "vieux", libelle: "ancienne entrée", forme: "simple", rubrique_cle: "image",
      rubriques: ["image"], definition: "retirée", structure: null, piege: null, exemples: [],
      cible_declaree: [], cibles: ["mots"], pose: "mots", cardinalite: "plusieurs",
      liste_cle: null, retiree: true, variantes: [] },
    { cle: "orpheline", libelle: "l’écho", forme: "simple", rubrique_cle: null, rubriques: [],
      definition: null, structure: null, piege: null, exemples: [], cible_declaree: [],
      cibles: ["mots"], pose: "mots", cardinalite: "plusieurs", liste_cle: null,
      retiree: false, variantes: [] },
  ],
  listes: [{ cle: "sources", libelle: "source du son",
             qualificatifs: [{ cle: "objet", libelle: "objet", definition: "un objet de la case" },
                             { cle: "hors-champ", libelle: "hors champ",
                               definition: "une source qu'on ne voit pas" }] }],
};

test("normaliser : accents, casse, apostrophes et espaces ne comptent pas", () => {
  assert.equal(A.normaliser("  L’ÉCHO   d'été "), "l'echo d'ete");
  assert.equal(A.normaliser(null), "");
});

test("le masque est celui de la collection choisie, jamais de « toutes »", () => {
  const actives = [{ id: 1, nom: "A", masquee_dans: [7] }, { id: 2, nom: "B", masquee_dans: [] }];
  assert.deepEqual(A.grillesVisibles(actives, 7).map((g) => g.id), [2]);
  assert.deepEqual(A.grillesVisibles(actives, "toutes").map((g) => g.id), [1, 2]);
  assert.deepEqual(A.grillesVisibles(actives, 8).map((g) => g.id), [1, 2]);
  assert.equal(A.masquee(actives[0], 7), true);
  assert.equal(A.grilleAOuvrir([{ id: 2 }, { id: 3 }], "3"), 3);
  assert.equal(A.grilleAOuvrir([{ id: 2 }, { id: 3 }], 1), 2);
  assert.equal(A.grilleAOuvrir([], 1), null);
});

test("l'infobulle d'un onglet dit la version, son état et sa note", () => {
  assert.equal(A.infobulleGrille({ nom: "Signaux", version: { numero: 2, etat: "publiee" } }, PLAN),
               "Signaux · version 2 (publiée) — deuxième jet");
  assert.equal(A.infobulleGrille({ nom: "Lieux", ouverte: true, version: { numero: 1 } }, null),
               "Lieux · ouverte : elle s'enrichit en posant");
});

test("le plan en arbre : rubriques imbriquées, entrées retirées absentes, orphelines à part", () => {
  const t = A.arbre(PLAN);
  assert.deepEqual(t.map((n) => n.cle), ["sons", "provenance", "image", ""]);
  assert.deepEqual(t[0].entrees, []);
  assert.deepEqual(t[0].enfants.map((n) => [n.cle, n.profondeur]), [["sons > voix", 1]]);
  assert.deepEqual(t[0].enfants[0].entrees.map((e) => e.cle), ["cri", "ton"]);
  assert.deepEqual(t[2].entrees.map((e) => e.cle), ["regard"]);
  assert.deepEqual(t[3].entrees.map((e) => e.cle), ["orpheline"]);
  assert.deepEqual(A.entreesSous(t[0]).map((e) => e.cle), ["cri", "ton"]);
  assert.equal(A.chemin(PLAN, PLAN.entrees[0]), "A. Sons › Voix");
});

test("« Afficher » propose les rubriques de tête, et rien pour une seule", () => {
  assert.deepEqual(A.vuesAfficher(PLAN).map((v) => v.cle), ["sons", "provenance", "image"]);
  const une = { rubriques: [PLAN.rubriques[2]], entrees: [PLAN.entrees[2]] };
  assert.deepEqual(A.vuesAfficher(une), []);
});

test("les relevés de la zone et de son contexte", () => {
  const rel = [{ id: 1, region_id: 10, planche_id: null }, { id: 2, region_id: 5, planche_id: null },
               { id: 3, region_id: null, planche_id: 99 }, { id: 4, region_id: 11, planche_id: null }];
  const caseR = { id: 5, type: "case" }, bulle = { id: 10, type: "bulle" };
  const z = A.relevesDeLaZone(rel, bulle, caseR, 99);
  assert.deepEqual(z.ici.map((r) => r.id), [1]);
  assert.deepEqual(z.contexte.map((r) => r.id), [2, 3]);
  const c = A.relevesDeLaZone(rel, caseR, caseR, 99);
  assert.deepEqual([c.ici.map((r) => r.id), c.contexte.map((r) => r.id)], [[2], [3]]);
  const p = A.relevesDeLaZone(rel, { pseudo: true, id: null }, null, 99);
  assert.deepEqual([p.ici.map((r) => r.id), p.contexte], [[3], []]);
});

test("« n ici » : par grille, par rubrique (descendants compris), par entrée", () => {
  const rel = [{ grille_id: 1, entree_cle: "cri" }, { grille_id: 1, entree_cle: "cri" },
               { grille_id: 1, entree_cle: "ton" }, { grille_id: 1, entree_cle: "origine" },
               { grille_id: 2, entree_cle: "cri" }];
  const n = A.compter(rel, 1, PLAN);
  assert.equal(n.total, 4);
  assert.equal(n.parEntree.get("cri"), 2);
  assert.equal(n.parRubrique.get("sons"), 3);
  assert.equal(n.parRubrique.get("sons > voix"), 3);
  assert.equal(n.parRubrique.get("provenance"), 1);
  assert.equal(n.parRubrique.get("image"), 0);
});

test("« plusieurs » sur une cible entière seulement ; la marque d'une cible propre", () => {
  const [cri, ton, origine, regard] = PLAN.entrees;
  assert.equal(A.marquePlusieurs(cri), false);
  assert.equal(A.marquePlusieurs(ton), false);
  assert.equal(A.marquePlusieurs(regard), true);
  assert.equal(A.marquePlusieurs({ pose: "planche", cardinalite: "plusieurs" }), true);
  assert.equal(A.marqueCible(cri), null);
  assert.equal(A.marqueCible(origine), null);
  assert.equal(A.marqueCible(ton), "toute la zone");
  assert.equal(A.marqueCible(regard), "la case");
  assert.equal(A.marqueCible({ cible_declaree: ["planche"], cibles: ["planche"], pose: "planche" }),
               "la planche");
  assert.equal(A.marqueCible({ cible_declaree: ["personnage"], cibles: ["personnage"], pose: "zone" }),
               "la boîte");
});

test("le filtre : accents, exemples, variantes, et les meilleurs d'abord", () => {
  assert.deepEqual(A.chercher(PLAN, ""), []);
  assert.deepEqual(A.chercher(PLAN, "cri").map((r) => [r.entree_cle, r.variante_cle]),
                   [["cri", null], ["ton", "crie"]]);
  assert.deepEqual(A.chercher(PLAN, "CRIÉ").map((r) => r.libelle), ["crié"]);
  assert.deepEqual(A.chercher(PLAN, "ouille").map((r) => [r.libelle, r.score]), [["cri", 3]]);
  assert.deepEqual(A.chercher(PLAN, "l'echo").map((r) => r.entree_cle), ["orpheline"]);
  assert.deepEqual(A.chercher(PLAN, "ancienne"), []);
  const v = A.chercher(PLAN, "psst")[0];
  assert.equal(v.chemin, "A. Sons › Voix › ton de voix");
  assert.equal(v.exemple, "psst");
});

test("le filtre range les résultats par score, puis dans l'ordre du plan", () => {
  const simple = (cle, libelle, definition) => ({
    cle, libelle, definition, forme: "simple", rubriques: [], exemples: [], variantes: [],
    retiree: false });
  const plan = { rubriques: [], listes: [],
                 entrees: [simple("a", "zéro", "un chat"), simple("b", "chat noir", null),
                           simple("c", "le chat", null)] };
  assert.deepEqual(A.chercher(plan, "chat").map((r) => [r.entree_cle, r.score]),
                   [["b", 0], ["c", 1], ["a", 3]]);
});

test("le filtre : « X par Y », et un qualificatif lu avec son phénomène", () => {
  assert.deepEqual(A.chercher(PLAN, "origine par hors").map((r) => [r.qualificatif_cle, r.libelle]),
                   [["hors-champ", "origine du son par hors champ"]]);
  assert.deepEqual(A.chercher(PLAN, "origine objet").map((r) => [r.qualificatif_cle, r.score]),
                   [["objet", 2]]);
  assert.deepEqual(A.chercher(PLAN, "origine").map((r) => r.qualificatif_cle), [null]);
});

test("la ligne du guide d'une entrée et d'une variante", () => {
  const cri = A.ligneDuGuide(PLAN, "cri");
  assert.equal(cri.libelle, "cri");
  assert.equal(cri.chemin, "A. Sons › Voix");
  assert.deepEqual(cri.exemples, ["AAAH !", "OUILLE"]);
  assert.equal(cri.piege, "un cri n'est pas une onomatopée");
  const ton = A.ligneDuGuide(PLAN, "ton");
  assert.deepEqual(ton.exemples, ["chuchoté : psst"]);
  const crie = A.ligneDuGuide(PLAN, "ton", "crie");
  assert.deepEqual([crie.libelle, crie.definition, crie.structure, crie.piege, crie.chemin],
                   ["crié", "à pleine voix", "[majuscules]", "pas un cri",
                    "A. Sons › Voix › ton de voix"]);
  assert.deepEqual(A.ligneDuGuide(PLAN, "origine").qualificatifs,
                   { libelle: "source du son", termes: ["objet", "hors champ"] });
  assert.equal(A.ligneDuGuide(PLAN, "absente"), null);
});

test("le guide complet, produit depuis la grille", () => {
  const g = A.guideComplet(PLAN);
  assert.deepEqual(g.sections.map((s) => [s.titre, s.niveau, s.lignes.length]),
                   [["A. Sons", 0, 0], ["Voix", 1, 2], ["B. Provenance", 0, 1],
                    ["E. Image", 0, 1], ["Sans rubrique", 0, 1]]);
  const ton = g.sections[1].lignes[1];
  assert.deepEqual(ton.aPoser.map((x) => x.libelle), ["chuchoté", "crié"]);
  assert.deepEqual(ton.exemples, ["psst"]);
  assert.equal(g.sections[2].lignes[0].aPoser[0].structure, "+ source du son");
  assert.deepEqual(g.listes[0].termes.map((t) => t.libelle), ["objet", "hors champ"]);
  assert.deepEqual(g.pieges.map((p) => p.entree), ["cri", "ton de voix › crié"]);
});

test("l'adresse porte la grille", () => {
  assert.equal(A.adresse({ album: 2, grille: 5 }), "?album=2&grille=5");
  assert.equal(A.lireAdresse("?grille=5").grille, 5);
});

/* ───────────── Désigner et poser (commit 3) ───────────── */
const MOTS = [{ rang: 0, forme: "IL" }, { rang: 1, forme: "NE" }, { rang: 2, forme: "VIENT" },
              { rang: 3, forme: "PAS" }];
const rel = (id, extra) => ({ id, region_id: 10, planche_id: null, grille_id: 1,
                              entree_cle: "cri", variante_cle: null, qualificatifs: [],
                              mots: [], ...extra });
const motsDe = (...r) => r.map((x, i) => ({ position: i, rang: x, forme: "?" }));

test("désigner : plage, bascule (passage à trou), texte d'un passage", () => {
  assert.deepEqual(A.plage(3, 1), [1, 2, 3]);
  assert.deepEqual(A.basculer([1, 2], 2), [1]);
  assert.deepEqual(A.basculer([1], 3), [1, 3]);
  assert.equal(A.texteDuPassage(MOTS, [3, 1]), "NE … PAS");
  assert.equal(A.texteDuPassage(MOTS, [0, 1, 2]), "IL NE VIENT");
  assert.equal(A.memesMots([2, 1], [1, 2]), true);
  assert.equal(A.memesMots([1], [1, 2]), false);
  assert.deepEqual(A.rangs(new Set([3, 1, 1, -1])), [1, 3]);
});

test("les couloirs : deux passages qui se chevauchent ne partagent pas un couloir", () => {
  const c = A.couloirs([rel(1, { mots: motsDe(0, 1) }), rel(2, { mots: motsDe(1, 3) }),
                        rel(3, { mots: motsDe(3) }), rel(4, { mots: motsDe(0, 3) }),
                        rel(5, {})]);
  // Le plus long d'abord à début égal : 4 (0–3) au couloir 0, 1 (0–1) au 1 ; 2 (1–3) au 2 ;
  // 3 (3) reprend le couloir 1, libre depuis 1.
  assert.deepEqual([c.get(4), c.get(1), c.get(2), c.get(3)], [0, 1, 2, 1]);
  assert.equal(c.has(5), false);
});

test("la teinte suit la rubrique de tête", () => {
  assert.equal(A.teinte(PLAN, "cri", 7), 0);
  assert.equal(A.teinte(PLAN, "origine", 7), 1);
  assert.equal(A.teinte(PLAN, "regard", 2), 0);      // rang 2, palette de 2
  assert.equal(A.teinte(PLAN, "orpheline", 7), null);
});

test("« Porte sur » : ce que la grille vise depuis la zone", () => {
  const bulle = { id: 10, type: "bulle" }, laCase = { id: 5, type: "case" };
  assert.deepEqual(A.optionsPorteSur(PLAN, bulle, laCase).map((o) => o.cle),
                   ["mots", "zone", "case"]);
  assert.equal(A.optionsPorteSur(PLAN, bulle, laCase)[1].libelle, "toute la bulle");
  assert.deepEqual(A.optionsPorteSur(PLAN, laCase, laCase).map((o) => o.cle), ["case"]);
  const planche = { entrees: [{ cle: "a", pose: "planche", cibles: ["planche"] }] };
  assert.deepEqual(A.optionsPorteSur(planche, bulle, laCase).map((o) => o.cle), ["planche"]);
});

test("la cible d'un geste : mots, zone, case, planche, et ce qui manque", () => {
  const [cri, ton, , regard] = PLAN.entrees;
  const bulle = { id: 10, type: "bulle" }, laCase = { id: 5, type: "case" };
  const ctx = { porte: "mots", zone: bulle, caseRegion: laCase, plancheId: 9, mots: [2, 1] };
  assert.deepEqual(A.cibleDePose(cri, ctx), { region_id: 10, mots: [1, 2] });
  assert.match(A.cibleDePose(cri, { ...ctx, mots: [] }).erreur, /désignez/);
  assert.match(A.cibleDePose(cri, { ...ctx, zone: laCase }).erreur, /bulle/);
  assert.deepEqual(A.cibleDePose(ton, ctx), { region_id: 10 });          // toute la zone
  assert.deepEqual(A.cibleDePose(regard, ctx), { region_id: 5 });        // la case
  assert.match(A.cibleDePose(ton, { ...ctx, zone: laCase }).erreur, /bulle/);
  assert.deepEqual(A.cibleDePose({ pose: "planche", libelle: "p" }, ctx), { planche_id: 9 });
  assert.match(A.cibleDePose({ pose: "entite", libelle: "p" }, ctx).erreur, /partout/);
  // Une entrée qui vise la case OU la bulle suit « Porte sur ».
  const deux = { pose: "zone", cibles: ["bulle", "case"], libelle: "x" };
  assert.deepEqual(A.cibleDePose(deux, ctx), { region_id: 10 });
  assert.deepEqual(A.cibleDePose(deux, { ...ctx, porte: "case" }), { region_id: 5 });
  // La case PSEUDO (la planche entière) n'est pas une région : rien ne s'y pose « sur la case ».
  const pseudo = { id: null, type: "case", pseudo: true };
  assert.match(A.cibleDePose(regard, { ...ctx, zone: pseudo, caseRegion: pseudo }).erreur, /case/);
});

test("les relevés d'une entrée sur CETTE cible", () => {
  const l = [rel(1, { mots: motsDe(1, 2) }), rel(2, { mots: motsDe(1) }),
             rel(3, { entree_cle: "ton" }), rel(4, { region_id: null, planche_id: 9,
                                                    entree_cle: "ambiance" })];
  assert.deepEqual(A.relevesSurLaCible(l, 1, "cri", { region_id: 10, mots: [2, 1] })
    .map((r) => r.id), [1]);
  assert.deepEqual(A.relevesSurLaCible(l, 1, "ton", { region_id: 10 }).map((r) => r.id), [3]);
  assert.deepEqual(A.relevesSurLaCible(l, 1, "ambiance", { planche_id: 9 }).map((r) => r.id), [4]);
  assert.deepEqual(A.relevesSurLaCible(l, 2, "cri", { region_id: 10, mots: [1, 2] }), []);
  assert.deepEqual(A.relevesSurLaCible(l, 1, "cri", { erreur: "x" }), []);
});

test("le geste : poser, retirer, remplacer une variante, ajouter un qualificatif", () => {
  const [cri, ton, origine, regard] = PLAN.entrees;
  assert.deepEqual(A.geste(cri, [], {}), { action: "poser", corps: {} });
  const r = rel(7, { mots: motsDe(1) });
  assert.deepEqual(A.geste(cri, [r], {}),
                   { action: "retirer", releve: r,
                     vu: { variante_cle: null, qualificatifs: [], mots: [1] } });
  // Une entrée « plusieurs » sur une cible entière ajoute à chaque clic.
  assert.equal(A.geste(regard, [rel(8, {})], {}).action, "poser");
  assert.deepEqual(A.geste(ton, [], { variante: "crie" }),
                   { action: "poser", corps: { variante_cle: "crie" } });
  const t = rel(9, { entree_cle: "ton", variante_cle: "crie" });
  assert.equal(A.geste(ton, [t], { variante: "crie" }).action, "retirer");
  assert.deepEqual(A.geste(ton, [t], { variante: "chuchote" }),
                   { action: "modifier", releve: t, corps: { variante_cle: "chuchote" },
                     vu: { variante_cle: "crie" } });
  assert.deepEqual(A.geste(origine, [], {}), { action: "poser", corps: { qualificatifs: [] } });
  assert.deepEqual(A.geste(origine, [], { qualificatif: "objet" }),
                   { action: "poser", corps: { qualificatifs: ["objet"] } });
  const o = rel(10, { entree_cle: "origine", qualificatifs: ["objet"] });
  assert.deepEqual(A.geste(origine, [o], { qualificatif: "hors-champ" }),
                   { action: "modifier", releve: o, corps: { qualificatifs: ["hors-champ", "objet"] },
                     vu: { qualificatifs: ["objet"] } });
  assert.deepEqual(A.geste(origine, [o], { qualificatif: "objet" }).corps, { qualificatifs: [] });
  assert.equal(A.geste(origine, [o], {}).action, "retirer");
});

test("le libellé d'un relevé et le mot de son état", () => {
  assert.equal(A.libelleReleve(rel(1, { entree_cle: "ton", variante_cle: "crie" }), PLAN),
               "ton de voix · crié");
  assert.equal(A.libelleReleve(rel(1, { entree_cle: "origine",
                                        qualificatifs: ["objet", "hors-champ"],
                                        precision: "le salon" }), PLAN),
               "origine du son · objet, hors champ — « le salon »");
  assert.equal(A.libelleReleve(rel(1, { entree_cle: "inconnue" }), PLAN), "inconnue");
  assert.equal(A.motEtat({ etat: "a_completer" }), "à compléter");
  assert.equal(A.motEtat({ etat: "normal" }), "");
});

test("la liste de ce qui est posé : sur les mots désignés, sinon la zone et sa case", () => {
  const l = [rel(1, { mots: motsDe(2, 3) }), rel(2, { mots: motsDe(0) }),
             rel(3, { entree_cle: "ton" }), rel(4, { region_id: 5 }),
             rel(5, { region_id: 99 }), rel(6, { region_id: null, planche_id: 9 })];
  const bulle = { id: 10, type: "bulle" }, laCase = { id: 5, type: "case" };
  assert.deepEqual(A.listeSurLaZone(l, bulle, laCase, 9, [3]).map((r) => r.id), [1]);
  assert.deepEqual(A.listeSurLaZone(l, bulle, laCase, 9, []).map((r) => r.id), [2, 1, 3, 4]);
  assert.deepEqual(A.listeSurLaZone(l, laCase, laCase, 9, []).map((r) => r.id), [4]);
  assert.deepEqual(A.listeSurLaZone(l, { pseudo: true }, null, 9, []).map((r) => r.id), [6]);
});

test("« Relevés : ▾ » se retient par personne et par projet, sous try/catch", () => {
  const memoire = {};
  const s = { getItem: (k) => memoire[k] ?? null, setItem: (k, v) => { memoire[k] = v; } };
  assert.equal(A.lireReglage(s, "ana", 2), null);
  assert.equal(A.retenirReglage(s, "ana", 2, [3, 1]), true);
  assert.deepEqual(A.lireReglage(s, "ana", 2), [1, 3]);
  assert.equal(A.lireReglage(s, "bob", 2), null);
  assert.equal(A.lireReglage(s, "ana", 4), null);
  const casse = { getItem: () => { throw new Error("bloqué"); },
                  setItem: () => { throw new Error("bloqué"); } };
  assert.equal(A.lireReglage(casse, "ana", 2), null);
  assert.equal(A.retenirReglage(casse, "ana", 2, [1]), false);
  assert.equal(A.retenirReglage(null, "ana", 2, [1]), false);
  const m = A.grillesMontrees([3, 9], [{ id: 1 }, { id: 3 }], 1);
  assert.deepEqual([...m].sort(), [1, 3]);
  assert.deepEqual([...A.grillesMontrees(null, [{ id: 1 }], 1)], [1]);
});

test("la cardinalité : « Remplacer par la mienne » modifie le relevé existant", () => {
  const det = { releve_existant: { id: 4, variante_cle: "crie", qualificatifs: [],
                                   auteur: "lea", auteur_nom: "Léa" } };
  assert.deepEqual(A.remplacementCardinalite(det, { variante_cle: "chuchote" }),
                   { releve_id: 4, corps: { variante_cle: "chuchote",
                                            vu: { variante_cle: "crie" } }, auteur: "Léa" });
  assert.equal(A.remplacementCardinalite({ message: "x" }, {}), null);
});

test("« Créer « … » » dans une grille ouverte seulement, sans doublon", () => {
  assert.equal(A.creerDansLeFiltre({ ouverte: true }, " Paris ", []), "Paris");
  assert.equal(A.creerDansLeFiltre({ ouverte: true }, "paris", [{ libelle: "Paris" }]), null);
  assert.equal(A.creerDansLeFiltre({ ouverte: false }, "Paris", []), null);
  assert.equal(A.creerDansLeFiltre({ ouverte: true }, "  ", []), null);
});

test("l'entrée qui naît en la posant suit la cible de la version", () => {
  assert.deepEqual(A.entreeNeuve({ porte_sur: ["mots"] }, "Paris").pose, "mots");
  assert.deepEqual(A.entreeNeuve({ porte_sur: ["case"] }, "Paris").pose, "zone");
  assert.deepEqual(A.entreeNeuve({ porte_sur: ["case"] }, "Paris").cibles, ["case"]);
  assert.deepEqual(A.entreeNeuve({ porte_sur: ["planche"] }, "Paris").pose, "planche");
  assert.deepEqual(A.vuDuReleve(rel(1, {})), { variante_cle: null, qualificatifs: [] });
  // Les qualificatifs vus forment un ENSEMBLE : ils partent triés, dans un ordre stable.
  assert.deepEqual(A.vuDuReleve(rel(1, { qualificatifs: ["objet", "hors-champ"] })).qualificatifs,
                   ["hors-champ", "objet"]);
});

/* ── Commit 4 : « terminée », le parcours ── */
const RANGEMENT = [
  { case: { id: 1, type: "case" },
    zones: [{ id: 11, type: "bulle" }, { id: 12, type: "personnage" }, { id: 13, type: "cartouche" }] },
  { case: { id: 2, type: "case" }, zones: [{ id: 21, type: "detail" }, { id: 22, type: "texte" }] },
];
const planDe = (cibles, porte) => ({ porte_sur: porte || [], rubriques: [],
  entrees: cibles.map((c, i) => ({ cle: `e${i}`, cibles: c, retiree: false })) });

test("le parcours se DÉRIVE des cibles, dans l'ordre de lecture", () => {
  const p = (plan) => A.parcours(RANGEMENT, plan).map((e) => e.zoneId === null ? `c${e.caseIx}` : e.zoneId);
  assert.deepEqual(p(planDe([["mots"]])), [11, 13, 22]);
  assert.deepEqual(p(planDe([["bulle"]])), [11]);
  assert.deepEqual(p(planDe([["case"], ["mots"]])), ["c0", 11, 13, "c1", 22]);
  assert.deepEqual(p(planDe([["personnage"], ["detail"]])), [12, 21]);
  assert.deepEqual(p(planDe([["entite"]])), []);
  // Une entrée retirée ne compte plus ; la version compte (une grille ouverte sans entrée).
  assert.deepEqual(p({ porte_sur: ["case"], entrees: [{ cibles: ["mots"], retiree: true }] }), ["c0", "c1"]);
  // La planche : une seule étape, en dernier, sur la case pseudo qu'on assure.
  const avec = A.assurerPlanche(RANGEMENT, 100, 200);
  assert.equal(avec.length, 3);
  assert.equal(A.assurerPlanche(avec, 1, 1), avec);
  assert.deepEqual(A.parcours(avec, planDe([["planche"], ["bulle"]])),
                   [{ caseIx: 0, zoneId: 11 }, { caseIx: 2, zoneId: null, planche: true }]);
  assert.deepEqual(A.parcours(RANGEMENT, planDe([["planche"]])), []);
  assert.ok(A.visePlanche(planDe([["planche"]])) && !A.visePlanche(planDe([["mots"]])));
  // Les zones hors cadre (case pseudo) suivent leur type, mais la case pseudo n'est pas une case.
  const hors = [...RANGEMENT, { case: { id: null, pseudo: true }, zones: [{ id: 31, type: "bulle" }] }];
  assert.deepEqual(A.parcours(hors, planDe([["case"], ["bulle"]])).map((e) => e.zoneId),
                   [null, 11, null, 31]);
});

test("le rang dans le parcours, et Suivante / Précédente", () => {
  const et = A.parcours(RANGEMENT, planDe([["case"], ["mots"]]));
  assert.equal(A.rangDansParcours(et, 0, null), 0);
  assert.equal(A.rangDansParcours(et, 0, 13), 2);
  assert.equal(A.rangDansParcours(et, 0, 12), -1);
  const fait = new Set([1, 2]);
  const faite = (e) => fait.has(et.indexOf(e));
  assert.equal(A.suivanteDuParcours(et, 0, 1, faite, false), 1);
  assert.equal(A.suivanteDuParcours(et, 0, 1, faite, true), 3);          // saute les terminées
  assert.equal(A.suivanteDuParcours(et, 4, 1, faite, false), 0);         // fait le tour
  assert.equal(A.suivanteDuParcours(et, 0, -1, faite, false), 4);
  assert.equal(A.suivanteDuParcours(et, 3, -1, faite, true), 0);
  assert.equal(A.suivanteDuParcours(et, -1, 1, faite, true), 0);         // hors parcours : du début
  assert.equal(A.suivanteDuParcours(et, -1, -1, faite, false), 4);       // … ou de la fin
  assert.equal(A.suivanteDuParcours(et, -1, 1, () => true, true), -1);   // plus rien à faire
  assert.equal(A.suivanteDuParcours(et, 2, 1, (e) => e !== et[2], true), 2);  // la seule : on reste
  assert.equal(A.suivanteDuParcours(et, 2, 1, () => true, true), -1);
  assert.equal(A.suivanteDuParcours([], 0, 1, faite, false), -1);
});

test("« terminée » : la zone, la rubrique, toute la grille par ses rubriques de tête", () => {
  const plan = { rubriques: [{ cle: "a", parent_cle: null }, { cle: "a > x", parent_cle: "a" },
                             { cle: "b", parent_cle: null }] };
  const pa = (rk, extra) => ({ grille_id: 1, region_id: 11, planche_id: null, rubrique_cle: rk,
                               par: "alice", par_nom: "Alice", ...extra });
  const z = { region_id: 11 };
  assert.deepEqual(A.terminee([], z, 1, "", plan), { terminee: false, passes: [] });
  assert.equal(A.terminee([pa("")], z, 1, "", plan).terminee, true);
  assert.equal(A.terminee([pa("")], z, 1, "a", plan).terminee, true);      // la grille entière vaut pour la rubrique
  assert.equal(A.terminee([pa("a")], z, 1, "a", plan).terminee, true);
  assert.equal(A.terminee([pa("a")], z, 1, "b", plan).terminee, false);
  assert.equal(A.terminee([pa("a")], z, 1, "", plan).terminee, false);
  const deux = [pa("a"), pa("b", { par: "bob", par_nom: "Bob" })];
  assert.equal(A.terminee(deux, z, 1, "", plan).terminee, true);           // toutes les rubriques de tête
  assert.deepEqual(A.signataires(A.terminee(deux, z, 1, "", plan).passes), ["Alice", "Bob"]);
  assert.deepEqual(A.signataires([pa(""), pa("a"), pa("b", { par_nom: null, par: "carl" })]),
                   ["Alice", "carl"]);
  // Une autre grille, une autre zone ne comptent pas ; la planche se lit sur la surface.
  assert.equal(A.terminee([pa("", { grille_id: 2 })], z, 1, "", plan).terminee, false);
  assert.equal(A.terminee([pa("", { region_id: 12 })], z, 1, "", plan).terminee, false);
  const surface = { grille_id: 1, region_id: null, planche_id: 9, rubrique_cle: "" };
  assert.equal(A.terminee([surface], { planche_id: 9 }, 1, "", plan).terminee, true);
  assert.equal(A.terminee([surface], { planche_id: 8 }, 1, "", plan).terminee, false);
  assert.equal(A.terminee([surface], { region_id: 11 }, 1, "", plan).terminee, false);
  // Sans rubrique de tête, seule la passe de toute la grille termine.
  assert.equal(A.terminee([pa("a")], z, 1, "", { rubriques: [] }).terminee, false);
  assert.deepEqual(A.cibleDePasse({ id: 11 }, 9), { region_id: 11 });
  assert.deepEqual(A.cibleDePasse({ id: null, pseudo: true }, 9), { planche_id: 9 });
  assert.deepEqual(A.rubriquesDeTete(plan), ["a", "b"]);
});

test("« Rouvrir » retire ce qui la dit terminée", () => {
  const pa = (rk) => ({ grille_id: 1, region_id: 11, planche_id: null, rubrique_cle: rk });
  const z = { region_id: 11 };
  assert.deepEqual(A.aRouvrir([pa(""), pa("a"), pa("b")], z, 1, ""), ["", "a", "b"]);
  assert.deepEqual(A.aRouvrir([pa(""), pa("a"), pa("b")], z, 1, "a"), ["a", ""]);
  assert.deepEqual(A.aRouvrir([pa("b")], z, 1, "a"), []);
  assert.deepEqual(A.aRouvrir([{ ...pa(""), grille_id: 2 }], z, 1, ""), []);
});

test("les marques de la minicarte : case terminée, doute ouvert", () => {
  const et = A.parcours(RANGEMENT, planDe([["mots"]]));
  assert.equal(A.caseTerminee(et, 0, (e) => e.zoneId === 11 || e.zoneId === 13), true);
  assert.equal(A.caseTerminee(et, 0, (e) => e.zoneId === 11), false);
  assert.equal(A.caseTerminee(et, 5, () => true), false);                 // aucune étape : pas « terminée »
  const avec = A.assurerPlanche(RANGEMENT, 1, 1);
  const doutes = A.casesEnDoute(avec, [{ region_id: 22, doute: { id: 1 } }, { region_id: 11, doute: null },
                                       { region_id: null, planche_id: 9, doute: { id: 2 } }]);
  assert.deepEqual([...doutes].sort(), [1, 2]);
  assert.deepEqual([...A.casesEnDoute(RANGEMENT, [{ region_id: 2, doute: {} }])], [1]);
});

/* ── Commit 5 : le doute et la Synthèse ── */
const rel5 = (id, extra = {}) => ({ id, grille_id: 1, region_id: 11, planche_id: null,
                                   entree_cle: "cri", variante_cle: null, qualificatifs: [],
                                   mots: [], etat: "normal", causes: [], doute: null,
                                   doutes_leves: [], ...extra });
const desMots = (...rangs) => rangs.map((r, i) => ({ position: i, rang: r, forme: `m${r}` }));

test("les causes de l'état, en mots, dans l'ordre du serveur ; une inconnue se dit", () => {
  assert.deepEqual(A.causesEnMots(rel5(1, { causes: ["texte_change", "mot_perdu"] })),
                   ["le texte a changé depuis la pose", "un mot désigné n'est plus dans le texte"]);
  assert.deepEqual(A.causesEnMots(rel5(1, { causes: ["precision_manquante", "lien_manquant"] })),
                   ["précision attendue", "lien attendu vers une autre zone"]);
  assert.deepEqual(A.causesEnMots(rel5(1, { causes: ["lien_perdu", "type_change", "entree_absente"] })),
                   ["la zone liée a disparu", "la zone a changé de sorte",
                    "l'entrée n'est plus dans la grille"]);
  assert.deepEqual(A.causesEnMots(rel5(1, { causes: ["nouvelle"] })), ["nouvelle"]);
  assert.deepEqual(A.causesEnMots(null), []);
});

test("ce que le relevé désignait : le passage ancré, ses trous compris", () => {
  assert.equal(A.passageAncre(rel5(1, { mots: desMots(2, 3, 5) })), "m2 m3 … m5");
  assert.equal(A.passageAncre(rel5(1, { mots: [] })), "");
});

test("comment un doute a été levé ; « Changer… » en place pour une entrée à variantes", () => {
  assert.equal(A.issueEnMots("garde"), "gardé");
  assert.equal(A.issueEnMots("change"), "changé");
  assert.equal(A.issueEnMots("retire"), "retiré");
  assert.equal(A.issueEnMots("autre"), "autre");
  const [cri, ton, origine] = PLAN.entrees;
  assert.equal(A.changerEnPlace(ton), true);
  assert.equal(A.changerEnPlace(cri), false);
  assert.equal(A.changerEnPlace(origine), false);
  assert.equal(A.changerEnPlace({ ...ton, variantes: [ton.variantes[0]] }), false);
  assert.equal(A.changerEnPlace(null), false);
});

test("une date de SQLite se lit comme de l'UTC", () => {
  assert.equal(A.isoDeSqlite("2026-10-28 12:30:00"), "2026-10-28T12:30:00Z");
  assert.equal(A.isoDeSqlite("2026-10-28T12:30"), "2026-10-28T12:30Z");
  assert.equal(A.isoDeSqlite("2026-10-28 12:30:00+02:00"), "2026-10-28T12:30:00+02:00");
  assert.equal(A.isoDeSqlite("2026-10-28"), null);
  assert.equal(A.isoDeSqlite(null), null);
  assert.equal(new Date(A.isoDeSqlite("2026-10-28 12:30:00")).getTime(),
               Date.UTC(2026, 9, 28, 12, 30, 0));
});

test("Relevés par case : la case, la zone dans la case, le premier mot, puis la surface", () => {
  const l = [
    rel5(1, { region_id: 22 }),                                   // case 1, zone 1
    rel5(2, { region_id: null, planche_id: 9 }),                  // la surface
    rel5(3, { region_id: 11, mots: desMots(4) }),                 // case 0, zone 0, mot 4
    rel5(4, { region_id: 11, mots: desMots(1, 2) }),              // case 0, zone 0, mot 1
    rel5(5, { region_id: 1 }),                                    // la case 0 elle-même
    rel5(6, { region_id: 999 }),                                  // plus sur la planche
    rel5(7, { region_id: 13 }),                                   // case 0, zone 2
  ];
  const g = A.relevesParCase(RANGEMENT, l);
  assert.deepEqual(g.map((x) => [x.cle, x.caseIx, x.surface, x.releves.map((r) => r.id)]), [
    ["case-0", 0, false, [5, 4, 3, 7]], ["case-1", 1, false, [1]],
    ["planche", null, true, [2]], ["ailleurs", null, false, [6]]]);
  assert.deepEqual(A.relevesParCase(RANGEMENT, []), []);
  // Sans mots, le relevé de la zone entière passe avant ceux de ses mots ; à égalité, l'id.
  assert.deepEqual(A.relevesParCase(RANGEMENT, [rel5(8, { mots: desMots(0) }), rel5(9), rel5(7)])[0]
    .releves.map((r) => r.id), [7, 9, 8]);
});

test("À revoir : doutes, à revoir, à compléter, doutes levés — et combien attendent", () => {
  const leve = (id) => ({ id, issue: "garde" });
  const l = [
    rel5(1, { region_id: 22, doute: { id: 10 }, etat: "a_revoir", causes: ["mot_perdu"] }),
    rel5(2, { region_id: 11, etat: "a_completer", causes: ["precision_manquante"] }),
    rel5(3, { region_id: 11, doute: { id: 11 }, doutes_leves: [leve(5), leve(6)] }),
    rel5(4, { region_id: 13, etat: "a_revoir" }),
    rel5(5, { region_id: 11, doutes_leves: [leve(7)] }),
    rel5(6, { region_id: 11 }),
  ];
  const v = A.aRevoir(l, RANGEMENT);
  assert.deepEqual(v.doutes.map((r) => r.id), [3, 1]);                 // ordre de lecture
  assert.deepEqual(v.revoir.map((r) => r.id), [4, 1]);
  assert.deepEqual(v.completer.map((r) => r.id), [2]);
  assert.deepEqual(v.leves.map((x) => [x.releve.id, x.doute.id]), [[3, 6], [3, 5], [5, 7]]);
  assert.equal(v.total, 4);                                            // 1, 2, 3, 4 : une fois chacun
  const vide = A.aRevoir([rel5(9)], RANGEMENT);
  assert.equal(vide.total, 0);
  assert.deepEqual([vide.doutes, vide.revoir, vide.completer, vide.leves], [[], [], [], []]);
});

test("le décompte : rubriques, entrées, variantes, qualificatifs, et ce qui n'est pas au plan", () => {
  const l = [
    rel5(1, { entree_cle: "cri" }), rel5(2, { entree_cle: "cri" }),
    rel5(3, { entree_cle: "ton", variante_cle: "crie" }),
    rel5(4, { entree_cle: "ton", variante_cle: "crie" }),
    rel5(5, { entree_cle: "origine", qualificatifs: ["objet", "hors-champ"] }),
    rel5(6, { entree_cle: "origine", qualificatifs: ["objet"] }),
    rel5(7, { entree_cle: "disparue" }),
    rel5(8, { entree_cle: "cri", grille_id: 2 }),                       // une autre grille
  ];
  const d = A.decompte(l, 1, PLAN);
  assert.equal(d.total, 7);
  assert.deepEqual(d.lignes.map((x) => [x.sorte, x.cle, x.niveau, x.n]), [
    ["rubrique", "sons", 0, 4],
    ["rubrique", "sons > voix", 1, 4],
    ["entree", "cri", 2, 2],
    ["entree", "ton", 2, 2],
    ["variante", "crie", 3, 2],
    ["rubrique", "provenance", 0, 2],
    ["entree", "origine", 1, 2],
    ["qualificatif", "objet", 2, 2],
    ["qualificatif", "hors-champ", 2, 1],
    ["entree", "disparue", 0, 1],
  ]);
  assert.equal(d.lignes.find((x) => x.cle === "crie").libelle, "crié");
  assert.equal(d.lignes.find((x) => x.cle === "hors-champ").libelle, "hors champ");
  assert.equal(d.lignes.find((x) => x.cle === "sons > voix").libelle, "Voix");
  // Un qualificatif répété sur un même relevé ne compte qu'une fois.
  assert.equal(A.decompte([rel5(1, { entree_cle: "origine", qualificatifs: ["objet", "objet"] })], 1, PLAN)
    .lignes.find((x) => x.cle === "objet").n, 1);
  // Sans plan, les entrées sous leur clé.
  assert.deepEqual(A.decompte(l, 2, null), { total: 1, lignes: [
    { sorte: "entree", cle: "cri", libelle: "cri", niveau: 0, n: 1 }] });
  assert.deepEqual(A.decompte([], 1, PLAN), { total: 0, lignes: [] });
});

test("zones terminées n / N : les étapes du parcours que la passe de toute la grille dit faites", () => {
  const plan = { porte_sur: [], rubriques: [{ cle: "a", parent_cle: null }],
                 entrees: [{ cle: "e", cibles: ["mots"], retiree: false }] };
  const pa = (region, rk) => ({ grille_id: 1, region_id: region, planche_id: null, rubrique_cle: rk });
  // Le parcours : 11, 13, 22.
  assert.deepEqual(A.zonesTerminees(RANGEMENT, plan, [], 1, 9), { n: 0, total: 3 });
  assert.deepEqual(A.zonesTerminees(RANGEMENT, plan, [pa(11, ""), pa(22, "a")], 1, 9),
                   { n: 2, total: 3 });                                // la rubrique de tête unique suffit
  assert.deepEqual(A.zonesTerminees(RANGEMENT, plan, [pa(11, ""), { ...pa(13, ""), grille_id: 2 }], 1, 9),
                   { n: 1, total: 3 });
  assert.deepEqual(A.zonesTerminees(RANGEMENT, plan, [pa(11, ""), pa(22, "")], 1, 9,
                                    (e) => e.caseIx === 0), { n: 1, total: 2 });
  // La planche : sa passe se lit sur la surface.
  const planche = { porte_sur: ["planche"], rubriques: [], entrees: [] };
  const avec = A.assurerPlanche(RANGEMENT, 10, 10);
  assert.deepEqual(A.zonesTerminees(avec, planche,
                                    [{ grille_id: 1, region_id: null, planche_id: 9, rubrique_cle: "" }], 1, 9),
                   { n: 1, total: 1 });
  assert.deepEqual(A.zonesTerminees(avec, planche, [], 1, 9), { n: 0, total: 1 });
});

/* ── Commit 7 : les correctifs de la passe du jalon 1 ── */
test("le texte d'un passage se lit tel qu'il est transcrit, ses trous dits « … »", () => {
  const texte = "L' CUL, NE VIENT PAS";
  const decoupe = [{ rang: 0, forme: "L", debut: 0, fin: 1 }, { rang: 1, forme: "'", debut: 1, fin: 2 },
                   { rang: 2, forme: "CUL", debut: 3, fin: 6 }, { rang: 3, forme: ",", debut: 6, fin: 7 },
                   { rang: 4, forme: "NE", debut: 8, fin: 10 }, { rang: 5, forme: "VIENT", debut: 11, fin: 16 },
                   { rang: 6, forme: "PAS", debut: 17, fin: 20 }];
  assert.equal(A.texteDuPassage(decoupe, [0, 1, 2], texte), "L' CUL");
  assert.equal(A.texteDuPassage(decoupe, [0, 1, 2]), "L ' CUL");            // sans texte : les formes
  assert.equal(A.texteDuPassage(decoupe, [4, 6], texte), "NE … PAS");
  assert.equal(A.texteDuPassage(decoupe, [2, 3, 5], texte), "CUL, … VIENT");
  // Un mot sans position (un relevé ancré ailleurs) : les formes.
  assert.equal(A.texteDuPassage([{ rang: 0, forme: "A" }, { rang: 1, forme: "B" }], [0, 1], "A B"), "A B");
  assert.equal(A.texteDuPassage(decoupe, [9], texte), "?");
});

test("un lien dit la zone qu'il désigne : son étiquette, le début de son texte", () => {
  const regions = [{ id: 11, type: "bulle", ocr_texte: "PÉDÉ !" },
                   { id: 13, type: "cartouche", ocr_texte: "UN TRÈS LONG CARTOUCHE QUI NE TIENT PAS" },
                   { id: 2, type: "case" }, { id: 12, type: "personnage" }];
  const rang = [{ case: { id: 1, type: "case", citation: { case: 1 } },
                  zones: [{ id: 11, type: "bulle", citation: { bulle: 2 } }, { id: 12, type: "personnage" },
                          { id: 13, type: "cartouche" }] },
                { case: { id: 2, type: "case", citation: { case: 2 } }, zones: [] }];
  assert.equal(A.nomDuLien(rang, regions, { region_id: 11, existe: true }, 11), "b2 « PÉDÉ ! »");
  assert.equal(A.nomDuLien(rang, regions, { region_id: 13, existe: true }, 11), "ca1 « UN TRÈS LONG CARTOUCHE… »");
  assert.equal(A.nomDuLien(rang, regions, { region_id: 2, existe: true }), "c2");
  assert.equal(A.nomDuLien(rang, regions, { region_id: 12, existe: true }, 11), "p1");
  assert.equal(A.nomDuLien(rang, regions, { region_id: 99, existe: true }), "une autre zone");
  assert.equal(A.nomDuLien(rang, regions, { region_id: 99, existe: false, texte: "ADIEU" }),
               "zone disparue « ADIEU »");
  assert.equal(A.nomDuLien(rang, regions, { region_id: 99, existe: false }), "zone disparue");
  assert.equal(A.nomDuLien(rang, regions, null), null);
});

test("un lien vers une zone d'une AUTRE case nomme cette case ; dans la même, la forme courte", () => {
  const regions = [{ id: 11, type: "bulle", ocr_texte: "PÉDÉ !" }, { id: 21, type: "bulle", ocr_texte: "OUI" },
                   { id: 31, type: "bulle", ocr_texte: "DEHORS" }];
  const rang = [{ case: { id: 1, type: "case", citation: { case: 1 } },
                  zones: [{ id: 11, type: "bulle", citation: { bulle: 1 } }] },
                { case: { id: 2, type: "case", citation: { case: 2 } },
                  zones: [{ id: 21, type: "bulle", citation: { bulle: 1 } }] },
                { case: { id: null, type: "case", pseudo: true }, zones: [{ id: 31, type: "bulle" }] }];
  const l = (id) => ({ region_id: id, existe: true });
  assert.equal(A.nomDuLien(rang, regions, l(21), 11), "c2 · b1 « OUI »");
  assert.equal(A.nomDuLien(rang, regions, l(11), 21), "c1 · b1 « PÉDÉ ! »");
  // Dans la même case : la bulle, ou la case elle-même, qui porte le relevé.
  assert.equal(A.nomDuLien(rang, regions, l(11), 11), "b1 « PÉDÉ ! »");
  assert.equal(A.nomDuLien(rang, regions, l(11), 1), "b1 « PÉDÉ ! »");
  // Un lien vers une case se dit déjà par sa case.
  assert.equal(A.nomDuLien(rang, regions, l(2), 11), "c2");
  // Un relevé de la planche (aucune région) : la case est toujours dite.
  assert.equal(A.nomDuLien(rang, regions, l(21), null), "c2 · b1 « OUI »");
  assert.equal(A.nomDuLien(rang, regions, l(21)), "c2 · b1 « OUI »");
  // Hors de toute case.
  assert.equal(A.nomDuLien(rang, regions, l(31), 11), "hors des cases · b1 « DEHORS »");
  assert.equal(A.nomDuLien(rang, regions, l(31), 31), "b1 « DEHORS »");
});

test("les relevés de la surface ; sur quoi un relevé est posé, un seul libellé par cible", () => {
  const l = [{ id: 1, region_id: null, planche_id: 9 }, { id: 2, region_id: 4, planche_id: null },
             { id: 3, region_id: null, planche_id: 8 }];
  assert.deepEqual(A.relevesDeSurface(l, 9).map((r) => r.id), [1]);
  const types = { 4: "case", 5: "bulle", 6: "personnage", 7: "cartouche" };
  const typeDe = (id) => types[id] || null;
  const bulle = { id: 5, type: "bulle" }, kase = { id: 4, type: "case" };
  // « regard caméra » sur la case se dit « la case », qu'on lise la bulle ou la case.
  assert.equal(A.ciblePosee({ region_id: 4 }, bulle, typeDe), "la case");
  assert.equal(A.ciblePosee({ region_id: 4 }, kase, typeDe), "la case");
  assert.equal(A.ciblePosee({ region_id: 5 }, bulle, typeDe), "toute la zone");
  assert.equal(A.ciblePosee({ region_id: 6 }, bulle, typeDe), "la boîte");
  assert.equal(A.ciblePosee({ region_id: 7 }, bulle, typeDe), "le cartouche");
  assert.equal(A.ciblePosee({ region_id: null, planche_id: 9 }, bulle, typeDe), "la planche");
  assert.equal(A.ciblePosee({ region_id: 99 }, bulle, typeDe), "la zone");
  assert.equal(A.ciblePosee(null, bulle, typeDe), "");
});

test("la boîte du guide repliée se retient sur le poste ; sans stockage, dépliée", () => {
  const m = new Map();
  const s = { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v) };
  assert.equal(A.lireGuideReplie(s), false);
  assert.equal(A.retenirGuideReplie(s, true), true);
  assert.equal(m.get("bd-annotation-guide"), "replie");
  assert.equal(A.lireGuideReplie(s), true);
  A.retenirGuideReplie(s, false);
  assert.equal(A.lireGuideReplie(s), false);
  const leve = { getItem() { throw new Error("x"); }, setItem() { throw new Error("x"); } };
  assert.equal(A.lireGuideReplie(leve), false);
  assert.equal(A.retenirGuideReplie(leve, true), false);
  assert.equal(A.lireGuideReplie(null), false);
  assert.equal(A.retenirGuideReplie(null, true), false);
});
