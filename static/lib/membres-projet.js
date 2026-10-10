/* « Qui y entre » (COL-3, tranche 1) — les membres d'UN projet, en module MONTABLE.

   Chargé en <script> APRÈS common.js et projet.js → expose `window.BDMembresProjet` ; aussi
   require()-able par `tests/js/membres-projet.test.js`. Il n'atteint le document qu'au
   MONTAGE : le charger ne lit ni `document`, ni `window.matchMedia`, ni l'adresse.

   C'EST LE FRÈRE DE `qui-entre.js`, PAS SA GÉNÉRALISATION. Les deux règlent « qui entre »,
   un étage d'écart, et se ressemblent exprès — la même ligne d'ajout, les mêmes notes sur
   l'annuaire. Mais un accès de collection est une échelle de niveaux, des actes et une case
   d'export, lus dans une description servie ; un membre de projet a un RÔLE parmi deux, et
   rien d'autre. Les fondre aurait fait porter à l'un les conditions de l'autre.

   CE QU'ÊTRE D'UN PROJET NE FAIT PAS, et le module le DIT à chaque montage : entrer dans un
   projet n'ouvre aucune de ses collections. Chacune garde son « Qui entre ».

   LE CONTRAT.

     BDMembresProjet.monter(cible, options) → { rafraichir, focaliser, demonter }

   `cible`               une <section> VIDE de l'hôte, DÉJÀ dans le document (sinon `monter`
                         lève). Le module l'INVESTIT : elle devient la partie « Qui y entre »
                         (classe, nom accessible), et `demonter` la rend vide. Monter deux
                         fois au même endroit remplace.
   `options.projet`      { id, nom, gerable } — la garde est celle de l'ACTE : sans `gerable`,
                         que le serveur calcule projet par projet, le module le dit et ne lit
                         rien.
   `options.groupesAdmin` `acces.groupes_admin` de `GET /api/moi`.
   `options.surMessage(ligne)`  appelé chaque fois que le module écrit sa ligne de message.
   `options.surChangement()`    appelé après un geste que le serveur a accepté.

   CE QUE LE MODULE NE FAIT PAS. Il ne cherche rien dans la page : il travaille dans SA
   section. Il n'efface aucun message ailleurs. Il ne lit ni l'adresse ni l'identité. En
   revanche il LIT ses propres données — `…/membres` et `…/membres/choix` —, sans quoi le
   contrat du serveur vivrait dans deux écrans.

   DEUX LECTURES, ET LA SECONDE N'ATTEND PAS. `…/membres` dessine la liste tout de suite ;
   `…/membres/choix`, qui lit l'annuaire, arrive après et remplit les marques et la liste des
   groupes. Un annuaire en panne ne retarde aucun geste.

   ON ENTRE MEMBRE, ON DEVIENT RESPONSABLE. « + Faire entrer » pose toujours le PREMIER rôle
   (`BDProjet.ROLES[0]`) ; nommer un responsable est un second geste, sur la ligne. Le `PUT`
   RE-POSE un rôle : faire entrer un nom déjà présent rétrograderait un responsable. L'écran
   le refuse avant d'envoyer, sur le couple (compte ou groupe, nom exact) — et le serveur
   refuse de son côté de rétrograder le DERNIER responsable. */
(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) {                    // Node (tests)
    const commun = require("./common.js");
    module.exports = factory({ esc: commun.escapeHtml, apiGet: commun.apiGet,
                               apiSend: commun.apiSend, BDProjet: require("./projet.js") });
  } else {
    root.BDMembresProjet = factory(root);                                   // navigateur
  }
})(typeof self !== "undefined" ? self : this, function (env) {
  "use strict";

  // Lus à l'APPEL, jamais au chargement : `env` est la fenêtre, et l'ordre des balises
  // <script> n'a pas à être deviné ici.
  const esc = (s) => env.esc(s);
  const projetLib = () => env.BDProjet;

  /* LES IDENTIFIANTS SONT PROPRES AU MONTAGE : le premier montage d'un projet garde le
     suffixe nu, un second montage VIVANT du même projet en reçoit un autre, et un montage
     dont la section a quitté le document ne retient rien — la règle de `qui-entre.js`, pour
     la même raison. */
  const SUFFIXES = new Map();          // suffixe → montage

  function prendreSuffixe(id, montage, vivant) {
    for (const [s, m] of SUFFIXES) if (!vivant(m)) SUFFIXES.delete(s);
    let s = String(id);
    for (let n = 2; SUFFIXES.has(s); n++) s = `${id}m${n}`;
    SUFFIXES.set(s, montage);
    return s;
  }

  /* Rendu par CELUI qui le tient, et par lui seul : un montage mort dont le suffixe a déjà
     été repris ne doit pas le retirer au vivant en se démontant après coup. */
  function rendreSuffixe(s, montage) {
    if (SUFFIXES.get(s) === montage) SUFFIXES.delete(s);
  }

  /* Quel montage occupe quelle cible : monter deux fois au même endroit REMPLACE. */
  const OCCUPANTS = new WeakMap();     // cible → montage

  /* Un administrateur règle tout projet sans en être membre : sans cette note, la liste
     mentirait par omission. Nommés d'après `/api/moi` ; rien en mono-poste, où l'on est seul. */
  function noteAdmin(groupes) {
    const g = groupes || [];
    if (!g.length) return "";
    return `<p class="col-note col-note-admin">Les administrateurs de l'instance
    (${g.map(esc).join(", ")}) règlent <strong>tout</strong> projet, sans figurer dans la
    liste de ses membres.</p>`;
  }

  function cle(a) {
    return `data-genre="${esc(a.genre)}" data-principal="${esc(a.principal)}"`;
  }

  function sel(a) {
    return `[data-genre="${CSS.escape(a.genre)}"][data-principal="${CSS.escape(a.principal)}"]`;
  }

  /* Le nom d'un membre, avec ce qu'il EST : l'icône pour l'œil, le mot pour le lecteur
     d'écran. « compte » et non « utilisateur » : le lexique de l'écran. */
  function qui(a) {
    const groupe = a.genre === "groupe";
    return `<span aria-hidden="true">${groupe ? "👥" : "👤"}</span> `
      + `<span class="sr-only">${groupe ? "groupe" : "compte"} </span>${esc(a.principal)}`;
  }

  /* Ce que l'annuaire dit d'un membre : « trouve », « inconnu », « non_verifie »,
     « sans_annuaire », ou null tant qu'il n'a pas répondu. */
  function verification(m, genre, principal) {
    const an = m.etat.annuaire;
    if (!an || !Array.isArray(an.membres)) return null;
    const par = genre === "groupe" ? "groupe" : "compte";
    const v = an.membres.find((x) => x.par === par
      && (par === "groupe" ? x.groupe : x.login) === principal);
    return v ? v.verification : null;
  }

  /* Les marques d'une ligne : ce que l'annuaire dit d'abord ; puis, pour un compte, qu'il n'a
     pas encore ouvert l'application — l'observation seule, qui ne distingue pas une faute de
     frappe d'un arrivant. */
  function signal(m, a) {
    const v = verification(m, a.genre, a.principal);
    const marques = [];
    if (v === "inconnu") marques.push(`<span class="mp-marque">inconnu de l'annuaire</span>`);
    else if (v === "non_verifie") marques.push(`<span class="mp-marque">non vérifié</span>`);
    if (a.jamais_vu === true && v !== "inconnu") {
      marques.push(`<span class="acces-jamais-vu">n'a pas encore ouvert l'application</span>`);
    }
    return marques.join(" ");
  }

  /* Le rôle d'une ligne, en `<select>` : deux valeurs, celles de `BDProjet.ROLES`, dans les
     mots de `libelleRole`. Un rôle INCONNU — une base retouchée à la main — s'affiche tel
     quel, en plus des deux autres, plutôt que d'être maquillé : le serveur le lit « membre »,
     l'écran n'a pas à le décider pour lui. */
  function roleHtml(a) {
    const lib = projetLib();
    const roles = lib.ROLES.includes(a.role) ? lib.ROLES : [...lib.ROLES, a.role];
    return `<select class="mp-role" ${cle(a)} aria-label="Rôle de ${esc(a.principal)}">`
      + roles.map((r) => `<option value="${esc(r)}"${r === a.role ? " selected" : ""}>`
        + `${esc(lib.libelleRole(r))}</option>`).join("") + `</select>`;
  }

  /* Une LISTE et non un tableau : trois choses par membre, qui se rangent en ligne quand la
     place est là et passent à la ligne sinon, sans cadre qui défile ni second rendu. */
  function listeHtml(m) {
    const etat = m.etat;
    if (etat.erreur) return `<p class="col-note">${esc(etat.erreur)}</p>`;
    if (!etat.membres) return `<p class="col-note">Chargement…</p>`;
    if (!etat.membres.length) {
      return `<p class="col-note">Personne n'est encore entré dans ce projet.</p>`;
    }
    return `<ul class="mp-liste">${etat.membres.map((a) => {
      const depuis = esc((a.date_creation || "").slice(0, 10));
      return `<li class="mp-ligne" ${cle(a)}>
        <span class="mp-qui">${qui(a)}</span>
        <span class="mp-signal">${signal(m, a)}</span>
        ${roleHtml(a)}
        ${depuis ? `<span class="mp-depuis">depuis le ${depuis}</span>` : ""}
        <button class="ghost small mp-sortir" type="button" ${cle(a)}
                aria-label="Faire sortir ${esc(a.principal)} du projet">✕</button></li>`;
    }).join("")}</ul>`;
  }

  /* Ce que la ligne d'ajout contenait, relevé avant de la redessiner : l'annuaire arrive
     APRÈS l'ouverture, et le nom qu'on a commencé à taper ne doit pas partir avec. */
  function releveAjout(sec) {
    const choix = sec.querySelector(".mp-choix");
    if (!choix) return null;
    return { choix: choix.value, touche: choix.dataset.touche === "1",
             nom: sec.querySelector(".mp-nom").value,
             genre: sec.querySelector(".mp-genre").value };
  }

  /* La ligne d'ajout, sur le patron de « Qui entre » : les GROUPES de l'annuaire (leurs noms
     seuls), puis la saisie libre, qui exige de dire « Compte » ou « Groupe » SANS valeur par
     défaut — un groupe entré comme compte ne ferait entrer personne. « Choisir… » en tête,
     sans quoi « + Faire entrer » ferait entrer le premier de la liste par inertie. */
  function ajoutHtml(m, garde) {
    const etat = m.etat;
    if (etat.erreur || !etat.membres) return "";
    const id = m.sfx;
    const an = etat.annuaire;
    const groupes = an && Array.isArray(an.groupes) ? an.groupes : [];
    const connues = new Set(["", "autre", ...groupes.map((g) => `groupe:${g}`)]);
    let choix, nom = "", genre = "", touche = false;
    if (garde && garde.touche && connues.has(garde.choix)) {
      ({ choix, nom, genre, touche } = garde);
    } else if (garde && garde.choix === "autre" && (garde.nom || garde.genre)) {
      ({ choix, nom, genre } = garde);
    } else {
      choix = groupes.length ? "" : "autre";
    }
    const opt = (v, lib) => `<option value="${esc(v)}"${v === choix ? " selected" : ""}>${esc(lib)}</option>`;
    return `<div class="mp-ajout-ligne">
      <label for="mp-choix-${id}">Faire entrer</label>
      <select id="mp-choix-${id}" class="mp-choix"${touche ? ' data-touche="1"' : ""}>
        ${opt("", "Choisir…")}
        ${groupes.length ? `<optgroup label="Groupes de l'annuaire">${groupes.map((g) =>
          opt(`groupe:${g}`, g)).join("")}</optgroup>` : ""}
        ${opt("autre", "Un compte, ou un groupe absent de la liste…")}
      </select>
      <span class="mp-libre"${choix === "autre" ? "" : " hidden"}>
        <input id="mp-nom-${id}" class="mp-nom" placeholder="nom exact"
               autocomplete="off" aria-label="Nom exact du compte ou du groupe"
               value="${esc(nom)}">
        <select id="mp-genre-${id}" class="mp-genre" aria-label="Compte ou groupe">
          <option value=""${genre ? "" : " selected"}>Compte ou groupe ?</option>
          <option value="utilisateur"${genre === "utilisateur" ? " selected" : ""}>Compte</option>
          <option value="groupe"${genre === "groupe" ? " selected" : ""}>Groupe</option>
        </select>
      </span>
      <button class="primary small mp-faire-entrer" type="button">+ Faire entrer</button>
    </div>`;
  }

  /* Ce qui vaut TOUJOURS, sous la ligne de message : ce qu'entrer ne fait pas, l'état de
     l'annuaire, le pouvoir des administrateurs. */
  function notesHtml(m) {
    const notes = [`<p class="col-note mp-n-ouvre-rien">Entrer dans le projet n'ouvre pas ses
      collections : chacune garde son « Qui entre ».</p>`];
    const an = m.etat.annuaire && m.etat.annuaire.annuaire;
    if (an && an.etat === "non_verifie") {
      notes.push(`<p class="col-note mp-annuaire-note">L'annuaire ne répond pas : impossible de
      proposer ses groupes, ni de vérifier le nom que vous tapez. Le nom entrera tel quel, et
      sera marqué « non vérifié ».</p>`);
    } else if (an && an.etat === "sans_annuaire") {
      notes.push(`<p class="col-note">Aucun annuaire n'est configuré : on fait entrer par un
      nom, que l'application ne peut pas vérifier. Un compte qui n'a pas encore ouvert
      l'application est signalé ; un nom de groupe ne peut pas l'être.</p>`);
    } else if (an && an.etat === "erreur") {
      notes.push(`<p class="col-note">La lecture de l'annuaire a échoué (${esc(an.motif)}) : la
      liste des groupes et les vérifications manquent. On fait entrer quand même par un
      nom.</p>`);
    }
    notes.push(noteAdmin(m.options.groupesAdmin));
    return `<div class="mp-notes-bloc">${notes.filter(Boolean).join("")}</div>`;
  }

  /* Vivant : monté, et sa section encore dans le document. */
  function vivant(m) {
    return !!(m && m.monte && m.sec && m.sec.isConnected);
  }

  /* Redessine ce qui dépend des données, jamais la ligne de message : un refus du serveur
     reste à l'écran après que la liste est revenue à ce qu'il a gardé. */
  function rendre(m) {
    if (!vivant(m)) return;
    const sec = m.sec;
    const garde = releveAjout(sec);
    sec.querySelector(".mp-membres").innerHTML = listeHtml(m);
    sec.querySelector(".mp-ajout").innerHTML = ajoutHtml(m, garde);
    sec.querySelector(".mp-notes").innerHTML = notesHtml(m);
  }

  /* La ligne de message du module, et elle seule. L'hôte est PRÉVENU à chaque écriture — y
     compris d'un message vide, qui est ce qu'un geste abouti écrit. */
  function dire(m, texte, erreur) {
    if (!m.sec) return;
    const l = m.sec.querySelector(".mp-msg");
    l.textContent = texte || "";
    // `erreur` vaut `true` pour un refus, « alerte » pour ce qui a RÉUSSI mais doit se lire.
    l.classList.toggle("erreur", erreur === true);
    l.classList.toggle("alerte", erreur === "alerte");
    if (typeof m.options.surMessage === "function") m.options.surMessage(l);
  }

  /* Les refus du serveur sont RENDUS, jamais avalés : le 409 qui nomme le dernier
     responsable, le 403 de qui ne gère plus ce projet. */
  async function tenter(m, fn) {
    try { await fn(); dire(m, ""); return true; }
    catch (e) { dire(m, e.message || "Échec", true); return false; }
  }

  /* Le focus, rendu APRÈS le rechargement qui suit un geste — le contrôle actionné a été
     détruit par le rendu. Seulement à qui ne l'a pas repris entre-temps. */
  function rendreFocus(m, cible) {
    if (!cible || !vivant(m)) return;
    const doc = m.sec.ownerDocument;
    if (doc.activeElement && doc.activeElement !== doc.body) return;
    const el = m.sec.querySelector(cible);
    if (el) el.focus();
  }

  const routeMembres = (m) => `/api/projets/${m.p.id}/membres`;

  async function lireMembres(m) {
    try {
      m.etat.membres = await env.apiGet(routeMembres(m));
      m.etat.erreur = null;
    } catch (e) { m.etat.erreur = e.message || "Les membres n'ont pas pu être lus."; }
  }

  async function lireAnnuaire(m) {
    try { m.etat.annuaire = await env.apiGet(`${routeMembres(m)}/choix`); }
    catch (e) {
      m.etat.annuaire = { annuaire: { etat: "erreur", motif: e.message || "échec" },
                          groupes: null, membres: [] };
    }
    return m.etat.annuaire;
  }

  /* À l'ouverture : la liste dès que les membres sont là, les marques quand l'annuaire répond. */
  async function ouvrir(m) {
    m.etat.annuaire = null;
    await lireMembres(m);
    rendre(m);
    await lireAnnuaire(m);
    rendre(m);
  }

  /* Après un geste : relire dans les DEUX cas, et dessiner ce que le serveur a enregistré
     plutôt que ce qu'on a cliqué. */
  async function apres(m, cible) {
    if (!vivant(m)) return;            // démonté pendant le geste : plus rien à relire ici
    await lireMembres(m);
    rendre(m);
    rendreFocus(m, cible);
  }

  /* L'hôte n'est prévenu que d'un geste ABOUTI, et EN DERNIER. */
  function changement(m, abouti) {
    if (abouti && typeof m.options.surChangement === "function") m.options.surChangement();
  }

  function membreDe(m, el) {
    return (m.etat.membres || []).find((a) => a.genre === el.dataset.genre
      && a.principal === el.dataset.principal);
  }

  /* Changer le rôle d'une ligne : nommer un responsable, ou le rétrograder. Le MÊME geste
     pour le serveur que « faire entrer » — un `PUT` qui pose un rôle. */
  async function gesteRole(m, select) {
    const a = membreDe(m, select);
    if (!a) { rendre(m); return; }
    const ok = await tenter(m, () => env.apiSend("PUT", routeMembres(m),
      { genre: a.genre, principal: a.principal, role: select.value }));
    await apres(m, `.mp-role${sel(a)}`);
    changement(m, ok);
  }

  async function sortir(m, bouton) {
    const a = membreDe(m, bouton);
    if (!a) return;
    const ok = await tenter(m, () => env.apiSend("DELETE",
      `${routeMembres(m)}/${encodeURIComponent(a.genre)}/${encodeURIComponent(a.principal)}`));
    // La ligne disparaît avec son bouton : le focus va au titre de la partie. Sur un refus,
    // la ligne reste, et le focus retrouve son bouton.
    await apres(m, ok ? ".mp-titre" : `.mp-sortir${sel(a)}`);
    changement(m, ok);
  }

  async function faireEntrer(m) {
    const sec = m.sec, p = m.p;
    const choix = sec.querySelector(".mp-choix").value;
    let genre, principal;
    if (!choix) {
      dire(m, "Choisissez un groupe dans la liste, ou « Un compte, ou un groupe absent de "
              + "la liste… ».", true);
      return;
    }
    if (choix === "autre") {
      principal = sec.querySelector(".mp-nom").value.trim();
      genre = sec.querySelector(".mp-genre").value;
      if (!principal) { dire(m, "Tapez le nom exact du compte ou du groupe.", true); return; }
      if (!genre) {
        dire(m, `Dites si « ${principal} » est un compte ou un groupe : un groupe entré `
             + "comme compte ne ferait entrer personne.", true);
        return;
      }
    } else {
      genre = "groupe";
      principal = choix.slice("groupe:".length);
    }
    const nomme = genre === "groupe" ? "Le groupe" : "Le compte";
    // Le couple, et non le nom seul : un compte et un groupe de même nom sont deux membres.
    if ((m.etat.membres || []).some((a) => a.genre === genre && a.principal === principal)) {
      dire(m, `${nomme} ${principal} est déjà du projet « ${p.nom} » : son rôle se règle `
           + "sur sa ligne.", true);
      return;
    }
    const premier = projetLib().ROLES[0];
    const ok = await tenter(m, () => env.apiSend("PUT", routeMembres(m),
      { genre, principal, role: premier }));
    if (!ok) return;
    // Démonté pendant l'aller-retour : le membre est entré, il n'y a plus de ligne d'ajout
    // à vider ni de message à écrire.
    if (!vivant(m)) { changement(m, true); return; }
    // La ligne d'ajout repart à vide : le nom est entré, le garder inviterait à le renvoyer.
    const choixEl = sec.querySelector(".mp-choix");
    choixEl.value = "";
    delete choixEl.dataset.touche;
    sec.querySelector(".mp-nom").value = "";
    sec.querySelector(".mp-genre").value = "";
    await apres(m, ".mp-choix");
    const an = await lireAnnuaire(m);
    rendre(m);
    if (!vivant(m)) { changement(m, true); return; }
    const v = verification(m, genre, principal);
    if (v === "inconnu") {
      dire(m, `${nomme} ${principal} n'est pas dans l'annuaire : il est inscrit au projet, `
           + "mais personne n'y entrera tant que ce nom n'y existe pas.", "alerte");
    } else if (v === "non_verifie" || (an && an.annuaire && an.annuaire.etat === "erreur")) {
      dire(m, `${nomme} ${principal} entre dans le projet « ${p.nom} » — non vérifié : `
           + "l'annuaire ne répondait pas.", "alerte");
    } else {
      dire(m, `${nomme} ${principal} entre dans le projet « ${p.nom} », comme `
           + `${projetLib().libelleRole(premier)}. Aucune collection ne lui est ouverte `
           + "pour autant.");
    }
    changement(m, true);
  }

  /* LE MODULE INVESTIT LA CIBLE, il n'y loge pas une section de plus : elle DEVIENT la partie
     « Qui y entre », reçoit la classe, l'identité du projet et son nom accessible. */
  function investir(m) {
    const sec = m.cible;
    sec.classList.add("mp");
    sec.dataset.mp = String(m.p.id);
    sec.setAttribute("aria-labelledby", `mp-titre-${m.sfx}`);
    sec.innerHTML = `
      <h4 class="mp-titre" id="mp-titre-${m.sfx}" tabindex="-1">Qui y entre</h4>
      <div class="mp-membres"><p class="col-note">Chargement…</p></div>
      <div class="mp-ajout"></div>
      <p class="col-msg muted small mp-msg" role="status" aria-live="polite"></p>
      <div class="mp-notes"></div>`;
    m.sec = sec;
  }

  /* Les gestes, délégués sur la SECTION du montage : ses parties naissent et meurent à
     chaque rendu, elle reste. Retenus pour être RETIRÉS : la cible appartient à l'hôte. */
  function brancher(m) {
    const sec = m.sec;
    const ecouter = (type, fn) => { sec.addEventListener(type, fn); m.ecouteurs.push([type, fn]); };
    ecouter("change", (ev) => {
      const t = ev.target;
      if (!t.matches) return;
      if (t.matches(".mp-role")) gesteRole(m, t);
      else if (t.matches(".mp-choix")) {
        t.dataset.touche = "1";
        const libre = sec.querySelector(".mp-libre");
        libre.hidden = t.value !== "autre";
        if (!libre.hidden) libre.querySelector(".mp-nom").focus();
      }
    });
    ecouter("click", (ev) => {
      const b = ev.target.closest && ev.target.closest("button");
      if (!b || !sec.contains(b)) return;
      if (b.classList.contains("mp-sortir")) sortir(m, b);
      else if (b.classList.contains("mp-faire-entrer")) faireEntrer(m);
    });
    ecouter("keydown", (ev) => {
      if (ev.key === "Enter" && ev.target.matches && ev.target.matches(".mp-nom")) {
        ev.preventDefault();
        faireEntrer(m);
      }
    });
  }

  /* Rend la cible telle qu'elle a été reçue : vidée, sans la classe ni les attributs posés
     en l'investissant, sans écouteur. Seulement si elle est encore à CE montage. */
  function demonter(m) {
    if (!m.monte) return;
    m.monte = false;
    if (m.sfx != null) rendreSuffixe(m.sfx, m);
    if (m.sec) for (const [type, fn] of m.ecouteurs) m.sec.removeEventListener(type, fn);
    m.ecouteurs = [];
    if (OCCUPANTS.get(m.cible) === m) {
      OCCUPANTS.delete(m.cible);
      m.cible.innerHTML = "";
      if (m.sec) {
        m.cible.classList.remove("mp");
        delete m.cible.dataset.mp;
        m.cible.removeAttribute("aria-labelledby");
      }
    }
    m.sec = null;
  }

  function monter(cible, options) {
    // La cible est DANS le document : « vivant » se lit à cela. Montée hors du document, la
    // partie passerait pour morte dès sa naissance et resterait sur « Chargement… » ; une
    // erreur le dit tout de suite, là où le silence ne le dirait jamais.
    if (!cible || !cible.isConnected) {
      throw new Error("BDMembresProjet.monter : la cible doit être dans le document.");
    }
    const o = options || {};
    const p = o.projet || {};
    const precedent = OCCUPANTS.get(cible);
    if (precedent) demonter(precedent);
    const m = { cible, options: o, p, monte: true, sec: null, sfx: null, ecouteurs: [],
                etat: { membres: null, erreur: null, annuaire: null } };
    OCCUPANTS.set(cible, m);
    const poignee = {
      rafraichir: async () => {
        if (!vivant(m)) return;
        await lireMembres(m);
        rendre(m);
        await lireAnnuaire(m);
        rendre(m);
      },
      /* Le focus sur le titre de la partie. Rend `false` quand il n'y a rien à viser. */
      focaliser: () => {
        const t = vivant(m) && m.sec.querySelector(".mp-titre");
        if (!t) return false;
        t.scrollIntoView({ block: "start" });
        t.focus();
        return true;
      },
      demonter: () => demonter(m),
    };
    if (!p.gerable) {
      // La liste des membres est une donnée sur des PERSONNES : un simple membre ne la voit
      // pas, et le serveur la lui refuse. Le module le DIT au lieu de se taire.
      cible.innerHTML = `<p class="col-note">Seul un responsable du projet voit et règle qui y
        entre.</p>${noteAdmin(o.groupesAdmin)}`;
      return poignee;
    }
    m.sfx = prendreSuffixe(p.id, m, vivant);
    investir(m);
    brancher(m);
    ouvrir(m);
    return poignee;
  }

  return { monter, noteAdmin, _suffixes: { prendre: prendreSuffixe, rendre: rendreSuffixe } };
});
