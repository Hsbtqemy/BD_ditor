/* ===================================================================
   BD Annotator — page Exploration (vanilla JS)
   Distributions de fréquence (lemme / POS / morph) sur les valeurs EFFECTIVES,
   via /api/analyse/frequences (socle du lot 2). Filtres combinables ; cliquer une
   valeur DESCEND aux preuves (Recherche pré-filtrée). État dans l'URL (partageable).
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

/* ---------------- En-tête : volumétrie ---------------- */
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
    const sel = $("#f-album");
    for (const a of albums) {
      const o = document.createElement("option");
      o.value = String(a.id);
      o.textContent = `${a.serie ? a.serie + " · " : ""}${a.titre}`;
      sel.appendChild(o);
    }
  } catch (e) { /* ignore */ }
}

/* ---------------- Paramètres / URL ---------------- */
function champ() { return $("#f-champ").value; }

/* Paramètres de distribution (vers /api/analyse/frequences ET l'URL). */
function distParams() {
  const p = new URLSearchParams();
  const set = (k, v) => { if (v && v.trim()) p.set(k, v.trim()); };
  set("champ", $("#f-champ").value);
  set("album", $("#f-album").value);
  set("type", $("#f-type").value);
  if ($("#f-champ").value !== "pos") set("pos", $("#f-pos").value);  // filtre POS redondant si on distribue par POS
  set("morph", $("#f-morph").value);
  set("provenance", $("#f-prov").value);
  return p;
}

/* URL de descente aux preuves : Recherche pré-filtrée sur la valeur cliquée
   (le champ courant devient une facette) + les mêmes filtres de sous-corpus. */
function drillUrl(valeur) {
  const p = distParams();
  p.delete("champ");
  p.set(champ(), valeur);     // lemme | pos | morph = valeur cliquée
  return "/recherche?" + p.toString();
}

/* ---------------- Distribution ---------------- */
function run() {
  const p = distParams();
  history.replaceState(null, "", "?" + p.toString());   // toujours au moins `champ`
  const url = new URLSearchParams(p); url.set("limit", "200");
  const gen = ++state.gen;
  $("#dist-info").textContent = "Calcul…";
  apiGet("/api/analyse/frequences?" + url.toString())
    .then((res) => { if (gen === state.gen) renderDist(res); })
    .catch((e) => { if (gen === state.gen) $("#dist-info").textContent = "Erreur : " + e.message; });
}

function valeurDe(r, ch) {
  if (ch === "lemme") return r.lemme;
  if (ch === "pos") return r.pos;
  return r.morph;           // peut être "" (aucun trait)
}

function renderDist(res) {
  const ch = res.champ;
  const rows = res.results || [];
  const box = $("#dist");
  box.innerHTML = "";
  if (!rows.length) {
    $("#dist-info").textContent = "Aucune donnée (relancer l'indexation NLP ?).";
    return;
  }
  const total = rows.reduce((s, r) => s + r.freq, 0);
  const max = Math.max(...rows.map((r) => r.freq));
  $("#dist-info").innerHTML =
    `${rows.length} valeur(s) de <b>${esc(ch)}</b> · ${total} occurrence(s)` +
    (rows.length >= 200 ? " (limité aux 200 plus fréquentes)" : "") +
    ` — cliquer une valeur pour voir les emplois en contexte`;
  for (const r of rows) {
    const v = valeurDe(r, ch);
    const label = v === "" ? "∅ (aucun trait)" : v;
    const sub = (ch === "lemme" && r.pos) ? ` <span class="dist-pos">${esc(r.pos)}</span>` : "";
    const row = document.createElement(v === "" ? "div" : "a");
    row.className = "dist-row";
    if (v !== "") { row.href = drillUrl(v); row.title = "Voir les emplois en contexte"; }
    row.innerHTML =
      `<span class="dist-label">${esc(label)}${sub}</span>` +
      `<span class="dist-bar"><i style="width:${(100 * r.freq / max).toFixed(1)}%"></i></span>` +
      `<span class="dist-freq">${r.freq}</span>`;
    box.appendChild(row);
  }
}

/* ---------------- Démarrage ---------------- */
function restoreFromUrl() {
  const p = new URLSearchParams(INITIAL_QS);
  $("#f-champ").value = p.get("champ") || "lemme";
  $("#f-album").value = p.get("album") || "";
  $("#f-type").value = p.get("type") || "";
  $("#f-pos").value = p.get("pos") || "";
  $("#f-morph").value = p.get("morph") || "";
  $("#f-prov").value = p.get("provenance") || "";
}

async function setup() {
  for (const u of UPOS) {
    const o = document.createElement("option"); o.value = u; o.textContent = u;
    $("#f-pos").appendChild(o);
  }
  const deb = () => { clearTimeout(state.timer); state.timer = setTimeout(run, 300); };
  $("#f-morph").addEventListener("input", deb);
  $("#f-champ").onchange = () => { syncControls(); run(); };
  ["#f-album", "#f-type", "#f-pos", "#f-prov"].forEach((s) => { $(s).onchange = run; });
  loadCorpus();
  await loadAlbums();        // options d'album avant restauration
  restoreFromUrl();
  syncControls();
  run();
}

/* Désactive le filtre POS quand on distribue PAR POS (redondant). */
function syncControls() {
  $("#f-pos").disabled = ($("#f-champ").value === "pos");
}

setup();
