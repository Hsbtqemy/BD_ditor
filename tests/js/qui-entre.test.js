/* Tests unitaires du module « Qui entre » (static/lib/qui-entre.js, UX-16).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Ce fichier ne joue AUCUN geste : les gestes se jouent dans un navigateur
   (tests/test_e2e_qui_entre.py), et la logique des droits a ses 42 cas dans
   droits.test.js. Il garde ce qui fait du panneau un MODULE, et que rien d'autre ne
   verrait : qu'il se charge sans document, et que deux montages ne se partagent jamais un
   identifiant — une condition qui tenait par chance tant que le panneau n'était monté
   qu'à un endroit. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

test("le module se charge sans document, sans fenêtre et sans adresse", () => {
  // Le `require` en tête de fichier le prouverait aussi, mais sans le DIRE : ici, les trois
  // globales sont vérifiées absentes AVANT, sans quoi un Node qui les fournirait un jour
  // rendrait ce test vert sur un module qui lit le document au chargement.
  assert.equal(typeof document, "undefined");
  assert.equal(typeof window, "undefined");
  assert.equal(typeof location, "undefined");
  const chemin = require.resolve("../../static/lib/qui-entre.js");
  delete require.cache[chemin];
  const api = require(chemin);
  assert.equal(typeof api.monter, "function");
  assert.equal(typeof api.noteAdmin, "function");
});

const { noteAdmin, SEUIL_ETROIT, _suffixes } = require("../../static/lib/qui-entre.js");

test("la note des administrateurs nomme les groupes reçus, et se tait sans eux", () => {
  // Mono-poste : aucun groupe n'est lu, donc rien à déclarer (AUTH-4).
  assert.equal(noteAdmin([]), "");
  assert.equal(noteAdmin(null), "");
  assert.equal(noteAdmin(undefined), "");
  const note = noteAdmin(["bd-admins", "direction"]);
  assert.match(note, /bd-admins, direction/);
  assert.match(note, /sans\s+figurer dans aucune liste d'accès/);
});

test("un nom de groupe ne s'injecte pas dans la note", () => {
  const note = noteAdmin(['<img src=x onerror="alert(1)">']);
  assert.ok(!note.includes("<img"), note);
  assert.match(note, /&lt;img/);
});

test("le seuil étroit n'est écrit qu'à un endroit", () => {
  // Le module bascule du tableau aux cartes par le RENDU, à 48em moins un seizième. Si la
  // feuille se mettait à porter le même seuil, il y aurait deux endroits à tenir d'accord —
  // et rien ne les y tiendrait. Qui en ajoute un le lit ici, et choisit.
  const css = require("node:fs").readFileSync(
    require("node:path").join(__dirname, "../../static/style.css"), "utf8");
  assert.equal(SEUIL_ETROIT, "(max-width: 47.9375em)");
  assert.ok(!css.includes("47.9375em"), "la feuille porte désormais ce seuil elle aussi");
});

/* Un registre de suffixes neuf par test serait plus propre ; il est unique par page, comme
   dans le navigateur. Chaque test prend donc un id de collection qui n'appartient qu'à lui. */
function banc() {
  const vivants = new Set();
  return {
    naitre: () => { const m = {}; vivants.add(m); return m; },
    mourir: (m) => vivants.delete(m),
    prendre: (id, m) => _suffixes.prendre(id, m, (x) => vivants.has(x)),
  };
}

test("le premier montage d'une collection garde le suffixe nu", () => {
  // C'est ce qui fait de l'extraction un déménagement sans effet : `qe-titre-12` reste
  // `qe-titre-12` tant que la collection n'est montée qu'une fois.
  const b = banc();
  assert.equal(b.prendre(101, b.naitre()), "101");
});

test("deux montages VIVANTS de la même collection n'ont pas le même suffixe", () => {
  const b = banc();
  const s1 = b.prendre(102, b.naitre());
  const s2 = b.prendre(102, b.naitre());
  const s3 = b.prendre(102, b.naitre());
  assert.equal(new Set([s1, s2, s3]).size, 3, [s1, s2, s3].join(" "));
  assert.equal(s1, "102");
});

test("deux collections ne se disputent rien", () => {
  const b = banc();
  assert.equal(b.prendre(103, b.naitre()), "103");
  assert.equal(b.prendre(104, b.naitre()), "104");
});

test("un montage mort ne retient pas son suffixe : redessiner ne le fait pas dériver", () => {
  // L'hôte qui redessine sans démonter — la Bibliothèque l'a fait pendant des semaines, à
  // chaque collection repliée puis dépliée — ne doit pas faire passer la collection de
  // `105` à `105m2`, puis `105m3`.
  const b = banc();
  for (let i = 0; i < 4; i++) {
    const m = b.naitre();
    assert.equal(b.prendre(105, m), "105", `au tour ${i}`);
    b.mourir(m);
  }
});

test("un mort qui se démonte après coup ne retire pas le suffixe d'un vivant", () => {
  // Le suffixe d'un mort est repris par son successeur ; si le mort le « rendait » ensuite,
  // un TROISIÈME montage le reprendrait pendant que le deuxième s'en sert encore.
  const b = banc();
  const mort = b.naitre();
  assert.equal(b.prendre(106, mort), "106");
  b.mourir(mort);
  const vivant = b.naitre();
  assert.equal(b.prendre(106, vivant), "106");
  _suffixes.rendre("106", mort);                    // démontage tardif du mort
  assert.notEqual(b.prendre(106, b.naitre()), "106");
});

test("un suffixe rendu par celui qui le tient redevient libre", () => {
  const b = banc();
  const m = b.naitre();
  assert.equal(b.prendre(107, m), "107");
  _suffixes.rendre("107", m);
  assert.equal(b.prendre(107, b.naitre()), "107");
});
