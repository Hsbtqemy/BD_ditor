/* ===================================================================
   BD Annotator — page Bibliothèque / gestion de corpus (vanilla JS)
   Gère les albums (CRUD + métadonnées), les planches (ouvrir/supprimer)
   et le traitement par lot (segmentation / bulles / OCR) en arrière-plan.
   =================================================================== */
"use strict";

const $ = (s) => document.querySelector(s);
const PASSES = ["segmenter", "bulles", "ocr"];

const state = {
  albums: [],
  openId: null,
  planches: [],
  checkedAlbums: new Set(),
  checkedPlanches: new Set(),
  editingId: null,
  jobTimer: null,
};

async function apiGet(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
async function apiSend(method, path, body) {
  const r = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.status === 204 ? null : r.json();
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function toast(msg, kind = "") {
  let box = $("#toasts");
  if (!box) { box = document.createElement("div"); box.id = "toasts"; document.body.appendChild(box); }
  const el = document.createElement("div");
  el.className = "toast " + kind; el.textContent = msg;
  box.appendChild(el); setTimeout(() => el.remove(), 4000);
}

/* ---------------- Albums ---------------- */
async function loadAlbums() {
  state.albums = await apiGet("/api/albums");
  // purge les sélections d'albums disparus
  const ids = new Set(state.albums.map((a) => a.id));
  state.checkedAlbums.forEach((id) => { if (!ids.has(id)) state.checkedAlbums.delete(id); });
  renderAlbums();
  if (state.openId != null && ids.has(state.openId)) openAlbum(state.openId);
  else { state.openId = null; $("#album-detail").hidden = true; }
  updateSelInfo();
}

function renderAlbums() {
  const body = $("#albums-body");
  body.innerHTML = "";
  if (!state.albums.length) {
    body.innerHTML = '<tr><td colspan="9" class="empty-cell">Aucun album. Créez-en un.</td></tr>';
    return;
  }
  for (const a of state.albums) {
    const tr = document.createElement("tr");
    tr.className = "album-row" + (a.id === state.openId ? " open" : "");
    tr.innerHTML =
      `<td class="c-chk"><input type="checkbox" ${state.checkedAlbums.has(a.id) ? "checked" : ""}></td>` +
      `<td class="c-titre">${esc(a.titre)}</td>` +
      `<td>${esc(a.serie || "")}</td><td>${esc(a.auteur || "")}</td>` +
      `<td class="c-num">${a.annee || ""}</td>` +
      `<td class="c-num">${a.nb_planches}</td>` +
      `<td class="c-num">${a.nb_regions}</td>` +
      `<td class="c-num">${a.nb_transcrites}</td>` +
      `<td class="c-act">` +
        `<button class="icon-btn" data-act="edit" title="Éditer les métadonnées">✎</button> ` +
        `<button class="icon-btn danger" data-act="del" title="Supprimer l'album">🗑</button>` +
      `</td>`;
    tr.querySelector("input").onchange = (e) => {
      e.target.checked ? state.checkedAlbums.add(a.id) : state.checkedAlbums.delete(a.id);
      updateSelInfo();
    };
    tr.querySelector('[data-act="edit"]').onclick = (e) => { e.stopPropagation(); openModal(a); };
    tr.querySelector('[data-act="del"]').onclick = (e) => { e.stopPropagation(); deleteAlbum(a); };
    tr.onclick = (e) => { if (e.target.tagName !== "INPUT") openAlbum(a.id); };
    body.appendChild(tr);
  }
}

async function openAlbum(id) {
  // La sélection de planches est propre à l'album ouvert (les cases ne sont
  // visibles que pour lui) → on la vide quand on change d'album.
  if (id !== state.openId) { state.checkedPlanches.clear(); updateSelInfo(); }
  state.openId = id;
  try { state.planches = await apiGet(`/api/albums/${id}/planches`); }
  catch (e) { toast("Album : " + e.message, "error"); return; }
  renderAlbums();
  renderDetail();
}

function renderDetail() {
  const a = state.albums.find((x) => x.id === state.openId);
  const box = $("#album-detail");
  if (!a) { box.hidden = true; return; }
  box.hidden = false;
  const planchesRows = state.planches.length
    ? state.planches.map((p) => `
        <tr>
          <td class="c-chk"><input type="checkbox" data-pid="${p.id}" ${state.checkedPlanches.has(p.id) ? "checked" : ""}></td>
          <td><img class="pl-thumb" loading="lazy" src="${p.url_web || ""}" alt=""></td>
          <td>p.${String(p.numero).padStart(3, "0")}</td>
          <td><span class="statut-pill statut-${p.statut}"></span> ${p.statut}</td>
          <td class="c-num">${p.nb_regions} rég.</td>
          <td class="c-num">${p.nb_annotees} ann.</td>
          <td class="c-act">
            <a class="icon-btn" href="/?album=${a.id}&planche=${p.id}" title="Ouvrir dans la visionneuse">↗</a>
            <button class="icon-btn danger" data-delp="${p.id}" title="Supprimer la planche">🗑</button>
          </td>
        </tr>`).join("")
    : '<tr><td colspan="7" class="empty-cell">Aucune planche. Importez-en depuis la visionneuse ou ShareDocs.</td></tr>';

  box.innerHTML = `
    <div class="detail-head">
      <h3>${esc(a.titre)} ${a.annee ? `<span class="muted">(${a.annee})</span>` : ""}</h3>
      <div class="detail-meta muted small">
        ${a.serie ? "Série : " + esc(a.serie) + " · " : ""}${a.auteur ? "Auteur : " + esc(a.auteur) + " · " : ""}
        ${a.editeur ? "Éditeur : " + esc(a.editeur) : ""}
      </div>
      ${a.description ? `<p class="detail-desc">${esc(a.description)}</p>` : ""}
      <button class="ghost small" id="detail-edit">✎ Éditer l'album</button>
    </div>
    <table class="corpus-table planches-table">
      <thead><tr><th class="c-chk"></th><th></th><th>N°</th><th>Statut</th>
        <th class="c-num">Régions</th><th class="c-num">Annotées</th><th></th></tr></thead>
      <tbody>${planchesRows}</tbody>
    </table>`;

  $("#detail-edit").onclick = () => openModal(a);
  box.querySelectorAll("input[data-pid]").forEach((cb) => {
    cb.onchange = () => {
      const pid = Number(cb.dataset.pid);
      cb.checked ? state.checkedPlanches.add(pid) : state.checkedPlanches.delete(pid);
      updateSelInfo();
    };
  });
  box.querySelectorAll("button[data-delp]").forEach((btn) => {
    btn.onclick = () => deletePlanche(Number(btn.dataset.delp));
  });
}

/* ---------------- Création / édition ---------------- */
function openModal(album) {
  state.editingId = album ? album.id : null;
  $("#modal-title").textContent = album ? "Éditer l'album" : "Nouvel album";
  $("#m-titre").value = album ? album.titre : "";
  $("#m-serie").value = (album && album.serie) || "";
  $("#m-auteur").value = (album && album.auteur) || "";
  $("#m-annee").value = (album && album.annee) || "";
  $("#m-editeur").value = (album && album.editeur) || "";
  $("#m-desc").value = (album && album.description) || "";
  $("#m-msg").textContent = "";
  $("#album-modal").hidden = false;
  $("#m-titre").focus();
}
function closeModal() { $("#album-modal").hidden = true; }

async function saveAlbum() {
  const titre = $("#m-titre").value.trim();
  if (!titre) { $("#m-msg").textContent = "Titre requis."; return; }
  const annee = parseInt($("#m-annee").value, 10);
  const body = {
    titre,
    serie: $("#m-serie").value.trim() || null,
    auteur: $("#m-auteur").value.trim() || null,
    annee: isNaN(annee) ? null : annee,
    editeur: $("#m-editeur").value.trim() || null,
    description: $("#m-desc").value.trim() || null,
  };
  try {
    if (state.editingId) await apiSend("PUT", `/api/albums/${state.editingId}`, body);
    else await apiSend("POST", "/api/albums", body);
    closeModal();
    await loadAlbums();
    toast("Album enregistré", "success");
  } catch (e) { $("#m-msg").textContent = "✗ " + e.message; }
}

async function deleteAlbum(a) {
  if (!confirm(`Supprimer l'album « ${a.titre} » et toutes ses planches/annotations ? Irréversible.`)) return;
  try {
    await apiSend("DELETE", `/api/albums/${a.id}`);
    state.checkedAlbums.delete(a.id);
    if (state.openId === a.id) state.openId = null;
    await loadAlbums();
    toast("Album supprimé");
  } catch (e) { toast("Suppression : " + e.message, "error"); }
}

async function deletePlanche(pid) {
  if (!confirm("Supprimer cette planche et ses régions ? Irréversible.")) return;
  try {
    await apiSend("DELETE", `/api/planches/${pid}`);
    state.checkedPlanches.delete(pid);
    await openAlbum(state.openId);
    await loadAlbums();          // met à jour les compteurs de la table
    toast("Planche supprimée");
  } catch (e) { toast("Suppression : " + e.message, "error"); }
}

/* ---------------- Traitement par lot ---------------- */
function selectedPasses() {
  return PASSES.filter((p) => $("#pass-" + p).checked);
}
function updateSelInfo() {
  const na = state.checkedAlbums.size, np = state.checkedPlanches.size;
  $("#sel-info").textContent = (na || np)
    ? `${na} album${na > 1 ? "s" : ""}${np ? ` + ${np} planche${np > 1 ? "s" : ""}` : ""}`
    : "rien de sélectionné";
  $("#btn-run").disabled = !(selectedPasses().length && (na || np));
}

async function runBatch() {
  const passes = selectedPasses();
  if (!passes.length || !(state.checkedAlbums.size || state.checkedPlanches.size)) return;
  try {
    const job = await apiSend("POST", "/api/jobs", {
      passes,
      album_ids: [...state.checkedAlbums],
      planche_ids: [...state.checkedPlanches],
    });
    toast(`Lot lancé : ${job.total} planche${job.total > 1 ? "s" : ""}`, "success");
    pollJobs();
  } catch (e) { toast("Lot : " + e.message, "error"); }
}

async function pollJobs() {
  let list = [];
  try { list = await apiGet("/api/jobs"); } catch (e) { return; }
  renderJobs(list);
  const actifs = list.some((j) => j.status === "en_cours");
  clearTimeout(state.jobTimer);
  if (actifs) {
    state.jobTimer = setTimeout(pollJobs, 1000);
  } else if (list.length) {
    await loadAlbums();          // compteurs à jour une fois le lot fini
  }
}

function renderJobs(list) {
  const box = $("#jobs");
  const recents = list.slice(0, 4);   // les plus récents (all_jobs trie décroissant)
  if (!recents.length) { box.innerHTML = ""; return; }
  box.innerHTML = recents.map((j) => {
    const pct = j.total ? Math.round(100 * j.done / j.total) : 0;
    const label = { en_cours: "en cours", termine: "terminé", annule: "annulé" }[j.status] || j.status;
    const err = j.errors.length ? ` · <span class="job-err">${j.errors.length} erreur(s)</span>` : "";
    return `<div class="job job-${j.status}">
      <div class="job-line">
        <b>Job #${j.id}</b> <span class="muted small">${j.passes.join(" → ")}</span>
        <span class="job-state">${label} — ${j.done}/${j.total}${err}</span>
        ${j.status === "en_cours" ? `<button class="ghost small" data-cancel="${j.id}">Annuler</button>` : ""}
      </div>
      <div class="job-bar"><div class="job-fill" style="width:${pct}%"></div></div>
    </div>`;
  }).join("");
  box.querySelectorAll("button[data-cancel]").forEach((btn) => {
    btn.onclick = async () => {
      try { await apiSend("POST", `/api/jobs/${btn.dataset.cancel}/annuler`); pollJobs(); }
      catch (e) { toast("Annulation : " + e.message, "error"); }
    };
  });
}

/* ---------------- Démarrage ---------------- */
function setup() {
  $("#btn-new").onclick = () => openModal(null);
  $("#m-save").onclick = saveAlbum;
  $("#m-cancel").onclick = closeModal;
  $("#album-modal").addEventListener("mousedown", (e) => {
    if (e.target.id === "album-modal") closeModal();
  });
  PASSES.forEach((p) => { $("#pass-" + p).onchange = updateSelInfo; });
  $("#btn-run").onclick = runBatch;
  loadAlbums();
  pollJobs();     // reprend l'affichage d'un éventuel job déjà en cours
}

setup();
