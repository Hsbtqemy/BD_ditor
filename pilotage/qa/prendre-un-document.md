---
passe: Prendre un document, rejoindre un travail
chantier: COL-3
duree: 90 min
derniere: —
---

# QA — la tranche 3a : la collection de base, prendre du fonds, prendre dans le projet, les demandes de cinq genres

**Écrite le 2026-10-18 sur `53a4b6a`, non jouée.** Elle porte sur l'écran de la tranche 3a de
`COL-3` — `f4a8d98` (l'Administration : cinq genres de demandes, la base et le fonds du
projet, l'accès tenu par le projet), `f8752c4` (la Bibliothèque : prendre du fonds, prendre
dans le projet, « Sur les collections », les demandes reçues) et leurs corrections
(`3ab0cd1`, `bcb6c87`) —, et sert les cases de la fiche `COL-3` que « la 3a ne part pas en
production sans » : la position des membres, l'accès tenu par le projet, les genres neufs.

**Ce que les tests couvrent déjà — ne pas le refaire ici** : qui peut prendre, rejoindre et
répondre, sous sept identités ; les refus et leurs codes ; ce qu'un second projet n'apprend
pas du premier ; les mots de chaque genre (tables de vérité de `lib/suppression.js` et
`lib/bibliotheque.js`). **Ce qui se regarde ici** : si chacun trouve son geste là où il le
cherche, si l'écran dit avant d'agir ce que le geste fera, et si la réponse se lit là où l'on
a agi — sous l'identité de qui agit, puis de qui répond.

**Ce que la passe ne juge pas** : la pagination des notices (la recette n'a que trois
documents : une seule page) ; les consentements à plusieurs signatures, écartés pour la 3a ;
le double compte d'un document dont on lit deux copies dans la Recherche et l'Exploration
(tranche 4, écrit dans le guide) ; la Bibliothèque en calque elle-même (`bibliotheque-en-calque`).

Les zones se jouent DANS L'ORDRE : la passe construit, zone après zone, six demandes de cinq
genres, puis les fait répondre. Dans les cases, **A1** désigne la copie d'« Annee_lievre-1 »
que l'administrateur prend pour « Projet QA », **E1** celle d'« esther v1 » qui y entre sur
demande — deux noms de travail, que l'écran n'affiche pas.

## Reste

### Le décor — `C:\temp\bd-recette\etat-de-base.ps1`, puis compte `admin-bd`, Administration

- [ ] `C:\temp\bd-recette\etat-de-base.ps1 restaurer` répond « bd-app : healthy » (ou « running ») — la passe crée deux projets, des copies, des demandes : la dernière zone rend la recette
- [ ] Sous `admin-bd` (une fenêtre privée par compte, pour toute la passe), `https://bd.127-0-0-1.sslip.io/administration?vue=instance` : « 🏷️ Version servie » affiche `53a4b6a` ou plus récent

### Un projet naît avec sa base, et la question de ses membres — compte `admin-bd`, Administration, vue « Projets »

- [ ] **+ Nouveau projet** : sous *Nom* et *Pourquoi ce projet existe*, un groupe « Ce que sa collection de base ouvre aux membres » de trois boutons radio — « ouverte » (coché), « en lecture », « protégée » —, chacun suivi de sa phrase (« Les membres du projet y annotent et y organisent les albums, comme ses responsables. », « Les membres voient ses albums sans y écrire ; … », « Personne d'autre que ses responsables — … ») ; dessous, « Le projet naît avec sa collection de base, de son nom : ce qu'il prend au fonds y arrive. … »
- [ ] Nom « Projet QA », « ouverte » laissé coché, *+ Créer le projet* : « « Projet QA » créé, avec sa collection de base : faites-y entrer quelqu'un dans sa fiche ; il prend ensuite au fonds depuis la Bibliothèque. » ; la fiche dit « 1 collection » et « sans responsable » ; partie *Collections* : « Projet QA » suivie de la puce « base »
- [ ] Partie « Ce que la base ouvre aux membres · Projet QA » : les trois radios sous « Position des membres dans « Projet QA » », « ouverte » cochée, et « La base n'ouvre qu'elle-même : aucune autre collection du projet ne suit. … » ; partie *Au fonds* : « Au fonds · 0 demande », « Aucune demande. « + Prendre du fonds… », dans la Bibliothèque, en dépose une. », puis « Copies gardées au fonds · 0 » et « Aucune. »
- [ ] *Qui y entre* : *Faire entrer* → « Un compte, ou un groupe absent de la liste… », `proprio`, « Compte », *+ Faire entrer*, puis passer sa ligne à « responsable du projet » ; de même `stagiaire`, laissé « membre » : « sans responsable » quitte la fiche, et la note dit « Entrer dans le projet n'ouvre que sa collection de base, selon ce que le projet a choisi : chaque autre collection garde son « Qui entre ». »

### Changer la position des membres — comptes `admin-bd` (fiche de « Projet QA ») et `stagiaire`

- [ ] Cocher « en lecture » : rien ne s'applique ; une phrase paraît, « Resserrer n'efface aucun travail : ce que les membres ont fait dans « Projet QA » y reste. Ils la liront encore, sans plus y écrire. », avec « Appliquer : base en lecture » et « Annuler » ; *Annuler* : « ouverte » est de nouveau cochée, la phrase disparaît
- [ ] Cocher « protégée » : « Resserrer n'efface aucun travail : … Ils ne la verront plus, sauf à y être entrés par « Qui entre ». » ; *Appliquer : base protégée* : « La base « Projet QA » est désormais protégée aux membres du projet. », et « protégée » reste cochée après F5
- [ ] Sous `stagiaire`, Bibliothèque, bande du haut, *Projet* → « Projet QA » : la liste des collections dit « Aucune collection ouverte pour vous dans le projet « Projet QA ». Créez-en une : vous en serez propriétaire. »
- [ ] Sous `admin-bd`, cocher « ouverte » : « Ouvrir donne à 1 entrée du projet le droit d'annoter et d'organiser les albums dans « Projet QA », dès maintenant. » ; *Appliquer : base ouverte* : « … désormais ouverte aux membres du projet. »
- [ ] Sous `stagiaire`, Bibliothèque rechargée : « Projet QA » paraît dans « Collections », marquée « base » ; sa fiche dit « ✓ annoter et organiser » ; l'onglet *Albums* « Aucun album dans cette collection : ce que le projet prendra au fonds arrivera ici. » ; l'onglet *Qui entre* « Seul un propriétaire de la collection voit et règle qui y entre. » — membre, il annote sans voir qui entre

### « Qui entre » d'une base, en deux groupes — comptes `proprio`, `stagiaire`, `admin-bd`

- [ ] Sous `proprio`, Bibliothèque, *Projet* → « Projet QA », nom « Projet QA » (onglet *Qui entre*) : un groupe « Par le projet · 2 » — `proprio` « responsable du projet », `stagiaire` « membre du projet », chacun avec ses actes en clair, SANS case, sans ✕, et « Régler dans le projet ↗ » — puis « Entrés ici · 0 » et « Personne encore : « Faire entrer » ajoute ici, hors du projet. »
- [ ] Sous le tableau, « C'est la collection de base du projet « Projet QA » : ses responsables en sont propriétaires, et ses membres y entrent selon ce que le projet a choisi. … » ; « Régler dans le projet ↗ » ouvre l'Administration sur la fiche de « Projet QA » (vue « Projets »)
- [ ] Sous `proprio`, fiche de « Projet QA », en-tête : la puce « collection de base », « ✓ décider qui entre » ; onglet *Description*, en bas : « La collection de base ne se supprime pas : elle part avec le projet. », et aucun bouton « Supprimer la collection… »
- [ ] Sous `proprio`, même onglet, *Faire entrer* → « Un compte, ou un groupe absent de la liste… », `lectrice`, « Compte », *+ Faire entrer* : « Entrés ici · 1 », et SA ligne porte des cases et un ✕, quand celles de « Par le projet · 2 » n'en ont aucun ; la retirer par son ✕ : « Entrés ici · 0 » revient
- [ ] Sous `admin-bd`, Administration, « Comptes et groupes », axe *Collections*, fiche de « Projet QA » : son *Qui entre* montre les mêmes deux groupes ; axe *Comptes*, fiche de `stagiaire`, partie *Collections* : « Projet QA » suivi de son accès et de « — par le projet « Projet QA » »

### « + Prendre du fonds… » : au responsable et à l'administrateur seulement — comptes `proprio`, `stagiaire`

- [ ] Sous `proprio`, Bibliothèque, projet « Projet QA », rien de choisi : la fiche du projet porte, en tête, le bouton « + Prendre du fonds… » ; la fiche de « Projet QA », onglet *Albums*, porte au-dessus du tableau « + Prendre du fonds… » ET « + Prendre dans le projet… »
- [ ] Sous `proprio`, *Projet* → « Projet principal » : la fiche du projet n'a PAS « + Prendre du fonds… », et l'onglet *Albums* de « Collection Test » n'offre que « + Prendre dans le projet… » — posséder une collection ne suffit pas, il faut être responsable du projet
- [ ] Sous `stagiaire`, projet « Projet QA » : ni la fiche du projet ni l'onglet *Albums* de « Projet QA » n'offrent « + Prendre du fonds… » ; l'onglet n'offre que « + Prendre dans le projet… »

### Demander des documents au fonds — compte `proprio`, Bibliothèque, projet « Projet QA »

- [ ] Fiche du projet, « + Prendre du fonds… » : un panneau « Prendre du fonds pour « Projet QA » » s'ouvre dessous, le champ « Titre, série, auteur… » a le focus ; *Dans* propose « Projet QA (base) », présélectionnée ; la liste montre trois notices — « Annee_lievre-1 », « Eau-terre », « esther v1 » — et « 3 notices · page 1 / 1 », ‹ et › éteints
- [ ] Taper `terre` : seule « Eau-terre » reste, « 1 notice · page 1 / 1 » ; vider le champ
- [ ] Sous la liste : « Pourquoi ces documents ? (obligatoire : l'administrateur le lira) », un bouton « Demander la sélection » éteint, « Fermer », et « Une seule demande part à un administrateur ; un document dont vous lisez déjà une copie dans le projet vous est donné sans attendre, en copie vierge. »
- [ ] Cocher « esther v1 » puis « Eau-terre » : le bouton dit « Demander 2 documents » ; le cliquer, motif VIDE : sous le panneau, en rouge, « Dites pourquoi : une demande sans motif ne se lit pas. », et rien ne part (aucune ligne ne dit « demandé »)
- [ ] Taper un motif, « Demander 2 documents » : chaque ligne cochée dit « demandé à un administrateur », et sous le panneau « 2 documents sont demandés à un administrateur : vous en suivrez la réponse dans la fiche du projet. » ; le focus est sur le titre du panneau
- [ ] Dans la bande d'outils (à côté des chiffres du corpus, sous la navigation), un lien « 1 demande au fonds, en attente » a paru ; la bande du haut, elle, n'a rien gagné
- [ ] Cocher de nouveau « Eau-terre », un motif, « Demander 1 document » : la ligne dit « refusé : Déjà demandé pour cette collection : la demande attend sa réponse. », et le message « 1 document refusé : la raison est sur sa ligne. » ; *Fermer* : le panneau se referme et le focus revient sur « + Prendre du fonds… »
- [ ] Cliquer « 1 demande au fonds, en attente » : l'Administration s'ouvre sur la fiche de « Projet QA » ; « Au fonds · 1 demande » montre « 2 documents pour « Projet QA » », « demandée le JJ/MM/AAAA » et l'état « en attente »

### L'administrateur prend, et répond à une partie — compte `admin-bd`

- [ ] Administration, « À faire » : une ligne « ENTRÉE DE DOCUMENTS », « … demande l'entrée de « … » et « … » dans « Projet QA » » (les deux titres), « le JJ/MM/AAAA · projet « Projet QA » » ; *Répondre* : le motif, « Chaque document accepté entre dans « Projet QA » avec une copie de travail vierge, créée au nom de … Un document déjà dans le projet y reçoit une seconde copie. », une ligne par document avec « Accepter » et « Refuser », puis « Tout accepter (2) » et « Refuser le reste »
- [ ] « Accepter » sur la ligne d'« esther v1 » : la demande reste dépliée, la ligne d'« esther v1 » dit « entré dans « Projet QA » » à la place de ses boutons, « « esther v1 » entre dans « Projet QA », en copie vierge. » se lit sous elle, et le bouton global dit « Tout accepter (1) ». Ne pas répondre pour « Eau-terre » ici
- [ ] Bibliothèque, *Projet* → « Projet QA », « + Prendre du fonds… » : AUCUN champ de motif ; la phrase dit « Chaque document entre tout de suite, en copie vierge. » ; « esther v1 » porte « déjà dans ce projet » ; cocher « Annee_lievre-1 » : le bouton dit « Prendre 1 document »
- [ ] « Prendre 1 document » : la ligne dit « fait », et « Fait : 1 document a désormais une copie de travail vierge dans « Projet QA ». » ; la liste des albums montre « Annee_lievre-1 » (A1) et « esther v1 » (E1), chacun « Projet QA »

### Une seconde copie, et la supprimer — compte `proprio`, Bibliothèque, projet « Projet QA »

- [ ] « + Prendre du fonds… » : « Annee_lievre-1 » et « esther v1 » portent « déjà dans ce projet », dont l'infobulle dit qu'une case cochée en prend une seconde copie, vierge ; cocher « Annee_lievre-1 », SANS motif, « Demander 1 document » : la ligne dit « fait » — aucune demande, la copie entre tout de suite
- [ ] La liste des albums montre maintenant DEUX lignes « Annee_lievre-1 » ; « Supprimer… » sur chacune : les deux panneaux disent « Ses images restent : une autre copie de ce document les emploie. », sans dire où ; l'un propose « Supprimer définitivement » (« Efface tout de suite cette copie et le travail fait dessus : vous l'avez créée, et personne d'autre n'y a travaillé. … »), l'autre la demande (« D'autres s'en servent, ou ce n'est pas vous qui avez créé cette copie : … »)
- [ ] Sur celle qui propose l'effacement : « Supprimer définitivement » ; la ligne quitte la liste ; la ligne « Annee_lievre-1 » qui reste s'ouvre sur ses planches, vignettes visibles — les images n'ont pas été effacées avec la sœur

### Prendre dans le projet : rejoindre, ou une copie vierge — compte `stagiaire`, Bibliothèque, projet « Projet QA »

- [ ] « + Créer une collection », nom « Carnet QA », *Créer* : « « Carnet QA » créée — vous en êtes propriétaire. … » (être membre du projet suffit pour y créer)
- [ ] Fiche de « Carnet QA », onglet *Albums*, « + Prendre dans le projet… » : « Prendre dans « Projet QA » pour « Carnet QA » », « 2 albums du projet que vous lisez, hors « Carnet QA » », et deux lignes, « Annee_lievre-1 · dans « Projet QA » » et « esther v1 · dans « Projet QA » », chacune avec « Rejoindre » et « Copie vierge » ; au survol, « Rejoindre » dit « … qui tient toutes ses collections doit l'accepter. Le travail sera partagé. », et « Copie vierge » « Une seconde copie, images seules, sans le travail de l'autre ; à votre nom, tout de suite. … »
- [ ] « Rejoindre » sur « Annee_lievre-1 » : ses deux boutons laissent place à « demandé à son propriétaire », et « Demandé à son propriétaire : « Annee_lievre-1 » rejoindra « Carnet QA » si la réponse est oui. Rien ne change d'ici là. »
- [ ] F5 (la fiche de « Carnet QA » se rouvre sur *Albums*), puis « + Prendre dans le projet… » : la ligne « Annee_lievre-1 » dit « rejoindre demandé » à la place de « Rejoindre », et garde « Copie vierge » ; cliquer « Copie vierge » : « fait », et « Fait : « Annee_lievre-1 » a une seconde copie, vierge, dans « Carnet QA », à votre nom. Ce qui se fera dans l'une n'arrivera pas dans l'autre. » ; le tableau de « Carnet QA » montre « Annee_lievre-1 »

### Cocher et décocher « Sur les collections » — compte `stagiaire`, Bibliothèque, projet « Projet QA »

- [ ] Fiche d'« esther v1 » (E1), *Sur les collections* : « Projet QA » cochée, « Carnet QA » non cochée ; cocher « Carnet QA » : « Pas rangé : rejoindre ce travail se demande au propriétaire de ses collections. La demande est partie. », et la case devient INDÉTERMINÉE (ni cochée ni vide), éteinte, suivie de « demandé » — l'album n'est pas rangé, sa ligne dit toujours « Projet QA » seule
- [ ] Ouvrir la ligne « Annee_lievre-1 » qui dit « Carnet QA » (la copie vierge) : *Sur les collections*, décocher « Carnet QA » ; une confirmation dit « Supprimer « Annee_lievre-1 » de « Carnet QA » ? », « C'est sa dernière collection : la copie de travail est gardée au fonds, avec tout son travail. Un administrateur peut la rendre. Vous ne le verrez plus, et ne pourrez pas l'y ranger de nouveau vous-même. »
- [ ] L'accepter : la fiche se referme, « « Annee_lievre-1 » n'est plus dans « Carnet QA ». Sa copie de travail est gardée au fonds. » s'affiche, et il ne reste qu'une ligne « Annee_lievre-1 » (A1, « Projet QA »)

### Demander à rendre une copie gardée — compte `proprio`

- [ ] Bibliothèque, projet « Projet QA », « + Prendre du fonds… » : la notice « Annee_lievre-1 » porte « une copie de ce projet est gardée au fonds — la demander à rendre ↗ » ; ce lien ouvre la fiche de « Projet QA » dans l'Administration ; *Fermer* le panneau d'abord si l'on revient
- [ ] Fiche de « Projet QA » : « Copies gardées au fonds · 1 », la ligne « Annee_lievre-1 » (« gardée depuis le JJ/MM/AAAA ») et « Demander à la rendre… » ; la note dit « … La rendre se demande à un administrateur, qui répond « Rendre » ou « Garder au fonds ». »
- [ ] « Demander à la rendre… » : à sa place, une liste qui propose « Projet QA (base) », « Demander » et « Annuler » ; « Demander » : « Votre demande est partie à un administrateur : il répondra « Rendre » ou « Garder au fonds ». », et la ligne dit « retour demandé le JJ/MM/AAAA »
- [ ] Bibliothèque rechargée, projet « Projet QA », bande d'outils : le lien dit « 2 demandes au fonds, en attente »

### Deux suppressions demandées — comptes `stagiaire`, `admin-bd`, `proprio`

- [ ] Sous `stagiaire`, Bibliothèque, projet « Projet QA », « Supprimer… » sur « Annee_lievre-1 » (A1), seconde carte : « D'autres s'en servent, ou ce n'est pas vous qui avez créé cette copie : la demande part à un administrateur, qui décide. Ses images restent : une autre copie de ce document les emploie. Rien n'est effacé d'ici là. » ; un motif, la case de certification, « Envoyer la demande » : la ligne porte « suppression demandée par vous »
- [ ] Sous `admin-bd`, Administration, « + Nouveau projet » « Vide QA » (une position quelconque), *+ Créer le projet* ; *Qui y entre* : `proprio`, « Compte », *+ Faire entrer*, puis « responsable du projet »
- [ ] Sous `proprio`, Administration, vue « Projets », fiche de « Vide QA », partie *Ce projet* : « Demander sa suppression… », un motif, « Envoyer la demande » : la puce « suppression demandée le JJ/MM/AAAA » remplace le bouton

### « À faire » : cinq genres, chacun ses boutons — compte `admin-bd`, Administration, vue « À faire »

- [ ] Sous « Demandes », six lignes, la plus ancienne d'abord : l'entrée de documents, le rejoindre d'« Annee_lievre-1 », celui d'« esther v1 », le retour, la suppression d'« Annee_lievre-1 », celle de « Vide QA » ; chacune dit son genre en petites capitales — « ENTRÉE DE DOCUMENTS », « REJOINDRE UN TRAVAIL », « RENDRE UNE COPIE GARDÉE », « SUPPRIMER UN DOCUMENT », « SUPPRIMER UN PROJET »
- [ ] Chaque ligne porte un filet de couleur à gauche, le même pour un même genre et différent d'un genre à l'autre : bleu (entrée), cyan (rejoindre), violet (retour), rouge (document), ambre (projet)
- [ ] *Répondre* sur le premier rejoindre : « … demande à ranger aussi « Annee_lievre-1 » dans « Carnet QA » », « Accepter range aussi cette copie dans « Carnet QA » : le travail est alors partagé entre ces collections, … », et deux boutons « Accepter : ranger aussi dans « Carnet QA » » et « Refuser » — jamais « Détruire » ; *Replier* sans répondre : c'est au propriétaire de le faire
- [ ] *Répondre* sur le retour : « … demande à rendre « Annee_lievre-1 » à « Projet QA » », « Copie de « Projet QA », gardée au fonds avec son travail. Elle était sortie de « Carnet QA » : la rendre ailleurs ouvre son travail à ceux qui entrent dans « Projet QA ». … », « Rendre à « Projet QA » » et « Garder au fonds »
- [ ] « Rendre à « Projet QA » » : « « Annee_lievre-1 » est rendu à « Projet QA », avec tout son travail. » en tête du bloc, la ligne part, et le focus est sur le titre « À faire »
- [ ] *Répondre* sur la suppression d'« Annee_lievre-1 » : le motif, « Certifié par … le JJ/MM/AAAA : ces données ne sont pas importantes. », « Copie créée par … », puis « Détruire » (rouge) et « Garder » ; « Détruire » : la confirmation dit « Détruire cette copie de « Annee_lievre-1 » ? Tout le travail fait dessus est effacé. Ses images restent : une autre copie de ce document les emploie. Irréversible. » ; *Annuler* : rien ne part
- [ ] « Garder » : « « Annee_lievre-1 » : gardé. La demande de … est close. », et la ligne part
- [ ] *Répondre* sur « Vide QA », « Supprimer le projet » : la confirmation dit « Supprimer le projet « Vide QA » ? Ses membres en sortent. Il ne se supprime que vide. » ; l'accepter : « Le projet « Vide QA » est supprimé. » (sa base, vide, part avec lui)
- [ ] *Répondre* sur l'entrée de documents, « Refuser le reste » : « Les documents qui attendaient sont refusés. La demande de … est close. », et la ligne part ; il reste les deux rejoindre

### Les demandes reçues, là où vit qui consent — compte `proprio`, Bibliothèque, projet « Projet QA »

- [ ] Bibliothèque rechargée, bande d'outils : un bouton « 2 demandes à répondre » (et plus de rappel « au fonds ») ; bloc « Collections » : « Projet QA » porte « ⚑ 2 » ; la bande du haut n'a rien gagné
- [ ] « 2 demandes à répondre » : la fiche de « Projet QA » s'ouvre sur *Albums*, dont l'onglet porte une pastille « 2 » ; en tête, « ⚑ 2 demandes de rejoindre un album de « Projet QA » » — « … demande que « Annee_lievre-1 » soit aussi rangé dans « Carnet QA » », la même pour « esther v1 », chacune datée, avec « Accepter » et « Refuser »
- [ ] « Accepter » sur « Annee_lievre-1 » : « « Annee_lievre-1 » est aussi rangé dans « Carnet QA » : le travail est partagé. » ; « Refuser » sur « esther v1 » : « Refusé : « esther v1 » reste où il est. La demande peut être redéposée. » ; le bloc ⚑, la marque « ⚑ », la pastille de l'onglet et le bouton de la bande d'outils ont disparu
- [ ] Administration, fiche de « Projet QA », « Au fonds · 2 demandes » : en tête, « Rendre « Annee_lievre-1 » à « Projet QA » », « acceptée » ; dessous, « 2 documents pour « Projet QA » », « acceptée en partie », et *Détail* : « esther v1 » « entré dans « Projet QA » », « Eau-terre » « refusé » ; « Copies gardées au fonds · 0 », « Aucune. »

### Un aller simple se confirme, et « + Nouvel album » propose la base — compte `stagiaire`, Bibliothèque, projet « Projet QA »

- [ ] La liste montre deux lignes « Annee_lievre-1 » : A1 (« Projet QA · Carnet QA ») et la copie rendue (« Projet QA ») ; fiche d'A1, *Sur les collections*, décocher « Carnet QA » : une confirmation dit « Le travail reste dans « Projet QA », où rien ne change. Vous ne pourrez l'y ranger de nouveau que sur demande, à son propriétaire ou à un administrateur. » ; *Annuler* : la case est de nouveau cochée, rien n'a bougé
- [ ] Bibliothèque rechargée, fiche d'« esther v1 » (E1) : la case « Carnet QA » n'est plus indéterminée — vide et active, la demande ayant été refusée
- [ ] Fiche du projet (rien de choisi), « + Nouvel album » : *Collection* propose « — choisir — », « Carnet QA » et « Projet QA », et c'est « Projet QA », la base, qui est PRÉSÉLECTIONNÉE ; dessous, « Seules les collections du projet « Projet QA » sont proposées : pour créer l'album dans un autre projet, choisissez-le en haut de la page. » ; nulle part « collection par défaut » ; *Annuler*
- [ ] Fiche de « Carnet QA » ouverte, « + Nouvel album » : *Collection* est sur « Carnet QA » — la collection d'où l'on vient l'emporte sur la base ; *Annuler*

### À l'étroit — comptes `proprio` et `admin-bd`, outils de développement en mode appareil

- [ ] Sous `proprio`, 375 px, Bibliothèque, projet « Projet QA », fiche du projet, « + Prendre du fonds… » : le panneau tient dans la largeur ; chaque notice, sa case et « déjà dans ce projet » se lisent sans défilement de côté ; *Dans*, le motif et « Demander … » restent entiers ; *Fermer*
- [ ] Sous `proprio`, 320 px, fiche de « Projet QA », onglet *Qui entre* : les deux groupes passent en cartes, « Par le projet · 2 » puis « Entrés ici · 0 », et « Régler dans le projet ↗ » se lit entier sur chaque carte dérivée
- [ ] Sous `admin-bd`, 320 px, Administration, fiche de « Projet QA » : les trois radios de la position et leurs phrases passent à la ligne sans défilement de côté ; vue « À faire », une demande dépliée : ses boutons (« Accepter : ranger aussi dans « Carnet QA » » compris) passent à la ligne sans se couper

### Rendre la recette — `C:\temp\bd-recette\etat-de-base.ps1`, puis compte `proprio`

- [ ] `C:\temp\bd-recette\etat-de-base.ps1 restaurer` répond « bd-app : healthy » (ou « running »)
- [ ] Sous `proprio`, Bibliothèque rechargée : la bande du haut ne propose plus « Projet QA » (le nom du projet s'affiche seul, sans liste), et la bande d'outils n'a ni « demandes à répondre » ni « demandes au fonds »
