/* La BIBLIOTHÈQUE en calque (UX-18) — sa logique pure, sans DOM.
   Chargé en <script> par la Bibliothèque → expose `window.BDBiblio` ; aussi require()-able
   par `tests/js/bibliotheque.test.js`, qui la vérifie par tables de cas. Rien n'est lu au
   chargement : ni le document, ni le stockage, ni l'adresse.

   CE QUE C'EST. La Bibliothèque montre les albums du projet courant, et pose les
   collections DESSUS, en calques qui se recoupent (tranché par Hugo le 2026-10-16, pour
   l'écran seulement) : cocher une collection FILTRE la liste, son nom OUVRE sa fiche, deux
   filtres ouvrent une comparaison. Ce module dit lesquels des albums restent, dans quel
   ordre se rangent les collections, ce que l'on peut faire d'un album et d'une collection,
   ce que deux collections ont en commun, et ce que l'adresse ouvre.

   CE N'EST PAS UNE GARDE. Tout ce qui suit lit ce que le serveur a déjà décidé — les
   collections d'un album qu'on LIT (`GET /api/albums`, clé `collections`), et ce qu'on
   peut faire dans chacune (`GET /api/collections` : `ecrivable`, `exportable`,
   `administrable`). Le serveur reste seul à trancher chaque geste, et il le refuse en le
   disant si l'écran s'est trompé. Deux règles y sont écrites UNE fois, parce que deux
   écritures finiraient par ne plus répondre pareil :

     · LES DROITS D'UN ALBUM SONT L'UNION DE CEUX DE SES COLLECTIONS. Écrire dans UNE de
       ses collections suffit à annoter l'album (`clause_album(ecriture=True)` côté
       serveur), quelle que soit la collection par laquelle on l'a ouvert. La ligne « Vos
       droits ici » d'une collection, elle, ne parle que de CETTE collection : les deux ne
       se lisent pas l'une pour l'autre (`droitsAlbum` contre `actesCollection`).
     · LE TOTAL NE SE DIT QU'À UNE PORTÉE TOTALE. Ce que la liste montre est la part du
       projet que l'on LIT ; pour tout autre, « 404, jamais 403 » (AUTH-2) interdit d'en
       dire le total, et les libellés disent « que vous lisez » (`libelleAlbums`). */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.BDBiblio = api;                                                   // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Les quatre onglets de la fiche d'une collection, dans leur ordre (tranché par Hugo le
     2026-10-07). La clé est celle de l'adresse (`?onglet=`). */
  const ONGLETS = [
    { cle: "albums", libelle: "Albums" },
    { cle: "qui", libelle: "Qui entre" },
    { cle: "description", libelle: "Description" },
    { cle: "diffusion", libelle: "Diffusion et dépôt" },
  ];
  const CLES_ONGLETS = ONGLETS.map((o) => o.cle);
  /* L'onglet qu'ouvre le NOM d'une collection, et une adresse qui n'en nomme aucun ; la case
     de la collection, elle, ouvre « Albums ». */
  const ONGLET_PAR_LE_NOM = "qui";
  const TRIS = ["alpha", "recents"];
  const MODES = ["une", "toutes"];

  /* Pour chercher sans tenir compte des accents ni de la casse : « Étude » trouve « etude ».
     La plage U+0300–U+036F est celle des diacritiques combinants que NFD détache. */
  function plier(s) {
    return String(s == null ? "" : s).normalize("NFD").replace(/[̀-ͯ]/g, "")
      .toLowerCase();
  }

  function ids(liste) {
    return new Set((Array.isArray(liste) ? liste : [...(liste || [])]).map(Number));
  }

  /* Les collections d'un album, telles que le serveur les rend : celles qu'on LIT, `{id,
     nom}`. Une liste absente vaut vide — une réponse d'avant la clé ne doit pas lever. */
  function collectionsDe(album) {
    return album && Array.isArray(album.collections) ? album.collections : [];
  }

  /* LE CALQUE. Les albums qui restent quand des collections sont cochées : ceux qui sont
     rangés dans L'UNE d'elles (`une`, le défaut), ou dans TOUTES (`toutes`, l'intersection
     qu'une comparaison propose). Aucune collection cochée : tout reste. Le texte cherche
     dans le titre, la série et l'auteur, sans accents. Un album sans collection lue (une
     copie au fonds, que seule une portée totale voit) ne passe jamais un calque. */
  function filtrerAlbums(albums, options) {
    const o = options || {};
    const calques = ids(o.calques);
    const toutes = o.mode === "toutes";
    const q = plier(o.texte || "").trim();
    return (Array.isArray(albums) ? albums : []).filter((a) => {
      if (calques.size) {
        const siennes = new Set(collectionsDe(a).map((c) => Number(c.id)));
        const dedans = [...calques].map((c) => siennes.has(c));
        if (toutes ? !dedans.every(Boolean) : !dedans.some(Boolean)) return false;
      }
      if (q) {
        const meule = plier([a.titre, a.serie, a.auteur].filter(Boolean).join(" "));
        if (!meule.includes(q)) return false;
      }
      return true;
    });
  }

  /* L'ordre de la liste des collections : la collection de BASE du projet d'abord (elle
     reçoit ce que le projet prend au fonds, COL-3 D10), puis par nom, ou par récence — la
     plus récemment créée d'abord. Le nom se compare à la française, sans casse ni accents ;
     à date égale (ou illisible), l'identifiant départage, le plus grand d'abord. */
  function trierCollections(collections, tri) {
    const l = (Array.isArray(collections) ? collections : []).slice();
    const parNom = (a, b) => String(a.nom || "").localeCompare(String(b.nom || ""), "fr",
                                                                { sensitivity: "base" })
                             || (a.id - b.id);
    const parRecence = (a, b) => {
      const da = String(a.date_creation || ""), db = String(b.date_creation || "");
      if (da !== db) return da < db ? 1 : -1;
      return b.id - a.id;
    };
    l.sort((a, b) => (Number(!!b.base) - Number(!!a.base))
                     || (tri === "recents" ? parRecence(a, b) : parNom(a, b)));
    return l;
  }

  /* LES DROITS D'UN ALBUM : l'union de ceux de ses collections. `collections` est la liste
     de `GET /api/collections` (chacune avec `ecrivable`). Rend :
       · `ecrites` — ses collections où l'on écrit, `{id, nom}` ;
       · `lues`    — ses collections qu'on lit, `{id, nom}` (toutes celles qu'il nomme) ;
       · `ecrire`  — vrai dès qu'il y a une collection écrite. Un album SANS collection lue
                     — une copie gardée au fonds, que seule une portée totale atteint — n'a
                     rien à unir : on garde alors ce que le serveur a dit (`ecrivable`).
     La collection par laquelle on a OUVERT l'album n'entre pas dans le calcul, et c'est le
     point : la fiche ne rétrécit pas les droits à ceux de la collection d'où l'on vient. */
  function droitsAlbum(album, collections) {
    const ecrivables = new Set((Array.isArray(collections) ? collections : [])
      .filter((c) => c && c.ecrivable).map((c) => Number(c.id)));
    const lues = collectionsDe(album).map((c) => ({ id: Number(c.id), nom: c.nom }));
    const ecrites = lues.filter((c) => ecrivables.has(c.id));
    const ecrire = lues.length ? ecrites.length > 0 : !!(album && album.ecrivable);
    return { ecrire, ecrites, lues };
  }

  /* « Vos droits ici », en ACTES — jamais un nom de niveau à l'écran (fiche UX-18). Chacun
     est présent ou absent, lu dans ce que le serveur a calculé pour CETTE collection. Lire
     est toujours présent : une collection qu'on ne lit pas ne s'affiche pas. */
  function actesCollection(c) {
    const x = c || {};
    return [
      { cle: "lire", libelle: "lire", oui: true },
      { cle: "ecrire", libelle: "annoter et organiser", oui: !!x.ecrivable },
      { cle: "exporter", libelle: "exporter", oui: !!x.exportable },
      { cle: "administrer", libelle: "décider qui entre", oui: !!x.administrable },
    ];
  }

  /* Les autres collections où l'album est rangé, parmi celles qu'on lit : la colonne
     « Aussi dans » de l'onglet Albums d'une collection. */
  function aussiDans(album, collectionId) {
    return collectionsDe(album).filter((c) => Number(c.id) !== Number(collectionId))
      .map((c) => c.nom);
  }

  /* Ce que la liste compte, dans des mots qui ne disent pas un total qu'on n'a pas le droit
     de connaître. `total` : la portée totale (`acces.total` de `GET /api/moi`). `sur` : le
     nombre AVANT filtre, quand un filtre est actif. */
  function libelleAlbums(n, options) {
    const o = options || {};
    const mot = (k) => `${k} album${k > 1 ? "s" : ""}`;
    const lus = o.total ? "" : " que vous lisez";
    if (o.sur !== undefined && o.sur !== null && o.sur !== n) {
      return `${mot(n)} sur ${o.sur}${lus}`;
    }
    return `${mot(n)}${lus}`;
  }

  /* LA COMPARAISON de deux collections cochées ou plus : par collection, ses albums, ses
     planches, et combien sont validées — sur la liste qu'on lit, jamais au-delà. Pour deux,
     le recoupement : seulement dans l'une, dans les deux, seulement dans l'autre. */
  function comparer(collections, albums) {
    const cols = Array.isArray(collections) ? collections : [];
    const liste = Array.isArray(albums) ? albums : [];
    const dans = (cid) => liste.filter((a) => collectionsDe(a).some((c) => Number(c.id) === Number(cid)));
    const lignes = cols.map((c) => {
      const al = dans(c.id);
      return {
        id: Number(c.id), nom: c.nom, regime: c.statut_diffusion || null,
        albums: al.length,
        planches: al.reduce((s, a) => s + (Number(a.nb_planches) || 0), 0),
        validees: al.reduce((s, a) => s + (Number(a.nb_validees) || 0), 0),
        ids: al.map((a) => a.id),
      };
    });
    let recoupement = null;
    if (lignes.length === 2) {
      const a = new Set(lignes[0].ids);
      const communs = lignes[1].ids.filter((id) => a.has(id)).length;
      recoupement = { communs, seulA: lignes[0].albums - communs,
                      seulB: lignes[1].albums - communs };
    }
    return { lignes: lignes.map(({ ids: _, ...r }) => r), recoupement };
  }

  /* Le bouton du recoupement, qui passe le corpus en mode « toutes » : accordé au nombre
     (« les 1 en commun » se lisait). Aucun album en commun : pas de bouton, il mènerait à
     une liste vide — la pastille « dans les deux : 0 » le dit déjà. */
  function libelleCommuns(n) {
    const k = Number(n) || 0;
    if (k <= 0) return "";
    return k === 1 ? "Ne montrer que le seul en commun" : `Ne montrer que les ${k} en commun`;
  }

  function entier(v) {
    return typeof v === "string" && /^[1-9]\d*$/.test(v) ? Number(v) : null;
  }

  /* CE QUE L'ADRESSE OUVRE. `?collection=<id>` (déjà là depuis AUTH-12), `&onglet=<clé>`,
     `?album=<id>` — et `&groupe=<nom>`, qui présélectionne un groupe dans « Qui entre » :
     plus aucun lien de l'application n'y mène (UX-16), mais une adresse envoyée doit
     continuer d'ouvrir la bonne collection, sur l'onglet où le groupe se lit.

     Sans onglet nommé, une collection s'ouvre sur « Qui entre » (`ONGLET_PAR_LE_NOM`) :
     c'est ce que fait son NOM dans la liste — la case, elle, filtre le corpus et montre ses
     albums —, et c'est ce que l'adresse ouvrait depuis AUTH-12, cible des liens de
     l'Administration. Un album l'emporte : sa fiche s'ouvre À LA PLACE de celle de la
     collection, qui reste celle d'où l'on vient (le retour). Toute valeur illisible vaut
     absente. */
  function lireAdresse(search) {
    const p = new URLSearchParams(search || "");
    const collection = entier(p.get("collection"));
    const album = entier(p.get("album"));
    const groupe = collection !== null ? (p.get("groupe") || null) : null;
    const nomme = CLES_ONGLETS.includes(p.get("onglet")) ? p.get("onglet") : null;
    return { collection, album, onglet: nomme || ONGLET_PAR_LE_NOM, groupe };
  }

  /* L'adresse de ce qui est ouvert, sans toucher aux autres paramètres (`retour`, qui sert
     le bouton « ← Retour », et tout ce qu'un lien a pu ajouter). L'onglet par défaut ne
     s'écrit pas : une adresse courte reste celle qu'on recopie. `groupe` ne vaut que pour
     la fiche d'une collection, qu'il a ouverte. */
  function ecrireAdresse(etat, search) {
    const p = new URLSearchParams(search || "");
    ["collection", "album", "onglet", "groupe"].forEach((k) => p.delete(k));
    const e = etat || {};
    const aCollection = e.collection !== null && e.collection !== undefined;
    const aAlbum = e.album !== null && e.album !== undefined;
    if (aCollection) p.set("collection", String(e.collection));
    if (aAlbum) p.set("album", String(e.album));
    if (aCollection && !aAlbum && CLES_ONGLETS.includes(e.onglet)
        && e.onglet !== ONGLET_PAR_LE_NOM) {
      p.set("onglet", e.onglet);
    }
    if (aCollection && !aAlbum && e.groupe) p.set("groupe", e.groupe);
    const s = p.toString();
    return s ? `?${s}` : "";
  }

  /* ═══ COL-3, tranche 3a — les gestes de la prise (Hugo, sur maquette, 2026-10-17) ═══
     Ce qui suit choisit ce que l'écran OFFRE et ce qu'il DIT d'une réponse ; le serveur
     reste seul à trancher chaque geste (`POST …/prendre`, `PUT …/collections/{cid}`), et il
     refuse en le disant si l'écran s'est trompé. */

  /* « + Prendre du fonds… » s'offre au RESPONSABLE du projet et à l'administrateur, et à
     eux seuls (D3) : le serveur le dit projet par projet (`gerable`, `GET /api/projets`).
     Un écrivain d'une collection ne puise que dans ce qu'il lit déjà — « + Prendre dans le
     projet… ». `collection`, quand on offre le geste DANS une collection : il faut aussi y
     écrire, puisque c'est elle qui recevra. */
  function offrirPrendreDuFonds(projet, collection) {
    if (!projet || projet.gerable !== true) return false;
    return collection === undefined || collection === null || collection.ecrivable === true;
  }

  /* Où une prise peut arriver : les collections du projet où l'on écrit, la BASE en tête
     (D10 : ce que le projet prend au fonds y arrive), puis par nom. */
  function destinationsPrise(collections, projetId) {
    const l = (Array.isArray(collections) ? collections : [])
      .filter((c) => c && c.ecrivable === true
                     && (projetId === null || projetId === undefined || c.projet_id === projetId));
    return trierCollections(l, "alpha");
  }

  /* La destination présélectionnée : celle d'où l'on vient, si elle peut recevoir ; sinon
     la base ; sinon la seule ; sinon aucune (on choisit). C'est aussi la règle de « + Nouvel
     album » (la base, sauf si l'on vient d'une collection ouverte). */
  function destinationParDefaut(destinations, depuis) {
    const l = Array.isArray(destinations) ? destinations : [];
    if (depuis !== null && depuis !== undefined) {
      const ici = l.find((c) => Number(c.id) === Number(depuis));
      if (ici) return ici.id;
    }
    const base = l.find((c) => c.base);
    if (base) return base.id;
    return l.length === 1 ? l[0].id : null;
  }

  /* Qui répondra à un « rejoindre » : le serveur le dit (`repondra`, Hugo, 2026-10-17 : le
     message ne ment pas) — un propriétaire qui tient toutes les collections de la copie,
     sinon un administrateur. */
  function quiRepondra(repondra) {
    return repondra === "administrateur" ? "un administrateur" : "son propriétaire";
  }

  /* La réponse à UNE ligne d'une prise, écrite sur place : « fait », « demandé à … », ou le
     refus et sa raison. Une entrée de documents et un retour se répondent par un
     administrateur ; un rejoindre, par qui `repondra`. Jamais « fait » sans que le serveur
     l'ait dit. */
  function reponsePrise(ligne) {
    const l = ligne || {};
    if (l.etat === "fait") return { classe: "fait", texte: "fait" };
    if (l.etat === "demande") {
      return { classe: "demande",
               texte: `demandé à ${l.repondra ? quiRepondra(l.repondra) : "un administrateur"}` };
    }
    return { classe: "refuse", texte: l.motif ? `refusé : ${l.motif}` : "refusé" };
  }

  /* Ce que dit une case cochée de « Sur les collections » (cocher = rejoindre). `rep` : la
     réponse du serveur — la liste des collections (201, fait), ou `{etat: "demande",
     repondra}` (202). Un 202 ne range RIEN : la case passe « demandée », et la phrase le
     dit. */
  function messageRejoindre(titre, collection, rep) {
    if (rep && rep.etat === "demande") {
      return { fait: false,
               texte: rep.repondra === "administrateur"
                 ? "Pas rangé : rejoindre ce travail se demande, et aucun propriétaire ne tient "
                   + "toutes ses collections — un administrateur y répondra. La demande est partie."
                 : "Pas rangé : rejoindre ce travail se demande au propriétaire de ses "
                   + "collections. La demande est partie." };
    }
    return { fait: true,
             texte: `Fait : « ${titre} » est aussi rangé dans « ${collection} ». Le travail est partagé.` };
  }

  /* Les demandes de rejoindre REÇUES, comptées pour la marque ⚑ d'une collection, la
     pastille de son onglet Albums et le compteur de la bande d'outils : celles auxquelles
     on peut répondre (`repondable`), en propriétaire. Une portée totale n'en compte aucune
     ici — l'administrateur les lit dans « À faire », en recours (maquette, écran 3). La
     route rend aussi, depuis la tranche 3b, les demandes d'EN PARTIR (`genre: "amorcer"`) :
     leur écran attend sa maquette (E10), et le bloc ⚑ ne les montre pas sous les mots d'un
     rejoindre — une demande sans `genre` est un rejoindre, la forme d'avant la 3b. */
  function demandesARepondre(demandes, total) {
    if (total) return [];
    return (Array.isArray(demandes) ? demandes : []).filter(
      (d) => d && d.repondable === true && (d.genre === undefined || d.genre === "rejoindre"));
  }

  /* Si l'on pourrait RANGER de nouveau un album dans une collection qu'on vient de lui
     retirer — la règle de `clause_rejoindre_directe` côté serveur (D4 stricte), lue dans ce
     que l'écran sait : `"soi"` pour une portée totale, ou si l'on ADMINISTRE chacune des
     collections où il vit encore et qu'il ne vit nulle part ailleurs (`partage` faux) ;
     sinon `"demande"`. À qui irait la demande — un propriétaire qui les tient toutes, ou un
     administrateur — ne se lit pas d'ici (les propriétaires des autres collections ne sont
     pas publiés) : la phrase nomme les deux. `restantes` : ses collections qu'on lit, hors
     celle qu'on retire ; `collections` : `GET /api/collections`. */
  function quiRecocherait(album, restantes, collections, total) {
    if (total) return "soi";
    const admin = new Set((Array.isArray(collections) ? collections : [])
      .filter((c) => c && c.administrable).map((c) => Number(c.id)));
    const r = Array.isArray(restantes) ? restantes : [];
    return !(album && album.partage) && r.length && r.every((c) => admin.has(Number(c.id)))
      ? "soi" : "demande";
  }

  /* Ce sur quoi un lot travaille, en une ligne (UX-18) — lu dans `albums`, que
     `GET /api/jobs` rend lot par lot ({id, titre, nb_planches}) et borne déjà à ce qu'on
     lit. Un album : « 3 planches de « Titre » » ; plusieurs : leurs titres, trois au plus,
     et le total des planches. Rien quand le lot ne nomme plus rien (ses planches ont été
     détruites depuis) : l'écran garde alors « Lot #12 », sans inventer de sujet. */
  const MAX_ALBUMS_NOMMES = 3;
  function sujetDuLot(albums) {
    const liste = (albums || []).filter((a) => a && a.titre);
    if (!liste.length) return "";
    const planches = (n) => `${n} planche${n > 1 ? "s" : ""}`;
    const total = liste.reduce((s, a) => s + (a.nb_planches || 0), 0);
    if (liste.length === 1) return `${planches(total)} de « ${liste[0].titre} »`;
    const noms = liste.slice(0, MAX_ALBUMS_NOMMES).map((a) => `« ${a.titre} »`);
    const reste = liste.length - noms.length;
    const enumeres = reste
      ? `${noms.join(", ")} et ${reste} autre${reste > 1 ? "s" : ""} album${reste > 1 ? "s" : ""}`
      : `${noms.slice(0, -1).join(", ")} et ${noms[noms.length - 1]}`;
    return `${enumeres} — ${planches(total)}`;
  }

  return { ONGLETS, CLES_ONGLETS, ONGLET_PAR_LE_NOM, TRIS, MODES, plier, filtrerAlbums, trierCollections,
           droitsAlbum, actesCollection, aussiDans, libelleAlbums, comparer, libelleCommuns, lireAdresse,
           ecrireAdresse, offrirPrendreDuFonds, destinationsPrise, destinationParDefaut,
           quiRepondra, reponsePrise, messageRejoindre, demandesARepondre, quiRecocherait,
           sujetDuLot };
});
