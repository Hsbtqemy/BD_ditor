"""Les RELEVÉS — ce qu'on pose avec une grille (ANN-7, tranche 1 ; cadrage R5 à R7, R9).

Un relevé est une entrée d'une version de grille posée sur UNE cible : des mots d'une zone de
texte, une région entière, ou la planche (la surface). Ce module en porte les routes, sans
écran — la page Annotation (tranche 2) les consommera (R13).

Le découpage en mots d'abord (R6, G11) : `GET /api/regions/{id}/mots` rend celui de l'outil
(`mots.py`), le seul — la page Annotation dessine depuis lui, elle ne découpe jamais.

Les gardes de la POSE (R5), dans cet ordre, chacune avec son refus :
1. la cible s'atteint EN ÉCRITURE par l'accesseur gardé — 404 sinon ;
2. la grille est ACTIVE dans le projet de l'album — 409 nommé ;
3. la version envoyée est celle de l'activation — 409 nommé (l'écran a vu une autre version) ;
4. l'entrée existe dans cette version et n'est pas retirée — 422 ;
5. la cible convient à l'entrée — le type de la région, des mots d'une zone de texte, la
   planche ; l'entité est refusée tant que les personnages n'ont pas leur étage de projet
   (G3) — 422 nommé ;
6. la forme est respectée — une variante de cette entrée, des qualificatifs de SA liste,
   rien de cela pour une simple ; une précision seulement si l'entrée l'attend — 422 ;
7. le lien désigne une région du MÊME ALBUM (G4) — 404 sinon, qui ne dit pas si elle existe
   ailleurs ;
puis la CARDINALITÉ (Q6) : un second relevé d'une entrée `une` sur la même cible est refusé
par un 409 qui rend le relevé existant — relu sous le verrou d'écriture, et tenu par l'index
unique partiel de la base.

La CONCURRENCE (R9, G1) : chaque valeur unique d'un relevé — la variante, les qualificatifs
(comme UN ensemble), la précision, le lien, le passage — s'écrit avec `vu`, la valeur que
l'écran avait vue ; une valeur périmée reçoit le 409 de CONC-3, mot pour mot. Sans colonne de
version : la valeur vue tient ce que Q7 demande, sans les deux défauts que CONC-3 a écrits
contre une colonne.

L'ÉTAT ne s'écrit pas (G2) : la vue `releves_effectifs` le dérive — « à revoir » (un mot du
passage perdu, le texte de la zone changé depuis l'ancrage, la région liée disparue, un type
de région qui ne convient plus, une entrée absente), « à compléter » (une précision ou un
lien attendus et absents), « normal » sinon.

Le JOURNAL (R10) : deux cibles, sur le patron des annotations — `releve` (`cible_id` = la
RÉGION du relevé) et `releve_planche` (`cible_id` = la PLANCHE) ; l'identifiant du relevé
voyage dans la charge. Retenues de toute sortie ; elles COMPTENT dans les rangs des
pseudonymes (G10).
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

import autorisation
import conflit
import grilles
import journal
import mots
from database import cle_tag, noms_lisibles, projet_d_album
from socle import _get_planche, _get_region, db, portee_courante

router = APIRouter()

# Les valeurs uniques d'un relevé que garde `vu` (R9) — la clé du corps de la requête, qui
# est aussi celle de la charge au journal.
CHAMPS_VUS = ("variante_cle", "qualificatifs", "precision", "lien_region_id", "mots")
LONGUEUR_PRECISION = 500
_MOTIF_INACTIVE = ("Cette grille n'est pas active dans le projet de cet album : ses relevés "
                   "se lisent, ils ne s'écrivent plus.")


# --------------------------------------------------------------------------- #
# Le découpage
# --------------------------------------------------------------------------- #
@router.get("/api/regions/{region_id}/mots")
def mots_de_la_region(region_id: int, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Le découpage en mots du texte d'une région : `{region_id, texte, mots: [{rang, forme,
    debut, fin}]}` — `texte[debut:fin] == forme`. À qui LIT la région (404 sinon). Une
    région sans texte n'a aucun mot. Sans moteur de langue, rien ne change : le découpage
    n'en dépend pas (la raison de la décision du 2026-10-14)."""
    r = _get_region(conn, portee, region_id)
    texte = r["ocr_texte"] or ""
    return {"region_id": region_id, "texte": texte, "mots": mots.decouper(texte)}


# --------------------------------------------------------------------------- #
# Ce qu'est un relevé, pour le journal et pour l'écran
# --------------------------------------------------------------------------- #
def cible_du_journal(releve) -> tuple[str, int]:
    """La cible au journal d'un relevé (R10) : sa région, ou sa planche."""
    if releve["region_id"] is not None:
        return "releve", releve["region_id"]
    return "releve_planche", releve["planche_id"]


def journaliser_releve(conn, type_: str, releve, **charges) -> int:
    """Écrit un acte sur un relevé (ou sur sa zone : un doute, une passe) sous sa cible — la
    RÉGION (`releve`) ou la PLANCHE (`releve_planche`). Deux appels LITTÉRAUX : le cliquet du
    journal (`test_journal_publie_par_decision`) relève les cibles par AST, et une cible
    calculée lui échapperait."""
    if releve["region_id"] is not None:
        return journal.journaliser(conn, type_, "releve", releve["region_id"], **charges)
    return journal.journaliser(conn, type_, "releve_planche", releve["planche_id"], **charges)


def qualificatifs_de(conn, releve_id: int) -> list:
    return [q[0] for q in conn.execute(
        "SELECT qualificatif_cle FROM releve_qualificatif WHERE releve_id = ? "
        "ORDER BY qualificatif_cle", (releve_id,))]


def instantane(conn: sqlite3.Connection, releve_id: int, *, profond: bool = False) -> dict:
    """L'état d'un relevé, pour le journal : ses colonnes, ses qualificatifs (triés), son
    passage — `mots` (les rangs, dans l'ordre) et `formes` —, et, `profond`, ses doutes et
    leur fil (une suppression : Ctrl+Z les rend). `releve_id` dans la charge : la cible au
    journal est la région ou la planche, que plusieurs relevés partagent."""
    r = conn.execute("SELECT * FROM releve WHERE id = ?", (releve_id,)).fetchone()
    if r is None:
        return {}
    passage = conn.execute("SELECT position, rang, forme FROM releve_mot WHERE releve_id = ? "
                           "ORDER BY position", (releve_id,)).fetchall()
    out = {"releve_id": r["id"], "region_id": r["region_id"], "planche_id": r["planche_id"],
           "grille_id": r["grille_id"], "version_id": r["version_id"],
           "entree_cle": r["entree_cle"], "variante_cle": r["variante_cle"],
           "precision": r["precision"], "lien_region_id": r["lien_region_id"],
           "lien_texte": r["lien_texte"], "texte_ancre": r["texte_ancre"], "une": r["une"],
           "origine_id": r["origine_id"], "auteur": r["auteur"], "cree_le": r["cree_le"],
           "modifie_par": r["modifie_par"], "modifie_le": r["modifie_le"],
           "qualificatifs": qualificatifs_de(conn, releve_id),
           "mots": [m["rang"] for m in passage], "formes": [m["forme"] for m in passage]}
    if profond:
        out["doutes"] = [
            {**dict(d), "messages": [dict(m) for m in conn.execute(
                "SELECT * FROM doute_message WHERE doute_id = ? ORDER BY id", (d["id"],))]}
            for d in conn.execute("SELECT * FROM doute WHERE releve_id = ? ORDER BY id",
                                  (releve_id,))]
    return out


def collectifs(conn, logins) -> set:
    """Ceux de ces logins qui sont des comptes PARTAGÉS (AUTH-6) : l'écran le dit, sans rien
    inventer de qui tape derrière."""
    voulus = sorted({x for x in logins if x})
    if not voulus:
        return set()
    return {r[0] for r in conn.execute(
        f"SELECT login FROM utilisateur WHERE nature = 'collectif' AND login IN "
        f"({', '.join('?' * len(voulus))})", voulus)}


_CAUSES = ("mot_perdu", "texte_change", "lien_perdu", "type_change", "entree_absente",
           "precision_manquante", "lien_manquant")


def vue_releve(conn, r, *, modifiable: bool, noms: dict, partages: set,
               doute=None) -> dict:
    """Un relevé tel que l'écran le lit (R13) — depuis une ligne de `releves_effectifs`."""
    passage = conn.execute("SELECT position, rang, forme FROM releve_mot WHERE releve_id = ? "
                           "ORDER BY position", (r["id"],)).fetchall()
    actuel = None
    if r["region_id"] is not None and passage and r["texte_change"]:
        # Le texte a changé depuis l'ancrage sans que tous les mots se retrouvent : l'écran
        # lit où chacun est AUJOURD'HUI (null : perdu) — dérivé, jamais écrit.
        texte = conn.execute("SELECT ocr_texte FROM regions WHERE id = ?",
                             (r["region_id"],)).fetchone()
        correspondance = mots.aligner(r["texte_ancre"], texte[0] if texte else None)
        actuel = {m["position"]: (correspondance.get(m["rang"]) if m["rang"] is not None
                                  else None) for m in passage}
    return {
        "id": r["id"], "region_id": r["region_id"], "planche_id": r["planche_id"],
        "grille_id": r["grille_id"], "version_id": r["version_id"],
        "entree_cle": r["entree_cle"], "variante_cle": r["variante_cle"],
        "qualificatifs": qualificatifs_de(conn, r["id"]), "precision": r["precision"],
        "mots": [{"position": m["position"], "rang": m["rang"], "forme": m["forme"],
                  **({"rang_actuel": actuel[m["position"]]} if actuel is not None else {})}
                 for m in passage],
        "lien": None if r["lien_region_id"] is None else {
            "region_id": r["lien_region_id"], "existe": not r["lien_perdu"],
            **({"texte": r["lien_texte"]} if r["lien_perdu"] else {})},
        "etat": r["etat"], "causes": [c for c in _CAUSES if r[c]], "une": bool(r["une"]),
        "auteur": r["auteur"], "auteur_nom": noms.get(r["auteur"]) if r["auteur"] else None,
        "collectif": r["auteur"] in partages, "cree_le": r["cree_le"],
        "modifie_par": r["modifie_par"], "modifie_le": r["modifie_le"],
        "recopie": r["origine_id"] is not None, "modifiable": modifiable, "doute": doute}


def album_du_releve(conn, r) -> int:
    if r["region_id"] is not None:
        return conn.execute("SELECT p.album_id FROM regions g JOIN planches p "
                            "ON p.id = g.planche_id WHERE g.id = ?",
                            (r["region_id"],)).fetchone()[0]
    return conn.execute("SELECT album_id FROM planches WHERE id = ?",
                        (r["planche_id"],)).fetchone()[0]


def doute_ouvert(conn, releve_id: int, noms: dict, partages: set):
    """Le doute OUVERT d'un relevé et son fil, ou None (R7) — chaque message signé, daté, et
    `collectif` quand il vient d'un compte partagé."""
    d = conn.execute("SELECT * FROM doute WHERE releve_id = ? AND leve_le IS NULL",
                     (releve_id,)).fetchone()
    if d is None:
        return None
    return {"id": d["id"], "ouvert_par": d["ouvert_par"], "ouvert_le": d["ouvert_le"],
            "messages": [{"id": m["id"], "auteur": m["auteur"],
                          "auteur_nom": noms.get(m["auteur"]) if m["auteur"] else None,
                          "collectif": m["auteur"] in partages, "date": m["date"],
                          "texte": m["texte"]}
                         for m in conn.execute("SELECT * FROM doute_message WHERE doute_id = ? "
                                               "ORDER BY id", (d["id"],))]}


def vues(conn, portee, lignes) -> list:
    """Les vues de plusieurs relevés, noms lisibles et comptes partagés lus en une fois, et
    `modifiable` : la grille active dans la version du relevé, et l'album écrit par
    l'appelant."""
    ids = [r["id"] for r in lignes]
    auteurs = [r["auteur"] for r in lignes] + [r["modifie_par"] for r in lignes]
    if ids:
        auteurs += [m[0] for m in conn.execute(
            f"SELECT m.auteur FROM doute_message m JOIN doute d ON d.id = m.doute_id "
            f"WHERE d.releve_id IN ({', '.join('?' * len(ids))})", ids)]
    noms = noms_lisibles(conn, auteurs)
    partages = collectifs(conn, auteurs)
    ecrit = {}
    sortie = []
    for r in lignes:
        album = album_du_releve(conn, r)
        if album not in ecrit:
            ou, params = portee.clause_album("a.id", ecriture=True)
            ecrit[album] = conn.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ou}",
                                        (album, *params)).fetchone() is not None
        act = grilles.activation(conn, projet_d_album(conn, album), r["grille_id"])
        modifiable = ecrit[album] and act is not None and act["version_id"] == r["version_id"]
        sortie.append(vue_releve(conn, r, modifiable=modifiable, noms=noms, partages=partages,
                                 doute=doute_ouvert(conn, r["id"], noms, partages)))
    return sortie


def vue_de(conn, portee, releve_id: int) -> dict:
    return vues(conn, portee, [conn.execute("SELECT * FROM releves_effectifs WHERE id = ?",
                                            (releve_id,)).fetchone()])[0]


# --------------------------------------------------------------------------- #
# Les gardes
# --------------------------------------------------------------------------- #
def cible_ecrite(conn, portee, *, region_id=None, planche_id=None) -> dict:
    """La cible d'un relevé ou d'une passe, atteinte EN ÉCRITURE par l'accesseur gardé (404
    sinon) : `{"region": …|None, "planche_id", "album_id"}`."""
    if region_id is not None:
        g = _get_region(conn, portee, region_id, ecriture=True)
        album = conn.execute("SELECT album_id FROM planches WHERE id = ?",
                             (g["planche_id"],)).fetchone()[0]
        return {"region": g, "planche_id": g["planche_id"], "album_id": album}
    p = _get_planche(conn, portee, planche_id, ecriture=True)
    return {"region": None, "planche_id": p["id"], "album_id": p["album_id"]}


def activation_ou_409(conn, album_id: int, grille_id: int):
    """L'activation de la grille dans le projet de l'album (R5, garde 2) — 409 nommé sinon."""
    act = grilles.activation(conn, projet_d_album(conn, album_id), grille_id)
    if act is None:
        raise HTTPException(409, _MOTIF_INACTIVE)
    return act


def _qualifs_de_la_liste(conn, version_id, entree) -> set:
    if not entree["liste_cle"]:
        return set()
    return {q[0] for q in conn.execute(
        "SELECT cle FROM grille_qualificatif WHERE version_id = ? AND liste_cle = ?",
        (version_id, entree["liste_cle"]))}


def _forme(conn, version_id, entree, variante_cle, qualificatifs) -> None:
    """La forme respectée (R5, garde 6) — 422 sinon."""
    forme = entree["forme"]
    if forme == "variantes":
        if not variante_cle:
            raise HTTPException(422, f"« {entree['libelle']} » est à variantes : choisissez-en "
                                     "une.")
        if conn.execute("SELECT 1 FROM grille_variante WHERE version_id = ? AND entree_cle = ? "
                        "AND cle = ?", (version_id, entree["cle"], variante_cle)).fetchone() \
                is None:
            raise HTTPException(422, f"« {variante_cle} » n'est pas une variante de "
                                     f"« {entree['libelle']} ».")
    elif variante_cle:
        raise HTTPException(422, f"« {entree['libelle']} » n'a pas de variantes.")
    if forme == "qualificatifs":
        inconnus = sorted(set(qualificatifs) - _qualifs_de_la_liste(conn, version_id, entree))
        if inconnus:
            raise HTTPException(422, f"Hors de la liste de « {entree['libelle']} » : "
                                     f"{', '.join(inconnus)}.")
    elif qualificatifs:
        raise HTTPException(422, f"« {entree['libelle']} » ne prend pas de qualificatifs.")


def _precision(entree, precision):
    precision = grilles.propre(precision)
    if precision is not None:
        if entree["precision"] is None:
            raise HTTPException(422, f"« {entree['libelle']} » n'attend pas de précision.")
        if len(precision) > LONGUEUR_PRECISION:
            raise HTTPException(422, f"Une précision tient en {LONGUEUR_PRECISION} caractères.")
    return precision


def _lien(conn, entree, lien_region_id, cible: dict):
    """Le lien (R5, garde 7, G4) : une région du MÊME ALBUM — 404 sinon, le même qu'une
    région qui n'existe pas, pour ne rien dire de ce qui vit ailleurs. Rend `(id, texte)` :
    le texte de la région désignée AU MOMENT DU LIEN, gardé pour le jour où elle disparaît."""
    if lien_region_id is None:
        return None, None
    if not entree["lien"]:
        raise HTTPException(422, f"« {entree['libelle']} » ne désigne pas d'autre région.")
    if cible["region"] is not None and lien_region_id == cible["region"]["id"]:
        raise HTTPException(422, "Un relevé ne se lie pas à sa propre région.")
    g = conn.execute("SELECT g.ocr_texte FROM regions g JOIN planches p ON p.id = g.planche_id "
                     "WHERE g.id = ? AND p.album_id = ?",
                     (lien_region_id, cible["album_id"])).fetchone()
    if g is None:
        raise HTTPException(404, f"Région {lien_region_id} introuvable")
    return lien_region_id, g[0]


def _passage(entree, cibles, cible: dict, rangs):
    """La cible convient-elle (R5, garde 5) ? Et, pour des mots, le passage : `[(rang,
    forme)]` dans l'ordre du texte, et le texte de l'ancrage. 422 nommé sinon."""
    pose = grilles.sorte_de_pose(cibles)
    if pose is None:
        raise HTTPException(422, "Cette entrée ne dit pas sur quoi elle se pose.")
    if pose == "entite":
        raise HTTPException(422, "Cette entrée se pose sur l'entité du registre des "
                                 "personnages : aucun relevé ne s'y pose avant l'étage de "
                                 "projet des personnages (G3).")
    region = cible["region"]
    if pose == "planche":
        if region is not None:
            raise HTTPException(422, f"« {entree['libelle']} » se pose sur la planche, pas sur "
                                     "une région.")
        return [], None
    if region is None:
        raise HTTPException(422, f"« {entree['libelle']} » se pose sur une région, pas sur la "
                                 "planche.")
    if not grilles.type_convient(region["type"], cibles):
        attendu = ", ".join(grilles.TYPES_TEXTE) if pose == "mots" else ", ".join(cibles)
        raise HTTPException(422, f"« {entree['libelle']} » se pose sur : {attendu} ; cette "
                                 f"région est une {region['type']}.")
    if pose == "zone":
        if rangs:
            raise HTTPException(422, f"« {entree['libelle']} » se pose sur toute la zone, pas "
                                     "sur des mots.")
        return [], None
    if not rangs:
        raise HTTPException(422, f"« {entree['libelle']} » se pose sur des mots : désignez-en "
                                 "au moins un.")
    texte = region["ocr_texte"] or ""
    decoupe = mots.decouper(texte)
    hors = [x for x in rangs if not isinstance(x, int) or x < 0 or x >= len(decoupe)]
    if hors:
        raise HTTPException(422, f"Ces mots ne sont pas dans le texte de la zone : {hors}.")
    return [(x, decoupe[x]["forme"]) for x in sorted(set(rangs))], texte


def verifier_valeur(conn, releve, champ, vu, nouveau, actuel) -> None:
    """Le 409 de CONC-3 sur une valeur unique d'un relevé (R9), l'auteur cherché parmi les
    actes de CE relevé (`objet`) : sa région en porte peut-être d'autres."""
    table, cible_id = cible_du_journal(releve)
    try:
        conflit.verifier(conn, table, cible_id, champ, vu=vu, actuel=actuel, nouveau=nouveau,
                         objet=("releve_id", releve["id"]))
    except conflit.Perime as exc:
        raise HTTPException(409, exc.detail())


def _existant_une(conn, *, region_id, planche_id, grille_id, entree_cle):
    return conn.execute(
        "SELECT * FROM releve WHERE COALESCE(region_id, 0) = ? AND COALESCE(planche_id, 0) = ? "
        "AND grille_id = ? AND entree_cle = ? AND une = 1",
        (region_id or 0, planche_id or 0, grille_id, entree_cle)).fetchone()


def _refus_cardinalite(conn, existant) -> HTTPException:
    """Le 409 de la cardinalité `une` : il rend le relevé existant — l'écran montre le
    conflit, et « Remplacer par la mienne » modifie CE relevé, avec `vu` (R5)."""
    nom = (noms_lisibles(conn, [existant["auteur"]]).get(existant["auteur"])
           if existant["auteur"] else None)
    return HTTPException(409, {
        "message": "Cette entrée ne se pose qu'une fois sur cette cible, et elle y est déjà : "
                   "modifiez le relevé en place.",
        "releve_existant": {"id": existant["id"], "variante_cle": existant["variante_cle"],
                            "qualificatifs": qualificatifs_de(conn, existant["id"]),
                            "auteur": existant["auteur"], "auteur_nom": nom}})


# --------------------------------------------------------------------------- #
# Poser, modifier, retirer
# --------------------------------------------------------------------------- #
class NouvelleEntreeIn(BaseModel):
    libelle: str


class ReleveIn(BaseModel):
    region_id: Optional[int] = None
    planche_id: Optional[int] = None
    grille_id: int
    version: int
    entree_cle: Optional[str] = None
    nouvelle_entree: Optional[NouvelleEntreeIn] = None
    variante_cle: Optional[str] = None
    qualificatifs: list[str] = []
    precision: Optional[str] = None
    lien_region_id: Optional[int] = None
    mots: list[int] = []


def _entree_neuve(conn, grille_id: int, version, libelle: str):
    """Une entrée qui naît EN LA POSANT, dans la version vivante d'une grille OUVERTE (G14,
    le patron des tags libres) : sa `cle` dérive de son libellé (`database.cle_tag`), une
    entrée de même clé est reprise. Simple, sans rubrique ; sa cible est celle de la
    version. Au journal, sous la grille, et l'empreinte de la version suit."""
    libelle = grilles.propre(libelle)
    if not libelle:
        raise HTTPException(422, "Une entrée neuve a besoin d'un libellé.")
    cle = cle_tag(libelle)
    e = grilles.entree(conn, version["id"], cle)
    if e is not None:
        return e
    rang = conn.execute("SELECT COALESCE(MAX(rang), -1) + 1 FROM grille_entree "
                        "WHERE version_id = ?", (version["id"],)).fetchone()[0]
    conn.execute("INSERT INTO grille_entree (version_id, cle, rang, forme, libelle) "
                 "VALUES (?, ?, ?, 'simple', ?)", (version["id"], cle, rang, libelle))
    conn.execute("UPDATE grille_version SET empreinte = ? WHERE id = ?",
                 (grilles.empreinte(grilles.contenu(conn, version["id"])), version["id"]))
    journal.journaliser(conn, "modification", "grille", grille_id,
                        apres={"entree_neuve": {"version": version["numero"], "cle": cle,
                                                "libelle": libelle}})
    return grilles.entree(conn, version["id"], cle)


@router.post("/api/releves", status_code=201)
def poser_releve(payload: ReleveIn, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """POSE un relevé (R5). Les gardes sont dites en tête du module, dans leur ordre."""
    if (payload.region_id is None) == (payload.planche_id is None):
        raise HTTPException(422, "Un relevé se pose sur UNE cible : une région, ou la planche.")
    if (payload.entree_cle is None) == (payload.nouvelle_entree is None):
        raise HTTPException(422, "Nommez l'entrée (`entree_cle`), ou une entrée neuve.")
    conflit.verrouiller(conn)
    cible = cible_ecrite(conn, portee, region_id=payload.region_id,
                         planche_id=payload.planche_id)
    act = activation_ou_409(conn, cible["album_id"], payload.grille_id)
    if act["numero"] != payload.version:
        raise HTTPException(409, f"La grille est active dans sa version {act['numero']} ; "
                                 f"votre écran montre la version {payload.version}. "
                                 "Rechargez la page.")
    version = grilles.version_par_id(conn, act["version_id"])
    if payload.nouvelle_entree is not None:
        ouverte = conn.execute("SELECT ouverte FROM grille WHERE id = ?",
                               (payload.grille_id,)).fetchone()[0]
        if not ouverte or version["etat"] != grilles.ETAT_VIVANTE:
            raise HTTPException(422, "Une entrée ne naît en posant que dans une grille "
                                     "ouverte.")
        entree = _entree_neuve(conn, payload.grille_id, version,
                               payload.nouvelle_entree.libelle)
    else:
        entree = grilles.entree(conn, version["id"], payload.entree_cle)
        if entree is None or entree["retiree"]:
            raise HTTPException(422, f"« {payload.entree_cle} » n'est pas une entrée de cette "
                                     "version de la grille.")
    cibles = grilles.cibles_effectives(entree, version)
    passage, texte_ancre = _passage(entree, cibles, cible, payload.mots)
    _forme(conn, version["id"], entree, payload.variante_cle, payload.qualificatifs)
    precision = _precision(entree, payload.precision)
    lien_id, lien_texte = _lien(conn, entree, payload.lien_region_id, cible)
    une = grilles.cardinalite_effective(entree, cibles) == "une"
    if une:
        existant = _existant_une(conn, region_id=payload.region_id,
                                 planche_id=payload.planche_id, grille_id=payload.grille_id,
                                 entree_cle=entree["cle"])
        if existant is not None:
            raise _refus_cardinalite(conn, existant)
    try:
        rid = conn.execute(
            "INSERT INTO releve (region_id, planche_id, grille_id, version_id, entree_cle, "
            "variante_cle, precision, lien_region_id, lien_texte, texte_ancre, une, auteur) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (payload.region_id, payload.planche_id, payload.grille_id, version["id"],
             entree["cle"], payload.variante_cle or None, precision, lien_id, lien_texte,
             texte_ancre, int(une), portee.utilisateur)).lastrowid
    except sqlite3.IntegrityError:
        # La ceinture : l'index unique partiel de la cardinalité. Sous le verrou, la relecture
        # ci-dessus l'a déjà vu ; une base retouchée, ou un chemin qui oublierait le verrou,
        # tombe ici, jamais sur deux relevés.
        existant = _existant_une(conn, region_id=payload.region_id,
                                 planche_id=payload.planche_id, grille_id=payload.grille_id,
                                 entree_cle=entree["cle"])
        raise _refus_cardinalite(conn, existant)
    conn.executemany("INSERT INTO releve_mot (releve_id, position, rang, forme) "
                     "VALUES (?, ?, ?, ?)",
                     [(rid, i, rang, forme) for i, (rang, forme) in enumerate(passage)])
    conn.executemany("INSERT INTO releve_qualificatif (releve_id, qualificatif_cle) "
                     "VALUES (?, ?)", [(rid, q) for q in sorted(set(payload.qualificatifs))])
    releve = conn.execute("SELECT * FROM releve WHERE id = ?", (rid,)).fetchone()
    journaliser_releve(conn, "creation", releve, apres=instantane(conn, rid))
    conn.commit()
    return vue_de(conn, portee, rid)


class ReleveUpdate(BaseModel):
    variante_cle: Optional[str] = None
    qualificatifs: Optional[list[str]] = None
    precision: Optional[str] = None
    lien_region_id: Optional[int] = None
    mots: Optional[list[int]] = None
    vu: Optional[dict] = None


def releve_a_ecrire(conn, portee, releve_id: int):
    """Le relevé, sa cible atteinte EN ÉCRITURE (404 sinon, comme un relevé qui n'existe
    pas), et l'activation de sa grille dans la version où il a été posé (409 nommé sinon :
    une grille désactivée laisse ses relevés en lecture). Rend `(relevé, cible)`."""
    r = conn.execute("SELECT * FROM releve WHERE id = ?", (releve_id,)).fetchone()
    if r is None:
        raise HTTPException(404, f"Relevé {releve_id} introuvable")
    try:
        cible = cible_ecrite(conn, portee, region_id=r["region_id"], planche_id=r["planche_id"])
    except HTTPException as refus:
        if refus.status_code == 404:
            raise HTTPException(404, f"Relevé {releve_id} introuvable")
        raise
    act = activation_ou_409(conn, cible["album_id"], r["grille_id"])
    if act["version_id"] != r["version_id"]:
        raise HTTPException(409, _MOTIF_INACTIVE)
    return r, cible


@router.put("/api/releves/{releve_id}")
def modifier_releve(releve_id: int, payload: ReleveUpdate,
                    conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """MODIFIE les valeurs envoyées d'un relevé, et elles seules : sa variante, ses
    qualificatifs (UN ensemble), sa précision, son lien (`null` le retire), son passage
    (`mots` : les rangs dans le texte d'AUJOURD'HUI). `vu` porte, pour chacune, la valeur que
    l'écran avait vue (R9) : une valeur périmée reçoit le 409 de CONC-3. Mêmes gardes que la
    pose, sur la valeur neuve."""
    champs = payload.model_dump(exclude_unset=True, exclude={"vu"})
    vu = payload.vu or {}
    inconnus = set(vu) - set(CHAMPS_VUS)
    if inconnus:
        raise HTTPException(422, f"« vu » ne porte que {', '.join(CHAMPS_VUS)} : "
                                 f"{', '.join(sorted(inconnus))} refusé.")
    conflit.verrouiller(conn)
    r, cible = releve_a_ecrire(conn, portee, releve_id)
    if not champs:
        return vue_de(conn, portee, releve_id)
    version = grilles.version_par_id(conn, r["version_id"])
    entree = grilles.entree(conn, r["version_id"], r["entree_cle"])
    if entree is None:
        raise HTTPException(409, "L'entrée de ce relevé n'existe plus dans sa version : il se "
                                 "retire, il ne se modifie plus.")
    actuel = instantane(conn, releve_id)
    nouveau = {}
    if "variante_cle" in champs or "qualificatifs" in champs:
        variante = champs.get("variante_cle", r["variante_cle"])
        qualifs = sorted(set(champs.get("qualificatifs", actuel["qualificatifs"]) or []))
        _forme(conn, r["version_id"], entree, variante, qualifs)
        if "variante_cle" in champs:
            nouveau["variante_cle"] = variante or None
        if "qualificatifs" in champs:
            nouveau["qualificatifs"] = qualifs
    if "precision" in champs:
        nouveau["precision"] = _precision(entree, champs["precision"])
    lien_texte = None
    if "lien_region_id" in champs:
        lien_id, lien_texte = _lien(conn, entree, champs["lien_region_id"], cible)
        nouveau["lien_region_id"] = lien_id
    passage, texte_ancre = None, None
    if "mots" in champs:
        cibles = grilles.cibles_effectives(entree, version)
        if grilles.sorte_de_pose(cibles) != "mots":
            raise HTTPException(422, "Ce relevé ne porte pas sur des mots.")
        passage, texte_ancre = _passage(entree, cibles, cible, champs["mots"] or [])
        nouveau["mots"] = [rang for rang, _f in passage]
    for champ, valeur in nouveau.items():
        if champ in vu:
            verifier_valeur(conn, r, champ, vu[champ], valeur, actuel[champ])
    change = {c: v for c, v in nouveau.items() if v != actuel[c]}
    if "mots" in nouveau and texte_ancre != actuel["texte_ancre"]:
        change["mots"] = nouveau["mots"]       # le même rang dans un texte neuf : ré-ancré
    if not change:
        return vue_de(conn, portee, releve_id)
    if "variante_cle" in change:
        conn.execute("UPDATE releve SET variante_cle = ? WHERE id = ?",
                     (change["variante_cle"], releve_id))
    if "qualificatifs" in change:
        conn.execute("DELETE FROM releve_qualificatif WHERE releve_id = ?", (releve_id,))
        conn.executemany("INSERT INTO releve_qualificatif (releve_id, qualificatif_cle) "
                         "VALUES (?, ?)", [(releve_id, q) for q in change["qualificatifs"]])
    if "precision" in change:
        conn.execute("UPDATE releve SET precision = ? WHERE id = ?",
                     (change["precision"], releve_id))
    if "lien_region_id" in change:
        conn.execute("UPDATE releve SET lien_region_id = ?, lien_texte = ? WHERE id = ?",
                     (change["lien_region_id"], lien_texte, releve_id))
    if "mots" in change:
        conn.execute("DELETE FROM releve_mot WHERE releve_id = ?", (releve_id,))
        conn.executemany("INSERT INTO releve_mot (releve_id, position, rang, forme) "
                         "VALUES (?, ?, ?, ?)",
                         [(releve_id, i, rang, forme) for i, (rang, forme) in enumerate(passage)])
        conn.execute("UPDATE releve SET texte_ancre = ? WHERE id = ?", (texte_ancre, releve_id))
    conn.execute("UPDATE releve SET modifie_par = ?, modifie_le = datetime('now') "
                 "WHERE id = ?", (portee.utilisateur, releve_id))
    avant = {"releve_id": releve_id, **{c: actuel[c] for c in change}}
    apres = {"releve_id": releve_id, **change}
    if "mots" in change:
        avant.update(formes=actuel["formes"], texte_ancre=actuel["texte_ancre"])
        apres.update(formes=[f for _r, f in passage], texte_ancre=texte_ancre)
    if "lien_region_id" in change:
        avant["lien_texte"], apres["lien_texte"] = actuel["lien_texte"], lien_texte
    journaliser_releve(conn, "modification", r, avant=avant, apres=apres)
    conn.commit()
    return vue_de(conn, portee, releve_id)


def retirer(conn, r) -> None:
    """Retire le relevé `r` et l'écrit au journal (sa suppression, instantané profond : Ctrl+Z
    le rend, sous son identifiant, ses doutes compris). Ne commite pas ; les gardes sont à
    l'appelant (la route, la levée d'un doute)."""
    avant = instantane(conn, r["id"], profond=True)
    conn.execute("DELETE FROM releve WHERE id = ?", (r["id"],))
    journaliser_releve(conn, "suppression", r, avant=avant)


@router.delete("/api/releves/{releve_id}", status_code=204)
def retirer_releve(releve_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """RETIRE un relevé — ses mots, ses qualificatifs, ses doutes avec lui."""
    conflit.verrouiller(conn)
    r, _cible = releve_a_ecrire(conn, portee, releve_id)
    retirer(conn, r)
    conn.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Lire
# --------------------------------------------------------------------------- #
@router.get("/api/planches/{planche_id}/releves")
def releves_de_la_planche(planche_id: int, conn: sqlite3.Connection = Depends(db),
                          portee: autorisation.Portee = Depends(portee_courante)):
    """Tous les relevés de la planche — ceux de ses régions et ceux de sa surface —, avec
    leur passage, leurs qualificatifs, leur lien (et le texte d'une région liée perdue),
    leur état DÉRIVÉ et ses causes, leur auteur et son nom lisible, `collectif` (un compte
    partagé), `modifiable` (la grille active dans leur version, l'album écrit), leur doute
    ouvert et son fil ; et les PASSES de la planche, chacune signée (R13). À qui LIT la
    planche (404 sinon) : lire un relevé, c'est lire l'album."""
    _get_planche(conn, portee, planche_id)
    lignes = conn.execute(
        "SELECT * FROM releves_effectifs WHERE planche_id = ? OR region_id IN "
        "(SELECT id FROM regions WHERE planche_id = ?) ORDER BY id",
        (planche_id, planche_id)).fetchall()
    return {"planche_id": planche_id, "releves": vues(conn, portee, lignes),
            "passes": passes_de_la_planche(conn, planche_id)}


# --------------------------------------------------------------------------- #
# Le DOUTE (R7 ; note §8 ; G20 a) — une propriété de tout relevé, avec son fil
# --------------------------------------------------------------------------- #
# Il porte sur UN relevé ; un seul OUVERT à la fois (un second « ? » ajoute un message au fil
# ouvert) ; il s'ouvre avec un commentaire obligatoire ; on y répond ; on le LÈVE en gardant,
# en changeant (la modification du relevé est un acte à part, avant la levée) ou en retirant
# le relevé. N'importe qui le lève — c'est-à-dire, ici, quiconque ÉCRIT dans l'album (G20 a,
# Hugo, 2026-10-25). Au journal sous la cible du relevé, par des TYPES à lui (`doute`,
# `doute_reponse`, `doute_levee`), hors de ceux que Ctrl+Z remonte : un doute se répond, il
# ne s'annule pas.
LONGUEUR_MESSAGE = 2000


class DouteIn(BaseModel):
    texte: str


class LeveeIn(BaseModel):
    issue: str
    vu: Optional[dict] = None


def _message(texte) -> str:
    texte = grilles.propre(texte)
    if not texte:
        raise HTTPException(422, "Un doute s'ouvre, et se répond, avec un commentaire.")
    if len(texte) > LONGUEUR_MESSAGE:
        raise HTTPException(422, f"Un message tient en {LONGUEUR_MESSAGE} caractères.")
    return texte


def _vue_doute(conn, doute_id: int) -> dict:
    d = conn.execute("SELECT * FROM doute WHERE id = ?", (doute_id,)).fetchone()
    messages = conn.execute("SELECT * FROM doute_message WHERE doute_id = ? ORDER BY id",
                            (doute_id,)).fetchall()
    logins = [d["ouvert_par"], d["leve_par"], *(m["auteur"] for m in messages)]
    noms, partages = noms_lisibles(conn, logins), collectifs(conn, logins)
    return {"id": d["id"], "releve_id": d["releve_id"], "ouvert_par": d["ouvert_par"],
            "ouvert_le": d["ouvert_le"], "leve_par": d["leve_par"], "leve_le": d["leve_le"],
            "issue": d["issue"],
            "messages": [{"id": m["id"], "auteur": m["auteur"],
                          "auteur_nom": noms.get(m["auteur"]) if m["auteur"] else None,
                          "collectif": m["auteur"] in partages, "date": m["date"],
                          "texte": m["texte"]} for m in messages]}


def _doute_a_ecrire(conn, portee, doute_id: int):
    d = conn.execute("SELECT * FROM doute WHERE id = ?", (doute_id,)).fetchone()
    if d is None:
        raise HTTPException(404, f"Doute {doute_id} introuvable")
    try:
        r, _cible = releve_a_ecrire(conn, portee, d["releve_id"])
    except HTTPException as refus:
        if refus.status_code == 404:
            raise HTTPException(404, f"Doute {doute_id} introuvable")
        raise
    return d, r


@router.post("/api/releves/{releve_id}/doutes", status_code=201)
def douter(releve_id: int, payload: DouteIn, conn: sqlite3.Connection = Depends(db),
           portee: autorisation.Portee = Depends(portee_courante)):
    """Ouvre un DOUTE sur un relevé, avec son commentaire — ou, s'il en a déjà un d'ouvert,
    ajoute ce commentaire à son fil (« un second ? ajoute un message »). À qui écrit dans
    l'album (G20 a), sur une grille active."""
    texte = _message(payload.texte)
    conflit.verrouiller(conn)
    r, _cible = releve_a_ecrire(conn, portee, releve_id)
    d = conn.execute("SELECT id FROM doute WHERE releve_id = ? AND leve_le IS NULL",
                     (releve_id,)).fetchone()
    if d is None:
        doute_id = conn.execute("INSERT INTO doute (releve_id, ouvert_par) VALUES (?, ?)",
                                (releve_id, portee.utilisateur)).lastrowid
        type_ = "doute"
    else:
        doute_id, type_ = d["id"], "doute_reponse"
    mid = conn.execute("INSERT INTO doute_message (doute_id, auteur, texte) VALUES (?, ?, ?)",
                       (doute_id, portee.utilisateur, texte)).lastrowid
    charge = {"releve_id": releve_id, "doute_id": doute_id, "message_id": mid}
    if type_ == "doute":
        journaliser_releve(conn, "doute", r, apres={**charge, "doute": "ouvert"})
    else:
        journaliser_releve(conn, "doute_reponse", r, apres=charge)
    conn.commit()
    return _vue_doute(conn, doute_id)


@router.post("/api/doutes/{doute_id}/messages", status_code=201)
def repondre_au_doute(doute_id: int, payload: DouteIn, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """RÉPOND à un doute ouvert : un message signé et daté de plus dans son fil. 409 nommé sur
    un doute levé — en ouvrir un autre sur le relevé."""
    texte = _message(payload.texte)
    conflit.verrouiller(conn)
    d, r = _doute_a_ecrire(conn, portee, doute_id)
    if d["leve_le"] is not None:
        raise HTTPException(409, "Ce doute est levé : ouvrez-en un autre sur le relevé.")
    mid = conn.execute("INSERT INTO doute_message (doute_id, auteur, texte) VALUES (?, ?, ?)",
                       (doute_id, portee.utilisateur, texte)).lastrowid
    journaliser_releve(conn, "doute_reponse", r,
                       apres={"releve_id": r["id"], "doute_id": doute_id, "message_id": mid})
    conn.commit()
    return _vue_doute(conn, doute_id)


@router.post("/api/doutes/{doute_id}/levee")
def lever_le_doute(doute_id: int, payload: LeveeIn, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """LÈVE un doute : en gardant le relevé, en le changeant (sa modification est un acte à
    part, faite avant), ou en le RETIRANT — la levée s'écrit, puis le retrait, qu'un Ctrl+Z
    rend. `vu` : `{"doute": "ouvert"}` (R9). Un doute déjà levé ne se relève pas autrement :
    la même issue passe sans rien écrire, une autre reçoit le 409 de CONC-3, qui nomme qui
    l'a levé."""
    if payload.issue not in grilles.ISSUES_DOUTE:
        raise HTTPException(422, f"Une levée garde, change ou retire le relevé "
                                 f"({' | '.join(grilles.ISSUES_DOUTE)}).")
    vu = payload.vu or {}
    if set(vu) - {"doute"}:
        raise HTTPException(422, "« vu » ne porte que « doute ».")
    conflit.verrouiller(conn)
    d, r = _doute_a_ecrire(conn, portee, doute_id)
    actuel = d["issue"] if d["leve_le"] is not None else "ouvert"
    table, cible_id = cible_du_journal(r)
    try:
        conflit.verifier(conn, table, cible_id, "doute", vu=vu.get("doute", "ouvert"),
                         actuel=actuel, nouveau=payload.issue, objet=("doute_id", doute_id))
    except conflit.Perime as exc:
        raise HTTPException(409, exc.detail())
    if actuel == payload.issue:
        return _vue_doute(conn, doute_id)
    conn.execute("UPDATE doute SET leve_par = ?, leve_le = datetime('now'), issue = ? "
                 "WHERE id = ?", (portee.utilisateur, payload.issue, doute_id))
    journaliser_releve(conn, "doute_levee", r,
                       avant={"releve_id": r["id"], "doute_id": doute_id, "doute": "ouvert"},
                       apres={"releve_id": r["id"], "doute_id": doute_id,
                              "doute": payload.issue})
    vue = _vue_doute(conn, doute_id)
    if payload.issue == "retire":
        retirer(conn, r)
        vue["releve_retire"] = True
    conn.commit()
    return vue


# --------------------------------------------------------------------------- #
# La PASSE (R7 ; Q7 : commune et signée) — « terminée »
# --------------------------------------------------------------------------- #
# Une ligne par zone (région ou planche), grille et rubrique (`''` : toute la grille). La
# marquer écrit qui et quand ; une passe déjà marquée par un autre RESTE (une écriture
# identique passe sans conflit) ; « Rouvrir » la retire. Elle distingue « 0 élision » de
# « pas regardé » (note §9) et ne tient à aucun relevé. Au journal sous la cible de sa zone,
# par ses types (`passe`, `passe_rouverte`), hors de Ctrl+Z.
class PasseIn(BaseModel):
    rubrique_cle: str = ""
    vu: Optional[dict] = None


def _zone(cible: dict) -> dict:
    """La zone d'une passe, sous la forme qu'attend `journaliser_releve`."""
    if cible["region"] is not None:
        return {"region_id": cible["region"]["id"], "planche_id": None}
    return {"region_id": None, "planche_id": cible["planche_id"]}


def _passe_cible(conn, portee, *, region_id=None, planche_id=None, grille_id: int,
                 rubrique_cle: str):
    rubrique_cle = (rubrique_cle or "").strip()
    cible = cible_ecrite(conn, portee, region_id=region_id, planche_id=planche_id)
    act = activation_ou_409(conn, cible["album_id"], grille_id)
    if rubrique_cle and conn.execute(
            "SELECT 1 FROM grille_rubrique WHERE version_id = ? AND cle = ?",
            (act["version_id"], rubrique_cle)).fetchone() is None:
        raise HTTPException(422, f"« {rubrique_cle} » n'est pas une rubrique de cette version "
                                 "de la grille.")
    zone = _zone(cible)
    existante = conn.execute(
        "SELECT * FROM passe WHERE COALESCE(region_id, 0) = ? AND COALESCE(planche_id, 0) = ? "
        "AND grille_id = ? AND rubrique_cle = ?",
        (zone["region_id"] or 0, zone["planche_id"] or 0, grille_id, rubrique_cle)).fetchone()
    return zone, act, rubrique_cle, existante


def _vue_passe(conn, p) -> dict:
    noms = noms_lisibles(conn, [p["par"]])
    return {"id": p["id"], "region_id": p["region_id"], "planche_id": p["planche_id"],
            "grille_id": p["grille_id"], "version_id": p["version_id"],
            "rubrique_cle": p["rubrique_cle"], "par": p["par"],
            "par_nom": noms.get(p["par"]) if p["par"] else None,
            "collectif": p["par"] in collectifs(conn, [p["par"]]), "le": p["le"]}


def _verifier_passe(conn, zone, grille_id, rubrique_cle, vu, actuel: bool, nouveau: bool):
    if "passe" not in vu:
        return
    table, cible_id = cible_du_journal(zone)
    try:
        conflit.verifier(conn, table, cible_id, "passe", vu=bool(vu["passe"]), actuel=actuel,
                         nouveau=nouveau, objet=("passe_cle", f"{grille_id}:{rubrique_cle}"))
    except conflit.Perime as exc:
        raise HTTPException(409, exc.detail())


def _marquer(conn, portee, payload: PasseIn, grille_id: int, **cible):
    vu = payload.vu or {}
    if set(vu) - {"passe"}:
        raise HTTPException(422, "« vu » ne porte que « passe ».")
    conflit.verrouiller(conn)
    zone, act, rk, existante = _passe_cible(conn, portee, grille_id=grille_id,
                                            rubrique_cle=payload.rubrique_cle, **cible)
    _verifier_passe(conn, zone, grille_id, rk, vu, existante is not None, True)
    if existante is not None:
        return _vue_passe(conn, existante)
    pid = conn.execute("INSERT INTO passe (region_id, planche_id, grille_id, version_id, "
                       "rubrique_cle, par) VALUES (?, ?, ?, ?, ?, ?)",
                       (zone["region_id"], zone["planche_id"], grille_id, act["version_id"],
                        rk, portee.utilisateur)).lastrowid
    charge = {"passe_cle": f"{grille_id}:{rk}", "grille_id": grille_id, "rubrique_cle": rk,
              "version_id": act["version_id"]}
    journaliser_releve(conn, "passe", zone, avant={**charge, "passe": False},
                       apres={**charge, "passe": True})
    conn.commit()
    return _vue_passe(conn, conn.execute("SELECT * FROM passe WHERE id = ?", (pid,)).fetchone())


def _rouvrir(conn, portee, grille_id: int, rubrique_cle: str, vu_marquee, **cible):
    conflit.verrouiller(conn)
    zone, act, rk, existante = _passe_cible(conn, portee, grille_id=grille_id,
                                            rubrique_cle=rubrique_cle, **cible)
    vu = {} if vu_marquee is None else {"passe": vu_marquee}
    _verifier_passe(conn, zone, grille_id, rk, vu, existante is not None, False)
    if existante is None:
        return Response(status_code=204)
    conn.execute("DELETE FROM passe WHERE id = ?", (existante["id"],))
    charge = {"passe_cle": f"{grille_id}:{rk}", "grille_id": grille_id, "rubrique_cle": rk,
              "version_id": existante["version_id"], "par": existante["par"]}
    journaliser_releve(conn, "passe_rouverte", zone, avant={**charge, "passe": True},
                       apres={**charge, "passe": False})
    conn.commit()
    return Response(status_code=204)


@router.put("/api/regions/{region_id}/passes/{grille_id}")
def marquer_passe_region(region_id: int, grille_id: int, payload: PasseIn,
                         conn: sqlite3.Connection = Depends(db),
                         portee: autorisation.Portee = Depends(portee_courante)):
    """Marque « terminée » la passe d'une grille (ou de l'une de ses rubriques) sur une
    région. Déjà marquée par un autre : elle reste, signée de lui. À qui écrit l'album."""
    return _marquer(conn, portee, payload, grille_id, region_id=region_id)


@router.delete("/api/regions/{region_id}/passes/{grille_id}", status_code=204)
def rouvrir_passe_region(region_id: int, grille_id: int, rubrique_cle: str = "",
                         vu_marquee: Optional[bool] = None,
                         conn: sqlite3.Connection = Depends(db),
                         portee: autorisation.Portee = Depends(portee_courante)):
    """ROUVRE la passe : elle n'est plus terminée. `vu_marquee` : ce que l'écran avait vu."""
    return _rouvrir(conn, portee, grille_id, rubrique_cle, vu_marquee, region_id=region_id)


@router.put("/api/planches/{planche_id}/passes/{grille_id}")
def marquer_passe_planche(planche_id: int, grille_id: int, payload: PasseIn,
                          conn: sqlite3.Connection = Depends(db),
                          portee: autorisation.Portee = Depends(portee_courante)):
    """La passe sur la planche entière (la surface)."""
    return _marquer(conn, portee, payload, grille_id, planche_id=planche_id)


@router.delete("/api/planches/{planche_id}/passes/{grille_id}", status_code=204)
def rouvrir_passe_planche(planche_id: int, grille_id: int, rubrique_cle: str = "",
                          vu_marquee: Optional[bool] = None,
                          conn: sqlite3.Connection = Depends(db),
                          portee: autorisation.Portee = Depends(portee_courante)):
    """Rouvre la passe de la planche entière."""
    return _rouvrir(conn, portee, grille_id, rubrique_cle, vu_marquee, planche_id=planche_id)


def passes_de_la_planche(conn, planche_id: int) -> list:
    return [_vue_passe(conn, p) for p in conn.execute(
        "SELECT * FROM passe WHERE planche_id = ? OR region_id IN "
        "(SELECT id FROM regions WHERE planche_id = ?) ORDER BY id", (planche_id, planche_id))]
