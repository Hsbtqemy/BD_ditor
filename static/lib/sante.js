/* État affiché des moteurs de reconnaissance (SANTE-1) — logique PURE, sans DOM.
   Chargé en <script> AVANT corpus.js → expose `window.BDSante` ; aussi require()-able
   par `tests/js/sante.test.js`, qui est le seul endroit où cette règle se vérifie
   vraiment : elle croise deux réponses du serveur, et un test qui lirait le source à la
   recherche des bons mots se satisfait de les trouver dans la mauvaise branche (mesuré).

   Pourquoi une règle plutôt qu'un affichage direct de `/api/sante`.

   Cette route répond en LOCALISANT les modules (`find_spec`), sans jamais les importer —
   raccourci délibéré, torch coûtant plusieurs secondes, et aveugle à toute
   incompatibilité binaire : le 2026-08-27 elle annonçait `bulles: true` sur une pile dont
   le premier `import ultralytics` levait une exception. Recopier sa réponse dans un
   panneau ne ferait que déplacer le mensonge dans une fenêtre, en le rendant plus
   crédible qu'avant.

   Deux règles, donc :

   1. NE PAS REJOUER LE MENSONGE. Le contrôle rapide n'autorise que le mot « présent » ;
      « opérationnel » ne s'écrit qu'après un import réel (`?profond=1`).
   2. L'ABSENCE N'EST PAS UNE PANNE. Les moteurs sont OPTIONNELS et la plupart des postes
      n'en installent aucun : crier « en panne » sur une machine où personne n'a voulu
      d'EasyOCR apprendrait à ignorer le panneau, et il serait ignoré le jour utile.

   D'où le croisement : le contrôle profond fait AUTORITÉ sur le fait — il a réellement
   tenté l'import — et le rapide ne choisit plus que le MOT de l'échec. Un module
   introuvable se dit « non installé », un module trouvé qui ne s'importe pas « en panne ».
   Ce dernier cas est le seul grave, et le seul que ce panneau existe pour montrer. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDSante = api;                                                    // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* `cle` (contrôle profond) et `rapide` (contrôle de présence) DIFFÈRENT pour le NLP :
     la route historique dit `lemmes`, `sante.MOTEURS` dit `nlp`, et le contrat public de
     `/api/sante` interdit de renommer l'un pour faire plaisir à l'autre. Les deux jeux de
     clefs sont donc appariés ICI, et `tests/test_sante.py` vérifie que cette table
     correspond toujours au serveur : un renommage côté Python laisserait sinon un panneau
     parfaitement muet, sans la moindre erreur nulle part. */
  const MOTEURS = [
    { cle: "kumiko", rapide: "kumiko", nom: "Kumiko",
      role: "découpe des cases — passe 1" },
    { cle: "bulles", rapide: "bulles", nom: "YOLOv8 (bulles)",
      role: "détection des bulles — passe 2" },
    { cle: "ocr", rapide: "ocr", nom: "EasyOCR",
      role: "lecture du texte — passe 3" },
    { cle: "nlp", rapide: "lemmes", nom: "spaCy",
      role: "lemmes et grammaire — Recherche, Exploration" },
  ];

  /* `rapide` = la réponse de `/api/sante` ; `profond` = son bloc `profond` (ou null tant
     que personne n'a éprouvé). Retourne { etat, mot, note } — `etat` sert la couleur, le
     MOT porte l'information à lui seul (WCAG 1.4.1 : la teinte ne fait que renforcer). */
  function etat(rapide, profond, moteur) {
    const present = !!(rapide && rapide[moteur.rapide]);
    const p = profond ? profond[moteur.cle] : null;
    if (!p) {
      return present
        ? { etat: "present", mot: "présent, non éprouvé",
            note: "Le module est là. Qu'il fonctionne reste à prouver." }
        : { etat: "absent", mot: "non installé",
            note: "Sa passe répondra 503. Normal si vous ne vous en servez pas." };
    }
    if (p.ok) {
      return { etat: "ok", mot: "opérationnel", note: "Importé pour de bon, sans erreur." };
    }
    const cause = p.erreur || "cause non rapportée par le serveur";
    return present
      ? { etat: "panne", mot: "en panne", note: cause }
      : { etat: "absent", mot: "non installé", note: cause };
  }

  /* Le BILAN d'une épreuve, en une phrase. Ici et non dans la page, parce qu'il a un
     mode d'échec silencieux : une réponse sans verdict — bloc `profond` absent, filtré
     par un proxy, ou parlant d'autres moteurs que les nôtres — laisse les quatre sur
     « non éprouvé ». Un bilan qui ne compterait que les pannes conclurait alors « aucun
     moteur installé », phrase rassurante et fausse à l'instant précis où le diagnostic
     vient d'échouer. On distingue donc « rien à rapporter » de « rien rapporté ».

     Le comptage porte sur NOS moteurs et non sur les clefs reçues : un serveur qui a
     renommé `nlp` renverrait un bloc non vide dont pas une clef ne nous concerne — c'est
     exactement la panne que surveille le cliquet de `tests/test_sante.py`, et il ne
     faudrait pas qu'elle passe ici pour un verdict. */
  function bilan(rapide, profond) {
    const verdicts = MOTEURS.filter((m) => profond && profond[m.cle]).length;
    if (!verdicts) {
      return { erreur: true,
               texte: "Le serveur n'a renvoyé aucun verdict : le contrôle profond n'a "
                      + "pas abouti. Rien n'est prouvé, ni dans un sens ni dans l'autre." };
    }
    const etats = MOTEURS.map((m) => etat(rapide, profond, m).etat);
    const pannes = etats.filter((e) => e === "panne").length;
    if (pannes) {
      return { erreur: true,
               texte: `${pannes} moteur${pannes > 1 ? "s" : ""} installé`
                      + `${pannes > 1 ? "s" : ""} mais inutilisable`
                      + `${pannes > 1 ? "s" : ""}. La cause est ci-dessus ; quoi en `
                      + "faire : docs/deploiement-docker.md, « Un moteur en panne »." };
    }
    return { erreur: false,
             texte: etats.includes("ok")
               ? "Tous les moteurs installés répondent."
               : "Aucun moteur installé sur cette instance. Les passes de "
                 + "reconnaissance répondront 503 ; le reste de l'outil fonctionne." };
  }

  return { MOTEURS, etat, bilan };
});
