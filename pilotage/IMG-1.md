---
chantier: IMG-1
statut: différé
---

# IMG-1 — accepter un format n'est pas savoir le convertir

**Arrêté sur** — la relecture du chantier, commit `7087fca`, 16 septembre, juste après le
cache des dérivés (`e9811c7` : `no-cache` et 304, mesuré dans Chromium avant et après). Avant
eux : le gris 16 bits (`fb53e67`), l'outil de régénération (`fd7cd38`, déclaré au cliquet par
`944f071`), le filtre d'extension (`cfbf85d`), le dialogue d'import (`654562f`). Poussé sur
`origin/dev` le 2026-09-16 (`dd7f6db`). DIFFÉRÉ exprès : ce qui reste attend le TIFF et le JP2 réels du scanner de l'équipe,
et les décisions de Hugo sur le stockage des masters et le coût d'import du JP2 ; la passe de
QA `derives-et-import-jp2` est à jouer.

## Reste

### Le gris 16 bits devient blanc
- [x] Un master en niveaux de gris 16 bits (`I;16` ou `I;16B`), TIFF comme JPEG 2000, importé depuis l'Atelier (⤓ Importer des images…) donne un dérivé dont les tons SUIVENT ceux du master : un dégradé 0 → 65535 sort en dégradé 0 → 255. Aujourd'hui `make_web_derivative` fait `convert("RGB")`, qui ÉCRÊTE — mesuré le 2026-09-14 : 0, 100, 255, 256, 1000, 16384, 32768, 65535 sortent en 0, 100, 255, 255, 255, 255, 255, 255. Un scan réel devient une page presque blanche, sans erreur à l'import
- [x] `pipeline/ocr._open_image` est corrigée DANS LE MÊME commit : elle ouvre le master et lui applique le même `convert("RGB")`, donc l'OCR d'un master gris 16 bits lit une page blanche même quand le dérivé est juste. Attendu : les deux sites appellent UNE fonction de conversion, et aucun `convert("RGB")` nu ne reste sur un master
- [x] Un test importe un vrai dégradé 16 bits par `POST /api/albums/{id}/import` et exige un dérivé NON saturé ; il est joué ROUGE sur le code d'avant correctif — sans quoi il pourrait passer sur n'importe quel dérivé
- [x] Les modes `I` (32 bits entiers) et `F` (flottant) sont mesurés comme `I;16` l'a été, et chacun reçoit une réponse : converti juste, ou refusé à l'import avec un message qui nomme le mode. Non mesurés le 2026-09-14
- [x] Le commentaire de `make_web_derivative` (« on convertit CMYK, 16 bits, palette ») ne promet que ce que la conversion corrigée fait vraiment
- [x] Sur la base de production, `SELECT mode, COUNT(*) FROM planches GROUP BY mode` dit combien de planches ont un master `I;16`, `I;16B`, `I` ou `F` (la colonne est persistée depuis A6). Zéro : rien à rattraper. Sinon, la zone suivante n'est plus facultative. Si la colonne rend `None`, la commande de repli en lecture seule du Contexte lit le mode dans les masters eux-mêmes. SANS OBJET, décidé par Hugo le 2026-09-16 : les planches déjà importées sont des planches de travail, sans incidence sur la constitution de la base réelle — la mesure n'est pas lancée
- [x] Si la mesure de production trouve un master `I` ou `F` importé avant le refus : `GET /api/regions/{id}/crop` (Transcription, vignettes) et `POST /api/figures` répondent un message qui nomme le mode, et non un 500 nu. `_open_image` lève désormais `OCRError` sur ce master, et seule la route OCR la rattrape — LU dans le code le 2026-09-16, non joué. Aucun master de ce mode : case sans objet. SANS OBJET par la même décision : aucun master antérieur au refus ne compte, et tout import neuf en `I` ou `F` est refusé

### Rattraper les dérivés existants
- [x] Un outil régénère le dérivé d'une planche depuis son master (`--album`, `--planche`, `--dry-run`, sur le patron de `tools/reindex_materiel.py`). Aujourd'hui `make_web_derivative` n'a qu'un appelant, `ingest_image` : un dérivé faux le reste, et changer `WEB_SCALE` ou `WEB_JPEG_QUALITY` ne touche aucune planche déjà importée
- [ ] Sur une planche segmentée puis régénérée, les cases restent à leur place dans l'Atelier : la régénération ne touche ni `largeur_px` ni `hauteur_px` (dimensions MASTER), et le navigateur recalcule l'échelle depuis l'image chargée. La base est ÉPROUVÉE par `tests/test_regenerer_derives.py` (ligne `planches` et régions identiques) ; le recalcul d'échelle est LU dans `static/viewer.js` (`webScale = naturalWidth / largeur_px`), pas joué dans l'Atelier. À jouer par la passe `pilotage/qa/derives-et-import-jp2.md`, zone « Les cases restent sur le dessin quand le dérivé change de taille »
- [x] Après régénération, une planche déjà ouverte dans l'Atelier montre le NOUVEAU dérivé au simple rechargement de la page, sans vider le cache. `GET /derivatives/…` répond un `FileResponse` sans `Cache-Control` (lu dans `main.py` le 2026-09-16) : un navigateur peut garder l'ancienne image par fraîcheur heuristique. Hypothèse, non mesurée — le middleware `no-cache` ne couvre que `/static` et les pages HTML. MESURÉ le 2026-09-16 côté serveur (client HTTP) : aucun `Cache-Control`, un `ETag` et un `Last-Modified` présents, mais une requête conditionnelle reçoit TOUJOURS 200 et le corps entier — la route ne répond jamais 304. Le comportement du navigateur reste à mesurer. DÉCISION de Hugo (2026-09-16) : `Cache-Control: no-cache` ET une réponse 304 quand l'ETag concorde, dans la même route, le 304 décidé APRÈS le contrôle de portée ; pas de bouton d'actualisation, personne ne sachant quand un dérivé a été régénéré. LIMITE ASSUMÉE : une planche déjà affichée au moment de la régénération ne change qu'au rechargement de la page ou au changement de planche. MESURÉ dans Chromium (Playwright) le même jour, dérivé vieilli de 30 jours puis refait au double : SANS le correctif, un rechargement (F5) montrait toujours l'ancien dérivé SANS AUCUNE requête au serveur, une nouvelle navigation aussi, et seul un cache vide voyait le nouveau ; AVEC le correctif, F5 montre le nouveau dérivé, et la navigation suivante ne coûte qu'un 304 sans corps. Le rechargement est mesuré, le changement de planche ne l'est pas

### JPEG 2000
- [x] La chaîne de production des JP2 est connue et écrite ici : l'outil qui les produit, avec ou sans perte, et si le master reste un TIFF archivé ailleurs. Seule elle tranche `resc`/`resd` et le 12 bits ; questions posées à Hugo le 2026-09-16. Réponses du même jour : le LOGICIEL DU SCANNER de l'équipe (modèle non précisé) ; SANS PERTE comme cas nominal (« le moins de perte possible ») ; master NON DÉCIDÉ — tout TIFF, TIFF et JP2 mêlés, ou JP2 privilégié à terme, donc l'application porte les deux formats de master sans supposer lequel l'emporte ; profondeur INCONNUE
- [ ] Le format de stockage des masters est décidé par Hugo et écrit ici — TIFF brut, TIFF compressé sans perte, JP2 sans perte, ou un mélange —, avec le coût d'import qu'il accepte. La comparaison mesurée sur deux vrais scans est au Contexte ; l'application porte déjà les deux formats de master
- [ ] Un JP2 produit par CE scanner, réglé sans perte, accompagné du TIFF de la MÊME page, est relevé, et la fiche note : le modèle du scanner et son réglage ; les boîtes de résolution présentes (`resc`, `resd`, les deux, aucune) et le `dpi` que l'import en tire ; la précision en bits et gris ou couleur (le mode Pillow à l'import) ; le poids du JP2 face au TIFF ; le temps d'import de chacun dans l'image. Ce seul couple de fichiers tranche le modèle, la profondeur et la case `resd` ci-dessous
- [ ] Un JP2 gris en 12 bits RÉEL, importé, donne un dérivé qui suit ses tons. `image_8_bits` le traite comme du 16 bits parce que le décodeur de Pillow étend toute précision à 16 (`shift = 16 - prec` dans `Jpeg2KDecode.c`, LU au tag 12.0.0) ; non mesuré, Pillow n'écrivant pas de JP2 12 bits. Si c'était faux, le dérivé sortirait presque NOIR
- [ ] Un JP2 RÉEL du corpus visé est inspecté, et la fiche dit s'il porte une boîte `resc`, `resd`, les deux, ou aucune. La case suivante ne se tranche pas sur un fichier fabriqué. Le JP2 du scanner de la case précédente EST ce fichier
- [ ] Un JP2 dont la résolution n'est écrite que dans `resd` reçoit un `dpi` à l'import — ou la fiche écrit pourquoi on s'y refuse. Aujourd'hui Pillow ne lit que `resc` : mesuré sur quatre fichiers forgés, `resc` → (300, 300), `resd` seule → `None`, `resd` puis `resc` → (300, 300). Sans dpi, pas de centimètres et la planche ne compte pas « avec résolution ». L'arbitrage est réel : `resc` dit ce que le scanner a capté, `resd` ce qu'on recommande d'afficher, et A6 décrit le MATÉRIEL
- [ ] Sous Windows, dans Chrome, le dialogue ouvert par ⤓ Importer des images… (Atelier) montre un fichier `.jp2` sans qu'on change le filtre. L'`accept` de `#file-input` ne citait que `image/*,.tif,.tiff` ; depuis `654562f` il énumère les quatorze extensions de `IMG_EXTS`, `.jp2` compris, sans `image/*`. Que le dialogue le MONTRE reste à jouer à la main : passe `pilotage/qa/derives-et-import-jp2.md`, zone « Le dialogue d'import propose les JP2, et seulement des images »
- [x] Un test compare à `config.IMG_EXTS` les deux copies de la liste d'extensions que porte le front : l'`accept` de `#file-input` dans `templates/index.html`, et la regex `SD_IMG` de l'explorateur ShareDocs dans `static/viewer.js`. `SD_IMG` coïncide avec la liste aujourd'hui, et rien ne l'y oblige
- [ ] Le temps d'import d'un JP2 SANS PERTE est mesuré sur un VRAI scan dans l'image, et une décision est écrite s'il dépasse ce qu'un annotateur attend devant le toast « Import en cours… ». Le cas fabriqué — A4 à 300 dpi rempli de bruit, le pire cas pour la compression — prend 19,2 s pour le seul dérivé dans `bd-recette-app`, contre 2,6 s en avec perte, et la requête d'import attend pendant ce temps. MESURÉ sur deux VRAIS scans le 2026-09-16 (chiffres au Contexte) : la requête d'import passe de 0,4 s en TIFF à 7 à 11 s en JP2 sans perte. La décision est posée à Hugo, non prise. Hugo (2026-09-16) : elle ATTEND un TIFF et un JP2 réels sortis du scanner, qu'il va chercher dans les prochains jours ; ni le décodage réduit ni la tâche de fond ne se codent d'ici là

### TIFF multipage
- [ ] Un TIFF de deux pages importé depuis l'Atelier est REFUSÉ avec un message qui dit « plusieurs pages », et rien n'est enregistré. Arbitrage rendu par Hugo le 2026-09-16 : refuser, et NON prioritaire — le code attendra que le cas se présente. Aujourd'hui seule la première page est lue et la seconde disparaît sans avertissement (mesuré : `n_frames` = 2, taille et pixel de la page 1)

### Le filtre d'extension
- [x] `POST /api/albums/{id}/import` d'un TIFF valide nommé `scan.dat` répond 400 et ne laisse aucun fichier dans `corpus/`, comme l'import ShareDocs le fait déjà. Aujourd'hui `import_planche` ne consulte pas `IMG_EXTS`, et `store_upload` range le master sous le suffixe reçu : lu dans le code le 2026-09-14, NON joué — la première étape est de le jouer. Ce n'est pas une faille, le décodage restant borné par `PILLOW_FORMATS` (SEC-3)

### Commentaires
- [x] Le commentaire de `DERIVATIVES_DIR` dans `config.py` ne dit plus « PNG/JPEG » : le dérivé est toujours un JPEG

## Contexte

**Point de départ** — 2026-09-14, en répondant à deux questions : « comment sont stockés
les dérivés ? » et « quels formats sont ingérés ? ». Tout ce qui suit a été MESURÉ, sur des
fichiers fabriqués passés par `read_metadata` puis `make_web_derivative`, dans le venv
(Pillow 12.0.0) et, pour le JPEG 2000, dans l'image de recette `bd-recette-app` (Pillow
12.0.0, OpenJPEG 2.5.4). Sauf le filtre d'extension, LU dans le code et non joué, et dit
comme tel. Aucune ligne de code touchée ce jour-là.

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
*Relu le 2026-09-16* : la première phrase est vraie du NOM aussi depuis `cfbf85d`, et le §6
décrit maintenant les deux contrôles ; le refus pour profondeur (`I`, `F`) y est ajouté. La
seconde reste à reprendre avec l'arbitrage `resd`.

**Voisinage.** `SEC-3` (`livré`) tient la liste des sept formats et la borne du décodeur.
Aucune case ici n'ajoute de format : éclater un TIFF multipage décode d'autres pages avec
le même décodeur TIFF. Un format AJOUTÉ, en revanche, rouvrirait SEC-3 par sa troisième
condition. `A6` (piste de la roadmap, fait) a introduit `dpi_x`, `dpi_y` et `mode` : c'est
lui qui rend la mesure de production possible en une requête. `CONC-2` a mesuré la mémoire
d'un vrai master TIFF 400 dpi ; celle d'un JP2 sans perte n'a pas été mesurée.

**2026-09-16 — le gris 16 bits corrigé, et ce que la mesure a ajouté.** Tout a été mesuré
dans le venv (Pillow 12.0.0), sur des fichiers forgés, sauf mention contraire.

- *Le 12 bits était le piège.* Pillow range un TIFF 12 bits en `I;16` SANS étendre ses
  valeurs : 4095 y reste 4095. Diviser tout `I;16` par 256 aurait remplacé le blanc par du
  NOIR. La profondeur se lit donc dans `BitsPerSample`. Le JPEG 2000 n'est pas concerné, son
  décodeur étendant toute précision à 16 bits — lu dans la source, pas mesuré, d'où la case.
- *Un PNG 16 bits se relit en `I;16`*, y compris écrit en mode `I`. Un TIFF 16 bits
  compressé (LZW, Deflate, PackBits) aussi, par libtiff : le test couvre le LZW, parce qu'un
  vrai scan est presque toujours compressé.
- *`I` et `F` sont refusés, pas convertis* — tranché dans cette session, rouvrable. `I` ne
  porte pas sa profondeur : Pillow y range le 16 bits SIGNÉ (-32768…32767) comme le 32 bits,
  et relit un 32 bits non signé valant 4294967295 en -1. Un `F` vaut 0,5 sans dire sur quelle
  échelle. Toute réduction serait devinée, et une page fausse qui s'affiche coûte plus
  qu'un refus. `I;16N` suit la même règle : `convert("I")` le lit faux (32768 → 255), mais
  aucun lecteur de fichier ne le produit.
- *Kumiko sur master* (`use_master=True`) lit le fichier avec OpenCV, hors de Pillow :
  mesuré avec cv2 4.13, un TIFF 16 bits sort juste (réduit à la lecture) et un TIFF 12 bits
  est REFUSÉ (`imread` rend `None`). Pas de page blanche, donc pas de case.

**La mesure de production a été préparée, puis déclarée sans objet par Hugo** le même jour :
les planches importées jusqu'ici sont des planches de travail, sans incidence sur la base
réelle. Elle n'est donc PAS lancée, et il n'y a rien à lui demander. Les deux commandes
restent ici parce qu'elles vaudront le jour où la base réelle existera — une ligne chacune,
base ouverte en lecture seule, chaque master ouvert (en-tête seul) puis refermé avant le
suivant, formats bornés comme dans l'app :

    docker exec bd-app python -c "import sqlite3; c = sqlite3.connect('file:/data/bd_annotator.sqlite?mode=ro', uri=True); print(c.execute('SELECT mode, COUNT(*) FROM planches GROUP BY mode ORDER BY 2 DESC').fetchall())"

    docker exec bd-app python -c "import sqlite3,collections;from PIL import Image as I;I.MAX_IMAGE_PIXELS=2*10**8;F=('TIFF','JPEG','JPEG2000','PNG','BMP','GIF','WEBP');exec(\"def m(p):\n try:\n  i=I.open('/data/'+p,formats=F);r=i.mode;i.close();return r\n except Exception as e:\n  return type(e).__name__\");c=sqlite3.connect('file:/data/bd_annotator.sqlite?mode=ro',uri=True);print(collections.Counter(m(p) for (p,) in c.execute('SELECT chemin_tiff FROM planches WHERE mode IS NULL AND chemin_tiff IS NOT NULL')))"

Jouées sur la RECETTE par la session de coordination : la première rend `[(None, 129)]` —
aucune planche de la recette n'a de mode en base —, la seconde `Counter({'RGB': 129})` en
0,7 s. Un TIFF 12 bits apparaît en `I;16` dans les deux.

**Deux arbitrages posés à Hugo, rendus le même jour.** *TIFF multipage* : la recommandation
transmise était de REFUSER — éclater oblige soit à partager un master entre N planches, et
supprimer l'une effacerait le fichier des autres (`remove_planche_files`), soit à réencoder
chaque page en un nouveau master, ce qui contredit « le master n'est jamais modifié ».
Hugo : refuser, mais NON prioritaire ; le code attendra que le cas se présente. *`resd` des
JP2* : aucune recommandation sans un JP2 réel. Hugo en fait la PRIORITÉ de la reprise, pour
une raison qui n'était pas dans la fiche : le poids des TIFF dans le stockage. Aucun JP2 du
fournisseur n'étant disponible, la reprise commence par ce qui se mesure sans lui — un vrai
scan TIFF de la recette, lu en lecture seule et converti en JP2 sans perte dans l'image,
pour la case du temps d'import — et par des questions à la chaîne de production (outil,
avec ou sans perte, TIFF archivé ailleurs ou non), dont dépendent `resc`/`resd` et le
12 bits.

**Rattraper, le jour où des masters en `I;16` ou `I;16B` importés avant `fb53e67` compteront**
(ce n'est pas le cas des planches de travail d'aujourd'hui, décision ci-dessus) — d'abord à
blanc, puis sans `--dry-run`. Les guillemets sont obligatoires : sans eux, `;` coupe la commande et
l'outil tourne sur les planches en mode `I` (mesuré en bash et en PowerShell).

    docker exec bd-app python tools/regenerer_derives.py --toutes --mode "I;16" --mode "I;16B" --dry-run

L'outil liste à la fin les planches dont des régions de moteur ont pu être posées sur le
dérivé écrêté. Il ne sait pas les dater : une région posée APRÈS le correctif est comptée
aussi. Il ne les efface jamais.

**Le filtre d'extension, joué avant correctif le 2026-09-16** : un TIFF valide nommé
`scan.dat` répondait 201 et entrait dans le corpus en `planche_0001.dat` — ce que la lecture
du 14 annonçait. Corrigé dans la route, avant toute lecture du fichier.

**Un rouge posé et réparé dans la même session.** `fd7cd38` ajoutait un outil sans le
déclarer au cliquet des sorties d'identité, qui exige que tout fichier de `tools/` soit
balayé ou déclaré avec sa raison : l'outil n'avait été joué qu'avec ses propres tests, et
seule la suite entière l'a vu. Réparé par `944f071`. Un fichier neuf dans `tools/` se valide
par la suite entière, pas par son test.

**La suite par défaut sans navigateur, le 2026-09-16**, rend cinq rouges qui ne sont pas à
ce chantier : trois dans `tests/test_surfaces.py` (`test_e2e_undo_rafraichit.py` ne déclare
pas ses surfaces) et deux dans `tests/test_ecart_venv_image.py` — le venv local a dérivé de
ses verrous (`fastapi` 0.137.0 pour 0.133.0, `pytest` 9.1.0 pour 9.0.2…), et `numpy` /
`pillow` y sont déclarés en écart alors qu'ils sont redevenus conformes. Signalé à la
coordination, qui a réaligné le venv sur ses verrous le même jour — pas ce chantier.

**Le JP2 sans perte sur de VRAIS scans — mesuré le 2026-09-16** dans un conteneur jetable de
`bd-recette-app` (image de `f5fd1eb`), volume de données monté en LECTURE SEULE, 8 cœurs,
OpenJPEG 2.5.4, aucun Chromium en parallèle. Deux masters de la recette, TIFF RVB **non
compressés** à 400 dpi : le plus lourd des 129 et un médian. Conversion par Pillow sans
perte (ondelette réversible, réglages par défaut) — ce n'est PAS le logiciel du scanner.

| | le plus lourd (3748 × 4710) | médian (3110 × 4045) |
|---|---|---|
| poids TIFF → JP2 | 53,0 Mo → 23,1 Mo (44 %) | 37,7 Mo → 18,5 Mo (49 %) |
| pixels relus | identiques | identiques |
| dérivé, TIFF | 0,23 / 0,25 s, pic 112 Mo | 0,18 / 0,19 s, pic 86 Mo |
| dérivé, JP2 | 8,7 / 8,9 s, pic 350 Mo | 7,3 / 7,2 s, pic 256 Mo |
| requête d'import, TIFF | 0,40 / 0,43 s | 0,37 / 0,33 s |
| requête d'import, JP2 | 8,5 / 11,4 s | 7,4 / 9,6 s |

(Deux répétitions chacune, dans un Python neuf. Le second passage JP2 par la route est plus
lent sans cause établie.) `read_metadata` coûte 30 à 40 ms dans les deux formats : tout le
temps est dans le DÉCODAGE plein du JP2. Les 19,2 s du cas fabriqué étaient un pire cas
(bruit) ; un vrai scan coûte deux fois moins, et reste vingt fois plus lent qu'un TIFF brut.

Deux faits en marge. *Le JP2 écrit par Pillow ne porte AUCUNE résolution*, même quand on lui
passe `dpi` : son encodeur n'écrit ni `resc` ni `resd` — l'import en tire donc `dpi = None`,
et cela ne dit RIEN du scanner. *Les TIFF de la recette sont non compressés* : le JP2 pèse
44–49 % d'un TIFF BRUT, et un TIFF compressé sans perte est un point intermédiaire — mesuré
plus bas, dans la table du TIFF compressé.

**Décoder le JP2 à résolution réduite** (`reduce`, que Pillow expose) pour le dérivé au quart,
mesuré sur les mêmes fichiers, comparé pixel à pixel au dérivé actuel (décodage plein puis
LANCZOS), avant compression JPEG :

| | le plus lourd | médian |
|---|---|---|
| `reduce=1` (moitié) + LANCZOS | 3,0 s, pic 114 Mo ; écart moyen 3,5/255, 15 % des pixels à plus de 8 | 2,1 s, pic 90 Mo ; écart moyen 1,5/255, 1,8 % à plus de 8 |
| `reduce=2` (quart), sans LANCZOS | 0,9 s, pic 66 Mo ; écart moyen 10/255, maximum 138, 25 % à plus de 8 | **ÉCHEC** : `OSError: broken data stream` |

`reduce=2` est donc écarté : visiblement différent là où il marche, et il ÉCHOUE sur un vrai
scan. Hypothèse cohérente avec les trois observations, non vérifiée dans OpenJPEG : Pillow
calcule la taille réduite en `int((n + 2) / 4)` quand le décodeur rend l'arrondi supérieur ;
les deux ne divergent que si `n` vaut 1 modulo 4 — 4045, la seule hauteur qui a échoué.
`reduce=1` (`int((n + 1) / 2)`) coïncide toujours. Un JP2 à trop peu de niveaux de
résolution échoue aussi (mesuré : deux résolutions, `reduce=2` → même erreur), si bien
qu'un décodage réduit exigerait un REPLI sur le décodage plein. Les écarts de `reduce=1` se
logent probablement dans les trames d'impression, que l'ondelette filtre autrement que
LANCZOS — hypothèse, non regardée à l'écran.

**Le TIFF compressé sans perte, pour la décision de stockage — mesuré le 2026-09-16**, mêmes
conditions et mêmes deux masters que le JP2 ci-dessus, à la demande de Hugo. Compression par
Pillow/libtiff. Le prédicteur horizontal passe par `tiffinfo={317: 2}` alors que Pillow ne
range pas la balise dans son noyau libtiff : il est APPLIQUÉ, vérifié en relisant la balise
(2) et au poids. Toutes les variantes relisent des pixels identiques et gardent leur dpi.

| variante | plus lourd : poids | import | médian : poids | import |
|---|---|---|---|---|
| brut | 53,0 Mo (100 %) | 0,44 / 0,51 s | 37,7 Mo (100 %) | 0,53 / 0,36 s |
| LZW | 49,5 Mo (93 %) | 1,05 / 1,10 s | 37,3 Mo (99 %) | 0,85 / 0,88 s |
| LZW + prédicteur | 33,8 Mo (64 %) | 1,15 / 1,18 s | 27,1 Mo (72 %) | 1,02 / 0,85 s |
| Deflate | 41,5 Mo (78 %) | 0,74 / 0,67 s | 30,7 Mo (81 %) | 0,53 / 0,44 s |
| Deflate + prédicteur | 31,2 Mo (59 %) | 0,82 / 0,74 s | 23,9 Mo (63 %) | 0,57 / 0,54 s |
| JP2 sans perte | 23,1 Mo (44 %) | 8,5 / 11,4 s | 18,5 Mo (49 %) | 7,4 / 9,6 s |

(« import » = la requête `POST /api/albums/{id}/import` entière, deux répétitions. Pic
mémoire de la requête : 204–254 Mo en Deflate + prédicteur, 237–310 Mo en brut, 383–483 Mo
en JP2.) LZW est dominé par Deflate sur les deux fichiers, et sans prédicteur il ne gagne
presque rien sur le médian. **Ce que la table met en balance, sans trancher** : Deflate +
prédicteur ramène le master à ~60 % pour +0,2 à 0,3 s d'import ; le JP2 sans perte gagne
encore ~25 % de stockage, pour 7 à 11 s par planche. Le temps d'ÉCRITURE (1 à 4 s pour les
TIFF, 11 à 14 s pour le JP2) est payé une fois par qui produit le fichier, pas à l'import.
Deux scans RVB d'une seule campagne, compressés par Pillow et non par le scanner : le couple
TIFF + JP2 réel que Hugo va chercher reste ce qui tranche.

**Différé le 2026-09-16, et pourquoi.** Tout ce qui se faisait sans le scanner est fait :
gris 16 et 12 bits, refus de `I` et `F`, outil de régénération, filtre d'extension, dialogue
d'import, cache des dérivés. Ce qui reste attend trois choses, qui ne dépendent pas de ce
chantier : le couple TIFF + JP2 que Hugo va chercher au scanner (profondeur, boîtes de
résolution, poids et temps réels), ses deux décisions (format de stockage des masters, coût
d'import du JP2 sans perte), et une passe de QA jouée à la main. Le TIFF multipage, décidé,
attend que le cas se présente. **Ce qui rouvre** : l'arrivée des fichiers du scanner, ou une
décision de stockage qui ferait du JP2 le master courant — le décodage réduit (`reduce=1`,
mesuré) redeviendrait alors la première piste. La question plus large, voir ce que les
AUTRES changent sur une planche ouverte, n'est pas celle-ci et vit ailleurs.

**Relecture du 2026-09-16, faite avant de différer.** Lu : les onze commits du chantier du
jour, code et fiches, leurs diffs et la fiche et la passe ASSEMBLÉES. Trouvé et corrigé
(`7087fca` pour le code et le guide, ce commit pour la fiche et la passe) : cinq phrases qui
promettaient plus que le code — « le seul chemin vers 8 bits » (Kumiko passe par OpenCV),
« avant d'écrire quoi que ce soit » (le dossier est créé), un `.jp2` « absent » du dialogue
jamais mesuré, « réexportez en 16 bits » sans « non signés », un refus « immédiat » qui suit
le téléversement ; et, dans la fiche, un « gain de 44–49 % » qui était un poids, une
hypothèse déjà mesurée plus bas, une dérive du venv réparée entre-temps ; dans la passe, une
phrase sur le commit servi par la recette, qui aurait vieilli. Chaque test neuf a été prouvé
dans les deux sens, sur une copie de `HEAD` et jamais dans l'arbre partagé : dix-sept
mutations, chacune rouge en échec d'assertion sur le test visé, témoins verts ; le test du
cache, rouge sur l'instantané sans correctif et sur un mutant qui décide le 304 avant la
portée.
La suite par défaut ENTIÈRE, jouée sur un instantané de `7087fca` avec `lib/kumiko` et sous
le `.venv` : 1262 verts, aucun test sauté, 2 rouges étrangers au chantier — un module e2e
d'une autre session qui répète sa liste de surfaces, et `test_les_unites_systemd_lancent_des_
fichiers_EXÉCUTABLES`, qui appelle `git ls-files` et ne peut que tomber hors d'un dépôt git :
joué dans l'arbre, il est vert.
