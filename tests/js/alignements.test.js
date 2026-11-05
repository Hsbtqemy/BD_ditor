/* Tests unitaires de l'alignement d'autorité d'un personnage (static/lib/alignements.js),
   COMMUN à l'Atelier (le panneau Personnage) et à la page Annotation (la fiche d'un
   personnage, ANN-7). Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous
   pytest). Le module est sorti de `viewer.js` tel quel : ces tables jouent ses règles sur un
   document de papier ; les pages se jouent dans un navigateur (test_e2e_a11y.py pour
   l'Atelier, test_e2e_annotation_page.py pour la page Annotation). */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

const A = require("../../static/lib/alignements.js");

/* Un document de papier : ce que le widget touche, rien de plus. */
function papier() {
  const ecouteurs = {};
  const el = (extra = {}) => ({ hidden: false, ...extra });
  const puce = () => {
    const e = { className: "", x: null, _html: "",
                set innerHTML(v) { this._html = v; this.x = v.includes('class="x"') ? { onclick: null } : null; },
                get innerHTML() { return this._html; },
                querySelector(sel) { return sel === ".x" ? this.x : null; } };
    return e;
  };
  const doc = { createElement: () => puce() };
  const current = { enfants: [], _html: "",
                    set innerHTML(v) { this._html = v; if (v === "" || !v.startsWith("<span class=\"tag-chip")) this.enfants = []; },
                    get innerHTML() { return this._html; },
                    appendChild(e) { this.enfants.push(e); } };
  const input = el({ value: "",
                     addEventListener(type, fn) { (ecouteurs[type] = ecouteurs[type] || []).push(fn); },
                     emettre(type, ev = {}) { for (const fn of ecouteurs[type] || []) fn({ preventDefault() {}, ...ev }); } });
  return { doc, section: el({ hidden: true }), current, input, saisie: el() };
}

const attendre = () => new Promise((r) => setTimeout(r, 0));

/* Le serveur : des alignements par personnage, éventuellement retenus. */
function serveur(par) {
  const envois = [], messages = [], retenues = [];
  return {
    envois, messages, retenues,
    apiGet: (url) => {
      const pid = Number(url.match(/personnages\/(\d+)\//)[1]);
      const rep = (par[pid] || []).slice();
      if (par.retenir && par.retenir.includes(pid)) {
        return new Promise((res) => retenues.push(() => res(rep)));
      }
      return Promise.resolve(rep);
    },
    apiSend: async (methode, url, corps) => {
      envois.push([methode, url, corps]);
      if (par.refus) throw new Error(par.refus);
      return {};
    },
    toast: (m) => messages.push(m),
    escapeHtml: (t) => String(t).replace(/</g, "&lt;"),
  };
}

function monter(par, env = {}) {
  const p = papier();
  const s = serveur(par);
  const w = A.monter({ section: p.section, current: p.current, input: p.input, saisie: p.saisie },
                     { ...s, document: p.doc, ...env });
  return { ...p, s, w };
}

const WIKI = { id: 5, source: "wikidata", uri: "https://www.wikidata.org/wiki/Q1" };

test("se charge sans document", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(typeof A.monter, "function");
});

test("charger un personnage montre la section et ses puces, chacune avec son ✕", async () => {
  const m = monter({ 7: [WIKI, { id: 6, source: null, uri: "https://exemple.org/x" }] });
  m.w.load(7);
  assert.equal(m.section.hidden, false);
  assert.equal(m.saisie.hidden, false);                  // sans `ecrit` : on écrit, comme l'Atelier
  await attendre();
  assert.equal(m.current.enfants.length, 2);
  assert.match(m.current.enfants[0].innerHTML, /wikidata ↗/);
  assert.match(m.current.enfants[1].innerHTML, /lien ↗/);   // source inconnue : « lien »
  assert.ok(m.current.enfants[0].x, "le ✕ manque");
  m.current.enfants[0].x.onclick();
  await attendre();
  assert.deepEqual(m.s.envois[0], ["DELETE", "/api/personnages/7/alignements/5", undefined]);
});

test("sans alignement : « Aucun » ; sans personnage : la section se cache", async () => {
  const m = monter({ 7: [] });
  m.w.load(7);
  await attendre();
  assert.match(m.current.innerHTML, /Aucun/);
  m.w.load(null);
  assert.equal(m.section.hidden, true);
});

test("Entrée ajoute l'URI tapée, vide le champ et relit ; un refus se dit", async () => {
  const m = monter({ 7: [] });
  m.w.load(7);
  m.input.value = "  https://viaf.org/viaf/1  ";
  m.input.emettre("keydown", { key: "Enter" });
  await attendre(); await attendre();
  assert.deepEqual(m.s.envois[0], ["POST", "/api/personnages/7/alignements",
                                   { uri: "https://viaf.org/viaf/1" }]);
  assert.equal(m.input.value, "");
  // Champ vide : rien ne part.
  m.input.emettre("keydown", { key: "Enter" });
  await attendre();
  assert.equal(m.s.envois.length, 1);
  const r = monter({ 7: [], refus: "L'alignement doit être une URI http(s)." });
  r.w.load(7);
  r.input.value = "wikidata";
  r.input.emettre("keydown", { key: "Enter" });
  await attendre();
  assert.deepEqual(r.s.messages, ["Alignement : L'alignement doit être une URI http(s)."]);
  assert.equal(r.input.value, "wikidata");             // la saisie reste
});

test("`ecrit` faux : ni champ ni ✕, la liste se lit", async () => {
  const m = monter({ 7: [WIKI] }, { ecrit: () => false });
  m.w.load(7);
  assert.equal(m.saisie.hidden, true);
  await attendre();
  assert.equal(m.current.enfants.length, 1);
  assert.equal(m.current.enfants[0].x, null);
  assert.doesNotMatch(m.current.enfants[0].innerHTML, /Retirer/);
  // Le même widget, rechargé où l'on écrit, rend le champ.
  const ouvert = { v: false };
  const n = monter({ 7: [WIKI] }, { ecrit: () => ouvert.v });
  n.w.load(7);
  assert.equal(n.saisie.hidden, true);
  ouvert.v = true;
  n.w.load(7);
  assert.equal(n.saisie.hidden, false);
});

test("une lecture revenue après une plus récente n'écrit rien : la liste d'un autre ne s'affiche pas", async () => {
  const m = monter({ 7: [WIKI], 8: [], retenir: [7] });
  m.w.load(7);                                         // retenue
  m.w.load(8);                                         // revient tout de suite : « Aucun »
  await attendre();
  assert.match(m.current.innerHTML, /Aucun/);
  m.s.retenues[0]();                                   // celle de 7 revient après
  await attendre();
  assert.equal(m.current.enfants.length, 0);
  assert.match(m.current.innerHTML, /Aucun/);
});

test("une URI est échappée dans la puce", async () => {
  const m = monter({ 7: [{ id: 1, source: "<b>", uri: "https://x.org/<i>" }] });
  m.w.load(7);
  await attendre();
  assert.doesNotMatch(m.current.enfants[0].innerHTML, /<b>|<i>/);
});
