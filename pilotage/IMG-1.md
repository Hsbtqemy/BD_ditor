---
chantier: IMG-1
statut: à venir
---

# IMG-1 — accepter un format n'est pas savoir le convertir

**Point de départ** — 2026-09-14, en répondant à deux questions : « comment sont stockés les
dérivés ? » et « quels formats sont ingérés ? ». Tout ce qui suit a été MESURÉ, sur des
fichiers fabriqués passés par `read_metadata` puis `make_web_derivative`, dans le venv
(Pillow 12.0.0) et, pour le JPEG 2000, dans l'image de recette `bd-recette-app` (Pillow
12.0.0, OpenJPEG 2.5.4). Sauf le filtre d'extension, LU dans le code et non joué, et dit
comme tel. Aucune ligne de code touchée.

## Reste

### Le gris 16 bits devient blanc
- [ ] Un master en niveaux de gris 16 bits (`I;16` ou `I;16B`), TIFF comme JPEG 2000, importé depuis l'Atelier (⤓ Importer des images…) donne un dérivé dont les tons SUIVENT ceux du master : un dégradé 0 → 65535 sort en dégradé 0 → 255. Aujourd'hui `make_web_derivative` fait `convert("RGB")`, qui ÉCRÊTE — mesuré le 2026-09-14 : 0, 100, 255, 256, 1000, 16384, 32768, 65535 sortent en 0, 100, 255, 255, 255, 255, 255, 255. Un scan réel devient une page presque blanche, sans erreur à l'import
- [ ] `pipeline/ocr._open_image` est corrigée DANS LE MÊME commit : elle ouvre le master et lui applique le même `convert("RGB")`, donc l'OCR d'un master gris 16 bits lit une page blanche même quand le dérivé est juste. Attendu : les deux sites appellent UNE fonction de conversion, et aucun `convert("RGB")` nu ne reste sur un master
- [ ] Un test importe un vrai dégradé 16 bits par `POST /api/albums/{id}/import` et exige un dérivé NON saturé ; il est joué ROUGE sur le code d'avant correctif — sans quoi il pourrait passer sur n'importe quel dérivé
- [ ] Les modes `I` (32 bits entiers) et `F` (flottant) sont mesurés comme `I;16` l'a été, et chacun reçoit une réponse : converti juste, ou refusé à l'import avec un message qui nomme le mode. Non mesurés le 2026-09-14
- [ ] Le commentaire de `make_web_derivative` (« on convertit CMYK, 16 bits, palette ») ne promet que ce que la conversion corrigée fait vraiment
- [ ] Sur la base de production, `SELECT mode, COUNT(*) FROM planches GROUP BY mode` dit combien de planches ont un master `I;16`, `I;16B`, `I` ou `F` (la colonne est persistée depuis A6). Zéro : rien à rattraper. Sinon, la zone suivante n'est plus facultative

### Rattraper les dérivés existants
- [ ] Un outil régénère le dérivé d'une planche depuis son master (`--album`, `--planche`, `--dry-run`, sur le patron de `tools/reindex_materiel.py`). Aujourd'hui `make_web_derivative` n'a qu'un appelant, `ingest_image` : un dérivé faux le reste, et changer `WEB_SCALE` ou `WEB_JPEG_QUALITY` ne touche aucune planche déjà importée
- [ ] Sur une planche segmentée puis régénérée, les cases restent à leur place dans l'Atelier : la régénération ne touche ni `largeur_px` ni `hauteur_px` (dimensions MASTER), et le navigateur recalcule l'échelle depuis l'image chargée

### JPEG 2000
- [ ] Un JP2 RÉEL du corpus visé est inspecté, et la fiche dit s'il porte une boîte `resc`, `resd`, les deux, ou aucune. La case suivante ne se tranche pas sur un fichier fabriqué
- [ ] Un JP2 dont la résolution n'est écrite que dans `resd` reçoit un `dpi` à l'import — ou la fiche écrit pourquoi on s'y refuse. Aujourd'hui Pillow ne lit que `resc` : mesuré sur quatre fichiers forgés, `resc` → (300, 300), `resd` seule → `None`, `resd` puis `resc` → (300, 300). Sans dpi, pas de centimètres et la planche ne compte pas « avec résolution ». L'arbitrage est réel : `resc` dit ce que le scanner a capté, `resd` ce qu'on recommande d'afficher, et A6 décrit le MATÉRIEL
- [ ] Sous Windows, dans Chrome, le dialogue ouvert par ⤓ Importer des images… (Atelier) montre un fichier `.jp2` sans qu'on change le filtre. L'`accept` de `#file-input` ne cite aujourd'hui que `image/*,.tif,.tiff`, et le rangement de `.jp2` sous `image/*` n'a pas été vérifié
- [ ] Un test compare à `config.IMG_EXTS` les deux copies de la liste d'extensions que porte le front : l'`accept` de `#file-input` dans `templates/index.html`, et la regex `SD_IMG` de l'explorateur ShareDocs dans `static/viewer.js`. `SD_IMG` coïncide avec la liste aujourd'hui, et rien ne l'y oblige
- [ ] Le temps d'import d'un JP2 SANS PERTE est mesuré sur un VRAI scan dans l'image, et une décision est écrite s'il dépasse ce qu'un annotateur attend devant le toast « Import en cours… ». Le cas fabriqué — A4 à 300 dpi rempli de bruit, le pire cas pour la compression — prend 19,2 s pour le seul dérivé dans `bd-recette-app`, contre 2,6 s en avec perte, et la requête d'import attend pendant ce temps

### TIFF multipage
- [ ] Un TIFF de deux pages importé depuis l'Atelier est soit REFUSÉ avec un message qui dit « plusieurs pages », soit éclaté en deux planches — l'arbitrage est rendu avant le code. Aujourd'hui seule la première page est lue et la seconde disparaît sans avertissement (mesuré : `n_frames` = 2, taille et pixel de la page 1)

### Le filtre d'extension
- [ ] `POST /api/albums/{id}/import` d'un TIFF valide nommé `scan.dat` répond 400 et ne laisse aucun fichier dans `corpus/`, comme l'import ShareDocs le fait déjà. Aujourd'hui `import_planche` ne consulte pas `IMG_EXTS`, et `store_upload` range le master sous le suffixe reçu : lu dans le code le 2026-09-14, NON joué — la première étape est de le jouer. Ce n'est pas une faille, le décodage restant borné par `PILLOW_FORMATS` (SEC-3)

### Commentaires
- [ ] Le commentaire de `DERIVATIVES_DIR` dans `config.py` ne dit plus « PNG/JPEG » : le dérivé est toujours un JPEG

## Contexte

**Le constat qui compte est le premier.** Les autres sont des angles morts ; celui-là est
un défaut silencieux de bout en bout. L'import répond 201 avec les bonnes dimensions, la
planche apparaît dans la Bibliothèque, et c'est à l'écran seulement qu'on voit du blanc.
Les passes de reconnaissance le propagent sans rien signaler : la détection de bulles
travaille toujours sur le dérivé, Kumiko aussi par défaut (`use_master=False`), et l'OCR,
qui préfère le master, lui applique la même conversion. Sur une planche touchée,
régénérer le dérivé ne suffira donc pas : les régions produites sur du blanc sont à
refaire, et la resegmentation garde le travail humain.

**Ce qui a été mesuré et tient**, pour qu'on ne le recherche pas :

| Master | Dérivé | |
|---|---|---|
| RVB 16 bits par canal (TIFF écrit à la main) | 32768 → 128, 65535 → 254 | réduit correctement par Pillow à la lecture |
| 1 bit | noir et blanc | |
| CMYK | papier → blanc, K = 255 → noir | conversion NAÏVE, sans profil ICC — non mesuré sur un vrai scan CMYK |
| PNG avec transparence | alpha abandonné | sans enjeu pour un scan |
| JP2 et flux brut `.j2k`, dans l'image | décodés | le décodeur OpenJPEG est bien dans le livrable |

Par la route, en local : un `.jp2` téléversé répond 201, le master reste en `.jp2` dans
`corpus/`, le dérivé est servi en `image/jpeg`.

**Le guide d'usage est concerné par deux phrases**, datées du 2026-09-14 et à relire le jour
où ce chantier avance. Sous *Étape 1 — Constituer le corpus*, il annonce qu'« un fichier
hors liste est refusé sans rien enregistrer » : c'est vrai du CONTENU, pas encore du NOM
(zone *Le filtre d'extension*). Et il annonce que « la résolution et le mode colorimétrique
sont lus dans le fichier » : pas la résolution d'un JP2 qui ne porte que `resd`.

**Voisinage.** `SEC-3` (`livré`) tient la liste des sept formats et la borne du décodeur.
Aucune case ici n'ajoute de format : éclater un TIFF multipage décode d'autres pages avec
le même décodeur TIFF. Un format AJOUTÉ, en revanche, rouvrirait SEC-3 par sa troisième
condition. `A6` (piste de la roadmap, fait) a introduit `dpi_x`, `dpi_y` et `mode` : c'est
lui qui rend la mesure de production possible en une requête. `CONC-2` a mesuré la mémoire
d'un vrai master TIFF 400 dpi ; celle d'un JP2 sans perte n'a pas été mesurée.
