/* Réglages d'affichage partagés par les 4 surfaces — thème (clair/sombre),
   contraste élevé, zoom UI. Appliqués AVANT le rendu (script en <head>) → aucun flash.
   Suit les préférences système (prefers-color-scheme, prefers-contrast) tant que
   l'utilisateur n'a pas tranché ; mémorise les choix (localStorage). Le menu « Aa »
   est injecté dans chaque .btn-theme → présent partout, source unique, sans toucher
   aux templates. */
(function () {
  "use strict";
  var root = document.documentElement;
  var KEY = { theme: "bd-theme", contrast: "bd-contrast", zoom: "bd-zoom", lecture: "bd-lecture" };
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
  // Pas de préférence système pour le confort de lecture → « normal » par défaut.
  function curLecture() { return get(KEY.lecture) === "confort" ? "confort" : "normal"; }

  function applyTheme(t) { root.dataset.theme = t; }
  function applyContrast(c) {
    if (c === "high") root.dataset.contrast = "high"; else delete root.dataset.contrast;
  }
  function applyZoom(z) { root.style.zoom = z === 1 ? "" : String(z); }
  function applyLecture(v) {
    if (v === "confort") root.dataset.lecture = "confort"; else delete root.dataset.lecture;
  }

  // 1) Application immédiate (pas de FOUC).
  applyTheme(curTheme());
  applyContrast(curContrast());
  applyZoom(curZoom());
  applyLecture(curLecture());

  // 2) Suit l'OS tant qu'aucun choix explicite n'a été mémorisé.
  mqLight.addEventListener("change", function () { if (!get(KEY.theme)) { applyTheme(curTheme()); sync(); } });
  mqContrast.addEventListener("change", function () { if (!get(KEY.contrast)) { applyContrast(curContrast()); sync(); } });

  // 3) Un AUTRE onglet a changé un réglage. `storage` ne se déclenche jamais dans
  //    l'onglet qui écrit, seulement dans les autres : l'écoute ne peut donc pas
  //    boucler, et rien d'autre ne préviendrait. Sans elle, deux onglets ouverts
  //    côte à côte affichaient deux thèmes différents jusqu'au rechargement (F1).
  //    `e.key === null` signale un `localStorage.clear()` : tout est à relire.
  window.addEventListener("storage", function (e) {
    var clefs = [KEY.theme, KEY.contrast, KEY.zoom, KEY.lecture];
    if (e.key !== null && clefs.indexOf(e.key) === -1) return;
    applyTheme(curTheme());
    applyContrast(curContrast());
    applyZoom(curZoom());
    applyLecture(curLecture());
    sync();
  });

  var menus = [];

  function sync() {
    var light = root.dataset.theme === "light";
    var high = root.dataset.contrast === "high";
    var comfort = root.dataset.lecture === "confort";
    var z = curZoom();
    menus.forEach(function (m) {
      m.cb.checked = high;
      m.lecCb.checked = comfort;
      m.zoomVal.textContent = Math.round(z * 100) + " %";
      m.bL.setAttribute("aria-pressed", String(light));
      m.bD.setAttribute("aria-pressed", String(!light));
    });
  }

  function setTheme(t) { put(KEY.theme, t); applyTheme(t); sync(); }
  function setContrast(h) { put(KEY.contrast, h ? "high" : "normal"); applyContrast(h ? "high" : "normal"); sync(); }
  function setLecture(on) { put(KEY.lecture, on ? "confort" : "normal"); applyLecture(on ? "confort" : "normal"); sync(); }
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

    var rL = el("label", "dm-row dm-check");
    rL.title = "Interligne et espacement augmentés, sans capitales forcées — confort de lecture (dys)";
    var lecCb = el("input"); lecCb.type = "checkbox";
    lecCb.onchange = function () { setLecture(lecCb.checked); };
    rL.appendChild(lecCb); rL.appendChild(el("span", null, "Confort de lecture")); panel.appendChild(rL);

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
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      var willOpen = panel.hidden;
      // Signale l'ouverture aux autres systèmes de menus (dropdowns du visualiseur)
      // → un seul menu ouvert à la fois, toutes barres confondues.
      if (willOpen) document.dispatchEvent(new CustomEvent("bd:menu-open", { detail: "display" }));
      open(willOpen);
    });
    panel.addEventListener("click", function (e) { e.stopPropagation(); });
    document.addEventListener("click", function () { open(false); });
    document.addEventListener("bd:menu-open", function (e) { if (e.detail !== "display") open(false); });
    // Échap ferme ET rend le focus au déclencheur (sinon il se perd, le panneau passant
    // en display:none) — important pour la navigation clavier.
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !panel.hidden) { open(false); btn.focus(); }
    });

    menus.push({ cb: cb, lecCb: lecCb, zoomVal: zV, bL: bL, bD: bD });
  }

  /* ---- Navigation transverse unifiée (source unique) ----
     Deux registres : l'ATELIER (Visionneuse, on modifie) ‖ l'ANALYSE (Bibliothèque /
     Recherche / Exploration, on consulte). Injectée dans chaque .surf-nav → même ordre
     partout, « vous êtes ici » automatique, plus de liens en dur divergents. */
  var SURFACES = [
    { href: "/",            label: "Atelier",      icon: "✏", group: "atelier" },
    { href: "/corpus",      label: "Bibliothèque", icon: "📚", group: "analyse" },
    { href: "/recherche",   label: "Recherche",    icon: "🔍", group: "analyse" },
    { href: "/exploration", label: "Exploration",  icon: "📊", group: "analyse" }
  ];

  function buildHeaderNav() {
    var navs = document.querySelectorAll(".surf-nav");
    if (!navs.length) return;
    var path = location.pathname.replace(/\/+$/, "") || "/";   // « / » = Atelier
    navs.forEach(function (nav) {
      if (!nav.getAttribute("aria-label")) nav.setAttribute("aria-label", "Surfaces");
      var prevGroup = null;
      SURFACES.forEach(function (s) {
        if (prevGroup && s.group !== prevGroup) {
          var sep = el("span", "surf-sep"); sep.textContent = "‖";
          sep.setAttribute("aria-hidden", "true");
          nav.appendChild(sep);
        }
        prevGroup = s.group;
        var a = el("a", "ghost surf-link surf-" + s.group, s.icon + " " + s.label);
        a.href = s.href; a.title = s.label;
        if (path === s.href) { a.classList.add("active"); a.setAttribute("aria-current", "page"); }
        nav.appendChild(a);
      });
    });
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

    // Le repère de navigation est porté par <nav class="surf-nav"> (cf. buildHeaderNav) ;
    // .header-actions n'est plus qu'une barre mixte (nav + actions + réglages) → on évite
    // d'y poser un second role=navigation, qui ferait un repère imbriqué redondant.

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

  /* ---- Portée vide : dire POURQUOI l'application paraît vide (AUTH-2) ----
     Le cloisonnement répond 404 partout à qui n'a aucune collection ouverte. C'est la
     bonne réponse de sécurité — rien ne fuit — et la pire réponse d'usage : l'écran est
     exactement celui d'un corpus vide, et la personne conclut que l'outil est cassé.
     On ne révèle rien en l'expliquant : le compte vient de /api/moi et parle de SES
     droits, pas du corpus. textContent partout (le nom vient d'un en-tête). */
  function porteeVide(d) {
    var a = d && d.acces;
    if (!a || a.total || a.collections !== 0) return;
    var titre, texte;
    if (d.utilisateur) {
      titre = "Aucune collection ne vous est ouverte.";
      texte = "Vous êtes bien connecté" + (d.nom ? " (" + d.nom + ")" : "")
        + " : ce n'est pas une panne, et le corpus n'est pas vide. L'accès se donne "
        + "collection par collection — demandez-en un à un administrateur de l'instance.";
    } else {
      /* Portée vide SANS identité : l'application se croit derrière un proxy d'auth
         (BD_AUTH_PROXY) mais aucun en-tête ne lui parvient. Elle ferme alors tout, par
         choix — panne bruyante plutôt que fuite. Reste à ce que le bruit soit AUDIBLE :
         sans ce message, l'écran est celui d'un corpus vide. Message d'exploitation,
         donc, et il ne dit rien du corpus. */
      titre = "Aucune identité ne parvient à l'application.";
      texte = "Elle est configurée comme étant derrière un proxy d'authentification "
        + "(BD_AUTH_PROXY) et n'a reçu aucun en-tête d'identité : elle ferme donc tout, "
        + "délibérément. Si vous administrez cette instance, vérifiez le forward_auth "
        + "du reverse-proxy — voir docs/deploiement-docker.md.";
    }
    var main = document.querySelector("main") || document.body;
    var box = el("div", "portee-vide");
    box.setAttribute("role", "status");
    box.appendChild(el("strong", null, titre));
    box.appendChild(el("p", null, texte));
    var grp = groupesLigne(d);
    if (grp) box.appendChild(grp);
    var ref = referentLigne(a.referent);
    if (ref) box.appendChild(ref);
    main.insertBefore(box, main.firstChild);
  }

  /* ---- Les groupes reçus (AUTH-1) ----
     `/api/moi` renvoie `groupes` depuis INFRA-2 et AUCUNE surface ne les lisait. C'est ici
     qu'ils servent, et pas ailleurs : ils DISTINGUENT trois pannes que le même écran vide
     confondait. Aucune identité (le forward_auth ne passe rien) ; une identité mais aucun
     groupe (le proxy pose `Remote-User` sans `Remote-Groups`, faute de configuration) ;
     une identité AVEC ses groupes, dont aucun n'a reçu d'accès — et là il n'y a rien à
     réparer, seulement un accès à demander.

     Les deux premières se réparent par l'administrateur, la troisième non. Les confondre,
     c'est envoyer quelqu'un chercher une panne qui n'existe pas, ou en ignorer une qui
     existe. On les nomme donc, sans commenter : la liste EST le diagnostic. */
  function groupesLigne(d) {
    if (!d.utilisateur) return null;          // sans identité, les groupes ne disent rien
    var g = d.groupes || [];
    var p = el("p", "portee-vide-groupes");
    if (!g.length) {
      p.appendChild(document.createTextNode(
        "Aucun groupe ne parvient avec votre identité : le proxy pose bien « qui vous "
        + "êtes » mais pas « à quoi vous appartenez ». Si des accès vous ont été accordés "
        + "par groupe, ils ne peuvent pas s'appliquer — c'est un réglage du proxy "
        + "(Remote-Groups), pas un droit manquant."));
      return p;
    }
    p.appendChild(document.createTextNode("Groupes reçus : "));
    p.appendChild(el("strong", null, g.join(", ")));
    p.appendChild(document.createTextNode(
      ". Aucun n'a reçu d'accès sur une collection — il n'y a donc rien de cassé, "
      + "seulement un accès à demander."));
    return p;
  }

  /* ---- Le référent d'instance (AUTH-4) ----
     C'est ICI que le chantier sert vraiment. Le message ci-dessus envoie une personne
     BLOQUÉE « demander un accès à un administrateur de l'instance » sans lui dire à qui —
     et elle ne peut lire AUCUNE collection, donc aucun référent de collection. Seul un
     référent d'instance peut l'aider ; sans lui, AUTH-4 ne servirait que des gens que
     rien ne bloque.

     La déclaration est DÉCLARATIVE et le dit : l'application ne connaît les groupes que
     de la personne qui frappe (AUTH-1), donc elle ne peut pas vérifier que ce nom
     appartient encore à l'équipe. Le dire vaut mieux que le laisser découvrir. */
  function referentLigne(r) {
    if (!r || (!r.nom && !r.contact)) return null;
    var p = el("p", "portee-vide-referent");
    p.appendChild(document.createTextNode("Référent de cette instance : "));
    p.appendChild(el("strong", null, r.nom || r.contact));
    if (r.contact) {
      p.appendChild(document.createTextNode(" — "));
      p.appendChild(contactNoeud(r.contact));
    }
    p.appendChild(document.createTextNode(
      " (déclaré à la configuration : l'application ne peut pas vérifier qu'il fait "
      + "toujours partie de l'équipe)."));
    return p;
  }

  /* Un lien SEULEMENT si le schéma est reconnu. La valeur vient de l'environnement, donc
     de qui déploie — mais « ça vient d'une source de confiance » est l'argument qui
     précède toutes les injections, et `javascript:` dans un href est une porte trop bon
     marché pour la laisser ouverte. Tout le reste s'affiche en texte. */
  function contactNoeud(contact) {
    var v = String(contact).trim();
    var href = /^https?:\/\//i.test(v) ? v
      : /^mailto:/i.test(v) ? v
        : /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? "mailto:" + v : null;
    if (!href) return document.createTextNode(v);
    var a = el("a", null, v);
    a.href = href;
    a.rel = "noopener noreferrer";
    return a;
  }

  /* ---- Utilisateur connecté + déconnexion (INFRA-1, source unique) ----
     Derrière le proxy d'auth (Authelia), /api/moi renvoie l'identité (en-tête
     Remote-User) et l'URL de logout du portail. En local, sans proxy,
     `utilisateur` est null → on n'injecte RIEN (dégradation propre). textContent
     partout : le nom vient d'un en-tête, jamais interprété comme du HTML. */
  /* `/api/moi` est demandé UNE fois par page et partagé : `theme.js` s'exécute sur les
     quatre surfaces, et chaque page qui refaisait l'appel écrivait une ligne de plus dans
     le miroir `utilisateur`. Une PROMESSE plutôt qu'une valeur — les pages se dessinent
     avant qu'elle aboutisse, et attendre est la seule façon honnête de le dire.
     Elle rend `null` sur échec ; aucun appelant ne doit supposer qu'elle réussit. */
  window.BDMoi = fetch("/api/moi", { headers: { Accept: "application/json" } })
    .then(function (r) { return r.ok ? r.json() : null; })
    .catch(function () { return null; });

  function buildUserChip() {
    var bar = document.getElementById("site-nav");
    if (!bar) return;
    window.BDMoi
      .then(function (d) {
        if (!d) return;
        porteeVide(d);                             // AVANT la pastille : le cas « proxy
                                                   // déclaré, aucune identité » n'a pas
                                                   // de pastille, et c'est justement lui
                                                   // qu'il faut expliquer.
        if (!d.utilisateur) return;                // pas d'auth (local) → pas de pastille
        var wrap = el("span", "user-chip");
        var who = el("span", "user-who");
        var nom = d.nom || d.utilisateur;
        who.textContent = nom;
        // Les groupes dans l'infobulle (AUTH-1) : ils gouvernent ce qu'on voit, et
        // personne ne pouvait les consulter — pas même pour vérifier une faute de frappe
        // dans un nom de groupe, qui n'ouvre rien SANS LE DIRE (invariant d'AUTH-2).
        var g = d.groupes || [];
        who.title = "Connecté : " + nom + " (" + d.utilisateur + ")"
          + (g.length ? " — groupes : " + g.join(", ")
                      : " — aucun groupe reçu du proxy");
        var ico = el("span", "user-ico", "👤"); ico.setAttribute("aria-hidden", "true");
        wrap.appendChild(ico); wrap.appendChild(who);
        if (d.deconnexion_url) {
          var out = el("a", "ghost small user-logout", "Déconnexion");
          out.href = d.deconnexion_url; out.title = "Se déconnecter";
          wrap.appendChild(out);
        }
        // Ancre AVANT le menu « Aa ». buildMenu a déplacé .btn-theme DANS un
        // wrapper .display-menu (enfant direct de #site-nav) ; viser .btn-theme
        // lèverait NotFoundError (plus enfant direct). Garde + repli en fin de bande.
        var anchor = bar.querySelector(".display-menu");
        if (anchor && anchor.parentNode === bar) bar.insertBefore(wrap, anchor);
        else bar.appendChild(wrap);
      })
      .catch(function () {});                       // hors-ligne / 4xx → silencieux
  }

  function wire() {
    buildHeaderNav();
    buildUserChip();
    document.querySelectorAll(".btn-theme").forEach(buildMenu);
    sync();
    a11y();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();
})();
