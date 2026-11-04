"""Les GRILLES d'annotation — importer, écrire sans import, publier, activer, masquer, lire
(ANN-7, tranche 1 ; cadrage R2 à R4, R8 ; décisions de Hugo du 2026-10-25 ; l'écriture sans
import, option HYBRIDE tranchée sur maquette le 2026-11-03).

Sans écran : les routes que la fiche d'un projet (Administration › Projets) et la page
Annotation consommeront. Une grille s'écrit dans un tableur (`grille_import`), se garde en
BROUILLON, se PUBLIE en une version figée et numérotée, s'ACTIVE sur un projet dans une
version ; une collection du projet peut la MASQUER — un filtre d'écran, pas une garde (Q1).

Qui fait quoi (R8) — les décisions d'accès d'une grille sont celles de SON projet :
- importer, écrire sans import (créer, modifier, retirer une grille, une rubrique, une entrée,
  une variante, une liste, une case), publier, supprimer un brouillon, retirer, supprimer une
  grille, corriger une coquille, activer, désactiver : qui GÈRE le projet (`peut_gerer_projet` —
  son responsable, l'administrateur qui passe outre). 404 sur une grille ou un projet qu'on
  ne voit pas, 403 nommé sur ce qu'on voit sans le gérer ;
- masquer dans une collection : qui l'ADMINISTRE (`peut_administrer`, G7) ;
- lire le plan publié (ou vivant), et son tableur : `Portee.clause_grille`, la seule question
  neuve ; lire un brouillon : qui gère le projet — « le brouillon reste chez ses auteurs ».

Le journal : tout s'écrit sous `grille` (`cible_id` = la grille), retenu de toute sortie et
sans rang (`tools/_commun.py`) — administrer un vocabulaire n'est pas annoter.
"""
from __future__ import annotations

import copy
import io
import json
import sqlite3
from typing import Optional, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

import autorisation
import conflit
import grille_ecriture
import grille_import
import grille_tableur
import grilles
import journal
from socle import (_disposition, _get_collection, _get_projet, _refuser_le_jeu, _row, db,
                   portee_courante)

router = APIRouter()

_MOTIF_GERER = ("Les grilles d'un projet se règlent par ses responsables (et les "
                "administrateurs de l'instance).")
_MOTIF_MASQUER = ("Masquer une grille dans une collection revient à son propriétaire, comme "
                  "sa description.")


def _get_grille(conn, portee: autorisation.Portee, grille_id: int, *,
                gerer: bool = False) -> dict:
    """La grille qu'on peut LIRE — par `clause_grille`, ou parce qu'on gère son projet (son
    brouillon est à soi) —, 404 sinon ; et, si `gerer`, dont on gère le projet, 403 nommé
    sinon : son nom est déjà à l'écran, un « introuvable » mentirait.

    Une grille qui n'a encore aucune version publiée ni vivante n'est qu'un BROUILLON : à qui
    ne gère pas son projet — un simple membre compris —, elle est introuvable, du même 404
    qu'un identifiant qui n'existe pas, et son nom ne sort pas (relecture croisée, constat 4 ;
    `clause_grille`, moitié (a)). La liste des grilles du projet suit la même clause."""
    ou, params = portee.clause_grille("g.id")
    g = _row(conn.execute("SELECT g.* FROM grille g WHERE g.id = ?", (grille_id,)))
    if g is None:
        raise HTTPException(404, f"Grille {grille_id} introuvable")
    lisible = conn.execute(f"SELECT 1 FROM grille g WHERE g.id = ? AND {ou}",
                           (grille_id, *params)).fetchone() is not None
    gerable = portee.peut_gerer_projet(g["projet_id"])
    if not (lisible or gerable):
        raise HTTPException(404, f"Grille {grille_id} introuvable")
    if gerer and not gerable:
        raise HTTPException(403, _MOTIF_GERER)
    g["gerable"] = gerable
    return g


def _get_version(conn, g: dict, numero: int) -> dict:
    """La version `numero` de la grille `g` ; un brouillon n'existe que pour qui gère le
    projet (404 sinon, comme une version qui n'existe pas)."""
    v = grilles.version(conn, g["id"], numero)
    if v is None or (v["etat"] == grilles.ETAT_BROUILLON and not g["gerable"]):
        raise HTTPException(404, f"Version {numero} introuvable")
    return dict(v)


def _vue_grille(conn, g: dict) -> dict:
    """Une grille telle que la fiche d'un projet la lit : ses versions (les brouillons pour
    qui gère seulement), ses activations dans son projet. Aucun login : qui a importé ou
    publié ne sort pas (option la plus fermée ; le journal le garde)."""
    versions = [{"numero": v["numero"], "etat": v["etat"],
                 "porte_sur": list(grilles.cibles_de(v["cible"])), "note": v["note"],
                 "publiee_le": v["publiee_le"], "importee_le": v["importee_le"]}
                for v in conn.execute("SELECT * FROM grille_version WHERE grille_id = ? "
                                      "ORDER BY numero", (g["id"],))
                if v["etat"] != grilles.ETAT_BROUILLON or g["gerable"]]
    act = grilles.activation(conn, g["projet_id"], g["id"])
    return {"id": g["id"], "nom": g["nom"], "projet_id": g["projet_id"],
            "ouverte": bool(g["ouverte"]), "retiree_le": g["retiree_le"],
            "gerable": g["gerable"], "versions": versions,
            "active": {"numero": act["numero"], "etat": act["etat"]} if act else None}


# --------------------------------------------------------------------------- #
# Lire
# --------------------------------------------------------------------------- #
@router.get("/api/projets/{projet_id}/grilles")
def grilles_du_projet(projet_id: int, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Les grilles ACTIVES du projet que l'appelant peut lire — leur version, ouverte ou non,
    et les collections du projet (qu'il lit) qui les MASQUENT ; et, à qui GÈRE le projet,
    toutes les siennes, brouillons et grilles retirées compris (R13). 404 sur un projet
    qu'on ne peut pas nommer."""
    _get_projet(conn, portee, projet_id)
    gerable = portee.peut_gerer_projet(projet_id)
    ou, params = portee.clause_grille("g.id")
    actives = []
    for r in conn.execute(
            f"SELECT g.*, v.numero, v.etat, v.cible FROM projet_grille pg "
            f"JOIN grille g ON g.id = pg.grille_id JOIN grille_version v ON v.id = pg.version_id "
            f"WHERE pg.projet_id = ? AND {ou} ORDER BY g.nom, g.id", (projet_id, *params)):
        masquee = [m["collection_id"] for m in conn.execute(
            "SELECT collection_id FROM collection_grille_masquee WHERE grille_id = ? "
            "ORDER BY collection_id", (r["id"],)) if portee.peut_lire(m["collection_id"])]
        actives.append({"id": r["id"], "nom": r["nom"], "ouverte": bool(r["ouverte"]),
                        "version": {"numero": r["numero"], "etat": r["etat"],
                                    "porte_sur": list(grilles.cibles_de(r["cible"]))},
                        "masquee_dans": masquee})
    corps = {"projet_id": projet_id, "gerable": gerable, "actives": actives}
    if gerable:
        corps["grilles"] = [
            _vue_grille(conn, {**dict(g), "gerable": True}) for g in conn.execute(
                "SELECT * FROM grille WHERE projet_id = ? ORDER BY nom, id", (projet_id,))]
    return corps


@router.get("/api/grilles/{grille_id}")
def fiche_grille(grille_id: int, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """La fiche d'une grille : ses versions, son activation dans son projet."""
    return _vue_grille(conn, _get_grille(conn, portee, grille_id))


@router.get("/api/grilles/{grille_id}/versions/{numero}")
def plan_de_version(grille_id: int, numero: int, emplois: bool = Query(False),
                    conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Le PLAN entier d'une version (R13) — rubriques imbriquées, entrées avec leur cible et
    leur cardinalité effectives, la précision et le lien attendus, variantes, listes,
    définitions, structures, exemples, pièges —, de quoi filtrer côté écran sans aller-
    retour. Un brouillon, à qui gère le projet seulement.

    `emplois` (le formulaire de construction) : ce que les relevés emploient dans la grille
    (`grille_ecriture.emplois`) — des comptes, sans personne —, à qui GÈRE le projet ; la clé
    est absente pour les autres, qui n'écrivent pas la grille."""
    g = _get_grille(conn, portee, grille_id)
    v = _get_version(conn, g, numero)
    corps = {"grille": {"id": g["id"], "nom": g["nom"], "ouverte": bool(g["ouverte"])},
             **grilles.plan(conn, v["id"])}
    if emplois and g["gerable"]:
        corps["emplois"] = grille_ecriture.emplois(conn, g, v, grilles.contenu(conn, v["id"]))
    return corps


# --------------------------------------------------------------------------- #
# Importer, publier, retirer
# --------------------------------------------------------------------------- #
def _octets(fichier: UploadFile | None, quoi: str) -> bytes | None:
    """Les octets d'un fichier reçu, BORNÉS : on n'en lit jamais plus que le plafond (413
    au-delà), CSV comme classeur."""
    if fichier is None:
        return None
    data = fichier.file.read(grille_tableur.TAILLE_MAX_RECUE + 1)
    if len(data) > grille_tableur.TAILLE_MAX_RECUE:
        raise HTTPException(413, f"Le fichier des {quoi} pèse plus de "
                                 f"{grille_tableur.TAILLE_MAX_RECUE // (1024 * 1024)} Mo : "
                                 "ce n'est pas une grille.")
    if not data:
        raise HTTPException(400, f"Le fichier des {quoi} est vide.")
    return data


def _texte_de(data: bytes | None, quoi: str) -> io.StringIO | None:
    if data is None:
        return None
    try:
        return io.StringIO(data.decode("utf-8-sig"), newline="")
    except UnicodeDecodeError:
        raise HTTPException(400, f"Le fichier des {quoi} doit être encodé en UTF-8, ou être "
                                 "un classeur .xlsx.")


def _nom_de(fichier: UploadFile | None, defaut: str) -> str:
    """Le nom d'un fichier reçu, sans son dossier — pour dire où est une faute."""
    nom = (getattr(fichier, "filename", None) or "").replace(chr(92), "/").rsplit("/", 1)[-1]
    return nom.strip() or defaut


def _refus_http(exc: grille_import.Refus) -> HTTPException:
    if exc.anomalies or exc.bilan:
        return HTTPException(exc.statut, {"message": exc.message, **exc.bilan,
                                          "anomalies": exc.anomalies})
    return HTTPException(exc.statut, exc.message)


def _reponses(texte: str | None) -> dict | None:
    """Les réponses aux entrées employées qui disparaissent d'une grille ouverte : un objet
    JSON, `{"cle": "retirer"}` ou `{"cle": "fusionner:autre"}`."""
    if not texte:
        return None
    try:
        valeur = json.loads(texte)
    except ValueError:
        raise HTTPException(422, "`reponses` doit être un objet JSON.")
    if not isinstance(valeur, dict):
        raise HTTPException(422, "`reponses` doit être un objet JSON.")
    return valeur


@router.post("/api/projets/{projet_id}/grilles/import")
def importer_grille(projet_id: int, fichier: UploadFile = File(...),
                    listes: Optional[UploadFile] = File(None),
                    grille_id: Optional[int] = Form(None, ge=1),
                    nom: Optional[str] = Form(None), ouverte: Optional[bool] = Form(None),
                    porte_sur: Optional[str] = Form(None), note: Optional[str] = Form(None),
                    a_blanc: bool = Form(False), reponses: Optional[str] = Form(None),
                    conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Importe un tableur (R3) — deux CSV (`fichier`, `listes`), ou un classeur `.xlsx`
    (`fichier` seul, reconnu à ses octets) : une grille NEUVE (`nom`, `ouverte`,
    `porte_sur`, ou la feuille « 1. La grille » du classeur) ou la version suivante d'une
    grille du projet (`grille_id`). Le fichier est vérifié ENTIER : une anomalie de structure
    le refuse (422, toutes les anomalies dites en DONNÉES, le verdict et « À savoir », rien
    d'écrit, G12). `a_blanc` rend le BILAN — verdict, « À savoir », « Ce qui va naître », ce
    qui change depuis la dernière version publiée — sans rien écrire. Réimporter le même
    fichier ne change rien. Une grille OUVERTE se réimporte (tranché par Hugo le
    2026-11-03) : une entrée employée qui disparaît attend sa réponse (`reponses`, un objet
    JSON — « retirer » ou « fusionner:<cle> ») ; sans elle, 409 avec le bilan qui la demande.
    Le fichier est borné (413) ; un classeur l'est aussi une fois déplié.

    À qui gère le projet (404 / 403 nommé) ; jamais dans le projet de jeu. Dans un bac à
    sable, oui (G6) : la grille n'existe que là, et part avec lui."""
    _get_projet(conn, portee, projet_id, gerer=True, motif=_MOTIF_GERER)
    _refuser_le_jeu(conn, projet_id=projet_id)
    data = _octets(fichier, "entrées")
    classeur = data if grille_tableur.est_un_classeur(data) else None
    if classeur is not None and listes is not None:
        raise HTTPException(422, "Un classeur porte ses listes dans sa feuille « "
                                 f"{grille_tableur.FEUILLE_LISTES} » : n'envoyez pas de "
                                 "second fichier.")
    flux = None if classeur is not None else _texte_de(data, "entrées")
    flux_listes = _texte_de(_octets(listes, "listes"), "listes")
    noms = (_nom_de(fichier, grille_import.NOMS_PAR_DEFAUT[0]),
            _nom_de(listes, grille_import.NOMS_PAR_DEFAUT[1]))
    reps = _reponses(reponses)
    conflit.verrouiller(conn)            # le nom unique et le brouillon se lisent sous le verrou
    try:
        res = grille_import.importer(conn, projet_id=projet_id, flux_entrees=flux,
                                     flux_listes=flux_listes, classeur=classeur,
                                     grille_id=grille_id, nom=nom, ouverte=ouverte,
                                     porte_sur=porte_sur, note=note, par=portee.utilisateur,
                                     a_blanc=a_blanc, reponses=reps, noms=noms)
    except grille_import.TropGros as e:
        raise HTTPException(413, str(e))
    except grille_import.FormatInvalide as e:
        raise HTTPException(400, str(e))
    except grille_import.Refus as e:
        raise _refus_http(e)
    if a_blanc:
        conn.rollback()
    else:
        conn.commit()
    return res


@router.post("/api/grilles/{grille_id}/versions/{numero}/publication")
def publier_version(grille_id: int, numero: int, conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Publie le BROUILLON : il devient une version figée, qui garde son numéro (le suivant).
    409 nommé sur une version qui n'est pas un brouillon, qui n'a aucune entrée, ou qui porte
    exactement la dernière version publiée (même empreinte et même ordre : rien à publier)."""
    conflit.verrouiller(conn)
    g = _get_grille(conn, portee, grille_id, gerer=True)
    v = _get_version(conn, g, numero)
    if v["etat"] != grilles.ETAT_BROUILLON:
        raise HTTPException(409, f"La version {numero} n'est pas un brouillon : elle est "
                                 f"{v['etat']}.")
    if not conn.execute("SELECT 1 FROM grille_entree WHERE version_id = ? LIMIT 1",
                        (v["id"],)).fetchone():
        # Une grille créée sans import naît vide (la règle de l'import : « aucune entrée »).
        raise HTTPException(409, f"La version {numero} n'a aucune entrée : elle ne se publie "
                                 "pas.")
    publiee = grilles.derniere_version(conn, grille_id, grilles.ETAT_PUBLIEE)
    if publiee is not None:
        # Un brouillon qui porte exactement la dernière version publiée — même contenu, même
        # ordre — ne fait pas une version : la publier donnerait deux numéros au même plan
        # (le patron de l'import, qui dit « aucun changement » ; choix à confirmer).
        b, p = grilles.contenu(conn, v["id"]), grilles.contenu(conn, publiee["id"])
        if grilles.empreinte(b) == grilles.empreinte(p) and grilles.ordre(b) == grilles.ordre(p):
            raise HTTPException(409, f"Le brouillon {numero} porte exactement la version "
                                     f"{publiee['numero']} publiée : il n'y a rien à publier. "
                                     "Changez-le, ou supprimez-le.")
    grille_import.publier(conn, grille_id, v, par=portee.utilisateur)
    conn.commit()
    return _vue_grille(conn, g)


@router.delete("/api/grilles/{grille_id}/versions/{numero}", status_code=204)
def supprimer_brouillon(grille_id: int, numero: int, conn: sqlite3.Connection = Depends(db),
                        portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime un BROUILLON. Une grille qui n'avait que lui part avec lui : elle n'a jamais
    rien été. 409 nommé sur une version publiée ou vivante."""
    conflit.verrouiller(conn)
    g = _get_grille(conn, portee, grille_id, gerer=True)
    v = _get_version(conn, g, numero)
    if v["etat"] != grilles.ETAT_BROUILLON:
        raise HTTPException(409, f"La version {numero} est {v['etat']} : seul un brouillon "
                                 "se supprime.")
    conn.execute("DELETE FROM grille_version WHERE id = ?", (v["id"],))
    seule = conn.execute("SELECT COUNT(*) FROM grille_version WHERE grille_id = ?",
                         (grille_id,)).fetchone()[0] == 0
    journal.journaliser(conn, "suppression", "grille", grille_id,
                        avant={"version": numero, "etat": grilles.ETAT_BROUILLON,
                               **({"nom": g["nom"]} if seule else {})})
    if seule:
        conn.execute("DELETE FROM grille WHERE id = ?", (grille_id,))
    conn.commit()
    return Response(status_code=204)


@router.post("/api/grilles/{grille_id}/retrait")
def retirer_grille(grille_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """RETIRE une grille : elle ne s'active plus, ne reçoit plus de version ; ses relevés
    restent. Seule la retraite s'écrit sur la grille (« en usage » se dérive). 409 nommé sur
    une grille encore active — la désactiver d'abord."""
    conflit.verrouiller(conn)
    g = _get_grille(conn, portee, grille_id, gerer=True)
    if conn.execute("SELECT 1 FROM projet_grille WHERE grille_id = ?",
                    (grille_id,)).fetchone():
        raise HTTPException(409, "Cette grille est active : désactivez-la d'abord dans son "
                                 "projet.")
    if not g["retiree_le"]:
        conn.execute("UPDATE grille SET retiree_le = datetime('now') WHERE id = ?",
                     (grille_id,))
        journal.journaliser(conn, "modification", "grille", grille_id,
                            avant={"retiree": False}, apres={"retiree": True})
        conn.commit()
    return _vue_grille(conn, _get_grille(conn, portee, grille_id))


@router.delete("/api/grilles/{grille_id}", status_code=204)
def supprimer_grille(grille_id: int, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime une grille que rien n'emploie — « la suppression suit l'emploi » : ni active,
    ni porteuse d'un relevé ou d'une passe (409 nommé sinon ; les relevés tiennent à leur
    grille). Le chemin qui libère un projet qu'on veut supprimer (G18)."""
    conflit.verrouiller(conn)
    g = _get_grille(conn, portee, grille_id, gerer=True)
    if conn.execute("SELECT 1 FROM projet_grille WHERE grille_id = ?",
                    (grille_id,)).fetchone():
        raise HTTPException(409, "Cette grille est active : désactivez-la d'abord.")
    n = conn.execute("SELECT (SELECT COUNT(*) FROM releve WHERE grille_id = ?) "
                     "+ (SELECT COUNT(*) FROM passe WHERE grille_id = ?)",
                     (grille_id, grille_id)).fetchone()[0]
    if n:
        raise HTTPException(409, f"Cette grille porte {n} relevé(s) ou passe(s) : elle ne se "
                                 "supprime pas. Retirez-la : ses relevés restent lisibles.")
    journal.journaliser(conn, "suppression", "grille", grille_id,
                        avant={"nom": g["nom"], "projet_id": g["projet_id"]})
    conn.execute("DELETE FROM grille WHERE id = ?", (grille_id,))
    conn.commit()
    return Response(status_code=204)


class CoquilleIn(BaseModel):
    """Une coquille corrigée sans nouvelle version (G15 ; « Une coquille se corrige à
    l'écran », tranché le 2026-10-22) : la définition, le piège ou les exemples d'une entrée
    ou d'une variante, la définition d'un qualificatif — ce qui ne touche aucun relevé."""
    entree_cle: Optional[str] = None
    variante_cle: Optional[str] = None
    liste_cle: Optional[str] = None
    qualificatif_cle: Optional[str] = None
    definition: Optional[str] = None
    piege: Optional[str] = None
    exemples: Optional[list[str]] = None


@router.patch("/api/grilles/{grille_id}/versions/{numero}/coquille")
def corriger_coquille(grille_id: int, numero: int, payload: CoquilleIn,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Corrige une COQUILLE dans une version publiée (ou vivante), sans nouvelle version, au
    journal : une définition, un piège, des exemples. L'empreinte de la version suit — un
    tableur qui porte la même correction se réimporte sans changement. 422 sur un champ qui
    ne se corrige pas ainsi (un libellé, une forme : une nouvelle version), et sur un
    exemple qui porte « | » ou un retour à la ligne (`exemple_separateur`, le refus de la
    création)."""
    conflit.verrouiller(conn)
    g = _get_grille(conn, portee, grille_id, gerer=True)
    v = _get_version(conn, g, numero)
    if v["etat"] not in (grilles.ETAT_PUBLIEE, grilles.ETAT_VIVANTE):
        raise HTTPException(409, "Un brouillon se corrige en réimportant le tableur.")
    champs = payload.model_dump(exclude_unset=True)
    nouveaux = {k: champs[k] for k in ("definition", "piege", "exemples") if k in champs}
    if not nouveaux:
        raise HTTPException(422, "Rien à corriger : definition, piege ou exemples.")
    if payload.qualificatif_cle is not None:
        if set(nouveaux) - {"definition"}:
            raise HTTPException(422, "Un qualificatif ne porte qu'une définition.")
        cible = ("grille_qualificatif", "liste_cle = ? AND cle = ?",
                 (payload.liste_cle, payload.qualificatif_cle))
        exemples_de = None
    elif payload.variante_cle is not None:
        cible = ("grille_variante", "entree_cle = ? AND cle = ?",
                 (payload.entree_cle, payload.variante_cle))
        exemples_de = (payload.entree_cle, payload.variante_cle)
    elif payload.entree_cle is not None:
        cible = ("grille_entree", "cle = ?", (payload.entree_cle,))
        exemples_de = (payload.entree_cle, None)
    else:
        raise HTTPException(422, "Nommez l'entrée, la variante ou le qualificatif.")
    table, ou, params = cible
    ligne = conn.execute(f"SELECT * FROM {table} WHERE version_id = ? AND {ou}",
                         (v["id"], *params)).fetchone()
    if ligne is None:
        raise HTTPException(404, "Introuvable dans cette version.")
    avant, apres = {}, {}
    for champ in ("definition", "piege"):
        if champ in nouveaux:
            avant[champ], apres[champ] = ligne[champ], grilles.propre(nouveaux[champ])
            conn.execute(f"UPDATE {table} SET {champ} = ? WHERE id = ?",
                         (apres[champ], ligne["id"]))
    if "exemples" in nouveaux:
        textes = [t for t in (grilles.propre(x) for x in (nouveaux["exemples"] or [])) if t]
        if not grille_ecriture._sans_separateur(textes):
            # Le refus de la création : le réexport découperait l'exemple en deux.
            raise _refus_http(_refus(
                "exemple_separateur", "un exemple porte un « | » ou un retour à la ligne, "
                "qui séparent deux exemples", "écrivez chaque exemple à part",
                cle=payload.entree_cle, colonne="exemples"))
        ancien = [r["texte"] for r in conn.execute(
            "SELECT texte FROM grille_exemple WHERE version_id = ? AND entree_cle = ? "
            "AND variante_cle IS ? ORDER BY rang, id", (v["id"], *exemples_de))]
        avant["exemples"], apres["exemples"] = ancien, textes
        conn.execute("DELETE FROM grille_exemple WHERE version_id = ? AND entree_cle = ? "
                     "AND variante_cle IS ?", (v["id"], *exemples_de))
        conn.executemany("INSERT INTO grille_exemple (version_id, entree_cle, variante_cle, "
                         "rang, texte) VALUES (?, ?, ?, ?, ?)",
                         [(v["id"], *exemples_de, i, t) for i, t in enumerate(textes)])
    conn.execute("UPDATE grille_version SET empreinte = ? WHERE id = ?",
                 (grilles.empreinte(grilles.contenu(conn, v["id"])), v["id"]))
    journal.journaliser(conn, "modification", "grille", grille_id,
                        avant={"coquille": {"version": numero, "objet": params, **avant}},
                        apres={"coquille": {"version": numero, "objet": params, **apres}})
    conn.commit()
    return grilles.plan(conn, v["id"])


_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/api/grilles/{grille_id}/versions/{numero}/tableur")
def reexporter_tableur(grille_id: int, numero: int,
                       forme: str = Query("xlsx", alias="format", pattern="^(xlsx|csv)$"),
                       conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """Le TABLEUR d'une version, identifiants compris (G16) : le CLASSEUR `.xlsx` en mots
    (gabarit tranché par Hugo le 2026-11-03 — listes déroulantes, aide sur les titres, la
    case fautive en rouge, une feuille d'exemple), ou, `?format=csv`, les deux CSV machine
    dans un zip. Réimporté tel quel, l'un comme l'autre rend la même empreinte.

    À qui LIT le plan de la version — la règle de `GET …/versions/{numero}` : `clause_grille`,
    et un brouillon à qui gère le projet seulement (404 sinon). Le classeur ne porte que le
    plan, qui se lit déjà en JSON : ni login, ni relevé, ni transcription. Une porte DÉCLARÉE
    hors du droit d'export (DROIT-2 borne le CORPUS ; une grille est un vocabulaire,
    `tests/test_droit_export.py`)."""
    g = _get_grille(conn, portee, grille_id)
    v = _get_version(conn, g, numero)
    if forme == "csv":
        return Response(content=grille_import.archive(conn, v["id"]),
                        media_type="application/zip",
                        headers={"Content-Disposition":
                                 _disposition(f"grille-{grille_id}-v{numero}.zip")})
    return Response(content=grille_import.classeur(conn, v["id"]), media_type=_XLSX,
                    headers={"Content-Disposition":
                             _disposition(f"grille-{grille_id}-v{numero}.xlsx")})


# --------------------------------------------------------------------------- #
# Activer, masquer
# --------------------------------------------------------------------------- #
class ActivationIn(BaseModel):
    version: int


@router.put("/api/projets/{projet_id}/grilles/{grille_id}/activation")
def activer_grille(projet_id: int, grille_id: int, payload: ActivationIn,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """ACTIVE une grille sur le projet, dans UNE version (R4) — publiée pour une grille
    fermée, vivante pour une ouverte. En tranche 1, un projet n'active que SES grilles (le
    catalogue n'existe pas : 409 nommé). Changer la version d'une activation qui porte des
    relevés est la MONTÉE DE VERSION, refusée (409 nommé) jusqu'à la tranche qui l'écrit.
    Les règles du modèle vivent dans `grille_import.activer`, que l'outil d'import partage
    (`--activer`) ; ici, le droit."""
    _get_projet(conn, portee, projet_id, gerer=True, motif=_MOTIF_GERER)
    _refuser_le_jeu(conn, projet_id=projet_id)
    conflit.verrouiller(conn)
    g = _get_grille(conn, portee, grille_id)
    try:
        ecrit = grille_import.activer(conn, projet_id=projet_id, grille_id=grille_id,
                                      numero=payload.version, par=portee.utilisateur)
    except grille_import.Refus as exc:
        raise HTTPException(exc.statut, exc.message)
    if ecrit:
        conn.commit()
    return _vue_grille(conn, g)


@router.delete("/api/projets/{projet_id}/grilles/{grille_id}/activation", status_code=204)
def desactiver_grille(projet_id: int, grille_id: int, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """DÉSACTIVE une grille : ses relevés restent, en LECTURE (« Désactiver une grille dans un
    projet ne supprime aucun relevé », 2026-10-22) — toute écriture sur eux est alors
    refusée par un 409 nommé. 404 si elle n'y est pas active."""
    _get_projet(conn, portee, projet_id, gerer=True, motif=_MOTIF_GERER)
    conflit.verrouiller(conn)
    act = grilles.activation(conn, projet_id, grille_id)
    if act is None:
        raise HTTPException(404, "Cette grille n'est pas active dans ce projet.")
    conn.execute("DELETE FROM projet_grille WHERE projet_id = ? AND grille_id = ?",
                 (projet_id, grille_id))
    journal.journaliser(conn, "delien", "grille", grille_id,
                        avant={"projet_id": projet_id, "version": act["numero"]})
    conn.commit()
    return Response(status_code=204)


@router.put("/api/collections/{collection_id}/grilles-masquees/{grille_id}")
def masquer_grille(collection_id: int, grille_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """MASQUE, dans cette collection, une grille active de son projet (Q1) — un filtre
    d'écran, pas une garde : aucune route de relevé ne le lit, les relevés déjà posés
    restent visibles en lecture. À qui administre la collection (G7). Le modèle :
    `grille_import.masquer`, partagé avec l'outil (`--masquer`)."""
    _get_collection(conn, portee, collection_id, administrer=True, motif=_MOTIF_MASQUER)
    conflit.verrouiller(conn)
    g = _get_grille(conn, portee, grille_id)
    try:
        if grille_import.masquer(conn, collection_id=collection_id, grille_id=grille_id,
                                 par=portee.utilisateur):
            conn.commit()
    except grille_import.Refus as exc:
        raise HTTPException(exc.statut, exc.message)
    return {"collection_id": collection_id, "grille_id": g["id"], "masquee": True}


@router.delete("/api/collections/{collection_id}/grilles-masquees/{grille_id}",
               status_code=204)
def demasquer_grille(collection_id: int, grille_id: int, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Remontre, dans cette collection, une grille masquée. 404 si elle ne l'était pas."""
    c = _get_collection(conn, portee, collection_id, administrer=True, motif=_MOTIF_MASQUER)
    conflit.verrouiller(conn)
    if not conn.execute("DELETE FROM collection_grille_masquee WHERE collection_id = ? "
                        "AND grille_id = ?", (collection_id, grille_id)).rowcount:
        raise HTTPException(404, "Cette grille n'est pas masquée dans cette collection.")
    journal.journaliser(conn, "delien", "grille", grille_id,
                        avant={"masquee_dans": collection_id, "collection": c["nom"]})
    conn.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Écrire une grille SANS IMPORT — les routes du formulaire (ANN-7 ; l'option HYBRIDE,
# tranchée par Hugo sur maquette le 2026-11-03)
# --------------------------------------------------------------------------- #
# Une grille fermée s'écrit dans son BROUILLON — né, s'il manque, de sa dernière version
# publiée —, une grille ouverte dans sa version vivante, en place
# (`grille_ecriture.version_en_ecriture`). Chaque geste relit la version ENTIÈRE sous les
# refus de l'import, et, sur une grille ouverte, sous les règles de son réimport : une entrée
# employée ne se supprime jamais, elle se retire ou se fusionne. Ce qui se MODIFIE accepte
# `vu`, la valeur que l'écran voyait (CONC-3) : périmée, 409 qui nomme qui l'a changée ; sans
# elle, le dernier gagne (Q8). Tout s'écrit sous `grille`, un acte par objet touché, dont la
# charge nomme l'objet (`objet` : « entree:cri », « variante:cri/bang », « rubrique:sons »,
# « liste:sources », « case:sources/objet », « grille », et pour un ordre les frères qu'il
# range, « ordre:entree:sons ») — c'est par elle que le 409 trouve
# l'auteur d'une valeur. À qui gère le projet : 404 sur une grille qu'on ne voit pas, 403
# nommé sur une grille qu'on lit sans la gérer. Ctrl+Z ne défait rien de cela, comme de
# l'import. La réponse rend le PLAN de la version écrite (`grilles.plan`), que le formulaire
# redessine.
Cible = Optional[Union[str, list[str]]]


class _Strict(BaseModel):
    """Un corps qui refuse ce qu'il ne connaît pas (422) : un identifiant, une nature
    (`ouverte`) qu'on croirait changer en silence."""
    model_config = ConfigDict(extra="forbid")


class GrilleIn(_Strict):
    nom: str
    ouverte: bool = False
    porte_sur: Cible = None
    note: Optional[str] = None


class GrillePatch(_Strict):
    nom: Optional[str] = None
    porte_sur: Cible = None
    note: Optional[str] = None
    vu: Optional[dict] = None


class VarianteIn(_Strict):
    cle: Optional[str] = None
    libelle: Optional[str] = None
    definition: Optional[str] = None
    structure: Optional[str] = None
    piege: Optional[str] = None
    exemples: Optional[list[str]] = None


class VariantePatch(_Strict):
    libelle: Optional[str] = None
    definition: Optional[str] = None
    structure: Optional[str] = None
    piege: Optional[str] = None
    exemples: Optional[list[str]] = None
    vu: Optional[dict] = None


class _ChampsEntree(_Strict):
    libelle: Optional[str] = None
    rubrique_cle: Optional[str] = None
    forme: Optional[str] = None
    definition: Optional[str] = None
    structure: Optional[str] = None
    piege: Optional[str] = None
    exemples: Optional[list[str]] = None
    precision: Optional[str] = None
    lien: Optional[bool] = None
    cible: Cible = None
    cardinalite: Optional[str] = None
    liste_cle: Optional[str] = None
    variantes: Optional[list[VarianteIn]] = None


class EntreeIn(_ChampsEntree):
    cle: Optional[str] = None


class EntreePatch(_ChampsEntree):
    vu: Optional[dict] = None


class FusionIn(_Strict):
    dans: str


class RubriqueIn(_Strict):
    cle: Optional[str] = None
    libelle: Optional[str] = None
    parent_cle: Optional[str] = None


class RubriquePatch(_Strict):
    libelle: Optional[str] = None
    parent_cle: Optional[str] = None
    vu: Optional[dict] = None


class CaseIn(_Strict):
    cle: Optional[str] = None
    libelle: Optional[str] = None
    definition: Optional[str] = None


class CasePatch(_Strict):
    libelle: Optional[str] = None
    definition: Optional[str] = None
    vu: Optional[dict] = None


class ListeIn(_Strict):
    cle: Optional[str] = None
    libelle: Optional[str] = None
    cases: Optional[list[CaseIn]] = None


class ListePatch(_Strict):
    libelle: Optional[str] = None
    vu: Optional[dict] = None


def _refus(code: str, probleme: str, a_faire=None, *, cle=None, colonne=None,
           statut: int = 422) -> grille_import.Refus:
    """Un refus qui porte UNE faute, au format de l'import."""
    return grille_import.Refus(statut, probleme[:1].upper() + probleme[1:] + ".",
                               [grille_import._faute(code, probleme, a_faire, cle=cle,
                                                     colonne=colonne)])


def _norme(champ: str, valeur, *, cle=None):
    """Une valeur reçue, ramenée à la forme du contenu d'une version (`grilles.contenu`)."""
    if champ == "exemples":
        return grille_ecriture.exemples(valeur)
    if champ == "lien":
        return bool(valeur)
    if champ == "forme":
        return grille_ecriture.forme(valeur)
    if champ == "cardinalite":
        return grille_ecriture.cardinalite(valeur)
    if champ in ("cible", "porte_sur"):
        stockee, erreur = grille_ecriture.cibles(valeur)
        if erreur:
            raise _refus("cible_inconnue" if champ == "cible" else "porte_sur_inconnu", erreur,
                         cle=cle, colonne=champ)
        return stockee
    return grille_ecriture.texte(valeur)


def _verifier_vu(conn, g, objet: str, vu, permis, actuel: dict, nouveau: dict) -> None:
    """CONC-3 : pour chaque champ que l'écran déclare avoir vu ET qu'il change, la valeur
    vue doit être celle qui est écrite — sinon `conflit.Perime`, qui nomme l'auteur par
    l'acte du journal dont la charge porte cet `objet`."""
    vu = vu or {}
    inconnus = set(vu) - set(permis)
    if inconnus:
        raise HTTPException(422, f"« vu » ne porte que {', '.join(permis)} : "
                                 f"{', '.join(sorted(inconnus))} n'en est pas.")
    for champ, valeur in vu.items():
        if champ in nouveau:
            conflit.verifier(conn, "grille", g["id"], champ,
                             vu=_norme(champ, valeur), actuel=actuel.get(champ),
                             nouveau=nouveau[champ], objet=("objet", objet))


def _charge(objet: str, version: int, champs: dict | None) -> dict | None:
    return None if champs is None else {"objet": objet, "version": version, **champs}


def _vue_entree(e: dict) -> dict:
    """Une entrée telle que le journal la garde : ses champs, et ses variantes nommées."""
    return {**{k: e[k] for k in grille_ecriture.CHAMPS_ENTREE}, "retiree": bool(e["retiree"]),
            "variantes": {vc: x["libelle"] for vc, x in e["variantes"].items()}}


def _version_montree(conn, g):
    """La version que le formulaire montre quand rien ne s'écrit : la vivante, le brouillon,
    ou la dernière publiée."""
    return (grilles.derniere_version(conn, g["id"], grilles.ETAT_VIVANTE)
            or grilles.derniere_version(conn, g["id"], grilles.ETAT_BROUILLON)
            or grilles.derniere_version(conn, g["id"], grilles.ETAT_PUBLIEE))


def _reponse(conn, g, v, *, cree: bool, cle=None, a_savoir=(), fusions=()) -> dict:
    """La réponse d'un geste : la version écrite, son PLAN que le formulaire redessine, et ce
    que les relevés y emploient (`grille_ecriture.emplois`) — de quoi n'offrir ensuite que
    les gestes que le serveur accepte."""
    v = dict(v)
    return {"grille_id": g["id"], "version": {"numero": v["numero"], "etat": v["etat"]},
            "brouillon_cree": cree, "cle": cle, "a_savoir": list(a_savoir),
            "fusions": [{k: f[k] for k in ("de", "dans", "releve_ids")} for f in fusions],
            "plan": grilles.plan(conn, v["id"]),
            "emplois": grille_ecriture.emplois(conn, g, v, grilles.contenu(conn, v["id"]))}


def _ecrire(conn, portee, grille_id: int, geste) -> dict:
    """Le patron de chaque geste du formulaire. `geste(g, v, avant, apres, ref)` change
    `apres` (une copie du contenu de la version en écriture) et rend `{"cle", "actes",
    "reponses"?, "note"?}` — `actes` : (type, objet, avant, après) à écrire au journal ; vide,
    rien ne change, et rien ne s'écrit (pas même un brouillon). Ici : le verrou, le droit, la
    version, la relecture entière (`grille_ecriture.ecrire`), le journal, le commit."""
    conflit.verrouiller(conn)
    g = _get_grille(conn, portee, grille_id, gerer=True)
    conn.execute("SAVEPOINT geste")       # ce qu'on défait si rien ne change, et rien d'autre
    try:
        v, cree = grille_ecriture.version_en_ecriture(conn, g, par=portee.utilisateur)
        avant = grilles.contenu(conn, v["id"])
        apres = copy.deepcopy(avant)
        fait = geste(g, v, avant, apres, grille_ecriture.reference(conn, g["id"]))
        if not fait["actes"]:
            conn.execute("ROLLBACK TO geste")
            conn.execute("RELEASE geste")
            conn.commit()
            return _reponse(conn, g, _version_montree(conn, g), cree=False, cle=fait["cle"])
        a_savoir, fusions = grille_ecriture.ecrire(conn, g, v, avant, apres,
                                                   note=fait.get("note", v["note"]),
                                                   reponses=fait.get("reponses"))
    except grille_import.Refus as exc:
        raise _refus_http(exc)
    except conflit.Perime as exc:
        raise HTTPException(409, exc.detail())
    faites = {f"entree:{f['de']}": f["releve_ids"] for f in fusions}
    for type_, objet, av, ap in fait["actes"]:
        if objet in faites and ap is not None:
            ap = {**ap, "releve_ids": faites[objet]}
        journal.journaliser(conn, type_, "grille", g["id"],
                            avant=_charge(objet, v["numero"], av),
                            apres=_charge(objet, v["numero"], ap))
    conn.commit()
    return _reponse(conn, g, v, cree=cree, cle=fait["cle"], a_savoir=a_savoir,
                    fusions=fusions)


def _modifier(objet: str, cible: dict, d: dict, champs, *, conn, g, vu, cle=None):
    """Applique à `cible` (un objet du contenu) les champs de `d` qui CHANGENT, après la
    garde de `vu`. Rend (avant, après) des champs changés — vides si rien ne change."""
    nouveaux = {c: _norme(c, d[c], cle=cle) for c in champs if c in d}
    _verifier_vu(conn, g, objet, vu, champs, cible, nouveaux)
    changes = {c: x for c, x in nouveaux.items() if x != cible.get(c)}
    av = {c: cible.get(c) for c in changes}
    cible.update(changes)
    return av, changes


def _introuvable(quoi: str, cle: str, v) -> HTTPException:
    return HTTPException(404, f"{quoi} « {cle} » introuvable dans la version {v['numero']}.")


@router.post("/api/projets/{projet_id}/grilles", status_code=201)
def creer_grille(projet_id: int, payload: GrilleIn, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """CRÉE une grille sans import, VIDE : fermée, son brouillon 1 ; ouverte, sa version
    vivante 1. Un nom unique dans le projet (409 nommé, la règle de l'import), « Porte sur »
    exigé (422). Une grille vide ne se publie pas. À qui gère le projet ; jamais dans le
    projet de jeu ; dans un bac à sable, oui (G6)."""
    _get_projet(conn, portee, projet_id, gerer=True, motif=_MOTIF_GERER)
    _refuser_le_jeu(conn, projet_id=projet_id)
    conflit.verrouiller(conn)
    nom = grilles.propre(payload.nom)
    try:
        if not nom:
            raise _refus("libelle_vide", "la grille n'a pas de nom", "donnez-lui un nom",
                         colonne="nom")
        if grille_import.nom_pris(conn, projet_id, nom):
            raise grille_import.Refus(409, f"Une grille de ce projet s'appelle déjà « {nom} » :"
                                           " choisissez un autre nom.")
        porte_sur = _norme("porte_sur", payload.porte_sur)
        if porte_sur is None:
            raise _refus("porte_sur_manque", "« Porte sur » manque : sur quoi la grille se "
                         "pose-t-elle ?", "des mots, la case, la planche, ou des sortes de "
                         "zone", colonne="porte_sur")
    except grille_import.Refus as exc:
        raise _refus_http(exc)
    gid = conn.execute("INSERT INTO grille (projet_id, nom, ouverte, cree_par) "
                       "VALUES (?, ?, ?, ?)", (projet_id, nom, int(payload.ouverte),
                                               portee.utilisateur)).lastrowid
    etat = grilles.ETAT_VIVANTE if payload.ouverte else grilles.ETAT_BROUILLON
    grille_import.ecrire_version(conn, gid, {"cible": porte_sur, "rubriques": {},
                                             "entrees": {}, "listes": {}},
                                 numero=1, etat=etat, note=grilles.propre(payload.note),
                                 par=portee.utilisateur)
    journal.journaliser(conn, "creation", "grille", gid,
                        apres={"projet_id": projet_id, "nom": nom,
                               "ouverte": payload.ouverte, "porte_sur": porte_sur,
                               "version": {"numero": 1, "etat": etat}})
    conn.commit()
    g = {**_row(conn.execute("SELECT * FROM grille WHERE id = ?", (gid,))), "gerable": True}
    return _reponse(conn, g, grilles.version(conn, gid, 1), cree=False)


@router.patch("/api/grilles/{grille_id}")
def modifier_grille(grille_id: int, payload: GrillePatch, conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Renomme une grille (`nom`, sur la grille : aucune version ne naît), ou change ce sur
    quoi elle porte d'ordinaire et sa note de version (`porte_sur`, `note` : dans la version
    en écriture). Sa nature, fermée ou ouverte, ne change pas (422 : le corps la refuse).
    `vu` : `nom`, `porte_sur`, `note`."""
    d = payload.model_dump(exclude_unset=True)
    vu = d.pop("vu", None) or {}
    if set(vu) - {"nom", "porte_sur", "note"}:
        raise HTTPException(422, "« vu » ne porte que nom, porte_sur, note.")
    if "nom" in d:
        conflit.verrouiller(conn)
        g = _get_grille(conn, portee, grille_id, gerer=True)
        nom = grilles.propre(d["nom"])
        if not nom:
            raise _refus_http(_refus("libelle_vide", "la grille n'a pas de nom",
                                     "donnez-lui un nom", colonne="nom"))
        try:
            _verifier_vu(conn, g, "grille", {k: x for k, x in vu.items() if k == "nom"},
                         ("nom",), {"nom": g["nom"]}, {"nom": nom})
        except conflit.Perime as exc:
            raise HTTPException(409, exc.detail())
        if nom != g["nom"]:
            if grille_import.nom_pris(conn, g["projet_id"], nom, sauf=grille_id):
                raise HTTPException(409, f"Une grille de ce projet s'appelle déjà « {nom} ».")
            conn.execute("UPDATE grille SET nom = ? WHERE id = ?", (nom, grille_id))
            journal.journaliser(conn, "modification", "grille", grille_id,
                                avant={"objet": "grille", "nom": g["nom"]},
                                apres={"objet": "grille", "nom": nom})
    if not {"porte_sur", "note"} & set(d):
        g = _get_grille(conn, portee, grille_id, gerer=True)
        conn.commit()
        return _reponse(conn, g, _version_montree(conn, g), cree=False)

    def geste(g, v, avant, apres, ref):
        actuel = {"porte_sur": apres["cible"], "note": v["note"]}
        nouveaux = {c: _norme(c, d[c]) for c in ("porte_sur", "note") if c in d}
        _verifier_vu(conn, g, "grille", {k: x for k, x in vu.items() if k != "nom"},
                     ("porte_sur", "note"), actuel, nouveaux)
        changes = {c: x for c, x in nouveaux.items() if x != actuel[c]}
        if "porte_sur" in changes:
            apres["cible"] = changes["porte_sur"]
        return {"cle": None, "note": changes.get("note", v["note"]),
                "actes": [("modification", "grille", {c: actuel[c] for c in changes},
                           changes)] if changes else []}
    return _ecrire(conn, portee, grille_id, geste)


# -- Les rubriques ------------------------------------------------------------ #
@router.post("/api/grilles/{grille_id}/rubriques", status_code=201)
def creer_rubrique(grille_id: int, payload: RubriqueIn, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Une rubrique, au premier niveau ou sous `parent_cle`. Son identifiant, s'il n'est pas
    donné, se reçoit de son chemin (la dérivation de l'import). Une rubrique vide se garde
    dans le formulaire ; le tableur, qui ne connaît une rubrique que par ses entrées, ne la
    réexporte pas."""
    def geste(g, v, avant, apres, ref):
        libelle = grilles.propre(payload.libelle)
        if not libelle:
            raise _refus("libelle_vide", "la rubrique n'a pas de nom", "donnez-lui un nom",
                         colonne="rubrique")
        parent = grilles.propre(payload.parent_cle)
        cle = grille_ecriture.cle_donnee(payload.cle, rubrique=True)
        if cle is None:
            cle = grille_ecriture.cle_neuve(
                grille_ecriture.chemin(apres["rubriques"], parent, libelle),
                deja=apres["rubriques"], ref=(ref or {}).get("rubriques"),
                defaut="rubrique", quoi="rubrique", texte_=libelle)
        elif cle in apres["rubriques"]:
            raise _refus("rubrique_deux_identifiants", f"l'identifiant « {cle} » est déjà "
                         "celui d'une rubrique", "donnez-lui un autre identifiant", cle=cle,
                         colonne="rubrique_cle")
        apres["rubriques"][cle] = {"libelle": libelle, "parent_cle": parent,
                                   "rang": grille_ecriture.rang_suivant(apres["rubriques"])}
        return {"cle": cle, "actes": [("creation", f"rubrique:{cle}", None,
                                       {"libelle": libelle, "parent_cle": parent})]}
    return _ecrire(conn, portee, grille_id, geste)


@router.patch("/api/grilles/{grille_id}/rubriques/{cle}")
def modifier_rubrique(grille_id: int, cle: str, payload: RubriquePatch,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Renomme une rubrique ou la range ailleurs (`parent_cle`, vide : au premier niveau).
    `vu` : `libelle`, `parent_cle`."""
    d = payload.model_dump(exclude_unset=True)
    vu = d.pop("vu", None)

    def geste(g, v, avant, apres, ref):
        r = apres["rubriques"].get(cle)
        if r is None:
            raise _introuvable("Rubrique", cle, v)
        av, ap = _modifier(f"rubrique:{cle}", r, d, grille_ecriture.CHAMPS_RUBRIQUE,
                           conn=conn, g=g, vu=vu, cle=cle)
        return {"cle": cle, "actes": [("modification", f"rubrique:{cle}", av, ap)] if ap else []}
    return _ecrire(conn, portee, grille_id, geste)


@router.delete("/api/grilles/{grille_id}/rubriques/{cle}")
def supprimer_rubrique(grille_id: int, cle: str, conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime une rubrique VIDE — ni entrée (retirées comprises), ni rubrique rangée sous
    elle : 409 nommé sinon (« on ne la supprime que vide », maquette du 2026-11-03)."""
    def geste(g, v, avant, apres, ref):
        r = apres["rubriques"].get(cle)
        if r is None:
            raise _introuvable("Rubrique", cle, v)
        n_e = sum(1 for e in apres["entrees"].values() if e["rubrique_cle"] == cle)
        n_r = sum(1 for x in apres["rubriques"].values() if x["parent_cle"] == cle)
        if n_e or n_r:
            raise grille_import.Refus(409, f"La rubrique « {r['libelle']} » range {n_e} "
                                           f"entrée(s) et {n_r} rubrique(s) : elle ne se "
                                           "supprime que vide. Rangez-les ailleurs d'abord.")
        del apres["rubriques"][cle]
        return {"cle": cle, "actes": [("suppression", f"rubrique:{cle}",
                                       {"libelle": r["libelle"], "parent_cle": r["parent_cle"]},
                                       None)]}
    return _ecrire(conn, portee, grille_id, geste)


# -- Les entrées ------------------------------------------------------------- #
def _variante_neuve(e: dict, x: dict, ref_entree: dict | None, *, entree_cle: str) -> str:
    """Ajoute à l'entrée `e` la variante décrite par `x` ; rend son identifiant."""
    libelle = grilles.propre(x.get("libelle"))
    if not libelle:
        raise _refus("variante_sans_nom", "la variante n'a pas de nom", "donnez-lui un nom",
                     cle=entree_cle, colonne="variante")
    vc = grille_ecriture.cle_donnee(x.get("cle"))
    if vc is None:
        vc = grille_ecriture.cle_neuve(libelle, deja=e["variantes"],
                                       ref=(ref_entree or {}).get("variantes"),
                                       defaut="variante", quoi="variante")
    elif vc in e["variantes"]:
        raise _refus("variante_en_double", f"la variante « {vc} » est déjà sous l'entrée",
                     "donnez-lui un autre identifiant", cle=entree_cle, colonne="variante")
    e["variantes"][vc] = {"libelle": libelle, "rang": grille_ecriture.rang_suivant(e["variantes"]),
                          **{c: _norme(c, x.get(c)) for c in ("definition", "structure",
                                                              "piege", "exemples")}}
    return vc


def _employee(conn, g, cle: str) -> int:
    return grille_ecriture.releves_sur(conn, g["id"], cle)


@router.post("/api/grilles/{grille_id}/entrees", status_code=201)
def creer_entree(grille_id: int, payload: EntreeIn, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Une entrée, avec ses réponses aux six questions et ce que lit l'annotateur ; une
    entrée à variantes arrive AVEC ses variantes (`variantes`), une entrée à cocher avec une
    liste qui a des cases — les refus de l'import (422). Son identifiant, s'il n'est pas
    donné, se reçoit de son nom (la dérivation de l'import)."""
    d = payload.model_dump(exclude_unset=True)

    def geste(g, v, avant, apres, ref):
        libelle = grilles.propre(d.get("libelle"))
        if not libelle:
            raise _refus("libelle_vide", "l'entrée n'a pas de nom", "donnez-lui un nom",
                         colonne="libelle")
        cle = grille_ecriture.cle_donnee(d.get("cle"))
        if cle is None:
            cle = grille_ecriture.cle_neuve(libelle, deja=apres["entrees"],
                                            ref=(ref or {}).get("entrees"), defaut="entree",
                                            quoi="entree")
        elif cle in apres["entrees"]:
            raise _refus("cle_en_double", f"l'identifiant « {cle} » est déjà celui d'une "
                         "autre entrée", "donnez-lui un autre identifiant", cle=cle,
                         colonne="cle")
        e = {"rubrique_cle": None, "rang": grille_ecriture.rang_suivant(apres["entrees"]),
             "forme": "simple", "libelle": libelle, "definition": None, "structure": None,
             "piege": None, "precision": None, "lien": False, "cible": None,
             "cardinalite": None, "liste_cle": None, "retiree": False, "exemples": [],
             "variantes": {}}
        e.update({c: _norme(c, d[c], cle=cle) for c in grille_ecriture.CHAMPS_ENTREE
                  if c in d and c != "libelle"})
        for x in d.get("variantes") or []:
            _variante_neuve(e, x, (ref or {}).get("entrees", {}).get(cle), entree_cle=cle)
        apres["entrees"][cle] = e
        return {"cle": cle, "actes": [("creation", f"entree:{cle}", None, _vue_entree(e))]}
    return _ecrire(conn, portee, grille_id, geste)


@router.patch("/api/grilles/{grille_id}/entrees/{cle}")
def modifier_entree(grille_id: int, cle: str, payload: EntreePatch,
                    conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Modifie une entrée — son nom, sa rubrique, ses réponses, ce que lit l'annotateur — et
    lui AJOUTE des variantes (`variantes` : c'est ainsi qu'une entrée devient « à variantes »).
    Quitter « des cases d'une liste » délie sa liste ; quitter « une variante » demande
    d'avoir retiré ses variantes (422). Sur une grille ouverte, une entrée employée ne change
    ni de forme ni de liste (409, la règle du réimport). `vu` : les champs de l'entrée."""
    d = payload.model_dump(exclude_unset=True)
    vu = d.pop("vu", None)
    neuves = d.pop("variantes", None) or []

    def geste(g, v, avant, apres, ref):
        e = apres["entrees"].get(cle)
        if e is None:
            raise _introuvable("Entrée", cle, v)
        champs = dict(d)
        if ("forme" in champs and _norme("forme", champs["forme"]) != "qualificatifs"
                and "liste_cle" not in champs):
            champs["liste_cle"] = None
        av, ap = _modifier(f"entree:{cle}", e, champs, grille_ecriture.CHAMPS_ENTREE,
                           conn=conn, g=g, vu=vu, cle=cle)
        actes = [("modification", f"entree:{cle}", av, ap)] if ap else []
        for x in neuves:
            vc = _variante_neuve(e, x, (ref or {}).get("entrees", {}).get(cle), entree_cle=cle)
            actes.append(("creation", f"variante:{cle}/{vc}", None,
                          {c: e["variantes"][vc][c] for c in grille_ecriture.CHAMPS_VARIANTE}))
        return {"cle": cle, "actes": actes}
    return _ecrire(conn, portee, grille_id, geste)


@router.delete("/api/grilles/{grille_id}/entrees/{cle}")
def supprimer_entree(grille_id: int, cle: str, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime une entrée que PERSONNE n'emploie. Une entrée employée — un relevé la porte,
    dans quelque version que ce soit — ne se supprime jamais (tranché par Hugo le
    2026-11-03) : 409 nommé, qui dit ce qu'on peut faire — la retirer, ou, sur une grille
    ouverte, la fusionner dans une entrée qui peut recevoir ses relevés (`fusionner_dans`)."""
    def geste(g, v, avant, apres, ref):
        e = apres["entrees"].get(cle)
        if e is None:
            raise _introuvable("Entrée", cle, v)
        n = _employee(conn, g, cle)
        if n:
            choix, vers = [grille_import.RETIRER], []
            if v["etat"] == grilles.ETAT_VIVANTE:
                sans = {**apres, "entrees": {k: x for k, x in apres["entrees"].items()
                                             if k != cle}}
                employees = {r[0] for r in conn.execute(
                    "SELECT DISTINCT variante_cle FROM releve WHERE grille_id = ? "
                    "AND version_id = ? AND entree_cle = ? AND variante_cle IS NOT NULL",
                    (g["id"], v["id"], cle))}
                vers = grille_import._vers_possibles(avant, sans, cle, employees)
                choix.append(grille_import.FUSIONNER)
            raise grille_import.Refus(
                409, f"{n} relevé(s) portent « {e['libelle']} » : elle ne se supprime pas. "
                     + ("Retirez-la, ou fusionnez-la dans une autre." if len(choix) > 1
                        else "Retirez-la : ses relevés restent lisibles dans leur version."),
                [], {"a_repondre": [{"cle": cle, "libelle": e["libelle"], "releves": n,
                                     "choix": choix, "fusionner_dans": vers}]})
        del apres["entrees"][cle]
        return {"cle": cle, "actes": [("suppression", f"entree:{cle}", _vue_entree(e), None)]}
    return _ecrire(conn, portee, grille_id, geste)


def _retrait(conn, portee, grille_id: int, cle: str, retiree: bool) -> dict:
    def geste(g, v, avant, apres, ref):
        e = apres["entrees"].get(cle)
        if e is None:
            raise _introuvable("Entrée", cle, v)
        if bool(e["retiree"]) == retiree:
            return {"cle": cle, "actes": []}
        e["retiree"] = retiree
        return {"cle": cle, "actes": [("modification", f"entree:{cle}",
                                       {"retiree": not retiree}, {"retiree": retiree})]}
    return _ecrire(conn, portee, grille_id, geste)


@router.post("/api/grilles/{grille_id}/entrees/{cle}/retrait")
def retirer_entree(grille_id: int, cle: str, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """RETIRE une entrée, ce que fait le réimport d'une grille ouverte : elle reste dans la
    version, ne se pose plus, et ses relevés restent, « à revoir » (`releves_effectifs`).
    Dans le brouillon d'une grille fermée, la version suivante la portera retirée."""
    return _retrait(conn, portee, grille_id, cle, True)


@router.delete("/api/grilles/{grille_id}/entrees/{cle}/retrait")
def remettre_entree(grille_id: int, cle: str, conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Remet en usage une entrée retirée — ce que fait le réimport d'un fichier qui la porte
    de nouveau."""
    return _retrait(conn, portee, grille_id, cle, False)


@router.post("/api/grilles/{grille_id}/entrees/{cle}/fusion")
def fusionner_entree(grille_id: int, cle: str, payload: FusionIn,
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """FUSIONNE une entrée employée dans une autre, ce que fait le réimport d'une grille
    ouverte : ses relevés passent à l'entrée d'arrivée, et elle quitte la version. Seulement
    vers une entrée de même forme, posée de la même manière, de la même liste, qui porte
    ses variantes employées, et sans poser deux fois une entrée « une seule fois »
    (`grille_import._vers_possibles`, `_fusion_en_double` : 409 et la faute). Sur une grille
    FERMÉE, refusé (409 nommé) : ses relevés vivent dans leur version publiée, que rien ne
    change ; on y retire l'entrée du brouillon. Sur une entrée que personne n'emploie : rien
    à fusionner, elle se supprime (409 nommé)."""
    def geste(g, v, avant, apres, ref):
        e = apres["entrees"].get(cle)
        if e is None:
            raise _introuvable("Entrée", cle, v)
        if v["etat"] != grilles.ETAT_VIVANTE:
            raise grille_import.Refus(409, "Une grille fermée ne fusionne pas : ses relevés "
                                           "vivent dans leur version publiée, qui ne change "
                                           "plus. Retirez l'entrée du brouillon.")
        if not _employee(conn, g, cle):
            raise grille_import.Refus(409, f"Aucun relevé ne porte « {e['libelle']} » : il "
                                           "n'y a rien à fusionner. Supprimez-la.")
        dans = grilles.propre(payload.dans)
        del apres["entrees"][cle]
        return {"cle": cle, "reponses": {cle: (grille_import.FUSIONNER, dans)},
                "actes": [("suppression", f"entree:{cle}", _vue_entree(e),
                           {"fusionnee_dans": dans})]}
    return _ecrire(conn, portee, grille_id, geste)


# -- Les variantes ------------------------------------------------------------ #
@router.post("/api/grilles/{grille_id}/entrees/{cle}/variantes", status_code=201)
def creer_variante(grille_id: int, cle: str, payload: VarianteIn,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Une variante de plus sous une entrée à variantes (422 sous une autre forme)."""
    def geste(g, v, avant, apres, ref):
        e = apres["entrees"].get(cle)
        if e is None:
            raise _introuvable("Entrée", cle, v)
        vc = _variante_neuve(e, payload.model_dump(exclude_unset=True),
                             (ref or {}).get("entrees", {}).get(cle), entree_cle=cle)
        return {"cle": vc, "actes": [("creation", f"variante:{cle}/{vc}", None,
                                      {c: e["variantes"][vc][c]
                                       for c in grille_ecriture.CHAMPS_VARIANTE})]}
    return _ecrire(conn, portee, grille_id, geste)


@router.patch("/api/grilles/{grille_id}/entrees/{cle}/variantes/{variante_cle}")
def modifier_variante(grille_id: int, cle: str, variante_cle: str, payload: VariantePatch,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Modifie une variante : son nom, ce que lit l'annotateur. `vu` : ses champs."""
    d = payload.model_dump(exclude_unset=True)
    vu = d.pop("vu", None)

    def geste(g, v, avant, apres, ref):
        x = (apres["entrees"].get(cle) or {}).get("variantes", {}).get(variante_cle)
        if x is None:
            raise _introuvable("Variante", f"{cle}/{variante_cle}", v)
        objet = f"variante:{cle}/{variante_cle}"
        av, ap = _modifier(objet, x, d, grille_ecriture.CHAMPS_VARIANTE, conn=conn, g=g,
                           vu=vu, cle=cle)
        return {"cle": variante_cle, "actes": [("modification", objet, av, ap)] if ap else []}
    return _ecrire(conn, portee, grille_id, geste)


@router.delete("/api/grilles/{grille_id}/entrees/{cle}/variantes/{variante_cle}")
def supprimer_variante(grille_id: int, cle: str, variante_cle: str,
                       conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime une variante que personne n'emploie (409 nommé sinon, sur une grille fermée
    comme sur une ouverte : rien ne la retire, et ses relevés la nomment). La dernière d'une
    entrée à variantes ne se supprime pas (422, la règle de l'import)."""
    def geste(g, v, avant, apres, ref):
        e = apres["entrees"].get(cle)
        x = (e or {}).get("variantes", {}).get(variante_cle)
        if x is None:
            raise _introuvable("Variante", f"{cle}/{variante_cle}", v)
        n = grille_ecriture.releves_sur(conn, g["id"], cle, variante_cle)
        if n:
            raise grille_import.Refus(409, f"{n} relevé(s) portent la variante "
                                           f"« {x['libelle']} » : elle ne se supprime pas.")
        del e["variantes"][variante_cle]
        objet = f"variante:{cle}/{variante_cle}"
        return {"cle": variante_cle, "actes": [("suppression", objet, {
            c: x[c] for c in grille_ecriture.CHAMPS_VARIANTE}, None)]}
    return _ecrire(conn, portee, grille_id, geste)


# -- Les listes et leurs cases ------------------------------------------------ #
def _case_neuve(liste: dict, x: dict, ref_liste: dict | None, *, liste_cle: str) -> str:
    libelle = grilles.propre(x.get("libelle"))
    if not libelle:
        raise _refus("libelle_vide", "la case n'a pas de nom", "donnez-lui un nom",
                     cle=liste_cle, colonne="libelle")
    qc = grille_ecriture.cle_donnee(x.get("cle"))
    if qc is None:
        qc = grille_ecriture.cle_neuve(libelle, deja=liste["qualificatifs"],
                                       ref=(ref_liste or {}).get("qualificatifs"),
                                       defaut="case", quoi="qualificatif")
    elif qc in liste["qualificatifs"]:
        raise _refus("qualificatif_en_double", f"la case « {qc} » est déjà dans la liste",
                     "donnez-lui un autre identifiant", cle=qc, colonne="libelle")
    liste["qualificatifs"][qc] = {"libelle": libelle,
                                  "definition": grilles.propre(x.get("definition")),
                                  "rang": grille_ecriture.rang_suivant(liste["qualificatifs"])}
    return qc


@router.post("/api/grilles/{grille_id}/listes", status_code=201)
def creer_liste(grille_id: int, payload: ListeIn, conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    """Une liste à cocher, avec ses cases (`cases`) ou vide ; une entrée ne la nomme qu'une
    fois qu'elle a une case. Son identifiant, s'il n'est pas donné, se reçoit de son nom."""
    def geste(g, v, avant, apres, ref):
        libelle = grilles.propre(payload.libelle)
        if not libelle:
            raise _refus("libelle_vide", "la liste n'a pas de nom", "donnez-lui un nom",
                         colonne="liste")
        lc = grille_ecriture.cle_donnee(payload.cle)
        if lc is None:
            lc = grille_ecriture.cle_neuve(libelle, deja=apres["listes"],
                                           ref=(ref or {}).get("listes"), defaut="liste",
                                           quoi="liste")
        elif lc in apres["listes"]:
            raise _refus("liste_en_double", f"l'identifiant « {lc} » est déjà celui d'une "
                         "liste", "donnez-lui un autre identifiant", cle=lc, colonne="liste")
        liste = apres["listes"][lc] = {"libelle": libelle, "qualificatifs": {}}
        ref_l = (ref or {}).get("listes", {}).get(lc)
        for x in payload.model_dump(exclude_unset=True).get("cases") or []:
            _case_neuve(liste, x, ref_l, liste_cle=lc)
        return {"cle": lc, "actes": [("creation", f"liste:{lc}", None, {
            "libelle": libelle, "cases": {qc: q["libelle"]
                                          for qc, q in liste["qualificatifs"].items()}})]}
    return _ecrire(conn, portee, grille_id, geste)


@router.patch("/api/grilles/{grille_id}/listes/{liste_cle}")
def modifier_liste(grille_id: int, liste_cle: str, payload: ListePatch,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Renomme une liste. `vu` : `libelle`."""
    d = payload.model_dump(exclude_unset=True)
    vu = d.pop("vu", None)

    def geste(g, v, avant, apres, ref):
        liste = apres["listes"].get(liste_cle)
        if liste is None:
            raise _introuvable("Liste", liste_cle, v)
        if "libelle" in d and not grilles.propre(d["libelle"]):
            raise _refus("libelle_vide", "la liste n'a pas de nom", "donnez-lui un nom",
                         cle=liste_cle, colonne="liste")
        av, ap = _modifier(f"liste:{liste_cle}", liste, d, grille_ecriture.CHAMPS_LISTE,
                           conn=conn, g=g, vu=vu)
        return {"cle": liste_cle,
                "actes": [("modification", f"liste:{liste_cle}", av, ap)] if ap else []}
    return _ecrire(conn, portee, grille_id, geste)


@router.delete("/api/grilles/{grille_id}/listes/{liste_cle}")
def supprimer_liste(grille_id: int, liste_cle: str, conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime une liste qu'aucune entrée ne nomme (retirées comprises : 409 nommé sinon) ;
    ses cases partent avec elle — sur une grille ouverte, une case qu'un relevé coche ne
    disparaît pas (409, la règle du réimport)."""
    def geste(g, v, avant, apres, ref):
        liste = apres["listes"].get(liste_cle)
        if liste is None:
            raise _introuvable("Liste", liste_cle, v)
        sert = [e["libelle"] for e in apres["entrees"].values()
                if e["liste_cle"] == liste_cle]
        if sert:
            raise grille_import.Refus(409, f"La liste « {liste['libelle'] or liste_cle} » sert "
                                           f"à {len(sert)} entrée(s) ({', '.join(sert)}) : "
                                           "elle ne se supprime pas.")
        del apres["listes"][liste_cle]
        return {"cle": liste_cle, "actes": [("suppression", f"liste:{liste_cle}", {
            "libelle": liste["libelle"],
            "cases": {qc: q["libelle"] for qc, q in liste["qualificatifs"].items()}}, None)]}
    return _ecrire(conn, portee, grille_id, geste)


@router.post("/api/grilles/{grille_id}/listes/{liste_cle}/cases", status_code=201)
def creer_case(grille_id: int, liste_cle: str, payload: CaseIn,
               conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    """Une case de plus dans une liste — elle s'offre à toutes les entrées qui la nomment."""
    def geste(g, v, avant, apres, ref):
        liste = apres["listes"].get(liste_cle)
        if liste is None:
            raise _introuvable("Liste", liste_cle, v)
        qc = _case_neuve(liste, payload.model_dump(exclude_unset=True),
                         (ref or {}).get("listes", {}).get(liste_cle), liste_cle=liste_cle)
        q = liste["qualificatifs"][qc]
        return {"cle": qc, "actes": [("creation", f"case:{liste_cle}/{qc}", None,
                                      {c: q[c] for c in grille_ecriture.CHAMPS_CASE})]}
    return _ecrire(conn, portee, grille_id, geste)


@router.patch("/api/grilles/{grille_id}/listes/{liste_cle}/cases/{case_cle}")
def modifier_case(grille_id: int, liste_cle: str, case_cle: str, payload: CasePatch,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Renomme une case, ou change sa définition. `vu` : `libelle`, `definition`."""
    d = payload.model_dump(exclude_unset=True)
    vu = d.pop("vu", None)

    def geste(g, v, avant, apres, ref):
        q = (apres["listes"].get(liste_cle) or {}).get("qualificatifs", {}).get(case_cle)
        if q is None:
            raise _introuvable("Case", f"{liste_cle}/{case_cle}", v)
        if "libelle" in d and not grilles.propre(d["libelle"]):
            raise _refus("libelle_vide", "la case n'a pas de nom", "donnez-lui un nom",
                         cle=case_cle, colonne="libelle")
        objet = f"case:{liste_cle}/{case_cle}"
        av, ap = _modifier(objet, q, d, grille_ecriture.CHAMPS_CASE, conn=conn, g=g, vu=vu,
                           cle=case_cle)
        return {"cle": case_cle, "actes": [("modification", objet, av, ap)] if ap else []}
    return _ecrire(conn, portee, grille_id, geste)


@router.delete("/api/grilles/{grille_id}/listes/{liste_cle}/cases/{case_cle}")
def supprimer_case(grille_id: int, liste_cle: str, case_cle: str,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime une case qu'aucun relevé ne coche (409 nommé sinon, sur une grille fermée
    comme sur une ouverte). La dernière case d'une liste qu'une entrée nomme ne se supprime
    pas (422)."""
    def geste(g, v, avant, apres, ref):
        liste = apres["listes"].get(liste_cle)
        q = (liste or {}).get("qualificatifs", {}).get(case_cle)
        if q is None:
            raise _introuvable("Case", f"{liste_cle}/{case_cle}", v)
        n = grille_ecriture.releves_sur_case(conn, g["id"], case_cle)
        if n:
            raise grille_import.Refus(409, f"{n} relevé(s) cochent la case « {q['libelle']} » :"
                                           " elle ne se supprime pas.")
        del liste["qualificatifs"][case_cle]
        objet = f"case:{liste_cle}/{case_cle}"
        return {"cle": case_cle, "actes": [("suppression", objet, {
            c: q[c] for c in grille_ecriture.CHAMPS_CASE}, None)]}
    return _ecrire(conn, portee, grille_id, geste)


# -- L'ordre ------------------------------------------------------------------ #
_ORDONNABLES = ("rubrique", "entree", "variante", "case")


class OrdreIn(_Strict):
    """Ranger un objet à une PLACE parmi ses frères : une rubrique parmi celles de même
    parent, une entrée parmi celles de sa rubrique, une variante parmi celles de son entrée,
    une case parmi celles de sa liste. `place` : son rang parmi eux, à partir de 0. `vu` :
    l'ordre des frères que l'écran voyait (leurs identifiants)."""
    quoi: str
    cle: str
    entree_cle: Optional[str] = None
    liste_cle: Optional[str] = None
    place: int
    vu: Optional[list[str]] = None


def _ranger(objets: dict, freres: list, neufs: list) -> None:
    """RENUMÉROTE les rangs de `objets` — tous ceux de la même sorte — de 0 à n : les
    `freres` reprennent, dans leur ordre neuf (`neufs`), les places qu'ils tenaient dans
    l'ordre entier, et les autres ne bougent pas."""
    places = iter(neufs)
    entier = [next(places) if k in freres else k for k in grilles._par_rang(objets)]
    for rang, k in enumerate(entier):
        objets[k]["rang"] = rang


@router.put("/api/grilles/{grille_id}/ordre")
def ranger_dans_la_grille(grille_id: int, payload: OrdreIn,
                          conn: sqlite3.Connection = Depends(db),
                          portee: autorisation.Portee = Depends(portee_courante)):
    """RANGE une rubrique, une entrée, une variante ou une case à une place parmi ses frères
    (`quoi`, `cle`, `entree_cle` pour une variante, `liste_cle` pour une case). L'ordre ne
    fait pas l'empreinte d'une version — réordonner les lignes du tableur n'en fait pas une
    (cadrage R3) —, mais il est ce que l'annotateur voit : sur une grille fermée, il s'écrit
    dans le brouillon comme tout geste du formulaire, et un brouillon qui ne change QUE
    l'ordre se publie. `vu` : l'ordre des frères que l'écran voyait — périmé, 409 de CONC-3,
    qui nomme qui l'a changé. Au journal, un acte sous la grille, dont l'objet nomme les
    frères (« ordre:entree:<rubrique> »). Une place hors des frères : 422."""
    if payload.quoi not in _ORDONNABLES:
        raise HTTPException(422, f"« quoi » est l'un de : {', '.join(_ORDONNABLES)}.")

    def geste(g, v, avant, apres, ref):
        quoi, cle = payload.quoi, payload.cle
        if quoi == "rubrique":
            r = apres["rubriques"].get(cle)
            if r is None:
                raise _introuvable("Rubrique", cle, v)
            objets, parent = apres["rubriques"], r["parent_cle"]
            freres = [k for k in grilles._par_rang(objets)
                      if objets[k]["parent_cle"] == parent]
        elif quoi == "entree":
            e = apres["entrees"].get(cle)
            if e is None:
                raise _introuvable("Entrée", cle, v)
            objets, parent = apres["entrees"], e["rubrique_cle"]
            freres = [k for k in grilles._par_rang(objets)
                      if objets[k]["rubrique_cle"] == parent]
        elif quoi == "variante":
            parent = payload.entree_cle
            e = apres["entrees"].get(parent or "")
            if e is None or cle not in e["variantes"]:
                raise _introuvable("Variante", f"{parent}/{cle}", v)
            objets = e["variantes"]
            freres = grilles._par_rang(objets)
        else:
            parent = payload.liste_cle
            liste = apres["listes"].get(parent or "")
            if liste is None or cle not in liste["qualificatifs"]:
                raise _introuvable("Case", f"{parent}/{cle}", v)
            objets = liste["qualificatifs"]
            freres = grilles._par_rang(objets)
        if not 0 <= payload.place < len(freres):
            raise HTTPException(422, f"La place {payload.place} n'existe pas : "
                                     f"{len(freres)} place(s), de 0 à {len(freres) - 1}.")
        objet = f"ordre:{quoi}:{parent or ''}"
        neufs = [k for k in freres if k != cle]
        neufs.insert(payload.place, cle)
        if payload.vu is not None:
            conflit.verifier(conn, "grille", g["id"], "ordre", vu=list(payload.vu),
                             actuel=freres, nouveau=neufs, objet=("objet", objet))
        if neufs == freres:
            return {"cle": cle, "actes": []}
        _ranger(objets, freres, neufs)
        return {"cle": cle, "actes": [("modification", objet, {"ordre": freres},
                                       {"ordre": neufs, "deplace": cle})]}
    return _ecrire(conn, portee, grille_id, geste)
