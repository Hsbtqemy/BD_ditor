"""L'annulation rafraîchit-elle l'écran, ou faut-il recharger ? (UX-15)

Relevé par l'équipe le 2026-09-14 en jouant `qa/normaliser-casse` : « Ctrl+Z fonctionne
bien, mais ça n'actualise pas la modification ; il faut recharger pour le voir ».

La LECTURE du code dit l'inverse, à chaque maillon : le serveur renvoie `region_id` et
`planche_id` (`undo.annuler`), le client appelle `loadRegions()` puis `renderPanel()`, et
`renderPanel()` écrit le texte dans `#ocr-text` (`static/viewer.js:453`). Quand chaque
maillon paraît juste et que l'écran dit non, continuer à relire est le mauvais réflexe :
c'est la mesure qui tranche.

Le test suit le geste de la passe à la lettre — normaliser une bulle en Transcription,
quitter, annuler — et regarde l'écran SANS recharger. Il mesure DEUX moments, parce que le
second ne veut rien dire si le premier est déjà faux : ce que le panneau affiche au retour
de la Transcription, puis ce qu'il affiche après l'annulation.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

# AUTH-2 : `ECRITURE` monte le décor avec les droits qu'il faut (sans effet hors proxy),
# et SEC-2 y ajoute l'en-tête anti-CSRF qu'un navigateur enverrait.
from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

CAPITALES = "BONJOURXYZ"
NORMALISE = "Bonjourxyz"


@pytest.fixture
def bulle_capitale(live_server):
    """Album + planche + case + bulle dont l'OCR est INTÉGRALEMENT capital.

    C'est la condition pour que « Normaliser la casse » soit offert : la garde `only_upper`
    de NLP-3 éteint le bouton dès qu'une minuscule traîne. Un décor en casse mixte ferait
    passer ce test pour vert en ne cliquant jamais rien.
    """
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "E2E undo"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        cid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "case", "x": 10, "y": 10, "w": 80, "h": 60}).json()["id"]
        # `timeout` généreux ICI : écrire l'OCR déclenche la réindexation, donc le
        # chargement À FROID de spaCy s'il est installé (~10 s, cf. le décor d'a11y).
        bid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 15, "y": 15, "w": 30, "h": 20,
                           "parent_id": cid, "ocr_texte": CAPITALES},
                     timeout=180).json()["id"]
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid, "region": bid}


def test_annuler_rafraichit_le_panneau_sans_recharger(page, bulle_capitale):
    s = bulle_capitale
    page.goto(f"{s['base']}/?album={s['album']}&planche={s['planche']}&region={s['region']}",
              wait_until="networkidle")
    ocr = page.locator("#ocr-text")
    expect(ocr).to_have_text(CAPITALES, timeout=15000)

    # Par le BOUTON et non la touche `T` : la touche insère son caractère dans la zone de
    # saisie qui vient de recevoir le focus — défaut mesuré le 2026-09-14 et éprouvé par
    # le test suivant. Entrer au clavier fausserait la mesure qu'on vient chercher ici.
    page.locator('button[data-mode="transcription"]').click()
    expect(page.locator("#transcription")).to_be_visible(timeout=15000)
    expect(page.locator("#tr-text")).to_have_value(CAPITALES, timeout=15000)

    page.locator("#tr-casse").click()
    expect(page.locator("#tr-text")).to_have_value(NORMALISE, timeout=15000)
    # L'écriture passe par le même chemin qu'une frappe, donc par la réindexation.
    expect(page.locator("#tr-save")).to_have_text("Enregistré", timeout=180000)

    # Par le BOUTON, délibérément : la sortie au clavier a sa propre mesure plus bas, et
    # ce test-ci ne doit dépendre que du geste qu'il éprouve — l'annulation.
    page.locator("#tr-exit").click()
    expect(page.locator("#transcription")).to_be_hidden()

    # PREMIER MOMENT — le panneau de l'Atelier montre-t-il le texte normalisé ? S'il
    # montrait encore les capitales ici, l'annulation ne serait pas en cause du tout.
    expect(ocr).to_have_text(NORMALISE, timeout=15000)

    # SECOND MOMENT — le geste de la passe : Ctrl+Z hors champ de saisie.
    page.keyboard.press("Control+z")
    expect(ocr).to_have_text(CAPITALES, timeout=15000)


def test_entrer_en_transcription_ne_tape_pas_dans_la_bulle(page, bulle_capitale):
    """La touche `T` ouvre la Transcription — elle ne doit pas écrire « t » dans la bulle.

    Trouvé DE BIAIS en montant le test ci-dessus, qui entrait par le clavier et lisait
    « BONJOURXYZt ». `setupKeyboard` appelle `setMode("transcription")` sans
    `preventDefault()` (`static/viewer.js`), et `renderTranscription()` donne aussitôt le
    focus à la zone de saisie : le caractère arrive dans un champ qui vient de naître.

    Ce n'est pas cosmétique. `trNext()` enregistre dès que la valeur diffère du stocké,
    si bien qu'un seul `Tab` PERSISTE la coquille dans `regions.ocr_texte`. Et c'est le
    chemin d'entrée que `pilotage/qa/normaliser-casse.md` prescrit noir sur blanc.
    """
    s = bulle_capitale
    page.goto(f"{s['base']}/?album={s['album']}&planche={s['planche']}&region={s['region']}",
              wait_until="networkidle")
    expect(page.locator("#ocr-text")).to_have_text(CAPITALES, timeout=15000)

    page.keyboard.press("t")
    expect(page.locator("#transcription")).to_be_visible(timeout=15000)
    expect(page.locator("#tr-text")).to_have_value(CAPITALES, timeout=15000)


def test_quitter_la_transcription_par_echap(page, bulle_capitale):
    """`Échap` quitte la Transcription, sans rien écrire dans la bulle.

    Le bouton annonçait « Quitter (N) », et ce raccourci-là ne pouvait PAS fonctionner :
    `renderTranscription()` focalise la zone de saisie, et `setupKeyboard` rend la main aux
    raccourcis natifs dès que le focus est dans un champ — sans quoi la lettre « n »
    deviendrait intapable. Mesuré le 2026-09-14 : la touche écrivait « n » dans la bulle et
    ne sortait pas. `Échap` était libre dans ce panneau, l'écouteur de la zone de saisie ne
    traitant que `Ctrl+Entrée` et `Tab`.

    Le test ne verrouille AUCUN libellé : il éprouve que le geste sort et n'écrit rien.
    Un test qui exigerait le texte du bouton deviendrait un miroir de la page.
    """
    s = bulle_capitale
    page.goto(f"{s['base']}/?album={s['album']}&planche={s['planche']}&region={s['region']}",
              wait_until="networkidle")
    page.locator('button[data-mode="transcription"]').click()
    expect(page.locator("#tr-text")).to_have_value(CAPITALES, timeout=15000)

    page.keyboard.press("Escape")
    expect(page.locator("#transcription")).to_be_hidden(timeout=15000)
    # Rien n'a été écrit : le panneau de l'Atelier montre le texte d'origine.
    expect(page.locator("#ocr-text")).to_have_text(CAPITALES)
