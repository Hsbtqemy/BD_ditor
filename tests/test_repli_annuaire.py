"""Le repli de l'annuaire vers le fichier se joue tel que la documentation l'écrit.  AUTH-7.

**Le défaut qu'il ferme, mesuré le 2026-09-16.** `docs/exploitation.md` basculait
`authentication_backend` par NUMÉROS de ligne — `85,93` pour décommenter `file:`, `95,100`
pour commenter `ldap:`. Le réglage `identity_validation.elevated_session`, ajouté plus haut
dans `configuration.yml`, a décalé les deux blocs de dix-huit lignes. Sur `main`, la
commande tombait juste ; sur `dev`, elle aurait édité d'autres lignes, et sur la production,
après la fusion, le jour même où l'annuaire serait tombé. Rien ne pouvait le signaler : une
procédure de secours ne s'exécute que le jour où l'on en a besoin.

**Ce test rejoue les commandes de la PAGE, pas une copie.** Il extrait les `sed` du bloc de
la section, les exécute sur une copie du fichier, puis lit le résultat. Une commande
recopiée ici vieillirait à côté de la vraie, et c'est exactement la panne qu'on répare.

**Ce qu'il ne prouve pas.** Qu'Authelia DÉMARRE sur le résultat : cela demande son binaire
et ses secrets. `authelia validate-config` a accepté les deux états le 2026-09-16, dans le
conteneur de la pile de recette (4.39.22). Ni que le fichier des comptes est à jour — c'est
l'affaire de `verifier_comptes.py`, et `docs/exploitation.md` dit ce qu'il ne voit pas.
"""
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parent.parent
DOC = RACINE / "docs" / "exploitation.md"
CONF = RACINE / "deploy" / "authelia" / "configuration.yml"
TITRE = "### Le repli de l'annuaire vers le fichier"

REPERES = ("# >>> repli-fichier", "# <<< repli-fichier",
           "# >>> annuaire-ldap", "# <<< annuaire-ldap")


def _section():
    texte = DOC.read_text(encoding="utf-8")
    assert TITRE in texte, f"la section « {TITRE} » a disparu de {DOC.name}"
    debut = texte.index(TITRE)
    fin = texte.find("\n### ", debut + len(TITRE))
    return texte[debut:] if fin == -1 else texte[debut:fin]


def _commandes_sed():
    """Les `sed` du premier bloc bash de la section, découpés comme un shell les lirait.

    `shlex` et non un `split("#")` : les motifs contiennent eux-mêmes `# >>>`, et seul un
    découpage qui respecte les guillemets distingue le motif du commentaire de fin de ligne.
    """
    bloc = re.search(r"```bash\n(.*?)```", _section(), re.S)
    assert bloc, "la section n'a plus de bloc de commandes"
    return [shlex.split(ligne, comments=True)
            for ligne in bloc.group(1).splitlines() if ligne.strip().startswith("sed ")]


def _sed():
    trouve = shutil.which("sed")
    git = Path(r"C:\Program Files\Git\usr\bin\sed.exe")
    return trouve or (str(git) if git.exists() else None)


def _backend(texte):
    """Le seul `authentication_backend`, lu en YAML.

    Le fichier ENTIER ne se lit pas en YAML : Authelia le passe d'abord dans son moteur de
    gabarits, et `{{- if env "SMTP_ADRESSE" }}` n'est pas du YAML. La section, elle, l'est.
    """
    lignes = texte.splitlines()
    i = lignes.index("authentication_backend:")
    fin = next((j for j in range(i + 1, len(lignes)) if re.match(r"[A-Za-z_]", lignes[j])),
               len(lignes))
    return yaml.safe_load("\n".join(lignes[i:fin]))["authentication_backend"]


def test_la_procedure_ne_vise_aucune_ligne_par_son_numero():
    commandes = _commandes_sed()
    ecritures = [c for c in commandes if "-i" in c]
    # Un plancher : sans lui, une section vidée de ses commandes rendrait ce test vert.
    assert len(ecritures) == 2, f"deux `sed -i` attendus (file:, ldap:), trouvés : {commandes}"
    for c in commandes:
        script = c[2]
        assert not re.match(r"\d", script), (
            f"`{' '.join(c)}` vise une ligne par son NUMÉRO : un bloc ajouté plus haut la "
            "décale sans rien dire. Viser les repères de configuration.yml")


def test_les_reperes_encadrent_exactement_les_deux_blocs():
    lignes = CONF.read_text(encoding="utf-8").splitlines()
    positions = []
    for repere in REPERES:
        occurrences = [i for i, l in enumerate(lignes) if l == repere]
        assert len(occurrences) == 1, f"« {repere} » doit figurer UNE fois, en colonne 0"
        positions.append(occurrences[0])
    assert positions == sorted(positions), "repères dans le désordre"

    repli = [l for l in lignes[positions[0] + 1:positions[1]] if l.strip()]
    annuaire = [l for l in lignes[positions[2] + 1:positions[3]] if l.strip()]
    assert repli and all(l.startswith("  #") for l in repli), (
        "le bloc de repli doit être entièrement commenté et indenté : c'est ce que le `sed` "
        "décommente")
    assert repli[0].strip() == "# file:"
    assert annuaire and all(l.startswith("  ") and not l.startswith("  #") for l in annuaire), (
        "le bloc de l'annuaire doit être actif et indenté : c'est ce que le `sed` commente")
    assert annuaire[0].strip() == "ldap:"


def test_la_procedure_bascule_le_backend_et_ne_touche_rien_d_autre(tmp_path):
    sed = _sed()
    if sed is None:
        pytest.skip("aucun `sed` sur ce poste : la procédure n'est rejouée que là où elle "
                    "le serait vraiment, dans l'image et sur le serveur")
    copie = tmp_path / "configuration.yml"
    avant = CONF.read_text(encoding="utf-8")
    copie.write_text(avant, encoding="utf-8", newline="\n")

    # `password_reset` vit dans la même section et ne bouge pas : on ne regarde que les deux
    # backends, dont un seul doit être actif à la fois.
    assert "ldap" in _backend(avant) and "file" not in _backend(avant), (
        "le fichier suivi doit servir l'annuaire")

    commandes = _commandes_sed()
    for c in commandes:
        if "-i" in c:
            subprocess.run([sed, *c[1:]], cwd=tmp_path, check=True)
    apres = copie.read_text(encoding="utf-8")

    backend = _backend(apres)
    assert "file" in backend and "ldap" not in backend, (
        f"après la procédure, la section porte {sorted(backend)}")
    assert backend["file"]["path"] == "/config/users_database.yml"

    # Hors des deux blocs, le fichier est identique à la ligne près : c'est ce qu'une
    # adresse par numéros ne garantissait pas.
    def hors_blocs(texte):
        garde, dedans = [], False
        for l in texte.splitlines():
            if l in (REPERES[0], REPERES[2]):
                dedans = True
            if not dedans:
                garde.append(l)
            if l in (REPERES[1], REPERES[3]):
                dedans = False
        return garde
    assert hors_blocs(apres) == hors_blocs(avant)

    lecture = next(c for c in commandes if "-n" in c)
    sortie = subprocess.run([sed, *lecture[1:]], cwd=tmp_path, check=True,
                            capture_output=True, text=True, encoding="utf-8")
    montrees = sortie.stdout.splitlines()
    assert montrees[0] == REPERES[0] and montrees[-1] == REPERES[3], (
        "la commande « LIRE avant d'aller plus loin » doit montrer les deux blocs, et eux seuls")
