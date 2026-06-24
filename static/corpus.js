/* ===================================================================
   BD Annotator — page Bibliothèque / gestion de corpus (vanilla JS)
   Gère les albums (CRUD + métadonnées), les planches (ouvrir/supprimer)
   et le traitement par lot (segmentation / bulles / OCR) en arrière-plan.
   =================================================================== */
"use strict";

// $, apiGet, apiSend, esc, toast : lib/common.js (chargé avant ce script).
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

/* Stats de corpus en bande 2 (mêmes chips que Recherche / Exploration — source
   /api/corpus). Aperçu non bloquant. */
async function loadCorpus() {
  try {
    const c = await apiGet("/api/corpus");
    $("#corpus-stats").innerHTML = [
      ["albums", "albums"], ["planches", "planches"], ["regions", "régions"],
      ["transcrites", "transcrites"], ["annotees", "annotées"], ["tags", "tags"],
    ].map(([k, lbl]) => `<span class="stat"><b>${c[k]}</b> ${lbl}</span>`).join("");
  } catch (e) { /* non bloquant */ }
}

/* ---------------- Albums ---------------- */
async function loadAlbums() {
  state.albums = await apiGet("/api/albums");
  // purge les sélections d'albums disparus
  const ids = new Set(state.albums.map((a) => a.id));
  state.checkedAlbums.forEach((id) => { if (!ids.has(id)) state.checkedAlbums.delete(id); });
  renderAlbums();
  if (state.openId != null && ids.has(state.openId)) openAlbum(state.openId);
  else { state.openId = null; state.checkedPlanches.clear(); $("#album-detail").hidden = true; }
  updateSelInfo();
  loadSynthese();
}

/* Badge « validées / total » avec mini-barre (vert si tout est validé). */
function validBadge(n, total) {
  const pct = total ? Math.round(100 * n / total) : 0;
  const cls = total && n === total ? "all" : "";
  return `<span class="val-album ${cls}" title="${n}/${total} planche(s) validée(s)">`
       + `${n}/${total}<i class="val-mini"><i style="width:${pct}%"></i></i></span>`;
}

/* Synthèse d'avancement du corpus (barre par statut + validées). */
async function loadSynthese() {
  let c;
  try { c = await apiGet("/api/corpus"); } catch (e) { return; }
  const order = ["importee", "segmentee", "corrigee", "annotee"];
  const lbl = { importee: "importées", segmentee: "segmentées",
                corrigee: "corrigées", annotee: "annotées" };
  const total = c.planches || 0, st = c.statuts || {};
  const bar = total ? order.map((s) => {
    const n = st[s] || 0;
    return n ? `<span class="seg seg-${s}" style="width:${(100 * n / total).toFixed(1)}%" title="${lbl[s]} : ${n}"></span>` : "";
  }).join("") : "";
  const pct = total ? Math.round(100 * c.validees / total) : 0;
  const el = $("#corpus-synthese");
  el.hidden = false;
  el.innerHTML =
    `<div class="synth-line"><b>Corpus</b> · ${c.albums} album(s) · ${total} planche(s)`
    + ` · <span class="synth-val">✔ ${c.validees} validée(s) (${pct} %)</span></div>`
    + `<div class="synth-bar">${bar}</div>`
    + `<div class="synth-legend muted small">`
    + order.map((s) => `<span><i class="seg seg-${s}"></i> ${lbl[s]} (${st[s] || 0})</span>`).join("")
    + `</div>`;
}

function renderAlbums() {
  const body = $("#albums-body");
  body.innerHTML = "";
  if (!state.albums.length) {
    body.innerHTML = '<tr><td colspan="10" class="empty-cell">Aucun album. Créez-en un.</td></tr>';
    return;
  }
  for (const a of state.albums) {
    const tr = document.createElement("tr");
    tr.className = "album-row" + (a.id === state.openId ? " open" : "");
    tr.innerHTML =
      `<td class="c-chk"><input type="checkbox" aria-label="Sélectionner l'album ${esc(a.titre)}" ${state.checkedAlbums.has(a.id) ? "checked" : ""}></td>` +
      `<td class="c-titre">${esc(a.titre)}</td>` +
      `<td>${esc(a.serie || "")}</td><td>${esc(a.auteur || "")}</td>` +
      `<td class="c-num">${a.annee || ""}</td>` +
      `<td class="c-num">${a.nb_planches}</td>` +
      `<td class="c-num">${a.nb_regions}</td>` +
      `<td class="c-num">${a.nb_transcrites}</td>` +
      `<td class="c-num c-val-album">${validBadge(a.nb_validees, a.nb_planches)}</td>` +
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
  // Purge les planches cochées qui n'existent plus (suppression concurrente, lot…).
  const pids = new Set(state.planches.map((p) => p.id));
  state.checkedPlanches.forEach((pid) => { if (!pids.has(pid)) state.checkedPlanches.delete(pid); });
  renderAlbums();
  renderDetail();
  updateSelInfo();
}

function renderDetail() {
  const a = state.albums.find((x) => x.id === state.openId);
  const box = $("#album-detail");
  if (!a) { box.hidden = true; return; }
  box.hidden = false;
  const planchesRows = state.planches.length
    ? state.planches.map((p) => `
        <tr>
          <td class="c-chk"><input type="checkbox" aria-label="Sélectionner la planche ${p.numero}" data-pid="${p.id}" ${state.checkedPlanches.has(p.id) ? "checked" : ""}></td>
          <td><img class="pl-thumb" loading="lazy" src="${esc(p.url_web || "")}" alt=""></td>
          <td class="c-pl">${plancheNum(p)}</td>
          <td><span class="statut-pill statut-${esc(p.statut)}"></span> ${esc(p.statut)}</td>
          <td class="c-num">${p.nb_regions} rég.</td>
          <td class="c-num">${p.nb_annotees} ann.</td>
          <td class="c-val">${validToggle(p)}</td>
          <td class="c-act">
            ${roleToggle(p)}
            ${lockToggle(p)}
            <a class="icon-btn" href="/?album=${a.id}&planche=${p.id}" title="Ouvrir dans la visionneuse">↗</a>
            <button class="icon-btn danger" data-delp="${p.id}" title="Supprimer la planche">🗑</button>
          </td>
        </tr>`).join("")
    : '<tr><td colspan="8" class="empty-cell">Aucune planche. Importez-en depuis la visionneuse ou ShareDocs.</td></tr>';

  box.innerHTML = `
    <div class="detail-head">
      <h3>${esc(a.titre)} ${a.annee ? `<span class="muted">(${a.annee})</span>` : ""}</h3>
      <div class="detail-meta muted small">
        ${a.serie ? "Série : " + esc(a.serie) + " · " : ""}${a.auteur ? "Auteur : " + esc(a.auteur) + " · " : ""}
        ${a.editeur ? "Éditeur : " + esc(a.editeur) : ""}
      </div>
      ${a.description ? `<p class="detail-desc">${esc(a.description)}</p>` : ""}
      <button class="ghost small" id="detail-edit">✎ Éditer l'album</button>
      <button class="ghost small" id="detail-validate-all">✔ Tout valider</button>
    </div>
    <table class="corpus-table planches-table">
      <thead><tr><th class="c-chk" aria-label="Sélection"></th><th aria-label="Aperçu"></th><th>Planche</th><th>Statut</th>
        <th class="c-num">Régions</th><th class="c-num">Annotées</th>
        <th>Validée</th><th aria-label="Actions"></th></tr></thead>
      <tbody>${planchesRows}</tbody>
    </table>`;

  $("#detail-edit").onclick = () => openModal(a);
  $("#detail-validate-all").onclick = validateAllAlbum;
  box.querySelectorAll("button[data-val]").forEach((btn) => {
    btn.onclick = () => validatePlanche(Number(btn.dataset.val), btn.dataset.on === "1");
  });
  box.querySelectorAll("button[data-lock]").forEach((btn) => {
    btn.onclick = () => lockPlanche(Number(btn.dataset.lock), btn.dataset.on === "1");
  });
  box.querySelectorAll("button[data-role]").forEach((btn) => {
    btn.onclick = () => setRole(Number(btn.dataset.role), btn.dataset.to);
  });
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
  const btn = $("#m-save");
  if (btn.disabled) return;               // anti-double-soumission (sinon album dupliqué)
  btn.disabled = true;
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
  finally { btn.disabled = false; }
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

/* Cellule « Planche » : numéro ÉDITORIAL (dérivé, cité) pour le récit, ou pastille
   Paratexte ; l'ordre d'import reste visible en discret (clé de tri stable, ≠ du
   numéro cité). Cf. docs/numerotation-et-citation.md. */
function plancheNum(p) {
  const imp = `<span class="muted small" title="ordre d'import">i.${String(p.numero).padStart(3, "0")}</span>`;
  if (p.role === "recit")
    return `<b title="Numéro éditorial (cité)">planche ${p.numero_editorial}</b><br>${imp}`;
  return `<span class="badge" title="Paratexte — hors numérotation du récit">Paratexte</span><br>${imp}`;
}

/* Bascule du rôle éditorial : récit ⇄ paratexte (couverture, liminaire, pub…).
   Marquer/retirer renumérote tout l'album (numéro éditorial dérivé). */
function roleToggle(p) {
  const para = p.role !== "recit";
  return `<button class="icon-btn" data-role="${p.id}" data-to="${para ? "recit" : "paratexte"}" `
    + `title="${para ? "Paratexte — cliquer pour rétablir en planche de récit"
                     : "Marquer comme paratexte (couverture, liminaire, pub… — hors numérotation)"}">`
    + `${para ? "📖" : "🏷"}</button>`;
}

async function setRole(pid, role) {
  try {
    await apiSend("PATCH", `/api/planches/${pid}/role`, { role });
    await openAlbum(state.openId);   // renumérotation dérivée → recharge l'album
    toast(role === "paratexte" ? "Planche marquée Paratexte 🏷" : "Planche rétablie en récit 📖");
  } catch (e) { toast("Rôle : " + e.message, "error"); }
}

/* Badge ✔ + bouton bascule de validation pour une planche. */
function validToggle(p) {
  return (p.validee ? `<span class="val-badge" title="Validée le ${esc(p.validee)}">✔</span> ` : "")
    + `<button class="icon-btn" data-val="${p.id}" data-on="${p.validee ? 0 : 1}" `
    + `title="${p.validee ? "Retirer la validation" : "Marquer comme validée"}">`
    + `${p.validee ? "↺" : "✔"}</button>`;
}

async function validatePlanche(pid, on) {
  try {
    await apiSend("PATCH", `/api/planches/${pid}/validation`, { validee: on });
    await loadAlbums();   // rafraîchit table + album ouvert + synthèse
  } catch (e) { toast("Validation : " + e.message, "error"); }
}

/* Bascule de verrou : une planche verrouillée est sautée par les lots (et ses
   passes directes refusées). 🔒 = verrouillée, 🔓 = libre. */
function lockToggle(p) {
  const on = !!p.verrouillee;
  return `<button class="icon-btn${on ? " locked" : ""}" data-lock="${p.id}" `
    + `data-on="${on ? 0 : 1}" `
    + `title="${on ? "Verrouillée le " + esc(p.verrouillee) + " — cliquer pour déverrouiller"
                   : "Verrouiller (protéger des traitements en lot)"}">`
    + `${on ? "🔒" : "🔓"}</button>`;
}

async function lockPlanche(pid, on) {
  try {
    await apiSend("PATCH", `/api/planches/${pid}/verrou`, { verrouillee: on });
    await openAlbum(state.openId);
    toast(on ? "Planche verrouillée 🔒" : "Planche déverrouillée 🔓");
  } catch (e) { toast("Verrou : " + e.message, "error"); }
}

async function validateAllAlbum() {
  const todo = state.planches.filter((p) => !p.validee);
  if (!todo.length) { toast("Toutes les planches sont déjà validées."); return; }
  if (!confirm(`Valider ${todo.length} planche(s) de cet album ?`)) return;
  try {
    for (const p of todo)
      await apiSend("PATCH", `/api/planches/${p.id}/validation`, { validee: true });
    await loadAlbums();
    toast(`${todo.length} planche(s) validée(s)`, "success");
  } catch (e) { toast("Validation : " + e.message, "error"); }
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
    if (job.verrouillees_ignorees)
      toast(`${job.verrouillees_ignorees} planche(s) verrouillée(s) ignorée(s) 🔒`);
    pollJobs();
  } catch (e) { toast("Lot : " + e.message, "error"); }
}

async function pollJobs() {
  clearTimeout(state.jobTimer);                  // annule tout tick en attente d'emblée
  const gen = (state.jobGen = (state.jobGen || 0) + 1);
  let list = [];
  try { list = await apiGet("/api/jobs"); } catch (e) { return; }
  if (gen !== state.jobGen) return;              // un poll plus récent a pris le relais
  renderJobs(list);
  const actifs = list.some((j) => j.status === "en_cours");
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

/* Bouton « ← Retour » : ramène à la surface d'origine via le `retour` reçu (page
   interne seulement, cf. lib/nav.js), à défaut history.back() si l'on vient de l'app.
   Masqué s'il n'y a nulle part où revenir. Calqué sur les autres surfaces. */
function setupBack() {
  const back = $("#back-link");
  if (!back) return;
  let target = Nav.safeRetour(new URLSearchParams(location.search).get("retour"));
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

/* ---------------- Démarrage ---------------- */
function setup() {
  setupBack();
  $("#btn-new").onclick = () => openModal(null);
  $("#m-save").onclick = saveAlbum;
  $("#m-cancel").onclick = closeModal;
  $("#album-modal").addEventListener("mousedown", (e) => {
    if (e.target.id === "album-modal") closeModal();
  });
  // Modale accessible : role=dialog, piège à focus, Échap, retour du focus (source unique).
  if (window.BDDialog)
    BDDialog.register($("#album-modal"),
      { box: ".modal-box", labelledby: "modal-title", onClose: closeModal });
  PASSES.forEach((p) => { $("#pass-" + p).onchange = updateSelInfo; });
  $("#btn-run").onclick = runBatch;
  loadCorpus();   // stats d'en-tête (bande 2)
  loadAlbums();
  pollJobs();     // reprend l'affichage d'un éventuel job déjà en cours
}

setup();
