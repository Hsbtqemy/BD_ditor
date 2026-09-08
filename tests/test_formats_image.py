"""SEC-3 — Pillow ne décode que ce que le corpus contient.

`CVE-2026-25990` : écriture hors limites au décodage d'une image **PSD** forgée (tuiles à
décalage négatif). Affecte Pillow ≥ 10.3.0, corrigé en 12.1.1 — et nous sommes tenus sous
12.0.0 par `iiif-prezi3`, qui n'a pas de sortie par le haut. Le contournement proposé par
l'avis lui-même est le paramètre `formats` d'`Image.open`, qui vaut **quelle que soit la
version installée** : c'est ce qui le rend indépendant du plafond.

**Le filtre d'extension de l'API ne suffit pas, et c'est tout le sujet.** `Image.open` ne
regarde pas le nom du fichier : il renifle l'en-tête. Un PSD renommé `.tif` franchit
`IMG_EXTS` sans encombre et arrive au décodeur PSD.

Ce module se garde d'un piège précis : un test qui déposerait n'importe quels octets et
constaterait un refus passerait aussi bien sur du bruit, et prouverait seulement que
l'ingest refuse ce qui n'est pas une image. La première fonction existe pour ça — elle
établit que le fichier EST un PSD que Pillow saurait ouvrir sans la garde. Sans elle, tout
le reste est décoratif.
"""
import io
import struct
from pathlib import Path

import pytest
from PIL import Image, UnidentifiedImageError

from config import IMG_EXTS, PILLOW_FORMATS
from conftest import ADMIN


def _psd_minimal(largeur: int = 1, hauteur: int = 1) -> bytes:
    """Un PSD VALIDE, réduit à son plus simple appareil.

    Pillow n'ÉCRIT pas le PSD — il faut donc poser l'en-tête à la main. Ce n'est pas un
    exploit : les tuiles à décalage négatif de l'avis ne sont pas reproduites, et il n'y a
    aucune raison de les fabriquer. Ce qu'on démontre, c'est que le décodeur PSD est
    ATTEIGNABLE ; l'avis dit ce qu'on y trouve.
    """
    d = b"8BPS" + struct.pack(">H", 1) + b"\0" * 6
    d += struct.pack(">H", 1)                                    # canaux
    d += struct.pack(">I", hauteur) + struct.pack(">I", largeur)
    d += struct.pack(">H", 8)                                    # bits par canal
    d += struct.pack(">H", 1)                                    # mode : niveaux de gris
    d += struct.pack(">I", 0) * 3            # color mode · resources · layers : vides
    d += struct.pack(">H", 0)                                    # compression : brute
    d += b"\x00" * (largeur * hauteur)
    return d


# --------------------------------------------------------------------------- #
# D'abord : le leurre en est bien un
# --------------------------------------------------------------------------- #
def test_le_PSD_forge_serait_ouvert_sans_la_garde():
    """Sans `formats`, Pillow ouvre ce fichier — donc le vecteur est réel, et les tests
    qui suivent mesurent une garde plutôt qu'un fichier illisible.

    C'est le contrôle qui empêche ce module de se rassurer tout seul : un test de refus
    passe aussi sur du bruit.
    """
    im = Image.open(io.BytesIO(_psd_minimal()))
    assert im.format == "PSD", im.format


def test_la_garde_referme_ce_que_la_precedente_a_ouvert():
    with pytest.raises(UnidentifiedImageError):
        Image.open(io.BytesIO(_psd_minimal()), formats=PILLOW_FORMATS)


# --------------------------------------------------------------------------- #
# Les deux listes ne peuvent pas diverger
# --------------------------------------------------------------------------- #
def test_chaque_extension_acceptee_a_son_format_autorise():
    """Une extension reçue dont le format n'est pas décodable casserait l'import ; c'est
    le sens BÉNIN de la divergence, et il se remarque.

    Le sens grave est l'autre, couvert par le test suivant.
    """
    Image.init()                       # peuple `Image.EXTENSION`
    orphelines = [e for e in IMG_EXTS
                  if Image.EXTENSION.get(e) not in PILLOW_FORMATS]
    assert not orphelines, (
        f"extensions acceptées dont Pillow ne pourra rien faire : {orphelines}")


def test_aucun_format_decodable_n_est_hors_du_corpus():
    """Le sens GRAVE : un format décodable qu'aucune extension n'apporte élargit la
    surface d'attaque sans rendre aucun service.

    C'est exactement ce qui rouvrirait le trou — pas une erreur visible, un format resté
    dans la liste après qu'on a cessé de l'accepter.
    """
    Image.init()
    apportes = {Image.EXTENSION.get(e) for e in IMG_EXTS}
    inutiles = [f for f in PILLOW_FORMATS if f not in apportes]
    assert not inutiles, (
        f"formats décodables qu'aucune extension acceptée n'apporte : {inutiles}")


def test_le_PSD_n_est_ni_accepte_ni_decodable():
    """Nommément, parce que c'est le format de l'avis. Un contrôle qui ne cite personne
    ne dit pas ce qu'il protège."""
    assert "PSD" not in PILLOW_FORMATS
    assert ".psd" not in IMG_EXTS


# --------------------------------------------------------------------------- #
# Bout en bout : l'ingest et la route
# --------------------------------------------------------------------------- #
def test_l_ingest_refuse_un_PSD_deguise_en_tiff(tmp_path):
    """`read_metadata` est la première chose que l'ingest appelle sur un fichier reçu."""
    from pipeline.ingest import make_web_derivative, read_metadata

    leurre = tmp_path / "planche.tif"           # extension MENTEUSE, contenu PSD
    leurre.write_bytes(_psd_minimal(4, 4))
    with pytest.raises(UnidentifiedImageError):
        read_metadata(leurre)
    # Et le second point d'entrée, qui décode aussi : ne pas le borner reviendrait à
    # fermer la porte en laissant la fenêtre.
    with pytest.raises(UnidentifiedImageError):
        make_web_derivative(leurre, tmp_path / "derive.jpg")


def test_la_route_d_import_refuse_et_ne_LAISSE_RIEN_sur_disque(client, album, data_dir):
    """400 plutôt que 500, et surtout : aucun master orphelin.

    Le fichier est écrit AVANT l'ingestion (le numéro doit être alloué d'abord), donc un
    refus tardif laisserait un PSD forgé dans `corpus/` — décodé à chaque passe OCR
    ultérieure si quoi que ce soit venait à le relire.
    """
    # Les FICHIERS seulement : `store_upload` crée le dossier de l'album avant d'écrire,
    # et un répertoire vide qui survit à un refus n'est ni une fuite ni une surface de
    # décodage. Le premier jet comptait aussi les dossiers et échouait sur `corpus/album_1`,
    # ce qui aurait fait chercher un défaut là où il n'y en a pas.
    fichiers = lambda: {p for p in Path(data_dir / "corpus").rglob("*") if p.is_file()}
    avant = fichiers()
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("planche.tif", _psd_minimal(8, 8), "image/tiff")},
                    headers=ADMIN)
    assert r.status_code == 400, r.text
    assert fichiers() == avant, (
        f"fichier(s) laissé(s) sur disque : {sorted(fichiers() - avant)}")


def test_une_vraie_image_passe_toujours(client, album, png_bytes):
    """L'autre bout : sans lui, une garde qui refuserait TOUT passerait les tests
    ci-dessus."""
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("planche.png", png_bytes, "image/png")},
                    headers=ADMIN)
    assert r.status_code in (200, 201), r.text


def test_l_OCR_refuse_AUSSI_un_master_forge(tmp_path, monkeypatch):
    """Les deux `Image.open` de l'OCR, que la passe de mutation avait trouvés NUS.

    Ils décodent des fichiers déjà écrits sur disque, donc on les croit protégés par
    l'ingest — et c'est l'argument qui les laisse sans garde. Il ne tient pas : un master
    antérieur à ce chantier, ou déposé par un autre chemin, est relu à chaque passe. Une
    porte fermée et une fenêtre ouverte font une pièce ouverte.

    Écrit APRÈS avoir mesuré : retirer `formats=` de ces deux lignes laissait la suite
    entièrement verte, alors que le module prétendait couvrir « les quatre `Image.open` ».
    """
    import pipeline.ocr as ocr
    monkeypatch.setattr(ocr, "DATA_DIR", tmp_path)

    (tmp_path / "master.tif").write_bytes(_psd_minimal(4, 4))
    with pytest.raises(UnidentifiedImageError):
        ocr._open_image({"chemin_tiff": "master.tif", "chemin_web": "web.jpg",
                         "largeur_px": 100})

    # L'autre branche : sans master, l'OCR retombe sur le dérivé web. Deux lignes, deux
    # cas — n'en éprouver qu'un laisserait l'autre exactement où il était.
    (tmp_path / "web.jpg").write_bytes(_psd_minimal(4, 4))
    with pytest.raises(UnidentifiedImageError):
        ocr._open_image({"chemin_tiff": None, "chemin_web": "web.jpg",
                         "largeur_px": 100})


@pytest.mark.usefixtures("data_dir")
def test_ultralytics_ne_garde_pas_la_main_sur_Image_open():
    """`ultralytics` remplace `PIL.Image.open` GLOBALEMENT, et il faut le défaire.

    Son enveloppe (`ultralytics/utils/patches.py`, « Image.open = image_open ») attrape
    TOUTE exception pour appeler `check_requirements("pi-heif")` — c'est-à-dire lancer un
    `pip install` depuis le réseau, au milieu d'une requête, avant de réessayer.

    Trois conséquences, et la première suffit à trancher : un serveur ne va pas chercher
    un décodeur sur Internet parce qu'une image est illisible, sur une entrée que
    l'appelant contrôle. La deuxième s'est vue ici même — nos refus délibérés
    ressortaient en `ModuleNotFoundError: pi_heif`, l'installation échouant toujours dans
    une image sans réseau. La troisième : le format apporté (HEIC) n'est pas dans
    `FORMATS_IMAGE`, donc on paierait un décodeur pour un format qu'on refuse.

    Le test n'exige PAS qu'ultralytics soit installé : ce qui doit tenir, c'est qu'à
    aucun moment de la vie du processus `Image.open` ne soit l'enveloppe. Sans le moteur,
    la question ne se pose pas — et l'assertion reste vraie, ce qui est le bon
    comportement pour une garde.
    """
    assert Image.open.__module__.startswith("PIL"), (
        f"`PIL.Image.open` a été remplacé par {Image.open.__module__} — "
        "un décodeur peut s'installer tout seul à l'exécution")


def test_le_chargeur_de_bulles_restaure_Image_open(monkeypatch):
    """La garde précédente dit l'état ; celle-ci dit que notre code le RÉTABLIT.

    On simule le patch plutôt que de charger le modèle : le télécharger prendrait des
    minutes et exigerait le réseau, alors que ce qu'on éprouve est trois lignes de
    `_load_model`. La doublure reproduit exactement ce que fait ultralytics — rebinder
    `Image.open` — et le test échoue si notre restauration disparaît.
    """
    import pipeline.bulles as bulles

    if not bulles.bulles_available():
        pytest.skip("ultralytics absent : `_load_model` refuserait avant d'importer")

    faux = lambda *a, **k: None                       # noqa: E731 — doublure du patch
    monkeypatch.setattr(Image, "open", faux)
    # `_load_model` capture `Image.open` AVANT d'importer ultralytics puis restaure : avec
    # notre doublure en place, il doit remettre `faux`, pas laisser autre chose.
    monkeypatch.setattr(bulles, "_model", None)
    try:
        bulles._load_model()
    except Exception:
        pass                                          # le téléchargement peut échouer
    assert Image.open is faux, (
        "`_load_model` n'a pas restauré `Image.open` : le patch d'ultralytics tient encore")


def test_l_import_ShareDocs_refuse_AUSSI_et_ne_laisse_rien(client, album, data_dir,
                                                           monkeypatch):
    """Le SECOND point d'entrée vers `corpus/`, que le module ne mesurait pas.

    Deux chemins écrivent dans le corpus — la route d'upload et l'import ShareDocs — et
    ils ont chacun leur gestion d'erreur. N'en éprouver qu'un laisse l'autre reposer sur
    la lecture du code, ce qui est précisément la substitution que ce dépôt refuse.

    L'enjeu n'est pas seulement le refus : c'est qu'aucun fichier ne RESTE. Kumiko reçoit
    un CHEMIN et décode avec OpenCV, hors de toute garde Pillow — un master forgé qui
    survivrait à l'ingest serait relu par lui à la première segmentation.
    """
    import pipeline.sharedocs as sd

    monkeypatch.setattr(sd, "download",
                        lambda chemin, *, principal, compte=None: _psd_minimal(8, 8))
    fichiers = lambda: {p for p in Path(data_dir / "corpus").rglob("*") if p.is_file()}
    avant = fichiers()

    r = client.post("/api/sharedocs/importer",
                    json={"album_id": album["id"], "chemins": ["dossier/planche.tif"]},
                    headers=ADMIN)
    # Le lot répond 200 : un fichier en échec ne stoppe pas les autres. C'est le CONTENU
    # de la réponse qui porte le refus, et c'est ce qu'il faut lire.
    assert r.status_code == 200, r.text
    corps = r.json()
    assert not corps.get("importes"), corps
    assert corps.get("erreurs"), "le PSD forgé est passé pour une planche valide"
    assert fichiers() == avant, (
        f"master forgé laissé sur disque : {sorted(fichiers() - avant)}")
