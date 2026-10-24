/* Tests unitaires de `static/lib/bac-a-sable.js` (COL-4) — ce que l'écran du bac à sable
   DÉCIDE : qui se voit offrir quoi, la date en heure de Paris, le plafond, ce qui part et ce
   qui revient, ce qu'on dit d'un bac à sable effacé. Lancés par `node --test tests/js` (et
   via tests/test_js_unit.py sous pytest).

   Les gestes se jouent dans un navigateur (`tests/test_e2e_bac_a_sable.py`), sous les
   identités qui les voient. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

test("le module se charge sans document, sans fenêtre, sans stockage", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(typeof window, "undefined");
  assert.equal(typeof localStorage, "undefined");
  const chemin = require.resolve("../../static/lib/bac-a-sable.js");
  delete require.cache[chemin];
  assert.equal(typeof require(chemin).ligne, "function");
});

const B = require("../../static/lib/bac-a-sable.js");

const MIEN = { id: 7, nom: "Mon bac à sable", gerable: true, nb_membres: 2,
               bac_a_sable: { mien: true, efface_le: "2026-10-26 03:00:00" } };
const INVITE = { id: 9, nom: "Bac · hsemil01", gerable: false,
                 bac_a_sable: { mien: false, efface_le: "2026-10-26 03:00:00",
                                proprietaire: "hsemil01" } };
const ORDINAIRE = { id: 1, nom: "Corpus test", gerable: false, repli: true };
const VUE = { id: 7, efface_le: "2026-10-26 03:00:00", planches_importees: 12,
              plafond_planches: 50,
              jeu: [{ role: "exemple", album_id: 30, planche_ids: [300] },
                    { role: "pas-a-pas", album_id: 31, planche_ids: [310, 311] },
                    { role: "stock", album_id: 32, planche_ids: [] }] };

/* ── Les dates, en heure de Paris ─────────────────────────────────────────────────────── */

test("la date d'effacement se dit en heure de Paris : ce lundi-ci est le 26", () => {
  // Relevé sur le code livré : `efface_le` = 2026-10-26 03:00:00 UTC, et le passage à
  // l'heure d'hiver tombe le 25. Le cadrage écrivait « 27 octobre » en exemple.
  assert.equal(B.jourEtHeure("2026-10-26 03:00:00"), "lundi 26 octobre à 4 h");
  // L'heure d'été : 2 h UTC est 4 h à Paris.
  assert.equal(B.jourEtHeure("2026-03-30 02:00:00"), "lundi 30 mars à 4 h");
  assert.equal(B.jourEtHeure("2026-07-06 02:00:00"), "lundi 6 juillet à 4 h");
  // Une minute se dit.
  assert.equal(B.jourEtHeure("2026-10-24 12:30:00"), "samedi 24 octobre à 14 h 30");
});

test("une date illisible ne s'écrit pas", () => {
  for (const v of [null, undefined, "", "demain", "2026-13-45 03:00:00", "2026-02-30 03:00:00",
                   "2026-10-26 25:00:00"]) {
    assert.equal(B.jourEtHeure(v), null, String(v));
  }
  assert.equal(B.jourCourt(null), null);
  assert.equal(B.jjmm(""), null);
});

test("les formes courtes : l'en-tête de la liste de l'Administration, « ouvert le »", () => {
  assert.equal(B.jourCourt("2026-10-26 03:00:00"), "lun. 26 oct., 4 h");
  assert.equal(B.jjmm("2026-10-24 22:30:00"), "25/10", "minuit passé à Paris");
  assert.equal(B.jjmm("2026-10-24 12:00:00"), "24/10");
});

/* ── Qui se voit offrir « Mon bac à sable » ───────────────────────────────────────────── */

test("offert à qui le serveur l'ouvrirait, tant qu'il n'en a pas", () => {
  const ouvrable = { bac_a_sable_ouvrable: true };
  assert.equal(B.offrir(ouvrable, []), true, "l'arrivant sans projet");
  assert.equal(B.offrir(ouvrable, [ORDINAIRE]), true, "qui a déjà un projet");
  assert.equal(B.offrir(ouvrable, [ORDINAIRE, INVITE]), true, "l'invité chez un autre");
  assert.equal(B.offrir(ouvrable, [ORDINAIRE, MIEN]), false, "il l'a : dans le sélecteur");
  assert.equal(B.offrir({ bac_a_sable_ouvrable: false }, []), false,
               "mono-poste, compte partagé, sans identité");
  assert.equal(B.offrir(null, []), false, "/api/moi illisible");
  assert.equal(B.offrir({}, []), false, "un serveur d'avant");
});

test("la page vide ne l'offre qu'à qui n'a aucun projet", () => {
  const ouvrable = { bac_a_sable_ouvrable: true };
  assert.equal(B.offrirPageVide(ouvrable, []), true);
  assert.equal(B.offrirPageVide(ouvrable, [ORDINAIRE]), false);
  assert.equal(B.offrirPageVide(ouvrable, [INVITE]), false);
  assert.equal(B.offrirPageVide({ bac_a_sable_ouvrable: false }, []), false);
});

test("le bandeau de portée vide se masque dans un bac à sable, et seulement là", () => {
  assert.equal(B.estBac(MIEN), true);
  assert.equal(B.estBac(INVITE), true);
  assert.equal(B.estBac(ORDINAIRE), false);
  assert.equal(B.estBac(null), false);
});

/* ── La ligne ────────────────────────────────────────────────────────────────────────── */

test("la ligne du propriétaire : nom, date, plafond, Inviter et Remettre à neuf", () => {
  const l = B.ligne(MIEN, VUE);
  assert.equal(l.nom, "Bac à sable");
  assert.equal(l.date, "s'efface lundi 26 octobre à 4 h");
  assert.deepEqual(l.gestes, ["inviter", "remettre"]);
  assert.equal(l.invites, 2);
  assert.equal(l.plafond.texte, "12 / 50 planches importées");
  assert.equal(l.plafond.plein, false);
  assert.match(l.aide, /chaque lundi à 4 h/);
});

test("la ligne de l'invité : le login entier, Quitter seul, aucun compte", () => {
  const l = B.ligne(INVITE, null);
  assert.equal(l.nom, "Bac à sable de hsemil01");
  assert.deepEqual(l.gestes, ["quitter"]);
  assert.equal(l.plafond, null);
  assert.equal(l.invites, null);
  assert.match(l.aide, /hsemil01/);
  // Une vue d'un AUTRE bac à sable (le sien) ne donne pas son compte à celui-ci.
  assert.equal(B.ligne(INVITE, VUE).plafond, null);
});

test("hors d'un bac à sable, pas de ligne", () => {
  assert.equal(B.ligne(ORDINAIRE, VUE), null);
  assert.equal(B.ligne(null, VUE), null);
});

test("« Inviter… (n) » porte le nombre d'invités", () => {
  assert.equal(B.libelleInviter(0), "Inviter…");
  assert.equal(B.libelleInviter(1), "Inviter… (1)");
  assert.equal(B.libelleInviter(3), "Inviter… (3)");
});

/* ── Le plafond ──────────────────────────────────────────────────────────────────────── */

test("le plafond : plein à 50 sur 50, et au-delà", () => {
  assert.equal(B.plafond({ planches_importees: 49, plafond_planches: 50 }).plein, false);
  assert.equal(B.plafond({ planches_importees: 50, plafond_planches: 50 }).plein, true);
  assert.equal(B.plafond({ planches_importees: 51, plafond_planches: 50 }).plein, true);
  assert.equal(B.plafond({ planches_importees: 0, plafond_planches: 0 }).plein, false,
               "sans plafond lu, rien ne s'éteint");
});

test("l'import s'éteint dans un album de MON bac à sable au plafond, et nulle part ailleurs", () => {
  const plein = { ...VUE, planches_importees: 50 };
  assert.match(B.raisonImportEteint(plein, 7), /Plafond atteint : 50 planches importées sur 50/);
  assert.equal(B.raisonImportEteint(VUE, 7), null, "pas encore plein");
  assert.equal(B.raisonImportEteint(plein, 9), null, "le bac à sable d'un autre");
  assert.equal(B.raisonImportEteint(plein, 1), null, "un vrai projet");
  assert.equal(B.raisonImportEteint(null, 7), null, "pas de bac à sable à soi");
  assert.equal(B.raisonImportEteint(plein, null), null, "un album sans projet");
});

/* ── Remettre à neuf ─────────────────────────────────────────────────────────────────── */

test("ce qui part : le travail, les planches importées, les collections, les invités nommés", () => {
  const r = B.remiseANeuf(VUE, ["dominique", "sam"]);
  assert.deepEqual(r.part, ["votre travail ici", "12 planches importées", "vos collections",
                            "le travail de dominique et sam",
                            "les invitations de dominique et sam"]);
  assert.deepEqual(r.revient, ["les 3 albums du jeu, vierges"]);
});

test("ce qui part, sans invité ni planche importée ; le jeu d'un seul album", () => {
  const r = B.remiseANeuf({ ...VUE, planches_importees: 0, jeu: [VUE.jeu[0]] }, []);
  assert.deepEqual(r.part, ["votre travail ici", "vos collections"]);
  assert.deepEqual(r.revient, ["l'album du jeu, vierge"]);
  assert.deepEqual(B.remiseANeuf({ ...VUE, planches_importees: 1, jeu: [] }, ["lea"]).part,
                   ["votre travail ici", "1 planche importée", "vos collections",
                    "le travail de lea", "l'invitation de lea"]);
  assert.deepEqual(B.remiseANeuf({ jeu: [] }, []).revient, ["un bac à sable neuf"]);
});

test("l'énumération à la française", () => {
  assert.equal(B.enumeration(["a"]), "a");
  assert.equal(B.enumeration(["a", "b"]), "a et b");
  assert.equal(B.enumeration(["a", "b", "c"]), "a, b et c");
});

/* ── Après le clic ───────────────────────────────────────────────────────────────────── */

test("après le clic, l'Atelier sur la planche du parcours", () => {
  assert.equal(B.adresseApresOuverture(VUE), "/?album=31&planche=310");
  // Sans parcours : la première planche du jeu ; sans jeu : l'Atelier tel quel.
  assert.equal(B.adresseApresOuverture({ jeu: [VUE.jeu[2], VUE.jeu[0]] }), "/?album=30&planche=300");
  assert.equal(B.adresseApresOuverture({ jeu: [] }), "/");
  assert.equal(B.adresseApresOuverture(null), "/");
});

/* ── L'effacement du lundi ───────────────────────────────────────────────────────────── */

const APRES = new Date(Date.UTC(2026, 9, 26, 3, 0, 1));
const AVANT = new Date(Date.UTC(2026, 9, 25, 12, 0, 0));

test("un bac à sable disparu de la liste se dit, une fois", () => {
  const souvenirs = B.souvenirsDe([ORDINAIRE, MIEN, INVITE]);
  assert.deepEqual(souvenirs.map((s) => s.id), [7, 9]);
  assert.deepEqual(B.disparus(souvenirs, [ORDINAIRE, MIEN, INVITE]), []);
  assert.deepEqual(B.disparus(souvenirs, [ORDINAIRE]).map((s) => s.id), [7, 9]);
});

test("le message : effacé lundi à 4 h, le sien ou celui d'un autre", () => {
  const [mien, invite] = B.souvenirsDe([MIEN, INVITE]);
  assert.equal(B.messageDisparu(mien, APRES), "Votre bac à sable a été effacé lundi à 4 h.");
  assert.equal(B.messageDisparu(invite, APRES),
               "Le bac à sable de hsemil01 a été effacé lundi à 4 h.");
});

test("avant sa date, un bac à sable disparu a été remis à neuf, ou effacé hors du lundi", () => {
  const [mien, invite] = B.souvenirsDe([MIEN, INVITE]);
  // Le sien : remis à neuf dans un autre onglet — le neuf est déjà dans la liste.
  const neuf = { ...MIEN, id: 8 };
  assert.equal(B.messageDisparu(mien, AVANT, [ORDINAIRE, neuf]), null);
  // Effacé hors du lundi (l'outil de l'exploitant) : dit, sans date.
  assert.equal(B.messageDisparu(mien, AVANT, [ORDINAIRE]), "Votre bac à sable a été effacé.");
  assert.equal(B.messageDisparu(mien, AVANT), "Votre bac à sable a été effacé.");
  // Chez un autre : il l'a quitté ailleurs, ou on l'en a retiré.
  assert.equal(B.messageDisparu(invite, AVANT), "Vous n'êtes plus dans le bac à sable de hsemil01.");
});

test("les souvenirs : lus et écrits sous try/catch, jamais une exception", () => {
  const leve = { getItem() { throw new Error("refusé"); }, setItem() { throw new Error("refusé"); } };
  assert.deepEqual(B.lireSouvenirs(leve), []);
  assert.equal(B.retenirSouvenirs([{ id: 1 }], leve), false);
  assert.deepEqual(B.lireSouvenirs(null), []);
  const m = new Map();
  const ok = { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v) };
  assert.equal(B.retenirSouvenirs(B.souvenirsDe([MIEN]), ok), true);
  assert.deepEqual(B.lireSouvenirs(ok).map((s) => s.id), [7]);
  ok.setItem(B.CLE_SOUVENIRS, "{pas du json");
  assert.deepEqual(B.lireSouvenirs(ok), []);
  ok.setItem(B.CLE_SOUVENIRS, JSON.stringify([{ id: "x" }, null, { id: 3 }]));
  assert.deepEqual(B.lireSouvenirs(ok).map((s) => s.id), [3]);
});

/* ── L'Administration ────────────────────────────────────────────────────────────────── */

const BACS = [
  { id: 1, date_creation: "2026-10-20 08:00:00", bac_a_sable: { proprietaire: "zoe", efface_le: "2026-10-26 03:00:00" } },
  { id: 2, date_creation: "2026-10-23 08:00:00", bac_a_sable: { proprietaire: "Alice", efface_le: "2026-10-26 03:00:00" } },
  { id: 3, date_creation: "2026-10-21 08:00:00", bac_a_sable: { proprietaire: "bruno", efface_le: "2026-10-26 03:00:00" } },
];

test("la liste des bacs à sable : par login, A → Z ou récents d'abord, filtrée par login", () => {
  assert.deepEqual(B.trierBacs(BACS, "alpha").map((p) => p.id), [2, 3, 1]);
  assert.deepEqual(B.trierBacs(BACS, "recents").map((p) => p.id), [2, 3, 1]);
  // Ouverts dans la même seconde : le dernier né d'abord.
  const memes = BACS.map((p) => ({ ...p, date_creation: "2026-10-24 10:00:00" }));
  assert.deepEqual(B.trierBacs(memes, "recents").map((p) => p.id), [3, 2, 1]);
  assert.deepEqual(B.trierBacs([BACS[0], BACS[2]], "recents").map((p) => p.id), [3, 1]);
  assert.deepEqual(B.trierBacs(BACS, "alpha", "BRU").map((p) => p.id), [3]);
  assert.deepEqual(B.trierBacs(BACS, "alpha", "personne"), []);
  assert.deepEqual(B.trierBacs([ORDINAIRE, ...BACS], "alpha").length, 3, "un projet n'y entre pas");
});

test("la date d'effacement UNE fois en tête de la liste", () => {
  assert.equal(B.enteteBacs(BACS), "tous s'effacent lun. 26 oct., 4 h");
  assert.equal(B.enteteBacs([]), "");
});

test("la phrase de la fiche : on n'entre pas dans le bac d'un autre", () => {
  assert.equal(B.phraseFicheBac(INVITE),
               "Vous n'y entrez pas. Pour aider hsemil01, faites-vous inviter.");
  assert.match(B.phraseFicheBac(MIEN), /C'est le vôtre/);
  assert.equal(B.phraseFicheBac(ORDINAIRE), "");
});
