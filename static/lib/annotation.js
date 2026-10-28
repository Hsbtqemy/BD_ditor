/* La page ANNOTATION — sa logique pure, sans DOM (ANN-7, tranche 2 ; ANN-6, l'écran du
   relevé ; cadrage `docs/ann7-tranche2-cadrage.md`). Chargé en <script> par la page →
   expose `window.BDAnnotation` ; aussi require()-able par `tests/js/annotation.test.js`,
   qui la vérifie par tables de cas. Rien n'est lu au chargement : ni le document, ni le
   stockage, ni l'adresse.

   Une surface ordinaire, PAS un module montable (H7, 2026-10-27) : la page n'a qu'un hôte.
   Ce qui garde la porte ouverte au second montage, c'est que sa logique vit ICI, hors de
   `static/annotation.js`, qui ne fait que dessiner.

   CE QUE CE PREMIER TEMPS DÉCIDE (commit 1 : la page, sans grille ni pose) :
     · comment une planche se range en CASES, dans l'ordre de lecture, et ce que chaque case
       contient — la minicarte ne sert qu'à choisir une case, et l'on choisit DANS la case ;
     · ce qu'une région s'appelle à l'écran (« c3 », « b2 ») et ce qu'est sa sorte ;
     · l'adresse de la page et le lien vers l'Atelier ;
     · la taille, en pixels master, d'une étiquette qu'on veut lire à taille d'écran
       constante quelle que soit la case ;
     · ce que dit « Préparée » et ce que montre le Contexte, en lecture.
   Le commit 2 y ajoute la grille en lecture (masque, arbre, comptes, filtre, guide) ; le
   commit 3 la désignation des mots et la pose (passage, couloirs, « Porte sur », la cible
   d'un geste et ce qu'il fait selon ce qui est déjà posé, la liste, « Relevés : ▾ », la
   cardinalité). Le parcours et le décompte s'y ajouteront, au même endroit.

   CE N'EST PAS UNE GARDE. Tout ce qui suit lit ce que le serveur a déjà décidé : les
   régions d'une planche qu'on lit, leurs citations, le statut de relecture. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDAnnotation = api;                                               // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Les zones de TEXTE : celles qui ont des mots (`grilles.TYPES_TEXTE`). */
  const TYPES_TEXTE = ["bulle", "cartouche", "texte"];

  /* Le nom d'une sorte de région, pour une phrase courte (« Note de la bulle b2 »). */
  const NOMS = {
    case: "case", bulle: "bulle", cartouche: "cartouche", texte: "texte",
    personnage: "boîte personnage", detail: "détail",
  };
  /* L'article de la sorte, pour « du cartouche » / « de la bulle ». */
  const MASCULINS = new Set(["cartouche", "texte", "detail"]);

  function estTexte(type) { return TYPES_TEXTE.includes(type); }
  function nomType(type) { return NOMS[type] || String(type || "zone"); }
  function deLa(type) {
    if (type === "personnage") return "de la boîte personnage";
    return (MASCULINS.has(type) ? "du " : "de la ") + nomType(type);
  }

  function entier(v) {
    if (typeof v === "number") return Number.isInteger(v) && v > 0 ? v : null;
    return typeof v === "string" && /^[1-9]\d*$/.test(v) ? Number(v) : null;
  }

  function parOrdre(a, b) {
    const oa = a.ordre === null || a.ordre === undefined ? Infinity : a.ordre;
    const ob = b.ordre === null || b.ordre === undefined ? Infinity : b.ordre;
    return oa === ob ? a.id - b.id : oa - ob;
  }

  function contient(c, r) {
    const cx = r.x + r.w / 2, cy = r.y + r.h / 2;
    return cx >= c.x && cx <= c.x + c.w && cy >= c.y && cy <= c.y + c.h;
  }

  /* LA PLANCHE EN CASES. `regions` : `GET /api/planches/{id}/regions` ; `W`, `H` : les
     dimensions master de la planche. Rend `[{ case, zones }]` dans l'ordre de lecture :
       · chaque CASE (le type `case`) dans son `ordre` — celui que l'outil recalcule —,
         puis ses ZONES : ses descendants dans l'arbre (`parent_id`), à toute profondeur,
         chacun suivi des siens, dans leur `ordre` ;
       · une région que l'arbre ne range dans aucune case va à la case qui contient son
         centre — l'arbre n'est pas toujours posé ;
       · ce qui ne tombe dans aucune case — une planche sans case, une bulle hors cadre —
         va à une case PSEUDO, la planche entière (`pseudo: true`, `id: null`), placée en
         dernier : jamais une zone qu'on ne peut pas choisir.
     Une région de type `case` rangée SOUS une autre case reste une case à part entière :
     « une zone tracée ici n'est jamais une case », et une case n'est jamais une zone. */
  function casesDeLaPlanche(regions, W, H) {
    const liste = Array.isArray(regions) ? regions : [];
    const parId = new Map(liste.map((r) => [r.id, r]));
    const cases = liste.filter((r) => r.type === "case").sort(parOrdre);
    const enfants = new Map();
    for (const r of liste) {
      if (r.parent_id === null || r.parent_id === undefined || !parId.has(r.parent_id)) continue;
      if (!enfants.has(r.parent_id)) enfants.set(r.parent_id, []);
      enfants.get(r.parent_id).push(r);
    }
    for (const l of enfants.values()) l.sort(parOrdre);
    const rangees = new Set();
    function descendants(id) {
      const out = [];
      for (const e of enfants.get(id) || []) {
        if (e.type === "case" || rangees.has(e.id)) continue;
        rangees.add(e.id);
        out.push(e, ...descendants(e.id));
      }
      return out;
    }
    const sortie = cases.map((c) => ({ case: c, zones: descendants(c.id) }));
    // Les RACINES hors de toute case : sans parent, ou d'un parent absent de la planche.
    const orphelines = liste.filter((r) => r.type !== "case" && !rangees.has(r.id))
      .filter((r) => r.parent_id === null || r.parent_id === undefined
              || !parId.has(r.parent_id)).sort(parOrdre);
    const reste = [];
    for (const r of orphelines) {
      const hote = sortie.find((s) => contient(s.case, r));
      rangees.add(r.id);
      const sous = [r, ...descendants(r.id)];
      if (hote) hote.zones.push(...sous);
      else reste.push(...sous);
    }
    if (reste.length || !sortie.length) {
      sortie.push({ case: { id: null, type: "case", pseudo: true, x: 0, y: 0,
                            w: W || 0, h: H || 0, citation: null },
                    zones: reste });
    }
    return sortie;
  }

  /* L'ÉTIQUETTE d'une région, celle de l'Atelier (`regionLabel`) : le rang de CITATION —
     « c2 » pour une case, « b1 » pour une zone de texte — ; sinon l'initiale de sa sorte et
     son rang parmi celles de sa case (`rang`, 1 pour la première). La case pseudo se dit
     « planche ». */
  function etiquette(region, rang) {
    if (!region) return "";
    if (region.pseudo) return "planche";
    const c = region.citation;
    if (c) {
      if (region.type === "case" && c.case !== null && c.case !== undefined) return "c" + c.case;
      if (region.type !== "case" && c.bulle !== null && c.bulle !== undefined) return "b" + c.bulle;
    }
    const initiale = { case: "c", personnage: "p", detail: "d", cartouche: "ca", texte: "t",
                       bulle: "b" }[region.type] || "z";
    return initiale + (rang || "?");
  }

  /* Les étiquettes des zones d'une case, une par zone : `Map(id → étiquette)`. Le rang de
     repli se compte PAR SORTE, dans l'ordre de la case. */
  function etiquettesDeLaCase(entree) {
    const rangs = {};
    const out = new Map();
    for (const z of (entree && entree.zones) || []) {
      rangs[z.type] = (rangs[z.type] || 0) + 1;
      out.set(z.id, etiquette(z, rangs[z.type]));
    }
    return out;
  }

  /* Où est une région : `{ caseIx, zoneId }` — l'index de sa case dans le rangement, et la
     zone (null : la case elle-même). `null` si elle n'est pas sur la planche. */
  function situer(rangement, regionId) {
    const id = entier(regionId);
    if (id === null) return null;
    const l = Array.isArray(rangement) ? rangement : [];
    for (let i = 0; i < l.length; i++) {
      if (l[i].case.id === id) return { caseIx: i, zoneId: null };
      if (l[i].zones.some((z) => z.id === id)) return { caseIx: i, zoneId: id };
    }
    return null;
  }

  /* Le libellé d'une planche dans la liste *Planche* : son numéro ÉDITORIAL (cité) pour une
     planche du récit, « paratexte » et son rang dans l'album sinon. */
  function libellePlanche(p) {
    if (!p) return "";
    if (p.role === "recit" && p.numero_editorial !== null && p.numero_editorial !== undefined) {
      return "planche " + p.numero_editorial;
    }
    return "paratexte · " + p.numero;
  }

  /* « Préparée » : combien de zones de texte porte la planche, et où en est sa relecture
     (`relecture_statut`, ANN-4 — le feu vert des relevés, Q9 : `a_faire`, `en_cours`,
     `faite`, `database.relecture_planches`), dite en mots. Une phrase COURTE, la même à
     chaque planche : la disposition ne bouge pas. Un statut inconnu se lit tel quel. */
  const RELECTURES = { a_faire: "à faire", en_cours: "en cours", faite: "faite" };

  function preparation(regions, relecture) {
    const n = (Array.isArray(regions) ? regions : []).filter((r) => estTexte(r.type)).length;
    const zones = n + (n > 1 ? " zones de texte" : " zone de texte");
    const statut = relecture && relecture.statut ? relecture.statut : null;
    return statut ? `${zones} · relecture ${RELECTURES[statut] || statut}` : zones;
  }

  /* L'ADRESSE de la page : `?collection=&album=&planche=&region=&grille=`, la forme de
     l'Atelier plus la collection et la grille ouverte. Ce qui est nul n'y est pas. */
  const CLES_ADRESSE = ["collection", "album", "planche", "region", "grille"];

  function adresse(etat) {
    const p = new URLSearchParams();
    for (const k of CLES_ADRESSE) {
      const v = etat ? etat[k] : null;
      if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
    }
    const qs = p.toString();
    return qs ? "?" + qs : "";
  }

  /* Ce que pose l'adresse : chaque clé en entier, ou `null`. La collection peut valoir
     « toutes » (`BDAtelier.TOUTES`) : elle se lit telle quelle. */
  function lireAdresse(search) {
    let p;
    try { p = new URLSearchParams(search || ""); } catch (e) { p = new URLSearchParams(); }
    const out = {};
    for (const k of CLES_ADRESSE) out[k] = entier(p.get(k));
    if (p.get("collection") === "toutes") out.collection = "toutes";
    return out;
  }

  /* « Ouvrir dans l'Atelier ↗ » : la même planche, la zone courante (ou la case), dans la
     même collection, et le retour vers cette page (`retour`, que `lib/nav.js` borne aux
     chemins internes). */
  function lienAtelier(etat, retour) {
    const p = new URLSearchParams();
    for (const k of ["album", "planche", "region", "collection"]) {
      const v = etat ? etat[k] : null;
      if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
    }
    if (retour) p.set("retour", retour);
    const qs = p.toString();
    return "/" + (qs ? "?" + qs : "");
  }

  /* L'ÉCHELLE d'un cadrage `meet` : combien de pixels d'écran par pixel master quand le
     rectangle `rect` (master) tient dans une boîte `largeur × hauteur` (écran). 0 sur une
     boîte ou un rectangle vides. */
  function echelle(rect, largeur, hauteur) {
    if (!rect || !(rect.w > 0) || !(rect.h > 0) || !(largeur > 0) || !(hauteur > 0)) return 0;
    return Math.min(largeur / rect.w, hauteur / rect.h);
  }

  /* La taille, en pixels MASTER, d'une étiquette lue à `px` pixels d'ÉCRAN sous cette
     échelle — « à ~12 px d'écran quelle que soit la case » (ANN-6, v3). Une échelle nulle
     (la boîte n'est pas encore mesurée) rend `null` : l'appelant n'écrit pas d'étiquette
     plutôt qu'une étiquette de taille absurde. */
  function taillePourEcran(px, k) {
    return k > 0 ? px / k : null;
  }

  /* LE RECADRAGE de la case dans le dérivé, en fond CSS (`background-size`,
     `background-position`, en pour cent) : l'image n'est pas un élément de la page, donc
     rien de la planche ne déborde de la boîte — un `<image>` découpé par un `clipPath`
     gardait son rectangle entier, hors de la fenêtre, et la mesure du reflow le comptait
     perdu (mesuré à 320 px dans un bac à sable). `W`, `H` : la planche en pixels master. */
  function recadrage(rect, W, H) {
    if (!rect || !(rect.w > 0) || !(rect.h > 0) || !(W > 0) || !(H > 0)) return null;
    const pos = (debut, cote, total) => (total === cote ? 0 : debut / (total - cote) * 100);
    return { taille: [W / rect.w * 100, H / rect.h * 100],
             position: [pos(rect.x, rect.w, W), pos(rect.y, rect.h, H)] };
  }

  /* Une zone bornée à sa case (l'intersection), ou `null` si elle n'y entre pas : une zone
     qui dépasse de sa case ne fait pas sortir son cadre de la boîte. */
  function dansLaCase(z, rect) {
    const x = Math.max(z.x, rect.x), y = Math.max(z.y, rect.y);
    const x2 = Math.min(z.x + z.w, rect.x + rect.w), y2 = Math.min(z.y + z.h, rect.y + rect.h);
    return x2 > x && y2 > y ? { x, y, w: x2 - x, h: y2 - y } : null;
  }

  /* Le CONTEXTE d'une zone, EN LECTURE : `[{ cle, libelle, valeur }]` — ce qui n'est pas du
     vocabulaire (ANN-6, « Le Contexte ne garde que ce qui n'est pas du vocabulaire ») : le
     locuteur d'une zone de texte, le personnage d'une boîte, la note de toute zone (la case
     comprise ; pas la case pseudo, qui n'est pas une région). `donnees` :
     `{ locuteur, personnage, note }` lus aux routes — `undefined` tant qu'ils ne sont pas
     revenus (« … »), `null` quand il n'y en a pas (« — »). */
  function contexte(zone, donnees) {
    if (!zone || zone.pseudo) return [];
    const d = donnees || {};
    const valeur = (v) => (v === undefined ? "…" : v === null || v === "" ? "—" : v);
    const nom = (p) => (p === undefined ? undefined : p ? p.nom : null);
    const lignes = [];
    if (estTexte(zone.type)) lignes.push({ cle: "locuteur", libelle: "Locuteur", valeur: valeur(nom(d.locuteur)) });
    if (zone.type === "personnage") {
      lignes.push({ cle: "personnage", libelle: "Personnage", valeur: valeur(nom(d.personnage)) });
    }
    lignes.push({ cle: "note", libelle: "Note", valeur: valeur(d.note) });
    return lignes;
  }

  /* ───────────── LA GRILLE, EN LECTURE (commit 2) ─────────────
     Ce qui suit lit ce que servent `GET /api/projets/{id}/grilles` (les grilles ACTIVES du
     projet, leur version, les collections qui les masquent) et `GET /api/grilles/{id}/
     versions/{n}` (le plan). L'outil ne connaît AUCUNE grille : rien ici ne nomme une
     rubrique, une entrée ou une forme d'une grille particulière — tout se lit dans le plan. */

  /* Une chaîne telle qu'on la compare : sans accents, en minuscules, les apostrophes
     typographiques ramenées à la droite, les espaces réduits — « l’écho » et « L'ECHO » se
     valent (maquette v3). */
  function normaliser(s) {
    return String(s === null || s === undefined ? "" : s).normalize("NFD")
      .replace(/\p{M}/gu, "").toLowerCase().replace(/[’‘`ʼ´]/g, "'")
      .replace(/\s+/g, " ").trim();
  }

  /* La collection choisie masque-t-elle cette grille ? « Toutes les collections du
     projet » ne masque rien : le masque est le filtre d'UNE collection (Q1). */
  function masquee(grille, collection) {
    return !!grille && (grille.masquee_dans || []).includes(collection);
  }

  /* Les ONGLETS : les grilles actives que la collection choisie ne masque pas, dans l'ordre
     où le serveur les rend (par nom). */
  function grillesVisibles(actives, collection) {
    return (Array.isArray(actives) ? actives : []).filter((g) => !masquee(g, collection));
  }

  /* La grille à ouvrir : celle qu'on voulait si elle est visible, sinon la première. */
  function grilleAOuvrir(visibles, voulue) {
    const l = Array.isArray(visibles) ? visibles : [];
    const v = entier(voulue);
    if (v !== null && l.some((g) => g.id === v)) return v;
    return l.length ? l[0].id : null;
  }

  const ETATS_VERSION = { publiee: "publiée", vivante: "vivante", brouillon: "brouillon" };

  /* L'infobulle d'un onglet : la version et sa note (maquette v3 : « version et note en
     infobulle »), et si la grille est ouverte. */
  function infobulleGrille(grille, plan) {
    if (!grille) return "";
    const v = grille.version || {};
    const parts = [grille.nom];
    if (grille.ouverte) parts.push("ouverte : elle s'enrichit en posant");
    else if (v.numero) parts.push(`version ${v.numero} (${ETATS_VERSION[v.etat] || v.etat})`);
    const note = plan && plan.note;
    return parts.join(" · ") + (note ? ` — ${note}` : "");
  }

  /* Le PLAN en arbre : les rubriques de tête dans leur ordre, chacune avec ses entrées puis
     ses sous-rubriques, à toute profondeur. Les entrées RETIRÉES n'y sont pas ; une entrée
     sans rubrique (ou d'une rubrique absente) va dans un groupe à part, en dernier
     (`cle: ""`). Rend `[{ cle, libelle, profondeur, entrees, enfants }]`. */
  function arbre(plan) {
    const rubriques = (plan && plan.rubriques) || [];
    const parCle = new Map(rubriques.map((r) => [r.cle, { cle: r.cle, libelle: r.libelle,
                                                          parent: r.parent_cle, entrees: [],
                                                          enfants: [] }]));
    const tete = [];
    for (const r of rubriques) {
      const n = parCle.get(r.cle);
      if (r.parent_cle !== null && r.parent_cle !== undefined && parCle.has(r.parent_cle)
          && r.parent_cle !== r.cle) parCle.get(r.parent_cle).enfants.push(n);
      else tete.push(n);
    }
    const seul = { cle: "", libelle: "Sans rubrique", parent: null, entrees: [], enfants: [] };
    for (const e of (plan && plan.entrees) || []) {
      if (e.retiree) continue;
      (parCle.get(e.rubrique_cle) || seul).entrees.push(e);
    }
    const profondeur = (n, k, vus) => {
      if (vus.has(n.cle)) return;
      vus.add(n.cle);
      n.profondeur = k;
      n.enfants.forEach((x) => profondeur(x, k + 1, vus));
    };
    const vus = new Set();
    tete.forEach((n) => profondeur(n, 0, vus));
    if (seul.entrees.length) { seul.profondeur = 0; tete.push(seul); }
    return tete;
  }

  /* Toutes les entrées (non retirées) d'un nœud de l'arbre et de ses descendants. */
  function entreesSous(noeud) {
    if (!noeud) return [];
    return [...noeud.entrees, ...noeud.enfants.flatMap(entreesSous)];
  }

  /* Le chemin d'une entrée, en mots : « A. Sons › Voix ». */
  function chemin(plan, entree) {
    const parCle = new Map(((plan && plan.rubriques) || []).map((r) => [r.cle, r.libelle]));
    return (entree && entree.rubriques ? entree.rubriques : [])
      .map((c) => parCle.get(c)).filter(Boolean).join(" › ");
  }

  /* Ce que « Afficher » propose : toute la grille, ou une rubrique de tête — et rien quand
     la grille n'en a qu'une (le choix n'aurait pas de sens). */
  function vuesAfficher(plan) {
    const tete = arbre(plan).filter((n) => n.cle !== "");
    return tete.length > 1 ? tete.map((n) => ({ cle: n.cle, libelle: n.libelle })) : [];
  }

  /* Les relevés de la ZONE choisie et de son CONTEXTE (maquette v3 : « dans cette zone et
     son contexte ») : sur la zone elle-même ; sur sa case, quand la zone est dans une case ;
     sur la planche (la surface). La case pseudo n'est pas une région : ses relevés « ici »
     sont ceux de la surface. Rend `{ ici, contexte }`. */
  function relevesDeLaZone(releves, zone, caseRegion, plancheId) {
    const l = Array.isArray(releves) ? releves : [];
    const surface = (r) => r.planche_id !== null && r.planche_id !== undefined
      && r.planche_id === plancheId;
    if (!zone) return { ici: [], contexte: [] };
    if (zone.pseudo) return { ici: l.filter(surface), contexte: [] };
    const ici = l.filter((r) => r.region_id === zone.id);
    const laCase = caseRegion && !caseRegion.pseudo && caseRegion.id !== zone.id
      ? caseRegion.id : null;
    const contexte = l.filter((r) => (laCase !== null && r.region_id === laCase) || surface(r));
    return { ici, contexte };
  }

  /* LES COMPTES « n ici » d'une grille, sur des relevés déjà choisis (`relevesDeLaZone`) :
     le total de la grille, par rubrique (descendants compris) et par entrée. Un relevé
     compte UNE fois, quelle que soit sa forme. */
  function compter(releves, grilleId, plan) {
    const siens = (Array.isArray(releves) ? releves : []).filter((r) => r.grille_id === grilleId);
    const parEntree = new Map();
    for (const r of siens) parEntree.set(r.entree_cle, (parEntree.get(r.entree_cle) || 0) + 1);
    const parRubrique = new Map();
    const visiter = (n) => {
      const total = n.entrees.reduce((a, e) => a + (parEntree.get(e.cle) || 0), 0)
        + n.enfants.reduce((a, x) => a + visiter(x), 0);
      parRubrique.set(n.cle, total);
      return total;
    };
    if (plan) arbre(plan).forEach(visiter);
    return { total: siens.length, parEntree, parRubrique };
  }

  /* La pastille « plusieurs » : la cardinalité ne se montre que là où elle surprend —
     « plusieurs » sur une cible ENTIÈRE (une zone, la planche), jamais sur des mots
     (tranché sur la v3, Q6). */
  function marquePlusieurs(entree) {
    return !!entree && entree.cardinalite === "plusieurs"
      && (entree.pose === "zone" || entree.pose === "planche");
  }

  /* La marque d'une cible PROPRE : une entrée qui déclare sa cible (`cible_declaree`) se
     pose d'elle-même sur elle, quel que soit « Porte sur ». Rend le mot court à écrire,
     ou `null` pour une entrée qui suit la cible de la version, ou qui vise des mots. */
  function marqueCible(entree) {
    if (!entree || !(entree.cible_declaree || []).length) return null;
    const c = entree.cibles || entree.cible_declaree;
    if (entree.pose === "planche") return "la planche";
    if (entree.pose === "entite") return "partout";
    if (entree.pose !== "zone") return null;
    if (c.every((x) => TYPES_TEXTE.includes(x))) return "toute la zone";
    if (c.length === 1 && c[0] === "case") return "la case";
    if (c.length === 1 && c[0] === "personnage") return "la boîte";
    if (c.length === 1 && c[0] === "detail") return "le détail";
    return "la zone";
  }

  /* LE FILTRE : les résultats de `requete` dans le plan, les meilleurs d'abord.
     Chaque mot de la requête doit se trouver (accents et apostrophes ignorés) dans le
     libellé, la définition, la structure ou les exemples. Une entrée à VARIANTES rend ses
     variantes ; une entrée à QUALIFICATIFS se rend seule, et « X par Y » (ou une requête
     qui ne se lit qu'avec un qualificatif) rend le phénomène AVEC un qualificatif de sa
     liste. Score : 0 le libellé commence par la requête, 1 il la contient, 2 elle ne se lit
     qu'avec un qualificatif, 3 ailleurs (définition, exemples). Rend `[{ entree_cle,
     variante_cle, qualificatif_cle, libelle, chemin, exemple, score }]`. */
  function chercher(plan, requete) {
    const nq = normaliser(requete);
    if (!nq || !plan) return [];
    const mots = nq.split(" ");
    const tout = (hay) => mots.every((m) => hay.includes(m));
    const score = (lib, base) => {
      const n = normaliser(lib);
      return n.startsWith(nq) ? 0 : n.includes(nq) ? 1 : base;
    };
    const par = nq.match(/^(.*\S)\s+par\s+(.+)$/);
    const listes = new Map(((plan.listes) || []).map((l) => [l.cle, l]));
    const sortie = [];
    let rang = 0;
    for (const e of plan.entrees || []) {
      if (e.retiree) continue;
      const ch = chemin(plan, e);
      const hayE = normaliser([e.libelle, e.definition, e.structure,
                               ...(e.exemples || [])].join(" "));
      const ajouter = (r) => sortie.push({ variante_cle: null, qualificatif_cle: null,
                                           exemple: null, chemin: ch, rang: rang++, ...r });
      if (e.forme === "variantes") {
        for (const v of e.variantes || []) {
          const hay = normaliser([v.libelle, v.definition, v.structure, ...(v.exemples || []),
                                  e.libelle].join(" "));
          if (tout(hay)) {
            ajouter({ entree_cle: e.cle, variante_cle: v.cle, libelle: v.libelle,
                      chemin: ch ? `${ch} › ${e.libelle}` : e.libelle,
                      exemple: (v.exemples || [])[0] || null, score: score(v.libelle, 3) });
          }
        }
        continue;
      }
      if (e.forme === "qualificatifs") {
        const liste = listes.get(e.liste_cle);
        const qualifs = liste ? liste.qualificatifs : [];
        if (par) {
          const [, gauche, droite] = par;
          if (normaliser(e.libelle).includes(gauche)) {
            for (const q of qualifs) {
              if (normaliser(q.libelle).includes(droite)) {
                ajouter({ entree_cle: e.cle, qualificatif_cle: q.cle,
                          libelle: `${e.libelle} par ${q.libelle}`, score: 0 });
              }
            }
          }
          continue;
        }
        if (tout(hayE)) {
          ajouter({ entree_cle: e.cle, libelle: e.libelle,
                    exemple: (e.exemples || [])[0] || null, score: score(e.libelle, 3) });
        } else {
          for (const q of qualifs) {
            if (tout(normaliser(`${e.libelle} ${q.libelle} ${q.definition || ""}`))) {
              ajouter({ entree_cle: e.cle, qualificatif_cle: q.cle,
                        libelle: `${e.libelle} · ${q.libelle}`, score: 2 });
            }
          }
        }
        continue;
      }
      if (tout(hayE)) {
        ajouter({ entree_cle: e.cle, libelle: e.libelle,
                  exemple: (e.exemples || [])[0] || null, score: score(e.libelle, 3) });
      }
    }
    sortie.sort((a, b) => a.score - b.score || a.rang - b.rang);
    return sortie.map(({ rang: _r, ...r }) => r);
  }

  /* LA LIGNE DU GUIDE d'une entrée (ou de l'une de ses variantes) : ce qu'on relève, sa
     structure, ses exemples, sa liste de qualificatifs, et son piège. `null` si l'entrée
     n'est pas dans le plan. */
  function ligneDuGuide(plan, entreeCle, varianteCle) {
    const e = ((plan && plan.entrees) || []).find((x) => x.cle === entreeCle);
    if (!e) return null;
    const v = varianteCle ? (e.variantes || []).find((x) => x.cle === varianteCle) : null;
    const ch = chemin(plan, e);
    const liste = e.liste_cle ? (plan.listes || []).find((l) => l.cle === e.liste_cle) : null;
    const exemples = v ? (v.exemples || [])
      : e.forme === "variantes"
        ? (e.variantes || []).flatMap((x) => (x.exemples || []).map((t) => `${x.libelle} : ${t}`))
        : (e.exemples || []);
    return {
      libelle: v ? v.libelle : e.libelle,
      chemin: v ? (ch ? `${ch} › ${e.libelle}` : e.libelle) : ch,
      definition: (v && v.definition) || e.definition || null,
      structure: (v && v.structure) || (v ? null : e.structure) || null,
      exemples,
      qualificatifs: liste ? { libelle: liste.libelle || liste.cle,
                               termes: liste.qualificatifs.map((q) => q.libelle) } : null,
      piege: (v && v.piege) || e.piege || null,
    };
  }

  /* LE GUIDE COMPLET, produit depuis la grille (« il ne se tient plus à côté de l'outil ») :
     une section par rubrique, à toute profondeur, chacune avec ses lignes — le phénomène,
     sa définition, ce qu'on pose (l'entrée, ses variantes et leur structure, ou sa liste de
     qualificatifs), ses exemples — ; puis les listes de qualificatifs ; puis les pièges.
     Rend `{ sections: [{ titre, niveau, lignes }], listes, pieges }`. */
  function guideComplet(plan) {
    const listes = new Map(((plan && plan.listes) || []).map((l) => [l.cle, l]));
    const ligne = (e) => ({
      cle: e.cle, phenomene: e.libelle, definition: e.definition || null,
      aPoser: e.forme === "variantes"
        ? (e.variantes || []).map((v) => ({ libelle: v.libelle, structure: v.structure || null }))
        : e.forme === "qualificatifs"
          ? [{ libelle: e.libelle,
               structure: listes.get(e.liste_cle)
                 ? `+ ${listes.get(e.liste_cle).libelle || e.liste_cle}` : null }]
          : [{ libelle: e.libelle, structure: e.structure || null }],
      exemples: e.forme === "variantes"
        ? (e.variantes || []).flatMap((v) => v.exemples || []) : (e.exemples || []),
    });
    const sections = [];
    const visiter = (n) => {
      sections.push({ titre: n.libelle, niveau: n.profondeur || 0, lignes: n.entrees.map(ligne) });
      n.enfants.forEach(visiter);
    };
    arbre(plan).forEach(visiter);
    const pieges = [];
    for (const e of (plan && plan.entrees) || []) {
      if (e.retiree) continue;
      if (e.piege) pieges.push({ entree: e.libelle, piege: e.piege });
      for (const v of e.variantes || []) {
        if (v.piege) pieges.push({ entree: `${e.libelle} › ${v.libelle}`, piege: v.piege });
      }
    }
    return {
      sections,
      listes: ((plan && plan.listes) || []).map((l) => ({
        libelle: l.libelle || l.cle,
        termes: l.qualificatifs.map((q) => ({ libelle: q.libelle, definition: q.definition || null })) })),
      pieges,
    };
  }

  /* ───────────── DÉSIGNER ET POSER (commit 3) ─────────────
     Les mots se désignent dans le découpage du SERVEUR (`GET /api/regions/{id}/mots` :
     `rang`, `forme`, `debut`, `fin`) — l'outil n'a pas de jumeau navigateur (G11). Une
     sélection est un ensemble de rangs. */

  function rangs(sel) {
    return [...new Set(Array.isArray(sel) ? sel : [...(sel || [])])]
      .filter((x) => Number.isInteger(x) && x >= 0).sort((a, b) => a - b);
  }

  /* Le passage CONTINU de `a` à `b` (clic-glissé, Maj+clic, Maj+flèches). */
  function plage(a, b) {
    const [d, f] = a <= b ? [a, b] : [b, a];
    const out = [];
    for (let i = d; i <= f; i++) out.push(i);
    return out;
  }

  /* Ctrl+clic : un mot ajouté au passage, ou retiré — « ne … pas ». */
  function basculer(sel, rang) {
    const s = new Set(rangs(sel));
    if (s.has(rang)) s.delete(rang); else s.add(rang);
    return rangs(s);
  }

  /* Le texte d'un passage, ses trous dits « … » : « ne … pas ». `mots` : le découpage. */
  function texteDuPassage(mots, sel) {
    const r = rangs(sel);
    const parRang = new Map((mots || []).map((m) => [m.rang, m.forme]));
    const out = [];
    r.forEach((x, i) => {
      if (i && x !== r[i - 1] + 1) out.push("…");
      out.push(parRang.has(x) ? parRang.get(x) : "?");
    });
    return out.join(" ");
  }

  /* Deux passages identiques ? (même ensemble de rangs, dans n'importe quel ordre) */
  function memesMots(a, b) {
    const x = rangs(a), y = rangs(b);
    return x.length === y.length && x.every((v, i) => v === y[i]);
  }

  /* Les rangs d'un relevé posé sur des mots (ceux de son ancrage). */
  function motsDuReleve(r) {
    return rangs(((r && r.mots) || []).map((m) => m.rang));
  }

  /* LES COULOIRS des traits sous les mots : un relevé garde la même hauteur d'un bout à
     l'autre de son passage, et deux passages qui se chevauchent (même par un trou) ne
     partagent pas un couloir. Rend `Map(id → n°)`, 0 le plus haut. Les plus longs d'abord
     à début égal, comme la maquette. */
  function couloirs(releves) {
    const l = (Array.isArray(releves) ? releves : [])
      .map((r) => ({ r, m: motsDuReleve(r) })).filter((x) => x.m.length)
      .map((x) => ({ id: x.r.id, a: x.m[0], b: x.m[x.m.length - 1] }))
      .sort((x, y) => x.a - y.a || (y.b - y.a) - (x.b - x.a) || x.id - y.id);
    const fins = [];
    const out = new Map();
    for (const x of l) {
      let n = fins.findIndex((f) => f < x.a);
      if (n < 0) { n = fins.length; fins.push(x.b); } else fins[n] = x.b;
      out.set(x.id, n);
    }
    return out;
  }

  /* LA TEINTE d'un relevé : le rang de la rubrique de TÊTE de son entrée parmi celles du
     plan, dans une palette de `n` jetons (les accents du thème). `null` pour une entrée
     sans rubrique ou absente : un trait gris. */
  function teinte(plan, entreeCle, n) {
    const e = ((plan && plan.entrees) || []).find((x) => x.cle === entreeCle);
    if (!e || !(e.rubriques || []).length) return null;
    const tete = ((plan && plan.rubriques) || []).filter((r) => r.parent_cle === null
      || r.parent_cle === undefined).map((r) => r.cle);
    const i = tete.indexOf(e.rubriques[0]);
    return i < 0 ? null : i % (n || 7);
  }

  /* « PORTE SUR » : ce que la grille ouverte vise depuis la zone choisie — des mots d'une
     zone de texte, la zone entière, la case, la planche. Rend `[{ cle, libelle }]`, dans cet
     ordre. L'entité (« X, partout ») n'est pas offerte : le serveur la refuse jusqu'à
     l'étage de projet des personnages (G3). */
  function optionsPorteSur(plan, zone, caseRegion) {
    const entrees = ((plan && plan.entrees) || []).filter((e) => !e.retiree);
    const out = [];
    const texte = !!zone && !zone.pseudo && estTexte(zone.type);
    const sur = (type) => entrees.some((e) => e.pose === "zone" && (e.cibles || []).includes(type));
    if (texte && entrees.some((e) => e.pose === "mots")) out.push({ cle: "mots", libelle: "des mots" });
    if (zone && !zone.pseudo && zone.type !== "case" && sur(zone.type)) {
      out.push({ cle: "zone", libelle: `toute ${zone.type === "personnage" ? "la boîte"
        : MASCULINS.has(zone.type) ? "le " + nomType(zone.type) : "la " + nomType(zone.type)}` });
    }
    if (caseRegion && !caseRegion.pseudo && sur("case")) out.push({ cle: "case", libelle: "la case" });
    if (entrees.some((e) => e.pose === "planche")) out.push({ cle: "planche", libelle: "la planche" });
    return out;
  }

  /* LA CIBLE qu'un geste pose pour une entrée : `{ region_id }` (avec `mots` pour des mots)
     ou `{ planche_id }`, ou `{ erreur }` en mots. `ctx` : `{ porte, zone, caseRegion,
     plancheId, mots }` — `mots` la sélection. Une entrée qui déclare SA cible s'y pose
     d'elle-même (« toute la zone », « la case »), quel que soit « Porte sur » ; une entrée
     de la zone suit « Porte sur » entre la zone et sa case. */
  function cibleDePose(entree, ctx) {
    const c = ctx || {};
    const zone = c.zone, laCase = c.caseRegion;
    if (!entree) return { erreur: "Entrée inconnue." };
    if (entree.pose === "planche") return { planche_id: c.plancheId };
    if (entree.pose === "entite") {
      return { erreur: "Cette entrée vise le personnage partout : elle ne se pose pas encore." };
    }
    if (entree.pose === "mots") {
      if (!zone || zone.pseudo || !estTexte(zone.type)) {
        return { erreur: `« ${entree.libelle} » se pose sur des mots : choisissez une bulle, un cartouche ou un texte.` };
      }
      const m = rangs(c.mots);
      if (!m.length) return { erreur: `« ${entree.libelle} » se pose sur des mots : désignez-en au moins un.` };
      return { region_id: zone.id, mots: m };
    }
    if (entree.pose !== "zone") return { erreur: "Cette entrée ne dit pas sur quoi elle se pose." };
    const cibles = entree.cibles || [];
    const candidats = [];
    if (c.porte === "case") candidats.push(laCase, zone);
    else candidats.push(zone, laCase);
    const r = candidats.find((x) => x && !x.pseudo && cibles.includes(x.type));
    if (!r) {
      return { erreur: `« ${entree.libelle} » se pose sur : ${cibles.map(nomType).join(", ")} — choisissez-en une dans la case.` };
    }
    return { region_id: r.id };
  }

  /* Les relevés d'une entrée sur CETTE cible (la même région ou la planche ; pour des mots,
     le même passage). */
  function relevesSurLaCible(releves, grilleId, entreeCle, cible) {
    if (!cible || cible.erreur) return [];
    return (Array.isArray(releves) ? releves : []).filter((r) => r.grille_id === grilleId
      && r.entree_cle === entreeCle
      && (cible.planche_id !== undefined
        ? r.planche_id === cible.planche_id && r.region_id === null
        : r.region_id === cible.region_id
          && (cible.mots ? memesMots(motsDuReleve(r), cible.mots) : !motsDuReleve(r).length)));
  }

  /* Ce que l'écran MONTRE d'un relevé qu'on retire : si un autre l'a changé depuis, le
     retrait reçoit le 409 de CONC-3 (`DELETE /api/releves/{id}` avec `vu`). */
  function vuDuReleve(x) {
    return { variante_cle: x.variante_cle || null,
             qualificatifs: [...(x.qualificatifs || [])].sort(),
             ...(motsDuReleve(x).length ? { mots: motsDuReleve(x) } : {}) };
  }

  /* L'entrée qui NAÎT en la posant dans une grille ouverte (G14) : simple, sans rubrique,
     sur la cible de la version — pour savoir où la poser avant qu'elle existe. */
  function entreeNeuve(plan, libelle) {
    const cibles = (plan && plan.porte_sur) || [];
    const pose = cibles.includes("mots") ? "mots" : cibles.includes("planche") ? "planche"
      : cibles.includes("entite") ? "entite" : "zone";
    return { cle: null, libelle, forme: "simple", cibles, pose, cardinalite: "plusieurs",
             cible_declaree: [], rubriques: [], variantes: [] };
  }

  /* LE GESTE d'un clic dans la grille, sur une entrée (`choix` vide), une variante
     (`{ variante }`) ou un qualificatif (`{ qualificatif }`), selon ce qui est déjà posé sur
     la cible. Cocher pose, recocher sur le même passage retire ; une autre variante
     REMPLACE (en place, avec `vu`) ; un qualificatif s'ajoute ou s'ôte (UN ensemble). Une
     entrée « plusieurs » sur une cible entière ajoute un relevé à chaque clic (on en retire
     un dans la liste). Rend `{ action: "poser", corps }`, `{ action: "retirer", releve, vu }`
     ou `{ action: "modifier", releve, corps, vu }`. */
  function geste(entree, existants, choix) {
    const ch = choix || {};
    const r = (existants || [])[0] || null;
    const vu = vuDuReleve;
    if (entree.forme === "variantes") {
      if (!ch.variante) return r ? { action: "retirer", releve: r, vu: vu(r) } : null;
      if (!r) return { action: "poser", corps: { variante_cle: ch.variante } };
      if (r.variante_cle === ch.variante) return { action: "retirer", releve: r, vu: vu(r) };
      return { action: "modifier", releve: r, corps: { variante_cle: ch.variante },
               vu: { variante_cle: r.variante_cle || null } };
    }
    if (entree.forme === "qualificatifs" && ch.qualificatif) {
      if (!r) return { action: "poser", corps: { qualificatifs: [ch.qualificatif] } };
      const q = [...(r.qualificatifs || [])].sort();
      const neuf = q.includes(ch.qualificatif) ? q.filter((x) => x !== ch.qualificatif)
        : [...q, ch.qualificatif].sort();
      return { action: "modifier", releve: r, corps: { qualificatifs: neuf },
               vu: { qualificatifs: q } };
    }
    if (r && !marquePlusieurs(entree)) return { action: "retirer", releve: r, vu: vu(r) };
    return { action: "poser", corps: entree.forme === "qualificatifs" ? { qualificatifs: [] } : {} };
  }

  /* Le LIBELLÉ d'un relevé : l'entrée, sa variante ou ses qualificatifs, sa précision —
     « onomatopée de choc · bang », « origine du son · objet, hors champ — « le salon » ». */
  function libelleReleve(r, plan) {
    const e = ((plan && plan.entrees) || []).find((x) => x.cle === r.entree_cle);
    if (!e) return r.entree_cle;
    let t = e.libelle;
    if (r.variante_cle) {
      const v = (e.variantes || []).find((x) => x.cle === r.variante_cle);
      t += ` · ${v ? v.libelle : r.variante_cle}`;
    }
    if ((r.qualificatifs || []).length) {
      const l = ((plan && plan.listes) || []).find((x) => x.cle === e.liste_cle);
      const nom = (q) => { const x = l && l.qualificatifs.find((y) => y.cle === q); return x ? x.libelle : q; };
      t += ` · ${r.qualificatifs.map(nom).join(", ")}`;
    }
    if (r.precision) t += ` — « ${r.precision} »`;
    return t;
  }

  /* Ce que dit l'état d'un relevé, en mots courts (un badge). */
  function motEtat(r) {
    return r && r.etat === "a_revoir" ? "à revoir" : r && r.etat === "a_completer" ? "à compléter" : "";
  }

  /* LA LISTE de ce qui est posé, en bas de la colonne : sur les mots désignés (ceux qui
     les touchent), sinon sur toute la zone (ses mots, la zone entière) et sa case ; pour
     une zone qui n'a pas de mots, sur elle ; pour la case pseudo, la planche. Rangée par
     début de passage, puis par identifiant. */
  function listeSurLaZone(releves, zone, caseRegion, plancheId, sel) {
    const l = Array.isArray(releves) ? releves : [];
    if (!zone) return [];
    if (zone.pseudo) return l.filter((r) => r.planche_id === plancheId && r.region_id === null);
    const s = rangs(sel);
    let out;
    if (s.length && estTexte(zone.type)) {
      out = l.filter((r) => r.region_id === zone.id && motsDuReleve(r).some((x) => s.includes(x)));
    } else {
      const laCase = caseRegion && !caseRegion.pseudo && caseRegion.id !== zone.id ? caseRegion.id : null;
      out = l.filter((r) => r.region_id === zone.id || (laCase !== null && r.region_id === laCase));
    }
    const debut = (r) => { const m = motsDuReleve(r); return m.length ? m[0] : Infinity; };
    return out.slice().sort((a, b) => debut(a) - debut(b) || a.id - b.id);
  }

  /* « RELEVÉS : ▾ » — quelles grilles montrent leurs relevés dans la liste et sous les
     mots. Par défaut la grille ouverte seule ; retenu par PERSONNE et par PROJET, dans le
     stockage local (clé `bd-annotation-releves`, un objet `{ "login|projet": [ids] }`, le
     patron de `bd-bacs-a-sable`), sous try/catch : sans stockage, le choix vaut pour la
     page. La grille ouverte est toujours montrée. */
  const CLE_RELEVES = "bd-annotation-releves";

  function cleReglage(login, projetId) {
    return `${login || "-"}|${projetId === null || projetId === undefined ? "-" : projetId}`;
  }

  function lireReglage(stockage, login, projetId) {
    try {
      const brut = stockage ? stockage.getItem(CLE_RELEVES) : null;
      const tout = brut ? JSON.parse(brut) : {};
      const v = tout && typeof tout === "object" ? tout[cleReglage(login, projetId)] : null;
      return Array.isArray(v) ? v.filter((x) => Number.isInteger(x)) : null;
    } catch (e) { return null; }
  }

  function retenirReglage(stockage, login, projetId, ids) {
    try {
      if (!stockage) return false;
      const brut = stockage.getItem(CLE_RELEVES);
      const tout = brut ? JSON.parse(brut) : {};
      const objet = tout && typeof tout === "object" && !Array.isArray(tout) ? tout : {};
      objet[cleReglage(login, projetId)] = rangs(ids);
      stockage.setItem(CLE_RELEVES, JSON.stringify(objet));
      return true;
    } catch (e) { return false; }
  }

  /* Les grilles dont on montre les relevés : le réglage retenu, parmi les actives, plus la
     grille ouverte. */
  function grillesMontrees(reglage, actives, ouverte) {
    const ids = new Set((Array.isArray(actives) ? actives : []).map((g) => g.id));
    const out = new Set((reglage || []).filter((x) => ids.has(x)));
    if (ouverte !== null && ouverte !== undefined) out.add(ouverte);
    return out;
  }

  /* LE BANDEAU de la cardinalité (un second relevé d'une entrée « une ») : le relevé déjà
     là, et ce que « Remplacer par la mienne » enverrait — un `PUT` de CE relevé avec `vu`
     égal à ce qu'il porte. `null` si le refus n'est pas celui-là. */
  function remplacementCardinalite(detail, corps) {
    const ex = detail && detail.releve_existant;
    if (!ex) return null;
    const changer = {};
    const vu = {};
    if (corps && corps.variante_cle !== undefined) {
      changer.variante_cle = corps.variante_cle;
      vu.variante_cle = ex.variante_cle || null;
    }
    if (corps && corps.qualificatifs !== undefined) {
      changer.qualificatifs = corps.qualificatifs;
      vu.qualificatifs = [...(ex.qualificatifs || [])].sort();
    }
    return { releve_id: ex.id, corps: { ...changer, vu }, auteur: ex.auteur_nom || ex.auteur || null };
  }

  /* « Créer « … » » dans une grille OUVERTE (G14) : le libellé à créer, si la requête ne
     nomme exactement aucun résultat ; `null` sinon, et toujours pour une grille fermée. */
  function creerDansLeFiltre(grille, requete, resultats) {
    const t = String(requete || "").trim();
    if (!grille || !grille.ouverte || !t) return null;
    const n = normaliser(t);
    return (resultats || []).some((r) => normaliser(r.libelle) === n) ? null : t;
  }

  return { TYPES_TEXTE, CLES_ADRESSE, CLE_RELEVES, estTexte, nomType, deLa, casesDeLaPlanche,
           etiquette, etiquettesDeLaCase, situer, libellePlanche, preparation, adresse,
           lireAdresse, lienAtelier, echelle, taillePourEcran, recadrage, dansLaCase, contexte,
           normaliser, masquee, grillesVisibles, grilleAOuvrir, infobulleGrille, arbre,
           entreesSous, chemin, vuesAfficher, relevesDeLaZone, compter, marquePlusieurs,
           marqueCible, chercher, ligneDuGuide, guideComplet,
           rangs, plage, basculer, texteDuPassage, memesMots, motsDuReleve, couloirs, teinte,
           optionsPorteSur, cibleDePose, relevesSurLaCible, geste, libelleReleve, motEtat,
           listeSurLaZone, lireReglage, retenirReglage, grillesMontrees,
           remplacementCardinalite, creerDansLeFiltre, vuDuReleve, entreeNeuve };

});
