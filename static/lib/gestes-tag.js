/* Remanier un tag depuis le panneau 📖 Lexique (ANN-8) — logique PURE, sans DOM.
   Chargé en <script> AVANT exploration.js → expose `window.BDGestesTag` ; aussi
   require()-able par `tests/js/gestes-tag.test.js`.

   Trois gestes : renommer, fusionner dans un autre tag, supprimer. Trois règles :

   1. L'ÉCRAN N'OFFRE QUE CE QUE LE SERVEUR ACCEPTERAIT, et il ne le devine pas. Fusionner,
      renommer ou supprimer un tag posé : la clé `remaniable` de `GET /api/lexique`, tag par
      tag (`Portee.peut_remanier_tag`). Renommer ou supprimer un tag que l'écran voit
      inutilisé (décision du 2026-10-22 pour le renommage) : le droit de MODIFIER le terme, lu comme le menu « Portée » le lit déjà — dans `ecrivable`
      de `GET /api/collections` (`modifiable`, miroir de `Portee.peut_ecrire_terme`). Une
      fréquence 0 n'est pas une preuve : elle compte ce qu'on lit, et le serveur, qui
      compte tout le corpus, peut encore refuser — son 403 se lit alors tel quel.
   2. LA FUSION NE PROPOSE QUE DES CIBLES AU MOINS AUSSI VISIBLES que le tag : globales, ou
      de la même collection. Le serveur refuse les autres (409 « le cacherait ») ; les
      offrir serait promettre un geste refusé.
   3. LE NOMBRE SE DIT AVANT DE CONFIRMER, et c'est le serveur qui le donne — la même
      route jouée à blanc, après ses gardes. La phrase de réussite dit ce qui a été fait,
      avec le nombre que la route rend en l'ayant fait. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDGestesTag = api;                                                // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* « 0 région », « 1 région », « 2 régions » : le français met le singulier à 0 et 1. */
  function nombre(n, singulier, pluriel) {
    return `${n} ${n > 1 ? pluriel : singulier}`;
  }

  /* Miroir de `Portee.peut_ecrire_terme`, lu dans `ecrivable` (AUTH-12) : un tag LOCAL se
     modifie si l'on écrit dans sa collection ; un tag GLOBAL, si l'on écrit quelque part. */
  function modifiable(tag, collections) {
    const cols = collections || [];
    if (tag.collection_id == null) return cols.some((c) => c.ecrivable);
    const sa = cols.find((c) => String(c.id) === String(tag.collection_id));
    return !!(sa && sa.ecrivable);
  }

  /* Les gestes offerts sur un tag. `remaniable` doit valoir `true` : une clé absente (une
     réponse d'avant ANN-8, une forme changée) n'offre rien plutôt que tout. */
  function gestesOfferts(tag, peutModifier) {
    const remaniable = tag.remaniable === true;
    const inutilise = peutModifier === true && tag.frequence === 0;
    return {
      renommer: remaniable || inutilise,
      fusionner: remaniable,
      supprimer: remaniable || inutilise,
    };
  }

  /* Les tags dans lesquels celui-ci peut être fusionné : tout autre tag visible, global ou
     de la même collection, par ordre alphabétique. */
  function ciblesDeFusion(tag, tags) {
    return (tags || [])
      .filter((t) => t.id !== tag.id &&
        (t.collection_id == null || String(t.collection_id) === String(tag.collection_id)))
      .sort((a, b) => a.label.localeCompare(b.label, "fr"));
  }

  const INFOBULLES = {
    renommer: "Change le libellé du tag partout où il est posé.",
    fusionner: "Les régions qui portent ce tag porteront le tag choisi ; celui-ci disparaît.",
    supprimer: "Retire ce tag de toutes les régions qui le portent, puis le supprime.",
  };

  /* `rep` : la réponse de la route jouée à blanc. */
  function confirmerSuppression(rep) {
    const n = rep.regions || 0;
    return n === 0
      ? `Supprimer le tag « ${rep.label} » ? Aucune région ne le porte.`
      : `Supprimer le tag « ${rep.label} » ? Il sera retiré de ${nombre(n, "région", "régions")}.`;
  }

  function confirmerFusion(rep) {
    const n = rep.regions || 0, deja = rep.deja || 0, cible = rep.cible.label;
    if (n === 0) {
      return `Fusionner « ${rep.label} » dans « ${cible} » ? Aucune région ne porte ` +
             `« ${rep.label} » : il disparaîtra.`;
    }
    const portent = deja ? ` (${deja} ${deja > 1 ? "le portent" : "le porte"} déjà)` : "";
    return `Fusionner « ${rep.label} » dans « ${cible} » ? ` +
           `${nombre(n, "région passera", "régions passeront")} à « ${cible} »${portent}, ` +
           `et « ${rep.label} » disparaîtra.`;
  }

  /* `rep` : la réponse de la route qui a écrit. */
  function reussiteSuppression(rep) {
    const n = rep.regions || 0;
    return n === 0 ? `Tag « ${rep.label} » supprimé.`
      : `Tag « ${rep.label} » supprimé et retiré de ${nombre(n, "région", "régions")}.`;
  }

  function reussiteFusion(rep) {
    const n = rep.regions || 0;
    return `« ${rep.label} » fusionné dans « ${rep.cible.label} » ` +
           `(${nombre(n, "région", "régions")}).`;
  }

  function reussiteRenommage(avant, rep) {
    return `Tag « ${avant} » renommé « ${rep.label} ».`;
  }

  return { nombre, modifiable, gestesOfferts, ciblesDeFusion, INFOBULLES,
           confirmerSuppression, confirmerFusion, reussiteSuppression, reussiteFusion,
           reussiteRenommage };
});
