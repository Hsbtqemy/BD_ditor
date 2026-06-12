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
};

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
function search() {
  const q = $("#q").value.trim();
  const album = $("#f-album").value;
  const type = $("#f-type").value;
  const tags = [...state.activeTags];

  if (!q && !album && !type && !tags.length) {
    $("#results").innerHTML =
      '<div class="search-hint">Tapez un mot-clé, ou choisissez un album / type / tag.</div>';
    $("#result-count").textContent = "";
    return;
  }

  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (album) params.set("album", album);
  if (type) params.set("type", type);
  if (tags.length) params.set("tags", tags.join(","));
  params.set("limit", "200");

  $("#result-count").textContent = "Recherche…";
  apiGet("/api/recherche?" + params.toString())
    .then((res) => renderResults(res, q))
    .catch((e) => { $("#result-count").textContent = "Erreur : " + e.message; });
}

function renderResults(res, q) {
  $("#result-count").textContent =
    `${res.count} résultat${res.count > 1 ? "s" : ""}` + (res.count >= 200 ? " (limité)" : "");
  const box = $("#results");
  box.innerHTML = "";
  if (!res.results.length) {
    box.innerHTML = '<div class="search-hint">Aucun résultat.</div>';
    return;
  }
  for (const r of res.results) {
    const card = document.createElement("a");
    card.className = "result";
    card.href = `/?album=${r.album_id}&planche=${r.planche_id}&region=${r.region_id}`;
    card.title = "Ouvrir dans la visionneuse";

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
        `<div class="r-meta muted small">${escapeHtml(r.album_titre)} · planche ${r.planche_numero} · ` +
        `<span class="r-type">${r.type}</span> · #${r.region_id}</div>` +
      `</div>`;
    // une vignette illisible (crop indisponible) est simplement masquée
    card.querySelector(".r-thumb").onerror = (e) => { e.target.style.display = "none"; };
    box.appendChild(card);
  }
}

/* ---------------- Démarrage ---------------- */
function setup() {
  $("#q").addEventListener("input", () => {
    clearTimeout(state.timer);
    state.timer = setTimeout(search, 300);
  });
  $("#f-album").onchange = search;
  $("#f-type").onchange = search;
  loadCorpus();
  loadAlbums();
  loadTags();
  search();   // affiche l'invite initiale
}

setup();
