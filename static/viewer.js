/* ===================================================================
   BéDéditeur — visionneuse & logique d'annotation (vanilla JS)
   -------------------------------------------------------------------
   Systèmes de coordonnées :
     • Les régions sont stockées en pixels MASTER.
     • L'overlay SVG a son viewBox en pixels MASTER, mais sa taille CSS
       (width/height) correspond au dérivé web : le SVG fait donc lui-même
       la conversion master→web. Les rects sont placés en coords master.
     • Le pan/zoom est une transform CSS sur #canvas (img + overlay).
     • getScreenCTM() de l'overlay intègre la transform CSS : on convertit
       donc écran→master directement, sans calcul manuel de ratio.
   =================================================================== */
"use strict";

const API = "";
const HANDLE_PX = 9;      // taille écran cible des poignées
const LABEL_PX = 13;      // taille écran cible des libellés de région
const SAVE_DEBOUNCE = 500;

const SVGNS = "http://www.w3.org/2000/svg";

// URL de départ captée AVANT tout chargement (le chargement met l'URL à jour via
// syncUrl → on ne pourrait plus relire le deep-link d'origine ensuite).
const INITIAL_QS = location.search;
// D'où l'on vient (drill Recherche/Exploration), validé (page interne seulement,
// cf. static/lib/nav.js) : conservé toute la session pour le bouton « ← Retour ».
const RETOUR = Nav.safeRetour(new URLSearchParams(INITIAL_QS).get("retour"));

/* ---------------- État global ---------------- */
/* Le login courant, pour distinguer « verrouillée par vous » de « par X » (AUTH-1).
   Il vient de la promesse partagée par `theme.js` : une seule requête par page, et la
   comparaison porte sur le LOGIN — deux personnes peuvent partager un nom d'affichage, et
   attribuer le verrou d'un homonyme serait pire que de ne rien dire. Reste `null` en
   mono-poste (agent anonyme) et si l'appel échoue, auquel cas l'écran nomme sans
   distinguer : dégradation lisible, jamais fausse. */
let VIEWER_MOI = null;
if (window.BDMoi) {
  window.BDMoi.then((d) => {
    VIEWER_MOI = (d && d.utilisateur) || null;
    // La boîte du verrou a pu se dessiner avant la réponse. On la REJOUE plutôt que de
    // parier sur l'ordre : elle est réentrante (elle ne lit que `state.planche`), et un
    // « par <votre nom> » adressé à soi-même n'est pas faux, seulement absurde.
    if (VIEWER_MOI) renderPlancheLock();
  });
}

const state = {
  albums: [],
  albumId: null,
  planches: [],
  planche: null,           // planche courante (objet de la liste)
  webScale: 1,             // web_width / master_width
  webW: 0, webH: 0,
  regions: [],
  regionsById: new Map(),
  selectedId: null,
  mode: "navigation",
  zoom: 1, tx: 0, ty: 0,
  tagVocab: [],            // [{label, couleur, frequence}]
  currentTags: [],         // labels (string) de l'annotation en cours
  saveTimer: null,
  trRegions: [],           // régions de texte à transcrire (ordre de lecture)
  trIndex: 0,
  trSaveTimer: null,
};

/* ---------------- Raccourcis DOM ($, apiGet, apiSend, toast, escapeHtml : lib/common.js) ---------------- */
const stage = $("#stage");
const canvas = $("#canvas");
const img = $("#planche-img");
const overlay = $("#overlay");

/* apiGet / apiSend (avec opts.signal) et toast viennent de lib/common.js.
   `API` (= "") reste local : il préfixe d'autres fetch directs (import, export, sauvegarde). */

/* ===================================================================
   Chargement albums / planches
   =================================================================== */
async function loadAlbums() {
  state.albums = await apiGet("/api/albums");
  const sel = $("#album-select");
  sel.innerHTML = "";
  if (!state.albums.length) {
    sel.innerHTML = '<option value="">— aucun album —</option>';
    return;
  }
  for (const a of state.albums) {
    const opt = document.createElement("option");
    opt.value = a.id;
    opt.textContent = `${a.serie ? a.serie + " · " : ""}${a.titre} (${a.nb_planches})`;
    sel.appendChild(opt);
  }
  const first = state.albumId || state.albums[0].id;
  sel.value = first;
  await selectAlbum(Number(first));
}

async function selectAlbum(id, autoSelect = true) {
  state.albumId = id;
  state.planches = await apiGet(`/api/albums/${id}/planches`);
  renderPlancheList();
  // `autoSelect=false` : un deep-link va choisir une planche PRÉCISE → ne pas charger
  // planche[0] pour rien (F5). On vide le stage en attendant : sinon, si le deep-link
  // pointe une planche inexistante, on afficherait la planche PÉRIMÉE de l'album précédent.
  if (autoSelect && state.planches.length) selectPlanche(state.planches[0].id);
  else { state.planche = null; clearStage(); }
}

/* Libellé éditorial d'une planche : numéro CITÉ (récit) ou « Paratexte ». Le numéro
   éditorial est dérivé côté serveur (cf. docs/numerotation-et-citation.md). */
function plancheLabel(p) {
  return p.role === "recit" ? `planche ${p.numero_editorial}` : "Paratexte";
}

/* Étiquette d'une région sur l'image : rang de CITATION (« c2 » pour une case,
   « b1 » pour une bulle) ; repli sur l'ordre brut hors récit. Cf. citation serveur. */
function regionLabel(r) {
  const c = r.citation;
  if (c) {
    if (r.type === "case" && c.case != null) return "c" + c.case;
    if (c.bulle != null) return "b" + c.bulle;
  }
  return `${r.ordre ?? "?"}·${r.type[0]}`;
}

function renderPlancheList() {
  const ul = $("#planche-list");
  ul.innerHTML = "";
  for (const p of state.planches) {
    const li = document.createElement("li");
    li.dataset.id = p.id;
    if (state.planche && p.id === state.planche.id) li.classList.add("active");
    li.innerHTML =
      `<span class="statut-pill statut-${escapeHtml(p.statut)}" title="${escapeHtml(p.statut)}"></span>` +
      `<span class="num" title="${escapeHtml(plancheLabel(p))}">` +
        `${p.role === "recit" ? "pl." + p.numero_editorial : "¶ para"}</span>` +
      `<span class="meta">${p.nb_regions} rég. · ${p.nb_annotees} ann.</span>`;
    li.onclick = () => selectPlanche(p.id);
    ul.appendChild(li);
  }
}

function clearStage() {
  img.removeAttribute("src");
  overlay.innerHTML = "";
  $("#stage-empty").style.display = "flex";
  $("#planche-info").textContent = "—";
  state.selectedId = null;
  renderPanel();   // masque l'arbre/le détail de l'ancienne planche
}

/* ===================================================================
   Sélection / chargement d'une planche
   =================================================================== */
let plancheGen = 0;   // anti-course : invalide les chargements de planche périmés

async function selectPlanche(id) {
  flushSave();
  const p = state.planches.find((x) => x.id === id);
  if (!p) return;
  const gen = ++plancheGen;   // seule la sélection la plus récente appliquera ses résultats
  state.planche = p;
  state.selectedId = null;
  state.collapsedNodes = new Set();   // l'état de pli de l'arbre est propre à la planche

  renderPlancheList();
  const album = state.albums.find((a) => a.id === state.albumId);
  $("#planche-info").textContent =
    `${album ? album.titre : ""} — ${plancheLabel(p)} · ${p.statut}`;

  // Charge l'image web puis les régions.
  $("#stage-empty").style.display = "none";
  await new Promise((res, rej) => {
    img.onload = () => res();
    img.onerror = () => rej(new Error("image illisible"));
    // Réassigner la même src ne refire pas onload : on résout d'emblée si
    // l'image est déjà chargée (re-sélection de la planche courante).
    if (img.getAttribute("src") === p.url_web && img.complete && img.naturalWidth)
      res();
    else
      img.src = p.url_web;
  }).catch(() => toast("Image de la planche introuvable", "error"));
  if (gen !== plancheGen) return;   // une sélection plus récente a pris le relais

  state.webW = img.naturalWidth;
  state.webH = img.naturalHeight;
  state.webScale = state.webW / p.largeur_px;
  canvas.style.width = state.webW + "px";
  canvas.style.height = state.webH + "px";
  overlay.setAttribute("width", state.webW);
  overlay.setAttribute("height", state.webH);
  overlay.setAttribute("viewBox", `0 0 ${p.largeur_px} ${p.hauteur_px}`);

  await loadRegions(id);
  if (gen !== plancheGen) return;
  fitView();
  renderPanel();
}

async function loadRegions(plancheId) {
  const gen = plancheGen;
  const rows = await apiGet(`/api/planches/${plancheId}/regions`);
  if (gen !== plancheGen) return;   // planche changée pendant le fetch → ne pas écraser
  state.regions = rows.map((r) => ({
    ...r,
    annotee: !!r.annotee,
    nb_enfants: r.nb_enfants || 0,
  }));
  state.regionsById = new Map(state.regions.map((r) => [r.id, r]));
  if (state.selectedId != null && !state.regionsById.has(state.selectedId))
    state.selectedId = null;                 // la sélection a été supprimée (re-détection)
  renderOverlay();
  updateStatus();
  renderPanel();                             // rafraîchit l'arbre
}

/* ===================================================================
   Transform (pan / zoom)
   =================================================================== */
function applyTransform() {
  canvas.style.transform =
    `translate(${state.tx}px, ${state.ty}px) scale(${state.zoom})`;
  $("#zoom-level").textContent = Math.round(state.zoom * 100) + " %";
  $("#stat-zoom").textContent = "Zoom " + Math.round(state.zoom * 100) + " %";
  requestAnimationFrame(updateOverlayScale);
}

function fitView() {
  const r = stage.getBoundingClientRect();
  if (!state.webW) return;
  state.zoom = Math.min(r.width / state.webW, r.height / state.webH) * 0.95;
  state.tx = (r.width - state.webW * state.zoom) / 2;
  state.ty = (r.height - state.webH * state.zoom) / 2;
  applyTransform();
}

function zoomAt(sx, sy, factor) {
  const z2 = Math.min(40, Math.max(0.02, state.zoom * factor));
  const cx = (sx - state.tx) / state.zoom;
  const cy = (sy - state.ty) / state.zoom;
  state.tx = sx - cx * z2;
  state.ty = sy - cy * z2;
  state.zoom = z2;
  applyTransform();
}

/* Échelle écran (px écran pour 1 unité master) via le CTM courant. */
function screenScale() {
  const ctm = overlay.getScreenCTM();
  return ctm ? ctm.a : state.webScale * state.zoom;
}

function clientToMaster(evt) {
  const ctm = overlay.getScreenCTM();
  if (!ctm) return { x: 0, y: 0 };
  const pt = overlay.createSVGPoint();
  pt.x = evt.clientX;
  pt.y = evt.clientY;
  const p = pt.matrixTransform(ctm.inverse());
  return { x: p.x, y: p.y };
}

/* ===================================================================
   Rendu de l'overlay SVG
   =================================================================== */
function svg(tag, attrs) {
  const el = document.createElementNS(SVGNS, tag);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  return el;
}

function renderOverlay() {
  overlay.innerHTML = "";
  if (!state.planche) return;

  // Toutes les régions de la planche (cases + bulles + enfants), distinguées
  // par la couleur de contour selon le type.
  const gRegions = svg("g", { id: "regions-group" });
  for (const r of state.regions) {
    const cls = ["region", "region-" + r.type];   // couleur de contour = type
    if (r.annotee) cls.push("annotee");
    if (r.id === state.selectedId) cls.push("selected");
    const rect = svg("rect", {
      x: r.x, y: r.y, width: r.w, height: r.h,
      class: cls.join(" "), "data-id": r.id,
    });
    gRegions.appendChild(rect);
    const label = svg("text", {
      x: r.x + 4, y: r.y + LABEL_PX + 2,
      class: "region-label", "data-label-for": r.id,
    });
    label.textContent = regionLabel(r);
    gRegions.appendChild(label);
  }
  overlay.appendChild(gRegions);

  if (state.mode === "edition" && state.selectedId != null) renderHandles();
  updateOverlayScale();
}

function renderHandles() {
  let g = overlay.querySelector("#handles-group");
  if (g) g.remove();
  const r = state.regionsById.get(state.selectedId);
  if (!r) return;

  g = svg("g", { id: "handles-group" });
  const s = HANDLE_PX / screenScale();
  const pts = [
    ["nw", r.x, r.y], ["n", r.x + r.w / 2, r.y], ["ne", r.x + r.w, r.y],
    ["e", r.x + r.w, r.y + r.h / 2], ["se", r.x + r.w, r.y + r.h],
    ["s", r.x + r.w / 2, r.y + r.h], ["sw", r.x, r.y + r.h],
    ["w", r.x, r.y + r.h / 2],
  ];
  for (const [dir, px, py] of pts) {
    g.appendChild(svg("rect", {
      x: px - s / 2, y: py - s / 2, width: s, height: s,
      class: "handle", "data-handle": dir,
    }));
  }
  overlay.appendChild(g);
}

/* Met à jour les tailles dépendantes du zoom (poignées, libellés). */
function updateOverlayScale() {
  if (!state.planche) return;
  const labelSize = LABEL_PX / screenScale();
  overlay.querySelectorAll(".region-label").forEach((t) =>
    t.setAttribute("font-size", labelSize));
  if (state.mode === "edition" && state.selectedId != null) renderHandles();
}

/* ===================================================================
   Sélection de région
   =================================================================== */
function selectRegion(id, reveal = true) {
  flushSave();
  state.selectedId = id;
  // F6 : la navigation clavier (flèches) passe reveal=false → ne pas re-déplier l'arbre à
  // chaque cran (le repli manuel des cases est respecté). Un clic/deep-link, lui, révèle.
  if (reveal) revealInTree(id);
  renderOverlay();
  renderPanel();
  if (state.mode === "annotation" && id != null) loadAnnotation(id);
}

/* Déplie les ancêtres d'une région dans l'arbre, pour qu'une sélection faite
   depuis l'image ou au clavier reste visible même si sa case est repliée. */
function revealInTree(id) {
  const set = state.collapsedNodes;
  if (!set || !set.size || id == null) return;
  const seen = new Set();
  let r = state.regionsById.get(id);
  while (r && r.parent_id != null && !seen.has(r.id)) {
    seen.add(r.id);
    set.delete(r.parent_id);
    r = state.regionsById.get(r.parent_id);
  }
}

function selectedRegion() {
  return state.selectedId != null ? state.regionsById.get(state.selectedId) : null;
}

/* Remplit le sélecteur de parent (cases de la planche, hors soi-même + descendants). */
function renderParentOptions(r) {
  const sel = $("#region-parent");
  if (!sel) return;
  const exclude = descendantIds(r.id);
  exclude.add(r.id);
  const cases = state.regions
    .filter((c) => c.type === "case" && !exclude.has(c.id))
    .sort((a, b) => (a.ordre || 0) - (b.ordre || 0) || a.id - b.id);
  sel.innerHTML = '<option value="">— aucun (planche) —</option>' +
    cases.map((c) => `<option value="${c.id}">case #${c.id}</option>`).join("");
  sel.value = r.parent_id != null ? String(r.parent_id) : "";
}

/* ===================================================================
   Panneau droit
   =================================================================== */
/* Reflète album/planche/région dans l'URL (replaceState : sans polluer l'historique)
   → recharger la page rouvre exactement au même endroit (cf. applyDeepLink). */
function syncUrl() {
  const p = new URLSearchParams();
  if (state.albumId) p.set("album", state.albumId);
  if (state.planche) p.set("planche", state.planche.id);
  if (state.selectedId != null) p.set("region", state.selectedId);
  if (RETOUR) p.set("retour", RETOUR);   // préservé : le ← Retour survit au reload
  const qs = p.toString();
  history.replaceState(null, "", qs ? "?" + qs : location.pathname);
}

/* Bouton « ← Retour » : ramène à la surface d'analyse d'origine (Recherche /
   Exploration) via le `retour` reçu dans l'URL ; à défaut, history.back() si l'on
   vient d'une autre page de l'app. Masqué s'il n'y a nulle part où revenir.
   Calqué sur recherche.js (même comportement sur toutes les surfaces). */
function setupBack() {
  const back = $("#back-link");
  if (!back) return;
  let target = RETOUR;
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

function renderPanel() {
  const hasPlanche = !!state.planche;
  const r = selectedRegion();
  syncUrl();
  $("#panel-empty").hidden = hasPlanche;     // l'invite ne sert que sans planche
  $("#panel-tree").hidden = !hasPlanche;
  $("#panel-content").hidden = !r;
  if (hasPlanche) renderTree();
  renderPlancheLock();
  renderBreadcrumb();
  if (!r) return;

  const cit = r.citation;
  $("#region-citation").innerHTML = cit
    ? escapeHtml(cit.texte) + (cit.global != null
        ? ` <span class="muted small" title="rang de la case dans l'album (récit)">${cit.global}/${cit.total}</span>`
        : "")
    : "—";
  $("#region-id").textContent = "#" + r.id;
  $("#region-type").value = r.type;
  $("#region-source").textContent = r.source;
  renderParentOptions(r);   // « Rattachée à » : visible dès qu'une région est sélectionnée

  $("#panel-edition").hidden = state.mode !== "edition";
  $("#panel-annotation").hidden = state.mode !== "annotation";

  $("#coord-x").value = r.x;
  $("#coord-y").value = r.y;
  $("#coord-w").value = r.w;
  $("#coord-h").value = r.h;

  $("#panel-ocr").hidden = !r.ocr_texte;
  if (r.ocr_texte) $("#ocr-text").textContent = r.ocr_texte;

  renderGrammaire(r);
}

/* ===================================================================
   Grammaire : analyse spaCy par token — LECTURE d'abord, édition au CLIC.
   Lignes compactes (mot · POS · lemme) colorées par provenance ; cliquer une
   ligne l'ouvre en éditeur (un seul à la fois, sauvegarde auto à la fermeture).
   Filtres : mots de contenu / à réviser. Valeur saisie = OVERRIDE ; vide = auto.
   =================================================================== */
const UPOS = ["ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN", "NUM",
              "PART", "PRON", "PROPN", "PUNCT", "SCONJ", "SYM", "VERB", "X"];
const PROV_LABEL = { auto: "auto", corrige: "corrigé", valide: "validé" };
const CONTENU_POS = new Set(["NOUN", "PROPN", "VERB", "ADJ", "ADV", "INTJ"]);
let gramEditor = null;   // éditeur ouvert : {ordre, lem, pos, mor, orig}

function gel(tag, cls, txt) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt != null) e.textContent = txt;
  return e;
}

async function renderGrammaire(r) {
  const wrap = $("#panel-grammaire");
  if (!wrap) return;
  // changer de région applique d'abord l'éditeur ouvert (sur l'ancienne région)
  if (state.gramRegion && (!r || r.id !== state.gramRegion)) await applyOpenEditor();
  if (!r || !r.ocr_texte) { wrap.hidden = true; state.gramRegion = null; return; }
  const rid = r.id;
  let toks;
  try { toks = await apiGet(`/api/regions/${rid}/tokens`); }
  catch (e) { wrap.hidden = true; return; }
  if (state.selectedId !== rid) return;     // anti-course : sélection changée entre-temps
  wrap.hidden = false;
  state.gramRegion = rid;
  state.gramTokens = toks;
  state.gramOpen = null;
  state.gramFilters = state.gramFilters || { contenu: false, arevoir: false };
  $("#gram-validate").onclick = validerGrammaire;
  const fc = $("#gram-f-contenu"), fa = $("#gram-f-arevoir");
  fc.checked = state.gramFilters.contenu; fa.checked = state.gramFilters.arevoir;
  fc.onchange = () => { state.gramFilters.contenu = fc.checked; renderGramList(); };
  fa.onchange = () => { state.gramFilters.arevoir = fa.checked; renderGramList(); };
  renderGramList();
}

function gramVisible(t) {
  const f = state.gramFilters;
  if (f.contenu && !CONTENU_POS.has(t.pos)) return false;   // mots de contenu (lexicaux)
  // « À réviser » = pas encore traité : on garde l'auto (les ⚠/dérives s'affichent en
  // auto), on masque corrigé + validé (déjà traités). La liste se vide à mesure du travail.
  if (f.arevoir && t.provenance !== "auto") return false;
  return true;
}

function renderGramList() {
  const box = $("#gram-tokens");
  box.innerHTML = "";
  const toks = state.gramTokens || [];
  if (!toks.length) {
    box.innerHTML = '<div class="muted small">Aucune analyse — relancer l\'indexation NLP.</div>';
    $("#gram-validate").hidden = true;
    return;
  }
  $("#gram-validate").hidden = false;
  const vis = toks.filter(gramVisible);
  if (!vis.length) {
    box.innerHTML = '<div class="muted small">Aucun token ne correspond au filtre.</div>';
    return;
  }
  for (const t of vis)
    box.appendChild(state.gramOpen === t.ordre ? gramEditorRow(t) : gramLine(t));
}

function gramLine(t) {
  const row = gel("div", "gram-line prov-" + t.provenance + (t.a_revoir ? " a-revoir" : ""));
  row.append(gel("span", "gram-mot", t.texte),
             gel("span", "gram-pos-chip", t.pos || "—"),
             gel("span", "gram-lemme-txt", t.lemme || ""));
  const meta = gel("span", "gram-meta");
  meta.appendChild(gel("span", "prov-chip prov-" + t.provenance, PROV_LABEL[t.provenance]));
  if (t.a_revoir) { const w = gel("span", "gram-warn", "⚠"); w.title = "à revérifier"; meta.appendChild(w); }
  if (t.corr_auteur && t.provenance !== "auto") {      // INFRA-2 : qui a corrigé/validé
    const by = gel("span", "gram-auteur", "· " + t.corr_auteur);
    by.title = "Corrigé / validé par " + t.corr_auteur;
    meta.appendChild(by);
  }
  row.appendChild(meta);
  row.title = "Cliquer pour corriger";
  row.onclick = async () => { await applyOpenEditor(); state.gramOpen = t.ordre; renderGramList(); };
  return row;
}

function gramEditorRow(t) {
  const row = gel("div", "gram-edit prov-" + t.provenance + (t.a_revoir ? " a-revoir" : ""));
  const head = gel("div", "gram-edit-head");
  head.append(gel("span", "gram-mot", t.texte),
              gel("span", "prov-chip prov-" + t.provenance, PROV_LABEL[t.provenance]));
  if (t.a_revoir) head.appendChild(gel("span", "gram-warn", "⚠ à revérifier"));
  if (t.corr_auteur && t.provenance !== "auto") {      // INFRA-2 : qui a corrigé/validé
    const by = gel("span", "gram-auteur", "· " + t.corr_auteur);
    by.title = "Corrigé / validé par " + t.corr_auteur;
    head.appendChild(by);
  }

  const lem = document.createElement("input");
  lem.className = "gram-in"; lem.value = t.corr_lemme || "";
  lem.placeholder = "lemme — auto : " + (t.lemme || "—");

  const pos = document.createElement("select");
  pos.className = "gram-in";
  const a = gel("option", null, "POS — auto : " + (t.pos || "—")); a.value = ""; pos.appendChild(a);
  for (const u of UPOS) { const o = gel("option", null, u); o.value = u; pos.appendChild(o); }
  pos.value = t.corr_pos || "";

  const mor = document.createElement("input");
  mor.className = "gram-in"; mor.value = t.corr_morph || "";
  mor.placeholder = "morph (UD) — auto : " + (t.morph || "—");

  const apply = gel("button", "ghost small", "✓ Appliquer");
  apply.onclick = async () => { await applyOpenEditor(); state.gramOpen = null; renderGramList(); };
  const reset = gel("button", "ghost small", "↺ Auto");
  reset.title = "Revenir à l'analyse automatique";
  reset.onclick = async () => { gramEditor = null; await gramSend("DELETE", t.ordre); state.gramOpen = null; renderGramList(); };
  const acts = gel("div", "gram-edit-actions"); acts.append(apply, reset);

  row.append(head, lem, pos, mor, acts);
  gramEditor = { ordre: t.ordre, lem, pos, mor,
                 orig: { lemme: t.corr_lemme || "", pos: t.corr_pos || "", morph: t.corr_morph || "" } };
  return row;
}

async function gramSend(method, ordre, body) {
  const rid = state.gramRegion;
  try {
    state.gramTokens = await apiSend(method, `/api/regions/${rid}/tokens/${ordre}`, body);
  } catch (e) { toast("Grammaire : " + e.message, "error"); }
}

async function applyOpenEditor() {     // sauvegarde l'éditeur ouvert s'il a réellement changé
  const ed = gramEditor; gramEditor = null;
  if (!ed) return;
  const now = { lemme: ed.lem.value.trim(), pos: ed.pos.value, morph: ed.mor.value.trim() };
  if (now.lemme === ed.orig.lemme && now.pos === ed.orig.pos && now.morph === ed.orig.morph) return;
  const vide = !now.lemme && !now.pos && !now.morph;       // plus d'override → retour auto
  await gramSend(vide ? "DELETE" : "PUT", ed.ordre,
                 vide ? undefined : { lemme: now.lemme || null, pos: now.pos || null, morph: now.morph || null });
}

async function validerGrammaire() {
  const rid = state.gramRegion;
  await applyOpenEditor();
  try {
    state.gramTokens = await apiSend("POST", `/api/regions/${rid}/grammaire/valider`);
    state.gramOpen = null;
    renderGramList();
    toast("Grammaire de la région validée", "success");
  } catch (e) { toast("Validation : " + e.message, "error"); }
}


/* Séquence de lecture globale : parcours en profondeur de l'arbre, chaque niveau
   trié par `ordre` (rang per-niveau). Reconstruit la lecture « case par case »
   (case, puis ses bulles, puis case suivante…) à partir des rangs locaux. Sert
   à la transcription et à la navigation au clavier. */
function readingSequence() {
  const byParent = new Map();
  for (const r of state.regions) {
    // Repli défensif : un parent absent (orphelin) est rattaché à la racine,
    // sinon la région disparaîtrait de la séquence/transcription/navigation.
    const k = (r.parent_id != null && state.regionsById.has(r.parent_id)) ? r.parent_id : "root";
    (byParent.get(k) || byParent.set(k, []).get(k)).push(r);
  }
  const sortSibs = (a) => a.sort((x, y) => (x.ordre || 0) - (y.ordre || 0) || x.id - y.id);
  const out = [];
  const walk = (key) => {
    const kids = byParent.get(key);
    if (!kids) return;
    for (const r of sortSibs(kids)) { out.push(r); walk(r.id); }
  };
  walk("root");
  return out;
}

/* ---- Glisser-déposer dans l'arbre : rattacher une région à une case ----
   On peut faire glisser n'importe quel nœud de région et le déposer sur une
   CASE (→ rattachement) ou sur la racine « Planche » (→ détachement). Garde
   anti-cycle : on n'autorise pas le dépôt sur soi-même ou un de ses descendants. */
function canReparent(draggedId, targetParentId) {
  if (draggedId == null || targetParentId === draggedId) return false;
  if (targetParentId != null && descendantIds(draggedId).has(targetParentId)) return false;
  return true;
}

function treeDraggable(node, id) {
  node.draggable = true;
  node.addEventListener("dragstart", (e) => {
    state.dragId = id;
    node.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(id));
  });
  node.addEventListener("dragend", () => {
    state.dragId = null;
    node.classList.remove("dragging");
    // Filet de sécurité : si le drag est annulé (Échap) au-dessus d'une cible,
    // son dragleave/drop ne se déclenche pas → on purge tout surlignage résiduel.
    document.querySelectorAll("#tree .drop-target")
      .forEach((n) => n.classList.remove("drop-target"));
  });
}

function treeDropTarget(node, targetParentId) {
  node.addEventListener("dragover", (e) => {
    if (!canReparent(state.dragId, targetParentId)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    node.classList.add("drop-target");
  });
  node.addEventListener("dragleave", (e) => {
    // Ne retire le surlignage que si on quitte vraiment le nœud (pas en entrant
    // dans un de ses sous-éléments → évite le scintillement).
    if (!node.contains(e.relatedTarget)) node.classList.remove("drop-target");
  });
  node.addEventListener("drop", (e) => {
    e.preventDefault();
    node.classList.remove("drop-target");
    const id = state.dragId;
    state.dragId = null;
    if (!canReparent(id, targetParentId)) return;
    const r = state.regionsById.get(id);
    if (r && (r.parent_id ?? null) !== targetParentId) {
      patchRegion(id, { parent_id: targetParentId });
      toast(targetParentId == null
        ? `Détachée (niveau planche)`
        : `Rattachée à case #${targetParentId}`);
    }
  });
}

/* Arbre complet de la planche : planche → cases → bulles (+ bulles orphelines).
   Structure DOM imbriquée (groupes) → lignes de guidage par bordure gauche.
   La région courante est mise en évidence ; clic sur un nœud = sélection +
   recentrage ; clic sur le caret = plie/déplie la case ; glisser = rattacher. */
function renderTree() {
  const box = $("#tree");
  const prevScroll = box.scrollTop;   // préserve la position de défilement (re-rendu fréquent)
  box.innerHTML = "";
  if (!state.planche) return;

  // Regroupe les régions par parent ("root" = enfants directs de la planche).
  const byParent = new Map();
  for (const rg of state.regions) {
    // Repli défensif : un parent absent (orphelin) est rattaché à la racine,
    // sinon la région serait invisible dans l'arbre tout en restant dessinée.
    const key = (rg.parent_id != null && state.regionsById.has(rg.parent_id)) ? rg.parent_id : "root";
    (byParent.get(key) || byParent.set(key, []).get(key)).push(rg);
  }
  const sorted = (arr) =>
    arr.sort((a, b) => (a.ordre || 0) - (b.ordre || 0) || a.id - b.id);
  const collapsed = state.collapsedNodes || (state.collapsedNodes = new Set());

  // Nœud racine : la planche (clic = vue d'ensemble / niveau planche).
  const root = document.createElement("div");
  root.className = "tnode tnode-root" + (state.selectedId == null ? " current" : "");
  root.innerHTML =
    `<span class="tn-caret tn-spacer"></span>` +
    `<span class="tn-ico"></span>` +
    `<span class="tn-label">Planche ${state.planche.numero}</span>` +
    `<span class="tn-count">${state.regions.length}</span>`;
  root.onclick = deselect;
  treeDropTarget(root, null);   // déposer sur la planche = détacher
  box.appendChild(root);

  const buildGroup = (parentKey) => {
    const kids = byParent.get(parentKey);
    if (!kids) return null;
    const group = document.createElement("div");
    group.className = "tgroup";
    for (const rg of sorted(kids)) {
      const item = document.createElement("div");
      item.className = "titem";
      const hasKids = byParent.has(rg.id);
      const isCollapsed = collapsed.has(rg.id);
      const node = document.createElement("div");
      node.className = "tnode tnode-" + rg.type +
        (rg.id === state.selectedId ? " current" : "") +
        (rg.annotee ? " is-annotee" : "");
      const full = (rg.ocr_texte || "").replace(/\s+/g, " ").trim();
      const txt = full.slice(0, 34);
      // Secondaire : conteneur → avancement OCR (bulles transcrites / total) ;
      // région de texte → extrait OCR ; sinon un espaceur vide (aligne le ✓).
      let meta;
      if (hasKids) {
        const kids = byParent.get(rg.id);
        const textKids = kids.filter((k) => TEXT_TYPES.has(k.type));
        if (textKids.length) {
          const done = textKids.filter((k) => (k.ocr_texte || "").trim()).length;
          const cls = done === textKids.length ? "done" : done ? "partial" : "none";
          meta = `<span class="tn-prog tn-prog-${cls}" ` +
                 `title="${done}/${textKids.length} bulles avec texte OCR">${done}/${textKids.length}</span>`;
        } else {
          meta = `<span class="tn-prog tn-prog-none">${kids.length}</span>`;
        }
      } else {
        meta = `<span class="tn-txt">${txt ? escapeHtml(txt) + (full.length > 34 ? "…" : "") : ""}</span>`;
      }
      // Contrôles de déplacement, seulement sur le nœud courant (évite le bruit).
      const moveCtrls = rg.id === state.selectedId
        ? `<span class="tn-move">` +
            `<button class="tn-mv" data-mv="haut" title="Monter (Alt+↑)">▲</button>` +
            `<button class="tn-mv" data-mv="bas" title="Descendre (Alt+↓)">▼</button>` +
          `</span>`
        : "";
      node.innerHTML =
        (hasKids
          ? `<span class="tn-caret" data-fold="${rg.id}">${isCollapsed ? "▸" : "▾"}</span>`
          : `<span class="tn-caret tn-spacer"></span>`) +
        `<span class="tn-dot"></span>` +
        `<span class="tn-label">${rg.type}</span>` +
        `<span class="tn-id mono">#${rg.id}</span>` +
        meta +
        (rg.annotee ? `<span class="tn-check">✓</span>` : "") +
        moveCtrls;
      node.onclick = (e) => {
        const mv = e.target.closest("[data-mv]");
        if (mv) { e.stopPropagation(); moveRegion(rg.id, mv.dataset.mv); return; }
        const fold = e.target.closest("[data-fold]");
        if (fold) {
          const id = Number(fold.dataset.fold);
          collapsed.has(id) ? collapsed.delete(id) : collapsed.add(id);
          renderTree();
          return;
        }
        selectAndCenter(rg.id);
      };
      node.onmouseenter = () => highlightRegion(rg.id);
      node.onmouseleave = () => highlightRegion(null);
      treeDraggable(node, rg.id);                       // glisser pour rattacher
      if (rg.type === "case") treeDropTarget(node, rg.id);   // déposer ici = enfant de la case
      item.appendChild(node);
      if (hasKids && !isCollapsed) {
        const sub = buildGroup(rg.id);
        if (sub) item.appendChild(sub);
      }
      group.appendChild(item);
    }
    return group;
  };
  const top = buildGroup("root");
  if (top) box.appendChild(top);
  box.scrollTop = prevScroll;
}

/* Sélectionne une région depuis l'arbre puis recentre la vue dessus. */
function selectAndCenter(id) {
  if (!state.regionsById.get(id)) return false;   // F5 : région inexistante → diagnostic possible
  selectRegion(id);
  centerOnRegion(id);
  return true;
}

function centerOnRegion(id) {
  const r = state.regionsById.get(id);
  if (!r || !state.webW) return;
  const rect = stage.getBoundingClientRect();
  // Zoom pour que la région occupe ~55 % du stage, borné (pas de sur-zoom).
  const fit = Math.min(rect.width / (r.w * state.webScale),
                       rect.height / (r.h * state.webScale)) * 0.55;
  state.zoom = Math.min(40, Math.max(0.02, Math.min(fit, 8)));
  const cx = (r.x + r.w / 2) * state.webScale;
  const cy = (r.y + r.h / 2) * state.webScale;
  state.tx = rect.width / 2 - cx * state.zoom;
  state.ty = rect.height / 2 - cy * state.zoom;
  applyTransform();
}

/* Survol d'un nœud de l'arbre : halo sur la région dans l'image, sans la
   sélectionner ni recentrer (id=null pour retirer la surbrillance). */
function highlightRegion(id) {
  overlay.querySelectorAll(".region.hover-hi").forEach((el) => el.classList.remove("hover-hi"));
  if (id == null) return;
  const rect = overlay.querySelector(`rect.region[data-id="${id}"]`);
  if (rect) rect.classList.add("hover-hi");
}

/* Plier / déplier toutes les cases (tout nœud ayant des enfants). */
function collapseAllTree() {
  const set = state.collapsedNodes || (state.collapsedNodes = new Set());
  set.clear();
  for (const r of state.regions) if (r.parent_id != null) set.add(r.parent_id);
  renderTree();
}
function expandAllTree() {
  state.collapsedNodes = new Set();
  renderTree();
}

/* Déplace la région d'un cran parmi ses frères ('haut' / 'bas'). */
async function moveRegion(id, sens) {
  if (id == null || !state.planche) return;
  try {
    const res = await apiSend("POST", `/api/regions/${id}/deplacer`, { sens });
    if (res && res.moved === false) { toast("Déjà en bout de liste", ""); return; }
    await loadRegions(state.planche.id);   // la fratrie a été re-rangée
  } catch (e) { toast("Déplacement : " + e.message, "error"); }
}

/* Recalcule l'ordre de lecture automatique de toute la planche. */
async function recalcOrder() {
  if (!state.planche) return;
  try {
    await apiSend("POST", `/api/planches/${state.planche.id}/reordonner`);
    await loadRegions(state.planche.id);
    toast("Ordre de lecture recalculé", "success");
  } catch (e) { toast("Réordonnancement : " + e.message, "error"); }
}

/* Désélectionne la région courante (retour au niveau planche). */
function deselect() {
  flushSave();
  state.selectedId = null;
  renderOverlay();
  renderPanel();
}

function renderBreadcrumb() {
  const bc = $("#breadcrumb");
  bc.innerHTML = "";
  if (!state.planche) return;
  const root = document.createElement("a");
  root.textContent = `Planche ${state.planche.numero}`;
  root.onclick = deselect;
  bc.appendChild(root);
}

/* ===================================================================
   Modes
   =================================================================== */
function setMode(mode) {
  flushSave();
  if (state.mode === "transcription" && mode !== "transcription") trSaveFlush();
  state.mode = mode;
  document.querySelectorAll(".mode-btn").forEach((b) => {
    const on = b.dataset.mode === mode;
    b.classList.toggle("active", on);
    b.setAttribute("aria-pressed", String(on));   // état exposé aux lecteurs d'écran
  });
  stage.classList.toggle("mode-edition", mode === "edition");
  const label = { navigation: "Navigation", edition: "Édition",
                  annotation: "Annotation", transcription: "Transcription" }[mode];
  $("#stat-mode").textContent = "Mode : " + label;
  $("#transcription").hidden = mode !== "transcription";
  renderOverlay();
  renderPanel();
  if (mode === "annotation" && state.selectedId != null) loadAnnotation(state.selectedId);
  if (mode === "transcription") enterTranscription();
}

/* ===================================================================
   Annotation (tags + note, sauvegarde auto)
   =================================================================== */
async function loadAnnotation(regionId) {
  try {
    const ann = await apiGet(`/api/regions/${regionId}/annotation`);
    state.currentTags = ann.tags.map((t) => t.label);
    $("#note-input").value = ann.note || "";
    renderTagChips();
    setSaveState("saved");
  } catch (e) {
    // F7 : sur échec, VIDER note + tags — sinon un scheduleSave ultérieur écrirait
    // l'annotation de la région PRÉCÉDENTE (restée dans #note-input) sur celle-ci.
    toast("Erreur chargement annotation : " + e.message, "error");
    state.currentTags = [];
    $("#note-input").value = "";
    renderTagChips();
    setSaveState("");
  }
  loadLocuteur(regionId);   // panneau Locuteur (bulles) — indépendant de l'annotation
  loadPerso(regionId);      // panneau Personnage (boîtes personnage) — identité + profil
  loadSituation(regionId);  // panneau Situation (cases)
}

function renderTagChips() {
  const box = $("#tag-chips");
  box.innerHTML = "";
  for (const label of state.currentTags) {
    const chip = document.createElement("span");
    chip.className = "tag-chip";
    const v = state.tagVocab.find((t) => t.label === label);
    if (v && v.couleur) chip.style.borderColor = v.couleur;
    chip.innerHTML = `<span>${escapeHtml(label)}</span><span class="x">×</span>`;
    chip.querySelector(".x").onclick = () => { removeTag(label); };
    box.appendChild(chip);
  }
}

function addTag(label) {
  label = label.trim().toLowerCase().replace(/\s+/g, " ");
  if (!label || state.currentTags.includes(label)) return;
  state.currentTags.push(label);
  renderTagChips();
  scheduleSave();
}
function removeTag(label) {
  state.currentTags = state.currentTags.filter((t) => t !== label);
  renderTagChips();
  scheduleSave();
}

function setSaveState(kind) {
  const el = $("#save-state");
  el.className = "save-state " + kind;
  el.textContent = { saving: "Enregistrement…", saved: "Enregistré", "": "" }[kind] || "";
}

function scheduleSave() {
  setSaveState("saving");
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(saveAnnotation, SAVE_DEBOUNCE);
}
function flushSave() {
  if (state.saveTimer) { clearTimeout(state.saveTimer); state.saveTimer = null; saveAnnotation(); }
}

async function saveAnnotation() {
  state.saveTimer = null;
  const id = state.selectedId;
  // F8 : si le timer tombe hors mode annotation (ou sans sélection), NE PAS laisser
  // l'indicateur bloqué sur « Enregistrement… ».
  if (id == null || state.mode !== "annotation") { setSaveState(""); return; }
  const note = $("#note-input").value;
  try {
    await apiSend("PUT", `/api/regions/${id}/annotation`, {
      note, tags: [...state.currentTags],
    });
    const r = state.regionsById.get(id);
    if (r) { r.annotee = !!(note || state.currentTags.length); }
    renderOverlay();
    renderTree();                            // reflète l'état annoté dans l'arbre
    setSaveState("saved");
    await refreshTagVocab();
    updateStatus();
  } catch (e) { toast("Échec de sauvegarde : " + e.message, "error"); }
}

async function refreshTagVocab() {
  try { state.tagVocab = await apiGet("/api/tags"); } catch (_) {}
}

/* ===================================================================
   Mode Transcription (correction rapide de l'OCR, bulle à bulle)
   =================================================================== */
const TEXT_TYPES = new Set(["bulle", "cartouche", "texte"]);

function enterTranscription() {
  if (!state.planche) {
    toast("Sélectionnez une planche", "error");
    setMode("navigation");
    return;
  }
  // Ordre « case par case » via le parcours d'arbre (les rangs `ordre` sont
  // relatifs aux frères, pas globaux).
  state.trRegions = readingSequence().filter((r) => TEXT_TYPES.has(r.type));
  state.trIndex = 0;
  buildTrMini();
  renderTranscription();
}

function buildTrMini() {
  const mini = $("#tr-mini");
  mini.innerHTML = "";
  if (!state.planche) return;
  const im = document.createElement("img");
  im.src = state.planche.url_web;
  mini.appendChild(im);
  const svg = document.createElementNS(SVGNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${state.planche.largeur_px} ${state.planche.hauteur_px}`);
  svg.setAttribute("preserveAspectRatio", "none");
  state.trRegions.forEach((r, i) => {
    const rect = svg.appendChild(document.createElementNS(SVGNS, "rect"));
    rect.setAttribute("x", r.x); rect.setAttribute("y", r.y);
    rect.setAttribute("width", r.w); rect.setAttribute("height", r.h);
    rect.setAttribute("class", "tr-region");
    rect.dataset.i = i;
    rect.onclick = () => { trSaveFlush(); state.trIndex = i; renderTranscription(); };
  });
  mini.appendChild(svg);
}

function renderTranscription() {
  const list = state.trRegions;
  const r = list[state.trIndex];
  $("#tr-progress").textContent = list.length
    ? `Bulle ${state.trIndex + 1} / ${list.length}` : "Aucune région de texte";
  $("#tr-type").textContent = r ? r.type : "";

  // crop NET de la bulle, recadré dans le master côté serveur.
  // Cache-buster sur les coordonnées : si la bbox change (mode Édition), l'URL
  // change → pas de crop périmé servi depuis le cache navigateur.
  const cropImg = $("#tr-crop");
  if (r) cropImg.src = `/api/regions/${r.id}/crop?b=${r.x}-${r.y}-${r.w}-${r.h}`;
  else cropImg.removeAttribute("src");
  // Sans région : MASQUER l'<img> (sinon Chrome affiche l'icône d'image cassée
  // + son cadre pointillé → impression de cadre « dédoublé ») et montrer un message.
  cropImg.hidden = !r;
  $("#tr-empty").hidden = !!r;

  // éditeur
  const ta = $("#tr-text");
  ta.value = r ? (r.ocr_texte || "") : "";
  ta.disabled = !r;
  setTrSave("");

  // surlignage + défilement dans la mini-planche
  const svg = $("#tr-mini svg");
  if (svg) svg.querySelectorAll(".tr-region").forEach((el, i) => {
    const cur = i === state.trIndex;
    el.classList.toggle("current", cur);
    if (cur) el.scrollIntoView({ block: "center", inline: "center" });
  });

  if (r) ta.focus();
}

function trCurrent() { return state.trRegions[state.trIndex]; }

function setTrSave(kind) {
  const el = $("#tr-save");
  el.className = "save-state " + kind;
  el.textContent = { saving: "Enregistrement…", saved: "Enregistré", "": "" }[kind] || "";
}

function trScheduleSave() {
  setTrSave("saving");
  clearTimeout(state.trSaveTimer);
  state.trSaveTimer = setTimeout(trSaveCurrent, SAVE_DEBOUNCE);
}
function trSaveFlush() {
  if (state.trSaveTimer) { clearTimeout(state.trSaveTimer); state.trSaveTimer = null; }
  trSaveCurrent();
}

async function trSaveCurrent() {
  clearTimeout(state.trSaveTimer);   // purge le debounce éventuel (évite refire)
  state.trSaveTimer = null;
  const r = trCurrent();
  if (!r) return;
  const val = $("#tr-text").value;
  if (val === (r.ocr_texte || "")) { setTrSave("saved"); return; }
  try {
    const updated = await apiSend("PUT", `/api/regions/${r.id}`, { ocr_texte: val });
    Object.assign(state.regionsById.get(r.id) || {}, updated);
    r.ocr_texte = val;
    setTrSave("saved");
  } catch (e) { toast("Sauvegarde : " + e.message, "error"); }
}

async function trNext() {
  await trSaveCurrent();
  if (state.trIndex < state.trRegions.length - 1) {
    state.trIndex++; renderTranscription();
  } else if ($("#tr-auto").checked) {
    const idx = state.planches.findIndex((p) => p.id === state.planche.id);
    const next = state.planches[idx + 1];
    if (next) {
      await selectPlanche(next.id);
      enterTranscription();
      toast(`Planche ${next.numero}`, "");
    } else { toast("Dernière planche de l'album", ""); }
  } else { toast("Dernière bulle de la planche", ""); }
}

async function trPrev() {
  await trSaveCurrent();
  if (state.trIndex > 0) { state.trIndex--; renderTranscription(); }
}

function setupTranscription() {
  $("#tr-text").addEventListener("input", trScheduleSave);
  $("#tr-text").addEventListener("keydown", (e) => {
    if ((e.key === "Enter" && (e.ctrlKey || e.metaKey)) ||
        (e.key === "Tab" && !e.shiftKey)) { e.preventDefault(); trNext(); }
    else if (e.key === "Tab" && e.shiftKey) { e.preventDefault(); trPrev(); }
  });
  $("#tr-next").onclick = trNext;
  $("#tr-prev").onclick = trPrev;
  $("#tr-exit").onclick = () => setMode("navigation");
}

/* --- autocomplétion tags --- */
function setupTagInput() {
  const input = $("#tag-input");
  const sug = $("#tag-suggest");
  let activeIdx = -1;

  function close() { sug.hidden = true; activeIdx = -1; }
  function render() {
    const q = input.value.trim().toLowerCase();
    const items = state.tagVocab
      .filter((t) => !state.currentTags.includes(t.label) &&
        (!q || t.label.includes(q)))
      .slice(0, 12);
    sug.innerHTML = "";
    if (!items.length) { close(); return; }
    items.forEach((t, i) => {
      const d = document.createElement("div");
      if (i === activeIdx) d.classList.add("active");
      d.dataset.label = t.label;
      d.innerHTML = `${escapeHtml(t.label)}<span class="freq">${escapeHtml(t.frequence)}</span>`;
      d.onmousedown = (e) => { e.preventDefault(); addTag(t.label); input.value = ""; close(); };
      sug.appendChild(d);
    });
    sug.hidden = false;
  }

  input.addEventListener("input", () => { activeIdx = -1; render(); });
  input.addEventListener("focus", render);
  input.addEventListener("blur", () => setTimeout(close, 150));
  input.addEventListener("keydown", (e) => {
    const items = sug.querySelectorAll("div");
    if (e.key === "ArrowDown") { activeIdx = Math.min(items.length - 1, activeIdx + 1); render(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { activeIdx = Math.max(0, activeIdx - 1); render(); e.preventDefault(); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIdx >= 0 && items[activeIdx]) addTag(items[activeIdx].dataset.label);
      else if (input.value.trim()) addTag(input.value);
      input.value = ""; close();
    } else if (e.key === "Backspace" && !input.value && state.currentTags.length) {
      removeTag(state.currentTags[state.currentTags.length - 1]);
    } else if (e.key === "Escape") { close(); }
  });
}

/* --- Locuteur : qui parle dans la bulle (registre corpus + création à la volée) --- */
async function loadLocuteur(regionId) {
  const sec = $("#loc-section");
  const r = state.regionsById.get(regionId);
  if (!r || r.type !== "bulle") { sec.hidden = true; state.locRegion = null; return; }
  sec.hidden = false;
  state.locRegion = regionId;
  $("#loc-input").value = "";
  $("#loc-suggest").hidden = true;
  renderLocuteur(null);
  try {
    const { locuteur } = await apiGet(`/api/regions/${regionId}/locuteur`);
    if (state.locRegion === regionId) renderLocuteur(locuteur);   // anti-course
  } catch (e) { /* non bloquant */ }
}

function renderLocuteur(loc) {
  const box = $("#loc-current");
  if (!box) return;
  box.innerHTML = "";
  if (loc) {
    const chip = document.createElement("span");
    chip.className = "tag-chip";
    chip.innerHTML = `<span>${escapeHtml(loc.nom)}${loc.serie ? " · " + escapeHtml(loc.serie) : ""}</span>`
      + `<span class="x" title="Retirer le locuteur">×</span>`;
    chip.querySelector(".x").onclick = clearLocuteur;
    box.appendChild(chip);
  } else {
    box.innerHTML = '<span class="muted small">Aucun locuteur</span>';
  }
  // profil du personnage : éditable dès qu'un locuteur est attribué (vaut pour tout le corpus)
  if (persoAttrWidget) persoAttrWidget.load(loc ? `/api/personnages/${loc.id}` : null);
  if (locAlignWidget) locAlignWidget.load(loc ? loc.id : null);   // alignement d'autorité (A5)
}

async function setLocuteur(pid) {
  const rid = state.locRegion;
  if (rid == null) return;
  try {
    const { locuteur } = await apiSend("PUT", `/api/regions/${rid}/locuteur`, { personnage_id: pid });
    if (state.locRegion === rid) renderLocuteur(locuteur);
  } catch (e) { toast("Locuteur : " + e.message, "error"); }
}

async function clearLocuteur() {
  const rid = state.locRegion;
  if (rid == null) return;
  try { await apiSend("DELETE", `/api/regions/${rid}/locuteur`); } catch (e) { return; }
  if (state.locRegion === rid) renderLocuteur(null);
}

/* --- Personnage MONTRÉ : identité d'une boîte personnage (§14, brique (a)). Miroir du
   locuteur, mais pour l'image — même entité, et le profil corpus se règle ICI aussi, donc
   atteignable pour un personnage muet (sans bulle). --- */
async function loadPerso(regionId) {
  const sec = $("#perso-section");
  const r = state.regionsById.get(regionId);
  if (!r || r.type !== "personnage") { sec.hidden = true; state.persoRegion = null; return; }
  sec.hidden = false;
  state.persoRegion = regionId;
  $("#perso-input").value = "";
  $("#perso-suggest").hidden = true;
  renderPerso(null);
  try {
    const { personnage } = await apiGet(`/api/regions/${regionId}/personnage`);
    if (state.persoRegion === regionId) renderPerso(personnage);   // anti-course
  } catch (e) { /* non bloquant */ }
}

function renderPerso(perso) {
  const box = $("#perso-current");
  if (!box) return;
  box.innerHTML = "";
  if (perso) {
    const chip = document.createElement("span");
    chip.className = "tag-chip";
    chip.innerHTML = `<span>${escapeHtml(perso.nom)}${perso.serie ? " · " + escapeHtml(perso.serie) : ""}</span>`
      + `<span class="x" title="Retirer l'identité">×</span>`;
    chip.querySelector(".x").onclick = clearPerso;
    box.appendChild(chip);
  } else {
    box.innerHTML = '<span class="muted small">Non identifié</span>';
  }
  // même profil corpus que par le locuteur, atteignable depuis la boîte (muets compris)
  if (persoBoxAttrWidget) persoBoxAttrWidget.load(perso ? `/api/personnages/${perso.id}` : null);
  if (persoAlignWidget) persoAlignWidget.load(perso ? perso.id : null);   // alignement d'autorité (A5)
}

async function setPerso(pid) {
  const rid = state.persoRegion;
  if (rid == null) return;
  try {
    const { personnage } = await apiSend("PUT", `/api/regions/${rid}/personnage`, { personnage_id: pid });
    if (state.persoRegion === rid) renderPerso(personnage);
  } catch (e) { toast("Personnage : " + e.message, "error"); }
}

async function clearPerso() {
  const rid = state.persoRegion;
  if (rid == null) return;
  try { await apiSend("DELETE", `/api/regions/${rid}/personnage`); } catch (e) { return; }
  if (state.persoRegion === rid) renderPerso(null);
}

/* Autocomplétion « personnage » réutilisable : registre corpus + création à la volée
   (modèle mentions→entités). `onPick(personnageId)` applique le choix — locuteur d'une
   bulle OU identité d'une boîte personnage (§14, brique (a)). Une seule logique pour les
   deux panneaux ; seule l'action finale (onPick) diffère. */
function setupPersoInput(inputSel, sugSel, onPick) {
  const input = $(inputSel), sug = $(sugSel);
  let timer = null, activeIdx = -1, items = [];
  function close() { sug.hidden = true; activeIdx = -1; }
  async function fetchList() {
    const q = input.value.trim();
    let persos = [];
    try { persos = await apiGet("/api/personnages?q=" + encodeURIComponent(q)); }
    catch (e) { persos = []; }
    items = persos.slice(0, 10).map((p) => ({ create: false, id: p.id, nom: p.nom, serie: p.serie }));
    // proposer la CRÉATION si la saisie n'a pas de correspondance exacte (modèle mentions→entités)
    if (q && !persos.some((p) => p.nom.toLowerCase() === q.toLowerCase()))
      items.push({ create: true, nom: q });
    render();
  }
  function render() {
    sug.innerHTML = "";
    if (!items.length) { close(); return; }
    items.forEach((it, i) => {
      const d = document.createElement("div");
      if (i === activeIdx) d.classList.add("active");
      d.innerHTML = it.create
        ? `➕ Créer « ${escapeHtml(it.nom)} »`
        : `${escapeHtml(it.nom)}${it.serie ? `<span class="freq">${escapeHtml(it.serie)}</span>` : ""}`;
      d.onmousedown = (e) => { e.preventDefault(); choose(it); };
      sug.appendChild(d);
    });
    sug.hidden = false;
  }
  async function choose(it) {
    input.value = ""; close();
    if (it.create) {
      try {
        const p = await apiSend("POST", "/api/personnages", { nom: it.nom });
        await onPick(p.id);
      } catch (e) { toast("Création : " + e.message, "error"); }
    } else { await onPick(it.id); }
  }
  input.addEventListener("input", () => { activeIdx = -1; clearTimeout(timer); timer = setTimeout(fetchList, 200); });
  input.addEventListener("focus", fetchList);
  input.addEventListener("blur", () => setTimeout(close, 150));
  input.addEventListener("keydown", (e) => {
    const n = sug.querySelectorAll("div").length;
    if (e.key === "ArrowDown") { activeIdx = Math.min(n - 1, activeIdx + 1); render(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { activeIdx = Math.max(0, activeIdx - 1); render(); e.preventDefault(); }
    else if (e.key === "Enter") {
      e.preventDefault();
      const q = input.value.trim();
      if (activeIdx >= 0 && items[activeIdx]) choose(items[activeIdx]);
      else if (q) {
        const exact = items.find((it) => !it.create && it.nom.toLowerCase() === q.toLowerCase());
        choose(exact || { create: true, nom: q });   // pas de doublon si le nom existe déjà
      }
    } else if (e.key === "Escape") { close(); }
  });
}

/* --- Attributs FACETTÉS & ÉMERGENTS : widget réutilisable (cible 'personnage' ou
   'case'). Saisie « dimension : valeur » → find-or-create la dimension ET la valeur,
   puis affecte. Le vocabulaire n'est pas figé : il émerge de la saisie. --- */
function makeAttributsWidget(ids, cible) {
  const sec = $(ids.section), cur = $(ids.current), input = $(ids.input), sug = $(ids.suggest);
  let target = null, timer = null, activeIdx = -1, items = [];

  async function refresh() {
    cur.innerHTML = "";
    let attrs = [];
    try { attrs = await apiGet(`${target}/attributs`); } catch (e) { return; }
    if (!attrs.length) { cur.innerHTML = '<span class="muted small">Aucun</span>'; return; }
    for (const a of attrs) {
      const chip = document.createElement("span");
      chip.className = "tag-chip";
      chip.innerHTML = `<span><b>${escapeHtml(a.dimension)}</b> : ${escapeHtml(a.valeur)}</span>`
        + `<span class="x" title="Retirer">×</span>`;
      chip.querySelector(".x").onclick = () => remove(a.valeur_id);
      cur.appendChild(chip);
    }
  }
  async function remove(vid) {
    try { await apiSend("DELETE", `${target}/attributs/${vid}`); } catch (e) { return; }
    refresh();
  }
  async function assign(vid) {
    try { await apiSend("PUT", `${target}/attributs`, { valeur_id: vid }); refresh(); }
    catch (e) { toast("Attribut : " + e.message, "error"); }
  }
  async function createAndAssign(dim, val) {
    try {
      const d = await apiSend("POST", "/api/attributs/dimensions", { cible, nom: dim });
      const v = await apiSend("POST", `/api/attributs/dimensions/${d.id}/valeurs`, { valeur: val });
      await assign(v.id);
    } catch (e) { toast("Attribut : " + e.message, "error"); }
  }
  function close() { sug.hidden = true; activeIdx = -1; }
  async function fetchList() {
    const q = input.value.trim();
    let vals = [];
    try { vals = await apiGet("/api/attributs/valeurs?cible=" + cible); } catch (e) { vals = []; }
    items = vals
      .map((v) => ({ create: false, id: v.id, dim: v.dimension, val: v.valeur,
                     label: `${v.dimension} : ${v.valeur}` }))
      .filter((it) => !q || it.label.toLowerCase().includes(q.toLowerCase())).slice(0, 10);
    const i = q.indexOf(":");   // « dimension : valeur » → proposition de création
    if (i > 0) {
      const dim = q.slice(0, i).trim(), val = q.slice(i + 1).trim();
      if (dim && val && !vals.some((v) => v.dimension.toLowerCase() === dim.toLowerCase()
                                       && v.valeur.toLowerCase() === val.toLowerCase()))
        items.push({ create: true, dim, val, label: `➕ ${dim} : ${val}` });
    }
    render();
  }
  function render() {
    sug.innerHTML = "";
    if (!items.length) { close(); return; }
    items.forEach((it, k) => {
      const d = document.createElement("div");
      if (k === activeIdx) d.classList.add("active");
      d.innerHTML = it.create ? escapeHtml(it.label)
        : `${escapeHtml(it.dim)}<span class="freq">${escapeHtml(it.val)}</span>`;
      d.onmousedown = (e) => { e.preventDefault(); choose(it); };
      sug.appendChild(d);
    });
    sug.hidden = false;
  }
  async function choose(it) {
    input.value = ""; close();
    if (it.create) await createAndAssign(it.dim, it.val);
    else await assign(it.id);
  }
  input.addEventListener("input", () => { activeIdx = -1; clearTimeout(timer); timer = setTimeout(fetchList, 200); });
  input.addEventListener("focus", fetchList);
  input.addEventListener("blur", () => setTimeout(close, 150));
  input.addEventListener("keydown", (e) => {
    const n = sug.querySelectorAll("div").length;
    if (e.key === "ArrowDown") { activeIdx = Math.min(n - 1, activeIdx + 1); render(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { activeIdx = Math.max(0, activeIdx - 1); render(); e.preventDefault(); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIdx >= 0 && items[activeIdx]) { choose(items[activeIdx]); return; }
      const q = input.value.trim(), i = q.indexOf(":");   // sans sélection : « dim : val »
      if (i > 0) {
        const dim = q.slice(0, i).trim().toLowerCase(), val = q.slice(i + 1).trim().toLowerCase();
        const exact = items.find((it) => !it.create && it.dim.toLowerCase() === dim && it.val.toLowerCase() === val);
        const create = items.find((it) => it.create);
        if (exact) choose(exact); else if (create) choose(create);
      } else if (items.length === 1) choose(items[0]);
    } else if (e.key === "Escape") { close(); }
  });

  return {
    load(path) {
      target = path;
      if (!path) { sec.hidden = true; return; }
      sec.hidden = false; input.value = ""; close(); refresh();
    },
  };
}

/* --- Alignement d'AUTORITÉ (A5) : widget réutilisable — relie l'ENTITÉ personnage à des
   référentiels externes (Wikidata/VIAF/IdRef…) en `skos:exactMatch`. Saisir une URI l'ajoute
   (source auto-détectée côté serveur) ; les puces ouvrent le référentiel / se retirent. --- */
function makeAlignementWidget(ids) {
  const sec = $(ids.section), cur = $(ids.current), input = $(ids.input);
  let pid = null;
  async function refresh() {
    cur.innerHTML = "";
    let items = [];
    try { items = await apiGet(`/api/personnages/${pid}/alignements`); } catch (e) { return; }
    if (!items.length) { cur.innerHTML = '<span class="muted small">Aucun</span>'; return; }
    for (const a of items) {
      const chip = document.createElement("span");
      chip.className = "tag-chip";
      const lbl = a.source ? escapeHtml(a.source) : "lien";
      chip.innerHTML =
        `<a href="${escapeHtml(a.uri)}" target="_blank" rel="noopener noreferrer" `
        + `title="${escapeHtml(a.uri)}">${lbl} ↗</a>`
        + `<span class="x" title="Retirer l'alignement">×</span>`;
      chip.querySelector(".x").onclick = () => remove(a.id);
      cur.appendChild(chip);
    }
  }
  async function remove(aid) {
    try { await apiSend("DELETE", `/api/personnages/${pid}/alignements/${aid}`); }
    catch (e) { toast("Alignement : " + e.message, "error"); return; }
    refresh();
  }
  async function add() {
    const uri = input.value.trim();
    if (!uri) return;
    try { await apiSend("POST", `/api/personnages/${pid}/alignements`, { uri }); input.value = ""; refresh(); }
    catch (e) { toast("Alignement : " + e.message, "error"); }
  }
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); add(); } });
  return {
    load(personnageId) {
      pid = personnageId;
      if (!personnageId) { sec.hidden = true; return; }
      sec.hidden = false; input.value = ""; refresh();
    },
  };
}

let sitWidget = null, persoAttrWidget = null, persoBoxAttrWidget = null;
let locAlignWidget = null, persoAlignWidget = null;
function setupAttributs() {
  sitWidget = makeAttributsWidget(
    { section: "#situation-section", current: "#sit-current", input: "#sit-input", suggest: "#sit-suggest" }, "case");
  persoAttrWidget = makeAttributsWidget(
    { section: "#perso-attr-section", current: "#perso-attr-current",
      input: "#perso-attr-input", suggest: "#perso-attr-suggest" }, "personnage");
  // 2ᵉ instance : le MÊME profil corpus, mais piloté depuis la boîte personnage (§14 a).
  persoBoxAttrWidget = makeAttributsWidget(
    { section: "#perso-profil-section", current: "#perso-profil-current",
      input: "#perso-profil-input", suggest: "#perso-profil-suggest" }, "personnage");
  // Alignement d'autorité (A5) — deux instances (via le locuteur, via la boîte personnage).
  locAlignWidget = makeAlignementWidget(
    { section: "#loc-align-section", current: "#loc-align-current", input: "#loc-align-input" });
  persoAlignWidget = makeAlignementWidget(
    { section: "#perso-align-section", current: "#perso-align-current", input: "#perso-align-input" });
}

function loadSituation(regionId) {
  const r = state.regionsById.get(regionId);
  if (sitWidget) sitWidget.load(r && r.type === "case" ? `/api/regions/${regionId}` : null);
}

/* ===================================================================
   Édition de région (type, coordonnées, suppression)
   =================================================================== */
async function patchRegion(id, fields) {
  const r = state.regionsById.get(id);
  if (r && r.source === "kumiko" &&
      ("x" in fields || "y" in fields || "w" in fields || "h" in fields || "type" in fields)) {
    fields.source = "corrige";
  }
  try {
    const updated = await apiSend("PUT", `/api/regions/${id}`, fields);
    Object.assign(state.regionsById.get(id), updated);
    renderOverlay();
    renderPanel();
  } catch (e) { toast("Échec mise à jour : " + e.message, "error"); }
}

async function deleteRegion(id) {
  try {
    await apiSend("DELETE", `/api/regions/${id}`);
    // Retire la région et ses descendants localement.
    const toRemove = new Set([id]);
    let changed = true;
    while (changed) {
      changed = false;
      for (const r of state.regions)
        if (r.parent_id != null && toRemove.has(r.parent_id) && !toRemove.has(r.id)) {
          toRemove.add(r.id); changed = true;
        }
    }
    state.regions = state.regions.filter((r) => !toRemove.has(r.id));
    state.regionsById = new Map(state.regions.map((r) => [r.id, r]));
    if (toRemove.has(state.selectedId)) state.selectedId = null;
    renderOverlay(); renderPanel(); updateStatus();
    toast("Région supprimée");
  } catch (e) { toast("Échec suppression : " + e.message, "error"); }
}

/* Plus petite case contenant le point (cx, cy) en px master, sinon null.
   Sert au rattachement hiérarchique d'une région dessinée à la main. */
function caseContaining(cx, cy, excludeId) {
  const hits = state.regions.filter((r) =>
    r.type === "case" && r.id !== excludeId &&
    cx >= r.x && cx <= r.x + r.w && cy >= r.y && cy <= r.y + r.h);
  if (!hits.length) return null;
  return hits.reduce((a, b) => ((a.w * a.h) <= (b.w * b.h) ? a : b)).id;
}

/* Ids de tous les descendants d'une région (pour les exclure des parents). */
function descendantIds(id) {
  const out = new Set();
  const stack = [id];
  while (stack.length) {
    const pid = stack.pop();
    for (const r of state.regions)
      if (r.parent_id === pid && !out.has(r.id)) { out.add(r.id); stack.push(r.id); }
  }
  return out;
}

async function createRegion(x, y, w, h) {
  // Rattachement par géométrie : dessinée DANS une case → bulle enfant de cette
  // case ; sinon → case de premier niveau. Le type reste corrigeable en Édition.
  const parent = caseContaining(x + w / 2, y + h / 2);
  const type = parent == null ? "case" : "bulle";
  try {
    const created = await apiSend("POST", `/api/planches/${state.planche.id}/regions`, {
      type, x: Math.round(x), y: Math.round(y),
      w: Math.round(w), h: Math.round(h),
      parent_id: parent, source: "manuel",
    });
    created.annotee = false; created.nb_enfants = 0;
    state.regions.push(created);
    state.regionsById.set(created.id, created);
    renderOverlay(); updateStatus();
    selectRegion(created.id);
  } catch (e) { toast("Échec création : " + e.message, "error"); }
}

/* ===================================================================
   Interactions souris sur le stage
   =================================================================== */
let drag = null;  // { kind, ... }

stage.addEventListener("wheel", (e) => {
  e.preventDefault();
  const r = stage.getBoundingClientRect();
  zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1.12 : 1 / 1.12);
}, { passive: false });

stage.addEventListener("mousedown", (e) => {
  if (!state.planche) return;
  const isMiddle = e.button === 1;
  const target = e.target;

  // Pan : molette enfoncée (tout mode) ou clic gauche sur fond en navigation.
  if (isMiddle || (e.button === 0 && state.mode === "navigation" && !target.closest(".region"))) {
    drag = { kind: "pan", sx: e.clientX, sy: e.clientY, tx: state.tx, ty: state.ty };
    stage.classList.add("panning");
    e.preventDefault();
    return;
  }
  if (e.button !== 0) return;

  // Poignée de redimensionnement (mode édition).
  if (target.classList.contains("handle")) {
    const r = selectedRegion();
    if (!r) return;                       // poignée résiduelle sans sélection
    drag = { kind: "resize", dir: target.dataset.handle, start: clientToMaster(e),
             orig: { x: r.x, y: r.y, w: r.w, h: r.h } };
    return;
  }

  const hit = target.closest(".region");
  if (state.mode === "navigation") {
    if (hit) selectRegion(Number(hit.dataset.id));
    return;
  }
  if (state.mode === "annotation") {
    if (hit) selectRegion(Number(hit.dataset.id));
    return;
  }
  if (state.mode === "edition") {
    if (e.shiftKey) {
      // Maj+glisser : forcer un nouveau tracé même au-dessus d'une case
      // (sinon le rect de la case intercepte le clic) → sous-région par géométrie.
      drag = { kind: "draw", start: clientToMaster(e) };
    } else if (hit && Number(hit.dataset.id) === state.selectedId) {
      // déplacer la région sélectionnée
      const r = selectedRegion();
      drag = { kind: "move", start: clientToMaster(e), orig: { x: r.x, y: r.y } };
    } else if (hit) {
      selectRegion(Number(hit.dataset.id));
    } else {
      // dessiner une nouvelle région (sur le fond)
      drag = { kind: "draw", start: clientToMaster(e) };
    }
  }
});

window.addEventListener("mousemove", (e) => {
  // coordonnées master sous le curseur
  if (state.planche) {
    const m = clientToMaster(e);
    if (m.x >= 0 && m.y >= 0)
      $("#stat-coords").textContent = `${Math.round(m.x)}, ${Math.round(m.y)} px`;
  }
  if (!drag) return;

  if (drag.kind === "pan") {
    state.tx = drag.tx + (e.clientX - drag.sx);
    state.ty = drag.ty + (e.clientY - drag.sy);
    applyTransform();
    return;
  }

  const p = clientToMaster(e);
  if (drag.kind === "draw") {
    let dr = overlay.querySelector("#draw-rect");
    if (!dr) { dr = svg("rect", { id: "draw-rect", class: "draw-rect" }); overlay.appendChild(dr); }
    const x = Math.min(drag.start.x, p.x), y = Math.min(drag.start.y, p.y);
    dr.setAttribute("x", x); dr.setAttribute("y", y);
    dr.setAttribute("width", Math.abs(p.x - drag.start.x));
    dr.setAttribute("height", Math.abs(p.y - drag.start.y));
  } else if (drag.kind === "move") {
    const r = selectedRegion();
    r.x = Math.round(drag.orig.x + (p.x - drag.start.x));
    r.y = Math.round(drag.orig.y + (p.y - drag.start.y));
    liveUpdateSelected();
  } else if (drag.kind === "resize") {
    resizeFrom(drag, p);
    liveUpdateSelected();
  }
});

window.addEventListener("mouseup", (e) => {
  stage.classList.remove("panning");
  if (!drag) return;
  const d = drag; drag = null;

  if (d.kind === "draw") {
    const dr = overlay.querySelector("#draw-rect");
    if (dr) {
      const w = +dr.getAttribute("width"), h = +dr.getAttribute("height");
      const x = +dr.getAttribute("x"), y = +dr.getAttribute("y");
      dr.remove();
      if (w > 4 && h > 4) createRegion(x, y, w, h);
    }
  } else if (d.kind === "move" || d.kind === "resize") {
    const r = selectedRegion();
    if (r) patchRegion(r.id, { x: r.x, y: r.y, w: r.w, h: r.h });
  }
});

const MIN_REGION = 5;   // taille minimale d'une région (px master), cohérente avec le dessin

function resizeFrom(d, p) {
  const r = selectedRegion();
  if (!r) return;
  let { x, y, w, h } = d.orig;
  const dx = p.x - d.start.x, dy = p.y - d.start.y;
  if (d.dir.includes("e")) w = d.orig.w + dx;
  if (d.dir.includes("s")) h = d.orig.h + dy;
  if (d.dir.includes("w")) {            // bord DROIT ancré
    const right = d.orig.x + d.orig.w;
    x = d.orig.x + dx; w = right - x;
    if (w < MIN_REGION) { w = MIN_REGION; x = right - MIN_REGION; }
  }
  if (d.dir.includes("n")) {            // bord BAS ancré
    const bottom = d.orig.y + d.orig.h;
    y = d.orig.y + dy; h = bottom - y;
    if (h < MIN_REGION) { h = MIN_REGION; y = bottom - MIN_REGION; }
  }
  if (w < MIN_REGION) w = MIN_REGION;   // bords est / sud
  if (h < MIN_REGION) h = MIN_REGION;
  Object.assign(r, { x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h) });
}

/* Met à jour visuellement la région sélectionnée pendant un drag. */
function liveUpdateSelected() {
  const r = selectedRegion();
  if (!r) return;
  const rect = overlay.querySelector(`rect.region[data-id="${r.id}"]`);
  if (rect) {
    rect.setAttribute("x", r.x); rect.setAttribute("y", r.y);
    rect.setAttribute("width", r.w); rect.setAttribute("height", r.h);
  }
  const label = overlay.querySelector(`text[data-label-for="${r.id}"]`);
  if (label) { label.setAttribute("x", r.x + 4); label.setAttribute("y", r.y + LABEL_PX + 2); }
  renderHandles();
  $("#coord-x").value = r.x; $("#coord-y").value = r.y;
  $("#coord-w").value = r.w; $("#coord-h").value = r.h;
}

/* ===================================================================
   Navigation clavier entre régions
   =================================================================== */
function navigateRegion(dir) {
  // Parcours en ordre de lecture (case → ses bulles → case suivante…).
  const list = readingSequence();
  if (!list.length) return;
  let idx = list.findIndex((r) => r.id === state.selectedId);
  idx = idx === -1 ? 0 : (idx + dir + list.length) % list.length;
  selectRegion(list[idx].id, false);   // F6 : ne pas re-déplier l'arbre à chaque flèche
}

/* ===================================================================
   Barre de statut
   =================================================================== */
function updateStatus() {
  const total = state.regions.length;
  const annot = state.regions.filter((r) => r.annotee).length;
  // Total de cases CITABLES de l'album (récit seul), porté par la citation serveur.
  const casesAlbum = state.regions.map((r) => r.citation && r.citation.total)
                                  .find((t) => t != null);
  $("#stat-cases").textContent = casesAlbum != null
    ? `${total} régions · ${casesAlbum} cases/album`
    : `${total} régions`;
  $("#stat-annotees").textContent = `${annot} annotées`;
  // met à jour le compteur dans la liste latérale
  const p = state.planche;
  if (p) { p.nb_regions = total; p.nb_annotees = annot; renderPlancheList(); }
}

/* ===================================================================
   Actions : segmenter, importer, nouvel album, export
   =================================================================== */
/* Verrou de planche : protège des passes automatiques (le backend refuse aussi en
   409, ceci évite juste le « en cours… » suivi d'une erreur). */
function plancheVerrouillee() {
  if (state.planche && state.planche.verrouillee) {
    toast("Planche verrouillée 🔒 — déverrouillez-la pour relancer un traitement.", "error");
    return true;
  }
  return false;
}

function renderPlancheLock() {
  const box = $("#planche-lock");
  if (!box) return;
  const p = state.planche;
  if (!p) { box.hidden = true; return; }
  box.hidden = false;
  const on = !!p.verrouillee;
  // AUTH-1 — le verrou est purement informatif (n'importe qui peut le lever) : ce qu'on
  // veut savoir avant de le faire, c'est À QUI en parler. `verrou_par` était consigné
  // depuis la v22 sans qu'aucun écran ne le montre.
  const par = p.verrou_par
    ? (VIEWER_MOI && p.verrou_par === VIEWER_MOI
        ? " par vous" : " par " + (p.verrou_par_nom || p.verrou_par))
    : "";
  box.innerHTML =
    `<button id="lock-toggle" class="lock-btn${on ? " locked" : ""}" ` +
    `title="${on ? "Verrouillée" + esc(par)
                   + " — protège des passes OCR/segmentation/bulles (en lot ou directes)"
                 : "Verrouiller la planche : la protéger des traitements automatiques"}">` +
    `${on ? "🔒 Verrouillée" + esc(par) : "🔓 Verrouiller la planche"}</button>`;
  $("#lock-toggle").onclick = toggleLock;
}

async function toggleLock() {
  const p = state.planche;
  if (!p) return;
  const on = !p.verrouillee;
  try {
    const upd = await apiSend("PATCH", `/api/planches/${p.id}/verrou`, { verrouillee: on });
    p.verrouillee = upd.verrouillee;     // p est la réf. partagée avec state.planches
    renderPlancheLock();
    toast(on ? "Planche verrouillée 🔒" : "Planche déverrouillée 🔓");
  } catch (e) { toast("Verrou : " + e.message, "error"); }
}

async function segmenter() {
  if (!state.planche || plancheVerrouillee()) return;
  toast("Segmentation en cours…");
  try {
    const res = await apiSend("POST", `/api/planches/${state.planche.id}/segmenter`);
    state.planche.statut = "segmentee";
    await loadRegions(state.planche.id);
    toast(`${res.nb_cases} cases détectées` +
          (res.reattaches ? `, ${res.reattaches} ré-rattachée(s)` : "") +
          (res.annotations_transferees ? `, ${res.annotations_transferees} annotation(s) transférée(s)` : "") +
          (res.annotations_preservees ? `, ${res.annotations_preservees} préservée(s)` : ""),
          "success");
  } catch (e) { toast("Segmentation : " + e.message, "error"); }
}

async function detecterBulles() {
  if (!state.planche || plancheVerrouillee()) return;
  toast("Détection des bulles…");
  try {
    const res = await apiSend("POST", `/api/planches/${state.planche.id}/detecter-bulles`);
    await loadRegions(state.planche.id);
    toast(`${res.nb_bulles} bulles détectées` +
          (res.preservees ? `, ${res.preservees} préservée(s)` : "") +
          (res.sans_case ? ` (${res.sans_case} hors case)` : ""), "success");
  } catch (e) { toast("Bulles : " + e.message, "error"); }
}

async function lancerOCR() {
  if (!state.planche || plancheVerrouillee()) return;
  toast("OCR en cours… (premier appel : chargement du modèle)");
  try {
    const res = await apiSend("POST", `/api/planches/${state.planche.id}/ocr`);
    await loadRegions(state.planche.id);
    toast(`OCR : ${res.ocr} régions pré-remplies` +
          (res.ignores ? `, ${res.ignores} déjà faites` : ""), "success");
  } catch (e) { toast("OCR : " + e.message, "error"); }
}

function setupImport() {
  // Deux déclencheurs (sidebar : accès rapide ; menu Import/Export : découvrable) →
  // même action : ouvrir le sélecteur de fichier sur l'album courant.
  const trigger = () => {
    if (!state.albumId) { toast("Créez d'abord un album", "error"); return; }
    $("#file-input").click();
  };
  $("#btn-import").onclick = trigger;
  const menuBtn = $("#btn-import-menu");
  if (menuBtn) menuBtn.onclick = trigger;
  $("#file-input").onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    toast("Import en cours…");
    try {
      const r = await fetch(`${API}/api/albums/${state.albumId}/import`, { method: "POST", body: fd });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
      await selectAlbum(state.albumId);
      toast("Planche importée", "success");
    } catch (err) { toast("Import : " + err.message, "error"); }
    e.target.value = "";
  };
}

async function newAlbum() {
  const titre = prompt("Titre de l'album ?");
  if (!titre) return;
  const auteur = prompt("Auteur ? (optionnel)") || null;
  const annee = parseInt(prompt("Année ? (optionnel)") || "", 10);
  try {
    const a = await apiSend("POST", "/api/albums", {
      titre, auteur, annee: isNaN(annee) ? null : annee,
    });
    state.albumId = a.id;
    await loadAlbums();
    toast("Album créé", "success");
  } catch (e) { toast("Création album : " + e.message, "error"); }
}

/* En-tête : menus déroulants « Traitement » / « Données ». Un seul ouvert à la fois ;
   se ferment au clic extérieur, sur Échap, et après activation d'un item (qui bulle
   jusqu'au document). Les actions (Segmenter/Bulles/OCR/ShareDocs, Sauvegarde) sont
   câblées ailleurs par id ; ici on gère l'ouverture + les liens d'export (data-fmt). */
function setupMenus() {
  const dropdowns = [...document.querySelectorAll(".dropdown")];

  // Items actionnables d'un menu, dans l'ordre du DOM, hors désactivés/masqués
  // (le menu gère le focus en « roving » : on saute ce qui n'est pas atteignable).
  const itemsOf = (menu) =>
    [...menu.querySelectorAll('[role="menuitem"]')]
      .filter((el) => !el.disabled && el.getClientRects().length > 0);

  // Ferme tous les menus. Rend le focus au déclencheur si le focus était DANS le menu
  // fermé (sinon il se perdrait sur <body> quand le menu passe en display:none) —
  // sauf `refocus=false`, p.ex. quand on ouvre un autre menu juste après.
  const closeAll = (refocus = true) => dropdowns.forEach((dd) => {
    const menu = dd.querySelector(".dropdown-menu"), btn = dd.querySelector("button");
    if (!menu || !btn || !menu.classList.contains("open")) return;
    const hadFocus = menu.contains(document.activeElement);
    menu.classList.remove("open");
    btn.setAttribute("aria-expanded", "false");
    if (refocus && hadFocus) btn.focus();
  });

  const openMenu = (btn, menu, focus) => {
    closeAll(false);                                    // un seul ouvert à la fois
    document.dispatchEvent(new CustomEvent("bd:menu-open", { detail: "dropdown" }));
    menu.classList.add("open");
    btn.setAttribute("aria-expanded", "true");
    const items = itemsOf(menu);
    if (focus === "first") items[0]?.focus();
    else if (focus === "last") items[items.length - 1]?.focus();
  };

  dropdowns.forEach((dd) => {
    const btn = dd.querySelector("button"), menu = dd.querySelector(".dropdown-menu");
    if (!btn || !menu) return;

    // Sémantique « menu button » (WAI-ARIA) — invisible, ne touche pas le rendu.
    btn.setAttribute("aria-haspopup", "menu");
    btn.setAttribute("aria-expanded", "false");
    if (menu.id) btn.setAttribute("aria-controls", menu.id);
    menu.setAttribute("role", "menu");
    if (btn.id) menu.setAttribute("aria-labelledby", btn.id);
    menu.querySelectorAll("button").forEach((b) => {
      b.setAttribute("role", "menuitem");
      b.tabIndex = -1;                                  // hors tabulation : le menu pilote le focus
    });

    btn.onclick = (e) => {
      e.stopPropagation();
      if (menu.classList.contains("open")) closeAll();
      else openMenu(btn, menu, null);                   // souris : on n'impose pas le focus dans le menu
    };
    // Ouverture au clavier depuis le déclencheur : ↓/Entrée/Espace → 1er item ; ↑ → dernier.
    btn.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
        e.preventDefault(); openMenu(btn, menu, "first");
      } else if (e.key === "ArrowUp") {
        e.preventDefault(); openMenu(btn, menu, "last");
      }
    });
    // Navigation au clavier DANS le menu (flèches bouclent, Origine/Fin, Échap, Tab).
    menu.addEventListener("keydown", (e) => {
      // Un menu focalisé capte le clavier : on isole des raccourcis globaux (←/→ =
      // navigation entre régions, lettres = changement de mode) tant qu'il est ouvert.
      e.stopPropagation();
      const items = itemsOf(menu);
      if (!items.length) return;
      const i = items.indexOf(document.activeElement), n = items.length;
      if (e.key === "ArrowDown") { e.preventDefault(); items[(i + 1) % n].focus(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); items[(i - 1 + n) % n].focus(); }
      else if (e.key === "Home") { e.preventDefault(); items[0].focus(); }
      else if (e.key === "End") { e.preventDefault(); items[n - 1].focus(); }
      else if (e.key === "Escape") { e.stopPropagation(); closeAll(); }   // ferme + focus au déclencheur
      else if (e.key === "Tab") { closeAll(); }                          // ferme ; Tab reprend depuis le déclencheur
    });
  });
  document.addEventListener("click", () => closeAll());
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeAll(); });
  // Coordination inter-systèmes : un AUTRE menu s'ouvre (ex. « Affichage » de
  // theme.js) → on ferme les dropdowns (un seul menu ouvert à la fois, toutes barres
  // confondues). Chaque système ignore son propre signal (detail).
  document.addEventListener("bd:menu-open", (e) => { if (e.detail !== "dropdown") closeAll(); });

  document.querySelectorAll("[data-fmt]").forEach((a) => {
    a.onclick = () => {
      if (!state.albumId) { toast("Aucun album", "error"); return; }
      window.open(`${API}/api/export/${a.dataset.fmt}?album_id=${state.albumId}`, "_blank");
    };
  });
}

/* ===================================================================
   Explorateur ShareDocs (WebDAV Huma-Num) — modale
   =================================================================== */
const SD_IMG = /\.(tif|tiff|jpe?g|jp2|j2k|jpf|jpx|jpc|j2c|png|bmp|gif|webp)$/i;
state.sd = { cwd: "", entries: [], selected: new Set(), importing: false, cancelImport: false, abort: null, compte: null };

function sdFmtSize(n) {
  if (n == null) return "";
  const u = ["o", "Ko", "Mo", "Go"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
}

function sdShow(which) {            // "login" | "browser"
  $("#sd-login").hidden = which !== "login";
  $("#sd-browser").hidden = which !== "browser";
  $("#sd-import-form").hidden = true;
}

/* SHARE-1 — il y a DEUX comptes possibles : le mien et celui de l'instance. L'écran doit
   dire lequel répond, sinon on dépose sans savoir où. Le libellé porte l'origine ; la
   liste déroulante ne paraît que s'il y a vraiment un choix à faire. */
const SD_COMPTES = { perso: "mon compte", instance: "compte de l'instance" };

function sdRendreComptes(etat) {
  const sel = $("#sd-compte");
  const dispo = [];
  if (etat.perso) dispo.push(["perso", etat.perso.user]);
  if (etat.instance) dispo.push(["instance", etat.instance.user]);
  sel.innerHTML = dispo.map(
    ([c, u]) => `<option value="${c}">${esc(SD_COMPTES[c])} — ${esc(u)}</option>`).join("");
  // Un choix mémorisé qui n'est plus disponible doit être ABANDONNÉ : après avoir fermé
  // ma session, `state.sd.compte === "perso"` désignerait un compte absent. Le `<select>`
  // refuserait la valeur en silence et afficherait la première option, pendant que la
  // navigation continuerait de réclamer l'autre — l'écran et l'état diraient deux choses.
  const noms = dispo.map(([c]) => c);
  if (state.sd.compte && !noms.includes(state.sd.compte)) state.sd.compte = null;
  const actif = etat.actif ? etat.actif.compte : null;
  if (actif) sel.value = state.sd.compte || actif;
  // Un choix à une seule branche n'est pas un choix : on le cache plutôt que de le griser.
  $("#sd-compte-box").hidden = dispo.length < 2;
  // « Mon compte… » n'a de sens que si je n'en ai pas encore ouvert un.
  $("#sd-connect-perso").hidden = !!etat.perso;
  $("#sd-conn-state").textContent = etat.actif
    ? `connecté · ${etat.actif.user} (${SD_COMPTES[etat.actif.compte]})`
    : "non connecté";
}

async function sdOpen() {
  $("#sharedocs").hidden = false;
  $("#sd-login-msg").textContent = "";
  try {
    const etat = await apiGet("/api/sharedocs/etat");
    sdRendreComptes(etat);
    if (etat.connecte) {
      sdShow("browser");
      sdNavigate(state.sd.cwd || "");
    } else {
      sdShow("login");
      $("#sd-url").value = (etat.prefill && etat.prefill.url) || "";
      $("#sd-user").value = (etat.prefill && etat.prefill.user) || "";
      $("#sd-pass").value = "";
      ($("#sd-url").value ? $("#sd-pass") : $("#sd-url")).focus();
    }
  } catch (e) { toast("ShareDocs : " + e.message, "error"); }
}

/* Changer de compte relance la navigation À LA RACINE : un chemin valide chez l'un ne
   l'est pas forcément chez l'autre, et rester sur place afficherait une erreur au lieu
   d'un dossier. */
function sdChangerCompte() {
  state.sd.compte = $("#sd-compte").value || null;
  state.sd.selected.clear();
  sdNavigate("");
}

function sdClose() { $("#sharedocs").hidden = true; }

async function sdConnect() {
  const msg = $("#sd-login-msg");
  msg.textContent = "Connexion…";
  try {
    const r = await apiSend("POST", "/api/sharedocs/connexion", {
      url: $("#sd-url").value.trim(),
      user: $("#sd-user").value.trim(),
      password: $("#sd-pass").value,
    });
    $("#sd-pass").value = "";        // ne pas laisser traîner le mot de passe dans le DOM
    // Un SEUL rendu de l'état de connexion (SHARE-1). Recomposer le libellé ici en
    // laissait tomber l'origine du compte, gardait la liste des comptes périmée alors
    // qu'un choix venait d'apparaître, et laissait « Mon compte… » affiché après l'avoir
    // ouvert : deux chemins qui rendent la même chose finissent par diverger, et celui-ci
    // avait divergé le jour même.
    state.sd.compte = null;          // on repart sur la règle par défaut : la mienne
    state.sd.selected.clear();
    try { sdRendreComptes(await apiGet("/api/sharedocs/etat")); } catch (_) {}
    sdShow("browser");
    sdNavigate("");
  } catch (e) { msg.textContent = "✗ " + e.message; }
}

async function sdDisconnect() {
  if (state.sd.abort) state.sd.abort.abort();   // stoppe un import en cours avant de réinitialiser
  try { await apiSend("POST", "/api/sharedocs/deconnexion"); } catch (_) {}
  state.sd = { cwd: "", entries: [], selected: new Set(), importing: false, cancelImport: false, abort: null, compte: null };
  $("#sd-pass").value = "";
  // Se déconnecter ferme MA session ; celle de l'instance peut prendre le relais, et
  // l'écran doit le dire au lieu d'annoncer « non connecté » à tort. La suite se décide
  // sur l'ÉTAT RENDU par le serveur, jamais en relisant le texte qu'on vient d'afficher :
  // une décision prise sur du texte rendu se casse au premier changement de libellé.
  let etat = null;
  try { etat = await apiGet("/api/sharedocs/etat"); } catch (_) { /* hors ligne */ }
  if (etat) sdRendreComptes(etat);
  else $("#sd-conn-state").textContent = "non connecté";
  if (etat && etat.connecte) { sdNavigate(""); return; }
  sdShow("login");
}

async function sdNavigate(path) {
  try {
    const entries = await apiGet(
      "/api/sharedocs/liste?chemin=" + encodeURIComponent(path)
      + (state.sd.compte ? "&compte=" + encodeURIComponent(state.sd.compte) : ""));
    state.sd.cwd = path;
    state.sd.entries = entries;
    sdRenderBreadcrumb();
    sdRenderList();
  } catch (e) { toast("ShareDocs : " + e.message, "error"); }
}

function sdRenderBreadcrumb() {
  const bc = $("#sd-breadcrumb");
  bc.innerHTML = "";
  const mk = (label, path) => {
    const a = document.createElement("a");
    a.textContent = label;
    a.onclick = () => sdNavigate(path);
    return a;
  };
  bc.appendChild(mk("racine", ""));
  let acc = "";
  for (const seg of state.sd.cwd.split("/").filter(Boolean)) {
    acc = acc ? acc + "/" + seg : seg;
    const sep = document.createElement("span");
    sep.className = "sep"; sep.textContent = "›";
    bc.appendChild(sep);
    bc.appendChild(mk(seg, acc));
  }
}

function sdRenderList() {
  const box = $("#sd-list");
  box.innerHTML = "";
  if (!state.sd.entries.length) {
    box.innerHTML = '<div class="sd-empty">Dossier vide.</div>';
    sdUpdateSel();
    return;
  }
  for (const e of state.sd.entries) {
    const row = document.createElement("div");
    const importable = !e.is_dir && SD_IMG.test(e.name);
    row.className = "sd-item" + (e.is_dir ? " dir" : "")
      + (!e.is_dir && !importable ? " disabled" : "")
      + (state.sd.selected.has(e.path) ? " selected" : "");
    if (e.is_dir) {
      row.innerHTML = `<span class="sd-ico">📁</span><span class="sd-name">${escapeHtml(e.name)}</span>`;
      row.onclick = () => sdNavigate(e.path);
    } else {
      const checked = state.sd.selected.has(e.path) ? "checked" : "";
      row.innerHTML =
        (importable ? `<input type="checkbox" ${checked}>` : `<span class="sd-ico"></span>`) +
        `<span class="sd-ico">${importable ? "🖼" : "📄"}</span>` +
        `<span class="sd-name">${escapeHtml(e.name)}</span>` +
        `<span class="sd-size">${sdFmtSize(e.size)}</span>`;
      if (importable) row.onclick = (ev) => {
        const cb = row.querySelector("input");
        if (ev.target !== cb) cb.checked = !cb.checked;
        sdToggleSel(e.path, cb.checked, row);
      };
    }
    box.appendChild(row);
  }
  sdUpdateSel();
}

function sdToggleSel(path, on, row) {
  if (on) state.sd.selected.add(path); else state.sd.selected.delete(path);
  row.classList.toggle("selected", on);
  sdUpdateSel();
}

/* Fichiers importables (images) du dossier courant. */
function sdImportablesIci() {
  return state.sd.entries.filter((e) => !e.is_dir && SD_IMG.test(e.name));
}

/* Sélectionne / désélectionne d'un coup tous les importables du dossier courant. */
function sdToggleSelectAll() {
  const imgs = sdImportablesIci();
  if (!imgs.length) return;
  const tousSelectionnes = imgs.every((e) => state.sd.selected.has(e.path));
  for (const e of imgs) {
    if (tousSelectionnes) state.sd.selected.delete(e.path);
    else state.sd.selected.add(e.path);
  }
  sdRenderList();   // rafraîchit cases + surbrillance + compteur
}

function sdUpdateSel() {
  const n = state.sd.selected.size;
  $("#sd-selcount").textContent = `${n} sélectionné${n > 1 ? "s" : ""}`;
  $("#sd-import").disabled = n === 0;
  // Bouton « Tout sélectionner / désélectionner » selon l'état du dossier courant.
  const imgs = sdImportablesIci();
  const btn = $("#sd-selectall");
  btn.disabled = imgs.length === 0;
  const tous = imgs.length > 0 && imgs.every((e) => state.sd.selected.has(e.path));
  btn.textContent = tous ? "Tout désélectionner" : "Tout sélectionner";
}

/* Remplit le sélecteur d'album cible (option « nouvel album » + albums existants). */
function sdFillAlbumSelect(selectedId) {
  const sel = $("#sd-album");
  sel.innerHTML = '<option value="__new__">➕ Nouvel album…</option>';
  for (const a of state.albums) {
    const o = document.createElement("option");
    o.value = String(a.id);
    o.textContent = `${a.serie ? a.serie + " · " : ""}${a.titre}`;
    sel.appendChild(o);
  }
  sel.value = selectedId ? String(selectedId) : "__new__";
  sdImportToggleNew();
}

function sdOpenImport() {
  if (state.sd.importing) { toast("Un import est déjà en cours.", ""); return; }
  const n = state.sd.selected.size;
  if (!n) return;
  $("#sd-import-title").textContent = `Importer ${n} fichier${n > 1 ? "s" : ""}`;
  sdFillAlbumSelect(state.albumId || null);
  $("#sd-newalbum").value = state.sd.cwd.split("/").filter(Boolean).pop() || "ShareDocs";
  sdImportToggleNew();
  $("#sd-import-msg").textContent = "";
  sdProgressReset();
  $("#sd-import-go").disabled = false;
  $("#sd-import-cancel").textContent = "Annuler";
  $("#sd-browser").hidden = true;
  $("#sd-import-form").hidden = false;
}

function sdImportToggleNew() {
  $("#sd-newalbum-wrap").hidden = $("#sd-album").value !== "__new__";
}

function sdCancelImport() {
  if (state.sd.importing) {            // import en cours → demande d'arrêt
    state.sd.cancelImport = true;
    if (state.sd.abort) state.sd.abort.abort();   // interrompt la requête en cours (arrêt immédiat)
    $("#sd-import-cancel").disabled = true;
    $("#sd-import-cancel").textContent = "Arrêt…";
    return;
  }
  $("#sd-import-form").hidden = true;
  $("#sd-browser").hidden = false;
}

/* --- Barre de progression de l'import --- */
function sdProgressReset() {
  $("#sd-progress").hidden = true;
  $("#sd-progress-fill").style.width = "0%";
  $("#sd-progress-label").textContent = "";
  $("#sd-progress-errors").innerHTML = "";
}
function sdProgressUpdate(done, total, current, segmenter, ok, ko) {
  $("#sd-progress").hidden = false;
  $("#sd-progress-fill").style.width = Math.round((done / total) * 100) + "%";
  const tally = `✓ ${ok}` + (ko ? ` · ✗ ${ko}` : "");
  $("#sd-progress-label").textContent = current
    ? `${done}/${total} (${tally}) — en cours : ${current}${segmenter ? " · segmentation…" : ""}`
    : `${done}/${total} (${tally}) — terminé`;
}
function sdProgressError(chemin, msg) {
  const li = document.createElement("li");
  li.textContent = `${chemin.split("/").pop()} : ${msg}`;
  $("#sd-progress-errors").appendChild(li);
}

async function sdDoImport() {
  if (state.sd.importing) return;        // garde-fou anti double-import concurrent
  const chemins = [...state.sd.selected];
  if (!chemins.length) return;
  const segmenter = $("#sd-segmenter").checked;

  // Résout l'album cible. Pour un nouvel album, on le crée explicitement d'abord
  // (album_id stable) plutôt que de laisser chaque appel tenter de le créer.
  let albumId, albumNeuf = false;
  if ($("#sd-album").value === "__new__") {
    const titre = $("#sd-newalbum").value.trim();
    if (!titre) { $("#sd-import-msg").textContent = "Nom d'album requis."; return; }
    try {
      const a = await apiSend("POST", "/api/albums", { titre });
      albumId = a.id; albumNeuf = true;
    } catch (e) { $("#sd-import-msg").textContent = "✗ " + e.message; return; }
  } else {
    albumId = Number($("#sd-album").value);
  }

  // Passe en mode « import en cours » : progression + bouton Annuler → Arrêter.
  state.sd.importing = true;
  state.sd.cancelImport = false;
  state.sd.abort = new AbortController();
  $("#sd-import-msg").textContent = "";
  $("#sd-import-go").disabled = true;
  $("#sd-import-cancel").disabled = false;
  $("#sd-import-cancel").textContent = "Arrêter";
  let ok = 0, ko = 0, i = 0;
  sdProgressReset();
  sdProgressUpdate(0, chemins.length, chemins[0].split("/").pop(), segmenter, ok, ko);

  for (; i < chemins.length; i++) {
    if (state.sd.cancelImport) break;
    const chemin = chemins[i];
    sdProgressUpdate(i, chemins.length, chemin.split("/").pop(), segmenter, ok, ko);
    try {
      const res = await apiSend("POST", "/api/sharedocs/importer",
        { chemins: [chemin], album_id: albumId, segmenter, compte: state.sd.compte },
        { signal: state.sd.abort.signal });
      if (res.importes.length) { ok++; state.sd.selected.delete(chemin); }
      for (const er of res.erreurs) { ko++; sdProgressError(er.chemin, er.erreur); }
    } catch (e) {
      if (e.name === "AbortError") break;   // arrêt demandé : sortie immédiate, pas un échec
      ko++; sdProgressError(chemin, e.message);
    }
  }
  sdProgressUpdate(i, chemins.length, "", false, ok, ko);

  // Album neuf resté vide (tout a échoué / annulé avant le moindre import) → on le retire.
  if (albumNeuf && ok === 0) {
    try { await apiSend("DELETE", "/api/albums/" + albumId); } catch (_) {}
  }

  const arrete = state.sd.cancelImport;
  state.sd.importing = false;
  state.sd.cancelImport = false;
  state.sd.abort = null;
  $("#sd-import-cancel").disabled = false;
  $("#sd-import-cancel").textContent = "Fermer";
  $("#sd-import-go").disabled = false;

  toast(`Import : ${ok} planche${ok > 1 ? "s" : ""}` +
        (ko ? `, ${ko} échec${ko > 1 ? "s" : ""}` : "") + (arrete ? " (arrêté)" : ""),
        ok ? (ko ? "" : "success") : "error");

  if (ok) {
    state.albumId = albumId;
    await loadAlbums();          // recharge albums → sélectionne la cible + ses planches
    if (!ko && !arrete) { sdClose(); return; }   // tout bon → on ferme
  }
  // On reste sur le formulaire : repointe le sélecteur sur l'album réellement
  // utilisé pour qu'un nouvel essai des échecs s'y ajoute (et ne crée pas un 2e
  // album neuf). Si l'album neuf a été supprimé (0 import), on retombe sur « nouvel ».
  const albumExiste = !(albumNeuf && ok === 0);
  sdFillAlbumSelect(albumExiste ? albumId : null);
  $("#sd-import-msg").textContent =
    ko ? `${ko} échec(s) — voir le détail ci-dessous.` : (arrete ? "Import arrêté." : "");
}

/* Dépose une sauvegarde (.sqlite zippé) dans le dossier ShareDocs courant. */
function sdDeposerSauvegarde() {
  const btn = $("#sd-deposer");
  const old = btn.textContent;
  btn.disabled = true; btn.textContent = "Dépôt…";
  apiSend("POST", "/api/sharedocs/deposer-sauvegarde",
          { dossier: state.sd.cwd, compte: state.sd.compte })
    // Le compte EMPLOYÉ est rendu par le serveur et affiché : une sauvegarde déposée sous
    // un compte personnel atterrit dans un espace qui s'en va avec la personne, et c'est
    // le genre de chose qu'on veut lire au moment où ça arrive.
    .then((res) => toast(
      `Sauvegarde déposée : ${res.depose} (${SD_COMPTES[res.compte] || res.compte}`
      + ` — ${res.compte_user})`, "success"))
    .catch((e) => toast("Dépôt : " + e.message, "error"))
    .finally(() => { btn.disabled = false; btn.textContent = old; });
}

function setupSharedocs() {
  $("#btn-sharedocs").onclick = sdOpen;
  $("#sd-close").onclick = sdClose;
  $("#sd-connect").onclick = sdConnect;
  $("#sd-pass").addEventListener("keydown", (e) => { if (e.key === "Enter") sdConnect(); });
  $("#sd-disconnect").onclick = sdDisconnect;
  $("#sd-deposer").onclick = sdDeposerSauvegarde;
  $("#sd-compte").onchange = sdChangerCompte;
  $("#sd-connect-perso").onclick = () => { $("#sd-pass").value = ""; sdShow("login"); };
  $("#sd-selectall").onclick = sdToggleSelectAll;
  $("#sd-import").onclick = sdOpenImport;
  $("#sd-album").onchange = sdImportToggleNew;
  $("#sd-import-go").onclick = sdDoImport;
  $("#sd-import-cancel").onclick = sdCancelImport;
  $("#sharedocs").addEventListener("mousedown", (e) => {
    if (e.target.id === "sharedocs") sdClose();   // clic sur le fond = fermer
  });
  // Modale accessible : role=dialog, piège à focus, Échap, retour du focus (source unique).
  if (window.BDDialog)
    BDDialog.register($("#sharedocs"),
      { box: ".sd-dialog", labelledby: "sd-title", onClose: sdClose });
}

/* Télécharge une sauvegarde de la base (zip horodaté). */
function downloadBackup() {
  const a = document.createElement("a");
  a.href = API + "/api/sauvegarde";
  a.download = "";
  document.body.appendChild(a); a.click(); a.remove();
  toast("Préparation de la sauvegarde…");
}

/* ===================================================================
   Figures citables (DROIT-1) — citer n'est pas publier

   Le régime de diffusion d'une collection ne bloque PAS la citation : il l'accompagne. Ce
   que produit l'export n'est donc pas une image, c'est une image LIÉE à sa référence — un
   crop nu se recrédite à la main, et c'est à la main que le crédit se perd.

   Un PANIER plutôt qu'un export immédiat : une communication a besoin de plusieurs
   figures, et une modale ouverte empêcherait de sélectionner la région suivante.
   =================================================================== */
const FIG = { regions: [], champs: null, libelles: [] };

function figMsg(texte, erreur) {
  const el = $("#fig-msg");
  if (!el) return;
  el.textContent = texte || "";
  el.classList.toggle("erreur", !!erreur);
}

/* Le bouton d'ouverture ne s'affiche QUE si le panier est garni : un bouton « Exporter »
   permanent sur un panier vide promet une action qui n'aboutit pas. */
function figRefreshBouton() {
  const b = $("#btn-fig-open");
  if (!b) return;
  b.hidden = FIG.regions.length === 0;
  b.textContent = `Exporter (${FIG.regions.length})`;
  b.title = `Exporter ${FIG.regions.length} figure(s) avec leur légende`;
}

function figAdd() {
  const r = selectedRegion();
  if (!r) { toast("Sélectionnez d'abord une région."); return; }
  if (FIG.regions.some((x) => x.id === r.id)) { toast("Déjà dans les figures."); return; }
  // On mémorise la CITATION avec l'id : elle sert d'étiquette dans le panier, et la
  // recalculer après un changement de planche demanderait de rappeler le serveur.
  FIG.regions.push({ id: r.id, libelle: (r.citation && r.citation.texte) || `région ${r.id}` });
  figRefreshBouton();
  toast(`Figure ajoutée (${FIG.regions.length}).`);
}

async function figChamps() {
  if (FIG.libelles.length) return FIG.libelles;
  // La liste vient du SERVEUR et n'est pas recopiée ici : deux listes qui divergent
  // produiraient une légende amputée sans rien signaler.
  FIG.libelles = await apiGet("/api/figure/champs");
  if (FIG.champs === null) FIG.champs = FIG.libelles.map((c) => c.champ);   // tout, au début
  return FIG.libelles;
}

function figRendre() {
  $("#fig-compte").textContent = String(FIG.regions.length);
  $("#fig-liste").innerHTML = FIG.regions.map((r) => `
    <li><span class="mono">${esc(r.libelle)}</span>
        <button class="ghost small" data-fig-retirer="${r.id}" type="button"
                title="Retirer cette figure">✕</button></li>`).join("");
  $("#fig-liste").querySelectorAll("[data-fig-retirer]").forEach((b) => {
    b.onclick = () => {
      FIG.regions = FIG.regions.filter((x) => String(x.id) !== b.dataset.figRetirer);
      figRefreshBouton();
      figRendre();
    };
  });
  $("#fig-champs").innerHTML = FIG.libelles.map((c) => `
    <label><input type="checkbox" value="${c.champ}"
      ${FIG.champs.includes(c.champ) ? "checked" : ""}> ${esc(c.libelle)}</label>`).join("");
  $("#fig-champs").querySelectorAll("input").forEach((i) => {
    i.onchange = () => {
      FIG.champs = [...$("#fig-champs").querySelectorAll("input:checked")].map((x) => x.value);
    };
  });
  $("#fig-export").disabled = FIG.regions.length === 0;
}

async function figOpen() {
  figMsg("");
  try { await figChamps(); }
  catch (e) { figMsg(e.message, true); }
  figRendre();
  $("#figure-modal").hidden = false;
  $("#fig-export").focus();
}

function figClose() { $("#figure-modal").hidden = true; }

async function figExport() {
  if (!FIG.regions.length) return;
  figMsg("Préparation…");
  try {
    const r = await fetch(API + "/api/figures", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ regions: FIG.regions.map((x) => x.id), champs: FIG.champs }),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    // Le nom du fichier vient du serveur (Content-Disposition) : le recomposer ici ferait
    // diverger deux horodatages pour un seul export.
    const nom = (r.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/);
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement("a");
    a.href = url; a.download = nom ? nom[1] : "figures.zip";
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    figMsg(`${FIG.regions.length} figure(s) exportée(s).`);
  } catch (e) { figMsg(e.message || "Échec de l'export", true); }
}

function figVider() {
  FIG.regions = [];
  figRefreshBouton();
  figRendre();
  figMsg("Panier vidé.");
}

/* ===================================================================
   Câblage des contrôles & raccourcis
   =================================================================== */
function setupControls() {
  document.querySelectorAll(".mode-btn").forEach((b) =>
    b.onclick = () => setMode(b.dataset.mode));
  $("#album-select").onchange = (e) => selectAlbum(Number(e.target.value));
  $("#btn-new-album").onclick = newAlbum;
  $("#btn-segmenter").onclick = segmenter;
  $("#btn-bulles").onclick = detecterBulles;
  $("#btn-ocr").onclick = lancerOCR;
  $("#btn-backup").onclick = downloadBackup;
  // Figures citables (DROIT-1) : citer se décide sur la région, l'export se fait ensuite.
  $("#btn-fig-add").onclick = figAdd;
  $("#btn-fig-open").onclick = figOpen;
  $("#fig-close").onclick = figClose;
  $("#fig-vider").onclick = figVider;
  $("#fig-export").onclick = figExport;
  $("#figure-modal").addEventListener("mousedown", (e) => {
    if (e.target.id === "figure-modal") figClose();
  });
  if (window.BDDialog)
    BDDialog.register($("#figure-modal"),
      { box: ".modal-box", labelledby: "figure-title", onClose: figClose });
  $("#zoom-in").onclick = () => { const r = stage.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1.2); };
  $("#zoom-out").onclick = () => { const r = stage.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1 / 1.2); };
  $("#zoom-fit").onclick = fitView;
  $("#zoom-reset").onclick = () => { state.zoom = 1; applyTransform(); };

  // Panneau : type & coordonnées
  $("#region-type").onchange = (e) => {
    if (state.selectedId != null) patchRegion(state.selectedId, { type: e.target.value });
  };
  $("#region-parent").onchange = (e) => {
    if (state.selectedId == null) return;
    patchRegion(state.selectedId, { parent_id: e.target.value === "" ? null : Number(e.target.value) });
  };
  ["x", "y", "w", "h"].forEach((k) => {
    $("#coord-" + k).onchange = (e) => {
      if (state.selectedId == null) return;
      patchRegion(state.selectedId, { [k]: Math.round(+e.target.value) });
    };
  });
  $("#btn-delete-region").onclick = () => {
    if (state.selectedId != null && confirm("Supprimer cette région et ses sous-régions ?"))
      deleteRegion(state.selectedId);
  };

  // Arbre : repli/dépli (escamote l'arbre pour dégager les champs Tags/Note/OCR)
  $("#tree-header").onclick = () =>
    $("#panel-tree").classList.toggle("collapsed");
  // Boutons tout déplier / tout replier (sans déclencher le repli de la section)
  $("#tree-expand").onclick = (e) => { e.stopPropagation(); expandAllTree(); };
  $("#tree-collapse").onclick = (e) => { e.stopPropagation(); collapseAllTree(); };
  $("#tree-recalc").onclick = (e) => { e.stopPropagation(); recalcOrder(); };

  // Annotation : note
  $("#note-input").addEventListener("input", scheduleSave);

  setupTagInput();
  setupPersoInput("#loc-input", "#loc-suggest", setLocuteur);     // locuteur (bulle)
  setupPersoInput("#perso-input", "#perso-suggest", setPerso);    // identité (boîte personnage)
  setupAttributs();
  setupImport();
  setupMenus();
  setupTranscription();
  setupSharedocs();
}

/* Annulation (undo, D1) — Ctrl+Z rejoue côté serveur l'INVERSE de la dernière action
   d'annotation (depuis le journal A3), puis rafraîchit la vue touchée. Le serveur porte la
   pile (Ctrl+Z répété remonte l'historique) ; ici on ne fait qu'appeler et rafraîchir. */
async function undoLast() {
  // Ne pas laisser une sauvegarde différée re-appliquer un buffer périmé APRÈS l'annulation.
  clearTimeout(state.saveTimer);
  state.saveTimer = null;
  let res;
  try {
    res = await apiSend("POST", "/api/undo");
  } catch (e) {
    toast(e.message, /rien à annuler/i.test(e.message) ? "" : "error");
    return;
  }
  toast("Annulé : " + res.description);
  if (res.planche_id && state.planche && res.planche_id === state.planche.id) {
    await loadRegions(state.planche.id);
    if (res.region_id != null && state.regionsById.has(res.region_id)) {
      state.selectedId = res.region_id;      // montre la région touchée + son état restauré
      renderOverlay();
      renderPanel();
      if (state.mode === "annotation") loadAnnotation(res.region_id);
    }
  } else if (res.planche_id && state.planches.some((p) => p.id === res.planche_id)) {
    selectPlanche(res.planche_id);           // l'action touchait une autre planche de l'album
  }
}

function setupKeyboard() {
  window.addEventListener("keydown", (e) => {
    const tag = (e.target.tagName || "").toLowerCase();
    const typing = tag === "input" || tag === "textarea" || tag === "select";
    // Ctrl/⌘+Z hors champ de saisie = annuler la dernière action (dans un champ : undo natif).
    if (!typing && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
      e.preventDefault();
      undoLast();
      return;
    }
    if (typing) return;

    const k = e.key.toLowerCase();
    if (k === "n") setMode("navigation");
    else if (k === "e") setMode("edition");
    else if (k === "a") setMode("annotation");
    else if (k === "t") setMode("transcription");
    else if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
      if (state.selectedId != null) moveRegion(state.selectedId, e.key === "ArrowUp" ? "haut" : "bas");
      e.preventDefault();
    }
    else if (e.key === "ArrowRight") { navigateRegion(1); e.preventDefault(); }
    else if (e.key === "ArrowLeft") { navigateRegion(-1); e.preventDefault(); }
    else if (e.key === "Delete" &&
             state.mode === "edition" && state.selectedId != null) {
      deleteRegion(state.selectedId); e.preventDefault();
    } else if (e.key === "Escape") {
      const dr = overlay.querySelector("#draw-rect");
      if (dr) dr.remove();
      drag = null;
      deselect();   // flushSave inclus : ne perd pas une annotation en attente
    }
  });
}

/* ===================================================================
   Démarrage
   =================================================================== */
/* Ouvre la visionneuse pile sur une région (lien venant de la recherche) :
   ?album=&planche=&region=. */
async function applyDeepLink() {
  const p = new URLSearchParams(INITIAL_QS);   // URL d'origine (avant que syncUrl ne l'ait modifiée)
  const album = p.get("album"), planche = p.get("planche"), region = p.get("region");
  if (!planche && !region) return;
  try {
    if (album && Number(album) !== state.albumId) {
      $("#album-select").value = album;
      await selectAlbum(Number(album), false);   // la planche du lien sera choisie ci-dessous
    }
    if (planche) {
      await selectPlanche(Number(planche));
      if (!state.planche || state.planche.id !== Number(planche)) {   // F5 : plus de silence
        toast("Planche du lien introuvable dans cet album.", "error");
        return;
      }
    }
    if (region) {
      setMode("navigation");
      if (!selectAndCenter(Number(region)))
        toast("Région du lien introuvable sur cette planche.", "error");
    }
  } catch (e) { toast("Lien : " + e.message, "error"); }
}

async function init() {
  setupControls();
  setupKeyboard();
  setupBack();
  setMode("navigation");
  window.addEventListener("resize", () => { if (state.planche) applyTransform(); });
  try {
    await refreshTagVocab();
    await loadAlbums();
    await applyDeepLink();
  } catch (e) {
    toast("Erreur de chargement : " + e.message, "error");
  }
}

init();
