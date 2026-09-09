/* Normalisation de casse d'une transcription (NLP-3) — côté JavaScript.
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   CE FICHIER EST LA MOITIÉ QUI MORD. La règle vit en double — le bouton du mode
   Transcription ici, l'outil de lot en Python — et `tests/cas-casse.json` est généré
   depuis `casse.py`. Côté Python il ne fait donc que se relire ; c'est ICI qu'il mesure
   quelque chose : chaque cas de la table est une assertion sur le fait que les deux
   écritures d'une même règle ne se sont pas séparées.

   Elles ont deux raisons de se séparer, et les deux sont silencieuses : le `\w` de
   JavaScript est resté ASCII (d'où `\p{L}` d'un côté, `[^\W\d_]` de l'autre), et
   `String.toUpperCase()` ne s'accorde pas avec `str.upper()` sur tout l'Unicode. Aucune
   des deux ne lève : elles rendent juste un texte un peu différent, sur un accent ou un
   point de suspension, et personne ne le voit. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { estToutCapitales, normaliser } = require("../../static/lib/casse.js");

const TABLE = JSON.parse(
  fs.readFileSync(path.join(__dirname, "..", "cas-casse.json"), "utf8"));

test("la table partagée : chaque cas rend le même texte qu'en Python", () => {
  assert.ok(TABLE.length > 10, "table de cas suspicieusement courte");
  for (const cas of TABLE) {
    assert.equal(normaliser(cas.entree), cas.attendu, cas.nom);
  }
});

test("la table sème les DEUX côtés d'only_upper", () => {
  // Mode d'échec de la table : ne contenir que des cas capitaux. La garde pourrait
  // alors disparaître sans qu'un seul cas bronche — et c'est elle qui empêche un
  // second clic de démolir « Tintin ».
  assert.ok(TABLE.some((c) => estToutCapitales(c.entree)), "aucun cas en capitales");
  assert.ok(TABLE.some((c) => c.entree && !estToutCapitales(c.entree)), "aucun cas mixte");
});

test("un sigle ponctué survit, et son point ne relève pas le mot suivant", () => {
  assert.equal(normaliser("LE F.B.I. ARRIVE."), "Le F.B.I. arrive.");
  assert.equal(normaliser("C'EST LE F.B.I. QUI ARRIVE."), "C'est le F.B.I. qui arrive.");
});

test("LIMITE ASSUMÉE — un sigle non ponctué et un nom propre ne sont pas relevés", () => {
  // Les deviner produirait des faux positifs muets ; les laisser en bas de casse met
  // l'erreur sous les yeux de qui vient de cliquer. Le relevé des noms suppose le
  // gazetteer d'ANN-3, qui n'est pas commencé.
  assert.equal(normaliser("LE FBI ARRIVE."), "Le fbi arrive.");
  assert.equal(normaliser("BONJOUR TINTIN."), "Bonjour tintin.");
});

test("le saut de ligne ne ferme pas la phrase (le lettrage coupe au milieu)", () => {
  assert.equal(normaliser("JE SUIS\nLÀ."), "Je suis\nlà.");
});

test("les points de suspension ne ferment pas la phrase", () => {
  assert.equal(normaliser("JE... JE NE SAIS PAS."), "Je... je ne sais pas.");
  assert.equal(normaliser("JE… JE NE SAIS PAS."), "Je… je ne sais pas.");
});

test("only_upper — une ligne qui n'est pas intégralement capitale n'est pas touchée", () => {
  for (const t of ["Je suis là, Tintin.", "je suis là", "JE SUIS Là", "?!  …", ""]) {
    assert.equal(normaliser(t), t);
  }
});

test("idempotence — un second clic ne démolit rien", () => {
  for (const cas of TABLE) {
    const une = normaliser(cas.entree);
    assert.equal(normaliser(une), une, cas.nom);
  }
});

test("réversible tant que la source était capitale", () => {
  // `upper(normalisé) === original` : le texte que la passe de lot remplace n'est pas
  // perdu, il se recalcule. La propriété tombe dès que la source est mixte — d'où la garde.
  for (const cas of TABLE) {
    if (estToutCapitales(cas.entree)) {
      assert.equal(normaliser(cas.entree).toUpperCase(), cas.entree, cas.nom);
    }
  }
});

test("le drapeau `g` du motif de sigle ne garde pas de curseur entre deux appels", () => {
  // `RegExp` avec `g` porte un `lastIndex` MUTABLE, partagé par tous les appels puisque
  // le motif est un littéral de module. Sans la remise à zéro, le deuxième appel
  // repartirait du milieu du premier texte et manquerait le sigle — silencieusement,
  // et une fois sur deux seulement.
  const t = "LE F.B.I. ARRIVE.";
  assert.equal(normaliser(t), normaliser(t));
  assert.equal(normaliser(t), "Le F.B.I. arrive.");
});

test("estToutCapitales", () => {
  for (const [t, attendu] of [["ALORS", true], ["Alors", false], ["alors", false],
                              ["ÉTÉ", true], ["?!", false], ["", false],
                              ["F.B.I.", true], ["30 ANS", true], ["30", false]]) {
    assert.equal(estToutCapitales(t), attendu, JSON.stringify(t));
  }
});
