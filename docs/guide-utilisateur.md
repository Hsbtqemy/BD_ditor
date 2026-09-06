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
refus explicite, jamais par une erreur obscure. Le panneau **🩺 Moteurs** de la Bibliothèque
dit lesquels sont là — et le bouton *Éprouver les moteurs* va plus loin en les **important
pour de bon**, parce qu'un moteur présent sur le disque peut très bien refuser de démarrer.

---

## 2. Les quatre surfaces

| Surface | Adresse | Ce qu'on y fait |
|---|---|---|
| **Bibliothèque** | `/corpus` | créer et décrire les albums, importer les planches, lancer les traitements par lot, gérer les collections et leurs accès, contrôler les moteurs |
| **Visionneuse** | `/` | tout ce qui se fait sur une planche : corriger le découpage, transcrire, annoter, relire la grammaire, exporter |
| **Recherche** | `/recherche` | interroger les dialogues, les notes et les tags ; chaque résultat rouvre la Visionneuse pile sur la région |
| **Exploration** | `/exploration` | mesurer : distributions, concordance, croisements, comparaison de deux sous-corpus ; documenter le vocabulaire |

Une barre de navigation commune les relie, sur les quatre pages. Les réglages d'affichage —
thème clair/sombre, contraste élevé, zoom de l'interface — y sont aussi, et suivent d'une
surface à l'autre.

---

## 3. Le parcours en huit étapes

C'est l'ordre à suivre pour un corpus qui part de zéro. **Sur un corpus déjà rempli**, on
entre directement à l'étape 4, 5 ou 6 selon ce qui reste à faire : la Bibliothèque affiche
pour chaque planche son statut, sa validation et son avancement de relecture.

### Étape 1 — Constituer le corpus
**Bibliothèque · `+ Nouvel album` — puis Visionneuse, menu `⇅ Import / Export` pour les images**

L'album se crée dans la Bibliothèque (ou par le `＋` de la barre latérale de la Visionneuse).
**L'import des images, lui, se fait depuis la Visionneuse** : *⤓ Importer des images…* pour
votre disque, *🖼 Depuis ShareDocs…* pour parcourir un dossier Huma-Num distant et importer une
sélection entière. La Bibliothèque gère l'inventaire, pas l'entrée des fichiers.

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
lancer planche par planche depuis la Visionneuse (menu *⚙ Traitement*).

L'ordre de lecture — rangées de haut en bas, gauche à droite, bulles groupées par case — est
recalculé automatiquement après chaque passe.

Une planche **verrouillée** (🔒) est sautée par les lots : c'est ainsi qu'on protège un travail
manuel d'une repasse automatique.

Si un moteur n'est pas installé, cette étape se saute entièrement — la suite fonctionne
identiquement, avec plus de travail manuel à l'étape 4.

### Étape 4 — Corriger le découpage
**Visionneuse · mode Édition (`E`)**

Redimensionnez les régions par leurs poignées, ajustez au pixel près par saisie numérique,
dessinez les régions manquantes au cliquer-glisser, supprimez les fausses (`Suppr`). Une
région porte un **type** : case, bulle, personnage, texte, cartouche.

**Cette étape conditionne la suivante, et c'est la raison de sa place ici.** Le crop
plein écran du mode Transcription est découpé dans le master **à partir du cadre de la
région** : une bulle mal détourée est illisible, donc intranscriptible. Elle reste taggable,
en revanche — la géométrie contraint le texte, pas l'interprétation.

### Étape 5 — Transcrire et relire
**Visionneuse · mode Transcription (`T`), puis panneau Grammaire**

Le mode Transcription est un plein écran bulle à bulle : le crop net à gauche, l'éditeur à
droite, `Tab` et `Maj+Tab` pour avancer et reculer, un enchaînement possible sur tout l'album.
La sauvegarde est automatique.

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
**Visionneuse · mode Annotation (`A`)**

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
s'annulent pas.

Sur le choix « tag ou dimension ? », voir [`modele-et-droits.md`](modele-et-droits.md) §4 :
un tag se cherche, un attribut se compte.

### Étape 7 — Chercher et explorer
**Recherche (`/recherche`), puis Exploration (`/exploration`)**

La **Recherche** interroge en plein texte les dialogues, les notes et les tags — et les lemmes
si l'analyse linguistique est active, auquel cas « otage » trouve « otages ». Les accents sont
ignorés. Filtres par album, type de région et tags, nuage de tags, export CSV des résultats.
Chaque résultat montre un extrait surligné et une vignette, et **rouvre la Visionneuse
exactement sur la région**.

L'**Exploration** mesure au lieu de retrouver, en quatre vues :

| Vue | Ce qu'elle répond |
|---|---|
| **Distribution** | quels lemmes, catégories ou traits morphologiques, et à quelle fréquence |
| **Concordance (KWIC)** | où exactement, avec le contexte de chaque occurrence — et un lien vers la Visionneuse |
| **Croisement (2D)** | une facette contre une autre, en tableau de contingence avec carte de chaleur ; une cellule s'ouvre en concordance |
| **Comparaison A / B** | ce qui est sur-représenté dans un sous-corpus par rapport à un autre |

L'état de la page est dans l'URL : une vue se partage par simple copier-coller du lien.

Trois panneaux complètent la surface : **📖 Lexique** (documenter le vocabulaire),
**🎯 Accord** (part des corrections que le modèle linguistique retrouvait déjà seul) et
**👥 Inter** (accord entre annotateurs, quand un relecteur retouche le travail d'un autre).
Ce dernier est le seul rapport **réservé** : il faut écrire quelque part pour le consulter,
parce qu'il mesure des personnes et non un corpus.

### Étape 8 — Exporter
**Visionneuse · menu `⇅ Import / Export`**

Trois formats, par album : **JSON-LD**, **CSV** et **TEI P5**. Une **sauvegarde** complète de
la base est également téléchargeable depuis ce menu — réservée aux administrateurs.

Pour citer une image dans un article, utilisez plutôt le bouton **`＋ Figure`** du panneau de
région : il constitue un lot de figures, exporté en archive avec, pour chacune, le crop, sa
légende (référence de citation, responsabilité, édition, licence) et sa notice.

Les exports de **dépôt** — description de collection, notices, manifestes IIIF — n'ont pas
encore de bouton : voir §5.

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
- **👥 Collections** : créer une collection, la renommer, la supprimer, accorder et retirer les
  accès, désigner un référent. Le panneau déclare aussi quels groupes d'administration voient
  tout le corpus. Cf. [`modele-et-droits.md`](modele-et-droits.md) §3.
- **🩺 Moteurs** : quels moteurs sont présents, et *Éprouver les moteurs* pour vérifier qu'ils
  démarrent réellement.

### Visionneuse (`/`)

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
| Régime de diffusion, licence, base légale, embargo, responsables d'une collection | `tools/gerer_collections.py` | [`export-metadonnees.md`](export-metadonnees.md) |
| Description de collection, enregistrements CSV/XLSX/JSON, manifestes IIIF | `tools/` | [`export-metadonnees.md`](export-metadonnees.md) |
| Notices Dublin Core / DataCite, provenance PROV-O / TEI | `tools/` | [`crosswalk-depot.md`](crosswalk-depot.md), [`provenance-audit.md`](provenance-audit.md) |
| Rapports d'accord (modèle↔humain, inter-annotateurs) en CSV/JSON | `tools/` | [`rapport-accord.md`](rapport-accord.md), [`accord-inter.md`](accord-inter.md) |
| Réindexer tout le corpus après un changement de modèle linguistique | `tools/reindex_nlp.py` | [`correction-grammaticale.md`](correction-grammaticale.md) |
| Relire la résolution des planches importées avant cette fonctionnalité | `tools/reindex_materiel.py` | [`materiel-numerisation.md`](materiel-numerisation.md) |
| Créer un compte, un groupe | fichier des comptes du portail | [`exploitation.md`](exploitation.md) §2 |

L'**import PDF** est annoncé dans le menu mais désactivé : il n'est pas encore implémenté.

---

## 6. Quand ça ne marche pas

**Je ne vois aucun album.**
Lisez le bandeau en haut de page, et **dépliez-le** : il distingue une panne de configuration
d'un simple manque d'accès, et nomme la personne à qui écrire quand l'instance en a déclaré
une. Cf. [`modele-et-droits.md`](modele-et-droits.md) §3, et §7 pour la question complète.

**Le bouton `Segmenter` (ou `Bulles`, ou `OCR`) ne fait rien / répond une erreur.**
Le moteur n'est probablement pas installé. Ouvrez **🩺 Moteurs** dans la Bibliothèque : il
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

**J'ai corrigé des mots, puis quelqu'un a relancé l'OCR. Mes corrections ?**
Intactes. Elles vivent dans une couche séparée que la réindexation ne touche pas.

**Les numéros de planche ont changé.**
Quelqu'un a basculé une planche en `paratexte`, ou l'inverse. Le numéro éditorial est le rang
parmi les seules planches de récit, recalculé à chaque lecture.

**Ctrl+Z ne fait rien.**
Trois cas : le curseur est dans un champ de saisie (c'est alors l'annulation du navigateur) ;
la dernière action était le fait d'un moteur, et les actes machine ne s'annulent pas ; ou il
n'y a plus rien à annuler.

**J'ai créé un tag et il n'apparaît pas chez un collègue.**
Il est probablement local à une collection. Cf. [`modele-et-droits.md`](modele-et-droits.md) §4.

**L'application répond « réessayez » pendant un traitement.**
Un lot en cours occupe brièvement la base. C'est attendu, et le message le dit plutôt que de
laisser passer une erreur obscure : relancez l'action.

**Le premier accès à l'analyse grammaticale est très lent.**
Le modèle linguistique se charge à la première demande — une dizaine de secondes. Ensuite il
reste en mémoire.
