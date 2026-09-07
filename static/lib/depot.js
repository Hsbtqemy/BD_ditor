/* Adresse d'un export de dépôt (EXP-1) — logique PURE, sans DOM.
   Chargé en <script> AVANT administration.js → expose `window.BDDepot` ; aussi
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
     `verbatim` : la route déclare-t-elle le paramètre. `base` : l'exige-t-elle. */
  const ROUTES = {
    description: { libelle: "Fiche de description", formats: ["json", "csv"],
                   verbatim: false, base: false },
    metadonnees: { libelle: "Enregistrements", formats: ["json", "zip", "xlsx"],
                   verbatim: true, base: false },
    iiif: { libelle: "Manifeste IIIF", formats: ["zip"], verbatim: true, base: true },
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
    if (spec.base && !base) {
      return { refus: "Indiquez l'adresse du serveur qui servira les images : "
                      + "l'application ne peut pas la deviner." };
    }
    let url = "/api/collections/" + encodeURIComponent(d.collectionId)
            + "/depot/" + d.quoi + "?format=" + encodeURIComponent(d.format);
    if (spec.verbatim && d.verbatim) url += "&verbatim=true";
    if (spec.base) url += "&base_url=" + encodeURIComponent(base);
    return { url: url };
  }

  return { ROUTES, FORMATS, choix, urlDepot };
});
