/* ===================================================================
   BD Annotator — visionneuse & logique d'annotation (vanilla JS)
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

/* ---------------- État global ---------------- */
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
  hierParent: null,        // parent_id du niveau affiché (null = racine planche)
  mode: "navigation",
  zoom: 1, tx: 0, ty: 0,
  tagVocab: [],            // [{label, couleur, frequence}]
  currentTags: [],         // labels (string) de l'annotation en cours
  saveTimer: null,
};

/* ---------------- Raccourcis DOM ---------------- */
const $ = (sel) => document.querySelector(sel);
const stage = $("#stage");
const canvas = $("#canvas");
const img = $("#planche-img");
const overlay = $("#overlay");

/* ===================================================================
   Utilitaires API
   =================================================================== */
async function apiGet(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
async function apiSend(method, path, body) {
  const r = await fetch(API + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.status === 204 ? null : r.json();
}

/* ===================================================================
   Toasts
   =================================================================== */
let toastBox;
function toast(msg, kind = "") {
  if (!toastBox) {
    toastBox = document.createElement("div");
    toastBox.id = "toasts";
    document.body.appendChild(toastBox);
  }
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.textContent = msg;
  toastBox.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

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

async function selectAlbum(id) {
  state.albumId = id;
  state.planches = await apiGet(`/api/albums/${id}/planches`);
  renderPlancheList();
  if (state.planches.length) selectPlanche(state.planches[0].id);
  else { state.planche = null; clearStage(); }
}

function renderPlancheList() {
  const ul = $("#planche-list");
  ul.innerHTML = "";
  for (const p of state.planches) {
    const li = document.createElement("li");
    li.dataset.id = p.id;
    if (state.planche && p.id === state.planche.id) li.classList.add("active");
    li.innerHTML =
      `<span class="statut-pill statut-${p.statut}" title="${p.statut}"></span>` +
      `<span class="num">p.${String(p.numero).padStart(3, "0")}</span>` +
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
}

/* ===================================================================
   Sélection / chargement d'une planche
   =================================================================== */
async function selectPlanche(id) {
  flushSave();
  const p = state.planches.find((x) => x.id === id);
  if (!p) return;
  state.planche = p;
  state.selectedId = null;
  state.hierParent = null;

  renderPlancheList();
  const album = state.albums.find((a) => a.id === state.albumId);
  $("#planche-info").textContent =
    `${album ? album.titre : ""} — planche ${p.numero} · ${p.statut}`;

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

  state.webW = img.naturalWidth;
  state.webH = img.naturalHeight;
  state.webScale = state.webW / p.largeur_px;
  canvas.style.width = state.webW + "px";
  canvas.style.height = state.webH + "px";
  overlay.setAttribute("width", state.webW);
  overlay.setAttribute("height", state.webH);
  overlay.setAttribute("viewBox", `0 0 ${p.largeur_px} ${p.hauteur_px}`);

  await loadRegions(id);
  fitView();
  renderPanel();
}

async function loadRegions(plancheId) {
  const rows = await apiGet(`/api/planches/${plancheId}/regions`);
  state.regions = rows.map((r) => ({
    ...r,
    annotee: !!r.annotee,
    nb_enfants: r.nb_enfants || 0,
  }));
  state.regionsById = new Map(state.regions.map((r) => [r.id, r]));
  renderOverlay();
  updateStatus();
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
function regionsAtLevel() {
  return state.regions.filter((r) => (r.parent_id ?? null) === state.hierParent);
}

function svg(tag, attrs) {
  const el = document.createElementNS(SVGNS, tag);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  return el;
}

function renderOverlay() {
  overlay.innerHTML = "";
  if (!state.planche) return;

  // Contexte : si on est dans un sous-niveau, on dessine le parent en pointillé.
  if (state.hierParent != null) {
    const parent = state.regionsById.get(state.hierParent);
    if (parent) {
      overlay.appendChild(svg("rect", {
        x: parent.x, y: parent.y, width: parent.w, height: parent.h,
        class: "region dimmed", "pointer-events": "none",
      }));
    }
  }

  const gRegions = svg("g", { id: "regions-group" });
  for (const r of regionsAtLevel()) {
    const cls = ["region"];
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
    label.textContent = `${r.ordre ?? "?"}·${r.type[0]}`;
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
  if (!r || (r.parent_id ?? null) !== state.hierParent) return;

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
function selectRegion(id) {
  flushSave();
  state.selectedId = id;
  renderOverlay();
  renderPanel();
  if (state.mode === "annotation" && id != null) loadAnnotation(id);
}

function selectedRegion() {
  return state.selectedId != null ? state.regionsById.get(state.selectedId) : null;
}

/* ===================================================================
   Panneau droit
   =================================================================== */
function renderPanel() {
  const r = selectedRegion();
  $("#panel-empty").hidden = !!r;
  $("#panel-content").hidden = !r;
  if (!r) { renderBreadcrumb(); return; }

  $("#region-id").textContent = "#" + r.id;
  $("#region-type").value = r.type;
  $("#region-source").textContent = r.source;

  $("#panel-edition").hidden = state.mode !== "edition";
  $("#panel-annotation").hidden = state.mode !== "annotation";

  $("#coord-x").value = r.x;
  $("#coord-y").value = r.y;
  $("#coord-w").value = r.w;
  $("#coord-h").value = r.h;

  $("#panel-ocr").hidden = !r.ocr_texte;
  if (r.ocr_texte) $("#ocr-text").textContent = r.ocr_texte;

  renderChildren(r);
  renderBreadcrumb();
}

function renderChildren(r) {
  const box = $("#children-list");
  box.innerHTML = "";
  const kids = state.regions.filter((c) => c.parent_id === r.id);
  if (!kids.length) {
    box.innerHTML = '<span class="muted small">Aucune sous-région.</span>';
  } else {
    for (const c of kids) {
      const div = document.createElement("div");
      div.className = "child-item";
      div.innerHTML = `<span class="type">${c.type}</span>` +
        `<span class="muted">#${c.id}</span>` +
        (c.annotee ? '<span style="margin-left:auto;color:var(--accent-green)">●</span>' : "");
      div.onclick = () => { drillTo(r.id); selectRegion(c.id); };
      box.appendChild(div);
    }
  }
  $("#btn-enter").hidden = false;
  $("#btn-enter").onclick = () => drillTo(r.id);
}

function renderBreadcrumb() {
  const bc = $("#breadcrumb");
  bc.innerHTML = "";
  if (!state.planche) return;
  const path = [];
  let pid = state.hierParent;
  while (pid != null) {
    const reg = state.regionsById.get(pid);
    if (!reg) break;
    path.unshift(reg);
    pid = reg.parent_id ?? null;
  }
  const root = document.createElement("a");
  root.textContent = `Planche ${state.planche.numero}`;
  root.onclick = () => { drillTo(null); };
  bc.appendChild(root);
  for (const reg of path) {
    const sep = document.createElement("span");
    sep.className = "sep"; sep.textContent = "›";
    bc.appendChild(sep);
    const a = document.createElement("a");
    a.textContent = `${reg.type} #${reg.id}`;
    a.onclick = () => drillTo(reg.id);
    bc.appendChild(a);
  }
}

function drillTo(parentId) {
  flushSave();
  state.hierParent = parentId;
  state.selectedId = null;
  renderOverlay();
  renderPanel();
}

/* ===================================================================
   Modes
   =================================================================== */
function setMode(mode) {
  flushSave();
  state.mode = mode;
  document.querySelectorAll(".mode-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.mode === mode));
  stage.classList.toggle("mode-edition", mode === "edition");
  const label = { navigation: "Navigation", edition: "Édition", annotation: "Annotation" }[mode];
  $("#stat-mode").textContent = "Mode : " + label;
  renderOverlay();
  renderPanel();
  if (mode === "annotation" && state.selectedId != null) loadAnnotation(state.selectedId);
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
  } catch (e) { toast("Erreur chargement annotation : " + e.message, "error"); }
}

function renderTagChips() {
  const box = $("#tag-chips");
  box.innerHTML = "";
  for (const label of state.currentTags) {
    const chip = document.createElement("span");
    chip.className = "tag-chip";
    const v = state.tagVocab.find((t) => t.label === label);
    if (v && v.couleur) chip.style.borderColor = v.couleur;
    chip.innerHTML = `<span>${label}</span><span class="x">×</span>`;
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
  if (id == null || state.mode !== "annotation") return;
  const note = $("#note-input").value;
  try {
    await apiSend("PUT", `/api/regions/${id}/annotation`, {
      note, tags: [...state.currentTags],
    });
    const r = state.regionsById.get(id);
    if (r) { r.annotee = !!(note || state.currentTags.length); }
    renderOverlay();
    setSaveState("saved");
    await refreshTagVocab();
    updateStatus();
  } catch (e) { toast("Échec de sauvegarde : " + e.message, "error"); }
}

async function refreshTagVocab() {
  try { state.tagVocab = await apiGet("/api/tags"); } catch (_) {}
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
      d.innerHTML = `${t.label}<span class="freq">${t.frequence}</span>`;
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

async function createRegion(x, y, w, h) {
  const type = state.hierParent == null ? "case" : "bulle";
  try {
    const created = await apiSend("POST", `/api/planches/${state.planche.id}/regions`, {
      type, x: Math.round(x), y: Math.round(y),
      w: Math.round(w), h: Math.round(h),
      parent_id: state.hierParent, source: "manuel",
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
    if (hit && Number(hit.dataset.id) === state.selectedId) {
      // déplacer la région sélectionnée
      const r = selectedRegion();
      drag = { kind: "move", start: clientToMaster(e), orig: { x: r.x, y: r.y } };
    } else if (hit) {
      selectRegion(Number(hit.dataset.id));
    } else {
      // dessiner une nouvelle région
      const p = clientToMaster(e);
      drag = { kind: "draw", start: p };
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

function resizeFrom(d, p) {
  const r = selectedRegion();
  let { x, y, w, h } = d.orig;
  const dx = p.x - d.start.x, dy = p.y - d.start.y;
  if (d.dir.includes("e")) w = d.orig.w + dx;
  if (d.dir.includes("s")) h = d.orig.h + dy;
  if (d.dir.includes("w")) { x = d.orig.x + dx; w = d.orig.w - dx; }
  if (d.dir.includes("n")) { y = d.orig.y + dy; h = d.orig.h - dy; }
  // Empêche les dimensions négatives.
  if (w < 1) { w = 1; }
  if (h < 1) { h = 1; }
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
  const list = regionsAtLevel().sort((a, b) => (a.ordre || 0) - (b.ordre || 0) || a.id - b.id);
  if (!list.length) return;
  let idx = list.findIndex((r) => r.id === state.selectedId);
  idx = idx === -1 ? 0 : (idx + dir + list.length) % list.length;
  selectRegion(list[idx].id);
}

/* ===================================================================
   Barre de statut
   =================================================================== */
function updateStatus() {
  const total = state.regions.length;
  const annot = state.regions.filter((r) => r.annotee).length;
  $("#stat-cases").textContent = `${total} régions`;
  $("#stat-annotees").textContent = `${annot} annotées`;
  // met à jour le compteur dans la liste latérale
  const p = state.planche;
  if (p) { p.nb_regions = total; p.nb_annotees = annot; renderPlancheList(); }
}

/* ===================================================================
   Actions : segmenter, importer, nouvel album, export
   =================================================================== */
async function segmenter() {
  if (!state.planche) return;
  toast("Segmentation en cours…");
  try {
    const res = await apiSend("POST", `/api/planches/${state.planche.id}/segmenter`);
    state.planche.statut = "segmentee";
    await loadRegions(state.planche.id);
    toast(`${res.nb_cases} cases détectées`, "success");
  } catch (e) { toast("Segmentation : " + e.message, "error"); }
}

async function detecterBulles() {
  if (!state.planche) return;
  toast("Détection des bulles…");
  try {
    const res = await apiSend("POST", `/api/planches/${state.planche.id}/detecter-bulles`);
    await loadRegions(state.planche.id);
    toast(`${res.nb_bulles} bulles détectées` +
          (res.sans_case ? ` (${res.sans_case} hors case)` : ""), "success");
  } catch (e) { toast("Bulles : " + e.message, "error"); }
}

async function lancerOCR() {
  if (!state.planche) return;
  toast("OCR en cours… (premier appel : chargement du modèle)");
  try {
    const res = await apiSend("POST", `/api/planches/${state.planche.id}/ocr`);
    await loadRegions(state.planche.id);
    toast(`OCR : ${res.ocr} régions pré-remplies` +
          (res.ignores ? `, ${res.ignores} déjà faites` : ""), "success");
  } catch (e) { toast("OCR : " + e.message, "error"); }
}

function setupImport() {
  $("#btn-import").onclick = () => {
    if (!state.albumId) { toast("Créez d'abord un album", "error"); return; }
    $("#file-input").click();
  };
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

function setupExport() {
  const btn = $("#btn-export"), menu = $("#export-menu");
  btn.onclick = (e) => { e.stopPropagation(); menu.classList.toggle("open"); };
  document.addEventListener("click", () => menu.classList.remove("open"));
  menu.querySelectorAll("a").forEach((a) => {
    a.onclick = () => {
      if (!state.albumId) { toast("Aucun album", "error"); return; }
      window.open(`${API}/api/export/${a.dataset.fmt}?album_id=${state.albumId}`, "_blank");
      menu.classList.remove("open");
    };
  });
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
  $("#zoom-in").onclick = () => { const r = stage.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1.2); };
  $("#zoom-out").onclick = () => { const r = stage.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1 / 1.2); };
  $("#zoom-fit").onclick = fitView;
  $("#zoom-reset").onclick = () => { state.zoom = 1; applyTransform(); };

  // Panneau : type & coordonnées
  $("#region-type").onchange = (e) => {
    if (state.selectedId != null) patchRegion(state.selectedId, { type: e.target.value });
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

  // Annotation : note
  $("#note-input").addEventListener("input", scheduleSave);

  setupTagInput();
  setupImport();
  setupExport();
}

function setupKeyboard() {
  window.addEventListener("keydown", (e) => {
    const tag = (e.target.tagName || "").toLowerCase();
    const typing = tag === "input" || tag === "textarea" || tag === "select";
    if (typing) return;

    const k = e.key.toLowerCase();
    if (k === "n") setMode("navigation");
    else if (k === "e") setMode("edition");
    else if (k === "a") setMode("annotation");
    else if (e.key === "ArrowRight") { navigateRegion(1); e.preventDefault(); }
    else if (e.key === "ArrowLeft") { navigateRegion(-1); e.preventDefault(); }
    else if (e.key === "Delete" &&
             state.mode === "edition" && state.selectedId != null) {
      deleteRegion(state.selectedId); e.preventDefault();
    } else if (e.key === "Escape") {
      const dr = overlay.querySelector("#draw-rect");
      if (dr) dr.remove();
      drag = null;
      state.selectedId = null; renderOverlay(); renderPanel();
    }
  });
}

/* ===================================================================
   Démarrage
   =================================================================== */
async function init() {
  setupControls();
  setupKeyboard();
  setMode("navigation");
  window.addEventListener("resize", () => { if (state.planche) applyTransform(); });
  try {
    await refreshTagVocab();
    await loadAlbums();
  } catch (e) {
    toast("Erreur de chargement : " + e.message, "error");
  }
}

init();
