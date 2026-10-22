---
passe: Le lot 1 — importer, la copie de travail, la collection de l'Atelier
chantier: —
duree: 95 min
derniere: —
---

# QA — le lot 1 : l'import en lot dans la Bibliothèque, la copie de travail à 300 dpi, l'Atelier qui choisit sa collection

**Écrite le 2026-10-21, complétée et vérifiée le 2026-10-22 sur la recette reconstruite sur `ad2e66a`** (décor de l'état `base` migré en schéma 34 : collections, accès, l'album 2 et ses quatre masters TIFF relus en base). Non jouée. Elle porte sur le lot entier :
`UX-11` (`9e501ea`, `7a221c8` : « ⤓ Importer des planches… » dans la fiche d'un album),
`IMG-1`, zone « La copie de travail » (`e86aadc`, `f3d821f`, `ae2fd1f`, `036b693`, `0f4b612`,
`a118461` : l'import ne garde qu'une copie JPEG à 300 dpi effectifs, le champ « Où vivent les
masters », l'outil de rattrapage) et `UX-19` (`af3ffd9` : la liste *Collection* avant *Album*
dans l'Atelier) ; puis les petits — `UX-13` (`41386ac` : « Rattachée à » surligne sa case),
`INFRA-5` (`6ccd8cb` : la Recherche et l'Exploration reprennent leur état par le menu), `UX-18`
(`6078b5b` : « Tout valider » en une requête, un lot qui nomme ses albums), `AUTH-12` (`8e5ee14`)
et `UX-16` (`e2ff809`) dans « Comptes et groupes », l'import à l'unité de l'Atelier (`a05df55`) —
et `ANN-8` (`9c8a9cc` … `da108ba`, puis `50c70bc` … `23bf9db` : le libellé du verrou, Ctrl+Z qui
rend locuteur et situation, les champs de personnage, les tags à l'apostrophe, les champs à 320 px,
le locuteur qui part avec le type, les homonymes).

**Ce que les tests couvrent déjà — ne pas le refaire ici** : l'ordre d'envoi et la boucle de
l'import (tables Node, `tests/js/import-planches.test.js`, et l'e2e `test_e2e_import_lot.py`),
le refus du SERVEUR à qui ne fait que lire (404, rien en base ni sur le disque), l'en-tête
anti-CSRF ; la géométrie de la copie de travail et le recadrage d'une région depuis elle
(`test_copie_de_travail.py`), l'outil de rattrapage (`test_convertir_copies_de_travail.py`),
l'origine du master, rendue par aucune route ; le défaut, la rétention, les liens et les gardes CONC-3
de la liste *Collection* (`test_e2e_atelier_collection.py`), la mesure de reflow et de police ;
la validation tout-ou-rien, son journal et ses gardes (`test_validation_lot.py`) ; un stockage de
session absent (`test_e2e_navigation.py`) ; l'annulation d'un lien dont l'objet a disparu
(`test_undo_liens.py`) ; la clé des tags (`test_cle_tag.py`, sous les deux langages).
**Ce qui se regarde ici** : ce que l'écran DIT pendant un import de vrais scans, ce que la
copie de travail donne à voir, et si l'on s'y retrouve dans l'Atelier sous chaque identité.

**Ce que la passe ne juge pas** : l'import ShareDocs, qui valide désormais planche par planche
(`7a221c8`) sans rien changer à l'écran, et demande un compte Huma-Num ; le correctif « une
résolution de 1 dpi n'en est pas une » (`91743c6`), sans rien de visible ; `master_origine`,
qu'aucune surface ne montre ; la décision sur le format des masters, qui reste à Hugo ;
`A11Y-3` — l'audit d'accessibilité voit le contraste 1:1 et le texte hors champ, rien ne change à
l'écran — et le contraste élevé audité d'`ANN-8` ; la région des messages posée d'avance, dont
seul un lecteur d'écran dirait l'effet, et aucun ne pilote cette passe ; ↓ puis Entrée pendant
que la liste se recharge (`ANN-8`, `c21cf58`), qu'un doigt ne sait pas jouer à l'instant voulu
— les tests le tiennent ; la consigne « #123 » du guide (`72447d8`), qui ne change rien à
l'écran ; l'annulation refusée quand un autre a changé le locuteur depuis (`23bf9db`), jouée par
les tests sous deux identités.

**Les scans d'essai** de `C:\temp\scans-essai` sont des œuvres sous droits : la passe les
importe sur la recette, locale, et nulle part ailleurs ; la dernière zone retire leurs copies
du dossier de travail. Les centimètres attendus ont été MESURÉS sur ces fichiers le 2026-10-21 :
`esther-vol1_006` et `_008` font 3667 × 4728 px à 400 dpi, `_007` 3748 × 4710 ; les JPEG 2000
`esther-vol6_*` n'écrivent aucune résolution. L'écran écrit les centimètres avec un POINT
décimal et sans zéro final (« 23.3×30 cm »).

Les zones se jouent DANS L'ORDRE : chacune s'appuie sur ce que la précédente a laissé. Une
fenêtre privée par compte, ouverte pour cette passe et gardée jusqu'au bout — l'Atelier
retient son choix de collection dans le navigateur, et la zone de l'Atelier mesure ce qu'il
fait quand rien n'est retenu. La dernière zone rend la recette.

## Reste

### Le décor — `C:\temp\bd-recette\etat-de-base.ps1`, PowerShell, puis comptes `admin-bd` et `proprio`

- [ ] `C:\temp\bd-recette\etat-de-base.ps1 restaurer` répond « bd-app : healthy » (ou « running ») — la passe crée des albums et un projet, importe des scans, convertit des masters : la dernière zone rend la recette
- [ ] Sous `admin-bd` (une fenêtre privée par compte, pour toute la passe), `https://bd.127-0-0-1.sslip.io/administration?vue=instance` : « 🏷️ Version servie » affiche `ad2e66a` ou plus récent — sur un serveur plus ancien, ni l'import en lot ni la copie de travail ni la liste *Collection* n'existent, et rien de ce qui suit ne mesure
- [ ] Dans une fenêtre PowerShell gardée pour la passe : `$d = 'C:\temp\bd-recette'; $s = 'C:\Users\hsemil01\AppData\Local\Temp\claude\c--Dev-BD-ditor\29b58d2d-5790-445f-a997-26aebc1704cb\scratchpad'; function recette { docker compose -p bd-recette --project-directory $d --env-file "$d\.env" -f C:\Dev\BD_ditor\deploy\docker-compose.yml -f "$d\override.yml" -f "$s\contexte-recette.yml" @args }; [Console]::OutputEncoding = [Text.Encoding]::UTF8` puis `recette ps` : la ligne `bd-app` dit « Up » (si `contexte-recette.yml` n'existe plus, retirer son `-f` : `exec` n'en a pas besoin)
- [ ] Le dossier de travail, HORS du dépôt : `$t = 'C:\temp\qa-lot1'; $e = 'C:\temp\scans-essai'; New-Item -ItemType Directory -Force "$t\tiff", "$t\jp2-a", "$t\jp2-b" | Out-Null; Copy-Item "$e\esther-vol1_006.tif" "$t\tiff\page-1.tif"; Copy-Item "$e\esther-vol1_007.tif" "$t\tiff\page-2.tif"; Copy-Item "$e\esther-vol1_008.tif" "$t\tiff\page-10.tif"; Set-Content -Encoding ascii "$t\tiff\page-3.tif" "pas une image"; Copy-Item "$e\esther-vol6_00[4-9].jp2" "$t\jp2-a"; Copy-Item "$e\esther-vol6_01[0-2].jp2" "$t\jp2-b"` — puis `(Get-ChildItem -Recurse $t -File).Count` répond `13` (quatre `.tif` dont un faux, six puis trois `.jp2`)
- [ ] Sous `proprio`, Bibliothèque, **+ Nouvel album** : titre « Lot TIFF QA », *Collection* « Collection Test », *Enregistrer* ; puis **+ Nouvel album** : « Lot JP2 QA », *Collection* « Étude B », *Enregistrer* — les deux lignes paraissent dans la liste, « 0 pl. »
- [ ] Sous `admin-bd`, Administration, vue « Projets », **+ Nouveau projet** : nom « Projet QA », « ouverte » laissé coché, *+ Créer le projet* — sa fiche s'ouvre ; la bande du haut propose désormais une liste *Projet* (la zone de l'Atelier en a besoin)

### Le bouton, à qui écrit — comptes `proprio` puis `lectrice`, Bibliothèque, « Lot TIFF QA » encore vide

- [ ] Sous `proprio`, fiche de « Lot TIFF QA » : sous *Sur les collections*, un bouton « ⤓ Importer des planches… », dont l'infobulle dit « Choisir des images : elles entrent dans l'ordre de leurs noms, à la suite des planches » ; le tableau des planches dit « Aucune planche : « ⤓ Importer des planches… » les fait entrer. »
- [ ] Sous `lectrice` (qui lit « Collection Test » sans y écrire), fiche de « Lot TIFF QA » : AUCUN bouton « ⤓ Importer des planches… », et le tableau dit seulement « Aucune planche. »

### Importer en lot : l'ordre des noms, un refus nommé — compte `proprio`, Bibliothèque, « Lot TIFF QA »

- [ ] Noter le nombre de planches de la bande d'outils (« … planches »), puis « ⤓ Importer des planches… » : le dialogue du système s'ouvre sur les images seulement et laisse en choisir PLUSIEURS — dans `C:\temp\qa-lot1\tiff`, Ctrl+A sélectionne les quatre `.tif`, *Ouvrir*
- [ ] Quelques secondes plus tard, à côté du bouton : « 3 planches importées, 1 échec », et dessous une ligne « page-3.tif : Échec de l'ingestion : cannot identify image file … » — le fichier refusé est NOMMÉ, et « page-10.tif », qui vient après lui, est entré quand même
- [ ] Le tableau montre trois planches dans cet ordre : « planche 1 » (i.001) avec « 400 dpi · RGB · 23.3×30 cm », « planche 2 » (i.002) avec « 400 dpi · RGB · 23.8×29.9 cm », « planche 3 » (i.003) avec « 400 dpi · RGB · 23.3×30 cm » — `page-2` (le seul à 23,8 cm) avant `page-10` : l'ordre « naturel », où 2 vient avant 10, et les centimètres du SCAN, que la copie réduite ne change pas (cet ordre a été choisi en route, sans décision de Hugo : s'il ne convient pas, ne pas cocher et le noter)
- [ ] Sans avoir rechargé la page : la ligne « Lot TIFF QA » de la liste dit « 3 pl. », et le nombre de planches de la bande d'outils a gagné 3
- [ ] Le serveur n'a gardé du TIFF qu'une copie de travail réduite à 75 % : lire `N` dans l'adresse de la fiche (`album=N`), puis `recette exec app python -c "import os; from PIL import Image; d = '/data/corpus/album_N'; [print(f, os.path.getsize(os.path.join(d, f)) // 1024, 'Ko', Image.open(os.path.join(d, f)).size) for f in sorted(os.listdir(d))]"` (N remplacé) : trois lignes `planche_0001.jpg … (2750, 3546)`, `planche_0002.jpg … (2811, 3532)`, `planche_0003.jpg … (2750, 3546)`, chacune de quelques milliers de Ko au plus — aucun `.tif`, là où chaque scan pesait plus de 50 000 Ko

### Un import long : la progression, un seul à la fois, Arrêter — compte `proprio`, Bibliothèque, « Lot JP2 QA »

- [ ] « ⤓ Importer des planches… », dans `C:\temp\qa-lot1\jp2-a` les six `.jp2`, *Ouvrir* : aussitôt « Import : 1 sur 6 — esther-vol6_004.jp2 », une barre d'avancement et un bouton « Arrêter » ; « ⤓ Importer des planches… » est éteint ; toutes les cinq ou six secondes la ligne passe au fichier suivant (« Import : 2 sur 6 — esther-vol6_005.jp2 »…) et la barre avance
- [ ] Pendant l'import, F5 : le navigateur demande de confirmer avant de recharger (« Recharger le site ? » dans Chrome) ; *Annuler* : la page reste, et la progression continue au fichier suivant
- [ ] Pendant l'import, ouvrir « Lot TIFF QA » dans la liste de gauche : son « ⤓ Importer des planches… » est ÉTEINT, et son infobulle dit « Un import est en cours dans « Lot JP2 QA » »
- [ ] Rester sur « Lot TIFF QA » jusqu'à la fin : une bulle verte dit « « Lot JP2 QA » : 6 planches importées », le bouton de « Lot TIFF QA » se rallume, et la ligne « Lot JP2 QA » de la liste dit « 6 pl. »
- [ ] Rouvrir « Lot JP2 QA » : le bilan « 6 planches importées » est là ; ses six planches portent sous leur numéro « RGB » seul — ni dpi, ni centimètres : ces JPEG 2000 n'écrivent pas leur résolution, et rien n'est inventé
- [ ] « ⤓ Importer des planches… », dans `C:\temp\qa-lot1\jp2-b` les trois `.jp2` ; pendant « Import : 1 sur 3 — esther-vol6_010.jp2 », cliquer « Arrêter » : il devient « Arrêt… », éteint ; le fichier en cours va au bout, puis le bilan dit « 1 planche importée — 2 fichiers non envoyés : import arrêté » (si le clic est parti plus tard : k importées, 3 − k non envoyés)
- [ ] La planche entrée vient À LA SUITE des six autres : « planche 7 » (i.007), « RGB »
- [ ] Un JPEG 2000 sans résolution est gardé à sa taille : `N` lu dans l'adresse de la fiche, la commande de la zone précédente sur `/data/corpus/album_N` liste `planche_0001.jpg … (2757, 3546)` — les dimensions mêmes d'`esther-vol6_004.jp2` — jusqu'à `planche_0007.jpg … (2771, 3546)`, aucun `.jp2`

### La fiche dit où vivent les masters — compte `proprio`, Bibliothèque, « Lot TIFF QA »

- [ ] « ✎ Modifier l'album » : la modale « Éditer l'album », groupe « Édition (détenue) », porte après « Source de numérisation » un champ « Où vivent les masters », vide, dont l'exemple dit « ex. ShareDocs, Projet/Scans ; disque de l'équipe » et l'infobulle « Le serveur ne garde qu'une copie de travail à 300 dpi : dites où sont les scans d'origine. »
- [ ] Y taper « Disque de l'équipe, Esther/vol1 », *Enregistrer* : « Album enregistré », et la fiche dit sous le titre « Masters : Disque de l'équipe, Esther/vol1 » — encore là après F5

### L'Atelier s'ouvre sur une collection — comptes `proprio` puis `admin-bd`, Atelier

- [ ] Sous `proprio`, dans sa fenêtre où l'Atelier n'a jamais été ouvert, `https://bd.127-0-0-1.sslip.io/` : dans la barre latérale, « Collection » et sa liste viennent AU-DESSUS d'« Album » ; la liste propose « Collection Test », « Essai qui entre », « Étude B », puis « Toutes les collections du projet » en dernier, et c'est « Collection Test » qui est choisie (`proprio` ne lit pas la base « Projet principal », protégée : l'Atelier prend la première qu'il lit) ; *Album* ne propose que « esther v1 » et « Lot TIFF QA (3) »
- [ ] *Collection* → « Étude B » : *Album* ne propose plus que « esther v1 » et « Lot JP2 QA (…) » — esther v1, rangé dans les deux, paraît dans chacune
- [ ] *Collection* → « Essai qui entre » (aucun album) : *Album* ne dit que « — aucun album dans cette collection — », la liste des planches est vide, et la scène dit « Sélectionnez ou importez une planche pour commencer. » — l'album d'avant ne reste pas affiché
- [ ] *Collection* → « Toutes les collections du projet » : *Album* propose les trois albums que `proprio` lit, « esther v1 », « Lot TIFF QA (3) » et « Lot JP2 QA (…) »
- [ ] *Collection* → « Étude B », puis F5 : « Étude B » revient ; ouvrir la Bibliothèque : aucune case de collection n'y est cochée, et la liste montre les trois albums — le choix de l'Atelier ne la filtre pas
- [ ] Sous `admin-bd`, première visite de l'Atelier dans sa fenêtre : la liste *Collection* commence par « Projet principal » (la base du projet), puis les autres collections de A à Z, et « Toutes les collections du projet » en dernier ; c'est « Toutes les collections du projet » qui est choisie — la base, qu'il lit, ne contient encore aucun album — et *Album* propose tous les albums du projet, « Eau-terre » et « Annee_lievre-1 » compris
- [ ] Sous `admin-bd`, Bibliothèque, **+ Nouvel album** : *Collection* est déjà sur « Projet principal », la base ; titre « Base QA », *Enregistrer* ; retour à l'Atelier, F5 : la collection choisie est maintenant « Projet principal », et *Album* propose « Base QA (0) » seul
- [ ] Sous `admin-bd`, *Collection* → « Étude B » ; bande du haut, *Projet* → « Projet QA » : *Collection* ne propose que « Projet QA » et « Toutes les collections du projet », celle-ci choisie (la base du projet neuf est vide), et *Album* dit « — aucun album — » ; *Projet* → « Projet principal » : « Étude B » revient — le choix est retenu projet par projet

### Les liens posent la collection — comptes `proprio` puis `stagiaire`

- [ ] Sous `proprio`, Atelier, *Collection* → « Collection Test » ; puis Bibliothèque, nom « Étude B » → onglet *Albums* → « esther v1 » (sa fiche dit « ← Étude B ») → le ↗ de sa première planche : l'Atelier s'ouvre avec *Collection* « Étude B » et *Album* « esther v1 » — la collection d'où l'on vient, et non « Collection Test », où esther v1 vit aussi et qui vient avant
- [ ] Sous `proprio`, Bibliothèque, fiche de « Lot TIFF QA » : clic droit sur le ↗ de « planche 1 » → *Copier l'adresse du lien* ; dans l'onglet de l'Atelier (encore sur « Étude B »), coller cette adresse en y retirant `&collection=…`, Entrée : *Collection* passe d'elle-même à « Collection Test », et « Lot TIFF QA » s'ouvre sur sa planche 1 — jamais un album ouvert hors de la liste
- [ ] Sous `proprio`, copier de même l'adresse du ↗ d'une planche de « Lot JP2 QA » ; sous `stagiaire`, qui ne lit pas « Étude B », la coller dans la barre d'adresse : l'Atelier dit « Album du lien introuvable. », et *Album* ne propose pas « Lot JP2 QA »

### Ce qui part de la copie de travail : la Transcription, une figure — compte `proprio`, Atelier, « Lot TIFF QA »

- [ ] *Collection* « Collection Test », *Album* « Lot TIFF QA (3) », planche « pl.2 », mode Édition (`E`) : un cliquer-glisser autour d'une bulle bien reconnaissable laisse un cadre exactement là où on l'a tracé, et le panneau dit *Type* « case » (une région tracée hors de toute case en est une) ; passer *Type* à « bulle »
- [ ] Mode Transcription (`T`) : « Bulle 1 / 1 », et la vue agrandie montre exactement ce que le cadre entoure — la même bulle, ni décalée vers le bas à droite, ni élargie d'un tiers (ce que donnerait une copie à 75 % lue sans son échelle)
- [ ] Retour en Édition, la bulle sélectionnée, « ＋ Figure » : « Figure ajoutée (1). » ; « Exporter (1) » ouvre « Exporter des figures », *Télécharger* : « 1 figure(s) exportée(s). » et un zip arrive ; son image montre la même bulle, nette, au même cadrage que la vue de la Transcription

### Rattraper les masters d'avant : l'outil, sur la recette — PowerShell, puis compte `proprio`

- [ ] AVANT l'outil, sous `proprio` : Bibliothèque, fiche d'« esther v1 » (l'adresse dit `album=2`) : sous les numéros de planche, AUCUNE ligne « … dpi · … cm » (ces masters ont été importés avant qu'on note la résolution) ; Atelier, « esther v1 », première planche, mode Transcription, « Bulle 1 / … » : faire une capture d'écran de la vue de la bulle, et noter un mot de son texte
- [ ] `recette exec app python tools/convertir_en_copies_de_travail.py --album 2` (à blanc) : la première ligne dit « ⚠ Convertir EFFACE le master du serveur : … », puis quatre lignes « · corpus/album_2/planche_000k.tif (à convertir) — planche(s) … : 49,6 Mo → … » (« 50,5 Mo » pour `planche_0002.tif`), puis « À blanc : 4 fichier(s) à convertir, 4 planche(s) ; … seraient libéré(s). Rien n'a été écrit — relancez avec --appliquer pour convertir. »
- [ ] F5 sur la fiche d'« esther v1 » : toujours AUCUNE ligne « … dpi » — le passage à blanc n'a rien écrit
- [ ] `recette exec app python tools/convertir_en_copies_de_travail.py --album 2 --appliquer` : quatre lignes « ✓ corpus/album_2/planche_000k.tif (converti) — … », puis « ✓ 4 fichier(s) converti(s), 4 planche(s) ; … libéré(s) sur le serveur. » (un peu moins de 200 Mo), et aucune liste de fichiers « qu'aucune planche ne désigne »
- [ ] F5 sur la fiche d'« esther v1 » : chaque planche porte maintenant « 400 dpi · RGB · 23.3×30 cm », sauf la deuxième ligne, « 400 dpi · RGB · 23.8×29.9 cm » — la résolution a été lue dans le master avant qu'il parte ; les vignettes sont inchangées
- [ ] Atelier, F5, « esther v1 », première planche : les cadres des cases et des bulles sont toujours sur le dessin ; mode Transcription, « Bulle 1 / … » : la vue est celle de la capture — la même bulle, au même cadrage
- [ ] Recherche, taper le mot noté : le résultat qui cite cette bulle d'« esther v1 » porte une vignette qui montre la même bulle, entière
- [ ] Relancer `… --album 2 --appliquer` : « ✓ 0 fichier(s) converti(s), 0 planche(s) ; 0 o libéré(s) sur le serveur. » — rien à refaire

### Annoter : rattacher, protéger, annuler — compte `proprio`, Atelier, « Lot TIFF QA », « pl.3 »

- [ ] Mode Édition (`E`) : tracer un grand cadre autour d'une première case du dessin, puis un autre autour d'une deuxième — chacune dit *Type* « case » ; puis un petit cadre autour d'une bulle de la PREMIÈRE case, *Type* → « bulle »
- [ ] La bulle sélectionnée, cliquer la liste « Rattachée à » puis la refermer par Échap, sans rien choisir : si elle désigne une case, cette case porte le halo de survol sur la planche ; au clavier, flèches ↑ ↓ sur la liste fermée : à chaque « case #… » choisie, CETTE case seule porte le halo ; sur « — aucun (planche) — », aucun halo
- [ ] Laisser « Rattachée à » sur la première case (celle qui contient la bulle), puis Tab : le halo disparaît avec le focus ; dans l'arbre de structure, la bulle est rangée sous cette case ; et survoler un nœud de l'arbre surligne toujours sa région, comme avant
- [ ] Dans la bande de la planche, le bouton dit « 🔓 Protéger des passes auto », et son infobulle « … N'empêche aucune annotation : inutile avant d'annoter. » ; un clic : il dit « 🔒 Protégée par vous », une bulle « Planche protégée des passes auto 🔒 » ; un second clic : « Protection levée 🔓 », le bouton redit « 🔓 Protéger des passes auto » — ce libellé est une PROPOSITION : s'il ne convient pas, ne pas cocher et noter celui qu'il faudrait
- [ ] Toujours sur « pl.3 », *Type* d'un nouveau petit cadre tracé autour d'un personnage → « personnage » ; mode Annotation (`A`), section « Personnage », champ « Identifier le personnage… » : taper « Zed QA », la liste propose « ➕ Créer « Zed QA » », Entrée — « Zed QA » s'affiche dans la section
- [ ] Aussitôt, sélectionner la bulle ; section « Locuteur », champ « Attribuer un personnage… » : taper « Zed QA » — la liste propose « Zed QA » une seule fois, et AUCUN « ➕ Créer « Zed QA » » ; Entrée : « Zed QA » est le locuteur de la bulle
- [ ] Sélectionner la première case ; section « Situation (scène) » : taper « lieu : falaise », Entrée — « lieu : falaise » s'affiche sous la section
- [ ] Mode Édition, la première case sélectionnée, « Supprimer la région », le navigateur demande « Supprimer cette région et ses sous-régions ? », *OK* : la case et sa bulle disparaissent du dessin et de l'arbre ; puis Ctrl+Z : une bulle « Annulé : … » ; la case et la bulle reviennent au même endroit, la bulle toujours sous la case
- [ ] Mode Annotation : la bulle a toujours « Zed QA » pour locuteur, et la case toujours « lieu : falaise » — avant le lot, Ctrl+Z ne rendait ni l'un ni l'autre
- [ ] La bulle sélectionnée, champ « Ajouter un tag… » : coller `c’est pluriel` (copié d'ici, apostrophe courbe), Entrée — l'étiquette paraît ; puis une SEULE flèche ↓ : une proposition de la liste est surlignée
- [ ] Sélectionner la boîte « Zed QA », champ des tags : taper au clavier `c'est pluriel` (apostrophe droite) — la liste propose l'étiquette déjà posée ; Entrée : l'étiquette ajoutée s'écrit « c’est pluriel », avec l'apostrophe courbe de la première — un seul tag, et non deux
- [ ] Mode Édition, la bulle (locuteur « Zed QA ») sélectionnée, *Type* → « case » : une bulle « Locuteur « Zed QA » retiré : ce type de région n'en porte pas. Ctrl+Z le rend. » (une proposition de phrase : si elle ne convient pas, ne pas cocher et noter la bonne) ; en mode Annotation, la région n'a plus de section « Locuteur »
- [ ] Aussitôt Ctrl+Z : « Annulé : modification d'une région et retrait de son locuteur » ; *Type* redit « bulle », et en mode Annotation son locuteur est de nouveau « Zed QA » — un seul Ctrl+Z pour les deux
- [ ] Un homonyme, posé à la main sur la recette (l'Atelier ne crée jamais un second « Zed QA »), dans la fenêtre PowerShell de la passe : `recette exec app python -c "import sqlite3, config; c = sqlite3.connect(str(config.DB_PATH)); c.execute('INSERT INTO personnages (nom, serie) VALUES (?, ?)', ('Zed QA', 'Serie QA')); c.commit(); print(c.execute('SELECT id, serie FROM personnages WHERE nom = ?', ('Zed QA',)).fetchall())"` — deux lignes : une à `None`, une à `'Serie QA'`
- [ ] Atelier, F5, « pl.3 », mode Édition : un nouveau petit cadre autour d'une autre bulle, *Type* → « bulle » ; mode Annotation, « Attribuer un personnage… » : taper « Zed QA » puis Entrée SANS flèche — rien n'est attribué ; la liste ne montre que les deux « Zed QA », l'un dit « sans série », l'autre « Serie QA », aucune n'est surlignée et aucun « ➕ Créer » n'est offert ; une seconde Entrée ne décide toujours rien
- [ ] ↓ jusqu'à la ligne « Serie QA », Entrée : « Zed QA » devient le locuteur de cette bulle ; la première bulle garde le sien
- [ ] Dans l'Atelier, l'album « Lot JP2 QA » (*Collection* « Étude B »), « ⤓ » de la barre latérale → dans `C:\temp\qa-lot1\jp2-b`, un fichier que l'arrêt de l'import long a laissé de côté (`esther-vol6_011.jp2` si l'arrêt est parti au premier) : « Import en cours… », puis « Planche importée », et une planche de plus en bas de la liste (« pl.8 » si sept étaient entrées) — l'import à l'unité passe désormais par le même envoi que la Bibliothèque, sans rien changer à l'écran

### La Recherche et l'Exploration reprennent leur état — compte `proprio`, nav du haut

- [ ] Recherche : taper « pluriel », *Tous les types* → « bulle » : un résultat, la bulle de « Lot TIFF QA » ; dans le nuage de tags déplié, « c’est pluriel » paraît UNE fois
- [ ] Nav → « Bibliothèque », puis nav → « Recherche » : le champ redit « pluriel », le type « bulle », et le même résultat est là sans rien retaper ; l'adresse porte `q=pluriel`
- [ ] Exploration : *Vue* → « Concordance (KWIC) » ; nav → « Atelier », puis nav → « Exploration » : la vue est toujours « Concordance (KWIC) »
- [ ] Dans la barre d'adresse : `https://bd.127-0-0-1.sslip.io/recherche?q=falaise`, Entrée : le champ dit « falaise », et non « pluriel » — une adresse qui porte un état l'emporte sur ce qui est retenu ; puis nav → « Bibliothèque », nav → « Recherche » : « falaise » revient, c'est le dernier état

### Valider d'un geste, un lot qui dit sur quoi il travaille — compte `proprio`, Bibliothèque

- [ ] Fiche de « Lot TIFF QA », « ✔ Tout valider » : le navigateur demande « Valider 3 planche(s) de cet album ? » ; *OK* : à côté du bouton, « 3 planches validées. », et le ✔ de chacune des trois planches est vert et enfoncé, son infobulle « Validée le … — cliquer pour retirer la validation »
- [ ] « ✔ Tout valider » une seconde fois : « Toutes les planches sont déjà validées. », sans question
- [ ] Nom « Étude B » → onglet *Albums* : cocher « Lot JP2 QA » seul ; la barre au-dessus dit « 1 album sélectionné » ; cocher « Segmenter », « ▶ Lancer » : une bulle « Lot lancé : N planches » (N, le nombre de planches de « Lot JP2 QA » : 8 si la zone de l'import long s'est arrêtée au premier fichier), et au-dessus du cadre une ligne « Lot #… segmenter » avec dessous « N planches de « Lot JP2 QA » », et une barre qui avance jusqu'à « terminé — N/N »

### Comptes et groupes : l'article, le lien sans flèche — compte `admin-bd`, Administration

- [ ] Vue « Comptes et groupes », axe *Collections*, sans fiche ouverte : la colonne de la fiche dit « Choisissez une collection dans la liste pour ouvrir sa fiche. » ; dans le filtre de la liste, `zzz` : « Aucune collection ne correspond à « zzz ». » ; axe *Comptes* : « Choisissez un compte dans la liste pour ouvrir sa fiche. »
- [ ] Axe *Collections*, ouvrir « Étude B » : sous le panneau « Qui entre », le lien dit « Décrire dans la Bibliothèque », SANS ↗ ; un clic l'ouvre dans le MÊME onglet, sur la fiche d'« Étude B », onglet *Description* ; Précédent ramène à la fiche d'« Étude B » dans « Comptes et groupes »

### À l'étroit et à grande police — compte `proprio`, outils de développement en mode appareil

- [ ] 320 px, Atelier, ☰ (« Planches ») : le tiroir montre « Collection » et sa liste, puis « Album » et la sienne, chacune dans la largeur du tiroir ; la page ne défile pas de côté
- [ ] 320 px, menu « Aa » → « A+ » jusqu'au plus grand, ☰ : les deux libellés et les deux listes restent lisibles et ne débordent pas du tiroir, et la liste des planches s'atteint en faisant défiler le tiroir ; « ↺ » ramène à 100 %
- [ ] 320 px, toujours au plus grand « A+ », Atelier, « Lot TIFF QA », « pl.3 », mode Annotation, la bulle sélectionnée : les champs « Attribuer un personnage… » et « Ajouter un tag… » tiennent dans la largeur du tiroir — aucun ne déborde, le tiroir ne défile pas de côté ; même chose sur la première case pour « dimension : valeur… » de la Situation ; puis « ↺ »
- [ ] 375 px, Bibliothèque, fiche de « Lot TIFF QA », « ⤓ Importer des planches… » → `C:\temp\qa-lot1\tiff\page-3.tif` seul : le bilan dit « Aucune planche importée, 1 échec », en rouge, et la ligne « page-3.tif : Échec de l'ingestion : … » passe à la ligne dans la largeur, sans défilement de côté

### Rendre la recette — `C:\temp\bd-recette\etat-de-base.ps1`, PowerShell, puis compte `proprio`

- [ ] `C:\temp\bd-recette\etat-de-base.ps1 restaurer` répond « bd-app : healthy » (ou « running »)
- [ ] Sous `proprio`, Bibliothèque rechargée : aucun album « … QA » dans la liste, et la fiche d'« esther v1 » ne montre plus de ligne « … dpi » sous ses planches — ses masters sont revenus avec l'état de base
- [ ] `Remove-Item -Recurse -Force C:\temp\qa-lot1`, et le zip de figure téléchargé est supprimé : `Test-Path C:\temp\qa-lot1` répond `False` — aucune copie des scans d'essai ne reste hors de `C:\temp\scans-essai`
