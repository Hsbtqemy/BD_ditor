"""Une grille s'écrit dans un TABLEUR, BD_ditor la vérifie et la garde (ANN-7, tranche 1 ;
cadrage R3, tranché par Hugo le 2026-10-14 et le 2026-10-25 ; le gabarit et le bilan, tranchés
sur maquette le 2026-11-03).

Cœur partagé, sans I/O propre — le patron de `lexique_import` : il reçoit des FLUX de texte
et une CONNEXION, l'appelant ouvre les fichiers et tient la transaction. Deux enveloppes : `tools/importer_grille.py` et
`POST /api/projets/{id}/grilles/import`.

Le FORMAT — deux CSV point-virgule, UTF-8 avec ou sans BOM, en-tête obligatoire, lus par NOM
de colonne — a deux sortes de mots, que `grille_tableur` décrit et que ce module lit toutes
deux : des colonnes MACHINE (`cle`, `forme`, `libelle`…), ou les titres du gabarit, qui sont
des QUESTIONS (« 4. Ce qu'on choisit »), aux réponses EN MOTS (« une variante », « la case »).
Les deux se mêlent : un titre ou une valeur se lit d'un côté ou de l'autre. `docs/import-grille.md` le dit pour qui remplit le tableur.

1. Les entrées : une ligne par ENTRÉE, et une ligne par VARIANTE. Une ligne de variante
   répète la `cle` de son entrée — ou la laisse vide, et appartient alors à l'entrée du
   DESSUS —, porte son libellé (`variante`), et laisse vides les colonnes propres à
   l'entrée, ou y recopie exactement celles de l'entrée.
2. Les listes de qualificatifs, facultatives : une ligne par qualificatif.
3. La DÉCLARATION (nom, ouverte ou fermée, « Porte sur », note) : en arguments de l'outil, en
   champs du formulaire de la route.

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
avertissements) et « Ce qui va naître ».
"""
from __future__ import annotations

import csv
import io
import sqlite3
import zipfile

import grille_tableur
import grilles
from grille_tableur import FormatInvalide  # noqa: F401 — ré-exportée
from grilles import CARDINALITES, FORMES, propre

COLONNES = ("cle", "rubrique", "rubrique_cle", "forme", "libelle", "variante_cle",
            "variante", "structure", "definition", "exemples", "piege", "liste",
            "precision", "lien", "cible", "cardinalite")
OBLIGATOIRES = ("forme", "libelle")
# Les colonnes PROPRES à une entrée : vides sur une ligne de variante, ou recopiées.
COLONNES_DE_L_ENTREE = ("rubrique", "rubrique_cle", "forme", "libelle", "liste",
                        "precision", "lien", "cible", "cardinalite")
COLONNES_LISTES = ("liste_cle", "liste", "cle", "libelle", "definition")
SEP_RUBRIQUE = ">"
SEP_EXEMPLES = "|"
NOMS_FICHIERS = ("grille-rubriques-entrees.csv", "grille-listes-qualificatifs.csv")
NOMS_PAR_DEFAUT = ("entrées", "listes")


class Refus(Exception):
    """L'import ne se fait pas : `statut` (le code HTTP qu'une route rendrait), un message,
    les anomalies quand c'est le tableur qui est refusé, et le `bilan` quand il y en a un —
    le verdict, « À savoir »."""

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
    et la `question` telle que le gabarit la pose, ce qui ne va pas (`probleme`) et ce qu'il
    faut faire (`a_faire`), en mots."""
    titres = grille_tableur.TITRES_LISTES if listes else grille_tableur.TITRES
    return {"code": code, "fichier": fichier, "ligne": ligne, "cle": cle, "colonne": colonne,
            "question": titres.get(colonne) if colonne else None, "probleme": probleme,
            "a_faire": a_faire}


def _complete(f: dict) -> dict:
    """Une faute venue du lecteur d'une feuille : toutes ses clés."""
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


class _Identifiants:
    """Les identifiants qui MANQUENT, reçus du NOM (ANN-7, tranché le 2026-11-03 : la colonne
    grise du gabarit peut être vide). Règle, dans cet ordre :

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
    """Valide un tableur déjà découpé en feuilles (`lire` pour les CSV) — cf. `lire`."""
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
    elif not cible_version:
        anomalies.append(_faute(
            "porte_sur_manque", "« Porte sur » manque : sur quoi la grille se pose-t-elle ?",
            "déclarez-le à l'import ("
            + " · ".join(grilles.CIBLES) + ")", colonne="porte_sur", **ou_porte_sur))

    # -- Les entrées.
    nom_e, entete_e, brutes_e = tableur["entrees"]
    lignes = _par_colonne(nom_e, entete_e, brutes_e, COLONNES, listes=False,
                          obligatoires=OBLIGATOIRES, anomalies=anomalies)
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
            anomalies.append(_faute(
                "forme_inconnue", f"la réponse « {l['forme'] or ''} » n'est pas une forme",
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
            "réexportez la grille après l'import : le tableur portera ses identifiants"))
    resultat = {"anomalies": anomalies, "avertissements": avert,
                "identifiants_deduits": deduits}
    if anomalies:
        return {"contenu": None, **resultat}
    return {"contenu": {"cible": grilles.ecrire_cibles(cible_version), "rubriques": rubriques,
                        "entrees": entrees, "listes": listes}, **resultat}


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
    grille d'`avant`)."""
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
    """Le VERDICT en tête du bilan : un état stable (`refuse`, `aucun_changement`,
    `importable`, `importe`) et sa phrase."""
    n = compte.get("n", 0)
    phrases = {
        "refuse": f"{n} faute{'s' if n > 1 else ''} à corriger : rien n'est importé tant "
                  "qu'il en reste une.",
        "aucun_changement": "Le fichier est juste, et la version en place porte déjà ce "
                            "contenu : rien n'est écrit.",
        "importable": "Le fichier est juste : l'import peut se faire.",
        "importe": "Le fichier est juste, et la grille est importée.",
    }
    return {"etat": etat, **compte, "phrase": phrases[etat]}


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
    """Les lignes du plan d'une version, depuis un contenu normalisé."""
    conn.executemany(
        "INSERT INTO grille_rubrique (version_id, cle, libelle, parent_cle, rang) "
        "VALUES (?, ?, ?, ?, ?)",
        [(vid, k, r["libelle"], r["parent_cle"], r["rang"]) for k, r in c["rubriques"].items()])
    for k, e in c["entrees"].items():
        conn.execute(
            "INSERT INTO grille_entree (version_id, cle, rubrique_cle, rang, forme, libelle, "
            "definition, structure, piege, precision, lien, cible, cardinalite, liste_cle, "
            "retiree) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (vid, k, e["rubrique_cle"], e["rang"], e["forme"], e["libelle"], e["definition"],
             e["structure"], e["piege"], e["precision"], int(bool(e["lien"])), e["cible"],
             e["cardinalite"], e["liste_cle"], int(bool(e.get("retiree")))))
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
    """Retire les lignes du plan d'une version (un brouillon qu'on remplace)."""
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


def tableur_de(flux_entrees, flux_listes=None, *, noms=NOMS_PAR_DEFAUT) -> dict:
    """Le tableur à lire, découpé en feuilles : les deux CSV."""
    return {"entrees": (noms[0], *grille_tableur.feuille_csv(flux_entrees)),
            "listes": (noms[1], *grille_tableur.feuille_csv(flux_listes))
            if flux_listes is not None else None}


def importer(conn: sqlite3.Connection, *, projet_id: int, flux_entrees, flux_listes=None,
             grille_id: int | None = None, nom: str | None = None, ouverte: bool = False,
             porte_sur: str | None = None, note: str | None = None, par=None,
             a_blanc: bool = False, noms=NOMS_PAR_DEFAUT) -> dict:
    """Importe un tableur comme version d'une grille — neuve (`nom`), ou suivante d'une grille
    existante de ce projet (`grille_id`). Le droit de l'appelant est vérifié AVANT (gérer le
    projet) ; ici, les règles du modèle :

    - une grille FERMÉE a au plus un brouillon : réimporter le REMPLACE ; si la dernière
      version est publiée, un brouillon neuf naît, au numéro suivant — sauf si son empreinte
      est celle de la version publiée, ou du brouillon en place : « aucun changement » ;
    - une grille OUVERTE n'a qu'une version, `vivante`, née au premier import ; elle
      s'enrichit EN POSANT (G14) — la réimporter avec un autre contenu est refusé (409,
      option la plus fermée, à trancher : remplacer écraserait les entrées nées en posant).

    `a_blanc` : rend le bilan sans rien écrire. Lève `Refus` (statut, message, anomalies,
    bilan), `FormatInvalide` sur un en-tête. Ne commite pas ; écrit au journal
    sous `grille` (sauf à blanc). Rend `{grille_id, version: {numero, etat} | None, ecrit,
    aucun_changement, verdict, a_savoir, va_naitre, bilan, compare_a, declaration,
    identifiants_deduits}`."""
    import journal                               # import paresseux : le cœur reste léger
    tableur = tableur_de(flux_entrees, flux_listes, noms=noms)
    g = None
    if grille_id is not None:
        g = conn.execute("SELECT * FROM grille WHERE id = ? AND projet_id = ?",
                         (grille_id, projet_id)).fetchone()
        if g is None:
            raise Refus(404, f"Grille {grille_id} introuvable dans ce projet.")
        if g["retiree_le"]:
            raise Refus(409, "Cette grille est retirée : on ne lui importe plus de version.")
        ouverte = bool(g["ouverte"])
    else:
        nom = propre(nom)
        if not nom:
            raise Refus(422, "Une grille neuve a besoin d'un nom.")
        if nom_pris(conn, projet_id, nom):
            raise Refus(409, f"Une grille de ce projet s'appelle déjà « {nom} » : importez "
                             "une version suivante de celle-ci, ou choisissez un autre nom.")
    reference = None                          # la version à laquelle on compare
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
    lu = lire_tableur(tableur, porte_sur=porte_sur, reference=reference_ids)
    anomalies = lu["anomalies"]
    a_savoir = lu["avertissements"]
    commun = {"declaration": {"nom": nom, "ouverte": bool(ouverte), "note": note,
                              "porte_sur": porte_sur},
              "identifiants_deduits": lu["identifiants_deduits"]}
    if anomalies:
        raise Refus(422, f"Le tableur est refusé : {len(anomalies)} anomalie(s). Rien n'est "
                         "importé.", anomalies,
                    {"verdict": verdict("refuse", n=len(anomalies)), "a_savoir": a_savoir,
                     **commun})
    c = lu["contenu"]
    b = bilan(conn, g["id"] if g is not None else None, avant, c)
    emp = grilles.empreinte(c)
    brouillon = (grilles.derniere_version(conn, g["id"], grilles.ETAT_BROUILLON)
                 if g is not None else None)
    resultat = {"grille_id": g["id"] if g is not None else None, "version": None,
                "ecrit": False, "aucun_changement": False, "bilan": b,
                "va_naitre": va_naitre(avant, c),
                "compare_a": reference["numero"] if reference is not None else None,
                "a_savoir": a_savoir, **commun}
    deja = [v for v in (reference, brouillon) if v is not None and v["empreinte"] == emp]
    if deja:
        resultat["aucun_changement"] = True
        resultat["version"] = {"numero": deja[0]["numero"], "etat": deja[0]["etat"]}
        resultat["verdict"] = verdict("aucun_changement")
        return resultat
    if ouverte and g is not None and reference is not None:
        raise Refus(409, "Une grille ouverte s'enrichit en posant : la réimporter avec un "
                         "autre contenu remplacerait les entrées nées en posant. Rien n'est "
                         "importé.")
    if a_blanc:
        resultat["verdict"] = verdict("importable")
        if brouillon is not None:
            resultat["version"] = {"numero": brouillon["numero"], "etat": brouillon["etat"],
                                   "remplace": True}
        return resultat
    if g is None:
        gid = conn.execute("INSERT INTO grille (projet_id, nom, ouverte, cree_par) "
                           "VALUES (?, ?, ?, ?)", (projet_id, nom, int(bool(ouverte)),
                                                   par)).lastrowid
        journal.journaliser(conn, "creation", "grille", gid,
                            apres={"projet_id": projet_id, "nom": nom,
                                   "ouverte": bool(ouverte)})
        resultat["grille_id"] = gid
    else:
        gid = g["id"]
    etat = grilles.ETAT_VIVANTE if ouverte else grilles.ETAT_BROUILLON
    en_place = brouillon
    if en_place is not None:
        effacer_plan(conn, en_place["id"])
        conn.execute("UPDATE grille_version SET cible = ?, note = ?, empreinte = ?, "
                     "importee_par = ?, importee_le = datetime('now') WHERE id = ?",
                     (c["cible"], note, emp, par, en_place["id"]))
        ecrire_plan(conn, en_place["id"], c)
        numero = en_place["numero"]
    else:
        derniere = grilles.derniere_version(conn, gid)
        numero = (derniere["numero"] + 1) if derniere is not None else 1
        ecrire_version(conn, gid, c, numero=numero, etat=etat, note=note, par=par)
    journal.journaliser(conn, "modification", "grille", gid,
                        apres={"import": {"numero": numero, "etat": etat, "empreinte": emp,
                                          "remplace": en_place is not None}})
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


def version_activable(conn: sqlite3.Connection, grille_id: int):
    """La version qu'on ACTIVERAIT sans en dire le numéro : la vivante d'une grille ouverte,
    la publiée la plus récente d'une fermée ; None s'il n'y en a pas (un brouillon seul)."""
    g = conn.execute("SELECT ouverte FROM grille WHERE id = ?", (grille_id,)).fetchone()
    if g is None:
        return None
    return grilles.derniere_version(
        conn, grille_id, grilles.ETAT_VIVANTE if g["ouverte"] else grilles.ETAT_PUBLIEE)


def activer(conn: sqlite3.Connection, *, projet_id: int, grille_id: int, numero: int,
            par=None) -> bool:
    """ACTIVE la grille sur le projet dans la version `numero` (R4) — publiée pour une
    grille fermée, vivante pour une ouverte. Un projet n'active que SES grilles (le
    catalogue n'existe pas) ; une grille retirée ne s'active plus ; changer la version
    d'une activation qui porte des relevés est la MONTÉE DE VERSION, refusée — qu'on
    l'active par-dessus ou qu'on désactive d'abord pour réactiver ensuite. Lève `Refus` ;
    rend True si l'activation s'est écrite, False si elle était déjà celle-là."""
    import database                              # import paresseux, cf. `importer`
    import journal
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
    if conn.execute("SELECT 1 FROM releve WHERE grille_id = ? AND version_id <> ? LIMIT 1",
                    (grille_id, v["id"])).fetchone():
        raise Refus(409, "Des relevés sont posés avec cette grille : changer de version est "
                         "une montée de version, qui n'existe pas encore. Rien n'est changé.")
    conn.execute("INSERT INTO projet_grille (projet_id, grille_id, version_id, active_par) "
                 "VALUES (?, ?, ?, ?) ON CONFLICT(projet_id, grille_id) DO UPDATE SET "
                 "version_id = excluded.version_id, active_par = excluded.active_par, "
                 "active_le = datetime('now')", (projet_id, grille_id, v["id"], par))
    journal.journaliser(conn, "lien", "grille", grille_id,
                        avant={"projet_id": projet_id, "version": act["numero"]}
                        if act else None,
                        apres={"projet_id": projet_id, "version": v["numero"]})
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
    Réimporté tel quel, il rend la même empreinte (`tests/test_grilles.py`)."""
    c = grilles.contenu(conn, version_id)

    def ligne(**valeurs):
        return [_neutre(valeurs.get(col)) for col in COLONNES]
    sortie = io.StringIO()
    w = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    w.writerow(COLONNES)
    for cle_, e in sorted(c["entrees"].items(), key=lambda kv: kv[1]["rang"]):
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
    w = csv.writer(listes, delimiter=";", lineterminator="\r\n")
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
