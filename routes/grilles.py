"""Les GRILLES d'annotation — importer, publier, activer, masquer, lire (ANN-7, tranche 1 ;
cadrage R2 à R4, R8 ; décisions de Hugo du 2026-10-25).

Sans écran : les routes que la fiche d'un projet (Administration › Projets) et la page
Annotation consommeront. Une grille s'écrit dans un tableur (`grille_import`), se garde en
BROUILLON, se PUBLIE en une version figée et numérotée, s'ACTIVE sur un projet dans une
version ; une collection du projet peut la MASQUER — un filtre d'écran, pas une garde (Q1).

Qui fait quoi (R8) — les décisions d'accès d'une grille sont celles de SON projet :
- importer, publier, supprimer un brouillon, retirer, supprimer une grille, corriger une
  coquille, réexporter, activer, désactiver : qui GÈRE le projet (`peut_gerer_projet` —
  son responsable, l'administrateur qui passe outre). 404 sur une grille ou un projet qu'on
  ne voit pas, 403 nommé sur ce qu'on voit sans le gérer ;
- masquer dans une collection : qui l'ADMINISTRE (`peut_administrer`, G7) ;
- lire le plan publié (ou vivant) : `Portee.clause_grille`, la seule question neuve ;
  lire un brouillon : qui gère le projet — « le brouillon reste chez ses auteurs ».

Le journal : tout s'écrit sous `grille` (`cible_id` = la grille), retenu de toute sortie et
sans rang (`tools/_commun.py`) — administrer un vocabulaire n'est pas annoter.
"""
from __future__ import annotations

import io
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

import autorisation
import conflit
import grille_import
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
def plan_de_version(grille_id: int, numero: int, conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Le PLAN entier d'une version (R13) — rubriques imbriquées, entrées avec leur cible et
    leur cardinalité effectives, la précision et le lien attendus, variantes, listes,
    définitions, structures, exemples, pièges —, de quoi filtrer côté écran sans aller-
    retour. Un brouillon, à qui gère le projet seulement."""
    g = _get_grille(conn, portee, grille_id)
    v = _get_version(conn, g, numero)
    return {"grille": {"id": g["id"], "nom": g["nom"], "ouverte": bool(g["ouverte"])},
            **grilles.plan(conn, v["id"])}


# --------------------------------------------------------------------------- #
# Importer, publier, retirer
# --------------------------------------------------------------------------- #
def _texte_de(fichier: UploadFile | None, quoi: str) -> io.StringIO | None:
    if fichier is None:
        return None
    data = fichier.file.read()
    if not data:
        raise HTTPException(400, f"Le fichier des {quoi} est vide.")
    try:
        return io.StringIO(data.decode("utf-8-sig"), newline="")
    except UnicodeDecodeError:
        raise HTTPException(400, f"Le fichier des {quoi} doit être encodé en UTF-8.")


def _refus_http(exc: grille_import.Refus) -> HTTPException:
    if exc.anomalies:
        return HTTPException(exc.statut, {"message": exc.message, "anomalies": exc.anomalies})
    return HTTPException(exc.statut, exc.message)


@router.post("/api/projets/{projet_id}/grilles/import")
def importer_grille(projet_id: int, fichier: UploadFile = File(...),
                    listes: Optional[UploadFile] = File(None),
                    grille_id: Optional[int] = Form(None, ge=1),
                    nom: Optional[str] = Form(None), ouverte: bool = Form(False),
                    porte_sur: Optional[str] = Form(None), note: Optional[str] = Form(None),
                    a_blanc: bool = Form(False),
                    conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Importe un tableur (R3) : une grille NEUVE (`nom`, `ouverte`, `porte_sur`) ou la
    version suivante d'une grille du projet (`grille_id`). Le fichier est vérifié ENTIER :
    une anomalie de structure le refuse (422, toutes les anomalies dites, rien d'écrit,
    G12). `a_blanc` rend le BILAN — ce qui naît, change, disparaît depuis la dernière
    version publiée — sans rien écrire. Réimporter le même fichier ne change rien.

    À qui gère le projet (404 / 403 nommé) ; jamais dans le projet de jeu. Dans un bac à
    sable, oui (G6) : la grille n'existe que là, et part avec lui."""
    _get_projet(conn, portee, projet_id, gerer=True, motif=_MOTIF_GERER)
    _refuser_le_jeu(conn, projet_id=projet_id)
    flux = _texte_de(fichier, "entrées")
    flux_listes = _texte_de(listes, "listes")
    conflit.verrouiller(conn)            # le nom unique et le brouillon se lisent sous le verrou
    try:
        res = grille_import.importer(conn, projet_id=projet_id, flux_entrees=flux,
                                     flux_listes=flux_listes, grille_id=grille_id, nom=nom,
                                     ouverte=ouverte, porte_sur=porte_sur, note=note,
                                     par=portee.utilisateur, a_blanc=a_blanc)
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
    409 nommé sur une version qui n'est pas un brouillon."""
    conflit.verrouiller(conn)
    g = _get_grille(conn, portee, grille_id, gerer=True)
    v = _get_version(conn, g, numero)
    if v["etat"] != grilles.ETAT_BROUILLON:
        raise HTTPException(409, f"La version {numero} n'est pas un brouillon : elle est "
                                 f"{v['etat']}.")
    conn.execute("UPDATE grille_version SET etat = ?, publiee_par = ?, "
                 "publiee_le = datetime('now') WHERE id = ?",
                 (grilles.ETAT_PUBLIEE, portee.utilisateur, v["id"]))
    journal.journaliser(conn, "modification", "grille", grille_id,
                        avant={"version": numero, "etat": grilles.ETAT_BROUILLON},
                        apres={"version": numero, "etat": grilles.ETAT_PUBLIEE})
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
    ne se corrige pas ainsi (un libellé, une forme : une nouvelle version)."""
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


@router.get("/api/grilles/{grille_id}/versions/{numero}/tableur")
def reexporter_tableur(grille_id: int, numero: int, conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """Le RÉEXPORT d'une version au format du tableur, identifiants compris (G16) : un zip,
    les deux CSV. À qui gère le projet. Une porte DÉCLARÉE hors du droit d'export (DROIT-2
    borne le CORPUS ; une grille est un vocabulaire, son plan ne porte aucune transcription,
    `tests/test_droit_export.py`)."""
    g = _get_grille(conn, portee, grille_id, gerer=True)
    v = _get_version(conn, g, numero)
    return Response(content=grille_import.archive(conn, v["id"]), media_type="application/zip",
                    headers={"Content-Disposition":
                             _disposition(f"grille-{grille_id}-v{numero}.zip")})


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
