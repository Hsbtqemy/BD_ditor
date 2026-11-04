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

/* ── La fenêtre sur la zone ───────────────────────────────────────────────────────────── */

const ATELIER = 1, BIBLIO = 3, RECHERCHE = 4, ADMIN = 6;

test("le « ? » de la barre du haut est une zone de la visite, entre « Aa » et le bac", () => {
  const bande = W.VISITE[0].zones.map((z) => z[0]);
  assert.deepEqual(bande, ["bande-pages", "bande-projet", "bande-compte", "bande-affichage",
                           "bande-aide", "bande-bac"]);
});

test("une page se joue en un ou deux temps, et la fenêtre change de côté avec lui", () => {
  assert.deepEqual(W.tempsDe(0), [0]);
  assert.deepEqual(W.tempsDe(ATELIER), [0, 1]);
  assert.deepEqual(W.tempsDe(RECHERCHE), [0]);
  assert.deepEqual(W.tempsDe(99), []);
  assert.equal(W.cote({ page: ATELIER, temps: 0 }), "droite");
  assert.equal(W.cote({ page: ATELIER, temps: 1 }), "gauche");
  assert.equal(W.cote({ page: RECHERCHE }), "droite");
});

test("« Suivant » passe au second temps, puis à la page suivante ; « ← » revient d'où l'on vient", () => {
  assert.deepEqual(W.suivant({ page: 0, temps: 0 }), { page: ATELIER, temps: 0 });
  assert.deepEqual(W.suivant({ page: ATELIER, temps: 0 }), { page: ATELIER, temps: 1 });
  assert.deepEqual(W.suivant({ page: ATELIER, temps: 1 }), { page: 2, temps: 0 });
  assert.deepEqual(W.precedent({ page: 2, temps: 0 }), { page: ATELIER, temps: 1 });
  assert.deepEqual(W.precedent({ page: ATELIER, temps: 1 }), { page: ATELIER, temps: 0 });
  assert.deepEqual(W.precedent({ page: ATELIER, temps: 0 }), { page: 0, temps: 0 });
  assert.equal(W.precedent({ page: 0, temps: 0 }), null);
  assert.equal(W.suivant({ page: ADMIN, temps: 0 }), null);
  assert.equal(W.estFin({ page: ADMIN, temps: 0 }), true);
  assert.equal(W.estFin({ page: ATELIER, temps: 0 }), false);
  // Toute la visite, en avançant : chaque page, chaque temps, une seule fois.
  const vus = [];
  for (let p = { page: 0, temps: 0 }; p; p = W.suivant(p)) vus.push(`${p.page}.${p.temps}`);
  assert.deepEqual(vus, ["0.0", "1.0", "1.1", "2.0", "2.1", "3.0", "3.1", "4.0", "5.0", "6.0"]);
  // Une position illisible ne mène nulle part.
  assert.equal(W.suivant({ page: RECHERCHE, temps: 1 }), null);
  assert.equal(W.position({ page: "1" }), null);
  assert.equal(W.position(null), null);
});

test("« Visite n / 7 » ne reste pas figé entre les deux temps d'une page", () => {
  assert.equal(W.compteVisite({ page: 0, temps: 0 }), "Visite 1 / 7");
  const a = W.compteVisite({ page: ATELIER, temps: 0 });
  const b = W.compteVisite({ page: ATELIER, temps: 1 });
  assert.notEqual(a, b);
  assert.match(a, /^Visite 2 \/ 7/);
  assert.match(b, /^Visite 2 \/ 7/);
  assert.equal(W.compteVisite({ page: 99 }), "");
});

test("hors d'un bac à sable, aucun repère ne parle du bac à sable", () => {
  // Le « ? » est offert à tout compte (Hugo, 2026-11-04) : la Recherche et l'Exploration
  // ne disent « votre bac à sable n'y paraît pas » que dans un bac à sable. La zone
  // `bande-bac` n'existe que dans un bac à sable : la fenêtre ne la nomme pas ailleurs.
  W.VISITE.forEach((v, i) => {
    if (i === 0 && v.bande) return;
    assert.doesNotMatch(W.phrasePage(i, null), /bac à sable/, v.titre);
    W.tempsDe(i).forEach((t) => W.reperes(i, t, (m) => m !== "bande-bac", null).forEach((r) =>
      assert.doesNotMatch(`${r.nom} ${r.phrase}`, /bac à sable/, `${v.titre} ${r.marque}`)));
  });
  assert.equal(W.phrasePage(RECHERCHE, null), "Retrouver un mot dans tout le corpus.");
  assert.match(W.reperes(RECHERCHE, 0, null, null)[0].phrase, /^Le corpus ouvert à votre compte\.$/);
  // Dans son bac à sable, la phrase de la maquette ; chez un invité, « ce bac à sable ».
  assert.match(W.phrasePage(RECHERCHE, "mien"), /Votre bac à sable n.y paraît pas\.$/);
  assert.match(W.phrasePage(RECHERCHE, "autre"), /Ce bac à sable n.y paraît pas\.$/);
  assert.match(W.phrasePage(RECHERCHE + 1, "autre"), /ce bac à sable\.$/);
  assert.match(W.reperes(RECHERCHE, 0, null, "autre")[0].phrase, /sans ce bac à sable/);
  assert.equal(W.bacDuProjet({ bac_a_sable: { mien: true } }), "mien");
  assert.equal(W.bacDuProjet({ bac_a_sable: { mien: false } }), "autre");
  assert.equal(W.bacDuProjet({ id: 3 }), null);
  assert.equal(W.bacDuProjet(null), null);
});

test("les repères ne nomment que ce que la page montre, numérotés sans trou", () => {
  const tout = W.reperes(ATELIER, 0);
  assert.deepEqual(tout.map((r) => [r.marque, r.n]),
                   [["atelier-planches", 1], ["atelier-modes", 2], ["atelier-planche", 3]]);
  assert.deepEqual(W.reperes(ATELIER, 1).map((r) => [r.marque, r.n]),
                   [["atelier-structure", 4], ["atelier-actions", 5]]);
  // Le panneau de structure n'est pas visible (un tiroir fermé) : il n'est pas nommé, et
  // la suite reprend à 4.
  const sauf = (m) => m !== "atelier-structure";
  assert.deepEqual(W.reperes(ATELIER, 1, sauf).map((r) => [r.marque, r.n]),
                   [["atelier-actions", 4]]);
  assert.deepEqual(W.reperes(ATELIER, 0, () => false), []);
  assert.equal(tout[0].nom, "Album et planches");
  assert.match(tout[1].phrase, /^Navigation pour parcourir/);
  // Un temps sans zone visible ne se propose pas au « ? ».
  const sansFiche = (m) => !["bibliotheque-fiche", "bibliotheque-nouvel-album"].includes(m);
  assert.deepEqual(W.tempsVisibles(BIBLIO, sansFiche), [0]);
  assert.deepEqual(W.tempsVisibles(BIBLIO), [0, 1]);
  assert.deepEqual(W.tempsVisibles(BIBLIO, () => false), [0]);
});

test("le « ? » rouvre la page de la surface, jamais la barre du haut", () => {
  assert.equal(W.pageDeLaSurface("/"), ATELIER);
  assert.equal(W.pageDeLaSurface("/corpus"), BIBLIO);
  assert.equal(W.pageDeLaSurface("/corpus/"), BIBLIO);
  assert.equal(W.pageDeLaSurface("/administration"), ADMIN);
  assert.equal(W.pageDeLaSurface("/docs"), -1);
  assert.equal(W.pageDeLaSurface(""), ATELIER);
});

test("chaque page de la visite mène à sa surface, sur la planche du parcours", () => {
  assert.deepEqual(W.VISITE.map((v, i) => W.adresseVisite(i, VUE)), [
    "/?album=31&planche=310",
    "/?album=31&planche=310",
    "/annotation?album=31&planche=310",
    "/corpus?album=31",
    "/recherche",
    "/exploration",
    "/administration?vue=instance",
  ]);
  // Ni mode ni outil : la visite montre, elle ne fait rien faire.
  for (let i = 0; i < W.VISITE.length; i += 1) {
    assert.doesNotMatch(W.adresseVisite(i, VUE), /mode=/);
  }
  assert.equal(W.adresseVisite(ATELIER, null), "/");
  assert.equal(W.adresseVisite(BIBLIO, { jeu: [] }), "/corpus");
  assert.equal(W.adresseVisite(99, VUE), "/");
});

test("la visite en cours se relit sous le même login et le même bac à sable, et s'oublie", () => {
  const s = memoire();
  s.removeItem = (k) => s.brut().delete(k);
  assert.equal(W.retenirVisite("camille", BAC, { page: ATELIER, temps: 1 }, s), true);
  assert.deepEqual(W.lireVisite("camille", BAC, s), { page: ATELIER, temps: 1 });
  assert.equal(W.lireVisite("lea", BAC, s), null);
  assert.equal(W.lireVisite("camille", { id: 42, efface_le: BAC.efface_le }, s), null);
  assert.equal(W.lireVisite("camille", { id: 41, efface_le: "2026-11-16 03:00:00" }, s), null);
  W.oublierVisite(s);
  assert.equal(W.lireVisite("camille", BAC, s), null);
  // Une position hors de la visite ne s'écrit pas ; un stockage hostile ne lève rien.
  assert.equal(W.retenirVisite("camille", BAC, { page: RECHERCHE, temps: 1 }, s), false);
  assert.equal(W.retenirVisite(null, BAC, { page: 0 }, s), false);
  assert.equal(W.retenirVisite("camille", BAC, { page: 0 }, HOSTILE), false);
  assert.equal(W.lireVisite("camille", BAC, HOSTILE), null);
  assert.doesNotThrow(() => W.oublierVisite(HOSTILE));
  assert.equal(W.lireVisite("camille", BAC, memoire({ [W.CLE_VISITE]: "{pas du json" })), null);
});
