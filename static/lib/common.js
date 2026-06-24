/* Helpers communs aux 4 surfaces (Visionneuse / Recherche / Corpus / Exploration).
   Chargé en <script> AVANT le script de page → expose les helpers en GLOBALS, pour
   que les appels nus restent inchangés : `$`, `apiGet`, `apiSend`, `escapeHtml`
   (alias `esc`), `toast`. Aussi require()-able par les tests Node (UMD, pas de build) :
   seule la logique pure (escapeHtml) y est testée — les autres ne touchent DOM/fetch
   qu'à l'APPEL, pas au chargement. Cf. QA-2 (docs/backlog.md §7). */
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

  /* GET JSON ; lève une Error portant le `detail` de l'API (ou statusText). */
  async function apiGet(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
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
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
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

  return { $, apiGet, apiSend, escapeHtml, toast };
});
