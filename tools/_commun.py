"""Helpers partagés par les scripts d'export de métadonnées (tools/)."""
from __future__ import annotations

import importlib.metadata as _im
import sys
from functools import lru_cache
from pathlib import Path


def forcer_utf8() -> None:
    """Force stdout/stderr en UTF-8. À appeler en tête de `main()` de chaque tool.

    Sur Windows, la console est en cp1252 : `print()` d'un caractère hors cp1252 (« → »,
    emoji, CJK — p. ex. un résumé PyPI dans le SBOM) lève UnicodeEncodeError. No-op si le
    flux n'est pas reconfigurable (déjà encapsulé, ou Python < 3.7)."""
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

# Racine du dépôt (tools/_commun.py → dépôt) et clone Kumiko vendu dedans.
_REPO = Path(__file__).resolve().parent.parent
_KUMIKO_DIR = _REPO / "lib" / "kumiko"        # clone git (cf. requirements-kumiko.txt)

# Paquets suivis (union des requirements : noyau + ocr + nlp + kumiko + export).
# `opencv-python-headless`, `numpy` et `requests` sont les dépendances d'EXÉCUTION
# de Kumiko (passe 1) — voir requirements-kumiko.txt.
_PAQUETS = ("fastapi", "uvicorn", "pydantic", "pillow", "python-multipart", "httpx",
            "ultralytics", "easyocr", "torch", "huggingface-hub", "spacy",
            "opencv-python-headless", "numpy", "requests", "openpyxl")

# Catalogue documentaire des composants logiciels : pour chaque brique,
# (catégorie, site officiel, rôle DANS le projet). La *description générique* (résumé
# éditeur) n'est PAS recopiée ici : elle est lue à l'export depuis les métadonnées du
# paquet installé (cf. `_resume_installe`), donc toujours à jour et sans doublon à
# maintenir. `python` / `kumiko` ne sont pas des paquets pip (traités à part).
_CATALOGUE = {
    "python": ("exécution", "https://www.python.org/",
               "Interpréteur qui exécute l'outil et les scripts d'export."),
    "kumiko": ("segmentation (passe 1)", "https://github.com/njean42/kumiko",
               "Découpe automatique des planches en cases (clone git vendu dans lib/kumiko)."),
    "fastapi": ("noyau", "https://fastapi.tiangolo.com/",
                "Framework web : sert l'API /api/ et les pages."),
    "uvicorn": ("noyau", "https://www.uvicorn.org/",
                "Serveur ASGI qui fait tourner l'application."),
    "pydantic": ("noyau", "https://docs.pydantic.dev/",
                 "Validation des corps de requête/réponse de l'API."),
    "pillow": ("noyau", "https://python-pillow.github.io/",
               "Lecture des images master + génération des dérivés web."),
    "python-multipart": ("noyau", "https://github.com/Kludex/python-multipart",
                         "Décodage des envois multipart (import de planches)."),
    "httpx": ("noyau", "https://www.python-httpx.org/",
              "Client HTTP du connecteur WebDAV ShareDocs (Huma-Num)."),
    "ultralytics": ("bulles (passe 2)", "https://docs.ultralytics.com/",
                    "YOLOv8 : détection des bulles (moteur optionnel)."),
    "huggingface-hub": ("bulles (passe 2)", "https://huggingface.co/docs/huggingface_hub",
                        "Téléchargement du modèle de bulles ogkalu (optionnel)."),
    "easyocr": ("OCR (passe 3)", "https://github.com/JaidedAI/EasyOCR",
                "OCR français : pré-remplit le texte des bulles (optionnel)."),
    "torch": ("ML (bulles / OCR)", "https://pytorch.org/",
              "Moteur tensoriel requis par YOLOv8 et EasyOCR (optionnel)."),
    "spacy": ("NLP", "https://spacy.io/",
              "Lemmes + grammaire (POS/morph) : recherche par lemme, analyse (optionnel)."),
    "opencv-python-headless": ("segmentation (passe 1)", "https://opencv.org/",
                               "Vision par ordinateur : dépendance d'exécution de Kumiko."),
    "numpy": ("segmentation (passe 1)", "https://numpy.org/",
              "Calcul matriciel : socle de Kumiko / OpenCV (et du ML)."),
    "requests": ("segmentation (passe 1)", "https://requests.readthedocs.io/",
                 "Client HTTP utilisé par Kumiko."),
    "openpyxl": ("export", "https://openpyxl.readthedocs.io/",
                 "Écriture des classeurs XLSX (dont cet export)."),
}


def _revision_git(git_dir) -> str | None:
    """Révision courte (7 car.) lue DIRECTEMENT dans un dossier `.git` (HEAD → ref,
    ou `packed-refs`), **sans invoquer `git`** : fiable et instantané même sur système
    de fichiers lent (Google Drive, réseau), où un subprocess `git` peut se bloquer
    indéfiniment. None si illisible (dossier absent, HEAD introuvable, hors dépôt)."""
    try:
        git = Path(git_dir)
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()          # ex. refs/heads/dev
            loose = git / ref
            if loose.exists():
                rev = loose.read_text(encoding="utf-8").strip()
            else:                                         # ref empaquetée (packed-refs)
                rev = None
                packed = git / "packed-refs"
                if packed.exists():
                    for ligne in packed.read_text(encoding="utf-8").splitlines():
                        if ligne and ligne[0] not in "#^" and ligne.endswith(ref):
                            rev = ligne.split()[0]
                            break
        else:
            rev = head                                    # HEAD détaché : SHA direct
    except Exception:
        rev = None
    return rev[:7] if rev else None


def _resume_installe(nom: str) -> str | None:
    """Description GÉNÉRIQUE (résumé éditeur) d'un paquet, lue dans ses métadonnées
    **installées** (champ `Summary` du .dist-info) — hors ligne, sans réseau. None si
    le paquet n'est pas installé ou n'expose pas de résumé."""
    try:
        resume = _im.metadata(nom).get("Summary")
        return resume.strip() if resume and resume.strip() else None
    except Exception:
        return None


@lru_cache(maxsize=None)
def _kumiko() -> dict:
    """Provenance du moteur de SEGMENTATION Kumiko (passe 1). Kumiko est un clone git
    *vendu* dans `lib/kumiko` — **pas un paquet pip**, donc invisible à
    `importlib.metadata` : on identifie sa version par sa **révision git**. Ses
    dépendances d'exécution (opencv-python-headless, numpy, requests) sont dans
    `paquets`. Non installé → `present=False`, `revision=None`."""
    entree = _KUMIKO_DIR / "kumiko"                       # script d'entrée (cf. segmentation.py)
    return {"present": entree.exists(),
            "revision": _revision_git(_KUMIKO_DIR / ".git")}


@lru_cache(maxsize=None)
def composants() -> list:
    """Inventaire logiciel documenté (SBOM léger) qui a produit CET export : une entrée
    par composant (Python + Kumiko + chaque paquet suivi), avec version **réellement
    installée** (révision git pour Kumiko), catégorie, rôle dans le projet, site officiel
    et description générique (résumé PyPI local). Un composant absent garde son
    entrée (version=None, installe=False) pour documenter ce qui *pourrait* servir."""
    lignes = []

    cat, site, role = _CATALOGUE["python"]
    lignes.append({"composant": "python", "categorie": cat,
                   "version": sys.version.split()[0], "installe": True,
                   "role": role, "site": site, "resume": None})

    k = _kumiko()
    cat, site, role = _CATALOGUE["kumiko"]
    lignes.append({"composant": "kumiko", "categorie": cat,
                   "version": k["revision"], "installe": k["present"],
                   "role": role, "site": site,
                   "resume": "Découpe de planches de bande dessinée en cases."})

    for nom in _PAQUETS:
        cat, site, role = _CATALOGUE.get(nom, ("", "", ""))
        try:
            ver = _im.version(nom)
        except Exception:
            ver = None
        lignes.append({"composant": nom, "categorie": cat, "version": ver,
                       "installe": ver is not None, "role": role, "site": site,
                       "resume": _resume_installe(nom)})
    return lignes


@lru_cache(maxsize=None)
def environnement() -> dict:
    """Environnement logiciel à l'EXPORT (paradonnée / reproductibilité) : version de
    Python + versions **réellement installées** des paquets des requirements (absent →
    None) + provenance des **moteurs vendus** (Kumiko : clone git, pas un paquet pip).
    C'est l'env qui a produit CET export ; les versions par passe (segmentation / OCR /
    NLP, à leur date) restent à-prévoir (journal d'activités). Vue documentée détaillée
    (rôle + site + description) : cf. `composants()`."""
    paquets = {}
    for nom in _PAQUETS:
        try:
            paquets[nom] = _im.version(nom)
        except Exception:
            paquets[nom] = None
    return {"python": sys.version.split()[0], "paquets": paquets,
            "moteurs": {"kumiko": _kumiko()}}


def portee_albums(album_ids) -> dict | None:
    """PORTÉE d'export par ensemble d'albums (scoping `--collection`).

    `album_ids=None` → renvoie None (corpus entier : aucun filtre). Sinon, renvoie des
    ENSEMBLES de valeurs SQL prêts à l'emploi dans un `IN` — les entiers sont inlinés (ils
    viennent de la base, JAMAIS d'une saisie utilisateur ; aucune injection possible) :

      • `albums`   : `(1,2,3)`                       → `... WHERE id IN {p['albums']}`
      • `planches` : `(SELECT id FROM planches …)`    → `... WHERE planche_id IN {p['planches']}`
      • `regions`  : `(SELECT id FROM regions …)`     → `... WHERE region_id IN {p['regions']}`

    Un ensemble vide (collection sans album) donne `(-1)` : aucun id ne matche → sortie vide,
    honnête. Partagé par metadonnees_collection.py et description_collection.py."""
    if album_ids is None:
        return None
    a = ",".join(str(int(i)) for i in album_ids) or "-1"
    planches = f"(SELECT id FROM planches WHERE album_id IN ({a}))"
    regions = f"(SELECT id FROM regions WHERE planche_id IN {planches})"
    return {"albums": f"({a})", "planches": planches, "regions": regions}


@lru_cache(maxsize=None)
def version_outil(base_dir) -> dict:
    """Provenance de l'outil produisant l'export (paradonnée / PROV).

    BéDéditeur n'a pas de version déclarée → on identifie le code par sa **révision
    git** (hash court), lue directement dans `.git` (cf. `_revision_git`), sans invoquer
    `git`. `version` reste None tant qu'aucune n'est déclarée. Pas de détection « arbre
    modifié » (elle exigerait `git status`, coûteux). Hors dépôt → revision=None.
    """
    return {"nom": "BéDéditeur", "version": None,
            "revision": _revision_git(Path(base_dir) / ".git")}


# --------------------------------------------------------------------------- #
# Pseudonymisation des annotateurs à la SORTIE (AUTH-1, 2026-08-31)
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Ce que le journal A3 publie AU DÉPÔT — par cible_table, et PAR DÉCISION (AUTH-1)
#
# `pseudonymes()` ci-dessous retire l'identité de la colonne `agent`. Elle ne pouvait
# rien contre les CHARGES : `metadonnees_collection` publie `avant`/`apres` mot pour mot,
# si bien qu'un login pseudonymisé en colonne 4 ressortait en clair en colonne 8, dans la
# même ligne. Mesuré le 2026-09-06 sur trois événements VIVANTS — `collection` publiait le
# login du propriétaire, `collection_acces` le principal de chaque partage, `sharedocs`
# un chemin serveur et un nom de compte Huma-Num.
#
# Le cliquet d'AUTH-5 ne pouvait pas le voir, et pas par accident : son semis met les
# sentinelles dans la colonne `agent`, et sa charge d'événement est un token
# (`{lemme, pos, morph}`). Une garde qui approuve en ne regardant pas la bonne colonne.
#
# La coupure n'est donc PAS « quelles colonnes » mais « quels ACTES » : le dépôt a besoin
# de savoir comment le CORPUS a été fait, jamais comment l'instance est administrée. Un
# lecteur ne tire rien de « annotateur-1 a modifié utilisateur/None », et la ligne seule
# invite la question à laquelle on refuse de répondre — d'où le retrait de l'événement
# entier plutôt que de sa charge.
#
# Une table ABSENTE des deux ensembles fait échouer `test_journal_publie_par_decision` :
# c'est le seul moyen qu'une future table administrative soit retenue PAR DÉFAUT et non
# par décision. Même forme que le correctif de `GET /api/export/json`, qui a cessé de
# faire `SELECT *` pour nommer ses colonnes.
# --------------------------------------------------------------------------- #
CIBLES_CORPUS = frozenset({
    "regions",             # géométrie et arbre de structure
    "annotations",         # note et tags d'une région
    "bulle_locuteur",      # attribution d'une bulle à un personnage
    "personnage_presence", # présence d'un personnage dans une case
    "token_correction",    # correction grammaticale — le cœur de l'accord ANN-5
    "planches",            # statut et validation d'une planche
    "evenement",           # les `annulation` de l'undo (D1) : un acte défait EST de la
                           # provenance de corpus, et le taire donnerait un historique
                           # où des actes annulés paraissent tenir encore
})

CIBLES_RETENUES = {
    "utilisateur":
        "AUTH-7 — la reprise d'un login. La charge porte le NOM AFFICHÉ d'une personne "
        "et son login, en clair : c'est exactement ce que `pseudonymes()` retire de la "
        "colonne d'à côté. Administration de comptes, jamais provenance de corpus.",
    "sharedocs":
        "SHARE-1 — chemin serveur du dépôt et nom du compte Huma-Num employé. Sauvegarder "
        "est un geste d'EXPLOITATION ; l'entrepôt n'a rien à en apprendre, et le nom de "
        "compte est une identité de tiers que personne n'a consenti à publier.",
    "collection":
        "AUTH-3 — la charge de création porte `proprietaire`, un login. Les descripteurs "
        "de la collection partent au dépôt par les blocs prévus pour cela, où ils sont "
        "choisis ; les faire ressortir ici les publierait une seconde fois, sans tri.",
    "collection_acces":
        "AUTH-3 — `principal` est un login ou un NOM DE GROUPE. Un registre de qui a eu "
        "accès à quoi est une pièce d'audit interne : il sert à répondre d'un accès "
        "accordé par erreur, et cette réponse se doit à l'équipe, pas à l'entrepôt.",
}


def evenements_publiables(conn, ordre: str = "ASC"):
    """Les événements du journal A3 qui partent au dépôt, dans l'ordre demandé.

    UN seul endroit fait le filtre, et les deux sérialisations l'appellent — pour la même
    raison que `pseudonymes()` est partagé : deux vues du même journal qui n'auraient pas
    les mêmes actes se contrediraient, et rien ne le signalerait.

    CONSÉQUENCE À CONNAÎTRE : `pseudonymes()` numérote sur le journal ENTIER, retenues
    comprises, et ce n'est pas un oubli. Son invariant est qu'une personne garde son numéro
    d'un artefact à l'autre et d'un dépôt au suivant ; le restreindre aux actes publiés le
    ferait dépendre de la liste blanche, si bien qu'y ajouter une table demain renumérote
    des dépôts déjà déposés. Le prix est que la suite publiée peut avoir des TROUS — un
    `annotateur-2` absent du graphe parce que ses seuls actes sont administratifs. Un trou
    se lit comme une omission ; c'est le moindre des deux maux, et il est ici par écrit.
    """
    if ordre not in ("ASC", "DESC"):
        raise ValueError(f"ordre : ASC ou DESC, pas {ordre!r}")
    cibles = tuple(sorted(CIBLES_CORPUS))
    return conn.execute(
        f"SELECT * FROM evenement WHERE cible_table IN ({','.join('?' * len(cibles))}) "
        f"ORDER BY id {ordre}", cibles)


def pseudonymes(conn) -> dict:
    """login humain → « annotateur-N ». Partagé par TOUS les exports d'un même corpus.

    Le journal A3 sert deux buts à la sortie, et le login n'en sert bien aucun. Pour
    l'AUDITABILITÉ du pré-remplissage — la valeur FAIR revendiquée — `agent_type` suffit :
    ce qui compte est « machine, puis retouché par un humain ». Pour l'ATTRIBUTION
    scientifique, le bon support existe déjà et c'est `contribution`, avec son ORCID ; un
    login identifie sans créditer, ce qui est le pire des deux.

    Mais un graphe PROV où tous les humains se confondent perd les CHAÎNES DE RÉVISION —
    on ne distingue plus deux relecteurs, et c'est tout l'intérêt de la provenance. D'où le
    pseudonyme, qui garde la structure et retire l'identité : même issue que les paires
    d'accord inter-annotateurs.

    **Les moteurs gardent leur nom**, et ce n'est pas un oubli : `kumiko`, `yolov8-bulles`
    et `easyocr` sont des LOGICIELS. Les nommer EST l'auditabilité qu'on revendique, et
    c'est pourquoi ils ne sont jamais collectés ici — un `pseudonymes(...).get(nom, nom)`
    les laisse passer tout seuls.

    ORDRE D'APPARITION et non ordre alphabétique : un annotateur qui rejoint l'équipe
    renumérote tout ce qui le suit dans l'alphabet, si bien que deux dépôts successifs du
    même corpus décriraient des équipes différentes. Par date de première trace, chacun
    garde son numéro tant que personne n'est retiré.

    Ce n'est PAS de l'anonymisation : dans une petite équipe, l'ordre d'arrivée et le
    volume de travail réidentifient. C'est une mesure de proportion — retirer le nom d'un
    artefact qui part définitivement — pas une garantie. Deux conséquences à connaître,
    toutes deux assumées :

    · Le mapping est CORPUS-ENTIER, jamais restreint à la collection exportée. C'est
      voulu — le même pseudonyme désigne la même personne d'un artefact à l'autre, sans
      quoi la chaîne de révisions cesserait de se lire entre deux exports du même travail.
      Le prix est qu'un dépôt d'une petite collection peut porter « annotateur-7 », donc
      révéler qu'il existe au moins sept annotateurs dans l'instance.
    · `token_correction.date_modif` est la date du DERNIER passage (la table est en
      upsert), pas de la première trace. L'ordre s'appuie donc surtout sur le journal, qui
      est append-only et porte les vraies dates ; `token_correction` n'est là que pour les
      corpus dont le journal ne couvre pas tout — sans elle, un correcteur sans acte
      journalisé sortirait sous son login.
    """
    vus: dict = {}
    for sql in (
            # `date` du premier acte : les trois sources sont fondues dans un même ordre.
            "SELECT agent, MIN(date) AS d FROM evenement "
            "WHERE agent_type = 'humain' AND agent IS NOT NULL GROUP BY agent",
            # `activite` n'a pas de colonne `date` mais un `date_debut` : un run a une
            # durée, un acte a un instant.
            "SELECT agent, MIN(date_debut) AS d FROM activite "
            "WHERE agent_type = 'humain' AND agent IS NOT NULL GROUP BY agent",
            "SELECT auteur AS agent, MIN(date_modif) AS d FROM token_correction "
            "WHERE auteur IS NOT NULL GROUP BY auteur"):
        for r in conn.execute(sql):
            nom, d = r[0], r[1] or ""
            if nom not in vus or d < vus[nom]:
                vus[nom] = d
    ordre = sorted(vus, key=lambda n: (vus[n], n))
    return {nom: f"annotateur-{i}" for i, nom in enumerate(ordre, 1)}
