/* ===================================================================
   BD Annotator — page Exploration (vanilla JS)
   • Distribution simple (lemme / POS / morph) d'un sous-corpus, OU
   • Comparaison de deux sous-corpus A / B (fréquences différentielles).
   Sur les valeurs EFFECTIVES (socle lot 2). Cliquer une valeur DESCEND aux preuves
   (Recherche pré-filtrée). État dans l'URL (partageable).
   =================================================================== */
"use strict";

const $ = (s) => document.querySelector(s);
const INITIAL_QS = location.search;
// `retour` validé : page interne seulement (cf. static/lib/nav.js → anti open-redirect/XSS).
const RETOUR = Nav.safeRetour(new URLSearchParams(INITIAL_QS).get("retour"));   // d'où l'on vient (si inbound)
const UPOS = ["ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN", "NUM",
              "PART", "PRON", "PROPN", "PUNCT", "SCONJ", "SYM", "VERB", "X"];
// Libellé de la cible d'une dimension (lève l'ambiguïté entre dimensions homonymes :
// une « origine » de personnage et une « origine » de case ne se confondent plus).
const CIBLE_LBL = { personnage: "locuteur", case: "scène" };
let ATTR_CATALOGUE = [];   // valeurs d'attribut à plat (cible→dim→valeur) — source des puces
const state = { timer: null, gen: 0, attributs: { f: new Set(), b: new Set() } };

async function apiGet(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function loadCorpus() {
  try {
    const c = await apiGet("/api/corpus");
    $("#corpus-stats").innerHTML = [
      ["albums", "albums"], ["planches", "planches"], ["regions", "régions"],
      ["transcrites", "transcrites"], ["annotees", "annotées"], ["tags", "tags"],
    ].map(([k, lbl]) => `<span class="stat"><b>${c[k]}</b> ${lbl}</span>`).join("");
  } catch (e) { /* non bloquant */ }
}

async function loadAlbums() {
  try {
    const albums = await apiGet("/api/albums");
    for (const id of ["#f-album", "#b-album"]) {
      const sel = $(id);
      for (const a of albums) {
        const o = document.createElement("option");
        o.value = String(a.id);
        o.textContent = `${a.serie ? a.serie + " · " : ""}${a.titre}`;
        sel.appendChild(o);
      }
    }
  } catch (e) { /* ignore */ }
}

async function loadTags() {
  try {
    const tags = await apiGet("/api/tags");
    for (const id of ["#f-tags", "#b-tags"]) {
      const sel = $(id);
      for (const t of tags) {
        const o = document.createElement("option");
        o.value = t.label;
        o.textContent = `${t.label} (${t.frequence})`;
        sel.appendChild(o);
      }
    }
  } catch (e) { /* ignore */ }
}

/* ---------------- Paramètres ---------------- */
function champ() { return $("#f-champ").value; }
function compareOn() { return $("#f-compare").checked; }

/* Filtres d'un côté (préfixe "f" = A, "b" = B) → {album,type,pos,morph,provenance}. */
function sideFilters(pre) {
  const g = (k) => ($(`#${pre}-${k}`).value || "").trim();
  const f = { album: g("album"), type: g("type"), morph: g("morph"),
              provenance: g("prov"), tags: g("tags"), personnage: g("personnage") };
  if (champ() !== "pos") f.pos = g("pos");   // filtre POS redondant si on distribue par POS
  return f;
}
// Portée du filtre tag : 'herite' (case parente incluse, défaut) ou 'propre'. Global (A+B).
function tagScope() { return $("#f-tagscope").checked ? "herite" : "propre"; }
// Attributs sélectionnés d'un côté → liste de valeur_id (ET côté backend).
function selectedAttributs(pre) {
  return [...state.attributs[pre]];
}

async function loadPersonnages() {
  try {
    const persos = await apiGet("/api/personnages");
    for (const id of ["#f-personnage", "#b-personnage"]) {
      const sel = $(id);
      for (const p of persos) {
        const o = document.createElement("option");
        o.value = String(p.id);
        o.textContent = p.nom + (p.serie ? ` · ${p.serie}` : "");
        sel.appendChild(o);
      }
    }
  } catch (e) { /* ignore */ }
}

async function loadAttributs() {
  try {
    ATTR_CATALOGUE = await apiGet("/api/attributs/valeurs");   // à plat, ordonné cible→dim→valeur
  } catch (e) { ATTR_CATALOGUE = []; }
  renderAttrChips("f");
  renderAttrChips("b");
}

/* (Re)rend les puces d'attribut d'un côté, groupées par dimension. Chaque puce est un
   bouton-bascule (toggle) : plus découvrable qu'un <select multiple> (qui imposait
   Ctrl-clic). L'état vit dans state.attributs[pre] (Set de valeur_id). */
function renderAttrChips(pre) {
  const box = $(`#${pre}-attr-chips`);
  if (!box) return;
  box.innerHTML = "";
  if (!ATTR_CATALOGUE.length) {
    box.innerHTML = '<span class="muted small">Aucun attribut défini.</span>';
    return;
  }
  const sel = state.attributs[pre];
  let curDim = null, grp = null;
  for (const v of ATTR_CATALOGUE) {
    if (v.dimension_id !== curDim) {            // nouvelle dimension → nouveau groupe
      curDim = v.dimension_id;
      grp = document.createElement("div");
      grp.className = "attr-group";
      const lbl = document.createElement("span");
      lbl.className = "attr-dim";
      lbl.textContent = `${CIBLE_LBL[v.cible] || v.cible} · ${v.dimension}`;
      grp.appendChild(lbl);
      box.appendChild(grp);
    }
    const id = String(v.id), actif = sel.has(id);
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "cloud-tag attr-chip" + (actif ? " active" : "");
    chip.dataset.vid = id;
    chip.textContent = v.valeur;
    chip.setAttribute("aria-pressed", actif ? "true" : "false");
    if (v.nb_usages != null) chip.title = `${v.nb_usages} usage(s)`;
    chip.onclick = () => {
      const on = !sel.has(id);
      if (on) sel.add(id); else sel.delete(id);
      chip.classList.toggle("active", on);
      chip.setAttribute("aria-pressed", on ? "true" : "false");
      run();
    };
    grp.appendChild(chip);
  }
}

/* URL/état : champ + compare + filtres A (nus) + filtres B (préfixés b_). */
function stateParams() {
  const p = new URLSearchParams();
  p.set("champ", champ());
  const a = sideFilters("f");
  for (const [k, v] of Object.entries(a)) if (v) p.set(k, v);
  selectedAttributs("f").forEach((v) => p.append("attributs", v));
  if (compareOn()) {
    p.set("compare", "1");
    const b = sideFilters("b");
    for (const [k, v] of Object.entries(b)) if (v) p.set("b_" + k, v);
    selectedAttributs("b").forEach((v) => p.append("b_attributs", v));
  }
  if (tagScope() === "propre") p.set("tag_scope", "propre");   // hérité = défaut, omis de l'URL
  if (RETOUR) p.set("retour", RETOUR);   // préservé : le ← Retour survit aux changements de filtre
  return p;
}

/* Descente aux preuves : Recherche pré-filtrée sur la valeur + les filtres du côté. */
function drillUrl(valeur, filtres, attributs) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(filtres)) if (v) p.set(k, v);
  p.set(champ(), valeur);
  if (filtres.tags) p.set("tag_scope", tagScope());   // Recherche filtre le tag avec le MÊME scope
  (attributs || []).forEach((v) => p.append("attributs", v));   // locuteur via filtres.personnage
  p.set("retour", location.pathname + location.search);   // pour revenir à l'Exploration
  return "/recherche?" + p.toString();
}

/* ---------------- Exécution ---------------- */
function run() {
  history.replaceState(null, "", "?" + stateParams().toString());
  const gen = ++state.gen;
  $("#dist").hidden = compareOn();
  $("#comparaison").hidden = !compareOn();
  $("#dist-info").textContent = "Calcul…";
  const done = (fn) => (res) => { if (gen === state.gen) fn(res); };
  const fail = (e) => { if (gen === state.gen) $("#dist-info").textContent = "Erreur : " + e.message; };

  if (compareOn()) {
    const p = new URLSearchParams();
    p.set("champ", champ());
    const a = sideFilters("f"), b = sideFilters("b");
    for (const [k, v] of Object.entries(a)) if (v) p.set("a_" + k, v);
    for (const [k, v] of Object.entries(b)) if (v) p.set("b_" + k, v);
    selectedAttributs("f").forEach((v) => p.append("a_attributs", v));
    selectedAttributs("b").forEach((v) => p.append("b_attributs", v));
    if (tagScope() === "propre") p.set("tag_scope", "propre");
    apiGet("/api/analyse/comparaison?" + p.toString()).then(done(renderComparaison)).catch(fail);
  } else {
    const p = new URLSearchParams();
    p.set("champ", champ());
    for (const [k, v] of Object.entries(sideFilters("f"))) if (v) p.set(k, v);
    selectedAttributs("f").forEach((v) => p.append("attributs", v));
    if (tagScope() === "propre") p.set("tag_scope", "propre");
    p.set("limit", "200");
    apiGet("/api/analyse/frequences?" + p.toString()).then(done(renderDist)).catch(fail);
  }
}

function valeurDe(r, ch) { return ch === "lemme" ? r.lemme : ch === "pos" ? r.pos : r.morph; }

/* ---------------- Rendu : distribution simple ---------------- */
function renderDist(res) {
  const ch = res.champ, rows = res.results || [], box = $("#dist");
  box.innerHTML = "";
  if (!rows.length) { $("#dist-info").textContent = "Aucune donnée (relancer l'indexation NLP ?)."; return; }
  const total = rows.reduce((s, r) => s + r.freq, 0);
  const max = Math.max(...rows.map((r) => r.freq));
  $("#dist-info").innerHTML =
    `${rows.length} valeur(s) de <b>${esc(ch)}</b> · ${total} occurrence(s)` +
    (rows.length >= 200 ? " (limité aux 200 plus fréquentes)" : "") +
    " — cliquer une valeur pour voir les emplois en contexte";
  const fa = sideFilters("f");
  for (const r of rows) {
    const v = valeurDe(r, ch);
    const label = v === "" ? "∅ (aucun trait)" : v;
    const sub = (ch === "lemme" && r.pos) ? `<span class="dist-pos">${esc(r.pos)}</span>` : "";
    const row = document.createElement(v === "" ? "div" : "a");
    row.className = "dist-row";
    if (v !== "") { row.href = drillUrl(v, fa, selectedAttributs("f")); row.title = "Voir les emplois en contexte"; }
    row.innerHTML =
      `<span class="dist-label">${esc(label)}${sub}</span>` +
      `<span class="dist-bar"><i style="width:${(100 * r.freq / max).toFixed(1)}%"></i></span>` +
      `<span class="dist-freq">${r.freq}</span>`;
    box.appendChild(row);
  }
}

/* ---------------- Rendu : comparaison A / B ---------------- */
function compColumn(items, side, filtres, attributs) {
  if (!items.length) return '<div class="muted small">—</div>';
  const max = Math.max(...items.map((x) => Math.abs(x.diff))) || 1;
  return items.map((x) => {
    const v = x.valeur, label = v === "" ? "∅ (aucun trait)" : v;
    const w = (100 * Math.abs(x.diff) / max).toFixed(1);
    const inner =
      `<span class="dist-label">${esc(label)}</span>` +
      `<span class="dist-bar"><i class="bar-${side}" style="width:${w}%"></i></span>` +
      `<span class="dist-freq" title="A:${x.freq_a} · B:${x.freq_b}">${x.freq_a}/${x.freq_b}</span>`;
    return v === ""
      ? `<div class="dist-row">${inner}</div>`
      : `<a class="dist-row" href="${esc(drillUrl(v, filtres, attributs))}" title="Voir les emplois en contexte">${inner}</a>`;
  }).join("");
}

function renderComparaison(res) {
  const box = $("#comparaison");
  $("#dist-info").innerHTML =
    `Comparaison par <b>${esc(res.champ)}</b> — A : ${res.total_a} occ. · B : ${res.total_b} occ. ` +
    "(différence de fréquence relative ; cliquer pour voir en contexte)";
  if (!res.total_a && !res.total_b) {
    box.innerHTML = '<div class="muted small">Aucune donnée dans ces sous-corpus.</div>';
    return;
  }
  box.innerHTML =
    `<div class="comp-col col-a"><h3 class="comp-h">▲ Sur-représentés en A</h3>` +
      `<div class="dist">${compColumn(res.sur_a, "a", sideFilters("f"), selectedAttributs("f"))}</div></div>` +
    `<div class="comp-col col-b"><h3 class="comp-h">▲ Sur-représentés en B</h3>` +
      `<div class="dist">${compColumn(res.sur_b, "b", sideFilters("b"), selectedAttributs("b"))}</div></div>`;
}

/* ---------------- Contrôles / démarrage ---------------- */
function syncControls() {
  const cmp = compareOn();
  $("#sub-b").hidden = !cmp;
  document.querySelectorAll(".sub-title").forEach((el) => { el.hidden = !cmp; });
  const byPos = champ() === "pos";
  $("#f-pos").disabled = byPos;     // filtre POS redondant si on distribue par POS
  $("#b-pos").disabled = byPos;
}

function restoreFromUrl() {
  const p = new URLSearchParams(INITIAL_QS);
  $("#f-champ").value = p.get("champ") || "lemme";
  $("#f-compare").checked = p.get("compare") === "1";
  const setSide = (pre, keyfn) => {
    $(`#${pre}-album`).value = p.get(keyfn("album")) || "";
    $(`#${pre}-type`).value = p.get(keyfn("type")) || "";
    $(`#${pre}-pos`).value = p.get(keyfn("pos")) || "";
    $(`#${pre}-morph`).value = p.get(keyfn("morph")) || "";
    $(`#${pre}-prov`).value = p.get(keyfn("provenance")) || "";
    $(`#${pre}-tags`).value = p.get(keyfn("tags")) || "";
    $(`#${pre}-personnage`).value = p.get(keyfn("personnage")) || "";
  };
  setSide("f", (k) => k);              // A = paramètres nus
  setSide("b", (k) => "b_" + k);       // B = préfixés
  state.attributs.f = new Set(p.getAll("attributs"));
  state.attributs.b = new Set(p.getAll("b_attributs"));
  renderAttrChips("f");                // reflète l'état restauré sur les puces
  renderAttrChips("b");
  $("#f-tagscope").checked = (p.get("tag_scope") || "herite") !== "propre";
}

/* Bouton « ← Retour » : revient d'où l'on vient via `retour` (ou history.back si
   l'on vient d'une autre page de l'app). Symétrique de Recherche/Visionneuse. */
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

async function setup() {
  for (const id of ["#f-pos", "#b-pos"]) {
    for (const u of UPOS) {
      const o = document.createElement("option"); o.value = u; o.textContent = u;
      $(id).appendChild(o);
    }
  }
  const deb = () => { clearTimeout(state.timer); state.timer = setTimeout(run, 300); };
  $("#f-morph").addEventListener("input", deb);
  $("#b-morph").addEventListener("input", deb);
  $("#f-champ").onchange = () => { syncControls(); run(); };
  $("#f-compare").onchange = () => { syncControls(); run(); };
  // Les puces d'attribut câblent leur propre clic (cf. renderAttrChips) — absentes d'ici.
  ["#f-album", "#f-type", "#f-pos", "#f-prov", "#f-tags", "#f-tagscope", "#f-personnage",
   "#b-album", "#b-type", "#b-pos", "#b-prov", "#b-tags", "#b-personnage"]
    .forEach((s) => { $(s).onchange = run; });
  loadCorpus();
  await loadAlbums();        // options d'album (A et B) avant restauration
  await loadTags();          // options de tag (A et B) avant restauration
  await loadPersonnages();   // locuteurs (A et B)
  await loadAttributs();     // valeurs d'attribut, groupées par dimension (A et B)
  restoreFromUrl();
  setupBack();
  syncControls();
  run();
}

setup();
