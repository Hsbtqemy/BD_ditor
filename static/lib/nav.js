/* Helpers de navigation partagés par les trois surfaces (Visionneuse / Recherche /
   Exploration). Chargé en <script> AVANT le script de page → expose `window.Nav` ;
   aussi require()-able par les tests Node (UMD minimal, pas de build).
   Cf. docs/navigation-round-trip.md. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;  // Node (tests)
  else root.Nav = api;                                                        // navigateur
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* `retour` ne doit viser qu'une page INTERNE (chemin relatif) : on rejette les URL
     absolues, protocol-relative (//evil) et les schémas dangereux (javascript:/data:)
     → pas d'open-redirect ni d'XSS via le href du bouton « ← Retour ». Accepte un
     chemin commençant par « / » non suivi de « / » ni « \ ». */
  const safeRetour = (v) =>
    (typeof v === "string" && /^\/(?![/\\])/.test(v)) ? v : null;

  /* ── Reprise d'état par la session (INFRA-5) ──────────────────────────────────────
     L'adresse couvre le rechargement et le partage ; revenir sur la Recherche ou
     l'Exploration PAR LE MENU, lui, repartait d'un état vide. La page mémorise donc son
     dernier état dans le stockage de SESSION — propre à l'onglet, perdu à sa fermeture :
     deux onglets ne se volent pas leur recherche — et le reprend quand on arrive sans
     rien dire.

     L'ADRESSE L'EMPORTE TOUJOURS. Une adresse qui porte un état — un lien partagé, le
     rechargement, un deep-link de concordance (B2) — est servie telle quelle ; la
     mémoire ne sert qu'à une adresse NUE. Sans cette règle, un lien envoyé s'ouvrirait
     sur la dernière recherche de qui le reçoit.

     `retour` n'est pas un état mais un CONTEXTE d'arrivée (d'où l'on vient) : il ne
     rend pas une adresse explicite, ne se mémorise pas — revenu par le menu, un
     « ← Retour » d'une visite passée ne mènerait nulle part de voulu — et celui de
     l'adresse est gardé quand la mémoire la complète.

     Le stockage peut MANQUER : navigation privée, données de site bloquées, quota. Son
     accès même peut lever (`window.sessionStorage` jette une SecurityError quand le site
     est bloqué). Toute lecture et toute écriture passent donc sous try/catch, et la page
     dégrade vers ce qu'elle faisait avant : l'état vide. */
  const CLE_ETAT = "bd-etat:";
  const CONTEXTE = ["retour"];

  function stockageDeSession(fenetre) {
    try { return (fenetre && fenetre.sessionStorage) || null; } catch (e) { return null; }
  }

  function sansContexte(qs) {
    const p = new URLSearchParams(qs || "");
    for (const k of CONTEXTE) p.delete(k);
    return p.toString();
  }

  function adresseExplicite(qs) {
    return [...new URLSearchParams(qs || "").keys()].some((k) => !CONTEXTE.includes(k));
  }

  /* L'état de départ d'une page : `{ qs, source }`, `source` ∈ adresse | memoire | vide.
     `qs` se lit comme `location.search` (avec son « ? », ou vide). */
  function etatDeDepart(qs, stockage, page) {
    const adresse = qs || "";
    if (adresseExplicite(adresse)) return { qs: adresse, source: "adresse" };
    let memo = null;
    try { memo = stockage ? stockage.getItem(CLE_ETAT + page) : null; } catch (e) { memo = null; }
    const m = new URLSearchParams(typeof memo === "string" ? sansContexte(memo) : "");
    if (![...m.keys()].length) return { qs: adresse, source: "vide" };
    const venu = new URLSearchParams(adresse);
    for (const k of CONTEXTE) if (venu.has(k)) m.set(k, venu.get(k));
    return { qs: "?" + m.toString(), source: "memoire" };
  }

  /* Retient l'état COURANT de la page (sans son contexte). Rien ne lève : un stockage
     plein ou refusé laisse simplement la page sans mémoire. */
  function memoriser(stockage, page, qs) {
    if (!stockage) return;
    try { stockage.setItem(CLE_ETAT + page, sansContexte(qs)); } catch (e) { /* sans mémoire */ }
  }

  /* ── Le LIEU partagé : l'Atelier et la page Annotation (ANN-7, tranche 2, commit 7) ──
     Hugo, 2026-10-30 : passer de l'un à l'autre PAR LA NAVIGATION garde le même album, la
     même planche et la même zone. Chacune écrit le lieu où elle est (`retenirLieu`, dans le
     stockage de SESSION, clé `bd-lieu`) ; arrivée sur une adresse NUE, chacune part de sa
     propre mémoire — ce qui lui est propre, la grille de la page Annotation — et y pose le
     lieu (`etatAvecLieu`). L'ADRESSE L'EMPORTE TOUJOURS, comme pour `etatDeDepart`. La zone
     ne suit que si elle a un sens des deux côtés : la page Annotation ne l'écrit pas pour la
     planche entière (la case pseudo n'est pas une région), et un lieu sans zone en retire
     une qu'une mémoire aurait gardée d'une autre planche. */
  const CLE_LIEU = "bd-lieu";
  const CLES_LIEU = ["album", "planche", "region"];

  function retenirLieu(stockage, qs) {
    if (!stockage) return;
    const p = new URLSearchParams(qs || "");
    const lieu = new URLSearchParams();
    for (const k of CLES_LIEU) if (p.get(k)) lieu.set(k, p.get(k));
    try {
      if (lieu.get("album")) stockage.setItem(CLE_LIEU, lieu.toString());
    } catch (e) { /* sans mémoire */ }
  }

  function etatAvecLieu(qs, stockage, page) {
    const depart = etatDeDepart(qs, stockage, page);
    if (depart.source === "adresse") return depart;
    let brut = null;
    try { brut = stockage ? stockage.getItem(CLE_LIEU) : null; } catch (e) { brut = null; }
    const lieu = new URLSearchParams(typeof brut === "string" ? brut : "");
    if (!lieu.get("album")) return depart;
    const m = new URLSearchParams(depart.qs || "");
    for (const k of CLES_LIEU) {
      if (lieu.get(k)) m.set(k, lieu.get(k)); else m.delete(k);
    }
    return { qs: "?" + m.toString(), source: "lieu" };
  }

  /* « Annoter ↗ » (H2 du cadrage d'ANN-7, tranche 2) : de l'Atelier vers la page Annotation,
     le même album, la même planche, la zone courante, la collection choisie, et le retour
     vers l'Atelier (`retour`, borné comme partout) — le pendant de « Ouvrir dans l'Atelier ↗ ».
     Le mode Annotation de l'Atelier reste : son sort se règle au basculement (tranche 3). */
  function lienAnnotation(etat, retour) {
    const p = new URLSearchParams();
    for (const k of ["album", "planche", "region", "collection"]) {
      const v = etat ? etat[k] : null;
      if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
    }
    const sur = safeRetour(retour);
    if (sur) p.set("retour", sur);
    const qs = p.toString();
    return "/annotation" + (qs ? "?" + qs : "");
  }

  return { safeRetour, CLE_ETAT, stockageDeSession, adresseExplicite, etatDeDepart, memoriser,
           CLE_LIEU, retenirLieu, etatAvecLieu, lienAnnotation };
});
