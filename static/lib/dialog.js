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

  // Éléments potentiellement focusables au clavier.
  var FOCUSABLE =
    'a[href],button:not([disabled]),input:not([disabled]),' +
    'select:not([disabled]),textarea:not([disabled]),' +
    '[tabindex]:not([tabindex="-1"])';

  /* Cible du focus quand Tab boucle dans une modale — LOGIQUE PURE (testée sous Node) :
     `list` = focusables visibles dans l'ordre du DOM, `active` = focus courant,
     `shift` = Maj enfoncé. Renvoie l'élément à focaliser, ou null si Tab doit suivre
     son cours normal (déplacement interne sans franchir les bords). */
  function trapTarget(list, active, shift) {
    if (!list.length) return null;
    var first = list[0], last = list[list.length - 1];
    var inside = list.indexOf(active) !== -1;
    if (shift) return (active === first || !inside) ? last : null;   // recule depuis le 1er → dernier
    return (active === last || !inside) ? first : null;              // avance depuis le dernier → 1er
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
      var t = trapTarget(f, document.activeElement, e.shiftKey);
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
