/* Administration (UX-10) — le lieu des gestes qui portent sur l'INSTANCE.

   QUATRE blocs, et aucun n'est une affaire de Bibliothèque : la version servie dit quel
   commit tourne ici (INFRA-10), le référent de l'instance dit à qui s'adresser quand on
   n'a accès à rien (AUTH-12, étape 4), les comptes et groupes disent qui utilise l'instance
   et par quoi il entre (AUTH-12, qui remplace la vue des comptes d'AUTH-7), les moteurs
   disent si l'instance sait encore reconnaître quelque chose. Les moteurs et les accès vivaient dans
   `/corpus` par ACCRÉTION — c'était le seul écran administratif, et tout ce qui y
   ressemblait s'y est ajouté —, donc les atteindre depuis la Visionneuse demandait de
   quitter son travail.

   LES ACCÈS SONT REPARTIS le 2026-09-17 (AUTH-12, décision 2 (b)) : qui entre dans UNE
   collection se règle dans SA fiche, dans la Bibliothèque. Ici ne reste que la vue
   TRANSVERSE — qui a accès à quoi, à travers toutes les collections — et « Régler qui
   entre » y mène.

   ILS ONT DÉMÉNAGÉ, ils ne sont pas dupliqués. Décision de l'équipe le 2026-09-07 : deux
   portes vers la même pièce se paient toujours, l'une des deux vieillit, et c'est celle
   qu'on ne regarde plus.

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

   IL NE MODIFIE RIEN, sauf la nature d'un compte (décision 1 (A) d'AUTH-12). Tout ce qui
   change un compte ou un groupe se fait dans l'annuaire ; tout ce qui change un accès se
   fait dans la fiche de la collection, dans la Bibliothèque (étape 3).

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
  return `<span class="cg-puce${genre ? " " + genre : ""}">${esc(texte)}</span>`;
}

/* Un lien qui ouvre un objet du bloc. Un BOUTON et non un <a> : il ne quitte pas la page,
   et `data-type`/`data-id` suffisent à la délégation d'événements. */
function cgLien(type, id, texte) {
  return `<button type="button" class="cg-lien" data-type="${type}" `
    + `data-id="${esc(String(id))}">${esc(texte)}</button>`;
}

function cgLienAnnuaire(texte) {
  const href = BDComptes.lienAnnuaire(CG.donnees.annuaire.lien);
  if (!href) return "";
  return `<a class="cg-ext" href="${esc(href)}" target="_blank" rel="noopener">${esc(texte)}`
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
  const description = await droits;
  CG.droits = BDDroits.estValide(description) ? description : null;
  CG.donnees = d;
  CG.index = {
    comptes: new Map(d.comptes.map((c) => [c.login, c])),
    groupes: new Map(d.groupes.map((g) => [g.nom, g])),
    collections: new Map(d.collections.map((c) => [c.id, c])),
  };
  cgRendre();
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

function cgRendre() {
  cgRendreAnnuaire();
  cgRendreControles();
  cgRendreSignaux();
  cgRendreListe();
  cgRendreFiche();
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
  $("#cg").classList.toggle("cg--fiche", CG.vueFiche && CG.sel !== null);
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
  const noms = {
    collections: Object.fromEntries(d.collections.map((c) => [c.id, c.nom])),
    comptes: Object.fromEntries(d.comptes.filter((c) => c.nom).map((c) => [c.login, c.nom])),
  };
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
    return `<li><button type="button" class="cg-objet" data-type="${type}" `
      + `data-id="${esc(String(id))}"${courant ? ' aria-current="true"' : ""}>`
      + `<span class="cg-nom">${esc(BDComptes.nomLu(o, CG.axe))}</span>`
      + `<span class="cg-etat${e.alerte ? " alerte" : ""}">${esc(e.texte)}</span></button></li>`;
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
    html = `<li class="cg-vide muted small">${CG.filtre.trim()
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
  const retour = `<button type="button" class="ghost small cg-retour" data-cg-retour="1">← Liste</button>`;
  if (CG.sel === null) {
    const [un] = CG_NOMS_AXE[CG.axe];
    box.innerHTML = `<p class="muted cg-accueil">Choisissez un ${un} dans la liste pour ouvrir
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
    groupes = `<div class="cg-pastilles">${c.groupes.length
      ? c.groupes.map((g) => cgLien("groupe", g, g)).join("")
      : `<span class="muted small">Aucun groupe.</span>`}
      ${c.dans_annuaire === true ? cgLienAnnuaire("Modifier dans l'annuaire") : ""}</div>`;
  }

  const lignes = c.collections.map((x) => `<li>${cgLien("collection", x.id, x.nom)}
    <span class="muted small">${esc(cgAccesLu(x))} — ${x.par === "groupe"
      ? `par le groupe ${cgLien("groupe", x.groupe, x.groupe)}` : "à son nom"}</span></li>`);
  let collections = "";
  if (c.administrateur === true) {
    collections += `<p class="col-note col-note-admin">Administrateur de l'instance : lit et
      écrit toute collection, sans figurer dans les accès.</p>`;
  }
  if (lignes.length) {
    collections += `<ul class="cg-lignes">${lignes.join("")}</ul>`;
  } else if (c.collections_completes && c.administrateur !== true) {
    collections += `<p class="cg-explique">Aucune collection ne lui est ouverte :
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
          « Qui entre » de chaque collection, dans la Bibliothèque.</li>
        ${suite}
      </ol></details>`;
  }

  return `<article class="cg-carte" aria-labelledby="cg-fiche-titre">
    <div class="cg-tete">
      <div>
        <h3 id="cg-fiche-titre" tabindex="-1">${esc(c.nom || c.login)}</h3>
        <p class="cg-sous"><span class="cg-login">${esc(c.login)}</span>
          ${vu ? `<span>vu le ${esc(vu)}</span>`
               : cgPuce("aucune connexion", c.usage === "annuaire" ? "" : "alerte")}
          ${puces.join("")}</p>
      </div>
      ${nature}
    </div>
    <section class="cg-section"><h4>Groupes</h4>${groupes}</section>
    <section class="cg-section"><h4>Collections</h4>${collections}</section>
    ${depart}
  </article>`;
}

function cgFicheGroupe(g) {
  const puces = [];
  if (g.dans_annuaire === false) puces.push(cgPuce("absent de l'annuaire", "rouge"));
  if (g.administrateur === true) puces.push(cgPuce("groupe d'administration"));
  if (g.role_annuaire === true) puces.push(cgPuce("rôle de l'annuaire"));

  const ouvertes = g.collections.map((x) => `<li>${cgLien("collection", x.id, x.nom)}
    <span class="muted small">${esc(cgAccesLu(x))}</span></li>`);
  let collections = g.administrateur === true
    ? `<p class="col-note col-note-admin">Ses membres lisent et écrivent toute collection,
        sans figurer dans les accès.</p>` : "";
  collections += ouvertes.length ? `<ul class="cg-lignes">${ouvertes.join("")}</ul>`
                                 : `<p class="muted small">Aucune.</p>`;
  // Arrivé avec l'étape 3 (AUTH-12) : la collection choisie s'ouvre dans la Bibliothèque,
  // sur « Qui entre », ce groupe déjà choisi dans la ligne d'ajout. Le geste se FAIT là-bas,
  // par qui possède la collection — cette fiche n'accorde rien.
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
    membres = `<p class="cg-explique">Ce groupe n'est pas dans l'annuaire : aucun compte n'en
      est membre, et ses accès n'ouvrent rien à personne.</p>`;
  } else if (g.membres === null || g.membres === undefined) {
    membres = `<p class="muted small">${esc(cgInconnu("ses membres"))}</p>`;
  } else if (!g.membres.length) {
    membres = `<p class="muted small">Aucun membre.</p>`;
  } else {
    const comptes = g.membres.map((l) => CG.index.comptes.get(l) || { login: l, nom: null });
    const jamais = comptes.filter((c) => !c.derniere_vue && c.usage !== "annuaire").length;
    if (jamais) titreMembres += ` — ${jamais} jamais ${jamais > 1 ? "venus" : "venu"}`;
    membres = `<ul class="cg-lignes">${BDComptes.trier(comptes, "comptes", "alpha").map((c) => {
      const vu = BDComptes.dateCourte(c.derniere_vue);
      return `<li>${cgLien("compte", c.login, c.nom || c.login)}${vu
        ? `<span class="muted small">vu le ${esc(vu)}</span>`
        : cgPuce("aucune connexion", c.usage === "annuaire" ? "" : "alerte")}</li>`;
    }).join("")}</ul>`;
  }

  return `<article class="cg-carte" aria-labelledby="cg-fiche-titre">
    <div class="cg-tete">
      <div>
        <h3 id="cg-fiche-titre" tabindex="-1">${esc(g.nom)}</h3>
        <p class="cg-sous">${g.nb_comptes !== null && g.nb_comptes !== undefined
          ? `<span>${g.nb_comptes} ${g.nb_comptes > 1 ? "comptes" : "compte"}</span>` : ""}
          ${puces.join("")}
          ${g.dans_annuaire === true ? cgLienAnnuaire("Défini dans l'annuaire") : ""}</p>
      </div>
    </div>
    <section class="cg-section"><h4>Collections ouvertes</h4>${collections}</section>
    <section class="cg-section"><h4>${esc(titreMembres)}</h4>${membres}</section>
  </article>`;
}

function cgFicheCollection(c) {
  const puces = [];
  const diffusion = BDComptes.diffusionLue(c.statut_diffusion);
  if (diffusion) puces.push(cgPuce(diffusion));
  if (c.repli) puces.push(cgPuce("collection de repli"));
  if ((c.signaux || []).includes("sans_proprietaire")) puces.push(cgPuce("sans propriétaire", "rouge"));
  if ((c.signaux || []).includes("proprietaire_absent")) {
    puces.push(cgPuce("propriétaire absent de l'annuaire", "rouge"));
  }
  const modif = BDComptes.dateCourte(c.derniere_modification);

  const acces = (c.acces || []).map((a) => {
    const groupe = a.par === "groupe";
    const nom = groupe ? a.groupe : a.login;
    const objet = groupe ? CG.index.groupes.get(nom) : CG.index.comptes.get(nom);
    const absent = objet && objet.dans_annuaire === false
      ? cgPuce("absent de l'annuaire", "rouge") : "";
    return `<li><span><span aria-hidden="true">${groupe ? "👥" : "👤"}</span>
      <span class="sr-only">${groupe ? "groupe" : "compte"}</span>
      ${cgLien(groupe ? "groupe" : "compte", nom, nom)} ${absent}</span>
      <span class="muted small">${esc(cgAccesLu(a))}</span></li>`;
  });

  return `<article class="cg-carte" aria-labelledby="cg-fiche-titre">
    <div class="cg-tete">
      <div>
        <h3 id="cg-fiche-titre" tabindex="-1">${esc(c.nom)}</h3>
        <p class="cg-sous"><span>${c.nb_albums} ${c.nb_albums > 1 ? "albums" : "album"}</span>
          ${modif ? `<span>modifiée le ${esc(modif)}</span>` : ""}
          ${puces.join("")}</p>
      </div>
    </div>
    <section class="cg-section"><h4>Qui entre</h4>
      ${acces.length ? `<ul class="cg-lignes">${acces.join("")}</ul>`
        : `<p class="muted small">Personne : seuls les administrateurs de l'instance la
            voient.</p>`}
      <p><a class="cg-regler" href="/corpus?collection=${c.id}">Régler qui entre</a></p>
      <p class="col-note">Les accès se lisent ici ; ils se règlent dans la fiche de la
        collection, dans la Bibliothèque.</p>
    </section>
  </article>`;
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

/* « Ouvrir une collection à ce groupe… » : la Bibliothèque, adressée sur la collection
   choisie et ce groupe (`?collection=…&groupe=…`). */
function cgOuvrirA(groupe) {
  const id = $("#cg-ouvrir-a").value;
  location.href = `/corpus?collection=${encodeURIComponent(id)}`
    + `&groupe=${encodeURIComponent(groupe)}`;
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
  // Pas de modale à ouvrir : les blocs SONT la page. On charge donc d'emblée — CINQ
  // requêtes, dont TROIS (`/api/version`, `/api/referent` et `/api/comptes-et-groupes`)
  // peuvent légitimement être refusées, chacune masquant son propre bloc et rien d'autre ;
  // la cinquième, `/api/droits`, accompagne les comptes (AUTH-12, étape 3). La liste des
  // collections n'est plus demandée ici : les accès sont partis dans la Bibliothèque.
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
  loadVersion();
  // AUTH-12 étape 4 : cinquième requête, qui peut elle aussi être légitimement refusée et
  // ne masque que son propre bloc.
  loadReferent();
  // L'adresse d'abord : le premier rendu ouvre directement l'axe et la fiche qu'elle nomme.
  cgLireAdresse();
  cgInstaller();
  cgCharger();
  santeCharger();
  // SANTE-1 : éprouver reste un geste SÉPARÉ et volontaire — le contrôle profond importe
  // les moteurs pour de bon, quelques secondes et quelques centaines de mégaoctets.
  $("#sante-eprouver").onclick = santeEprouver;
}

setup();
