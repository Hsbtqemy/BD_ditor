---
chantier: COL-2
statut: livré
---

# COL-2 — gérer une collection à l'écran, et pas seulement en ligne de commande

**Arrêté sur** — 2026-09-16, `de38999` : la passe de revue demandée par Hugo est faite, et ce qu'elle a établi est réparé — un seul message de collection à la fois, un message qui survit à une relecture ratée, des tests qui exigent qu'il SE VOIE. Avant elle, le même jour : le message s'affiche dans la collection où l'on a agi et *Enregistrer* ne fait plus sauter l'écran (`e07e89b`), un nouvel accès n'a plus de genre par défaut (`1677c67`). Rien n'a été écrit côté serveur. Reste une case ouverte, qui attend une mesure et non du code : les annonces sous NVDA. Les cases non cochées de la passe *Les collections dans la Bibliothèque* la portent, et supposent une pile reconstruite — elle sert encore `61662f0`.

Le déménagement lui-même était fait le 2026-09-11 (`6737b52`) : la Bibliothèque porte ce que la collection EST — la créer, la décrire, régler sa diffusion, désigner son référent, l'exporter —, l'Administration ne garde que les accès, et chaque écran dit où vit l'autre moitié.

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
- [x] **Ce qui part et ce qui reste est écrit acte par acte — 2026-09-11, avant le premier fichier touché.** Partent vers la Bibliothèque : **créer** ; **renommer**, qui devient un champ du formulaire au lieu d'un `prompt()` ; **supprimer** ; le **référent**, écrit par le propriétaire et lu par tout participant ; les **sept champs absents** ; la **pastille d'embargo** et son message, là où la date se modifie ; et le **bloc d'export de dépôt**, déplacé TEL QUEL. Sa garde — lire pour télécharger, posséder pour déposer — ne change pas ici : exporter devient un droit à part dans `DROIT-2`, qui la posera au serveur, à un seul endroit. Restent en Administration : la liste avec MON niveau ; les **accès** (accorder, changer, retirer, « jamais vu ») ; la **déclaration des administrateurs d'instance** ; la **vue des comptes**, qui devient un bloc à part au lieu d'être nichée sous les collections ; et `#col-msg`, dont `test_e2e_sante` se sert de témoin (disparu le 2026-09-16 : les messages vivent désormais dans chaque collection, cf. « Un message s'affiche là où l'on a agi », et le témoin a changé)
- [x] **La création n'exige AUCUN droit, l'édition en exige un, et c'est le même écran** — éprouvé sous une identité qui ne possède rien : elle ne voit pas la collection du décor, voit le bouton, crée, et c'est son formulaire qui s'ouvre (`test_creer_ne_demande_aucun_droit_mais_decrire_si`)
- [x] **Rien ne subsiste en double** — l'Administration a perdu la création, le renommage, la suppression, le référent, la pastille d'embargo et l'export ; le script du déménagement refusait d'écrire s'il en restait une trace, et `test_a11y_administration_collections` exige qu'aucun champ de création n'y subsiste
- [x] **Le 409 de la suppression reste lisible après le déménagement** — rendu tel quel dans le message du bloc, et la collection survit au refus (`test_supprimer_rend_le_409_et_son_compte_d_albums`). Cette case disait que le message NOMME les albums isolés : il les COMPTE (« 1 album(s) n'appartiennent qu'à cette collection… »). Mesuré en écrivant le test, dont le premier jet ne vérifiait que le mot « album » et aurait donc passé sur l'affirmation fausse
- [x] **Ce que le déménagement coûte est écrit, et dit à l'écran dans les deux sens** — chaque collection dépliée nomme l'écran où vit l'autre moitié, avec son lien, et les deux sections le disent dans leur introduction. `test_a11y_administration_collections` vérifie le renvoi vers la Bibliothèque
- [x] **Créer puis partager — le trajet que la frontière coupe en deux** — le message qui suit la création dit où faire entrer quelqu'un, avec le lien vers l'Administration (`test_a11y_bibliotheque_collections`)

### Les trois pièges du formulaire, qui ne se devinent pas
- [x] **`date_embargo` RETIENT, elle ne PROMEUT jamais, et l'écran le dit** — sous le champ, une note dit ce que la date fait. Le piège s'est révélé plus concret que prévu : un champ `type=date` affiche VIDE une date qu'il ne sait pas lire, donc le premier enregistrement l'aurait effacée. D'où un champ TEXTE, et l'envoi des seuls champs modifiés (`test_le_formulaire_n_envoie_que_ce_qui_a_change`)
- [x] **`referent_*` et `responsables` ne sont pas confondus** — le référent a son groupe, dont la note dit que c'est une ADRESSE qui ne sort d'aucun export, et qu'elle n'est pas le responsable scientifique ; les responsables ne sont pas dans le formulaire
- [x] **Le nom de la collection de repli est RÉSERVÉ, et son 422 est rendu** — le nom n'est envoyé que s'il a changé, donc le repli s'édite sans être renommé ; prendre son nom est refusé et lisible (`test_prendre_le_nom_du_repli_est_refuse_la_ou_l_on_a_agi`)

### Ce qui doit se voir à l'écran une fois fait
- [x] Depuis la Bibliothèque, un propriétaire pose `statut_diffusion` à `public` sans ouvrir de terminal, et le manifeste IIIF cesse d'emporter son `AVERTISSEMENTS.txt` — le geste exact qui a manqué le 2026-09-10 (`test_passer_public_a_l_ecran_libere_le_manifeste`)
- [x] Une valeur hors vocabulaire ne peut pas être choisie : le régime est une liste FERMÉE, dont l'accord avec `config.STATUTS_DIFFUSION` est mesuré (`test_le_formulaire_propose_exactement_le_regime_du_serveur`, trois mutants tués), et le serveur la refuserait en nommant les valeurs admises
- [x] L'échéance d'embargo dépassée est SIGNALÉE là où on la modifie — la pastille a suivi la date dans la Bibliothèque, et son message est repris sous le champ (`test_a11y_collections_embargo_echu`)
- [x] Une personne en écriture seule ne voit pas le formulaire, et une personne sans accès ne voit pas la collection — éprouvé en lecture ET en écriture, puis sous une identité sans accès (`test_le_participant_non_proprietaire_voit_le_referent`, `test_creer_ne_demande_aucun_droit_mais_decrire_si`)

### Un message s'affiche là où l'on a agi
- [x] *Bibliothèque → 📚 Collections*, trois collections dont une dépliée : prendre le nom « Collection par défaut » puis *Enregistrer* montre le refus DANS la collection dépliée, visible sans défiler depuis le bouton. Même attendu pour la confirmation d'enregistrement et pour le 409 de *Supprimer la collection* — **fait le 2026-09-16, `e07e89b`** : chaque collection dépliée porte sa ligne, sous *Enregistrer* et *Supprimer*, et les trois messages y tombent (`test_prendre_le_nom_du_repli_est_refuse_la_ou_l_on_a_agi`, `test_le_formulaire_n_envoie_que_ce_qui_a_change`, `test_passer_public_a_l_ecran_libere_le_manifeste`, `test_supprimer_rend_le_409_et_son_compte_d_albums`). Une suppression RÉUSSIE ne peut pas parler dans la collection, qui disparaît : sa confirmation prend la place qu'elle occupait dans la liste. `#col-msg` n'existe plus
- [x] Le message qui suit *+ Créer* s'affiche sous le champ de création, en haut du bloc, et non sous la liste des collections — `#col-creer-msg`, entre le champ et la liste. Situé à l'ÉCRAN, pour le refus d'un nom vide comme pour le succès (`test_la_creation_parle_sous_son_champ`, ajouté par la passe de revue : la première version de cette case citait un test qui ne lisait que l'adresse de la ligne)
- [x] *Administration → 👥 Accès aux collections* : un refus d'accorder, de changer un niveau ou de retirer un accès s'affiche dans la collection dépliée — sa ligne est sous la ligne d'ajout. Le piège n'y était pas une hypothèse : changer un niveau RECHARGE la liste même sur un refus, donc le 409 du dernier propriétaire s'effaçait aussitôt affiché si on ne le reportait pas dans la collection redessinée (`test_un_refus_d_acces_survit_au_rechargement_de_la_collection`)
- [x] Un test lit la PLACE du message et non plus seulement son texte : il tombe si le refus du nom réservé revient sous la liste — `_message_du_geste` cherche le message par son TEXTE, n'importe où dans la page, puis exige que sa boîte soit dans celle de la collection dépliée, et qu'il se VOIE : le point au début de sa première ligne doit le désigner (`elementFromPoint`). La première version se contentait des 720 px du viewport, alors que la page défile dans `main` sous un en-tête — une sonde a montré un message rogné (y = 63) qu'elle approuvait, et que le critère actuel refuse. Mutants tués, chacun sur sa raison : messages sous la liste (« hors de la collection dépliée »), report perdu dans la Bibliothèque, report perdu dans l'Administration, remplissage de la collection différé (« pas visible à l'écran »)
- [x] Le genre d'un nouvel accès est tranché, et la raison écrite : sans valeur par défaut (*+ Accorder* refuse tant que le genre n'est pas choisi), ou « Utilisateur » gardé — **tranché par Hugo le 2026-09-16 : SANS valeur par défaut**, fait dans `1677c67`. La raison : l'erreur ne se RATTRAPE pas à l'écran. Un groupe accordé en utilisateur n'ouvre rien à personne, et le seul signal est « n'a pas encore ouvert l'application », qui ne distingue pas cette faute d'un arrivant pas encore venu — et ne doit pas la distinguer (AUTH-6). Ne pouvant la signaler après coup, l'écran l'empêche d'arriver par inertie : un choix de plus, pour un geste rare. La liste démarre sur « Utilisateur ou groupe ? », et le refus dit pourquoi, dans la collection (`test_accorder_demande_de_choisir_utilisateur_ou_groupe` ; deux mutants tués, présélection rétablie et garde retirée)
- [ ] Les messages suivis d'un rechargement sont ANNONCÉS par un lecteur d'écran, ou la correction est décidée sur mesure — la confirmation d'enregistrement de la Bibliothèque et le 409 d'un niveau dans l'Administration naissent dans une ligne détruite un aller-retour plus tard, ce que la ligne unique d'avant ne faisait pas (WCAG 4.1.3). **Tranché par Hugo le 2026-09-16 : mesurer d'abord.** Attendu : les deux cases NVDA de la passe *Les collections dans la Bibliothèque* sont jouées ; si NVDA lit les deux messages, la case se coche sans code ; s'il en tait un, une région d'annonce persistante hors de la liste le porte, et les lignes visibles cessent d'être « live »

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

## Ce que la passe de recette a trouvé — 2026-09-16

La passe *Les collections dans la Bibliothèque* a été jouée 27/27 sur la pile locale. Ses
cases disent vrai ; deux choses qu'aucune ne portait se sont vues en jouant.

**Les messages tombent loin du geste.** Le refus du nom « Collection par défaut » est
arrivé, en rouge et lisible, et n'a pas été vu : il était sous toutes les collections,
avant la table des albums. Le 409 d'une suppression refusée a fait la même chose plus tard
dans la passe. Les deux se voyaient en défilant. `colMsg()` écrit dans une seule ligne pour tout
le bloc — confirmation, refus, création —, et la suite ne pouvait pas le voir : elle lit le
texte et la classe de cette ligne, jamais sa distance au bouton. Le panneau des accès de
l'Administration a la même ligne, pas encore jouée sous un refus.

**Le genre par défaut a trompé deux fois sur deux.** À la remise en état, `annotateurs` et
`etudiants` ont d'abord été accordés en « Utilisateur », puis retirés et reposés en
groupes — journal A3, événements 117 à 122. La faute a été rattrapée ; l'écran ne la
nommait pas. Le code ne pose que `jamais_vu`, qui
RAPPORTE une absence et n'en explique aucune (AUTH-6) : un nom de groupe accordé en
utilisateur et un login pas encore venu y sont indistinguables, et c'est voulu.

## Ce que la réparation a trouvé — 2026-09-16

**Le test qui lit la place a trouvé un défaut plus ancien que lui.** Sa première passe est
tombée sur les deux tests d'enregistrement : la confirmation était bien DANS la collection
redessinée, mais à y = 991 dans une fenêtre de 720. La première hypothèse — le document
ramené en haut — était fausse : `scrollY` restait à 0, la page ne défile pas. C'est
`main#corpus-body` qui défile, et la sonde l'a montré passer de 564 à 0 au rechargement.
`chargerCollections` vidait la liste, rouvrait les collections, mais ne les remplissait qu'à
l'événement `toggle`, qui arrive après : entre les deux, la zone ne mesurait plus que sa
propre hauteur, et le navigateur y ramenait le défilement. La collection qu'on venait
d'enregistrer réapparaissait 564 px plus bas, hors de la fenêtre. Ce rechargement est
antérieur au chantier et remplissait déjà les collections à `toggle` : *Enregistrer*
faisait donc sauter l'écran avant lui — déduit du code, pas rejoué sur l'ancienne version —,
et lire le seul TEXTE d'un message ne pouvait pas le voir. La collection rouverte est désormais
remplie dans la même tâche (`e07e89b`).

**L'Administration a été mesurée, pas supposée.** Son rechargement attend un aller-retour
réseau par collection rouverte, donc le même saut y semblait inévitable. Sonde avec 300 ms
de latence sur la liste des accès, huit accès et le sélecteur en haut de la fenêtre : le
défilement tient (265 avant, 265 après), le message reste visible — dans CETTE position, la seule mesurée. Le paragraphe
en tirait une explication générale, et elle était fausse (relevé par la passe de revue) : il
suffisait selon lui d'avoir la collection dans la fenêtre pour que la page ne raccourcisse
pas. En réalité le défilement est ramené dès que la hauteur perdue pendant « Chargement… »
dépasse ce qui reste de page SOUS le bas de la fenêtre — donc en bas de page, et plus
facilement sans le bloc Comptes, qu'un propriétaire non administrateur ne voit pas. Ce cas
n'est pas mesuré ; l'attendu de la case, « dans la collection dépliée », ne promet d'ailleurs
pas qu'un refus de l'Administration se voie sans défiler, et une longue liste d'accès
l'éloigne de toute façon de la ligne qu'on a réglée. Rien n'y a été changé pour cette raison. Une première sonde, défilée au
maximum, n'avait rien prouvé : elle avait sorti le sélecteur de la fenêtre AVANT le geste.

**La passe de recette portait deux avertissements que ce chantier rend faux** — « le refus
s'affiche en bas du bloc, défiler avant de conclure » et « le genre vaut Utilisateur par
défaut ». Réécrits dans `pilotage/qa/collections-bibliotheque.md`, sans toucher à une coche,
et trois cases NON cochées y sont ajoutées pour ce que l'écran doit maintenant montrer : le
refus sous les boutons, l'écran qui ne saute plus à l'enregistrement, et le refus
d'accorder sans genre.

## Ce que la passe de revue a trouvé — 2026-09-16

Demandée par Hugo après les trois premiers commits. Un relecteur qui n'avait pas écrit le
code a lu les commits en entier, et ce qu'il avançait a été vérifié dans la source ou mesuré
avant d'être corrigé. Les défauts se trouvaient en LISANT : la suite était verte, et les
mutants tués plus tôt dans la journée n'y voyaient rien.

**Établis, et réparés dans `de38999`.**
- *Des messages périmés, reposés indéfiniment.* Chaque collection ayant sa ligne, un refus
  restait affiché — et reposé à chaque rechargement — après un geste réussi dans une AUTRE
  collection, à côté d'un formulaire qui ne contenait plus le nom refusé ; « créée » restait
  en tête du bloc après la suppression de la collection créée. La ligne unique d'avant, que
  chaque geste écrasait, ne le faisait pas. Un seul message à la fois, dans les deux écrans.
- *Une confirmation qui disparaît derrière une erreur.* Si la relecture de la liste échouait
  après un enregistrement réussi, l'erreur remplaçait la liste et emportait « enregistrée ».
  Le dernier message survit désormais à l'erreur, dans la Bibliothèque et dans
  l'Administration, que la relecture rate sur la liste ou sur les accès.
- *Un test qui approuvait l'invisible.* « Dans la fenêtre » voulait dire « dans les 720 px
  du viewport » ; la page défile dans `main`, sous un en-tête. Sonde : un message rogné sous
  l'en-tête, à y = 63, passait. Le critère est devenu celui d'un œil (`elementFromPoint`),
  et la même sonde le voit refuser l'état rogné.
- *Des affirmations sans test* : la place de la confirmation d'une suppression réussie ; la
  place de la ligne de création, lue par son adresse ; la garde du genre, « prouvée » par une
  liste d'accès vide que le serveur, qui refuse lui-même un genre vide, garantissait de toute
  façon — elle se prouve maintenant par l'absence de requête. Et aucun audit axe n'avait
  jamais photographié un refus rouge ALLUMÉ : c'est fait, dans les deux thèmes.
- *Deux cases de QA injouables.* L'une visait « Collection Test » dans l'Administration, à
  une zone où la passe l'a déjà supprimée ; l'autre enregistrait une description juste après
  un refus du nom, sans remettre le nom — le 422 serait revenu, et l'écran aurait été accusé.
- *Trois textes* : un renvoi à un test renommé, une phrase datée devenue fausse sur
  `#col-msg`, et l'explication du défilement de l'Administration, dont la condition était
  fausse (cf. « Ce que la réparation a trouvé »).

Quinze mutants tués, chacun sur l'assertion qu'il visait — dont deux pour une même garde,
parce qu'une assertion qui en affirme deux doit tomber pour chacune.

**Probable, non mesuré, et c'est le seul point laissé ouvert.** Les messages suivis d'un
rechargement ne sont sans doute pas annoncés par un lecteur d'écran : la ligne `role=status`
qui les reçoit est détruite un aller-retour plus tard, pendant que le focus retombe. Un
commentaire du code affirmait le contraire ; il est corrigé. Hugo a choisi de mesurer avant
de corriger — case ouverte ci-dessus, et deux cases NVDA dans la passe.

**Vu et laissé, avec la raison.** Deux rechargements qui se chevauchent dans l'Administration
pourraient perdre un message : il faut deux gestes quasi simultanés dans deux collections,
hypothèse non éprouvée. Et après *Enregistrer*, le focus de la Bibliothèque retombe sur la
page : c'était déjà le cas avant ce chantier.

**La pile de recette sert `61662f0`**, une image du 2026-09-14, lue sur le conteneur. Les
cases neuves de la passe n'y sont pas jouables avant reconstruction, ce que la passe dit en
tête.

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

**Renvoi vers `AUTH-12`, posé le 2026-09-16.** Le cadrage de la gestion des comptes propose
de rouvrir la frontière tranchée ici deux fois le 2026-09-10 (sa décision 2) : régler qui
entre dans UNE collection depuis cette collection, dans la Bibliothèque, l'Administration
gardant la vue transverse des personnes et des groupes. La raison est la demande elle-même,
qui nomme la répartition entre Bibliothèque et Administration comme source de la complexité.
Rien n'est tranché. Si la frontière change, la case « Où vit l'écran » garde son état du
2026-09-10 et reçoit un renvoi daté, plutôt que d'être réécrite.
