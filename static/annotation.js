/* La page ANNOTATION (`/annotation`) — la sixième surface (ANN-7, tranche 2 ; ANN-6, l'écran
   du relevé). Cadrage : `docs/ann7-tranche2-cadrage.md`. Ce script DESSINE ; ce qui se
   décide — le rangement d'une planche en cases, les étiquettes, l'adresse, le Contexte —
   vit dans `static/lib/annotation.js` (`BDAnnotation`), testé sous Node.

   LE JALON 1, commits 1 et 2 : la page et la grille EN LECTURE, sans pose. On y choisit une
   collection, un album et une planche du PROJET COURANT ; sur la minicarte, une CASE ; dans
   la case agrandie, une zone — une bulle, un cartouche, un texte, une boîte personnage —, ou
   le fond (la case elle-même). Le Contexte se lit (locuteur, personnage, note), sans geste :
   il s'écrit dans l'Atelier, où mène « Ouvrir dans l'Atelier ↗ ». À droite, les grilles
   actives du projet que la collection ne masque pas : leur plan, le filtre, la ligne du
   guide, le guide complet (commit 2).

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
  marquerMini();
  rendreTete();
  rendreCase();
  rendreZones();
  rendreTexte();
  rendreContexte();
  rendreGrille();
  lirePersonnagesDeLaCase();
  syncAdresse();
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
      racine.appendChild(svg("rect", { class: "an-mz-enfant", x: z.x, y: z.y, width: z.w,
                                        height: z.h, "aria-hidden": "true" }));
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

/* Le texte d'une zone de texte, en lecture. Les MOTS — à désigner — viennent au commit 3. */
function rendreTexte() {
  const z = zoneCourante();
  const titre = $("#an-texte-titre");
  const corps = $("#an-texte");
  if (z && A.estTexte(z.type)) {
    const c = caseCourante();
    titre.textContent = `Texte ${A.deLa(z.type)} ${A.etiquettesDeLaCase(c).get(z.id)}`;
    corps.textContent = z.ocr_texte || "—";
    corps.classList.toggle("muted", !z.ocr_texte);
  } else {
    titre.textContent = "Texte";
    corps.textContent = "—";
    corps.classList.add("muted");
  }
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
  rendreCorps();
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
  if (e.forme === "variantes") {
    const tete = el("button", { type: "button", classe: `an-ent-btn an-ent-tete${guide ? " guide" : ""}`,
                                "data-guide-e": e.cle, id: `an-ent-${e.cle}` },
                    el("span", { classe: "an-ent-lib", texte: e.libelle }),
                    el("span", { classe: "muted small", texte: "une parmi" }), ...marques(e, n));
    const vars = el("div", { classe: "an-vars" }, ...(e.variantes || []).map((v) =>
      el("button", { type: "button",
                     classe: `ghost an-var${S.guide && S.guide.e === e.cle && S.guide.v === v.cle ? " guide" : ""}`,
                     "data-guide-e": e.cle, "data-guide-v": v.cle, texte: v.libelle })));
    return el("div", { classe: "an-ent", role: "group", "aria-labelledby": `an-ent-${e.cle}` },
              tete, vars);
  }
  const liste = e.forme === "qualificatifs"
    ? (plan.listes || []).find((l) => l.cle === e.liste_cle) : null;
  return el("div", { classe: "an-ent" },
    el("button", { type: "button", classe: `an-ent-btn${guide ? " guide" : ""}`,
                   "data-guide-e": e.cle },
       el("span", { classe: "an-box", "aria-hidden": "true" }),
       el("span", { classe: "an-ent-lib", texte: e.libelle }),
       liste ? el("span", { classe: "muted small",
                            texte: `+ ${liste.libelle || liste.cle}` }) : null,
       ...marques(e, n)));
}

/* Les résultats du filtre : une liste d'options que le champ désigne
   (`aria-activedescendant`) ; « Aussi dans » les autres grilles visibles. */
function rendreResultats(plan, filtre) {
  const res = $("#an-resultats");
  const champ = $("#an-filtre");
  const trouves = A.chercher(plan, filtre);
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
      classe: `an-res${i === S.actif ? " actif" : ""}` },
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
    if (b) montrerGuide(b.dataset.guideE, b.dataset.guideV);
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
      // La pose viendra au commit 3 ; d'ici là, Entrée dit la ligne du guide du résultat.
      e.preventDefault();
      const r = S.resultats[S.actif];
      montrerGuide(r.entree_cle, r.variante_cle);
    }
  });
  $("#an-resultats").addEventListener("click", (e) => {
    const li = e.target.closest("[data-res]");
    if (!li) return;
    S.actif = Number(li.dataset.res);
    const r = S.resultats[S.actif];
    rendreCorps();
    montrerGuide(r.entree_cle, r.variante_cle);
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
    choisir(S.caseIx, r.dataset.zone === "" ? null : Number(r.dataset.zone));
  });
  $("#an-zones").addEventListener("click", (e) => {
    const b = e.target.closest(".an-zone-btn");
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
  try {
    await chargerAlbums();
  } catch (e) {
    toast("Erreur de chargement : " + e.message, "error");
  }
}

demarrer();
