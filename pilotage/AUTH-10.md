---
chantier: AUTH-10
statut: à venir
---

# AUTH-10 — `ecriture` recouvre l'acte qu'on défait et celui dont on ne revient pas

**Point de départ** — 2026-09-10, en conversation, à partir d'une mesure qui cherchait
autre chose. Le `GET /api/moi` du compte `stagiaire` sur la production rend `ecriture: 0`,
et la question « faut-il un droit d'annoter ? » a rendu un constat plus précis.

**Corrigé le jour même, et la correction RENFORCE la fiche.** Ce compte-là est atypique :
des stagiaires ont bien l'écriture en production, et c'est voulu. Ce chantier n'est donc
pas ouvert sur un arrivant qui ne peut rien faire — il est ouvert sur l'inverse. **Des
personnes ont aujourd'hui le droit de supprimer un album, et aucun Ctrl+Z ne le
rattrape.** La prémisse d'origine était une lecture hâtive d'un compte d'essai ; elle est
écrite ici plutôt que remplacée, parce que c'est en la corrigeant qu'on a vu que le
risque était actuel et non hypothétique.

**`DELETE /api/albums/{id}` exige `_get_album(..., ecriture=True)` — exactement le même
droit qu'annoter une bulle.** Qui reçoit l'écriture pour annoter peut supprimer un album
entier, et `undo.py` ne connaît que quatre tables (`regions`, `annotations`,
`bulle_locuteur`, `personnage_presence`) : cette suppression-là ne se défait pas. Le seul
retour est la sauvegarde, c'est-à-dire hors de l'application.

**Cette dernière phrase est INEXACTE, et de deux façons opposées** (mesuré le 2026-09-10,
voir « Le fait trouvé en chiffrant »). La sauvegarde ne suffit pas : elle ne contient
aucune image, la suppression efface les masters du disque et n'inscrit **aucun** événement
au journal. Mais elle n'est pas non plus le seul retour : l'équipe garde une copie des
masters hors du VPS. Le vrai coût est donc entre les deux — une restauration de base, donc
la perte de ce qui a été annoté depuis la dernière sauvegarde MANUELLE, plus un re-dépôt
des images. La phrase est gardée telle quelle parce que c'est elle qu'on a crue en ouvrant
le chantier, et que la corriger sur place ferait disparaître la raison pour laquelle on a
cherché ailleurs.

## L'inventaire, mesuré — 73 routes mutantes

Relevé par AST sur `main.py` + `routes/*.py` le 2026-09-10. Quatre familles, séparées par
ce qui se DÉFAIT et non par l'objet qu'elles touchent.

| famille | routes | réversible ? |
|---|---|---|
| l'acte interprétatif (région) | 13 | oui, par Ctrl+Z — sauf deux |
| la structure du corpus (planche, album) | 17 | non |
| le vocabulaire (domaines, dimensions, valeurs, tags, personnages) | ~15 | non, et déborde la collection |
| la machine (lots, passes, `ml/liberer`) | ~4 | sans perte, mais accapare le `ML_LOCK` |

**Le résultat qui compte : la frontière de l'annulation passe À L'INTÉRIEUR du niveau
`ecriture`, et elle ne suit pas la hiérarchie des objets.** `PUT /api/regions/{id}/tokens/
{ordre}` et `POST /api/regions/{id}/grammaire/valider` portent le même droit et le même
objet que les onze autres routes de région, et ne sont pas annulables — la grammaire est
« dormante » pour l'undo, c'est écrit dans D1. Donc même à l'échelle d'une région,
« écriture » ne dit rien de la réversibilité.

Deux familles sont DÉJÀ séparées et ne sont pas en cause : ce qui porte sur l'instance
(`ADMIN` sur la sauvegarde et ShareDocs) et ce qui décide qui entre (`administrer`). Les
trois écarts restants sont tous à l'intérieur d'`ecriture`.

## Reste

### Trancher — et la première décision est de ne rien faire, éventuellement
- [x] **Le REMÈDE MOINS CHER est évalué avant le remède structurel** — chiffré le 2026-09-10, section « Les deux remèdes, chiffrés » ci-dessous. **Le résultat contredit l'énoncé de cette case** : le remède de l'undo ne supprime pas « la moitié du problème », il porte sur 2 routes de la famille où le dommage est DÉJÀ réversible, et ne touche pas d'un cheveu les 17 routes de structure. Les deux remèdes ne sont donc pas substituables, et le chiffrage a fait apparaître un TROISIÈME remède, moins cher que les deux et qui vise le dommage réel
- [ ] **Trancher entre les trois remèdes, maintenant qu'ils sont chiffrés.** L'ordre n'est plus une question de coût mais de ce que chacun ACHÈTE : la trace et le sursis (remède C) rendent une suppression d'album rattrapable ; le niveau `contribution` (remède B) empêche que la question se pose ; l'alignement de l'undo (remède A) rend homogène une famille qui ne détruit rien d'irremplaçable. C et B ne s'excluent pas — C protège les gens qui ont légitimement le droit de supprimer, et aucun niveau de droits ne les couvre. **Cette case reste ouverte EXPRÈS : le 2026-09-10, l'équipe a décidé de ne rien engager pour l'instant**, section « La décision du 2026-09-10 » — l'exposition qui demeure y est écrite, pour qu'elle soit acceptée et non subie
- [ ] **La décision d'ajouter un niveau est prise avec son coût écrit.** Un quatrième niveau est une quatrième occasion de refus SILENCIEUX : `Portee.__init__` cumule à un seul endroit, et AUTH-3 a déjà nommé le mode d'échec — « un `in portee.ecriture` qui oublierait les propriétaires serait un refus silencieux et parfaitement crédible ». Ce défaut ne casse aucun test
- [ ] **Si un niveau est retenu, c'est `contribution`, et la raison est STRUCTURELLE et non ergonomique.** Le cumul de ce modèle est dérivé d'un ORDRE, pas stocké : `collection_acces` a pour clé primaire `(collection_id, genre, principal)` — une ligne, un seul `niveau` — et `Portee.__init__` fait `ecriture |= propriete` puis `lecture |= ecriture`. Seul ce qui s'ORDONNE peut donc s'y insérer. `lecture ⊂ contribution ⊂ ecriture ⊂ proprietaire` s'ordonne ; « vocabulaire » et « structure » ne s'ordonnent pas entre eux, et leur imposer un rang inventerait une hiérarchie que le travail n'a pas
- [ ] **Le périmètre exact de `contribution` est écrit route par route**, et il ne se déduit pas de l'objet : les 13 routes de région, corrections de tokens comprises. L'attendu est une LISTE, parce que « les routes de région » a déjà deux exceptions connues

### L'interface et le modèle sont DEUX questions, et les coller a failli coûter cher
- [ ] **L'interface se rend en CASES À COCHER, et c'est acquis quel que soit le modèle retenu.** « Écriture » ne dit à personne qu'il autorise à supprimer un album ; une case libellée « supprimer des planches et des albums » le dit. Une ÉCHELLE se rend parfaitement en cases — cocher un cran coche ceux du dessous —, donc la lisibilité s'obtient **sans toucher à `collection_acces`**. Attendu : les libellés énumèrent des ACTES, jamais des noms de niveau
- [ ] **La matrice est une décision DISTINCTE, et elle ne se prend que si une capacité résiste à l'ORDRE.** Ce qu'elle coûte, mesuré et non supposé : `collection_acces` a une ligne par personne (clé primaire `(collection_id, genre, principal)`), donc un ensemble demande une colonne-liste ou une ligne par capacité ; le cumul **cesse d'être structurel** — aujourd'hui dérivé une fois dans `Portee.__init__`, il deviendrait un test d'appartenance par question, et l'oubli qu'AUTH-3 signale se multiplierait par le nombre de cases ; enfin une matrice admet des états que le métier interdit (« peut supprimer » sans « peut lire »), donc il faudrait des règles de dépendance — c'est-à-dire une échelle réintroduite à la main
- [ ] **S'il faut une capacité hors rang, le gabarit existe DÉJÀ dans ce modèle** : `bd-admins` court-circuite entièrement `collection_acces` (AUTH-4). Une échelle et un axe orthogonal y cohabitent depuis v25. Une capacité non ordonnable serait donc **un drapeau de plus**, pas un changement de modèle — et la meilleure candidate est la curation du vocabulaire, seule des quatre familles à déborder la collection où l'on travaille
- [ ] **Le signe qu'un ordre subsiste est dans la proposition elle-même** : « toutes les cases cochées = propriétaire ». S'il existe un SOMMET, il existe un ordre au moins partiel — ce qui se demande n'est donc pas une matrice libre, mais une échelle avec une ou deux cases hors rang. L'attendu de cette case est de le vérifier plutôt que de le supposer : énumérer les paires de capacités et dire, pour chacune, si l'une implique l'autre

### Ce qui devra être vrai, si le niveau est fait
- [ ] Un compte `contribution` annote, transcrit et corrige un token, et reçoit un refus NOMMÉ sur la suppression d'une planche ou d'un album — pas un 404
- [ ] Un compte `contribution` ne peut ni fusionner deux valeurs, ni fusionner deux personnages, ni renommer un terme global : ces actes ne se défont pas et débordent la collection où l'on travaille
- [ ] Un compte `contribution` ne peut pas lancer de lot : le `ML_LOCK` est sérialisé, et le dommage n'est pas la perte mais l'ACCAPAREMENT — une passe sur tout le corpus bloque les autres pendant des minutes
- [ ] Le cliquet de `tests/test_autorisation.py` exige que chaque route ait tranché ENTRE QUATRE niveaux et non trois — sans quoi une route neuve hériterait du niveau le plus permissif par défaut et non par décision
- [ ] Le cumul est éprouvé par table de vérité aux QUATRE niveaux, et pas seulement aux extrémités : c'est le seul endroit où l'oubli d'AUTH-3 se reproduirait

### Le trou d'affichage, qui existe indépendamment de ce chantier
- [ ] **Un refus d'écriture sur une donnée est un 404, et il ment à qui VOIT l'objet.** `_get_region(..., ecriture=True)` lève « Région 42 introuvable » sur une région affichée à l'écran. La règle vient d'AUTH-2 — « 404, jamais 403 : "existe mais pas pour vous" révèle la composition du corpus » — mais elle ne s'applique PAS ici : la personne lit déjà cette région. Le 404 ne lui cache rien du corpus, il lui cache la raison du refus. Attendu : un 403 nommé quand l'objet est LISIBLE et l'écriture refusée, le 404 restant pour qui ne le voit pas. La doctrine n'est pas rompue, elle est précisée
- [ ] Ce raffinement est éprouvé dans les DEUX sens — un lecteur reçoit 403 sur ce qu'il voit, un étranger reçoit 404 sur ce qu'il ne voit pas — sans quoi on aurait remplacé un mensonge par une fuite

## Les deux remèdes, chiffrés — 2026-09-10

**Le remède A se coupe en deux moitiés qui n'ont pas le même prix**, et l'énoncé qui les
réunissait — « rendre la correction de tokens et la validation grammaticale annulables » —
masquait l'écart.

**A1, la correction d'un token, est bon marché parce que le journal porte déjà tout.**
`corriger_token` inscrit un événement `creation`/`modification` sur `token_correction` avec
`avant` ET `apres` complets — les six colonnes `ordre, forme, lemme, pos, morph, etat` ;
`annuler_correction` inscrit une `suppression` avec son `avant`. Rien à changer côté
écriture. Ce qui manque est dans `undo.py` seul : la table dans `_TABLES`, une branche dans
`_inverser` sur le patron exact de `_restaurer_annotation`, et un `reindex_region`. Un
écueil à trancher, petit mais réel : `cible_id` y est l'id de la ligne `token_correction`,
qui est RÉATTRIBUÉ après suppression — c'est précisément pourquoi les actes d'annotation
ciblent `region_id` et non l'id d'annotation. Soit on accepte le 409 « id réattribué » que
`_inverser` sait déjà rendre, soit on re-cible sur la région, ce qui suppose de porter
l'`ordre` dans un `cible_id` qui est un entier unique.

**A2, la validation grammaticale, est chère, et pas pour la raison qu'on suppose.** Son
événement est écrit sans `avant` (`validation` / `regions`, avec pour tout contenu
`{"grammaire": "validee"}`), et `validation` ne figure pas dans `undo._TYPES`. Surtout,
l'acte est EN LOT : il passe à `valide` toutes les corrections non obsolètes de la région
et INSÈRE une ligne par token qui n'en avait pas. Son inverse demande l'état antérieur de
chaque ligne touchée — que le journal ne porte pas. Il faut donc changer ce que la route
inscrit, et les événements DÉJÀ écrits resteront non inversibles, le journal étant
append-only. La dormance nommée par D1 n'était pas de la paresse.

**Ce que le remède A n'achète pas, et c'est le résultat du chiffrage.** Il porte sur 2
routes des 13 de la famille « région » — celle qui est déjà réversible et dont le pire
dommage est un lemme à retaper. Les 17 routes de structure restent exactement où elles
étaient. « La moitié du problème » était une estimation faite avant de regarder.

## Le fait trouvé en chiffrant, et qui déplace la question — 2026-09-10

Cette fiche disait : « le seul retour est la sauvegarde, c'est-à-dire hors de
l'application ». **C'est trop optimiste, et de loin.** Mesuré en lisant `delete_album` :

- elle exige `_get_album(..., ecriture=True)` — le droit d'annoter une bulle, comme annoncé ;
- **elle ne journalise RIEN.** Aucun appel à `journal.journaliser` : là où la suppression
  d'une RÉGION inscrit son instantané profond, celle d'un album n'inscrit rien du tout. Un
  undo étendu à la famille « structure » n'aurait donc rien à lire — le substrat manque
  avant même la question du périmètre ;
- elle appelle `remove_album_files`, c'est-à-dire un `shutil.rmtree` sur le dossier
  `corpus/album_N` **et** son dérivé : **les masters TIFF quittent le disque** ;
- et la sauvegarde de `pipeline/backup.py` est un `VACUUM INTO` de la base, zippé. **Elle
  ne contient aucune image** — `docs/hebergement-securite.md` dit pourquoi en une ligne :
  le disque est dominé par les masters, dizaines à centaines de Go.

**Donc restaurer la sauvegarde après une suppression d'album rend une base qui pointe vers
des fichiers absents.**

**Ce que ça coûte VRAIMENT — corrigé le 2026-09-10, quelques minutes après avoir été
écrit trop noir.** Cette section concluait qu'il faudrait re-scanner les albums physiques.
C'est faux : l'équipe garde une copie des masters hors du VPS, et `corpus/` n'est pas
l'unique exemplaire. La perte n'est donc pas le corpus, c'est **le temps de re-déposer les
images et de réaligner ce qui pend à leur identifiant** — un album supprimé emporte ses
planches et ses régions par CASCADE, donc les annotations avec. Deux choses restent vraies
et suffisent à motiver le chantier : la suppression n'inscrit **aucun** événement, donc le
journal ne dira jamais qui l'a faite ni sur quoi ; et le retour passe par une restauration
de base, c'est-à-dire par la perte de tout ce qui a été annoté depuis la dernière
sauvegarde — **qui est un geste MANUEL** (`deployer.sh` le dit lui-même : il ne sauvegarde
pas), donc d'une fraîcheur qui dépend de ce que quelqu'un a pensé à faire.

**La leçon d'écriture, notée parce qu'elle se répète** : la phrase fautive n'était pas une
mesure, c'était une déduction — de « la sauvegarde ne contient pas d'images » à « les
images n'existent nulle part ailleurs ». Le dépôt savait la première ; la seconde
demandait de connaître les habitudes d'une équipe, ce qu'aucun fichier ne dit. Même forme
que la lecture de sources réfutée par AUTH-8 la veille : *lire un dépôt n'est pas mesurer
un déploiement*.

**Le remède C, qui n'était pas dans la fiche et qui coûte moins que les deux autres.**
Journaliser la suppression (l'instantané profond existe déjà pour les régions, le patron
est écrit) et ne pas effacer les fichiers dans le même geste — un sursis, une corbeille,
un dossier `corpus/.supprime/` purgé par une commande explicite. Il ne touche **aucun
modèle de droits**, ne crée aucune occasion de refus silencieux, et il protège quelqu'un
que B ne protégera jamais : la personne qui a LÉGITIMEMENT le droit de supprimer et se
trompe d'album. Un niveau de droits répond à « qui » ; il ne répond pas à « je n'avais pas
vu que c'était celui-là ».

## La décision du 2026-09-10 : on ne fait rien maintenant

**Aucun des trois remèdes n'est engagé**, et le chantier reste `à venir`. Décidé par
l'équipe le jour même du chiffrage, en connaissance de ce qui suit — c'est-à-dire pas par
inadvertance, et c'est toute la différence entre une exposition acceptée et une exposition
ignorée.

**Ce qui reste ouvert en production pendant ce temps**, écrit ici pour que la reprise
n'ait pas à le redécouvrir :

- des comptes en `ecriture` — des stagiaires, et c'est voulu — peuvent supprimer un album
  ou une planche ;
- l'acte n'inscrit aucun événement au journal : ni auteur, ni date, ni instantané ;
- il efface les fichiers du disque dans le même geste, sans sursis ;
- le retour existe, mais il coûte une restauration de base (donc la perte des annotations
  postérieures à la dernière sauvegarde manuelle) plus un re-dépôt des images depuis la
  copie tenue hors du VPS.

**Ce qui rend l'attente tenable** : la copie hors VPS existe, la population concernée est
petite et connue, et rien n'indique que le cas se soit produit. **Ce qui la rendrait
intenable** : un premier incident, ou l'arrivée d'une promotion de trente personnes — le
chiffre est dans `AUTH-7`, et c'est le pic, pas le total, qui décide.

**Le remède le moins cher reste C** (journaliser + surseoir à l'effacement), et il ne
demande aucune décision de modèle de droits — s'il faut agir vite un jour, c'est par là.

## Ce qui rouvrira la question sans la décider — 2026-09-10

**Ne rien engager suppose qu'on n'ouvre pas le modèle de droits EXPRÈS. Cela ne suppose
pas que le code reste immobile, et il ne le restera pas.** Trois chantiers ouverts portent
déjà une case qui atterrit dans ce code-ci, et aucun ne mentionnait AUTH-10 avant ce jour.

- **`AUTH-6`** en porte deux. Sa case sur le compte COLLECTIF constate qu'`undo.py` filtre
  par AGENT, donc que sous un login partagé n'importe qui défait l'acte d'un autre : qui la
  traitera sera DANS `undo.py`, à quelques lignes de la branche `token_correction` du
  remède A1 — dont le journal porte déjà tout ce qu'il faut. Le risque n'est pas le conflit,
  c'est qu'un remède se fasse sans être déclaré, ou qu'on passe à côté en y étant. Ses deux
  autres cases — un groupe renommé ou supprimé dans l'annuaire, une collection dont l'unique
  propriétaire perd son groupe — travaillent la sémantique de `collection_acces`,
  c'est-à-dire la table que le remède B modifierait.

  **Déclaré le 2026-09-11** : la case du compte collectif est faite (`ff95ec0`). Elle est
  passée DANS `undo.py`, comme prévu : un délai de cinq minutes sur la recherche du dernier
  acte et sur le ciblage par id. Elle n'a touché ni `_TABLES` ni `_TYPES`. La branche
  `token_correction` d'A1 reste donc dormante, rien du remède n'a été fait en passant, et la
  décision de ne rien engager tient.
- **`UX-11`** construit une Bibliothèque qui sait « ouvrir et supprimer une planche », et
  cite déjà l'asymétrie d'AUTH-2 — le client ne reçoit pas `peut_ecrire` et découvre un
  refus en recevant son 403. C'est exactement la famille de routes que cette fiche décrit,
  et l'écran qui la rendra atteignable en deux clics.
- **`COL-1`** fera circuler le travail ENTRE collections : c'est la famille « vocabulaire »,
  la seule des quatre à DÉBORDER la collection où l'on travaille.

**Ce que ça change à la décision : rien. Ce que ça change à sa TENUE : elle doit être
lisible depuis ces chantiers-là et non depuis cette fiche seule** — une décision de
différer qui ne dit pas ce qui la rouvrira se fait contourner sans que personne l'ait
voulu. Les trois fiches portent désormais un renvoi ici.

**Et le remède C ne croise aucun d'eux** : journaliser une suppression et surseoir à
l'effacement ne touche ni `collection_acces`, ni `undo.py`, ni le modèle de droits. Il
reste disponible à tout moment, sans rien attendre ni bloquer.

## Une capacité hors de l'échelle est engagée ailleurs — 2026-09-11

**Exporter devient un droit à part, accordé par collection** (`DROIT-2`). C'est le patron
que cette fiche a écrit — *« une capacité non ordonnable serait un drapeau de plus, pas un
changement de modèle »* — appliqué à un acte qui n'est PAS dans son inventaire : les
exports sont des lectures qui sortent, et les 73 routes recensées ici sont des écritures.

**Ce que ça change pour cette fiche** : sa décision de ne rien engager tient, mais le patron
sera éprouvé avant qu'on ait à le poser sur la suppression. Le jour où ce chantier se
rouvrira, `DROIT-2` dira ce qu'a coûté une case à côté du niveau — la migration, le cliquet
d'une garde qui échoue ouvert, l'écran —, et la décision se prendra sur une mesure au lieu
d'une prévision.

## Contexte

**Pourquoi ça se pose maintenant et pas avant.** Le modèle à trois niveaux répond à
*« jusqu'où t'a-t-on laissé entrer »* : c'est un axe d'APPARTENANCE, et il était juste tant
qu'une collection était l'espace d'une équipe qui se connaît. « Peut annoter » est un axe
d'ACTE. Les mélanger est ce qui pourrit un modèle de droits, donc l'absence n'était pas un
oubli — c'était une frontière tenue. Ce qui change, c'est l'arrivée de gens dont le métier
est exactement UNE des familles.

**Ce que le chantier ne doit pas devenir.** Un modèle de capacités où chaque acte a son
drapeau. Le cumul de ce modèle est dérivé d'un ordre ; passer à un ENSEMBLE demanderait de
renoncer à la clé primaire de `collection_acces` ou d'y stocker une liste, et de rendre
EXPLICITE un cumul aujourd'hui structurel. C'est précisément là que naissent les refus
silencieux.

**Voisinage.** `AUTH-2` (le point de passage unique, et le 404 qui ne fuit rien), `AUTH-3`
(les trois niveaux et le piège du cumul), `D1` (l'annulation, son périmètre et ses
dormances), `AUTH-6` (le modèle de comptes, qui a soulevé la question par un
`ecriture: 0`), `COL-2` (les descripteurs, l'autre chose qu'on ne peut pas encore régler à
l'écran).
