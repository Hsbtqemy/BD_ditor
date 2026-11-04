/* Le FORMULAIRE de construction d'une grille (Administration › Projets › Grilles) — logique
   PURE, sans DOM (ANN-7 ; l'option HYBRIDE tranchée par Hugo sur maquette le 2026-11-03 : un
   formulaire pour construire, le tableur pour retoucher en nombre).

   Chargé en <script> APRÈS `grilles-projet.js` et AVANT administration.js → expose
   `window.BDGrilleFormulaire` ; aussi require()-able par `tests/js/grille-formulaire.test.js`.
   Rien n'est lu au chargement : ni le document, ni l'adresse, ni le stockage — si le
   formulaire a un jour un second public, il deviendra un module montable sans rien défaire.

   Le formulaire écrit par les routes de `routes/grilles.py`, un geste à la fois, chacun avec
   la valeur qu'il voyait (CONC-3). Ce qui se décide ICI, et rien d'autre :

   1. LES RÉPONSES aux six questions du catalogue (`docs/ce-qu-une-grille-peut-demander.md`),
      lues dans le plan que rend le serveur (`grilles.plan`), et ce qu'une réponse ENVOIE ;
   2. CE QUI ATTEND : une réponse que le serveur refuserait encore — « une variante » sans
      variante, « des cases d'une liste » sans liste, une zone sans sorte, un champ sans nom.
      Le formulaire la garde chez lui (choix 2 du 2026-11-04 : « le formulaire garde chez lui
      une entrée à compléter jusqu'à sa première variante ») et la marque ● ; rien ne part.
      C'est ainsi qu'il REND IMPOSSIBLES les fautes de structure au lieu de les refuser ;
   3. CE QUI S'OFFRE sur un objet, selon ce que les relevés emploient (`emplois`, que le
      serveur rend avec le plan) : une entrée employée se RETIRE — ou, sur une grille ouverte,
      se FUSIONNE —, jamais ne se SUPPRIME (tranché par Hugo le 2026-11-03) ; « Fusionner
      dans… » n'est pas offert sur une grille fermée (choix 1 du 2026-11-04) ; une variante ou
      une case employée ne se supprime pas (choix 3). Une offre n'est pas une garde : chaque
      route pose sa question, et l'écran dit son refus ;
   4. L'ORDRE (`PUT …/ordre`) : la place d'un objet parmi ses frères, et l'ordre vu ;
   5. LA FAUTE D'UN IMPORT qui mène à son objet (« Corriger dans le formulaire ↗ »). */
(function (root, factory) {
  const P = typeof module !== "undefined" && module.exports
    ? require("./grilles-projet.js") : root.BDGrillesProjet;
  const api = factory(P);
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDGrilleFormulaire = api;                                         // navigateur
})(typeof self !== "undefined" ? self : this, function (P) {
  "use strict";

  /* L'ordre des cibles en base (`grilles.CIBLES`) : une réponse s'envoie dans cet ordre. */
  const CIBLES = ["mots", "bulle", "cartouche", "texte", "case", "personnage", "detail",
                  "planche", "entite"];
  /* Les sortes d'« une zone entière » que la question 2 coche (le catalogue). « La case » est
     une réponse à elle : une zone qui ne nomme qu'elle se lit « la case ». */
  const ZONES = ["bulle", "cartouche", "texte", "personnage", "detail"];
  const TYPES_TEXTE = ["bulle", "cartouche", "texte"];

  /* Les mots d'une sorte : ceux du tableur (`grille_tableur.CIBLES_MOTS`), recopiés UNE fois
     dans `grilles-projet.js` et mesurés contre lui. */
  const mot = (s) => (P && P.CIBLES_MOTS && P.CIBLES_MOTS[s]) || s;

  const FORMES = {
    simple: { nom: "Rien", phrase: "on la pose, ou non" },
    variantes: { nom: "Une variante parmi plusieurs", phrase: "compte l'entrée et sa variante" },
    qualificatifs: { nom: "Des cases d'une liste",
                     phrase: "zéro, une ou plusieurs ; compte une fois l'entrée" },
  };

  /* Les six questions, leurs titres et leur aide (en infobulle : l'écran ne la dit pas en
     phrases). Le titre est celui du catalogue et du classeur. */
  const QUESTIONS = {
    1: { titre: "Où se range-t-elle ?",
         aide: "Une rubrique du plan, sur autant de niveaux qu'il faut, ou aucune." },
    2: { titre: "Sur quoi se pose-t-elle ?",
         aide: "Des mots se désignent dans UNE zone, voisins ou non. Des mots et une zone ne "
           + "se mêlent pas dans une même entrée." },
    3: { titre: "Combien de fois ?",
         aide: "Sur une même cible. « Une seule » : en choisir une autre remplace la première." },
    4: { titre: "Que choisit-on en la posant ?",
         aide: "Un relevé compte toujours UNE occurrence de l'entrée. Si deux choix doivent "
           + "compter pour deux, écrivez deux entrées, ou une entrée à variantes posée deux fois." },
    5: { titre: "Faut-il écrire quelque chose ?",
         aide: "Un champ libre, un seul par entrée. S'il manque, le relevé s'enregistre "
           + "« à compléter »." },
    6: { titre: "Faut-il désigner une autre zone ?",
         aide: "Après la pose, « Désigner sur la planche » puis un clic sur l'autre zone. "
           + "L'arrivée est une zone entière de la planche ouverte, jamais des mots. Un seul "
           + "lien par relevé." },
  };

  function pluriel(n, singulier, plurielle) {
    return `${n} ${n > 1 ? (plurielle || singulier + "s") : singulier}`;
  }

  function ordonner(sortes) {
    const s = new Set(sortes || []);
    return CIBLES.filter((c) => s.has(c));
  }

  /* --- 1. Les réponses --------------------------------------------------------------- */

  /* Des cibles (une liste de sortes, `cible_declaree` ou `porte_sur`) → la réponse à la
     question 2 : { choix, sortes }. `choix` : « grille » (aucune cible déclarée : comme la
     grille), « mots », « case », « planche », « entite », ou « zone » avec ses sortes. */
  function reponseCible(cibles) {
    const c = ordonner(cibles);
    if (!c.length) return { choix: "grille", sortes: [] };
    if (c.length === 1 && ["mots", "case", "planche", "entite"].includes(c[0])) {
      return { choix: c[0], sortes: [] };
    }
    return { choix: "zone", sortes: c };
  }

  /* Une réponse à la question 2 → les cibles à envoyer (`[]` : comme la grille), ou `null`
     tant qu'elle n'est pas complète (une zone sans sorte). */
  function ciblesDeReponse(rep) {
    if (!rep) return null;
    if (rep.choix === "grille") return [];
    if (rep.choix === "zone") {
      const s = ordonner(rep.sortes);
      return s.length ? s : null;
    }
    return [rep.choix];
  }

  /* Ce sur quoi portent ces cibles, en mots : « des mots », « la case », « bulle, cartouche
     ou texte hors bulle ». */
  function ciblesEnMots(cibles) {
    const c = ordonner(cibles);
    return c.length ? P.porteSurEnMots(c) : "";
  }

  /* La cardinalité DÉCLARÉE → la réponse à la question 3 : « ordinaire », « une »,
     « plusieurs ». */
  function reponseCardinalite(declaree) {
    return declaree === "une" || declaree === "plusieurs" ? declaree : "ordinaire";
  }

  /* Le défaut d'une cible (`grilles.cardinalite_effective`) : plusieurs sur des mots, une
     fois sur une région entière, la planche ou l'entité. */
  function cardinaliteParDefaut(ciblesEffectives) {
    const c = ordonner(ciblesEffectives);
    return c.length === 1 && c[0] === "mots" ? "plusieurs" : "une";
  }

  /* Les réponses MONTRÉES d'une entrée : celles du serveur, et par-dessus ce qui attend
     (`att`, cf. 2). Rend { cible, cardinalite, forme, liste, precision: { oui, nom }, lien }.
     `porteSur` : les cibles de la version. */
  function reponses(e, att, porteSur) {
    const a = att || {};
    const cible = a.cible || reponseCible(e.cible_declaree);
    const effectives = ciblesDeReponse(cible);
    const forme = a.forme || e.forme;
    return {
      cible,
      ciblesEffectives: effectives && effectives.length ? effectives : ordonner(porteSur),
      cardinalite: reponseCardinalite(e.cardinalite_declaree),
      forme,
      liste: forme === "qualificatifs" ? (a.forme ? (a.liste || null) : e.liste_cle) : null,
      precision: a.precision ? { oui: true, nom: "" }
        : e.precision ? { oui: true, nom: e.precision } : { oui: false, nom: "" },
      lien: !!e.lien,
    };
  }

  /* --- 2. Ce qui attend --------------------------------------------------------------- */

  /* Ce qui MANQUE à une entrée pour que le serveur l'accepte telle qu'on la répond : les ●
     du plan et des questions. [{ q, texte }], vide si rien. */
  function manques(e, att, plan) {
    const a = att || {};
    const m = [];
    if (a.cible && a.cible.choix === "zone" && !ordonner(a.cible.sortes).length) {
      m.push({ q: 2, texte: "Cochez au moins une sorte de zone." });
    }
    if (a.forme === "variantes" && !(e.variantes || []).length) {
      m.push({ q: 4, texte: "Ajoutez au moins une variante." });
    }
    if (a.forme === "qualificatifs" && !a.liste) {
      m.push({ q: 4, texte: listesUtilisables(plan).length
        ? "Choisissez la liste où l'on coche."
        : "Aucune liste n'a de case : créez-en une avec « + Liste » dans le plan." });
    }
    if (a.precision) m.push({ q: 5, texte: "Donnez un nom au champ à écrire." });
    return m;
  }

  /* Les listes qu'une entrée peut nommer : celles qui ont au moins une case (`liste_vide`). */
  function listesUtilisables(plan) {
    return ((plan && plan.listes) || []).filter((l) => (l.qualificatifs || []).length);
  }

  /* Le nombre d'entrées à compléter (`attente` : une Map cle → ce qui attend). */
  function aCompleter(plan, attente) {
    let n = 0;
    for (const e of (plan && plan.entrees) || []) {
      if (manques(e, attente && attente.get(e.cle), plan).length) n += 1;
    }
    return n;
  }

  /* Un geste sur une RÉPONSE de l'entrée : rend { envoi, att } — `envoi`, le corps du PATCH
     (null si rien ne part encore), et `att`, ce qui attend désormais. `q` : « cible »,
     « forme », « liste », « precision » (oui/non), « nomPrecision ». */
  function repondre(e, att, q, valeur) {
    const a = { ...(att || {}) };
    const sansAttente = (x) => (Object.keys(x).length ? x : null);
    if (q === "cible") {
      const cibles = ciblesDeReponse(valeur);
      if (cibles === null) { a.cible = { choix: "zone", sortes: [] }; return { envoi: null, att: sansAttente(a) }; }
      delete a.cible;
      const avant = ordonner(e.cible_declaree);
      if (avant.join("|") === cibles.join("|")) return { envoi: null, att: sansAttente(a) };
      return { envoi: { cible: cibles }, att: sansAttente(a) };
    }
    if (q === "forme") {
      delete a.forme; delete a.liste;
      if (valeur === e.forme) return { envoi: null, att: sansAttente(a) };
      if (valeur === "simple") {
        // Quitter « des cases d'une liste » délie la liste sans question ; quitter « une
        // variante » demande d'avoir supprimé les variantes (choix 5) — le refus du serveur.
        return { envoi: { forme: "simple" }, att: sansAttente(a) };
      }
      if (valeur === "variantes" && (e.variantes || []).length) {
        return { envoi: { forme: "variantes" }, att: sansAttente(a) };
      }
      a.forme = valeur;                      // une variante, ou une liste, à venir
      return { envoi: null, att: sansAttente(a) };
    }
    if (q === "liste") {
      if (!valeur) { if (a.forme === "qualificatifs") a.liste = null; return { envoi: null, att: sansAttente(a) }; }
      const enAttente = a.forme === "qualificatifs";
      delete a.forme; delete a.liste;
      if (!enAttente && e.liste_cle === valeur) return { envoi: null, att: sansAttente(a) };
      return { envoi: enAttente ? { forme: "qualificatifs", liste_cle: valeur }
        : { liste_cle: valeur }, att: sansAttente(a) };
    }
    if (q === "precision") {
      if (valeur) {
        if (e.precision) { delete a.precision; return { envoi: null, att: sansAttente(a) }; }
        a.precision = true;
        return { envoi: null, att: sansAttente(a) };
      }
      delete a.precision;
      return { envoi: e.precision ? { precision: null } : null, att: sansAttente(a) };
    }
    if (q === "nomPrecision") {
      const nom = String(valeur || "").trim();
      if (!nom) {
        if (e.precision) return { envoi: null, att: sansAttente(a), refus: "Le champ à écrire garde un nom : répondez « Non » pour qu'il n'y en ait plus." };
        a.precision = true;
        return { envoi: null, att: sansAttente(a) };
      }
      delete a.precision;
      if (nom === e.precision) return { envoi: null, att: sansAttente(a) };
      return { envoi: { precision: nom }, att: sansAttente(a) };
    }
    throw new Error(`question inconnue : ${q}`);
  }

  /* La première variante d'une entrée qui l'ATTEND (« une variante » répondu, aucune encore) :
     la forme et la variante partent ensemble — l'import refuse une entrée à variantes sans
     variante. Ailleurs, une variante de plus. Rend { methode, chemin, corps }. */
  function envoiVariante(grilleId, e, att, libelle) {
    const nom = String(libelle || "").trim();
    if ((att && att.forme === "variantes") || e.forme !== "variantes") {
      return { methode: "PATCH", chemin: `/api/grilles/${grilleId}/entrees/${encodeURIComponent(e.cle)}`,
               corps: { forme: "variantes", variantes: [{ libelle: nom }],
                        vu: { forme: e.forme } } };
    }
    return { methode: "POST",
             chemin: `/api/grilles/${grilleId}/entrees/${encodeURIComponent(e.cle)}/variantes`,
             corps: { libelle: nom } };
  }

  /* --- Les valeurs vues (CONC-3) ------------------------------------------------------ */

  /* La valeur VUE d'un champ d'une entrée, telle que la route la compare : la forme de son
     contenu (`grilles.contenu`), pas celle de l'écran. */
  function vuEntree(e, champ) {
    switch (champ) {
      case "cible": return ordonner(e.cible_declaree);
      case "cardinalite": return e.cardinalite_declaree || null;
      case "exemples": return e.exemples || [];
      case "lien": return !!e.lien;
      default: return e[champ] === undefined ? null : e[champ];
    }
  }

  /* Le corps d'un PATCH : les champs, et `vu` pour chacun d'eux. `vus` : champ → valeur vue. */
  function avecVu(champs, vus) {
    const vu = {};
    for (const c of Object.keys(champs)) if (c in vus) vu[c] = vus[c];
    return { ...champs, vu };
  }

  function corpsEntree(e, champs) {
    const vus = {};
    for (const c of Object.keys(champs)) vus[c] = vuEntree(e, c);
    return avecVu(champs, vus);
  }

  /* Les exemples écrits un par ligne → la liste qui part. Un « | » sépare deux exemples dans
     le tableur : refusé ICI, la saisie gardée (`exemple_separateur`). { exemples, refus }. */
  function exemplesDeTexte(texte) {
    const lignes = String(texte || "").split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
    if (lignes.some((l) => l.includes("|"))) {
      return { exemples: null, refus: "Un exemple ne porte pas de « | » : écrivez chaque "
        + "exemple sur sa ligne." };
    }
    return { exemples: lignes, refus: null };
  }

  function texteDExemples(exemples) {
    return (exemples || []).join("\n");
  }

  /* --- 3. Ce qui s'offre --------------------------------------------------------------- */

  const vide = { entrees: {}, variantes: {}, cases: {}, fusionner_dans: {} };

  /* Une entrée, selon ce que les relevés emploient et la version où l'on écrit (`etat` :
     « vivante » pour une grille ouverte, sinon le brouillon d'une fermée). Rend :
     - `releves` : le nombre de relevés qui la portent, toutes versions confondues ;
     - `supprimer` : vrai seulement si personne ne l'emploie — JAMAIS sur une employée ;
     - `retirer` : sur une employée en usage ; `remettre` : sur une retirée ;
     - `fusionner` : les entrées où la fusionner (une liste, peut-être vide), ou `null` quand
       la fusion ne s'offre pas — personne ne l'emploie, ou la grille est fermée ;
     - `figee` : sa forme et sa liste ne changent pas (une ouverte, sous des relevés : 409),
       avec `raisonFigee`. */
  function offresEntree(e, emplois, etat) {
    const em = emplois || vide;
    const n = (em.entrees || {})[e.cle] || 0;
    const ouverte = etat === "vivante";
    return {
      releves: n,
      supprimer: n === 0,
      retirer: n > 0 && !e.retiree,
      remettre: !!e.retiree,
      fusionner: ouverte && n > 0 ? ((em.fusionner_dans || {})[e.cle] || []) : null,
      figee: ouverte && n > 0,
      raisonFigee: ouverte && n > 0
        ? `${pluriel(n, "relevé la porte", "relevés la portent")} : sa forme et sa liste ne `
          + "changent pas. Pour changer, écrivez une autre entrée et fusionnez-y celle-ci."
        : "",
    };
  }

  /* Les FORMES qu'une entrée peut prendre maintenant, et pourquoi les autres non :
     { simple, variantes, qualificatifs } → `""` (offerte) ou la raison. Sous des relevés,
     sur une grille ouverte, la forme ne change pas (`offresEntree().figee`). Une entrée qui a
     des variantes les garde : la dernière ne se supprime pas (choix 2 du 2026-11-04), et
     quitter « une variante » demande de les avoir supprimées (choix 5) — elle ne change
     donc plus de forme ; on en écrit une autre. */
  function formesPossibles(e, offres) {
    const sortie = { simple: "", variantes: "", qualificatifs: "" };
    for (const f of Object.keys(sortie)) {
      if (f === e.forme) continue;
      if (offres && offres.figee) sortie[f] = offres.raisonFigee;
      else if (e.forme === "variantes" && (e.variantes || []).length) {
        sortie[f] = "Une entrée à variantes garde au moins une variante : elle ne change pas "
          + "de forme. Écrivez une autre entrée.";
      }
    }
    return sortie;
  }

  /* Une variante : elle se supprime si personne ne l'emploie et qu'elle n'est pas la
     dernière de son entrée. { supprimer, raison }. */
  function offresVariante(e, vc, emplois) {
    const n = (((emplois || vide).variantes || {})[e.cle] || {})[vc] || 0;
    if (n) {
      return { supprimer: false, releves: n, raison: `${pluriel(n, "relevé porte", "relevés portent")}`
        + " cette variante : elle ne se supprime pas." };
    }
    if ((e.variantes || []).length <= 1) {
      return { supprimer: false, releves: 0, raison: "La dernière variante d'une entrée à "
        + "variantes ne se supprime pas." };
    }
    return { supprimer: true, releves: 0, raison: "" };
  }

  /* Une case d'une liste : elle se supprime si aucun relevé ne la coche, et qu'elle n'est pas
     la dernière d'une liste qu'une entrée nomme. */
  function offresCase(plan, lc, qc, emplois) {
    const n = ((emplois || vide).cases || {})[qc] || 0;
    const liste = ((plan && plan.listes) || []).find((l) => l.cle === lc);
    const nommee = ((plan && plan.entrees) || []).some((e) => e.liste_cle === lc);
    if (n) {
      return { supprimer: false, releves: n, raison: `${pluriel(n, "relevé coche", "relevés cochent")}`
        + " cette case : elle ne se supprime pas." };
    }
    if (nommee && liste && liste.qualificatifs.length <= 1) {
      return { supprimer: false, releves: 0, raison: "La dernière case d'une liste qu'une "
        + "entrée nomme ne se supprime pas." };
    }
    return { supprimer: true, releves: 0, raison: "" };
  }

  /* Une rubrique ne se supprime que VIDE — ni entrée (retirées comprises), ni rubrique. */
  function offresRubrique(plan, rc) {
    const ne = ((plan && plan.entrees) || []).filter((e) => e.rubrique_cle === rc).length;
    const nr = ((plan && plan.rubriques) || []).filter((r) => r.parent_cle === rc).length;
    const n = ne + nr;
    return { supprimer: n === 0, raison: n ? `Elle range ${pluriel(ne, "entrée")} et `
      + `${pluriel(nr, "rubrique")} : rangez-les ailleurs d'abord.` : "" };
  }

  /* Une liste ne se supprime que si aucune entrée ne la nomme (retirées comprises). */
  function offresListe(plan, lc) {
    const sert = ((plan && plan.entrees) || []).filter((e) => e.liste_cle === lc);
    return { sert: sert.map((e) => e.libelle), supprimer: !sert.length,
             raison: sert.length ? `Elle sert à ${pluriel(sert.length, "entrée")} : elle ne se `
               + "supprime pas." : "" };
  }

  /* Les places où ranger une rubrique : toutes, sauf elle-même et ses descendantes. */
  function placesDeRubrique(plan, rc) {
    const rubriques = (plan && plan.rubriques) || [];
    const exclues = new Set([rc]);
    let ajout = true;
    while (ajout) {
      ajout = false;
      for (const r of rubriques) {
        if (!exclues.has(r.cle) && exclues.has(r.parent_cle)) { exclues.add(r.cle); ajout = true; }
      }
    }
    return rubriques.filter((r) => !exclues.has(r.cle));
  }

  /* Le chemin d'une rubrique, en mots : « Extérieur › En ville ». */
  function cheminDeRubrique(plan, rc) {
    const par = new Map(((plan && plan.rubriques) || []).map((r) => [r.cle, r]));
    const out = [];
    const vus = new Set();
    let r = par.get(rc);
    while (r && !vus.has(r.cle)) {
      vus.add(r.cle);
      out.unshift(r.libelle);
      r = par.get(r.parent_cle);
    }
    return out.join(" › ");
  }

  /* Ce que dit la tête du formulaire : où s'écrit un geste. `g` : la grille telle que
     `_vue_grille` la rend. */
  function ouSEcrit(g) {
    const vs = (g && g.versions) || [];
    const der = (etat) => vs.filter((v) => v.etat === etat).pop() || null;
    if (g && g.ouverte) return { etiquette: "ouverte · s'écrit en place", brouillon: null };
    const b = der("brouillon");
    if (b) return { etiquette: `brouillon v${b.numero}`, brouillon: b.numero };
    const p = der("publiee");
    return { etiquette: p ? `v${p.numero} publiée · un brouillon v${p.numero + 1} naîtra au `
      + "premier changement" : "aucune version", brouillon: null };
  }

  /* La NOTE de version (ce que la version change) : celle de la version où s'écrit un geste
     — la vivante d'une ouverte, le brouillon d'une fermée — ; sur une fermée sans brouillon,
     celle du brouillon qui naîtra au premier changement, vide (il naît sans note). `numero` :
     la version qu'elle décrit ; `vue` : ce que l'écran déclare avoir vu (CONC-3). */
  function noteDeVersion(g) {
    const vs = (g && g.versions) || [];
    const der = (etat) => vs.filter((v) => v.etat === etat).pop() || null;
    const v = g && g.ouverte ? der("vivante") || vs[vs.length - 1] || null : der("brouillon");
    if (v) return { numero: v.numero, vue: v.note || "", naitra: false };
    const p = der("publiee");
    return { numero: p ? p.numero + 1 : 1, vue: "", naitra: true };
  }

  /* La version que le formulaire MONTRE quand rien ne s'écrit encore : la vivante, le
     brouillon, ou la dernière publiée (`routes/grilles._version_montree`). */
  function versionMontree(g) {
    const vs = (g && g.versions) || [];
    const der = (etat) => vs.filter((v) => v.etat === etat).pop() || null;
    const v = der("vivante") || der("brouillon") || der("publiee");
    return v ? v.numero : null;
  }

  /* « Publier… » (fermée) ou « Activer dans le projet » (ouverte) : { ok, raison }. Une
     entrée à compléter les éteint — ce qui attend n'est pas écrit, et la version partirait
     sans lui —, une grille vide aussi. */
  function publiable(plan, attente) {
    const n = aCompleter(plan, attente);
    if (n) {
      return { ok: false, raison: `${pluriel(n, "entrée")} à compléter, marquée${n > 1 ? "s" : ""}`
        + " ● dans le plan." };
    }
    if (!((plan && plan.entrees) || []).some((e) => !e.retiree)) {
      return { ok: false, raison: "La grille n'a aucune entrée en usage." };
    }
    return { ok: true, raison: "" };
  }

  /* --- Le plan, colonne de gauche ---------------------------------------------------- */

  /* Les lignes du plan, dans l'ordre où le formulaire les montre : « Toute la grille », chaque
     rubrique suivie de ses entrées puis de ses sous-rubriques, « Hors rubrique », puis les
     listes à cocher. [{ t, cle, libelle, profondeur, etat, alerte, retiree }] ; une ligne
     `t: "sep"` ouvre un groupe. */
  function lignesDuPlan(plan, attente, emplois) {
    const rubriques = (plan && plan.rubriques) || [];
    const entrees = (plan && plan.entrees) || [];
    const connues = new Set(rubriques.map((r) => r.cle));
    const etatE = (e) => {
      if (manques(e, attente && attente.get(e.cle), plan).length) return ["● à compléter", true];
      if (e.retiree) return ["retirée", false];
      const n = ((emplois || vide).entrees || {})[e.cle] || 0;
      const forme = e.forme === "variantes" ? pluriel((e.variantes || []).length, "var.", "var.")
        : e.forme === "qualificatifs" ? "cases" : "";
      return [[forme, n ? pluriel(n, "relevé") : ""].filter(Boolean).join(" · "), false];
    };
    const lignes = [];
    const ent = (e, p) => {
      const [etat, alerte] = etatE(e);
      lignes.push({ t: "entree", cle: e.cle, libelle: e.libelle, profondeur: p, etat, alerte,
                    retiree: !!e.retiree });
    };
    const vus = new Set();
    const rub = (r, p) => {
      if (vus.has(r.cle)) return;
      vus.add(r.cle);
      lignes.push({ t: "rubrique", cle: r.cle, libelle: r.libelle, profondeur: p, etat: "",
                    alerte: false, retiree: false });
      entrees.filter((e) => e.rubrique_cle === r.cle).forEach((e) => ent(e, p + 1));
      rubriques.filter((x) => x.parent_cle === r.cle).forEach((x) => rub(x, p + 1));
    };
    lignes.push({ t: "grille", cle: "", libelle: "Toute la grille", profondeur: 0, etat: "",
                  alerte: false, retiree: false });
    rubriques.filter((r) => r.parent_cle === null || r.parent_cle === undefined
                     || !connues.has(r.parent_cle)).forEach((r) => rub(r, 0));
    const hors = entrees.filter((e) => !e.rubrique_cle || !connues.has(e.rubrique_cle));
    if (hors.length) {
      lignes.push({ t: "sep", cle: "hors", libelle: "Hors rubrique" });
      hors.forEach((e) => ent(e, 0));
    }
    return lignes;
  }

  /* --- 4. L'ordre --------------------------------------------------------------------- */

  /* Les FRÈRES d'un objet, dans leur ordre (la règle de `PUT …/ordre`) : une rubrique parmi
     celles de même parent, une entrée parmi celles de sa rubrique (retirées comprises), une
     variante parmi celles de son entrée, une case parmi celles de sa liste. `parent` : la
     clé de l'entrée (variante) ou de la liste (case). */
  function freres(plan, quoi, cle, parent) {
    const p = plan || {};
    if (quoi === "rubrique") {
      const r = (p.rubriques || []).find((x) => x.cle === cle);
      return r ? (p.rubriques || []).filter((x) => (x.parent_cle || null) === (r.parent_cle || null))
        .map((x) => x.cle) : [];
    }
    if (quoi === "entree") {
      const e = (p.entrees || []).find((x) => x.cle === cle);
      return e ? (p.entrees || []).filter((x) => (x.rubrique_cle || null) === (e.rubrique_cle || null))
        .map((x) => x.cle) : [];
    }
    if (quoi === "variante") {
      const e = (p.entrees || []).find((x) => x.cle === parent);
      return e ? (e.variantes || []).map((x) => x.cle) : [];
    }
    if (quoi === "case") {
      const l = (p.listes || []).find((x) => x.cle === parent);
      return l ? (l.qualificatifs || []).map((x) => x.cle) : [];
    }
    return [];
  }

  /* Monter (`sens` -1) ou descendre (+1) un objet : le corps de `PUT …/ordre`, ou `null` au
     bord. */
  function deplacer(plan, quoi, cle, sens, parent) {
    const f = freres(plan, quoi, cle, parent);
    const i = f.indexOf(cle);
    const j = i + sens;
    if (i < 0 || j < 0 || j >= f.length) return null;
    const corps = { quoi, cle, place: j, vu: f };
    if (quoi === "variante") corps.entree_cle = parent;
    if (quoi === "case") corps.liste_cle = parent;
    return corps;
  }

  /* --- L'aperçu ----------------------------------------------------------------------- */

  /* Le plan tel que l'aperçu le dessine : celui du serveur, et par-dessus ce qui attend —
     la forme et la liste répondues, pas encore écrites. L'aperçu suit chaque réponse. */
  function planDApercu(plan, attente) {
    if (!plan) return null;
    return { ...plan, entrees: (plan.entrees || []).map((e) => {
      const a = attente && attente.get(e.cle);
      if (!a || !a.forme) return e;
      return { ...e, forme: a.forme, liste_cle: a.forme === "qualificatifs" ? (a.liste || null) : null };
    }) };
  }

  /* --- 5. La faute d'un import, et son objet ------------------------------------------- */

  /* L'objet du formulaire où se corrige une faute du bilan d'un réimport : { t, cle } ou
     `null` quand le plan ne le connaît pas (une entrée que le fichier ajoute). `f` : une
     anomalie telle que le serveur la rend (`cle`, `colonne`, `listes`, `fichier`, `code`). */
  function cibleDeFaute(f, plan) {
    if (!f || !plan) return null;
    const entrees = plan.entrees || [];
    const listes = plan.listes || [];
    const rubriques = plan.rubriques || [];
    if (f.listes) {
      if (listes.some((l) => l.cle === f.cle)) return { t: "liste", cle: f.cle };
      const l = listes.find((x) => (x.qualificatifs || []).some((q) => q.cle === f.cle));
      return l ? { t: "liste", cle: l.cle } : null;
    }
    if (f.cle && entrees.some((e) => e.cle === f.cle)) return { t: "entree", cle: f.cle };
    if (f.cle && rubriques.some((r) => r.cle === f.cle)) return { t: "rubrique", cle: f.cle };
    if (f.colonne === "porte_sur" || f.fichier === "déclaration"
        || /^porte_sur/.test(f.code || "")) return { t: "grille", cle: "" };
    return null;
  }

  return {
    CIBLES, ZONES, TYPES_TEXTE, FORMES, QUESTIONS, mot, pluriel, ordonner, reponseCible,
    ciblesDeReponse, ciblesEnMots, reponseCardinalite, cardinaliteParDefaut, reponses,
    manques, listesUtilisables, aCompleter, repondre, envoiVariante, vuEntree, avecVu,
    corpsEntree, exemplesDeTexte, texteDExemples, offresEntree, formesPossibles, offresVariante, offresCase,
    offresRubrique, offresListe, placesDeRubrique, cheminDeRubrique, ouSEcrit, noteDeVersion,
    versionMontree, publiable, lignesDuPlan, freres, deplacer, planDApercu, cibleDeFaute,
  };
});
