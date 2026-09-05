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
    col = client.get("/api/collections", headers=ident).json()[0]

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
    # Ces huit-là IMPRIMENT un compte rendu — dire « aucune sortie » serait faux. Ce
    # qu'on affirme est plus étroit et se vérifie : aucun ne mentionne `utilisateur`,
    # `agent`, `auteur`, `verrou_par` ni un en-tête `Remote-` (relevé le 2026-08-31).
    ("outil", "importer_vocabulaire.py"): (
        "IMPORTE un tableur de vocabulaire : il écrit en base, et son compte rendu ne "
        "nomme que des termes."),
    ("outil", "reindex_materiel.py"): (
        "Maintenance : relit les masters et écrit `planches.dpi_*`/`mode`. Son compte "
        "rendu est un décompte de planches."),
    ("outil", "reindex_nlp.py"): (
        "Maintenance : régénère les tokens et l'index FTS. Son compte rendu est un "
        "décompte de régions."),
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
}


def _balayer_routes(client, seme) -> dict:
    vus = {}
    for r in _routes_get():
        cle = ("route", r.path)
        chemin = _chemin_concret(r.path, seme)
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

    classees = {
        "albums": set(main._EXPORT_ALBUM_COLS),
        "planches": set(main._EXPORT_PLANCHE_COLS) | set(main._EXPORT_PLANCHE_RETENUES),
    }
    for table, colonnes in reel.items():
        neuves = colonnes - classees[table]
        assert not neuves, (
            f"{table} : {sorted(neuves)} n'est ni publiée ni retenue. Ajoute la colonne à "
            f"_EXPORT_{table[:-1].upper()}_COLS si elle est descriptive, ou à "
            f"_EXPORT_PLANCHE_RETENUES avec sa raison. Ne rien faire la publierait.")
        fantomes = classees[table] - colonnes
        assert not fantomes, (
            f"{table} : {sorted(fantomes)} est classée mais n'existe plus — "
            "une liste périmée rassure.")

    for col, raison in main._EXPORT_PLANCHE_RETENUES.items():
        assert raison and len(raison) > 20, f"{col} est retenue sans raison écrite"
