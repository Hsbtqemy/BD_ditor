/* CTRL+Z, la partie COMMUNE à l'Atelier et à la page Annotation (D1, ANN-8 ; ANN-7,
   tranche 2 : sortie de `viewer.js` pour ne pas être recopiée — `docs/ann7-tranche2-cadrage.md`,
   « Ctrl+Z »). Chargé en <script> → `window.BDAnnulation` ; require()-able par
   `tests/js/annulation.test.js`. Rien n'est lu au chargement : le document ne sert qu'à
   l'appel (la boîte des messages, pour « Passer ce geste »).

   L'annulation est celle de l'AGENT, pas de la page : le serveur porte la pile (le journal
   A3), et le dernier geste peut avoir été fait sur l'autre surface, ou sur une autre planche.
   Ce module appelle, dit ce qui s'est passé — le message lent du premier appel, « Annulé : … »
   et ce qui n'a pas été rendu, le refus de CONC-3 et « Passer ce geste » —, et rend la
   réponse : chaque surface RAFRAÎCHIT ce qu'elle montre, elle seule le sait. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module !== "undefined" && module.exports) module.exports = api;   // Node (tests)
  else root.BDAnnulation = api;                                                // navigateur
})(typeof self !== "undefined" ? self : this, function (root) {
  "use strict";

  /* Le premier Ctrl+Z après un redémarrage peut attendre le moteur de langue (9 à 17 s
     mesurés, ANN-8) sans rien afficher : passé un instant, l'écran le dit ; l'attente
     ordinaire (quelques centièmes) ne montre rien. */
  const ANNULATION_LENTE = "Annulation en cours — le premier appel charge le moteur de langue.";
  const ANNULATION_LENTE_MS = 1500;
  const PASSER_DUREE_MS = 15000;

  function conflitApi() {
    if (root && root.BDConflit) return root.BDConflit;
    if (typeof require === "function") return require("./conflit.js");
    return null;
  }

  const pluriel = (n, un, plusieurs) => (n > 1 ? plusieurs : un);

  /* CE QUE DIT un Ctrl+Z réussi, et combien de temps : « Annulé : … », puis ce qui n'a pas
     été rendu — des liens (personnage ou valeur disparus), des tags (Ctrl+Z ne recrée jamais
     un tag, ANN-8), des relevés (grille désactivée ou entrée disparue depuis, ANN-7). */
  function messageAnnule(res) {
    const r = res || {};
    const liens = r.liens_non_rendus || 0;
    const tags = r.tags_non_rendus || 0;
    const releves = r.releves_non_rendus || 0;
    let t = "Annulé : " + (r.description || "le dernier geste");
    if (liens) {
      t += ` — ${liens} ${pluriel(liens, "lien non rendu", "liens non rendus")} (personnage ou valeur disparus, ou type qui ne les montre pas)`;
    }
    if (tags) {
      t += ` — ${tags} ${pluriel(tags, "tag non rendu", "tags non rendus")} (${pluriel(tags, "supprimé", "supprimés")} depuis, ou hors de portée)`;
    }
    if (releves) {
      t += ` — ${releves} ${pluriel(releves, "relevé non rendu", "relevés non rendus")} (grille désactivée ou entrée disparue depuis)`;
    }
    return { texte: t, duree: liens || tags || releves ? 8000 : 4000 };
  }

  /* « PASSER CE GESTE » : Ctrl+Z refusé par un conflit laisse l'acte en tête de la pile, et
     chaque Ctrl+Z redonnait le même refus. Le message offre de le passer : le serveur pose
     la trace qui le sort de la pile (`POST /api/undo/passer`), le travail de l'autre reste,
     et le Ctrl+Z suivant remonte au geste d'avant. Le serveur revérifie que l'acte est
     encore le prochain et que le conflit tient. `env` : `{ apiSend, toast, document }`. */
  function offrirDePasser(message, evenementId, env) {
    const e = env || {};
    // `toast` nu, comme sur les surfaces : `tests/test_toasts.py` lit ses classes.
    const { apiSend, toast } = e;
    const doc = e.document || (typeof document !== "undefined" ? document : null);
    const box = doc && doc.getElementById("toasts");
    if (!box) { toast(message, "error", 8000); return null; }
    const el = doc.createElement("div");
    el.className = "toast error toast-action";
    const texte = doc.createElement("span");
    texte.textContent = message + " ";
    const bouton = doc.createElement("button");
    bouton.type = "button";
    bouton.textContent = "Passer ce geste";
    bouton.title = "Ctrl+Z remontera au geste d'avant ; le travail de l'autre reste.";
    const fermer = () => el.remove();
    const minuterie = setTimeout(fermer, PASSER_DUREE_MS);
    bouton.onclick = async () => {
      clearTimeout(minuterie);
      bouton.disabled = true;
      try {
        const res = await apiSend("POST", "/api/undo/passer", { evenement_id: evenementId });
        fermer();
        toast(`Geste passé : ${res.description}. Ctrl+Z remonte au geste d'avant.`, "", 6000);
      } catch (err) {
        fermer();
        toast(err.message, "error", 8000);
      }
    };
    el.append(texte, bouton);
    box.appendChild(el);
    return el;
  }

  /* ANNULER le dernier geste de l'agent. `env` : `{ apiSend, toast, document? }`. Rend la
     réponse du serveur (`planche_id`, `region_id`, …) si un geste a été défait, `null`
     sinon — refus, rien à annuler, panne : le message est déjà dit. */
  async function annuler(env) {
    const e = env || {};
    const { apiSend, toast } = e;
    const lent = setTimeout(() => toast(ANNULATION_LENTE), ANNULATION_LENTE_MS);
    let res;
    try {
      res = await apiSend("POST", "/api/undo");
    } catch (err) {
      if (err && err.statut === 409 && err.detail && err.detail.conflit) {
        // CONC-3 : annuler écraserait ce qu'un autre a changé depuis. L'acte reste en tête
        // de la pile ; le message offre de le PASSER (décision de Hugo du 2026-10-22).
        const C = conflitApi();
        const message = C ? C.messageAnnulationRefusee(err.detail.conflit) : err.message;
        if (err.detail.passable) offrirDePasser(message, err.detail.passable.evenement_id, e);
        else toast(message, "error", 8000);
        return null;
      }
      const m = (err && err.message) || "Annulation impossible.";
      toast(m, /rien à annuler/i.test(m) ? "" : "error");
      return null;
    } finally { clearTimeout(lent); }
    const dit = messageAnnule(res);
    toast(dit.texte, "", dit.duree);
    return res;
  }

  /* Le raccourci : Ctrl/⌘+Z hors d'un champ de saisie (dans un champ, l'annulation native). */
  function estRaccourci(ev) {
    if (!ev || !(ev.ctrlKey || ev.metaKey) || ev.shiftKey) return false;
    if (String(ev.key || "").toLowerCase() !== "z") return false;
    const t = ev.target || {};
    const tag = String(t.tagName || "").toLowerCase();
    return !(tag === "input" || tag === "textarea" || tag === "select");
  }

  return { ANNULATION_LENTE, ANNULATION_LENTE_MS, PASSER_DUREE_MS, messageAnnule,
           offrirDePasser, annuler, estRaccourci };
});
