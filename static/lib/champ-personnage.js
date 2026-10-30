/* LE CHAMP « PERSONNAGE » — le locuteur d'une zone de texte, l'identité d'une boîte
   personnage —, COMMUN à l'Atelier et à la page Annotation (ANN-7, tranche 2, commit 8 :
   sorti de `viewer.js` pour ne pas être recopié, `docs/ann7-tranche2-cadrage.md`, item 7).
   Chargé en <script> → `window.BDChampPersonnage` ; require()-able par
   `tests/js/champ-personnage.test.js`. Rien n'est lu au chargement : le document, les
   aides de `common.js` (`apiGet`, `apiSend`, `toast`, `escapeHtml`) et `BDPropositions` ne
   servent qu'à l'appel — l'hôte peut les PASSER (`env`), sinon ce sont les globales de la
   page.

   Ce module ne fait que la LISTE et le CHOIX : chaque surface garde ce qu'elle fait du choix
   (`onPick(personnageId, zone, nom)`) — la valeur vue de CONC-4, le bandeau d'un 409, la
   file des gestes —, parce qu'elle seule sait où elle le montre.

   Ce qui suit est le commentaire d'origine, inchangé :

   Autocomplétion « personnage » réutilisable : registre corpus + création à la volée
   (modèle mentions→entités). `onPick(personnageId)` applique le choix — locuteur d'une
   zone de texte OU identité d'une boîte personnage (§14, brique (a)). Une seule logique pour les
   deux panneaux ; seule l'action finale (onPick) diffère. `zone()` rend la région que le
   panneau sert à cet instant.

   ANN-6 — ENTRÉE NE CRÉE PAS UN HOMONYME FAUTE D'AVOIR REGARDÉ. Ici la liste dépend de la
   saisie côté serveur (`?q=`), calculée 200 ms après la dernière frappe ; Entrée y
   cherchait l'homonyme exact telle qu'elle était, et créait faute de l'y trouver. « Zed »
   existant, tapé vite, devenait un SECOND « Zed », aussitôt attribué (mesuré le
   2026-10-12, quatorze personnages au registre). La série distingue des homonymes
   légitimes : la garde est donc ici. Depuis ANN-8, le serveur retrouve aussi, au lieu de
   créer, un personnage qu'on voit et qui porte le même nom sans casse ni accents dans la
   même série — un filet, pour une liste lue trop tôt ; la décision reste celle de l'écran.

   - L'écran retient POUR QUELLE SAISIE sa liste vaut (`listePour`). Une réponse ne
     s'affiche que si elle vaut encore : aucune lecture partie depuis, saisie inchangée.
     Et dès qu'un geste part d'ici, elle ne vaut plus pour aucune : après avoir créé
     « Zed » sur une bulle, le retaper vite sur la suivante relit le registre.
   - Si la liste ne vaut pas pour ce qui est tapé au moment d'Entrée, le registre est RELU
     pour cette saisie avant toute décision — par la lecture déjà en vol si elle porte la
     même saisie, sinon par une lecture de plus. Le geste lent, lui, n'émet rien de neuf.
   - L'homonyme exact se cherche dans TOUTE la réponse, pas dans les dix propositions
     affichées : au-delà de la dixième, il n'était ni proposé ni trouvé, et Entrée créait
     un doublon même tapé lentement (mesuré le 2026-10-13).
   - Une lecture en ÉCHEC n'est pas un registre vide : rien n'est proposé — pas même de
     créer —, et Entrée rend la saisie avec un message au lieu de créer à l'aveugle.

   - Le geste vaut pour la zone où il est FAIT. Relire prend du temps, créer aussi : la
     zone est retenue à l'Entrée (ou au clic), et le choix lui revient même si l'on en a
     sélectionné une autre entre-temps — il partait sinon vers celle-là.

   ANN-8 — PLUSIEURS PERSONNAGES DU MÊME NOM SE DÉPARTAGENT À L'ÉCRAN (Hugo, 2026-10-21).
   Entrée prenait le premier homonyme exact dans l'ordre du registre (nom, puis série),
   sans le dire. Elle ne décide plus : la liste se réduit aux homonymes, chacun avec sa
   série (« sans série » quand il n'en a pas), et l'on choisit — flèches et Entrée, ou clic.
   Un seul personnage de ce nom : il est pris, comme avant. La règle vit dans
   `BDPropositions.decisionNom`.

   ANN-8 — ↓ PUIS ENTRÉE PENDANT QUE LA LISTE SE RECHARGE (Hugo, 2026-10-21). Entre une
   frappe et le retour de sa liste, la liste à l'écran est celle de la saisie d'AVANT ; ↓
   y surligne une ligne, et Entrée la prenait. À Entrée, la surlignée est revérifiée contre
   ce qui est tapé (`BDPropositions.entreePersonnage`) : si elle y répond encore — son nom
   contient la saisie, comme le filtre du serveur —, elle part ; sinon rien n'est pris, la
   liste se relit pour la saisie et s'affiche sans rien surligner, et l'on choisit dedans.
   La liste n'est pas fermée pendant la lecture : les flèches y restent vivantes.

   ANN-8 — LES DEUX CHAMPS SAVENT CE QUE L'AUTRE VIENT DE CRÉER. Chaque montage tient sa
   liste ; « Zed » créé par la boîte personnage, puis tapé vite dans le champ du locuteur,
   se décidait sur la liste de CE champ — et si « Zed » y avait déjà été cherché, elle
   disait encore « Créer » : un second « Zed ». Une création, d'où qu'elle parte, avance
   `registreModifie` ; une liste lue AVANT ne vaut plus pour décider, et « Créer » choisi
   dans une telle liste relit d'abord le registre.

   ANN-8 — APRÈS UNE VALIDATION, UNE SEULE ↓ SURLIGNE. Le champ vient d'être vidé et la
   liste ne vaut pour aucune saisie : la première ↓ la relit pour le champ vide, et surligne
   la première proposition à son retour. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module !== "undefined" && module.exports) module.exports = api;   // Node (tests)
  else root.BDChampPersonnage = api;                                           // navigateur
})(typeof self !== "undefined" ? self : this, function (root) {
  "use strict";

  // Avance à chaque personnage créé depuis l'un des champs de la page (ANN-8 : « les deux
  // champs savent ce que l'autre vient de créer »). Un compteur par PAGE, donc par module.
  let registreModifie = 0;

  /* Les aides de la page, lues à l'APPEL (jamais au chargement) ; l'hôte peut les passer. */
  function outils(env) {
    const e = env || {};
    const g = (nom) => (e[nom] !== undefined ? e[nom] : root ? root[nom] : undefined);
    return {
      apiGet: g("apiGet"), apiSend: g("apiSend"), toast: g("toast"),
      escapeHtml: g("escapeHtml"),
      propositions: e.propositions || (root && root.BDPropositions)
        || (typeof require === "function" ? require("./propositions.js") : null),
      document: e.document || (typeof document !== "undefined" ? document : null),
    };
  }

  /* Un élément, ou un sélecteur à chercher dans le document. */
  function element(x, doc) {
    return typeof x === "string" ? doc.querySelector(x) : x;
  }

  /* MONTER le champ : `champ` (le champ de saisie) et `liste` (la boîte des propositions),
     des éléments ou des sélecteurs ; `onPick(personnageId, zone, nom)` applique le choix ;
     `zone()` rend la région que le champ sert à cet instant. */
  function monter(champ, liste, onPick, zone, env) {
    // Les aides se relisent à CHAQUE appel, comme les globales nues d'avant : une page qui
    // enveloppe `apiSend` après le montage (pour noter ses propres écritures) est suivie.
    const o = () => outils(env);
    const apiGet = (...a) => o().apiGet(...a);
    const apiSend = (...a) => o().apiSend(...a);
    const toast = (...a) => o().toast.apply(null, a);   // `.apply` : un seul appel compté
    const escapeHtml = (t) => o().escapeHtml(t);
    const BDPropositions = o().propositions;
    const doc = o().document;
    const input = element(champ, doc), sug = element(liste, doc);
    let timer = null, activeIdx = -1, items = [];
    let lecture = null;       // la dernière lecture PARTIE pour la liste : { q, promesse }
    let listePour = null;     // la saisie pour laquelle `items` vaut — nul : pour aucune
    let listeDuRegistre = -1; // l'état du registre (`registreModifie`) quand la liste a été LUE
    let lus = [];             // la réponse ENTIÈRE du registre pour `listePour`, pas les dix affichés
    let surlignerAuRetour = false;   // une ↓ a demandé la liste : surligner la première
    function close() { sug.hidden = true; activeIdx = -1; }
    const lire = (q) => apiGet("/api/personnages?q=" + encodeURIComponent(q));
    /* La liste vaut-elle pour décider de `q` ? Lue pour cette saisie, et depuis aucune création. */
    const vaut = (q) => listePour === q && listeDuRegistre === registreModifie;
    async function fetchList() {
      const q = input.value.trim();
      const etat = registreModifie;
      const moi = lecture = { q, promesse: lire(q), etat };
      let persos = null;
      try { persos = await moi.promesse; } catch (e) { persos = null; }
      // Elle ne vaut plus : une lecture est partie depuis, ou la saisie a changé.
      if (lecture !== moi || input.value.trim() !== q) return;
      listePour = persos ? q : null;
      listeDuRegistre = etat;
      lus = persos || [];
      items = lus.slice(0, 10).map((p) => ({ create: false, id: p.id, nom: p.nom, serie: p.serie }));
      // proposer la CRÉATION si la saisie n'a pas de correspondance exacte (modèle mentions→entités)
      if (persos && q && !BDPropositions.homonymes(persos, q).length) items.push({ create: true, nom: q });
      if (surlignerAuRetour) { surlignerAuRetour = false; activeIdx = BDPropositions.fleche(-1, items.length, "bas"); }
      render();
    }
    function render() {
      sug.innerHTML = "";
      if (!items.length) { close(); return; }
      items.forEach((it, i) => {
        const d = doc.createElement("div");
        if (i === activeIdx) d.classList.add("active");
        // Un homonyme à départager dit TOUJOURS sa série : sans elle, deux lignes identiques.
        const serie = it.serie ? escapeHtml(it.serie) : it.homonyme ? "sans série" : "";
        d.innerHTML = it.create
          ? `➕ Créer « ${escapeHtml(it.nom)} »`
          : `${escapeHtml(it.nom)}${serie ? `<span class="freq">${serie}</span>` : ""}`;
        d.onmousedown = (e) => { e.preventDefault(); choose(it); };
        sug.appendChild(d);
      });
      sug.hidden = false;
    }
    async function appliquer(it, z) {
      // Un geste part : ni la liste ni la lecture qui l'a faite ne font plus foi. Créer
      // change le registre, et le même nom retapé aussitôt — ici ou sur la zone suivante —
      // ne doit pas se décider d'après ce qu'on savait AVANT de créer.
      listePour = null; lecture = null; items = [];
      if (it.create) {
        try {
          const p = await apiSend("POST", "/api/personnages", { nom: it.nom });
          registreModifie++;                           // ANN-8 : l'autre champ le saura aussi
          await onPick(p.id, z, p.nom);                // le nom : CONC-4, pour le bandeau
        } catch (e) { toast("Création : " + e.message, "error"); }
      } else { await onPick(it.id, z, it.nom); }
    }
    async function choose(it) {
      // ANN-8 — « Créer » pris dans une liste lue avant une création (ici ou dans l'autre
      // champ) : le nom existe peut-être déjà. On relit avant de créer.
      if (it.create && listeDuRegistre !== registreModifie) { valider(it.nom); return; }
      input.value = ""; close();
      await appliquer(it, zone());
    }
    /* Plusieurs personnages portent le nom tapé : la liste se réduit à eux, chacun avec sa
       série, rien de surligné — Entrée n'a rien pris, l'on choisit. */
    function departager(homos, q, etat) {
      listePour = q; listeDuRegistre = etat; lus = homos;
      items = homos.map((p) => ({ create: false, id: p.id, nom: p.nom, serie: p.serie, homonyme: true }));
      activeIdx = -1;
      render();
    }
    /* Entrée sans sélection : l'homonyme exact de CE qui est tapé s'il est seul, la liste des
       homonymes s'ils sont plusieurs, sinon la création. */
    async function valider(q) {
      // La lecture différée de la frappe n'a plus d'objet : Entrée décide, sur la liste qui
      // vaut ou sur sa propre lecture. Partie après, elle rouvrirait la liste ENTIÈRE par-dessus
      // celle des homonymes.
      clearTimeout(timer);
      if (vaut(q)) {                                   // la liste vaut pour cette saisie
        const d = BDPropositions.decisionNom(lus, q);
        if (d.geste === "departager") departager(d.homonymes, q, listeDuRegistre);
        else choose(d.geste === "choisir" ? d.item : { create: true, nom: d.nom });   // pas de doublon
        return;
      }
      // Elle ne vaut pas pour cette saisie : on relit avant de décider. Le champ se vide
      // tout de suite — une seconde Entrée pendant la lecture ne part pas deux fois. Une
      // lecture déjà en vol ne sert que si elle est partie APRÈS la dernière création.
      const z = zone();
      const etat = registreModifie;
      input.value = ""; close();
      let persos;
      try {
        persos = await (lecture && lecture.q === q && lecture.etat === registreModifie
          ? lecture.promesse : lire(q));
      }
      catch (e) {
        if (!input.value) input.value = q;             // rien n'est fait : la saisie revient
        toast("Registre des personnages : " + e.message, "error");
        return;
      }
      const d = BDPropositions.decisionNom(persos, q);
      if (d.geste === "departager") {
        // Rien n'est fait : la saisie revient, avec les homonymes — si l'on est resté sur la
        // zone du geste et qu'on n'a rien tapé depuis. Sinon on est passé à autre chose.
        if (zone() === z && !input.value) { input.value = q; departager(d.homonymes, q, etat); }
        return;
      }
      appliquer(d.geste === "choisir" ? d.item : { create: true, nom: d.nom }, z);
    }
    input.addEventListener("input", () => {
      activeIdx = -1; surlignerAuRetour = false;
      clearTimeout(timer); timer = setTimeout(fetchList, 200);
    });
    input.addEventListener("focus", fetchList);
    input.addEventListener("blur", () => setTimeout(close, 150));
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        // ANN-8 — liste fermée qui ne vaut pas pour ce qui est tapé (le champ vient d'être vidé par
        // une validation) : la relire, et surligner la première à son retour.
        if (sug.hidden && !vaut(input.value.trim())) { surlignerAuRetour = true; fetchList(); return; }
        activeIdx = BDPropositions.fleche(activeIdx, items.length, "bas"); render();
      }
      else if (e.key === "ArrowUp") { activeIdx = BDPropositions.fleche(activeIdx, items.length, "haut"); render(); e.preventDefault(); }
      else if (e.key === "Enter") {
        e.preventDefault();
        const q = input.value.trim();
        const d = BDPropositions.entreePersonnage({ q, actif: activeIdx, items });
        if (d.geste === "choisir") choose(d.item);
        else if (d.geste === "valider") valider(q);
        else if (d.geste === "relire") {
          // ANN-8 — la surlignée vient de la liste d'une saisie d'avant et n'y répond plus :
          // rien n'est pris. La liste de CETTE saisie se lit (une seule fois : celle qui est
          // déjà en vol suffit), et s'affiche sans rien surligner.
          activeIdx = -1; render();
          clearTimeout(timer);
          if (!(lecture && lecture.q === q && lecture.etat === registreModifie)) fetchList();
        }
      } else if (e.key === "Escape") { close(); }
    });
  }

  /* Pour les tests : l'état du registre, que la page ne lit pas. */
  function etatDuRegistre() { return registreModifie; }

  return { monter, etatDuRegistre };
});
