/* ===================================================================
   BéDéditeur — page Exploration (vanilla JS)
   • Distribution simple (lemme / POS / morph) d'un sous-corpus, OU
   • Comparaison de deux sous-corpus A / B (fréquences différentielles).
   Sur les valeurs EFFECTIVES (socle lot 2). Cliquer une valeur DESCEND aux preuves
   (Recherche pré-filtrée). État dans l'URL (partageable).
   =================================================================== */
"use strict";

// $, apiGet, esc : lib/common.js (chargé avant ce script).
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
function vue() { return $("#f-vue").value; }   // distribution | concordance | comparaison
function kwicStyle() { return $("#f-kwic-style").value; }

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

/* Vue Concordance (KWIC) : critères du sous-corpus A + un lemme/mot dédié → params backend
   (noms attendus par /api/analyse/concordance). Le POS est TOUJOURS inclus ici (pas
   d'exclusion « distribuer par POS » comme dans sideFilters). */
function concordanceParams() {
  const p = new URLSearchParams();
  const lemme = ($("#f-lemme").value || "").trim();
  if (lemme) p.set("lemme", lemme);
  const g = (k) => ($(`#f-${k}`).value || "").trim();
  for (const [ctl, key] of [["album", "album"], ["type", "type"], ["pos", "pos"],
       ["morph", "morph"], ["prov", "provenance"], ["tags", "tags"], ["personnage", "personnage"]]) {
    const v = g(ctl); if (v) p.set(key, v);
  }
  selectedAttributs("f").forEach((v) => p.append("attributs", v));
  if (tagScope() === "propre") p.set("tag_scope", "propre");
  return p;
}
// Le backend exige au moins un critère grammatical/sémantique : album/type/provenance seuls
// ne suffisent pas. On le vérifie AVANT l'appel pour afficher une invite plutôt qu'une erreur.
function concordanceHasCriterion(p) {
  return ["lemme", "pos", "morph", "tags", "personnage"].some((k) => p.get(k))
    || p.getAll("attributs").length > 0;
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

/* URL/état : vue + (champ|lemme) + filtres A (nus) + filtres B (préfixés b_). Partageable. */
function stateParams() {
  const v = vue();
  if (v === "concordance") {                     // params = noms backend (lemme, provenance…)
    const p = concordanceParams();
    p.set("vue", v);
    p.set("kwic", kwicStyle());
    if (RETOUR) p.set("retour", RETOUR);
    return p;
  }
  const p = new URLSearchParams();
  p.set("vue", v);
  p.set("champ", champ());
  const a = sideFilters("f");
  for (const [k, val] of Object.entries(a)) if (val) p.set(k, val);
  selectedAttributs("f").forEach((val) => p.append("attributs", val));
  if (v === "comparaison") {
    const b = sideFilters("b");
    for (const [k, val] of Object.entries(b)) if (val) p.set("b_" + k, val);
    selectedAttributs("b").forEach((val) => p.append("b_attributs", val));
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
  const v = vue();
  $("#dist").hidden = v !== "distribution";
  $("#comparaison").hidden = v !== "comparaison";
  $("#kwic").hidden = v !== "concordance";
  const gen = ++state.gen;
  $("#dist-info").textContent = "Calcul…";
  const done = (fn) => (res) => { if (gen === state.gen) fn(res); };
  const fail = (e) => { if (gen === state.gen) $("#dist-info").textContent = "Erreur : " + e.message; };

  if (v === "comparaison") {
    const p = new URLSearchParams();
    p.set("champ", champ());
    const a = sideFilters("f"), b = sideFilters("b");
    for (const [k, val] of Object.entries(a)) if (val) p.set("a_" + k, val);
    for (const [k, val] of Object.entries(b)) if (val) p.set("b_" + k, val);
    selectedAttributs("f").forEach((val) => p.append("a_attributs", val));
    selectedAttributs("b").forEach((val) => p.append("b_attributs", val));
    if (tagScope() === "propre") p.set("tag_scope", "propre");
    apiGet("/api/analyse/comparaison?" + p.toString()).then(done(renderComparaison)).catch(fail);
  } else if (v === "concordance") {
    const p = concordanceParams();
    if (!concordanceHasCriterion(p)) {           // sinon le backend renverrait 422 → invite claire
      $("#dist-info").textContent = "";
      $("#kwic").className = "kwic";              // retire une grille « aligné » résiduelle d'un rendu précédent
      $("#kwic").innerHTML =
        '<p class="muted small">Précisez un lemme / mot, ou un filtre POS, morpho, tag, locuteur ou attribut.</p>';
      return;
    }
    p.set("limit", "200");
    apiGet("/api/analyse/concordance?" + p.toString()).then(done(renderKwic)).catch(fail);
  } else {
    const p = new URLSearchParams();
    p.set("champ", champ());
    for (const [k, val] of Object.entries(sideFilters("f"))) if (val) p.set(k, val);
    selectedAttributs("f").forEach((val) => p.append("attributs", val));
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

/* ---------------- Rendu : concordance (KWIC) ---------------- */
/* Localise le mot-pivot (forme du token) dans le texte de la bulle, insensible à la casse
   (le lettrage est en capitales, la forme parfois minusculée). 1re occurrence ; null si
   introuvable → la ligne retombe sur le texte entier. */
function splitPivot(texte, pivot) {
  if (!texte || !pivot) return null;
  const i = texte.toLowerCase().indexOf(pivot.toLowerCase());
  if (i < 0) return null;
  return { left: texte.slice(0, i), key: texte.slice(i, i + pivot.length),
           right: texte.slice(i + pivot.length) };
}
// Deep-link Visionneuse (voir la case réelle) + `retour` pour revenir à l'Exploration.
function kwicViewerHref(r) {
  const p = new URLSearchParams();
  if (r.album_id) p.set("album", r.album_id);
  if (r.planche_id) p.set("planche", r.planche_id);
  if (r.region_id) p.set("region", r.region_id);
  p.set("retour", location.pathname + location.search);
  return "/?" + p.toString();
}
function kwicMeta(r) {
  const cit = (r.citation && r.citation.texte) ? r.citation.texte
            : (r.planche_numero != null ? "pl." + r.planche_numero : "—");
  return esc(cit + (r.locuteur ? " · " + r.locuteur : "") + (r.pos ? " · " + r.pos : ""));
}
function kwicRowAligne(r) {
  const parts = splitPivot(r.ocr_texte, r.texte);
  const L = parts ? esc(parts.left) : esc(r.ocr_texte || "");
  const K = parts ? esc(parts.key) : "";
  const R = parts ? esc(parts.right) : "";
  return `<a class="kwic-row" href="${esc(kwicViewerHref(r))}" title="Voir la case">` +
    `<span class="kw-left">${L}</span><span class="kw-key">${K}</span>` +
    `<span class="kw-right">${R}</span><span class="kw-meta">${kwicMeta(r)}</span></a>`;
}
function kwicRowListe(r) {
  const parts = splitPivot(r.ocr_texte, r.texte);
  const texte = parts
    ? `${esc(parts.left)}<b class="kw-hit">${esc(parts.key)}</b>${esc(parts.right)}`
    : esc(r.ocr_texte || "");
  return `<a class="kwic-item" href="${esc(kwicViewerHref(r))}" title="Voir la case">` +
    `<span class="kwic-meta">${kwicMeta(r)}</span>` +
    `<span class="kwic-text">« ${texte} »</span></a>`;
}
function renderKwic(res) {
  const box = $("#kwic"), rows = res.results || [];
  const lemme = ($("#f-lemme").value || "").trim();
  $("#dist-info").innerHTML =
    `${res.count} occurrence(s)` + (lemme ? ` de <b>${esc(lemme)}</b>` : "") +
    (res.count >= 200 ? " (limité à 200)" : "") +
    " — cliquer une ligne pour voir la case";
  if (!rows.length) {
    box.className = "kwic";
    box.innerHTML = '<p class="muted small">Aucune occurrence.</p>';
    return;
  }
  const aligne = kwicStyle() === "aligne";
  box.className = "kwic" + (aligne ? " kwic-aligned" : " kwic-list");
  box.innerHTML = rows.map((r) => aligne ? kwicRowAligne(r) : kwicRowListe(r)).join("");
}

/* ---------------- Contrôles / démarrage ---------------- */
function syncControls() {
  const v = vue();
  $("#sub-b").hidden = v !== "comparaison";
  document.querySelectorAll(".sub-title").forEach((el) => { el.hidden = v !== "comparaison"; });
  $("#wrap-champ").hidden = v === "concordance";     // « distribuer par » hors concordance
  $("#wrap-lemme").hidden = v !== "concordance";     // champ lemme/mot en concordance
  $("#wrap-kwic").hidden = v !== "concordance";      // bascule aligné/liste en concordance
  const byPos = v !== "concordance" && champ() === "pos";
  $("#f-pos").disabled = byPos;     // filtre POS redondant si on distribue par POS
  $("#b-pos").disabled = byPos;
}

function restoreFromUrl() {
  const p = new URLSearchParams(INITIAL_QS);
  // `vue` (nouveau) ; rétro-compat : ancien `compare=1` → comparaison.
  $("#f-vue").value = p.get("vue") || (p.get("compare") === "1" ? "comparaison" : "distribution");
  $("#f-champ").value = p.get("champ") || "lemme";
  $("#f-lemme").value = p.get("lemme") || "";
  $("#f-kwic-style").value = p.get("kwic") || "aligne";
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

/* ---------------- Lexique situé (A4) : documenter le vocabulaire ----------------
   Modale d'édition de la couche définitionnelle SKOS (definition / note de portée /
   état provisoire→défini / portée d'appartenance) sur dimensions, valeurs et tags.
   Read model : GET /api/lexique ; écriture : PATCH .../lexique (partielle). */
let LEX_COLLECTIONS = [];   // {id, nom, …} — menu « portée »
let LEX_DOMAINES = [];      // {id, nom, …} — menu « domaine » des dimensions (piste B)

async function openLexique() { $("#lexique-modal").hidden = false; await loadLexique(); }
function closeLexique() { $("#lexique-modal").hidden = true; }

async function loadLexique() {
  const body = $("#lex-body");
  body.textContent = "Chargement…";
  try {
    const [lex, cols] = await Promise.all([apiGet("/api/lexique"), apiGet("/api/collections")]);
    LEX_COLLECTIONS = cols;
    LEX_DOMAINES = lex.domaines || [];
    renderLexique(lex);
  } catch (e) { body.textContent = "Impossible de charger le lexique."; }
}

function lexResume(r) {
  const pct = r.pct_defini == null ? "—" : Math.round(r.pct_defini * 100) + " %";
  return `${r.definis}/${r.total} terme(s) défini(s) — ${pct}`;
}

function porteeOptions(sel) {
  return [`<option value="">Global</option>`].concat(
    LEX_COLLECTIONS.map((c) =>
      `<option value="${c.id}"${String(c.id) === String(sel) ? " selected" : ""}>${esc(c.nom)}</option>`)
  ).join("");
}

function domaineOptions(sel) {
  return [`<option value="">Hors domaine</option>`].concat(
    LEX_DOMAINES.map((d) =>
      `<option value="${d.id}"${String(d.id) === String(sel) ? " selected" : ""}>${esc(d.nom)}</option>`)
  ).join("");
}

/* Éditeur d'un terme (domaine | dimension | valeur | tag). `defi` = définition courante (la
   `description` pour un tag). Câble un PATCH par champ modifié. Une dimension porte en plus un
   sélecteur de DOMAINE (piste B) → PATCH .../domaine (réorganise, re-rend la modale). */
function termEditor(kind, term, defi) {
  const url = kind === "tag" ? `/api/tags/${term.id}/lexique`
            : kind === "valeur" ? `/api/attributs/valeurs/${term.id}/lexique`
            : kind === "domaine" ? `/api/domaines/${term.id}/lexique`
            : `/api/attributs/dimensions/${term.id}/lexique`;
  const nom = kind === "tag" ? term.label : (term.nom || term.valeur);
  const sub = kind === "dimension" ? (CIBLE_LBL[term.cible] || term.cible)
            : kind === "domaine" ? `${term.nb_dimensions} dimension(s)`
            : kind === "valeur" ? `${term.nb_usages} usage(s)` : `${term.frequence} pose(s)`;
  const defini = term.etat === "defini";
  const domaineField = kind === "dimension"
    ? `<label>Domaine <select data-f="domaine_id">${domaineOptions(term.domaine_id)}</select></label>`
    : "";
  const d = document.createElement("details");
  d.className = "lex-term" + (kind === "domaine" ? " lex-domaine" : "");
  d.innerHTML = `
    <summary>
      <span class="lex-name">${esc(nom)}</span>
      <span class="lex-sub">${esc(sub)}</span>
      <span class="lex-badge${defini ? " defini" : ""}" data-role="badge">${defini ? "défini" : "provisoire"}</span>
    </summary>
    <div class="lex-fields">
      <label>Définition
        <textarea rows="2" data-f="definition" placeholder="sens du terme">${esc(defi || "")}</textarea>
      </label>
      <label>Note de portée <span class="muted small">(cadre d'emploi dans ce corpus)</span>
        <textarea rows="2" data-f="note_portee" placeholder="ex. ici, « rural » = hors grande ville">${esc(term.note_portee || "")}</textarea>
      </label>
      <div class="lex-row">
        <label class="lex-check"><input type="checkbox" data-f="etat"${defini ? " checked" : ""}> Défini</label>
        <label>Portée <select data-f="collection_id">${porteeOptions(term.collection_id)}</select></label>
        ${domaineField}
      </div>
    </div>`;
  const badge = d.querySelector('[data-role="badge"]');
  const domSel = d.querySelector('[data-f="domaine_id"]');   // dimensions seulement
  if (domSel) domSel.addEventListener("change", async (e) => {
    try {
      await apiSend("PATCH", `/api/attributs/dimensions/${term.id}/domaine`,
                    { domaine_id: e.target.value ? Number(e.target.value) : null });
      toast("Domaine mis à jour"); loadLexique();          // regroupement changé → re-render
    } catch (err) { toast("Échec : " + err.message, "err"); }
  });
  // `save` renvoie true/false : les MAJ optimistes (badge, % défini) ne s'appliquent QUE
  // sur succès — sinon l'UI divergerait de la base (ex. 409 base occupée, 500).
  const save = async (patch) => {
    try { await apiSend("PATCH", url, patch); toast("Enregistré"); return true; }
    catch (e) { toast("Échec : " + e.message, "err"); return false; }
  };
  d.querySelectorAll("textarea[data-f]").forEach((ta) =>
    ta.addEventListener("change", () => save({ [ta.dataset.f]: ta.value })));
  d.querySelector('[data-f="etat"]').addEventListener("change", async (e) => {
    if (!await save({ etat: e.target.checked ? "defini" : "provisoire" })) {
      e.target.checked = !e.target.checked;   // échec → reverter la case (pas de change re-déclenché)
      return;
    }
    badge.textContent = e.target.checked ? "défini" : "provisoire";
    badge.classList.toggle("defini", e.target.checked);
    refreshLexResume();                       // le % défini change (succès uniquement)
  });
  d.querySelector('[data-f="collection_id"]').addEventListener("change", (e) =>
    save({ collection_id: e.target.value ? Number(e.target.value) : null }));
  return d;
}

function renderLexique(lex) {
  const body = $("#lex-body");
  body.textContent = "";
  $("#lex-resume").textContent = lexResume(lex.resume);
  $("#lex-import-portee").innerHTML = porteeOptions("");   // menu « portée » de l'amorçage CSV

  // --- Domaines (piste B) + attributs facettés regroupés par domaine -------- #
  const grp = document.createElement("div");
  grp.className = "lex-group";
  grp.innerHTML = `<h4>Domaines &amp; attributs facettés</h4>
    <div class="lex-add">
      <input id="lex-dom-nom" placeholder="Nouveau domaine (ex. émotions, représentation)"
             autocomplete="off" aria-label="Nom du nouveau domaine">
      <button id="lex-dom-add" class="ghost small" type="button">+ Domaine</button>
    </div>`;
  body.appendChild(grp);

  const parDomaine = new Map();               // domaine_id (ou null) → [dimensions]
  for (const dim of lex.dimensions) {
    if (!parDomaine.has(dim.domaine_id)) parDomaine.set(dim.domaine_id, []);
    parDomaine.get(dim.domaine_id).push(dim);
  }
  const renderDims = (dims) => {
    for (const dim of dims || []) {
      grp.appendChild(termEditor("dimension", dim, dim.definition));
      for (const val of dim.valeurs) {
        const ve = termEditor("valeur", val, val.definition);
        ve.classList.add("lex-nested");
        grp.appendChild(ve);
      }
    }
  };
  for (const dom of lex.domaines) {           // un domaine documentable + ses dimensions
    grp.appendChild(termEditor("domaine", dom, dom.definition));
    renderDims(parDomaine.get(dom.id));
  }
  const horsDomaine = parDomaine.get(null) || parDomaine.get(undefined);
  if (horsDomaine && horsDomaine.length) {
    grp.insertAdjacentHTML("beforeend", `<p class="lex-subhead muted small">Hors domaine</p>`);
    renderDims(horsDomaine);
  }
  if (!lex.dimensions.length && !lex.domaines.length)
    grp.insertAdjacentHTML("beforeend", `<p class="muted small">Aucun domaine ni dimension.</p>`);
  $("#lex-dom-add").onclick = async () => {
    const nom = $("#lex-dom-nom").value.trim();
    if (!nom) return;
    try { await apiSend("POST", "/api/domaines", { nom }); loadLexique(); }
    catch (e) { toast("Domaine : " + e.message, "err"); }
  };
  $("#lex-dom-nom").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); $("#lex-dom-add").click(); }
  });

  // --- Étiquettes (tags) ---------------------------------------------------- #
  const tg = document.createElement("div");
  tg.className = "lex-group";
  tg.innerHTML = "<h4>Étiquettes (tags)</h4>";
  if (!lex.tags.length)
    tg.insertAdjacentHTML("beforeend", `<p class="muted small">Aucun tag.</p>`);
  for (const tag of lex.tags) tg.appendChild(termEditor("tag", tag, tag.description));
  body.appendChild(tg);
}

async function refreshLexResume() {
  try { $("#lex-resume").textContent = lexResume((await apiGet("/api/lexique")).resume); }
  catch (e) { /* non bloquant */ }
}

/* Amorçage EN LOT du vocabulaire depuis un tableur CSV (bouton « Importer »). Envoi
   multipart vers POST /api/lexique/importer (même cœur que l'outil headless) ; le bilan
   passe en toasts et la modale se recharge. Cf. docs/import-vocabulaire.md. */
async function importerTableur(e) {
  const input = e.target;
  const fichier = input.files && input.files[0];
  if (!fichier) return;
  const fd = new FormData();
  fd.append("file", fichier);
  const cid = $("#lex-import-portee").value;
  if (cid) fd.append("collection_id", cid);
  try {
    const r = await fetch("/api/lexique/importer", { method: "POST", body: fd });
    const out = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(out.detail || r.statusText);
    const s = out.resume;
    toast(`Import : ${s.domaines.cree} domaine(s), ${s.dimensions.cree} dimension(s), `
          + `${s.valeurs.cree} valeur(s) créé(s)`);
    (out.anomalies || []).concat(out.avertissements || []).forEach((a) => toast(a, "err"));
    await loadLexique();
  } catch (err) {
    toast("Import échoué : " + err.message, "err");
  } finally {
    input.value = "";                 // réautorise le réimport du même fichier
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
  $("#f-lemme").addEventListener("input", deb);   // concordance : frappe du lemme/mot
  $("#f-champ").onchange = () => { syncControls(); run(); };
  $("#f-vue").onchange = () => { syncControls(); run(); };
  $("#f-kwic-style").onchange = run;               // bascule aligné/liste (re-rend)
  // Les puces d'attribut câblent leur propre clic (cf. renderAttrChips) — absentes d'ici.
  ["#f-album", "#f-type", "#f-pos", "#f-prov", "#f-tags", "#f-tagscope", "#f-personnage",
   "#b-album", "#b-type", "#b-pos", "#b-prov", "#b-tags", "#b-personnage"]
    .forEach((s) => { $(s).onchange = run; });
  // Lexique situé (A4) — modale accessible (piège à focus, Échap, retour du focus).
  $("#btn-lexique").onclick = openLexique;
  $("#lex-close").onclick = closeLexique;
  $("#lex-import").onclick = () => $("#lex-import-file").click();   // amorçage CSV
  $("#lex-import-file").addEventListener("change", importerTableur);
  $("#lexique-modal").addEventListener("mousedown", (e) => {
    if (e.target.id === "lexique-modal") closeLexique();
  });
  if (window.BDDialog)
    BDDialog.register($("#lexique-modal"),
      { box: ".modal-box", labelledby: "lexique-title", onClose: closeLexique });
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
