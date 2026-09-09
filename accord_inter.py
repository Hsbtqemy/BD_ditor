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

**Un agent COLLECTIF n'est pas mesurable, et c'est écrit ici plutôt que découvert** (AUTH-6,
2026-09-09). Le cadrage a décidé des logins PARTAGÉS — groupes d'étudiants, stagiaires,
démos —, et cette mesure repose entièrement sur l'hypothèse « un agent = une personne ».
Deux choses cassent, dont une qui cassait DÉJÀ sans que rien ne le dise :

· Deux personnes qui se relisent sous le MÊME login ne produisent aucun désaccord
  mesurable — la condition de re-touche est `agent_précédent != agent`, donc ces
  révisions ne sont pas comptées comme des accords : elles SORTENT de l'échantillon.
  L'écart ne se voit nulle part, et le taux affiché porte alors sur moins de travail qu'on
  ne croit. C'est le mode d'échec d'ARCH-2 — une mesure qui rétrécit en silence — et le
  seul remède est de COMPTER ce qu'on ne peut pas mesurer.
· Une paire (personne, groupe) prête à un GROUPE le comportement d'un annotateur. Le taux
  aurait un sens statistique et aucun sens scientifique : on ne peut pas réunir « le
  groupe » pour arbitrer une divergence, ce qui est l'usage entier de ce rapport.

D'où `non_attribuable` : ces révisions sont retirées des taux et RAPPORTÉES à part. Refuser
de répondre est le résultat correct ; rendre un chiffre serait l'erreur.
"""
import json

import database

CHAMPS = ("lemme", "pos", "morph")


def agents_collectifs(conn) -> set:
    """Les logins DÉCLARÉS collectifs (AUTH-6, `utilisateur.nature`).

    Lecture directe et sans repli : si la table manquait, un ensemble vide dirait « aucun
    compte partagé », ce qui est précisément l'affirmation fausse que cette colonne existe
    pour empêcher. Mieux vaut l'erreur bruyante — la table est créée par `SCHEMA_SQL`
    depuis la v22 et toute connexion passe par les migrations.
    """
    return {r["login"] for r in conn.execute(
        "SELECT login FROM utilisateur WHERE nature = ?", (database.NATURE_COLLECTIF,))}


def rapport(conn, divergence_limit: int = 50, album_ids=None) -> dict:
    """Rapport d'accord inter-annotateurs (dict sérialisable). `divergence_limit` borne la
    liste détaillée (les compteurs, eux, portent sur tout).

    `album_ids` (None = corpus entier) RESTREINT aux corrections dont la région appartient
    à l'un de ces albums — même contrat que `accord.rapport`, et c'est par là que passe le
    cloisonnement d'AUTH-2. Une liste VIDE (aucun album lisible) → rapport vide.

    Une limite à connaître quand on scope : le journal SURVIT à la suppression de sa cible
    (`cible_id` n'est pas une FK, c'est le substrat de l'undo). Une correction effacée n'a
    donc plus de région, donc plus d'album — elle sort de l'échantillon dès qu'on restreint,
    alors qu'elle comptait dans le rapport global. C'est le prix du filtre, et il vaut mieux
    que l'alternative : rattacher un événement orphelin à un album par défaut.
    """
    ou, params = "", []
    if album_ids is not None:
        if album_ids:
            qm = ",".join("?" * len(album_ids))
            ou = (f"  AND cible_id IN (SELECT tc.id FROM token_correction tc "
                  f"     JOIN regions r ON r.id = tc.region_id "
                  f"     JOIN planches p ON p.id = r.planche_id "
                  f"    WHERE p.album_id IN ({qm})) ")
            params = list(album_ids)
        else:
            ou = "  AND 0 "                     # aucun album lisible → rapport vide
    events = conn.execute(
        "SELECT cible_id, agent, avant, apres FROM evenement "
        "WHERE cible_table = 'token_correction' AND agent_type = 'humain' "
        "  AND type IN ('creation', 'modification') AND agent IS NOT NULL "
        + ou +
        "ORDER BY cible_id, date, id", params).fetchall()

    collectifs = agents_collectifs(conn)
    champs = {ch: {"retouches": 0, "accords": 0} for ch in CHAMPS}
    paires = {}                                  # (a, b) triés → {retouches, accords}
    divergences = []
    prev = {}                                    # cible_id → agent précédent (chaîne humaine)
    # Ce que la mesure REFUSE de trancher, compté plutôt que perdu (AUTH-6).
    internes = 0        # re-touche sous le MÊME login collectif — invisible jusqu'ici
    avec_collectif = 0  # paire dont au moins un côté est un groupe
    vus = set()         # les agents de CET échantillon, cf. la sortie plus bas
    for e in events:
        cid, agent = e["cible_id"], e["agent"]
        vus.add(agent)
        anterieur = prev.get(cid)
        if anterieur is not None and anterieur == agent and agent in collectifs:
            # Sous un login partagé, « le même agent » ne veut pas dire « la même
            # personne ». On ne peut pas savoir si c'est une relecture par un tiers ou une
            # correction de soi-même, donc on ne mesure rien — mais on cesse de l'ignorer.
            internes += 1
        elif anterieur is not None and anterieur != agent and (
                anterieur in collectifs or agent in collectifs):
            avec_collectif += 1
        elif anterieur is not None and anterieur != agent:  # re-touche INTER-annotateurs
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
        # AUTH-6 — ce que le rapport a VU sans pouvoir le mesurer. Toujours présent, même à
        # zéro : une clé qui n'apparaîtrait qu'en cas de problème ferait lire son absence
        # comme une absence de problème, alors qu'elle signifierait « je n'ai pas regardé ».
        #
        # RESTREINT AUX AGENTS DE L'ÉCHANTILLON, et pas seulement par exactitude. Cette
        # route est cloisonnable par `album_ids` (AUTH-2) ; rendre ici tous les comptes
        # collectifs de l'instance publierait des logins de groupes à quelqu'un qui ne lit
        # que ses propres albums — une voie de sortie d'identité neuve, que le cliquet
        # d'AUTH-5 ne pouvait pas voir puisque sa sentinelle n'est pas déclarée collective.
        # Et le rapport doit de toute façon décrire SON échantillon, jamais l'instance.
        "non_attribuable": {
            "agents_collectifs": sorted(collectifs & vus),
            "revisions_internes": internes,
            "revisions_avec_collectif": avec_collectif,
        },
        "champs": {ch: {**champs[ch], "taux": _taux(champs[ch]["accords"], champs[ch]["retouches"])}
                   for ch in CHAMPS},
        "paires": [{"a": a, "b": b, "retouches": p["retouches"], "accords": p["accords"],
                    "taux": _taux(p["accords"], p["retouches"])}
                   for (a, b), p in sorted(paires.items())],
        "divergences": divergences, "divergences_tronque": tronque,
    }
