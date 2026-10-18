/* Administration (UX-10) — le lieu des gestes qui portent sur l'INSTANCE.

   CINQ VUES adressables depuis COL-3 (2026-10-16) — À faire · Fonds · Projets · Comptes et
   groupes · Instance —, cf. « Les VUES » plus bas. Elles rangent les blocs sans en changer
   aucune garde.

   SIX blocs, et aucun n'est une affaire de Bibliothèque : la version servie dit quel
   commit tourne ici (INFRA-10), le référent de l'instance dit à qui s'adresser quand on
   n'a accès à rien (AUTH-12, étape 4), les projets disent quel étage coiffe les collections
   et qui y entre (COL-3), le fonds dit ce que l'instance détient et quelles suppressions
   on lui demande (COL-3, tranche 2), les comptes et groupes disent qui utilise l'instance
   et par quoi il entre (AUTH-12, qui remplace la vue des comptes d'AUTH-7), les moteurs
   disent si l'instance sait encore reconnaître quelque chose. Les moteurs et les accès vivaient dans
   `/corpus` par ACCRÉTION — c'était le seul écran administratif, et tout ce qui y
   ressemblait s'y est ajouté —, donc les atteindre depuis la Visionneuse demandait de
   quitter son travail.

   LES ACCÈS SONT REPARTIS le 2026-09-17 (AUTH-12, décision 2 (b)) : qui entre dans UNE
   collection se règle dans SA fiche, dans la Bibliothèque. Ici restait la vue TRANSVERSE
   — qui a accès à quoi, à travers toutes les collections —, et un lien y menait.

   ET LE PANNEAU EST MONTÉ ICI UNE SECONDE FOIS (UX-16) : dans la fiche d'une collection de
   « Comptes et groupes », l'administrateur RÈGLE qui entre, sur place. Ce n'est pas le
   troisième déménagement : la Bibliothèque garde le sien, à l'identique, pour le
   propriétaire qui part de son corpus. Un panneau va là où la question se pose, et un
   second public se sert par un second montage.

   MONTÉ, PAS RECOPIÉ. La règle du 2026-09-07 tient toujours — deux portes vers la même
   pièce se paient, l'une vieillit, et c'est celle qu'on ne regarde plus — et c'est
   précisément pourquoi le panneau n'est ÉCRIT qu'une fois, dans `static/lib/qui-entre.js` :
   ce fichier ne dessine rien de lui et n'appelle aucune de ses routes, un cliquet le
   vérifie (`tests/test_qui_entre_module.py`). Deux portes, une seule pièce, un seul plan.

   ET CE NE SONT PLUS DES MODALES. Une page est un lieu : les blocs sont là, lisibles
   ensemble, sans piège à focus ni Échap à gérer. `dialog.js` ne sert donc plus ici.

   LA GARDE RESTE SUR L'ACTE, JAMAIS SUR L'ÉCRAN QUI LE CONTIENT. C'est la condition posée
   par UX-10, et elle vient d'une erreur réelle : dans AUTH-4, le référent d'une collection
   — une simple ADRESSE — s'est retrouvé derrière la garde du PARTAGE parce qu'il vivait
   dans ce panneau-là, donc lisible du seul propriétaire. Ici, chaque bloc pose SA question :
   la version servie et les comptes et groupes n'apparaissent que si leur route répond (403
   aux non-administrateurs), et les moteurs sont ouverts à tous — regarder si l'OCR
   fonctionne n'est pas un pouvoir.
   La page, elle, ne garde rien.

   Et la garde d'un bloc RÉSERVÉ se pose au même endroit que celle d'un bloc ouvert : sur
   la route. Un `if` côté client qui lirait les groupes ferait deux sources à tenir
   d'accord — et celle qui se tromperait serait la muette, puisqu'un bloc masqué à tort
   ne lève aucune erreur et ne casse aucun test. */

/* --- Référent de l'instance (AUTH-12, étape 4) ------------------------------------
   Une ligne de LECTURE : le réglage vit dans l'environnement du serveur, et rien ici ne
   l'écrit (décision 6 (b), 2026-09-17).

   CE BLOC EST ÉCRIT POUR SES DEUX ÉTATS MUETS, et c'est ce qui décide de sa forme. Le
   référent s'affiche déjà — mais au seul bandeau de portée vide, donc à qui ne voit rien.
   Celui qui pourrait le corriger ne le voyait jamais. Le cas « tout va bien » se contente
   donc d'une ligne ; les deux autres portent la note du serveur, qui dit ce qu'ils coûtent
   et où les régler.

   L'ÉTAT VIENT DU SERVEUR (`etat`), il ne se déduit pas ici. Le JS saurait le faire —
   `referent` nul, puis `contact` nul — mais la règle serait alors écrite à deux endroits,
   et c'est celle de l'écran qui dériverait sans que rien ne tombe.

   LE CONTACT RESTE DU TEXTE, jamais un lien, et c'est délibéré. `theme.js` en fait un lien
   parce qu'une personne BLOQUÉE doit pouvoir cliquer, et il porte pour cela une règle de
   schéma sûr (`javascript:` refusé dans un href). La recopier ici mettrait une décision de
   sécurité en deux exemplaires ; ce bloc CONSTATE un réglage, il ne sert pas à écrire au
   référent. -------------------------------------------------------------------------- */
async function loadReferent() {
  const bloc = $("#referent-bloc");
  let d;
  // On DEMANDE, et un refus signifie « pas pour vous » — même patron que la version servie.
  try { d = await apiGet("/api/referent"); }
  catch (e) { bloc.hidden = true; return; }
  bloc.hidden = false;
  AF.referent = d.etat;
  afRendre();

  const corps = $("#referent-corps");
  const note = $("#referent-note");
  corps.className = "referent-corps referent-" + d.etat;
  if (d.etat === "absent") {
    corps.innerHTML = "<b>Personne n'est désigné.</b>";
  } else if (d.etat === "injoignable") {
    // Le pire des trois, et le seul qui TROMPE : le bandeau nomme quelqu'un sans dire
    // comment l'atteindre. Il crie donc plus fort que l'absence pure.
    corps.innerHTML = `<b>${esc(d.referent.nom)}</b> — <b>aucun contact déclaré.</b>`;
  } else {
    // Un contact sans nom reste JOIGNABLE : c'est une adresse, et l'adresse est ce qui
    // sert. On dit simplement que le nom manque, sans en faire une alerte.
    const qui = d.referent.nom
      ? `<b>${esc(d.referent.nom)}</b>`
      : `<span class="muted">Aucun nom déclaré</span>`;
    corps.innerHTML = `${qui} — ${esc(d.referent.contact)}`;
  }
  // La note vient du SERVEUR : lui seul sait pourquoi l'état est celui-là, et une raison
  // devinée ici enverrait régler la mauvaise variable. `textContent`, parce qu'elle
  // n'a pas à porter de balise.
  note.textContent = d.note || "";
  note.hidden = !d.note;
}

/* --- Version servie (INFRA-10) ---------------------------------------------------
   L'application ne connaît QU'UN BOUT de la comparaison : le commit qu'elle sert. L'autre
   — `origin/main` — vit dans le dépôt, et l'écran le dit au lieu de faire croire qu'il
   compare. Une phrase qui affirmerait « à jour » sans avoir vu la référence serait pire
   que pas de phrase : c'est le silence lu comme une approbation, le mode d'échec
   d'`ARCH-2`, et c'est exactement ce qui a laissé passer six commits de retard.
   -------------------------------------------------------------------------------- */
async function loadVersion() {
  const bloc = $("#version-bloc");
  let d;
  // On DEMANDE, et un refus signifie « pas pour vous » — même patron que les comptes.
  try { d = await apiGet("/api/version"); }
  catch (e) { bloc.hidden = true; return; }
  bloc.hidden = false;

  const corps = $("#version-corps");
  if (!d.commit) {
    // La `note` vient du SERVEUR : lui seul sait pourquoi il ne sait pas, et une raison
    // devinée ici enverrait chercher la mauvaise panne.
    corps.textContent = d.note || "Commit servi inconnu.";
    return;
  }
  corps.innerHTML =
    `Cette instance sert le commit <code>${esc(d.commit.slice(0, 7))}</code> ` +
    `<span class="muted">(${esc(d.commit)})</span>.<br>` +
    `À comparer avec <code>git log --oneline -1 origin/main</code> depuis le dépôt : ` +
    `l'application ne connaît que ce bout-là, et ne peut donc pas dire elle-même ` +
    `si elle est à jour.`;
}


/* ═══════════════════════════════════════════════════════════════════════════
   Comptes et groupes (AUTH-12, étape 2) — une liste et une fiche, côte à côte

   Remplace « 👤 Comptes vus par l'application » (AUTH-7). Ce que celle-ci montrait n'est
   pas perdu, il a changé de place : la nature d'un compte se déclare en tête de sa fiche,
   avec ce qu'elle change ; le VERDICT se lit dans « Départ », replié ; « identité changée »
   est une marque de la fiche, et un signal de « À regarder » pendant trente jours. Le
   regroupement des comptes par verdict, lui, disparaît — tranché par Hugo le 2026-09-17.

   CE QUE L'ÉCRAN NE FAIT PAS, et c'est le contrat avec `GET /api/comptes-et-groupes` : il
   ne réunit pas l'annuaire, le miroir et les accès, et ne calcule aucun signal. Le serveur
   rend tout cela fait, « À regarder » déjà ORDONNÉ. Ce qui reste ici est de l'affichage, et
   sa logique pure (tri, filtre, adresse, regroupement des signaux) vit dans
   `static/lib/comptes.js`, testée par tables de cas.

   IL NE MODIFIE QUE DEUX CHOSES : la nature d'un compte (décision 1 (A) d'AUTH-12), et qui
   entre dans une collection — par le module « Qui entre », MONTÉ dans la fiche de la
   collection (UX-16), qui lit et écrit ses propres routes. Tout ce qui change un compte ou
   un groupe se fait dans l'annuaire. La fiche d'une collection fait donc DEUX lectures :
   celle de la vue, pour son en-tête, et celle du panneau, pour ses accès. Ce n'est pas un
   doublon : passer les accès de la vue au panneau ferait vivre le contrat de `…/acces`
   dans deux écrans.

   CE QUE L'ON PEUT RÉGLER SE DEMANDE AU SERVEUR, collection par collection (`administrable`,
   dans `GET /api/collections`), et jamais parce que cette vue est réservée aux
   administrateurs : un panneau qui se croirait réglable parce que son contenant est gardé
   hériterait de la garde de son contenant — la leçon d'AUTH-4, celle que cette page existe
   pour fermer.

   L'AXE, LA SÉLECTION ET LE TRI VIVENT DANS L'ADRESSE, pour qu'on puisse envoyer une fiche
   et que « Retour » défasse le dernier saut. Le filtre n'y est pas : c'est une saisie en
   cours, pas un endroit.
   ═══════════════════════════════════════════════════════════════════════════ */
const CG = {
  donnees: null,
  droits: null,          // la description des droits en actes, ou null si illisible
  index: null,           // { comptes: Map login, groupes: Map nom, collections: Map id }
  axe: "comptes", tri: "alpha", sel: null,
  filtre: "",
  vueFiche: false,       // sous le seuil étroit, la fiche REMPLACE la liste
  msgNature: null,       // { login, texte, erreur } — survit au rechargement du geste
  // UX-16 — « Qui entre », monté dans la fiche d'une collection.
  reglables: null,       // Map id → la collection selon `GET /api/collections` ; null = illisible
  reglablesMotif: null,  // pourquoi elle est illisible, quand elle l'est
  groupesAdmin: [],      // `acces.groupes_admin` de `/api/moi`, pour la note d'AUTH-4
  quiEntre: null,        // { id, poignee } — le montage de la fiche ouverte, s'il y en a un
  preselection: null,    // { id, groupe } — « Ouvrir une collection à ce groupe… », une fois
};

/* Les deux natures d'un compte (AUTH-6), dans les mots de la maquette validée. La valeur
   envoyée au serveur ne change pas ; seul le libellé suit le lexique de la décision 7. */
const CG_NATURES = [["nominatif", "une personne"], ["collectif", "un login partagé"]];

/* Le seuil étroit, en `em` comme les autres de la feuille : il suit la police choisie. La
   même valeur que la règle `@media` de `style.css` — sinon le focus irait vers une fiche
   que la mise en page n'affiche pas. */
const CG_ETROIT = window.matchMedia("(max-width: 40em)");

/* Ce qui s'est passé, dit en entier — et non un mot entre parenthèses derrière « l'annuaire
   n'a pas répondu », qui supposait toujours qu'on lui avait demandé quelque chose.
   `non_configure` est le cas qui l'a montré : sans identifiant de service, rien ne part, et
   l'écran affichait « accès refusé » (revue du 2026-09-18). Chaque phrase RAPPORTE ce qui a
   eu lieu, aucune ne dit pourquoi. */
const CG_MOTIFS = {
  delai: "l'annuaire n'a pas répondu (délai dépassé)",
  refus: "l'annuaire a refusé la connexion",
  reponse_illisible: "l'annuaire a répondu quelque chose d'illisible",
  non_configure: "l'annuaire n'a pas été interrogé : aucun identifiant de service n'est configuré",
};

function cgPuce(texte, genre) {
  return `<span class="lf-puce cg-puce${genre ? " " + genre : ""}">${esc(texte)}</span>`;
}

/* Un lien qui ouvre un objet du bloc. Un BOUTON et non un <a> : il ne quitte pas la page,
   et `data-type`/`data-id` suffisent à la délégation d'événements. */
function cgLien(type, id, texte) {
  return `<button type="button" class="lf-lien cg-lien" data-type="${type}" `
    + `data-id="${esc(String(id))}">${esc(texte)}</button>`;
}

function cgLienAnnuaire(texte) {
  const href = BDComptes.lienAnnuaire(CG.donnees.annuaire.lien);
  if (!href) return "";
  return `<a class="lf-ext cg-ext" href="${esc(href)}" target="_blank" rel="noopener">${esc(texte)}`
    + `<span aria-hidden="true"> ↗</span><span class="sr-only"> (nouvel onglet)</span></a>`;
}

/* Ce qu'un accès permet, dit en ACTES (AUTH-12, étape 3), lus dans la description des
   droits servie par `GET /api/droits` : l'écran n'écrit ni acte ni niveau. Sans description
   lisible, le NIVEAU tel quel — la fiche ne se vide pas pour une description manquante. Les
   valeurs hors rang sont celles de l'accès, rangées sous le `champ` que la description
   nomme. */
function cgAccesLu(acces) {
  if (!CG.droits) return String(acces.niveau) + (acces.exporter ? " · exporter" : "");
  const valeurs = Object.fromEntries(CG.droits.hors_rang.map((h) => [h.champ, !!acces[h.champ]]));
  return BDDroits.actesLus(CG.droits, acces.niveau, valeurs);
}

/* Ce qu'on dit quand l'annuaire n'a rien pu apprendre sur un point précis. Deux phrases et
   non une : « non vérifié » en mono-poste ferait chercher une panne qui n'existe pas. « n'a
   pas été LU » et non « n'a pas répondu » : les quatre motifs de `non_verifie` n'ont pas tous
   vu partir une requête, et celui-ci ne les distingue pas — la ligne du haut le fait. */
function cgInconnu(quoi) {
  return CG.donnees.annuaire.etat === "non_verifie"
    ? `Non vérifié : l'annuaire n'a pas été lu, on ne connaît pas ${quoi}.`
    : `Aucun annuaire n'est configuré : l'application ne connaît pas ${quoi}.`;
}

/* --- Chargement ------------------------------------------------------------------ */

async function cgCharger(opts = {}) {
  const bloc = $("#cg-bloc");
  let d;
  const droits = apiGet("/api/droits").catch(() => null);
  try { d = await apiGet("/api/comptes-et-groupes"); }
  catch (e) {
    // Un 403 veut dire « pas pour vous » : la garde est celle du serveur, et le bloc se tait.
    // Toute AUTRE panne se dit : un administrateur devant un bloc qui disparaît sans un mot
    // chercherait un droit qu'il a déjà.
    if (e.statut === 403) { bloc.hidden = true; return; }
    bloc.hidden = false;
    const n = $("#cg-annuaire");
    n.textContent = `La liste des comptes n'a pas pu être lue : ${e.message}`;
    n.classList.add("erreur");
    return;
  }
  bloc.hidden = false;
  $("#cg-annuaire").classList.remove("erreur");
  // Ce qu'on peut RÉGLER, demandé une fois que la vue a répondu : à qui le bloc reste fermé,
  // la question ne part pas. Les deux lectures qui suivent ne font tomber ni l'une ni
  // l'autre la vue — une liste des collections illisible se DIT dans la fiche, à l'endroit
  // où elle manque, et le reste du bloc se lit quand même.
  const reglables = apiGet("/api/collections").then(
    (liste) => ({ liste }), (e) => ({ motif: e.message || "échec" }));
  const description = await droits;
  CG.droits = BDDroits.estValide(description) ? description : null;
  const lues = await reglables;
  CG.reglables = lues.liste ? new Map(lues.liste.map((c) => [c.id, c])) : null;
  CG.reglablesMotif = lues.liste ? null : lues.motif;
  const moi = await Promise.resolve(window.BDMoi).catch(() => null);
  CG.groupesAdmin = (moi && moi.acces && moi.acces.groupes_admin) || [];
  CG.donnees = d;
  CG.index = {
    comptes: new Map(d.comptes.map((c) => [c.login, c])),
    groupes: new Map(d.groupes.map((g) => [g.nom, g])),
    collections: new Map(d.collections.map((c) => [c.id, c])),
  };
  cgRendre(opts.garderFiche);
  afRendre();                      // « À faire » porte les accès à régler
  // Le focus rendu APRÈS le rechargement qui suit un geste : le contrôle actionné a été
  // détruit par le rendu, et le clavier perdrait sa place. Seulement à qui ne l'a pas repris.
  if (opts.focus && document.activeElement === document.body) {
    const el = document.querySelector(opts.focus);
    if (el) el.focus();
  }
}

function cgLireAdresse() {
  const a = BDComptes.lireAdresse(location.search);
  CG.axe = a.axe; CG.tri = a.tri; CG.sel = a.sel;
  CG.vueFiche = a.sel !== null;
}

/* `pousser` : un SAUT (choisir un objet, changer d'axe) entre dans l'historique, pour que
   « Retour » le défasse ; un changement de tri remplace l'entrée courante. */
function cgEcrireAdresse(pousser) {
  const s = BDComptes.ecrireAdresse({ axe: CG.axe, tri: CG.tri, sel: CG.sel }, location.search);
  const url = location.pathname + s + location.hash;
  if (url === location.pathname + location.search + location.hash) return;
  history[pousser ? "pushState" : "replaceState"](null, "", url);
}

/* --- Rendu ----------------------------------------------------------------------- */

/* `garderFiche` : après un geste de « Qui entre », tout ce qui DÉPEND des accès se redessine
   — la ligne de l'annuaire, « À regarder », la liste, l'en-tête de la fiche —, mais pas la
   fiche elle-même si elle montre encore la collection qu'on vient de régler : la redessiner
   remonterait le panneau, c'est-à-dire effacerait le message qu'il vient d'écrire et lui
   reprendrait le focus qu'il vient de rendre. */
function cgRendre(garderFiche) {
  cgRendreAnnuaire();
  cgRendreControles();
  cgRendreSignaux();
  cgRendreListe();
  if (garderFiche && cgRafraichirTeteCollection()) return;
  // Entre le geste et la relecture, on a pu ouvrir une AUTRE fiche : elle a été dessinée sur
  // les données d'avant, donc elle se redessine. Si le clavier y était, il retrouve le titre
  // plutôt que de retomber sur la page.
  const box = $("#cg-fiche");
  const dedans = garderFiche && box.contains(document.activeElement);
  cgRendreFiche();
  if (dedans) { const t = $("#cg-fiche-titre"); if (t) t.focus(); }
}

function cgRendreAnnuaire() {
  const a = CG.donnees.annuaire, n = $("#cg-annuaire");
  n.classList.toggle("non-verifie", a.etat === "non_verifie");
  if (a.etat === "lu") {
    const t = a.lu_le ? new Date(a.lu_le) : null;
    const heure = t && !Number.isNaN(t.getTime())
      ? ` à ${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`
      : "";
    // Une doublure qui s'annonce comme un annuaire serait le pire des mensonges de cet
    // écran : des comptes inventés, présentés comme ceux de l'instance.
    n.textContent = `Annuaire lu${heure}.` + (a.source === "doublure"
      ? " Doublure de test : ces comptes et ces groupes ne sont pas ceux d'un annuaire réel."
      : "");
  } else if (a.etat === "non_verifie") {
    const motif = CG_MOTIFS[a.motif] || a.motif;
    n.textContent = `Non vérifié : ${motif || "l'annuaire n'a pas répondu"}. `
      + "Ce qui suit est ce que l'application sait seule, et les signaux qui supposent "
      + "l'annuaire ne sont pas calculés.";
  } else {
    n.textContent = "Aucun annuaire n'est configuré : la liste montre les comptes déjà venus "
      + "et ceux qui ont un accès, et les groupes nommés dans un accès.";
  }
}

function cgRendreControles() {
  document.querySelectorAll("#cg [data-axe]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.axe === CG.axe)));
  document.querySelectorAll("#cg [data-tri]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.tri === CG.tri)));
  const lien = $("#cg-annuaire-lien");
  const href = BDComptes.lienAnnuaire(CG.donnees.annuaire.lien);
  // Créer se fait dans l'annuaire, pour un compte ou un groupe — pas pour une collection,
  // qui se crée dans la Bibliothèque.
  lien.hidden = !href || CG.axe === "collections";
  if (href) lien.href = href;
  $("#cg").classList.toggle("lf--fiche", CG.vueFiche && CG.sel !== null);
}

/* « À regarder » : l'ordre est celui du serveur. Redessiné au CHARGEMENT seulement, pas à
   chaque sélection — une ligne repliée qu'on vient de déplier ne se referme pas sous la main. */
function cgRendreSignaux() {
  const d = CG.donnees, liste = d.a_regarder;
  // À ZÉRO, l'alerte s'ÉTEINT : ni ⚠, ni ambre, ni cadre, et repliée. Le seul élément de la
  // page conçu pour attraper l'œil était allumé en permanence, y compris quand il
  // n'annonçait rien (relevé par Hugo le 2026-09-18). Un signal montré TOUJOURS apprend à ne
  // plus être lu : le jour où il y a vraiment un accès mort, il a la même apparence qu'un
  // mois de rien, et on l'a perdu en l'ayant toujours montré. Même règle que le bandeau de
  // portée vide (AUTH-2), qui nomme les quatre situations mais ne se déplie d'office que
  // pour la seule panne CERTAINE. Le COMPTE, lui, reste affiché dans les deux cas : « (0) »
  // n'est pas le problème, c'est le décor d'alerte autour de lui.
  //
  // L'ouverture ne se force qu'au PREMIER rendu et aux changements d'état : sans cela, un
  // repli fait à la main se rouvrirait à chaque rechargement de la vue.
  const bloc = $("#cg-regarder"), vide = !liste.length;
  if (bloc.dataset.rendu !== "1" || vide !== bloc.classList.contains("est-vide")) {
    bloc.open = !vide;
  }
  bloc.classList.toggle("est-vide", vide);
  bloc.dataset.rendu = "1";
  $("#cg-regarder-titre").textContent = `${vide ? "" : "⚠ "}À regarder (${liste.length})`;
  const noms = cgNomsSignaux();
  const ligne = (s) => {
    const c = BDComptes.cibleSignal(s), texte = BDComptes.texteSignal(s, noms);
    return `<li>${c ? cgLien(c.type, c.id, texte) : esc(texte)}</li>`;
  };
  const ouverts = new Set([...document.querySelectorAll("#cg-signaux details[open]")]
    .map((x) => x.dataset.signal));
  $("#cg-signaux").innerHTML = liste.length
    ? BDComptes.regrouperSignaux(liste).map((x) => (x.replie
      ? `<li><details class="cg-replie" data-signal="${esc(x.signal)}"`
        + `${ouverts.has(x.signal) ? " open" : ""}><summary>`
        + `${esc(BDComptes.texteGroupeSignaux(x.signal, x.signaux.length))}</summary>`
        + `<ul>${x.signaux.map(ligne).join("")}</ul></details></li>`
      : ligne(x))).join("")
    : `<li class="muted small">Rien à regarder.</li>`;
}

/* Les noms avec lesquels un signal se dit — partagés par « À regarder » et « À faire ». */
function cgNomsSignaux() {
  const d = CG.donnees;
  if (!d) return {};
  return {
    collections: Object.fromEntries(d.collections.map((c) => [c.id, c.nom])),
    comptes: Object.fromEntries(d.comptes.filter((c) => c.nom).map((c) => [c.login, c.nom])),
    demandes: FD.textes,          // COL-3 : ce que le bloc du fonds a lu des demandes
  };
}

const CG_NOMS_AXE = { comptes: ["compte", "comptes"], groupes: ["groupe", "groupes"],
                      collections: ["collection", "collections"] };

/* Ce qui sert l'ANNUAIRE plutôt que l'application — comptes de service, compte d'amorçage,
   groupes de rôle de LLDAP — se replie en fin de liste. Rendu et non caché : qu'un compte
   soit `lldap_admin` explique que « Mot de passe oublié ? » échoue pour lui. */
function cgAParte(o) {
  if (CG.axe === "comptes") return o.usage === "annuaire";
  if (CG.axe === "groupes") return o.role_annuaire === true;
  return false;
}

function cgRendreListe() {
  const d = CG.donnees;
  const brut = CG.axe === "comptes" ? d.comptes : CG.axe === "groupes" ? d.groupes
                                                                       : d.collections;
  const objets = BDComptes.trier(BDComptes.filtrer(brut, CG.axe, CG.filtre), CG.axe, CG.tri);
  // Le focus est-il sur une ligne ? Le rendu va la détruire : on la retrouvera.
  const actif = document.activeElement;
  const garde = actif && actif.closest && actif.closest("#cg-objets")
    && actif.dataset.id !== undefined ? actif.dataset.id : null;
  const type = BDComptes.TYPE_DE_L_AXE[CG.axe];

  const ligne = (o) => {
    const id = BDComptes.identifiant(o, CG.axe);
    const e = BDComptes.etatCourt(o, CG.axe, CG.tri, d.annuaire.etat);
    const courant = CG.sel !== null && String(CG.sel) === String(id);
    return `<li><button type="button" class="lf-objet cg-objet" data-type="${type}" `
      + `data-id="${esc(String(id))}"${courant ? ' aria-current="true"' : ""}>`
      + `<span class="lf-nom cg-nom">${esc(BDComptes.nomLu(o, CG.axe))}</span>`
      + `<span class="lf-etat cg-etat${e.alerte ? " alerte" : ""}">${esc(e.texte)}</span></button></li>`;
  };
  const [un, plusieurs] = CG_NOMS_AXE[CG.axe];
  const ordinaires = objets.filter((o) => !cgAParte(o));
  const aParte = objets.filter(cgAParte);
  let html = ordinaires.map(ligne).join("");
  if (aParte.length) {
    const titre = CG.axe === "comptes"
      ? `${aParte.length} ${aParte.length > 1 ? "comptes" : "compte"} de l'annuaire`
      : `${aParte.length} ${aParte.length > 1 ? "groupes" : "groupe"} de rôle de l'annuaire`;
    // Déplié quand on FILTRE : un objet trouvé ne doit pas rester caché dans un repli.
    html += `<li><details class="cg-a-parte"${CG.filtre.trim() ? " open" : ""}>`
      + `<summary>${esc(titre)}</summary><ul>${aParte.map(ligne).join("")}</ul></details></li>`;
  }
  if (!objets.length) {
    html = `<li class="lf-vide cg-vide muted small">${CG.filtre.trim()
      ? `Aucun ${un} ne correspond à « ${esc(CG.filtre.trim())} ».` : `Aucun ${un}.`}</li>`;
  }
  $("#cg-objets").innerHTML = html;
  $("#cg-objets-titre").textContent = `${plusieurs[0].toUpperCase()}${plusieurs.slice(1)} (${objets.length})`;
  if (garde !== null) {
    const b = document.querySelector(`#cg-objets .cg-objet[data-id="${CSS.escape(garde)}"]`);
    if (b) b.focus();
  }
}

function cgRendreFiche() {
  const box = $("#cg-fiche");
  // Le panneau « Qui entre » de la fiche d'avant meurt AVEC elle, et avant elle : démonté,
  // il ne parle plus. Laissé à lui-même, un geste encore en route chez lui viendrait écrire
  // son message — et faire taire, par `cgTaireSauf`, celui de la fiche qu'on lit maintenant.
  cgDemonterQuiEntre();
  // La présélection ne vaut que pour LE rendu qui suit le geste qui l'a posée.
  const preselection = CG.preselection;
  CG.preselection = null;
  // La fiche défile seule : une fiche NEUVE s'ouvre en haut, et non à la hauteur où l'on
  // avait laissé la précédente. Le même objet re-rendu (la nature posée recharge tout)
  // garde sa position — c'est là qu'on était en train de lire.
  const cle = `${CG.axe}:${CG.sel}`;
  if (box.dataset.cle !== cle) { box.scrollTop = 0; box.dataset.cle = cle; }
  const retour = `<button type="button" class="ghost small lf-retour cg-retour" data-cg-retour="1">← Liste</button>`;
  if (CG.sel === null) {
    const [un] = CG_NOMS_AXE[CG.axe];
    box.innerHTML = `<p class="muted lf-accueil cg-accueil">Choisissez un ${un} dans la liste pour ouvrir
      sa fiche.</p>`;
    return;
  }
  const o = CG.index[CG.axe].get(CG.sel);
  if (!o) {
    box.innerHTML = `${retour}<p class="col-note">« ${esc(String(CG.sel))} » n'est pas dans
      la liste : l'adresse le nomme, mais ni l'annuaire, ni les venues, ni les accès ne le
      connaissent.</p>`;
    return;
  }
  box.innerHTML = retour + (CG.axe === "comptes" ? cgFicheCompte(o)
    : CG.axe === "groupes" ? cgFicheGroupe(o) : cgFicheCollection(o));
  if (CG.axe === "collections") {
    cgMonterQuiEntre(box, o, preselection && preselection.id === o.id
      ? preselection.groupe : null);
  }
}

function cgFicheCompte(c) {
  const d = CG.donnees;
  const vu = BDComptes.dateCourte(c.derniere_vue);
  const puces = [];
  if (c.administrateur === true) puces.push(cgPuce("administrateur"));
  if (c.usage === "annuaire") puces.push(cgPuce("compte de l'annuaire"));
  if (c.dans_annuaire === false) puces.push(cgPuce("absent de l'annuaire", "rouge"));
  if (c.reprises) {
    const quand = BDComptes.dateCourte(c.derniere_reprise);
    puces.push(cgPuce(`identité changée ${c.reprises} ×${quand ? ` (dernière le ${quand})` : ""}`,
                      "rouge"));
  }

  // La nature (AUTH-6). Elle ne se pose que sur un compte VENU : le serveur n'en connaît pas
  // d'autre, et lui en fabriquer une inventerait un compte actif qui ne l'est pas.
  let nature;
  if (c.nature === null || c.nature === undefined) {
    nature = `<p class="muted small cg-nature">Nature : se déclare à sa première connexion.</p>`;
  } else {
    const msg = CG.msgNature && CG.msgNature.login === c.login ? CG.msgNature : null;
    nature = `<div class="cg-nature">
      <label for="cg-nature">Nature</label>
      <select id="cg-nature" data-login="${esc(c.login)}">${CG_NATURES.map(([v, l]) =>
        `<option value="${v}"${v === c.nature ? " selected" : ""}>${l}</option>`).join("")}</select>
      <p class="col-msg muted small${msg && msg.erreur ? " erreur" : ""}" id="cg-nature-msg"
         role="status" aria-live="polite">${msg ? esc(msg.texte) : ""}</p>
      <details class="cg-aide"><summary>Ce que change un login partagé</summary>
        <p>Un login partagé est utilisé par plusieurs personnes. L'accord
        inter-annotateurs cesse de le mesurer — il compte à part ce qu'il ne peut pas
        trancher —, les exports le nomment « collectif-N » au lieu de « annotateur-N », et
        Ctrl+Z n'y remonte que les cinq dernières minutes, faute de savoir qui a fait quoi.
        Aucun droit d'accès n'en dépend. L'application ne peut pas deviner qu'un login est
        partagé : il faut le déclarer.</p></details>
    </div>`;
  }

  let groupes;
  if (c.groupes === null || c.groupes === undefined) {
    groupes = `<p class="muted small">${esc(cgInconnu("ses groupes"))}</p>`;
  } else {
    groupes = `<div class="lf-pastilles cg-pastilles">${c.groupes.length
      ? c.groupes.map((g) => cgLien("groupe", g, g)).join("")
      : `<span class="muted small">Aucun groupe.</span>`}
      ${c.dans_annuaire === true ? cgLienAnnuaire("Modifier dans l'annuaire") : ""}</div>`;
  }

  // « par le projet » (COL-3, écran de la 3a) : l'entrée dans une collection de BASE, que le
  // serveur dérive de la place du compte — ou d'un de ses groupes — dans le projet.
  const parQui = (x) => {
    if (x.par === "projet") {
      return `par le projet « ${esc(x.par_projet || "")} »${x.groupe
        ? `, comme membre du groupe ${cgLien("groupe", x.groupe, x.groupe)}` : ""}`;
    }
    return x.par === "groupe" ? `par le groupe ${cgLien("groupe", x.groupe, x.groupe)}`
                              : "à son nom";
  };
  const lignes = c.collections.map((x) => `<li>${cgLien("collection", x.id, x.nom)}
    <span class="muted small">${esc(cgAccesLu(x))} — ${parQui(x)}</span></li>`);
  let collections = "";
  if (c.administrateur === true) {
    collections += `<p class="col-note col-note-admin">Administrateur de l'instance : lit et
      écrit toute collection, sans figurer dans les accès.</p>`;
  }
  if (lignes.length) {
    collections += `<ul class="lf-lignes cg-lignes">${lignes.join("")}</ul>`;
  } else if (c.collections_completes && c.administrateur !== true) {
    collections += `<p class="lf-explique cg-explique">Aucune collection ne lui est ouverte :
      l'application lui montre un corpus vide.</p>`;
  } else if (!c.collections_completes) {
    collections += `<p class="muted small">Aucun accès à son nom.</p>`;
  }
  // Ce que la vue ne sait pas, dit là où l'on s'en sert : c'est en lisant les collections
  // d'un compte qu'on conclurait à tort « il n'a accès à rien ».
  if (d.limite) collections += `<p class="col-note">${esc(d.limite)}</p>`;

  let depart = "";
  if (c.usage !== "annuaire") {
    const rien = c.verdict === "rien à orpheliner";
    const n = c.acces_explicites || 0;
    const conseq = BDComptes.consequenceSuppression(c);
    const annuaire = cgLienAnnuaire("l'annuaire") || "l'annuaire";
    const suite = c.dans_annuaire === false
      ? `<li>Il n'est déjà plus dans l'annuaire : ${esc(conseq)}.</li>`
      : `<li>Le retirer de ses groupes dans ${annuaire} : cela coupe les accès qu'il tient
           d'un groupe.</li>
         <li>Le supprimer dans ${annuaire} : ${esc(conseq)}.</li>`;
    depart = `<details class="cg-depart"><summary>Départ ${cgPuce(c.verdict, rien ? "ok" : "alerte")}</summary>
      <ol>
        <li>Retirer ses accès à son nom${n ? ` (${n})` : " — il n'en a aucun"}, dans
          « Qui entre » de chaque collection : sa fiche s'ouvre depuis « Collections »,
          ci-dessus.</li>
        ${c.entrees_projet ? `<li>Le retirer des projets dont il est
          (${c.entrees_projet}), dans « Qui y entre » de la fiche de chacun — vue
          « Projets ». Responsable seul d'un projet, nommez-en d'abord un autre : il est
          propriétaire de sa collection de base.</li>` : ""}
        ${suite}
      </ol></details>`;
  }

  return `<article class="lf-carte cg-carte" aria-labelledby="cg-fiche-titre">
    <div class="lf-tete cg-tete">
      <div>
        <h3 id="cg-fiche-titre" tabindex="-1">${esc(c.nom || c.login)}</h3>
        <p class="lf-sous cg-sous"><span class="cg-login">${esc(c.login)}</span>
          ${vu ? `<span>vu le ${esc(vu)}</span>`
               : cgPuce("aucune connexion", c.usage === "annuaire" ? "" : "alerte")}
          ${puces.join("")}</p>
      </div>
      ${nature}
    </div>
    <section class="lf-section cg-section"><h4>Groupes</h4>${groupes}</section>
    <section class="lf-section cg-section"><h4>Collections</h4>${collections}</section>
    ${depart}
  </article>`;
}

function cgFicheGroupe(g) {
  const puces = [];
  if (g.dans_annuaire === false) puces.push(cgPuce("absent de l'annuaire", "rouge"));
  if (g.administrateur === true) puces.push(cgPuce("groupe d'administration"));
  if (g.role_annuaire === true) puces.push(cgPuce("rôle de l'annuaire"));

  const ouvertes = g.collections.map((x) => `<li>${cgLien("collection", x.id, x.nom)}
    <span class="muted small">${esc(cgAccesLu(x))}${x.par_projet !== undefined
      ? ` — par le projet « ${esc(x.par_projet || "")} »` : ""}</span></li>`);
  let collections = g.administrateur === true
    ? `<p class="col-note col-note-admin">Ses membres lisent et écrivent toute collection,
        sans figurer dans les accès.</p>` : "";
  collections += ouvertes.length ? `<ul class="lf-lignes cg-lignes">${ouvertes.join("")}</ul>`
                                 : `<p class="muted small">Aucune.</p>`;
  // Arrivé avec l'étape 3 (AUTH-12), où la collection choisie s'ouvrait dans la Bibliothèque.
  // Depuis UX-16, c'est SA FICHE qui s'ouvre, ici, ce groupe déjà choisi dans la ligne
  // d'ajout de « Qui entre » (`cgOuvrirA`). Cette fiche-ci n'accorde toujours rien : le
  // geste se fait dans le panneau, et c'est lui qui pose la question du droit.
  const choix = CG.donnees.collections;
  if (choix.length) {
    collections += `<div class="cg-ouvrir">
      <label for="cg-ouvrir-a">Ouvrir une collection à ce groupe</label>
      <select id="cg-ouvrir-a">${BDComptes.trier(choix, "collections", "alpha").map((x) =>
        `<option value="${x.id}">${esc(x.nom)}</option>`).join("")}</select>
      <button type="button" class="ghost small" data-cg-ouvrir="${esc(g.nom)}">Régler qui
        entre…</button></div>`;
  }

  let membres, titreMembres = "Membres";
  if (g.dans_annuaire === false) {
    membres = `<p class="lf-explique cg-explique">Ce groupe n'est pas dans l'annuaire : aucun compte n'en
      est membre, et ses accès n'ouvrent rien à personne.</p>`;
  } else if (g.membres === null || g.membres === undefined) {
    membres = `<p class="muted small">${esc(cgInconnu("ses membres"))}</p>`;
  } else if (!g.membres.length) {
    membres = `<p class="muted small">Aucun membre.</p>`;
  } else {
    const comptes = g.membres.map((l) => CG.index.comptes.get(l) || { login: l, nom: null });
    const jamais = comptes.filter((c) => !c.derniere_vue && c.usage !== "annuaire").length;
    if (jamais) titreMembres += ` — ${jamais} jamais ${jamais > 1 ? "venus" : "venu"}`;
    membres = `<ul class="lf-lignes cg-lignes">${BDComptes.trier(comptes, "comptes", "alpha").map((c) => {
      const vu = BDComptes.dateCourte(c.derniere_vue);
      return `<li>${cgLien("compte", c.login, c.nom || c.login)}${vu
        ? `<span class="muted small">vu le ${esc(vu)}</span>`
        : cgPuce("aucune connexion", c.usage === "annuaire" ? "" : "alerte")}</li>`;
    }).join("")}</ul>`;
  }

  return `<article class="lf-carte cg-carte" aria-labelledby="cg-fiche-titre">
    <div class="lf-tete cg-tete">
      <div>
        <h3 id="cg-fiche-titre" tabindex="-1">${esc(g.nom)}</h3>
        <p class="lf-sous cg-sous">${g.nb_comptes !== null && g.nb_comptes !== undefined
          ? `<span>${g.nb_comptes} ${g.nb_comptes > 1 ? "comptes" : "compte"}</span>` : ""}
          ${puces.join("")}
          ${g.dans_annuaire === true ? cgLienAnnuaire("Défini dans l'annuaire") : ""}</p>
      </div>
    </div>
    <section class="lf-section cg-section"><h4>Collections ouvertes</h4>${collections}</section>
    <section class="lf-section cg-section"><h4>${esc(titreMembres)}</h4>${membres}</section>
  </article>`;
}

/* Ce que l'en-tête d'une collection dit sous son nom. À part, parce que c'est la seule
   partie de la fiche qui se redessine après un geste de « Qui entre » : « sans
   propriétaire » doit disparaître quand on vient d'en désigner un, sans remonter le panneau
   qui vient de le faire (cf. `cgRafraichirTeteCollection`). */
function cgSousCollection(c) {
  const puces = [];
  const diffusion = BDComptes.diffusionLue(c.statut_diffusion);
  if (diffusion) puces.push(cgPuce(diffusion));
  if (c.repli) puces.push(cgPuce("collection de repli"));
  if ((c.signaux || []).includes("sans_proprietaire")) puces.push(cgPuce("sans propriétaire", "rouge"));
  if ((c.signaux || []).includes("proprietaire_absent")) {
    puces.push(cgPuce("propriétaire absent de l'annuaire", "rouge"));
  }
  const modif = BDComptes.dateCourte(c.derniere_modification);
  return `<span>${c.nb_albums} ${c.nb_albums > 1 ? "albums" : "album"}</span>
          ${modif ? `<span>modifiée le ${esc(modif)}</span>` : ""}
          ${puces.join("")}`;
}

/* La fiche d'une collection : son en-tête, lu dans la vue, et UNE section vide que le module
   « Qui entre » investit (UX-16, décision A de Hugo, 2026-09-23). La liste en lecture et le
   renvoi « Régler qui entre » ont disparu : on règle ici. Le lien qui reste nomme ce qu'il
   mène VOIR, pas le geste — ce que la collection EST se règle dans la Bibliothèque, et y
   reste (décision B). */
function cgFicheCollection(c) {
  return `<article class="lf-carte cg-carte" aria-labelledby="cg-fiche-titre">
    <div class="lf-tete cg-tete">
      <div>
        <h3 id="cg-fiche-titre" tabindex="-1">${esc(c.nom)}</h3>
        <p class="lf-sous cg-sous">${cgSousCollection(c)}</p>
      </div>
    </div>
    <section class="lf-section cg-section" data-qui-entre></section>
    <p class="cg-ailleurs"><a class="cg-decrire" href="/corpus?collection=${c.id}&amp;onglet=description">Décrire
      dans la Bibliothèque<span aria-hidden="true"> ↗</span></a></p>
    <p class="col-note">Ce que la collection est — sa description, sa diffusion, son
      référent, ses exports — se règle dans sa fiche, dans la Bibliothèque.</p>
  </article>`;
}

/* ── « Qui entre », monté dans la fiche d'une collection (UX-16) ─────────────────────
   Le SECOND montage du module : la Bibliothèque le monte dans chaque collection dépliée,
   pour le propriétaire qui part de son corpus ; ici, l'administrateur part d'une personne ou
   d'un groupe et règle sur place. Ce que cet hôte garde, et ce sont des affaires d'ÉCRAN :
   la question « puis-je régler celle-ci ? », qu'il pose au serveur ; la règle « un seul
   message à la fois » de son bloc ; ce qu'il redessine autour après un geste ; et où mènent
   les noms. Il n'écrit rien du panneau et n'appelle aucune de ses routes. */

function cgDemonterQuiEntre() {
  if (CG.quiEntre) CG.quiEntre.poignee.demonter();
  CG.quiEntre = null;
}

/* UN message à la fois dans le bloc — une règle de CET écran, que le module ne connaît pas :
   il écrit sa ligne et prévient. Le message du dernier geste fait taire les autres lignes du
   bloc, et celui que la fiche d'un compte GARDE en mémoire pour survivre à son rechargement
   (`CG.msgNature`) : sans cela, un refus de la nature reviendrait à l'écran dès qu'on
   retrouve sa fiche par l'historique, après un geste qui n'a rien à voir avec lui. Rien
   n'est touché hors du bloc :
   la fiche d'un projet, à côté, a sa propre règle (`pjTaireSauf`). */
function cgTaireSauf(el) {
  document.querySelectorAll("#cg-bloc .col-msg").forEach((l) => {
    if (l === el) return;
    l.textContent = "";
    l.classList.remove("erreur", "alerte");
  });
  CG.msgNature = null;
}

/* Monte le panneau dans la section que `cgFicheCollection` vient de dessiner.

   LA GARDE EST CELLE DE L'ACTE. `administrable` vient de `GET /api/collections`, collection
   par collection ; le module la reçoit et dit lui-même ce qu'il faut lire quand elle manque.
   Une collection que cette liste ne nomme pas n'est pas réglable d'ici — on ne la lit pas.
   Et une liste ILLISIBLE n'est pas une liste vide : la fiche dit qu'elle ne sait pas, au
   lieu d'annoncer « seul un propriétaire… » à qui l'est peut-être. */
function cgMonterQuiEntre(box, c, groupe) {
  const cible = box.querySelector("[data-qui-entre]");
  if (!cible) return;
  if (CG.reglables === null) {
    cible.innerHTML = `<h4>Qui entre</h4>
      <p class="col-note">La liste des collections n'a pas pu être lue
      (${esc(CG.reglablesMotif || "échec")}) : impossible de savoir si vous réglez qui entre
      dans celle-ci. Rechargez la page pour le redemander.</p>`;
    return;
  }
  const lue = CG.reglables.get(c.id);
  CG.quiEntre = { id: c.id, poignee: BDQuiEntre.monter(cible, {
    collection: { id: c.id, nom: c.nom, administrable: !!(lue && lue.administrable) },
    droits: CG.droits,
    groupesAdmin: CG.groupesAdmin,
    preselection: groupe,
    niveauTitre: 4,                 // sous le <h3> de la fiche, comme ses autres sections
    // La fiche partage la largeur du bloc avec la liste : le panneau n'y dispose pas de la
    // page, et le seuil de FENÊTRE du module lui laissait un tableau à moitié hors champ
    // entre 768 et 1 110 px. Il passe donc en cartes dès que le tableau ne tient plus dans
    // SA section — une mesure que le module fait lui-même, sans qu'aucune largeur ne soit
    // écrite ici.
    ajusterALaPlace: true,
    surMessage: cgTaireSauf,
    surChangement: cgApresAcces,
    surOuvrir: cgOuvrirDepuisAcces,
  }) };
}

/* Après un geste que le serveur a accepté : la vue DÉPEND des accès — « sans propriétaire »,
   « À regarder », l'état court des lignes — et se relit. La fiche, elle, reste (cf.
   `cgRendre`). */
async function cgApresAcces() {
  await cgCharger({ garderFiche: true });
}

/* Redessine la seule ligne de l'en-tête qui dépend des accès. Rend `false` quand la fiche
   n'est plus celle de la collection montée — on a changé de fiche pendant la relecture, ou
   la collection a disparu de la vue : à l'appelant de redessiner. Le titre n'est pas
   touché : il peut porter le focus. */
function cgRafraichirTeteCollection() {
  if (CG.axe !== "collections" || !CG.quiEntre || CG.quiEntre.id !== CG.sel) return false;
  const c = CG.index.collections.get(CG.sel);
  const sous = document.querySelector("#cg-fiche .cg-sous");
  if (!c || !sous) return false;
  sous.innerHTML = cgSousCollection(c);
  return true;
}

/* Un nom du panneau mène à SA fiche, comme la liste en lecture le faisait. Le module rend
   le couple tel que le serveur le nomme ; c'est ici qu'il devient un axe. */
function cgOuvrirDepuisAcces(a) {
  cgAller(a.genre === "groupe" ? "groupe" : "compte", a.principal, false);
}

/* --- Gestes ---------------------------------------------------------------------- */

/* Ouvrir un objet : depuis la liste, un signal, ou un lien d'une fiche. Le filtre s'efface
   quand l'axe change — sinon l'objet visé pourrait ne pas figurer dans la liste qui s'ouvre. */
function cgAller(type, id, depuisListe) {
  const axe = BDComptes.AXE_DU_TYPE[type];
  if (!axe) return;
  if (axe !== CG.axe) {
    CG.axe = axe;
    CG.filtre = "";
    $("#cg-filtre").value = "";
  }
  const sel = axe === "collections" ? Number(id) : id;
  if (!CG.msgNature || CG.msgNature.login !== sel) CG.msgNature = null;
  CG.sel = sel;
  CG.vueFiche = true;
  cgEcrireAdresse(true);
  cgRendreControles();
  cgRendreListe();
  cgRendreFiche();
  // Le focus suit la FICHE quand la liste disparaît (seuil étroit) ou quand on vient d'un
  // lien ailleurs que la liste ; au large, un choix dans la liste y laisse le clavier, pour
  // parcourir la suivante sans revenir.
  if (!depuisListe || CG_ETROIT.matches) {
    const t = $("#cg-fiche-titre");
    if (t) t.focus();
  }
}

function cgChangerAxe(axe) {
  if (axe === CG.axe) return;
  CG.axe = axe;
  CG.sel = null;
  CG.vueFiche = false;
  CG.filtre = "";
  CG.msgNature = null;
  $("#cg-filtre").value = "";
  cgEcrireAdresse(true);
  cgRendreControles();
  cgRendreListe();
  cgRendreFiche();
}

async function cgPoserNature(select) {
  const login = select.dataset.login;
  try {
    await apiSend("PATCH", `/api/comptes/${encodeURIComponent(login)}/nature`,
                  { nature: select.value });
    CG.msgNature = { login, texte: "Nature enregistrée.", erreur: false };
  } catch (e) {
    CG.msgNature = { login, texte: e.message || "Échec", erreur: true };
  }
  // On recharge dans les DEUX cas, comme la vue qu'on remplace : en cas de refus, le
  // sélecteur afficherait une nature que le serveur n'a pas enregistrée. Ici le mensonge
  // coûterait plus qu'ailleurs — c'est cette valeur qui décide si une mesure d'accord a le
  // droit de répondre.
  await cgCharger({ focus: "#cg-nature" });
}

/* « Ouvrir une collection à ce groupe… » : la fiche de la collection choisie, ICI, ce groupe
   déjà choisi dans la ligne d'ajout de « Qui entre ». Le geste menait à la Bibliothèque
   (`/corpus?collection=…&groupe=…`) tant que le panneau n'y vivait que là.

   La présélection n'entre PAS dans l'adresse : le paramètre `groupe` de cette page désigne
   déjà une fiche (`?axe=groupes&groupe=…`), et le réemployer ferait dire deux choses au même
   mot. Elle vaut donc pour ce geste et pour lui seul — recharger, ou revenir par
   « Retour », ouvre la fiche sans elle.

   Le focus va au titre de « Qui entre », comme il y allait dans la Bibliothèque ; quand il
   n'y a pas de panneau à viser, il reste sur le titre de la fiche, où `cgAller` l'a mis. */
function cgOuvrirA(groupe) {
  const id = Number($("#cg-ouvrir-a").value);
  CG.preselection = { id, groupe };
  cgAller("collection", id, false);
  if (CG.quiEntre && CG.quiEntre.id === id) CG.quiEntre.poignee.focaliser();
}

function cgInstaller() {
  const racine = $("#cg");
  racine.addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (!b || !racine.contains(b)) return;
    if (b.dataset.axe) { cgChangerAxe(b.dataset.axe); return; }
    if (b.dataset.tri) {
      if (b.dataset.tri === CG.tri) return;
      CG.tri = b.dataset.tri;
      cgEcrireAdresse(false);
      cgRendreControles();
      cgRendreListe();
      return;
    }
    if (b.dataset.cgRetour) {
      CG.vueFiche = false;
      cgRendreControles();
      const courant = document.querySelector('#cg-objets .cg-objet[aria-current="true"]');
      (courant || $("#cg-filtre")).focus();
      return;
    }
    if (b.dataset.cgOuvrir !== undefined) { cgOuvrirA(b.dataset.cgOuvrir); return; }
    // COL-3 — une demande mène à « À faire », où l'on y répond ; jamais à un axe.
    if (b.dataset.type === "demande") { afAllerDemande(Number(b.dataset.id)); return; }
    if (b.dataset.type && b.dataset.id !== undefined) {
      cgAller(b.dataset.type, b.dataset.id, b.classList.contains("cg-objet"));
    }
  });
  $("#cg-filtre").addEventListener("input", (ev) => {
    CG.filtre = ev.target.value;
    if (CG.donnees) cgRendreListe();
  });
  racine.addEventListener("change", (ev) => {
    if (ev.target.id === "cg-nature") cgPoserNature(ev.target);
  });
  // La liste se parcourt aux FLÈCHES, en plus de Tab : trois cents comptes à la tabulation
  // ne se parcourent pas. Seules les lignes visibles comptent — un repli fermé ne vole pas
  // le focus. Par l'état du repli et non par `offsetParent` : Chromium ne rend plus le
  // contenu d'un <details> fermé en `display: none`, et `offsetParent` y reste renseigné
  // (mesuré : « Fin » atterrissait dans le repli fermé).
  $("#cg-objets").addEventListener("keydown", (ev) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(ev.key)) return;
    const lignes = [...document.querySelectorAll("#cg-objets .cg-objet")]
      .filter((x) => !x.closest("details:not([open])"));
    const i = lignes.indexOf(document.activeElement);
    if (i < 0 || !lignes.length) return;
    ev.preventDefault();
    const j = ev.key === "Home" ? 0 : ev.key === "End" ? lignes.length - 1
      : Math.max(0, Math.min(lignes.length - 1, i + (ev.key === "ArrowDown" ? 1 : -1)));
    lignes[j].focus();
  });
  window.addEventListener("popstate", () => {
    if (!CG.donnees) return;
    const avant = CG.axe;
    cgLireAdresse();
    if (CG.axe !== avant) { CG.filtre = ""; $("#cg-filtre").value = ""; }
    cgRendreControles();
    cgRendreListe();
    cgRendreFiche();
  });
}

/* ═══════════════════════════════════════════════════════════════════════════
   Projets (COL-3, tranche 1) — une liste et une fiche, pour qui en règle au moins un

   Un PROJET est l'étage au-dessus des collections. Ce bloc dit lesquels on règle, et pour
   chacun : pourquoi il existe, qui y entre, quelles collections en sont. Il est à lui — sa
   section, ses fonctions `pj…`, son état —, et ne partage rien avec « Comptes et groupes »,
   qui est réservé aux administrateurs par sa route : un responsable de projet doit voir SA
   fiche, et un bloc logé dans l'autre aurait hérité de sa garde.

   DEUX POUVOIRS, DEUX QUESTIONS, et aucune n'est posée par l'écran. RÉGLER qui entre dans un
   projet : le serveur le dit projet par projet (`gerable`, dans `GET /api/projets`) — son
   responsable, et l'administrateur qui passe outre. DÉCIDER quels projets existent — créer,
   renommer, décrire et justifier, supprimer : la portée totale, que `GET /api/moi` publie (`acces.total`), donc
   l'administrateur et le mono-poste. L'écran lit ces deux réponses ; s'il se trompait, le
   serveur refuserait le geste en le nommant.

   CE QUE LE BLOC NE MONTRE PAS. Les projets qu'on ne règle pas : y être simple membre ne
   donne rien à faire ici, et la bande du haut les nomme déjà. La justification d'un projet à
   qui ne le gère pas : le serveur ne la lui rend pas. Les collections qu'on ne lit pas : un
   responsable ne voit de son projet que celles où il entre déjà.

   QUI ENTRE est un module monté dans la fiche (`static/lib/membres-projet.js`) : il lit et
   écrit SES routes, et ce fichier n'en appelle aucune — un cliquet le vérifie
   (`tests/test_membres_projet_module.py`).

   UNE LISTE ET UNE FICHE, le gabarit `lf-` du fonds (COL-3, l'Administration à l'échelle) :
   une vingtaine de projets ne se règlent pas dans une liste plate. La liste se filtre par
   NOM, et chaque ligne dit son nombre de collections et ce qui attend — « sans
   responsable » (`sans_responsable`, rendu à qui gère ; jamais pour le projet de repli, que
   la migration a fait naître sans responsable et qu'une alerte permanente n'aiderait pas),
   « suppression demandée ». « + Nouveau projet » ouvre son formulaire DANS la fiche, comme
   « Importer au fonds ». Sous 40em, une colonne à la fois, avec « ← Liste ».

   LA FICHE OUVERTE VIT DANS L'ADRESSE (`?vue=projets&projet=…`), comme celle du fonds, pour
   qu'on puisse l'envoyer ; le filtre n'y est pas. Sans projet nommé, la fiche du premier
   s'ouvre, comme avant — une adresse qui nomme un projet qu'on ne règle pas le dit, sans
   dire s'il existe.
   ═══════════════════════════════════════════════════════════════════════════ */
const PJ = {
  projets: [],           // ceux qu'on RÈGLE, dans l'ordre du serveur
  collections: [],       // celles qu'on lit, pour nommer celles de chaque projet
  decide: false,         // créer, renommer, supprimer
  groupesAdmin: [],
  lu: false,             // la liste a été lue au moins une fois
  filtre: "",
  sel: null,             // l'identifiant du projet dont la fiche est ouverte
  nomme: false,          // `sel` vient de l'adresse ou d'un choix, pas du repli sur le premier
  creer: false,          // la fiche montre le formulaire « Nouveau projet »
  vueFiche: false,       // sous le seuil étroit, la fiche REMPLACE la liste
  demanderOuvert: null,  // le projet dont le motif de « Demander sa suppression… » est ouvert
  membres: null,         // la poignée du module monté dans la fiche
  position: undefined,   // la position choisie dans la fiche, pas encore appliquée
  fonds: null,           // { projet, demandes, gardees, erreur } — « Au fonds », lu par fiche
  rendreOuvert: null,    // la copie gardée dont « Demander à la rendre… » est ouvert
  details: new Set(),    // les demandes d'entrée dépliées (document par document)
};

/* UN message à la fois dans le bloc : celui de la création, celui d'un geste de la fiche,
   celui du module. Une règle de CET écran — le module écrit sa ligne et prévient, il
   n'efface rien.

   Chaque geste de « Ce projet » a SA ligne, posée contre son contrôle (`pjLigneDeGeste`) :
   une ligne unique en pied de section se lisait sous « Supprimer le projet » et sa note,
   quatre lignes plus bas que le bouton qu'on venait d'actionner. Elles portent toutes
   `.col-msg`, donc cette règle les tient ensemble : écrire dans l'une fait taire les autres. */
function pjTaireSauf(el) {
  document.querySelectorAll("#projets-bloc .col-msg").forEach((l) => {
    if (l === el) return;
    l.textContent = "";
    l.classList.remove("erreur", "alerte");
  });
}

function pjMsg(el, texte, erreur) {
  pjTaireSauf(el);
  el.textContent = texte || "";
  el.classList.toggle("erreur", !!erreur);
}

/* La ligne de message d'UN geste de la fiche. Elle est rendue avec la fiche, vide, et non
   posée au moment d'y écrire : un refus ne redessine pas la fiche, et une zone d'annonce
   (`role="status"`) dit ce qui CHANGE en elle — elle doit donc déjà être là. */
function pjLigneDeGeste(geste, balise) {
  return `<${balise} id="pj-${geste}-msg" class="col-msg pj-geste-msg muted small" `
    + `role="status" aria-live="polite"></${balise}>`;
}

function pjPluriel(n, mot) { return `${n} ${mot}${n > 1 ? "s" : ""}`; }

/* Prévient la bande du haut que la LISTE des projets a changé : un projet créé, renommé ou
   supprimé ici se lit là-haut sans attendre un rechargement. */
function pjPrevenirLaBande() {
  document.dispatchEvent(new CustomEvent("bd:projets-maj"));
}

/* Lit les projets et les collections. Rend `false` si la liste n'a pas pu être lue — et le
   DIT : un bloc qui disparaîtrait sans un mot ferait chercher un droit qu'on a déjà. */
async function pjLire() {
  let projets;
  try { projets = await apiGet("/api/projets"); }
  catch (e) {
    $("#projets-ferme").hidden = false;
    $("#projets-bloc").hidden = true;
    $("#projets-ferme-texte").textContent =
      `La liste des projets n'a pas pu être lue : ${e.message}`;
    return false;
  }
  const moi = await Promise.resolve(window.BDMoi).catch(() => null);
  PJ.decide = !!(moi && moi.acces && moi.acces.total);
  PJ.groupesAdmin = (moi && moi.acces && moi.acces.groupes_admin) || [];
  PJ.projets = projets.filter((p) => p.gerable);
  // Les collections ne servent qu'à NOMMER celles de chaque projet : sans elles, la fiche le
  // dit, et rien d'autre n'en dépend.
  try { PJ.collections = await apiGet("/api/collections"); }
  catch (e) { PJ.collections = null; }
  pjDireAuxAutres(projets);
  return true;
}

/* À qui ne règle aucun projet : ce que la page ne lui montre pas, et pourquoi. Rien du tout
   à qui n'en voit aucun — une portée vide a son propre bandeau, qui parle d'accès. */
function pjDireAuxAutres(projets) {
  const regle = PJ.decide || PJ.projets.length > 0;
  $("#projets-bloc").hidden = !regle;
  $("#projets-ferme").hidden = regle || !projets.length;
  if (regle || !projets.length) return;
  const miens = projets.filter((p) => p.mon_role).map((p) => `« ${p.nom} »`);
  const suite = !miens.length
    ? "Vous n'en réglez aucun."
    : miens.length === 1
      ? `Vous êtes membre du projet ${miens[0]} : vous n'y réglez rien.`
      : `Vous êtes membre des projets ${miens.slice(0, -1).join(", ")} et `
        + `${miens[miens.length - 1]} : vous n'y réglez rien.`;
  $("#projets-ferme-texte").textContent =
    `Les projets se règlent par leur responsable. ${suite}`;
}

async function pjCharger() {
  const lu = await pjLire();
  vueMajLiens();
  if (!lu) return;
  PJ.lu = true;
  $("#pj-creer-ouvrir").hidden = !PJ.decide;
  pjRendre();
}

function pjProjet() {
  return PJ.projets.find((p) => p.id === PJ.sel) || null;
}

function pjRendre() {
  // La fiche ouverte reste ouverte si son projet est encore là ; sinon la première — sauf si
  // l'adresse en nommait un autre : la fiche dit alors qu'on ne le règle pas.
  if (!pjProjet() && !PJ.nomme) PJ.sel = PJ.projets.length ? PJ.projets[0].id : null;
  pjRendreListe();
  pjRendreFiche();
  pjRendreDisposition();
}

/* Sous le seuil étroit, la fiche remplace la liste dès qu'on en a choisi une. */
function pjRendreDisposition() {
  $("#pj").classList.toggle("lf--fiche", PJ.vueFiche && (PJ.sel !== null || PJ.creer));
}

/* Ce qui attend sur un projet, en un mot, ou rien. « Sans responsable » ne se dit pas du
   projet de repli : la migration l'a fait naître ainsi, et une alerte qui ne s'éteint
   jamais apprend à ne plus être lue. */
function pjAlerte(p) {
  if (p.demande_suppression) return "suppression demandée";
  if (p.sans_responsable && !p.repli) return "sans responsable";
  return "";
}

function pjFiltres() {
  const f = BDComptes.normaliser(PJ.filtre.trim());
  return f ? PJ.projets.filter((p) => BDComptes.normaliser(p.nom).includes(f)) : PJ.projets;
}

function pjRendreListe() {
  const l = pjFiltres();
  // Redessinée après un geste ailleurs (le module, un renommage) : une ligne qui avait le
  // focus le retrouve, au lieu de le rendre à la page.
  const actif = document.activeElement;
  const garde = actif && actif.closest && actif.closest("#pj-objets") && actif.dataset.pj
    ? actif.dataset.pj : null;
  $("#pj-liste-compte").textContent = l.length === PJ.projets.length
    ? pjPluriel(l.length, "projet") : `${l.length} sur ${PJ.projets.length}`;
  $("#pj-objets").innerHTML = l.length
    ? l.map((p) => {
      const alerte = pjAlerte(p);
      return `<li><button type="button" class="lf-objet pj-objet" data-pj="${p.id}"`
        + `${p.id === PJ.sel && !PJ.creer ? ' aria-current="true"' : ""}>`
        + `<span class="lf-nom pj-nom">${esc(p.nom)}</span>`
        + `<span class="lf-etat pj-etat">${esc(pjPluriel(p.nb_collections, "collection"))}</span>`
        + (alerte ? `<span class="lf-detail pj-alerte">⚠ ${esc(alerte)}</span>` : "")
        + `</button></li>`;
    }).join("")
    : `<li class="lf-vide muted small">${PJ.projets.length
      ? "Aucun projet ne répond à ce filtre." : "Aucun projet."}</li>`;
  if (garde !== null) {
    const b = document.querySelector(`#pj-objets [data-pj="${CSS.escape(garde)}"]`);
    if (b) b.focus();
  }
}

/* Les collections d'un projet QU'ON LIT : la liste vient de `GET /api/collections`, qui ne
   rend que celles-là. Chaque nom mène à la Bibliothèque, où l'adresse choisit le projet. */
function pjCollections(p) {
  if (PJ.collections === null) {
    return `<p class="muted small">Les collections n'ont pas pu être lues.</p>`;
  }
  // La base en tête, marquée : c'est elle que règle « Ce que la base ouvre aux membres ».
  const siennes = PJ.collections.filter((c) => c.projet_id === p.id)
    .sort((a, b) => (b.base ? 1 : 0) - (a.base ? 1 : 0));
  const liens = siennes.map((c) =>
    `<li><a href="/corpus?collection=${c.id}">${esc(c.nom)}</a>${c.base
      ? ` <span class="pj-puce">base</span>` : ""}</li>`).join("");
  return (siennes.length ? `<ul class="pj-collections">${liens}</ul>`
                         : `<p class="muted small">Aucune.</p>`)
    + `<p class="col-note">${PJ.decide ? "" : "Seules les collections que vous lisez sont "
      + "nommées ici. "}Une collection se crée dans la Bibliothèque, une fois ce projet
      choisi en haut de la page.</p>`;
}

/* Un texte libre tel qu'on le COMPARE : sans ses blancs de bord, et avec les fins de ligne
   d'une zone de saisie. Sans quoi un texte arrivé par l'API avec un retour chariot paraîtrait
   modifié dès qu'on l'affiche, et partirait avec le premier enregistrement venu. */
function pjTexte(v) {
  return String(v == null ? "" : v).replace(/\r\n?/g, "\n").trim();
}

/* Les deux textes d'un projet, pour qui en DÉCIDE : sa description, et pourquoi il existe.
   La justification n'a son champ que si le serveur l'a rendue — la clé absente ne se lit
   pas « jamais écrite » (cf. `pjRendreFiche`), et un champ vide dessiné à sa place
   proposerait d'effacer ce qu'on n'a pas lu. */
function pjChampsDecrire(p) {
  return `<div class="pj-decrire">
      <label for="pj-decrire-description">Description</label>
      <textarea id="pj-decrire-description" rows="2">${esc(pjTexte(p.description))}</textarea>
      ${"justification" in p ? `<label for="pj-decrire-justification">Pourquoi ce projet
        existe <span class="muted small">— sa justification, scientifique d'abord. Elle se lit
        dans cette fiche, par ses responsables et les administrateurs.</span></label>
      <textarea id="pj-decrire-justification" rows="3">${esc(pjTexte(p.justification))}</textarea>` : ""}
      <div class="pj-decrire-pied"><button type="button" class="ghost small"
        data-pj-decrire="1">Enregistrer</button>${pjLigneDeGeste("decrire", "span")}</div>
    </div>`;
}

/* Ce que DÉCIDER permet, ou la phrase qui dit à qui le demander. Le projet de repli se
   renomme et ne se supprime pas : le serveur le refuserait, et le dirait — autant ne pas
   offrir un bouton dont on connaît la réponse.

   La phrase du responsable nomme TOUT ce qu'il ne peut pas : il lit la description et la
   justification dans cette fiche, et rien ne lui disait à qui demander de les corriger. */
function pjDecider(p) {
  if (!PJ.decide) {
    return `<p class="col-note pj-a-demander">Vous réglez qui entre dans ce projet. Le
      renommer, corriger sa description ou sa justification, ou le supprimer se demande à un
      administrateur de l'instance.</p><div id="pj-demander-zone">${pjDemander(p)}</div>`;
  }
  return `<div class="pj-renommer">
      <label for="pj-renommer-nom">Nom</label>
      <input id="pj-renommer-nom" autocomplete="off" value="${esc(p.nom)}">
      <button type="button" class="ghost small" data-pj-renommer="1">Renommer</button>
    </div>
    ${pjLigneDeGeste("renommer", "p")}
    ${pjChampsDecrire(p)}
    ${p.repli
      ? `<p class="col-note">C'est le projet de repli : une collection créée sans nommer de
          projet y est rangée. Il se renomme, il ne se supprime pas.</p>`
      : `<p class="pj-supprimer"><button type="button" class="danger"
          data-pj-supprimer="1">Supprimer le projet</button></p>
         ${pjLigneDeGeste("supprimer", "p")}
         <p class="col-note">Un projet ne se supprime que vide : tant qu'une collection lui
          appartient, le serveur le refuse.</p>`}`;
}

/* COL-3, tranche 2 (décision B5) — le responsable DEMANDE la suppression de son projet, motif
   à l'appui ; un administrateur y répond dans le fonds. Une demande qui attend se dit, et
   ne se redépose pas. Le projet de repli ne se supprime pas : rien à demander. */
function pjDemander(p) {
  if (p.repli) return "";
  if (p.demande_suppression) {
    return `<p class="pj-demande-etat" tabindex="-1"><span class="pj-puce">suppression `
      + `demandée le ${esc(BDSuppression.dateLue(p.demande_suppression.date_creation))}</span>`
      + `</p>${pjLigneDeGeste("demander", "p")}`;
  }
  // Un geste RARE : pas de champ à demeure dans la fiche (préférence de Hugo). Le bouton
  // ouvre le motif à sa place, sans bascule — il disparaît, le champ prend le focus, et
  // « Annuler » le rend.
  if (PJ.demanderOuvert !== p.id) {
    return `<p class="pj-demander-ouvrir"><button type="button" class="ghost small"
        data-pj-demander-ouvrir="1">Demander sa suppression…</button></p>
      ${pjLigneDeGeste("demander", "p")}`;
  }
  return `<div class="pj-demander">
      <label for="pj-demander-motif">Pourquoi le supprimer</label>
      <textarea id="pj-demander-motif" rows="2"></textarea>
      <div class="pj-decrire-pied"><button type="button" class="ghost small"
        data-pj-demander="1">Envoyer la demande</button><button type="button" class="ghost small"
        data-pj-demander-annuler="1">Annuler</button>${pjLigneDeGeste("demander", "span")}</div>
    </div>`;
}

/* Ouvre ou referme le motif SUR PLACE : seule la zone du geste se redessine, pas la fiche
   (qui remonterait « Qui y entre » et effacerait son message). */
function pjDemanderBasculer(ouvrir) {
  const p = pjProjet(), zone = $("#pj-demander-zone");
  if (!p || !zone) return;
  PJ.demanderOuvert = ouvrir ? p.id : null;
  pjTaireSauf(null);
  zone.innerHTML = pjDemander(p);
  const cible = ouvrir ? $("#pj-demander-motif")
                       : zone.querySelector("[data-pj-demander-ouvrir]");
  if (cible) cible.focus();
}

async function pjDemanderSuppression() {
  const p = pjProjet(), ligne = $("#pj-demander-msg");
  if (!p) return;
  const motif = $("#pj-demander-motif").value.trim();
  if (!motif) {
    pjMsg(ligne, "Dites pourquoi : c'est ce que l'administrateur lira pour décider.", true);
    $("#pj-demander-motif").focus();
    return;
  }
  try {
    await apiSend("POST", "/api/demandes",
                  { genre: BDSuppression.GENRE_PROJET, projet_id: p.id, motif });
  } catch (e) { pjMsg(ligne, e.message || "Échec", true); return; }
  PJ.demanderOuvert = null;
  if (!await pjLire()) return;
  pjRendre();
  // Le message se lit CONTRE ce qui a changé — la puce qui remplace le geste —, pas en tête
  // du bloc, où il poussait toute la page d'une ligne (relevé sur capture).
  pjMsg($("#pj-demander-msg"), "Votre demande est partie à un administrateur. Rien n'est "
    + "supprimé d'ici sa réponse.");
  const etat = document.querySelector("#pj-fiche .pj-demande-etat");
  if (etat) etat.focus();
}

/* La ligne sous le nom : le nombre de collections, et les états. Écrite à part, parce
   qu'après un geste du module sur les membres elle se REDESSINE seule (« sans responsable »
   peut s'y allumer ou s'y éteindre) : remonter la fiche effacerait le message du module. */
function pjSous(p) {
  return `<span>${esc(pjPluriel(p.nb_collections, "collection"))}</span>`
    + (p.repli ? `<span class="pj-puce">projet de repli</span>` : "")
    + (p.sans_responsable && !p.repli
      ? `<span class="lf-puce alerte pj-sans-responsable">sans responsable</span>` : "")
    + (p.demande_suppression && PJ.decide
      ? `<span class="sp-pastille">suppression demandée</span>` : "");
}

function pjRafraichirTete() {
  const p = pjProjet(), sous = document.querySelector("#pj-fiche .pj-sous");
  if (p && sous) sous.innerHTML = pjSous(p);
}

/* « Nouveau projet », dans la fiche. Le nom est BORNÉ par le serveur
   (`database.LONGUEUR_NOM_PROJET`, recopiée une fois dans `lib/projet.js`). */
function pjFicheCreer() {
  return `<article class="pj-carte pj-creer" id="pj-creer" aria-labelledby="pj-creer-titre">
    <div class="pj-tete"><h3 id="pj-creer-titre" tabindex="-1">Nouveau projet</h3></div>
    <div class="pj-creer-ligne">
      <label for="pj-nom">Nom</label>
      <input id="pj-nom" autocomplete="off" aria-describedby="pj-nom-aide">
    </div>
    <p class="muted small" id="pj-nom-aide">${BDProjet.LONGUEUR_NOM} caractères au plus : le
      nom se lit en haut de chaque page, où il ne se coupe pas.</p>
    <label for="pj-justification">Pourquoi ce projet existe <span class="muted small">— sa
      justification, scientifique d'abord. Elle se lit dans sa fiche, par ses responsables et
      les administrateurs.</span></label>
    <textarea id="pj-justification" rows="3"></textarea>
    ${pjRadiosPosition("pj-creer-position", "ecriture",
      "Ce que sa collection de base ouvre aux membres")}
    <p class="col-note">Le projet naît avec sa collection de base, de son nom : ce qu'il prend
      au fonds y arrive. La position se change ensuite dans sa fiche.</p>
    <div class="pj-decrire-pied"><button id="pj-ajouter" class="primary small"
      type="button">+ Créer le projet</button><button type="button" class="ghost small"
      data-pj-creer-annuler="1">Annuler</button>${pjLigneDeGeste("creer", "span")}</div>
  </article>`;
}

/* --- Ce que la base ouvre aux membres (COL-3, D10 ; écran de la 3a) ------------------- */

/* Trois boutons radio, une phrase chacun — les mots de `BDProjet.POSITIONS`. `valeur` :
   celle qui est cochée (`null` = protégée). La base protégée porte la valeur vide dans le
   formulaire, et `pjPositionChoisie` la rend à `null`. */
function pjRadiosPosition(nom, valeur, legende) {
  return `<fieldset class="pj-positions" id="${nom}">
    <legend>${esc(legende)}</legend>
    ${BDProjet.POSITIONS.map((p, i) => `<label class="pj-position">
      <input type="radio" name="${nom}" value="${p.valeur || ""}" id="${nom}-${i}"
        aria-describedby="${nom}-${i}-phrase"${(valeur === undefined ? null : valeur) === p.valeur
          ? " checked" : ""}>
      <span class="pj-position-nom">${esc(p.libelle)}</span>
      <span class="pj-position-phrase muted small" id="${nom}-${i}-phrase">${esc(p.phrase)}</span>
    </label>`).join("")}
  </fieldset>`;
}

function pjPositionChoisie(nom) {
  const r = document.querySelector(`input[name="${nom}"]:checked`);
  return r && r.value ? r.value : null;
}

/* Le bloc de la fiche. Changer de radio n'applique RIEN : une phrase dit d'abord ce que le
   changement fait — resserrer n'efface aucun travail ; ouvrir dit à combien d'entrées cela
   s'ouvre (`BDProjet.phraseChangement`) —, et « Appliquer » le fait. */
function pjBase(p) {
  if (!p.base) {
    return `<p class="col-note">Ce projet n'a pas de collection de base : signalez-le à un
      administrateur.</p>`;
  }
  const avant = p.base.acces_membres;
  const choix = PJ.position === undefined ? avant : PJ.position;
  const phrase = BDProjet.phraseChangement(avant, choix, p.nb_membres, p.base.nom);
  return `${pjRadiosPosition(`pj-position-${p.id}`, choix,
      `Position des membres dans « ${p.base.nom} »`)}
    ${phrase ? `<div class="pj-position-confirme">
      <p class="small">${esc(phrase)}</p>
      <div class="pj-decrire-pied"><button type="button" class="primary small"
        data-pj-position-ok="1">Appliquer : base ${esc(BDProjet.position(choix).libelle)}</button>
        <button type="button" class="ghost small" data-pj-position-annuler="1">Annuler</button>
      </div></div>` : ""}
    <p class="col-note">La base n'ouvre qu'elle-même : aucune autre collection du projet ne
      suit. Ses responsables en sont propriétaires, quelle que soit la position.</p>
    ${pjLigneDeGeste("position", "p")}`;
}

/* Redessine le bloc SUR PLACE — remonter la fiche remonterait « Qui y entre » et effacerait
   son message. Le focus reste sur la radio qu'on vient de cocher. */
function pjBaseRedessiner(focus) {
  const p = pjProjet(), zone = $("#pj-base-zone");
  if (!p || !zone) return;
  zone.innerHTML = pjBase(p);
  if (focus) {
    const el = zone.querySelector(focus);
    if (el) el.focus();
  }
}

async function pjBaseAppliquer() {
  const p = pjProjet();
  if (!p || !p.base || PJ.position === undefined) return;
  const valeur = PJ.position;
  try {
    await apiSend("PUT", `/api/projets/${p.id}/acces-membres`, { acces_membres: valeur });
  } catch (e) { pjMsg($("#pj-position-msg"), e.message || "Échec", true); return; }
  PJ.position = undefined;
  if (!await pjLire()) return;
  pjRendreListe();
  pjBaseRedessiner(`input[name="pj-position-${p.id}"]:checked`);
  pjMsg($("#pj-position-msg"), `La base « ${p.base.nom} » est désormais `
    + `${BDProjet.position(valeur).libelle} aux membres du projet.`);
}

/* --- Au fonds : les demandes du projet et ses copies gardées (écran de la 3a) ---------- */

/* Lu à part, après la fiche : deux routes réservées à qui GÈRE le projet. Une panne le DIT
   dans le bloc, sans rien cacher d'autre. */
async function pjChargerFonds(p) {
  const id = p.id;
  let demandes, gardees, erreur = null;
  try {
    [demandes, gardees] = await Promise.all([
      apiGet(`/api/projets/${id}/demandes`), apiGet(`/api/projets/${id}/copies-gardees`)]);
  } catch (e) { erreur = e.message || "échec"; }
  if (PJ.sel !== id) return;                 // la fiche a changé pendant la lecture
  PJ.fonds = { projet: id, demandes: demandes || [], gardees: gardees || [], erreur };
  pjFondsRedessiner();
}

function pjFondsRedessiner(focus) {
  const zone = $("#pj-fonds-zone"), p = pjProjet();
  if (!zone || !p) return;
  zone.innerHTML = pjFonds(p);
  if (focus) {
    const el = zone.querySelector(focus);
    if (el) el.focus();
  }
}

/* Les collections du projet où l'on écrit, la base en tête : là où une copie gardée peut
   revenir. Ce que `GET /api/collections` rend, filtré à l'écran ; la garde est celle du
   serveur. */
function pjDestinations(p) {
  return (PJ.collections || []).filter((c) => c.projet_id === p.id && c.ecrivable)
    .sort((a, b) => (b.base ? 1 : 0) - (a.base ? 1 : 0) || a.nom.localeCompare(b.nom, "fr"));
}

function pjFonds(p) {
  const f = PJ.fonds;
  if (!f || f.projet !== p.id) return `<p class="col-note">Chargement…</p>`;
  if (f.erreur) return `<p class="col-note erreur">Ce que le projet attend du fonds n'a pas pu
    être lu : ${esc(f.erreur)}</p>`;
  const G = BDSuppression;
  const demandes = f.demandes.map((d) => {
    const e = G.etatDemande(d);
    const titres = (d.documents || []).map((x) => `« ${x.titre} »`).join(", ");
    const arrivee = `« ${d.collection_nom || "une collection supprimée"} »`;
    const quoi = d.genre === G.GENRE_RENDRE ? `Rendre ${titres} à ${arrivee}`
      : `${pjPluriel((d.documents || []).length, "document")} pour ${arrivee}`;
    const ouvert = PJ.details.has(d.id);
    const quand = [`demandée le ${G.dateLue(d.date_creation)}`,
                   d.date_reponse ? `répondue le ${G.dateLue(d.date_reponse)}` : ""]
      .filter(Boolean).join(" · ");
    return `<li class="pj-demande" data-genre="${esc(d.genre)}">
      <span class="pj-demande-quoi"><b>${esc(quoi)}</b>
        <span class="muted small">${esc(quand)}</span></span>
      <span class="pj-demande-etat-ligne"><span class="af-etat af-etat-${esc(e.code)}">${esc(
        e.libelle)}</span>${d.genre === G.GENRE_ENTREE ? `<button type="button"
        class="ghost small" data-pj-detail="${d.id}" aria-expanded="${ouvert}">${ouvert
          ? "Replier" : "Détail"}</button>` : ""}</span>
      ${ouvert ? `<ul class="lf-lignes pj-demande-docs">${(d.documents || []).map((x) => {
        const l = G.etatLigne(x, d);
        return `<li><span>${esc(x.titre || `document ${x.document_id}`)}</span>
          <span class="af-etat af-etat-${esc(l.code)}">${esc(l.libelle)}</span></li>`;
      }).join("")}</ul>` : ""}
    </li>`;
  }).join("");
  const dest = pjDestinations(p);
  const gardees = f.gardees.map((c) => {
    const notice = [c.serie, c.auteur].filter(Boolean).join(" · ");
    const depuis = c.garde_depuis ? `gardée depuis le ${G.dateLue(c.garde_depuis)}` : "";
    let geste;
    if (c.retour) {
      geste = `<span class="af-etat af-etat-attente">retour demandé le ${esc(
        G.dateLue(c.retour.date_creation))}</span>`;
    } else if (PJ.rendreOuvert === c.album_id) {
      geste = dest.length ? `<span class="pj-rendre">
          <label class="sr-only" for="pj-rendre-${c.album_id}">Rendre « ${esc(c.titre)} » à la
            collection</label>
          <select id="pj-rendre-${c.album_id}">${dest.map((x) => `<option value="${x.id}">${esc(
            x.nom)}${x.base ? " (base)" : ""}</option>`).join("")}</select>
          <button type="button" class="primary small" data-pj-rendre-ok="${c.album_id}">${PJ.decide
            ? "Rendre" : "Demander"}</button>
          <button type="button" class="ghost small" data-pj-rendre-annuler="1">Annuler</button>
        </span>`
        : `<span class="col-note">Aucune collection de ce projet où vous écrivez.</span>`;
    } else {
      geste = `<button type="button" class="ghost small" data-pj-rendre="${c.album_id}">${PJ.decide
        ? "Rendre à…" : "Demander à la rendre…"}</button>`;
    }
    return `<li class="pj-gardee"><span><b>${esc(c.titre)}</b>${notice || depuis
      ? ` <span class="muted small">${esc([notice, depuis].filter(Boolean).join(" · "))}</span>`
      : ""}</span><span class="pj-gardee-geste">${geste}</span></li>`;
  }).join("");
  return `<h4>Au fonds · ${pjPluriel(f.demandes.length, "demande")}</h4>
    ${f.demandes.length ? `<ul class="lf-lignes pj-demandes">${demandes}</ul>`
      : `<p class="muted small">Aucune demande. « + Prendre du fonds… », dans la Bibliothèque,
          en dépose une.</p>`}
    <h4 class="pj-gardees-titre">Copies gardées au fonds · ${f.gardees.length}</h4>
    ${f.gardees.length ? `<ul class="lf-lignes pj-gardees">${gardees}</ul>`
      : `<p class="muted small">Aucune.</p>`}
    <p class="col-note">Une copie gardée au fonds a été retirée de sa dernière collection, avec
      son travail. ${PJ.decide ? "Vous la rendez directement." : "La rendre se demande à un "
      + "administrateur, qui répond « Rendre » ou « Garder au fonds »."}</p>
    ${pjLigneDeGeste("fonds", "p")}`;
}

/* « Demander à la rendre » : la prise du projet avec la réponse `reprendre` — un RETOUR
   que l'administrateur accepte ou refuse ; une portée totale la rend tout de suite. */
async function pjRendreCopie(albumId) {
  const p = pjProjet(), f = PJ.fonds;
  const c = f && f.gardees.find((x) => x.album_id === albumId);
  const sel = $(`#pj-rendre-${albumId}`);
  if (!p || !c || !sel) return;
  const nom = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text : "";
  let r;
  try {
    r = await apiSend("POST", `/api/collections/${sel.value}/prendre`, {
      documents: [{ document_id: c.document_id, reponse: "reprendre", album_id: albumId }] });
  } catch (e) { pjMsg($("#pj-fonds-msg"), e.message || "Échec", true); return; }
  const ligne = (r && r.documents && r.documents[0]) || {};
  PJ.rendreOuvert = null;
  await pjChargerFonds(p);
  const msg = $("#pj-fonds-msg");
  if (ligne.etat === "fait") {
    pjMsg(msg, `« ${c.titre} » est rendu à « ${nom.replace(/ \(base\)$/, "")} », avec son travail.`);
  } else if (ligne.etat === "demande") {
    pjMsg(msg, `Votre demande est partie à un administrateur : il répondra « Rendre » ou « Garder `
      + "au fonds ».");
  } else {
    pjMsg(msg, ligne.motif || "Refusé.", true);
  }
  const t = $("#pj-fonds-zone .pj-gardees-titre");
  if (t) { t.setAttribute("tabindex", "-1"); t.focus(); }
}

function pjRendreFiche() {
  const box = $("#pj-fiche");
  if (PJ.membres) { PJ.membres.demonter(); PJ.membres = null; }
  const retour = `<button type="button" class="ghost small lf-retour" data-pj-retour="1">← Liste</button>`;
  if (PJ.creer) { box.innerHTML = retour + pjFicheCreer(); return; }
  const p = pjProjet();
  if (!p) {
    // Un numéro qu'on ne règle pas : la même phrase, qu'il existe ou non.
    box.innerHTML = PJ.sel !== null && PJ.projets.length
      ? `${retour}<p class="col-note">Ce projet n'est pas parmi ceux que vous réglez.</p>`
      : PJ.decide ? `<p class="muted lf-accueil">Aucun projet : créez-en un avec « + Nouveau
          projet ».</p>` : "";
    return;
  }
  // La justification n'est rendue par le serveur qu'à qui gère le projet : la clé ABSENTE
  // ne se lit pas « jamais écrite », et la fiche ne l'invente pas.
  const justification = !("justification" in p) ? ""
    : `<section class="pj-section"><h4>Pourquoi ce projet existe</h4>
        ${p.justification
          ? `<p class="pj-justification">${esc(p.justification)}</p>`
          : `<p class="muted small">Aucune justification n'a été saisie.</p>`}</section>`;
  box.innerHTML = `${retour}<article class="pj-carte" aria-labelledby="pj-fiche-titre">
    <div class="pj-tete">
      <h3 id="pj-fiche-titre" tabindex="-1">${esc(p.nom)}</h3>
      <p class="pj-sous">${pjSous(p)}</p>
    </div>
    ${p.description ? `<p class="pj-description">${esc(p.description)}</p>` : ""}
    ${justification}
    <section class="pj-section" data-membres-projet></section>
    <section class="pj-section"><h4>Collections</h4>${pjCollections(p)}</section>
    <section class="pj-section pj-base" aria-labelledby="pj-base-titre">
      <h4 id="pj-base-titre">Ce que la base ouvre aux membres${p.base
        ? ` · ${esc(p.base.nom)}` : ""}</h4>
      <div id="pj-base-zone">${pjBase(p)}</div></section>
    <section class="pj-section pj-fonds" id="pj-fonds-zone">${pjFonds(p)}</section>
    <section class="pj-section"><h4>Ce projet</h4>${pjDecider(p)}</section>
  </article>`;
  if (!PJ.fonds || PJ.fonds.projet !== p.id) pjChargerFonds(p);
  PJ.membres = BDMembresProjet.monter(box.querySelector("[data-membres-projet]"), {
    projet: { id: p.id, nom: p.nom, gerable: !!p.gerable },
    groupesAdmin: PJ.groupesAdmin,
    surMessage: pjTaireSauf,
    surChangement: pjApresMembres,
  });
}

/* Après un geste du module sur les membres : la LISTE des projets peut avoir changé — un
   responsable qui se fait sortir ne règle plus le sien, et « sans responsable » s'allume ou
   s'éteint. La fiche, elle, n'est redessinée que si son projet a disparu : la remonter
   effacerait le message que le module vient d'écrire. Sa tête seule suit. */
async function pjApresMembres() {
  const avant = PJ.sel;
  if (!await pjLire()) return;
  if (pjProjet() && PJ.sel === avant) { pjRendreListe(); pjRafraichirTete(); return; }
  PJ.nomme = false;
  pjRendre();
  pjPrevenirLaBande();
}

/* --- Navigation ---------------------------------------------------------------------- */

function pjLireAdresse() {
  const brut = new URLSearchParams(location.search).get("projet");
  PJ.sel = brut && /^[1-9]\d*$/.test(brut) ? Number(brut) : null;
  PJ.nomme = PJ.sel !== null;
  PJ.vueFiche = PJ.sel !== null;
  PJ.creer = false;
}

function pjEcrireAdresse(pousser) {
  const p = new URLSearchParams(location.search);
  if (PJ.sel === null || !PJ.nomme) p.delete("projet"); else p.set("projet", String(PJ.sel));
  const s = p.toString(), url = location.pathname + (s ? "?" + s : "") + location.hash;
  if (url === location.pathname + location.search + location.hash) return;
  history[pousser ? "pushState" : "replaceState"](null, "", url);
}

/* Ouvrir un projet depuis la liste. Au large, le clavier reste sur la ligne choisie, pour
   parcourir la suivante ; sous le seuil étroit, où la fiche remplace la liste, il la suit.
   La fiche déjà ouverte n'est pas remontée : son module garderait sinon son message perdu. */
function pjOuvrir(id, depuisListe) {
  const meme = id === PJ.sel && !PJ.creer && !!pjProjet();
  PJ.sel = id;
  PJ.nomme = true;
  PJ.creer = false;
  PJ.vueFiche = true;
  pjEcrireAdresse(true);
  if (!meme) {
    PJ.position = undefined;
    PJ.rendreOuvert = null;
    PJ.details.clear();
    pjTaireSauf(null);
    pjRendreListe();
    pjRendreFiche();
    $("#pj-fiche").scrollTop = 0;
  }
  pjRendreDisposition();
  if (!depuisListe || CG_ETROIT.matches) {
    const t = $("#pj-fiche-titre");
    if (t) t.focus();
  } else {
    const courant = document.querySelector('#pj-objets .pj-objet[aria-current="true"]');
    if (courant) courant.focus();
  }
}

/* « + Nouveau projet » est dans la LISTE : sous le seuil étroit, « Annuler » y ramène, là où
   le clavier retrouve le bouton qui l'avait ouvert. */
function pjOuvrirCreer(ouvrir) {
  PJ.creer = ouvrir;
  PJ.vueFiche = ouvrir;
  pjTaireSauf(null);
  pjRendreListe();
  pjRendreFiche();
  pjRendreDisposition();
  const cible = ouvrir ? $("#pj-nom") : $("#pj-creer-ouvrir");
  if (cible) cible.focus();
}

/* --- Gestes -------------------------------------------------------------------------- */

async function pjCreer() {
  const ligne = $("#pj-creer-msg");
  const nom = $("#pj-nom").value.trim();
  if (!nom) { pjMsg(ligne, "Donnez un nom au projet.", true); $("#pj-nom").focus(); return; }
  const justification = $("#pj-justification").value.trim();
  // La position des membres dans la base (D10) : la question est POSÉE, « ouverte »
  // présélectionnée, et la réponse part toujours — le serveur ne devine rien.
  const corps = { nom, acces_membres: pjPositionChoisie("pj-creer-position") };
  if (justification) corps.justification = justification;
  let cree;
  try {
    cree = await apiSend("POST", "/api/projets", corps);
  } catch (e) { pjMsg(ligne, e.message || "Échec", true); return; }
  PJ.creer = false;
  PJ.sel = cree.id;
  PJ.nomme = true;
  PJ.vueFiche = true;
  pjEcrireAdresse(true);
  if (!await pjLire()) return;
  pjRendre();
  pjPrevenirLaBande();
  pjMsg($("#pj-msg"), `« ${cree.nom} » créé, avec sa collection de base : faites-y entrer `
    + "quelqu'un dans sa fiche ; il prend ensuite au fonds depuis la Bibliothèque.");
  const titre = $("#pj-fiche-titre");
  if (titre) titre.focus();
}

async function pjRenommer() {
  const p = pjProjet(), ligne = $("#pj-renommer-msg");
  if (!p) return;
  const nom = $("#pj-renommer-nom").value.trim();
  if (!nom) { pjMsg(ligne, "Donnez un nom au projet.", true); return; }
  if (nom === p.nom) { pjMsg(ligne, "Rien n'a changé."); return; }
  try { await apiSend("PATCH", `/api/projets/${p.id}`, { nom }); }
  catch (e) { pjMsg(ligne, e.message || "Échec", true); return; }
  if (!await pjLire()) return;
  pjRendre();
  pjPrevenirLaBande();
  pjMsg($("#pj-renommer-msg"), `Le projet s'appelle désormais « ${nom} ».`);
  $("#pj-renommer-nom").focus();
}

/* Enregistre la description et la justification — CE QUI A CHANGÉ, et rien d'autre : un
   champ qu'on n'a pas touché ne part pas, pour qu'un texte corrigé entre-temps par quelqu'un
   d'autre ne soit pas réécrit par-dessus avec ce que cette page avait lu. Un champ vidé part
   à `null` : le projet n'a plus ce texte, et la fiche le dit.

   La fiche est redessinée — le nouveau texte se lit là où on le lisait —, donc le bouton sur
   lequel on a cliqué n'existe plus : le focus revient sur celui qui le remplace, au lieu de
   retomber en haut de la page. */
async function pjDecrire() {
  const p = pjProjet(), ligne = $("#pj-decrire-msg");
  if (!p) return;
  const champs = [["description", "#pj-decrire-description", "Description"],
                  ["justification", "#pj-decrire-justification", "Justification"]];
  const corps = {}, dits = [];
  for (const [cle, sel, libelle] of champs) {
    const zone = $(sel);
    if (!zone) continue;                       // la justification que le serveur n'a pas rendue
    const texte = pjTexte(zone.value);
    if (texte === pjTexte(p[cle])) continue;
    corps[cle] = texte || null;
    dits.push(libelle);
  }
  if (!dits.length) { pjMsg(ligne, "Rien n'a changé."); return; }
  try { await apiSend("PATCH", `/api/projets/${p.id}`, corps); }
  catch (e) { pjMsg(ligne, e.message || "Échec", true); return; }
  if (!await pjLire()) return;
  pjRendre();
  pjMsg($("#pj-decrire-msg"), dits.length === 2
    ? "Description et justification enregistrées."
    : `${dits[0]} enregistrée.`);
  const bouton = document.querySelector("#pj-fiche [data-pj-decrire]");
  if (bouton) bouton.focus();
}

async function pjSupprimer() {
  const p = pjProjet(), ligne = $("#pj-supprimer-msg");
  if (!p) return;
  if (!confirm(`Supprimer le projet « ${p.nom} » ? Ses membres en sortent. Aucune collection `
               + "n'est touchée : un projet ne se supprime que s'il n'en porte aucune.")) return;
  try { await apiSend("DELETE", `/api/projets/${p.id}`); }
  catch (e) { pjMsg(ligne, e.message || "Échec", true); return; }
  PJ.sel = null;
  PJ.nomme = false;
  PJ.vueFiche = false;
  pjEcrireAdresse(false);
  if (!await pjLire()) return;
  pjRendre();
  pjPrevenirLaBande();
  pjMsg($("#pj-msg"), `« ${p.nom} » supprimé.`);
  $("#projets-titre").focus();
}

function pjDemarrer() {
  pjLireAdresse();
  $("#pj-filtre").addEventListener("input", (ev) => { PJ.filtre = ev.target.value; pjRendreListe(); });
  // La liste se parcourt aux FLÈCHES, comme celles du fonds et de « Comptes et groupes ».
  $("#pj-objets").addEventListener("keydown", (ev) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(ev.key)) return;
    const lignes = [...document.querySelectorAll("#pj-objets .pj-objet")];
    const i = lignes.indexOf(document.activeElement);
    if (i < 0 || !lignes.length) return;
    ev.preventDefault();
    const j = ev.key === "Home" ? 0 : ev.key === "End" ? lignes.length - 1
      : Math.max(0, Math.min(lignes.length - 1, i + (ev.key === "ArrowDown" ? 1 : -1)));
    lignes[j].focus();
  });
  $("#pj").addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    if (b.dataset.pj) pjOuvrir(Number(b.dataset.pj), true);
    else if (b.id === "pj-creer-ouvrir") pjOuvrirCreer(true);
    else if (b.dataset.pjCreerAnnuler) pjOuvrirCreer(false);
    else if (b.id === "pj-ajouter") pjCreer();
    else if (b.dataset.pjRetour) {
      PJ.vueFiche = false;
      pjRendreDisposition();
      const courant = document.querySelector('#pj-objets .pj-objet[aria-current="true"]');
      (courant || $("#pj-filtre")).focus();
    } else if (b.dataset.pjRenommer) pjRenommer();
    else if (b.dataset.pjDecrire) pjDecrire();
    else if (b.dataset.pjSupprimer) pjSupprimer();
    else if (b.dataset.pjDemander) pjDemanderSuppression();
    else if (b.dataset.pjDemanderOuvrir) pjDemanderBasculer(true);
    else if (b.dataset.pjDemanderAnnuler) pjDemanderBasculer(false);
    else if (b.dataset.pjPositionOk) pjBaseAppliquer();
    else if (b.dataset.pjPositionAnnuler) {
      PJ.position = undefined;
      pjTaireSauf(null);
      const p = pjProjet();
      pjBaseRedessiner(p ? `input[name="pj-position-${p.id}"]:checked` : null);
    } else if (b.dataset.pjDetail) {
      const id = Number(b.dataset.pjDetail);
      if (PJ.details.has(id)) PJ.details.delete(id); else PJ.details.add(id);
      pjFondsRedessiner(`[data-pj-detail="${id}"]`);
    } else if (b.dataset.pjRendre) {
      PJ.rendreOuvert = Number(b.dataset.pjRendre);
      pjTaireSauf(null);
      pjFondsRedessiner(`#pj-rendre-${PJ.rendreOuvert}`);
    } else if (b.dataset.pjRendreAnnuler) {
      const id = PJ.rendreOuvert;
      PJ.rendreOuvert = null;
      pjFondsRedessiner(`[data-pj-rendre="${id}"]`);
    } else if (b.dataset.pjRendreOk) pjRendreCopie(Number(b.dataset.pjRendreOk));
  });
  // Une radio de « Ce que la base ouvre aux membres » : rien ne s'applique, la phrase et
  // « Appliquer » paraissent sous elles. Celles du formulaire de création ne font rien ici.
  $("#pj").addEventListener("change", (ev) => {
    const t = ev.target, p = pjProjet();
    if (!p || !t.matches || !t.matches(`input[name="pj-position-${p.id}"]`)) return;
    PJ.position = t.value || null;
    if (p.base && PJ.position === p.base.acces_membres) PJ.position = undefined;
    pjTaireSauf(null);
    pjBaseRedessiner(`input[name="pj-position-${p.id}"]:checked`);
  });
  $("#pj").addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter") return;
    if (ev.target.id === "pj-renommer-nom") { ev.preventDefault(); pjRenommer(); }
    else if (ev.target.id === "pj-nom") { ev.preventDefault(); pjCreer(); }
  });
  return pjCharger();
}


/* ═══════════════════════════════════════════════════════════════════════════
   Le fonds (COL-3, tranche 2) — ce que l'instance détient, pour qui le TIENT

   Tout album est la copie de travail d'un DOCUMENT, et le document appartient à l'instance.
   Ce bloc montre les documents — d'où chacun vient, où il est employé, lesquels ne sont
   appelés par personne — et les gestes de qui tient le fonds : RENDRE une copie gardée à une
   collection de son projet, DÉTRUIRE un document que personne n'appelle, et IMPORTER AU
   FONDS (Hugo, 2026-10-11), un album qui naît « appelé par personne ». Répondre à une
   demande de suppression se fait dans « À faire » (Hugo, 2026-10-16) : la fiche d'un
   document qui en porte une y MÈNE, elle ne la double pas.

   UNE LISTE ET UNE FICHE (le gabarit `lf-` de « Comptes et groupes ») : un millier de
   documents rendus en entier l'un sous l'autre, sans filtre ni regroupement, ne se lisaient
   plus (relevé par Hugo le 2026-10-16). On cherche par titre, série ou auteur, par projet,
   par qui l'a importé, par état — les quatre entrées nommées par Hugo sur la maquette. La
   liste ne dessine que `FD_MAX` lignes à la fois et dit combien restent : le serveur rend
   tout d'un coup, c'est le DOM qui ne suivrait pas.

   LA GARDE EST CELLE DU SERVEUR. Le bloc est `hidden` par défaut et ne se lève que si
   `GET /api/fonds` répond : un 403 le laisse fermé, sans un mot — c'est la réponse d'une
   route réservée, comme celle de « Comptes et groupes ». Aucune autre panne ne le cache :
   un administrateur devant un bloc qui disparaît chercherait un droit qu'il a déjà. Qui le
   tient : l'administrateur, et l'usage sur un seul poste (`Portee.peut_tenir_le_fonds`).

   « Rendre » et « Détruire » n'ont pas de route à eux : ce sont le rangement
   (`PUT /api/albums/{id}/collections/{cid}`) et la destruction (`DELETE /api/albums/{id}`)
   d'aujourd'hui, joués par une portée totale. Les mots — ce qu'une demande dit, d'où vient
   un document — viennent de `lib/suppression.js`.

   LA SÉLECTION VIT DANS L'ADRESSE (`?vue=fonds&document=…`), pour qu'on puisse envoyer une
   fiche ; les filtres n'y sont pas : ce sont des saisies, pas des endroits.
   ═══════════════════════════════════════════════════════════════════════════ */
const FD = {
  documents: [],
  demandes: [],          // les demandes EN ATTENTE, telles que `GET /api/demandes` les rend
  collections: null,     // pour « Rendre à… » ; null = illisible
  textes: {},            // id de demande → { texte }, lu par « À regarder »
  sansDocument: [],
  lu: false,             // le fonds a répondu
  filtre: "", etat: "tous", projet: "", importeur: "", tri: "recents",
  sel: null,             // l'identifiant du document dont la fiche est ouverte
  importer: false,       // la fiche montre le formulaire « Importer au fonds »
  vueFiche: false,       // sous le seuil étroit, la fiche REMPLACE la liste
  prendre: null,         // le document dont « Prendre dans… » est ouvert
};
const FD_MAX = 400;

/* UN message à la fois dans le bloc — la règle de « Projets », appliquée ici à SES lignes. */
function fdTaireSauf(el) {
  document.querySelectorAll("#fonds-bloc .col-msg").forEach((l) => {
    if (l === el) return;
    l.textContent = "";
    l.classList.remove("erreur", "alerte");
  });
}

function fdMsg(el, texte, erreur) {
  fdTaireSauf(el);
  el.textContent = texte || "";
  el.classList.toggle("erreur", !!erreur);
}

async function fdCharger() {
  let fonds;
  try { fonds = await apiGet("/api/fonds"); }
  catch (e) {
    FD.lu = false;
    if (e.statut === 403) { $("#fonds-bloc").hidden = true; return false; }
    $("#fonds-bloc").hidden = false;
    fdMsg($("#fd-msg"), `Le fonds n'a pas pu être lu : ${e.message}`, true);
    return false;
  }
  // Les demandes et les collections ne font tomber ni l'une ni l'autre le bloc : sans elles,
  // il le DIT là où elles manquent.
  const [demandes, collections] = await Promise.all([
    apiGet("/api/demandes").catch(() => null),
    apiGet("/api/collections").catch(() => null),
  ]);
  FD.lu = true;
  FD.documents = fonds.documents || [];
  FD.sansDocument = fonds.copies_sans_document || [];
  // TOUS les genres qui attendent (COL-3, écran de la 3a) : « À faire » rend chacun avec SES
  // mots et SES boutons (`BDSuppression.genreDemande`) — l'entrée de documents, le rejoindre,
  // le retour d'une copie gardée comme les deux suppressions. Le filtre posé par la relecture
  // croisée du serveur de la prise, faute de cet écran, est levé : « Détruire » ne répond
  // qu'à une suppression de document.
  FD.demandes = demandes === null ? null : demandes.filter((d) => d.en_attente);
  FD.collections = collections;
  FD.textes = Object.fromEntries((FD.demandes || []).map((d) =>
    [d.id, { texte: BDSuppression.texteDemande(d) }]));
  $("#fonds-bloc").hidden = false;
  fdRendre();
  // « À regarder » se nomme avec ce que le fonds vient de lire, et « À faire » s'en nourrit.
  if (CG.donnees) cgRendreSignaux();
  afRendre();
  return true;
}

/* --- Lecture d'un document ----------------------------------------------------------- */

function fdPremiere(d) { return d.copies[0] || {}; }
function fdGardees(d) { return d.copies.filter((c) => !c.collections.length); }
/* Une copie GARDÉE est une copie sans collection qui garde son projet ; celle qu'on importe
   au fonds n'en a jamais eu, et n'est qu'« appelée par personne ». */
function fdAUneCopieGardee(d) { return fdGardees(d).some((c) => c.projet_id != null); }
function fdProjetNom(d) { return fdPremiere(d).projet_nom || ""; }

/* Ce que la ligne dit de l'état, en un mot — l'alerte d'abord : quelqu'un attend. */
function fdEtatCourt(d) {
  if (d.demande) return { texte: "⚠ suppression demandée", alerte: true };
  if (!d.appele) return { texte: fdAUneCopieGardee(d) ? "copie gardée" : "appelé par personne",
                          alerte: false };
  // Plusieurs copies (COL-3, tranche 3a) : le nombre de copies d'abord, c'est ce qui distingue
  // ce document des autres.
  if (d.copies.length > 1) return { texte: pjPluriel(d.copies.length, "copie"), alerte: false };
  const n = d.copies.reduce((s, c) => s + c.collections.length, 0);
  return { texte: pjPluriel(n, "collection"), alerte: false };
}

/* Deux copies du même document disent-elles deux titres ? La notice reste sur chaque copie
   (D7), libre de diverger ; le fonds montre celle de la plus ancienne, et dit l'écart. */
function fdNoticeDivergente(d, c) {
  const p = fdPremiere(d);
  return d.copies.length > 1 && c.album_id !== p.album_id && (c.titre || "") !== (p.titre || "");
}

function fdFiltres() {
  const f = BDComptes.normaliser(FD.filtre.trim());
  let l = FD.documents.filter((d) => {
    if (FD.etat === "demande" && !d.demande) return false;
    if (FD.etat === "personne" && d.appele) return false;
    if (FD.etat === "gardee" && !fdAUneCopieGardee(d)) return false;
    if (FD.etat === "soeurs" && d.copies.length < 2) return false;
    if (FD.projet === "-" ? fdPremiere(d).projet_id != null
        : FD.projet && String(fdPremiere(d).projet_id) !== FD.projet) return false;
    if (FD.importeur === "-" ? !!d.importe_par
        : FD.importeur && d.importe_par !== FD.importeur) return false;
    if (!f) return true;
    const p = fdPremiere(d);
    return [p.titre, p.serie, p.auteur].some((x) => x && BDComptes.normaliser(x).includes(f));
  });
  const titre = (d) => BDSuppression.titreDocument(d);
  const parTitre = (a, b) => titre(a).localeCompare(titre(b), "fr");
  if (FD.tri === "alpha") l = l.sort(parTitre);
  else if (FD.tri === "projet") {
    l = l.sort((a, b) => (fdProjetNom(a) || "￿").localeCompare(fdProjetNom(b) || "￿", "fr")
                         || parTitre(a, b));
  } else {
    // Récents d'abord ; un import dont la date n'est pas écrite (avant le fonds) après.
    l = l.sort((a, b) => String(b.importe_le || "").localeCompare(String(a.importe_le || ""))
                         || b.id - a.id);
  }
  return l;
}

/* --- Rendu ------------------------------------------------------------------------- */

function fdRendre() {
  const docs = FD.documents;
  const personne = docs.filter((d) => !d.appele).length;
  // Le compte du fonds parle de SUPPRESSIONS : les autres demandes ne visent pas un document
  // qu'on détruirait, elles se lisent dans « À faire ».
  const n = FD.demandes ? FD.demandes.filter(BDSuppression.estUneSuppression).length : 0;
  $("#fd-compte").textContent = [
    pjPluriel(docs.length, "document"),
    `${personne} appelé${personne > 1 ? "s" : ""} par personne`,
    FD.demandes === null ? "demandes illisibles"
      : `${n} suppression${n > 1 ? "s" : ""} demandée${n > 1 ? "s" : ""}`,
  ].join(" · ");
  $("#vue-compte-fonds").textContent = ` ${docs.length}`;
  fdRendreChoix();
  fdRendreControles();
  fdRendreListe();
  fdRendreFiche();
  $("#fd-sans-document").hidden = !FD.sansDocument.length;
  $("#fd-sans-document").textContent = FD.sansDocument.length
    ? `${pjPluriel(FD.sansDocument.length, "album")} sans document (base retouchée à la main) : `
      + FD.sansDocument.map((id) => `n° ${id}`).join(", ") + "."
    : "";
}

/* Les deux listes de choix se composent avec ce que le fonds a rendu : aucun projet ni
   aucun importateur n'y figure sans document derrière. La valeur choisie survit au rendu. */
function fdRendreChoix() {
  const projets = new Map(), importeurs = new Map();
  let sansProjet = false, sansImporteur = false;
  FD.documents.forEach((d) => {
    const p = fdPremiere(d);
    if (p.projet_id != null) projets.set(String(p.projet_id), p.projet_nom || `projet ${p.projet_id}`);
    else sansProjet = true;
    if (d.importe_par) importeurs.set(d.importe_par, d.importe_par_nom || d.importe_par);
    else sansImporteur = true;
  });
  const options = (m, vide, sans, sansLib) => `<option value="">${vide}</option>`
    + (sans ? `<option value="-">${sansLib}</option>` : "")
    + [...m].sort((a, b) => a[1].localeCompare(b[1], "fr"))
      .map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join("");
  const sp = $("#fd-projet"), si = $("#fd-importeur");
  sp.innerHTML = options(projets, "Tous", sansProjet, "Sans projet");
  si.innerHTML = options(importeurs, "Tous", sansImporteur, "Non écrit (avant le fonds)");
  if (![...sp.options].some((o) => o.value === FD.projet)) FD.projet = "";
  if (![...si.options].some((o) => o.value === FD.importeur)) FD.importeur = "";
  sp.value = FD.projet;
  si.value = FD.importeur;
}

function fdRendreControles() {
  const docs = FD.documents;
  const nombres = {
    tous: docs.length,
    demande: docs.filter((d) => d.demande).length,
    personne: docs.filter((d) => !d.appele).length,
    gardee: docs.filter(fdAUneCopieGardee).length,
    soeurs: docs.filter((d) => d.copies.length > 1).length,
  };
  document.querySelectorAll("#fd [data-fd-etat]").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.fdEtat === FD.etat));
    if (!b.dataset.libelle) b.dataset.libelle = b.textContent;
    b.textContent = `${b.dataset.libelle} ${nombres[b.dataset.fdEtat]}`;
  });
  document.querySelectorAll("#fd [data-fd-tri]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.fdTri === FD.tri)));
  $("#fd").classList.toggle("lf--fiche", FD.vueFiche && (FD.sel !== null || FD.importer));
}

function fdRendreListe() {
  const l = fdFiltres();
  const actif = document.activeElement;
  const garde = actif && actif.closest && actif.closest("#fd-objets") && actif.dataset.fdDoc
    ? actif.dataset.fdDoc : null;
  $("#fd-liste-compte").textContent = l.length === FD.documents.length
    ? pjPluriel(l.length, "document") : `${l.length} sur ${FD.documents.length}`;
  let html = "", groupe = null;
  l.slice(0, FD_MAX).forEach((d) => {
    if (FD.tri === "projet") {
      const g = fdProjetNom(d) || "Sans projet";
      if (g !== groupe) { groupe = g; html += `<li class="lf-groupe">${esc(g)}</li>`; }
    }
    const e = fdEtatCourt(d);
    const detail = [fdProjetNom(d) || "sans projet",
                    d.importe_par ? (d.importe_par_nom || d.importe_par) : "importateur non écrit",
                    BDSuppression.dateLue(d.importe_le)].filter(Boolean).join(" · ");
    html += `<li><button type="button" class="lf-objet fd-objet" data-fd-doc="${d.id}"`
      + `${FD.sel === d.id ? ' aria-current="true"' : ""}>`
      + `<span class="lf-nom">${esc(BDSuppression.titreDocument(d))}</span>`
      + `<span class="lf-etat${e.alerte ? " alerte" : ""}">${esc(e.texte)}</span>`
      + `<span class="lf-detail">${esc(detail)}</span></button></li>`;
  });
  if (l.length > FD_MAX) {
    html += `<li class="lf-vide muted small">… et ${l.length - FD_MAX} de plus : affinez le
      filtre.</li>`;
  }
  if (!l.length) {
    html = `<li class="lf-vide muted small">${FD.documents.length
      ? "Aucun document ne répond à ces filtres." : "Aucun document."}</li>`;
  }
  $("#fd-objets").innerHTML = html;
  if (garde !== null) {
    const b = document.querySelector(`#fd-objets [data-fd-doc="${CSS.escape(garde)}"]`);
    if (b) b.focus();
  }
}

function fdRendreFiche() {
  const box = $("#fd-fiche");
  const retour = `<button type="button" class="ghost small lf-retour" data-fd-retour="1">← Liste</button>`;
  if (FD.importer) { box.innerHTML = retour + fdFicheImporter(); return; }
  const d = FD.sel === null ? null : FD.documents.find((x) => x.id === FD.sel);
  if (!d) {
    box.innerHTML = FD.sel === null
      ? `<p class="muted lf-accueil">Choisissez un document dans la liste pour ouvrir sa fiche.</p>`
      : `${retour}<p class="col-note">Ce document n'est plus au fonds.</p>`;
    return;
  }
  box.innerHTML = retour + fdFicheDocument(d);
}

function fdFicheImporter() {
  return `<article class="lf-carte" aria-labelledby="fd-importer-titre">
    <div class="lf-tete"><h3 id="fd-importer-titre" tabindex="-1">Importer au fonds</h3></div>
    <p class="muted small">L'album naît appelé par personne, sans projet ; « Rendre » le range
      ensuite dans une collection.</p>
    <div class="fd-importer-ligne">
      <label class="sr-only" for="fd-titre">Titre de l'album à importer au fonds</label>
      <input id="fd-titre" placeholder="Titre de l'album" autocomplete="off">
      <label class="sr-only" for="fd-fichiers">Planches à importer</label>
      <input id="fd-fichiers" type="file" multiple
             accept=".tif,.tiff,.jpg,.jpeg,.jp2,.j2k,.jpf,.jpx,.jpc,.j2c,.png,.bmp,.gif,.webp">
      <button id="fd-importer" class="primary small" type="button">+ Importer au fonds</button>
      <button class="ghost small" type="button" data-fd-importer-annuler="1">Annuler</button>
    </div>
    <p id="fd-importer-msg" class="col-msg muted small" role="status" aria-live="polite"></p>
  </article>`;
}

function fdFicheDocument(d) {
  const titre = BDSuppression.titreDocument(d);
  const p = fdPremiere(d);
  const sous = [p.serie, p.auteur, d.copies.length ? pjPluriel(p.nb_planches || 0, "planche") : ""]
    .filter(Boolean).map((x) => `<span>${esc(x)}</span>`).join("");
  const e = fdEtatCourt(d);
  const emplois = BDSuppression.emplois(d);
  const gardees = fdGardees(d);
  const demande = d.demande ? `<section class="lf-section lf-large fd-demande-fiche">
      <h4>Suppression demandée</h4>
      <p class="small">${esc(BDSuppression.pastille(d.demande))}${d.demande.date_creation
        ? ` le ${esc(BDSuppression.dateLue(d.demande.date_creation))}` : ""}.</p>
      ${d.demande.motif ? `<p class="fd-motif">${esc(d.demande.motif)}</p>` : ""}
      <p><button type="button" class="ghost small" data-fd-repondre="${d.demande.id}">Répondre
        dans « À faire » →</button></p>
    </section>` : "";
  const atelier = p.album_id
    ? `<a class="ghost small" href="/?album=${p.album_id}">Ouvrir dans l'Atelier</a>` : "";
  return `<article class="lf-carte fd-doc" id="fd-doc-${d.id}" aria-labelledby="fd-fiche-titre">
    <div class="lf-tete">
      <div>
        <h3 id="fd-fiche-titre" tabindex="-1">${esc(titre)}</h3>
        <p class="lf-sous">${sous}<span class="lf-puce${e.alerte ? " alerte" : ""}">${esc(
          e.texte.replace(/^⚠ /, ""))}</span></p>
      </div>
      ${atelier ? `<div class="lf-gestes-tete">${atelier}</div>` : ""}
    </div>
    ${demande}
    <section class="lf-section"><h4>Origine</h4>
      <p class="small fd-origine">${esc(BDSuppression.origine(d))}</p></section>
    <section class="lf-section"><h4>Employé dans</h4>
      ${emplois.length ? `<p class="small fd-emplois">Employé par ${esc(emplois.join(" ; "))}</p>`
        : `<p class="small">Aucune collection.</p>`}
    </section>
    <section class="lf-section fd-copies-section"><h4>Copies de travail · ${d.copies.length}</h4>
      <ul class="lf-lignes fd-copies">${d.copies.map((c) => fdCopie(d, c)).join("")}</ul>
      ${gardees.map((c) => fdGardee(d, c)).join("")}
      ${d.copies.length > 1 ? `<p class="col-note">Les copies d'un même document partagent ses
        images ; chacune garde sa notice et son travail.</p>` : ""}
    </section>
    <section class="lf-section fd-prendre-section"><h4>Prendre dans…</h4>${fdPrendre(d)}</section>
    ${!d.appele && d.copies.length ? `<div class="fd-zone-danger"><button type="button"
        class="danger" data-fd-detruire="${d.id}">Détruire</button><span class="muted small">Personne
        ne l'appelle : il peut être détruit.</span></div>` : ""}
    <p id="fd-doc-msg-${d.id}" class="col-msg fd-ligne-msg muted small" role="status"
       aria-live="polite"></p>
  </article>`;
}

/* Une COPIE DE TRAVAIL du document (COL-3, tranche 3a) : sa notice — marquée « notice
   divergente » quand elle dit un autre titre que la première (D7) —, son projet, ses
   collections ou « copie gardée », qui l'a créée, et si c'est une copie vierge. Un retour qui
   l'attend se dit, et mène à « À faire ». */
function fdCopie(d, c) {
  const G = BDSuppression;
  const ou = c.collections.length ? c.collections.map((x) => x.nom).join(", ")
    : c.projet_id != null ? "copie gardée au fonds" : "appelée par personne";
  const parts = [c.projet_nom || "sans projet", ou,
                 c.creee_par ? `créée par ${c.creee_par_nom || c.creee_par}`
                   : "qui l'a créée n'est pas écrit",
                 c.cran === "images" ? "copie vierge, images partagées" : ""].filter(Boolean);
  return `<li class="fd-copie"><span><b>${esc(c.titre)}</b>${fdNoticeDivergente(d, c)
      ? ` <span class="lf-puce alerte" title="La notice reste sur chaque copie : celle-ci dit un autre titre">notice divergente</span>`
      : ""}
      <span class="muted small fd-copie-detail">${esc(parts.join(" · "))}</span></span>
    ${c.retour ? `<button type="button" class="ghost small" data-fd-repondre="${c.retour.id}">Retour
      demandé le ${esc(G.dateLue(c.retour.date_creation))} →</button>` : ""}
  </li>`;
}

/* « Prendre dans… » (COL-3, tranche 3a, D3) : l'administrateur prend DIRECTEMENT ce document
   pour une collection — une copie vierge, à son nom. Les collections groupées par projet, la
   base de chacun en tête (D10). Le résultat est « fait », jamais « demandé ». */
function fdPrendre(d) {
  if (FD.collections === null) {
    return `<p class="col-note">Les collections n'ont pas pu être lues.</p>`;
  }
  if (FD.prendre !== d.id) {
    return `<p><button type="button" class="ghost small" data-fd-prendre="${d.id}">Prendre
      dans…</button></p>
      <p class="col-note">Une copie de travail vierge entre dans la collection choisie ; les
        images sont celles du document, et ses autres copies ne bougent pas.</p>`;
  }
  const projets = new Map();
  FD.collections.filter((c) => c.ecrivable !== false).forEach((c) => {
    const cle = c.projet_id == null ? "" : String(c.projet_id);
    if (!projets.has(cle)) projets.set(cle, { nom: c.projet_nom || "Sans projet", cols: [] });
    projets.get(cle).cols.push(c);
  });
  const groupes = [...projets.values()].sort((a, b) => a.nom.localeCompare(b.nom, "fr"))
    .map((p) => `<optgroup label="${esc(p.nom)}">${p.cols
      .sort((a, b) => (b.base ? 1 : 0) - (a.base ? 1 : 0) || a.nom.localeCompare(b.nom, "fr"))
      .map((c) => `<option value="${c.id}">${esc(c.nom)}${c.base ? " (base)" : ""}</option>`)
      .join("")}</optgroup>`).join("");
  return `<div class="fd-prendre">
    <label for="fd-prendre-dest">Collection d'arrivée</label>
    <select id="fd-prendre-dest">${groupes}</select>
    <button type="button" class="primary small" data-fd-prendre-ok="${d.id}">Prendre</button>
    <button type="button" class="ghost small" data-fd-prendre-annuler="1">Annuler</button>
  </div>`;
}

async function fdPrendreDans(docId) {
  const d = FD.documents.find((x) => x.id === docId), sel = $("#fd-prendre-dest");
  const ligne = $(`#fd-doc-msg-${docId}`);
  if (!d || !sel) return;
  const nom = (sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text : "")
    .replace(/ \(base\)$/, "");
  let r;
  try {
    r = await apiSend("POST", `/api/collections/${sel.value}/prendre`,
                      { documents: [{ document_id: d.id, reponse: "zero" }] });
  } catch (e) { fdMsg(ligne, e.message || "Échec", true); return; }
  const l = (r && r.documents && r.documents[0]) || {};
  if (l.etat !== "fait") { fdMsg(ligne, l.motif || "La prise n'a pas abouti.", true); return; }
  FD.prendre = null;
  await fdApres(`#fd-doc-msg-${docId}`, `Fait : une copie vierge de « ${
    BDSuppression.titreDocument(d)} » est entrée dans « ${nom} ».`);
  const t = $("#fd-fiche-titre");
  if (t) t.focus();
}

/* Une copie GARDÉE — retirée de sa dernière collection, ou importée au fonds — et
   « Rendre à… », vers une collection de SON projet : le serveur refuse toute autre. */
function fdGardee(d, c) {
  const projet = c.projet_nom ? `projet « ${c.projet_nom} »` : "sans projet";
  const choix = FD.collections === null ? null : BDSuppression.rendreA(c, FD.collections);
  let geste;
  if (choix === null) {
    geste = `<span class="col-note">Les collections n'ont pas pu être lues.</span>`;
  } else if (!choix.length) {
    geste = `<span class="col-note">Aucune collection de son projet où la rendre.</span>`;
  } else {
    geste = `<label class="sr-only" for="fd-rendre-${c.album_id}">Rendre « ${esc(c.titre)} » à
        la collection</label>
      <select id="fd-rendre-${c.album_id}">${choix.map((x) =>
        `<option value="${x.id}">${esc(x.nom)}</option>`).join("")}</select>
      <button type="button" class="ghost small" data-fd-rendre="${c.album_id}"
              data-fd-doc-de="${d.id}">Rendre</button>`;
  }
  return `<div class="fd-gardee">
    <span class="small">Copie gardée ici (${esc(projet)}).</span>
    <span class="fd-rendre">${geste}</span>
  </div>`;
}

/* --- Navigation ---------------------------------------------------------------------- */

function fdLireAdresse() {
  const brut = new URLSearchParams(location.search).get("document");
  FD.sel = brut && /^[1-9]\d*$/.test(brut) ? Number(brut) : null;
  FD.vueFiche = FD.sel !== null;
  FD.importer = false;
}

function fdEcrireAdresse(pousser) {
  const p = new URLSearchParams(location.search);
  if (FD.sel === null) p.delete("document"); else p.set("document", String(FD.sel));
  const s = p.toString(), url = location.pathname + (s ? "?" + s : "") + location.hash;
  if (url === location.pathname + location.search + location.hash) return;
  history[pousser ? "pushState" : "replaceState"](null, "", url);
}

/* Ouvrir un document : depuis la liste, ou depuis un autre bloc. Au large, un choix dans la
   liste y laisse le clavier, pour parcourir la suivante ; sinon le focus suit la fiche. */
function fdOuvrir(id, depuisListe) {
  if (FD.sel !== id) FD.prendre = null;
  FD.sel = id;
  FD.importer = false;
  FD.vueFiche = true;
  fdTaireSauf(null);
  fdEcrireAdresse(true);
  fdRendreControles();
  fdRendreListe();
  fdRendreFiche();
  $("#fd-fiche").scrollTop = 0;
  if (!depuisListe || CG_ETROIT.matches) {
    const t = $("#fd-fiche-titre");
    if (t) t.focus();
  }
}

/* ── Gestes ─────────────────────────────────────────────────────────────────────── */

/* Après un geste : le fonds se relit, et ce qui en dépend ailleurs dans la page aussi —
   « À regarder », et, si un projet a pu disparaître, le bloc des projets et la bande. */
async function fdApres(el, texte, projetTouche) {
  await fdCharger();
  if (CG.donnees) await cgCharger({ garderFiche: true });
  if (projetTouche && await pjLire()) { pjRendre(); pjPrevenirLaBande(); }
  const lu = typeof el === "string" ? $(el) : el;
  const cible = lu && document.contains(lu) ? lu : $("#fd-msg");
  if (cible.closest("#afaire-bloc")) afTaireSauf(cible);
  fdMsg(cible, texte);
}

/* Répondre à une demande — depuis « À faire », où la ligne s'est dépliée. Le message se lit
   en tête de « À faire » : la ligne, répondue, disparaît avec la demande. */
/* Répondre à une demande, quel qu'en soit le genre. `documentId` : pour une entrée de
   documents, la ligne à laquelle on répond ; absent, la réponse vaut pour toutes celles qui
   attendent (« Tout accepter (n) », « Refuser le reste »). Seules les deux suppressions se
   confirment : ce sont les seules réponses qui effacent quelque chose. Une entrée encore en
   attente après la réponse reste dépliée, et le message se lit sur SA ligne ; une demande
   close disparaît, et le message se lit en tête de « À faire ». */
async function fdRepondre(id, reponse, documentId) {
  const d = (FD.demandes || []).find((x) => x.id === id);
  if (!d) return;
  const ligne = $(`#fd-demande-msg-${id}`);
  const G = BDSuppression;
  const accepter = reponse === G.ACCEPTER;
  const qui = d.demandeur_nom || d.demandeur || "quelqu'un";
  const titres = (d.documents || []).map((x) => `« ${x.titre} »`).join(", ");
  const arrivee = `« ${d.collection_nom || "la collection demandée"} »`;
  if (accepter && d.genre === G.GENRE_PROJET
      && !confirm(`Supprimer le projet « ${d.projet_nom || d.projet_id} » ? Ses membres en `
                  + "sortent. Il ne se supprime que vide.")) return;
  // Une autre copie du document l'emploie-t-elle ? Le fonds le sait : ses images restent
  // alors (D6), et la confirmation le dit — sans dire où vit l'autre copie.
  const soeur = (d.documents || []).some((x) => {
    const doc = FD.documents.find((y) => y.id === x.document_id);
    return !!doc && doc.copies.length > 1;
  });
  if (accepter && d.genre === G.GENRE_DOCUMENT
      && !confirm(G.confirmationDetruire((d.documents || []).map((x) => x.titre).join(", "),
                                         soeur))) {
    return;
  }
  const corps = { reponse };
  if (documentId !== undefined) corps.document_id = documentId;
  let vue;
  try {
    vue = await apiSend("POST", `/api/demandes/${id}/reponse`, corps);
  } catch (e) { afMsg(ligne, e.message || "Échec", true); return; }
  const enAttente = !!(vue && vue.en_attente);
  const doc = documentId === undefined ? null
    : (d.documents || []).find((x) => x.document_id === documentId);
  let texte;
  switch (d.genre) {
    case G.GENRE_PROJET:
      texte = accepter ? `Le projet « ${d.projet_nom || d.projet_id} » est supprimé.`
        : `Le projet « ${d.projet_nom || d.projet_id} » : gardé. La demande de ${qui} est close.`;
      break;
    case G.GENRE_DOCUMENT:
      texte = accepter ? `${titres} : détruit — cette copie, et le travail fait dessus.`
        : `${titres} : gardé. La demande de ${qui} est close.`;
      break;
    case G.GENRE_ENTREE:
      if (doc) {
        texte = accepter ? `« ${doc.titre} » entre dans ${arrivee}, en copie vierge.`
          : `« ${doc.titre} » : refusé.`;
      } else {
        texte = accepter ? `Les documents qui attendaient entrent dans ${arrivee}.`
          : `Les documents qui attendaient sont refusés. La demande de ${qui} est close.`;
      }
      break;
    case G.GENRE_REJOINDRE:
      texte = accepter ? `${titres} est aussi rangé dans ${arrivee}.`
        : `La demande de ${qui} est refusée : rien n'est rangé.`;
      break;
    case G.GENRE_RENDRE:
      texte = accepter ? `${titres} est rendu à ${arrivee}, avec tout son travail.`
        : `${titres} reste au fonds. La demande de ${qui} est close.`;
      break;
    default:
      texte = "Réponse enregistrée.";
  }
  if (!enAttente) AF.ouverts.delete(id);
  await fdApres(enAttente ? `#fd-demande-msg-${id}` : $("#af-msg"), texte,
                d.genre === G.GENRE_PROJET && accepter);
  const cible = enAttente ? $(`#fd-demande-${id}`) : $("#afaire-titre");
  if (cible) cible.focus();
}

async function fdRendreCopie(albumId, docId) {
  const sel = $(`#fd-rendre-${albumId}`), ligne = $(`#fd-doc-msg-${docId}`);
  if (!sel) return;
  const nom = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text : "";
  try {
    await apiSend("PUT", `/api/albums/${albumId}/collections/${sel.value}`);
  } catch (e) { fdMsg(ligne, e.message || "Échec", true); return; }
  await fdApres(`#fd-doc-msg-${docId}`, `Copie rendue à « ${nom} », avec tout son travail.`);
  const t = $("#fd-fiche-titre");
  if (t) t.focus();
}

async function fdDetruire(docId) {
  const d = FD.documents.find((x) => x.id === docId);
  if (!d) return;
  const titre = BDSuppression.titreDocument(d), ligne = $(`#fd-doc-msg-${docId}`);
  if (!confirm(BDSuppression.confirmationDetruireDocument(titre, d.copies.length))) return;
  try {
    for (const c of d.copies) await apiSend("DELETE", `/api/albums/${c.album_id}`);
  } catch (e) { fdMsg(ligne, e.message || "Échec", true); return; }
  FD.sel = null;
  FD.vueFiche = false;
  fdEcrireAdresse(false);
  await fdApres($("#fd-msg"), `« ${titre} » : détruit, avec ses images et tout le travail `
    + "fait dessus.");
  $("#fonds-titre").focus();
}

function fdOuvrirImporter(ouvrir) {
  FD.importer = ouvrir;
  FD.vueFiche = ouvrir || FD.sel !== null;
  fdTaireSauf(null);
  fdRendreControles();
  fdRendreFiche();
  const cible = ouvrir ? $("#fd-titre") : $("#fd-importer-ouvrir");
  if (cible) cible.focus();
}

/* « Importer au fonds » : l'album naît sans collection ni projet (`au_fonds`), puis ses
   planches entrent une à une — la route d'import d'un album, la même que l'Atelier. Un
   fichier refusé n'arrête pas les suivants ; le bilan dit ce qui est entré, et la fiche du
   document qui vient de naître s'ouvre. */
async function fdImporter() {
  const ligne = $("#fd-importer-msg"), bouton = $("#fd-importer");
  const titre = $("#fd-titre").value.trim();
  const fichiers = [...$("#fd-fichiers").files];
  if (!titre) { fdMsg(ligne, "Donnez un titre à l'album.", true); $("#fd-titre").focus(); return; }
  if (bouton.disabled) return;
  bouton.disabled = true;
  let album;
  try { album = await apiSend("POST", "/api/albums", { titre, au_fonds: true }); }
  catch (e) { fdMsg(ligne, e.message || "Échec", true); bouton.disabled = false; return; }
  const refus = [];
  for (const f of fichiers) {
    const fd = new FormData();
    fd.append("file", f);
    try {
      const r = await fetch(`/api/albums/${album.id}/import`,
        { method: "POST", headers: { "X-BD-Requete": "1" }, body: fd });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    } catch (e) { refus.push(`${f.name} (${e.message})`); }
  }
  bouton.disabled = false;
  const entrees = fichiers.length - refus.length;
  await fdCharger();
  const doc = FD.documents.find((d) => d.copies.some((c) => c.album_id === album.id));
  FD.importer = false;
  if (doc) { FD.sel = doc.id; FD.vueFiche = true; fdEcrireAdresse(true); }
  fdRendreControles();
  fdRendreListe();
  fdRendreFiche();
  const msg = doc ? $(`#fd-doc-msg-${doc.id}`) : $("#fd-msg");
  fdMsg(msg, `« ${titre} » est au fonds, appelé par personne : `
    + `${pjPluriel(entrees, "planche")} importée${entrees > 1 ? "s" : ""}.`
    + (refus.length ? ` Refusé : ${refus.join(", ")}.` : ""));
  if (refus.length) msg.classList.add("alerte");
  const t = $("#fd-fiche-titre");
  if (t) t.focus();
}

function fdDemarrer() {
  fdLireAdresse();
  const racine = $("#fd");
  racine.addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (!b || !racine.contains(b)) return;
    if (b.dataset.fdDoc) { fdOuvrir(Number(b.dataset.fdDoc), true); return; }
    if (b.dataset.fdEtat) { FD.etat = b.dataset.fdEtat; fdRendreControles(); fdRendreListe(); return; }
    if (b.dataset.fdTri) { FD.tri = b.dataset.fdTri; fdRendreControles(); fdRendreListe(); return; }
    if (b.dataset.fdRetour) {
      FD.vueFiche = false;
      fdRendreControles();
      const courant = document.querySelector('#fd-objets [aria-current="true"]');
      (courant || $("#fd-filtre")).focus();
      return;
    }
    if (b.id === "fd-importer-ouvrir") { fdOuvrirImporter(true); return; }
    if (b.dataset.fdImporterAnnuler) { fdOuvrirImporter(false); return; }
    if (b.id === "fd-importer") { fdImporter(); return; }
    if (b.dataset.fdRepondre) { afAllerDemande(Number(b.dataset.fdRepondre)); return; }
    if (b.dataset.fdPrendre) {
      FD.prendre = Number(b.dataset.fdPrendre);
      fdTaireSauf(null);
      fdRendreFiche();
      const s = $("#fd-prendre-dest");
      if (s) s.focus();
      return;
    }
    if (b.dataset.fdPrendreAnnuler) {
      const id = FD.prendre;
      FD.prendre = null;
      fdRendreFiche();
      const r = document.querySelector(`#fd-fiche [data-fd-prendre="${id}"]`);
      if (r) r.focus();
      return;
    }
    if (b.dataset.fdPrendreOk) { fdPrendreDans(Number(b.dataset.fdPrendreOk)); return; }
    if (b.dataset.fdRendre) fdRendreCopie(Number(b.dataset.fdRendre), Number(b.dataset.fdDocDe));
    else if (b.dataset.fdDetruire) fdDetruire(Number(b.dataset.fdDetruire));
  });
  $("#fd-filtre").addEventListener("input", (ev) => { FD.filtre = ev.target.value; fdRendreListe(); });
  $("#fd-projet").addEventListener("change", (ev) => { FD.projet = ev.target.value; fdRendreListe(); });
  $("#fd-importeur").addEventListener("change", (ev) => { FD.importeur = ev.target.value; fdRendreListe(); });
  // La liste se parcourt aux FLÈCHES, comme celle de « Comptes et groupes » : un millier de
  // documents ne se parcourent pas à la tabulation.
  $("#fd-objets").addEventListener("keydown", (ev) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(ev.key)) return;
    const lignes = [...document.querySelectorAll("#fd-objets .fd-objet")];
    const i = lignes.indexOf(document.activeElement);
    if (i < 0 || !lignes.length) return;
    ev.preventDefault();
    const j = ev.key === "Home" ? 0 : ev.key === "End" ? lignes.length - 1
      : Math.max(0, Math.min(lignes.length - 1, i + (ev.key === "ArrowDown" ? 1 : -1)));
    lignes[j].focus();
  });
  return fdCharger();
}


/* ═══════════════════════════════════════════════════════════════════════════
   À faire (COL-3) — ce qui attend un geste, dans l'ordre où on l'attend

   L'ouverture de la page dès que quelque chose attend (décision de Hugo du 2026-10-16, sur
   maquette : « Tout ce qui est nécessaire. Là, tout est partout et c'est illisible »). Trois
   groupes, dans cet ordre : les DEMANDES — quelqu'un attend une réponse —, les ACCÈS à
   régler — les signaux d'« À regarder », hors les demandes —, l'INSTANCE. Le plus ancien
   d'abord : les demandes par leur date de dépôt ; les signaux n'en ont pas, et gardent
   l'ordre du serveur.

   ON RÉPOND À UNE DEMANDE SUR PLACE : la ligne se déplie — motif, certification, ce que
   d'autres y ont fait —, et « Détruire » ou « Garder » (« Supprimer le projet » pour un
   projet) partent d'ici. Les mots viennent de `lib/suppression.js`.

   CE BLOC NE POSE AUCUNE QUESTION À LUI : il lit ce que les blocs qui le nourrissent ont
   déjà lu, chacun gardé par SA route — le fonds (`GET /api/fonds`, puis `/api/demandes`),
   les comptes et groupes, le référent. Il se lève si l'un d'eux a répondu.
   ═══════════════════════════════════════════════════════════════════════════ */
const AF = {
  ouverts: new Set(),    // les demandes dépliées
  referent: null,        // l'état du référent, s'il a été lu (`absent`, `injoignable`, …)
};

function afTaireSauf(el) {
  document.querySelectorAll("#afaire-bloc .col-msg").forEach((l) => {
    if (l === el) return;
    l.textContent = "";
    l.classList.remove("erreur", "alerte");
  });
}

function afMsg(el, texte, erreur) {
  afTaireSauf(el);
  el.textContent = texte || "";
  el.classList.toggle("erreur", !!erreur);
}

/* Les demandes en attente, la plus ANCIENNE d'abord : quelqu'un attend depuis plus longtemps. */
function afDemandes() {
  return (FD.demandes || []).slice().sort((a, b) =>
    String(a.date_creation || "").localeCompare(String(b.date_creation || "")) || a.id - b.id);
}

/* Les signaux d'« À regarder » qui demandent de régler un accès : tous, sauf les demandes,
   qui ont leur groupe en tête, et les comptes JAMAIS VENUS — une information, pas un geste
   (maquette) : une quarantaine de comptes qui n'ont pas encore ouvert l'application
   rempliraient « À faire » pour toujours, et la page ne s'ouvrirait plus jamais ailleurs. */
const AF_INFORMATION = ["jamais_venu"];
function afSignaux() {
  return CG.donnees ? CG.donnees.a_regarder.filter((s) => s.signal !== "demande_en_attente"
    && !AF_INFORMATION.includes(s.signal)) : [];
}
function afInformations() {
  return CG.donnees ? CG.donnees.a_regarder.filter((s) => AF_INFORMATION.includes(s.signal)) : [];
}

/* Ce qui, de l'instance, attend un geste : un référent absent ou injoignable — l'adresse que
   lit une personne sans aucun accès. */
function afInstance() {
  if (AF.referent === "absent") return [{ texte: "Personne n'est désigné comme référent de l'instance" }];
  if (AF.referent === "injoignable") return [{ texte: "Le référent de l'instance n'a aucun contact déclaré" }];
  return [];
}

function afNombre() {
  return afDemandes().length + afSignaux().length + afInstance().length;
}

/* Le bloc se lève dès qu'un de ceux qui le nourrissent a répondu. */
function afDisponible() {
  return FD.lu || !!CG.donnees || AF.referent !== null;
}

function afRendre() {
  $("#afaire-bloc").hidden = !afDisponible();
  const n = afNombre();
  $("#vue-compte-afaire").textContent = n ? ` ${n}` : "";
  $("#vue-lien-afaire").classList.toggle("a-faire", n > 0);
  afRendreDemandes();
  afRendreAcces();
  afRendreInstance();
  $("#af-rien").hidden = n > 0 || FD.demandes === null;
  vueMajLiens();
}

function afRendreDemandes() {
  const liste = $("#af-demandes-liste");
  if (FD.lu && FD.demandes === null) {
    $("#af-demandes").hidden = false;
    liste.innerHTML = `<li class="col-note erreur">Les demandes n'ont pas pu être lues.</li>`;
    return;
  }
  const demandes = afDemandes();
  $("#af-demandes").hidden = !demandes.length;
  const actif = document.activeElement;
  const garde = actif && actif.dataset && actif.dataset.afDeplier ? actif.dataset.afDeplier : null;
  liste.innerHTML = demandes.map(afLigneDemande).join("");
  if (garde !== null) {
    const b = document.querySelector(`#af-demandes-liste [data-af-deplier="${CSS.escape(garde)}"]`);
    if (b) b.focus();
  }
}

/* UNE ligne par demande, quel qu'en soit le genre (COL-3, écran de la 3a, tranché par Hugo sur
   maquette le 2026-10-17) : son genre en tête, une couleur de tranche par genre (la classe
   `af-genre-…`), et, dépliée, SES mots et SES boutons — `BDSuppression.genreDemande` les
   donne. « Détruire / Garder » n'appartient qu'à la suppression d'un document ; un genre que
   l'écran ne connaît pas se lit, sans aucun bouton. */
function afLigneDemande(d) {
  const G = BDSuppression, genre = G.genreDemande(d);
  const ouvert = AF.ouverts.has(d.id);
  const msg = `<span id="fd-demande-msg-${d.id}" class="col-msg fd-ligne-msg muted small"
              role="status" aria-live="polite"></span>`;
  let gestes = "";
  if (d.genre === G.GENRE_DOCUMENT || d.genre === G.GENRE_PROJET) {
    gestes = `<div class="fd-gestes">
        <button type="button" class="danger" data-fd-accepter="${d.id}">${esc(genre.accepter)}</button>
        <button type="button" class="ghost" data-fd-refuser="${d.id}">${esc(genre.refuser)}</button>
        ${msg}</div>`;
  } else if (d.genre === G.GENRE_ENTREE) {
    const attente = (d.documents || []).filter((x) => !x.reponse).length;
    gestes = `<ul class="lf-lignes af-documents">${(d.documents || []).map((x) => {
      const e = G.etatLigne(x, d);
      return `<li><span class="af-doc-titre">${esc(x.titre || `document ${x.document_id}`)}</span>
        <span class="af-doc-gestes">${x.reponse
          ? `<span class="af-etat af-etat-${esc(e.code)}">${esc(e.libelle)}</span>`
          : `<button type="button" class="ghost small" data-fd-accepter="${d.id}"
               data-fd-document="${x.document_id}"
               aria-label="${esc(genre.accepter)} « ${esc(x.titre || "")} »">${esc(genre.accepter)}</button>
             <button type="button" class="ghost small" data-fd-refuser="${d.id}"
               data-fd-document="${x.document_id}"
               aria-label="${esc(genre.refuser)} « ${esc(x.titre || "")} »">${esc(genre.refuser)}</button>`}
        </span></li>`;
    }).join("")}</ul>
      <div class="fd-gestes">${attente ? `
        <button type="button" class="primary small" data-fd-accepter="${d.id}">${esc(
          G.toutAccepter(d))}</button>
        <button type="button" class="ghost small" data-fd-refuser="${d.id}">${esc(
          G.REFUSER_LE_RESTE)}</button>` : ""}
        ${msg}</div>`;
  } else if (genre.connu) {
    gestes = `<div class="fd-gestes">
        <button type="button" class="primary small" data-fd-accepter="${d.id}">${esc(genre.accepter)}</button>
        <button type="button" class="ghost small" data-fd-refuser="${d.id}">${esc(genre.refuser)}</button>
        ${msg}</div>`;
  } else {
    gestes = `<p class="col-note">L'écran ne sait pas répondre à ce genre de demande.</p>${msg}`;
  }
  const explication = G.explicationDemande(d);
  const detail = !ouvert ? "" : `<div class="af-detail" id="af-detail-${d.id}">
      ${d.motif ? `<p class="fd-motif">${esc(d.motif)}</p>` : ""}
      ${d.certifie_le ? `<p class="small fd-certif">${esc(G.certifiee(d))}</p>` : ""}
      ${explication ? `<p class="muted small af-explique">${esc(explication)}</p>` : ""}
      ${d.genre === G.GENRE_DOCUMENT ? (d.documents || []).map(fdTravailDesAutres).join("") : ""}
      ${gestes}
    </div>`;
  return `<li class="af-ligne fd-demande af-genre-${esc(genre.classe)}" id="fd-demande-${d.id}"
      tabindex="-1" data-genre="${esc(d.genre)}">
    <div class="af-quoi">
      <span class="af-genre-nom muted small">${esc(genre.libelle)}</span>
      <p class="fd-demande-texte">${esc(G.texteDemande(d))}</p>
      <p class="muted small fd-demande-contexte">${esc(G.contexteDemande(d))}</p>
    </div>
    <button type="button" class="ghost small" data-af-deplier="${d.id}" aria-expanded="${ouvert}"
      ${ouvert ? `aria-controls="af-detail-${d.id}"` : ""}>${ouvert ? "Replier" : "Répondre"}</button>
    ${detail}
  </li>`;
}

/* Sous une demande de suppression d'un document : ce que les AUTRES y ont fait (Hugo,
   2026-10-15) — qui, combien de gestes de chaque sorte, le dernier —, lu par le serveur à
   la source même de la règle de suppression, au moment de la lecture. Une demande dont le
   serveur n'a rien rendu (illisible) ne dit rien plutôt que de dire « personne ». */
function fdTravailDesAutres(doc) {
  const t = BDSuppression.travailDesAutres(doc);
  if (!t) return "";
  return `<div class="fd-autres">
    <p class="muted small">${esc(t.origine)}</p>
    ${t.vide ? `<p class="small">${esc(t.texteVide)}</p>`
      : `<p class="small fd-autres-titre">${esc(t.titre)}</p>
         <ul class="fd-autres-liste small">${t.lignes.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>`}
  </div>`;
}

function afRendreAcces() {
  const signaux = afSignaux();
  $("#af-acces").hidden = !signaux.length;
  const noms = cgNomsSignaux();
  $("#af-acces-liste").innerHTML = signaux.map((s, i) => {
    const c = BDComptes.cibleSignal(s);
    return `<li class="af-ligne"><div class="af-quoi"><p>${esc(BDComptes.texteSignal(s, noms))}</p></div>
      ${c ? `<button type="button" class="ghost small" data-af-signal="${i}">Régler →</button>` : ""}</li>`;
  }).join("");
  // Les comptes jamais venus, à titre d'information : repliés, hors du compte de la vue.
  const infos = afInformations();
  $("#af-info").hidden = !infos.length;
  $("#af-info-titre").textContent = infos.length
    ? BDComptes.texteGroupeSignaux(infos[0].signal, infos.length) + " — à titre d'information"
    : "";
  $("#af-info-liste").innerHTML = infos.map((s, i) =>
    `<li>${BDComptes.cibleSignal(s) ? `<button type="button" class="lf-lien" data-af-info="${i}">${esc(
      BDComptes.texteSignal(s, noms))}</button>` : esc(BDComptes.texteSignal(s, noms))}</li>`).join("");
}

function afRendreInstance() {
  const lignes = afInstance();
  $("#af-instance").hidden = !lignes.length;
  $("#af-instance-liste").innerHTML = lignes.map((l) => `<li class="af-ligne"><div class="af-quoi">
      <p>${esc(l.texte)}</p></div>
      <button type="button" class="ghost small" data-af-instance="1">Voir →</button></li>`).join("");
}

/* Mène à la demande dans « À faire », dépliée, sous les yeux et sous le clavier — depuis
   « À regarder » ou la fiche d'un document. Une demande qu'on ne trouve plus a reçu sa
   réponse entre-temps : on relit, puis on le dit. */
async function afAllerDemande(id) {
  vueAller("afaire");
  if (!(FD.demandes || []).some((d) => d.id === id)) await fdCharger();
  if (!(FD.demandes || []).some((d) => d.id === id)) {
    afMsg($("#af-msg"), "Cette demande a déjà reçu sa réponse.");
    $("#afaire-titre").focus();
    return;
  }
  AF.ouverts.add(id);
  afRendreDemandes();
  const el = $(`#fd-demande-${id}`);
  el.scrollIntoView({ block: "center" });
  el.focus();
}

function afDemarrer() {
  $("#afaire-bloc").addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    if (b.dataset.afDeplier) {
      const id = Number(b.dataset.afDeplier);
      if (AF.ouverts.has(id)) AF.ouverts.delete(id); else AF.ouverts.add(id);
      afRendreDemandes();
    } else if (b.dataset.fdAccepter || b.dataset.fdRefuser) {
      const doc = b.dataset.fdDocument ? Number(b.dataset.fdDocument) : undefined;
      fdRepondre(Number(b.dataset.fdAccepter || b.dataset.fdRefuser),
                 b.dataset.fdAccepter ? BDSuppression.ACCEPTER : BDSuppression.REFUSER, doc);
    }
    else if (b.dataset.afSignal !== undefined || b.dataset.afInfo !== undefined) {
      const c = BDComptes.cibleSignal(b.dataset.afSignal !== undefined
        ? afSignaux()[Number(b.dataset.afSignal)] : afInformations()[Number(b.dataset.afInfo)]);
      if (!c) return;
      vueAller("comptes");
      cgAller(c.type, c.id, false);
    } else if (b.dataset.afInstance) {
      vueAller("instance");
      $("#referent-titre").focus();
    }
  });
}


/* ═══════════════════════════════════════════════════════════════════════════
   Les VUES (COL-3) — une page, cinq vues adressables

   Décision de Hugo du 2026-10-16, sur maquette : UNE page `/administration` dont la vue
   change selon son adresse (`?vue=…`) — À faire · Fonds · Projets · Comptes et groupes ·
   Instance —, et non cinq pages. Six blocs empilés ne tenaient plus : « Comptes et groupes »,
   le plus servi, descendait sous un fonds qui grossit.

   CHAQUE VUE POSE SA QUESTION À TRAVERS SES BLOCS. Un lien de vue ne se lève que si l'un de
   ses blocs a répondu (`hidden` levé par son propre chargement) : la garde reste celle des
   routes, jamais celle de ce menu. Seule « Instance » est là pour tous — les moteurs sont
   ouverts à tous. Une vue masque ses blocs par une CLASSE (`hors-vue`), jamais par `hidden`,
   que chaque bloc garde pour dire s'il a le droit de paraître.

   L'OUVERTURE : l'adresse si elle nomme une vue — ou un objet de « Comptes et groupes »
   (`?compte=…`, `?axe=…`), un document du fonds (`?document=…`), un projet (`?projet=…`) ; sinon « À faire » dès
   que quelque chose attend ; sinon la DERNIÈRE vue consultée, retenue par le navigateur
   (stockage local, lu sous try/catch) ; sinon « Comptes et groupes », la plus servie, ou ce
   qui reste. L'Administration TRAVERSE les projets : elle ne lit pas le projet courant.
   ═══════════════════════════════════════════════════════════════════════════ */
const VUES = ["afaire", "fonds", "projets", "comptes", "instance"];
const VUE_CLE = "bd-admin-vue";
const VUE = { courante: null, initiale: null, decidee: false };
const VUE_CLES_CG = ["axe", "tri", "compte", "groupe", "collection"];

function vueDeLAdresse() {
  const p = new URLSearchParams(location.search);
  if (VUES.includes(p.get("vue"))) return p.get("vue");
  if (VUE_CLES_CG.some((k) => p.has(k))) return "comptes";
  if (p.has("document")) return "fonds";
  if (p.has("projet")) return "projets";
  return null;
}

function vueDisponibles() {
  return {
    afaire: !$("#afaire-bloc").hidden,
    fonds: !$("#fonds-bloc").hidden,
    projets: !$("#projets-bloc").hidden || !$("#projets-ferme").hidden,
    comptes: !$("#cg-bloc").hidden,
    instance: true,
  };
}

function vueRetenue() {
  try { return localStorage.getItem(VUE_CLE); } catch (e) { return null; }
}

function vueRetenir(v) {
  if (!v || v === "afaire") return;
  try { localStorage.setItem(VUE_CLE, v); } catch (e) { /* stockage indisponible */ }
}

function vueOuverture() {
  const dispo = vueDisponibles();
  if (dispo.afaire && afNombre() > 0) return "afaire";
  const retenue = vueRetenue();
  if (VUES.includes(retenue) && dispo[retenue]) return retenue;
  return ["comptes", "projets", "afaire", "instance"].find((v) => dispo[v]);
}

/* Les liens de vue suivent ce que les blocs ont rendu ; une vue courante qui cesse d'être
   disponible cède la place à l'ouverture. */
function vueMajLiens() {
  const dispo = vueDisponibles();
  $("#vue-lien-afaire").hidden = !dispo.afaire;
  $("#vue-lien-fonds").hidden = !dispo.fonds;
  $("#vue-lien-projets").hidden = !dispo.projets;
  $("#vue-lien-comptes").hidden = !dispo.comptes;
  if (VUE.decidee && VUE.courante && !dispo[VUE.courante]) vueAfficher(vueOuverture());
}

function vueAfficher(v) {
  VUE.courante = v;
  document.querySelectorAll("#admin-body [data-dans-vue]").forEach((s) =>
    s.classList.toggle("hors-vue", s.dataset.dansVue !== v));
  document.querySelectorAll("#admin-vues [data-vue]").forEach((a) => {
    if (a.dataset.vue === v) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  $("#admin-body").scrollTop = 0;
  vueRetenir(v);
}

/* Changer de vue par le menu, ou depuis un autre bloc : l'adresse dit la vue et ce qu'elle
   montre — la fiche ouverte de « Comptes et groupes », du fonds ou des projets —, et rien
   d'autre. */
function vueAller(v) {
  if (v === VUE.courante) return;
  const p = new URLSearchParams();
  p.set("vue", v);
  if (v === "comptes") {
    new URLSearchParams(BDComptes.ecrireAdresse({ axe: CG.axe, tri: CG.tri, sel: CG.sel }, ""))
      .forEach((val, k) => p.set(k, val));
  }
  if (v === "fonds" && FD.sel !== null) p.set("document", String(FD.sel));
  if (v === "projets" && PJ.sel !== null && PJ.nomme) p.set("projet", String(PJ.sel));
  history.pushState(null, "", `${location.pathname}?${p}${location.hash}`);
  vueAfficher(v);
}

function vueDemarrer(chargements) {
  const nommee = vueDeLAdresse();
  VUE.initiale = nommee;
  // Avant la décision, aucun bloc ne paraît : la page ne s'ouvre pas sur une vue pour sauter
  // sur une autre une fois les blocs chargés. Une vue NOMMÉE s'affiche tout de suite.
  vueAfficher(nommee || "");
  $("#admin-vues").addEventListener("click", (ev) => {
    const a = ev.target.closest("a[data-vue]");
    if (!a || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button) return;
    ev.preventDefault();
    vueAller(a.dataset.vue);
  });
  window.addEventListener("popstate", () => {
    const v = vueDeLAdresse() || VUE.initiale;
    fdLireAdresse();
    if (FD.lu) { fdRendreControles(); fdRendreListe(); fdRendreFiche(); }
    pjLireAdresse();
    if (PJ.lu) pjRendre();
    if (v && v !== VUE.courante && vueDisponibles()[v]) vueAfficher(v);
  });
  Promise.allSettled(chargements).then(() => {
    VUE.decidee = true;
    const dispo = vueDisponibles();
    if (!nommee || !dispo[nommee]) {
      VUE.initiale = vueOuverture();
      vueAfficher(VUE.initiale);
    }
    vueMajLiens();
  });
}


/* ── Moteurs (SANTE-1) — la présence n'est pas le fonctionnement ───────────────────
   Le panneau qui rend le contrôle PROFOND atteignable : il existait depuis `ed17b32`,
   mais il fallait connaître `?profond=1` et l'appeler à la main — ce qu'un opérateur sans
   accès shell, seul public de la question, ne découvrira jamais tout seul.

   La RÈGLE d'affichage (présent ≠ opérationnel, absent ≠ en panne) vit dans
   `static/lib/sante.js`, pure et testée sous Node : elle croise deux réponses du serveur,
   et c'est le genre de logique qu'un test lisant le source déclare couverte sans l'être.
   Ici, il ne reste que du DOM. */
const SANTE_ETAT = { rapide: null, profond: null };

function santeMsg(texte, erreur) {
  const el = $("#sante-msg");
  el.textContent = texte || "";
  el.classList.toggle("erreur", !!erreur);
}

function santeRendu() {
  $("#sante-body").innerHTML = BDSante.MOTEURS.map((m) => {
    const e = BDSante.etat(SANTE_ETAT.rapide, SANTE_ETAT.profond, m);
    return `<div class="sante-ligne">
      <div class="sante-tete">
        <b>${esc(m.nom)}</b>
        <span class="sante-etat sante-${esc(e.etat)}">${esc(e.mot)}</span>
      </div>
      <p class="muted small sante-note">${esc(m.role)} · ${esc(e.note)}</p>
    </div>`;
  }).join("");
}

async function santeCharger() {
  try {
    SANTE_ETAT.rapide = await apiGet("/api/sante");
  } catch (e) {
    $("#sante-body").innerHTML = `<p class="col-note">${esc(e.message)}</p>`;
    return;
  }
  santeRendu();
}

/* Occupé, mais TOUJOURS FOCUSABLE — `aria-disabled` et non `disabled`, et ce n'est pas
   du purisme. Désarmer pour de bon un bouton qui porte le FOCUS le fait rendre au
   <body> : la modale cesse alors de piéger Tab et Échap ne la ferme plus, pendant les
   quinze secondes que dure l'import de torch. Une modale devient un cul-de-sac au
   clavier sans qu'aucune exception ne soit levée, et l'audit axe n'y voit rien — il
   photographie un écran, il n'appuie sur aucune touche. C'est un test de bout en bout
   qui l'a trouvé, en cherchant autre chose. */
function santeOccupe(occupe) {
  const b = $("#sante-eprouver");
  b.setAttribute("aria-busy", occupe ? "true" : "false");
  if (occupe) b.setAttribute("aria-disabled", "true");
  else b.removeAttribute("aria-disabled");
}

const santeEnCours = () => $("#sante-eprouver").getAttribute("aria-disabled") === "true";

/* Le contrôle profond, sur clic et JAMAIS au chargement : c'est un acte coûteux (torch
   en mémoire), et une route de santé qui charge les moteurs pour répondre n'est plus une
   route de santé. Le bouton s'annonce occupé pendant l'appel — le premier peut durer une
   minute, et rien à l'écran ne le dirait autrement. */
async function santeEprouver() {
  if (santeEnCours()) return;        // `aria-disabled` n'empêche pas le clic : nous, si
  santeOccupe(true);
  santeMsg("Chargement réel des moteurs… le premier appel peut durer une minute.");
  try {
    const d = await apiGet("/api/sante?profond=1");
    SANTE_ETAT.rapide = d;
    SANTE_ETAT.profond = d.profond || {};
    santeRendu();
    const bilan = BDSante.bilan(SANTE_ETAT.rapide, SANTE_ETAT.profond);
    santeMsg(bilan.texte, bilan.erreur);
  } catch (e) {
    santeMsg(e.message, true);
  } finally {
    santeOccupe(false);
  }
}


function setup() {
  // Pas de modale à ouvrir : les blocs SONT la page. On charge donc d'emblée — SEPT
  // requêtes, dont TROIS (`/api/version`, `/api/referent` et `/api/comptes-et-groupes`)
  // peuvent légitimement être refusées, chacune masquant son propre bloc et rien d'autre ;
  // la cinquième, `/api/droits`, accompagne les comptes (AUTH-12, étape 3). Les deux
  // dernières sont celles des projets (COL-3) : `/api/projets`, et `/api/collections`, qui
  // revient ici pour NOMMER les collections de chaque projet. Le module monté dans la fiche
  // d'un projet lit ensuite les siennes.
  //
  // Une HUITIÈME part quand `/api/comptes-et-groupes` a répondu, et seulement alors :
  // `/api/collections` une seconde fois, pour « Comptes et groupes », qui y lit ce qu'on
  // peut RÉGLER (`administrable`, UX-16). Deux lectures de la même route, par deux blocs
  // qui ne partagent rien — celui des projets est à lui, et doit rester lisible à qui l'autre
  // est fermé. Et le panneau « Qui entre » monté dans la fiche d'une collection lit ensuite
  // SES deux routes, à chaque fiche ouverte.
  //
  // COL-3, tranche 2 — le FONDS en ajoute : `/api/fonds`, qui peut être refusé et ne masque
  // alors que son bloc ; puis, s'il a répondu, `/api/demandes`, et `/api/collections` une
  // TROISIÈME fois, pour « Rendre à… ». Trois blocs, trois lectures de la même route : aucun
  // ne doit tomber parce qu'un autre est fermé.
  //
  // Le compte est tenu à jour ICI parce que ce commentaire a déjà menti : il disait
  // « deux requêtes » depuis le premier jour, à trois lignes de la ligne qui le
  // contredisait (cf. plus bas). Un chiffre dans un commentaire est une affirmation
  // vérifiable, et il vieillit dans le sens rassurant.
  //
  // Les comptes se chargent ICI (`cgCharger()` depuis AUTH-12, `loadComptes()` avant
  // lui), et non depuis le chargement des collections où la vue des comptes a vécu
  // jusqu'au 2026-09-07. Elle y était nichée APRÈS le `return` du cas « aucune
  // collection », si bien qu'une portée sans collection escamotait la vue des comptes —
  // un bloc masqué par une condition qui ne le concerne pas, c'est-à-dire très exactement
  // le motif d'AUTH-4 que cette page existe pour fermer. Mesuré alors : sans collection,
  // la route des comptes n'était JAMAIS demandée par le navigateur.
  //
  // Le déménagement n'a pas créé le défaut, il l'a rendu ATTEIGNABLE : dans la modale de
  // la Bibliothèque, le chargement des collections était le geste d'ouverture, donc la nidification
  // ne se voyait pas et ne coûtait rien. C'est l'argument inverse de celui qu'on oppose
  // d'habitude aux déménagements.
  //
  // Le commentaire ci-dessus disait « deux requêtes » depuis le premier jour : il
  // décrivait l'intention et se lisait comme une description du fait. Qui cherchait dans
  // `setup()` si les comptes se chargeaient d'emblée y trouvait « oui », à trois lignes de
  // la ligne qui disait le contraire.
  //
  // COL-3 — les VUES n'ajoutent aucune requête : « À faire » lit ce que les autres blocs ont
  // lu, et la vue d'ouverture se décide quand tous ont répondu (`vueDemarrer`).
  afDemarrer();
  // L'adresse d'abord : le premier rendu ouvre directement l'axe et la fiche qu'elle nomme.
  cgLireAdresse();
  cgInstaller();
  const chargements = [
    loadVersion(),
    // AUTH-12 étape 4 : cinquième requête, qui peut elle aussi être légitimement refusée et
    // ne masque que son propre bloc.
    loadReferent(),
    cgCharger(),
    pjDemarrer(),                  // COL-3 : le bloc des projets, à lui (cf. `PJ`)
    fdDemarrer(),                  // COL-3, tranche 2 : le fonds, réservé par sa route
    santeCharger(),
  ];
  vueDemarrer(chargements);
  // SANTE-1 : éprouver reste un geste SÉPARÉ et volontaire — le contrôle profond importe
  // les moteurs pour de bon, quelques secondes et quelques centaines de mégaoctets.
  $("#sante-eprouver").onclick = santeEprouver;
}

setup();
