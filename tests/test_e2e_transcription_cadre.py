"""Le cadre du mode Transcription tient-il la bulle, ou la bulle dicte-t-elle le cadre ? (UX-15)

**Ce que cette garde retient.** Le 2026-09-14, une bulle haute chassait la zone de saisie,
les boutons et la barre d'aide hors de la fenêtre : `#transcription`, item d'une rangée
`1fr` — donc `minmax(auto, 1fr)` —, laissait son minimum automatique enfler la rangée, et
le crop DICTAIT la hauteur du panneau au lieu de la subir. Un panneau de 1 793 px dans une
fenêtre de 800. Corrigé par `464ab62` avec deux `min-height: 0` et un crop BORNÉ, et RETENU
PAR RIEN depuis : `#tr-crop` n'était éprouvé que masqué ou visible, jamais mesuré.

**Pourquoi un navigateur et non une lecture du CSS.** Les trois hypothèses avancées sur ce
défaut étaient fausses, et aucune relecture ne l'a montré — c'est un banc de mesure qui a
tranché, en jugeant seize situations d'un coup. Une règle CSS ne dit pas ce qu'une grille
en fait ; `getBoundingClientRect` si.

**Les deux largeurs, et pourquoi elles.** Le défaut ne dépendait PAS de la largeur,
contrairement au périmètre d'UX-7 (sous 1 000 px) — c'est ce qui fait de ce chantier un
chantier à part. Jouer 1280 ET 900 est donc la mesure qui le VÉRIFIE, et non une précaution
de style : si un jour l'un des deux tombait seul, la ligne de partage aurait bougé et il
faudrait le savoir.

**La hauteur est 800, et c'est un choix mesuré.** C'est la fenêtre où le banc du
2026-09-14 a relevé les 1 793 px. Le code d'aujourd'hui tient de 900 jusqu'à 400 px de
haut (mesuré le 2026-09-23, sept hauteurs × deux largeurs) ; prendre 900 rendrait la garde
plus confortable donc moins sensible, et prendre 400 la calerait sur une fenêtre que
personne n'utilise.

**Ce que la garde vérifie AVANT de conclure**, et c'est la leçon du semis d'AUTH-5 : un
panneau vide tiendrait dans n'importe quelle fenêtre. Chaque mesure commence donc par
établir que le crop est bien CHARGÉ et que c'est bien la grande bulle qu'on regarde.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

# AUTH-2 : le décor se monte avec les droits qu'il faut (sans effet hors proxy) ;
# SEC-2 y ajoute l'en-tête anti-CSRF qu'un navigateur poserait.
from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source. Le mode Transcription
# n'existe que dans l'Atelier ; les quatre autres surfaces n'ont pas de `#transcription`.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/recherche": "aucun mode Transcription : la page n'a ni crop, ni zone de saisie de bulle",
    "/corpus": "aucun mode Transcription : la page liste des albums, elle n'édite pas de bulle",
    "/exploration": "aucun mode Transcription : les panneaux d'analyse ne montrent aucun crop",
    "/administration": "aucun mode Transcription : la page porte sur l'instance, pas sur une planche",
}

# Le master est assez grand pour loger une bulle plus haute que n'importe quel cadre.
MASTER = (1200, 1600)
# 458 × 930, rapport 0,49 : la bulle EXACTE du signalement du 2026-09-14.
HAUTE = {"x": 100, "y": 60, "w": 458, "h": 930}
# Plus petite que le cadre aux deux largeurs, mesuré À LA HAUTEUR QUE CE MODULE JOUE : le
# cadre fait 771 × 438 à 1280 px et 528 × 438 à 900 px pour une fenêtre de 800 px de haut.
# Elle a donc la PLACE de grossir, ce qui est la condition pour que « elle ne grossit
# pas » veuille dire quelque chose — et la garde le revérifie à chaque passe plutôt que de
# s'en remettre à ce commentaire.
PETITE = {"x": 100, "y": 60, "w": 220, "h": 130}

HAUTEUR = 800
LARGEURS = [1280, 900]


@pytest.fixture
def corpus_deux_bulles(live_server):
    """Deux planches d'UNE bulle : la plus haute du corpus, et une plus petite que le cadre.

    Une bulle par planche, délibérément : `enterTranscription()` repart toujours de
    `trIndex = 0`, si bien qu'un décor à deux bulles sur la même planche ouvrirait sur
    celle du premier rang de lecture et non sur celle qu'on veut mesurer.
    """
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=60, headers=ECRITURE)
    out = {"base": live_server}
    try:
        aid = c.post("/api/albums", json={"titre": "E2E cadre transcription"}).json()["id"]
        out["album"] = aid
        for nom, bbox in (("haute", HAUTE), ("petite", PETITE)):
            pid = c.post(f"/api/albums/{aid}/import",
                         files={"file": (f"{nom}.png", make_png(*MASTER),
                                         "image/png")}).json()["id"]
            cid = c.post(f"/api/planches/{pid}/regions",
                         json={"type": "case", "x": 0, "y": 0,
                               "w": MASTER[0], "h": MASTER[1]}).json()["id"]
            # `timeout` généreux : écrire l'OCR déclenche la réindexation, donc le
            # chargement À FROID de spaCy s'il est installé (~10 s).
            rid = c.post(f"/api/planches/{pid}/regions",
                         json={"type": "bulle", "parent_id": cid,
                               "ocr_texte": "TEXTE", **bbox},
                         timeout=180).json()["id"]
            out[nom] = {"planche": pid, "region": rid}
    finally:
        c.close()
    return out


def _ouvrir_en_transcription(page, corpus, quoi):
    """Ouvre l'Atelier sur une bulle, entre en Transcription, attend que le crop SOIT LÀ.

    Par le BOUTON et non par la touche `T` : la touche a son propre défaut mesuré
    (`test_e2e_undo_rafraichit`), et une garde de mise en page n'a pas à en dépendre.
    """
    s = corpus[quoi]
    page.goto(f"{corpus['base']}/?album={corpus['album']}&planche={s['planche']}"
              f"&region={s['region']}", wait_until="networkidle")
    page.wait_for_selector("#ocr-text", timeout=15000)
    page.locator('button[data-mode="transcription"]').click()
    page.wait_for_selector("#transcription:not([hidden])", timeout=15000)
    # Le crop CHARGÉ, et pas seulement l'élément présent : une image encore vide n'occupe
    # aucune place, et le panneau tiendrait alors dans n'importe quelle fenêtre. C'est le
    # mode d'échec du SEMIS d'AUTH-5 — un vert qui ne mesure rien.
    page.wait_for_function(
        "() => { const c = document.querySelector('#tr-crop');"
        " return c && c.complete && c.naturalWidth > 0; }", timeout=20000)


_MESURE = """() => {
  const b = (sel) => { const e = document.querySelector(sel);
    if (!e) return null; const r = e.getBoundingClientRect();
    return {haut: Math.round(r.top), bas: Math.round(r.bottom),
            largeur: Math.round(r.width), hauteur: Math.round(r.height)}; };
  const crop = document.querySelector('#tr-crop');
  return {fenetre: window.innerHeight,
          saisie: b('#tr-text'), boutons: b('#tr-controls'), aide: b('.tr-hint'),
          cadre: b('#tr-crop-wrap'), crop: b('#tr-crop'), barre: b('#statusbar'),
          naturel: {largeur: crop.naturalWidth, hauteur: crop.naturalHeight}};
}"""


@pytest.mark.parametrize("largeur", LARGEURS)
def test_la_bulle_la_plus_haute_ne_chasse_rien_hors_de_la_fenetre(
        page, corpus_deux_bulles, largeur):
    """Zone de saisie, boutons et barre d'aide restent VISIBLES sous la plus haute bulle.

    Le critère n'est pas « dans la fenêtre » mais « au-dessus de la barre d'état » : la
    barre occupe la dernière rangée de la grille, et un panneau qui la recouvrirait
    tiendrait encore dans `innerHeight` tout en cachant ce qu'on vient y lire. Les deux
    conditions sont écrites séparément pour que le message dise laquelle a cédé.
    """
    page.set_viewport_size({"width": largeur, "height": HAUTEUR})
    _ouvrir_en_transcription(page, corpus_deux_bulles, "haute")
    m = page.evaluate(_MESURE)

    # C'est bien la grande bulle qu'on mesure — sans quoi la garde pourrait passer sur
    # n'importe quel crop et ne dirait plus rien du cas qu'elle retient.
    assert (m["naturel"]["largeur"], m["naturel"]["hauteur"]) == (HAUTE["w"], HAUTE["h"]), (
        f"le crop chargé fait {m['naturel']} au lieu de {HAUTE['w']}×{HAUTE['h']} : ce "
        "n'est pas la bulle du signalement, la mesure ne porte pas sur le bon cas")
    assert m["crop"]["hauteur"] > 0, "le crop n'occupe aucune place : rien n'est mesuré"

    for nom in ("saisie", "boutons", "aide"):
        assert m[nom]["bas"] <= m["fenetre"], (
            f"à {largeur}×{HAUTEUR}, « {nom} » descend à {m[nom]['bas']} px pour une "
            f"fenêtre de {m['fenetre']} px : la bulle dicte de nouveau la hauteur du "
            "panneau au lieu de la subir. Deux réglages la retiennent, et un seul a "
            "jamais été coupable : le `min-height: 0` de `#transcription`, ou la borne "
            "de `#tr-crop`. Celui de `#tr-right` est REDONDANT — zéro écart sur 64 "
            "combinaisons, mesuré le 2026-09-23 — et l'accuser ferait perdre du temps")
        assert m[nom]["bas"] <= m["barre"]["haut"], (
            f"à {largeur}×{HAUTEUR}, « {nom} » descend à {m[nom]['bas']} px et recouvre "
            f"la barre d'état, qui commence à {m['barre']['haut']} px")


@pytest.mark.parametrize("largeur", LARGEURS)
def test_une_bulle_plus_petite_que_le_cadre_n_est_pas_agrandie(
        page, corpus_deux_bulles, largeur):
    """Un crop de master n'est jamais étiré : agrandir n'ajoute pas d'information, du flou.

    `width/height: 100%` + `object-fit: contain` remplissait la boîte, donc grossissait les
    petites bulles — jusqu'à ×6 sur le banc, et le 317 % relevé à l'écran. Sans cette
    mesure, un futur `width: 100%` rétablirait le flou sans faire tomber quoi que ce soit.

    La garde vérifie d'abord que le cadre est PLUS GRAND que la bulle : « elle n'a pas
    grossi » ne veut rien dire là où il n'y avait pas la place de grossir.
    """
    page.set_viewport_size({"width": largeur, "height": HAUTEUR})
    _ouvrir_en_transcription(page, corpus_deux_bulles, "petite")
    m = page.evaluate(_MESURE)

    assert (m["naturel"]["largeur"], m["naturel"]["hauteur"]) == (PETITE["w"], PETITE["h"]), (
        f"le crop chargé fait {m['naturel']} au lieu de {PETITE['w']}×{PETITE['h']}")
    assert (m["cadre"]["largeur"] > m["naturel"]["largeur"]
            and m["cadre"]["hauteur"] > m["naturel"]["hauteur"]), (
        f"à {largeur}×{HAUTEUR} le cadre fait {m['cadre']['largeur']}×"
        f"{m['cadre']['hauteur']} pour une bulle de {m['naturel']['largeur']}×"
        f"{m['naturel']['hauteur']} : il n'y a pas la place de l'agrandir, donc cette "
        "garde ne mesure plus rien. Réduire la bulle du décor, ou agrandir la fenêtre")

    assert m["crop"]["largeur"] == m["naturel"]["largeur"], (
        f"à {largeur}×{HAUTEUR}, la bulle est rendue sur {m['crop']['largeur']} px de "
        f"large pour {m['naturel']['largeur']} px de master : elle est AGRANDIE, donc "
        "floue. Le crop doit être BORNÉ (`max-width`/`max-height`), jamais étiré")
    assert m["crop"]["hauteur"] == m["naturel"]["hauteur"], (
        f"à {largeur}×{HAUTEUR}, la bulle est rendue sur {m['crop']['hauteur']} px de "
        f"haut pour {m['naturel']['hauteur']} px de master : elle est AGRANDIE")
