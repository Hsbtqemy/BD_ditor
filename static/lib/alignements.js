/* L'ALIGNEMENT D'AUTORITÉ d'un personnage (A5) — COMMUN à l'Atelier (le panneau Personnage,
   atteint par le locuteur et par la boîte) et à la page Annotation (la fiche d'un personnage,
   ANN-7 : une condition du retrait du mode Annotation de l'Atelier). Sorti de `viewer.js`
   (`makeAlignementWidget`) pour ne pas être recopié, comme `champ-personnage.js`.
   Chargé en <script> → `window.BDAlignements` ; require()-able par
   `tests/js/alignements.test.js`. Rien n'est lu au chargement : le document et les aides de
   `common.js` (`apiGet`, `apiSend`, `toast`, `escapeHtml`) ne servent qu'à l'appel — l'hôte
   peut les PASSER (`env`), sinon ce sont les globales de la page.

   Ce qui suit est le commentaire d'origine, inchangé :

   Widget réutilisable — relie l'ENTITÉ personnage à des référentiels externes
   (Wikidata/VIAF/IdRef…) en `skos:exactMatch`. Saisir une URI l'ajoute (source auto-détectée
   côté serveur) ; les puces ouvrent le référentiel / se retirent.

   Deux ajouts, sans rien changer à ce que l'Atelier montre :
   - `env.ecrit` (une fonction), absent par défaut : faux, ni ✕ ni champ — la page Annotation
     ne propose d'écrire que sur un album où l'on écrit, comme le reste de son Contexte. Sans
     elle, le widget offre toujours d'écrire, comme dans l'Atelier ; le serveur tranche.
   - Une lecture revenue après une PLUS RÉCENTE (un autre personnage chargé entre-temps, ou
     une autre lecture du même) n'écrit rien : la liste d'un personnage ne s'affiche jamais
     sous un autre. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module !== "undefined" && module.exports) module.exports = api;   // Node (tests)
  else root.BDAlignements = api;                                               // navigateur
})(typeof self !== "undefined" ? self : this, function (root) {
  "use strict";

  /* Les aides de la page, lues à l'APPEL (jamais au chargement) ; l'hôte peut les passer. */
  function outils(env) {
    const e = env || {};
    const g = (nom) => (e[nom] !== undefined ? e[nom] : root ? root[nom] : undefined);
    return {
      apiGet: g("apiGet"), apiSend: g("apiSend"), toast: g("toast"),
      escapeHtml: g("escapeHtml"),
      document: e.document || (typeof document !== "undefined" ? document : null),
    };
  }

  function element(x, doc) {
    return typeof x === "string" ? doc.querySelector(x) : x;
  }

  /* MONTER le widget sur `ids` : `section` (montrée dès qu'un personnage est chargé),
     `current` (les puces), `input` (la saisie d'une URI), et, facultatif, `saisie` (ce qui se
     cache avec le champ quand on n'écrit pas ; le champ lui-même par défaut). Rend
     `{ load(personnageId) }` : null cache la section. */
  function monter(ids, env) {
    // Les aides se relisent à CHAQUE appel, comme les globales nues d'avant : une page qui
    // enveloppe `apiSend` après le montage (pour noter ses propres écritures) est suivie.
    const o = () => outils(env);
    const apiGet = (...a) => o().apiGet(...a);
    const apiSend = (...a) => o().apiSend(...a);
    const toast = (...a) => o().toast.apply(null, a);
    const escapeHtml = (t) => o().escapeHtml(t);
    const doc = o().document;
    const sec = element(ids.section, doc), cur = element(ids.current, doc);
    const input = element(ids.input, doc);
    const saisie = ids.saisie ? element(ids.saisie, doc) : input;
    const ecrit = () => !(env && typeof env.ecrit === "function") || !!env.ecrit();
    let pid = null;
    let tour = 0;                       // la lecture la plus récente gagne
    async function refresh() {
      const moi = ++tour;
      cur.innerHTML = "";
      let items = [];
      try { items = await apiGet(`/api/personnages/${pid}/alignements`); } catch (e) { return; }
      if (moi !== tour) return;
      cur.innerHTML = "";
      if (!items.length) { cur.innerHTML = '<span class="muted small">Aucun</span>'; return; }
      const retirable = ecrit();
      for (const a of items) {
        const chip = doc.createElement("span");
        chip.className = "tag-chip";
        const lbl = a.source ? escapeHtml(a.source) : "lien";
        chip.innerHTML =
          `<a href="${escapeHtml(a.uri)}" target="_blank" rel="noopener noreferrer" `
          + `title="${escapeHtml(a.uri)}">${lbl} ↗</a>`
          + (retirable ? `<span class="x" title="Retirer l'alignement">×</span>` : "");
        if (retirable) chip.querySelector(".x").onclick = () => remove(a.id);
        cur.appendChild(chip);
      }
    }
    async function remove(aid) {
      try { await apiSend("DELETE", `/api/personnages/${pid}/alignements/${aid}`); }
      catch (e) { toast("Alignement : " + e.message, "error"); return; }
      refresh();
    }
    async function add() {
      const uri = input.value.trim();
      if (!uri) return;
      try { await apiSend("POST", `/api/personnages/${pid}/alignements`, { uri }); input.value = ""; refresh(); }
      catch (e) { toast("Alignement : " + e.message, "error"); }
    }
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); add(); } });
    return {
      load(personnageId) {
        pid = personnageId;
        if (!personnageId) { tour++; sec.hidden = true; return; }
        sec.hidden = false; input.value = "";
        saisie.hidden = !ecrit();
        refresh();
      },
    };
  }

  return { monter };
});
