"""Figure citable — l'extrait accompagné de ce qui le rend citable.  DROIT-1.

Ce module ne restreint rien. Il fait l'inverse : il rend POSSIBLE l'usage savant d'un
corpus qu'on ne peut pas diffuser.

**La distinction que porte DROIT-1 est CITER contre PUBLIER**, et elle passe par la nature
de l'acte, pas par un volume. *Publier*, c'est mettre un corpus à disposition — un
manifeste IIIF servi à des visionneuses, un paquet de dépôt : ces gestes portent sur une
collection entière, et n'emportent d'images que si elle est déclarée `public`. *Citer*,
c'est extraire une case identifiée pour l'accompagner d'un discours — un article, une
communication. Ce second geste n'est jamais bloqué par le régime de diffusion : c'est
l'usage même que la recherche revendique, et un fonds sous droits est justement celui
qu'on cite plutôt que de le diffuser.

Ce qui rend une citation défendable, c'est qu'elle soit COURTE, IDENTIFIÉE et ACCOMPAGNÉE.
L'outil produit donc les trois d'un seul geste, plutôt qu'une image nue qu'il faudrait
recréditer à la main — parce que c'est à la main que l'accompagnement se perd.

**Les mentions sont CHOISIES par la personne qui cite** (arbitrage du 2026-08-28). Une
légende d'article, une légende de diapositive et une notice de catalogue n'ont pas les
mêmes besoins, et imposer un gabarit obligerait à le retailler à la main — donc à sortir
de l'outil, donc à perdre le lien entre l'image et sa référence. `CHAMPS` énumère ce qui
est offert ; l'appelant prend ce qu'il veut, dans cet ordre.

Un champ demandé mais vide en base ne produit RIEN plutôt qu'un blanc : une légende ne
doit pas annoncer « éditeur : » suivi du vide. Le seul champ qui s'affiche même absent est
`base_legale` — « non établie » est une information, et c'est aujourd'hui la vérité du
dépôt (cf. DEPOT-1). La taire ferait passer pour réglé ce qui ne l'est pas.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from database import citations_regions, contributions_album

# Mentions offertes, DANS L'ORDRE où elles composent la légende. L'ordre est celui d'une
# référence bibliographique usuelle : l'œuvre, puis sa responsabilité, puis son édition,
# puis le repère interne, puis le cadre juridique.
CHAMPS = (
    "titre",            # titre de l'album (+ série si elle existe)
    "auteur",           # contributions N0 si présentes, sinon `albums.auteur` (legacy)
    "editeur",
    "annee",            # date_edition si renseignée, sinon `annee` (legacy)
    "isbn",
    "citation",         # repère interne dérivé : « pl. 3 · c2 · b1 »
    "collection",       # nom du corpus d'étude d'où vient l'extrait
    "licence",          # licence du jeu ENRICHI (jamais celle de l'œuvre)
    "base_legale",      # à quel titre le corpus est détenu — « non établie » si vide
    "mention_citation",  # la formule de courte citation
    "date_export",
)

MENTION_CITATION = "Reproduction au titre de la courte citation, à fin d'illustration " \
                   "d'un propos scientifique."

BASE_LEGALE_ABSENTE = "base légale non établie (cf. DEPOT-1)"


def _album_de_region(conn: sqlite3.Connection, region_id: int) -> Optional[dict]:
    r = conn.execute(
        "SELECT a.* FROM regions r "
        "JOIN planches p ON p.id = r.planche_id "
        "JOIN albums a   ON a.id = p.album_id "
        "WHERE r.id = ?", (region_id,)).fetchone()
    return dict(r) if r else None


def _collection_de_region(conn: sqlite3.Connection, region_id: int,
                          collection_id: Optional[int] = None,
                          lisibles: Optional[set] = None) -> Optional[dict]:
    """La collection à créditer. `collection_id` la désigne explicitement (un album vit
    dans PLUSIEURS collections depuis AUTH-3, et c'est à la personne qui cite de dire au
    nom de quelle étude elle le fait). À défaut, la plus ancienne de celles qu'on LIT.

    `lisibles` borne le choix aux collections visibles (None = aucune restriction, pour le
    mono-poste et l'administrateur). Sans cette borne — écart trouvé en relisant, sur une
    suite verte — la légende créditait la plus ancienne des collections de l'album, y
    compris une étude qu'on n'a pas le droit de voir : elle en exportait alors le nom, la
    licence et la base légale, dans un artefact qui QUITTE l'instance. C'est la fuite « par
    la bande » qu'AUTH-2 avait déjà trouvée sur les attributs d'un objet partagé.
    """
    sql = ("SELECT c.* FROM regions r "
           "JOIN planches p        ON p.id = r.planche_id "
           "JOIN collection_album ca ON ca.album_id = p.album_id "
           "JOIN collection c      ON c.id = ca.collection_id "
           "WHERE r.id = ? ")
    params: list = [region_id]
    if collection_id is not None:
        sql += "AND c.id = ? "
        params.append(collection_id)
    elif lisibles is not None:
        if not lisibles:
            return None
        sql += f"AND c.id IN ({', '.join('?' * len(lisibles))}) "
        params.extend(sorted(lisibles))
    sql += "ORDER BY c.id LIMIT 1"
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def _auteur(conn: sqlite3.Connection, album: dict) -> Optional[str]:
    """Responsabilité de l'album : les contributions N0 (nom + rôle, modèle Zotero-like)
    si elles existent, sinon la chaîne `auteur` legacy. On ne mélange pas les deux — une
    légende qui répéterait le même nom sous deux formes se lit comme une erreur."""
    contribs = contributions_album(conn, album["id"])
    if contribs:
        return ", ".join(
            f"{c['nom']} ({c['role']})" if c.get("role") else c["nom"] for c in contribs)
    return album.get("auteur") or None


def legende(conn: sqlite3.Connection, region_id: int, champs=CHAMPS, *,
            collection_id: Optional[int] = None,
            lisibles: Optional[set] = None) -> dict:
    """Les mentions demandées, résolues, dans l'ordre de `CHAMPS`.

    Renvoie un dict ORDONNÉ ne contenant que les champs demandés ET renseignés (sauf
    `base_legale`, cf. l'en-tête du module). Lève `LookupError` si la région n'existe pas.

    `lisibles` : les collections que l'appelant a le droit de lire (None = aucune
    restriction). Ce module reçoit un ensemble d'ids plutôt qu'une `Portee` pour ne pas
    dépendre de `autorisation` — la règle reste écrite là-bas, comme pour `lexique_resume`.
    """
    album = _album_de_region(conn, region_id)
    if album is None:
        raise LookupError(f"Région {region_id} introuvable")
    demandes = [c for c in CHAMPS if c in set(champs)]     # l'ordre reste celui de CHAMPS
    coll = (_collection_de_region(conn, region_id, collection_id, lisibles)
            if {"collection", "licence", "base_legale"} & set(demandes) else None)
    cit = citations_regions(conn, [region_id]).get(region_id) if "citation" in demandes else None

    brut = {
        "titre": " — ".join(x for x in (album.get("serie"), album["titre"]) if x),
        "auteur": _auteur(conn, album) if "auteur" in demandes else None,
        "editeur": album.get("editeur"),
        "annee": album.get("date_edition") or (
            str(album["annee"]) if album.get("annee") else None),
        "isbn": album.get("isbn"),
        "citation": (cit or {}).get("texte"),
        "collection": (coll or {}).get("nom"),
        "licence": (coll or {}).get("licence_defaut"),
        # Seul champ qui parle même absent : « non établie » est une information.
        "base_legale": (coll or {}).get("base_legale") or BASE_LEGALE_ABSENTE,
        "mention_citation": MENTION_CITATION,
        "date_export": date.today().isoformat(),
    }
    return {c: brut[c] for c in demandes if brut[c]}


# Étiquettes de la ligne rendue. Le titre, l'auteur et l'année se composent sans étiquette
# (c'est la forme d'une référence bibliographique) ; le reste s'annonce.
#
# « Consulté le » et non « Version du » : le corpus n'est PAS versionné (le gel versionné
# reste un dormant), et « version » promettrait qu'on peut redemander celle-là. C'est la
# convention bibliographique pour une ressource mouvante — et le corpus l'est, puisque
# l'enrichissement se poursuit après l'extraction ; le scan, lui, ne bouge pas.
_ETIQUETTES = {
    "isbn": "ISBN", "citation": None, "collection": "Corpus",
    "licence": "Licence du jeu enrichi", "base_legale": "Base légale",
    "mention_citation": None, "date_export": "Consulté le",
}


def texte(leg: dict) -> str:
    """La légende rendue, prête à coller sous une figure.

    Deux blocs séparés par un tiret cadratin : la RÉFÉRENCE de l'œuvre (forme
    bibliographique, sans étiquettes), puis le CADRE (corpus, droits, date), chacun
    annoncé. Un lecteur doit pouvoir distinguer d'un coup d'œil ce qui décrit l'œuvre citée
    de ce qui décrit les conditions de sa reproduction.
    """
    ref = [leg[c] for c in ("titre", "auteur", "editeur", "annee") if c in leg]
    cadre = []
    for c in ("isbn", "citation", "collection", "licence", "base_legale",
              "mention_citation", "date_export"):
        if c not in leg:
            continue
        etiq = _ETIQUETTES.get(c)
        cadre.append(f"{etiq} : {leg[c]}" if etiq else str(leg[c]))
    morceaux = [", ".join(ref)] if ref else []
    morceaux += cadre
    return " — ".join(m for m in morceaux if m)
