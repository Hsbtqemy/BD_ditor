"""Accord inter-annotateurs (ANN-5) — cœur partagé.

Le modèle ne garde qu'UNE correction courante par token (avec son `auteur`, INFRA-2). La donnée
multi-auteurs vit donc dans le journal A3 (`evenement`), où chaque correction de token est un
événement avec son agent + `avant`/`après`, et où `cible_id` (l'id de la correction) est STABLE
(ON CONFLICT DO UPDATE) → une CHAÎNE de révisions par token.

Ce n'est pas de l'annotation parallèle indépendante : on mesure l'accord de RÉVISION. Quand un
annotateur RE-TOUCHE le token laissé par un AUTRE, garde-t-il (accord) ou change-t-il
(divergence) la valeur, par champ (lemme/POS/morpho) ? L'événement porte déjà `avant` (valeur du
précédent) et `après` (du courant) ; l'agent précédent de la chaîne donne l'identité.

Rapport : taux d'accord par champ + par PAIRE d'auteurs + liste des points de divergence
(citation, champ, qui a mis quoi). Rare tant qu'on n'est pas multi-utilisateur (piste C) — la
capacité est prête. Partagé par `GET /api/analyse/accord-inter` et `tools/rapport_accord_inter.py`.
"""
import json

import database

CHAMPS = ("lemme", "pos", "morph")


def rapport(conn, divergence_limit: int = 50) -> dict:
    """Rapport d'accord inter-annotateurs (dict sérialisable). `divergence_limit` borne la
    liste détaillée (les compteurs, eux, portent sur tout)."""
    events = conn.execute(
        "SELECT cible_id, agent, avant, apres FROM evenement "
        "WHERE cible_table = 'token_correction' AND agent_type = 'humain' "
        "  AND type IN ('creation', 'modification') AND agent IS NOT NULL "
        "ORDER BY cible_id, date, id").fetchall()

    champs = {ch: {"retouches": 0, "accords": 0} for ch in CHAMPS}
    paires = {}                                  # (a, b) triés → {retouches, accords}
    divergences = []
    prev = {}                                    # cible_id → agent précédent (chaîne humaine)
    for e in events:
        cid, agent = e["cible_id"], e["agent"]
        anterieur = prev.get(cid)
        if anterieur is not None and anterieur != agent:    # re-touche INTER-annotateurs
            avant = json.loads(e["avant"]) if e["avant"] else {}
            apres = json.loads(e["apres"]) if e["apres"] else {}
            diffs = []
            for ch in CHAMPS:
                champs[ch]["retouches"] += 1
                if avant.get(ch) == apres.get(ch):
                    champs[ch]["accords"] += 1
                else:
                    diffs.append({"champ": ch, "avant": avant.get(ch), "apres": apres.get(ch)})
            p = paires.setdefault(tuple(sorted((anterieur, agent))),
                                  {"retouches": 0, "accords": 0})
            p["retouches"] += 1
            if not diffs:                        # accord au niveau ÉVÉNEMENT = aucun champ changé
                p["accords"] += 1
            else:
                divergences.append({"cible_id": cid, "de": anterieur, "a": agent, "diffs": diffs})
        prev[cid] = agent

    retouches = max((c["retouches"] for c in champs.values()), default=0)

    # Résolution des divergences → citation (le token_correction peut avoir disparu : le journal
    # lui survit → citation None). Bornée à `divergence_limit`.
    tronque = len(divergences) > divergence_limit
    divergences = divergences[:divergence_limit]
    cids = [d["cible_id"] for d in divergences]
    infos, cits = {}, {}
    if cids:
        qm = ",".join("?" * len(cids))
        infos = {r["id"]: dict(r) for r in conn.execute(
            f"SELECT id, region_id, ordre, forme FROM token_correction WHERE id IN ({qm})", cids)}
        cits = database.citations_regions(conn, [i["region_id"] for i in infos.values()])
    for d in divergences:
        info = infos.get(d["cible_id"])
        d["forme"] = info["forme"] if info else None
        d["citation"] = cits.get(info["region_id"]) if info else None

    def _taux(a, r):
        return round(a / r, 4) if r else None

    return {
        "retouches": retouches,
        "auteurs": sorted({a for cle in paires for a in cle}),
        "champs": {ch: {**champs[ch], "taux": _taux(champs[ch]["accords"], champs[ch]["retouches"])}
                   for ch in CHAMPS},
        "paires": [{"a": a, "b": b, "retouches": p["retouches"], "accords": p["accords"],
                    "taux": _taux(p["accords"], p["retouches"])}
                   for (a, b), p in sorted(paires.items())],
        "divergences": divergences, "divergences_tronque": tronque,
    }
