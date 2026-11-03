/* Tests unitaires de `static/lib/wizard.js` (UX-6) — ce que « Par où commencer » DÉCIDE :
   le souvenir et ce qui le périme, quand l'album s'ouvre seul, les parcours, où mène une
   étape, les textes de l'album. Lancés par `node --test tests/js` (et via
   tests/test_js_unit.py sous pytest).

   Les gestes se jouent dans un navigateur (`tests/test_e2e_wizard.py`) ; les marques de la
   visite sont confrontées aux gabarits par `tests/test_wizard_marques.py`. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

test("le module se charge sans document, sans fenêtre, sans stockage", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(typeof window, "undefined");
  assert.equal(typeof localStorage, "undefined");
  const chemin = require.resolve("../../static/lib/wizard.js");
  delete require.cache[chemin];
  assert.equal(typeof require(chemin).lireSouvenir, "function");
});

const W = require("../../static/lib/wizard.js");

/* Un stockage en mémoire, et un qui refuse tout. */
function memoire(depart) {
  const m = new Map(Object.entries(depart || {}));
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)),
           brut: () => m };
}
const HOSTILE = { getItem() { throw new Error("refusé"); }, setItem() { throw new Error("plein"); } };

const BAC = { id: 41, efface_le: "2026-11-09 03:00:00" };
const MIEN = { id: 41, nom: "Mon bac à sable",
               bac_a_sable: { mien: true, efface_le: "2026-11-09 03:00:00" } };
const INVITE = { id: 52, nom: "Bac · lea",
                 bac_a_sable: { mien: false, efface_le: "2026-11-09 03:00:00", proprietaire: "lea" } };
const ORDINAIRE = { id: 3, nom: "Corpus test" };
const VUE = { id: 41, efface_le: "2026-11-09 03:00:00",
              jeu: [{ role: "exemple", titre: "Un exemple", album_id: 30, planche_ids: [300] },
                    { role: "pas-a-pas", titre: "Moustache et Trottinette", album_id: 31,
                      planche_ids: [310, 311] },
                    { role: "stock", titre: "Le stock", album_id: 32, planche_ids: [] }] };

/* ── Le souvenir ──────────────────────────────────────────────────────────────────────── */

test("un souvenir retenu se relit, sous le même login et le même bac à sable", () => {
  const s = memoire();
  const souvenir = W.choisirParcours(W.neuf(), "rapide");
  assert.equal(W.retenirSouvenir("camille", BAC, W.allerA(souvenir, 2), s), true);
  assert.deepEqual(W.lireSouvenir("camille", BAC, s),
                   { album_vu: true, parcours: "rapide", etape: 2 });
  // Rangé par login : un autre compte du même navigateur n'en hérite pas.
  assert.deepEqual(W.lireSouvenir("lea", BAC, s), W.neuf());
  const brut = JSON.parse(s.brut().get(W.CLE));
  assert.deepEqual(Object.keys(brut), ["camille"]);
  assert.equal(brut.camille.bac, 41);
});

test("après un effacement, le souvenir de l'ancien bac à sable n'est plus lu", () => {
  const s = memoire();
  W.retenirSouvenir("camille", BAC, { album_vu: true, parcours: "complet", etape: 5 }, s);
  // La remise à neuf fait naître un projet NEUF : un autre identifiant, la même date.
  assert.deepEqual(W.lireSouvenir("camille", { id: 57, efface_le: BAC.efface_le }, s), W.neuf());
  // Le lundi : un autre identifiant, une autre date.
  assert.deepEqual(W.lireSouvenir("camille", { id: 63, efface_le: "2026-11-16 03:00:00" }, s),
                   W.neuf());
  // Un identifiant repris malgré tout (une base restaurée) : la date fait la différence.
  assert.deepEqual(W.lireSouvenir("camille", { id: 41, efface_le: "2026-11-16 03:00:00" }, s),
                   W.neuf());
  // Et le nouveau bac à sable REMPLACE l'ancien : un souvenir par login.
  W.retenirSouvenir("camille", { id: 57, efface_le: BAC.efface_le }, W.neuf(), s);
  assert.deepEqual(W.lireSouvenir("camille", BAC, s), W.neuf());
  assert.equal(JSON.parse(s.brut().get(W.CLE)).camille.bac, 57);
});

test("le souvenir d'un compte ne touche pas celui d'un autre", () => {
  const s = memoire();
  W.retenirSouvenir("camille", BAC, { album_vu: true, parcours: "rapide", etape: 1 }, s);
  W.retenirSouvenir("lea", { id: 70, efface_le: null }, { album_vu: true, parcours: null, etape: 0 }, s);
  assert.deepEqual(W.lireSouvenir("camille", BAC, s), { album_vu: true, parcours: "rapide", etape: 1 });
  assert.deepEqual(W.lireSouvenir("lea", { id: 70, efface_le: null }, s),
                   { album_vu: true, parcours: null, etape: 0 });
});

test("sans login, sans bac à sable ou sans stockage : rien n'est lu ni écrit", () => {
  const s = memoire();
  assert.equal(W.retenirSouvenir(null, BAC, W.neuf(), s), false);
  assert.equal(W.retenirSouvenir("camille", null, W.neuf(), s), false);
  assert.equal(W.retenirSouvenir("camille", { id: "41" }, W.neuf(), s), false);
  assert.equal(s.brut().size, 0);
  assert.equal(W.retenirSouvenir("camille", BAC, W.neuf(), null), false);
  assert.equal(W.retenirSouvenir("camille", BAC, W.neuf(), HOSTILE), false);
  assert.deepEqual(W.lireSouvenir("camille", BAC, HOSTILE), W.neuf());
  assert.deepEqual(W.lireSouvenir("camille", BAC, null), W.neuf());
  assert.deepEqual(W.lireSouvenir(null, BAC, s), W.neuf());
});

test("une mémoire illisible ou d'une autre forme vaut un départ", () => {
  for (const brut of ["{", "[]", "null", "42", '"texte"', '{"camille": 3}', '{"camille": []}']) {
    const s = memoire({ [W.CLE]: brut });
    assert.deepEqual(W.lireSouvenir("camille", BAC, s), W.neuf(), brut);
    // Et l'écriture répare : elle ne lève pas.
    assert.equal(W.retenirSouvenir("camille", BAC, W.neuf(), s), true, brut);
  }
});

test("la lecture est tolérante, champ par champ", () => {
  const ecrit = (v) => memoire({ [W.CLE]: JSON.stringify({ camille: Object.assign(
    { bac: 41, efface_le: BAC.efface_le }, v) }) });
  // Un parcours inconnu : aucun ; une étape hors bornes : la première.
  assert.deepEqual(W.lireSouvenir("camille", BAC, ecrit({ parcours: "express", etape: 3 })),
                   W.neuf());
  assert.deepEqual(W.lireSouvenir("camille", BAC, ecrit({ parcours: "rapide", etape: 4 })),
                   { album_vu: true, parcours: "rapide", etape: 0 });
  assert.deepEqual(W.lireSouvenir("camille", BAC, ecrit({ parcours: "complet", etape: 8 })),
                   { album_vu: true, parcours: "complet", etape: 8 });
  assert.deepEqual(W.lireSouvenir("camille", BAC, ecrit({ parcours: "rapide", etape: "2" })),
                   { album_vu: true, parcours: "rapide", etape: 0 });
  // « album_vu » ne se devine pas d'une valeur vraie quelconque.
  assert.deepEqual(W.lireSouvenir("camille", BAC, ecrit({ album_vu: "oui" })), W.neuf());
  // Un parcours choisi suppose l'album vu.
  assert.deepEqual(W.lireSouvenir("camille", BAC, ecrit({ album_vu: false, parcours: "rapide" })),
                   { album_vu: true, parcours: "rapide", etape: 0 });
});

/* ── Quand l'album s'ouvre seul ───────────────────────────────────────────────────────── */

test("l'album s'ouvre seul dans SON bac à sable, tant qu'il n'a pas été vu", () => {
  assert.equal(W.ouvreSeul("camille", MIEN, W.neuf()), true);
  // Un parcours choisi, ou « Ne plus afficher » : il ne s'ouvre plus seul.
  assert.equal(W.ouvreSeul("camille", MIEN, W.choisirParcours(W.neuf(), "complet")), false);
  assert.equal(W.ouvreSeul("camille", MIEN, W.neJamaisAfficher(W.neuf(), true)), false);
  // Décoché : il revient.
  assert.equal(W.ouvreSeul("camille", MIEN, W.neJamaisAfficher(W.neuf(), false)), true);
  // Ni chez un autre, ni hors d'un bac à sable, ni sans identité.
  assert.equal(W.ouvreSeul("camille", INVITE, W.neuf()), false);
  assert.equal(W.ouvreSeul("camille", ORDINAIRE, W.neuf()), false);
  assert.equal(W.ouvreSeul("camille", null, W.neuf()), false);
  assert.equal(W.ouvreSeul(null, MIEN, W.neuf()), false);
});

test("bacASoi : le sien seulement, avec sa date d'effacement", () => {
  assert.deepEqual(W.bacASoi(MIEN), { id: 41, efface_le: "2026-11-09 03:00:00" });
  assert.equal(W.bacASoi(INVITE), null);
  assert.equal(W.bacASoi(ORDINAIRE), null);
  assert.equal(W.bacASoi({ id: "41", bac_a_sable: { mien: true } }), null);
});

/* ── Les parcours ─────────────────────────────────────────────────────────────────────── */

test("neuf étapes au parcours complet, quatre gestes au parcours rapide", () => {
  assert.deepEqual(W.etapes("complet").map((e) => e.k),
                   ["corpus", "decrire", "preremplir", "tracer", "decoupage", "transcrire",
                    "annoter", "chercher", "exporter"]);
  assert.deepEqual(W.etapes("rapide").map((e) => e.k),
                   ["tracer", "decoupage", "transcrire", "annoter"]);
  assert.deepEqual(W.etapes(null), []);
  assert.deepEqual(W.etapes("express"), []);
  // « Tracer une zone » entre « Pré-remplir » et « Corriger le découpage » (2026-11-02).
  const k = W.ETAPES.map((e) => e.k);
  assert.equal(k.indexOf("tracer"), k.indexOf("preremplir") + 1);
  assert.equal(k.indexOf("decoupage"), k.indexOf("tracer") + 1);
});

test("changer de parcours garde l'étape où l'on est, si elle y figure", () => {
  const rapide = W.allerA(W.choisirParcours(W.neuf(), "rapide"), 2);       // transcrire
  const complet = W.choisirParcours(rapide, "complet");
  assert.equal(W.etapes("complet")[complet.etape].k, "transcrire");
  // « Décrire l'album » n'est pas du parcours rapide : on repart de sa première étape.
  const decrire = W.allerA(W.choisirParcours(W.neuf(), "complet"), 1);
  assert.deepEqual(W.choisirParcours(decrire, "rapide"),
                   { album_vu: true, parcours: "rapide", etape: 0 });
  // Un parcours inconnu ne change rien.
  assert.deepEqual(W.choisirParcours(rapide, "express"), rapide);
});

test("allerA refuse une étape hors du parcours", () => {
  const s = W.choisirParcours(W.neuf(), "rapide");
  assert.equal(W.allerA(s, 3).etape, 3);
  assert.equal(W.allerA(s, 4).etape, 0);
  assert.equal(W.allerA(s, -1).etape, 0);
  assert.equal(W.allerA(W.neuf(), 0).etape, 0);
});

/* ── Où mène une étape ────────────────────────────────────────────────────────────────── */

test("chaque étape mène à sa surface, à son outil et à la planche du parcours", () => {
  const ou = Object.fromEntries(W.ETAPES.map((e) => [e.k, W.adresseEtape(e, VUE)]));
  assert.deepEqual(ou, {
    corpus: "/corpus",
    decrire: "/corpus?album=31",
    preremplir: "/?album=31&planche=310",
    tracer: "/?album=31&planche=310&mode=edition",
    decoupage: "/?album=31&planche=310&mode=edition",
    transcrire: "/?album=31&planche=310&mode=transcription",
    annoter: "/annotation?album=31&planche=310",
    chercher: "/recherche",
    exporter: "/corpus?album=31",
  });
  // Sans album du parcours : la surface seule.
  assert.equal(W.adresseEtape(W.ETAPES[3], { jeu: [] }), "/");
  assert.equal(W.adresseEtape(W.ETAPES[6], null), "/annotation");
});

test("l'album du parcours : le rôle pas-à-pas, sinon la première copie qui a des planches", () => {
  assert.equal(W.albumDuParcours(VUE).album_id, 31);
  assert.equal(W.albumDuParcours({ jeu: [VUE.jeu[2], VUE.jeu[0]] }).album_id, 30);
  assert.equal(W.albumDuParcours({ jeu: [VUE.jeu[2]] }), null);
  assert.equal(W.albumDuParcours(null), null);
});

test("la phrase de « Constituer le corpus » nomme l'album du parcours", () => {
  assert.equal(W.phraseEtape(W.ETAPES[0], VUE, W.moteurs({ ocr: true })),
               "Un album rassemble des planches. Le vôtre est déjà là : ouvrez "
               + "Moustache et Trottinette.");
  assert.match(W.phraseEtape(W.ETAPES[0], null, null), /ouvrez l'album du parcours\.$/);
});

/* ── Sans moteur ──────────────────────────────────────────────────────────────────────── */

test("sans moteur, « Pré-remplir » se dit optionnel ici, et l'album le dit aussi", () => {
  const sans = W.moteurs({ kumiko: false, bulles: false, ocr: false, lemmes: true });
  const avec = W.moteurs({ kumiko: true, bulles: true, ocr: true, lemmes: true });
  const pre = W.ETAPES.find((e) => e.k === "preremplir");
  assert.equal(W.marqueEtape(pre, avec), "facultatif");
  assert.equal(W.marqueEtape(pre, sans), "optionnel ici");
  assert.equal(W.marqueEtape(W.ETAPES[0], sans), null);
  assert.match(W.phraseEtape(pre, VUE, sans), /^Aucun moteur n'est installé/);
  assert.match(W.phraseEtape(pre, VUE, avec), /^Un moteur peut lire/);
  const page = W.PAGES.find((p) => p.k === "moteurs");
  assert.match(W.textePage(page, sans), /les moteurs ne sont pas installés/);
  assert.match(W.textePage(page, avec), /^Réalisez une première reconnaissance/);
  // L'OCR seul absent : la page reste celle de l'instance équipée, l'étape dit l'option.
  const sansOcr = W.moteurs({ kumiko: true, bulles: true, ocr: false });
  assert.equal(sansOcr.aucun, false);
  assert.equal(W.marqueEtape(pre, sansOcr), "optionnel ici");
  // Une réponse illisible ne conclut pas à l'absence.
  assert.deepEqual(W.moteurs(null), { aucun: false, ocr: true });
});

/* ── Les textes ───────────────────────────────────────────────────────────────────────── */

test("sept pages, dans l'ordre retenu : le corpus en 2e, le travail à plusieurs à part", () => {
  assert.deepEqual(W.PAGES.map((p) => p.k),
                   ["outil", "corpus", "zones", "moteurs", "analyse", "collab", "sortir"]);
  assert.deepEqual(W.FIN.parcours.map((p) => p.k), ["rapide", "complet"]);
});

test("la typographie : insécables devant la ponctuation haute et dans les nombres", () => {
  assert.equal(W.typo("Comment le texte et l'image se répondent-ils ?"),
               "Comment le texte et l'image se répondent‑ils ?");
  assert.equal(W.typo("« planche 3, case 2, bulle 1 »"),
               "« planche 3, case 2, bulle 1 »");
  assert.equal(W.typo("Les 9 étapes, 15 minutes : du corpus"),
               "Les 9 étapes, 15 minutes : du corpus");
  assert.equal(W.typo(null), "");
});

/* ── La visite ────────────────────────────────────────────────────────────────────────── */

test("la visite : sept pages, la barre du haut puis les six surfaces, des marques uniques", () => {
  assert.equal(W.VISITE.length, 7);
  assert.equal(W.VISITE[0].bande, true);
  assert.deepEqual(W.VISITE.slice(1).map((v) => v.surface),
                   ["/", "/annotation", "/corpus", "/recherche", "/exploration", "/administration"]);
  const m = W.marques().map((x) => x.marque);
  assert.equal(new Set(m).size, m.length, "une marque nomme une seule zone");
  for (const x of m) assert.match(x, /^[a-z]+(-[a-z]+)+$/, x);
  // Une page de plusieurs zones se joue en un ou deux temps, jamais trois.
  for (const v of W.VISITE) for (const z of v.zones) assert.ok([undefined, 1].includes(z[3]), z[0]);
});
