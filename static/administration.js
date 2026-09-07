/* Administration (UX-10) — le lieu des gestes qui portent sur l'INSTANCE.

   Trois blocs, et aucun n'est une affaire de Bibliothèque : les collections décident qui
   voit quoi dans tout le corpus, la vue des comptes dit ce que chaque login a laissé, les
   moteurs disent si l'instance sait encore reconnaître quelque chose. Ils vivaient dans
   `/corpus` par ACCRÉTION — c'était le seul écran administratif, et tout ce qui y
   ressemblait s'y est ajouté —, donc les atteindre depuis la Visionneuse demandait de
   quitter son travail.

   ILS ONT DÉMÉNAGÉ, ils ne sont pas dupliqués. Décision de l'équipe le 2026-09-07 : deux
   portes vers la même pièce se paient toujours, l'une des deux vieillit, et c'est celle
   qu'on ne regarde plus.

   ET CE NE SONT PLUS DES MODALES. Une page est un lieu : les trois blocs sont là, lisibles
   ensemble, sans piège à focus ni Échap à gérer. `dialog.js` ne sert donc plus ici.

   LA GARDE RESTE SUR L'ACTE, JAMAIS SUR L'ÉCRAN QUI LE CONTIENT. C'est la condition posée
   par UX-10, et elle vient d'une erreur réelle : dans AUTH-4, le référent d'une collection
   — une simple ADRESSE — s'est retrouvé derrière la garde du PARTAGE parce qu'il vivait
   dans ce panneau-là, donc lisible du seul propriétaire. Ici, chaque bloc pose SA question :
   les collections sont filtrées par la portée du serveur, la vue des comptes n'apparaît que
   si `GET /api/comptes` répond, et les moteurs sont ouverts à tous — regarder si l'OCR
   fonctionne n'est pas un pouvoir. La page, elle, ne garde rien. */

/* ═══════════════════════════════════════════════════════════════════════════
   Collections (AUTH-3) — espaces de travail : créer, partager, ranger

   AUTH-2 avait fait le cloisonnement, pas son administration : `collection_acces` ne se
   remplissait qu'en SQL à la main. Cet écran est ce qui rend le reste utilisable — sans
   lui, tout le travail de routes reste du curl.

   Trois niveaux, et le troisième est la nouveauté : lecture · écriture · PROPRIÉTAIRE.
   Écrire, c'est annoter ; posséder, c'est décider qui d'autre entrera.
   ═══════════════════════════════════════════════════════════════════════════ */
const COL_NIVEAUX = [["lecture", "Lecture"], ["ecriture", "Écriture"],
                     ["proprietaire", "Propriétaire"]];

function colMsg(texte, erreur) {
  const el = $("#col-msg");
  el.textContent = texte || "";
  el.classList.toggle("erreur", !!erreur);
}

/* Les refus du serveur sont RENDUS, jamais avalés. Les deux cas d'AUTH-3 (dernier
   propriétaire, dernière collection) sont des 409 qui nomment un ÉTAT INTERDIT et non un
   droit manquant : les remplacer par un « échec » générique ferait croire à un bug. */
async function colTenter(fn) {
  try { await fn(); colMsg(""); return true; }
  catch (e) { colMsg(e.message || "Échec", true); return false; }
}

function niveauOptions(courant) {
  return COL_NIVEAUX.map(([v, l]) =>
    `<option value="${v}"${v === courant ? " selected" : ""}>${l}</option>`).join("");
}

/* DROIT-1 — ce que la date d'embargo raconte, en clair.

   L'application ne lève JAMAIS un embargo toute seule : une date qui passe dit que le
   délai a couru, pas que les droits sont acquis. Mais se taire aurait son propre coût —
   un embargo échu que personne ne remarque garde un corpus fermé par inertie, ce qui
   trahit l'orientation open-science aussi sûrement qu'une fuite trahit les droits.

   Le libellé PORTE le sens ; la couleur ne fait que le renforcer (WCAG 1.4.1). */
function colEmbargo(c) {
  const date = c.date_embargo || "";
  if (c.embargo === "echu")
    return [`Embargo échu`, "est-echu",
            `L'embargo est échu depuis le ${date}, et la collection reste déclarée `
            + `« ${c.statut_diffusion || "sans régime"} ». L'application ne la publie pas `
            + `pour autant : si les droits sont acquis, déclarez-la « public ».`];
  if (c.embargo === "illisible")
    return [`Embargo : date illisible`, "est-echu",
            `« ${date} » n'est pas une date lisible (attendu AAAA-MM-JJ). Par précaution, `
            + `les scans ne sortent pas tant qu'elle ne l'est pas.`];
  if (c.embargo === "pendant")
    return [`Embargo jusqu'au ${date}`, "",
            c.statut_diffusion === "public"
              ? `La collection est déclarée « public », mais l'embargo court jusqu'au `
                + `${date} : les scans ne sortiront pas avant cette date.`
              : `L'embargo court jusqu'au ${date}. Le travail interne n'en est pas `
                + `affecté : seule la publication l'est.`];
  return null;
}

/* Une collection = un <details>. Repliée, elle dit son nom, son volume et MON niveau ;
   dépliée, elle montre qui a accès — mais seulement si je peux l'administrer, la liste
   des membres d'une étude étant une donnée sur des personnes. */
function colItem(c) {
  const d = document.createElement("details");
  d.className = "col-item";
  d.dataset.id = String(c.id);
  // « Propriétaire » ne s'affiche qu'à un vrai propriétaire : le dire à un administrateur
  // lui ferait croire à un lien personnel avec une collection qui n'est pas la sienne.
  const badge = c.mon_niveau
    ? `<span class="col-niveau${c.mon_niveau === "proprietaire" ? " est-proprietaire" : ""}">`
      + `${COL_NIVEAUX.find((n) => n[0] === c.mon_niveau)[1]}</span>`
    : (c.administrable ? `<span class="col-niveau">Administrateur</span>` : "");
  const emb = colEmbargo(c);
  d.innerHTML = `
    <summary>
      <span class="col-nom">${esc(c.nom)}</span>
      <span class="muted small">${c.nb_albums} album(s)</span>
      ${badge}
      ${emb ? `<span class="col-embargo ${emb[1]}" title="${esc(emb[2])}">${esc(emb[0])}</span>`
            : ""}
    </summary>
    <div class="col-detail"></div>`;
  d.addEventListener("toggle", () => { if (d.open) colDetail(d, c); });
  return d;
}

/* AUTH-4 — le fait que la liste des accès taisait.

   `_acces_de()` ne lit que `collection_acces`, où un administrateur d'instance ne figure
   sur AUCUNE ligne : sa portée court-circuite la table en amont (`clause_album()` rend
   « 1 » quand elle est totale). La liste affichait donc trois noms là où quatre personnes
   lisent — sur un écran qui protège soigneusement cette liste au motif qu'elle parle de
   personnes. Ce n'est pas un défaut d'autorisation, c'est un défaut de DÉCLARATION : le
   pouvoir est inévitable dans un système auto-hébergé, son invisibilité ne l'est pas. */
function colAdminNote() {
  const g = (MOI.groupes_admin || []);
  if (!g.length) return "";
  // Formulée sans « ci-dessus » : les deux branches de `colDetail` l'affichent, et le
  // participant non propriétaire n'a AUCUNE liste d'accès sous les yeux. Un renvoi à ce
  // qui n'est pas là est une petite fausseté, mais c'est la même que celle qu'AUTH-4
  // corrige — un écran qui parle d'autre chose que de ce qu'il montre.
  return `<p class="col-note col-note-admin">Les administrateurs de l'instance
    (${g.map(esc).join(", ")}) lisent et écrivent <strong>toute</strong> collection, sans
    figurer dans aucune liste d'accès. Chacun de leurs actes est nommé au journal de
    provenance.</p>`;
}

/* Le référent, en LECTURE. Le contact s'affiche en TEXTE et non en lien, contrairement au
   référent d'instance du bandeau (`theme.js`) : celui-là vient de l'environnement, donc de
   qui déploie, tandis que celui-ci est saisi par un propriétaire de collection. Plutôt que
   de recopier ici l'autorisation de schémas — deux listes qui divergeraient un jour —, on
   n'ouvre pas la porte du tout : un `href` est la seule chose qui rende `javascript:`
   dangereux, et une adresse reste lisible sans être cliquable. */
function colReferentLu(c) {
  const nom = (c.referent_nom || "").trim();
  const contact = (c.referent_contact || "").trim();
  if (!nom && !contact) return "";
  return `<p class="col-note col-note-referent">Référent de cette collection :
    <strong>${esc(nom || contact)}</strong>${nom && contact ? ` — ${esc(contact)}` : ""}.</p>`;
}

async function colDetail(d, c) {
  const box = d.querySelector(".col-detail");
  if (!c.administrable) {
    // Le participant NON propriétaire est celui à qui AUTH-4 sert le plus, et le premier
    // jet le laissait sortir d'ici les mains vides : le référent et la déclaration
    // vivaient tous deux sous ce `return`, donc visibles du seul propriétaire — celui qui
    // les a écrits. DÉSIGNER un référent engage la collection et reste au propriétaire ;
    // le LIRE est le geste de quelqu'un qui a une question. Deux droits distincts qu'une
    // seule garde confondait.
    box.innerHTML = `<p class="col-note">Vous participez à cette collection sans la
      posséder : seul un propriétaire voit et modifie la liste des accès.</p>
      ${colReferentLu(c)}${colAdminNote()}`;
    return;
  }
  box.innerHTML = `<p class="col-note">Chargement…</p>`;
  let acces = [];
  try { acces = await apiGet(`/api/collections/${c.id}/acces`); }
  catch (e) { box.innerHTML = `<p class="col-note">${esc(e.message)}</p>`; return; }
  box.innerHTML = `
    <ul class="acces-liste">${acces.map((a) => `
      <li>
        <span class="acces-principal">${esc(a.principal)}</span>
        <span class="acces-genre">${a.genre === "groupe" ? "groupe" : "utilisateur"}</span>
        <select data-genre="${esc(a.genre)}" data-principal="${esc(a.principal)}"
                aria-label="Niveau de ${esc(a.principal)}">${niveauOptions(a.niveau)}</select>
        <button class="ghost small" data-retirer="1" data-genre="${esc(a.genre)}"
                data-principal="${esc(a.principal)}" type="button"
                title="Retirer l'accès de ${esc(a.principal)}">✕</button>
      </li>`).join("")}</ul>
    <div class="contrib-add">
      <input class="col-principal" placeholder="Login ou nom de groupe" autocomplete="off"
             aria-label="Login ou nom de groupe à qui accorder l'accès">
      <select class="col-genre" aria-label="Genre du principal">
        <option value="utilisateur">Utilisateur</option>
        <option value="groupe">Groupe</option>
      </select>
      <select class="col-niveau-neuf" aria-label="Niveau accordé">${niveauOptions("lecture")}</select>
      <button class="ghost small" data-accorder="1" type="button">+ Accorder</button>
    </div>
    <p class="col-note">Un accès se déclare par un NOM, pas par une personne vérifiée :
      l'application n'a aucun annuaire, elle lit les groupes dans les en-têtes du proxy à
      chaque requête. Un login mal orthographié n'ouvre rien — sans le dire.</p>
    ${colAdminNote()}
    <fieldset class="col-referent">
      <legend>Référent de cette collection</legend>
      <p class="col-note">À qui s'adresser pour cet espace. C'est une ADRESSE, pas un
        droit : la nommer n'accorde rien et ne retire rien.</p>
      <input class="col-ref-nom" placeholder="Nom lisible" autocomplete="off"
             aria-label="Nom du référent" value="${esc(c.referent_nom || "")}">
      <input class="col-ref-contact" placeholder="Courriel ou adresse de page"
             autocomplete="off" aria-label="Contact du référent"
             value="${esc(c.referent_contact || "")}">
      <button class="ghost small" data-referent="1" type="button">Enregistrer</button>
    </fieldset>
    <div class="modal-actions">
      <button class="ghost small" data-renommer="1" type="button">Renommer</button>
      <button class="ghost small" data-supprimer="1" type="button">Supprimer la collection</button>
    </div>`;

  const recharger = async () => { await loadCollections(); };
  const btnRef = box.querySelector("[data-referent]");
  if (btnRef) btnRef.onclick = async () => {
    // Champs vides = référent retiré, et c'est un geste légitime : on n'invente pas une
    // suppression séparée pour deux champs de texte.
    if (await colTenter(() => apiSend("PATCH", `/api/collections/${c.id}`, {
      referent_nom: box.querySelector(".col-ref-nom").value.trim(),
      referent_contact: box.querySelector(".col-ref-contact").value.trim(),
    }))) recharger();
  };
  box.querySelectorAll("[data-retirer]").forEach((b) => {
    b.onclick = async () => {
      const { genre, principal } = b.dataset;
      if (await colTenter(() => apiSend("DELETE",
          `/api/collections/${c.id}/acces/${genre}/${encodeURIComponent(principal)}`)))
        recharger();
    };
  });
  box.querySelectorAll("select[data-principal]").forEach((s) => {
    s.onchange = async () => {
      const { genre, principal } = s.dataset;
      // On recharge dans les DEUX cas : en cas de refus, le <select> afficherait sinon
      // un niveau que le serveur n'a pas accordé — l'écran mentirait sur l'état réel.
      await colTenter(() => apiSend("PUT", `/api/collections/${c.id}/acces`,
        { genre, principal, niveau: s.value }));
      recharger();
    };
  });
  box.querySelector("[data-accorder]").onclick = async () => {
    const principal = box.querySelector(".col-principal").value.trim();
    if (!principal) { colMsg("Indiquez un login ou un nom de groupe.", true); return; }
    if (await colTenter(() => apiSend("PUT", `/api/collections/${c.id}/acces`, {
        genre: box.querySelector(".col-genre").value,
        principal,
        niveau: box.querySelector(".col-niveau-neuf").value })))
      recharger();
  };
  box.querySelector("[data-renommer]").onclick = async () => {
    const nom = prompt("Nouveau nom de la collection :", c.nom);
    if (nom === null || !nom.trim()) return;
    if (await colTenter(() => apiSend("PATCH", `/api/collections/${c.id}`, { nom: nom.trim() })))
      recharger();
  };
  box.querySelector("[data-supprimer]").onclick = async () => {
    if (!confirm(`Supprimer « ${c.nom} » ? Ses albums ne sont pas supprimés : ils sortent `
                 + `simplement de cette collection.`)) return;
    if (await colTenter(() => apiSend("DELETE", `/api/collections/${c.id}`))) recharger();
  };
}

/* Les noms des groupes d'administration, lus UNE fois. Ils viennent de `/api/moi` et non
   d'une constante recopiée ici : `BD_AUTH_ADMIN_GROUPS` est configurable, et deux listes
   qui divergent afficheraient un groupe qui n'administre plus rien. */
/* L'identité courante. Elle vit dans `common.identite()` depuis UX-10, parce que la
   Bibliothèque en a besoin AUSSI — pour dire « verrouillé par vous » — et qu'une seconde
   copie aurait fini par répondre autre chose. `theme.js` ne demande `/api/moi` qu'une
   fois par page ; ce helper ne fait que mémoïser la lecture du résultat. */
let MOI = { login: null, groupes_admin: [] };

async function loadCollections() {
  const body = $("#col-body");
  // Avant le rendu : la note qui déclare les administrateurs en dépend, et une note qui
  // ne paraît pas laisse la liste mentir par omission comme avant le chantier.
  MOI = await identite();
  let cols = [];
  try { cols = await apiGet("/api/collections"); }
  catch (e) { body.innerHTML = `<p class="col-note">${esc(e.message)}</p>`; return; }
  body.innerHTML = "";
  if (!cols.length) {
    body.innerHTML = `<p class="col-note">Aucune collection ouverte pour vous. Créez-en une
      ci-dessus : vous en serez propriétaire.</p>`;
    return;
  }
  cols.forEach((c) => body.appendChild(colItem(c)));
}

/* --- Vue des comptes (AUTH-7) ---------------------------------------------------
   Ce que chaque login a LAISSÉ, pour que la règle de suppression — validée le 2026-09-06
   — soit consultable par des gens qui n'étaient pas dans la conversation où elle s'est
   décidée. D'où un VERDICT plutôt que des chiffres, et des comptes GROUPÉS par verdict.

   Le verdict parle de CONSÉQUENCE, jamais de recommandation : « rien à orpheliner » et
   non « supprimable ». L'écran dit ce qu'une suppression casserait ; décider reste un
   geste humain, et il se fait ailleurs — dans l'annuaire, que cet écran ne commande pas.
   -------------------------------------------------------------------------------- */
async function loadComptes() {
  const bloc = $("#comptes-bloc");
  let d;
  // On DEMANDE, et un refus signifie « pas pour vous ». La garde vit sur la route
  // (403 aux non-administrateurs) ; la reproduire ici en lisant les groupes ferait
  // deux sources à tenir d'accord, et l'écran finirait par mentir dans un sens ou l'autre.
  try { d = await apiGet("/api/comptes"); }
  catch (e) { bloc.hidden = true; return; }
  bloc.hidden = false;

  // La limite EST le contenu : sans elle, un administrateur — qui n'a aucune ligne
  // d'accès explicite — se lit « rien à orpheliner ». Exact, et trompeur.
  $("#comptes-limite").textContent = d.limite || "";

  const body = $("#comptes-body");
  if (!d.comptes.length) {
    body.innerHTML = `<p class="col-note">Aucun compte n'a encore ouvert de page.</p>`;
    return;
  }
  // « Rien à orpheliner » d'abord : c'est le groupe sur lequel on agit, et celui qui
  // porte aussi le signal « s'est connecté et ne voit rien ».
  const groupes = new Map();
  d.comptes.forEach((c) => {
    if (!groupes.has(c.verdict)) groupes.set(c.verdict, []);
    groupes.get(c.verdict).push(c);
  });
  const ordre = [...groupes.keys()].sort(
    (a, b) => (a === "rien à orpheliner" ? -1 : b === "rien à orpheliner" ? 1 : a.localeCompare(b)));

  // UX-7 — le cadre défilant, comme les quatre autres tableaux larges du dépôt (albums,
  // planches, Accord, Inter). Six colonnes ne tiennent pas dans 320 px, et sans cadre le
  // débordement sort de l'écran au lieu de défiler. Il manquait ici, et le harnais de
  // reflow ne pouvait pas le dire : sans `BD_AUTH_PROXY` le décor n'inscrit personne dans
  // `utilisateur`, donc ce tableau se rend VIDE pendant la mesure. Ce que la page ne rend
  // pas, l'instrument ne le voit pas — l'avertissement que `test_e2e_reflow.py` s'écrit à
  // lui-même pour la Recherche vaut ici, et personne ne l'y avait appliqué.
  //
  // L'étiquette porte le VERDICT parce qu'il y a un tableau par groupe : plusieurs
  // régions au nom identique se valent un « lequel ? » à la navigation par régions.
  body.innerHTML = ordre.map((v) => `
    <h4 class="comptes-verdict">${esc(v)} <span class="muted">(${groupes.get(v).length})</span></h4>
    <div class="table-cadre" tabindex="0" role="region"
         aria-label="Comptes — ${esc(v)}">
    <table class="corpus-table comptes-table">
      <thead><tr>
        <th scope="col">Login</th><th scope="col">Nom</th>
        <th scope="col">Dernière visite</th>
        <th scope="col" class="c-num">Actes</th><th scope="col" class="c-num">Accès</th>
        <th scope="col">Signal</th>
      </tr></thead>
      <tbody>${groupes.get(v).map((c) => `
        <tr>
          <td class="c-titre">${esc(c.login)}</td>
          <td>${esc(c.nom || "—")}</td>
          <td>${esc((c.derniere_vue || "—").slice(0, 10))}</td>
          <td class="c-num">${c.actes}</td>
          <td class="c-num">${c.acces_explicites}</td>
          <td>${c.reprises
              ? `<span class="compte-repris">identité changée ${c.reprises}\u00a0×</span>`
              : ""}</td>
        </tr>`).join("")}</tbody>
    </table>
    </div>`).join("");
}

async function creerCollection() {
  const nom = $("#col-nom").value.trim();
  if (!nom) { colMsg("Donnez un nom à la collection.", true); return; }
  if (await colTenter(() => apiSend("POST", "/api/collections", { nom }))) {
    $("#col-nom").value = "";
    colMsg(`« ${nom} » créée — vous en êtes propriétaire.`);
    loadCollections();
  }
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
  // Pas de modale à ouvrir : les trois blocs sont la page. On charge donc d'emblée —
  // trois requêtes, dont l'une (`/api/comptes`) peut légitimement être refusée.
  //
  // `loadComptes()` s'appelle ICI, et non depuis `loadCollections()` où elle a vécu
  // jusqu'au 2026-09-07. Elle y était nichée APRÈS le `return` du cas « aucune
  // collection », si bien qu'une portée sans collection escamotait la vue des comptes —
  // un bloc masqué par une condition qui ne le concerne pas, c'est-à-dire très exactement
  // le motif d'AUTH-4 que cette page existe pour fermer. Mesuré : sans collection,
  // `/api/comptes` n'était JAMAIS demandé par le navigateur ; avec, la table se rendait.
  //
  // Le déménagement n'a pas créé le défaut, il l'a rendu ATTEIGNABLE : dans la modale de
  // la Bibliothèque, `loadCollections()` était le geste d'ouverture, donc la nidification
  // ne se voyait pas et ne coûtait rien. C'est l'argument inverse de celui qu'on oppose
  // d'habitude aux déménagements.
  //
  // Le commentaire ci-dessus disait « deux requêtes » depuis le premier jour : il
  // décrivait l'intention et se lisait comme une description du fait. Qui cherchait dans
  // `setup()` si les comptes se chargeaient d'emblée y trouvait « oui », à trois lignes de
  // la ligne qui disait le contraire.
  loadCollections();
  loadComptes();
  santeCharger();
  $("#col-add").onclick = creerCollection;
  $("#col-nom").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); creerCollection(); }
  });
  // SANTE-1 : éprouver reste un geste SÉPARÉ et volontaire — le contrôle profond importe
  // les moteurs pour de bon, quelques secondes et quelques centaines de mégaoctets.
  $("#sante-eprouver").onclick = santeEprouver;
}

setup();
