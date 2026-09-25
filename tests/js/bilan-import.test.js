/* Tests unitaires du bilan d'un import de vocabulaire (static/lib/bilan-import.js).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Le défaut réparé est MUET : un import entièrement refusé annonçait « 0 créé » sur le
   ton d'un succès, et aucune suite ne lisait la phrase. Chaque test ci-dessous vise une
   façon de le rouvrir — un motif perdu, un pluriel faux, une liste qui ne se borne plus. */
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const assert = require("node:assert/strict");
const { MOTIFS, DETAILS_MAX, SANS_ECRITURE, nombre, bilan, suite, menuImport }
  = require("../../static/lib/bilan-import.js");

/* Une réponse de `POST /api/lexique/importer`, à la forme exacte du serveur. */
function reponse({ lignes = 0, cree = [0, 0, 0], refusees = {}, anomalies = [],
                   avertissements = [] } = {}) {
  const [d, di, v] = cree;
  return {
    resume: {
      domaines: { cree: d, existant: 0 }, dimensions: { cree: di, existant: 0 },
      valeurs: { cree: v, existant: 0 },
      refusees: Object.assign({ libelle_pris: 0, lecture_seule: 0, parent_ailleurs: 0 }, refusees),
    },
    lignes, anomalies, avertissements,
  };
}

test("les motifs de l'écran sont ceux du serveur, mot pour mot et dans le même ordre", () => {
  // `lexique_import.MOTIFS` est la source ; un motif reformulé côté Python laisserait sinon
  // l'écran dire autre chose que l'avertissement ligne par ligne. Un motif AJOUTÉ côté
  // serveur ne fait pas tomber ce test — l'écran l'affiche sous sa clé brute (cf. le test
  // « motif inconnu »), jamais ne le perd ; lui donner des mots est un geste d'écran.
  const source = fs.readFileSync(path.join(__dirname, "../../lexique_import.py"), "utf8");
  const bloc = source.match(/^MOTIFS = \{([\s\S]*?)\}/m);
  assert.ok(bloc, "MOTIFS introuvable dans lexique_import.py");
  const serveur = [...bloc[1].matchAll(/"(\w+)":\s*"([^"]+)"/g)].map((m) => [m[1], m[2]]);
  assert.ok(serveur.length >= 2, "la lecture de MOTIFS ne voit plus rien");
  const communs = serveur.filter(([cle]) => cle in MOTIFS);
  assert.deepEqual(Object.entries(MOTIFS), communs,
    "un motif de l'écran manque au serveur, a changé de mots ou d'ordre");
});

test("tout accepté : la synthèse compte les créations, ton de succès, aucun détail", () => {
  const b = bilan(reponse({ lignes: 3, cree: [1, 2, 3] }));
  assert.equal(b.texte, "Import : 1 domaine, 2 dimensions, 3 valeurs créés.");
  assert.equal(b.ton, "success");
  assert.deepEqual(b.details, []);
  assert.equal(b.reste, 0);
});

test("partiellement refusé : le nombre de lignes refusées, par motif, ton neutre", () => {
  const b = bilan(reponse({
    lignes: 4, cree: [0, 1, 1], refusees: { libelle_pris: 2, lecture_seule: 1 },
    avertissements: ["L.3 : a", "L.4 : b", "L.5 : c"] }));
  assert.equal(b.texte, "Import : 0 domaine, 1 dimension, 1 valeur créés. "
    + "3 lignes refusées : libellé déjà pris (2), en lecture seule pour vous (1).");
  assert.equal(b.ton, "");
  assert.deepEqual(b.details, ["L.3 : a", "L.4 : b", "L.5 : c"]);
});

test("tout refusé : ne dit pas « 0 créé », et prend le ton d'une erreur", () => {
  const b = bilan(reponse({ lignes: 3, refusees: { libelle_pris: 3 } }));
  assert.equal(b.texte, "Rien n'a été importé. 3 lignes refusées : libellé déjà pris (3).");
  assert.equal(b.ton, "error");
  assert.ok(!/créé/.test(b.texte), "un import vide se dirait comme un succès sans nouveauté");
});

test("un motif à zéro n'est pas nommé, un seul refus se dit au singulier", () => {
  const b = bilan(reponse({ lignes: 2, cree: [0, 1, 0], refusees: { lecture_seule: 1 } }));
  assert.match(b.texte, /1 ligne refusée : en lecture seule pour vous \(1\)\.$/);
  assert.ok(!b.texte.includes("libellé"), "un motif à zéro est nommé");
});

/* La synthèse n'est faite QUE de chiffres, des libellés de `MOTIFS` (ceux du serveur) et
   des phrases fixes du module. Garde de STRUCTURE et non de formulation : une liste de
   mots interdits (« caché », « collection »…) ne verrait pas « ailleurs », « privé » ou
   n'importe quel mot qu'on n'a pas pensé à interdire ; ici, tout mot ajouté fait tomber
   le test, et c'est à la relecture de décider s'il élargit ce que dit le serveur. */
const FIXES = ["Rien n'a été importé.", "Le fichier ne contient aucune ligne.", "Import :",
  "créés.", "lignes refusées", "ligne refusée", "lignes mal formées", "ligne mal formée",
  "ignorées.", "ignorée.", "domaines", "domaine", "dimensions", "dimension", "valeurs",
  "valeur"];

function horsVocabulaire(texte) {
  let reste = texte;
  const morceaux = Object.values(MOTIFS).concat(FIXES).sort((a, b) => b.length - a.length);
  for (const m of morceaux) reste = reste.split(m).join(" ");
  return reste.replace(/[\s\d(),.:]+/g, "");
}

test("la synthèse ne dit rien d'autre que des chiffres, les motifs du serveur et ses phrases fixes", () => {
  const cas = [];
  for (const lignes of [0, 1, 3]) {
    for (const cree of [[0, 0, 0], [1, 1, 1], [2, 3, 4]]) {
      for (const refusees of [{}, { libelle_pris: 1 }, { lecture_seule: 2 },
                              { parent_ailleurs: 1 },
                              { libelle_pris: 2, lecture_seule: 1, parent_ailleurs: 3 }]) {
        for (const anomalies of [[], ["L.2"], ["L.2", "L.3"]]) {
          cas.push(reponse({ lignes, cree, refusees, anomalies }));
        }
      }
    }
  }
  for (const r of cas) {
    const t = bilan(r).texte;
    assert.equal(horsVocabulaire(t), "", `mot hors vocabulaire dans : ${t}`);
  }
  // La garde voit quelque chose : un mot ajouté la fait tomber.
  assert.notEqual(horsVocabulaire("3 lignes refusées : libellé déjà pris ailleurs (3)."), "");
});

test("le troisième motif (AUTH-11, 2026-09-24) se dit avec ses mots, après les deux autres", () => {
  // `parent_ailleurs` : un terme neuf, ou une dimension rattachée, hors de la collection de
  // son parent — un parent VISIBLE, que le dire ne révèle pas. Il s'affiche en toutes
  // lettres, pas sous sa clé brute, et à sa place dans l'ordre du serveur.
  const b = bilan(reponse({ lignes: 4, cree: [0, 1, 0],
                            refusees: { parent_ailleurs: 2, libelle_pris: 1 } }));
  assert.equal(b.texte, "Import : 0 domaine, 1 dimension, 0 valeur créés. 3 lignes refusées : "
    + "libellé déjà pris (1), hors de la collection de son parent (2).");
  assert.equal(b.ton, "");
});

test("un motif inconnu de l'écran est affiché sous sa clé, jamais perdu", () => {
  const b = bilan(reponse({ lignes: 2, refusees: { motif_neuf: 2 } }));
  assert.equal(b.texte, "Rien n'a été importé. 2 lignes refusées : motif_neuf (2).");
  assert.equal(b.ton, "error");
});

test("les lignes mal formées se comptent à part et passent en tête du détail", () => {
  const b = bilan(reponse({ lignes: 1, cree: [0, 1, 0],
                            anomalies: ["L.3 : dimension vide — ligne ignorée"],
                            avertissements: ["x : deux définitions divergentes"] }));
  assert.equal(b.texte, "Import : 0 domaine, 1 dimension, 0 valeur créés. "
    + "1 ligne mal formée, ignorée.");
  assert.equal(b.ton, "", "un avertissement suffit à retirer le ton de succès");
  assert.deepEqual(b.details, ["L.3 : dimension vide — ligne ignorée",
                               "x : deux définitions divergentes"]);
  const deux = bilan(reponse({ anomalies: ["L.2", "L.3"] }));
  assert.equal(deux.texte, "Rien n'a été importé. 2 lignes mal formées, ignorées.");
});

test("un fichier sans ligne le dit, sans se donner pour un succès", () => {
  const b = bilan(reponse());
  assert.equal(b.texte, "Rien n'a été importé. Le fichier ne contient aucune ligne.");
  assert.equal(b.ton, "error");
});

test("le détail se borne à `max` lignes et compte le reste", () => {
  const avert = Array.from({ length: 25 }, (_, i) => `L.${i + 2} : refus`);
  const b = bilan(reponse({ lignes: 25, refusees: { libelle_pris: 25 },
                            avertissements: avert }));
  assert.equal(b.details.length, DETAILS_MAX);
  assert.deepEqual(b.details, avert.slice(0, DETAILS_MAX));
  assert.equal(b.reste, 25 - DETAILS_MAX);
  assert.equal(suite(b.reste), "… et 15 autres.");
  // Pile à la borne : rien de coupé, aucune ligne « et 0 autre ».
  const juste = bilan(reponse({ lignes: 3, refusees: { libelle_pris: 3 },
                                avertissements: avert.slice(0, 3) }), 3);
  assert.equal(juste.reste, 0);
  assert.equal(suite(juste.reste), "");
  assert.equal(suite(1), "… et 1 autre.");
});

test("le pluriel suit la règle française : singulier à 0 et à 1", () => {
  assert.equal(nombre(0, "valeur", "valeurs"), "0 valeur");
  assert.equal(nombre(1, "valeur", "valeurs"), "1 valeur");
  assert.equal(nombre(2, "valeur", "valeurs"), "2 valeurs");
});

/* Le menu « Importer dans » (AUTH-12 appliqué à l'import) : l'écriture, pas la lecture. */
const COLS = [{ id: 1, nom: "A", ecrivable: true }, { id: 2, nom: "B", ecrivable: false },
              { id: 3, nom: "C", ecrivable: true }];

test("le menu n'offre que les collections où l'on écrit, après « Global »", () => {
  const m = menuImport(COLS, false);
  assert.equal(m.ouvert, true);
  assert.equal(m.note, "");
  assert.deepEqual(m.options, [{ value: "", label: "Global" },
                               { value: "1", label: "A" }, { value: "3", label: "C" }]);
});

test("sans collection où écrire, l'import se ferme et une note dit pourquoi", () => {
  const m = menuImport([{ id: 2, nom: "B", ecrivable: false }], false);
  assert.equal(m.ouvert, false);
  assert.deepEqual(m.options, []);
  assert.equal(m.note, SANS_ECRITURE);
  assert.match(SANS_ECRITURE, /^Vous n'écrivez dans aucune collection/);
  assert.equal(menuImport([], false).ouvert, false);
  assert.equal(menuImport(undefined, false).ouvert, false);
});

test("une portée totale garde « Global » ouvert, même sans collection", () => {
  const m = menuImport([], true);
  assert.equal(m.ouvert, true);
  assert.deepEqual(m.options, [{ value: "", label: "Global" }]);
  // …et ne réintroduit pas pour autant une collection que le serveur dit non écrivable.
  assert.deepEqual(menuImport([{ id: 2, nom: "B", ecrivable: false }], true).options,
                   [{ value: "", label: "Global" }]);
});

test("le choix précédent est gardé d'un remplissage à l'autre, s'il est encore offert", () => {
  // Revenir à « Global » enverrait le réimport dans le vocabulaire de toute l'instance.
  assert.equal(menuImport(COLS, false, "3").valeur, "3");
  assert.equal(menuImport(COLS, false, 3).valeur, "3");
  assert.equal(menuImport(COLS, false, "").valeur, "");
  assert.equal(menuImport(COLS, false).valeur, "", "premier remplissage : Global");
  // Une collection devenue non écrivable (ou disparue) n'est pas gardée.
  assert.equal(menuImport(COLS, false, "2").valeur, "");
  assert.equal(menuImport(COLS, false, "9").valeur, "");
});
