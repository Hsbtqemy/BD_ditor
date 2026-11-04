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
  // L'adresse d'arrivée, lue avant le script de la surface : l'Atelier réécrit la sienne
  // pendant qu'il charge (`syncUrl`), et le guide doit savoir sur quelle planche on arrive.
  const ADRESSE_D_ARRIVEE = location.search;

  const S = { E: null, login: null, bac: null, souvenir: W.neuf(), guide: W.guideNeuf(),
              moteurs: null, mode: "album", page: 0 };
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
    S.guide = W.lireGuide(S.login, S.bac);
  }

  function retenirLeGuide(guide) {
    S.guide = guide;
    W.retenirGuide(S.login, S.bac, guide);
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

  /* `reprendre` : la carte fermée rend la place au guide, s'il est ouvert et que son étape
     est sur cette page. Faux quand un autre geste prend la suite (la visite, une étape). */
  function fermer(reprendre = true) {
    if (!voile || voile.hidden) return;
    const carte = S.mode === "carte";
    voile.hidden = true;
    const b = document.getElementById("bac-commencer");
    if (b) b.setAttribute("aria-expanded", "false");
    if (reprendre && carte) reprendreLeGuide();
  }

  async function ouvrir(mode) {
    // L'album et la carte prennent la place de la fenêtre sur la zone : jamais les deux.
    fermerFenetre(false);
    await lireMoteurs();
    if (mode === "carte") await lireDonnees();
    dialogue();
    S.mode = mode;
    S.page = 0;
    dessiner();
    voile.hidden = false;
    const b = document.getElementById("bac-commencer");
    if (b) b.setAttribute("aria-expanded", "true");
    // La carte s'ouvre sur l'étape où l'on est.
    const a = mode === "carte" && boite.querySelector('.wizard-etapes li[aria-current="step"] a');
    if (a) a.focus();
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
      const h3 = el("h3", null, W.typo(p.titre));
      const marque = W.marquePage(p, S.moteurs);
      if (marque) h3.appendChild(el("span", "wizard-marque", marque));
      txt.appendChild(h3);
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
    fermer(false);
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
      // Une étape faite : « ✓ » à la place de son numéro, et « fait » pour le lecteur
      // d'écran (la maquette).
      const ok = W.faite(e, G.d, s.parcours);
      const num = el("span", "wizard-n" + (ok ? " ok" : ""), ok ? "✓" : String(i + 1));
      num.setAttribute("aria-hidden", "true");
      li.appendChild(num);
      const corps = el("div", "wizard-etape");
      const a = el("a", "wizard-lien", W.typo(e.titre));
      a.href = W.adresseEtape(e, v);
      a.addEventListener("click", (ev) => {
        retenir(W.allerA(S.souvenir, i));
        retenirLeGuide({ actif: true, vues: S.guide.vues });
        // Déjà sur la page de l'étape : le guide s'ouvre sans recharger.
        if (memePage(a.getAttribute("href"))) {
          ev.preventDefault();
          fermer(false);
          ouvrirLeGuide();
        }
      });
      corps.appendChild(a);
      if (ok) corps.appendChild(el("span", "sr-only wizard-fait", " (fait)"));
      const marque = W.marqueEtape(e, S.moteurs, true);
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
    // L'ordre et les mots de la maquette : la présentation, puis les pages.
    const revoir = bouton("ghost small", "Revoir la présentation", "wizard-revoir");
    revoir.addEventListener("click", () => { S.mode = "album"; S.page = 0; dessiner("#wizard-suiv"); });
    act.appendChild(revoir);
    const visite = bouton("ghost small", "Revoir les pages", "wizard-revoir-visite");
    visite.addEventListener("click", () => { fermer(false); commencerVisite({ page: 0, temps: 0 }); });
    act.appendChild(visite);
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
  function reperesDuTemps() {
    return W.reperes(F.pos.page, F.pos.temps, voit, W.bacDuProjet(S.E && S.E.courant));
  }

  /* Les zones jouables de la fenêtre : les repères du temps pour la visite et le « ? » ;
     pour le guide, les zones de l'étape qui se voient, sans numéro (elles ne sont pas une
     liste à lire, mais l'endroit du geste). */
  function zonesActives() {
    if (F.mode !== "etape") return reperesDuTemps();
    const e = etapeCourante();
    if (G.fin || !e) return [];
    return (e.zones || []).filter(voit).map((m) => ({ marque: m, n: null }));
  }

  function dessinerFenetre(focus) {
    const page = W.VISITE[F.pos.page], plan = F.mode === "plan";
    libererLaPose();
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
    fenetre.appendChild(el("p", "wf-phrase",
      W.phrasePage(F.pos.page, W.bacDuProjet(S.E && S.E.courant))));

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
    zonesActives().forEach((r) => k.push(...zonesDe(r.marque)));
    if (F.mode === "etape") k.push(...elementsDuFoyer());
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
    const trou = (t) => masque.appendChild(svg("rect", { x: t.l, y: t.t, width: t.r - t.l,
                                                         height: t.b - t.t, rx: 6, fill: "#000" }));
    // Le guide : UN trou, le rectangle commun de son foyer (`foyerDeLEtape`).
    const f = F.mode === "etape" ? foyerDeLEtape() : null;
    if (f) {
      const t = { l: Math.max(f.l - m, 0), t: Math.max(f.t - m, 0), r: Math.min(f.r + m, W0),
                  b: Math.min(f.b + m, H0), rep: { marque: null, n: null } };
      trous.push(t);
      trou(t);
    }
    (F.mode === "etape" ? [] : zonesActives()).forEach((r) => {
      const els = zonesDe(r.marque);
      if (!els.length) return;
      // Le trou ne déborde pas de la fenêtre du navigateur : une zone de toute la largeur
      // (la bande) dessinerait sinon un cadre plus large que la page.
      const q = rectDe(els);
      const t = { l: Math.max(q.l - m, 0), t: Math.max(q.t - m, 0),
                  r: Math.min(q.r + m, W0), b: Math.min(q.b + m, H0), rep: r };
      if (t.r - t.l < 1 || t.b - t.t < 1) return;
      trous.push(t);
      trou(t);
      // Un menu ouvert depuis la zone (« Aa », « Traitement ») déborde d'elle : il se lit
      // en clair, comme elle (`pilotage/UX-6.md`, choix de la tranche 2).
      menusOuverts(els).forEach((q) => trou({ l: Math.max(q.left - m, 0), t: Math.max(q.top - m, 0),
                                              r: Math.min(q.right + m, W0),
                                              b: Math.min(q.bottom + m, H0) }));
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
      if (t.rep.n == null) return;   // les zones du guide n'ont pas de numéro
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
    if (F.mode === "etape") noterLaFiche();
    const cle = zonesActives().map((r) => r.marque).join(" ");
    if (cle !== F.cle) {
      const a = document.activeElement;
      const garde = a && fenetre.contains(a) ? (a.id ? `#${a.id}`
        : a.dataset.zone ? `[data-zone="${a.dataset.zone}"]` : null) : null;
      if (F.mode === "etape") dessinerEtape(garde); else dessinerFenetre(garde);
    }
    if (F.mode === "etape") poserFenetre(); else reserverLaVisite();
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
    if (mode === "etape") dessinerEtape(); else dessinerFenetre();
    if (mode === "etape") poserFenetre(); else reserverLaVisite();
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
    if (F.mode === "etape") sortirDuCadrage();
    G.fin = false;
    libererLaPose();
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
    F.choisie = premiereDuSecondTemps();
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
  /* Au bout de la visite, ou passée : les gestes (la maquette, « vis-fin ») — le guide sur
     l'étape où l'on est, sur sa page. */
  function finirVisite() {
    fermerFenetre(false);
    relire();
    retenirLeGuide({ actif: true, vues: S.guide.vues });
    const e = etapeCourante();
    if (!e) { ouvrir("carte"); return; }
    const adresse = W.adresseEtape(e, vue());
    if (memePage(adresse)) ouvrirLeGuide(); else location.assign(adresse);
  }

  /* Le « ? » : les repères de la page où l'on est, sans rien y changer. */
  function reperes(declencheur) {
    const i = W.pageDeLaSurface(chemin());
    if (i < 0) return;
    fermerFenetre(false);
    const t = W.tempsVisibles(i, voit);
    ouvrirFenetre("plan", { page: i, temps: t[0] }, declencheur);
  }

  /* Le second temps d'une page éclaire d'emblée sa première zone : la fenêtre vient de
     passer à gauche pour elle (la maquette). Au premier temps, aucune. */
  function premiereDuSecondTemps() {
    if (!F.pos || F.pos.temps !== 1) return null;
    const r = reperesDuTemps()[0];
    return r ? r.marque : null;
  }

  function choisirZone(marque) {
    F.choisie = F.choisie === marque ? null : marque;
    fenetre.querySelectorAll(".wf-zone").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.zone === F.choisie)));
    if (F.choisie) {
      const els = zonesDe(F.choisie);
      // Sur un écran étroit, la zone choisie remonte au-dessus de la feuille.
      if (els.length && etroit()) amener(els, true);
      else if (els.length) els[0].scrollIntoView({ block: "nearest", inline: "nearest" });
    }
    dessinerVoile();
  }

  function clicFenetre(ev) {
    const z = ev.target.closest(".wf-zone");
    if (z) { choisirZone(z.dataset.zone); return; }
    const b = ev.target.closest("[data-geste]");
    if (!b || b.disabled) return;
    const g = b.dataset.geste;
    if (gesteDuGuide(g)) return;
    if (g === "fermer") fermerFenetre();
    else if (g === "suiv") allerVisite(W.suivant(F.pos), "#wizard-visite-suiv");
    else if (g === "prec") allerVisite(W.precedent(F.pos), "#wizard-visite-prec");
    else if (g === "fin") finirVisite();
    else if (g === "plan-prec" || g === "plan-suiv") {
      const i = F.temps.indexOf(F.pos.temps) + (g === "plan-suiv" ? 1 : -1);
      if (i < 0 || i >= F.temps.length) return;
      F.pos = { page: F.pos.page, temps: F.temps[i] };
      F.choisie = premiereDuSecondTemps();
      dessinerFenetre(g === "plan-suiv" ? "#wizard-reperes-suiv" : "#wizard-reperes-prec");
      mettreAJour();
    }
  }

  /* Les touches tapées dans la fenêtre ne remontent pas à la page : sous elle, l'Atelier
     change de mode à une lettre et de zone aux flèches. Échap la ferme. */
  function clavierFenetre(ev) {
    ev.stopPropagation();
    if (ev.key === "Escape") { ev.preventDefault(); echap(); }
  }

  /* Échap ferme la fenêtre ; dans le guide, c'est « Quitter » (✕). */
  function echap() {
    if (F.mode === "etape") quitterLeGuide(); else fermerFenetre();
  }

  // Échap quand le focus est perdu sur la page (un élément gardé qu'un rendu a remplacé).
  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape" || !F.mode) return;
    const a = document.activeElement;
    if (!a || a === document.body) echap();
  });

  /* ── Le guide, étape par étape ───────────────────────────────────────────────────────
     Après la visite, la même fenêtre guide les GESTES, un par étape du parcours choisi (Hugo,
     2026-11-02, déroulé 4) : posée à côté des zones de l'étape — le reste assombri et
     `inert`, les zones jouables —, sur la page où le geste se fait. Une étape faite se voit
     sur la planche, sans coche à déclarer (décision C) : le guide relit la planche du
     parcours après chaque écriture de la page, la marque « ✓ Fait » et fait de « Suivant »
     son geste principal ; il ne passe pas seul à l'étape suivante. Ce qui compte comme fait
     est écrit dans `lib/wizard.js` (`faite`).

     Il vit dans l'onglet (`BDWizard.retenirGuide`, stockage de session) : ouvert, il se
     rouvre sur la page de son étape ; ailleurs, il attend. ✕ ou Échap le quittent, « Par où
     commencer » le rouvre par la carte, qui le reprend là où on était. ☰ ouvre la carte.

     « Corriger le découpage » : l'Atelier cadre seul (`BDAtelierVue.cadrer`) — la planche se
     rapproche de la bulle à corriger en entrant dans l'étape, et revient à la planche
     entière en sortant (`BDAtelierVue.toutVoir`). */
  const G = { d: null, lecture: 0, attente: 0, cadree: false, fin: false, vue: null,
              annoncee: null };

  function annoncer(texte) {
    let z = document.getElementById("wizard-annonce");
    if (!z) {
      z = el("p", "sr-only");
      z.id = "wizard-annonce";
      z.setAttribute("aria-live", "polite");
      (foyer || document.body).appendChild(z);
    }
    z.textContent = "";
    setTimeout(() => { z.textContent = texte; }, 50);
  }

  function etapeCourante() {
    const l = W.etapes(S.souvenir.parcours);
    return l[S.souvenir.etape] || null;
  }

  /* L'adresse d'une étape est-elle la page où l'on est ? Même chemin, et chaque paramètre
     qu'elle nomme a ici la même valeur — l'Atelier ajoute les siens (la zone choisie). */
  function memePage(adresse) {
    let u;
    try { u = new URL(adresse, location.href); } catch (e) { return false; }
    if ((u.pathname.replace(/\/+$/, "") || "/") !== chemin()) return false;
    const ici = new URLSearchParams(location.search);
    for (const [k, v] of u.searchParams) if (ici.get(k) !== v) return false;
    return true;
  }

  /* Ce que le guide lit pour dire une étape faite : la planche du parcours (ses régions,
     ses relevés) et la ligne de son album. Une lecture refusée laisse sa part vide. La plus
     récente l'emporte. */
  async function lireDonnees() {
    const a = W.albumDuParcours(vue());
    const n = ++G.lecture;
    const d = { regions: [], releves: [], album: null, vues: S.guide.vues };
    if (a) {
      const pid = a.planche_ids[0];
      const [regions, releves, albums] = await Promise.all([
        apiGet(`/api/planches/${pid}/regions`).catch(() => null),
        apiGet(`/api/planches/${pid}/releves`).catch(() => null),
        apiGet("/api/albums").catch(() => null)]);
      d.regions = Array.isArray(regions) ? regions : [];
      d.releves = releves && Array.isArray(releves.releves) ? releves.releves : [];
      d.album = Array.isArray(albums) ? albums.find((x) => x.id === a.album_id) || null : null;
    }
    if (n === G.lecture) G.d = d;
    return G.d;
  }

  /* Chaque écriture de la page — un tracé, un cadre repris, un texte, un relevé, la
     notice — fait relire la planche, une fois les écritures d'une rafale passées. */
  function relireBientot() {
    if (F.mode !== "etape") return;
    clearTimeout(G.attente);
    G.attente = setTimeout(async () => {
      if (F.mode !== "etape") return;
      await lireDonnees();
      if (F.mode === "etape") dessinerEtape(focusGarde());
    }, 400);
  }

  (function ecouterLesEcritures() {
    const envoyer = window.apiSend;
    if (typeof envoyer !== "function") return;
    window.apiSend = async function (...args) {
      const r = await envoyer.apply(this, args);
      relireBientot();
      return r;
    };
  })();

  function focusGarde() {
    const a = document.activeElement;
    return a && fenetre && fenetre.contains(a) && a.id ? `#${a.id}` : null;
  }

  /* « Constituer le corpus » : la fiche de l'album du parcours s'ouvre dans la
     Bibliothèque — son adresse le nomme. Lu à chaque mise à jour de la fenêtre. */
  function noterLaFiche() {
    const e = etapeCourante(), a = W.albumDuParcours(vue());
    if (!e || e.k !== "corpus" || !a || chemin() !== "/corpus") return;
    if (new URLSearchParams(location.search).get("album") !== String(a.album_id)) return;
    if (S.guide.vues.includes("corpus")) return;
    retenirLeGuide(W.marquerVue(S.guide, "corpus"));
    if (G.d) G.d = Object.assign({}, G.d, { vues: S.guide.vues });
    dessinerEtape(focusGarde());
  }

  function dessinerEtape(focus) {
    const s = S.souvenir, liste = W.etapes(s.parcours), i = s.etape, e = liste[i];
    const d = Object.assign({}, G.d || {}, { vues: S.guide.vues });
    fenetre.innerHTML = "";
    fenetre.classList.remove("gauche");
    fenetre.classList.add("etape");
    fenetre.setAttribute("aria-label", "Le parcours");
    const h = el("h2", "wf-titre");
    h.id = "wizard-fenetre-titre";
    h.tabIndex = -1;
    const act = el("div", "wf-actions");
    const quitter = bouton("ghost small", "Fermer ✕", "wizard-guide-quitter");
    quitter.dataset.geste = "guide-quitter";
    if (G.fin || !e) {
      h.textContent = "Parcours terminé";
      fenetre.appendChild(h);
      fenetre.appendChild(el("p", "wf-phrase", W.typo(
        "Continuez sur une autre planche : rien ne vous guide, rien ne se perd avant lundi.")));
      // Les autres planches du jeu, en vignettes (la maquette) : chacune mène à l'Atelier.
      const v = vue(), parcours = W.albumDuParcours(v);
      const autres = (v && Array.isArray(v.jeu) ? v.jeu : []).filter((j) =>
        j !== parcours && Array.isArray(j.planche_ids) && j.planche_ids.length);
      if (autres.length) {
        const pl = el("div", "wf-vignettes");
        autres.forEach((j) => {
          const lien = el("a", "wf-vignette");
          lien.href = `/?album=${j.album_id}&planche=${j.planche_ids[0]}`;
          lien.title = j.titre || "";
          const img = miniature(j.planche_ids[0]);
          img.alt = j.titre || "Une planche du jeu";
          lien.appendChild(img);
          pl.appendChild(lien);
        });
        fenetre.appendChild(pl);
      }
      act.appendChild(quitter);
      fenetre.appendChild(act);
      F.cle = "";
    } else {
      const tete = el("div", "wf-tete");
      const compte = el("span", "wf-compte", `${i + 1} / ${liste.length}`);
      compte.id = "wizard-guide-compte";
      tete.appendChild(compte);
      const barre = el("span", "wf-barre");
      barre.setAttribute("aria-hidden", "true");
      liste.forEach((x, j) => barre.appendChild(
        el("i", W.faite(x, d, s.parcours) ? "ok" : j === i ? "ici" : null)));
      tete.appendChild(barre);
      fenetre.appendChild(tete);
      h.textContent = W.typo(e.titre);
      const marque = W.marqueEtape(e, S.moteurs);
      if (marque) h.appendChild(el("span", "wizard-marque", marque));
      fenetre.appendChild(h);
      fenetre.appendChild(el("p", "wf-phrase", W.phraseGuide(e, vue(), S.moteurs, d, s.parcours)));
      const estFaite = W.faite(e, d, s.parcours);
      const fait = el("span", "wf-fait", estFaite ? "✓ Fait" : "");
      fait.id = "wizard-guide-fait";
      // Une étape qui DEVIENT faite s'annonce, dans une région qui ne se redessine pas.
      const cle = `${s.parcours}:${i}`;
      if (estFaite && G.annoncee !== cle && G.vue === cle) annoncer(`${W.typo(e.titre)} : fait.`);
      if (estFaite) G.annoncee = cle;
      G.vue = cle;
      const prec = bouton("ghost small", "←", "wizard-guide-prec");
      prec.setAttribute("aria-label", "Étape précédente");
      prec.disabled = i === 0;
      prec.dataset.geste = "guide-prec";
      const carte = bouton("ghost small", "☰", "wizard-guide-carte");
      carte.setAttribute("aria-label", "Toutes les étapes");
      carte.title = "Toutes les étapes";
      carte.dataset.geste = "guide-carte";
      quitter.textContent = "✕";
      quitter.setAttribute("aria-label", "Quitter le parcours");
      quitter.title = "Quitter : « Par où commencer » le rouvre";
      const b = W.boutonGuide(e, d, S.moteurs, s.parcours, i === liste.length - 1);
      const suiv = bouton(`${b.principal ? "primary" : "ghost"} small`, b.texte, "wizard-guide-suiv");
      suiv.dataset.geste = "guide-suiv";
      // L'ordre de la maquette : « ✓ Fait », ←, le geste principal (poussé à droite), ☰, ✕.
      [fait, prec, suiv, carte, quitter].forEach((x) => act.appendChild(x));
      fenetre.appendChild(act);
      F.cle = zonesActives().map((r) => r.marque).join(" ");
    }
    // Son contenu a changé, donc sa taille : elle se repose (sans attendre une mutation de
    // la page, que l'observateur ne voit pas quand elle vient de la fenêtre).
    if (F.mode === "etape") poserFenetre();
    let f = focus ? fenetre.querySelector(focus) : null;
    if (focus && (!f || f.disabled)) f = h;
    if (f) f.focus({ preventScroll: true });
  }

  /* Ouvrir le guide sur l'étape où l'on est, sur cette page : lire la planche, dessiner,
     puis — pour « Corriger » — cadrer la bulle. Une étape dite est vue dès qu'elle s'affiche. */
  async function ouvrirLeGuide(recherche = location.search) {
    const e = etapeCourante();
    if (!e || !W.etapeIci(e, chemin(), recherche, vue())) return;
    fermerFenetre(false);
    G.fin = false;
    if (e.dite) retenirLeGuide(W.marquerVue(S.guide, e.k));
    await lireMoteurs();
    await lireDonnees();
    ouvrirFenetre("etape", null, null);
    entrerDansLeCadrage();
  }

  /* La carte fermée, ou une page qui se charge : le guide reprend s'il est ouvert. */
  async function reprendreLeGuide(recherche = location.search) {
    relire();
    if (!S.guide.actif || !S.souvenir.parcours || F.mode) return;
    const e = etapeCourante();
    if (e && W.etapeIci(e, chemin(), recherche, vue())) await ouvrirLeGuide(recherche);
  }

  /* Aller à l'étape `i` du parcours : sur cette page, la fenêtre se redessine ; ailleurs,
     on y va, et la page suivante rouvre le guide. */
  async function allerEtape(i, focus) {
    sortirDuCadrage();
    retenir(W.allerA(S.souvenir, i));
    const e = etapeCourante();
    if (!e) return;
    const adresse = W.adresseEtape(e, vue());
    if (!memePage(adresse)) { location.assign(adresse); return; }
    if (e.dite) retenirLeGuide(W.marquerVue(S.guide, e.k));
    await lireDonnees();
    if (F.mode !== "etape") return;
    dessinerEtape(focus);
    mettreAJour();
    entrerDansLeCadrage();
  }

  function quitterLeGuide() {
    retenirLeGuide({ actif: false, vues: S.guide.vues });
    fermerFenetre();
    if (typeof toast === "function") toast(W.typo("« Par où commencer » le rouvre, à la même étape."));
  }

  function gesteDuGuide(g) {
    if (F.mode !== "etape" || !/^guide-/.test(g)) return false;
    const l = W.etapes(S.souvenir.parcours), i = S.souvenir.etape;
    if (g === "guide-quitter") quitterLeGuide();
    else if (g === "guide-carte") ouvrir("carte");
    else if (g === "guide-prec" && i > 0) allerEtape(i - 1, "#wizard-guide-prec");
    else if (g === "guide-suiv") {
      if (i + 1 < l.length) allerEtape(i + 1, "#wizard-guide-suiv");
      else { sortirDuCadrage(); G.fin = true; dessinerEtape("#wizard-guide-quitter"); mettreAJour(); }
    }
    return true;
  }

  /* « Corriger » : l'Atelier se rapproche de la bulle à corriger, si l'étape n'est pas
     déjà faite et que la planche du parcours est celle qu'il montre. */
  function entrerDansLeCadrage() {
    const e = etapeCourante(), a = W.albumDuParcours(vue());
    if (!e || e.k !== "decoupage" || chemin() !== "/" || !window.BDAtelierVue || !a) return;
    if (W.faite(e, G.d, S.souvenir.parcours)) return;
    const b = W.bulleACorriger(G.d && G.d.regions);
    if (!b) return;
    G.cadree = true;
    G.bulle = b.id;
    G.recadre = null;
    window.BDAtelierVue.cadrer(a.planche_ids[0], b.id);
  }

  function sortirDuCadrage() {
    G.bulle = null;
    if (!G.cadree) return;
    G.cadree = false;
    if (window.BDAtelierVue) window.BDAtelierVue.toutVoir();
  }

  /* ── Le foyer de l'étape, et la place de la fenêtre ─────────────────────────────────
     Hugo, sur la maquette (2026-11-02, redit le 2026-11-04) : le trou de l'assombri est le
     rectangle commun des éléments PRÉCIS que l'étape éclaire (`BDWizard.FOYERS`), mesuré à
     chaque dessin, et la fenêtre se pose à côté — à droite s'il y a la place, sinon à
     gauche, dessous, dessus (`BDWizard.placerFenetre`). Quand rien ne tient, et toujours sur
     un écran étroit (sous 40em), elle est une FEUILLE en bas, et la page lui réserve sa
     hauteur : rien de la page n'est sous elle. Elle se remesure à chaque mise à jour de la
     fenêtre — une taille, un zoom de la planche, un foyer qui change. Une étape neuve amène
     son foyer dans la vue. */
  function elementsDuFoyer() {
    const e = etapeCourante();
    if (F.mode !== "etape" || G.fin || !e) return [];
    const a = W.albumDuParcours(vue()), out = [];
    W.foyer(e).forEach((m) => {
      let sel = `[data-parcours="${m}"]`;
      if (m === "@album") {
        sel = a ? `[data-parcours="bibliotheque-catalogue"] [data-ouvrir-album="${a.album_id}"]` : null;
      } else if (m === "@bulle") {
        const b = G.bulle != null ? G.bulle
          : ((G.d && G.d.regions) || []).filter((r) => r.type === "bulle" && r.source === "corrige")
            .map((r) => r.id)[0];
        sel = b != null ? `#overlay rect.region[data-id="${b}"]` : null;
      }
      if (sel) document.querySelectorAll(sel).forEach((x) => { if (partVisible(x)) out.push(x); });
    });
    return out;
  }

  /* La part d'un élément qui se voit : son rectangle, coupé par chaque ancêtre qui ne laisse
     pas déborder (une région zoomée s'arrête au bord de la scène) et par l'écran ; `null`
     s'il ne se voit pas. */
  function partVisible(x) {
    if (foyer && foyer.contains(x)) return null;
    const q = x.getBoundingClientRect();
    if (q.width < 1 || q.height < 1 || getComputedStyle(x).visibility === "hidden") return null;
    let r = { l: q.left, t: q.top, r: q.right, b: q.bottom };
    const couper = (z) => { r = { l: Math.max(r.l, z.left), t: Math.max(r.t, z.top),
                                  r: Math.min(r.r, z.right), b: Math.min(r.b, z.bottom) }; };
    for (let a = x.parentElement; a && a !== document.body; a = a.parentElement) {
      const st = getComputedStyle(a);
      if (st.overflowX !== "visible" || st.overflowY !== "visible") couper(a.getBoundingClientRect());
    }
    couper({ left: 0, top: 0, right: window.innerWidth, bottom: window.innerHeight });
    return r.r - r.l >= 1 && r.b - r.t >= 1 ? r : null;
  }

  function foyerDeLEtape() {
    const rs = elementsDuFoyer().map(partVisible).filter(Boolean);
    if (!rs.length) return null;
    return { l: Math.min(...rs.map((r) => r.l)), t: Math.min(...rs.map((r) => r.t)),
             r: Math.max(...rs.map((r) => r.r)), b: Math.max(...rs.map((r) => r.b)) };
  }

  const ETROIT = "(max-width: 40em)";

  function etroit() { return !!(window.matchMedia && window.matchMedia(ETROIT).matches); }

  /* La visite et les repères, sur un écran étroit (sous 40em), sont une feuille en bas
     (`style.css`) : comme pour le guide, la page lui réserve sa hauteur, pour que le bas
     de la page — les résultats de la Recherche et de l'Exploration — puisse remonter
     au-dessus d'elle ; choisir un repère l'y amène (`pilotage/UX-6.md`, « La maquette se
     mesure sur l'écran codé », 768 px sous une grande police). */
  function reserverLaVisite() {
    if (F.mode === "etape" || !fenetre) return;
    reserver(etroit() ? fenetre.offsetHeight + 24 : 0);
  }

  function reserver(px) {
    const b = document.body, root = document.documentElement;
    const avant = b.classList.contains("wizard-reserve") ? root.style.getPropertyValue("--wizard-reserve") : "";
    if (px > 0) {
      root.style.setProperty("--wizard-reserve", `${Math.ceil(px)}px`);
      b.classList.add("wizard-reserve");
    } else if (b.classList.contains("wizard-reserve")) {
      b.classList.remove("wizard-reserve");
      root.style.removeProperty("--wizard-reserve");
    }
    const apres = b.classList.contains("wizard-reserve") ? root.style.getPropertyValue("--wizard-reserve") : "";
    // La scène de l'Atelier a changé de taille : la planche entière s'y réajuste.
    if (avant !== apres && window.BDAtelierVue && window.BDAtelierVue.ajuster) {
      window.BDAtelierVue.ajuster();
    }
  }

  function libererLaPose() {
    if (!fenetre) return;
    fenetre.classList.remove("etape", "feuille");
    fenetre.style.left = "";
    fenetre.style.top = "";
    reserver(0);
    G.pose = null;
    G.amene = null;
  }

  function poserFenetre() {
    if (F.mode !== "etape" || !fenetre) return;
    const etape = `${S.souvenir.parcours}:${S.souvenir.etape}:${G.fin}`;
    const cle = `${etape}:${window.innerWidth}x${window.innerHeight}`;
    // Le repli est tenu pour l'étape et la taille de l'écran : la feuille réserve sa place,
    // ce qui change la page, et la fenêtre n'en repartirait pas à côté pour revenir.
    let feuille = etroit() || !!(G.pose && G.pose.cle === cle && G.pose.feuille);
    if (!feuille) {
      fenetre.classList.remove("feuille");
      reserver(0);
      const w = fenetre.offsetWidth, h = fenetre.offsetHeight, m = 8;
      const p = W.placerFenetre(foyerDeLEtape(), { w, h },
        { l: m, t: m, r: window.innerWidth - m, b: window.innerHeight - m }, 14);
      if (p.cote === "repli") feuille = true;
      else {
        fenetre.style.left = `${Math.round(p.x)}px`;
        fenetre.style.top = `${Math.round(p.y)}px`;
      }
    }
    if (feuille) {
      fenetre.style.left = "";
      fenetre.style.top = "";
      fenetre.classList.add("feuille");
      reserver(fenetre.offsetHeight + 24);
    }
    G.pose = { cle, etape, feuille };
    // Une étape neuve amène son foyer dans la vue, au-dessus de la feuille — dès qu'il est
    // là : la fiche d'un album, par exemple, se dessine après la fenêtre.
    // Une seconde et demie durant : une fiche, un catalogue se dessinent après la fenêtre et
    // déplacent le foyer.
    if (G.amene !== etape) { G.amene = etape; G.ameneDepuis = Date.now(); }
    if (Date.now() - G.ameneDepuis < 1500) {
      const els = elementsDuFoyer();
      if (els.length) amener(els, feuille);
      else if (F.attente === 0) setTimeout(planifier, 100);
    }
    garderLaBulleHorsDeLaFenetre();
  }

  /* Amener le foyer dans la vue : d'abord dans son cadre de défilement, puis la page
     elle-même, quand elle défile (à l'étroit, sous une grande police), pour que son bas
     passe au-dessus de la feuille. */
  function amener(els, feuille) {
    const haut = 8, bas = () => window.innerHeight - (feuille ? fenetre.offsetHeight + 24 : 8);
    const union = () => {
      const rs = els.map((x) => x.getBoundingClientRect());
      return { t: Math.min(...rs.map((r) => r.top)), b: Math.max(...rs.map((r) => r.bottom)) };
    };
    let r = union();
    if (r.t >= haut && r.b <= bas()) return;
    els[0].scrollIntoView({ block: "nearest", inline: "nearest" });
    r = union();
    if (r.b > bas()) window.scrollBy({ top: Math.min(r.t - haut, r.b - bas()), behavior: "instant" });
    else if (r.t < haut) window.scrollBy({ top: r.t - haut, behavior: "instant" });
  }

  /* « Corriger » cadre la bulle de sorte qu'elle reste hors de la fenêtre : si la fenêtre
     la recouvre, ou que la bulle n'est plus dans la scène (la feuille a réduit la page),
     l'Atelier la recadre dans la part de la scène que la fenêtre laisse libre — une fois
     par mise en page, sans boucle. */
  function garderLaBulleHorsDeLaFenetre() {
    if (!G.cadree || G.bulle == null || !window.BDAtelierVue) return;
    const bulle = document.querySelector(`#overlay rect.region[data-id="${G.bulle}"]`);
    const scene = document.getElementById("stage");
    if (!bulle || !scene) return;
    const q = bulle.getBoundingClientRect(), s = scene.getBoundingClientRect();
    const fq = fenetre.getBoundingClientRect();
    const b = { l: q.left, t: q.top, r: q.right, b: q.bottom };
    const sc = { l: s.left, t: s.top, r: s.right, b: s.bottom };
    const fen = { l: fq.left, t: fq.top, r: fq.right, b: fq.bottom };
    const dedans = b.l >= sc.l && b.r <= sc.r && b.t >= sc.t && b.b <= sc.b;
    if (dedans && !W.recouvre(b, fen)) return;
    const cle = `${G.pose && G.pose.cle}:${Math.round(sc.r - sc.l)}x${Math.round(sc.b - sc.t)}`;
    if (G.recadre === cle) return;
    G.recadre = cle;
    const a = W.albumDuParcours(vue());
    if (a) window.BDAtelierVue.cadrer(a.planche_ids[0], G.bulle, W.zoneLibre(sc, fen, 14));
  }


  /* Un menu ouvert depuis une zone : sa liste déborde d'elle. */
  function menusOuverts(els) {
    const out = [];
    els.forEach((e) => e.querySelectorAll(".dropdown-menu, .display-panel").forEach((m) => {
      const r = m.getBoundingClientRect();
      if (r.width >= 1 && r.height >= 1 && getComputedStyle(m).visibility !== "hidden") out.push(r);
    }));
    return out;
  }

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
        } else {
          // Le guide ouvert dans cet onglet reprend sur la page de son étape.
          await reprendreLeGuide(ADRESSE_D_ARRIVEE);
        }
      }
    } finally {
      // Ouvert seul ou non, c'est tranché : ce que les tests attendent avant de dire qu'il
      // ne s'est PAS ouvert (une absence se constate trop tôt sinon).
      ecran.decide = true;
    }
  }

  const ecran = { ouvrir, reperes, fermerFenetre, decide: false,
                  elementsDuFoyer: () => elementsDuFoyer() };
  window.BDWizardEcran = ecran;

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarrer);
  else demarrer();
})();
