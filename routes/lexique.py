"""Lexique situé — la couche définitionnelle SKOS du vocabulaire émergent (A4).

Domaines, dimensions, valeurs et tags portent tous le même patron « contrôlé-mais-ouvert » :
une `definition`, une `note_portee` (le SKOS `scopeNote`, c'est-à-dire le « situé »), un
`etat` provisoire→défini, et une collection d'appartenance. Ce module en est le read model
et l'édition, plus l'amorçage en lot depuis un tableur.

`GET /api/lexique` agrège TOUT le vocabulaire en quatre requêtes : c'est le seul endroit où
l'oubli d'un filtre de portée rendrait vain le cloisonnement des routes unitaires, puisque
le panneau Lexique passe par ici et non par elles.

Bloc sorti de `main.py` (ARCH-1). Chemins et contrat d'API inchangés : un routeur inclus
apparaît dans `app.routes` comme une route déclarée sur `app`, ce dont dépendent les trois
cliquets du dépôt. Les imports sont CALCULÉS depuis les noms libres du bloc, jamais
recopiés à l'œil — c'est cette erreur-là qui a produit 49 tests rouges au premier bloc.
"""
from __future__ import annotations

import io
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

import autorisation
import lexique_import
from database import lexique_resume

from socle import (
    LexiqueIn, _clause_personnage, _get_dimension, _get_valeur, _patch_lexique, _row, _rows,
    db, portee_courante,
)

router = APIRouter()

@router.get("/api/lexique")
def get_lexique(conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    """Tout le lexique situé pour l'édition : domaines + dimensions (→ valeurs) + tags, avec
    leur couche définitionnelle (definition/note_portee/etat/portée) et le nombre d'usages ;
    plus le résumé « % défini ». Read model du panneau Lexique.

    AUTH-2 — c'est le read model qui agrège TOUT le vocabulaire : quatre requêtes, quatre
    filtres, et l'oubli d'un seul rendrait vain le cloisonnement des routes unitaires
    ci-dessus, puisque le panneau Lexique passe par ici et non par elles."""
    ou_dom, p_dom = portee.clause_terme("domaine.collection_id")
    ou_dimx, p_dimx = portee.clause_terme("x.collection_id")
    ou_dim, p_dim = portee.clause_terme("d.collection_id")
    ou_val, p_val = portee.clause_terme("v.collection_id")
    ou_tag, p_tag = portee.clause_terme("t.collection_id")
    ou_album, p_album = portee.clause_album("pl.album_id")
    ou_perso, p_perso = _clause_personnage(portee)
    domaines = _rows(conn.execute(
        f"SELECT id, nom, definition, note_portee, etat, collection_id, "
        f"       (SELECT COUNT(*) FROM attribut_dimension x "
        f"         WHERE x.domaine_id = domaine.id AND {ou_dimx}) AS nb_dimensions "
        f"FROM domaine WHERE {ou_dom} ORDER BY nom", [*p_dimx, *p_dom]))
    dims = _rows(conn.execute(
        f"SELECT d.id, d.cible, d.nom, d.domaine_id, d.definition, d.note_portee, d.etat, "
        f"       d.collection_id "
        f"FROM attribut_dimension d WHERE {ou_dim} ORDER BY d.cible, d.nom", p_dim))
    vals = _rows(conn.execute(
        f"SELECT v.id, v.dimension_id, v.valeur, v.definition, v.note_portee, v.etat, "
        f"       v.collection_id, "
        f"       ((SELECT COUNT(*) FROM personnage_attribut pa JOIN personnages p "
        f"           ON p.id = pa.personnage_id "
        f"         WHERE pa.valeur_id = v.id AND {ou_perso}) "
        f"      + (SELECT COUNT(*) FROM region_attribut ra "
        f"           JOIN regions r   ON r.id = ra.region_id "
        f"           JOIN planches pl ON pl.id = r.planche_id "
        f"         WHERE ra.valeur_id = v.id AND {ou_album})) AS nb_usages "
        f"FROM attribut_valeur v WHERE {ou_val} ORDER BY v.valeur",
        [*p_perso, *p_album, *p_val]))
    par_dim = {}
    for v in vals:
        par_dim.setdefault(v["dimension_id"], []).append(v)
    for d in dims:
        d["valeurs"] = par_dim.get(d["id"], [])
    tags = _rows(conn.execute(
        f"SELECT t.id, t.label, t.description, t.note_portee, t.etat, t.collection_id, "
        f"       (SELECT COUNT(*) FROM annotation_tags at "
        f"          JOIN annotations an ON an.id = at.annotation_id "
        f"          JOIN regions r      ON r.id = an.region_id "
        f"          JOIN planches pl    ON pl.id = r.planche_id "
        f"        WHERE at.tag_id = t.id AND {ou_album}) AS frequence "
        f"FROM tags t WHERE {ou_tag} ORDER BY t.label", [*p_album, *p_tag]))
    # AUTH-2 — le résumé se filtre COMME les quatre listes ci-dessus. Il ne montrait aucun
    # terme, mais les COMPTAIT tous : « 3 définis sur 41 » à qui n'en voit que trois dit le
    # volume de vocabulaire des autres, et rend le pourcentage faux pour qui le lit.
    return {"domaines": domaines, "dimensions": dims, "tags": tags,
            "resume": lexique_resume(conn, clause=portee.clause_terme("collection_id"))}


@router.post("/api/lexique/importer")
def importer_lexique(file: UploadFile = File(...),
                     collection_id: Optional[int] = Form(None, ge=1),
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Amorçage EN LOT du vocabulaire depuis un tableur CSV (point-virgule) — bouton
    « Importer » du panneau 📖 Lexique. Même cœur et même doctrine que l'outil headless
    (pré-remplir sans écraser, idempotent ; cf. lexique_import + docs/import-vocabulaire.md).
    `collection_id` = portée d'appartenance (absent = global)."""
    # AUTH-2 — amorcer le vocabulaire est une écriture, et une écriture de PORTÉE :
    # `collection_id` range les termes chez quelqu'un. On exige donc le droit d'écrire
    # sur CETTE collection, et un simple droit d'écriture quelque part pour du global.
    if collection_id is None:
        if not portee.peut_ecrire_quelque_part():
            raise HTTPException(403, "Importer du vocabulaire demande un droit d'écriture "
                                     "sur au moins une collection.")
    elif not portee.peut_ecrire(collection_id):
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    if collection_id is not None and conn.execute(
            "SELECT 1 FROM collection WHERE id = ?", (collection_id,)).fetchone() is None:
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    data = file.file.read()
    if not data:
        raise HTTPException(400, "Fichier vide")
    try:
        texte = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "Le fichier doit être encodé en UTF-8.")
    try:
        lignes, anomalies = lexique_import.lire(io.StringIO(texte))
    except lexique_import.FormatInvalide as e:
        raise HTTPException(400, str(e))
    res, avert = lexique_import.importer(conn, lignes, collection_id)
    conn.commit()
    return {"resume": res, "lignes": len(lignes),
            "anomalies": anomalies, "avertissements": avert}


@router.patch("/api/attributs/dimensions/{dim_id}/lexique")
def patch_dimension_lexique(dim_id: int, payload: LexiqueIn,
                            conn: sqlite3.Connection = Depends(db),
                            portee: autorisation.Portee = Depends(portee_courante)):
    """Documente une dimension : définition + note de portée + état + portée d'appartenance."""
    _get_dimension(conn, portee, dim_id, ecriture=True)
    _patch_lexique(conn, "attribut_dimension", dim_id, payload, portee)
    return _row(conn.execute("SELECT * FROM attribut_dimension WHERE id = ?", (dim_id,)))


@router.patch("/api/attributs/valeurs/{val_id}/lexique")
def patch_valeur_lexique(val_id: int, payload: LexiqueIn,
                         conn: sqlite3.Connection = Depends(db),
                         portee: autorisation.Portee = Depends(portee_courante)):
    """Documente une valeur canonique (même couche définitionnelle)."""
    _get_valeur(conn, portee, val_id, ecriture=True)
    _patch_lexique(conn, "attribut_valeur", val_id, payload, portee)
    return _row(conn.execute("SELECT * FROM attribut_valeur WHERE id = ?", (val_id,)))


@router.patch("/api/tags/{tag_id}/lexique")
def patch_tag_lexique(tag_id: int, payload: LexiqueIn,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Documente un tag : sa `description` EST la définition SKOS ; + note de portée, état,
    portée d'appartenance (même patron que le vocabulaire facetté)."""
    ou, params = portee.clause_terme("t.collection_id")
    tag = _row(conn.execute(f"SELECT * FROM tags t WHERE t.id = ? AND {ou}",
                            (tag_id, *params)))
    if tag is None:
        raise HTTPException(404, f"Tag {tag_id} introuvable")
    if not portee.peut_ecrire_terme(tag.get("collection_id")):
        raise HTTPException(403, "Ce tag est en lecture seule pour vous.")
    _patch_lexique(conn, "tags", tag_id, payload, portee, col_definition="description")
    return _row(conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)))
