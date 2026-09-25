"""AUTH-11 — l'écran 📖 Lexique dit les lignes qu'un import de vocabulaire a REFUSÉES.

`POST /api/lexique/importer` compte depuis AUTH-11 les lignes refusées par motif
(`resume.refusees`), et l'écran ne les lisait pas : un import dont toutes les lignes étaient
refusées annonçait « Import : 0 domaine(s), 0 dimension(s), 0 valeur(s) créé(s) », puis
empilait un toast par ligne. Aucun test d'API ne le voyait — la réponse était juste, c'est
la PHRASE qui mentait. Ce module joue le geste sous l'identité concernée, derrière le proxy :
en mono-poste la portée est totale et aucune ligne n'est jamais refusée.

Le décor : Bob écrit dans « Étude A », lit « Étude C », ne voit pas « Étude B ». Un domaine
et une dimension vivent dans B (invisibles pour lui : « libellé déjà pris »), une dimension
sans note vit dans C (lui en écrire une : « en lecture seule pour vous »).
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/exploration",)
SURFACES_HORS_PERIMETRE = {
    "/": "l'Atelier annote une planche ; l'import de vocabulaire n'y vit pas",
    "/corpus": "la Bibliothèque gère albums et collections ; aucun import de vocabulaire",
    "/recherche": "la Recherche interroge le corpus ; aucun import de vocabulaire",
    "/administration": "l'Administration règle l'instance ; aucun import de vocabulaire",
}

_ENTETE = ("domaine;domaine_definition;cible;dimension;dimension_definition;"
           "dimension_note_portee;valeur;valeur_definition\n")
# Trois lignes, trois refus : un domaine caché sous lequel naîtrait une dimension, une
# dimension cachée, une note posée sur une dimension en lecture seule.
_REFUSEES = ("Champ B;;case;autre axe;;;;", ";;case;axe b;;;;", ";;case;axe lu;;note bob;;")


def _csv(*lignes):
    return (_ENTETE + "".join(l + "\n" for l in lignes)).encode("utf-8")


@pytest.fixture
def decor(live_server):
    admin = {**ECRITURE, "Remote-User": "decor", "Remote-Groups": "bd-admins"}
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=admin) as c:
        ids = {}
        for nom in ("Étude A", "Étude B", "Étude C"):
            r = c.post("/api/collections", json={"nom": nom})
            assert r.status_code in (200, 201), r.text
            ids[nom] = r.json()["id"]
        # Douze axes dans A, que Bob lit : la modale DÉFILE, comme sur un vrai vocabulaire,
        # et un bilan posé en bas sans y ramener la vue resterait hors de l'écran.
        for nom, lignes in (("Étude A", [f";;case;axe {i};;;;" for i in range(12)]),
                            ("Étude B", ["Champ B;;case;axe b;;;val b;"]),
                            ("Étude C", [";;case;axe lu;;;;"])):
            r = c.post("/api/lexique/importer",
                       files={"file": ("v.csv", _csv(*lignes), "text/csv")},
                       data={"collection_id": str(ids[nom])})
            assert r.status_code == 200, r.text
        # « lectrice » ne fait que lire C : elle n'écrit nulle part.
        for qui, nom, niveau in (("bob", "Étude A", "ecriture"), ("bob", "Étude C", "lecture"),
                                 ("lectrice", "Étude C", "lecture")):
            r = c.put(f"/api/collections/{ids[nom]}/acces", json={
                "genre": "utilisateur", "principal": qui, "niveau": niveau})
            assert r.status_code == 200, r.text
    return {"base": live_server, "a": ids["Étude A"], "c": ids["Étude C"]}


def _importer(page, decor, contenu):
    """Le geste : ouvrir 📖 Lexique sous Bob, choisir « Étude A », déposer le fichier."""
    page.set_extra_http_headers({"Remote-User": "bob"})
    page.goto(decor["base"] + "/exploration", wait_until="networkidle")
    page.click("#btn-lexique")
    page.locator(f"#lex-import-portee option[value='{decor['a']}']").wait_for(state="attached")
    page.select_option("#lex-import-portee", str(decor["a"]))
    with page.expect_response(lambda r: r.url.endswith("/api/lexique/importer")) as rep:
        page.set_input_files("#lex-import-file", files=[
            {"name": "voc.csv", "mimeType": "text/csv", "buffer": contenu}])
    assert rep.value.status == 200, rep.value.text()
    bilan = page.locator("#lex-import-bilan")
    bilan.locator("p").wait_for()
    return bilan


# Compté À L'INSTANT, sans réessai : `expect(...).to_have_count(1)` attend jusqu'à 5 s, et
# des toasts par ligne (4 s) auraient le temps de s'effacer — la garde passerait en
# regardant l'écran APRÈS le défaut (mesuré : le mutant qui les rétablit survivait).
_TOASTS_A_L_INSTANT = "() => document.querySelectorAll('#toasts .toast').length"


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_import_partiel_dit_ses_lignes_refusees_par_motif(page, decor):
    """La case de la fiche : trois lignes refusées se disent « 3 lignes refusées », par
    motif, dans la synthèse — et UN toast, pas un par ligne. Le motif « libellé déjà pris »
    reste ce qu'il est : l'écran ne dit pas où le libellé est pris."""
    bilan = _importer(page, decor, _csv(";;case;axe deux;;;w1;", *_REFUSEES))
    synthese = ("Import : 0 domaine, 1 dimension, 1 valeur créés. 3 lignes refusées : "
                "libellé déjà pris (2), en lecture seule pour vous (1).")
    expect(bilan.locator("p")).to_have_text(synthese)
    expect(bilan.locator("li")).to_have_count(3)
    expect(bilan.locator("li").nth(2)).to_contain_text("en lecture seule pour vous")
    assert page.evaluate(_TOASTS_A_L_INSTANT) == 1, "un toast par ligne est revenu"
    toasts = page.locator("#toasts .toast")
    expect(toasts).to_have_text(synthese)
    # Un import partiel n'est ni un succès sans reste, ni un échec : ton neutre.
    expect(toasts).not_to_have_class("toast success")
    expect(toasts).not_to_have_class("toast error")
    assert not any(m in bilan.inner_text().lower()
                   for m in ("caché", "cachée", "autre collection"))


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_import_tout_refuse_ne_ressemble_pas_a_un_succes(page, decor):
    """Rien n'est entré : la synthèse ne dit pas « 0 créé » mais « Rien n'a été importé »,
    sur le ton d'une erreur. Et un gros fichier ne rend pas treize messages : dix, puis le
    compte de ce qui n'est pas montré."""
    lignes = list(_REFUSEES) + [";;case;axe b;;;;" for _ in range(10)]
    bilan = _importer(page, decor, _csv(*lignes))
    expect(bilan.locator("p")).to_have_text(
        "Rien n'a été importé. 13 lignes refusées : libellé déjà pris (12), "
        "en lecture seule pour vous (1).")
    expect(bilan.locator("li")).to_have_count(11)
    expect(bilan.locator("li").last).to_have_text("… et 3 autres.")
    assert page.evaluate(_TOASTS_A_L_INSTANT) == 1, "un toast par ligne est revenu"
    expect(page.locator("#toasts .toast")).to_have_class("toast error")
    expect(bilan).to_be_in_viewport()


def _ouvrir_lexique(page, decor, qui):
    page.set_extra_http_headers({"Remote-User": qui})
    page.goto(decor["base"] + "/exploration", wait_until="networkidle")
    page.click("#btn-lexique")
    page.locator("#lex-body .lex-group").first.wait_for()
    return page.locator("#lex-import-portee")


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_le_menu_importer_dans_n_offre_que_les_collections_ou_l_on_ecrit(page, decor):
    """AUTH-12 a posé `ecrivable` dans `GET /api/collections`, et la modale d'album s'en
    sert. Le menu « Importer dans » proposait toutes les collections LUES : Bob y trouvait
    « Étude C », qu'il ne fait que lire, et l'import répondait « Collection introuvable »."""
    menu = _ouvrir_lexique(page, decor, "bob")
    # Le menu se remplit après /api/moi : attendre la collection écrite avant de compter.
    expect(menu.locator(f"option[value='{decor['a']}']")).to_have_count(1)
    valeurs = menu.locator("option").evaluate_all("(os) => os.map((o) => o.value)")
    assert str(decor["c"]) not in valeurs, "une collection seulement LUE est proposée"
    assert valeurs == ["", str(decor["a"])], valeurs
    expect(menu).to_be_visible()
    expect(page.locator("#lex-import")).to_be_visible()
    expect(page.locator("#lex-import-note")).to_be_hidden()


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_qui_n_ecrit_nulle_part_lit_pourquoi_le_menu_est_ferme(page, decor):
    """Sans collection où écrire, l'import est refusé partout — même « Global », qui exige
    d'écrire quelque part. L'écran le DIT dans une note visible, et retire le menu et le
    bouton plutôt que de les désactiver : un contrôle `disabled` ne prend pas le focus, et
    l'explication qu'il porterait resterait hors d'atteinte au clavier."""
    menu = _ouvrir_lexique(page, decor, "lectrice")
    note = page.locator("#lex-import-note")
    expect(note).to_be_visible()
    expect(note).to_contain_text("Vous n'écrivez dans aucune collection")
    expect(menu).to_be_hidden()
    expect(page.locator("#lex-import")).to_be_hidden()


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_le_menu_garde_la_collection_choisie_apres_un_import(page, decor):
    """Le menu se reremplit à chaque rechargement du lexique — après un import, un
    domaine changé. Il revenait à « Global » : on importait dans « Étude A », on lisait
    « 3 lignes refusées », on corrigeait le fichier, et le réimport partait en GLOBAL,
    ses termes visibles de toute l'instance, sans qu'on ait rien choisi."""
    _importer(page, decor, _csv(";;case;axe garde;;;;"))
    menu = page.locator("#lex-import-portee")
    expect(menu).to_have_value(str(decor["a"]))
    # Un second import sans retoucher le menu : le terme doit naître dans A, pas en global.
    with page.expect_response(lambda r: r.url.endswith("/api/lexique/importer")) as rep:
        page.set_input_files("#lex-import-file", files=[
            {"name": "voc.csv", "mimeType": "text/csv", "buffer": _csv(";;case;axe garde 2;;;;")}])
    assert rep.value.status == 200, rep.value.text()
    admin = {**ECRITURE, "Remote-User": "decor", "Remote-Groups": "bd-admins"}
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30, headers=admin) as c:
        dims = {d["nom"]: d for d in c.get("/api/lexique").json()["dimensions"]}
    assert dims["axe garde 2"]["collection_id"] == decor["a"], dims["axe garde 2"]
    expect(menu).to_have_value(str(decor["a"]))


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_import_en_echec_efface_le_bilan_precedent(page, decor):
    """Le bilan d'un import réussi, laissé sous un import qui échoue, se lirait comme le
    résultat du second. Le masquer est la seule façon de ne pas mentir."""
    bilan = _importer(page, decor, _csv(";;case;axe avant;;;;"))
    expect(bilan).to_be_visible()
    with page.expect_response(lambda r: r.url.endswith("/api/lexique/importer")) as rep:
        page.set_input_files("#lex-import-file", files=[   # en-tête sans `cible` : 400
            {"name": "voc.csv", "mimeType": "text/csv", "buffer": b"dimension\naxe\n"}])
    assert rep.value.status == 400
    expect(page.locator("#toasts .toast.error", has_text="Import échoué")).to_have_count(1)
    expect(bilan).to_be_hidden()

@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_rattachement_refuse_ne_laisse_pas_le_selecteur_mentir(page, decor):
    """AUTH-11, 2026-09-24 — un rattachement qui déplacerait une portée est refusé (409 de
    `PATCH …/domaine` : ranger d'abord la dimension dans la collection du domaine). Le
    toast le disait, mais le sélecteur de domaine du 📖 Lexique restait sur le domaine
    choisi, alors que rien n'était enregistré : l'écran affichait un rattachement qui
    n'existait pas, jusqu'au rechargement suivant. Après le refus, il montre de nouveau
    ce qu'il montrait avant — « Hors domaine » pour une dimension orpheline, son domaine
    pour une dimension déjà rangée — et la base le confirme.

    Troisième cas, celui qui départage « ce qui est en base » de « ce qui était affiché » :
    une dimension de A rangée sous un domaine CACHÉ à Bob (d'une collection qu'il ne lit
    pas). Son domaine n'est pas une option du sélecteur, qui affiche donc « Hors domaine » ;
    y remettre l'identifiant en base ne sélectionnerait RIEN (`selectedIndex` à -1). Le
    refus vient ici d'un domaine d'une collection D où Bob écrit aussi."""
    admin = {**ECRITURE, "Remote-User": "decor", "Remote-Groups": "bd-admins"}
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30, headers=admin) as c:
        dom = c.post("/api/domaines", json={"nom": "champ de a"}).json()
        assert c.patch(f"/api/domaines/{dom['id']}/lexique",
                       json={"collection_id": decor["a"]}).status_code == 200
        commun = c.post("/api/domaines", json={"nom": "champ commun"}).json()   # global
        dims = {  # deux dimensions GLOBALES : l'une orpheline, l'autre sous le domaine global
            "axe orphelin": c.post("/api/attributs/dimensions",
                                   json={"cible": "case", "nom": "axe orphelin"}).json(),
            "axe range": c.post("/api/attributs/dimensions",
                                json={"cible": "case", "nom": "axe range",
                                      "domaine_id": commun["id"]}).json()}
        ids = {}
        for nom in ("Étude D", "Étude E"):          # Bob écrit dans D, ne voit pas E
            r = c.post("/api/collections", json={"nom": nom})
            assert r.status_code in (200, 201), r.text
            ids[nom] = r.json()["id"]
        assert c.put(f"/api/collections/{ids['Étude D']}/acces", json={
            "genre": "utilisateur", "principal": "bob",
            "niveau": "ecriture"}).status_code == 200
        dom_d = c.post("/api/domaines", json={"nom": "champ de d"}).json()
        cache = c.post("/api/domaines", json={"nom": "champ cache"}).json()
        for d_id, coll in ((dom_d["id"], ids["Étude D"]), (cache["id"], ids["Étude E"])):
            assert c.patch(f"/api/domaines/{d_id}/lexique",
                           json={"collection_id": coll}).status_code == 200
        sous_cache = c.post("/api/attributs/dimensions",   # naît dans E, sous son domaine
                            json={"cible": "case", "nom": "axe sous cache",
                                  "domaine_id": cache["id"]}).json()
        assert c.patch(f"/api/attributs/dimensions/{sous_cache['id']}/lexique",
                       json={"collection_id": decor["a"]}).status_code == 200   # rangée dans A
        dims["axe sous cache"] = sous_cache
    attendu = {"axe orphelin": ("champ de a", "", "Hors domaine", None),
               "axe range": ("champ de a", str(commun["id"]), "champ commun", commun["id"]),
               "axe sous cache": ("champ de d", "", "Hors domaine", cache["id"])}
    _ouvrir_lexique(page, decor, "bob")
    for nom, (cible, valeur, libelle, en_base) in attendu.items():
        terme = page.locator(".lex-term:not(.lex-domaine)",
                             has=page.locator(".lex-name", has_text=nom))
        terme.locator("summary").click()
        sel = terme.locator('select[data-f="domaine_id"]')
        with page.expect_response(lambda r: "/domaine" in r.url
                                  and r.request.method == "PATCH") as rep:
            sel.select_option(label=cible)
        assert rep.value.status == 409, rep.value.text()
        expect(page.locator("#toasts .toast.error").last).to_contain_text("Rangez d'abord")
        expect(sel).to_have_value(valeur)
        expect(sel.locator("option:checked")).to_have_text(libelle)
        with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30,
                          headers=admin) as c:
            d = next(x for x in c.get("/api/attributs/dimensions").json()
                     if x["id"] == dims[nom]["id"])
        assert d["domaine_id"] == en_base, nom
