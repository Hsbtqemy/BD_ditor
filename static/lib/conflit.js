/* Ce que l'Atelier DIT d'un conflit (CONC-3, second temps) — logique PURE, sans DOM.
   Chargé en <script> AVANT viewer.js → expose `window.BDConflit` ; aussi require()-able
   par `tests/js/conflit.test.js`.

   Le serveur refuse un enregistrement fait sur une valeur périmée par un 409 qui porte
   `detail.conflit` (champ, valeur actuelle, auteur), et une écriture sur une région
   supprimée par un 410 qui porte `detail.suppression`. Ce module en fait des PHRASES :
   le titre du bandeau, l'heure lisible, le message d'une case supprimée. Il vit ici et
   non dans viewer.js pour une propriété — l'heure relative et l'accord des mots se
   vérifient par une table de cas —, et parce que les LIBELLÉS des deux gestes doivent
   vivre à UN seul endroit : Hugo les a encore précisés après la maquette (2026-09-17). */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDConflit = api;                                                  // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Les deux gestes du bandeau. « Remplacer par la mienne » renvoie SA version, qui écrase celle de
     l'autre ; « Garder l'autre » conserve la version concurrente. Partout, compte partagé
     compris. Changer un libellé se fait ICI, et nulle part ailleurs. */
  const GESTES = Object.freeze({
    remplacer: "Remplacer par la mienne",
    garderAutre: "Garder l'autre",
  });

  /* Le nom qu'un titre donne au champ, avec son accord : « Note modifiée », « Texte
     modifié ». Un champ inconnu se nomme par défaut au féminin, « Valeur modifiée ». */
  const CHAMPS = {
    note: ["Note", "f", "la note"],
    ocr_texte: ["Texte", "m", "le texte"],
    x: ["Position", "f", "la position"], y: ["Position", "f", "la position"],
    w: ["Taille", "f", "la taille"], h: ["Taille", "f", "la taille"],
    type: ["Type", "m", "le type"],
    parent_id: ["Rattachement", "m", "le rattachement"],
  };
  const INCONNU = ["Valeur", "f", "la valeur"];

  /* Comment désigner une région dans « Cette case a été supprimée ». */
  const REGIONS = {
    case: ["Cette case", "f"],
    bulle: ["Cette bulle", "f"],
    cartouche: ["Ce cartouche", "m"],
    texte: ["Cette zone de texte", "f"],
    personnage: ["Cette boîte personnage", "f"],
  };

  const accord = (genre) => (genre === "m" ? "" : "e");
  const deux = (n) => String(n).padStart(2, "0");

  /* « 14 h 32 », « 8 h 05 » : l'heure sans zéro de tête, les minutes sur deux chiffres. */
  function heure(d) {
    return `${d.getHours()} h ${deux(d.getMinutes())}`;
  }

  /* Le moment d'une modification, en heure LOCALE, avec la date quand ce n'est pas le jour
     (verdict de Hugo) : « à 14 h 32 », « hier à 14 h 32 », « le 15/09 à 14 h 32 ».
     L'année ne s'écrit que si elle n'est pas celle de `maintenant`. Une date illisible ne
     fabrique pas d'heure : la phrase s'en passe. */
  function quand(iso, maintenant) {
    const d = new Date(iso);
    if (!iso || isNaN(d.getTime())) return "";
    const ref = maintenant || new Date();
    const jour = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const ecart = Math.round((jour(ref) - jour(d)) / 86400000);
    if (ecart === 0) return `à ${heure(d)}`;
    if (ecart === 1) return `hier à ${heure(d)}`;
    const date = `${deux(d.getDate())}/${deux(d.getMonth() + 1)}` +
      (d.getFullYear() === ref.getFullYear() ? "" : `/${d.getFullYear()}`);
    return `le ${date} à ${heure(d)}`;
  }

  /* Qui : « par Bob Martin », « depuis un autre écran de ce même compte », ou « ailleurs »
     quand le journal n'a personne à nommer. */
  function parQui(auteur) {
    if (!auteur) return "ailleurs";
    if (auteur.meme_compte) return "depuis un autre écran de ce même compte";
    const nom = auteur.nom || auteur.login;
    return nom ? `par ${nom}` : "ailleurs";
  }

  const phrase = (...morceaux) => morceaux.filter(Boolean).join(" ");

  /* Le titre du bandeau : « Note modifiée par Bob Martin à 14 h 32 ». */
  function titreConflit(conflit, maintenant) {
    const [nom, genre] = CHAMPS[conflit && conflit.champ] || INCONNU;
    const a = conflit && conflit.auteur;
    return phrase(`${nom} modifié${accord(genre)}`, parQui(a),
                  a ? quand(a.le, maintenant) : "");
  }

  /* Le toast d'un conflit arrivé APRÈS qu'on a quitté le champ — l'enregistrement parti en
     changeant de bulle ou de mode : il n'y a plus de champ où ouvrir le bandeau, et le
     dire est tout ce qui reste. « Note modifiée par Bob Martin à 14 h 32 : la vôtre n'a
     pas été enregistrée. » */
  function messageNonEnregistre(conflit, maintenant) {
    const [, genre] = CHAMPS[conflit && conflit.champ] || INCONNU;
    return `${titreConflit(conflit, maintenant)} : ${genre === "m" ? "le" : "la"} vôtre ` +
      `n'a pas été enregistré${accord(genre)}.`;
  }

  /* Le toast d'une région supprimée par un autre : « Cette case a été supprimée par Alice
     Dupont à 8 h 14 ». */
  function messageSuppression(suppression, typeRegion, maintenant) {
    const [ce, genre] = REGIONS[typeRegion] || ["Cette région", "f"];
    const a = suppression && suppression.auteur;
    return phrase(`${ce} a été supprimé${accord(genre)}`, parQui(a),
                  a ? quand(a.le, maintenant) : "") + ".";
  }

  /* Le refus d'une annulation qui écraserait ce qu'un autre a changé depuis. */
  function messageAnnulationRefusee(conflit, maintenant) {
    const [, genre, article] = CHAMPS[conflit && conflit.champ] || INCONNU;
    const a = conflit && conflit.auteur;
    return phrase(`Annulation impossible : ${article} a été modifié${accord(genre)} depuis`,
                  parQui(a), a ? quand(a.le, maintenant) : "") + ".";
  }

  return { GESTES, heure, quand, parQui, titreConflit, messageNonEnregistre,
           messageSuppression, messageAnnulationRefusee };
});
