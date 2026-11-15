"""Une grille s'écrit dans un TABLEUR, BD_ditor la vérifie et la garde (ANN-7, tranche 1 ;
cadrage R3, tranché par Hugo le 2026-10-14 et le 2026-10-25 ; le gabarit et le bilan, tranchés
sur maquette le 2026-11-03).

Cœur partagé, sans I/O propre — le patron de `lexique_import` : il reçoit des FLUX de texte
(ou les octets d'un classeur) et une CONNEXION, l'appelant ouvre les fichiers et tient la
transaction. Deux enveloppes : `tools/importer_grille.py` et
`POST /api/projets/{id}/grilles/import`.

Le FORMAT a deux formes, que `grille_tableur` décrit et que ce module lit toutes deux : deux
CSV point-virgule aux colonnes MACHINE (`cle`, `forme`, `libelle`…), ou un classeur `.xlsx`
dont les titres sont les QUESTIONS du gabarit (« 4. Ce qu'on choisit ») et les cellules des
réponses EN MOTS (« une variante », « la case »). Les deux se mêlent : un titre ou une valeur
se lit d'un côté ou de l'autre. `docs/import-grille.md` le dit pour qui remplit le tableur.

1. Les entrées : une ligne par ENTRÉE, et une ligne par VARIANTE. Une ligne de variante
   répète la `cle` de son entrée — ou la laisse vide, et appartient alors à l'entrée du
   DESSUS —, porte son libellé (`variante`), et laisse vides les colonnes propres à
   l'entrée, ou y recopie exactement celles de l'entrée.
2. Les listes de qualificatifs, facultatives : une ligne par qualificatif.
3. La DÉCLARATION (nom, ouverte ou fermée, « Porte sur », note) : en arguments de l'outil, en
   champs du formulaire de la route, ou dans la feuille « 1. La grille » du classeur.

Les IDENTIFIANTS sont facultatifs à la création (`_Identifiants`) : une entrée, une
variante, une rubrique, une liste ou un qualificatif sans le sien le reçoit de son NOM —
repris d'un objet de même nom dans la version à laquelle on compare, sinon DÉRIVÉ du libellé
(`grille_tableur.deriver`). Le réexport les rend, pour qu'un renommage reste un renommage.

La VALIDATION refuse le fichier ENTIER à la première anomalie de structure, et les dit
TOUTES (G12) : une ligne écartée se lirait, dans le bilan, comme une entrée disparue. Ce qui
ne casse rien est un AVERTISSEMENT. Les deux sont des DONNÉES (`_faute`) — où (feuille ou
fichier, ligne), quelle entrée, quelle question, ce qui ne va pas, ce qu'il faut faire —, que
l'écran dessine et que `en_mots` rend lisibles à l'outil.

Le BILAN compare au plus récent état publié de la grille (ou à sa version vivante), par
`cle` : ce qui naît, ce qui est renommé, retouché, déplacé, changé, ce qui disparaît — avec le
nombre de relevés posés sur chaque disparu. Il porte en tête un VERDICT, « À savoir » (les
avertissements) et « Ce qui va naître ». Pour une grille OUVERTE qu'on réimporte (tranché par
Hugo le 2026-11-03), une entrée EMPLOYÉE qui disparaît ne se supprime jamais : le bilan
demande « retirer » ou « fusionner dans… », et l'import attend la réponse.
"""
from __future__ import annotations

import copy
import csv
import io
import sqlite3
import zipfile

import grille_tableur
import grilles
from sortie_csv import ecrivain_csv
from grille_tableur import FormatInvalide, TropGros  # noqa: F401 — ré-exportées
from grilles import CARDINALITES, FORMES, propre

COLONNES = ("cle", "rubrique", "rubrique_cle", "forme", "libelle", "variante_cle",
            "variante", "structure", "definition", "exemples", "piege", "liste",
            "precision", "lien", "cible", "cardinalite")
OBLIGATOIRES = ("forme", "libelle")


def sans_cible(contenu: dict) -> list[str]:
    """Les libellés des entrées vivantes qui ne disent pas où elles se posent, dans une
    version sans défaut : ce qui retient une publication."""
    if grilles.cibles_de(contenu["cible"]):
        return []
    return [e["libelle"] or cle for cle, e in sorted(contenu["entrees"].items(),
                                                       key=lambda kv: kv[1]["rang"])
            if not e.get("retiree") and not grilles.cibles_de(e["cible"])]


def _forme_en_faute(valeur) -> str:
    """Le problème d'une forme refusée : une réponse qu'on ne connaît pas, ou aucune."""
    texte = str(valeur or "").strip()
    return (f"la réponse « {texte} » n'est pas une forme" if texte
            else "aucune réponse : l'entrée ne dit pas ce qu'on choisit")
# Les colonnes PROPRES à une entrée : vides sur une ligne de variante, ou recopiées.
COLONNES_DE_L_ENTREE = ("rubrique", "rubrique_cle", "forme", "libelle", "liste",
                        "precision", "lien", "cible", "cardinalite")
COLONNES_LISTES = ("liste_cle", "liste", "cle", "libelle", "definition")
SEP_RUBRIQUE = ">"
SEP_EXEMPLES = "|"
NOMS_FICHIERS = ("grille-rubriques-entrees.csv", "grille-listes-qualificatifs.csv")
NOMS_PAR_DEFAUT = ("entrées", "listes")

# Les réponses à une entrée employée qui disparaît d'une grille ouverte.
RETIRER, FUSIONNER = "retirer", "fusionner"


class Refus(Exception):
    """L'import ne se fait pas : `statut` (le code HTTP qu'une route rendrait), un message,
    les anomalies quand c'est le tableur qui est refusé, et le `bilan` quand il y en a un —
    le verdict, « À savoir », ce qui attend une réponse."""

    def __init__(self, statut: int, message: str, anomalies=None, bilan=None):
        super().__init__(message)
        self.statut, self.message = statut, message
        self.anomalies, self.bilan = list(anomalies or []), dict(bilan or {})


# --------------------------------------------------------------------------- #
# Une faute, un avertissement : des DONNÉES
# --------------------------------------------------------------------------- #
CHAMPS_FAUTE = ("code", "fichier", "ligne", "cle", "colonne", "question", "probleme",
                "a_faire")


def _faute(code: str, probleme: str, a_faire=None, *, fichier=None, ligne=None, cle=None,
           colonne=None, listes: bool = False) -> dict:
    """Une anomalie (ou un avertissement) : `code` (stable, pour l'écran et les tests), où —
    `fichier` (la feuille ou le fichier), `ligne` —, l'entrée (`cle`), la `colonne` machine
    et la `question` telle que le classeur la pose, ce qui ne va pas (`probleme`) et ce qu'il
    faut faire (`a_faire`), en mots."""
    titres = {**(grille_tableur.TITRES_LISTES if listes else grille_tableur.TITRES),
              **grille_tableur.TITRES_GRILLE}
    return {"code": code, "fichier": fichier, "ligne": ligne, "cle": cle, "colonne": colonne,
            "question": titres.get(colonne) if colonne else None, "probleme": probleme,
            "a_faire": a_faire}


def _complete(f: dict) -> dict:
    """Une faute venue du classeur (une formule, une date) : toutes ses clés."""
    return {**{c: None for c in CHAMPS_FAUTE}, **f}


def en_mots(f) -> str:
    """Une faute ou un avertissement, lisible d'une ligne : « entrées, ligne 12 · « cri » ·
    4. Ce qu'on choisit : forme « libre » inconnue → répondez … »."""
    if isinstance(f, str):
        return f
    ou = []
    if f.get("fichier"):
        ou.append(f"{f['fichier']}" + (f", ligne {f['ligne']}" if f.get("ligne") else ""))
    if f.get("cle"):
        ou.append(f"« {f['cle']} »")
    if f.get("question"):
        ou.append(f["question"])
    texte = (" · ".join(ou) + " : " if ou else "") + f["probleme"]
    return texte + (f" → {f['a_faire']}" if f.get("a_faire") else "")


# --------------------------------------------------------------------------- #
# Lecture et validation
# --------------------------------------------------------------------------- #
_FORMULE = ("=", "+", "-", "@", chr(9), chr(13))


def _neutre(valeur) -> str:
    """Une cellule du réexport CSV, neutralisée contre l'injection de formule : une cellule
    qui commence par `= + - @` serait EXÉCUTÉE par un tableur ; on la préfixe d'une
    apostrophe (le patron de `socle._csv_safe`), que l'import retire."""
    v = "" if valeur is None else str(valeur)
    return "'" + v if v[:1] in _FORMULE else v


def _sans_echappement(valeur):
    """L'inverse de `_neutre`, à la lecture : l'apostrophe devant `= + - @` est retirée, et
    elle seule — « 'tain » reste « 'tain »."""
    if valeur and len(valeur) > 1 and valeur[0] == "'" and valeur[1] in _FORMULE:
        return valeur[1:]
    return valeur


def _etages(texte) -> list:
    return [propre(x) for x in str(texte or "").split(SEP_RUBRIQUE)] if texte else []


def _exemples(texte) -> list:
    """Plusieurs exemples : séparés par « | », ou un par ligne dans la cellule."""
    morceaux = str(texte or "").replace("\r\n", "\n").replace("\n", SEP_EXEMPLES)
    return [x for x in (propre(e) for e in morceaux.split(SEP_EXEMPLES)) if x]


def _exiger(nom, entete, obligatoires, *, listes: bool) -> list:
    """Les colonnes MACHINE d'un en-tête (None pour une colonne ignorée). Lève
    `FormatInvalide` quand une colonne obligatoire manque."""
    cols = [grille_tableur.colonne_de(t, listes=listes) for t in entete]
    titres = grille_tableur.TITRES_LISTES if listes else grille_tableur.TITRES
    manquantes = [c for c in obligatoires if c not in cols]
    if listes and "liste_cle" not in cols and "liste" not in cols:
        manquantes.insert(0, "liste")
    if manquantes:
        raise FormatInvalide(
            f"{nom} : en-tête invalide, colonnes obligatoires manquantes "
            + ", ".join(f"{c} (« {titres.get(c, c)} »)" for c in manquantes)
            + ". La première ligne qui n'est ni vide ni un commentaire est l'en-tête.")
    return cols


def _par_colonne(nom, entete, lignes, attendues, *, listes, obligatoires, anomalies):
    """Les lignes d'une feuille, par nom de colonne MACHINE, cellules nettoyées ; une ligne
    où rien n'est écrit dans une colonne connue est ignorée."""
    cols = _exiger(nom, entete, obligatoires, listes=listes)
    sortie = []
    for n, cellules in lignes:
        if any(str(x).strip() for x in cellules[len(cols):]):
            anomalies.append(_faute(
                "cellules_en_trop", "la ligne a plus de cellules que l'en-tête n'a de colonnes",
                "un « ; » dans une cellule ? Mettez la cellule entre guillemets, ou retirez "
                "le « ; »", fichier=nom, ligne=n, listes=listes))
            continue
        ligne = {c: None for c in attendues}
        for c, v in zip(cols, cellules):
            if c in ligne and ligne[c] is None:
                ligne[c] = _sans_echappement(propre(v))
        if any(v is not None for v in ligne.values()):
            sortie.append((n, ligne))
    return sortie


SEP_ADRESSE = "/"


def _barres_obliques(nom, lignes, colonnes, *, listes, anomalies) -> None:
    """Un identifiant ÉCRIT qui porte une « / » est une faute : il ne tiendrait pas dans
    l'adresse d'une route (`…/entrees/{cle}/variantes/{variante}`), que le formulaire emploie
    pour l'écrire, ni dans la charge du journal (« variante:cri/bang ») ; le formulaire le
    refuse déjà (`grille_ecriture.cle_donnee`). Une fois par valeur, à sa première ligne :
    la ligne d'une variante répète l'identifiant de son entrée."""
    dits = set()
    for n, l in lignes:
        for c in colonnes:
            valeur = l.get(c)
            if not valeur or SEP_ADRESSE not in valeur or (c, valeur) in dits:
                continue
            dits.add((c, valeur))
            anomalies.append(_faute(
                "cle_barre_oblique", f"l'identifiant « {valeur} » porte une « / », qu'un "
                "identifiant ne porte pas", "retirez-la, ou videz la cellule : l'identifiant "
                "se prendra du nom", fichier=nom, ligne=n, colonne=c, listes=listes))


class _Identifiants:
    """Les identifiants qui MANQUENT, reçus du NOM (ANN-7, tranché le 2026-11-03 : la colonne
    grise du classeur peut être vide). Règle, dans cet ordre :

    1. un identifiant écrit dans le fichier est gardé tel quel, et aucun autre ne le prend ;
    2. sans identifiant, l'objet REPREND celui de l'objet de même NOM dans la version à
       laquelle on compare (même libellé exact ; pour une rubrique, même chemin ; pour une
       variante ou un qualificatif, sous la même entrée ou la même liste), si aucune ligne
       du fichier ne le revendique — deux objets de même nom les reprennent dans l'ordre ;
    3. sinon il est DÉRIVÉ du libellé (`grille_tableur.slug` : `écho lointain` →
       `echo-lointain`), suffixé `-2`, `-3`… s'il est déjà pris — par le fichier ou par la
       version de référence, pour qu'un nouveau venu ne passe jamais pour un renommage.

    Stable : le même fichier, comparé à la même version, rend les mêmes identifiants ; le
    réexport les écrit, et un fichier réexporté ne dérive plus rien."""

    def __init__(self, deja_pris, reference_par_nom: dict):
        self.prises = set(deja_pris)
        self.reprendre = {k: list(v) for k, v in reference_par_nom.items()}
        self.deduits: list = []

    def reserver(self, cles) -> None:
        explicites = {c for c in cles if c}
        self.prises |= explicites
        for nom in self.reprendre:
            self.reprendre[nom] = [c for c in self.reprendre[nom] if c not in explicites]

    def donner(self, nom, *, defaut: str, quoi: str, ligne=None, fichier=None,
               texte=None) -> str:
        """L'identifiant de l'objet `nom` (son libellé ; pour une rubrique, son chemin) ;
        `texte` : ce dont on le dérive, quand ce n'est pas `nom`."""
        repris = self.reprendre.get(nom) or []
        if repris:
            cle, reprise = repris.pop(0), True
            self.prises.add(cle)
        else:
            cle = grille_tableur.deriver(nom if texte is None else texte, self.prises,
                                         defaut=defaut)
            reprise = False
        self.deduits.append({"quoi": quoi, "fichier": fichier, "ligne": ligne,
                             "libelle": nom if texte is None else texte, "cle": cle,
                             "repris": reprise})
        return cle


def _par_nom(objets: dict, cle_nom=lambda x: x["libelle"]) -> dict:
    out: dict = {}
    for k, x in sorted(objets.items(), key=lambda kv: (kv[1].get("rang", 0), kv[0])):
        if cle_nom(x):
            out.setdefault(cle_nom(x), []).append(k)
    return out


def _chemins_de_reference(rubriques: dict) -> dict:
    out = {}
    for rc in rubriques:
        chemin = tuple(rubriques[r]["libelle"]
                       for r in grilles.chemin_de_rubrique(rubriques, rc))
        out.setdefault(chemin, []).append(rc)
    return out


def lire(flux_entrees, flux_listes=None, *, porte_sur=None, reference=None,
         noms=NOMS_PAR_DEFAUT) -> dict:
    """Lit et VALIDE un tableur CSV. Rend `{"contenu", "anomalies", "avertissements",
    "identifiants_deduits"}` — `contenu` est la forme normalisée de `grilles.contenu`, None
    dès qu'une anomalie existe. `porte_sur` : la cellule « Porte sur » de la déclaration ;
    `reference` : le contenu auquel on compare (les identifiants manquants en sont repris) ;
    `noms` : les noms des deux fichiers, pour dire où est une faute."""
    tableur = {"entrees": (noms[0], *grille_tableur.feuille_csv(flux_entrees)),
               "listes": (noms[1], *grille_tableur.feuille_csv(flux_listes))
               if flux_listes is not None else None}
    return lire_tableur(tableur, porte_sur=porte_sur, reference=reference)


def lire_tableur(tableur: dict, *, porte_sur=None, reference=None,
                 ou_porte_sur=None) -> dict:
    """Valide un tableur déjà découpé en feuilles (`lire` pour les CSV,
    `grille_tableur.lire_classeur` pour un classeur) — cf. `lire`."""
    anomalies = [_complete(f) for f in tableur.get("fautes", [])]
    avert = [_complete(f) for f in tableur.get("notes", [])]
    ref = reference or {"cible": None, "rubriques": {}, "entrees": {}, "listes": {}}
    ou_porte_sur = ou_porte_sur or {"fichier": "déclaration"}

    # -- Les listes d'abord : une entrée à qualificatifs nomme la sienne.
    listes: dict = {}
    ids_listes = _Identifiants(ref["listes"], _par_nom(ref["listes"]))
    deduits = []
    if tableur.get("listes") is not None:
        nom_l, entete_l, brutes_l = tableur["listes"]
        lignes_l = _par_colonne(nom_l, entete_l, brutes_l, COLONNES_LISTES, listes=True,
                                obligatoires=("libelle",), anomalies=anomalies)
        _barres_obliques(nom_l, lignes_l, ("liste_cle", "cle"), listes=True,
                         anomalies=anomalies)
        ids_listes.reserver(l["liste_cle"] for _, l in lignes_l)
        nom_vers_cle = {}
        for _, l in lignes_l:
            if l["liste_cle"] and l["liste"]:
                nom_vers_cle.setdefault(l["liste"], l["liste_cle"])
        resolues = []
        for n, l in lignes_l:
            ou = {"fichier": nom_l, "ligne": n, "listes": True}
            lc = l["liste_cle"]
            if not lc:
                if not l["liste"]:
                    anomalies.append(_faute(
                        "qualificatif_sans_liste",
                        f"la case « {l['libelle'] or l['cle']} » n'appartient à aucune liste",
                        "écrivez le nom de sa liste, colonne « Liste »", colonne="liste", **ou))
                    continue
                lc = nom_vers_cle.get(l["liste"])
                if lc is None:
                    lc = nom_vers_cle[l["liste"]] = ids_listes.donner(
                        l["liste"], defaut="liste", quoi="liste", ligne=n, fichier=nom_l)
            if not l["libelle"]:
                anomalies.append(_faute("libelle_vide", "la case n'a pas de nom",
                                        "écrivez ce qu'on coche, colonne « Case »",
                                        cle=l["cle"], colonne="libelle", **ou))
                continue
            resolues.append((n, l, lc))
        ids_q = {}
        for lc in {lc for _, _, lc in resolues}:
            ref_q = (ref["listes"].get(lc) or {}).get("qualificatifs", {})
            ids_q[lc] = _Identifiants(ref_q, _par_nom(ref_q))
            ids_q[lc].reserver(l["cle"] for _, l, x in resolues if x == lc)
        for n, l, lc in resolues:
            ou = {"fichier": nom_l, "ligne": n, "listes": True}
            liste = listes.setdefault(lc, {"libelle": l["liste"], "qualificatifs": {}})
            if l["liste"] and liste["libelle"] and l["liste"] != liste["libelle"]:
                avert.append(_faute(
                    "liste_deux_libelles",
                    f"la liste « {lc} » a deux noms — « {liste['libelle']} » est retenu",
                    "écrivez le même nom sur toutes ses lignes", colonne="liste", **ou))
            liste["libelle"] = liste["libelle"] or l["liste"]
            qc = l["cle"] or ids_q[lc].donner(l["libelle"], defaut="case", quoi="qualificatif",
                                              ligne=n, fichier=nom_l)
            if qc in liste["qualificatifs"]:
                anomalies.append(_faute(
                    "qualificatif_en_double",
                    f"la case « {qc} » est deux fois dans la liste « {liste['libelle'] or lc} »",
                    "gardez une seule ligne pour elle", cle=qc, colonne="libelle", **ou))
                continue
            liste["qualificatifs"][qc] = {"libelle": l["libelle"], "definition": l["definition"],
                                          "rang": len(liste["qualificatifs"])}
        deduits += ids_listes.deduits + [d for x in ids_q.values() for d in x.deduits]

    cible_version, erreur = grilles.lire_cibles(grille_tableur.cibles_lues(porte_sur))
    if erreur:
        anomalies.append(_faute("porte_sur_inconnu", f"« Porte sur » : {erreur}",
                                "écrivez des mots, la case, la planche, ou des sortes de "
                                "zone", colonne="porte_sur", **ou_porte_sur))

    # -- Les entrées.
    nom_e, entete_e, brutes_e = tableur["entrees"]
    lignes = _par_colonne(nom_e, entete_e, brutes_e, COLONNES, listes=False,
                          obligatoires=OBLIGATOIRES, anomalies=anomalies)
    _barres_obliques(nom_e, lignes, ("cle", "rubrique_cle", "variante_cle"), listes=False,
                     anomalies=anomalies)
    est_variante = {n: bool(l["variante_cle"] or l["variante"]) for n, l in lignes}
    ids_e = _Identifiants(ref["entrees"], _par_nom(ref["entrees"]))
    ids_e.reserver(l["cle"] for n, l in lignes if not est_variante[n])
    # Les rubriques : un identifiant écrit vaut pour son chemin partout dans le fichier.
    ids_r = _Identifiants(ref["rubriques"], _chemins_de_reference(ref["rubriques"]))
    chemin_cle: dict = {}
    for _, l in lignes:
        etages, cles_ = _etages(l["rubrique"]), _etages(l["rubrique_cle"])
        if cles_ and len(etages) == len(cles_) and all(etages) and all(cles_):
            ids_r.reserver(cles_)
            for k in range(len(etages)):
                chemin_cle.setdefault(tuple(etages[:k + 1]), cles_[k])

    entrees: dict = {}
    lignes_variantes = []
    rubriques: dict = {}
    par_chemin: dict = {}
    au_dessus = None                       # l'entrée de la dernière ligne d'entrée
    for n, l in lignes:
        ou = {"fichier": nom_e, "ligne": n}
        if est_variante[n]:
            lignes_variantes.append((n, l, l["cle"] or au_dessus, bool(l["cle"])))
            continue
        cle_ = l["cle"]
        if not cle_:
            if not l["libelle"]:
                anomalies.append(_faute("libelle_vide", "l'entrée n'a ni nom ni identifiant",
                                        "écrivez son nom, colonne « Entrée »",
                                        colonne="libelle", **ou))
                au_dessus = False          # ses variantes ne se disent pas une seconde fois
                continue
            cle_ = ids_e.donner(l["libelle"], defaut="entree", quoi="entree", ligne=n,
                                fichier=nom_e)
        au_dessus = cle_
        ou["cle"] = cle_
        if cle_ in entrees:
            anomalies.append(_faute(
                "cle_en_double", f"l'identifiant « {cle_} » est déjà celui d'une autre entrée",
                "donnez-lui un autre identifiant ; une ligne de variante se reconnaît à sa "
                "colonne « Variante »", colonne="cle", **ou))
            continue
        forme = grille_tableur.forme_lue(l["forme"]) or ""
        if forme not in FORMES:
            # Une case VIDE n'est pas une réponse inconnue : « la réponse «  » » se lisait
            # comme une faute de frappe invisible (2026-11-12).
            anomalies.append(_faute(
                "forme_inconnue", _forme_en_faute(l["forme"]),
                "répondez « rien », « une variante » ou « des cases d'une liste » ("
                + " · ".join(FORMES) + ")", colonne="forme", **ou))
        if not l["libelle"]:
            anomalies.append(_faute("libelle_vide", "l'entrée n'a pas de nom",
                                    "écrivez son nom, colonne « Entrée »", colonne="libelle",
                                    **ou))
        # La rubrique : autant d'étages des deux côtés ; un identifiant manquant se déduit.
        etages, cles_ = _etages(l["rubrique"]), _etages(l["rubrique_cle"])
        if etages and not cles_ and all(etages):
            for k in range(len(etages)):
                chemin = tuple(etages[:k + 1])
                if chemin not in chemin_cle:
                    chemin_cle[chemin] = ids_r.donner(chemin, defaut="rubrique",
                                                      quoi="rubrique", ligne=n, fichier=nom_e,
                                                      texte=etages[k])
                    ids_r.deduits[-1]["libelle"] = " > ".join(chemin)
                cles_.append(chemin_cle[chemin])
        rubrique_cle = None
        if etages or cles_:
            if len(etages) != len(cles_) or not all(etages) or not all(cles_):
                anomalies.append(_faute(
                    "rubrique_etages",
                    f"la rubrique et son identifiant n'ont pas les mêmes étages ("
                    f"{len(etages)} et {len(cles_)})",
                    "un identifiant par étage, séparés par « > », ou l'identifiant vide",
                    colonne="rubrique", **ou))
            else:
                parent = None
                for k, (libelle, rc) in enumerate(zip(etages, cles_)):
                    chemin = tuple(etages[:k + 1])
                    deja = rubriques.get(rc)
                    if deja is None:
                        rubriques[rc] = {"libelle": libelle, "parent_cle": parent,
                                         "rang": len(rubriques)}
                    elif deja["libelle"] != libelle:
                        anomalies.append(_faute(
                            "rubrique_deux_libelles",
                            f"la rubrique « {rc} » a deux noms — « {deja['libelle']} » et "
                            f"« {libelle} »", "écrivez-la partout de la même façon",
                            colonne="rubrique", **ou))
                    elif deja["parent_cle"] != parent:
                        anomalies.append(_faute(
                            "rubrique_deux_parents",
                            f"la rubrique « {rc} » est rangée sous deux rubriques — "
                            f"« {deja['parent_cle']} » et « {parent} »",
                            "écrivez son chemin partout de la même façon", colonne="rubrique",
                            **ou))
                    autre = par_chemin.setdefault(chemin, rc)
                    if autre != rc:
                        anomalies.append(_faute(
                            "rubrique_deux_identifiants",
                            f"la rubrique « {' > '.join(chemin)} » a deux identifiants — "
                            f"« {autre} » et « {rc} »", "gardez-en un seul",
                            colonne="rubrique_cle", **ou))
                    parent = rc
                rubrique_cle = cles_[-1]
        liste = l["liste"]
        if liste and liste not in listes:
            memes = [lc for lc, x in listes.items() if x["libelle"] == liste]
            liste = memes[0] if len(memes) == 1 else liste
        if forme == "qualificatifs":
            if not liste:
                anomalies.append(_faute(
                    "liste_manque", "l'entrée se pose avec des cases d'une liste, et aucune "
                    "liste n'est nommée", "écrivez le nom d'une liste, colonne « Liste à "
                    "cocher »", colonne="liste", **ou))
            elif liste not in listes:
                anomalies.append(_faute(
                    "liste_inconnue", f"la liste « {liste} » n'existe pas dans les listes à "
                    "cocher", "ajoutez-la, ou recopiez son nom à l'identique",
                    colonne="liste", **ou))
        elif liste:
            anomalies.append(_faute(
                "liste_hors_qualificatifs",
                f"une liste est nommée (« {l['liste']} »), mais l'entrée ne se pose pas avec "
                "des cases d'une liste", "répondez « des cases d'une liste » à la question 4, "
                "ou videz la colonne « Liste à cocher »", colonne="liste", **ou))
        lien = grille_tableur.norme(l["lien"])
        if lien not in ("", "oui", "non"):
            anomalies.append(_faute(
                "lien_inconnu", f"la réponse « {l['lien']} » n'est ni oui ni non",
                "répondez « oui » (l'annotateur désigne une autre zone) ou laissez vide",
                colonne="lien", **ou))
        cible, erreur = grilles.lire_cibles(grille_tableur.cibles_lues(l["cible"]))
        if erreur:
            anomalies.append(_faute(
                "cible_inconnue", erreur, "laissez vide (comme la grille), ou écrivez des "
                "mots, la case, la planche, ou des sortes de zone", colonne="cible", **ou))
        elif not cible and not cible_version:
            # Sans défaut, chaque entrée dit la sienne (Hugo, 2026-11-12) : un fichier est
            # entier, la faute s'y corrige là où elle est.
            anomalies.append(_faute(
                "cible_manque", "l'entrée ne dit pas où elle se pose, et la grille ne pose "
                "rien par défaut", "répondez à sa question 2, ou donnez à la grille une "
                "réponse par défaut (feuille « 1. La grille »)", colonne="cible", **ou))
        cardinalite = grille_tableur.cardinalite_lue(l["cardinalite"]) or None
        if cardinalite is not None and cardinalite not in CARDINALITES:
            anomalies.append(_faute(
                "cardinalite_inconnue", f"la réponse « {l['cardinalite']} » n'est pas un "
                "nombre de fois", "répondez « une seule », « plusieurs », ou laissez vide",
                colonne="cardinalite", **ou))
        effectives = cible or cible_version
        if grilles.CIBLE_ENTITE in effectives:
            avert.append(_faute(
                "vise_l_entite", "l'entrée vise l'entité du registre : elle s'importe, mais "
                "aucun relevé ne s'y pose avant l'étage de projet des personnages (G3)",
                colonne="cible", **ou))
        entrees[cle_] = {
            "rubrique_cle": rubrique_cle, "rang": len(entrees), "forme": forme,
            "libelle": l["libelle"], "definition": l["definition"],
            "structure": l["structure"], "piege": l["piege"], "precision": l["precision"],
            "lien": lien == "oui", "cible": grilles.ecrire_cibles(cible),
            "cardinalite": cardinalite, "liste_cle": liste if forme == "qualificatifs" else None,
            "retiree": False, "exemples": _exemples(l["exemples"]), "variantes": {},
            "_ligne": l}

    # -- Les variantes : à l'entrée qu'elles nomment, ou à celle du dessus.
    ids_v = {}
    for k in entrees:
        ref_v = (ref["entrees"].get(k) or {}).get("variantes", {})
        ids_v[k] = _Identifiants(ref_v, _par_nom(ref_v))
        ids_v[k].reserver(l["variante_cle"] for _, l, c, _e in lignes_variantes if c == k)
    for n, l, cle_, explicite in lignes_variantes:
        ou = {"fichier": nom_e, "ligne": n, "cle": cle_ or None}
        nom_v = l["variante"] or l["variante_cle"]
        if cle_ is False:                       # sous une entrée sans nom, déjà dite
            continue
        if cle_ is None:
            anomalies.append(_faute(
                "variante_sans_entree", f"la variante « {nom_v} » est écrite avant toute "
                "entrée", "écrivez-la juste sous l'entrée à laquelle elle appartient",
                colonne="variante", **ou))
            continue
        e = entrees.get(cle_)
        if e is None:
            if explicite:
                anomalies.append(_faute(
                    "variante_entree_inconnue",
                    f"la variante « {nom_v} » nomme l'entrée « {cle_} », qu'aucune ligne ne "
                    "déclare", "écrivez l'entrée, ou corrigez l'identifiant de la ligne",
                    colonne="cle", **ou))
            continue
        if not l["variante"]:
            anomalies.append(_faute(
                "variante_sans_nom", f"la variante « {nom_v} » n'a pas de nom",
                "écrivez son nom, colonne « Variante »", colonne="variante", **ou))
            continue
        if e["forme"] != "variantes":
            anomalies.append(_faute(
                "variante_sous_autre_forme",
                f"une variante, « {nom_v} », est écrite sous « {e['libelle'] or cle_} », qui "
                "ne se pose pas avec une variante",
                f"répondez « une variante » à la question 4 pour « {e['libelle'] or cle_} », "
                "ou retirez la ligne", colonne="variante", **ou))
            continue
        for c in COLONNES_DE_L_ENTREE:
            if l[c] is not None and l[c] != e["_ligne"][c]:
                anomalies.append(_faute(
                    "variante_remplit_l_entree",
                    f"la ligne de la variante « {nom_v} » remplit la colonne de l'entrée "
                    "autrement qu'elle", "laissez cette colonne vide sur la ligne de variante",
                    colonne=c, **ou))
                break
        vc = l["variante_cle"] or ids_v[cle_].donner(l["variante"], defaut="variante",
                                                     quoi="variante", ligne=n, fichier=nom_e)
        if vc in e["variantes"]:
            anomalies.append(_faute(
                "variante_en_double", f"la variante « {vc} » est deux fois sous l'entrée",
                "gardez une seule ligne pour elle", colonne="variante", **ou))
            continue
        e["variantes"][vc] = {
            "libelle": l["variante"], "definition": l["definition"],
            "structure": l["structure"], "piege": l["piege"], "rang": len(e["variantes"]),
            "exemples": _exemples(l["exemples"])}
    deduits += ids_e.deduits + ids_r.deduits + [d for x in ids_v.values() for d in x.deduits]

    for cle_, e in entrees.items():
        if e["forme"] == "variantes" and not e["variantes"]:
            anomalies.append(_faute(
                "variantes_absentes", "l'entrée se pose avec une variante, et aucune ligne de "
                "variante n'est écrite pour elle", "écrivez chaque variante sur sa ligne, juste "
                "sous l'entrée, colonne « Variante » ; ou répondez « rien » à la question 4",
                fichier=nom_e, cle=cle_, colonne="forme"))
        e.pop("_ligne", None)
    # Un parent circulaire (« a > b » puis « b > a » a déjà deux parents ; reste le cas d'une
    # rubrique qui serait son propre ancêtre par un autre chemin).
    for rc in rubriques:
        vus, x = set(), rc
        while x is not None and x in rubriques:
            if x in vus:
                anomalies.append(_faute(
                    "rubrique_circulaire", f"la rubrique « {rc} » est son propre ancêtre",
                    "vérifiez les chemins de rubrique", fichier=nom_e, colonne="rubrique"))
                break
            vus.add(x)
            x = rubriques[x]["parent_cle"]
    utilisees = {e["liste_cle"] for e in entrees.values() if e["liste_cle"]}
    for lc in listes:
        if lc not in utilisees:
            avert.append(_faute("liste_inutilisee",
                                f"la liste « {listes[lc]['libelle'] or lc} » n'est nommée par "
                                "aucune entrée", fichier=(tableur.get("listes") or ("",))[0],
                                colonne="liste", listes=True))
    if not entrees and not anomalies:
        anomalies.append(_faute("aucune_entree", "le tableur ne porte aucune entrée",
                                "écrivez au moins une entrée", fichier=nom_e))
    if deduits:
        par_quoi = {}
        for d in deduits:
            par_quoi[d["quoi"]] = par_quoi.get(d["quoi"], 0) + 1
        avert.append(_faute(
            "identifiants_deduits",
            "des identifiants manquaient : ils sont pris du nom (" + ", ".join(
                f"{n} {q}" for q, n in sorted(par_quoi.items())) + ")",
            "réexportez la grille après l'import : le classeur portera ses identifiants"))
    resultat = {"anomalies": anomalies, "avertissements": avert,
                "identifiants_deduits": deduits}
    if anomalies:
        return {"contenu": None, **resultat}
    return {"contenu": {"cible": grilles.ecrire_cibles(cible_version), "rubriques": rubriques,
                        "entrees": entrees, "listes": listes}, **resultat}


# --------------------------------------------------------------------------- #
# La déclaration : les arguments, ou la feuille « 1. La grille »
# --------------------------------------------------------------------------- #
def declarer(tableur: dict, *, nom=None, ouverte=None, porte_sur=None, note=None,
             grille=None) -> tuple[dict, list, list]:
    """Ce que l'import déclare — `nom`, `ouverte`, `porte_sur`, `note` —, des ARGUMENTS
    (l'outil, le formulaire) et de la feuille « 1. La grille » quand le classeur la porte.
    La feuille remplit ce que les arguments laissent vide ; un argument DONNÉ l'emporte sur
    elle — on réimporte le classeur d'une grille sous un autre nom pour la dériver —, et le
    bilan le dit (« À savoir ») : rien ne change en silence. `grille` : la grille existante
    d'une version suivante — son nom et sa nature ne changent pas par l'import, et une
    feuille qui dit une autre NATURE est une anomalie. Rend (déclaration, anomalies,
    avertissements) ; la déclaration dit ce qui vient de la feuille (`lus`)."""
    feuille = tableur.get("grille") or {}
    nom_feuille = tableur.get("nom_grille") or grille_tableur.FEUILLE_GRILLE
    anomalies, avert = [], []
    if grille is not None:              # sa nature est la sienne : l'argument ne la change pas
        ouverte = bool(grille["ouverte"])
    decl = {"nom": propre(nom), "ouverte": ouverte, "porte_sur": propre(porte_sur),
            "note": propre(note), "lus": [], "ou": {}}

    def lu(champ):
        valeur, ligne = feuille.get(champ, (None, None))
        return propre(valeur), {"fichier": nom_feuille, "ligne": ligne}

    for champ in ("nom", "porte_sur", "note"):
        valeur, ou = lu(champ)
        if valeur is None:
            continue
        decl["ou"][champ] = ou
        if champ == "porte_sur":
            comparable = grilles.lire_cibles(grille_tableur.cibles_lues(valeur))[0]
            donne = grilles.lire_cibles(grille_tableur.cibles_lues(decl[champ]))[0] \
                if decl[champ] else None
            differe = donne is not None and comparable != donne
        else:
            differe = decl[champ] is not None and decl[champ] != valeur
        if grille is not None and champ == "nom":
            if valeur != grille["nom"]:
                avert.append(_faute(
                    "nom_de_la_feuille", f"le classeur nomme la grille « {valeur} », elle "
                    f"s'appelle « {grille['nom']} » : son nom ne change pas par l'import",
                    colonne="nom", **ou))
            continue
        if differe:
            avert.append(_faute(
                "declaration_remplacee", f"la feuille dit « {valeur} », l'import déclare "
                f"« {decl[champ]} » : la déclaration de l'import est retenue",
                colonne=champ, **ou))
            continue
        if decl[champ] is None:
            decl[champ] = valeur
            decl["lus"].append(champ)
    valeur, ou = lu("ouverte")
    if valeur is not None:
        decl["ou"]["ouverte"] = ou
        lue = grille_tableur.ouverte_lue(valeur)
        attendue = bool(grille["ouverte"]) if grille is not None else ouverte
        if not isinstance(lue, bool):
            anomalies.append(_faute(
                "nature_inconnue", f"la réponse « {valeur} » n'est ni « fermée » ni "
                "« ouverte »", "répondez « fermée » ou « ouverte »", colonne="ouverte", **ou))
        elif grille is not None and lue != attendue:
            anomalies.append(_faute(
                "nature_contredite", f"la feuille dit « {valeur} », la grille est "
                f"« {grille_tableur.OUVERTE_MOTS[attendue]} »",
                "une grille ne change pas de nature : accordez la feuille, ou importez-la "
                "comme une grille neuve", colonne="ouverte", **ou))
        elif attendue is not None and lue != attendue:
            avert.append(_faute(
                "declaration_remplacee", f"la feuille dit « {valeur} », l'import déclare "
                f"« {grille_tableur.OUVERTE_MOTS[attendue]} » : la déclaration de l'import "
                "est retenue", colonne="ouverte", **ou))
        elif decl["ouverte"] is None:
            decl["ouverte"] = lue
            decl["lus"].append("ouverte")
    if decl["ouverte"] is None:
        decl["ouverte"] = bool(grille["ouverte"]) if grille is not None else False
    return decl, anomalies, avert


def origine_en_mots(origine: dict | None) -> str:
    """« dérivée de « Signaux », v2 » ; sans nom ni version, ce qui en reste. Le pendant de
    `BDGrillesProjet.origineEnMots`, pour l'outil."""
    if not origine:
        return ""
    texte = (f"dérivée de « {origine['nom']} »" if origine.get("nom")
             else "dérivée d'une autre grille")
    return texte + (f", v{origine['version']}" if origine.get("version") else "")


def origine_du_classeur(conn: sqlite3.Connection, tableur: dict, *,
                        grille=None) -> tuple[dict | None, list]:
    """D'où vient le classeur (v40, ANN-7, « Une grille dérivée dit d'où elle vient », Hugo,
    2026-11-15) : la grille dont il a été tiré, telle que les dernières lignes de sa feuille
    « 1. La grille » la disent (`grille_tableur.CHAMPS_ORIGINE`) — son identifiant, son nom,
    la version tirée. Rend (`{identifiant, nom, version}` | None, avertissements).

    - Deux CSV, ou un classeur sans ces lignes (rempli à la main) : rien, sans rien dire.
    - Un identifiant qui ne se lit pas : rien, et « À savoir » le dit.
    - `grille`, la grille d'une version SUIVANTE : rien ne s'écrit — l'origine d'une grille
      s'écrit à sa naissance et ne change plus. Le classeur tiré d'elle-même se tait ; tiré
      d'une AUTRE, « À savoir » le dit.
    - Une grille neuve : l'origine, de cette instance ou d'une autre. Le nom manquant se lit
      sur la grille de l'instance qui porte cet identifiant, s'il y en a une."""
    feuille = tableur.get("grille") or {}
    ou = {"fichier": tableur.get("nom_grille") or grille_tableur.FEUILLE_GRILLE}

    def lu(champ):
        valeur, ligne = feuille.get(champ, (None, None))
        return propre(valeur), {**ou, "ligne": ligne}

    brut, ou_id = lu("origine_identifiant")
    if brut is None:
        return None, []
    identifiant = grilles.identifiant_lu(brut)
    if identifiant is None:
        return None, [_faute("origine_illisible",
                             f"l'identifiant de la grille d'origine (« {brut} ») ne se lit "
                             "pas : la grille ne dira pas d'où elle vient",
                             colonne="origine_identifiant", **ou_id)]
    nom, _ = lu("origine_nom")
    texte, ou_v = lu("origine_version")
    notes = []
    version = None
    if texte is not None:
        chiffres = texte.lower().removeprefix("v").strip()
        version = int(chiffres) if chiffres.isdigit() and int(chiffres) > 0 else None
        if version is None:
            notes.append(_faute("origine_version_illisible",
                                f"la version tirée (« {texte} ») ne se lit pas : la grille "
                                "dira d'où elle vient, sans sa version",
                                colonne="origine_version", **ou_v))
    if grille is not None:
        if identifiant != grille["identifiant"]:
            source = f"« {nom} »" if nom else "une autre grille"
            notes.append(_faute(
                "origine_ignoree",
                f"le classeur a été tiré de {source} : l'origine d'une grille s'écrit à "
                f"sa naissance, celle de « {grille['nom']} » ne change pas",
                colonne="origine_identifiant", **ou_id))
        return None, notes
    if nom is None:
        source = conn.execute("SELECT nom FROM grille WHERE identifiant = ?",
                              (identifiant,)).fetchone()
        nom = source["nom"] if source is not None else None
    return {"identifiant": identifiant, "nom": nom, "version": version}, notes


# --------------------------------------------------------------------------- #
# Le bilan
# --------------------------------------------------------------------------- #
_CHAMPS_RETOUCHES = ("definition", "structure", "piege", "exemples")
_CHAMPS_CHANGES = ("forme", "cible", "cardinalite", "liste_cle", "precision", "lien")


def _releves_sur(conn, grille_id, entree_cle, variante_cle=None) -> int:
    if grille_id is None:
        return 0
    if variante_cle is None:
        return conn.execute("SELECT COUNT(*) FROM releve WHERE grille_id = ? "
                            "AND entree_cle = ?", (grille_id, entree_cle)).fetchone()[0]
    return conn.execute("SELECT COUNT(*) FROM releve WHERE grille_id = ? AND entree_cle = ? "
                        "AND variante_cle = ?", (grille_id, entree_cle,
                                                 variante_cle)).fetchone()[0]


def _releves_sur_qualificatif(conn, grille_id, qualificatif_cle) -> int:
    if grille_id is None:
        return 0
    return conn.execute(
        "SELECT COUNT(*) FROM releve_qualificatif rq JOIN releve r ON r.id = rq.releve_id "
        "WHERE r.grille_id = ? AND rq.qualificatif_cle = ?",
        (grille_id, qualificatif_cle)).fetchone()[0]


def bilan(conn: sqlite3.Connection, grille_id, avant: dict | None, apres: dict) -> dict:
    """Ce qui change de `avant` (le contenu d'une version, ou None) à `apres`, par `cle` —
    « Ce qui change ». Les disparus comptent les relevés posés sur eux (`grille_id` : la
    grille d'`avant`). Une entrée RETIRÉE qu'on garde retirée n'est pas un disparu."""
    b = {"nes": [], "renommes": [], "retouches": [], "deplaces": [], "changes": [],
         "disparus": []}
    avant = avant or {"cible": None, "rubriques": {}, "entrees": {}, "listes": {}}
    if avant["cible"] != apres["cible"]:
        b["changes"].append({"quoi": "version", "cle": None, "champ": "porte_sur",
                             "avant": avant["cible"], "apres": apres["cible"]})
    for quoi, cle_a, cle_b in (("rubrique", avant["rubriques"], apres["rubriques"]),):
        for cle_ in cle_b.keys() - cle_a.keys():
            b["nes"].append({"quoi": quoi, "cle": cle_, "libelle": cle_b[cle_]["libelle"]})
        for cle_ in cle_a.keys() - cle_b.keys():
            b["disparus"].append({"quoi": quoi, "cle": cle_, "libelle": cle_a[cle_]["libelle"],
                                  "releves": 0})
        for cle_ in cle_a.keys() & cle_b.keys():
            if cle_a[cle_]["libelle"] != cle_b[cle_]["libelle"]:
                b["renommes"].append({"quoi": quoi, "cle": cle_, "avant": cle_a[cle_]["libelle"],
                                      "apres": cle_b[cle_]["libelle"]})
            if cle_a[cle_]["parent_cle"] != cle_b[cle_]["parent_cle"]:
                b["deplaces"].append({"quoi": quoi, "cle": cle_,
                                      "avant": cle_a[cle_]["parent_cle"],
                                      "apres": cle_b[cle_]["parent_cle"]})
    ea, eb = avant["entrees"], apres["entrees"]
    for cle_ in sorted(eb.keys() - ea.keys(), key=lambda k: eb[k]["rang"]):
        b["nes"].append({"quoi": "entree", "cle": cle_, "libelle": eb[cle_]["libelle"]})
    for cle_ in sorted(ea.keys() - eb.keys()):
        b["disparus"].append({"quoi": "entree", "cle": cle_, "libelle": ea[cle_]["libelle"],
                              "releves": _releves_sur(conn, grille_id, cle_)})
    for cle_ in sorted(ea.keys() & eb.keys(), key=lambda k: eb[k]["rang"]):
        a, n = ea[cle_], eb[cle_]
        if n.get("retiree") and not a.get("retiree"):
            b["changes"].append({"quoi": "entree", "cle": cle_, "champ": "retiree",
                                 "avant": False, "apres": True})
        if a["libelle"] != n["libelle"]:
            b["renommes"].append({"quoi": "entree", "cle": cle_, "avant": a["libelle"],
                                  "apres": n["libelle"]})
        retouches = [c for c in _CHAMPS_RETOUCHES if a.get(c) != n.get(c)]
        if retouches:
            b["retouches"].append({"quoi": "entree", "cle": cle_, "champs": retouches})
        if a["rubrique_cle"] != n["rubrique_cle"]:
            b["deplaces"].append({"quoi": "entree", "cle": cle_, "avant": a["rubrique_cle"],
                                  "apres": n["rubrique_cle"]})
        for c in _CHAMPS_CHANGES:
            if a.get(c) != n.get(c):
                b["changes"].append({"quoi": "entree", "cle": cle_, "champ": c,
                                     "avant": a.get(c), "apres": n.get(c)})
        va, vb = a["variantes"], n["variantes"]
        for vc in vb.keys() - va.keys():
            b["nes"].append({"quoi": "variante", "cle": f"{cle_}/{vc}",
                             "libelle": vb[vc]["libelle"]})
        for vc in sorted(va.keys() - vb.keys()):
            b["disparus"].append({"quoi": "variante", "cle": f"{cle_}/{vc}",
                                  "libelle": va[vc]["libelle"],
                                  "releves": _releves_sur(conn, grille_id, cle_, vc)})
        for vc in va.keys() & vb.keys():
            if va[vc]["libelle"] != vb[vc]["libelle"]:
                b["renommes"].append({"quoi": "variante", "cle": f"{cle_}/{vc}",
                                      "avant": va[vc]["libelle"], "apres": vb[vc]["libelle"]})
            retouches = [c for c in _CHAMPS_RETOUCHES if va[vc].get(c) != vb[vc].get(c)]
            if retouches:
                b["retouches"].append({"quoi": "variante", "cle": f"{cle_}/{vc}",
                                       "champs": retouches})
    la, lb = avant["listes"], apres["listes"]
    for lc in lb.keys() - la.keys():
        b["nes"].append({"quoi": "liste", "cle": lc, "libelle": lb[lc]["libelle"]})
    for lc in la.keys() - lb.keys():
        b["disparus"].append({"quoi": "liste", "cle": lc, "libelle": la[lc]["libelle"],
                              "releves": 0})
    for lc in la.keys() & lb.keys():
        qa, qb = la[lc]["qualificatifs"], lb[lc]["qualificatifs"]
        for qc in qb.keys() - qa.keys():
            b["nes"].append({"quoi": "qualificatif", "cle": f"{lc}/{qc}",
                             "libelle": qb[qc]["libelle"]})
        for qc in qa.keys() - qb.keys():
            b["disparus"].append({"quoi": "qualificatif", "cle": f"{lc}/{qc}",
                                  "libelle": qa[qc]["libelle"],
                                  "releves": _releves_sur_qualificatif(conn, grille_id, qc)})
        for qc in qa.keys() & qb.keys():
            if qa[qc]["libelle"] != qb[qc]["libelle"]:
                b["renommes"].append({"quoi": "qualificatif", "cle": f"{lc}/{qc}",
                                      "avant": qa[qc]["libelle"], "apres": qb[qc]["libelle"]})
            if qa[qc].get("definition") != qb[qc].get("definition"):
                b["retouches"].append({"quoi": "qualificatif", "cle": f"{lc}/{qc}",
                                       "champs": ["definition"]})
    b["releves_touches"] = sum(d["releves"] for d in b["disparus"])
    return b


def va_naitre(avant: dict | None, apres: dict) -> dict:
    """« Ce qui va naître » : combien de rubriques, d'entrées, de variantes, de listes et de
    qualificatifs l'import fait naître."""
    avant = avant or {"rubriques": {}, "entrees": {}, "listes": {}}
    ea, eb = avant["entrees"], apres["entrees"]
    la, lb = avant["listes"], apres["listes"]
    variantes = sum(len(eb[k]["variantes"]) for k in eb.keys() - ea.keys()) + sum(
        len(eb[k]["variantes"].keys() - ea[k]["variantes"].keys()) for k in eb.keys() & ea.keys())
    qualificatifs = sum(len(lb[k]["qualificatifs"]) for k in lb.keys() - la.keys()) + sum(
        len(lb[k]["qualificatifs"].keys() - la[k]["qualificatifs"].keys())
        for k in lb.keys() & la.keys())
    return {"rubriques": len(apres["rubriques"].keys() - avant["rubriques"].keys()),
            "entrees": len(eb.keys() - ea.keys()), "variantes": variantes,
            "listes": len(lb.keys() - la.keys()), "qualificatifs": qualificatifs}


def verdict(etat: str, **compte) -> dict:
    """Le VERDICT en tête du bilan : un état stable (`refuse`, `a_repondre`,
    `aucun_changement`, `importable`, `importe`) et sa phrase."""
    n = compte.get("n", 0)
    phrases = {
        "refuse": f"{n} faute{'s' if n > 1 else ''} à corriger : rien n'est importé tant "
                  "qu'il en reste une.",
        "a_repondre": f"Le fichier est juste. {n} entrée{'s' if n > 1 else ''} employée"
                      f"{'s' if n > 1 else ''} disparai{'ssent' if n > 1 else 't'} : "
                      "dites pour chacune « retirer » ou « fusionner dans… » avant "
                      "d'importer.",
        "aucun_changement": "Le fichier est juste, et la version en place porte déjà ce "
                            "contenu : rien n'est écrit.",
        "importable": "Le fichier est juste : l'import peut se faire.",
        "importe": "Le fichier est juste, et la grille est importée.",
    }
    return {"etat": etat, **compte, "phrase": phrases[etat]}


# --------------------------------------------------------------------------- #
# Réimporter une grille OUVERTE : ce qui disparaît (tranché par Hugo le 2026-11-03)
# --------------------------------------------------------------------------- #
def lire_reponses(reponses) -> dict:
    """Les réponses aux entrées employées qui disparaissent : `{cle: "retirer"}` ou
    `{cle: "fusionner:<cle d'arrivée>"}` (ou `{"fusionner": cle}`). Lève `Refus` (422) sur
    une réponse qui n'est ni l'une ni l'autre."""
    sortie = {}
    for cle_, r in (reponses or {}).items():
        if isinstance(r, dict) and set(r) == {FUSIONNER}:
            sortie[cle_] = (FUSIONNER, str(r[FUSIONNER]))
        elif isinstance(r, str) and r == RETIRER:
            sortie[cle_] = (RETIRER, None)
        elif isinstance(r, str) and r.startswith(FUSIONNER + ":") and r[len(FUSIONNER) + 1:]:
            sortie[cle_] = (FUSIONNER, r[len(FUSIONNER) + 1:])
        else:
            raise Refus(422, f"La réponse pour « {cle_} » n'est ni « retirer » ni "
                             "« fusionner:<identifiant> ».")
    return sortie


def _vers_possibles(avant: dict, apres: dict, cle_: str, employees: set) -> list:
    """Les entrées où les relevés de `cle_` peuvent être FUSIONNÉS sans rien perdre : du
    fichier, non retirées, de la même forme, posées de la même manière, à la même liste —
    et, pour une entrée à variantes, qui portent toutes les variantes employées."""
    e = avant["entrees"][cle_]
    vers = []
    for k, x in sorted(apres["entrees"].items(), key=lambda kv: kv[1]["rang"]):
        if k == cle_ or x.get("retiree"):
            continue
        if x["forme"] != e["forme"] or x.get("liste_cle") != e.get("liste_cle"):
            continue
        cibles_e = grilles.cibles_de(e["cible"]) or grilles.cibles_de(avant["cible"])
        cibles_x = grilles.cibles_de(x["cible"]) or grilles.cibles_de(apres["cible"])
        if grilles.sorte_de_pose(cibles_e) != grilles.sorte_de_pose(cibles_x):
            continue
        if e["forme"] == "variantes" and not employees <= set(x["variantes"]):
            continue
        vers.append(k)
    return vers


def reconcilier_ouverte(conn, grille_id: int, version_id: int, avant: dict, apres: dict,
                        reponses: dict) -> tuple[dict, list, list, list]:
    """Le contenu à ÉCRIRE pour une grille ouverte qu'on réimporte, et ce qui attend.

    - une entrée déjà RETIRÉE que le fichier ne porte pas reste retirée, sans question ;
    - une entrée que personne n'emploie et que le fichier ne porte pas part ;
    - une entrée EMPLOYÉE que le fichier ne porte pas ne se supprime jamais : on la RETIRE
      (elle reste dans la version, ne se pose plus, et ses relevés passent « à revoir ») ou
      on FUSIONNE ses relevés dans une autre entrée. Sans réponse, elle est « à répondre ».

    Rend (contenu, à répondre, fusions, fautes). Les fautes refusent l'import : une réponse
    qui ne vaut pas (une fusion impossible), une variante ou une case employée qui
    disparaîtrait, la forme ou la liste d'une entrée employée qui changerait sous ses
    relevés — la version est VIVANTE, ses relevés la lisent telle qu'elle sera."""
    apres = copy.deepcopy(apres)
    a_repondre, fusions, fautes = [], [], []
    rang = max([e["rang"] for e in apres["entrees"].values()] + [-1])

    def garder(cle_, retiree):
        nonlocal rang
        rang += 1
        apres["entrees"][cle_] = {**copy.deepcopy(avant["entrees"][cle_]), "rang": rang,
                                  "retiree": retiree}
        lc = apres["entrees"][cle_].get("liste_cle")
        if lc and lc not in apres["listes"] and lc in avant["listes"]:
            apres["listes"][lc] = copy.deepcopy(avant["listes"][lc])

    employees_v = {}
    for r in conn.execute("SELECT entree_cle, variante_cle, COUNT(*) AS n FROM releve "
                          "WHERE grille_id = ? AND version_id = ? GROUP BY entree_cle, "
                          "variante_cle", (grille_id, version_id)):
        employees_v.setdefault(r["entree_cle"], {})[r["variante_cle"]] = r["n"]
    for cle_ in sorted(avant["entrees"].keys() - apres["entrees"].keys(),
                       key=lambda k: avant["entrees"][k]["rang"]):
        e = avant["entrees"][cle_]
        n = sum(employees_v.get(cle_, {}).values())
        if e.get("retiree"):
            garder(cle_, True)
            continue
        if n == 0:
            continue
        vers = _vers_possibles(avant, apres, cle_, {v for v in employees_v.get(cle_, {})
                                                    if v is not None})
        reponse = reponses.get(cle_)
        if reponse is None:
            a_repondre.append({"cle": cle_, "libelle": e["libelle"], "releves": n,
                               "choix": [RETIRER, FUSIONNER], "fusionner_dans": vers})
        elif reponse[0] == RETIRER:
            garder(cle_, True)
        elif reponse[1] not in vers:
            fautes.append(_faute(
                "fusion_impossible", f"les relevés de « {e['libelle']} » ne peuvent pas être "
                f"fusionnés dans « {reponse[1]} »",
                "fusionnez dans une entrée du fichier de même forme, posée de la même façon "
                "(et qui porte ses variantes) : " + (", ".join(vers) or "aucune ici")
                + " ; ou retirez-la", cle=cle_))
        else:
            # `une` : la cardinalité EFFECTIVE de l'entrée d'arrivée, telle que la version
            # l'écrira — ses relevés reportés la prennent (`_fusionner`).
            une = _cardinalite_de(apres["entrees"][reponse[1]], apres) == "une"
            if _fusion_en_double(conn, grille_id, version_id, cle_, reponse[1], une=une):
                fautes.append(_faute(
                    "fusion_en_double", f"fusionner « {e['libelle']} » dans « {reponse[1]} » "
                    "poserait deux fois, sur une même cible, une entrée qui ne s'y pose qu'une "
                    "fois — ou la même valeur deux fois",
                    "retirez-la plutôt, ou retirez d'abord les relevés en trop", cle=cle_))
            else:
                fusions.append({"de": cle_, "dans": reponse[1], "releves": n, "une": une})
    # Ce qui change SOUS des relevés posés, dans une version vivante.
    for cle_, x in apres["entrees"].items():
        e = avant["entrees"].get(cle_)
        employes = employees_v.get(cle_, {})
        if e is None or not employes or x.get("retiree"):
            continue
        for champ in ("forme", "liste_cle"):
            if e.get(champ) != x.get(champ):
                fautes.append(_faute(
                    "change_sous_des_releves",
                    f"« {e['libelle']} » change de {'forme' if champ == 'forme' else 'liste'} "
                    f"alors que {sum(employes.values())} relevé(s) la portent",
                    "gardez sa forme et sa liste ; pour changer, écrivez une autre entrée "
                    "et fusionnez-y celle-ci", cle=cle_,
                    colonne="forme" if champ == "forme" else "liste"))
        if (_cardinalite_de(x, apres) == "une" and _cardinalite_de(e, avant) != "une"):
            # J3 (« se tranchent en route », le plus prudent) : passer à « une seule fois »
            # une entrée dont deux relevés vivent sur une même cible les ferait se contredire
            # — la règle de `_fusion_en_double`. Sans contradiction, ses relevés suivent
            # (`reporter_cardinalites`).
            n = _cibles_en_double(conn, grille_id, version_id, cle_)
            if n:
                fautes.append(_faute(
                    "cardinalite_contredite",
                    f"« {e['libelle']} » passerait à « une seule fois » alors que {n} cible(s) "
                    "en portent déjà plusieurs relevés",
                    "retirez d'abord les relevés en trop, ou gardez « plusieurs »", cle=cle_,
                    colonne="cardinalite"))
        for vc, n in employes.items():
            if vc is not None and vc not in x["variantes"]:
                fautes.append(_faute(
                    "variante_employee_disparait",
                    f"la variante « {e['variantes'].get(vc, {}).get('libelle', vc)} » de "
                    f"« {e['libelle']} » disparaît alors que {n} relevé(s) la portent",
                    "gardez sa ligne", cle=cle_, colonne="variante"))
    for lc, liste in avant["listes"].items():
        for qc, q in liste["qualificatifs"].items():
            if qc in (apres["listes"].get(lc) or {}).get("qualificatifs", {}):
                continue
            n = _releves_sur_qualificatif(conn, grille_id, qc)
            if n:
                fautes.append(_faute(
                    "case_employee_disparait",
                    f"la case « {q['libelle']} » de la liste « {liste['libelle'] or lc} » "
                    f"disparaît alors que {n} relevé(s) la cochent", "gardez sa ligne",
                    fichier=NOMS_PAR_DEFAUT[1], colonne="libelle", listes=True))
    for cle_ in reponses.keys() - {a["cle"] for a in a_repondre} - {
            f["de"] for f in fusions} - {k for k, x in apres["entrees"].items()
                                         if x.get("retiree")}:
        if cle_ in apres["entrees"] or cle_ not in avant["entrees"]:
            fautes.append(_faute(
                "reponse_sans_objet", f"une réponse est donnée pour « {cle_} », qui ne "
                "disparaît pas", "retirez cette réponse", cle=cle_))
    return apres, a_repondre, fusions, fautes


def reconcilier_fermee(conn, grille_id: int, avants, apres: dict,
                       reponses: dict) -> tuple[dict, list, list]:
    """Une ENTRÉE employée qui disparaît ENTIÈRE du réimport d'une grille FERMÉE attend sa
    réponse, comme sur une ouverte (`reconcilier_ouverte`) — la règle du formulaire, où une
    entrée employée ne se supprime jamais. La seule réponse est « retirer » : elle reste dans
    le brouillon, retirée, et ses relevés se relisent dans leur version publiée ;
    « fusionner dans… » est refusé sur une fermée (choix 1 des routes d'écriture, le
    2026-11-04) : on fusionne À LA MONTÉE DE VERSION (`montee`, M2), qui demande, pour chaque
    entrée retirée, « laisser » ou « fusionner dans… ».

    Recommandation de la session de pilotage, à confirmer par Hugo. `avants` : les contenus
    que le fichier remplace (la dernière version publiée, le brouillon en place, le plus
    récent en dernier). Une entrée retirée que le fichier ne porte pas reste retirée, sans
    question ; une entrée que personne n'emploie part. Rend (contenu, à répondre, fautes)."""
    apres = copy.deepcopy(apres)
    avants = [a for a in avants if a]
    a_repondre, fautes = [], []
    rang = max([e["rang"] for e in apres["entrees"].values()] + [-1])
    connues = {}
    for a in avants:                      # le plus récent l'emporte : le brouillon en place
        for k, e in a["entrees"].items():
            connues[k] = (e, a)

    def garder(cle_):
        nonlocal rang
        e, a = connues[cle_]
        rang += 1
        apres["entrees"][cle_] = {**copy.deepcopy(e), "rang": rang, "retiree": True}
        lc = e.get("liste_cle")
        if lc and lc not in apres["listes"] and lc in a["listes"]:
            apres["listes"][lc] = copy.deepcopy(a["listes"][lc])

    for cle_ in sorted(connues.keys() - apres["entrees"].keys(),
                       key=lambda k: connues[k][0]["rang"]):
        e = connues[cle_][0]
        if e.get("retiree"):
            garder(cle_)
            continue
        n = _releves_sur(conn, grille_id, cle_)
        if n == 0:
            continue
        reponse = reponses.get(cle_)
        if reponse is None:
            a_repondre.append({"cle": cle_, "libelle": e["libelle"], "releves": n,
                               "choix": [RETIRER], "fusionner_dans": []})
        elif reponse[0] == RETIRER:
            garder(cle_)
        else:
            fautes.append(_faute(
                "fusion_sur_une_fermee", f"« {e['libelle']} » ne peut pas être fusionnée : "
                "une grille fermée ne fusionne pas, ses relevés vivent dans leur version "
                "publiée", "retirez-la", cle=cle_))
    for cle_ in reponses.keys() - {a["cle"] for a in a_repondre} - {
            k for k, x in apres["entrees"].items() if x.get("retiree")} - {
            f["cle"] for f in fautes}:
        fautes.append(_faute(
            "reponse_sans_objet", f"une réponse est donnée pour « {cle_} », qui ne "
            "disparaît pas", "retirez cette réponse", cle=cle_))
    return apres, a_repondre, fautes


def employes_qui_disparaissent(conn, grille_id: int, avants, apres: dict) -> list:
    """Les fautes d'un réimport d'une grille FERMÉE qui ferait disparaître, de son brouillon,
    une VARIANTE ou une CASE qu'un relevé emploie — dans quelque version que ce soit : ses
    relevés vivent dans une version publiée, et la nomment. La règle du formulaire (« une
    variante ou une case employée ne se supprime pas, même dans le brouillon d'une fermée »,
    tranché par Hugo le 2026-11-04 ; `routes/grilles.supprimer_variante`, `supprimer_case`)
    et celle du réimport d'une OUVERTE (`reconcilier_ouverte`), aux mêmes codes.

    `avants` : les contenus que le fichier remplace (la dernière version publiée, le
    brouillon en place) — ce qu'on en connaît dit le nom d'un disparu. Une variante ne se
    cherche que sous une entrée que le fichier porte encore : une entrée qui disparaît
    entière a sa règle à elle."""
    avants = [a for a in avants if a]
    fautes = []
    for cle_, x in apres["entrees"].items():
        connues = {}
        for a in avants:
            for vc, var in ((a["entrees"].get(cle_) or {}).get("variantes") or {}).items():
                connues.setdefault(vc, var["libelle"])
        for vc, libelle in connues.items():
            if vc in x["variantes"]:
                continue
            n = _releves_sur(conn, grille_id, cle_, vc)
            if n:
                fautes.append(_faute(
                    "variante_employee_disparait",
                    f"la variante « {libelle or vc} » de « {x['libelle'] or cle_} » disparaît "
                    f"alors que {n} relevé(s) la portent", "gardez sa ligne", cle=cle_,
                    colonne="variante"))
    cases = {}
    for a in avants:
        for lc, liste in a["listes"].items():
            for qc, q in liste["qualificatifs"].items():
                cases.setdefault((lc, qc), (liste["libelle"], q["libelle"]))
    for (lc, qc), (nom_liste, libelle) in cases.items():
        if qc in (apres["listes"].get(lc) or {}).get("qualificatifs", {}):
            continue
        n = _releves_sur_qualificatif(conn, grille_id, qc)
        if n:
            fautes.append(_faute(
                "case_employee_disparait",
                f"la case « {libelle or qc} » de la liste « {nom_liste or lc} » disparaît "
                f"alors que {n} relevé(s) la cochent", "gardez sa ligne",
                fichier=NOMS_PAR_DEFAUT[1], colonne="libelle", listes=True))
    return fautes


def _fusion_en_double(conn, grille_id: int, version_id: int, de: str, dans: str, *,
                      une: bool) -> bool:
    """Reporter les relevés de `de` sur `dans` ferait-il se contredire une cible ?

    - `une` (la cardinalité EFFECTIVE de `dans`, telle que la version l'écrira) : une cible
      qui porte un relevé de `de` en porterait alors PLUSIEURS de `dans` — ceux de `de`
      entre eux compris : une étiquette « plusieurs » (« sentiment : perte », « sentiment :
      tristesse » sur une même bulle, J3) ne se fond pas dans une entrée « une seule fois »
      (relecture croisée du mode libre ; le refus d'un passage à « une », sur une fusion) ;
    - sinon, la même VARIANTE deux fois sur une même cible entière — le doublon que la pose
      refuse (J3, `releves.doublon`), qu'une fusion ne doit pas fabriquer."""
    if une:
        return conn.execute(
            "SELECT 1 FROM releve WHERE grille_id = ? AND version_id = ? AND entree_cle IN "
            "(?, ?) GROUP BY COALESCE(region_id, 0), COALESCE(planche_id, 0) "
            "HAVING COUNT(*) > 1 AND SUM(entree_cle = ?) > 0 LIMIT 1",
            (grille_id, version_id, de, dans, de)).fetchone() is not None
    return conn.execute(
        "SELECT 1 FROM releve a JOIN releve b ON COALESCE(a.region_id, 0) = "
        "COALESCE(b.region_id, 0) AND COALESCE(a.planche_id, 0) = COALESCE(b.planche_id, 0) "
        "AND b.grille_id = a.grille_id AND b.version_id = a.version_id AND b.entree_cle = ? "
        "WHERE a.grille_id = ? AND a.version_id = ? AND a.entree_cle = ? "
        "AND a.variante_cle IS NOT NULL AND a.variante_cle = b.variante_cle "
        "AND NOT EXISTS (SELECT 1 FROM releve_mot m WHERE m.releve_id IN (a.id, b.id)) "
        "LIMIT 1", (dans, grille_id, version_id, de)).fetchone() is not None


def vers_sans_double(conn, grille_id: int, version_id: int, c: dict, cle_: str,
                     vers: list) -> list:
    """Parmi les entrées `vers` (`_vers_possibles`, une règle du contenu seul), celles où la
    fusion de `cle_` ne serait pas refusée sur ses relevés (`_fusion_en_double`, la
    cardinalité lue dans le contenu `c`) : ce que l'écran offre dans « Fusionner dans… »,
    pour ne pas offrir ce que le serveur refuserait."""
    return [k for k in vers
            if not _fusion_en_double(conn, grille_id, version_id, cle_, k,
                                     une=_cardinalite_de(c["entrees"][k], c) == "une")]


def _cardinalite_de(e: dict, c: dict) -> str:
    """La cardinalité EFFECTIVE d'une entrée du contenu `c` (`grilles.cardinalite_effective`,
    sa cible ou celle de la version)."""
    return grilles.cardinalite_effective(
        e, grilles.cibles_de(e.get("cible")) or grilles.cibles_de(c.get("cible")))


def _cibles_en_double(conn, grille_id: int, version_id: int, entree_cle: str) -> int:
    """Le nombre de cibles qui portent PLUSIEURS relevés de cette entrée, dans la version."""
    return conn.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM releve WHERE grille_id = ? AND version_id = ? "
        "AND entree_cle = ? GROUP BY COALESCE(region_id, 0), COALESCE(planche_id, 0) "
        "HAVING COUNT(*) > 1)", (grille_id, version_id, entree_cle)).fetchone()[0]


def reporter_cardinalites(conn, grille_id: int, version_id: int, avant: dict,
                          apres: dict) -> None:
    """Après l'écriture d'une version VIVANTE : les relevés d'une entrée dont la cardinalité
    EFFECTIVE a changé — déclarée, ou « Porte sur » qui change le défaut — suivent (`une`,
    figé à la pose). Sans quoi, passée à « une seule fois », l'entrée gardait des relevés
    `une = 0` que ni la relecture de la pose ni l'index ne voyaient, et recevait un second
    relevé sur la même cible (mesuré par le cadrage du mode libre). `reconcilier_ouverte` a
    refusé le passage à `une` d'une entrée qui se contredirait : l'index ne lève pas ici."""
    for cle_, x in apres["entrees"].items():
        e = avant["entrees"].get(cle_)
        if e is None:
            continue
        neuve = _cardinalite_de(x, apres)
        if neuve == _cardinalite_de(e, avant):
            continue
        conn.execute("UPDATE releve SET une = ? WHERE grille_id = ? AND version_id = ? "
                     "AND entree_cle = ?", (int(neuve == "une"), grille_id, version_id, cle_))


def reindexer_libelles(conn, grille_id: int, version_id: int, avant: dict, apres: dict,
                       fusions=()) -> list:
    """Après l'écriture d'une version VIVANTE (donc d'une grille ouverte, la seule dont les
    libellés entrent dans l'index plein texte, J6) : les ÉTIQUETTES des régions dont un
    relevé lit un libellé qui a CHANGÉ — une entrée, une variante, une case renommée —, et
    celles des relevés FUSIONNÉS (`fusions`, avec leurs `releve_ids`), sont réécrites
    (`database.reindex_etiquettes`). APRÈS `ecrire_plan` : c'est le plan neuf qu'elles
    lisent. Un retrait, une entrée remise, un ordre ne changent aucun libellé. Rend les
    régions réécrites."""
    from database import regions_des_releves, reindex_etiquettes   # import paresseux
    av_e, ap_e = avant["entrees"], apres["entrees"]
    entrees = {k for k, x in ap_e.items() if k in av_e and av_e[k]["libelle"] != x["libelle"]}
    variantes = {(k, vc) for k, x in ap_e.items() if k in av_e
                 for vc, v in x["variantes"].items()
                 if vc in av_e[k]["variantes"]
                 and av_e[k]["variantes"][vc]["libelle"] != v["libelle"]}
    cases = {(lc, qc) for lc, l in apres["listes"].items() if lc in avant["listes"]
             for qc, q in l["qualificatifs"].items()
             if qc in avant["listes"][lc]["qualificatifs"]
             and avant["listes"][lc]["qualificatifs"][qc]["libelle"] != q["libelle"]}
    regions = set(regions_des_releves(conn, [i for f in fusions
                                             for i in f.get("releve_ids") or []]))
    if entrees or variantes:
        for r in conn.execute("SELECT region_id, entree_cle, variante_cle FROM releve "
                              "WHERE grille_id = ? AND version_id = ? AND region_id IS NOT NULL",
                              (grille_id, version_id)):
            if r["entree_cle"] in entrees or (r["entree_cle"], r["variante_cle"]) in variantes:
                regions.add(r["region_id"])
    if cases:
        listes = {k: x.get("liste_cle") for k, x in ap_e.items()}
        for r in conn.execute("SELECT r.region_id, r.entree_cle, q.qualificatif_cle "
                              "FROM releve r JOIN releve_qualificatif q ON q.releve_id = r.id "
                              "WHERE r.grille_id = ? AND r.version_id = ? "
                              "AND r.region_id IS NOT NULL", (grille_id, version_id)):
            if (listes.get(r["entree_cle"]), r["qualificatif_cle"]) in cases:
                regions.add(r["region_id"])
    reindex_etiquettes(conn, regions)
    return sorted(regions)


def _fusionner(conn, grille_id: int, version_id: int, fusion: dict) -> list:
    """Reporte les relevés d'une entrée sur une autre (« fusionner dans… »), et rend leurs
    identifiants. `reconcilier_ouverte` a dit le doublon d'une cardinalité `une` ; relu ici
    sous le verrou de l'appelant, il refuse encore, au lieu de tomber sur l'index. Les relevés
    reportés prennent le drapeau `une` de l'entrée d'arrivée (`fusion["une"]`, sa cardinalité
    effective) : sans quoi, née « plusieurs », l'étiquette fondue laissait à une entrée « une
    seule fois » des relevés `une = 0`, que ni la pose ni l'index ne voyaient.

    L'état de chaque relevé AVANT le report reste sur `fusion` (`releves_avant`) : l'acte que
    l'appelant écrit ensuite sur chacun (`journaliser_fusion`) le lit. Rien de cette clé ne
    sort — les réponses et la charge de l'acte de grille ne gardent que `de`, `dans` et
    `releve_ids`."""
    lignes = conn.execute(
        f"SELECT {', '.join(_COLONNES_D_UN_REPORT)} FROM releve WHERE grille_id = ? "
        "AND version_id = ? AND entree_cle = ? ORDER BY id",
        (grille_id, version_id, fusion["de"])).fetchall()
    ids = [r[0] for r in lignes]
    fusion["releves_avant"] = {r[0]: dict(zip(_COLONNES_D_UN_REPORT, r)) for r in lignes}
    if _fusion_en_double(conn, grille_id, version_id, fusion["de"], fusion["dans"],
                         une=fusion["une"]):
        raise Refus(409, f"Fusionner « {fusion['de']} » dans « {fusion['dans']} » poserait "
                         "deux fois une entrée qui ne se pose qu'une fois sur la même cible. "
                         "Retirez-la plutôt, ou retirez d'abord l'un des deux relevés. Rien "
                         "n'est importé.")
    conn.execute("UPDATE releve SET entree_cle = ?, une = ? WHERE grille_id = ? "
                 "AND version_id = ? AND entree_cle = ?",
                 (fusion["dans"], int(fusion["une"]), grille_id, version_id, fusion["de"]))
    return ids


# Ce qu'un acte de fusion dit d'un relevé, avant et après : ce qui tient à son identité (sa
# cible, sa grille, sa version) et ce que la fusion change (l'entrée, le drapeau `une`) ; la
# variante, qui ne change pas — l'entrée d'arrivée porte les variantes employées —, pour lire
# l'acte seul. Rien d'autre : ni précision, ni passage, ni lien (du texte libre, et des
# valeurs que la fusion ne touche pas). Et `conflit.auteur_du_champ` ne nomme que qui a CHANGÉ
# un champ : ni la variante, ni rien de ce que garde CONC-3 n'y change.
_COLONNES_D_UN_REPORT = ("id", "region_id", "planche_id", "grille_id", "version_id",
                         "entree_cle", "variante_cle", "une")


def journaliser_fusion(conn, grille_id: int, numero: int, fusion: dict,
                       acte_id: int | None, *, vers: dict | None = None) -> int:
    """Écrit au journal un acte par relevé qu'une fusion a déplacé (`_fusionner`), sous sa
    cible ordinaire — la RÉGION (`releve`) ou la PLANCHE (`releve_planche`) —, du type
    `grilles.ACTE_FUSION` : ni Ctrl+Z ne l'offre, ni « qui perd quoi » ne le compte
    (`grilles.sql_acte_qui_range`). À appeler APRÈS l'acte de grille de la fusion, dont
    `acte_id` est l'identifiant (None si l'appelant n'en a pas écrit) : chaque acte de relevé
    le nomme (`fusion.acte`), la grille et le numéro de sa version avec, et l'acte de grille
    nomme déjà ses relevés (`releve_ids`). L'état d'après est relu en base : le drapeau `une`
    a pu changer encore après le report (`reporter_cardinalites`). Ne commite pas ; rend le
    nombre d'actes écrits.

    Le journal n'est lu que par des sorties bornées — Ctrl+Z (les actes de l'agent, de ses
    types), la garde de CONC-3 (qui a changé un champ qu'elle garde), « qui perd quoi »
    (bornée à qui efface l'album, et qui l'écarte), et aucun export (`releve` est retenu) :
    écrire l'acte sur un relevé d'un album que le responsable ne lit pas ne lui en montre
    rien, et ne le montre à personne.

    `vers` (ANN-7, « Passer dans une grille… », `structurer`) : la grille et la version
    d'ARRIVÉE quand la fusion change de grille — `{grille_id, version}`, nommées dans le lien ;
    la charge, elle, dit déjà la grille d'avant et d'après."""
    import journal                               # import paresseux, cf. `importer`
    avants = fusion.get("releves_avant") or {}
    ids = list(fusion.get("releve_ids") or [])
    lien = {"acte": acte_id, "grille_id": grille_id, "version": numero,
            "de": fusion["de"], "dans": fusion["dans"]}
    if vers is not None:
        lien["vers"] = {"grille_id": vers["grille_id"], "version": vers["version"]}
    n = 0
    for i in range(0, len(ids), 500):
        tranche = ids[i:i + 500]
        apres = {r[0]: dict(zip(_COLONNES_D_UN_REPORT, r)) for r in conn.execute(
            f"SELECT {', '.join(_COLONNES_D_UN_REPORT)} FROM releve "
            f"WHERE id IN ({', '.join('?' * len(tranche))})", tranche)}
        for rid in tranche:
            ap, av = apres.get(rid), avants.get(rid)
            if ap is None or av is None:
                continue
            charge_av = {"releve_id": rid, **{k: av[k] for k in _COLONNES_D_UN_REPORT[1:]}}
            charge_ap = {"releve_id": rid, **{k: ap[k] for k in _COLONNES_D_UN_REPORT[1:]},
                         "fusion": lien}
            # Deux appels LITTÉRAUX, comme `routes/releves.journaliser_releve` : le cliquet du
            # journal relève les cibles par AST.
            if ap["region_id"] is not None:
                journal.journaliser(conn, grilles.ACTE_FUSION, "releve", ap["region_id"],
                                    avant=charge_av, apres=charge_ap)
            else:
                journal.journaliser(conn, grilles.ACTE_FUSION, "releve_planche",
                                    ap["planche_id"], avant=charge_av, apres=charge_ap)
            n += 1
    return n


# --------------------------------------------------------------------------- #
# L'écriture d'une version
# --------------------------------------------------------------------------- #
def ecrire_version(conn: sqlite3.Connection, grille_id: int, c: dict, *, numero: int,
                   etat: str, note, par) -> int:
    """Écrit une version et son plan — toutes ses lignes —, et rend son identifiant. Ne
    commite pas, n'écrit rien au journal (l'appelant le fait)."""
    vid = conn.execute(
        "INSERT INTO grille_version (grille_id, numero, etat, cible, note, empreinte, "
        "importee_par, importee_le) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (grille_id, numero, etat, c["cible"], note, grilles.empreinte(c), par)).lastrowid
    ecrire_plan(conn, vid, c)
    return vid


def ecrire_plan(conn: sqlite3.Connection, vid: int, c: dict) -> None:
    """Les lignes du plan d'une version, depuis un contenu normalisé. Une entrée qui ne dit
    pas son ÉTAT (un tableur ne le porte pas) est ÉCRITE, donc DÉFINIE (J4) — même dans une
    grille ouverte : seule une entrée née en posant naît provisoire."""
    conn.executemany(
        "INSERT INTO grille_rubrique (version_id, cle, libelle, parent_cle, rang) "
        "VALUES (?, ?, ?, ?, ?)",
        [(vid, k, r["libelle"], r["parent_cle"], r["rang"]) for k, r in c["rubriques"].items()])
    for k, e in c["entrees"].items():
        conn.execute(
            "INSERT INTO grille_entree (version_id, cle, rubrique_cle, rang, forme, libelle, "
            "definition, structure, piege, precision, lien, cible, cardinalite, liste_cle, "
            "retiree, etat) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (vid, k, e["rubrique_cle"], e["rang"], e["forme"], e["libelle"], e["definition"],
             e["structure"], e["piege"], e["precision"], int(bool(e["lien"])), e["cible"],
             e["cardinalite"], e["liste_cle"], int(bool(e.get("retiree"))),
             e.get("etat") or grilles.ENTREE_DEFINIE))
        for i, texte in enumerate(e["exemples"]):
            conn.execute("INSERT INTO grille_exemple (version_id, entree_cle, variante_cle, "
                         "rang, texte) VALUES (?, ?, NULL, ?, ?)", (vid, k, i, texte))
        for vc, x in e["variantes"].items():
            conn.execute(
                "INSERT INTO grille_variante (version_id, entree_cle, cle, libelle, "
                "definition, structure, piege, rang) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (vid, k, vc, x["libelle"], x["definition"], x["structure"], x["piege"],
                 x["rang"]))
            for i, texte in enumerate(x["exemples"]):
                conn.execute("INSERT INTO grille_exemple (version_id, entree_cle, "
                             "variante_cle, rang, texte) VALUES (?, ?, ?, ?, ?)",
                             (vid, k, vc, i, texte))
    for lc, l in c["listes"].items():
        conn.execute("INSERT INTO grille_liste (version_id, cle, libelle) VALUES (?, ?, ?)",
                     (vid, lc, l["libelle"]))
        conn.executemany(
            "INSERT INTO grille_qualificatif (version_id, liste_cle, cle, libelle, "
            "definition, rang) VALUES (?, ?, ?, ?, ?, ?)",
            [(vid, lc, qc, q["libelle"], q["definition"], q["rang"])
             for qc, q in l["qualificatifs"].items()])


def effacer_plan(conn: sqlite3.Connection, vid: int) -> None:
    """Retire les lignes du plan d'une version (un brouillon qu'on remplace, la version
    vivante d'une grille ouverte qu'on réimporte)."""
    for t in ("grille_rubrique", "grille_entree", "grille_variante", "grille_liste",
              "grille_qualificatif", "grille_exemple"):
        conn.execute(f"DELETE FROM {t} WHERE version_id = ?", (vid,))


# --------------------------------------------------------------------------- #
# L'import — le geste entier, partagé par l'outil et la route
# --------------------------------------------------------------------------- #
def nom_pris(conn: sqlite3.Connection, projet_id: int, nom: str, *, sauf=None) -> bool:
    """Le nom est-il celui d'une autre grille de ce projet ? Comparé par la clé d'un
    libellé (`database.cle_tag` : casse, apostrophes, espaces), dans le projet SEUL —
    aucune unicité d'instance, donc aucun oracle « ce nom est pris ailleurs »."""
    return conn.execute(
        "SELECT 1 FROM grille WHERE projet_id = ? AND cle_tag(nom) = cle_tag(?) "
        "AND id IS NOT ?", (projet_id, nom, sauf)).fetchone() is not None


def tableur_de(flux_entrees=None, flux_listes=None, *, classeur: bytes | None = None,
               noms=NOMS_PAR_DEFAUT) -> dict:
    """Le tableur à lire, découpé en feuilles : un classeur (ses octets), ou les deux CSV."""
    if classeur is not None:
        return grille_tableur.lire_classeur(classeur)
    return {"entrees": (noms[0], *grille_tableur.feuille_csv(flux_entrees)),
            "listes": (noms[1], *grille_tableur.feuille_csv(flux_listes))
            if flux_listes is not None else None}


def importer(conn: sqlite3.Connection, *, projet_id: int, flux_entrees=None, flux_listes=None,
             classeur: bytes | None = None, grille_id: int | None = None,
             nom: str | None = None, ouverte: bool | None = None,
             porte_sur: str | None = None, note: str | None = None, par=None,
             a_blanc: bool = False, reponses=None, noms=NOMS_PAR_DEFAUT) -> dict:
    """Importe un tableur — deux CSV (`flux_entrees`, `flux_listes`) ou un classeur
    (`classeur`, ses octets) — comme version d'une grille, neuve (`nom`) ou suivante d'une
    grille existante de ce projet (`grille_id`). Le droit de l'appelant est vérifié AVANT
    (gérer le projet) ; ici, les règles du modèle :

    - la déclaration (`nom`, `ouverte`, `porte_sur`, `note`) vient des arguments, ou de la
      feuille « 1. La grille » du classeur (`declarer`) ;
    - une grille FERMÉE a au plus un brouillon : réimporter le REMPLACE ; si la dernière
      version est publiée, un brouillon neuf naît, au numéro suivant — sauf si son empreinte
      est celle de la version publiée, ou du brouillon en place : « aucun changement » ; une
      variante ou une case qu'un relevé emploie n'en disparaît pas (409, la règle du
      formulaire : `employes_qui_disparaissent`), et une ENTRÉE employée que le fichier ne
      porte plus attend « retirer » (`reconcilier_fermee`, recommandation de la pilote à
      confirmer par Hugo) ;
    - une grille OUVERTE n'a qu'une version, `vivante`, née au premier import, qui s'enrichit
      EN POSANT (G14) ; la réimporter la récrit EN PLACE (tranché par Hugo le 2026-11-03,
      renversant le 409 d'avant), et une entrée employée que le fichier ne porte pas attend
      sa réponse (`reponses` : « retirer » ou « fusionner:<cle> », `reconcilier_ouverte`) —
      sans elle, l'import est refusé (409) avec le bilan qui la demande.

    `a_blanc` : rend le bilan sans rien écrire. Lève `Refus` (statut, message, anomalies,
    bilan), `FormatInvalide` sur un fichier ou un en-tête. Ne commite pas ; écrit au journal
    sous `grille` (sauf à blanc). Rend `{grille_id, version: {numero, etat} | None, ecrit,
    aucun_changement, verdict, a_savoir, va_naitre, bilan, a_repondre, compare_a,
    declaration, identifiants_deduits}`."""
    import journal                               # import paresseux : le cœur reste léger
    tableur = tableur_de(flux_entrees, flux_listes, classeur=classeur, noms=noms)
    g = None
    if grille_id is not None:
        g = conn.execute("SELECT * FROM grille WHERE id = ? AND projet_id = ?",
                         (grille_id, projet_id)).fetchone()
        if g is None:
            raise Refus(404, f"Grille {grille_id} introuvable dans ce projet.")
        if g["retiree_le"]:
            raise Refus(409, "Cette grille est retirée : on ne lui importe plus de version.")
    decl, fautes_decl, notes_decl = declarer(tableur, nom=nom, ouverte=ouverte,
                                             porte_sur=porte_sur, note=note, grille=g)
    origine, notes_origine = origine_du_classeur(conn, tableur, grille=g)
    notes_decl += notes_origine
    ouverte, nom, note = decl["ouverte"], decl["nom"], decl["note"]
    if g is None:
        if not nom and not fautes_decl:
            raise Refus(422, "Une grille neuve a besoin d'un nom (déclaré, ou dans la "
                             f"feuille « {grille_tableur.FEUILLE_GRILLE} »).")
        if nom and nom_pris(conn, projet_id, nom):
            raise Refus(409, f"Une grille de ce projet s'appelle déjà « {nom} » : importez "
                             "une version suivante de celle-ci, ou choisissez un autre nom.")
    reference = None                          # la version à laquelle on compare
    porte_sur = decl["porte_sur"]
    if g is not None:
        reference = grilles.derniere_version(conn, g["id"], grilles.ETAT_PUBLIEE,
                                             grilles.ETAT_VIVANTE)
        if porte_sur is None:
            derniere = grilles.derniere_version(conn, g["id"])
            porte_sur = (" | ".join(grilles.cibles_de(derniere["cible"]))
                         if derniere is not None else None)
    avant = grilles.contenu(conn, reference["id"]) if reference is not None else None
    reference_ids = avant
    if g is not None and reference is None:
        brouillon_ = grilles.derniere_version(conn, g["id"], grilles.ETAT_BROUILLON)
        reference_ids = grilles.contenu(conn, brouillon_["id"]) if brouillon_ else None
    lu = lire_tableur(tableur, porte_sur=porte_sur, reference=reference_ids,
                      ou_porte_sur=decl["ou"].get("porte_sur"))
    anomalies = fautes_decl + lu["anomalies"]
    a_savoir = notes_decl + lu["avertissements"]
    commun = {"declaration": {k: decl[k] for k in ("nom", "ouverte", "note", "lus")}
              | {"porte_sur": porte_sur},
              "identifiants_deduits": lu["identifiants_deduits"]}
    if anomalies:
        raise Refus(422, f"Le tableur est refusé : {len(anomalies)} anomalie(s). Rien n'est "
                         "importé.", anomalies,
                    {"verdict": verdict("refuse", n=len(anomalies)), "a_savoir": a_savoir,
                     **commun})
    c = lu["contenu"]
    vivante = ouverte and g is not None and reference is not None
    a_repondre, fusions = [], []
    if vivante:
        c, a_repondre, fusions, fautes = reconcilier_ouverte(
            conn, g["id"], reference["id"], avant, c, lire_reponses(reponses))
        if fautes:
            raise Refus(409, f"La grille ouverte ne peut pas être réimportée ainsi : "
                             f"{len(fautes)} point(s) à régler. Rien n'est importé.", fautes,
                        {"verdict": verdict("refuse", n=len(fautes)), "a_savoir": a_savoir,
                         **commun})
    elif g is not None:
        # Une grille FERMÉE : son brouillon tient la règle du formulaire sur une variante ou
        # une case employée — elle ne disparaît pas (choix 3 des routes d'écriture).
        brouillon_en_place = grilles.derniere_version(conn, g["id"], grilles.ETAT_BROUILLON)
        avants = (avant, grilles.contenu(conn, brouillon_en_place["id"])
                  if brouillon_en_place is not None else None)
        # Une ENTRÉE employée qui disparaît entière attend « retirer », comme sur une ouverte
        # (recommandation de la pilote, à confirmer par Hugo : `reconcilier_fermee`).
        c, a_repondre, fautes = reconcilier_fermee(conn, g["id"], avants, c,
                                                   lire_reponses(reponses))
        fautes += employes_qui_disparaissent(conn, g["id"], avants, c)
        if fautes:
            raise Refus(409, f"La grille ne peut pas être réimportée ainsi : {len(fautes)} "
                             "point(s) à régler. Rien n'est importé.", fautes,
                        {"verdict": verdict("refuse", n=len(fautes)), "a_savoir": a_savoir,
                         **commun})
    b = bilan(conn, g["id"] if g is not None else None, avant, c)
    for d in b["disparus"] if g is not None else ():
        if d["quoi"] == "entree":
            fusion = next((f for f in fusions if f["de"] == d["cle"]), None)
            d["decision"] = (f"{FUSIONNER}:{fusion['dans']}" if fusion
                             else "a_repondre" if any(a["cle"] == d["cle"] for a in a_repondre)
                             else "part")
    for ch in b["changes"]:
        if ch["champ"] == "retiree":
            ch["decision"] = RETIRER
    emp = grilles.empreinte(c)
    brouillon = (grilles.derniere_version(conn, g["id"], grilles.ETAT_BROUILLON)
                 if g is not None else None)
    resultat = {"grille_id": g["id"] if g is not None else None, "version": None,
                "ecrit": False, "aucun_changement": False, "bilan": b,
                "derivee_de": ({"nom": origine["nom"], "version": origine["version"]}
                               if origine else None),
                "va_naitre": va_naitre(avant, c), "a_repondre": a_repondre,
                "compare_a": reference["numero"] if reference is not None else None,
                "a_savoir": a_savoir, **commun}
    deja = [v for v in (reference, brouillon) if v is not None and v["empreinte"] == emp]
    if deja and not fusions:
        resultat["aucun_changement"] = True
        resultat["version"] = {"numero": deja[0]["numero"], "etat": deja[0]["etat"]}
        resultat["verdict"] = verdict("aucun_changement")
        return resultat
    if a_repondre:
        resultat["verdict"] = verdict("a_repondre", n=len(a_repondre))
        if not vivante:                       # une fermée ne fusionne pas : « retirer » seul
            resultat["verdict"]["phrase"] = resultat["verdict"]["phrase"].replace(
                "« retirer » ou « fusionner dans… »", "« retirer »")
        if a_blanc:
            return resultat
        raise Refus(409, f"{len(a_repondre)} entrée(s) employée(s) disparaissent de la grille "
                         + ("ouverte : dites pour chacune « retirer » ou « fusionner dans… »."
                            if vivante else ": dites pour chacune « retirer » (une grille "
                            "fermée ne fusionne pas).")
                         + " Rien n'est importé.", [], resultat)
    if a_blanc:
        resultat["verdict"] = verdict("importable")
        if brouillon is not None:
            resultat["version"] = {"numero": brouillon["numero"], "etat": brouillon["etat"],
                                   "remplace": True}
        return resultat
    if g is None:
        # Son identifiant est NEUF, toujours : celui que le classeur porte est celui de la
        # grille dont il a été tiré, que la neuve nomme comme son origine (v40).
        o = origine or {}
        gid = conn.execute(
            "INSERT INTO grille (projet_id, nom, ouverte, cree_par, identifiant, "
            "derivee_de_identifiant, derivee_de_nom, derivee_de_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (projet_id, nom, int(bool(ouverte)), par, grilles.identifiant_neuf(),
             o.get("identifiant"), o.get("nom"), o.get("version"))).lastrowid
        journal.journaliser(conn, "creation", "grille", gid,
                            apres={"projet_id": projet_id, "nom": nom,
                                   "ouverte": bool(ouverte),
                                   **({"derivee_de": origine} if origine else {})})
        resultat["grille_id"] = gid
    else:
        gid = g["id"]
    etat = grilles.ETAT_VIVANTE if ouverte else grilles.ETAT_BROUILLON
    # Une entrée que le fichier porte DÉJÀ garde son état (v39) : le tableur ne le dit pas,
    # et réimporter ne change pas ce qu'elle était — une étiquette née en posant reste
    # provisoire tant qu'un responsable ne l'a pas définie. Une entrée neuve est définie
    # (`ecrire_plan`).
    for k, e in c["entrees"].items():
        if "etat" not in e and avant is not None and k in avant["entrees"]:
            e["etat"] = avant["entrees"][k]["etat"]
    trace = {}
    en_place = reference if vivante else brouillon
    if en_place is not None:
        if vivante:
            for f in fusions:
                f["releve_ids"] = _fusionner(conn, gid, reference["id"], f)
            trace = {"retirees": [k for k, x in c["entrees"].items()
                                  if x.get("retiree") and not avant["entrees"][k].get("retiree")],
                     "fusions": [{k: f[k] for k in ("de", "dans", "releve_ids")}
                                 for f in fusions]}
        effacer_plan(conn, en_place["id"])
        conn.execute("UPDATE grille_version SET cible = ?, note = ?, empreinte = ?, "
                     "importee_par = ?, importee_le = datetime('now') WHERE id = ?",
                     (c["cible"], note, emp, par, en_place["id"]))
        ecrire_plan(conn, en_place["id"], c)
        if vivante:
            reporter_cardinalites(conn, gid, en_place["id"], avant, c)
            reindexer_libelles(conn, gid, en_place["id"], avant, c, fusions)
        numero = en_place["numero"]
    else:
        derniere = grilles.derniere_version(conn, gid)
        numero = (derniere["numero"] + 1) if derniere is not None else 1
        ecrire_version(conn, gid, c, numero=numero, etat=etat, note=note, par=par)
    acte = journal.journaliser(conn, "modification", "grille", gid,
                               apres={"import": {"numero": numero, "etat": etat,
                                                 "empreinte": emp,
                                                 "remplace": en_place is not None, **trace}})
    # Un acte par relevé déplacé, après l'acte de l'import qu'il prolonge (le mode libre).
    if trace:                                    # une version vivante, écrite en place
        for f in fusions:
            journaliser_fusion(conn, gid, numero, f, acte)
    resultat.update(ecrit=True, verdict=verdict("importe"),
                    version={"numero": numero, "etat": etat,
                             **({"remplace": True} if en_place is not None else {})})
    return resultat




# --------------------------------------------------------------------------- #
# Publier, activer, masquer — le cœur partagé de la route et de l'outil (ANN-7, tranche 2, H3)
# --------------------------------------------------------------------------- #
# Les règles du MODÈLE seulement : qui a le droit (gérer le projet, administrer la
# collection) est vérifié AVANT par l'appelant — la route par la portée, l'outil parce qu'un
# shell tient la base entre ses mains. Ni commit, ni verrou : l'appelant tient la transaction.
_MOTIF_JEU = ("C'est le jeu des bacs à sable : il ne reçoit pas de grille, et ne se change "
              "que par son outil (`tools/preparer_jeu.py`).")


def publier(conn: sqlite3.Connection, grille_id: int, version, *, par=None) -> None:
    """PUBLIE un brouillon (`version` : sa ligne, vérifiée par l'appelant) : il devient une
    version figée, qui garde son numéro, et l'acte s'écrit sous `grille`."""
    import journal                               # import paresseux, cf. `importer`
    conn.execute("UPDATE grille_version SET etat = ?, publiee_par = ?, "
                 "publiee_le = datetime('now') WHERE id = ?",
                 (grilles.ETAT_PUBLIEE, par, version["id"]))
    journal.journaliser(conn, "modification", "grille", grille_id,
                        avant={"version": version["numero"], "etat": grilles.ETAT_BROUILLON},
                        apres={"version": version["numero"], "etat": grilles.ETAT_PUBLIEE})


def installer(conn: sqlite3.Connection, *, projet_id: int, flux_entrees, flux_listes=None,
              nom: str, porte_sur: str, note: str | None = None, par=None) -> int:
    """Une grille NEUVE, importée, publiée et active sur le projet, d'un seul geste : ce que
    reçoit un bac à sable à sa naissance (H4). Rien de neuf : les trois gestes d'une personne,
    à la suite, sous leurs règles. Lève ce qu'ils lèvent ; rend l'identifiant de la grille."""
    res = importer(conn, projet_id=projet_id, flux_entrees=flux_entrees,
                   flux_listes=flux_listes, nom=nom, porte_sur=porte_sur, note=note, par=par)
    gid, numero = res["grille_id"], res["version"]["numero"]
    publier(conn, gid, grilles.version(conn, gid, numero), par=par)
    activer(conn, projet_id=projet_id, grille_id=gid, numero=numero, par=par)
    return gid


def installer_grille_de_travail(conn: sqlite3.Connection, projet_id: int, *,
                                agent: str | None = None,
                                agent_type: str = "humain") -> int | None:
    """La grille de TRAVAIL d'un projet qui naît (ANN-7, le basculement ; Hugo, 2026-11-05) :
    OUVERTE, VIDE, sur toute zone (les types de `grilles.CIBLES_ZONE`), active dans sa
    version vivante 1, et à PERSONNE — aucun `cree_par`, comme la grille d'un bac à sable : le
    journal garde seul l'acte, sous `grille`. Tout annotateur y fait naître une étiquette en
    la posant (G14), « lieu : forêt » compris (`routes/releves._entree_neuve`).

    Rien d'une grille n'est dans le code : une grille vide et nommée n'est pas un vocabulaire,
    et son nom vit dans `config.GRILLE_DE_TRAVAIL_NOM`. Elle se DÉSIGNE par son drapeau
    (`grille.travail`, J2, v39 : au plus une par projet), et non par ce nom, qui se change.
    Jamais dans le projet de jeu ; rien si le projet a déjà la sienne (rejouée, elle ne double
    rien). Une autre grille du projet qui porterait déjà ce nom lui laisse le sien : la
    grille de travail prend « … 2 », « … 3 » (un nom est unique dans son projet). Ne commite
    pas ; rend l'identifiant, ou None. `agent`, `agent_type` : qui la journalise — par défaut
    l'humain de la requête, qui fait naître le projet ; la migration v39 se nomme."""
    import database                              # import paresseux, cf. `importer`
    import journal
    from config import GRILLE_DE_TRAVAIL_NOM, GRILLE_DE_TRAVAIL_NOTE
    if database.est_jeu(conn, projet_id) or conn.execute(
            "SELECT 1 FROM grille WHERE projet_id = ? AND travail = 1",
            (projet_id,)).fetchone():
        return None
    nom, n = GRILLE_DE_TRAVAIL_NOM, 1
    while nom_pris(conn, projet_id, nom):
        n += 1
        nom = f"{GRILLE_DE_TRAVAIL_NOM} {n}"
    cible = grilles.ecrire_cibles(grilles.CIBLES_ZONE)
    gid = conn.execute("INSERT INTO grille (projet_id, nom, ouverte, travail, identifiant) "
                       "VALUES (?, ?, 1, 1, ?)",
                       (projet_id, nom, grilles.identifiant_neuf())).lastrowid
    ecrire_version(conn, gid, {"cible": cible, "rubriques": {}, "entrees": {}, "listes": {}},
                   numero=1, etat=grilles.ETAT_VIVANTE, note=GRILLE_DE_TRAVAIL_NOTE, par=None)
    journal.journaliser(conn, "creation", "grille", gid,
                        apres={"projet_id": projet_id, "nom": nom,
                               "ouverte": True, "porte_sur": cible, "travail": True,
                               "version": {"numero": 1, "etat": grilles.ETAT_VIVANTE}},
                        agent=agent, agent_type=agent_type)
    activer(conn, projet_id=projet_id, grille_id=gid, numero=1, agent=agent,
            agent_type=agent_type)
    return gid


def grille_sans_rien(conn: sqlite3.Connection, grille_id: int) -> bool:
    """La grille de TRAVAIL d'un projet (`grille.travail`, J2) qui ne porte RIEN : aucune
    entrée dans aucune de ses versions, aucun relevé, aucune passe. Elle n'est pas un
    vocabulaire — née avec le projet, on n'y a rien posé — et part avec son projet
    (`socle._supprimer_projet`). Toute AUTRE grille, même vide, a été créée exprès : elle
    retient son projet (G18)."""
    porte = conn.execute(
        "SELECT NOT COALESCE((SELECT travail FROM grille WHERE id = ?), 0), "
        "       EXISTS (SELECT 1 FROM grille_entree e JOIN grille_version v "
        "               ON v.id = e.version_id WHERE v.grille_id = ?), "
        "       EXISTS (SELECT 1 FROM releve WHERE grille_id = ?), "
        "       EXISTS (SELECT 1 FROM passe WHERE grille_id = ?)",
        (grille_id, grille_id, grille_id, grille_id)).fetchone()
    return not any(porte)


def version_activable(conn: sqlite3.Connection, grille_id: int):
    """La version qu'on ACTIVERAIT sans en dire le numéro : la vivante d'une grille ouverte,
    la publiée la plus récente d'une fermée ; None s'il n'y en a pas (un brouillon seul)."""
    g = conn.execute("SELECT ouverte FROM grille WHERE id = ?", (grille_id,)).fetchone()
    if g is None:
        return None
    return grilles.derniere_version(
        conn, grille_id, grilles.ETAT_VIVANTE if g["ouverte"] else grilles.ETAT_PUBLIEE)


def activer(conn: sqlite3.Connection, *, projet_id: int, grille_id: int, numero: int,
            par=None, agent: str | None = None, agent_type: str = "humain",
            reponses=None, vu: str | None = None, exiger_vu: bool = True) -> bool:
    """ACTIVE la grille sur le projet dans la version `numero` (R4) — publiée pour une
    grille fermée, vivante pour une ouverte. Un projet n'active que SES grilles (le
    catalogue n'existe pas) ; une grille retirée ne s'active plus. Lève `Refus` ; rend True
    si l'activation s'est écrite, False si elle était déjà celle-là.

    Changer la version d'une activation sous laquelle le projet porte des relevés — qu'on
    l'active par-dessus, ou qu'on la réactive après l'avoir désactivée — est la MONTÉE DE
    VERSION (`montee`, ANN-7, tranchée par Hugo le 2026-11-15) : elle attend `vu`, le
    condensé du bilan que l'écran a lu (`exiger_vu` : la route ; l'outil, qui calcule et
    écrit dans la même transaction, s'en passe), et `reponses` (`montee.lire_reponses`) pour
    chaque entrée retirée ; un bilan changé, une réponse qui manque ou ne vaut pas, une cible
    qui se contredirait, une version plus ancienne : `Refus` (409) qui porte le bilan. Une
    activation sous laquelle le projet ne porte que des PASSES y applique la règle des passes,
    sans bilan exigé."""
    import database                              # import paresseux, cf. `importer`
    import journal
    import montee
    if database.est_jeu(conn, projet_id):
        raise Refus(409, _MOTIF_JEU)
    g = conn.execute("SELECT * FROM grille WHERE id = ?", (grille_id,)).fetchone()
    if g is None:
        raise Refus(404, f"Grille {grille_id} introuvable")
    if g["projet_id"] != projet_id:
        raise Refus(409, "Un projet n'active que ses grilles : le catalogue, d'où l'on "
                         "active la grille d'un autre projet, n'existe pas encore.")
    if g["retiree_le"]:
        raise Refus(409, "Cette grille est retirée : elle ne s'active plus.")
    v = grilles.version(conn, grille_id, numero)
    attendu = grilles.ETAT_VIVANTE if g["ouverte"] else grilles.ETAT_PUBLIEE
    if v is None or v["etat"] != attendu:
        raise Refus(409, f"Une grille {'ouverte' if g['ouverte'] else 'fermée'} s'active "
                         f"dans une version {attendu}.")
    act = grilles.activation(conn, projet_id, grille_id)
    if act is not None and act["version_id"] == v["id"]:
        return False
    calcul = montee.calculer(conn, projet_id=projet_id, grille_id=grille_id, version=v,
                             reponses=montee.lire_reponses(reponses))
    if calcul is not None:
        b = montee.bilan_lisible(calcul)
        if calcul["refuse"]:
            raise Refus(409, f"La montée vers la version {numero} est refusée : "
                             f"{b['verdict']['phrase']} Rien n'est changé.", [], b)
        if calcul["a_monter"] and exiger_vu and vu != b["vu"]:
            raise Refus(409, "Le bilan de la montée n'est plus celui que vous avez lu (ou "
                             "vous ne l'avez pas lu) : relisez-le avant de monter. Rien n'est "
                             "changé.", [], b)
        if calcul["fautes"]:
            raise Refus(409, f"{len(calcul['fautes'])} réponse(s) ne valent pas : rien n'est "
                             "changé.", calcul["fautes"], b)
        # (retirées, absentes de la version d'arrivée) : un couple, jamais vrai par lui-même.
        if sum(calcul["repondre"]):
            raise Refus(409, f"{sum(calcul['repondre'])} entrée(s) retirée(s) ou absente(s) de "
                             f"la version {v['numero']} attendent votre réponse : « laisser » "
                             "ou « fusionner dans… ». Rien n'est changé.", [], b)
        montee.ecrire(conn, calcul, projet_id=projet_id, grille_id=grille_id, version=v,
                      act=act, par=par, agent=agent, agent_type=agent_type)
        return True
    conn.execute("INSERT INTO projet_grille (projet_id, grille_id, version_id, active_par) "
                 "VALUES (?, ?, ?, ?) ON CONFLICT(projet_id, grille_id) DO UPDATE SET "
                 "version_id = excluded.version_id, active_par = excluded.active_par, "
                 "active_le = datetime('now')", (projet_id, grille_id, v["id"], par))
    journal.journaliser(conn, "lien", "grille", grille_id,
                        avant={"projet_id": projet_id, "version": act["numero"]}
                        if act else None,
                        apres={"projet_id": projet_id, "version": v["numero"]},
                        agent=agent, agent_type=agent_type)
    return True


def masquer(conn: sqlite3.Connection, *, collection_id: int, grille_id: int,
            par=None) -> bool:
    """MASQUE la grille dans la collection (Q1) — un filtre d'écran, pas une garde. Elle doit
    être ACTIVE dans le projet de la collection : sinon il n'y a rien à masquer. Lève
    `Refus` ; rend True si le masque s'est écrit, False s'il y était déjà."""
    import database
    import journal
    c = conn.execute("SELECT nom FROM collection WHERE id = ?", (collection_id,)).fetchone()
    if c is None:
        raise Refus(404, f"Collection {collection_id} introuvable")
    if grilles.activation(conn, database.projet_de_collection(conn, collection_id),
                          grille_id) is None:
        raise Refus(409, "Cette grille n'est pas active dans le projet de la collection : il "
                         "n'y a rien à masquer.")
    if not conn.execute("INSERT OR IGNORE INTO collection_grille_masquee (collection_id, "
                        "grille_id, masque_par) VALUES (?, ?, ?)",
                        (collection_id, grille_id, par)).rowcount:
        return False
    journal.journaliser(conn, "lien", "grille", grille_id,
                        apres={"masquee_dans": collection_id, "collection": c["nom"]})
    return True


# --------------------------------------------------------------------------- #
# Le réexport — le tableur, identifiants compris
# --------------------------------------------------------------------------- #
def _cellule_cibles(valeur) -> str:
    return " | ".join(grilles.cibles_de(valeur))


def exporter(conn: sqlite3.Connection, version_id: int) -> tuple[str, str]:
    """Les deux CSV d'une version, au format MACHINE de l'import, identifiants compris : le
    chemin de la DÉRIVATION allégée (réexporter, réimporter comme grille de son projet,
    tranché le 2026-10-22), et la seule façon de vérifier les `cle` par aller-retour.
    Réimporté tel quel, il rend la même empreinte (`tests/test_grilles.py`). Une entrée
    RETIRÉE n'y est pas (cf. `grille_tableur.rangees`)."""
    c = grilles.contenu(conn, version_id)

    def ligne(**valeurs):
        return [_neutre(valeurs.get(col)) for col in COLONNES]
    sortie = io.StringIO()
    w = ecrivain_csv(sortie, lineterminator="\r\n")
    w.writerow(COLONNES)
    for cle_, e in sorted(c["entrees"].items(), key=lambda kv: kv[1]["rang"]):
        if e.get("retiree"):            # ne se pose plus ; un réimport la garde retirée
            continue
        chemin = grilles.chemin_de_rubrique(c["rubriques"], e["rubrique_cle"])
        w.writerow(ligne(
            cle=cle_, rubrique=" > ".join(c["rubriques"][r]["libelle"] for r in chemin),
            rubrique_cle=" > ".join(chemin), forme=e["forme"], libelle=e["libelle"],
            structure=e["structure"], definition=e["definition"],
            exemples=" | ".join(e["exemples"]), piege=e["piege"], liste=e["liste_cle"],
            precision=e["precision"], lien="oui" if e["lien"] else "",
            cible=_cellule_cibles(e["cible"]), cardinalite=e["cardinalite"]))
        for vc, x in sorted(e["variantes"].items(), key=lambda kv: kv[1]["rang"]):
            w.writerow(ligne(cle=cle_, variante_cle=vc, variante=x["libelle"],
                             structure=x["structure"], definition=x["definition"],
                             exemples=" | ".join(x["exemples"]), piege=x["piege"]))
    listes = io.StringIO()
    w = ecrivain_csv(listes, lineterminator="\r\n")
    w.writerow(COLONNES_LISTES)
    for lc, l in sorted(c["listes"].items()):
        for qc, q in sorted(l["qualificatifs"].items(), key=lambda kv: kv[1]["rang"]):
            w.writerow([_neutre(x) for x in (lc, l["libelle"], qc, q["libelle"],
                                             q["definition"])])
    return sortie.getvalue(), listes.getvalue()


def archive(conn: sqlite3.Connection, version_id: int) -> bytes:
    """Le zip du réexport : les deux CSV, en UTF-8 AVEC BOM (pour qu'un tableur lise les
    accents), sous leurs noms d'import (`NOMS_FICHIERS`)."""
    entrees, listes = exporter(conn, version_id)
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(NOMS_FICHIERS[0], "﻿" + entrees)
        z.writestr(NOMS_FICHIERS[1], "﻿" + listes)
    return tampon.getvalue()


# --------------------------------------------------------------------------- #
# Le classeur — le tableur EN MOTS, identifiants compris (gabarit du 2026-11-03)
# --------------------------------------------------------------------------- #
def contenu_d_exemple() -> dict | None:
    """Le contenu du modèle FICTIF (`config.GRILLE_DU_BAC`), pour la feuille d'exemple du
    classeur ; None s'il ne se lit pas — le classeur se produit sans exemple."""
    import config
    try:
        with open(config.GRILLE_DU_BAC, encoding="utf-8-sig", newline="") as e,                 open(config.GRILLE_DU_BAC_LISTES, encoding="utf-8-sig", newline="") as li:
            return lire(e, li, porte_sur=config.GRILLE_DU_BAC_PORTE_SUR)["contenu"]
    except (OSError, ValueError, csv.Error):
        return None


def classeur(conn: sqlite3.Connection, version_id: int) -> bytes:
    """Le classeur `.xlsx` d'une version (`grille_tableur.ecrire_classeur`) : sa
    déclaration, ses entrées et ses listes EN MOTS, identifiants compris, et l'exemple.
    Relu par l'import, il rend la même empreinte."""
    v = grilles.version_par_id(conn, version_id)
    g = conn.execute("SELECT nom, ouverte, identifiant FROM grille WHERE id = ?",
                     (v["grille_id"],)).fetchone()
    # D'où vient le classeur (v40) : réimporté comme grille neuve, il en fera une dérivée.
    origine = ({"identifiant": g["identifiant"], "nom": g["nom"], "version": v["numero"]}
               if g["identifiant"] else None)
    return grille_tableur.ecrire_classeur(
        grilles.contenu(conn, version_id), nom=g["nom"], ouverte=bool(g["ouverte"]),
        porte_sur=v["cible"], note=v["note"], exemple=contenu_d_exemple(), origine=origine)
