/* « Par où commencer » (UX-6) — ce que le wizard DESSINE, sur les six surfaces.

   Tranché par Hugo sur maquette le 2026-11-02 (`pilotage/UX-6.md`). Les RÈGLES — les
   textes, les étapes, le souvenir, quand l'album s'ouvre seul, où mène une étape — vivent
   dans `static/lib/wizard.js` (`BDWizard`), testé sous Node ; ce fichier ne fait que les
   poser sur la page :

     · l'ALBUM de présentation, qui s'ouvre seul au chargement d'une page de SON bac à
       sable tant qu'il n'a pas été vu, avec « Passer » et « Fermer ✕ », et dont la
       dernière page fait choisir un parcours, rapide ou complet ;
     · la VISITE des sept pages, après le choix d'un parcours, dans la FENÊTRE posée à
       côté des zones — le reste assombri et `inert`, les zones jouables —, puis la CARTE
       des étapes du parcours choisi, chacune menant à sa surface et à son outil ;
     · « Par où commencer », premier geste de la ligne du bac à sable, qui rouvre l'album
       ou la carte ;
     · les REPÈRES de la page où l'on est, dans la même fenêtre, que rouvre le « ? » de la
       bande (`theme.js`), sur les six surfaces et pour tout compte.

   L'album et la carte sont bâtis sur `static/lib/dialog.js` : rôle, piège à focus, Échap,
   retour du focus. La fenêtre sur la zone ne l'est pas : elle n'est pas une modale (cf. sa
   section). Le guide pas à pas, étape par étape, n'est pas encore là : la carte en tient
   lieu.

   Chargé APRÈS `lib/bac-a-sable.js`, `bac-a-sable.js` et `lib/wizard.js`, AVANT le script
   de la surface. Il lit ce que `bac-a-sable.js` a déjà lu (`BDBacEcran.pret` : l'identité,
   les projets, la vue de son bac à sable) et ne demande en plus que `GET /api/sante`, à
   l'ouverture.

   Le harnais des tests navigateur pose `window.BD_SANS_WIZARD = true` avant tout script
   (`tests/conftest.py`, un seul endroit) : l'album ne s'ouvre alors plus SEUL — sans quoi
   il se poserait devant le premier clic de chaque test du bac à sable. « Par où
   commencer » l'ouvre toujours. */
(function () {
  "use strict";
  const W = window.BDWizard, B = window.BDBacEcran;
  if (!W || !B) return;

  const S = { E: null, login: null, bac: null, souvenir: W.neuf(), moteurs: null,
              mode: "album", page: 0 };
  let voile = null, boite = null;

  function el(tag, cls, txt) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }

  function bouton(cls, txt, id) {
    const b = el("button", cls, txt);
    b.type = "button";
    if (id) b.id = id;
    return b;
  }

  /* Le bac à sable courant et sa vue, relus à chaque fois : le projet courant change. */
  function relire() {
    const E = S.E;
    S.login = (E && E.moi && E.moi.utilisateur) || null;
    S.bac = W.bacASoi(E && E.courant);
    S.souvenir = W.lireSouvenir(S.login, S.bac);
  }

  function vue() {
    const E = S.E;
    return E && E.vue && S.bac && E.vue.id === S.bac.id ? E.vue : null;
  }

  function retenir(souvenir) {
    S.souvenir = souvenir;
    W.retenirSouvenir(S.login, S.bac, souvenir);
  }

  async function lireMoteurs() {
    if (S.moteurs) return S.moteurs;
    let sante = null;
    try { sante = await apiGet("/api/sante"); } catch (e) { sante = null; }
    S.moteurs = W.moteurs(sante);
    return S.moteurs;
  }

  /* ── Le dialogue ─────────────────────────────────────────────────────────────────── */
  function dialogue() {
    if (voile) return boite;
    voile = el("div", "wizard-modal");
    voile.id = "wizard-modal";
    voile.hidden = true;
    boite = el("div", "modal-box wizard-boite");
    voile.appendChild(boite);
    document.body.appendChild(voile);
    voile.addEventListener("mousedown", (ev) => { if (ev.target === voile) fermer(); });
    boite.addEventListener("keydown", clavier);
    if (window.BDDialog) {
      BDDialog.register(voile, { box: ".wizard-boite", labelledby: "wizard-titre",
                                 onClose: fermer, retour: retourDuFocus });
    }
    return boite;
  }

  /* Ouvert seul au chargement, l'album n'a pas de déclencheur : le focus revient à
     « Par où commencer », sinon au contenu de la page. */
  function retourDuFocus() {
    return document.getElementById("bac-commencer") || document.getElementById("contenu")
      || document.querySelector("main");
  }

  function fermer() {
    if (!voile || voile.hidden) return;
    voile.hidden = true;
    const b = document.getElementById("bac-commencer");
    if (b) b.setAttribute("aria-expanded", "false");
  }

  async function ouvrir(mode) {
    // L'album et la carte prennent la place de la fenêtre sur la zone : jamais les deux.
    fermerFenetre(false);
    await lireMoteurs();
    dialogue();
    S.mode = mode;
    S.page = 0;
    dessiner();
    voile.hidden = false;
    const b = document.getElementById("bac-commencer");
    if (b) b.setAttribute("aria-expanded", "true");
  }

  function dessiner(focus) {
    boite.innerHTML = "";
    if (S.mode === "carte") dessinerCarte(); else dessinerAlbum();
    if (focus) {
      const f = boite.querySelector(focus);
      if (f) f.focus();
    }
  }

  function tete(titre, avecPasser) {
    const t = el("div", "wizard-tete");
    const h = el("h2", null, titre);
    h.id = "wizard-titre";
    t.appendChild(h);
    const haut = el("span", "wizard-haut");
    if (avecPasser) {
      const p = bouton("ghost small", "Passer", "wizard-passer");
      p.title = "Aller au choix du parcours";
      p.addEventListener("click", () => tourner(nbPages() - 1, "#wizard-choix-rapide"));
      haut.appendChild(p);
    }
    const f = bouton("ghost small", "Fermer ✕", "wizard-fermer");
    f.addEventListener("click", fermer);
    haut.appendChild(f);
    t.appendChild(haut);
    return t;
  }

  /* ── L'album ─────────────────────────────────────────────────────────────────────── */
  function nbPages() { return W.PAGES.length + 1; }

  /* Les illustrations ne viennent que de l'instance : les miniatures des planches que le
     jeu a posées dans le bac à sable. Une miniature absente s'efface sans laisser de cadre. */
  function miniature(plancheId, cls) {
    const img = el("img", cls);
    img.alt = "";
    img.loading = "lazy";
    img.src = `/api/planches/${plancheId}/miniature`;
    img.addEventListener("error", () => img.remove());
    return img;
  }

  function illustration(page) {
    const v = vue();
    const jeu = (v && Array.isArray(v.jeu) ? v.jeu : [])
      .filter((j) => Array.isArray(j.planche_ids) && j.planche_ids.length);
    const parcours = W.albumDuParcours(v);
    if (page.k === "outil" && jeu.length) {
      const d = el("div", "wizard-eventail");
      jeu.slice(0, 5).forEach((j) => d.appendChild(miniature(j.planche_ids[0])));
      return d;
    }
    if (page.k === "corpus" && jeu.length) {
      const d = el("ul", "wizard-vignettes");
      jeu.forEach((j) => {
        const li = el("li");
        li.appendChild(miniature(j.planche_ids[0]));
        li.appendChild(el("span", "wizard-vignette-titre", j.titre || ""));
        d.appendChild(li);
      });
      return d;
    }
    if (["zones", "moteurs", "analyse"].includes(page.k) && parcours) {
      const d = el("div", "wizard-planche");
      d.appendChild(miniature(parcours.planche_ids[0]));
      return d;
    }
    return null;
  }

  function dessinerAlbum() {
    const n = nbPages(), i = S.page, derniere = i === n - 1;
    boite.classList.add("wizard-album");
    boite.classList.remove("wizard-carte");
    boite.appendChild(tete(W.TITRE_ALBUM, !derniere));

    const page = el("div", "wizard-page");
    page.id = "wizard-page";
    page.setAttribute("role", "group");
    page.setAttribute("aria-label", `Page ${i + 1} sur ${n}`);
    if (!derniere) {
      const p = W.PAGES[i];
      const ill = illustration(p);
      if (ill) { const c = el("div", "wizard-ill"); c.appendChild(ill); page.appendChild(c); }
      else page.classList.add("sans-ill");
      const txt = el("div", "wizard-txt");
      const num = el("span", "wizard-num", String(i + 1));
      num.setAttribute("aria-hidden", "true");
      txt.appendChild(num);
      txt.appendChild(el("h3", null, W.typo(p.titre)));
      txt.appendChild(el("p", null, W.textePage(p, S.moteurs)));
      page.appendChild(txt);
    } else {
      page.classList.add("wizard-fin");
      page.appendChild(el("h3", null, W.typo(W.FIN.titre)));
      page.appendChild(el("p", null, W.typo(W.FIN.texte)));
      const choix = el("div", "wizard-choix");
      W.FIN.parcours.forEach((c) => {
        const b = bouton("wizard-choix-btn", null, `wizard-choix-${c.k}`);
        b.dataset.choix = c.k;
        b.appendChild(el("strong", null, c.titre));
        b.appendChild(el("span", null, W.typo(c.detail)));
        b.addEventListener("click", () => choisir(c.k));
        choix.appendChild(b);
      });
      page.appendChild(choix);
      const lab = el("label", "wizard-jamais");
      const cb = el("input");
      cb.type = "checkbox";
      cb.id = "wizard-jamais";
      cb.checked = S.souvenir.album_vu && !S.souvenir.parcours;
      cb.addEventListener("change", () => retenir(W.neJamaisAfficher(S.souvenir, cb.checked)));
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(` ${W.FIN.jamais}`));
      page.appendChild(lab);
    }
    boite.appendChild(page);

    const bas = el("div", "wizard-bas");
    const prec = bouton("ghost small", "←", "wizard-prec");
    prec.setAttribute("aria-label", "Page précédente");
    prec.disabled = i === 0;
    prec.addEventListener("click", () => tourner(S.page - 1, "#wizard-prec"));
    bas.appendChild(prec);
    const points = el("span", "wizard-points");
    points.setAttribute("aria-hidden", "true");
    for (let k = 0; k < n; k += 1) points.appendChild(el("i", k === i ? "ici" : null));
    bas.appendChild(points);
    const compte = el("span", "wizard-compte", `${i + 1} / ${n}`);
    compte.id = "wizard-compte";
    compte.setAttribute("role", "status");
    bas.appendChild(compte);
    if (!derniere) {
      const suiv = bouton("primary small", "Suivant →", "wizard-suiv");
      suiv.addEventListener("click", () => tourner(S.page + 1, "#wizard-suiv"));
      bas.appendChild(suiv);
    }
    boite.appendChild(bas);
  }

  /* Tourner la page garde le focus sur le bouton pressé ; sur la dernière page, où
     « Suivant » n'est plus, il passe au premier parcours. */
  function tourner(i, focus) {
    const n = nbPages();
    const j = Math.max(0, Math.min(n - 1, i));
    if (j === S.page && S.mode === "album") return;
    S.page = j;
    let cible = focus;
    if (j === n - 1 && (focus === "#wizard-suiv" || focus === "#wizard-passer")) {
      cible = "#wizard-choix-rapide";
    }
    if (j === 0 && focus === "#wizard-prec") cible = "#wizard-suiv";
    dessiner(cible);
  }

  /* Les flèches tournent les pages de l'album, hors d'un champ — et ne vont pas plus loin :
     sous l'album, l'Atelier passe d'une zone à l'autre aux mêmes touches. */
  function clavier(ev) {
    if (S.mode !== "album" || ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.target && /^(INPUT|TEXTAREA|SELECT)$/.test(ev.target.tagName)) return;
    if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
    ev.preventDefault();
    ev.stopPropagation();
    if (ev.key === "ArrowRight") tourner(S.page + 1, "#wizard-suiv");
    else tourner(S.page - 1, "#wizard-prec");
  }

  /* Choisir un parcours ouvre la VISITE des pages, qui passe avant les deux parcours (Hugo,
     2026-11-02, décision H) ; la carte des étapes vient au bout de la visite, ou quand on la
     passe. */
  function choisir(parcours) {
    retenir(W.choisirParcours(S.souvenir, parcours));
    fermer();
    commencerVisite({ page: 0, temps: 0 });
  }

  /* ── La carte des étapes ─────────────────────────────────────────────────────────── */
  function dessinerCarte() {
    boite.classList.add("wizard-carte");
    boite.classList.remove("wizard-album");
    boite.appendChild(tete(W.TITRE_CARTE, false));
    boite.appendChild(el("p", "wizard-avertissement muted small", W.typo(
      "Les moteurs de reconnaissance ne font que pré-remplir : l'analyse reste la vôtre.")));
    const s = S.souvenir, liste = W.etapes(s.parcours), v = vue();
    const ol = el("ol", "wizard-etapes");
    ol.setAttribute("aria-label", s.parcours === "rapide" ? "Parcours rapide" : "Parcours complet");
    liste.forEach((e, i) => {
      const li = el("li");
      if (i === s.etape) li.setAttribute("aria-current", "step");
      const num = el("span", "wizard-n", String(i + 1));
      num.setAttribute("aria-hidden", "true");
      li.appendChild(num);
      const corps = el("div", "wizard-etape");
      const a = el("a", "wizard-lien", W.typo(e.titre));
      a.href = W.adresseEtape(e, v);
      a.addEventListener("click", () => retenir(W.allerA(S.souvenir, i)));
      corps.appendChild(a);
      const marque = W.marqueEtape(e, S.moteurs);
      if (marque) corps.appendChild(el("span", "wizard-marque", marque));
      corps.appendChild(el("span", "muted small", ` · ${W.typo(e.ou)}`));
      corps.appendChild(el("p", "wizard-phrase", W.phraseEtape(e, v, S.moteurs)));
      li.appendChild(corps);
      ol.appendChild(li);
    });
    boite.appendChild(ol);
    const act = el("div", "modal-actions wizard-actions");
    const autre = s.parcours === "rapide" ? "complet" : "rapide";
    const changer = bouton("ghost small", `Passer au parcours ${autre}`, "wizard-changer");
    changer.addEventListener("click", () => {
      retenir(W.choisirParcours(S.souvenir, autre));
      dessiner("#wizard-changer");
    });
    act.appendChild(changer);
    const visite = bouton("ghost small", "Revoir la visite", "wizard-revoir-visite");
    visite.addEventListener("click", () => { fermer(); commencerVisite({ page: 0, temps: 0 }); });
    act.appendChild(visite);
    const revoir = bouton("ghost small", "Revoir la présentation", "wizard-revoir");
    revoir.addEventListener("click", () => { S.mode = "album"; S.page = 0; dessiner("#wizard-suiv"); });
    act.appendChild(revoir);
    boite.appendChild(act);
  }

  /* ── La fenêtre sur la zone ──────────────────────────────────────────────────────────
     Tranchée par Hugo sur maquette le 2026-11-02 : une fenêtre posée à côté de la zone, le
     reste assombri, la zone JOUABLE. Elle sert deux fois :
       · la VISITE des pages (« Visite n / 7 »), après le choix d'un parcours : sept pages,
         la barre du haut puis les six surfaces, chacune en un ou deux temps ;
       · les REPÈRES de la page où l'on est, que rouvre le « ? » de la bande (`theme.js`),
         pour tout compte, sans rien changer à la page — ni mode, ni album.

     Ce N'EST PAS une modale (la case « La fenêtre sur la zone se dessine au clavier ») :
       · les zones du temps sont jouables, tout le reste est `inert` — ni clic, ni focus, ni
         lecteur d'écran ; l'assombri n'est qu'une image (`pointer-events: none`) ;
       · aucun piège à focus. La fenêtre est posée en fin de document : Tab la quitte
         comme on quitte une page, et Maj+Tab depuis la fenêtre entre dans les zones, qui la
         précèdent ; depuis les zones, Tab revient à elle. Échap la ferme et rend le focus à
         qui l'avait ouverte ;
       · une boîte de dialogue ouverte depuis une zone (« Remettre à neuf… ») reste jouable
         au-dessus d'elle.

     Elle change de côté avec le TEMPS, au bouton « Suivant » — à droite au premier, à gauche
     au second —, jamais au survol (refusé par Hugo). Sa place est à la feuille : rien ne la
     déplace pendant qu'on lit. Ce qui bouge est l'assombri, redessiné quand la page change
     (une zone qui arrive, un tiroir qui s'ouvre, le défilement).

     La visite traverse les pages : sa position vit dans le stockage de session
     (`BDWizard.retenirVisite`), et la page suivante la reprend à son chargement. */
  const SVG = "http://www.w3.org/2000/svg";
  const F = { mode: null, pos: null, temps: [], choisie: null, declencheur: null,
              inertes: new Set(), cle: "", obs: null, attente: 0 };
  let foyer = null, voileSvg = null, fenetre = null;

  function chemin() { return location.pathname.replace(/\/+$/, "") || "/"; }

  /* Les éléments d'une zone qui se voient : une boîte non vide, ni `visibility: hidden`
     (les tiroirs fermés de l'Atelier et de la page Annotation), ni un bloc masqué. */
  function zonesDe(marque) {
    return Array.from(document.querySelectorAll(`[data-parcours="${marque}"]`)).filter((e) => {
      if (foyer && foyer.contains(e)) return false;
      const r = e.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return false;
      return getComputedStyle(e).visibility !== "hidden";
    });
  }

  function voit(marque) { return zonesDe(marque).length > 0; }

  function rectDe(els) {
    const rs = els.map((e) => e.getBoundingClientRect());
    return { l: Math.min(...rs.map((r) => r.left)), t: Math.min(...rs.map((r) => r.top)),
             r: Math.max(...rs.map((r) => r.right)), b: Math.max(...rs.map((r) => r.bottom)) };
  }

  function svg(tag, attrs) {
    const e = document.createElementNS(SVG, tag);
    Object.keys(attrs || {}).forEach((k) => e.setAttribute(k, attrs[k]));
    return e;
  }

  function construireFoyer() {
    if (foyer) return;
    foyer = el("div", "wizard-foyer");
    foyer.id = "wizard-foyer";
    voileSvg = svg("svg", { class: "wizard-voile", "aria-hidden": "true", focusable: "false",
                            preserveAspectRatio: "none" });
    fenetre = el("section", "wizard-fenetre");
    fenetre.id = "wizard-fenetre";
    fenetre.addEventListener("keydown", clavierFenetre);
    fenetre.addEventListener("click", clicFenetre);
    foyer.appendChild(voileSvg);
    foyer.appendChild(fenetre);
    document.body.appendChild(foyer);
  }

  /* Les repères du temps affiché, et la page qu'ils décrivent. */
  function reperesDuTemps() { return W.reperes(F.pos.page, F.pos.temps, voit); }

  function dessinerFenetre(focus) {
    const page = W.VISITE[F.pos.page], plan = F.mode === "plan";
    fenetre.innerHTML = "";
    fenetre.classList.toggle("gauche", W.cote(F.pos) === "gauche");
    fenetre.setAttribute("aria-label", plan ? "Les repères de cette page" : "La visite des pages");

    const tete = el("div", "wf-tete");
    const compte = el("span", "wf-compte", plan ? "Cette page" : W.compteVisite(F.pos));
    compte.id = "wizard-visite-compte";
    compte.setAttribute("aria-live", "polite");
    tete.appendChild(compte);
    if (!plan) {
      const barre = el("span", "wf-barre");
      barre.setAttribute("aria-hidden", "true");
      W.VISITE.forEach((x, i) => barre.appendChild(
        el("i", i < F.pos.page ? "ok" : i === F.pos.page ? "ici" : null)));
      tete.appendChild(barre);
    }
    fenetre.appendChild(tete);

    const h = el("h2", "wf-titre", W.typo(page.titre));
    h.id = "wizard-fenetre-titre";
    h.tabIndex = -1;
    fenetre.appendChild(h);
    fenetre.appendChild(el("p", "wf-phrase", W.typo(page.phrase)));

    const ol = el("ol", "wf-zones");
    ol.id = "wizard-zones";
    ol.setAttribute("aria-label", "Repères");
    const reps = reperesDuTemps();
    F.cle = reps.map((r) => r.marque).join(" ");
    reps.forEach((r) => {
      const li = el("li");
      const b = bouton("wf-zone", null);
      b.dataset.zone = r.marque;
      b.setAttribute("aria-pressed", String(F.choisie === r.marque));
      const n = el("span", "wf-n", String(r.n));
      n.setAttribute("aria-hidden", "true");
      b.appendChild(n);
      const t = el("span", "wf-texte");
      t.appendChild(el("b", null, r.nom));
      t.appendChild(document.createTextNode(" "));
      t.appendChild(el("span", "wf-detail", r.phrase));
      b.appendChild(t);
      li.appendChild(b);
      ol.appendChild(li);
    });
    fenetre.appendChild(ol);

    const act = el("div", "wf-actions");
    if (plan) {
      if (F.temps.length > 1) {
        const i = F.temps.indexOf(F.pos.temps);
        const p = bouton("ghost small", "←", "wizard-reperes-prec");
        p.setAttribute("aria-label", "Repères précédents");
        p.disabled = i <= 0;
        p.dataset.geste = "plan-prec";
        const s = bouton("ghost small", "→", "wizard-reperes-suiv");
        s.setAttribute("aria-label", "Repères suivants");
        s.disabled = i >= F.temps.length - 1;
        s.dataset.geste = "plan-suiv";
        act.appendChild(p);
        act.appendChild(s);
      }
      const f = bouton("primary small", "Fermer ✕", "wizard-reperes-fermer");
      f.dataset.geste = "fermer";
      act.appendChild(f);
    } else {
      const p = bouton("ghost small", "←", "wizard-visite-prec");
      p.setAttribute("aria-label", "Précédent");
      p.disabled = W.precedent(F.pos) === null;
      p.dataset.geste = "prec";
      const passer = bouton("ghost small", "Passer la visite", "wizard-visite-passer");
      passer.dataset.geste = "fin";
      const fin = W.estFin(F.pos);
      const s = bouton("primary small", fin ? "Commencer →" : "Suivant →", "wizard-visite-suiv");
      s.dataset.geste = fin ? "fin" : "suiv";
      act.appendChild(p);
      act.appendChild(passer);
      act.appendChild(s);
    }
    fenetre.appendChild(act);

    let f = focus ? fenetre.querySelector(focus) : null;
    // Un bouton éteint ne prend pas le focus : le titre le reçoit à sa place.
    if (focus && (!f || f.disabled)) f = h;
    if (f) f.focus({ preventScroll: true });
  }

  /* Ce qui reste jouable : les zones du temps affiché, la fenêtre, les messages de la page,
     et une boîte de dialogue ouverte par-dessus. Tout le reste devient `inert` — posé sur
     les frères du chemin qui mène du corps à chaque élément gardé (un élément inerte rend
     inerte tout ce qu'il contient, sans retour possible pour un descendant). Ce que la page
     avait déjà rendu inerte n'est ni compté ni rendu. */
  function gardes() {
    const k = [foyer];
    reperesDuTemps().forEach((r) => k.push(...zonesDe(r.marque)));
    const toasts = document.getElementById("toasts");
    if (toasts) k.push(toasts);
    document.querySelectorAll('[aria-modal="true"]').forEach((d) => {
      if (d.getClientRects().length) k.push(d);
    });
    return k;
  }

  function appliquerInert() {
    const k = gardes(), voulu = new Set();
    (function marquer(parent) {
      Array.from(parent.children).forEach((c) => {
        if (k.includes(c)) return;
        if (k.some((x) => c.contains(x))) { marquer(c); return; }
        if (/^(SCRIPT|STYLE|LINK|TEMPLATE)$/.test(c.tagName)) return;
        voulu.add(c);
      });
    })(document.body);
    F.inertes.forEach((e) => { if (!voulu.has(e)) { e.inert = false; F.inertes.delete(e); } });
    voulu.forEach((e) => {
      if (F.inertes.has(e)) { e.inert = true; return; }
      if (!e.inert) { e.inert = true; F.inertes.add(e); }
    });
  }

  function rendreInert() {
    F.inertes.forEach((e) => { e.inert = false; });
    F.inertes.clear();
  }

  /* L'assombri : un SVG qui couvre la fenêtre du navigateur, troué d'un rectangle par zone
     du temps (un masque : deux trous qui se touchent ne se réassombrissent pas), un cadre
     autour de la zone choisie et une pastille numérotée sur chacune. Ses coordonnées sont
     celles de `getBoundingClientRect`, dans la boîte de la fenêtre (`viewBox`) : le zoom de
     l'interface, posé sur la racine, ne les déforme pas. */
  function dessinerVoile() {
    const W0 = window.innerWidth, H0 = window.innerHeight, m = 4;
    const z = typeof document.documentElement.currentCSSZoom === "number"
      ? document.documentElement.currentCSSZoom : 1;
    voileSvg.setAttribute("viewBox", `0 0 ${W0} ${H0}`);
    voileSvg.innerHTML = "";
    const defs = svg("defs");
    const masque = svg("mask", { id: "wizard-masque", maskUnits: "userSpaceOnUse",
                                 x: 0, y: 0, width: W0, height: H0 });
    masque.appendChild(svg("rect", { x: 0, y: 0, width: W0, height: H0, fill: "#fff" }));
    const trous = [];
    reperesDuTemps().forEach((r) => {
      const els = zonesDe(r.marque);
      if (!els.length) return;
      // Le trou ne déborde pas de la fenêtre du navigateur : une zone de toute la largeur
      // (la bande) dessinerait sinon un cadre plus large que la page.
      const q = rectDe(els);
      const t = { l: Math.max(q.l - m, 0), t: Math.max(q.t - m, 0),
                  r: Math.min(q.r + m, W0), b: Math.min(q.b + m, H0), rep: r };
      if (t.r - t.l < 1 || t.b - t.t < 1) return;
      trous.push(t);
      masque.appendChild(svg("rect", { x: t.l, y: t.t, width: t.r - t.l, height: t.b - t.t,
                                       rx: 6, fill: "#000" }));
    });
    defs.appendChild(masque);
    voileSvg.appendChild(defs);
    voileSvg.appendChild(svg("rect", { class: "wf-ombre", x: 0, y: 0, width: W0, height: H0,
                                       mask: "url(#wizard-masque)" }));
    const rayon = 11 * z;
    trous.forEach((t) => {
      voileSvg.appendChild(svg("rect", {
        class: "wf-cadre" + (t.rep.marque === F.choisie ? " ici" : ""),
        x: t.l, y: t.t, width: t.r - t.l, height: t.b - t.t, rx: 6 }));
      const cx = Math.max(t.l, rayon + 2), cy = Math.max(t.t, rayon + 2);
      const g = svg("g", { class: "wf-pastille" });
      g.appendChild(svg("circle", { cx, cy, r: rayon }));
      const txt = svg("text", { x: cx, y: cy, "text-anchor": "middle",
                                "dominant-baseline": "central", "font-size": 13 * z });
      txt.textContent = String(t.rep.n);
      g.appendChild(txt);
      voileSvg.appendChild(g);
    });
  }

  /* Une mise à jour par image au plus : la page qui se dessine, le défilement et la taille
     de la fenêtre en demandent en rafale. La liste ne se redessine que si les zones visibles
     ont changé — une zone qui arrive avec la page — et garde alors le focus qu'elle avait. */
  function mettreAJour() {
    F.attente = 0;
    if (!F.mode || !foyer) return;
    const cle = reperesDuTemps().map((r) => r.marque).join(" ");
    if (cle !== F.cle) {
      const a = document.activeElement;
      const garde = a && fenetre.contains(a) ? (a.id ? `#${a.id}`
        : a.dataset.zone ? `[data-zone="${a.dataset.zone}"]` : null) : null;
      dessinerFenetre(garde);
    }
    dessinerVoile();
    appliquerInert();
  }

  function planifier() {
    if (!F.mode || F.attente) return;
    F.attente = window.requestAnimationFrame(mettreAJour);
  }

  function observer() {
    if (F.obs) return;
    F.obs = new MutationObserver((liste) => {
      if (liste.some((m) => !foyer || !foyer.contains(m.target))) planifier();
    });
    F.obs.observe(document.body, { childList: true, subtree: true, attributes: true,
                                   attributeFilter: ["class", "hidden", "style", "open"] });
    window.addEventListener("resize", planifier);
    document.addEventListener("scroll", planifier, true);
    document.addEventListener("transitionend", planifier, true);
  }

  function cesserDObserver() {
    if (F.obs) F.obs.disconnect();
    F.obs = null;
    window.removeEventListener("resize", planifier);
    document.removeEventListener("scroll", planifier, true);
    document.removeEventListener("transitionend", planifier, true);
    if (F.attente) window.cancelAnimationFrame(F.attente);
    F.attente = 0;
  }

  /* Ouvrir la fenêtre sur la page où l'on est. Le focus va au titre une fois la main rendue :
     ouverte depuis l'album, la fenêtre suit la fermeture d'une modale, qui rend le focus à
     son déclencheur dans la même foulée (`dialog.js`). */
  function ouvrirFenetre(mode, pos, declencheur) {
    construireFoyer();
    F.mode = mode;
    F.pos = pos;
    F.choisie = null;
    F.declencheur = declencheur || null;
    F.temps = mode === "plan" ? W.tempsVisibles(pos.page, voit) : [];
    foyer.hidden = false;
    dessinerFenetre();
    dessinerVoile();
    appliquerInert();
    observer();
    setTimeout(() => {
      const h = document.getElementById("wizard-fenetre-titre");
      if (F.mode && h) h.focus({ preventScroll: true });
    }, 0);
  }

  /* Fermer : la page redevient entière, puis le focus revient à qui a ouvert la fenêtre
     (le « ? »), sinon à « Par où commencer », sinon au contenu. `rendre` à faux : une autre
     fenêtre prend la suite (l'album, la carte) et pose le focus elle-même. */
  function fermerFenetre(rendre) {
    if (!F.mode) return;
    const visite = F.mode === "visite", decl = F.declencheur;
    cesserDObserver();
    rendreInert();
    F.mode = null;
    F.pos = null;
    F.choisie = null;
    if (foyer) foyer.hidden = true;
    if (fenetre) fenetre.innerHTML = "";
    if (voileSvg) voileSvg.innerHTML = "";
    if (visite) W.oublierVisite();
    if (rendre === false) return;
    const cible = [decl, document.getElementById("bac-commencer"), retourDuFocus()]
      .find((e) => e && e.isConnected && e.getClientRects().length);
    if (cible) cible.focus();
  }

  /* Aller à une position de la visite : sur la même surface, la fenêtre se redessine ; sur
     une autre, la position est retenue et la page suivante la reprend. */
  function allerVisite(pos, focus) {
    const p = W.position(pos);
    if (!p) return;
    const surface = W.VISITE[p.page].surface;
    if (surface !== chemin()) {
      // La page peut retenir le départ (une saisie à perdre) : la fenêtre reste alors
      // telle quelle, sur la position d'où l'on partait.
      W.retenirVisite(S.login, S.bac, p);
      location.assign(W.adresseVisite(p.page, vue()));
      return;
    }
    W.retenirVisite(S.login, S.bac, p);
    const pageNeuve = !F.pos || F.pos.page !== p.page;
    F.pos = p;
    F.choisie = null;
    dessinerFenetre(pageNeuve ? "#wizard-fenetre-titre" : focus);
    mettreAJour();
  }

  function commencerVisite(pos) {
    relire();
    const p = W.position(pos);
    if (!p) return;
    if (W.VISITE[p.page].surface === chemin()) {
      W.retenirVisite(S.login, S.bac, p);
      ouvrirFenetre("visite", p, null);
    } else {
      allerVisite(p);
    }
  }

  /* Au bout de la visite, ou passée : la carte, le focus sur l'étape où l'on est. */
  function finirVisite() {
    fermerFenetre(false);
    relire();
    ouvrir("carte").then(() => {
      const a = boite && boite.querySelector('.wizard-etapes li[aria-current="step"] a');
      if (a) a.focus();
    });
  }

  /* Le « ? » : les repères de la page où l'on est, sans rien y changer. */
  function reperes(declencheur) {
    const i = W.pageDeLaSurface(chemin());
    if (i < 0) return;
    fermerFenetre(false);
    const t = W.tempsVisibles(i, voit);
    ouvrirFenetre("plan", { page: i, temps: t[0] }, declencheur);
  }

  function choisirZone(marque) {
    F.choisie = F.choisie === marque ? null : marque;
    fenetre.querySelectorAll(".wf-zone").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.zone === F.choisie)));
    if (F.choisie) {
      const e = zonesDe(F.choisie)[0];
      if (e) e.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
    dessinerVoile();
  }

  function clicFenetre(ev) {
    const z = ev.target.closest(".wf-zone");
    if (z) { choisirZone(z.dataset.zone); return; }
    const b = ev.target.closest("[data-geste]");
    if (!b || b.disabled) return;
    const g = b.dataset.geste;
    if (g === "fermer") fermerFenetre();
    else if (g === "suiv") allerVisite(W.suivant(F.pos), "#wizard-visite-suiv");
    else if (g === "prec") allerVisite(W.precedent(F.pos), "#wizard-visite-prec");
    else if (g === "fin") finirVisite();
    else if (g === "plan-prec" || g === "plan-suiv") {
      const i = F.temps.indexOf(F.pos.temps) + (g === "plan-suiv" ? 1 : -1);
      if (i < 0 || i >= F.temps.length) return;
      F.pos = { page: F.pos.page, temps: F.temps[i] };
      F.choisie = null;
      dessinerFenetre(g === "plan-suiv" ? "#wizard-reperes-suiv" : "#wizard-reperes-prec");
      mettreAJour();
    }
  }

  /* Les touches tapées dans la fenêtre ne remontent pas à la page : sous elle, l'Atelier
     change de mode à une lettre et de zone aux flèches. Échap la ferme. */
  function clavierFenetre(ev) {
    ev.stopPropagation();
    if (ev.key === "Escape") { ev.preventDefault(); fermerFenetre(); }
  }

  // Échap quand le focus est perdu sur la page (un élément gardé qu'un rendu a remplacé).
  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape" || !F.mode) return;
    const a = document.activeElement;
    if (!a || a === document.body) fermerFenetre();
  });

  /* ── « Par où commencer », dans la ligne du bac à sable ──────────────────────────── */
  function poserLeBouton() {
    const gestes = document.querySelector("#bac-ligne .bac-gestes");
    const ancien = document.getElementById("bac-commencer");
    if (!gestes || !S.bac) { if (ancien) ancien.remove(); return; }
    if (ancien && ancien.parentNode === gestes) return;
    const b = bouton("ghost small", W.TITRE_CARTE, "bac-commencer");
    b.setAttribute("aria-haspopup", "dialog");
    b.setAttribute("aria-expanded", "false");
    b.addEventListener("click", (ev) => {
      ev.stopPropagation();
      relire();
      ouvrir(S.souvenir.parcours ? "carte" : "album");
    });
    gestes.insertBefore(b, gestes.firstChild);
  }

  async function demarrer() {
    try { S.E = await B.pret; } catch (e) { ecran.decide = true; return; }
    relire();
    poserLeBouton();
    // La ligne se redessine — un projet changé, une invitation : le bouton la suit.
    document.addEventListener("bd:bac-a-sable-maj", () => { relire(); poserLeBouton(); });
    try {
      // Une visite en cours reprend sur la page où elle mène ; arrivée ailleurs — un lien
      // suivi pendant la visite —, elle s'arrête.
      const enCours = W.lireVisite(S.login, S.bac);
      if (enCours && W.VISITE[enCours.page].surface === chemin()) {
        ouvrirFenetre("visite", enCours, null);
      } else {
        if (enCours) W.oublierVisite();
        if (window.BD_SANS_WIZARD !== true && W.ouvreSeul(S.login, S.E.courant, S.souvenir)) {
          await ouvrir("album");
        }
      }
    } finally {
      // Ouvert seul ou non, c'est tranché : ce que les tests attendent avant de dire qu'il
      // ne s'est PAS ouvert (une absence se constate trop tôt sinon).
      ecran.decide = true;
    }
  }

  const ecran = { ouvrir, reperes, fermerFenetre, decide: false };
  window.BDWizardEcran = ecran;

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarrer);
  else demarrer();
})();
