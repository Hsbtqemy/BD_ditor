/* Tests unitaires du filtre de collection de l'Atelier (static/lib/atelier.js, UX-19).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Ce fichier garde la RÈGLE — le défaut sur la base, ce qui est retenu projet par projet,
   l'adresse qui l'emporte, l'album d'un lien qui fait changer de collection. Que l'Atelier
   s'en serve se joue dans un navigateur (tests/test_e2e_atelier_collection.py). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

test("le module se charge sans document, sans fenêtre, sans adresse et sans stockage", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(typeof window, "undefined");
  assert.equal(typeof location, "undefined");
  assert.equal(typeof localStorage, "undefined");
  const chemin = require.resolve("../../static/lib/atelier.js");
  delete require.cache[chemin];
  const api = require(chemin);
  assert.equal(typeof api.resoudre, "function");
  assert.equal(api.CLE, "bd-atelier-collection");
});

const { CLE, TOUTES, LIBELLE_TOUTES, lire, retenir, parDefaut, valide, filtrer, resoudre,
        albumAOuvrir, collectionDeLAdresse, libelleVide } = require("../../static/lib/atelier.js");

// Les collections d'un projet, DANS L'ORDRE de la liste : la base en tête, puis A → Z.
const BASE = { id: 9, nom: "Base du projet", base: true };
const ETUDE_A = { id: 3, nom: "Étude A", base: false };
const ETUDE_B = { id: 5, nom: "Étude B", base: false };
const COLS = [BASE, ETUDE_A, ETUDE_B];

const sur = (...cols) => cols.map((c) => ({ id: c.id, nom: c.nom }));
const DE_LA_BASE = { id: 11, titre: "De la base", collections: sur(BASE) };
const DE_A = { id: 12, titre: "De A", collections: sur(ETUDE_A) };
const DE_A_ET_B = { id: 13, titre: "De A et de B", collections: sur(ETUDE_A, ETUDE_B) };
const DE_B = { id: 14, titre: "De B", collections: sur(ETUDE_B) };
const ALBUMS = [DE_LA_BASE, DE_A, DE_A_ET_B, DE_B];
const titres = (l) => l.map((a) => a.titre);

/* Un stockage en mémoire, qui peut aussi refuser. */
function memoire(initial, refuse) {
  const m = new Map(initial ? Object.entries(initial) : []);
  return {
    getItem(k) { if (refuse) throw new Error("refusé"); return m.has(k) ? m.get(k) : null; },
    setItem(k, v) { if (refuse) throw new Error("refusé"); m.set(k, String(v)); },
    brut: m,
  };
}

test("rien de choisi : la base qui contient un album lu, même hors de la tête de la liste", () => {
  assert.equal(parDefaut(COLS, ALBUMS), 9);
  assert.equal(parDefaut([ETUDE_A, BASE], ALBUMS), 9);
  assert.equal(parDefaut(COLS, [DE_LA_BASE]), 9);
});

test("la base lue mais VIDE de tout album lu : toutes les collections du projet", () => {
  const sansLaBase = ALBUMS.filter((a) => a !== DE_LA_BASE);
  assert.equal(parDefaut(COLS, sansLaBase), TOUTES);
  assert.equal(parDefaut(COLS, []), TOUTES);
  assert.equal(parDefaut(COLS), TOUTES);   // aucun album donné : rien n'est su de la base
});

test("la base qu'on ne lit pas : la première collection qu'on lit, dans l'ordre de la liste", () => {
  assert.equal(parDefaut([ETUDE_A, ETUDE_B], ALBUMS), 3);
  assert.equal(parDefaut([ETUDE_B, ETUDE_A], ALBUMS), 5);
  assert.equal(parDefaut([ETUDE_A, ETUDE_B], []), 3);   // inchangé, même sans album
});

test("aucune collection lue (liste illisible) : toutes, rien n'est caché", () => {
  assert.equal(parDefaut([], ALBUMS), TOUTES);
  assert.equal(parDefaut(null), TOUTES);
});

test("filtrer : les albums rangés dans la collection, un album de deux collections dans chacune", () => {
  assert.deepEqual(titres(filtrer(ALBUMS, 9)), ["De la base"]);
  assert.deepEqual(titres(filtrer(ALBUMS, 3)), ["De A", "De A et de B"]);
  assert.deepEqual(titres(filtrer(ALBUMS, 5)), ["De A et de B", "De B"]);
});

test("filtrer sous « Toutes les collections du projet » : la liste d'avant, entière", () => {
  assert.deepEqual(filtrer(ALBUMS, TOUTES), ALBUMS);
  assert.equal(LIBELLE_TOUTES, "Toutes les collections du projet");
});

test("filtrer une collection où l'on ne lit aucun album : vide, et la liste vide le dit", () => {
  assert.deepEqual(filtrer(ALBUMS, 77), []);
  assert.deepEqual(filtrer([{ id: 1, titre: "sans clé" }], 3), []);   // `collections` absent
  assert.equal(libelleVide(3), "— aucun album dans cette collection —");
  assert.equal(libelleVide(TOUTES), "— aucun album —");
});

test("valide : un choix ne vaut que parmi les collections proposées ; « toutes » vaut toujours", () => {
  assert.equal(valide(5, COLS), 5);
  assert.equal(valide("5", COLS), 5);
  assert.equal(valide(77, COLS), null);
  assert.equal(valide(TOUTES, []), TOUTES);
  for (const v of [null, undefined, "", "0", "-3", "abc", 2.5]) assert.equal(valide(v, COLS), null);
});

/* La résolution, par table : [cas, entrées, choix attendu, raison attendue]. */
const CAS = [
  ["rien : la base", {}, 9, "defaut"],
  ["un choix retenu", { retenu: 5 }, 5, "retenu"],
  ["« toutes » retenu", { retenu: TOUTES }, TOUTES, "retenu"],
  ["un choix retenu qui n'est plus lu : la base", { retenu: 77 }, 9, "defaut"],
  ["l'adresse l'emporte sur le retenu", { adresse: 5, retenu: 3 }, 5, "adresse"],
  ["une adresse qu'on ne lit pas ne compte pas", { adresse: 77, retenu: 3 }, 3, "retenu"],
  ["l'album du lien est dans la collection retenue : elle reste", { retenu: 5, albumVise: 13 }, 5,
   "retenu"],
  ["l'album du lien n'y est pas : la première collection qui le contient",
   { retenu: 9, albumVise: 13 }, 3, "album"],
  ["l'album du lien, hors de la base par défaut", { albumVise: 14 }, 5, "album"],
  ["l'adresse pose B, l'album du lien y est : B, même s'il vit aussi dans A",
   { adresse: 5, albumVise: 13 }, 5, "adresse"],
  ["l'adresse pose la base, l'album du lien n'y est pas : on change quand même",
   { adresse: 9, albumVise: 12 }, 3, "album"],
  ["sous « toutes », l'album du lien y est toujours", { retenu: TOUTES, albumVise: 14 }, TOUTES,
   "retenu"],
  ["un album du lien qui n'est pas du projet ne change rien", { retenu: 5, albumVise: 99 }, 5,
   "retenu"],
];
for (const [nom, entrees, choix, raison] of CAS) {
  test(`résoudre — ${nom}`, () => {
    assert.deepEqual(resoudre({ collections: COLS, albums: ALBUMS, ...entrees }),
                     { choix, raison });
  });
}

test("résoudre — un album du projet qu'aucune collection proposée ne contient : toutes", () => {
  const orphelin = { id: 20, titre: "Rangé ailleurs", collections: sur({ id: 40, nom: "X" }) };
  assert.deepEqual(resoudre({ collections: COLS, albums: [...ALBUMS, orphelin], albumVise: 20 }),
                   { choix: TOUTES, raison: "album" });
});

test("résoudre — la base vide : toutes ; l'album d'un lien n'y change rien", () => {
  const sansLaBase = ALBUMS.filter((a) => a !== DE_LA_BASE);
  assert.deepEqual(resoudre({ collections: COLS, albums: sansLaBase }),
                   { choix: TOUTES, raison: "defaut" });
  assert.deepEqual(resoudre({ collections: COLS, albums: sansLaBase, albumVise: 14 }),
                   { choix: TOUTES, raison: "defaut" });
  // Un choix retenu l'emporte toujours sur le défaut.
  assert.deepEqual(resoudre({ collections: COLS, albums: sansLaBase, retenu: 9 }),
                   { choix: 9, raison: "retenu" });
});

test("résoudre — la base qu'on ne lit pas : la première collection lue", () => {
  assert.deepEqual(resoudre({ collections: [ETUDE_A, ETUDE_B], albums: ALBUMS }),
                   { choix: 3, raison: "defaut" });
});

test("l'album à ouvrir : le voulu s'il est dans la liste, sinon l'ouvert, sinon le premier", () => {
  const l = filtrer(ALBUMS, 3);
  assert.equal(albumAOuvrir(l, 13, 12), 13);
  assert.equal(albumAOuvrir(l, 14, 13), 13);   // le voulu n'y est pas : l'ouvert
  assert.equal(albumAOuvrir(l, null, 14), 12); // ni l'un ni l'autre : le premier
  assert.equal(albumAOuvrir([], 12, 12), null);
});

test("l'adresse : `collection=` lu comme un identifiant, rien sinon", () => {
  assert.equal(collectionDeLAdresse("?album=3&planche=4&collection=5"), 5);
  assert.equal(collectionDeLAdresse("?album=3"), null);
  assert.equal(collectionDeLAdresse("?collection=abc"), null);
  assert.equal(collectionDeLAdresse("?collection=0"), null);
  assert.equal(collectionDeLAdresse(""), null);
  assert.equal(collectionDeLAdresse(undefined), null);
});

test("retenu projet par projet : choisir dans l'un ne touche pas l'autre", () => {
  const s = memoire();
  assert.equal(lire(1, s), null);
  assert.equal(retenir(1, 5, s), true);
  assert.equal(retenir(4, TOUTES, s), true);
  assert.equal(lire(1, s), 5);
  assert.equal(lire(4, s), TOUTES);
  assert.equal(lire(7, s), null);
  assert.deepEqual(JSON.parse(s.brut.get(CLE)), { 1: 5, 4: TOUTES });
});

test("sans projet courant, le choix se range à part", () => {
  const s = memoire();
  retenir(null, 3, s);
  assert.equal(lire(null, s), 3);
  assert.equal(lire(1, s), null);
});

test("un choix illisible n'est ni retenu ni lu", () => {
  const s = memoire();
  assert.equal(retenir(1, "n'importe quoi", s), false);
  assert.equal(s.brut.has(CLE), false);
  for (const brut of ["pas du json", "[1,2]", '"5"', '{"1": "abc"}', '{"1": -2}']) {
    assert.equal(lire(1, memoire({ [CLE]: brut })), null, brut);
  }
});

test("le stockage qui manque ou refuse : rien ne lève, rien n'est retenu", () => {
  assert.equal(lire(1, null), null);
  assert.equal(retenir(1, 5, null), false);
  const refuse = memoire(null, true);
  assert.equal(lire(1, refuse), null);
  assert.equal(retenir(1, 5, refuse), false);
});

test("sans `localStorage` du tout (Node), lire et retenir ne lèvent pas", () => {
  assert.equal(lire(1), null);
  assert.equal(retenir(1, 5), false);
});
