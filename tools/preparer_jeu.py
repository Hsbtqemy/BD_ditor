r"""Prépare le JEU des bacs à sable (COL-4) : les documents dont chaque bac à sable prend une
copie à sa naissance, et leur copie de RÉFÉRENCE dans le projet de jeu, caché.

Le jeu se DÉCRIT, il ne se fabrique pas à la main : une description déclarative (`jeu.json`)
et ses images, dans DEUX sources, parce que ses planches n'ont pas le même statut (Hugo,
2026-10-22, « un peu des trois ») :

- la part du DÉPÔT (`jeu/` à la racine du dépôt, ou `--depot DOSSIER`) : des planches du
  domaine public ou sous licence libre, versionnées avec le code. Leur export est PERMIS
  dans un bac à sable, sauf si la description dit `"exportable": false` ;
- la part du SERVEUR (`--serveur DOSSIER`, ou la variable `BD_JEU_SERVEUR`) : des scans sous
  droits, posés à la main sur le serveur, JAMAIS dans le dépôt. Leur export est FERMÉ dans
  un bac à sable, document par document — la description ne peut pas l'ouvrir.

Une part dont la source n'est pas donnée, ou n'a pas de `jeu.json`, est IGNORÉE : ses
documents déjà préparés restent tels quels. Sans cela, lancer l'outil sur une instance qui
n'a pas la part du serveur (la recette) retirerait du jeu tout ce qui en vient.

`jeu.json` : `{"documents": [ … ]}`, chaque document :
    cle        identifiant STABLE (unique dans les deux sources) — c'est par lui qu'un
               document se reconnaît d'un passage à l'autre
    titre      requis ; `serie`, `auteur` facultatifs (la notice)
    role       `pas-a-pas` (le parcours où l'on suit toutes les étapes), `exemple`, `stock`
    rang       l'ordre dans son rôle (0 par défaut)
    cran       jusqu'où chaque bac à sable recopie le travail de la référence : `images`
               (vierge, par défaut), `decoupage`, `transcription`, `grammaire`. Pas au-delà
               dans le lot 2 : au cran `annotations`, les personnages du jeu deviendraient
               communs à tous les bacs à sable (S4 du cadrage)
    exportable faux pour fermer l'export d'un document de la part du dépôt
    planches   une liste, chacune `{"fichier": "p1.png", "regions": [ … ]}` — le fichier
               relatif au dossier de la source ; une région : `type`, `x`, `y`, `w`, `h`
               (pixels du SCAN), `ordre`, `texte`, `enfants` (des régions dans celle-ci),
               `corrections` (`[{"ordre", "forme", "lemme", "pos", "morph"}]`, la couche
               grammaticale de son texte)

Le travail du jeu n'est à PERSONNE : aucun événement par région, des corrections sans
auteur. La naissance de chaque référence s'écrit sous son document (cible `document`,
retenue de toute sortie), sans agent — un shell n'a pas d'identité. Les images passent par
l'import ordinaire (`pipeline.ingest`) : la copie de travail d'IMG-1 s'applique d'elle-même,
et `master_origine` note `jeu:<fichier>`.

Changer le jeu = changer la description et relancer. Un document dont la description ou une
image a changé (son EMPREINTE) est un document NEUF : l'outil le crée, et retire l'ancien
du jeu ; un document absent de la description en est retiré. Une référence retirée reste
tant qu'un bac à sable en tient une copie — ses images aussi, par référence —, et part avec
la dernière : ici même si aucune ne la tient plus, sinon au prochain effacement
(`tools/effacer_bacs_a_sable.py`). Les bacs à sable existants gardent l'ancien document
jusqu'à leur remise à neuf.

Par défaut l'outil ne fait que DIRE ce qu'il ferait, base ouverte en LECTURE SEULE et sans
`database.init_db()` ; une base qui n'est pas à la version du code est refusée. Avec
`--appliquer`, sous un verrou propre à l'outil (`preparer_jeu.verrou` à la racine des
données, créé en exclusif) et le verrou d'écriture de la base, document par document.

Usage :
    python tools/preparer_jeu.py                          # à blanc
    python tools/preparer_jeu.py --appliquer
    python tools/preparer_jeu.py --serveur /srv/jeu --appliquer

En production, dans le conteneur, depuis `~/BD_ditor/deploy` :
    docker compose exec app python tools/preparer_jeu.py --serveur /donnees/jeu --appliquer
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _commun import forcer_utf8                                   # noqa: E402
import autorisation                                               # noqa: E402
import conflit                                                    # noqa: E402
import database                                                   # noqa: E402
import journal                                                    # noqa: E402
from config import BASE_DIR, IMG_EXTS, TYPES_REGION              # noqa: E402
from pipeline import ingest                                       # noqa: E402

DOSSIER_DEPOT = BASE_DIR / "jeu"
VARIABLE_SERVEUR = "BD_JEU_SERVEUR"
NOM_DESCRIPTION = "jeu.json"
NOM_DU_VERROU = "preparer_jeu.verrou"
# Les crans qu'un document du jeu peut porter : pas au-delà de la grammaire (cf. l'en-tête).
CRANS_DU_JEU = database.CRANS[:database.CRANS.index(database.CRAN_GRAMMAIRE) + 1]


class DescriptionInvalide(ValueError):
    """La description d'une source ne se lit pas : rien n'est écrit."""


class PassageEnCours(RuntimeError):
    """Un autre passage `--appliquer` tient le verrou de l'outil."""


# --------------------------------------------------------------------------- #
# Lire et valider une description
# --------------------------------------------------------------------------- #
def _region_valide(r, ou: str) -> None:
    if not isinstance(r, dict):
        raise DescriptionInvalide(f"{ou} : une région est un objet.")
    if r.get("type") not in TYPES_REGION:
        raise DescriptionInvalide(f"{ou} : type de région inconnu {r.get('type')!r} "
                                  f"({' | '.join(TYPES_REGION)}).")
    for k in ("x", "y", "w", "h"):
        if not isinstance(r.get(k), int) or r[k] < 0:
            raise DescriptionInvalide(f"{ou} : `{k}` doit être un entier positif (pixels du "
                                      "scan).")
    if r.get("texte") is not None and not isinstance(r["texte"], str):
        raise DescriptionInvalide(f"{ou} : `texte` est une chaîne.")
    for c in r.get("corrections") or ():
        if not (isinstance(c, dict) and isinstance(c.get("ordre"), int)
                and isinstance(c.get("forme"), str) and c["forme"]):
            raise DescriptionInvalide(f"{ou} : une correction porte `ordre` (entier) et "
                                      "`forme` (le mot visé).")
    for i, e in enumerate(r.get("enfants") or ()):
        _region_valide(e, f"{ou}, enfant {i + 1}")


def lire_description(dossier, part: str) -> list[dict]:
    """Les documents décrits dans `dossier/jeu.json`, validés, chacun avec sa `part`, son
    `dossier` et son EMPREINTE (la description et les octets de ses images). Lève
    `DescriptionInvalide` sur la première faute, avant toute écriture."""
    dossier = Path(dossier)
    chemin = dossier / NOM_DESCRIPTION
    try:
        racine = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DescriptionInvalide(f"{chemin} ne se lit pas : {exc}") from None
    docs = racine.get("documents") if isinstance(racine, dict) else None
    if not isinstance(docs, list):
        raise DescriptionInvalide(f"{chemin} : `documents` doit être une liste.")
    sortie = []
    for i, d in enumerate(docs):
        ou = f"{chemin}, document {i + 1}"
        if not isinstance(d, dict):
            raise DescriptionInvalide(f"{ou} : un document est un objet.")
        cle = d.get("cle")
        if not isinstance(cle, str) or not cle.strip():
            raise DescriptionInvalide(f"{ou} : `cle` est requise (un identifiant stable).")
        ou = f"{chemin}, « {cle} »"
        if not isinstance(d.get("titre"), str) or not d["titre"].strip():
            raise DescriptionInvalide(f"{ou} : `titre` est requis.")
        if d.get("role") not in database.ROLES_JEU:
            raise DescriptionInvalide(f"{ou} : rôle inconnu {d.get('role')!r} "
                                      f"({' | '.join(database.ROLES_JEU)}).")
        cran = d.get("cran", database.CRAN_IMAGES)
        if cran not in CRANS_DU_JEU:
            raise DescriptionInvalide(f"{ou} : cran {cran!r} hors du jeu "
                                      f"({' | '.join(CRANS_DU_JEU)}) — au-delà de la "
                                      "grammaire, les personnages deviendraient communs à "
                                      "tous les bacs à sable.")
        if not isinstance(d.get("rang", 0), int):
            raise DescriptionInvalide(f"{ou} : `rang` est un entier.")
        planches = d.get("planches")
        if not isinstance(planches, list) or not planches:
            raise DescriptionInvalide(f"{ou} : au moins une planche.")
        h = hashlib.sha256(json.dumps({**d, "_part": part}, sort_keys=True,
                                      ensure_ascii=False).encode("utf-8"))
        for j, pl in enumerate(planches):
            o2 = f"{ou}, planche {j + 1}"
            fichier = pl.get("fichier") if isinstance(pl, dict) else None
            if not isinstance(fichier, str) or not fichier:
                raise DescriptionInvalide(f"{o2} : `fichier` est requis.")
            rel = Path(fichier)
            if rel.is_absolute() or ".." in rel.parts:
                raise DescriptionInvalide(f"{o2} : `fichier` est relatif au dossier de la "
                                          "source, sans « .. ».")
            if rel.suffix.lower() not in IMG_EXTS:
                raise DescriptionInvalide(f"{o2} : extension {rel.suffix!r} non gérée.")
            image = dossier / rel
            if not image.is_file():
                raise DescriptionInvalide(f"{o2} : image introuvable ({image}).")
            h.update(image.read_bytes())
            for k, r in enumerate(pl.get("regions") or ()):
                _region_valide(r, f"{o2}, région {k + 1}")
        exportable = part == database.PART_DEPOT and d.get("exportable", True) is not False
        sortie.append({**d, "cle": cle.strip(), "cran": cran, "rang": d.get("rang", 0),
                       "part": part, "dossier": dossier, "exportable": exportable,
                       "empreinte": h.hexdigest()})
    return sortie


def _source(dossier) -> Path | None:
    """Le dossier d'une part s'il porte une description, None sinon (la part est ignorée)."""
    if dossier is None:
        return None
    dossier = Path(dossier)
    return dossier if (dossier / NOM_DESCRIPTION).is_file() else None


# --------------------------------------------------------------------------- #
# Le plan : ce qui se crée, se garde, se retire
# --------------------------------------------------------------------------- #
def planifier(conn, sources: dict) -> dict:
    """`sources` : `{part: dossier ou None}`. Rend `{"creer", "garder", "retirer",
    "ignorees"}` — des documents décrits (créer), des clés (garder), des lignes de
    `jeu_document` (retirer) — sans rien écrire. Une clé décrite dans deux parts est une
    faute : `DescriptionInvalide`."""
    decrits, ignorees = [], []
    for part in database.PARTS_JEU:
        dossier = _source(sources.get(part))
        if dossier is None:
            ignorees.append(part)
            continue
        decrits += lire_description(dossier, part)
    vues = {}
    for d in decrits:
        if d["cle"] in vues:
            raise DescriptionInvalide(f"La clé « {d['cle']} » est décrite deux fois "
                                      f"({vues[d['cle']]} et {d['part']}).")
        vues[d["cle"]] = d["part"]
    existants = {r["cle"]: dict(r) for r in conn.execute(
        "SELECT document_id, album_reference, cle, empreinte, part FROM jeu_document")}
    plan = {"creer": [], "garder": [], "retirer": [], "ignorees": ignorees}
    for d in decrits:
        e = existants.get(d["cle"])
        if e is not None and e["empreinte"] == d["empreinte"] and e["part"] == d["part"]:
            plan["garder"].append(d["cle"])
        else:
            plan["creer"].append(d)
            if e is not None:
                plan["retirer"].append(e)
    for cle, e in existants.items():
        if cle not in vues and e["part"] not in ignorees:
            plan["retirer"].append(e)
    return plan


# --------------------------------------------------------------------------- #
# Appliquer
# --------------------------------------------------------------------------- #
def _poser_les_regions(conn, planche_id: int, regions, parent=None) -> list[int]:
    """Les régions décrites, et leurs enfants, sous `parent` ; rend celles qui portent un
    texte, à indexer. Aucun événement : le travail du jeu n'est à personne."""
    a_indexer = []
    for i, r in enumerate(regions or ()):
        rid = conn.execute(
            "INSERT INTO regions (planche_id, parent_id, type, x, y, w, h, ordre, ocr_texte, "
            "source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'jeu')",
            (planche_id, parent, r["type"], r["x"], r["y"], r["w"], r["h"],
             r.get("ordre", i + 1), r.get("texte"))).lastrowid
        for c in r.get("corrections") or ():
            conn.execute(
                "INSERT INTO token_correction (region_id, ordre, forme, lemme, pos, morph, "
                "etat, auteur) VALUES (?, ?, ?, ?, ?, ?, 'corrige', NULL)",
                (rid, c["ordre"], c["forme"], c.get("lemme"), c.get("pos"), c.get("morph")))
        if r.get("texte"):
            a_indexer.append(rid)
        a_indexer += _poser_les_regions(conn, planche_id, r.get("enfants"), rid)
    return a_indexer


def _creer_une_reference(conn, d: dict) -> tuple[int, int]:
    """La copie de référence d'un document décrit, dans la collection du jeu ; rend
    `(document_id, album_id)`. Commite à chaque planche : l'ingest ne décode pas sous une
    transaction ouverte."""
    projet = database.creer_projet_de_jeu(conn)
    collection = database.collection_de_base(conn, projet)
    conflit.verrouiller(conn)
    album_id = conn.execute("INSERT INTO albums (titre, serie, auteur) VALUES (?, ?, ?)",
                            (d["titre"].strip(), d.get("serie"), d.get("auteur"))).lastrowid
    ingest.ecarter_dossiers_d_album(album_id)
    conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                 (collection, album_id))
    document_id = database.creer_document(conn, album_id, importe_par=None, projet_id=projet)
    journal.journaliser(conn, "creation", "document", document_id,
                        apres={"album_id": album_id, "titre": d["titre"].strip(),
                               "jeu": {"cle": d["cle"], "part": d["part"]}})
    journal.journaliser_emploi(conn, "lien", album_id, collection)
    conn.commit()
    for pl in d["planches"]:
        planche = ingest.ingest_image(conn, album_id, d["dossier"] / pl["fichier"],
                                      origine=f"jeu:{Path(pl['fichier']).name}")
        a_indexer = _poser_les_regions(conn, planche["id"], pl.get("regions"))
        if pl.get("regions"):
            database.avancer_statut(conn, planche["id"], "segmentee")
        for rid in a_indexer:
            database.reindex_region(conn, rid)
        conn.commit()
    return document_id, album_id


def purger_les_references(conn) -> list[int]:
    """Détruit les copies de référence que plus rien n'appelle : un album du projet de jeu
    dont le document n'est plus dans `jeu_document`, et dont AUCUNE autre copie ne vit —
    aucun bac à sable n'en tient. Ses images partent par référence
    (`socle._detruire_album`), et son document avec lui. Rend les albums détruits. Lu aussi
    par `tools/effacer_bacs_a_sable.py`, après l'effacement."""
    import socle                                  # le seul chemin de la destruction
    projet = database.projet_de_jeu(conn)
    if projet is None:
        return []
    candidats = [r[0] for r in conn.execute(
        f"SELECT a.id FROM albums a WHERE {database.sql_projet_d_album('a')} = ? "
        "AND (a.document_id IS NULL OR a.document_id NOT IN "
        "     (SELECT document_id FROM jeu_document)) "
        "AND NOT EXISTS (SELECT 1 FROM albums b WHERE b.document_id = a.document_id "
        "                AND b.id <> a.id) ORDER BY a.id", (projet,))]
    for album_id in candidats:
        socle._detruire_album(conn, autorisation.TOTALE, album_id, reference_du_jeu=True)
    return candidats


def appliquer(conn, plan: dict, *, dire=print) -> dict:
    """Applique un plan. Les retraits d'abord (la ligne de `jeu_document` seulement), puis
    les créations, puis la purge des références que plus rien n'appelle."""
    for e in plan["retirer"]:
        conflit.verrouiller(conn)
        conn.execute("DELETE FROM jeu_document WHERE document_id = ?", (e["document_id"],))
        conn.commit()
        dire(f"  − retiré du jeu : « {e['cle']} » (document {e['document_id']})")
    crees = []
    for d in plan["creer"]:
        document_id, album_id = _creer_une_reference(conn, d)
        conflit.verrouiller(conn)
        conn.execute(
            "INSERT INTO jeu_document (document_id, album_reference, cran, role, rang, cle, "
            "empreinte, part, exportable) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (document_id, album_id, d["cran"], d["role"], d["rang"], d["cle"],
             d["empreinte"], d["part"], int(d["exportable"])))
        conn.commit()
        crees.append(document_id)
        dire(f"  + au jeu : « {d['cle']} » ({d['part']}, {d['role']}, cran {d['cran']}) — "
             f"document {document_id}, référence {album_id}")
    purges = purger_les_references(conn)
    for a in purges:
        dire(f"  × référence {a} détruite : plus aucun bac à sable n'en tient de copie")
    return {"crees": crees, "retires": [e["document_id"] for e in plan["retirer"]],
            "gardes": plan["garder"], "purges": purges, "ignorees": plan["ignorees"]}


@contextmanager
def _verrou_de_l_outil():
    chemin = Path(ingest.DATA_DIR) / NOM_DU_VERROU
    try:
        fd = os.open(chemin, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise PassageEnCours(
            f"Un autre passage --appliquer tient le verrou {chemin}. S'il ne tourne plus — "
            "arrêté brutalement —, effacez ce fichier, puis relancez.") from None
    try:
        os.write(fd, f"pid {os.getpid()}, depuis {time.strftime('%Y-%m-%d %H:%M:%S')}"
                 .encode("utf-8"))
    finally:
        os.close(fd)
    try:
        yield
    finally:
        chemin.unlink(missing_ok=True)


def preparer(conn, *, depot=None, serveur=None, appliquer_: bool = False,
             dire=print) -> dict:
    """Le cœur, pour la ligne de commande et les tests : planifie, et avec `appliquer_`
    applique sous le verrou de l'outil. À blanc, rend le plan seul."""
    plan = planifier(conn, {database.PART_DEPOT: depot, database.PART_SERVEUR: serveur})
    for part in plan["ignorees"]:
        dire(f"  · part « {part} » ignorée : aucune description ({NOM_DESCRIPTION}) ; ses "
             "documents déjà préparés restent tels quels.")
    if not appliquer_:
        for d in plan["creer"]:
            dire(f"  + créerait « {d['cle']} » ({d['part']}, {d['role']}, cran {d['cran']})")
        for e in plan["retirer"]:
            dire(f"  − retirerait « {e['cle']} » (document {e['document_id']})")
        return {"plan": plan}
    with _verrou_de_l_outil():
        return {"plan": plan, **appliquer(conn, plan, dire=dire)}


def _ouvrir_la_base(appliquer_: bool):
    """La base, SANS `database.init_db()` ; à blanc, en LECTURE SEULE. Une base qui n'est pas
    à la version du code est refusée : c'est l'application qui migre."""
    if not Path(database.DB_PATH).is_file():
        raise SystemExit(f"Base introuvable : {database.DB_PATH}")
    lecture = sqlite3.connect(Path(database.DB_PATH).resolve().as_uri() + "?mode=ro",
                              uri=True)
    version = lecture.execute("PRAGMA user_version").fetchone()[0]
    if version != database.SCHEMA_VERSION:
        lecture.close()
        raise SystemExit(f"Base au schéma v{version}, ce code attend la "
                         f"v{database.SCHEMA_VERSION} : démarrez l'application une fois.")
    if not appliquer_:
        lecture.row_factory = sqlite3.Row
        return lecture
    lecture.close()
    return database.get_connection()


def main(argv=None) -> int:
    forcer_utf8()
    ap = argparse.ArgumentParser(
        description="Prépare le jeu des bacs à sable (COL-4) depuis ses descriptions. À "
                    "blanc par défaut.")
    ap.add_argument("--appliquer", action="store_true", help="écrit pour de bon")
    ap.add_argument("--depot", default=str(DOSSIER_DEPOT),
                    help="dossier de la part du dépôt (défaut : jeu/ à la racine du dépôt)")
    ap.add_argument("--serveur", default=os.environ.get(VARIABLE_SERVEUR) or None,
                    help=f"dossier de la part du serveur (défaut : ${VARIABLE_SERVEUR})")
    args = ap.parse_args(argv)
    try:
        conn = _ouvrir_la_base(args.appliquer)
    except SystemExit as exc:
        print(f"✗ {exc}")
        return 2
    try:
        bilan = preparer(conn, depot=args.depot, serveur=args.serveur,
                         appliquer_=args.appliquer,
                         dire=lambda ligne: print(ligne, flush=True))
    except (DescriptionInvalide, PassageEnCours) as exc:
        print(f"✗ {exc}")
        return 2
    finally:
        conn.close()
    plan = bilan["plan"]
    if args.appliquer:
        print(f"✓ {len(bilan['crees'])} document(s) créé(s), {len(bilan['retires'])} "
              f"retiré(s), {len(bilan['gardes'])} inchangé(s), {len(bilan['purges'])} "
              "référence(s) détruite(s).")
    else:
        print(f"À blanc : {len(plan['creer'])} document(s) à créer, {len(plan['retirer'])} "
              f"à retirer, {len(plan['garder'])} inchangé(s). Rien n'a été écrit — relancez "
              "avec --appliquer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
