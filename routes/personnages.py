"""Personnages, attribution et vocabulaire facetté (ANN-2, A5, piste B).

Le registre des ENTITÉS — personnage, locuteur d'une bulle, présence dans une case —,
ses alignements sur des référentiels externes (A5), et le vocabulaire FACETTÉ qui le
décrit : domaines, dimensions, valeurs, et l'affectation de ces valeurs à un personnage
ou à une région.

L'affectation vivait ailleurs, après le lexique, par accrétion : elle est remontée ici
avant l'extraction. C'est l'« attribution » du titre — la séparer du registre aurait
fabriqué un module qui ment sur son contenu, ce que le fichier unique pouvait se
permettre et qu'un module ne peut plus.

Ce qui N'est PAS ici, et c'est délibéré : `_clause_personnage` et `_get_personnage`
vivent dans `socle.py`. La portée d'un personnage est DÉRIVÉE de ses apparitions
(AUTH-2) et le lexique s'en sert aussi ; les garder ici aurait obligé le module du
lexique à remonter vers celui-ci, puis vers `main`.

Bloc sorti de `main.py` (ARCH-1), le plus gros des quatre — 659 lignes. Chemins et
contrat d'API inchangés : un routeur inclus apparaît dans `app.routes` comme une route
déclarée sur `app`, ce dont dépendent les trois cliquets du dépôt. Les imports
ci-dessous sont CALCULÉS depuis les noms libres du bloc, jamais recopiés à l'œil —
c'est cette erreur-là qui a produit 49 tests rouges au premier bloc extrait.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

import autorisation
import journal
from config import CIBLES_ATTRIBUT

from socle import (
    AlignementIn, AttributIn, DimensionDomaineIn, DimensionIn, DomaineIn, FusionIn,
    LexiqueIn, LocuteurIn, PersonnageIn, PersonnageUpdate, PresenceIn, ValeurIn,
    _attributs_de, _clause_personnage, _get_dimension, _get_personnage, _get_region,
    _get_valeur, _norm_tag, _patch_lexique, _row, _rows, _sans_accents, db, portee_courante,
    _descendre_portee,          # v24 : la portée suit le rattachement, et elle DESCEND
)

router = APIRouter()


def _locuteur_for(conn, region_id):
    """Locuteur attribué à une bulle (ou None) → {locuteur: {id, nom, serie} | None}."""
    return {"locuteur": _row(conn.execute(
        "SELECT p.id, p.nom, p.serie FROM bulle_locuteur bl "
        "JOIN personnages p ON p.id = bl.personnage_id WHERE bl.region_id = ?", (region_id,)))}


def _personnage_for(conn, region_id):
    """Personnage MONTRÉ dans une boîte (ou None) → {personnage: {id, nom, serie} | None}.
    Miroir de _locuteur_for, côté image (§14, brique (a))."""
    return {"personnage": _row(conn.execute(
        "SELECT p.id, p.nom, p.serie FROM personnage_presence pp "
        "JOIN personnages p ON p.id = pp.personnage_id WHERE pp.region_id = ?", (region_id,)))}


@router.get("/api/personnages")
def list_personnages(q: Optional[str] = None, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Registre des personnages + nombre de bulles attribuées.
    `q` filtre par nom (autocomplétion à la saisie / canonicalisation à la volée).

    AUTH-2 — la portée d'un personnage se DÉRIVE de ses apparitions (cf.
    `_clause_personnage`), et `nb_bulles` ne compte que les bulles lisibles : un compteur
    global dirait le volume de travail des autres, et fausserait la lecture du registre."""
    ou, params = _clause_personnage(portee)
    ou_album, p_album = portee.clause_album("pl.album_id")
    rows = _rows(conn.execute(
        f"SELECT p.id, p.nom, p.serie, p.notes, "
        f"       (SELECT COUNT(*) FROM bulle_locuteur bl "
        f"          JOIN regions r   ON r.id = bl.region_id "
        f"          JOIN planches pl ON pl.id = r.planche_id "
        f"        WHERE bl.personnage_id = p.id AND {ou_album}) AS nb_bulles "
        f"FROM personnages p WHERE {ou} ORDER BY p.nom, p.serie",
        [*p_album, *params]))
    if q and q.strip():
        cible = _sans_accents(q)   # autocomplétion insensible à la casse ET aux accents
        rows = [r for r in rows if cible in _sans_accents(r["nom"])]
    return rows


@router.post("/api/personnages", status_code=201)
def create_personnage(payload: PersonnageIn, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """AUTH-2 — le registre des personnages n'appartient à aucune collection : y écrire
    demande le droit d'écrire quelque part, comme pour le vocabulaire global."""
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Le registre des personnages est en lecture seule "
                                 "pour vous.")
    nom = (payload.nom or "").strip()
    if not nom:
        raise HTTPException(422, "Nom de personnage vide")
    pid = conn.execute(
        "INSERT INTO personnages (nom, serie, notes) VALUES (?, ?, ?)",
        (nom, (payload.serie or "").strip() or None, payload.notes)).lastrowid
    conn.commit()
    return _get_personnage(conn, portee, pid)


@router.put("/api/personnages/{personnage_id}")
def update_personnage(personnage_id: int, payload: PersonnageUpdate,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    sets, params = [], []
    if payload.nom is not None:
        nom = payload.nom.strip()
        if not nom:
            raise HTTPException(422, "Nom de personnage vide")
        sets.append("nom = ?"); params.append(nom)
    if payload.serie is not None:
        sets.append("serie = ?"); params.append(payload.serie.strip() or None)
    if payload.notes is not None:
        sets.append("notes = ?"); params.append(payload.notes)
    if sets:
        params.append(personnage_id)
        conn.execute(f"UPDATE personnages SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
    return _get_personnage(conn, portee, personnage_id, ecriture=True)


@router.delete("/api/personnages/{personnage_id}", status_code=204)
def delete_personnage(personnage_id: int, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    conn.execute("DELETE FROM personnages WHERE id = ?", (personnage_id,))   # CASCADE : détache liens/attributs
    conn.commit()


@router.post("/api/personnages/{personnage_id}/fusion")
def fusionner_personnage(personnage_id: int, payload: FusionIn,
                         conn: sqlite3.Connection = Depends(db),
                         portee: autorisation.Portee = Depends(portee_courante)):
    """Fusionne `personnage_id` (doublon) DANS `cible_id` (canonique) : réaffecte les
    liens locuteur et les attributs, puis supprime le doublon. Idempotent sur les
    affectations (INSERT OR IGNORE). Soupape du modèle mentions→entités (curation)."""
    if payload.cible_id == personnage_id:
        raise HTTPException(422, "Un personnage ne peut être fusionné avec lui-même")
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    _get_personnage(conn, portee, payload.cible_id, ecriture=True)
    # locuteur : une bulle a au plus un locuteur (region_id PK) → réaffectation directe.
    conn.execute("UPDATE bulle_locuteur SET personnage_id = ? WHERE personnage_id = ?",
                 (payload.cible_id, personnage_id))
    # attributs : éviter le doublon (personnage_id, valeur_id) → OR IGNORE ; le reste du
    # doublon part au DELETE (CASCADE).
    conn.execute("INSERT OR IGNORE INTO personnage_attribut (personnage_id, valeur_id) "
                 "SELECT ?, valeur_id FROM personnage_attribut WHERE personnage_id = ?",
                 (payload.cible_id, personnage_id))
    # alignements d'autorité (A5) : mêmes règles — dédupliqués par (personnage_id, uri).
    conn.execute("INSERT OR IGNORE INTO personnage_alignement (personnage_id, source, uri) "
                 "SELECT ?, source, uri FROM personnage_alignement WHERE personnage_id = ?",
                 (payload.cible_id, personnage_id))
    conn.execute("DELETE FROM personnages WHERE id = ?", (personnage_id,))
    conn.commit()
    return _get_personnage(conn, portee, payload.cible_id, ecriture=True)


# --- Alignement d'autorité (A5, N6) : personnage → référentiel externe (skos:exactMatch) ---
_AUTORITES = {                       # hôte → étiquette de source (auto-détection)
    "wikidata.org": "wikidata", "viaf.org": "viaf", "idref.fr": "idref",
    "isni.org": "isni", "data.bnf.fr": "bnf", "id.loc.gov": "loc", "d-nb.info": "gnd",
}


def _source_autorite(uri: str) -> Optional[str]:
    """Devine l'autorité depuis l'hôte de l'URI (Wikidata/VIAF/IdRef…) ; None si inconnu
    (l'alignement reste valide, `source` non renseignée)."""
    from urllib.parse import urlparse
    host = (urlparse(uri).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    for cle, src in _AUTORITES.items():
        if host == cle or host.endswith("." + cle):
            return src
    return None


def _alignements_de(conn, personnage_id):
    return _rows(conn.execute(
        "SELECT id, source, uri, date_creation FROM personnage_alignement "
        "WHERE personnage_id = ? ORDER BY id", (personnage_id,)))


@router.get("/api/personnages/{personnage_id}/alignements")
def list_alignements(personnage_id: int, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Alignements d'autorité d'un personnage (skos:exactMatch vers Wikidata/VIAF/IdRef…)."""
    _get_personnage(conn, portee, personnage_id)
    return _alignements_de(conn, personnage_id)


@router.post("/api/personnages/{personnage_id}/alignements", status_code=201)
def add_alignement(personnage_id: int, payload: AlignementIn,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Aligne un personnage sur une URI d'autorité. `source` auto-détectée depuis l'URI si
    absente. Idempotent : re-poster la même URI met à jour la source, sans doublon."""
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    uri = (payload.uri or "").strip()
    if not (uri.startswith("http://") or uri.startswith("https://")):
        raise HTTPException(422, "L'alignement doit être une URI http(s).")
    source = (payload.source or "").strip() or _source_autorite(uri)
    conn.execute(
        "INSERT INTO personnage_alignement (personnage_id, source, uri) VALUES (?, ?, ?) "
        "ON CONFLICT(personnage_id, uri) DO UPDATE SET source = excluded.source",
        (personnage_id, source, uri))
    conn.commit()
    return _row(conn.execute(
        "SELECT id, source, uri, date_creation FROM personnage_alignement "
        "WHERE personnage_id = ? AND uri = ?", (personnage_id, uri)))


@router.delete("/api/personnages/{personnage_id}/alignements/{alignement_id}", status_code=204)
def delete_alignement(personnage_id: int, alignement_id: int,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    cur = conn.execute("DELETE FROM personnage_alignement WHERE id = ? AND personnage_id = ?",
                       (alignement_id, personnage_id))
    if not cur.rowcount:
        raise HTTPException(404, f"Alignement {alignement_id} introuvable")
    conn.commit()


@router.get("/api/regions/{region_id}/locuteur")
def get_locuteur(region_id: int, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id)
    return _locuteur_for(conn, region_id)


@router.put("/api/regions/{region_id}/locuteur")
def set_locuteur(region_id: int, payload: LocuteurIn, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    _get_personnage(conn, portee, payload.personnage_id)
    ancien = conn.execute("SELECT personnage_id FROM bulle_locuteur WHERE region_id = ?",
                          (region_id,)).fetchone()
    conn.execute("INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?) "
                 "ON CONFLICT(region_id) DO UPDATE SET personnage_id = excluded.personnage_id",
                 (region_id, payload.personnage_id))
    journal.journaliser(conn, "lien", "bulle_locuteur", region_id,
                        avant=({"personnage_id": ancien["personnage_id"]} if ancien else None),
                        apres={"personnage_id": payload.personnage_id})
    conn.commit()
    return _locuteur_for(conn, region_id)


@router.delete("/api/regions/{region_id}/locuteur", status_code=204)
def clear_locuteur(region_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    ancien = conn.execute("SELECT personnage_id FROM bulle_locuteur WHERE region_id = ?",
                          (region_id,)).fetchone()
    conn.execute("DELETE FROM bulle_locuteur WHERE region_id = ?", (region_id,))
    if ancien:
        journal.journaliser(conn, "delien", "bulle_locuteur", region_id,
                            avant={"personnage_id": ancien["personnage_id"]})
    conn.commit()


# --- Présence : quelle entité est MONTRÉE dans une boîte personnage (§14, brique (a)).
#     Strict miroir du locuteur, mais pour l'image — la boîte porte l'identité, et le
#     profil de l'entité devient atteignable depuis l'image (muets compris). La cohérence
#     de type (region.type = 'personnage') est assurée côté UI, comme pour le locuteur.
@router.get("/api/regions/{region_id}/personnage")
def get_presence(region_id: int, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id)
    return _personnage_for(conn, region_id)


@router.put("/api/regions/{region_id}/personnage")
def set_presence(region_id: int, payload: PresenceIn, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    _get_personnage(conn, portee, payload.personnage_id)
    ancien = conn.execute("SELECT personnage_id FROM personnage_presence WHERE region_id = ?",
                          (region_id,)).fetchone()
    conn.execute("INSERT INTO personnage_presence (region_id, personnage_id) VALUES (?, ?) "
                 "ON CONFLICT(region_id) DO UPDATE SET personnage_id = excluded.personnage_id",
                 (region_id, payload.personnage_id))
    journal.journaliser(conn, "lien", "personnage_presence", region_id,
                        avant=({"personnage_id": ancien["personnage_id"]} if ancien else None),
                        apres={"personnage_id": payload.personnage_id})
    conn.commit()
    return _personnage_for(conn, region_id)


@router.delete("/api/regions/{region_id}/personnage", status_code=204)
def clear_presence(region_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    ancien = conn.execute("SELECT personnage_id FROM personnage_presence WHERE region_id = ?",
                          (region_id,)).fetchone()
    conn.execute("DELETE FROM personnage_presence WHERE region_id = ?", (region_id,))
    if ancien:
        journal.journaliser(conn, "delien", "personnage_presence", region_id,
                            avant={"personnage_id": ancien["personnage_id"]})
    conn.commit()


# --- DOMAINES (piste B) : champ analytique émergent qui REGROUPE des dimensions (émotions,
#     représentation…). Orthogonal à `cible`. Même patron contrôlé-ouvert + lexique SKOS que
#     les dimensions. Cf. docs/domaines.md.
def _get_domaine(conn, portee: autorisation.Portee, dom_id, *, ecriture: bool = False):
    """Terme du vocabulaire, VISIBLE (404 sinon) et, si `ecriture`, MODIFIABLE.

    Le refus d'écriture est un 403 et non un 404, contrairement aux données : le
    terme vient d'être listé, prétendre qu'il n'existe pas serait incohérent — et
    le refus ne parle que des droits de l'appelant, il ne fuit rien.
    """
    ou, params = portee.clause_terme("t.collection_id")
    d = _row(conn.execute(
        f"SELECT t.* FROM domaine t WHERE t.id = ? AND {ou}", (dom_id, *params)))
    if d is None:
        raise HTTPException(404, f"Domaine {dom_id} introuvable")
    if ecriture and not portee.peut_ecrire_terme(d.get("collection_id")):
        raise HTTPException(403, "Ce terme du vocabulaire est en lecture seule "
                                 "pour vous.")
    return d


@router.get("/api/domaines")
def list_domaines(conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Domaines + nombre de dimensions rattachées + couche lexique (pour l'organisation/l'analyse).

    AUTH-2 — un domaine est un terme du vocabulaire : visible s'il est global
    (`collection_id` NULL) ou s'il appartient à une collection qu'on lit. Le compte de
    dimensions suit la même règle, sinon il dirait combien d'axes existent ailleurs."""
    ou, params = portee.clause_terme("d.collection_id")
    ou_dim, p_dim = portee.clause_terme("x.collection_id")
    return _rows(conn.execute(
        f"SELECT d.id, d.nom, d.definition, d.note_portee, d.etat, d.collection_id, "
        f"       (SELECT COUNT(*) FROM attribut_dimension x "
        f"         WHERE x.domaine_id = d.id AND {ou_dim}) AS nb_dimensions "
        f"FROM domaine d WHERE {ou} ORDER BY d.nom", [*p_dim, *params]))


@router.post("/api/domaines", status_code=201)
def create_domaine(payload: DomaineIn, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """AUTH-2 — même garde que la création de tag : enrichir un vocabulaire partagé
    suppose de pouvoir écrire quelque part."""
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Créer un domaine demande un droit d'écriture sur au "
                                 "moins une collection.")
    nom = _norm_tag(payload.nom)
    if not nom:
        raise HTTPException(422, "Nom de domaine vide")
    conn.execute("INSERT INTO domaine (nom) VALUES (?) ON CONFLICT(nom) DO NOTHING", (nom,))
    conn.commit()
    return _row(conn.execute("SELECT * FROM domaine WHERE nom = ?", (nom,)))


@router.patch("/api/domaines/{dom_id}")
def rename_domaine(dom_id: int, payload: DomaineIn, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Renomme un domaine (préserve son regroupement de dimensions, contrairement à un
    supprimer/recréer). Le nom reste normalisé et UNIQUE."""
    _get_domaine(conn, portee, dom_id, ecriture=True)
    nom = _norm_tag(payload.nom)
    if not nom:
        raise HTTPException(422, "Nom de domaine vide")
    if conn.execute("SELECT 1 FROM domaine WHERE nom = ? AND id <> ?", (nom, dom_id)).fetchone():
        raise HTTPException(409, f"Domaine « {nom} » déjà existant.")
    conn.execute("UPDATE domaine SET nom = ? WHERE id = ?", (nom, dom_id))
    conn.commit()
    return _row(conn.execute("SELECT * FROM domaine WHERE id = ?", (dom_id,)))


@router.delete("/api/domaines/{dom_id}", status_code=204)
def delete_domaine(dom_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime un domaine. Ses dimensions ne sont PAS détruites : `domaine_id` repasse à NULL
    (ON DELETE SET NULL) — elles redeviennent « hors domaine » (soupape *promotion*)."""
    _get_domaine(conn, portee, dom_id, ecriture=True)
    conn.execute("DELETE FROM domaine WHERE id = ?", (dom_id,))
    conn.commit()


@router.patch("/api/domaines/{dom_id}/lexique")
def patch_domaine_lexique(dom_id: int, payload: LexiqueIn, conn: sqlite3.Connection = Depends(db),
                          portee: autorisation.Portee = Depends(portee_courante)):
    """Documente un domaine (même couche SKOS que dimensions/valeurs/tags)."""
    _get_domaine(conn, portee, dom_id, ecriture=True)
    promus = _patch_lexique(conn, "domaine", dom_id, payload, portee)
    return {**_row(conn.execute("SELECT * FROM domaine WHERE id = ?", (dom_id,))),
            "promus": promus}


# --- Attributs FACETTÉS & ÉMERGENTS : dimensions (axes) / valeurs canoniques /
#     affectations. Vocabulaire NON figé — créé au fil de l'eau. Valeurs et noms de
#     dimension normalisés (comme les tags) → agrégeables. Cf. docs/personnages-et-attribution.md.
@router.get("/api/attributs/dimensions")
def list_dimensions(cible: Optional[str] = None, conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Dimensions (axes émergents) + nombre de valeurs + domaine de rattachement (v20).
    `cible` filtre 'personnage' | 'case'.

    AUTH-2 — mêmes règles que les domaines : le terme est visible s'il est global ou
    local à une collection qu'on lit, et le compte de valeurs est filtré pareillement.
    Le NOM du domaine de rattachement est un terme lui aussi : il se filtre, sinon une
    dimension globale nommerait le domaine privé auquel on l'a rattachée. Il revient donc
    à `null` quand le domaine n'est pas visible — la dimension, elle, reste."""
    ou, p_dim = portee.clause_terme("d.collection_id")
    ou_val, p_val = portee.clause_terme("v.collection_id")
    ou_dom, p_dom = portee.clause_terme("dom.collection_id")
    sql = (f"SELECT d.id, d.cible, d.nom, d.domaine_id, "
           f"       (SELECT nom FROM domaine dom WHERE dom.id = d.domaine_id "
           f"          AND {ou_dom}) AS domaine, "
           f"       (SELECT COUNT(*) FROM attribut_valeur v "
           f"         WHERE v.dimension_id = d.id AND {ou_val}) AS nb_valeurs "
           f"FROM attribut_dimension d WHERE {ou} ")
    params = [*p_dom, *p_val, *p_dim]
    if cible:
        sql += "AND d.cible = ? "
        params.append(cible)
    sql += "ORDER BY d.cible, d.nom"
    return _rows(conn.execute(sql, params))


@router.post("/api/attributs/dimensions", status_code=201)
def create_dimension(payload: DimensionIn, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Créer une dimension demande un droit d'écriture sur au "
                                 "moins une collection.")
    if payload.cible not in CIBLES_ATTRIBUT:
        raise HTTPException(422, f"Cible invalide : {payload.cible} (personnage | case).")
    nom = _norm_tag(payload.nom)
    if not nom:
        raise HTTPException(422, "Nom de dimension vide")
    # AUTH-2 — la dimension HÉRITE de la portée de son domaine. Un terme ne peut pas être
    # plus global que celui dont il dépend : une dimension globale rattachée à un domaine
    # privé se montrait à tout le monde, et nommait le domaine au passage. Sans domaine,
    # la dimension reste globale, comme avant.
    cid = None
    if payload.domaine_id is not None:
        dom = _get_domaine(conn, portee, payload.domaine_id, ecriture=True)    # 404 si le domaine n'existe pas
        cid = dom["collection_id"]
    conn.execute("INSERT INTO attribut_dimension (cible, nom, domaine_id, collection_id) "
                 "VALUES (?, ?, ?, ?) ON CONFLICT(cible, nom) DO NOTHING",
                 (payload.cible, nom, payload.domaine_id, cid))
    conn.commit()
    return _row(conn.execute("SELECT * FROM attribut_dimension WHERE cible = ? AND nom = ?",
                             (payload.cible, nom)))


@router.patch("/api/attributs/dimensions/{dim_id}/domaine")
def patch_dimension_domaine(dim_id: int, payload: DimensionDomaineIn,
                            conn: sqlite3.Connection = Depends(db),
                            portee: autorisation.Portee = Depends(portee_courante)):
    """Rattache une dimension à un domaine (ou l'en détache avec `domaine_id: null`).

    v24 — la PORTÉE suit le rattachement. La création héritait déjà du domaine ; ce
    déplacement ne le faisait pas, si bien qu'une dimension GLOBALE passée sous un domaine
    PRIVÉ y restait globale (mesuré le 2026-09-06, HTTP 200 sans un mot). Ce qui fuyait
    alors n'était pas un mot mais le NOM DE L'AXE — la grille d'analyse d'une collection
    fermée, nommée à tout le monde, ce que v24 décrit précisément comme le défaut à fermer.

    DÉTACHER ne promeut pas. `domaine_id: null` laisse la portée en place, alors que la
    création sans domaine naît globale : les deux ne sont pas le même geste. Sortir une
    dimension de son domaine est un rangement ; la rendre globale au passage serait une
    publication que personne n'a demandée — exactement la classe de défaut réparée ici.
    """
    _get_dimension(conn, portee, dim_id, ecriture=True)
    # « Ne pas toucher à la portée » et « la mettre à NULL » sont deux choses, et NULL
    # est une valeur légitime : il faut donc un troisième état pour dire « rien ».
    RIEN = object()
    cible = RIEN
    if payload.domaine_id is not None:
        dom = _get_domaine(conn, portee, payload.domaine_id, ecriture=True)
        cible = dom["collection_id"]
    conn.execute("UPDATE attribut_dimension SET domaine_id = ? WHERE id = ?",
                 (payload.domaine_id, dim_id))
    if cible is not RIEN:
        conn.execute("UPDATE attribut_dimension SET collection_id = ? WHERE id = ?",
                     (cible, dim_id))
        # Et la portée DESCEND : une dimension devenue locale laisserait ses valeurs
        # globales au-dessus d'elle. Même réserve que la migration v24 — seules les valeurs
        # sans portée bougent ; une valeur déjà locale ailleurs est un fait délibéré.
        _descendre_portee(conn, "attribut_dimension", dim_id, cible)
    conn.commit()
    return _row(conn.execute("SELECT * FROM attribut_dimension WHERE id = ?", (dim_id,)))


@router.delete("/api/attributs/dimensions/{dim_id}", status_code=204)
def delete_dimension(dim_id: int, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    _get_dimension(conn, portee, dim_id, ecriture=True)
    conn.execute("DELETE FROM attribut_dimension WHERE id = ?", (dim_id,))   # CASCADE : valeurs + affectations
    conn.commit()


@router.get("/api/attributs/dimensions/{dim_id}/valeurs")
def list_valeurs(dim_id: int, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """AUTH-2 — `nb_usages` comptait TOUS les emplois du corpus. Il ne compte plus que
    les régions lisibles (côté case) et les personnages visibles (côté locuteur) : sinon
    la fréquence d'une valeur trahit le volume d'annotation des autres."""
    _get_dimension(conn, portee, dim_id)
    ou_terme, p_terme = portee.clause_terme("v.collection_id")
    ou_album, p_album = portee.clause_album("pl.album_id")
    ou_perso, p_perso = _clause_personnage(portee)
    return _rows(conn.execute(
        f"SELECT v.id, v.dimension_id, v.valeur, "
        f"       ((SELECT COUNT(*) FROM personnage_attribut pa JOIN personnages p "
        f"           ON p.id = pa.personnage_id "
        f"         WHERE pa.valeur_id = v.id AND {ou_perso}) "
        f"      + (SELECT COUNT(*) FROM region_attribut ra "
        f"           JOIN regions r   ON r.id = ra.region_id "
        f"           JOIN planches pl ON pl.id = r.planche_id "
        f"         WHERE ra.valeur_id = v.id AND {ou_album})) AS nb_usages "
        f"FROM attribut_valeur v WHERE v.dimension_id = ? AND {ou_terme} ORDER BY v.valeur",
        [*p_perso, *p_album, dim_id, *p_terme]))


@router.post("/api/attributs/dimensions/{dim_id}/valeurs", status_code=201)
def create_valeur(dim_id: int, payload: ValeurIn, conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    dim = _get_dimension(conn, portee, dim_id, ecriture=True)
    valeur = _norm_tag(payload.valeur)
    if not valeur:
        raise HTTPException(422, "Valeur vide")
    # AUTH-2 — même héritage qu'un cran plus haut : la valeur prend la portée de sa
    # dimension. La route ne posait aucun `collection_id`, si bien que toute valeur
    # naissait GLOBALE — y compris sous un axe d'analyse local à une étude. Le dommage
    # n'est pas le mot (« palpable » ne dit rien) mais ce qu'il traîne : les routes à plat
    # renvoient le NOM de sa dimension.
    conn.execute("INSERT INTO attribut_valeur (dimension_id, valeur, collection_id) "
                 "VALUES (?, ?, ?) ON CONFLICT(dimension_id, valeur) DO NOTHING",
                 (dim_id, valeur, dim["collection_id"]))
    conn.commit()
    return _row(conn.execute("SELECT * FROM attribut_valeur WHERE dimension_id = ? AND valeur = ?",
                             (dim_id, valeur)))


@router.delete("/api/attributs/valeurs/{val_id}", status_code=204)
def delete_valeur(val_id: int, conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    _get_valeur(conn, portee, val_id, ecriture=True)
    conn.execute("DELETE FROM attribut_valeur WHERE id = ?", (val_id,))   # CASCADE : affectations
    conn.commit()


@router.get("/api/attributs/valeurs")
def list_valeurs_plat(cible: Optional[str] = None, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Toutes les valeurs (avec leur dimension), à plat — sert les facettes d'analyse
    (évite un N+1 dimensions→valeurs). `cible` filtre 'personnage' | 'case'.

    AUTH-2 — mêmes deux filtres qu'ailleurs : les TERMES visibles, et des `nb_usages`
    comptés sur le seul sous-corpus lisible. La dimension jointe est filtrée elle aussi :
    c'est elle qui porte le nom, donc la fuite (cf. `_attributs_de`)."""
    ou_terme, p_terme = portee.clause_terme("v.collection_id")
    ou_dim, p_dim = portee.clause_terme("d.collection_id")
    ou_album, p_album = portee.clause_album("pl.album_id")
    ou_perso, p_perso = _clause_personnage(portee)
    sql = (f"SELECT v.id, v.valeur, d.id AS dimension_id, d.nom AS dimension, d.cible, "
           f"       ((SELECT COUNT(*) FROM personnage_attribut pa JOIN personnages p "
           f"           ON p.id = pa.personnage_id "
           f"         WHERE pa.valeur_id = v.id AND {ou_perso}) "
           f"      + (SELECT COUNT(*) FROM region_attribut ra "
           f"           JOIN regions r   ON r.id = ra.region_id "
           f"           JOIN planches pl ON pl.id = r.planche_id "
           f"         WHERE ra.valeur_id = v.id AND {ou_album})) AS nb_usages "
           f"FROM attribut_valeur v JOIN attribut_dimension d ON d.id = v.dimension_id "
           f"WHERE {ou_terme} AND {ou_dim} ")
    params = [*p_perso, *p_album, *p_terme, *p_dim]
    if cible:
        sql += "AND d.cible = ? "
        params.append(cible)
    sql += "ORDER BY d.cible, d.nom, v.valeur"
    return _rows(conn.execute(sql, params))


@router.put("/api/attributs/valeurs/{val_id}")
def rename_valeur(val_id: int, payload: ValeurIn, conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Renomme une valeur (curation). Conflit avec une valeur existante de la même
    dimension → 409 (utiliser la fusion à la place)."""
    v = _get_valeur(conn, portee, val_id, ecriture=True)
    valeur = _norm_tag(payload.valeur)
    if not valeur:
        raise HTTPException(422, "Valeur vide")
    if _row(conn.execute("SELECT id FROM attribut_valeur "
                         "WHERE dimension_id = ? AND valeur = ? AND id <> ?",
                         (v["dimension_id"], valeur, val_id))):
        raise HTTPException(409, "Cette valeur existe déjà dans la dimension — fusionnez-les.")
    conn.execute("UPDATE attribut_valeur SET valeur = ? WHERE id = ?", (valeur, val_id))
    conn.commit()
    return _get_valeur(conn, portee, val_id, ecriture=True)


@router.post("/api/attributs/valeurs/{val_id}/fusion")
def fusionner_valeur(val_id: int, payload: FusionIn, conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Fusionne la valeur `val_id` DANS `cible_id` (même dimension) : réaffecte les
    affectations (personnages + cases) en INSERT OR IGNORE, puis supprime le doublon."""
    if payload.cible_id == val_id:
        raise HTTPException(422, "Une valeur ne peut être fusionnée avec elle-même")
    v = _get_valeur(conn, portee, val_id, ecriture=True)
    cible = _get_valeur(conn, portee, payload.cible_id, ecriture=True)
    if v["dimension_id"] != cible["dimension_id"]:
        raise HTTPException(422, "On ne fusionne que deux valeurs d'une même dimension.")
    for table, col in (("personnage_attribut", "personnage_id"), ("region_attribut", "region_id")):
        conn.execute(f"INSERT OR IGNORE INTO {table} ({col}, valeur_id) "
                     f"SELECT {col}, ? FROM {table} WHERE valeur_id = ?", (payload.cible_id, val_id))
    conn.execute("DELETE FROM attribut_valeur WHERE id = ?", (val_id,))   # CASCADE purge le reste
    conn.commit()
    return _get_valeur(conn, portee, payload.cible_id, ecriture=True)






def _affecter(conn, portee, table, col, oid, valeur_id, cible_attendue):
    """Affecte une valeur à une cible, après contrôle de cohérence de la dimension."""
    v = _get_valeur(conn, portee, valeur_id)
    if _get_dimension(conn, portee, v["dimension_id"])["cible"] != cible_attendue:
        raise HTTPException(422, f"Cette valeur n'appartient pas à une dimension de {cible_attendue}.")
    conn.execute(f"INSERT OR IGNORE INTO {table} ({col}, valeur_id) VALUES (?, ?)", (oid, valeur_id))
    conn.commit()


@router.get("/api/personnages/{personnage_id}/attributs")
def list_personnage_attributs(personnage_id: int, conn: sqlite3.Connection = Depends(db),
                              portee: autorisation.Portee = Depends(portee_courante)):
    _get_personnage(conn, portee, personnage_id)
    return _attributs_de(conn, portee, "personnage_attribut", "personnage_id", personnage_id)


@router.put("/api/personnages/{personnage_id}/attributs")
def add_personnage_attribut(personnage_id: int, payload: AttributIn,
                            conn: sqlite3.Connection = Depends(db),
                            portee: autorisation.Portee = Depends(portee_courante)):
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    _affecter(conn, portee, "personnage_attribut", "personnage_id", personnage_id, payload.valeur_id, "personnage")
    return _attributs_de(conn, portee, "personnage_attribut", "personnage_id", personnage_id)


@router.delete("/api/personnages/{personnage_id}/attributs/{valeur_id}", status_code=204)
def remove_personnage_attribut(personnage_id: int, valeur_id: int,
                               conn: sqlite3.Connection = Depends(db),
                               portee: autorisation.Portee = Depends(portee_courante)):
    _get_personnage(conn, portee, personnage_id, ecriture=True)
    conn.execute("DELETE FROM personnage_attribut WHERE personnage_id = ? AND valeur_id = ?",
                 (personnage_id, valeur_id))
    conn.commit()


@router.get("/api/regions/{region_id}/attributs")
def list_region_attributs(region_id: int, conn: sqlite3.Connection = Depends(db),
                          portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id)
    return _attributs_de(conn, portee, "region_attribut", "region_id", region_id)


@router.put("/api/regions/{region_id}/attributs")
def add_region_attribut(region_id: int, payload: AttributIn,
                        conn: sqlite3.Connection = Depends(db),
                        portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    _affecter(conn, portee, "region_attribut", "region_id", region_id, payload.valeur_id, "case")
    return _attributs_de(conn, portee, "region_attribut", "region_id", region_id)


@router.delete("/api/regions/{region_id}/attributs/{valeur_id}", status_code=204)
def remove_region_attribut(region_id: int, valeur_id: int,
                           conn: sqlite3.Connection = Depends(db),
                           portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    conn.execute("DELETE FROM region_attribut WHERE region_id = ? AND valeur_id = ?",
                 (region_id, valeur_id))
    conn.commit()
