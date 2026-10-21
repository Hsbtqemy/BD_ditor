/* L'import de planches EN LOT (UX-11) — sa logique, sans DOM.
   Chargé en <script> par la Bibliothèque → expose `window.BDImport` ; aussi require()-able
   par `tests/js/import-planches.test.js`, qui la vérifie par tables de cas. Rien n'est lu au
   chargement : ni le document, ni `fetch`, ni l'adresse — l'envoi d'un fichier est PASSÉ par
   l'appelant, et c'est `apiSend` (lib/common.js), le chemin de toute écriture.

   CE QUE LA MESURE A IMPOSÉ (2026-10-21, vrais scans, image de production) : une planche
   coûte ~0,5 s en TIFF et ~5,7 s en JPEG 2000 sans perte, sans compter le téléversement
   (52 Mo par TIFF). Un album de cinquante pages prend donc des minutes, et la forme en
   découle :

     · UN FICHIER PAR REQUÊTE, L'UN APRÈS L'AUTRE — la route de l'Atelier,
       `POST /api/albums/{id}/import`, et aucune autre. Un lot dans une seule requête
       tiendrait le verrou d'écriture de SQLite des minutes durant : les autres écritures
       attendraient 5 s puis recevraient un 409. Et un fichier importé est en base dès sa
       réponse : un échec plus loin ne défait rien.
     · L'ORDRE DES NOMS, pas celui du sélecteur du système, qui est arbitraire : le numéro
       d'une planche est son rang d'arrivée, et le numéro éditorial en dérive
       (`database.numeros_editoriaux`). Les nombres s'y lisent comme des nombres (« p2 »
       avant « p10 ») : un nom sans zéros en tête se range comme on le lit.
     · UN ÉCHEC NOMME SON FICHIER ET N'ARRÊTE PAS LES SUIVANTS. Seul un refus qui porte sur
       l'ALBUM et non sur le fichier arrête la série — l'album n'est plus à votre portée
       (404) ou l'identité manque (401, 403) : les fichiers suivants recevraient la même
       réponse, et cinquante lignes identiques ne disent rien de plus qu'une.
     · UNE PROGRESSION QUI DIT « n sur N » et le nom en cours, puis UN BILAN. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDImport = api;                                                   // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const pluriel = (n, un, plus) => `${n} ${n > 1 ? (plus || un + "s") : un}`;

  /* L'ordre d'envoi : le nom, les nombres lus comme des nombres, sans égard à la casse ni
     aux accents ; à égalité, l'ordre exact des caractères, pour qu'un même choix donne
     toujours le même ordre. Rend une COPIE : la sélection reçue n'est pas touchée. */
  const COLLATION = new Intl.Collator("fr", { numeric: true, sensitivity: "base" });
  function ordonner(fichiers) {
    return Array.from(fichiers || []).sort((a, b) =>
      COLLATION.compare(a.name, b.name) || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  }

  /* Un refus qui porte sur l'album, et non sur le fichier : la série s'arrête. */
  const STATUTS_D_ALBUM = [401, 403, 404];
  function arreteLaSerie(statut) { return STATUTS_D_ALBUM.includes(statut); }

  /* Envoie les fichiers UN PAR UN, dans l'ordre des noms, et rend le bilan.
     `envoyer(fichier)` : une promesse, rejetée par une erreur qui porte `statut` et un
     message lisible (celle d'`apiSend`). `surProgres(etat)` est appelé AVANT chaque envoi
     (`{ fait, total, nom, echecs }`) puis une fois à la fin (`nom` vide). `doitArreter()` :
     relu entre deux fichiers — l'envoi en cours va jusqu'au bout. */
  async function importerEnLot(fichiers, envoyer, options = {}) {
    const surProgres = options.surProgres || (() => {});
    const doitArreter = options.doitArreter || (() => false);
    const liste = ordonner(fichiers);
    const bilan = { total: liste.length, importes: [], echecs: [], nonEnvoyes: [],
                    arret: null };
    for (let i = 0; i < liste.length; i++) {
      const f = liste[i];
      if (doitArreter()) {
        bilan.arret = "demande";
        bilan.nonEnvoyes = liste.slice(i).map((x) => x.name);
        break;
      }
      surProgres({ fait: i, total: liste.length, nom: f.name, echecs: bilan.echecs.length });
      try {
        const planche = await envoyer(f);
        bilan.importes.push({ nom: f.name, planche });
      } catch (e) {
        const message = (e && e.message) || "échec de l'envoi";
        bilan.echecs.push({ nom: f.name, message });
        if (e && arreteLaSerie(e.statut)) {
          bilan.arret = "album";
          bilan.nonEnvoyes = liste.slice(i + 1).map((x) => x.name);
          break;
        }
      }
    }
    surProgres({ fait: bilan.importes.length + bilan.echecs.length, total: liste.length,
                 nom: "", echecs: bilan.echecs.length });
    return bilan;
  }

  /* Ce que dit la ligne d'état pendant l'import : le rang du fichier ENVOYÉ, sur le
     total, et son nom ; les échecs déjà vus, s'il y en a. */
  function libelleProgression(etat) {
    const e = etat || {};
    const rang = `${Math.min((e.fait || 0) + 1, e.total || 0)} sur ${e.total || 0}`;
    const echecs = e.echecs ? ` · ${pluriel(e.echecs, "échec")}` : "";
    return `${rang} — ${e.nom || ""}${echecs}`;
  }

  /* Le bilan, en une ligne : ce qui est entré, ce qui a échoué, ce qui n'est pas parti. Le
     détail des échecs se lit à part, fichier par fichier (`bilan.echecs`). */
  function libelleBilan(bilan) {
    const b = bilan || {};
    const n = (b.importes || []).length, k = (b.echecs || []).length;
    const m = (b.nonEnvoyes || []).length;
    const parts = [n ? `${pluriel(n, "planche importée", "planches importées")}`
                     : "Aucune planche importée"];
    if (k) parts.push(pluriel(k, "échec"));
    let phrase = parts.join(", ");
    if (m) {
      phrase += ` — ${pluriel(m, "fichier non envoyé", "fichiers non envoyés")}`
        + (b.arret === "album" ? " : l'album n'accepte plus d'import de votre part"
                               : " : import arrêté");
    }
    return phrase;
  }

  /* Le ton du bilan : rien d'entré se lit comme une erreur ; un import partiel, neutre ;
     tout entré, un succès. */
  function tonBilan(bilan) {
    const b = bilan || {};
    const n = (b.importes || []).length;
    if (!n) return "erreur";
    return (b.echecs || []).length || (b.nonEnvoyes || []).length ? "partiel" : "succes";
  }

  return { ordonner, arreteLaSerie, importerEnLot, libelleProgression, libelleBilan, tonBilan,
           STATUTS_D_ALBUM };
});
