/* ===================================================================
   BéDéditeur — page Bibliothèque / gestion de corpus (vanilla JS)
   Gère les albums (CRUD + métadonnées), les planches (ouvrir/supprimer),
   le traitement par lot (segmentation / bulles / OCR) en arrière-plan — et,
   depuis COL-2, ce que chaque collection EST (la créer, la décrire, l'exporter).
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
  rafraichirCollections();   // COL-2 : le décompte d'albums bouge
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
  MOI = await identite();
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
    <div class="table-cadre" tabindex="0" role="region" aria-label="Planches de l'album">
      <table class="corpus-table planches-table">
        <thead><tr><th class="c-chk" aria-label="Sélection"></th><th aria-label="Aperçu"></th><th>Planche</th><th>Statut</th>
          <th class="c-num">Régions</th><th class="c-num">Annotées</th>
          <th>Relecture</th><th>Validée</th><th aria-label="Actions"></th></tr></thead>
        <tbody>${planchesRows}</tbody>
      </table>
    </div>`;

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
  // AUTH-12 — seulement celles où l'on ÉCRIT : une collection qu'on ne fait que lire
  // menait à « Collection N introuvable » à l'enregistrement. Le serveur le dit
  // (`ecrivable`), comme `exportable` pour l'export.
  cols = cols.filter((c) => c.ecrivable);
  if (!cols.length) {
    // Sans collection où écrire, deux cas que la note ne doit pas confondre : qui écrit
    // PARTOUT (administrateur, mono-poste) verra naître la collection de repli ; les
    // autres seront refusés, et le savoir avant de remplir le formulaire vaut mieux.
    const moi = await Promise.resolve(window.BDMoi).catch(() => null);
    note.textContent = moi && moi.acces && moi.acces.total
      ? "Aucune collection : l'album entrera dans une collection par défaut, créée à "
        + "cette occasion."
      : "Vous n'écrivez dans aucune collection : l'album ne pourra pas être créé. "
        + "Demandez un accès en écriture au propriétaire d'une collection.";
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
  // Par son IDENTIFIANT, et non par `$(".contrib-add")` : ce sélecteur rendait la
  // PREMIÈRE ligne de cette classe dans la page. C'était déjà celle de l'appartenance et
  // non celle des contributions ; depuis COL-2, c'eût été le formulaire de création de
  // collection, masqué à chaque « Nouvel album » sans qu'aucune erreur ne le dise.
  $("#m-contrib-ligne").style.display = exist ? "" : "none";
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
/* L'identité courante, pour dire « verrouillé par vous » plutôt que par votre propre nom.
   Elle vient de `common.identite()` depuis UX-10 : la page d'administration en a besoin
   aussi, pour d'autres raisons, et deux copies auraient fini par se répondre autrement. */
let MOI = { login: null, groupes_admin: [] };

function parQui(p) {
  if (!p.verrou_par) return "";
  if (MOI.login && p.verrou_par === MOI.login) return "par vous ";
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
        rafraichirCollections();
      } catch (e) { appMsg(e.message, true); }
    };
  });
  cible.innerHTML = "";
  // AUTH-12 — ranger exige d'écrire dans la collection cible : n'offrir que celles-là.
  const restantes = toutes.filter((c) => !dedans.has(c.id) && c.ecrivable);
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
    rafraichirCollections();
  } catch (e) { appMsg(e.message, true); }
}


/* ═══════════════════════════════════════════════════════════════════════════
   Collections (COL-2) — ce que chaque collection EST

   La frontière, tranchée le 2026-09-11 : QUI ENTRE relevait de l'instance et vivait dans
   l'Administration ; CE QUE LA COLLECTION EST relève du corpus et vit ici — la créer, la
   renommer, la supprimer, la décrire, désigner son référent, régler sa diffusion,
   l'exporter. Tout cela s'était accumulé dans le panneau des accès, et le régime de
   diffusion ne s'y écrivait même pas : passer une collection en « public » demandait
   `tools/gerer_collections.py`, donc un shell.

   ROUVERTE le 2026-09-17 (AUTH-12, décision 2 (b)) : qui entre dans UNE collection se règle
   désormais ICI, en tête de la collection dépliée — cf. « Qui entre » plus bas.
   L'Administration ne garde que la vue transverse des comptes et des groupes. Déménagé,
   pas dupliqué (UX-10).

   LA GARDE RESTE SUR L'ACTE, et ce bloc en pose TROIS. Créer n'exige aucun droit — une
   identité suffit : refuser la création à qui n'a encore rien rendrait l'outil inutilisable
   au premier jour. Éditer, renommer, supprimer exigent la propriété (`administrable`, que
   le serveur calcule). Lire les descripteurs est ouvert à qui voit la collection. Une garde
   unique posée sur le bloc masquerait le bouton de création à tout arrivant, et l'erreur
   échouerait en se FERMANT : c'est mot pour mot AUTH-4.
   ═══════════════════════════════════════════════════════════════════════════ */

/* Le vocabulaire du régime de diffusion — en DOUBLE de `config.STATUTS_DIFFUSION`, parce
   que les gabarits sont servis tels quels et qu'aucune route ne le publie. Leur accord est
   MESURÉ : `tests/test_collections_admin.py` échoue si l'un bouge sans l'autre. La valeur
   vide est « sans régime » — NULL en base, l'état de toute collection neuve. */
const REGIMES_DIFFUSION = [
  ["", "sans régime"],
  ["public", "public"],
  ["embargo", "sous embargo"],
  ["restreint", "restreint"],
  ["prive", "privé"],
];

/* Les champs, dans l'ordre où on les lit, et rangés par ce qu'ils ENGAGENT (fiche COL-2) :
   un formulaire plat mettrait le nom et la base légale sur le même plan. `responsables`
   n'y est pas, et c'est voulu : scientifique, porteur d'ORCID, parti au dépôt, il ne passe
   pas par `CollectionUpdate` et reste à `tools/gerer_collections.py`. */
const COL_GROUPES = [
  { id: "description", legende: "Description", champs: [
    { cle: "nom", libelle: "Nom" },
    { cle: "description", libelle: "Description", zone: true },
    { cle: "date_debut", libelle: "Début", aide: "AAAA ou AAAA-MM-JJ" },
    { cle: "date_fin", libelle: "Fin", aide: "AAAA ou AAAA-MM-JJ" },
  ] },
  { id: "diffusion", legende: "Diffusion — ce qui sort de l'instance", champs: [
    { cle: "statut_diffusion", libelle: "Régime de diffusion", regime: true },
    // Un champ TEXTE et non `type=date` : un champ date affiche VIDE une valeur qu'il ne
    // sait pas lire. Une date illisible disparaîtrait donc de l'écran, et le premier
    // enregistrement l'effacerait — une levée d'embargo déguisée en faute de frappe.
    { cle: "date_embargo", libelle: "Fin d'embargo", aide: "AAAA-MM-JJ" },
    { cle: "licence_defaut", libelle: "Licence", aide: "ex. CC-BY-4.0" },
    { cle: "base_legale", libelle: "Base légale" },
  ] },
  { id: "referent", legende: "Référent — à qui s'adresser", champs: [
    { cle: "referent_nom", libelle: "Nom lisible" },
    { cle: "referent_contact", libelle: "Contact", aide: "Courriel ou adresse de page" },
  ] },
];

/* Vrai dès que la liste a été dessinée une fois : avant, un rafraîchissement des décomptes
   n'a rien à rafraîchir, et le déclencher ferait dessiner la liste deux fois au démarrage,
   dont une AVANT que l'état ShareDocs soit connu. */
let COLS_RENDUES = false;

/* COL-2 (2026-09-16) — un message s'affiche LÀ OÙ L'ON A AGI.

   Il n'y avait qu'une ligne, `#col-msg`, sous TOUTE la liste. La passe de recette y a vu
   arriver le refus du nom réservé, rouge et lisible — et ne l'a pas vu : il tombait sous
   les autres collections, loin du bouton. La suite ne pouvait pas le dire, elle lisait le
   texte de la ligne et jamais sa place. Chaque collection dépliée porte donc SA ligne,
   sous ses boutons, et la création a la sienne, sous son champ : `el` est toujours la
   ligne du geste, jamais une ligne commune. */
function colMsg(el, texte, erreur) {
  // UN message à la fois pour tout le bloc, comme au temps de la ligne unique, que chaque
  // geste écrasait. Les lignes vivant désormais chacune dans sa collection, écrire ici doit
  // effacer les autres : sinon un refus resterait posé — et reposé à chaque rechargement —
  // à côté d'un formulaire qui ne contient plus ce qu'il refusait, ou « créée » au-dessus
  // d'une collection qu'on vient de supprimer. Trouvé par la passe de revue (2026-09-16).
  document.querySelectorAll("#collections-bloc .col-msg").forEach((l) => {
    if (l === el) return;
    if (l.dataset.trace) { l.remove(); return; }
    l.textContent = "";
    l.classList.remove("erreur", "alerte");
  });
  el.textContent = texte || "";
  // `erreur` vaut `true` pour un refus, « alerte » pour ce qui a RÉUSSI mais doit se lire :
  // un accès accordé à un nom que l'annuaire ne connaît pas (AUTH-12, décision 4).
  el.classList.toggle("erreur", erreur === true);
  el.classList.toggle("alerte", erreur === "alerte");
}

/* Une ligne de message qui n'appartient plus à aucune collection : ce qui reste quand
   celle qui parlait a disparu — supprimée, ou toute la liste remplacée par une erreur de
   relecture. Marquée, pour que le geste suivant l'ôte au lieu de la vider. */
function colTrace(texte, erreur) {
  const p = document.createElement("p");
  p.className = "col-msg muted small";
  p.dataset.trace = "1";
  colMsg(p, texte, erreur);
  return p;
}

/* Ce qu'une collection dépliée affiche, relevé AVANT qu'un rechargement ne la détruise.
   Enregistrer redessine la liste, donc la collection qu'on vient de modifier : sans ce
   relevé, sa confirmation partirait avec elle, une fraction de seconde après être née. */
function colMsgReleve(d) {
  const l = d.querySelector(".col-msg-formulaire");
  return l && l.textContent ? { texte: l.textContent, erreur: l.classList.contains("erreur") }
                            : null;
}

/* Les refus du serveur sont RENDUS, jamais avalés : un 409 qui dit combien d'albums une
   suppression laisserait sans collection, un 422 qui nomme les valeurs admises, un 403 qui
   dit qu'aucune identité ne parvient. Trois causes qui ne se corrigent pas de la même
   façon, qu'un « échec » générique ferait prendre pour un bug. */
async function colTenter(el, fn) {
  try { await fn(); colMsg(el, ""); return true; }
  catch (e) { colMsg(el, e.message || "Échec", true); return false; }
}

/* Le libellé d'un régime. Une valeur HORS vocabulaire — un reste d'avant la validation —
   s'affiche telle quelle plutôt que d'être maquillée en « sans régime ». */
function colRegime(v) {
  const r = REGIMES_DIFFUSION.find(([val]) => val === (v || ""));
  return r ? r[1] : String(v);
}

/* ── Déplacé TEL QUEL de l'Administration (COL-2, 2026-09-11) ─────────────────────────
   L'état d'embargo, le référent lu, l'export de dépôt et l'état ShareDocs ci-dessous sont
   ceux qui vivaient dans le panneau des accès, sans une ligne changée. La garde de l'export
   — lire pour télécharger, posséder pour déposer — n'est PAS l'affaire de ce déménagement :
   exporter devient un droit à part dans DROIT-2, qui la posera au serveur, à un seul
   endroit. La restreindre ici aurait laissé les neuf autres portes ouvertes en donnant
   l'impression d'avoir fermé. */

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

/* Le dépôt ShareDocs. Il RÉUTILISE les réglages des lignes du dessus — la case
   « avec le texte relevé » et l'adresse du serveur d'images — parce que ce sont les mêmes
   réglages du même artefact : les redemander ici laisserait deux jeux de valeurs se
   contredire à l'écran, et personne ne saurait lequel est parti.

   Le bloc n'existe que pour qui ADMINISTRE la collection, et c'est le serveur qui tranche
   (403) : `administrable` ne fait que lui éviter de proposer un geste qu'il refusera.
   L'inverse — décider ici et laisser le serveur ouvert — est l'erreur qui ne se voit
   jamais, puisque l'écran a l'air correct. */
async function colDeposer(bouton) {
  const boite = bouton.closest(".col-export");
  const msg = boite.querySelector(".dep-msg");
  const [quoi, format] = boite.querySelector(".dep-choix").value.split("|");
  const base = boite.querySelector(".dep-base").value.trim();

  // La même règle que pour le téléchargement : un manifeste sans serveur d'images ne
  // part pas, et le dire avant d'appeler évite un aller-retour pour rien.
  const { refus } = BDDepot.urlDepot({ collectionId: bouton.dataset.col, quoi, format,
                                       baseUrl: base });
  if (refus) { msg.textContent = refus; msg.className = "dep-msg erreur"; return; }

  msg.className = "dep-msg";
  msg.textContent = "Dépôt en cours…";
  try {
    const r = await apiSend("POST", `/api/collections/${bouton.dataset.col}/depot/deposer`,
      { quoi, format, verbatim: Boolean(boite.querySelector("[data-verbatim]").checked),
        base_url: base, dossier: boite.querySelector(".dep-dossier").value.trim() });
    // Le compte EMPLOYÉ vient du serveur et s'affiche : un dépôt fait sous le compte de
    // l'instance alors qu'on en a un personnel doit se voir (SHARE-1).
    msg.textContent = `Déposé : ${r.depose} (compte ${r.compte}).`;
  } catch (e) {
    msg.className = "dep-msg erreur";
    msg.textContent = e.message || "Échec du dépôt.";
  }
}

/* Branche les boutons du bloc d'export. Appelé par les DEUX branches de `colDetail` :
   c'est le seul endroit où l'oubli serait silencieux — un bouton sans gestionnaire ne
   proteste pas, il ne fait rien. */
function colBrancherExport(box) {
  box.querySelectorAll("[data-dep]").forEach((b) => {
    b.type = "button";
    b.onclick = () => colTelecharger(b);
  });
  const dep = box.querySelector("[data-depot]");
  if (dep) { dep.type = "button"; dep.onclick = () => colDeposer(dep); }
}


/* EXP-1 — l'export de dépôt, pour qui n'a pas de shell.

   Ce bloc s'affiche dans les DEUX branches de `colDetail`, et c'est la leçon d'AUTH-4
   appliquée avant de se refaire prendre : une garde d'interface se pose sur l'ACTE, jamais
   sur l'écran qui le contient. Décrire une collection qu'on lit n'est pas la partager —
   le serveur n'exigeait ici que `peut_lire`, et le ranger sous le `return` réservé aux
   propriétaires en ferait, exactement comme le référent, un droit d'écriture déguisé. On
   se serait aperçu de rien : l'erreur échoue en se FERMANT, aucun test ne tombe, et une
   revue de sécurité l'approuve.

   Le nom du fichier vient du serveur (`Content-Disposition`) : le recomposer ici ferait
   diverger deux horodatages pour un seul export — même raison que l'export de figures.

   DROIT-2 (2026-09-11) — le serveur exige désormais le droit d'EXPORTER, une case que le
   propriétaire accorde accès par accès. Le bloc suit `exportable` : sans le droit, il se
   réduit à une note qui dit ce qui manque — dans les deux branches, toujours. La garde
   reste sur l'acte, au serveur ; l'écran évite seulement de proposer un geste perdu. */
function colExport(c) {
  if (!c.exportable) {
    return `
    <div class="col-export">
      <h4>Export de dépôt</h4>
      <p class="col-note">Exporter cette collection demande le droit d'exporter, que son
        propriétaire accorde accès par accès : la lire n'y suffit pas.</p>
    </div>`;
  }
  const b = `data-col="${c.id}"`;
  return `
    <div class="col-export">
      <h4>Export de dépôt</h4>
      <p class="muted small">Ce que produisaient les scripts <code>tools/</code>, sur cette
        collection seulement.</p>
      <div class="dep-ligne">
        <span class="dep-quoi">Fiche de description</span>
        <button class="ghost small" ${b} data-dep="description" data-fmt="json">JSON</button>
        <button class="ghost small" ${b} data-dep="description" data-fmt="csv">CSV</button>
      </div>
      <div class="dep-ligne">
        <span class="dep-quoi">Enregistrements</span>
        <button class="ghost small" ${b} data-dep="metadonnees" data-fmt="json">JSON</button>
        <button class="ghost small" ${b} data-dep="metadonnees" data-fmt="zip">CSV (zip)</button>
        <button class="ghost small" ${b} data-dep="metadonnees" data-fmt="xlsx">XLSX</button>
        <label class="dep-verbatim"><input type="checkbox" data-verbatim="1">
          <span>avec le texte relevé</span></label>
      </div>
      <div class="dep-ligne dep-iiif">
        <span class="dep-quoi">Manifeste IIIF
          <span class="dep-moment">au moment du dépôt</span></span>
        <input type="url" class="dep-base" placeholder="Adresse publique des images (facultatif)"
               aria-label="Adresse publique sous laquelle les images seront servies (facultatif)">
        <button class="ghost small" ${b} data-dep="iiif" data-fmt="zip">Télécharger</button>
      </div>
      <p class="muted small dep-aide">Le manifeste décrit les planches et <b>pointe</b> vers
        les images : il ne les contient pas, et n'attend pas un serveur IIIF — de simples
        JPEG suffisent. L'adresse est celle sous laquelle le dossier <code>derivatives/</code>
        sera publiquement servi : un partage ShareDocs, ou ce que rend l'entrepôt.
        <b>Laissez vide tant que les images ne sont publiées nulle part</b> — le manifeste
        sort alors en aperçu, et le déclare.</p>
      ${c.administrable ? `
      <div class="dep-ligne dep-depot">
        <span class="dep-quoi">Déposer sur ShareDocs</span>
        ${SD.connecte ? `
        <select class="dep-choix" aria-label="Artefact à déposer">
          ${BDDepot.choix().map((o) =>
            `<option value="${o.quoi}|${o.format}">${esc(o.libelle)}</option>`).join("")}
        </select>
        <input class="dep-dossier" placeholder="ex. @Home/mon-dossier (vide = racine)"
               aria-label="Dossier ShareDocs de destination, chemin relatif à la racine WebDAV">
        <button class="ghost small" ${b} data-depot="1">Déposer</button>`
        : `<a class="ghost small dep-connexion"
              href="${BDDepot.lienConnexionSharedocs()}">Se connecter à ShareDocs…</a>`}
      </div>
      ${SD.connecte
        ? `<p class="muted small dep-aide">Compte employé :
             <b>${esc(SD.actif ? (SD.actif.compte || "") : "")}</b>
             ${SD.actif && SD.actif.user ? `(${esc(SD.actif.user)})` : ""}.
             Le dossier est un chemin <b>relatif</b>, séparé par des barres obliques — pas
             le fil d'Ariane de l'interface web, dont les noms d'affichage diffèrent des
             chemins réels. Le dépôt ne crée aucun dossier manquant.</p>`
        : `<p class="muted small dep-aide">Aucune session ShareDocs n'est ouverte. Le lien
             ci-dessus ouvre la connexion dans l'Atelier et ramène ici.</p>`}` : ""}
      <p class="dep-msg" role="status" aria-live="polite"></p>
    </div>`;
}

/* Le téléchargement lui-même. Les refus du serveur sont RENDUS À L'ÉCRAN et non avalés :
   ils portent des messages qui distinguent quatre causes (pas publique, embargo en cours,
   date illisible, aucune collection nommée), et ces quatre-là ne se corrigent pas de la
   même façon. Les remplacer par « échec » perdrait tout ce que l'outil sait dire. */
async function colTelecharger(bouton) {
  const boite = bouton.closest(".col-export");
  const msg = boite.querySelector(".dep-msg");
  const quoi = bouton.dataset.dep;
  const verbatim = boite.querySelector("[data-verbatim]")?.checked;
  const base = boite.querySelector(".dep-base")?.value.trim();

  // L'adresse se DÉCIDE dans `static/lib/depot.js`, pas ici : trois erreurs y sont
  // muettes — `verbatim` envoyé à une route qui l'ignore, une adresse d'images non
  // encodée qui INJECTE des paramètres, un format proposé pour le mauvais export. Une
  // concaténation dans ce gestionnaire ne serait vérifiable que par un test qui relit le
  // source, et le dépôt sait depuis `sante.js` ce que vaut cette lecture-là.
  const { url, refus } = BDDepot.urlDepot({
    collectionId: bouton.dataset.col, quoi, format: bouton.dataset.fmt, verbatim,
    baseUrl: base,
  });
  if (refus) {
    msg.textContent = refus;
    msg.className = "dep-msg erreur";
    return;
  }

  msg.className = "dep-msg";
  msg.textContent = "Préparation…";
  try {
    const r = await fetch(url);
    if (!r.ok) {
      throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    }
    const nom = (r.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/);
    const href = URL.createObjectURL(await r.blob());
    const a = document.createElement("a");
    a.href = href; a.download = nom ? nom[1] : "export";
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(href);
    msg.textContent = nom ? `${nom[1]} téléchargé.` : "Export téléchargé.";
  } catch (e) {
    msg.className = "dep-msg erreur";
    msg.textContent = e.message || "Échec de l'export.";
  }
}


/* L'état de la session ShareDocs, lu une fois par chargement de page (EXP-1).

   Il ne DÉCIDE rien — le serveur refusera de lui-même —, il évite seulement de proposer
   un dépôt qui échouerait sur une erreur de transport WebDAV, laquelle ne nomme pas la
   cause. Relu au chargement suffit : on revient ici par un aller-retour, qui recharge. */
let SD = { connecte: false, actif: null };

async function loadEtatSharedocs() {
  // Un échec ici ne doit rien empêcher : sans état connu, on retombe sur « pas de
  // session », qui propose le lien de connexion. Se tromper dans ce sens fait proposer un
  // geste inutile ; se tromper dans l'autre ferait échouer un dépôt sans l'expliquer.
  try { SD = await apiGet("/api/sharedocs/etat"); }
  catch (e) { SD = { connecte: false, actif: null }; }
}


/* Un champ du formulaire. Aucune valeur n'est interprétée ici : le serveur valide, et ses
   refus sont rendus tels quels. Une valeur de régime HORS vocabulaire reste sélectionnée et
   nommée comme telle, pour qu'enregistrer autre chose ne la fasse pas disparaître en
   silence. */
function colChamp(c, f) {
  const id = `col-${c.id}-${f.cle}`;
  const v = c[f.cle] == null ? "" : String(c[f.cle]);
  const a = `id="${id}" data-champ="${f.cle}"`;
  let champ;
  if (f.regime) {
    const connue = REGIMES_DIFFUSION.some(([val]) => val === v);
    champ = `<select ${a}>${REGIMES_DIFFUSION.map(([val, lib]) =>
      `<option value="${val}"${val === v ? " selected" : ""}>${esc(lib)}</option>`).join("")}${
      connue ? "" : `<option value="${esc(v)}" selected>${esc(v)} (hors vocabulaire)</option>`}</select>`;
  } else if (f.zone) {
    champ = `<textarea ${a} rows="2">${esc(v)}</textarea>`;
  } else {
    champ = `<input ${a} value="${esc(v)}" autocomplete="off"${
      f.aide ? ` placeholder="${esc(f.aide)}"` : ""}>`;
  }
  return `<div class="contrib-add col-champ"><label for="${id}">${esc(f.libelle)}</label>${champ}</div>`;
}

/* Ce que chaque groupe ENGAGE, dit sous ses champs. La date d'embargo est la plus traître :
   l'écran doit dire ce qu'elle FAIT, pas seulement l'accepter (piège écrit dans COL-2). */
function colNoteGroupe(c, g) {
  if (g.id === "diffusion") {
    const emb = colEmbargo(c);
    return `${emb ? `<p class="col-note">${esc(emb[2])}</p>` : ""}
      <p class="col-note">Le régime décide de ce qui SORT de l'instance — les images d'un
        manifeste IIIF, l'avertissement d'un dépôt ; à l'intérieur, il ne borne rien. La date
        d'embargo RETIENT : tant qu'elle court, les scans ne sortent pas, même d'une
        collection « public ». Elle ne publie jamais rien d'elle-même — une échéance passée
        se signale sans rien lever, et une date illisible retient aussi.</p>`;
  }
  if (g.id === "referent") {
    return `<p class="col-note">C'est une ADRESSE, pas un droit : la nommer n'accorde rien et
      ne retire rien. Elle ne sort d'aucun export, et ce n'est pas le responsable
      scientifique, qui part au dépôt avec son ORCID.</p>`;
  }
  return "";
}

function colFormulaire(c) {
  return COL_GROUPES.map((g) => `
    <fieldset class="modal-section">
      <legend>${esc(g.legende)}</legend>
      ${g.champs.map((f) => colChamp(c, f)).join("")}
      ${colNoteGroupe(c, g)}
    </fieldset>`).join("") + `
    <div class="modal-actions">
      <button class="primary small" data-enregistrer="1" type="button">Enregistrer</button>
      <button class="ghost small" data-supprimer="1" type="button">Supprimer la collection</button>
    </div>
    <p class="col-msg col-msg-formulaire muted small" role="status" aria-live="polite"></p>`;
}

/* Ce qu'un participant non propriétaire LIT. Il sait sous quel régime il travaille, et à
   qui écrire ; il ne peut rien changer. Le régime s'affiche toujours, même vide : « sans
   régime » est une information, pas une absence. */
function colDescriptionLue(c) {
  const lignes = [`<p class="col-note"><b>Régime de diffusion</b> :
    ${esc(colRegime(c.statut_diffusion))}</p>`];
  for (const g of COL_GROUPES) {
    for (const f of g.champs) {
      if (f.cle === "nom" || f.regime || g.id === "referent") continue;
      const v = c[f.cle];
      if (v == null || String(v).trim() === "") continue;
      lignes.push(`<p class="col-note"><b>${esc(f.libelle)}</b> : ${esc(String(v))}</p>`);
    }
  }
  const emb = colEmbargo(c);
  if (emb) lignes.push(`<p class="col-note">${esc(emb[2])}</p>`);
  return lignes.join("");
}

/* ═══════════════════════════════════════════════════════════════════════════
   Qui entre (AUTH-12, étape 3) — les accès d'une collection, dans SA fiche

   Ils vivaient dans l'Administration, panneau « 👥 Accès aux collections », au nom d'une
   frontière tranchée deux fois le 2026-09-10 : qui entre relève de l'instance. Hugo l'a
   rouverte le 2026-09-17 (décision 2 (b) d'AUTH-12) : le trajet le plus courant d'un
   propriétaire — créer sa collection, puis y faire entrer ses étudiants — traversait deux
   écrans, dont un intitulé « ce qui porte sur l'instance ». Déménagé, pas dupliqué :
   l'Administration a perdu le panneau dans le même commit, et ne garde que la vue
   TRANSVERSE des comptes et des groupes.

   EN ACTES, JAMAIS EN NIVEAUX. Le tableau lit la description des droits servie par
   `GET /api/droits` et n'écrit ni acte, ni libellé, ni niveau : toute la logique est dans
   `static/lib/droits.js`, éprouvée sur la description d'aujourd'hui ET sur deux issues
   hypothétiques d'AUTH-10. Une case par CRAN : des actes que le serveur accorde ensemble
   ne se cochent pas séparément.

   DEUX LECTURES, ET LA SECONDE N'ATTEND PAS. `…/acces` dessine le tableau tout de suite ;
   `…/annuaire` arrive après et remplit « Signal » et la liste des groupes. Un annuaire en
   panne ne retarde donc aucun geste (c'est la raison même des deux routes).

   CE QUE LE REFUS D'ÉCRAN NE FERME PAS. Le `PUT` d'un accès RE-POSE un niveau : « faire
   entrer » un nom déjà présent le rétrograderait en lecture. L'écran le refuse avant
   d'envoyer, sur le couple (compte ou groupe, nom exact) — mais un autre onglet, ou une
   liste relue avant le geste d'un autre, peut encore rétrograder. Limite écrite dans la
   fiche AUTH-12, pas fermée côté serveur à cette étape.
   ═══════════════════════════════════════════════════════════════════════════ */

/* La description des droits, lue UNE fois par page. Illisible, elle vaut null : l'écran le
   dit et ne dessine aucune case, plutôt que d'inventer un modèle. */
let DROITS = null;
const DROITS_PRETS = apiGet("/api/droits")
  .then((d) => { DROITS = BDDroits.estValide(d) ? d : null; })
  .catch(() => { DROITS = null; });

/* Sous 48em, le tableau devient une carte par accès (tranché par Hugo le 2026-09-17). Le
   seuil est celui de la règle `@media` de `style.css` ; on redessine au franchissement. */
const QE_ETROIT = window.matchMedia("(max-width: 47.9375em)");

/* L'état de « Qui entre », par collection : ce qu'on a lu, et ce qu'une adresse demande. */
const QE = new Map();
let QE_PRESELECTION = null;       // { id, groupe } — `?collection=…&groupe=…`, consommé une fois

function qeEtat(c) {
  if (!QE.has(c.id)) QE.set(c.id, { acces: null, erreur: null, annuaire: null });
  const etat = QE.get(c.id);
  etat.c = c;
  return etat;
}

function qeCle(a) {
  return `data-genre="${esc(a.genre)}" data-principal="${esc(a.principal)}"`;
}

function qeSel(a) {
  return `[data-genre="${CSS.escape(a.genre)}"][data-principal="${CSS.escape(a.principal)}"]`;
}

/* Le nom d'un accès, avec ce qu'il EST : l'icône pour l'œil, le mot pour le lecteur d'écran.
   « compte » et non « utilisateur » : lexique de la décision 7 d'AUTH-12. */
function qeQui(a) {
  const groupe = a.genre === "groupe";
  return `<span aria-hidden="true">${groupe ? "👥" : "👤"}</span> `
    + `<span class="sr-only">${groupe ? "groupe" : "compte"} </span>${esc(a.principal)}`;
}

/* Les valeurs des cases hors rang d'un accès, sous leur `champ` : ce que le serveur rend
   dans `…/acces`, et ce que le `PUT` renvoie. */
function qeValeurs(a) {
  return Object.fromEntries(DROITS.hors_rang.map((h) => [h.champ, !!a[h.champ]]));
}

/* Ce que l'annuaire dit d'un accès : « trouve », « inconnu », « non_verifie »,
   « sans_annuaire », ou null tant qu'il n'a pas répondu. */
function qeVerification(etat, genre, principal) {
  const an = etat.annuaire;
  if (!an || !Array.isArray(an.acces)) return null;
  const par = genre === "groupe" ? "groupe" : "compte";
  const v = an.acces.find((x) => x.par === par
    && (par === "groupe" ? x.groupe : x.login) === principal);
  return v ? v.verification : null;
}

/* La colonne « Signal » (UX-4). Ce que l'annuaire dit d'abord ; puis, pour un compte,
   qu'il n'a pas encore ouvert l'application (AUTH-6) — l'observation seule, qui ne
   distingue pas une faute de frappe d'un arrivant, et ne doit pas le prétendre. */
function qeSignal(etat, a) {
  const v = qeVerification(etat, a.genre, a.principal);
  const marques = [];
  if (v === "inconnu") marques.push(`<span class="qe-marque">inconnu de l'annuaire</span>`);
  else if (v === "non_verifie") marques.push(`<span class="qe-marque">non vérifié</span>`);
  if (a.jamais_vu === true && v !== "inconnu") {
    marques.push(`<span class="acces-jamais-vu">n'a pas encore ouvert l'application</span>`);
  }
  return marques.join(" ");
}

function qeDepuis(a) {
  return esc((a.date_creation || "").slice(0, 10));
}

/* Le tableau, au-dessus de 48em. Les en-têtes de colonnes sont les ACTES ; une case par
   cran, dont la cellule couvre les actes qu'elle accorde ensemble. Le nom accessible de
   chaque case CROISE l'en-tête de ligne et ceux de ses colonnes (`aria-labelledby`) : un
   lecteur d'écran entend « groupe annotateurs, annoter, organiser les albums… » sur une
   case unique, c'est-à-dire la liaison dite en clair. */
/* L'identifiant de l'avertissement affiché : celui de son PREMIER acte, qui suffit à le
   distinguer — un texte n'est rendu qu'une fois, quel que soit le nombre d'actes qui le
   portent. */
function qeIdAvertissement(c, av) {
  return `qe-${c.id}-av-${av.actes[0].code}`;
}

/* Les avertissements AFFICHÉS, rangés par cran : la case d'un cran est DÉCRITE par
   l'avertissement de l'acte qu'elle accorde (`aria-describedby`) — cocher ce cran accorde
   cet acte, donc la description est vraie et non décorative. Recalculé ici plutôt que passé
   de signature en signature : `avertissements` est une fonction pure. */
function qeDescriptions(c, etat) {
  const par = {};
  if (!DROITS || !etat.acces) return par;
  for (const av of BDDroits.avertissements(DROITS, etat.acces.map((a) => a.niveau))) {
    for (const n of av.niveaux) par[n] = qeIdAvertissement(c, av);
  }
  return par;
}

function qeDecritPar(decrit, niveau) {
  return decrit[niveau] ? ` aria-describedby="${esc(decrit[niveau])}"` : "";
}

function qeTable(c, etat) {
  const id = c.id;
  const cols = BDDroits.colonnes(DROITS);
  const decrit = qeDescriptions(c, etat);
  const idsCran = (col) => (col.actes.length
    ? col.actes.map((a) => `qe-${id}-a-${a.code}`) : [`qe-${id}-n-${col.niveau}`]);
  // Les actes accordés ENSEMBLE sont CHAPEAUTÉS, sur deux rangs d'en-tête. Le trait dessiné
  // sous leur case unique disait bien la liaison, et disait aussi autre chose : deux pixels
  // en travers d'une cellule, une case posée au milieu, c'est le vocabulaire d'un curseur
  // qu'on croit pouvoir glisser (relevé par Hugo le 2026-09-18). L'intention était
  // structurelle, le rendu décoratif, et c'est le rendu qui gagne. Un chapeau EST la
  // structure : il ne se confond avec rien, et un lecteur d'écran l'annonce — un dessin, lui,
  // ne s'annonce jamais. Le second rang n'existe que s'il y a quelque chose à chapeauter.
  const groupe = (col) => col.type === "cran" && col.actes.length > 1;
  const chapeaux = cols.some(groupe);
  const rang2 = chapeaux ? ' rowspan="2"' : "";
  const idsEnTete = (col) => (groupe(col) ? [`qe-${id}-g-${esc(col.niveau)}`] : idsCran(col));
  const tetes = cols.map((col) => {
    if (col.type !== "cran") {
      return `<th scope="col"${rang2} id="qe-${id}-h-${esc(col.code)}" class="qe-hors-rang">${esc(col.libelle)}</th>`;
    }
    if (groupe(col)) {
      return `<th scope="colgroup" colspan="${col.actes.length}" class="qe-groupe"`
        + ` id="${idsEnTete(col)[0]}">${esc(col.libelle)}</th>`;
    }
    const seul = col.actes.length ? col.actes[0] : { libelle: col.libelle };
    return `<th scope="col"${rang2} id="${idsCran(col)[0]}" class="qe-acte">${esc(seul.libelle)}</th>`;
  }).join("");
  // Le second rang ne porte QUE les actes chapeautés : les autres colonnes le traversent par
  // `rowspan`, et le navigateur range donc ces en-têtes sous leur chapeau, dans l'ordre.
  const sousTetes = chapeaux
    ? `<tr>${cols.filter(groupe).map((col) => col.actes.map((a, k) =>
        `<th scope="col" id="${idsCran(col)[k]}" class="qe-acte">${esc(a.libelle)}</th>`)
        .join("")).join("")}</tr>`
    : "";
  const lignes = etat.acces.map((a, i) => {
    const qui = `qe-${id}-r${i}`;
    const valeurs = qeValeurs(a);
    const hr = BDDroits.horsRang(DROITS, a.niveau, valeurs);
    const cellules = cols.map((col) => {
      if (col.type === "cran") {
        const n = Math.max(1, col.actes.length);
        const coche = BDDroits.cranCoche(DROITS, a.niveau, col.niveau);
        const libre = BDDroits.cranModifiable(DROITS, col.niveau);
        // `qe-lie` ne dessine plus rien : elle NOMME la cellule fusionnée, pour la feuille
        // comme pour le test qui vérifie que les actes liés n'ont qu'une case.
        return `<td class="qe-cran${n > 1 ? " qe-lie" : ""}"${n > 1 ? ` colspan="${n}"` : ""}>`
          + `<input type="checkbox" class="qe-case" data-cran="${esc(col.niveau)}" ${qeCle(a)}`
          + ` aria-labelledby="${qui} ${idsEnTete(col).join(" ")}"`
          + qeDecritPar(decrit, col.niveau)
          + `${coche ? " checked" : ""}${libre ? "" : " disabled"}></td>`;
      }
      const h = hr.find((x) => x.code === col.code);
      return `<td class="qe-hors-rang"><input type="checkbox" class="qe-case"`
        + ` data-hors-rang="${esc(col.code)}" data-hors-rang-champ="${esc(col.champ)}" ${qeCle(a)}`
        + ` aria-labelledby="${qui} qe-${id}-h-${esc(col.code)}"`
        + `${h.coche ? " checked" : ""}${h.d_office ? " disabled" : ""}>`
        + `${h.d_office ? ` <span class="muted small">(d'office)</span>` : ""}</td>`;
    }).join("");
    return `<tr ${qeCle(a)}><th scope="row" id="${qui}">${qeQui(a)}</th>${cellules}
      <td class="qe-depuis">${qeDepuis(a)}</td>
      <td class="qe-signal">${qeSignal(etat, a)}</td>
      <td><button class="ghost small qe-retirer" type="button" ${qeCle(a)}
                  aria-label="Retirer l'accès de ${esc(a.principal)}">✕</button></td></tr>`;
  }).join("");
  return `<div class="table-cadre qe-cadre" tabindex="0" role="region"
               aria-label="Qui entre dans ${esc(c.nom)}">
    <table class="corpus-table qe-table">
      <thead><tr><th scope="col"${rang2}>Qui</th>${tetes}<th scope="col"${rang2}>Depuis le</th>
        <th scope="col"${rang2}>Signal</th>
        <th scope="col"${rang2}><span class="sr-only">Retirer</span></th></tr>${sousTetes}</thead>
      <tbody>${lignes}</tbody>
    </table></div>`;
}

/* Les cartes, sous 48em : une par accès, une case par cran libellée des actes qu'elle
   accorde, puis les cases hors rang, et « Depuis le » en ligne. */
function qeCartes(c, etat) {
  const id = c.id;
  const crans = BDDroits.crans(DROITS);
  const decrit = qeDescriptions(c, etat);
  return `<ul class="qe-cartes">${etat.acces.map((a, i) => {
    const qui = `qe-${id}-r${i}`;
    const valeurs = qeValeurs(a);
    const cases = crans.map((cr) => {
      const lib = `${qui}-n-${cr.niveau}`;
      return `<label class="qe-case-carte"><input type="checkbox" class="qe-case"`
        + ` data-cran="${esc(cr.niveau)}" ${qeCle(a)} aria-labelledby="${qui} ${lib}"`
        + qeDecritPar(decrit, cr.niveau)
        + `${BDDroits.cranCoche(DROITS, a.niveau, cr.niveau) ? " checked" : ""}`
        + `${BDDroits.cranModifiable(DROITS, cr.niveau) ? "" : " disabled"}>`
        + ` <span id="${lib}">${esc(BDDroits.libelleCran(cr))}</span></label>`;
    }).join("") + BDDroits.horsRang(DROITS, a.niveau, valeurs).map((h) => {
      const lib = `${qui}-h-${h.code}`;
      return `<label class="qe-case-carte"><input type="checkbox" class="qe-case"`
        + ` data-hors-rang="${esc(h.code)}" data-hors-rang-champ="${esc(h.champ)}" ${qeCle(a)}`
        + ` aria-labelledby="${qui} ${lib}"${h.coche ? " checked" : ""}${h.d_office ? " disabled" : ""}>`
        + ` <span id="${lib}">${esc(h.libelle)}${h.d_office ? " (d'office)" : ""}</span></label>`;
    }).join("");
    const depuis = qeDepuis(a);
    return `<li class="qe-carte" ${qeCle(a)}>
      <div class="qe-carte-tete"><span class="qe-qui" id="${qui}">${qeQui(a)}</span>
        <span class="qe-signal">${qeSignal(etat, a)}</span>
        <button class="ghost small qe-retirer" type="button" ${qeCle(a)}
                aria-label="Retirer l'accès de ${esc(a.principal)}">✕</button></div>
      <div class="qe-carte-cases">${cases}</div>
      ${depuis ? `<p class="muted small qe-depuis">Depuis le ${depuis}</p>` : ""}</li>`;
  }).join("")}</ul>`;
}

function qeTableauHtml(c, etat) {
  if (etat.erreur) return `<p class="col-note">${esc(etat.erreur)}</p>`;
  if (!etat.acces) return `<p class="col-note">Chargement…</p>`;
  if (!DROITS) {
    return `<p class="col-note">La description des droits n'a pas pu être lue : les accès ne
      se règlent pas d'ici tant qu'elle manque.</p>
      <ul class="qe-noms">${etat.acces.map((a) =>
        `<li>${qeQui(a)} — ${esc(a.niveau)}</li>`).join("")}</ul>`;
  }
  if (!etat.acces.length) {
    return `<p class="col-note">Aucun accès n'est accordé sur cette collection.</p>`;
  }
  return QE_ETROIT.matches ? qeCartes(c, etat) : qeTable(c, etat);
}

/* Ce que la ligne d'ajout contenait, relevé avant de la redessiner : l'annuaire arrive
   APRÈS l'ouverture, et le nom qu'on a commencé à taper ne doit pas partir avec. */
function qeReleveAjout(sec) {
  const choix = sec.querySelector(".qe-choix");
  if (!choix) return null;
  return { choix: choix.value, touche: choix.dataset.touche === "1",
           nom: sec.querySelector(".qe-nom").value,
           genre: sec.querySelector(".qe-genre").value };
}

/* La ligne d'ajout, dans l'ordre de la décision 4 (2) : les GROUPES de l'annuaire (leurs
   noms seuls — le propriétaire ne voit ni les comptes ni les membres), puis la saisie
   libre, qui exige de dire « Compte » ou « Groupe » SANS valeur par défaut (COL-2, tranché
   le 2026-09-16 : un groupe accordé comme compte n'ouvre rien à personne). Et aucune
   présélection d'un groupe non plus : « Choisir… » en tête, sans quoi « + Faire entrer »
   accorderait le premier de la liste par inertie. */
function qeAjoutHtml(c, etat, garde) {
  if (!DROITS || etat.erreur || !etat.acces) return "";
  const id = c.id;
  const an = etat.annuaire;
  const groupes = an && Array.isArray(an.groupes) ? an.groupes : [];
  const valeurs = new Set(["", "autre", ...groupes.map((g) => `groupe:${g}`)]);
  let choix, nom = "", genre = "", touche = false;
  if (garde && garde.touche && valeurs.has(garde.choix)) {
    ({ choix, nom, genre, touche } = garde);
  } else if (garde && garde.choix === "autre" && (garde.nom || garde.genre)) {
    ({ choix, nom, genre } = garde);
  } else {
    choix = groupes.length ? "" : "autre";
  }
  // L'adresse `?collection=…&groupe=…` (« Ouvrir une collection à ce groupe… »), consommée
  // une fois l'annuaire connu : listé, le groupe est choisi ; absent, il est tapé.
  if (an && QE_PRESELECTION && QE_PRESELECTION.id === id) {
    const g = QE_PRESELECTION.groupe;
    QE_PRESELECTION = null;
    if (groupes.includes(g)) { choix = `groupe:${g}`; }
    else { choix = "autre"; nom = g; genre = "groupe"; }
    touche = true;
  }
  const opt = (v, lib) => `<option value="${esc(v)}"${v === choix ? " selected" : ""}>${esc(lib)}</option>`;
  return `<div class="qe-ajout-ligne">
      <label for="qe-choix-${id}">Faire entrer</label>
      <select id="qe-choix-${id}" class="qe-choix"${touche ? ' data-touche="1"' : ""}>
        ${opt("", "Choisir…")}
        ${groupes.length ? `<optgroup label="Groupes de l'annuaire">${groupes.map((g) =>
          opt(`groupe:${g}`, g)).join("")}</optgroup>` : ""}
        ${opt("autre", "Un compte, ou un groupe absent de la liste…")}
      </select>
      <span class="qe-libre"${choix === "autre" ? "" : " hidden"}>
        <input id="qe-nom-${id}" class="qe-nom col-principal" placeholder="nom exact"
               autocomplete="off" aria-label="Nom exact du compte ou du groupe"
               value="${esc(nom)}">
        <select id="qe-genre-${id}" class="qe-genre" aria-label="Compte ou groupe">
          <option value=""${genre ? "" : " selected"}>Compte ou groupe ?</option>
          <option value="utilisateur"${genre === "utilisateur" ? " selected" : ""}>Compte</option>
          <option value="groupe"${genre === "groupe" ? " selected" : ""}>Groupe</option>
        </select>
      </span>
      <button class="primary small qe-faire-entrer" type="button">+ Faire entrer</button>
    </div>`;
}

/* Les administrateurs d'instance lisent et écrivent toute collection sans figurer dans
   aucune liste d'accès (AUTH-4). Déménagée avec le panneau : sans elle, la liste mentirait
   par omission. Nommés d'après `/api/moi`, jamais une constante recopiée ; rien en
   mono-poste, où l'on est seul. */
function colAdminNote() {
  const g = (MOI.groupes_admin || []);
  if (!g.length) return "";
  return `<p class="col-note col-note-admin">Les administrateurs de l'instance
    (${g.map(esc).join(", ")}) lisent et écrivent <strong>toute</strong> collection, sans
    figurer dans aucune liste d'accès. Chacun de leurs actes est nommé au journal de
    provenance.</p>`;
}

/* Ce qui vaut TOUJOURS, sous la ligne de message, et d'un seul tenant : l'avertissement d'un
   acte, l'état de l'annuaire, le pouvoir des administrateurs. Trois traitements visuels en
   trois lignes ne disaient pas lequel comptait (relevé par Hugo le 2026-09-18) ; ils tiennent
   désormais dans UN bloc, distinct de ce qui vient du dernier geste. L'ordre ne change pas —
   ce qu'on est en train d'accorder d'abord, ce que l'application ne sait pas ensuite, ce
   qu'elle n'a pas à dire deux fois à la fin. */
function qeNotesHtml(c, etat) {
  const notes = [];
  if (DROITS && etat.acces) {
    // L'avertissement NOMME son acte. Rendu seul, il ne disait plus de quoi il parlait : on
    // lisait « Supprimer un album efface ses images » sans savoir ce qu'on accordait. Et la
    // case du cran qui l'accorde le cite en `aria-describedby` (cf. `qeDescriptions`).
    for (const av of BDDroits.avertissements(DROITS, etat.acces.map((a) => a.niveau))) {
      notes.push(`<p class="col-note qe-avertissement" id="${esc(qeIdAvertissement(c, av))}">`
        + `<strong>${av.actes.map((a) => esc(a.libelle)).join(", ")}</strong> — `
        + `${esc(av.texte)}</p>`);
    }
  }
  const an = etat.annuaire && etat.annuaire.annuaire;
  if (an && an.etat === "non_verifie") {
    // Le texte retenu par Hugo le 2026-09-17, sans « et ses comptes » : le propriétaire
    // ne se voit proposer aucun compte, il n'y a donc rien à ne pas pouvoir proposer.
    notes.push(`<p class="col-note qe-annuaire-note">L'annuaire ne répond pas : impossible de
      proposer ses groupes, ni de vérifier le nom que vous tapez. L'accès sera accordé tel
      quel, et marqué « non vérifié ».</p>`);
  } else if (an && an.etat === "sans_annuaire") {
    notes.push(`<p class="col-note">Aucun annuaire n'est configuré : un accès se déclare par
      un nom, que l'application ne peut pas vérifier. Un compte qui n'a pas encore ouvert
      l'application est signalé ; un nom de groupe ne peut pas l'être.</p>`);
  } else if (an && an.etat === "erreur") {
    notes.push(`<p class="col-note">La lecture de l'annuaire a échoué (${esc(an.motif)}) : la
      liste des groupes et les vérifications manquent. L'accès se déclare quand même par un
      nom.</p>`);
  }
  notes.push(colAdminNote());
  const corps = notes.filter(Boolean).join("");
  return corps ? `<div class="qe-notes-bloc">${corps}</div>` : "";
}

/* Redessine ce qui dépend des données, jamais la ligne de message : elle survit ainsi à un
   rechargement, refus compris — le 409 du dernier propriétaire reste à l'écran après que le
   tableau est revenu à ce que le serveur a gardé (COL-2). */
function qeRendre(sec) {
  if (!sec || !sec.isConnected) return;
  const etat = QE.get(Number(sec.dataset.qe));
  if (!etat) return;
  const garde = qeReleveAjout(sec);
  sec.querySelector(".qe-tableau").innerHTML = qeTableauHtml(etat.c, etat);
  sec.querySelector(".qe-ajout").innerHTML = qeAjoutHtml(etat.c, etat, garde);
  sec.querySelector(".qe-notes").innerHTML = qeNotesHtml(etat.c, etat);
}

function qeSection(id) {
  return document.querySelector(`#col-body .qe[data-qe="${id}"]`);
}

/* Le focus, rendu APRÈS le rechargement qui suit un geste — le contrôle actionné a été
   détruit par le rendu. Seulement à qui ne l'a pas repris entre-temps : l'aller-retour
   réseau laisse le temps de cliquer ailleurs. */
function qeRendreFocus(sec, cible) {
  if (!cible || !sec || !sec.isConnected) return;
  if (document.activeElement && document.activeElement !== document.body) return;
  const el = sec.querySelector(cible);
  if (el) el.focus();
}

async function qeLireAcces(id) {
  const etat = QE.get(id);
  try { etat.acces = await apiGet(`/api/collections/${id}/acces`); etat.erreur = null; }
  catch (e) { etat.erreur = e.message || "Les accès n'ont pas pu être lus."; }
}

async function qeLireAnnuaire(id) {
  const etat = QE.get(id);
  try { etat.annuaire = await apiGet(`/api/collections/${id}/annuaire`); }
  catch (e) {
    etat.annuaire = { annuaire: { etat: "erreur", motif: e.message || "échec" },
                      groupes: null, acces: [] };
  }
  return etat.annuaire;
}

/* À l'ouverture : le tableau dès que les accès sont là, les marques quand l'annuaire répond. */
async function qeOuvrir(sec, c) {
  const etat = qeEtat(c);
  etat.annuaire = null;
  await DROITS_PRETS;
  await qeLireAcces(c.id);
  qeRendre(qeSection(c.id));
  await qeLireAnnuaire(c.id);
  qeRendre(qeSection(c.id));
}

/* Après un geste : relire les accès dans les DEUX cas, et dessiner ce que le serveur a
   enregistré plutôt que ce qu'on a cliqué. */
async function qeApres(id, cible) {
  await qeLireAcces(id);
  const sec = qeSection(id);
  qeRendre(sec);
  qeRendreFocus(sec, cible);
}

function qeAcces(etat, el) {
  return (etat.acces || []).find((a) => a.genre === el.dataset.genre
    && a.principal === el.dataset.principal);
}

async function qeGesteCran(input) {
  const sec = input.closest(".qe");
  const id = Number(sec.dataset.qe), etat = QE.get(id);
  const a = qeAcces(etat, input);
  const niveau = a ? BDDroits.niveauApresGeste(DROITS, input.dataset.cran, input.checked) : null;
  if (!a || !niveau) { qeRendre(sec); return; }
  const cible = `.qe-case[data-cran="${CSS.escape(input.dataset.cran)}"]${qeSel(a)}`;
  // Le niveau COURANT est passé : ce que la liste rend d'une case d'office n'est pas une
  // décision, et l'affirmer en changeant de cran l'accorderait (cf. `corpsAcces`).
  await colTenter(sec.querySelector(".qe-msg"), () => apiSend("PUT",
    `/api/collections/${id}/acces`,
    BDDroits.corpsAcces(DROITS, { genre: a.genre, principal: a.principal }, niveau,
                        qeValeurs(a), a.niveau)));
  await qeApres(id, cible);
}

async function qeGesteHorsRang(input) {
  const sec = input.closest(".qe");
  const id = Number(sec.dataset.qe), etat = QE.get(id);
  const a = qeAcces(etat, input);
  if (!a) { qeRendre(sec); return; }
  const valeurs = { ...qeValeurs(a), [input.dataset.horsRangChamp]: input.checked };
  const cible = `.qe-case[data-hors-rang="${CSS.escape(input.dataset.horsRang)}"]${qeSel(a)}`;
  // Le niveau ne change pas ici, mais les AUTRES cases hors rang, elles, peuvent être
  // d'office : elles ne se stockent pas parce qu'on a coché celle d'à côté.
  await colTenter(sec.querySelector(".qe-msg"), () => apiSend("PUT",
    `/api/collections/${id}/acces`,
    BDDroits.corpsAcces(DROITS, { genre: a.genre, principal: a.principal }, a.niveau, valeurs,
                        a.niveau)));
  await qeApres(id, cible);
}

async function qeRetirer(bouton) {
  const sec = bouton.closest(".qe");
  const id = Number(sec.dataset.qe), etat = QE.get(id);
  const a = qeAcces(etat, bouton);
  if (!a) return;
  const ok = await colTenter(sec.querySelector(".qe-msg"), () => apiSend("DELETE",
    `/api/collections/${id}/acces/${encodeURIComponent(a.genre)}/${encodeURIComponent(a.principal)}`));
  // La ligne disparaît avec son bouton : le focus va au titre de la partie, et non nulle
  // part. Sur un refus, la ligne reste, et le focus retrouve son bouton.
  await qeApres(id, ok ? ".qe-titre" : `.qe-retirer${qeSel(a)}`);
}

async function qeFaireEntrer(sec) {
  const id = Number(sec.dataset.qe), etat = QE.get(id), c = etat.c;
  const ligne = sec.querySelector(".qe-msg");
  const choix = sec.querySelector(".qe-choix").value;
  let genre, principal;
  if (!choix) {
    colMsg(ligne, "Choisissez un groupe dans la liste, ou « Un compte, ou un groupe absent de "
                  + "la liste… ».", true);
    return;
  }
  if (choix === "autre") {
    principal = sec.querySelector(".qe-nom").value.trim();
    genre = sec.querySelector(".qe-genre").value;
    if (!principal) { colMsg(ligne, "Tapez le nom exact du compte ou du groupe.", true); return; }
    if (!genre) {
      colMsg(ligne, `Dites si « ${principal} » est un compte ou un groupe : un groupe accordé `
             + "comme compte n'ouvrirait rien à personne.", true);
      return;
    }
  } else {
    genre = "groupe";
    principal = choix.slice("groupe:".length);
  }
  const qui = genre === "groupe" ? "Le groupe" : "Le compte";
  // Le couple, et non le nom seul : un compte et un groupe de même nom sont deux accès.
  if ((etat.acces || []).some((a) => a.genre === genre && a.principal === principal)) {
    colMsg(ligne, `${qui} ${principal} entre déjà dans « ${c.nom} » : ses actes se règlent `
           + "dans le tableau.", true);
    return;
  }
  const premier = DROITS.echelle[0];
  const ok = await colTenter(ligne, () => apiSend("PUT", `/api/collections/${id}/acces`,
    BDDroits.corpsAcces(DROITS, { genre, principal }, premier, {})));
  if (!ok) return;
  // La ligne d'ajout repart à vide : le nom est entré, le garder inviterait à le renvoyer.
  const choixEl = sec.querySelector(".qe-choix");
  choixEl.value = "";
  delete choixEl.dataset.touche;
  sec.querySelector(".qe-nom").value = "";
  sec.querySelector(".qe-genre").value = "";
  await qeApres(id, ".qe-choix");
  const an = await qeLireAnnuaire(id);
  qeRendre(qeSection(id));
  const v = qeVerification(QE.get(id), genre, principal);
  const l = (qeSection(id) || sec).querySelector(".qe-msg");
  if (v === "inconnu") {
    colMsg(l, `${qui} ${principal} n'est pas dans l'annuaire : l'accès est accordé, en `
           + `${premier}, mais n'ouvrira rien tant que ce nom n'y existe pas.`, "alerte");
  } else if (v === "non_verifie" || (an && an.annuaire && an.annuaire.etat === "erreur")) {
    colMsg(l, `${qui} ${principal} entre dans « ${c.nom} », en ${premier} — non vérifié : `
           + "l'annuaire ne répondait pas.", "alerte");
  } else {
    colMsg(l, `${qui} ${principal} entre dans « ${c.nom} », en ${premier}. Cochez les autres `
           + "actes.");
  }
}

function qeSquelette(c) {
  return `<section class="qe" data-qe="${c.id}" aria-labelledby="qe-titre-${c.id}">
      <h3 class="qe-titre" id="qe-titre-${c.id}" tabindex="-1">Qui entre</h3>
      <div class="qe-tableau"><p class="col-note">Chargement…</p></div>
      <div class="qe-ajout"></div>
      <p class="col-msg muted small qe-msg" role="status" aria-live="polite"></p>
      <div class="qe-notes"></div>
    </section>`;
}

/* Les gestes de « Qui entre », délégués une fois sur la liste : les sections naissent et
   meurent à chaque rechargement, la liste reste. */
function qeInstaller() {
  const body = $("#col-body");
  body.addEventListener("change", (ev) => {
    const t = ev.target;
    if (!t.closest || !t.closest(".qe")) return;
    if (t.matches(".qe-case[data-cran]")) qeGesteCran(t);
    else if (t.matches(".qe-case[data-hors-rang]")) qeGesteHorsRang(t);
    else if (t.matches(".qe-choix")) {
      t.dataset.touche = "1";
      const libre = t.closest(".qe").querySelector(".qe-libre");
      libre.hidden = t.value !== "autre";
      if (!libre.hidden) libre.querySelector(".qe-nom").focus();
    }
  });
  body.addEventListener("click", (ev) => {
    const b = ev.target.closest && ev.target.closest("button");
    if (!b || !b.closest(".qe")) return;
    if (b.classList.contains("qe-retirer")) qeRetirer(b);
    else if (b.classList.contains("qe-faire-entrer")) qeFaireEntrer(b.closest(".qe"));
  });
  body.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && ev.target.matches && ev.target.matches(".qe-nom")) {
      ev.preventDefault();
      qeFaireEntrer(ev.target.closest(".qe"));
    }
  });
  QE_ETROIT.addEventListener("change", () =>
    document.querySelectorAll("#col-body .qe").forEach(qeRendre));
}


/* La pastille qui vivait dans l'Administration, déménagée avec les accès. « propriétaire »
   au DERNIER cran de l'échelle, lu dans la description et non écrit ici ; « administrateur »
   pour qui administre sans figurer dans les accès — un pouvoir qu'on déclare (AUTH-4), et
   jamais en mono-poste, où il n'y a qu'un rôle. Le libellé porte le sens (WCAG 1.4.1). */
function colBadge(c) {
  if (DROITS && c.mon_niveau
      && BDDroits.rang(DROITS, c.mon_niveau) === DROITS.echelle.length - 1) {
    return `<span class="col-niveau est-proprietaire">propriétaire</span>`;
  }
  if (c.administrable && !c.mon_niveau && (MOI.groupes_admin || []).length) {
    return `<span class="col-niveau">administrateur</span>`;
  }
  return "";
}

function colItem(c) {
  const d = document.createElement("details");
  d.className = "col-item";
  d.dataset.id = String(c.id);
  const emb = colEmbargo(c);
  d.innerHTML = `
    <summary>
      <span class="col-nom">${esc(c.nom)}</span>
      <span class="muted small col-nb">${c.nb_albums} album(s)</span>
      <span class="muted small col-regime">${esc(colRegime(c.statut_diffusion))}</span>
      ${emb ? `<span class="col-embargo ${emb[1]}" title="${esc(emb[2])}">${esc(emb[0])}</span>`
            : ""}
      ${colBadge(c)}
    </summary>
    <div class="col-detail"></div>`;
  // Remplie une fois par OUVERTURE. `chargerCollections` devance l'événement pour les
  // collections qu'il rouvre (il les remplit dans la même tâche, cf. là-bas) : `toggle`,
  // qui n'arrive qu'après, ne les redessine donc pas une seconde fois — ce qui effacerait
  // le message qu'il vient d'y reposer. Replier puis déplier redessine à neuf, sans lui.
  d.addEventListener("toggle", () => {
    if (!d.open) { delete d.dataset.remplie; return; }
    if (d.dataset.remplie) return;
    d.dataset.remplie = "1";
    colDetail(d, c);
  });
  return d;
}

function colDetail(d, c, msg) {
  const box = d.querySelector(".col-detail");
  if (!c.administrable) {
    // LIRE et MODIFIER sont deux droits distincts, qu'une seule garde confondait (AUTH-4).
    // La liste des accès est une donnée sur des PERSONNES : le participant ne la voit pas,
    // mais il apprend qu'un administrateur lit sans y figurer (déménagé de l'Administration).
    box.innerHTML = `<p class="col-note">Seul un propriétaire de la collection voit et règle
        qui y entre.</p>${colAdminNote()}
      ${colDescriptionLue(c)}${colReferentLu(c)}
      <p class="col-note">Seul un propriétaire de la collection modifie sa description, son
        régime de diffusion et son référent.</p>
      ${colExport(c)}`;
    colBrancherExport(box);
    return;
  }
  // « Qui entre » EN PREMIER : c'est le geste de chaque cours, la description est rare (ordre
  // de la maquette validée, AUTH-12). Sa ligne de message est la sienne, sous sa ligne
  // d'ajout ; celle du formulaire reste sous « Enregistrer ».
  box.innerHTML = qeSquelette(c) + colFormulaire(c) + colExport(c);
  colBrancherExport(box);
  qeOuvrir(box.querySelector(".qe"), c);
  // Reposé tel quel dans la collection redessinée. Qu'un lecteur d'écran l'ait ANNONCÉ
  // n'est pas établi : la ligne où il est né a été détruite un aller-retour plus tard, ce
  // que la ligne unique d'avant ne faisait pas. À mesurer sous NVDA avant d'en rien conclure
  // (décision du 2026-09-16 ; passe de QA « Les collections dans la Bibliothèque »).
  if (msg) colMsg(box.querySelector(".col-msg-formulaire"), msg.texte, msg.erreur);
  box.querySelector("[data-enregistrer]").onclick = () => colEnregistrer(box, c);
  box.querySelector("[data-supprimer]").onclick = () => colSupprimer(d, c);
}

/* N'envoie que ce qui a CHANGÉ, et pour deux raisons qui se vérifient. Un régime HORS
   vocabulaire — un reste d'avant la validation — ferait refuser TOUT l'enregistrement en
   422 s'il était renvoyé tel quel, alors qu'on voulait seulement corriger la licence. Et un
   champ qu'on n'a pas touché ne doit pas écraser ce qu'une autre personne vient d'y écrire.
   La date d'embargo illisible, elle, est protégée par son champ TEXTE (cf. `COL_GROUPES`) :
   c'est lui qui la réaffiche telle quelle. Un champ vidé part en `null` — c'est un geste,
   pas un oubli. */
async function colEnregistrer(box, c) {
  const ligne = box.querySelector(".col-msg-formulaire");
  const modifs = {};
  box.querySelectorAll("[data-champ]").forEach((el) => {
    const cle = el.dataset.champ;
    const avant = c[cle] == null ? "" : String(c[cle]).trim();
    const apres = el.value.trim();
    if (apres !== avant) modifs[cle] = apres === "" ? null : apres;
  });
  if (!Object.keys(modifs).length) { colMsg(ligne, "Rien n'a changé."); return; }
  if (await colTenter(ligne, () => apiSend("PATCH", `/api/collections/${c.id}`, modifs))) {
    colMsg(ligne, `« ${modifs.nom || c.nom} » enregistrée.`);
    chargerCollections(c.id);
  }
}

async function colSupprimer(d, c) {
  const ligne = d.querySelector(".col-msg-formulaire");
  if (!confirm(`Supprimer « ${c.nom} » ? Ses albums ne sont pas supprimés : ils sortent `
               + `simplement de cette collection.`)) return;
  if (await colTenter(ligne, () => apiSend("DELETE", `/api/collections/${c.id}`))) {
    colMsg(ligne, `« ${c.nom} » supprimée.`);
    // La collection disparaît, et sa ligne avec elle. La confirmation prend donc la PLACE
    // qu'elle occupait dans la liste — c'est là que l'œil est resté —, avant la suivante.
    const body = $("#col-body");
    const ids = [...body.querySelectorAll("details.col-item")].map((x) => x.dataset.id);
    const suivante = ids[ids.indexOf(String(c.id)) + 1];
    await chargerCollections();
    const avant = suivante && body.querySelector(`details.col-item[data-id="${suivante}"]`);
    body.insertBefore(colTrace(`« ${c.nom} » supprimée.`), avant || null);
  }
}

async function creerCollection() {
  const ligne = $("#col-creer-msg");
  const nom = $("#col-nom").value.trim();
  if (!nom) { colMsg(ligne, "Donnez un nom à la collection.", true); return; }
  let creee = null;
  if (await colTenter(ligne, async () => {
    creee = await apiSend("POST", "/api/collections", { nom });
  })) {
    $("#col-nom").value = "";
    // Le trajet que la frontière coupait en deux se fait désormais d'un tenant : la
    // collection créée s'ouvre sur « Qui entre » (AUTH-12, étape 3). Le dire au moment où
    // l'on vient de créer, c'est le seul moment où la question se pose.
    //
    // AUTH-12 — « vous en êtes propriétaire » n'était vrai que pour qui n'administre pas
    // l'instance. Un administrateur crée une collection SANS propriétaire (AUTH-3, décision
    // tenue le 2026-09-16), et le mono-poste aussi : le message lit la réponse du serveur
    // au lieu de le supposer.
    const moi = await identite();
    const proprietaire = !!moi.login && ((creee && creee.acces) || []).some((a) =>
      a.niveau === "proprietaire" && a.genre === "utilisateur" && a.principal === moi.login);
    const lieu = `« Qui entre », dans la collection ouverte ci-dessous`;
    ligne.classList.remove("erreur", "alerte");
    ligne.textContent = proprietaire
      ? `« ${nom} » créée — vous en êtes propriétaire. Pour y faire entrer quelqu'un : ${lieu}.`
      : moi.login
        ? `« ${nom} » créée. Vous l'administrez comme administrateur de l'instance, sans en `
          + `être propriétaire : désignez-lui un propriétaire dans ${lieu}, pour qu'elle ne `
          + `dépende pas de vous.`
        : `« ${nom} » créée. Qui peut y entrer se règle dans ${lieu}.`;
    chargerCollections(creee && creee.id);
  }
}

async function chargerCollections(ouvrir) {
  const body = $("#col-body");
  await DROITS_PRETS;
  MOI = await identite();
  let cols = [];
  try { cols = await apiGet("/api/collections"); }
  catch (e) {
    // Le message du dernier geste survit à l'échec de la relecture : un « enregistrée » qui
    // disparaîtrait derrière l'erreur ferait croire raté un enregistrement qui a eu lieu.
    const garde = [...body.querySelectorAll("details.col-item[open]")]
      .map(colMsgReleve).find(Boolean);
    body.innerHTML = `<p class="col-note">${esc(e.message)}</p>`;
    if (garde) body.appendChild(colTrace(garde.texte, garde.erreur));
    return;
  }
  // Les collections dépliées le restent, et gardent ce qu'elles disaient : recharger après
  // un enregistrement ne doit ni replier sous les yeux celle qu'on vient de modifier, ni
  // effacer le message qui le confirme.
  const ouvertes = new Map([...body.querySelectorAll("details.col-item[open]")]
    .map((d) => [d.dataset.id, colMsgReleve(d)]));
  if (ouvrir != null && !ouvertes.has(String(ouvrir))) ouvertes.set(String(ouvrir), null);
  body.innerHTML = "";
  COLS_RENDUES = true;
  if (!cols.length) {
    // « vous en serez propriétaire » ne vaut que pour qui n'écrit pas partout (AUTH-12).
    const moi = await Promise.resolve(window.BDMoi).catch(() => null);
    const total = !!(moi && moi.acces && moi.acces.total);
    body.innerHTML = `<p class="col-note">Aucune collection ouverte pour vous. Créez-en une
      ci-dessus${total ? "." : " : vous en serez propriétaire."}</p>`;
    return;
  }
  for (const c of cols) {
    const d = colItem(c);
    body.appendChild(d);
    const id = String(c.id);
    if (!ouvertes.has(id)) continue;
    // Rouverte ET remplie dans la même tâche, et non à l'événement `toggle`, qui arrive
    // après. Entre les deux, le navigateur pouvait mettre en page une liste de collections
    // toutes vides : la zone qui défile (`main`) raccourcissait d'autant, son défilement
    // revenait en haut, et la collection qu'on venait d'enregistrer réapparaissait d'autant
    // plus bas qu'on avait défilé (564 px dans le décor du test) — sa confirmation hors de
    // la fenêtre. Mesuré le 2026-09-16 par le test qui
    // lit la PLACE du message (COL-2) ; lire son seul texte ne pouvait pas le voir.
    d.open = true;
    d.dataset.remplie = "1";
    colDetail(d, c, ouvertes.get(id));
  }
}

/* Après un geste sur les ALBUMS — créer, supprimer, ranger —, seul le décompte bouge. On ne
   redessine donc pas la liste, ce qui replierait un formulaire en cours de saisie et
   perdrait ce qu'on y a tapé : on met à jour les nombres, et on ne reconstruit que si
   l'ensemble des collections a changé (la première création d'album en fait naître une). */
async function rafraichirCollections() {
  if (!COLS_RENDUES) return;
  let cols;
  try { cols = await apiGet("/api/collections"); } catch (e) { return; }
  const body = $("#col-body");
  const affichees = [...body.querySelectorAll("details.col-item")].map((d) => d.dataset.id);
  const ids = cols.map((c) => String(c.id));
  if (affichees.length !== ids.length || affichees.some((id, i) => id !== ids[i])) {
    chargerCollections();
    return;
  }
  for (const c of cols) {
    const n = body.querySelector(`details.col-item[data-id="${c.id}"] .col-nb`);
    if (n) n.textContent = `${c.nb_albums} album(s)`;
  }
}

/* AUTH-12, étape 3 — la Bibliothèque ADRESSABLE. `?collection=<id>` déplie cette collection
   et donne le focus au titre de « Qui entre » : c'est la cible de « Régler qui entre » dans
   l'Administration. `&groupe=<nom>` présélectionne ce groupe dans la ligne d'ajout
   (« Ouvrir une collection à ce groupe… »). Une collection qu'on ne lit pas n'ouvre rien, et
   une ligne le dit — sans dire si elle existe : c'est la règle du 404 (AUTH-2). */
async function ouvrirDepuisAdresse() {
  const p = new URLSearchParams(location.search);
  const brut = p.get("collection");
  const id = brut && /^[1-9]\d*$/.test(brut) ? Number(brut) : null;
  if (id !== null && p.get("groupe")) QE_PRESELECTION = { id, groupe: p.get("groupe") };
  await chargerCollections(id);
  if (id === null) return;
  const body = $("#col-body");
  const d = body.querySelector(`details.col-item[data-id="${id}"]`);
  if (!d) {
    QE_PRESELECTION = null;
    body.insertBefore(colTrace(`La collection demandée n'est pas dans la liste : elle ne vous `
      + `est pas ouverte, ou elle n'existe pas.`, true), body.firstChild);
    return;
  }
  const cible = d.querySelector(".qe-titre") || d.querySelector("summary");
  cible.scrollIntoView({ block: "start" });
  cible.focus();
}

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
  // Les Moteurs (SANTE-1) vivent dans `/administration` (UX-10). Ce que la collection EST
  // — la créer, la décrire, l'exporter — est revenu ICI avec COL-2 (2026-09-11), et QUI Y
  // ENTRE l'a rejoint avec AUTH-12 (2026-09-17). Rien n'est joignable des deux côtés : deux
  // portes vers la même pièce, l'une vieillit, et c'est celle qu'on ne regarde plus.
  $("#col-add").onclick = creerCollection;
  $("#col-nom").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); creerCollection(); }
  });
  $("#m-appartenance-add").onclick = rangerAlbum;
  // AUTH-1 — amorcé ici, et non à la seule ouverture des collections : `parQui()` a besoin
  // du login courant pour dire « par vous », et la table des planches se dessine bien avant
  // que quiconque ouvre ce panneau. Amorcer n'est pas attendre — c'est `openAlbum()` qui
  // attend, juste avant de dessiner.
  identite().then((m) => { MOI = m; });
  loadCorpus();   // stats d'en-tête (bande 2)
  loadAlbums();
  qeInstaller();
  loadEtatSharedocs().then(() => ouvrirDepuisAdresse());   // l'état AVANT le rendu (EXP-1)
  pollJobs();     // reprend l'affichage d'un éventuel job déjà en cours
}

setup();
