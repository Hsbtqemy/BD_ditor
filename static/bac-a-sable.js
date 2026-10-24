/* « Mon bac à sable » (COL-4) — ce que l'écran en DESSINE, sur les cinq surfaces.

   Tranché par Hugo sur maquette le 2026-10-24 (`pilotage/COL-4.md`, zone « L'écran »). Les
   RÈGLES — qui se voit offrir quoi, la date en heure de Paris, le plafond, ce qui part et ce
   qui revient — vivent dans `static/lib/bac-a-sable.js` (`BDBac`), testé sous Node ; ce
   fichier ne fait que les poser sur la page :

     · « Mon bac à sable » à côté du projet, dans la bande du haut, tant qu'il n'existe pas ;
       dans le bandeau de portée vide, à droite, visible sans déplier ; la page vide de
       l'Atelier et la fiche de la Bibliothèque le demandent par `BDBacEcran.gestePageVide`.
       Jamais dans le menu du compte. Après le clic : l'Atelier, sur la planche du parcours ;
     · la LIGNE du bac à sable, une rangée rayée sous la bande, quand le projet courant en
       est un : son nom (l'aide en infobulle), sa date, le compte des planches importées, et
       ses gestes — « Inviter… (n) » et « Remettre à neuf… », ou « Quitter… » ;
     · le bandeau « Aucune collection ne vous est ouverte » masqué dans un bac à sable ;
     · sur la Recherche et l'Exploration, dans un bac à sable, la phrase qui dit qu'elles ne
       le voient pas, au-dessus de leurs résultats (l'élément `[data-bac-hors-recherche]`
       de leur gabarit) ;
     · l'effacement du lundi, dit par un message à la requête suivante.

   Chargé APRÈS `common.js`, `projet.js`, `dialog.js`, `membres-projet.js` et
   `lib/bac-a-sable.js`, AVANT le script de la surface, qui lit `window.BDBacEcran`.
   Il lit ce que `theme.js` a demandé une fois pour la page (`window.BDMoi`,
   `window.BDProjets`) et ne demande en plus que la vue de SON bac à sable
   (`GET /api/bac-a-sable`), à qui en a un. */
(function () {
  "use strict";
  const L = window.BDBac, P = window.BDProjet;
  if (!L || !P) return;

  const MESSAGE_SESSION = "bd-bac-message";     // le message d'un effacement vu en page
  const DUREE_MESSAGE = 10000;

  const E = { moi: null, projets: null, vue: null, courant: null, lu: false };
  let tour = 0;
  let tranche = false;         // la première lecture a répondu (ou échoué) : le bandeau suit                // une lecture dépassée par une plus récente ne dessine pas

  function el(tag, cls, txt) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }

  function courantDe(projets) {
    const l = Array.isArray(projets) ? projets : [];
    const id = P.courant(l, P.lire());
    return l.find((p) => p.id === id) || null;
  }

  /* ── Lire ─────────────────────────────────────────────────────────────────────────── */
  async function lire() {
    const mien = ++tour;
    const [moi, projets] = await Promise.all([
      Promise.resolve(window.BDMoi).catch(() => null),
      Promise.resolve(window.BDProjets).catch(() => null)]);
    let vue = null;
    const lp = Array.isArray(projets) ? projets : null;
    if (lp && L.mien(lp)) {
      try { vue = await apiGet("/api/bac-a-sable"); } catch (e) { vue = null; }
    }
    if (mien !== tour) return E;
    E.moi = moi; E.projets = lp; E.vue = vue; E.courant = courantDe(lp); E.lu = true;
    if (lp) direLesDisparus(lp);
    return E;
  }

  function login() { return (E.moi && E.moi.utilisateur) || null; }

  /* Un bac à sable que CE compte avait vu à la page précédente, et absent de la liste : le
     message, une fois. Seulement sur une liste LUE et non vide, et sous une identité — la
     mémoire est rangée par login (`lib/bac-a-sable.js`). */
  function direLesDisparus(projets) {
    const qui = login();
    if (!qui) return;
    const partis = L.disparusDe(qui, projets);
    L.retenirSouvenirs(qui, L.souvenirsDe(projets));
    const maintenant = new Date();
    partis.forEach((s) => {
      const m = L.messageDisparu(s, maintenant, projets);
      if (m) toast(m, "", DUREE_MESSAGE);
    });
  }

  /* ── « Mon bac à sable » : le geste ──────────────────────────────────────────────── */
  async function ouvrir(bouton) {
    const libelle = bouton ? bouton.textContent : "";
    if (bouton) { bouton.disabled = true; bouton.textContent = "Ouverture…"; }
    try {
      const vue = await apiSend("POST", "/api/bac-a-sable");
      P.retenir(vue.id);
      // La page suivante le connaît déjà : son absence ne s'y lira pas comme un effacement.
      L.retenirSouvenirs(login(), [...L.lireSouvenirs(login()).filter((s) => s.id !== vue.id),
                                   { id: vue.id, mien: true, proprietaire: null,
                                     efface_le: vue.efface_le }]);
      location.assign(L.adresseApresOuverture(vue));
    } catch (e) {
      toast(e.message || "Le bac à sable n'a pas pu s'ouvrir.", "error", 8000);
      if (bouton) { bouton.disabled = false; bouton.textContent = libelle; }
    }
  }

  function bouton(classe) {
    const b = el("button", classe, "Mon bac à sable");
    b.type = "button";
    b.title = "Ouvrir un projet à vous, rempli d'un jeu de planches, pour apprendre l'outil.";
    b.addEventListener("click", (ev) => { ev.stopPropagation(); ouvrir(b); });
    return b;
  }

  function offre() { return E.projets !== null && L.offrir(E.moi, E.projets); }

  /* ── La bande du haut : le bouton à côté du projet ───────────────────────────────── */
  function dessinerBouton() {
    const bar = document.getElementById("site-nav");
    if (!bar) return;
    const ancien = bar.querySelector(".bac-ouvrir-bande");
    if (ancien) ancien.remove();
    if (!offre()) return;
    const b = bouton("ghost small bac-ouvrir-bande");
    const projet = bar.querySelector(".projet-courant");
    const ancre = projet && projet.parentNode === bar ? projet.nextSibling
      : bar.querySelector(".user-chip") || bar.querySelector(".display-menu");
    if (ancre && ancre.parentNode === bar) bar.insertBefore(b, ancre);
    else bar.appendChild(b);
  }

  /* ── Le bandeau de portée vide ───────────────────────────────────────────────────── */
  /* `theme.js` fait naître le bandeau CACHÉ quand ce script est là (sans quoi il paraîtrait
     un instant avant d'être masqué dans un bac à sable) : c'est ici, la question tranchée,
     qu'il se montre — même si la liste n'a pas pu se lire. */
  function ajusterBandeau() {
    const box = document.getElementById("portee-vide");
    if (!box) return;
    box.hidden = L.estBac(E.courant);
    const geste = box.querySelector(".portee-vide-geste");
    if (!offre()) {
      if (geste) geste.remove();
      box.classList.remove("avec-geste");
      return;
    }
    if (geste) return;
    const g = el("span", "portee-vide-geste");
    g.appendChild(el("span", "muted small", "En attendant :"));
    g.appendChild(bouton("primary small"));
    box.appendChild(g);
    box.classList.add("avec-geste");
  }

  /* ── La ligne du bac à sable ─────────────────────────────────────────────────────── */
  function dessinerLigne() {
    const bar = document.getElementById("site-nav");
    if (!bar) return;
    const ancienne = document.getElementById("bac-ligne");
    if (ancienne) ancienne.remove();
    const l = L.ligne(E.courant, E.vue);
    if (!l) return;
    const box = el("div", "bac-ligne");
    box.id = "bac-ligne";
    box.setAttribute("role", "region");
    box.setAttribute("aria-label", "Bac à sable");
    // Le nom porte l'aide en infobulle (« un écran stable, sans phrases ») ; au clavier et
    // au lecteur d'écran, la même aide par sa description.
    const nom = el("span", "bac-nom", l.nom);
    nom.title = l.aide;
    nom.tabIndex = 0;
    nom.setAttribute("aria-describedby", "bac-aide");
    box.appendChild(nom);
    const aide = el("span", "sr-only", l.aide);
    aide.id = "bac-aide";
    box.appendChild(aide);
    const sep = () => { const s = el("span", "bac-sep", "·"); s.setAttribute("aria-hidden", "true"); return s; };
    if (l.date) { box.appendChild(sep()); box.appendChild(el("span", "bac-date", l.date)); }
    if (l.plafond) {
      box.appendChild(sep());
      const c = el("span", "bac-plafond" + (l.plafond.plein ? " est-plein" : ""), l.plafond.texte);
      c.id = "bac-plafond";
      if (l.plafond.plein) c.title = L.raisonImportEteint(E.vue, E.vue.id);
      box.appendChild(c);
    }
    const gestes = el("span", "bac-gestes");
    if (l.gestes.includes("inviter")) {
      const b = el("button", "ghost small", L.libelleInviter(l.invites));
      b.type = "button"; b.id = "bac-inviter";
      b.setAttribute("aria-haspopup", "dialog");
      b.addEventListener("click", (ev) => { ev.stopPropagation(); dialogueInviter(b); });
      gestes.appendChild(b);
    }
    if (l.gestes.includes("remettre")) {
      const b = el("button", "ghost small", "Remettre à neuf…");
      b.type = "button"; b.id = "bac-remettre";
      b.setAttribute("aria-haspopup", "dialog");
      b.addEventListener("click", (ev) => { ev.stopPropagation(); dialogueRemise(b); });
      gestes.appendChild(b);
    }
    if (l.gestes.includes("quitter")) {
      const b = el("button", "ghost small", "Quitter…");
      b.type = "button"; b.id = "bac-quitter";
      b.setAttribute("aria-haspopup", "dialog");
      b.addEventListener("click", (ev) => { ev.stopPropagation(); dialogueQuitter(b); });
      gestes.appendChild(b);
    }
    box.appendChild(gestes);
    bar.appendChild(box);
  }

  /* ── La Recherche et l'Exploration : la phrase, dans un bac à sable ─────────────────
     Juste avant l'élément que le gabarit désigne (`data-bac-hors-recherche`), au-dessus des
     résultats ; ni masquable ni repliable. Hors d'un bac à sable elle n'existe pas, et elle
     part dès qu'on en sort. Le même texte n'est pas redessiné : la ligne reste en place. */
  function dessinerHorsRecherche() {
    const ancre = document.querySelector("[data-bac-hors-recherche]");
    const ancienne = document.getElementById("bac-hors-recherche");
    const texte = ancre ? L.horsRecherche(E.courant) : null;
    if (!texte) {
      if (ancienne) ancienne.remove();
      return;
    }
    if (ancienne && ancienne.textContent === texte) return;
    const p = ancienne || el("p", "bac-hors-recherche");
    p.id = "bac-hors-recherche";
    p.textContent = texte;
    if (!ancienne) ancre.parentNode.insertBefore(p, ancre);
  }

  function dessiner() {
    dessinerBouton();
    ajusterBandeau();
    dessinerLigne();
    dessinerHorsRecherche();
    document.dispatchEvent(new CustomEvent("bd:bac-a-sable-maj"));
  }

  /* Après un geste qui change la liste — inviter, remettre à neuf, quitter : la bande se
     relit (`theme.js` écoute le même événement), puis ce fichier. */
  async function relireTout() {
    document.dispatchEvent(new CustomEvent("bd:projets-maj"));
  }

  /* ── Le dialogue ─────────────────────────────────────────────────────────────────── */
  /* UN voile pour les trois dialogues, créé au premier, réutilisé : `BDDialog` y pose le
     rôle, le piège à focus, Échap et le retour du focus au bouton de la ligne. */
  let voile = null, boite = null, surFermer = null;
  function dialogue() {
    if (voile) return boite;
    voile = el("div", "bac-modal");
    voile.id = "bac-modal";
    voile.hidden = true;
    boite = el("div", "modal-box bac-boite");
    voile.appendChild(boite);
    document.body.appendChild(voile);
    voile.addEventListener("mousedown", (ev) => { if (ev.target === voile) fermer(); });
    if (window.BDDialog) {
      BDDialog.register(voile, { box: ".bac-boite", labelledby: "bac-modal-titre",
                                 onClose: fermer });
    }
    return boite;
  }

  function fermer() {
    if (!voile || voile.hidden) return;
    voile.hidden = true;
    const f = surFermer;
    surFermer = null;
    if (typeof f === "function") f();
  }

  function ouvrirDialogue(remplir, apres) {
    const b = dialogue();
    b.innerHTML = "";
    remplir(b);
    surFermer = apres || null;
    voile.hidden = false;
  }

  function actions(libelleOk, classeOk, faire) {
    const act = el("div", "modal-actions bac-actions");
    const non = el("button", "ghost", "Annuler");
    non.type = "button";
    non.addEventListener("click", fermer);
    const oui = el("button", classeOk, libelleOk);
    oui.type = "button";
    const msg = el("p", "col-msg muted small bac-msg");
    msg.setAttribute("role", "status");
    msg.setAttribute("aria-live", "polite");
    oui.addEventListener("click", async () => {
      oui.disabled = true; non.disabled = true;
      try { await faire(); }
      catch (e) {
        msg.textContent = e.message || "Échec";
        msg.classList.add("erreur");
        oui.disabled = false; non.disabled = false;
      }
    });
    act.appendChild(non);
    act.appendChild(oui);
    return [act, msg, non];
  }

  /* « Remettre à neuf… » : deux colonnes, « Ce qui part » et « Ce qui revient ». Les
     invités se nomment : leur invitation part avec le projet. */
  async function dialogueRemise() {
    const invites = await BDMembresProjet.invites(E.courant.id);
    const r = L.remiseANeuf(E.vue, invites);
    ouvrirDialogue((b) => {
      const h = el("h3", null, "Remettre votre bac à sable à neuf ?");
      h.id = "bac-modal-titre";
      b.appendChild(h);
      const cols = el("div", "bac-deux-col");
      [["Ce qui part", r.part], ["Ce qui revient", r.revient]].forEach(([titre, items]) => {
        const c = el("div");
        c.appendChild(el("strong", null, titre));
        const ul = el("ul");
        items.forEach((t) => ul.appendChild(el("li", null, t)));
        c.appendChild(ul);
        cols.appendChild(c);
      });
      b.appendChild(cols);
      const [act, msg, non] = actions("Remettre à neuf", "danger", async () => {
        const vue = await apiSend("POST", "/api/bac-a-sable/remise-a-neuf");
        P.retenir(vue.id);
        L.retenirSouvenirs(login(), [...L.lireSouvenirs(login()).filter((s) => s.mien !== true),
                                     { id: vue.id, mien: true, proprietaire: null,
                                       efface_le: vue.efface_le }]);
        // Le projet a changé d'identifiant. Dans l'Atelier, la planche du parcours, comme
        // au premier clic ; ailleurs, la même surface, sans son adresse — elle nommait des
        // objets du bac d'avant (Hugo, 2026-10-24).
        garderMessage("Bac à sable remis à neuf.");
        location.assign(L.adresseApresRemise(vue, location.pathname));
      });
      b.appendChild(act);
      b.appendChild(msg);
      setTimeout(() => non.focus(), 0);
    });
  }

  /* « Quitter… » : une ligne. */
  function dialogueQuitter() {
    const p = E.courant, qui = p.bac_a_sable.proprietaire;
    ouvrirDialogue((b) => {
      const h = el("h3", null, `Quitter le bac à sable de ${qui} ?`);
      h.id = "bac-modal-titre";
      b.appendChild(h);
      b.appendChild(el("p", null, `${qui} pourra vous inviter à nouveau.`));
      const [act, msg, non] = actions("Quitter", "danger", async () => {
        await apiSend("POST", `/api/bac-a-sable/${p.id}/quitter`);
        L.retenirSouvenirs(login(), L.lireSouvenirs(login()).filter((s) => s.id !== p.id));
        garderMessage(`Vous avez quitté le bac à sable de ${qui}.`);
        // La page retombe sur le projet suivant, ou vide : un rechargement le fait sur
        // toutes les surfaces, qui lisent leur projet au chargement — sans l'adresse, qui
        // nommait peut-être un objet du bac quitté. Le message passe à la page qui suit.
        location.assign(location.pathname);
      });
      b.appendChild(act);
      b.appendChild(msg);
      setTimeout(() => non.focus(), 0);
    });
  }

  /* « Inviter… » : « Qui y entre », le module des membres d'un projet MONTÉ dans le
     dialogue, réduit à ce qu'un bac à sable permet (`bacASable`). */
  let montage = null, aChange = false;
  function dialogueInviter() {
    const p = E.courant;
    aChange = false;
    ouvrirDialogue((b) => {
      const sec = el("section", "bac-membres");
      b.appendChild(sec);
      montage = BDMembresProjet.monter(sec, {
        projet: { id: p.id, nom: p.nom, gerable: !!p.gerable },
        groupesAdmin: [],
        bacASable: true,
        niveauTitre: 3,
        // Le champ naît quand la liste est lue : il prend le focus, que le dialogue a posé
        // en s'ouvrant sur « Fermer », le seul focalisable d'alors.
        focaliserAjout: true,
        surChangement: () => { aChange = true; },
      });
      // Le titre de la partie nomme le dialogue.
      const titre = sec.querySelector("h3");
      if (titre) voile.querySelector(".bac-boite").setAttribute("aria-labelledby", titre.id);
      const act = el("div", "modal-actions bac-actions");
      const f = el("button", "ghost", "Fermer");
      f.type = "button";
      f.addEventListener("click", fermer);
      act.appendChild(f);
      b.appendChild(act);
    }, () => {
      if (montage) { montage.demonter(); montage = null; }
      voile.querySelector(".bac-boite").setAttribute("aria-labelledby", "bac-modal-titre");
      if (aChange) relireTout();
    });
  }

  /* ── L'effacement du lundi, vu EN PAGE ───────────────────────────────────────────────
     Une page ouverte sur un bac à sable qui s'efface ne le sait pas : la requête suivante
     reçoit un 404 (`common.js` le signale, `bd:introuvable`). On relit alors la liste des
     projets ; si le bac à sable courant n'y est plus, le message est gardé pour la page qui
     suit, et la page se recharge — elle retombe sur le projet suivant, ou vide, et les
     places de « Mon bac à sable » reviennent. */
  let verifie = false;
  async function verifierApresUnRefus() {
    if (verifie || !L.estBac(E.courant)) return;
    verifie = true;
    try {
      const r = await fetch("/api/projets", { headers: { Accept: "application/json" } });
      const projets = r.ok ? await r.json() : null;
      if (!Array.isArray(projets)) return;
      const partis = L.disparus(L.souvenirsDe([E.courant]), projets);
      if (!partis.length) return;
      const m = L.messageDisparu(partis[0], new Date(), projets);
      L.retenirSouvenirs(login(), L.souvenirsDe(projets));
      if (m) garderMessage(m);
      // Sans l'adresse : un lien vers un album du bac à sable effacé n'a plus d'objet, et
      // l'Atelier dirait « introuvable » par-dessus le message.
      location.assign(location.pathname);
    } catch (e) { /* hors ligne : rien à conclure */ }
    finally { verifie = false; }
  }

  function garderMessage(m) {
    try { sessionStorage.setItem(MESSAGE_SESSION, m); } catch (e) { /* sans lui */ }
  }

  function messageGarde() {
    try {
      const m = sessionStorage.getItem(MESSAGE_SESSION);
      if (m) { sessionStorage.removeItem(MESSAGE_SESSION); toast(m, "", DUREE_MESSAGE); }
    } catch (e) { /* stockage indisponible */ }
  }

  /* ── Ce que les surfaces lisent ──────────────────────────────────────────────────── */
  const pret = lire().then(() => E);

  window.BDBacEcran = {
    pret,
    /* Le geste de la page vide, ou `null` si la page ne l'offre pas : un bloc avec son
       texte et le bouton. Lu APRÈS `pret`. */
    gestePageVide(classe, texte) {
      if (!E.lu || E.projets === null || !L.offrirPageVide(E.moi, E.projets)) return null;
      const g = el("div", classe);
      g.appendChild(el("span", null, texte));
      g.appendChild(bouton("primary small"));
      return g;
    },
    /* La raison d'éteindre l'import dans un album de ce projet, ou `null`. */
    raisonImport(albumProjetId) { return L.raisonImportEteint(E.vue, albumProjetId); },
    /* Le projet courant est-il un bac à sable ? — `null` s'il n'en est pas un, sa ligne de
       `GET /api/projets` sinon. */
    bacCourant() { return L.estBac(E.courant) ? E.courant : null; },
    /* Après un import : le compte des planches importées a pu changer. */
    async rafraichir() {
      if (!E.projets || !L.mien(E.projets)) return;
      try { E.vue = await apiGet("/api/bac-a-sable"); } catch (e) { return; }
      dessiner();
    },
  };

  function demarrer() {
    messageGarde();
    pret.then(() => { tranche = true; dessiner(); },
              () => { tranche = true; ajusterBandeau(); });
    // La liste a changé (ici, dans l'Administration) : `theme.js` relit `BDProjets`
    // pendant l'envoi de l'événement, on relit derrière lui.
    document.addEventListener("bd:projets-maj", () => { lire().then(dessiner); });
    // Le projet courant a changé : la ligne, le bandeau et le bouton suivent.
    document.addEventListener(P.EVENEMENT, () => {
      if (!E.lu) return;
      E.courant = courantDe(E.projets);
      dessiner();
    });
    document.addEventListener("bd:portee-vide", () => { if (tranche) ajusterBandeau(); });
    document.addEventListener("bd:introuvable", verifierApresUnRefus);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarrer);
  else demarrer();
})();
