"""Sème un corpus de DÉMONSTRATION reproductible (aucun corpus réel n'est versionné).

Sert à (re)produire les exemples de `docs/exemples/` — cf. `tools/regenerer_exemples.py`,
qui orchestre semis → réindexation NLP → exports. Le contenu est fictif et neutre.

Écrit dans la base désignée par l'ENVIRONNEMENT (BD_DATA_DIR / BD_DB_PATH), via la vraie
API (validations + réindexation FTS/NLP + génération des dérivés) — à lancer sur une base
JETABLE, JAMAIS sur des données réelles :

    BD_DATA_DIR=/tmp/demo BD_DB_PATH=/tmp/demo/demo.sqlite \\
        python tools/semer_demo.py

Les planches sont des pages de couleur unie (PNG encodé en bibliothèque standard) : les
cases/bulles sont posées explicitement en coordonnées master, comme dans la visionneuse.
"""
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

LARGEUR, HAUTEUR = 1240, 1754
MARGE, GOUTTIERE = 40, 30


# --------------------------------------------------------------------------- #
# Image : PNG couleur unie, sans dépendance (IHDR + IDAT zlib + IEND).
# --------------------------------------------------------------------------- #
def _png(rgb) -> bytes:
    def bloc(typ, data):
        c = typ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", LARGEUR, HAUTEUR, 8, 2, 0, 0, 0)   # 8 bits, truecolor
    brut = (b"\x00" + bytes(rgb) * LARGEUR) * HAUTEUR                 # filtre 0 + pixels
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", ihdr)
            + bloc(b"IDAT", zlib.compress(brut, 6)) + bloc(b"IEND", b""))


def _grille(cols, rangs):
    """Rectangles (x, y, w, h) master d'une grille cols×rangs."""
    lc = (LARGEUR - 2 * MARGE - (cols - 1) * GOUTTIERE) // cols
    lr = (HAUTEUR - 2 * MARGE - (rangs - 1) * GOUTTIERE) // rangs
    return [(MARGE + c * (lc + GOUTTIERE), MARGE + r * (lr + GOUTTIERE), lc, lr)
            for r in range(rangs) for c in range(cols)]


def _bulle(rect, haut=110, marge=36):
    x, y, w, h = rect
    return (x + marge, y + marge, w - 2 * marge, haut)


# --------------------------------------------------------------------------- #
# Wrappers API.
# --------------------------------------------------------------------------- #
class _Api:
    def __init__(self, cli):
        self.cli = cli

    def post(self, chemin, **corps):
        r = self.cli.post(chemin, json=corps); r.raise_for_status(); return r.json()

    def put(self, chemin, **corps):
        r = self.cli.put(chemin, json=corps); r.raise_for_status()
        return r.json() if r.content else None

    def patch(self, chemin, **corps):
        self.cli.patch(chemin, json=corps).raise_for_status()

    def importer(self, album_id, rgb, numero):
        r = self.cli.post(f"/api/albums/{album_id}/import",
                          files={"file": (f"planche{numero}.png", _png(rgb), "image/png")},
                          data={"numero": str(numero)})
        r.raise_for_status(); return r.json()

    def case(self, planche_id, rect, ordre):
        x, y, w, h = rect
        return self.post(f"/api/planches/{planche_id}/regions",
                         type="case", x=x, y=y, w=w, h=h, ordre=ordre, source="manuel")

    def texte(self, planche_id, parent_id, rect, ocr, type_="bulle"):
        x, y, w, h = rect
        return self.post(f"/api/planches/{planche_id}/regions", type=type_, x=x, y=y,
                         w=w, h=h, parent_id=parent_id, ocr_texte=ocr, source="manuel")


# --------------------------------------------------------------------------- #
# Corpus de démonstration.
# --------------------------------------------------------------------------- #
def semer(cli):
    api = _Api(cli)

    # Tags de travail (avec couleurs).
    for label, coul, desc in [
        ("dialogue", "#3b82f6", "Réplique parlée"),
        ("récitatif", "#10b981", "Voix off / cartouche narratif"),
        ("onomatopée", "#f59e0b", "Bruitage lettré"),
        ("action", "#ef4444", "Moment d'action"),
        ("décor", "#8b5cf6", "Décor remarquable"),
        ("indice", "#0ea5e9", "Indice pour l'intrigue"),
    ]:
        api.post("/api/tags", label=label, couleur=coul, description=desc)

    # Personnages (série de démo).
    lea = api.post("/api/personnages", nom="Léa", serie="Les Explorateurs",
                   notes="Cartographe, curieuse.")
    sacha = api.post("/api/personnages", nom="Sacha", serie="Les Explorateurs",
                     notes="Prudent, taquin.")
    cap = api.post("/api/personnages", nom="Le Capitaine", serie="Les Explorateurs")

    # Attributs facettés (→ vocabulaire).
    dim_reg = api.post("/api/attributs/dimensions", cible="personnage", nom="registre de langue")
    reg = {v: api.post(f"/api/attributs/dimensions/{dim_reg['id']}/valeurs", valeur=v)["id"]
           for v in ("familier", "courant", "soutenu")}
    dim_lieu = api.post("/api/attributs/dimensions", cible="case", nom="lieu")
    lieu = {v: api.post(f"/api/attributs/dimensions/{dim_lieu['id']}/valeurs", valeur=v)["id"]
            for v in ("falaise", "phare", "cabine", "rivage")}
    api.put(f"/api/personnages/{lea['id']}/attributs", valeur_id=reg["courant"])
    api.put(f"/api/personnages/{sacha['id']}/attributs", valeur_id=reg["familier"])
    api.put(f"/api/personnages/{cap['id']}/attributs", valeur_id=reg["soutenu"])

    def poser(planche, rects, lignes):
        """Pose cases + bulles/cartouches + annotations + locuteurs + attributs de case.

        Chaque ligne = (texte, tag, personnage|None, type_région, note|None, lieu). `lieu`
        vaut une valeur de la dimension « lieu » (→ attribut de case), ou "indice" (ajoute
        le tag indice, sans attribut), ou None."""
        for i, rc in enumerate(rects):
            ca = api.case(planche["id"], rc, i + 1)
            texte, tag, perso, typ, note, lieu_val = lignes[i]
            reg_txt = api.texte(planche["id"], ca["id"], _bulle(rc), texte, typ)
            api.put(f"/api/regions/{reg_txt['id']}/annotation",
                    note=(note or None), tags=[tag] + (["indice"] if lieu_val == "indice" else []))
            if perso:
                api.put(f"/api/regions/{reg_txt['id']}/locuteur", personnage_id=perso["id"])
            if lieu_val in lieu:
                api.put(f"/api/regions/{ca['id']}/attributs", valeur_id=lieu[lieu_val])

    # ---- Album 1 : L'Île aux Énigmes (4 planches) -----------------------
    a1 = api.post("/api/albums", titre="L'Île aux Énigmes", serie="Les Explorateurs",
                  auteur="A. Démo", editeur="Éditions Démo", annee=2019,
                  date_edition="2019", date_originale="2018", langue="fr",
                  type_oeuvre="BD", lieu_edition="Bruxelles",
                  isbn="978-2-0000-0001-9", format_physique="30 cm, cartonné",
                  description="Aventure de démonstration : Léa et Sacha sur la piste "
                              "d'une vieille carte au trésor.")
    for nom, role in [("A. Démo", "scénariste"), ("B. Croquis", "dessinateur"),
                      ("C. Teintes", "coloriste")]:                    # N0 : contributions
        api.post(f"/api/albums/{a1['id']}/contributions", nom=nom, role=role)

    p1 = api.importer(a1["id"], (247, 243, 233), 1)
    poser(p1, _grille(2, 3), [
        ("Regarde, Sacha ! Une carte au trésor !", "dialogue", lea, "bulle",
         "Ouverture in medias res : la carte lance l'intrigue.", "falaise"),
        ("Tu crois qu'elle est authentique, Léa ?", "dialogue", sacha, "bulle", None, None),
        ("Plus tard, sur la falaise…", "récitatif", None, "cartouche", None, "falaise"),
        ("VLAM !", "onomatopée", None, "bulle", "Onomatopée d'impact, lettrage gras.", None),
        ("Attention à la marche, ça glisse !", "dialogue", sacha, "bulle", None, "falaise"),
        ("Le trésor ! Enfin !", "dialogue", lea, "bulle", None, "indice"),
    ])
    api.patch(f"/api/planches/{p1['id']}/statut", statut="annotee")
    api.patch(f"/api/planches/{p1['id']}/validation", validee=True)

    p2 = api.importer(a1["id"], (233, 240, 247), 2)
    poser(p2, _grille(2, 2), [
        ("Le vieux phare cache quelque chose…", "dialogue", lea, "bulle", None, "phare"),
        ("CRAAC", "onomatopée", None, "bulle", None, None),
        ("Une trappe ! Aide-moi à l'ouvrir.", "dialogue", sacha, "bulle", None, "phare"),
        ("Bienvenue, jeunes gens.", "dialogue", cap, "bulle", None, "cabine"),
    ])
    api.patch(f"/api/planches/{p2['id']}/statut", statut="corrigee")

    p3 = api.importer(a1["id"], (240, 236, 224), 3)
    poser(p3, _grille(1, 2), [
        ("Nous voilà dans la cabine du gardien.", "dialogue", lea, "bulle", None, "cabine"),
        ("Ces cartes marines sont anciennes.", "dialogue", cap, "bulle", None, "cabine"),
    ])
    api.patch(f"/api/planches/{p3['id']}/statut", statut="segmentee")

    p4 = api.importer(a1["id"], (210, 224, 236), 4)      # couverture (paratexte)
    api.patch(f"/api/planches/{p4['id']}/role", role="paratexte")

    # ---- Album 2 : Le Secret du Vieux Phare (2 planches) ----------------
    a2 = api.post("/api/albums", titre="Le Secret du Vieux Phare", serie="Les Explorateurs",
                  auteur="A. Démo", editeur="Éditions Démo", annee=2021,
                  date_edition="2021", langue="fr", type_oeuvre="BD",
                  lieu_edition="Bruxelles", isbn="978-2-0000-0002-6",
                  description="Deuxième tome de démonstration.")
    for nom, role in [("A. Démo", "scénariste"), ("B. Croquis", "dessinateur"),
                      ("D. Trad", "traducteur")]:
        api.post(f"/api/albums/{a2['id']}/contributions", nom=nom, role=role)

    q1 = api.importer(a2["id"], (236, 233, 224), 1)
    poser(q1, _grille(1, 3), [
        ("La tempête approche, rentrons !", "dialogue", sacha, "bulle", None, "rivage"),
        ("BOUM", "onomatopée", None, "bulle", None, None),
        ("Regarde cette inscription gravée…", "dialogue", lea, "bulle", None, "indice"),
    ])
    api.patch(f"/api/planches/{q1['id']}/statut", statut="annotee")

    q2 = api.importer(a2["id"], (224, 236, 233), 2)
    poser(q2, _grille(2, 1), [
        ("Elle indique une position en mer.", "dialogue", cap, "bulle", None, "rivage"),
        ("Cap au nord, moussaillons !", "action", cap, "bulle", None, None),
    ])
    api.patch(f"/api/planches/{q2['id']}/statut", statut="corrigee")

    albums = cli.get("/api/albums").json()
    planches = sum(len(cli.get(f"/api/albums/{a['id']}/planches").json()) for a in albums)
    print(f"OK — {len(albums)} albums, {planches} planches semés.")


def main() -> int:
    with TestClient(app) as cli:
        semer(cli)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
