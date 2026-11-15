"""La MONTÉE DE VERSION d'une grille fermée (ANN-7 ; cadrage
`docs/ann7-montee-de-version-cadrage.md`, tranché par Hugo le 2026-11-15, les sept questions
comme proposé).

Monter, c'est faire passer les relevés d'un PROJET d'une version publiée à une version publiée
PLUS RÉCENTE (M5 : on ne revient pas ; pour revenir, on publie une version qui reprend
l'ancienne, puis on monte). Un relevé garde toutes ses valeurs — variante, cases, précision,
lien, passage, auteur, dates — : la montée ne réécrit que sa version, son drapeau `une`, et son
entrée quand on la fusionne. Ce qui ne convient plus à la version d'arrivée se DIT par l'état
dérivé (`releves_effectifs`, la règle de `grilles.causes_dans_la_version`), jamais corrigé en
silence.

LE PÉRIMÈTRE est le projet, écrit dès maintenant : les relevés et les passes dont l'album est du
projet (`database.sql_projet_d_album`, copies gardées au fonds comprises). Aujourd'hui c'est la
grille entière ; le jour du catalogue, deux projets tiendront la même grille dans deux versions,
et une montée écrite « par grille » déplacerait les relevés de l'autre. Tout ce qui suit lit et
écrit par identifiant, depuis la liste des relevés du projet — jamais par `grille_id` seul.

CE QUI SE DÉCIDE avant de monter (le bilan, `bilan`) :
- une entrée employée RETIRÉE dans la version d'arrivée (ou qui en a disparu) attend sa
  réponse — « laisser » (ses relevés passent, à revoir) ou « fusionner dans… » une entrée de la
  version d'arrivée (M2), aux règles de la fusion d'une grille ouverte
  (`grille_import._vers_possibles`) et sans fabriquer de doublon ;
- une cible qui porterait deux relevés d'une entrée qui ne s'y pose plus qu'une fois refuse la
  montée (M1), cible par cible, tant qu'on n'en a pas retiré un ;
- une version qui n'est pas publiée, ou plus ancienne que celle des relevés, se refuse (M5).

LES PASSES « terminée » (M4 c) : une passe se ROUVRE quand la version d'arrivée lui ajoute
quelque chose à regarder sur SA zone — une entrée née, entrée dans sa rubrique, ou dont
« Porte sur » s'élargit au type de la zone. Une passe dont la rubrique n'existe plus part.
Toute autre passe reste, sa version portée à l'arrivée.

LE JOURNAL : un acte `lien` sous `grille` (l'activation, sa charge dit la montée) ; un acte
`fusion` par relevé fusionné (`grille_import.journaliser_fusion`) ; un acte `passe_rouverte`
par passe rouverte, marqué `montee` dans sa charge — ni Ctrl+Z ne l'offre, ni « qui perd
quoi » ne le compte (`grilles.sql_acte_qui_range`). Aucun acte par relevé qui change seulement
de version : l'acte de grille, daté, dit qu'avant lui les relevés étaient dans l'autre version.

Le droit de l'appelant est vérifié AVANT (gérer le projet) ; ni commit, ni verrou : l'appelant
tient la transaction, comme pour `grille_import.activer`.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3

import grilles

LAISSER = "laisser"
FUSIONNER = "fusionner"
# Combien de zones le bilan nomme par cause, au plus : les autres sont comptées.
ZONES_PAR_CAUSE = 50


def _refus(statut: int, message: str, anomalies=None, bilan=None):
    from grille_import import Refus                 # import paresseux : grille_import nous lit
    return Refus(statut, message, anomalies, bilan)


def lire_reponses(reponses) -> dict:
    """Les réponses aux entrées retirées : `{cle: "laisser"}` ou `{cle: "fusionner:<cle>"}`.
    Lève `Refus` (422) sur une réponse qui n'est ni l'une ni l'autre."""
    sortie = {}
    for cle_, r in (reponses or {}).items():
        if isinstance(r, str) and r == LAISSER:
            sortie[cle_] = (LAISSER, None)
        elif isinstance(r, str) and r.startswith(FUSIONNER + ":") and r[len(FUSIONNER) + 1:]:
            sortie[cle_] = (FUSIONNER, r[len(FUSIONNER) + 1:])
        else:
            raise _refus(422, f"La réponse pour « {cle_} » n'est ni « laisser » ni "
                              "« fusionner:<identifiant> ».")
    return sortie


# --------------------------------------------------------------------------- #
# Ce que le projet porte de la grille
# --------------------------------------------------------------------------- #
def _sql_du_projet(alias: str) -> str:
    """Le `FROM … WHERE` des lignes (`releve` ou `passe`, alias `alias`) d'une grille dont
    l'album est du projet : deux `?`, la grille puis le projet."""
    from database import sql_projet_d_album         # import paresseux, cf. `_refus`
    return (f"LEFT JOIN regions g ON g.id = {alias}.region_id "
            f"JOIN planches p ON p.id = COALESCE(g.planche_id, {alias}.planche_id) "
            f"JOIN albums a ON a.id = p.album_id "
            f"WHERE {alias}.grille_id = ? AND {sql_projet_d_album('a')} = ?")


def releves_du_projet(conn: sqlite3.Connection, projet_id: int, grille_id: int) -> list:
    """Les relevés de la grille dont l'album est du projet, chacun sous la forme que lit la
    règle (`grilles.causes_dans_la_version`), avec son identifiant, sa version, son drapeau
    `une`, sa zone (`region_id`, `planche_id` : la planche où il vit) et son album, et les
    causes qui ne dépendent pas de la version (`texte`, lues dans `releves_effectifs`)."""
    lignes = conn.execute(
        "SELECT r.id, r.region_id, r.planche_id AS surface, r.version_id, r.entree_cle, "
        "r.variante_cle, r.precision, r.lien_region_id, r.une, g.type AS type_region, "
        "p.id AS planche_id, p.album_id, "
        "EXISTS (SELECT 1 FROM releve_mot m WHERE m.releve_id = r.id) AS sur_des_mots "
        f"FROM releve r {_sql_du_projet('r')} ORDER BY r.id", (grille_id, projet_id)).fetchall()
    ids = [x["id"] for x in lignes]
    qualifs, texte = {}, {}
    for i in range(0, len(ids), 500):
        tranche = ids[i:i + 500]
        marques = ", ".join("?" * len(tranche))
        for rid, q in conn.execute(f"SELECT releve_id, qualificatif_cle FROM releve_qualificatif "
                                   f"WHERE releve_id IN ({marques}) ORDER BY qualificatif_cle",
                                   tranche):
            qualifs.setdefault(rid, []).append(q)
        for x in conn.execute(f"SELECT id, mot_perdu, texte_change, lien_perdu FROM "
                              f"releves_effectifs WHERE id IN ({marques})", tranche):
            texte[x["id"]] = [c for c in grilles.CAUSES_A_REVOIR_DU_TEXTE if x[c]]
    return [{"id": x["id"], "region_id": x["region_id"], "planche_id": x["planche_id"],
             "album_id": x["album_id"], "version_id": x["version_id"], "une": x["une"],
             "entree_cle": x["entree_cle"], "planche": x["surface"] is not None,
             "type_region": x["type_region"], "mots": bool(x["sur_des_mots"]),
             "variante_cle": x["variante_cle"], "qualificatifs": qualifs.get(x["id"], []),
             "precision": x["precision"], "lien_region_id": x["lien_region_id"],
             "texte": texte.get(x["id"], [])} for x in lignes]


def passes_du_projet(conn: sqlite3.Connection, projet_id: int, grille_id: int) -> list:
    """Les passes de la grille dont l'album est du projet, avec le type de leur zone (None
    pour la planche) et leur album."""
    return [dict(x) for x in conn.execute(
        "SELECT ps.id, ps.region_id, ps.planche_id AS surface, ps.version_id, ps.rubrique_cle, "
        "ps.par, g.type AS type_region, p.id AS planche_id, p.album_id "
        f"FROM passe ps {_sql_du_projet('ps')} ORDER BY ps.id", (grille_id, projet_id))]


# --------------------------------------------------------------------------- #
# Les règles
# --------------------------------------------------------------------------- #
def _cible(r) -> tuple:
    """La cible d'un relevé, pour compter ce qu'elle porte : sa région, ou sa planche."""
    return ("r", r["region_id"]) if r["region_id"] is not None else ("p", r["planche_id"])


def _une(c: dict, cle_: str) -> bool:
    """L'entrée `cle_` de la version `c` ne se pose-t-elle qu'une fois ? Absente : non."""
    e = c["entrees"].get(cle_)
    if e is None:
        return False
    return grilles.cardinalite_effective(
        e, grilles.cibles_de(e.get("cible")) or grilles.cibles_de(c.get("cible"))) == "une"


def _en_double(releves: list, finale: dict, arrivee: dict, fusionnes=frozenset()) -> dict:
    """Les cibles qui se contrediraient après la montée, `{(cible, entrée): (genre, [ids])}`
    — deux relevés d'une entrée « une seule fois » (M1, `cardinalite_contredite`) ; ou, pour
    une entrée « plusieurs », la même variante deux fois sur une cible ENTIÈRE dont l'un est
    FUSIONNÉ (`fusion_en_double` : le doublon de J3, qu'une fusion ne doit pas fabriquer ; un
    doublon d'avant J3, que rien ne fusionne, n'est pas l'affaire de la montée). `finale` :
    l'entrée de chaque relevé après la montée ; `fusionnes` : les relevés qu'une fusion
    déplace."""
    groupes: dict = {}
    for r in releves:
        groupes.setdefault((_cible(r), finale[r["id"]]), []).append(r)
    sortie = {}
    for (cible, cle_), rs in groupes.items():
        if len(rs) < 2:
            continue
        if _une(arrivee, cle_):
            sortie[(cible, cle_)] = ("cardinalite_contredite", [r["id"] for r in rs])
            continue
        vues: dict = {}
        for r in rs:
            if r["mots"] or not r["variante_cle"]:
                continue
            vues.setdefault(r["variante_cle"], []).append(r["id"])
        for ids in vues.values():
            if len(ids) > 1 and set(ids) & set(fusionnes):
                sortie[(cible, cle_)] = ("fusion_en_double", ids)
    return sortie


def _dans_la_rubrique(c: dict, e: dict, rubrique_cle: str) -> bool:
    return (rubrique_cle == ""
            or rubrique_cle in grilles.chemin_de_rubrique(c["rubriques"], e.get("rubrique_cle")))


def _se_pose_sur(c: dict, e: dict, type_region) -> bool:
    """L'entrée `e` de la version `c` se pose-t-elle sur une zone de ce type (None : la
    planche) ?"""
    cibles = grilles.cibles_de(e.get("cible")) or grilles.cibles_de(c.get("cible"))
    if type_region is None:
        return grilles.sorte_de_pose(cibles) == "planche"
    return grilles.type_convient(type_region, cibles)


def a_regarder(c: dict, rubrique_cle: str, type_region) -> set:
    """Les entrées de la version `c`, non retirées, qu'une passe de cette rubrique, sur une
    zone de ce type (None : la planche), a à regarder. Une passe se rouvre quand la version
    d'arrivée en a plus à regarder que la sienne (M4 c) ; Ctrl+Z ne rend une passe dans la
    version active qu'à la même condition (`undo._version_de_la_passe`)."""
    return {k for k, e in c["entrees"].items()
            if not e.get("retiree") and _dans_la_rubrique(c, e, rubrique_cle)
            and _se_pose_sur(c, e, type_region)}


def _phrase(n: int, revoir: int, completer: int, repondre: int, refus: int, passes: int,
            numero: int) -> str:
    morceaux = []
    if n:
        morceaux.append(f"{n} relevé{'s' if n > 1 else ''} passe{'nt' if n > 1 else ''} en "
                        f"version {numero}.")
    else:
        morceaux.append(f"Aucun relevé ne change de version : la version {numero} "
                        "s'active.")
    suite = []
    if revoir:
        suite.append(f"{revoir} {'seront' if revoir > 1 else 'sera'} à revoir")
    if completer:
        suite.append(f"{completer} à compléter" if revoir
                     else f"{completer} {'seront' if completer > 1 else 'sera'} à compléter")
    if suite:
        morceaux.append(", ".join(suite) + ".")
    if passes:
        morceaux.append(f"{passes} passe{'s' if passes > 1 else ''} « terminée » se "
                        f"rouvre{'nt' if passes > 1 else ''}.")
    if repondre:
        morceaux.append(f"{repondre} entrée{'s' if repondre > 1 else ''} retirée"
                        f"{'s' if repondre > 1 else ''} attend{'ent' if repondre > 1 else ''} "
                        "votre réponse.")
    if refus:
        morceaux.append(f"{refus} cible{'s' if refus > 1 else ''} porte{'nt' if refus > 1 else ''}"
                        " deux relevés d'une entrée qui ne s'y pose plus qu'une fois : "
                        "retirez-en un avant de monter.")
    return " ".join(morceaux)


# --------------------------------------------------------------------------- #
# Le calcul — tout ce que le bilan dit et ce que la montée écrirait
# --------------------------------------------------------------------------- #
def calculer(conn: sqlite3.Connection, *, projet_id: int, grille_id: int, version,
             reponses=None) -> dict | None:
    """Ce que la montée de la grille vers `version` (sa ligne) ferait dans le projet, ou None
    si rien n'est à monter (aucun relevé ni aucune passe du projet dans une autre version :
    l'activation est celle d'aujourd'hui). Lit, n'écrit rien.

    Rend un dict INTERNE — le bilan (`bilan`, ce qui sort), et ce que `ecrire` lit :
    `releves` (ceux qui passent), `finale` (l'entrée de chacun après la montée), `une`
    (son drapeau), `fusions` (`{de, dans, releve_ids}`), `rouvertes` et `gardees` (passes),
    `fautes` (des réponses qui ne valent pas). `reponses` : déjà lues (`lire_reponses`)."""
    reponses = reponses or {}
    g = conn.execute("SELECT * FROM grille WHERE id = ?", (grille_id,)).fetchone()
    if g is None or g["ouverte"]:
        return None
    act = grilles.activation(conn, projet_id, grille_id)
    releves = releves_du_projet(conn, projet_id, grille_id)
    passes = passes_du_projet(conn, projet_id, grille_id)
    vid = version["id"]
    for p in passes:                       # une passe sans version : celle de l'activation
        if p["version_id"] is None and act is not None:
            p["version_id"] = act["version_id"]
    a_monter = [r for r in releves if r["version_id"] != vid]
    passes_a_voir = [p for p in passes if p["version_id"] is not None
                     and p["version_id"] != vid]
    if not a_monter and not passes_a_voir:
        return None
    contenus: dict = {}

    def contenu(v_id):
        if v_id not in contenus:
            contenus[v_id] = grilles.contenu(conn, v_id)
        return contenus[v_id]

    numeros = dict(conn.execute("SELECT id, numero FROM grille_version WHERE grille_id = ?",
                                (grille_id,)).fetchall())
    sources = sorted({r["version_id"] for r in a_monter}
                     | {p["version_id"] for p in passes_a_voir}, key=lambda v: numeros[v])
    de_id = act["version_id"] if act is not None and act["version_id"] in sources \
        else sources[-1]
    arrivee = contenu(vid)
    refus_version = []
    if version["etat"] != grilles.ETAT_PUBLIEE:
        refus_version.append({"code": "pas_publiee",
                              "probleme": f"La version {version['numero']} n'est pas publiée : "
                                          "on ne monte que vers une version publiée."})
    plus_recente = max(numeros[v] for v in sources)
    if version["numero"] < plus_recente:
        refus_version.append({"code": "plus_ancienne",
                              "probleme": f"Les relevés sont en version {plus_recente} : on ne "
                                          "monte que vers une version plus récente. Pour "
                                          "revenir, publiez une version qui reprend "
                                          "l'ancienne, puis montez."})

    # Les entrées employées que la version d'arrivée retire (ou n'a plus) : à décider.
    employees: dict = {}
    for r in a_monter:
        src = contenu(r["version_id"])
        e_src = src["entrees"].get(r["entree_cle"])
        e_dst = arrivee["entrees"].get(r["entree_cle"])
        if e_src is None or e_src.get("retiree") or (e_dst is not None
                                                     and not e_dst.get("retiree")):
            continue
        x = employees.setdefault(r["entree_cle"], {"cle": r["entree_cle"],
                                                   "libelle": e_src["libelle"], "releves": 0,
                                                   "source": r["version_id"], "variantes": set()})
        x["releves"] += 1
        if r["variante_cle"]:
            x["variantes"].add(r["variante_cle"])
    finale_sans = {r["id"]: r["entree_cle"] for r in releves}
    a_repondre, fautes, fusions = [], [], []
    from grille_import import _vers_possibles        # import paresseux, cf. `_refus`
    for cle_, x in sorted(employees.items(), key=lambda kv: kv[0]):
        src = contenu(x["source"])
        possibles = _vers_possibles(src, arrivee, cle_, x["variantes"])
        vers = []
        deplaces = {r["id"] for r in a_monter if r["entree_cle"] == cle_}
        for k in possibles:                           # sans fabriquer de doublon (M1)
            essai = {**finale_sans, **{i: k for i in deplaces}}
            if not any(kk == k and set(ids) & deplaces for (_c, kk), (_g, ids)
                       in _en_double(releves, essai, arrivee, deplaces).items()):
                vers.append(k)
        rep = reponses.get(cle_)
        a_repondre.append({"cle": cle_, "libelle": x["libelle"], "releves": x["releves"],
                           "choix": [LAISSER, FUSIONNER], "fusionner_dans": vers,
                           "reponse": None if rep is None else (
                               LAISSER if rep[0] == LAISSER else f"{FUSIONNER}:{rep[1]}")})
        if rep is None or rep[0] == LAISSER:
            continue
        if rep[1] not in vers:
            fautes.append({"code": "fusion_impossible", "cle": cle_,
                           "probleme": f"Les relevés de « {x['libelle']} » ne peuvent pas être "
                                       f"fusionnés dans « {rep[1]} ».",
                           "a_faire": "Fusionnez dans une entrée de la version d'arrivée, de "
                                      "même forme, posée de la même façon (et qui porte ses "
                                      "variantes), sans poser deux fois ce qui ne se pose "
                                      "qu'une fois : " + (", ".join(vers) or "aucune ici")
                                      + " ; ou laissez-la."})
            continue
        fusions.append({"de": cle_, "dans": rep[1],
                        "releve_ids": [r["id"] for r in a_monter if r["entree_cle"] == cle_]})
    for cle_ in sorted(set(reponses) - set(employees)):
        fautes.append({"code": "reponse_sans_objet", "cle": cle_,
                       "probleme": f"Une réponse est donnée pour « {cle_} », qui n'attend "
                                   "rien.", "a_faire": "Retirez cette réponse."})
    finale = dict(finale_sans)
    for f in fusions:
        for i in f["releve_ids"]:
            finale[i] = f["dans"]
    # M1 : une cible qui porterait deux relevés d'une entrée « une seule fois ».
    doubles = _en_double(releves, finale, arrivee,
                         {i for f in fusions for i in f["releve_ids"]})
    refus_cibles = []
    par_id = {r["id"]: r for r in releves}
    for (cible, cle_), (genre, ids) in sorted(doubles.items(),
                                             key=lambda kv: (kv[0][1], str(kv[0][0]))):
        r = par_id[ids[0]]
        e = arrivee["entrees"].get(cle_) or {}
        refus_cibles.append({"code": genre, "cle": cle_,
                             "libelle": e.get("libelle") or cle_, "releves": ids,
                             "zone": {"album_id": r["album_id"], "planche_id": r["planche_id"],
                                      "region_id": r["region_id"]}})
    # Ce que devient chaque relevé.
    issues, une = {}, {}
    for r in releves:
        causes = grilles.causes_dans_la_version(arrivee, {**r, "entree_cle": finale[r["id"]]})
        tout = r["texte"] + causes
        issues[r["id"]] = (grilles.etat_des_causes(tout), tout)
        une[r["id"]] = _une(arrivee, finale[r["id"]])
    # Les passes (M4 c).
    rouvertes, gardees = [], []
    regarde: dict = {}

    def a_regarder_dans(v_id, rk, type_region):
        cle_ = (v_id, rk, type_region)
        if cle_ not in regarde:
            regarde[cle_] = a_regarder(contenu(v_id), rk, type_region)
        return regarde[cle_]

    for p in passes_a_voir:
        type_zone = None if p["surface"] is not None else p["type_region"]
        if p["rubrique_cle"] and p["rubrique_cle"] not in arrivee["rubriques"]:
            rouvertes.append({**p, "pourquoi": "rubrique_absente"})
        elif a_regarder_dans(vid, p["rubrique_cle"], type_zone) - a_regarder_dans(
                p["version_id"], p["rubrique_cle"], type_zone):
            rouvertes.append({**p, "pourquoi": "a_regarder"})
        else:
            gardees.append(p)
    # Le bilan, en données.
    montes = {r["id"] for r in a_monter}
    comptes = {"total": len(a_monter), "normal": 0, "a_revoir": 0, "a_completer": 0}
    par_cause: dict = {}
    for r in a_monter:
        etat, causes = issues[r["id"]]
        comptes[etat] += 1
        for c in causes:
            x = par_cause.setdefault(c, {"cause": c, "etat": grilles.etat_des_causes([c]),
                                         "n": 0, "_zones": []})
            x["n"] += 1
            x["_zones"].append(r)
    numero_de = numeros[de_id]
    from grille_import import bilan as bilan_du_plan  # import paresseux, cf. `_refus`
    plan = bilan_du_plan(conn, None, contenu(de_id), arrivee)
    for d in plan["disparus"]:            # les relevés DU PROJET, et non de la grille entière
        if d["quoi"] == "entree":
            d["releves"] = sum(1 for r in a_monter if r["entree_cle"] == d["cle"])
        elif d["quoi"] == "variante":
            ec, _, vc = d["cle"].partition("/")
            d["releves"] = sum(1 for r in a_monter if r["entree_cle"] == ec
                               and r["variante_cle"] == vc)
        elif d["quoi"] == "qualificatif":
            qc = d["cle"].partition("/")[2]
            d["releves"] = sum(1 for r in a_monter if qc in r["qualificatifs"])
    plan["releves_touches"] = sum(d["releves"] for d in plan["disparus"])
    repondre = sum(1 for a in a_repondre if a["reponse"] is None)
    refuse = bool(refus_version or refus_cibles)
    etat = "refuse" if refuse else "a_repondre" if repondre or fautes else "montable"
    phrase = _phrase(len(a_monter), comptes["a_revoir"], comptes["a_completer"], repondre,
                     len(refus_cibles), len(rouvertes), version["numero"])
    if refus_version:
        phrase = " ".join(x["probleme"] for x in refus_version)
    vu = hashlib.sha256(json.dumps({
        "vers": vid, "de": sources,
        "releves": [[r["id"], r["version_id"], r["entree_cle"], r["variante_cle"],
                     r["qualificatifs"], r["type_region"], r["planche"], r["mots"],
                     bool((r["precision"] or "").strip()), r["lien_region_id"] is not None,
                     r["texte"], r["une"]] for r in releves],
        "passes": [[p["id"], p["version_id"], p["rubrique_cle"], p["type_region"]]
                   for p in passes]}, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    bilan = {
        "grille_id": grille_id, "projet_id": projet_id, "montee": True,
        "de": numero_de, "vers": version["numero"],
        "verdict": {"etat": etat, "phrase": phrase},
        "plan": plan, "releves": comptes,
        "causes": [par_cause[c] for c in (grilles.CAUSES_A_REVOIR_DU_TEXTE
                                          + grilles.CAUSES_A_REVOIR_DE_VERSION
                                          + grilles.CAUSES_A_COMPLETER_DE_VERSION)
                   if c in par_cause],
        "a_repondre": a_repondre, "fautes": fautes,
        "refus": refus_version + refus_cibles,
        "passes_rouvertes": {"n": len(rouvertes), "_zones": rouvertes},
        "vu": vu,
    }
    return {"bilan": bilan, "releves": [r for r in releves if r["id"] in montes],
            "finale": finale, "une": une, "fusions": fusions, "rouvertes": rouvertes,
            "gardees": gardees, "fautes": fautes, "refuse": refuse, "repondre": repondre,
            "de_id": de_id, "a_monter": bool(a_monter)}


def _zone(x) -> dict:
    return {"album_id": x["album_id"], "planche_id": x["planche_id"],
            "region_id": x["region_id"]}


def bilan_lisible(calcul: dict, albums_lus=None) -> dict:
    """Le bilan tel qu'il SORT : les zones nommées par cause et des passes rouvertes,
    bornées aux albums que l'appelant lit (`albums_lus`, None : tous — l'outil), au plus
    `ZONES_PAR_CAUSE` par cause ; les autres sont comptées (`hors_vue`) — une copie gardée
    au fonds, un album d'une collection qu'on ne lit pas."""
    b = copy.deepcopy(calcul["bilan"])

    def borner(lignes):
        lues = [x for x in lignes if albums_lus is None or x["album_id"] in albums_lus]
        vues, seen = [], set()
        for x in lues:
            z = _zone(x)
            k = (z["planche_id"], z["region_id"])
            if k not in seen:
                seen.add(k)
                vues.append(z)
        return vues[:ZONES_PAR_CAUSE], len(lignes) - len(lues)

    for c in b["causes"]:
        c["zones"], c["hors_vue"] = borner(c.pop("_zones"))
    p = b["passes_rouvertes"]
    p["zones"], p["hors_vue"] = borner(p.pop("_zones"))
    for r in b["refus"]:
        if "zone" in r and albums_lus is not None and r["zone"]["album_id"] not in albums_lus:
            r["zone"] = None
    return b


# --------------------------------------------------------------------------- #
# L'écriture
# --------------------------------------------------------------------------- #
def ecrire(conn: sqlite3.Connection, calcul: dict, *, projet_id: int, grille_id: int, version,
           act, par=None, agent=None, agent_type: str = "humain") -> dict:
    """ÉCRIT la montée que `calcul` a établie — l'appelant a vérifié qu'elle se fait (rien à
    répondre, aucun refus, le bilan vu). Les fusions, le report des relevés et leur drapeau
    `une`, les passes, l'activation, puis le journal. Rend le résumé de l'acte de grille."""
    import journal                                   # import paresseux, cf. `_refus`
    from grille_import import _COLONNES_D_UN_REPORT, journaliser_fusion
    ids = [r["id"] for r in calcul["releves"]]
    avants = {}
    for i in range(0, len(ids), 500):
        tranche = ids[i:i + 500]
        for x in conn.execute(f"SELECT {', '.join(_COLONNES_D_UN_REPORT)} FROM releve "
                              f"WHERE id IN ({', '.join('?' * len(tranche))})", tranche):
            avants[x[0]] = dict(zip(_COLONNES_D_UN_REPORT, x))
    # Le drapeau `une` d'abord à 0 partout : l'index unique partiel ne voit ainsi jamais un
    # état intermédiaire où deux relevés d'une cible le porteraient.
    conn.executemany("UPDATE releve SET une = 0 WHERE id = ?", [(i,) for i in ids])
    conn.executemany("UPDATE releve SET version_id = ?, entree_cle = ?, une = ? WHERE id = ?",
                     [(version["id"], calcul["finale"][i], int(calcul["une"][i]), i)
                      for i in ids])
    rouvertes = calcul["rouvertes"]
    conn.executemany("DELETE FROM passe WHERE id = ?", [(p["id"],) for p in rouvertes])
    conn.executemany("UPDATE passe SET version_id = ? WHERE id = ?",
                     [(version["id"], p["id"]) for p in calcul["gardees"]])
    conn.execute("INSERT INTO projet_grille (projet_id, grille_id, version_id, active_par) "
                 "VALUES (?, ?, ?, ?) ON CONFLICT(projet_id, grille_id) DO UPDATE SET "
                 "version_id = excluded.version_id, active_par = excluded.active_par, "
                 "active_le = datetime('now')", (projet_id, grille_id, version["id"], par))
    b = calcul["bilan"]
    resume = {"de": b["de"], "vers": b["vers"], "releves": b["releves"],
              "fusions": [{k: f[k] for k in ("de", "dans", "releve_ids")}
                          for f in calcul["fusions"]],
              "laissees": [a["cle"] for a in b["a_repondre"] if a["reponse"] == LAISSER],
              "passes_rouvertes": len(rouvertes)}
    acte = journal.journaliser(conn, "lien", "grille", grille_id,
                               avant={"projet_id": projet_id, "version": act["numero"]}
                               if act else None,
                               apres={"projet_id": projet_id, "version": version["numero"],
                                      "montee": resume},
                               agent=agent, agent_type=agent_type)
    for f in calcul["fusions"]:
        journaliser_fusion(conn, grille_id, version["numero"],
                           {**f, "releves_avant": {i: avants[i] for i in f["releve_ids"]}},
                           acte)
    montee = {"acte": acte, "de": b["de"], "vers": b["vers"]}
    for p in rouvertes:
        charge = {"passe_cle": f"{grille_id}:{p['rubrique_cle']}", "grille_id": grille_id,
                  "rubrique_cle": p["rubrique_cle"], "version_id": p["version_id"],
                  "par": p["par"]}
        avant = {**charge, "passe": True}
        apres = {**charge, "passe": False, "montee": montee}
        # Deux appels LITTÉRAUX, comme `routes/releves.journaliser_releve` : le cliquet du
        # journal relève les cibles par AST.
        if p["region_id"] is not None:
            journal.journaliser(conn, "passe_rouverte", "releve", p["region_id"], avant=avant,
                                apres=apres, agent=agent, agent_type=agent_type)
        else:
            journal.journaliser(conn, "passe_rouverte", "releve_planche", p["planche_id"],
                                avant=avant, apres=apres, agent=agent, agent_type=agent_type)
    return {**resume, "acte": acte}
