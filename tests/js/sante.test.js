/* Tests unitaires de la règle d'affichage des moteurs (static/lib/sante.js).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Cette règle croise DEUX réponses du serveur, et l'erreur qu'elle évite est muette :
   afficher « en panne » sur un moteur simplement non installé — l'état normal de la
   plupart des postes, les moteurs étant optionnels — n'échoue nulle part, ne casse
   aucune suite, et apprend seulement à ne plus lire le panneau. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { MOTEURS, etat, bilan } = require("../../static/lib/sante.js");

const OCR = MOTEURS.find((m) => m.cle === "ocr");
const NLP = MOTEURS.find((m) => m.cle === "nlp");

test("sans contrôle profond, on ne dit jamais qu'un moteur fonctionne", () => {
  const e = etat({ ocr: true }, null, OCR);
  assert.equal(e.etat, "present");
  assert.equal(e.mot, "présent, non éprouvé");
  // Le mot « opérationnel » est réservé à un import réel : c'est tout le chantier.
  assert.notEqual(e.mot, "opérationnel");
});

test("un moteur absent n'est pas une panne, avant comme après l'épreuve", () => {
  const avant = etat({ ocr: false }, null, OCR);
  assert.equal(avant.etat, "absent");
  const apres = etat({ ocr: false },
                     { ocr: { ok: false, erreur: "ModuleNotFoundError: easyocr" } }, OCR);
  assert.equal(apres.etat, "absent");
  assert.equal(apres.mot, "non installé");
});

test("installé mais cassé : le seul cas grave, et il se dit", () => {
  const e = etat({ ocr: true },
                 { ocr: { ok: false, erreur: "RuntimeError: torchvision::nms" } }, OCR);
  assert.equal(e.etat, "panne");
  assert.equal(e.mot, "en panne");
  assert.match(e.note, /torchvision::nms/);   // la CAUSE est reportée, pas résumée
});

test("le contrôle profond fait autorité sur le fait", () => {
  // Le rapide se trompait (c'est sa raison d'être) : l'import a réussi, donc il marche.
  const e = etat({ ocr: false }, { ocr: { ok: true, erreur: null } }, OCR);
  assert.equal(e.etat, "ok");
  assert.equal(e.mot, "opérationnel");
});

test("les deux jeux de clefs sont appariés — `nlp` côté profond, `lemmes` côté rapide", () => {
  assert.equal(NLP.rapide, "lemmes");
  assert.equal(etat({ lemmes: true }, null, NLP).etat, "present");
  assert.equal(etat({ nlp: true }, null, NLP).etat, "absent");     // clef ignorée : bonne
  assert.equal(etat({ lemmes: true }, { nlp: { ok: true } }, NLP).etat, "ok");
});

test("une panne sans message reste une panne, et le dit", () => {
  const e = etat({ ocr: true }, { ocr: { ok: false, erreur: null } }, OCR);
  assert.equal(e.etat, "panne");
  assert.ok(e.note, "une panne muette laisserait une ligne rouge sans explication");
});

test("aucune réponse du serveur : rien n'est affirmé", () => {
  for (const m of MOTEURS) assert.equal(etat(null, null, m).etat, "absent");
});

test("chaque moteur porte un nom et un rôle lisibles", () => {
  for (const m of MOTEURS) {
    assert.ok(m.nom && m.role, `moteur ${m.cle} incomplet`);
    // Le MOT porte l'état à lui seul (WCAG 1.4.1) : quatre états, quatre libellés.
    const mots = new Set([
      etat({ [m.rapide]: false }, null, m).mot,
      etat({ [m.rapide]: true }, null, m).mot,
      etat({ [m.rapide]: true }, { [m.cle]: { ok: true } }, m).mot,
      etat({ [m.rapide]: true }, { [m.cle]: { ok: false, erreur: "x" } }, m).mot,
    ]);
    assert.equal(mots.size, 4, `états indistinguables sans la couleur pour ${m.cle}`);
  }
});

/* ── Le bilan d'une épreuve ─────────────────────────────────────────────────────── */

const TOUT_LA = { kumiko: true, bulles: true, ocr: true, lemmes: true };
const RIEN_LA = { kumiko: false, bulles: false, ocr: false, lemmes: false };
const tousOk = Object.fromEntries(MOTEURS.map((m) => [m.cle, { ok: true }]));
const tousAbsents = Object.fromEntries(
  MOTEURS.map((m) => [m.cle, { ok: false, erreur: "ModuleNotFoundError" }]));

test("un rapport profond VIDE ne se lit pas comme une bonne nouvelle", () => {
  /* Le cas qui a fait sortir ce bilan de la page : `/api/sante?profond=1` répond sans son
     bloc `profond` (proxy qui filtre, serveur plus ancien). Les quatre moteurs restent
     « non éprouvés », donc zéro panne — et un bilan qui compte les pannes annonce
     tranquillement « aucun moteur installé » à l'instant où le diagnostic vient
     d'échouer. Aucune exception, aucun test rouge : juste une phrase fausse. */
  // La quatrième forme du vide : un bloc NON vide qui ne parle pas de nos moteurs.
  // Un serveur ayant renommé `nlp` renverrait exactement cela.
  for (const vide of [null, undefined, {}, { langue: { ok: true } }]) {
    const b = bilan(TOUT_LA, vide);
    assert.equal(b.erreur, true);
    assert.match(b.texte, /aucun verdict/i);
    assert.doesNotMatch(b.texte, /aucun moteur installé/i);
  }
});

test("une panne est annoncée, comptée, et renvoie quelque part", () => {
  const un = bilan(TOUT_LA, { ...tousOk,
                              bulles: { ok: false, erreur: "RuntimeError" } });
  assert.equal(un.erreur, true);
  assert.match(un.texte, /^1 moteur installé mais inutilisable\./);   // singulier
  assert.match(un.texte, /deploiement-docker/);   // « en panne » sans « et alors ? »

  const deux = bilan(TOUT_LA, { ...tousOk,
                                bulles: { ok: false, erreur: "x" },
                                ocr: { ok: false, erreur: "y" } });
  assert.match(deux.texte, /^2 moteurs installés mais inutilisables\./);
});

test("tout va bien se dit sans emphase, et n'est pas une erreur", () => {
  const b = bilan(TOUT_LA, tousOk);
  assert.equal(b.erreur, false);
  assert.match(b.texte, /répondent/);
});

test("aucun moteur installé n'est pas une panne, et le bilan le dit", () => {
  const b = bilan(RIEN_LA, tousAbsents);
  assert.equal(b.erreur, false, "un poste sans moteur n'a rien à réparer");
  assert.match(b.texte, /503/);   // ce qui arrivera concrètement, pas juste « absent »
});
