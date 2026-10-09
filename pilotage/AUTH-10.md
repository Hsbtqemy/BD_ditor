---
chantier: AUTH-10
statut: différé
---

# AUTH-10 — `ecriture` recouvre l'acte qu'on défait et celui dont on ne revient pas

**Arrêté sur** — 2026-10-08, commit `d92500b` (la règle écrite dans `CLAUDE.md` et la
documentation d'usage), après `a17b634` (le code) : la zone « Supprimer n'est pas sortir » est
codée — détruire un album ou l'une de ses planches demande d'écrire dans toutes ses
collections, le sortir d'une collection reste permis à qui y écrit. Reste à jouer la passe
`supprimer-n-est-pas-sortir`, et à trancher deux choses : le veto que la règle donne à qui
range l'album chez soi, et la « collection de base » proposée par Hugo, à faire en chantier
propre après la fusion vers `main`. Les trois remèdes du 2026-09-10 attendent toujours.

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
- [ ] Le cliquet de `tests/test_autorisation.py` exige que chaque route ait tranché ENTRE QUATRE niveaux — **ce qu'il ne fait pas aujourd'hui, même à trois** : il vérifie qu'une route CONSULTE la portée, jamais QUEL niveau elle exige (relu le 2026-09-11). C'est donc une EXTENSION du cliquet, pas son passage de trois à quatre — sans quoi une route neuve hériterait du niveau le plus permissif par défaut et non par décision
- [ ] Le cumul est éprouvé par table de vérité aux QUATRE niveaux, et pas seulement aux extrémités : c'est le seul endroit où l'oubli d'AUTH-3 se reproduirait

### Le trou d'affichage, qui existe indépendamment de ce chantier
- [ ] **Un refus d'écriture sur une donnée est un 404, et il ment à qui VOIT l'objet.** `_get_region(..., ecriture=True)` lève « Région 42 introuvable » sur une région affichée à l'écran. La règle vient d'AUTH-2 — « 404, jamais 403 : "existe mais pas pour vous" révèle la composition du corpus » — mais elle ne s'applique PAS ici : la personne lit déjà cette région. Le 404 ne lui cache rien du corpus, il lui cache la raison du refus. Attendu : un 403 nommé quand l'objet est LISIBLE et l'écriture refusée, le 404 restant pour qui ne le voit pas. La doctrine n'est pas rompue, elle est précisée
- [ ] Ce raffinement est éprouvé dans les DEUX sens — un lecteur reçoit 403 sur ce qu'il voit, un étranger reçoit 404 sur ce qu'il ne voit pas — sans quoi on aurait remplacé un mensonge par une fuite

### Supprimer n'est pas sortir — un album rangé dans plusieurs collections
- [x] **Trancher ce que « supprimer un album » fait quand il vit AUSSI ailleurs.** Aujourd'hui : écrire dans UNE de ses collections suffit à l'effacer de TOUTES (`delete_album` → `_get_album(ecriture=True)` → `clause_album(ecriture=True)`, un `EXISTS` sur les collections où l'on écrit). Options : **(1)** exiger d'écrire dans TOUTES ses collections — mais le refus, pour être honnête, doit dire qu'il vit ailleurs, c'est-à-dire révéler l'existence d'une collection qu'on ne lit pas ; **(2)** depuis une collection, le geste ne fait que l'en SORTIR tant qu'il vit ailleurs, et ne supprime que la dernière fois — c'est la règle déjà tenue pour une collection (« supprimer une collection ne supprime pas ses albums », `AUTH-3`), le geste devient réversible, et le scénario de l'incubateur est protégé. **Recommandation : (2)**, avec un message qui ne distingue pas les deux issues pour qui ne lit pas l'autre collection — sans quoi (2) fuit comme (1). Attendu : l'option, sa raison, et ce que dit l'écran dans chaque cas **Tranché le 2026-10-08 par Hugo : (2)** — « on supprime la présence dans une collection, mais pas spécialement l'album ». SORTIR est permis à qui écrit dans la collection, DÉTRUIRE seulement à qui écrit dans toutes celles où l'album vit ; la recommandation du message indistinct est abandonnée. Section « La décision du 2026-10-08 »
- [x] **Le constat est gardé par un test, quelle que soit l'option** — attendu : un album rangé dans deux collections, un compte qui n'écrit que dans l'une et ne lit pas l'autre ; après son geste, le lecteur de l'AUTRE collection voit toujours l'album. Reproduit le 2026-10-08 par un essai jetable, sur le code de `dev` : le compte ne lit que « Incubateur », son `DELETE` répond 204, et l'album a disparu pour la lectrice de la collection principale comme pour l'administrateur **Fait par `a17b634`** : `tests/test_destruction.py`, dix-neuf tests — le geste joué sous chaque identité, et ce que voient les AUTRES regardé ensuite. Y sont aussi le compte qui LIT l'autre collection sans y écrire (sans quoi « écrire partout » se réduirait en « voir partout »), le droit reçu par un GROUPE, le propriétaire d'un seul côté, et trois collections
- [x] **La suppression d'une PLANCHE est relue sous la même question** — attendu : dit et écrit. Une planche n'a pas d'appartenance propre, elle suit son album : la supprimer depuis une collection la retire donc de toutes, et il n'y a pas de « sortir » pour elle. Si (2) est retenue pour l'album, la planche reste le chemin par lequel un compte en écriture vide un album partagé, une planche à la fois **Tranché le 2026-10-08 avec la précédente** : même règle — détruire une planche demande d'écrire dans toutes les collections de son album. Ce chemin se ferme ; le prix est qu'un compte qui n'écrit que d'un côté ne retire plus un scan fautif d'un album partagé
- [x] **`delete_album` et `delete_planche` exigent l'écriture dans TOUTES les collections de l'album** — attendu : le compte qui n'écrit que dans l'une reçoit un refus NOMMÉ (403 — il lit l'album, un 404 lui mentirait : c'est la case du « trou d'affichage » ci-dessus, appliquée ici), l'album et ses planches restent intacts ; qui écrit partout, ou porte une portée totale, détruit comme aujourd'hui ; un album rangé dans une seule collection se détruit comme aujourd'hui. La question s'écrit dans `autorisation.py`, à côté de `clause_album`, et non dans les deux routes **Fait par `a17b634`** : `Portee.clause_destruction`, et `socle._exiger_destruction` qui dit comment refuser. Le 403 ne vient qu'APRÈS l'accesseur gardé en écriture : qui n'écrit nulle part reçoit toujours son 404 ; il ne nomme aucune collection et ne dit pas combien. Un cliquet lit le source des routes — toute fonction qui efface un album, une planche ou leurs fichiers pose la garde ou figure sur `HORS_GARDE` avec sa raison : l'oubli échouait OUVERT. Dix-sept mutants côté serveur, dix-sept tués
- [x] **Le serveur dit, album par album, si on peut le détruire, et l'écran ne propose que ce qui aboutira** — attendu : « Retirer de cette collection » pour un album qui vit ailleurs (`sortir_album` existe et suffit), « Détruire l'album » seulement quand le serveur l'annonce possible. Le client ne peut pas le déduire seul : la liste des collections d'un album qu'il reçoit est PARTIELLE (`list_collections_album` ne rend que celles qu'on lit). À faire avec la fiche d'album d'`UX-18`, qui porte ces gestes **Fait par `a17b634`, dans l'écran ACTUEL** : `GET /api/albums` publie `destructible` et `ecrivable`. La corbeille d'un album et celles de ses planches ne s'offrent qu'à qui peut détruire ; à qui écrit sans écrire partout, un ✕ de même gabarit ouvre la fiche sur « sortir », dit pourquoi, fait confirmer quand on y perd l'écriture, et ferme la fiche quand l'album a quitté ce qu'on lit ; à qui ne fait que lire, rien. Les libellés NOMMÉS — « Retirer de cette collection », « Détruire l'album » — restent à la refonte d'`UX-18` : la ligne d'aujourd'hui n'a que des icônes. Quinze mutants côté écran, quinze tués
- [ ] **La passe `supprimer-n-est-pas-sortir` est jouée** — attendu : ses cases cochées par Hugo, sur la pile de recette reconstruite avec `a17b634`. La suite ne dit pas si un ✕ à la place d'une corbeille se COMPREND — **REPORTÉE le 2026-10-09, décision de Hugo, prise au moment de jouer les passes d'avant la fusion `dev` → `main`** : elle n'en est plus un préalable. Son écran — le ✕ à la place de la corbeille, la confirmation de sortie — ne s'atteint que sur un album rangé dans plusieurs collections, derrière le proxy ; d'après ce que Hugo en a dit à la session qui a codé la règle, la production n'en porte pas ; et la tranche 2 de `COL-3` RÉÉCRIRA cette passe au lieu de la rejouer (sa case « `supprimer-n-est-pas-sortir` est RÉÉCRITE »). La règle part donc en production gardée par ses tests — dix-neuf côté serveur, un navigateur à quatre identités, un cliquet — et NON vue à l'écran par un humain. Ce qui rouvre avant `COL-3` : un album partagé entre deux collections en production ; la passe se joue alors telle quelle, sur la recette
- [ ] **Trancher le veto de qui range l'album chez soi** — attendu : accepté par écrit, ou fermé, avec sa raison. Un co-écrivain qui range l'album dans une collection à lui retire à tous les autres le droit de le détruire, et ils ne peuvent pas le défaire. Mesuré par la relecture croisée, section « Ce que la relecture croisée a trouvé ». Sans objet si la collection de base est retenue
- [ ] **La collection de base — l'autre forme, proposée par Hugo le 2026-10-08, à trancher** — « une collection de base, qui récupère tous les imports ; et impossible de supprimer dedans, sauf admin ». Attendu : retenue ou écartée, avec sa raison. Ce qu'elle achète et ce qu'elle demande est écrit dans « La décision du 2026-10-08 ». Elle ne remplace pas les deux cases précédentes, elle s'y AJOUTE : « écrire partout », appliqué à un album qui vit aussi dans une collection où seul l'administrateur écrit, donne exactement « sauf admin ». **Un de ses coûts est accepté par Hugo le 2026-10-08** : que supprimer une PLANCHE y devienne un geste d'administrateur. Restent à trancher l'export (la base ne doit pas compter comme titre), son écran, et la variante sans collection. **Reformulée par Hugo le 2026-10-09 en FONDS** — tout album appartient à l'instance, « supprimer » le retire d'une collection, seul l'administrateur détruit et réintègre : c'est la variante sans collection, et l'export n'y est plus un coût. Section « Le fonds », avec ce qu'un essai a montré et les décisions qui restent

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
- **`UX-4`** reprend l'Administration, et sa première cible est le panneau des accès —
  c'est-à-dire l'écran qui rend le `<select>` de niveau que la case « l'interface se rend
  en cases à cocher » veut remplacer. **Déclaré le 2026-09-13** : la refonte en TABLEAU y
  est écrite avec la consigne explicite de laisser ce contrôle intact et de faire en sorte
  que la colonne « Niveau » puisse changer seule. Le risque n'est pas le conflit, il est
  dans les deux sens : qu'un écran se mette à énumérer des ACTES sans que la décision de
  modèle ait été prise, ou — plus discret — qu'une refonte fige le menu déroulant dans un
  gabarit dont on ne sorte plus sans tout rouvrir.

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

## Une description des actes est posée à côté de `NIVEAUX` — 2026-09-17

**Déclaré, comme la décision du 2026-09-10 le demande.** `3a30843` ajoute dans
`autorisation.py`, juste sous `NIVEAUX`, une table de DONNÉES — `ACTES` et `HORS_RANG` —
servie par `GET /api/droits` à l'écran qui attribuera les accès (AUTH-12, étape 3). Elle dit
en actes le modèle d'aujourd'hui : lire, annoter, structurer le corpus, gérer le vocabulaire,
lancer des lots, décider qui entre. Les quatre actes d'écriture y sont LIÉS, puisque
`ecriture` les accorde ensemble, et `exporter` y est hors rang.

**Elle ne change aucun accès.** Aucune garde ne la lit, et un test l'exige
(`tests/test_droits.py`). Un autre la confronte à `Portee` par table de vérité : elle ne peut
pas dire d'un niveau ce que le cumul ne fait pas.

**Cette table de vérité éprouvait l'ÉCHELLE, pas le niveau de chaque acte** — corrigé le
même jour. Elle choisissait la question posée à `Portee` d'après le niveau que l'acte
déclare, si bien que « décider qui entre » ou « lire » déclarés en écriture y restaient
cohérents : deux mutants ont survécu. Chaque acte est désormais JOUÉ, par un geste qui le
représente, sous un membre de chaque niveau (`4db9e03`) — un geste par acte, qui ne devient
pas pour autant le périmètre route par route de la case citée ci-dessous.

**Aucune décision de cette fiche n'y est prise, et ses remèdes la feront évoluer.** Le remède
B détacherait `annoter` : un niveau `contribution`, une liaison rompue, un cran de plus dans
l'échelle — la table et ses tests changeraient, l'écran non. Le remède C retirerait
l'avertissement sur la suppression d'un album, qui n'est vrai que tant qu'elle efface sans
trace ni sursis.

**Ce qu'elle ne prouve pas** est l'objet de la case « Le périmètre exact de `contribution` est
écrit route par route » : qu'une route donnée exige le niveau de son acte. La table reprend le
tableau d'AUTH-12, lui-même tiré de l'inventaire des 73 routes de cette fiche. Ses libellés
sont provisoires et soumis à Hugo.


## Un album partagé se supprime depuis une seule de ses collections — 2026-10-08

Trouvé en relisant la Bibliothèque pour `UX-18`, pas en cherchant un défaut de droits. Cette
fiche porte depuis le 2026-09-10 que la suppression d'un album ne se RATTRAPE pas, et que
l'écriture qui permet d'annoter permet aussi de supprimer. Elle ne portait pas ceci : la
suppression ne regarde qu'UNE des collections de l'album.

**Le fait.** Un album vit dans plusieurs collections (`AUTH-3`, N-N depuis la v14, et c'est
voulu : un même album nourrit deux études). Son droit d'écriture est l'UNION — écrire dans
une de ses collections suffit —, ce qui est la bonne règle pour annoter : le travail fait
dans l'une se voit dans l'autre, c'est le but. Mais la suppression passe par le même
accesseur, et elle efface l'album partout : images, régions, annotations, pour toutes ses
collections, y compris celles que celui qui supprime ne LIT pas. Il ne peut même pas le
savoir — la règle du 404 lui cache l'autre collection, à raison.

**Pourquoi ce n'est pas le même constat que celui du 2026-09-10.** Le premier disait : ce
droit est trop large pour ce qu'il coûte. Celui-ci dit : ce droit s'exerce HORS de la
collection où on l'a reçu. Les remèdes chiffrés ici n'y répondent pas tous — la trace et le
sursis (remède C) rendraient la perte rattrapable, mais le niveau `contribution` ne change
rien pour un compte en `ecriture` pleine, et c'est exactement ce que reçoit un groupe
d'incubateur.

**Ce qu'il fait à `COL-1`.** L'incubateur donne `ecriture` à un groupe fermé sur SA
collection, puis promeut un album en le rattachant à la collection principale AVANT de le
détacher de l'incubateur — « sans trou », dit sa fiche. Entre les deux, l'album vit dans les
deux, et tout membre de l'incubateur peut l'effacer du corpus principal. La fenêtre que
`COL-1` ouvre pour ne perdre aucun album est celle où un album se perd le plus facilement.
Le renvoi est posé chez lui.

**Ce qui n'était pas décidé en l'écrivant.** Rien : la zone « Supprimer n'est pas sortir »
du `Reste` posait les deux options et une recommandation. La décision est venue le jour
même, section suivante. Celle du 2026-09-10 de ne rien engager sur les niveaux n'est pas
rouverte par ce constat — il ne demande aucun niveau.

## La décision du 2026-10-08 : on retire une présence, on ne détruit pas un album

Hugo, en réponse à la zone « Supprimer n'est pas sortir » : *« Pour moi, on supprime la
présence dans une collection, mais pas spécialement l'album, non ? »* — puis *« Je te
suis »* sur la règle qui en a été tirée.

**La règle.** Deux gestes là où il n'y en avait qu'un.

- **SORTIR** un album de sa collection : permis à qui y écrit, tant que l'album vit
  ailleurs. Rien à écrire côté serveur — `sortir_album` le fait déjà, 409 compris sur la
  dernière collection.
- **DÉTRUIRE** un album, ou l'une de ses planches : seulement à qui écrit dans TOUTES les
  collections où l'album vit. Pour un album rangé dans une seule collection, rien ne change.

Annoter reste gouverné par l'UNION, et c'est voulu : le travail fait dans une collection se
voit dans l'autre, et il se défait par Ctrl+Z.

**Deux conséquences acceptées avec elle.**

1. *L'écran révèle qu'un album vit ailleurs.* « Détruire » n'étant proposé que là où il
   aboutira, son absence dit qu'une autre collection porte l'album — sans la nommer.
   L'éviter demanderait une corbeille avec sursis (le remède C). Cela REMPLACE la
   recommandation écrite le matin même dans la zone, « un message qui ne distingue pas les
   deux issues » : elle supposait un seul geste à deux issues, il y en a deux.
2. *Un album d'une seule collection se détruit toujours par quiconque y écrit.* C'est la
   question du 2026-09-10, et cette décision ne la rouvre pas.

**Ce que cela fait à la fenêtre de `COL-1`.** Un membre de l'incubateur peut sortir l'album
de l'incubateur — le dernier temps de la promotion, fait trop tôt, sans perte — ; il ne peut
plus ni le détruire ni le vider planche par planche. Le prix est du même côté : tant que
l'album vit des deux côtés, il n'en retire plus non plus un scan fautif.

### L'autre forme, proposée le même jour : une collection de base

Hugo, dans le même message : *« Ou sinon on fait une collection de base, qui récupère tous
les imports. Et impossible de supprimer dedans, sauf admin ? »*

**Ce qu'elle achète, et que la règle n'achète pas.** La destruction réservée à
l'administrateur PARTOUT, y compris pour l'album d'une seule collection : c'est une réponse
à la question du 2026-09-10 qui ne demande aucun niveau. « Supprimer » devient toujours
rattrapable — l'album sorti de partout reste dans la base, où l'administrateur le re-range
ou le détruit : la corbeille du remède C, sans sursis. Et la conséquence 1 disparaît,
puisque personne d'autre ne voit jamais « détruire ».

**Ce qu'elle n'est pas : la « Collection par défaut » d'aujourd'hui.** Celle-ci reçoit déjà
les albums créés sans collection nommée (`create_album`, et l'import de l'Atelier par
`nouvel_album`), mais c'est une collection ORDINAIRE — on y donne des accès, qui y écrit y
supprime, et un album créé dans une collection nommée n'y figure pas.

**Ce qu'elle demande.** Lu dans le code le 2026-10-08, rien n'a été joué.

- *Elle est fermée à tous, sauf portée totale.* La lire serait lire tout le corpus, et le
  cloisonnement d'`AUTH-2` tomberait. Ce serait la première collection à régime propre :
  aujourd'hui la collection de repli n'est spéciale que par son nom.
- *Elle heurte l'export décidé la veille.* `_collection_d_export` répond 422 à tout album
  rangé dans plusieurs collections exportables, portée totale comprise (`AUTH-11`,
  2026-10-07). Sous une base, TOUT album vit dans deux collections pour l'administrateur et
  pour le mono-poste : chaque export d'album demanderait de nommer son titre, à moins que
  la base ne compte jamais comme un titre. Même question pour les outils de dépôt, dont la
  collection est l'unité.
- *La planche n'a toujours pas de « sortir ».* Supprimer une planche deviendrait un geste
  d'administrateur partout, y compris pour corriger son propre import. À accepter, ou à
  doubler d'un retrait de planche rattrapable.
- *Ce qui est sorti de partout s'accumule, vu du seul administrateur.* Il lui faut un écran
  pour re-ranger ou détruire (`UX-18`), sans quoi l'instance garde des scans que personne
  ne voit. Et le 409 « dernière collection » change de sens : sortir de sa dernière
  collection de travail devient permis.
- *Une migration*, et chaque chemin de création range deux fois.

**Une variante, à peser avec elle** (proposée par la session, pas par Hugo). La même
garantie sans collection : un album sorti de sa dernière collection reste en base, hors
collection, et seule une portée totale le lit — c'est ce que la docstring de
`_collection_d_export` dit déjà d'un orphelin, à vérifier par un test avant de s'y appuyer.
Elle n'a ni le coût d'export ni le double rangement ; elle renverse en revanche l'invariant
d'`AUTH-2`, « aucun album hors collection », écrit pour qu'aucune politique ne s'invente
dans le code.

**Recommandation de la session, non tranchée.** Faire la règle d'abord, la base ensuite,
comme un chantier à elle. La règle est la garde dont la base a besoin : la base n'ajoute
qu'un FAIT — tout album vit aussi là où seul l'administrateur écrit —, et « écrire partout »
fait le reste sans une ligne de plus dans les routes de suppression.

## Ce que la relecture croisée a trouvé, et ce que la règle laisse ouvert — 2026-10-08

Le code de la zone « Supprimer n'est pas sortir » (`a17b634`) a été relu AVANT son commit par
un agent neuf, lancé par la session de pilotage et non par celle qui l'avait écrit. La garde
serveur est sortie juste ; quatre constats ont bloqué le commit, et aucun n'était visible à
une suite verte et dix-neuf mutants tués.

- **La garde de planche n'était pas éprouvée sur l'album qu'elle regarde.** Le décor créait
  l'album 1 avec la planche 1 : une garde interrogeant l'id de la PLANCHE passait tout. Les
  identifiants sont désormais décroisés, et le décor l'affirme.
- **L'écran offrait « sortir » à qui ne fait que lire.** `destructible: false` a deux
  causes — on n'écrit pas partout, ou on n'écrit nulle part —, et l'écran les confondait :
  une lectrice voyait le ✕ sur TOUS les albums, pour un geste qui lui répondait
  « introuvable ». La session l'avait vu en écrivant et l'avait écarté d'un « pas pire
  qu'aujourd'hui » ; c'était faux, puisqu'elle y menait désormais. D'où `ecrivable`, à côté
  de `destructible`, et un test navigateur joué sous quatre identités au lieu d'une.
- **« Le geste se défait » était faux pour celui qui le fait.** Ranger demande d'écrire dans
  l'album : sorti de la seule collection où il y écrivait, il ne l'y range pas de nouveau
  (404, mesuré). Corrigé dans les quatre textes, gardé par un test, et l'écran fait CONFIRMER
  cet aller simple. La première confirmation ne se déclenchait que si l'album DISPARAISSAIT
  de la liste ; la relecture du delta a montré qu'on perd l'écriture sans perdre la vue dès
  qu'on lit l'album par ailleurs. Le critère est donc l'écriture, et le texte dit lequel des
  deux on perd.
- **La passe de QA se contredisait** : une case « avant de sortir l'album » placée après la
  sortie, et une précondition qui autorisait un album que `stagiaire` lisait déjà — auquel
  cas la moitié des attendus décrivaient un autre écran.

**Ce que la règle laisse ouvert, et qui n'était écrit nulle part.**

- *Épingler.* Ranger un album chez soi ne demande que d'écrire dans l'album et dans la
  collection d'arrivée, et créer une collection ne demande qu'une identité. Un simple
  co-écrivain peut donc ranger l'album dans sa collection privée : la propriétaire d'origine
  passe à `destructible: false`, reçoit 403, et ne peut pas le défaire — elle ne lit pas
  cette collection. C'est un VETO offert à tout écrivain, y compris contre le retrait d'un
  scan fautif. Mesuré par la relecture, porté à Hugo, non tranché ; la collection de base le
  rendrait sans objet, puisque seul l'administrateur y détruirait.
- *Supprimer la collection « de l'autre côté » rouvre la destruction* à qui n'écrivait que
  d'un côté : l'album n'a plus qu'une collection. C'est cohérent avec la règle — elle porte
  sur les collections où l'album VIT —, et c'est dit ici pour qu'on ne le découvre pas.
- *Un album d'une seule collection se détruit toujours par quiconque y écrit.* Inchangé :
  c'est la question du 2026-09-10.

## Le fonds : tout album appartient à l'instance — proposé le 2026-10-09, non tranché

Hugo, après avoir relu le veto de qui range un album chez soi : *« Pour moi, il doit y avoir
une sorte de back où tous les albums sont stockés. Avec leurs origines et leurs utilisations
dans différentes collections. Quitte à ce qu'on considère que tout ce qui est ajouté sur
BéDéditeur appartient à BéDéditeur, et que les gestionnaires de collection soient en mode
"j'ai des droits dessus dans la limite où j'intègre ceci dans ma collection". Je peux donc
supprimer n'importe quel album, il continuera à vivre dans BéDéditeur sans être appelé par
personne. Seuls les admins, et éventuellement une requête / consultation des éléments
disponibles, permettent d'intégrer ou réintégrer des albums dans d'autres collections. »*

**C'est la « collection de base » sans la collection**, et c'est la meilleure des deux
formes : le fonds n'est pas un rangement de plus, c'est la table des albums elle-même. Un
album rangé nulle part est « au fonds ». Il n'y a donc ni double rangement, ni titre
d'export en trop — le coût qui pesait sur la collection de base disparaît.

**Le code d'aujourd'hui se comporte déjà ainsi**, joué le 2026-10-09 par un essai jetable sur
`22cc644` : un album dont on retire tous les rangements (à la main, en base) disparaît de la
liste de qui le possédait, ses planches lui répondent 404, il ne peut ni y toucher ni le
ranger de nouveau ; l'administrateur le voit, avec ses planches intactes, l'export le refuse
(409, « rangé dans aucune collection ») et un rangement par l'administrateur le rend à qui
le lisait. Une seule chose s'y oppose aujourd'hui : le 409 « dernière collection » de
`sortir_album`, écrit pour l'invariant « aucun album hors collection ».

**Ce que le fonds règle.** La destruction devient un geste d'administrateur, partout — la
question du 2026-09-10 trouve sa réponse sans niveau de droits. « Supprimer » devient
toujours rattrapable. Le veto n'a plus d'objet, puisque personne d'autre ne détruit. Et si
intégrer un album est réservé, comme proposé, un écrivain ne garde plus par son propre
rangement l'accès à un album dont on lui a retiré la collection.

**Ce qu'il renverse, et qu'il faudra écrire.**

- *« Aucun album hors collection »* (`AUTH-2`) devient « un album hors collection est au
  fonds, lu des seuls administrateurs ». La raison de l'invariant — qu'aucune politique ne
  s'invente dans le code — est tenue autrement : la politique est écrite.
- *« Ranger demande d'écrire dans l'album et dans la collection d'arrivée »* (`AUTH-3`)
  devient un geste d'administrateur, ou le résultat d'une demande.
- *La règle codée la veille* (`a17b634`, écrire dans toutes les collections) se simplifie
  en « portée totale ». Le geste « sortir », sa confirmation et le cliquet restent.

**Ce qui frotte, et attend une décision.**

- *La consultation du fonds contre le cloisonnement.* « 404, jamais 403 » existe pour que
  personne n'apprenne ce que le corpus contient hors de sa portée. Un catalogue que les
  gestionnaires consultent dit qu'un album existe. À trancher : qui le consulte, et ce
  qu'il montre — la notice (titre, série, auteur) sans les images, sans les annotations, et
  sans dire quelle collection l'emploie ; ou rien, la demande passant par l'administrateur.
- *Intégrer un album, c'est rejoindre un travail partagé.* Régions, transcriptions et
  annotations tiennent à l'album, pas à la collection : qui l'intègre les reçoit toutes,
  et la collection qui le « supprime » laisse son travail au fonds. C'est cohérent avec
  « tout appartient à l'instance », et c'est à DIRE aux gestionnaires. Le vocabulaire
  local, lui, reste à sa collection.
- *Une planche n'a pas de fonds.* La supprimer deviendrait un geste d'administrateur, y
  compris pour retirer son propre scan fautif — accepté par Hugo le 2026-10-08 —, ou
  demande un retrait rattrapable.
- *Les origines et les emplois ne sont écrits nulle part.* `albums` ne porte que
  `date_import` ; ni qui a importé, ni où ; `collection_album` n'a ni date ni auteur, et ni
  créer, ni ranger, ni sortir, ni supprimer un album n'est journalisé. À tracer à partir du
  jour où le fonds existe ; l'existant ne se reconstitue pas.
- *Il faut un écran au fonds*, pour l'administrateur : les albums, d'où ils viennent, qui
  les emploie, lesquels ne sont appelés par personne. Rien n'étant plus détruit par les
  autres, c'est aussi là que se voit ce que l'instance garde.

**Deux précisions de Hugo, le même jour.**

- *Deux réponses à « supprimer ».* « Supprimer de la collection » et « Supprimer
  définitivement » : on importe parfois ce qui n'a rien à faire dans l'instance, et il faut
  pouvoir le dire. La seconde efface directement, ou envoie une demande à un
  administrateur. Une demande n'a pas besoin d'une messagerie : c'est un ÉTAT de l'album
  (qui, quand, pourquoi), que le fonds montre à l'administrateur et que « À regarder »
  peut porter.
- *Intégrer un album n'est pas en recevoir le travail.* Hugo refuse la phrase écrite plus
  haut (« c'est rejoindre un travail partagé ») : un album intégré doit arriver VIERGE, ou
  avec les couches de travail qu'on choisit d'y ajouter — et ces couches ont des droits,
  on ne fait pas ce qu'on veut du travail d'un autre. **Cela dépasse cette fiche.**
  Aujourd'hui un album n'a qu'UN travail : les régions tiennent à la planche,
  `annotations.region_id` est UNIQUE, la transcription est une colonne de la région, et
  une correction de token se range par région et par rang. Qui écrit dans une collection
  de l'album modifie donc le travail de l'autre. C'était VOULU — arbitrage du 2026-08-27,
  `AUTH-3` : dupliquer l'album « casserait l'analyse inter-corpus » — et c'est cette
  décision-là que la demande rouvre. Seul le vocabulaire local est déjà masqué d'une
  étude à l'autre.

Rien n'est codé ni décidé. C'est un chantier à lui, après la fusion vers `main` : **`COL-3`**, ouvert le 2026-10-09. Le fonds, les deux réponses à « supprimer », les copies de travail et l'étage du PROJET que Hugo a posé ensuite s'y décident ; cette fiche n'en garde que la trace, et les cases « veto » et « collection de base » de sa zone trouveront leur réponse là-bas. Sa règle, elle, reste vraie à l'intérieur d'un projet.

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

**Renvoi vers `AUTH-12`, posé le 2026-09-16.** Le cadrage de la gestion des comptes construit
l'écran d'attribution en ACTES — la case « L'interface se rend en cases à cocher » y trouve
son écran — et dessine LIÉS les actes que le modèle accorde ensemble, pour ne pas promettre
une finesse que le serveur n'a pas : c'est le risque que « Ce qui rouvrira la question »
décrit à propos d'`UX-4`. L'écran y lit la description des actes servie par le serveur, de
sorte que la décision d'ici — les remèdes, le niveau `contribution`, une case hors rang —
change une description et non un gabarit. Aucune décision de cette fiche n'y est prise.
`AUTH-12` note seulement que son scénario d'arrivée d'une promotion est l'un des deux
déclencheurs que « La décision du 2026-09-10 » juge intenables.
