"""Personnages et attribution (ANN-2, A5).

Le registre des ENTITÉS — personnage, locuteur d'une zone de texte, présence dans une
case — et ses alignements sur des référentiels externes (A5).

Le vocabulaire FACETTÉ qui le décrivait — domaines, dimensions, valeurs, et leur
affectation à un personnage ou à une région — vivait ici jusqu'au basculement d'ANN-7 :
ses routes sont retirées, la situation d'une case et le profil d'un personnage deviennent
des grilles (`docs/ann7-tranche3-cadrage.md`).

Ce qui N'est PAS ici, et c'est délibéré : `_clause_personnage` et `_get_personnage`
vivent dans `socle.py`. La portée d'un personnage est DÉRIVÉE de ses apparitions
(AUTH-2) et d'autres modules s'en servent ; les garder ici les aurait obligés à remonter
vers celui-ci, puis vers `main`.

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
from config import TYPES_LOCUTEUR, TYPES_PRESENCE
from database import est_bac_a_sable

from socle import (
    AlignementIn, FusionIn, LocuteurIn, PersonnageIn, PersonnageUpdate, PresenceIn,
    _clause_personnage, _exiger_une_rive, _get_personnage, _get_region, _rive_d_un_album,
    _rive_d_un_personnage, _row, _rows, _sans_accents, db, portee_courante,
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
    conn.execute("DELETE FROM personnages WHERE id = ?", (personnage_id,))   # CASCADE : détache les liens
    conn.commit()


@router.post("/api/personnages/{personnage_id}/fusion")
def fusionner_personnage(personnage_id: int, payload: FusionIn,
                         conn: sqlite3.Connection = Depends(db),
                         portee: autorisation.Portee = Depends(portee_courante)):
    """Fusionne `personnage_id` (doublon) DANS `cible_id` (canonique) : réaffecte les
    liens locuteur, les personnages montrés et les alignements, puis supprime le doublon.
    Idempotent sur les affectations (INSERT OR IGNORE). Soupape du modèle mentions→entités (curation). (Le
    profil, `personnage_attribut`, suivait aussi jusqu'au basculement d'ANN-7 : il ne se lit
    plus, et part avec le doublon.)"""
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
    # ANN-8 — présence : une boîte montre au plus un personnage (region_id PK), donc la même
    # réaffectation directe, sans doublon possible. Oubliée, les présences du doublon
    # partaient par CASCADE avec lui : la boîte perdait son personnage sans rien dire. Comme
    # pour le locuteur, rien n'est écrit au journal (R3 de `docs/undo.md`).
    conn.execute("UPDATE personnage_presence SET personnage_id = ? WHERE personnage_id = ?",
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
