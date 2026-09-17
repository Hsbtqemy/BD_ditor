/* Tests purs de static/lib/conflit.js — ce que l'Atelier DIT d'un conflit (CONC-3). */
const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../../static/lib/conflit.js");

/* Les dates sont construites en HEURE LOCALE puis passées en ISO : le test ne dépend pas du
   fuseau de la machine qui le joue. */
const local = (a, mo, j, h, mi) => new Date(a, mo - 1, j, h, mi);
const iso = (d) => d.toISOString();
const MAINTENANT = local(2026, 9, 17, 18, 0);

test("les deux gestes vivent à un seul endroit, et ne se modifient pas en passant", () => {
  assert.equal(C.GESTES.remplacer, "Remplacer");
  assert.equal(C.GESTES.garderAutre, "Garder l'autre");
  assert.ok(Object.isFrozen(C.GESTES));
});

test("l'heure : sans zéro de tête, minutes sur deux chiffres", () => {
  assert.equal(C.heure(local(2026, 9, 17, 14, 32)), "14 h 32");
  assert.equal(C.heure(local(2026, 9, 17, 8, 5)), "8 h 05");
});

test("le jour même, hier, un autre jour, une autre année", () => {
  assert.equal(C.quand(iso(local(2026, 9, 17, 14, 32)), MAINTENANT), "à 14 h 32");
  assert.equal(C.quand(iso(local(2026, 9, 16, 14, 32)), MAINTENANT), "hier à 14 h 32");
  assert.equal(C.quand(iso(local(2026, 9, 15, 14, 32)), MAINTENANT), "le 15/09 à 14 h 32");
  assert.equal(C.quand(iso(local(2025, 12, 31, 23, 59)), MAINTENANT), "le 31/12/2025 à 23 h 59");
});

test("« hier » franchit un changement de mois", () => {
  assert.equal(C.quand(iso(local(2026, 8, 31, 22, 10)), local(2026, 9, 1, 7, 0)),
               "hier à 22 h 10");
});

test("une date illisible ne fabrique pas d'heure", () => {
  assert.equal(C.quand("", MAINTENANT), "");
  assert.equal(C.quand("pas une date", MAINTENANT), "");
});

test("qui : le nom affiché, le login à défaut, le même compte, ou personne", () => {
  assert.equal(C.parQui({ nom: "Bob Martin", login: "bob" }), "par Bob Martin");
  assert.equal(C.parQui({ nom: null, login: "bob" }), "par bob");
  assert.equal(C.parQui({ nom: "Alice", login: "alice", meme_compte: true }),
               "depuis un autre écran de ce même compte");
  assert.equal(C.parQui({ nom: null, login: null }), "ailleurs");
  assert.equal(C.parQui(null), "ailleurs");
});

test("le titre nomme le champ et l'accorde", () => {
  const auteur = { nom: "Bob Martin", login: "bob", le: iso(local(2026, 9, 17, 14, 32)) };
  assert.equal(C.titreConflit({ champ: "note", auteur }, MAINTENANT),
               "Note modifiée par Bob Martin à 14 h 32");
  assert.equal(C.titreConflit({ champ: "ocr_texte", auteur }, MAINTENANT),
               "Texte modifié par Bob Martin à 14 h 32");
  assert.equal(C.titreConflit({ champ: "note", auteur: { ...auteur, meme_compte: true } },
                              MAINTENANT),
               "Note modifiée depuis un autre écran de ce même compte à 14 h 32");
  assert.equal(C.titreConflit({ champ: "note", auteur: null }, MAINTENANT),
               "Note modifiée ailleurs");
});

test("le message d'une région supprimée dit ce qu'elle était", () => {
  const sup = { auteur: { nom: "Alice Dupont", login: "alice", le: iso(local(2026, 9, 17, 8, 14)) } };
  assert.equal(C.messageSuppression(sup, "case", MAINTENANT),
               "Cette case a été supprimée par Alice Dupont à 8 h 14.");
  assert.equal(C.messageSuppression(sup, "cartouche", MAINTENANT),
               "Ce cartouche a été supprimé par Alice Dupont à 8 h 14.");
  assert.equal(C.messageSuppression(sup, "inconnu", MAINTENANT),
               "Cette région a été supprimée par Alice Dupont à 8 h 14.");
});

test("une annulation refusée dit ce qui a changé, et depuis quand", () => {
  const conflit = { champ: "note", auteur: { nom: "Bob Martin", le: iso(local(2026, 9, 16, 9, 0)) } };
  assert.equal(C.messageAnnulationRefusee(conflit, MAINTENANT),
               "Annulation impossible : la note a été modifiée depuis par Bob Martin hier à 9 h 00.");
  assert.equal(C.messageAnnulationRefusee({ champ: "x", auteur: null }, MAINTENANT),
               "Annulation impossible : la position a été modifiée depuis ailleurs.");
});
