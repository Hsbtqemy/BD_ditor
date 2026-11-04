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
