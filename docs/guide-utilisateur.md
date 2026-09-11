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
| **Bibliothèque** | `/corpus` | créer et décrire les albums et les collections, régler la diffusion d'une collection et l'exporter, lancer les traitements par lot, suivre l'avancement planche par planche |
| **Atelier** | `/` | tout ce qui se fait sur une planche : corriger le découpage, transcrire, annoter, relire la grammaire, exporter |
| **Recherche** | `/recherche` | interroger les dialogues, les notes et les tags ; chaque résultat rouvre l'Atelier pile sur la région |
| **Exploration** | `/exploration` | mesurer : distributions, concordance, croisements, comparaison de deux sous-corpus ; documenter le vocabulaire |
| **Administration** | `/administration` | ce qui porte sur l'**instance** et non sur un album : qui entre dans chaque collection, les comptes, l'état des moteurs |

Une barre de navigation commune les relie, sur les cinq pages. Les réglages d'affichage —
thème clair/sombre, contraste élevé, zoom de l'interface — y sont aussi, et suivent d'une
surface à l'autre.

> **L'Administration n'est pas réservée**, et ça surprend. La page s'ouvre à tout le monde :
> c'est **chaque bloc** qui décide de ce qu'il montre — la liste des collections est filtrée
> par vos droits, la vue des comptes n'apparaît que si le serveur vous la sert, et l'état des
> moteurs est ouvert à tous, parce que savoir si l'OCR fonctionne n'est un pouvoir pour
> personne. Fermer la page entière aurait enfermé des choses qui n'ont rien à y faire.

> **Un mot sur le nom de la première.** La barre de navigation l'appelle **Atelier**, et
> c'est le nom retenu ici puisque c'est celui qu'on lit à l'écran. Elle s'est longtemps
> appelée **Visionneuse**, mot qu'on croise encore dans le code et dans les documents
> antérieurs : c'est la même page, `/`.

---

## 3. Le parcours en huit étapes

C'est l'ordre à suivre pour un corpus qui part de zéro. **Sur un corpus déjà rempli**, on
entre directement à l'étape 4, 5 ou 6 selon ce qui reste à faire : la Bibliothèque affiche
pour chaque planche son statut, sa validation et son avancement de relecture.

### Étape 1 — Constituer le corpus
**Bibliothèque · `+ Nouvel album` — puis Atelier, menu `⇅ Import / Export` pour les images**

L'album se crée dans la Bibliothèque (ou par le `＋` de la barre latérale de l'Atelier).
**L'import des images, lui, se fait depuis l'Atelier** : *⤓ Importer des images…* pour
votre disque, *🖼 Depuis ShareDocs…* pour parcourir un dossier Huma-Num distant et importer une
sélection entière. La Bibliothèque gère l'inventaire, pas l'entrée des fichiers.

**Sept formats sont acceptés, et rien d'autre** : TIFF et JPEG — les deux du corpus —, puis
JPEG 2000, PNG, BMP, GIF et WebP. La liste est courte exprès : elle borne aussi ce que le
décodeur d'images a le droit d'ouvrir, ce qui ferme une classe de fichiers piégés. Un
fichier hors liste est refusé sans rien enregistrer ; §6 dit à quoi ressemble le refus.

Chaque image importée est rangée en deux exemplaires : le **master** (le scan haute
résolution, jamais modifié) et un **dérivé web** allégé, qui est ce que vous voyez à l'écran.
La résolution et le mode colorimétrique sont lus dans le fichier au passage, ce qui permettra
d'afficher les dimensions physiques en centimètres.

Un album créé sans collection explicite entre dans la *Collection par défaut* ; si vous savez
déjà à quelle étude il appartient, choisissez sa collection au moment de le créer.

### Étape 2 — Décrire l'album
**Bibliothèque · fiche de l'album**

C'est ici que se saisissent la **paternité** (contributions : un nom, un rôle — scénariste,
dessinateur, coloriste…), les champs d'**édition** (date, éditeur, lieu, ISBN, format), la
**source de numérisation** (l'appareil et les conditions du scan) et l'appartenance aux
collections.

Ce n'est pas de la paperasse : c'est ce qui rendra le corpus citable et déposable. Le faire
maintenant coûte cinq minutes ; le faire deux ans plus tard suppose de retrouver l'exemplaire.

### Étape 3 — Pré-remplir *(optionnel)*
**Bibliothèque · cases à cocher `Segmenter` / `Bulles` / `OCR`, puis `▶ Lancer`**

Trois passes, dans cet ordre : les **cases**, puis les **bulles** à l'intérieur des cases, puis
le **texte** des bulles. Elles se lancent par lot sur une sélection d'albums et de planches, en
tâche de fond, avec une barre de progression et un bouton d'annulation. On peut aussi les
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
plein écran du mode Transcription est découpé dans le master **à partir du cadre de la
région** : une bulle mal détourée est illisible, donc intranscriptible. Elle reste taggable,
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

- le **locuteur** d'une bulle — quelle entité personnage y parle ;
- la **présence** dans une boîte personnage — quelle entité y est montrée ;
- le **profil** du personnage (dimensions de cible `personnage`) ;
- la **situation** d'une case (dimensions de cible `case`) ;
- les **tags** — vocabulaire libre, cumulatif, avec autocomplétion ;
- une **note** en texte libre.

Les personnages sont des entités de corpus : le même personnage traverse les albums, et peut
être **aligné** sur un référentiel externe (Wikidata, VIAF, IdRef) depuis son panneau.

Tout est sauvegardé automatiquement, une demi-seconde après la dernière frappe. **`Ctrl+Z`
annule la dernière action d'annotation** — y compris une suppression de région, recréée avec
tout ce qu'elle contenait et ses identifiants d'origine. Les actes des moteurs, eux, ne
s'annulent pas. Sous un compte déclaré partagé, Ctrl+Z ne remonte que les cinq dernières
minutes : au-delà, l'acte peut être celui d'un collègue qui tapait sous le même nom.

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
| **Comparaison A / B** | ce qui est sur-représenté dans un sous-corpus par rapport à un autre |

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
de l'une d'elles, et l'export dit laquelle.

Pour citer une image dans un article, utilisez plutôt le bouton **`＋ Figure`** du panneau de
région : il constitue un lot de figures, exporté en archive avec, pour chacune, le crop, sa
légende (référence de citation, responsabilité, édition, licence) et sa notice.

Les exports de **dépôt** — fiche de description, enregistrements, manifestes IIIF — se
prennent ailleurs, parce qu'ils portent sur une **collection** et non sur un album :
*Bibliothèque → 📚 Collections*, en dépliant la collection voulue (§4). Les **notices**
Dublin Core / DataCite et la **provenance** restent, elles, en ligne de commande (§5).

---

## 4. Les surfaces en détail

### Bibliothèque (`/corpus`)

L'inventaire et le poste de commande.

- **Albums** : créer, éditer les métadonnées, supprimer. La fiche porte la description, les
  contributions, les champs d'édition, la source de numérisation et l'appartenance aux
  collections.
- **Planches** : ouvrir, supprimer, et trois marques indépendantes —
  **rôle** (`récit`, numéroté, ou `paratexte` : couverture, liminaire, publicité, écarté de la
  numérotation), **validation** (✔ relue et finalisée, décomptée par album) et
  **verrou** (🔒 protège des passes automatiques).
- **Relecture** : une pastille par planche, et un filtre pour n'afficher que les planches à
  faire, en cours ou faites.
- **Traitements par lot** : cocher les passes voulues, sélectionner des albums ou des planches,
  lancer. Progression et annulation en direct.
- **📚 Collections** : créer une collection — il suffit d'être connecté, et l'on en devient
  propriétaire —, la décrire (description, dates), régler sa diffusion (régime, embargo,
  licence, base légale), désigner son référent, la renommer, la supprimer, et l'exporter
  pour un dépôt (ci-dessous). Seul un propriétaire modifie ; un participant lit la
  description et sait à qui écrire. La date d'embargo **retient** : tant qu'elle court, les
  scans ne sortent pas, même d'une collection « public » — et elle ne publie jamais rien
  d'elle-même. Qui entre dans une collection, et à quel niveau, se règle dans
  l'Administration.

#### Exporter une collection pour un dépôt

Dans **Bibliothèque → 📚 Collections**, dépliez une collection : le bloc **Export de
dépôt** produit, sans passer par la ligne de commande, les trois artefacts qu'un entrepôt
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

Ce qui porte sur l'instance : quelle version tourne ici, qui voit quoi, quels comptes
existent, et si les moteurs répondent encore. Quatre blocs, chacun avec sa propre règle
d'accès (cf. §2).

- **🏷️ Version servie** : le commit que cette instance fait tourner. N'apparaît que si le
  serveur vous le sert — c'est réservé aux administrateurs, parce que le dépôt est public
  et qu'un numéro de version y dit quels correctifs sont en place. L'application ne connaît
  que ce bout-là : elle affiche le commit servi et vous laisse le comparer à `origin/main`,
  plutôt que d'affirmer « à jour » sans avoir vu la référence.
- **👥 Accès aux collections** : accorder, changer et retirer les accès, collection par
  collection. Chaque accès porte une case **peut exporter** : sortir le contenu en
  fichier est un droit à part, que le propriétaire accorde ici — il l'a lui-même
  d'office, et sa case le montre sans se laisser décocher. Le bloc déclare aussi quels
  groupes d'administration voient tout le corpus.
  Créer, décrire, renommer, supprimer ou exporter une collection se fait dans la
  Bibliothèque. Cf. [`modele-et-droits.md`](modele-et-droits.md) §3.
- **Comptes vus par l'application** : n'apparaît que si le serveur vous le sert. C'est un
  miroir d'affichage — l'application n'a pas d'annuaire (cf. [`modele-et-droits.md`](modele-et-droits.md) §3).
- **🩺 Moteurs** : quels moteurs sont présents, et *Éprouver les moteurs* pour vérifier qu'ils
  démarrent réellement.

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

### Exploration (`/exploration`)

Les quatre vues du tableau de l'étape 7, avec des filtres communs : album, type de région,
catégorie grammaticale, **provenance** (auto / corrigé / validé), tag, locuteur. Le filtre de
provenance est celui qui permet de ne mesurer que sur ce qui a été relu par un humain.

Le panneau **📖 Lexique** liste tout le vocabulaire — domaines, dimensions, valeurs, tags —
avec pour chacun sa définition, sa note de portée, son état et sa portée d'appartenance, plus
un « % défini » d'ensemble. C'est aussi de là qu'on **importe une taxonomie** depuis un
tableur.

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
| Créer un compte, un groupe | fichier des comptes du portail | [`exploitation.md`](exploitation.md), « Ajouter un compte sans couper le portail » |

L'**import PDF** est annoncé dans le menu mais désactivé : il n'est pas encore implémenté.

---

## 6. Quand ça ne marche pas

**Je ne vois aucun album.**
Lisez le bandeau en haut de page, et **dépliez-le** : il distingue une panne de configuration
d'un simple manque d'accès, et nomme la personne à qui écrire quand l'instance en a déclaré
une. Cf. [`modele-et-droits.md`](modele-et-droits.md) §3, et §7 pour la question complète.

**Mon image est refusée à l'import.**
Son format n'est pas dans les sept acceptés (étape 1). C'est le **contenu** du fichier qui
décide, pas son extension : renommer un `.psd` en `.tif` ne le fait pas passer, et c'est
précisément ce que le contrôle empêche. Le message diffère selon la provenance — depuis
ShareDocs, le refus est immédiat et dit « type non géré (image attendue) » ; depuis votre
disque, le fichier est lu d'abord et le message commence par « Échec de l'ingestion ». Dans
les deux cas rien n'a été enregistré : convertissez en TIFF ou en JPEG et réimportez.

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
