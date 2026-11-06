/* ===================================================================
   BéDéditeur — page de recherche / index (vanilla JS)
   Interroge /api/recherche (FTS5) + /api/corpus + /api/albums.
   Un clic sur un résultat ouvre la visionneuse pile sur la région.
   =================================================================== */
"use strict";

// $, apiGet, escapeHtml : lib/common.js (chargé avant ce script).

const state = {
  albums: [],
  personnage: "",       // facette ANN-2 transportée par le drill Exploration (pas d'UI propre ici)
  // ANN-7, I7 — les paramètres d'hier (`tags`, `tag_scope`, `attributs`) d'un lien
  // enregistré : envoyés UNE fois au serveur, qui les refuse par un 422 qui le dit. Les
  // taire rendrait le corpus entier sous un lien qui a l'air filtré.
  anciens: [],
  timer: null,
  searchGen: 0,   // jeton de fraîcheur : ignore les réponses de recherche périmées
  corpus: Promise.resolve(null),   // GET /api/corpus, ou null : la cause d'un écran vide (UX-6)
};

// INFRA-5 — l'état de départ (avant que search() ne réécrive l'URL) : celui de l'adresse
// s'il y en a un, sinon — on arrive par le menu — la dernière recherche de cet onglet,
// gardée en stockage de SESSION. L'adresse l'emporte toujours ; cf. static/lib/nav.js.
const STOCKAGE = Nav.stockageDeSession(window);
const INITIAL_QS = Nav.etatDeDepart(location.search, STOCKAGE, "recherche").qs;
// `retour` n'est suivi que s'il vise une page interne (cf. static/lib/nav.js → anti
// open-redirect/XSS).
const RETOUR = Nav.safeRetour(new URLSearchParams(INITIAL_QS).get("retour"));   // d'où l'on vient (drill Exploration)
const UPOS = ["ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN", "NUM",
              "PART", "PRON", "PROPN", "PUNCT", "SCONJ", "SYM", "VERB", "X"];

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
    $("#corpus-stats").innerHTML = Resultats.chiffresCorpus(c);   // accordés (UX-6)
    return c;
  } catch (e) { return null; /* aperçu non bloquant */ }
}

/* UX-6 — un écran vide dit sa cause quand le corpus la donne : sans album à lire, ni
   « Tapez un mot-clé » ni « Aucun résultat » ne disent pourquoi rien ne viendra. Écrit
   seulement si aucune recherche n'est partie depuis. */
function direVide(defaut) {
  const gen = state.searchGen;
  const box = $("#results");
  box.innerHTML = `<div class="search-hint">${escapeHtml(defaut)}</div>`;
  state.corpus.then((c) => {
    const cause = Resultats.causeVide(c);
    if (cause && gen === state.searchGen)
      box.innerHTML = `<div class="search-hint">${escapeHtml(cause)}</div>`;
  });
}

/* ---------------- Filtres : albums ---------------- */
async function loadAlbums() {
  try {
    // COL-3, tranche 2 — une copie gardée au fonds n'est plus un album de travail : seule
    // une portée totale la reçoit, et elle se règle dans l'Administration. Un filtre
    // d'écran, pas une garde.
    state.albums = (await apiGet("/api/albums")).filter((a) => !a.au_fonds);
    const sel = $("#f-album");
    for (const a of state.albums) {
      const o = document.createElement("option");
      o.value = String(a.id);
      o.textContent = `${serieTome(a) ? serieTome(a) + " · " : ""}${a.titre}`;
      sel.appendChild(o);
    }
  } catch (e) { /* ignore */ }
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
  if (state.personnage) p.set("personnage", state.personnage);
  state.anciens.forEach(([k, v]) => p.append(k, v));
  return p;
}

function search() {
  const p = searchParams();                    // critères réels (fetch + test de vacuité)
  state.anciens = [];                          // dits une fois : le geste suivant s'en passe
  const vide = [...p].length === 0;
  // état dans l'URL (replaceState) → recherche partageable + rechargement sans perte ;
  // on y conserve `retour` (contexte de drill) sans l'envoyer à la requête.
  const display = new URLSearchParams(p);
  if (RETOUR) display.set("retour", RETOUR);
  history.replaceState(null, "", [...display].length ? "?" + display.toString() : location.pathname);
  Nav.memoriser(STOCKAGE, "recherche", display.toString());   // INFRA-5 : vide compris
  if (vide) {
    ++state.searchGen;                         // une réponse en vol n'écrase plus l'invite
    direVide("Tapez un mot-clé, ou choisissez un album / type / facette grammaticale.");
    $("#result-count").textContent = "";
    $("#btn-export").disabled = true;
    return;
  }
  // On demande UN de plus que ce qu'on affichera : ce résultat surnuméraire ne se
  // voit jamais, il sert uniquement de témoin « il y en a d'autres ». Sans lui, un
  // corpus de exactement 200 correspondances serait annoncé « (limité) » à tort (C1).
  const url = new URLSearchParams(p);
  url.set("limit", String(Resultats.LIMITE + 1));
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
  // `retour` = l'URL de recherche courante (filtres + son propre retour vers
  // l'Exploration s'il existe) → la Visionneuse pourra ramener « à sa place ».
  $("#preview-edit").href = `/?album=${r.album_id}&planche=${r.planche_id}&region=${r.region_id}`
    + `&retour=${encodeURIComponent(location.pathname + location.search)}`;
  const img = $("#preview-img"), svg = $("#preview-overlay");
  img.src = r.url_web || "";
  svg.setAttribute("viewBox", `0 0 ${r.largeur_px || 0} ${r.hauteur_px || 0}`);
  svg.innerHTML = (r.w && r.h)
    ? `<rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" class="pv-rect"/>` : "";
  $("#preview-text").innerHTML = (r.ocr_texte || "").trim()
    ? escapeHtml(r.ocr_texte) : '<span class="muted">(sans texte)</span>';
  $("#preview-meta").innerHTML = r.note ? "📝 " + escapeHtml(r.note) : "";
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
  const compte = Resultats.etat(res.count);
  $("#result-count").textContent = compte.texte;
  $("#btn-export").disabled = !res.count;
  const box = $("#results");
  box.innerHTML = "";
  if (!res.results.length) {
    // « Aucun résultat » est vrai et inutile quand la requête ne portait aucun terme
    // cherchable : la personne croit que le corpus est muet, alors que c'est sa
    // saisie qui n'a rien demandé. Le serveur tranche (la règle est celle du
    // tokenizer) ; l'écran se contente de le dire.
    box.innerHTML = res.sans_terme
      ? '<div class="search-hint">Cette recherche ne contient aucun terme cherchable :'
        + ' la ponctuation et les symboles ne sont pas indexés. Essayez un mot,'
        + ' ou passez par les filtres.</div>'
      : "";
    if (!res.sans_terme) direVide("Aucun résultat.");
    return;
  }
  for (const r of res.results.slice(0, compte.n)) {
    const card = document.createElement("div");
    card.className = "result";
    card.title = "Aperçu en place (clic) — ✏️ pour éditer dans l'Atelier";
    // Cliquable mais pas un lien (ouvre l'aperçu) → le rendre accessible au clavier.
    card.setAttribute("role", "button");
    card.tabIndex = 0;

    const texte = (r.ocr_texte || "").trim();
    const noteHtml = r.note
      ? `<div class="r-note">📝 ${highlight(r.note, q)}</div>` : "";

    card.innerHTML =
      `<img class="r-thumb" loading="lazy" alt=""` +
      ` src="/api/regions/${r.region_id}/crop?taille=260">` +
      `<div class="r-body">` +
        `<div class="r-text">${texte ? highlight(texte, q) : '<span class="muted">(sans texte)</span>'}</div>` +
        noteHtml +
        `<div class="r-meta muted small">${escapeHtml(r.album_titre)} · ` +
        `<span class="r-cite">${escapeHtml(r.citation ? r.citation.texte : "planche " + r.planche_numero)}</span> · ` +
        `<span class="r-type">${r.type}</span></div>` +
      `</div>`;
    // une vignette illisible (crop indisponible) est simplement masquée
    card.querySelector(".r-thumb").onerror = (e) => { e.target.style.display = "none"; };
    const activate = () => {
      box.querySelectorAll(".result.active").forEach((el) => el.classList.remove("active"));
      card.classList.add("active");
      openPreview(r);
    };
    card.onclick = activate;
    card.addEventListener("keydown", (e) => {   // Entrée/Espace = activer (clavier)
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activate(); }
    });
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
  state.personnage = p.get("personnage") || "";
  state.anciens = [...p].filter(([k]) => ["tags", "tag_scope", "attributs"].includes(k));
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
  // DROIT-2 — le bouton ne se propose qu'à qui peut exporter quelque part, et la note
  // dit quand le fichier emportera moins que l'écran. La garde reste au serveur.
  Promise.resolve(window.BDMoi).catch(() => null).then((moi) => {
    const etat = etatExport(moi);
    $("#btn-export").hidden = etat === "rien";
    const note = $("#export-note");
    note.textContent = noteExport(etat, moi);
    note.hidden = !note.textContent;
  });
  $("#preview-close").onclick = closePreview;
  document.addEventListener("keydown", (e) => {   // Échap ferme l'aperçu
    if (e.key === "Escape" && !$("#preview").hidden) closePreview();
  });
  setupBack();   // bouton « ← Retour » (drill explicite, ou history.back si on vient de l'app)
  state.corpus = loadCorpus();
  await loadAlbums();        // options d'album AVANT de restaurer la sélection d'album
  restoreFromUrl();
  search();                  // rejoue la recherche restaurée (ou affiche l'invite)
}

setup();
