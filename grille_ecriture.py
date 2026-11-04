"""Une grille s'écrit SANS IMPORT — les règles du modèle, sans route (ANN-7 ; option HYBRIDE
tranchée par Hugo sur maquette le 2026-11-03 : un formulaire pour construire, le tableur pour
retoucher en nombre).

Le patron de `grille_import` : ni droit, ni verrou, ni commit — l'appelant (`routes/grilles.py`)
a vérifié qu'on gère le projet, tient le verrou et la transaction. Ici, ce qu'une écriture doit
au modèle :

- OÙ elle s'écrit (`version_en_ecriture`) : une grille OUVERTE dans sa version vivante, EN
  PLACE ; une grille FERMÉE dans son BROUILLON — et, quand elle n'en a pas, dans un brouillon
  qui naît de sa dernière version publiée, recopiée entière, au numéro suivant (le geste que
  fait l'import d'une version suivante, sans tableur). Une version publiée ne change pas,
  hors d'une coquille (`PATCH …/coquille`) ;
- ce qu'elle refuse : les REFUS DE L'IMPORT, aux mêmes codes (`valider`, qui relit la version
  ENTIÈRE après chaque geste, et non le seul objet touché) — de quoi garder qu'une version
  écrite au formulaire se réexporte en un tableur qui se réimporte ;
- ce qu'elle doit aux relevés, sur une grille ouverte : les règles du réimport
  (`grille_import.reconcilier_ouverte`), réemployées et non récrites — une entrée employée ne
  se supprime jamais, elle se RETIRE ou se FUSIONNE ; sous des relevés, une entrée ne change
  ni de forme ni de liste ; une variante ou une case employée ne disparaît pas ;
- les identifiants reçus du NOM quand on ne les donne pas, par la dérivation de l'import
  (`grille_import._Identifiants`).

Rien de ce module ne crée ni ne casse un relevé : ce que l'écriture rend « à revoir » (une
entrée retirée, une cible qui ne convient plus) se DÉRIVE dans `releves_effectifs`.
"""
from __future__ import annotations

import sqlite3

import grille_import
import grille_tableur
import grilles
from grille_import import Refus, _faute
from grilles import CARDINALITES, FORMES, propre

# Les champs d'une entrée que le formulaire écrit (les six questions du catalogue et « ce que
# lit l'annotateur »), et ceux d'une variante, d'une rubrique, d'une liste, d'une case.
CHAMPS_ENTREE = ("libelle", "rubrique_cle", "forme", "definition", "structure", "piege",
                 "exemples", "precision", "lien", "cible", "cardinalite", "liste_cle")
CHAMPS_VARIANTE = ("libelle", "definition", "structure", "piege", "exemples")
CHAMPS_RUBRIQUE = ("libelle", "parent_cle")
CHAMPS_LISTE = ("libelle",)
CHAMPS_CASE = ("libelle", "definition")
CHAMPS_VERSION = ("porte_sur", "note")


# --------------------------------------------------------------------------- #
# Où l'on écrit
# --------------------------------------------------------------------------- #
def version_en_ecriture(conn: sqlite3.Connection, g, *, par=None) -> tuple[dict, bool]:
    """La version où s'écrit un geste du formulaire, et si elle vient de naître.

    Ouverte : sa version vivante, en place. Fermée : son brouillon ; sans brouillon, un
    brouillon NEUF, copie entière de la dernière version publiée (plan, entrées retirées
    comprises), au numéro suivant, sans note — la note dit ce que la version change, et elle
    n'a encore rien changé. Sa naissance s'écrit au journal sous la grille. Une grille
    retirée ne s'écrit plus (409, la règle de l'import)."""
    import journal                               # import paresseux, le patron de `grille_import`
    if g["retiree_le"]:
        raise Refus(409, "Cette grille est retirée : elle ne s'écrit plus.")
    if g["ouverte"]:
        v = grilles.derniere_version(conn, g["id"], grilles.ETAT_VIVANTE)
        if v is None:
            raise Refus(409, "Cette grille ouverte n'a pas de version vivante.")
        return dict(v), False
    b = grilles.derniere_version(conn, g["id"], grilles.ETAT_BROUILLON)
    if b is not None:
        return dict(b), False
    publiee = grilles.derniere_version(conn, g["id"], grilles.ETAT_PUBLIEE)
    if publiee is None:
        raise Refus(409, "Cette grille n'a ni brouillon ni version publiée.")
    numero = grilles.derniere_version(conn, g["id"])["numero"] + 1
    vid = grille_import.ecrire_version(conn, g["id"], grilles.contenu(conn, publiee["id"]),
                                       numero=numero, etat=grilles.ETAT_BROUILLON, note=None,
                                       par=par)
    journal.journaliser(conn, "creation", "grille", g["id"],
                        apres={"brouillon": {"numero": numero,
                                             "depuis": publiee["numero"]}})
    return dict(grilles.version_par_id(conn, vid)), True


def reference(conn: sqlite3.Connection, grille_id: int) -> dict | None:
    """Le contenu auquel l'import compare — la dernière version publiée ou vivante —, d'où
    se reprend l'identifiant d'un objet de même nom (`cle_neuve`)."""
    v = grilles.derniere_version(conn, grille_id, grilles.ETAT_PUBLIEE, grilles.ETAT_VIVANTE)
    return grilles.contenu(conn, v["id"]) if v is not None else None


# --------------------------------------------------------------------------- #
# Ce qu'on reçoit, ramené à la forme du contenu (`grilles.contenu`)
# --------------------------------------------------------------------------- #
def texte(valeur) -> str | None:
    return propre(valeur)


def exemples(valeurs) -> list:
    return [x for x in (propre(e) for e in (valeurs or [])) if x]


def cibles(valeur) -> tuple[str | None, str | None]:
    """Une cible reçue — une liste de sortes, ou une cellule (« bulle | cartouche », « la
    case ») — → (sa forme en base, None) ou (None, l'erreur). Vide : None, sans erreur."""
    if isinstance(valeur, (list, tuple)):
        valeur = " | ".join(str(x) for x in valeur)
    sortes, erreur = grilles.lire_cibles(grille_tableur.cibles_lues(valeur))
    return (None, erreur) if erreur else (grilles.ecrire_cibles(sortes), None)


def forme(valeur) -> str | None:
    return grille_tableur.forme_lue(valeur) if valeur is not None else None


def cardinalite(valeur) -> str | None:
    lue = grille_tableur.cardinalite_lue(valeur) if valeur is not None else None
    return lue or None


def cle_donnee(valeur, *, rubrique: bool = False) -> str | None:
    """Un identifiant DONNÉ : nettoyé ; 422 s'il ne tiendrait pas dans une adresse ou dans le
    tableur (une barre oblique, et pour une rubrique le « > » qui sépare ses étages)."""
    cle = propre(valeur)
    if cle is None:
        return None
    interdits = "/>" if rubrique else "/"
    if any(c in cle for c in interdits):
        raise Refus(422, f"L'identifiant « {cle} » porte un caractère qu'un identifiant ne "
                         f"porte pas ({' ou '.join(f'« {c} »' for c in interdits)}).")
    return cle


def cle_neuve(nom, *, deja: dict, ref: dict | None, defaut: str, quoi: str,
              texte_=None) -> str:
    """L'identifiant d'un objet créé sans le sien : la dérivation de l'import
    (`grille_import._Identifiants`) — repris d'un objet de même NOM dans la version de
    référence, s'il n'est pas déjà dans celle qu'on écrit ; sinon dérivé du libellé, hors de
    tout identifiant de l'une et de l'autre. `deja` et `ref` : les objets de même sorte (les
    entrées, les variantes d'une entrée, les rubriques, les listes, les cases d'une liste),
    par identifiant ; une rubrique se nomme par son CHEMIN (`nom` est alors un tuple de
    libellés, `texte_` son dernier étage)."""
    ref = ref or {}
    libres = {k: x for k, x in ref.items() if k not in deja}
    if quoi == "rubrique":
        par_nom = grille_import._chemins_de_reference(ref)
        par_nom = {n: [k for k in ks if k in libres] for n, ks in par_nom.items()}
    else:
        par_nom = grille_import._par_nom(libres)
    ids = grille_import._Identifiants(set(deja) | set(ref), par_nom)
    return ids.donner(nom, defaut=defaut, quoi=quoi, texte=texte_)


def chemin(rubriques: dict, parent_cle, libelle) -> tuple:
    """Le chemin (les libellés, du plus large au plus fin) d'une rubrique de ce libellé, sous
    ce parent."""
    return tuple(rubriques[r]["libelle"] for r in grilles.chemin_de_rubrique(rubriques,
                                                                              parent_cle)) \
        + (libelle,)


def rang_suivant(objets: dict) -> int:
    return max([x.get("rang", 0) for x in objets.values()] + [-1]) + 1


# --------------------------------------------------------------------------- #
# Ce qu'un relevé emploie
# --------------------------------------------------------------------------- #
def releves_sur(conn, grille_id: int, entree_cle: str, variante_cle=None) -> int:
    """Les relevés posés sur cette entrée (cette variante) de la grille, toutes versions
    confondues : sur une grille fermée, une entrée employée dans une version publiée l'est
    pour le brouillon qui la suit. La règle de l'import (`grille_import._releves_sur`)."""
    return grille_import._releves_sur(conn, grille_id, entree_cle, variante_cle)


def releves_sur_case(conn, grille_id: int, qualificatif_cle: str) -> int:
    return grille_import._releves_sur_qualificatif(conn, grille_id, qualificatif_cle)


def emplois(conn, g, v: dict, c: dict) -> dict:
    """Ce qu'un relevé emploie dans la grille `g`, pour que le FORMULAIRE n'offre que les
    gestes que le serveur accepte (la case « Le formulaire suit cette règle ») : une entrée
    employée se retire — ou, sur une grille ouverte, se fusionne —, jamais ne se supprime ;
    une variante ou une case employée ne se supprime pas. Les comptes sont ceux des refus
    (`releves_sur`, `releves_sur_case`) : toutes versions confondues. `c` : le contenu de la
    version `v`, que le formulaire montre.

    Rend `{"entrees": {cle: n}, "variantes": {cle: {vc: n}}, "cases": {qc: n},
    "fusionner_dans": {cle: [...]}}` — les seuls objets employés ; `fusionner_dans` (dans une
    version VIVANTE seulement) : les entrées où la fusion se ferait, la règle du refus de
    `routes/grilles.supprimer_entree` (`grille_import._vers_possibles`)."""
    entrees, variantes = {}, {}
    for r in conn.execute("SELECT entree_cle, variante_cle, COUNT(*) AS n FROM releve "
                          "WHERE grille_id = ? GROUP BY entree_cle, variante_cle", (g["id"],)):
        entrees[r["entree_cle"]] = entrees.get(r["entree_cle"], 0) + r["n"]
        if r["variante_cle"] is not None:
            variantes.setdefault(r["entree_cle"], {})[r["variante_cle"]] = r["n"]
    cases = {r["qualificatif_cle"]: r["n"] for r in conn.execute(
        "SELECT rq.qualificatif_cle, COUNT(*) AS n FROM releve_qualificatif rq "
        "JOIN releve r ON r.id = rq.releve_id WHERE r.grille_id = ? "
        "GROUP BY rq.qualificatif_cle", (g["id"],))}
    fusionner = {}
    if v["etat"] == grilles.ETAT_VIVANTE:
        for cle in c["entrees"]:
            if not entrees.get(cle):
                continue
            employees = {r[0] for r in conn.execute(
                "SELECT DISTINCT variante_cle FROM releve WHERE grille_id = ? "
                "AND version_id = ? AND entree_cle = ? AND variante_cle IS NOT NULL",
                (g["id"], v["id"], cle))}
            sans = {**c, "entrees": {k: x for k, x in c["entrees"].items() if k != cle}}
            fusionner[cle] = grille_import._vers_possibles(c, sans, cle, employees)
    return {"entrees": entrees, "variantes": variantes, "cases": cases,
            "fusionner_dans": fusionner}


# --------------------------------------------------------------------------- #
# Les refus de l'import, sur une version entière
# --------------------------------------------------------------------------- #
def _sans_separateur(textes) -> bool:
    """Un exemple ne porte ni « | » ni retour à la ligne : le tableur les lit comme deux
    exemples, et la version réexportée ne se réimporterait plus à l'identique."""
    return all(grille_import.SEP_EXEMPLES not in t and "\n" not in t and "\r" not in t
               for t in textes)


def valider(c: dict) -> tuple[list, list]:
    """Les FAUTES (refusent l'écriture) et les AVERTISSEMENTS d'une version entière, aux codes
    de l'import (`grille_import.lire_tableur`) — sans fichier ni ligne : il n'y a pas de
    tableur. Trois codes de plus, pour ce qu'un tableur ne peut pas écrire mais qu'un
    formulaire enverrait : une rubrique au parent inconnu, une entrée rangée dans une
    rubrique inconnue, une entrée à cocher dans une liste VIDE (que le tableur, qui ne connaît
    une liste que par ses cases, lirait inconnue) ; et deux pour ce qu'il découperait — un
    « > » dans un nom de rubrique, un « | » dans un exemple. Rend (fautes, avertissements)."""
    fautes, avert = [], []

    def faute(code, probleme, a_faire=None, *, cle=None, colonne=None, listes=False):
        fautes.append(_faute(code, probleme, a_faire, cle=cle, colonne=colonne, listes=listes))

    sortes, erreur = grilles.lire_cibles(c["cible"])
    if erreur:
        faute("porte_sur_inconnu", f"« Porte sur » : {erreur}", colonne="porte_sur")
    elif not sortes:
        faute("porte_sur_manque", "« Porte sur » manque : sur quoi la grille se pose-t-elle ?",
              "des mots, la case, la planche, ou des sortes de zone", colonne="porte_sur")
    rubriques, listes = c["rubriques"], c["listes"]
    vus_chemin: dict = {}
    dits_en_boucle: set = set()
    for rc, r in rubriques.items():
        if not r["libelle"]:
            faute("libelle_vide", "la rubrique n'a pas de nom", "donnez-lui un nom", cle=rc,
                  colonne="rubrique")
        elif grille_import.SEP_RUBRIQUE in r["libelle"]:
            faute("rubrique_separateur", f"le nom de la rubrique « {r['libelle']} » porte un "
                  f"« {grille_import.SEP_RUBRIQUE} », qui sépare les étages d'une rubrique",
                  "retirez-le ; pour ranger une rubrique dans une autre, choisissez sa place",
                  cle=rc, colonne="rubrique")
        if r["parent_cle"] is not None and r["parent_cle"] not in rubriques:
            faute("rubrique_parent_inconnu", f"la rubrique « {r['libelle']} » est rangée sous "
                  f"« {r['parent_cle']} », qui n'existe pas", "choisissez une autre place",
                  cle=rc, colonne="rubrique")
        autre = vus_chemin.setdefault((r["parent_cle"], r["libelle"]), rc)
        if autre != rc:
            faute("rubrique_deux_identifiants", f"deux rubriques s'appellent « {r['libelle']} » "
                  "au même endroit", "renommez l'une, ou rangez-la ailleurs", cle=rc,
                  colonne="rubrique")
        vus, x = [], rc
        while x is not None and x in rubriques:
            if x in vus:                  # un cycle, dit UNE fois, à sa première rubrique
                boucle = vus[vus.index(x):]
                if rc == x and not dits_en_boucle & set(boucle):
                    dits_en_boucle.update(boucle)
                    faute("rubrique_circulaire", f"la rubrique « {rc} » est son propre "
                          "ancêtre", "rangez-la ailleurs", cle=rc, colonne="rubrique")
                break
            vus.append(x)
            x = rubriques[x]["parent_cle"]
    for k, e in c["entrees"].items():
        if e["forme"] not in FORMES:
            faute("forme_inconnue", f"la réponse « {e['forme'] or ''} » n'est pas une forme",
                  " · ".join(FORMES), cle=k, colonne="forme")
        if not e["libelle"]:
            faute("libelle_vide", "l'entrée n'a pas de nom", "donnez-lui un nom", cle=k,
                  colonne="libelle")
        if e["rubrique_cle"] is not None and e["rubrique_cle"] not in rubriques:
            faute("rubrique_inconnue", f"l'entrée est rangée dans « {e['rubrique_cle']} », qui "
                  "n'est pas une rubrique de la grille", "choisissez une rubrique, ou aucune",
                  cle=k, colonne="rubrique")
        liste = e["liste_cle"]
        if e["forme"] == "qualificatifs":
            if not liste:
                faute("liste_manque", "l'entrée se pose avec des cases d'une liste, et aucune "
                      "liste n'est nommée", "choisissez une liste", cle=k, colonne="liste")
            elif liste not in listes:
                faute("liste_inconnue", f"la liste « {liste} » n'existe pas",
                      "choisissez une liste de la grille", cle=k, colonne="liste")
            elif not listes[liste]["qualificatifs"]:
                faute("liste_vide", f"la liste « {listes[liste]['libelle'] or liste} » n'a "
                      "aucune case", "ajoutez-lui une case d'abord", cle=k, colonne="liste")
        elif liste:
            faute("liste_hors_qualificatifs", f"une liste est nommée (« {liste} »), mais "
                  "l'entrée ne se pose pas avec des cases d'une liste",
                  "répondez « des cases d'une liste », ou ne nommez pas de liste", cle=k,
                  colonne="liste")
        _, erreur = grilles.lire_cibles(e["cible"])
        if erreur:
            faute("cible_inconnue", erreur, cle=k, colonne="cible")
        if e["cardinalite"] is not None and e["cardinalite"] not in CARDINALITES:
            faute("cardinalite_inconnue", f"la réponse « {e['cardinalite']} » n'est pas un "
                  "nombre de fois", "une seule, plusieurs, ou comme d'ordinaire", cle=k,
                  colonne="cardinalite")
        if e["variantes"] and e["forme"] != "variantes":
            faute("variante_sous_autre_forme", f"« {e['libelle'] or k} » a des variantes, et ne "
                  "se pose pas avec une variante", "répondez « une variante », ou retirez "
                  "d'abord ses variantes", cle=k, colonne="variante")
        if e["forme"] == "variantes" and not e["variantes"]:
            faute("variantes_absentes", "l'entrée se pose avec une variante, et n'en a "
                  "aucune", "donnez-lui au moins une variante", cle=k, colonne="forme")
        for vc, x in e["variantes"].items():
            if not x["libelle"]:
                faute("variante_sans_nom", f"la variante « {vc} » n'a pas de nom",
                      "donnez-lui un nom", cle=k, colonne="variante")
            if not _sans_separateur(x["exemples"]):
                faute("exemple_separateur", f"un exemple de la variante « {x['libelle'] or vc} »"
                      " porte un « | » ou un retour à la ligne, qui séparent deux exemples",
                      "écrivez chaque exemple à part", cle=k, colonne="exemples")
        if not _sans_separateur(e["exemples"]):
            faute("exemple_separateur", "un exemple porte un « | » ou un retour à la ligne, "
                  "qui séparent deux exemples", "écrivez chaque exemple à part", cle=k,
                  colonne="exemples")
        effectives = grilles.cibles_de(e["cible"]) or sortes
        if grilles.CIBLE_ENTITE in effectives:
            avert.append(_faute(
                "vise_l_entite", "l'entrée vise l'entité du registre : aucun relevé ne s'y pose "
                "avant l'étage de projet des personnages (G3)", cle=k, colonne="cible"))
    for lc, l in listes.items():
        for qc, q in l["qualificatifs"].items():
            if not q["libelle"]:
                faute("libelle_vide", f"la case « {qc} » n'a pas de nom", "donnez-lui un nom",
                      cle=qc, colonne="libelle", listes=True)
    utilisees = {e["liste_cle"] for e in c["entrees"].values() if e["liste_cle"]}
    for lc in listes:
        if lc not in utilisees:
            avert.append(_faute("liste_inutilisee", f"la liste « {listes[lc]['libelle'] or lc} »"
                                " n'est nommée par aucune entrée", cle=lc, colonne="liste",
                                listes=True))
    return fautes, avert


# --------------------------------------------------------------------------- #
# Écrire une version
# --------------------------------------------------------------------------- #
def ecrire(conn: sqlite3.Connection, g, v: dict, avant: dict, apres: dict, *,
           note=None, reponses: dict | None = None) -> tuple[list, list]:
    """Écrit `apres` dans la version `v` (de la grille `g`), qui portait `avant` ; `note` :
    la note de la version (celle qu'elle porte, si l'appelant ne la change pas). Rend
    (avertissements, fusions faites — chacune avec ses `releve_ids`).

    1. Les refus de l'import, sur la version entière (`valider`) : 422 et toutes les fautes.
    2. Sur une version VIVANTE, les règles du réimport d'une grille ouverte
       (`grille_import.reconcilier_ouverte`) : une entrée employée qui disparaîtrait attend
       « retirer » ou « fusionner dans… » (409, avec ce qu'on peut faire) ; ce qui
       changerait sous des relevés est refusé (409, les fautes) ; une fusion reporte les
       relevés (`grille_import._fusionner`). Une entrée déjà RETIRÉE se supprime ou se
       fusionne aussi : le réimport la garderait retirée sans rien demander, le formulaire
       la nomme exprès.
    3. Le plan récrit en place, puis « Porte sur », la note et l'empreinte de la version,
       relue sur ce qui est écrit (le patron de la coquille)."""
    fautes, avert = valider(apres)
    if fautes:
        raise Refus(422, f"La grille est refusée : {len(fautes)} faute(s). Rien n'est écrit.",
                    fautes)
    fusions = []
    if v["etat"] == grilles.ETAT_VIVANTE:
        # Une entrée retirée que le geste fait PARTIR (supprimée, fusionnée) se lit non
        # retirée : le réimport la garderait retirée sans lire la réponse, quand le
        # formulaire la nomme exprès — employée, elle attend encore « fusionner dans… ».
        partent = {k for k, e in avant["entrees"].items()
                   if e.get("retiree") and k not in apres["entrees"]}
        lu = {**avant, "entrees": {k: ({**e, "retiree": False} if k in partent else e)
                                   for k, e in avant["entrees"].items()}}
        apres, a_repondre, fusions, fautes = grille_import.reconcilier_ouverte(
            conn, g["id"], v["id"], lu, apres, reponses or {})
        if fautes:
            raise Refus(409, f"La grille ouverte ne s'écrit pas ainsi : {len(fautes)} point(s) "
                             "à régler. Rien n'est écrit.", fautes)
        if a_repondre:
            raise Refus(409, "Des relevés sont posés sur cette entrée : elle ne se supprime "
                             "pas. Retirez-la, ou fusionnez-la dans une autre. Rien n'est "
                             "écrit.", [], {"a_repondre": a_repondre})
        for f in fusions:
            f["releve_ids"] = grille_import._fusionner(conn, g["id"], v["id"], f)
    elif reponses:                    # une fusion ne se fait que dans une version vivante
        raise Refus(409, "Une fusion ne s'écrit que dans une grille ouverte.")
    grille_import.effacer_plan(conn, v["id"])
    grille_import.ecrire_plan(conn, v["id"], apres)
    conn.execute("UPDATE grille_version SET cible = ?, note = ? WHERE id = ?",
                 (apres["cible"], note, v["id"]))
    conn.execute("UPDATE grille_version SET empreinte = ? WHERE id = ?",
                 (grilles.empreinte(grilles.contenu(conn, v["id"])), v["id"]))
    return avert, fusions
