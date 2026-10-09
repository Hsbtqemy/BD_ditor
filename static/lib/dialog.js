/* Modale accessible — enveloppe RÉUTILISABLE pour les boîtes de dialogue (album,
   ShareDocs). Les scripts de page continuent d'ouvrir/fermer comme avant
   (`el.hidden = true/false`) ; ce helper OBSERVE l'attribut `hidden` et, sans rien
   changer à leur logique métier :
     • pose role="dialog" + aria-modal (+ nom accessible) sur la boîte ;
     • à l'ouverture, déplace le focus dans la boîte (sauf si la page l'a déjà placé) ;
     • PIÈGE le focus clavier (Tab / Maj+Tab bouclent dans la boîte) ;
     • ferme sur Échap ;
     • à la fermeture, REND le focus à l'élément d'où l'on venait (le déclencheur).
   Source unique → même comportement clavier/lecteur d'écran partout.
   UMD minimal (require()-able par les tests Node, comme nav.js) : aucun accès au DOM
   au chargement, uniquement à l'appel de register(). Cf. docs/navigation-round-trip.md. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDDialog = api;                                                   // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Éléments potentiellement focusables au clavier.
     `summary` y manquait, et un `<summary>` est focalisable SANS `tabindex` : chaque terme
     du lexique en est un (`<details><summary>`). Seul le PREMIER `<summary>` enfant direct
     d'un `<details>` l'est — d'où le sélecteur —, et le contenu d'un `<details>` fermé
     n'est pas rendu : `focusables()` l'écarte déjà par `getClientRects`.
     Cette liste n'a pas à être complète pour que le piège tienne (cf. `trapTarget`) ; elle
     doit l'être pour que le focus d'OUVERTURE et les deux bords tombent juste. Les sept
     modales de l'application ne portent aucun autre focalisable natif — ni
     `contenteditable`, ni `iframe`, ni média à commandes : on ne l'allonge pas pour des
     cas qui n'existent pas ici. */
  var FOCUSABLE =
    'a[href],button:not([disabled]),input:not([disabled]),' +
    'select:not([disabled]),textarea:not([disabled]),' +
    'details > summary:first-of-type,' +
    '[tabindex]:not([tabindex="-1"])';

  /* Cible du focus quand Tab boucle dans une modale — LOGIQUE PURE (testée sous Node) :
     `list` = focusables visibles dans l'ordre du DOM, `active` = focus courant,
     `shift` = Maj enfoncé, `precede(a, b)` = « a vient avant b dans le document ».
     Renvoie l'élément à focaliser, ou null si Tab doit suivre son cours normal
     (déplacement interne sans franchir les bords).

     **Un focus que la liste ne connaît pas n'est PAS un focus perdu.** La règle d'avant
     renvoyait au premier élément dès que `active` n'était pas dans la liste, et c'est elle
     qui a fait d'un oubli de sélecteur un cul-de-sac : arrivé sur le premier `<summary>`
     du lexique, Tab repartait au début, et tout ce qui suivait — les autres termes,
     l'import, « Fermer » — ne s'atteignait plus au clavier (mesuré le 2026-10-09).
     Désormais on regarde OÙ il est : s'il reste un élément connu devant lui dans le sens
     de la marche, Tab suit son cours — il ne peut alors pas quitter la boîte, puisqu'il
     rencontrera cet élément-là au plus tard. Ce n'est qu'au-delà du dernier connu (ou en
     deçà du premier) qu'on boucle. Sans `precede`, on ne sait pas situer le focus, et on
     garde la règle prudente : l'extrémité d'entrée. */
  function trapTarget(list, active, shift, precede) {
    if (!list.length) return null;
    var first = list[0], last = list[list.length - 1];
    if (list.indexOf(active) !== -1) {
      if (shift) return active === first ? last : null;   // recule depuis le 1er → dernier
      return active === last ? first : null;              // avance depuis le dernier → 1er
    }
    if (!precede) return shift ? last : first;
    if (shift) return precede(first, active) ? null : last;
    return precede(active, last) ? null : first;
  }

  /* `a` vient-il avant `b` dans le document ? Un conteneur PRÉCÈDE ce qu'il contient :
     c'est ce qui fait entrer Tab dans la boîte quand le focus est sur elle. */
  function precede(a, b) {
    return !!(a.compareDocumentPosition(b) & 4);   // Node.DOCUMENT_POSITION_FOLLOWING
  }

  var roots = [];                 // conteneurs enregistrés (pour reconnaître « hors modale »)
  var lastExternalFocus = null;   // dernier focus HORS de toute modale = cible du retour
  var tracking = false;

  function insideAnyDialog(node) {
    return roots.some(function (r) { return r.contains(node); });
  }

  // Visible ET disposé (getClientRects = 0 si display:none — p.ex. un sous-panneau
  // [hidden] de ShareDocs), dans l'ordre du DOM.
  function focusables(box) {
    return Array.prototype.filter.call(
      box.querySelectorAll(FOCUSABLE),
      function (el) { return el.getClientRects().length > 0; }
    );
  }

  function canFocus(el) {
    return !!el && el.isConnected && el.getClientRects().length > 0;
  }

  function register(toggleEl, opts) {
    opts = opts || {};

    // Suivi global du focus « extérieur » — installé une seule fois.
    if (!tracking) {
      document.addEventListener("focusin", function (e) {
        if (!insideAnyDialog(e.target)) lastExternalFocus = e.target;
      });
      tracking = true;
    }
    roots.push(toggleEl);

    // La boîte (role=dialog + piège) peut être un descendant de l'élément basculé
    // (ShareDocs : overlay #sharedocs ⊃ boîte .sd-dialog).
    var box = opts.box ? (toggleEl.querySelector(opts.box) || toggleEl) : toggleEl;
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    if (opts.labelledby) box.setAttribute("aria-labelledby", opts.labelledby);
    else if (opts.label) box.setAttribute("aria-label", opts.label);

    var close = opts.onClose || function () { toggleEl.hidden = true; };

    // Échap ferme · Tab/Maj+Tab bouclent. Écouteur sur l'élément basculé : les
    // événements clavier de la boîte y remontent ; stopPropagation évite que les
    // gestionnaires globaux (raccourcis, fermeture des dropdowns) ne s'en mêlent.
    toggleEl.addEventListener("keydown", function (e) {
      if (toggleEl.hidden) return;
      // stopPropagation : neutralise les raccourcis/fermetures de menus globaux. Pas
      // de preventDefault — Échap n'a pas d'action par défaut utile et le supprimer
      // gênerait la fermeture du popup natif d'un <select> (ex. #sd-album).
      if (e.key === "Escape") { e.stopPropagation(); close(); return; }
      if (e.key !== "Tab") return;
      var f = focusables(box);
      if (!f.length) { e.preventDefault(); return; }   // rien à focaliser : on ne s'échappe pas
      var t = trapTarget(f, document.activeElement, e.shiftKey, precede);
      if (t) { t.focus(); e.preventDefault(); }
    });

    // Bascule de `hidden`, peu importe qui la déclenche (bouton, clic sur le fond,
    // code) : ouverture → focus dans la boîte (sauf si la page l'a déjà posé) ;
    // fermeture → focus rendu à l'élément d'origine.
    var wasOpen = !toggleEl.hidden;
    function onToggle() {
      var open = !toggleEl.hidden;
      if (open === wasOpen) return;
      wasOpen = open;
      if (open) {
        if (!box.contains(document.activeElement)) {
          var f = focusables(box);
          if (f.length) f[0].focus();
        }
      } else if (canFocus(lastExternalFocus)) {
        lastExternalFocus.focus();
      }
    }
    new MutationObserver(onToggle)
      .observe(toggleEl, { attributes: true, attributeFilter: ["hidden"] });
    if (wasOpen) onToggle();   // déjà ouverte au câblage (rare) : pose le focus
  }

  return { register: register, _trapTarget: trapTarget };
});
