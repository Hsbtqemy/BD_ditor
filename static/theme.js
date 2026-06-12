/* Bascule de thème clair/sombre — partagée par les 3 pages.
   - applique le thème AVANT le rendu (script en <head>) → aucun flash ;
   - suit la préférence système tant que l'utilisateur n'a pas tranché ;
   - mémorise le choix explicite (localStorage) et câble le(s) bouton(s) .btn-theme. */
(function () {
  "use strict";
  var KEY = "bd-theme";
  var mq = window.matchMedia("(prefers-color-scheme: light)");
  var root = document.documentElement;

  function stored() {
    var v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  }
  function apply(theme) { root.dataset.theme = theme; }

  // 1) Appliqué immédiatement (pas de FOUC) : choix explicite, sinon système.
  apply(stored() || (mq.matches ? "light" : "dark"));

  function syncButtons() {
    var dark = root.dataset.theme === "dark";
    document.querySelectorAll(".btn-theme").forEach(function (b) {
      b.textContent = dark ? "☀️" : "🌙";
      b.title = dark ? "Passer au thème clair" : "Passer au thème sombre";
      b.setAttribute("aria-label", b.title);
    });
  }
  function toggle() {
    var next = root.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem(KEY, next);
    apply(next);
    syncButtons();
  }

  // 2) Suit l'OS tant qu'aucun choix explicite n'a été mémorisé.
  mq.addEventListener("change", function () {
    if (!stored()) { apply(mq.matches ? "light" : "dark"); syncButtons(); }
  });

  // 3) Câblage du/des bouton(s) une fois le DOM prêt.
  function wire() {
    document.querySelectorAll(".btn-theme").forEach(function (b) {
      b.addEventListener("click", toggle);
    });
    syncButtons();
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", wire);
  else wire();
})();
