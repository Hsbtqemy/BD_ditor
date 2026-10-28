/* Tests unitaires de la partie COMMUNE de Ctrl+Z (static/lib/annulation.js), lue par
   l'Atelier et la page Annotation. Lancés par `node --test tests/js` (et via
   tests/test_js_unit.py sous pytest). Que chaque surface rafraîchisse ce qu'elle montre se
   joue dans un navigateur (test_e2e_conflit_a_deux.py, test_e2e_annotation_page.py). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

const U = require("../../static/lib/annulation.js");

test("se charge sans document", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(typeof U.annuler, "function");
});

test("le message d'un Ctrl+Z réussi dit ce qui n'a pas été rendu", () => {
  assert.deepEqual(U.messageAnnule({ description: "pose d'un relevé" }),
                   { texte: "Annulé : pose d'un relevé", duree: 4000 });
  const m = U.messageAnnule({ description: "x", liens_non_rendus: 2, tags_non_rendus: 1,
                              releves_non_rendus: 3 });
  assert.match(m.texte, /2 liens non rendus/);
  assert.match(m.texte, /1 tag non rendu \(supprimé depuis/);
  assert.match(m.texte, /3 relevés non rendus \(grille désactivée/);
  assert.equal(m.duree, 8000);
  assert.match(U.messageAnnule({ description: "x", releves_non_rendus: 1 }).texte,
               /1 relevé non rendu \(/);
  assert.equal(U.messageAnnule({ description: "x", tags_non_rendus: 1 }).duree, 8000);
});

test("le raccourci : Ctrl/⌘+Z hors d'un champ de saisie", () => {
  const ev = (o) => ({ ctrlKey: true, key: "z", target: { tagName: "DIV" }, ...o });
  assert.equal(U.estRaccourci(ev({})), true);
  assert.equal(U.estRaccourci(ev({ key: "Z" })), true);
  assert.equal(U.estRaccourci(ev({ ctrlKey: false, metaKey: true })), true);
  assert.equal(U.estRaccourci(ev({ ctrlKey: false })), false);
  assert.equal(U.estRaccourci(ev({ shiftKey: true })), false);
  assert.equal(U.estRaccourci(ev({ key: "y" })), false);
  for (const tagName of ["INPUT", "TEXTAREA", "SELECT"]) {
    assert.equal(U.estRaccourci(ev({ target: { tagName } })), false, tagName);
  }
});

function env(reponse) {
  const dits = [];
  const appels = [];
  return {
    dits, appels,
    toast: (m, genre, duree) => dits.push([m, genre || "", duree || null]),
    apiSend: async (methode, chemin, corps) => {
      appels.push([methode, chemin, corps]);
      if (reponse instanceof Error) throw reponse;
      return reponse;
    },
  };
}

test("annuler : la réponse est rendue, et dite", async () => {
  const e = env({ description: "pose", planche_id: 3, region_id: 7 });
  const res = await U.annuler(e);
  assert.deepEqual(res, { description: "pose", planche_id: 3, region_id: 7 });
  assert.deepEqual(e.appels, [["POST", "/api/undo", undefined]]);
  assert.deepEqual(e.dits, [["Annulé : pose", "", 4000]]);
});

test("annuler : rien à annuler n'est pas une erreur ; une panne en est une", async () => {
  const vide = Object.assign(new Error("Rien à annuler."), { statut: 404 });
  const e = env(vide);
  assert.equal(await U.annuler(e), null);
  assert.deepEqual(e.dits, [["Rien à annuler.", "", null]]);
  const panne = env(Object.assign(new Error("Erreur 500"), { statut: 500 }));
  assert.equal(await U.annuler(panne), null);
  assert.deepEqual(panne.dits, [["Erreur 500", "error", null]]);
});

test("annuler : le refus de CONC-3, sans « passer » quand le serveur ne l'offre pas", async () => {
  const conflit = { champ: "note", valeur_actuelle: "b", auteur: "Bob", date: null };
  const e = env(Object.assign(new Error("conflit"), { statut: 409, detail: { conflit } }));
  assert.equal(await U.annuler(e), null);
  assert.equal(e.dits.length, 1);
  assert.equal(e.dits[0][1], "error");
  assert.equal(e.dits[0][0], require("../../static/lib/conflit.js").messageAnnulationRefusee(conflit));
});

test("« Passer ce geste » : sans boîte des messages, le refus se dit seul", async () => {
  const conflit = { champ: "note", valeur_actuelle: "b", auteur: "Bob", date: null };
  const e = env(Object.assign(new Error("conflit"),
                              { statut: 409, detail: { conflit, passable: { evenement_id: 9 } } }));
  e.document = { getElementById: () => null };
  assert.equal(await U.annuler(e), null);
  assert.equal(e.dits.length, 1);
  assert.equal(e.dits[0][1], "error");
});
