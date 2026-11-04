/* Tests unitaires du formulaire de construction d'une grille (static/lib/grille-formulaire.js).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Ce qui se joue ici sans navigateur : les réponses aux six questions lues dans le plan et ce
   qu'elles envoient, ce qui ATTEND chez le formulaire (rien ne part tant que le serveur le
   refuserait), ce qui s'offre selon ce que les relevés emploient — une entrée employée ne se
   supprime jamais, « Fusionner dans… » jamais sur une fermée —, l'ordre, et la faute d'un
   import qui mène à son objet. Les plans ont la forme exacte de `grilles.plan`, les emplois
   celle de `grille_ecriture.emplois`. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const F = require("../../static/lib/grille-formulaire.js");

const E = (cle, o = {}) => ({ cle, libelle: cle, forme: "simple", rubrique_cle: null,
                              rubriques: [], definition: null, structure: null, piege: null,
                              exemples: [], precision: null, lien: false, cible_declaree: [],
                              cibles: ["case"], pose: "zone", cardinalite: "une",
                              cardinalite_declaree: null, liste_cle: null, retiree: false,
                              variantes: [], ...o });
const V = (cle) => ({ cle, libelle: cle, definition: null, structure: null, piege: null,
                      exemples: [] });
const PLAN = {
  porte_sur: ["case"],
  rubriques: [{ cle: "int", libelle: "Intérieur", parent_cle: null },
              { cle: "ext", libelle: "Extérieur", parent_cle: null },
              { cle: "ville", libelle: "En ville", parent_cle: "ext" },
              { cle: "rue", libelle: "Rues", parent_cle: "ville" }],
  entrees: [E("domicile", { rubrique_cle: "int", forme: "variantes",
                            variantes: [V("cuisine"), V("chambre")] }),
            E("ecole", { rubrique_cle: "int" }),
            E("magasin", { rubrique_cle: "ville", forme: "qualificatifs", liste_cle: "moment" }),
            E("ailleurs")],
  listes: [{ cle: "moment", libelle: "moment", qualificatifs: [{ cle: "jour", libelle: "jour" },
                                                               { cle: "nuit", libelle: "nuit" }] },
           { cle: "vide", libelle: "vide", qualificatifs: [] }],
};
const entree = (cle) => PLAN.entrees.find((e) => e.cle === cle);

/* --- Les réponses -------------------------------------------------------------------- */

test("une cible déclarée se lit comme une réponse à la question 2, et revient telle quelle", () => {
  const cas = [[[], { choix: "grille", sortes: [] }, []],
               [["mots"], { choix: "mots", sortes: [] }, ["mots"]],
               [["case"], { choix: "case", sortes: [] }, ["case"]],
               [["planche"], { choix: "planche", sortes: [] }, ["planche"]],
               [["texte", "bulle"], { choix: "zone", sortes: ["bulle", "texte"] }, ["bulle", "texte"]],
               [["case", "bulle"], { choix: "zone", sortes: ["bulle", "case"] }, ["bulle", "case"]]];
  for (const [cibles, rep, envoi] of cas) {
    assert.deepEqual(F.reponseCible(cibles), rep, cibles.join("|"));
    assert.deepEqual(F.ciblesDeReponse(rep), envoi, cibles.join("|"));
  }
  // Une zone sans sorte n'est pas une réponse complète : rien ne part.
  assert.equal(F.ciblesDeReponse({ choix: "zone", sortes: [] }), null);
});

test("« comme d'ordinaire » dit le défaut de la cible effective", () => {
  assert.equal(F.reponseCardinalite(null), "ordinaire");
  assert.equal(F.reponseCardinalite("une"), "une");
  assert.equal(F.cardinaliteParDefaut(["mots"]), "plusieurs");
  assert.equal(F.cardinaliteParDefaut(["bulle", "texte"]), "une");
  assert.equal(F.cardinaliteParDefaut(["planche"]), "une");
  // Une entrée sans cible à elle suit celle de la grille.
  assert.deepEqual(F.reponses(E("x"), null, ["mots"]).ciblesEffectives, ["mots"]);
  assert.deepEqual(F.reponses(E("x", { cible_declaree: ["planche"] }), null, ["mots"])
    .ciblesEffectives, ["planche"]);
});

/* --- Ce qui attend : rien ne part tant que le serveur le refuserait -------------------- */

test("« une variante » sans variante attend, et la première variante part avec la forme", () => {
  const e = entree("ecole");
  const r = F.repondre(e, null, "forme", "variantes");
  assert.equal(r.envoi, null);                          // rien ne part encore
  assert.deepEqual(r.att, { forme: "variantes" });
  assert.deepEqual(F.manques(e, r.att, PLAN), [{ q: 4, texte: "Ajoutez au moins une variante." }]);
  assert.deepEqual(F.envoiVariante(7, e, r.att, " porche "), {
    methode: "PATCH", chemin: "/api/grilles/7/entrees/ecole",
    corps: { forme: "variantes", variantes: [{ libelle: "porche" }], vu: { forme: "simple" } } });
  // Sur une entrée déjà à variantes, une variante de plus.
  assert.deepEqual(F.envoiVariante(7, entree("domicile"), null, "salon"), {
    methode: "POST", chemin: "/api/grilles/7/entrees/domicile/variantes",
    corps: { libelle: "salon" } });
});

test("« des cases d'une liste » attend sa liste, et la liste part avec la forme", () => {
  const e = entree("ecole");
  const r = F.repondre(e, null, "forme", "qualificatifs");
  assert.equal(r.envoi, null);
  assert.deepEqual(F.manques(e, r.att, PLAN)[0].q, 4);
  const choisie = F.repondre(e, r.att, "liste", "moment");
  assert.deepEqual(choisie.envoi, { forme: "qualificatifs", liste_cle: "moment" });
  assert.equal(choisie.att, null);
  // Une liste vide ne se nomme pas : seules les listes qui ont une case s'offrent.
  assert.deepEqual(F.listesUtilisables(PLAN).map((l) => l.cle), ["moment"]);
  // Sans aucune liste utilisable, la question dit où en créer une.
  assert.match(F.manques(e, r.att, { ...PLAN, listes: [] })[0].texte, /« \+ Liste »/);
  // Changer de liste une entrée déjà à cocher : la liste seule.
  assert.deepEqual(F.repondre(entree("magasin"), null, "liste", "autre").envoi,
                   { liste_cle: "autre" });
});

test("revenir à « Rien » part tout de suite, et défait ce qui attendait", () => {
  const e = entree("magasin");
  assert.deepEqual(F.repondre(e, null, "forme", "simple").envoi, { forme: "simple" });
  const att = F.repondre(entree("ecole"), null, "forme", "variantes").att;
  const r = F.repondre(entree("ecole"), att, "forme", "simple");
  assert.equal(r.envoi, null);                          // elle était déjà simple
  assert.equal(r.att, null);
});

test("une zone entière sans sorte attend ; cochée, elle part", () => {
  const e = entree("ecole");
  const r = F.repondre(e, null, "cible", { choix: "zone", sortes: [] });
  assert.equal(r.envoi, null);
  assert.equal(F.manques(e, r.att, PLAN)[0].q, 2);
  const s = F.repondre(e, r.att, "cible", { choix: "zone", sortes: ["texte", "bulle"] });
  assert.deepEqual(s.envoi, { cible: ["bulle", "texte"] });
  assert.equal(s.att, null);
  // Revenir à « comme la grille » envoie une cible vide ; répondre ce qui est écrit, rien.
  assert.deepEqual(F.repondre(E("x", { cible_declaree: ["mots"] }), null, "cible",
                              { choix: "grille", sortes: [] }).envoi, { cible: [] });
  assert.equal(F.repondre(e, null, "cible", { choix: "grille", sortes: [] }).envoi, null);
});

test("un champ à écrire attend son nom ; « Non » le retire", () => {
  const e = entree("ecole");
  const oui = F.repondre(e, null, "precision", true);
  assert.equal(oui.envoi, null);
  assert.equal(F.manques(e, oui.att, PLAN)[0].q, 5);
  assert.deepEqual(F.repondre(e, oui.att, "nomPrecision", " laquelle ").envoi,
                   { precision: "laquelle" });
  const nomme = E("y", { precision: "laquelle" });
  assert.deepEqual(F.repondre(nomme, null, "precision", false).envoi, { precision: null });
  // Vider le nom d'un champ écrit ne l'efface pas en silence : la réponse est « Non ».
  const vide = F.repondre(nomme, null, "nomPrecision", "  ");
  assert.equal(vide.envoi, null);
  assert.match(vide.refus, /répondez « Non »/);
});

test("ce qui attend se compte, éteint « Publier… » et se voit dans l'aperçu", () => {
  const att = new Map([["ecole", { forme: "variantes" }]]);
  assert.equal(F.aCompleter(PLAN, att), 1);
  assert.deepEqual(F.publiable(PLAN, att), { ok: false,
    raison: "1 entrée à compléter, marquée ● dans le plan." });
  assert.deepEqual(F.publiable(PLAN, new Map()), { ok: true, raison: "" });
  assert.equal(F.publiable({ entrees: [E("a", { retiree: true })] }, new Map()).ok, false);
  const ap = F.planDApercu(PLAN, att);
  assert.equal(ap.entrees.find((e) => e.cle === "ecole").forme, "variantes");
  assert.equal(PLAN.entrees.find((e) => e.cle === "ecole").forme, "simple");   // intact
});

/* --- Les valeurs vues ---------------------------------------------------------------- */

test("chaque champ envoyé porte sa valeur vue, à la forme du contenu", () => {
  const e = E("x", { cible_declaree: ["texte", "bulle"], cardinalite_declaree: null,
                     exemples: ["A"], definition: "def", lien: true });
  assert.deepEqual(F.corpsEntree(e, { definition: "neuve", cible: ["mots"], exemples: [] }), {
    definition: "neuve", cible: ["mots"], exemples: [],
    vu: { definition: "def", cible: ["bulle", "texte"], exemples: ["A"] } });
  assert.equal(F.vuEntree(e, "cardinalite"), null);
  assert.equal(F.vuEntree(e, "lien"), true);
  assert.equal(F.vuEntree(e, "precision"), null);
});

test("les exemples s'écrivent un par ligne ; un « | » est refusé, sans rien envoyer", () => {
  assert.deepEqual(F.exemplesDeTexte(" A \n\nB\r\n"), { exemples: ["A", "B"], refus: null });
  const r = F.exemplesDeTexte("A | B");
  assert.equal(r.exemples, null);
  assert.match(r.refus, /« \| »/);
  assert.equal(F.texteDExemples(["A", "B"]), "A\nB");
});

/* --- Ce qui s'offre ------------------------------------------------------------------ */

test("une entrée employée ne s'offre JAMAIS à supprimer, ouverte ou fermée", () => {
  const em = { entrees: { ecole: 3 }, variantes: {}, cases: {},
               fusionner_dans: { ecole: ["ailleurs"] } };
  for (const etat of ["vivante", "brouillon"]) {
    const o = F.offresEntree(entree("ecole"), em, etat);
    assert.equal(o.supprimer, false, etat);
    assert.equal(o.retirer, true, etat);
    assert.equal(o.releves, 3, etat);
  }
  // Personne ne l'emploie : elle se supprime, et ne se retire ni ne se fusionne.
  const libre = F.offresEntree(entree("ailleurs"), em, "vivante");
  assert.deepEqual([libre.supprimer, libre.retirer, libre.fusionner], [true, false, null]);
});

test("« Fusionner dans… » s'offre sur une ouverte, jamais sur une fermée", () => {
  const em = { entrees: { ecole: 1 }, variantes: {}, cases: {},
               fusionner_dans: { ecole: ["ailleurs"] } };
  assert.deepEqual(F.offresEntree(entree("ecole"), em, "vivante").fusionner, ["ailleurs"]);
  assert.equal(F.offresEntree(entree("ecole"), em, "brouillon").fusionner, null);
  // Ouverte, aucune entrée ne peut la recevoir : l'offre est là, vide — l'écran le dit.
  assert.deepEqual(F.offresEntree(entree("ecole"), { ...em, fusionner_dans: {} }, "vivante")
    .fusionner, []);
});

test("une entrée retirée se remet ; employée, elle se fusionne encore sur une ouverte", () => {
  const e = E("vieux", { retiree: true });
  const em = { entrees: { vieux: 2 }, variantes: {}, cases: {}, fusionner_dans: { vieux: [] } };
  const o = F.offresEntree(e, em, "vivante");
  assert.deepEqual([o.remettre, o.retirer, o.supprimer], [true, false, false]);
  assert.deepEqual(o.fusionner, []);
  assert.equal(F.offresEntree(e, {}, "vivante").supprimer, true);
});

test("sous des relevés, une ouverte fige la forme et la liste ; une fermée non", () => {
  const em = { entrees: { magasin: 1 }, variantes: {}, cases: {}, fusionner_dans: {} };
  const ouverte = F.offresEntree(entree("magasin"), em, "vivante");
  assert.equal(ouverte.figee, true);
  assert.match(ouverte.raisonFigee, /1 relevé la porte/);
  assert.deepEqual(F.formesPossibles(entree("magasin"), ouverte),
                   { simple: ouverte.raisonFigee, variantes: ouverte.raisonFigee,
                     qualificatifs: "" });
  const fermee = F.offresEntree(entree("magasin"), em, "brouillon");
  assert.equal(fermee.figee, false);
  assert.deepEqual(F.formesPossibles(entree("magasin"), fermee),
                   { simple: "", variantes: "", qualificatifs: "" });
});

test("une entrée à variantes ne change pas de forme : sa dernière variante reste", () => {
  const p = F.formesPossibles(entree("domicile"), F.offresEntree(entree("domicile"), {}, "brouillon"));
  assert.equal(p.variantes, "");
  assert.match(p.simple, /garde au moins une variante/);
  assert.match(p.qualificatifs, /garde au moins une variante/);
});

test("une variante ou une case employée ne se supprime pas, ni la dernière", () => {
  const em = { entrees: {}, variantes: { domicile: { cuisine: 2 } }, cases: { jour: 1 },
               fusionner_dans: {} };
  assert.deepEqual(F.offresVariante(entree("domicile"), "cuisine", em),
                   { supprimer: false, releves: 2,
                     raison: "2 relevés portent cette variante : elle ne se supprime pas." });
  assert.equal(F.offresVariante(entree("domicile"), "chambre", em).supprimer, true);
  const une = E("u", { forme: "variantes", variantes: [V("seule")] });
  assert.equal(F.offresVariante(une, "seule", em).supprimer, false);
  assert.equal(F.offresCase(PLAN, "moment", "jour", em).supprimer, false);
  assert.equal(F.offresCase(PLAN, "moment", "nuit", em).supprimer, true);
  const seule = { ...PLAN, listes: [{ cle: "moment", libelle: "m",
                                      qualificatifs: [{ cle: "nuit", libelle: "nuit" }] }] };
  assert.match(F.offresCase(seule, "moment", "nuit", em).raison, /dernière case/);
});

test("une rubrique ne se supprime que vide, une liste que si personne ne la nomme", () => {
  assert.equal(F.offresRubrique(PLAN, "int").supprimer, false);
  assert.match(F.offresRubrique(PLAN, "ville").raison, /1 entrée et 1 rubrique/);
  assert.equal(F.offresRubrique(PLAN, "rue").supprimer, true);
  assert.deepEqual(F.offresListe(PLAN, "moment").sert, ["magasin"]);
  assert.equal(F.offresListe(PLAN, "vide").supprimer, true);
});

test("une rubrique ne se range ni sous elle-même ni sous ses descendantes", () => {
  assert.deepEqual(F.placesDeRubrique(PLAN, "ext").map((r) => r.cle), ["int"]);
  assert.deepEqual(F.placesDeRubrique(PLAN, "rue").map((r) => r.cle), ["int", "ext", "ville"]);
  assert.equal(F.cheminDeRubrique(PLAN, "rue"), "Extérieur › En ville › Rues");
});

test("la tête dit où s'écrit un geste, et quelle version se montre", () => {
  const v = (numero, etat) => ({ numero, etat });
  assert.equal(F.ouSEcrit({ ouverte: true, versions: [v(1, "vivante")] }).etiquette,
               "ouverte · s'écrit en place");
  assert.equal(F.ouSEcrit({ ouverte: false, versions: [v(1, "publiee")] }).etiquette,
               "v1 publiée · un brouillon v2 naîtra au premier changement");
  assert.deepEqual(F.ouSEcrit({ ouverte: false, versions: [v(1, "publiee"), v(2, "brouillon")] }),
                   { etiquette: "brouillon v2", brouillon: 2 });
  assert.equal(F.versionMontree({ versions: [v(1, "publiee"), v(2, "brouillon")] }), 2);
  assert.equal(F.versionMontree({ versions: [v(1, "publiee")] }), 1);
});

/* --- Le plan, l'ordre ---------------------------------------------------------------- */

test("le plan range chaque rubrique avec ses entrées, puis « Hors rubrique »", () => {
  const att = new Map([["ecole", { precision: true }]]);
  const em = { entrees: { magasin: 2 }, variantes: {}, cases: {}, fusionner_dans: {} };
  const l = F.lignesDuPlan(PLAN, att, em);
  assert.deepEqual(l.map((x) => `${x.t}:${x.cle}:${x.profondeur ?? ""}`), [
    "grille::0", "rubrique:int:0", "entree:domicile:1", "entree:ecole:1", "rubrique:ext:0",
    "rubrique:ville:1", "entree:magasin:2", "rubrique:rue:2", "sep:hors:", "entree:ailleurs:0"]);
  const ecole = l.find((x) => x.cle === "ecole");
  assert.deepEqual([ecole.etat, ecole.alerte], ["● à compléter", true]);
  assert.equal(l.find((x) => x.cle === "domicile").etat, "2 var.");
  assert.equal(l.find((x) => x.cle === "magasin").etat, "cases · 2 relevés");
});

test("monter, descendre : la place parmi les frères, et l'ordre vu", () => {
  assert.deepEqual(F.freres(PLAN, "entree", "ecole"), ["domicile", "ecole"]);
  assert.deepEqual(F.deplacer(PLAN, "entree", "ecole", -1),
                   { quoi: "entree", cle: "ecole", place: 0, vu: ["domicile", "ecole"] });
  assert.equal(F.deplacer(PLAN, "entree", "ecole", 1), null);         // au bord
  assert.deepEqual(F.deplacer(PLAN, "rubrique", "int", 1),
                   { quoi: "rubrique", cle: "int", place: 1, vu: ["int", "ext"] });
  assert.deepEqual(F.deplacer(PLAN, "variante", "cuisine", 1, "domicile"),
                   { quoi: "variante", cle: "cuisine", place: 1, vu: ["cuisine", "chambre"],
                     entree_cle: "domicile" });
  assert.deepEqual(F.deplacer(PLAN, "case", "nuit", -1, "moment"),
                   { quoi: "case", cle: "nuit", place: 0, vu: ["jour", "nuit"],
                     liste_cle: "moment" });
});

/* --- La faute d'un import, et son objet ------------------------------------------------ */

test("« Corriger dans le formulaire ↗ » mène à l'objet que le plan connaît", () => {
  assert.deepEqual(F.cibleDeFaute({ cle: "ecole", colonne: "forme" }, PLAN),
                   { t: "entree", cle: "ecole" });
  assert.deepEqual(F.cibleDeFaute({ cle: "ville", colonne: "rubrique" }, PLAN),
                   { t: "rubrique", cle: "ville" });
  assert.deepEqual(F.cibleDeFaute({ cle: "nuit", listes: true }, PLAN),
                   { t: "liste", cle: "moment" });
  assert.deepEqual(F.cibleDeFaute({ cle: "moment", listes: true }, PLAN),
                   { t: "liste", cle: "moment" });
  assert.deepEqual(F.cibleDeFaute({ code: "porte_sur_inconnu", colonne: "porte_sur" }, PLAN),
                   { t: "grille", cle: "" });
  // Une entrée que le FICHIER ajoute n'est pas dans le plan : rien où mener.
  assert.equal(F.cibleDeFaute({ cle: "nouvelle", colonne: "forme" }, PLAN), null);
  assert.equal(F.cibleDeFaute({ cle: "ecole" }, null), null);
});
