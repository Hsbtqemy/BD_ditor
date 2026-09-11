/* Adresse d'un export de dépôt (EXP-1) — logique PURE, sans DOM.
   Chargé en <script> AVANT corpus.js (la Bibliothèque, depuis COL-2) → expose `window.BDDepot` ; aussi
   require()-able par `tests/js/depot.test.js`.

   Pourquoi une règle isolée plutôt qu'une concaténation dans le gestionnaire du bouton.

   La leçon est celle de `sante.js`, et elle a été payée : un test qui LIT le source d'une
   surface se satisfait de trouver les bons mots, fût-ce dans la mauvaise branche. Ce qui
   se construit ici n'est pas décoratif — c'est l'URL qui décide quel artefact part, avec
   quel périmètre et quel contenu — et trois erreurs y sont muettes.

   1. **`verbatim` envoyé à une route qui l'ignore.** FastAPI n'a que faire d'un paramètre
      inconnu : la case cochée n'aurait aucun effet, et l'écran aurait promis le texte de
      l'œuvre sans le livrer. Rien ne le signale, ni au client ni au serveur.
   2. **`base_url` non encodé.** Une adresse contenant `&` INJECTE des paramètres dans la
      requête — `verbatim=true` s'y glisse sans qu'on l'ait coché. C'est le seul défaut
      d'ici qui change les DROITS de ce qui sort.
   3. **Un format proposé pour le mauvais export.** La fiche ne produit pas de XLSX, les
      enregistrements pas de CSV isolé : le serveur répond 422, l'écran dit « échec », et
      personne ne sait que c'est le bouton qui a tort.

   La table `ROUTES` est donc la déclaration de ce que chaque export accepte, et
   `tests/js/depot.test.js` la parcourt. Elle doit rester d'accord avec `routes/depot.py` :
   c'est la contrepartie assumée de la duplication, et elle est étroite — trois lignes. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDDepot = api;                                                    // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Ce que chaque export accepte, en face de `routes/depot.py`.
     `verbatim` et `base` disent si la route DÉCLARE le paramètre — plus si elle l'exige.
     `base_url` a été obligatoire une demi-journée, et c'était une faute d'usage : on ne
     peut pas nommer l'adresse d'images qu'on n'a pas encore publiées. Sans elle, le
     manifeste sort en aperçu, et c'est le serveur qui le déclare. */
  const ROUTES = {
    description: { libelle: "Fiche de description", formats: ["json", "csv"],
                   verbatim: false, base: false },
    metadonnees: { libelle: "Enregistrements", formats: ["json", "zip", "xlsx"],
                   verbatim: true, base: false },
    iiif: { libelle: "Manifeste IIIF", formats: ["zip"], verbatim: true, base: false },
  };

  /* Le nom d'un format à l'écran. « CSV (zip) » plutôt que « zip » : ce qu'on télécharge
     est une archive DE CSV, et le dire évite d'ouvrir l'archive pour le découvrir. */
  const FORMATS = { json: "JSON", csv: "CSV", zip: "CSV (zip)", xlsx: "XLSX" };

  /* Les couples (export, format) offerts, dans l'ordre de la table. Dérivé plutôt que
     recopié : une liste écrite à la main OUBLIE ce qu'on ajoute — le mode d'échec de
     `test_csp`, et il est silencieux. */
  function choix() {
    const out = [];
    for (const quoi of Object.keys(ROUTES)) {
      for (const format of ROUTES[quoi].formats) {
        out.push({ quoi, format,
                   libelle: ROUTES[quoi].libelle + " — "
                            + (quoi === "iiif" ? "archive" : FORMATS[format]) });
      }
    }
    return out;
  }

  /* Le retour de l'aller-retour vers l'Atelier. Un chemin ABSOLU, et c'est tout le
     piège : `Nav.safeRetour` n'accepte qu'un chemin commençant par « / » — protection
     contre l'open-redirect —, et l'écrire sans la barre le ferait REJETER en silence.
     Le lien « ← Retour » ne s'afficherait simplement pas, et l'aller-retour deviendrait
     un aller simple sans que rien n'échoue. `tests/js/depot.test.js` confronte donc cette
     valeur à la règle de `nav.js` plutôt que de la relire. */
  const RETOUR_BIBLIOTHEQUE = "/corpus";

  /* Le lien qui ouvre la session ShareDocs dans l'Atelier et ramène ici (EXP-1).

     La connexion vit là-bas parce qu'elle est arrivée par l'import d'images ; le dépôt
     d'exports vit ici. Plutôt que d'indiquer un chemin à suivre — une réponse de
     documentation à un problème d'interface —, on emmène et on ramène. */
  function lienConnexionSharedocs() {
    return "/?sharedocs=1&retour=" + encodeURIComponent(RETOUR_BIBLIOTHEQUE);
  }

  /* Rend `{ url }` ou `{ refus }`. Jamais les deux, jamais ni l'un ni l'autre : un
     appelant qui oublierait de tester `refus` construirait sinon une requête depuis
     `undefined`, et le serveur répondrait quelque chose de plausible. */
  function urlDepot(demande) {
    const d = demande || {};
    const spec = ROUTES[d.quoi];
    if (!spec) return { refus: "Export inconnu." };
    if (spec.formats.indexOf(d.format) === -1) {
      return { refus: "Le format « " + d.format + " » n'existe pas pour cet export." };
    }
    const base = String(d.baseUrl || "").trim();
    let url = "/api/collections/" + encodeURIComponent(d.collectionId)
            + "/depot/" + d.quoi + "?format=" + encodeURIComponent(d.format);
    if (spec.verbatim && d.verbatim) url += "&verbatim=true";
    // Envoyé seulement s'il y a quelque chose à envoyer : une adresse vide fait sortir
    // le manifeste en APERÇU, ce qui est le cas ordinaire tant que les images ne sont
    // publiées nulle part. `base` reste dans la table pour dire QUI accepte ce paramètre.
    if (spec.base !== undefined && base) url += "&base_url=" + encodeURIComponent(base);
    return { url: url };
  }

  return { ROUTES, FORMATS, RETOUR_BIBLIOTHEQUE, choix, lienConnexionSharedocs,
           urlDepot };
});
