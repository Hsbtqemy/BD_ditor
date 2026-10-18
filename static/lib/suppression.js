/* « Supprimer » a deux réponses, et le fonds en garde la trace (COL-3, tranche 2) — la
   logique PURE des deux écrans qui en parlent, sans DOM.

   Chargé en <script> par la Bibliothèque ET par l'Administration → `window.BDSuppression` ;
   aussi require()-able par `tests/js/suppression.test.js`, qui la vérifie par tables de cas.
   Ce n'est PAS un module montable : rien ici ne dessine. Il est là pour une propriété — ce
   qu'un geste ANNONCE se décide par une règle, et une règle se vérifie par table de vérité,
   pas en relisant un gabarit.

   CE QUI N'EST PAS ICI, et c'est le contrat : QUI peut quoi. Le serveur le dit album par
   album (`ecrivable`, `destructible`, `partage`, `au_fonds`, `demande`, dans
   `GET /api/albums`), et il le dit seul — `autorisation.py` tranche, l'écran lit. Ce module
   ne déduit aucun droit : il choisit les MOTS de ce que le serveur a décidé.

   Aucun accès au document, à la fenêtre ni à l'adresse au chargement. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDSuppression = api;                                              // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Les genres d'une demande et ses deux réponses. Le serveur les accepte sans les publier
     par une route : ils ne se recopient qu'ICI, et `tests/test_suppression_ecran.py` mesure
     leur accord avec `database`. */
  const GENRE_DOCUMENT = "suppression_document";
  const GENRE_PROJET = "suppression_projet";
  /* COL-3, tranche 3a — les trois genres qui ne sont PAS des suppressions : faire entrer
     des documents du fonds, rejoindre un travail, rendre une copie gardée au fonds. Recopiés
     ici pour la même raison que les deux premiers, et mesurés de même. */
  const GENRE_ENTREE = "entree_documents";
  const GENRE_REJOINDRE = "rejoindre";
  const GENRE_RENDRE = "rendre_copie";
  const ACCEPTER = "acceptee";
  const REFUSER = "refusee";
  /* L'état d'une demande dont les documents ont reçu des réponses mêlées (D9) : jamais une
     réponse qu'on envoie, seulement ce qu'on lit. */
  const PARTIELLE = "partielle";

  const g = (texte) => `« ${texte} »`;

  function et(noms) {
    if (noms.length <= 1) return noms.join("");
    return `${noms.slice(0, -1).join(", ")} et ${noms[noms.length - 1]}`;
  }

  /* « 2026-10-14 22:58:00 » → « 15/10/2026 » à Paris. Ce que le serveur rend est une date
     SQLite, `datetime('now')`, donc en UTC et sans le dire : la couper à dix caractères
     donnait la veille à qui regarde entre minuit et deux heures (relevé sur capture). Une
     date AVEC heure se lit donc comme de l'UTC et se rend dans le fuseau du navigateur —
     la règle que `BDComptes.dateCourte` applique déjà aux dates ISO de « Comptes et
     groupes », qui ne lit pas cette forme et coupe l'année. Une date SANS heure est un jour,
     pas un instant : elle se rend telle quelle. Une valeur illisible aussi, plutôt que de
     disparaître. */
  function dateLue(iso) {
    if (!iso) return "";
    const texte = String(iso);
    const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/.exec(texte);
    if (!m) return texte;
    if (m[4] === undefined) return `${m[3]}/${m[2]}/${m[1]}`;
    // Un décalage écrit (« Z », « +02:00 ») se respecte ; sans lui, c'est de l'UTC.
    const t = /(Z|[+-]\d{2}:?\d{2})$/.test(texte)
      ? Date.parse(texte.replace(" ", "T"))
      : Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0));
    if (Number.isNaN(t)) return texte;
    const d = new Date(t);
    return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`
      + `/${d.getFullYear()}`;
  }

  /* Le nom de qui a demandé : le nom lisible, sinon le login, sinon rien. Le serveur ne le
     rend qu'à une portée totale et à la personne elle-même (Hugo, 2026-10-15) : à tout
     autre lecteur la demande arrive sans nom, et l'écran n'a rien à supposer. `moi` : le
     login de qui regarde, pour dire « vous ». */
  function demandeur(demande, moi) {
    if (!demande) return "";
    if (moi && demande.demandeur && demande.demandeur === moi) return "vous";
    return demande.demandeur_nom || demande.demandeur || "";
  }

  /* La pastille d'une ligne d'album : une demande de suppression l'attend. */
  function pastille(demande, moi) {
    if (!demande) return "";
    const qui = demandeur(demande, moi);
    return qui ? `suppression demandée par ${qui}` : "suppression demandée";
  }

  /* « Supprimer… » ne s'offre qu'à qui ÉCRIT dans l'album : à qui ne fait que le lire,
     aucune des deux réponses n'aboutirait. Une copie gardée au fonds n'est pas un album de
     travail : elle se règle dans l'Administration. */
  function offrir(album) {
    return !!(album && album.ecrivable && !album.au_fonds);
  }

  /* Supprimer DE la collection `collectionId` : ce que devient le travail, et ce qu'on y perd.

     `siennes` : les collections de l'album QU'ON LIT ({id, nom}) — la liste est partielle,
     c'est tout ce qu'on peut nommer. `ecrites` : les identifiants de celles où l'on écrit.
     `partage` : l'album vit aussi dans une collection qu'on ne lit pas (le serveur le dit).
     `total` : une portée totale — l'administrateur, ou l'usage sur un seul poste.

     Rend :
       reste       — "lu" (il reste dans des collections qu'on lit, nommées), "cache" (il
                     reste ailleurs, sans nom), "fonds" (c'était sa dernière collection) ;
       autres      — les noms des collections lues où il reste ;
       perdEcriture— on n'y écrira plus (c'était la seule collection où l'on y écrivait) ;
       perdVue     — on ne le verra plus ;
       confirmer   — le geste mérite une confirmation : il part au fonds, ou on y perd ;
       texte       — ce qui arrive, en une ou deux phrases. */
  function retrait({ siennes, ecrites, collectionId, partage, total }) {
    const lues = (siennes || []).filter((c) => c.id !== collectionId);
    const ecr = new Set(ecrites || []);
    const reste = lues.length ? "lu" : partage ? "cache" : "fonds";
    const ouJEcris = (siennes || []).filter((c) => ecr.has(c.id));
    const perdEcriture = !total && ouJEcris.length === 1 && ouJEcris[0].id === collectionId;
    const perdVue = !total && !lues.length;
    const phrases = [];
    if (reste === "lu") {
      phrases.push(`Le travail reste dans ${et(lues.map((c) => g(c.nom)))}, où rien ne change.`);
    } else if (reste === "cache") {
      phrases.push("Le travail reste dans une collection que vous ne lisez pas, où rien ne change.");
    } else {
      phrases.push("C'est sa dernière collection : la copie de travail est gardée au fonds, "
        + "avec tout son travail. "
        + (total ? "Vous pourrez la rendre depuis l'Administration."
                 : "Un administrateur peut la rendre."));
    }
    if (perdEcriture) {
      phrases.push(perdVue
        ? "Vous ne le verrez plus, et ne pourrez pas l'y ranger de nouveau vous-même."
        : "Vous continuerez de le lire, mais vous n'y écrirez plus, et ne pourrez pas l'y "
          + "ranger de nouveau vous-même.");
    } else if (perdVue) {
      phrases.push("Vous ne le verrez plus.");
    }
    return {
      reste, autres: lues.map((c) => c.nom), perdEcriture, perdVue,
      confirmer: reste === "fonds" || perdEcriture || perdVue,
      texte: phrases.join(" "),
    };
  }

  /* Supprimer DÉFINITIVEMENT : effacer tout de suite, ou demander, ou attendre une demande
     déjà partie. `destructible` est la réponse du serveur — l'écran ne la recalcule pas.
     Rend { mode: "direct" | "demande" | "attente", texte, bouton }. */
  /* Ce que dit la suppression d'une copie dont le document a une SŒUR (COL-3, tranche 3a,
     D5-D6) : les images appartiennent au document, et elles restent tant qu'une copie les
     emploie. La phrase ne dit pas OÙ vit l'autre copie — qui ne lit qu'un projet n'a pas à
     apprendre qu'un autre l'emploie (cadrage, « Les écrans touchés »). Le panneau
     « Supprimer… » de la Bibliothèque l'affiche quand le serveur dit qu'une sœur existe
     (`soeur`, dans `GET /api/albums`, rendu à qui écrit dans la copie). */
  const IMAGES_RESTENT = "Ses images restent : une autre copie de ce document les emploie.";

  /* `soeur` : le document a une autre copie — les images restent, et la phrase le dit. */
  function definitif({ destructible, demande, total, moi, soeur }) {
    if (destructible) {
      const efface = soeur ? "cette copie et" : "cette copie, ses images et";
      const reste = soeur ? ` ${IMAGES_RESTENT}` : "";
      return {
        mode: "direct", bouton: "Supprimer définitivement",
        texte: total
          ? `Efface tout de suite ${efface} tout le travail fait dessus.${reste} Irréversible.`
          : `Efface tout de suite ${efface} le travail fait dessus : vous l'avez créée, et `
            + `personne d'autre n'y a travaillé.${reste} Irréversible.`,
      };
    }
    if (demande) {
      const qui = demandeur(demande, moi), quand = dateLue(demande.date_creation);
      return {
        mode: "attente", bouton: "",
        texte: "Sa suppression est déjà demandée" + (qui ? ` par ${qui}` : "")
          + (quand ? `, le ${quand}` : "")
          + " : un administrateur y répondra. Rien n'est effacé d'ici là.",
      };
    }
    return {
      mode: "demande", bouton: "Envoyer la demande",
      texte: "D'autres s'en servent, ou ce n'est pas vous qui avez créé cette copie : la "
        + `demande part à un administrateur, qui décide.${soeur ? ` ${IMAGES_RESTENT}` : ""} `
        + "Rien n'est effacé d'ici là.",
    };
  }

  /* La CERTIFICATION qui accompagne une demande de suppression définitive (Hugo,
     2026-10-15) : ce que la suppression détruit, la question, et la case. Le serveur exige
     la case (`certifie`) ; il n'en garde que la date. Les mots vivent ici, une fois. */
  const CERTIFICATION = {
    texte: "Supprimer définitivement détruit tout ce qui a été posé sur les planches — "
      + "découpage, transcription, annotations, métadonnées —, que d'autres utilisent "
      + "peut-être dans le projet ou dans ses collections. Pouvez-vous certifier que ces "
      + "données ne sont pas importantes ?",
    caseACocher: "Je certifie que ces données ne sont pas importantes.",
    manque: "Cochez la certification : la demande ne part pas sans elle.",
  };

  /* Ce qu'on lit une fois le geste fait. */
  function apresRetrait(titre, collection, reste) {
    return `${g(titre)} n'est plus dans ${g(collection)}. `
      + (reste === "fonds" ? "Sa copie de travail est gardée au fonds."
                           : "Le travail continue ailleurs.");
  }

  function apresDefinitif(titre, mode) {
    return mode === "direct"
      ? `${g(titre)} est supprimé définitivement, avec ses images et le travail fait dessus.`
      : "Votre demande est partie à un administrateur. Rien n'est effacé d'ici sa réponse.";
  }

  /* ── Le fonds, vu par qui le tient ─────────────────────────────────────────────────── */

  /* D'où vient un document. Qui l'a importé n'est écrit que depuis le fonds : avant, et sur
     un seul poste où personne ne s'annonce, il n'y a pas de nom — et l'écran ne l'invente
     pas. */
  function origine(doc) {
    const qui = doc.importe_par
      ? (doc.importe_par_nom ? `${doc.importe_par_nom} (${doc.importe_par})` : doc.importe_par)
      : "";
    const quand = dateLue(doc.importe_le);
    const ou = doc.projet_origine_nom ? `, dans ${g(doc.projet_origine_nom)}` : "";
    if (qui) return `Importé par ${qui}` + (quand ? `, le ${quand}` : "") + `${ou}.`;
    if (quand) return `Importé le ${quand}${ou} ; qui l'a importé n'est pas écrit.`;
    return "Ni la date ni l'auteur de l'import ne sont écrits"
      + (doc.projet_origine_nom ? ` ; projet d'origine ${g(doc.projet_origine_nom)}` : "") + ".";
  }

  /* Où un document est employé : une ligne par copie RANGÉE, « Projet : collections ». */
  function emplois(doc) {
    return (doc.copies || []).filter((c) => (c.collections || []).length).map((c) =>
      `${c.projet_nom || "projet inconnu"} : ${c.collections.map((x) => x.nom).join(", ")}`);
  }

  /* Le titre d'un document : celui de sa première copie. */
  function titreDocument(doc) {
    const c = (doc.copies || [])[0];
    return c ? c.titre : `Document ${doc.id}, sans copie`;
  }

  /* Les genres de demande qui sont des SUPPRESSIONS. Les seuls auxquels « Détruire »
     (ou « Supprimer le projet ») répond : la relecture croisée du serveur de la prise avait
     trouvé une entrée de documents présentée en suppression, et ACCEPTÉE par « Détruire »
     (défaut 1). */
  const GENRES_SUPPRESSION = [GENRE_DOCUMENT, GENRE_PROJET];
  function estUneSuppression(d) {
    return !!d && GENRES_SUPPRESSION.includes(d.genre);
  }

  /* CHAQUE GENRE A SES MOTS (COL-3, écran de la 3a, tranché par Hugo sur maquette le
     2026-10-17) : son nom sur la ligne de « À faire », sa CLASSE (la couleur de tranche — une
     par genre, posée par la feuille de style), et les libellés de ses deux réponses. Jamais
     « Détruire / Garder » hors d'une suppression de document. Un genre que l'écran ne connaît
     pas se dit « Demande », sans aucun bouton : un geste qu'on ne sait pas nommer ne
     s'offre pas. `accepter` et `refuser` sont des fonctions de la demande : un rejoindre et
     un retour nomment leur collection d'arrivée. Pour une entrée, ce sont les réponses d'UN
     document ; « Tout accepter (n) » et « Refuser le reste » valent pour celles qui
     attendent (`toutAccepter`, `refuserLeReste`). */
  const nomArrivee = (d) => g(d.collection_nom || `collection ${d.collection_id}`);
  const GENRES = {
    [GENRE_DOCUMENT]: { libelle: "Supprimer un document", classe: "document",
                        accepter: () => "Détruire", refuser: () => "Garder" },
    [GENRE_PROJET]: { libelle: "Supprimer un projet", classe: "projet",
                      accepter: () => "Supprimer le projet", refuser: () => "Garder" },
    [GENRE_ENTREE]: { libelle: "Entrée de documents", classe: "entree",
                      accepter: () => "Accepter", refuser: () => "Refuser" },
    [GENRE_REJOINDRE]: { libelle: "Rejoindre un travail", classe: "rejoindre",
                         accepter: (d) => `Accepter : ranger aussi dans ${nomArrivee(d)}`,
                         refuser: () => "Refuser" },
    [GENRE_RENDRE]: { libelle: "Rendre une copie gardée", classe: "rendre",
                      accepter: (d) => `Rendre à ${nomArrivee(d)}`,
                      refuser: () => "Garder au fonds" },
  };

  /* Ce qu'un écran sait d'un genre : { connu, libelle, classe, accepter, refuser } —
     `accepter` et `refuser` déjà évalués pour CETTE demande, chaîne vide pour un genre
     inconnu. */
  function genreDemande(d) {
    const e = d && GENRES[d.genre];
    if (!e) return { connu: false, libelle: "Demande", classe: "autre", accepter: "", refuser: "" };
    return { connu: true, libelle: e.libelle, classe: e.classe,
             accepter: e.accepter(d), refuser: e.refuser(d) };
  }

  /* Les réponses globales d'une entrée de documents, avec le nombre de documents qui
     attendent encore leur réponse. */
  function attente(d) {
    return (d.documents || []).filter((x) => !x.reponse).length;
  }
  function toutAccepter(d) { return `Tout accepter (${attente(d)})`; }
  const REFUSER_LE_RESTE = "Refuser le reste";

  /* L'ÉTAT d'une demande, pour qui l'a déposée (fiche du projet, D9) : en attente, acceptée,
     refusée, acceptée en partie. `code` sert de classe ; `libelle` se lit. */
  function etatDemande(d) {
    if (!d || d.reponse === null || d.reponse === undefined) {
      return { code: "attente", libelle: "en attente" };
    }
    if (d.reponse === ACCEPTER) return { code: "acceptee", libelle: "acceptée" };
    if (d.reponse === REFUSER) return { code: "refusee", libelle: "refusée" };
    if (d.reponse === PARTIELLE) return { code: "partielle", libelle: "acceptée en partie" };
    return { code: "autre", libelle: String(d.reponse) };
  }

  /* La réponse d'UN document d'une entrée, pour la fiche du projet : « entré dans … »,
     « refusé », « en attente ». */
  function etatLigne(x, d) {
    if (x.reponse === ACCEPTER) return { code: "acceptee", libelle: `entré dans ${nomArrivee(d)}` };
    if (x.reponse === REFUSER) return { code: "refusee", libelle: "refusé" };
    return { code: "attente", libelle: "en attente" };
  }

  /* La phrase d'une demande, pour qui y répond. Une suppression se dit suppression ; un autre
     genre ne l'est JAMAIS, même mal connu de l'écran. */
  function texteDemande(d) {
    const qui = d.demandeur_nom || d.demandeur || "Quelqu'un";
    const titres = (d.documents || []).map((x) => g(x.titre || "document " + x.document_id));
    if (d.genre === GENRE_PROJET) {
      return `${qui} demande la suppression du projet ${g(d.projet_nom || "projet " + d.projet_id)}`;
    }
    if (d.genre === GENRE_DOCUMENT) {
      return `${qui} demande la suppression définitive de ${et(titres) || "un document"}`;
    }
    const ou = d.collection_nom ? ` dans ${g(d.collection_nom)}` : "";
    if (d.genre === GENRE_ENTREE) {
      const n = (d.documents || []).length;
      return `${qui} demande l'entrée de ${n > 2 ? `${n} documents` : et(titres) || "documents"}${ou}`;
    }
    if (d.genre === GENRE_REJOINDRE) {
      return `${qui} demande à ranger aussi ${et(titres) || "une copie"}${ou}`;
    }
    if (d.genre === GENRE_RENDRE) {
      return `${qui} demande à rendre ${et(titres) || "une copie gardée"} à `
        + `${d.collection_nom ? g(d.collection_nom) : "une collection"}`;
    }
    return `${qui} a déposé une demande`;
  }

  /* Ce que la réponse FERA, dit sous la demande dépliée — pour les trois genres qui ne sont
     pas des suppressions. Rien pour une suppression : son détail est ailleurs (le motif, la
     certification, le travail des autres). */
  function explicationDemande(d) {
    const qui = d.demandeur_nom || d.demandeur || "le demandeur";
    if (d.genre === GENRE_ENTREE) {
      return `Chaque document accepté entre dans ${nomArrivee(d)} avec une copie de travail `
        + `vierge, créée au nom de ${qui}. Un document déjà dans le projet y reçoit une `
        + "seconde copie.";
    }
    if (d.genre === GENRE_REJOINDRE) {
      return `Accepter range aussi cette copie dans ${nomArrivee(d)} : le travail est alors `
        + "partagé entre ces collections, et ce qui s'y fait d'un côté se voit de l'autre.";
    }
    if (d.genre === GENRE_RENDRE) {
      // D'où elle était sortie, quand le serveur le sait (`sortie_de`, lu au journal) : un
      // travail fait dans une collection fermée ne se rend pas, sans le savoir, dans une
      // base ouverte à tout le projet.
      const sortie = d.sortie_de
        ? ` Elle était sortie de ${g(d.sortie_de)}`
          + (d.sortie_de !== d.collection_nom ? " : la rendre ailleurs ouvre son travail à "
            + `ceux qui entrent dans ${nomArrivee(d)}.` : ".")
        : "";
      return `Copie de ${g(d.projet_nom || "son projet")}, gardée au fonds avec son travail.`
        + `${sortie} « Rendre » la range dans ${nomArrivee(d)}, la collection que le `
        + "responsable a nommée ; « Garder au fonds » la laisse où elle est.";
    }
    return "";
  }

  /* « Certifié par … le … » : la certification d'une demande, pour qui y répond. Rien pour
     une demande qui n'en porte pas (un projet). */
  function certifiee(d) {
    if (!d || !d.certifie_le) return "";
    const qui = d.demandeur_nom || d.demandeur || "le demandeur";
    return `Certifié par ${qui}`
      + (d.demandeur_collectif ? ` (${COMPTE_PARTAGE})` : "")
      + ` le ${dateLue(d.certifie_le)} : ces données ne sont pas importantes.`;
  }

  /* Derrière un compte partagé, un login n'est pas une personne (relecture croisée de la
     tranche 2) : « personne d'autre » et « certifié par » se disent avec cette réserve.
     Le serveur dit quels comptes sont partagés (`collectif`, `demandeur_collectif`). */
  const COMPTE_PARTAGE = "compte partagé : plusieurs personnes peuvent avoir travaillé "
    + "sous ce login";

  /* Les sortes de gestes que la règle de suppression lit, dites pour un humain. La clé est
     la `sorte` que rend le serveur (`autorisation.sql_actes_sur_album`) : la cible d'un
     acte au journal, ou la table lue. Une sorte inconnue se dit telle quelle plutôt que de
     disparaître. */
  const SORTES = {
    regions: ["geste sur une case ou une bulle", "gestes sur des cases ou des bulles"],
    annotations: ["annotation", "annotations"],
    bulle_locuteur: ["locuteur", "locuteurs"],
    personnage_presence: ["présence de personnage", "présences de personnage"],
    region_attribut: ["attribut de case", "attributs de case"],
    token_correction: ["correction grammaticale", "corrections grammaticales"],
    planches: ["validation de planche", "validations de planche"],
    document: ["geste sur le document (import, scan, notice)",
               "gestes sur le document (import, scans, notice)"],
  };

  function gestes(compte) {
    return Object.entries(compte || {})
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([sorte, n]) => {
        const mots = SORTES[sorte] || [sorte, sorte];
        return `${n} ${n > 1 ? mots[1] : mots[0]}`;
      }).join(", ");
  }

  /* Ce que les AUTRES ont fait sur le document d'une demande, pour l'administrateur qui y
     répond (Hugo, 2026-10-15). `doc` : une entrée de `documents` dans `GET /api/demandes`.
     Rend { origine, lignes, vide } — `origine` dit qui a importé, ou que ce n'est pas écrit ;
     une ligne par personne, « Nom (login) : n gestes … — dernier le … », et une pour les
     gestes dont l'auteur n'est pas écrit ; `vide` dit qu'il n'y a personne d'autre.
     `undefined` si le serveur n'a rien rendu (une demande répondue). */
  function travailDesAutres(doc) {
    if (!doc || !Array.isArray(doc.travail_des_autres)) return undefined;
    const nomme = (login, nom) => (nom && nom !== login ? `${nom} (${login})` : login);
    // « Créée » et non « importé » (COL-3, tranche 3a) : la règle lit qui a créé CETTE copie
    // (`creee_par`), qui n'est l'importateur du document que pour sa copie d'origine.
    let origine;
    if (doc.creee_par) {
      origine = `Copie créée par ${nomme(doc.creee_par, doc.creee_par_nom)}`
        + (doc.importe_par && doc.importe_par !== doc.creee_par
          ? ` ; document importé par ${nomme(doc.importe_par, doc.importe_par_nom)}.` : ".");
    } else if (doc.importe_par) {
      origine = `Importé par ${nomme(doc.importe_par, doc.importe_par_nom)}.`;
    } else {
      origine = "Qui a créé cette copie n'est pas écrit (un album d'avant le fonds) : tout "
        + "geste compte comme celui d'un autre.";
    }
    const lignes = doc.travail_des_autres.map((e) => {
      const qui = e.agent
        ? (e.agent_nom && e.agent_nom !== e.agent ? `${e.agent_nom} (${e.agent})` : e.agent)
        : "Auteur non écrit";
      const quand = e.dernier ? ` — dernier le ${dateLue(e.dernier)}` : "";
      return `${qui} : ${gestes(e.gestes)}${quand}`
        + (e.collectif ? ` (${COMPTE_PARTAGE})` : "");
    });
    return {
      origine, lignes, vide: !lignes.length,
      // Ce sont des GESTES lus au journal, pas ce qui reste sur les planches.
      titre: "Gestes d'autres personnes, lus au journal — un geste défait depuis compte "
        + "encore :",
      texteVide: "Personne d'autre que le demandeur n'y a laissé de geste"
        + (doc.demandeur_collectif ? ` — mais c'est un ${COMPTE_PARTAGE}.` : "."),
    };
  }

  /* La ligne sous une demande : quand, et si la même a déjà été refusée. */
  function contexteDemande(d) {
    const parts = [];
    if (d.date_creation) parts.push(`le ${dateLue(d.date_creation)}`);
    if (d.genre === GENRE_DOCUMENT && d.projet_nom) parts.push(`depuis ${g(d.projet_nom)}`);
    else if (d.genre !== GENRE_PROJET && d.projet_nom) parts.push(`projet ${g(d.projet_nom)}`);
    if (d.refus_anterieurs) {
      parts.push(d.refus_anterieurs === 1 ? "déjà refusée une fois"
                                          : `déjà refusée ${d.refus_anterieurs} fois`);
    }
    return parts.join(" · ");
  }

  /* Ce que coûte « Détruire », dit avant de le faire. Accepter une demande ne détruit que la
     COPIE demandée (D5) : ses images partent avec elle, sauf si une autre copie du document
     les emploie (`soeur`, D6) — et la phrase ne dit pas où vit cette autre copie. */
  function confirmationDetruire(titre, soeur) {
    return `Détruire cette copie de ${g(titre)} ? Tout le travail fait dessus est effacé`
      + (soeur ? `. ${IMAGES_RESTENT}` : ", ses images aussi.") + " Irréversible.";
  }

  /* Détruire un DOCUMENT que personne n'appelle, depuis le fonds : toutes ses copies partent,
     et ses images avec. */
  function confirmationDetruireDocument(titre, nCopies) {
    const n = nCopies || 1;
    return `Détruire ${g(titre)} ? Ses images et le travail de `
      + (n > 1 ? `ses ${n} copies` : "sa copie") + " sont effacés. Irréversible.";
  }

  /* Les collections où « Rendre à… » peut ranger une copie gardée : celles de SON projet —
     le serveur refuse toute autre — ou, pour une copie importée au fonds qui n'en a jamais
     eu, toutes. `collections` : ce que rend `GET /api/collections` (avec `projet_id`). */
  function rendreA(copie, collections) {
    const ou = (collections || []).filter((c) => c.ecrivable !== false);
    return copie.projet_id == null ? ou : ou.filter((c) => c.projet_id === copie.projet_id);
  }

  return {
    GENRE_DOCUMENT, GENRE_PROJET, GENRE_ENTREE, GENRE_REJOINDRE, GENRE_RENDRE,
    GENRES_SUPPRESSION, estUneSuppression, genreDemande, etatDemande, etatLigne,
    toutAccepter, REFUSER_LE_RESTE, explicationDemande, IMAGES_RESTENT,
    ACCEPTER, REFUSER, PARTIELLE, CERTIFICATION, SORTES,
    dateLue, demandeur, pastille, offrir, retrait, definitif, apresRetrait, apresDefinitif,
    origine, emplois, titreDocument, texteDemande, contexteDemande, confirmationDetruire,
    confirmationDetruireDocument, rendreA, certifiee, gestes, travailDesAutres,
  };
});
