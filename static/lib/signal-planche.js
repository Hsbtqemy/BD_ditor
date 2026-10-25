/* Le SIGNAL de la planche ouverte (CONC-4) — logique PURE, sans DOM. Chargé en <script>
   AVANT viewer.js → expose `window.BDSignal` ; aussi require()-able par
   `tests/js/signal-planche.test.js`.

   Réécrit par Hugo le 2026-10-21 : ni temps réel ni rien — un SIGNAL. L'Atelier demande de
   temps en temps, et au retour sur l'onglet, l'empreinte de la planche ouverte
   (`GET /api/planches/{id}/empreinte` : une empreinte PAR RÉGION, cf. `empreinte.py`), la
   compare à celle qu'il avait, et propose « Actualiser » si quelque chose a changé AILLEURS
   — sans rien recharger d'office.

   Ce module décide trois choses, chacune vérifiable par une table de cas :
   - ce qu'une écriture de l'écran a TOUCHÉ (`regionsTouchees`), pour ne pas se signaler à
     lui-même ses propres gestes ;
   - ce qui a changé ailleurs entre deux empreintes (`comparer`), et la base à garder : une
     différence d'ailleurs RESTE dans la base tant qu'on n'a pas actualisé, si bien que le
     signal dure — et s'éteint de lui-même si l'autre revient exactement à ce qu'on voyait ;
   - ce que dit l'infobulle du bouton (`titre`).

   LIMITE ÉCRITE : une région que l'écran vient de toucher adopte sa nouvelle empreinte à la
   vérification suivante, et le changement qu'un AUTRE y aurait fait dans le même intervalle
   s'y fond. Sur le même champ, c'est le 409 de CONC-3 qui le dit à l'enregistrement ; sur un
   autre champ de la même région, rien jusqu'au prochain changement d'ailleurs. Et une
   écriture que ce module ne sait pas placer est réputée avoir tout touché (`tout`) :
   l'erreur va du côté du signal manqué, jamais du côté d'un signal faux. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDSignal = api;                                                   // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Trente secondes : assez pour qu'une modification d'ailleurs se signale pendant qu'on
     travaille sur la planche, assez peu pour ne pas peser — une lecture légère, suspendue
     quand l'onglet est caché, et refaite au retour. */
  const INTERVALLE_MS = 30000;

  /* Les écritures qui ne changent l'empreinte d'AUCUNE région : le registre des personnages
     (créer, renommer, son profil, ses alignements), le lexique, l'état d'une planche, la
     grammaire d'une région (elle n'entre pas dans l'empreinte), l'import de planches,
     ShareDocs et « Passer ce geste ». Tout le reste qui n'est pas placé plus bas vaut
     `tout`. */
  const SANS_EFFET = [
    /^\/api\/personnages(\?|$)/,                                   // POST : créer
    /^\/api\/personnages\/\d+(\?|$)/,                               // PUT : renommer
    /^\/api\/personnages\/\d+\/(attributs|alignements)(\/|\?|$)/,
    /\/lexique(\?|$)/,
    /^\/api\/attributs\/dimensions(\/\d+\/valeurs)?(\?|$)/,          // POST : créer
    /^\/api\/planches\/\d+\/(statut|relecture|validation|verrou|role)(\?|$)/,
    /^\/api\/regions\/\d+\/(tokens|grammaire)(\/|\?|$)/,
    /^\/api\/albums\/\d+\/import(\?|$)/,
    /^\/api\/sharedocs\//,
    /^\/api\/undo\/passer(\?|$)/,
  ];

  /* Ce qu'une écriture de l'écran a touché : `null` (rien), `{ tout: true }`, ou
     `{ ids: [...], sousArbre }` — `sousArbre` : la suppression d'une région emporte ses
     enfants, que l'appelant connaît (le module, lui, n'a pas l'arbre). `reponse` : le corps
     rendu, d'où vient l'identifiant d'une région CRÉÉE. */
  function regionsTouchees(methode, chemin, reponse, plancheId) {
    const m = String(methode || "GET").toUpperCase();
    if (m === "GET" || m === "HEAD") return null;
    const p = String(chemin || "").replace(/^https?:\/\/[^/]+/, "");
    // Supprimer un personnage emporte ses locuteurs et ses présences par cascade.
    if (m === "DELETE" && /^\/api\/personnages\/\d+(\?|$)/.test(p)) return { tout: true };
    if (SANS_EFFET.some((re) => re.test(p))) return null;
    // Monter / descendre échange le rang de deux sœurs : la voisine bouge aussi.
    if (/^\/api\/regions\/\d+\/deplacer(\?|$)/.test(p)) return { tout: true };
    const region = p.match(/^\/api\/regions\/(\d+)(\/[^?]*)?(\?|$)/);
    if (region) {
      return { ids: [Number(region[1])], sousArbre: m === "DELETE" && !region[2] };
    }
    const planche = p.match(/^\/api\/planches\/(\d+)\/regions(\?|$)/);
    if (planche && m === "POST") {
      if (Number(planche[1]) !== plancheId) return null;
      return reponse && reponse.id != null ? { ids: [Number(reponse.id)], sousArbre: false }
        : { tout: true };
    }
    return { tout: true };
  }

  /* `base`, `nouvelle` : { "<id de région>": empreinte }. `touchees` : { tout, ids:Set }.
     Rend { autres: { creees, modifiees, supprimees } (identifiants triés), base }. */
  function comparer(base, nouvelle, touchees) {
    const autres = { creees: [], modifiees: [], supprimees: [] };
    if (touchees && touchees.tout) return { autres, base: { ...nouvelle } };
    const ids = touchees && touchees.ids ? touchees.ids : new Set();
    const suite = {};
    for (const id of new Set([...Object.keys(base), ...Object.keys(nouvelle)])) {
      const avant = base[id], apres = nouvelle[id];
      if (avant === apres || ids.has(Number(id))) {
        if (apres !== undefined) suite[id] = apres;   // inchangée, ou touchée ici : adoptée
        continue;
      }
      if (avant === undefined) autres.creees.push(Number(id));
      else if (apres === undefined) autres.supprimees.push(Number(id));
      else autres.modifiees.push(Number(id));
      if (avant !== undefined) suite[id] = avant;     // l'écart reste jusqu'à « Actualiser »
    }
    for (const k of Object.keys(autres)) autres[k].sort((a, b) => a - b);
    return { autres, base: suite };
  }

  function nombre(autres) {
    return autres.creees.length + autres.modifiees.length + autres.supprimees.length;
  }

  /* L'infobulle du bouton : « La planche a changé ailleurs : 2 régions modifiées, 1 créée.
     Actualiser la recharge, sans perdre votre saisie. » Vide s'il n'y a rien. */
  function titre(autres) {
    const morceaux = [];
    for (const [cle, mot] of [["modifiees", "modifiée"], ["creees", "créée"],
                              ["supprimees", "supprimée"]]) {
      const n = autres[cle].length;
      if (!n) continue;
      const s = n > 1 ? "s" : "";
      morceaux.push(morceaux.length ? `${n} ${mot}${s}` : `${n} région${s} ${mot}${s}`);
    }
    if (!morceaux.length) return "";
    return `La planche a changé ailleurs : ${morceaux.join(", ")}. `
      + "Actualiser la recharge, sans perdre votre saisie.";
  }

  return { INTERVALLE_MS, regionsTouchees, comparer, nombre, titre };
});
