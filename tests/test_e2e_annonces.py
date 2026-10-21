"""ANN-8 — la région des messages existe AVANT son premier message, sur les cinq surfaces.

`toast()` (static/lib/common.js) créait `#toasts` — `role="status"`, `aria-live="polite"` —
avec son PREMIER message. Une région live qui naît avec son contenu n'est pas annoncée de
façon fiable par les lecteurs d'écran ; et depuis ANN-6, ce premier message est souvent
« Rien n'est ajouté… », la seule réponse d'Entrée quand elle ne fait rien. `theme.js`, chargé
par les cinq gabarits, la pose désormais vide au chargement.

**Ce que ce fichier mesure, et ce qu'il ne mesure pas.** Il vérifie la condition que les
lecteurs d'écran demandent — la région est dans le document, vide, avec ses attributs, avant
tout message, et c'est elle que `toast()` remplit ensuite, sans en créer une seconde. Ce
qu'un lecteur d'écran PRONONCE ne se mesure pas ici : aucun n'est piloté par la suite, et la
case d'ANN-8 qui le demande reste ouverte pour cette moitié-là.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source : les cinq, sans exception —
# la région est posée par `theme.js`, que les cinq gabarits chargent.
SURFACES_AUDITEES = {
    "/": lambda d: f"/?album={d['album']}&planche={d['planche']}",
    "/recherche": lambda d: "/recherche",
    "/corpus": lambda d: "/corpus",
    "/exploration": lambda d: "/exploration",
    "/administration": lambda d: "/administration",
}
SURFACES_HORS_PERIMETRE = {}


@pytest.fixture
def decor(live_server):
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE) as c:
        aid = c.post("/api/albums", json={"titre": "E2E annonces"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
    return {"base": live_server, "album": aid, "planche": pid}


# Ce que la page a vu NAÎTRE, dans l'ordre : la région vide, puis un message dedans. Le
# relevé commence avant tout script de la page (`add_init_script`) : il dit si la région
# existait AVANT son premier message, ce qu'un état final ne dit pas.
_RELEVE = """(() => {
  window.__naissances = [];
  new MutationObserver((muts) => {
    for (const m of muts) for (const n of m.addedNodes) {
      if (n.nodeType !== 1) continue;
      if (n.id === 'toasts') window.__naissances.push('region:' + n.childElementCount);
      else if (n.classList && n.classList.contains('toast')) window.__naissances.push('message');
    }
  }).observe(document, {childList: true, subtree: true});
})();"""


@pytest.mark.parametrize("surface", list(SURFACES_AUDITEES))
def test_la_region_des_messages_precede_son_premier_message(page, decor, surface):
    page.add_init_script(_RELEVE)
    page.goto(decor["base"] + SURFACES_AUDITEES[surface](decor), wait_until="networkidle")
    region = page.locator("#toasts")
    expect(region).to_have_count(1)
    expect(region).to_have_attribute("role", "status")
    expect(region).to_have_attribute("aria-live", "polite")
    # Un premier message, comme l'écran en émet : il va DANS la région déjà là.
    page.evaluate("() => toast('Message de mesure')")
    expect(page.locator("#toasts .toast", has_text="Message de mesure")).to_have_count(1)
    expect(page.locator("#toasts")).to_have_count(1)
    naissances = page.evaluate("() => window.__naissances")
    assert naissances and naissances[0] == "region:0", (
        f"{surface} : la région n'est pas née vide avant le premier message — {naissances}")
    assert naissances.index("message") > 0, naissances


def test_l_annonce_d_un_conflit_a_sa_region_des_le_chargement(page, decor):
    """L'Atelier a une seconde région live, celle du bandeau de conflit (CONC-3) : elle
    aussi est là avant sa première annonce."""
    page.goto(decor["base"] + SURFACES_AUDITEES["/"](decor), wait_until="networkidle")
    zone = page.locator("#conflit-annonce")
    expect(zone).to_have_count(1)
    expect(zone).to_have_attribute("aria-live", "polite")
    expect(zone).to_have_text("")
