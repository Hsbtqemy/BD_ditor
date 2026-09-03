"""Socle commun des routes de l'API — dépendances, helpers, accesseurs gardés.  ARCH-1.

`main.py` a franchi les 4 400 lignes pour 125 routes, contre un seuil de 3 200 déclaré
dans `pilotage/journal.config.mjs`. Le découpage se fait par DOMAINE (`routes/`), et ce
module porte ce dont tous les domaines dépendent — mesuré avant de découper : chaque bloc
de main.py n'utilisait que 5 à 20 noms définis ailleurs, et presque toujours les mêmes.

**Ce module ne définit AUCUNE route.** Il n'importe pas `main`, ce qui garantit l'absence
de cycle : `routes/*` importe `socle`, `main` importe `routes/*`.

Deux choses y gagnent plus qu'un rangement.

Les **accesseurs gardés** (`_get_album`, `_get_planche`, `_get_region`) sont, dit
CLAUDE.md, « la seule façon d'atteindre un objet du corpus ». C'était jusqu'ici une
convention : rien n'empêchait un nouveau bloc d'écrire son propre `SELECT * FROM albums`.
Les rassembler dans un module que les routes doivent IMPORTER en fait une contrainte
qu'on voit, sans rien changer à leur comportement.

Et `main.py` **ré-exporte** tout ce qui suit. Ce n'est pas de la compatibilité par
paresse : `tests/test_autorisation.py` compare l'IDENTITÉ de `main.portee_courante` aux
dépendances de chaque route, et `tests/test_sorties_identite.py` balaie les routes depuis
`main`. Le ré-export garde ces cliquets exacts sans qu'une ligne en soit réécrite — ce que
la fiche ARCH-1 posait comme condition du découpage.
"""
from __future__ import annotations

import sqlite3
import unicodedata
from typing import Iterator, Optional

from fastapi import Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

import autorisation
from database import get_connection

# --------------------------------------------------------------------------- #
# Dépendance connexion
# --------------------------------------------------------------------------- #


def db() -> Iterator[sqlite3.Connection]:
    """Une connexion par requête. Le commit est fait EXPLICITEMENT dans chaque
    route d'écriture (et non après le yield) : le code post-yield d'une
    dépendance FastAPI s'exécute APRÈS l'envoi de la réponse, ce qui rendait
    une écriture invisible à une lecture immédiate (course écriture→lecture).
    Ici la dépendance ne gère que le rollback en cas d'erreur et la fermeture.
    """
    conn = get_connection()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def portee_courante(request: Request,
                    conn: sqlite3.Connection = Depends(db)) -> autorisation.Portee:
    """Dépendance FastAPI : la portée d'autorisation de la requête courante (AUTH-2).

    Enveloppe minuscule autour de `autorisation.resoudre` — la logique vit dans le module,
    pas ici. Toute route qui touche aux données du corpus déclare CETTE dépendance ; c'est
    ce que vérifie `tests/test_autorisation.py`, qui échoue si une route l'oublie.
    """
    return autorisation.resoudre(conn, request)


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _row(cur) -> Optional[dict]:
    r = cur.fetchone()
    return dict(r) if r else None


# --------------------------------------------------------------------------- #
# Helpers métier
# --------------------------------------------------------------------------- #
def _norm_tag(label: str) -> str:
    """Tags insensibles à la casse, stockés en minuscules, espaces compactés."""
    return " ".join(label.strip().lower().split())


def _sans_accents(s: str) -> str:
    """Minuscule sans diacritiques — pour une autocomplétion insensible aux accents
    (« etienne » trouve « Étienne »)."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _ensure_tags(conn: sqlite3.Connection, labels: list[str]) -> list[dict]:
    """Crée les tags manquants et renvoie les lignes correspondantes."""
    normalized = sorted({_norm_tag(l) for l in labels if _norm_tag(l)})
    for label in normalized:
        conn.execute(
            "INSERT INTO tags (label) VALUES (?) ON CONFLICT(label) DO NOTHING",
            (label,),
        )
    if not normalized:
        return []
    placeholders = ",".join("?" * len(normalized))
    return _rows(conn.execute(
        f"SELECT id, label, couleur FROM tags WHERE label IN ({placeholders})",
        normalized,
    ))


def _annotation_for_region(conn: sqlite3.Connection, region_id: int) -> dict:
    """Représentation d'annotation (note + tags) ; structure vide si absente."""
    ann = conn.execute(
        "SELECT id, note, date_creation, date_modification "
        "FROM annotations WHERE region_id = ?", (region_id,)
    ).fetchone()
    if ann is None:
        return {"region_id": region_id, "note": None, "tags": [],
                "date_modification": None}
    tags = _rows(conn.execute(
        """SELECT t.id, t.label, t.couleur
           FROM annotation_tags at JOIN tags t ON t.id = at.tag_id
           WHERE at.annotation_id = ? ORDER BY t.label""",
        (ann["id"],),
    ))
    return {"region_id": region_id, "note": ann["note"], "tags": tags,
            "date_modification": ann["date_modification"]}


# --------------------------------------------------------------------------- #
# Accesseurs GARDÉS (AUTH-2) — la seule façon d'atteindre un objet du corpus
# --------------------------------------------------------------------------- #
# Chacun exige une `Portee` et renvoie 404 quand l'objet existe mais sort d'elle. Le 404
# n'est pas une approximation du 403 : dire « cet album existe, mais pas pour vous »
# révélerait la composition du corpus — combien d'albums, quelles études voisines. La
# contrepartie est à connaître : qui perd un droit ne verra pas d'erreur, ses objets
# auront simplement disparu.
#
# La `Portee` est un paramètre OBLIGATOIRE, sans valeur par défaut. Une valeur par défaut
# qui sauterait le contrôle rendrait l'oubli invisible — c'est exactement le motif que
# SANTE-1 vient de corriger ailleurs dans ce dépôt.

def _get_album(conn, portee: autorisation.Portee, album_id: int, *,
               ecriture: bool = False) -> dict:
    ou, params = portee.clause_album("albums.id", ecriture=ecriture)
    a = _row(conn.execute(f"SELECT * FROM albums WHERE id = ? AND {ou}",
                          (album_id, *params)))
    if a is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
    return a


def _get_planche(conn, portee: autorisation.Portee, planche_id: int, *,
                 ecriture: bool = False) -> dict:
    ou, params = portee.clause_album("planches.album_id", ecriture=ecriture)
    p = _row(conn.execute(f"SELECT * FROM planches WHERE id = ? AND {ou}",
                          (planche_id, *params)))
    if p is None:
        raise HTTPException(404, f"Planche {planche_id} introuvable")
    return p


def _get_region(conn, portee: autorisation.Portee, region_id: int, *,
                ecriture: bool = False) -> dict:
    """Une région s'autorise par sa planche, qui s'autorise par son album."""
    ou, params = portee.clause_album("pl.album_id", ecriture=ecriture)
    r = _row(conn.execute(
        f"SELECT r.* FROM regions r JOIN planches pl ON pl.id = r.planche_id "
        f"WHERE r.id = ? AND {ou}", (region_id, *params)))
    if r is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    return r


def _refuser_si_verrouillee(planche: dict) -> dict:
    """Une planche verrouillée est protégée des passes AUTOMATIQUES (segmentation /
    détection de bulles / OCR) : il faut la déverrouiller explicitement. L'édition
    manuelle (texte, tags, régions) reste libre. Renvoie la planche pour chaînage."""
    if planche.get("verrouillee"):
        raise HTTPException(409, "Planche verrouillée 🔒 : déverrouillez-la pour "
                            "relancer un traitement automatique "
                            "(l'édition manuelle reste possible).")
    return planche


def _validate_parent(conn: sqlite3.Connection, planche_id: int,
                     parent_id: Optional[int], region_id: Optional[int] = None) -> None:
    """Valide un parent_id : il doit exister, être sur LA MÊME planche, et ne pas
    créer de cycle (ni s'auto-référencer). Lève HTTPException 422 sinon. Une FK
    seule ne garantit pas ces invariants — sans quoi une région cross-planche ou
    un cycle casse l'export (région omise) et fait boucler le DELETE récursif."""
    if parent_id is None:
        return
    parent = _row(conn.execute(
        "SELECT planche_id FROM regions WHERE id = ?", (parent_id,)))
    if parent is None:
        raise HTTPException(422, f"parent_id {parent_id} introuvable")
    if parent["planche_id"] != planche_id:
        raise HTTPException(422, "parent_id appartient à une autre planche")
    if region_id is not None:
        if parent_id == region_id:
            raise HTTPException(422, "Une région ne peut pas être son propre parent")
        # parent_id ne doit pas être un descendant de region_id (UNION → termine
        # même si la base contient déjà un cycle).
        descendants = {r["id"] for r in conn.execute(
            """WITH RECURSIVE d(id) AS (
                   SELECT id FROM regions WHERE id = ?
                   UNION
                   SELECT r.id FROM regions r JOIN d ON r.parent_id = d.id
               ) SELECT id FROM d""", (region_id,))}
        if parent_id in descendants:
            raise HTTPException(422, "parent_id créerait un cycle")

# --------------------------------------------------------------------------- #
# Accesseurs GARDÉS du VOCABULAIRE (AUTH-2) — VOIR n'est pas CHANGER
# --------------------------------------------------------------------------- #
# Même garde que ci-dessus, autre règle : un terme se VOIT par `clause_terme` (global,
# ou local à une collection qu'on lit) et se MODIFIE par `peut_ecrire_terme`. D'où le
# refus en 403 et non en 404 — le terme vient d'être listé, prétendre qu'il n'existe
# pas serait incohérent, et le refus ne parle que des droits de l'appelant.
#
# Ils descendent ici parce qu'ils sont à CHEVAL sur la coupe : définis dans le bloc
# Personnages, ils servent au bloc Collections (lexique) — les laisser en place aurait
# obligé `routes/collections.py` à remonter vers `main`, ce qu'un cliquet interdit.

def _get_dimension(conn, portee: autorisation.Portee, dim_id, *, ecriture: bool = False):
    """Terme du vocabulaire, VISIBLE (404 sinon) et, si `ecriture`, MODIFIABLE.

    Le refus d'écriture est un 403 et non un 404, contrairement aux données : le
    terme vient d'être listé, prétendre qu'il n'existe pas serait incohérent — et
    le refus ne parle que des droits de l'appelant, il ne fuit rien.
    """
    ou, params = portee.clause_terme("t.collection_id")
    d = _row(conn.execute(
        f"SELECT t.* FROM attribut_dimension t WHERE t.id = ? AND {ou}", (dim_id, *params)))
    if d is None:
        raise HTTPException(404, f"Dimension {dim_id} introuvable")
    if ecriture and not portee.peut_ecrire_terme(d.get("collection_id")):
        raise HTTPException(403, "Ce terme du vocabulaire est en lecture seule "
                                 "pour vous.")
    return d


def _get_valeur(conn, portee: autorisation.Portee, val_id, *, ecriture: bool = False):
    """Terme du vocabulaire, VISIBLE (404 sinon) et, si `ecriture`, MODIFIABLE.

    Le refus d'écriture est un 403 et non un 404, contrairement aux données : le
    terme vient d'être listé, prétendre qu'il n'existe pas serait incohérent — et
    le refus ne parle que des droits de l'appelant, il ne fuit rien.
    """
    ou, params = portee.clause_terme("t.collection_id")
    v = _row(conn.execute(
        f"SELECT t.* FROM attribut_valeur t WHERE t.id = ? AND {ou}", (val_id, *params)))
    if v is None:
        raise HTTPException(404, f"Valeur d'attribut {val_id} introuvable")
    if ecriture and not portee.peut_ecrire_terme(v.get("collection_id")):
        raise HTTPException(403, "Ce terme du vocabulaire est en lecture seule "
                                 "pour vous.")
    return v


def _attributs_de(conn, portee, table, col, oid):
    """Valeurs (avec leur dimension) affectées à une cible (personnage | région).

    AUTH-2 — les valeurs sont filtrées comme des TERMES : sans cela, un objet partagé
    (typiquement un personnage, qui traverse les albums) exposerait le vocabulaire privé
    d'une autre étude — sa grille d'analyse, pas seulement un mot. Écart trouvé en
    relisant : `GET /api/attributs/valeurs` masquait déjà ces termes, mais on les
    retrouvait ici par la bande.

    Conséquence assumée : la liste d'attributs d'un objet peut être PARTIELLE. C'est le
    bon compromis — un objet peut légitimement porter les annotations d'études auxquelles
    on ne participe pas, et il vaut mieux ne pas les montrer que de montrer un vocabulaire
    qu'on ne peut ni comprendre ni situer.

    La DIMENSION est filtrée à son tour (relecture du 2026-08-28). Les routes de création
    ne posaient aucun `collection_id` : toute base antérieure à v24 contient des valeurs
    globales sous des axes privés, et c'est le NOM de l'axe qui fuit, pas le mot. Les
    créations héritent désormais de leur parent, et la migration v24 recolle l'existant ;
    ce filtre-ci reste la ceinture.
    """
    ou, params = portee.clause_terme("v.collection_id")
    ou_dim, p_dim = portee.clause_terme("d.collection_id")
    return _rows(conn.execute(
        f"SELECT v.id AS valeur_id, v.valeur, d.id AS dimension_id, d.nom AS dimension, d.cible "
        f"FROM {table} x JOIN attribut_valeur v ON v.id = x.valeur_id "
        f"JOIN attribut_dimension d ON d.id = v.dimension_id "
        f"WHERE x.{col} = ? AND {ou} AND {ou_dim} ORDER BY d.nom, v.valeur",
        (oid, *params, *p_dim)))


_ETATS_LEXIQUE = ("provisoire", "defini")


def _patch_lexique(conn, table, oid, payload, portee, *, col_definition="definition"):
    """Mise à jour PARTIELLE de la couche définitionnelle (definition/note_portee/etat/
    collection_id) d'un terme. `col_definition='description'` pour les tags (leur glose EST
    la définition). Valide l'état et l'existence de la collection de portée. Champ omis =
    inchangé ; `collection_id: null` explicite = promotion en global."""
    fields = payload.model_dump(exclude_unset=True)
    updates = {}
    if "definition" in fields:
        updates[col_definition] = fields["definition"]
    for k in ("note_portee", "etat", "collection_id"):
        if k in fields:
            updates[k] = fields[k]
    if "etat" in updates and updates["etat"] not in _ETATS_LEXIQUE:
        raise HTTPException(422, f"État invalide : {updates['etat']} (provisoire | defini).")
    # AUTH-2 — changer la PORTÉE d'un terme, c'est le déplacer chez quelqu'un (ou l'en
    # sortir). Il faut donc écrire dans la collection VISÉE, pas seulement dans celle
    # d'origine : sans cela, on rangerait son vocabulaire dans l'étude d'un autre.
    if "collection_id" in updates:
        cible = updates["collection_id"]
        if cible is None:
            if not portee.peut_ecrire_quelque_part():
                raise HTTPException(403, "Promouvoir un terme en global demande un droit "
                                         "d'écriture.")
        elif not portee.peut_ecrire(cible):
            raise HTTPException(404, f"Collection {cible} introuvable.")
        elif conn.execute("SELECT 1 FROM collection WHERE id = ?",
                          (cible,)).fetchone() is None:
            raise HTTPException(404, f"Collection {cible} introuvable.")
    if updates:
        cols = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE {table} SET {cols} WHERE id = ?", (*updates.values(), oid))
        conn.commit()


# --------------------------------------------------------------------------- #
# Portée DÉRIVÉE — le registre des personnages (AUTH-2)
# --------------------------------------------------------------------------- #

def _clause_personnage(portee: autorisation.Portee) -> tuple[str, list]:
    """Visibilité d'un personnage (`p.id`), DÉRIVÉE de ses apparitions.  AUTH-2.

    `personnages` est un registre posé à côté du corpus : la table ne porte aucune
    collection, et lui en ajouter une reviendrait à demander, à la création, à quelle
    collection appartient un personnage — question sans bonne réponse pour une série qui
    traverse plusieurs albums. La portée se dérive donc de l'usage : on voit un personnage
    qui apparaît quelque part où l'on peut lire.

    Avec une exception nécessaire : le personnage qui n'apparaît NULLE PART reste visible.
    Sans elle, le geste courant — créer le personnage, puis lui attribuer une bulle —
    serait cassé, l'entité disparaissant à l'instant même de sa création, y compris pour
    la personne qui vient de la créer.

    Ce n'est pas une mesure de confidentialité : quiconque accède à l'instance peut déjà
    télécharger la base entière (décision du 2026-08-27, cf. docs/hebergement-securite.md
    §6). C'est une mesure d'USAGE — sans elle, l'autocomplétion de locuteur grossit avec
    l'instance entière au lieu de rester à la taille de l'étude en cours.
    """
    ou, pp = portee.clause_album("pl.album_id")
    if ou == "1":
        return "1", []
    apparait = (
        "EXISTS (SELECT 1 FROM {table} x "
        "          JOIN regions r   ON r.id = x.region_id "
        "          JOIN planches pl ON pl.id = r.planche_id "
        f"        WHERE x.personnage_id = p.id AND {ou})")
    jamais = ("NOT EXISTS (SELECT 1 FROM bulle_locuteur b WHERE b.personnage_id = p.id) "
              "AND NOT EXISTS (SELECT 1 FROM personnage_presence q "
              "                WHERE q.personnage_id = p.id)")
    return (f"(({jamais}) "
            f" OR {apparait.format(table='bulle_locuteur')} "
            f" OR {apparait.format(table='personnage_presence')})",
            [*pp, *pp])


def _get_personnage(conn, portee: autorisation.Portee, personnage_id, *,
                    ecriture: bool = False):
    """Personnage VISIBLE (404 sinon) et, si `ecriture`, modifiable.

    Un personnage n'appartient à aucune collection (sa portée se DÉRIVE de ses
    apparitions) : il n'y a donc pas de collection sur laquelle vérifier le droit
    d'écrire. La règle est celle du vocabulaire global — écrire quelque part suffit,
    personne ne possède le registre."""
    ou, params = _clause_personnage(portee)
    p = _row(conn.execute(
        f"SELECT p.* FROM personnages p WHERE p.id = ? AND {ou}",
        (personnage_id, *params)))
    if p is None:
        raise HTTPException(404, f"Personnage {personnage_id} introuvable")
    if ecriture and not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Le registre des personnages est en lecture seule "
                                 "pour vous.")
    return p


# --------------------------------------------------------------------------- #
# Sortie CSV — partagée par la recherche et l'export (ARCH-1)
# --------------------------------------------------------------------------- #
# Ces trois-là vivaient dans le bloc Recherche, où l'Export allait les chercher. Le
# découpage rend la dépendance visible au lieu de la laisser au hasard du voisinage —
# et `_csv_safe` porte une règle de sécurité (anti-injection de formule) qui gagne au
# même titre que les accesseurs gardés à être un import plutôt qu'une convention.
_BOM = chr(0xFEFF)   # BOM UTF-8 : permet à Excel (Windows) de lire les accents correctement


def _csv_response(contenu: str, filename: str) -> Response:
    """Réponse CSV téléchargeable, préfixée d'un BOM UTF-8 pour qu'Excel (Windows) lise
    correctement les accents français. (R/pandas : lire en `utf-8-sig`.)"""
    return Response(content=_BOM + contenu, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _csv_safe(v):
    """Neutralise l'injection de FORMULE (CSV → tableur) : une cellule TEXTE débutant par
    `= + - @` (ou tab/CR) est préfixée d'une apostrophe → un tableur l'affiche littéralement
    au lieu de l'exécuter. À n'appliquer qu'au texte libre (pas aux nombres : « -5 » reste un
    nombre). Cf. OWASP « CSV Injection »."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v

# --------------------------------------------------------------------------- #
# Qui appelle (AUTH-2) — lecture des en-têtes d'identité
# --------------------------------------------------------------------------- #

def _auteur(request: Request) -> Optional[str]:
    """Login de la personne connectée — délégué à `autorisation.auteur` (AUTH-2).

    La lecture des en-têtes d'identité a migré dans `autorisation.py` : la portée
    d'autorisation en dépend, et deux implémentations de « qui est là » finiraient par
    diverger. Le nom local reste, il a des appelants dans tout le fichier.
    """
    return autorisation.auteur(request)


def _groupes(request: Request) -> list[str]:
    """Groupes de la personne connectée — délégué à `autorisation.groupes` (AUTH-2)."""
    return autorisation.groupes(request)


# Miroir des identités déjà écrites : évite une écriture SQLite à CHAQUE requête, ce qui
# sérialiserait tout le trafic derrière l'unique verrou d'écriture du WAL.
#
# On réécrit dans DEUX cas : le nom ou l'email a changé (Authelia fait foi), ou la
# dernière écriture date de plus d'une heure. Ce second cas n'est pas du zèle : sans lui,
# `derniere_vue` ne bougerait qu'au changement de nom, et la colonne mentirait sur ce
# qu'elle prétend mesurer. Une écriture par personne et par heure reste négligeable.


# --------------------------------------------------------------------------- #
# Modèles Pydantic — le CONTRAT d'entrée de l'API (ARCH-1)
# --------------------------------------------------------------------------- #
# Ici plutôt que dans chaque domaine, et c'est une décision : `LexiqueIn` sert à deux
# blocs, `AttributIn` à un bloc sorti et un bloc resté. Les répartir exactement
# demanderait une carte d'usage pour 27 déclarations sans logique, et se tromperait
# sans bruit. Ce sont des contrats, pas de la mécanique de domaine.

class AlbumIn(BaseModel):
    # AUTH-2 : collection d'accueil. N'est PAS une colonne d'`albums` —
    # l'appartenance vit dans `collection_album` (N-N) et le champ est
    # retiré avant l'INSERT. Omis => collection de repli.
    collection_id: Optional[int] = None
    titre: str
    auteur: Optional[str] = None                # legacy → voir contributions
    annee: Optional[int] = None                 # legacy → précisé par date_edition
    editeur: Optional[str] = None
    serie: Optional[str] = None
    description: Optional[str] = None
    # Enrichissement descriptif N0 (v15) — édition détenue.
    date_edition: Optional[str] = None
    date_originale: Optional[str] = None
    langue: Optional[str] = None
    type_oeuvre: Optional[str] = None
    lieu_edition: Optional[str] = None
    edition_tirage: Optional[str] = None
    isbn: Optional[str] = None
    format_physique: Optional[str] = None
    source_numerisation: Optional[str] = None   # matériel N1 (A6) : appareil / conditions de scan


class AlbumUpdate(BaseModel):
    titre: Optional[str] = None
    auteur: Optional[str] = None
    annee: Optional[int] = None
    editeur: Optional[str] = None
    serie: Optional[str] = None
    description: Optional[str] = None
    date_edition: Optional[str] = None
    date_originale: Optional[str] = None
    langue: Optional[str] = None
    type_oeuvre: Optional[str] = None
    lieu_edition: Optional[str] = None
    edition_tirage: Optional[str] = None
    isbn: Optional[str] = None
    format_physique: Optional[str] = None
    source_numerisation: Optional[str] = None   # matériel N1 (A6)


class ContributionIn(BaseModel):
    nom: str
    role: Optional[str] = None                  # label du rôle (contrôlé-ouvert : créé au besoin)


class ContributionRoleIn(BaseModel):            # ≠ `RoleIn` (rôle de planche, plus bas)
    label: str
    bucket: Optional[str] = None                # 'creator' | 'contributor' (défaut : contributor)
    marc: Optional[str] = None


class RegionIn(BaseModel):
    type: str
    x: int = Field(0, ge=0)
    y: int = Field(0, ge=0)
    w: int = Field(0, ge=0)
    h: int = Field(0, ge=0)
    parent_id: Optional[int] = None
    ordre: Optional[int] = None
    ocr_texte: Optional[str] = None
    source: str = "manuel"


class RegionUpdate(BaseModel):
    type: Optional[str] = None
    x: Optional[int] = Field(None, ge=0)
    y: Optional[int] = Field(None, ge=0)
    w: Optional[int] = Field(None, ge=0)
    h: Optional[int] = Field(None, ge=0)
    parent_id: Optional[int] = None
    ordre: Optional[int] = None
    ocr_texte: Optional[str] = None
    source: Optional[str] = None


class StatutIn(BaseModel):
    statut: str


class ValidationIn(BaseModel):
    validee: bool


class VerrouIn(BaseModel):
    verrouillee: bool


class RoleIn(BaseModel):
    role: str


class RelectureIn(BaseModel):
    relecture: Optional[str] = None      # 'a_faire'|'en_cours'|'faite' ; null = auto (dérivé)


class TokenCorrectionIn(BaseModel):
    lemme: Optional[str] = None
    pos: Optional[str] = None
    morph: Optional[str] = None
    etat: str = "corrige"          # 'corrige' | 'valide'


class MoveIn(BaseModel):
    sens: str   # "haut" | "bas"


class SharedocsConnIn(BaseModel):
    url: str
    user: str
    password: Optional[str] = None   # vide => repli sur BD_SHAREDOCS_PASS
    # SHARE-1 — 'instance' remplace le compte de l'instance (administrateurs seuls) ;
    # sinon on ouvre SA propre session.
    compte: Optional[str] = None


class SharedocsImportIn(BaseModel):
    chemins: list[str] = Field(default_factory=list)
    album_id: Optional[int] = None
    nouvel_album: Optional[str] = None
    segmenter: bool = False
    compte: Optional[str] = None            # SHARE-1 : 'perso' | 'instance' | None (auto)


class DeposerIn(BaseModel):
    dossier: str = ""   # dossier ShareDocs cible (vide = racine)
    # SHARE-1 — le compte se CHOISIT à chaque dépôt (décision du 2026-08-28). Une
    # sauvegarde déposée sous un compte personnel atterrit dans un espace qui s'en va
    # avec la personne ; mais l'imposer priverait d'un dépôt de dépannage. None = la
    # règle par défaut (la mienne si j'en ai une, celle de l'instance sinon).
    compte: Optional[str] = None


class JobIn(BaseModel):
    passes: list[str] = Field(default_factory=list)        # segmenter / bulles / ocr
    album_ids: list[int] = Field(default_factory=list)
    planche_ids: list[int] = Field(default_factory=list)


class AnnotationIn(BaseModel):
    note: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class TagIn(BaseModel):
    label: str
    couleur: Optional[str] = None
    description: Optional[str] = None


class PersonnageIn(BaseModel):
    nom: str
    serie: Optional[str] = None
    notes: Optional[str] = None


class PersonnageUpdate(BaseModel):
    nom: Optional[str] = None
    serie: Optional[str] = None
    notes: Optional[str] = None


class LocuteurIn(BaseModel):
    personnage_id: int


class PresenceIn(BaseModel):
    personnage_id: int   # entité montrée dans une boîte personnage (§14, brique (a))


class FusionIn(BaseModel):
    cible_id: int   # personnage canonique dans lequel fusionner le doublon


class AlignementIn(BaseModel):
    """Alignement d'autorité (A5) : URI d'un référentiel externe (skos:exactMatch)."""
    uri: str
    source: Optional[str] = None   # 'wikidata'|'viaf'|'idref'… ; auto-détecté si absent


class DomaineIn(BaseModel):
    """Domaine analytique (piste B) — champ émergent qui regroupe des dimensions."""
    nom: str


class FigureIn(BaseModel):
    """Demande d'export de figure(s) citable(s) — DROIT-1.

    `champs` choisit les MENTIONS qui composeront la légende : une légende d'article, une
    légende de diapositive et une notice de catalogue n'ont pas les mêmes besoins, et
    imposer un gabarit obligerait à le retailler à la main, donc hors de l'outil, donc en
    perdant le lien entre l'image et sa référence. Défaut = tout, faute d'en savoir plus.

    `collection_id` dit AU NOM DE QUELLE ÉTUDE on cite : un album vit dans plusieurs
    collections depuis AUTH-3, et le corpus crédité n'est pas déductible.
    """
    regions: list[int]
    champs: Optional[list[str]] = None
    collection_id: Optional[int] = None
    taille: int = 1600


class CollectionIn(BaseModel):
    """Création d'une collection (AUTH-3). Volontairement minimale : un espace de travail
    s'ouvre avec un nom, et les descripteurs de DÉPÔT (licence, base légale, embargo…) se
    remplissent ensuite, quand la collection sert vraiment à quelque chose."""
    nom: str
    description: Optional[str] = None


class CollectionUpdate(BaseModel):
    """Édition partielle des descripteurs. Champ omis = inchangé."""
    nom: Optional[str] = None
    description: Optional[str] = None
    licence_defaut: Optional[str] = None
    base_legale: Optional[str] = None
    statut_diffusion: Optional[str] = None
    date_embargo: Optional[str] = None
    date_debut: Optional[str] = None
    date_fin: Optional[str] = None
    # AUTH-4 — le référent d'EXPLOITATION, désigné par le propriétaire. Distinct de
    # `responsables`, qui est scientifique et part au dépôt.
    referent_nom: Optional[str] = None
    referent_contact: Optional[str] = None


class AccesIn(BaseModel):
    """Un accès accordé : QUI (genre + principal) et à quel NIVEAU.

    `principal` est un nom, pas une référence vérifiée — l'application n'a aucun annuaire
    (invariant AUTH-1) et lit les groupes dans `Remote-Groups` à chaque requête."""
    genre: str = autorisation.UTILISATEUR      # 'utilisateur' | 'groupe'
    principal: str
    niveau: str = autorisation.LECTURE         # 'lecture' | 'ecriture' | 'proprietaire'


class DimensionDomaineIn(BaseModel):
    domaine_id: Optional[int] = None   # null = retirer la dimension de son domaine


class DimensionIn(BaseModel):
    cible: str      # 'personnage' | 'case'
    nom: str
    domaine_id: Optional[int] = None   # champ analytique de rattachement (v20 ; optionnel)


class ValeurIn(BaseModel):
    valeur: str


class LexiqueIn(BaseModel):
    """Couche définitionnelle SKOS (A4) — mise à jour PARTIELLE (patch). Champ omis = laissé
    tel quel ; `collection_id: null` explicite = promotion en GLOBAL (patron mentions→entités)."""
    definition: Optional[str] = None      # SKOS definition (→ tags.description)
    note_portee: Optional[str] = None     # SKOS scopeNote — le « situé »
    etat: Optional[str] = None            # 'provisoire' | 'defini'
    collection_id: Optional[int] = None   # portée d'appartenance ; null = global


class AttributIn(BaseModel):
    valeur_id: int
