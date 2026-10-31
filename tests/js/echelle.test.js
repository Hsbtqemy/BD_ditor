/* Tests unitaires de l'échelle des crans et de l'effacement (static/lib/echelle.js, COL-3,
   tranche 3b). Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Ce module dit les MOTS de l'écran tranché par Hugo sur maquette le 2026-10-25 : ce qu'un
   cran ajoute (l'aperçu de « Copie… »), ce qu'un retour efface (« Part »), « qui perd quoi »
   avant d'effacer, et par quel chemin l'on efface sans demander. Une phrase fausse ici fait
   faire un geste qu'on n'aurait pas fait — ou cache à quelqu'un qu'il efface le travail des
   autres. Que les deux écrans s'en servent se joue dans un navigateur
   (tests/test_e2e_ecran_3b.py). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

test("le module se charge sans document, sans fenêtre et sans adresse", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(typeof window, "undefined");
  assert.equal(typeof location, "undefined");
  const chemin = require.resolve("../../static/lib/echelle.js");
  delete require.cache[chemin];
  const api = require(chemin);
  assert.equal(typeof api.lignesEchelle, "function");
});

const E = require("../../static/lib/echelle.js");
const date = (d) => `le-${d}`;

/* ── L'échelle et ses mots ─────────────────────────────────────────────────────── */

test("cinq crans dans l'ordre, et les crans d'arrivée de « repartir » sans le plus haut", () => {
  assert.deepEqual(E.VALEURS, ["images", "decoupage", "transcription", "grammaire", "annotations"]);
  assert.deepEqual(E.CRANS_DE_REPARTIR, ["images", "decoupage", "transcription", "grammaire"]);
  assert.equal(E.rang("transcription"), 2);
  assert.equal(E.rang("inconnu"), -1);
});

test("les mots d'un cran : jusqu'où, vers où, le bouton, la puce", () => {
  assert.equal(E.jusqua("images"), "images seules");
  assert.equal(E.jusqua("annotations"), "jusqu'aux annotations");
  assert.equal(E.jusqua("inconnu"), "inconnu", "une valeur inconnue se dit telle quelle");
  assert.equal(E.vers("decoupage"), "au découpage");
  assert.equal(E.boutonRepartir("transcription"), "Repartir de la transcription");
  assert.equal(E.boutonRepartir("images"), "Repartir des images seules");
  assert.equal(E.boutonRepartir("x"), "Repartir de zéro");
  assert.equal(E.repartieDe("grammaire"), "repartie de la grammaire relue");
});

/* ── « Copie… » : l'échelle en tableau ───────────────────────────────────────────── */

const APERCU = { copies: { regions: 1840, textes: 1310, corrections: 0, annotations: 420,
                           tags: 610, attributs: 230, locuteurs: 980, presences: 0 },
                 laisses: { tags: 38, attributs: 0 }, personnages: 9, etat: "demande",
                 repondra: "proprietaire" };

test("une ligne par cran, ce qu'elle AJOUTE en nombres, grise quand la source n'a pas ce travail", () => {
  const l = E.lignesEchelle(APERCU);
  assert.deepEqual(l.map((x) => x.valeur), E.VALEURS);
  assert.equal(l[0].texte, "la notice et les planches");
  assert.equal(l[0].vide, false, "les images seules ne sont jamais vides");
  assert.equal(l[1].texte, "1 840 régions");
  assert.equal(l[2].texte, "1 310 textes");
  assert.equal(l[3].vide, true);
  assert.equal(l[3].texte, "rien : la source n'a pas ce travail");
  assert.equal(l[4].texte, "420 annotations · 610 tags · 230 attributs de case · 980 locuteurs",
               "un compte nul ne s'écrit pas");
});

test("sans aperçu, l'échelle dit ce que chaque cran ajoute en mots, sans rien supposer", () => {
  const l = E.lignesEchelle(null);
  assert.ok(l.every((x) => !x.vide));
  assert.equal(l[2].texte, "le texte des bulles");
});

test("sous le tableau : ce qui reste et ce qui devient lisible, au cran des annotations seulement", () => {
  const s = E.sousLEchelle(APERCU, "annotations", "Exercices");
  assert.equal(s.restent, "Restent : 38 tags");
  assert.ok(s.aide.includes("« Exercices » ne voit pas"));
  assert.ok(!/«[^»]*tag/.test(s.restent), "jamais un libellé");
  assert.equal(s.personnages, "9 fiches de personnage deviennent lisibles ici");
  assert.deepEqual(E.sousLEchelle(APERCU, "grammaire", "X"), { restent: "", aide: "", personnages: "" });
  assert.deepEqual(E.sousLEchelle(null, "annotations", "X"), { restent: "", aide: "", personnages: "" });
});

test("la réponse attendue : immédiat aux images seules, sinon ce que le serveur a dit", () => {
  const im = E.reponseCopie({ cran: "images", etat: "demande", arrivee: "X" });
  assert.deepEqual([im.direct, im.bouton], [true, "Copier les images"]);
  assert.ok(im.texte.startsWith("Immédiat"));
  const fait = E.reponseCopie({ cran: "transcription", etat: "fait", arrivee: "X" });
  assert.deepEqual([fait.direct, fait.bouton], [true, "Copier jusqu'à la transcription"]);
  assert.ok(fait.texte.includes("vous tenez toutes les collections"));
  const prop = E.reponseCopie({ cran: "decoupage", etat: "demande", repondra: "proprietaire",
                                arrivee: "Exercices" });
  assert.deepEqual([prop.direct, prop.bouton], [false, "Demander"]);
  assert.equal(prop.texte, "Son propriétaire doit l'accepter : copier ce travail le fait lire dans « Exercices ».");
  const adm = E.reponseCopie({ cran: "decoupage", etat: "demande", repondra: "administrateur" });
  assert.ok(adm.texte.startsWith("Un administrateur doit l'accepter"));
  // Sans réponse du serveur, rien n'est dit immédiat.
  assert.equal(E.reponseCopie({ cran: "decoupage" }).direct, false);
  const total = E.reponseCopie({ cran: "annotations", etat: "demande", total: true });
  assert.equal(total.direct, true, "la portée totale copie tout de suite");
});

/* ── Repartir de zéro ─────────────────────────────────────────────────────────── */

test("« Revenir… » : les crans au niveau du travail ou au-dessus sont éteints", () => {
  const c = E.cransRepartir("transcription");
  assert.deepEqual(c.map((x) => [x.valeur, x.eteint]),
                   [["images", false], ["decoupage", false], ["transcription", true],
                    ["grammaire", true]]);
  assert.equal(c[0].libelle, "Aux images seules");
  assert.equal(c[0].sous, "plus aucune région");
  assert.equal(c[1].sous, "garder le découpage");
  assert.equal(c[2].sous, "le travail ne va pas plus haut");
  assert.ok(E.cransRepartir("images").every((x) => x.eteint), "rien au-dessus des images");
  assert.ok(E.cransRepartir("annotations").every((x) => !x.eteint));
});

test("le cran coché à l'ouverture n'ôte que la couche du dessus", () => {
  assert.equal(E.cranParDefaut("annotations"), "grammaire");
  assert.equal(E.cranParDefaut("grammaire"), "transcription");
  assert.equal(E.cranParDefaut("decoupage"), "images");
  assert.equal(E.cranParDefaut("images"), null);
});

test("« Part » : les nombres de l'aperçu, validations comprises, dans l'ordre de l'échelle", () => {
  assert.deepEqual(E.part({ annotations: 2, regions: 0, textes: 12, planches_devalidees: 3,
                            corrections: 1 }),
                   ["12 textes", "1 correction", "2 annotations", "3 validations de planche"]);
  assert.deepEqual(E.part({}), []);
  // Le nom d'un détail est du cran des annotations : il se compte quand il part ou suit.
  assert.deepEqual(E.part({ presences: 1, noms: 2, planches_devalidees: 1 }),
                   ["1 présence", "2 noms de détail", "1 validation de planche"]);
  const l = E.lignesEchelle({ copies: { regions: 1, noms: 1 } });
  assert.equal(l[l.length - 1].texte, "1 nom de détail");
});

test("ce qui reste, pour un album et pour une planche", () => {
  assert.equal(E.restent(null, 46), "Sur les 46 planches. Restent : les images, la notice, les planches et leur verrou.");
  assert.equal(E.restent("la planche 3 (i.003)", 46),
               "Seule la planche 3 (i.003) change. Restent : ses images, la notice et son verrou.");
  assert.ok(E.restent("le paratexte i.001").startsWith("Seul le paratexte"));
});

test("le panneau : faire, demander, attendre — et une planche ne se demande pas (B4)", () => {
  const d = E.panneauRepartir({ direct: true, pouvoir: "responsable" });
  assert.deepEqual([d.mode, d.texte], ["direct", "Vous êtes responsable du projet : rien à demander."]);
  assert.equal(E.panneauRepartir({ direct: true }).texte, "Rien à demander.");
  const dem = E.panneauRepartir({ direct: false });
  assert.equal(dem.mode, "demande");
  assert.ok(dem.texte.includes("la demande part à un administrateur"));
  const pl = E.panneauRepartir({ direct: false, planche: true });
  assert.equal(pl.mode, "planche");
  assert.ok(pl.texte.includes("ne se demande pas"));
  // Hugo, 2026-10-25 : il renvoie à la demande sur l'album entier, ou à un administrateur.
  assert.ok(pl.texte.includes("Demandez-le pour l'album entier"), pl.texte);
  assert.ok(pl.texte.includes("adressez-vous à un administrateur"), pl.texte);
  const att = E.panneauRepartir({ direct: false, attente: { cran: "decoupage",
                                                            date_creation: "2026-10-24" }, dateLue: date });
  assert.equal(att.mode, "attente");
  assert.ok(att.texte.startsWith("Repartir du découpage est déjà demandé, le le-2026-10-24"));
  // Une planche qu'on PEUT ramener soi-même : le geste, pas le refus de B4.
  assert.equal(E.panneauRepartir({ direct: true, planche: true, pouvoir: "proprietaire" }).mode,
               "direct");
  // Qui peut le faire soi-même ne lit jamais « demandé » : `direct` l'emporte.
  assert.equal(E.panneauRepartir({ direct: true, attente: { cran: "images" } }).mode, "direct");
});

test("la certification de repartir reprend les mots de la suppression, adaptés", () => {
  assert.ok(E.CERTIFICATION_REPARTIR.texte.startsWith("Repartir de zéro détruit ce qui a été posé sur les planches"));
  assert.ok(E.CERTIFICATION_REPARTIR.texte.endsWith("Pouvez-vous certifier que ces données ne sont pas importantes ?"));
});

/* ── Le chemin de l'effacement ───────────────────────────────────────────────────── */

test("le chemin le plus précis d'abord ; aucun, rien n'est supposé", () => {
  assert.equal(E.pouvoir({ total: true, responsable: true }), "admin");
  assert.equal(E.pouvoir({ bac: true, createur: true }), "bac");
  assert.equal(E.pouvoir({ createur: true, responsable: true }), "createur");
  assert.equal(E.pouvoir({ responsable: true, proprietaire: true }), "responsable");
  assert.equal(E.pouvoir({ proprietaire: true }), "proprietaire");
  assert.equal(E.pouvoir({}), null);
});

test("le créateur seul : sa copie, et personne d'autre — le travail recopié compris", () => {
  const vue = { creee_par: "lea", travail_des_autres: [], travail_recopie: null };
  assert.equal(E.createurIntact(vue, "lea"), true);
  assert.equal(E.createurIntact(vue, "sam"), false);
  assert.equal(E.createurIntact({ ...vue, travail_des_autres: [{ agent: "sam" }] }, "lea"), false);
  assert.equal(E.createurIntact({ ...vue, travail_recopie: { gestes: { regions: 1 } } }, "lea"), false);
  assert.equal(E.createurIntact(null, "lea"), false);
  assert.equal(E.createurIntact(vue, null), false, "sans login, personne n'est le créateur");
  // Un créateur inconnu (avant le fonds) sur un poste sans login : pas « vous l'avez créée ».
  assert.equal(E.createurIntact({ creee_par: null, travail_des_autres: [] }, null), false);
});

/* ── Qui perd quoi ─────────────────────────────────────────────────────────────── */

const TRAVAIL = [
  { agent: "hbrunet", agent_nom: "Hélène Brunet", collectif: false, dernier: "2027-10-21",
    gestes: { regions: 400, token_correction: 1100, annotations: 190, bulle_locuteur: 10 } },
  { agent: "stagiaire", agent_nom: null, collectif: true, dernier: "2027-10-18",
    gestes: { token_correction: 900 } },
  { agent: null, agent_nom: null, collectif: false, dernier: null,
    gestes: { region_attribut: 3 } },
  { agent: "etu", agent_nom: "Étu", collectif: false, dernier: "2027-09-01",
    gestes: { document: 2 } },
];

test("supprimer : toutes les sortes, une colonne seulement si quelqu'un y a un geste", () => {
  const t = E.quiPerdQuoi(TRAVAIL, { geste: "supprimer", dateLue: date });
  assert.equal(t.titre, "Ce que 4 autres personnes perdent");
  assert.deepEqual(t.colonnes.map((c) => c.cle), ["regions", "corrections", "annotations", "document"],
                   "aucune validation : pas de colonne « validations »");
  assert.deepEqual(t.lignes.map((l) => l.qui),
                   ["Hélène Brunet (hbrunet)", "stagiaire — compte partagé", "Auteur non écrit", "Étu (etu)"]);
  assert.equal(t.lignes[0].valeurs.annotations, 200, "les annotations réunissent leurs sortes");
  assert.equal(t.lignes[0].dernier, "le-2027-10-21");
  assert.equal(t.note, "Des gestes, comptés au journal");
  assert.ok(t.aide.includes("défaits compris"));
});

test("repartir : seules les sortes que ce cran efface ; qui n'en a aucune ne perd rien", () => {
  const t = E.quiPerdQuoi(TRAVAIL, { geste: "repartir", cran: "grammaire" });
  assert.deepEqual(t.colonnes.map((c) => c.cle), ["annotations"]);
  assert.deepEqual(t.lignes.map((l) => l.qui), ["Hélène Brunet (hbrunet)", "Auteur non écrit"],
                   "les corrections et la notice restent : ni stagiaire, ni Étu ne perdent rien");
  assert.equal(t.titre, "Ce que 2 autres personnes perdent");
  const tr = E.quiPerdQuoi(TRAVAIL, { geste: "repartir", cran: "transcription" });
  assert.deepEqual(tr.colonnes.map((c) => c.cle), ["corrections", "annotations"]);
  const im = E.quiPerdQuoi(TRAVAIL, { geste: "repartir", cran: "images" });
  assert.ok(im.colonnes.some((c) => c.cle === "regions"));
  assert.ok(!im.colonnes.some((c) => c.cle === "document"), "repartir garde la notice et les scans");
});

test("une seule personne ; personne ; le retrait ; un titre imposé", () => {
  assert.equal(E.quiPerdQuoi([TRAVAIL[0]], { geste: "supprimer" }).titre, "Ce qu'une autre personne perd");
  assert.equal(E.quiPerdQuoi([], { geste: "supprimer" }), null);
  assert.equal(E.quiPerdQuoi(null, { geste: "supprimer" }), null);
  assert.equal(E.quiPerdQuoi([TRAVAIL[3]], { geste: "repartir", cran: "images" }), null,
               "seule la notice touchée : repartir n'y efface rien");
  const rt = E.quiPerdQuoi([TRAVAIL[0]], { geste: "retirer",
                                          recopie: { gestes: { token_correction: 5 }, dernier: "2027-01-01" } });
  assert.equal(rt.titre, "Qui y a travaillé (rien n'est effacé)");
  assert.equal(rt.lignes[1].qui, "Recopié d'une autre copie (auteurs non nommés)");
  assert.equal(E.quiPerdQuoi([TRAVAIL[0]], { geste: "repartir", cran: "images", titre: "T" }).titre, "T");
});

test("le tableau dessiné échappe ce qu'il écrit", () => {
  const html = E.htmlQuiPerdQuoi(E.quiPerdQuoi([{ agent: "<b>x</b>", gestes: { regions: 1 } }],
                                               { geste: "supprimer" }));
  assert.ok(html.includes("&lt;b&gt;x&lt;/b&gt;"));
  assert.ok(!html.includes("<b>x</b>"));
  assert.equal(E.htmlQuiPerdQuoi(null), "");
});

/* ── Entre deux projets (E7) ─────────────────────────────────────────────────────── */

const COPIES = [
  { album_id: 10, titre: "V", niveau: "decoupage", tient: false, apercu: null },
  { album_id: 11, titre: "V", niveau: "annotations", tient: true,
    apercu: { copies: { regions: 3 }, laisses: {}, personnages: 0 } },
  { album_id: 12, titre: "V", niveau: "annotations", tient: true, apercu: null },
];
const ALBUMS = [{ id: 11, collections: [{ id: 1, nom: "Inventaire" }] }];

test("« Depuis quelle copie » : la première qui tient, jamais une éteinte ; le choix retenu s'il tient", () => {
  assert.equal(E.copieParDefaut(COPIES), 11);
  assert.equal(E.copieParDefaut(COPIES, 12), 12);
  assert.equal(E.copieParDefaut(COPIES, 10), 11, "une copie trop peu travaillée ne se coche pas");
  assert.equal(E.copieParDefaut([COPIES[0]]), null);
  assert.equal(E.nomCopie(COPIES[1], ALBUMS[0]), "« Inventaire »");
  assert.equal(E.nomCopie(COPIES[2], undefined), "« V »", "sans album lu, son titre");
  assert.deepEqual(E.nomCopieChoisie(COPIES, ALBUMS, null), { id: 11, nom: "« Inventaire »" });
  assert.equal(E.accepterDepuis("« Inventaire »"), "Accepter : copier depuis « Inventaire »");
  assert.equal(E.detailCopie(COPIES[0], { cran: "annotations" }),
               "travaillée jusqu'au découpage — pas assez haut pour jusqu'aux annotations");
});

test("les radios de la source : éteintes quand elles ne tiennent pas, l'aperçu de la cochée", () => {
  const html = E.htmlSourcesE7({ id: 5, cran: "annotations", collection_nom: "Base" },
                               { copies: COPIES, albums: ALBUMS, choisie: null });
  assert.equal((html.match(/data-e7-source="5"/g) || []).length, 3);
  assert.ok(/value="10"[^>]*disabled/.test(html.replace(/\s+/g, " ")), "la copie qui ne tient pas est éteinte");
  assert.ok(/value="11"[^>]*checked/.test(html.replace(/\s+/g, " ")));
  assert.ok(html.includes("3 régions"), "l'aperçu de la copie cochée");
  assert.ok(E.htmlSourcesE7({ id: 5 }, { copies: [] }).includes("Aucune copie que vous lisez"));
});

test("« attend … » : qui tient le travail, ou c'est à l'administrateur", () => {
  assert.equal(E.attend(["Hélène Brunet"]), "attend Hélène Brunet");
  assert.equal(E.attend(["A", "B", "A"]), "attend A et B");
  assert.equal(E.attend([]), "aucun responsable ne tient ce travail : à vous");
  assert.equal(E.attend([], { dansLeProjet: true }),
               "aucun propriétaire ne tient toutes ses collections : à vous");
  assert.deepEqual(E.responsablesDesSources([
    { responsables: [{ genre: "utilisateur", principal: "mdumas", nom: "Marion Dumas" }] },
    { responsables: [{ genre: "groupe", principal: "lettrage" },
                     { genre: "utilisateur", principal: "mdumas", nom: "Marion Dumas" }] }]),
    ["Marion Dumas", "groupe lettrage"]);
});

test("l'aperçu d'une demande : ce qui part, ce qui reste sans nom, ce qui devient lisible", () => {
  const a = E.apercuDemande(APERCU, "Exercices");
  assert.ok(a.partent.includes("1 840 régions"));
  assert.deepEqual(a.restent, ["38 tags"]);
  assert.ok(a.personnages.includes("9 fiches de personnage deviennent lisibles dans « Exercices »"));
  assert.equal(E.apercuDemande(null).rien, false);
  assert.ok(E.htmlApercuDemande(null).includes("n'a pas pu être compté"));
});

/* ── Les traces ──────────────────────────────────────────────────────────────── */

test("la puce d'une copie remise à zéro : le cran, la date, et qui en infobulle s'il est rendu", () => {
  assert.deepEqual(E.puceRepartie({ cran: "transcription", le: "2027-10-12", par: "lea", par_nom: "Léa" }, date),
                   { texte: "repartie de la transcription le le-2027-10-12",
                     titre: "Par Léa. Ce qui était au-dessus a été effacé ; le journal garde l'acte." });
  assert.ok(!E.puceRepartie({ cran: "images", le: "x" }, date).titre.includes("Par"),
            "une lectrice reçoit la puce sans nom");
  assert.equal(E.puceRepartie(null), null);
});

test("la puce d'une copie née d'une autre ; rien pour la copie d'origine", () => {
  assert.equal(E.puceCopie("origine"), "");
  assert.equal(E.puceCopie(null), "");
  assert.equal(E.puceCopie("images"), "copie vierge");
  assert.equal(E.puceCopie("grammaire"), "copie · jusqu'à la grammaire relue");
});

test("l'avis de retrait : qui, quand, le motif ; « vous » pour soi-même", () => {
  const r = { titre: "Le Gorille", par: "proprio", par_nom: "Paule", le: "2027-10-25", motif: "Erreur" };
  assert.deepEqual(E.ligneRetrait(r, "hbrunet", date),
                   { texte: "« Le Gorille » a été retiré du projet par Paule le le-2027-10-25 : il est gardé au fonds, avec son travail.",
                     motif: "Motif : Erreur" });
  assert.ok(E.ligneRetrait(r, "proprio", date).texte.includes("par vous"));
  assert.equal(E.ligneRetrait({ ...r, motif: null }, "x").motif, "");
});

test("le panneau du retrait nomme les collections et ceux qui le verront disparaître, hors soi", () => {
  const cols = [
    { nom: "Corpus", proprietaires: [{ genre: "utilisateur", principal: "proprio", nom: "Paule" }] },
    { nom: "Témoins", proprietaires: [{ genre: "utilisateur", principal: "hbrunet", nom: "Hélène" },
                                      { genre: "groupe", principal: "oralite" }] },
  ];
  assert.equal(E.texteRetirer("Oralité", cols),
               "Il quitte toutes les collections de « Oralité » : « Corpus » et « Témoins ». Il part au fonds avec son travail ; un administrateur peut le rendre.");
  assert.equal(E.proprietairesQuiVerront(cols, "proprio"),
               "Hélène et le groupe oralite le verront disparaître, avec votre nom et la date.");
  assert.equal(E.proprietairesQuiVerront([cols[0]], "proprio"), "", "personne d'autre que soi");
  assert.ok(E.proprietairesQuiVerront([cols[0]], "admin").startsWith("Paule le verra"));
});

test("« + Créer une collection » éteint nomme les responsables, ou dit que seuls les administrateurs créent", () => {
  assert.equal(E.raisonCreerEteint("Oralité", ["Paule Propriétaire"]),
               "Dans « Oralité », seuls les responsables créent des collections : demandez-le à Paule Propriétaire.");
  assert.equal(E.raisonCreerEteint("Repli", []),
               "Dans « Repli », seuls les administrateurs de l'instance créent des collections.");
});
