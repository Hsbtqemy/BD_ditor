r"""Fabrique une VRAIE base d'une version passée, avec le code de cette version lui-même.

Pourquoi. Une migration se vérifie sur une base de la version PRÉCÉDENTE qui a vécu, pas sur
une base neuve qu'on aurait ramenée en arrière à la main (règle posée par Hugo le
2026-10-16, après la v30 de COL-3) : les bases « défaites » des tests n'avaient ni
destructions, ni journal, ni dossiers d'images, et c'est là que la v30 s'est trompée trois
fois. Cet outil extrait le code d'un commit (`git archive`, dans un dossier temporaire), le
fait tourner — ses routes, derrière le proxy, sous trois comptes —, puis vide la base
obtenue en SQL dans le fichier demandé. Le test de la migration suivante charge ce fichier
et migre.

Usage :
    python tools/fabriquer_base_de_version.py <commit> <fichier .sql>
    python tools/fabriquer_base_de_version.py 10a3a90 tests/bases/v29-10a3a90.sql

Le commit est celui du DERNIER état de la version à fabriquer (la tête de `main` avant la
migration, par exemple). Le fichier se nomme `tests/bases/v<version>-<commit>.sql` ; son
en-tête dit la version, le commit, la commande qui le refait et ce que la base contient.
Refaire le fichier change ses dates (créations, actes du journal) et rien d'autre : les
identifiants, les comptes et le contenu sont les mêmes à chaque fabrication, à moteur NLP
égal — sans spaCy, aucun token n'est écrit.

Ce que le parcours pose, et pourquoi :
- deux collections, trois comptes (un administrateur, deux qui écrivent) ;
- quatre albums, des planches importées, des cases et des bulles, du texte, une
  annotation, un locuteur, une présence, un attribut de case, une planche validée, un
  Ctrl+Z ;
- des destructions EN HAUT de chaque table : la dernière région, le dernier album, le
  dernier personnage — et la dernière planche, que seule la PORTÉE d'une activité nomme
  (une passe sans effet, par `journal.passe_ml` du code joué). Ce sont les identifiants
  qu'une migration ne doit pas rendre ;
- à partir de la v30 (`_parcours_v30`, COL-3, tranche 3) : deux responsables du projet de
  repli (un compte, un groupe) ; un second projet, son responsable, un membre et un groupe
  membres ; la collection de repli ; une copie gardée
  au fonds ; un album importé au fonds puis rendu ; des demandes de suppression en attente,
  refusée, acceptée ; une demande de suppression de projet ; deux projets supprimés vides,
  le plus grand identifiant de projet n'étant plus nommé que par le journal et une demande ;
- à partir de la v31 (`_parcours_v31`, COL-3, tranche 3b) : la base d'un projet ouverte ;
  deux copies sœurs d'un document ; un « rejoindre » accepté, un refusé ; un retour qui
  attend ;
- à partir de la v34 (`_parcours_v34`, COL-4) : une copie amorcée (`region_origine`) ; deux
  collections détruites en haut de leur table, la première nommée encore par une demande,
  la seconde par le seul journal. Les planches du code v34 notent leur `master_origine` ;
- à partir de la v35 (`_parcours_v35`, COL-3, tranche 3b) : le jeu des bacs à sable, préparé
  par son outil ; deux bacs à sable, dont l'un où un invité a créé une collection et importé
  un album ; une collection créée par un simple membre d'un projet ordinaire ;
- à partir de la v36 (`_parcours_v36`, ANN-7, tranche 1) : des régions des cinq types, des
  textes à apostrophes et à tirets ; une copie sœur amorcée au cran `annotations` ; un album
  retiré du projet ; le réglage de création ouvert ; une planche et une région détruites en
  haut de leur table.

Le parcours n'emploie que des routes stables depuis la v29. Si une version les change, il
gagne une branche sur `database.SCHEMA_VERSION` plutôt que de perdre l'ancienne forme :
chaque fichier de `tests/bases/` doit rester refabricable. Une réponse inattendue arrête
tout en disant laquelle.

Ce que l'outil ne fait pas : il ne lit ni n'écrit la base de l'instance, ni ses dossiers
d'images. Tout vit dans le dossier temporaire, effacé à la fin. Les moteurs ML ne sont pas
requis (Kumiko n'est pas copié). L'option `--copie` est interne : c'est la seconde moitié
de l'outil, lancée par la première dans le code extrait.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Première moitié : extraire le code du commit, et y lancer la seconde
# --------------------------------------------------------------------------- #
def _extraire_puis_fabriquer(commit: str, sortie: Path) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _commun import forcer_utf8
    forcer_utf8()
    sha = subprocess.run(["git", "rev-parse", "--verify", f"{commit}^{{commit}}"],
                         cwd=RACINE, capture_output=True, text=True)
    if sha.returncode:
        print(f"Commit introuvable dans {RACINE} : {commit}\n{sha.stderr}", file=sys.stderr)
        return 2
    sha = sha.stdout.strip()
    sortie = sortie.resolve()
    sortie.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="bd-base-de-version-"))
    try:
        archive = subprocess.run(["git", "archive", "--format=tar", sha], cwd=RACINE,
                                 capture_output=True, check=True).stdout
        code = tmp / "code"
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(code, filter="data")
        # La seconde moitié tourne DANS le code extrait : ses modules sont ceux du commit.
        return subprocess.run([sys.executable, str(Path(__file__).resolve()), sha, str(sortie),
                               "--copie", str(code)], cwd=code).returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Seconde moitié : jouer le parcours avec le code du commit
# --------------------------------------------------------------------------- #
ADMIN = {"Remote-User": "hugo", "Remote-Name": "Hugo", "Remote-Groups": "bd-admins"}
LEA = {"Remote-User": "lea", "Remote-Name": "Lea"}
SAM = {"Remote-User": "sam", "Remote-Name": "Sam"}


def _ok(r, *codes):
    assert r.status_code in codes, (r.request.method, str(r.request.url), r.status_code,
                                    r.text[:300])
    return r.json() if r.content else None


def _png() -> bytes:
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (40, 50), "white").save(b, "PNG")
    return b.getvalue()


# La version du code joué, posée par `_jouer_le_parcours` : quelques gestes ont changé de
# forme d'une version à l'autre, et chaque fichier de `tests/bases/` doit rester refabricable.
_VERSION = 0


def _collection_du_repli(c, qui, nom: str) -> int:
    """Une collection du projet de REPLI, possédée par `qui`. Jusqu'à la v35, tout compte
    identifié en créait une ; depuis la v36 (COL-3, tranche 3b), créer une collection revient
    aux responsables du projet et aux administrateurs : l'administrateur la crée, puis en
    fait `qui` propriétaire — le même état, par les gestes que la v36 permet."""
    if _VERSION < 36:
        return _ok(c.post("/api/collections", headers=qui, json={"nom": nom}), 201)["id"]
    cid = _ok(c.post("/api/collections", headers=ADMIN, json={"nom": nom}), 201)["id"]
    _ok(c.put(f"/api/collections/{cid}/acces", headers=ADMIN,
              json={"genre": "utilisateur", "principal": qui["Remote-User"],
                    "niveau": "proprietaire"}), 200)
    return cid


def _jouer_le_parcours(main, database, journal) -> dict:
    """Le parcours, par les routes du code joué. Rend ce qu'il faut savoir de la base."""
    from fastapi.testclient import TestClient
    global _VERSION
    _VERSION = database.SCHEMA_VERSION
    with TestClient(main.app, headers={main.EN_TETE_REQUETE: "1"}) as c:
        for qui in (ADMIN, LEA, SAM):
            c.get("/api/moi", headers=qui)
        principal = _ok(c.post("/api/collections", json={"nom": "Corpus principal"},
                               headers=ADMIN), 201)["id"]
        incub = _ok(c.post("/api/collections", json={"nom": "Incubateur"},
                           headers=ADMIN), 201)["id"]
        for cid, qui in ((principal, "lea"), (incub, "lea"), (principal, "sam")):
            _ok(c.put(f"/api/collections/{cid}/acces", headers=ADMIN,
                      json={"genre": "utilisateur", "principal": qui, "niveau": "ecriture"}),
                200)
        dim = _ok(c.post("/api/attributs/dimensions", headers=LEA,
                         json={"cible": "case", "nom": "cadrage"}), 201)["id"]
        valeur = _ok(c.post(f"/api/attributs/dimensions/{dim}/valeurs", headers=LEA,
                            json={"valeur": "gros plan"}), 201)["id"]
        persos = [_ok(c.post("/api/personnages", json={"nom": n}, headers=LEA), 200, 201)["id"]
                  for n in ("Tintin", "Haddock")]
        albums, planches, regions = [], [], []
        for i, (qui, cid) in enumerate(((LEA, principal), (SAM, principal), (LEA, incub),
                                        (LEA, principal))):
            a = _ok(c.post("/api/albums", headers=qui,
                           json={"titre": f"Album {i + 1}", "collection_id": cid}), 201)["id"]
            albums.append(a)
            for p in range(2):
                pl = _ok(c.post(f"/api/albums/{a}/import", headers=qui,
                                files={"file": ("p.png", _png(), "image/png")}), 201)["id"]
                planches.append(pl)
                case = _ok(c.post(f"/api/planches/{pl}/regions", headers=qui,
                                  json={"type": "case", "x": 0, "y": 0, "w": 30, "h": 20}),
                           201)["id"]
                bulle = _ok(c.post(f"/api/planches/{pl}/regions", headers=qui,
                                   json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                                         "parent_id": case}), 201)["id"]
                regions += [case, bulle]
                _ok(c.put(f"/api/regions/{bulle}", headers=qui,
                          json={"ocr_texte": f"TINTIN ET LE OTAGE {i} {p}"}), 200)
                if p == 0:
                    _ok(c.put(f"/api/regions/{bulle}/annotation", headers=qui,
                              json={"note": "vu", "tags": ["dialogue"]}), 200)
                    _ok(c.put(f"/api/regions/{bulle}/locuteur", headers=qui,
                              json={"personnage_id": persos[0]}), 200)
                    # La présence d'un personnage se montre sur une BOÎTE personnage
                    # depuis un commit de la v34 (422 sur une case) : la branche garde
                    # l'ancienne forme, et chaque fichier refabricable à l'identique.
                    montre = case
                    if database.SCHEMA_VERSION >= 34:
                        montre = _ok(c.post(f"/api/planches/{pl}/regions", headers=qui,
                                            json={"type": "personnage", "x": 2, "y": 2,
                                                  "w": 5, "h": 5, "parent_id": case}),
                                     201)["id"]
                    _ok(c.put(f"/api/regions/{montre}/personnage", headers=qui,
                              json={"personnage_id": persos[1]}), 200)
                    _ok(c.put(f"/api/regions/{case}/attributs", headers=qui,
                              json={"valeur_id": valeur}), 200)
                    _ok(c.patch(f"/api/planches/{pl}/validation", headers=qui,
                                json={"validee": True}), 200)
        # Un Ctrl+Z, pour que le journal porte une annulation.
        _ok(c.put(f"/api/regions/{regions[1]}", headers=LEA,
                  json={"ocr_texte": "AVANT ANNULER"}), 200)
        _ok(c.post("/api/undo", headers=LEA), 200)
        # La dernière région détruite (instantané profond).
        _ok(c.delete(f"/api/regions/{regions[-1]}", headers=LEA), 204)
        # Une passe automatique sans effet sur la dernière planche, puis cette planche
        # détruite : seule la portée de l'activité la nomme.
        derniere_planche = planches[-1]
        with database.connect() as conn:
            with journal.passe_ml(conn, "ocr", derniere_planche, agent="easyocr"):
                pass
        _ok(c.delete(f"/api/planches/{derniere_planche}", headers=ADMIN), 204)
        # Le dernier album détruit, son dossier d'images avec lui (par l'application).
        _ok(c.delete(f"/api/albums/{albums[-1]}", headers=ADMIN), 204)
        # Le dernier personnage : un locuteur le nomme, puis il est détruit.
        mort = _ok(c.post("/api/personnages", json={"nom": "Rastapopoulos"}, headers=LEA),
                   200, 201)["id"]
        _ok(c.put(f"/api/regions/{regions[1]}/locuteur", headers=LEA,
                  json={"personnage_id": mort}), 200)
        _ok(c.put(f"/api/regions/{regions[1]}/locuteur", headers=LEA,
                  json={"personnage_id": persos[0]}), 200)
        _ok(c.delete(f"/api/personnages/{mort}", headers=LEA), 204)
        faits = {"album_detruit": albums[-1], "planche_detruite": derniere_planche,
                 "region_detruite": regions[-1], "personnage_detruit": mort}
        if database.SCHEMA_VERSION >= 30:
            faits.update(_parcours_v30(c, principal, albums[0]))
        if database.SCHEMA_VERSION >= 31:
            faits.update(_parcours_v31(c, principal, albums[1], faits))
        if database.SCHEMA_VERSION >= 34:
            faits.update(_parcours_v34(c, albums[1], faits))
        if database.SCHEMA_VERSION >= 35:
            faits.update(_parcours_v35(c, database, faits))
        if database.SCHEMA_VERSION >= 36:
            faits.update(_parcours_v36(c, faits))
    return faits


def _parcours_v30(c, principal: int, album_de_lea: int) -> dict:
    """Ce qu'une base v30 doit porter pour que la migration suivante ait de quoi se tromper
    (COL-3, tranche 3) : un second projet, son responsable, un membre et un groupe membres ;
    la collection de repli ; une copie gardée au fonds ; un album importé au fonds puis
    rendu ; des demandes de suppression en attente, refusée, acceptée ; une demande de
    suppression de projet ; et un projet supprimé VIDE, dont l'identifiant n'est plus nommé
    que par le journal et par une demande. Par les routes du code v30, sous les trois
    comptes du parcours."""
    def album(qui, cid, titre, planche=False):
        a = _ok(c.post("/api/albums", headers=qui,
                       json={"titre": titre, "collection_id": cid}), 201)["id"]
        if planche:
            _ok(c.post(f"/api/albums/{a}/import", headers=qui,
                       files={"file": ("p.png", _png(), "image/png")}), 201)
        return a

    def demander(qui, album_id):
        return _ok(c.post("/api/demandes", headers=qui,
                          json={"genre": "suppression_document", "album_id": album_id,
                                "motif": "Importé par erreur.", "certifie": True}), 201)["id"]

    def membre(projet, principal_, role, genre="utilisateur"):
        _ok(c.put(f"/api/projets/{projet}/membres", headers=ADMIN,
                  json={"genre": genre, "principal": principal_, "role": role}), 200)

    repli = next(p["id"] for p in _ok(c.get("/api/projets", headers=ADMIN), 200)
                 if p["repli"])
    # La collection de repli naît d'un album créé sans collection.
    sans_collection = _ok(c.post("/api/albums", headers=ADMIN,
                                 json={"titre": "Album sans collection"}), 201)["id"]
    membre(repli, "sam", "membre")
    # Des RESPONSABLES du projet de repli, un compte et un groupe : la v31 donne à chaque
    # projet une base dont ses responsables sont propriétaires — rien d'existant ne doit
    # s'ouvrir à eux (relecture croisée de la v31, constat 1).
    membre(repli, "rita", "responsable")
    membre(repli, "chefs", "responsable", genre="groupe")
    etude = _ok(c.post("/api/projets", headers=ADMIN, json={"nom": "Étude B"}), 201)["id"]
    membre(etude, "lea", "responsable")
    membre(etude, "sam", "membre")
    membre(etude, "etudiants", "membre", genre="groupe")
    collection_b = _ok(c.post("/api/collections", headers=LEA,
                              json={"nom": "Collection B", "projet_id": etude}), 201)["id"]
    # Une copie gardée au fonds : supprimée de sa dernière collection, son projet écrit.
    gardee = album(LEA, collection_b, "Gardée au fonds", planche=True)
    _ok(c.delete(f"/api/albums/{gardee}/collections/{collection_b}", headers=LEA), 204)
    # Un album importé au fonds par l'administrateur, puis rendu à une collection.
    rendu = _ok(c.post("/api/albums", headers=ADMIN,
                       json={"titre": "Importé au fonds", "au_fonds": True}), 201)["id"]
    _ok(c.put(f"/api/albums/{rendu}/collections/{principal}", headers=ADMIN), 201)
    # Trois demandes de suppression : en attente, refusée, acceptée.
    en_attente = demander(SAM, album_de_lea)
    refusee_album = album(LEA, principal, "Demande refusée")
    refusee = demander(SAM, refusee_album)
    _ok(c.post(f"/api/demandes/{refusee}/reponse", headers=ADMIN,
               json={"reponse": "refusee"}), 200)
    acceptee_album = album(LEA, principal, "Demande acceptée", planche=True)
    acceptee = demander(SAM, acceptee_album)
    _ok(c.post(f"/api/demandes/{acceptee}/reponse", headers=ADMIN,
               json={"reponse": "acceptee"}), 200)
    # La suppression d'un projet demandée par son responsable : elle attend (il porte une
    # collection).
    demande_projet = _ok(c.post("/api/demandes", headers=LEA,
                                json={"genre": "suppression_projet", "projet_id": etude,
                                      "motif": "Étude terminée."}), 201)["id"]
    # Un projet supprimé vide par l'administrateur, puis un second — l'identifiant rendu par
    # SQLite en v30 — supprimé sur la demande de son responsable : le plus grand identifiant
    # de projet n'est plus nommé que par le journal et par `demande.projet_id`.
    ephemere = _ok(c.post("/api/projets", headers=ADMIN, json={"nom": "Éphémère"}), 201)["id"]
    _ok(c.delete(f"/api/projets/{ephemere}", headers=ADMIN), 204)
    ephemere_2 = _ok(c.post("/api/projets", headers=ADMIN,
                            json={"nom": "Éphémère 2"}), 201)["id"]
    membre(ephemere_2, "sam", "responsable")
    demande_ephemere = _ok(c.post("/api/demandes", headers=SAM,
                                  json={"genre": "suppression_projet",
                                        "projet_id": ephemere_2,
                                        "motif": "Créé par erreur."}), 201)["id"]
    _ok(c.post(f"/api/demandes/{demande_ephemere}/reponse", headers=ADMIN,
               json={"reponse": "acceptee"}), 200)
    return {"projet_repli": repli, "projet_etude": etude, "collection_b": collection_b,
            "album_sans_collection": sans_collection, "album_garde_au_fonds": gardee,
            "album_rendu": rendu, "album_detruit_sur_demande": acceptee_album,
            "demandes": {"en_attente": en_attente, "refusee": refusee, "acceptee": acceptee,
                         "projet_en_attente": demande_projet,
                         "projet_acceptee": demande_ephemere},
            "projets_supprimes": sorted({ephemere, ephemere_2})}


def _parcours_v31(c, principal: int, album_de_sam: int, faits: dict) -> dict:
    """Ce qu'une base v31 doit porter pour que la v32 ait de quoi se tromper (COL-3,
    tranche 3b) : la base d'un projet OUVERTE à ses membres ; deux copies SŒURS d'un même
    document, la seconde vierge, prise dans une autre collection du projet ; un
    « rejoindre » demandé puis accepté, un autre refusé ; un retour d'une copie gardée au
    fonds, qui attend. Par les routes du code v31.

    Ce qu'il ne pose pas : des corrections grammaticales. Elles demandent spaCy, que la
    fabrication ne requiert pas (« sans spaCy, aucun token n'est écrit ») ; la v32 n'en
    touche aucune."""
    etude = faits["projet_etude"]
    projets = {p["id"]: p for p in _ok(c.get("/api/projets", headers=LEA), 200)}
    base_etude = projets[etude]["base"]["id"]
    _ok(c.put(f"/api/projets/{etude}/acces-membres", headers=LEA,
              json={"acces_membres": "ecriture"}), 200)
    collection_c = _ok(c.post("/api/collections", headers=LEA,
                              json={"nom": "Collection C", "projet_id": etude}), 201)["id"]
    # La source des sœurs : un album travaillé dans la Collection B.
    source = _ok(c.post("/api/albums", headers=LEA,
                        json={"titre": "Source des sœurs",
                              "collection_id": faits["collection_b"]}), 201)["id"]
    pl = _ok(c.post(f"/api/albums/{source}/import", headers=LEA,
                    files={"file": ("p.png", _png(), "image/png")}), 201)["id"]
    case = _ok(c.post(f"/api/planches/{pl}/regions", headers=LEA,
                      json={"type": "case", "x": 0, "y": 0, "w": 30, "h": 20}), 201)["id"]
    bulle = _ok(c.post(f"/api/planches/{pl}/regions", headers=LEA,
                       json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                             "parent_id": case}), 201)["id"]
    _ok(c.put(f"/api/regions/{bulle}", headers=LEA, json={"ocr_texte": "LE OTAGE SOEUR"}),
        200)
    _ok(c.put(f"/api/regions/{bulle}/annotation", headers=LEA,
              json={"note": "source", "tags": ["dialogue"]}), 200)
    document = next(a["document_id"] for a in _ok(c.get("/api/albums", headers=ADMIN), 200)
                    if a["id"] == source)
    # La sœur vierge, prise par la responsable pour une autre collection de son projet.
    prise = _ok(c.post(f"/api/collections/{collection_c}/prendre", headers=LEA,
                       json={"documents": [{"document_id": document, "reponse": "zero",
                                            "album_id": source}]}), 200)
    soeur = prise["documents"][0]["copie_id"]
    assert soeur, prise
    # Deux « rejoindre » : Léa range dans sa collection un album de Sam qu'elle lit ; le
    # Corpus principal n'a pas de propriétaire, donc un administrateur répond.
    lea_seule = _collection_du_repli(c, LEA, "Collection de Léa")
    rejoint = _ok(c.put(f"/api/albums/{album_de_sam}/collections/{lea_seule}",
                        headers=LEA), 202)["demande_id"]
    _ok(c.post(f"/api/demandes/{rejoint}/reponse", headers=ADMIN,
               json={"reponse": "acceptee"}), 200)
    autre = _ok(c.post("/api/albums", headers=SAM,
                       json={"titre": "Rejoindre refusé", "collection_id": principal}),
                201)["id"]
    refuse = _ok(c.put(f"/api/albums/{autre}/collections/{lea_seule}", headers=LEA),
                 202)["demande_id"]
    _ok(c.post(f"/api/demandes/{refuse}/reponse", headers=ADMIN,
               json={"reponse": "refusee"}), 200)
    # Un retour qui attend : la responsable demande à reprendre sa copie gardée au fonds.
    gardee = faits["album_garde_au_fonds"]
    doc_garde = next(a["document_id"] for a in _ok(c.get("/api/albums", headers=ADMIN), 200)
                     if a["id"] == gardee)
    retour = _ok(c.post(f"/api/projets/{etude}/prendre", headers=LEA,
                        json={"documents": [{"document_id": doc_garde,
                                             "reponse": "reprendre", "album_id": gardee}],
                              "motif": "On y retravaille."}), 200)["documents"][0]["demande_id"]
    return {"base_etude": base_etude, "collection_c": collection_c,
            "album_source_des_soeurs": source, "album_soeur": soeur,
            "collection_de_lea": lea_seule,
            "demandes_v31": {"rejoindre_acceptee": rejoint, "rejoindre_refusee": refuse,
                             "retour": retour}}


def _parcours_v34(c, album_de_sam: int, faits: dict) -> dict:
    """Ce qu'une base v34 doit porter pour que la v35 ait de quoi se tromper (COL-4) : des
    COLLECTIONS détruites en haut de leur table — la v35 leur donne `AUTOINCREMENT`, et
    leur compteur doit repartir au-dessus de ce que le journal et une demande nomment
    encore —, et une copie AMORCÉE (tranche 3b : `region_origine`). Les planches importées
    par le code v34 notent déjà le nom du fichier reçu (`master_origine`, IMG-1) ; les
    copies sœurs viennent de `_parcours_v31`. Par les routes du code v34.

    Deux collections détruites, et dans cet ordre : la première est nommée, après sa
    destruction, par une demande de « rejoindre » refusée (`demande.collection_id`, sans
    clé étrangère) ; la seconde, la plus haute, par le seul journal."""
    # Une copie amorcée jusqu'au cran `transcription` : la source a du texte, et la
    # responsable tient ses deux collections (immédiat, `clause_rejoindre_directe`).
    source = faits["album_source_des_soeurs"]
    document = next(a["document_id"] for a in _ok(c.get("/api/albums", headers=ADMIN), 200)
                    if a["id"] == source)
    prise = _ok(c.post(f"/api/collections/{faits['collection_c']}/prendre", headers=LEA,
                       json={"documents": [{"document_id": document, "reponse": "amorcer",
                                            "album_id": source,
                                            "cran": "transcription"}]}), 200)
    amorcee = prise["documents"][0]["copie_id"]
    assert amorcee and prise["documents"][0]["etat"] == "fait", prise
    # Les deux naissent d'abord — en v34 l'identifiant d'une collection détruite revient au
    # suivant, et la seconde reprendrait celui de la première. La première : un
    # « rejoindre » la vise, refusé par sa destruction. La seconde, la plus haute : le
    # journal seul la nomme.
    visee = _collection_du_repli(c, LEA, "Arrivée détruite")
    haute = _collection_du_repli(c, LEA, "Éphémère")
    assert haute > visee
    _ok(c.put(f"/api/albums/{album_de_sam}/collections/{visee}", headers=LEA), 202)
    _ok(c.delete(f"/api/collections/{visee}", headers=LEA), 204)
    _ok(c.delete(f"/api/collections/{haute}", headers=LEA), 204)
    return {"album_amorce": amorcee, "collections_detruites": [visee, haute]}


def _parcours_v35(c, database, faits: dict) -> dict:
    """Ce qu'une base v35 doit porter pour que la v36 ait de quoi se tromper (COL-3, tranche
    3b : qui crée une collection devient un réglage du projet) : le JEU des bacs à sable,
    préparé par son outil ; deux BACS À SABLE — celui de Léa, où Sam est invité, a créé une
    collection et importé un album ; celui de l'administrateur — ; et une collection créée
    par un simple MEMBRE d'un projet ordinaire (Sam, dans Étude B), ce que la v35 laissait
    faire. La v36 ajoute à `projet` un réglage que tout l'existant reçoit à « non », sans
    rien changer d'autre. Par les routes du code v35 et par son outil du jeu, importé du
    code extrait."""
    sys.path.insert(0, str(Path.cwd() / "tools"))
    import preparer_jeu
    depot = Path(os.environ["BD_DATA_DIR"]) / "jeu-depot"
    depot.mkdir()
    for nom in ("j1.png", "j2.png"):
        (depot / nom).write_bytes(_png())
    bulle = {"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9, "texte": "LE OTAGE"}
    (depot / "jeu.json").write_text(json.dumps({"documents": [
        {"cle": "parcours", "titre": "Le parcours", "role": "pas-a-pas", "rang": 1,
         "cran": "images", "planches": [{"fichier": "j1.png"}]},
        {"cle": "exemple", "titre": "Un exemple", "role": "exemple", "cran": "transcription",
         "planches": [{"fichier": "j2.png", "regions": [
             {"type": "case", "x": 0, "y": 0, "w": 30, "h": 30, "enfants": [bulle]}]}]},
    ]}, ensure_ascii=False), encoding="utf-8")
    with database.connect() as conn:
        preparer_jeu.preparer(conn, depot=depot, appliquer_=True, dire=lambda _l: None)
        jeu = database.projet_de_jeu(conn)
    bac_lea = _ok(c.post("/api/bac-a-sable", headers=LEA), 201)
    _ok(c.put(f"/api/projets/{bac_lea['id']}/membres", headers=LEA,
              json={"genre": "utilisateur", "principal": "sam", "role": "membre"}), 200)
    chez_sam = _ok(c.post("/api/collections", headers=SAM,
                          json={"nom": "Chez Sam", "projet_id": bac_lea["id"]}), 201)["id"]
    du_bac = _ok(c.post("/api/albums", headers=SAM,
                        json={"titre": "Importé au bac", "collection_id": chez_sam}),
                 201)["id"]
    _ok(c.post(f"/api/albums/{du_bac}/import", headers=SAM,
               files={"file": ("p.png", _png(), "image/png")}), 201)
    bac_admin = _ok(c.post("/api/bac-a-sable", headers=ADMIN), 201)
    # Depuis la v36, un simple membre ne crée une collection que si le projet le lui ouvre :
    # la responsable ouvre le réglage d'abord (le même état, par les gestes de la v36).
    if _VERSION >= 36:
        _ok(c.put(f"/api/projets/{faits['projet_etude']}/creation-de-collections",
                  headers=LEA, json={"membres": True}), 200)
    par_un_membre = _ok(c.post("/api/collections", headers=SAM,
                               json={"nom": "Par un membre",
                                     "projet_id": faits["projet_etude"]}), 201)["id"]
    return {"projet_de_jeu": jeu, "bacs_a_sable": [bac_lea["id"], bac_admin["id"]],
            "collection_d_un_invite": chez_sam, "album_du_bac": du_bac,
            "collection_d_un_membre": par_un_membre}


def _parcours_v36(c, faits: dict) -> dict:
    """Ce qu'une base v36 doit porter pour que la v37 ait de quoi se tromper (ANN-7, tranche
    1 : les grilles et les relevés, seize tables neuves et `regions.nom`) : des régions des
    CINQ types d'aujourd'hui (case, bulle, cartouche, texte, boîte personnage), des textes à
    apostrophes — droites et typographiques —, à tirets et à ponctuations répétées (ce que
    le découpage en mots de la v37 lira) ; deux copies SŒURS dont l'une AMORCÉE au cran
    `annotations` (le cran où les relevés suivront) ; un album RETIRÉ du projet par sa
    responsable, avec un motif ; le réglage « les membres créent des collections » ouvert sur
    Étude B ; et, en haut de leur table, une planche et une région détruites — les
    identifiants qu'une migration ne doit pas rendre. Les bacs à sable viennent de
    `_parcours_v35`. Par les routes du code v36."""
    etude, collection_b = faits["projet_etude"], faits["collection_b"]
    cinq = _ok(c.post("/api/albums", headers=LEA,
                      json={"titre": "Cinq types", "collection_id": collection_b}), 201)["id"]
    pl = _ok(c.post(f"/api/albums/{cinq}/import", headers=LEA,
                    files={"file": ("p.png", _png(), "image/png")}), 201)["id"]
    case = _ok(c.post(f"/api/planches/{pl}/regions", headers=LEA,
                      json={"type": "case", "x": 0, "y": 0, "w": 30, "h": 30}), 201)["id"]
    zones = {}
    for type_, texte in (("bulle", "J'SAIS PAS… AUJOURD’HUI, PEUT-ÊTRE !!!"),
                         ("cartouche", "— C'EST L'HISTOIRE D'UN OTAGE..."),
                         ("texte", "presqu'île, dis-moi : va-t-il por-\ntrait ?!")):
        zones[type_] = _ok(c.post(f"/api/planches/{pl}/regions", headers=LEA,
                                  json={"type": type_, "x": 1, "y": 1, "w": 9, "h": 9,
                                        "parent_id": case}), 201)["id"]
        _ok(c.put(f"/api/regions/{zones[type_]}", headers=LEA, json={"ocr_texte": texte}), 200)
    boite = _ok(c.post(f"/api/planches/{pl}/regions", headers=LEA,
                       json={"type": "personnage", "x": 2, "y": 2, "w": 5, "h": 5,
                             "parent_id": case}), 201)["id"]
    _ok(c.put(f"/api/regions/{zones['bulle']}/annotation", headers=LEA,
              json={"note": "à relever", "tags": ["dialogue"]}), 200)
    # Sa sœur AMORCÉE au cran `annotations`, dans la Collection C : la responsable tient les
    # deux collections, la copie naît tout de suite (`clause_rejoindre_directe`).
    document = next(a["document_id"] for a in _ok(c.get("/api/albums", headers=ADMIN), 200)
                    if a["id"] == cinq)
    prise = _ok(c.post(f"/api/collections/{faits['collection_c']}/prendre", headers=LEA,
                       json={"documents": [{"document_id": document, "reponse": "amorcer",
                                            "album_id": cinq, "cran": "annotations"}]}), 200)
    amorcee = prise["documents"][0]["copie_id"]
    assert amorcee and prise["documents"][0]["etat"] == "fait", prise
    # Un album RETIRÉ du projet par sa responsable : il part au fonds, l'acte le dit.
    retire = _ok(c.post("/api/albums", headers=LEA,
                        json={"titre": "Retiré du projet", "collection_id": collection_b}),
                 201)["id"]
    _ok(c.post(f"/api/albums/{retire}/import", headers=LEA,
               files={"file": ("p.png", _png(), "image/png")}), 201)
    _ok(c.post(f"/api/albums/{retire}/retirer-du-projet", headers=LEA,
               json={"motif": "Entré par erreur."}), 200)
    # Le réglage de la v36 est ouvert sur Étude B par `_parcours_v35`, avant qu'un membre y
    # crée sa collection.
    # En DERNIER, une planche puis une région détruites en haut de leur table.
    haute = _ok(c.post(f"/api/albums/{cinq}/import", headers=LEA,
                       files={"file": ("p.png", _png(), "image/png")}), 201)["id"]
    region_haute = _ok(c.post(f"/api/planches/{pl}/regions", headers=LEA,
                              json={"type": "bulle", "x": 3, "y": 3, "w": 4, "h": 4}),
                       201)["id"]
    _ok(c.delete(f"/api/planches/{haute}", headers=ADMIN), 204)
    _ok(c.delete(f"/api/regions/{region_haute}", headers=LEA), 204)
    return {"album_cinq_types": cinq, "regions_cinq_types": {**zones, "case": case,
                                                             "personnage": boite},
            "album_amorce_annotations": amorcee, "album_retire_du_projet": retire,
            "planche_detruite_v36": haute, "region_detruite_v36": region_haute}


def _vider_en_sql(base: Path, sortie: Path, version: int, sha: str, faits: dict) -> None:
    conn = sqlite3.connect(base)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    assert conn.execute("PRAGMA user_version").fetchone()[0] == version
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    faits = {
        "albums_vivants": [r[0] for r in conn.execute("SELECT id FROM albums ORDER BY id")],
        **faits,
        "max": {t: conn.execute(f"SELECT MAX(id) FROM {t}").fetchone()[0]
                for t in ("albums", "planches", "regions", "personnages")},
        "comptes": {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in ("albums", "planches", "regions", "personnages", "evenement",
                              "activite", "tokens", "annotations", "recherche")},
        "activites": [tuple(r) for r in conn.execute("SELECT type, portee FROM activite")],
    }
    if version >= 30:
        # Ce que la v30 a ajouté, compté à part : un fichier v29 refait reste identique.
        faits["max"].update({t: conn.execute(f"SELECT MAX(id) FROM {t}").fetchone()[0]
                             for t in ("projet", "collection", "document", "demande")})
        faits["comptes"].update({t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                                 for t in ("projet", "projet_acces", "collection",
                                           "document", "demande", "demande_document")})
    if version >= 31:
        faits["comptes"].update({t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                                 for t in ("copie",)})
        faits["demandes_par_genre"] = dict(conn.execute(
            "SELECT genre, COUNT(*) FROM demande GROUP BY genre ORDER BY genre").fetchall())
    if version >= 34:
        faits["comptes"].update({t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                                 for t in ("region_origine",)})
        faits["planches_avec_master_origine"] = conn.execute(
            "SELECT COUNT(*) FROM planches WHERE master_origine IS NOT NULL").fetchone()[0]
    if version >= 35:
        faits["comptes"].update({t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                                 for t in ("jeu_document",)})
        faits["natures_de_projet"] = dict(conn.execute(
            "SELECT CASE WHEN jeu = 1 THEN 'jeu' WHEN bac_a_sable_de IS NOT NULL "
            "THEN 'bac à sable' WHEN repli = 1 THEN 'repli' ELSE 'ordinaire' END AS n, "
            "COUNT(*) FROM projet GROUP BY n ORDER BY n").fetchall())
    if version >= 36:
        faits["comptes"].update({t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                                 for t in ("geste_sur_copie", "retrait_vu")})
        faits["regions_par_type"] = dict(conn.execute(
            "SELECT type, COUNT(*) FROM regions GROUP BY type ORDER BY type").fetchall())
        faits["crans_des_copies"] = dict(conn.execute(
            "SELECT cran, COUNT(*) FROM copie GROUP BY cran ORDER BY cran").fetchall())
    try:
        relatif = sortie.relative_to(RACINE).as_posix()
    except ValueError:
        relatif = sortie.name
    with open(sortie, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"-- Base v{version} faite par le code de {sha[:7]} (ses routes, sous trois "
                "comptes), vidée par\n"
                "-- `sqlite3.Connection.iterdump` (la table plein texte recréée par son "
                "CREATE).\n"
                f"-- Refaite par : python tools/fabriquer_base_de_version.py {sha[:7]} "
                f"{relatif}\n"
                "-- Ce qu'elle contient :\n")
        for cle, val in faits.items():
            f.write(f"--   {cle} : {json.dumps(val, ensure_ascii=False)}\n")
        # `iterdump` rend une table virtuelle par une écriture dans `sqlite_master`, que
        # SQLite refuse en silence au rechargement, et ses tables internes à part. La table
        # plein texte est donc recréée par son CREATE, et remplie par ses lignes : FTS5
        # refait ses tables internes lui-même.
        virtuelles = {n: s for n, s in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE sql LIKE 'CREATE VIRTUAL TABLE%'")}
        internes = tuple(f"'{n}_" for n in virtuelles) + tuple(f'"{n}_' for n in virtuelles)
        for ligne in conn.iterdump():
            if ligne.startswith("PRAGMA writable_schema"):
                continue
            if ligne.startswith("INSERT INTO sqlite_master"):
                nom = next(n for n in virtuelles if f"'{n}'" in ligne)
                f.write(virtuelles[nom] + ";\n")
                continue
            if ligne.startswith(tuple(f"CREATE TABLE {p}" for p in internes)) or \
                    ligne.startswith(tuple(f"INSERT INTO {p}" for p in internes)):
                continue
            f.write(ligne + "\n")
        f.write(f"PRAGMA user_version = {version};\n")
    conn.close()
    print(json.dumps(faits, ensure_ascii=False))


def _fabriquer_dans(copie: Path, sha: str, sortie: Path) -> int:
    # Le dossier de l'outil (celui du dépôt courant) sort du chemin d'import : seuls les
    # modules du commit doivent répondre à `import database`.
    ici = str(Path(__file__).resolve().parent)
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != Path(ici)]
    sys.path.insert(0, str(copie))
    os.chdir(copie)
    travail = copie / "_donnees"
    travail.mkdir()
    base = travail / "base.sqlite"
    os.environ.update(BD_DB_PATH=str(base), BD_DATA_DIR=str(travail), BD_AUTH_PROXY="1")
    import database
    import journal
    import main
    faits = _jouer_le_parcours(main, database, journal)
    _vider_en_sql(base, sortie, database.SCHEMA_VERSION, sha, faits)
    print(f"v{database.SCHEMA_VERSION}, {sortie} ({sortie.stat().st_size} octets)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Fabrique une vraie base d'une version passée, avec le code de cette "
                    "version, et la vide en SQL (tests de migration).")
    ap.add_argument("commit", help="le commit dont le code fabrique la base (ex. 10a3a90)")
    ap.add_argument("sortie", help="le fichier .sql à écrire (ex. tests/bases/v29-10a3a90.sql)")
    ap.add_argument("--copie", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.copie:
        return _fabriquer_dans(Path(args.copie), args.commit, Path(args.sortie))
    return _extraire_puis_fabriquer(args.commit, Path(args.sortie))


if __name__ == "__main__":
    sys.exit(main())
