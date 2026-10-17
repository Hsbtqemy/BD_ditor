"""COL-3, tranche 3a — défauts trouvés par la relecture croisée, prouvés et NON corrigés.

Chaque test échoue sur `16bf291` ; il décrit ce qui devrait tenir.

1. « À faire » (Administration) lit TOUTES les demandes en attente de `GET /api/demandes`
   (`fdCharger` : `demandes.filter((d) => d.en_attente)`) et rend chacune, hors projet, comme
   une demande de SUPPRESSION DÉFINITIVE : `afLigneDemande` ne distingue que
   `GENRE_PROJET`, et `BDSuppression.texteDemande` écrit « … demande la suppression
   définitive de « titre » ». Or la tranche 3a dépose désormais deux autres genres depuis
   l'écran d'AUJOURD'HUI — `rejoindre` par « + Ranger ici » (202), `entree_documents` par la
   prise. L'administrateur lit « X demande la suppression définitive de « Le Lotus bleu » »,
   clique « Détruire », confirme « Ses images et tout le travail fait dessus sont effacés…
   Irréversible » — et le serveur ACCEPTE l'entrée (une copie naît) ou le rejoindre (le
   travail est partagé avec une autre collection), puis l'écran annonce « détruit ».
   « Garder » refuse, à son insu, une entrée ou un partage.

2. Une demande de REJOINDRE survit à la destruction de sa copie : `_detruire_album` ne clôt
   que les suppressions qui la visaient. Elle reste en attente pour toujours, invisible des
   propriétaires (`…/collections/{id}/demandes` la perd par sa jointure, la réponse leur
   répond 404), et ne se lit plus que dans « À faire » — sous le défaut 1.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import ADMIN
from test_prendre import (ECRIVAIN, PROPRIO, _copie_dans, _entree, prise)  # noqa: F401

SUPPRESSION_JS = Path(__file__).resolve().parent.parent / "static" / "lib" / "suppression.js"


def _textes_a_faire(demandes, tmp_path):
    """Ce que « À faire » écrit de chaque demande en attente — par le module même de l'écran."""
    entree = tmp_path / "demandes.json"
    entree.write_text(json.dumps(demandes), encoding="utf-8")
    script = (f"const S = require({json.dumps(str(SUPPRESSION_JS))});"
              f"const d = JSON.parse(require('fs').readFileSync({json.dumps(str(entree))}, 'utf8'));"
              "process.stdout.write(JSON.stringify(d.map((x) => [x.genre, S.texteDemande(x)])));")
    sortie = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                            encoding="utf-8", check=True)
    return json.loads(sortie.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js non installé")
def test_a_faire_ne_presente_pas_une_entree_ou_un_rejoindre_comme_une_suppression(
        client, prise, tmp_path):
    _entree(client, prise, ("d1",))                              # le responsable demande
    cx = _copie_dans(client, prise, "d2", prise["x"])
    r = client.put(f"/api/albums/{cx}/collections/{prise['y']}", headers=ECRIVAIN)
    assert r.status_code == 202, r.text                          # « + Ranger ici » demande
    en_attente = [d for d in client.get("/api/demandes", headers=ADMIN).json()
                  if d["en_attente"]]                            # ce que lit « À faire »
    assert {d["genre"] for d in en_attente} == {"entree_documents", "rejoindre"}
    textes = _textes_a_faire(en_attente, tmp_path)
    menteurs = [(g, t) for g, t in textes if "suppression" in t]
    assert menteurs == [], (
        "« À faire » présente ces demandes comme des suppressions définitives, avec un "
        f"bouton « Détruire » qui les ACCEPTE : {menteurs}")


def test_une_demande_de_rejoindre_se_clot_avec_sa_copie(client, prise):
    cx = _copie_dans(client, prise, "d1", prise["x"])
    r = client.put(f"/api/albums/{cx}/collections/{prise['y']}", headers=ECRIVAIN)
    assert r.status_code == 202, r.text
    demande = r.json()["demande_id"]
    assert client.delete(f"/api/albums/{cx}", headers=ADMIN).status_code == 204
    vue = {d["id"]: d for d in client.get("/api/demandes", headers=ADMIN).json()}[demande]
    assert client.get(f"/api/collections/{prise['x']}/demandes", headers=PROPRIO).json() == []
    assert vue["en_attente"] is False, (
        "la copie est détruite, et la demande de la rejoindre attend toujours — invisible de "
        "son propriétaire, et lue dans « À faire » comme une suppression")
