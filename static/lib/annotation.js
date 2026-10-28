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
   Les règles de la grille, de la pose, du parcours et du décompte s'y ajouteront aux
   commits suivants, au même endroit.

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

  /* L'ADRESSE de la page : `?collection=&album=&planche=&region=`, la forme de l'Atelier
     plus la collection (la grille s'y ajoutera). Ce qui est nul n'y est pas. */
  const CLES_ADRESSE = ["collection", "album", "planche", "region"];

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

  return { TYPES_TEXTE, CLES_ADRESSE, estTexte, nomType, deLa, casesDeLaPlanche, etiquette,
           etiquettesDeLaCase, situer, libellePlanche, preparation, adresse, lireAdresse,
           lienAtelier, echelle, taillePourEcran, recadrage, dansLaCase, contexte };
});
