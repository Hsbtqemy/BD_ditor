/* Helpers communs aux 4 surfaces (Visionneuse / Recherche / Corpus / Exploration).
   Chargé en <script> AVANT le script de page → expose les helpers en GLOBALS, pour
   que les appels nus restent inchangés : `$`, `apiGet`, `apiSend`, `escapeHtml`
   (alias `esc`), `toast`. Aussi require()-able par les tests Node (UMD, pas de build) :
   seule la logique pure (escapeHtml, messageErreur) y est testée — les autres
   ne touchent DOM/fetch qu'à l'APPEL, pas au chargement. Cf. QA-2.
   (docs/backlog.md §7 ; le suivi vit désormais dans pilotage/). */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;                 // Node (tests)
  } else {                                // navigateur : globals (appels nus inchangés)
    root.$ = api.$;
    root.apiGet = api.apiGet;
    root.apiSend = api.apiSend;
    root.escapeHtml = api.escapeHtml;
    root.esc = api.escapeHtml;            // alias historique (corpus / exploration)
    root.toast = api.toast;
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Échappe les métacaractères HTML. `?? ""` : null/undefined → "" (jamais le
     littéral « null »/« undefined » injecté dans le HTML). */
  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  /* Raccourci querySelector (document interrogé à l'APPEL). */
  const $ = (sel) => document.querySelector(sel);

  /* Le message de Pydantic est en ANGLAIS, et tout ce projet est en français. On
     traduit les contraintes que cette application produit réellement, et on retombe
     sur le texte d'origine pour les autres : une table exhaustive se périmerait en
     silence à la première version de la bibliothèque, un texte anglais reste lisible.
     `ctx` porte la borne, qui est ce que la personne a besoin de savoir. */
  function phrase(e) {
    const ctx = (e && e.ctx) || {};
    switch (e && e.type) {
      case "greater_than_equal": return "doit valoir au moins " + ctx.ge;
      case "less_than_equal":    return "doit valoir au plus " + ctx.le;
      case "greater_than":       return "doit dépasser " + ctx.gt;
      case "less_than":          return "doit rester sous " + ctx.lt;
      case "missing":            return "champ obligatoire";
      case "int_parsing":        return "nombre entier attendu";
      default:                   return (e && e.msg) || "valeur refusée";
    }
  }

  /* Le message d'erreur QU'ON MONTRE, à partir du corps de la réponse.

     Les refus métier de l'app posent `detail` en CHAÎNE, écrite en français et
     destinée à être lue telle quelle. Mais une erreur de VALIDATION (422) vient de
     FastAPI, et son `detail` est une LISTE d'objets : `new Error(liste)` affichait
     alors « [object Object] », c'est-à-dire rien, précisément à qui vient de taper
     une valeur refusée. Le défaut dormait tant qu'aucun champ de formulaire n'était
     borné ; borner `annee` (E3) l'a rendu atteignable par une simple faute de frappe. */
  function messageErreur(corps, statusText) {
    const d = corps && corps.detail;
    if (typeof d === "string" && d) return d;
    if (Array.isArray(d) && d.length) {
      return d.map((e) => {
        // `loc` = ["body", "annee"] : le dernier segment NOMME le champ fautif, et
        // c'est la seule part que l'utilisateur peut relier à ce qu'il a saisi.
        const champ = Array.isArray(e.loc) && e.loc.length ? e.loc[e.loc.length - 1] : null;
        return champ ? champ + " : " + phrase(e) : phrase(e);
      }).join(" · ");
    }
    return statusText;
  }

  /* GET JSON ; lève une Error portant le message lisible du refus. */
  async function apiGet(path) {
    const r = await fetch(path);
    if (!r.ok) {
      throw new Error(messageErreur(await r.json().catch(() => ({})), r.statusText));
    }
    return r.json();
  }

  /* POST/PUT/DELETE JSON. `opts.signal` : AbortController optionnel (annulation).
     204 → null (pas de corps à parser). */
  async function apiSend(method, path, body, opts = {}) {
    const r = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: opts.signal,
    });
    if (!r.ok) {
      throw new Error(messageErreur(await r.json().catch(() => ({})), r.statusText));
    }
    return r.status === 204 ? null : r.json();
  }

  /* Toast accessible (role=status / aria-live=polite), auto-effacé après 4 s. Le
     conteneur #toasts est créé à la demande puis réutilisé. */
  function toast(msg, kind = "") {
    let box = document.getElementById("toasts");
    if (!box) {
      box = document.createElement("div");
      box.id = "toasts";
      box.setAttribute("role", "status");
      box.setAttribute("aria-live", "polite");
      document.body.appendChild(box);
    }
    const el = document.createElement("div");
    el.className = "toast " + kind;
    el.textContent = msg;
    box.appendChild(el);
    setTimeout(() => el.remove(), 4000);
  }

  return { $, apiGet, apiSend, escapeHtml, toast, messageErreur };
});
