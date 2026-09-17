/* Tests unitaires de la logique pure du bloc « 👥 Comptes et groupes » (static/lib/comptes.js).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Tables de cas plutôt qu'exemples isolés : un tri qui range juste trois comptes peut
   ranger faux le quatrième, et c'est toujours le cas qu'on n'a pas écrit — sans date, ex
   æquo, accent, nom absent. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../../static/lib/comptes.js");

const ordre = (liste, axe) => liste.map((o) => C.identifiant(o, axe));

/* ── Tri ─────────────────────────────────────────────────────────────────────────── */

const COMPTES = [
  { login: "zoe", nom: "Chloé Vasseur", derniere_vue: "2026-09-14T08:00:00Z" },
  { login: "bob", nom: null, derniere_vue: null },
  { login: "alice", nom: "Alice Moreau", derniere_vue: "2026-09-16T10:00:00Z" },
  { login: "emile", nom: "Émile Durand", derniere_vue: "2026-09-16T10:00:00Z" },
  { login: "arrivant", nom: "Sacha Benali", derniere_vue: null },
];

test("A → Z porte sur le nom LU, accents compris, et un compte sans nom se lit par son login", () => {
  assert.deepEqual(ordre(C.trier(COMPTES, "comptes", "alpha"), "comptes"),
                   ["alice", "bob", "zoe", "emile", "arrivant"]);
});

test("Récents d'abord : la plus récente en tête, les ex æquo par nom, sans date à la fin", () => {
  // alice et emile sont venus à la même heure (`derniere_vue` est à l'heure près) : le nom
  // les départage, sinon deux rendus successifs pourraient les intervertir.
  assert.deepEqual(ordre(C.trier(COMPTES, "comptes", "recents"), "comptes"),
                   ["alice", "emile", "zoe", "bob", "arrivant"]);
});

test("les ex æquo de « Récents » sont départagés par nom, QUEL QUE SOIT l'ordre reçu", () => {
  // Le tri du moteur est stable : reçus dans le bon ordre, deux ex æquo y restent sans que
  // rien ne les départage — c'est l'ordre inverse qui prouve la règle (mutant survivant,
  // 2026-09-17).
  const recus = [COMPTES[3], COMPTES[2]];   // emile, puis alice, venus à la même heure
  assert.deepEqual(ordre(C.trier(recus, "comptes", "recents"), "comptes"), ["alice", "emile"]);
});

test("le tri ne modifie pas le tableau reçu", () => {
  const avant = ordre(COMPTES, "comptes");
  C.trier(COMPTES, "comptes", "recents");
  assert.deepEqual(ordre(COMPTES, "comptes"), avant);
});

const CAS_TRI = [
  { axe: "groupes", tri: "alpha",
    objets: [{ nom: "etudiants-bd-2026", derniere_venue: null },
             { nom: "annotateurs", derniere_venue: "2026-09-10T00:00:00Z" },
             { nom: "Enseignants", derniere_venue: "2026-09-12T00:00:00Z" }],
    attendu: ["annotateurs", "Enseignants", "etudiants-bd-2026"] },
  { axe: "groupes", tri: "recents",
    objets: [{ nom: "etudiants-bd-2026", derniere_venue: null },
             { nom: "annotateurs", derniere_venue: "2026-09-10T00:00:00Z" },
             { nom: "enseignants", derniere_venue: "2026-09-12T00:00:00Z" }],
    attendu: ["enseignants", "annotateurs", "etudiants-bd-2026"] },
  { axe: "collections", tri: "alpha",
    objets: [{ id: 3, nom: "Étude B", derniere_modification: null },
             { id: 1, nom: "Collection 10", derniere_modification: "2026-09-01T00:00:00Z" },
             { id: 2, nom: "Collection 9", derniere_modification: "2026-09-02T00:00:00Z" }],
    // `numeric` : « Collection 9 » avant « Collection 10 », comme on les lit.
    attendu: [2, 1, 3] },
  { axe: "collections", tri: "recents",
    objets: [{ id: 3, nom: "Étude B", derniere_modification: null },
             { id: 1, nom: "Collection 10", derniere_modification: "2026-09-01T00:00:00Z" },
             { id: 2, nom: "Collection 9", derniere_modification: "2026-09-02T00:00:00Z" }],
    attendu: [2, 1, 3] },
  { axe: "collections", tri: "recents",
    // Une date illisible est traitée comme une absence de date, jamais comme la plus récente.
    objets: [{ id: 1, nom: "A", derniere_modification: "pas une date" },
             { id: 2, nom: "B", derniere_modification: "2020-01-01T00:00:00Z" }],
    attendu: [2, 1] },
];

for (const cas of CAS_TRI) {
  test(`tri ${cas.axe} / ${cas.tri} → ${cas.attendu.join(", ")}`, () => {
    assert.deepEqual(ordre(C.trier(cas.objets, cas.axe, cas.tri), cas.axe), cas.attendu);
  });
}

test("chaque axe trie « Récents » sur SA date", () => {
  assert.equal(C.dateDe({ derniere_vue: "x", derniere_venue: "y" }, "comptes"), "x");
  assert.equal(C.dateDe({ derniere_vue: "x", derniere_venue: "y" }, "groupes"), "y");
  assert.equal(C.dateDe({ derniere_modification: "z", derniere_vue: "x" }, "collections"), "z");
  assert.equal(C.dateDe({}, "comptes"), null);
});

/* ── Filtre ──────────────────────────────────────────────────────────────────────── */

const CAS_FILTRE = [
  ["", ["zoe", "bob", "alice", "emile", "arrivant"]],
  ["chloe", ["zoe"]],             // sans accent → trouve « Chloé »
  ["CHLOÉ", ["zoe"]],             // casse et accent de l'autre côté
  ["zo", ["zoe"]],                // par le login
  ["bob", ["bob"]],               // un compte sans nom se trouve par son login
  ["  alice  ", ["alice"]],       // espaces autour ignorés
  ["emile", ["emile"]],           // « Émile »
  ["personne", []],
];
for (const [texte, attendu] of CAS_FILTRE) {
  test(`filtre comptes « ${texte} » → [${attendu.join(", ")}]`, () => {
    assert.deepEqual(ordre(C.filtrer(COMPTES, "comptes", texte), "comptes"), attendu);
  });
}

test("le filtre d'un groupe ou d'une collection porte sur son nom", () => {
  const g = [{ nom: "etudiants-bd-2026" }, { nom: "annotateurs" }];
  assert.deepEqual(ordre(C.filtrer(g, "groupes", "BD"), "groupes"), ["etudiants-bd-2026"]);
  const c = [{ id: 1, nom: "Étude B" }, { id: 2, nom: "Presse" }];
  assert.deepEqual(ordre(C.filtrer(c, "collections", "etude"), "collections"), [1]);
});

/* ── Adresse ─────────────────────────────────────────────────────────────────────── */

const CAS_LECTURE = [
  ["", { axe: "comptes", tri: "alpha", sel: null }],
  ["?compte=alice", { axe: "comptes", tri: "alpha", sel: "alice" }],
  ["?axe=groupes&groupe=etudiants-bd-2026&tri=recents",
   { axe: "groupes", tri: "recents", sel: "etudiants-bd-2026" }],
  ["?axe=collections&collection=12", { axe: "collections", tri: "alpha", sel: 12 }],
  // Une valeur inconnue retombe sur le défaut, sans casser le reste de l'adresse.
  ["?axe=personnes&tri=date&compte=alice", { axe: "comptes", tri: "alpha", sel: "alice" }],
  // La sélection n'est lue que pour l'axe affiché.
  ["?axe=groupes&compte=alice", { axe: "groupes", tri: "alpha", sel: null }],
  // Un id de collection qui n'est pas un entier positif n'ouvre rien.
  ["?axe=collections&collection=abc", { axe: "collections", tri: "alpha", sel: null }],
  ["?axe=collections&collection=0", { axe: "collections", tri: "alpha", sel: null }],
  ["?compte=", { axe: "comptes", tri: "alpha", sel: null }],
  // Un login qui porte des caractères d'adresse se relit tel quel.
  ["?compte=poste%20salle%26204", { axe: "comptes", tri: "alpha", sel: "poste salle&204" }],
];
for (const [search, attendu] of CAS_LECTURE) {
  test(`lireAdresse(${JSON.stringify(search)})`, () => {
    assert.deepEqual(C.lireAdresse(search), attendu);
  });
}

test("écrire puis relire l'adresse rend le même état, sur chaque axe et chaque tri", () => {
  const sels = { comptes: "poste salle&204", groupes: "etudiants-bd-2026", collections: 7 };
  for (const axe of C.AXES) {
    for (const tri of C.TRIS) {
      for (const sel of [null, sels[axe]]) {
        const etat = { axe, tri, sel };
        assert.deepEqual(C.lireAdresse(C.ecrireAdresse(etat, "")), etat);
      }
    }
  }
});

test("l'adresse tait les défauts et garde les paramètres qui ne sont pas au bloc", () => {
  assert.equal(C.ecrireAdresse({ axe: "comptes", tri: "alpha", sel: null }, ""), "");
  assert.equal(C.ecrireAdresse({ axe: "comptes", tri: "alpha", sel: null }, "?x=1&tri=recents"),
               "?x=1");
  // Changer d'axe efface la sélection de l'axe quitté : deux sélections ne coexistent pas.
  assert.equal(C.ecrireAdresse({ axe: "groupes", tri: "recents", sel: null },
                               "?compte=alice&tri=recents"),
               "?axe=groupes&tri=recents");
});

test("le tri survit au changement d'axe dans l'adresse", () => {
  const avant = C.lireAdresse("?tri=recents&compte=alice");
  const apres = C.lireAdresse(C.ecrireAdresse({ ...avant, axe: "collections", sel: null },
                                              "?tri=recents&compte=alice"));
  assert.equal(apres.tri, "recents");
  assert.equal(apres.axe, "collections");
});

/* ── État court d'une ligne ──────────────────────────────────────────────────────── */

const MAINTENANT = new Date("2026-09-17T12:00:00Z");

test("dateCourte : jour et mois dans l'année, l'année au-delà, rien pour une absence", () => {
  assert.equal(C.dateCourte("2026-09-14T12:00:00Z", MAINTENANT), "14/09");
  assert.equal(C.dateCourte("2025-09-14T12:00:00Z", MAINTENANT), "14/09/2025");
  assert.equal(C.dateCourte(null, MAINTENANT), null);
  assert.equal(C.dateCourte("pas une date", MAINTENANT), null);
});

const CAS_ETAT = [
  // [objet, axe, tri, état annuaire, texte, alerte]
  [{ derniere_vue: "2026-09-14T12:00:00Z", signaux: [] }, "comptes", "alpha", "lu",
   "vu le 14/09", false],
  [{ derniere_vue: null, signaux: ["jamais_venu"] }, "comptes", "alpha", "lu",
   "aucune connexion", true],
  [{ dans_annuaire: true, nb_comptes: 12, derniere_venue: null, signaux: [] },
   "groupes", "alpha", "lu", "12 comptes", false],
  [{ dans_annuaire: true, nb_comptes: 1, derniere_venue: null, signaux: [] },
   "groupes", "alpha", "lu", "1 compte", false],
  [{ dans_annuaire: true, nb_comptes: 0, derniere_venue: null, signaux: [] },
   "groupes", "alpha", "lu", "0 compte", false],
  [{ dans_annuaire: true, nb_comptes: 4, derniere_venue: "2026-09-12T12:00:00Z", signaux: [] },
   "groupes", "recents", "lu", "actif le 12/09", false],
  [{ dans_annuaire: true, nb_comptes: 4, derniere_venue: null, signaux: [] },
   "groupes", "recents", "lu", "aucune venue", false],
  // Un groupe absent de l'annuaire est une alerte, quel que soit le tri.
  [{ dans_annuaire: false, nb_comptes: null, derniere_venue: null, signaux: [] },
   "groupes", "recents", "lu", "absent de l'annuaire", true],
  // Panne : on ne sait pas — et on le DIT. Sans annuaire : il n'y a rien à vérifier, donc
  // on ne parle pas de vérification, on dit ce que l'application sait.
  [{ dans_annuaire: null, nb_comptes: null, derniere_venue: null, collections: [{}, {}] },
   "groupes", "alpha", "non_verifie", "non vérifié", false],
  [{ dans_annuaire: null, nb_comptes: null, derniere_venue: null, collections: [{}, {}] },
   "groupes", "recents", "sans_annuaire", "2 collections", false],
  [{ nb_albums: 12, derniere_modification: null, signaux: [] }, "collections", "alpha", "lu",
   "12 albums", false],
  [{ nb_albums: 1, derniere_modification: "2026-09-16T09:00:00Z", signaux: ["sans_proprietaire"] },
   "collections", "recents", "lu", "modifiée le 16/09", true],
  [{ nb_albums: 0, derniere_modification: null, signaux: [] }, "collections", "recents", "lu",
   "jamais modifiée", false],
];
for (const [objet, axe, tri, etat, texte, alerte] of CAS_ETAT) {
  test(`etatCourt ${axe}/${tri}/${etat} → « ${texte} »${alerte ? " (alerte)" : ""}`, () => {
    assert.deepEqual(C.etatCourt(objet, axe, tri, etat, MAINTENANT), { texte, alerte });
  });
}

/* ── Niveaux et diffusion ────────────────────────────────────────────────────────── */

test("un niveau inconnu s'affiche TEL QUEL, il ne disparaît pas", () => {
  assert.equal(C.niveauLu("ecriture"), "écriture");
  assert.equal(C.niveauLu("proprietaire"), "propriétaire");
  assert.equal(C.niveauLu("contribution"), "contribution");   // le jour où AUTH-10 l'ajoute
  assert.equal(C.niveauLu("toString"), "toString");            // pas un piège de prototype
});

test("un régime de diffusion inconnu s'affiche tel quel, un régime absent ne s'affiche pas", () => {
  assert.equal(C.diffusionLue("prive"), "privé");
  assert.equal(C.diffusionLue("autre"), "autre");
  assert.equal(C.diffusionLue(null), null);
});

/* ── Signaux ─────────────────────────────────────────────────────────────────────── */

const NOMS = { collections: { 5: "Étude B", 7: "Presse" },
               comptes: { bob: "Bob Martin" } };

const CAS_SIGNAUX = [
  [{ signal: "groupe_absent", groupe: "ancien-cours", collection: 5 },
   { type: "groupe", id: "ancien-cours" },
   "Le groupe ancien-cours n'est pas dans l'annuaire (accès à « Étude B »)"],
  [{ signal: "compte_absent", login: "eve", collection: 7 },
   { type: "compte", id: "eve" },
   "Le compte eve n'est pas dans l'annuaire (accès à « Presse »)"],
  [{ signal: "proprietaire_absent", collection: 5 }, { type: "collection", id: 5 },
   "« Étude B » n'a plus de propriétaire dans l'annuaire"],
  [{ signal: "sans_proprietaire", collection: 7 }, { type: "collection", id: 7 },
   "« Presse » n'a pas de propriétaire"],
  [{ signal: "identite_changee", login: "bob" }, { type: "compte", id: "bob" },
   "Bob Martin (bob) : identité changée"],
  [{ signal: "jamais_venu", login: "carole" }, { type: "compte", id: "carole" },
   "carole : aucune connexion"],
  // Une collection absente de la table des noms se nomme par son id, jamais « undefined ».
  [{ signal: "sans_proprietaire", collection: 99 }, { type: "collection", id: 99 },
   "« collection 99 » n'a pas de propriétaire"],
  // Un code que l'écran ne connaît pas encore se montre par son nom, et mène quelque part.
  [{ signal: "nouveau_code", login: "dora" }, { type: "compte", id: "dora" }, "nouveau_code"],
];
for (const [s, cible, texte] of CAS_SIGNAUX) {
  test(`signal ${s.signal} → ${cible.type} ${cible.id}`, () => {
    assert.deepEqual(C.cibleSignal(s), cible);
    assert.equal(C.texteSignal(s, NOMS), texte);
  });
}

const venus = (n) => Array.from({ length: n }, (_, i) => ({ signal: "jamais_venu",
                                                              login: `e${i}` }));

test("cinq signaux du même code restent ligne à ligne", () => {
  const r = C.regrouperSignaux(venus(5));
  assert.equal(r.length, 5);
  assert.ok(r.every((x) => !x.replie));
});

test("au-delà de cinq, UNE ligne dépliable qui garde tous les signaux", () => {
  const r = C.regrouperSignaux(venus(6));
  assert.equal(r.length, 1);
  assert.equal(r[0].replie, true);
  assert.equal(r[0].signaux.length, 6);
  assert.equal(C.texteGroupeSignaux(r[0].signal, r[0].signaux.length), "6 comptes jamais venus");
});

test("chaque code se décide seul, et l'ordre du serveur est gardé", () => {
  const serveur = [
    { signal: "groupe_absent", groupe: "g1", collection: 1 },
    { signal: "sans_proprietaire", collection: 2 },
    ...venus(12),
  ];
  const r = C.regrouperSignaux(serveur);
  assert.deepEqual(r.map((x) => (x.replie ? `[${x.signal}×${x.signaux.length}]` : x.signal)),
                   ["groupe_absent", "sans_proprietaire", "[jamais_venu×12]"]);
});

test("le seuil est cinq, et c'est une constante du module", () => {
  assert.equal(C.SEUIL_REGROUPEMENT, 5);
  assert.equal(C.regrouperSignaux(venus(3), 2).length, 1);
});

/* ── Annuaire et départ ──────────────────────────────────────────────────────────── */

test("le lien vers l'annuaire n'accepte qu'une adresse web", () => {
  assert.equal(C.lienAnnuaire("https://annuaire.exemple.fr/"), "https://annuaire.exemple.fr/");
  assert.equal(C.lienAnnuaire(null), null);
  assert.equal(C.lienAnnuaire(""), null);
  assert.equal(C.lienAnnuaire("javascript:alert(1)"), null);
  assert.equal(C.lienAnnuaire("doublure:"), null);
});

const CAS_DEPART = [
  [{ actes: 0, acces_explicites: 0 }, "rien à orpheliner"],
  [{ actes: 1, acces_explicites: 0 },
   "1 acte resterait à ce login ; un compte recréé sous ce nom en hériterait"],
  [{ actes: 12, acces_explicites: 0 },
   "12 actes resteraient à ce login ; un compte recréé sous ce nom en hériterait"],
  [{ actes: 0, acces_explicites: 1 },
   "1 accès resterait à ce login ; un compte recréé sous ce nom en hériterait"],
  [{ actes: 214, acces_explicites: 2 },
   "214 actes et 2 accès resteraient à ce login ; un compte recréé sous ce nom en hériterait"],
];
for (const [compte, texte] of CAS_DEPART) {
  test(`départ : ${compte.actes} acte(s), ${compte.acces_explicites} accès`, () => {
    const t = C.consequenceSuppression(compte);
    assert.equal(t, texte);
    // La doctrine d'AUTH-7 : une CONSÉQUENCE, jamais une recommandation.
    assert.doesNotMatch(t, /possible|recommand|supprimable/i);
  });
}
