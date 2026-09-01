/* ===================================================================
   BéDéditeur — page Bibliothèque / gestion de corpus (vanilla JS)
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
  relFilter: "",            // ANN-4 : filtre de relecture du détail d'album ("" = toutes)
};

// Libellés du statut de relecture (ANN-4). Clés = valeurs backend.
const RELECTURE_LBL = { a_faire: "à faire", en_cours: "en cours", faite: "faite" };

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
  // ATTENDU, pas espéré : `renderDetail()` est synchrone et `parQui()` y compare le login
  // courant. L'appel de `setup()` part en parallèle et gagne presque toujours la course —
  // « presque » n'est pas une garantie, et le perdre afficherait « par <votre nom> » à
  // vous-même. L'attente ne coûte rien : la promesse de `theme.js` est déjà en vol, et le
  // mémo rend l'appel gratuit ensuite.
  await colChargerEtat();
  renderAlbums();
  renderDetail();
  updateSelInfo();
}

function renderDetail() {
  const a = state.albums.find((x) => x.id === state.openId);
  const box = $("#album-detail");
  if (!a) { box.hidden = true; return; }
  box.hidden = false;
  // Filtre de relecture (ANN-4) : n'affiche que les planches du statut effectif choisi.
  const planches = state.relFilter
    ? state.planches.filter((p) => (p.relecture_statut || {}).statut === state.relFilter)
    : state.planches;
  const videMsg = state.planches.length
    ? "Aucune planche pour ce filtre de relecture."
    : "Aucune planche. Importez-en depuis la visionneuse ou ShareDocs.";
  const planchesRows = planches.length
    ? planches.map((p) => `
        <tr>
          <td class="c-chk"><input type="checkbox" aria-label="Sélectionner la planche ${p.numero}" data-pid="${p.id}" ${state.checkedPlanches.has(p.id) ? "checked" : ""}></td>
          <td><img class="pl-thumb" loading="lazy" src="${esc(p.url_web || "")}" alt=""></td>
          <td class="c-pl">${plancheNum(p)}${materielInfo(p)}</td>
          <td><span class="statut-pill statut-${esc(p.statut)}"></span> ${esc(p.statut)}</td>
          <td class="c-num">${p.nb_regions} rég.</td>
          <td class="c-num">${p.nb_annotees} ann.</td>
          <td class="c-rel">${relectureCell(p)}</td>
          <td class="c-val">${validToggle(p)}</td>
          <td class="c-act">
            ${roleToggle(p)}
            ${lockToggle(p)}
            <a class="icon-btn" href="/?album=${a.id}&planche=${p.id}" title="Ouvrir dans la visionneuse">↗</a>
            <button class="icon-btn danger" data-delp="${p.id}" title="Supprimer la planche">🗑</button>
          </td>
        </tr>`).join("")
    : `<tr><td colspan="9" class="empty-cell">${videMsg}</td></tr>`;

  const edParts = [
    a.date_edition && "Éd. " + esc(a.date_edition),
    a.langue && esc(a.langue),
    a.type_oeuvre && esc(a.type_oeuvre),
    a.lieu_edition && esc(a.lieu_edition),
    a.isbn && "ISBN " + esc(a.isbn),
    a.format_physique && esc(a.format_physique),
  ].filter(Boolean).join(" · ");
  box.innerHTML = `
    <div class="detail-head">
      <h3>${esc(a.titre)} ${a.annee ? `<span class="muted">(${a.annee})</span>` : ""}</h3>
      <div class="detail-meta muted small">
        ${a.serie ? "Série : " + esc(a.serie) + " · " : ""}${a.auteur ? "Auteur : " + esc(a.auteur) + " · " : ""}
        ${a.editeur ? "Éditeur : " + esc(a.editeur) : ""}
      </div>
      ${edParts ? `<div class="detail-meta muted small">${edParts}</div>` : ""}
      ${a.source_numerisation ? `<div class="detail-meta muted small">Numérisation : ${esc(a.source_numerisation)}</div>` : ""}
      <div id="detail-contribs" class="detail-meta small"></div>
      ${a.description ? `<p class="detail-desc">${esc(a.description)}</p>` : ""}
      <button class="ghost small" id="detail-edit">✎ Éditer l'album</button>
      <button class="ghost small" id="detail-validate-all">✔ Tout valider</button>
      <label class="muted small detail-relfilter">Relecture
        <select id="rel-filter" aria-label="Filtrer les planches par statut de relecture">
          <option value="">toutes</option>
          <option value="a_faire">à faire</option>
          <option value="en_cours">en cours</option>
          <option value="faite">faite</option>
        </select>
      </label>
    </div>
    <table class="corpus-table planches-table">
      <thead><tr><th class="c-chk" aria-label="Sélection"></th><th aria-label="Aperçu"></th><th>Planche</th><th>Statut</th>
        <th class="c-num">Régions</th><th class="c-num">Annotées</th>
        <th>Relecture</th><th>Validée</th><th aria-label="Actions"></th></tr></thead>
      <tbody>${planchesRows}</tbody>
    </table>`;

  $("#detail-edit").onclick = () => openModal(a);
  $("#detail-validate-all").onclick = validateAllAlbum;
  $("#rel-filter").value = state.relFilter;                       // reflète l'état courant
  $("#rel-filter").onchange = (e) => { state.relFilter = e.target.value; renderDetail(); };
  box.querySelectorAll("select[data-rel]").forEach((sel) => {
    sel.onchange = () => setRelecture(Number(sel.dataset.rel), sel.value);
  });
  loadDetailContribs(a.id);
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
/* AUTH-2 — la collection est l'unité de cloisonnement : un album y appartient TOUJOURS.
   L'API accepte de retomber sur une collection de repli, mais lui laisser ce choix ferait
   s'entasser tout le corpus dans un seul seau et le cloisonnement ne servirait jamais.
   L'UI demande donc explicitement — sauf quand il n'y a rien à demander.

   Trois cas, et le troisième est celui qui empêche l'impasse :
     · plusieurs collections → aucune présélection, le choix est fait à la main ;
     · une seule            → présélectionnée (la question n'a qu'une réponse) ;
     · aucune               → pas de sélecteur, une note dit que l'API en créera une.
   À l'ÉDITION, le champ disparaît : déplacer un album d'une collection à l'autre est un
   geste d'espace de travail, qui appartient à AUTH-3. */
async function remplirCollections(edition) {
  const wrap = $("#m-collection-wrap"), sel = $("#m-collection"), note = $("#m-collection-note");
  wrap.hidden = true; note.hidden = true; sel.innerHTML = "";
  if (edition) return;
  let cols = [];
  try { cols = await apiGet("/api/collections"); } catch (e) { cols = []; }
  if (!cols.length) {
    note.textContent = "Aucune collection : l'album entrera dans une collection par "
      + "défaut, créée à cette occasion.";
    note.hidden = false;
    return;
  }
  if (cols.length > 1) sel.appendChild(new Option("— choisir —", ""));
  for (const c of cols) sel.appendChild(new Option(c.nom, String(c.id)));
  sel.value = cols.length === 1 ? String(cols[0].id) : "";
  wrap.hidden = false;
}

async function openModal(album) {
  state.editingId = album ? album.id : null;
  $("#modal-title").textContent = album ? "Éditer l'album" : "Nouvel album";
  const g = (k) => (album && album[k]) || "";
  $("#m-titre").value = album ? album.titre : "";
  $("#m-serie").value = g("serie");
  $("#m-auteur").value = g("auteur");
  $("#m-annee").value = g("annee");
  $("#m-editeur").value = g("editeur");
  $("#m-desc").value = g("description");
  $("#m-date-edition").value = g("date_edition");
  $("#m-date-originale").value = g("date_originale");
  $("#m-langue").value = g("langue");
  $("#m-type").value = g("type_oeuvre");
  $("#m-lieu").value = g("lieu_edition");
  $("#m-tirage").value = g("edition_tirage");
  $("#m-isbn").value = g("isbn");
  $("#m-format").value = g("format_physique");
  $("#m-source-num").value = g("source_numerisation");   // matériel (A6)
  $("#m-msg").textContent = "";
  // Contributions : éditables seulement sur un album EXISTANT (elles ont besoin de son id).
  $("#m-contrib-nom").value = "";
  $("#m-contrib-role").value = "";
  const exist = !!state.editingId;
  $("#m-contrib-hint").hidden = exist;
  $(".contrib-add").style.display = exist ? "" : "none";
  $("#m-contribs").innerHTML = "";
  if (exist) { loadRoles(); loadContributions(state.editingId); }
  // AWAIT avant d'ouvrir : sans cela, une sauvegarde plus rapide que la requête verrait
  // le sélecteur encore caché et retomberait EN SILENCE sur la collection de repli —
  // exactement ce que ce champ existe pour empêcher.
  await remplirCollections(exist);
  await loadAppartenance(state.editingId);   // AUTH-3 : N-N, édition seulement
  $("#album-modal").hidden = false;
  $("#m-titre").focus();
}

async function loadRoles() {
  try {
    const roles = await apiGet("/api/contribution-roles");
    $("#dl-roles").innerHTML = roles.map((r) => `<option value="${esc(r.label)}">`).join("");
  } catch (e) { /* datalist vide : non bloquant */ }
}

async function loadContributions(albumId) {
  try { renderContribs(await apiGet(`/api/albums/${albumId}/contributions`)); }
  catch (e) { $("#m-contribs").innerHTML = ""; }
}

function renderContribs(list) {
  const box = $("#m-contribs");
  if (!list.length) { box.innerHTML = '<p class="muted small">Aucune contribution.</p>'; return; }
  box.innerHTML = list.map((c) => `
    <div class="contrib-row">
      <span class="contrib-nom">${esc(c.nom)}</span>
      <span class="contrib-role muted small">${c.role ? esc(c.role) : "—"}</span>
      <button class="icon-btn danger" type="button" data-delc="${c.id}" title="Retirer" aria-label="Retirer ${esc(c.nom)}">✕</button>
    </div>`).join("");
  box.querySelectorAll("button[data-delc]").forEach((b) => {
    b.onclick = () => removeContribution(Number(b.dataset.delc));
  });
}

async function addContribution() {
  if (!state.editingId) return;
  const nom = $("#m-contrib-nom").value.trim();
  if (!nom) { $("#m-contrib-nom").focus(); return; }
  const role = $("#m-contrib-role").value.trim() || null;
  try {
    await apiSend("POST", `/api/albums/${state.editingId}/contributions`, { nom, role });
    $("#m-contrib-nom").value = "";
    $("#m-contrib-role").value = "";
    await loadContributions(state.editingId);
    await loadRoles();                 // un nouveau rôle rejoint la datalist
    $("#m-contrib-nom").focus();
  } catch (e) { $("#m-msg").textContent = "✗ " + e.message; }
}

async function removeContribution(id) {
  try { await apiSend("DELETE", `/api/contributions/${id}`); await loadContributions(state.editingId); }
  catch (e) { $("#m-msg").textContent = "✗ " + e.message; }
}

async function loadDetailContribs(albumId) {
  const el = $("#detail-contribs");
  if (!el) return;
  try {
    const list = await apiGet(`/api/albums/${albumId}/contributions`);
    el.innerHTML = list.length
      ? "Contributions : " + list.map((c) =>
          `${esc(c.nom)}${c.role ? ` <span class="muted">(${esc(c.role)})</span>` : ""}`).join(", ")
      : "";
  } catch (e) { el.innerHTML = ""; }
}
function closeModal() { $("#album-modal").hidden = true; }

async function saveAlbum() {
  const titre = $("#m-titre").value.trim();
  if (!titre) { $("#m-msg").textContent = "Titre requis."; return; }
  // Le sélecteur n'est visible qu'à la création, et seulement s'il y a un choix à faire.
  const wrap = $("#m-collection-wrap");
  const collectionId = wrap.hidden ? null : ($("#m-collection").value || null);
  if (!wrap.hidden && !collectionId) {
    $("#m-msg").textContent = "Choisissez la collection qui accueillera cet album.";
    return;
  }
  const btn = $("#m-save");
  if (btn.disabled) return;               // anti-double-soumission (sinon album dupliqué)
  btn.disabled = true;
  const annee = parseInt($("#m-annee").value, 10);
  const val = (id) => $(id).value.trim() || null;
  const body = {
    titre,
    serie: val("#m-serie"),
    auteur: val("#m-auteur"),
    annee: isNaN(annee) ? null : annee,
    editeur: val("#m-editeur"),
    description: val("#m-desc"),
    date_edition: val("#m-date-edition"),
    date_originale: val("#m-date-originale"),
    langue: val("#m-langue"),
    type_oeuvre: val("#m-type"),
    lieu_edition: val("#m-lieu"),
    edition_tirage: val("#m-tirage"),
    isbn: val("#m-isbn"),
    format_physique: val("#m-format"),
    source_numerisation: val("#m-source-num"),   // matériel (A6)
  };
  if (collectionId) body.collection_id = parseInt(collectionId, 10);   // AUTH-2
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

/* Matériel de numérisation (A6) — résolution / mode / dimensions physiques (cm, dérivées
   px÷dpi côté serveur). Ligne discrète en lecture seule ; masquée si rien de connu. */
function materielInfo(p) {
  const parts = [];
  if (p.dpi_x) parts.push(p.dpi_x === p.dpi_y ? `${p.dpi_x} dpi` : `${p.dpi_x}×${p.dpi_y} dpi`);
  if (p.mode) parts.push(esc(p.mode));
  if (p.dimensions_cm) parts.push(`${p.dimensions_cm.largeur}×${p.dimensions_cm.hauteur} cm`);
  return parts.length
    ? `<br><span class="muted small" title="Matériel de numérisation">${parts.join(" · ")}</span>`
    : "";
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

/* Relecture grammaticale (ANN-4) : pastille du statut EFFECTIF (dérivé ⊕ forcé) + sélecteur
   d'override (3 états | auto). Le titre détaille le dérivé (relus/tokens) et l'éventuel forçage. */
function relectureCell(p) {
  const rs = p.relecture_statut
    || { statut: "a_faire", derive: "a_faire", force: false, tokens: 0, relus: 0 };
  const title = `Dérivé : ${RELECTURE_LBL[rs.derive]} (${rs.relus}/${rs.tokens} token(s) relu(s))`
    + (rs.force ? ` · forcé « ${RELECTURE_LBL[rs.statut]} »` : "");
  const opts = ["a_faire", "en_cours", "faite"].map((s) =>
    `<option value="${s}"${rs.force && rs.statut === s ? " selected" : ""}>${RELECTURE_LBL[s]}</option>`).join("");
  return `<span class="rel-pill rel-${rs.statut}${rs.force ? " rel-force" : ""}" title="${esc(title)}">`
    + `${RELECTURE_LBL[rs.statut]}</span>`
    + `<select class="rel-sel" data-rel="${p.id}" title="Forcer le statut de relecture (ou auto)" `
    + `aria-label="Forcer la relecture de la planche ${p.numero}">`
    + `<option value=""${rs.force ? "" : " selected"}>auto</option>${opts}</select>`;
}

async function setRelecture(pid, value) {
  try {
    await apiSend("PATCH", `/api/planches/${pid}/relecture`, { relecture: value || null });
    await openAlbum(state.openId);   // recharge : pastille + filtre reflètent le nouveau statut
  } catch (e) { toast("Relecture : " + e.message, "error"); }
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
    + `title="${on ? "Verrouillée " + esc(parQui(p)) + "le " + esc(p.verrouillee)
                     + " — cliquer pour déverrouiller"
                   : "Verrouiller (protéger des traitements en lot)"}">`
    + `${on ? "🔒" : "🔓"}</button>`;
}

/* AUTH-1 — « verrouillée le … » ne disait pas PAR QUI, alors que `verrou_par` est consigné
   depuis la v22. C'est pourtant la seule information dont on ait besoin : le verrou est
   purement informatif, n'importe qui peut le lever, et la question qu'on se pose devant est
   « à qui demander avant de le faire ».

   « par vous » se décide sur le LOGIN et non sur le nom affiché : deux personnes peuvent
   porter le même nom, et se voir attribuer le verrou d'un homonyme serait pire que de ne
   rien savoir. Rien en mono-poste, où l'agent est NULL — un acte anonyme, honnêtement. */
function parQui(p) {
  if (!p.verrou_par) return "";
  if (COL_ETAT.moi && p.verrou_par === COL_ETAT.moi) return "par vous ";
  return "par " + (p.verrou_par_nom || p.verrou_par) + " ";
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
    const label = { en_cours: "en cours", termine: "terminé", annule: "annulé",
                    echec: "échec" }[j.status] || j.status;
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
/* ═══════════════════════════════════════════════════════════════════════════
   Collections (AUTH-3) — espaces de travail : créer, partager, ranger

   AUTH-2 avait fait le cloisonnement, pas son administration : `collection_acces` ne se
   remplissait qu'en SQL à la main. Cet écran est ce qui rend le reste utilisable — sans
   lui, tout le travail de routes reste du curl.

   Trois niveaux, et le troisième est la nouveauté : lecture · écriture · PROPRIÉTAIRE.
   Écrire, c'est annoter ; posséder, c'est décider qui d'autre entrera.
   ═══════════════════════════════════════════════════════════════════════════ */
const COL_NIVEAUX = [["lecture", "Lecture"], ["ecriture", "Écriture"],
                     ["proprietaire", "Propriétaire"]];

function colMsg(texte, erreur) {
  const el = $("#col-msg");
  el.textContent = texte || "";
  el.classList.toggle("erreur", !!erreur);
}

/* Les refus du serveur sont RENDUS, jamais avalés. Les deux cas d'AUTH-3 (dernier
   propriétaire, dernière collection) sont des 409 qui nomment un ÉTAT INTERDIT et non un
   droit manquant : les remplacer par un « échec » générique ferait croire à un bug. */
async function colTenter(fn) {
  try { await fn(); colMsg(""); return true; }
  catch (e) { colMsg(e.message || "Échec", true); return false; }
}

function niveauOptions(courant) {
  return COL_NIVEAUX.map(([v, l]) =>
    `<option value="${v}"${v === courant ? " selected" : ""}>${l}</option>`).join("");
}

/* DROIT-1 — ce que la date d'embargo raconte, en clair.

   L'application ne lève JAMAIS un embargo toute seule : une date qui passe dit que le
   délai a couru, pas que les droits sont acquis. Mais se taire aurait son propre coût —
   un embargo échu que personne ne remarque garde un corpus fermé par inertie, ce qui
   trahit l'orientation open-science aussi sûrement qu'une fuite trahit les droits.

   Le libellé PORTE le sens ; la couleur ne fait que le renforcer (WCAG 1.4.1). */
function colEmbargo(c) {
  const date = c.date_embargo || "";
  if (c.embargo === "echu")
    return [`Embargo échu`, "est-echu",
            `L'embargo est échu depuis le ${date}, et la collection reste déclarée `
            + `« ${c.statut_diffusion || "sans régime"} ». L'application ne la publie pas `
            + `pour autant : si les droits sont acquis, déclarez-la « public ».`];
  if (c.embargo === "illisible")
    return [`Embargo : date illisible`, "est-echu",
            `« ${date} » n'est pas une date lisible (attendu AAAA-MM-JJ). Par précaution, `
            + `les scans ne sortent pas tant qu'elle ne l'est pas.`];
  if (c.embargo === "pendant")
    return [`Embargo jusqu'au ${date}`, "",
            c.statut_diffusion === "public"
              ? `La collection est déclarée « public », mais l'embargo court jusqu'au `
                + `${date} : les scans ne sortiront pas avant cette date.`
              : `L'embargo court jusqu'au ${date}. Le travail interne n'en est pas `
                + `affecté : seule la publication l'est.`];
  return null;
}

/* Une collection = un <details>. Repliée, elle dit son nom, son volume et MON niveau ;
   dépliée, elle montre qui a accès — mais seulement si je peux l'administrer, la liste
   des membres d'une étude étant une donnée sur des personnes. */
function colItem(c) {
  const d = document.createElement("details");
  d.className = "col-item";
  d.dataset.id = String(c.id);
  // « Propriétaire » ne s'affiche qu'à un vrai propriétaire : le dire à un administrateur
  // lui ferait croire à un lien personnel avec une collection qui n'est pas la sienne.
  const badge = c.mon_niveau
    ? `<span class="col-niveau${c.mon_niveau === "proprietaire" ? " est-proprietaire" : ""}">`
      + `${COL_NIVEAUX.find((n) => n[0] === c.mon_niveau)[1]}</span>`
    : (c.administrable ? `<span class="col-niveau">Administrateur</span>` : "");
  const emb = colEmbargo(c);
  d.innerHTML = `
    <summary>
      <span class="col-nom">${esc(c.nom)}</span>
      <span class="muted small">${c.nb_albums} album(s)</span>
      ${badge}
      ${emb ? `<span class="col-embargo ${emb[1]}" title="${esc(emb[2])}">${esc(emb[0])}</span>`
            : ""}
    </summary>
    <div class="col-detail"></div>`;
  d.addEventListener("toggle", () => { if (d.open) colDetail(d, c); });
  return d;
}

/* AUTH-4 — le fait que la liste des accès taisait.

   `_acces_de()` ne lit que `collection_acces`, où un administrateur d'instance ne figure
   sur AUCUNE ligne : sa portée court-circuite la table en amont (`clause_album()` rend
   « 1 » quand elle est totale). La liste affichait donc trois noms là où quatre personnes
   lisent — sur un écran qui protège soigneusement cette liste au motif qu'elle parle de
   personnes. Ce n'est pas un défaut d'autorisation, c'est un défaut de DÉCLARATION : le
   pouvoir est inévitable dans un système auto-hébergé, son invisibilité ne l'est pas. */
function colAdminNote() {
  const g = (COL_ETAT.groupes_admin || []);
  if (!g.length) return "";
  // Formulée sans « ci-dessus » : les deux branches de `colDetail` l'affichent, et le
  // participant non propriétaire n'a AUCUNE liste d'accès sous les yeux. Un renvoi à ce
  // qui n'est pas là est une petite fausseté, mais c'est la même que celle qu'AUTH-4
  // corrige — un écran qui parle d'autre chose que de ce qu'il montre.
  return `<p class="col-note col-note-admin">Les administrateurs de l'instance
    (${g.map(esc).join(", ")}) lisent et écrivent <strong>toute</strong> collection, sans
    figurer dans aucune liste d'accès. Chacun de leurs actes est nommé au journal de
    provenance.</p>`;
}

/* Le référent, en LECTURE. Le contact s'affiche en TEXTE et non en lien, contrairement au
   référent d'instance du bandeau (`theme.js`) : celui-là vient de l'environnement, donc de
   qui déploie, tandis que celui-ci est saisi par un propriétaire de collection. Plutôt que
   de recopier ici l'autorisation de schémas — deux listes qui divergeraient un jour —, on
   n'ouvre pas la porte du tout : un `href` est la seule chose qui rende `javascript:`
   dangereux, et une adresse reste lisible sans être cliquable. */
function colReferentLu(c) {
  const nom = (c.referent_nom || "").trim();
  const contact = (c.referent_contact || "").trim();
  if (!nom && !contact) return "";
  return `<p class="col-note col-note-referent">Référent de cette collection :
    <strong>${esc(nom || contact)}</strong>${nom && contact ? ` — ${esc(contact)}` : ""}.</p>`;
}

async function colDetail(d, c) {
  const box = d.querySelector(".col-detail");
  if (!c.administrable) {
    // Le participant NON propriétaire est celui à qui AUTH-4 sert le plus, et le premier
    // jet le laissait sortir d'ici les mains vides : le référent et la déclaration
    // vivaient tous deux sous ce `return`, donc visibles du seul propriétaire — celui qui
    // les a écrits. DÉSIGNER un référent engage la collection et reste au propriétaire ;
    // le LIRE est le geste de quelqu'un qui a une question. Deux droits distincts qu'une
    // seule garde confondait.
    box.innerHTML = `<p class="col-note">Vous participez à cette collection sans la
      posséder : seul un propriétaire voit et modifie la liste des accès.</p>
      ${colReferentLu(c)}${colAdminNote()}`;
    return;
  }
  box.innerHTML = `<p class="col-note">Chargement…</p>`;
  let acces = [];
  try { acces = await apiGet(`/api/collections/${c.id}/acces`); }
  catch (e) { box.innerHTML = `<p class="col-note">${esc(e.message)}</p>`; return; }
  box.innerHTML = `
    <ul class="acces-liste">${acces.map((a) => `
      <li>
        <span class="acces-principal">${esc(a.principal)}</span>
        <span class="acces-genre">${a.genre === "groupe" ? "groupe" : "utilisateur"}</span>
        <select data-genre="${esc(a.genre)}" data-principal="${esc(a.principal)}"
                aria-label="Niveau de ${esc(a.principal)}">${niveauOptions(a.niveau)}</select>
        <button class="ghost small" data-retirer="1" data-genre="${esc(a.genre)}"
                data-principal="${esc(a.principal)}" type="button"
                title="Retirer l'accès de ${esc(a.principal)}">✕</button>
      </li>`).join("")}</ul>
    <div class="contrib-add">
      <input class="col-principal" placeholder="Login ou nom de groupe" autocomplete="off"
             aria-label="Login ou nom de groupe à qui accorder l'accès">
      <select class="col-genre" aria-label="Genre du principal">
        <option value="utilisateur">Utilisateur</option>
        <option value="groupe">Groupe</option>
      </select>
      <select class="col-niveau-neuf" aria-label="Niveau accordé">${niveauOptions("lecture")}</select>
      <button class="ghost small" data-accorder="1" type="button">+ Accorder</button>
    </div>
    <p class="col-note">Un accès se déclare par un NOM, pas par une personne vérifiée :
      l'application n'a aucun annuaire, elle lit les groupes dans les en-têtes du proxy à
      chaque requête. Un login mal orthographié n'ouvre rien — sans le dire.</p>
    ${colAdminNote()}
    <fieldset class="col-referent">
      <legend>Référent de cette collection</legend>
      <p class="col-note">À qui s'adresser pour cet espace. C'est une ADRESSE, pas un
        droit : la nommer n'accorde rien et ne retire rien.</p>
      <input class="col-ref-nom" placeholder="Nom lisible" autocomplete="off"
             aria-label="Nom du référent" value="${esc(c.referent_nom || "")}">
      <input class="col-ref-contact" placeholder="Courriel ou adresse de page"
             autocomplete="off" aria-label="Contact du référent"
             value="${esc(c.referent_contact || "")}">
      <button class="ghost small" data-referent="1" type="button">Enregistrer</button>
    </fieldset>
    <div class="modal-actions">
      <button class="ghost small" data-renommer="1" type="button">Renommer</button>
      <button class="ghost small" data-supprimer="1" type="button">Supprimer la collection</button>
    </div>`;

  const recharger = async () => { await loadCollections(); };
  const btnRef = box.querySelector("[data-referent]");
  if (btnRef) btnRef.onclick = async () => {
    // Champs vides = référent retiré, et c'est un geste légitime : on n'invente pas une
    // suppression séparée pour deux champs de texte.
    if (await colTenter(() => apiSend("PATCH", `/api/collections/${c.id}`, {
      referent_nom: box.querySelector(".col-ref-nom").value.trim(),
      referent_contact: box.querySelector(".col-ref-contact").value.trim(),
    }))) recharger();
  };
  box.querySelectorAll("[data-retirer]").forEach((b) => {
    b.onclick = async () => {
      const { genre, principal } = b.dataset;
      if (await colTenter(() => apiSend("DELETE",
          `/api/collections/${c.id}/acces/${genre}/${encodeURIComponent(principal)}`)))
        recharger();
    };
  });
  box.querySelectorAll("select[data-principal]").forEach((s) => {
    s.onchange = async () => {
      const { genre, principal } = s.dataset;
      // On recharge dans les DEUX cas : en cas de refus, le <select> afficherait sinon
      // un niveau que le serveur n'a pas accordé — l'écran mentirait sur l'état réel.
      await colTenter(() => apiSend("PUT", `/api/collections/${c.id}/acces`,
        { genre, principal, niveau: s.value }));
      recharger();
    };
  });
  box.querySelector("[data-accorder]").onclick = async () => {
    const principal = box.querySelector(".col-principal").value.trim();
    if (!principal) { colMsg("Indiquez un login ou un nom de groupe.", true); return; }
    if (await colTenter(() => apiSend("PUT", `/api/collections/${c.id}/acces`, {
        genre: box.querySelector(".col-genre").value,
        principal,
        niveau: box.querySelector(".col-niveau-neuf").value })))
      recharger();
  };
  box.querySelector("[data-renommer]").onclick = async () => {
    const nom = prompt("Nouveau nom de la collection :", c.nom);
    if (nom === null || !nom.trim()) return;
    if (await colTenter(() => apiSend("PATCH", `/api/collections/${c.id}`, { nom: nom.trim() })))
      recharger();
  };
  box.querySelector("[data-supprimer]").onclick = async () => {
    if (!confirm(`Supprimer « ${c.nom} » ? Ses albums ne sont pas supprimés : ils sortent `
                 + `simplement de cette collection.`)) return;
    if (await colTenter(() => apiSend("DELETE", `/api/collections/${c.id}`))) recharger();
  };
}

/* Les noms des groupes d'administration, lus UNE fois. Ils viennent de `/api/moi` et non
   d'une constante recopiée ici : `BD_AUTH_ADMIN_GROUPS` est configurable, et deux listes
   qui divergent afficheraient un groupe qui n'administre plus rien. */
const COL_ETAT = { groupes_admin: null, moi: null };

async function colChargerEtat() {
  if (COL_ETAT.groupes_admin !== null) return;
  // La promesse partagée de `theme.js` : `/api/moi` n'est demandé qu'UNE fois par page.
  // Deux appels écrivaient deux fois dans le miroir `utilisateur` pour rien.
  const moi = window.BDMoi ? await window.BDMoi : null;
  COL_ETAT.groupes_admin = (moi && moi.acces && moi.acces.groupes_admin) || [];
  COL_ETAT.moi = (moi && moi.utilisateur) || null;   // login, pour dire « par vous »
}

async function loadCollections() {
  const body = $("#col-body");
  // Avant le rendu : la note qui déclare les administrateurs en dépend, et une note qui
  // ne paraît pas laisse la liste mentir par omission comme avant le chantier.
  await colChargerEtat();
  let cols = [];
  try { cols = await apiGet("/api/collections"); }
  catch (e) { body.innerHTML = `<p class="col-note">${esc(e.message)}</p>`; return; }
  body.innerHTML = "";
  if (!cols.length) {
    body.innerHTML = `<p class="col-note">Aucune collection ouverte pour vous. Créez-en une
      ci-dessus : vous en serez propriétaire.</p>`;
    return;
  }
  cols.forEach((c) => body.appendChild(colItem(c)));
}

function openCollections() {
  colMsg("");
  $("#col-nom").value = "";
  $("#collections-modal").hidden = false;
  loadCollections();
  $("#col-nom").focus();
}

function closeCollections() {
  $("#collections-modal").hidden = true;
  // Le sélecteur de la modale album lit la même liste : la rafraîchir évite qu'une
  // collection tout juste créée manque au prochain « Nouvel album ».
  loadAlbums();
}

async function creerCollection() {
  const nom = $("#col-nom").value.trim();
  if (!nom) { colMsg("Donnez un nom à la collection.", true); return; }
  if (await colTenter(() => apiSend("POST", "/api/collections", { nom }))) {
    $("#col-nom").value = "";
    colMsg(`« ${nom} » créée — vous en êtes propriétaire.`);
    loadCollections();
  }
}

/* ── Appartenance d'un album (N-N) — dans la modale d'édition ─────────────────────────
   AUTH-2 posait le choix de la collection à la CRÉATION et cachait le champ à l'édition,
   faute de propriétaire pour dire qui a le droit de déplacer quoi. Le propriétaire existe
   maintenant, et l'appartenance se révèle pour ce qu'elle est depuis la v14 : N-N. Un même
   album peut nourrir deux études — le dupliquer casserait l'analyse inter-corpus. */
function appMsg(texte, erreur) {
  const el = $("#m-appartenance-msg");
  el.textContent = texte || "";
  el.classList.toggle("erreur", !!erreur);
}

async function loadAppartenance(albumId) {
  const bloc = $("#m-appartenance"), liste = $("#m-appartenance-liste"),
        cible = $("#m-appartenance-cible");
  bloc.hidden = !albumId;
  if (!albumId) return;
  let siennes = [], toutes = [];
  try {
    siennes = await apiGet(`/api/albums/${albumId}/collections`);
    toutes = await apiGet("/api/collections");
  } catch (e) { appMsg(e.message, true); return; }
  const dedans = new Set(siennes.map((c) => c.id));
  liste.innerHTML = siennes.map((c) => `
    <li><span class="col-nom">${esc(c.nom)}</span>
        <button class="ghost small" data-sortir="${c.id}" type="button"
                title="Sortir de cette collection">✕</button></li>`).join("");
  liste.querySelectorAll("[data-sortir]").forEach((b) => {
    b.onclick = async () => {
      try {
        await apiSend("DELETE", `/api/albums/${albumId}/collections/${b.dataset.sortir}`);
        appMsg("");
        loadAppartenance(albumId);
      } catch (e) { appMsg(e.message, true); }
    };
  });
  cible.innerHTML = "";
  const restantes = toutes.filter((c) => !dedans.has(c.id));
  for (const c of restantes) cible.appendChild(new Option(c.nom, String(c.id)));
  cible.disabled = !restantes.length;
  $("#m-appartenance-add").disabled = !restantes.length;
}

async function rangerAlbum() {
  const id = state.editingId, cible = $("#m-appartenance-cible").value;
  if (!id || !cible) return;
  try {
    await apiSend("PUT", `/api/albums/${id}/collections/${cible}`);
    appMsg("");
    loadAppartenance(id);
  } catch (e) { appMsg(e.message, true); }
}

/* ── Moteurs (SANTE-1) — la présence n'est pas le fonctionnement ───────────────────
   Le panneau qui rend le contrôle PROFOND atteignable : il existait depuis `ed17b32`,
   mais il fallait connaître `?profond=1` et l'appeler à la main — ce qu'un opérateur sans
   accès shell, seul public de la question, ne découvrira jamais tout seul.

   La RÈGLE d'affichage (présent ≠ opérationnel, absent ≠ en panne) vit dans
   `static/lib/sante.js`, pure et testée sous Node : elle croise deux réponses du serveur,
   et c'est le genre de logique qu'un test lisant le source déclare couverte sans l'être.
   Ici, il ne reste que du DOM. */
const SANTE_ETAT = { rapide: null, profond: null };

function santeMsg(texte, erreur) {
  const el = $("#sante-msg");
  el.textContent = texte || "";
  el.classList.toggle("erreur", !!erreur);
}

function santeRendu() {
  $("#sante-body").innerHTML = BDSante.MOTEURS.map((m) => {
    const e = BDSante.etat(SANTE_ETAT.rapide, SANTE_ETAT.profond, m);
    return `<div class="sante-ligne">
      <div class="sante-tete">
        <b>${esc(m.nom)}</b>
        <span class="sante-etat sante-${esc(e.etat)}">${esc(e.mot)}</span>
      </div>
      <p class="muted small sante-note">${esc(m.role)} · ${esc(e.note)}</p>
    </div>`;
  }).join("");
}

async function santeCharger() {
  try {
    SANTE_ETAT.rapide = await apiGet("/api/sante");
  } catch (e) {
    $("#sante-body").innerHTML = `<p class="col-note">${esc(e.message)}</p>`;
    return;
  }
  santeRendu();
}

/* Occupé, mais TOUJOURS FOCUSABLE — `aria-disabled` et non `disabled`, et ce n'est pas
   du purisme. Désarmer pour de bon un bouton qui porte le FOCUS le fait rendre au
   <body> : la modale cesse alors de piéger Tab et Échap ne la ferme plus, pendant les
   quinze secondes que dure l'import de torch. Une modale devient un cul-de-sac au
   clavier sans qu'aucune exception ne soit levée, et l'audit axe n'y voit rien — il
   photographie un écran, il n'appuie sur aucune touche. C'est un test de bout en bout
   qui l'a trouvé, en cherchant autre chose. */
function santeOccupe(occupe) {
  const b = $("#sante-eprouver");
  b.setAttribute("aria-busy", occupe ? "true" : "false");
  if (occupe) b.setAttribute("aria-disabled", "true");
  else b.removeAttribute("aria-disabled");
}

const santeEnCours = () => $("#sante-eprouver").getAttribute("aria-disabled") === "true";

/* Le contrôle profond, sur clic et JAMAIS au chargement : c'est un acte coûteux (torch
   en mémoire), et une route de santé qui charge les moteurs pour répondre n'est plus une
   route de santé. Le bouton s'annonce occupé pendant l'appel — le premier peut durer une
   minute, et rien à l'écran ne le dirait autrement. */
async function santeEprouver() {
  if (santeEnCours()) return;        // `aria-disabled` n'empêche pas le clic : nous, si
  santeOccupe(true);
  santeMsg("Chargement réel des moteurs… le premier appel peut durer une minute.");
  try {
    const d = await apiGet("/api/sante?profond=1");
    SANTE_ETAT.rapide = d;
    SANTE_ETAT.profond = d.profond || {};
    santeRendu();
    const bilan = BDSante.bilan(SANTE_ETAT.rapide, SANTE_ETAT.profond);
    santeMsg(bilan.texte, bilan.erreur);
  } catch (e) {
    santeMsg(e.message, true);
  } finally {
    santeOccupe(false);
  }
}

function openSante() {
  // Une épreuve en cours SURVIT à la fermeture du panneau — le fetch continue, et le
  // bouton reste occupé. Rouvrir ne doit donc pas effacer son message : on retrouverait
  // un bouton grisé sans un mot pour l'expliquer, pendant les quinze secondes que dure
  // l'import de torch, et ça se lit comme une panne du panneau lui-même.
  if (!santeEnCours()) santeMsg("");
  $("#sante-modal").hidden = false;
  santeCharger();
  $("#sante-eprouver").focus();
}

function closeSante() { $("#sante-modal").hidden = true; }

function setup() {
  setupBack();
  $("#btn-new").onclick = () => openModal(null);
  $("#m-save").onclick = saveAlbum;
  $("#m-cancel").onclick = closeModal;
  $("#m-contrib-add").onclick = addContribution;
  ["#m-contrib-nom", "#m-contrib-role"].forEach((id) =>
    $(id).addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); addContribution(); }
    }));
  $("#album-modal").addEventListener("mousedown", (e) => {
    if (e.target.id === "album-modal") closeModal();
  });
  // Modale accessible : role=dialog, piège à focus, Échap, retour du focus (source unique).
  if (window.BDDialog)
    BDDialog.register($("#album-modal"),
      { box: ".modal-box", labelledby: "modal-title", onClose: closeModal });
  PASSES.forEach((p) => { $("#pass-" + p).onchange = updateSelInfo; });
  $("#btn-run").onclick = runBatch;
  // Collections (AUTH-3) : l'écran qui remplace `tools/gerer_collections.py`.
  $("#btn-collections").onclick = openCollections;
  $("#col-close").onclick = closeCollections;
  // SANTE-1 : le contrôle profond, atteignable au clic. Pas de préchargement — ouvrir le
  // panneau ne coûte qu'un contrôle rapide, éprouver est un geste séparé et volontaire.
  $("#btn-sante").onclick = openSante;
  $("#sante-close").onclick = closeSante;
  $("#sante-eprouver").onclick = santeEprouver;
  $("#sante-modal").addEventListener("mousedown", (e) => {
    if (e.target.id === "sante-modal") closeSante();
  });
  if (window.BDDialog)
    BDDialog.register($("#sante-modal"),
      { box: ".modal-box", labelledby: "sante-title", onClose: closeSante });
  $("#col-add").onclick = creerCollection;
  $("#col-nom").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); creerCollection(); }
  });
  $("#m-appartenance-add").onclick = rangerAlbum;
  $("#collections-modal").addEventListener("mousedown", (e) => {
    if (e.target.id === "collections-modal") closeCollections();
  });
  if (window.BDDialog)
    BDDialog.register($("#collections-modal"),
      { box: ".modal-box", labelledby: "collections-title", onClose: closeCollections });
  // AUTH-1 — amorcé ici, et non à la seule ouverture des collections : `parQui()` a besoin
  // du login courant pour dire « par vous », et la table des planches se dessine bien avant
  // que quiconque ouvre ce panneau. Amorcer n'est pas attendre — c'est `openAlbum()` qui
  // attend, juste avant de dessiner.
  colChargerEtat();
  loadCorpus();   // stats d'en-tête (bande 2)
  loadAlbums();
  pollJobs();     // reprend l'affichage d'un éventuel job déjà en cours
}

setup();
