/* Tests unitaires du champ « personnage » (static/lib/champ-personnage.js), COMMUN à l'Atelier
   (le locuteur, l'identité d'une boîte) et à la page Annotation (le locuteur du Contexte).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest). Le module
   est sorti de `viewer.js` tel quel (ANN-7, tranche 2, commit 8) : ces tables jouent ses
   règles sur un document de papier ; la page elle-même se joue dans un navigateur
   (test_e2e_atelier_propositions.py, test_e2e_annotation_page.py). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

const C = require("../../static/lib/champ-personnage.js");

/* Un document de papier : ce que le champ touche, rien de plus. */
function papier() {
  const doc = {
    createElement() {
      const e = { classList: { add(c) { e.classes.push(c); } }, classes: [], innerHTML: "",
                  onmousedown: null };
      return e;
    },
  };
  const ecouteurs = {};
  const champ = {
    value: "",
    addEventListener(type, fn) { (ecouteurs[type] = ecouteurs[type] || []).push(fn); },
    emettre(type, ev = {}) { for (const fn of ecouteurs[type] || []) fn({ preventDefault() {}, ...ev }); },
  };
  const liste = {
    hidden: true, enfants: [],
    set innerHTML(v) { if (v === "") this.enfants = []; },
    appendChild(e) { this.enfants.push(e); },
  };
  return { doc, champ, liste };
}

const attendre = () => new Promise((r) => setTimeout(r, 0));

/* Un registre servi par `apiGet`, compté ; `apiSend` crée. */
function serveur(registre) {
  const lectures = [], creations = [], messages = [];
  let suivant = 100;
  return {
    lectures, creations, messages,
    apiGet: async (url) => {
      const q = decodeURIComponent(url.split("?q=")[1] || "");
      lectures.push(q);
      if (registre === null) throw new Error("panne");
      return registre.filter((p) => p.nom.toLowerCase().includes(q.toLowerCase()));
    },
    apiSend: async (methode, url, corps) => {
      creations.push(corps.nom);
      const p = { id: suivant++, nom: corps.nom, serie: null };
      registre.push(p);
      return p;
    },
    toast: (m) => messages.push(m),
    escapeHtml: (t) => String(t),
  };
}

function monter(registre, zone = () => 7) {
  const p = papier();
  const s = serveur(registre);
  const choix = [];
  C.monter(p.champ, p.liste, (id, z, nom) => { choix.push({ id, z, nom }); }, zone,
           { ...s, document: p.doc });
  return { ...p, s, choix };
}

test("se charge sans document", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(typeof C.monter, "function");
});

test("Entrée sur un nom porté par UN personnage le prend, après avoir relu le registre", async () => {
  const m = monter([{ id: 1, nom: "Haddock", serie: "Tintin" }, { id: 2, nom: "Milou", serie: null }]);
  m.champ.value = "haddock";
  m.champ.emettre("keydown", { key: "Enter" });
  await attendre(); await attendre();
  assert.deepEqual(m.s.lectures, ["haddock"]);        // la liste ne valait pour rien : relue
  assert.deepEqual(m.choix, [{ id: 1, z: 7, nom: "Haddock" }]);
  assert.equal(m.champ.value, "");
  assert.deepEqual(m.s.creations, []);
});

test("deux homonymes : Entrée ne décide pas, la liste les montre avec leur série", async () => {
  const m = monter([{ id: 1, nom: "Zed", serie: "Spirou" }, { id: 2, nom: "Zed", serie: null }]);
  m.champ.value = "Zed";
  m.champ.emettre("keydown", { key: "Enter" });
  await attendre(); await attendre();
  assert.deepEqual(m.choix, []);
  assert.equal(m.champ.value, "Zed");                  // la saisie revient
  assert.equal(m.liste.hidden, false);
  assert.equal(m.liste.enfants.length, 2);
  assert.match(m.liste.enfants[0].innerHTML, /Spirou/);
  assert.match(m.liste.enfants[1].innerHTML, /sans série/);
  // Un clic en prend un.
  m.liste.enfants[1].onmousedown({ preventDefault() {} });
  await attendre();
  assert.deepEqual(m.choix, [{ id: 2, z: 7, nom: "Zed" }]);
});

test("aucun personnage de ce nom : Entrée le crée, puis l'attribue", async () => {
  const registre = [{ id: 1, nom: "Haddock", serie: null }];
  const m = monter(registre);
  const avant = C.etatDuRegistre();
  m.champ.value = "Tournesol";
  m.champ.emettre("keydown", { key: "Enter" });
  await attendre(); await attendre(); await attendre();
  assert.deepEqual(m.s.creations, ["Tournesol"]);
  assert.deepEqual(m.choix, [{ id: 100, z: 7, nom: "Tournesol" }]);
  assert.equal(C.etatDuRegistre(), avant + 1);         // l'autre champ le saura
});

test("une lecture en échec ne crée rien : la saisie revient, avec un message", async () => {
  const m = monter(null);
  m.champ.value = "Zed";
  m.champ.emettre("keydown", { key: "Enter" });
  await attendre(); await attendre();
  assert.deepEqual(m.choix, []);
  assert.deepEqual(m.s.creations, []);
  assert.equal(m.champ.value, "Zed");
  assert.match(m.s.messages[0], /Registre des personnages : panne/);
});

test("le geste vaut pour la zone où il est FAIT, même si l'on en change pendant la lecture", async () => {
  let zone = 7;
  const m = monter([{ id: 1, nom: "Haddock", serie: null }], () => zone);
  m.champ.value = "Haddock";
  m.champ.emettre("keydown", { key: "Enter" });
  zone = 8;                                            // une autre zone, avant la réponse
  await attendre(); await attendre();
  assert.deepEqual(m.choix, [{ id: 1, z: 7, nom: "Haddock" }]);
});

test("« Créer » pris dans une liste lue AVANT une création relit le registre", async () => {
  const registre = [];
  const a = monter(registre);
  const b = monter(registre);
  // Le champ B lit « Zed » : rien, donc « Créer ».
  b.champ.value = "Zed";
  b.champ.emettre("focus");
  await attendre(); await attendre();
  assert.match(b.liste.enfants[0].innerHTML, /Créer « Zed »/);
  // Le champ A crée « Zed ».
  a.champ.value = "Zed";
  a.champ.emettre("keydown", { key: "Enter" });
  await attendre(); await attendre(); await attendre();
  assert.deepEqual(a.s.creations, ["Zed"]);
  // B choisit « Créer » dans sa liste d'avant : il relit, trouve « Zed », le prend.
  b.liste.enfants[0].onmousedown({ preventDefault() {} });
  await attendre(); await attendre(); await attendre();
  assert.deepEqual(b.s.creations, []);
  assert.equal(b.choix.length, 1);
  assert.equal(b.choix[0].nom, "Zed");
});
