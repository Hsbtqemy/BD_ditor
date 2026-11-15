/* Tests unitaires du bloc « Grilles » de la fiche d'un projet (static/lib/grilles-projet.js).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Deux décisions se jouent ici sans navigateur : ce qui s'offre sur une grille selon son
   état, et le bilan d'un import en mots. Les réponses sont à la forme exacte du serveur
   (`_vue_grille`, `grille_import.importer`, `_refus_http`). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const G = require("../../static/lib/grilles-projet.js");

const v = (numero, etat, porte_sur = ["mots"]) => ({ numero, etat, porte_sur, note: null,
                                                     publiee_le: null, importee_le: null });

/* --- Ce qui s'offre ----------------------------------------------------------------- */

test("une grille fermée publiée, active : télécharger, réimporter, désactiver", () => {
  const e = G.etat({ id: 1, nom: "S", ouverte: false, retiree_le: null,
                     versions: [v(1, "publiee")], active: { numero: 1, etat: "publiee" } });
  assert.equal(e.etiquette, "v1 publiée · active");
  assert.equal(e.porteSur, "des mots");
  assert.deepEqual(e.telecharger, [{ numero: 1, libelle: "le classeur v1" }]);
  assert.equal(e.reimporter, true);
  assert.equal(e.publier, null);
  assert.equal(e.activer, null);            // déjà active dans cette version
  assert.equal(e.desactiver, true);
});

test("un brouillon s'offre à publier, et se télécharge à côté de la version publiée", () => {
  const e = G.etat({ ouverte: false, retiree_le: null,
                     versions: [v(1, "publiee"), v(2, "brouillon", ["case"])], active: null });
  assert.equal(e.etiquette, "v1 publiée · pas active · brouillon v2");
  assert.equal(e.publier, 2);
  assert.equal(e.activer, 1);               // la dernière publiée, pas le brouillon
  assert.equal(e.desactiver, false);
  assert.deepEqual(e.telecharger.map((t) => t.numero), [1, 2]);
  // Un brouillon seul ne s'active pas ; ce sur quoi il porte se dit quand même.
  const seul = G.etat({ ouverte: false, retiree_le: null, versions: [v(1, "brouillon", ["case"])],
                        active: null });
  assert.equal(seul.etiquette, "brouillon v1");
  assert.equal(seul.activer, null);
  assert.equal(seul.porteSur, "la case");
});

test("une grille ouverte : sa version vivante s'active, rien ne se publie", () => {
  const e = G.etat({ ouverte: true, retiree_le: null,
                     versions: [v(1, "vivante", ["bulle", "cartouche", "texte"])], active: null });
  assert.equal(e.etiquette, "ouverte · pas active");
  assert.equal(e.porteSur, "bulle, cartouche ou texte hors bulle");
  assert.equal(e.activer, 1);
  assert.equal(e.publier, null);
  assert.deepEqual(e.telecharger, [{ numero: 1, libelle: "le classeur" }]);
});

test("une grille retirée ne s'offre plus qu'à télécharger, et à désactiver si besoin", () => {
  const e = G.etat({ ouverte: false, retiree_le: "2026-11-04", versions: [v(1, "publiee"),
                     v(2, "brouillon")], active: null });
  assert.equal(e.etiquette, "retirée");
  assert.equal(e.reimporter, false);
  assert.equal(e.publier, null);
  assert.equal(e.activer, null);
  assert.equal(e.telecharger.length, 2);
});

/* --- Le bilan ------------------------------------------------------------------------ */

const faute = { code: "forme_inconnue", fichier: "2. Les entrées", ligne: 12, cle: "cri",
                colonne: "forme", question: "4. Ce qu'on choisit",
                probleme: "la réponse « libre » n'est pas une forme",
                a_faire: "répondez « rien », « une variante » ou « des cases d'une liste »" };

test("une faute dit OÙ, QUOI et QUE FAIRE, la feuille d'un classeur nommée comme telle", () => {
  const f = G.fauteEnMots(faute, true);
  assert.equal(f.ou, "feuille « 2. Les entrées », ligne 12 · « cri » · 4. Ce qu'on choisit");
  assert.equal(f.quoi, "La réponse « libre » n'est pas une forme.");
  assert.equal(f.faire, "Répondez « rien », « une variante » ou « des cases d'une liste ».");
  // Un CSV se nomme par son fichier ; la déclaration n'est pas une feuille.
  assert.equal(G.ouEnMots({ ...faute, fichier: "e.csv" }, false),
               "e.csv, ligne 12 · « cri » · 4. Ce qu'on choisit");
  assert.equal(G.ouEnMots({ fichier: "déclaration", question: "Porte sur" }, true),
               "déclaration · Porte sur");
  assert.equal(G.ouEnMots({}, true), "");
});

test("un refus en données : le verdict du serveur, ses fautes, et Importer éteint", () => {
  const corps = { message: "Le tableur est refusé : 1 anomalie(s). Rien n'est importé.",
                  verdict: { etat: "refuse", n: 1, phrase: "1 faute à corriger : rien n'est "
                             + "importé tant qu'il en reste une." },
                  a_savoir: [], anomalies: [faute], declaration: { nom: "S", ouverte: false,
                  porte_sur: "mots", note: null, lus: ["nom"] }, identifiants_deduits: [] };
  const vue = G.lireReponse(422, corps);
  assert.equal(vue.etat, "refuse");
  assert.equal(vue.phrase, corps.verdict.phrase);
  assert.equal(vue.fautes.length, 1);
  assert.equal(vue.changements.length, 0);
  const im = G.importable(vue, {});
  assert.equal(im.ok, false);
  assert.match(im.raison, /1 faute à corriger/);
  assert.equal(G.declarationEnMots(vue.declaration), "« S », fermée, porte sur des mots");
});

test("un refus en une phrase (nom pris, fichier illisible) se dit tel quel", () => {
  const vue = G.lireReponse(409, "Une grille de ce projet s'appelle déjà « S » : choisissez "
                                 + "un autre nom.");
  assert.equal(vue.etat, "refuse");
  assert.match(vue.phrase, /s'appelle déjà/);
  assert.equal(G.importable(vue, {}).ok, false);
  assert.equal(G.lireReponse(400, null).phrase, "Le fichier n'a pas pu être vérifié.");
});

test("un fichier juste : Importer s'offre ; « Ce qui va naître » se compte", () => {
  const vue = G.lireReponse(200, { verdict: { etat: "importable", phrase: "Le fichier est "
    + "juste : l'import peut se faire." }, a_savoir: [{ code: "identifiants_deduits",
    fichier: null, ligne: null, cle: null, colonne: null, question: null,
    probleme: "des identifiants manquaient", a_faire: null }],
    va_naitre: { rubriques: 2, entrees: 6, variantes: 1, listes: 1, qualificatifs: 0 },
    bilan: { nes: [], renommes: [], retouches: [], deplaces: [], changes: [], disparus: [] },
    a_repondre: [], grille_id: null, ecrit: false });
  assert.equal(vue.vaNaitre, "2 rubriques · 6 entrées · 1 variante · 1 liste");
  assert.equal(vue.aSavoir[0].quoi, "Des identifiants manquaient.");
  assert.deepEqual(G.importable(vue, {}), { ok: true, raison: "" });
  assert.equal(G.vaNaitreEnMots({ rubriques: 0, entrees: 0 }), "");
});

test("rien ne change : Importer reste éteint, et le dit", () => {
  const vue = G.lireReponse(200, { verdict: { etat: "aucun_changement", phrase: "…" },
                                   aucun_changement: true, a_repondre: [] });
  const im = G.importable(vue, {});
  assert.equal(im.ok, false);
  assert.match(im.raison, /Rien ne change/);
});

test("une entrée employée qui disparaît : Importer attend sa réponse", () => {
  const vue = G.lireReponse(200, { verdict: { etat: "a_repondre", phrase: "…" },
    a_repondre: [{ cle: "cri", libelle: "cri", releves: 2, choix: ["retirer", "fusionner"],
                   fusionner_dans: ["hurlement"] }],
    bilan: { nes: [{ quoi: "entree", cle: "hurlement", libelle: "hurlement" }], renommes: [],
             retouches: [], deplaces: [], changes: [],
             disparus: [{ quoi: "entree", cle: "cri", libelle: "cri", releves: 2,
                          decision: "a_repondre" }] } });
  assert.equal(vue.aRepondre.length, 1);
  assert.match(G.importable(vue, {}).raison, /1 entrée à répondre/);
  const choix = G.choixDeReponse(vue.aRepondre[0], { entree: { hurlement: "Hurlement" } });
  assert.deepEqual(choix.map((c) => c.valeur), ["retirer", "fusionner:hurlement"]);
  assert.match(choix[0].libelle, /ses 2 relevés restent/);
  assert.match(choix[1].libelle, /« Hurlement »/);
  assert.deepEqual(G.importable(vue, { cri: "retirer" }), { ok: true, raison: "" });
  // Ne part que la réponse d'une entrée qui la demande.
  assert.deepEqual(G.reponsesPourEnvoi(vue, { cri: "retirer", autre: "retirer", x: "" }),
                   { cri: "retirer" });
  const part = vue.changements.find((c) => c.genre === "disparaît");
  assert.equal(part.detail, "2 relevés posés · à répondre plus bas");
  // Un relevé seul : « son relevé reste ».
  assert.match(G.choixDeReponse({ ...vue.aRepondre[0], releves: 1 }, null)[0].libelle,
               /son relevé reste/);
});

test("« Ce qui change » nomme les objets par la version comparée", () => {
  const noms = G.nomsDuPlan({
    rubriques: [{ cle: "voix", libelle: "Voix" }, { cle: "image", libelle: "Image" }],
    entrees: [{ cle: "cri", libelle: "cri", variantes: [] },
              { cle: "onomatopee", libelle: "onomatopée", variantes: [{ cle: "bang", libelle: "bang" }] }],
    listes: [{ cle: "sources", libelle: "source du son",
               qualificatifs: [{ cle: "objet", libelle: "objet" }] }] });
  const lignes = G.changementsEnMots({
    nes: [{ quoi: "variante", cle: "onomatopee/boum", libelle: "boum" }],
    renommes: [{ quoi: "entree", cle: "cri", avant: "cri", apres: "cri perçant" }],
    retouches: [{ quoi: "variante", cle: "onomatopee/bang", champs: ["definition", "piege"] }],
    deplaces: [{ quoi: "entree", cle: "cri", avant: "voix", apres: null }],
    changes: [{ quoi: "entree", cle: "cri", champ: "retiree", avant: false, apres: true },
              { quoi: "version", cle: null, champ: "porte_sur", avant: "mots", apres: "case" }],
    disparus: [{ quoi: "qualificatif", cle: "sources/objet", libelle: "objet", releves: 0 },
               { quoi: "entree", cle: "echo", libelle: "écho", releves: 1,
                 decision: "fusionner:cri" }] }, noms);
  const dits = lignes.map((l) => [l.genre, l.quoi, l.nom, l.detail]);
  assert.deepEqual(dits, [
    ["naît", "variante", "boum", ""],
    ["renommée", "entrée", "cri → cri perçant", "même identifiant : ses relevés la suivent"],
    ["retouchée", "variante", "onomatopée › bang", "définition, piège"],
    ["déplacée", "entrée", "cri", "« Voix » → hors rubrique"],
    ["retirée", "entrée", "cri", "elle ne se pose plus ; ses relevés restent, à revoir"],
    ["changée", "la grille", "", "ce sur quoi la grille porte"],
    ["disparaît", "case", "objet", ""],
    ["disparaît", "entrée", "écho", "1 relevé posé · fusionnée dans « cri »"],
  ]);
});

test("seul un classeur .xlsx s'envoie", () => {
  assert.equal(G.estUnClasseur("Lieux.xlsx"), true);
  assert.equal(G.estUnClasseur("LIEUX.XLSX "), true);
  assert.equal(G.estUnClasseur("lieux.ods"), false);
  assert.equal(G.estUnClasseur("entrees.csv"), false);
});

test("une cible se dit en mots, une inconnue sous sa clé", () => {
  assert.equal(G.porteSurEnMots(["planche"]), "la planche");
  assert.equal(G.porteSurEnMots(["case", "zzz"]), "la case ou zzz");
  assert.equal(G.porteSurEnMots([]), "");
});

test("sur une grille fermée, l'entrée qui disparaît n'attend que « retirer »", () => {
  const vue = { etat: "a_repondre", fautes: [], aRepondre: [{ cle: "cri", libelle: "cri",
    releves: 1, choix: ["retirer"], fusionnerDans: [] }] };
  assert.deepEqual(G.importable(vue, {}), { ok: false,
    raison: "1 entrée à répondre : dites pour chacune « retirer »." });
  assert.deepEqual(G.choixDeReponse(vue.aRepondre[0], null).map((c) => c.valeur), ["retirer"]);
  assert.equal(G.importable(vue, { cri: "retirer" }).ok, true);
});

test("la grille de travail (le mode libre) : « Désactiver » s'y montre éteint, et dit pourquoi", () => {
  const travail = G.etat({ ouverte: true, travail: true, retiree_le: null,
                           versions: [v(1, "vivante", ["bulle"])], active: { numero: 1, etat: "vivante" } });
  assert.equal(travail.desactiver, true);
  assert.match(travail.desactiverRaison, /grille de travail du projet/);
  const autre = G.etat({ ouverte: true, retiree_le: null, versions: [v(1, "vivante", ["bulle"])],
                         active: { numero: 1, etat: "vivante" } });
  assert.equal(autre.desactiverRaison, null);
  // Pas active (une base d'avant) : rien à désactiver, rien à dire.
  const inactive = G.etat({ ouverte: true, travail: true, retiree_le: null,
                            versions: [v(1, "vivante")], active: null });
  assert.equal(inactive.desactiver, false);
  assert.equal(inactive.desactiverRaison, null);
});

/* --- La fin d'une grille (Hugo, 2026-11-13) ------------------------------------------ */

test("personne ne l'emploie : elle se supprime ; employée, elle se retire", () => {
  const base = { nom: "S", ouverte: false, retiree_le: null, versions: [v(1, "publiee")],
                 active: null, travail: false };
  const libre = G.etat({ ...base, releves: 0, passes: 0 });
  assert.deepEqual(libre.fin, { geste: "supprimer", releves: 0, passes: 0, raison: null });
  assert.equal(G.etat({ ...base, releves: 3, passes: 0 }).fin.geste, "retirer");
  // Une passe sans relevé l'emploie aussi : le serveur refuse alors de la supprimer.
  assert.equal(G.etat({ ...base, releves: 0, passes: 1 }).fin.geste, "retirer");
  // Sans les comptes (qui ne gère pas le projet), aucun geste.
  assert.equal(G.etat(base).fin, null);
});

test("active ou grille de travail : le geste s'éteint et dit pourquoi", () => {
  const base = { nom: "S", ouverte: false, retiree_le: null, versions: [v(1, "publiee")],
                 releves: 0, passes: 0 };
  const active = G.etat({ ...base, active: { numero: 1, etat: "publiee" }, travail: false });
  assert.match(active.fin.raison, /désactivez-la d'abord/);
  const travail = G.etat({ ...base, ouverte: true, versions: [v(1, "vivante")], active: null,
                           travail: true });
  assert.match(travail.fin.raison, /grille de travail du projet/);
});

test("retirée et employée, plus rien ; retirée sans emploi, elle se supprime", () => {
  const base = { nom: "S", ouverte: false, retiree_le: "2026-11-13", versions: [v(1, "publiee")],
                 active: null, travail: false };
  assert.equal(G.etat({ ...base, releves: 2, passes: 0 }).fin, null);
  assert.equal(G.etat({ ...base, releves: 0, passes: 0 }).fin.geste, "supprimer");
});

test("un brouillon se supprime à côté d'une version publiée, jamais seul", () => {
  const base = { nom: "S", ouverte: false, retiree_le: null, active: null, travail: false,
                 releves: 0, passes: 0 };
  assert.equal(G.etat({ ...base, versions: [v(1, "publiee"), v(2, "brouillon")] })
    .supprimerBrouillon, 2);
  // Seul, la grille part avec lui : « Supprimer… » le fait déjà.
  assert.equal(G.etat({ ...base, versions: [v(1, "brouillon")] }).supprimerBrouillon, null);
  assert.equal(G.etat({ ...base, ouverte: true, versions: [v(1, "vivante")] })
    .supprimerBrouillon, null);
});

test("la confirmation dit ce qui part et ce qui reste", () => {
  const g = { nom: "Sons", ouverte: false, retiree_le: null, active: null, travail: false,
              versions: [v(1, "publiee"), v(2, "brouillon")], releves: 0, passes: 0 };
  const e = G.etat(g);
  assert.deepEqual(G.confirmation(g, e, "supprimer"), {
    texte: "« Sons » part : personne ne l'emploie, aucun relevé ne se perd. "
      + "Ce geste ne s'annule pas.", bouton: "Supprimer la grille" });
  assert.equal(G.confirmation(g, e, "brouillon").bouton, "Supprimer le brouillon v2");
  const g3 = { ...g, releves: 3 };
  assert.equal(G.confirmation(g3, G.etat(g3), "retirer").texte,
    "Retirée, « Sons » ne s'active plus et ne reçoit plus de version. 3 relevés restent "
    + "lisibles. Ce geste ne s'annule pas.");
  const g1 = { ...g, releves: 1 };
  assert.match(G.confirmation(g1, G.etat(g1), "retirer").texte, /1 relevé reste lisible\./);
});

/* --- D'où vient une grille (v40) ------------------------------------------------------ */

test("une grille dérivée dit d'où elle vient ; une autre ne dit rien", () => {
  const g = { ouverte: false, retiree_le: null, versions: [v(1, "brouillon")], active: null };
  assert.equal(G.etat({ ...g, derivee_de: { nom: "Signaux", version: 2 } }).origine,
               "dérivée de « Signaux », v2");
  assert.equal(G.etat({ ...g, derivee_de: null }).origine, "");
  assert.equal(G.etat(g).origine, "");                  // une réponse d'avant la v40
  assert.equal(G.origineEnMots({ nom: "Signaux", version: null }), "dérivée de « Signaux »");
  assert.equal(G.origineEnMots({ nom: null, version: 3 }), "dérivée d'une autre grille, v3");
});

test("le bilan d'un import dit d'où viendra la grille neuve", () => {
  const corps = { verdict: { etat: "importable", phrase: "Le fichier est juste." },
                  a_savoir: [], va_naitre: { rubriques: 1, entrees: 2 }, a_repondre: [],
                  bilan: { nes: [], renommes: [], retouches: [], deplaces: [], changes: [],
                           disparus: [] }, grille_id: null, ecrit: false };
  assert.equal(G.lireReponse(200, { ...corps, derivee_de: { nom: "Signaux", version: 1 } })
    .deriveeDe, "dérivée de « Signaux », v1");
  assert.equal(G.lireReponse(200, { ...corps, derivee_de: null }).deriveeDe, "");
  assert.equal(G.lireReponse(422, "Le fichier est illisible.").deriveeDe, "");
});

/* --- La montée de version (ANN-7) --------------------------------------------------- */

test("une version publiée plus récente sur une grille qui porte des relevés : « Monter »", () => {
  const g = { ouverte: false, retiree_le: null, versions: [v(1, "publiee"), v(2, "publiee")],
              active: { numero: 1, etat: "publiee" }, releves: 3, passes: 0 };
  const e = G.etat(g);
  assert.equal(e.monter, 2);
  assert.equal(e.activer, null);
  // Sans relevé ni passe, c'est une activation ; sans les comptes (qui ne gère pas), rien.
  assert.deepEqual([G.etat({ ...g, releves: 0 }).activer, G.etat({ ...g, releves: 0 }).monter],
                   [2, null]);
  assert.equal(G.etat({ ...g, releves: 0, passes: 2 }).monter, 2);
  assert.equal(G.etat({ ...g, releves: undefined }).monter, null);
  // Une grille ouverte ne monte pas : elle n'a qu'une version.
  assert.equal(G.etat({ ...g, ouverte: true, versions: [v(1, "vivante")] }).monter, null);
});

const BILAN = {
  montee: true, de: 1, vers: 2, vu: "abc",
  verdict: { etat: "a_repondre", phrase: "3 relevés passent en version 2. 1 sera à revoir." },
  releves: { total: 3, normal: 2, a_revoir: 1, a_completer: 0 },
  causes: [{ cause: "variante_absente", etat: "a_revoir", n: 1, zones: [], hors_vue: 0 }],
  plan: { nes: [], renommes: [], retouches: [], deplaces: [], changes: [], disparus: [] },
  a_repondre: [{ cle: "echo", libelle: "écho", releves: 2, choix: ["laisser", "fusionner"],
                 fusionner_dans: ["origine-du-son"], reponse: null }],
  fautes: [], refus: [], passes_rouvertes: { n: 0, zones: [], hors_vue: 0 },
};

test("le bilan d'une montée en mots : les causes avec les mots de la page, les choix", () => {
  const vue = G.lireMontee(BILAN, { causes: { variante_absente: "cette valeur n'existe plus" },
                                    noms: { entree: { "origine-du-son": "origine du son" } } });
  assert.equal(vue.phrase, BILAN.verdict.phrase);
  assert.deepEqual(vue.causes, [{ cause: "variante_absente", etat: "a_revoir", n: 1,
                                  mots: "cette valeur n'existe plus" }]);
  assert.deepEqual(vue.aRepondre[0].choix.map((c) => c.valeur),
                   ["laisser", "fusionner:origine-du-son"]);
  assert.match(vue.aRepondre[0].choix[1].libelle, /« origine du son »/);
  assert.deepEqual(G.montable(vue, {}).ok, false);
  assert.match(G.montable(vue, {}).raison, /1 entrée retirée à répondre/);
  assert.deepEqual(G.montable(vue, { echo: "laisser" }), { ok: true, raison: "" });
  assert.deepEqual(G.reponsesDeMontee(vue, { echo: "laisser", autre: "x" }), { echo: "laisser" });
  // Perdue par la version sans y être retirée : la raison ne la dit pas « retirée ».
  const absente = G.lireMontee({ ...BILAN, a_repondre: [{ ...BILAN.a_repondre[0], absente: true }] });
  assert.equal(absente.aRepondre[0].absente, true);
  assert.match(G.montable(absente, {}).raison, /^1 entrée qui n'est plus dans la version à répondre/);
  assert.doesNotMatch(G.montable(absente, {}).raison, /retirée/);
});

test("une montée refusée n'offre pas « Monter », et dit pourquoi", () => {
  const vue = G.lireMontee({ ...BILAN, a_repondre: [], verdict: { etat: "refuse", phrase: "…" },
                             refus: [{ code: "cardinalite_contredite", cle: "cri", libelle: "cri",
                                       zone: { album_id: 1, planche_id: 2, region_id: 3 } }] });
  assert.equal(vue.refus[0].texte, "« cri » : deux relevés sur une même zone");
  assert.deepEqual(vue.refus[0].zone, { album_id: 1, planche_id: 2, region_id: 3 });
  assert.equal(G.montable(vue, {}).ok, false);
  assert.match(G.montable(vue, {}).raison, /deux relevés/);
});
