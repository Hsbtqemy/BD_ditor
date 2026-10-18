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
        albumsDuProjet, basculeVers, pourRanger, libelleRole } = require("../../static/lib/projet.js");

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

/* Les albums de travail d'un projet (COL-3, tranche 3) : la liste de la Bibliothèque, du lot
   et de l'Atelier. Par table : [les albums, le projet courant, les identifiants montrés].
   `projet_id` est le projet EFFECTIF publié par `GET /api/albums`. */
const AL1 = { id: 1, projet_id: 1, au_fonds: false },
      AL2 = { id: 2, projet_id: 4, au_fonds: false },
      AL3 = { id: 3, projet_id: 1, au_fonds: false },
      FONDS_P1 = { id: 4, projet_id: 1, au_fonds: true },     // gardée au fonds, emporte son projet
      FONDS_SANS = { id: 5, projet_id: null, au_fonds: true }, // importée au fonds, d'aucun projet
      ORPHELIN = { id: 6, projet_id: null, au_fonds: false };  // ne devrait pas exister
const ALBUMS = [
  ["le projet 1 : ses albums, dans l'ordre reçu", [AL1, AL2, AL3], 1, [1, 3]],
  ["le projet 4 : l'album de l'autre projet seul", [AL1, AL2, AL3], 4, [2]],
  ["un projet sans album : une liste vide", [AL1, AL2], 7, []],
  ["sans projet courant : tous les albums de travail", [AL1, AL2, AL3], null, [1, 2, 3]],
  ["sans projet courant (indéfini) : de même", [AL1, AL2], undefined, [1, 2]],
  ["une copie gardée au fonds ne se montre pas, même dans son projet", [AL1, FONDS_P1], 1, [1]],
  ["ni sans projet courant", [AL1, FONDS_P1, FONDS_SANS], null, [1]],
  ["une copie importée au fonds, sous un projet", [AL2, FONDS_SANS], 4, [2]],
  ["un album sans projet hors du fonds : d'aucun projet, montré sans projet courant",
   [AL1, ORPHELIN], null, [1, 6]],
  ["…et pas sous un projet", [AL1, ORPHELIN], 1, [1]],
  ["une liste illisible", null, 1, []],
  ["une liste illisible, sans projet", undefined, null, []],
];

for (const [nom, albums, projet, attendu] of ALBUMS) {
  test(`albums du projet courant — ${nom}`, () => {
    assert.deepEqual(albumsDuProjet(albums, projet).map((a) => a.id), attendu);
  });
}

test("le projet d'un album se compare en NOMBRE, jamais en chaîne", () => {
  assert.deepEqual(albumsDuProjet([AL1, AL2], "1").map((a) => a.id), []);
});

/* La bascule par l'adresse. Par table : [les projets nommables, le courant, le visé, le résultat]. */
const BASCULE = [
  ["un objet d'un autre projet nommable : on bascule", [REPLI, SECOND], 1, 4, 4],
  ["dans l'autre sens", [REPLI, SECOND], 4, 1, 1],
  ["le projet visé est déjà le courant : rien", [REPLI, SECOND], 4, 4, null],
  ["le projet visé n'est pas nommable : rien", [REPLI, SECOND], 1, 7, null],
  ["rien de visé (objet introuvable, ou sans projet) : rien", [REPLI, SECOND], 1, null, null],
  ["rien de visé (indéfini) : rien", [REPLI, SECOND], 1, undefined, null],
  ["sans projet courant, un visé nommable : on bascule", [REPLI, SECOND], null, 4, 4],
  ["aucun projet nommable : rien", [], null, 4, null],
  ["une liste illisible : rien", null, 1, 4, null],
];

for (const [nom, projets, courantId, vise, attendu] of BASCULE) {
  test(`bascule par l'adresse — ${nom}`, () => {
    assert.equal(basculeVers(projets, courantId, vise), attendu);
  });
}

/* Où un album peut se ranger : dans SON projet, lu dans ses collections — jamais dans le
   projet courant, que cette fonction ne reçoit même pas. Par table :
   [les collections de l'album, les candidates, les projets où il vit, les proposées, les écartées]. */
const A = { id: 10, projet_id: 1 }, B = { id: 11, projet_id: 1 }, C = { id: 12, projet_id: 4 },
      D = { id: 13, projet_id: 4 }, E = { id: 14, projet_id: 7 };
const RANGER = [
  ["un album d'un projet : les candidates de ce projet", [A], [B, C, D], [1], [11], 2],
  ["le même, vu depuis ses deux collections du même projet", [A, B], [C, E], [1], [], 2],
  ["un album de l'autre projet", [C], [A, B, D, E], [4], [13], 3],
  ["rien à écarter : toutes les candidates sont du projet", [A], [B], [1], [11], 0],
  ["aucune candidate", [A], [], [1], [], 0],
  ["un album de DEUX projets : aucune candidate, toutes écartées", [A, C], [B, D, E], [1, 4], [], 3],
  ["un album de deux projets, sans candidate", [A, C], [], [1, 4], [], 0],
  ["on ne lit aucune collection de l'album : rien n'est écarté", [], [B, C], [], [11, 12], 0],
  ["des collections sans projet lisible ne désignent aucun projet",
   [{ id: 20 }, { id: 21, projet_id: null }], [B, C], [], [11, 12], 0],
  ["des listes illisibles", null, null, [], [], 0],
];

for (const [nom, siennes, candidates, projets, proposees, ecartees] of RANGER) {
  test(`où ranger un album — ${nom}`, () => {
    const r = pourRanger(siennes, candidates);
    assert.deepEqual(r.projets, projets);
    assert.deepEqual(r.collections.map((c) => c.id), proposees);
    assert.equal(r.ecartees, ecartees);
  });
}

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

/* COL-3, écran de la 3a — ce que la base ouvre aux membres. */
test("trois positions, « ouverte » d'abord, la protégée vaut null", () => {
  const P = require("../../static/lib/projet.js");
  assert.deepEqual(P.POSITIONS.map((p) => [p.valeur, p.libelle]),
                   [["ecriture", "ouverte"], ["lecture", "en lecture"], [null, "protégée"]]);
  for (const p of P.POSITIONS) assert.ok(p.phrase.length > 20, p.libelle);
  assert.equal(P.position("lecture").libelle, "en lecture");
  assert.equal(P.position(null).libelle, "protégée");
  assert.equal(P.position(undefined).libelle, "protégée");
});

test("la phrase dite avant d'appliquer : resserrer n'efface rien, ouvrir compte les entrées", () => {
  const P = require("../../static/lib/projet.js");
  assert.equal(P.phraseChangement("lecture", "lecture", 3, "Base"), "");
  const resserre = P.phraseChangement("ecriture", null, 3, "Base");
  assert.ok(resserre.startsWith("Resserrer n'efface aucun travail"), resserre);
  assert.ok(resserre.includes("ne la verront plus"), resserre);
  assert.ok(P.phraseChangement("ecriture", "lecture", 3, "Base").includes("sans plus y écrire"));
  const ouvre = P.phraseChangement(null, "ecriture", 3, "Base");
  assert.ok(ouvre.includes("3 entrées du projet") && ouvre.includes("d'annoter"), ouvre);
  assert.ok(P.phraseChangement(null, "lecture", 1, "Base").includes("1 entrée du projet le droit de lire"));
  assert.ok(P.phraseChangement(null, "lecture", 0, "Base").includes("aucune entrée"));
});

test("+ Faire entrer dit ce que la base ouvre à l'arrivant, selon sa position (D10)", () => {
  // « Aucune collection ne lui est ouverte » était faux depuis la collection de base : le
  // membre y entre au niveau que le projet a choisi, et n'entre nulle part ailleurs.
  const P = require("../../static/lib/projet.js");
  assert.equal(P.phraseEntree({ nom: "Base S", acces_membres: "ecriture" }),
    "Il entre dans la collection de base « Base S », pour y annoter ; aucune autre "
    + "collection ne lui est ouverte pour autant.");
  assert.equal(P.phraseEntree({ nom: "Base S", acces_membres: "lecture" }),
    "Il entre dans la collection de base « Base S », en lecture ; aucune autre collection "
    + "ne lui est ouverte pour autant.");
  for (const protegee of [null, undefined]) {
    assert.equal(P.phraseEntree({ nom: "Base S", acces_membres: protegee }),
      "La collection de base « Base S » est protégée : aucune collection ne lui est ouverte "
      + "pour autant.");
  }
  // Un projet sans base : rien ne s'ouvre, et c'est alors vrai.
  assert.equal(P.phraseEntree(null), "Aucune collection ne lui est ouverte pour autant.");
  // Sans rien savoir de la base, la phrase dit la règle — jamais « aucune collection ».
  const regle = P.phraseEntree();
  assert.ok(regle.startsWith("Sa collection de base lui est ouverte selon ce que le projet"), regle);
});
