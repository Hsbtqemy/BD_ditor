/* Tests unitaires du projet courant (static/lib/projet.js, COL-3).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Ce module est lu par DEUX écrans — la bande du haut, sur les cinq surfaces, et la
   Bibliothèque — qui doivent désigner le même projet. Ce fichier garde la règle elle-même ;
   que les deux écrans s'en servent se joue dans un navigateur (tests/test_e2e_projets.py). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

test("le module se charge sans document, sans fenêtre, sans adresse et sans stockage", () => {
  // Vérifiées absentes AVANT : un Node qui les fournirait un jour rendrait ce test vert sur
  // un module qui lit le stockage au chargement.
  assert.equal(typeof document, "undefined");
  assert.equal(typeof window, "undefined");
  assert.equal(typeof location, "undefined");
  const chemin = require.resolve("../../static/lib/projet.js");
  delete require.cache[chemin];
  const api = require(chemin);
  assert.equal(typeof api.courant, "function");
  assert.equal(api.CLE, "bd-projet");
});

const { CLE, EVENEMENT, LONGUEUR_NOM, ROLES, courant, lire, retenir, choisir, duProjet,
        libelleRole } = require("../../static/lib/projet.js");

const REPLI = { id: 1, nom: "Projet principal", repli: true };
const SECOND = { id: 4, nom: "Séminaire 2026", repli: false };
const TROISIEME = { id: 7, nom: "Étude des émotions", repli: false };

/* La règle, par table : [ce qu'on peut nommer, ce qu'on avait retenu, le projet courant]. */
const CAS = [
  ["aucun projet, rien de retenu", [], null, null],
  ["aucun projet, un choix retenu d'avant", [], 4, null],
  ["la liste n'a pas pu être lue", null, 4, null],
  ["un seul projet, rien de retenu", [REPLI], null, 1],
  ["un seul projet, qui n'est pas celui de repli", [SECOND], null, 4],
  ["deux projets, rien de retenu : celui de repli", [REPLI, SECOND], null, 1],
  ["deux projets, le second retenu", [REPLI, SECOND], 4, 4],
  ["le projet retenu n'est plus visible : celui de repli", [REPLI, SECOND], 7, 1],
  ["le repli n'est pas en tête de liste : c'est lui quand même", [SECOND, REPLI], null, 1],
  ["sans projet de repli visible, le premier", [SECOND, TROISIEME], null, 4],
  ["sans projet de repli visible, le retenu", [SECOND, TROISIEME], 7, 7],
  ["le retenu n'est plus visible, et le repli non plus : le premier", [TROISIEME, SECOND], 1, 7],
];

for (const [nom, projets, retenu, attendu] of CAS) {
  test(`projet courant — ${nom}`, () => {
    assert.equal(courant(projets, retenu), attendu);
  });
}

test("un identifiant retenu se compare en NOMBRE, jamais en chaîne", () => {
  // `lire` rend un nombre ; passer la chaîne brute du stockage ne désignerait rien, et l'on
  // retomberait en silence sur le projet de repli à chaque page.
  assert.equal(courant([REPLI, SECOND], "4"), 1);
  assert.equal(courant([REPLI, SECOND], lire(faux({ [CLE]: "4" }))), 4);
});

/* Un stockage de doublure : ce qu'il contient, et s'il lève. */
function faux(contenu, leve) {
  const m = { ...contenu };
  return {
    getItem: (k) => { if (leve) throw new Error("refusé"); return k in m ? m[k] : null; },
    setItem: (k, v) => { if (leve) throw new Error("plein"); m[k] = v; },
    contenu: m,
  };
}

test("lire rend l'identifiant retenu, et rien d'autre qu'un identifiant", () => {
  assert.equal(lire(faux({ [CLE]: "12" })), 12);
  for (const v of ["", "abc", "0", "-3", "1.5", "07", " 4", "4 ", "null"]) {
    assert.equal(lire(faux({ [CLE]: v })), null, JSON.stringify(v));
  }
  assert.equal(lire(faux({})), null);
  assert.equal(lire(faux({ "bd-theme": "4" })), null);
});

test("un stockage absent ou qui lève ne fait rien échouer", () => {
  assert.equal(lire(null), null);
  assert.equal(lire(faux({ [CLE]: "4" }, true)), null);
  assert.equal(retenir(4, null), false);
  assert.equal(retenir(4, faux({}, true)), false);
});

test("retenir écrit sous la clé du projet, et lire le retrouve", () => {
  const s = faux({});
  assert.equal(retenir(9, s), true);
  assert.deepEqual(s.contenu, { [CLE]: "9" });
  assert.equal(lire(s), 9);
});

test("sous Node, sans stockage ni document, lire et choisir ne lèvent pas", () => {
  assert.equal(lire(), null);
  assert.doesNotThrow(() => choisir(4));
  assert.equal(EVENEMENT, "bd:projet-change");
});

test("les collections d'un projet sont celles qui le nomment", () => {
  const cols = [{ id: 10, projet_id: 1 }, { id: 11, projet_id: 4 }, { id: 12, projet_id: 1 }];
  assert.deepEqual(duProjet(cols, 1).map((c) => c.id), [10, 12]);
  assert.deepEqual(duProjet(cols, 4).map((c) => c.id), [11]);
  assert.deepEqual(duProjet(cols, 7), []);
});

test("sans projet courant, la liste est rendue ENTIÈRE et non vidée", () => {
  // La liste des projets n'a pas pu être lue : ce n'est pas une raison de cacher des
  // collections que le serveur vient de rendre.
  const cols = [{ id: 10, projet_id: 1 }, { id: 11, projet_id: 4 }];
  assert.deepEqual(duProjet(cols, null), cols);
  assert.deepEqual(duProjet(cols, undefined), cols);
  assert.deepEqual(duProjet(null, 1), []);
});

test("les rôles se disent dans les mots de l'écran, et un rôle inconnu se lit tel quel", () => {
  assert.equal(libelleRole("membre"), "membre");
  assert.equal(libelleRole("responsable"), "responsable du projet");
  assert.equal(libelleRole("observateur"), "observateur");
});

test("le premier rôle est celui qu'on reçoit en entrant", () => {
  // « + Faire entrer » pose `ROLES[0]` : si l'ordre s'inversait, entrer nommerait
  // responsable. L'accord avec le serveur, lui, est mesuré par tests/test_projet_ecran.py.
  assert.equal(ROLES[0], "membre");
  assert.ok(Number.isInteger(LONGUEUR_NOM) && LONGUEUR_NOM > 0);
});
