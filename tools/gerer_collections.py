"""Gestion des COLLECTIONS (palier supérieur — unité de dépôt).

Outil HEADLESS d'écriture : crée / édite des collections et y range des albums
(appartenance N-N STATIQUE, figeable → citable). Une collection décrit un JEU DE
DONNÉES (une sélection constituée pour une étude) et sert d'unité de dépôt
(1 collection = 1 dépôt Nakala/HAL = 1 DOI). Les descripteurs DÉCRIVENT le régime de
droits ; ils ne l'imposent pas — l'accès reste géré par l'auth / l'entrepôt
(cf. docs/dictionnaire-metadonnees.md, palier « Collection »).

Les exports (`metadonnees_collection.py`, `description_collection.py`,
`iiif_manifest.py`) acceptent `--collection <id>` pour restreindre leur périmètre à une
collection ; sans elle, ils portent sur le corpus entier.

Sous-commandes :
    lister                            liste les collections
    montrer   ID                      détaille une collection + ses albums
    creer     --nom … [options]       crée une collection (imprime son id sur stdout)
    modifier  ID [options]            modifie les descripteurs
    ajouter   ID --albums 1,2,3       range des albums dans la collection
    retirer   ID --albums 1,2         retire des albums (n'efface pas les albums)
    supprimer ID                      supprime la collection (pas les albums)

AUTH-3 — depuis l'écran Collections de la Bibliothèque, cet outil n'est plus le SEUL moyen
d'écrire : c'était son défaut, il exigeait un accès shell pour ouvrir un espace de travail.
Il reste utile pour l'amorçage et les descripteurs de dépôt (licence, embargo, responsables),
que l'écran ne couvre pas.

Une collection créée ici naît SANS PROPRIÉTAIRE — donc administrable par les seuls
`bd-admins`. C'est cohérent (il n'y a pas d'identité dans un shell), mais rarement ce qu'on
veut : `--proprietaire LOGIN` (ou `--proprietaire-groupe NOM`) l'inscrit d'emblée, et évite
d'avoir à ouvrir la base pour rendre la collection utilisable par quelqu'un.

La base suit la config du projet (BD_DB_PATH / BD_DATA_DIR).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402

# Importé de config : la route d'édition (AUTH-3) valide la MÊME liste. Deux chemins
# d'écriture sur un champ contrôlé ne peuvent pas avoir chacun la sienne.
from config import STATUTS_DIFFUSION as STATUTS  # noqa: E402
# Descripteurs éditables (colonne SQL ← attribut argparse). `responsables` est traité à
# part (liste JSON). `nom` est requis à la création, éditable ensuite.
_CHAMPS = {"nom": "nom", "description": "description", "licence": "licence_defaut",
           "statut": "statut_diffusion", "date_embargo": "date_embargo",
           "base_legale": "base_legale", "date_debut": "date_debut", "date_fin": "date_fin"}


def _err(msg):
    print(msg, file=sys.stderr)


def _checkpoint():
    """Rabat le WAL dans la base principale → un lecteur RO séparé (les exports) voit
    immédiatement l'écriture. Même précaution que la fixture de test."""
    conn = database.get_connection()
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _parse_responsables(valeurs):
    """`--responsable "Nom;rôle;orcid"` (répétable) → liste de dicts. Champs vides omis."""
    out = []
    for v in valeurs or []:
        parts = [p.strip() for p in v.split(";")]
        nom = parts[0] if parts else ""
        d = {"nom": nom}
        if len(parts) > 1 and parts[1]:
            d["role"] = parts[1]
        if len(parts) > 2 and parts[2]:
            d["orcid"] = parts[2]
        if nom:
            out.append(d)
    return out


def _descripteurs(args) -> dict:
    """Colonnes descriptives fournies sur la ligne de commande (attribut non-None →
    à écrire). Valide `statut`. `responsables` géré séparément par l'appelant."""
    maj = {}
    for opt, col in _CHAMPS.items():
        val = getattr(args, opt, None)
        if val is not None:
            maj[col] = val
    if maj.get("statut_diffusion") and maj["statut_diffusion"] not in STATUTS:
        raise SystemExit(f"statut inconnu : {maj['statut_diffusion']} "
                         f"(attendus : {', '.join(STATUTS)})")
    return maj


def _albums_ids(arg) -> list[int]:
    """« 1,2,3 » → [1, 2, 3] (ignore les vides). Erreur CLAIRE sur un jeton non entier."""
    if not arg:
        return []
    out = []
    for x in arg.replace(" ", "").split(","):
        if not x:
            continue
        try:
            out.append(int(x))
        except ValueError:
            raise SystemExit(f"--albums : « {x} » n'est pas un identifiant d'album "
                             "(entiers séparés par des virgules attendus, ex. 1,2,3).")
    return out


def _lire_responsables(brut) -> list:
    """JSON `responsables` (en base) → liste de dicts ; [] si absent/illisible (parité avec
    les exports, qui protègent aussi ce décodage)."""
    if not brut:
        return []
    try:
        val = json.loads(brut)
        return val if isinstance(val, list) else []
    except (ValueError, TypeError):
        return []


def _albums_existants(conn, ids) -> list[int]:
    """Filtre les ids d'albums réellement présents (avertit sur les absents)."""
    if not ids:
        return []
    qm = ",".join("?" * len(ids))
    ok = {r[0] for r in conn.execute(
        f"SELECT id FROM albums WHERE id IN ({qm})", ids)}
    for i in ids:
        if i not in ok:
            _err(f"  ⚠ album {i} introuvable — ignoré")
    return [i for i in ids if i in ok]


def _ranger(conn, collection_id, album_ids):
    """Ajoute des albums à une collection (INSERT OR IGNORE), `rang` en fin de liste.
    Renvoie le nombre effectivement ajoutés."""
    depart = conn.execute(
        "SELECT COALESCE(MAX(rang), 0) FROM collection_album WHERE collection_id = ?",
        (collection_id,)).fetchone()[0]
    n = 0
    for i, aid in enumerate(album_ids, start=1):
        cur = conn.execute(
            "INSERT OR IGNORE INTO collection_album (collection_id, album_id, rang) "
            "VALUES (?, ?, ?)", (collection_id, aid, depart + i))
        n += cur.rowcount
    return n


# --------------------------------------------------------------------------- #
# Sous-commandes
# --------------------------------------------------------------------------- #
def cmd_lister(args) -> int:
    with database.connect() as conn:
        cols = database.collections(conn)
    if not cols:
        _err("Aucune collection. Créez-en une : gerer_collections.py creer --nom \"…\"")
        return 0
    for c in cols:
        statut = c["statut_diffusion"] or "—"
        print(f"{c['id']:>4}  {c['nom']}  ({c['nb_albums']} album(s), {statut})")
    return 0


def cmd_montrer(args) -> int:
    with database.connect() as conn:
        row = database.collection_row(conn, args.id)
        if row is None:
            raise SystemExit(f"Collection {args.id} introuvable.")
        ids = database.collection_album_ids(conn, args.id)
        albums = {r["id"]: r["titre"] for r in conn.execute("SELECT id, titre FROM albums")}
    resp = _lire_responsables(row["responsables"])
    print(f"Collection {row['id']} — {row['nom']}")
    if row["description"]:
        print(f"  description      : {row['description']}")
    print(f"  licence défaut   : {row['licence_defaut'] or '—'}")
    print(f"  statut diffusion : {row['statut_diffusion'] or '—'}"
          + (f" (levée {row['date_embargo']})" if row["date_embargo"] else ""))
    print(f"  base légale      : {row['base_legale'] or '— (à établir)'}")
    print(f"  responsables     : "
          + ("; ".join(r.get("nom", "") for r in resp) if resp else "—"))
    print(f"  période          : {row['date_debut'] or '—'} → {row['date_fin'] or '—'}")
    print(f"  albums ({len(ids)}) : "
          + (", ".join(f"{i}·{albums.get(i, '?')}" for i in ids) if ids else "—"))
    return 0


def _refuser_nom_reserve(nom) -> None:
    """Même garde que la route (AUTH-3) : `collection_par_defaut` désigne le repli par son
    NOM, et se l'attribuer capture les albums créés sans collection explicite. Un outil
    d'opérateur n'a pas plus de raison qu'une UI de casser cet invariant en silence."""
    if nom and database.nom_reserve(nom):
        raise SystemExit(f"« {nom} » est réservé à la collection de repli "
                         "(albums créés sans collection explicite).")


def cmd_creer(args) -> int:
    _refuser_nom_reserve(args.nom)
    maj = _descripteurs(args)
    maj["nom"] = args.nom
    maj["responsables"] = json.dumps(_parse_responsables(args.responsable),
                                     ensure_ascii=False) if args.responsable else None
    cols = list(maj.keys())
    vals = [maj[k] for k in cols]
    qm = ",".join("?" * len(cols))
    with database.connect() as conn:
        cur = conn.execute(
            f"INSERT INTO collection ({','.join(cols)}) VALUES ({qm})", vals)
        cid = cur.lastrowid
        n = 0
        if args.albums:
            n = _ranger(conn, cid, _albums_existants(conn, _albums_ids(args.albums)))
        # AUTH-3 — sans propriétaire, la collection n'est administrable que par un
        # administrateur. C'est un état valable (un shell n'a pas d'identité) mais rarement
        # voulu : le poser ici évite d'ouvrir la base pour rendre la collection utilisable.
        proprio = args.proprietaire or args.proprietaire_groupe
        if proprio:
            conn.execute(
                "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
                "VALUES (?, ?, ?, 'proprietaire')",
                (cid, "groupe" if args.proprietaire_groupe else "utilisateur", proprio))
    _checkpoint()
    _err(f"Collection créée : {cid} — « {args.nom} » ({n} album(s))"
         + (f", propriétaire : {proprio}" if proprio else
            " — SANS propriétaire (administrable par bd-admins seulement)"))
    print(cid)                      # stdout = l'id seul (scriptable)
    return 0


def cmd_modifier(args) -> int:
    _refuser_nom_reserve(getattr(args, "nom", None))
    maj = _descripteurs(args)
    if args.responsable is not None:      # --responsable fourni (même vide) → remplace
        maj["responsables"] = json.dumps(_parse_responsables(args.responsable),
                                         ensure_ascii=False) if args.responsable else None
    if not maj:
        raise SystemExit("Rien à modifier (aucun descripteur fourni).")
    with database.connect() as conn:
        if database.collection_row(conn, args.id) is None:
            raise SystemExit(f"Collection {args.id} introuvable.")
        set_sql = ", ".join(f"{k} = ?" for k in maj)
        conn.execute(f"UPDATE collection SET {set_sql} WHERE id = ?",
                     [*maj.values(), args.id])
    _checkpoint()
    _err(f"Collection {args.id} modifiée ({', '.join(maj)}).")
    return 0


def cmd_ajouter(args) -> int:
    with database.connect() as conn:
        if database.collection_row(conn, args.id) is None:
            raise SystemExit(f"Collection {args.id} introuvable.")
        ids = _albums_existants(conn, _albums_ids(args.albums))
        n = _ranger(conn, args.id, ids)
    _checkpoint()
    _err(f"{n} album(s) ajouté(s) à la collection {args.id}.")
    return 0


def cmd_retirer(args) -> int:
    ids = _albums_ids(args.albums)
    with database.connect() as conn:
        if database.collection_row(conn, args.id) is None:
            raise SystemExit(f"Collection {args.id} introuvable.")
        n = 0
        if ids:
            qm = ",".join("?" * len(ids))
            cur = conn.execute(
                f"DELETE FROM collection_album WHERE collection_id = ? "
                f"AND album_id IN ({qm})", [args.id, *ids])
            n = cur.rowcount
    _checkpoint()
    _err(f"{n} album(s) retiré(s) de la collection {args.id}.")
    return 0


def cmd_supprimer(args) -> int:
    with database.connect() as conn:
        if database.collection_row(conn, args.id) is None:
            raise SystemExit(f"Collection {args.id} introuvable.")
        conn.execute("DELETE FROM collection WHERE id = ?", (args.id,))
    _checkpoint()
    _err(f"Collection {args.id} supprimée (les albums sont conservés).")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _ajouter_descripteurs(sp):
    """Options descriptives partagées par `creer` et `modifier`."""
    sp.add_argument("--description", help="objet / périmètre / critères de sélection")
    sp.add_argument("--licence", help="licence du jeu enrichi (ex. CC-BY-4.0)")
    sp.add_argument("--statut", help=f"régime d'accès ({' | '.join(STATUTS)})")
    sp.add_argument("--date-embargo", dest="date_embargo", help="levée d'embargo (AAAA-MM-JJ)")
    sp.add_argument("--base-legale", dest="base_legale",
                    help="base légale d'accès aux données (à établir, hors code)")
    sp.add_argument("--responsable", action="append",
                    help="« Nom;rôle;orcid » (répétable ; role/orcid facultatifs)")
    sp.add_argument("--date-debut", dest="date_debut", help="début de constitution/couverture")
    sp.add_argument("--date-fin", dest="date_fin", help="fin de constitution/couverture")


def main(argv=None) -> int:
    from _commun import forcer_utf8
    forcer_utf8()                             # Windows : stdout/stderr en UTF-8 (cp1252 sinon)
    ap = argparse.ArgumentParser(
        description="Gestion des collections (palier supérieur / unité de dépôt).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("lister", help="liste les collections").set_defaults(func=cmd_lister)

    p = sub.add_parser("montrer", help="détaille une collection")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_montrer)

    p = sub.add_parser("creer", help="crée une collection")
    p.add_argument("--nom", required=True)
    p.add_argument("--albums", help="albums à ranger d'emblée (« 1,2,3 »)")
    p.add_argument("--proprietaire", metavar="LOGIN",
                   help="login qui POSSÈDE la collection (accorde/retire les accès)")
    p.add_argument("--proprietaire-groupe", dest="proprietaire_groupe", metavar="NOM",
                   help="idem, mais un groupe Remote-Groups (un labo, pas une personne)")
    _ajouter_descripteurs(p)
    p.set_defaults(func=cmd_creer)

    p = sub.add_parser("modifier", help="modifie les descripteurs d'une collection")
    p.add_argument("id", type=int)
    p.add_argument("--nom")
    _ajouter_descripteurs(p)
    p.set_defaults(func=cmd_modifier)

    p = sub.add_parser("ajouter", help="range des albums dans une collection")
    p.add_argument("id", type=int)
    p.add_argument("--albums", required=True, help="« 1,2,3 »")
    p.set_defaults(func=cmd_ajouter)

    p = sub.add_parser("retirer", help="retire des albums d'une collection")
    p.add_argument("id", type=int)
    p.add_argument("--albums", required=True, help="« 1,2,3 »")
    p.set_defaults(func=cmd_retirer)

    p = sub.add_parser("supprimer", help="supprime une collection (pas les albums)")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_supprimer)

    args = ap.parse_args(argv)
    database.init_db()             # garantit le schéma v14 (idempotent)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
