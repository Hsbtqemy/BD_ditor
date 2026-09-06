# Le modèle : ce qu'on manipule, et qui peut quoi

Ce document explique les **objets** de l'outil et les **règles** qui décident qui voit
quoi. Il se lit une fois, avant de commencer, puis se rouvre quand une question de droits
ou de vocabulaire se pose. Les gestes — importer, segmenter, transcrire, annoter — vivent
dans [`guide-utilisateur.md`](guide-utilisateur.md), qui renvoie ici chaque fois qu'un mot
demande à être défini.

Il décrit ce que l'outil **fait**, pas ce qu'il fera : les renvois vers les notes de
conception (`docs/*.md`) sont là pour qui veut le pourquoi, jamais pour compléter un manque.

---

## 1. La hiérarchie des objets

```
COLLECTION      espace de travail ET unité de dépôt ; c'est elle qui PORTE LES ACCÈS
    │           (lien N-N : un album peut vivre dans plusieurs collections,
    │            aucun album ne vit hors collection)
    ▼
ALBUM           un ouvrage numérisé : titre, paternité, édition, source de numérisation
    │
    ▼
PLANCHE         une image (master + dérivé web) : rôle récit/paratexte, statut,
    │           validation, verrou, statut de relecture
    ▼
RÉGION          une zone rectangulaire, en PIXELS MASTER
    │           types : case · bulle · personnage · texte · cartouche
    │           arborescente : une bulle a sa case pour parent
    │
    ├──▶ ANNOTATION ......... une note libre + des TAGS (N-N)
    ├──▶ TEXTE OCR ..........▶ TOKENS (lemme, catégorie, morphologie) — NLP optionnel
    ├──▶ LOCUTEUR (bulle) ...─┐
    ├──▶ PRÉSENCE (perso.) ..─┼──▶ PERSONNAGE   entité de corpus, transverse aux albums
    └──▶ SITUATION (case) ...─┘                 (+ alignements Wikidata / VIAF / IdRef)
                                    │
                                    └──▶ VALEURS D'ATTRIBUTS (domaine → dimension → valeur)
```

Trois objets ne sont dans aucune boîte, et c'est voulu.

- **Le personnage** est une entité de **corpus**, pas de planche : « Tintin » est le même
  d'un album à l'autre. Une bulle lui est reliée par un **locuteur** (qui parle), une boîte
  personnage par une **présence** (qui est montré). L'entité est le moyeu où la parole et
  l'image se rejoignent.
- **Le vocabulaire** (tags, domaines, dimensions, valeurs) vit au niveau du corpus, avec sa
  propre règle de portée — cf. §4.
- **Le journal de provenance** enregistre chaque acte (qui, quoi, avant/après) sans jamais
  être modifié. C'est lui que remonte l'annulation (Ctrl+Z), et il **survit à la suppression**
  de ce qu'il décrit. Cf. [`provenance-audit.md`](provenance-audit.md) et [`undo.md`](undo.md).

### Ce qui est dérivé, jamais stocké

Cinq informations sont **recalculées** à chaque lecture au lieu d'être enregistrées. Ce n'est
pas une économie de place : un chiffre recopié vieillit en silence, alors qu'un chiffre
dérivé ne peut pas se désaccorder de ce dont il dépend.

| Information | Dérivée de | Conséquence pratique |
|---|---|---|
| Numéro éditorial d'une planche | rang parmi les planches de rôle `récit` | basculer une planche en `paratexte` renumérote la suite, sans rien à corriger |
| Citation `pl·c` / `pl·c·b` | numéro éditorial + ordre de lecture | réordonner les cases change les citations : à figer avant de citer par écrit |
| Dimensions physiques (cm) | pixels ÷ résolution lue à l'import | une planche sans résolution n'affiche pas de cm, et c'est un fait, pas un bug |
| Statut de relecture d'une planche | provenance de ses tokens | il avance tout seul à mesure qu'on relit ; on peut le **forcer**, jamais le fabriquer |
| État d'un embargo | date d'embargo comparée à aujourd'hui | cf. §5 : une date **retient**, elle ne promeut jamais |

### Les coordonnées sont en pixels master

Une région est stockée dans les coordonnées du **scan haute résolution**, jamais dans celles
de l'image affichée. L'affichage web est un dérivé à 25 % ; la conversion se fait au moment
de dessiner. Vous n'avez rien à faire de cette règle, sauf en connaître la conséquence : les
coordonnées lues dans le mode Édition sont celles du master, donc environ quatre fois plus
grandes que ce que vous mesureriez à l'écran.

---

## 2. La collection : un objet, trois métiers

La collection est le seul objet qui remplit **trois rôles à la fois**, et c'est la source
de la plupart des malentendus.

| Rôle | Ce que ça veut dire | Où ça se voit |
|---|---|---|
| **Espace de travail** | c'est elle qui porte les accès : donner un droit sur une collection le donne sur tous ses albums | panneau *👥 Collections* de la Bibliothèque |
| **Unité de dépôt** | 1 collection = 1 dépôt Nakala/HAL = 1 DOI ; elle porte licence, base légale, régime de diffusion, responsables scientifiques | outils `tools/`, cf. [`export-metadonnees.md`](export-metadonnees.md) |
| **Portée d'appartenance du vocabulaire** | un terme peut être *global* ou *local à une collection* | panneau *📖 Lexique* de l'Exploration |

Trois règles en découlent, qu'il vaut mieux connaître avant de les rencontrer.

- **Un album peut vivre dans plusieurs collections** (lien N-N). Il suit alors les droits de
  chacune : y être admis par l'une suffit.
- **Aucun album ne vit hors collection.** Un album créé sans collection explicite entre dans
  la *Collection par défaut* — un album orphelin ne correspondrait à aucune règle, et il
  faudrait en inventer une dans le code. Ce nom est **réservé** : personne ne peut le donner
  à une collection neuve.
- **Retirer le dernier lien est refusé**, avec un message qui nomme la contrainte : ni
  collection sans propriétaire, ni album sans collection.

---

## 3. Qui peut quoi

### L'application n'authentifie personne

C'est le point le plus contre-intuitif, et il explique tout le reste. BéDéditeur ne
demande jamais de mot de passe, ne stocke aucun secret et n'a **aucun annuaire**. En
production, c'est **Authelia** — un portail placé devant l'application — qui vérifie
l'identité et la double authentification, puis transmet à l'application trois en-têtes :
qui vous êtes, votre nom lisible, et vos groupes.

L'application ne croit ces en-têtes que si on lui a **déclaré** qu'un proxy est bien devant
elle (`BD_AUTH_PROXY`). Deux conséquences :

- **En local, sans proxy** : les en-têtes sont ignorés, tout acte est anonyme et **la portée
  est totale**. C'est le mono-poste, et il ne change pas.
- **Avec le drapeau mais sans identité qui parvient** : la portée est **vide**. Fermeture par
  défaut — une panne bruyante plutôt qu'une fuite discrète.

### Un groupe est un NOM, jamais une appartenance

L'application ne stocke **jamais** « Alice est dans `bd-lettrage` ». Elle stocke
« `bd-lettrage` ouvre la collection 3 », et relit la composition du groupe dans les
en-têtes **à chaque requête**. Retirer quelqu'un d'un groupe côté Authelia lui ferme donc la
porte immédiatement, sans rien à nettoyer dans l'application.

Le revers est à connaître : **un accès se déclare par un nom, pas par une personne vérifiée.**
Un login mal orthographié n'ouvre rien — et ne le dit pas, puisque l'application n'a aucun
moyen de savoir que ce nom n'existe pas.

### Les trois niveaux

Un accès associe un **principal** (un login, ou un nom de groupe) à une collection, avec un
niveau. Les niveaux **s'empilent** : un propriétaire écrit et lit ; qui écrit lit aussi.

| Geste | lecture | écriture | propriétaire | `bd-admins` |
|---|:---:|:---:|:---:|:---:|
| **Créer** une collection | ✅ | ✅ | ✅ | ✅ |
| Voir les albums, planches, régions, annotations | ✅ | ✅ | ✅ | ✅ |
| Chercher, explorer, exporter le contenu (JSON-LD / CSV / TEI) | ✅ | ✅ | ✅ | ✅ |
| Transcrire, corriger le découpage, annoter, relire la grammaire | — | ✅ | ✅ | ✅ |
| Lancer les passes automatiques (cases, bulles, OCR) | — | ✅ | ✅ | ✅ |
| Créer et documenter du vocabulaire local à la collection | — | ✅ | ✅ | ✅ |
| Consulter le rapport d'accord **inter-annotateurs** (*👥 Inter*) | — | ✅ | ✅ | ✅ |
| Accorder et retirer les accès de la collection | — | — | ✅ | ✅ |
| Renommer, supprimer la collection, désigner son référent | — | — | ✅ | ✅ |
| Modifier licence, base légale, régime de diffusion, embargo | — | — | ✅ | ✅ |
| Télécharger la sauvegarde complète de la base | — | — | — | ✅ |
| Couper ou remplacer la session ShareDocs **d'instance** | — | — | — | ✅ |

**Écrire n'est pas administrer, et la distinction est délibérée** : annoter, c'est travailler ;
décider qui d'autre entrera, c'est autre chose. Un membre en écriture n'hérite pas du droit
d'élargir le cercle.

Une seule mesure d'analyse est **réservée**, et c'est l'accord inter-annotateurs : toutes les
autres portent sur le corpus, celle-ci porte sur des **personnes** — elle nomme, apparie et
cite à la ligne près. La règle est que *ceux qui voient la mesure sont ceux qu'elle mesure*,
d'où le niveau écriture. Au dépôt, la fiche ne garde que le nombre d'auteurs et des paires
sans identités : « relu à plusieurs, accord 0,87 » ne demande aucun nom.

**Un groupe peut posséder une collection**, et c'est souvent le bon choix : un espace de
travail survit rarement au départ d'une personne.

**Créer une collection ne demande aucun droit — seulement une identité**, et son créateur en
devient propriétaire. Refuser la création à qui n'a encore rien rendrait l'application
inutilisable au premier jour de chacun. Deux cas ne posent pas de propriétaire, et c'est
normal : en mono-poste, il n'y a personne à inscrire ; pour un administrateur, qui possède
déjà tout, un lien personnel avec chaque collection créée fausserait la notion — s'il la veut,
il se l'accorde.

### L'administrateur, et pourquoi il est déclaré

Le groupe `bd-admins` lit et écrit **tout le corpus sans figurer dans aucune liste d'accès**.
Ce n'est pas un défaut : c'est la vérité de tout auto-hébergement — qui tient la machine tient
les données. Ce qui serait fautif, c'est que ce pouvoir soit **invisible**. Le panneau
*👥 Collections* le **déclare donc en clair**, en nommant les groupes réellement lus plutôt
qu'une constante recopiée dans un coin.

C'est aussi un **recours** : sans lui, le départ du dernier propriétaire d'une collection
fabriquerait un espace définitivement bloqué.

*En mono-poste, rien de tout cela n'apparaît* : sans proxy, aucun groupe n'est lu — nommer
`bd-admins` là où l'on est seul distinguerait deux rôles qui n'en font qu'un.

### Ce qu'on ne voit pas est *absent*, pas *interdit*

Un album auquel vous n'avez pas accès répond **404 — introuvable**, jamais 403. Dire
« ça existe, mais pas pour vous » révélerait la composition du corpus : combien d'albums,
sur quoi travaillent les autres équipes.

Ce choix a un prix d'ergonomie, assumé et compensé : **une portée vide rend l'application
indistinguable d'un corpus vide.** D'où un bandeau qui distingue **trois** pannes — et non
deux — par les groupes reçus :

| Ce qui parvient | Ce que ça signifie | Qui répare |
|---|---|---|
| aucune identité | le portail ne transmet rien : l'application est joignable sans passer par lui | administrateur système |
| une identité, **aucun groupe** | le portail transmet le login mais pas les groupes | administrateur système |
| une identité **et** ses groupes, dont aucun n'a d'accès | tout fonctionne : personne ne vous a encore donné accès | un **propriétaire** de collection |

Les deux premières se réparent dans la configuration ; la troisième non. Les confondre envoie
chercher une panne qui n'existe pas — c'est pourquoi la liste des groupes reçus se lit à cet
endroit précis, et à cet endroit seulement.

Le bandeau donne d'abord la réponse courte — *pourquoi* l'écran est vide — et **replie le
détail derrière son titre** : ce qu'il faut en faire peut attendre un clic. Il s'ouvre de
lui-même dans le seul cas dont on sache qu'il est une panne : aucune identité ne parvient
alors qu'un proxy est déclaré. Quand une instance a déclaré un **référent global**, c'est ici
qu'il est nommé — et c'est le seul endroit possible, puisqu'une portée vide ne lit aucune
collection, donc aucun référent de collection.

### Le référent : une adresse, pas un droit

Une collection peut nommer un **référent** — un nom lisible et un moyen de le joindre. Le
désigner est un geste de propriétaire ; le **lire** est le geste de quiconque a une question,
y compris un participant qui ne possède rien.

Un référent **n'accorde rien et ne retire rien**. Il est distinct des **responsables
scientifiques**, qui portent un ORCID et partent dans les notices de dépôt : le référent, lui,
ne sort d'aucun artefact exporté. C'est une adresse d'exploitation, elle reste dans la maison.

Une instance peut aussi déclarer un **référent global** (`BD_REFERENT_NOM` /
`BD_REFERENT_CONTACT`, dans la configuration serveur) : c'est le seul destinataire qu'une
portée vide puisse lire, puisqu'elle ne voit aucune collection.

---

## 4. Le vocabulaire

Aucune taxonomie n'est imposée. Les catégories **émergent du corpus** : on crée le terme
quand on en a besoin, et on le documente ensuite. Ce qui suit décrit les deux familles de
termes, et la couche de définition qu'elles partagent.

### Deux familles, deux usages

| | **Tags** | **Attributs facettés** |
|---|---|---|
| Forme | une étiquette à plat | un axe et ses valeurs canoniques |
| Structure | aucune | **domaine → dimension → valeur** |
| S'applique à | n'importe quelle région, via son annotation | un **personnage** (profil) ou une **case** (situation de scène) |
| Bon pour | repérer, marquer, retrouver | **compter, croiser, comparer** |
| Où on l'écrit | panneau *Tags* de la Visionneuse | panneaux *Personnage* et *Situation (scène)* de la Visionneuse |
| Où on le documente | panneau *📖 Lexique* de l'Exploration | panneau *📖 Lexique* de l'Exploration |

La règle de choix tient en une phrase : **un tag se cherche, un attribut se compte.** « scène
de nuit » en tag vous rendra les régions concernées ; la même chose en dimension `moment` avec
les valeurs `jour` / `nuit` / `indéterminé` vous rendra un tableau — et un croisement avec une
autre dimension.

Les tags sont insensibles à la casse et stockés en minuscules.

### Domaine → dimension → valeur

```
DOMAINE       un champ analytique          « émotions »
   │                                        (regroupe des dimensions ; facultatif)
   ▼
DIMENSION     un AXE, avec une cible        « type d'émotion » (cible : case)
   │                                        « milieu social »  (cible : personnage)
   ▼
VALEUR        une valeur canonique          « colère » · « joie » · « peur »
```

Trois précisions qui évitent des impasses :

- **Le domaine est facultatif.** Une dimension peut vivre sans domaine ; on regroupe le jour
  où le regroupement dit quelque chose.
- **Le domaine est orthogonal à la cible** : un même domaine peut réunir des dimensions qui
  s'appliquent aux personnages **et** aux cases. Les émotions ne sont qu'un domaine parmi
  d'autres, pas un module figé de l'outil.
- **La valeur est canonique** : « rural » est une entrée, pas trois orthographes. C'est ce qui
  rend l'agrégation possible — sans quoi le comptage compterait des variantes.

Supprimer un domaine ne supprime pas ses dimensions : elles remontent simplement « hors
domaine ». Supprimer une dimension, en revanche, emporte ses valeurs.

### Le lexique situé : quatre champs par terme

Chaque terme — domaine, dimension, valeur **et** tag — porte la même couche définitionnelle,
au format SKOS, éditable dans le panneau *📖 Lexique*.

| Champ | Ce qu'on y met | Pourquoi |
|---|---|---|
| **Définition** | ce que le terme veut dire | sans elle, deux personnes annotent deux choses sous le même mot |
| **Note de portée** | le cadre d'emploi : quand l'appliquer, quand ne pas l'appliquer | c'est le « **situé** » — la partie qui se perd le plus vite et qu'on ne retrouve jamais |
| **État** | `provisoire` → `défini` | même geste que `auto` → `validé` sur la grammaire : dit ce qui est stabilisé |
| **Portée** | globale, ou locale à une collection | cf. ci-dessous |

Le panneau affiche un **« % défini »**, qui mesure la part du vocabulaire documenté. Il est
calculé sur ce que vous voyez, pas sur le corpus entier.

### Global ou local à une collection

Un terme est soit **global** (visible partout), soit **local** à une collection (visible de
ceux qui lisent cette collection). Un terme local peut être **promu** global ; c'est un geste,
pas un accident.

Deux règles gouvernent cette portée, et la seconde n'est pas intuitive.

1. **Un terme n'est jamais plus global que celui dont il dépend.** Une dimension hérite de la
   portée de son domaine, une valeur de celle de sa dimension. Sans cette règle, une valeur
   créée sous un axe privé naîtrait globale — et ce qui fuirait ne serait pas le mot, mais le
   **nom de l'axe**, c'est-à-dire une grille d'analyse. Déplacer une dimension sous un domaine
   privé la fait donc **descendre** avec lui ; l'en **détacher ne la promeut pas**, parce que
   ranger n'est pas publier.
2. **Le vocabulaire ne suit pas la même règle que les données.** Vous voyez un terme s'il est
   global **ou** local à une collection que vous lisez. En revanche ses **compteurs**
   (fréquences, usages) sont filtrés comme des données : un nuage de tags doit refléter le
   sous-corpus qu'on regarde, pas le corpus entier.

**Voir n'est pas modifier.** Un terme *local* se modifie si vous écrivez dans **sa**
collection ; un terme *global* se modifie si vous écrivez **quelque part**. Un refus de
modification sur un terme est un **403** — il vient d'être listé, un 404 mentirait.

### Amorcer le vocabulaire en lot

On peut charger une taxonomie entière depuis un tableur CSV (séparateur `;`), colonnes :

```
domaine ; domaine_definition ; cible ; dimension ; dimension_definition ;
dimension_note_portee ; valeur ; valeur_definition
```

L'import **pré-remplit sans écraser** — exactement comme l'OCR : un terme qui existe déjà
garde sa définition. Il est donc rejouable sans risque. Deux portes, le même cœur : le bouton
*Importer un tableur…* du panneau *📖 Lexique* (avec un sélecteur de portée), et
`tools/importer_vocabulaire.py` en ligne de commande (`--collection`, `--dry-run`, modèle dans
`tools/vocabulaire-modele.csv`). Cf. [`import-vocabulaire.md`](import-vocabulaire.md).

---

## 5. Les régimes de diffusion — citer n'est pas publier

Une collection déclare un **régime** et, éventuellement, une **date d'embargo**. Ces
descripteurs ne bordent **rien à l'intérieur de l'instance** : qui est admis sur une
collection en reçoit tout, scans compris. L'annotation repose sur les images, et le
cloisonnement entre équipes est l'affaire des accès (§3), pas du régime.

Le régime devient opposable **à la sortie**, et là seulement.

| Régime | Ce que ça change |
|---|---|
| `public` | seul régime dont un manifeste IIIF emporte les **images** |
| `embargo` | les images sont retenues jusqu'à la date, et la date **retient** même une collection déclarée publique |
| `restreint` · `prive` | les images ne sortent pas ; la géométrie et l'enrichissement restent publiables |

Trois choses valent d'être sues :

- **Un manifeste amputé le déclare.** Retenir ses images et les avoir oubliées seraient
  autrement indistinguables.
- **Une échéance passée ne rend rien publiable toute seule.** L'outil ignore *pourquoi*
  l'embargo existe : un délai qu'on s'est donné se lève seul, un délai imposé par un ayant
  droit non. Une échéance dépassée est **signalée** — dans l'écran Collections, dans le
  manifeste, dans l'outil en ligne de commande — pour qu'un corpus ne reste pas fermé par
  inertie. La décision, elle, reste humaine.
- **Une date illisible retient aussi.** Une faute de frappe ne doit ni ouvrir la porte, ni
  passer pour une décision.

**Citer, en revanche, n'est jamais bloqué par le régime.** La **figure citable** (bouton
*＋ Figure* de la Visionneuse) produit un crop accompagné de sa légende — référence `pl·c·b`,
responsabilité, édition, licence, base légale, « non établie » quand c'est le cas — et de sa
notice. Le cloisonnement des accès s'y applique entièrement : on ne cite que ce qu'on voit.
Cf. [`figure-citable.md`](figure-citable.md) et [`hebergement-securite.md`](hebergement-securite.md).

Régime, licence, base légale, embargo et responsables **n'ont pas encore de formulaire** :
ils s'affichent dans la Bibliothèque, mais s'écrivent par `tools/gerer_collections.py`
(cf. [`export-metadonnees.md`](export-metadonnees.md)).

---

## 6. Administrer l'instance : comptes et groupes

> Les commandes exactes vivent dans [`exploitation.md`](exploitation.md) §2, qui **fait foi**.
> Ce qui suit en donne la forme et les pièges, pour comprendre et pour expliquer.

### Où vit quoi

| | Comptes et groupes | Accès aux collections |
|---|---|---|
| Où | `deploy/authelia/users_database.yml`, sur le serveur | dans l'application, panneau *👥 Collections* |
| Qui | administrateur système (accès shell) | tout **propriétaire** de la collection |
| Effet | qui peut **entrer** | qui voit **quoi** |
| Prise d'effet | au redémarrage du conteneur Authelia | immédiate |

Les deux sont nécessaires, et dans cet ordre. **Un compte créé sans accès ouvre une
application vide** — la personne se connectera parfaitement et ne verra rien, sans qu'aucun
message ne l'explique autrement que par le bandeau de portée vide.

### Ajouter quelqu'un — la forme

1. Générer un **hash** de mot de passe (jamais le mot de passe en clair dans un fichier ou
   dans l'historique du shell).
2. **Copier le fichier des comptes avant de l'éditer.** C'est cette copie qui rend l'étape 4
   réparable.
3. Dupliquer un bloc sous `users:` — adresse, hash, groupes.
4. **Contrôler le YAML.** Une faute de syntaxe empêche Authelia de démarrer, donc **tout le
   monde** de se connecter. C'est le seul geste de la liste dont l'oubli fait tomber le
   service.
5. Redémarrer le conteneur, puis **accorder les accès dans l'application**.

Trois points qui ne se devinent pas : **une adresse par personne, jamais une adresse
d'équipe** (qui lit cette boîte peut réinitialiser le mot de passe puis réenrôler la 2FA) ;
le groupe `bd-admins` voit tout le corpus, à donner en connaissance de cause ; et pour une
arrivée nombreuse, poser un mot de passe **aléatoire non transmis** et laisser chacun passer
par « mot de passe oublié ».

### Créer un groupe

Il n'y a rien à créer. Un groupe **existe** dès qu'un compte le porte dans le fichier des
comptes ; l'application le découvre en le lisant dans les en-têtes. Côté application, il
suffit de le nommer dans le panneau *👥 Collections*, en choisissant le genre **groupe**
plutôt qu'utilisateur — le genre est demandé explicitement parce qu'un login et un groupe
peuvent porter le même nom, et qu'une ambiguïté silencieuse sur un contrôle d'accès n'est pas
une hypothèse qu'on se permet.

---

## 7. Questions fréquentes

**Je me connecte et je ne vois rien. C'est cassé ?**
Pas forcément. Lisez le bandeau : il distingue trois situations (§3). S'il nomme vos groupes,
tout fonctionne — il manque seulement qu'un propriétaire vous donne accès à une collection.
S'il n'en nomme aucun, c'est une panne de configuration côté serveur.

**J'ai donné un accès et la personne ne voit toujours rien.**
Vérifiez l'orthographe du login ou du nom de groupe. L'application n'a aucun annuaire : un nom
mal écrit est accepté sans broncher et n'ouvre rien. Vérifiez aussi le **genre** — un accès
déclaré « utilisateur » ne s'applique pas à un groupe du même nom.

**Pourquoi un album que je sais exister me répond « introuvable » ?**
Parce que répondre « interdit » révélerait sa présence, donc la composition du corpus. C'est
délibéré (§3).

**Je peux annoter mais pas partager la collection. Pourquoi ?**
Vous avez le niveau *écriture*. Décider qui entre est le niveau *propriétaire* : écrire, c'est
annoter ; posséder, c'est décider du cercle.

**Le dernier propriétaire d'une collection est parti.**
Un membre du groupe `bd-admins` peut se rendre propriétaire ou désigner quelqu'un d'autre.
C'est exactement le cas pour lequel ce recours existe.

**Tag ou dimension ?**
Un tag se cherche, un attribut se compte. Si vous voulez un jour un tableau, une comparaison
ou un croisement là-dessus, c'est une dimension.

**J'ai créé une valeur et un collègue ne la voit pas.**
Elle est probablement locale à votre collection — soit parce que vous l'y avez créée, soit
parce que sa dimension ou son domaine l'était (§4, règle 1). Promouvez-la en portée globale
depuis le panneau *📖 Lexique*.

**À quoi sert l'état `provisoire` / `défini` ?**
À dire ce qui est stabilisé. Rien n'est empêché tant qu'un terme est provisoire : c'est une
information pour les humains qui annotent, et un indicateur dans le « % défini ».

**Ma collection est en `restreint`. Mes collègues peuvent-ils voir les scans ?**
Oui, s'ils ont accès à la collection. Le régime ne borde que la **sortie** — publication IIIF,
dépôt — jamais le travail interne (§5).

**Qui peut télécharger toute la base ?**
Les seuls membres de `bd-admins`. Une sauvegarde est entière par nature — une sauvegarde
partielle ne restaure pas une instance — donc elle change de public plutôt que de contenu.

**Où sont les mots de passe et les groupes dans la base ?**
Nulle part. Aucun secret n'y est stocké, et aucune appartenance de groupe non plus : la table
des utilisateurs n'est qu'un **miroir d'affichage**, et les groupes sont relus dans les
en-têtes à chaque requête.
