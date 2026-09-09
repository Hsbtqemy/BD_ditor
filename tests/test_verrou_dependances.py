"""La spec et le verrou disent-ils la même chose ?  ARCH-2.

Le dépôt tient ses dépendances en DEUX temps, et c'est un bon modèle : les
`requirements*.txt` sont la spec lisible (des planchers, une intention), les
`requirements*.lock` sont le verrou de reproductibilité (des versions exactes, QA-1).
L'image de déploiement installe le verrou ; une personne qui développe installe, presque
toujours, la spec.

Rien ne rapprochait les deux. Le 2026-09-05 on a mesuré l'écart : la spec disait
`fastapi>=0.110`, le verrou `fastapi==0.133.0`, et le venv local avait dérivé jusqu'à
0.137 — une version où `app.routes` change de forme. Les deux cliquets qui énumèrent les
routes de l'application y sont devenus aveugles à 56 % du contrat, sans échouer.

L'écart lui-même est ce que ce fichier ferme. QA-5 l'avait dénoncé dans l'autre sens
(« 451 tests verts en local, trois moteurs morts dans l'image ») ; ici c'est le local qui
voyait juste, et ce qu'il voyait, c'est que la garde ne gardait plus rien. Dans les deux
sens la faute est la même : l'environnement qui MESURE n'est pas celui qui SERT, et rien ne
le dit.

Ce que ces tests ne font PAS : ils ne résolvent aucune dépendance. Ils ne peuvent donc pas
promettre qu'un `pip install` neuf rendra la version du verrou — cela demanderait le réseau
et l'index. Ils promettent l'invariant qui reste vérifiable hors ligne, et qui est celui
qui a manqué : la spec et le verrou ne se CONTREDISENT pas.
"""
import re
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

RACINE = Path(__file__).resolve().parent.parent

SPECS = ("requirements.txt", "requirements-dev.txt", "requirements-export.txt",
         "requirements-ocr.txt", "requirements-nlp.txt", "requirements-kumiko.txt")
VERROUS = ("requirements.lock", "requirements-dev.lock")

# Les verrous TRANSITIFS, engendrés depuis l'image par `deploy/geler_verrous.py` (QA-4).
# Ils ne remplacent pas les précédents : ceux-là disent ce qu'on a CHOISI, ceux-ci ce qui
# SUIT de ces choix. Mesuré le 2026-09-09 — 91 paquets à l'exécution pour 13 épinglés.
VERROUS_IMAGE = ("verrou-torch.lock", "verrou-image.lock", "verrou-test.lock")

# Deux distributions qui fournissent le MÊME paquet d'import. Elles s'écrasent l'une
# l'autre à l'installation, si bien qu'épingler l'une sans l'autre ne borde rien : c'est
# la dernière posée qui gagne. Une famille se déclare ici AVEC sa raison — le patron de
# `HORS_PERIMETRE` dans `test_autorisation`, où une exception s'écrit au lieu de se
# constater.
JUMEAUX = {
    ("opencv-python", "opencv-python-headless"):
        "les deux s'installent dans le même `cv2/`. Mesuré le 2026-08-27 dans l'image : "
        "headless 4.13 posé par le verrou, `opencv-python` résolu librement en 5.0.0.93, "
        "`cv2.__version__ == 5.0.0` — et Kumiko cassé (`HoughLinesP` rend (N, 4) en "
        "OpenCV 5 au lieu de (N, 1, 4)) pendant que `/api/sante` annonçait `kumiko: true`",
}

# Les paquets dont le dépôt lit un détail que le paquet ne PROMET pas. Ceux-là portent un
# plafond, et la raison s'écrit à côté du plafond, dans la spec.
#
# La liste n'est pas une précaution générale : plafonner tout mettrait le dépôt en dette de
# montée permanente, pour un gain nul là où l'on n'utilise que l'API publique. Ce qui la
# justifie ici est précis — `app.routes` est un attribut interne que trois fichiers de test
# ÉNUMÈRENT, et dont la forme a déjà changé une fois sous eux.
PLAFONNES = {
    "fastapi": "ARCH-2 — `app.routes` change de forme entre 0.133 et 0.137, et deux "
               "cliquets en tirent leur inventaire de routes",
}


def _lignes(nom: str) -> list[str]:
    """Les lignes utiles d'un fichier de dépendances, `-r` et commentaires écartés."""
    texte = (RACINE / nom).read_text(encoding="utf-8")
    return [l.strip() for l in texte.splitlines()
            if l.strip() and not l.strip().startswith(("#", "-r ", "--"))]


def _exigences(noms) -> dict:
    """{paquet: [Requirement, …]} sur un jeu de fichiers, extras compris."""
    out = {}
    for nom in noms:
        for ligne in _lignes(nom):
            exig = Requirement(re.sub(r"\s+#.*$", "", ligne))
            out.setdefault(exig.name.lower(), []).append((nom, exig))
    return out


def test_le_verrou_ne_contredit_jamais_la_spec():
    """Une version épinglée doit SATISFAIRE la spec qui la décrit.

    C'est l'invariant qui manquait, et sa violation est silencieuse dans les deux sens : un
    verrou qui sort de la spec fait installer autre chose selon le fichier employé, et une
    spec resserrée sous son verrou rend le verrou non installable. Ni l'un ni l'autre ne se
    remarque avant que deux environnements ne mesurent des choses différentes.
    """
    specs = _exigences(SPECS)
    fautes = []
    for nom in VERROUS:
        for paquet, paires in _exigences([nom]).items():
            for _, exig in paires:
                epingles = [s.version for s in exig.specifier if s.operator == "=="]
                if not epingles:
                    fautes.append(f"{nom} : `{exig}` n'épingle pas de version — un verrou "
                                  "qui ne verrouille pas est un fichier de plus à lire")
                    continue
                version = Version(epingles[0])
                for src, spec in specs.get(paquet, []):
                    if version not in spec.specifier:
                        fautes.append(
                            f"{paquet} : {nom} épingle {version}, que {src} exclut "
                            f"(`{spec}`). Un `pip install -r {src}` n'installera JAMAIS la "
                            f"version que {nom} — et l'image — utilisent.")
    assert not fautes, (
        "La spec et le verrou se contredisent :\n  " + "\n  ".join(fautes))


def _raison_declaree(nom: str, paquet: str) -> str:
    """Le bloc de commentaires contigus posé JUSTE AU-DESSUS d'un pin, s'il y en a un.

    Le test lit la déclaration au lieu de tenir une liste d'exemptions — même patron que
    les `# noqa: F401` du ré-export, dans `test_decoupage_api`. Une liste d'exemptions vit
    loin du cas qu'elle exempte, et elle survit à sa raison ; un commentaire posé sur la
    ligne part avec elle.
    """
    lignes = (RACINE / nom).read_text(encoding="utf-8").splitlines()
    for i, ligne in enumerate(lignes):
        nu = re.sub(r"\s+#.*$", "", ligne.strip())
        if not nu or nu.startswith(("#", "-r ", "--")):
            continue
        if Requirement(nu).name.lower() != paquet:
            continue
        bloc = []
        for precedente in reversed(lignes[:i]):
            if not precedente.strip().startswith("#"):
                break
            bloc.insert(0, precedente.strip().lstrip("# ").rstrip())
        return " ".join(bloc)
    return ""


def test_tout_paquet_du_verrou_a_une_spec_lisible_ou_une_raison_ecrite():
    """Un pin sans spec est une version qui ne vit qu'à un endroit, et sans intention.

    Le verrou dit QUOI installer, la spec dit POURQUOI cette borne. Un paquet qui n'existe
    que dans le verrou se monte à l'aveugle : personne ne sait quelle plage le dépôt tolère,
    donc personne ne sait si la prochaine montée est un choix ou un accident.

    L'exception est PRÉVUE et elle existe déjà : `opencv-python` est épinglé sans spec
    exprès — `ultralytics` le tire en transitif non épinglé, les deux paquets s'installent
    dans le même `cv2/`, et le non-épinglé gagne à l'import. Épingler le jumeau est le seul
    moyen de rendre le pin effectif. C'est une décision, et elle est écrite au-dessus du
    pin ; ce test la LIT au lieu de la connaître par cœur, faute de quoi il faudrait tenir
    une seconde liste, ailleurs, qui survivrait à sa raison.
    """
    specs = set(_exigences(SPECS))
    fautes = []
    for nom in VERROUS:
        for paquet in _exigences([nom]):
            if paquet in specs:
                continue
            raison = _raison_declaree(nom, paquet)
            if len(raison) < 120:
                fautes.append(
                    f"{nom} : `{paquet}` est épinglé sans figurer dans aucun "
                    f"requirements*.txt, et sans raison écrite au-dessus du pin "
                    f"({len(raison)} caractères de commentaire). Ajoutez la borne lisible "
                    "dans la spec, ou la raison ici — un pin muet est une version que "
                    "personne ne saura monter.")
    assert not fautes, "\n  " + "\n  ".join(fautes)


def test_les_paquets_dont_on_lit_les_entrailles_portent_un_plafond():
    """`fastapi` ne peut plus s'ouvrir jusqu'à une version qui change `app.routes`.

    Le plafond ne remplace pas le plancher dérivé d'`inventaire_routes` : celui-ci fait
    ÉCHOUER un inventaire qui rétrécit, quelle qu'en soit la cause, y compris une cause
    qu'on n'a pas prévue. Le plafond fait autre chose — il empêche l'environnement qui
    mesure de s'éloigner de l'image qui sert. Retirer l'un parce que l'autre existe
    reproduirait exactement la situation du 2026-09-05, par l'un des deux bouts.
    """
    specs = _exigences(["requirements.txt"])
    for paquet, raison in PLAFONNES.items():
        paires = specs.get(paquet)
        assert paires, f"{paquet} a disparu de requirements.txt"
        for src, exig in paires:
            plafonds = [s for s in exig.specifier if s.operator in ("<", "<=", "==", "~=")]
            assert plafonds, (
                f"{src} : `{exig}` n'a plus de plafond. Raison du plafond — {raison}. "
                "Le retirer rouvre la dérive entre le venv de développement et l'image "
                "livrée ; si la raison a cessé de valoir, retirez l'entrée de PLAFONNES "
                "en écrivant pourquoi.")


def _pins_des_verrous() -> dict:
    """{paquet canonique: (fichier, Version)} pour tout ce que les verrous épinglent."""
    pins = {}
    for nom in VERROUS:
        for paquet, paires in _exigences([nom]).items():
            for _, exig in paires:
                for s in exig.specifier:
                    if s.operator == "==":
                        pins[canonicalize_name(paquet)] = (nom, Version(s.version))
    return pins


def test_aucun_paquet_installe_ne_contredit_le_verrou():
    """Les exigences que les paquets portent EUX-MÊMES respectent-elles nos pins ?

    Les deux tests ci-dessus confrontent des fichiers du dépôt entre eux. Ils ne peuvent
    donc RIEN voir d'une borne qui vit dans les métadonnées d'un paquet — et c'est
    exactement par là que le trou de QA-4 est passé : `iiif-prezi3==3.1.1` exige
    `Pillow<=12.0.0`, `requirements.lock` est monté à `pillow==12.1.0` en juin 2026, et les
    deux sont devenus mutuellement exclusifs sans qu'aucune lecture du dépôt puisse le
    dire. Découvert deux mois et demi plus tard, en construisant l'image.

    Ce cas précis est désormais REDIT dans `requirements-export.txt`, donc attrapé hors
    ligne par le test du haut, même sans le paquet installé. Ce test-ci couvre l'AUTRE
    moitié : le couple qu'on n'a pas prévu. C'est la leçon de l'incident opencv — un pin
    ne vaut que si rien d'autre ne le contredit —, et elle ne se referme pas en traitant
    les cas un par un.

    Il ne résout aucune dépendance et ne touche pas le réseau : il lit ce qui est
    INSTALLÉ ici. Sa limite est donc son environnement, et il la DIT plutôt que de la
    taire — un paquet absent est nommé dans le message, jamais confondu avec un paquet sain.
    """
    pins = _pins_des_verrous()
    fautes, examines, absents, derives = [], [], [], []
    for paquet, (fichier, epinglee) in sorted(pins.items()):
        try:
            posee = Version(metadata.version(paquet))
            exigences = metadata.requires(paquet) or []
        except metadata.PackageNotFoundError:
            absents.append(paquet)
            continue
        examines.append(paquet)
        # Ce qu'on lit ici sont les exigences de la version POSÉE, qui n'est pas toujours
        # celle du verrou — ce venv en fait dériver sept (QA-4, zone 1). Le message doit
        # donc citer la version LUE : l'attribuer au pin ferait dire au test une chose
        # qu'il n'a pas mesurée, dans le fichier même qui traque cet écart.
        if posee != epinglee:
            derives.append(f"{paquet} {posee} posé / {epinglee} épinglé")
        for brute in exigences:
            exig = Requirement(brute)
            # Les extras ne sont pas installés, et un marqueur de plateforme non satisfait
            # ne s'applique pas ici : les évaluer évite des faux positifs bruyants.
            if exig.marker and not exig.marker.evaluate({"extra": ""}):
                continue
            cible = canonicalize_name(exig.name)
            if cible not in pins:
                continue          # transitif flottant — c'est la zone 1 de QA-4, pas ici
            f_cible, v_cible = pins[cible]
            if v_cible not in exig.specifier:
                fautes.append(
                    f"{paquet} {posee} (posé ici) exige `{exig}`, que {f_cible} contredit "
                    f"en épinglant {cible}=={v_cible}. Les deux ne s'installeront jamais "
                    "ensemble — pip répondra `ResolutionImpossible`, ou pire, un test se "
                    "skippera en silence.")

    assert examines, (
        "Aucun paquet du verrou n'est installé : ce test n'a rien regardé, et un vert "
        "voudrait dire « je n'ai rien vu » plutôt que « tout va bien ». Installez "
        "requirements-dev.lock.")
    assert not fautes, (
        f"Le verrou se contredit lui-même ({len(examines)} paquets examinés, "
        f"{len(absents)} non installés : {', '.join(absents) or '—'} ; "
        f"{len(derives)} posés à une autre version que le pin : "
        f"{', '.join(derives) or '—'}) :\n  "
        + "\n  ".join(fautes))


# --------------------------------------------------------------------------- #
# QA-4 — les verrous transitifs, et ce qu'ils ne doivent jamais contredire
# --------------------------------------------------------------------------- #
def _pins(nom: str) -> dict:
    """{paquet canonique: version} d'un fichier de verrou.

    Les lignes `nom @ URL` sont IGNORÉES : elles épinglent par empreinte et non par
    version (le modèle spaCy), donc elles n'ont pas de version à comparer.
    """
    d = {}
    for l in _lignes(nom):
        m = re.match(r"^([A-Za-z0-9._-]+)\s*==\s*([^\s;]+)", l)
        if m:
            d[canonicalize_name(m.group(1))] = m.group(2)
    return d


def test_les_verrous_d_image_ne_contredisent_pas_les_verrous_choisis():
    """Une dépendance CHOISIE doit se retrouver dans l'image à la version choisie.

    Les deux familles de verrous répondent à des questions différentes — « qu'a-t-on
    décidé » et « qu'est-ce qui en découle » —, et c'est justement pourquoi elles peuvent
    diverger sans que rien ne le dise : `requirements.lock` n'est plus installé DANS
    l'image depuis QA-4, donc une modification qu'on y ferait n'aurait aucun effet, et le
    fichier continuerait d'affirmer une version que l'image ne porte pas.

    C'est le mode d'échec le plus vicieux de ce chantier : le verrou lu par un humain et
    le verrou exécuté par la machine cesseraient de parler du même logiciel.
    """
    choisis = {}
    for nom in VERROUS:
        for paquet, version in _pins(nom).items():
            choisis[paquet] = (version, nom)

    image = {}
    for nom in VERROUS_IMAGE:
        image.update(_pins(nom))

    ecarts = {p: (v, image[p]) for p, (v, _) in choisis.items()
              if p in image and image[p] != v}
    assert not ecarts, (
        "ces paquets sont épinglés à une version que l'image ne porte pas "
        f"(choisi, image) : {ecarts}. Régénérer par `python deploy/geler_verrous.py`")

    absents = sorted(p for p in choisis if p not in image)
    assert not absents, (
        f"{absents} sont épinglés dans {VERROUS} sans exister dans l'image : le verrou "
        f"décrit un logiciel qui n'est pas installé")


def test_les_paquets_jumeaux_portent_la_meme_version():
    """Deux distributions qui écrasent le même `import` ne peuvent pas diverger.

    Épingler l'une sans l'autre ne borde RIEN — la dernière posée gagne —, et les
    épingler à des versions différentes est pire : l'installation « réussit », l'import
    prend la mauvaise, et rien ne le dit. C'est ainsi que Kumiko est mort dans l'image
    pendant que `/api/sante` l'annonçait vivant.

    La garde balaie les DEUX familles de verrous : celle des choix comme celle du gel.
    Un jumeau qui n'apparaît nulle part n'est pas une faute — la famille se déclare pour
    le cas où il apparaît.
    """
    for nom in VERROUS + VERROUS_IMAGE:
        pins = _pins(nom)
        for famille, raison in JUMEAUX.items():
            presents = {canonicalize_name(x): pins[canonicalize_name(x)]
                        for x in famille if canonicalize_name(x) in pins}
            versions = set(presents.values())
            assert len(versions) <= 1, (
                f"{nom} épingle {presents} à des versions différentes — {raison}")


def test_le_dockerfile_n_epingle_aucune_version_hors_verrou():
    """Toute version installée dans l'image vient d'un fichier de verrou, jamais d'une
    ligne du Dockerfile.

    `torch==2.13.0 torchvision==0.28.0` y était écrit à la main pendant que
    `requirements.lock` se disait « LE verrou » : deux endroits décidaient des versions,
    dont un seul se lisait comme tel. Le gel les a repris ; cette garde empêche qu'on en
    réintroduise un, ce qui est le geste le plus naturel du monde quand une construction
    échoue et qu'on veut « juste forcer une version ».
    """
    # Les continuations `\` sont jointes d'abord : un `RUN pip install` tient souvent sur
    # deux lignes, et c'est justement sur la SECONDE que la version se trouve — un
    # balayage ligne à ligne ne verrait rien et resterait vert.
    texte = (RACINE / "deploy" / "Dockerfile").read_text(encoding="utf-8")
    texte = texte.replace("\\\n", " ")
    fautives = [l.strip() for l in texte.splitlines()
                if not l.strip().startswith("#") and "pip install" in l and "==" in l]
    assert not fautives, (
        f"le Dockerfile épingle des versions hors verrou : {fautives}. Les ajouter au "
        f"verrou concerné et régénérer (`python deploy/geler_verrous.py`) — sinon deux "
        f"endroits décident des versions, dont un seul se lit comme tel")
