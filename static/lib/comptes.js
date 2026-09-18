/* « 👥 Comptes et groupes » (AUTH-12, étape 2) — la logique PURE du bloc, sans DOM.
   Chargé en <script> AVANT administration.js → expose `window.BDComptes` ; aussi
   require()-able par `tests/js/comptes.test.js`, qui la vérifie par tables de cas.

   CE QUI N'EST PAS ICI, et c'est le contrat accordé avec le serveur : la fusion des comptes
   (annuaire, miroir `utilisateur`, accès) et le calcul de « À regarder », ordre compris.
   `GET /api/comptes-et-groupes` les rend faits. Les refaire côté client fabriquerait la
   seconde source que la page existe pour éviter (UX-10) — et celle qui se tromperait serait
   la muette.

   CE QUI EST ICI : ce que l'écran fait des données sans rien en conclure sur les droits —
   trier, filtrer, dire l'état court d'une ligne, regrouper les signaux trop nombreux, lire
   et écrire l'adresse, et nommer ce que le serveur rend par des codes.

   AUCUN NIVEAU ni acte ici : depuis l'étape 3, ce qu'un accès permet se dit en actes, lus
   dans la description servie par le serveur (`static/lib/droits.js`). La table de libellés
   de niveaux qui vivait ici à l'étape 2 est partie avec elle. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDComptes = api;                                                  // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const AXES = ["comptes", "groupes", "collections"];
  const TRIS = ["alpha", "recents"];
  /* Le paramètre d'adresse qui porte la sélection, par axe. Un par axe plutôt qu'un `sel`
     générique : `?groupe=etudiants-bd` se lit, et se recopie dans un message. */
  const CLE_SELECTION = { comptes: "compte", groupes: "groupe", collections: "collection" };
  const TYPE_DE_L_AXE = { comptes: "compte", groupes: "groupe", collections: "collection" };
  const AXE_DU_TYPE = { compte: "comptes", groupe: "groupes", collection: "collections" };

  /* Décision de Hugo du 2026-09-17 : AU-DELÀ de cinq signaux du même code, une seule ligne
     dépliable. Trente arrivants à la rentrée feraient sinon trente lignes dans une liste
     dépliée en tête, et la liste des objets passerait sous l'écran. */
  const SEUIL_REGROUPEMENT = 5;

  const COLLATION = new Intl.Collator("fr", { sensitivity: "base", numeric: true });

  /* Le nom LU : celui qu'on voit à l'écran et donc celui sur lequel « A → Z » doit porter.
     Un compte sans nom lisible se lit par son login. */
  function nomLu(objet, axe) {
    if (axe === "comptes") return objet.nom || objet.login;
    return String(objet.nom);
  }

  /* L'identifiant stable d'un objet dans son axe — ce que l'adresse porte. */
  function identifiant(objet, axe) {
    if (axe === "comptes") return objet.login;
    if (axe === "groupes") return objet.nom;
    return objet.id;
  }

  /* La date de « Récents d'abord » : la dernière venue d'un compte, la dernière venue d'un
     de ses membres pour un groupe, la dernière modification de sa description ou de ses
     accès pour une collection (décision du 2026-09-17 — les albums ne comptent pas). */
  function dateDe(objet, axe) {
    if (axe === "comptes") return objet.derniere_vue || null;
    if (axe === "groupes") return objet.derniere_venue || null;
    return objet.derniere_modification || null;
  }

  function comparerNoms(u, v, axe) {
    return COLLATION.compare(nomLu(u, axe), nomLu(v, axe))
      || COLLATION.compare(String(identifiant(u, axe)), String(identifiant(v, axe)));
  }

  /* Trie SANS modifier le tableau reçu. « Récents d'abord » : la plus récente en tête, ce
     qui n'a pas de date à la FIN, et les ex æquo par nom — sans quoi deux comptes venus la
     même heure (`derniere_vue` est à l'heure près) changeraient d'ordre d'un rendu à
     l'autre. */
  function trier(objets, axe, tri) {
    const copie = objets.slice();
    if (tri !== "recents") return copie.sort((u, v) => comparerNoms(u, v, axe));
    return copie.sort((u, v) => {
      const du = Date.parse(dateDe(u, axe) || ""), dv = Date.parse(dateDe(v, axe) || "");
      const au = !Number.isNaN(du), av = !Number.isNaN(dv);
      if (au !== av) return au ? -1 : 1;
      if (au && du !== dv) return dv - du;
      return comparerNoms(u, v, axe);
    });
  }

  /* Insensible à la casse ET aux accents, comme la Recherche (`remove_diacritics`) : on
     tape « chloe » pour trouver « Chloé Vasseur ». */
  function normaliser(texte) {
    return String(texte || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .toLowerCase().trim();
  }

  function filtrer(objets, axe, texte) {
    const f = normaliser(texte);
    if (!f) return objets.slice();
    return objets.filter((o) => {
      const cibles = axe === "comptes" ? [o.nom, o.login] : [o.nom];
      return cibles.some((c) => normaliser(c).includes(f));
    });
  }

  /* Ce que dit l'adresse. Une valeur inconnue retombe sur le défaut au lieu de casser le
     rendu : une adresse se recopie, se tronque, et vieillit. La sélection n'est lue QUE
     pour l'axe affiché — `?axe=groupes&compte=alice` ouvre l'axe des groupes, sans fiche. */
  function lireAdresse(search) {
    const p = new URLSearchParams(search || "");
    const axe = AXES.includes(p.get("axe")) ? p.get("axe") : "comptes";
    const tri = TRIS.includes(p.get("tri")) ? p.get("tri") : "alpha";
    const brut = p.get(CLE_SELECTION[axe]);
    let sel = null;
    if (brut !== null && brut !== "") {
      if (axe === "collections") {
        sel = /^[1-9]\d*$/.test(brut) ? Number(brut) : null;
      } else {
        sel = brut;
      }
    }
    return { axe, tri, sel };
  }

  /* L'inverse, en gardant les paramètres qui ne sont pas à ce bloc. Les défauts sont TUS :
     `/administration` reste l'adresse de la page nue, et une adresse partagée ne dit que ce
     qui a été choisi. */
  function ecrireAdresse(etat, searchActuel) {
    const p = new URLSearchParams(searchActuel || "");
    ["axe", "tri", ...Object.values(CLE_SELECTION)].forEach((k) => p.delete(k));
    if (etat.axe && etat.axe !== "comptes") p.set("axe", etat.axe);
    if (etat.tri && etat.tri !== "alpha") p.set("tri", etat.tri);
    if (etat.sel !== null && etat.sel !== undefined && etat.sel !== "") {
      p.set(CLE_SELECTION[etat.axe || "comptes"], String(etat.sel));
    }
    const s = p.toString();
    return s ? "?" + s : "";
  }

  function pluriel(n, singulier, pluriel_) {
    return `${n} ${n > 1 ? pluriel_ : singulier}`;
  }

  /* « 14/09 » dans l'année, « 14/09/2025 » au-delà : un compte venu il y a un an ne doit pas
     se lire comme venu la semaine dernière. Date LOCALE : le serveur rend de l'UTC. */
  function dateCourte(iso, maintenant) {
    const t = Date.parse(iso || "");
    if (Number.isNaN(t)) return null;
    const d = new Date(t), m = maintenant || new Date();
    const jj = String(d.getDate()).padStart(2, "0"), mm = String(d.getMonth() + 1).padStart(2, "0");
    return d.getFullYear() === m.getFullYear() ? `${jj}/${mm}` : `${jj}/${mm}/${d.getFullYear()}`;
  }

  /* L'état court d'une ligne de la liste. `etatAnnuaire` distingue un groupe qu'on n'a pas
     pu VÉRIFIER (panne) d'un groupe dont personne ne peut rien savoir (aucun annuaire) :
     écrire « non vérifié » en mono-poste ferait chercher une panne qui n'existe pas. */
  function etatCourt(objet, axe, tri, etatAnnuaire, maintenant) {
    const alerte = !!(objet.signaux && objet.signaux.length);
    if (axe === "comptes") {
      const d = dateCourte(objet.derniere_vue, maintenant);
      return { texte: d ? `vu le ${d}` : "aucune connexion", alerte };
    }
    if (axe === "groupes") {
      if (objet.dans_annuaire === false) return { texte: "absent de l'annuaire", alerte: true };
      if (objet.nb_comptes === null || objet.nb_comptes === undefined) {
        if (etatAnnuaire === "non_verifie") return { texte: "non vérifié", alerte };
        return { texte: pluriel((objet.collections || []).length, "collection", "collections"),
                 alerte };
      }
      if (tri === "recents") {
        const d = dateCourte(objet.derniere_venue, maintenant);
        return { texte: d ? `actif le ${d}` : "aucune venue", alerte };
      }
      return { texte: pluriel(objet.nb_comptes, "compte", "comptes"), alerte };
    }
    if (tri === "recents") {
      const d = dateCourte(objet.derniere_modification, maintenant);
      return { texte: d ? `modifiée le ${d}` : "jamais modifiée", alerte };
    }
    return { texte: pluriel(objet.nb_albums || 0, "album", "albums"), alerte };
  }

  const DIFFUSIONS_LUES = { public: "public", embargo: "sous embargo", restreint: "restreint",
                            prive: "privé" };
  function diffusionLue(statut) {
    if (statut === null || statut === undefined || statut === "") return null;
    return Object.prototype.hasOwnProperty.call(DIFFUSIONS_LUES, statut)
      ? DIFFUSIONS_LUES[statut] : String(statut);
  }

  /* Où mène un signal : la fiche de l'objet qui demande un geste. Un accès mort mène au
     compte ou au groupe absent — c'est lui qu'on ira chercher dans l'annuaire. */
  function cibleSignal(s) {
    switch (s.signal) {
      case "groupe_absent": return { type: "groupe", id: s.groupe };
      case "compte_absent":
      case "identite_changee":
      case "jamais_venu": return { type: "compte", id: s.login };
      case "proprietaire_absent":
      case "sans_proprietaire": return { type: "collection", id: s.collection };
      default:
        if (s.login) return { type: "compte", id: s.login };
        if (s.groupe) return { type: "groupe", id: s.groupe };
        if (s.collection !== undefined && s.collection !== null)
          return { type: "collection", id: s.collection };
        return null;
    }
  }

  /* Le texte d'un signal. Le serveur rend des CODES (contrat accordé) : les phrases vivent
     ici, à un seul endroit, dans le lexique de la décision 7. Un code inconnu se montre par
     son nom plutôt que de disparaître — un signal qu'on tait est pire qu'un signal mal dit.
     `noms` : { collections: {id → nom}, comptes: {login → nom lisible} }. */
  function texteSignal(s, noms) {
    const col = (id) => {
      const n = noms && noms.collections ? noms.collections[id] : undefined;
      return `« ${n !== undefined ? n : "collection " + id} »`;
    };
    const qui = (login) => {
      const n = noms && noms.comptes ? noms.comptes[login] : undefined;
      return n ? `${n} (${login})` : String(login);
    };
    switch (s.signal) {
      case "groupe_absent":
        return `Le groupe ${s.groupe} n'est pas dans l'annuaire (accès à ${col(s.collection)})`;
      case "compte_absent":
        return `Le compte ${s.login} n'est pas dans l'annuaire (accès à ${col(s.collection)})`;
      case "proprietaire_absent":
        return `${col(s.collection)} n'a plus de propriétaire dans l'annuaire`;
      case "sans_proprietaire":
        return `${col(s.collection)} n'a pas de propriétaire`;
      case "identite_changee":
        return `${qui(s.login)} : identité changée`;
      case "jamais_venu":
        return `${qui(s.login)} : aucune connexion`;
      default:
        return String(s.signal);
    }
  }

  function texteGroupeSignaux(code, n) {
    switch (code) {
      case "groupe_absent": return `${n} accès à des groupes absents de l'annuaire`;
      case "compte_absent": return `${n} accès à des comptes absents de l'annuaire`;
      case "proprietaire_absent": return `${n} collections sans propriétaire dans l'annuaire`;
      case "sans_proprietaire": return `${n} collections sans propriétaire`;
      case "identite_changee": return `${n} comptes à l'identité changée`;
      case "jamais_venu": return `${n} comptes jamais venus`;
      default: return `${n} × ${code}`;
    }
  }

  /* Regroupe, SANS réordonner : l'ordre est celui du serveur, et le groupe prend la place
     du premier signal de son code. « Au-delà de cinq » : cinq restent ligne à ligne, six se
     replient. Chaque code se décide seul — un code rare et grave ne se replie pas parce
     qu'un autre est nombreux. */
  function regrouperSignaux(signaux, seuil) {
    const s = seuil === undefined ? SEUIL_REGROUPEMENT : seuil;
    const compte = new Map();
    signaux.forEach((x) => compte.set(x.signal, (compte.get(x.signal) || 0) + 1));
    const sortie = [], groupes = new Map();
    signaux.forEach((x) => {
      if (compte.get(x.signal) > s) {
        if (!groupes.has(x.signal)) {
          const g = { replie: true, signal: x.signal, signaux: [] };
          groupes.set(x.signal, g);
          sortie.push(g);
        }
        groupes.get(x.signal).signaux.push(x);
      } else {
        sortie.push(x);
      }
    });
    return sortie;
  }

  /* L'adresse de l'annuaire pour « ↗ ». L'ACCUEIL seulement : les liens vers la fiche d'un
     compte ou d'un groupe supposent des chemins de l'interface de LLDAP qui n'ont pas été
     mesurés (hypothèse écrite dans le format de la route). Un lien profond qui mène à une
     page d'erreur coûterait plus qu'un clic de plus. */
  function lienAnnuaire(base) {
    if (typeof base !== "string") return null;
    return /^https?:\/\/\S+$/i.test(base.trim()) ? base.trim() : null;
  }

  /* Ce qu'une suppression laisserait, dit en CONSÉQUENCE et jamais en recommandation
     (doctrine du verdict d'AUTH-7). Les actes restent attribués au login : le journal est
     clé sur lui. Ce qui se perd, c'est que ce login ne désigne plus personne. */
  function consequenceSuppression(compte) {
    const actes = compte.actes || 0, acces = compte.acces_explicites || 0;
    if (!actes && !acces) return "rien à orpheliner";
    const parts = [];
    if (actes) parts.push(pluriel(actes, "acte", "actes"));
    if (acces) parts.push(pluriel(acces, "accès", "accès"));
    const seul = parts.length === 1 && (actes || acces) === 1;
    return `${parts.join(" et ")} ${seul ? "resterait" : "resteraient"} à ce login ; un compte `
      + "recréé sous ce nom en hériterait";
  }

  return {
    AXES, TRIS, SEUIL_REGROUPEMENT, TYPE_DE_L_AXE, AXE_DU_TYPE,
    nomLu, identifiant, dateDe, trier, normaliser, filtrer,
    lireAdresse, ecrireAdresse, dateCourte, etatCourt,
    diffusionLue, cibleSignal, texteSignal, texteGroupeSignaux,
    regrouperSignaux, lienAnnuaire, consequenceSuppression,
  };
});
