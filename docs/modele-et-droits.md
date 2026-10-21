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
PROJET          l'étage au-dessus : il se nomme en haut de chaque page, et l'on en EST
    │           (une collection appartient à UN projet ; en être n'ouvre que sa
    │            collection de BASE, et selon ce que le projet a choisi — cf. §2,
    │            « Au-dessus de la collection : le projet »)
    ▼
COLLECTION      espace de travail ET unité de dépôt ; c'est elle qui PORTE LES ACCÈS
    │           (lien N-N : un album peut vivre dans plusieurs collections ; un album
    │            supprimé de sa dernière collection est GARDÉ AU FONDS — cf. §2)
    ▼
ALBUM           un ouvrage numérisé : titre, paternité, édition, source de numérisation ;
    │           c'est la COPIE DE TRAVAIL d'un DOCUMENT, qui appartient à l'instance
    │           (le FONDS : qui l'a importé, quand, dans quel projet — cf. §2)
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
    ├──▶ LOCUTEUR (bulle, cartouche, texte) ─┐
    ├──▶ PRÉSENCE (boîte personnage) .......─┼──▶ PERSONNAGE   entité de corpus, transverse
    └──▶ SITUATION (case) ..................─┘     │           aux albums (+ alignements
                                                   │           Wikidata / VIAF / IdRef)
                                                   └──▶ VALEURS D'ATTRIBUTS
                                                        (domaine → dimension → valeur)
```

Trois objets ne sont dans aucune boîte, et c'est voulu.

- **Le personnage** est une entité de **corpus**, pas de planche : « Tintin » est le même
  d'un album à l'autre. Une zone de texte — bulle, cartouche ou texte — lui est reliée par
  un **locuteur** (qui parle), une boîte personnage par une **présence** (qui est montré).
  Un locuteur ne s'attribue ni à une case ni à une boîte personnage : la route le refuse,
  une zone de texte qui devient l'une ou l'autre le perd, et Ctrl+Z ne l'y repose pas.
  L'entité est le moyeu où la parole et l'image se rejoignent.
- **Le vocabulaire** (tags, domaines, dimensions, valeurs) vit au niveau du corpus, avec sa
  propre règle de portée — cf. §4.
- **Le journal de provenance** enregistre chaque acte (qui, quoi, avant/après) sans jamais
  être modifié. C'est lui que remonte l'annulation (Ctrl+Z), et il **survit à la suppression**
  de ce qu'il décrit. C'est aussi lui qu'on lit pour savoir si **quelqu'un d'autre** a
  travaillé sur un album, avant de vous laisser le supprimer seul (§2, *Le fonds*). Cf.
  [`provenance-audit.md`](provenance-audit.md) et [`undo.md`](undo.md).

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
| **Espace de travail** | c'est elle qui porte les accès : donner un droit sur une collection le donne sur tous ses albums | *Qui entre*, onglet de la fiche de la collection, dans la Bibliothèque ; et, pour un administrateur, dans la fiche de la collection, *👥 Comptes et groupes* de l'Administration — le même panneau, à deux endroits (cf. *Où vit quoi*, plus bas) |
| **Unité de dépôt** | 1 collection = 1 dépôt Nakala/HAL = 1 DOI ; elle porte licence, base légale, régime de diffusion, responsables scientifiques | fiche de la collection dans la Bibliothèque, onglets *Description* et *Diffusion et dépôt* ; les responsables scientifiques par `tools/gerer_collections.py`, cf. [`export-metadonnees.md`](export-metadonnees.md) |
| **Portée d'appartenance du vocabulaire** | un terme peut être *global* ou *local à une collection* | panneau *📖 Lexique* de l'Exploration |

Trois règles en découlent, qu'il vaut mieux connaître avant de les rencontrer.

- **Un album peut vivre dans plusieurs collections** (lien N-N). Il suit alors les droits de
  chacune : y être admis par l'une suffit — pour le lire, et pour l'annoter si l'on y écrit.
  Le **supprimer** est l'exception, et il a deux sens, décrits plus bas (*Le fonds*) :
  le supprimer **de la collection** ne détruit rien — l'album reste entier pour les autres
  collections, ou il est gardé au fonds —, le supprimer **définitivement** l'efface pour
  tout le monde. Le premier geste se défait par le propriétaire de chacune des collections
  où l'album vit encore, ou par un administrateur : ranger un album, c'est *rejoindre* son
  travail, et cela se consent (§2, *Le fonds*, « Prendre un document »). Qui écrit des deux
  côtés sans posséder le demande ; celui qui n'y écrivait que par cette collection ne le
  voit plus, et ne peut plus rien demander.
- **Un album naît dans une collection** — sauf quand un administrateur l'importe directement
  au fonds (plus bas). Créé sans collection explicite, il entre dans la *Collection par
  défaut*. Ce nom est **réservé** : personne ne peut le donner à une
  collection neuve. Il peut en revanche **sortir de toutes** : il est alors gardé au fonds,
  où aucune collection ne l'ouvre — seul un administrateur le voit.
- **Retirer le dernier propriétaire d'une collection est refusé**, avec un message qui nomme
  la contrainte. Retirer à un album sa dernière collection l'était aussi ; ce ne l'est plus :
  il part au fonds. Reste refusé, en revanche, de **supprimer une collection** qui est la
  dernière de certains de ses albums : le message dit combien, et qu'il faut les ranger
  ailleurs ou les supprimer d'abord de la collection — ils sont alors gardés au fonds.
- **Une collection créée par un administrateur n'a pas de propriétaire.** Elle naît ainsi,
  et les administrateurs la gèrent sans en être propriétaires ; ils peuvent lui en désigner
  un dans *Qui entre* — dans la Bibliothèque, ou dans la fiche de la collection, dans
  l'Administration —, en cochant *décider qui entre* sur sa ligne.

### Au-dessus de la collection : le projet

Depuis le 2026-10-10, toute collection appartient à **un projet**, et à un seul. Le projet
est l'étage au-dessus : le cadre à l'intérieur duquel plusieurs études se côtoient. Son nom
se lit **en haut de chaque page**, et la Bibliothèque montre les collections du projet où
vous travaillez.

**Aujourd'hui, un projet fait quatre choses, et pas une de plus.** Il se **nomme** ; on y
**fait entrer** des comptes ou des groupes, comme *membres* ou comme *responsables* ; l'on
y **crée des collections** ; et il a sa **collection de base**, qu'il ouvre à ses membres
s'il l'a choisi. Ce qu'il ne fait pas se rencontre plus vite que ce qu'il fait, et vaut
d'être su d'avance.

- **Entrer dans un projet n'ouvre aucune de ses collections, hors sa collection de base**
  (ci-dessous). Chacune des autres garde son *Qui entre*. Être membre d'un projet et n'y
  voir aucun album est un état normal : sa base est vide, ou fermée à ses membres, et il
  manque un accès de collection, pas une réparation.
- **Un accès de collection se passe d'être du projet.** Qui lit une collection sans être
  membre de son projet continue de la lire exactement comme avant. Il voit le **nom** du
  projet — sans quoi sa collection ne serait rangée nulle part à l'écran — et rien d'autre :
  ni ses membres, ni ses autres collections.
- **Une collection ne change pas de projet.** Elle naît dans l'un et y reste : aucun geste
  ne la déplace.
- **Ranger un album ne traverse pas les projets.** Un album qui vit dans une collection d'un
  projet ne se range pas dans une collection d'un autre ; le refus le dit (« le rangement ne
  traverse pas les projets »). À l'intérieur d'un même projet, rien n'a changé : un album
  peut toujours vivre dans plusieurs de ses collections.
- **La Recherche et l'Exploration ne s'arrêtent pas au projet.** Elles portent toujours sur
  tout ce que vous lisez, tous projets confondus ; seule la liste des collections de la
  Bibliothèque suit le projet choisi.
- **Le projet ne sort dans aucun export.** La collection reste l'unité de dépôt et le titre
  d'un export ; ni le nom d'un projet, ni ses membres, ni sa justification ne quittent
  l'instance.

**La collection de base** (depuis le 2026-10-17). Tout projet naît avec **une**
collection, qui porte d'abord son nom : sa collection de base. C'est là qu'arrivera ce que
le projet prend au fonds, et c'est elle que l'import proposera d'abord — on peut travailler
dans un projet avant d'avoir pensé ses collections. Elle se renomme ; elle ne se supprime
pas, et ne change pas de projet : elle part avec lui, s'il est supprimé vide.

- **Ses responsables en sont propriétaires**, du seul fait d'être responsables du projet :
  nommer un autre responsable lui en donne la propriété, rétrograder quelqu'un la lui
  retire. Aucune ligne de *Qui entre* n'est écrite pour cela.
- **Ses membres y entrent selon ce que le projet a choisi** : en **écriture** (« ouverte »,
  le choix par défaut à la création), en **lecture** — les membres voient le corpus et
  travaillent dans leurs propres collections, puisqu'annoter un album ne demande d'écrire
  que dans l'une de ses collections —, ou **pas du tout** (« protégée » : ses propriétaires
  seuls, et qui ils font entrer par *Qui entre*). Ce choix se fait à la création du projet
  et se change ensuite par qui règle le projet ; le resserrer n'efface aucun travail —
  ceux qui ne la voient plus ne voient plus ce qu'ils y ont fait, qui reste.
- **Ces accès se voient là où l'on regarde qui entre.** *Qui entre* d'une collection de
  base se lit en deux groupes : *Par le projet* — ses responsables, propriétaires, et ses
  membres selon le choix du projet —, puis *Entrés ici*, ceux qu'on y a fait entrer à la
  main. Les premiers ne se règlent pas ligne à ligne : *Régler dans le projet ↗* mène à la
  fiche du projet. Ils comptent comme propriétaires : la dernière personne entrée ici comme
  propriétaire peut sortir tant que le projet a un responsable. *Comptes et groupes* les
  montre aussi, « par le projet ».
- **Qui sort du projet sort de sa base** — qu'il soit un compte ou un groupe —, et ne
  perd rien d'autre : un accès donné dans *Qui entre*, sur la base comme sur toute autre
  collection, reste.
- **Le jour où une instance reçoit la collection de base, rien ne s'ouvre** : chaque projet
  existant — le projet de repli compris — en reçoit une **neuve, vide et protégée**. Aucune
  collection existante ne devient une base : la « Collection par défaut », où tombent les
  albums créés sans collection, reste ce qu'elle était. Une mise à jour ne donne d'accès à
  personne sans qu'on l'ait décidé ; seuls les responsables d'un projet deviennent
  propriétaires de sa base neuve, vide.
- **Ce qu'on reçoit par la base est un accès comme un autre**, avec tout ce qui s'y lit.
  Un membre d'une base **ouverte en écriture** écrit quelque part : il peut donc enrichir
  le vocabulaire commun à toute l'instance, et ouvrir la mesure de l'accord entre
  annotateurs sur les albums de la base — ce que, jusque-là, être membre d'un projet ne
  donnait pas. Et un responsable, propriétaire de la base, y peut tout ce que peut un
  propriétaire : la décrire, régler sa diffusion et son référent, faire entrer d'autres
  personnes, l'exporter, la déposer sur ShareDocs.

**Le projet de repli.** Tout ce qui existait avant cette date a été rangé, sans rien y
changer, dans un premier projet. Il est né sous le nom « Projet principal » et il est fait
pour être renommé : ce n'est pas son nom qui le désigne, c'est son rôle. C'est le **projet
de repli** — une collection créée sans dire dans quel projet y entre. Il se renomme ; il ne
se supprime pas. Le jour où une instance reçoit les projets, tous ceux — comptes et
groupes — qui avaient un accès à une collection en deviennent **membres**, et personne
n'est désigné responsable : c'est un choix, que la mise à jour ne devine pas. C'est une
photographie de ce jour-là : recevoir plus tard un accès à une collection ne fait pas entrer
dans son projet.

**La justification.** Un projet peut porter un texte qui dit **pourquoi il existe** — sa
justification, scientifique d'abord. Elle se saisit à sa création, et se corrige ensuite
dans sa fiche — *Ce projet*, champ *Pourquoi ce projet existe* — par un administrateur,
comme sa description. Elle se lit dans cette fiche, par ses responsables et par les
administrateurs ; un simple membre ne la reçoit pas.

**Le nom d'un projet est court, et c'est une contrainte d'écran.** Il se lit dans la bande
du haut de chaque page, où il ne se coupe pas — ni points de suspension, ni retour à la
ligne. Le plafond a donc été fixé en mesurant cette bande sur un écran étroit, à grande
police ; l'écran de création l'annonce sous le champ, et un nom trop long est refusé par un
message qui donne le plafond et la longueur du nom proposé. Deux projets ne portent pas le
même nom, sans égard aux majuscules.

### Le fonds : sous la collection, ce que l'instance détient

**Tout album est la copie de travail d'un document, et le document appartient à
l'instance.** Ce qu'on importe ne vous appartient pas, ni à votre collection : c'est
l'instance qui le détient. Les collections l'**emploient** ; une collection qui ne veut plus
d'un album s'en défait, mais ne le détruit pas pour autant. L'ensemble de ces documents est
le **fonds** — y compris ceux qu'aucune collection n'appelle plus.

**Un document a une origine écrite** : qui l'a importé, quand, et dans quel projet d'abord
— dont le **nom** est gardé tel qu'il était à l'import, pour qu'il se lise encore si le
projet est un jour supprimé ou renommé (pour un album d'avant le 2026-10-17, c'est le nom
que le projet portait ce jour-là).
Cela s'écrit depuis la mise à jour qui a introduit le fonds. Pour un album créé avant, la
date et le projet sont connus, **pas l'importateur** : rien ne l'avait noté, et l'application
ne le devine pas. En usage sur un seul poste, sans portail d'identité, l'importateur n'est
pas écrit non plus — il n'y a personne à nommer.

**« Supprimer » a deux réponses, et elles ne font pas la même chose.**

- **Supprimer de la collection** ne détruit rien. C'est le geste de quiconque écrit dans la
  collection, qu'il ait importé l'album ou non. Le travail reste là où l'album vit encore.
  Si c'était sa **dernière** collection, l'album est **gardé au fonds**, avec tout son
  travail : plus personne ne le voit, sauf les administrateurs, qui peuvent le **rendre** à
  une collection — de son projet seulement : un album garde le projet où il vivait, et ne
  passe pas dans un autre en revenant. Le geste ne s'annule pas, et le propriétaire de la
  collection ne peut pas reprendre l'album lui-même : le responsable du projet le demande à
  un administrateur, depuis la fiche du projet (cf. plus bas, *se reprend*).
- **Supprimer définitivement** efface les images et tout le travail fait dessus, pour tout
  le monde, dans tous les projets. Il efface **sans rien demander** à quatre conditions,
  toutes nécessaires : écrire dans **toutes** les collections de l'album ; l'avoir
  **importé** vous-même — plus exactement, avoir créé cette copie de travail, ce qui
  revient au même tant qu'un document n'en a qu'une ; ne pas travailler sous un **compte
  partagé** (un login commun à
  plusieurs personnes : « celui qui l'a importé » n'y désigne personne) ; et que **personne
  d'autre n'y ait travaillé**. C'est le cas de l'import par erreur, qui n'a à attendre
  personne. Hors de ce cas, la suppression **se demande** à un administrateur.

**« Personne d'autre n'y a travaillé »** se lit dans le journal de l'instance, sur ce qui
existe encore. Compte comme travail tout geste d'une autre personne sur l'album : dessiner
ou modifier une case ou une bulle, transcrire, annoter (note, tags), poser un locuteur, une
présence ou un attribut de case, corriger la grammaire, valider une planche, ajouter ou
retirer une planche, modifier la notice ou la paternité, forcer le statut de relecture.
Ne comptent pas : un travail supprimé depuis ; une passe automatique, même lancée par un
collègue — elle est attribuée à son moteur, pas à une personne ; ranger l'album dans une
collection ; déposer une demande. Un geste dont l'auteur n'est pas écrit compte comme celui
d'un autre : on ne sait pas que c'est vous. Et un album d'avant le fonds, dont
l'importateur n'est pas écrit, **se demande toujours** — seul un administrateur le détruit.

**Une demande dit pourquoi, et se certifie.** On la dépose depuis un album où l'on écrit, par
*Supprimer…* puis *Supprimer définitivement*. Le motif est obligatoire — c'est ce que
l'administrateur lira pour décider. Et une case l'est aussi : supprimer définitivement
détruit tout ce qui a été posé sur les planches — découpage, transcription, annotations,
métadonnées —, que d'autres utilisent peut-être dans le projet ou dans ses collections ; on
certifie que ces données ne sont pas importantes, et la date de cette certification est
gardée. La même suppression ne se demande pas deux fois tant qu'elle attend, et ne se demande
pas quand on peut la faire soi-même : les deux refus le disent.

**L'administrateur répond** *Détruire* — l'album, ses images et son travail disparaissent —
ou *Garder* : rien n'est effacé, la demande est close, et l'on peut la redéposer ;
l'administrateur verra alors qu'elle a déjà été refusée. *Garder* répond à une demande : il
ne protège pas l'album de qui l'a importé, si les quatre conditions tiennent toujours. Une
demande ne se retire pas. Il n'y a pas de messagerie : la demande est un état, qui se lit
sur la ligne de l'album et dans l'Administration.

**Qui voit quoi d'une demande.**

| Ce qu'on lit | qui lit l'album | qui a demandé | administrateur |
|---|:---:|:---:|:---:|
| qu'une suppression est demandée (*suppression demandée*, sur la ligne de l'album) | ✅ | ✅ | ✅ |
| **qui** l'a demandée | — | ✅ (*par vous*) | ✅ |
| le motif, la certification | — | — | ✅ |
| qui a importé l'album, et ce que d'**autres** y ont fait | — | — | ✅ |

Le nom de qui demande n'est pas montré aux autres lecteurs, et c'est une question de
cloisonnement : un album peut vivre dans plusieurs collections, et quelqu'un qui n'écrit que
dans l'une aurait sinon été nommé aux lecteurs de l'autre. Ce que l'administrateur lit du
travail des autres, sous une demande, est ce que la règle a lu : qui, combien de gestes de
chaque sorte, la date du dernier. Ce sont des **gestes** lus dans le journal — un geste défait
depuis compte encore —, pas ce qui reste sur les planches ; et derrière un compte partagé,
une ligne peut être le travail de plusieurs personnes, ce que l'écran rappelle.

**Une planche suit la règle de l'album**, sans demande à elle : on la supprime là où l'on
supprimerait l'album sans rien demander. Ailleurs, sa corbeille dit de s'adresser à un
administrateur.

**Un projet se demande aussi** : son responsable, qui ne le supprime pas lui-même, en demande
la suppression avec un motif — sans certification, puisqu'un projet ne se supprime que vide.
L'administrateur le supprime, si le projet est bien vide, ou le garde.

**Ce que l'administrateur fait du fonds**, dans le bloc *🗄️ Le fonds* de l'Administration :
répondre aux demandes ; **rendre** une copie gardée ; **détruire** un album qu'aucune
collection n'appelle ; et **importer au fonds** — un album qui naît sans collection ni
projet, « appelé par personne », pour être distribué ensuite : il prend le projet de la
première collection où on le range.

**Prendre un document.** Les règles ci-dessous existent côté serveur. L'Administration
les montre depuis l'écran de la 3a : « À faire » rend toutes les demandes, chacune avec ses
mots et ses boutons — une entrée se répond document par document, un rejoindre par
« Accepter : ranger aussi dans … », un retour par « Rendre à … » ou « Garder au fonds » ;
seule une suppression de document se répond par « Détruire » —, et la fiche d'un projet
dit ses demandes au fonds et leur état. La Bibliothèque les offre : « + Prendre du
fonds… » au responsable et à l'administrateur, « + Prendre dans le projet… » à qui écrit
dans la collection, les cases de « Sur les collections » dans la fiche d'un album, et les
demandes de rejoindre reçues dans l'onglet *Albums* de la collection de leur propriétaire
(cf. [`guide-utilisateur.md`](guide-utilisateur.md) §4, *Bibliothèque*).

Un document du fonds peut entrer dans une collection, de deux façons, et dans plusieurs
projets à la fois : chaque projet qui le prend en a sa COPIE de travail, une *sœur* des
autres.

- **Partir de zéro** : une copie vierge — la notice et la paternité recopiées, puis libres
  de diverger ; les mêmes images, sans rien dupliquer ; aucun travail. Elle naît dans le
  projet de la collection qui la prend. Qui lit déjà une copie du document dans le projet
  la prend sans rien demander. Sinon, c'est au **responsable** du projet de la demander : il
  parcourt les *notices* du fonds — titre, série, auteur, et rien d'autre : ni qui l'a
  importé, ni qui l'emploie —, coche plusieurs documents et les demande pour une collection
  de son projet, motif à l'appui ; sans nommer de collection, ils arrivent dans la
  collection de base. Un administrateur répond document par document, ou accepte tout ; la
  demande dit ensuite *acceptée*, *refusée* ou *acceptée en partie*, ce que le serveur rend
  à son responsable. La copie accordée est alors celle de qui l'a demandée : il la supprime
  lui-même s'il en a besoin, comme une copie qu'il aurait prise. On ne part de zéro que
  depuis une copie du même projet : qui en lit une ailleurs passe par la demande du
  responsable. Un administrateur prend directement.
- **Rejoindre** le travail d'une autre collection du projet — ranger ici une copie qu'on
  lit : cocher sa collection dans « Sur les collections ». C'est partager ce travail : la décision de qui le
  tient. Immédiat si vous possédez chacune des collections où la copie vit ; sinon une
  demande à leur propriétaire, qui la reçoit avec votre nom et celui de la collection
  d'arrivée, et l'accepte ou la refuse. Quand aucun propriétaire ne tient toutes ces
  collections — l'une n'en a pas, ou elles en ont de différents —, c'est un administrateur
  qui répond, et la réponse à votre geste le dit. Rejoindre ne traverse jamais deux projets.
  Une demande qui visait une copie détruite depuis se clôt avec elle.

Une copie gardée au fonds se **reprend** : son responsable la voit dans la fiche du projet
(*Copies gardées au fonds*) et *Demande à la rendre* à une collection du projet où il écrit
— la base, d'abord. C'est une demande à part, une par copie, à laquelle un administrateur
répond *Rendre à …* (la copie revient, avec tout son travail) ou *Garder au fonds* — en
lisant de quelle collection elle était sortie, quand c'est écrit. Elle ne s'attend qu'une
fois par copie, et se clôt d'elle-même si la copie est détruite, ou rendue autrement : elle
dit alors où la copie est réellement revenue. Une demande de **rejoindre** qui visait une
copie partie ensuite au fonds se clôt, refusée : la reprendre passe par le responsable. Une copie qui a une sœur se supprime
seule : ses images restent tant qu'une sœur les emploie, et le document part avec sa
dernière copie. « Supprimer… » le dit à qui écrit dans la copie — *Ses images restent* —,
sans dire où vit la sœur ni laquelle : la liste des albums ne porte qu'un oui ou non
(`soeur`), et une lectrice ne le reçoit jamais.

**Accepté : l'adresse d'une image dit d'où vient la copie.** Une copie sœur ne duplique pas
les images : ses planches désignent les fichiers de la copie dont elle a été tirée, rangés
dans le dossier de celle-ci. L'adresse d'une image (`chemin_web`, `chemin_tiff` dans
`GET /api/albums/{id}/planches`, de la forme `corpus/album_<source>/…`) porte donc
l'identifiant de dossier de la copie SOURCE : qui lit la sœur apprend que le document a ou a
eu une copie ailleurs, et son identifiant — jamais son projet, sa collection, ni ce qu'on y
a fait. C'est le prix des fichiers partagés (décision D6), accepté jusqu'à `IMG-2`, qui
nommera les fichiers par image et non plus par album.

**Ce que le fonds ne fait pas encore.** Partir du travail d'une autre copie — son découpage,
sa transcription, ses annotations — viendra plus tard. Et l'administrateur, comme l'usage
sur un seul poste, lit encore dans la Recherche et l'Exploration le texte d'un album gardé
au fonds — et deux fois le texte d'un document dont il lit deux copies : ces deux pages
portent sur tout ce qu'il lit, et il lit tout. Ce double compte vaut pour quiconque lit deux
copies d'un même document — une copie vierge prise dans le même projet, par exemple —, jusqu'à
la tranche 4.

---

## 3. Qui peut quoi

### L'application n'authentifie personne

C'est le point le plus contre-intuitif, et il explique tout le reste. BéDéditeur ne
demande jamais de mot de passe et ne stocke aucun secret. En production, c'est
**Authelia** — un portail placé devant l'application — qui vérifie l'identité et la double
authentification, puis transmet à l'application trois en-têtes : qui vous êtes, votre nom
lisible, et vos groupes.

**Trois actes, trois endroits, et il faut les tenir séparés.** *Authentifier*, c'est
Authelia : lui seul dit QUI frappe, et l'application le croit sur parole. *Autoriser*, c'est
l'application : elle tranche sur les groupes que le portail lui transmet, à chaque requête,
et rien d'autre n'entre dans cette décision. *Lire l'annuaire* est un troisième acte, et il
est récent : l'application LIT désormais les comptes et les groupes qui existent, pour
COMPOSER la vue *👥 Comptes et groupes* et pour vérifier un nom qu'on lui tape — jamais pour
authentifier, jamais pour autoriser. Aucun accès ne change selon ce que l'annuaire répond, et
une panne de lecture ne ferme rien : elle dit qu'elle n'a pas pu vérifier. Lire, ce n'est donc
ni authentifier ni décider ; c'est montrer ce qui existe pour qu'on n'ait plus à le deviner.

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
| **Créer** une collection — hors du projet de repli, il faut être membre du projet (cf. « Le projet », plus bas) | ✅ | ✅ | ✅ | ✅ |
| Voir les albums, planches, régions, annotations | ✅ | ✅ | ✅ | ✅ |
| Chercher, explorer le contenu | ✅ | ✅ | ✅ | ✅ |
| **Exporter** le contenu — un album (JSON-LD / CSV / TEI), les CSV de la Recherche et de l'Exploration, les figures, les exports de dépôt | avec la case | avec la case | ✅ | ✅ |
| Transcrire, corriger le découpage, annoter, relire la grammaire | — | ✅ | ✅ | ✅ |
| Lancer les passes automatiques (cases, bulles, OCR) | — | ✅ | ✅ | ✅ |
| Créer et documenter du vocabulaire local à la collection | — | ✅ | ✅ | ✅ |
| **Supprimer un album de la collection** — même la dernière : il est alors gardé au fonds | — | ✅ | ✅ | ✅ |
| **Supprimer définitivement** un album ou une planche sans rien demander — à condition de l'avoir importé, que personne d'autre n'y ait travaillé, d'écrire dans *toutes* ses collections, et de ne pas être sous un compte partagé (§2, *Le fonds*) | — | ✅ | ✅ | ✅ |
| **Demander** la suppression définitive d'un album, motif et certification à l'appui | — | ✅ | ✅ | — (il la fait) |
| **Rejoindre** le travail d'une autre collection du projet (cocher dans « Sur les collections ») sans rien demander — à condition de posséder *chacune* des collections où il vit ; sinon le demander | — | demander | ✅ (les siennes) | ✅ |
| **Répondre** à une demande de rejoindre une copie de sa collection | — | — | ✅ (s'il possède toutes les collections de la copie) | ✅ |
| Tenir le **fonds** : le voir, répondre aux demandes, rendre une copie gardée, importer au fonds | — | — | — | ✅ |
| Consulter le rapport d'accord **inter-annotateurs** (*👥 Inter*) | — | ✅ | ✅ | ✅ |
| Accorder et retirer les accès de la collection | — | — | ✅ | ✅ |
| Renommer, supprimer la collection, désigner son référent | — | — | ✅ | ✅ |
| Modifier licence, base légale, régime de diffusion, embargo | — | — | ✅ | ✅ |
| Télécharger la sauvegarde complète de la base | — | — | — | ✅ |
| Couper ou remplacer la session ShareDocs **d'instance** | — | — | — | ✅ |

**Écrire n'est pas administrer, et la distinction est délibérée** : annoter, c'est travailler ;
décider qui d'autre entrera, c'est autre chose. Un membre en écriture n'hérite pas du droit
d'élargir le cercle.

**Exporter est une case, pas un niveau** (depuis le 2026-09-11). Voir un contenu n'est pas
l'emporter : un fichier qui quitte l'instance part vers un poste qu'elle ne contrôle plus.
Le propriétaire coche donc, pour chaque accès de sa collection, s'il peut **exporter** —
quel que soit son niveau : un stagiaire en écriture annote sans pouvoir sortir le texte,
un relecteur en lecture peut recevoir la case. Un propriétaire exporte d'office.

- Un export qui porte sur **plusieurs** collections — la Recherche, l'Exploration —
  n'emporte que celles où vous avez la case : l'écran peut montrer plus que le fichier.
- Un album rangé dans plusieurs collections sort **au titre de l'une d'elles**, où vous
  avez la case ; si vous l'avez sur plusieurs, il faut dire laquelle, et l'export le dit.
  Cela vaut pour tout le monde depuis le 2026-10-07, administrateur et mono-poste compris.
- Cet export d'album (JSON-LD, CSV, TEI) ne porte que **le vocabulaire de cette
  collection et le vocabulaire global** — **quel que soit qui exporte** (décidé le
  2026-10-07). Un tag propre à une autre collection, posé sur une région de l'album, n'y
  figure pas, même si vous avez aussi le droit d'exporter l'autre : la région sort, avec sa
  note et ses autres tags, sans celui-là. C'est la règle des exports de dépôt (§ Le vocabulaire).
- Sans la case, l'export est **refusé en le disant**, jamais rendu vide.

Une seule mesure d'analyse est **réservée**, et c'est l'accord inter-annotateurs : toutes les
autres portent sur le corpus, celle-ci porte sur des **personnes** — elle nomme, apparie et
cite à la ligne près. La règle est que *ceux qui voient la mesure sont ceux qu'elle mesure*,
d'où le niveau écriture. Au dépôt, la fiche ne garde que le nombre d'auteurs et des paires
sans identités : « relu à plusieurs, accord 0,87 » ne demande aucun nom.

Une autre lecture porte sur des personnes, et **elle ne suit pas cette règle** — c'est une
décision du 2026-10-15. Sous une demande de suppression, l'**administrateur** voit qui a
travaillé sur l'album et combien de gestes chacun y a laissés, pour savoir qui perdrait son
travail avant de détruire. Ceux qu'elle compte ne la voient pas ; elle ne sert qu'à répondre
à la demande, et ne sort de l'instance par aucun export (§2, *Le fonds*).

Les administrateurs suppriment définitivement **sans condition** : c'est le recours d'une
demande, et c'est eux qui y répondent.

**Un groupe peut posséder une collection**, et c'est souvent le bon choix : un espace de
travail survit rarement au départ d'une personne.

**Créer une collection ne demande aucun droit — seulement une identité**, et son créateur en
devient propriétaire. Refuser la création à qui n'a encore rien rendrait l'application
inutilisable au premier jour de chacun. Deux cas ne posent pas de propriétaire, et c'est
normal : en mono-poste, il n'y a personne à inscrire ; pour un administrateur, qui possède
déjà tout, un lien personnel avec chaque collection créée fausserait la notion — s'il la veut,
il se l'accorde.

**« Seulement une identité » vaut pour le projet de repli** (précisé le 2026-10-10). Une
collection naît dans le projet où vous travaillez. Dans le projet de repli, rien n'a
changé : être connecté suffit. Dans un **autre** projet, il faut en être **membre** — le
refus le dit (« Créer une collection dans ce projet demande d'en être membre »), et il
arrive à qui voit le nom du projet par une collection qu'il lit, sans en être.

### Le projet : en être, le régler, en décider

Un projet (§2) a deux **rôles**, et l'instance deux **pouvoirs** qui ne se confondent pas.

| Geste | simple membre | responsable du projet | `bd-admins` |
|---|:---:|:---:|:---:|
| Lire le nom du projet, en haut de chaque page | ✅ | ✅ | ✅ |
| **Créer une collection** dans le projet | ✅ | ✅ | ✅ |
| Lire ou annoter la **collection de base** du projet | selon le choix du projet (écriture, lecture, ou rien) | ✅ (propriétaire) | ✅ |
| Lire ou annoter une **autre** collection du projet | par un accès de collection | par un accès de collection | ✅ |
| **Régler** ce que les membres peuvent dans la collection de base | — | ✅ | ✅ |
| Voir **qui est** du projet | — | ✅ | ✅ |
| **Faire entrer**, faire sortir, nommer un autre responsable | — | ✅ | ✅ |
| Lire la **justification** du projet | — | ✅ | ✅ |
| **Demander** la suppression du projet, avec un motif | — | ✅ | — (il la fait) |
| **Créer**, **renommer**, **supprimer** un projet | — | — | ✅ |

- **Membre ou responsable.** On fait entrer un **compte** ou un **groupe**, comme pour un
  accès de collection, et la même règle vaut : ce qui est enregistré est un nom, jamais une
  appartenance vérifiée. On entre toujours **membre** ; nommer quelqu'un *responsable du
  projet* est un second geste, sur sa ligne. Un responsable est aussi membre.
- **Régler n'est pas décider.** Le responsable règle **qui entre** dans son projet. Il ne
  décide ni de son nom ni de son existence : créer, renommer et supprimer un projet
  reviennent aux administrateurs de l'instance — le nom d'un projet se lit sur l'écran de
  tous ceux qui y travaillent. Le responsable en **demande** la suppression, dans la fiche
  du projet, et un administrateur y répond (§2, *Le fonds*). En mono-poste, où l'on est
  seul, on fait tout.
- **La liste des membres n'est pas publique dans le projet.** C'est une donnée sur des
  personnes : un simple membre ne voit pas qui d'autre en est, ni qui en répond.
- **Les administrateurs règlent tout projet sans figurer parmi ses membres**, et *Qui y
  entre* le déclare sous la liste, comme *Qui entre* le fait pour une collection.
- **Faire sortir quelqu'un ne lui retire aucun accès de collection donné dans *Qui
  entre***, et ne détruit rien : son travail lui reste attribué. Il ne sort que de la
  collection de base, où il n'entrait que par le projet.

Cinq refus se **nomment**, pour la raison qui vaut déjà pour les collections — ce n'est pas
un droit qui manque, c'est un état que le geste fabriquerait.

- *Le dernier responsable d'un projet* ne se retire pas et ne se rétrograde pas : il faut
  en désigner un autre d'abord. Un projet peut en revanche **naître** sans responsable —
  seuls les administrateurs le règlent alors, jusqu'à ce qu'ils en nomment un.
- *Le projet de repli* ne se supprime pas : c'est là qu'entre une collection qui ne nomme
  aucun projet.
- *Un projet qui porte encore une collection* ne se supprime pas : un projet ne se supprime
  que vide. Sa collection de base ne compte pas tant qu'elle est vide — elle part avec lui ;
  si elle porte un album, ou du vocabulaire qui lui est propre — que sa suppression rendrait
  visible de toute l'instance —, le refus le dit.
- *La collection de base* ne se supprime pas seule : elle part avec son projet.
- *Un projet dont des albums sont gardés au fonds* ne se supprime pas non plus : un album
  gardé emporte son projet, et le supprimer le laisserait désigner un projet qui n'existe
  plus. Il faut d'abord détruire ces albums, depuis le fonds.

Comme une collection ne change pas de projet, qu'une collection ne se supprime pas tant
qu'un album n'a qu'elle (§2), et qu'un album supprimé de ses collections reste au fonds avec
son projet, **un projet où des albums sont entrés ne se vide aujourd'hui qu'en DÉTRUISANT
ces albums**. À savoir avant d'en créer un pour essayer.

### L'administrateur, et pourquoi il est déclaré

Le groupe `bd-admins` lit et écrit **tout le corpus sans figurer dans aucune liste d'accès**.
Ce n'est pas un défaut : c'est la vérité de tout auto-hébergement — qui tient la machine tient
les données. Ce qui serait fautif, c'est que ce pouvoir soit **invisible**. *Qui entre* le
**déclare donc en clair**, sous la liste des accès, en nommant les groupes lus plutôt
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
indistinguable d'un corpus vide.** D'où un bandeau qui distingue **quatre** situations — et
non deux — par ce que le portail transmet :

| Ce qui parvient | Ce que ça signifie | Qui répare |
|---|---|---|
| aucune identité | le portail ne transmet rien : l'application est joignable sans passer par lui | administrateur système |
| une identité, la liste des groupes **non transmise** | le login parvient, la liste des groupes non — mais **sur cette instance, c'est aussi ce que produit un compte sans aucun groupe** (mesuré le 2026-09-09) | à départager avant de réparer |
| une identité, la liste des groupes **transmise et vide** | tout fonctionne : ce compte n'appartient simplement à aucun groupe | un **propriétaire** de collection |
| une identité **et** ses groupes, dont aucun n'a d'accès | tout fonctionne : personne ne vous a encore donné accès | un **propriétaire** de collection |

**Aucune des quatre ne se répare sur la seule foi du bandeau, et la deuxième moins que les
autres.** Cette page a longtemps écrit qu'elle signalait une panne de configuration — le
portail transmettant le login sans les groupes, ce qui rend inopérant tout accès accordé à
un GROUPE. C'était déduit du fonctionnement annoncé d'Authelia, jamais mesuré ici. Mesuré le
2026-09-09, c'est faux sur cette instance : un compte sans aucun groupe ne reçoit pas une
liste vide, il ne reçoit rien. La deuxième situation est donc le cas ORDINAIRE d'un
arrivant, et la troisième ne se produit jamais.

Les deux du milieu se ressemblent — dans les deux cas vous n'avez aucun groupe — et
l'application les a longtemps confondues : elles ne se distinguent qu'à un détail de
protocole, la liste vide n'étant pas la même chose que la liste absente. La DISTINCTION
reste juste et vaut d'être lue ; c'est ce qu'on en concluait qui ne l'était pas. Les
confondre envoie chercher une panne qui n'existe pas, ou fait ignorer celle qui existe — et
cette page en avait fait l'expérience dans le premier sens.

Le bandeau donne d'abord la réponse courte — *pourquoi* l'écran est vide — et **replie le
détail derrière son titre** : ce qu'il faut en faire peut attendre un clic. Il s'ouvre de
lui-même dans le seul cas dont on sache qu'il est une panne : aucune identité ne parvient
alors qu'un proxy est déclaré. Quand une instance a déclaré un **référent global**, c'est ici
qu'il est nommé — et c'est le seul endroit possible, puisqu'une portée vide ne lit aucune
collection, donc aucun référent de collection.

### Un écran peut sembler ouvert et refuser quand on agit

Le serveur distingue finement ce que vous pouvez faire : lire, écrire, administrer, et
plusieurs questions plus étroites sur le vocabulaire. **Le navigateur, lui, n'en reçoit
qu'une** — « puis-je administrer cette collection ? ». Le droit d'**écrire** ne traverse pas.

La conséquence est visible et vaut d'être connue : sur une collection où vous n'avez que la
lecture, les écrans ne se ferment pas. Le panneau d'annotation s'ouvre, les champs
s'affichent, le bouton répond — et **c'est en enregistrant que le refus arrive**. Rien n'est
cassé ; personne ne vous a menti ; l'interface ne savait simplement pas quoi masquer.

Quelques gestes font exception, parce que le serveur les dit album par album et
collection par collection : dans la Bibliothèque, *Supprimer…* n'est offert que sur un album
où vous écrivez, et sa réponse *Supprimer définitivement* dit d'avance si elle effacera ou si
elle enverra une demande ; la fiche d'une collection dit vos droits **en actes** (*lire*,
*annoter et organiser*, *exporter*, *décider qui entre*). **Ce que vous pouvez faire d'un
album est l'union de ce que vous pouvez faire dans ses collections** : écrire dans une seule
suffit à l'annoter, quelle que soit la collection par laquelle vous l'avez ouvert — la fiche
d'un album ne le réduit pas aux droits de la collection d'où vous venez. Les onglets d'une
fiche ne sont jamais fermés : c'est le bloc qui dit ce qui manque (*Exporter : droit
manquant*).

C'est un compromis assumé, et il tient parce que **la garde est du côté du serveur**. Un
bouton visible n'accorde rien : l'acte est vérifié quand il est demandé, jamais quand il est
affiché. Le prix se paie en confort, pas en sécurité — un refus tardif plutôt qu'un bouton
absent.

Le revers concerne qui fabrique l'application plus que qui l'utilise, mais il explique une
famille de bogues : **tout ce qu'on ajoute dans un panneau déjà gardé hérite de cette garde
par défaut, et non par décision.** C'est ainsi que le référent — une simple adresse, décrite
plus bas — s'est retrouvé derrière la garde du *partage*, donc lisible du seul propriétaire :
celui qui venait de l'écrire. L'erreur échoue en se **fermant**, ne casse aucun test, et une
revue de sécurité l'approuve. La règle écrite dans `CLAUDE.md` (§ AUTH-2) est qu'une garde
d'interface se pose sur l'**acte**, jamais sur l'écran qui le contient.

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
| Où on l'écrit | panneau *Tags* de l'Atelier | panneaux *Personnage* et *Situation (scène)* de l'Atelier |
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
   **nom de l'axe**, c'est-à-dire une grille d'analyse. **Rattacher une dimension à un domaine
   ne change jamais sa portée** (décidé le 2026-09-24 ; avant, elle descendait avec lui, ou
   devenait globale sous un domaine global) : sous un domaine global ou de sa collection, le
   rattachement passe ; sous un domaine propre à une autre collection, il est refusé, et
   l'écran dit de ranger d'abord la dimension dans la collection du domaine (menu *Portée*).
   L'en **détacher ne la promeut pas** non plus, parce que ranger n'est pas publier. Et
   **ranger un terme dans une collection ne le sépare pas de ses termes liés** (décidé le
   2026-09-25) : c'est refusé si son parent, ou un terme qui en dépend, est propre à une
   autre collection — l'écran dit lequel, s'il vous est lisible. Un parent global convient,
   et les termes globaux qui en dépendent suivent. Ranger la **racine** d'une branche (un
   terme sans parent local) d'une collection à une autre **emporte** ses termes restés dans
   l'ancienne, d'un seul geste (décidé le même jour) ; un terme d'une troisième collection
   la retient toujours.
2. **Le vocabulaire ne suit pas la même règle que les données.** Vous voyez un terme s'il est
   global **ou** local à une collection que vous lisez. En revanche ses **compteurs**
   (fréquences, usages) sont filtrés comme des données : un nuage de tags doit refléter le
   sous-corpus qu'on regarde, pas le corpus entier.

**Voir n'est pas modifier.** Un terme *local* se modifie si vous écrivez dans **sa**
collection ; un terme *global* se modifie si vous écrivez **quelque part**. Un refus de
modification sur un terme est un **403** — il vient d'être listé, un 404 mentirait.

**Voir n'est pas non plus ce qui SORT, et il y a deux règles de sortie** (mis au vrai le
2026-10-07).

- **Ce qui sort au titre d'UNE collection suit la collection, pas la personne.** Les exports
  de dépôt (depuis le 2026-09-23) et l'export d'un album en JSON-LD, CSV ou TEI (depuis le
  2026-10-07) ne portent que le vocabulaire *global* et celui *propre à cette collection*.
  Deux personnes qui exportent le même album au titre de la même collection obtiennent le
  même fichier — un propriétaire de cette seule collection, un propriétaire de plusieurs,
  un administrateur. Avant cette date, l'export d'album suivait ce que la personne avait le
  droit d'exporter : le même fichier, étiqueté A, portait un tag propre à B pour qui
  exportait aussi B. Ce n'était pas un accès indu ; c'était un fichier qui variait selon
  qui cliquait, sous une étiquette qui ne variait pas.
  Une région dont le **seul** tag est propre à une autre collection, et qui n'a pas de note,
  sort sans être dite annotée : il n'en reste rien à montrer. Les données de l'album —
  régions, texte, notes — sortent toujours entières.
- **Ce qui traverse plusieurs collections suit la personne.** Les CSV de la Recherche et de
  l'Exploration ne sortent au titre d'aucune collection : leur vocabulaire est celui des
  collections que **vous** avez le droit d'exporter, même quand vous les filtrez sur un seul
  album. Deux personnes n'y obtiennent donc pas forcément le même fichier, et c'est voulu.

**Aucun album ne sort sans titre** (décidé le 2026-10-07). S'il n'y a qu'une collection
au titre de laquelle **vous** pouvez l'exporter, il sort au titre de celle-là sans qu'on ait
à la nommer — même rangé ailleurs aussi, dans une collection où vous n'avez pas le droit
d'exporter. S'il y en a plusieurs, il faut dire laquelle — y compris pour un administrateur
et en mono-poste, qui en étaient dispensés jusque-là : la demande est refusée (422) en
nommant les collections possibles. Un album rangé dans **aucune** collection — l'invariant
l'interdit, seule une base retouchée à la main le produit — ne sort pas : la demande est
refusée (409) en le disant.
L'Atelier le fait pour vous : il nomme la collection, ou vous la demande. Chaque format dit
son titre : le JSON dans `exporte_au_titre_de`, le CSV et le TEI dans leur nom
(`album_<id>_c<N>.csv`, `album_<id>_c<N>_tei.xml`), et le TEI dans son bloc `availability`
(« Exporté au titre de la collection … »).

**Une limite connue, et assumée : l'index plein texte.** La Recherche interroge un index qui
agrège le dialogue, la note **et les tags** d'une région. Les tags y sont indexés tous, sans
distinction de portée : un mot tapé dans le champ de recherche peut donc faire sortir une
région **parce qu'elle porte un tag que vous ne lisez pas**, sans que ce tag vous soit jamais
montré. Décision du 2026-09-24 : on garde l'index tel quel, et on écrit la limite.

Ce que la mesure dit exactement, parce que c'est elle qui rend la décision tenable (mesuré le
2026-09-23, revérifié le 2026-09-24) :

- c'est un canal de **confirmation**, pas d'énumération. Il faut **déjà connaître le mot** —
  rien ne le donne — et il n'en revient qu'un bit : « oui, une de vos régions porte ce mot » ;
- il ne porte que sur des régions **que vous lisez déjà**. Cherché sur une région hors de
  votre portée, le même mot ne rend **rien** : le cloisonnement des données tient ;
- **le libellé n'est jamais rendu.** Le résultat sort avec ses tags filtrés comme partout
  ailleurs — c'est-à-dire sans celui-là — et la Recherche ne produit aucun extrait depuis
  l'index. Vous voyez une région qui a répondu, sans savoir à quoi.

**Ce qui rouvrirait la question.** Aujourd'hui les tags sont massivement globaux, et l'oracle
ne porte donc presque sur rien. Si le vocabulaire d'étude naît **local** (chantier `ANN-1`),
la proportion de tags cachés monte et la valeur de ce canal avec elle. Le remède — retirer
les tags de l'index, au profit du seul filtre par tag, qui lui est déjà cloisonné — coûte une
migration de schéma **et une réindexation complète du corpus** : le bon moment est la
**prochaine migration FTS forcée**, pour ne payer la réindexation qu'une fois. Retirer les
tags de l'index ferait aussi mentir la promesse du champ de recherche, qui annonce
« dialogues, notes, tags » ; c'est à réécrire le même jour.

**Une seconde limite assumée : ranger un terme global.** Un terme ne se range pas hors de la
collection de ses dépendants. Ranger dans votre collection un terme **global** qui porte, sous
lui, un terme rangé dans une collection que vous ne lisez pas est donc refusé — et le refus
dit « un terme lié que vous ne lisez pas ». Il vous apprend ainsi qu'**une autre collection a
précisé ce terme** : un bit par terme global, sans nom ni collection, mais la sorte du terme
tu se déduit de la structure (sous une dimension, ce ne peut être qu'une valeur). Quiconque
écrit quelque part peut poser la question. Décision du 2026-09-25 : on garde le refus — le
retirer recréerait un terme séparé de ce qui en dépend — et on écrit la limite. **Ce qui la
fermerait** : que rendre privé un terme partagé demande davantage que d'écrire quelque part,
question ouverte avec le chantier `COL-1`.

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
Depuis l'écran, l'import s'applique avec vos droits : le menu propose les collections où
l'on écrit, et *Global* à quiconque écrit quelque part — un choix lourd, puisque les termes
ainsi créés sont visibles de toute l'instance (sauf sous un parent propre à une collection,
dont un terme neuf hérite de la portée, comme dans l'app). Une ligne qui nomme un terme que vous ne
lisez pas (« libellé déjà pris », sans dire où), qui écrirait sur un terme en lecture
seule pour vous, ou qui rangerait un terme hors de la collection de son parent (« hors de la
collection de son parent ») est refusée entière, et comptée par motif dans le bilan.

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
  droit non. Une échéance dépassée est **signalée** — dans la Bibliothèque, dans la fiche de la
  collection et son onglet *Diffusion et dépôt*, dans le manifeste, dans l'outil en ligne de commande — pour qu'un corpus ne
  reste pas fermé par inertie. La décision, elle, reste humaine.
- **Une date illisible retient aussi.** Une faute de frappe ne doit ni ouvrir la porte, ni
  passer pour une décision.

**Citer, en revanche, n'est jamais bloqué par le régime.** La **figure citable** (bouton
*＋ Figure* de l'Atelier) produit un crop accompagné de sa légende — référence `pl·c·b`,
responsabilité, édition, licence, base légale, « non établie » quand c'est le cas — et de sa
notice. Le cloisonnement des accès s'y applique entièrement : on ne cite que ce qu'on voit.
Cf. [`figure-citable.md`](figure-citable.md) et [`hebergement-securite.md`](hebergement-securite.md).

Régime, licence, base légale et embargo **se règlent à l'écran** depuis le 2026-09-11 :
onglet *Diffusion et dépôt* de la fiche d'une collection, dans la **Bibliothèque**, par qui la possède. L'embargo s'y
saisit en texte `AAAA-MM-JJ` et non dans un sélecteur de date, qui afficherait vide une
date illisible — et l'effacerait au premier enregistrement. Seuls les **responsables
scientifiques** n'ont pas de formulaire : ils s'écrivent par `tools/gerer_collections.py`
(cf. [`export-metadonnees.md`](export-metadonnees.md)).

---

## 6. Administrer l'instance : comptes et groupes

> **Depuis la bascule du 2026-09-07 (AUTH-7), les comptes et les groupes vivent dans
> l'annuaire LLDAP**, administré par son interface web, derrière Authelia. Le fichier des
> comptes n'est plus que le REPLI. Les commandes de l'annuaire sont dans
> [`exploitation.md`](exploitation.md), sous « **Basculer vers l'annuaire LLDAP** » ; celles
> du fichier, sous « **Ajouter un compte sans couper le portail** », qui **fait foi** pour le
> repli. Ce qui suit donne la forme et les pièges, pour comprendre et pour expliquer.
>
> Le renvoi nomme cette sous-section et non le § entier, exprès : « fait foi » sur toute une
> section endosse d'avance ce qu'on y ajoutera, et personne ne reviendra le relire.

### Où vit quoi

| | Comptes et groupes | Qui entre dans une collection |
|---|---|---|
| Où | l'annuaire LLDAP, par son interface web (le fichier `deploy/authelia/users_database.yml` n'est plus que le repli) | dans l'application, *Qui entre* : onglet de la fiche de la collection (Bibliothèque), et dans la fiche de la collection, *👥 Comptes et groupes*, axe *Collections* (Administration) |
| Qui | un administrateur (`bd-admins`), sans accès shell | tout **propriétaire** de la collection, dans la Bibliothèque ; un administrateur, à l'un ou l'autre endroit |
| Effet | qui peut **entrer** | qui voit **quoi** |
| Prise d'effet | sans redémarrer Authelia — c'était le cas du fichier, et c'est ce que la bascule a supprimé | immédiate |

**Pourquoi deux endroits pour *Qui entre*, et un seul panneau.** La question se pose à deux
personnes qui ne partent pas du même point. Le propriétaire part de son corpus : il ouvre la
fiche de sa collection, dans la Bibliothèque, et fait entrer quelqu'un dans la foulée — il n'a jamais à
ouvrir l'Administration. L'administrateur part d'une personne ou d'un groupe : dans
*👥 Comptes et groupes*, la fiche d'un compte nomme ses collections, chacune mène à sa fiche,
et *Qui entre* s'y règle sur place ; depuis la fiche d'un groupe, *Ouvrir une collection à ce
groupe* y mène avec le groupe déjà choisi. C'est le MÊME panneau, monté deux fois : mêmes
gestes, mêmes refus, et ce qu'on règle d'un côté se lit aussitôt de l'autre. Ce que la
collection **est** — description, diffusion, référent, exports — ne vit qu'à un endroit, la
Bibliothèque, où *Décrire dans la Bibliothèque* ramène depuis l'Administration.

Les deux sont nécessaires, et dans cet ordre. **Un compte créé sans accès ouvre une
application vide** — la personne se connectera parfaitement et ne verra rien, sans qu'aucun
message ne l'explique autrement que par le bandeau de portée vide.

**Faire entrer ce compte dans un projet ne lui ouvre que la collection de base de ce
projet**, et seulement si le projet l'a ouverte à ses membres (depuis le 2026-10-17 ;
auparavant, rien du tout). Le bloc *🗂️ Projets* de l'Administration règle qui est d'un
projet. Un arrivant qu'on a seulement fait entrer dans un projet à base protégée lira le nom
du projet en haut de la page — et, comme avant, le bandeau de portée vide. Il pourra y créer
une collection ; il ne lira aucune de celles des autres. Tout autre accès se donne toujours
collection par collection, dans *Qui entre*.

### Ajouter quelqu'un — la forme

**Dans l'annuaire**, un compte se crée par l'interface de LLDAP, puis on le range dans ses
groupes : un formulaire, sans shell, sans redémarrage. **Les étapes suivantes ne valent plus
que pour le fichier de REPLI** — elles restent écrites parce que ce recours existe. Les trois
points qui les suivent, eux, valent pour l'annuaire aussi.

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
par « mot de passe oublié » — **puis ouvrir l'adresse de l'application, jamais celle du
portail** : revenu au portail sans destination, Authelia propose d'enrôler un second facteur
à tout le monde, y compris à qui n'en a pas besoin (cf. [`exploitation.md`](exploitation.md),
*Ajouter un compte*).

### Créer un groupe

**Dans l'annuaire, un groupe se CRÉE** dans l'interface de LLDAP, puis on y range les comptes
(cf. [`exploitation.md`](exploitation.md), étape 7 de *Basculer vers l'annuaire LLDAP*). Dans
le fichier de repli, il n'y a rien à créer : un groupe existe dès qu'un compte le porte. Dans
les deux cas, l'application le découvre en le lisant dans les en-têtes. Côté application, il
suffit de le nommer dans *Qui entre* — dans la Bibliothèque, ou dans l'Administration pour
un administrateur —, en répondant **groupe** à « Compte ou groupe ? » — la question est posée explicitement parce qu'un login et un groupe
peuvent porter le même nom, et qu'une ambiguïté silencieuse sur un contrôle d'accès n'est pas
une hypothèse qu'on se permet.

---

## 7. Questions fréquentes

**Je me connecte et je ne vois rien. C'est cassé ?**
Pas forcément. Lisez le bandeau : il distingue quatre situations (§3). S'il nomme vos groupes,
tout fonctionne — il manque seulement qu'un propriétaire vous donne accès à une collection.
S'il n'en nomme aucun, il dit ce qu'il a reçu, sans en tirer de cause : la liste des groupes
**non transmise**, ou **transmise et vide**. La première n'est PAS forcément une panne : sur
cette instance, c'est aussi ce que produit un compte sans aucun groupe (mesuré le
2026-09-09). Dans les deux cas, le plus probable est qu'il suffise qu'un propriétaire vous
donne accès à votre nom ; si cela ne suffit pas, montrez à l'administrateur la ligne
technique du bandeau (§3), qui départage.

**J'ai donné un accès et la personne ne voit toujours rien.**
Vérifiez l'orthographe du login ou du nom de groupe, dans *Qui entre*. L'application y
confronte désormais le nom que vous tapez à l'annuaire, et le marque : **inconnu de
l'annuaire** s'il n'y existe pas, **non vérifié** si l'annuaire n'a pas répondu. La marque
avertit, elle ne bloque pas — l'accès est accordé tel quel dans les deux cas, et un nom
marqué « inconnu de l'annuaire » n'ouvre rien. C'est la première chose à regarder.
Vérifiez aussi qu'il a été déclaré **compte** ou **groupe** selon ce qu'il est : un accès
donné à un compte ne s'applique pas à un groupe du même nom.

**Je suis membre d'un projet et je n'y vois aucune collection.**
C'est normal si sa collection de base est fermée à ses membres : entrer dans un projet
n'ouvre que celle-là, et seulement si le projet l'a choisi (§2). Pour une autre, il faut
qu'un propriétaire vous y donne accès, dans *Qui entre* — ou que vous en créiez une.

**Je suis responsable d'un projet. Pourquoi ne puis-je pas le renommer ?**
Parce que régler qui entre dans un projet n'est pas décider de son nom ni de son
existence : cela revient aux administrateurs de l'instance (§3), et la fiche du projet
vous le dit. Sa suppression, vous pouvez la **demander**, depuis la même fiche.

**J'ai importé un album par erreur. Comment l'effacer ?**
Dans la Bibliothèque, *Supprimer…* dans la fiche de l'album, puis *Supprimer définitivement* : si vous
l'avez importé vous-même et que personne d'autre n'y a travaillé, il est effacé tout de
suite. Sinon, la même réponse envoie une demande à un administrateur (§2, *Le fonds*).

**J'ai supprimé un album de ma collection. Est-il perdu ?**
Non. S'il vit dans d'autres collections, il y reste entier. Si c'était sa dernière, il est
gardé au fonds avec tout son travail, et un administrateur peut le rendre à une collection
du même projet.

**Pourquoi mon album d'avant le fonds se demande-t-il toujours ?**
Parce que personne n'avait noté qui l'avait importé : l'application ne peut pas savoir que
c'est vous. Dans le doute, la suppression définitive revient à un administrateur.

**Qui sait que j'ai demandé une suppression ?**
Tous ceux qui lisent l'album voient qu'une suppression est demandée ; seuls vous et les
administrateurs voient que c'est vous. Le motif ne se lit que par les administrateurs.

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

**Je vois une collection : pourquoi ne puis-je pas l'exporter ?**
Parce qu'exporter est un droit à part, que le propriétaire accorde accès par accès (§ Les
trois niveaux) : la lire ou l'annoter n'y suffit pas. Demandez-le à son propriétaire, ou
à son référent.

**Où sont les mots de passe et les groupes dans la base ?**
Nulle part. Aucun secret n'y est stocké, et aucune appartenance de groupe non plus : la table
des utilisateurs n'est qu'un **miroir d'affichage**, et les groupes sont relus dans les
en-têtes à chaque requête.
