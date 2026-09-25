"""Amorçage en lot du VOCABULAIRE analytique (piste B) — cœur partagé.

Logique de parsing + upsert d'un tableur CSV (domaines → dimensions → valeurs + couche
lexique SKOS A4), commune à l'outil headless `tools/importer_vocabulaire.py` et à la route
`POST /api/lexique/importer` (bouton « Importer » du panneau 📖 Lexique). Aucune I/O propre :
on reçoit un FLUX de texte (fichier ou tampon décodé) et une CONNEXION — l'appelant gère
l'ouverture du fichier et la transaction.

Doctrine « pré-remplir, jamais écraser » (comme l'OCR, `pipeline/ocr.py`, `only_empty=True`) :
un terme déjà présent est RÉUTILISÉ (idempotent) ; sa `definition` / `note_portee` n'est
renseignée QUE si elle est encore vide, et le rattachement d'une dimension à son domaine
(`domaine_id`) suit la même règle — posé à la création, ou sur une dimension existante qui
n'en avait pas. L'état (`provisoire`→`defini`) et sa validation restent des actes humains
dans l'app. Cf. docs/import-vocabulaire.md.

La PORTÉE (`collection_id`) suit ce que font les routes unitaires (AUTH-11, mesuré
combinaison par combinaison le 2026-09-24, deux points tranchés par Hugo le même jour) :
- un terme NEUF importé SANS collection hérite de son parent, comme
  `POST /api/attributs/dimensions` et `POST …/valeurs` — il naissait global sous un parent
  local, ce que v24 interdit ;
- un terme NEUF importé DANS la collection C y naît, sous un parent global ou de C ; sous un
  parent local à une AUTRE collection, la ligne est REFUSÉE (`parent_ailleurs`) — elle y
  naissait, hors de la collection de son parent ;
- RATTACHER une dimension existante à un domaine ne déplace JAMAIS sa portée, pas plus que
  `PATCH /api/attributs/dimensions/{id}/domaine` : permis sous un domaine global ou de la
  même collection, REFUSÉ (`parent_ailleurs`) sous un domaine local à une autre collection
  — dimension globale comprise, qui serait plus globale que son domaine ;
- un terme existant ne change de portée par aucune voie : réimporter dans une collection ne
  déplace pas un terme déjà là (décision d'appartenance = humaine, geste `PATCH …/lexique`).

Réutiliser un terme existant PEUT être une écriture sur lui (sa glose vide se remplit, un
enfant naît sous lui) : la portée de l'appelant est donc un paramètre OBLIGATOIRE
d'`importer` (AUTH-11), comme celle de `socle._ensure_tags` — cf. `_refus`.
"""
from __future__ import annotations

import csv
import sqlite3

CIBLES = ("personnage", "case")
COLONNES = ("domaine", "domaine_definition", "cible", "dimension", "dimension_definition",
            "dimension_note_portee", "valeur", "valeur_definition")


class FormatInvalide(ValueError):
    """En-tête inexploitable (colonnes obligatoires absentes) : erreur de FORMAT, pas de
    données. L'outil la transforme en message CLI, la route en HTTP 400."""


def _norm(nom) -> str:
    """Nom canonique, IDENTIQUE à l'app (`main._norm_tag`) : minuscule, espaces compactés.
    Garantit que l'import et la création émergente convergent sur la même forme."""
    return " ".join((nom or "").strip().lower().split())


def _txt(v):
    """Cellule de texte libre → contenu nettoyé, ou None si vide (une définition vide veut
    dire « non fournie », pas « effacer »)."""
    v = (v or "").strip()
    return v or None


# --------------------------------------------------------------------------- #
# Lecture / validation
# --------------------------------------------------------------------------- #
def lire(flux) -> tuple[list[dict], list[str]]:
    """Analyse un flux de texte CSV (point-virgule) → (lignes valides, anomalies). Une ligne
    invalide (dimension vide, cible inconnue) est ÉCARTÉE et signalée ; une ligne entièrement
    vide est ignorée en silence. Lecture par nom de colonne (ordre libre, colonnes en trop
    tolérées). Lève `FormatInvalide` si une colonne obligatoire manque."""
    lignes, anomalies = [], []
    lecteur = csv.DictReader(flux, delimiter=";")
    entete = lecteur.fieldnames or []
    manquantes = [c for c in ("cible", "dimension") if c not in entete]
    if manquantes:
        raise FormatInvalide(
            f"En-tête invalide : colonnes obligatoires manquantes {manquantes}. "
            f"Attendu (point-virgule) : {';'.join(COLONNES)}")
    for i, brut in enumerate(lecteur, start=2):          # ligne 1 = en-tête
        domaine, cible = _norm(brut.get("domaine")), _norm(brut.get("cible"))
        dimension, valeur = _norm(brut.get("dimension")), _norm(brut.get("valeur"))
        if not (domaine or dimension or valeur):
            continue                                     # ligne blanche → ignorée
        if not dimension:
            anomalies.append(f"L.{i} : dimension vide — ligne ignorée")
            continue
        if cible not in CIBLES:
            anomalies.append(
                f"L.{i} : cible « {(brut.get('cible') or '').strip()} » invalide "
                f"(attendu : {' | '.join(CIBLES)}) — ligne ignorée")
            continue
        lignes.append({
            "no": i, "domaine": domaine, "cible": cible, "dimension": dimension,
            "valeur": valeur,
            "domaine_def": _txt(brut.get("domaine_definition")),
            "dimension_def": _txt(brut.get("dimension_definition")),
            "dimension_note": _txt(brut.get("dimension_note_portee")),
            "valeur_def": _txt(brut.get("valeur_definition"))})
    return lignes, anomalies


# --------------------------------------------------------------------------- #
# Écriture (upsert « pré-remplir sans écraser »)
# --------------------------------------------------------------------------- #
def _a_poser(row, fill: dict) -> dict:
    """Les colonnes de `fill` qu'un upsert écrirait sur la ligne existante `row` : fournies,
    et encore vides en base. UNE seule définition, lue par `_upsert` pour écrire et par
    `_refus` pour savoir si une ligne écrirait — deux copies finiraient par diverger, et la
    garde jugerait une écriture que l'upsert ne fait pas (ou l'inverse)."""
    return {k: v for k, v in fill.items()
            if v is not None and (row[k] is None or str(row[k]).strip() == "")}


def _upsert(conn, table, cle: dict, creation: dict, fill: dict) -> tuple[int, bool]:
    """Upsert idempotent d'un terme. `cle` = clé naturelle (WHERE + posée à la création) ;
    `creation` = colonnes fixées SEULEMENT à la création (portée) ; `fill` = colonnes
    définitionnelles remplies uniquement si ENCORE vides (jamais d'écrasement) — le
    `domaine_id` d'une dimension compris : rattacher n'écrit rien d'autre. Renvoie
    (id, cree). Ne commit pas : l'appelant gère la transaction."""
    where = " AND ".join(f"{k} = ?" for k in cle)
    row = conn.execute(f"SELECT * FROM {table} WHERE {where}", tuple(cle.values())).fetchone()
    if row is None:
        cols = {**cle, **creation, **fill}
        cur = conn.execute(f"INSERT INTO {table} ({','.join(cols)}) "
                           f"VALUES ({','.join('?' * len(cols))})", tuple(cols.values()))
        return cur.lastrowid, True          # id = INTEGER PRIMARY KEY → lastrowid fiable
    a_poser = _a_poser(row, fill)
    if a_poser:
        conn.execute(f"UPDATE {table} SET {', '.join(f'{k} = ?' for k in a_poser)} "
                     f"WHERE id = ?", (*a_poser.values(), row["id"]))
    return row["id"], False


def _portee_de(conn, table, oid):
    """La portée (`collection_id`) d'un terme existant, lue en base."""
    return conn.execute(f"SELECT collection_id FROM {table} WHERE id = ?",
                        (oid,)).fetchone()["collection_id"]


def _portee_a_la_creation(collection_id, portee_parent):
    """La portée d'un terme NEUF, alignée sur les routes (AUTH-11, 2026-09-24).

    Les routes de création font hériter l'enfant de son parent (`POST
    /api/attributs/dimensions` du domaine, `POST …/valeurs` de la dimension) ; les racines
    naissent globales. Importer DANS une collection, c'est donc créer puis ranger —
    `PATCH …/lexique {collection_id}` — et importer SANS collection, créer sans ranger :

    - sans collection → la portée du parent (None sous un parent global ou sans parent).
      L'import faisait naître l'enfant GLOBAL sous un parent local — un état que les routes
      ne produisent jamais (promouvoir cet enfant répond 409) et que v24 interdit ;
    - avec la collection C → C. Sous un parent global ou de C, c'est ce que donnent la
      création suivie du rangement (un terme plus local que son parent est légitime, A4).
      Sous un parent local à une AUTRE collection, `_refus` a déjà écarté la ligne
      (`parent_ailleurs`, tranché par Hugo le 2026-09-24) : les routes ne tranchaient pas
      ce cas, et y naître dans C laissait un terme qu'on ne pouvait ni lire en entier ni
      promouvoir depuis C."""
    return collection_id if collection_id is not None else portee_parent


def _existant(conn, portee, table, cle: dict):
    """Le terme de cette clé naturelle, s'il existe : sa ligne entière (`row`, pour savoir
    ce qu'un upsert y écrirait) et deux verdicts, `visible` (`portee.clause_terme` — la
    règle reste écrite dans `autorisation.py`) et `modifiable` (`portee.peut_ecrire_terme`).
    None s'il n'existe pas. La clé est EXACTEMENT celle que `_upsert` cherche et que
    l'unicité du schéma compare — la forme normalisée par `_norm` : une clé cherchée
    autrement laisserait passer le terme."""
    ou, params = portee.clause_terme("t.collection_id")
    where = " AND ".join(f"t.{k} = ?" for k in cle)
    row = conn.execute(f"SELECT t.*, {ou} AS visible FROM {table} t WHERE {where}",
                       (*params, *cle.values())).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "row": row, "visible": bool(row["visible"]),
            "modifiable": portee.peut_ecrire_terme(row["collection_id"])}


def _refus(conn, portee, r, collection_id):
    """Pourquoi cette ligne ne s'applique pas — (motif, quoi) —, ou None si elle s'applique.

    AUTH-11 (2026-09-24). La clé naturelle d'un terme est unique dans TOUTE l'instance
    (`domaine.nom`, `attribut_dimension(cible, nom)`, `attribut_valeur(dimension_id,
    valeur)`), et `_upsert` la cherchait sans portée : un import remplissait la note de
    portée vide d'une dimension locale à une collection qu'on ne lit pas, créait une valeur
    sous elle, et le résumé (`existant: 1`) disait qu'elle existait. La ligne est jugée
    ENTIÈRE, avant toute écriture, sur les termes qu'elle nomme, en trois passes dans cet
    ordre — chacune ne commence qu'une fois la précédente finie sur toute la ligne, de
    sorte qu'un terme caché l'emporte toujours sur un terme en lecture seule, quel que soit
    leur palier, et l'un comme l'autre sur un parent rangé ailleurs (passe 3, plus bas) :

    1. Un terme nommé INVISIBLE — domaine, dimension, ou valeur sous une dimension qu'on
       peut modifier — refuse la ligne, motif `libelle_pris`. Cela couvre le PARENT caché
       (une dimension qui naîtrait sous un domaine caché, une valeur sous une dimension
       cachée), puisque la ligne nomme ce parent. Le motif est celui d'un libellé pris,
       rien de plus : ni la collection, ni la définition, ni que le terme est « caché ». Il
       confirme qu'un libellé est pris, où qu'il vive — un bit par libellé, le même oracle
       que celui déjà accepté pour `socle._ensure_tags` et `POST /api/tags`, LIMITE écrite
       que l'unicité par collection fermera avec `COL-1`.
    2. Une ligne qui ÉCRIRAIT sur un terme visible mais NON MODIFIABLE (`peut_ecrire_terme`)
       est refusée, motif `lecture_seule` — le dire ne révèle rien, le terme étant visible.
       Écrire, c'est ce que ferait `_upsert` : remplir un champ encore vide (`_a_poser`,
       la même fonction), ou poser un enfant sous le terme — une dimension neuve sous un
       domaine, une dimension existante rattachée au domaine qu'elle n'avait pas, une
       valeur sous une dimension.

    **VOIR n'est pas CHANGER** : une ligne qui ne fait que NOMMER un terme visible en
    lecture seule, sans rien lui écrire, passe et le compte en `existant` — comme
    `POST /api/attributs/dimensions` rend en 201 une dimension qu'on lit. Sans quoi le
    réimport idempotent d'un fichier qui nomme des termes seulement lus échouerait ligne
    par ligne.

    Les valeurs suivent la route unitaire `POST …/valeurs`, qui répond 403 sur une dimension
    en lecture seule SANS regarder ses valeurs : une valeur n'est donc cherchée que sous
    une dimension visible ET modifiable. Nommer une valeur sous une dimension en lecture
    seule est refusé `lecture_seule`, qu'elle existe ou non, cachée ou non — la chercher
    rendrait le bit que l'API refuse (« existe cachée » contre « n'existe pas »).

    3. Une ligne qui rangerait un terme HORS DE LA COLLECTION DE SON PARENT est refusée,
       motif `parent_ailleurs` (tranché par Hugo le 2026-09-24) — le parent est alors
       visible et modifiable, les deux passes d'avant ayant parlé sinon, et le dire ne
       révèle rien. Deux formes :
       - importée DANS la collection C, une dimension NEUVE sous un domaine local à une
         autre collection, ou une valeur NEUVE sous une dimension locale à une autre
         collection (un parent global, ou de C, passe) ;
       - le RATTACHEMENT d'une dimension orpheline à un domaine local à une autre
         collection que la sienne — dimension GLOBALE comprise, qui serait plus globale que
         son domaine (v24). `PATCH …/domaine` répond 409 aux mêmes cas : un rattachement
         ne déplace plus de portée, ni là ni ici.
       Un domaine qui NAÎT dans la ligne naît dans la collection de l'import (ou global) :
       c'est sa portée qui est jugée.

    Les écritures de `importer`, confrontées une à une (2026-09-24, après le renversement
    du rattachement) : créer un domaine ; remplir sa définition (`_a_poser`) ; créer une
    dimension — sous un domaine, écriture sur lui (passe 2), dans la collection de
    l'import ou celle du domaine (`_portee_a_la_creation`), hors de la collection du
    domaine jamais (passe 3) ; remplir `domaine_id`, définition ou note d'une dimension
    (`_a_poser`, passe 2 ; le rattachement, passe 3 aussi) ; créer une valeur — écriture
    sur sa dimension (passe 2), hors de sa collection jamais (passe 3) ; remplir la
    définition d'une valeur (`_a_poser`). Rattacher n'écrit plus que le `domaine_id` : la
    portée de la dimension et celle de ses valeurs ne bougent plus, et aucune garde ne
    les prévoit, faute d'écriture.

    Sous une portée TOTALE (l'outil en ligne de commande, le mono-poste), tout est visible
    et modifiable : les deux premières passes ne refusent rien, la troisième s'applique —
    elle ne protège pas un lecteur, elle garde l'invariant de portée."""
    dom = None
    if r["domaine"]:
        dom = _existant(conn, portee, "domaine", {"nom": r["domaine"]})
    dim = _existant(conn, portee, "attribut_dimension",
                    {"cible": r["cible"], "nom": r["dimension"]})
    val = None
    if r["valeur"] and dim is not None and dim["visible"] and dim["modifiable"]:
        val = _existant(conn, portee, "attribut_valeur",
                        {"dimension_id": dim["id"], "valeur": r["valeur"]})

    quoi_dom = f"domaine « {r['domaine']} »"
    quoi_dim = f"dimension « {r['cible']}/{r['dimension']} »"
    quoi_val = f"valeur « {r['dimension']}/{r['valeur']} »"
    for quoi, t in ((quoi_dom, dom), (quoi_dim, dim), (quoi_val, val)):
        if t is not None and not t["visible"]:
            return "libelle_pris", quoi

    # Ce que la ligne écrirait sur chaque terme existant — miroir de `importer`.
    ecrit = []
    if dom is not None:
        ecrit.append((quoi_dom, dom, bool(
            _a_poser(dom["row"], {"definition": r["domaine_def"]})
            or dim is None                                  # une dimension naîtrait dessous
            or dim["row"]["domaine_id"] is None)))          # la dimension s'y rattacherait
    if dim is not None:
        ecrit.append((quoi_dim, dim, bool(
            _a_poser(dim["row"], {"domaine_id": dom["id"] if dom else (r["domaine"] or None),
                                  "definition": r["dimension_def"],
                                  "note_portee": r["dimension_note"]})
            or r["valeur"])))                               # une valeur, nommée dessous
    if val is not None:
        ecrit.append((quoi_val, val, bool(_a_poser(val["row"],
                                                    {"definition": r["valeur_def"]}))))
    for quoi, t, ecrirait in ecrit:
        if ecrirait and not t["modifiable"]:
            return "lecture_seule", quoi

    # 3. Hors de la collection de son parent — miroir de `_portee_a_la_creation` et de la
    # route `PATCH …/domaine`. Un domaine neuf naît dans la collection de l'import ; une
    # dimension neuve aussi, et sa valeur neuve l'y suit : seule une dimension EXISTANTE
    # peut être le parent « ailleurs » d'une valeur.
    portee_dom = (dom["row"]["collection_id"] if dom is not None
                  else (collection_id if r["domaine"] else None))
    if dim is None:
        if collection_id is not None and portee_dom not in (None, collection_id):
            return "parent_ailleurs", quoi_dim              # dimension neuve
        return None
    portee_dim = dim["row"]["collection_id"]      # sans domaine nommé, `portee_dom` est None
    if dim["row"]["domaine_id"] is None and portee_dom not in (None, portee_dim):
        return "parent_ailleurs", quoi_dim                  # rattachement
    if (r["valeur"] and val is None and collection_id is not None
            and portee_dim not in (None, collection_id)):
        return "parent_ailleurs", quoi_val                  # valeur neuve
    return None


MOTIFS = {"libelle_pris": "libellé déjà pris",
          "lecture_seule": "en lecture seule pour vous",
          "parent_ailleurs": "hors de la collection de son parent"}


def _divergence(memo, cle, champ, valeur, avert, quoi):
    """Signale (sans bloquer) deux valeurs DIFFÉRENTES pour un même champ définitionnel dans
    le fichier — faute de saisie typique. La première rencontrée fait foi (cohérent avec le
    « ne jamais écraser » côté base)."""
    if valeur is None:
        return
    ancienne = memo.get((cle, champ))
    if ancienne is None:
        memo[(cle, champ)] = valeur
    elif ancienne != valeur:
        avert.append(f"{quoi} : deux « {champ} » divergentes (« {ancienne} » ≠ "
                     f"« {valeur} ») — la première est retenue")


def importer(conn, lignes, collection_id, *, portee) -> tuple[dict, list[str]]:
    """Applique les lignes déjà validées. Renvoie (résumé, avertissements). Chaque palier
    est compté UNE fois (à sa première rencontre), en distinguant créés / déjà présents.

    `portee` (une `autorisation.Portee`) est OBLIGATOIRE et sans défaut, comme pour
    `socle._ensure_tags` : un défaut qui sauterait le contrôle rendrait l'oubli invisible.
    L'outil en ligne de commande passe `autorisation.TOTALE`. Une ligne refusée par
    `_refus` n'écrit rien et n'est comptée dans aucun palier : elle s'ajoute à
    `refusees[motif]` (par LIGNE) et à un avertissement qui nomme le libellé fourni et le
    motif, jamais le terme en base. « Existant caché » n'a pas de compteur à lui : il se
    confond avec « libellé pris », et c'est le but."""
    res = {k: {"cree": 0, "existant": 0} for k in ("domaines", "dimensions", "valeurs")}
    res["refusees"] = {motif: 0 for motif in MOTIFS}
    avert, memo, vus = [], {}, set()

    def _compter(palier, cle, cree):
        if cle not in vus:
            vus.add(cle)
            res[palier]["cree" if cree else "existant"] += 1

    for r in lignes:
        refus = _refus(conn, portee, r, collection_id)
        if refus is not None:
            motif, quoi = refus
            res["refusees"][motif] += 1
            avert.append(f"L.{r['no']} : {quoi} — {MOTIFS[motif]}, ligne ignorée")
            continue
        domaine_id, portee_domaine = None, None
        if r["domaine"]:
            _divergence(memo, ("dom", r["domaine"]), "domaine_definition",
                        r["domaine_def"], avert, f"domaine « {r['domaine']} »")
            domaine_id, cree = _upsert(
                conn, "domaine", {"nom": r["domaine"]},
                {"collection_id": collection_id}, {"definition": r["domaine_def"]})
            _compter("domaines", ("dom", r["domaine"]), cree)
            portee_domaine = _portee_de(conn, "domaine", domaine_id)

        cle_dim = ("dim", r["cible"], r["dimension"])
        _divergence(memo, cle_dim, "dimension_definition", r["dimension_def"], avert,
                    f"dimension « {r['cible']}/{r['dimension']} »")
        _divergence(memo, cle_dim, "note_portee", r["dimension_note"], avert,
                    f"dimension « {r['cible']}/{r['dimension']} »")
        if r["domaine"]:
            _divergence(memo, cle_dim, "domaine", r["domaine"], avert,
                        f"dimension « {r['cible']}/{r['dimension']} »")
        dim_id, cree = _upsert(
            conn, "attribut_dimension", {"cible": r["cible"], "nom": r["dimension"]},
            {"collection_id": _portee_a_la_creation(collection_id, portee_domaine)},
            {"domaine_id": domaine_id, "definition": r["dimension_def"],
             "note_portee": r["dimension_note"]})
        _compter("dimensions", cle_dim, cree)

        if r["valeur"]:
            cle_val = ("val", dim_id, r["valeur"])
            _divergence(memo, cle_val, "valeur_definition", r["valeur_def"], avert,
                        f"valeur « {r['dimension']}/{r['valeur']} »")
            _, cree = _upsert(
                conn, "attribut_valeur", {"dimension_id": dim_id, "valeur": r["valeur"]},
                {"collection_id": _portee_a_la_creation(
                    collection_id, _portee_de(conn, "attribut_dimension", dim_id))},
                {"definition": r["valeur_def"]})
            _compter("valeurs", cle_val, cree)
    return res, avert
