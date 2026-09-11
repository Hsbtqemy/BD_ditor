/* Administration (UX-10) — le lieu des gestes qui portent sur l'INSTANCE.

   Quatre blocs, et aucun n'est une affaire de Bibliothèque : la version servie dit quel
   commit tourne ici (INFRA-10), les collections décident qui voit quoi dans tout le
   corpus, la vue des comptes dit ce que chaque login a laissé, les moteurs disent si
   l'instance sait encore reconnaître quelque chose. Les trois derniers vivaient dans
   `/corpus` par ACCRÉTION — c'était le seul écran administratif, et tout ce qui y
   ressemblait s'y est ajouté —, donc les atteindre depuis la Visionneuse demandait de
   quitter son travail.

   ILS ONT DÉMÉNAGÉ, ils ne sont pas dupliqués. Décision de l'équipe le 2026-09-07 : deux
   portes vers la même pièce se paient toujours, l'une des deux vieillit, et c'est celle
   qu'on ne regarde plus.

   ET CE NE SONT PLUS DES MODALES. Une page est un lieu : les blocs sont là, lisibles
   ensemble, sans piège à focus ni Échap à gérer. `dialog.js` ne sert donc plus ici.

   LA GARDE RESTE SUR L'ACTE, JAMAIS SUR L'ÉCRAN QUI LE CONTIENT. C'est la condition posée
   par UX-10, et elle vient d'une erreur réelle : dans AUTH-4, le référent d'une collection
   — une simple ADRESSE — s'est retrouvé derrière la garde du PARTAGE parce qu'il vivait
   dans ce panneau-là, donc lisible du seul propriétaire. Ici, chaque bloc pose SA question :
   la version servie et la vue des comptes n'apparaissent que si leur route répond (403
   aux non-administrateurs), les collections sont filtrées par la portée du serveur, et
   les moteurs sont ouverts à tous — regarder si l'OCR fonctionne n'est pas un pouvoir.
   La page, elle, ne garde rien.

   Et la garde d'un bloc RÉSERVÉ se pose au même endroit que celle d'un bloc ouvert : sur
   la route. Un `if` côté client qui lirait les groupes ferait deux sources à tenir
   d'accord — et celle qui se tromperait serait la muette, puisqu'un bloc masqué à tort
   ne lève aucune erreur et ne casse aucun test. */

/* ═══════════════════════════════════════════════════════════════════════════
   Accès aux collections (AUTH-3) — qui entre, et à quel niveau

   AUTH-2 avait fait le cloisonnement, pas son administration : `collection_acces` ne se
   remplissait qu'en SQL à la main. Cet écran est ce qui rend le reste utilisable — sans
   lui, tout le travail de routes reste du curl.

   Trois niveaux, et le troisième est la nouveauté : lecture · écriture · PROPRIÉTAIRE.
   Écrire, c'est annoter ; posséder, c'est décider qui d'autre entrera.

   DROIT-2 (2026-09-11) — et une case à côté du niveau : « peut exporter ». Sortir le
   contenu en fichier ne s'ordonne pas avec annoter ; un propriétaire exporte d'office,
   et sa case le montre sans se laisser décocher.

   COL-2 (2026-09-11) — CE QUE LA COLLECTION EST a déménagé dans la Bibliothèque : la
   créer, la renommer, la supprimer, la décrire, désigner son référent, régler sa
   diffusion, l'exporter. Tout cela s'était accumulé ici parce que c'était le seul écran
   qui touchait une collection. La frontière, tenue en connaissance de cause : QUI ENTRE
   relève de l'instance et reste ici ; ce que la collection EST relève du corpus.
   Déménagé, pas dupliqué (UX-10) — et chaque écran dit où vit l'autre moitié.
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

/* AUTH-6 — les deux natures d'un compte, LIBELLÉES pour qui n'était pas dans la décision.
   « Collectif (login partagé) » plutôt que « collectif » seul : le mot désigne ici un fait
   technique précis — plusieurs personnes derrière un même login — et non une appartenance
   à une équipe, que le lecteur pourrait comprendre à la place. La conséquence est dite au
   même endroit, sous le tableau, parce qu'un choix sans conséquence visible se fait au
   hasard. */
const COMPTE_NATURES = [["nominatif", "Nominatif (une personne)"],
                        ["collectif", "Collectif (login partagé)"]];

function natureOptions(courante) {
  return COMPTE_NATURES.map(([v, l]) =>
    `<option value="${v}"${v === courante ? " selected" : ""}>${l}</option>`).join("");
}

function niveauOptions(courant) {
  return COL_NIVEAUX.map(([v, l]) =>
    `<option value="${v}"${v === courant ? " selected" : ""}>${l}</option>`).join("");
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
  d.innerHTML = `
    <summary>
      <span class="col-nom">${esc(c.nom)}</span>
      <span class="muted small">${c.nb_albums} album(s)</span>
      ${badge}
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

/* Où est l'autre moitié (COL-2). Dite dans les DEUX branches : la frontière coupe en deux
   le trajet le plus courant — on crée et on décrit dans la Bibliothèque, on fait entrer
   ici —, et un écran qui ne dit pas où vit le reste fait chercher au mauvais endroit. C'est
   le coût écrit du déménagement, payé à l'écran plutôt que dans une documentation. */
function colAilleurs() {
  return `<p class="col-note">La description de cette collection, son régime de diffusion,
    son référent et son export se lisent et se règlent dans la
    <a href="/corpus">Bibliothèque</a>.</p>`;
}

async function colDetail(d, c) {
  const box = d.querySelector(".col-detail");
  if (!c.administrable) {
    // Le participant NON propriétaire ne voit pas la liste des accès — c'est une donnée
    // sur des personnes —, mais il apprend qu'un administrateur d'instance lit ici sans y
    // figurer (AUTH-4). Le référent, qu'il a besoin de LIRE, a suivi les descripteurs dans
    // la Bibliothèque (COL-2) : c'est là qu'on cherche à qui écrire pour une collection.
    box.innerHTML = `<p class="col-note">Vous participez à cette collection sans la
      posséder : seul un propriétaire voit et modifie la liste des accès.</p>
      ${colAdminNote()}${colAilleurs()}`;
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
        <span class="acces-genre">${a.genre === "groupe" ? "groupe" : "utilisateur"}</span>${
          a.jamais_vu === true
            ? `<span class="acces-jamais-vu">n'a pas encore ouvert l'application</span>`
            : ""}
        <select data-genre="${esc(a.genre)}" data-principal="${esc(a.principal)}"
                aria-label="Niveau de ${esc(a.principal)}">${niveauOptions(a.niveau)}</select>
        <label class="acces-export"><input type="checkbox" data-export="1"
                 data-genre="${esc(a.genre)}" data-principal="${esc(a.principal)}"
                 data-niveau="${esc(a.niveau)}" aria-label="${esc(a.principal)} peut exporter"
                 ${a.exporter ? "checked" : ""}${a.niveau === "proprietaire" ? " disabled" : ""}>
          peut exporter${a.niveau === "proprietaire"
            ? ` <span class="muted small">(d'office, en propriétaire)</span>` : ""}</label>
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
      <label class="acces-export"><input type="checkbox" class="col-export-neuf">
        peut exporter</label>
      <button class="ghost small" data-accorder="1" type="button">+ Accorder</button>
    </div>
    <p class="col-note">Un accès se déclare par un NOM, pas par une personne vérifiée :
      l'application n'a aucun annuaire, elle lit les groupes dans les en-têtes du proxy à
      chaque requête. Un LOGIN qui n'a pas encore ouvert l'application est signalé
      ci-dessus — l'observation seule&nbsp;: une faute de frappe et un arrivant qui
      n'est pas encore venu produisent la même absence, et rien ici ne peut les
      distinguer. Un nom de GROUPE, lui, ne peut pas l'être : l'application n'en
      connaît aucun.</p>
    <p class="col-note">« Peut exporter », c'est sortir le contenu de la collection en
      fichier — un album, une concordance, une figure, un export de dépôt. Lire ou
      annoter n'y suffit pas ; un propriétaire exporte d'office.</p>
    ${colAdminNote()}
    ${colAilleurs()}`;

  const recharger = async () => { await loadCollections(); };
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
  box.querySelectorAll("input[data-export]").forEach((i) => {
    i.onchange = async () => {
      const { genre, principal, niveau } = i.dataset;
      // Même règle que le niveau : on recharge dans les deux cas, pour que la case
      // affichée soit celle que le serveur a enregistrée, pas celle qu'on a cliquée.
      await colTenter(() => apiSend("PUT", `/api/collections/${c.id}/acces`,
        { genre, principal, niveau, exporter: i.checked }));
      recharger();
    };
  });
  box.querySelector("[data-accorder]").onclick = async () => {
    const principal = box.querySelector(".col-principal").value.trim();
    if (!principal) { colMsg("Indiquez un login ou un nom de groupe.", true); return; }
    if (await colTenter(() => apiSend("PUT", `/api/collections/${c.id}/acces`, {
        genre: box.querySelector(".col-genre").value,
        principal,
        niveau: box.querySelector(".col-niveau-neuf").value,
        exporter: box.querySelector(".col-export-neuf").checked })))
      recharger();
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
    body.innerHTML = `<p class="col-note">Aucune collection ouverte pour vous. On en crée
      une dans la <a href="/corpus">Bibliothèque</a>, et l'on en devient propriétaire.</p>`;
    return;
  }
  cols.forEach((c) => body.appendChild(colItem(c)));
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
  //
  // AUTH-6 y ajoute les conséquences de la nature. Elles sont écrites à CÔTÉ du sélecteur
  // qui la pose, et pas seulement dans une fiche : déclarer un login collectif retire du
  // travail à une mesure et raccourcit Ctrl+Z, ce qui ne se devine pas depuis un menu à
  // deux entrées. Et c'est la DÉCLARATION qui déclenche tout : un login partagé que
  // personne ne déclare garde un Ctrl+Z sans limite.
  $("#comptes-limite").textContent = (d.limite || "") + " Un compte déclaré COLLECTIF est "
    + "un login partagé par plusieurs personnes : l'accord inter-annotateurs cesse de le "
    + "mesurer — il compte à part ce qu'il ne peut pas trancher —, les exports le "
    + "nomment « collectif-N » au lieu de « annotateur-N », et Ctrl+Z n'y remonte que "
    + "les cinq dernières minutes, faute de savoir qui a fait quoi. Aucun droit d'accès "
    + "n'en dépend.";

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
  // planches, Accord, Inter). SEPT colonnes depuis AUTH-6 (2026-09-09) — la nature s'y est
  // ajoutée — et elles ne tiennent pas dans 320 px ; sans cadre le
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
        <th scope="col">Login</th><th scope="col">Nature</th><th scope="col">Nom</th>
        <th scope="col">Dernière visite</th>
        <th scope="col" class="c-num">Actes</th><th scope="col" class="c-num">Accès</th>
        <th scope="col">Signal</th>
      </tr></thead>
      <tbody>${groupes.get(v).map((c) => `
        <tr>
          <td class="c-titre">${esc(c.login)}</td>
          <td><select data-nature-de="${esc(c.login)}"
                      aria-label="Nature du compte ${esc(c.login)}">${
            natureOptions(c.nature)}</select></td>
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

  // Le geste qui POSE la nature. Il vit ici et non dans un écran à part parce que c'est
  // là qu'on lit ce qu'un compte a laissé — et qu'un compte collectif change la lecture de
  // toute sa ligne : « laisse des actes » cesse alors de désigner une personne.
  body.querySelectorAll("select[data-nature-de]").forEach((sel) => {
    sel.onchange = async () => {
      const login = sel.dataset.natureDe;
      try {
        await apiSend("PATCH", `/api/comptes/${encodeURIComponent(login)}/nature`,
                      { nature: sel.value });
      } catch (e) {
        toast(e.message || "Échec", "err");
      }
      // On recharge dans les DEUX cas, comme le sélecteur de niveau d'accès : en cas de
      // refus, le <select> afficherait une nature que le serveur n'a pas enregistrée, et
      // l'écran mentirait sur l'état réel. Ici le mensonge coûterait plus cher qu'ailleurs
      // — c'est cette valeur qui décide si une mesure d'accord a le droit de répondre.
      loadComptes();
    };
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
  // Pas de modale à ouvrir : les blocs SONT la page. On charge donc d'emblée — quatre
  // requêtes, dont deux (`/api/version` et `/api/comptes`) peuvent légitimement être
  // refusées, chacune masquant son propre bloc et rien d'autre.
  //
  // Le compte est tenu à jour ICI parce que ce commentaire a déjà menti : il disait
  // « deux requêtes » depuis le premier jour, à trois lignes de la ligne qui le
  // contredisait (cf. plus bas). Un chiffre dans un commentaire est une affirmation
  // vérifiable, et il vieillit dans le sens rassurant.
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
  loadVersion();
  loadCollections();
  loadComptes();
  santeCharger();
  // SANTE-1 : éprouver reste un geste SÉPARÉ et volontaire — le contrôle profond importe
  // les moteurs pour de bon, quelques secondes et quelques centaines de mégaoctets.
  $("#sante-eprouver").onclick = santeEprouver;
}

setup();
