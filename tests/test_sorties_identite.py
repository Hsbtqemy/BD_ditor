"""AUTH-5 — le cliquet des voies de sortie : ce qui laisse partir une identité l'a déclaré.

Le patron est celui de `test_autorisation.py` : énumérer les surfaces, exiger que chacune
ait été TRANCHÉE, échouer sur celle qui ne figure nulle part. Il ferme la porte de l'OUBLI,
pas celle de l'erreur — il dit qu'une sortie a été VUE, jamais qu'elle est légitime.

Il existe parce que l'énumération à la main a échoué QUATRE fois de suite sur AUTH-1 (27,
28 et 31 août, deux fois ce jour-là), la dernière malgré une recherche méthodique de ce qui
lit `evenement` / `activite` / `utilisateur`. Ce qui a fini par trouver le chemin manquant
— l'onglet XLSX de `metadonnees_collection.py` — n'est aucune des quatre relectures : c'est
un `KeyError`. D'où un cliquet plutôt qu'une cinquième liste.

TROIS sortes d'identité, et pas une seule : AUTH-1 les distingue déjà — « ce n'est pas
l'email ni le nom lisible, mais un login identifie une personne ». La déclaration dit donc
QUELLE sorte chaque surface peut émettre, ce qu'une sentinelle unique ne saurait exprimer.
"""
import importlib.util
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

import inventaire_routes
import main

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"

# Introuvables par accident : aucune n'est sous-chaîne d'un mot français, d'un chemin, d'un
# nom de colonne, ni l'une de l'autre. Un faux positif rend un cliquet insupportable, et un
# cliquet insupportable finit désactivé.
SENTINELLES = {
    "login": "zzlogin7",
    "nom": "Zznom7",
    "courriel": "zzmel7@zzdom7.invalid",
}

# Un SECOND annotateur, non surveillé : certaines surfaces ne nomment que par CONTRASTE.
# L'accord inter-annotateurs ne compte que les re-touches d'un auteur sur le travail d'un
# AUTRE ; avec un seul agent, il ne nomme personne et paraît muet.
AUTRE_AGENT = "zzautre7"


# --------------------------------------------------------------------------- #
# Lecture d'une sortie, quel que soit son emballage
# --------------------------------------------------------------------------- #
def _texte(blob: bytes) -> str:
    """Rend le contenu FOUILLABLE d'une sortie, en dépliant les archives.

    Un XLSX est un zip (les chaînes vivent dans `sharedStrings.xml`) et la sauvegarde est
    un zip contenant un fichier SQLite (dont les pages portent le texte en clair). Les lire
    en octets ne prouve RIEN : c'est la faute qu'une mutation a révélée le 2026-08-31 sur le
    test du dépôt, où un classeur passait pour muet parce qu'il était compressé.
    """
    if blob[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                return "\n".join(z.read(n).decode("latin-1") for n in z.namelist())
        except zipfile.BadZipFile:                       # zip tronqué : on lit tel quel
            pass
    return blob.decode("latin-1")


def _sortes(blob: bytes) -> frozenset:
    """Les sortes d'identité présentes dans une sortie.

    Recherche INSENSIBLE À LA CASSE : une surface qui minusculerait un nom lisible — ce
    que fait couramment une normalisation, une clé de tri, un slug — y échapperait sinon,
    et le cliquet la déclarerait muette sans que rien ne le dise.
    """
    t = _texte(blob).lower()
    return frozenset(sorte for sorte, s in SENTINELLES.items() if s.lower() in t)


# --------------------------------------------------------------------------- #
# Le décor : chaque sentinelle dans CHAQUE colonne qui la porte
# --------------------------------------------------------------------------- #
@pytest.fixture
def seme(client, db_path, data_dir, png_bytes, derriere_proxy):
    """Un corpus minimal où l'identité sentinelle est partout où le modèle la range.

    Une colonne oubliée ici rend muette toute surface qui ne lit QUE cette colonne, et le
    vert du cliquet devient un mensonge. C'est le mode d'échec du cliquet lui-même — d'où
    `test_le_semis_est_visible`, qui exige que chaque sentinelle soit vue passer quelque
    part.
    """
    ident = {"Remote-User": SENTINELLES["login"],
             "Remote-Name": SENTINELLES["nom"],
             "Remote-Email": SENTINELLES["courriel"],
             "Remote-Groups": "bd-admins"}
    # Par l'API tant que c'est possible : le journal A3 enregistre alors l'agent lui-même,
    # ce qu'un INSERT direct ne prouverait pas.
    client.get("/api/moi", headers=ident)                       # → miroir `utilisateur`
    a = client.post("/api/albums", json={"titre": "Cliquet"}, headers=ident).json()
    pl = client.post(f"/api/albums/{a['id']}/import", headers=ident,
                     files={"file": ("p.png", png_bytes, "image/png")}).json()
    r = client.post(f"/api/planches/{pl['id']}/regions", headers=ident,
                    json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}).json()
    client.put(f"/api/regions/{r['id']}", json={"ocr_texte": "OTAGE"}, headers=ident)
    client.put(f"/api/regions/{r['id']}/annotation",
               json={"note": "n", "tags": ["t"]}, headers=ident)
    perso = client.post("/api/personnages", json={"nom": "P"}, headers=ident).json()
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "cadrage"}, headers=ident).json()
    # La collection de l'album — pas « la première », qui est depuis la v31 la base du
    # projet de repli, née avec lui et où l'album n'est pas.
    col = client.get(f"/api/albums/{a['id']}/collections", headers=ident).json()[0]
    # AUTH-12, étape 3 — un accès NOMINATIF au login sentinelle. Sans lui, `…/acces` et
    # `…/annuaire` rendaient des listes vides et passaient pour muettes alors qu'elles portent
    # des logins : le trou relevé par UX-4 le 2026-09-13, fermé ici pour qu'une colonne
    # d'identité ajoutée plus tard allume un rouge.
    r_acces = client.put(f"/api/collections/{col['id']}/acces", headers=ident,
                         json={"genre": "utilisateur", "principal": SENTINELLES["login"],
                               "niveau": "lecture"})
    assert r_acces.status_code in (200, 201), r_acces.text
    # COL-3 — et le même login MEMBRE d'un projet, pour la même raison : sans lui,
    # `…/membres` et `…/membres/choix` rendraient des listes vides et passeraient pour
    # muettes alors qu'elles portent des logins. Aucune vérification ici : un semis qui
    # échouerait laisserait leurs deux déclarations annoncer un login qu'elles n'émettent
    # pas, et c'est `test_les_declarations_ne_mentent_pas` qui tomberait.
    projet = client.get("/api/projets", headers=ident).json()[0]
    client.put(f"/api/projets/{projet['id']}/membres", headers=ident,
               json={"genre": "utilisateur", "principal": SENTINELLES["login"],
                     "role": "membre"})
    # COL-3, écran de la 3a — sa collection de BASE, OUVERTE à ses membres : le login
    # sentinelle y entre par le projet, et `…/acces-du-projet` le rend. La base du repli
    # naît protégée (rien ne s'ouvre au déploiement), et sur une collection ordinaire la
    # route rend une liste vide : sans ces deux gestes, elle passait pour muette.
    client.put(f"/api/projets/{projet['id']}/acces-membres", headers=ident,
               json={"acces_membres": "ecriture"})
    base = next(c for c in client.get("/api/collections", headers=ident).json()
                if c["base"] and c["projet_id"] == projet["id"])

    # Ce que l'API ne produit pas d'elle-même hors multi-utilisateur.
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE planches SET verrou_par = ? WHERE id = ?",
                     (SENTINELLES["login"], pl["id"]))
        # Le token AUTO sous la correction, POSÉ SI PERSONNE NE L'A POSÉ. `tokens_effectifs`
        # part `FROM tokens` (database.py) : une correction sans ligne de base à rejoindre
        # n'existe pour AUCUNE surface d'analyse. spaCy le pose quand le modèle est là ;
        # sans modèle `tokens` reste vide, et le cliquet concluait que la déclaration de
        # `/api/regions/{id}/tokens` mentait — un rouge qui fait chercher une régression
        # là où il n'y a qu'un moteur absent (QA-6, 2026-09-05).
        #
        # CONDITIONNEL, et il doit l'être : `tokens` n'a pas d'unicité sur
        # (region_id, ordre), un doublon ne lèverait donc RIEN et se paierait ailleurs —
        # l'accord modèle↔humain, la concordance et le « % relu » d'ANN-4 compteraient
        # deux tokens là où le corpus en a un. Cf. `test_le_semis_ne_double_pas_le_token`.
        #
        # Six autres fichiers de tests sèment `tokens` par SQL direct, et SANS condition :
        # leurs régions n'ont pas de texte OCR posé par l'API, donc rien ne déclenche
        # spaCy chez eux. Ce semis-ci passe par `PUT /api/regions/{id}`, et c'est la
        # seule raison pour laquelle il a besoin de la garde.
        conn.execute(
            "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
            "SELECT ?, 0, 'OTAGE', 'otage', 'NOUN', '' "
            "WHERE NOT EXISTS (SELECT 1 FROM tokens WHERE region_id = ? AND ordre = 0)",
            (r["id"], r["id"]))
        # Le LEMME est indispensable au semis, pas décoratif : `/api/analyse/concordance`
        # exige un critère, et sans lemme elle ne trouve rien — elle passerait donc pour
        # muette alors qu'elle sait filtrer PAR AUTEUR, donc parler d'annotateurs.
        conn.execute("INSERT INTO token_correction "
                     "(region_id, ordre, forme, lemme, pos, auteur) "
                     "VALUES (?, 0, 'OTAGE', 'otage', 'NOUN', ?)",
                     (r["id"], SENTINELLES["login"]))
        # COL-3, tranche 2 — une DEMANDE de suppression déposée par le login sentinelle, en
        # attente. Posée ici et non par l'API : la sentinelle est administratrice, et
        # l'API lui répond 409 — elle peut supprimer elle-même, il n'y a rien à demander.
        # Sans elle, `/api/demandes` rendrait une liste vide et `/api/albums` ne porterait
        # aucun demandeur : deux surfaces qui nomment passeraient pour muettes.
        doc = conn.execute("SELECT document_id FROM albums WHERE id = ?",
                           (a["id"],)).fetchone()[0]
        dem = conn.execute(
            "INSERT INTO demande (genre, demandeur, motif) "
            "VALUES ('suppression_document', ?, 'semis')", (SENTINELLES["login"],)).lastrowid
        conn.execute("INSERT INTO demande_document (demande_id, document_id, album_id, titre) "
                     "VALUES (?, ?, ?, 'Cliquet')", (dem, doc, a["id"]))
        # COL-3, tranche 3 — une demande de REJOINDRE l'album depuis sa collection, et une
        # ENTRÉE de documents pour le projet, déposées par le login sentinelle et en attente.
        # Sans elles, `…/collections/{id}/demandes` et `…/projets/{id}/demandes` rendraient
        # des listes vides et passeraient pour muettes alors qu'elles nomment qui demande.
        for genre in ("rejoindre", "entree_documents"):
            dem = conn.execute(
                "INSERT INTO demande (genre, demandeur, motif, projet_id, collection_id, "
                "collection_nom) VALUES (?, ?, 'semis', ?, ?, 'Arrivée')",
                (genre, SENTINELLES["login"], projet["id"], col["id"])).lastrowid
            conn.execute("INSERT INTO demande_document (demande_id, document_id, album_id, "
                         "titre) VALUES (?, ?, ?, 'Cliquet')",
                         (dem, doc, a["id"] if genre == "rejoindre" else None))
        act = conn.execute(
            "INSERT INTO activite (type, agent, agent_type) VALUES ('session', ?, 'humain')",
            (SENTINELLES["login"],)).lastrowid
        # Une CHAÎNE de révisions à deux auteurs. Sans le second, `accord-inter` ne
        # nomme personne — il ne compte que les re-touches INTER-auteurs — et le cliquet
        # prendrait pour muette la route qu'AUTH-1 vient tout juste de réserver. Le mode
        # d'échec d'un cliquet est son semis, jamais son balayage.
        for agent, pos, avant in ((AUTRE_AGENT, "NOUN", None),
                                  (SENTINELLES["login"], "VERB", "NOUN")):
            conn.execute(
                "INSERT INTO evenement (activite_id, type, agent, agent_type, cible_table, "
                "cible_id, avant, apres) VALUES (?, 'modification', ?, 'humain', "
                "'token_correction', 1, ?, ?)",
                (act, agent,
                 json.dumps({"lemme": "o", "pos": avant, "morph": ""}) if avant else None,
                 json.dumps({"lemme": "o", "pos": pos, "morph": ""})))
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")       # les tools lisent à part
    finally:
        conn.close()

    return {"ident": ident, "db": db_path, "data": data_dir,
            "album_id": a["id"], "planche_id": pl["id"], "region_id": r["id"],
            "collection_id": col["id"], "personnage_id": perso["id"],
            "dim_id": dim["id"],
            "projet_id": projet["id"],
            "base_id": base["id"],
            # `chemin_web` vaut « derivatives/xxx.jpg » ; la route monte déjà sur
            # /derivatives, on ne garde donc que la partie qui suit.
            "chemin": (pl.get("chemin_web") or "").split("derivatives/")[-1]}


# --------------------------------------------------------------------------- #
# Ce que chaque surface a le DROIT de laisser sortir, et pourquoi
# --------------------------------------------------------------------------- #
# Une entrée = une surface → (sortes émises, raison écrite). Le cliquet échoue sur une
# surface qui émet une sorte non déclarée, ET sur une déclaration qui annonce une sorte
# que la surface n'émet plus : une liste périmée est pire qu'absente, elle rassure.
#
# La liste a été bâtie par BALAYAGE le 2026-08-31, pas de mémoire — c'est tout l'objet du
# chantier. Elle décrit l'existant, y compris ce qu'on juge mauvais : le cliquet est un
# instrument d'inventaire, pas un arbitrage de masse. Chaque « à traiter » ci-dessous
# mérite sa décision, comme celle du 31 août sur l'accord inter-annotateurs.
SORTIES_DECLAREES = {
    # ---- Routes ----------------------------------------------------------- #
    ("route", "/api/comptes-et-groupes"): (
        {"login", "nom", "courriel"},
        "La vue « 👥 Comptes et groupes » (AUTH-12, étape 2), qui a remplacé `/api/comptes` : "
        "les trois sortes, chacune pour une raison — le login est la clé qu'on retape dans "
        "l'annuaire, le nom lisible évite de traduire, le courriel est par où l'on JOINT "
        "quelqu'un avant de toucher à son compte. Ce qu'elle ajoute (AUTH-6) : les comptes de "
        "l'ANNUAIRE, venus ou non, avec leurs groupes et les membres de chaque groupe. Le "
        "balayage n'y voit que le miroir `utilisateur`, la suite ne posant aucun annuaire : "
        "l'exposition réelle est plus large, et c'est écrit ici plutôt que tu. RÉSERVÉE aux "
        "administrateurs d'instance (403 sinon), elle ne sort de l'instance par aucun "
        "artefact : ni export, ni dépôt."),
    ("route", "/api/collections/{collection_id}/acces"): (
        {"login"},
        "Qui entre dans UNE collection : le principal d'un accès est un login ou un nom de "
        "groupe, et c'est lui qu'on retire ou qu'on change. Réservée au propriétaire de la "
        "collection. AUCUNE colonne d'identité n'y est jointe — ni nom lisible, ni dernière "
        "visite (UX-4, 2026-09-13) : le propriétaire sait déjà qui il a fait entrer. Balayée "
        "muette jusqu'au 2026-09-17 parce que le semis n'insérait aucun accès ; le semis en "
        "pose un désormais, pour qu'une colonne ajoutée plus tard allume un rouge."),
    ("route", "/api/collections/{collection_id}/annuaire"): (
        {"login"},
        "La vérification des accès DÉJÀ accordés sur cette collection (AUTH-12, étape 3) : "
        "mêmes logins que `…/acces`, un état d'annuaire en plus. Les groupes proposés au "
        "propriétaire sont des NOMS de groupe, sans membres ni id — aucune des trois sortes. "
        "Réservée au propriétaire de la collection."),
    ("route", "/api/projets/{projet_id}/membres"): (
        {"login"},
        "Qui est d'UN projet (COL-3) : le principal d'un membre est un login ou un nom de "
        "groupe, et c'est lui qu'on fait sortir ou dont on change le rôle. Réservée à qui "
        "GÈRE le projet — son responsable, ou un administrateur ; un simple membre reçoit "
        "un 403. Même forme que `…/acces` un étage plus bas : aucune colonne d'identité n'y "
        "est jointe, ni nom lisible, ni dernière visite. `GET /api/projets`, elle, ne nomme "
        "ni membres ni responsables, et reste muette."),
    ("route", "/api/projets/{projet_id}/membres/choix"): (
        {"login"},
        "La vérification des membres DÉJÀ posés sur ce projet (COL-3) : mêmes logins que "
        "`…/membres`, un état d'annuaire en plus. Les groupes proposés sont des NOMS de "
        "groupe, sans membres ni id — aucune des trois sortes. Réservée à qui gère le "
        "projet."),
    ("route", "/api/albums"): (
        {"login", "nom"},
        "COL-3, tranche 2 — QUI a demandé la suppression d'un album, sur la ligne de cet "
        "album (`demande.demandeur`, et son nom lisible par le miroir `utilisateur`). Rendu "
        "à une portée TOTALE — l'administrateur, qui y répond, ce que mesure ce balayage — "
        "et à la personne elle-même, à PERSONNE d'autre : tout autre lecteur reçoit la "
        "demande sans ces deux clés (Hugo, 2026-10-15, qui renverse la proposition R2 du "
        "cadrage ; mesuré sous une lectrice par "
        "`test_une_lectrice_lit_la_demande_sans_le_nom`). Le MOTIF n'y est pas — il ne se "
        "lit que dans le fonds. Le courriel ne sort pas : `noms_lisibles` ne lit jamais "
        "cette colonne. Avant la tranche 2 la liste ne nommait personne."),
    ("route", "/api/fonds"): (
        {"login", "nom"},
        "COL-3, tranche 2 — l'écran du FONDS : qui a importé chaque document "
        "(`document.importe_par`, et son nom lisible), et qui demande sa suppression. C'est "
        "l'ORIGINE que la tranche existe pour écrire. Réservée à qui tient le fonds — une "
        "portée totale (403 nommé sinon, avant toute lecture) ; aucun export ni dépôt n'en "
        "sort (`document` et `demande` sont des cibles retenues)."),
    ("route", "/api/demandes"): (
        {"login", "nom"},
        "COL-3, tranche 2 — les demandes : qui demande, qui a répondu, et leurs noms "
        "lisibles. Une demande sans auteur ne se répond pas. Réservée à qui tient le fonds, "
        "comme lui ; le motif y est, et ne sort par aucun artefact."),
    ("route", "/api/collections/{collection_id}/demandes"): (
        {"login", "nom"},
        "COL-3, tranche 3 — les demandes de REJOINDRE qui attendent sur une copie de cette "
        "collection : QUI demande (`demande.demandeur`, et son nom lisible). Réservée à qui "
        "ADMINISTRE la collection — son propriétaire, qui consent (D4, D11) ; on ne consent "
        "pas à partager un travail avec quelqu'un dont on ignore le nom, ce que le cadrage a "
        "accepté par écrit. Le nom passe par `Portee.peut_nommer_le_demandeur(consentement=…)`. "
        "Aucun artefact n'en sort (`demande` est une cible retenue)."),
    ("route", "/api/collections/{collection_id}/acces-du-projet"): (
        {"login"},
        "COL-3, écran de la 3a — les accès que le PROJET tient sur sa collection de base : "
        "le principal de chaque responsable et de chaque membre, un login ou un nom de "
        "groupe, comme `…/acces`. Mêmes bornes que lui, et pour la même raison — une donnée "
        "sur des PERSONNES : à qui ADMINISTRE la collection. Balayée sur la BASE du semis "
        "(`SUR_LA_BASE`), où elle parle ; aucun artefact n'en sort."),
    ("route", "/api/projets/{projet_id}/demandes"): (
        {"login", "nom"},
        "COL-3, tranche 3 — les ENTRÉES de documents demandées pour ce projet, lues par son "
        "responsable. Qui a déposé ne s'y nomme que pour soi-même et pour une portée totale "
        "(`Portee.peut_nommer_le_demandeur`) — ce que mesure ce balayage, la sentinelle étant "
        "administratrice. Qui a répondu n'y est pas. Réservée à qui gère le projet."),
    ("route", "/api/moi"): (
        {"login", "nom"},
        "L'identité de l'APPELANT, la sienne — c'est l'objet même de la route, et elle ne "
        "révèle rien du corpus (AUTH-2). Le courriel, lui, n'en sort PAS : il reste dans "
        "le miroir `utilisateur`, donc dans la seule sauvegarde."),
    ("route", "/api/albums/{album_id}/planches"): (
        {"login", "nom"},
        "`planches.verrou_par` — qui détient le verrou d'une planche. Nécessaire au geste : "
        "sans lui on ne sait pas à qui demander la libération. Le NOM LISIBLE l'accompagne "
        "depuis le 2026-08-31 (`verrou_par_nom`, miroir `utilisateur`) : un écran qui "
        "affiche un login demande à la personne de traduire elle-même, et deux logins "
        "voisins se confondent. Le login RESTE dans la charge utile — il est stable, et lui "
        "seul permet à l'écran de dire « par vous » plutôt que de comparer des noms "
        "d'affichage, que deux personnes peuvent partager. Le courriel, lui, ne sort pas : "
        "`noms_lisibles` ne lit jamais cette colonne."),
    ("route", "/api/regions/{region_id}/tokens"): (
        {"login"},
        "`token_correction.auteur` — qui a corrigé ce mot. C'est le socle de la relecture "
        "(ANN-4) et de l'accord modèle↔humain : une correction sans auteur ne se relit "
        "pas. Le MÊME champ sort PSEUDONYMISÉ des exports depuis le 2026-08-31, et ce "
        "n'est pas une incohérence : c'est la ligne DEDANS / DEHORS de DROIT-1 appliquée "
        "aux personnes. À l'intérieur de l'instance, savoir qui a corrigé est le travail ; "
        "dans un artefact qui part et ne bouge plus, c'est une donnée sur quelqu'un."),
    ("route", "/api/analyse/accord-inter"): (
        {"login"},
        "La mesure ne peut pas ne pas nommer — un accord inter-annotateurs sans "
        "annotateurs n'est pas un rapport affaibli, c'en est plus un du tout. TRANCHÉ le "
        "2026-08-31 : réservée à qui ÉCRIT, de sorte que ceux qui voient la mesure soient "
        "ceux qu'elle mesure. Cf. docs/accord-inter.md."),
    ("route", "/api/analyse/accord-inter.csv"): (
        {"login"},
        "Le MÊME rapport que sa jumelle JSON, en fichier — donc les mêmes noms, et le "
        "même 403 HÉRITÉ et non réécrit. TRANCHÉ le 2026-09-08 (ANA-7), et la question "
        "était neuve : le dépôt tenait déjà TROIS positions — l'écran nomme, le CLI nomme "
        "(« un rapport d'accord se lit pour arbitrer, puis se jette »), le dépôt ne publie "
        "que `nb_auteurs` et des taux —, et un fichier téléchargé tombait entre le CLI et "
        "le dépôt, là où AUTH-1 n'avait pas tracé de ligne. Retenu : NOMMER. Refuser au "
        "fichier ce que l'écran donne à la même personne serait une friction sans "
        "protection, la capture d'écran restant possible ; et ce fichier a UN usage — "
        "réunir deux personnes pour arbitrer un désaccord — que des pseudonymes rendraient "
        "impraticable. Ce qu'on accepte en échange est écrit plutôt que tu : un fichier "
        "PERSISTE et circule là où le CLI se jette. La garde n'est donc pas dans la forme, "
        "elle est dans l'accès."),
    ("route", "/api/sauvegarde"): (
        {"login", "nom", "courriel"},
        "La base ENTIÈRE, par construction — c'est ce qu'on attend d'une sauvegarde, et "
        "une sauvegarde partielle ne restaure pas une instance. Réservée aux "
        "administrateurs depuis DROIT-1 ; le zip est déplié par le balayage, sans quoi la "
        "compression la ferait passer pour muette."),

    # ---- Outils ----------------------------------------------------------- #

    ("outil", "rapport_accord_inter.py --json"): (
        {"login"},
        "L'instrument d'arbitrage de l'équipe : il nomme délibérément, et sans les noms on "
        "ne peut pas réunir deux personnes pour trancher un désaccord. TRANCHÉ le "
        "2026-08-31. "
        "Le SEUL outil qui nomme encore, et la question se pose puisque "
        "`provenance_export.py` demande le même accès shell et a, lui, été pseudonymisé. "
        "Ce n'est pas l'accès qui les sépare mais la DESTINATION : la sérialisation PROV-O "
        "est faite pour être DÉPOSÉE — c'est tout l'objet de la piste A — tandis qu'un "
        "rapport d'accord se lit pour arbitrer, puis se jette. Le jour où l'on voudrait "
        "déposer celui-ci, il faudra reprendre cette ligne."),
}

# Ces quatre-là émettaient un login jusqu'au 2026-08-31, et ne l'émettent plus : l'identité
# humaine est PSEUDONYMISÉE à la sortie (`_commun.pseudonymes`), les moteurs gardant leur
# nom. Elles ne sont plus déclarées — c'est le cliquet qui l'a exigé, en refusant une
# déclaration devenue périmée :
#   provenance_export.py --out-dir · metadonnees_collection.py --json / --csv-dir / --xlsx
# Le mapping est PARTAGÉ : deux tables ou deux sérialisations du même export qui
# nommeraient différemment la même personne se contrediraient sans que rien ne le dise.

# Surfaces qu'on ne sait pas encore atteindre, avec la raison — un trou ÉCRIT reste un
# trou, mais il ne se prend plus pour une couverture.
NON_BALAYE = {
    # ---- Limites du balayage lui-même, écrites plutôt que devinées ---------- #
    ("famille", "routes non-GET"): (
        "Le balayage n'appelle que des GET : une écriture demanderait une charge utile par "
        "route, donc une table aussi grande que l'application. La sortie connue de cette "
        "famille est `POST /api/figures`, qui rend un zip légendé (DROIT-1, « citer n'est "
        "pas publier ») ; sa légende est bâtie sur la PATERNITÉ de l'œuvre — contributions, "
        "édition, licence — et non sur les annotateurs. Mais « il n'y a pas de login "
        "là-dedans » est exactement ce que quatre inventaires ont affirmé avant d'avoir "
        "tort : ceci est un TROU, pas une garantie."),
    ("famille", "portée du balayeur"): (
        "La sentinelle est ADMINISTRATRICE (`Remote-Groups: bd-admins`), donc le balayage "
        "voit l'exposition MAXIMALE. C'est le bon choix pour chercher une fuite — un "
        "compte restreint en verrait moins et rassurerait à tort — mais cela signifie que "
        "le cliquet ne dit rien de ce que voit un lecteur ordinaire. C'est AUTH-2 qui "
        "répond de cela, et son propre cliquet."),

    # ---- Surfaces qu'on ne sait pas encore atteindre ------------------------ #
    ("route", "/api/jobs/{job_id}"): (
        "Un job est ÉPHÉMÈRE (threads daemon, registre RAM) : le décor ne sait pas en "
        "fabriquer un, et un id inventé rendrait 404. Il porte pourtant l'agent qui a "
        "lancé le lot — trou connu, à combler le jour où le décor sait lancer une passe."),
    ("route", "/api/sharedocs/liste"): (
        "Demande une session ShareDocs VIVANTE (400 sans). Elle liste un dossier distant "
        "chez Huma-Num, pas la base : aucune colonne d'identité ne la traverse."),
    ("outil", "_commun.py"): (
        "Bibliothèque partagée, sans `main()` — elle ne produit rien."),
    # CEUX-CI IMPRIMENT un compte rendu — dire « aucune sortie » serait faux. Ce qu'on
    # affirme est plus étroit et se vérifie : aucun ne mentionne `utilisateur`, `agent`,
    # `auteur`, `verrou_par` ni un en-tête `Remote-` (relevé le 2026-08-31).
    # Le compte a été retiré de cette phrase le 2026-09-09 : elle annonçait « ces huit-là »
    # devant DOUZE entrées. Un nombre posé au-dessus d'une liste où l'on ajoute vieillit
    # forcément, et il vieillit vers une phrase qui a encore du sens — donc que personne
    # ne relit. La liste se compte toute seule.
    ("outil", "importer_vocabulaire.py"): (
        "IMPORTE un tableur de vocabulaire : il écrit en base, et son compte rendu ne "
        "nomme que des termes."),
    ("outil", "reindex_materiel.py"): (
        "Maintenance : relit les masters et écrit `planches.dpi_*`/`mode`. Son compte "
        "rendu est un décompte de planches."),
    ("outil", "regenerer_derives.py"): (
        "Maintenance (IMG-1) : réécrit les dérivés JPEG depuis les masters, sans écrire "
        "en base. Son compte rendu est un décompte, des identifiants de planche et, en "
        "cas d'échec, le message de l'exception — un chemin de fichier au plus, jamais "
        "une colonne d'identité."),
    ("outil", "convertir_en_copies_de_travail.py"): (
        "Maintenance (IMG-1) : remplace les masters gardés par des copies de travail et "
        "écrit `planches.chemin_tiff`/`master_origine`. Son compte rendu est un décompte, "
        "des chemins de fichier, des identifiants de planche, des tailles et, en cas "
        "d'échec, le message de l'exception — jamais une colonne d'identité."),
    ("outil", "reindex_nlp.py"): (
        "Maintenance : régénère les tokens et l'index FTS. Son compte rendu est un "
        "décompte de régions."),
    ("outil", "normaliser_casse.py"): (
        "Maintenance (NLP-3) : normalise la casse des transcriptions et réindexe. Son "
        "compte rendu est un décompte, plus un APERÇU de huit répliques avant/après — donc "
        "du texte de bulle, jamais une colonne d'identité. C'est la seule de ces sorties "
        "qui recopie du contenu de corpus, et c'est voulu : on ne juge pas une règle de "
        "casse sur un chiffre. La passe se journalise en `agent_type='moteur'` sous le nom "
        "du LOGICIEL (`normalisation-casse`), jamais sous celui de qui la lance — la règle "
        "d'AUTH-1, « les moteurs gardent leur nom »."),
    ("outil", "semer_demo.py"): (
        "Sème un corpus de démonstration. Il écrit `albums.auteur` — l'AUTEUR DE LA BD, "
        "pas un annotateur : dans ce projet le mot désigne les deux, et c'est le seul "
        "endroit du balayage où la confusion pourrait rassurer à tort."),
    ("outil", "faux_proxy_auth.py"): (
        "Outil de DÉVELOPPEMENT : un faux proxy d'authentification, pour voir AUTH-2/3/4 "
        "fonctionner sans monter Authelia. Il n'ouvre jamais la base — il relaie du HTTP "
        "et POSE des en-têtes d'identité au lieu d'en lire. Les logins qu'il affiche "
        "(alice, bob, claire, admin) sont FICTIFS et codés en dur dans le fichier : "
        "aucun ne vient du corpus, et c'est ce qui le rend inoffensif pour ce cliquet-ci. "
        "Sa dangerosité est ailleurs, et elle est écrite en tête du fichier : devant une "
        "instance réelle il donnerait à quiconque l'identité de son choix."),
    ("outil", "identite_pile.py"): (
        "Rapporte l'identité de la PILE (QA-5) : version de Python, plateforme, empreintes "
        "des verrous, versions de paquets, état des moteurs, et le commit servi lu dans "
        "`BD_COMMIT`. Il n'ouvre JAMAIS la base — sa seule source est `importlib.metadata` "
        "et les fichiers de verrou du dépôt, donc aucune colonne d'identité ne peut le "
        "traverser. Le `commit` qu'il affiche est celui de l'ARTEFACT, pas d'une personne : "
        "c'est la même valeur que le panneau de version d'INFRA-10, déjà déclarée ailleurs "
        "dans ce cliquet."),
    ("outil", "mesurer_reflow.py"): (
        "Outil de CONSTAT (UX-7) : pilote un Chromium sur une instance DÉJÀ lancée et "
        "compare le rectangle de chaque élément à la largeur de la fenêtre. Il n'ouvre "
        "jamais la base, n'écrit rien, et ne rend que des dimensions en pixels — aucune "
        "colonne d'identité ne peut le traverser."),
    ("outil", "pdf_check.py"): (
        "Contrôle un PDF fourni en argument ; n'ouvre pas la base."),
    ("outil", "sharedocs_check.py"): (
        "Vérifie une connexion WebDAV ; n'ouvre pas la base."),
    ("outil", "verifier_moteurs.py"): (
        "Vérifie la présence des moteurs ML ; n'ouvre pas la base."),
    ("outil", "valider_iiif.py"): (
        "Valide des manifestes fournis en argument ; n'ouvre pas la base."),
    ("outil", "regenerer_exemples.py"): (
        "Écrit dans `docs/exemples/`, donc DANS le dépôt versionné — ce serait une voie de "
        "sortie majeure s'il lisait la base réelle. Il ne le fait jamais : il sème un "
        "corpus jetable (`semer_demo.py`) dans un dossier temporaire, et n'exporte que "
        "celui-là. Le balayer réécrirait `docs/exemples/` pendant la suite."),
    ("outil", "fabriquer_base_de_version.py"): (
        "Écrit une base de TEST dans le fichier qu'on lui nomme (`tests/bases/`), donc "
        "dans le dépôt versionné. Il ne lit jamais la base réelle : il extrait le code "
        "d'un commit dans un dossier temporaire et y joue un parcours sous trois comptes "
        "FICTIFS (hugo, lea, sam), codés en dur dans le fichier. Le balayer ferait "
        "tourner une autre version de l'application pendant la suite."),
}


# --------------------------------------------------------------------------- #
# Le balayage
# --------------------------------------------------------------------------- #
def _routes_get():
    """Les routes GET de l'app, par l'inventaire partagé (`inventaire_routes`, ARCH-2).

    C'était un `isinstance(r, APIRoute)` posé ici, et il a écarté 28 des 51 routes GET
    sans un mot le 2026-09-05 : FastAPI 0.137 n'aplatit plus les routeurs inclus dans
    `app.routes`, et l'objet paresseux qui les remplace n'est pas une `APIRoute`. Le
    cliquet a continué de passer en ne balayant plus que 23 surfaces sur 51 — dont plus
    aucune du domaine `analyse`, celui qui NOMME.
    """
    return sorted((r for r in inventaire_routes.routes_api() if "GET" in r.methods),
                  key=lambda r: r.path)


def _chemin_concret(gabarit: str, seme: dict):
    """Remplit les paramètres depuis le décor, ou None si on ne sait pas."""
    manque = []

    def sub(m):
        nom = m.group(1).split(":")[0]
        if nom not in seme:
            manque.append(nom)
            return ""
        return str(seme[nom])

    concret = re.sub(r"{([^}]+)}", sub, gabarit)
    return None if manque else concret


# Les paramètres de REQUÊTE sans lesquels une route refuse de répondre. Sans cette table,
# les trois routes d'export et deux routes d'analyse sortaient en 422 — c'est-à-dire que le
# balayage les comptait « non atteintes » alors qu'elles sont parmi les plus bavardes du
# lot. Un cliquet qui ne voit pas les exports ne vaut rien.
QUETES = {
    "/api/export/json": "album_id={album_id}",
    "/api/export/csv": "album_id={album_id}",
    "/api/export/tei": "album_id={album_id}",
    # `auteur` est un FILTRE de ces deux routes : elles savent trier par annotateur, donc
    # elles savent en parler. On les interroge sans le filtre — c'est le cas ordinaire.
    "/api/analyse/concordance": "lemme=otage",
    "/api/analyse/croisement": "axe_x=pos&axe_y=provenance",
    # ANA-7 — les exports CSV des vues d'analyse. Mêmes exigences que leurs jumelles
    # JSON, et pour la même raison : sans ces valeurs elles répondent 422 et quittent le
    # balayage. Ce sont les surfaces les plus bavardes du domaine — un fichier qu'on
    # emporte —, donc exactement celles qu'un cliquet doit voir.
    "/api/analyse/concordance.csv": "lemme=otage",
    "/api/analyse/croisement.csv": "axe_x=pos&axe_y=provenance",
    # EXP-1 — `base_url` n'a AUCUN défaut, et c'est délibéré : l'application ne peut pas
    # deviner quel serveur servira les images, et s'y désigner elle-même fabriquerait un
    # manifeste dont chaque image répond 404 chez le destinataire. Sans valeur ici, la
    # route répondrait 422 et quitterait le balayage — or c'est l'une des rares surfaces
    # qui publie les métadonnées d'album, et la SEULE destinée à sortir de l'instance.
    "/api/collections/{collection_id}/depot/iiif":
        "base_url=https://images.example.org/iiif",
    # COL-3, tranche 3b — l'aperçu d'« en partir » exige sa collection d'arrivée et son
    # cran, sans défaut : sans eux, 422, et la route quitterait le balayage. Au cran le
    # plus haut, elle compte tout ce qu'une copie emporterait.
    "/api/albums/{album_id}/amorcer/apercu": "collection={collection_id}&cran=annotations",
}


# Les routes qui ne parlent que sur une collection de BASE : balayées sur elle, et non sur
# la collection de l'album, où elles rendraient une liste vide (COL-3, écran de la 3a).
SUR_LA_BASE = {"/api/collections/{collection_id}/acces-du-projet"}


def _balayer_routes(client, seme) -> dict:
    vus = {}
    for r in _routes_get():
        cle = ("route", r.path)
        decor = {**seme, "collection_id": seme["base_id"]} if r.path in SUR_LA_BASE else seme
        chemin = _chemin_concret(r.path, decor)
        if chemin is None:
            continue                                    # → exigé dans NON_BALAYE
        if r.path in QUETES:
            chemin += "?" + QUETES[r.path].format(**seme)
        rep = client.get(chemin, headers=seme["ident"])
        if rep.status_code >= 400:
            continue                                    # → exigé dans NON_BALAYE
        vus[cle] = _sortes(rep.content)
    return vus


def _outils():
    return sorted(p.name for p in TOOLS.glob("*.py"))


# --------------------------------------------------------------------------- #
# Ce qu'un EXTRA absent empêche de balayer (ARCH-2)
# --------------------------------------------------------------------------- #
# Deux invocations exigent `openpyxl`, qui vit dans `requirements-export.txt` et n'est pas
# du noyau. Sans lui, l'outil sort en erreur — et c'est son BON comportement, pas une
# régression. La convention du dépôt est de skipper proprement une dépendance optionnelle
# (`requires_kumiko` / `requires_bulles` / `requires_ocr`) ; ces trois tests ÉCHOUAIENT, ce
# qui apprend la mauvaise chose : un rouge sur un extra absent fait chercher un bug qui
# n'existe pas. `requirements-dev.lock` l'annonçait d'ailleurs déjà — « sans lui, des tests
# d'export se skippent ».
#
# Le skip est CIBLÉ, et pas porté sur le test entier. Ce cliquet ne vaut que par son
# exhaustivité : le mettre en pause parce qu'un tableur manque le rendrait muet sur les dix
# AUTRES invocations — le journal, la provenance, les métadonnées, le crosswalk. Il balaie
# donc ce qu'il peut, et le dernier test du fichier AFFICHE ce qu'il n'a pas vu : un
# cliquet partiel qui se taît est un cliquet qui rassure à tort. La contrepartie est
# écrite : sur une machine sans l'extra, une déclaration périmée
# de ces deux surfaces survivrait au contrôle (1) ci-dessous. Elle ne survit pas dans
# l'image, qui installe `requirements-dev.lock` — et l'image est l'artefact livré (QA-5).
SANS_EXTRA = {
    "dictionnaire_xlsx.py --out": "openpyxl",
    "metadonnees_collection.py --xlsx": "openpyxl",
}


def _extra_absent(surface: str):
    """Le nom de l'extra manquant qui empêche de balayer cette surface, ou None."""
    extra = SANS_EXTRA.get(surface)
    if extra and importlib.util.find_spec(extra) is None:
        return extra
    return None


# Comment invoquer ce qui PRODUIT quelque chose. Une entrée = une SORTIE et non un outil :
# `metadonnees_collection.py` en a trois — le JSON, les CSV et l'onglet XLSX — et c'est
# précisément la troisième qui a échappé à quatre inventaires. Regrouper par outil
# reproduirait l'angle mort dans le cliquet censé le fermer.
#
# Un outil absent d'ici doit figurer dans NON_BALAYE avec sa raison : celui qui n'exporte
# rien le DIT, il ne s'absente pas — sans quoi un exportateur neuf entrerait sans être
# regardé, ce qui est exactement l'histoire d'AUTH-1.
def _invocations(t):
    """(surface, outil, arguments, chemins produits à relire)."""
    return [
        ("crosswalk_depot.py --out-dir", "crosswalk_depot.py",
         ["--out-dir", str(t / "cw")], [t / "cw"]),
        ("description_collection.py --json", "description_collection.py",
         ["--json", "-"], []),
        ("description_collection.py --csv", "description_collection.py",
         ["--csv", str(t / "fiche.csv")], [t / "fiche.csv"]),
        ("dictionnaire_xlsx.py --out", "dictionnaire_xlsx.py",
         ["--out", str(t / "dico.xlsx")], [t / "dico.xlsx"]),
        ("gerer_collections.py lister", "gerer_collections.py", ["lister"], []),
        ("iiif_manifest.py --out-dir", "iiif_manifest.py",
         ["--base-url", "http://exemple/iiif", "--out-dir", str(t / "iiif")], [t / "iiif"]),
        ("metadonnees_collection.py --json", "metadonnees_collection.py",
         ["--json", "-"], []),
        ("metadonnees_collection.py --csv-dir", "metadonnees_collection.py",
         ["--csv-dir", str(t / "csv")], [t / "csv"]),
        ("metadonnees_collection.py --xlsx", "metadonnees_collection.py",
         ["--xlsx", str(t / "m.xlsx")], [t / "m.xlsx"]),
        # SEC-3 — il ne lit ni la base ni le corpus : il croise les verrous du dépôt avec
        # les métadonnées des paquets INSTALLÉS. Balayé quand même, parce que « ne devrait
        # rien émettre » est exactement ce qu'on croyait des trois chemins de
        # `metadonnees_collection` avant qu'un `KeyError` n'en trouve un quatrième.
        ("plafonds_dependances.py", "plafonds_dependances.py", [], []),
        ("provenance_export.py --out-dir", "provenance_export.py",
         ["--out-dir", str(t / "prov")], [t / "prov"]),
        ("rapport_accord.py --json", "rapport_accord.py",
         ["--json", str(t / "acc.json")], [t / "acc.json"]),
        ("rapport_accord_inter.py --json", "rapport_accord_inter.py",
         ["--json", str(t / "inter.json")], [t / "inter.json"]),
    ]


def _balayer_outils(seme, tmp_path) -> dict:
    vus = {}
    env = {**os.environ, "BD_DB_PATH": str(seme["db"]),
           "BD_DATA_DIR": str(seme["data"])}
    for surface, outil, args, sorties in _invocations(tmp_path):
        if _extra_absent(surface):
            continue                       # cf. SANS_EXTRA — non balayée, et pas en panne
        p = subprocess.run([sys.executable, str(TOOLS / outil), *args],
                           cwd=str(REPO_ROOT), env=env, capture_output=True)
        assert p.returncode == 0, (surface, p.stderr.decode("latin-1")[-900:])
        blobs = [p.stdout, p.stderr]
        for chemin in sorties:
            c = Path(chemin)
            blobs += ([c.read_bytes()] if c.is_file()
                      else [f.read_bytes() for f in c.glob("**/*") if f.is_file()])
        vus[("outil", surface)] = frozenset().union(*(_sortes(b) for b in blobs))
    return vus


# --------------------------------------------------------------------------- #
# Les cliquets
# --------------------------------------------------------------------------- #
def test_aucune_sortie_d_identite_n_est_ignoree(client, seme, tmp_path):
    """Toute surface qui laisse partir une identité l'a DÉCLARÉ, avec sa raison écrite.

    Le cliquet ne dit pas qu'une sortie est légitime — il dit qu'elle a été VUE. C'est la
    même limite que `test_autorisation.py`, qui vérifie qu'une route consulte la portée
    sans jamais vérifier qu'elle en tire la bonne conclusion.
    """
    vus = {**_balayer_routes(client, seme), **_balayer_outils(seme, tmp_path)}
    fautes = []
    for cle, sortes in sorted(vus.items()):
        declare = SORTIES_DECLAREES.get(cle, (frozenset(), None))[0]
        surprise = sortes - set(declare)
        if surprise:
            fautes.append(f"{cle[0]} {cle[1]} laisse sortir {sorted(surprise)} "
                          f"sans l'avoir déclaré")
    assert not fautes, (
        "Des identités sortent par des surfaces qui ne l'ont pas déclaré.\n  "
        + "\n  ".join(fautes)
        + "\n\nSoit la surface cesse de les émettre, soit elle entre dans "
          "SORTIES_DECLAREES avec la SORTE émise et sa raison. Écrire la raison EST le "
          "travail : c'est elle qui transforme un oubli en décision.")


def test_les_declarations_ne_mentent_pas(client, seme, tmp_path):
    """Une liste périmée est pire qu'absente : elle rassure.

    Trois mensonges possibles, et le troisième est celui qui a coûté quatre inventaires à
    AUTH-1 : une surface qui n'est ni balayée ni déclarée hors balayage passe inaperçue.
    """
    vus = {**_balayer_routes(client, seme), **_balayer_outils(seme, tmp_path)}
    fautes = []

    # (1) Une déclaration qui annonce une sorte que la surface n'émet plus.
    for cle, (sortes, raison) in sorted(SORTIES_DECLAREES.items()):
        assert raison, f"{cle} est déclarée sans raison écrite"
        if cle not in vus:
            if cle[0] == "outil" and _extra_absent(cle[1]):
                continue      # non balayée faute d'un extra, pas disparue — cf. SANS_EXTRA
            fautes.append(f"{cle[0]} {cle[1]} est déclarée mais n'est plus balayée")
        elif set(sortes) - vus[cle]:
            fautes.append(f"{cle[0]} {cle[1]} déclare {sorted(set(sortes) - vus[cle])} "
                          f"qu'elle n'émet plus — à retirer de la déclaration")

    # (2) Un trou déclaré qui n'existe plus.
    #
    # ATTENTION à la clé, et c'est un piège que ce test s'était tendu à lui-même : sous le
    # même préfixe `("outil", …)`, `SORTIES_DECLAREES` range des SORTIES
    # (« metadonnees_collection.py --xlsx ») tandis que `NON_BALAYE` range des OUTILS
    # entiers (« pdf_check.py »). Un `cle in vus` naïf ne pouvait donc jamais être vrai
    # pour un outil : le jour où l'un d'eux deviendrait exportateur, sa raison périmée
    # (« ne touche pas la base ») aurait survécu en silence, et le contrôle (3) l'aurait
    # laissée passer puisqu'il est désormais couvert. Le mensonge que ce test traque,
    # exactement, dans le test qui le traque.
    couverts = {o for _, o, _, _ in _invocations(tmp_path)}
    for cle, raison in sorted(NON_BALAYE.items()):
        assert raison, f"{cle} est hors balayage sans raison écrite"
        atteinte = cle[1] in couverts if cle[0] == "outil" else cle in vus
        if atteinte:
            fautes.append(f"{cle[0]} {cle[1]} est balayée maintenant : "
                          f"la retirer de NON_BALAYE")

    # (3) Une surface ni balayée ni déclarée hors balayage — le trou INVISIBLE.
    attendus = ([("route", r.path) for r in _routes_get()]
                + [("outil", o) for o in _outils()])
    for cle in attendus:
        if cle[0] == "outil":
            if cle[1] in couverts or cle in NON_BALAYE:
                continue
        elif cle in vus or cle in NON_BALAYE:
            continue
        fautes.append(f"{cle[0]} {cle[1]} n'est ni balayée ni déclarée hors balayage")

    assert not fautes, (
        "Les listes du cliquet ne décrivent plus la réalité.\n  "
        + "\n  ".join(fautes))


def test_l_inventaire_des_routes_get_n_a_pas_retreci():
    """Le balayage doit ÉCHOUER quand il cesse de voir les surfaces, pas raccourcir.

    Les trois cliquets de ce fichier partent tous de `_routes_get()`. Aucun ne pose de
    question à une route qui n'est pas dans cette liste — donc aucun ne peut se plaindre
    d'une liste qui rétrécit. Le 2026-09-05, elle est passée de 51 à 23 sans un mot :
    FastAPI 0.137 a cessé d'aplatir les routeurs inclus dans `app.routes`, et le filtre
    `isinstance(r, APIRoute)` posé ici a écarté tout ce qui en venait — dont le domaine
    `analyse` en entier, celui dont une route NOMME les annotateurs et cite à la ligne.

    Le plancher se dérive du source par AST (`inventaire_routes.plancher_source`), et non
    d'un chiffre écrit ici. Ce fichier avait justement un chiffre écrit (`len(vus) >= 55`) :
    il visait la bonne chose et il aurait tiré, mais il vivait DERRIÈRE le balayage, qu'un
    extra absent faisait mourir avant. Un plancher ne protège que ce qui le précède.
    """
    inventaire_routes.exiger_plancher(len(_routes_get()),
                                      "le cliquet des sorties d'identité (AUTH-5)",
                                      methode="get")


def test_les_exemptions_d_extra_visent_des_surfaces_reelles(tmp_path):
    """Une exemption qui vise une surface disparue dormirait en rassurant.

    Même mensonge que celui du contrôle (2) plus haut, sur la liste d'à côté : le jour où
    `--xlsx` change de nom ou d'outil, `SANS_EXTRA` cesserait d'exempter quoi que ce soit,
    et le rouge reviendrait sans qu'on comprenne pourquoi l'exemption ne joue plus.
    """
    surfaces = {s for s, *_ in _invocations(tmp_path)}
    inconnues = sorted(set(SANS_EXTRA) - surfaces)
    assert not inconnues, (
        f"{inconnues} figurent dans SANS_EXTRA mais ne sont plus des invocations : "
        "l'exemption ne s'applique à rien. La retirer, ou corriger le libellé.")


def test_le_skip_d_extra_retire_exactement_les_surfaces_visees(monkeypatch, tmp_path):
    """Le skip doit jouer sur une machine sans l'extra, et NE PAS jouer sur une avec.

    Il ne se vérifie pas en regardant la machine qui lance la suite : celle-ci a l'extra la
    moitié du temps, et un skip qu'on ne peut éprouver que par accident d'environnement
    n'est pas éprouvé. On simule donc les deux réponses de `find_spec` — c'est le seul
    endroit où la décision se prend.

    L'exigence est une ÉGALITÉ et non une inclusion : un skip qui retirerait une surface de
    plus que `SANS_EXTRA` rendrait le balayage silencieusement plus court, ce qui est la
    faute entière d'ARCH-2.
    """
    monkeypatch.setattr(importlib.util, "find_spec", lambda nom: None)
    assert {s for s, *_ in _invocations(tmp_path) if _extra_absent(s)} == set(SANS_EXTRA)

    monkeypatch.setattr(importlib.util, "find_spec", lambda nom: object())
    assert not [s for s, *_ in _invocations(tmp_path) if _extra_absent(s)]


def test_le_balayage_dit_ce_qu_il_n_a_pas_vu(capsys):
    """N'échoue pas : AFFICHE les surfaces qu'un extra absent empêche de balayer.

    Un cliquet partiel qui se taît est un cliquet qui rassure à tort — c'est la leçon
    entière d'ARCH-2, où deux gardes ont approuvé la moitié d'un contrat sans le dire. Le
    skip ciblé de `SANS_EXTRA` est justifié, mais il ne doit pas être silencieux : sur une
    machine sans l'extra, ces surfaces ne sont regardées par personne jusqu'à ce que
    l'image tourne.
    """
    manquants = {s: e for s in SANS_EXTRA if (e := _extra_absent(s))}
    with capsys.disabled():
        if manquants:
            print("\n  AUTH-5 — balayage PARTIEL, "
                  f"{len(manquants)} surface(s) non regardée(s) :")
            for surface, extra in sorted(manquants.items()):
                print(f"    {surface} — `{extra}` absent "
                      "(pip install -r requirements-export.txt)")
        else:
            print(f"\n  AUTH-5 — balayage complet, {len(_invocations(Path('.')))} "
                  "invocations d'outils")


def test_le_semis_est_visible(client, seme, tmp_path):
    """Le mode d'échec d'un cliquet est son SEMIS, jamais son balayage.

    Une sentinelle absente d'une colonne rend muette toute surface qui ne lit que cette
    colonne, et le vert devient un mensonge. Même famille que les deux assertions vacantes
    trouvées le 2026-08-31 : une non-vacuité prouvée sur l'ensemble, un `stdout` vide parce
    que l'outil écrivait dans un fichier. Si personne ne voit passer une sentinelle, c'est
    le décor qui est faux, pas le code qui est propre.
    """
    vus = {**_balayer_routes(client, seme), **_balayer_outils(seme, tmp_path)}
    aperçues = frozenset().union(*vus.values()) if vus else frozenset()
    assert aperçues == set(SENTINELLES), (
        f"sentinelles jamais vues passer : {sorted(set(SENTINELLES) - aperçues)} — "
        "le semis ne les place nulle part, ou le balayage ne lit pas la surface qui les "
        "porte. Un cliquet qui ne voit rien est vert pour la mauvaise raison.")
    # Le plancher du balayage, DÉRIVÉ (ARCH-2). C'était `>= 55`, un chiffre recopié — et
    # il avait raison : sous FastAPI 0.137, le balayage tombait à 33 surfaces, donc il
    # aurait tiré. Il n'a pas tiré parce qu'`openpyxl` manquait : `_balayer_outils` mourait
    # sur la quatrième invocation, bien avant cette ligne. Les deux constats d'ARCH-2 ne
    # sont pas indépendants — le second a étouffé le seul plancher que le dépôt avait déjà.
    #
    # Dérivé, il ne peut plus vieillir dans le sens permissif : toute route GET qui n'est
    # pas déclarée hors balayage DOIT être balayée, et toute invocation qui ne bute pas sur
    # un extra absent aussi.
    attendues = (sum(1 for r in _routes_get() if ("route", r.path) not in NON_BALAYE)
                 + sum(1 for s, *_ in _invocations(tmp_path) if not _extra_absent(s)))
    assert len(vus) >= attendues, (
        f"balayage anormalement court : {len(vus)} surfaces vues pour {attendues} "
        "attendues. Une surface qui répond 4xx ou dont les paramètres ne se remplissent "
        "pas doit entrer dans NON_BALAYE avec sa raison, jamais disparaître du compte.")


def test_une_lectrice_lit_la_demande_sans_le_nom(client, seme):
    """Le balayage mesure l'exposition MAXIMALE — sa sentinelle est administratrice. Pour
    `/api/albums`, la déclaration promet MOINS à tout autre lecteur : la demande de
    suppression s'y lit, son auteur non (Hugo, 2026-10-15). Ce test joue la même liste,
    sur le même semis, sous une lectrice de la collection, et exige que ni le login, ni le
    nom, ni le courriel de la sentinelle n'en sortent — ET que la demande y soit, sans
    quoi le silence viendrait d'une liste vide et non de la règle."""
    r = client.put(f"/api/collections/{seme['collection_id']}/acces", headers=seme["ident"],
                   json={"genre": "utilisateur", "principal": "zzlectrice7",
                         "niveau": "lecture"})
    assert r.status_code in (200, 201), r.text
    rep = client.get("/api/albums", headers={"Remote-User": "zzlectrice7"})
    assert rep.status_code == 200, rep.text
    ligne = {a["id"]: a for a in rep.json()}[seme["album_id"]]
    assert ligne["demande"] is not None, "le semis ne pose pas de demande sur cet album"
    assert _sortes(rep.content) == frozenset(), _sortes(rep.content)
    # Et l'envers, sur le même semis : la sentinelle se lit elle-même.
    assert {"login", "nom"} <= _sortes(client.get("/api/albums",
                                                  headers=seme["ident"]).content)


def test_le_semis_ne_double_pas_le_token(seme):
    """Le token auto du semis existe, et il n'existe QU'UNE FOIS (QA-6, 2026-09-05).

    Deux configurations, un seul état attendu. Avec le modèle spaCy, c'est le pipeline qui
    pose la ligne `tokens` et le semis ne doit rien ajouter ; sans modèle, `tokens` reste
    vide et le semis est le seul à la poser — faute de quoi la correction sentinelle ne se
    voit NULLE PART, `tokens_effectifs` partant `FROM tokens`.

    Le doublon est le risque précis de cette réparation, et il est SILENCIEUX : `tokens`
    n'a pas d'unicité sur (region_id, ordre), donc rien ne lèverait — l'accord
    modèle↔humain, la concordance et le « % relu » d'ANN-4 compteraient simplement deux
    tokens là où le corpus en a un. C'est pourquoi le compte est vérifié ici plutôt que
    laissé à la lecture du SQL.
    """
    conn = sqlite3.connect(seme["db"])
    conn.row_factory = sqlite3.Row
    try:
        auto = conn.execute(
            "SELECT COUNT(*) AS n FROM tokens WHERE region_id = ? AND ordre = 0",
            (seme["region_id"],)).fetchone()["n"]
        effectifs = [r["corr_auteur"] for r in conn.execute(
            "SELECT corr_auteur FROM tokens_effectifs WHERE region_id = ? AND ordre = 0",
            (seme["region_id"],)).fetchall()]
    finally:
        conn.close()

    assert auto == 1, (
        f"{auto} token auto sur (region, ordre 0) — attendu exactement 1. À 0 la "
        "correction sentinelle est invisible et le cliquet croit la déclaration périmée ; "
        "au-delà, le semis double la ligne que spaCy pose déjà.")
    assert effectifs == [SENTINELLES["login"]], (
        f"tokens_effectifs rend {effectifs} — attendu la seule correction sentinelle. "
        "C'est le read model que lisent toutes les surfaces d'analyse : ce qu'il compte "
        "ici, elles le comptent partout.")


def test_toute_colonne_exportable_est_classee(client, db_path):
    """`GET /api/export/json` NOMME ce qu'il publie, et le reste est retenu AVEC sa raison.

    Il faisait `SELECT *` sur `albums` et `planches` : 34 colonnes dont personne n'avait
    décidé la publication, dont `verrou_par` — qui tient un verrou d'édition, un état de
    travail transitoire, dans un artefact destiné à un entrepôt qui garde ses versions.

    Le défaut n'était pas la fuite mais le MÉCANISME : une colonne ajoutée à `planches` se
    publiait toute seule, par défaut et non par décision. Ce test le referme — une colonne
    neuve fait échouer la suite tant que personne ne l'a classée, publiée ou retenue.
    """
    import sqlite3 as _sq
    conn = _sq.connect(db_path)
    try:
        reel = {t: {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
                for t in ("albums", "planches")}
    finally:
        conn.close()

    # COL-3 (v30) — `albums` a désormais SES retenues : jusque-là toutes ses colonnes étaient
    # descriptives, et la liste publiée suffisait à la classer.
    retenues = {"albums": main._EXPORT_ALBUM_RETENUES,
                "planches": main._EXPORT_PLANCHE_RETENUES}
    classees = {
        "albums": set(main._EXPORT_ALBUM_COLS) | set(retenues["albums"]),
        "planches": set(main._EXPORT_PLANCHE_COLS) | set(retenues["planches"]),
    }
    for table, colonnes in reel.items():
        neuves = colonnes - classees[table]
        assert not neuves, (
            f"{table} : {sorted(neuves)} n'est ni publiée ni retenue. Ajoute la colonne à "
            f"_EXPORT_{table[:-1].upper()}_COLS si elle est descriptive, ou à "
            f"_EXPORT_{table[:-1].upper()}_RETENUES avec sa raison. Ne rien faire la "
            "publierait.")
        fantomes = classees[table] - colonnes
        assert not fantomes, (
            f"{table} : {sorted(fantomes)} est classée mais n'existe plus — "
            "une liste périmée rassure.")

    for table, liste in retenues.items():
        for col, raison in liste.items():
            assert raison and len(raison) > 20, f"{table}.{col} est retenue sans raison écrite"

    # Publiée ET retenue : la colonne passait les deux contrôles ci-dessus — elle est
    # classée, deux fois — et partait au dépôt avec sa raison de ne pas partir.
    doubles = set(main._EXPORT_PLANCHE_COLS) & set(main._EXPORT_PLANCHE_RETENUES)
    assert not doubles, (
        f"planches : {sorted(doubles)} est à la fois publiée et retenue. Les deux listes "
        "se contredisent, et c'est la liste publiée qui gagne à l'export.")
    doubles = set(main._EXPORT_ALBUM_COLS) & set(main._EXPORT_ALBUM_RETENUES)
    assert not doubles, (
        f"albums : {sorted(doubles)} est à la fois publiée et retenue. Les deux listes "
        "se contredisent, et c'est la liste publiée qui gagne à l'export.")


# --------------------------------------------------------------------------- #
# Ce qui est RETENU ne sort d'aucun export d'album (AUTH-11)
# --------------------------------------------------------------------------- #
# Le cliquet ci-dessus compare le SCHÉMA à deux listes de `main` : il dit qu'une colonne a
# été classée, jamais qu'un export tient le classement. Il ne joue aucun export — et le
# TEI n'employait pas ces listes : il lisait `SELECT *` et choisissait ses champs à la
# main. `chemin_web` a donc été RETENUE avec sa raison écrite, le cliquet vert, pendant que
# le TEI du même album l'écrivait dans un `<graphic url>` (relevé le 2026-10-07).
#
# Ce qui suit mesure la SORTIE, par trois recherches qui ne se recouvrent pas :
#   - la VALEUR semée dans chaque colonne retenue (ce qu'un export LIT en base) ;
#   - les formes du chemin RÉEL que l'import a écrit, relevées avant le semis (ce qu'un
#     export RECONSTRUIT depuis l'album et le numéro, deux valeurs publiées) ;
#   - le NOM d'une colonne retenue (ce qu'un export en dit sans en donner la valeur :
#     `"verrouillee": true`).
# Et par un inventaire de ce qui PORTE une planche, là où elle a un porteur à elle : les
# clés de son objet JSON, les attributs et les enfants de sa `<surface>` TEI. Un porteur
# neuf se déclare, quoi qu'il porte.
#
# **Ce qu'elle ne voit pas, et qu'il ne faut pas lui prêter.** Une valeur TRANSFORMÉE —
# hachée, encodée en base64, tronquée, traduite (`type="locked"`) — ne ressemble plus à
# rien de ce qu'on cherche : aucune recherche par valeur ne la verra, et l'inventaire ne
# la voit que si elle arrive par un porteur NEUF de la planche. Dans un porteur qui existe
# déjà (un attribut déclaré, le texte d'une note, une cellule du CSV), ou dans une colonne
# neuve du CSV — dont les lignes sont des régions, que ce contrôle n'inventorie pas —,
# elle passe. Un chemin reconstruit sous une AUTRE forme que celle de l'ingestion passe de
# même. Le décor exerce les branches que les trois exports ONT (récit et paratexte,
# surface vide, zone nue, zone enfant, texte, note avec et sans tag), pas celles qu'on
# leur ajoutera : une fuite posée sous une condition neuve demande que le décor la
# remplisse. Ne sont jouées que les routes GET sous `/api/export/`.
EXPORTS_D_ALBUM = "/api/export/"
TROIS_FORMATS = {"/api/export/json", "/api/export/csv", "/api/export/tei"}

# Ce que le décor PUBLIE, et que chaque export doit donc porter : la preuve que le lecteur
# lit ce qui sort, et que chaque branche du décor atteint le fichier.
TITRE_PUBLIE = "ZZTITRE-PUBLIE-7"
PUBLIES = {
    "le titre de l'album": TITRE_PUBLIE,
    "le texte de la bulle enfant": "ZZTEXTE-BULLE-7",
    "sa note": "ZZNOTE-AVEC-TAG-7",
    "son tag": "zztag7",
    "le texte du cartouche de la planche paratexte": "ZZTEXTE-PARATEXTE-7",
    "sa note, sans tag": "ZZNOTE-SEULE-7",
}
# Ce qui PORTE une planche dans un export, déclaré. C'est sous un porteur neuf qu'une
# colonne retenue sortirait transformée — `"verrou": true`, `subtype="locked"`, un
# `<graphic>` au chemin haché — sans rien qui ressemble à ce qu'on cherche.
#   - JSON : les clés d'une planche, EN PLUS de ses colonnes publiées — dérivées de
#     colonnes publiées, ou l'arbre de ses régions ;
#   - TEI : les attributs d'une `<surface>` (dimensions du master, identifiant, numéro
#     éditorial ou paratexte) et ses enfants (ses zones, rien d'autre).
# Le CSV n'a pas de porteur de planche : ses lignes sont des RÉGIONS, hors de ce contrôle.
DERIVEES_PLANCHE = {"numero_editorial", "dimensions_cm", "regions"}
ATTRIBUTS_SURFACE = {"ulx", "uly", "lrx", "lry", "xml:id", "n", "type"}
ENFANTS_SURFACE = {"zone"}


def _jetons_retenus() -> dict:
    """{colonne retenue: (jeton de dossier, jeton de fichier)} — DÉRIVÉ de la liste retenue.

    Dérivé, pour qu'une colonne retenue demain soit semée sans que personne y pense : une
    table écrite ici à la main oublierait ce qu'on ajoute, et la colonne oubliée passerait
    pour propre faute d'avoir jamais porté de valeur à chercher.

    DEUX jetons, parce que deux des quatre colonnes sont des chemins et qu'un chemin fuit
    aussi par MORCEAUX : le nom du fichier sans son dossier, le dossier sans son fichier.
    Rien que des lettres minuscules et des chiffres : ni un XML, ni un JSON, ni une URL ne
    les échappe, et une réécriture des séparateurs (tirets en soulignés) ne les entame pas.
    Le jeton ne contient PAS le nom de sa colonne, que `_noms_retenus_dans` cherche à part.
    """
    return {col: (f"zzretenue{i}dossier7", f"zzretenue{i}fichier7")
            for i, col in enumerate(sorted(main._EXPORT_PLANCHE_RETENUES))}


def _retenues_dans(texte: str) -> set:
    """Les colonnes retenues dont un jeton se lit dans ce texte, casse ignorée."""
    t = texte.lower()
    return {col for col, jetons in _jetons_retenus().items() if any(j in t for j in jetons)}


def _noms_retenus_dans(texte: str) -> set:
    """Les colonnes retenues NOMMÉES dans ce texte : clé JSON, en-tête CSV, nom ou valeur
    d'attribut du TEI. Une colonne dite sans sa valeur — `"verrouillee": true` — sort
    quand même : c'est l'état que la liste retient, pas son horodatage."""
    t = texte.lower()
    return {col for col in main._EXPORT_PLANCHE_RETENUES if col.lower() in t}


def _formes_d_un_chemin(chemin: str) -> set:
    """Ce qu'un chemin RÉEL laisse reconnaître de lui : entier, puis par morceaux.

    Les morceaux se DÉRIVENT du chemin que l'import vient d'écrire, jamais d'un motif
    recopié ici : un motif diverge du code sans que rien le dise, et la recherche
    deviendrait vraie par construction. `derivatives/album_1/planche_0001.jpg` rend le
    chemin, sa racine (`derivatives/`), son dossier d'album (`album_1/`), son fichier
    (`planche_0001.jpg`) et ce fichier sans extension (`planche_0001`, pour un chemin
    reconstruit sous une autre extension).
    """
    segments = chemin.split("/")
    fichier = segments[-1]
    return {f.lower() for f in ({chemin, fichier, fichier.rsplit(".", 1)[0]}
                                | {s + "/" for s in segments[:-1]})}


def _formes_dans(texte: str, formes: set) -> set:
    t = texte.lower()
    return {f for f in formes if f in t}


def _local(nom: str) -> str:
    """`{espace}nom` → `nom`, et `xml:id` pour l'espace XML : comme on l'écrit."""
    espace, _, local = nom.rpartition("}")
    return ("xml:" if espace.endswith("XML/1998/namespace") else "") + local


def _branches_du_tei(racine) -> dict:
    """Les branches du TEI que le décor doit EXERCER, lues dans l'arbre et non dans sa
    sérialisation : sans elles, un `<graphic>` posé sur les seules planches paratexte, ou
    sur les seules zones enfants, ne rencontrait personne. Lues dans l'arbre pour qu'une
    fuite ne les fasse pas tomber À SA PLACE — une surface « sans zone » le reste quand on
    lui ajoute un `<graphic>`, et c'est la recherche de la fuite qui doit le dire."""
    def de(nom):
        return [e for e in racine.iter() if _local(e.tag) == nom]

    surfaces, zones, notes = de("surface"), de("zone"), de("note")
    return {
        "une surface paratexte": any(s.get("type") == "paratexte" for s in surfaces),
        "une surface de récit": any(s.get("n") for s in surfaces),
        "une surface sans zone": any(not [c for c in s if _local(c.tag) == "zone"]
                                     for s in surfaces),
        "une zone nue": any(len(z) == 0 for z in zones),
        "une zone dans une zone": any(_local(c.tag) == "zone" for z in zones for c in z),
        "une ligne de texte": bool(de("line")),
        "une note avec tags": any(n.get("ana") for n in notes),
        "une note sans tag": any(not n.get("ana") for n in notes),
    }


def test_aucune_colonne_retenue_ne_sort_d_un_export_d_album(client, db_path, data_dir,
                                                           png_bytes):
    """Les exports d'un album — JSON, CSV, TEI — tiennent la MÊME règle, mesurée à la sortie.

    Rouge avant le correctif du TEI : `<graphic url="/derivatives/…">` portait `chemin_web`.
    Les routes sont ÉNUMÉRÉES (toute route GET sous `/api/export/`) : un quatrième format
    est joué le jour où il arrive, et s'il ne se laisse pas jouer avec le seul `album_id`,
    il fait échouer au lieu de quitter le contrôle.
    """
    jetons = _jetons_retenus()

    # Les jetons se DÉRIVENT de la liste retenue : une colonne qu'on en sort n'est plus
    # cherchée nulle part. Pour les deux chemins, c'est une DÉCISION et non un rangement —
    # publier un chemin, c'est le publier dans les trois formats — et la façon la plus
    # courte de faire taire ce contrôle. Elle se prend donc ici, à voix haute.
    assert {"chemin_tiff", "chemin_web"} <= set(jetons), (
        "un chemin de fichier n'est plus RETENU par l'export d'album : s'il devient "
        "publiable, c'est une décision à écrire (la raison dans `main.py`, et ce que "
        "`docs/dictionnaire-metadonnees.md` dit de la colonne), pas une ligne à déplacer.")

    # (1) Le décor. Trois planches, pour que chaque branche des exports rencontre quelque
    # chose : une de récit (une case qui contient une bulle avec texte, note et tag, et
    # une case NUE), une de paratexte (un cartouche avec texte et une note sans tag), une
    # de récit sans aucune région. Le décor d'origine — une planche, une case nue —
    # laissait passer toute fuite posée sous une condition : sur les seules planches
    # paratexte, sur les seules zones qui ont un texte, dans une note, sur les seules
    # zones enfants.
    a = client.post("/api/albums", json={"titre": TITRE_PUBLIE}).json()

    def importer(nom):
        return client.post(f"/api/albums/{a['id']}/import",
                           files={"file": (nom, png_bytes, "image/png")}).json()

    def region(planche, **champs):
        rep = client.post(f"/api/planches/{planche['id']}/regions",
                          json={"x": 0, "y": 0, "w": 9, "h": 9, **champs})
        assert rep.status_code in (200, 201), rep.text
        return rep.json()

    recit, paratexte, vide = importer("p1.png"), importer("p2.png"), importer("p3.png")
    case = region(recit, type="case")
    region(recit, type="case", x=20)          # NUE : ni texte, ni note, ni enfant
    bulle = region(recit, type="bulle", parent_id=case["id"],
                   ocr_texte=PUBLIES["le texte de la bulle enfant"])
    cartouche = region(paratexte, type="cartouche",
                       ocr_texte=PUBLIES["le texte du cartouche de la planche paratexte"])
    for rid, corps in ((bulle["id"], {"note": PUBLIES["sa note"], "tags": [PUBLIES["son tag"]]}),
                       (cartouche["id"], {"note": PUBLIES["sa note, sans tag"], "tags": []})):
        rep = client.put(f"/api/regions/{rid}/annotation", json=corps)
        assert rep.status_code == 200, rep.text
    rep = client.patch(f"/api/planches/{paratexte['id']}/role", json={"role": "paratexte"})
    assert rep.status_code == 200, rep.text
    ids = [recit["id"], paratexte["id"], vide["id"]]

    conn = sqlite3.connect(db_path)
    try:
        # (2) Les chemins RÉELS, relevés avant que le semis ne les recouvre. Ce sont ceux
        # que l'ingestion a écrits — le dérivé est sur le disque à cet endroit —, donc ceux
        # qu'un export retrouverait sans lire la colonne : `album_id` et `numero` suffisent
        # à les reconstruire, et le JSON publie les deux.
        reels = [c for ligne in conn.execute(
            "SELECT chemin_tiff, chemin_web FROM planches WHERE album_id = ?", (a["id"],))
            for c in ligne if c]
        derives = [r[0] for r in conn.execute(
            "SELECT chemin_web FROM planches WHERE album_id = ?", (a["id"],))]
        assert len(derives) == 3 and all((data_dir / d).is_file() for d in derives), (
            f"les chemins relevés ne sont pas ceux que l'import a écrits : {derives}")
        assert len(reels) == 6, f"un master ou un dérivé manque au décor : {reels}"
        formes = set().union(*(_formes_d_un_chemin(c) for c in reels))

        # (3) Le semis : CHAQUE colonne retenue de CHAQUE planche porte sa valeur.
        for col, (dossier, fichier) in jetons.items():
            conn.execute(f"UPDATE planches SET {col} = ? WHERE album_id = ?",
                         (f"{dossier}/{fichier}.jpg", a["id"]))
        conn.commit()
        en_base = {pid: dict(zip(jetons, conn.execute(
            f"SELECT {', '.join(jetons)} FROM planches WHERE id = ?", (pid,)).fetchone()))
            for pid in ids}
    finally:
        conn.close()
    # Le mode d'échec d'un cliquet est son SEMIS : une colonne restée vide ne peut pas fuir.
    for pid, ligne in en_base.items():
        assert {c: _retenues_dans(v or "") for c, v in ligne.items()} == {c: {c} for c in jetons}, (
            f"le semis n'a pas pris sur la planche {pid} : {ligne}")

    # (4) Les trois recherches MORDENT : un détecteur qui ne reconnaîtrait pas ce qu'il
    # cherche approuverait tout. Chacune est éprouvée sur ce qu'elle doit voir, et sur un
    # témoin qu'elle ne doit pas voir.
    dossier, fichier = jetons["chemin_web"]
    assert _retenues_dans(f'<graphic url="/{dossier}/{fichier}.jpg" />') == {"chemin_web"}
    assert _retenues_dans(f"{fichier.upper()}.JPG") == {"chemin_web"}      # le nom seul
    assert _retenues_dans(json.dumps({"dossier": dossier})) == {"chemin_web"}
    assert _noms_retenus_dans('{"chemin_web": true}') == {"chemin_web"}
    assert _noms_retenus_dans('<surface subtype="CHEMIN_TIFF" />') == {"chemin_tiff"}
    assert formes and all(len(f) >= 6 for f in formes), (
        f"les formes dérivées des chemins réels sont trop courtes pour rien prouver : "
        f"{sorted(formes)}")
    for reel in reels:
        segments = reel.split("/")
        assert len(segments) >= 3 and "." in segments[-1], (
            f"`{reel}` n'a plus la forme racine/album/fichier.ext : revois "
            "`_formes_d_un_chemin`, qui en dérive ce qu'il cherche.")
        # Entier derrière un hôte, le fichier seul, le fichier sous une autre extension.
        assert reel.lower() in _formes_dans(f'url="https://exemple/{reel}"', formes)
        assert _formes_dans(f'<graphic url="{segments[-1].upper()}" />', formes)
        assert _formes_dans(segments[-1].rsplit(".", 1)[0] + ".tif", formes)
    temoin = '<surface xml:id="planche_1" n="1" lrx="400" /> {"album_id": 1, "numero": 1}'
    assert not (_retenues_dans(temoin) | _noms_retenus_dans(temoin) | _formes_dans(temoin, formes))

    # (5) Les exports d'album, depuis l'inventaire des routes — jamais une liste recopiée.
    toutes = _routes_get()
    inventaire_routes.exiger_plancher(len(toutes), "le cliquet des colonnes retenues", "GET")
    exports = [r.path for r in toutes if r.path.startswith(EXPORTS_D_ALBUM)]
    assert TROIS_FORMATS <= set(exports), (
        f"{sorted(TROIS_FORMATS - set(exports))} n'est plus sous {EXPORTS_D_ALBUM} : ce "
        "contrôle ne le joue plus, et il passerait au vert en le taisant. Un export "
        "d'album qui change d'adresse doit rester joué ici.")

    for chemin in exports:
        rep = client.get(chemin, params={"album_id": a["id"]})
        assert rep.status_code == 200, (
            f"{chemin} répond {rep.status_code} avec le seul `album_id` : apprends à ce "
            f"contrôle à le jouer, sans quoi il sort sans avoir été regardé. {rep.text[:300]}")
        # Lu en UTF-8 quand c'est du texte — les preuves du décor portent un point médian
        # (`c1·b1`) —, déplié comme le balayage quand c'est une archive.
        texte = (_texte(rep.content) if rep.content[:2] == b"PK"
                 else rep.content.decode("utf-8"))
        # Non-vacuité : ce que le décor publie, chaque format le porte. Un export lu de
        # travers (compressé, vide, autre album) ne le porterait pas — et paraîtrait
        # propre ; un décor aminci non plus, et ses branches ne seraient plus exercées.
        absents = [quoi for quoi, valeur in PUBLIES.items() if valeur.lower() not in texte.lower()]
        assert not absents, (
            f"{chemin} ne porte pas {absents} : ce contrôle ne lit pas ce qui sort, ou le "
            "décor n'exerce plus les branches qu'il annonce.")

        # (a) Les trois recherches. Elles passent AVANT l'inventaire et les preuves du
        # décor : une fuite doit être dite par ce qui la cherche, pas par un voisin.
        fuites = _retenues_dans(texte)
        assert not fuites, (
            f"{chemin} publie {sorted(fuites)}, que `main._EXPORT_PLANCHE_RETENUES` retient : "
            + " ; ".join(f"{c} — {main._EXPORT_PLANCHE_RETENUES[c]}" for c in sorted(fuites))
            + ". Deux formats du même album ne tiennent pas la même règle.")
        reconstruits = _formes_dans(texte, formes)
        assert not reconstruits, (
            f"{chemin} porte {sorted(reconstruits)} : la forme d'un chemin que l'import a "
            "réellement écrit pour cet album. La colonne n'est pas lue — le semis l'aurait "
            "montré — mais le chemin est RECONSTRUIT, et c'est le même chemin qui sort.")
        nommees = _noms_retenus_dans(texte)
        assert not nommees, (
            f"{chemin} NOMME {sorted(nommees)}, que `main._EXPORT_PLANCHE_RETENUES` retient : "
            "une colonne dite sans sa valeur sort quand même.")

        # (b) Ce qui PORTE une planche est déclaré, et (c) le décor exerce ses branches.
        if chemin == "/api/export/json":
            planches = rep.json()["planches"]
            cles = set().union(*(p.keys() for p in planches))
            attendues = set(main._EXPORT_PLANCHE_COLS) | DERIVEES_PLANCHE
            assert cles == attendues, (
                f"une planche du JSON porte {sorted(cles - attendues)} en trop, "
                f"{sorted(attendues - cles)} en moins : une clé neuve se DÉCLARE "
                "(`DERIVEES_PLANCHE`) en disant de quelles colonnes publiées elle dérive.")
            assert len(planches) == 3 and any(
                e["enfants"] for p in planches for e in p["regions"]), (
                "le JSON du décor n'a plus ses trois planches ou sa zone enfant.")
        if chemin == "/api/export/tei":
            racine = ET.fromstring(rep.content)
            surfaces = [e for e in racine.iter() if _local(e.tag) == "surface"]
            attributs = {_local(k) for s in surfaces for k in s.attrib}
            enfants = {_local(c.tag) for s in surfaces for c in s}
            assert attributs == ATTRIBUTS_SURFACE and enfants == ENFANTS_SURFACE, (
                f"une `<surface>` du TEI porte des attributs "
                f"({sorted(attributs ^ ATTRIBUTS_SURFACE)}) ou des enfants "
                f"({sorted(enfants ^ ENFANTS_SURFACE)}) que ce contrôle ne déclare pas, ou "
                "n'en porte plus qu'il déclare : ce qui porte une planche se DÉCLARE "
                "(`ATTRIBUTS_SURFACE`, `ENFANTS_SURFACE`), en disant ce qu'il publie.")
            sans = [quoi for quoi, vu in _branches_du_tei(racine).items() if not vu]
            assert not sans, (
                f"le TEI du décor ne montre plus {sans} : ces branches ne sont plus exercées.")
