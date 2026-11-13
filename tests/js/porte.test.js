/* Tests unitaires des relevés dans la Recherche et du filtre « porte… »
   (static/lib/porte.js, ANN-7 — le mode libre, J7 ; tranché sur maquette le 2026-11-06).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Les relevés se lisent EN LIGNE : « Mode libre : silence, sentiment : surprise · Sons et
   paroles : ton de voix : crié ». Ce qui est vérifié ici : l'ordre des grilles, le nom du
   Mode libre, les séparateurs, le surlignage sans accents, la zone sans texte, la liste
   « Porte… » tirée du plan, le nom d'un filtre posé et la composition de l'adresse. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const P = require("../../static/lib/porte.js");

/* Le texte d'un fragment HTML, sans ses balises : ce que l'œil lit. */
const lu = (html) => html.replace(/<[^>]+>/g, "").replace(/&#39;/g, "'").replace(/&amp;/g, "&");

const TRAVAIL = 7, SONS = 3, AUTRE = 9;
function rel(grille_id, grille, entree, variante, extra) {
  const travail = grille_id === TRAVAIL;
  const cle = entree.replace(/\s/g, "-");
  return { id: Math.random(), grille_id, grille, travail, ouverte: travail, entree_cle: cle,
           entree, variante_cle: variante ? variante.replace(/\s/g, "-") : null,
           variante: variante || null, qualificatifs: [],
           porte: variante ? `${grille_id}/variante/${cle}/${variante.replace(/\s/g, "-")}`
             : `${grille_id}/entree/${cle}`, ...(extra || {}) };
}

test("la ligne : le Mode libre d'abord, puis les grilles par leur nom ; virgules et « · »", () => {
  // Reçus dans le désordre : l'écran ne se fie pas à l'ordre du serveur.
  const releves = [
    rel(SONS, "Sons et paroles", "ton de voix", "crié"),
    rel(TRAVAIL, "Travail en cours", "silence"),
    rel(AUTRE, "Autres", "regard caméra"),
    rel(TRAVAIL, "Travail en cours", "sentiment", "surprise"),
  ];
  assert.equal(lu(P.ligneReleves(releves, "")),
    "Mode libre : silence, sentiment : surprise · Autres : regard caméra"
    + " · Sons et paroles : ton de voix : crié");
});

test("le nom de la grille est en encre discrète, suivi de « : », et chaque relevé l'isole", () => {
  const html = P.ligneReleves([rel(TRAVAIL, "Travail en cours", "sentiment", "surprise")], "");
  assert.match(html, /^<span class="r-gr">Mode libre :<\/span> <button type="button" class="r-releve"/);
  assert.match(html, new RegExp(`data-porte="${TRAVAIL}/variante/sentiment/surprise"`));
  assert.match(html, /title="Isoler les zones qui portent « sentiment : surprise »"/);
  assert.equal(P.ligneReleves([], "x"), "");
  assert.equal(P.ligneReleves(undefined, "x"), "");
});

test("les grilles de même nom se distinguent par leur identifiant, à la française", () => {
  const g = P.grouperReleves([rel(5, "écho", "a"), rel(4, "Écho", "b"), rel(2, "Zèbre", "c"),
                              rel(1, "abri", "d")]);
  assert.deepEqual(g.map((x) => x.grille_id), [1, 4, 5, 2]);
});

test("les qualificatifs suivent l'entrée entre parenthèses, isolables s'ils ont une liste", () => {
  const r = rel(SONS, "Signaux", "écho", null, { qualificatifs: [
    { cle: "objet", libelle: "objet", porte: `${SONS}/qualificatif/sources/objet` },
    { cle: "x", libelle: "sans liste" }] });
  const html = P.ligneReleves([r], "");
  assert.equal(lu(html), "Signaux : écho (objet, sans liste)");
  assert.match(html, new RegExp(`data-porte="${SONS}/qualificatif/sources/objet"`));
  assert.equal((html.match(/<button/g) || []).length, 2, "« sans liste » n'est pas un bouton");
});

test("le mot cherché est surligné dans une étiquette comme dans le texte, sans accents", () => {
  const html = P.ligneReleves([rel(TRAVAIL, "Travail en cours", "lieu", "forêt")], "foret");
  assert.match(html, /lieu : <mark>forêt<\/mark>/);
  // Le nom de la grille, lui, n'est pas une étiquette.
  assert.equal(P.ligneReleves([rel(TRAVAIL, "x", "silence")], "mode").includes("<mark>"), false);
});

test("surligner : casse, accents, plusieurs termes, sans chevauchement, échappé", () => {
  assert.equal(P.surligner("MILLE SABORDS !", "sabords"), "MILLE <mark>SABORDS</mark> !");
  assert.equal(P.surligner("Une forêt, une FORÊT", "FORET"),
               "Une <mark>forêt</mark>, une <mark>FORÊT</mark>");
  assert.equal(P.surligner("pouvoir", "pouv"), "<mark>pouv</mark>oir");
  assert.equal(P.surligner("abc abcd", "abcd abc"), "<mark>abc</mark> <mark>abcd</mark>");
  assert.equal(P.surligner("D'ACCORD <b>", "d'accord"), "<mark>D&#39;ACCORD</mark> &lt;b&gt;");
  assert.equal(P.surligner("a.b", "."), "a<mark>.</mark>b");
  assert.equal(P.surligner("texte", "  "), "texte");
  assert.equal(P.surligner(null, "x"), "");
  // Un terme recherché accentué trouve la forme non accentuée.
  assert.equal(P.surligner("ete", "été"), "<mark>ete</mark>");
});

test("une zone sans texte dit ce qu'elle est : « Case c3, sans texte »", () => {
  assert.equal(P.sansTexte({ type: "case", citation: { planche: 1, case: 3, texte: "pl.1 · c3" } }),
               "Case c3, sans texte");
  assert.equal(P.sansTexte({ type: "bulle",
                             citation: { planche: 2, texte: "pl.2 · c1 · b2" } }),
               "Bulle c1 · b2, sans texte");
  assert.equal(P.sansTexte({ type: "bulle", citation: { planche: 2, texte: "pl.2 · hors-case" } }),
               "Bulle hors-case, sans texte");
  assert.equal(P.sansTexte({ type: "personnage", citation: { planche: 2, texte: "pl.2" } }),
               "Personnage, sans texte");
  assert.equal(P.sansTexte({ type: "case", citation: { planche: null, texte: "Paratexte" } }),
               "Case, sans texte");
  assert.equal(P.sansTexte({ type: "case" }), "Case, sans texte");
});

test("lirePorte : la forme du serveur, ou null", () => {
  assert.deepEqual(P.lirePorte("3/entree/cri/echo"),
                   { grille_id: 3, sorte: "entree", parent: null, valeurs: ["cri", "echo"] });
  assert.deepEqual(P.lirePorte("3/variante/ton-de-voix/crie"),
                   { grille_id: 3, sorte: "variante", parent: "ton-de-voix", valeurs: ["crie"] });
  assert.deepEqual(P.lirePorte("3/rubrique/sons > voix"),
                   { grille_id: 3, sorte: "rubrique", parent: null, valeurs: ["sons > voix"] });
  for (const faux of ["", "x/entree/a", "3/autre/a", "3/entree", "3/variante/a", "3/entree//a"]) {
    assert.equal(P.lirePorte(faux), null, faux);
  }
});

/* Deux grilles actives : la grille de travail (sans rubrique) et un modèle à rubriques. */
const GRILLES = [
  { id: SONS, nom: "Signaux", travail: false, plan: {
    rubriques: [
      { cle: "sons > voix", libelle: "Voix", parent_cle: "sons" },
      { cle: "sons", libelle: "Sons", parent_cle: null },
      { cle: "provenance", libelle: "Provenance", parent_cle: null }],
    entrees: [
      { cle: "cri", libelle: "cri", rubrique_cle: "sons > voix", variantes: [] },
      { cle: "ton-de-voix", libelle: "ton de voix", rubrique_cle: "sons > voix",
        variantes: [{ cle: "chuchote", libelle: "chuchoté" }, { cle: "crie", libelle: "crié" }] },
      { cle: "echo", libelle: "écho", rubrique_cle: "provenance", variantes: [] },
      { cle: "vieux", libelle: "vieux", rubrique_cle: null, retiree: true, variantes: [] }],
    listes: [{ cle: "sources", libelle: "source du son",
               qualificatifs: [{ cle: "objet", libelle: "objet" }] }] } },
  { id: TRAVAIL, nom: "Travail en cours", travail: true, plan: {
    rubriques: [], listes: [],
    entrees: [
      { cle: "silence", libelle: "silence", rubrique_cle: null, variantes: [] },
      { cle: "sentiment", libelle: "sentiment", rubrique_cle: null,
        variantes: [{ cle: "surprise", libelle: "surprise" }] }] } },
  { id: AUTRE, nom: "Illisible", travail: false, plan: null },
];

test("la liste « Porte… » : le Mode libre d'abord, entrées et variantes, rubriques en retrait", () => {
  const g = P.optionsPorte(GRILLES);
  assert.deepEqual(g.map((x) => x.nom), ["Mode libre", "Signaux"], "sans plan, pas de groupe");
  const nb = (s) => s.replace(/^ +/, "");
  assert.deepEqual(g[0].options.map((o) => [o.valeur, nb(o.texte), o.profondeur]), [
    [`${TRAVAIL}/entree/silence`, "silence", 0],
    [`${TRAVAIL}/entree/sentiment`, "sentiment", 0],
    [`${TRAVAIL}/variante/sentiment/surprise`, "sentiment : surprise", 1],
  ]);
  assert.deepEqual(g[1].options.map((o) => [o.valeur, nb(o.texte), o.profondeur]), [
    [`${SONS}/entree/vieux`, "vieux (retirée)", 0],
    [`${SONS}/rubrique/sons`, "Rubrique : Sons", 0],
    [`${SONS}/rubrique/sons > voix`, "Rubrique : Voix", 1],
    [`${SONS}/entree/cri`, "cri", 2],
    [`${SONS}/entree/ton-de-voix`, "ton de voix", 2],
    [`${SONS}/variante/ton-de-voix/chuchote`, "ton de voix : chuchoté", 3],
    [`${SONS}/variante/ton-de-voix/crie`, "ton de voix : crié", 3],
    [`${SONS}/rubrique/provenance`, "Rubrique : Provenance", 0],
    [`${SONS}/entree/echo`, "écho", 1],
  ]);
  // Le retrait est fait d'espaces insécables, trois par étage.
  assert.equal(g[1].options[3].texte.indexOf("cri"), 6);
  assert.deepEqual(P.optionsPorte([]), []);
});

test("le nom d'un filtre posé : par le plan, par les résultats, sinon par sa clé", () => {
  const dico = P.dictionnaire(GRILLES);
  assert.deepEqual(P.libellePorte(`${TRAVAIL}/variante/sentiment/surprise`, dico),
                   { grille: "Mode libre", libelle: "sentiment : surprise" });
  assert.deepEqual(P.libellePorte(`${SONS}/rubrique/sons > voix`, dico),
                   { grille: "Signaux", libelle: "rubrique Voix" });
  assert.deepEqual(P.libellePorte(`${SONS}/qualificatif/sources/objet`, dico),
                   { grille: "Signaux", libelle: "source du son : objet" });
  // « ou » entre deux valeurs d'un filtre écrit dans l'adresse : chacune nommée.
  assert.deepEqual(P.libellePorte(`${SONS}/entree/cri/echo`, dico),
                   { grille: "Signaux", libelle: "cri ou écho" });
  // Une grille que la liste ne connaît pas : ce que les résultats ont rendu la nomme.
  P.apprendre(dico, [rel(42, "Ailleurs", "lieu", "grotte")]);
  assert.deepEqual(P.libellePorte("42/variante/lieu/grotte", dico),
                   { grille: "Ailleurs", libelle: "lieu : grotte" });
  assert.deepEqual(P.libellePorte("42/entree/autre", dico),
                   { grille: "Ailleurs", libelle: "autre" });
  // Rien de connu : la clé, et la grille par son numéro.
  assert.deepEqual(P.libellePorte("77/variante/a/b", new Map()),
                   { grille: "Grille 77", libelle: "a : b" });
  assert.deepEqual(P.libellePorte("n'importe quoi", dico),
                   { grille: "", libelle: "n'importe quoi" });
});

test("apprendre ne remplace pas ce que le plan nomme", () => {
  const dico = P.dictionnaire(GRILLES);
  P.apprendre(dico, [{ ...rel(SONS, "Signaux", "cri"), entree: "ancien libellé" }]);
  assert.equal(P.libellePorte(`${SONS}/entree/cri`, dico).libelle, "cri");
});

test("l'adresse porte les filtres : répétés, dans leur ordre, sans doublon", () => {
  assert.deepEqual(P.portesDe("q=x&porte=3%2Fentree%2Fcri&porte=7%2Fentree%2Fa&porte=3%2Fentree%2Fcri&porte="),
                   ["3/entree/cri", "7/entree/a"]);
  assert.deepEqual(P.portesDe(new URLSearchParams("porte=1/entree/a")), ["1/entree/a"]);
  assert.deepEqual(P.portesDe(""), []);
  let l = P.ajouterPorte([], "3/entree/cri");
  l = P.ajouterPorte(l, "7/entree/a");
  assert.deepEqual(P.ajouterPorte(l, "3/entree/cri"), l, "un filtre ne se double pas");
  assert.deepEqual(P.ajouterPorte(l, " "), l);
  assert.deepEqual(P.retirerPorte(l, "3/entree/cri"), ["7/entree/a"]);
  const p = P.avecPortes(new URLSearchParams("q=x"), l);
  assert.equal(p.toString(), "q=x&porte=3%2Fentree%2Fcri&porte=7%2Fentree%2Fa");
  assert.deepEqual(P.portesDe(p), l, "aller-retour par l'adresse");
});

test("le module ne touche pas au document au chargement", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(P.MODE_LIBRE, "Mode libre");
  assert.equal(P.nomDeGrille({ travail: true, grille: "Travail en cours" }), "Mode libre");
  assert.equal(P.nomDeGrille({ travail: false, nom: "Signaux" }), "Signaux");
});
