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
