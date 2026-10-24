/* ===================================================================
   BéDéditeur — page Bibliothèque (vanilla JS)

   UX-18 — UNE LISTE ET UNE FICHE, côte à côte, le gabarit `lf-` de l'Administration. La
   liste porte les deux usages de la page (tranché par Hugo le 2026-10-16) : CHERCHER un
   album — les albums du projet courant, chacun nommant ses collections — et RÉGLER une
   collection — le bloc « Collections », où la case FILTRE le corpus (la collection est un
   calque posé sur lui) et le nom OUVRE la fiche. La fiche est celle du projet, d'une
   collection (quatre onglets : Albums · Qui entre · Description · Diffusion et dépôt),
   d'une comparaison quand deux calques sont cochés, ou d'un album, qui s'ouvre À LA PLACE
   de la collection d'où l'on vient. L'objet ouvert est dans l'adresse.

   La logique pure — le calque, le tri, les droits d'un album (l'union de ses collections),
   les actes d'une collection, la comparaison, l'adresse — vit dans `lib/bibliotheque.js`,
   sous table de vérité Node. Rien ici n'est une garde : le serveur tranche chaque geste, et
   chaque BLOC de la fiche pose sa propre question (leçon d'AUTH-4), jamais l'onglet.
   =================================================================== */
"use strict";

// $, apiGet, apiSend, esc, toast : lib/common.js (chargé avant ce script).
const PASSES = ["segmenter", "bulles", "ocr"];
const PASSES_LBL = { segmenter: "Segmenter", bulles: "Bulles", ocr: "OCR" };

const state = {
  albums: [],               // les albums de TRAVAIL du projet courant (lib/projet.js)
  openId: null,             // l'album dont la fiche est ouverte
  planches: [],
  checkedAlbums: new Set(), // la sélection d'albums, dans l'onglet Albums d'une collection
  checkedPlanches: new Set(), // la sélection de planches, dans la fiche de l'album ouvert
  passes: new Set(),        // les passes cochées, gardées d'un lot à l'autre
  editingId: null,
  jobTimer: null,
  relFilter: "",            // ANN-4 : filtre de relecture de la fiche d'album ("" = toutes)
};

/* Ce que la Bibliothèque montre, hors des données : le calque, le tri, l'objet ouvert. */
const B = {
  calques: new Set(),       // les collections cochées : elles filtrent la liste des albums
  mode: "une",              // deux calques ou plus : « une » (union) ou « toutes »
  filtre: "",               // ce qu'on cherche dans les albums
  tri: "alpha",             // l'ordre des collections : « alpha » ou « recents »
  ouverte: null,            // la collection ouverte par son NOM ou par l'adresse
  onglet: BDBiblio.ONGLET_PAR_LE_NOM,
  depuis: null,             // la collection d'où l'album ouvert a été ouvert : le retour
  vueFiche: false,          // sous le seuil étroit, la fiche REMPLACE la liste
  edition: null,            // l'onglet dont le formulaire est ouvert : « description » | « diffusion »
  total: false,             // portée totale (`acces.total`) : le total du projet se dit
  perdues: null,            // { n, titre } : la sélection de planches vidée en changeant d'album
};

/* 40em : le seuil de « Comptes et groupes » (`CG_ETROIT`, administration.js) et de la
   feuille (`.lf` sous 40em). Au-dessous, une colonne à la fois. */
const ETROIT = window.matchMedia("(max-width: 40em)");

// Libellés du statut de relecture (ANN-4). Clés = valeurs backend.
const RELECTURE_LBL = { a_faire: "à faire", en_cours: "en cours", faite: "faite" };

const pluriel = (n, un, plus) => `${n} ${n > 1 ? (plus || un + "s") : un}`;

/* La première lecture des albums : l'adresse l'attend avant d'ouvrir un album qu'elle nomme. */
let ALBUMS_PRETS = Promise.resolve();

/* COL-4 — les chiffres de la Bibliothèque suivent le projet courant QUAND C'EST UN BAC À
   SABLE (relevé sur la maquette : « 0 albums » dans un bac tout neuf) : `?bac_a_sable=<id>`.
   Hors d'un bac à sable, ceux du corpus, comme la Recherche et l'Exploration, aveugles aux
   bacs (S8). */
function routeCorpus() {
  const p = PROJETS.find((x) => x.id === PROJET);
  return p && p.bac_a_sable ? `/api/corpus?bac_a_sable=${p.id}` : "/api/corpus";
}

/* Stats de corpus en bande 2 (mêmes chips que Recherche / Exploration — source
   /api/corpus). Aperçu non bloquant. */
async function loadCorpus() {
  try {
    const c = await apiGet(routeCorpus());
    $("#corpus-stats").innerHTML = [
      ["albums", "albums"], ["planches", "planches"], ["regions", "régions"],
      ["transcrites", "transcrites"], ["annotees", "annotées"], ["tags", "tags"],
    ].map(([k, lbl]) => `<span class="stat"><b>${c[k]}</b> ${lbl}</span>`).join("");
  } catch (e) { /* non bloquant */ }
}

/* ═══════════════════════════════════════════════════════════════════════════
   La liste — les albums du projet courant
   ═══════════════════════════════════════════════════════════════════════════ */

async function loadAlbums(compter = true) {
  // COL-3 — les albums de TRAVAIL du projet courant, et eux seuls : la liste, donc le lot
  // qui part de leur sélection. Une copie GARDÉE AU FONDS n'en est jamais une — elle se règle
  // dans l'Administration — et un album d'un autre projet ne se montre pas ici : dans un
  // projet neuf, la liste est vide. La règle est dans `lib/projet.js`. Des filtres d'écran,
  // pas des gardes : le serveur rend toujours tout ce qu'on lit. Le projet est lu APRÈS la
  // liste, pour filtrer sur sa valeur au moment où la liste arrive — l'adresse a pu le faire
  // basculer entre-temps. Il est lu SANS la ligne « Dans le projet … », qui se dessine avec
  // la liste des collections qu'elle nomme, pas avant elle.
  const lus = await apiGet("/api/albums");
  await lireProjet();
  state.albums = BDProjet.albumsDuProjet(lus, PROJET);
  const ids = new Set(state.albums.map((a) => a.id));
  state.checkedAlbums.forEach((id) => { if (!ids.has(id)) state.checkedAlbums.delete(id); });
  rendreListeAlbums();
  if (state.openId !== null && ids.has(state.openId)) await openAlbum(state.openId, { garder: true });
  else if (state.openId !== null) fermerAlbum();
  else rafraichirFicheApresAlbums();
  loadSynthese();
  // COL-2 : le décompte d'albums bouge. Pas quand le projet vient de changer (`compter`
  // faux) : la liste des collections se redessine déjà.
  if (compter) rafraichirCollections();
}

/* Badge « validées / total » avec mini-barre (vert si tout est validé). */
function validBadge(n, total) {
  const pct = total ? Math.round(100 * n / total) : 0;
  const cls = total && n === total ? "all" : "";
  return `<span class="val-album ${cls}" title="${n}/${total} planche(s) validée(s)">`
       + `${n}/${total}<i class="val-mini"><i style="width:${pct}%"></i></i></span>`;
}

/* La liste des albums, filtrée par le calque et la recherche. Chaque album nomme ses
   collections — celles qu'on lit, et celles qui sont cochées ressortent. Une demande de
   suppression qui attend se lit sur la ligne. Le compte ne dit le total du projet qu'à une
   portée totale (« 404, jamais 403 »). */
function rendreListeAlbums() {
  const corps = $("#albums-body");
  const vus = BDBiblio.filtrerAlbums(state.albums, { calques: B.calques, mode: B.mode,
                                                     texte: B.filtre });
  const filtre = B.calques.size > 0 || B.filtre.trim() !== "";
  $("#bi-compte").textContent = BDBiblio.libelleAlbums(vus.length, {
    total: B.total, sur: filtre ? state.albums.length : undefined });
  if (!state.albums.length) {
    corps.innerHTML = `<li class="lf-vide muted small">Aucun album dans ce projet.</li>`;
    return;
  }
  if (!vus.length) {
    corps.innerHTML = `<li class="lf-vide muted small">Aucun album ne répond.</li>`;
    return;
  }
  corps.innerHTML = vus.map((a) => {
    const cols = (a.collections || []).map((c) =>
      `<span class="${B.calques.has(c.id) ? "sur-actif" : ""}">${esc(c.nom)}</span>`).join(" · ");
    const pastille = BDSuppression.pastille(a.demande, MOI.login);
    return `<li><button type="button" class="lf-objet album-row" data-id="${a.id}"
        ${a.id === state.openId ? 'aria-current="true"' : ""}>
      ${serieTome(a) ? `<span class="lf-serie">${esc(serieTome(a))}</span>` : ""}
      <span class="lf-nom c-titre">${esc(a.titre)}</span>
      <span class="lf-etat${a.demande ? " alerte" : ""}">${a.demande ? "⚠ " : ""}${pluriel(a.nb_planches, "pl.", "pl.")}</span>
      ${cols ? `<span class="lf-detail">${cols}</span>` : ""}
      ${pastille ? `<span class="sp-pastille">${esc(pastille)}</span>` : ""}
    </button></li>`;
  }).join("");
}

/* La demande de suppression qui attend, sur une ligne d'album — un état marqué là où l'on
   agit. Le nom est celui que le serveur rend ; s'il n'en rend pas, la pastille n'en suppose
   aucun. */
function pastilleDemande(a) {
  const texte = BDSuppression.pastille(a.demande, MOI.login);
  return texte ? ` <span class="sp-pastille">${esc(texte)}</span>` : "";
}

/* ═══════════════════════════════════════════════════════════════════════════
   La liste — le bloc « Collections »
   ═══════════════════════════════════════════════════════════════════════════ */

/* COL-3 — LE PROJET COURANT BORNE la liste des collections, le projet où « + Créer une
   collection » crée, les collections proposées à un album qu'on CRÉE et la liste des
   albums, donc le lot. La fiche d'un album existant suit le projet de l'ALBUM, pas le
   courant (`rangementDeLAlbum`).

   Il se lit comme la bande le lit — la règle est dans `lib/projet.js`, pour que les deux
   désignent le même projet —, sur la même liste (`window.BDProjets`, demandée une fois par
   page). Sans liste lisible, `PROJET` reste nul : rien n'est filtré, rien n'est nommé, et
   créer n'envoie aucun projet — l'écran d'avant, plutôt qu'une liste vidée par une panne
   qui ne la concerne pas. CE N'EST PAS UNE GARDE. */
let PROJET = null;                // l'identifiant du projet courant
let PROJETS = [];                 // ceux qu'on peut nommer

async function lireProjet() {
  const projets = await Promise.resolve(window.BDProjets).catch(() => null);
  PROJETS = Array.isArray(projets) ? projets : [];
  // Ce que la PAGE a retenu prime sur le stockage, une fois qu'elle a choisi : quand il
  // refuse d'écrire, le choix vaut encore pour elle.
  PROJET = BDProjet.courant(PROJETS, PROJET === null ? BDProjet.lire() : PROJET);
}

async function lireProjetCourant() {
  await lireProjet();
  colDireProjet();
}

function colNomProjet() {
  const p = PROJETS.find((x) => x.id === PROJET);
  return p ? p.nom : null;
}

/* La ligne au-dessus du cadre : de quel projet sont ces collections et ces albums. */
function colDireProjet() {
  const ligne = $("#collections-projet");
  const nom = colNomProjet();
  ligne.hidden = nom === null;
  ligne.textContent = nom === null ? "" : `Dans le projet « ${nom} »`;
}

/* Les collections lues, et celles du projet courant dans l'ordre choisi. */
const COLS = { toutes: [], projet: [] };
let COLS_RENDUES = false;

function collection(id) {
  return COLS.toutes.find((c) => c.id === Number(id)) || null;
}

/* Les collections lues, sans attendre que leur liste soit dessinée : la fiche d'un album en
   a besoin pour dire ce qu'on peut y faire (l'union de ses collections), et elle peut
   s'ouvrir avant que la liste ait lu les siennes — la liste se dessine après l'état
   ShareDocs. Lues une fois, puis tenues à jour par la liste. */
let COLS_LUES = false;
async function collectionsLues() {
  if (COLS_LUES) return COLS.toutes;
  try { COLS.toutes = await apiGet("/api/collections"); COLS_LUES = true; }
  catch (e) { /* la fiche dira ce qu'elle peut : sans collections, aucun geste d'écriture */ }
  return COLS.toutes;
}

/* La pastille de rôle, déménagée de l'Administration avec les accès. « propriétaire » au
   DERNIER cran de l'échelle, lu dans la description et non écrit ici ; « administrateur »
   pour qui administre sans figurer dans les accès — un pouvoir qu'on déclare (AUTH-4), et
   jamais en mono-poste, où il n'y a qu'un rôle. Le libellé porte le sens (WCAG 1.4.1). */
function colBadge(c) {
  if (DROITS && c.mon_niveau
      && BDDroits.rang(DROITS, c.mon_niveau) === DROITS.echelle.length - 1) {
    return `<span class="col-niveau est-proprietaire">propriétaire</span>`;
  }
  if (c.administrable && !c.mon_niveau && (MOI.groupes_admin || []).length) {
    return `<span class="col-niveau">administrateur</span>`;
  }
  return "";
}

/* La collection dont la fiche est montrée : par son nom, par l'adresse, ou parce qu'elle
   est le SEUL calque coché. */
function collectionMontree() {
  if (state.openId !== null) return null;
  if (B.ouverte !== null) return B.ouverte;
  return B.calques.size === 1 ? [...B.calques][0] : null;
}

function rendreListeCollections() {
  const corps = $("#col-body");
  const montree = collectionMontree();
  COLS.projet = BDBiblio.trierCollections(BDProjet.duProjet(COLS.toutes, PROJET), B.tri);
  const nomProjet = colNomProjet();
  $("#collections-titre").textContent = `Collections · ${COLS.projet.length}`;
  document.querySelectorAll("#collections-bloc [data-tri]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.tri === B.tri)));
  const tout = $("#calques-tout");
  tout.hidden = !B.calques.size;
  tout.textContent = B.total ? "Tout le projet" : "Tout ce que vous lisez";
  const mode = $("#calques-mode");
  mode.hidden = B.calques.size < 2;
  mode.querySelectorAll("[data-mode]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.mode === B.mode)));
  if (!COLS.projet.length) {
    // Une portée VIDE a déjà son bandeau (`theme.js`), qui dit à qui s'adresser : la liste
    // ne le double pas d'un second « rien », elle dit seulement ce qu'on peut faire. Qui lit
    // des collections ailleurs, lui, apprend que c'est CE projet qui est vide pour lui.
    const ou = COLS.toutes.length && nomProjet !== null ? ` dans le projet « ${esc(nomProjet)} »` : "";
    const promesse = B.total ? "" : " : vous en serez propriétaire";
    corps.innerHTML = PORTEE_VIDE
      ? `<li class="col-note">Créez une collection${promesse}.</li>`
      : `<li class="col-note">Aucune collection ouverte pour vous${ou}. Créez-en une${promesse}.</li>`;
    return;
  }
  corps.innerHTML = COLS.projet.map((c) => {
    const courante = c.id === montree;
    return `<li class="col-item${courante ? " courante" : ""}" data-id="${c.id}">
      <input type="checkbox" class="col-calque" data-calque="${c.id}" ${B.calques.has(c.id) ? "checked" : ""}
             aria-label="Filtrer les albums sur « ${esc(c.nom)} »" title="Filtrer les albums sur cette collection">
      <button type="button" class="col-nom col-ouvrir" data-ouvrir-col="${c.id}"
              ${courante ? 'aria-current="true"' : ""} title="Ouvrir la fiche de la collection">${esc(c.nom)}</button>
      ${c.base ? `<span class="col-base" title="La collection de base du projet">base</span>` : ""}
      ${colBadge(c)}
      ${marqueRecues(c)}
      <span class="col-nb">${nbAlbumsCourt(c.nb_albums)}</span>
    </li>`;
  }).join("");
}

/* Le décompte d'une ligne de collection : le nombre seul à l'écran, la phrase entière pour
   qui l'entend — « 3 » ne dirait rien, lu à voix haute. */
function nbAlbumsCourt(n) {
  return `<span aria-hidden="true">${n}</span><span class="sr-only">${pluriel(n, "album")}</span>`;
}

/* Vrai pour une portée VIDE : aucune collection ouverte, et pas de portée totale — l'état où
   `theme.js` pose son bandeau. Lu dans `GET /api/moi`. */
let PORTEE_VIDE = false;

async function chargerCollections(opts = {}) {
  await DROITS_PRETS;
  MOI = await identite();
  const moi = await Promise.resolve(window.BDMoi).catch(() => null);
  B.total = !!(moi && moi.acces && moi.acces.total);
  PORTEE_VIDE = !!(moi && moi.acces && !moi.acces.total && moi.acces.collections === 0);
  await lireProjetCourant();
  let toutes;
  try { toutes = await apiGet("/api/collections"); }
  catch (e) {
    // L'erreur prend la place de la LISTE, et la fiche reste telle qu'elle est : le message
    // du dernier geste y survit — un « enregistrée » qui disparaîtrait derrière l'erreur
    // ferait croire raté un enregistrement qui a eu lieu.
    $("#col-body").innerHTML = `<li class="col-note col-erreur-lecture">${esc(e.message)}</li>`;
    return false;
  }
  COLS.toutes = toutes;
  COLS_LUES = true;
  // COL-3 — L'ADRESSE GAGNE. `?collection=<id>` peut nommer une collection d'un AUTRE projet
  // que le courant : c'est la cible des liens de l'Administration, qui ne sait rien du
  // projet où l'on travaille. Sans cette bascule, la collection ne serait pas dans la liste
  // filtrée. `PROJET` est posé AVANT de prévenir : l'écoute de cette page reconnaît son
  // propre choix et ne recharge pas une seconde fois. La liste des albums suit.
  if (opts.basculerVers != null) {
    const visee = toutes.find((c) => c.id === opts.basculerVers);
    const vers = BDProjet.basculeVers(PROJETS, PROJET, visee ? visee.projet_id : null);
    if (vers !== null) {
      PROJET = vers;
      colDireProjet();
      BDProjet.choisir(PROJET);
      await loadAlbums(false).catch(() => {});
    }
  }
  // Ce qui n'est plus lisible ne reste ni coché, ni ouvert.
  const lues = new Set(BDProjet.duProjet(toutes, PROJET).map((c) => c.id));
  [...B.calques].forEach((id) => { if (!lues.has(id)) B.calques.delete(id); });
  COLS_RENDUES = true;
  rendreListeCollections();
  rendreListeAlbums();
  // COL-3, tranche 3a — ce qui attend une réponse : non bloquant, et redessiné à l'arrivée.
  chargerDemandesRecues();
  chargerMesDemandes();
  return true;
}

/* Après un geste sur les ALBUMS — créer, supprimer, ranger —, seuls les décomptes bougent :
   on ne redessine pas la fiche, ce qui replierait un formulaire en cours de saisie et
   perdrait ce qu'on y a tapé. On ne reconstruit la liste que si l'ensemble des collections a
   changé (la première création d'album peut en faire naître une). */
async function rafraichirCollections() {
  if (!COLS_RENDUES) return;
  let toutes;
  try { toutes = await apiGet("/api/collections"); } catch (e) { return; }
  const avant = BDProjet.duProjet(COLS.toutes, PROJET).map((c) => c.id).sort().join(",");
  COLS.toutes = toutes;
  const apres = BDProjet.duProjet(toutes, PROJET).map((c) => c.id).sort().join(",");
  if (avant !== apres) { rendreListeCollections(); return; }
  for (const c of toutes) {
    const n = document.querySelector(`#col-body .col-item[data-id="${c.id}"] .col-nb`);
    if (n) n.innerHTML = nbAlbumsCourt(c.nb_albums);
  }
  const f = $("#col-fiche");
  if (f) {
    const c = collection(f.dataset.id);
    const nb = f.querySelector(".col-fiche-nb");
    if (c && nb) nb.textContent = pluriel(c.nb_albums, "album");
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
   La fiche — ce qu'elle montre, et l'adresse qui le dit
   ═══════════════════════════════════════════════════════════════════════════ */

/* Ce que la fiche montre : l'album ouvert, sinon la collection ouverte (ou le seul calque
   coché), sinon la comparaison de deux calques ou plus, sinon le projet. */
function ficheCourante() {
  if (state.openId !== null) return { genre: "album", id: state.openId };
  const c = collectionMontree();
  if (c !== null) return { genre: "collection", id: c };
  if (B.calques.size > 1) return { genre: "comparaison" };
  return { genre: "accueil" };
}

/* L'adresse de ce qui est ouvert. Un geste qui ouvre quelque chose POUSSE une entrée, pour
   que « Retour » le défasse ; changer d'onglet la remplace. */
function ecrireAdresse(pousser) {
  const f = ficheCourante();
  const etat = {
    collection: f.genre === "collection" ? f.id : (f.genre === "album" ? B.depuis : null),
    album: f.genre === "album" ? f.id : null,
    onglet: B.onglet,
    groupe: PRESELECTION && f.genre === "collection" && PRESELECTION.id === f.id
      ? PRESELECTION.groupe : null,
  };
  const s = BDBiblio.ecrireAdresse(etat, location.search);
  const url = `${location.pathname}${s}${location.hash}`;
  if (url === `${location.pathname}${location.search}${location.hash}`) return;
  history[pousser ? "pushState" : "replaceState"](null, "", url);
}

/* Sous le seuil étroit, la fiche remplace la liste (`.lf--fiche`) ; « ← Liste » y ramène.
   Tant que rien n'est choisi — la fiche du projet, ou la comparaison que les cases de la
   liste viennent d'ouvrir —, la fiche se lit SOUS la liste (`.lf--empile`) : cachée, elle
   ferait des deux cases cochées un geste sans effet visible, et du résumé du projet un
   contenu perdu au premier rétrécissement. */
function rendreVue() {
  const biblio = $("#biblio");
  biblio.classList.toggle("lf--fiche", B.vueFiche);
  biblio.classList.toggle("lf--empile",
    !B.vueFiche && ["accueil", "comparaison"].includes(ficheCourante().genre));
}

const RETOUR_LISTE = `<button type="button" class="ghost small lf-retour" data-bi-retour="1">← Liste</button>`;

/* Dessine la fiche courante. `msg` : une ligne à reposer dans la fiche redessinée — la
   confirmation d'un enregistrement, qui ne doit pas partir avec la fiche qu'elle confirme. */
function rendreFiche(msg) {
  const f = ficheCourante();
  if (f.genre !== "collection") demonterQuiEntre();
  if (f.genre === "album") { renderDetail(); rendreVue(); return; }
  if (f.genre === "collection") {
    const c = collection(f.id);
    if (c) { rendreFicheCollection(c, msg); rendreVue(); return; }
    // Ouverte puis disparue (supprimée, ou plus lisible) : la fiche du projet, qui le dit.
    B.ouverte = null;
    B.calques.delete(f.id);
  }
  if (ficheCourante().genre === "comparaison") rendreComparaison();
  else rendreAccueil();
  if (msg) $("#biblio-fiche").appendChild(colTrace(msg.texte, msg.erreur));
  rendreVue();
}

/* Ce qui suit un geste sur les albums, quand aucun album n'est ouvert : l'onglet Albums de
   la collection montrée — et lui seul, sans toucher aux formulaires des autres onglets —, ou
   la fiche du projet et la comparaison, qui comptent des albums. */
function rafraichirFicheApresAlbums() {
  const f = ficheCourante();
  if (f.genre === "collection") {
    const c = collection(f.id);
    const panneau = document.getElementById("panneau-albums");
    if (c && panneau && $("#col-fiche") && Number($("#col-fiche").dataset.id) === c.id) {
      rendreAlbumsDeLaCollection(panneau, c);
      return;
    }
  }
  if (f.genre !== "album") rendreFiche();
}

/* ── La fiche du PROJET : ce que la Bibliothèque montre quand rien n'est choisi ───────── */
function rendreAccueil() {
  const fiche = $("#biblio-fiche");
  const p = PROJETS.find((x) => x.id === PROJET);
  const cols = COLS.projet;
  const n = state.albums.length;
  const plusieurs = state.albums.filter((a) => (a.collections || []).length > 1).length;
  const lignes = cols.map((c) => {
    const k = state.albums.filter((a) => (a.collections || []).some((x) => x.id === c.id)).length;
    const pct = n ? Math.round(100 * k / n) : 0;
    return `<li><button type="button" class="lf-lien" data-ouvrir-col="${c.id}">${esc(c.nom)}</button>
      <span class="muted small bi-part"><span>${k} / ${n}</span>
        <i class="val-mini bi-part-barre" aria-hidden="true"><i style="width:${pct}%"></i></i></span></li>`;
  }).join("");
  // COL-3, tranche 3a — « + Prendre du fonds… » EN TÊTE DU CORPUS, vers la base (D10), au
  // responsable du projet et à l'administrateur seulement (D3).
  const fonds = BDBiblio.offrirPrendreDuFonds(p);
  fiche.innerHTML = `${RETOUR_LISTE}
    <div class="lf-tete"><div>
      <h3 id="bi-accueil-titre" tabindex="-1">${esc(p ? p.nom : "Bibliothèque")}</h3>
      <p class="lf-sous"><span>${esc(BDBiblio.libelleAlbums(n, { total: B.total }))}</span>
        <span>${pluriel(cols.length, "collection")}${B.total ? "" : " que vous lisez"}</span></p>
    </div>
    ${fonds ? `<div class="lf-gestes-tete">
      <button type="button" class="primary small" id="bi-prendre-fonds" data-prendre-fonds="tete"
              aria-expanded="${!!(P3A.prise && P3A.prise.ou === "tete")}" aria-controls="bi-prise-zone">+ Prendre du fonds…</button>
    </div>` : ""}</div>
    <div id="bi-prise-zone" class="bi-prise-zone"></div>
    <div id="bi-bac-carte"></div>
    ${p && p.description ? `<p class="bi-projet-description">${esc(p.description)}</p>` : ""}
    <section id="corpus-synthese" class="corpus-synthese" hidden></section>
    ${cols.length ? `<section class="lf-section">
      <h4>${B.total ? "Les collections, posées sur le corpus" : "Les collections, posées sur ce que vous lisez"}</h4>
      <ul class="lf-lignes bi-parts">${lignes}</ul>
      <p class="col-note">${pluriel(plusieurs, "album")} sur plusieurs collections.
        Cochez une collection pour filtrer les albums ; son nom ouvre sa fiche.</p>
    </section>` : ""}`;
  if (!fonds || (P3A.prise && P3A.prise.ou !== "tete")) P3A.prise = null;
  P3A.dansProjet = null;
  rendreZonePrise();
  loadSynthese();
  carteBacASable();
}

/* COL-4 — « Mon bac à sable » en carte dans la fiche, à qui n'a encore aucun projet (le
   premier clic d'un arrivant ; Hugo, 2026-10-24). Qui offre, et à qui, est la règle de
   `lib/bac-a-sable.js`. */
async function carteBacASable() {
  if (!window.BDBacEcran) return;
  await BDBacEcran.pret;
  const zone = document.getElementById("bi-bac-carte");
  if (!zone || zone.firstChild) return;
  const g = BDBacEcran.gestePageVide("bac-vide-carte",
                                     "Essayez l'outil sur un jeu de planches, dans un projet à vous.");
  if (g) zone.appendChild(g);
}

/* Synthèse d'avancement (barre par statut + validées), sur ce qu'on lit. */
async function loadSynthese() {
  const el = $("#corpus-synthese");
  if (!el) return;
  let c;
  try { c = await apiGet(routeCorpus()); } catch (e) { return; }
  const ici = $("#corpus-synthese");
  if (!ici) return;                     // la fiche a changé entre-temps
  const order = ["importee", "segmentee", "corrigee", "annotee"];
  const lbl = { importee: "importées", segmentee: "segmentées",
                corrigee: "corrigées", annotee: "annotées" };
  const total = c.planches || 0, st = c.statuts || {};
  const bar = total ? order.map((s) => {
    const n = st[s] || 0;
    return n ? `<span class="seg seg-${s}" style="width:${(100 * n / total).toFixed(1)}%" title="${lbl[s]} : ${n}"></span>` : "";
  }).join("") : "";
  const pct = total ? Math.round(100 * c.validees / total) : 0;
  ici.hidden = false;
  ici.innerHTML =
    `<div class="synth-line"><b>Tout ce que vous lisez</b> · ${c.albums} album(s) · ${total} planche(s)`
    + ` · <span class="synth-val">✔ ${c.validees} validée(s) (${pct} %)</span></div>`
    + `<div class="synth-bar">${bar}</div>`
    + `<div class="synth-legend muted small">`
    + order.map((s) => `<span><i class="seg seg-${s}"></i> ${lbl[s]} (${st[s] || 0})</span>`).join("")
    + `</div>`;
}

/* ── La COMPARAISON : deux calques cochés ou plus (orientation de Hugo, 2026-10-16) ────── */
function rendreComparaison() {
  const fiche = $("#biblio-fiche");
  const cols = COLS.projet.filter((c) => B.calques.has(c.id));
  const r = BDBiblio.comparer(cols, state.albums);
  const pct = (a, b) => (b ? `${Math.round(100 * a / b)} %` : "—");
  const tete = r.lignes.map((l) => `<th scope="col">${esc(l.nom)}</th>`).join("");
  const ligne = (titre, f) => `<tr><th scope="row">${titre}</th>${r.lignes.map((l) =>
    `<td class="c-num">${f(l)}</td>`).join("")}</tr>`;
  const rec = r.recoupement;
  fiche.innerHTML = `${RETOUR_LISTE}
    <div class="lf-tete"><div>
      <h3 id="bi-comparaison-titre" tabindex="-1">Comparer ${pluriel(cols.length, "collection")}</h3>
      <p class="lf-sous">${cols.map((c) => `<span>${esc(c.nom)}</span>`).join("")}</p>
    </div></div>
    <p class="col-note">Sur ce que vous lisez de ces collections, dans ce projet.</p>
    <div class="table-cadre" tabindex="0" role="region" aria-label="Comparaison des collections">
      <table class="corpus-table bi-comparaison">
        <thead><tr><td></td>${tete}</tr></thead>
        <tbody>
          ${ligne("Albums", (l) => l.albums)}
          ${ligne("Planches", (l) => l.planches)}
          ${ligne("Validées", (l) => pct(l.validees, l.planches))}
          <tr><th scope="row">Régime</th>${r.lignes.map((l) =>
            `<td>${esc(colRegime(l.regime))}</td>`).join("")}</tr>
        </tbody>
      </table>
    </div>
    ${rec ? `<section class="lf-section"><h4>Recoupement</h4>
      <p class="lf-pastilles">
        <span class="lf-puce">seulement ${esc(r.lignes[0].nom)} : ${rec.seulA}</span>
        <span class="lf-puce ok">dans les deux : ${rec.communs}</span>
        <span class="lf-puce">seulement ${esc(r.lignes[1].nom)} : ${rec.seulB}</span></p>
      ${B.mode !== "toutes" && BDBiblio.libelleCommuns(rec.communs) ? `<p><button type="button" class="ghost small" data-mode-fiche="toutes">${esc(BDBiblio.libelleCommuns(rec.communs))}</button></p>` : ""}
    </section>` : ""}`;
}

/* ═══════════════════════════════════════════════════════════════════════════
   La fiche d'une COLLECTION — quatre onglets (tranché par Hugo le 2026-10-07)
   ═══════════════════════════════════════════════════════════════════════════ */

/* L'en-tête dit mes droits en ACTES, lus dans ce que `GET /api/collections` rend pour CETTE
   collection (`lib/bibliotheque.js`). Un acte absent se barre ET se marque d'un tiret, pas
   seulement d'une couleur (WCAG 1.4.1) ; le lecteur d'écran entend « oui » ou « non ». */
function htmlDroits(c) {
  return `<ul class="droits" aria-label="Vos droits ici">${BDBiblio.actesCollection(c).map((a) =>
    `<li class="${a.oui ? "oui" : "non"}" data-acte="${a.cle}">${esc(a.libelle)}<span class="sr-only">${a.oui ? " : oui" : " : non"}</span></li>`).join("")}</ul>`;
}

function rendreFicheCollection(c, msg) {
  const fiche = $("#biblio-fiche");
  const emb = colEmbargo(c);
  const onglets = BDBiblio.ONGLETS.map((o) => `<button type="button" role="tab"
      id="onglet-${o.cle}" aria-controls="panneau-${o.cle}" data-onglet="${o.cle}"
      aria-selected="${o.cle === B.onglet}" tabindex="${o.cle === B.onglet ? "0" : "-1"}">${esc(o.libelle)}${o.cle === "albums" ? pastilleOngletAlbums(c) : ""}</button>`).join("");
  const panneaux = BDBiblio.ONGLETS.map((o) => `<div class="bi-panneau" role="tabpanel"
      id="panneau-${o.cle}" aria-labelledby="onglet-${o.cle}" tabindex="0"
      ${o.cle === B.onglet ? "" : "hidden"}></div>`).join("");
  demonterQuiEntre();
  fiche.innerHTML = `${RETOUR_LISTE}
    <section id="col-fiche" class="col-fiche" data-id="${c.id}" aria-labelledby="col-fiche-titre">
      <div class="lf-tete"><div>
        <h3 id="col-fiche-titre" tabindex="-1">${esc(c.nom)}</h3>
        <p class="lf-sous">
          <span class="col-fiche-nb">${pluriel(c.nb_albums, "album")}</span>
          ${c.base ? `<span class="lf-puce" title="Ce que le projet prend au fonds y arrive">collection de base</span>` : ""}
          ${colBadge(c)}
          <span class="lf-puce col-regime">${esc(colRegime(c.statut_diffusion))}</span>
          ${emb ? `<span class="lf-puce alerte col-embargo ${emb[1]}" title="${esc(emb[2])}">${esc(emb[0])}</span>` : ""}
        </p>
        ${htmlDroits(c)}
      </div></div>
      <div class="onglets" role="tablist" aria-label="Parties de la collection">${onglets}</div>
      ${panneaux}
    </section>`;
  const f = $("#col-fiche");
  rendreAlbumsDeLaCollection(f.querySelector("#panneau-albums"), c);
  f.querySelector("#panneau-qui").innerHTML = `<section data-qui-entre></section>`;
  monterQuiEntre(f.querySelector("#panneau-qui"), c);
  rendreDescription(f.querySelector("#panneau-description"), c, msg && msg.onglet === "description" ? msg : null);
  rendreDiffusion(f.querySelector("#panneau-diffusion"), c, msg && msg.onglet === "diffusion" ? msg : null);
  if (msg && !msg.onglet) {
    f.querySelector(`#panneau-${B.onglet}`).prepend(colTrace(msg.texte, msg.erreur));
  }
}

/* Changer d'onglet : la fiche reste, seul le panneau change. Le motif ARIA des onglets —
   un seul onglet dans la tabulation, les flèches pour passer de l'un à l'autre. */
function choisirOnglet(cle, focaliser) {
  if (!BDBiblio.CLES_ONGLETS.includes(cle)) return;
  B.onglet = cle;
  const f = $("#col-fiche");
  if (!f) return;
  f.querySelectorAll('[role="tab"]').forEach((t) => {
    const oui = t.dataset.onglet === cle;
    t.setAttribute("aria-selected", String(oui));
    t.tabIndex = oui ? 0 : -1;
    if (oui && focaliser) t.focus();
  });
  f.querySelectorAll('[role="tabpanel"]').forEach((partie) => {
    partie.hidden = partie.id !== `panneau-${cle}`;
  });
  ecrireAdresse(false);
}

/* ── Onglet ALBUMS : le tableau des albums DE cette collection, et le lot sur sa sélection ── */
function albumsDe(c) {
  return state.albums.filter((a) => (a.collections || []).some((x) => x.id === c.id));
}

function rendreAlbumsDeLaCollection(panneau, c) {
  const albums = albumsDe(c);
  const coches = albums.filter((a) => state.checkedAlbums.has(a.id));
  const lignes = albums.map((a) => {
    const droits = BDBiblio.droitsAlbum(a, COLS.toutes);
    const aussi = BDBiblio.aussiDans(a, c.id);
    const offrir = BDSuppression.offrir({ ...a, ecrivable: droits.ecrire });
    return `<tr class="col-album" data-id="${a.id}">
      <td class="c-chk"><input type="checkbox" data-coche-album="${a.id}"
          aria-label="Sélectionner l'album ${esc(a.titre)}" ${state.checkedAlbums.has(a.id) ? "checked" : ""}></td>
      <td class="c-titre"><button type="button" class="lf-lien bi-titre" data-ouvrir-album="${a.id}">${esc(a.titre)}</button>${pastilleDemande(a)}</td>
      <td class="c-act">${droits.ecrire ? `<button class="icon-btn" type="button" data-act="edit" data-id="${a.id}"
          title="Éditer les métadonnées" aria-label="Éditer les métadonnées de ${esc(a.titre)}">✎</button>` : ""}
        ${offrir ? `<button class="ghost small sp-ouvrir" type="button" data-act="supprimer" data-id="${a.id}"
          aria-label="Supprimer ${esc(a.titre)}…">Supprimer…</button>` : ""}</td>
      <td class="c-num" data-l="Planches">${a.nb_planches}</td>
      <td class="c-num c-val-album" data-l="Validées">${validBadge(a.nb_validees, a.nb_planches)}</td>
      <td class="c-aussi${aussi.length ? "" : " vide-carte"}" data-l="Aussi dans">${aussi.length ? aussi.map(esc).join(", ") : `<span class="muted">—</span>`}</td>
    </tr>`;
  }).join("");
  // COL-3, tranche 3a — le bloc ⚑ des demandes reçues en tête de l'onglet (D11), puis les
  // deux gestes de la prise, à droite au-dessus du tableau, avant le lot. « + Prendre du
  // fonds… » au responsable et à l'administrateur (D3) ; « + Prendre dans le projet… » à
  // qui écrit dans la collection.
  const projet = PROJETS.find((x) => x.id === c.projet_id) || null;
  const fonds = BDBiblio.offrirPrendreDuFonds(projet, c);
  const ecrit = !!c.ecrivable;
  if (P3A.prise && (P3A.prise.ou !== "collection" || P3A.prise.depuis !== c.id || !fonds)) P3A.prise = null;
  if (P3A.dansProjet && (P3A.dansProjet.collection !== c.id || !ecrit)) P3A.dansProjet = null;
  panneau.innerHTML = `<div id="bi-recues-zone"></div>
    ${ecrit ? `<div class="bi-gestes-albums">
      ${fonds ? `<button type="button" class="ghost small" id="bi-prendre-fonds" data-prendre-fonds="collection"
          aria-expanded="${!!P3A.prise}" aria-controls="bi-prise-zone">+ Prendre du fonds…</button>` : ""}
      <button type="button" class="ghost small" id="bi-dans-projet" aria-expanded="${!!P3A.dansProjet}"
          aria-controls="bi-prise-zone"
          title="Ranger ici un album que le projet a déjà : rejoindre son travail, ou en prendre une copie vierge">+ Prendre dans le projet…</button>
    </div>
    <div id="bi-prise-zone" class="bi-prise-zone"></div>` : ""}
    ${barreLot("albums", coches.length)}
    <div class="table-cadre bi-cadre" tabindex="0" role="region" aria-label="Albums de « ${esc(c.nom)} »">
      <table class="corpus-table bi-table bi-table-albums">
        <thead><tr><th class="c-chk"><span class="sr-only">Sélection</span></th><th>Titre</th>
          <th class="c-act"><span class="sr-only">Gestes</span></th><th class="c-num">Planches</th>
          <th class="c-num">Validées</th><th>Aussi dans</th></tr></thead>
        <tbody>${lignes || `<tr><td colspan="6" class="empty-cell">Aucun album dans cette collection${c.base ? " : ce que le projet prendra au fonds arrivera ici" : ""}.</td></tr>`}</tbody>
      </table>
    </div>`;
  rendreBlocRecues(c);
  rendreZonePrise();
}

/* ── Onglet DESCRIPTION : la LECTURE d'abord, le formulaire au geste ──────────────────── */

/* Le vocabulaire du régime de diffusion — en DOUBLE de `config.STATUTS_DIFFUSION`, parce
   que les gabarits sont servis tels quels et qu'aucune route ne le publie. Leur accord est
   MESURÉ : `tests/test_collections_admin.py` échoue si l'un bouge sans l'autre. La valeur
   vide est « sans régime » — NULL en base, l'état de toute collection neuve. */
const REGIMES_DIFFUSION = [
  ["", "sans régime"],
  ["public", "public"],
  ["embargo", "sous embargo"],
  ["restreint", "restreint"],
  ["prive", "privé"],
];

/* Les champs, dans l'ordre où on les lit, et rangés par ce qu'ils ENGAGENT (fiche COL-2) :
   un formulaire plat mettrait le nom et la base légale sur le même plan. `responsables`
   n'y est pas, et c'est voulu : scientifique, porteur d'ORCID, parti au dépôt, il ne passe
   pas par `CollectionUpdate` et reste à `tools/gerer_collections.py`. UX-18 : les groupes
   « description » et « référent » vivent dans l'onglet Description, « diffusion » dans
   l'onglet Diffusion et dépôt, à côté de ce que le régime gouverne. */
const COL_GROUPES = [
  { id: "description", legende: "Description", champs: [
    { cle: "nom", libelle: "Nom" },
    { cle: "description", libelle: "Description", zone: true },
    { cle: "date_debut", libelle: "Début", aide: "AAAA ou AAAA-MM-JJ" },
    { cle: "date_fin", libelle: "Fin", aide: "AAAA ou AAAA-MM-JJ" },
  ] },
  { id: "diffusion", legende: "Diffusion — ce qui sort de l'instance", champs: [
    { cle: "statut_diffusion", libelle: "Régime de diffusion", regime: true },
    // Un champ TEXTE et non `type=date` : un champ date affiche VIDE une valeur qu'il ne
    // sait pas lire. Une date illisible disparaîtrait donc de l'écran, et le premier
    // enregistrement l'effacerait — une levée d'embargo déguisée en faute de frappe.
    { cle: "date_embargo", libelle: "Fin d'embargo", aide: "AAAA-MM-JJ" },
    { cle: "licence_defaut", libelle: "Licence", aide: "ex. CC-BY-4.0" },
    { cle: "base_legale", libelle: "Base légale" },
  ] },
  { id: "referent", legende: "Référent — à qui s'adresser", champs: [
    { cle: "referent_nom", libelle: "Nom lisible" },
    { cle: "referent_contact", libelle: "Contact", aide: "Courriel ou adresse de page" },
  ] },
];
const GROUPES_DE_L_ONGLET = { description: ["description", "referent"], diffusion: ["diffusion"] };

function lu(v) {
  return v == null || String(v).trim() === "" ? `<span class="muted">—</span>` : esc(String(v));
}

function rendreDescription(panneau, c, msg) {
  const edition = B.edition === "description" && c.administrable;
  const periode = c.date_debut || c.date_fin
    ? `${esc(c.date_debut || "…")} – ${esc(c.date_fin || "…")}` : `<span class="muted">—</span>`;
  const lecture = `<dl class="bi-lecture">
      <dt>Nom</dt><dd>${esc(c.nom)}</dd>
      <dt>Description</dt><dd class="bi-texte">${lu(c.description)}</dd>
      <dt>Période</dt><dd>${periode}</dd>
      <dt>Référent</dt><dd>${colReferentLu(c) || `<span class="muted">—</span>`}</dd>
    </dl>`;
  panneau.innerHTML = `${edition ? colFormulaire(c, "description") : lecture}
    ${c.administrable ? (edition ? "" : `<p class="bi-gestes"><button class="ghost small" type="button" data-modifier="description">Modifier</button></p>`)
      : `<p class="col-note">Seul un propriétaire de la collection modifie sa description, son
           régime de diffusion et son référent.</p>`}
    ${edition ? "" : `<p class="col-msg col-msg-formulaire muted small" role="status" aria-live="polite"></p>`}
    ${zoneDanger(c)}`;
  if (msg) colMsg(panneau.querySelector(".col-msg-formulaire"), msg.texte, msg.erreur);
}

/* « Supprimer la collection » quitte le voisinage d'« Enregistrer » (UX-18) : une zone à
   part, en bas de l'onglet, qu'on n'atteint pas en visant le bouton d'à côté. La collection
   de base d'un projet ne se supprime pas : elle part avec le projet (COL-3, D10). */
function zoneDanger(c) {
  if (!c.administrable) return "";
  return `<div class="bi-zone-danger">
    ${c.base ? `<p class="muted small">La collection de base ne se supprime pas : elle part avec le projet.</p>`
      : `<button class="ghost small bi-supprimer-col" type="button" data-supprimer="1">Supprimer la collection…</button>
         <p class="col-msg col-msg-danger muted small" role="status" aria-live="polite"></p>`}
  </div>`;
}

/* ── Onglet DIFFUSION ET DÉPÔT : le régime, puis les exports, puis ShareDocs ──────────── */
function rendreDiffusion(panneau, c, msg) {
  const edition = B.edition === "diffusion" && c.administrable;
  const emb = colEmbargo(c);
  const lecture = `<dl class="bi-lecture">
      <dt>Régime de diffusion</dt><dd class="col-regime">${esc(colRegime(c.statut_diffusion))}</dd>
      <dt>Fin d'embargo</dt><dd>${lu(c.date_embargo)}</dd>
      <dt>Licence</dt><dd>${lu(c.licence_defaut)}</dd>
      <dt>Base légale</dt><dd>${lu(c.base_legale)}</dd>
    </dl>
    ${emb ? `<p class="col-note col-embargo-note ${emb[1]}">${esc(emb[2])}</p>` : ""}
    ${NOTE_REGIME}`;
  panneau.innerHTML = `${edition ? colFormulaire(c, "diffusion") : lecture}
    ${c.administrable ? (edition ? "" : `<p class="bi-gestes"><button class="ghost small" type="button" data-modifier="diffusion">Modifier</button></p>`) : ""}
    ${edition ? "" : `<p class="col-msg col-msg-formulaire muted small" role="status" aria-live="polite"></p>`}
    ${colExport(c)}`;
  if (msg) colMsg(panneau.querySelector(".col-msg-formulaire"), msg.texte, msg.erreur);
  colBrancherExport(panneau);
}

const NOTE_REGIME = `<p class="col-note">Le régime décide de ce qui SORT de l'instance — les
  images d'un manifeste IIIF, l'avertissement d'un dépôt ; à l'intérieur, il ne borne rien. La
  date d'embargo RETIENT : tant qu'elle court, les scans ne sortent pas, même d'une collection
  « public ». Elle ne publie jamais rien d'elle-même — une échéance passée se signale sans
  rien lever, et une date illisible retient aussi.</p>`;

/* Un champ du formulaire. Aucune valeur n'est interprétée ici : le serveur valide, et ses
   refus sont rendus tels quels. Une valeur de régime HORS vocabulaire reste sélectionnée et
   nommée comme telle, pour qu'enregistrer autre chose ne la fasse pas disparaître en
   silence. */
function colChamp(c, f) {
  const id = `col-${c.id}-${f.cle}`;
  const v = c[f.cle] == null ? "" : String(c[f.cle]);
  const a = `id="${id}" data-champ="${f.cle}"`;
  let champ;
  if (f.regime) {
    const connue = REGIMES_DIFFUSION.some(([val]) => val === v);
    champ = `<select ${a}>${REGIMES_DIFFUSION.map(([val, lib]) =>
      `<option value="${val}"${val === v ? " selected" : ""}>${esc(lib)}</option>`).join("")}${
      connue ? "" : `<option value="${esc(v)}" selected>${esc(v)} (hors vocabulaire)</option>`}</select>`;
  } else if (f.zone) {
    champ = `<textarea ${a} rows="2">${esc(v)}</textarea>`;
  } else {
    champ = `<input ${a} value="${esc(v)}" autocomplete="off"${
      f.aide ? ` placeholder="${esc(f.aide)}"` : ""}>`;
  }
  return `<div class="contrib-add col-champ"><label for="${id}">${esc(f.libelle)}</label>${champ}</div>`;
}

/* Ce que chaque groupe ENGAGE, dit sous ses champs. La date d'embargo est la plus traître :
   l'écran doit dire ce qu'elle FAIT, pas seulement l'accepter (piège écrit dans COL-2). */
function colNoteGroupe(c, g) {
  if (g.id === "diffusion") {
    const emb = colEmbargo(c);
    return `${emb ? `<p class="col-note">${esc(emb[2])}</p>` : ""}${NOTE_REGIME}`;
  }
  if (g.id === "referent") {
    return `<p class="col-note">C'est une ADRESSE, pas un droit : la nommer n'accorde rien et
      ne retire rien. Elle ne sort d'aucun export, et ce n'est pas le responsable
      scientifique, qui part au dépôt avec son ORCID.</p>`;
  }
  return "";
}

function colFormulaire(c, onglet) {
  return COL_GROUPES.filter((g) => GROUPES_DE_L_ONGLET[onglet].includes(g.id)).map((g) => `
    <fieldset class="modal-section">
      <legend>${esc(g.legende)}</legend>
      ${g.champs.map((f) => colChamp(c, f)).join("")}
      ${colNoteGroupe(c, g)}
    </fieldset>`).join("") + `
    <div class="modal-actions">
      <button class="primary small" data-enregistrer="${onglet}" type="button">Enregistrer</button>
      <button class="ghost small" data-annuler-edition="1" type="button">Annuler</button>
    </div>
    <p class="col-msg col-msg-formulaire muted small" role="status" aria-live="polite"></p>`;
}

/* N'envoie que ce qui a CHANGÉ, et pour deux raisons qui se vérifient. Un régime HORS
   vocabulaire — un reste d'avant la validation — ferait refuser TOUT l'enregistrement en
   422 s'il était renvoyé tel quel, alors qu'on voulait seulement corriger la licence. Et un
   champ qu'on n'a pas touché ne doit pas écraser ce qu'une autre personne vient d'y écrire.
   La date d'embargo illisible, elle, est protégée par son champ TEXTE (cf. `COL_GROUPES`) :
   c'est lui qui la réaffiche telle quelle. Un champ vidé part en `null` — c'est un geste,
   pas un oubli. */
async function colEnregistrer(panneau, c, onglet) {
  const ligne = panneau.querySelector(".col-msg-formulaire");
  const modifs = {};
  panneau.querySelectorAll("[data-champ]").forEach((el) => {
    const cle = el.dataset.champ;
    const avant = c[cle] == null ? "" : String(c[cle]).trim();
    const apres = el.value.trim();
    if (apres !== avant) modifs[cle] = apres === "" ? null : apres;
  });
  if (!Object.keys(modifs).length) { colMsg(ligne, "Rien n'a changé."); return; }
  if (await colTenter(ligne, () => apiSend("PATCH", `/api/collections/${c.id}`, modifs))) {
    const msg = { texte: `« ${modifs.nom || c.nom} » enregistrée.`, erreur: false, onglet };
    colMsg(ligne, msg.texte);
    if (await chargerCollections()) {
      B.edition = null;
      rendreFiche(msg);
      // Le formulaire redessiné emporte « Enregistrer » et le focus avec lui : il revient
      // au « Modifier » du même panneau, comme après « Annuler » — dans la même tâche que
      // le message de la fiche.
      const m = document.querySelector(`#panneau-${onglet} [data-modifier]`);
      if (m) m.focus();
    }
  }
}

async function colSupprimer(c) {
  const ligne = $("#col-fiche .col-msg-danger");
  if (!confirm(`Supprimer « ${c.nom} » ? Ses albums ne sont pas supprimés : ils sortent `
               + `simplement de cette collection.`)) return;
  if (await colTenter(ligne, () => apiSend("DELETE", `/api/collections/${c.id}`))) {
    // La collection disparaît, et sa fiche avec elle. La confirmation prend la place de la
    // fiche — c'est là que l'œil est resté —, en tête de celle du projet.
    B.ouverte = null;
    B.calques.delete(c.id);
    B.edition = null;
    if (await chargerCollections()) {
      rendreFiche({ texte: `« ${c.nom} » supprimée.`, erreur: false });
      ecrireAdresse(false);
    }
  }
}

/* ── Les messages : un seul à la fois, là où l'on a agi ───────────────────────────────── */

/* COL-2 (2026-09-16) — un message s'affiche LÀ OÙ L'ON A AGI : sous le champ de création,
   sous les boutons d'un formulaire, dans la zone de suppression. UN message à la fois pour
   toute la page : écrire l'un efface les autres, sans quoi un refus resterait posé — et
   reposé à chaque rechargement — à côté d'un formulaire qui ne contient plus ce qu'il
   refusait. C'est une règle de CET écran : le module « Qui entre » écrit sa propre ligne et
   prévient l'hôte, qui fait taire le reste ICI (UX-16). */
function colTaireSauf(el) {
  document.querySelectorAll("#biblio .col-msg").forEach((l) => {
    if (l === el) return;
    if (l.dataset.trace) { l.remove(); return; }
    l.textContent = "";
    l.classList.remove("erreur", "alerte");
  });
}

function colMsg(el, texte, erreur) {
  if (!el) return;
  colTaireSauf(el);
  el.textContent = texte || "";
  // `erreur` vaut `true` pour un refus, « alerte » pour ce qui a RÉUSSI mais doit se lire :
  // un accès accordé à un nom que l'annuaire ne connaît pas (AUTH-12, décision 4).
  el.classList.toggle("erreur", erreur === true);
  el.classList.toggle("alerte", erreur === "alerte");
}

/* Une ligne de message qui n'appartient plus à aucun formulaire : ce qui reste quand celui
   qui parlait a disparu — une collection supprimée, une relecture ratée. Marquée, pour que
   le geste suivant l'ôte au lieu de la vider. */
function colTrace(texte, erreur) {
  const p = document.createElement("p");
  p.className = "col-msg muted small";
  p.setAttribute("role", "status");
  p.dataset.trace = "1";
  colMsg(p, texte, erreur);
  return p;
}

/* Les refus du serveur sont RENDUS, jamais avalés : un 409 qui dit combien d'albums une
   suppression laisserait sans collection, un 422 qui nomme les valeurs admises, un 403 qui
   dit qu'aucune identité ne parvient. Trois causes qui ne se corrigent pas de la même
   façon, qu'un « échec » générique ferait prendre pour un bug. */
async function colTenter(el, fn) {
  try { await fn(); colMsg(el, ""); return true; }
  catch (e) { colMsg(el, e.message || "Échec", true); return false; }
}

/* Le libellé d'un régime. Une valeur HORS vocabulaire — un reste d'avant la validation —
   s'affiche telle quelle plutôt que d'être maquillée en « sans régime ». */
function colRegime(v) {
  const r = REGIMES_DIFFUSION.find(([val]) => val === (v || ""));
  return r ? r[1] : String(v);
}

/* DROIT-1 — ce que la date d'embargo raconte, en clair.

   L'application ne lève JAMAIS un embargo toute seule : une date qui passe dit que le
   délai a couru, pas que les droits sont acquis. Mais se taire aurait son propre coût —
   un embargo échu que personne ne remarque garde un corpus fermé par inertie, ce qui
   trahit l'orientation open-science aussi sûrement qu'une fuite trahit les droits.

   Le libellé PORTE le sens ; la couleur ne fait que le renforcer (WCAG 1.4.1). Dérivé ICI,
   lu par l'en-tête de la fiche ET par l'onglet Diffusion : deux lectures du même champ
   finiraient sinon par se contredire. */
function colEmbargo(c) {
  const date = c.date_embargo || "";
  if (c.embargo === "echu")
    return [`Embargo échu`, "est-echu",
            `L'embargo est échu depuis le ${date}, et la collection reste déclarée `
            + `« ${c.statut_diffusion || "sans régime"} ». L'application ne la publie pas `
            + `pour autant : si les droits sont acquis, déclarez-la « public ».`];
  if (c.embargo === "illisible")
    return [`Embargo : date illisible`, "est-echu",
            `« ${date} » n'est pas une date lisible (attendu AAAA-MM-JJ). Par précaution, `
            + `les scans ne sortent pas tant qu'elle ne l'est pas.`];
  if (c.embargo === "pendant")
    return [`Embargo jusqu'au ${date}`, "",
            c.statut_diffusion === "public"
              ? `La collection est déclarée « public », mais l'embargo court jusqu'au `
                + `${date} : les scans ne sortiront pas avant cette date.`
              : `L'embargo court jusqu'au ${date}. Le travail interne n'en est pas `
                + `affecté : seule la publication l'est.`];
  return null;
}

/* Le référent, en LECTURE. Le contact s'affiche en TEXTE et non en lien, contrairement au
   référent d'instance du bandeau (`theme.js`) : celui-là vient de l'environnement, donc de
   qui déploie, tandis que celui-ci est saisi par un propriétaire de collection. Plutôt que
   de recopier ici l'autorisation de schémas — deux listes qui divergeraient un jour —, on
   n'ouvre pas la porte du tout : un `href` est la seule chose qui rende `javascript:`
   dangereux, et une adresse reste lisible sans être cliquable. */
function colReferentLu(c) {
  const nom = (c.referent_nom || "").trim();
  const contact = (c.referent_contact || "").trim();
  if (!nom && !contact) return "";
  return `<span class="col-note-referent">Référent de cette collection :
    <strong>${esc(nom || contact)}</strong>${nom && contact ? ` — ${esc(contact)}` : ""}.</span>`;
}

/* Le dépôt ShareDocs. Il RÉUTILISE les réglages des lignes du dessus — la case
   « avec le texte relevé » et l'adresse du serveur d'images — parce que ce sont les mêmes
   réglages du même artefact : les redemander ici laisserait deux jeux de valeurs se
   contredire à l'écran, et personne ne saurait lequel est parti.

   Le bloc n'existe que pour qui ADMINISTRE la collection, et c'est le serveur qui tranche
   (403) : `administrable` ne fait que lui éviter de proposer un geste qu'il refusera.
   L'inverse — décider ici et laisser le serveur ouvert — est l'erreur qui ne se voit
   jamais, puisque l'écran a l'air correct. */
async function colDeposer(bouton) {
  const boite = bouton.closest(".col-export");
  const msg = boite.querySelector(".dep-msg");
  const [quoi, format] = boite.querySelector(".dep-choix").value.split("|");
  const base = boite.querySelector(".dep-base").value.trim();

  // La même règle que pour le téléchargement : un manifeste sans serveur d'images ne
  // part pas, et le dire avant d'appeler évite un aller-retour pour rien.
  const { refus } = BDDepot.urlDepot({ collectionId: bouton.dataset.col, quoi, format,
                                       baseUrl: base });
  if (refus) { msg.textContent = refus; msg.className = "dep-msg erreur"; return; }

  msg.className = "dep-msg";
  msg.textContent = "Dépôt en cours…";
  try {
    const r = await apiSend("POST", `/api/collections/${bouton.dataset.col}/depot/deposer`,
      { quoi, format, verbatim: Boolean(boite.querySelector("[data-verbatim]").checked),
        base_url: base, dossier: boite.querySelector(".dep-dossier").value.trim() });
    // Le compte EMPLOYÉ vient du serveur et s'affiche : un dépôt fait sous le compte de
    // l'instance alors qu'on en a un personnel doit se voir (SHARE-1).
    msg.textContent = `Déposé : ${r.depose} (compte ${r.compte}).`;
  } catch (e) {
    msg.className = "dep-msg erreur";
    msg.textContent = e.message || "Échec du dépôt.";
  }
}

/* Branche les boutons du bloc d'export, à chaque dessin de l'onglet Diffusion et dépôt :
   c'est le seul endroit où l'oubli serait silencieux — un bouton sans gestionnaire ne
   proteste pas, il ne fait rien. */
function colBrancherExport(box) {
  box.querySelectorAll("[data-dep]").forEach((b) => {
    b.type = "button";
    b.onclick = () => colTelecharger(b);
  });
  const dep = box.querySelector("[data-depot]");
  if (dep) { dep.type = "button"; dep.onclick = () => colDeposer(dep); }
}


/* EXP-1 — l'export de dépôt, pour qui n'a pas de shell.

   Ce bloc s'affiche dans l'onglet Diffusion et dépôt quel que soit le droit de qui le lit,
   et c'est la leçon d'AUTH-4 appliquée avant de se refaire prendre : une garde d'interface
   se pose sur l'ACTE, jamais sur l'écran — ni sur l'onglet — qui le contient. Décrire une collection qu'on lit n'est pas la partager —
   le serveur n'exigeait ici que `peut_lire`, et le ranger sous le `return` réservé aux
   propriétaires en ferait, exactement comme le référent, un droit d'écriture déguisé. On
   se serait aperçu de rien : l'erreur échoue en se FERMANT, aucun test ne tombe, et une
   revue de sécurité l'approuve.

   Le nom du fichier vient du serveur (`Content-Disposition`) : le recomposer ici ferait
   diverger deux horodatages pour un seul export — même raison que l'export de figures.

   DROIT-2 (2026-09-11) — le serveur exige désormais le droit d'EXPORTER, une case que le
   propriétaire accorde accès par accès. Le bloc suit `exportable` : sans le droit, il se
   réduit à une note qui dit ce qui manque — dans les deux branches, toujours. La garde
   reste sur l'acte, au serveur ; l'écran évite seulement de proposer un geste perdu.
   UX-18 : « Exporter : droit manquant » se lit sous l'intitulé, pour qu'une annotatrice sans
   la case sache, d'un coup d'œil, ce qui lui manque. */
function colExport(c) {
  if (!c.exportable) {
    return `
    <div class="col-export">
      <h4>Export de dépôt</h4>
      <p class="col-export-manque"><b>Exporter : droit manquant.</b></p>
      <p class="col-note">Exporter cette collection demande le droit d'exporter, que son
        propriétaire accorde accès par accès : la lire n'y suffit pas.</p>
    </div>`;
  }
  const b = `data-col="${c.id}"`;
  return `
    <div class="col-export">
      <h4>Export de dépôt</h4>
      <p class="muted small">Ce que produisaient les scripts <code>tools/</code>, sur cette
        collection seulement.</p>
      <div class="dep-ligne">
        <span class="dep-quoi">Fiche de description</span>
        <button class="ghost small" ${b} data-dep="description" data-fmt="json">JSON</button>
        <button class="ghost small" ${b} data-dep="description" data-fmt="csv">CSV</button>
      </div>
      <div class="dep-ligne">
        <span class="dep-quoi">Enregistrements</span>
        <button class="ghost small" ${b} data-dep="metadonnees" data-fmt="json">JSON</button>
        <button class="ghost small" ${b} data-dep="metadonnees" data-fmt="zip">CSV (zip)</button>
        <button class="ghost small" ${b} data-dep="metadonnees" data-fmt="xlsx">XLSX</button>
        <label class="dep-verbatim"><input type="checkbox" data-verbatim="1">
          <span>avec le texte relevé</span></label>
      </div>
      <div class="dep-ligne dep-iiif">
        <span class="dep-quoi">Manifeste IIIF
          <span class="dep-moment">au moment du dépôt</span></span>
        <input type="url" class="dep-base" placeholder="Adresse publique des images (facultatif)"
               aria-label="Adresse publique sous laquelle les images seront servies (facultatif)">
        <button class="ghost small" ${b} data-dep="iiif" data-fmt="zip">Télécharger</button>
      </div>
      <p class="muted small dep-aide">Le manifeste décrit les planches et <b>pointe</b> vers
        les images : il ne les contient pas, et n'attend pas un serveur IIIF — de simples
        JPEG suffisent. L'adresse est celle sous laquelle le dossier <code>derivatives/</code>
        sera publiquement servi : un partage ShareDocs, ou ce que rend l'entrepôt.
        <b>Laissez vide tant que les images ne sont publiées nulle part</b> — le manifeste
        sort alors en aperçu, et le déclare.</p>
      ${c.administrable ? `
      <div class="dep-ligne dep-depot">
        <span class="dep-quoi">Déposer sur ShareDocs</span>
        ${SD.connecte ? `
        <select class="dep-choix" aria-label="Artefact à déposer">
          ${BDDepot.choix().map((o) =>
            `<option value="${o.quoi}|${o.format}">${esc(o.libelle)}</option>`).join("")}
        </select>
        <input class="dep-dossier" placeholder="ex. @Home/mon-dossier (vide = racine)"
               aria-label="Dossier ShareDocs de destination, chemin relatif à la racine WebDAV">
        <button class="ghost small" ${b} data-depot="1">Déposer</button>`
        : `<a class="ghost small dep-connexion"
              href="${esc(BDDepot.lienConnexionSharedocs(
                BDBiblio.ecrireAdresse({ collection: c.id, onglet: "diffusion" }, "")))}">Se connecter à ShareDocs…</a>`}
      </div>
      ${SD.connecte
        ? `<p class="muted small dep-aide">Compte employé :
             <b>${esc(SD.actif ? (SD.actif.compte || "") : "")}</b>
             ${SD.actif && SD.actif.user ? `(${esc(SD.actif.user)})` : ""}.
             Le dossier est un chemin <b>relatif</b>, séparé par des barres obliques — pas
             le fil d'Ariane de l'interface web, dont les noms d'affichage diffèrent des
             chemins réels. Le dépôt ne crée aucun dossier manquant.</p>`
        : `<p class="muted small dep-aide">Aucune session ShareDocs n'est ouverte. Le lien
             ci-dessus ouvre la connexion dans l'Atelier et ramène ici.</p>`}` : ""}
      <p class="dep-msg" role="status" aria-live="polite"></p>
    </div>`;
}

/* Le téléchargement lui-même. Les refus du serveur sont RENDUS À L'ÉCRAN et non avalés :
   ils portent des messages qui distinguent quatre causes (pas publique, embargo en cours,
   date illisible, aucune collection nommée), et ces quatre-là ne se corrigent pas de la
   même façon. Les remplacer par « échec » perdrait tout ce que l'outil sait dire. */
async function colTelecharger(bouton) {
  const boite = bouton.closest(".col-export");
  const msg = boite.querySelector(".dep-msg");
  const quoi = bouton.dataset.dep;
  const verbatim = boite.querySelector("[data-verbatim]")?.checked;
  const base = boite.querySelector(".dep-base")?.value.trim();

  // L'adresse se DÉCIDE dans `static/lib/depot.js`, pas ici : trois erreurs y sont
  // muettes — `verbatim` envoyé à une route qui l'ignore, une adresse d'images non
  // encodée qui INJECTE des paramètres, un format proposé pour le mauvais export. Une
  // concaténation dans ce gestionnaire ne serait vérifiable que par un test qui relit le
  // source, et le dépôt sait depuis `sante.js` ce que vaut cette lecture-là.
  const { url, refus } = BDDepot.urlDepot({
    collectionId: bouton.dataset.col, quoi, format: bouton.dataset.fmt, verbatim,
    baseUrl: base,
  });
  if (refus) {
    msg.textContent = refus;
    msg.className = "dep-msg erreur";
    return;
  }

  msg.className = "dep-msg";
  msg.textContent = "Préparation…";
  try {
    const r = await fetch(url);
    if (!r.ok) {
      throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    }
    const nom = (r.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/);
    const href = URL.createObjectURL(await r.blob());
    const a = document.createElement("a");
    a.href = href; a.download = nom ? nom[1] : "export";
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(href);
    msg.textContent = nom ? `${nom[1]} téléchargé.` : "Export téléchargé.";
  } catch (e) {
    msg.className = "dep-msg erreur";
    msg.textContent = e.message || "Échec de l'export.";
  }
}


/* L'état de la session ShareDocs, lu une fois par chargement de page (EXP-1).

   Il ne DÉCIDE rien — le serveur refusera de lui-même —, il évite seulement de proposer
   un dépôt qui échouerait sur une erreur de transport WebDAV, laquelle ne nomme pas la
   cause. Relu au chargement suffit : on revient ici par un aller-retour, qui recharge. */
let SD = { connecte: false, actif: null };

async function loadEtatSharedocs() {
  // Un échec ici ne doit rien empêcher : sans état connu, on retombe sur « pas de
  // session », qui propose le lien de connexion. Se tromper dans ce sens fait proposer un
  // geste inutile ; se tromper dans l'autre ferait échouer un dépôt sans l'expliquer.
  try { SD = await apiGet("/api/sharedocs/etat"); }
  catch (e) { SD = { connecte: false, actif: null }; }
}


/* ═══════════════════════════════════════════════════════════════════════════
   La fiche d'un ALBUM — à la place de celle de la collection, avec le retour vers elle
   ═══════════════════════════════════════════════════════════════════════════ */

/* Ouvre la fiche d'un album. `garder` : la fiche se redessine sur le même album (après un
   geste), sans déplacer le focus ni toucher à l'adresse. */
async function openAlbum(id, opts = {}) {
  if (id !== state.openId) {
    // La sélection de planches est propre à l'album ouvert : elle se vide quand on change
    // d'album — et la fiche du suivant LE DIT, au lieu de la perdre en silence.
    const avant = state.albums.find((a) => a.id === state.openId);
    B.perdues = state.checkedPlanches.size && avant
      ? { n: state.checkedPlanches.size, titre: avant.titre } : null;
    state.checkedPlanches.clear();
    state.relFilter = "";
  }
  state.openId = id;
  let planches;
  try { planches = await apiGet(`/api/albums/${id}/planches`); }
  catch (e) { toast("Album : " + e.message, "error"); return; }
  if (state.openId !== id) return;      // un autre album a été ouvert entre-temps
  state.planches = planches;
  // Purge les planches cochées qui n'existent plus (suppression concurrente, lot…).
  const pids = new Set(state.planches.map((p) => p.id));
  state.checkedPlanches.forEach((pid) => { if (!pids.has(pid)) state.checkedPlanches.delete(pid); });
  // ATTENDU, pas espéré : `renderDetail()` est synchrone et `parQui()` y compare le login
  // courant. L'attente ne coûte rien : la promesse de `theme.js` est déjà en vol, et le
  // mémo rend l'appel gratuit ensuite.
  MOI = await identite();
  await collectionsLues();
  if (state.openId !== id) return;
  rendreListeAlbums();
  rendreListeCollections();
  renderDetail();
}

/* Revient de la fiche d'un album à ce qu'on regardait avant : la collection d'où on l'a
   ouvert, ou la fiche du projet. */
function fermerAlbum() {
  const depuis = B.depuis;
  state.openId = null;
  state.planches = [];
  state.checkedPlanches.clear();
  B.depuis = null;
  B.perdues = null;
  if (depuis !== null && collection(depuis) && collectionMontree() !== depuis) B.ouverte = depuis;
  rendreListeAlbums();
  rendreListeCollections();
  rendreFiche();
}

function renderDetail() {
  const a = state.albums.find((x) => x.id === state.openId);
  const fiche = $("#biblio-fiche");
  if (!a) { fermerAlbum(); return; }
  const droits = BDBiblio.droitsAlbum(a, COLS.toutes);
  const ecrire = droits.ecrire;
  // Filtre de relecture (ANN-4) : n'affiche que les planches du statut effectif choisi.
  const planches = state.relFilter
    ? state.planches.filter((p) => (p.relecture_statut || {}).statut === state.relFilter)
    : state.planches;
  const videMsg = state.planches.length
    ? "Aucune planche pour ce filtre de relecture."
    : (a.ecrivable ? "Aucune planche : « ⤓ Importer des planches… » les fait entrer."
                   : "Aucune planche.");
  // UX-19 — l'Atelier s'ouvre sur la collection d'où l'on a ouvert l'album (son retour),
  // même si l'album vit aussi ailleurs : l'Atelier la pose par l'adresse, et la retient.
  const versAtelier = B.depuis !== null ? `&collection=${B.depuis}` : "";
  // UX-11 (Hugo, 2026-10-22) — le nom du fichier d'origine au SURVOL de la ligne, et rien de
  // plus : Hugo n'est pas sûr qu'il mérite une colonne. Une planche d'avant la v34 n'en a pas.
  const planchesRows = planches.length
    ? planches.map((p) => `
        <tr data-ligne-planche="${p.id}"${p.nom_fichier_origine ? ` title="${esc("Fichier : " + p.nom_fichier_origine)}"` : ""}>
          <td class="c-chk"><input type="checkbox" aria-label="Sélectionner ${esc(plancheNomLu(p))}" data-pid="${p.id}" ${state.checkedPlanches.has(p.id) ? "checked" : ""}></td>
          <td class="c-vig"><img class="pl-thumb" loading="lazy" src="${esc(p.url_web || "")}" alt=""></td>
          <td class="c-pl">${plancheNum(p)}${materielInfo(p)}</td>
          <td class="c-act c-gestes">${boutonsOrdre(a, p)}${roleToggle(p)} ${lockToggle(p)} <a class="icon-btn" href="/?album=${a.id}&planche=${p.id}${versAtelier}" title="Ouvrir dans l'Atelier" aria-label="Ouvrir ${esc(plancheNomLu(p))} dans l'Atelier">↗</a> ${corbeillePlanche(a, p, droits)}</td>
          <td data-l="Statut"><span class="statut-pill statut-${esc(p.statut)}"></span> ${esc(p.statut)}</td>
          <td class="c-num" data-l="Régions">${p.nb_regions} rég.</td>
          <td class="c-num" data-l="Annotées">${p.nb_annotees} ann.</td>
          <td class="c-rel" data-l="Relecture">${relectureCell(p, ecrire)}</td>
          <td class="c-val" data-l="Validée">${ecrire ? validToggle(p) : validLu(p)}</td>
        </tr>`).join("")
    : `<tr><td colspan="9" class="empty-cell">${videMsg}</td></tr>`;

  // Les séparateurs se posent ENTRE les parties présentes, jamais derrière la dernière :
  // concaténés un à un, ils laissaient « Auteur : X · » quand l'éditeur manquait.
  const idParts = [
    a.serie && "Série : " + esc(a.serie),
    a.tome && "Tome : " + esc(a.tome),
    a.auteur && "Auteur : " + esc(a.auteur),
    a.editeur && "Éditeur : " + esc(a.editeur),
  ].filter(Boolean).join(" · ");
  const edParts = [
    a.date_edition && "Éd. " + esc(a.date_edition),
    a.langue && esc(a.langue),
    a.type_oeuvre && esc(a.type_oeuvre),
    a.lieu_edition && esc(a.lieu_edition),
    a.isbn && "ISBN " + esc(a.isbn),
    a.format_physique && esc(a.format_physique),
  ].filter(Boolean).join(" · ");
  const depuis = B.depuis !== null ? collection(B.depuis) : null;
  const retour = depuis ? `← ${esc(depuis.nom)}` : "← Le projet";
  const offrir = BDSuppression.offrir({ ...a, ecrivable: ecrire });
  const coches = state.checkedPlanches.size;
  demonterQuiEntre();
  fiche.innerHTML = `${RETOUR_LISTE}
    <section id="album-detail" aria-labelledby="album-titre">
      <p class="bi-retour-collection"><button type="button" class="lf-lien small" data-retour-album="1">${retour}</button></p>
      <div class="lf-tete detail-head"><div>
        ${serieTome(a) ? `<p class="lf-serie">${esc(serieTome(a))}</p>` : ""}
        <h3 id="album-titre" tabindex="-1">${esc(a.titre)} ${a.annee ? `<span class="muted">(${a.annee})</span>` : ""}</h3>
        ${idParts ? `<div class="detail-meta muted small">${idParts}</div>` : ""}
        ${edParts ? `<div class="detail-meta muted small">${edParts}</div>` : ""}
        ${a.source_numerisation ? `<div class="detail-meta muted small">Numérisation : ${esc(a.source_numerisation)}</div>` : ""}
        ${a.lieu_masters ? `<div class="detail-meta muted small">Masters : ${esc(a.lieu_masters)}</div>` : ""}
        <div id="detail-contribs" class="detail-meta small"></div>
        ${a.description ? `<p class="detail-desc">${esc(a.description)}</p>` : ""}
        ${pastilleDemande(a)}
      </div>
      ${ecrire ? `<div class="lf-gestes-tete">
        <button class="ghost small" type="button" id="detail-edit">✎ Modifier l'album</button>
        <button class="ghost small" type="button" id="detail-validate-all">✔ Tout valider</button>
        ${offrir ? `<button class="ghost small sp-ouvrir" type="button" data-act="supprimer" data-id="${a.id}" aria-label="Supprimer ${esc(a.titre)}…">Supprimer…</button>` : ""}
      </div>` : ""}
      </div>
      <p id="detail-valider-msg" class="col-msg muted small" role="status" aria-live="polite"></p>
      ${htmlRangement()}
      ${htmlImport(a)}
      ${barreLot("planches", coches)}
      ${B.perdues ? `<p class="muted small bi-perdues">La sélection de ${pluriel(B.perdues.n, "planche")} de « ${esc(B.perdues.titre)} » a été vidée en changeant d'album.</p>` : ""}
      <div class="bi-relfiltre">
        <label class="muted small detail-relfilter">Relecture
          <select id="rel-filter" aria-label="Filtrer les planches par statut de relecture">
            <option value="">toutes</option>
            <option value="a_faire">à faire</option>
            <option value="en_cours">en cours</option>
            <option value="faite">faite</option>
          </select>
        </label>
      </div>
      <div class="table-cadre bi-cadre" tabindex="0" role="region" aria-label="Planches de l'album">
        <table class="corpus-table planches-table bi-table bi-table-planches">
          <thead><tr><th class="c-chk"><span class="sr-only">Sélection</span></th><th><span class="sr-only">Aperçu</span></th><th>Planche</th>
            <th class="c-act"><span class="sr-only">Gestes</span></th><th>Statut</th>
            <th class="c-num">Régions</th><th class="c-num">Annotées</th>
            <th>Relecture</th><th>Validée</th></tr></thead>
          <tbody>${planchesRows}</tbody>
        </table>
      </div>
    </section>`;
  $("#rel-filter").value = state.relFilter;                       // reflète l'état courant
  if (IMPORT.focus) { IMPORT.focus = false; const b = $("#bi-importer"); if (b) b.focus(); }
  rendreFocusOrdre();
  loadDetailContribs(a.id);
  rangementDeLAlbum(a.id, ecrire);
}

/* ── Importer des planches, EN LOT (UX-11) ─────────────────────────────────────────────
   Le geste qui CONSTITUE un corpus vit ici, à côté du lot qui le traite : l'Atelier garde
   son import à l'unité, pour la page oubliée pendant qu'on annote. Les deux passent par la
   même route, `POST /api/albums/{id}/import`, un fichier par requête (`lib/import-planches.js`
   dit pourquoi, et range les fichiers dans l'ordre de leurs noms).

   Le bouton n'est offert que si le serveur dit l'album `ecrivable` — la question exacte de
   la route (`_get_album(…, ecriture=True)`) —, et ce n'est pas une garde : la route refuse
   d'elle-même. Un import dure des minutes ; son état vit donc HORS de la fiche (`IMPORT`),
   que chaque geste redessine, et la fiche le relit en se dessinant. Un seul à la fois. */
const IMPORT = { albumId: null, titre: "", enCours: false, arreter: false, etat: null,
                 bilan: null, focus: false };

/* COL-4 — la raison d'éteindre l'import dans cet album, ou `null` (`lib/bac-a-sable.js`). */
function raisonPlafond(a) {
  return window.BDBacEcran ? BDBacEcran.raisonImport(a.projet_id) : null;
}

/* Le compte des planches importées a changé (la ligne l'a relu) : la fiche ouverte d'un
   album redessine son seul bloc d'import, sans rien remonter d'autre. */
function majImportPlafond() {
  const a = state.albums.find((x) => x.id === state.openId);
  const bloc = document.getElementById("bi-import");
  if (!a || !bloc || IMPORT.enCours) return;
  const avant = !!bloc.querySelector('#bi-importer[aria-disabled="true"]');
  if (avant === !!raisonPlafond(a)) return;
  const tmp = document.createElement("div");
  tmp.innerHTML = htmlImport(a);
  const neuf = tmp.querySelector("#bi-import");
  if (neuf) bloc.replaceWith(neuf);
}

function htmlImport(a) {
  if (!a.ecrivable) return "";
  const ici = IMPORT.albumId === a.id;
  const ailleurs = IMPORT.enCours && !ici;
  const titre = ailleurs ? `Un import est en cours dans « ${IMPORT.titre} »`
    : "Choisir des images : elles entrent dans l'ordre de leurs noms, à la suite des planches";
  let etat = "", suite = "";
  if (ici && IMPORT.enCours && IMPORT.etat) {
    etat = esc("Import : " + BDImport.libelleProgression(IMPORT.etat));
    suite = `<progress id="bi-import-barre" max="${IMPORT.etat.total}" value="${IMPORT.etat.fait}"
        aria-label="Avancement de l'import"></progress>
      <button class="lf-lien small" type="button" id="bi-import-arreter"
        title="L'envoi en cours va jusqu'au bout ; les suivants ne partent pas"
        ${IMPORT.arreter ? "disabled" : ""}>${IMPORT.arreter ? "Arrêt…" : "Arrêter"}</button>`;
  } else if (ici && IMPORT.bilan) {
    etat = esc(BDImport.libelleBilan(IMPORT.bilan));
    // UX-11 (Hugo, 2026-10-22) — quel fichier est devenu quelle planche, lu dans la liste
    // ACTUELLE : après un réordonnancement, le bilan dit où chacune est maintenant.
    const entres = BDImport.correspondances(IMPORT.bilan, state.planches);
    if (entres.length) {
      suite += `<ul class="bi-import-planches" aria-label="Fichiers importés">${entres.map((x) =>
        `<li>${esc(x.nom)} → ${esc(x.planche)}</li>`).join("")}</ul>`;
    }
    if (IMPORT.bilan.echecs.length) {
      suite += `<ul class="bi-import-echecs" aria-label="Fichiers refusés">${IMPORT.bilan.echecs.map((e) => {
        const l = BDImport.ligneEchec(e);
        return `<li><b>${esc(l.nom)}</b>${esc(l.suite)}</li>`;
      }).join("")}</ul>`;
    }
  }
  const ton = ici && !IMPORT.enCours && IMPORT.bilan ? ` ton-${BDImport.tonBilan(IMPORT.bilan)}` : "";
  // COL-4 — plafond d'import atteint dans SON bac à sable : le geste s'éteint, la raison en
  // infobulle. Éteint et non retiré, et FOCALISABLE (`aria-disabled`, comme ↑ ↓ plus bas) :
  // il dit pourquoi au clavier comme à la souris.
  const plafond = IMPORT.enCours ? null : raisonPlafond(a);
  return `<div class="bi-import" id="bi-import">
    <button class="ghost small" type="button" id="bi-importer" title="${esc(plafond || titre)}"
      ${IMPORT.enCours ? "disabled" : ""}${plafond
        ? ` aria-disabled="true" aria-describedby="bi-import-plafond"` : ""}>⤓ Importer des planches…</button>
    ${plafond ? `<span id="bi-import-plafond" class="sr-only">${esc(plafond)}</span>` : ""}
    <button class="ghost small" type="button" id="bi-ranger-nom"
      title="Remettre les planches dans l'ordre des noms de leurs fichiers d'origine — une confirmation dit d'abord ce qui change"
      ${IMPORT.enCours || ORDRE.enCours ? "disabled" : ""}>⇅ Ranger par nom de fichier</button>
    <span id="bi-import-etat" class="bi-import-etat small${ton}" role="status" aria-live="polite">${etat}</span>
    ${suite}
  </div>
  <p id="bi-ordre-msg" class="col-msg muted small" role="status" aria-live="polite"></p>
  ${ordreEteint(a) ? `<span id="bi-ordre-raison" class="sr-only">${esc(ordreEteint(a))}.</span>` : ""}`;
}

/* ── Changer l'ordre des planches (UX-11, Hugo, 2026-10-22) ────────────────────────────
   Deux gestes, offerts à qui écrit dans l'album (`ecrivable`, la question exacte de la
   route) : « Ranger par nom de fichier », qui confirme d'abord, et ↑ ↓ sur chaque ligne.
   Tous deux envoient l'ordre ENTIER à `PUT /api/albums/{id}/ordre-des-planches`, avec
   l'ordre que la fiche montrait (`vu`) : si quelqu'un l'a changé entre-temps, le serveur
   refuse par un 409 qui le nomme, et la fiche se recharge sur l'ordre actuel. Le numéro
   change, pas les fichiers. Un geste à la fois : un second ↑ pendant que le premier part
   enverrait un ordre déjà périmé, et se refuserait à lui-même. La logique pure (l'ordre
   naturel, un cran, la confirmation) vit dans `lib/import-planches.js`. */
const ORDRE = { enCours: false, focus: null };

/* Pourquoi ↑ ↓ sont éteints sur toute la fiche, ou null s'ils peuvent servir. Le filtre de
   relecture CACHE des planches : un cran se compte dans l'album entier, et ↑ échangerait la
   planche avec une voisine qu'on ne voit pas. Un import en lot dans CET album ajoute des
   planches pendant qu'on les déplacerait : l'ordre envoyé serait périmé à chaque fichier. */
function ordreEteint(a) {
  if (state.relFilter) {
    return "Retirez le filtre de relecture pour changer l'ordre : il cache des planches, "
      + "et un cran se compte dans l'album entier";
  }
  if (IMPORT.enCours && IMPORT.albumId === a.id) {
    return "Un import est en cours dans cet album : l'ordre se change une fois qu'il a fini";
  }
  return null;
}

/* ÉTEINTS pour une raison de la fiche (filtre, import), les boutons restent FOCALISABLES —
   `aria-disabled`, et non `disabled`, qui les sortirait de la tabulation et tairait leur
   raison au clavier, au lecteur d'écran et au doigt (contre-relecture d'UX-11) : la raison
   est leur description (`aria-describedby` → `#bi-ordre-raison`), et les toucher la dit
   dans la ligne d'état. Au BORD de l'album, `disabled` reste : il n'y a rien à expliquer. */
function boutonsOrdre(a, p) {
  if (!a.ecrivable) return "";
  const i = state.planches.findIndex((x) => x.id === p.id);
  const nom = esc(plancheNomLu(p));
  const eteint = ordreEteint(a);
  const bouton = (attr, glyphe, verbe, titre, auBord) => (eteint
    ? `<button type="button" class="icon-btn ordre-eteint" data-${attr}="${p.id}" `
      + `aria-disabled="true" aria-describedby="bi-ordre-raison" title="${esc(eteint)}" `
      + `aria-label="${verbe} ${nom}"><span aria-hidden="true">${glyphe}</span></button>`
    : `<button type="button" class="icon-btn" data-${attr}="${p.id}" title="${titre}" `
      + `aria-label="${verbe} ${nom}" ${auBord || ORDRE.enCours ? "disabled" : ""}>${glyphe}</button>`);
  return bouton("monter", "↑", "Monter", "Monter d'un cran dans l'album", i <= 0)
    + bouton("descendre", "↓", "Descendre", "Descendre d'un cran dans l'album",
             i < 0 || i >= state.planches.length - 1) + " ";
}

/* Après un ↑ ↓, le focus reste sur le bouton de la planche DÉPLACÉE, qui a changé de ligne :
   un second appui la déplace encore. Au bord, ce bouton s'éteint ; le focus passe à l'autre. */
function rendreFocusOrdre() {
  if (!ORDRE.focus) return;
  const { pid, sens } = ORDRE.focus;
  ORDRE.focus = null;
  const voulu = document.querySelector(`[data-${sens < 0 ? "monter" : "descendre"}="${pid}"]`);
  const autre = document.querySelector(`[data-${sens < 0 ? "descendre" : "monter"}="${pid}"]`);
  const b = voulu && !voulu.disabled ? voulu : autre;
  if (b) b.focus();
}

/* Envoie l'ordre voulu ; rend null si c'est passé, sinon l'erreur. La fiche est rechargée
   dans les deux cas : un refus 409 montre l'ordre que l'autre a posé. */
async function envoyerOrdre(albumId, ordre, geste, focus) {
  const vu = state.planches.map((p) => p.id);
  ORDRE.enCours = true;
  let erreur = null;
  try {
    await apiSend("PUT", `/api/albums/${albumId}/ordre-des-planches`, { ordre, vu, geste });
  } catch (e) {
    erreur = e;
  } finally {
    ORDRE.enCours = false;
  }
  if (state.openId !== albumId) return erreur;
  ORDRE.focus = focus || null;
  await openAlbum(albumId);
  return erreur;
}

async function deplacerPlanche(pid, sens) {
  const a = state.albums.find((x) => x.id === state.openId);
  if (ORDRE.enCours || !a) return;
  const eteint = ordreEteint(a);
  if (eteint) { colMsg($("#bi-ordre-msg"), eteint + "."); return; }
  const albumId = state.openId;
  const ordre = BDImport.deplacer(state.planches.map((p) => p.id), pid, sens);
  if (!ordre) return;
  const erreur = await envoyerOrdre(albumId, ordre, sens < 0 ? "monter" : "descendre",
                                    { pid, sens });
  if (state.openId !== albumId) return;
  const p = state.planches.find((x) => x.id === pid);
  if (erreur) colMsg($("#bi-ordre-msg"), erreur.message, true);
  else if (p) colMsg($("#bi-ordre-msg"), `Déplacée : c'est maintenant ${plancheNomLu(p)}.`);
}

async function rangerParNom() {
  if (ORDRE.enCours) return;
  const albumId = state.openId;
  const plan = BDImport.ordreParNom(state.planches);
  const phrase = BDImport.phraseRangerParNom(plan);
  if (!phrase.confirmer) { colMsg($("#bi-ordre-msg"), phrase.message); return; }
  if (!confirm(phrase.confirmer)) return;
  const erreur = await envoyerOrdre(albumId, plan.ordre, "ranger_par_nom");
  if (state.openId !== albumId) return;
  const ligne = $("#bi-ordre-msg");
  if (erreur) colMsg(ligne, erreur.message, true);
  else colMsg(ligne, `Planches rangées dans l'ordre des noms de fichier : ${pluriel(plan.deplacees, "planche a changé", "planches ont changé")} de place.`);
  const b = $("#bi-ranger-nom");
  if (b) b.focus();
}

/* Ce qui change pendant l'import, sans redessiner la fiche : la barre et la ligne d'état. */
function majImport() {
  if (state.openId !== IMPORT.albumId || !IMPORT.etat) return;
  const barre = $("#bi-import-barre"), ligne = $("#bi-import-etat");
  if (!barre || !ligne) { renderDetail(); return; }
  barre.max = IMPORT.etat.total;
  barre.value = IMPORT.etat.fait;
  // L'état final (aucun nom) ne se dit pas : le bilan le remplace aussitôt.
  if (IMPORT.etat.nom) ligne.textContent = "Import : " + BDImport.libelleProgression(IMPORT.etat);
}

async function importerPlanches(albumId, fichiers) {
  const a = state.albums.find((x) => x.id === albumId);
  if (!a || IMPORT.enCours || !fichiers.length) return;
  Object.assign(IMPORT, { albumId, titre: a.titre, enCours: true, arreter: false,
                          etat: { fait: 0, total: fichiers.length,
                                  nom: BDImport.ordonner(fichiers)[0].name, echecs: 0 },
                          bilan: null, focus: false });
  if (state.openId === albumId) {
    // Le bouton se grise pendant l'import : le focus qu'il portait passe à « Arrêter ».
    const actif = document.activeElement;
    const dedans = !!(actif && actif.closest && actif.closest("#bi-import"));
    renderDetail();
    const arreter = $("#bi-import-arreter");
    if (dedans && arreter) arreter.focus();
  }
  const envoyer = (f) => {
    const fd = new FormData();
    fd.append("file", f, f.name);
    return apiSend("POST", `/api/albums/${albumId}/import`, fd);
  };
  let bilan;
  try {
    bilan = await BDImport.importerEnLot(fichiers, envoyer, {
      surProgres: (etat) => { IMPORT.etat = etat; majImport(); },
      doitArreter: () => IMPORT.arreter,
    });
  } finally {
    // Le focus revient au bouton s'il était dans le bloc : la fiche va se redessiner.
    const actif = document.activeElement;
    IMPORT.focus = state.openId === albumId && !!(actif && actif.closest && actif.closest("#bi-import"));
    IMPORT.enCours = false;
    IMPORT.bilan = bilan || null;
  }
  // La liste (le compte de planches) et la fiche, sans recharger la page. Une fiche
  // ouverte sur un autre album n'est pas déplacée : le bilan s'y dit par un toast.
  await loadAlbums();
  loadCorpus();                          // les chiffres de la bande d'outils
  // COL-4 — le compte des planches importées d'un bac à sable : la ligne le relit, et la
  // fiche éteint l'import au plafond (`bd:bac-a-sable-maj`).
  if (window.BDBacEcran) BDBacEcran.rafraichir();
  if (state.openId !== albumId) {
    const texte = `« ${a.titre} » : ${BDImport.libelleBilan(bilan)}`;
    const ton = BDImport.tonBilan(bilan);
    if (ton === "succes") toast(texte, "success");
    else if (ton === "erreur") toast(texte, "error");
    else toast(texte);
  }
}

/* Un import qui part avec la page s'interrompt au fichier en cours : le navigateur le dit. */
window.addEventListener("beforeunload", (e) => {
  if (IMPORT.enCours) { e.preventDefault(); e.returnValue = ""; }
});

/* La validation, en LECTURE, pour qui ne fait que lire l'album : l'état, sans geste. */
function validLu(p) {
  return p.validee ? `<span class="val-lu" title="Validée le ${esc(p.validee)}">✔<span class="sr-only"> validée</span></span>`
                   : `<span class="muted" aria-hidden="true">—</span><span class="sr-only">non validée</span>`;
}

/* COL-3, tranche 2 (décision B4) — une planche suit la règle du DOCUMENT, sans demande à
   elle : on la supprime là où l'on pourrait supprimer l'album sans rien demander
   (`destructible`). Ailleurs, à qui écrit dans l'album, la corbeille reste à sa place mais
   ÉTEINTE, et dit à qui s'adresser — un bouton qui manquerait sans un mot ferait chercher
   un droit. À qui ne fait que lire : rien. Les gestes suivent le NOM de la planche (Hugo,
   2026-10-16) : la corbeille ne tombe plus hors du cadre, dernière d'un tableau qui défile.

   Ce qu'elle dit se lit CONTRE elle, dans la ligne de sa planche — l'idiome de « Ce
   projet » (« le message d'un geste se lit contre son contrôle ») : un toast, en bas à
   droite, couvrait le bouton qu'on venait de toucher. Une seule parle à la fois. */
const PLANCHE_A_DEMANDER = "Cette planche ne se supprime pas d'ici : vous n'avez pas importé "
  + "l'album, ou d'autres y ont travaillé. Adressez-vous à un administrateur de l'instance.";

function corbeillePlanche(a, p, droits) {
  if (a.destructible) {
    return `<button class="icon-btn danger" type="button" data-delp="${p.id}" title="Supprimer la planche"
              aria-label="Supprimer ${esc(plancheNomLu(p))}">🗑</button>`;
  }
  if (!droits.ecrire) return "";
  return `<button class="icon-btn corbeille-eteinte" type="button" data-delp-refus="${p.id}" aria-disabled="true" `
    + `title="${esc(PLANCHE_A_DEMANDER)}" aria-label="Supprimer la planche : `
    + `à demander à un administrateur" aria-describedby="pl-refus-msg-${p.id}">`
    + `<span aria-hidden="true">🗑</span></button>`
    + `<span class="col-msg pl-refus-msg muted small" id="pl-refus-msg-${p.id}" `
    + `role="status" aria-live="polite"></span>`;
}

function direPlancheADemander(bouton) {
  const ligne = $(`#pl-refus-msg-${bouton.dataset.delpRefus}`);
  colMsg(ligne, PLANCHE_A_DEMANDER);
}

/* ── « Sur les collections » : où l'album est rangé, et le geste qui le range ─────────────
   AUTH-2 posait le choix de la collection à la création ; l'appartenance est N-N depuis la
   v14, et un même album peut nourrir deux études. UX-18 l'a sortie de la modale d'édition
   (« Rangé dans », un ✕ et « + Ranger ici ») ; COL-3, tranche 3a (Hugo, sur maquette,
   2026-10-17) en fait UNE seule façon de faire : une case par collection du projet de
   l'ALBUM qu'on lit. COCHER, c'est REJOINDRE le travail (D4 stricte) — fait tout de suite si
   l'on tient chacune de ses collections, sinon DEMANDÉ à qui les tient, et la case passe
   « demandée », indéterminée, sans rien ranger ; DÉCOCHER, c'est supprimer de la
   collection, la première des deux réponses de « Supprimer… », avec ses mots. Une case ne
   s'offre que sur une collection où l'on écrit ; les autres se lisent, éteintes. */
function htmlRangement() {
  return `<section id="album-range" class="album-range">
    <fieldset id="album-range-cases" class="album-cases" aria-describedby="album-range-projet">
      <legend id="album-range-titre">Sur les collections</legend>
      <span class="muted small">Lecture des collections…</span>
    </fieldset>
    <p id="album-range-projet" class="muted small" hidden></p>
    <p id="album-range-msg" class="col-msg muted small" role="status" aria-live="polite"></p>
  </section>`;
}

function rangeMsg(texte, erreur) {
  colMsg($("#album-range-msg"), texte, erreur);
}

const LEGENDE_RANGE = `<legend id="album-range-titre">Sur les collections</legend>`;
/* Ce que les cases ont lu, pour que décocher se confirme AU GESTE, sans relire : `confirm`
   suit le clic, et une relecture glissée entre eux laisserait la case décochée sans réponse. */
let RANGE_LU = { albumId: null, siennes: [], ecrites: [], toutes: [], total: false };

/* Les collections de l'album et ce qu'on peut y faire. Lues dans la route de l'album, qui
   dit leur PROJET (le rangement ne traverse pas les projets, COL-3). Une lecture ratée ne
   laisse AUCUN geste : une case dessinée pour l'album d'avant agirait sur lui (reproduit le
   2026-10-11). */
async function rangementDeLAlbum(albumId, ecrire) {
  const cases = $("#album-range-cases");
  direProjetDeLAlbum({ projets: [], collections: [], ecartees: 0 });
  let siennes = [], toutes = [];
  try {
    siennes = await apiGet(`/api/albums/${albumId}/collections`);
    toutes = await apiGet("/api/collections");
  } catch (e) {
    if (state.openId !== albumId || cases !== $("#album-range-cases")) return;
    cases.innerHTML = LEGENDE_RANGE;
    rangeMsg(`Les collections de cet album n'ont pas pu être lues : ${e.message}`, true);
    $("#album-range").dataset.pret = "1";
    return;
  }
  if (state.openId !== albumId || cases !== $("#album-range-cases")) return;  // une autre fiche s'est ouverte
  const dedans = new Set(siennes.map((c) => c.id));
  const ecrites = new Set(toutes.filter((c) => c.ecrivable).map((c) => c.id));
  // La portée totale se lit ICI, avant de dessiner : décocher en dépend, et il se confirme
  // au geste, sans rien attendre (relecture croisée de t3a-c4).
  const moi = await Promise.resolve(window.BDMoi).catch(() => null);
  const total = !!(moi && moi.acces && moi.acces.total);
  RANGE_LU = { albumId, siennes, ecrites: [...ecrites], toutes, total };
  // COL-3 — un rangement ne traverse pas les projets : seules les collections du projet où
  // l'ALBUM vit déjà se proposent, lu dans ses collections. La règle est dans
  // `lib/projet.js` ; le projet est lu ici parce que la fiche peut s'ouvrir avant que la
  // liste des collections l'ait lu.
  await lireProjetCourant();
  if (state.openId !== albumId || cases !== $("#album-range-cases")) return;
  const candidates = toutes.filter((c) => !dedans.has(c.id));
  const tri = PROJET === null
    ? { projets: [], collections: candidates, ecartees: 0 }     // sans projets lisibles : l'écran d'avant
    : BDProjet.pourRanger(siennes, candidates);
  const album = state.albums.find((a) => a.id === albumId);
  const demandees = new Set((album && album.rejoindre_demande) || []);
  // Celles où il est rangé d'abord, puis celles où l'on peut le ranger, dans l'ordre du serveur.
  const liste = [...siennes, ...tri.collections];
  cases.innerHTML = LEGENDE_RANGE + (liste.length ? liste.map((c) => {
    const sur = dedans.has(c.id);
    // Une portée totale range directement, ce qui clôt la demande qui attendait : sa case
    // reste un geste (relecture croisée de t3a-c4).
    const demande = !sur && demandees.has(c.id) && !total;
    const peut = ecrites.has(c.id) && !demande;
    const titre = !ecrites.has(c.id) ? "Vous lisez cette collection sans y écrire"
      : demande ? "Rejoindre ce travail est demandé : la case attend la réponse"
      : sur ? "Décocher : supprimer de cette collection (le travail reste ailleurs, ou la "
              + "copie est gardée au fonds)"
      : "Cocher : ranger aussi ici — tout de suite si vous tenez toutes ses collections, "
        + "sinon une demande à qui les tient";
    return `<label class="album-case" title="${esc(titre)}">
      <input type="checkbox" data-ranger="${c.id}" data-nom="${esc(c.nom)}" ${sur ? "checked" : ""}
             ${peut ? "" : "disabled"} ${demande ? 'data-demande="1"' : ""}>
      <span class="col-nom">${esc(c.nom)}</span>${demande ? ` <span class="reponse demande">demandé</span>` : ""}</label>`;
  }).join("") : `<span class="muted small">Dans aucune collection que vous lisez.</span>`);
  cases.querySelectorAll("input[data-demande]").forEach((x) => { x.indeterminate = true; });
  if (ecrire) direProjetDeLAlbum(tri);
  // Lu jusqu'au bout : les cases et ce qu'elles proposent sont posées.
  $("#album-range").dataset.pret = "1";
}

/* Ce que les cases ne proposent PAS, et pourquoi (COL-3). Une ligne à demeure sous elles,
   distincte de celle des gestes (`#album-range-msg`). Rien tant que rien n'est écarté :
   avec un seul projet, la fiche est celle d'avant. */
function direProjetDeLAlbum(tri) {
  const ligne = $("#album-range-projet");
  if (!ligne) return;
  const nommer = (id) => {
    const p = PROJETS.find((x) => x.id === id);
    return p ? `« ${p.nom} »` : "(un projet que vous ne pouvez pas nommer)";
  };
  ligne.classList.toggle("alerte", tri.projets.length > 1);
  if (tri.projets.length > 1) {
    // Une base retouchée à la main : l'album vit dans plusieurs projets, et le serveur
    // refusera TOUT nouveau rangement tant que c'est le cas. Les cases cochées restent :
    // c'est en les décochant qu'on en sort.
    ligne.textContent = `Cet album est rangé dans des collections de plusieurs projets `
      + `(${tri.projets.map(nommer).join(", ")}), ce qui ne devrait pas arriver : il ne se `
      + "range nulle part ailleurs tant que c'est le cas. Décochez d'abord les collections "
      + "qui ne sont pas de son projet.";
  } else if (tri.ecartees) {
    ligne.textContent = `Cet album vit dans le projet ${nommer(tri.projets[0])} : seules les `
      + "collections de ce projet sont proposées, un album ne se rangeant pas d'un projet à "
      + "l'autre.";
  } else {
    ligne.textContent = "";
  }
  ligne.hidden = !ligne.textContent;
}

/* Cocher = rejoindre. Le serveur dit si c'est fait (201) ou demandé (202) : la phrase et la
   case suivent sa réponse, jamais l'intention. */
async function rangerAlbum(caseACocher) {
  const id = state.openId, cible = caseACocher.dataset.ranger, nom = caseACocher.dataset.nom;
  const album = state.albums.find((a) => a.id === id);
  if (!id || !cible) return;
  caseACocher.disabled = true;
  let rep;
  try {
    rep = await apiSend("PUT", `/api/albums/${id}/collections/${cible}`);
  } catch (e) {
    caseACocher.checked = false;
    caseACocher.disabled = false;
    rangeMsg(e.message, true);
    return;
  }
  const m = BDBiblio.messageRejoindre(album ? album.titre : "", nom, rep);
  await apresRangement(id, "");
  rangeMsg(m.texte);
}

/* Décocher = supprimer de la collection. Les mots sont ceux de « Supprimer… »
   (`lib/suppression.js`) ; le geste se confirme quand il coûte — la copie part au fonds, on
   perd l'écriture (un aller simple, AUTH-10), on perd l'album de vue — ou on ne pourra pas
   l'y ranger de nouveau soi-même : depuis D4 stricte, écrire des deux côtés ne suffit plus,
   recocher est un rejoindre, qui ne se fait sans demande que si l'on tient toutes les
   collections où il vit encore (`BDBiblio.quiRecocherait`). Seule une portée totale, ou qui
   les tient toutes, n'a rien à confirmer. */
async function sortirAlbum(caseADecocher) {
  const albumId = state.openId, cid = Number(caseADecocher.dataset.ranger);
  const nom = caseADecocher.dataset.nom;
  const album = state.albums.find((a) => a.id === albumId);
  const titre = album ? album.titre : "";
  if (RANGE_LU.albumId !== albumId) { caseADecocher.checked = true; return; }
  const restantes = RANGE_LU.siennes.filter((c) => c.id !== cid);
  const r = BDSuppression.retrait({
    siennes: RANGE_LU.siennes, ecrites: RANGE_LU.ecrites, collectionId: cid,
    partage: !!(album && album.partage), total: RANGE_LU.total,
    recocher: BDBiblio.quiRecocherait(album, restantes, RANGE_LU.toutes, RANGE_LU.total) });
  if (r.confirmer && !confirm(`Supprimer « ${titre} » de « ${nom} » ?\n\n${r.texte}`)) {
    caseADecocher.checked = true;
    return;
  }
  caseADecocher.disabled = true;
  try {
    await apiSend("DELETE", `/api/albums/${albumId}/collections/${cid}`);
  } catch (e) {
    caseADecocher.checked = true;
    caseADecocher.disabled = false;
    rangeMsg(e.message, true);
    return;
  }
  apresRangement(albumId, BDSuppression.apresRetrait(titre, nom, r.reste));
}

/* Ranger ou sortir change ce que la LISTE dit de l'album — où il vit, donc s'il se supprime
   (AUTH-10, COL-3) : elle se relit, et la fiche avec elle. Supprimer un album de la seule
   collection qu'on lisait le fait quitter l'écran — comme sa dernière, qui l'envoie au
   fonds : la fiche se referme en le disant. */
async function apresRangement(albumId, sorti) {
  try { await loadAlbums(); } catch (e) { rangeMsg(e.message, true); return; }
  if (state.albums.some((a) => a.id === albumId)) {
    if (sorti) rangeMsg(sorti);
    return;
  }
  if (sorti) toast(sorti);
}

async function loadDetailContribs(albumId) {
  const el = $("#detail-contribs");
  if (!el) return;
  try {
    const list = await apiGet(`/api/albums/${albumId}/contributions`);
    if (state.openId !== albumId || !$("#detail-contribs")) return;
    $("#detail-contribs").innerHTML = list.length
      ? "Contributions : " + list.map((c) =>
          `${esc(c.nom)}${c.role ? ` <span class="muted">(${esc(c.role)})</span>` : ""}`).join(", ")
      : "";
  } catch (e) { /* non bloquant */ }
}

/* ═══════════════════════════════════════════════════════════════════════════
   Le lot — AU-DESSUS de sa sélection (UX-18)
   ═══════════════════════════════════════════════════════════════════════════
   Les passes et « Lancer » n'apparaissent qu'au-dessus d'une sélection, et nulle part
   ailleurs : des albums cochés dans l'onglet Albums d'une collection, ou des planches
   cochées dans la fiche d'un album. Un lot porte donc sur des albums OU sur les planches
   d'un album, jamais sur un mélange des deux — la barre d'avant disait « 2 albums + 3
   planches », d'un endroit qui n'était aucun des deux. Sans sélection, une phrase dit
   comment en faire une. Les lots en cours restent visibles au-dessus du cadre, quel que
   soit l'objet ouvert. */
function barreLot(sur, n) {
  const mot = sur === "albums" ? "album" : "planche";
  if (!n) {
    return `<p class="muted small bi-lot-aide">${sur === "albums"
      ? "Cochez des albums pour lancer un lot de segmentation, de bulles ou d'OCR."
      : "Cochez des planches pour lancer un lot. Changer d'album vide la sélection."}</p>`;
  }
  return `<div class="lot bi-lot" role="group" aria-label="Lot sur la sélection">
    <b>${pluriel(n, mot)} sélectionné${mot === "planche" ? "e" : ""}${n > 1 ? "s" : ""}</b>
    ${PASSES.map((p) => `<label class="pass"><input type="checkbox" data-passe="${p}" ${state.passes.has(p) ? "checked" : ""}> ${PASSES_LBL[p]}</label>`).join("")}
    <button class="primary small" type="button" data-lancer="${sur}" ${state.passes.size ? "" : "disabled"}>▶ Lancer</button>
    <button class="lf-lien small" type="button" data-vider="${sur}">Tout désélectionner</button>
  </div>`;
}

/* Redessine la barre du lot sans toucher au reste : cocher une case ne redessine pas le
   tableau, qui garderait sinon le focus perdu. */
function rafraichirLot(sur) {
  const racine = sur === "albums" ? document.getElementById("panneau-albums") : $("#album-detail");
  if (!racine) return;
  const n = sur === "albums"
    ? albumsDe(collection($("#col-fiche").dataset.id)).filter((a) => state.checkedAlbums.has(a.id)).length
    : state.checkedPlanches.size;
  const ancien = racine.querySelector(".bi-lot, .bi-lot-aide");
  if (!ancien) return;
  const tmp = document.createElement("div");
  tmp.innerHTML = barreLot(sur, n);
  ancien.replaceWith(tmp.firstElementChild);
}

async function runBatch(sur) {
  const passes = PASSES.filter((p) => state.passes.has(p));
  let corps;
  if (sur === "albums") {
    const c = collection($("#col-fiche") && $("#col-fiche").dataset.id);
    const ici = c ? albumsDe(c).filter((a) => state.checkedAlbums.has(a.id)).map((a) => a.id) : [];
    corps = { passes, album_ids: ici, planche_ids: [] };
  } else {
    corps = { passes, album_ids: [], planche_ids: [...state.checkedPlanches] };
  }
  if (!passes.length || !(corps.album_ids.length || corps.planche_ids.length)) return;
  try {
    const job = await apiSend("POST", "/api/jobs", corps);
    toast(`Lot lancé : ${job.total} planche${job.total > 1 ? "s" : ""}`, "success");
    if (job.verrouillees_ignorees)
      toast(`${job.verrouillees_ignorees} planche(s) verrouillée(s) ignorée(s) 🔒`);
    pollJobs();
  } catch (e) { toast("Lot : " + e.message, "error"); }
}

async function pollJobs() {
  clearTimeout(state.jobTimer);                  // annule tout tick en attente d'emblée
  const gen = (state.jobGen = (state.jobGen || 0) + 1);
  let list = [];
  try { list = await apiGet("/api/jobs"); } catch (e) { return; }
  if (gen !== state.jobGen) return;              // un poll plus récent a pris le relais
  renderJobs(list);
  const actifs = list.some((j) => j.status === "en_cours");
  if (actifs) {
    state.jobTimer = setTimeout(pollJobs, 1000);
  } else if (list.length) {
    await loadAlbums();          // compteurs à jour une fois le lot fini
  }
}

/* Les lots récents. Leurs erreurs se LISENT, sur place : la route les rend (`errors`), et
   « 3 erreur(s) » sans le détail ne disait pas quoi reprendre (relevé le 2026-10-08). Et
   chaque lot dit SUR QUOI il travaille — ses albums, ou « N planches de « Titre » » —, lu
   dans `albums`, que `GET /api/jobs` rend lot par lot et borne à ce qu'on lit : un lot dont
   une planche nous échappe n'est pas listé du tout (`_job_visible`). La phrase vient de
   `BDBiblio.sujetDuLot`. */
function renderJobs(list) {
  const box = $("#jobs");
  const recents = list.slice(0, 4);   // les plus récents (all_jobs trie décroissant)
  if (!recents.length) { box.innerHTML = ""; return; }
  box.innerHTML = recents.map((j) => {
    const pct = j.total ? Math.round(100 * j.done / j.total) : 0;
    const label = { en_cours: "en cours", termine: "terminé", annule: "annulé",
                    echec: "échec" }[j.status] || j.status;
    const err = j.errors.length ? ` · <span class="job-err">${j.errors.length} erreur(s)</span>` : "";
    const detail = j.errors.length ? `<details class="job-erreurs"><summary>Voir les erreurs</summary>
      <ul>${j.errors.map((e) => `<li>${esc(e.planche_id ? `Planche ${e.planche_id}` : "Lot")}${
        e.passe ? ` · ${esc(e.passe)}` : ""} : ${esc(e.erreur || e.message || "")}</li>`).join("")}</ul></details>` : "";
    const sujet = BDBiblio.sujetDuLot(j.albums);
    return `<div class="job job-${j.status}">
      <div class="job-line">
        <b>Lot #${j.id}</b> <span class="muted small">${j.passes.join(" → ")}</span>
        <span class="job-state">${label} — ${j.done}/${j.total}${err}</span>
        ${j.status === "en_cours" ? `<button class="ghost small" type="button" data-cancel="${j.id}">Annuler</button>` : ""}
      </div>
      ${sujet ? `<div class="job-sujet small">${esc(sujet)}</div>` : ""}
      <div class="job-bar"><div class="job-fill" style="width:${pct}%"></div></div>
      ${detail}
    </div>`;
  }).join("");
  box.querySelectorAll("button[data-cancel]").forEach((btn) => {
    btn.onclick = async () => {
      try { await apiSend("POST", `/api/jobs/${btn.dataset.cancel}/annuler`); pollJobs(); }
      catch (e) { toast("Annulation : " + e.message, "error"); }
    };
  });
}

/* ---------------- Création / édition ---------------- */
/* AUTH-2 — la collection est l'unité de cloisonnement : un album y appartient TOUJOURS.
   L'API accepte de retomber sur une collection de repli, mais lui laisser ce choix ferait
   s'entasser tout le corpus dans un seul seau et le cloisonnement ne servirait jamais.
   L'UI demande donc explicitement — sauf quand il n'y a rien à demander.

   Trois cas, et le troisième est celui qui empêche l'impasse :
     · plusieurs collections → la collection de BASE présélectionnée (COL-3, tranche 3a,
       maquette, écran 9), sauf si l'on vient d'une collection ouverte, qui l'est alors ;
       sans base où l'on écrit, aucune présélection, le choix est fait à la main ;
     · une seule            → présélectionnée (la question n'a qu'une réponse) ;
     · aucune               → pas de sélecteur. La note « l'album entrera dans une collection
       par défaut, créée à cette occasion » est partie avec la tranche 3a : tout projet naît
       avec sa base, et elle ne pouvait plus s'afficher.
   À l'ÉDITION, le champ disparaît : déplacer un album d'une collection à l'autre est un
   geste d'espace de travail, qui appartient à AUTH-3.

   COL-3 — LE PROJET COURANT BORNE CETTE LISTE, comme il borne celle des collections plus
   bas : un album naît dans une collection du projet où l'on travaille. Deux choses en
   découlent, que l'écran DIT au lieu de les laisser deviner.
     · Ce que le filtre a écarté : dès qu'une collection où l'on écrit n'est pas proposée,
       une ligne nomme le projet, et dit où en changer.
     · Un projet où l'on n'écrit dans AUCUNE collection, alors qu'on écrit ailleurs : pas de
       liste vide, une phrase — et l'enregistrement s'arrête là (`SANS_COLLECTION_ICI`).
       Sans cet arrêt, la requête partirait sans collection et le serveur rangerait l'album
       dans la collection de repli, c'est-à-dire dans un AUTRE projet que celui qu'on lit en
       haut de la page.
   Sans projet courant — la liste des projets n'a pas pu être lue —, rien n'est filtré :
   l'écran d'avant. Et ce n'est toujours pas une garde : le serveur accepte une collection
   de n'importe quel projet où l'on écrit, l'écran range ce qu'il propose. */
let SANS_COLLECTION_ICI = "";     // pourquoi l'album ne peut pas naître ici, ou vide

async function remplirCollections(edition, depuis = null) {
  const wrap = $("#m-collection-wrap"), sel = $("#m-collection"), note = $("#m-collection-note");
  wrap.hidden = true; note.hidden = true; note.textContent = ""; sel.innerHTML = "";
  SANS_COLLECTION_ICI = "";
  if (edition) return;
  let cols = [];
  try { cols = await apiGet("/api/collections"); } catch (e) { cols = []; }
  // AUTH-12 — seulement celles où l'on ÉCRIT : une collection qu'on ne fait que lire
  // menait à « Collection N introuvable » à l'enregistrement. Le serveur le dit
  // (`ecrivable`), comme `exportable` pour l'export.
  const ecrites = cols.filter((c) => c.ecrivable);
  // Le projet est lu ICI aussi : la modale peut s'ouvrir avant que le bloc des collections
  // ait fini de se dessiner, et un filtre absent par simple hâte ne se verrait pas.
  await lireProjetCourant();
  cols = BDProjet.duProjet(ecrites, PROJET);
  const projet = colNomProjet();
  if (!cols.length && ecrites.length) {
    SANS_COLLECTION_ICI = `Aucune collection ne peut accueillir cet album dans le projet `
      + `« ${projet} ».`;
    note.textContent = `Vous n'écrivez dans aucune collection du projet « ${projet} » : `
      + "l'album ne peut pas y être créé. Créez-y d'abord une collection, ou choisissez un "
      + "autre projet en haut de la page.";
    note.hidden = false;
    return;
  }
  if (!cols.length) {
    // Sans collection où écrire : qui écrit PARTOUT (administrateur, mono-poste) n'a rien à
    // lire ici — le serveur range l'album dans la collection de repli ; les autres seront
    // refusés, et le savoir avant de remplir le formulaire vaut mieux.
    const moi = await Promise.resolve(window.BDMoi).catch(() => null);
    if (moi && moi.acces && moi.acces.total) return;
    note.textContent = "Vous n'écrivez dans aucune collection : l'album ne pourra pas être "
      + "créé. Demandez un accès en écriture au propriétaire d'une collection.";
    note.hidden = false;
    return;
  }
  // La base présélectionnée, sauf si l'on vient d'une collection ouverte
  // (`lib/bibliotheque.js`). L'ordre reste celui du serveur.
  const pre = BDBiblio.destinationParDefaut(cols, depuis);
  if (cols.length > 1) sel.appendChild(new Option("— choisir —", ""));
  for (const c of cols) sel.appendChild(new Option(c.nom, String(c.id)));
  sel.value = pre === null ? "" : String(pre);
  wrap.hidden = false;
  if (cols.length < ecrites.length) {
    note.textContent = `Seules les collections du projet « ${projet} » sont proposées : pour `
      + "créer l'album dans un autre projet, choisissez-le en haut de la page.";
    note.hidden = false;
  }
}

async function openModal(album, depuis = null) {
  state.editingId = album ? album.id : null;
  $("#modal-title").textContent = album ? "Éditer l'album" : "Nouvel album";
  const g = (k) => (album && album[k]) || "";
  $("#m-titre").value = album ? album.titre : "";
  $("#m-serie").value = g("serie");
  $("#m-tome").value = g("tome");
  $("#m-auteur").value = g("auteur");
  $("#m-annee").value = g("annee");
  $("#m-editeur").value = g("editeur");
  $("#m-desc").value = g("description");
  $("#m-date-edition").value = g("date_edition");
  $("#m-date-originale").value = g("date_originale");
  $("#m-langue").value = g("langue");
  $("#m-type").value = g("type_oeuvre");
  $("#m-lieu").value = g("lieu_edition");
  $("#m-tirage").value = g("edition_tirage");
  $("#m-isbn").value = g("isbn");
  $("#m-format").value = g("format_physique");
  $("#m-source-num").value = g("source_numerisation");   // matériel (A6)
  $("#m-lieu-masters").value = g("lieu_masters");         // IMG-1 : où vivent les masters
  $("#m-msg").textContent = "";
  // Contributions : éditables seulement sur un album EXISTANT (elles ont besoin de son id).
  $("#m-contrib-nom").value = "";
  $("#m-contrib-role").value = "";
  const exist = !!state.editingId;
  $("#m-contrib-hint").hidden = exist;
  // Par son IDENTIFIANT, et non par `$(".contrib-add")` : ce sélecteur rendait la
  // PREMIÈRE ligne de cette classe dans la page. C'était déjà celle de l'appartenance et
  // non celle des contributions ; depuis COL-2, c'eût été le formulaire de création de
  // collection, masqué à chaque « Nouvel album » sans qu'aucune erreur ne le dise.
  $("#m-contrib-ligne").style.display = exist ? "" : "none";
  $("#m-contribs").innerHTML = "";
  if (exist) { loadRoles(); loadContributions(state.editingId); }
  // AWAIT avant d'ouvrir : sans cela, une sauvegarde plus rapide que la requête verrait
  // le sélecteur encore caché et retomberait EN SILENCE sur la collection de repli —
  // exactement ce que ce champ existe pour empêcher.
  await remplirCollections(exist, depuis);
  $("#album-modal").hidden = false;
  $("#m-titre").focus();
}

async function loadRoles() {
  try {
    const roles = await apiGet("/api/contribution-roles");
    $("#dl-roles").innerHTML = roles.map((r) => `<option value="${esc(r.label)}">`).join("");
  } catch (e) { /* datalist vide : non bloquant */ }
}

async function loadContributions(albumId) {
  try { renderContribs(await apiGet(`/api/albums/${albumId}/contributions`)); }
  catch (e) { $("#m-contribs").innerHTML = ""; }
}

function renderContribs(list) {
  const box = $("#m-contribs");
  if (!list.length) { box.innerHTML = '<p class="muted small">Aucune contribution.</p>'; return; }
  box.innerHTML = list.map((c) => `
    <div class="contrib-row">
      <span class="contrib-nom">${esc(c.nom)}</span>
      <span class="contrib-role muted small">${c.role ? esc(c.role) : "—"}</span>
      <button class="icon-btn danger" type="button" data-delc="${c.id}" title="Retirer" aria-label="Retirer ${esc(c.nom)}">✕</button>
    </div>`).join("");
  box.querySelectorAll("button[data-delc]").forEach((b) => {
    b.onclick = () => removeContribution(Number(b.dataset.delc));
  });
}

async function addContribution() {
  if (!state.editingId) return;
  const nom = $("#m-contrib-nom").value.trim();
  if (!nom) { $("#m-contrib-nom").focus(); return; }
  const role = $("#m-contrib-role").value.trim() || null;
  try {
    await apiSend("POST", `/api/albums/${state.editingId}/contributions`, { nom, role });
    $("#m-contrib-nom").value = "";
    $("#m-contrib-role").value = "";
    await loadContributions(state.editingId);
    await loadRoles();                 // un nouveau rôle rejoint la datalist
    $("#m-contrib-nom").focus();
  } catch (e) { $("#m-msg").textContent = "✗ " + e.message; }
}

async function removeContribution(id) {
  try { await apiSend("DELETE", `/api/contributions/${id}`); await loadContributions(state.editingId); }
  catch (e) { $("#m-msg").textContent = "✗ " + e.message; }
}

function closeModal() { $("#album-modal").hidden = true; }

async function saveAlbum() {
  const titre = $("#m-titre").value.trim();
  if (!titre) { $("#m-msg").textContent = "Titre requis."; return; }
  // COL-3 — aucune collection où écrire dans le projet courant : rien ne part. La note sous
  // le titre dit quoi faire ; ici, pourquoi le bouton n'a rien enregistré.
  if (!state.editingId && SANS_COLLECTION_ICI) {
    $("#m-msg").textContent = SANS_COLLECTION_ICI;
    return;
  }
  // Le sélecteur n'est visible qu'à la création, et seulement s'il y a un choix à faire.
  const wrap = $("#m-collection-wrap");
  const collectionId = wrap.hidden ? null : ($("#m-collection").value || null);
  if (!wrap.hidden && !collectionId) {
    $("#m-msg").textContent = "Choisissez la collection qui accueillera cet album.";
    return;
  }
  const btn = $("#m-save");
  if (btn.disabled) return;               // anti-double-soumission (sinon album dupliqué)
  btn.disabled = true;
  const annee = parseInt($("#m-annee").value, 10);
  const val = (id) => $(id).value.trim() || null;
  const body = {
    titre,
    serie: val("#m-serie"),
    tome: val("#m-tome"),
    auteur: val("#m-auteur"),
    annee: isNaN(annee) ? null : annee,
    editeur: val("#m-editeur"),
    description: val("#m-desc"),
    date_edition: val("#m-date-edition"),
    date_originale: val("#m-date-originale"),
    langue: val("#m-langue"),
    type_oeuvre: val("#m-type"),
    lieu_edition: val("#m-lieu"),
    edition_tirage: val("#m-tirage"),
    isbn: val("#m-isbn"),
    format_physique: val("#m-format"),
    source_numerisation: val("#m-source-num"),   // matériel (A6)
    lieu_masters: val("#m-lieu-masters"),        // IMG-1 : le serveur ne garde qu'une copie de travail
  };
  if (collectionId) body.collection_id = parseInt(collectionId, 10);   // AUTH-2
  try {
    if (state.editingId) await apiSend("PUT", `/api/albums/${state.editingId}`, body);
    else await apiSend("POST", "/api/albums", body);
    closeModal();
    await loadAlbums();
    toast("Album enregistré", "success");
  } catch (e) { $("#m-msg").textContent = "✗ " + e.message; }
  finally { btn.disabled = false; }
}

/* ── « Supprimer… » : deux réponses (COL-3, tranche 2) ──────────────────────────────────
   Décidé par Hugo (2026-10-09, confirmé le 2026-10-11) : SUPPRIMER DE LA COLLECTION ne
   détruit rien — le travail reste là où l'album vit encore, ou, si c'était sa dernière
   collection, la copie est GARDÉE AU FONDS avec tout son travail ; SUPPRIMER
   DÉFINITIVEMENT efface tout de suite quand on a importé l'album et que personne d'autre
   n'y a travaillé, et sinon DEMANDE à un administrateur, motif à l'appui — et, depuis le
   2026-10-15, une certification : que les données posées sur les planches ne sont pas
   importantes.

   Le panneau EST la confirmation : chaque réponse dit ce qui arrivera avant qu'on la
   choisisse. Les mots se choisissent dans `lib/suppression.js`, sous table de vérité ; QUI
   peut quoi, le serveur le dit album par album (`destructible`, `partage`, `demande`), et
   ce panneau ne le recalcule pas.

   La première réponse propose un bouton par collection de l'album OÙ L'ON ÉCRIT, qu'on ait
   ouvert le panneau de l'onglet Albums d'une collection ou de la fiche de l'album (UX-18) :
   le geste vaut pour l'album, pas pour la collection d'où l'on vient. Les collections qu'on
   lit se nomment ; celle qu'on ne lit pas se dit sans nom (`partage`). */
const SUPPR = { album: null, definitif: null };

function spMsg(texte, erreur) {
  const el = $("#sp-msg");
  el.textContent = texte || "";
  el.classList.toggle("erreur", !!erreur);
}

async function ouvrirSuppression(a) {
  SUPPR.album = a;
  SUPPR.definitif = null;
  $("#sp-titre").textContent = `Supprimer « ${a.titre} »`;
  spMsg("");
  $("#sp-motif").value = "";
  $("#sp-certif").checked = false;
  const retrait = $("#sp-retrait");
  retrait.innerHTML = `<p class="muted small">Lecture des collections…</p>`;
  const moi = await Promise.resolve(window.BDMoi).catch(() => null);
  const total = !!(moi && moi.acces && moi.acces.total);
  // La seconde réponse ne dépend que de la ligne : elle se dit tout de suite.
  const d = BDSuppression.definitif({ destructible: a.destructible, demande: a.demande,
                                      total, moi: MOI.login, soeur: !!a.soeur });
  SUPPR.definitif = d;
  $("#sp-def-texte").textContent = d.texte;
  $("#sp-motif-wrap").hidden = d.mode !== "demande";
  // La certification accompagne la demande (Hugo, 2026-10-15) : ses mots sont ceux de
  // `lib/suppression.js`, et le serveur l'exige aussi.
  $("#sp-certif-wrap").hidden = d.mode !== "demande";
  $("#sp-certif-texte").textContent = BDSuppression.CERTIFICATION.texte;
  $("#sp-certif-libelle").textContent = BDSuppression.CERTIFICATION.caseACocher;
  $("#sp-def").hidden = !d.bouton;
  $("#sp-def").textContent = d.bouton;
  $("#suppr-modal").hidden = false;
  $("#sp-annuler").focus();
  let siennes, toutes;
  try {
    siennes = await apiGet(`/api/albums/${a.id}/collections`);
    toutes = await apiGet("/api/collections");
  } catch (e) {
    // Rien n'est offert sur ce qu'on n'a pas lu : un bouton nommé d'après une collection
    // supposée retirerait l'album d'ailleurs que là où l'on croit.
    retrait.innerHTML = "";
    spMsg(`Les collections de cet album n'ont pas pu être lues : ${e.message}`, true);
    return;
  }
  if (SUPPR.album !== a) return;          // on a fermé, ou ouvert un autre album, entre-temps
  const ecrites = toutes.filter((c) => c.ecrivable).map((c) => c.id);
  const ouJEcris = siennes.filter((c) => ecrites.includes(c.id));
  retrait.innerHTML = ouJEcris.length
    ? ouJEcris.map((c) => {
        const restantes = siennes.filter((x) => x.id !== c.id);
        const r = BDSuppression.retrait({ siennes, ecrites, collectionId: c.id,
                                          partage: a.partage, total,
                                          recocher: BDBiblio.quiRecocherait(a, restantes, toutes, total) });
        return `<div class="sp-option">
          <p class="sp-texte" id="sp-r-${c.id}">${esc(r.texte)}</p>
          <button type="button" class="ghost" data-retirer="${c.id}" data-nom="${esc(c.nom)}"
                  data-reste="${r.reste}" aria-describedby="sp-r-${c.id}">Supprimer de « ${esc(c.nom)} »</button>
        </div>`;
      }).join("")
    : `<p class="muted small">Vous n'écrivez dans aucune de ses collections.</p>`;
}

function fermerSuppression() {
  SUPPR.album = null;
  $("#suppr-modal").hidden = true;
}

async function spRetirer(bouton) {
  const a = SUPPR.album;
  if (!a || bouton.disabled) return;
  bouton.disabled = true;
  try {
    await apiSend("DELETE", `/api/albums/${a.id}/collections/${bouton.dataset.retirer}`);
  } catch (e) { spMsg(e.message, true); bouton.disabled = false; return; }
  fermerSuppression();
  state.checkedAlbums.delete(a.id);
  await loadAlbums();
  toast(BDSuppression.apresRetrait(a.titre, bouton.dataset.nom, bouton.dataset.reste));
}

async function spDefinitif() {
  const a = SUPPR.album, d = SUPPR.definitif, bouton = $("#sp-def");
  if (!a || !d || bouton.disabled) return;
  let motif = "";
  if (d.mode === "demande") {
    motif = $("#sp-motif").value.trim();
    if (!motif) {
      spMsg("Dites pourquoi : c'est ce que l'administrateur lira pour décider.", true);
      $("#sp-motif").focus();
      return;
    }
    if (!$("#sp-certif").checked) {
      spMsg(BDSuppression.CERTIFICATION.manque, true);
      $("#sp-certif").focus();
      return;
    }
  }
  bouton.disabled = true;
  try {
    if (d.mode === "direct") await apiSend("DELETE", `/api/albums/${a.id}`);
    else await apiSend("POST", "/api/demandes",
                       { genre: BDSuppression.GENRE_DOCUMENT, album_id: a.id, motif,
                         certifie: true });
  } catch (e) {
    spMsg(e.message, true);
    bouton.disabled = false;
    // Le serveur a pu changer d'avis entre la liste et le geste (une demande déposée par un
    // autre, un travail ajouté) : la ligne se relit, sans fermer le panneau.
    loadAlbums().catch(() => {});
    return;
  }
  bouton.disabled = false;
  fermerSuppression();
  if (d.mode === "direct") state.checkedAlbums.delete(a.id);
  await loadAlbums();
  toast(BDSuppression.apresDefinitif(a.titre, d.mode, !!a.soeur), "success");
}


/* Cellule « Planche » : numéro ÉDITORIAL (dérivé, cité) pour le récit, ou pastille
   Paratexte ; le RANG dans l'album reste visible en discret (clé de tri, ≠ du numéro
   cité) — l'ordre d'import, tant qu'on ne l'a pas changé (UX-11, ↑ ↓ et « Ranger par nom
   de fichier »). Cf. docs/numerotation-et-citation.md. */
function plancheNum(p) {
  const imp = `<span class="muted small" title="rang dans l'album (l'ordre d'import, sauf s'il a été changé)">i.${String(p.numero).padStart(3, "0")}</span>`;
  if (p.role === "recit")
    return `<b title="Numéro éditorial (cité)">planche ${p.numero_editorial}</b><br>${imp}`;
  return `<span class="badge" title="Paratexte — hors numérotation du récit">Paratexte</span><br>${imp}`;
}

/* Le nom d'une planche tel que l'ÉCRAN le montre, pour ce qui le dit à voix haute. La case
   de sélection annonçait l'ordre d'IMPORT (« planche 5 ») là où la ligne affiche le numéro
   ÉDITORIAL (« planche 3 ») : deux numéros pour la même ligne, et c'est celui qu'on ne voit
   pas qu'entendait le lecteur d'écran. */
function plancheNomLu(p) {
  const imp = `i.${String(p.numero).padStart(3, "0")}`;
  return p.role === "recit" ? `la planche ${p.numero_editorial} (${imp})` : `le paratexte ${imp}`;
}

/* Matériel de numérisation (A6) — résolution / mode / dimensions physiques (cm, dérivées
   px÷dpi côté serveur). Ligne discrète en lecture seule ; masquée si rien de connu. */
function materielInfo(p) {
  const parts = [];
  if (p.dpi_x) parts.push(p.dpi_x === p.dpi_y ? `${p.dpi_x} dpi` : `${p.dpi_x}×${p.dpi_y} dpi`);
  if (p.mode) parts.push(esc(p.mode));
  if (p.dimensions_cm) parts.push(`${p.dimensions_cm.largeur}×${p.dimensions_cm.hauteur} cm`);
  return parts.length
    ? `<br><span class="muted small" title="Matériel de numérisation">${parts.join(" · ")}</span>`
    : "";
}

/* Bascule du rôle éditorial : récit ⇄ paratexte (couverture, liminaire, pub…).
   Marquer/retirer renumérote tout l'album (numéro éditorial dérivé). */
function roleToggle(p) {
  const para = p.role !== "recit";
  return `<button class="icon-btn" data-role="${p.id}" data-to="${para ? "recit" : "paratexte"}" `
    + `title="${para ? "Paratexte — cliquer pour rétablir en planche de récit"
                     : "Marquer comme paratexte (couverture, liminaire, pub… — hors numérotation)"}">`
    + `${para ? "📖" : "🏷"}</button>`;
}

async function setRole(pid, role) {
  try {
    await apiSend("PATCH", `/api/planches/${pid}/role`, { role });
    await openAlbum(state.openId);   // renumérotation dérivée → recharge l'album
    toast(role === "paratexte" ? "Planche marquée Paratexte 🏷" : "Planche rétablie en récit 📖");
  } catch (e) { toast("Rôle : " + e.message, "error"); }
}

/* Relecture grammaticale (ANN-4) : pastille du statut EFFECTIF (dérivé ⊕ forcé) + sélecteur
   d'override (3 états | auto). Le titre détaille le dérivé (relus/tokens) et l'éventuel forçage. */
function relectureCell(p, ecrire = true) {
  const rs = p.relecture_statut
    || { statut: "a_faire", derive: "a_faire", force: false, tokens: 0, relus: 0 };
  const title = `Dérivé : ${RELECTURE_LBL[rs.derive]} (${rs.relus}/${rs.tokens} token(s) relu(s))`
    + (rs.force ? ` · forcé « ${RELECTURE_LBL[rs.statut]} »` : "");
  const opts = ["a_faire", "en_cours", "faite"].map((s) =>
    `<option value="${s}"${rs.force && rs.statut === s ? " selected" : ""}>${RELECTURE_LBL[s]}</option>`).join("");
  const pastille = `<span class="rel-pill rel-${rs.statut}${rs.force ? " rel-force" : ""}" title="${esc(title)}">`
    + `${RELECTURE_LBL[rs.statut]}</span>`;
  // Forcer le statut est un geste d'écriture : à qui ne fait que lire, la pastille seule.
  if (!ecrire) return pastille;
  return pastille
    + `<select class="rel-sel" data-rel="${p.id}" title="Forcer le statut de relecture (ou auto)" `
    + `aria-label="Forcer la relecture de la planche ${p.numero}">`
    + `<option value=""${rs.force ? "" : " selected"}>auto</option>${opts}</select>`;
}

async function setRelecture(pid, value) {
  try {
    await apiSend("PATCH", `/api/planches/${pid}/relecture`, { relecture: value || null });
    await openAlbum(state.openId);   // recharge : pastille + filtre reflètent le nouveau statut
  } catch (e) { toast("Relecture : " + e.message, "error"); }
}

/* Valider une planche : UN bouton qui porte son état (UX-18, tranché par Hugo le 2026-10-17
   sur la maquette de la tranche 3a). ✔ gris quand elle ne l'est pas, ✔ vert et ENFONCÉ quand
   elle l'est (`aria-pressed`), et le même clic dans les deux sens — le verrou parle déjà
   ainsi. Le badge ✔ à côté d'un ↺ disait l'état et l'acte inverse avec deux signes, et le
   ↺ se lisait « annuler » plutôt que « retirer la validation ». Le nom accessible reste le
   même dans les deux états : c'est `aria-pressed` qui dit lequel, et la date, quand le
   serveur la rend, passe dans l'infobulle. */
function validToggle(p) {
  const on = !!p.validee;
  return `<button type="button" class="icon-btn val-btn" data-val="${p.id}" `
    + `data-on="${on ? 0 : 1}" aria-pressed="${on}" `
    + `aria-label="Validée : ${esc(plancheNomLu(p))}" `
    + `title="${on ? "Validée le " + esc(p.validee) + " — cliquer pour retirer la validation"
                   : "Marquer comme validée"}">✔</button>`;
}

async function validatePlanche(pid, on) {
  try {
    await apiSend("PATCH", `/api/planches/${pid}/validation`, { validee: on });
    await loadAlbums();   // rafraîchit table + album ouvert + synthèse
  } catch (e) { toast("Validation : " + e.message, "error"); }
}

/* Bascule de verrou : une planche verrouillée est sautée par les lots (et ses
   passes directes refusées). 🔒 = verrouillée, 🔓 = libre. */
function lockToggle(p) {
  const on = !!p.verrouillee;
  return `<button class="icon-btn${on ? " locked" : ""}" data-lock="${p.id}" `
    + `data-on="${on ? 0 : 1}" `
    + `title="${on ? "Verrouillée " + esc(parQui(p)) + "le " + esc(p.verrouillee)
                     + " — cliquer pour déverrouiller"
                   : "Verrouiller (protéger des traitements en lot)"}">`
    + `${on ? "🔒" : "🔓"}</button>`;
}

/* AUTH-1 — « verrouillée le … » ne disait pas PAR QUI, alors que `verrou_par` est consigné
   depuis la v22. C'est pourtant la seule information dont on ait besoin : le verrou est
   purement informatif, n'importe qui peut le lever, et la question qu'on se pose devant est
   « à qui demander avant de le faire ».

   « par vous » se décide sur le LOGIN et non sur le nom affiché : deux personnes peuvent
   porter le même nom, et se voir attribuer le verrou d'un homonyme serait pire que de ne
   rien savoir. Rien en mono-poste, où l'agent est NULL — un acte anonyme, honnêtement. */
/* L'identité courante, pour dire « verrouillé par vous » plutôt que par votre propre nom.
   Elle vient de `common.identite()` depuis UX-10 : la page d'administration en a besoin
   aussi, pour d'autres raisons, et deux copies auraient fini par se répondre autrement. */
let MOI = { login: null, groupes_admin: [] };

function parQui(p) {
  if (!p.verrou_par) return "";
  if (MOI.login && p.verrou_par === MOI.login) return "par vous ";
  return "par " + (p.verrou_par_nom || p.verrou_par) + " ";
}

async function lockPlanche(pid, on) {
  try {
    await apiSend("PATCH", `/api/planches/${pid}/verrou`, { verrouillee: on });
    await openAlbum(state.openId);
    toast(on ? "Planche verrouillée 🔒" : "Planche déverrouillée 🔓");
  } catch (e) { toast("Verrou : " + e.message, "error"); }
}

/* « Tout valider » : UN geste, UNE requête (`POST /api/albums/{id}/valider`, UX-18). Elle
   partait en une requête par planche, l'une après l'autre — 122 pour le plus gros album de
   la capture du 2026-10-08 —, et un échec au milieu laissait l'album à moitié validé. Le
   serveur valide désormais tout dans une transaction : un échec n'a RIEN validé, et le
   message le dit. Le nombre annoncé vient de la RÉPONSE et non de la liste affichée, que
   quelqu'un d'autre a pu changer entre-temps. */
async function validateAllAlbum() {
  const todo = state.planches.filter((p) => !p.validee);
  const ligne = $("#detail-valider-msg");
  if (!todo.length) { colMsg(ligne, "Toutes les planches sont déjà validées."); return; }
  if (!confirm(`Valider ${todo.length} planche(s) de cet album ?`)) return;
  const albumId = state.openId;
  colMsg(ligne, `Validation de ${todo.length} planche(s)…`);
  let r;
  try {
    r = await apiSend("POST", `/api/albums/${albumId}/valider`);
  } catch (e) {
    await loadAlbums().catch(() => {});
    colMsg($("#detail-valider-msg"), `Aucune planche validée : ${e.message}`, true);
    return;
  }
  await loadAlbums();
  const n = r.validees.length;
  colMsg($("#detail-valider-msg"), `${n} planche${n > 1 ? "s" : ""} validée${n > 1 ? "s" : ""}.`);
}

async function deletePlanche(pid) {
  if (!confirm("Supprimer cette planche et ses régions ? Irréversible.")) return;
  try {
    await apiSend("DELETE", `/api/planches/${pid}`);
    state.checkedPlanches.delete(pid);
    await loadAlbums();          // les compteurs, et la fiche de l'album, rouverte
    toast("Planche supprimée");
  } catch (e) { toast("Suppression : " + e.message, "error"); }
}


/* ═══════════════════════════════════════════════════════════════════════════
   Qui entre — MONTÉ dans l'onglet de la fiche, écrit dans `static/lib/qui-entre.js` (UX-16)

   Ce fichier ne dessine rien du panneau et n'appelle pas ses routes — un cliquet le vérifie
   (`tests/test_qui_entre_module.py`). Ce qui RESTE à l'hôte, ce sont des règles d'ÉCRAN :
   la description des droits, lue une fois pour la page ; « un seul message à la fois »
   (`colTaireSauf`) ; l'adresse `?collection=…&groupe=…`, lue ici et PASSÉE au montage ; et,
   depuis UX-18, la place : le panneau vit dans la COLONNE de la fiche, plus étroite que la
   page — `ajusterALaPlace` lui fait céder le tableau aux cartes dès qu'il n'y tient plus.
   ═══════════════════════════════════════════════════════════════════════════ */

/* La description des droits, lue UNE fois par page. Illisible, elle vaut null : le module
   le dit et ne dessine aucune case, plutôt que d'inventer un modèle. */
let DROITS = null;
const DROITS_PRETS = apiGet("/api/droits")
  .then((d) => { DROITS = BDDroits.estValide(d) ? d : null; })
  .catch(() => { DROITS = null; });

let QUI_ENTRE = null;             // { id, poignee } : le montage vivant, un à la fois
let PRESELECTION = null;          // { id, groupe } — `?collection=…&groupe=…`, passée une fois

function demonterQuiEntre() {
  if (QUI_ENTRE) QUI_ENTRE.poignee.demonter();
  QUI_ENTRE = null;
}

/* La garde n'est pas posée ici : le module reçoit `administrable` et dit lui-même ce qu'un
   participant non propriétaire doit lire (leçon d'AUTH-4 — un bloc pose SA question, jamais
   son contenant, et l'onglet « Qui entre » s'ouvre à tous). */
function monterQuiEntre(panneau, c) {
  demonterQuiEntre();
  const groupe = PRESELECTION && PRESELECTION.id === c.id ? PRESELECTION.groupe : null;
  QUI_ENTRE = { id: c.id, poignee: BDQuiEntre.monter(panneau.querySelector("[data-qui-entre]"), {
    collection: { id: c.id, nom: c.nom, administrable: !!c.administrable },
    droits: DROITS,
    groupesAdmin: MOI.groupes_admin,
    preselection: groupe,
    surMessage: colTaireSauf,
    ajusterALaPlace: true,
  }) };
}

/* ═══════════════════════════════════════════════════════════════════════════
   COL-3, tranche 3a — prendre un document, rejoindre un travail, répondre
   ═══════════════════════════════════════════════════════════════════════════
   Tranché par Hugo sur maquette le 2026-10-17. On prend au fonds DANS la Bibliothèque :
   « + Prendre du fonds… », au responsable du projet et à l'administrateur seulement (D3),
   en tête du corpus (vers la base) et dans l'onglet Albums d'une collection (vers elle) ;
   « + Prendre dans le projet… », à qui écrit dans la collection, sur les albums du projet
   qu'il lit. Une demande de rejoindre se répond là où vit qui consent (D11) : le bloc ⚑ en
   tête de l'onglet Albums de SA collection, la marque ⚑ sur elle dans le bloc
   « Collections », un compteur dans la bande d'outils — rien dans la bande du haut. Le
   responsable suit ses demandes au fonds dans la fiche du projet (Administration) ; un
   rappel court y mène depuis la bande d'outils.

   Rien ici n'est une garde : ce que l'écran offre se lit dans ce que le serveur a dit
   (`gerable`, `ecrivable`, `administrable`, `repondable`), et chaque geste est tranché par
   lui — un refus se dit sur place, dans ses mots. */
const P3A = {
  recues: new Map(),        // collection → demandes de rejoindre auxquelles on peut répondre
  mesDemandes: 0,           // mes demandes au fonds qui attendent, dans le projet courant
  prise: null,              // le panneau « Prendre du fonds… » ouvert
  dansProjet: null,         // le panneau « Prendre dans le projet… » ouvert
  minuterie: null,
};
const NOTICES_PAR_PAGE = 25;

function projetCourant() {
  return PROJETS.find((x) => x.id === PROJET) || null;
}

/* ── Ce qui attend une réponse ─────────────────────────────────────────────────────────── */

/* Les demandes de rejoindre REÇUES, collection par collection, pour celles qu'on administre
   dans le projet courant. Une portée totale n'en lit aucune ici : l'administrateur y répond
   dans « À faire », en recours (maquette, écran 3). Une lecture ratée ne compte rien. */
async function chargerDemandesRecues() {
  const recues = new Map();
  if (!B.total) {
    const miennes = COLS.projet.filter((c) => c.administrable);
    await Promise.all(miennes.map(async (c) => {
      const l = await apiGet(`/api/collections/${c.id}/demandes`).catch(() => []);
      const a = BDBiblio.demandesARepondre(l, B.total);
      if (a.length) recues.set(c.id, a);
    }));
  }
  P3A.recues = recues;
  rendreRappels();
  rendreListeCollections();
  majPastilleOnglet();
  const f = $("#col-fiche");
  if (f && collection(f.dataset.id)) rendreBlocRecues(collection(f.dataset.id));
}

/* Les demandes au fonds du RESPONSABLE, en attente, dans le projet courant : le rappel de
   la bande d'outils. Celles qu'il a déposées lui-même ; une portée totale n'en dépose
   aucune qui attende (elle prend). */
async function chargerMesDemandes() {
  const p = projetCourant();
  let n = 0;
  if (p && p.gerable && !B.total && MOI.login) {
    const l = await apiGet(`/api/projets/${p.id}/demandes`).catch(() => []);
    n = l.filter((d) => d.en_attente && d.demandeur === MOI.login).length;
  }
  P3A.mesDemandes = n;
  rendreRappels();
}

function nbRecues() {
  const ids = new Set();
  P3A.recues.forEach((l) => l.forEach((d) => ids.add(d.id)));
  return ids.size;
}

/* La bande d'outils : le compteur des demandes à répondre, et le rappel des siennes. */
function rendreRappels() {
  const zone = $("#bi-rappels");
  if (!zone) return;
  const n = nbRecues();
  const p = projetCourant();
  zone.innerHTML = (n ? `<button type="button" class="rappel" id="bi-recues-compteur"
        title="Des demandes de rejoindre attendent votre réponse">${pluriel(n, "demande")} à répondre</button>` : "")
    + (P3A.mesDemandes && p ? `<a class="rappel calme" id="bi-mes-demandes"
        href="/administration?vue=projets&projet=${p.id}"
        title="Vos demandes au fonds, en attente d'un administrateur : suivez-les dans la fiche du projet">${pluriel(P3A.mesDemandes, "demande")} au fonds, en attente</a>` : "");
  zone.hidden = !zone.innerHTML;
}

/* La marque ⚑ d'une collection du bloc « Collections ». */
function marqueRecues(c) {
  const n = (P3A.recues.get(c.id) || []).length;
  if (!n) return "";
  return `<span class="col-marque" title="${pluriel(n, "demande")} de rejoindre à répondre"><span aria-hidden="true">⚑ ${n}</span><span class="sr-only">${pluriel(n, "demande")} de rejoindre à répondre</span></span>`;
}

/* La pastille de l'onglet Albums d'une collection. */
function pastilleOngletAlbums(c) {
  const n = (P3A.recues.get(c.id) || []).length;
  return `<span class="bi-onglet-pastille" data-pastille-albums ${n ? "" : "hidden"}>${n ? `<span aria-hidden="true">${n}</span><span class="sr-only"> (${pluriel(n, "demande")} à répondre)</span>` : ""}</span>`;
}

function majPastilleOnglet() {
  const f = $("#col-fiche");
  const el = f && f.querySelector("[data-pastille-albums]");
  const c = f && collection(f.dataset.id);
  if (el && c) el.outerHTML = pastilleOngletAlbums(c);
}

/* Le bloc ⚑ en tête de l'onglet Albums : chaque demande, qui la fait, pour quelle
   collection d'arrivée, et « Accepter / Refuser ». */
function rendreBlocRecues(c, msg) {
  const zone = $("#bi-recues-zone");
  if (!zone) return;
  const l = P3A.recues.get(c.id) || [];
  if (!l.length) {
    zone.innerHTML = msg ? `<p id="bi-recues-msg" class="col-msg muted small" role="status">${esc(msg)}</p>` : "";
    return;
  }
  zone.innerHTML = `<section id="bi-recues-bloc" class="recues" aria-labelledby="bi-recues-titre">
    <h4 id="bi-recues-titre">⚑ ${pluriel(l.length, "demande")} de rejoindre un album de « ${esc(c.nom)} »</h4>
    <ul class="lf-lignes">${l.map((d) => `<li data-demande="${d.id}">
      <span><b>${esc(d.demandeur_nom || d.demandeur || "Quelqu'un")}</b> demande que
        « ${esc(d.titre || "")} » soit aussi rangé dans « ${esc(d.collection_nom || "")} »
        <span class="muted small">· ${esc(BDSuppression.dateLue(d.date_creation))}</span></span>
      <span class="bi-boutons">
        <button type="button" class="primary small" data-repondre="${d.id}" data-reponse="${BDSuppression.ACCEPTER}"
                title="Ranger aussi dans « ${esc(d.collection_nom || "")} » : le travail est partagé">Accepter</button>
        <button type="button" class="ghost small" data-repondre="${d.id}" data-reponse="${BDSuppression.REFUSER}">Refuser</button>
      </span></li>`).join("")}</ul>
    <p id="bi-recues-msg" class="col-msg muted small" role="status" aria-live="polite">${msg ? esc(msg) : ""}</p>
  </section>`;
}

async function repondreDemande(bouton) {
  const id = Number(bouton.dataset.repondre), reponse = bouton.dataset.reponse;
  const f = $("#col-fiche");
  const c = f ? collection(f.dataset.id) : null;
  const d = c ? (P3A.recues.get(c.id) || []).find((x) => x.id === id) : null;
  bouton.disabled = true;
  try {
    await apiSend("POST", `/api/demandes/${id}/reponse`, { reponse });
  } catch (e) {
    bouton.disabled = false;
    colMsg($("#bi-recues-msg"), e.message, true);
    return;
  }
  const titre = d ? d.titre : "", arrivee = d ? d.collection_nom : "";
  const texte = reponse === BDSuppression.ACCEPTER
    ? `« ${titre} » est aussi rangé dans « ${arrivee} » : le travail est partagé.`
    : `Refusé : « ${titre} » reste où il est. La demande peut être redéposée.`;
  P3A.recues.forEach((l, cid) => {
    const reste = l.filter((x) => x.id !== id);
    if (reste.length) P3A.recues.set(cid, reste); else P3A.recues.delete(cid);
  });
  rendreRappels();
  rendreListeCollections();
  majPastilleOnglet();
  if (c) rendreBlocRecues(c, texte);
  if (reponse === BDSuppression.ACCEPTER) {
    await loadAlbums().catch(() => {});
    if (c && $("#col-fiche")) rendreBlocRecues(c, texte);
  }
}

/* ── Les deux panneaux de la prise ────────────────────────────────────────────────────── */

function rendreZonePrise() {
  const zone = $("#bi-prise-zone");
  if (!zone) return;
  if (P3A.prise) { zone.innerHTML = htmlPrise(); rendreNotices(); return; }
  if (P3A.dansProjet) { zone.innerHTML = htmlDansProjet(); rendreDansProjet(); return; }
  zone.innerHTML = "";
}

/* Ouvrir « + Prendre du fonds… » : en tête du corpus (vers la base) ou depuis l'onglet
   Albums d'une collection (vers elle). Le même bouton le referme. */
function basculerPrise(ou) {
  const depuis = ou === "collection" && $("#col-fiche") ? Number($("#col-fiche").dataset.id) : null;
  if (P3A.prise && P3A.prise.ou === ou) { P3A.prise = null; majBoutonsPrise(); rendreZonePrise(); return; }
  const dests = BDBiblio.destinationsPrise(COLS.toutes, PROJET);
  P3A.dansProjet = null;
  P3A.prise = { ou, depuis, dest: BDBiblio.destinationParDefaut(dests, depuis), q: "", offset: 0,
                total: 0, notices: null, coches: new Set(), reponses: new Map(), motif: "",
                msg: null, erreur: false };
  majBoutonsPrise();
  rendreZonePrise();
  chargerNotices();
  const q = $("#bi-prise-q");
  if (q) q.focus();
}

function majBoutonsPrise() {
  const fonds = $("#bi-prendre-fonds");
  if (fonds) fonds.setAttribute("aria-expanded", String(!!P3A.prise));
  const dp = $("#bi-dans-projet");
  if (dp) dp.setAttribute("aria-expanded", String(!!P3A.dansProjet));
}

function htmlPrise() {
  const pr = P3A.prise;
  const dests = BDBiblio.destinationsPrise(COLS.toutes, PROJET);
  const dest = dests.find((c) => c.id === pr.dest);
  return `<section id="bi-prise" class="bi-prise" aria-labelledby="bi-prise-titre">
    <h4 id="bi-prise-titre" tabindex="-1">Prendre du fonds${dest ? ` pour « ${esc(dest.nom)} »` : ""}</h4>
    <div class="bi-prise-ligne">
      <label class="sr-only" for="bi-prise-q">Chercher au fonds</label>
      <input type="search" id="bi-prise-q" placeholder="Titre, série, auteur…" autocomplete="off"
             value="${esc(pr.q)}">
      <label class="bi-prise-dest muted small">Dans
        <select id="bi-prise-dest">${dests.length ? "" : `<option value="">—</option>`}${dests.map((c) =>
          `<option value="${c.id}" ${c.id === pr.dest ? "selected" : ""}>${esc(c.nom)}${c.base ? " (base)" : ""}</option>`).join("")}</select></label>
    </div>
    <ul id="bi-prise-notices" class="bi-notices" aria-label="Notices du fonds"></ul>
    <div class="bi-pagin">
      <span id="bi-prise-compte" class="muted small"></span>
      <span class="bi-boutons">
        <button type="button" class="ghost small" data-prise-page="-1" aria-label="Page précédente">‹</button>
        <button type="button" class="ghost small" data-prise-page="1" aria-label="Page suivante">›</button>
      </span>
    </div>
    ${B.total ? "" : `<label class="bi-prise-motif">Pourquoi ces documents ? <span class="muted small">(obligatoire : l'administrateur le lira)</span>
      <textarea id="bi-prise-motif" rows="2" required aria-required="true">${esc(pr.motif)}</textarea></label>`}
    <div class="bi-boutons bi-prise-actions">
      <button type="button" class="primary small" id="bi-prise-ok"></button>
      <button type="button" class="ghost small" id="bi-prise-fermer">Fermer</button>
      <span class="muted small">${B.total ? "Chaque document entre tout de suite, en copie vierge."
        : "Une seule demande part à un administrateur ; un document dont vous lisez déjà une copie dans le projet vous est donné sans attendre, en copie vierge."}</span>
    </div>
    <p id="bi-prise-msg" class="col-msg muted small" role="status" aria-live="polite"></p>
  </section>`;
}

async function chargerNotices() {
  const pr = P3A.prise;
  if (!pr) return;
  const q = new URLSearchParams({ q: pr.q, offset: String(pr.offset), limit: String(NOTICES_PAR_PAGE) });
  if (PROJET !== null) q.set("projet_id", String(PROJET));
  let r;
  try { r = await apiGet(`/api/fonds/notices?${q}`); }
  catch (e) {
    if (P3A.prise !== pr) return;
    pr.notices = [];
    pr.total = 0;
    pr.msg = e.message; pr.erreur = true;
    rendreNotices();
    return;
  }
  if (P3A.prise !== pr) return;                     // refermé, ou rouvert entre-temps
  pr.notices = r.notices || [];
  pr.total = r.total || 0;
  rendreNotices();
}

/* La liste seule se redessine : le champ de recherche garde sa saisie et son focus. */
function rendreNotices() {
  const pr = P3A.prise, ul = $("#bi-prise-notices");
  if (!pr || !ul) return;
  if (pr.notices === null) {
    ul.innerHTML = `<li class="muted small">Lecture des notices…</li>`;
  } else {
    ul.innerHTML = pr.notices.length ? pr.notices.map((n) => {
      const rep = pr.reponses.get(n.document_id);
      const id = `bi-notice-${n.document_id}`;
      return `<li data-notice="${n.document_id}">
        <label for="${id}"><input type="checkbox" id="${id}" data-notice-coche="${n.document_id}"
            ${pr.coches.has(n.document_id) ? "checked" : ""}>
          <span><span class="bi-notice-titre">${esc(n.titre || "")}</span>
            <span class="muted small">${[n.serie, n.auteur].filter(Boolean).map((x) => `· ${esc(x)}`).join(" ")}</span></span></label>
        ${n.dans_le_projet ? `<span class="bi-deja" title="Une collection de ce projet l'a déjà ; cocher en prend une seconde copie, vierge — demandée, sauf si vous lisez déjà la première">déjà dans ce projet</span>` : ""}
        ${n.garde_au_fonds ? `<a class="bi-garde" href="/administration?vue=projets&amp;projet=${PROJET}"
            title="Une copie de ce document, avec son travail, a été retirée de sa dernière collection du projet : son responsable peut demander à la rendre, dans la fiche du projet">une copie de ce projet est gardée au fonds — la demander à rendre ↗</a>` : ""}
        ${rep ? `<span class="reponse ${rep.classe}">${esc(rep.texte)}</span>` : ""}
      </li>`;
    }).join("") : `<li class="muted small">Aucune notice ne répond.</li>`;
  }
  const pages = Math.max(1, Math.ceil(pr.total / NOTICES_PAR_PAGE));
  const page = Math.floor(pr.offset / NOTICES_PAR_PAGE);
  $("#bi-prise-compte").textContent = pr.notices === null ? ""
    : `${pluriel(pr.total, "notice")} · page ${page + 1} / ${pages}`;
  const prec = document.querySelector('[data-prise-page="-1"]');
  const suiv = document.querySelector('[data-prise-page="1"]');
  if (prec) prec.disabled = page === 0;
  if (suiv) suiv.disabled = page >= pages - 1;
  const ok = $("#bi-prise-ok");
  const n = pr.coches.size;
  ok.textContent = `${B.total ? "Prendre" : "Demander"} ${n ? pluriel(n, "document") : "la sélection"}`;
  ok.disabled = !n || !pr.dest;
  if (pr.msg !== null) colMsg($("#bi-prise-msg"), pr.msg, pr.erreur);
}

async function envoyerPrise() {
  const pr = P3A.prise, ok = $("#bi-prise-ok");
  if (!pr || !pr.coches.size || !pr.dest || ok.disabled) return;
  const motifEl = $("#bi-prise-motif");
  if (motifEl) pr.motif = motifEl.value;
  const documents = [...pr.coches].map((d) => ({ document_id: d, reponse: "zero" }));
  const corps = { documents };
  if (pr.motif.trim()) corps.motif = pr.motif.trim();
  ok.disabled = true;
  let r;
  try { r = await apiSend("POST", `/api/collections/${pr.dest}/prendre`, corps); }
  catch (e) {
    pr.msg = e.message; pr.erreur = true;
    rendreNotices();
    return;
  }
  const lignes = r.documents || [];
  lignes.forEach((l) => pr.reponses.set(l.document_id, BDBiblio.reponsePrise(l)));
  pr.coches.clear();
  const faits = lignes.filter((l) => l.etat === "fait").length;
  const demandes = lignes.filter((l) => l.etat === "demande").length;
  const refus = lignes.length - faits - demandes;
  const dest = collection(pr.dest);
  const ou = dest ? ` dans « ${dest.nom} »` : "";
  pr.msg = [
    faits ? `Fait : ${pluriel(faits, "document")} ${faits > 1 ? "ont" : "a"} désormais une copie de travail vierge${ou}.` : "",
    demandes ? `${pluriel(demandes, "document")} ${demandes > 1 ? "sont demandés" : "est demandé"} à un administrateur : vous en suivrez la réponse dans la fiche du projet.` : "",
    refus ? `${pluriel(refus, "document")} refusé${refus > 1 ? "s" : ""} : la raison est sur sa ligne.` : "",
  ].filter(Boolean).join(" ");
  pr.erreur = false;
  if (demandes) { pr.motif = ""; chargerMesDemandes(); }
  if (faits) { await loadAlbums().catch(() => {}); chargerNotices(); }
  else rendreNotices();
  const t = $("#bi-prise-titre");
  if (t) t.focus();
}

/* « + Prendre dans le projet… » : les albums du projet que l'on LIT, hors cette collection.
   Deux boutons par ligne (Hugo, 2026-10-17), l'explication en infobulle, la réponse écrite
   sur place. Rejoindre partage le travail — tout de suite si l'on tient toutes ses
   collections, sinon demandé à qui les tient (D4) ; une copie vierge, images seules, est
   toujours immédiate, à son nom. */
function basculerDansProjet() {
  const f = $("#col-fiche");
  if (!f) return;
  const id = Number(f.dataset.id);
  if (P3A.dansProjet) { P3A.dansProjet = null; majBoutonsPrise(); rendreZonePrise(); return; }
  P3A.prise = null;
  P3A.dansProjet = { collection: id, q: "", reponses: new Map(), msg: null, erreur: false };
  majBoutonsPrise();
  rendreZonePrise();
  const q = $("#bi-dp-q");
  if (q) q.focus();
}

function htmlDansProjet() {
  const dp = P3A.dansProjet;
  const c = collection(dp.collection);
  const p = projetCourant();
  return `<section id="bi-dans-projet-panneau" class="bi-prise" aria-labelledby="bi-dp-titre">
    <h4 id="bi-dp-titre" tabindex="-1">Prendre dans ${p ? `« ${esc(p.nom)} »` : "le projet"} pour « ${esc(c ? c.nom : "")} »</h4>
    <div class="bi-prise-ligne">
      <label class="sr-only" for="bi-dp-q">Chercher un album du projet</label>
      <input type="search" id="bi-dp-q" placeholder="Titre, série…" autocomplete="off" value="${esc(dp.q)}">
      <span id="bi-dp-compte" class="muted small"></span>
    </div>
    <ul id="bi-dp-liste" class="lf-lignes bi-dp-liste"></ul>
    <div class="bi-boutons"><button type="button" class="ghost small" id="bi-dp-fermer">Fermer</button></div>
    <p id="bi-dp-msg" class="col-msg muted small" role="status" aria-live="polite"></p>
  </section>`;
}

function rendreDansProjet() {
  const dp = P3A.dansProjet, ul = $("#bi-dp-liste");
  if (!dp || !ul) return;
  const c = collection(dp.collection);
  const dedans = (a) => (a.collections || []).some((x) => x.id === dp.collection);
  const candidats = BDBiblio.filtrerAlbums(state.albums, { texte: dp.q }).filter((a) =>
    (a.collections || []).length && (!dedans(a) || dp.reponses.has(a.id)));
  $("#bi-dp-compte").textContent = `${pluriel(candidats.filter((a) => !dedans(a)).length, "album")} du projet `
    + `que vous lisez, hors « ${c ? c.nom : ""} »`;
  const admin = new Set(COLS.toutes.filter((x) => x.administrable).map((x) => x.id));
  ul.innerHTML = candidats.slice(0, 60).map((a) => {
    const rep = dp.reponses.get(a.id);
    const ou = (a.collections || []).map((x) => `« ${esc(x.nom)} »`).join(", ")
      + (a.partage ? " et une collection que vous ne lisez pas" : "");
    const direct = B.total || (!a.partage && (a.collections || []).every((x) => admin.has(x.id)));
    // Un rejoindre vers CETTE collection attend déjà (`rejoindre_demande`) : le redemander
    // répondrait 409. Une portée totale range directement, ce qui clôt la demande.
    const dejaDemande = !B.total && (a.rejoindre_demande || []).includes(dp.collection);
    const titreRej = direct
      ? "Ranger aussi ici cette copie : vous tenez toutes ses collections, c'est immédiat. Le travail est partagé."
      : "Ranger aussi ici cette copie : qui tient toutes ses collections doit l'accepter. Le travail sera partagé.";
    return `<li data-dp-album="${a.id}"><span><b>${esc(a.titre)}</b> <span class="muted small">· dans ${ou}</span></span>
      <span class="bi-boutons">${rep ? `<span class="reponse ${rep.classe}">${esc(rep.texte)}</span>`
        : `${dejaDemande ? `<span class="reponse demande" title="Rejoindre ce travail depuis cette collection est déjà demandé : la demande attend sa réponse">rejoindre demandé</span>`
          : `<button type="button" class="ghost small" data-dp="rejoindre" data-id="${a.id}" title="${esc(titreRej)}">Rejoindre</button>`}
           <button type="button" class="ghost small" data-dp="zero" data-id="${a.id}"
                   title="Une seconde copie, images seules, sans le travail de l'autre ; à votre nom, tout de suite. Ce qui se corrigera dans l'une n'arrivera pas dans l'autre.">Copie vierge</button>`}</span></li>`;
  }).join("") || `<li class="muted small">Rien à prendre : tout ce que vous lisez du projet est déjà ici.</li>`;
  if (dp.msg !== null) colMsg($("#bi-dp-msg"), dp.msg, dp.erreur);
}

async function prendreDansProjet(bouton) {
  const dp = P3A.dansProjet;
  if (!dp) return;
  const a = state.albums.find((x) => x.id === Number(bouton.dataset.id));
  if (!a) return;
  const reponse = bouton.dataset.dp;
  bouton.disabled = true;
  let r;
  try {
    r = await apiSend("POST", `/api/collections/${dp.collection}/prendre`, {
      documents: [{ document_id: a.document_id, reponse, album_id: a.id }] });
  } catch (e) {
    bouton.disabled = false;
    dp.msg = e.message; dp.erreur = true;
    rendreDansProjet();
    return;
  }
  const l = (r.documents || [])[0] || {};
  dp.reponses.set(a.id, BDBiblio.reponsePrise(l));
  const c = collection(dp.collection);
  dp.erreur = false;
  dp.msg = l.etat === "fait"
    ? (reponse === "zero"
      ? `Fait : « ${a.titre} » a une seconde copie, vierge, dans « ${c ? c.nom : ""} », à votre nom. Ce qui se fera dans l'une n'arrivera pas dans l'autre.`
      : `Fait : « ${a.titre} » est aussi rangé dans « ${c ? c.nom : ""} ». Le travail est partagé.`)
    : l.etat === "demande"
      ? `Demandé à ${BDBiblio.quiRepondra(l.repondra)} : « ${a.titre} » rejoindra « ${c ? c.nom : ""} » si la réponse est oui. Rien ne change d'ici là.`
      : (l.motif || "Refusé.");
  if (l.etat === "fait") await loadAlbums().catch(() => {});
  else rendreDansProjet();
  const t = $("#bi-dp-titre");
  if (t) t.focus();
}

/* ═══════════════════════════════════════════════════════════════════════════
   Ouvrir, revenir — les gestes de la liste
   ═══════════════════════════════════════════════════════════════════════════ */

/* Le focus suit la FICHE quand la liste disparaît (seuil étroit) ou quand on vient d'ailleurs
   que la liste ; au large, un choix dans la liste y laisse le clavier, pour parcourir le
   suivant sans revenir (le motif de « Comptes et groupes »). */
function focaliserFiche(depuisListe) {
  if (depuisListe && !ETROIT.matches) return;
  const t = titreDeFiche();
  if (t) t.focus();
}

// Le titre de la fiche ouverte : là où le focus revient quand son geste a disparu.
function titreDeFiche() { return $("#biblio-fiche h3[tabindex]"); }

function ouvrirCollection(id, onglet, depuisListe) {
  if (state.openId !== null) {
    state.openId = null; state.planches = []; state.checkedPlanches.clear(); B.depuis = null;
  }
  B.ouverte = id;
  B.onglet = onglet || BDBiblio.ONGLET_PAR_LE_NOM;
  B.edition = null;
  B.vueFiche = true;
  colTaireSauf(null);
  rendreListeCollections();
  rendreListeAlbums();
  rendreFiche();
  rendreVue();
  ecrireAdresse(true);
  focaliserFiche(depuisListe);
}

async function ouvrirAlbumDepuis(id, depuisListe) {
  const montree = collectionMontree();
  const album = state.albums.find((a) => a.id === id);
  // Le retour : la collection qu'on regardait, si l'album y est rangé ; sinon la première
  // de ses collections qu'on lit ; sinon la fiche du projet.
  const siennes = album ? (album.collections || []).map((c) => c.id) : [];
  B.depuis = montree !== null && siennes.includes(montree) ? montree
    : (state.openId !== null && B.depuis !== null ? B.depuis : (siennes[0] ?? null));
  B.vueFiche = true;
  colTaireSauf(null);
  await openAlbum(id);
  rendreVue();
  ecrireAdresse(true);
  focaliserFiche(depuisListe);
}

function revenirALaListe() {
  B.vueFiche = false;
  rendreVue();
  const courant = document.querySelector("#albums-body [aria-current], #col-body [aria-current]");
  (courant || $("#albums-filtre")).focus();
}

/* Cocher une collection FILTRE la liste ; la fiche suit ce que le calque montre — la
   collection seule cochée, la comparaison de deux ou plus, le projet. Sous le seuil étroit,
   on reste dans la liste qu'on est en train de filtrer. */
function basculerCalque(id, coche) {
  if (coche) B.calques.add(id); else B.calques.delete(id);
  if (B.calques.size < 2) B.mode = "une";
  B.ouverte = null;
  B.onglet = "albums";
  B.edition = null;
  if (state.openId !== null) {
    state.openId = null; state.planches = []; state.checkedPlanches.clear(); B.depuis = null;
  }
  colTaireSauf(null);
  rendreListeCollections();
  rendreListeAlbums();
  rendreFiche();
  ecrireAdresse(false);
}

function toutLeProjet() {
  B.calques.clear();
  B.mode = "une";
  B.ouverte = null;
  B.edition = null;
  if (state.openId !== null) {
    state.openId = null; state.planches = []; state.checkedPlanches.clear(); B.depuis = null;
  }
  rendreListeCollections();
  rendreListeAlbums();
  rendreFiche();
  ecrireAdresse(true);
}

function choisirMode(mode) {
  if (!BDBiblio.MODES.includes(mode)) return;
  B.mode = mode;
  rendreListeCollections();
  rendreListeAlbums();
  if (ficheCourante().genre === "comparaison") rendreFiche();
}

/* ── Créer une collection : le champ n'apparaît qu'au geste ───────────────────────────── */
function ouvrirCreation(ouvrir) {
  const zone = $("#col-creer-zone");
  zone.hidden = !ouvrir;
  $("#col-creer").setAttribute("aria-expanded", String(ouvrir));
  if (ouvrir) $("#col-nom").focus();
}

async function creerCollection() {
  const ligne = $("#col-creer-msg");
  const nom = $("#col-nom").value.trim();
  if (!nom) { colMsg(ligne, "Donnez un nom à la collection.", true); return; }
  let creee = null;
  if (await colTenter(ligne, async () => {
    // COL-3 — dans le projet COURANT : c'est lui que la liste montre, donc là que l'on
    // s'attend à voir naître ce qu'on crée. Sans projet connu, rien n'est nommé et le
    // serveur range la collection dans le projet de repli, comme avant.
    creee = await apiSend("POST", "/api/collections",
                          PROJET === null ? { nom } : { nom, projet_id: PROJET });
  })) {
    $("#col-nom").value = "";
    ouvrirCreation(false);
    // La collection créée s'ouvre sur « Qui entre » (AUTH-12, étape 3) : le dire au moment
    // où l'on vient de créer, c'est le seul moment où la question se pose.
    //
    // AUTH-12 — « vous en êtes propriétaire » n'est vrai que pour qui n'administre pas
    // l'instance. Un administrateur crée une collection SANS propriétaire (AUTH-3), et le
    // mono-poste aussi : le message lit la réponse du serveur au lieu de le supposer.
    const moi = await identite();
    const proprietaire = !!moi.login && ((creee && creee.acces) || []).some((a) =>
      a.niveau === "proprietaire" && a.genre === "utilisateur" && a.principal === moi.login);
    const lieu = `« Qui entre », dans sa fiche`;
    const texte = proprietaire
      ? `« ${nom} » créée — vous en êtes propriétaire. Pour y faire entrer quelqu'un : ${lieu}.`
      : moi.login
        ? `« ${nom} » créée. Vous l'administrez comme administrateur de l'instance, sans en `
          + `être propriétaire : désignez-lui un propriétaire dans ${lieu}, pour qu'elle ne `
          + `dépende pas de vous.`
        : `« ${nom} » créée. Qui peut y entrer se règle dans ${lieu}.`;
    if (await chargerCollections()) {
      if (creee && collection(creee.id)) ouvrirCollection(creee.id, "qui", true);
      colMsg(ligne, texte);
    }
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
   L'adresse — ce qu'elle ouvre au chargement et au retour arrière
   ═══════════════════════════════════════════════════════════════════════════ */

/* AUTH-12, étape 3 — la Bibliothèque ADRESSABLE, et UX-18 y ajoute l'album et l'onglet.
   `?collection=<id>` ouvre la fiche de cette collection — sur « Qui entre » si l'adresse ne
   nomme pas d'onglet, comme son nom dans la liste —, et donne le focus au titre du panneau ;
   `&groupe=<nom>` y présélectionne ce groupe (plus aucun lien de l'application n'y mène
   depuis UX-16, mais l'adresse reste valide). `?album=<id>` ouvre la fiche de l'album. Une
   collection ou un album qu'on ne lit pas n'ouvre rien, et une ligne le dit — sans dire s'il
   existe : c'est la règle du 404 (AUTH-2). */
async function ouvrirDepuisAdresse(retourArriere) {
  const a = BDBiblio.lireAdresse(location.search);
  if (!retourArriere) await ALBUMS_PRETS;
  if (a.groupe && a.collection !== null && !retourArriere) {
    PRESELECTION = { id: a.collection, groupe: a.groupe };
  }
  if (!retourArriere) {
    if (!(await chargerCollections({ basculerVers: a.collection }))) return;
  }
  colTaireSauf(null);
  B.edition = null;
  B.onglet = a.onglet;
  if (a.album !== null) {
    if (!state.albums.some((x) => x.id === a.album) && !retourArriere) {
      // Un album d'un autre projet que le courant, qu'on LIT : on bascule dans le sien.
      const lus = await apiGet("/api/albums").catch(() => []);
      const vise = lus.find((x) => x.id === a.album && !x.au_fonds);
      const vers = vise ? BDProjet.basculeVers(PROJETS, PROJET, vise.projet_id) : null;
      if (vers !== null) {
        PROJET = vers;
        colDireProjet();
        BDProjet.choisir(PROJET);
        await loadAlbums(false).catch(() => {});
        rendreListeCollections();
      }
    }
    if (state.albums.some((x) => x.id === a.album)) {
      B.ouverte = null;
      B.depuis = a.collection !== null && collection(a.collection) ? a.collection : null;
      B.vueFiche = true;
      await openAlbum(a.album);
      rendreVue();
      if (!retourArriere) focaliserFiche(false);
      return;
    }
    state.openId = null;
    rendreFiche();
    $("#biblio-fiche").prepend(colTrace("L'album demandé n'est pas dans la liste : il ne vous "
      + "est pas ouvert, ou il n'existe pas.", true));
    return;
  }
  if (state.openId !== null) {
    state.openId = null; state.planches = []; state.checkedPlanches.clear(); B.depuis = null;
  }
  if (a.collection === null) {
    B.ouverte = null;
    B.vueFiche = false;
    rendreListeCollections();
    rendreListeAlbums();
    rendreFiche();
    rendreVue();
    return;
  }
  if (!collection(a.collection) || !COLS.projet.some((c) => c.id === a.collection)) {
    PRESELECTION = null;
    B.ouverte = null;
    rendreListeCollections();
    rendreFiche();
    $("#biblio-fiche").prepend(colTrace("La collection demandée n'est pas dans la liste : elle ne "
      + "vous est pas ouverte, ou elle n'existe pas.", true));
    return;
  }
  B.ouverte = a.collection;
  B.vueFiche = true;
  rendreListeCollections();
  rendreListeAlbums();
  rendreFiche();
  rendreVue();
  if (retourArriere) return;
  // Le titre de « Qui entre » quand l'onglet est le sien et que le panneau en a un ; sinon
  // le titre de la fiche — un participant non propriétaire n'a pas de panneau à viser.
  if (B.onglet === "qui" && QUI_ENTRE && QUI_ENTRE.poignee.focaliser()) return;
  focaliserFiche(false);
}

/* Bouton « ← Retour » : ramène à la surface d'origine via le `retour` reçu (page
   interne seulement, cf. lib/nav.js), à défaut history.back() si l'on vient de l'app.
   Masqué s'il n'y a nulle part où revenir. Calqué sur les autres surfaces. */
function setupBack() {
  const back = $("#back-link");
  if (!back) return;
  let target = Nav.safeRetour(new URLSearchParams(location.search).get("retour"));
  if (!target) {
    try {
      const ref = document.referrer ? new URL(document.referrer) : null;
      if (ref && ref.origin === location.origin && ref.pathname !== location.pathname)
        target = "__back__";
    } catch (e) { /* referrer non parsable */ }
  }
  if (!target) return;
  back.hidden = false;
  if (target === "__back__") {
    back.href = "#";
    back.onclick = (e) => { e.preventDefault(); history.back(); };
  } else {
    back.href = target;
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
   Démarrage — un gestionnaire par zone, délégué : la liste et la fiche se redessinent
   ═══════════════════════════════════════════════════════════════════════════ */

function brancherListe() {
  $("#col-creer").onclick = () => ouvrirCreation($("#col-creer-zone").hidden);
  $("#col-add").onclick = creerCollection;
  $("#col-nom").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); creerCollection(); }
    if (e.key === "Escape") { e.preventDefault(); ouvrirCreation(false); $("#col-creer").focus(); }
  });
  $("#collections-bloc").addEventListener("click", (e) => {
    const t = e.target.closest("[data-tri]");
    if (t) {
      if (t.dataset.tri !== B.tri) { B.tri = t.dataset.tri; rendreListeCollections(); }
      return;
    }
    const m = e.target.closest("[data-mode]");
    if (m) { choisirMode(m.dataset.mode); return; }
    if (e.target.closest("#calques-tout")) { toutLeProjet(); return; }
    const o = e.target.closest("[data-ouvrir-col]");
    if (o) ouvrirCollection(Number(o.dataset.ouvrirCol), BDBiblio.ONGLET_PAR_LE_NOM, true);
  });
  $("#collections-bloc").addEventListener("change", (e) => {
    const c = e.target.closest("[data-calque]");
    if (c) basculerCalque(Number(c.dataset.calque), c.checked);
  });
  $("#albums-filtre").addEventListener("input", (e) => {
    B.filtre = e.target.value;
    rendreListeAlbums();
  });
  $("#albums-body").addEventListener("click", (e) => {
    const b = e.target.closest(".album-row[data-id]");
    if (b) ouvrirAlbumDepuis(Number(b.dataset.id), true);
  });
}

function brancherFiche() {
  const fiche = $("#biblio-fiche");
  fiche.addEventListener("click", (e) => {
    const t = e.target;
    if (t.closest("[data-bi-retour]")) { revenirALaListe(); return; }
    const onglet = t.closest('[role="tab"][data-onglet]');
    if (onglet) { choisirOnglet(onglet.dataset.onglet, false); return; }
    // COL-3, tranche 3a — la prise, le rejoindre, les réponses.
    const pf = t.closest("[data-prendre-fonds]");
    if (pf) { basculerPrise(pf.dataset.prendreFonds); return; }
    if (t.closest("#bi-dans-projet")) { basculerDansProjet(); return; }
    if (t.closest("#bi-prise-fermer")) {
      P3A.prise = null; majBoutonsPrise(); rendreZonePrise();
      const b = $("#bi-prendre-fonds"); if (b) b.focus();
      return;
    }
    if (t.closest("#bi-dp-fermer")) {
      P3A.dansProjet = null; majBoutonsPrise(); rendreZonePrise();
      const b = $("#bi-dans-projet"); if (b) b.focus();
      return;
    }
    const page = t.closest("[data-prise-page]");
    if (page && P3A.prise) {
      P3A.prise.offset = Math.max(0, P3A.prise.offset + Number(page.dataset.prisePage) * NOTICES_PAR_PAGE);
      chargerNotices();
      return;
    }
    if (t.closest("#bi-prise-ok")) { envoyerPrise(); return; }
    const dpb = t.closest("button[data-dp]");
    if (dpb) { prendreDansProjet(dpb); return; }
    const rp = t.closest("button[data-repondre]");
    if (rp) { repondreDemande(rp); return; }
    const oc = t.closest("[data-ouvrir-col]");
    if (oc) { ouvrirCollection(Number(oc.dataset.ouvrirCol), "albums", false); return; }
    const oa = t.closest("[data-ouvrir-album]");
    if (oa) { ouvrirAlbumDepuis(Number(oa.dataset.ouvrirAlbum), false); return; }
    if (t.closest("[data-retour-album]")) {
      fermerAlbum();
      ecrireAdresse(true);
      focaliserFiche(false);
      return;
    }
    const mf = t.closest("[data-mode-fiche]");
    if (mf) { choisirMode(mf.dataset.modeFiche); return; }
    const c = $("#col-fiche") ? collection($("#col-fiche").dataset.id) : null;
    const mod = t.closest("[data-modifier]");
    if (mod && c) {
      B.edition = mod.dataset.modifier;
      const p = document.getElementById(`panneau-${B.edition}`);
      if (B.edition === "description") rendreDescription(p, c);
      else rendreDiffusion(p, c);
      const premier = p.querySelector("[data-champ]");
      if (premier) premier.focus();
      return;
    }
    if (t.closest("[data-annuler-edition]") && c) {
      const qui = B.edition;
      B.edition = null;
      const p = document.getElementById(`panneau-${qui}`);
      if (qui === "description") rendreDescription(p, c); else rendreDiffusion(p, c);
      const m = p.querySelector("[data-modifier]");
      if (m) m.focus();
      return;
    }
    const enr = t.closest("[data-enregistrer]");
    if (enr && c) { colEnregistrer(enr.closest('[role="tabpanel"]'), c, enr.dataset.enregistrer); return; }
    if (t.closest("[data-supprimer]") && c) { colSupprimer(c); return; }
    const act = t.closest("[data-act]");
    if (act) {
      const a = state.albums.find((x) => x.id === Number(act.dataset.id));
      if (a && act.dataset.act === "edit") openModal(a);
      if (a && act.dataset.act === "supprimer") ouvrirSuppression(a);
      return;
    }
    if (t.closest("#detail-edit")) {
      const a = state.albums.find((x) => x.id === state.openId);
      if (a) openModal(a);
      return;
    }
    if (t.closest("#detail-validate-all")) { validateAllAlbum(); return; }
    if (t.closest("#bi-importer")) {
      if (t.closest("#bi-importer").getAttribute("aria-disabled") === "true") return;
      const champ = $("#bi-import-fichiers");
      champ.dataset.album = String(state.openId);
      champ.click();
      return;
    }
    if (t.closest("#bi-ranger-nom")) { rangerParNom(); return; }
    const monter = t.closest("button[data-monter]");
    if (monter) { deplacerPlanche(Number(monter.dataset.monter), -1); return; }
    const descendre = t.closest("button[data-descendre]");
    if (descendre) { deplacerPlanche(Number(descendre.dataset.descendre), 1); return; }
    if (t.closest("#bi-import-arreter")) {
      IMPORT.arreter = true;
      const b = $("#bi-import-arreter");
      if (b) { b.disabled = true; b.textContent = "Arrêt…"; }
      return;
    }
    const lancer = t.closest("[data-lancer]");
    if (lancer) { runBatch(lancer.dataset.lancer); return; }
    const vider = t.closest("[data-vider]");
    if (vider) {
      if (vider.dataset.vider === "albums") {
        fiche.querySelectorAll("[data-coche-album]").forEach((x) => {
          state.checkedAlbums.delete(Number(x.dataset.cocheAlbum)); x.checked = false; });
      } else {
        state.checkedPlanches.clear();
        fiche.querySelectorAll("input[data-pid]").forEach((x) => { x.checked = false; });
      }
      rafraichirLot(vider.dataset.vider);
      return;
    }
    const val = t.closest("button[data-val]");
    if (val) { validatePlanche(Number(val.dataset.val), val.dataset.on === "1"); return; }
    const lock = t.closest("button[data-lock]");
    if (lock) { lockPlanche(Number(lock.dataset.lock), lock.dataset.on === "1"); return; }
    const role = t.closest("button[data-role]");
    if (role) { setRole(Number(role.dataset.role), role.dataset.to); return; }
    const delp = t.closest("button[data-delp]");
    if (delp) { deletePlanche(Number(delp.dataset.delp)); return; }
    const refus = t.closest("button[data-delp-refus]");
    if (refus) { direPlancheADemander(refus); return; }
  });
  fiche.addEventListener("change", (e) => {
    const t = e.target;
    if (t.matches("[data-coche-album]")) {
      const id = Number(t.dataset.cocheAlbum);
      if (t.checked) state.checkedAlbums.add(id); else state.checkedAlbums.delete(id);
      rafraichirLot("albums");
      return;
    }
    if (t.matches("input[data-pid]")) {
      const pid = Number(t.dataset.pid);
      if (t.checked) state.checkedPlanches.add(pid); else state.checkedPlanches.delete(pid);
      B.perdues = null;
      rafraichirLot("planches");
      return;
    }
    if (t.matches("[data-passe]")) {
      if (t.checked) state.passes.add(t.dataset.passe); else state.passes.delete(t.dataset.passe);
      const l = fiche.querySelector("[data-lancer]");
      if (l) l.disabled = !state.passes.size;
      return;
    }
    if (t.matches("[data-notice-coche]") && P3A.prise) {
      const d = Number(t.dataset.noticeCoche);
      if (t.checked) P3A.prise.coches.add(d); else P3A.prise.coches.delete(d);
      rendreNotices();
      const el = document.getElementById(`bi-notice-${d}`);
      if (el) el.focus();
      return;
    }
    if (t.matches("#bi-prise-dest") && P3A.prise) {
      P3A.prise.dest = t.value ? Number(t.value) : null;
      const d = collection(P3A.prise.dest);
      $("#bi-prise-titre").textContent = `Prendre du fonds${d ? ` pour « ${d.nom} »` : ""}`;
      rendreNotices();
      return;
    }
    if (t.matches("input[data-ranger]")) {
      if (t.checked) rangerAlbum(t); else sortirAlbum(t);
      return;
    }
    if (t.matches("#rel-filter")) { state.relFilter = t.value; renderDetail(); return; }
    if (t.matches("select[data-rel]")) setRelecture(Number(t.dataset.rel), t.value);
  });
  // La recherche des deux panneaux de la prise : seule la liste se redessine.
  fiche.addEventListener("input", (e) => {
    const t = e.target;
    if (t.matches("#bi-prise-q") && P3A.prise) {
      P3A.prise.q = t.value;
      P3A.prise.offset = 0;
      clearTimeout(P3A.minuterie);
      P3A.minuterie = setTimeout(chargerNotices, 250);
      return;
    }
    if (t.matches("#bi-prise-motif") && P3A.prise) { P3A.prise.motif = t.value; return; }
    if (t.matches("#bi-dp-q") && P3A.dansProjet) { P3A.dansProjet.q = t.value; rendreDansProjet(); }
  });
  // Le motif ARIA des onglets : les flèches passent d'un onglet à l'autre, Début et Fin vont
  // au premier et au dernier.
  fiche.addEventListener("keydown", (e) => {
    const tab = e.target.closest('[role="tab"][data-onglet]');
    if (!tab) return;
    const cles = BDBiblio.CLES_ONGLETS;
    const i = cles.indexOf(tab.dataset.onglet);
    const vers = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: cles.length - 1 }[e.key];
    if (vers === undefined) return;
    e.preventDefault();
    choisirOnglet(cles[(vers + cles.length) % cles.length], true);
  });
}

function setup() {
  setupBack();
  // UX-11 — le champ vit HORS de la fiche, que chaque geste redessine : une sélection en
  // cours ne doit pas perdre son champ. L'album est celui dont la fiche a ouvert le
  // sélecteur.
  $("#bi-import-fichiers").addEventListener("change", (e) => {
    const champ = e.target;
    const fichiers = Array.from(champ.files || []);
    const albumId = Number(champ.dataset.album || state.openId);
    champ.value = "";
    importerPlanches(albumId, fichiers);
  });
  // COL-3, tranche 3a — la base présélectionnée, sauf si l'on vient d'une collection ouverte.
  $("#btn-new").onclick = () => {
    const f = ficheCourante();
    openModal(null, f.genre === "collection" ? f.id : null);
  };
  $("#m-save").onclick = saveAlbum;
  $("#m-cancel").onclick = closeModal;
  $("#m-contrib-add").onclick = addContribution;
  ["#m-contrib-nom", "#m-contrib-role"].forEach((id) =>
    $(id).addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); addContribution(); }
    }));
  $("#album-modal").addEventListener("mousedown", (e) => {
    if (e.target.id === "album-modal") closeModal();
  });
  // Modale accessible : role=dialog, piège à focus, Échap, retour du focus (source unique).
  // `retour` : la fiche redessinée sans le geste d'où l'on venait (l'album parti d'une
  // collection, ou du projet), son titre plutôt que `body`.
  if (window.BDDialog)
    BDDialog.register($("#album-modal"),
      { box: ".modal-box", labelledby: "modal-title", onClose: closeModal,
        retour: titreDeFiche });
  // COL-3, tranche 2 — « Supprimer… », ses deux réponses.
  $("#sp-annuler").onclick = fermerSuppression;
  $("#sp-def").onclick = spDefinitif;
  $("#sp-retrait").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-retirer]");
    if (b) spRetirer(b);
  });
  $("#suppr-modal").addEventListener("mousedown", (e) => {
    if (e.target.id === "suppr-modal") fermerSuppression();
  });
  if (window.BDDialog)
    BDDialog.register($("#suppr-modal"),
      { box: ".modal-box", labelledby: "sp-titre", onClose: fermerSuppression,
        retour: titreDeFiche });
  brancherListe();
  brancherFiche();
  // COL-3, tranche 3a — le compteur des demandes reçues mène à la première collection qui
  // en attend, sur son onglet Albums, où se trouve le bloc ⚑.
  $("#bi-rappels").addEventListener("click", (e) => {
    if (!e.target.closest("#bi-recues-compteur")) return;
    const premiere = COLS.projet.find((c) => P3A.recues.has(c.id));
    if (premiere) ouvrirCollection(premiere.id, "albums", false);
  });
  // COL-3 — on a changé de projet, par le sélecteur de la bande ou dans un autre onglet :
  // la liste est celle du nouveau, et ce qui était ouvert dans l'ancien se referme.
  document.addEventListener(BDProjet.EVENEMENT, async (e) => {
    const id = e.detail ? e.detail.id : null;
    if (id == null || id === PROJET) return;
    PROJET = id;
    colTaireSauf(null);
    P3A.prise = null; P3A.dansProjet = null;
    B.calques.clear(); B.mode = "une"; B.ouverte = null; B.edition = null; B.depuis = null;
    state.openId = null; state.planches = []; state.checkedPlanches.clear();
    state.checkedAlbums.clear();
    B.vueFiche = false;
    rendreVue();
    await chargerCollections();
    await loadAlbums(false).catch(() => {});
    rendreFiche();
    ecrireAdresse(false);
    loadCorpus();
    // Une modale « Nouvel album » restée ouverte propose les collections du projet d'AVANT
    // (un autre onglet vient d'en changer) : sa liste suit.
    if (!$("#album-modal").hidden && !state.editingId) remplirCollections(false, null);
  });
  window.addEventListener("popstate", () => { ouvrirDepuisAdresse(true); });
  ETROIT.addEventListener("change", rendreVue);
  // AUTH-1 — amorcé ici : `parQui()` a besoin du login courant pour dire « par vous ».
  identite().then((m) => { MOI = m; });
  // Les albums, puis l'état ShareDocs AVANT le rendu de la fiche (EXP-1), puis l'adresse.
  ALBUMS_PRETS = loadAlbums(false).catch((e) => toast("Albums : " + e.message, "error"));
  // Stats d'en-tête (bande 2), une fois le projet courant lu : celles d'un bac à sable sont
  // les siennes (COL-4).
  ALBUMS_PRETS.then(loadCorpus);
  // COL-4 — la ligne du bac à sable a lu son état (le compte des planches importées) : la
  // fiche d'un album ouverte éteint ou rallume son import.
  document.addEventListener("bd:bac-a-sable-maj", majImportPlafond);
  loadEtatSharedocs().then(() => ouvrirDepuisAdresse(false));
  pollJobs();     // reprend l'affichage d'un éventuel lot déjà en cours
}

setup();
