---
chantier: IMG-1
statut: interrompu
---

# IMG-1 — accepter un format n'est pas savoir le convertir

**Arrêté sur** — le filtre d'extension de l'import depuis le disque, commit `cfbf85d`,
16 septembre, après le gris 16 bits (`fb53e67`), l'outil de régénération (`fd7cd38`) et sa
déclaration au cliquet des sorties (`944f071`). Rien n'est poussé. Ce qui reste attend
Hugo : la mesure de production, un JP2 réel du corpus, l'arbitrage du TIFF multipage.

## Reste

### Le gris 16 bits devient blanc
- [x] Un master en niveaux de gris 16 bits (`I;16` ou `I;16B`), TIFF comme JPEG 2000, importé depuis l'Atelier (⤓ Importer des images…) donne un dérivé dont les tons SUIVENT ceux du master : un dégradé 0 → 65535 sort en dégradé 0 → 255. Aujourd'hui `make_web_derivative` fait `convert("RGB")`, qui ÉCRÊTE — mesuré le 2026-09-14 : 0, 100, 255, 256, 1000, 16384, 32768, 65535 sortent en 0, 100, 255, 255, 255, 255, 255, 255. Un scan réel devient une page presque blanche, sans erreur à l'import
- [x] `pipeline/ocr._open_image` est corrigée DANS LE MÊME commit : elle ouvre le master et lui applique le même `convert("RGB")`, donc l'OCR d'un master gris 16 bits lit une page blanche même quand le dérivé est juste. Attendu : les deux sites appellent UNE fonction de conversion, et aucun `convert("RGB")` nu ne reste sur un master
- [x] Un test importe un vrai dégradé 16 bits par `POST /api/albums/{id}/import` et exige un dérivé NON saturé ; il est joué ROUGE sur le code d'avant correctif — sans quoi il pourrait passer sur n'importe quel dérivé
- [x] Les modes `I` (32 bits entiers) et `F` (flottant) sont mesurés comme `I;16` l'a été, et chacun reçoit une réponse : converti juste, ou refusé à l'import avec un message qui nomme le mode. Non mesurés le 2026-09-14
- [x] Le commentaire de `make_web_derivative` (« on convertit CMYK, 16 bits, palette ») ne promet que ce que la conversion corrigée fait vraiment
- [ ] Sur la base de production, `SELECT mode, COUNT(*) FROM planches GROUP BY mode` dit combien de planches ont un master `I;16`, `I;16B`, `I` ou `F` (la colonne est persistée depuis A6). Zéro : rien à rattraper. Sinon, la zone suivante n'est plus facultative. Si la colonne rend `None`, la commande de repli en lecture seule du Contexte lit le mode dans les masters eux-mêmes
- [ ] Si la mesure de production trouve un master `I` ou `F` importé avant le refus : `GET /api/regions/{id}/crop` (Transcription, vignettes) et `POST /api/figures` répondent un message qui nomme le mode, et non un 500 nu. `_open_image` lève désormais `OCRError` sur ce master, et seule la route OCR la rattrape — LU dans le code le 2026-09-16, non joué. Aucun master de ce mode : case sans objet

### Rattraper les dérivés existants
- [x] Un outil régénère le dérivé d'une planche depuis son master (`--album`, `--planche`, `--dry-run`, sur le patron de `tools/reindex_materiel.py`). Aujourd'hui `make_web_derivative` n'a qu'un appelant, `ingest_image` : un dérivé faux le reste, et changer `WEB_SCALE` ou `WEB_JPEG_QUALITY` ne touche aucune planche déjà importée
- [ ] Sur une planche segmentée puis régénérée, les cases restent à leur place dans l'Atelier : la régénération ne touche ni `largeur_px` ni `hauteur_px` (dimensions MASTER), et le navigateur recalcule l'échelle depuis l'image chargée. La base est ÉPROUVÉE par `tests/test_regenerer_derives.py` (ligne `planches` et régions identiques) ; le recalcul d'échelle est LU dans `static/viewer.js` (`webScale = naturalWidth / largeur_px`), pas joué dans l'Atelier
- [ ] Après régénération, une planche déjà ouverte dans l'Atelier montre le NOUVEAU dérivé au simple rechargement de la page, sans vider le cache. `GET /derivatives/…` répond un `FileResponse` sans `Cache-Control` (lu dans `main.py` le 2026-09-16) : un navigateur peut garder l'ancienne image par fraîcheur heuristique. Hypothèse, non mesurée — le middleware `no-cache` ne couvre que `/static` et les pages HTML

### JPEG 2000
- [ ] Un JP2 gris en 12 bits RÉEL, importé, donne un dérivé qui suit ses tons. `image_8_bits` le traite comme du 16 bits parce que le décodeur de Pillow étend toute précision à 16 (`shift = 16 - prec` dans `Jpeg2KDecode.c`, LU au tag 12.0.0) ; non mesuré, Pillow n'écrivant pas de JP2 12 bits. Si c'était faux, le dérivé sortirait presque NOIR
- [ ] Un JP2 RÉEL du corpus visé est inspecté, et la fiche dit s'il porte une boîte `resc`, `resd`, les deux, ou aucune. La case suivante ne se tranche pas sur un fichier fabriqué
- [ ] Un JP2 dont la résolution n'est écrite que dans `resd` reçoit un `dpi` à l'import — ou la fiche écrit pourquoi on s'y refuse. Aujourd'hui Pillow ne lit que `resc` : mesuré sur quatre fichiers forgés, `resc` → (300, 300), `resd` seule → `None`, `resd` puis `resc` → (300, 300). Sans dpi, pas de centimètres et la planche ne compte pas « avec résolution ». L'arbitrage est réel : `resc` dit ce que le scanner a capté, `resd` ce qu'on recommande d'afficher, et A6 décrit le MATÉRIEL
- [ ] Sous Windows, dans Chrome, le dialogue ouvert par ⤓ Importer des images… (Atelier) montre un fichier `.jp2` sans qu'on change le filtre. L'`accept` de `#file-input` ne cite aujourd'hui que `image/*,.tif,.tiff`, et le rangement de `.jp2` sous `image/*` n'a pas été vérifié
- [ ] Un test compare à `config.IMG_EXTS` les deux copies de la liste d'extensions que porte le front : l'`accept` de `#file-input` dans `templates/index.html`, et la regex `SD_IMG` de l'explorateur ShareDocs dans `static/viewer.js`. `SD_IMG` coïncide avec la liste aujourd'hui, et rien ne l'y oblige
- [ ] Le temps d'import d'un JP2 SANS PERTE est mesuré sur un VRAI scan dans l'image, et une décision est écrite s'il dépasse ce qu'un annotateur attend devant le toast « Import en cours… ». Le cas fabriqué — A4 à 300 dpi rempli de bruit, le pire cas pour la compression — prend 19,2 s pour le seul dérivé dans `bd-recette-app`, contre 2,6 s en avec perte, et la requête d'import attend pendant ce temps

### TIFF multipage
- [ ] Un TIFF de deux pages importé depuis l'Atelier est soit REFUSÉ avec un message qui dit « plusieurs pages », soit éclaté en deux planches — l'arbitrage est rendu avant le code. Aujourd'hui seule la première page est lue et la seconde disparaît sans avertissement (mesuré : `n_frames` = 2, taille et pixel de la page 1)

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

**La mesure de production est transmise à Hugo** par la session de coordination, aucune
session n'ayant d'accès au VPS. La commande de la case, puis celle de repli si la colonne
est vide — une ligne, base ouverte en lecture seule, chaque master ouvert (en-tête seul)
puis refermé avant le suivant, formats bornés comme dans l'app :

    docker exec bd-app python -c "import sqlite3; c = sqlite3.connect('file:/data/bd_annotator.sqlite?mode=ro', uri=True); print(c.execute('SELECT mode, COUNT(*) FROM planches GROUP BY mode ORDER BY 2 DESC').fetchall())"

    docker exec bd-app python -c "import sqlite3,collections;from PIL import Image as I;I.MAX_IMAGE_PIXELS=2*10**8;F=('TIFF','JPEG','JPEG2000','PNG','BMP','GIF','WEBP');exec(\"def m(p):\n try:\n  i=I.open('/data/'+p,formats=F);r=i.mode;i.close();return r\n except Exception as e:\n  return type(e).__name__\");c=sqlite3.connect('file:/data/bd_annotator.sqlite?mode=ro',uri=True);print(collections.Counter(m(p) for (p,) in c.execute('SELECT chemin_tiff FROM planches WHERE mode IS NULL AND chemin_tiff IS NOT NULL')))"

Jouées sur la RECETTE par la session de coordination : la première rend `[(None, 129)]` —
aucune planche de la recette n'a de mode en base —, la seconde `Counter({'RGB': 129})` en
0,7 s. Un TIFF 12 bits apparaît en `I;16` dans les deux.

**Deux arbitrages sont posés à Hugo, non tranchés.** *TIFF multipage* : la recommandation
transmise est de REFUSER. Éclater oblige soit à partager un master entre N planches — et
supprimer l'une effacerait le fichier des autres (`remove_planche_files`) —, soit à
réencoder chaque page en un nouveau master, ce qui contredit « le master n'est jamais
modifié ». *`resd` des JP2* : aucune recommandation sans un JP2 réel du corpus, ce que la
case exige déjà.

**Rattraper, si la mesure trouve des masters en `I;16` ou `I;16B`** — d'abord à blanc, puis
sans `--dry-run`. Les guillemets sont obligatoires : sans eux, `;` coupe la commande et
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
coordination, pas réparé ici.
