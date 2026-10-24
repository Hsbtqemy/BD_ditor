/* « Mon bac à sable » (COL-4) — ce que l'écran en DÉCIDE, sans DOM.

   Chargé en <script> sur les CINQ surfaces → expose `window.BDBac` ; aussi require()-able par
   `tests/js/bac-a-sable.test.js`, qui le vérifie par tables de cas. Rien n'est lu au
   chargement : ni le document, ni le stockage, ni l'heure.

   L'écran a été tranché par Hugo sur maquette le 2026-10-24 (`pilotage/COL-4.md`, zone
   « L'écran ») ; ce module en tient les RÈGLES, et `static/bac-a-sable.js` les dessine :
     · qui se voit offrir « Mon bac à sable », et où (`offrir`, `offrirPageVide`) ;
     · ce que dit la ligne du bac à sable — son nom, sa date en heure de Paris, le compte
       des planches importées — et quels gestes elle porte (`ligne`) ;
     · ce qui part et ce qui revient à la remise à neuf (`remiseANeuf`) ;
     · quand le geste d'import s'éteint (`raisonImportEteint`) ;
     · ce qu'on dit d'un bac à sable qui a disparu depuis la dernière page (`disparus`,
       `messageDisparu`) — l'effacement du lundi se dit à la requête suivante.

   Le serveur reste seul à trancher : il refuse ce que l'écran aurait offert à tort, et ce
   module n'invente aucun droit — il lit `bac_a_sable` dans `GET /api/projets`, la vue de
   `GET /api/bac-a-sable` et `bac_a_sable_ouvrable` dans `GET /api/moi`. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDBac = api;                                                      // navigateur
})(typeof self !== "undefined" ? self : this, function (root) {
  "use strict";

  const FUSEAU = "Europe/Paris";
  /* Les bacs à sable vus à la dernière page : de quoi dire, à la suivante, qu'il a été
     effacé. Stockage local, lu et écrit sous try/catch, RANGÉ PAR LOGIN : deux comptes se
     succèdent sur un même navigateur, et le souvenir de l'un ne doit jamais parler à
     l'autre — il lui annoncerait un faux effacement, ou lui apprendrait qui est invité chez
     qui (relecture de l'écran, 2026-10-24). Sans login, rien n'est ni lu ni écrit. */
  const CLE_SOUVENIRS = "bd-bacs-a-sable";

  /* L'aide, dans l'infobulle du nom (« sans phrases à l'écran »). */
  const AIDE_MIEN = "Un projet à vous pour apprendre l'outil, rempli d'un jeu de planches. "
    + "Tout ce qu'il contient part chaque lundi à 4 h : « Mon bac à sable » en ouvre alors "
    + "un neuf. Rien n'en sort, et la Recherche et l'Exploration ne le voient pas.";
  function aide(projet) {
    const b = projet && projet.bac_a_sable;
    if (!b || b.mien) return AIDE_MIEN;
    return `Le bac à sable de ${b.proprietaire} : un projet pour apprendre l'outil, où il `
      + "vous a invité. Tout ce qu'il contient part chaque lundi à 4 h, ou quand il le "
      + "remet à neuf. Rien n'en sort, et la Recherche et l'Exploration ne le voient pas.";
  }

  /* ── Les dates ─────────────────────────────────────────────────────────────────────
     Le serveur rend ses dates en UTC, à la forme SQLite (« 2026-10-26 03:00:00 ») ; l'écran
     les dit en heure de PARIS, celle de l'effacement (lundi 4 h), quel que soit le fuseau
     du poste. `null` pour une date illisible : rien ne s'écrit plutôt qu'une date fausse. */
  function instant(s) {
    const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/.exec(String(s || ""));
    if (!m) return null;
    const [an, mois, jour_, h, mn, sec] = [+m[1], +m[2], +m[3], +m[4], +m[5], +(m[6] || 0)];
    const d = new Date(Date.UTC(an, mois - 1, jour_, h, mn, sec));
    // Une date qui DÉBORDE (le 45 du 13e mois) n'est pas reportée au suivant : illisible.
    if (Number.isNaN(d.getTime()) || d.getUTCMonth() !== mois - 1 || d.getUTCDate() !== jour_
        || d.getUTCHours() !== h || d.getUTCMinutes() !== mn) return null;
    return d;
  }

  function parties(d, options) {
    const f = new Intl.DateTimeFormat("fr-FR", Object.assign({ timeZone: FUSEAU }, options));
    const o = {};
    f.formatToParts(d).forEach((p) => { if (p.type !== "literal") o[p.type] = p.value; });
    return o;
  }

  /* « 4 h », « 14 h 30 » — l'heure de Paris, à la française. */
  function heure(d) {
    const p = parties(d, { hour: "numeric", minute: "2-digit", hourCycle: "h23" });
    const h = String(Number(p.hour)), mn = p.minute;
    return mn === "00" ? `${h} h` : `${h} h ${mn}`;
  }

  /* « lundi 26 octobre à 4 h ». */
  function jourEtHeure(s) {
    const d = instant(s);
    if (!d) return null;
    const p = parties(d, { weekday: "long", day: "numeric", month: "long" });
    return `${p.weekday} ${p.day} ${p.month} à ${heure(d)}`;
  }

  /* « lun. 26 oct., 4 h » — l'en-tête de la liste des bacs à sable de l'Administration.
     Les abréviations sont celles d'`Intl`, telles quelles : « mars », « mai », « juin »,
     « août » n'en ont pas, et un point ajouté d'office les doublait (« 3 mai., 4 h »). */
  function jourCourt(s) {
    const d = instant(s);
    if (!d) return null;
    const p = parties(d, { weekday: "short", day: "numeric", month: "short" });
    return `${p.weekday} ${p.day} ${p.month}, ${heure(d)}`;
  }

  /* « 24/10 » — « ouvert le » d'une ligne de la liste. */
  function jjmm(s) {
    const d = instant(s);
    if (!d) return null;
    const p = parties(d, { day: "2-digit", month: "2-digit" });
    return `${p.day}/${p.month}`;
  }

  /* Le jour de la semaine seul, « lundi » — le message de l'effacement. */
  function jour(s) {
    const d = instant(s);
    return d ? parties(d, { weekday: "long" }).weekday : null;
  }

  /* ── Qui se voit offrir « Mon bac à sable » ─────────────────────────────────────────
     Trois places (Hugo, 2026-10-24) : la bande du haut, TANT QU'IL N'EXISTE PAS — ensuite
     il est dans le sélecteur de projet, comme les autres — ; le bandeau de portée vide ; et
     la page vide. Jamais le menu du compte. Offert à qui le serveur l'ouvrirait
     (`bac_a_sable_ouvrable`), administrateur compris : il en a un aussi. */
  function mien(projets) {
    return (Array.isArray(projets) ? projets : [])
      .find((p) => p && p.bac_a_sable && p.bac_a_sable.mien) || null;
  }

  function offrir(moi, projets) {
    return !!(moi && moi.bac_a_sable_ouvrable) && !mien(projets);
  }

  /* La page vide — sous « Sélectionnez ou importez une planche pour commencer » (Atelier),
     en carte dans la fiche (Bibliothèque) — ne l'offre qu'à qui n'a AUCUN projet : c'est
     là seulement que la page est vide pour lui (le premier clic d'un arrivant). Qui a déjà
     un projet le trouve dans la bande. */
  function offrirPageVide(moi, projets) {
    return offrir(moi, projets) && !(Array.isArray(projets) && projets.length);
  }

  /* Dans un bac à sable, le bandeau « Aucune collection ne vous est ouverte » se masque —
     il contredisait ce qu'on voit ; la ligne du bac à sable en tient lieu. Il revient dès
     que le projet courant n'en est plus un. */
  function estBac(projet) { return !!(projet && projet.bac_a_sable); }

  /* ── La ligne du bac à sable ───────────────────────────────────────────────────────
     Une rangée sous la bande, sur toutes les surfaces, quand le projet courant est un bac
     à sable : le nom (et l'aide en infobulle), la date, au propriétaire le compte des
     planches importées, puis les gestes — « Inviter… (n) » et « Remettre à neuf… » au
     propriétaire, « Quitter… » à l'invité. Rien pour « Par où commencer » avant le lot 4.

     `projet` : sa ligne de `GET /api/projets` ; `vue` : `GET /api/bac-a-sable` (le sien
     seulement, null sinon). `null` hors d'un bac à sable. */
  function ligne(projet, vue) {
    const b = projet && projet.bac_a_sable;
    if (!b) return null;
    const date = jourEtHeure(b.efface_le);
    const l = {
      nom: b.mien ? "Bac à sable" : `Bac à sable de ${b.proprietaire}`,
      aide: aide(projet),
      date: date ? `s'efface ${date}` : null,
      plafond: null,
      gestes: b.mien ? ["inviter", "remettre"] : ["quitter"],
      invites: b.mien ? Number(projet.nb_membres) || 0 : null,
    };
    if (b.mien && vue && vue.id === projet.id) l.plafond = plafond(vue);
    return l;
  }

  function libelleInviter(n) {
    return n ? `Inviter… (${n})` : "Inviter…";
  }

  /* « 12 / 50 planches importées » ; `plein` au plafond, que la ligne dit en encre d'alerte
     et qui éteint les gestes d'import. Les planches du jeu ne comptent pas (le serveur). */
  function plafond(vue) {
    const n = Number(vue && vue.planches_importees) || 0;
    const max = Number(vue && vue.plafond_planches) || 0;
    return { texte: `${n} / ${max} planche${max > 1 ? "s" : ""} importée${max > 1 ? "s" : ""}`,
             plein: max > 0 && n >= max, n, max };
  }

  /* Le geste d'import s'éteint, la raison en infobulle, dans un album de MON bac à sable
     dont le plafond est atteint (« au même endroit du geste », Hugo, 2026-10-24) : la fiche
     d'un album de la Bibliothèque, le menu « Import / Export » de l'Atelier. `null` sinon —
     un invité n'en connaît pas le compte, et le serveur lui refuse l'import en le disant. */
  function raisonImportEteint(vue, albumProjetId) {
    if (!vue || albumProjetId == null || vue.id !== albumProjetId) return null;
    const p = plafond(vue);
    if (!p.plein) return null;
    return `Plafond atteint : ${p.n} planches importées sur ${p.max}. Supprimez-en, ou `
      + "remettez le bac à sable à neuf.";
  }

  /* ── Remettre à neuf : ce qui part, ce qui revient ─────────────────────────────────
     Deux colonnes (Hugo, 2026-10-24). La remise à neuf supprime le projet et en fait
     naître un neuf (S5) : les invitations partent avec lui, et se nomment. `invites` : les
     logins des membres (sans le propriétaire). */
  function enumeration(noms) {
    if (noms.length <= 1) return noms.join("");
    return `${noms.slice(0, -1).join(", ")} et ${noms[noms.length - 1]}`;
  }

  function remiseANeuf(vue, invites) {
    const n = Number(vue && vue.planches_importees) || 0;
    const qui = (Array.isArray(invites) ? invites : []).filter(Boolean);
    const part = ["votre travail ici"];
    if (n) part.push(`${n} planche${n > 1 ? "s" : ""} importée${n > 1 ? "s" : ""}`);
    part.push("vos collections");
    if (qui.length) {
      part.push(`le travail de ${enumeration(qui)}`);
      part.push(`${qui.length > 1 ? "les invitations" : "l'invitation"} de ${enumeration(qui)}`);
    }
    const k = Array.isArray(vue && vue.jeu) ? vue.jeu.length : 0;
    const revient = [k === 0 ? "un bac à sable neuf"
      : k === 1 ? "l'album du jeu, vierge" : `les ${k} albums du jeu, vierges`];
    return { part, revient };
  }

  /* ── Après le clic : l'Atelier, sur la planche du parcours ─────────────────────────
     La planche du rôle `pas-a-pas` de la carte du jeu — là où le wizard du lot 4
     commencera —, sinon la première planche du jeu, sinon l'Atelier tel quel. */
  function adresseApresOuverture(vue) {
    const jeu = Array.isArray(vue && vue.jeu) ? vue.jeu : [];
    const avec = jeu.filter((j) => Array.isArray(j.planche_ids) && j.planche_ids.length);
    const j = avec.find((x) => x.role === "pas-a-pas") || avec[0];
    return j ? `/?album=${j.album_id}&planche=${j.planche_ids[0]}` : "/";
  }

  /* ── L'effacement du lundi, dit à la requête suivante ──────────────────────────────
     Un bac à sable vu à la page précédente et absent de la liste : effacé lundi à 4 h si
     sa date est passée — « Votre bac à sable a été effacé lundi à 4 h. », ou « Le bac à
     sable de <login> a été effacé… » chez un invité.

     Avant sa date, deux cas. Le SIEN : remis à neuf dans un autre onglet — le neuf est déjà
     dans la liste, rien à dire —, sinon effacé hors du lundi (l'outil de l'exploitant,
     `--tous`) : on le dit, sans date. Celui d'un AUTRE : on en a été retiré, on l'a quitté
     ailleurs, ou son propriétaire l'a remis à neuf — l'écran ne sait pas lequel, et le dit
     comme un fait. */
  function souvenirsDe(projets) {
    return (Array.isArray(projets) ? projets : []).filter((p) => p && p.bac_a_sable)
      .map((p) => ({ id: p.id, mien: !!p.bac_a_sable.mien,
                     proprietaire: p.bac_a_sable.proprietaire || null,
                     efface_le: p.bac_a_sable.efface_le || null }));
  }

  function disparus(souvenirs, projets) {
    const ids = new Set((Array.isArray(projets) ? projets : []).map((p) => p && p.id));
    return (Array.isArray(souvenirs) ? souvenirs : []).filter((s) => s && !ids.has(s.id));
  }

  function messageDisparu(s, maintenant, projets) {
    if (!s) return null;
    const echeance = instant(s.efface_le);
    const t = maintenant instanceof Date ? maintenant.getTime() : Number(maintenant);
    const passe = echeance && t >= echeance.getTime();
    const quand = `${jour(s.efface_le) || "lundi"} à ${echeance ? heure(echeance) : "4 h"}`;
    if (s.mien) {
      if (passe) return `Votre bac à sable a été effacé ${quand}.`;
      return mien(projets) ? null : "Votre bac à sable a été effacé.";
    }
    if (passe) return `Le bac à sable de ${s.proprietaire} a été effacé ${quand}.`;
    return `Vous n'êtes plus dans le bac à sable de ${s.proprietaire}.`;
  }

  function stockage() {
    try { return root.localStorage || null; } catch (e) { return null; }
  }

  /* Toute la mémoire : `{ login: [souvenirs] }`. Une forme d'avant (une liste nue, qui ne
     dit pas de qui elle est) ne vaut pour personne. */
  function tous(s) {
    const v = s ? JSON.parse(s.getItem(CLE_SOUVENIRS) || "{}") : {};
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  }

  function lireSouvenirs(login, depuis) {
    const s = depuis === undefined ? stockage() : depuis;
    if (!login) return [];
    try {
      const v = tous(s)[login];
      return Array.isArray(v) ? v.filter((x) => x && Number.isInteger(x.id)) : [];
    } catch (e) { return []; }
  }

  function retenirSouvenirs(login, liste, dans) {
    const s = dans === undefined ? stockage() : dans;
    if (!login) return false;
    try {
      if (!s) return false;
      let t;
      try { t = tous(s); } catch (e) { t = {}; }
      t[login] = liste || [];
      s.setItem(CLE_SOUVENIRS, JSON.stringify(t));
      return true;
    } catch (e) { return false; }
  }

  /* Les bacs à sable que CE compte avait vus et qui manquent : rien sans login, rien sur
     une liste illisible. Une liste VIDE, lue sous une identité, compte : c'est celle de
     l'arrivant dont le bac à sable était le seul projet, le premier à devoir lire
     l'effacement ; le souvenir étant rangé par login, elle ne parle jamais d'un autre. */
  function disparusDe(login, projets, depuis) {
    if (!login || !Array.isArray(projets)) return [];
    return disparus(lireSouvenirs(login, depuis), projets);
  }

  /* ── L'Administration : la liste des bacs à sable ──────────────────────────────────
     Par login du propriétaire, filtre sur le login, tri A → Z ou récents d'abord ; la date
     d'effacement une fois en tête (elle est la même pour tous). */
  /* Le login du propriétaire d'un bac à sable : rendu par le serveur pour les autres, et
     pour le sien — qu'il ne nomme pas — celui de qui regarde (`monLogin`). */
  function proprietaire(p, monLogin) {
    const b = p && p.bac_a_sable;
    if (!b) return "";
    return String(b.proprietaire || (b.mien ? monLogin || "" : ""));
  }

  function trierBacs(bacs, tri, filtre, monLogin) {
    const f = String(filtre || "").trim().toLowerCase();
    const login = (p) => proprietaire(p, monLogin);
    const l = (Array.isArray(bacs) ? bacs : []).filter((p) => p && p.bac_a_sable
      && (!f || login(p).toLowerCase().includes(f)));
    if (tri === "recents") {
      // Ouverts dans la même seconde : le dernier né d'abord (les identifiants ne
      // reviennent pas, v31).
      return l.sort((a, b) => String(b.date_creation || "").localeCompare(String(a.date_creation || ""))
        || (b.id || 0) - (a.id || 0));
    }
    return l.sort((a, b) => login(a).localeCompare(login(b), "fr", { sensitivity: "base" }));
  }

  /* « tous s'effacent lun. 26 oct., 4 h » — la plus proche des échéances, s'ils en avaient
     deux (une liste lue à cheval sur un lundi). */
  function enteteBacs(bacs) {
    const dates = (Array.isArray(bacs) ? bacs : []).map((p) => p && p.bac_a_sable
      && p.bac_a_sable.efface_le).filter((d) => instant(d)).sort();
    return dates.length ? `tous s'effacent ${jourCourt(dates[0])}` : "";
  }

  /* La phrase de la fiche d'un bac à sable, à l'administrateur : sans elle, on cherche un
     bouton pour y entrer. Le sien, il l'a dans la bande. */
  function phraseFicheBac(projet) {
    const b = projet && projet.bac_a_sable;
    if (!b) return "";
    if (b.mien) return "C'est le vôtre : il se règle depuis sa ligne, en haut de page, quand "
      + "il est votre projet courant.";
    return `Vous n'y entrez pas. Pour aider ${b.proprietaire}, faites-vous inviter.`;
  }

  /* L'axe « Bacs à sable » de l'Administration ne paraît que là où un bac à sable peut
     exister : derrière le proxy (une identité) — jamais en mono-poste, où personne n'en
     ouvre —, ou s'il y en a déjà (une base copiée d'une instance). */
  function axeBacsVisible(moi, bacs) {
    return !!(moi && moi.utilisateur) || (Array.isArray(bacs) && bacs.length > 0);
  }

  /* Après « Remettre à neuf » : dans l'Atelier, la planche du parcours, comme au premier
     clic ; ailleurs, la même surface, sans son adresse (Hugo, 2026-10-24). */
  function adresseApresRemise(vue, chemin) {
    return chemin === "/" ? adresseApresOuverture(vue) : chemin;
  }

  /* « samedi 24 octobre à 14 h 30 » — « Ouvert », dans la fiche. */
  function dateLongue(s) { return jourEtHeure(s); }

  return { CLE_SOUVENIRS, AIDE_MIEN, aide, instant, jourEtHeure, jourCourt, jjmm, jour,
           heure, mien, offrir, offrirPageVide, estBac, ligne, libelleInviter, plafond,
           raisonImportEteint, remiseANeuf, enumeration, adresseApresOuverture,
           souvenirsDe, disparus, disparusDe, messageDisparu, lireSouvenirs,
           retenirSouvenirs, proprietaire, axeBacsVisible, adresseApresRemise,
           trierBacs, enteteBacs, phraseFicheBac, dateLongue };
});
