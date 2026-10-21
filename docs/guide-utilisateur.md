# Guide d'utilisation

Ce guide décrit **les gestes** : par où commencer, dans quel ordre, avec quel bouton. Les
**objets et les droits** — collection, groupe, portée, vocabulaire, qui peut quoi — sont
expliqués dans [`modele-et-droits.md`](modele-et-droits.md), auquel ce guide renvoie chaque
fois qu'un mot demande à être défini.

Les autres fichiers de `docs/` sont des **notes de conception** : ils expliquent pourquoi une
décision a été prise, pas comment se servir de l'outil. C'est ici qu'on cherche « comment
faire », là-bas qu'on cherche « pourquoi comme ça ».

---

## 1. Ce que l'outil fait, et ce qu'il ne fait pas

BéDéditeur sert à **annoter des bandes dessinées numérisées** et à interroger le résultat.

**Aucune intelligence artificielle n'entre dans la boucle d'annotation.** Le travail
interprétatif est intégralement humain. Trois moteurs automatiques existent — découpage des
cases, détection des bulles, reconnaissance de texte — et leur rôle est strictement de
**pré-remplir** ce que vous corrigerez. En particulier, **l'OCR n'écrase jamais un texte déjà
saisi par quelqu'un** : il ne remplit que le vide.

Ces trois moteurs sont **optionnels**. Sans eux, l'outil fonctionne entièrement : on dessine
les régions à la main et on saisit le texte. Une passe dont le moteur est absent répond par un
refus explicite, jamais par une erreur obscure. Le bloc **🩺 Moteurs** de l'Administration
dit lesquels sont là — et le bouton *Éprouver les moteurs* va plus loin en les **important
pour de bon**, parce qu'un moteur présent sur le disque peut très bien refuser de démarrer.

---

## 2. Les cinq surfaces

| Surface | Adresse | Ce qu'on y fait |
|---|---|---|
| **Bibliothèque** | `/corpus` | une **liste** et une **fiche** : à gauche les collections du **projet** où vous travaillez — la case d'une collection filtre les albums, son nom ouvre sa fiche — puis ses albums ; à droite la fiche ouverte. Créer et décrire les albums et les collections, **supprimer** un album (de sa collection, ou définitivement), régler **qui entre** dans une collection et ce qu'il peut y faire, régler sa diffusion et l'exporter, **importer les planches d'un album en lot**, lancer les traitements par lot, suivre l'avancement planche par planche |
| **Atelier** | `/` | tout ce qui se fait sur une planche : ajouter une image à l'album affiché, corriger le découpage, transcrire, annoter, relire la grammaire, exporter |
| **Recherche** | `/recherche` | interroger les dialogues, les notes et les tags ; chaque résultat rouvre l'Atelier pile sur la région |
| **Exploration** | `/exploration` | mesurer : distributions, concordance, croisements, comparaison de deux sous-corpus ; documenter le vocabulaire |
| **Administration** | `/administration` | ce qui porte sur l'**instance** et non sur un album : quels projets existent et qui y entre, ce que l'instance détient (**le fonds**, et les suppressions qu'on lui demande), quels comptes et quels groupes existent — et, pour un administrateur, qui entre dans quelle collection —, la version servie, l'état des moteurs |

Une barre de navigation commune les relie, sur les cinq pages. Les réglages d'affichage —
thème clair/sombre, contraste élevé, zoom de l'interface — y sont aussi, et suivent d'une
surface à l'autre. Elle dit enfin dans quel **projet** vous travaillez : le mot *Projet*,
suivi de son nom — ou d'une liste déroulante dès que vous en voyez plusieurs (§4,
*Bibliothèque*).

> **L'Administration n'est pas réservée**, et ça surprend. La page s'ouvre à tout le monde :
> c'est **chaque bloc** qui décide de ce qu'il montre — **👥 Comptes et groupes** n'apparaît
> que si le serveur vous le sert, **🏷️ Version servie** de même, **🗄️ Le fonds** aussi — il
> n'apparaît qu'à un administrateur —, **🗂️ Projets** ne montre
> que les projets que vous réglez, et l'état des moteurs est
> ouvert à tous, parce que savoir si l'OCR fonctionne n'est un pouvoir pour personne. Fermer
> la page entière aurait enfermé des choses qui n'ont rien à y faire.

> **Un mot sur le nom de la première.** La barre de navigation l'appelle **Atelier**, et
> c'est le nom retenu ici puisque c'est celui qu'on lit à l'écran. Elle s'est longtemps
> appelée **Visionneuse**, mot qu'on croise encore dans le code et dans les documents
> antérieurs : c'est la même page, `/`.

---

## 3. Le parcours en huit étapes

**Avant d'entrer dans une collection, vous entrez dans un projet** : son nom se lit en haut
de chaque page, et c'est de ce projet que la Bibliothèque vous montre les collections.

C'est l'ordre à suivre pour un corpus qui part de zéro. **Sur un corpus déjà rempli**, on
entre directement à l'étape 4, 5 ou 6 selon ce qui reste à faire : la Bibliothèque affiche
pour chaque planche son statut, sa validation et son avancement de relecture.

### Étape 1 — Constituer le corpus
**Bibliothèque · `+ Nouvel album`, puis `⤓ Importer des planches…` dans la fiche de l'album**

**L'album se crée dans la Bibliothèque, et seulement là.** C'est elle qui vous demande dans
quelle collection il entre — donc dans quel projet —, et l'application retient qui l'a
créé, quand et dans quel projet : c'est son **origine**, et c'est elle qui vous laissera le
supprimer vous-même si vous l'avez importé par erreur (§4, *Bibliothèque*, « Supprimer un
album »).
L'Atelier ne crée plus d'albums : le bouton `＋` de sa barre latérale a disparu.

**Les images d'un album entrent EN LOT depuis sa fiche, dans la Bibliothèque**, si vous
écrivez dans l'album : *⤓ Importer des planches…* ouvre un sélecteur où l'on choisit autant
de fichiers qu'on veut. Ils partent **un par un, dans l'ordre de leurs noms** — pas dans
celui que montre le sélecteur ; les nombres s'y lisent comme des nombres, `p2` avant
`p10` —, et chacun devient la planche suivante de l'album. À côté du bouton, l'import dit
où il en est (*Import : 3 sur 50 — p003.tif*) ; un scan lourd prend plusieurs secondes,
un album entier plusieurs minutes, et la page doit rester ouverte jusqu'au bout.
*Arrêter* laisse finir le fichier en cours et n'envoie pas les suivants. À la fin, un
bilan — *48 planches importées, 2 échecs* — et, sous lui, chaque fichier refusé avec sa
raison : un refus ne défait pas les planches déjà entrées et n'empêche pas les suivantes.
Réimportez les fichiers refusés une fois corrigés : ils s'ajoutent à la suite. Qui ne fait
que lire l'album ne voit pas le bouton.

**L'Atelier garde l'import à l'unité**, pour la page oubliée pendant qu'on annote : choisissez
la collection dans la liste *Collection* de la barre latérale, puis
l'album dans la liste *Album* qui la suit, puis, dans le menu *⇅ Import / Export* :
*⤓ Importer des images…* pour votre disque — l'image entre dans l'album affiché —, ou
*🖼 Depuis ShareDocs…* pour parcourir un dossier Huma-Num distant et importer une sélection
entière. Le formulaire ShareDocs propose, sous *Destination*, les
seuls albums où vous écrivez ; si vous n'en avez aucun, il le dit — *Aucun album où vous
écrivez : un album se crée dans la Bibliothèque, avec sa collection, puis ses planches
s'importent ici.* — et *Importer* reste éteint. Pour ajouter des planches à un album déjà
rempli, c'est le même geste : elles s'ajoutent à la suite.

**Dans l'Atelier, la collection se choisit avant l'album.** La liste *Collection* propose
les collections du projet où vous travaillez que vous lisez — sa collection de **base** en
tête, puis les autres dans l'ordre alphabétique — et, en dernier, *Toutes les collections
du projet*. La liste *Album* ne montre que les albums rangés dans la collection choisie ; un
album rangé dans deux collections paraît dans chacune, et *Toutes les collections du
projet* rend la liste entière du projet. Une collection où vous ne lisez aucun album le dit
dans la liste *Album* — *— aucun album dans cette collection —*. Quand vous n'avez rien
choisi, l'Atelier s'ouvre sur la base du projet ; si elle ne contient encore aucun
album que vous lisez, sur *Toutes les collections du projet* ; si vous ne la lisez pas,
sur la première collection de la liste. Votre choix est retenu par votre navigateur, **projet par
projet** et pour l'Atelier seulement : la Bibliothèque n'en est pas changée. Un lien vers un
album qui n'est pas dans la collection choisie passe à une collection qui le contient ; et
le lien *↗ Ouvrir dans l'Atelier* d'une planche, dans la fiche d'un album ouverte depuis une
collection de la Bibliothèque, ouvre l'Atelier sur cette collection. Le formulaire
ShareDocs, lui, propose toujours tous les albums du projet où vous écrivez.

**Sept formats sont acceptés, et rien d'autre** : TIFF et JPEG — les deux du corpus —, puis
JPEG 2000, PNG, BMP, GIF et WebP. La liste est courte exprès : elle borne aussi ce que le
décodeur d'images a le droit d'ouvrir, ce qui ferme une classe de fichiers piégés. Un
fichier hors liste est refusé sans rien enregistrer ; §6 dit à quoi ressemble le refus.

**Le serveur ne garde pas votre fichier** : il en garde deux images. Une **copie de
travail**, en JPEG à 300 dpi — un scan plus fin est réduit jusque-là (un scan à 400 dpi passe
aux trois quarts), un scan à 300 dpi ou moins est gardé à sa taille, comme un scan qui
n'écrit pas sa résolution (c'est le cas des JPEG 2000 du scanner de l'équipe). C'est d'elle
que partent la lecture automatique du texte, les vues de la Transcription et les figures. Et
un **dérivé web** allégé, qui est ce que vous voyez à l'écran. La résolution et le mode
colorimétrique du scan sont lus dans le fichier au passage, ce qui permettra d'afficher les
dimensions physiques en centimètres — ceux du scan, que la réduction ne change pas.

**Le master, lui, reste chez vous** — sur ShareDocs, un disque, des disques durs, selon le
projet. Gardez-le : c'est l'objet scientifique, et le serveur n'en a plus d'exemplaire.
L'outil note ce qu'il en sait pour chaque planche (le chemin ShareDocs d'un import depuis
ShareDocs, sinon le nom du fichier importé), et la fiche de l'album a un champ pour dire où
vivent ses masters (Étape 2).

*+ Nouvel album* propose les collections du projet où vous écrivez, et présélectionne sa
**collection de base** — celle qui reçoit aussi ce que le projet prend au fonds —, sauf si
vous venez d'ouvrir une collection : c'est alors elle qui est choisie. Si vous savez déjà à
quelle étude l'album appartient, choisissez sa collection au moment de le créer.

**Un document peut aussi venir du fonds** plutôt que d'un import : le responsable du projet
le prend parmi les notices du fonds, et quiconque écrit dans une collection peut y ranger un
album que le projet a déjà (§4, *Bibliothèque*, « Prendre un document »).

### Étape 2 — Décrire l'album
**Bibliothèque · fiche de l'album, puis `✎ Modifier l'album`**

La fiche s'ouvre à droite quand on choisit l'album dans la liste. *✎ Modifier l'album* ouvre
le formulaire où se saisissent la **paternité** (contributions : un nom, un rôle —
scénariste, dessinateur, coloriste…), les champs d'**édition** (date, éditeur, lieu, ISBN,
format), la **source de numérisation** (l'appareil et les conditions du scan) et **où
vivent les masters** (un dossier ShareDocs, un disque — facultatif, mais c'est le seul endroit
où l'outil le dira : le serveur ne garde qu'une copie de travail).
L'appartenance aux collections se lit et se règle dans la fiche même, sous *Sur les
collections*.

Ce n'est pas de la paperasse : c'est ce qui rendra le corpus citable et déposable. Le faire
maintenant coûte cinq minutes ; le faire deux ans plus tard suppose de retrouver l'exemplaire.

### Étape 3 — Pré-remplir *(optionnel)*
**Bibliothèque · cocher des albums ou des planches, puis `Segmenter` / `Bulles` / `OCR` et `▶ Lancer`**

Trois passes, dans cet ordre : les **cases**, puis les **bulles** à l'intérieur des cases, puis
le **texte** des bulles. Elles se lancent par lot, en tâche de fond, avec une barre de
progression et un bouton d'annulation. Le lot apparaît **au-dessus de sa sélection** : cochez
des albums dans l'onglet *Albums* d'une collection, ou des planches dans la fiche d'un album —
un lot porte sur l'un ou l'autre, jamais sur un mélange. Chaque lot dit sur quoi il travaille —
ses albums, ou « 3 planches de *Titre* » —, et ses erreurs se lisent sous sa barre, *Voir les
erreurs*. On peut aussi les
lancer planche par planche depuis l'Atelier (menu *⚙ Traitement*).

L'ordre de lecture — rangées de haut en bas, gauche à droite, bulles groupées par case — est
recalculé automatiquement après chaque passe.

Une planche **verrouillée** (🔒) est sautée par les lots : c'est ainsi qu'on protège un travail
manuel d'une repasse automatique.

Si un moteur n'est pas installé, cette étape se saute entièrement — la suite fonctionne
identiquement, avec plus de travail manuel à l'étape 4.

### Étape 4 — Corriger le découpage
**Atelier · mode Édition (`E`)**

Redimensionnez les régions par leurs poignées, ajustez au pixel près par saisie numérique,
dessinez les régions manquantes au cliquer-glisser, supprimez les fausses (`Suppr`). Une
région porte un **type** : case, bulle, personnage, texte, cartouche.

**Cette étape conditionne la suivante, et c'est la raison de sa place ici.** Le crop
plein écran du mode Transcription est découpé dans la copie de travail **à partir du cadre
de la région** : une bulle mal détourée est illisible, donc intranscriptible. Elle reste taggable,
en revanche — la géométrie contraint le texte, pas l'interprétation.

### Étape 5 — Transcrire et relire
**Atelier · mode Transcription (`T`), puis panneau Grammaire**

Le mode Transcription est un plein écran bulle à bulle : le crop net à gauche, l'éditeur à
droite, `Tab` et `Maj+Tab` pour avancer et reculer, un enchaînement possible sur tout l'album.
La sauvegarde est automatique.

**Le lettrage est en capitales, et l'OCR les restitue telles quelles.** Le bouton
*Normaliser la casse* propose la casse de phrase pour la bulle affichée — « ALORS TINTIN,
LE F.B.I. T'ATTEND » devient « Alors tintin, le F.B.I. t'attend ». Il ne fait rien tout
seul : c'est vous qui cliquez, et vous relisez avant de passer à la suivante. Deux choses
à savoir, parce qu'elles sont voulues :

- **les noms propres restent en bas de casse** (« tintin »). L'outil ne les connaît pas et
  ne les devine pas ; il vous laisse les relever, ce qui est plus rapide que de rattraper
  ceux qu'une devinette aurait inventés ;
- **les sigles ponctués sont préservés** (`F.B.I.`), les autres non (`FBI` devient `fbi`) —
  sur un texte tout en capitales, rien ne distingue `FBI` d'un mot ordinaire.

Le bouton s'éteint dès que la bulle n'est plus intégralement en capitales : le geste est
déjà fait, ou le texte a été corrigé, et le recliquer ne peut pas défaire votre travail.

Si l'analyse linguistique est installée, le **panneau Grammaire** apparaît dès qu'une région
sélectionnée porte du texte : il liste ses mots avec lemme, catégorie grammaticale et traits
morphologiques. Chaque mot se corrige à la main, ou se valide tel quel ; le bouton
*✓ Valider la région* valide tout d'un coup. Deux filtres aident à ne pas relire ce qui est
déjà fait : *mots lexicaux seulement*, et *pas encore traités*.

**Vos corrections ne sont jamais écrasées.** Elles vivent dans une couche séparée qui survit à
toute réindexation, y compris après un changement de modèle linguistique.

La Bibliothèque affiche par planche un **statut de relecture** — à faire, en cours, faite —
qui avance tout seul à mesure que les mots sont relus, et qu'on peut forcer si besoin.

### Étape 6 — Annoter
**Atelier · mode Annotation (`A`)**

C'est le cœur du travail. Sélectionnez une région ; le panneau de droite propose, selon son
type :

- le **locuteur** d'une zone de texte — bulle, cartouche ou texte : quelle entité
  personnage y parle. Celui d'un cartouche se choisit dans le registre des personnages,
  comme celui d'une bulle. On peut y créer une entrée pour un narrateur ; la façon de
  le nommer n'est pas encore arrêtée. Tapez le nom puis Entrée : s'il est déjà au
  registre, c'est ce personnage qui est pris, même tapé vite ; il n'est créé que si aucun
  ne porte exactement ce nom. Quand plusieurs le portent — un par série —, Entrée prend
  le premier de la liste : choisissez le vôtre dans les propositions. Une proposition
  surlignée aux flèches n'est prise que si elle correspond encore à ce qui est tapé : si
  la liste n'a pas encore suivi votre frappe, Entrée ne prend rien et la liste se met à
  jour — choisissez dans celle-ci. Une zone de texte qu'on passe en case ou en boîte
  personnage **perd son locuteur** — un message le dit —, et un seul Ctrl+Z rend le type
  et le locuteur ;
- la **présence** dans une boîte personnage — quelle entité y est montrée, choisie de la
  même façon ;
- le **profil** du personnage (dimensions de cible `personnage`) ;
- la **situation** d'une case (dimensions de cible `case`). Le champ attend la forme
  « dimension : valeur », deux-points compris — `lieu : falaise` —, et la phrase sous le
  champ le rappelle. Sous cette forme, Entrée suffit, sans attendre les propositions : la
  valeur est reprise si elle existe, créée sinon. Un mot tapé seul, « falaise », ne crée
  ni axe ni valeur : Entrée ne le prend que s'il désigne UNE seule proposition de la
  liste, et répond sinon par un message. Le profil d'un personnage se saisit sous la même
  forme — `registre : familier` —, avec la même phrase sous son champ ;
- les **tags** — vocabulaire libre, cumulatif, avec autocomplétion ;
- une **note** en texte libre.

Les personnages sont des entités de corpus : le même personnage traverse les albums, et peut
être **aligné** sur un référentiel externe (Wikidata, VIAF, IdRef) depuis son panneau.

Tout est sauvegardé automatiquement, une demi-seconde après la dernière frappe. **`Ctrl+Z`
annule la dernière action d'annotation** — y compris une suppression de région, recréée avec
tout ce qu'elle contenait et ses identifiants d'origine. Les actes des moteurs, eux, ne
s'annulent pas. Sous un compte déclaré partagé, Ctrl+Z ne remonte que les cinq dernières
minutes : au-delà, l'acte peut être celui d'un collègue qui tapait sous le même nom. **Et
même dans ces cinq minutes**, l'application ne distingue pas deux personnes connectées sous
le même nom : Ctrl+Z peut défaire le geste d'un collègue, dont l'écran continue de le
montrer comme fait (mesuré le 2026-09-16). Sur un compte partagé, ne comptez pas sur Ctrl+Z
pour ne défaire que vos propres gestes.

**À plusieurs sur la même bulle, rien ne s'écrase en silence.** Si quelqu'un d'autre a modifié
la note ou le texte d'une bulle depuis que vous l'avez ouverte, votre enregistrement est
refusé et un **bandeau** s'ouvre au-dessus du champ : il dit qui a modifié et quand, montre sa
version, et garde la vôtre dans le champ. **Remplacer par la mienne** enregistre votre version
à la place de la sienne ; **Garder l'autre** reprend sa version et abandonne la vôtre. Tant
que vous n'avez pas choisi, vous ne pouvez pas changer de bulle ni de mode — les tags, eux,
continuent de s'enregistrer. Si vous changez de bulle, de mode ou de planche juste après avoir
tapé, l'Atelier attend d'abord que votre saisie soit enregistrée : l'indicateur dit
« Enregistrement en cours… », puis le geste se fait de lui-même, ou le bandeau s'ouvre si
quelqu'un a modifié entre-temps. Si le serveur ne répond pas en quelques secondes, un message
le dit, votre saisie reste dans le champ, et refaire le geste part sans attendre. Quand le
bandeau dit « depuis un autre écran de ce même compte », c'est vous dans un autre onglet, ou un collègue sous le même compte partagé. Si c'est la position d'une
région qui a changé ailleurs, elle se recharge simplement ; si la région a été supprimée, un
message dit par qui, et elle disparaît de votre écran. Ctrl+Z refuse de même de défaire un
geste que quelqu'un a modifié après vous.

Sur le choix « tag ou dimension ? », voir [`modele-et-droits.md`](modele-et-droits.md) §4 :
un tag se cherche, un attribut se compte.

### Étape 7 — Chercher et explorer
**Recherche (`/recherche`), puis Exploration (`/exploration`)**

La **Recherche** interroge en plein texte les dialogues, les notes et les tags — et les lemmes
si l'analyse linguistique est active, auquel cas « otage » trouve « otages ». Les accents sont
ignorés. Filtres par album, type de région et tags, nuage de tags, export CSV des résultats.
Chaque résultat montre un extrait surligné et une vignette, et **rouvre l'Atelier
exactement sur la région**.

L'**Exploration** mesure au lieu de retrouver, en quatre vues :

| Vue | Ce qu'elle répond |
|---|---|
| **Distribution** | quels lemmes, catégories ou traits morphologiques, et à quelle fréquence |
| **Concordance (KWIC)** | où exactement, avec le contexte de chaque occurrence, ses tags (ceux de la case compris, marqués « case ») et sa note — et un lien vers l'Atelier. Un lemme terminé par `*` cherche par préfixe : `otage*` trouve « otage » et « otages » |
| **Croisement (2D)** | une facette contre une autre, en tableau de contingence avec carte de chaleur ; une cellule s'ouvre en concordance |
| **Comparaison A / B** | ce qui est sur-représenté dans un sous-corpus par rapport à un autre. « Classer par » choisit la mesure : l'écart de fréquence relative, ou la **keyness** (log-vraisemblance), qui fait remonter un mot rare mais propre à un côté plutôt qu'un mot fréquent partout. L'export trie comme l'écran |

L'état de la page est dans l'URL : une vue se partage par simple copier-coller du lien.

Trois panneaux complètent la surface : **📖 Lexique** (documenter le vocabulaire),
**🎯 Accord** (part des corrections que le modèle linguistique retrouvait déjà seul) et
**👥 Inter** (accord entre annotateurs, quand un relecteur retouche le travail d'un autre).
Ce dernier est le seul rapport **réservé** : il faut écrire quelque part pour le consulter,
parce qu'il mesure des personnes et non un corpus.

### Étape 8 — Exporter
**Atelier · menu `⇅ Import / Export`**

Trois formats, par album : **JSON-LD**, **CSV** et **TEI P5**. Une **sauvegarde** complète de
la base est également téléchargeable depuis ce menu — réservée aux administrateurs.

**Exporter demande un droit à part**, que le propriétaire d'une collection accorde à
chaque accès : lire ou annoter un album n'y suffit pas (cf.
[`modele-et-droits.md`](modele-et-droits.md)). Il vaut pour tout ce qui sort : l'album,
les figures, les CSV de la Recherche et de l'Exploration, les exports de dépôt. Sans lui,
l'export est refusé en le disant. Un album rangé dans plusieurs collections sort au titre
de l'une d'elles, et l'export dit laquelle ; l'Atelier vous demande laquelle dès que vous
pouvez l'exporter au titre de plusieurs — à tout le monde, administrateur et mono-poste
compris.

**Le fichier ne porte que le vocabulaire de cette collection, plus le vocabulaire global :
l'Atelier peut en montrer davantage.** Un tag propre à une *autre* collection, que vous
voyez sur une région parce que vous lisez aussi cette autre collection, ne figure pas dans
l'export — la région sort, avec sa note et ses autres tags, sans celui-là. C'est vrai pour
tout le monde, propriétaire et administrateur compris : deux personnes qui exportent le même
album au titre de la même collection obtiennent le même fichier (depuis le 2026-10-07).

Pour citer une image dans un article, utilisez plutôt le bouton **`＋ Figure`** du panneau de
région : il constitue un lot de figures, exporté en archive avec, pour chacune, le crop, sa
légende (référence de citation, responsabilité, édition, licence) et sa notice.

Les exports de **dépôt** — fiche de description, enregistrements, manifestes IIIF — se
prennent ailleurs, parce qu'ils portent sur une **collection** et non sur un album :
*Bibliothèque*, dans la fiche de la collection, onglet *Diffusion et dépôt* (§4). Les **notices**
Dublin Core / DataCite et la **provenance** restent, elles, en ligne de commande (§5).

---

## 4. Les surfaces en détail

### Bibliothèque (`/corpus`)

L'inventaire et le poste de commande, en **une liste et une fiche** côte à côte.

- **La liste, à gauche.** En tête, le bloc *Collections* : les collections du projet que
  vous lisez, la collection de base d'abord, puis par nom ou *Récentes d'abord*. **La case**
  d'une collection **filtre** les albums sur les siens — c'est un calque posé sur le corpus :
  une collection cochée ouvre sa fiche sur ses albums, deux cochées ouvrent leur
  **comparaison** (albums, planches, validées, et ce qu'elles ont en commun), et *Dans l'une* /
  *Dans toutes* choisit l'union ou l'intersection ; *Tout ce que vous lisez* défait le calque.
  **Le nom** d'une collection **ouvre sa fiche**, sans rien filtrer. Dessous, les albums du
  projet — ceux que vous lisez —, chacun nommant ses collections, et un champ pour chercher
  par titre, série ou auteur. *+ Créer une collection* ouvre son champ au geste. Le compte
  ne dit le total du projet qu'à un administrateur : pour les autres, c'est *… albums que
  vous lisez*. Sous une largeur de téléphone, la liste et la fiche se montrent l'une après
  l'autre, et *← Liste* ramène à la liste.
- **La fiche d'une collection** dit vos droits **en actes** — *lire*, *annoter et
  organiser*, *exporter*, *décider qui entre*, chacun coché ou barré — et a **quatre
  onglets** : *Albums* (ses albums, et dans quelles autres collections ils sont aussi
  rangés), *Qui entre*, *Description* (lue d'abord ; *Modifier* ouvre le formulaire) et
  *Diffusion et dépôt* (le régime, puis les exports et ShareDocs). Tous s'ouvrent à tous :
  ce que vous ne pouvez pas faire, le bloc concerné le dit — *Exporter : droit manquant*.
  *Supprimer la collection…* est à part, en bas de *Description*. L'adresse de la page dit
  la fiche et l'onglet ouverts : un lien les rouvre.
- **La fiche d'un album** s'ouvre à la place de celle de la collection, avec *← la
  collection* pour y revenir ; elle dit où l'album est **rangé**, et ce que vous pouvez y
  faire vaut pour l'album entier : il suffit d'écrire dans **une** de ses collections, quelle
  que soit celle par laquelle vous l'avez ouvert.

- **Le projet, en haut de la page.** La bande du haut porte le mot *Projet* et le nom de
  celui où vous travaillez ; si vous en voyez plusieurs, c'est une liste déroulante, et
  vous y **choisissez**. Le choix est retenu par votre navigateur : il vous suit d'une page
  à l'autre et d'un onglet à l'autre, pas d'un poste à l'autre, et un lien que vous envoyez
  ne le porte pas. **Dans la Bibliothèque, il borne la liste des collections** : une ligne
  au-dessus du bloc *📚 Collections* dit *Dans le projet « … »*, la liste est celle de ce
  projet, et *+ Créer* y crée. Ouvrir un lien vers une collection d'un autre projet vous y
  fait basculer. Un projet où rien ne vous est ouvert le dit — *Aucune collection ouverte
  pour vous dans le projet « … »* —, ce qui n'est pas avoir tout perdu : changez de projet.
  **La liste des albums le suit aussi**, et donc les lots ; la Recherche et l'Exploration
  affichent son nom et portent toujours sur tout ce que vous lisez. Deux listes de cette
  page suivent le projet, chacune le sien. *Collection*, dans *+ Nouvel
  album*, ne propose que les collections du projet **courant** où vous écrivez, et le dit
  dès qu'elle en écarte une : *Seules les collections du projet « … » sont proposées : pour
  créer l'album dans un autre projet, choisissez-le en haut de la page.* Si vous n'écrivez
  dans aucune collection de ce projet, il n'y a pas de liste vide mais une phrase — *Vous
  n'écrivez dans aucune collection du projet « … » : l'album ne peut pas y être créé.
  Créez-y d'abord une collection, ou choisissez un autre projet en haut de la page.* —, et
  *Enregistrer* n'enregistre rien. *Sur les collections*, dans la fiche d'un album, ne
  propose que les collections du projet où **l'album** vit déjà, qui n'est pas forcément le
  projet courant : *Cet album vit dans le projet « … » : seules les collections de ce projet
  sont proposées, un album ne se rangeant pas d'un projet à l'autre.* Ce qu'est un projet,
  et ce qu'il n'ouvre pas : [`modele-et-droits.md`](modele-et-droits.md) §2.
- **Albums** : créer (*+ Nouvel album*, en haut de la page), éditer les métadonnées (*✎
  Modifier l'album*, dans sa fiche), supprimer (ci-dessous). La fiche porte la description,
  les contributions, les champs d'édition, la source de numérisation et *Sur les
  collections* : une case par collection du projet de l'album que vous lisez, cochée là où
  il est rangé. Seules les cases des collections où vous **écrivez** s'offrent ; les autres
  se lisent, éteintes. **Cocher, c'est rejoindre** le travail de l'album depuis cette
  collection : c'est fait tout de suite si vous possédez chacune des collections où il vit
  (*Fait : « … » est aussi rangé dans « … ». Le travail est partagé.*) ; sinon la demande part
  à leur propriétaire — ou à un administrateur quand aucun propriétaire ne les tient toutes —,
  la phrase le dit (*Pas rangé : … La demande est partie.*), et la case reste **indéterminée**,
  marquée *demandé*, jusqu'à la réponse. **Décocher, c'est supprimer de la collection**
  (ci-dessous).
- **Supprimer un album : deux réponses.** Dans la fiche d'un album où vous **écrivez** — et
  sur sa ligne, dans l'onglet *Albums* d'une collection —, le bouton *Supprimer…* ouvre un
  panneau qui propose deux gestes, et dit pour chacun ce qui arrivera avant que vous le
  choisissiez — le panneau est la confirmation. *Annuler* le referme sans rien faire. Si
  vous ne faites que **lire** un album, il n'a pas de bouton *Supprimer…*.
  - **Supprimer de la collection** ne détruit rien. Il y a un bouton par collection de
    l'album où vous écrivez, *Supprimer de « … »*, et le texte au-dessus dit ce que devient
    le travail : il **reste** dans les autres collections que vous lisez, nommées ; ou il
    reste dans *une collection que vous ne lisez pas*, sans la nommer ; ou c'était la
    **dernière** collection de l'album, et *la copie de travail est gardée au fonds, avec
    tout son travail* — un administrateur peut la rendre (§4, *Administration*). Le texte
    dit aussi ce que **vous** y perdez : si c'était la seule collection par laquelle vous y
    écriviez, vous continuerez de le lire mais n'y écrirez plus, ou vous ne le verrez plus
    du tout — et vous ne pourrez pas l'y ranger de nouveau vous-même. **Même si vous gardez
    la vue et l'écriture**, le ranger de nouveau, c'est le **rejoindre** : vous ne le
    referez seul que si vous possédez chacune des collections où il reste ; sinon le texte
    le dit — *Vous ne pourrez l'y ranger de nouveau que sur demande, à son propriétaire ou à
    un administrateur.* — et le geste se fait confirmer. Le geste ne s'annule pas autrement,
    et un administrateur rend une copie gardée au fonds. Décocher une collection, sous *Sur
    les collections* dans la fiche de l'album, fait le même geste, avec les mêmes mots, et
    le fait confirmer quand il coûte ; la case ne s'offre que sur les collections où vous
    écrivez.
  - **Supprimer définitivement** efface les images et tout le travail fait dessus, pour
    tout le monde, dans tous les projets. Il efface **tout de suite** si vous avez créé
    cette copie vous-même — importée, ou prise du fonds — et que personne d'autre n'y a
    travaillé : c'est l'erreur, qui n'a à attendre personne ; le panneau le dit (*… vous
    l'avez créée, et personne d'autre n'y a travaillé. Irréversible.*) et le bouton
    s'appelle *Supprimer définitivement*. **Sinon, il se demande à un administrateur** : le
    panneau dit *D'autres s'en servent, ou ce n'est pas vous qui avez créé cette copie : la
    demande part à un administrateur, qui décide. Rien n'est effacé d'ici là.* Remplissez *Pourquoi ce
    document n'a pas sa place ici*, lisez ce que la suppression détruirait, cochez *Je
    certifie que ces données ne sont pas importantes.*, puis *Envoyer la demande*. Sans
    motif ou sans la case, rien ne part, et le panneau le dit. Ce qui compte comme « avoir
    travaillé », et pourquoi un album créé avant l'arrivée du fonds se demande toujours :
    [`modele-et-droits.md`](modele-et-droits.md) §2, *Le fonds*.
  - **Une demande en attente se voit sur l'album**, dans la liste et dans sa fiche : *suppression demandée par
    vous*, ou *suppression demandée* sans nom — seuls un administrateur et la personne qui a
    demandé lisent qui l'a fait. Tant qu'elle attend, *Supprimer définitivement* le dit,
    sans bouton, et rien n'est effacé. L'administrateur répond *Détruire* — l'album disparaît
    pour tous — ou *Garder* : la pastille disparaît, et l'on peut demander de nouveau.
  - **Une copie qui a une sœur** — le même document, pris ailleurs en copie vierge — se
    supprime seule : le panneau ajoute *Ses images restent : une autre copie de ce document
    les emploie.*, sans dire où vit l'autre copie.
- **Prendre un document** (tranche 3a). Deux gestes, au-dessus du tableau de l'onglet
  *Albums* d'une collection, et le premier aussi en tête de la fiche du projet :
  - **+ Prendre du fonds…** n'est offert qu'au **responsable** du projet et à un
    administrateur. Il ouvre la liste des **notices** du fonds — titre, série, auteur, et rien
    d'autre —, cherchées au serveur, 25 par page. Cochez un ou plusieurs documents, choisissez
    *Dans* quelle collection ils arrivent — la base est en tête, et présélectionnée en tête du
    corpus ; dans une collection, c'est elle —, écrivez *Pourquoi ces documents ?* et
    *Demander* : une seule demande part à un administrateur, et chaque document dit sa
    réponse sur sa ligne — *fait* quand le projet a déjà une copie que vous lisez (une copie
    vierge entre tout de suite), *demandé à un administrateur* sinon, ou *refusé* et pourquoi.
    *Déjà dans ce projet* signale un document qu'une collection du projet a déjà, sans dire
    laquelle ; il reste cochable, pour une seconde copie. *Une copie de ce projet est gardée
    au fonds — la demander à rendre ↗* signale qu'une copie du projet, avec son travail, a
    quitté sa dernière collection, et mène à la fiche du projet, dans l'Administration, où
    l'on demande à la rendre. Le motif est obligatoire. Un administrateur *Prend* : tout
    entre tout de suite, sans motif.
  - **+ Prendre dans le projet…** est offert à qui **écrit** dans la collection : les albums du
    projet que vous lisez et qui n'y sont pas encore. Sur chaque ligne, *Rejoindre* — le même
    travail, partagé avec ses collections : immédiat si vous les possédez toutes, sinon
    *demandé à son propriétaire* (ou *à un administrateur*) — ou *Copie vierge* — une seconde
    copie, images seules, sans le travail de l'autre, à votre nom, tout de suite. L'infobulle
    de chaque bouton le redit, et la réponse s'écrit à la place des boutons. Un album dont
    le rejoindre vers cette collection attend déjà dit *rejoindre demandé* au lieu du bouton.
- **Les demandes de rejoindre que vous recevez**, comme propriétaire d'une collection : une
  marque **⚑ n** sur la collection, dans le bloc *Collections* ; dans la bande d'outils, *n
  demandes à répondre*, qui mène à la première ; et en tête de l'onglet *Albums*, dont
  l'onglet porte une pastille, un bloc ⚑ qui dit qui demande que quel album soit aussi rangé
  dans quelle collection — *Accepter* (le travail est partagé) ou *Refuser* (l'album reste où
  il est, et la demande peut être redéposée). Rien n'apparaît dans la bande du haut. Un
  administrateur les lit dans *À faire*, en recours. **Responsable**, vos demandes au fonds
  qui attendent se rappellent dans la bande d'outils — *n demandes au fonds, en attente* —, et
  mènent à la fiche du projet, dans l'Administration, où se lit leur état.
- **Supprimer une planche** suit la règle de l'album, sans demande à elle : sa corbeille 🗑
  est active là où vous supprimeriez l'album définitivement sans rien demander. Ailleurs,
  si vous écrivez dans l'album, elle est **grisée** et, quand on la touche, dit sous elle :
  *Cette planche ne se supprime pas d'ici : vous n'avez pas importé l'album, ou d'autres y
  ont travaillé. Adressez-vous à un administrateur de l'instance.* À qui ne fait que lire,
  pas de corbeille.
- **Planches** : ouvrir, supprimer, et trois marques indépendantes —
  **rôle** (`récit`, numéroté, ou `paratexte` : couverture, liminaire, publicité, écarté de la
  numérotation), **validation** et **verrou** (🔒 protège des passes automatiques). Les gestes
  d'une planche (rôle, verrou, ↗ ouvrir dans l'Atelier, 🗑) suivent son nom. **Valider** est
  un seul bouton qui porte son état : ✔ gris tant que la planche ne l'est pas, ✔ vert enfoncé
  quand elle l'est, le même clic dans les deux sens. *✔ Tout valider* valide d'un seul geste
  toutes les planches qui ne le sont pas : tout passe, ou rien — un échec ne laisse pas
  l'album à moitié validé, et le message le dit.
- **Importer des planches en lot** : *⤓ Importer des planches…*, dans la fiche d'un album où
  vous écrivez. Autant de fichiers qu'on veut, envoyés un par un dans l'ordre de leurs noms ;
  la ligne à côté du bouton dit *n sur N* et le fichier en cours, puis le bilan, et nomme
  chaque fichier refusé. Cf. étape 1.
- **Relecture** : une pastille par planche, et un filtre pour n'afficher que les planches à
  faire, en cours ou faites.
- **Traitements par lot** : cocher des albums (onglet *Albums* d'une collection) ou des
  planches (fiche d'un album) ; le lot paraît au-dessus de la sélection — cochez les passes,
  lancez. Progression, annulation et erreurs en direct, au-dessus de la liste.
- **Collections** : créer une collection (*+ Créer une collection*) — elle naît dans le projet choisi en haut de la
  page ; il suffit d'être connecté dans le projet de repli, et d'être membre du projet
  dans un autre ; l'on en devient
  propriétaire, sauf un administrateur, qui l'administre sans la posséder et peut lui
  désigner un propriétaire dans *Qui entre* —, la décrire (description, dates), régler
  sa diffusion (régime, embargo, licence, base légale), désigner son référent, la renommer,
  la supprimer, et l'exporter pour un dépôt (ci-dessous) — chaque chose dans son onglet de
  la fiche. Seuls un propriétaire et un
  administrateur modifient ; un participant lit la description et sait à qui écrire. La date d'embargo **retient** : tant qu'elle court, les
  scans ne sortent pas, même d'une collection « public » — et elle ne publie jamais rien
  d'elle-même.
- **Qui entre** : l'onglet de la fiche d'une collection — celui qu'ouvre son nom —, qui entre dans cette collection et ce
  qu'il peut y faire. Les accès s'y règlent en **actes** — *lire*, *annoter*, *décider qui
  entre* — plutôt qu'en niveaux à deviner : *Faire entrer* admet en lecture, puis on coche.
  On désigne un **compte** ou un **groupe**, la question étant posée explicitement parce
  qu'un login et un groupe peuvent porter le même nom ; le nom tapé est confronté à
  l'annuaire et marqué **inconnu de l'annuaire** s'il n'y existe pas, **non vérifié** si
  l'annuaire n'a pas répondu — la marque avertit, elle ne bloque pas. **Exporter est un acte
  à part**, en dehors de ces trois : sortir le contenu en fichier ne découle pas du droit
  d'annoter, un propriétaire l'accorde accès par accès, et il l'a lui-même d'office. Le bloc
  déclare aussi quels groupes d'administration lisent et écrivent tout le corpus sans figurer
  dans aucune liste d'accès. Seul un propriétaire, ou un administrateur, y règle quelque
  chose ; les autres lisent. Pour la **collection de base** d'un projet, la liste a deux
  groupes : *Par le projet* — ses responsables, propriétaires, et ses membres selon ce que
  le projet a choisi —, sans case ni ✕, avec *Régler dans le projet ↗* ; puis *Entrés ici*,
  ceux qu'on y fait entrer à la main.
  **Le même panneau se trouve à un second endroit**, pour un second public : un
  administrateur, qui part d'une personne ou d'un groupe plutôt que d'un corpus, le retrouve
  dans l'Administration, dans la fiche de chaque collection de *👥 Comptes et groupes*
  (ci-dessous). On y fait les mêmes gestes, et ce qu'on règle d'un côté se lit de l'autre.
  Un propriétaire n'a rien à y chercher : tout ce qu'il règle est ici.

#### Exporter une collection pour un dépôt

Dans la **Bibliothèque**, ouvrez la fiche d'une collection, onglet **Diffusion et dépôt** :
le bloc **Export de dépôt** produit, sans passer par la ligne de commande, les trois artefacts qu'un entrepôt
attend.

| Ce que vous obtenez | À quoi ça sert | Formats |
|---|---|---|
| **Fiche de description** | *quels champs employez-vous, et avec quelle couverture ?* | JSON, CSV |
| **Enregistrements** | les métadonnées elles-mêmes, entité par entité | JSON, CSV (zip), XLSX |
| **Manifeste IIIF** | ce qu'on dépose chez Nakala : les Canvas, et les images si le régime le permet | archive |

Ce qu'il faut savoir avant de cliquer.

- **Il faut le droit d'exporter CETTE collection.** Son propriétaire l'accorde accès par
  accès ; la lire n'y suffit pas.
- **L'export porte sur CETTE collection**, jamais sur le corpus entier — c'est ce qui rend
  la fiche citable, et ce qui garantit que rien d'un autre corpus ne s'y glisse.
- **Le manifeste IIIF ne contient pas les images : il pointe vers elles.** Le champ
  d'adresse n'attend donc pas un « serveur IIIF » — de simples JPEG suffisent — mais
  l'adresse publique sous laquelle le dossier `derivatives/` sera servi : un partage
  ShareDocs, ou ce que rend l'entrepôt. L'application ne peut pas la deviner : elle sert
  bien vos images, mais seulement à ceux qu'elle a admis, et se désigner elle-même
  produirait un manifeste introuvable chez le destinataire.
- **Laissez le champ vide tant que les images ne sont publiées nulle part** — le cas
  ordinaire avant un premier dépôt. Le manifeste sort alors en **aperçu** : on peut le
  regarder, il ne se dépose pas, et son nom de fichier le dit (`depot-iiif-apercu-…`).
- **Un manifeste sans images n'est pas un échec.** C'est la forme habituelle d'un dépôt,
  qui porte les Canvas et l'enrichissement. L'archive contient alors un fichier
  `AVERTISSEMENTS.txt` qui dit *pourquoi* les scans sont retenus — collection non déclarée
  publique, embargo en cours, date illisible — et les trois ne se corrigent pas de la même
  façon.

Un **propriétaire** de la collection peut en plus **déposer** l'artefact sur ShareDocs
plutôt que de le télécharger. Ce droit-là est plus étroit que le téléchargement, et c'est
volontaire : emporter un fichier pour soi n'est pas l'écrire dans un dossier partagé dont
l'application ne contrôle pas l'audience.

### Administration (`/administration`)

Ce qui porte sur l'instance : quelle version tourne ici, à qui s'adresser quand on est
bloqué, quels projets existent et qui y entre, ce que l'instance détient, quels comptes et
quels groupes existent, et si les moteurs répondent encore. Six blocs, chacun avec sa propre
règle d'accès (cf. §2).

- **🏷️ Version servie** : le commit que cette instance fait tourner. N'apparaît que si le
  serveur vous le sert — c'est réservé aux administrateurs, parce que le dépôt est public
  et qu'un numéro de version y dit quels correctifs sont en place. L'application ne connaît
  que ce bout-là : elle affiche le commit servi et vous laisse le comparer à `origin/main`,
  plutôt que d'affirmer « à jour » sans avoir vu la référence.
- **📇 Référent de l'instance** : à qui s'adresser quand on n'a accès à rien — l'adresse
  que donne le bandeau de portée vide. Réservé aux administrateurs, et en lecture seule :
  elle se règle dans l'environnement du serveur, pas ici.
- **🗂️ Projets** : les projets que vous **réglez**, en liste, et la fiche de celui que vous
  choisissez. Le bloc s'affiche pour le responsable d'un projet, pour les administrateurs,
  et en mono-poste. Un simple membre lit à sa place une phrase qui le lui dit — *Les projets
  se règlent par leur responsable. Vous êtes membre du projet « … » : vous n'y réglez
  rien.* — et qui ne voit aucun projet ne lit rien ici.
  - **Créer un projet** (administrateurs) : un nom dans *Nouveau projet*, puis *+ Créer le
    projet*. Le nom est court — le plafond est annoncé sous le champ, parce qu'il se lit
    en haut de chaque page, où il ne se coupe pas. *Pourquoi ce projet existe* reçoit sa
    justification, scientifique d'abord. *Ce que sa collection de base ouvre aux membres*
    pose une question, trois réponses — *ouverte* (présélectionnée : les membres y
    annotent), *en lecture*, *protégée* (ses responsables seuls) —, une phrase sous
    chacune. Le projet naît sans membre ni responsable, avec sa **collection de base**, de
    son nom ; le message vous donne la suite : y faire entrer quelqu'un dans sa fiche.
  - **La fiche** : le nom, le nombre de collections que vous y lisez, la mention *projet
    de repli* s'il l'est ; puis *Pourquoi ce projet existe*, *Qui y entre*, *Collections*
    — celles que vous lisez, la base marquée *base*, chacune menant à sa fiche dans la
    Bibliothèque —, *Ce que la base ouvre aux membres*, *Au fonds* et *Ce projet*.
  - **Ce que la base ouvre aux membres** : les trois réponses de la création. En cocher une
    autre n'applique rien : une phrase dit d'abord ce que le changement fait — *Resserrer
    n'efface aucun travail…*, ou *Ouvrir donne à 3 entrées du projet le droit…* —, puis
    *Appliquer : base …* (ou *Annuler*). La base n'ouvre qu'elle-même.
  - **Au fonds** : *Au fonds · n demandes* — les documents demandés pour le projet et leur
    état (*en attente*, *acceptée*, *refusée*, *acceptée en partie* ; *Détail* les dit
    document par document) ; puis *Copies gardées au fonds · n*, les copies du projet
    retirées de leur dernière collection. *Demander à la rendre…* ouvre le choix d'une
    collection du projet où vous écrivez — la base d'abord —, puis *Demander* : un
    administrateur répondra *Rendre* ou *Garder au fonds*, et la ligne dit *retour demandé
    le …* d'ici là. Un administrateur, lui, lit *Rendre à…* et rend tout de suite.
  - **Qui y entre** : dans *Faire entrer*, choisissez un groupe sous *Groupes de
    l'annuaire*, ou *Un compte, ou un groupe absent de la liste…* — il faut alors taper son
    *nom exact* et répondre à *Compte ou groupe ?*, sans valeur par défaut : un groupe
    entré comme compte ne ferait entrer personne. Puis *+ Faire entrer*. **On entre
    toujours *membre*** ; pour nommer un responsable, changez le rôle sur sa ligne (*membre*
    / *responsable du projet*). Le ✕ de la ligne fait sortir. Les marques sont celles de
    *Qui entre* : *inconnu de l'annuaire*, *non vérifié*, *n'a pas encore ouvert
    l'application* — elles avertissent, elles ne bloquent pas. Et la partie le rappelle à
    chaque fois : *Entrer dans le projet n'ouvre que sa collection de base, selon ce que le
    projet a choisi : chaque autre collection garde son « Qui entre ».*
  - **Ce projet** (administrateurs) : *Renommer* ; deux champs, *Description* et *Pourquoi
    ce projet existe*, avec leur bouton *Enregistrer* — seul ce que vous avez changé est
    enregistré, un champ vidé efface son texte, et la fiche répond *Description
    enregistrée.*, *Justification enregistrée.*, *Description et justification
    enregistrées.* ou *Rien n'a changé.* ; et *Supprimer le projet* — après confirmation.
    Chaque réponse se lit à côté du bouton qu'on vient d'actionner.
    Un responsable n'y reçoit aucun champ, et y lit à la place : *Vous réglez qui entre dans
    ce projet. Le renommer, corriger sa description ou sa justification, ou le supprimer se
    demande à un administrateur de l'instance.* Sous cette phrase, **il a le geste de le
    demander** : *Demander sa suppression…* ouvre un champ, *Pourquoi le supprimer* — sans
    motif, rien ne part —, puis *Envoyer la demande* (*Annuler* referme le champ). La fiche
    dit ensuite *suppression demandée le …*, et la demande se lit dans le fonds, où un
    administrateur y répond. Le projet de repli n'offre pas ce geste.
  - **Quatre refus, qui se disent.** Le *dernier responsable* d'un projet ne se retire pas
    et ne se rétrograde pas : désignez-en un autre d'abord. Le *projet de repli* se
    renomme, il ne se supprime pas — le bouton n'y est pas offert. *Un projet ne se
    supprime que vide* : tant qu'une autre collection que sa base lui appartient, c'est
    refusé, en disant combien, et sa base doit être sans album ni vocabulaire propre — vide,
    elle part avec lui, et la confirmation le dit. Et tant que des albums de ce projet sont **gardés au fonds**, aussi : il faut
    d'abord les détruire depuis le fonds.

  Cf. [`modele-et-droits.md`](modele-et-droits.md) §2 et §3.
- **🗄️ Le fonds** : ce que l'instance détient — tous les albums, y compris ceux qu'aucune
  collection n'appelle plus. Réservé aux administrateurs, et ouvert en mono-poste : pour
  tout autre compte, le bloc n'apparaît pas. Une ligne de compte, en tête, dit combien de
  documents, combien sont *appelés par personne*, combien de suppressions sont demandées.
  - **Suppressions demandées**, en tête quand il y en a : qui demande la suppression de quoi,
    quand, depuis quel projet, si la même a *déjà été refusée*, le motif, et la
    certification (*Certifié par … le … : ces données ne sont pas importantes.*). Sous la
    demande d'un album : qui l'a importé — ou *Qui l'a importé n'est pas écrit (un album
    d'avant le fonds)* —, puis ce que d'**autres** que le demandeur y ont fait, une ligne
    par personne (*Nom (login) : 3 annotations, 1 locuteur — dernier le …*), ou *Personne
    d'autre que le demandeur n'y a laissé de geste.* Ce sont des gestes lus dans le journal
    — un geste défait depuis compte encore —, pas ce qui reste sur les planches ; et sous un
    compte partagé, la ligne rappelle que plusieurs personnes ont pu travailler sous ce
    login. **Détruire** efface l'album pour tous, après une confirmation qui dit ce qui
    part ; **Garder** clôt la demande sans rien effacer. Une demande de suppression de
    projet se répond de même, par *Supprimer le projet* ou *Garder* ; si le projet n'est
    pas vide, le refus le dit et la demande reste en attente.
  - **Les autres demandes**, dans *À faire* avec elles, chacune nommée en tête de sa ligne
    et marquée de sa couleur : une **entrée de documents** (un responsable demande des
    documents du fonds pour une collection de son projet) se répond document par document
    — *Accepter*, *Refuser* —, ou d'un coup, *Tout accepter (n)* et *Refuser le reste* ;
    chaque document accepté entre en copie vierge, au nom du demandeur. Un **rejoindre** (un
    écrivain demande à ranger aussi une copie dans sa collection) : *Accepter : ranger aussi
    dans « … »* ou *Refuser* — c'est d'abord au propriétaire de répondre, l'administrateur
    est le recours. Un **retour** (le responsable demande à rendre une copie gardée) :
    *Rendre à « … »* ou *Garder au fonds*. Aucune de ces trois-là ne se répond par
    *Détruire*.
  - **Importer au fonds** : un titre, des fichiers, puis *+ Importer au fonds*. L'album
    naît **appelé par personne**, sans collection ni projet, et ses planches entrent une à
    une ; le message dit combien sont entrées et lesquelles ont été refusées. C'est le
    moyen de charger un corpus avant de le distribuer.
  - **Documents** : pour chaque album, d'où il vient (*Importé par … le …, dans « … »*, ou
    ce qui n'est pas écrit), où il est employé (*Employé par Projet : collections*), la
    marque *appelé par personne* s'il n'est rangé nulle part, et la demande qui l'attend.
    *Copies de travail · n* liste ses copies — une par projet qui l'a pris, parfois deux :
    leur projet et leurs collections, qui a créé chacune, *copie vierge, images partagées*,
    et *notice divergente* quand une copie dit un autre titre que la première. Le filtre
    *Plusieurs copies* les retrouve. *Prendre dans…* : choisissez une collection — groupées
    par projet, la base de chacun en tête —, puis *Prendre* ; une copie vierge y entre, à
    votre nom, les images du document avec elle.
    Une **copie gardée** — supprimée de sa dernière collection, ou importée au fonds — se
    **rend** : choisissez une collection, puis *Rendre* ; elle y revient avec tout son
    travail. Seules les collections de **son** projet sont proposées (une copie importée au
    fonds, qui n'en a pas encore, peut aller partout, et prend le projet de cette
    collection). Un album que personne n'appelle se **détruit** par *Détruire*, après
    confirmation.
  - **« À regarder »**, dans *👥 Comptes et groupes*, porte aussi les demandes en attente,
    en tête ; un clic y mène à la demande, dans le fonds.
- **👥 Comptes et groupes** : réservé aux administrateurs, parce qu'il porte sur des
  personnes et non sur le corpus. Il réunit trois sources qui ne se recouvrent pas — ce que
  l'**annuaire** rend (les comptes et les groupes qui EXISTENT, venus ou non), ce que
  l'application a **vu**, et ce qu'elle a **accordé** — sur trois axes : *Comptes*,
  *Groupes*, *Collections*. En tête, **⚠ À regarder** liste ce qui trompe en silence : un
  accès donné à un groupe absent de l'annuaire, une collection dont plus aucun propriétaire
  n'est vivant, un compte qui n'est jamais venu. La fiche d'un compte porte sa **Nature** —
  *une personne* ou *un login partagé* —, qui se déclare à sa première connexion.
  **Les accès se règlent ici aussi** : axe *Collections*, la fiche d'une collection porte
  *Qui entre* — le panneau de la Bibliothèque, monté ici une seconde fois, pour qui part
  d'une personne ou d'un groupe plutôt que d'un corpus. On y fait entrer (*Faire entrer*, puis *+ Faire entrer*), on coche les
  actes, on fait sortir par le ✕ de la ligne, sans quitter la page ; et chaque nom du
  tableau mène à la fiche de ce compte ou de ce groupe. Depuis la fiche d'un **groupe**,
  *Ouvrir une collection à ce groupe* puis *Régler qui entre…* ouvre la fiche de la
  collection choisie, ce groupe déjà choisi dans *Faire entrer* : il reste à cliquer
  *+ Faire entrer*. Ce que la collection **est** — sa description, sa diffusion, son
  référent, ses exports — ne se règle pas ici : *Décrire dans la Bibliothèque*, sous le
  panneau, y mène dans le même onglet (Précédent ramène). Si l'annuaire ne répond pas, le bloc s'affiche
  quand même avec ce que l'application sait seule, et le dit — il n'annonce jamais qu'un
  accès est mort sur la foi d'une lecture qui a échoué.
  Cf. [`modele-et-droits.md`](modele-et-droits.md) §3.
- **🩺 Moteurs de reconnaissance** : quels moteurs sont présents, et *Éprouver les moteurs*
  pour vérifier qu'ils démarrent réellement.

### Atelier (`/`)

Quatre modes, un sélecteur en haut, un raccourci chacun :

| Mode | Touche | Ce qu'on y fait |
|---|:---:|---|
| **Navigation** | `N` | lire : zoom molette, déplacement au cliquer-glisser, `←` `→` d'une région à l'autre |
| **Édition** | `E` | corriger la géométrie : poignées, coordonnées, dessin, `Suppr` |
| **Annotation** | `A` | locuteur, personnages, situation, tags, note |
| **Transcription** | `T` | plein écran bulle à bulle, `Tab` / `Maj+Tab` |

Les onglets sont un **sélecteur**, pas un parcours : leur ordre n'est pas celui des huit
étapes, et c'est assumé.

Le panneau de gauche liste les planches ; celui de droite dépend de la sélection. Il contient
l'**arbre de structure** (planche → cases → bulles, avec l'avancement de l'OCR par case) : un
clic sélectionne et recentre, le survol surligne dans l'image, et l'ordre de lecture se
réarrange à la main (`Alt+↑` / `Alt+↓`, ou le bouton de recalcul).

Sur écran étroit, les deux panneaux deviennent des tiroirs, ouverts par les bascules ☰ et ▤.

Autres raccourcis : **`Ctrl+Z`** annule la dernière action d'annotation ; **`Échap`** annule un
tracé en cours et désélectionne (en sauvegardant ce qui était en attente).

### Recherche (`/recherche`)

Un champ, trois filtres (album, type de région, tags), un nuage de tags cliquable, un export
CSV. La recherche porte sur les dialogues, les notes et les tags — plus les lemmes si
l'analyse linguistique est installée ; sans elle, elle retombe proprement sur la recherche par
préfixe, toujours insensible aux accents.

**Un document dont vous lisez deux copies compte deux fois** — une copie vierge prise dans le
même projet, ou deux projets que vous lisez : la Recherche porte sur tout ce que vous lisez,
et chaque copie a son texte. Ce double compte tient jusqu'à ce que la Recherche et
l'Exploration soient bornées au projet (tranche 4 de COL-3).

**Revenir par le menu reprend la dernière recherche** de l'onglet, filtres compris ; un lien
qui porte sa propre recherche — partagé, ou venu de l'Exploration — l'emporte toujours. Rien
n'est retenu d'un onglet à l'autre, ni après sa fermeture (et rien du tout en navigation
privée, où la page repart simplement vide).

Elle porte sur les tags **sans distinguer leur portée** : un mot peut faire sortir une de vos
régions parce qu'elle porte un tag local à une collection que vous ne lisez pas — le tag ne
vous est pas montré pour autant, et rien ne sort d'une région hors de votre portée. Limite
connue et mesurée, décrite dans `docs/modele-et-droits.md` § *Le vocabulaire*.

### Exploration (`/exploration`)

Les quatre vues du tableau de l'étape 7, avec des filtres communs : album, type de région,
catégorie grammaticale, **provenance** (auto / corrigé / validé), tag, locuteur. Le filtre de
provenance est celui qui permet de ne mesurer que sur ce qui a été relu par un humain.

Comme la Recherche, elle porte sur tout ce que vous lisez : **un document dont vous lisez deux
copies y compte deux fois**, jusqu'à la tranche 4 de COL-3. Et comme elle, revenue par le
menu, elle reprend la dernière vue de l'onglet et ses filtres ; un lien qui porte sa vue
l'emporte.

Le panneau **📖 Lexique** liste tout le vocabulaire — domaines, dimensions, valeurs, tags —
avec pour chacun sa définition, sa note de portée, son état et sa portée d'appartenance, plus
un « % défini » d'ensemble. Changer la portée d'un terme est refusé s'il se retrouverait
séparé de son parent ou d'un terme qui en dépend, rangé dans une autre collection : le
message dit lequel quand vous le lisez. Changer la portée d'un domaine, ou d'une dimension
sans domaine ou sous un domaine global, emporte avec lui les termes qui en dépendent et
partageaient sa collection — sauf depuis *Global*, d'où rien n'est emporté. C'est aussi de là qu'on **importe une taxonomie** depuis un tableur ;
une ligne qui nommerait un terme que vous ne lisez pas, écrirait sur un terme
en lecture seule pour vous, ou rangerait un terme hors de la collection de son parent, est
refusée, et le bilan le dit par motif
(cf. [`import-vocabulaire.md`](import-vocabulaire.md)).

---

## 5. Ce qui n'a pas (encore) de bouton

Certaines opérations vivent en ligne de commande, sur la machine qui héberge l'application.
Elles sont documentées ; elles ne sont simplement pas dans l'interface.

| Opération | Où | Documentation |
|---|---|---|
| Responsables scientifiques d'une collection (nom, rôle, ORCID) — tout le reste de sa description se règle dans la Bibliothèque | `tools/gerer_collections.py` | [`export-metadonnees.md`](export-metadonnees.md) |
| Notices Dublin Core / DataCite, provenance PROV-O / TEI | `tools/` | [`crosswalk-depot.md`](crosswalk-depot.md), [`provenance-audit.md`](provenance-audit.md) |
| Rapports d'accord (modèle↔humain, inter-annotateurs) en CSV/JSON | `tools/` | [`rapport-accord.md`](rapport-accord.md), [`accord-inter.md`](accord-inter.md) |
| Réindexer tout le corpus après un changement de modèle linguistique | `tools/reindex_nlp.py` | [`correction-grammaticale.md`](correction-grammaticale.md) |
| Relire la résolution des planches importées avant cette fonctionnalité | `tools/reindex_materiel.py` | [`materiel-numerisation.md`](materiel-numerisation.md) |
| Remplacer par des copies de travail les masters gardés avant la v34 — **efface les masters du serveur** | `tools/convertir_en_copies_de_travail.py` | [`materiel-numerisation.md`](materiel-numerisation.md), « La copie de travail » |
| Créer un compte, un groupe | l'annuaire LLDAP, par son interface web (le fichier des comptes du portail n'est plus que le repli) | [`exploitation.md`](exploitation.md), « Basculer vers l'annuaire LLDAP » |

L'**import PDF** est annoncé dans le menu mais désactivé : il n'est pas encore implémenté.

---

## 6. Quand ça ne marche pas

**Je ne vois aucun album.**
Lisez le bandeau en haut de page, et **dépliez-le** : il distingue une panne de configuration
d'un simple manque d'accès, et nomme la personne à qui écrire quand l'instance en a déclaré
une. Cf. [`modele-et-droits.md`](modele-et-droits.md) §3, et §7 pour la question complète.

**Une collection que je lisais n'est plus dans la Bibliothèque.**
Elle est probablement d'un autre **projet** que celui choisi en haut de la page : la liste
des collections suit le projet. Changez-le dans la liste déroulante *Projet* — la ligne
*Dans le projet « … »*, au-dessus des collections, dit lequel est affiché. Rien ne vous a
été retiré : la Recherche et l'Exploration, qui ne suivent pas le projet, la lisent encore.

**J'ai supprimé un album de ma collection : il a disparu de la Bibliothèque.**
C'est attendu si c'était la seule collection par laquelle vous le lisiez. S'il n'était rangé
nulle part ailleurs, il est **gardé au fonds** avec tout son travail : rien n'est perdu, et
un administrateur peut le rendre à une collection du même projet. Écrivez-lui en lui
donnant le titre.

**« Supprimer définitivement » envoie une demande au lieu d'effacer.**
L'album n'est effacé tout de suite que si vous avez créé cette copie vous-même — importée, ou
prise du fonds —, que personne d'autre n'y a travaillé, et que vous écrivez dans toutes ses
collections. Un album créé avant
l'arrivée du fonds n'a pas d'importateur écrit : sa suppression se demande toujours. Sous un
compte partagé aussi. Cf. [`modele-et-droits.md`](modele-et-droits.md) §2, *Le fonds*.

**La corbeille d'une planche est grisée.**
Une planche se supprime là où l'album se supprimerait sans rien demander, et nulle part
ailleurs. Touchez-la : elle dit à qui s'adresser. Un administrateur peut la supprimer.

**Le bouton `＋` de l'Atelier a disparu.**
Un album se crée désormais dans la Bibliothèque (`+ Nouvel album`), qui demande sa
collection. Ses images s'importent ensuite depuis sa fiche, dans la Bibliothèque
(étape 1).

**Je suis entré dans un projet et je n'y vois rien.**
Entrer dans un projet n'ouvre que sa collection de base, et seulement si le projet l'a
ouverte à ses membres ; toute autre collection garde son *Qui entre*. Demandez l'accès au
propriétaire de la collection voulue, ou créez la vôtre. Cf.
[`modele-et-droits.md`](modele-et-droits.md) §2.

**Mon image est refusée à l'import.**
Son format n'est pas dans les sept acceptés (étape 1). Deux contrôles se suivent, et l'un
ne remplace pas l'autre. L'**extension** du nom d'abord : hors liste, le fichier est refusé sans être décodé
— depuis ShareDocs il dit « type non géré (image attendue) », depuis votre disque il nomme
l'extension refusée. Puis le **contenu** : renommer un `.psd` en `.tif` passe le premier
contrôle mais pas le second, et c'est précisément ce qu'il empêche ; depuis votre disque, ce
refus-là commence par « Échec de l'ingestion ». Dans tous les cas rien n'a été enregistré :
convertissez en TIFF ou en JPEG et réimportez.

Un format accepté peut aussi être refusé pour sa **profondeur** : un scan en entiers 32 bits
(mode `I`) ou en nombres flottants (mode `F`) n'a pas d'équivalent sûr à l'écran, et le
message nomme le mode entre guillemets. Réexportez-le en 8 ou 16 bits entiers NON SIGNÉS : un
16 bits signé est rangé avec le 32 bits, et refusé de même. Les niveaux de gris
en 12 ou 16 bits, eux, sont acceptés et s'affichent avec leurs tons.

**Le bouton `Segmenter` (ou `Bulles`, ou `OCR`) ne fait rien / répond une erreur.**
Le moteur n'est probablement pas installé. Ouvrez **🩺 Moteurs** dans l'Administration : il
distingue « absent » de « présent mais cassé ». Un moteur absent n'empêche que sa propre passe.

**Le lot a sauté des planches.**
Les planches **verrouillées** (🔒) sont ignorées par les traitements par lot, exprès.

**L'OCR n'a rien changé sur cette bulle.**
Elle contenait déjà du texte. L'OCR ne remplit que le vide — il n'écrase jamais une saisie
humaine.

**La transcription affiche un crop illisible.**
Le cadre de la région est mal placé. Repassez en mode Édition (`E`), corrigez la géométrie, et
revenez : le crop est découpé à partir de ce cadre.

**Le panneau Grammaire ne s'affiche pas.**
Soit la région sélectionnée ne porte pas de texte, soit l'analyse linguistique n'est pas
installée sur cette instance. Dans le second cas, tout le reste fonctionne et la recherche
retombe sur le préfixe.

**Le champ s'ouvre, je saisis, et l'enregistrement est refusé.**
Vous n'avez que la lecture sur cette collection. L'interface ne reçoit pas votre droit
d'écriture, donc elle n'a rien masqué : le refus arrive au moment d'agir, pas avant. Rien
n'est cassé, et rien n'a été enregistré. Cf. [`modele-et-droits.md`](modele-et-droits.md) §3.

**J'ai corrigé des mots, puis quelqu'un a relancé l'OCR. Mes corrections ?**
Intactes. Elles vivent dans une couche séparée que la réindexation ne touche pas.

**Les numéros de planche ont changé.**
Quelqu'un a basculé une planche en `paratexte`, ou l'inverse. Le numéro éditorial est le rang
parmi les seules planches de récit, recalculé à chaque lecture.

**Ctrl+Z ne fait rien.**
Quatre cas : le curseur est dans un champ de saisie (c'est alors l'annulation du
navigateur) ; la dernière action était le fait d'un moteur, et les actes machine ne
s'annulent pas ; vous travaillez sous un compte déclaré PARTAGÉ (un groupe, une démonstration), où
Ctrl+Z ne remonte que les cinq dernières minutes — le message le dit ; ou il n'y a plus rien
à annuler.

**J'ai créé un tag et il n'apparaît pas chez un collègue.**
Il est probablement local à une collection. Cf. [`modele-et-droits.md`](modele-et-droits.md) §4.

**L'application répond « réessayez » pendant un traitement.**
Un lot en cours occupe brièvement la base. C'est attendu, et le message le dit plutôt que de
laisser passer une erreur obscure : relancez l'action.

**Le premier accès à l'analyse grammaticale est très lent.**
Le modèle linguistique se charge à la première demande — une dizaine de secondes. Ensuite il
reste en mémoire.
