/* La page ANNOTATION (`/annotation`) — la sixième surface (ANN-7, tranche 2 ; ANN-6, l'écran
   du relevé). Cadrage : `docs/ann7-tranche2-cadrage.md`. Ce script DESSINE ; ce qui se
   décide — le rangement d'une planche en cases, les étiquettes, l'adresse, le Contexte —
   vit dans `static/lib/annotation.js` (`BDAnnotation`), testé sous Node.

   CE PREMIER TEMPS (commit 1 du jalon 1) : la page, sans grille ni pose. On y choisit une
   collection, un album et une planche du PROJET COURANT ; sur la minicarte, une CASE ; dans
   la case agrandie, une zone — une bulle, un cartouche, un texte, une boîte personnage —, ou
   le fond (la case elle-même). Le Contexte se lit (locuteur, personnage, note), sans geste :
   il s'écrit dans l'Atelier, où mène « Ouvrir dans l'Atelier ↗ ».

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
  S.personnages = new Map();
  if (S.planche) {
    $("#an-planche-choix").value = String(S.planche.id);
    const regions = await apiGet(`/api/planches/${S.planche.id}/regions`);
    if (tour !== tourPlanche) return;
    S.regions = regions;
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

/* ───────────── L'adresse ───────────── */
function etatAdresse() {
  const z = zoneCourante();
  return {
    collection: S.collection, album: S.albumId,
    planche: S.planche ? S.planche.id : null,
    region: z && !z.pseudo ? z.id : null,
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
  try {
    await chargerAlbums();
  } catch (e) {
    toast("Erreur de chargement : " + e.message, "error");
  }
}

demarrer();
