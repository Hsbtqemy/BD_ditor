/* ===================================================================
   BD Annotator — page de recherche / index (vanilla JS)
   Interroge /api/recherche (FTS5) + /api/corpus + /api/tags + /api/albums.
   Un clic sur un résultat ouvre la visionneuse pile sur la région.
   =================================================================== */
"use strict";

const $ = (s) => document.querySelector(s);

const state = {
  albums: [],
  activeTags: new Set(),
  timer: null,
  searchGen: 0,   // jeton de fraîcheur : ignore les réponses de recherche périmées
};

const INITIAL_QS = location.search;   // état de départ (avant que search() ne réécrive l'URL)
const RETOUR = new URLSearchParams(INITIAL_QS).get("retour");   // d'où l'on vient (drill Exploration)
const UPOS = ["ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN", "NUM",
              "PART", "PRON", "PROPN", "PUNCT", "SCONJ", "SYM", "VERB", "X"];

async function apiGet(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* Surligne les termes de la requête dans un texte. On échappe le texte ET les
   termes de la même façon, pour que les apostrophes/caractères spéciaux (« D'… »
   → « D&#39;… » très fréquents en français) se retrouvent bien. */
function highlight(text, q) {
  const safe = escapeHtml(text);
  const terms = q.trim().split(/\s+/).filter(Boolean)
    .map((t) => escapeHtml(t).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!terms.length) return safe;
  const re = new RegExp("(" + terms.join("|") + ")", "gi");
  return safe.replace(re, "<mark>$1</mark>");
}

/* ---------------- Aperçu du corpus ---------------- */
async function loadCorpus() {
  try {
    const c = await apiGet("/api/corpus");
    const chips = [
      ["albums", "albums"], ["planches", "planches"], ["regions", "régions"],
      ["transcrites", "transcrites"], ["annotees", "annotées"], ["tags", "tags"],
    ];
    $("#corpus-stats").innerHTML = chips
      .map(([k, lbl]) => `<span class="stat"><b>${c[k]}</b> ${lbl}</span>`)
      .join("");
  } catch (e) { /* aperçu non bloquant */ }
}

/* ---------------- Filtres : albums + nuage de tags ---------------- */
async function loadAlbums() {
  try {
    state.albums = await apiGet("/api/albums");
    const sel = $("#f-album");
    for (const a of state.albums) {
      const o = document.createElement("option");
      o.value = String(a.id);
      o.textContent = `${a.serie ? a.serie + " · " : ""}${a.titre}`;
      sel.appendChild(o);
    }
  } catch (e) { /* ignore */ }
}

async function loadTags() {
  try {
    const tags = (await apiGet("/api/tags")).filter((t) => t.frequence > 0);
    const box = $("#tag-cloud");
    if (!tags.length) { box.innerHTML = '<span class="muted small">Aucun tag.</span>'; return; }
    const max = Math.max(...tags.map((t) => t.frequence));
    box.innerHTML = "";
    for (const t of tags) {
      const el = document.createElement("button");
      el.className = "cloud-tag";
      el.textContent = t.label;
      el.dataset.label = t.label;
      el.style.fontSize = (0.85 + 0.9 * (t.frequence / max)).toFixed(2) + "rem";
      if (t.couleur) el.style.borderColor = t.couleur;
      el.title = `${t.frequence} occurrence${t.frequence > 1 ? "s" : ""}`;
      el.onclick = () => toggleTag(t.label);
      box.appendChild(el);
    }
  } catch (e) { /* ignore */ }
}

function toggleTag(label) {
  if (state.activeTags.has(label)) state.activeTags.delete(label);
  else state.activeTags.add(label);
  renderActiveTags();
  search();
}

function renderActiveTags() {
  const box = $("#active-tags");
  box.innerHTML = "";
  for (const label of state.activeTags) {
    const chip = document.createElement("span");
    chip.className = "active-tag";
    chip.innerHTML = `<span>${escapeHtml(label)}</span><span class="x">×</span>`;
    chip.querySelector(".x").onclick = () => toggleTag(label);
    box.appendChild(chip);
  }
  document.querySelectorAll(".cloud-tag").forEach((el) =>
    el.classList.toggle("active", state.activeTags.has(el.dataset.label)));
}

/* ---------------- Recherche ---------------- */
/* Critères courants (texte + facettes corpus + facettes grammaticales) → URLSearchParams.
   `limit` exclu : l'URL reste propre/partageable, on l'ajoute juste pour la requête. */
function searchParams() {
  const p = new URLSearchParams();
  const set = (k, v) => { if (v && v.trim()) p.set(k, v.trim()); };
  set("q", $("#q").value);
  set("album", $("#f-album").value);
  set("type", $("#f-type").value);
  set("pos", $("#f-pos").value);
  set("lemme", $("#f-lemme").value);
  set("morph", $("#f-morph").value);
  set("provenance", $("#f-prov").value);
  state.activeTags.forEach((t) => p.append("tags", t));   // un param par tag
  return p;
}

function search() {
  const p = searchParams();                    // critères réels (fetch + test de vacuité)
  const vide = [...p].length === 0;
  // état dans l'URL (replaceState) → recherche partageable + rechargement sans perte ;
  // on y conserve `retour` (contexte de drill) sans l'envoyer à la requête.
  const display = new URLSearchParams(p);
  if (RETOUR) display.set("retour", RETOUR);
  history.replaceState(null, "", [...display].length ? "?" + display.toString() : location.pathname);
  if (vide) {
    $("#results").innerHTML =
      '<div class="search-hint">Tapez un mot-clé, ou choisissez un album / type / tag / facette grammaticale.</div>';
    $("#result-count").textContent = "";
    $("#btn-export").disabled = true;
    return;
  }
  const url = new URLSearchParams(p); url.set("limit", "200");
  const gen = ++state.searchGen;                    // anti-course : seule la dernière réponse rend
  $("#result-count").textContent = "Recherche…";
  apiGet("/api/recherche?" + url.toString())
    .then((res) => { if (gen === state.searchGen) renderResults(res, p.get("q") || ""); })
    .catch((e) => { if (gen === state.searchGen) $("#result-count").textContent = "Erreur : " + e.message; });
}

/* Export CSV du jeu de résultats courant (mêmes critères que la recherche affichée). */
function exportCsv() {
  const p = searchParams();
  if ([...p].length === 0) return;
  window.location = "/api/recherche/export.csv?" + p.toString();
}

/* Aperçu en place : la planche avec la région surlignée, SANS quitter la recherche.
   Le retour aux résultats se fait par le bouton Précédent (la recherche est dans l'URL). */
function openPreview(r) {
  $("#preview-title").textContent =
    `${r.album_titre} · ${r.citation ? r.citation.texte : "planche " + r.planche_numero} · ${r.type}`;
  $("#preview-edit").href = `/?album=${r.album_id}&planche=${r.planche_id}&region=${r.region_id}`;
  const img = $("#preview-img"), svg = $("#preview-overlay");
  img.src = r.url_web || "";
  svg.setAttribute("viewBox", `0 0 ${r.largeur_px || 0} ${r.hauteur_px || 0}`);
  svg.innerHTML = (r.w && r.h)
    ? `<rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" class="pv-rect"/>` : "";
  $("#preview-text").innerHTML = (r.ocr_texte || "").trim()
    ? escapeHtml(r.ocr_texte) : '<span class="muted">(sans texte)</span>';
  const tags = (r.tags || []).map((t) => `<span class="r-tag">${escapeHtml(t)}</span>`).join("");
  $("#preview-meta").innerHTML = (r.note ? "📝 " + escapeHtml(r.note) + "<br>" : "") + tags;
  $("#preview").hidden = false;
}

function closePreview() {
  $("#preview").hidden = true;
  document.querySelectorAll(".result.active").forEach((el) => el.classList.remove("active"));
}

/* Bouton « ← Retour » : cible le `retour` explicite (drill, survit au rechargement) ;
   à défaut, si on vient d'une AUTRE page de l'app, fait un history.back() — robuste
   même si la page d'origine tournait avec un ancien JS. */
function setupBack() {
  const back = $("#back-link");
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

function renderResults(res, q) {
  $("#result-count").textContent =
    `${res.count} résultat${res.count > 1 ? "s" : ""}` + (res.count >= 200 ? " (limité)" : "");
  $("#btn-export").disabled = !res.count;
  const box = $("#results");
  box.innerHTML = "";
  if (!res.results.length) {
    box.innerHTML = '<div class="search-hint">Aucun résultat.</div>';
    return;
  }
  for (const r of res.results) {
    const card = document.createElement("div");
    card.className = "result";
    card.title = "Aperçu en place (clic) — ✏️ pour éditer dans la visionneuse";

    const texte = (r.ocr_texte || "").trim();
    const noteHtml = r.note
      ? `<div class="r-note">📝 ${highlight(r.note, q)}</div>` : "";
    const tagsHtml = (r.tags || []).length
      ? `<div class="r-tags">${r.tags.map((t) => `<span class="r-tag">${escapeHtml(t)}</span>`).join("")}</div>`
      : "";

    card.innerHTML =
      `<img class="r-thumb" loading="lazy" alt=""` +
      ` src="/api/regions/${r.region_id}/crop?taille=260">` +
      `<div class="r-body">` +
        `<div class="r-text">${texte ? highlight(texte, q) : '<span class="muted">(sans texte)</span>'}</div>` +
        noteHtml + tagsHtml +
        `<div class="r-meta muted small">${escapeHtml(r.album_titre)} · ` +
        `<span class="r-cite">${escapeHtml(r.citation ? r.citation.texte : "planche " + r.planche_numero)}</span> · ` +
        `<span class="r-type">${r.type}</span></div>` +
      `</div>`;
    // une vignette illisible (crop indisponible) est simplement masquée
    card.querySelector(".r-thumb").onerror = (e) => { e.target.style.display = "none"; };
    card.onclick = () => {
      box.querySelectorAll(".result.active").forEach((el) => el.classList.remove("active"));
      card.classList.add("active");
      openPreview(r);
    };
    box.appendChild(card);
  }
}

/* ---------------- Démarrage ---------------- */
/* Restaure les critères depuis l'URL initiale (lien partagé / rechargement). À appeler
   APRÈS loadAlbums (pour que l'option d'album existe) et le peuplement des POS. */
function restoreFromUrl() {
  const p = new URLSearchParams(INITIAL_QS);
  $("#q").value = p.get("q") || "";
  $("#f-album").value = p.get("album") || "";
  $("#f-type").value = p.get("type") || "";
  $("#f-pos").value = p.get("pos") || "";
  $("#f-lemme").value = p.get("lemme") || "";
  $("#f-morph").value = p.get("morph") || "";
  $("#f-prov").value = p.get("provenance") || "";
  state.activeTags = new Set(p.getAll("tags"));
  renderActiveTags();
  if (p.get("pos") || p.get("lemme") || p.get("morph") || p.get("provenance"))
    $("#gram-facets").open = true;     // déplie si une facette grammaticale est active
}

async function setup() {
  for (const u of UPOS) {              // peuple le select POS (UPOS)
    const o = document.createElement("option"); o.value = u; o.textContent = u;
    $("#f-pos").appendChild(o);
  }
  const deb = () => { clearTimeout(state.timer); state.timer = setTimeout(search, 300); };
  $("#q").addEventListener("input", deb);
  $("#f-lemme").addEventListener("input", deb);
  $("#f-morph").addEventListener("input", deb);
  ["#f-album", "#f-type", "#f-pos", "#f-prov"].forEach((s) => { $(s).onchange = search; });
  $("#btn-export").onclick = exportCsv;   // export du jeu de résultats courant (CSV)
  $("#preview-close").onclick = closePreview;
  setupBack();   // bouton « ← Retour » (drill explicite, ou history.back si on vient de l'app)
  loadCorpus();
  loadTags();
  await loadAlbums();        // options d'album AVANT de restaurer la sélection d'album
  restoreFromUrl();
  search();                  // rejoue la recherche restaurée (ou affiche l'invite)
}

setup();
