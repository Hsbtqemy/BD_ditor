"""Personnages, attribution et vocabulaire facetté (ANN-2, A5, piste B).

Le registre des ENTITÉS — personnage, locuteur d'une zone de texte, présence dans une
case —, ses alignements sur des référentiels externes (A5), et le vocabulaire FACETTÉ
qui le décrit : domaines, dimensions, valeurs, et l'affectation de ces valeurs à un
personnage ou à une région.

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

from fastapi import APIRouter, Depends, HTTPException, Response

import autorisation
import conflit
import journal
from config import CIBLES_ATTRIBUT, TYPES_LOCUTEUR, TYPES_PRESENCE, TYPES_SITUATION
from database import est_bac_a_sable

from socle import (
    AlignementIn, AttributIn, DimensionDomaineIn, DimensionIn, DomaineIn, FusionIn,
    LexiqueIn, LocuteurIn, PersonnageIn, PersonnageUpdate, PresenceIn, ValeurIn,
    _attributs_de, _clause_personnage, _exiger_une_rive, _get_dimension, _get_personnage,
    _get_region, _get_valeur, _norm_tag, _patch_lexique, _rive_d_un_album,
    _rive_d_un_personnage, _rive_d_un_terme, _row, _rows, _sans_accents, db, portee_courante,
)

router = APIRouter()


def _locuteur_for(conn, region_id):
    """Locuteur attribué à une zone de texte — bulle, cartouche ou texte (ou None) →
    {locuteur: {id, nom, serie} | None}. La table garde le nom qu'elle avait quand seule
    une bulle parlait."""
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
    """Registre des personnages + nombre de zones de texte qui leur sont attribuées.
    `q` filtre par nom (autocomplétion à la saisie / canonicalisation à la volée).

    **`nb_bulles` compte des PRISES DE PAROLE, pas des bulles** (ANN-6) : une ligne par
    région dont le personnage est le locuteur, et un cartouche ou une zone de texte en
    reçoivent un depuis ce chantier. La clé garde son nom parce que renommer une clé de
    réponse est une décision, pas une retouche ; aucun écran ne la lit aujourd'hui.

    AUTH-2 — la portée d'un personnage se DÉRIVE de ses apparitions (cf.
    `_clause_personnage`), et `nb_bulles` ne compte que les zones lisibles : un compteur
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


def _cle_homonyme(nom, serie) -> tuple:
    """Ce qui fait de deux personnages le MÊME : le nom et la série, sans casse ni accents
    (`socle._sans_accents`, la règle du filtre du registre). Une série absente est une
    valeur : « sans série » n'est pas l'homonyme d'une série nommée."""
    serie = (serie or "").strip()
    return _sans_accents((nom or "").strip()), _sans_accents(serie) if serie else None


@router.post("/api/personnages", status_code=201)
def create_personnage(payload: PersonnageIn, response: Response,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """AUTH-2 — le registre des personnages n'appartient à aucune collection : y écrire
    demande le droit d'écrire quelque part, comme pour le vocabulaire global.

    ANN-8 (Hugo, 2026-10-21) — **l'accent ne distingue pas deux personnages** : dans une
    même série, deux noms égaux sans casse ni accents désignent le même. Un personnage
    qu'on VOIT (`_clause_personnage`) et qui porte ce nom dans cette série est donc RENDU au
    lieu d'être créé une seconde fois — 200 au lieu de 201, rien d'écrit, ses notes
    inchangées. L'Atelier, qui crée par ici à Entrée, attribue alors celui qui existe : c'est
    le filet de sa propre règle (`BDPropositions.homonymes`), pour une liste lue avant que
    l'homonyme n'existe. Un personnage qu'on ne voit pas n'est pas retrouvé : le rendre
    dirait qu'il existe, et l'attacherait hors de la portée de qui le demande — on en crée
    un, comme avant. Les noms déjà en double dans la base le restent : aucune fusion ici.

    COL-4 (Hugo, 2026-10-24) — `bac_a_sable_id` : le personnage NAÎT dans ce bac à sable,
    dont l'appelant doit être membre (404 sinon, comme un projet qu'on ne voit pas) — il
    n'existe que pour ses membres, ne s'attribue que là, et part avec lui. Le registre
    demande toujours d'écrire quelque part hors des bacs à sable. L'homonyme se cherche
    dans le même registre : un « Spirou » du registre ne répond pas à qui en crée un dans
    son bac à sable."""
    bac = payload.bac_a_sable_id
    if bac is not None:
        if bac not in portee.bacs_a_sable and not (portee.tout and not portee.bornee):
            raise HTTPException(404, f"Projet {bac} introuvable")
        if not est_bac_a_sable(conn, bac):
            raise HTTPException(422, "Seul un bac à sable a un registre de personnages à "
                                     "lui.")
    elif not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Le registre des personnages est en lecture seule "
                                 "pour vous.")
    nom = (payload.nom or "").strip()
    if not nom:
        raise HTTPException(422, "Nom de personnage vide")
    serie = (payload.serie or "").strip() or None
    cle = _cle_homonyme(nom, serie)
    # Le verrou d'écriture AVANT de chercher : deux créations simultanées de « Étienne » et
    # « etienne » lisaient toutes deux « aucun », et en créaient deux (relecture de la suite
    # d'ANN-8, S4). La seconde attend, et trouve la première.
    conflit.verrouiller(conn)
    ou, params = _clause_personnage(portee)
    for r in conn.execute(f"SELECT p.id, p.nom, p.serie FROM personnages p WHERE {ou} "
                          f"AND p.bac_a_sable_id IS ? ORDER BY p.id", (*params, bac)):
        if _cle_homonyme(r["nom"], r["serie"]) == cle:
            response.status_code = 200
            return _get_personnage(conn, portee, r["id"])
    pid = conn.execute(
        "INSERT INTO personnages (nom, serie, notes, bac_a_sable_id) VALUES (?, ?, ?, ?)",
        (nom, serie, payload.notes, bac)).lastrowid
    conn.commit()
    return _get_personnage(conn, portee, pid)


def _refuser_un_homonyme(conn, portee, personnage_id, nom, serie) -> None:
    """ANN-8 (décision du 2026-10-22) — renommer un personnage, ou changer sa série, ne
    fabrique pas un homonyme à l'accent près dans la même série : 409 qui nomme l'existant
    et renvoie à la fusion. Parmi les personnages qu'on VOIT seulement, comme à la création
    (`create_personnage`) : refuser au nom d'un personnage qu'on ne voit pas dirait qu'il
    existe. Le verrou se prend avant de chercher, pour la raison de la création."""
    conflit.verrouiller(conn)
    cle = _cle_homonyme(nom, serie)
    ou, params = _clause_personnage(portee)
    # COL-4 — dans le même registre : celui du bac à sable du personnage, ou celui de tous.
    bac = conn.execute("SELECT bac_a_sable_id FROM personnages WHERE id = ?",
                       (personnage_id,)).fetchone()[0]
    for r in conn.execute(f"SELECT p.id, p.nom, p.serie FROM personnages p WHERE {ou} "
                          f"AND p.bac_a_sable_id IS ? ORDER BY p.id", (*params, bac)):
        if r["id"] != personnage_id and _cle_homonyme(r["nom"], r["serie"]) == cle:
            dans = f"dans la série « {r['serie']} »" if r["serie"] else "sans série"
            raise HTTPException(409, f"Un personnage « {r['nom']} » existe déjà {dans} : "
                                     "l'accent et la casse ne distinguent pas deux "
                                     "personnages. Fusionnez-les plutôt.")


@router.put("/api/personnages/{personnage_id}")
def update_personnage(personnage_id: int, payload: PersonnageUpdate,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    actuel = _get_personnage(conn, portee, personnage_id, ecriture=True)
    if payload.nom is not None or payload.serie is not None:
        _refuser_un_homonyme(conn, portee, personnage_id,
                             payload.nom if payload.nom is not None else actuel["nom"],
                             payload.serie if payload.serie is not None else actuel["serie"])
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
    # COL-4 — un personnage né dans un bac à sable ne se fond pas dans le registre, ni
    # l'inverse : ses apparitions passeraient la frontière.
    _exiger_une_rive(conn, _rive_d_un_personnage(conn, personnage_id),
                     _rive_d_un_personnage(conn, payload.cible_id))
    # locuteur : une zone a au plus un locuteur (region_id PK) → réaffectation directe.
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
    """Attribue un locuteur à une zone de TEXTE — bulle, cartouche ou texte (ANN-6).

    Le serveur tient la règle de l'écran. Il ne la tenait pas : la cohérence de type était
    « assurée côté UI », si bien que la route posait un locuteur sur une case ou sur une
    boîte personnage (mesuré le 2026-10-12 : 200 sur les cinq types), et que l'écran, lui,
    n'offrait le bloc qu'à la bulle. Les deux se rejoignent sur `config.TYPES_LOCUTEUR`.

    Le refus est un **422 qui nomme le type**, comme `_affecter` refuse une valeur posée
    sur la mauvaise cible : la région est lisible et modifiable par l'appelant — l'accesseur
    gardé vient de le dire —, il n'y a donc rien à taire. Il vient avant la lecture du
    personnage : la question porte sur la région, et sa réponse ne dépend pas de qui
    l'on voulait y faire parler.

    Seule l'ATTRIBUTION est gardée ici. Lire et retirer restent ouverts à tout type : une
    base d'avant ANN-8 porte des cases qui ont gardé le locuteur de la bulle qu'elles
    étaient, et il faut pouvoir le leur retirer. Depuis ANN-8 (Hugo, 2026-10-21), le
    changement de type l'emporte (`PUT /api/regions/{id}`, `database.retirer_locuteur_muet`)
    et `tools/retirer_locuteurs_muets.py` rattrape ce que la base portait déjà.

    **L'ordre des deux contrôles compte, et il est tenu par un test.** L'accesseur gardé EN
    ÉCRITURE passe d'abord : qui ne lit pas la région, ou la lit sans l'écrire, reçoit le
    404 de toute région introuvable, sur une case comme sur une bulle — jamais le 422, qui
    nomme un type. Posée avant l'accesseur, la garde dirait à un inconnu de quel type est
    une région qu'il ne voit pas ; l'accesseur passé en lecture laisserait une lectrice
    attribuer. Les deux fautes laissaient la suite entière verte (relecture du 2026-10-12)
    jusqu'à `test_poser_un_locuteur_sans_ecrire_la_region_repond_introuvable`.

    **L'annulation tient la même règle, par son propre chemin.** Cette garde-ci ne vaut que
    pour la ROUTE, et `undo.py` rejoue un état passé par des mutations brutes, hors routes — c'est sa nature,
    sans quoi chaque annulation se rejournaliserait. Une bulle dont on avait retiré le
    locuteur, passée en case par une collègue, le retrouvait EN TANT QUE CASE au Ctrl+Z
    suivant. Depuis ANN-8 (Hugo, 2026-10-21), `undo._poser_lien` refuse un locuteur sur un
    type qui n'en porte pas : l'acte est passé (`test_l_annulation_ne_repose_pas_un_
    locuteur_sur_une_region_devenue_muette`). « Aucune case ne porte de locuteur » reste
    pourtant hors du schéma : c'est la route, le changement de type et l'annulation qui le
    tiennent, et une base d'avant peut encore en porter.
    """
    conflit.verrouiller(conn)      # CONC-4 : le locuteur actuel se lit sous le verrou
    region = _get_region(conn, portee, region_id, ecriture=True)
    if region["type"] not in TYPES_LOCUTEUR:
        raise HTTPException(422, f"Un locuteur ne s'attribue qu'à une zone de texte "
                                 f"({', '.join(TYPES_LOCUTEUR)}) : cette région est de "
                                 f"type « {region['type']} ».")
    _get_personnage(conn, portee, payload.personnage_id)
    _exiger_le_personnage_ici(conn, payload.personnage_id, region)
    ancien = conn.execute("SELECT personnage_id FROM bulle_locuteur WHERE region_id = ?",
                          (region_id,)).fetchone()
    if "personnage_vu" in payload.model_fields_set:
        _garder_le_lien(conn, "bulle_locuteur", region_id, vu=payload.personnage_vu,
                        actuel=ancien["personnage_id"] if ancien else None,
                        nouveau=payload.personnage_id)
    conn.execute("INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?) "
                 "ON CONFLICT(region_id) DO UPDATE SET personnage_id = excluded.personnage_id",
                 (region_id, payload.personnage_id))
    journal.journaliser(conn, "lien", "bulle_locuteur", region_id,
                        avant=({"personnage_id": ancien["personnage_id"]} if ancien else None),
                        apres={"personnage_id": payload.personnage_id})
    conn.commit()
    return _locuteur_for(conn, region_id)


# CONC-4 — le champ que le 409 nomme pour chaque lien, et ce qui décrit le personnage présent
# (pour que l'écran montre la version de l'autre sans relire).
_LIENS_GARDES = {
    "bulle_locuteur": ("locuteur", lambda conn, rid: _locuteur_for(conn, rid)["locuteur"]),
    "personnage_presence": ("presence",
                            lambda conn, rid: _personnage_for(conn, rid)["personnage"]),
}


def _garder_le_lien(conn, table: str, region_id: int, *, vu, actuel, nouveau) -> None:
    """CONC-4 — refuser une attribution ou un retrait fait sur une valeur PÉRIMÉE (Hugo,
    2026-10-21 : le patron du temps b de CONC-3, `conflit.verifier`).

    Mesuré le 2026-10-25 à deux navigateurs, sur le code d'avant : Alice pose Zed, Bob — dont
    l'écran montrait « aucun » — pose Yann ; la base gardait Yann, et aucun écran n'en disait
    rien. Puis le ✕ d'Alice, qui voyait encore Zed, retirait Yann, en silence.

    `vu` est le personnage que l'écran VOYAIT (un identifiant, ou None pour « aucun »). Si la
    base porte autre chose — et que l'écriture ne pose pas déjà ce qu'elle porte —, c'est le
    409 de CONC-3 : `detail.conflit` avec le champ (`locuteur`, `presence`), le personnage
    présent en `valeur_actuelle` et, en plus, décrit (`personnage` : id, nom, série, ou None),
    et l'auteur du dernier acte qui l'a posé ou ôté — un `lien`/`delien`, ou le changement de
    type qui l'a retiré (ANN-8). Rien n'est écrit. Appelée sous le verrou d'écriture, pris
    AVANT de lire `actuel` : deux attributions simultanées ne passent pas toutes deux.

    L'appelant ne l'appelle que si la valeur vue a été ENVOYÉE : elle reste facultative pour
    l'API (Q8), et sans elle le dernier gagne, comme avant."""
    champ, decrire = _LIENS_GARDES[table]
    try:
        conflit.verifier(conn, table, region_id, champ, vu=vu, actuel=actuel, nouveau=nouveau,
                         sources=((table, "personnage_id"), ("regions", champ)))
    except conflit.Perime as exc:
        detail = exc.detail()
        detail["conflit"]["personnage"] = decrire(conn, region_id)
        raise HTTPException(409, detail)


def _exiger_le_personnage_ici(conn, personnage_id, region: dict) -> None:
    """COL-4 — un personnage né dans un bac à sable ne s'attribue que dans ce bac à sable
    (409 nommé). Un personnage du registre s'attribue partout, bac à sable compris : ses
    apparitions là ne comptent pas pour sa visibilité (`socle._clause_personnage`)."""
    rive = _rive_d_un_personnage(conn, personnage_id)
    if rive:
        album = conn.execute("SELECT album_id FROM planches WHERE id = ?",
                             (region["planche_id"],)).fetchone()
        _exiger_une_rive(conn, rive, _rive_d_un_album(conn, album[0]) if album else 0)


@router.delete("/api/regions/{region_id}/locuteur", status_code=204)
def clear_locuteur(region_id: int, personnage_vu: Optional[int] = None,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Retire le locuteur. CONC-4 — `?personnage_vu=` : celui que l'écran voyait ; s'il n'est
    plus là, 409 nommé (`_garder_le_lien`). Facultatif (Q8)."""
    conflit.verrouiller(conn)      # CONC-4 : le locuteur actuel se lit sous le verrou
    _get_region(conn, portee, region_id, ecriture=True)
    ancien = conn.execute("SELECT personnage_id FROM bulle_locuteur WHERE region_id = ?",
                          (region_id,)).fetchone()
    if personnage_vu is not None:
        _garder_le_lien(conn, "bulle_locuteur", region_id, vu=personnage_vu,
                        actuel=ancien["personnage_id"] if ancien else None, nouveau=None)
    conn.execute("DELETE FROM bulle_locuteur WHERE region_id = ?", (region_id,))
    if ancien:
        journal.journaliser(conn, "delien", "bulle_locuteur", region_id,
                            avant={"personnage_id": ancien["personnage_id"]})
    conn.commit()


# --- Présence : quelle entité est MONTRÉE dans une boîte personnage (§14, brique (a)).
#     Miroir du locuteur, mais pour l'image — la boîte porte l'identité, et le profil de
#     l'entité devient atteignable depuis l'image (muets compris). La cohérence de type
#     (region.type = 'personnage', `config.TYPES_PRESENCE`) est gardée par l'attribution
#     depuis ANN-8 (422), comme le locuteur depuis ANN-6 ; lire et retirer restent ouverts
#     à tout type, pour nettoyer ce qu'une base d'avant porte. Le changement de type retire
#     le personnage d'une région qui cesse d'en montrer un, et l'annulation ne l'y repose pas.
@router.get("/api/regions/{region_id}/personnage")
def get_presence(region_id: int, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id)
    return _personnage_for(conn, region_id)


@router.put("/api/regions/{region_id}/personnage")
def set_presence(region_id: int, payload: PresenceIn, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    conflit.verrouiller(conn)      # CONC-4 : le personnage actuel se lit sous le verrou
    region = _get_region(conn, portee, region_id, ecriture=True)
    # ANN-8 (décision du 2026-10-22) — le miroir du locuteur : seule une boîte personnage
    # montre un personnage. Après l'accesseur gardé, pour la raison de `set_locuteur`.
    if region["type"] not in TYPES_PRESENCE:
        raise HTTPException(422, "Seule une boîte personnage montre un personnage : cette "
                                 f"région est de type « {region['type']} ».")
    _get_personnage(conn, portee, payload.personnage_id)
    _exiger_le_personnage_ici(conn, payload.personnage_id, region)
    ancien = conn.execute("SELECT personnage_id FROM personnage_presence WHERE region_id = ?",
                          (region_id,)).fetchone()
    if "personnage_vu" in payload.model_fields_set:     # CONC-4, cf. `set_locuteur`
        _garder_le_lien(conn, "personnage_presence", region_id, vu=payload.personnage_vu,
                        actuel=ancien["personnage_id"] if ancien else None,
                        nouveau=payload.personnage_id)
    conn.execute("INSERT INTO personnage_presence (region_id, personnage_id) VALUES (?, ?) "
                 "ON CONFLICT(region_id) DO UPDATE SET personnage_id = excluded.personnage_id",
                 (region_id, payload.personnage_id))
    journal.journaliser(conn, "lien", "personnage_presence", region_id,
                        avant=({"personnage_id": ancien["personnage_id"]} if ancien else None),
                        apres={"personnage_id": payload.personnage_id})
    conn.commit()
    return _personnage_for(conn, region_id)


@router.delete("/api/regions/{region_id}/personnage", status_code=204)
def clear_presence(region_id: int, personnage_vu: Optional[int] = None,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Retire le personnage montré ; `?personnage_vu=` : cf. `clear_locuteur` (CONC-4)."""
    conflit.verrouiller(conn)      # CONC-4 : le personnage actuel se lit sous le verrou
    _get_region(conn, portee, region_id, ecriture=True)
    ancien = conn.execute("SELECT personnage_id FROM personnage_presence WHERE region_id = ?",
                          (region_id,)).fetchone()
    if personnage_vu is not None:
        _garder_le_lien(conn, "personnage_presence", region_id, vu=personnage_vu,
                        actuel=ancien["personnage_id"] if ancien else None, nouveau=None)
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
    suppose de pouvoir écrire quelque part.

    **Créer ne rend pas ce qu'on ne lit pas** (AUTH-11, 2026-09-24). Le nom étant unique
    dans TOUTE l'instance (`domaine.nom UNIQUE`), l'`ON CONFLICT(nom) DO NOTHING`
    ci-dessous n'écrit rien sur un domaine existant — mais le `SELECT *` qui suit rendait
    ce domaine entier, qu'on le lise ou non : qui écrivait dans une collection recevait en
    201 la définition, la note de portée et le `collection_id` d'un domaine local à une
    collection qu'il ne lit pas. Même forme, même remède que `POST /api/tags` (`b1c49d0`) :
    l'existant se lit sur EXACTEMENT la clé que compare l'`ON CONFLICT` — le nom
    normalisé —, et un domaine qu'on ne VOIT pas (`portee.clause_terme`) répond **409**
    sans rien en dire ni rien écrire. Le verrou d'écriture (`conflit.verrouiller`) couvre
    tout le trajet : pris avant de lire l'existant, il tient pendant l'`INSERT` et la
    lecture du terme rendu, et ne tombe qu'au `commit`, qui vient APRÈS cette lecture.
    Sans lui — ou avec un rendu lu après le `commit` —, un `PATCH …/lexique` concurrent
    qui rattacherait le domaine à une collection illisible entre la garde et le `SELECT *`
    le ferait rendre quand même.

    Un domaine visible garde le comportement d'avant, lecture seule comprise : le
    `DO NOTHING` ne le modifie pas, et le rendre ne dit rien qu'on ne lise déjà. Le 409
    confirme en revanche que le nom est pris, où qu'il vive — un bit par nom deviné, le
    même oracle que celui déjà accepté pour `socle._ensure_tags` et `POST /api/tags` ; une
    LIMITE écrite, que l'unicité (nom, collection) fermera avec `COL-1`."""
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Créer un domaine demande un droit d'écriture sur au "
                                 "moins une collection.")
    nom = _norm_tag(payload.nom)
    if not nom:
        raise HTTPException(422, "Nom de domaine vide")
    conflit.verrouiller(conn)      # l'existant se lit sous le verrou d'écriture
    ou, params = portee.clause_terme("d.collection_id")
    existant = conn.execute(f"SELECT {ou} AS visible FROM domaine d WHERE d.nom = ?",
                            (*params, nom)).fetchone()
    if existant is not None and not existant["visible"]:
        raise HTTPException(409, "Ce nom de domaine est déjà pris : choisissez-en un autre.")
    conn.execute("INSERT INTO domaine (nom) VALUES (?) ON CONFLICT(nom) DO NOTHING", (nom,))
    rendu = _row(conn.execute("SELECT * FROM domaine WHERE nom = ?", (nom,)))
    conn.commit()                  # le verrou tombe ici, APRÈS la lecture du rendu
    return rendu


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
    """Documente un domaine (même couche SKOS que dimensions/valeurs/tags).

    AUTH-11 (2026-09-25) — le verrou d'écriture (`conflit.verrouiller`) est pris avant toute
    lecture : les gardes du rangement (termes liés, emport de la branche) et l'écriture
    voient le même état. Sans lui, une dimension créée entre la garde et l'UPDATE, dans
    l'ancienne collection d'un domaine qu'on range, restait derrière lui (mesuré par la
    relecture) — et l'argument « les droits des emportés sont ceux de la racine » en
    dépend aussi."""
    conflit.verrouiller(conn)
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
    """Crée une dimension (un axe émergent), ou rend celle qui existe déjà.

    **Créer ne rend pas ce qu'on ne lit pas** (AUTH-11, 2026-09-24) — même défaut et même
    remède que `POST /api/domaines` juste au-dessus : la clé `(cible, nom)` étant unique
    dans toute l'instance, le `SELECT *` qui suit l'`ON CONFLICT … DO NOTHING` rendait en
    201 une dimension locale à une collection qu'on ne lit pas, définition, note de
    portée, `collection_id` et `domaine_id` compris. Une dimension existante qu'on ne VOIT
    pas répond donc **409**, sans rien en dire ni rien écrire ; l'existant se lit sur la
    clé exacte de l'`ON CONFLICT` (la cible et le nom normalisé). Le verrou d'écriture est
    pris avant cette lecture et ne tombe qu'au `commit`, qui suit la lecture du terme
    rendu : la garde, l'`INSERT` et le rendu voient le même état. Une dimension visible
    garde le comportement d'avant, lecture seule comprise (`DO NOTHING` ne la modifie
    pas). Le 409 confirme qu'un nom est pris : le même oracle d'un bit que
    `socle._ensure_tags` et `POST /api/tags`, LIMITE écrite que l'unicité par collection
    fermera avec `COL-1`."""
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Créer une dimension demande un droit d'écriture sur au "
                                 "moins une collection.")
    if payload.cible not in CIBLES_ATTRIBUT:
        raise HTTPException(422, f"Cible invalide : {payload.cible} (personnage | case).")
    nom = _norm_tag(payload.nom)
    if not nom:
        raise HTTPException(422, "Nom de dimension vide")
    conflit.verrouiller(conn)      # l'existant se lit sous le verrou d'écriture
    ou, params = portee.clause_terme("d.collection_id")
    existant = conn.execute(f"SELECT {ou} AS visible FROM attribut_dimension d "
                            f"WHERE d.cible = ? AND d.nom = ?",
                            (*params, payload.cible, nom)).fetchone()
    if existant is not None and not existant["visible"]:
        raise HTTPException(409, "Ce nom de dimension est déjà pris : choisissez-en un "
                                 "autre.")
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
    rendu = _row(conn.execute("SELECT * FROM attribut_dimension WHERE cible = ? AND nom = ?",
                              (payload.cible, nom)))
    conn.commit()                  # le verrou tombe ici, APRÈS la lecture du rendu
    return rendu


@router.patch("/api/attributs/dimensions/{dim_id}/domaine")
def patch_dimension_domaine(dim_id: int, payload: DimensionDomaineIn,
                            conn: sqlite3.Connection = Depends(db),
                            portee: autorisation.Portee = Depends(portee_courante)):
    """Rattache une dimension à un domaine (ou l'en détache avec `domaine_id: null`).

    **Un rattachement ne déplace JAMAIS une portée** — renversement daté, tranché par Hugo
    le 2026-09-24 (AUTH-11). v24 faisait suivre la portée : une dimension GLOBALE passée
    sous un domaine PRIVÉ y descendait avec ses valeurs globales — ce qui les retirait sans
    un mot à toutes les autres collections —, et une dimension LOCALE passée sous un
    domaine GLOBAL devenait globale — ce qui publiait son nom à toute l'instance. Deux
    déplacements que personne n'avait demandés, par un geste de rangement.

    Désormais :
    - sous un domaine GLOBAL, ou de la même collection que la dimension : permis, et rien
      ne bouge (une dimension plus locale que son domaine est légitime, A4) ;
    - sous un domaine LOCAL à une autre collection que la sienne — dimension globale
      comprise, qui serait plus globale que son domaine (v24) : **409**, qui dit de ranger
      d'abord la dimension dans la collection du domaine (`PATCH …/lexique`, menu Portée du
      📖 Lexique) — sans promettre que ce rangement réussira : depuis le 2026-09-25, il est
      refusé à son tour si un terme lié à la dimension est rangé dans une troisième
      collection, et son propre 409 le dit. C'est ce geste-là qui déplace la portée — la
      dimension, ses valeurs GLOBALES qui descendent avec elle, et, si elle est la racine
      de sa branche, ses valeurs restées dans son ancienne collection (option β, même
      jour). La réponse nomme ces dernières dans `promus`, pas les valeurs globales
      descendues ; l'écran recharge le lexique après le rangement. Pour une dimension
      déjà rangée sous un domaine de sa collection, le vrai chemin est de la détacher, la
      ranger, puis la rattacher : rangée seule, elle serait le milieu d'une branche, et
      son propre rangement serait refusé. Le message nomme le domaine, que l'appelant
      vient de choisir et lit ; rien d'autre.

    Le verrou d'écriture (`conflit.verrouiller`) est pris avant de lire la dimension et le
    domaine, comme dans les autres routes d'AUTH-11 : la garde et l'écriture voient le même
    état, et un `PATCH …/lexique` concurrent ne peut pas changer une portée entre les deux.

    DÉTACHER ne promeut pas. `domaine_id: null` laisse la portée en place, alors que la
    création sans domaine naît globale : les deux ne sont pas le même geste. Sortir une
    dimension de son domaine est un rangement ; la rendre globale au passage serait une
    publication que personne n'a demandée.

    L'import de vocabulaire refuse les mêmes cas (`lexique_import`, motif
    `parent_ailleurs`).
    """
    conflit.verrouiller(conn)      # la garde et l'écriture voient le même état
    dim = _get_dimension(conn, portee, dim_id, ecriture=True)
    if payload.domaine_id is not None:
        dom = _get_domaine(conn, portee, payload.domaine_id, ecriture=True)
        # COL-4 — ni sous un domaine d'un bac à sable depuis le corpus, ni l'inverse.
        _exiger_une_rive(conn, _rive_d_un_terme(conn, dim["collection_id"]),
                         _rive_d_un_terme(conn, dom["collection_id"]))
        if dom["collection_id"] is not None and dim["collection_id"] != dom["collection_id"]:
            raise HTTPException(409, f"Le domaine « {dom['nom']} » est propre à une "
                                     f"collection, et cette dimension n'y est pas rangée. "
                                     f"Rangez d'abord la dimension dans la collection du "
                                     f"domaine (📖 Lexique, menu Portée) — si elle est déjà "
                                     f"sous un autre domaine, détachez-la avant —, puis "
                                     f"rattachez-la ; si ce rangement est refusé à son tour, "
                                     f"son refus dit quel terme lié l'en empêche.")
    conn.execute("UPDATE attribut_dimension SET domaine_id = ? WHERE id = ?",
                 (payload.domaine_id, dim_id))
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
    """Crée une valeur canonique sous une dimension, ou rend celle qui existe déjà.

    La dimension est gardée d'abord (`_get_dimension(ecriture=True)`) : invisible → 404,
    visible en lecture seule → 403, AVANT qu'on regarde les valeurs — ce qui vit sous une
    dimension qu'on ne peut pas modifier n'est donc jamais interrogé.

    **Créer ne rend pas ce qu'on ne lit pas** (AUTH-11, 2026-09-24) — même défaut et même
    remède que `POST /api/domaines` et `POST /api/attributs/dimensions` : la clé
    `(dimension_id, valeur)` étant unique quelle que soit la portée, une valeur LOCALE à
    une collection qu'on ne lit pas peut vivre sous une dimension qu'on lit et modifie
    (une dimension globale, typiquement), et le `SELECT *` qui suit l'`ON CONFLICT … DO
    NOTHING` la rendait entière en 201 — définition, note de portée, `collection_id`.
    Une valeur existante qu'on ne VOIT pas répond donc **409**, sans rien en dire ni rien
    écrire ; l'existant se lit sur la clé exacte de l'`ON CONFLICT` (la dimension et la
    valeur normalisée). Le verrou d'écriture est pris avant toute lecture — la dimension
    comprise — et ne tombe qu'au `commit`, qui suit la lecture de la valeur rendue : les
    gardes, l'`INSERT` et le rendu voient le même état. Une valeur visible garde le
    comportement d'avant (`DO NOTHING` ne la modifie pas). Le 409 confirme qu'une valeur
    est prise sous cette dimension : le même oracle d'un bit que `socle._ensure_tags` et
    `POST /api/tags`, LIMITE écrite que l'unicité par collection fermera avec `COL-1`."""
    conflit.verrouiller(conn)      # la dimension et l'existant se lisent sous le verrou
    dim = _get_dimension(conn, portee, dim_id, ecriture=True)
    valeur = _norm_tag(payload.valeur)
    if not valeur:
        raise HTTPException(422, "Valeur vide")
    ou, params = portee.clause_terme("v.collection_id")
    existant = conn.execute(f"SELECT {ou} AS visible FROM attribut_valeur v "
                            f"WHERE v.dimension_id = ? AND v.valeur = ?",
                            (*params, dim_id, valeur)).fetchone()
    if existant is not None and not existant["visible"]:
        raise HTTPException(409, "Cette valeur est déjà prise dans cette dimension : "
                                 "choisissez-en une autre.")
    # AUTH-2 — même héritage qu'un cran plus haut : la valeur prend la portée de sa
    # dimension. La route ne posait aucun `collection_id`, si bien que toute valeur
    # naissait GLOBALE — y compris sous un axe d'analyse local à une étude. Le dommage
    # n'est pas le mot (« palpable » ne dit rien) mais ce qu'il traîne : les routes à plat
    # renvoient le NOM de sa dimension.
    conn.execute("INSERT INTO attribut_valeur (dimension_id, valeur, collection_id) "
                 "VALUES (?, ?, ?) ON CONFLICT(dimension_id, valeur) DO NOTHING",
                 (dim_id, valeur, dim["collection_id"]))
    rendu = _row(conn.execute("SELECT * FROM attribut_valeur WHERE dimension_id = ? "
                              "AND valeur = ?", (dim_id, valeur)))
    conn.commit()                  # le verrou tombe ici, APRÈS la lecture du rendu
    return rendu


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
    # COL-4 — une valeur d'un bac à sable ne se fond pas dans une valeur du corpus, ni
    # l'inverse : ses emplois passeraient la frontière.
    _exiger_une_rive(conn, _rive_d_un_terme(conn, v["collection_id"]),
                     _rive_d_un_terme(conn, cible["collection_id"]))
    for table, col in (("personnage_attribut", "personnage_id"), ("region_attribut", "region_id")):
        conn.execute(f"INSERT OR IGNORE INTO {table} ({col}, valeur_id) "
                     f"SELECT {col}, ? FROM {table} WHERE valeur_id = ?", (payload.cible_id, val_id))
    conn.execute("DELETE FROM attribut_valeur WHERE id = ?", (val_id,))   # CASCADE purge le reste
    conn.commit()
    return _get_valeur(conn, portee, payload.cible_id, ecriture=True)






def _affecter(conn, portee, table, col, oid, valeur_id, cible_attendue):
    """Affecte une valeur à une cible, après contrôle de cohérence de la dimension.

    COL-3, tranche 2 — l'attribut d'une CASE s'écrit au journal (`lien`, cible
    `region_attribut`, `cible_id` = la région, la valeur dans la charge) : c'est du travail
    sur l'album, et « supprimer définitivement » demande de savoir si quelqu'un d'autre y a
    travaillé (`autorisation._sql_travail_d_autrui`). `region_attribut` n'a pas d'auteur ;
    le journal en tient lieu. Un attribut de PERSONNAGE ne s'écrit pas : il ne tient à
    aucun album. Re-poser un attribut déjà là n'écrit rien."""
    v = _get_valeur(conn, portee, valeur_id)
    if _get_dimension(conn, portee, v["dimension_id"])["cible"] != cible_attendue:
        raise HTTPException(422, f"Cette valeur n'appartient pas à une dimension de {cible_attendue}.")
    # COL-4 — une valeur d'un bac à sable ne se pose que dans ce bac à sable. Une valeur du
    # corpus posée dans un bac à sable n'y emporte rien hors de lui : permis.
    rive = _rive_d_un_terme(conn, v["collection_id"])
    if rive and table == "region_attribut":
        album = conn.execute("SELECT pl.album_id FROM regions r JOIN planches pl "
                             "ON pl.id = r.planche_id WHERE r.id = ?", (oid,)).fetchone()
        _exiger_une_rive(conn, rive, _rive_d_un_album(conn, album[0]) if album else 0)
    elif rive:
        # Un personnage du registre (rive 0), ou né dans un AUTRE bac à sable.
        _exiger_une_rive(conn, rive, _rive_d_un_personnage(conn, oid))
    pose = conn.execute(f"INSERT OR IGNORE INTO {table} ({col}, valeur_id) VALUES (?, ?)",
                        (oid, valeur_id)).rowcount
    if pose and table == "region_attribut":
        journal.journaliser(conn, "lien", "region_attribut", oid,
                            apres={"valeur_id": valeur_id})
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
    _get_valeur(conn, portee, valeur_id)   # la route sœur de S3 : retirer demande de voir
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
    region = _get_region(conn, portee, region_id, ecriture=True)
    # ANN-8 (décision du 2026-10-22) — seule une case reçoit une situation (422).
    if region["type"] not in TYPES_SITUATION:
        raise HTTPException(422, "Seule une case reçoit une situation : cette région est de "
                                 f"type « {region['type']} ».")
    _affecter(conn, portee, "region_attribut", "region_id", region_id, payload.valeur_id, "case")
    return _attributs_de(conn, portee, "region_attribut", "region_id", region_id)


@router.delete("/api/regions/{region_id}/attributs/{valeur_id}", status_code=204)
def remove_region_attribut(region_id: int, valeur_id: int,
                           conn: sqlite3.Connection = Depends(db),
                           portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    # Retirer une valeur demande de la VOIR, comme la poser (`_affecter`) : sans quoi, son
    # identifiant suffisait à effacer la situation locale d'une collection qu'on ne lit pas
    # (relecture de la suite d'ANN-8, S3). 404, la valeur n'existe pas pour l'appelant.
    _get_valeur(conn, portee, valeur_id)
    if conn.execute("DELETE FROM region_attribut WHERE region_id = ? AND valeur_id = ?",
                    (region_id, valeur_id)).rowcount:
        journal.journaliser(conn, "delien", "region_attribut", region_id,
                            avant={"valeur_id": valeur_id})
    conn.commit()
