"""Un libellé de l'Atelier annonce-t-il une touche que le focus rend impossible ? (UX-15)

**D'où vient cette garde.** Le bouton de sortie du mode Transcription annonçait
« Quitter (N) », et ce raccourci ne pouvait PAS fonctionner : `renderTranscription()`
focalise la zone de saisie, et `setupKeyboard` rend la main aux raccourcis natifs dès que
le focus est dans un champ — sans quoi la lettre « n » deviendrait intapable. La touche
écrivait « n » dans la bulle et ne sortait pas. Aucun test ne pouvait l'attraper, parce
qu'aucun test ne lisait ce qu'un bouton PROMET ; et le défaut n'a pas été cherché, il
s'est mis en travers du chemin d'une autre mesure. Rien ne garantissait qu'il fût seul.

**Ce que la garde fait, et ce qu'elle ne fait pas.** Elle RECENSE tout ce que l'Atelier
annonce comme touche, et exige que chaque annonce soit déclarée ici — jouée, ou écartée
avec sa raison. C'est le patron de `HORS_PERIMETRE` dans `test_autorisation` et de
`SURFACES_HORS_PERIMETRE` dans `tests/surfaces.py` : on ne ferme pas la porte de l'erreur,
on ferme celle de l'OUBLI. Elle ne dit pas qu'un raccourci est bien choisi, ni qu'il est
découvrable ; elle dit qu'aucune annonce ne dort sans qu'on l'ait regardée.

**La clé est le COUPLE (porteur, touche), et c'est ce qui la rend utile.** Une déclaration
par touche seule laisserait passer exactement le défaut d'origine : « N » est légitimement
annoncé par le badge du mode Navigation, si bien qu'un bouton de sortie redevenu
« Quitter (N) » retomberait sur une entrée déjà déclarée et la garde resterait verte. En
nommant l'élément qui porte le libellé, l'annonce fautive devient une entrée INCONNUE.

**Et la sortie se joue sur la touche LUE à l'écran**, pas sur une touche écrite ici. Le
test demande au bouton ce qu'il annonce, traduit l'annonce en frappe et l'exécute : rendu
à « Quitter (N) », il presserait « n » et constaterait que le panneau reste ouvert. Un test
qui EXIGERAIT le libellé serait un miroir de la page — c'est l'écueil que
`test_e2e_undo_rafraichit` nomme —, celui-ci fait l'inverse : il ne pose aucune condition
sur le texte, il le CROIT et vérifie que l'écran tient parole.

**Ce que le recensement ne voit pas, écrit plutôt que supposé.** Il lit le DOM dans les
quatre modes, sur une planche à deux bulles dont une région est sélectionnée — sans quoi
les boutons de déplacement de l'arbre, qui ne s'affichent que sur le nœud courant,
n'existeraient pas. Une annonce qui n'apparaîtrait que dans un état non visité (un bandeau
de conflit, une modale) lui échapperait. Il lit AUSSI les libellés masqués sous l'overlay :
un libellé caché aujourd'hui se réaffiche demain, et la visibilité serait un critère qui
bouge tout seul. **Et le porteur ne distingue pas des FRÈRES de même classe** : les quatre
boutons de mode s'effondrent en un seul `button.mode-btn`, les deux flèches de l'arbre en
un seul `button.tn-mv`. Une touche qui migrerait d'un bouton de mode à un autre garderait
donc un couple déjà déclaré et resterait invisible ici. C'est étroit — les deux familles
sont des séries homogènes dont les membres promettent la même chose au même endroit — et
les distinguer demanderait au porteur de dépendre d'un `data-mode` ou d'un rang, c'est-à-
dire de casser dès qu'on réordonne les boutons.

**Le cliquet de la DÉCLARATION vit dans `tests/test_promesses_atelier.py`**, hors marqueur
`e2e`, avec `PROMESSES` et `CLAVIER` : il ne demande aucun navigateur et doit tourner dans
la suite par défaut. Ce module-ci ne garde que ce qui exige un écran.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402
from test_promesses_atelier import CLAVIER, PROMESSES  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/recherche": "aucun raccourci annoncé : la page n'a ni badge de mode ni barre d'aide clavier",
    "/corpus": "aucun raccourci annoncé : la page n'expose aucune touche dans ses libellés",
    "/exploration": "aucun raccourci annoncé : les panneaux d'analyse ne promettent aucune touche",
    "/administration": "aucun raccourci annoncé : la page ne porte aucun libellé de touche",
}


# -----------------------------------------------------------------------------
# Décor
# ---------------------------------------------------------------------------
@pytest.fixture
def planche_a_deux_bulles(live_server):
    """Une planche, une case, DEUX bulles : de quoi éprouver « suivante » et « précédente »."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=60, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "E2E promesses"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(1200, 1600),
                                     "image/png")}).json()["id"]
        cid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "case", "x": 0, "y": 0,
                           "w": 1200, "h": 1600}).json()["id"]
        # `timeout` généreux : l'écriture de l'OCR réindexe, donc charge spaCy à froid.
        premiere = c.post(f"/api/planches/{pid}/regions",
                          json={"type": "bulle", "parent_id": cid, "ocr_texte": "PREMIERE",
                                "x": 100, "y": 60, "w": 300, "h": 200},
                          timeout=180).json()["id"]
        seconde = c.post(f"/api/planches/{pid}/regions",
                         json={"type": "bulle", "parent_id": cid, "ocr_texte": "SECONDE",
                               "x": 600, "y": 400, "w": 300, "h": 200},
                         timeout=180).json()["id"]
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid,
            "premiere": premiere, "seconde": seconde}


def _atelier(page, s, region=None):
    cible = region or s["premiere"]
    page.goto(f"{s['base']}/?album={s['album']}&planche={s['planche']}&region={cible}",
              wait_until="networkidle")
    page.wait_for_selector("#ocr-text", timeout=15000)


def _transcription(page, s):
    """Entre par le BOUTON : la touche `T` a son propre défaut mesuré, on n'en dépend pas."""
    _atelier(page, s)
    page.locator('button[data-mode="transcription"]').click()
    expect(page.locator("#transcription")).to_be_visible(timeout=15000)
    expect(page.locator("#tr-text")).to_have_value("PREMIERE", timeout=15000)


# Recense les touches ANNONCÉES, et par QUI. Deux formes seulement, et c'est écrit :
#   — un `<kbd>`, dont c'est le sens même en HTML : son texte EST la touche ;
#   — une parenthèse dans un texte, un `title`, un `placeholder` ou un `aria-label`.
# Dans une parenthèse, un nom de touche à plusieurs lettres est reconnu où qu'il soit
# (« Tab ou Ctrl+Entrée = suivante ») ; une LETTRE seule ne l'est que si la parenthèse ne
# contient QU'elle. Sans cette restriction, « morph (UD) » annoncerait deux touches et
# « sigles pointés (F.B.I.) » trois — des recensements faux qu'on apprendrait à ignorer.
_RECENSEMENT = r"""() => {
  const MULTI = '(?:Tab|Entrée|Échap|Maj|Ctrl|Alt|Suppr|Espace|←|→|↑|↓)';
  const RE = new RegExp(MULTI + '(?:\\+(?:' + MULTI + '|[A-Z]))*', 'g');
  const vus = new Set();
  const porteur = (e) => {
    const p = e.closest('[id], [class]') || e;
    return p.id ? '#' + p.id
                : p.tagName.toLowerCase() + (p.classList.length ? '.' + p.classList[0] : '');
  };
  const ajoute = (e, touche) => { if (touche) vus.add(porteur(e) + '\u0000' + touche); };

  document.querySelectorAll('kbd').forEach((k) => ajoute(k, k.textContent.trim()));

  const parentheses = (e, txt) => {
    for (const m of txt.matchAll(/\(([^)]*)\)/g)) {
      const dedans = m[1].trim();
      if (/^[A-Z]$/.test(dedans)) { ajoute(e, dedans); continue; }
      for (const tk of (dedans.match(RE) || [])) ajoute(e, tk);
    }
  };
  document.querySelectorAll('*').forEach((e) => {
    // Seulement les nœuds de texte PROPRES à l'élément : sans cela, chaque ancêtre
    // re-déclarerait le libellé de ses descendants sous son propre nom.
    const propre = [...e.childNodes].filter((n) => n.nodeType === 3)
      .map((n) => n.textContent).join(' ');
    for (const txt of [propre, e.title, e.placeholder, e.getAttribute('aria-label')])
      if (txt && txt.includes('(')) parentheses(e, txt);
  });
  return [...vus];
}"""


def _recenser(page, s):
    """Les annonces vues dans les QUATRE modes, réunies."""
    _atelier(page, s)
    vues = set(page.evaluate(_RECENSEMENT))
    for mode in ("edition", "annotation", "transcription"):
        page.locator(f'button[data-mode="{mode}"]').click()
        page.wait_for_timeout(400)
        vues |= set(page.evaluate(_RECENSEMENT))
    page.keyboard.press("Escape")       # quitter la Transcription proprement
    return {tuple(v.split("\u0000", 1)) for v in vues}


# ---------------------------------------------------------------------------
# Le recensement
# ---------------------------------------------------------------------------
def test_aucune_touche_annoncee_n_echappe_a_la_declaration(page, planche_a_deux_bulles):
    """LE test de ce fichier : tout ce que l'écran promet est déclaré, dans les deux sens.

    Le sens ABSENT ferme l'oubli — une annonce neuve, ou déplacée sur un autre porteur,
    tombe rouge. Le sens FANTÔME ferme l'autre moitié : une déclaration qui survit au
    libellé qu'elle décrivait rassure, et les tests qui la jouent deviennent vacants.
    """
    vues = _recenser(page, planche_a_deux_bulles)
    assert vues, (
        "aucune touche annoncée détectée dans l'Atelier : le recensement ne reconnaît plus "
        "ni les `<kbd>` ni les parenthèses, et tout ce fichier est devenu vacant sans "
        "échouer — c'est le mode d'échec d'ARCH-2, une garde qui approuve en ne voyant rien")

    inconnues = sorted(vues - set(PROMESSES))
    assert not inconnues, (
        "l'Atelier annonce des touches que ce fichier ne déclare pas : "
        + " ; ".join(f"{p} → {t!r}" for p, t in inconnues)
        + ". Chacune doit être AJOUTÉE à `PROMESSES`, soit jouée par un test de ce "
        "fichier, soit écartée avec la raison de ne pas la jouer. Une annonce qu'aucun "
        "test ne presse est exactement « Quitter (N) » : elle a l'air vraie et elle "
        "peut être impossible")

    fantomes = sorted(set(PROMESSES) - vues)
    assert not fantomes, (
        "ce fichier déclare des annonces que l'Atelier ne fait plus : "
        + " ; ".join(f"{p} → {t!r}" for p, t in fantomes)
        + ". Soit le libellé a disparu — et la déclaration doit partir avec lui —, soit "
        "il a changé de porteur, et c'est précisément le déplacement qu'on veut voir")


# ---------------------------------------------------------------------------
# Les promesses, jouées
# ---------------------------------------------------------------------------
def test_le_bouton_de_sortie_tient_la_touche_qu_il_affiche(page, planche_a_deux_bulles):
    """On LIT la touche sur le bouton, puis on la presse depuis la zone de saisie.

    C'est le défaut d'origine, retenu à l'endroit exact où il s'était produit : rendu à
    « Quitter (N) », ce test presserait « n », verrait le panneau rester ouvert et la
    lettre s'ajouter au texte de la bulle. Il ne verrouille AUCUN libellé — changer
    « Échap » pour une autre touche réellement branchée le laisse vert.
    """
    _transcription(page, planche_a_deux_bulles)

    annonce = page.evaluate(
        "() => (document.querySelector('#tr-exit').textContent.match(/\\(([^)]*)\\)/)"
        " || [])[1]")
    assert annonce in CLAVIER, (
        f"le bouton de sortie annonce {annonce!r}, que ce test ne sait pas presser. "
        "Ajouter la traduction dans `CLAVIER` — une annonce qu'on ne sait pas jouer est "
        "une annonce qu'on ne peut pas éprouver, et c'est ainsi que « Quitter (N) » a vécu")

    page.locator("#tr-text").focus()
    page.keyboard.press(CLAVIER[annonce])
    expect(page.locator("#transcription")).to_be_hidden(timeout=15000)
    # Et elle ne laisse pas sa lettre derrière elle : c'était l'autre moitié du défaut.
    expect(page.locator("#ocr-text")).to_have_text("PREMIERE")


def test_la_barre_d_aide_tient_ses_promesses_de_navigation(page, planche_a_deux_bulles):
    """`Tab` suivante, `Maj+Tab` précédente, `Ctrl+Entrée` suivante — depuis le champ.

    Les trois sont jouées à la suite sur la même page : elles partagent l'écouteur de
    `#tr-text`, et les enchaîner éprouve en plus qu'aucune ne laisse le panneau dans un
    état d'où la suivante ne marcherait plus.
    """
    s = planche_a_deux_bulles
    _transcription(page, s)
    progres = page.locator("#tr-progress")
    expect(progres).to_have_text("Bulle 1 / 2")

    page.locator("#tr-text").focus()
    page.keyboard.press(CLAVIER["Tab"])
    expect(progres).to_have_text("Bulle 2 / 2", timeout=15000)
    expect(page.locator("#tr-text")).to_have_value("SECONDE")

    page.keyboard.press(CLAVIER["Maj+Tab"])
    expect(progres).to_have_text("Bulle 1 / 2", timeout=15000)
    expect(page.locator("#tr-text")).to_have_value("PREMIERE")

    page.keyboard.press(CLAVIER["Ctrl+Entrée"])
    expect(progres).to_have_text("Bulle 2 / 2", timeout=15000)


def test_entree_reste_un_retour_a_la_ligne(page, planche_a_deux_bulles):
    """La seule promesse du panneau qui demande à la touche de NE PAS être interceptée.

    Elle mérite d'être jouée pour cette raison même : une garde qui n'éprouverait que les
    touches détournées inviterait à détourner celle-ci aussi, et « Entrée retour ligne »
    deviendrait faux sans que rien ne tombe.
    """
    _transcription(page, planche_a_deux_bulles)
    champ = page.locator("#tr-text")
    champ.focus()
    page.keyboard.press(CLAVIER["Entrée"])
    page.keyboard.type("suite")

    expect(champ).to_have_value("PREMIERE\nsuite", timeout=15000)
    expect(page.locator("#tr-progress")).to_have_text("Bulle 1 / 2")


def test_les_badges_de_mode_tiennent_leur_promesse(page, planche_a_deux_bulles):
    """Les quatre `<kbd>` de la bande d'outils, joués depuis le corps de la page.

    **Ils ne sont PAS joués depuis la Transcription, et ce n'est pas un oubli.** Mesuré le
    2026-09-23 : le mode y focalise la zone de saisie à chaque rendu, si bien que `n`, `e`,
    `a` et `t` écrivent leur lettre dans la bulle — « BONJOUR » devient « BONJOURnea », et
    l'enregistrement automatique la persiste. C'est la même forme que « Quitter (N) », à
    ceci près que ces badges-là disent vrai dans les trois autres modes ; ce que la garde
    éprouve est donc la promesse là où elle vaut, et la question de ce que ces badges
    devraient afficher PENDANT la Transcription reste ouverte, consignée, non tranchée ici.

    `T` vient en dernier : une fois en Transcription, la touche suivante serait tapée dans
    la bulle au lieu de changer de mode — ce que ce commentaire vient de dire.
    """
    _atelier(page, planche_a_deux_bulles)
    mode = page.locator("#stat-mode")
    expect(mode).to_have_text("Mode : Navigation")

    for touche, attendu in (("E", "Édition"), ("A", "Annotation"),
                            ("N", "Navigation"), ("T", "Transcription")):
        page.keyboard.press(CLAVIER[touche])
        expect(mode).to_have_text(f"Mode : {attendu}", timeout=15000)
    expect(page.locator("#transcription")).to_be_visible()


def test_les_fleches_de_l_arbre_tiennent_leur_promesse(page, planche_a_deux_bulles):
    """`Alt+↑` / `Alt+↓` déplacent la région SÉLECTIONNÉE dans sa fratrie.

    Les deux boutons n'existent que sur le nœud courant, donc le décor ouvre sur la
    SECONDE bulle : c'est elle qui a une voisine au-dessus à dépasser.
    """
    s = planche_a_deux_bulles
    _atelier(page, s, region=s["seconde"])
    arbre = ("(() => [...document.querySelectorAll('#tree .tn-id')]"
             ".map((e) => e.textContent.trim()))")
    avant = page.evaluate(arbre)
    assert f"#{s['premiere']}" in avant and f"#{s['seconde']}" in avant, (
        f"l'arbre ne montre pas les deux bulles ({avant}) : la mesure porterait à vide")
    assert avant.index(f"#{s['premiere']}") < avant.index(f"#{s['seconde']}")

    page.keyboard.press(CLAVIER["Alt+↑"])
    page.wait_for_function(
        f"() => {{ const l = {arbre}(); "
        f"return l.indexOf('#{s['seconde']}') < l.indexOf('#{s['premiere']}'); }}",
        timeout=15000)

    page.keyboard.press(CLAVIER["Alt+↓"])
    page.wait_for_function(
        f"() => {{ const l = {arbre}(); "
        f"return l.indexOf('#{s['premiere']}') < l.indexOf('#{s['seconde']}'); }}",
        timeout=15000)
