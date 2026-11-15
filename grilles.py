"""Les GRILLES d'annotation — le modèle, sans route ni tableur (ANN-7, tranche 1 ; cadrage R2).

Une grille appartient à un projet ; elle a des VERSIONS, chacune un INSTANTANÉ COMPLET de son
plan (rubriques, entrées, variantes, listes de qualificatifs, exemples), dont les lignes se
désignent entre elles par leur `cle` et jamais par leur `id` (tranché le 2026-10-14) :
copier une version, c'est recopier des lignes sans renuméroter de références. L'outil ne
connaît AUCUN vocabulaire — ni un tag, ni un niveau, ni le mot « linguistique » — ; tout ce
qui fait une grille est une donnée importée (ANN-7, 2026-10-14). Ce qui est borné, ce sont
les FORMES (trois) et les CIBLES (neuf sortes) : les listes de ce module, les seules qui
fassent foi — le schéma ne porte aucun `CHECK`, pour la raison écrite sur
`utilisateur.nature`.

Ce module LIT et TRANCHE : la cible et la cardinalité effectives d'une entrée, la version
active d'une grille dans un projet, le contenu normalisé d'une version et son empreinte, le
plan rendu à l'écran. Il n'écrit rien et ne décide d'aucun droit — qui lit quoi est
`autorisation.Portee.clause_grille`, qui écrit quoi les routes.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
import uuid

# Les trois FORMES d'une entrée (note §3) — et ce que chacune COMPTE (cadrage R2, tranché le
# 2026-10-22 : « le modèle ne change pas ») : une entrée SIMPLE est posée ou non ; une
# entrée À VARIANTES est posée avec UNE de ses variantes ; une entrée À QUALIFICATIFS est
# posée avec zéro, un ou plusieurs qualificatifs de SA liste, et compte UNE fois son
# phénomène, quel que soit le nombre de qualificatifs cochés.
FORMES = ("simple", "variantes", "qualificatifs")

# Les CIBLES (cadrage R2) : des mots d'une zone de texte ; une région entière, d'un des types
# qu'elle nomme (`personnage` est la BOÎTE, une région, Q4) ; la planche (la SURFACE,
# IMG-2) ; l'entité du registre des personnages (Q4). `entite` s'importe — c'est une donnée
# — mais aucun relevé ne s'y pose avant l'étage de projet des personnages (G3). Un `detail`
# se trace sur la page Annotation depuis la tranche 2 (commit 9, G17), et s'y relève.
CIBLE_MOTS = "mots"
CIBLES_ZONE = ("bulle", "cartouche", "texte", "case", "personnage", "detail")
CIBLE_PLANCHE = "planche"
CIBLE_ENTITE = "entite"
CIBLES = (CIBLE_MOTS, *CIBLES_ZONE, CIBLE_PLANCHE, CIBLE_ENTITE)
# Les zones où l'on désigne des MOTS : celles qui portent un texte.
TYPES_TEXTE = ("bulle", "cartouche", "texte")

CARDINALITES = ("une", "plusieurs")
ETAT_BROUILLON, ETAT_PUBLIEE, ETAT_VIVANTE = "brouillon", "publiee", "vivante"
ETATS_VERSION = (ETAT_BROUILLON, ETAT_PUBLIEE, ETAT_VIVANTE)
# L'ÉTAT d'une entrée (v39, ANN-7 ; « les étiquettes de travail », Hugo, 2026-11-05 ; J4,
# 2026-11-06) : ce qu'on ne sait pas encore nommer est PROVISOIRE — une entrée née EN LA
# TAPANT, en posant (G14, « nom : valeur » compris : `routes/releves._entree_par_nom`) — ; ce
# qui est ÉCRIT, par l'import ou le formulaire, est DÉFINI, même dans une grille ouverte. Les
# responsables le changent (`PATCH …/entrees/{cle}`, avec `vu`) ; l'empreinte d'une version
# ne le lit pas, et il ne gouverne encore rien d'autre.
ENTREE_PROVISOIRE, ENTREE_DEFINIE = "provisoire", "defini"
ETATS_ENTREE = (ENTREE_PROVISOIRE, ENTREE_DEFINIE)
ISSUES_DOUTE = ("garde", "change", "retire")
# Le TYPE de l'acte qu'une FUSION d'entrées écrit sur chaque relevé qu'elle déplace, sous sa
# cible ordinaire (`releve` : la région ; `releve_planche` : la planche) — ANN-7, le mode
# libre (`grille_import.journaliser_fusion`). Un type à lui, comme `doute` et `passe` : hors
# de la pile de Ctrl+Z (`undo._TYPES`) — l'entrée de départ n'existe plus, et chaque relevé
# rejoué vers elle serait un acte passé de plus —, et pas un TRAVAIL sur l'album : la fusion
# range un vocabulaire (son acte sous `grille`), le relevé reste celui de qui l'a posé. Ce
# qui lit le journal pour dire « qui a travaillé » l'écarte par `sql_acte_de_fusion`.
ACTE_FUSION = "fusion"


def sql_acte_de_fusion(e: str) -> str:
    """Fragment SQL VRAI si l'acte `e` (un alias de `evenement`) est le report d'un relevé
    par une fusion d'entrées (`ACTE_FUSION`), sous l'une des deux cibles d'un relevé."""
    return (f"({e}.type = '{ACTE_FUSION}' "
            f"AND {e}.cible_table IN ('releve', 'releve_planche'))")

# Le séparateur de plusieurs cibles, dans une cellule du tableur (« bulle | cartouche |
# texte ») et en base (« bulle|cartouche|texte », dans l'ordre de `CIBLES`).
SEP_CIBLES = "|"


# --------------------------------------------------------------------------- #
# Les cibles
# --------------------------------------------------------------------------- #
def lire_cibles(texte) -> tuple[tuple, str | None]:
    """Une cellule « Porte sur » ou `cible` → (les sortes, dans l'ordre de `CIBLES` ; une
    erreur en mots, ou None). Vide : `()`, sans erreur. Une sorte inconnue, ou un mélange
    qui ne désigne pas UNE manière de poser, est une erreur — les mots se combinent avec rien
    (on ne pose pas des mots ET une case), la planche et l'entité non plus ; les types de
    zone, entre eux, oui (« bulle | cartouche | texte » : toute la zone, l'une des trois)."""
    morceaux = [m.strip().lower() for m in str(texte or "").split(SEP_CIBLES)]
    morceaux = [m for m in morceaux if m]
    if not morceaux:
        return (), None
    inconnues = [m for m in morceaux if m not in CIBLES]
    if inconnues:
        return (), (f"cible inconnue « {', '.join(inconnues)} » "
                    f"(attendu : {' · '.join(CIBLES)})")
    sortes = tuple(c for c in CIBLES if c in morceaux)
    if len(sortes) > 1 and not set(sortes) <= set(CIBLES_ZONE):
        return (), (f"« {' | '.join(sortes)} » mêle des cibles qui ne se combinent pas : seuls "
                    f"des types de zone se combinent entre eux")
    return sortes, None


def ecrire_cibles(sortes) -> str | None:
    """Les sortes → leur forme en base (« bulle|cartouche|texte »), None si aucune."""
    return SEP_CIBLES.join(c for c in CIBLES if c in set(sortes)) or None


def cibles_de(valeur) -> tuple:
    """La forme en base → les sortes (un tuple vide pour NULL)."""
    return tuple(c for c in str(valeur or "").split(SEP_CIBLES) if c)


def cibles_effectives(entree, version) -> tuple:
    """Les cibles d'une entrée : les siennes si elle en déclare (« Une entrée peut déclarer sa
    propre cible », 2026-10-22), sinon celles de sa version (« Porte sur »)."""
    return cibles_de(entree["cible"]) or cibles_de(version["cible"])


def sorte_de_pose(cibles) -> str | None:
    """Comment se pose une entrée de ces cibles : `mots`, `zone`, `planche`, `entite`, ou
    None si elle n'en a aucune (une version sans « Porte sur »)."""
    if not cibles:
        return None
    if cibles == (CIBLE_MOTS,):
        return "mots"
    if cibles == (CIBLE_PLANCHE,):
        return "planche"
    if cibles == (CIBLE_ENTITE,):
        return "entite"
    return "zone"


def cardinalite_effective(entree, cibles) -> str:
    """`une` ou `plusieurs` (Q6, tranché le 2026-10-22) : celle que l'entrée déclare ; vide,
    le défaut de sa cible — `plusieurs` sur des mots (deux élisions dans une bulle), `une`
    sur une région entière, la planche ou l'entité (un seul registre par bulle)."""
    if entree["cardinalite"] in CARDINALITES:
        return entree["cardinalite"]
    return "plusieurs" if sorte_de_pose(cibles) == "mots" else "une"


def type_convient(type_region: str, cibles) -> bool:
    """Une région de ce type convient-elle à ces cibles ? Des mots demandent une zone de
    texte ; une cible de zone demande l'un de ses types."""
    sorte = sorte_de_pose(cibles)
    if sorte == "mots":
        return type_region in TYPES_TEXTE
    if sorte == "zone":
        return type_region in cibles
    return False


# --------------------------------------------------------------------------- #
# Un relevé dans une version (ANN-7, la montée de version ; cadrage
# `docs/ann7-montee-de-version-cadrage.md`, §3)
# --------------------------------------------------------------------------- #
# Les CAUSES qu'une VERSION donne à un relevé — ce qui dépend du plan seul, et que la montée
# change : les autres (un mot perdu, un texte changé, une zone liée disparue) suivent le
# texte et les liens, quelle que soit la version. `releves_effectifs` les écrit en SQL, cette
# règle en Python : `tests/test_regle_du_releve.py` les accorde, cas par cas. La montée, Ctrl+Z
# (un relevé rendu dans la version active) et « Passer dans une grille… » l'appellent.
CAUSES_A_REVOIR_DE_VERSION = ("type_change", "pose_changee", "entree_absente",
                              "variante_absente", "variante_sans_place", "case_absente",
                              "case_sans_place")
CAUSES_A_COMPLETER_DE_VERSION = ("variante_manquante", "precision_manquante", "lien_manquant")
# Celles qui ne dépendent pas de la version (la vue les dit aussi).
CAUSES_A_REVOIR_DU_TEXTE = ("mot_perdu", "texte_change", "lien_perdu")


def causes_dans_la_version(c: dict, r: dict) -> list:
    """Les causes que la version de contenu `c` (`contenu`) donne au relevé `r`, dans l'ordre
    de `CAUSES_A_REVOIR_DE_VERSION` puis `CAUSES_A_COMPLETER_DE_VERSION` — vide : il y passe
    « normal ». `r` : `{entree_cle, planche (un relevé de SURFACE), type_region (None sur la
    planche), mots (il désigne des mots), variante_cle, qualificatifs, precision,
    lien_region_id}`.

    - l'entrée absente de la version, ou RETIRÉE : `entree_absente` (rien d'autre ne se dit
      d'une entrée qui n'existe pas ; une retirée garde ses autres causes) ;
    - le TYPE de la région ne convient plus à la cible de l'entrée : `type_change` (G8) ;
    - la SORTE DE POSE a changé : un relevé de planche dont l'entrée ne vise plus la planche,
      des mots dont l'entrée vise toute la zone, une zone entière dont l'entrée vise des mots
      — `pose_changee` ;
    - une VARIANTE qui n'existe plus dans l'entrée (`variante_absente`), ou qui n'a plus de
      place, l'entrée n'étant plus à variantes (`variante_sans_place`) ; une entrée devenue à
      variantes sous un relevé qui n'en porte pas : `variante_manquante`, à compléter ;
    - une CASE cochée qui n'est pas dans la liste de l'entrée (`case_absente`), ou des cases
      sur une entrée qui n'en prend plus (`case_sans_place`) ;
    - une précision ou un lien attendus et absents (`precision_manquante`, `lien_manquant`).

    Une entrée qui ne dit pas où elle se pose (une version sans « Porte sur ») ne dit rien du
    type ni de la sorte de pose : la vue rend NULL, la règle se tait de même."""
    e = c["entrees"].get(r["entree_cle"])
    if e is None:
        return ["entree_absente"]
    causes = set()
    if e.get("retiree"):
        causes.add("entree_absente")
    cibles = cibles_de(e.get("cible")) or cibles_de(c.get("cible"))
    pose = sorte_de_pose(cibles)
    if cibles and not r["planche"] and not type_convient(r["type_region"], cibles):
        causes.add("type_change")
    if cibles and ((r["planche"] and pose != "planche")
                   or (not r["planche"] and r["mots"] and pose == "zone")
                   or (not r["planche"] and not r["mots"] and pose == "mots")):
        causes.add("pose_changee")
    forme = e["forme"]
    if r.get("variante_cle"):
        if forme != "variantes":
            causes.add("variante_sans_place")
        elif r["variante_cle"] not in (e.get("variantes") or {}):
            causes.add("variante_absente")
    elif forme == "variantes":
        causes.add("variante_manquante")
    cochees = set(r.get("qualificatifs") or ())
    if cochees:
        if forme != "qualificatifs":
            causes.add("case_sans_place")
        else:
            liste = (c.get("listes") or {}).get(e.get("liste_cle")) or {}
            if cochees - set(liste.get("qualificatifs") or {}):
                causes.add("case_absente")
    if e.get("precision") is not None and not (r.get("precision") or "").strip(" "):
        causes.add("precision_manquante")
    if e.get("lien") and r.get("lien_region_id") is None:
        causes.add("lien_manquant")
    return [x for x in CAUSES_A_REVOIR_DE_VERSION + CAUSES_A_COMPLETER_DE_VERSION
            if x in causes]


def etat_des_causes(causes) -> str:
    """L'ÉTAT que des causes donnent à un relevé — la règle de `releves_effectifs` :
    `a_revoir` dès une cause à revoir, sinon `a_completer` dès une cause à compléter, sinon
    `normal`."""
    causes = set(causes)
    if causes & set(CAUSES_A_REVOIR_DE_VERSION + CAUSES_A_REVOIR_DU_TEXTE):
        return "a_revoir"
    if causes & set(CAUSES_A_COMPLETER_DE_VERSION):
        return "a_completer"
    return "normal"


def convient(c: dict, r: dict) -> bool:
    """Le relevé `r` peut-il VIVRE dans la version `c` comme s'il y avait été posé — son
    entrée y existe et n'est pas retirée, sa variante et ses cases y ont leur place, il s'y
    pose de la même manière, sur une zone d'un type qu'elle vise ? La règle que Ctrl+Z lit
    pour rendre un relevé d'avant la montée dans la version active (cadrage, §7). Une
    précision ou un lien manquants ne l'empêchent pas : ils se complètent."""
    return not (set(causes_dans_la_version(c, r)) & set(CAUSES_A_REVOIR_DE_VERSION
                                                        + ("variante_manquante",)))


# --------------------------------------------------------------------------- #
# L'identifiant d'une grille, et son origine (v40)
# --------------------------------------------------------------------------- #
def identifiant_neuf() -> str:
    """L'IDENTIFIANT d'une grille qui naît (v40, ANN-7, « Une grille dérivée dit d'où elle
    vient », Hugo, 2026-11-15) : un UUID, qui survit à l'instance là où `grille.id` lui est
    propre. Toute naissance en reçoit un neuf — import, formulaire, grille de travail, grille
    d'un bac à sable — ; il n'est jamais recopié d'un classeur."""
    return str(uuid.uuid4())


def identifiant_lu(valeur) -> str | None:
    """Un identifiant de grille tel qu'un classeur le dit, sous sa forme canonique (un UUID
    en minuscules) ; None s'il ne se lit pas comme tel."""
    try:
        return str(uuid.UUID(str(valeur).strip()))
    except (ValueError, AttributeError, TypeError):
        return None


def origine(g) -> dict | None:
    """L'ORIGINE d'une grille (sa ligne) : `{nom, version}` de la grille dont elle est
    dérivée, ou None. L'identifiant de la source ne sort pas : il ne dit rien à l'écran."""
    if g is None or not g["derivee_de_identifiant"]:
        return None
    return {"nom": g["derivee_de_nom"], "version": g["derivee_de_version"]}


# --------------------------------------------------------------------------- #
# Les versions, l'activation
# --------------------------------------------------------------------------- #
def version(conn: sqlite3.Connection, grille_id: int, numero: int):
    """La ligne d'une version, par sa grille et son numéro ; None si elle n'existe pas."""
    return conn.execute("SELECT * FROM grille_version WHERE grille_id = ? AND numero = ?",
                        (grille_id, numero)).fetchone()


def version_par_id(conn: sqlite3.Connection, version_id: int):
    return conn.execute("SELECT * FROM grille_version WHERE id = ?", (version_id,)).fetchone()


def derniere_version(conn: sqlite3.Connection, grille_id: int, *etats):
    """La version de plus haut numéro de cette grille, parmi ces états (tous sans rien)."""
    if etats:
        return conn.execute(
            f"SELECT * FROM grille_version WHERE grille_id = ? AND etat IN "
            f"({', '.join('?' * len(etats))}) ORDER BY numero DESC LIMIT 1",
            (grille_id, *etats)).fetchone()
    return conn.execute("SELECT * FROM grille_version WHERE grille_id = ? "
                        "ORDER BY numero DESC LIMIT 1", (grille_id,)).fetchone()


def activation(conn: sqlite3.Connection, projet_id, grille_id: int):
    """L'activation de cette grille dans ce projet — `projet_grille` jointe à sa version
    (`numero`, `etat`, `cible`) —, ou None si elle n'y est pas active."""
    if projet_id is None:
        return None
    return conn.execute(
        "SELECT pg.projet_id, pg.grille_id, pg.version_id, pg.active_le, v.numero, v.etat, "
        "v.cible FROM projet_grille pg JOIN grille_version v ON v.id = pg.version_id "
        "WHERE pg.projet_id = ? AND pg.grille_id = ?", (projet_id, grille_id)).fetchone()


def entree(conn: sqlite3.Connection, version_id: int, cle: str):
    return conn.execute("SELECT * FROM grille_entree WHERE version_id = ? AND cle = ?",
                        (version_id, cle)).fetchone()


# --------------------------------------------------------------------------- #
# Le contenu normalisé d'une version, et son empreinte
# --------------------------------------------------------------------------- #
def propre(valeur) -> str | None:
    """Une cellule NETTOYÉE : forme composée (NFC), espaces de bord retirés ; vide → None."""
    if valeur is None:
        return None
    s = unicodedata.normalize("NFC", str(valeur)).strip()
    return s or None


def contenu(conn: sqlite3.Connection, version_id: int) -> dict:
    """Le contenu d'une version, sous la forme NORMALISÉE que produit aussi la lecture d'un
    tableur (`grille_import.lire`) : c'est sur elle que se calculent l'empreinte, le bilan
    et le réexport. Les rangs y sont : l'empreinte les écarte, le réexport les suit."""
    v = version_par_id(conn, version_id)
    rubriques = {r["cle"]: {"libelle": r["libelle"], "parent_cle": r["parent_cle"],
                            "rang": r["rang"]}
                 for r in conn.execute("SELECT * FROM grille_rubrique WHERE version_id = ?",
                                       (version_id,))}
    exemples: dict = {}
    for x in conn.execute("SELECT * FROM grille_exemple WHERE version_id = ? "
                          "ORDER BY rang, id", (version_id,)):
        exemples.setdefault((x["entree_cle"], x["variante_cle"]), []).append(x["texte"])
    entrees = {}
    for e in conn.execute("SELECT * FROM grille_entree WHERE version_id = ?", (version_id,)):
        entrees[e["cle"]] = {
            "rubrique_cle": e["rubrique_cle"], "rang": e["rang"], "forme": e["forme"],
            "libelle": e["libelle"], "definition": e["definition"],
            "structure": e["structure"], "piege": e["piege"], "precision": e["precision"],
            "lien": bool(e["lien"]), "cible": e["cible"], "cardinalite": e["cardinalite"],
            "liste_cle": e["liste_cle"], "retiree": bool(e["retiree"]),
            "etat": e["etat"],
            "exemples": exemples.get((e["cle"], None), []), "variantes": {}}
    for x in conn.execute("SELECT * FROM grille_variante WHERE version_id = ?",
                          (version_id,)):
        if x["entree_cle"] in entrees:
            entrees[x["entree_cle"]]["variantes"][x["cle"]] = {
                "libelle": x["libelle"], "definition": x["definition"],
                "structure": x["structure"], "piege": x["piege"], "rang": x["rang"],
                "exemples": exemples.get((x["entree_cle"], x["cle"]), [])}
    listes = {l["cle"]: {"libelle": l["libelle"], "qualificatifs": {}}
              for l in conn.execute("SELECT * FROM grille_liste WHERE version_id = ?",
                                    (version_id,))}
    for q in conn.execute("SELECT * FROM grille_qualificatif WHERE version_id = ?",
                          (version_id,)):
        listes.setdefault(q["liste_cle"], {"libelle": None, "qualificatifs": {}})
        listes[q["liste_cle"]]["qualificatifs"][q["cle"]] = {
            "libelle": q["libelle"], "definition": q["definition"], "rang": q["rang"]}
    return {"cible": v["cible"] if v else None, "rubriques": rubriques, "entrees": entrees,
            "listes": listes}


def _sans_rangs(objet):
    """Le contenu sans ce qui ne fait pas une version : les rangs, l'ÉTAT d'une entrée (un
    état de travail, que le tableur ne porte pas : v39), et le drapeau `retiree`
    quand il est FAUX. Vrai, il compte (ANN-7, 2026-11-03) : retirer une entrée d'une grille
    ouverte change la version, et la remettre aussi — sans quoi la même empreinte dirait
    « aucun changement » et laisserait l'entrée retirée. Faux, il est absent, ce qui garde
    intactes les empreintes écrites avant lui."""
    if isinstance(objet, dict):
        return {k: _sans_rangs(v) for k, v in objet.items()
                if k not in ("rang", "etat") and not (k == "retiree" and not v)}
    if isinstance(objet, list):
        return [_sans_rangs(v) for v in objet]
    return objet


def _par_rang(objets: dict) -> list:
    return [k for k, _ in sorted(objets.items(), key=lambda kv: (kv[1].get("rang", 0), kv[0]))]


def ordre(c: dict) -> dict:
    """L'ORDRE d'un contenu, que l'empreinte écarte : les identifiants des rubriques, des
    entrées, des variantes de chaque entrée et des cases de chaque liste, dans l'ordre de
    leurs rangs. Deux contenus de même empreinte et de même ordre sont la même version À
    L'ÉCRAN — ce qu'on ne publie pas deux fois (`routes/grilles.publier_version`)."""
    return {"rubriques": _par_rang(c["rubriques"]), "entrees": _par_rang(c["entrees"]),
            "variantes": {k: _par_rang(e["variantes"]) for k, e in c["entrees"].items()},
            "cases": {lc: _par_rang(l["qualificatifs"]) for lc, l in c["listes"].items()}}


def empreinte(c: dict) -> str:
    """Le SHA-256 du contenu normalisé : cellules nettoyées, lignes triées par `cle` (les
    clés JSON triées), sans les rangs — réordonner les lignes du tableur ne fait pas une
    version (cadrage R3). Même empreinte, aucun changement écrit."""
    texte = json.dumps(_sans_rangs(c), sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"))
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Le plan rendu à l'écran
# --------------------------------------------------------------------------- #
def chemin_de_rubrique(rubriques: dict, cle) -> list:
    """Les clés de la rubrique `cle` et de ses ancêtres, de la plus large à la plus fine.
    Un parent circulaire (une base retouchée : l'import le refuse) s'arrête au premier
    retour."""
    chemin, vus = [], set()
    while cle is not None and cle in rubriques and cle not in vus:
        vus.add(cle)
        chemin.insert(0, cle)
        cle = rubriques[cle]["parent_cle"]
    return chemin


def plan(conn: sqlite3.Connection, version_id: int) -> dict:
    """Le plan entier d'une version, de quoi dessiner et filtrer côté écran sans aller-
    retour (R13) : les rubriques (ordonnées, avec leur parent et leur chemin), les entrées
    (ordonnées) avec leur cible et leur cardinalité EFFECTIVES, la précision et le lien
    attendus, leurs variantes et leurs exemples, les listes et leurs qualificatifs."""
    v = version_par_id(conn, version_id)
    c = contenu(conn, version_id)
    rubriques = [{"cle": cle, "libelle": r["libelle"], "parent_cle": r["parent_cle"],
                  "chemin": chemin_de_rubrique(c["rubriques"], cle), "rang": r["rang"]}
                 for cle, r in sorted(c["rubriques"].items(), key=lambda kv: kv[1]["rang"])]
    entrees = []
    for cle, e in sorted(c["entrees"].items(), key=lambda kv: kv[1]["rang"]):
        cibles = cibles_de(e["cible"]) or cibles_de(v["cible"])
        entrees.append({
            "cle": cle, "libelle": e["libelle"], "forme": e["forme"],
            "rubrique_cle": e["rubrique_cle"],
            "rubriques": chemin_de_rubrique(c["rubriques"], e["rubrique_cle"]),
            "definition": e["definition"], "structure": e["structure"], "piege": e["piege"],
            "exemples": e["exemples"], "precision": e["precision"], "lien": e["lien"],
            "cible_declaree": list(cibles_de(e["cible"])), "cibles": list(cibles),
            "pose": sorte_de_pose(cibles),
            "cardinalite": cardinalite_effective(e, cibles),
            "cardinalite_declaree": e["cardinalite"],
            "liste_cle": e["liste_cle"], "retiree": e["retiree"], "etat": e["etat"],
            "variantes": [{"cle": vc, "libelle": x["libelle"], "definition": x["definition"],
                           "structure": x["structure"], "piege": x["piege"],
                           "exemples": x["exemples"]}
                          for vc, x in sorted(e["variantes"].items(),
                                              key=lambda kv: kv[1]["rang"])]})
    listes = [{"cle": lc, "libelle": l["libelle"],
               "qualificatifs": [{"cle": qc, "libelle": q["libelle"],
                                  "definition": q["definition"]}
                                 for qc, q in sorted(l["qualificatifs"].items(),
                                                     key=lambda kv: kv[1]["rang"])]}
              for lc, l in sorted(c["listes"].items())]
    return {"version_id": version_id, "numero": v["numero"], "etat": v["etat"],
            "porte_sur": list(cibles_de(v["cible"])), "note": v["note"],
            "publiee_le": v["publiee_le"], "rubriques": rubriques, "entrees": entrees,
            "listes": listes}
