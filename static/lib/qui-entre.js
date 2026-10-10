/* « Qui entre » (UX-16) — les accès d'UNE collection, en module MONTABLE.

   Chargé en <script> APRÈS common.js et droits.js → expose `window.BDQuiEntre` ; aussi
   require()-able par `tests/js/qui-entre.test.js`. Il n'atteint le document qu'au MONTAGE :
   le charger ne lit ni `document`, ni `window.matchMedia`, ni l'adresse.

   POURQUOI UN MODULE. Le panneau a déménagé deux fois en treize jours — l'Administration
   (COL-2, 2026-09-10), puis la fiche de la collection dans la Bibliothèque (AUTH-12,
   2026-09-17) — et l'usage a contesté la seconde place dès le 2026-09-23. Ce n'était pas un
   mauvais choix qui revenait : c'est un panneau à DEUX publics. Le propriétaire part de son
   corpus, l'administrateur part d'une personne ; quel que soit l'endroit unique retenu,
   l'autre traverse deux écrans. Un second public ne se sert pas par un déménagement de plus,
   mais par un second montage — et le même écran ne s'écrit pas deux fois.

   LE CONTRAT.

     BDQuiEntre.monter(cible, options) → { rafraichir, focaliser, demonter }

   `cible`               une <section> VIDE de l'hôte, DÉJÀ dans le document (sinon `monter`
                         lève). Le module l'INVESTIT : elle devient la partie « Qui entre »
                         (classe, nom accessible), et `demonter` la rend vide, sans ce qu'il y
                         a posé. Monter deux fois au même endroit remplace.
   `options.collection`  { id, nom, administrable } — la garde est celle de l'ACTE : sans
                         `administrable`, le module le DIT au lieu de se taire, et ne lit rien.
   `options.droits`      la description servie par `GET /api/droits`, déjà validée, ou null
                         si elle est illisible ; une promesse est acceptée.
   `options.groupesAdmin` `acces.groupes_admin` de `GET /api/moi` (AUTH-4).
   `options.preselection` un nom de groupe à présélectionner dans la ligne d'ajout, consommé
                         une fois l'annuaire connu.
   `options.surMessage(ligne)`  appelé chaque fois que le module écrit sa ligne de message.
   `options.surChangement()`    appelé après un geste que le serveur a accepté.
   `options.surOuvrir({ genre, principal })`  si l'hôte a une FICHE à ouvrir pour un compte
                         ou un groupe : chaque nom devient alors un bouton qui l'appelle. Sans
                         elle, un nom est du texte — un propriétaire, dans la Bibliothèque,
                         n'a aucune fiche de compte à ouvrir, et un bouton qui ne mènerait
                         nulle part serait pire que pas de bouton.
   `options.niveauTitre` le rang du titre « Qui entre » dans le plan de l'hôte (3 par défaut,
                         de 2 à 6) : le panneau EST une partie de la page qui le monte, et
                         son titre se range sous celui qui le précède là-bas.

   CE QUE LE MODULE NE FAIT PAS, et ce sont les cinq coutures mesurées le 2026-09-23.
   Il ne cherche rien dans la page : il travaille dans SA section. Il n'efface aucun message
   ailleurs : « un seul message à la fois » est une règle d'ÉCRAN, que l'hôte applique s'il
   la veut, prévenu par `surMessage`. Il ne lit ni `location` ni l'historique : la
   présélection lui est passée. Il ne charge ni la description des droits ni l'identité :
   l'hôte les a déjà. En revanche il LIT ses propres données — `…/acces` et `…/annuaire` —,
   sans quoi le contrat du serveur vivrait dans deux écrans.

   EN ACTES, JAMAIS EN NIVEAUX. Le tableau lit la description des droits et n'écrit ni acte,
   ni libellé, ni niveau : toute la logique est dans `static/lib/droits.js`, éprouvée sur la
   description d'aujourd'hui ET sur deux issues hypothétiques d'AUTH-10. Une case par CRAN :
   des actes que le serveur accorde ensemble ne se cochent pas séparément.

   DEUX LECTURES, ET LA SECONDE N'ATTEND PAS. `…/acces` dessine le tableau tout de suite ;
   `…/annuaire` arrive après et remplit « Signal » et la liste des groupes. Un annuaire en
   panne ne retarde donc aucun geste (c'est la raison même des deux routes).

   CE QUE LE REFUS D'ÉCRAN NE FERME PAS. Le `PUT` d'un accès RE-POSE un niveau : « faire
   entrer » un nom déjà présent le rétrograderait en lecture. L'écran le refuse avant
   d'envoyer, sur le couple (compte ou groupe, nom exact) — mais un autre onglet, ou une
   liste relue avant le geste d'un autre, peut encore rétrograder. Limite écrite dans la
   fiche AUTH-12, pas fermée côté serveur. */
(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) {                    // Node (tests)
    const commun = require("./common.js");
    module.exports = factory({ esc: commun.escapeHtml, apiGet: commun.apiGet,
                               apiSend: commun.apiSend, BDDroits: require("./droits.js") });
  } else {
    root.BDQuiEntre = factory(root);                                        // navigateur
  }
})(typeof self !== "undefined" ? self : this, function (env) {
  "use strict";

  // Lus à l'APPEL, jamais au chargement : `env` est la fenêtre, et l'ordre des balises
  // <script> n'a pas à être deviné ici.
  const esc = (s) => env.esc(s);
  const droitsLib = () => env.BDDroits;

  /* Sous 48em, le tableau devient une carte par accès (tranché par Hugo le 2026-09-17), et
     l'on redessine au franchissement. Le seuil n'est écrit QU'ICI : c'est le rendu qui
     bascule, pas la feuille. Le commentaire d'origine le disait « celui de la règle `@media`
     de `style.css` » ; elle n'en a aucune à ce seuil (mesuré le 2026-10-07, par un test
     écrit pour vérifier la phrase). */
  const SEUIL_ETROIT = "(max-width: 47.9375em)";

  /* LES IDENTIFIANTS SONT PROPRES AU MONTAGE. Le suffixe était l'id de la collection
     (`qe-choix-12`) : il tenait tant qu'une collection n'était montée qu'une fois par page,
     et cette condition était une chance. C'est ici une PROPRIÉTÉ : le premier montage d'une
     collection garde le suffixe nu — rien ne change pour lui —, un second montage VIVANT de
     la même collection en reçoit un autre. Un montage dont la section a quitté le document
     ne compte plus : l'hôte qui redessine sans démonter ne fabrique pas de collision, ni de
     suffixe qui dérive. */
  const SUFFIXES = new Map();          // suffixe → montage

  function prendreSuffixe(id, montage, vivant) {
    for (const [s, m] of SUFFIXES) if (!vivant(m)) SUFFIXES.delete(s);
    let s = String(id);
    for (let n = 2; SUFFIXES.has(s); n++) s = `${id}m${n}`;
    SUFFIXES.set(s, montage);
    return s;
  }

  /* Rendu par CELUI qui le tient, et par lui seul : un montage mort dont le suffixe a déjà
     été repris par un vivant ne doit pas le lui retirer en se démontant après coup — ce
     serait fabriquer, un geste plus tard, la collision que ce registre empêche. */
  function rendreSuffixe(s, montage) {
    if (SUFFIXES.get(s) === montage) SUFFIXES.delete(s);
  }

  /* Quel montage occupe quelle cible. Monter deux fois au même endroit REMPLACE, et un
     montage mort ne vide pas, en se démontant, ce qu'un autre a dessiné depuis à sa place. */
  const OCCUPANTS = new WeakMap();     // cible → montage

  /* Les administrateurs d'instance lisent et écrivent toute collection sans figurer dans
     aucune liste d'accès (AUTH-4). Sans cette note, la liste mentirait par omission. Nommés
     d'après `/api/moi`, jamais une constante recopiée ; rien en mono-poste, où l'on est
     seul. */
  function noteAdmin(groupes) {
    const g = groupes || [];
    if (!g.length) return "";
    return `<p class="col-note col-note-admin">Les administrateurs de l'instance
    (${g.map(esc).join(", ")}) lisent et écrivent <strong>toute</strong> collection, sans
    figurer dans aucune liste d'accès. Chacun de leurs actes est nommé au journal de
    provenance.</p>`;
  }

  function cle(a) {
    return `data-genre="${esc(a.genre)}" data-principal="${esc(a.principal)}"`;
  }

  function sel(a) {
    return `[data-genre="${CSS.escape(a.genre)}"][data-principal="${CSS.escape(a.principal)}"]`;
  }

  /* Le nom d'un accès, avec ce qu'il EST : l'icône pour l'œil, le mot pour le lecteur d'écran.
     « compte » et non « utilisateur » : lexique de la décision 7 d'AUTH-12.

     Le nom n'est un BOUTON que si l'hôte a dit où il mène (`surOuvrir`). Sans cela il reste
     le texte qu'il a toujours été : le montage de la Bibliothèque ne change pas d'un
     caractère, et c'est lui le témoin. */
  function qui(m, a) {
    const groupe = a.genre === "groupe";
    const nom = typeof m.options.surOuvrir === "function"
      ? `<button type="button" class="qe-ouvrir" ${cle(a)}>${esc(a.principal)}</button>`
      : esc(a.principal);
    return `<span aria-hidden="true">${groupe ? "👥" : "👤"}</span> `
      + `<span class="sr-only">${groupe ? "groupe" : "compte"} </span>${nom}`;
  }

  /* Les valeurs des cases hors rang d'un accès, sous leur `champ` : ce que le serveur rend
     dans `…/acces`, et ce que le `PUT` renvoie. */
  function valeurs(m, a) {
    return Object.fromEntries(m.droits.hors_rang.map((h) => [h.champ, !!a[h.champ]]));
  }

  /* Ce que l'annuaire dit d'un accès : « trouve », « inconnu », « non_verifie »,
     « sans_annuaire », ou null tant qu'il n'a pas répondu. */
  function verification(m, genre, principal) {
    const an = m.etat.annuaire;
    if (!an || !Array.isArray(an.acces)) return null;
    const par = genre === "groupe" ? "groupe" : "compte";
    const v = an.acces.find((x) => x.par === par
      && (par === "groupe" ? x.groupe : x.login) === principal);
    return v ? v.verification : null;
  }

  /* La colonne « Signal » (UX-4). Ce que l'annuaire dit d'abord ; puis, pour un compte,
     qu'il n'a pas encore ouvert l'application (AUTH-6) — l'observation seule, qui ne
     distingue pas une faute de frappe d'un arrivant, et ne doit pas le prétendre. */
  function signal(m, a) {
    const v = verification(m, a.genre, a.principal);
    const marques = [];
    if (v === "inconnu") marques.push(`<span class="qe-marque">inconnu de l'annuaire</span>`);
    else if (v === "non_verifie") marques.push(`<span class="qe-marque">non vérifié</span>`);
    if (a.jamais_vu === true && v !== "inconnu") {
      marques.push(`<span class="acces-jamais-vu">n'a pas encore ouvert l'application</span>`);
    }
    return marques.join(" ");
  }

  function depuis(a) {
    return esc((a.date_creation || "").slice(0, 10));
  }

  /* L'identifiant de l'avertissement affiché : celui de son PREMIER acte, qui suffit à le
     distinguer — un texte n'est rendu qu'une fois, quel que soit le nombre d'actes qui le
     portent. */
  function idAvertissement(m, av) {
    return `qe-${m.sfx}-av-${av.actes[0].code}`;
  }

  /* Les avertissements AFFICHÉS, rangés par cran : la case d'un cran est DÉCRITE par
     l'avertissement de l'acte qu'elle accorde (`aria-describedby`) — cocher ce cran accorde
     cet acte, donc la description est vraie et non décorative. Recalculé ici plutôt que passé
     de signature en signature : `avertissements` est une fonction pure. */
  function descriptions(m) {
    const par = {};
    if (!m.droits || !m.etat.acces) return par;
    for (const av of droitsLib().avertissements(m.droits, m.etat.acces.map((a) => a.niveau))) {
      for (const n of av.niveaux) par[n] = idAvertissement(m, av);
    }
    return par;
  }

  function decritPar(decrit, niveau) {
    return decrit[niveau] ? ` aria-describedby="${esc(decrit[niveau])}"` : "";
  }

  /* Le tableau, au-dessus de 48em. Les en-têtes de colonnes sont les ACTES ; une case par
     cran, dont la cellule couvre les actes qu'elle accorde ensemble. Le nom accessible de
     chaque case CROISE l'en-tête de ligne et ceux de ses colonnes (`aria-labelledby`) : un
     lecteur d'écran entend « groupe annotateurs, annoter, organiser les albums… » sur une
     case unique, c'est-à-dire la liaison dite en clair. */
  function table(m) {
    const BDDroits = droitsLib(), DROITS = m.droits, etat = m.etat;
    const id = m.sfx;
    const cols = BDDroits.colonnes(DROITS);
    const decrit = descriptions(m);
    const idsCran = (col) => (col.actes.length
      ? col.actes.map((a) => `qe-${id}-a-${a.code}`) : [`qe-${id}-n-${col.niveau}`]);
    // Les actes accordés ENSEMBLE sont CHAPEAUTÉS, sur deux rangs d'en-tête. Le trait dessiné
    // sous leur case unique disait bien la liaison, et disait aussi autre chose : deux pixels
    // en travers d'une cellule, une case posée au milieu, c'est le vocabulaire d'un curseur
    // qu'on croit pouvoir glisser (relevé par Hugo le 2026-09-18). L'intention était
    // structurelle, le rendu décoratif, et c'est le rendu qui gagne. Un chapeau EST la
    // structure : il ne se confond avec rien, et un lecteur d'écran l'annonce — un dessin, lui,
    // ne s'annonce jamais. Le second rang n'existe que s'il y a quelque chose à chapeauter.
    const groupe = (col) => col.type === "cran" && col.actes.length > 1;
    const chapeaux = cols.some(groupe);
    const rang2 = chapeaux ? ' rowspan="2"' : "";
    const idsEnTete = (col) => (groupe(col) ? [`qe-${id}-g-${esc(col.niveau)}`] : idsCran(col));
    const tetes = cols.map((col) => {
      if (col.type !== "cran") {
        return `<th scope="col"${rang2} id="qe-${id}-h-${esc(col.code)}" class="qe-hors-rang">${esc(col.libelle)}</th>`;
      }
      if (groupe(col)) {
        return `<th scope="colgroup" colspan="${col.actes.length}" class="qe-groupe"`
          + ` id="${idsEnTete(col)[0]}">${esc(col.libelle)}</th>`;
      }
      const seul = col.actes.length ? col.actes[0] : { libelle: col.libelle };
      return `<th scope="col"${rang2} id="${idsCran(col)[0]}" class="qe-acte">${esc(seul.libelle)}</th>`;
    }).join("");
    // Le second rang ne porte QUE les actes chapeautés : les autres colonnes le traversent par
    // `rowspan`, et le navigateur range donc ces en-têtes sous leur chapeau, dans l'ordre.
    const sousTetes = chapeaux
      ? `<tr>${cols.filter(groupe).map((col) => col.actes.map((a, k) =>
          `<th scope="col" id="${idsCran(col)[k]}" class="qe-acte">${esc(a.libelle)}</th>`)
          .join("")).join("")}</tr>`
      : "";
    const lignes = etat.acces.map((a, i) => {
      const ligne = `qe-${id}-r${i}`;
      const vals = valeurs(m, a);
      const hr = BDDroits.horsRang(DROITS, a.niveau, vals);
      const cellules = cols.map((col) => {
        if (col.type === "cran") {
          const n = Math.max(1, col.actes.length);
          const coche = BDDroits.cranCoche(DROITS, a.niveau, col.niveau);
          const libre = BDDroits.cranModifiable(DROITS, col.niveau);
          // `qe-lie` ne dessine plus rien : elle NOMME la cellule fusionnée, pour la feuille
          // comme pour le test qui vérifie que les actes liés n'ont qu'une case.
          return `<td class="qe-cran${n > 1 ? " qe-lie" : ""}"${n > 1 ? ` colspan="${n}"` : ""}>`
            + `<input type="checkbox" class="qe-case" data-cran="${esc(col.niveau)}" ${cle(a)}`
            + ` aria-labelledby="${ligne} ${idsEnTete(col).join(" ")}"`
            + decritPar(decrit, col.niveau)
            + `${coche ? " checked" : ""}${libre ? "" : " disabled"}></td>`;
        }
        const h = hr.find((x) => x.code === col.code);
        return `<td class="qe-hors-rang"><input type="checkbox" class="qe-case"`
          + ` data-hors-rang="${esc(col.code)}" data-hors-rang-champ="${esc(col.champ)}" ${cle(a)}`
          + ` aria-labelledby="${ligne} qe-${id}-h-${esc(col.code)}"`
          + `${h.coche ? " checked" : ""}${h.d_office ? " disabled" : ""}>`
          + `${h.d_office ? ` <span class="muted small">(d'office)</span>` : ""}</td>`;
      }).join("");
      return `<tr ${cle(a)}><th scope="row" id="${ligne}">${qui(m, a)}</th>${cellules}
      <td class="qe-depuis">${depuis(a)}</td>
      <td class="qe-signal">${signal(m, a)}</td>
      <td><button class="ghost small qe-retirer" type="button" ${cle(a)}
                  aria-label="Retirer l'accès de ${esc(a.principal)}">✕</button></td></tr>`;
    }).join("");
    return `<div class="table-cadre qe-cadre" tabindex="0" role="region"
               aria-label="Qui entre dans ${esc(m.c.nom)}">
    <table class="corpus-table qe-table">
      <thead><tr><th scope="col"${rang2}>Qui</th>${tetes}<th scope="col"${rang2}>Depuis le</th>
        <th scope="col"${rang2}>Signal</th>
        <th scope="col"${rang2}><span class="sr-only">Retirer</span></th></tr>${sousTetes}</thead>
      <tbody>${lignes}</tbody>
    </table></div>`;
  }

  /* Les cartes, sous 48em : une par accès, une case par cran libellée des actes qu'elle
     accorde, puis les cases hors rang, et « Depuis le » en ligne. */
  function cartes(m) {
    const BDDroits = droitsLib(), DROITS = m.droits, etat = m.etat;
    const id = m.sfx;
    const crans = BDDroits.crans(DROITS);
    const decrit = descriptions(m);
    return `<ul class="qe-cartes">${etat.acces.map((a, i) => {
      const ligne = `qe-${id}-r${i}`;
      const vals = valeurs(m, a);
      const cases = crans.map((cr) => {
        const lib = `${ligne}-n-${cr.niveau}`;
        return `<label class="qe-case-carte"><input type="checkbox" class="qe-case"`
          + ` data-cran="${esc(cr.niveau)}" ${cle(a)} aria-labelledby="${ligne} ${lib}"`
          + decritPar(decrit, cr.niveau)
          + `${BDDroits.cranCoche(DROITS, a.niveau, cr.niveau) ? " checked" : ""}`
          + `${BDDroits.cranModifiable(DROITS, cr.niveau) ? "" : " disabled"}>`
          + ` <span id="${lib}">${esc(BDDroits.libelleCran(cr))}</span></label>`;
      }).join("") + BDDroits.horsRang(DROITS, a.niveau, vals).map((h) => {
        const lib = `${ligne}-h-${h.code}`;
        return `<label class="qe-case-carte"><input type="checkbox" class="qe-case"`
          + ` data-hors-rang="${esc(h.code)}" data-hors-rang-champ="${esc(h.champ)}" ${cle(a)}`
          + ` aria-labelledby="${ligne} ${lib}"${h.coche ? " checked" : ""}${h.d_office ? " disabled" : ""}>`
          + ` <span id="${lib}">${esc(h.libelle)}${h.d_office ? " (d'office)" : ""}</span></label>`;
      }).join("");
      const d = depuis(a);
      return `<li class="qe-carte" ${cle(a)}>
      <div class="qe-carte-tete"><span class="qe-qui" id="${ligne}">${qui(m, a)}</span>
        <span class="qe-signal">${signal(m, a)}</span>
        <button class="ghost small qe-retirer" type="button" ${cle(a)}
                aria-label="Retirer l'accès de ${esc(a.principal)}">✕</button></div>
      <div class="qe-carte-cases">${cases}</div>
      ${d ? `<p class="muted small qe-depuis">Depuis le ${d}</p>` : ""}</li>`;
    }).join("")}</ul>`;
  }

  function tableauHtml(m) {
    const etat = m.etat;
    if (etat.erreur) return `<p class="col-note">${esc(etat.erreur)}</p>`;
    if (!etat.acces) return `<p class="col-note">Chargement…</p>`;
    if (!m.droits) {
      return `<p class="col-note">La description des droits n'a pas pu être lue : les accès ne
      se règlent pas d'ici tant qu'elle manque.</p>
      <ul class="qe-noms">${etat.acces.map((a) =>
        `<li>${qui(m, a)} — ${esc(a.niveau)}</li>`).join("")}</ul>`;
    }
    if (!etat.acces.length) {
      return `<p class="col-note">Aucun accès n'est accordé sur cette collection.</p>`;
    }
    return m.etroit.matches ? cartes(m) : table(m);
  }

  /* Ce que la ligne d'ajout contenait, relevé avant de la redessiner : l'annuaire arrive
     APRÈS l'ouverture, et le nom qu'on a commencé à taper ne doit pas partir avec. */
  function releveAjout(sec) {
    const choix = sec.querySelector(".qe-choix");
    if (!choix) return null;
    return { choix: choix.value, touche: choix.dataset.touche === "1",
             nom: sec.querySelector(".qe-nom").value,
             genre: sec.querySelector(".qe-genre").value };
  }

  /* La ligne d'ajout, dans l'ordre de la décision 4 (2) : les GROUPES de l'annuaire (leurs
     noms seuls — le propriétaire ne voit ni les comptes ni les membres), puis la saisie
     libre, qui exige de dire « Compte » ou « Groupe » SANS valeur par défaut (COL-2, tranché
     le 2026-09-16 : un groupe accordé comme compte n'ouvre rien à personne). Et aucune
     présélection d'un groupe non plus : « Choisir… » en tête, sans quoi « + Faire entrer »
     accorderait le premier de la liste par inertie. */
  function ajoutHtml(m, garde) {
    const etat = m.etat;
    if (!m.droits || etat.erreur || !etat.acces) return "";
    const id = m.sfx;
    const an = etat.annuaire;
    const groupes = an && Array.isArray(an.groupes) ? an.groupes : [];
    const connues = new Set(["", "autre", ...groupes.map((g) => `groupe:${g}`)]);
    let choix, nom = "", genre = "", touche = false;
    if (garde && garde.touche && connues.has(garde.choix)) {
      ({ choix, nom, genre, touche } = garde);
    } else if (garde && garde.choix === "autre" && (garde.nom || garde.genre)) {
      ({ choix, nom, genre } = garde);
    } else {
      choix = groupes.length ? "" : "autre";
    }
    // La présélection passée par l'hôte (« Ouvrir une collection à ce groupe… »), consommée
    // une fois l'annuaire connu : listé, le groupe est choisi ; absent, il est tapé.
    if (an && m.preselection) {
      const g = m.preselection;
      m.preselection = null;
      if (groupes.includes(g)) { choix = `groupe:${g}`; }
      else { choix = "autre"; nom = g; genre = "groupe"; }
      touche = true;
    }
    const opt = (v, lib) => `<option value="${esc(v)}"${v === choix ? " selected" : ""}>${esc(lib)}</option>`;
    return `<div class="qe-ajout-ligne">
      <label for="qe-choix-${id}">Faire entrer</label>
      <select id="qe-choix-${id}" class="qe-choix"${touche ? ' data-touche="1"' : ""}>
        ${opt("", "Choisir…")}
        ${groupes.length ? `<optgroup label="Groupes de l'annuaire">${groupes.map((g) =>
          opt(`groupe:${g}`, g)).join("")}</optgroup>` : ""}
        ${opt("autre", "Un compte, ou un groupe absent de la liste…")}
      </select>
      <span class="qe-libre"${choix === "autre" ? "" : " hidden"}>
        <input id="qe-nom-${id}" class="qe-nom" placeholder="nom exact"
               autocomplete="off" aria-label="Nom exact du compte ou du groupe"
               value="${esc(nom)}">
        <select id="qe-genre-${id}" class="qe-genre" aria-label="Compte ou groupe">
          <option value=""${genre ? "" : " selected"}>Compte ou groupe ?</option>
          <option value="utilisateur"${genre === "utilisateur" ? " selected" : ""}>Compte</option>
          <option value="groupe"${genre === "groupe" ? " selected" : ""}>Groupe</option>
        </select>
      </span>
      <button class="primary small qe-faire-entrer" type="button">+ Faire entrer</button>
    </div>`;
  }

  /* Ce qui vaut TOUJOURS, sous la ligne de message, et d'un seul tenant : l'avertissement d'un
     acte, l'état de l'annuaire, le pouvoir des administrateurs. Trois traitements visuels en
     trois lignes ne disaient pas lequel comptait (relevé par Hugo le 2026-09-18) ; ils tiennent
     désormais dans UN bloc, distinct de ce qui vient du dernier geste. L'ordre ne change pas —
     ce qu'on est en train d'accorder d'abord, ce que l'application ne sait pas ensuite, ce
     qu'elle n'a pas à dire deux fois à la fin. */
  function notesHtml(m) {
    const etat = m.etat;
    const notes = [];
    if (m.droits && etat.acces) {
      // L'avertissement NOMME son acte. Rendu seul, il ne disait plus de quoi il parlait : on
      // lisait « Supprimer un album efface ses images » sans savoir ce qu'on accordait. Et la
      // case du cran qui l'accorde le cite en `aria-describedby` (cf. `descriptions`).
      for (const av of droitsLib().avertissements(m.droits, etat.acces.map((a) => a.niveau))) {
        notes.push(`<p class="col-note qe-avertissement" id="${esc(idAvertissement(m, av))}">`
          + `<strong>${av.actes.map((a) => esc(a.libelle)).join(", ")}</strong> — `
          + `${esc(av.texte)}</p>`);
      }
    }
    const an = etat.annuaire && etat.annuaire.annuaire;
    if (an && an.etat === "non_verifie") {
      // Le texte retenu par Hugo le 2026-09-17, sans « et ses comptes » : le propriétaire
      // ne se voit proposer aucun compte, il n'y a donc rien à ne pas pouvoir proposer.
      notes.push(`<p class="col-note qe-annuaire-note">L'annuaire ne répond pas : impossible de
      proposer ses groupes, ni de vérifier le nom que vous tapez. L'accès sera accordé tel
      quel, et marqué « non vérifié ».</p>`);
    } else if (an && an.etat === "sans_annuaire") {
      notes.push(`<p class="col-note">Aucun annuaire n'est configuré : un accès se déclare par
      un nom, que l'application ne peut pas vérifier. Un compte qui n'a pas encore ouvert
      l'application est signalé ; un nom de groupe ne peut pas l'être.</p>`);
    } else if (an && an.etat === "erreur") {
      notes.push(`<p class="col-note">La lecture de l'annuaire a échoué (${esc(an.motif)}) : la
      liste des groupes et les vérifications manquent. L'accès se déclare quand même par un
      nom.</p>`);
    }
    notes.push(noteAdmin(m.options.groupesAdmin));
    const corps = notes.filter(Boolean).join("");
    return corps ? `<div class="qe-notes-bloc">${corps}</div>` : "";
  }

  /* Vivant : monté, et sa section encore dans le document. Un hôte qui redessine sans
     démonter laisse des montages morts ; ils ne dessinent plus rien et ne retiennent rien. */
  function vivant(m) {
    return !!(m && m.monte && m.sec && m.sec.isConnected);
  }

  /* Redessine ce qui dépend des données, jamais la ligne de message : elle survit ainsi à un
     rechargement, refus compris — le 409 du dernier propriétaire reste à l'écran après que le
     tableau est revenu à ce que le serveur a gardé (COL-2). */
  function rendre(m) {
    if (!vivant(m)) return;
    const sec = m.sec;
    const garde = releveAjout(sec);
    sec.querySelector(".qe-tableau").innerHTML = tableauHtml(m);
    sec.querySelector(".qe-ajout").innerHTML = ajoutHtml(m, garde);
    sec.querySelector(".qe-notes").innerHTML = notesHtml(m);
  }

  /* La ligne de message du module, et elle seule. L'hôte est PRÉVENU à chaque écriture —
     y compris d'un message vide, qui est ce qu'un geste abouti écrit : c'est à lui de faire
     taire le reste de son écran, s'il tient à n'avoir qu'un message à la fois. */
  function dire(m, texte, erreur) {
    if (!m.sec) return;
    const l = m.sec.querySelector(".qe-msg");
    l.textContent = texte || "";
    // `erreur` vaut `true` pour un refus, « alerte » pour ce qui a RÉUSSI mais doit se lire :
    // un accès accordé à un nom que l'annuaire ne connaît pas (AUTH-12, décision 4).
    l.classList.toggle("erreur", erreur === true);
    l.classList.toggle("alerte", erreur === "alerte");
    if (typeof m.options.surMessage === "function") m.options.surMessage(l);
  }

  /* Les refus du serveur sont RENDUS, jamais avalés : un 409 qui nomme le dernier
     propriétaire, un 422 qui nomme les valeurs admises, un 403 qui dit qu'aucune identité ne
     parvient. */
  async function tenter(m, fn) {
    try { await fn(); dire(m, ""); return true; }
    catch (e) { dire(m, e.message || "Échec", true); return false; }
  }

  /* Le focus, rendu APRÈS le rechargement qui suit un geste — le contrôle actionné a été
     détruit par le rendu. Seulement à qui ne l'a pas repris entre-temps : l'aller-retour
     réseau laisse le temps de cliquer ailleurs. */
  function rendreFocus(m, cible) {
    if (!cible || !vivant(m)) return;
    const doc = m.sec.ownerDocument;
    if (doc.activeElement && doc.activeElement !== doc.body) return;
    const el = m.sec.querySelector(cible);
    if (el) el.focus();
  }

  async function lireAcces(m) {
    try {
      m.etat.acces = await env.apiGet(`/api/collections/${m.c.id}/acces`);
      m.etat.erreur = null;
    } catch (e) { m.etat.erreur = e.message || "Les accès n'ont pas pu être lus."; }
  }

  async function lireAnnuaire(m) {
    try { m.etat.annuaire = await env.apiGet(`/api/collections/${m.c.id}/annuaire`); }
    catch (e) {
      m.etat.annuaire = { annuaire: { etat: "erreur", motif: e.message || "échec" },
                          groupes: null, acces: [] };
    }
    return m.etat.annuaire;
  }

  /* À l'ouverture : le tableau dès que les accès sont là, les marques quand l'annuaire répond. */
  async function ouvrir(m) {
    m.etat.annuaire = null;
    // Une valeur ou une promesse ; une promesse REJETÉE vaut une description illisible, et
    // se dit comme telle — sans cela le panneau resterait sur « Chargement… » sans un mot.
    try { m.droits = (await m.options.droits) || null; } catch (e) { m.droits = null; }
    await lireAcces(m);
    rendre(m);
    await lireAnnuaire(m);
    rendre(m);
  }

  /* Après un geste : relire les accès dans les DEUX cas, et dessiner ce que le serveur a
     enregistré plutôt que ce qu'on a cliqué. */
  async function apres(m, cible) {
    if (!vivant(m)) return;            // démonté pendant le geste : plus rien à relire ici
    await lireAcces(m);
    rendre(m);
    rendreFocus(m, cible);
  }

  /* L'hôte n'est prévenu que d'un geste ABOUTI — ce qu'il affiche par ailleurs n'a pas bougé
     sur un refus —, et EN DERNIER : après le rendu, le focus et le message, pour que ce
     qu'il rafraîchit autour ne coure pas contre ce que le module est en train d'écrire. */
  function changement(m, abouti) {
    if (abouti && typeof m.options.surChangement === "function") m.options.surChangement();
  }

  function accesDe(m, el) {
    return (m.etat.acces || []).find((a) => a.genre === el.dataset.genre
      && a.principal === el.dataset.principal);
  }

  const routeAcces = (m) => `/api/collections/${m.c.id}/acces`;

  async function gesteCran(m, input) {
    const BDDroits = droitsLib();
    const a = accesDe(m, input);
    const niveau = a ? BDDroits.niveauApresGeste(m.droits, input.dataset.cran, input.checked) : null;
    if (!a || !niveau) { rendre(m); return; }
    const cible = `.qe-case[data-cran="${CSS.escape(input.dataset.cran)}"]${sel(a)}`;
    // Le niveau COURANT est passé : ce que la liste rend d'une case d'office n'est pas une
    // décision, et l'affirmer en changeant de cran l'accorderait (cf. `corpsAcces`).
    const ok = await tenter(m, () => env.apiSend("PUT", routeAcces(m),
      BDDroits.corpsAcces(m.droits, { genre: a.genre, principal: a.principal }, niveau,
                          valeurs(m, a), a.niveau)));
    await apres(m, cible);
    changement(m, ok);
  }

  async function gesteHorsRang(m, input) {
    const BDDroits = droitsLib();
    const a = accesDe(m, input);
    if (!a) { rendre(m); return; }
    const vals = { ...valeurs(m, a), [input.dataset.horsRangChamp]: input.checked };
    const cible = `.qe-case[data-hors-rang="${CSS.escape(input.dataset.horsRang)}"]${sel(a)}`;
    // Le niveau ne change pas ici, mais les AUTRES cases hors rang, elles, peuvent être
    // d'office : elles ne se stockent pas parce qu'on a coché celle d'à côté.
    const ok = await tenter(m, () => env.apiSend("PUT", routeAcces(m),
      BDDroits.corpsAcces(m.droits, { genre: a.genre, principal: a.principal }, a.niveau, vals,
                          a.niveau)));
    await apres(m, cible);
    changement(m, ok);
  }

  async function retirer(m, bouton) {
    const a = accesDe(m, bouton);
    if (!a) return;
    const ok = await tenter(m, () => env.apiSend("DELETE",
      `${routeAcces(m)}/${encodeURIComponent(a.genre)}/${encodeURIComponent(a.principal)}`));
    // La ligne disparaît avec son bouton : le focus va au titre de la partie, et non nulle
    // part. Sur un refus, la ligne reste, et le focus retrouve son bouton.
    await apres(m, ok ? ".qe-titre" : `.qe-retirer${sel(a)}`);
    changement(m, ok);
  }

  async function faireEntrer(m) {
    const BDDroits = droitsLib();
    const sec = m.sec, c = m.c;
    const choix = sec.querySelector(".qe-choix").value;
    let genre, principal;
    if (!choix) {
      dire(m, "Choisissez un groupe dans la liste, ou « Un compte, ou un groupe absent de "
              + "la liste… ».", true);
      return;
    }
    if (choix === "autre") {
      principal = sec.querySelector(".qe-nom").value.trim();
      genre = sec.querySelector(".qe-genre").value;
      if (!principal) { dire(m, "Tapez le nom exact du compte ou du groupe.", true); return; }
      if (!genre) {
        dire(m, `Dites si « ${principal} » est un compte ou un groupe : un groupe accordé `
             + "comme compte n'ouvrirait rien à personne.", true);
        return;
      }
    } else {
      genre = "groupe";
      principal = choix.slice("groupe:".length);
    }
    const nomme = genre === "groupe" ? "Le groupe" : "Le compte";
    // Le couple, et non le nom seul : un compte et un groupe de même nom sont deux accès.
    if ((m.etat.acces || []).some((a) => a.genre === genre && a.principal === principal)) {
      dire(m, `${nomme} ${principal} entre déjà dans « ${c.nom} » : ses actes se règlent `
           + "dans le tableau.", true);
      return;
    }
    const premier = m.droits.echelle[0];
    const ok = await tenter(m, () => env.apiSend("PUT", routeAcces(m),
      BDDroits.corpsAcces(m.droits, { genre, principal }, premier, {})));
    if (!ok) return;
    // Démonté pendant l'aller-retour — l'hôte a redessiné sa liste, par exemple : l'accès
    // est accordé, il n'y a plus de ligne d'ajout à vider ni de message à écrire. `demonter`
    // VIDE la cible, ce que le panneau d'avant l'extraction ne faisait pas : sans cette
    // garde, la ligne suivante lèverait sur une section vide (passe de revue, 2026-10-07).
    if (!vivant(m)) { changement(m, true); return; }
    // La ligne d'ajout repart à vide : le nom est entré, le garder inviterait à le renvoyer.
    const choixEl = sec.querySelector(".qe-choix");
    choixEl.value = "";
    delete choixEl.dataset.touche;
    sec.querySelector(".qe-nom").value = "";
    sec.querySelector(".qe-genre").value = "";
    await apres(m, ".qe-choix");
    const an = await lireAnnuaire(m);
    rendre(m);
    if (!vivant(m)) { changement(m, true); return; }
    const v = verification(m, genre, principal);
    if (v === "inconnu") {
      dire(m, `${nomme} ${principal} n'est pas dans l'annuaire : l'accès est accordé, en `
           + `${premier}, mais n'ouvrira rien tant que ce nom n'y existe pas.`, "alerte");
    } else if (v === "non_verifie" || (an && an.annuaire && an.annuaire.etat === "erreur")) {
      dire(m, `${nomme} ${principal} entre dans « ${c.nom} », en ${premier} — non vérifié : `
           + "l'annuaire ne répondait pas.", "alerte");
    } else {
      dire(m, `${nomme} ${principal} entre dans « ${c.nom} », en ${premier}. Cochez les autres `
           + "actes.");
    }
    changement(m, true);
  }

  /* LE MODULE INVESTIT LA CIBLE, il n'y loge pas une section de plus. La cible DEVIENT la
     partie « Qui entre » : elle reçoit la classe, l'identité de la collection et son nom
     accessible, et le module n'écrit que ce qu'elle contient. C'est à l'hôte de donner une
     <section> — nommée par son titre, elle est le repère que les lecteurs d'écran annoncent.
     Une enveloppe autour aurait suffi à faire tourner le code ; elle déplaçait le panneau
     d'un cran dans l'arbre, et le témoin de l'extraction l'a dit au premier essai. */
  function investir(m) {
    const sec = m.cible;
    sec.classList.add("qe");
    sec.dataset.qe = String(m.c.id);
    sec.setAttribute("aria-labelledby", `qe-titre-${m.sfx}`);
    // Le rang du titre est celui que l'hôte donne : sous un <h3>, la partie s'annonce <h4>.
    // Une valeur hors de 2 à 6 retombe sur le rang d'origine plutôt que d'écrire une balise
    // qui n'existe pas.
    const rang = [2, 3, 4, 5, 6].includes(m.options.niveauTitre) ? m.options.niveauTitre : 3;
    sec.innerHTML = `
      <h${rang} class="qe-titre" id="qe-titre-${m.sfx}" tabindex="-1">Qui entre</h${rang}>
      <div class="qe-tableau"><p class="col-note">Chargement…</p></div>
      <div class="qe-ajout"></div>
      <p class="col-msg muted small qe-msg" role="status" aria-live="polite"></p>
      <div class="qe-notes"></div>`;
    m.sec = sec;
  }

  /* Les gestes, délégués sur la SECTION du montage : ses parties naissent et meurent à
     chaque rendu, elle reste. Ils vivaient sur la liste de la Bibliothèque — un sélecteur de
     page, c'est-à-dire la première des cinq coutures. Retenus pour être RETIRÉS : la cible
     appartient à l'hôte, qui peut la remonter. */
  function brancher(m) {
    const sec = m.sec;
    const ecouter = (type, fn) => { sec.addEventListener(type, fn); m.ecouteurs.push([type, fn]); };
    ecouter("change", (ev) => {
      const t = ev.target;
      if (!t.matches) return;
      if (t.matches(".qe-case[data-cran]")) gesteCran(m, t);
      else if (t.matches(".qe-case[data-hors-rang]")) gesteHorsRang(m, t);
      else if (t.matches(".qe-choix")) {
        t.dataset.touche = "1";
        const libre = sec.querySelector(".qe-libre");
        libre.hidden = t.value !== "autre";
        if (!libre.hidden) libre.querySelector(".qe-nom").focus();
      }
    });
    ecouter("click", (ev) => {
      const b = ev.target.closest && ev.target.closest("button");
      if (!b || !sec.contains(b)) return;
      if (b.classList.contains("qe-retirer")) retirer(m, b);
      else if (b.classList.contains("qe-faire-entrer")) faireEntrer(m);
      else if (b.classList.contains("qe-ouvrir") && typeof m.options.surOuvrir === "function") {
        // L'hôte reçoit le couple tel que le serveur le nomme, et choisit sa fiche : le
        // module ne sait pas ce qu'est une fiche, ni s'il y en a une.
        m.options.surOuvrir({ genre: b.dataset.genre, principal: b.dataset.principal });
      }
    });
    ecouter("keydown", (ev) => {
      if (ev.key === "Enter" && ev.target.matches && ev.target.matches(".qe-nom")) {
        ev.preventDefault();
        faireEntrer(m);
      }
    });
    m.auSeuil = () => { if (vivant(m)) rendre(m); else demonter(m); };
    m.etroit.addEventListener("change", m.auSeuil);
  }

  /* Rend la cible telle qu'elle a été reçue : vidée, sans la classe ni les attributs posés
     en l'investissant, sans écouteur. Seulement si elle est encore à CE montage. */
  function demonter(m) {
    if (!m.monte) return;
    m.monte = false;
    if (m.etroit && m.auSeuil) m.etroit.removeEventListener("change", m.auSeuil);
    if (m.sfx != null) rendreSuffixe(m.sfx, m);
    if (m.sec) for (const [type, fn] of m.ecouteurs) m.sec.removeEventListener(type, fn);
    m.ecouteurs = [];
    if (OCCUPANTS.get(m.cible) === m) {
      OCCUPANTS.delete(m.cible);
      m.cible.innerHTML = "";
      if (m.sec) {
        m.cible.classList.remove("qe");
        delete m.cible.dataset.qe;
        m.cible.removeAttribute("aria-labelledby");
      }
    }
    m.sec = null;
  }

  function monter(cible, options) {
    // La cible est DANS le document : « vivant » se lit à cela, pour qu'un montage que son
    // hôte a redessiné par-dessus ne dessine plus et ne retienne aucun identifiant. Monté
    // hors du document, un panneau passerait pour mort dès sa naissance — il resterait sur
    // « Chargement… », et son suffixe serait repris par le suivant. Une erreur le dit tout
    // de suite, là où le silence ne le dirait jamais.
    if (!cible || !cible.isConnected) {
      throw new Error("BDQuiEntre.monter : la cible doit être dans le document.");
    }
    const o = options || {};
    const c = o.collection || {};
    const precedent = OCCUPANTS.get(cible);
    if (precedent) demonter(precedent);
    const m = { cible, options: o, c, droits: null, monte: true, sec: null, sfx: null,
                etroit: null, auSeuil: null, ecouteurs: [],
                preselection: o.preselection || null,
                etat: { acces: null, erreur: null, annuaire: null } };
    OCCUPANTS.set(cible, m);
    const poignee = {
      rafraichir: async () => {
        if (!vivant(m)) return;
        await lireAcces(m);
        rendre(m);
        await lireAnnuaire(m);
        rendre(m);
      },
      /* Le focus sur le titre de la partie, pour l'hôte qui y mène par une adresse. Rend
         `false` quand il n'y a rien à viser : à l'hôte de choisir un repli. */
      focaliser: () => {
        const t = vivant(m) && m.sec.querySelector(".qe-titre");
        if (!t) return false;
        t.scrollIntoView({ block: "start" });
        t.focus();
        return true;
      },
      demonter: () => demonter(m),
    };
    if (!c.administrable) {
      // LIRE et MODIFIER sont deux droits distincts, qu'une seule garde confondait (AUTH-4).
      // La liste des accès est une donnée sur des PERSONNES : le participant ne la voit pas,
      // mais il apprend qu'un administrateur lit sans y figurer.
      cible.innerHTML = `<p class="col-note">Seul un propriétaire de la collection voit et règle
        qui y entre.</p>${noteAdmin(o.groupesAdmin)}`;
      return poignee;
    }
    m.sfx = prendreSuffixe(c.id, m, vivant);
    investir(m);
    m.etroit = cible.ownerDocument.defaultView.matchMedia(SEUIL_ETROIT);
    brancher(m);
    ouvrir(m);
    return poignee;
  }

  return { monter, noteAdmin, SEUIL_ETROIT, _suffixes: { prendre: prendreSuffixe, rendre: rendreSuffixe } };
});
