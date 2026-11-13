/* Les RELEVÉS dans la Recherche, et le filtre « porte… » (ANN-7, le mode libre ; J7, élargi
   par Hugo le 2026-11-06 ; tranché sur maquette le même jour) — la RÈGLE, pas le rendu de la
   page. Chargé en <script> AVANT recherche.js → expose `window.BDPorte` ; aussi require()-able
   par les tests Node (UMD minimal, pas de build). Aucun accès au document.

   Ce que le serveur rend (`GET /api/recherche`, `routes/recherche.py`) : chaque résultat
   porte `releves`, ceux de sa zone, de toutes les grilles — `grille`, `travail`, `entree`,
   `variante`, `qualificatifs` (chacun avec son libellé et, s'il a une liste, son `porte`) —
   et `porte`, la valeur du filtre qui l'isole. Le filtre `porte=` est répétable : deux
   filtres se combinent par « et ». Ce module :
     · met les relevés d'un résultat EN LIGNE : « Mode libre : silence, sentiment : surprise
       · Sons et paroles : ton de voix : crié » — la grille de travail d'abord, appelée
       « Mode libre », les autres par leur nom ; chaque relevé est un bouton qui l'isole ;
     · surligne le mot cherché, dans le texte comme dans une étiquette, sans égard aux
       accents ni à la casse (la règle de l'index : `remove_diacritics 2`) ;
     · dit une zone sans texte (« Case c3, sans texte ») ;
     · compose la liste « Porte… » à partir du PLAN des grilles actives du projet, et nomme
       un filtre posé (les puces au-dessus des résultats) ;
     · lit et compose les filtres de l'adresse.
   Il ne valide rien : la forme d'une valeur de `porte` et le droit de lire sa grille sont au
   serveur (422 nommé, 404). */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDPorte = api;                                                    // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Le nom que la Recherche donne à la grille de travail d'un projet (passation de la
     maquette, point 10). Son nom en base reste le sien (« Travail en cours », renommable). */
  const MODE_LIBRE = "Mode libre";

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  /* ───────────── Surligner ───────────── */
  /* Une lettre ramenée à sa forme cherchée : sans accent, en minuscule. */
  function plier(c) {
    return c.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }

  /* Le texte échappé, chaque occurrence d'un terme de `q` dans un <mark>. Un terme se
     reconnaît sans égard aux accents ni à la casse — « foret » surligne « forêt », comme
     l'index le trouve — et n'importe où dans un mot (la règle d'avant, qui surlignait
     « pouv » dans « pouvoir »). Les termes les plus longs d'abord, sans chevauchement. */
  function surligner(texte, q) {
    const t = String(texte ?? "");
    const termes = [...new Set(String(q ?? "").trim().split(/\s+/)
      .map((x) => [...x].map(plier).join("")).filter(Boolean))]
      .sort((a, b) => b.length - a.length);
    if (!termes.length || !t) return esc(t);
    // Le texte plié, lettre à lettre, et pour chacune la lettre d'origine dont elle vient
    // (« æ » ne change pas de longueur, « ŉ » en prend deux : la table les suit).
    const lettres = [...t];
    const unites = [], origine = [];
    lettres.forEach((c, i) => {
      for (const p of plier(c)) { unites.push(p); origine.push(i); }
    });
    const marque = new Array(lettres.length).fill(false);
    for (const terme of termes) {
      const u = [...terme];
      for (let i = 0; i + u.length <= unites.length; i++) {
        let ok = true;
        for (let k = 0; k < u.length && ok; k++) ok = unites[i + k] === u[k];
        if (!ok) continue;
        const debut = origine[i], fin = origine[i + u.length - 1];
        let libre = true;
        for (let j = debut; j <= fin && libre; j++) libre = !marque[j];
        if (!libre) continue;
        for (let j = debut; j <= fin; j++) marque[j] = true;
        i += u.length - 1;
      }
    }
    let sortie = "", dedans = false;
    lettres.forEach((c, i) => {
      if (marque[i] && !dedans) { sortie += "<mark>"; dedans = true; }
      if (!marque[i] && dedans) { sortie += "</mark>"; dedans = false; }
      sortie += esc(c);
    });
    return dedans ? sortie + "</mark>" : sortie;
  }

  /* ───────────── Les relevés d'un résultat ───────────── */
  function nomDeGrille(g) {
    return g && g.travail ? MODE_LIBRE : String((g && (g.grille ?? g.nom)) ?? "");
  }

  /* Les relevés rangés par grille : la grille de travail d'abord, puis les autres par leur
     nom (à la française), puis par identifiant ; dans une grille, l'ordre reçu. Le serveur
     rend déjà cet ordre : l'écran ne s'y fie pas. */
  function grouperReleves(releves) {
    const parGrille = new Map();
    for (const r of Array.isArray(releves) ? releves : []) {
      if (!parGrille.has(r.grille_id)) {
        parGrille.set(r.grille_id, { grille_id: r.grille_id, nom: nomDeGrille(r),
                                     travail: !!r.travail, releves: [] });
      }
      parGrille.get(r.grille_id).releves.push(r);
    }
    return [...parGrille.values()].sort((a, b) =>
      (a.travail === b.travail ? 0 : a.travail ? -1 : 1)
      || a.nom.localeCompare(b.nom, "fr", { sensitivity: "base" })
      || (a.grille_id - b.grille_id));
  }

  /* « entrée » ou « entrée : variante ». */
  function libelleReleve(r) {
    return r.variante ? `${r.entree} : ${r.variante}` : String(r.entree ?? "");
  }

  function boutonIsoler(porte, libelleHtml, libelleBrut) {
    return `<button type="button" class="r-releve" data-porte="${esc(porte)}"`
      + ` title="Isoler les zones qui portent « ${esc(libelleBrut)} »">${libelleHtml}</button>`;
  }

  /* La ligne des relevés d'un résultat, en HTML — vide sans relevé. Le nom de chaque grille
     en encre discrète, suivi de « : » ; les relevés d'une grille séparés par des virgules,
     les grilles par « · » ; le mot cherché surligné. Les qualificatifs d'un relevé suivent
     son entrée entre parenthèses, chacun isolable s'il a son `porte`. */
  function ligneReleves(releves, q) {
    const groupes = grouperReleves(releves);
    if (!groupes.length) return "";
    return groupes.map((g) => {
      const items = g.releves.map((r) => {
        const lib = libelleReleve(r);
        let html = boutonIsoler(r.porte, surligner(lib, q), lib);
        const quals = (r.qualificatifs || []).map((x) => (x.porte
          ? boutonIsoler(x.porte, surligner(x.libelle, q), x.libelle)
          : `<span class="r-qualif">${surligner(x.libelle, q)}</span>`));
        if (quals.length) html += ` (${quals.join(", ")})`;
        return html;
      });
      return `<span class="r-gr">${esc(g.nom)} :</span> ${items.join(", ")}`;
    }).join(` <span class="r-sep" aria-hidden="true">·</span> `);
  }

  /* ───────────── Une zone sans texte ───────────── */
  const TYPES = { case: "Case", bulle: "Bulle", cartouche: "Cartouche", texte: "Texte",
                  personnage: "Personnage", detail: "Détail" };

  /* « Case c3, sans texte » : le type, puis le repère de la zone dans sa planche (la
     citation sans son « pl.N · »), puis « sans texte ». Un repère qui ne dit que la planche,
     ou une planche de paratexte, n'en laisse aucun. */
  function sansTexte(r) {
    const type = TYPES[r && r.type] || String((r && r.type) ?? "Zone");
    const cite = r && r.citation && r.citation.planche != null ? String(r.citation.texte || "")
      : "";
    const repere = cite.replace(/^pl\.[^·]*·\s*/, "").replace(/^pl\.\S*$/, "").trim();
    return `${type}${repere ? " " + repere : ""}, sans texte`;
  }

  /* ───────────── Le filtre « porte… » ───────────── */
  /* Une valeur de `porte`, lue — `{grille_id, sorte, parent, valeurs}` —, ou `null` : la
     même lecture que le serveur (`routes/recherche._lire_porte`), pour NOMMER un filtre ;
     le serveur seul la refuse. */
  function lirePorte(valeur) {
    const parts = String(valeur ?? "").split("/").map((p) => p.trim());
    if (parts.length < 3 || !/^\d+$/.test(parts[0])
        || !["entree", "variante", "rubrique", "qualificatif"].includes(parts[1])
        || parts.slice(2).some((p) => !p)) return null;
    const sorte = parts[1];
    let valeurs = parts.slice(2), parent = null;
    if (sorte === "variante" || sorte === "qualificatif") {
      if (valeurs.length < 2) return null;
      parent = valeurs[0];
      valeurs = valeurs.slice(1);
    }
    return { grille_id: Number(parts[0]), sorte, parent, valeurs };
  }

  /* Les grilles dans l'ordre de la liste : la grille de travail d'abord, puis par nom. */
  function ordonnerGrilles(grilles) {
    return (Array.isArray(grilles) ? grilles : []).slice().sort((a, b) =>
      (!!a.travail === !!b.travail ? 0 : a.travail ? -1 : 1)
      || String(a.nom ?? "").localeCompare(String(b.nom ?? ""), "fr", { sensitivity: "base" })
      || (a.id - b.id));
  }

  const RETRAIT = "   ";

  /* Les groupes de la liste « Porte… », en DONNÉES : `[{grille_id, nom, options:
     [{valeur, texte, profondeur}]}]`. `grilles` : les grilles actives du projet, chacune avec
     son `plan` (`GET /api/grilles/{id}/versions/{n}`) ; une grille sans plan lu n'y est pas.
     Dans une grille : les entrées sans rubrique, puis chaque rubrique (« Rubrique : … ») et
     ses entrées, ses sous-rubriques en retrait ; sous chaque entrée, ses variantes
     (« entrée : variante »). Une entrée retirée le dit. Les qualificatifs ne s'y choisissent
     pas : un clic sur un qualificatif d'un résultat les isole. */
  function optionsPorte(grilles) {
    const groupes = [];
    for (const g of ordonnerGrilles(grilles)) {
      const plan = g && g.plan;
      if (!plan || !Array.isArray(plan.entrees)) continue;
      const options = [];
      const rubriques = Array.isArray(plan.rubriques) ? plan.rubriques : [];
      const connues = new Set(rubriques.map((r) => r.cle));
      const pousserEntree = (e, prof) => {
        const lib = String(e.libelle ?? e.cle) + (e.retiree ? " (retirée)" : "");
        options.push({ valeur: `${g.id}/entree/${e.cle}`, texte: RETRAIT.repeat(prof) + lib,
                       profondeur: prof });
        for (const v of e.variantes || []) {
          options.push({ valeur: `${g.id}/variante/${e.cle}/${v.cle}`,
                         texte: RETRAIT.repeat(prof + 1) + `${e.libelle ?? e.cle} : ${v.libelle ?? v.cle}`,
                         profondeur: prof + 1 });
        }
      };
      for (const e of plan.entrees) {
        if (!e.rubrique_cle || !connues.has(e.rubrique_cle)) pousserEntree(e, 0);
      }
      const enfants = new Map();
      for (const r of rubriques) {
        const p = r.parent_cle && connues.has(r.parent_cle) ? r.parent_cle : null;
        if (!enfants.has(p)) enfants.set(p, []);
        enfants.get(p).push(r);
      }
      const vus = new Set();
      const descendre = (parent, prof) => {
        for (const r of enfants.get(parent) || []) {
          if (vus.has(r.cle)) continue;
          vus.add(r.cle);
          options.push({ valeur: `${g.id}/rubrique/${r.cle}`,
                         texte: RETRAIT.repeat(prof) + `Rubrique : ${r.libelle ?? r.cle}`,
                         profondeur: prof });
          for (const e of plan.entrees) if (e.rubrique_cle === r.cle) pousserEntree(e, prof + 1);
          descendre(r.cle, prof + 1);
        }
      };
      descendre(null, 0);
      if (options.length) groupes.push({ grille_id: g.id, nom: nomDeGrille(g), options });
    }
    return groupes;
  }

  /* Le DICTIONNAIRE des filtres nommables : `Map(valeur → {grille, libelle})`, tiré du plan
     des grilles (entrées, variantes, rubriques, qualificatifs de leurs listes). `apprendre`
     y ajoute ce que les résultats ont rendu — un filtre d'une grille d'un autre projet, ou
     qui n'est plus active, se nomme encore. */
  function dictionnaire(grilles) {
    const dico = new Map();
    dico.grilles = new Map();
    for (const g of Array.isArray(grilles) ? grilles : []) {
      const nom = nomDeGrille(g);
      dico.grilles.set(g.id, nom);
      const plan = g && g.plan;
      if (!plan) continue;
      for (const e of plan.entrees || []) {
        dico.set(`${g.id}/entree/${e.cle}`, { grille: nom, libelle: String(e.libelle ?? e.cle) });
        for (const v of e.variantes || []) {
          dico.set(`${g.id}/variante/${e.cle}/${v.cle}`,
                   { grille: nom, libelle: `${e.libelle ?? e.cle} : ${v.libelle ?? v.cle}` });
        }
      }
      for (const r of plan.rubriques || []) {
        dico.set(`${g.id}/rubrique/${r.cle}`, { grille: nom,
                                                libelle: `rubrique ${r.libelle ?? r.cle}` });
      }
      for (const l of plan.listes || []) {
        for (const q of l.qualificatifs || []) {
          dico.set(`${g.id}/qualificatif/${l.cle}/${q.cle}`,
                   { grille: nom, libelle: `${l.libelle ?? l.cle} : ${q.libelle ?? q.cle}` });
        }
      }
    }
    return dico;
  }

  function apprendre(dico, releves) {
    if (!dico.grilles) dico.grilles = new Map();
    for (const r of Array.isArray(releves) ? releves : []) {
      const nom = nomDeGrille(r);
      if (!dico.grilles.has(r.grille_id)) dico.grilles.set(r.grille_id, nom);
      if (r.porte && !dico.has(r.porte)) dico.set(r.porte, { grille: nom, libelle: libelleReleve(r) });
      for (const q of r.qualificatifs || []) {
        if (q.porte && !dico.has(q.porte)) dico.set(q.porte, { grille: nom, libelle: String(q.libelle) });
      }
    }
    return dico;
  }

  /* Le nom d'un filtre posé, pour sa puce : `{grille, libelle}`. Une valeur à plusieurs
     valeurs (« ou », écrite à la main dans l'adresse) nomme chacune ; ce que le dictionnaire
     ne connaît pas se dit par sa clé, la grille par son numéro. */
  function libellePorte(valeur, dico) {
    const d = dico || new Map();
    if (d.has(valeur)) return d.get(valeur);
    const f = lirePorte(valeur);
    if (!f) return { grille: "", libelle: String(valeur ?? "") };
    const grille = (d.grilles && d.grilles.get(f.grille_id)) || `Grille ${f.grille_id}`;
    const prefixe = `${f.grille_id}/${f.sorte}/` + (f.parent !== null ? `${f.parent}/` : "");
    const noms = f.valeurs.map((v) => {
      const connu = d.get(prefixe + v);
      if (connu) return connu.libelle;
      if (f.sorte === "variante") return `${f.parent} : ${v}`;
      if (f.sorte === "rubrique") return `rubrique ${v}`;
      return v;
    });
    return { grille, libelle: noms.join(" ou ") };
  }

  /* ───────────── Les filtres de l'adresse ───────────── */
  /* Les valeurs de `porte` d'une adresse (une chaîne de requête, ou des URLSearchParams),
     dans leur ordre, sans doublon ni valeur vide. */
  function portesDe(qs) {
    const p = qs instanceof URLSearchParams ? qs : new URLSearchParams(String(qs ?? ""));
    return [...new Set(p.getAll("porte").map((v) => v.trim()).filter(Boolean))];
  }

  function ajouterPorte(portes, valeur) {
    const v = String(valeur ?? "").trim();
    return !v || portes.includes(v) ? portes.slice() : [...portes, v];
  }

  function retirerPorte(portes, valeur) {
    return portes.filter((v) => v !== valeur);
  }

  /* Ajoute les filtres à des paramètres de requête (répétés, dans leur ordre). */
  function avecPortes(params, portes) {
    for (const v of portes || []) params.append("porte", v);
    return params;
  }

  return { MODE_LIBRE, surligner, nomDeGrille, grouperReleves, libelleReleve, ligneReleves,
           sansTexte, lirePorte, ordonnerGrilles, optionsPorte, dictionnaire, apprendre,
           libellePorte, portesDe, ajouterPorte, retirerPorte, avecPortes };
});
