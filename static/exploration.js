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
const UPOS = ["ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN", "NUM",
              "PART", "PRON", "PROPN", "PUNCT", "SCONJ", "SYM", "VERB", "X"];
const state = { timer: null, gen: 0 };

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
      ["transcrites", "transcrites"],
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

/* ---------------- Paramètres ---------------- */
function champ() { return $("#f-champ").value; }
function compareOn() { return $("#f-compare").checked; }

/* Filtres d'un côté (préfixe "f" = A, "b" = B) → {album,type,pos,morph,provenance}. */
function sideFilters(pre) {
  const g = (k) => ($(`#${pre}-${k}`).value || "").trim();
  const f = { album: g("album"), type: g("type"), morph: g("morph"), provenance: g("prov") };
  if (champ() !== "pos") f.pos = g("pos");   // filtre POS redondant si on distribue par POS
  return f;
}

/* URL/état : champ + compare + filtres A (nus) + filtres B (préfixés b_). */
function stateParams() {
  const p = new URLSearchParams();
  p.set("champ", champ());
  const a = sideFilters("f");
  for (const [k, v] of Object.entries(a)) if (v) p.set(k, v);
  if (compareOn()) {
    p.set("compare", "1");
    const b = sideFilters("b");
    for (const [k, v] of Object.entries(b)) if (v) p.set("b_" + k, v);
  }
  return p;
}

/* Descente aux preuves : Recherche pré-filtrée sur la valeur + les filtres du côté. */
function drillUrl(valeur, filtres) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(filtres)) if (v) p.set(k, v);
  p.set(champ(), valeur);
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
    apiGet("/api/analyse/comparaison?" + p.toString()).then(done(renderComparaison)).catch(fail);
  } else {
    const p = new URLSearchParams();
    p.set("champ", champ());
    for (const [k, v] of Object.entries(sideFilters("f"))) if (v) p.set(k, v);
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
    if (v !== "") { row.href = drillUrl(v, fa); row.title = "Voir les emplois en contexte"; }
    row.innerHTML =
      `<span class="dist-label">${esc(label)}${sub}</span>` +
      `<span class="dist-bar"><i style="width:${(100 * r.freq / max).toFixed(1)}%"></i></span>` +
      `<span class="dist-freq">${r.freq}</span>`;
    box.appendChild(row);
  }
}

/* ---------------- Rendu : comparaison A / B ---------------- */
function compColumn(items, side, filtres) {
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
      : `<a class="dist-row" href="${esc(drillUrl(v, filtres))}" title="Voir les emplois en contexte">${inner}</a>`;
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
    `<div class="comp-col"><h3 class="comp-h">Sur-représentés en A</h3>` +
      `<div class="dist">${compColumn(res.sur_a, "a", sideFilters("f"))}</div></div>` +
    `<div class="comp-col"><h3 class="comp-h">Sur-représentés en B</h3>` +
      `<div class="dist">${compColumn(res.sur_b, "b", sideFilters("b"))}</div></div>`;
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
  };
  setSide("f", (k) => k);              // A = paramètres nus
  setSide("b", (k) => "b_" + k);       // B = préfixés
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
  ["#f-album", "#f-type", "#f-pos", "#f-prov",
   "#b-album", "#b-type", "#b-pos", "#b-prov"].forEach((s) => { $(s).onchange = run; });
  loadCorpus();
  await loadAlbums();        // options d'album (A et B) avant restauration
  restoreFromUrl();
  syncControls();
  run();
}

setup();
