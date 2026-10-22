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
     · UNE PROGRESSION QUI DIT « n sur N » et le nom en cours, puis UN BILAN — qui dit,
       depuis le 2026-10-22, quel fichier est devenu quelle planche.

   L'ORDRE DES PLANCHES vit ici aussi (UX-11, 2026-10-22) : « Ranger par nom de fichier »
   reprend l'ordre naturel des noms qui range un import en lot — il ne s'écrit qu'une fois —,
   et ↑ ↓ déplacent une planche d'un cran. */
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

  /* ── Quel fichier est devenu quelle planche (UX-11, Hugo, 2026-10-22) ──────────────────
     Le numéro d'une planche est son RANG : dans un dossier mal nommé, l'ordre d'import peut
     défaire un ordre que seul l'utilisateur connaît, et le nom du fichier reste son seul
     repère. Le bilan le dit donc, fichier par fichier. */

  /* Le nom court d'une planche, tel que la fiche le montre en gras : « planche 3 » pour le
     récit (le numéro ÉDITORIAL, celui qu'on cite), « paratexte i.003 » sinon. */
  function libellePlanche(p) {
    const imp = `i.${String(p.numero).padStart(3, "0")}`;
    return p.role === "recit" && p.numero_editorial ? `planche ${p.numero_editorial}`
                                                    : `paratexte ${imp}`;
  }

  /* Une ligne par fichier ENTRÉE, dans l'ordre d'envoi : `{ nom, planche }`. La planche se
     lit dans la liste ACTUELLE de l'album (`planches`), par son identifiant : relu après un
     réordonnancement ou un changement de rôle, le bilan dit où elle est maintenant. Une
     planche qui n'y est plus (supprimée depuis) le dit. */
  function correspondances(bilan, planches) {
    const parId = new Map((planches || []).map((p) => [p.id, p]));
    return ((bilan && bilan.importes) || []).map((x) => {
      const p = x.planche && parId.get(x.planche.id);
      return { nom: x.nom, planche: p ? libellePlanche(p) : "planche supprimée depuis" };
    });
  }

  /* Un refus du serveur NOMME déjà le fichier (« page-3.tif n'est pas une image lisible :
     … ») ; le bilan le met en gras sans le répéter. Un message qui ne le nomme pas (un
     refus de l'album, une panne) garde « nom : message ». Rend `{ nom, suite }`, la suite
     commençant par son propre séparateur. */
  function ligneEchec(echec) {
    const nom = (echec && echec.nom) || "";
    const message = (echec && echec.message) || "";
    if (nom && message.startsWith(nom + " ")) return { nom, suite: message.slice(nom.length) };
    return { nom, suite: ` : ${message}` };
  }

  /* ── Changer l'ordre des planches (UX-11, Hugo, 2026-10-22) ─────────────────────────────
     Le serveur reçoit l'ordre ENTIER, en identifiants (`PUT /api/albums/{id}/ordre-des-
     planches`) ; ces fonctions le calculent à partir de la liste affichée, dans son ordre. */

  /* Monter (`sens` -1) ou descendre (+1) une planche d'un cran : le nouvel ordre, ou null si
     elle est déjà au bord — ou absente. */
  function deplacer(ids, id, sens) {
    const i = (ids || []).indexOf(id), j = i + sens;
    if (i < 0 || (sens !== -1 && sens !== 1) || j < 0 || j >= ids.length) return null;
    const ordre = ids.slice();
    [ordre[i], ordre[j]] = [ordre[j], ordre[i]];
    return ordre;
  }

  /* « Ranger par nom de fichier » : l'ordre NATUREL des noms d'origine (`nom_fichier_origine`,
     la règle de l'import en lot — p2 avant p10, ni casse ni accents), à égalité l'ordre
     exact des caractères puis l'ordre actuel. Les planches sans nom noté (importées avant
     que l'outil le note) gardent leur ordre relatif, EN TÊTE : elles sont les plus
     anciennes de l'album. Rend `{ ordre, deplacees, sansNom, avecNom }` — `deplacees` :
     combien changent de rang. */
  function ordreParNom(planches) {
    const liste = Array.from(planches || []);
    const rang = new Map(liste.map((p, i) => [p.id, i]));
    const sans = liste.filter((p) => !p.nom_fichier_origine);
    const avec = liste.filter((p) => p.nom_fichier_origine).sort((a, b) => {
      const x = a.nom_fichier_origine, y = b.nom_fichier_origine;
      return COLLATION.compare(x, y) || (x < y ? -1 : x > y ? 1 : 0)
        || rang.get(a.id) - rang.get(b.id);
    });
    const ordre = sans.concat(avec).map((p) => p.id);
    const deplacees = ordre.filter((id, i) => rang.get(id) !== i).length;
    return { ordre, deplacees, sansNom: sans.length, avecNom: avec.length };
  }

  /* Ce que dit le geste avant d'agir. `confirmer` : la question à poser, ou null quand il
     n'y a rien à faire — `message` dit alors pourquoi. */
  function phraseRangerParNom(plan) {
    const p = plan || {};
    if (!p.avecNom) {
      return { confirmer: null, message: "Aucune planche de cet album n'a de nom de fichier "
        + "noté : elles ont été importées avant que l'outil le note." };
    }
    if (!p.deplacees) {
      return { confirmer: null, message: "Les planches sont déjà dans l'ordre des noms de fichier." };
    }
    let q = `Ranger les planches dans l'ordre des noms de fichier ?\n\n`
      + `${pluriel(p.deplacees, "planche change", "planches changent")} de place. `
      + "Les numéros éditoriaux et les citations « pl·c·b » qui en dérivent changent : une "
      + "citation faite avec l'ancien numéro ne désignera plus la même planche.";
    if (p.sansNom) {
      q += `\n\n${pluriel(p.sansNom, "planche n'a", "planches n'ont")} pas de nom de fichier `
        + `noté (importée${p.sansNom > 1 ? "s" : ""} avant que l'outil le note) : `
        + `${p.sansNom > 1 ? "elles restent" : "elle reste"} en tête, dans `
        + `${p.sansNom > 1 ? "leur" : "son"} ordre actuel.`;
    }
    return { confirmer: q, message: null };
  }

  return { ordonner, arreteLaSerie, importerEnLot, libelleProgression, libelleBilan, tonBilan,
           STATUTS_D_ALBUM, libellePlanche, correspondances, ligneEchec, deplacer, ordreParNom,
           phraseRangerParNom };
});
