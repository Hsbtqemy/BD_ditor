---
chantier: COL-2
statut: livré
---

# COL-2 — gérer une collection à l'écran, et pas seulement en ligne de commande

**Arrêté sur** — 2026-09-11, `6737b52` : le déménagement est fait. La Bibliothèque porte ce que la collection EST — la créer, la décrire, régler sa diffusion, désigner son référent, l'exporter —, l'Administration ne garde que les accès, et chaque écran dit où vit l'autre moitié. Rien n'a été écrit côté serveur.

**Point de départ** — 2026-09-10, trouvé pendant la passe de QA d'EXP-1. Une case demandait
une collection déclarée `public` ; l'écran d'Administration **AFFICHE** `statut_diffusion`
(« sans régime ») et ne permet pas de le changer. Il a fallu un troisième terminal et
`tools/gerer_collections.py modifier 1 --statut public`. Décidé dans la foulée : il faut une
interface, **probablement dans la Bibliothèque**.

**Rien à écrire côté serveur, et c'est le seul point sur lequel le cadrage d'origine
tenait.** `PATCH /api/collections/{id}` existe, il est **gardé** (`_get_collection(...,
administrer=True)`, donc propriétaire), il valide le vocabulaire contrôlé de
`statut_diffusion` (422 nommant les valeurs admises) et il protège le nom réservé de la
collection de repli. Dix champs sont déjà acceptés par `CollectionUpdate` : `nom`,
`description`, `licence_defaut`, `base_legale`, `statut_diffusion`, `date_embargo`,
`date_debut`, `date_fin`, `referent_nom`, `referent_contact`.

**Mais « plus petit qu'il n'en a l'air » était FAUX, et l'a été jusqu'au 2026-09-10.**
Cette fiche a été écrite, puis arbitrée une première fois, sans que personne ouvre
`static/administration.js`. Mesuré depuis : le panneau **👥 Collections** ne fait pas
qu'AFFICHER — il **crée** une collection (`POST /api/collections`), la **renomme**
(`PATCH`, champ `nom`), la **supprime** (`DELETE`), gère ses **accès**, et pose son
**référent** (`referent_nom`, `referent_contact`). Trois des dix champs sont donc déjà
éditables à l'écran, plus l'existence même de l'objet.

Il ne manque que **sept champs** : `description`, `date_debut`, `date_fin`, et le bloc qui
compte — `statut_diffusion`, `date_embargo`, `licence_defaut`, `base_legale`, c'est-à-dire
ce qui décide de ce qui SORT de l'instance. Et comme la frontière retenue place ces
champs-là dans la Bibliothèque, **le chantier n'est pas un ajout : c'est un
DÉPLACEMENT** — plus gros que ce qui était annoncé, et portant sur du code qui marche.

## Reste

### Trancher, avant d'écrire une ligne
- [x] **Où vit l'écran, et la raison est écrite — tranché le 2026-09-10 : la BIBLIOTHÈQUE.** La frontière, qui est l'attendu de cette case et non la préférence : **_qui entre_ relève de l'INSTANCE et vit dans Administration ; _ce que la collection EST_ relève du CORPUS et vit dans la Bibliothèque.** Le panneau **👥 Collections** (AUTH-3) garde donc les accès, et les dix champs de `CollectionUpdate` — régime de diffusion compris — vont à la Bibliothèque. La phrase se vérifie sur le cas limite qui la teste le mieux : `statut_diffusion` décide de ce qui SORT, ce qui sonne administratif, mais il décrit ce que la collection EST vis-à-vis du dehors et se lit à côté de sa licence et de son embargo — pas à côté de la liste de ses membres. Cohérent avec UX-10, dont Administration porte « ce qui porte sur l'INSTANCE et non sur un album ». **Arbitrée DEUX FOIS le même jour, et la seconde est celle qui vaut** : la première l'a été sans avoir lu `static/administration.js`, donc sans savoir que le panneau éditait déjà le nom — « ce que la collection EST » — et le référent, qui n'est pas « qui entre ». La frontière était contredite dès le premier jour par du code qui marche. Remise à l'équipe avec la mesure, elle a été TENUE : la Bibliothèque reçoit les sept champs manquants **et** récupère le nom, la création, la suppression et le référent ; Administration ne garde que les accès et la vue des comptes

- [x] **Quels champs entrent dans le formulaire — tranché le 2026-09-11.** Trois groupes, et c'est l'ordre du formulaire : **descriptif** (`nom`, `description`, `date_debut`, `date_fin`), **diffusion** (`statut_diffusion`, `date_embargo`, `licence_defaut`, `base_legale`), **référent** (`referent_nom`, `referent_contact`). Reste DEHORS : `responsables`, qui n'est pas dans `CollectionUpdate` — scientifique, porteur d'ORCID, parti au dépôt. Le formulaire n'envoie que les champs MODIFIÉS : le PATCH est partiel côté serveur, et un formulaire qui renverrait tout réécrirait une date d'embargo illisible par la valeur vide d'un champ — une levée d'embargo déguisée en enregistrement
- [x] **La garde de l'écran est celle de l'ACTE, et elle est nommée** — trois questions dans le même bloc, et c'est le serveur qui les tranche toutes : créer demande une identité, décrire, renommer et supprimer demandent `administrable`, lire demande la seule portée. Écrit en tête du bloc dans `static/corpus.js`, éprouvé par `test_creer_ne_demande_aucun_droit_mais_decrire_si` et `test_le_participant_non_proprietaire_voit_le_referent`
- [x] **Le sort de `tools/gerer_collections.py` est décidé et écrit** — il reste, pour l'amorçage et les responsables scientifiques, que l'écran ne couvre pas. Sa docstring disait « l'écran ne couvre pas licence ni embargo » ; c'est corrigé, et elle dit la seule règle commune aux deux portes (`config.STATUTS_DIFFUSION`) — et que toute autre règle ajoutée à l'une ne vaut pas pour l'autre

### Le déménagement, et ce qu'il coûte
- [x] **Ce qui part et ce qui reste est écrit acte par acte — 2026-09-11, avant le premier fichier touché.** Partent vers la Bibliothèque : **créer** ; **renommer**, qui devient un champ du formulaire au lieu d'un `prompt()` ; **supprimer** ; le **référent**, écrit par le propriétaire et lu par tout participant ; les **sept champs absents** ; la **pastille d'embargo** et son message, là où la date se modifie ; et le **bloc d'export de dépôt**, déplacé TEL QUEL. Sa garde — lire pour télécharger, posséder pour déposer — ne change pas ici : exporter devient un droit à part dans `DROIT-2`, qui la posera au serveur, à un seul endroit. Restent en Administration : la liste avec MON niveau ; les **accès** (accorder, changer, retirer, « jamais vu ») ; la **déclaration des administrateurs d'instance** ; la **vue des comptes**, qui devient un bloc à part au lieu d'être nichée sous les collections ; et `#col-msg`, dont `test_e2e_sante` se sert de témoin
- [x] **La création n'exige AUCUN droit, l'édition en exige un, et c'est le même écran** — éprouvé sous une identité qui ne possède rien : elle ne voit pas la collection du décor, voit le bouton, crée, et c'est son formulaire qui s'ouvre (`test_creer_ne_demande_aucun_droit_mais_decrire_si`)
- [x] **Rien ne subsiste en double** — l'Administration a perdu la création, le renommage, la suppression, le référent, la pastille d'embargo et l'export ; le script du déménagement refusait d'écrire s'il en restait une trace, et `test_a11y_administration_collections` exige qu'aucun champ de création n'y subsiste
- [x] **Le 409 de la suppression reste lisible après le déménagement** — rendu tel quel dans le message du bloc, et la collection survit au refus (`test_supprimer_rend_le_409_et_son_compte_d_albums`). Cette case disait que le message NOMME les albums isolés : il les COMPTE (« 1 album(s) n'appartiennent qu'à cette collection… »). Mesuré en écrivant le test, dont le premier jet ne vérifiait que le mot « album » et aurait donc passé sur l'affirmation fausse
- [x] **Ce que le déménagement coûte est écrit, et dit à l'écran dans les deux sens** — chaque collection dépliée nomme l'écran où vit l'autre moitié, avec son lien, et les deux sections le disent dans leur introduction. `test_a11y_administration_collections` vérifie le renvoi vers la Bibliothèque
- [x] **Créer puis partager — le trajet que la frontière coupe en deux** — le message qui suit la création dit où faire entrer quelqu'un, avec le lien vers l'Administration (`test_a11y_bibliotheque_collections`)

### Les trois pièges du formulaire, qui ne se devinent pas
- [x] **`date_embargo` RETIENT, elle ne PROMEUT jamais, et l'écran le dit** — sous le champ, une note dit ce que la date fait. Le piège s'est révélé plus concret que prévu : un champ `type=date` affiche VIDE une date qu'il ne sait pas lire, donc le premier enregistrement l'aurait effacée. D'où un champ TEXTE, et l'envoi des seuls champs modifiés (`test_le_formulaire_n_envoie_que_ce_qui_a_change`)
- [x] **`referent_*` et `responsables` ne sont pas confondus** — le référent a son groupe, dont la note dit que c'est une ADRESSE qui ne sort d'aucun export, et qu'elle n'est pas le responsable scientifique ; les responsables ne sont pas dans le formulaire
- [x] **Le nom de la collection de repli est RÉSERVÉ, et son 422 est rendu** — le nom n'est envoyé que s'il a changé, donc le repli s'édite sans être renommé ; prendre son nom est refusé et lisible (`test_prendre_le_nom_du_repli_est_refuse_et_lisible`)

### Ce qui doit se voir à l'écran une fois fait
- [x] Depuis la Bibliothèque, un propriétaire pose `statut_diffusion` à `public` sans ouvrir de terminal, et le manifeste IIIF cesse d'emporter son `AVERTISSEMENTS.txt` — le geste exact qui a manqué le 2026-09-10 (`test_passer_public_a_l_ecran_libere_le_manifeste`)
- [x] Une valeur hors vocabulaire ne peut pas être choisie : le régime est une liste FERMÉE, dont l'accord avec `config.STATUTS_DIFFUSION` est mesuré (`test_le_formulaire_propose_exactement_le_regime_du_serveur`, trois mutants tués), et le serveur la refuserait en nommant les valeurs admises
- [x] L'échéance d'embargo dépassée est SIGNALÉE là où on la modifie — la pastille a suivi la date dans la Bibliothèque, et son message est repris sous le champ (`test_a11y_collections_embargo_echu`)
- [x] Une personne en écriture seule ne voit pas le formulaire, et une personne sans accès ne voit pas la collection — éprouvé en lecture ET en écriture, puis sous une identité sans accès (`test_le_participant_non_proprietaire_voit_le_referent`, `test_creer_ne_demande_aucun_droit_mais_decrire_si`)

## Ce que le déménagement a trouvé — 2026-09-11

**Un piège qui aurait été muet.** `openModal()` masquait la ligne d'ajout des
contributions par `$(".contrib-add")`, c'est-à-dire la PREMIÈRE ligne de cette classe dans
la page — déjà celle de l'appartenance, pas celle des contributions. Le formulaire de
création de collection, posé au-dessus de la table, devenait cette première ligne : il
aurait disparu à chaque « Nouvel album », sans une erreur. La ligne est désormais désignée
par son identifiant, et `test_nouvel_album_ne_masque_pas_la_creation_de_collection` tombe
si l'on revient au sélecteur de classe.

**La question de l'export a ouvert un chantier.** En demandant où le bloc d'export
déménageait, on a mesuré que toute personne qui LIT une collection pouvait en exporter le
contenu, texte relevé compris — dix portes. L'équipe a fait d'« exporter » un droit à part :
`DROIT-2`. Le bloc a donc déménagé TEL QUEL, extrait de la version commitée plutôt que
recopié, et sa garde sera posée là-bas, au serveur, pour les dix portes à la fois.

**Aucun fichier de style touché.** Le formulaire réutilise les classes existantes ;
`static/style.css` restait libre pour la session voisine, qui y travaillait au même moment.

## Contexte

**Ce que l'écart coûte aujourd'hui.** Le régime de diffusion décide de ce qui quitte
l'instance (DROIT-1) : il est ce que le manifeste DÉCLARE, et ce qui retient ou libère les
images au dépôt. Il est affiché sur un écran d'administration et modifiable nulle part
ailleurs qu'en ligne de commande, sur une machine qui a le dépôt et la base sous la main.
Un administrateur qui le LIT essaiera de le changer — c'est ce qui s'est produit le
2026-09-10, en pleine passe de QA.

**Pourquoi ce n'est pas un simple oubli.** La ligne de commande était le bon outil tant que
les collections se créaient au montage d'un corpus, par la personne qui l'hébergeait. Depuis
AUTH-3, une collection est un espace de travail qu'on ouvre pour une étude, et depuis
AUTH-7 les comptes se gèrent sans SSH. L'écrit est resté en arrière du modèle.

**Voisinage.** `AUTH-3` (le panneau des accès, déjà dans Administration), `AUTH-4` (le
référent, et la garde d'écran qui se pose sur l'acte), `DROIT-1` (ce que le régime borde, et
ce qu'il ne borde pas), `EXP-1` (l'export de dépôt, dont la QA a révélé le manque),
`UX-10` (l'administration rassemblée), `COL-1` (l'incubateur, qui fera circuler le travail
ENTRE collections et supposera qu'on sache les décrire).
