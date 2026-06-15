/* Réglages d'affichage partagés par les 4 surfaces — thème (clair/sombre),
   contraste élevé, zoom UI. Appliqués AVANT le rendu (script en <head>) → aucun flash.
   Suit les préférences système (prefers-color-scheme, prefers-contrast) tant que
   l'utilisateur n'a pas tranché ; mémorise les choix (localStorage). Le menu « Aa »
   est injecté dans chaque .btn-theme → présent partout, source unique, sans toucher
   aux templates. */
(function () {
  "use strict";
  var root = document.documentElement;
  var KEY = { theme: "bd-theme", contrast: "bd-contrast", zoom: "bd-zoom" };
  var mqLight = window.matchMedia("(prefers-color-scheme: light)");
  var mqContrast = window.matchMedia("(prefers-contrast: more)");

  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function put(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  function curTheme() {
    var v = get(KEY.theme);
    return (v === "light" || v === "dark") ? v : (mqLight.matches ? "light" : "dark");
  }
  function curContrast() {
    var v = get(KEY.contrast);
    if (v === "high" || v === "normal") return v;
    return mqContrast.matches ? "high" : "normal";
  }
  function curZoom() {
    var z = parseFloat(get(KEY.zoom));
    return (z >= 0.8 && z <= 2.0) ? z : 1;
  }

  function applyTheme(t) { root.dataset.theme = t; }
  function applyContrast(c) {
    if (c === "high") root.dataset.contrast = "high"; else delete root.dataset.contrast;
  }
  function applyZoom(z) { root.style.zoom = z === 1 ? "" : String(z); }

  // 1) Application immédiate (pas de FOUC).
  applyTheme(curTheme());
  applyContrast(curContrast());
  applyZoom(curZoom());

  // 2) Suit l'OS tant qu'aucun choix explicite n'a été mémorisé.
  mqLight.addEventListener("change", function () { if (!get(KEY.theme)) { applyTheme(curTheme()); sync(); } });
  mqContrast.addEventListener("change", function () { if (!get(KEY.contrast)) { applyContrast(curContrast()); sync(); } });

  var menus = [];

  function sync() {
    var light = root.dataset.theme === "light";
    var high = root.dataset.contrast === "high";
    var z = curZoom();
    menus.forEach(function (m) {
      m.cb.checked = high;
      m.zoomVal.textContent = Math.round(z * 100) + " %";
      m.bL.setAttribute("aria-pressed", String(light));
      m.bD.setAttribute("aria-pressed", String(!light));
    });
  }

  function setTheme(t) { put(KEY.theme, t); applyTheme(t); sync(); }
  function setContrast(h) { put(KEY.contrast, h ? "high" : "normal"); applyContrast(h ? "high" : "normal"); sync(); }
  function setZoom(z) {
    z = Math.min(2.0, Math.max(0.8, Math.round(z * 10) / 10));
    put(KEY.zoom, String(z)); applyZoom(z); sync();
  }

  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }

  // Transforme un bouton .btn-theme existant en déclencheur du menu « Affichage ».
  function buildMenu(btn) {
    var wrap = el("span", "display-menu");
    btn.parentNode.insertBefore(wrap, btn);
    btn.textContent = "Aa";
    btn.title = "Affichage (thème, contraste, zoom)";
    btn.setAttribute("aria-haspopup", "true");
    btn.setAttribute("aria-expanded", "false");
    btn.setAttribute("aria-label", "Réglages d'affichage");
    wrap.appendChild(btn);

    var panel = el("div", "display-panel");
    panel.hidden = true;
    panel.setAttribute("aria-label", "Réglages d'affichage");

    var rT = el("div", "dm-row"); rT.appendChild(el("span", "dm-label", "Thème"));
    var bL = el("button", "ghost small", "Clair"); var bD = el("button", "ghost small", "Sombre");
    bL.onclick = function () { setTheme("light"); }; bD.onclick = function () { setTheme("dark"); };
    rT.appendChild(bL); rT.appendChild(bD); panel.appendChild(rT);

    var rC = el("label", "dm-row dm-check");
    var cb = el("input"); cb.type = "checkbox";
    cb.onchange = function () { setContrast(cb.checked); };
    rC.appendChild(cb); rC.appendChild(el("span", null, "Contraste élevé")); panel.appendChild(rC);

    var rZ = el("div", "dm-row"); rZ.appendChild(el("span", "dm-label", "Zoom"));
    var zM = el("button", "ghost small", "A−"); var zV = el("span", "dm-zoom-val");
    var zP = el("button", "ghost small", "A+"); var zR = el("button", "ghost small", "↺");
    zM.setAttribute("aria-label", "Réduire le zoom");
    zP.setAttribute("aria-label", "Augmenter le zoom");
    zR.setAttribute("aria-label", "Zoom 100 %");
    zM.onclick = function () { setZoom(curZoom() - 0.1); };
    zP.onclick = function () { setZoom(curZoom() + 0.1); };
    zR.onclick = function () { setZoom(1); };
    rZ.appendChild(zM); rZ.appendChild(zV); rZ.appendChild(zP); rZ.appendChild(zR); panel.appendChild(rZ);

    wrap.appendChild(panel);

    function open(o) { panel.hidden = !o; btn.setAttribute("aria-expanded", String(o)); }
    btn.addEventListener("click", function (e) { e.stopPropagation(); open(panel.hidden); });
    panel.addEventListener("click", function (e) { e.stopPropagation(); });
    document.addEventListener("click", function () { open(false); });
    // Échap ferme ET rend le focus au déclencheur (sinon il se perd, le panneau passant
    // en display:none) — important pour la navigation clavier.
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !panel.hidden) { open(false); btn.focus(); }
    });

    menus.push({ cb: cb, zoomVal: zV, bL: bL, bD: bD });
  }

  /* ---- Accessibilité transverse (ARIA ciblé, invisible) ---- */
  // Boutons-icônes : recopie le `title` en `aria-label` (lecteurs d'écran), seulement
  // si l'élément n'a pas de texte LISIBLE (que des symboles/emoji) → n'altère pas les
  // boutons textuels. Couvre le statique ET le dynamique (rendus JS) via un observer.
  function reflectAria(el) {
    if ((el.tagName === "BUTTON" || el.tagName === "A") && el.title &&
        !el.getAttribute("aria-label") && !/\p{L}/u.test(el.textContent || "")) {
      el.setAttribute("aria-label", el.title);
    }
  }
  function reflectIn(node) {
    if (node.nodeType !== 1) return;
    reflectAria(node);
    if (node.querySelectorAll) node.querySelectorAll("button[title], a[title]").forEach(reflectAria);
  }

  function a11y() {
    reflectIn(document.body);
    new MutationObserver(function (muts) {
      muts.forEach(function (m) { m.addedNodes.forEach(reflectIn); });
    }).observe(document.body, { childList: true, subtree: true });

    // Repère de navigation : le groupe liens/réglages de l'en-tête.
    var ha = document.querySelector(".header-actions");
    if (ha && !ha.getAttribute("role")) {
      ha.setAttribute("role", "navigation");
      ha.setAttribute("aria-label", "Navigation et réglages");
    }

    // Lien d'évitement « Aller au contenu » + cible focusable (clavier / lecteur d'écran).
    var main = document.querySelector("main");
    if (main && !document.querySelector(".skip-link")) {
      if (!main.id) main.id = "contenu";
      if (!main.hasAttribute("tabindex")) main.setAttribute("tabindex", "-1");
      var skip = el("a", "skip-link"); skip.href = "#" + main.id; skip.textContent = "Aller au contenu";
      skip.addEventListener("click", function () { setTimeout(function () { main.focus(); }, 0); });
      document.body.insertBefore(skip, document.body.firstChild);
    }
  }

  function wire() {
    document.querySelectorAll(".btn-theme").forEach(buildMenu);
    sync();
    a11y();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();
})();
