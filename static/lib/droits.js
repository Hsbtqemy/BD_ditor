/* Les droits dits en ACTES (AUTH-12, étape 3) — la logique PURE de l'écran qui les montre.
   Chargé en <script> → expose `window.BDDroits` ; aussi require()-able par
   `tests/js/droits.test.js`.

   L'ÉCRAN NE CONNAÎT AUCUN NIVEAU, AUCUN ACTE, AUCUN LIBELLÉ. Il reçoit leur description de
   `GET /api/droits` — une table de DONNÉES posée dans `autorisation.py`, à côté de ce qui
   tranche vraiment les accès — et tout ce qui suit se déduit d'elle :

     { echelle:   ["lecture", "ecriture", "proprietaire"],   // un cran inclut ceux du dessous
       actes:     [{ code, libelle, niveau, lies, avertissement }, …],
       hors_rang: [{ code, libelle, champ, d_office }, …] }

   C'est ce qui permet à AUTH-10 de trancher sans refaire l'écran : un niveau
   `contribution`, une case hors rang pour le vocabulaire, ne sont que d'autres données. Les
   tests le prouvent sur deux descriptions HYPOTHÉTIQUES, et non sur la seule d'aujourd'hui.

   UNE CASE PAR CRAN, JAMAIS PAR ACTE. Le serveur accorde un NIVEAU : tous les actes d'un
   même niveau s'accordent ENSEMBLE. Les cocher séparément promettrait une finesse que le
   modèle n'a pas, et un refus viendrait la démentir (AUTH-10). Le cran se déduit donc du
   `niveau` de chaque acte, qui est ce que le `PUT` envoie ; `lies` le redit, et un test
   côté serveur exige que des actes liés partagent leur niveau. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDDroits = api;                                                   // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Une description qu'on peut lire sans se tromper. Sinon l'écran retombe sur le NIVEAU
     tel quel plutôt que de dessiner des cases fausses : une description manquante ne doit
     ni vider l'écran ni lui faire inventer un modèle. */
  function estValide(d) {
    if (!d || !Array.isArray(d.echelle) || !d.echelle.length) return false;
    if (!d.echelle.every((n) => typeof n === "string" && n)) return false;
    if (new Set(d.echelle).size !== d.echelle.length) return false;
    if (!Array.isArray(d.actes) || !Array.isArray(d.hors_rang)) return false;
    const niveaux = new Set(d.echelle);
    return d.actes.every((a) => a && typeof a.libelle === "string" && niveaux.has(a.niveau))
      && d.hors_rang.every((h) => h && typeof h.champ === "string" && h.champ
        && typeof h.libelle === "string"
        && (h.d_office === null || h.d_office === undefined || niveaux.has(h.d_office)));
  }

  /* Le rang d'un niveau dans l'échelle ; -1 pour un niveau que la description ne connaît pas. */
  function rang(d, niveau) {
    return d.echelle.indexOf(niveau);
  }

  /* Les crans, du bas vers le haut, chacun avec SES actes dans l'ordre servi. Un cran sans
     acte reste un cran : il s'accorde, donc il se coche, et se nomme par son niveau. */
  function crans(d) {
    return d.echelle.map((niveau, i) => ({
      niveau, rang: i,
      actes: d.actes.filter((a) => a.niveau === niveau),
    }));
  }

  function libelleCran(cran) {
    return cran.actes.length ? cran.actes.map((a) => a.libelle).join(" · ") : cran.niveau;
  }

  /* L'ordre des colonnes, tranché le 2026-09-17 par la coordination : l'échelle entière, puis
     les cases hors rang. Changer d'ordre ne touche que cette fonction. */
  function colonnes(d) {
    return [
      ...crans(d).map((c) => ({ type: "cran", niveau: c.niveau, rang: c.rang, actes: c.actes,
                                libelle: libelleCran(c) })),
      ...d.hors_rang.map((h) => ({ type: "hors_rang", code: h.code, champ: h.champ,
                                   libelle: h.libelle, d_office: h.d_office ?? null })),
    ];
  }

  /* Le cran est-il coché pour un accès de ce niveau ? Un niveau inconnu ne coche rien : mieux
     vaut une case vide, avec le niveau affiché tel quel, qu'une case cochée à tort. */
  function cranCoche(d, niveau, niveauCran) {
    const r = rang(d, niveau), c = rang(d, niveauCran);
    return r >= 0 && c >= 0 && r >= c;
  }

  /* Le premier cran ne se décoche pas : un accès lit toujours, et se RETIRE autrement. Sans
     cette règle, décocher « lire » réclamerait un état « aucun acte » que le serveur n'a pas. */
  function cranModifiable(d, niveauCran) {
    return rang(d, niveauCran) > 0;
  }

  /* Le niveau à envoyer après un geste sur un cran. Cocher pose ce cran ; décocher pose le
     cran du dessous. Rend null quand le geste n'a pas de sens (premier cran, cran inconnu) :
     l'appelant n'envoie rien. */
  function niveauApresGeste(d, niveauCran, coche) {
    const c = rang(d, niveauCran);
    if (c < 0) return null;
    if (coche) return d.echelle[c];
    return c === 0 ? null : d.echelle[c - 1];
  }

  /* L'état de chaque case hors rang pour un accès. « D'office » quand le niveau atteint
     `d_office` : la case est alors cochée ET ne se décoche pas — un propriétaire exporte,
     quoi qu'en dise la colonne. */
  function horsRang(d, niveau, valeurs) {
    const r = rang(d, niveau);
    return d.hors_rang.map((h) => {
      const office = h.d_office !== null && h.d_office !== undefined && r >= 0
        && r >= rang(d, h.d_office);
      return { code: h.code, champ: h.champ, libelle: h.libelle, d_office: office,
               coche: office || !!(valeurs && valeurs[h.champ]) };
    });
  }

  /* Le corps du `PUT` d'un accès : le niveau, et chaque champ hors rang qui est une DÉCISION.
     Le `PUT` ne change pas (AUTH-12, étape 3) ; seul ce qui le remplit se déduit de la
     description.

     `actuel` — le niveau de l'accès AVANT le geste — est ce qui fait la différence, et son
     absence a accordé un droit d'export (relevé le 2026-09-18). La liste des accès rend le
     droit EFFECTIF : un propriétaire y porte `exporter` vrai même si sa case n'a jamais été
     cochée, parce qu'il exporte D'OFFICE, et c'est la bonne réponse pour l'afficher — une
     liste qui le dirait « sans export » serait exacte et trompeuse (DROIT-2). Mais renvoyer
     cette valeur telle quelle en le RÉTROGRADANT la stocke, et le rétrogradé garde un droit
     que personne ne lui a donné. La faute échoue OUVERT : l'écran montre fidèlement ce que le
     serveur a enregistré, et aucun test ne tombe.

     Un champ d'office au niveau courant n'est donc pas AFFIRMÉ, il est OMIS — le serveur
     traite un champ absent en « ne pas y toucher », et la case redevient ce qu'elle est : une
     décision, ou rien. Sans `actuel`, rien n'est omis : les valeurs sont alors des décisions,
     ce qui est le cas d'un accès qu'on CRÉE. */
  function corpsAcces(d, base, niveau, valeurs, actuel) {
    const corps = { ...base, niveau };
    const office = new Set(actuel === undefined || actuel === null ? []
      : horsRang(d, actuel, valeurs).filter((h) => h.d_office).map((h) => h.champ));
    for (const h of d.hors_rang) {
      if (!office.has(h.champ)) corps[h.champ] = !!(valeurs && valeurs[h.champ]);
    }
    return corps;
  }

  /* Ce qu'un accès permet, en une phrase lisible — pour les fiches de « 👥 Comptes et
     groupes » et pour « Mon compte ». Les actes d'un cran se disent ensemble, reliés par
     « · » ; le DERNIER cran se dit « tous les actes », parce que c'est ce qu'il est, et
     « dont » nomme ce qu'il ajoute. Un niveau inconnu se dit tel quel : il ne disparaît pas
     (règle de l'étape 2, gardée). */
  function actesLus(d, niveau, valeurs) {
    const r = rang(d, niveau);
    if (r < 0) return String(niveau);
    const cs = crans(d);
    if (r === cs.length - 1 && cs.length > 1) {
      // « Tous » n'est vrai que si aucune case hors rang ne manque : une case qui ne vient
      // pas d'office au dernier cran se dit par son absence, au lieu d'être promise.
      const manquent = horsRang(d, niveau, valeurs).filter((h) => !h.coche)
        .map((h) => h.libelle);
      const haut = cs[r].actes.map((a) => a.libelle);
      return (manquent.length ? `tous les actes sauf ${manquent.join(", ")}` : "tous les actes")
        + (haut.length ? `, dont ${haut.join(" · ")}` : "");
    }
    const parties = cs.slice(0, r + 1).map(libelleCran);
    for (const h of horsRang(d, niveau, valeurs)) if (h.coche) parties.push(h.libelle);
    return parties.join(", ");
  }

  /* Les avertissements à dire sous le tableau : ceux des actes qu'au moins UN accès porte,
     dans l'ordre des actes. Un avertissement que personne ne peut déclencher ne se dit pas.

     CHACUN PORTE SES ACTES, et c'est le correctif du 2026-09-18 : la fonction ne rendait que
     des PHRASES, si bien que l'acte était perdu ICI, à la source. Rendue seule sous le
     tableau, « Supprimer un album efface ses images » ne disait plus de quoi elle parlait :
     on lisait un avertissement sans savoir ce qu'on était en train d'accorder. Le rattraper à
     l'affichage aurait demandé à l'écran de retrouver ce que le module avait jeté.

     UN SEUL PAR TEXTE, et il NOMME TOUS ses actes : deux actes qui partagent un
     avertissement le font dire une fois, en se nommant tous les deux — le taire pour l'un
     des deux serait un mensonge par omission. `niveaux` dit quelles cases l'accordent, pour
     que chacune puisse être DÉCRITE par lui ; c'est une liste parce que rien n'oblige deux
     actes de même avertissement à partager leur cran. */
  function avertissements(d, niveaux) {
    const par = new Map();
    for (const a of d.actes) {
      if (!a.avertissement) continue;
      if (!niveaux.some((n) => cranCoche(d, n, a.niveau))) continue;
      const e = par.get(a.avertissement)
        || { texte: a.avertissement, actes: [], niveaux: [] };
      e.actes.push({ code: a.code, libelle: a.libelle });
      if (!e.niveaux.includes(a.niveau)) e.niveaux.push(a.niveau);
      par.set(a.avertissement, e);
    }
    return [...par.values()];
  }

  return {
    estValide, rang, crans, libelleCran, colonnes, cranCoche, cranModifiable,
    niveauApresGeste, horsRang, corpsAcces, actesLus, avertissements,
  };
});
