/* ===================================================================
   BéDéditeur — page Exploration (vanilla JS)
   • Distribution simple (lemme / POS / morph) d'un sous-corpus, OU
   • Comparaison de deux sous-corpus A / B (fréquences différentielles).
   Sur les valeurs EFFECTIVES (socle lot 2). Cliquer une valeur DESCEND aux preuves
   (Recherche pré-filtrée). État dans l'URL (partageable).
   =================================================================== */
"use strict";

// $, apiGet, esc : lib/common.js (chargé avant ce script).
// INFRA-5 — l'état de départ : celui de l'adresse s'il y en a un, sinon — on arrive par
// le menu — la dernière vue de cet onglet, gardée en stockage de SESSION. L'adresse
// l'emporte toujours (un deep-link de concordance reste prévisible) ; cf. static/lib/nav.js.
const STOCKAGE = Nav.stockageDeSession(window);
const INITIAL_QS = Nav.etatDeDepart(location.search, STOCKAGE, "exploration").qs;
// `retour` validé : page interne seulement (cf. static/lib/nav.js → anti open-redirect/XSS).
const RETOUR = Nav.safeRetour(new URLSearchParams(INITIAL_QS).get("retour"));   // d'où l'on vient (si inbound)
const UPOS = ["ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN", "NUM",
              "PART", "PRON", "PROPN", "PUNCT", "SCONJ", "SYM", "VERB", "X"];
// `corpus` : GET /api/corpus, ou null — la cause d'un écran vide (UX-6, `direVide`).
// `anciens` (ANN-7, I7) : les paramètres d'hier (`tags`, `tag_scope`, `attributs`…) d'un
// lien enregistré, envoyés UNE fois au serveur, qui les refuse par un 422 qui le dit. Les
// taire rendrait le corpus entier sous un lien qui a l'air filtré.
const state = { timer: null, gen: 0, corpus: Promise.resolve(null), anciens: [] };
const PARAMETRES_D_HIER = ["tags", "b_tags", "tag_scope", "attributs", "b_attributs"];

async function loadCorpus() {
  try {
    const c = await apiGet("/api/corpus");
    $("#corpus-stats").innerHTML = Resultats.chiffresCorpus(c);   // accordés (UX-6)
    return c;
  } catch (e) { return null; /* non bloquant */ }
}

/* UX-6 — un écran vide dit sa VRAIE cause. « Aucune donnée (relancer l'indexation NLP ?) »
   s'affichait aussi quand aucun corpus n'est ouvert — l'arrivant qui n'a que son bac à
   sable, exclu de l'Exploration — et se lisait comme une panne. Le corpus que l'Exploration
   lit (`GET /api/corpus`, même portée que ses requêtes) dit s'il n'y a aucun album ou aucun
   texte ; sinon, des critères posés expliquent le vide ; sinon seulement, l'index. `ecrire`
   reçoit le message, et n'est appelé que si aucun calcul n'est reparti depuis. */
function direVide(ecrire, criteres, defaut) {
  const gen = state.gen;
  state.corpus.then((c) => {
    if (gen !== state.gen) return;
    ecrire(Resultats.causeVide(c, { texte: true })
      || (criteres ? "Aucune donnée pour ces critères." : defaut));
  });
}
const NLP_A_RELANCER = "Aucune donnée (relancer l'indexation NLP ?).";
// Des critères posés sur le sous-corpus A.
function criteresA() {
  return [...filtresA().keys()].length > 0;
}

async function loadAlbums() {
  try {
    // COL-3, tranche 2 — une copie gardée au fonds n'est plus un album de travail : seule
    // une portée totale la reçoit, et elle se règle dans l'Administration. Un filtre
    // d'écran, pas une garde.
    const albums = (await apiGet("/api/albums")).filter((a) => !a.au_fonds);
    for (const id of ["#f-album", "#b-album"]) {
      const sel = $(id);
      for (const a of albums) {
        const o = document.createElement("option");
        o.value = String(a.id);
        o.textContent = `${serieTome(a) ? serieTome(a) + " · " : ""}${a.titre}`;
        sel.appendChild(o);
      }
    }
  } catch (e) { /* ignore */ }
}

/* ---------------- Paramètres ---------------- */
function champ() { return $("#f-champ").value; }
function vue() { return $("#f-vue").value; }   // distribution | concordance | comparaison
function kwicStyle() { return $("#f-kwic-style").value; }
function metrique() { return $("#f-metrique").value; }   // comparaison : diff | ll (ANA-4)

/* Filtres d'un côté (préfixe "f" = A, "b" = B) → {album,type,pos,morph,provenance}. */
function sideFilters(pre) {
  const g = (k) => ($(`#${pre}-${k}`).value || "").trim();
  const f = { album: g("album"), type: g("type"), morph: g("morph"),
              provenance: g("prov"), personnage: g("personnage") };
  if (champ() !== "pos") f.pos = g("pos");   // filtre POS redondant si on distribue par POS
  return f;
}

/* Sous-corpus A → params backend (noms attendus par concordance / croisement). Le POS est
   TOUJOURS inclus (pas d'exclusion « distribuer par POS » comme dans sideFilters). Partagé
   par la concordance (KWIC) et le croisement 2D. */
function filtresA() {
  const p = new URLSearchParams();
  const g = (k) => ($(`#f-${k}`).value || "").trim();
  for (const [ctl, key] of [["album", "album"], ["type", "type"], ["pos", "pos"],
       ["morph", "morph"], ["prov", "provenance"], ["personnage", "personnage"]]) {
    const v = g(ctl); if (v) p.set(key, v);
  }
  return p;
}
// Le lemme saisi, ou "" s'il ne dit rien. Un joker seul (« * ») n'est pas un préfixe : le
// laisser partir rendrait un 422 là où l'invite doit parler, et armerait un export voué à
// l'échec (ANA-6).
function lemmeSaisi() {
  const v = ($("#f-lemme").value || "").trim();
  return v.replace(/\*+$/, "") ? v : "";
}
// Concordance : filtres A + le lemme/mot dédié.
function concordanceParams() {
  const p = filtresA();
  const lemme = lemmeSaisi();
  if (lemme) p.set("lemme", lemme);
  return p;
}
// Croisement 2D : filtres A + les deux axes.
function croisementParams() {
  const p = filtresA();
  p.set("axe_x", $("#f-axe-x").value);
  p.set("axe_y", $("#f-axe-y").value);
  return p;
}
// Facettes croisables. Les axes « tag » et « dimension d'attribut » sont partis avec le
// basculement d'ANN-7 ; la tranche 4 croisera les relevés.
const AXES_STATIQUES = [
  ["pos", "catégorie (POS)"], ["morph", "morphologie"], ["type", "type de région"],
  ["provenance", "provenance"], ["locuteur", "locuteur"],
];
function axeOptions(sel) {
  return AXES_STATIQUES.map(([val, lbl]) =>
    `<option value="${esc(val)}"${val === sel ? " selected" : ""}>${esc(lbl)}</option>`).join("");
}
function populateAxes() {
  $("#f-axe-x").innerHTML = axeOptions($("#f-axe-x").value || "pos");
  $("#f-axe-y").innerHTML = axeOptions($("#f-axe-y").value || "type");
}
// Le backend exige au moins un critère grammatical/sémantique : album/type/provenance seuls
// ne suffisent pas. On le vérifie AVANT l'appel pour afficher une invite plutôt qu'une erreur.
function concordanceHasCriterion(p) {
  return ["lemme", "pos", "morph", "personnage"].some((k) => p.get(k));
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
  if (v === "croisement") {                       // filtres A + axe_x/axe_y
    const p = croisementParams();
    p.set("vue", v);
    if (RETOUR) p.set("retour", RETOUR);
    return p;
  }
  const p = new URLSearchParams();
  p.set("vue", v);
  p.set("champ", champ());
  const a = sideFilters("f");
  for (const [k, val] of Object.entries(a)) if (val) p.set(k, val);
  if (v === "comparaison") {
    const b = sideFilters("b");
    for (const [k, val] of Object.entries(b)) if (val) p.set("b_" + k, val);
    if (metrique() !== "diff") p.set("metrique", metrique());   // défaut omis de l'URL
  }
  if (RETOUR) p.set("retour", RETOUR);   // préservé : le ← Retour survit aux changements de filtre
  return p;
}

/* Descente aux preuves : Recherche pré-filtrée sur la valeur + les filtres du côté. */
function drillUrl(valeur, filtres) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(filtres)) if (v) p.set(k, v);   // locuteur compris
  p.set(champ(), valeur);
  p.set("retour", location.pathname + location.search);   // pour revenir à l'Exploration
  return "/recherche?" + p.toString();
}

/* ANA-7 — l'export rejoue les paramètres qui ont produit l'AFFICHAGE.

   Ils sont retenus ici, à l'endroit exact où la vue les construit, plutôt que rebâtis au
   moment du clic. Les rebâtir, ce serait écrire une seconde fois la même chose : les deux
   copies finiraient par diverger sur un filtre, et personne ne le verrait — l'écran et le
   fichier resteraient tous les deux plausibles. C'est la même raison qui fait partager un
   cœur aux routes JSON et CSV côté serveur.

   `limit` n'y entre PAS : il borne l'aperçu, et l'export a le sien, plus haut. */
function armerExport(vue, p) {
  state.exportAnalyse = { vue, params: p.toString() };
  $("#btn-export-analyse").disabled = false;
  $("#croise-forme").hidden = vue !== "croisement";
}

function desarmerExport() {
  state.exportAnalyse = null;
  $("#btn-export-analyse").disabled = true;
  $("#croise-forme").hidden = true;
}

function exporterAnalyse() {
  const e = state.exportAnalyse;
  if (!e) return;
  const q = new URLSearchParams(e.params);
  if (e.vue === "croisement") q.set("forme", $("#croise-forme").value);
  window.location = `/api/analyse/${e.vue}.csv?` + q.toString();
}

/* ---------------- Exécution ---------------- */
function run() {
  // ANN-7, I7 — les paramètres d'hier partent avec ce calcul-ci, et lui seul : l'erreur du
  // serveur les dit ; le geste suivant s'en passe.
  const anciens = state.anciens;
  state.anciens = [];
  const avecAnciens = (p) => { anciens.forEach(([k, val]) => p.append(k, val)); return p; };
  const etat = avecAnciens(stateParams()).toString();
  history.replaceState(null, "", "?" + etat);
  Nav.memoriser(STOCKAGE, "exploration", etat);   // INFRA-5
  const v = vue();
  $("#dist").hidden = v !== "distribution";
  $("#comparaison").hidden = v !== "comparaison";
  $("#kwic").hidden = v !== "concordance";
  $("#croise").hidden = v !== "croisement";
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
    if (metrique() !== "diff") p.set("metrique", metrique());   // l'export trie comme l'écran
    avecAnciens(p);
    armerExport("comparaison", p);
    apiGet("/api/analyse/comparaison?" + p.toString()).then(done(renderComparaison)).catch(fail);
  } else if (v === "concordance") {
    const p = avecAnciens(concordanceParams());
    if (!anciens.length && !concordanceHasCriterion(p)) {   // sinon 422 → invite claire
      $("#dist-info").textContent = "";
      $("#kwic").className = "kwic";              // retire une grille « aligné » résiduelle d'un rendu précédent
      $("#kwic").innerHTML =
        '<p class="muted small">Précisez un lemme / mot, ou un filtre POS, morpho ou locuteur.</p>';
      desarmerExport();          // rien n'a été demandé : il n'y a rien à emporter
      return;
    }
    armerExport("concordance", p);
    p.set("limit", String(Resultats.LIMITE + 1));
    apiGet("/api/analyse/concordance?" + p.toString()).then(done(renderKwic)).catch(fail);
  } else if (v === "croisement") {
    const p = avecAnciens(croisementParams());
    armerExport("croisement", p);
    p.set("limit", String(CROISE_LIMIT));
    apiGet("/api/analyse/croisement?" + p.toString()).then(done(renderCroise)).catch(fail);
  } else {
    const p = new URLSearchParams();
    p.set("champ", champ());
    for (const [k, val] of Object.entries(sideFilters("f"))) if (val) p.set(k, val);
    avecAnciens(p);
    armerExport("frequences", p);
    p.set("limit", String(Resultats.LIMITE + 1));
    apiGet("/api/analyse/frequences?" + p.toString()).then(done(renderDist)).catch(fail);
  }
}

function valeurDe(r, ch) { return ch === "lemme" ? r.lemme : ch === "pos" ? r.pos : r.morph; }

/* ---------------- Rendu : distribution simple ---------------- */
function renderDist(res) {
  const ch = res.champ, box = $("#dist");
  // Même règle qu'à la Recherche, et le même piège : on demande un de plus qu'on
  // n'affiche, sinon « limité » se déclenche à EXACTEMENT la limite, là où il n'y a
  // pourtant rien de caché (C1). Le témoin est retiré avant tout calcul — inclus
  // dans `total`, il gonflerait un décompte d'occurrences affiché comme exact.
  const compte = Resultats.etat((res.results || []).length);
  const rows = (res.results || []).slice(0, compte.n);
  box.innerHTML = "";
  if (!rows.length) {
    $("#dist-info").textContent = "";
    direVide((m) => { $("#dist-info").textContent = m; },
             Object.values(sideFilters("f")).some(Boolean),
             NLP_A_RELANCER);
    return;
  }
  const total = rows.reduce((s, r) => s + r.freq, 0);
  const max = Math.max(...rows.map((r) => r.freq));
  $("#dist-info").innerHTML =
    `${Resultats.nombre(rows.length, "valeur")} de <b>${esc(ch)}</b> · `
    + Resultats.nombre(total, "occurrence") +
    (compte.tronque ? ` (limité aux ${Resultats.LIMITE} plus fréquentes)` : "") +
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
/* `cle` = la mesure qui a classé la liste (`diff` ou `ll`) : la barre en montre la force,
   sans quoi un classement par keyness s'afficherait avec les longueurs de l'autre mesure. */
function compColumn(items, side, filtres, cle) {
  if (!items.length) return '<div class="muted small">—</div>';
  const max = Math.max(...items.map((x) => Math.abs(x[cle]))) || 1;
  return items.map((x) => {
    const v = x.valeur, label = v === "" ? "∅ (aucun trait)" : v;
    const w = (100 * Math.abs(x[cle]) / max).toFixed(1);
    const g2 = cle === "ll" ? ` · G² ${Math.abs(x.ll)}` : "";
    const inner =
      `<span class="dist-label">${esc(label)}</span>` +
      `<span class="dist-bar"><i class="bar-${side}" style="width:${w}%"></i></span>` +
      `<span class="dist-freq" title="A:${x.freq_a} · B:${x.freq_b}${g2}">${x.freq_a}/${x.freq_b}</span>`;
    return v === ""
      ? `<div class="dist-row">${inner}</div>`
      : `<a class="dist-row" href="${esc(drillUrl(v, filtres))}" title="Voir les emplois en contexte">${inner}</a>`;
  }).join("");
}

function renderComparaison(res) {
  const box = $("#comparaison");
  const cle = res.metrique === "ll" ? "ll" : "diff";
  const mesure = cle === "ll"
    ? "keyness : log-vraisemblance G², qui pèse l'écart par le nombre d'occurrences"
    : "différence de fréquence relative";
  $("#dist-info").innerHTML =
    `Comparaison par <b>${esc(res.champ)}</b> — A : ${res.total_a} occ. · B : ${res.total_b} occ. ` +
    `(${mesure} ; cliquer pour voir en contexte)`;
  if (!res.total_a && !res.total_b) {
    box.innerHTML = "";
    direVide((m) => { box.innerHTML = `<div class="muted small">${esc(m)}</div>`; },
             false, "Aucune donnée dans ces sous-corpus.");
    return;
  }
  box.innerHTML =
    `<div class="comp-col col-a"><h3 class="comp-h">▲ Sur-représentés en A</h3>` +
      `<div class="dist">${compColumn(res.sur_a, "a", sideFilters("f"), cle)}</div></div>` +
    `<div class="comp-col col-b"><h3 class="comp-h">▲ Sur-représentés en B</h3>` +
      `<div class="dist">${compColumn(res.sur_b, "b", sideFilters("b"), cle)}</div></div>`;
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
/* ANA-6 — la note d'une ligne : un repère dans le rendu aligné, la note entière dans la
   liste. Les tags qui l'accompagnaient sont partis avec le basculement d'ANN-7. `note` peut
   manquer (doublure de test, réponse ancienne) : absente, il n'y a rien à montrer. */
function kwicRepere(r) {
  return r.note ? '<span class="kw-note" role="img" aria-label="porte une note"'
    + ' title="Porte une note — le rendu liste la montre en entier">📝</span>' : "";
}
function kwicRowAligne(r, avecNote) {
  const parts = splitPivot(r.ocr_texte, r.texte);
  const L = parts ? esc(parts.left) : esc(r.ocr_texte || "");
  const K = parts ? esc(parts.key) : "";
  const R = parts ? esc(parts.right) : "";
  // Une cellule par ligne dans la 5e colonne, VIDE comprise : les lignes sont en
  // `display: contents`, et une cellule manquante décalerait toute la grille.
  const note = avecNote ? `<span class="kw-notes">${kwicRepere(r)}</span>` : "";
  return `<a class="kwic-row" href="${esc(kwicViewerHref(r))}" title="Voir la case">` +
    `<span class="kw-left">${L}</span><span class="kw-key">${K}</span>` +
    `<span class="kw-right">${R}</span><span class="kw-meta">${kwicMeta(r)}</span>${note}</a>`;
}
function kwicRowListe(r) {
  const parts = splitPivot(r.ocr_texte, r.texte);
  const texte = parts
    ? `${esc(parts.left)}<b class="kw-hit">${esc(parts.key)}</b>${esc(parts.right)}`
    : esc(r.ocr_texte || "");
  // La liste dit TOUT : la note entière en encre pleine — c'est ici qu'on la lit, et une
  // note en petit texte atténué serait l'invisible déplacé.
  const note = r.note ? `<span class="kwic-note">📝 ${esc(r.note)}</span>` : "";
  return `<a class="kwic-item" href="${esc(kwicViewerHref(r))}" title="Voir la case">` +
    `<span class="kwic-meta">${kwicMeta(r)}</span>` +
    `<span class="kwic-text">« ${texte} »</span>${note}</a>`;
}
function renderKwic(res) {
  const box = $("#kwic");
  const compte = Resultats.etat(res.count);
  const rows = (res.results || []).slice(0, compte.n);
  const lemme = lemmeSaisi();
  $("#dist-info").innerHTML =
    Resultats.nombre(compte.n, "occurrence") + (lemme ? ` de <b>${esc(lemme)}</b>` : "") +
    (compte.tronque ? ` (limité à ${Resultats.LIMITE})` : "") +
    " — cliquer une ligne pour voir la case";
  if (!rows.length) {
    box.className = "kwic";
    box.innerHTML = "";
    direVide((m) => { box.innerHTML = `<p class="muted small">${esc(m)}</p>`; },
             false, "Aucune occurrence.");
    return;
  }
  const aligne = kwicStyle() === "aligne";
  // La 5e colonne n'existe que si une ligne AFFICHÉE a une note : sur un corpus sans
  // note, elle ne coûterait qu'une gouttière vide.
  const avecNote = aligne && rows.some((r) => r.note);
  box.className = "kwic" + (aligne ? " kwic-aligned" + (avecNote ? " kwic-notes" : "")
                                   : " kwic-list");
  box.innerHTML = rows.map((r) => aligne ? kwicRowAligne(r, avecNote) : kwicRowListe(r)).join("");
}

/* ---------------- Rendu : tableau croisé 2D (ANA-2) ---------------- */
const CROISE_LIMIT = 20;                 // top-N par axe (borne la lisibilité du tableau)
let CROISE = null;                       // dernier résultat, pour le drill des cellules

function croiseLbl(v) { return v.libelle == null ? "(vide)" : v.libelle; }

function renderCroise(res) {
  CROISE = res;
  const box = $("#croise"), xs = res.x, ys = res.y;
  const tronque = res.x_tronque || res.y_tronque;
  $("#dist-info").innerHTML =
    `<b>${esc(res.libelle_x)}</b> × <b>${esc(res.libelle_y)}</b> — ${Resultats.nombre(res.total, "croisement")}` +
    (tronque ? ` (top ${CROISE_LIMIT} par axe)` : "") +
    " — cliquer une cellule pour voir les tokens en contexte";
  if (!xs.length || !ys.length) {
    box.innerHTML = "";
    direVide((m) => { box.innerHTML = `<p class="muted small">${esc(m)}</p>`; },
             criteresA(), NLP_A_RELANCER);
    return;
  }
  const maxCell = Math.max(1, ...res.grille.flat());
  let html = '<table class="croise-table"><thead><tr>' +
    `<th class="croise-corner">${esc(res.libelle_x)} \\ ${esc(res.libelle_y)}</th>`;
  for (const y of ys) html += `<th scope="col">${esc(croiseLbl(y))}</th>`;
  html += '<th scope="col" class="croise-tot" title="Total de la ligne">Σ</th></tr></thead><tbody>';
  xs.forEach((x, i) => {
    html += `<tr><th scope="row">${esc(croiseLbl(x))}</th>`;
    ys.forEach((y, j) => {
      const n = res.grille[i][j];
      const a = (n / maxCell).toFixed(3);
      if (n > 0 && x.cle != null && y.cle != null)     // cellule cliquable → preuves
        html += `<td class="croise-cell" style="--a:${a}">`
              + `<button type="button" class="croise-hit" data-i="${i}" data-j="${j}" `
              + `title="Voir « ${esc(croiseLbl(x))} × ${esc(croiseLbl(y))} » en concordance">${n}</button></td>`;
      else
        html += `<td class="croise-cell${n ? "" : " zero"}" style="--a:${a}">${n || ""}</td>`;
    });
    html += `<td class="croise-tot">${x.total}</td></tr>`;
  });
  html += '<tr class="croise-totrow"><th scope="row">Σ</th>';
  for (const y of ys) html += `<td class="croise-tot">${y.total}</td>`;
  html += `<td class="croise-tot">${res.total}</td></tr></tbody></table>`;
  box.innerHTML = html;
  box.querySelectorAll(".croise-hit").forEach((btn) => {
    btn.onclick = () => drillCroise(Number(btn.dataset.i), Number(btn.dataset.j));
  });
}

/* Descente aux preuves : applique les deux valeurs de la cellule aux filtres A puis bascule
   en Concordance (tokens en contexte — chaque ligne deep-linke ensuite la Visionneuse). */
function drillCroise(i, j) {
  if (!CROISE) return;
  $("#f-vue").value = "concordance";
  syncControls();                                   // active les contrôles (POS, etc.)
  applyAxisFilter(CROISE.filtre_x, CROISE.x[i].cle);
  applyAxisFilter(CROISE.filtre_y, CROISE.y[j].cle);
  run();
}
function applyAxisFilter(param, cle) {
  if (cle == null) return;                           // cellule « (vide) » : pas de filtre d'absence
  const v = String(cle);
  if (param === "type") $("#f-type").value = v;
  else if (param === "pos") $("#f-pos").value = v;
  else if (param === "provenance") $("#f-prov").value = v;
  else if (param === "morph") $("#f-morph").value = v;
  else if (param === "personnage") $("#f-personnage").value = v;
}

/* ---------------- Contrôles / démarrage ---------------- */
function syncControls() {
  const v = vue();
  $("#sub-b").hidden = v !== "comparaison";
  document.querySelectorAll(".sub-title").forEach((el) => { el.hidden = v !== "comparaison"; });
  $("#wrap-champ").hidden = v === "concordance" || v === "croisement";  // « distribuer par » : distrib./comp.
  $("#wrap-metrique").hidden = v !== "comparaison";  // « classer par » : comparaison seule (ANA-4)
  $("#wrap-lemme").hidden = v !== "concordance";     // champ lemme/mot en concordance
  $("#wrap-kwic").hidden = v !== "concordance";      // bascule aligné/liste en concordance
  $("#wrap-axes").hidden = v !== "croisement";       // sélecteurs d'axes en croisement
  const byPos = (v === "distribution" || v === "comparaison") && champ() === "pos";
  $("#f-pos").disabled = byPos;     // filtre POS redondant si on distribue PAR POS
  $("#b-pos").disabled = byPos;
}

function restoreFromUrl() {
  const p = new URLSearchParams(INITIAL_QS);
  // `vue` (nouveau) ; rétro-compat : ancien `compare=1` → comparaison.
  $("#f-vue").value = p.get("vue") || (p.get("compare") === "1" ? "comparaison" : "distribution");
  $("#f-champ").value = p.get("champ") || "lemme";
  $("#f-lemme").value = p.get("lemme") || "";
  $("#f-kwic-style").value = p.get("kwic") || "aligne";
  $("#f-metrique").value = p.get("metrique") === "ll" ? "ll" : "diff";   // inconnu → défaut
  $("#f-axe-x").value = p.get("axe_x") || "pos";     // options déjà peuplées (populateAxes)
  $("#f-axe-y").value = p.get("axe_y") || "type";
  const setSide = (pre, keyfn) => {
    $(`#${pre}-album`).value = p.get(keyfn("album")) || "";
    $(`#${pre}-type`).value = p.get(keyfn("type")) || "";
    $(`#${pre}-pos`).value = p.get(keyfn("pos")) || "";
    $(`#${pre}-morph`).value = p.get(keyfn("morph")) || "";
    $(`#${pre}-prov`).value = p.get(keyfn("provenance")) || "";
    $(`#${pre}-personnage`).value = p.get(keyfn("personnage")) || "";
  };
  setSide("f", (k) => k);              // A = paramètres nus
  setSide("b", (k) => "b_" + k);       // B = préfixés
  state.anciens = [...p].filter(([k]) => PARAMETRES_D_HIER.includes(k));
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

/* ---------------- Accord modèle↔humain (NLP-1) : qualité de l'index ----------------
   Modale de consultation : part des tokens relus où le modèle avait déjà la valeur finale
   (par champ) + confusion POS. Read model : GET /api/analyse/accord. */
async function openAccord() { $("#accord-modal").hidden = false; await loadAccord(); }
function closeAccord() { $("#accord-modal").hidden = true; }

async function loadAccord() {
  const body = $("#accord-body");
  body.textContent = "Chargement…";
  try { renderAccord(await apiGet("/api/analyse/accord")); }
  catch (e) { body.textContent = "Impossible de charger le rapport d'accord."; }
}

function pctAccord(x) { return x == null ? "—" : Math.round(x * 100) + " %"; }

const ACCORD_CHAMPS = [["lemme", "lemme"], ["pos", "catégorie (POS)"], ["morph", "morphologie"]];

function renderAccord(r) {
  const body = $("#accord-body");
  const modele = r.modele ? esc(r.modele) : "modèle inconnu";
  const date = r.indexe_le ? ` · indexé le ${esc(r.indexe_le)}` : "";
  if (!r.revus) {
    body.innerHTML = `<p class="muted small">Modèle : <b>${modele}</b>${date}</p>`
      + `<p class="muted small">Aucun token relu — corrigez ou validez des tokens (Atelier)`
      + ` pour mesurer l'accord.</p>`;
    return;
  }
  let html = `<p class="muted small">Modèle : <b>${modele}</b>${date} — <b>${r.revus}</b> `
    + `${Resultats.accord(r.revus, "token relu", "tokens relus")} `
    + `(${Resultats.nombre(r.corriges, "corrigé")}, ${Resultats.nombre(r.valides, "validé")})</p>`;
  html += '<div class="table-cadre" tabindex="0" role="region" aria-label="Accord par champ">'
    + '<table class="accord-table"><thead><tr><th scope="col">Champ</th>'
    + '<th scope="col">Accord</th><th scope="col">Taux</th></tr></thead><tbody>';
  for (const [ch, lbl] of ACCORD_CHAMPS) {
    const c = r.champs[ch];
    const pct = c.taux == null ? 0 : Math.round(c.taux * 100);
    html += `<tr><th scope="row">${esc(lbl)}</th><td>${c.accord}/${c.revus}</td>`
      + `<td><span class="accord-bar"><i style="width:${pct}%"></i></span> ${pctAccord(c.taux)}</td></tr>`;
  }
  html += '</tbody></table></div>';
  if (r.confusion_pos.length) {
    html += '<h4 class="accord-h">Confusion POS (auto → corrigé)</h4><ul class="accord-conf">';
    for (const x of r.confusion_pos)
      html += `<li><code>${esc(x.auto || "∅")}</code> → <code>${esc(x.humain)}</code>`
        + ` <span class="muted">× ${x.n}</span></li>`;
    html += '</ul>';
  }
  body.innerHTML = html;
}

/* ---------------- Accord inter-annotateurs (ANN-5) : accord de révision entre auteurs ---------- */
async function openAccordInter() { $("#accord-inter-modal").hidden = false; await loadAccordInter(); }
function closeAccordInter() { $("#accord-inter-modal").hidden = true; }

async function loadAccordInter() {
  const body = $("#accord-inter-body");
  body.textContent = "Chargement…";
  // Le message du SERVEUR, et non un libellé maison : depuis AUTH-1 la route peut refuser
  // (403) en expliquant pourquoi — elle nomme des personnes, elle est réservée à qui écrit.
  // `apiGet` porte déjà le `detail` ; l'écraser par « Impossible de charger le rapport »
  // transformait une décision motivée en panne apparente, exactement le silence qu'AUTH-2
  // combat. Le bouton RESTE visible : le cacher priverait la personne de la raison.
  try { renderAccordInter(await apiGet("/api/analyse/accord-inter")); }
  catch (e) { body.textContent = e.message || "Impossible de charger le rapport."; }
}

function valInter(v) { return (v == null || v === "") ? "∅" : v; }

function renderAccordInter(r) {
  const body = $("#accord-inter-body");
  if (!r.retouches) {
    body.innerHTML = '<p class="muted small">Aucune re-touche entre auteurs distincts — rien à '
      + 'comparer (nécessite plusieurs relecteurs authentifiés).</p>';
    return;
  }
  let html = `<p class="muted small"><b>${r.retouches}</b> `
    + `${Resultats.accord(r.retouches, "re-touche")} inter-auteurs · `
    + `${Resultats.nombre(r.auteurs.length, "auteur")} : ${r.auteurs.map(esc).join(", ")}</p>`;
  html += '<div class="table-cadre" tabindex="0" role="region" aria-label="Accord de révision par champ">'
    + '<table class="accord-table"><thead><tr><th scope="col">Champ</th>'
    + '<th scope="col">Accord</th><th scope="col">Taux</th></tr></thead><tbody>';
  for (const [ch, lbl] of ACCORD_CHAMPS) {
    const c = r.champs[ch], pct = c.taux == null ? 0 : Math.round(c.taux * 100);
    html += `<tr><th scope="row">${esc(lbl)}</th><td>${c.accords}/${c.retouches}</td>`
      + `<td><span class="accord-bar"><i style="width:${pct}%"></i></span> ${pctAccord(c.taux)}</td></tr>`;
  }
  html += '</tbody></table></div>';
  if (r.paires.length) {
    html += '<h4 class="accord-h">Par paire d\'auteurs</h4><ul class="accord-conf">';
    for (const p of r.paires)
      html += `<li>${esc(p.a)} ↔ ${esc(p.b)} <span class="muted">${p.accords}/${p.retouches}`
        + ` — ${pctAccord(p.taux)}</span></li>`;
    html += '</ul>';
  }
  if (r.divergences.length) {
    html += `<h4 class="accord-h">Divergences${r.divergences_tronque ? " (tronqué)" : ""}</h4>`
      + '<ul class="accord-conf">';
    for (const d of r.divergences) {
      const cit = (d.citation && d.citation.texte) ? esc(d.citation.texte) + " · " : "";
      for (const x of d.diffs)
        html += `<li>${cit}<code>${esc(valInter(d.forme))}</code> [${esc(x.champ)}] `
          + `${esc(d.de)}=<code>${esc(valInter(x.avant))}</code> → `
          + `${esc(d.a)}=<code>${esc(valInter(x.apres))}</code></li>`;
    }
    html += '</ul>';
  }
  body.innerHTML = html;
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
  $("#f-metrique").onchange = run;                 // comparaison : mesure de classement
  $("#f-axe-x").onchange = run;                    // croisement : axes
  $("#f-axe-y").onchange = run;
  ["#f-album", "#f-type", "#f-pos", "#f-prov", "#f-personnage",
   "#b-album", "#b-type", "#b-pos", "#b-prov", "#b-personnage"]
    .forEach((s) => { $(s).onchange = run; });
  $("#btn-export-analyse").onclick = exporterAnalyse;
  // DROIT-2 — les trois exports de la page ne se proposent qu'à qui peut exporter
  // quelque part ; la note dit quand le fichier emportera moins que l'écran.
  Promise.resolve(window.BDMoi).catch(() => null).then((moi) => {
    const etat = etatExport(moi);
    for (const id of ["#btn-export-analyse", "#btn-export-accord",
                      "#btn-export-accord-inter"]) $(id).hidden = etat === "rien";
    const note = $("#export-note");
    note.textContent = noteExport(etat, moi);
    note.hidden = !note.textContent;
  });
  // Les deux panneaux n'ont pas de critères : leur export est l'écran, en fichier.
  $("#btn-export-accord").onclick = () => { window.location = "/api/analyse/accord.csv"; };
  $("#btn-export-accord-inter").onclick = () => {
    window.location = "/api/analyse/accord-inter.csv";
  };
  $("#btn-accord").onclick = openAccord;
  $("#accord-close").onclick = closeAccord;
  $("#accord-modal").addEventListener("mousedown", (e) => {
    if (e.target.id === "accord-modal") closeAccord();
  });
  if (window.BDDialog)
    BDDialog.register($("#accord-modal"),
      { box: ".modal-box", labelledby: "accord-title", onClose: closeAccord });
  // Accord inter-annotateurs (ANN-5) — modale accessible.
  $("#btn-accord-inter").onclick = openAccordInter;
  $("#accord-inter-close").onclick = closeAccordInter;
  $("#accord-inter-modal").addEventListener("mousedown", (e) => {
    if (e.target.id === "accord-inter-modal") closeAccordInter();
  });
  if (window.BDDialog)
    BDDialog.register($("#accord-inter-modal"),
      { box: ".modal-box", labelledby: "accord-inter-title", onClose: closeAccordInter });
  state.corpus = loadCorpus();
  await loadAlbums();        // options d'album (A et B) avant restauration
  await loadPersonnages();   // locuteurs (A et B)
  populateAxes();            // options des axes de croisement
  restoreFromUrl();
  setupBack();
  syncControls();
  run();
}

setup();
