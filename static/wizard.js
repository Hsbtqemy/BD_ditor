/* « Par où commencer » (UX-6) — ce que le wizard DESSINE, sur les six surfaces.

   Tranché par Hugo sur maquette le 2026-11-02 (`pilotage/UX-6.md`). Les RÈGLES — les
   textes, les étapes, le souvenir, quand l'album s'ouvre seul, où mène une étape — vivent
   dans `static/lib/wizard.js` (`BDWizard`), testé sous Node ; ce fichier ne fait que les
   poser sur la page :

     · l'ALBUM de présentation, qui s'ouvre seul au chargement d'une page de SON bac à
       sable tant qu'il n'a pas été vu, avec « Passer » et « Fermer ✕ », et dont la
       dernière page fait choisir un parcours, rapide ou complet ;
     · la CARTE des étapes du parcours choisi, chacune menant à sa surface et à son outil ;
     · « Par où commencer », premier geste de la ligne du bac à sable, qui rouvre l'une ou
       l'autre.

   Les deux sont bâtis sur `static/lib/dialog.js` : rôle, piège à focus, Échap, retour du
   focus. La FENÊTRE posée sur la zone — le guide pas à pas, le reste `inert` — et la visite
   des sept pages ne sont pas encore là : la carte en tient lieu.

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

  function choisir(parcours) {
    retenir(W.choisirParcours(S.souvenir, parcours));
    S.mode = "carte";
    dessiner(".wizard-etapes a");
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
    const revoir = bouton("ghost small", "Revoir la présentation", "wizard-revoir");
    revoir.addEventListener("click", () => { S.mode = "album"; S.page = 0; dessiner("#wizard-suiv"); });
    act.appendChild(revoir);
    boite.appendChild(act);
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
      if (window.BD_SANS_WIZARD !== true && W.ouvreSeul(S.login, S.E.courant, S.souvenir)) {
        await ouvrir("album");
      }
    } finally {
      // Ouvert seul ou non, c'est tranché : ce que les tests attendent avant de dire qu'il
      // ne s'est PAS ouvert (une absence se constate trop tôt sinon).
      ecran.decide = true;
    }
  }

  const ecran = { ouvrir, decide: false };
  window.BDWizardEcran = ecran;

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarrer);
  else demarrer();
})();
