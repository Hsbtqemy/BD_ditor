/* Le bloc « Grilles » de la fiche d'un projet (Administration › Projets) — logique PURE,
   sans DOM (ANN-7 ; le bloc et le bilan tranchés par Hugo sur maquette le 2026-11-03).

   Chargé en <script> AVANT administration.js → expose `window.BDGrillesProjet` ; aussi
   require()-able par `tests/js/grilles-projet.test.js`.

   Trois choses s'y décident, et rien d'autre :

   1. CE QUI S'OFFRE sur une grille, selon son état tel que le serveur le rend
      (`GET /api/projets/{id}/grilles`, `_vue_grille`) : télécharger le classeur d'une version,
      réimporter, publier un brouillon, activer — ou monter —, désactiver. Une offre n'est pas
      une garde : chaque route pose sa question, et l'écran dit son refus. Le bloc entier ne
      se dessine que si le serveur rend les grilles du projet (`grilles`, à qui le GÈRE).
   2. LE BILAN EN MOTS d'un import (`POST /api/projets/{id}/grilles/import`) : le verdict en
      tête ; pour chaque faute, où (feuille ou fichier, ligne, entrée, question), ce qui ne
      va pas, ce qu'il faut faire ; « À savoir », « Ce qui va naître », « Ce qui change »,
      et les entrées employées qui disparaissent d'une grille ouverte, avec la réponse à
      donner (« retirer » ou « fusionner dans… »). Le serveur NOMME — le verdict, le
      problème, ce qu'il faut faire sont ses phrases — ; l'écran les range et les compte.
      « Importer » ne s'offre que sur un fichier juste, et une fois chaque disparu répondu.
   3. LE BILAN EN MOTS d'une MONTÉE DE VERSION (ANN-7 ; l'écran minimal d'avant la maquette,
      M6 (a), tranché par Hugo le 2026-11-15) : la phrase, les relevés par cause, ce qui
      change, les entrées retirées à répondre (« laisser » ou « fusionner dans… »), ce qui se
      refuse. « Monter » ne s'offre qu'une fois chaque entrée répondue, et jamais sur un refus.

   Les mots d'une CIBLE (« la case », « des mots ») sont ceux de `grille_tableur.CIBLES_MOTS`,
   recopiés UNE fois ici : aucune route ne les publie, et `tests/test_grilles_projet_ecran.py`
   mesure leur accord. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDGrillesProjet = api;                                            // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Miroir de `grille_tableur.CIBLES_MOTS`, dans le même ordre. */
  const CIBLES_MOTS = {
    mots: "des mots",
    bulle: "bulle",
    cartouche: "cartouche",
    texte: "texte hors bulle",
    case: "la case",
    personnage: "boîte de personnage",
    detail: "détail d'image",
    planche: "la planche",
    entite: "l'entité du registre",
  };

  /* Le type d'un classeur : c'est le seul format que l'écran importe (le gabarit tranché le
     2026-11-03) ; les deux CSV restent le format machine de l'outil. */
  const TYPE_CLASSEUR =
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

  function pluriel(n, singulier, plurielle) {
    return `${n} ${n > 1 ? (plurielle || singulier + "s") : singulier}`;
  }

  /* « bulle, cartouche ou texte hors bulle » ; une sorte inconnue se dit sous sa clé. */
  function enumerer(mots) {
    if (mots.length <= 1) return mots.join("");
    return `${mots.slice(0, -1).join(", ")} ou ${mots[mots.length - 1]}`;
  }

  function porteSurEnMots(sortes) {
    return enumerer((sortes || []).map((s) => CIBLES_MOTS[s] || s));
  }

  /* D'où vient une grille (v40) : `derivee_de` de `_vue_grille` ou du bilan d'un import,
     `{nom, version}` ou null → « dérivée de « Signaux », v2 » ; sans nom ni version, ce
     qui en reste ; "" pour une grille qui ne vient d'aucune autre. Le pendant de
     `grille_import.origine_en_mots`. */
  function origineEnMots(o) {
    if (!o) return "";
    const texte = o.nom ? `dérivée de « ${o.nom} »` : "dérivée d'une autre grille";
    return o.version ? `${texte}, v${o.version}` : texte;
  }

  /* --- 1. L'état d'une grille, et ce qui s'y offre ------------------------------------ */

  function derniere(versions, etat) {
    const v = (versions || []).filter((x) => x.etat === etat);
    return v.length ? v[v.length - 1] : null;
  }

  /* `g` : une grille telle que `_vue_grille` la rend. Rend :
     - `etiquette` : son état en quelques mots (« v1 publiée · active », « ouverte · pas
       active », « brouillon v2 », « retirée ») ;
     - `origine` : d'où elle vient (`origineEnMots`), "" si de nulle part ;
     - `porteSur` : ce sur quoi porte sa version de référence, en mots ;
     - `telecharger` : les versions dont on offre le classeur — la référence (la vivante, ou
       la dernière publiée) et le brouillon ;
     - `reimporter`, `desactiver` : vrai ou faux ;
     - `desactiverRaison` : la grille de TRAVAIL (le mode libre, J2) ne se désactive pas — le
       serveur le refuse par un 409 : « Désactiver » s'y montre ÉTEINT, et voici pourquoi ;
       `null` ailleurs ;
     - `publier` : le numéro du brouillon qui se publierait (grille fermée), ou null ;
     - `activer` : le numéro de la version qui s'activerait, ou null — la vivante d'une
       ouverte, la dernière publiée d'une fermée, si elle n'est pas déjà celle active. */
  const RAISON_TRAVAIL = "C'est la grille de travail du projet, qui porte son mode libre : "
    + "elle ne se désactive, ne se retire ni ne se supprime.";
  function etat(g) {
    const versions = g.versions || [];
    const brouillon = derniere(versions, "brouillon");
    const publiee = derniere(versions, "publiee");
    const vivante = derniere(versions, "vivante");
    const reference = g.ouverte ? vivante : publiee;
    const active = g.active || null;
    const retiree = !!g.retiree_le;
    let etiquette;
    if (retiree) etiquette = "retirée";
    else if (g.ouverte) etiquette = active ? "ouverte · active" : "ouverte · pas active";
    else {
      const morceaux = [];
      if (active) morceaux.push(`v${active.numero} publiée · active`);
      else if (publiee) morceaux.push(`v${publiee.numero} publiée · pas active`);
      if (brouillon) morceaux.push(`brouillon v${brouillon.numero}`);
      etiquette = morceaux.join(" · ") || "aucune version";
    }
    const telecharger = [];
    if (reference) {
      telecharger.push({ numero: reference.numero,
                         libelle: g.ouverte ? "le classeur" : `le classeur v${reference.numero}` });
    }
    if (brouillon) {
      telecharger.push({ numero: brouillon.numero, libelle: `le brouillon v${brouillon.numero}` });
    }
    const activable = retiree ? null : reference;
    // La MONTÉE DE VERSION (ANN-7) : une version publiée plus récente que l'active, sur une
    // grille fermée qui porte des relevés ou des passes — « Activer » devient « Monter à la
    // version M… ». Les comptes ne viennent qu'à qui gère le projet ; ailleurs, aucun geste.
    const porte = typeof g.releves === "number" && g.releves + (g.passes || 0) > 0;
    const monter = !g.ouverte && activable && active && porte
      && activable.numero > active.numero ? activable.numero : null;
    // La FIN d'une grille (Hugo, 2026-11-13) : employée, elle se retire — ses relevés restent
    // lisibles ; personne ne l'emploie, elle se supprime. Les deux attendent qu'elle soit
    // désactivée, et jamais sur la grille de travail : le geste s'y montre ÉTEINT, avec sa
    // raison. Les comptes ne viennent qu'à qui gère le projet : sans eux, aucun geste.
    let fin = null;
    if (typeof g.releves === "number") {
      const employee = g.releves + (g.passes || 0) > 0;
      if (!(retiree && employee)) {
        fin = { geste: employee ? "retirer" : "supprimer", releves: g.releves,
                passes: g.passes || 0,
                raison: g.travail ? RAISON_TRAVAIL
                  : active ? "Elle est active dans le projet : désactivez-la d'abord." : null };
      }
    }
    return {
      etiquette,
      origine: origineEnMots(g.derivee_de),
      porteSur: porteSurEnMots(((reference || brouillon || {}).porte_sur) || []),
      telecharger,
      reimporter: !retiree,
      publier: !retiree && !g.ouverte && brouillon ? brouillon.numero : null,
      activer: activable && !monter && !(active && active.numero === activable.numero)
        ? activable.numero : null,
      monter,
      desactiver: !!active,
      desactiverRaison: active && g.travail ? RAISON_TRAVAIL : null,
      fin,
      // Un brouillon se supprime ; seul, la grille part avec lui, ce que « fin » offre déjà.
      supprimerBrouillon: !g.ouverte && brouillon && versions.length > 1 ? brouillon.numero : null,
    };
  }

  /* Ce que dit la confirmation d'une fin — `geste` : « supprimer », « retirer » ou
     « brouillon » — et le bouton qui la fait. */
  function confirmation(g, e, geste) {
    const nom = `« ${g.nom} »`;
    if (geste === "brouillon") {
      return { texte: `Le brouillon v${e.supprimerBrouillon} part, avec tout ce qu'il change. `
                 + "Les versions publiées restent.",
               bouton: `Supprimer le brouillon v${e.supprimerBrouillon}` };
    }
    if (geste === "retirer") {
      const n = e.fin ? e.fin.releves : 0;
      return { texte: `Retirée, ${nom} ne s'active plus et ne reçoit plus de version. `
                 + (n ? `${pluriel(n, "relevé")} ${n > 1 ? "restent lisibles" : "reste lisible"}.`
                   : "Ce qu'elle porte reste lisible.") + " Ce geste ne s'annule pas.",
               bouton: "Retirer la grille" };
    }
    return { texte: `${nom} part : personne ne l'emploie, aucun relevé ne se perd. `
               + "Ce geste ne s'annule pas.",
             bouton: "Supprimer la grille" };
  }

  /* --- 2. Le bilan d'un import, en mots ---------------------------------------------- */

  /* Où est une faute : « feuille « 2. Les entrées », ligne 12 · « cri » · 4. Ce qu'on
     choisit ». `classeur` : la faute vient d'un classeur, dont `fichier` nomme la FEUILLE. */
  function ouEnMots(f, classeur) {
    const ou = [];
    if (f.fichier) {
      const lieu = classeur && f.fichier !== "déclaration"
        ? `feuille « ${f.fichier} »` : f.fichier;
      ou.push(f.ligne ? `${lieu}, ligne ${f.ligne}` : lieu);
    } else if (f.ligne) ou.push(`ligne ${f.ligne}`);
    if (f.cle) ou.push(`« ${f.cle} »`);
    if (f.question) ou.push(f.question);
    return ou.join(" · ");
  }

  function majuscule(t) {
    const s = String(t || "");
    return s ? s[0].toUpperCase() + s.slice(1) : s;
  }

  function point(t) {
    const s = majuscule(t);
    return s && !/[.!?…]$/.test(s) ? s + "." : s;
  }

  /* Une faute ou un avertissement : { ou, quoi, faire }. */
  function fauteEnMots(f, classeur) {
    return { ou: ouEnMots(f, classeur), quoi: point(f.probleme), faire: f.a_faire
      ? point(f.a_faire) : "", code: f.code || null };
  }

  /* Les noms d'un PLAN (`GET /api/grilles/{id}/versions/{n}`), par sorte d'objet : de quoi
     dire « cri » plutôt que son identifiant dans « Ce qui change ». */
  function nomsDuPlan(plan) {
    const n = { entree: {}, variante: {}, rubrique: {}, liste: {}, qualificatif: {} };
    if (!plan) return n;
    for (const r of plan.rubriques || []) n.rubrique[r.cle] = r.libelle;
    for (const e of plan.entrees || []) {
      n.entree[e.cle] = e.libelle;
      for (const v of e.variantes || []) n.variante[`${e.cle}/${v.cle}`] = `${e.libelle} › ${v.libelle}`;
    }
    for (const l of plan.listes || []) {
      n.liste[l.cle] = l.libelle;
      for (const q of l.qualificatifs || []) n.qualificatif[`${l.cle}/${q.cle}`] = `${l.libelle} › ${q.libelle}`;
    }
    return n;
  }

  const QUOI = { entree: "entrée", variante: "variante", rubrique: "rubrique", liste: "liste",
                 qualificatif: "case", version: "la grille" };
  const CHAMPS_RETOUCHES = { definition: "définition", structure: "structure",
                             piege: "piège", exemples: "exemples" };
  const CHAMPS_CHANGES = { forme: "ce qu'on choisit", cible: "ce sur quoi elle se pose",
                           cardinalite: "combien de fois", liste_cle: "la liste à cocher",
                           precision: "le champ à écrire", lien: "l'autre zone",
                           porte_sur: "ce sur quoi la grille porte" };

  /* « Ce qui change » (`bilan` de l'import), une ligne par changement :
     { genre, quoi, nom, detail }. `noms` : `nomsDuPlan` de la version comparée ; un objet
     qu'elle ne nomme pas se dit par son identifiant. */
  function changementsEnMots(b, noms) {
    if (!b) return [];
    const N = noms || nomsDuPlan(null);
    const nom = (quoi, cle, libelle) => libelle || (N[quoi] && N[quoi][cle]) || cle;
    const lignes = [];
    for (const x of b.nes || []) {
      lignes.push({ genre: "naît", quoi: QUOI[x.quoi] || x.quoi, nom: x.libelle || x.cle, detail: "" });
    }
    for (const x of b.renommes || []) {
      lignes.push({ genre: "renommée", quoi: QUOI[x.quoi] || x.quoi, nom: `${x.avant} → ${x.apres}`,
                    detail: "même identifiant : ses relevés la suivent" });
    }
    for (const x of b.retouches || []) {
      lignes.push({ genre: "retouchée", quoi: QUOI[x.quoi] || x.quoi, nom: nom(x.quoi, x.cle),
                    detail: (x.champs || []).map((c) => CHAMPS_RETOUCHES[c] || c).join(", ") });
    }
    for (const x of b.deplaces || []) {
      const ou = (c) => (c ? `« ${nom("rubrique", c)} »` : "hors rubrique");
      lignes.push({ genre: "déplacée", quoi: QUOI[x.quoi] || x.quoi, nom: nom(x.quoi, x.cle),
                    detail: `${ou(x.avant)} → ${ou(x.apres)}` });
    }
    for (const x of b.changes || []) {
      if (x.champ === "retiree") {
        lignes.push({ genre: "retirée", quoi: QUOI[x.quoi] || x.quoi, nom: nom(x.quoi, x.cle),
                      detail: "elle ne se pose plus ; ses relevés restent, à revoir" });
        continue;
      }
      lignes.push({ genre: "changée", quoi: QUOI[x.quoi] || x.quoi,
                    nom: x.quoi === "version" ? "" : nom(x.quoi, x.cle),
                    detail: CHAMPS_CHANGES[x.champ] || x.champ });
    }
    for (const x of b.disparus || []) {
      const releves = x.releves ? pluriel(x.releves, "relevé posé", "relevés posés") : "";
      let suite = "";
      if (x.decision === "a_repondre") suite = "à répondre plus bas";
      else if (x.decision === "part") suite = "personne ne l'emploie : elle part";
      else if (typeof x.decision === "string" && x.decision.startsWith("fusionner:")) {
        suite = `fusionnée dans « ${nom("entree", x.decision.slice(10))} »`;
      }
      lignes.push({ genre: "disparaît", quoi: QUOI[x.quoi] || x.quoi, nom: x.libelle || x.cle,
                    detail: [releves, suite].filter(Boolean).join(" · ") });
    }
    return lignes;
  }

  /* « Ce qui va naître » : « 2 rubriques · 6 entrées · 4 variantes · 1 liste · 3 cases »,
     vide si rien ne naît. */
  function vaNaitreEnMots(v) {
    if (!v) return "";
    return [[v.rubriques, "rubrique"], [v.entrees, "entrée"], [v.variantes, "variante"],
            [v.listes, "liste"], [v.qualificatifs, "case"]]
      .filter(([n]) => n > 0).map(([n, mot]) => pluriel(n, mot)).join(" · ");
  }

  /* La réponse de la route d'import, en ce que l'écran dessine. `statut` : le code HTTP ;
     `corps` : le JSON rendu (200), ou le `detail` d'un refus (un objet structuré, ou une
     phrase). Rend { etat, phrase, fautes, aSavoir, changements, vaNaitre, deriveeDe,
     aRepondre, declaration, compareA, ecrit, grilleId } — `deriveeDe` : d'où viendra la
     grille neuve, en mots (`origineEnMots`), "" sinon. */
  function lireReponse(statut, corps, opts) {
    const o = opts || {};
    const classeur = o.classeur !== false;
    const vue = { etat: "refuse", phrase: "", fautes: [], aSavoir: [], changements: [],
                  vaNaitre: "", deriveeDe: "", aRepondre: [], declaration: null,
                  compareA: null,
                  ecrit: false, grilleId: null };
    if (typeof corps === "string" || corps == null) {
      vue.phrase = corps ? point(corps) : "Le fichier n'a pas pu être vérifié.";
      return vue;
    }
    const v = corps.verdict || {};
    vue.etat = v.etat || (statut >= 400 ? "refuse" : "importable");
    vue.phrase = v.phrase || (corps.message ? point(corps.message) : "");
    vue.fautes = (corps.anomalies || []).map((f) => fauteEnMots(f, classeur));
    vue.aSavoir = (corps.a_savoir || []).map((f) => fauteEnMots(f, classeur));
    vue.changements = statut < 400 || vue.etat === "a_repondre"
      ? changementsEnMots(corps.bilan, o.noms) : [];
    vue.vaNaitre = vaNaitreEnMots(corps.va_naitre);
    vue.deriveeDe = origineEnMots(corps.derivee_de);
    vue.aRepondre = (corps.a_repondre || []).map((a) => ({
      cle: a.cle, libelle: a.libelle, releves: a.releves || 0,
      choix: a.choix || [], fusionnerDans: a.fusionner_dans || [] }));
    vue.declaration = corps.declaration || null;
    vue.compareA = corps.compare_a == null ? null : corps.compare_a;
    vue.ecrit = !!corps.ecrit;
    vue.grilleId = corps.grille_id == null ? null : corps.grille_id;
    if (!vue.phrase && vue.etat === "refuse") {
      vue.phrase = vue.fautes.length
        ? `${pluriel(vue.fautes.length, "faute")} à corriger : rien n'est importé tant qu'il en reste une.`
        : "Le fichier est refusé.";
    }
    return vue;
  }

  /* Les choix offerts à une entrée employée qui disparaît : « retirer », puis une fusion
     par entrée d'arrivée possible. { valeur, libelle }. */
  function choixDeReponse(a, noms) {
    const N = (noms && noms.entree) || {};
    const choix = [];
    if (a.choix.includes("retirer")) {
      choix.push({ valeur: "retirer", libelle: `Retirer : elle ne se pose plus, ${a.releves > 1
        ? `ses ${a.releves} relevés restent` : "son relevé reste"}, à revoir` });
    }
    if (a.choix.includes("fusionner")) {
      for (const k of a.fusionnerDans) {
        choix.push({ valeur: `fusionner:${k}`,
                     libelle: `Fusionner dans « ${N[k] || k} » : ${a.releves > 1
                       ? "ses relevés la suivent" : "son relevé la suit"}` });
      }
    }
    return choix;
  }

  /* « Importer » s'offre-t-il ? { ok, raison }. Un fichier juste (« importable »), ou juste
     dont chaque disparu a sa réponse (« à répondre ») ; jamais sur une faute, ni quand rien
     ne change, ni une fois importé. */
  function importable(vue, reponses) {
    if (!vue) return { ok: false, raison: "Vérifiez d'abord le fichier." };
    const r = reponses || {};
    if (vue.etat === "refuse") {
      return { ok: false, raison: vue.fautes.length
        ? `${pluriel(vue.fautes.length, "faute")} à corriger : rien n'est importé tant qu'il en reste une.`
        : "Le fichier est refusé : rien ne s'importe." };
    }
    if (vue.etat === "aucun_changement") {
      return { ok: false, raison: "Rien ne change : il n'y a rien à importer." };
    }
    if (vue.etat === "importe") return { ok: false, raison: "Le fichier est importé." };
    const manquent = vue.aRepondre.filter((a) => !r[a.cle]);
    if (manquent.length) {
      // Une grille fermée ne fusionne pas : « retirer » est sa seule réponse.
      const fusion = manquent.some((a) => (a.choix || []).includes("fusionner"));
      return { ok: false, raison: `${pluriel(manquent.length, "entrée")} à répondre : dites `
        + (fusion ? "pour chacune « retirer » ou « fusionner dans… »."
          : "pour chacune « retirer ».") };
    }
    return { ok: true, raison: "" };
  }

  /* Les réponses telles que la route les attend : `{cle: "retirer"}` ou
     `{cle: "fusionner:<cle>"}`, les seules des entrées qui les demandent. */
  function reponsesPourEnvoi(vue, reponses) {
    const r = reponses || {};
    const sortie = {};
    for (const a of (vue && vue.aRepondre) || []) if (r[a.cle]) sortie[a.cle] = r[a.cle];
    return sortie;
  }

  /* --- 3. Le bilan d'une MONTÉE DE VERSION, en mots (ANN-7) ------------------------- */

  /* Le bilan de `GET /api/projets/{id}/grilles/{gid}/montee` — ou le `detail` d'un 409 de
     `PUT …/activation`, qui le porte — en ce que la confirmation sous la ligne dessine.
     `opts.causes` : les mots des causes (`BDAnnotation.CAUSES`, ceux de la page
     Annotation) ; `opts.noms` : `nomsDuPlan` de la version d'arrivée. Rend { etat, phrase,
     de, vers, comptes, causes: [{ cause, etat, n, mots }], changements, aRepondre, refus:
     [{ texte, zone }], passes, vu }. */
  function lireMontee(b, opts) {
    const o = opts || {};
    const mots = o.causes || {};
    const N = (o.noms && o.noms.entree) || {};
    const v = (b && b.verdict) || {};
    const vue = { etat: v.etat || "refuse", phrase: v.phrase || "", de: b ? b.de : null,
                  vers: b ? b.vers : null, comptes: (b && b.releves) || null, causes: [],
                  changements: [], aRepondre: [], refus: [], passes: 0,
                  vu: (b && b.vu) || null };
    if (!b) return vue;
    vue.causes = (b.causes || []).map((c) => ({
      cause: c.cause, etat: c.etat, n: c.n || 0, mots: mots[c.cause] || c.cause }));
    vue.changements = changementsEnMots(b.plan, o.noms);
    vue.aRepondre = (b.a_repondre || []).map((a) => ({
      cle: a.cle, libelle: a.libelle, releves: a.releves || 0,
      choix: [{ valeur: "laisser", libelle: `Laisser : ${a.releves > 1
        ? `ses ${a.releves} relevés passent` : "son relevé passe"}, à revoir` }]
        .concat((a.fusionner_dans || []).map((k) => ({
          valeur: `fusionner:${k}`, libelle: `Fusionner dans « ${N[k] || k} » : ${a.releves > 1
            ? "ses relevés la suivent" : "son relevé la suit"}` }))) }));
    vue.refus = (b.refus || []).map((r) => ({
      texte: r.probleme || `« ${r.libelle || r.cle} » : deux relevés sur une même zone`,
      zone: r.zone || null }));
    vue.passes = (b.passes_rouvertes && b.passes_rouvertes.n) || 0;
    return vue;
  }

  /* « Monter » s'offre-t-il ? { ok, raison }. Jamais sur un refus ; une fois chaque entrée
     retirée répondue. */
  function montable(vue, reponses) {
    if (!vue) return { ok: false, raison: "Lisez d'abord le bilan." };
    const r = reponses || {};
    if (vue.etat === "refuse") {
      return { ok: false, raison: vue.refus.length
        ? vue.refus.map((x) => point(x.texte)).join(" ")
        : "La montée est refusée : rien ne change." };
    }
    const manquent = vue.aRepondre.filter((a) => !r[a.cle]);
    if (manquent.length) {
      return { ok: false, raison: `${pluriel(manquent.length, "entrée retirée", "entrées retirées")} `
        + "à répondre : « laisser » ou « fusionner dans… »." };
    }
    return { ok: true, raison: "" };
  }

  /* Les réponses telles que `PUT …/activation` les attend : `{cle: "laisser"}` ou
     `{cle: "fusionner:<cle>"}`, celles des seules entrées qui les demandent. */
  function reponsesDeMontee(vue, reponses) {
    const r = reponses || {};
    const sortie = {};
    for (const a of (vue && vue.aRepondre) || []) if (r[a.cle]) sortie[a.cle] = r[a.cle];
    return sortie;
  }

  /* La déclaration lue, en une ligne : « « Signaux », fermée, porte sur des mots ». */
  function declarationEnMots(d) {
    if (!d) return "";
    const sortes = String(d.porte_sur || "").split("|").map((s) => s.trim()).filter(Boolean);
    const morceaux = [];
    if (d.nom) morceaux.push(`« ${d.nom} »`);
    if (d.ouverte !== undefined && d.ouverte !== null) morceaux.push(d.ouverte ? "ouverte" : "fermée");
    if (sortes.length) morceaux.push(`porte sur ${porteSurEnMots(sortes)}`);
    return morceaux.join(", ");
  }

  /* Un fichier qu'on peut envoyer : un classeur, reconnu à son nom (le serveur le reconnaît
     à ses octets, et dit son refus). */
  function estUnClasseur(nom) {
    return /\.xlsx$/i.test(String(nom || "").trim());
  }

  return {
    CIBLES_MOTS, TYPE_CLASSEUR, pluriel, porteSurEnMots, origineEnMots, etat, ouEnMots,
    fauteEnMots,
    nomsDuPlan, changementsEnMots, vaNaitreEnMots, lireReponse, choixDeReponse, importable,
    reponsesPourEnvoi, declarationEnMots, estUnClasseur, confirmation, lireMontee, montable,
    reponsesDeMontee,
  };
});
