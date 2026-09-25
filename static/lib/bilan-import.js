/* Bilan d'un import de vocabulaire (AUTH-11) — logique PURE, sans DOM.
   Chargé en <script> AVANT exploration.js → expose `window.BDBilanImport` ; aussi
   require()-able par `tests/js/bilan-import.test.js`.

   `POST /api/lexique/importer` compte les lignes REFUSÉES par motif (`resume.refusees`)
   depuis AUTH-11, et l'écran ne les lisait pas : un import dont toutes les lignes étaient
   refusées annonçait « Import : 0 domaine(s), 0 dimension(s), 0 valeur(s) créé(s) » — la
   phrase d'un import qui a réussi sans rien trouver de neuf —, puis empilait un toast par
   ligne, illisible sur un gros fichier.

   Trois règles :

   1. LE SERVEUR NOMME, L'ÉCRAN RECOPIE. Les motifs se disent avec les mots de
      `lexique_import.MOTIFS` (le test JS confronte les deux tables). « Libellé déjà pris »
      est la limite d'UN bit que le serveur accepte de dire : il ne dit pas OÙ le libellé
      est pris, et l'écran ne doit pas l'élargir en « terme caché » ou « dans une autre
      collection ». Un motif que cette table ne connaît pas s'affiche sous sa clé brute
      plutôt que de disparaître — une ligne refusée qu'on ne compterait pas serait le
      défaut même que ce module répare.
   2. UN IMPORT OÙ RIEN N'EST ENTRÉ NE RESSEMBLE PAS À UN SUCCÈS. Il ne dit pas « 0 créé » :
      il dit « Rien n'a été importé », et son ton est celui d'une erreur. Un import
      partiel garde un ton neutre — une partie est entrée, et les mots portent le reste.
   3. LE DÉTAIL SE BORNE. Les `max` premières lignes, puis « … et K autres » : sur un
      fichier de trois cents lignes, trois cents messages ne se lisent pas. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDBilanImport = api;                                              // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Miroir de `lexique_import.MOTIFS`, dans le même ordre. */
  const MOTIFS = {
    libelle_pris: "libellé déjà pris",
    lecture_seule: "en lecture seule pour vous",
    parent_ailleurs: "hors de la collection de son parent",
  };

  const DETAILS_MAX = 10;

  /* « 0 valeur », « 1 valeur », « 2 valeurs » : le français met le singulier à 0 et 1. */
  function nombre(n, singulier, pluriel) {
    return `${n} ${n > 1 ? pluriel : singulier}`;
  }

  /* `out` = la réponse de la route ({resume, lignes, anomalies, avertissements}).
     Rend { ton, texte, details, reste } :
     - `ton` : "success" (tout est entré, rien à signaler), "" (neutre : entré en partie,
       ou entré avec des avertissements), "error" (rien n'est entré) — les classes de
       `toast()` ;
     - `texte` : la phrase de synthèse ;
     - `details` : au plus `max` messages ligne par ligne (anomalies de format d'abord,
       puis avertissements, dans l'ordre du serveur) ;
     - `reste` : combien n'y figurent pas. */
  function bilan(out, max = DETAILS_MAX) {
    const s = (out && out.resume) || {};
    const refus = s.refusees || {};
    const compte = (palier) => (s[palier] && s[palier].cree) || 0;

    const cles = Object.keys(MOTIFS)
      .concat(Object.keys(refus).filter((k) => !(k in MOTIFS)));
    const presents = cles.filter((k) => (refus[k] || 0) > 0);
    const nbRefusees = presents.reduce((t, k) => t + refus[k], 0);
    const anomalies = (out && out.anomalies) || [];
    const avertissements = (out && out.avertissements) || [];
    const appliquees = Math.max(0, ((out && out.lignes) || 0) - nbRefusees);

    const phrases = [];
    if (appliquees > 0) {
      phrases.push(`Import : ${nombre(compte("domaines"), "domaine", "domaines")}, `
        + `${nombre(compte("dimensions"), "dimension", "dimensions")}, `
        + `${nombre(compte("valeurs"), "valeur", "valeurs")} créés.`);
    } else {
      phrases.push("Rien n'a été importé.");
    }
    if (nbRefusees > 0) {
      phrases.push(`${nombre(nbRefusees, "ligne refusée", "lignes refusées")} : `
        + presents.map((k) => `${MOTIFS[k] || k} (${refus[k]})`).join(", ") + ".");
    }
    if (anomalies.length > 0) {
      phrases.push(`${nombre(anomalies.length, "ligne mal formée", "lignes mal formées")}, `
        + `ignorée${anomalies.length > 1 ? "s" : ""}.`);
    }
    if (appliquees === 0 && nbRefusees === 0 && anomalies.length === 0) {
      phrases.push("Le fichier ne contient aucune ligne.");
    }

    const tous = anomalies.concat(avertissements);
    const details = tous.slice(0, max);
    let ton = "success";
    if (appliquees === 0) ton = "error";
    else if (tous.length > 0 || nbRefusees > 0) ton = "";

    return { ton, texte: phrases.join(" "), details, reste: tous.length - details.length };
  }

  /* La ligne qui clôt une liste tronquée — vide si rien n'a été coupé. */
  function suite(reste) {
    return reste > 0 ? `… et ${nombre(reste, "autre", "autres")}.` : "";
  }

  /* Le menu « Importer dans » : les collections où l'on ÉCRIT (`ecrivable`, AUTH-12 — comme
     la modale d'album), précédées de « Global ». Il proposait toutes les collections LUES,
     et choisir l'une d'elles répondait « Collection introuvable ».

     Sans collection où écrire, « Global » échouerait aussi (la route exige d'écrire
     QUELQUE PART) : l'import se ferme, et une NOTE dit pourquoi — pas un menu désactivé,
     qu'on n'atteint pas au clavier (même patron que `#m-collection-note` dans corpus.js).
     Sauf sous une portée TOTALE (`acces.total` de /api/moi — administrateur, mono-poste),
     qui écrit partout, même avant qu'une collection existe : « Global » y reste ouvert.

     `avant` est la valeur choisie au remplissage précédent. Le menu se reremplit à chaque
     rechargement du lexique — après un import, un domaine changé — et revenir à « Global »
     enverrait le réimport d'un fichier corrigé dans le vocabulaire de TOUTE l'instance,
     sans que personne l'ait choisi. Elle est gardée tant qu'elle figure parmi les options.
     Rend { ouvert, options: [{ value, label }], valeur, note }. */
  const SANS_ECRITURE = "Vous n'écrivez dans aucune collection : l'import de vocabulaire "
    + "vous est fermé. Demandez un accès en écriture au propriétaire d'une collection.";
  function menuImport(collections, total, avant) {
    const ecr = (collections || []).filter((c) => c.ecrivable);
    if (!ecr.length && !total) {
      return { ouvert: false, options: [], valeur: "", note: SANS_ECRITURE };
    }
    const options = [{ value: "", label: "Global" }]
      .concat(ecr.map((c) => ({ value: String(c.id), label: c.nom })));
    const garde = avant != null && options.some((o) => o.value === String(avant));
    return { ouvert: true, options, valeur: garde ? String(avant) : "", note: "" };
  }

  return { MOTIFS, DETAILS_MAX, SANS_ECRITURE, nombre, bilan, suite, menuImport };
});
