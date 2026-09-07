/* Tests unitaires de l'adresse d'un export de dépôt (static/lib/depot.js).
   Lancés par `node --test tests/js` (et via tests/test_js_unit.py sous pytest).

   Les trois erreurs que cette règle évite sont MUETTES : elles produisent une requête
   parfaitement valide, à laquelle le serveur répond quelque chose de plausible. Aucune ne
   se verrait à la relecture du gestionnaire de bouton, et la deuxième change les droits de
   ce qui sort de l'instance. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { ROUTES, RETOUR_ADMINISTRATION, choix, lienConnexionSharedocs, urlDepot }
  = require("../../static/lib/depot.js");

const params = (u) => new URLSearchParams(u.split("?")[1] || "");

test("chaque export ne propose que les formats de sa route", () => {
  // La table de vérité complète : trois exports × les formats des trois autres.
  const tous = ["json", "csv", "zip", "xlsx"];
  for (const quoi of Object.keys(ROUTES)) {
    for (const format of tous) {
      const r = urlDepot({ collectionId: 1, quoi, format, baseUrl: "https://i.example" });
      if (ROUTES[quoi].formats.indexOf(format) === -1) {
        assert.ok(r.refus, `${quoi}/${format} devrait être refusé`);
        assert.ok(!r.url, `${quoi}/${format} rend une URL malgré le refus`);
      } else {
        assert.ok(r.url, `${quoi}/${format} devrait être accepté`);
        assert.ok(!r.refus, `${quoi}/${format} rend un refus malgré l'URL`);
      }
    }
  }
});

test("`verbatim` ne part QUE vers les routes qui le déclarent", () => {
  // La fiche de description n'a pas de paramètre `verbatim` : le lui envoyer serait
  // ignoré en silence, et l'écran aurait promis le texte de l'œuvre sans le livrer.
  const fiche = urlDepot({ collectionId: 1, quoi: "description", format: "json",
                           verbatim: true });
  assert.equal(params(fiche.url).get("verbatim"), null);

  const records = urlDepot({ collectionId: 1, quoi: "metadonnees", format: "zip",
                             verbatim: true });
  assert.equal(params(records.url).get("verbatim"), "true");

  // Non coché : le paramètre est ABSENT, pas « false ». Les deux marchent côté serveur,
  // mais une URL qui ne porte que ce qu'on a demandé se relit.
  const sans = urlDepot({ collectionId: 1, quoi: "metadonnees", format: "zip" });
  assert.equal(params(sans.url).get("verbatim"), null);
});

test("une adresse d'images n'INJECTE pas de paramètres", () => {
  // Le seul défaut d'ici qui change les DROITS de ce qui sort : sans encodage, le `&`
  // ferait passer `verbatim=true` que personne n'a coché.
  const r = urlDepot({ collectionId: 1, quoi: "iiif", format: "zip",
                       baseUrl: "https://i.example/iiif?x=1&verbatim=true" });
  const p = params(r.url);
  assert.equal(p.get("verbatim"), null, "verbatim s'est glissé par l'adresse d'images");
  assert.equal(p.get("base_url"), "https://i.example/iiif?x=1&verbatim=true");
});

test("sans adresse, le manifeste part quand même — et sans paramètre vide", () => {
  // Règle renversée le 2026-09-07 : le champ a été obligatoire une demi-journée, et
  // c'était une faute d'usage. On ne peut pas nommer l'adresse d'images qu'on n'a pas
  // encore publiées — le cas de tout le monde avant le premier dépôt.
  for (const base of [undefined, "", "   "]) {
    const r = urlDepot({ collectionId: 1, quoi: "iiif", format: "zip", baseUrl: base });
    assert.ok(r.url, `base « ${base} » devrait passer`);
    assert.ok(!r.refus);
    // `base_url=` vide n'est PAS envoyé : le serveur distingue « absent » de « vide »
    // pour décider de l'aperçu, et lui envoyer une chaîne vide serait lui mentir sur
    // une intention. C'est la même distinction qu'AUTH-8 a dû faire sur Remote-Groups.
    assert.equal(params(r.url).has("base_url"), false, r.url);
  }
});

test("l'identifiant de collection est encodé", () => {
  const r = urlDepot({ collectionId: "1/../2", quoi: "description", format: "json" });
  assert.ok(!r.url.includes("1/../2"), "l'identifiant traverse le chemin tel quel");
});

test("un export inconnu est refusé plutôt que construit", () => {
  const r = urlDepot({ collectionId: 1, quoi: "crosswalk", format: "json" });
  assert.ok(r.refus);
  assert.ok(!r.url);
});

test("jamais les deux, jamais aucun des deux", () => {
  // Un appelant qui oublierait de tester `refus` construirait sinon une requête depuis
  // `undefined`, à laquelle le serveur répondrait quelque chose de plausible.
  const cas = [
    { collectionId: 1, quoi: "description", format: "json" },
    { collectionId: 1, quoi: "iiif", format: "zip" },
    { collectionId: 1, quoi: "inconnu", format: "json" },
    {},
  ];
  for (const c of cas) {
    const r = urlDepot(c);
    assert.equal(Boolean(r.url) !== Boolean(r.refus), true, JSON.stringify(c));
  }
});

test("l'écran n'offre AUCUNE combinaison que la règle refuserait", () => {
  // Le panneau construit son menu depuis `choix()` et son URL depuis `urlDepot()`. Si les
  // deux se désaccordaient, l'écran proposerait un artefact que le clic refuse — une
  // panne qui n'existe que pour l'utilisateur, jamais pour le serveur.
  const offerts = choix();
  assert.ok(offerts.length >= 6, "le menu s'est vidé");
  for (const o of offerts) {
    const r = urlDepot({ collectionId: 1, quoi: o.quoi, format: o.format,
                         baseUrl: "https://i.example/iiif" });
    assert.ok(r.url, `${o.libelle} est offert mais refusé : ${r.refus}`);
    assert.ok(o.libelle && !o.libelle.includes("undefined"), o.libelle);
  }
  // Et chaque libellé est unique : deux entrées de même texte rendraient le menu illisible.
  assert.equal(new Set(offerts.map((o) => o.libelle)).size, offerts.length);
});

test("le lien de connexion ShareDocs REVIENT bien ici", () => {
  // Le défaut que ce test attrape est muet : `Nav.safeRetour` n'accepte qu'un chemin
  // commençant par « / » (protection contre l'open-redirect). Écrire
  // « retour=administration » sans la barre le ferait rejeter, le bouton « ← Retour »
  // ne s'afficherait pas, et l'aller-retour deviendrait un aller simple — sans erreur,
  // sans trace, et sans que personne pense à regarder de ce côté.
  //
  // On confronte donc la valeur de `depot.js` à la RÈGLE de `nav.js`, au lieu de relire
  // l'une ou l'autre.
  const Nav = require("../../static/lib/nav.js");
  const href = lienConnexionSharedocs();
  const [chemin, qs] = href.split("?");
  assert.equal(chemin, "/", "le lien doit viser l'Atelier");

  const p = new URLSearchParams(qs);
  assert.equal(p.get("sharedocs"), "1", "la modale ne s'ouvrirait pas");
  assert.equal(Nav.safeRetour(p.get("retour")), RETOUR_ADMINISTRATION,
               "`retour` est rejeté par nav.js : le ← Retour disparaîtrait en silence");
});
