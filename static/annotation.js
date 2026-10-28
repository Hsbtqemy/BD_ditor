/* La page ANNOTATION (`/annotation`) — la sixième surface (ANN-7, tranche 2 ; ANN-6, l'écran
   du relevé). Cadrage : `docs/ann7-tranche2-cadrage.md`. Ce script DESSINE ; ce qui se
   décide — le rangement d'une planche en cases, les étiquettes, l'adresse, le Contexte —
   vit dans `static/lib/annotation.js` (`BDAnnotation`), testé sous Node.

   LE JALON 1, commits 1 à 3 : la page, la grille, et la POSE des relevés. On y choisit une
   collection, un album et une planche du PROJET COURANT ; sur la minicarte, une CASE ; dans
   la case agrandie, une zone — une bulle, un cartouche, un texte, une boîte personnage —, ou
   le fond (la case elle-même). Le Contexte se lit (locuteur, personnage, note), sans geste :
   il s'écrit dans l'Atelier, où mène « Ouvrir dans l'Atelier ↗ ». À droite, les grilles
   actives du projet que la collection ne masque pas : leur plan, le filtre, la ligne du
   guide, le guide complet (commit 2). On y désigne des mots, on y pose, change et retire
   des relevés, et ce qui est posé se lit en bas de la colonne (commit 3).

   LA DISPOSITION NE BOUGE PAS PENDANT LE TRAVAIL (Hugo, 2026-10-14) : trois colonnes, une
   boîte de case de hauteur constante, des blocs de hauteur fixe ; l'aide est en infobulle,
   jamais en phrases à l'écran. Changer de case ou de zone redessine des PARTIES — la minicarte,
   la case, le Contexte —, jamais la page.

   LE PROJET COURANT BORNE LA PAGE, comme l'Atelier et la Bibliothèque (`lib/projet.js`) ; la
   liste *Collection* est le filtre de l'Atelier (`lib/atelier.js`), et son choix, retenu
   projet par projet, est le MÊME que celui de l'Atelier (la clé `bd-atelier-collection`) : on
   passe de l'un à l'autre sur la même planche. Un lien vers un album d'un autre projet qu'on
   lit fait basculer (`BDProjet.basculeVers`). L'ADRESSE l'emporte sur la mémoire de session
   (`lib/nav.js`). */
"use strict";

const A = window.BDAnnotation;
const PAGE = "annotation";
const SVGNS = "http://www.w3.org/2000/svg";
// La taille d'ÉCRAN des étiquettes posées sur la case agrandie (ANN-6, v3 : « à ~12 px
// d'écran quelle que soit la case »).
const ETIQUETTE_PX = 12;

const DEPART = Nav.etatDeDepart(location.search, Nav.stockageDeSession(window), PAGE);
// D'où l'on vient (`?retour=`, borné aux chemins internes) : « ← Retour » y ramène, et
// l'adresse le garde à chaque choix, pour qu'il survive au rechargement.
const RETOUR = Nav.safeRetour(new URLSearchParams(DEPART.qs).get("retour"));
const S = {
  projet: null, projets: [],
  collections: [], collection: null, collectionProjet: null,
  albumsProjet: [], albums: [], albumId: null,
  planches: [], planche: null,
  regions: [], rangement: [],
  caseIx: 0, zoneId: null,
  personnages: new Map(),      // région (boîte) → nom du personnage montré, ou null
  lienLu: false,
  // La grille (commit 2)
  grilles: [],                 // les grilles ACTIVES du projet courant
  plans: new Map(),            // « grille:numéro » → plan, lu une fois par version
  grilleId: null, vue: "*",    // la grille ouverte, et « Afficher »
  replis: new Set(),           // « grille:rubrique » repliées
  filtre: "", actif: 0, resultats: [],
  guide: null,                 // { e, v } : l'entrée (et la variante) de la ligne du guide
  releves: [],                 // ceux de la planche, pour « n ici »
  // Désigner et poser (commit 3)
  mots: null,                  // le découpage de la zone (`GET /api/regions/{id}/mots`)
  sel: [], ancre: null, curseur: null,   // les mots désignés
  porte: null,                 // « Porte sur »
  conflit: null,               // le bandeau ouvert (CONC-3, cardinalité)
  designer: null,              // le relevé dont on désigne le lien sur la planche
  login: null, reglage: null,  // « Relevés : ▾ », retenu par personne et par projet
  etats: new Map(),            // entrée → relevés posés sur la cible courante
};
let tourContexte = 0;          // la lecture du Contexte la plus récente gagne
let tourPlanche = 0;           // idem pour une planche

/* ───────────── Le projet, les collections, les albums ───────────── */
async function lireProjetCourant() {
  const projets = await Promise.resolve(window.BDProjets).catch(() => null);
  S.projets = Array.isArray(projets) ? projets : [];
  S.projet = BDProjet.courant(S.projets, S.projet === null ? BDProjet.lire() : S.projet);
}

async function chargerAlbums() {
  const [lus, cols] = await Promise.all([
    apiGet("/api/albums"),
    apiGet("/api/collections").catch(() => []),
  ]);
  await lireProjetCourant();
  const adr = A.lireAdresse(DEPART.qs);
  const premier = !S.lienLu;
  let lien = null, adresse = null;
  if (premier) {
    S.lienLu = true;
    lien = adr.album === null ? null : lus.find((a) => a.id === adr.album && !a.au_fonds) || null;
    if (adr.album !== null && !lien) toast("Album du lien introuvable.", "error");
    adresse = adr.collection;
    const posee = typeof adresse === "number" ? (cols || []).find((c) => c.id === adresse) : null;
    const vise = lien ? lien.projet_id : (posee ? posee.projet_id : null);
    const vers = BDProjet.basculeVers(S.projets, S.projet, vise);
    if (vers !== null) { S.projet = vers; BDProjet.choisir(vers); }
  }
  S.albumsProjet = BDProjet.albumsDuProjet(lus, S.projet);
  S.collections = BDBiblio.trierCollections(BDProjet.duProjet(cols || [], S.projet), "alpha");
  const retenu = S.collectionProjet === S.projet && S.collection !== null
    ? S.collection : BDAtelier.lire(S.projet);
  const voulu = premier ? (lien ? lien.id : null) : S.albumId;
  const { choix, raison } = BDAtelier.resoudre({
    collections: S.collections, albums: S.albumsProjet, adresse, retenu, albumVise: voulu,
  });
  S.collection = choix;
  S.collectionProjet = S.projet;
  if (raison === "adresse" || raison === "album") BDAtelier.retenir(S.projet, choix);
  rendreCollections();
  await chargerGrilles(premier ? adr.grille : undefined);
  await afficherAlbums(voulu, premier ? adr : null);
}

function option(valeur, texte) {
  const o = document.createElement("option");
  o.value = String(valeur);
  o.textContent = texte;
  return o;
}

function rendreCollections() {
  const sel = $("#an-collection");
  sel.replaceChildren(...S.collections.map((c) => option(c.id, c.nom)),
                      option(BDAtelier.TOUTES, BDAtelier.LIBELLE_TOUTES));
  sel.value = String(S.collection);
}

/* La liste *Album* sous la collection choisie, puis l'album qu'elle ouvre. `adr` : ce que
   l'adresse d'arrivée nomme (planche, région), au premier chargement seulement. */
async function afficherAlbums(voulu, adr) {
  S.albums = BDAtelier.filtrer(S.albumsProjet, S.collection);
  const sel = $("#an-album");
  const cible = BDAtelier.albumAOuvrir(S.albums, voulu, S.albumId);
  if (cible === null) {
    sel.replaceChildren(option("", BDAtelier.libelleVide(S.collection)));
    S.albumId = null;
    S.planches = [];
    rendrePlanches();
    await ouvrirPlanche(null);
    return;
  }
  sel.replaceChildren(...S.albums.map((a) => {
    const st = serieTome(a);
    return option(a.id, `${st ? st + " · " : ""}${a.titre}`);
  }));
  sel.value = String(cible);
  // Ce que l'adresse nomme ne vaut que pour SON album : jamais une planche d'un autre.
  await ouvrirAlbum(cible, adr && adr.album === cible ? adr : null);
}

async function ouvrirAlbum(id, adr) {
  S.albumId = id;
  S.planches = await apiGet(`/api/albums/${id}/planches`);
  rendrePlanches();
  const voulue = adr && adr.planche !== null && S.planches.some((p) => p.id === adr.planche)
    ? adr.planche : (S.planches.length ? S.planches[0].id : null);
  if (adr && adr.planche !== null && voulue !== adr.planche) {
    toast("Planche du lien introuvable dans cet album.", "error");
  }
  await ouvrirPlanche(voulue, adr ? adr.region : null);
}

function rendrePlanches() {
  const sel = $("#an-planche-choix");
  if (!S.planches.length) {
    sel.replaceChildren(option("", "— aucune planche —"));
    return;
  }
  sel.replaceChildren(...S.planches.map((p) => option(p.id, A.libellePlanche(p))));
}

/* ───────────── La planche ───────────── */
async function ouvrirPlanche(id, regionVoulue = null) {
  const tour = ++tourPlanche;
  S.planche = id === null ? null : S.planches.find((p) => p.id === id) || null;
  S.regions = [];
  S.releves = [];
  S.personnages = new Map();
  if (S.planche) {
    $("#an-planche-choix").value = String(S.planche.id);
    const [regions, releves] = await Promise.all([
      apiGet(`/api/planches/${S.planche.id}/regions`),
      apiGet(`/api/planches/${S.planche.id}/releves`).then((d) => d.releves).catch(() => []),
    ]);
    if (tour !== tourPlanche) return;
    S.regions = regions;
    S.releves = releves;
  }
  S.rangement = S.planche
    ? A.casesDeLaPlanche(S.regions, S.planche.largeur_px, S.planche.hauteur_px) : [];
  const ou = regionVoulue === null ? null : A.situer(S.rangement, regionVoulue);
  if (regionVoulue !== null && !ou) toast("Région du lien introuvable sur cette planche.", "error");
  S.caseIx = ou ? ou.caseIx : 0;
  S.zoneId = ou ? ou.zoneId : null;
  $("#an-preparee").textContent = S.planche
    ? A.preparation(S.regions, S.planche.relecture_statut) : "";
  rendreMini();
  choisir(S.caseIx, S.zoneId);
}

function caseCourante() { return S.rangement[S.caseIx] || null; }
function zoneCourante() {
  const c = caseCourante();
  if (!c) return null;
  return S.zoneId === null ? c.case : c.zones.find((z) => z.id === S.zoneId) || c.case;
}

/* Choisir une case et, dedans, une zone (null : la case). Redessine ce qui en dépend. */
function choisir(caseIx, zoneId) {
  S.caseIx = caseIx;
  S.zoneId = zoneId;
  S.sel = [];
  S.ancre = null;
  S.curseur = null;
  marquerMini();
  rendreTete();
  rendreCase();
  rendreZones();
  rendreMots();
  rendreContexte();
  rendreGrille();
  lirePersonnagesDeLaCase();
  syncAdresse();
  const z = zoneCourante();
  chargerMots().then(() => {
    if (zoneCourante() === z) { rendreMots(); rendreCorps(); rendreListe(); }
  });
}

/* ───────────── La minicarte : elle ne sert qu'à choisir une CASE ───────────── */
function svg(tag, attrs) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, String(v));
  return e;
}

function imagePlanche() {
  const p = S.planche;
  return svg("image", { href: p.url_web || "", x: 0, y: 0, width: p.largeur_px,
                        height: p.hauteur_px, preserveAspectRatio: "none" });
}

function rendreMini() {
  const boite = $("#an-mini");
  if (!S.planche) {
    boite.replaceChildren();
    $("#an-mini-titre").textContent = "Planche";
    return;
  }
  const p = S.planche;
  const album = S.albums.find((a) => a.id === S.albumId);
  $("#an-mini-titre").textContent = `${album ? album.titre + " · " : ""}${A.libellePlanche(p)}`;
  const racine = svg("svg", { viewBox: `0 0 ${p.largeur_px} ${p.hauteur_px}`,
                              preserveAspectRatio: "xMidYMid meet", class: "an-mini-svg",
                              role: "group", "aria-label": "Cases de la planche" });
  racine.appendChild(imagePlanche());
  S.rangement.forEach((entree, i) => {
    for (const z of entree.zones) {
      racine.appendChild(svg("rect", { class: `an-mz-enfant t-${z.type}`, x: z.x, y: z.y,
                                        width: z.w, height: z.h, "aria-hidden": "true",
                                        "data-region": z.id }));
    }
    if (entree.case.pseudo) return;
    const nom = "Case " + A.etiquette(entree.case);
    const r = svg("rect", { class: "an-mz", x: entree.case.x, y: entree.case.y,
                            width: entree.case.w, height: entree.case.h, tabindex: 0,
                            role: "button", "aria-label": nom, "data-case": i });
    const t = svg("title", {});
    t.textContent = nom;
    r.appendChild(t);
    racine.appendChild(r);
  });
  boite.replaceChildren(racine);
}

function marquerMini() {
  for (const r of document.querySelectorAll("#an-mini .an-mz")) {
    const courante = Number(r.dataset.case) === S.caseIx;
    r.classList.toggle("courante", courante);
    r.setAttribute("aria-pressed", String(courante));
  }
}

/* ───────────── La case agrandie ───────────── */
function rendreTete() {
  const c = caseCourante();
  const z = zoneCourante();
  const nCases = S.rangement.filter((e) => !e.case.pseudo).length;
  $("#an-tete-case").textContent = c
    ? (c.case.pseudo ? "Hors des cases" : "Case " + A.etiquette(c.case)) : "—";
  $("#an-tete-zone").textContent = z && z !== c.case
    ? `${A.nomType(z.type)} ${A.etiquettesDeLaCase(c).get(z.id)}` : "";
  $("#an-tete-rang").textContent = c && !c.case.pseudo && nCases
    ? `${S.caseIx + 1} / ${nCases}` : "";
}

/* Dessine la case courante dans sa boîte : le dérivé de la planche entière, cadré par la
   `viewBox` sur le rectangle de la case — l'image se recadre d'elle-même, sans requête
   (le dérivé est déjà en cache pour la minicarte). Un clic sur une zone la choisit ; un clic
   sur le fond choisit la case. Les zones ne sont pas focalisables ici : leur chemin au
   clavier est la rangée « Zones de la case », juste en dessous. */
function rendreCase() {
  const boite = $("#an-vue-case");
  const c = caseCourante();
  if (!S.planche || !c) { boite.replaceChildren(); return; }
  const rect = c.case;
  const etiq = A.etiquettesDeLaCase(c);
  // La case, cadrée à la taille qu'elle prend dans la boîte (`meet`), le dérivé en FOND :
  // cf. `BDAnnotation.recadrage`. Le calque des zones a la `viewBox` de la case.
  const st = getComputedStyle(boite);
  const largeur = boite.clientWidth - parseFloat(st.paddingLeft) - parseFloat(st.paddingRight);
  const hauteur = boite.clientHeight - parseFloat(st.paddingTop) - parseFloat(st.paddingBottom);
  const k = A.echelle(rect, largeur, hauteur);
  const cadre = document.createElement("div");
  cadre.className = "an-crop";
  const fond = A.recadrage(rect, S.planche.largeur_px, S.planche.hauteur_px);
  if (k > 0) {
    cadre.style.width = `${rect.w * k}px`;
    cadre.style.height = `${rect.h * k}px`;
  }
  if (fond && S.planche.url_web) {
    cadre.style.backgroundImage = `url("${encodeURI(S.planche.url_web)}")`;
    cadre.style.backgroundSize = `${fond.taille[0]}% ${fond.taille[1]}%`;
    cadre.style.backgroundPosition = `${fond.position[0]}% ${fond.position[1]}%`;
  }
  const racine = svg("svg", { viewBox: `${rect.x} ${rect.y} ${rect.w} ${rect.h}`,
                              preserveAspectRatio: "none", class: "an-case-svg",
                              role: "img",
                              "aria-label": c.case.pseudo ? "La planche"
                                : "Case " + A.etiquette(c.case) });
  racine.appendChild(svg("rect", { class: "an-fond" + (S.zoneId === null ? " choisi" : ""),
                                   x: rect.x, y: rect.y, width: rect.w, height: rect.h,
                                   "data-zone": "" }));
  const taille = A.taillePourEcran(ETIQUETTE_PX, k);
  for (const zone of c.zones) {
    const borne = A.dansLaCase(zone, rect);
    if (!borne) continue;
    const z = { ...zone, ...borne };
    racine.appendChild(svg("rect", {
      class: `an-vz t-${z.type}${z.id === S.zoneId ? " choisi" : ""}`, x: z.x, y: z.y,
      width: z.w, height: z.h, "data-zone": z.id }));
    if (taille === null) continue;
    const nom = z.type === "personnage" && S.personnages.get(z.id)
      ? S.personnages.get(z.id) : etiq.get(z.id);
    const t = svg("text", { class: "an-vz-lbl", x: z.x + taille * 0.4, y: z.y + taille * 1.1,
                            "font-size": taille.toFixed(2),
                            "stroke-width": (taille / 7).toFixed(2), "aria-hidden": "true" });
    t.textContent = nom;
    racine.appendChild(t);
  }
  cadre.appendChild(racine);
  boite.replaceChildren(cadre);
}

/* Les boîtes personnage de la case COURANTE disent leur personnage sur l'image : une requête
   par boîte (2 à 6 par case), gardée pour la planche. */
async function lirePersonnagesDeLaCase() {
  const c = caseCourante();
  if (!c) return;
  const tour = tourPlanche;
  const boites = c.zones.filter((z) => z.type === "personnage" && !S.personnages.has(z.id));
  if (!boites.length) return;
  const lus = await Promise.all(boites.map((z) =>
    apiGet(`/api/regions/${z.id}/personnage`).then((d) => d.personnage)
      .catch(() => null)));
  if (tour !== tourPlanche) return;
  boites.forEach((z, i) => S.personnages.set(z.id, lus[i] ? lus[i].nom : null));
  if (caseCourante() === c) rendreCase();
}

/* La rangée des zones de la case : la case elle-même, puis chacune de ses zones. Le chemin
   au clavier vers une zone, et sa liste lisible. */
function rendreZones() {
  const rangee = $("#an-zones");
  const c = caseCourante();
  if (!c) { rangee.replaceChildren(); return; }
  const etiq = A.etiquettesDeLaCase(c);
  const bouton = (zoneId, texte, titre) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ghost small an-zone-btn";
    b.dataset.zone = zoneId === null ? "" : String(zoneId);
    b.setAttribute("aria-pressed", String(zoneId === S.zoneId));
    b.textContent = texte;
    if (titre) b.title = titre;
    return b;
  };
  rangee.replaceChildren(
    bouton(null, c.case.pseudo ? "La planche" : "La case " + A.etiquette(c.case)),
    ...c.zones.map((z) => bouton(z.id, `${etiq.get(z.id)} · ${A.nomType(z.type)}`,
                                 A.estTexte(z.type) ? z.ocr_texte || "" : "")));
}

/* ───────────── Le Contexte, en lecture ───────────── */
async function rendreContexte() {
  const tour = ++tourContexte;
  const z = zoneCourante();
  const dessiner = (donnees) => {
    if (tour !== tourContexte) return;
    const dl = $("#an-ctx-corps");
    const lignes = A.contexte(z, donnees);
    dl.replaceChildren(...lignes.flatMap((l) => {
      const dt = document.createElement("dt");
      dt.textContent = l.libelle;
      const dd = document.createElement("dd");
      dd.textContent = l.valeur;
      dd.dataset.ctx = l.cle;
      if (l.valeur === "—" || l.valeur === "…") dd.classList.add("muted");
      return [dt, dd];
    }));
  };
  dessiner({});
  if (!z || z.pseudo) return;
  const lire = (chemin, cle) => apiGet(chemin).then((d) => d[cle]).catch(() => null);
  const [locuteur, personnage, note] = await Promise.all([
    A.estTexte(z.type) ? lire(`/api/regions/${z.id}/locuteur`, "locuteur") : null,
    z.type === "personnage" ? lire(`/api/regions/${z.id}/personnage`, "personnage") : null,
    lire(`/api/regions/${z.id}/annotation`, "note"),
  ]);
  dessiner({ locuteur, personnage, note });
}

/* ───────────── La grille, en lecture (commit 2) ─────────────
   Les onglets des grilles ACTIVES du projet que la collection choisie ne masque pas, le
   plan de la grille ouverte (ses rubriques repliables, « n ici », ses trois formes), le
   filtre, la ligne du guide à hauteur fixe et le guide complet. Rien ne se pose encore
   (commit 3) : une entrée qu'on survole, qu'on parcourt ou qu'on touche dit sa ligne du
   guide. La règle — l'arbre, les comptes, le filtre, le guide — est dans `BDAnnotation`. */
function el(tag, attrs, ...enfants) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "texte") e.textContent = v;
    else if (k === "classe") e.className = v;
    else e.setAttribute(k, v === true ? "" : String(v));
  }
  for (const x of enfants) if (x !== null && x !== undefined) e.append(x);
  return e;
}

function planDe(grille) {
  return grille && grille.version
    ? S.plans.get(`${grille.id}:${grille.version.numero}`) || null : null;
}

function grilleOuverte() {
  return S.grilles.find((g) => g.id === S.grilleId) || null;
}

/* Les grilles actives du projet courant, et le plan de chacune (lu une fois par version,
   gardé pour la page). Une liste illisible n'empêche rien : la colonne reste vide. */
async function chargerGrilles(voulue) {
  S.grilles = [];
  if (S.projet !== null) {
    const d = await apiGet(`/api/projets/${S.projet}/grilles`).catch(() => null);
    S.grilles = d && Array.isArray(d.actives) ? d.actives : [];
  }
  await Promise.all(S.grilles.map(async (g) => {
    const cle = `${g.id}:${g.version.numero}`;
    if (S.plans.has(cle)) return;
    const plan = await apiGet(`/api/grilles/${g.id}/versions/${g.version.numero}`)
      .catch(() => null);
    if (plan) S.plans.set(cle, plan);
  }));
  const moi = await Promise.resolve(window.BDMoi).catch(() => null);
  S.login = moi && moi.utilisateur ? moi.utilisateur : null;
  S.reglage = A.lireReglage(stockageLocal(), S.login, S.projet);
  const visibles = A.grillesVisibles(S.grilles, S.collection);
  const avant = S.grilleId;
  S.grilleId = A.grilleAOuvrir(visibles, voulue !== undefined && voulue !== null ? voulue : avant);
  if (S.grilleId !== avant) { S.vue = "*"; S.guide = null; }
}

/* Les relevés de la zone choisie et de son contexte, pour « n ici ». */
function relevesIci() {
  const c = caseCourante();
  const z = zoneCourante();
  const { ici, contexte } = A.relevesDeLaZone(S.releves, z, c ? c.case : null,
                                              S.planche ? S.planche.id : null);
  return [...ici, ...contexte];
}

/* L'infobulle de la liste *Collection* dit combien de grilles du projet elle masque. */
function marquerCollection() {
  const n = S.grilles.filter((g) => A.masquee(g, S.collection)).length;
  const sel = $("#an-collection");
  if (n) {
    sel.title = `Cette collection masque ${n} grille${n > 1 ? "s" : ""} du projet. ` +
      "Leurs relevés restent visibles, en lecture.";
  } else sel.removeAttribute("title");
}

function rendreGrille() {
  marquerCollection();
  rendreOnglets();
  rendreAfficher();
  rendrePorte();
  rendreCorps();
  rendreListe();
  rendreGuide();
}

function rendreOnglets() {
  const liste = $("#an-onglets");
  const ici = relevesIci();
  const visibles = A.grillesVisibles(S.grilles, S.collection);
  liste.replaceChildren(...visibles.map((g) => {
    const n = A.compter(ici, g.id, null).total;
    const choisi = g.id === S.grilleId;
    return el("button", { type: "button", classe: "ghost an-onglet", role: "tab",
                          id: `an-onglet-${g.id}`, "data-grille": g.id,
                          "aria-selected": String(choisi), "aria-controls": "an-grille-corps",
                          tabindex: choisi ? "0" : "-1",
                          title: A.infobulleGrille(g, planDe(g)) },
              g.nom, n ? el("span", { classe: "an-n", texte: ` (${n})` }) : null);
  }));
  const corps = $("#an-grille-corps");
  if (S.grilleId !== null) corps.setAttribute("aria-labelledby", `an-onglet-${S.grilleId}`);
  else corps.setAttribute("aria-labelledby", "an-grille-titre");
}

function rendreAfficher() {
  const sel = $("#an-afficher");
  const vues = A.vuesAfficher(planDe(grilleOuverte()));
  if (S.vue !== "*" && !vues.some((v) => v.cle === S.vue)) S.vue = "*";
  sel.replaceChildren(option("*", "Toute la grille"),
                      ...vues.map((v) => option(v.cle, v.libelle)));
  sel.value = S.vue;
  sel.disabled = !vues.length;
}

function rendreCorps() {
  const g = grilleOuverte();
  const plan = planDe(g);
  const filtre = S.filtre.trim();
  const res = $("#an-resultats");
  const ailleurs = $("#an-ailleurs");
  const arbre = $("#an-plan");
  const champ = $("#an-filtre");
  champ.placeholder = g && g.ouverte ? "Chercher dans la grille ouverte…"
    : "Chercher dans la grille…";
  if (!plan) {
    arbre.replaceChildren(el("p", { classe: "muted", texte: "—" }));
    res.hidden = true;
    arbre.hidden = false;
    ailleurs.replaceChildren();
    champ.removeAttribute("aria-activedescendant");
    return;
  }
  if (filtre) {
    rendreResultats(plan, filtre);
    res.hidden = false;
    arbre.hidden = true;
    return;
  }
  res.hidden = true;
  res.replaceChildren();
  ailleurs.replaceChildren();
  champ.removeAttribute("aria-activedescendant");
  arbre.hidden = false;
  const n = A.compter(relevesIci(), g.id, plan);
  const ctx = contexteDePose();
  S.etats = new Map(plan.entrees.map((e) => [e.cle,
    A.relevesSurLaCible(S.releves, g.id, e.cle, A.cibleDePose(e, ctx))]));
  const tete = A.arbre(plan).filter((r) => S.vue === "*" || r.cle === S.vue);
  arbre.replaceChildren(...tete.map((r) => rubrique(g, plan, r, n, 3)));
}

function rubrique(g, plan, noeud, n, niveau) {
  const cle = `${g.id}:${noeud.cle}`;
  const ouvert = !S.replis.has(cle);
  const compte = n.parRubrique.get(noeud.cle) || 0;
  const titre = el(`h${Math.min(niveau, 6)}`, { classe: "an-rub-titre" },
    el("button", { type: "button", classe: "an-rub-btn", "data-rub": noeud.cle,
                   "aria-expanded": String(ouvert) },
       el("span", { classe: "an-caret", "aria-hidden": "true", texte: "▾" }),
       el("span", { classe: "an-rub-lib", texte: noeud.libelle }),
       el("span", { classe: "an-cnt", texte: compte ? `${compte} ici` : "" })));
  const sec = el("section", { classe: `an-rub an-niv-${Math.min(noeud.profondeur || 0, 3)}` },
                 titre);
  if (!ouvert) return sec;
  for (const e of noeud.entrees) sec.append(entree(e, plan, n));
  for (const x of noeud.enfants) sec.append(rubrique(g, plan, x, n, niveau + 1));
  return sec;
}

function marques(e, n) {
  const cible = A.marqueCible(e);
  const compte = n.parEntree.get(e.cle) || 0;
  return [
    cible ? el("span", { classe: "an-marque", texte: cible,
                         title: "Se pose sur elle d'elle-même, quel que soit « Porte sur »" })
      : null,
    A.marquePlusieurs(e) ? el("span", { classe: "an-marque",
                                        texte: "plusieurs",
                                        title: "Plusieurs fois sur la même cible" }) : null,
    el("span", { classe: "an-cnt", texte: compte ? String(compte) : "" }),
  ];
}

function entree(e, plan, n) {
  const guide = S.guide && S.guide.e === e.cle && !S.guide.v;
  const poses = S.etats.get(e.cle) || [];
  const r0 = poses[0] || null;
  const lecture = ecrivable() ? null : "true";
  if (e.forme === "variantes") {
    const tete = el("button", { type: "button", classe: `an-ent-btn an-ent-tete${guide ? " guide" : ""}`,
                                "data-guide-e": e.cle, id: `an-ent-${e.cle}` },
                    el("span", { classe: "an-ent-lib", texte: e.libelle }),
                    el("span", { classe: "muted small", texte: "une parmi" }), ...marques(e, n));
    const vars = el("div", { classe: "an-vars" }, ...(e.variantes || []).map((v) =>
      el("button", { type: "button",
                     classe: `ghost an-var${S.guide && S.guide.e === e.cle && S.guide.v === v.cle ? " guide" : ""}`,
                     "data-guide-e": e.cle, "data-guide-v": v.cle, "data-pose": "1",
                     "aria-pressed": String(!!r0 && r0.variante_cle === v.cle),
                     "aria-disabled": lecture, texte: v.libelle })));
    return el("div", { classe: "an-ent", role: "group", "aria-labelledby": `an-ent-${e.cle}` },
              tete, vars);
  }
  const liste = e.forme === "qualificatifs"
    ? (plan.listes || []).find((l) => l.cle === e.liste_cle) : null;
  const boite = el("span", { classe: "an-box", "aria-hidden": "true",
                             texte: poses.length > 1 ? String(poses.length) : poses.length ? "✓" : "" });
  const bloc = el("div", { classe: "an-ent" },
    el("button", { type: "button", classe: `an-ent-btn${guide ? " guide" : ""}`,
                   "data-guide-e": e.cle, "data-pose": "1", role: "checkbox",
                   "aria-checked": String(poses.length > 0), "aria-disabled": lecture,
                   id: `an-ent-${e.cle}` },
       boite,
       el("span", { classe: "an-ent-lib", texte: e.libelle }),
       liste ? el("span", { classe: "muted small",
                            texte: `+ ${liste.libelle || liste.cle}` }) : null,
       e.lien ? el("span", { classe: "muted small", texte: "↔ une autre zone" }) : null,
       ...marques(e, n)));
  if (liste) {
    bloc.append(el("div", { classe: "an-vars an-quals", role: "group",
                            "aria-label": `${liste.libelle || liste.cle} pour ${e.libelle}` },
      ...liste.qualificatifs.map((q) => el("button", {
        type: "button", classe: "ghost an-var", "data-guide-e": e.cle, "data-qualif": q.cle,
        "data-pose": "1", "aria-disabled": lecture, title: q.definition || null,
        "aria-pressed": String(!!r0 && (r0.qualificatifs || []).includes(q.cle)),
        texte: q.libelle }))));
  }
  return bloc;
}

/* Les résultats du filtre : une liste d'options que le champ désigne
   (`aria-activedescendant`) ; « Aussi dans » les autres grilles visibles. */
function rendreResultats(plan, filtre) {
  const res = $("#an-resultats");
  const champ = $("#an-filtre");
  const trouves = A.chercher(plan, filtre);
  const aCreer = ecrivable() ? A.creerDansLeFiltre(grilleOuverte(), filtre, trouves) : null;
  if (aCreer) trouves.push({ creer: aCreer, libelle: `Créer « ${aCreer} »`,
                             chemin: `dans ${grilleOuverte().nom}`, exemple: null });
  S.resultats = trouves;
  if (S.actif >= trouves.length) S.actif = 0;
  if (!trouves.length) {
    res.replaceChildren(el("li", { role: "option", "aria-disabled": "true",
                                   "aria-selected": "false", id: "an-res-vide",
                                   classe: "an-res-vide muted",
                                   texte: `Rien pour « ${filtre} »` }));
    champ.removeAttribute("aria-activedescendant");
  } else {
    res.replaceChildren(...trouves.map((r, i) => el("li", {
      role: "option", id: `an-res-${i}`, "data-res": i, "aria-selected": String(i === S.actif),
      classe: `an-res${i === S.actif ? " actif" : ""}${r.creer ? " an-res-creer" : ""}` },
      el("span", { classe: "an-res-chemin", texte: r.chemin }),
      el("span", { classe: "an-res-lib", texte: r.libelle }),
      r.exemple ? el("span", { classe: "an-res-ex", texte: r.exemple }) : null)));
    champ.setAttribute("aria-activedescendant", `an-res-${S.actif}`);
  }
  const autres = A.grillesVisibles(S.grilles, S.collection)
    .filter((x) => x.id !== S.grilleId)
    .map((x) => ({ x, n: A.chercher(planDe(x), filtre).length })).filter((o) => o.n);
  const ailleurs = $("#an-ailleurs");
  ailleurs.replaceChildren(...(autres.length ? [
    el("span", { classe: "muted small", texte: "Aussi dans : " }),
    ...autres.map((o) => el("button", { type: "button", classe: "ghost small an-ailleurs-btn",
                                        "data-grille": o.x.id, texte: `${o.x.nom} (${o.n})` })),
  ] : []));
}

/* LA LIGNE DU GUIDE, à hauteur fixe : ce qu'on relève, la structure, les exemples, la
   liste de qualificatifs, le piège — de l'entrée qu'on survole, parcourt ou touche. */
function rendreGuide() {
  const boite = $("#an-guide-contenu");
  boite.classList.toggle("an-conflit", !!S.conflit);
  if (S.conflit) { boite.replaceChildren(...bandeau()); return; }
  const plan = planDe(grilleOuverte());
  const l = plan && S.guide ? A.ligneDuGuide(plan, S.guide.e, S.guide.v) : null;
  if (!l) { boite.replaceChildren(); return; }
  // `replaceChildren` écrirait « null » pour une partie absente : on ne passe que les autres.
  boite.replaceChildren(...[
    el("div", { classe: "an-g-tete" },
       el("span", { classe: "an-g-lib", texte: l.libelle }),
       l.chemin ? el("span", { classe: "an-g-chemin", texte: l.chemin }) : null),
    l.definition ? el("p", { texte: l.definition }) : null,
    l.structure ? el("p", { texte: `Structure : ${l.structure}` }) : null,
    l.exemples.length ? el("p", {}, "Exemples : ",
                           el("span", { classe: "an-g-ex", texte: l.exemples.join(" · ") }))
      : null,
    l.qualificatifs ? el("p", { classe: "muted small",
                                texte: `${l.qualificatifs.libelle} : ${l.qualificatifs.termes.join(", ")}` })
      : null,
    l.piege ? el("p", { classe: "an-g-piege", texte: l.piege }) : null].filter(Boolean));
}

function montrerGuide(e, v) {
  if (S.guide && S.guide.e === e && (S.guide.v || null) === (v || null)) return;
  S.guide = { e, v: v || null };
  if (S.conflit) return;                 // le bandeau garde la place
  rendreGuide();
  for (const b of document.querySelectorAll("#an-plan [data-guide-e]")) {
    b.classList.toggle("guide", b.dataset.guideE === e
      && (b.dataset.guideV || null) === (v || null));
  }
}

/* LE GUIDE COMPLET, produit depuis la grille, dans une modale (`BDDialog`). */
function ouvrirGuideComplet() {
  const g = grilleOuverte();
  const plan = planDe(g);
  if (!plan) return;
  const v = g.version || {};
  $("#an-guide-titre").textContent = `Guide — ${g.nom}`
    + (v.numero && !g.ouverte ? ` (version ${v.numero})` : "");
  const gc = A.guideComplet(plan);
  const corps = $("#an-guide-corps");
  const blocs = [];
  if (plan.note) blocs.push(el("p", { classe: "muted small", texte: plan.note }));
  for (const s of gc.sections) {
    blocs.push(el(`h${Math.min(4 + s.niveau, 6)}`, { classe: "an-gc-titre", texte: s.titre }));
    if (!s.lignes.length) continue;
    const tbody = el("tbody", {}, ...s.lignes.map((l) => el("tr", {},
      el("td", {}, el("b", { texte: l.phenomene }), l.definition ? ` — ${l.definition}` : ""),
      el("td", {}, ...l.aPoser.flatMap((x, i) => [i ? el("br") : null, el("code", { texte: x.libelle }),
                                                   x.structure ? ` ${x.structure}` : null])),
      el("td", {}, el("i", { texte: l.exemples.join(" / ") })))));
    blocs.push(el("div", { classe: "an-gc-table" },
      el("table", {}, el("thead", {}, el("tr", {}, el("th", { scope: "col", texte: "Phénomène" }),
                                         el("th", { scope: "col", texte: "À poser" }),
                                         el("th", { scope: "col", texte: "Exemples" }))), tbody)));
  }
  for (const liste of gc.listes) {
    blocs.push(el("h4", { classe: "an-gc-titre", texte: liste.libelle }));
    blocs.push(el("ul", {}, ...liste.termes.map((t) => el("li", {}, el("code", { texte: t.libelle }),
                                                          t.definition ? ` — ${t.definition}` : ""))));
  }
  if (gc.pieges.length) {
    blocs.push(el("h4", { classe: "an-gc-titre", texte: "Pièges" }));
    blocs.push(el("ul", {}, ...gc.pieges.map((p) => el("li", {}, el("b", { texte: p.entree }),
                                                       ` — ${p.piege}`))));
  }
  corps.replaceChildren(...blocs);
  $("#an-guide-modal").hidden = false;
}

function fermerGuideComplet() { $("#an-guide-modal").hidden = true; }

function poserResultat(r) {
  if (!r) return;
  if (r.creer) { creer(r.creer); return; }
  montrerGuide(r.entree_cle, r.variante_cle);
  poser(r.entree_cle, { variante: r.variante_cle, qualificatif: r.qualificatif_cle });
}

function choisirGrille(id) {
  if (id === S.grilleId) return;
  S.grilleId = id;
  S.vue = "*";
  S.guide = null;
  S.actif = 0;
  rendreGrille();
  syncAdresse();
}

function brancherGrille() {
  const onglets = $("#an-onglets");
  onglets.addEventListener("click", (e) => {
    const b = e.target.closest("[data-grille]");
    if (b) choisirGrille(Number(b.dataset.grille));
  });
  onglets.addEventListener("keydown", (e) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
    const tous = [...onglets.querySelectorAll("[role=tab]")];
    const i = tous.indexOf(document.activeElement);
    if (i < 0 || !tous.length) return;
    e.preventDefault();
    const j = e.key === "Home" ? 0 : e.key === "End" ? tous.length - 1
      : (i + (e.key === "ArrowRight" ? 1 : -1) + tous.length) % tous.length;
    choisirGrille(Number(tous[j].dataset.grille));
    const cible = $(`#an-onglet-${tous[j].dataset.grille}`);
    if (cible) cible.focus();
  });
  $("#an-afficher").addEventListener("change", (e) => {
    S.vue = e.target.value || "*";
    rendreCorps();
  });
  const plan = $("#an-plan");
  plan.addEventListener("click", (e) => {
    const rub = e.target.closest("[data-rub]");
    if (rub) {
      const cle = `${S.grilleId}:${rub.dataset.rub}`;
      if (S.replis.has(cle)) S.replis.delete(cle); else S.replis.add(cle);
      rendreCorps();
      const remis = [...document.querySelectorAll("#an-plan [data-rub]")]
        .find((b) => b.dataset.rub === rub.dataset.rub);
      if (remis) remis.focus();
      return;
    }
    const b = e.target.closest("[data-guide-e]");
    if (!b) return;
    montrerGuide(b.dataset.guideE, b.dataset.guideV);
    if (b.dataset.pose && b.getAttribute("aria-disabled") !== "true") {
      poser(b.dataset.guideE, { variante: b.dataset.guideV, qualificatif: b.dataset.qualif });
    }
  });
  for (const type of ["mouseover", "focusin"]) {
    plan.addEventListener(type, (e) => {
      const b = e.target.closest("[data-guide-e]");
      if (b) montrerGuide(b.dataset.guideE, b.dataset.guideV);
    });
  }
  const champ = $("#an-filtre");
  champ.addEventListener("input", () => {
    S.filtre = champ.value;
    S.actif = 0;
    rendreCorps();
  });
  champ.addEventListener("keydown", (e) => {
    const n = (S.resultats || []).length;
    if (e.key === "Escape") {
      if (!champ.value) return;
      e.preventDefault();
      champ.value = "";
      S.filtre = "";
      rendreCorps();
    } else if ((e.key === "ArrowDown" || e.key === "ArrowUp") && S.filtre.trim() && n) {
      e.preventDefault();
      S.actif = (S.actif + (e.key === "ArrowDown" ? 1 : -1) + n) % n;
      rendreCorps();
      const actif = $(`#an-res-${S.actif}`);
      if (actif) actif.scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter" && S.filtre.trim() && n) {
      // Entrée POSE le résultat désigné (ou le retire s'il est déjà posé là).
      e.preventDefault();
      poserResultat(S.resultats[S.actif]);
    }
  });
  $("#an-resultats").addEventListener("click", (e) => {
    const li = e.target.closest("[data-res]");
    if (!li) return;
    S.actif = Number(li.dataset.res);
    rendreCorps();
    poserResultat(S.resultats[S.actif]);
  });
  $("#an-ailleurs").addEventListener("click", (e) => {
    const b = e.target.closest("[data-grille]");
    if (b) choisirGrille(Number(b.dataset.grille));
  });
  // « / » cherche dans la grille, hors d'un champ de saisie.
  document.addEventListener("keydown", (e) => {
    if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    if (t && (t.closest("input, textarea, select, [contenteditable]") || t.isContentEditable)) return;
    if (!$("#an-guide-modal").hidden) return;
    e.preventDefault();
    champ.focus();
    champ.select();
  });
  $("#an-guide-complet").addEventListener("click", ouvrirGuideComplet);
  $("#an-guide-fermer").addEventListener("click", fermerGuideComplet);
  const modale = $("#an-guide-modal");
  modale.addEventListener("mousedown", (e) => {
    if (e.target.id === "an-guide-modal") fermerGuideComplet();
  });
  if (window.BDDialog) {
    BDDialog.register(modale, { box: ".modal-box", labelledby: "an-guide-titre",
                                onClose: fermerGuideComplet });
  }
}

/* ───────────── Désigner et poser (commit 3) ─────────────
   Les MOTS de la zone se désignent dans le découpage du serveur (`GET /api/regions/{id}/mots`,
   sans jumeau navigateur) ; « Porte sur » dit ce que la grille vise ; un clic dans la grille
   POSE, retire ou change un relevé (`BDAnnotation.geste`), et chaque écriture d'une valeur
   unique porte `vu` — le retrait compris. Un refus de CONC-3, ou de la cardinalité, ouvre
   son bandeau À LA PLACE de la ligne du guide, sans changer la hauteur de la colonne ; tant
   qu'il est ouvert, aucun autre geste d'écriture ne part.
   Pendant un GLISSÉ, rien n'est redessiné sous le pointeur : seules les classes des mots
   changent ; les traits, la liste et la grille se redessinent au relâchement. */
const PALETTE = 7;              // les teintes des rubriques, `.an-teinte-0` à `-6`

function annoncer(texte) {
  const a = $("#an-annonce");
  a.textContent = "";
  setTimeout(() => { a.textContent = texte; }, 30);
}

function albumOuvert() { return S.albums.find((a) => a.id === S.albumId) || null; }
function ecrivable() { const a = albumOuvert(); return !!(a && a.ecrivable); }

function contexteDePose() {
  const c = caseCourante();
  return { porte: S.porte, zone: zoneCourante(), caseRegion: c ? c.case : null,
           plancheId: S.planche ? S.planche.id : null, mots: S.sel };
}

/* Les relevés montrés : ceux des grilles que « Relevés : ▾ » retient, plus la grille
   ouverte. */
function relevesMontres() {
  const m = A.grillesMontrees(S.reglage, S.grilles, S.grilleId);
  return S.releves.filter((r) => m.has(r.grille_id));
}

function grilleDe(id) { return S.grilles.find((g) => g.id === id) || null; }

/* ── « Porte sur » ── */
function rendrePorte() {
  const boite = $("#an-porte");
  const plan = planDe(grilleOuverte());
  const c = caseCourante();
  const opts = plan ? A.optionsPorteSur(plan, zoneCourante(), c ? c.case : null) : [];
  if (!opts.some((o) => o.cle === S.porte)) S.porte = opts.length ? opts[0].cle : null;
  boite.replaceChildren(
    el("span", { classe: "an-gr-lbl", texte: "Porte sur" }),
    ...(opts.length ? opts.map((o) => el("button", {
      type: "button", classe: "ghost small an-porte-btn", "data-porte": o.cle,
      "aria-pressed": String(o.cle === S.porte), texte: o.libelle }))
      : [el("span", { classe: "muted", texte: "—" })]));
}

/* ── Les mots ── */
async function chargerMots() {
  const z = zoneCourante();
  if (!z || z.pseudo || !A.estTexte(z.type)) { S.mots = null; return; }
  if (S.mots && S.mots.region_id === z.id) return;
  const tour = tourPlanche;
  const d = await apiGet(`/api/regions/${z.id}/mots`).catch(() => null);
  if (tour !== tourPlanche || !zoneCourante() || zoneCourante().id !== z.id) return;
  S.mots = d;
}

/* Les traits sous un mot (ou sous l'espace qui suit un mot) : un `<i>` par couloir, coloré
   quand un relevé du couloir passe là. */
function traits(position, lanes, nLanes, entreDeux) {
  const t = el("span", { classe: "an-traits", "aria-hidden": "true" });
  for (let L = 0; L < nLanes; L++) {
    const x = lanes.find((o) => o.lane === L && (entreDeux
      ? o.rangs.includes(position) && o.rangs.includes(position + 1)
      : o.rangs.includes(position)));
    t.append(el("i", { classe: x ? `an-trait ${x.classe}` : "an-trait-vide" }));
  }
  return t;
}

function rendreMots() {
  const z = zoneCourante();
  const titre = $("#an-texte-titre");
  const boite = $("#an-mots");
  const legende = $("#an-legende");
  for (const a of ["role", "aria-multiselectable", "tabindex", "aria-label", "aria-activedescendant"]) {
    boite.removeAttribute(a);
  }
  legende.replaceChildren();
  if (!z || z.pseudo || !A.estTexte(z.type)) {
    titre.textContent = "Texte";
    boite.replaceChildren("—");
    boite.classList.add("muted");
    return;
  }
  const c = caseCourante();
  titre.textContent = `Mots ${A.deLa(z.type)} ${A.etiquettesDeLaCase(c).get(z.id)}`;
  const d = S.mots && S.mots.region_id === z.id ? S.mots : null;
  if (!d || !d.mots.length) {
    boite.replaceChildren(d ? "—" : "…");
    boite.classList.add("muted");
    return;
  }
  boite.classList.remove("muted");
  boite.setAttribute("role", "listbox");
  boite.setAttribute("aria-multiselectable", "true");
  boite.setAttribute("tabindex", "0");
  boite.setAttribute("aria-label", titre.textContent);
  const plan = planDe(grilleOuverte());
  const surZone = relevesMontres().filter((r) => r.region_id === z.id
    && A.motsDuReleve(r).length);
  const lanesDe = A.couloirs(surZone);
  const lanes = surZone.map((r) => {
    const t = r.grille_id === S.grilleId ? A.teinte(plan, r.entree_cle, PALETTE) : null;
    return { lane: lanesDe.get(r.id), rangs: A.motsDuReleve(r),
             classe: t === null ? "an-trait-autre" : `an-teinte-${t}`, releve: r };
  });
  const nLanes = lanes.reduce((m, x) => Math.max(m, x.lane + 1), 0);
  const parties = [];
  d.mots.forEach((m, i) => {
    if (i) {
      const esp = d.texte.slice(d.mots[i - 1].fin, m.debut);   // verbatim, vide compris
      parties.push(el("span", { classe: "an-esp", "data-avant": m.rang },
                      el("span", { classe: "an-mot-t", texte: esp }),
                      traits(d.mots[i - 1].rang, lanes, nLanes, true)));
    }
    const sur = lanes.filter((x) => x.rangs.includes(m.rang))
      .map((x) => A.libelleReleve(x.releve, planDe(grilleDe(x.releve.grille_id))));
    parties.push(el("span", { classe: "an-mot", id: `an-mot-${m.rang}`, role: "option",
                              "data-rang": m.rang, "aria-selected": "false",
                              title: sur.length ? sur.join(" · ") : null },
                    el("span", { classe: "an-mot-t", texte: m.forme }),
                    traits(m.rang, lanes, nLanes, false)));
  });
  boite.replaceChildren(...parties);
  // La légende : une pastille par rubrique de tête dont un relevé est là, en lettres.
  const vues = new Map();
  for (const x of lanes) {
    if (x.classe === "an-trait-autre") { vues.set("autre", ["an-trait-autre", "autres grilles"]); continue; }
    const e = plan && plan.entrees.find((y) => y.cle === x.releve.entree_cle);
    const rub = e && plan.rubriques.find((r) => r.cle === e.rubriques[0]);
    if (rub) vues.set(rub.cle, [x.classe, rub.libelle]);
  }
  legende.replaceChildren(...[...vues.values()].map(([cl, lib]) =>
    el("span", { classe: "an-leg" }, el("i", { classe: `an-trait ${cl}` }), lib)));
  marquerSelection();
}

/* La sélection, sur les mots déjà dessinés : leurs classes et `aria-selected` seulement —
   ce que fait un glissé, à chaque mot survolé. */
function marquerSelection() {
  const sel = new Set(S.sel);
  for (const m of document.querySelectorAll("#an-mots .an-mot")) {
    const r = Number(m.dataset.rang);
    m.classList.toggle("sel", sel.has(r));
    m.setAttribute("aria-selected", String(sel.has(r)));
    m.classList.toggle("curseur", r === S.curseur);
  }
  for (const e of document.querySelectorAll("#an-mots .an-esp")) {
    const apres = Number(e.dataset.avant);
    e.classList.toggle("sel", sel.has(apres) && sel.has(apres - 1));
  }
  const boite = $("#an-mots");
  if (S.curseur !== null && $(`#an-mot-${S.curseur}`)) {
    boite.setAttribute("aria-activedescendant", `an-mot-${S.curseur}`);
  } else boite.removeAttribute("aria-activedescendant");
}

/* Ce qui suit un changement de sélection, hors glissé : la porte passe aux mots, la liste
   et l'état des entrées suivent. */
function apresSelection() {
  if (S.sel.length && A.optionsPorteSur(planDe(grilleOuverte()), zoneCourante(),
                                        caseCourante() && caseCourante().case)
        .some((o) => o.cle === "mots")) S.porte = "mots";
  marquerSelection();
  rendrePorte();
  rendreCorps();
  rendreListe();
}

function brancherMots() {
  const boite = $("#an-mots");
  let glisse = null;
  const motSous = (e) => {
    const m = e.target.closest && e.target.closest(".an-mot");
    return m ? Number(m.dataset.rang) : null;
  };
  boite.addEventListener("pointerdown", (e) => {
    const r = motSous(e);
    if (r === null || e.button !== 0) return;
    e.preventDefault();
    boite.focus({ preventScroll: true });
    S.curseur = r;
    if (e.ctrlKey || e.metaKey) {
      S.sel = A.basculer(S.sel, r);
      S.ancre = r;
      apresSelection();
      return;
    }
    if (e.shiftKey && S.ancre !== null) {
      S.sel = A.plage(S.ancre, r);
      apresSelection();
      return;
    }
    S.ancre = r;
    S.sel = [r];
    glisse = { dernier: r };
    marquerSelection();
  });
  boite.addEventListener("pointerover", (e) => {
    if (!glisse) return;
    const r = motSous(e);
    if (r === null || r === glisse.dernier) return;
    glisse.dernier = r;
    S.curseur = r;
    S.sel = A.plage(S.ancre, r);
    marquerSelection();            // rien d'autre sous le pointeur
  });
  const finir = () => {
    if (!glisse) return;
    glisse = null;
    apresSelection();
  };
  // Le glissé se termine aussi quand le navigateur l'avale (relâché hors de la fenêtre).
  document.addEventListener("pointerup", finir);
  document.addEventListener("pointercancel", finir);
  window.addEventListener("blur", finir);
  boite.addEventListener("keydown", (e) => {
    const d = S.mots;
    if (!d || !d.mots.length || boite.getAttribute("role") !== "listbox") return;
    const n = d.mots.length;
    const pos = S.curseur === null ? -1 : S.curseur;
    if (["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) {
      e.preventDefault();
      const neuf = e.key === "Home" ? 0 : e.key === "End" ? n - 1
        : Math.max(0, Math.min(n - 1, pos + (e.key === "ArrowRight" ? 1 : -1)));
      if (e.shiftKey) {
        if (S.ancre === null) S.ancre = pos < 0 ? neuf : pos;
        S.curseur = neuf;
        S.sel = A.plage(S.ancre, neuf);
        apresSelection();
      } else {
        S.curseur = neuf;
        marquerSelection();
      }
    } else if (e.key === " ") {
      e.preventDefault();
      if (S.curseur === null) return;
      S.sel = A.basculer(S.sel, S.curseur);
      S.ancre = S.curseur;
      apresSelection();
    } else if (e.key === "Enter") {
      e.preventDefault();
      $("#an-filtre").focus();
    } else if (e.key === "Escape" && S.sel.length) {
      e.preventDefault();
      S.sel = [];
      S.ancre = null;
      apresSelection();
    }
  });
}

/* ── Poser, changer, retirer ── */
function corpsDeCible(cible) {
  return cible.planche_id !== undefined ? { planche_id: cible.planche_id }
    : { region_id: cible.region_id, ...(cible.mots ? { mots: cible.mots } : {}) };
}

function remplacerReleve(vue) {
  const i = S.releves.findIndex((r) => r.id === vue.id);
  if (i < 0) S.releves.push(vue); else S.releves[i] = vue;
}

function oterReleve(id) { S.releves = S.releves.filter((r) => r.id !== id); }

/* Après une écriture : la page PATCHE ce qu'elle montre (la vue que la route rend), sans
   relire la planche, et redessine les traits, la liste et la grille — jamais la case. */
function apresEcriture() {
  rendreMots();
  rendreOnglets();
  rendreCorps();
  rendreListe();
}

function conflitOuvert() {
  if (!S.conflit) return false;
  toast("Réglez d'abord le conflit, en bas de la grille.", "error");
  const b = $("#an-cf-mienne");
  if (b) b.focus();
  return true;
}

/* Un geste d'écriture : `{ action, corps?, releve?, vu? }` (cf. `BDAnnotation.geste`), pour
   l'entrée `e` de la grille `g`, sur `cible`. `nouvelle` : le libellé d'une entrée qui naît
   en la posant (grille ouverte). */
async function ecrire(g, e, cible, gst, nouvelle) {
  const plan = planDe(g);
  try {
    if (gst.action === "poser") {
      const corps = { ...corpsDeCible(cible), grille_id: g.id, version: g.version.numero,
                      ...(nouvelle ? { nouvelle_entree: { libelle: nouvelle } }
                        : { entree_cle: e.cle }), ...gst.corps };
      const vue = await apiSend("POST", "/api/releves", corps);
      remplacerReleve(vue);
      if (nouvelle) await rechargerPlan(g);
      annoncer(`Posé : ${A.libelleReleve(vue, planDe(g))}`);
    } else if (gst.action === "modifier") {
      const vue = await apiSend("PUT", `/api/releves/${gst.releve.id}`,
                                { ...gst.corps, vu: gst.vu });
      remplacerReleve(vue);
      annoncer(`Changé : ${A.libelleReleve(vue, plan)}`);
    } else if (gst.action === "retirer") {
      await apiSend("DELETE", `/api/releves/${gst.releve.id}`, { vu: gst.vu });
      oterReleve(gst.releve.id);
      annoncer(`Retiré : ${A.libelleReleve(gst.releve, plan)}`);
    }
  } catch (err) {
    refus(err, { g, e, cible, gst, nouvelle });
  }
  apresEcriture();
}

/* Les refus que l'écran sait dire sans rien deviner. */
function refus(err, contexte) {
  const d = err && err.detail;
  if (err.statut === 409 && d && d.conflit) {
    S.conflit = { sorte: "valeur", detail: d, ...contexte };
    rendreGuide();
    annoncer(BDConflit.titreConflit(d.conflit));
    const b = $("#an-cf-mienne");
    if (b) b.focus();
    return;
  }
  if (err.statut === 409 && d && d.releve_existant) {
    S.conflit = { sorte: "cardinalite", detail: d, ...contexte,
                  remplacement: A.remplacementCardinalite(d, contexte.gst.corps) };
    rendreGuide();
    annoncer(d.message);
    const b = $("#an-cf-mienne");
    if (b) b.focus();
    return;
  }
  if (err.statut === 404 && contexte.gst.releve) {
    oterReleve(contexte.gst.releve.id);
    toast("Ce relevé a été retiré depuis, par un autre écran.", "error");
    annoncer("Ce relevé a été retiré depuis, par un autre écran.");
    return;
  }
  toast(err.message || "Refusé.", "error");
  annoncer(err.message || "Refusé.");
}

/* Le geste d'un clic dans la grille, ou d'Entrée sur un résultat du filtre. */
async function poser(entreeCle, choix) {
  if (conflitOuvert()) return;
  const g = grilleOuverte();
  const plan = planDe(g);
  const e = plan && plan.entrees.find((x) => x.cle === entreeCle);
  if (!e) return;
  if (!ecrivable()) { annoncer("Vous lisez cet album : rien ne s'y pose."); return; }
  const cible = A.cibleDePose(e, contexteDePose());
  if (cible.erreur) { toast(cible.erreur, "error"); annoncer(cible.erreur); return; }
  const gst = A.geste(e, A.relevesSurLaCible(S.releves, g.id, e.cle, cible), choix);
  if (!gst) return;
  await ecrire(g, e, cible, gst);
}

/* « Créer « … » » : une entrée naît en la posant, dans une grille ouverte (G14). */
async function creer(libelle) {
  if (conflitOuvert()) return;
  const g = grilleOuverte();
  const plan = planDe(g);
  if (!g || !g.ouverte || !plan || !ecrivable()) return;
  const e = A.entreeNeuve(plan, libelle);
  const cible = A.cibleDePose(e, contexteDePose());
  if (cible.erreur) { toast(cible.erreur, "error"); annoncer(cible.erreur); return; }
  await ecrire(g, e, cible, { action: "poser", corps: {} }, libelle);
  S.filtre = "";
  $("#an-filtre").value = "";
  rendreCorps();
}

async function rechargerPlan(g) {
  const cle = `${g.id}:${g.version.numero}`;
  const plan = await apiGet(`/api/grilles/${g.id}/versions/${g.version.numero}`).catch(() => null);
  if (plan) S.plans.set(cle, plan);
}

/* Le BANDEAU d'un conflit, à la place de la ligne du guide : ce qui n'est pas enregistré,
   la version de l'autre, « Remplacer par la mienne », « Garder l'autre ». */
function bandeau() {
  const cf = S.conflit;
  const plan = planDe(cf.g);
  const lignes = [];
  if (cf.sorte === "valeur") {
    const c = cf.detail.conflit;
    const actuelle = c.valeur_actuelle;
    let version;
    if (c.champ === "variante_cle") {
      const v = (cf.e.variantes || []).find((x) => x.cle === actuelle);
      version = actuelle ? (v ? v.libelle : actuelle) : "aucune variante";
    } else if (c.champ === "qualificatifs") {
      version = A.libelleReleve({ entree_cle: cf.e.cle, qualificatifs: actuelle || [] }, plan);
    } else if (c.champ === "mots") {
      version = S.mots ? `« ${A.texteDuPassage(S.mots.mots, actuelle || [])} »` : "un autre passage";
    } else {
      version = actuelle === null || actuelle === undefined || actuelle === "" ? "—" : String(actuelle);
    }
    lignes.push(el("p", { classe: "an-bandeau-titre", id: "an-cf-titre" },
                   el("span", { "aria-hidden": "true", texte: "⚠ " }),
                   BDConflit.titreConflit(c)));
    lignes.push(el("p", { texte: cf.gst.action === "retirer"
      ? "Votre retrait n'est pas enregistré." : "Votre choix n'est pas enregistré." }));
    lignes.push(el("p", { classe: "an-bandeau-version" },
                   el("span", { classe: "muted", texte: "Version enregistrée : " }), version));
  } else {
    lignes.push(el("p", { classe: "an-bandeau-titre", id: "an-cf-titre" },
                   el("span", { "aria-hidden": "true", texte: "⚠ " }),
                   `« ${cf.e.libelle} » est déjà posé ici`
                     + (cf.remplacement && cf.remplacement.auteur ? ` par ${cf.remplacement.auteur}` : "")));
    lignes.push(el("p", { texte: cf.detail.message }));
  }
  lignes.push(el("div", { classe: "an-bandeau-gestes", role: "group",
                          "aria-labelledby": "an-cf-titre" },
                 el("button", { type: "button", classe: "ghost small", id: "an-cf-mienne",
                                texte: BDConflit.GESTES.remplacer }),
                 el("button", { type: "button", classe: "ghost small", id: "an-cf-autre",
                                texte: BDConflit.GESTES.garderAutre })));
  return lignes;
}

async function resoudreConflit(garderMienne) {
  const cf = S.conflit;
  S.conflit = null;
  if (garderMienne) {
    if (cf.sorte === "valeur") {
      // On renvoie SA version, gardée cette fois sur la valeur qu'on vient de lire.
      const c = cf.detail.conflit;
      const gst = { ...cf.gst, vu: { ...(cf.gst.vu || {}), [c.champ]: c.valeur_actuelle } };
      await ecrire(cf.g, cf.e, cf.cible, gst, cf.nouvelle);
    } else if (cf.remplacement) {
      const ex = S.releves.find((r) => r.id === cf.remplacement.releve_id) || { id: cf.remplacement.releve_id };
      const { vu, ...corps } = cf.remplacement.corps;
      await ecrire(cf.g, cf.e, cf.cible, { action: "modifier", releve: ex, corps, vu });
    }
  } else {
    await relireReleves();
    annoncer("La version enregistrée est gardée.");
  }
  rendreGuide();
}

async function relireReleves() {
  if (!S.planche) return;
  const d = await apiGet(`/api/planches/${S.planche.id}/releves`).catch(() => null);
  if (d) S.releves = d.releves;
  apresEcriture();
}

/* ── Ce qui est posé, en bas de la colonne ── */
function rendreListe() {
  const titre = $("#an-poses-titre");
  const liste = $("#an-poses-liste");
  const bouton = $("#an-releves-btn");
  const g = grilleOuverte();
  const z = zoneCourante();
  const c = caseCourante();
  const m = A.grillesMontrees(S.reglage, S.grilles, S.grilleId);
  const autres = [...m].filter((id) => id !== S.grilleId).length;
  bouton.textContent = `Relevés : ${g ? g.nom : "—"}${autres ? ` + ${autres}` : ""} ▾`;
  if (!z) { titre.textContent = "—"; liste.replaceChildren(); return; }
  const passage = S.sel.length && S.mots ? A.texteDuPassage(S.mots.mots, S.sel) : null;
  titre.textContent = passage ? `Sur « ${passage} »`
    : z.pseudo ? "Sur la planche" : `Dans ${laZone(z)}`;
  const montres = A.listeSurLaZone(relevesMontres(), z, c ? c.case : null,
                                   S.planche ? S.planche.id : null, S.sel);
  liste.replaceChildren(...(montres.length ? montres.map(itemReleve)
    : [el("li", { classe: "an-pose-vide muted", texte: "—" })]));
  rendrePopover();
}

/* « la bulle b1 », « le cartouche b2 », « la case c3 », « la boîte p1 ». */
function laZone(z) {
  const c = caseCourante();
  const etiq = z.type === "case" ? A.etiquette(z) : c ? A.etiquettesDeLaCase(c).get(z.id) : "";
  const nom = z.type === "personnage" ? "la boîte"
    : `${["cartouche", "texte", "detail"].includes(z.type) ? "le" : "la"} ${A.nomType(z.type)}`;
  return `${nom} ${etiq || ""}`.trim();
}

function itemReleve(r) {
  const g = grilleDe(r.grille_id);
  const plan = planDe(g);
  const e = plan && plan.entrees.find((x) => x.cle === r.entree_cle);
  const masquee = g && A.masquee(g, S.collection);
  const gestes = r.modifiable && !masquee && ecrivable();
  const t = g && g.id === S.grilleId ? A.teinte(plan, r.entree_cle, PALETTE) : null;
  const passage = A.motsDuReleve(r).length && S.mots && S.mots.region_id === r.region_id
    ? `« ${A.texteDuPassage(S.mots.mots, A.motsDuReleve(r))} »`
    : r.planche_id ? "la planche" : r.region_id === (zoneCourante() || {}).id ? "toute la zone" : "la case";
  const etat = A.motEtat(r);
  const libelle = A.libelleReleve(r, plan);
  const li = el("li", { classe: `an-pose${masquee ? " an-pose-masquee" : ""}` },
    el("button", { type: "button", classe: "an-pose-btn", "data-releve": r.id,
                   title: masquee ? "Grille masquée dans cette collection : en lecture" : null },
       el("i", { classe: `an-pastille ${t === null ? "an-trait-autre" : `an-teinte-${t}`}`,
                 "aria-hidden": "true" }),
       el("span", { classe: "an-pose-lib", texte: libelle }),
       el("span", { classe: "an-pose-pass", texte: passage }),
       etat ? el("span", { classe: `an-etat an-etat-${r.etat}`, texte: etat }) : null,
       g && g.id !== S.grilleId ? el("span", { classe: "an-pose-gr", texte: g.nom }) : null));
  if (gestes && e && e.precision) {
    li.append(el("span", { classe: "an-pose-prec" },
      el("input", { type: "text", classe: "an-prec", "data-releve": r.id,
                    "aria-label": `${e.precision} — ${libelle}`, placeholder: e.precision,
                    value: r.precision || "", maxlength: 500 })));
  }
  if (gestes && e && e.lien) {
    const designe = S.designer === r.id;
    li.append(el("button", { type: "button", classe: "ghost small an-lien-btn",
                             "data-lien": r.id, "aria-pressed": String(designe),
                             title: designe ? "Cliquez l'autre bulle · Échap annule" : null,
                             texte: r.lien && r.lien.existe ? "Changer le lien" : "Désigner sur la planche" }));
  }
  if (gestes) {
    li.append(el("button", { type: "button", classe: "ghost small an-retirer", "data-retirer": r.id,
                             "aria-label": `Retirer ${libelle}`, title: "Retirer ce relevé",
                             texte: "✕" }));
  }
  return li;
}

/* « Relevés : ▾ » : les cases des grilles actives, la grille ouverte toujours cochée. */
function rendrePopover() {
  const pop = $("#an-releves-pop");
  const m = A.grillesMontrees(S.reglage, S.grilles, S.grilleId);
  const g = grilleOuverte();
  pop.replaceChildren(...S.grilles.map((x) => el("label", { classe: "an-pop-l" },
    el("input", { type: "checkbox", "data-voir": x.id, checked: m.has(x.id),
                  disabled: x.id === S.grilleId }),
    ` ${x.nom}`, x.id === S.grilleId ? el("span", { classe: "muted small", texte: " · ouverte" })
      : A.masquee(x, S.collection) ? el("span", { classe: "muted small", texte: " · masquée ici" }) : null)),
  el("div", { classe: "an-pop-gestes" },
     el("button", { type: "button", classe: "ghost small", "data-voir-tout": "1", texte: "Toutes" }),
     el("button", { type: "button", classe: "ghost small", "data-voir-seule": "1",
                    texte: `${g ? g.nom : "La grille"} seule` })));
}

function changerReglage(ids) {
  S.reglage = A.rangs(ids);
  A.retenirReglage(stockageLocal(), S.login, S.projet, S.reglage);
  rendreMots();
  rendreListe();
}

function stockageLocal() { try { return window.localStorage || null; } catch (e) { return null; } }

/* Le lien d'un chevauchement : « Désigner sur la planche », puis un clic sur l'autre zone
   de texte — dans la case agrandie, sur la minicarte, ou dans la rangée des zones. */
async function designerLien(regionId) {
  const r = S.releves.find((x) => x.id === S.designer);
  S.designer = null;
  document.body.classList.remove("an-designer");
  if (!r) return;
  const g = grilleDe(r.grille_id);
  const plan = planDe(g);
  const e = plan && plan.entrees.find((x) => x.cle === r.entree_cle);
  await ecrire(g, e, null, { action: "modifier", releve: r, corps: { lien_region_id: regionId },
                             vu: { lien_region_id: r.lien ? r.lien.region_id : null } });
}

function brancherPose() {
  brancherMots();
  $("#an-porte").addEventListener("click", (e) => {
    const b = e.target.closest("[data-porte]");
    if (!b) return;
    S.porte = b.dataset.porte;
    rendrePorte();
    rendreCorps();
  });
  const liste = $("#an-poses-liste");
  liste.addEventListener("click", (e) => {
    const ret = e.target.closest("[data-retirer]");
    if (ret) {
      if (conflitOuvert()) return;
      const r = S.releves.find((x) => x.id === Number(ret.dataset.retirer));
      if (!r) return;
      const g = grilleDe(r.grille_id);
      const plan = planDe(g);
      const ent = plan && plan.entrees.find((x) => x.cle === r.entree_cle);
      ecrire(g, ent, null, { action: "retirer", releve: r, vu: A.vuDuReleve(r) });
      return;
    }
    const lien = e.target.closest("[data-lien]");
    if (lien) {
      if (conflitOuvert()) return;
      const id = Number(lien.dataset.lien);
      S.designer = S.designer === id ? null : id;
      document.body.classList.toggle("an-designer", S.designer !== null);
      if (S.designer !== null) annoncer("Désignez l'autre zone de texte, sur la planche ou dans la case. Échap annule.");
      rendreListe();
      return;
    }
    const item = e.target.closest("[data-releve].an-pose-btn");
    if (!item) return;
    const r = S.releves.find((x) => x.id === Number(item.dataset.releve));
    if (!r) return;
    if (r.grille_id !== S.grilleId && grilleDe(r.grille_id)
        && !A.masquee(grilleDe(r.grille_id), S.collection)) choisirGrille(r.grille_id);
    if (A.motsDuReleve(r).length && r.region_id === (zoneCourante() || {}).id) {
      S.sel = A.motsDuReleve(r);
      S.ancre = S.sel[0];
      apresSelection();
    }
    montrerGuide(r.entree_cle, r.variante_cle);
  });
  // La précision attendue : Entrée ou la sortie du champ l'enregistrent, avec `vu`.
  const precision = (champ) => {
    const r = S.releves.find((x) => x.id === Number(champ.dataset.releve));
    if (!r || (champ.value.trim() || null) === (r.precision || null)) return;
    if (conflitOuvert()) return;
    const g = grilleDe(r.grille_id);
    const plan = planDe(g);
    const ent = plan && plan.entrees.find((x) => x.cle === r.entree_cle);
    ecrire(g, ent, null, { action: "modifier", releve: r,
                           corps: { precision: champ.value.trim() || null },
                           vu: { precision: r.precision || null } });
  };
  liste.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target.matches(".an-prec")) { e.preventDefault(); precision(e.target); }
  });
  liste.addEventListener("focusout", (e) => { if (e.target.matches(".an-prec")) precision(e.target); });
  const bouton = $("#an-releves-btn");
  const pop = $("#an-releves-pop");
  bouton.addEventListener("click", () => {
    const ouvrir = pop.hidden;
    pop.hidden = !ouvrir;
    bouton.setAttribute("aria-expanded", String(ouvrir));
  });
  pop.addEventListener("change", (e) => {
    const c = e.target.closest("[data-voir]");
    if (!c) return;
    const m = A.grillesMontrees(S.reglage, S.grilles, S.grilleId);
    const id = Number(c.dataset.voir);
    if (c.checked) m.add(id); else m.delete(id);
    changerReglage([...m]);
  });
  pop.addEventListener("click", (e) => {
    if (e.target.closest("[data-voir-tout]")) changerReglage(S.grilles.map((g) => g.id));
    else if (e.target.closest("[data-voir-seule]")) changerReglage([]);
  });
  $("#an-guide-contenu").addEventListener("click", (e) => {
    if (e.target.closest("#an-cf-mienne")) resoudreConflit(true);
    else if (e.target.closest("#an-cf-autre")) resoudreConflit(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && S.designer !== null) {
      S.designer = null;
      document.body.classList.remove("an-designer");
      rendreListe();
    }
  });
}

/* ───────────── L'adresse ───────────── */
function etatAdresse() {
  const z = zoneCourante();
  return {
    collection: S.collection, album: S.albumId,
    planche: S.planche ? S.planche.id : null,
    region: z && !z.pseudo ? z.id : null,
    grille: S.grilleId,
  };
}

function syncAdresse() {
  const etat = etatAdresse();
  const qs = A.adresse(etat);
  const avecRetour = RETOUR
    ? (qs ? qs + "&" : "?") + "retour=" + encodeURIComponent(RETOUR) : qs;
  history.replaceState(null, "", location.pathname + avecRetour);
  Nav.memoriser(Nav.stockageDeSession(window), PAGE, avecRetour);
  const lien = $("#an-atelier");
  lien.href = A.lienAtelier(etat, location.pathname + qs);
}

/* « ← Retour » : le `retour` explicite ; à défaut, la page d'où l'on arrive dans l'app
   (`history.back()`). Masqué s'il n'y a nulle part où revenir — le patron des autres
   surfaces (`recherche.js`). */
function preparerRetour() {
  const back = $("#back-link");
  let cible = RETOUR;
  if (!cible) {
    try {
      const ref = document.referrer ? new URL(document.referrer) : null;
      if (ref && ref.origin === location.origin && ref.pathname !== location.pathname) {
        cible = "__back__";
      }
    } catch (e) { /* referrer illisible */ }
  }
  if (!cible) return;
  back.hidden = false;
  if (cible === "__back__") {
    back.href = "#";
    back.addEventListener("click", (e) => { e.preventDefault(); history.back(); });
  } else {
    back.href = cible;
  }
}

/* ───────────── Les gestes ───────────── */
async function changerCollection(valeur) {
  const choix = BDAtelier.valide(valeur, S.collections);
  if (choix === null) { $("#an-collection").value = String(S.collection); return; }
  S.collection = choix;
  S.collectionProjet = S.projet;
  BDAtelier.retenir(S.projet, choix);
  // Le masque d'une grille est celui de la collection choisie : les onglets suivent.
  await chargerGrilles();
  await afficherAlbums(S.albumId, null);
}

function brancher() {
  $("#an-collection").addEventListener("change", (e) =>
    changerCollection(e.target.value).catch((err) => toast(err.message, "error")));
  $("#an-album").addEventListener("change", (e) => {
    const id = Number(e.target.value);
    if (id) ouvrirAlbum(id, null).catch((err) => toast(err.message, "error"));
  });
  $("#an-planche-choix").addEventListener("change", (e) => {
    const id = Number(e.target.value);
    if (id) ouvrirPlanche(id).catch((err) => toast(err.message, "error"));
  });
  const mini = $("#an-mini");
  mini.addEventListener("click", (e) => {
    const d = e.target.closest("[data-region]");
    if (d && S.designer !== null) { designerLien(Number(d.dataset.region)); return; }
    const r = e.target.closest(".an-mz");
    if (r) choisir(Number(r.dataset.case), null);
  });
  mini.addEventListener("keydown", (e) => {
    const r = e.target.closest(".an-mz");
    if (r && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      choisir(Number(r.dataset.case), null);
    }
  });
  $("#an-vue-case").addEventListener("click", (e) => {
    const r = e.target.closest("[data-zone]");
    if (!r) return;
    if (S.designer !== null && r.dataset.zone !== "") { designerLien(Number(r.dataset.zone)); return; }
    choisir(S.caseIx, r.dataset.zone === "" ? null : Number(r.dataset.zone));
  });
  $("#an-zones").addEventListener("click", (e) => {
    const b = e.target.closest(".an-zone-btn");
    if (b && S.designer !== null && b.dataset.zone !== "") {
      designerLien(Number(b.dataset.zone));
      return;
    }
    if (b) choisir(S.caseIx, b.dataset.zone === "" ? null : Number(b.dataset.zone));
  });
  // La taille des étiquettes suit la boîte : une fenêtre qu'on élargit, un zoom d'interface.
  if (typeof ResizeObserver === "function") {
    let attente = null;
    new ResizeObserver(() => {
      cancelAnimationFrame(attente);
      attente = requestAnimationFrame(rendreCase);
    }).observe($("#an-vue-case"));
  }
  document.addEventListener(BDProjet.EVENEMENT, (e) => {
    const id = e.detail ? e.detail.id : null;
    if (id == null || id === S.projet) return;
    S.projet = id;
    chargerAlbums().catch((err) => toast("Erreur de chargement : " + err.message, "error"));
  });
}

async function demarrer() {
  preparerRetour();
  brancher();
  brancherGrille();
  brancherPose();
  try {
    await chargerAlbums();
  } catch (e) {
    toast("Erreur de chargement : " + e.message, "error");
  }
}

demarrer();
