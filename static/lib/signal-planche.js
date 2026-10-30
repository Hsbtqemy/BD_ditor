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
   l'erreur va du côté du signal manqué, jamais du côté d'un signal faux.

   LA PAGE ANNOTATION (ANN-7, tranche 2) s'en sert aussi, avec l'empreinte des RELEVÉS que la
   route rend à part (`releves` : une clé par zone qui porte un relevé ou une passe, et
   « planche » pour la surface). `cles` les réunit aux régions sous des clés `releves:<id>`
   et `releves:planche` ; une écriture sur un relevé, un doute ou une passe touche la zone
   du relevé, que la page connaît (`ou`). Toucher une région touche aussi ses relevés, et
   l'inverse : la limite écrite plus haut vaut pour les deux. L'Atelier ne lit que les
   régions : un relevé posé ailleurs ne lui signale rien, puisqu'il n'en montre rien. */
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
  function regionsTouchees(methode, chemin, reponse, plancheId, ou) {
    const m = String(methode || "GET").toUpperCase();
    if (m === "GET" || m === "HEAD") return null;
    const p = String(chemin || "").replace(/^https?:\/\/[^/]+/, "");
    const releve = releveTouche(m, p, reponse, plancheId, ou);
    if (releve !== undefined) return releve;
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

  /* Une écriture sur un relevé, un doute ou une passe de PLANCHE (la page Annotation) : la
     zone qu'elle touche, `{ ids: [région] }` ou `{ ids: [], planche: true }` pour la
     surface ; `{ tout: true }` quand on ne sait pas la placer ; `undefined` pour une
     écriture qui n'est pas de cette sorte. `ou(sorte, id)` — `sorte` : « releve » ou
     « doute » — rend `{ region_id, planche_id }` d'après ce que l'écran a lu, ou `null`. */
  function zoneDe(x) {
    if (!x) return null;
    if (x.region_id !== null && x.region_id !== undefined) return { ids: [Number(x.region_id)], sousArbre: false };
    if (x.planche_id !== null && x.planche_id !== undefined) return { ids: [], sousArbre: false, planche: true };
    return null;
  }

  function releveTouche(m, p, reponse, plancheId, ou) {
    const lire = (sorte, id) => (typeof ou === "function" ? ou(sorte, id) : null);
    const tout = { tout: true };
    if (/^\/api\/releves(\?|$)/.test(p)) return m === "POST" ? zoneDe(reponse) || tout : tout;
    const r = p.match(/^\/api\/releves\/(\d+)(\/doutes)?(\?|$)/);
    if (r) return zoneDe(reponse && !r[2] ? reponse : null) || zoneDe(lire("releve", Number(r[1]))) || tout;
    const d = p.match(/^\/api\/doutes\/(\d+)\/(messages|levee)(\?|$)/);
    if (d) {
      return zoneDe(reponse && reponse.releve_id != null ? lire("releve", Number(reponse.releve_id)) : null)
        || zoneDe(lire("doute", Number(d[1]))) || tout;
    }
    const pl = p.match(/^\/api\/planches\/(\d+)\/passes\//);
    if (pl) return Number(pl[1]) === plancheId ? { ids: [], sousArbre: false, planche: true } : null;
    return undefined;
  }

  /* Les clés d'une empreinte pour la page Annotation : les régions, et les relevés de chaque
     zone sous `releves:<id>` (`releves:planche` pour la surface). */
  const PREFIXE = "releves:";
  function cles(reponse) {
    const out = { ...((reponse && reponse.regions) || {}) };
    for (const [k, v] of Object.entries((reponse && reponse.releves) || {})) out[PREFIXE + k] = v;
    return out;
  }

  /* Une clé est-elle touchée ? Une région l'est par son identifiant ; les relevés d'une zone,
     par l'identifiant de la zone, ou par `planche` pour la surface. */
  function touchee(cle, touchees) {
    const ids = touchees && touchees.ids ? touchees.ids : new Set();
    if (!String(cle).startsWith(PREFIXE)) return ids.has(Number(cle));
    const reste = String(cle).slice(PREFIXE.length);
    return reste === "planche" ? !!(touchees && touchees.planche) : ids.has(Number(reste));
  }

  /* Une région se nomme par son identifiant (un nombre) ; les relevés d'une zone, par leur clé. */
  const nom = (cle) => (String(cle).startsWith(PREFIXE) ? String(cle) : Number(cle));
  const ordre = (a, b) => (typeof a === typeof b ? (typeof a === "number" ? a - b : a < b ? -1 : a > b ? 1 : 0)
    : typeof a === "number" ? -1 : 1);

  /* `base`, `nouvelle` : { "<id de région>": empreinte }. `touchees` : { tout, ids:Set }.
     Rend { autres: { creees, modifiees, supprimees } (identifiants triés), base }. */
  function comparer(base, nouvelle, touchees) {
    const autres = { creees: [], modifiees: [], supprimees: [] };
    if (touchees && touchees.tout) return { autres, base: { ...nouvelle } };
    const suite = {};
    for (const id of new Set([...Object.keys(base), ...Object.keys(nouvelle)])) {
      const avant = base[id], apres = nouvelle[id];
      if (avant === apres || touchee(id, touchees)) {
        if (apres !== undefined) suite[id] = apres;   // inchangée, ou touchée ici : adoptée
        continue;
      }
      if (avant === undefined) autres.creees.push(nom(id));
      else if (apres === undefined) autres.supprimees.push(nom(id));
      else autres.modifiees.push(nom(id));
      if (avant !== undefined) suite[id] = avant;     // l'écart reste jusqu'à « Actualiser »
    }
    for (const k of Object.keys(autres)) autres[k].sort(ordre);
    return { autres, base: suite };
  }

  function nombre(autres) {
    return autres.creees.length + autres.modifiees.length + autres.supprimees.length;
  }

  /* L'infobulle du bouton : « La planche a changé ailleurs : 2 régions modifiées, 1 créée.
     Actualiser la recharge, sans perdre votre saisie. » Vide s'il n'y a rien. */
  function titre(autres) {
    const morceaux = [];
    const regions = (l) => l.filter((x) => typeof x === "number");
    for (const [cle, mot] of [["modifiees", "modifiée"], ["creees", "créée"],
                              ["supprimees", "supprimée"]]) {
      const n = regions(autres[cle]).length;
      if (!n) continue;
      const s = n > 1 ? "s" : "";
      morceaux.push(morceaux.length ? `${n} ${mot}${s}` : `${n} région${s} ${mot}${s}`);
    }
    // Les relevés (la page Annotation) : sur combien de zones ils ont changé.
    const zones = new Set(["creees", "modifiees", "supprimees"]
      .flatMap((k) => autres[k].filter((x) => typeof x !== "number")));
    if (zones.size) {
      morceaux.push(`des relevés sur ${zones.size} zone${zones.size > 1 ? "s" : ""}`);
    }
    if (!morceaux.length) return "";
    return `La planche a changé ailleurs : ${morceaux.join(", ")}. `
      + "Actualiser la recharge, sans perdre votre saisie.";
  }

  return { INTERVALLE_MS, regionsTouchees, comparer, nombre, titre, cles, PREFIXE };
});
