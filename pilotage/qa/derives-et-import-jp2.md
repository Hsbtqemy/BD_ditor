---
passe: Dérivés régénérés et import JPEG 2000
chantier: IMG-1
duree: 15 min
derniere: 2026-09-23
---

# QA — un JP2 se choisit dans le dialogue, et un dérivé qui change de taille garde les cases en place

Deux choses que les tests ne peuvent pas lire. Le filtre du dialogue d'import est verrouillé
par un test qui lit l'attribut `accept` — mais c'est Windows qui construit le dialogue, et
personne n'a regardé s'il montre un `.jp2`. L'outil `tools/regenerer_derives.py` est éprouvé
en base (dimensions MASTER et régions intactes) — mais que les cases restent posées sur le
dessin quand le dérivé change de taille dépend du navigateur, qui recalcule l'échelle depuis
l'image chargée, et cela ne se voit qu'à l'écran.

**Pas sur la pile de recette.** La seconde zone fait refaire un dérivé par des commandes
posées sur les données du serveur, ce qui ne se fait pas sur une pile partagée ; et la
recette servait, à l'écriture de la passe, un commit antérieur au nouveau filtre. La passe se
joue donc sur un serveur LOCAL lancé depuis le dépôt, avec des données ISOLÉES dans
`C:\temp\qa-img1` — rien n'y touche la base du dépôt ni la recette. Sous Windows, dans
Chrome. Toutes les commandes se tapent dans PowerShell, depuis la racine du dépôt
(`C:\Dev\BD_ditor`), au commit `654562f` ou plus récent. Les trois commandes ci-dessous ont
été jouées telles quelles le 2026-09-16, sur des données jetables.

**Préalable, dans cet ordre.**

1. Si `C:\temp\qa-img1` existe d'une passe précédente, le supprimer : la seconde zone
   suppose que l'album créé plus bas est le PREMIER de ces données (`album_1`).
2. Fabriquer trois fichiers — un rectangle noir sur fond blanc, en JP2 et en TIFF, et un
   texte qui n'est pas une image :

       New-Item -ItemType Directory -Force C:\temp\qa-img1\fichiers | Out-Null
       .venv\Scripts\python -c "from PIL import Image, ImageDraw; im = Image.new('RGB', (2000, 2800), 'white'); ImageDraw.Draw(im).rectangle((400, 600, 1599, 1399), fill='black'); im.save(r'C:\temp\qa-img1\fichiers\rectangle.jp2'); im.save(r'C:\temp\qa-img1\fichiers\rectangle.tif')"
       Set-Content -Path C:\temp\qa-img1\fichiers\notes.txt -Value "pas une image"

3. Lancer le serveur sur ces données, dans une fenêtre PowerShell qu'on laisse ouverte :

       $env:BD_DATA_DIR = "C:\temp\qa-img1\donnees"
       .venv\Scripts\python -m uvicorn main:app --port 8010

4. Ouvrir `http://127.0.0.1:8010/` (l'Atelier), créer un album par le `＋` de la barre
   latérale, et le sélectionner.

### Le dialogue d'import propose les JP2, et seulement des images

- [x] Atelier, menu « ⇅ Import / Export » en haut, puis « ⤓ Importer des images… » ; dans le dialogue Windows, aller dans `C:\temp\qa-img1\fichiers` SANS toucher à la liste des types en bas à droite : `rectangle.jp2` et `rectangle.tif` sont listés, `notes.txt` ne l'est pas
- [x] Dans ce même dialogue, choisir `rectangle.jp2` : un message « Planche importée » s'affiche, et la planche montre un rectangle NOIR sur fond BLANC — ni une page blanche, ni une page noire
- [x] Rouvrir « ⤓ Importer des images… », changer la liste des types en bas à droite pour l'entrée qui montre tous les fichiers, choisir `notes.txt` : un message d'erreur commence par « Import : Extension « .txt » non gérée : image attendue », et aucune planche ne s'ajoute. Si la liste n'offre aucune entrée qui montre tous les fichiers, la case est sans objet (le refus est éprouvé par `tests/test_formats_image.py`) : le noter à côté

### Les cases restent sur le dessin quand le dérivé change de taille

**Préalable de zone.** Sur la planche importée ci-dessus, passer en mode Édition (touche
`E`) et dessiner au cliquer-glisser, sur le fond, une région qui colle aux quatre bords du
rectangle noir. Dessinée hors de toute case, elle naît de type « case » et reste
sélectionnée : NOTER les quatre valeurs du bloc « Coordonnées (px master) » — X, Y, L, H —,
la dernière case les compare. Garder l'Atelier ouvert sur cette planche, et ouvrir dans un
second onglet `http://127.0.0.1:8010/derivatives/album_1/planche_0001.jpg`, le dérivé
lui-même. Ouvrir enfin une SECONDE fenêtre PowerShell à la racine du dépôt, et y poser les
données de la passe : `$env:BD_DATA_DIR = "C:\temp\qa-img1\donnees"`.

**La commande « doubler »**, qui refait le dérivé au double de sa taille, comme le ferait un
`WEB_SCALE` changé :

    .venv\Scripts\python -c "import sqlite3; from config import DATA_DIR; from pipeline.ingest import make_web_derivative; c = sqlite3.connect(DATA_DIR / 'bd_annotator.sqlite'); m, w = c.execute('SELECT chemin_tiff, chemin_web FROM planches ORDER BY id DESC LIMIT 1').fetchone(); print(make_web_derivative(DATA_DIR / m, DATA_DIR / w, scale=0.5))"

Les rechargements de cette zone se font en `Ctrl+F5`, EXPRÈS : qu'un simple rechargement
suffise est une autre question — le cache des dérivés, mesurée à part. Ici on ne regarde que
la géométrie.

- [x] Second onglet (le dérivé) : le titre de l'onglet contient `500×700` — le quart du master, qui fait 2000 × 2800
- [x] Seconde fenêtre PowerShell : la commande « doubler » imprime `(1000, 1400)` ; second onglet, `Ctrl+F5` : le titre contient désormais `1000×1400`
- [x] Onglet de l'Atelier, `Ctrl+F5`, revenir sur la planche : le cadre de la case colle TOUJOURS aux quatre bords du rectangle noir, à l'œil, comme avant le changement de taille
- [x] Seconde fenêtre PowerShell : `.venv\Scripts\python tools\regenerer_derives.py --planche 1` imprime « ✓ 1 dérivé(s) régénéré(s) sur 1 planche(s). » ; second onglet, `Ctrl+F5` : le titre contient de nouveau `500×700`
- [x] Onglet de l'Atelier, `Ctrl+F5`, revenir sur la planche en mode Édition et sélectionner la case : son cadre colle encore aux bords du rectangle, et le bloc « Coordonnées (px master) » montre les MÊMES X, Y, L, H que ceux notés au préalable — ils sont en pixels master, et rien ne devait les toucher

Fin de passe : arrêter le serveur (`Ctrl+C` dans sa fenêtre) ; `C:\temp\qa-img1` peut être
supprimé.
