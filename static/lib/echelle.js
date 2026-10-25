/* L'ÉCHELLE DES CRANS et l'effacement (COL-3, tranche 3b) — la logique PURE de l'écran
   tranché par Hugo sur maquette le 2026-10-25, sans DOM.

   Chargé en <script> par la Bibliothèque ET par l'Administration → `window.BDEchelle` ;
   aussi require()-able par `tests/js/echelle.test.js`, qui la vérifie par tables de cas.
   Rien n'est lu au chargement : ni le document, ni la fenêtre, ni l'adresse.

   CE QUE C'EST. Cinq crans, du plus nu au plus travaillé (E1) : les images seules, puis le
   découpage, la transcription, la grammaire relue, les annotations. On EN PART (« Copie… »,
   une demande d'en partir entre deux projets), et l'on Y REVIENT (« Repartir de zéro »). Ce
   module dit les MOTS de chaque cran, ce qu'un cran ajoute en nombres (l'aperçu, E5-E6), ce
   qu'un retour efface (« Part »), « qui perd quoi » avant d'effacer, et pourquoi l'on peut
   effacer sans rien demander — une phrase par chemin de la règle du 2026-10-21.

   CE N'EST PAS UNE GARDE. Qui peut quoi, le serveur le dit : `direct` (l'aperçu de
   « Repartir »), `etat` et `repondra` (l'aperçu d'« en partir »), `destructible` et
   `derniere_copie` (`GET /api/albums`), et ce qu'il compte (`travail_des_autres`). Ce module
   choisit les mots de ce qui a été décidé, et n'en déduit aucun droit.

   UNE VALEUR RECOPIÉE DU SERVEUR, et son accord est MESURÉ : la liste des crans
   (`database.CRANS`, et `CRANS_DE_REPARTIR`, tous sauf le plus haut). Aucune route ne la
   publie ; `tests/test_echelle_ecran.py` fait tomber la suite si l'une s'écarte. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDEchelle = api;                                                  // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Les cinq crans, dans l'ordre de l'échelle (E1). `court` : le libellé d'une radio ;
     `ajoute` : ce que le cran ajoute, en mots, quand on n'a pas encore de nombres. */
  const CRANS = [
    { valeur: "images", court: "Images seules",
      ajoute: "la notice et les planches : une copie vierge" },
    { valeur: "decoupage", court: "+ le découpage", ajoute: "cases, bulles, ordre de lecture" },
    { valeur: "transcription", court: "+ la transcription", ajoute: "le texte des bulles" },
    { valeur: "grammaire", court: "+ la grammaire relue", ajoute: "lemmes et catégories corrigés" },
    { valeur: "annotations", court: "+ les annotations",
      ajoute: "notes, tags, attributs de case, locuteurs, présences" },
  ];
  const VALEURS = CRANS.map((c) => c.valeur);
  /* Les crans VERS lesquels on repart de zéro : tous sauf le plus haut, au-dessus duquel il
     n'y a rien à retirer (`database.CRANS_DE_REPARTIR`). */
  const CRANS_DE_REPARTIR = VALEURS.slice(0, -1);

  const JUSQUA = {
    images: "images seules", decoupage: "jusqu'au découpage",
    transcription: "jusqu'à la transcription", grammaire: "jusqu'à la grammaire relue",
    annotations: "jusqu'aux annotations",
  };
  const VERS = {
    images: "aux images seules", decoupage: "au découpage", transcription: "à la transcription",
    grammaire: "à la grammaire relue",
  };
  const DEPUIS = {
    images: "des images seules", decoupage: "du découpage", transcription: "de la transcription",
    grammaire: "de la grammaire relue", annotations: "des annotations",
  };

  const g = (t) => `« ${t} »`;
  const majuscule = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
  /* Un nombre à la française, ses milliers séparés par une espace fine insécable (U+202F) :
     écrit ici plutôt que confié à `toLocaleString`, dont le séparateur change d'un moteur
     (et d'une version d'ICU) à l'autre. */
  const nf = (n) => String(Math.trunc(Number(n) || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");

  function et(noms) {
    const l = (noms || []).filter(Boolean);
    if (l.length <= 1) return l.join("");
    return `${l.slice(0, -1).join(", ")} et ${l[l.length - 1]}`;
  }

  /* Le rang d'un cran sur l'échelle ; -1 pour une valeur inconnue. */
  function rang(valeur) { return VALEURS.indexOf(valeur); }

  /* « jusqu'à la transcription », « images seules » — une valeur inconnue se dit telle
     quelle plutôt que de disparaître. */
  function jusqua(valeur) { return JUSQUA[valeur] || String(valeur || ""); }
  function vers(valeur) { return VERS[valeur] || String(valeur || ""); }
  /* Le bouton qui repart de zéro VERS ce cran : « Repartir de la transcription ». */
  function boutonRepartir(valeur) {
    return DEPUIS[valeur] ? `Repartir ${DEPUIS[valeur]}` : "Repartir de zéro";
  }
  /* La puce d'une copie remise à zéro : « repartie de la transcription ». */
  function repartieDe(valeur) {
    return DEPUIS[valeur] ? `repartie ${DEPUIS[valeur]}` : "repartie de zéro";
  }

  /* ── Les nombres ──────────────────────────────────────────────────────────────────── */

  /* Ce que veut dire chaque compte que le serveur rend, au singulier et au pluriel. */
  const MOTS = {
    regions: ["région", "régions"], textes: ["texte", "textes"],
    corrections: ["correction", "corrections"], annotations: ["annotation", "annotations"],
    tags: ["tag", "tags"], attributs: ["attribut de case", "attributs de case"],
    locuteurs: ["locuteur", "locuteurs"], presences: ["présence", "présences"],
    planches_devalidees: ["validation de planche", "validations de planche"],
  };
  function compte(cle, n) {
    const m = MOTS[cle] || [cle, cle];
    return `${nf(n)} ${Number(n) > 1 ? m[1] : m[0]}`;
  }

  /* Les comptes d'un cran, parmi ce que l'aperçu rend (`copies`) : ce que ce cran AJOUTE au
     précédent — la table de `database.compter_le_travail`, cran par cran. */
  const AJOUTS = {
    images: [], decoupage: ["regions"], transcription: ["textes"], grammaire: ["corrections"],
    annotations: ["annotations", "tags", "attributs", "locuteurs", "presences"],
  };

  /* L'ÉCHELLE EN TABLEAU (écran de la 3b, « l'aperçu se lit DANS l'échelle ») : une ligne par
     cran, et ce qu'elle ajoute en nombres. `apercu` : la réponse de
     `GET /api/albums/{id}/amorcer/apercu` au cran le plus haut — elle porte tous les
     comptes —, ou null tant qu'on ne l'a pas. Rend, cran par cran :
       { valeur, court, ajout: [« 1 840 régions », …], vide, texte } —
     `vide` : la source n'a pas ce travail (la ligne se lit en gris, le cran reste
     choisissable) ; `texte` : ce que la ligne dit. Sans aperçu, la phrase du cran. */
  function lignesEchelle(apercu) {
    const copies = apercu && apercu.copies ? apercu.copies : null;
    return CRANS.map((c, i) => {
      if (i === 0) {
        return { valeur: c.valeur, court: c.court, ajout: [], vide: false,
                 texte: "la notice et les planches" };
      }
      if (!copies) return { valeur: c.valeur, court: c.court, ajout: [], vide: false, texte: c.ajoute };
      const ajout = AJOUTS[c.valeur].filter((k) => Number(copies[k]) > 0)
        .map((k) => compte(k, copies[k]));
      return { valeur: c.valeur, court: c.court, ajout, vide: !ajout.length,
               texte: ajout.length ? ajout.join(" · ") : "rien : la source n'a pas ce travail" };
    });
  }

  /* Sous le tableau, au cran des annotations seulement : les tags et attributs qui RESTENT
     (comptés, jamais nommés, E5) et les fiches de personnage qui deviennent lisibles (E6).
     `arrivee` : le nom de la collection d'arrivée. Rend { restent, aide, personnages } —
     chaînes vides quand il n'y a rien à dire. */
  function sousLEchelle(apercu, cran, arrivee) {
    const vide = { restent: "", aide: "", personnages: "" };
    if (!apercu || cran !== "annotations") return vide;
    const l = apercu.laisses || {};
    const restent = ["tags", "attributs"].filter((k) => Number(l[k]) > 0).map((k) => compte(k, l[k]));
    const n = Number(apercu.personnages) || 0;
    return {
      restent: restent.length ? `Restent : ${restent.join(", ")}` : "",
      aide: restent.length
        ? `Locaux à une collection que ${g(arrivee)} ne voit pas : ils ne suivent pas, et ne `
          + "sont pas nommés." : "",
      personnages: n ? `${nf(n)} fiche${n > 1 ? "s" : ""} de personnage deviennent lisibles ici`
        : "",
    };
  }

  /* L'aperçu d'une DEMANDE d'en partir, pour qui y répond (le bloc ⚑, la fiche du projet
     source, « À faire ») : ce qui part avec la copie, ce qui reste, ce qui devient lisible.
     `apercu` : `database.compter_le_travail` au cran demandé, que le serveur joint à la
     demande ; null quand il ne le peut pas (la collection d'arrivée supprimée). */
  function apercuDemande(apercu, arrivee) {
    if (!apercu) return { partent: [], restent: [], personnages: "", rien: false };
    const c = apercu.copies || {};
    const partent = Object.keys(MOTS).filter((k) => Number(c[k]) > 0).map((k) => compte(k, c[k]));
    const l = apercu.laisses || {};
    const restent = ["tags", "attributs"].filter((k) => Number(l[k]) > 0).map((k) => compte(k, l[k]));
    const n = Number(apercu.personnages) || 0;
    return {
      partent, restent, rien: !partent.length,
      aide: restent.length
        ? `Locaux à une collection que ${g(arrivee || "la collection d'arrivée")} ne voit pas : `
          + "ils ne suivent pas, et ne sont pas nommés." : "",
      personnages: n ? `${nf(n)} fiche${n > 1 ? "s" : ""} de personnage deviennent lisibles dans `
        + `${g(arrivee || "la collection d'arrivée")}` : "",
    };
  }

  /* ── « Copie… » : la réponse attendue, avant de copier ────────────────────────────────── */

  /* Ce que « Copie… » fera, dit AVANT (écran de la 3b) : immédiat, ou à accepter par qui. Le
     serveur l'a dit dans l'aperçu (`etat`, `repondra`) — sauf aux images seules, toujours
     immédiates pour qui lit déjà une copie du projet (la copie vierge de la 3a).
     Rend { direct, texte, bouton }. */
  function reponseCopie({ cran, etat, repondra, total, arrivee }) {
    if (cran === "images") {
      return { direct: true, texte: "Immédiat : une copie vierge, à votre nom.",
               bouton: "Copier les images" };
    }
    if (total || etat === "fait") {
      return { direct: true,
               texte: total ? "Immédiat : vous administrez l'instance. La copie est à votre nom."
                 : "Immédiat : vous tenez toutes les collections de cette copie. La copie est à "
                   + "votre nom.",
               bouton: `Copier ${jusqua(cran)}` };
    }
    const qui = repondra === "administrateur" ? "Un administrateur" : "Son propriétaire";
    return { direct: false,
             texte: `${qui} doit l'accepter : copier ce travail le fait lire dans `
               + `${g(arrivee || "cette collection")}.`,
             bouton: "Demander" };
  }

  /* ── Repartir de zéro ───────────────────────────────────────────────────────────── */

  /* Les radios « Revenir… » : les quatre crans d'arrivée, ceux au niveau du travail de la
     copie ou au-dessus ÉTEINTS (on ne repart que vers plus bas que ce qu'elle porte). `niveau`
     : le plus haut travail de la copie, ou de la planche (l'aperçu le rend). */
  function cransRepartir(niveau) {
    const haut = rang(niveau);
    return CRANS_DE_REPARTIR.map((v, i) => {
      const eteint = i >= haut;
      const garde = CRANS.slice(1, i + 1).map((c) => c.court.replace(/^\+ /, ""));
      return {
        valeur: v, libelle: majuscule(vers(v)), eteint,
        sous: eteint ? "le travail ne va pas plus haut"
          : i === 0 ? "plus aucune région" : `garder ${et(garde)}`,
      };
    });
  }

  /* Le cran coché à l'ouverture : le plus haut qu'on puisse choisir — n'ôter que la couche
     du dessus, le geste le moins destructeur. `null` quand rien n'est au-dessus des images. */
  function cranParDefaut(niveau) {
    const haut = rang(niveau);
    return haut >= 1 ? CRANS_DE_REPARTIR[Math.min(haut, CRANS_DE_REPARTIR.length) - 1] : null;
  }

  /* « Part », en nombres, validations comprises — les comptes que l'aperçu rend
     (`database.compter_repartir`), dans l'ordre de l'échelle. */
  const ORDRE_PART = ["regions", "textes", "corrections", "annotations", "attributs",
                      "locuteurs", "presences", "planches_devalidees"];
  function part(comptes) {
    const c = comptes || {};
    return ORDRE_PART.filter((k) => Number(c[k]) > 0).map((k) => compte(k, c[k]));
  }

  /* Ce qui reste, en tête du panneau. `planche` : le libellé de la planche, ou null pour
     l'album entier. */
  function restent(planche, nbPlanches) {
    if (planche) {
      return `${/^le /.test(planche) ? "Seul" : "Seule"} ${planche} change. Restent : ses `
        + "images, la notice et son verrou.";
    }
    const n = Number(nbPlanches) || 0;
    return `${n ? `Sur ${n > 1 ? `les ${nf(n)} planches` : "sa planche"}. ` : ""}Restent : les `
      + "images, la notice, les planches et leur verrou.";
  }

  /* LA CERTIFICATION d'une demande de repartir de zéro : les mots de la suppression,
     adaptés (écran de la 3b). Le serveur l'exige (`certifie`) et n'en garde que la date. */
  const CERTIFICATION_REPARTIR = {
    texte: "Repartir de zéro détruit ce qui a été posé sur les planches au-dessus du cran "
      + "choisi, que d'autres utilisent peut-être dans le projet ou dans ses collections. "
      + "Pouvez-vous certifier que ces données ne sont pas importantes ?",
    caseACocher: "Je certifie que ces données ne sont pas importantes.",
    manque: "Cochez la certification : la demande ne part pas sans elle.",
  };

  /* Ce que dit le panneau « Repartir de zéro » après le choix du cran : faire tout de
     suite, demander, ou attendre une demande déjà partie. Une PLANCHE n'a pas de demande à
     elle (décision B4, que le serveur tient pour « repartir » comme pour « supprimer ») :
     sans le droit de le faire soi-même, le panneau le dit et n'offre rien.
     `direct` : la réponse du serveur ; `pouvoir` : la clé de `POUVOIRS` (ou null) ;
     `attente` : la demande qui attend déjà sur la copie (`demande_repartir`), ou null.
     Rend { mode: "direct" | "demande" | "attente" | "planche", texte }. */
  function panneauRepartir({ direct, pouvoir, planche, attente, dateLue }) {
    if (direct) {
      return { mode: "direct",
               texte: pouvoir && POUVOIRS[pouvoir] ? `${POUVOIRS[pouvoir]} : rien à demander.`
                 : "Rien à demander." };
    }
    if (planche) {
      return { mode: "planche",
               texte: "D'autres se servent de cet album, ou ce n'est pas vous qui avez créé cette "
                 + "copie : repartir de zéro sur une planche ne se demande pas. Adressez-vous à "
                 + "un administrateur de l'instance." };
    }
    if (attente) {
      const quand = attente.date_creation && dateLue ? `, le ${dateLue(attente.date_creation)}` : "";
      return { mode: "attente",
               texte: `Repartir ${DEPUIS[attente.cran] || "de zéro"} est déjà demandé${quand} : un `
                 + "administrateur y répondra. Rien n'est effacé d'ici là." };
    }
    return { mode: "demande",
             texte: "D'autres y ont travaillé, ou ce n'est pas vous qui avez créé cette copie : "
               + "la demande part à un administrateur, qui décide. Rien n'est effacé d'ici là." };
  }

  /* ── Pourquoi l'on efface sans demander : une phrase par chemin (Hugo, 2026-10-21) ────── */

  const POUVOIRS = {
    admin: "Vous administrez l'instance",
    bac: "C'est votre bac à sable",
    createur: "Vous avez créé cette copie, et personne d'autre n'y a travaillé",
    responsable: "Vous êtes responsable du projet",
    proprietaire: "Vous tenez toutes ses collections",
  };

  /* Le CRÉATEUR d'une copie que personne d'autre n'a touchée, lu dans ce que rend
     `GET /api/albums/{id}/travail-des-autres` : `creee_par` est l'appelant, et personne
     d'autre n'y a laissé de geste — le travail RECOPIÉ d'une autre copie compris, que la
     règle compte comme les autres. */
  function createurIntact(vue, moi) {
    return !!(vue && moi && vue.creee_par === moi
              && !(vue.travail_des_autres || []).length && !vue.travail_recopie);
  }

  /* LE CHEMIN par lequel on efface sans demander, pour le dire — jamais pour décider : le
     serveur a déjà dit si on le peut. Le plus précis d'abord : la portée totale, son bac à
     sable, le créateur seul, le responsable du projet, le propriétaire de toutes les
     collections de l'album (qu'on ADMINISTRE toutes, et qui ne vit nulle part ailleurs).
     `null` : aucun — l'écran ne suppose rien. */
  function pouvoir({ total, bac, createur, responsable, proprietaire }) {
    if (total) return "admin";
    if (bac) return "bac";
    if (createur) return "createur";
    if (responsable) return "responsable";
    if (proprietaire) return "proprietaire";
    return null;
  }

  /* ── « Qui perd quoi » (écran de la 3b, le tableau) ──────────────────────────────────── */

  /* Les sortes de gestes que la règle lit (`autorisation.sql_actes_sur_album`), réunies en
     colonnes. `perdu` : à partir de quel cran d'arrivée « repartir » efface cette famille
     (le cran d'arrivée doit être STRICTEMENT au-dessous) — le découpage et le texte vivent
     tous deux sur la région ; une validation part toujours ; la notice et les scans ne
     partent qu'avec une suppression. */
  const COLONNES = [
    { cle: "regions", libelle: "cases et bulles", sortes: ["regions"], perdu: "transcription",
      aide: "Gestes sur le découpage et le texte des bulles" },
    { cle: "corrections", libelle: "corrections", sortes: ["token_correction"], perdu: "grammaire",
      aide: "Corrections grammaticales" },
    { cle: "annotations", libelle: "annotations",
      sortes: ["annotations", "bulle_locuteur", "personnage_presence", "region_attribut"],
      perdu: "annotations", aide: "Notes, tags, locuteurs, présences, attributs de case" },
    { cle: "validations", libelle: "validations", sortes: ["planches"], perdu: "annotations",
      aide: "Validations et relectures de planche" },
    { cle: "document", libelle: "notice et scans", sortes: ["document"], perdu: null,
      aide: "Gestes sur la notice, les contributions et les scans" },
  ];
  const AIDE_GESTES = "Ce sont des gestes, défaits compris, pas ce qui reste sur les planches.";

  /* Les colonnes CONCERNÉES par un geste : tout ce qu'une suppression efface ; ce que
     « repartir » vers `cran` efface ; pour « retirer », qui n'efface rien, tout ce qui a été
     fait. */
  function colonnesConcernees(geste, cran) {
    if (geste === "repartir") {
      const r = rang(cran);
      return COLONNES.filter((c) => c.perdu !== null && r >= 0 && r < rang(c.perdu));
    }
    return COLONNES.slice();
  }

  /* Le tableau « qui perd quoi » : `travail` — la liste `travail_des_autres` que rend le
     serveur ({agent, agent_nom, collectif, gestes: {sorte: n}, dernier}), déjà privée de
     l'appelant. `geste` : « supprimer », « repartir » (avec `cran`), « retirer » ou
     « demande » (l'administrateur, sous une demande de repartir). `recopie` (« retirer »
     seulement) : le travail recopié d'une autre copie, compté sans auteur.
     Rend null quand personne n'a de geste dans les colonnes concernées — le panneau ne dit
     alors rien —, sinon { titre, colonnes, lignes: [{qui, valeurs, dernier}], note, aide }.
     Une colonne n'y est que si quelqu'un y a un geste. */
  function quiPerdQuoi(travail, { geste, cran, recopie, dateLue, titre: titreImpose } = {}) {
    const concernees = colonnesConcernees(geste, cran);
    const date = (d) => (d && dateLue ? dateLue(d) : d || "");
    const ligne = (gestes) => {
      const valeurs = {};
      for (const c of concernees) {
        valeurs[c.cle] = c.sortes.reduce((s, k) => s + (Number((gestes || {})[k]) || 0), 0);
      }
      return valeurs;
    };
    const lignes = (Array.isArray(travail) ? travail : []).map((e) => {
      const nom = e.agent ? (e.agent_nom && e.agent_nom !== e.agent
        ? `${e.agent_nom} (${e.agent})` : e.agent) : "Auteur non écrit";
      return { qui: e.collectif ? `${nom} — compte partagé` : nom,
               valeurs: ligne(e.gestes), dernier: date(e.dernier) };
    }).filter((l) => Object.values(l.valeurs).some((n) => n > 0));
    if (geste === "retirer" && recopie && recopie.gestes) {
      const valeurs = ligne(recopie.gestes);
      if (Object.values(valeurs).some((n) => n > 0)) {
        lignes.push({ qui: "Recopié d'une autre copie (auteurs non nommés)", valeurs,
                      dernier: date(recopie.dernier) });
      }
    }
    if (!lignes.length) return null;
    const colonnes = concernees.filter((c) => lignes.some((l) => l.valeurs[c.cle] > 0))
      .map(({ cle, libelle, aide }) => ({ cle, libelle, aide }));
    const autres = lignes.filter((l) => !l.qui.startsWith("Recopié")).length;
    const titre = titreImpose ? titreImpose
      : geste === "retirer" ? "Qui y a travaillé (rien n'est effacé)"
      : geste === "demande" ? "Ce que d'autres que le demandeur y ont fait"
      : autres > 1 ? `Ce que ${autres} autres personnes perdent` : "Ce qu'une autre personne perd";
    return { titre, colonnes, lignes, note: "Des gestes, comptés au journal", aide: AIDE_GESTES };
  }

  /* ── Entre deux projets (E7) : la copie source, chez qui tient le travail ─────────────── */

  /* Le nom d'une copie source dans « Depuis quelle copie » : ses collections qu'on lit
     (`collections` de `GET /api/albums`), sinon son titre ; et jusqu'où elle est travaillée.
     `copie` : une ligne de `copies` (`GET /api/projets/{id}/demandes-recues`) ou de
     `sources` (`GET /api/demandes`). */
  function nomCopie(copie, album) {
    const cols = album && Array.isArray(album.collections) ? album.collections : [];
    return cols.length ? cols.map((c) => g(c.nom)).join(", ")
      : g(copie && copie.titre ? copie.titre : "une copie");
  }
  function detailCopie(copie, demande) {
    const tient = copie.tient !== false;
    return `travaillée ${jusqua(copie.niveau)}`
      + (tient ? "" : ` — pas assez haut pour ${jusqua(demande ? demande.cran : "")}`);
  }

  /* La copie cochée d'abord : celle qu'on avait choisie, si elle tient encore le travail ;
     sinon la première qui le tient ; sinon aucune. */
  function copieParDefaut(copies, choisie) {
    const l = (Array.isArray(copies) ? copies : []).filter((c) => c.tient !== false);
    if (choisie !== undefined && choisie !== null && l.some((c) => c.album_id === choisie)) {
      return choisie;
    }
    return l.length ? l[0].album_id : null;
  }

  /* « Accepter : copier depuis « … » » — le nom de la copie choisie. */
  function accepterDepuis(nom) { return `Accepter : copier depuis ${nom}`; }

  /* Ce que la demande dit à qui y répond : qui la fait, pour quel projet, quel document,
     jusqu'où. */
  function texteEnPartir(d) {
    const qui = d.demandeur_nom || d.demandeur || "Quelqu'un";
    const titre = d.titre || ((d.documents || [])[0] || {}).titre || "un document";
    return `${qui} demande d'en partir : ${g(titre)}, ${jusqua(d.cran)}`;
  }

  /* L'« attend … » d'une demande consentie, dans « À faire » (l'administrateur la voit et
     peut répondre à sa place) : les noms des responsables des projets qui tiennent le
     travail (E7), ou des propriétaires qui tiennent toutes les collections de la copie
     (dans un projet). Personne : c'est à lui. */
  function attend(noms, { dansLeProjet } = {}) {
    const l = [...new Set((noms || []).filter(Boolean))];
    if (l.length) return `attend ${et(l)}`;
    return dansLeProjet ? "aucun propriétaire ne tient toutes ses collections : à vous"
      : "aucun responsable ne tient ce travail : à vous";
  }

  /* Les noms qu'attend une demande d'en partir ENTRE DEUX PROJETS : les responsables de
     chaque projet qui tient le travail (`sources[].responsables`, que le serveur ne rend
     qu'à l'administrateur) — un login par son nom lisible, un groupe par « groupe <nom> ». */
  function responsablesDesSources(sources) {
    const noms = [];
    for (const s of sources || []) {
      for (const r of s.responsables || []) {
        noms.push(r.genre === "groupe" ? `groupe ${r.principal}` : (r.nom || r.principal));
      }
    }
    return [...new Set(noms.filter(Boolean))];
  }

  /* ── Les traces ──────────────────────────────────────────────────────────────────── */

  /* La puce d'une copie remise à zéro (écran de la 3b) : « repartie de la transcription le
     12/10/2027 », et qui en infobulle — quand le serveur le rend. `repartie` : la clé de
     `GET /api/albums`. Rend { texte, titre } ou null. */
  function puceRepartie(repartie, dateLue) {
    if (!repartie || !repartie.cran) return null;
    const quand = repartie.le && dateLue ? ` le ${dateLue(repartie.le)}` : "";
    const qui = repartie.par ? (repartie.par_nom || repartie.par) : "";
    return { texte: `${repartieDe(repartie.cran)}${quand}`,
             titre: `${qui ? `Par ${qui}. ` : ""}Ce qui était au-dessus a été effacé ; le journal `
               + "garde l'acte." };
  }

  /* La puce d'une copie NÉE d'une autre (« Copie… ») : « copie · jusqu'à la transcription »,
     « copie vierge » aux images seules ; rien pour la copie d'origine du document. */
  function puceCopie(cran) {
    if (!cran || cran === "origine") return "";
    return cran === "images" ? "copie vierge" : `copie · ${jusqua(cran)}`;
  }

  /* Ce que lit chaque propriétaire d'une collection quittée, en tête de son onglet Albums,
     jusqu'à « Vu » (écran de la 3b). `r` : une ligne de `GET /api/collections/{id}/retraits`.
     `moi` : le login de qui lit, pour dire « vous ». */
  function ligneRetrait(r, moi, dateLue) {
    const qui = r.par && moi && r.par === moi ? "vous" : (r.par_nom || r.par || "quelqu'un");
    const quand = r.le && dateLue ? ` le ${dateLue(r.le)}` : "";
    return { texte: `${g(r.titre || "Un album")} a été retiré du projet par ${qui}${quand} : il `
               + "est gardé au fonds, avec son travail.",
             motif: r.motif ? `Motif : ${r.motif}` : "" };
  }

  /* Ce que dit le panneau « Retirer du projet » de ceux qui le verront disparaître : les
     propriétaires des collections quittées, hors l'appelant. `collections` : celles de
     l'aperçu, chacune avec ses `proprietaires` ({genre, principal, nom}). */
  function proprietairesQuiVerront(collections, moi) {
    const vus = new Set(), noms = [];
    for (const c of collections || []) {
      for (const x of c.proprietaires || []) {
        const cle = `${x.genre}:${x.principal}`;
        if (vus.has(cle) || (x.genre === "utilisateur" && x.principal === moi)) continue;
        vus.add(cle);
        noms.push(x.genre === "groupe" ? `le groupe ${x.principal}` : (x.nom || x.principal));
      }
    }
    if (!noms.length) return "";
    return `${majuscule(et(noms))} ${noms.length > 1 ? "le verront" : "le verra"} disparaître, `
      + "avec votre nom et la date.";
  }

  /* La phrase de tête du panneau « Retirer du projet ». */
  function texteRetirer(projet, collections) {
    const noms = (collections || []).map((c) => g(c.nom));
    return `Il quitte toutes les collections de ${g(projet || "son projet")}${noms.length
      ? ` : ${et(noms)}` : ""}. Il part au fonds avec son travail ; un administrateur peut le `
      + "rendre.";
  }

  /* « + Créer une collection » ÉTEINT pour un membre (écran de la 3b) : la raison, en
     infobulle, qui nomme les responsables — `responsables` : leurs noms, que le serveur rend
     au membre qui ne crée pas. Sans responsable, seuls les administrateurs créent. */
  function raisonCreerEteint(projet, responsables) {
    const l = (responsables || []).filter(Boolean);
    const ou = g(projet || "ce projet");
    return l.length
      ? `Dans ${ou}, seuls les responsables créent des collections : demandez-le à ${et(l)}.`
      : `Dans ${ou}, seuls les administrateurs de l'instance créent des collections.`;
  }

  /* ── Trois fragments que deux écrans dessinent pareil ─────────────────────────────────
     « Qui perd quoi », l'aperçu d'une demande d'en partir et « Depuis quelle copie » se
     lisent dans la Bibliothèque ET dans l'Administration : un seul dessin, ici, plutôt que
     deux copies qui finiraient par dire autre chose. Des chaînes, échappées ici ; aucun
     accès au document. Les gestes qui les entourent restent à chaque écran. */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  /* Le tableau de `quiPerdQuoi` : Qui · une colonne par sorte de geste concernée · dernier
     geste ; puis « Des gestes, comptés au journal », l'explication en infobulle. Vide quand
     personne n'a de geste. */
  function htmlQuiPerdQuoi(t) {
    if (!t) return "";
    return `<section class="perd"><h5 class="perd-titre">${esc(t.titre)}</h5>
      <div class="table-cadre perd-cadre" tabindex="0" role="region" aria-label="${esc(t.titre)}">
      <table class="perd-table"><thead><tr><th scope="col">Qui</th>${t.colonnes.map((c) =>
        `<th scope="col" class="c-num" title="${esc(c.aide)}">${esc(c.libelle)}</th>`).join("")}<th scope="col">Dernier geste</th></tr></thead>
      <tbody>${t.lignes.map((l) => `<tr><th scope="row">${esc(l.qui)}</th>${t.colonnes.map((c) =>
        `<td class="c-num" data-l="${esc(c.libelle)}">${l.valeurs[c.cle] ? esc(nf(l.valeurs[c.cle])) : "—"}</td>`).join("")}<td data-l="Dernier geste">${esc(l.dernier || "—")}</td></tr>`).join("")}</tbody>
      </table></div>
      <p class="muted small perd-note" title="${esc(t.aide)}">${esc(t.note)} <span aria-hidden="true">ⓘ</span><span class="sr-only"> : ${esc(t.aide)}</span></p></section>`;
  }

  /* L'aperçu d'une demande d'en partir, en nombres : ce qui part, ce qui reste (compté,
     jamais nommé), ce qui devient lisible. */
  function htmlApercuDemande(apercu, arrivee) {
    const a = apercuDemande(apercu, arrivee);
    if (!apercu) {
      return `<p class="muted small apercu-absent">L'aperçu n'a pas pu être compté : la collection `
        + "d'arrivée n'existe peut-être plus.</p>";
    }
    return `<div class="apercu"><h5>Partent avec la copie</h5>${a.rien
      ? `<p class="muted small">Aucun travail à ce cran sur cette copie.</p>`
      : `<ul>${a.partent.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`}
      ${a.restent.length ? `<p class="small apercu-reste">Restent : ${esc(a.restent.join(", "))}
        <span class="muted" title="${esc(a.aide)}" aria-hidden="true">ⓘ</span><span class="sr-only"> — ${esc(a.aide)}</span></p>` : ""}
      ${a.personnages ? `<p class="small">${esc(a.personnages)}</p>` : ""}</div>`;
  }

  /* « Depuis quelle copie » (E7) : une radio par copie, les trop peu travaillées éteintes,
     puis l'aperçu de celle qui est cochée. `copies` : `{album_id, titre, niveau, tient,
     apercu, projet_nom?}` ; `albums` : `GET /api/albums`, pour nommer chaque copie par ses
     collections ; `choisie` : l'identifiant coché ; `projet` : vrai pour dire le projet de
     chaque copie (l'administrateur, qui en voit plusieurs). Le nom de la radio et ses
     attributs (`data-e7-source`) sont ceux que les deux écrans écoutent. */
  function htmlSourcesE7(d, { copies, albums, choisie, projet }) {
    const parId = new Map((albums || []).map((a) => [a.id, a]));
    const l = Array.isArray(copies) ? copies : [];
    if (!l.length) {
      return `<p class="small e7-aucune">Aucune copie que vous lisez ne tient ce travail : vous `
        + "pouvez refuser la demande ; un administrateur peut y répondre à votre place.</p>";
    }
    const coche = copieParDefaut(l, choisie);
    const choisieCopie = l.find((c) => c.album_id === coche) || null;
    return `<fieldset class="e7-sources"><legend>Depuis quelle copie</legend>
      ${l.map((c) => `<label class="e7-source"><input type="radio" name="e7-src-${d.id}"
          value="${c.album_id}" data-e7-source="${d.id}" ${c.album_id === coche ? "checked" : ""}
          ${c.tient === false ? "disabled" : ""}>
        <span>${esc(nomCopie(c, parId.get(c.album_id)))} <span class="muted small">· ${projet && c.projet_nom
          ? `${esc(c.projet_nom)} · ` : ""}${esc(detailCopie(c, d))}</span></span></label>`).join("")}
      </fieldset>
      ${choisieCopie ? htmlApercuDemande(choisieCopie.apercu, d.collection_nom) : ""}`;
  }

  /* Le nom, pour « Accepter : copier depuis « … » », de la copie cochée. */
  function nomCopieChoisie(copies, albums, choisie) {
    const l = Array.isArray(copies) ? copies : [];
    const id = copieParDefaut(l, choisie);
    const c = l.find((x) => x.album_id === id);
    if (!c) return null;
    const a = (albums || []).find((x) => x.id === c.album_id);
    return { id, nom: nomCopie(c, a) };
  }

  return {
    CRANS, VALEURS, CRANS_DE_REPARTIR, POUVOIRS, COLONNES, CERTIFICATION_REPARTIR, AIDE_GESTES,
    htmlQuiPerdQuoi, htmlApercuDemande, htmlSourcesE7, nomCopieChoisie,
    rang, jusqua, vers, boutonRepartir, repartieDe, compte, lignesEchelle, sousLEchelle,
    apercuDemande, reponseCopie, cransRepartir, cranParDefaut, part, restent, panneauRepartir,
    createurIntact, pouvoir, colonnesConcernees, quiPerdQuoi, nomCopie, detailCopie,
    copieParDefaut, accepterDepuis, texteEnPartir, attend, responsablesDesSources,
    puceRepartie, puceCopie,
    ligneRetrait, proprietairesQuiVerront, texteRetirer, raisonCreerEteint, et,
  };
});
