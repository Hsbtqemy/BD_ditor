"""« PASSER DANS UNE GRILLE… » — STRUCTURER une étiquette du Mode libre (ANN-7, J8 ; règles
tranchées par Hugo le 2026-11-06, `docs/ann7-mode-libre-cadrage.md`, « Structurer » ; complétées
par le §8 de `docs/ann7-montee-de-version-cadrage.md`, M7 tranché le 2026-11-15).

Une entrée de la grille de TRAVAIL d'un projet passe, avec ses relevés, dans une entrée d'une
AUTRE grille active du même projet :

- VERS LA VERSION ACTIVE de la grille d'arrivée (`projet_grille.version_id`) — vivante pour une
  ouverte, publiée pour une fermée : on y AJOUTE des relevés, le geste ordinaire. Jamais le
  brouillon, et AUCUNE version ne naît : si l'entrée d'arrivée manque, le bilan le dit (« écrivez-
  la dans le brouillon, publiez, montez la version, puis revenez »).
- LA RÈGLE est celle de la montée (`grilles.causes_dans_la_version`, `grilles.convient`) : le
  relevé, mis dans l'entrée d'arrivée avec sa variante traduite, convient-il à cette version ?
  À la montée, un relevé qui ne convient plus passe et se dit « à revoir » ; ici, il RESTE dans le
  Mode libre, et le bilan dit pourquoi — mêmes causes. S'y ajoutent les causes propres au
  passage : une valeur sans équivalent (`sans_equivalent`), une entrée « une seule fois » déjà
  posée sur la zone, ou la même valeur déjà posée (`deja_pose`), deux relevés qui y arriveraient
  ensemble (`en_double`, la cardinalité ; `meme_valeur`, le doublon de J3).
- LA VARIANTE : une table de correspondance, proposée par le libellé (`database.cle_tag`) et
  corrigée à la main. Une valeur sans correspondance reste ; un relevé SANS valeur peut recevoir
  une valeur de l'entrée d'arrivée (proposée par le nom de l'étiquette), sinon il reste
  (« choisissez une valeur ») ; vers une entrée qui ne prend pas de valeur, une valeur reste.
- Une précision ou un lien attendus à l'arrivée : le relevé PASSE, et se dit « à compléter »
  (dérivé, `releves_effectifs`).
- LE JOURNAL : un acte `fusion` par relevé déplacé (`grille_import.journaliser_fusion`) — ni
  Ctrl+Z ne l'offre, ni « qui perd quoi » ne le compte (`grilles.sql_acte_qui_range`) —, et un
  acte sous la grille de travail qui résume. Les doutes suivent le relevé ; AUCUNE passe ne se
  rouvre (on ajoute des relevés, le plan ne change pas). Les étiquettes des régions touchées se
  réindexent (la grille de travail est dans l'index, une fermée non).
- L'ÉTIQUETTE VIDÉE se propose au retrait : la réponse le dit (`videe`).

Pas de Ctrl+Z du geste (comme la fusion). Le droit est vérifié par l'appelant (gérer le projet) ;
ni commit, ni verrou : l'appelant tient la transaction, comme `montee`.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

import grilles
import montee

# Les causes d'un relevé qui RESTE dans le Mode libre — celles de la montée qui l'empêchent de
# convenir (`grilles.convient`), dans leur ordre, puis celles du passage.
CAUSES_QUI_RETIENNENT = grilles.CAUSES_A_REVOIR_DE_VERSION + ("variante_manquante",)
CAUSES_DU_PASSAGE = ("sans_equivalent", "deja_pose", "en_double", "meme_valeur")
ORDRE_DES_CAUSES = CAUSES_QUI_RETIENNENT + CAUSES_DU_PASSAGE
# La clé de la correspondance des relevés qui ne portent AUCUNE valeur.
SANS_VALEUR = ""


def _cle_tag(texte) -> str:
    from database import cle_tag                    # import paresseux : database nous lit
    return cle_tag(texte)


def _refus(statut: int, message: str, anomalies=None, bilan=None):
    from grille_import import Refus                 # import paresseux, cf. `montee._refus`
    return Refus(statut, message, anomalies, bilan)


def grilles_d_arrivee(conn: sqlite3.Connection, projet_id: int, source_id: int) -> list:
    """Les grilles où l'on peut passer : celles qui sont ACTIVES dans le projet, hors la grille
    de départ — ni retirées, ni de travail (il n'y en a qu'une par projet) —, par nom."""
    return [{"id": r["grille_id"], "nom": r["nom"], "ouverte": bool(r["ouverte"]),
             "version": r["numero"], "version_id": r["version_id"]}
            for r in conn.execute(
                "SELECT pg.grille_id, pg.version_id, g.nom, g.ouverte, v.numero "
                "FROM projet_grille pg JOIN grille g ON g.id = pg.grille_id "
                "JOIN grille_version v ON v.id = pg.version_id "
                "WHERE pg.projet_id = ? AND g.id <> ? AND g.retiree_le IS NULL "
                "AND g.travail = 0 ORDER BY g.nom COLLATE NOCASE, g.id",
                (projet_id, source_id))]


def _entrees_vues(c: dict) -> list:
    """Les entrées d'une version où l'on peut passer (non retirées), dans leur ordre."""
    return [{"cle": k, "libelle": e["libelle"], "forme": e["forme"],
             "variantes": [{"cle": vc, "libelle": v["libelle"]}
                           for vc, v in sorted(e["variantes"].items(),
                                               key=lambda kv: kv[1]["rang"])]}
            for k, e in sorted(c["entrees"].items(), key=lambda kv: kv[1]["rang"])
            if not e.get("retiree")]


def _par_libelle(objets: dict, libelle) -> str | None:
    """La clé de l'objet de `objets` (`{cle: {libelle…}}`) dont le libellé est le même,
    comparé comme un tag (`cle_tag`) ; None s'il n'y en a pas."""
    voulu = _cle_tag(libelle)
    if not voulu:
        return None
    return next((k for k, x in objets.items()
                 if not x.get("retiree") and _cle_tag(x["libelle"]) == voulu), None)


def _absente(conn, vers: dict, libelle: str, *, ouverte: bool, cle: str | None = None) -> str:
    """La phrase d'une entrée d'arrivée qui manque (cadrage de la montée, §8) : où l'écrire,
    et — pour une grille fermée — qu'elle ne s'emploie qu'une fois la version montée. Si une
    version publiée plus récente que l'active la porte déjà (par sa clé `cle`, sinon par son
    libellé), il ne reste qu'à monter."""
    if ouverte:
        return (f"Aucune entrée « {libelle} » dans « {vers['nom']} » : choisissez-en une, ou "
                "écrivez-la dans la grille, puis revenez.")
    plus = conn.execute(
        "SELECT numero FROM grille_version WHERE grille_id = ? AND etat = ? AND numero > ? "
        "ORDER BY numero DESC", (vers["id"], grilles.ETAT_PUBLIEE, vers["version"])).fetchall()
    for (numero,) in plus:
        c = grilles.contenu(conn, grilles.version(conn, vers["id"], numero)["id"])
        e = c["entrees"].get(cle) if cle else None
        if (e is not None and not e.get("retiree")) or (cle is None
                                                         and _par_libelle(c["entrees"], libelle)):
            return (f"Aucune entrée « {libelle} » dans la version {vers['version']} active de "
                    f"« {vers['nom']} » : la version {numero} la porte — montez la version, "
                    "puis revenez.")
    return (f"Aucune entrée « {libelle} » dans la version {vers['version']} active de "
            f"« {vers['nom']} » : choisissez-en une, ou écrivez-la dans le brouillon, publiez, "
            "montez la version, puis revenez.")


def _cle_de_valeur(r: dict, variante_cle) -> tuple:
    """Ce qui fait d'un relevé sur une cible ENTIÈRE « la même valeur » qu'un autre (J3,
    `releves.doublon`) : sa variante quand il en a une, sinon ses cases, sa précision et son
    lien."""
    if variante_cle:
        return ("v", variante_cle)
    return ("r", tuple(sorted(r["qualificatifs"])), r["precision"] or None, r["lien_region_id"])


def calculer(conn: sqlite3.Connection, *, projet_id: int, source: dict, cle: str,
             vers_id: int | None = None, dans: str | None = None,
             correspondance: dict | None = None) -> dict:
    """Ce que le passage de l'entrée `cle` de la grille de travail `source` (sa ligne) dans
    l'entrée `dans` de la grille `vers_id` ferait dans le projet. Lit, n'écrit rien. Rend un
    dict INTERNE : `bilan` (ce qui sort) et ce que `ecrire` lit — `passent` (`{id, variante}`),
    la version d'arrivée, le drapeau `une`, les `fautes` d'une correspondance qui ne vaut pas.

    Sans `vers_id`, le bilan liste les grilles où passer ; sans `dans`, les entrées de la
    version active d'arrivée et celle que le libellé propose. `correspondance` : `{valeur du
    Mode libre (sa clé, ou "" pour les relevés sans valeur): clé de la variante d'arrivée, ou
    None}` ; ce qui n'y est pas suit la proposition."""
    act = grilles.activation(conn, projet_id, source["id"])
    src = grilles.contenu(conn, act["version_id"])
    e_src = src["entrees"][cle]
    releves = [r for r in montee.releves_du_projet(conn, projet_id, source["id"])
               if r["entree_cle"] == cle and r["version_id"] == act["version_id"]]
    arrivees = grilles_d_arrivee(conn, projet_id, source["id"])
    de = {"grille_id": source["id"], "cle": cle, "libelle": e_src["libelle"],
          "releves": len(releves)}
    bilan = {"de": de, "grilles": [{k: g[k] for k in ("id", "nom", "ouverte", "version")}
                                   for g in arrivees],
             "vers": None, "entrees": [], "propose": None, "dans": None,
             "correspondance": [], "releves": {"total": len(releves), "passent": 0,
                                               "restent": 0, "a_completer": 0},
             "restent": [], "a_completer": [], "videe": False}
    sortie = {"bilan": bilan, "passent": [], "fautes": [], "releves": releves}

    def verdict(etat, phrase):
        bilan["verdict"] = {"etat": etat, "phrase": phrase}
        return sortie

    if not releves:
        return verdict("rien_a_passer", f"Personne ne pose « {e_src['libelle']} » : il n'y a "
                                        "rien à passer. Retirez-la plutôt.")
    if not arrivees:
        return verdict("aucune_grille", "Aucune autre grille n'est active dans le projet : "
                                        "activez-en une, puis revenez.")
    if vers_id is None:
        return verdict("choisir_grille", "Choisissez la grille qui reçoit l'étiquette.")
    vers = next((g for g in arrivees if g["id"] == vers_id), None)
    if vers is None:
        raise _refus(409, "Cette grille n'est pas active dans le projet : on ne passe que dans "
                          "une grille active du projet, autre que le Mode libre.")
    bilan["vers"] = {k: vers[k] for k in ("id", "nom", "ouverte", "version")}
    dst = grilles.contenu(conn, vers["version_id"])
    bilan["entrees"] = _entrees_vues(dst)
    bilan["propose"] = _par_libelle(dst["entrees"], e_src["libelle"])
    if dans is None:
        if bilan["propose"] is None:
            return verdict("choisir_entree", _absente(conn, vers, e_src["libelle"],
                                                      ouverte=vers["ouverte"]))
        return verdict("choisir_entree", "Choisissez l'entrée qui reçoit ses relevés.")
    e_dst = dst["entrees"].get(dans)
    if e_dst is None or e_dst.get("retiree"):
        return verdict("entree_absente", _absente(conn, vers, dans, ouverte=vers["ouverte"],
                                                  cle=dans))
    bilan["dans"] = {"cle": dans, "libelle": e_dst["libelle"], "forme": e_dst["forme"]}

    # La correspondance des valeurs : proposée par le libellé, corrigée à la main.
    correspondance = dict(correspondance or {})
    a_variantes = e_dst["forme"] == "variantes"
    valeurs: dict = {}
    for r in releves:
        valeurs[r["variante_cle"] or SANS_VALEUR] = valeurs.get(r["variante_cle"] or SANS_VALEUR,
                                                                0) + 1
    table = {}
    for vc in sorted(valeurs, key=lambda k: (k != SANS_VALEUR,
                                             (e_src["variantes"].get(k) or {}).get("rang", 0))):
        libelle = e_src["libelle"] if vc == SANS_VALEUR else (
            (e_src["variantes"].get(vc) or {}).get("libelle") or vc)
        propose = _par_libelle(e_dst["variantes"], libelle) if a_variantes else None
        choisi = propose
        if vc in correspondance:
            choisi = correspondance.pop(vc) or None
            if choisi is not None and (not a_variantes or choisi not in e_dst["variantes"]):
                sortie["fautes"].append({
                    "code": "valeur_inconnue", "cle": vc,
                    "probleme": f"« {choisi} » n'est pas une valeur de « {e_dst['libelle']} »."})
                choisi = None
        table[vc] = choisi
        bilan["correspondance"].append({
            "de": {"cle": vc or None, "libelle": None if vc == SANS_VALEUR else libelle,
                   "releves": valeurs[vc]},
            "propose": propose, "vers": choisi})
    for vc in sorted(correspondance):
        sortie["fautes"].append({"code": "valeur_sans_objet", "cle": vc,
                                 "probleme": f"Aucun relevé de « {e_src['libelle']} » ne porte "
                                             f"la valeur « {vc} »."})

    # Ce que devient chaque relevé : la règle de la montée, puis celles du passage.
    cibles_dst = grilles.cibles_de(e_dst.get("cible")) or grilles.cibles_de(dst.get("cible"))
    une = grilles.cardinalite_effective(e_dst, cibles_dst) == "une"
    issues, candidats = {}, []
    for r in releves:
        cible_v = table.get(r["variante_cle"] or SANS_VALEUR)
        # Vers une entrée qui ne prend pas de valeur, le relevé garde la sienne pour la règle :
        # elle n'y a pas de place (`variante_sans_place`), et il reste.
        causes = grilles.causes_dans_la_version(dst, {
            **r, "entree_cle": dans,
            "variante_cle": cible_v if a_variantes else r["variante_cle"]})
        if r["variante_cle"] and a_variantes and cible_v is None:
            causes = [c for c in causes if c != "variante_manquante"] + ["sans_equivalent"]
        retenu = [c for c in causes if c in CAUSES_QUI_RETIENNENT or c in CAUSES_DU_PASSAGE]
        issues[r["id"]] = {"variante": cible_v, "causes": causes, "retenu": retenu}
        if not retenu:
            candidats.append(r)
    # La cardinalité et le doublon, contre ce que l'arrivée porte déjà et entre les candidats.
    import releves as module_releves                 # le doublon de J3, écrit une fois
    groupes: dict = {}
    for r in candidats:
        groupes.setdefault(montee._cible(r), []).append(r)
    existants = []
    for (_sorte, _id), rs in groupes.items():
        r0 = rs[0]
        cible = {"region_id": r0["region_id"], "planche_id": None if r0["region_id"] is not None
                 else r0["planche_id"]}
        if une:
            deja = module_releves.existant_une(conn, **cible, grille_id=vers["id"],
                                               entree_cle=dans) or conn.execute(
                "SELECT * FROM releve WHERE COALESCE(region_id, 0) = ? "
                "AND COALESCE(planche_id, 0) = ? AND grille_id = ? AND entree_cle = ? "
                "ORDER BY id LIMIT 1", (cible["region_id"] or 0, cible["planche_id"] or 0,
                                        vers["id"], dans)).fetchone()
            if deja is not None:
                existants.append(deja["id"])
                for r in rs:
                    issues[r["id"]]["retenu"].append("deja_pose")
            elif len(rs) > 1:
                for r in rs:
                    issues[r["id"]]["retenu"].append("en_double")
            continue
        vues: dict = {}
        for r in rs:
            if r["mots"]:                             # des mots : jamais une cible entière
                continue
            v = issues[r["id"]]["variante"]
            deja = module_releves.doublon(conn, **cible, grille_id=vers["id"], entree_cle=dans,
                                          variante_cle=v, qualificatifs=r["qualificatifs"],
                                          precision=r["precision"],
                                          lien_region_id=r["lien_region_id"])
            if deja is not None:
                existants.append(deja["id"])
                issues[r["id"]]["retenu"].append("deja_pose")
            else:
                vues.setdefault(_cle_de_valeur(r, v), []).append(r)
        for memes in vues.values():
            if len(memes) > 1:
                for r in memes:
                    issues[r["id"]]["retenu"].append("meme_valeur")

    # Le bilan, relevé par relevé : passés, et restés par cause.
    restent: dict = {}
    completer: dict = {}
    for r in releves:
        x = issues[r["id"]]
        if x["retenu"]:
            bilan["releves"]["restent"] += 1
            for c in [c for c in ORDRE_DES_CAUSES if c in x["retenu"]]:
                g = restent.setdefault((c, _designe(r) if c == "pose_changee" else None),
                                       {"cause": c, "n": 0, "_zones": []})
                if c == "pose_changee":
                    g["designe"] = _designe(r)
                g["n"] += 1
                g["_zones"].append(r)
            continue
        bilan["releves"]["passent"] += 1
        sortie["passent"].append({"id": r["id"], "variante": x["variante"]})
        a_completer = [c for c in x["causes"] if c in grilles.CAUSES_A_COMPLETER_DE_VERSION]
        if a_completer:
            bilan["releves"]["a_completer"] += 1
        for c in a_completer:
            g = completer.setdefault(c, {"cause": c, "n": 0, "_zones": []})
            g["n"] += 1
            g["_zones"].append(r)
    bilan["restent"] = sorted(restent.values(),
                              key=lambda g: (ORDRE_DES_CAUSES.index(g["cause"]),
                                             g.get("designe") or ""))
    bilan["a_completer"] = [completer[c] for c in grilles.CAUSES_A_COMPLETER_DE_VERSION
                            if c in completer]
    n, reste = bilan["releves"]["passent"], bilan["releves"]["restent"]
    bilan["videe"] = n > 0 and reste == 0
    sortie.update(vers=vers, dans=dans, une=une, e_dst=e_dst, act=act)
    nom = f"« {vers['nom']} › {e_dst['libelle']} »"
    morceaux = []
    if n:
        morceaux.append(f"{n} relevé{'s' if n > 1 else ''} passe{'nt' if n > 1 else ''} dans "
                        f"{nom}")
        k = bilan["releves"]["a_completer"]
        morceaux[-1] += (f", {k} à compléter." if k else ".")
    else:
        morceaux.append(f"Aucun relevé ne peut passer dans {nom}.")
    if reste:
        morceaux.append(f"{reste} reste{'nt' if reste > 1 else ''} dans le Mode libre.")
    elif n:
        morceaux.append(f"« {e_src['libelle']} » sera vide : vous pourrez la retirer.")
    if sortie["fautes"]:
        morceaux.append(f"{len(sortie['fautes'])} correspondance(s) ne valent pas.")
    etat = "a_corriger" if sortie["fautes"] else "passable" if n else "rien_a_passer"
    bilan["vu"] = hashlib.sha256(json.dumps({
        "de": act["version_id"], "vers": vers["version_id"], "dans": dans,
        "entree": {k: e_dst.get(k) for k in ("forme", "cible", "cardinalite", "precision",
                                             "lien", "liste_cle")},
        "valeurs": sorted(e_dst["variantes"]), "table": table,
        "releves": [[r["id"], r["variante_cle"], r["qualificatifs"], r["type_region"],
                     r["planche"], r["mots"], bool((r["precision"] or "").strip()),
                     r["lien_region_id"], r["texte"], issues[r["id"]]["retenu"]]
                    for r in releves],
        "existants": sorted(set(existants))}, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return verdict(etat, " ".join(morceaux))


def _designe(r: dict) -> str:
    """Ce qu'un relevé désigne, pour dire en mots une sorte de pose qui ne convient pas : la
    planche, des mots, ou une zone entière."""
    return "planche" if r["planche"] else "mots" if r["mots"] else "zone"


def bilan_lisible(calcul: dict, albums_lus=None) -> dict:
    """Le bilan tel qu'il SORT : les zones nommées par cause, bornées aux albums que
    l'appelant lit (None : tous), au plus `montee.ZONES_PAR_CAUSE` par cause ; les autres
    sont comptées (`hors_vue`). Ni login, ni identifiant de relevé."""
    b = json.loads(json.dumps(calcul["bilan"]))
    for groupe in b["restent"] + b["a_completer"]:
        lignes = groupe.pop("_zones")
        lues = [x for x in lignes if albums_lus is None or x["album_id"] in albums_lus]
        vues, vus = [], set()
        for x in lues:
            z = montee._zone(x)
            k = (z["planche_id"], z["region_id"])
            if k not in vus:
                vus.add(k)
                vues.append(z)
        groupe["zones"], groupe["hors_vue"] = vues[:montee.ZONES_PAR_CAUSE], len(lignes) - len(lues)
    return b


def ecrire(conn: sqlite3.Connection, calcul: dict, *, source: dict) -> dict:
    """ÉCRIT le passage que `calcul` a établi — l'appelant a vérifié qu'il se fait (le bilan
    vu, quelque chose à passer, aucune faute). Les relevés changent de grille, de version,
    d'entrée, de variante et de drapeau `une` ; un acte sous la grille de travail résume, puis
    un acte `fusion` par relevé déplacé ; les étiquettes de leurs régions se réindexent. Rend
    le résumé."""
    import journal                                   # import paresseux, cf. `_refus`
    from database import regions_des_releves, reindex_etiquettes
    from grille_import import _COLONNES_D_UN_REPORT, journaliser_fusion
    vers, dans, act = calcul["vers"], calcul["dans"], calcul["act"]
    passent = calcul["passent"]
    ids = [p["id"] for p in passent]
    avants = {}
    for i in range(0, len(ids), 500):
        tranche = ids[i:i + 500]
        for x in conn.execute(f"SELECT {', '.join(_COLONNES_D_UN_REPORT)} FROM releve "
                              f"WHERE id IN ({', '.join('?' * len(tranche))})", tranche):
            avants[x[0]] = dict(zip(_COLONNES_D_UN_REPORT, x))
    # Les régions d'AVANT (les mêmes : un relevé ne change pas de zone) — leurs étiquettes
    # quittent le Mode libre, et entrent dans la grille d'arrivée si elle est ouverte.
    regions = regions_des_releves(conn, ids)
    # Le drapeau `une` d'abord à 0 : l'index unique partiel ne voit jamais un état
    # intermédiaire où deux relevés d'une cible le porteraient.
    conn.executemany("UPDATE releve SET une = 0 WHERE id = ?", [(i,) for i in ids])
    conn.executemany(
        "UPDATE releve SET grille_id = ?, version_id = ?, entree_cle = ?, variante_cle = ?, "
        "une = ? WHERE id = ?",
        [(vers["id"], vers["version_id"], dans, p["variante"], int(calcul["une"]), p["id"])
         for p in passent])
    b = calcul["bilan"]
    table = {x["de"]["cle"] or SANS_VALEUR: x["vers"] for x in b["correspondance"]}
    resume = {"vers": {"grille_id": vers["id"], "version": vers["version"], "entree": dans},
              "variantes": table, "releve_ids": ids, "restent": b["releves"]["restent"]}
    acte = journal.journaliser(conn, "modification", "grille", source["id"],
                               avant={"objet": f"entree:{b['de']['cle']}",
                                      "version": act["numero"]},
                               apres={"objet": f"entree:{b['de']['cle']}",
                                      "version": act["numero"], "passee_dans": resume})
    journaliser_fusion(conn, source["id"], act["numero"],
                       {"de": b["de"]["cle"], "dans": dans, "releve_ids": ids,
                        "releves_avant": avants}, acte,
                       vers={"grille_id": vers["id"], "version": vers["version"]})
    reindex_etiquettes(conn, regions)
    return {"passes": len(ids), "restent": b["releves"]["restent"], "videe": b["videe"],
            "releve_ids": ids, "acte": acte}
