---
passe: Supprimer a deux réponses, et le fonds garde ce qu'on retire
chantier: COL-3
duree: 60 min
derniere: —
---

# QA — « Supprimer… » : de la collection, ou définitivement ; la demande, et le fonds de l'administrateur

**Réécrite le 2026-10-16 pour la tranche 2 de `COL-3`, et non rejouée.** La version d'avant
(`AUTH-10` : une corbeille, un ✕ qui menait à « sortir ») n'a jamais été jouée, et l'écran
qu'elle décrivait n'existe plus ; elle vit dans l'historique de ce fichier.

La tranche fait de chaque album la copie de travail d'un DOCUMENT qui appartient à
l'instance. « Supprimer » y a deux réponses : **de la collection** — rien n'est détruit, et la
copie part au fonds si c'était sa dernière collection — ou **définitivement** — tout de suite
quand on a importé l'album et que personne d'autre n'y a travaillé, sinon une DEMANDE motivée
et certifiée à un administrateur, qui la tranche dans un bloc « 🗄️ Le fonds ».

**Ce que les tests couvrent déjà — ne pas le refaire ici** : la règle sous chaque identité
(importateur, travail d'un autre, compte partagé, album d'avant le fonds, mono-poste), les
requêtes parties de chaque geste, les refus et leurs codes, qui lit le nom du demandeur, la
garde sous le verrou d'écriture, la migration v30, le bloc du fonds à 320 px sous deux polices.

**Ce qui se regarde ici** : ce que l'écran DIT, à qui, et si on le comprend avant d'agir —
le panneau est la confirmation. Et ce que voient les AUTRES après un geste.

**Ce que la passe ne juge pas** : la Recherche et l'Exploration de l'administrateur, qui
lisent encore le texte d'une copie gardée au fonds (tranche 4) ; la rapidité de la liste des
albums sur un gros journal ; le formulaire d'import ShareDocs, qui ne propose plus que les
albums où l'on écrit — il demande une session Huma-Num que la recette n'a pas d'office, et
`tests/test_e2e_atelier_album.py` le joue ; et le message qui suit une demande, qui s'affiche en bas à
droite sur la colonne d'actions — défaut connu, ouvert dans la fiche `COL-3`, à ne pas
re-signaler ici.

**Où** — la pile de recette, `https://bd.127-0-0-1.sslip.io`, **reconstruite sur un HEAD qui
contient `99eae43`** (cf. `C:\temp\bd-recette\LISEZ-MOI.md`, « Reconstruire l'application »).
Une fenêtre de navigation PRIVÉE par identité. Comptes : `admin-bd` (administrateur),
`proprio` (possède « Collection Test » et « Étude B »), `stagiaire` (écrit dans « Collection
Test »), `lectrice` (lit « Collection Test » par le groupe `annotateurs`), `collectif` (compte
partagé, écrit dans « Collection Test » par le groupe `etudiants`), `arrivant` (aucun accès).
Deux images JPEG ou PNG du poste, n'importe lesquelles, pour les imports.

**Avant de commencer : `C:\temp\bd-recette\etat-de-base.ps1 restaurer`.** L'état `base` est
en schéma 29 : il migre en v30 au redémarrage, et ses albums deviennent des documents dont
l'importateur n'est pas écrit — c'est le décor « album d'avant le fonds ». **La passe ABÎME
le décor** : elle crée et détruit des albums, en envoie un au fonds, dépose des demandes,
crée puis supprime un projet. Sa dernière zone le rend. **Ne jamais détruire « esther v1 »
ni la supprimer d'une collection** : d'autres passes en dépendent, et une seule case la
touche, pour lire.

Les zones se jouent DANS L'ORDRE : chacune s'appuie sur ce que la précédente a laissé.

### Le décor — comptes `admin-bd`, `proprio`, `stagiaire`, `collectif`

- [x] Sous `admin-bd`, Administration, bloc « 🏷️ Version servie » : le commit affiché est `99eae43` ou plus récent — sur un serveur plus ancien, aucune case de cette passe ne mesure rien
- [x] Sous `admin-bd`, Administration, « 👥 Comptes et groupes », fiche du compte `collectif` : sa *Nature* est « un login partagé » ; sinon, la régler ainsi et l'enregistrer — la fiche le redit après F5
- [x] Sous `proprio`, Bibliothèque, **+ Nouvel album** : titre « Album de Proprio QA », *Collection* = « Collection Test », *Enregistrer*. Puis, dans sa fiche (✎), bloc *Collections* : « Étude B » → **+ Ranger ici**. La fiche liste les deux collections
- [x] Sous `proprio`, Bibliothèque, **+ Nouvel album** « Travail partagé QA » puis « Retrait QA », chacun dans « Collection Test » seule. Les deux lignes apparaissent, 0 planche
- [x] Sous `proprio`, Atelier : choisir « Travail partagé QA » dans la liste *Album*, puis *⇅ Import / Export* → *⤓ Importer des images…* → une image. La planche apparaît dans la barre latérale. Même geste pour « Retrait QA »
- [x] Sous `stagiaire`, Atelier, album « Travail partagé QA », mode Édition (`E`) : dessiner une région au cliquer-glisser. Elle apparaît dans l'arbre de structure, et y est encore après F5
- [x] Sous `stagiaire`, Bibliothèque, **+ Nouvel album** : le champ *Collection* propose « Collection Test ». Créer « Import par erreur QA » dedans, puis dans l'Atelier, **choisir cet album dans la liste *Album*** — l'Atelier ouvre le premier de la liste, pas celui qu'on vient de créer —, puis *⇅ Import / Export* → *⤓ Importer des images…* → une image : la planche apparaît
- [x] Sous `collectif`, Bibliothèque, **+ Nouvel album** « Import collectif QA » dans « Collection Test », puis dans l'Atelier, **choisir cet album dans la liste *Album*** — l'Atelier ouvre le premier de la liste, pas celui qu'on vient de créer —, puis *⇅ Import / Export* → *⤓ Importer des images…* → une image : la planche apparaît *(réécrite le 2026-10-16 : sans le choix de l'album, l'image partait dans « Album de Proprio QA », et l'effacement direct de la zone de `proprio` devenait une demande)*

### L'Atelier ne crée plus d'albums — comptes `stagiaire` et `arrivant`, Atelier

- [x] Sous `stagiaire` : la barre latérale n'a pas de bouton `＋` à côté de la liste *Album* — on ne crée plus un album ici
- [x] Sous `arrivant`, qui ne lit aucun album : *⇅ Import / Export* → *⤓ Importer des images…* affiche « Aucun album : un album se crée dans la Bibliothèque, puis ses planches s'importent ici. », et aucun sélecteur de fichiers ne s'ouvre

### Qui ne fait que lire ne se voit rien offrir — compte `lectrice`, Bibliothèque

- [x] Les lignes de « esther v1 », « Travail partagé QA » et « Retrait QA » portent ✎ et **pas** de bouton *Supprimer…*
- [x] Cliquer la ligne de « Travail partagé QA » : sa planche s'affiche sans corbeille 🗑, ni active ni grisée

### « Supprimer… » ouvre deux réponses — compte `stagiaire`, Bibliothèque

- [x] Les lignes des albums de « Collection Test » portent chacune un bouton *Supprimer…*, à la place de l'ancienne corbeille
- [x] *Supprimer…* sur « Import par erreur QA » : un panneau titré « Supprimer « Import par erreur QA » » s'ouvre, le focus est sur *Annuler* (anneau visible), et il montre deux cartes, « Supprimer de la collection » et « Supprimer définitivement »
- [x] Dans ce panneau, la première carte dit « C'est sa dernière collection : la copie de travail est gardée au fonds, avec tout son travail. Un administrateur peut la rendre. », puis « Vous ne le verrez plus, et ne pourrez pas l'y ranger de nouveau vous-même. », au-dessus d'un bouton « Supprimer de « Collection Test » »
- [x] Dans ce panneau, la seconde carte dit « Efface tout de suite ses images et le travail fait dessus : vous l'avez importé, et personne d'autre n'y a travaillé. Irréversible. », avec un bouton rouge « Supprimer définitivement » et **aucun** champ de motif. *Annuler* referme sans rien faire
- [x] *Supprimer…* sur « Travail partagé QA », seconde carte : « D'autres s'en servent, ou ce n'est pas vous qui l'avez importé : la demande part à un administrateur, qui décide. Rien n'est effacé d'ici là. », un champ « Pourquoi ce document n'a pas sa place ici », le texte de la certification (« Supprimer définitivement détruit tout ce qui a été posé sur les planches — découpage, transcription, annotations, métadonnées —, … Pouvez-vous certifier que ces données ne sont pas importantes ? »), une case « Je certifie que ces données ne sont pas importantes. » non cochée, et un bouton « Envoyer la demande ». Échap referme
- [x] *Supprimer…* sur « Album de Proprio QA », première carte : « Le travail reste dans une collection que vous ne lisez pas, où rien ne change. » puis « Vous ne le verrez plus, et ne pourrez pas l'y ranger de nouveau vous-même. » — et le nom « Étude B » n'apparaît nulle part sur la page. *Annuler*
- [x] *Supprimer…* sur « esther v1 » — l'album d'avant le fonds —, seconde carte : c'est la demande (« D'autres s'en servent, ou ce n'est pas vous qui l'avez importé… »), pas l'effacement. *Annuler* — ne rien envoyer

### Une planche suit l'album — compte `stagiaire`, Bibliothèque

- [x] Cliquer la ligne de « Import par erreur QA », puis faire défiler le tableau des planches vers la droite (Maj + molette, ou sa barre de défilement) — la corbeille est sa dernière colonne et tombe hors champ si la fenêtre n'est pas très large : la corbeille 🗑 de sa planche est ACTIVE — pleine, sans contour pointillé, et son fond passe au rouge au survol. Ne pas cliquer
- [x] Cliquer la ligne de « Travail partagé QA » : la corbeille de sa planche est grisée, au contour pointillé ; la toucher affiche, juste sous elle, « Cette planche ne se supprime pas d'ici : vous n'avez pas importé l'album, ou d'autres y ont travaillé. Adressez-vous à un administrateur de l'instance. » — et aucun message ne s'affiche en bas à droite
- [x] Menu « Aa » → thème clair : la corbeille grisée se distingue encore d'un emplacement vide (son contour se voit). Revenir au thème d'avant

### Son import par erreur s'efface tout de suite — compte `stagiaire`, Bibliothèque

- [x] *Supprimer…* sur « Import par erreur QA » → *Supprimer définitivement* : le panneau se ferme, « « Import par erreur QA » est supprimé définitivement, avec ses images et le travail fait dessus. » s'affiche, et la ligne a quitté la liste
- [x] Sous `admin-bd`, Administration, « 🗄️ Le fonds », liste *Documents* : « Import par erreur QA » n'y est pas — rien n'a été gardé

### Le travail d'un autre fait demander, même à qui a importé — compte `proprio`, Bibliothèque

- [x] *Supprimer…* sur « Travail partagé QA » — qu'elle a importé, mais où `stagiaire` a dessiné une région : la seconde carte propose la demande (« D'autres s'en servent… », motif, certification), pas l'effacement. *Annuler*
- [x] *Supprimer…* sur « Album de Proprio QA » — importé par elle, rangé dans deux de ses collections, où personne d'autre n'a rien fait : la première carte a deux boutons, et au-dessus de « Supprimer de « Collection Test » » on lit « Le travail reste dans « Étude B », où rien ne change. », sans phrase sur ce qu'elle perdrait ; la seconde carte dit « Efface tout de suite… vous l'avez importé, et personne d'autre n'y a travaillé. Irréversible. »
- [x] AVANT de cliquer, relever dans « 📚 Collections » le nombre affiché sur la ligne repliée de « Collection Test » et d'« Étude B » (« N album(s) » : le bloc ne dit pas LESQUELS, cf. `UX-18`). Puis, dans ce panneau, *Supprimer définitivement* : « « Album de Proprio QA » est supprimé définitivement… » s'affiche, la ligne quitte la liste, et les deux nombres ont baissé d'un *(réécrite le 2026-10-16 : « ne le compte plus » ne se vérifiait pas sans le nombre d'avant)*

### L'album d'un autre part en demande — compte `stagiaire`, Bibliothèque

- [x] *Supprimer…* sur « Travail partagé QA », motif vide, *Envoyer la demande* : « Dites pourquoi : c'est ce que l'administrateur lira pour décider. » s'affiche en rouge dans le panneau, le focus va au champ, et rien ne part (le panneau reste ouvert)
- [x] Taper un motif, laisser la case vide, *Envoyer la demande* : « Cochez la certification : la demande ne part pas sans elle. » s'affiche, le focus va à la case, et rien ne part
- [x] Cocher la case, *Envoyer la demande* : le panneau se ferme, « Votre demande est partie à un administrateur. Rien n'est effacé d'ici sa réponse. » s'affiche, et la ligne de « Travail partagé QA » porte la pastille « suppression demandée par vous »
- [x] L'album est intact : sa ligne compte toujours 1 planche, et dans l'Atelier la région de `stagiaire` est encore là
- [x] Rouvrir *Supprimer…* sur lui : la seconde carte dit « Sa suppression est déjà demandée par vous, le JJ/MM/AAAA : un administrateur y répondra. Rien n'est effacé d'ici là. », à la date du jour, sans bouton ni champ
- [x] Sous `proprio`, Bibliothèque : la ligne de « Travail partagé QA » porte la pastille « suppression demandée », **sans nom** ; *Supprimer…* → la seconde carte dit « Sa suppression est déjà demandée, le … » sans nommer personne, et sans bouton

### Supprimer de la collection, et l'album quitte l'écran — compte `stagiaire`, Bibliothèque

- [x] ✎ sur « esther v1 », bloc *Collections*, ✕ de « Collection Test » : une confirmation demande « Supprimer « esther v1 » de « Collection Test » ? », dit que le travail reste ailleurs (« Le travail reste dans …, où rien ne change. ») et ce que `stagiaire` y perdrait — et ne nomme pas « Étude B ». **Refuser** : rien ne bouge, la fiche reste ouverte. La fermer
- [x] *Supprimer…* sur « Retrait QA » → « Supprimer de « Collection Test » » : le panneau se ferme, « « Retrait QA » n'est plus dans « Collection Test ». Sa copie de travail est gardée au fonds. » s'affiche, et la ligne a quitté la liste
- [x] Sous `proprio`, Bibliothèque rechargée : « Retrait QA » n'est plus dans sa liste non plus, et « 📚 Collections » compte un album de moins dans « Collection Test »

### Un compte partagé demande toujours — compte `collectif`, Bibliothèque

- [x] *Supprimer…* sur « Import collectif QA » — qu'il a importé, où personne d'autre n'a rien fait : la seconde carte propose la demande, pas l'effacement
- [x] Motif, case cochée, *Envoyer la demande* : la ligne porte « suppression demandée par vous »

### « À regarder » et les demandes — compte `admin-bd`, Administration

- [x] « 👥 Comptes et groupes », « ⚠ À regarder » : ses premières lignes sont les demandes, chacune nommée (« … demande la suppression définitive de « Travail partagé QA » », de même pour « Import collectif QA »), avant tout autre signal
- [x] Cliquer la ligne de « Travail partagé QA » : la page REMONTE jusqu'à cette demande, dans « 🗄️ Le fonds » (placé au-dessus de « 👥 Comptes et groupes »), qui prend le focus — aucune fiche de compte ne s'ouvre *(corrigée le 2026-10-16 : elle disait « descend »)*
- [x] « 🗄️ Le fonds » : sa ligne de compte dit « … · 2 suppressions demandées », et la section « Suppressions demandées » vient en tête du bloc, avant « Importer au fonds »
- [x] Demande de « Travail partagé QA » : le nom de `stagiaire`, la date du jour et « depuis « Projet principal » » (ou le nom du projet de repli), le motif tapé, puis « Certifié par … le JJ/MM/AAAA : ces données ne sont pas importantes. »
- [x] Sous cette demande : « Importé par … (proprio). », puis « Gestes d'autres personnes, lus au journal — un geste défait depuis compte encore : » et une ligne pour `proprio` qui compte ses gestes sur le document (« … gestes sur le document (import, scans, notice) — dernier le … ») ; aucune ligne pour `stagiaire`, la demandeuse
- [x] Demande de « Import collectif QA » : la certification se lit « Certifié par … (compte partagé : plusieurs personnes peuvent avoir travaillé sous ce login) le … », et dessous « Personne d'autre que le demandeur n'y a laissé de geste — mais c'est un compte partagé : plusieurs personnes peuvent avoir travaillé sous ce login. »
- [x] *Supprimer…* sur « esther v1 » dans la Bibliothèque, seconde carte : « Efface tout de suite ses images et tout le travail fait dessus, dans tous les projets. Irréversible. » — l'administrateur n'a rien à demander. **Annuler**, ne rien cliquer d'autre

### Garder, puis redemander — comptes `admin-bd` et `stagiaire`

- [x] Sous `admin-bd`, demande de « Travail partagé QA » → *Garder* : « « Travail partagé QA » : gardé. La demande de … est close. » s'affiche, la demande quitte la liste, et « À regarder » ne la porte plus
- [x] Sous `stagiaire`, Bibliothèque rechargée : la pastille de « Travail partagé QA » a disparu, et *Supprimer…* repropose la demande, champ et case vides
- [x] Redéposer la demande (motif, case cochée). Sous `admin-bd`, « 🗄️ Le fonds » rechargé : sa ligne de contexte dit « … · déjà refusée une fois »

### Détruire une demande — compte `admin-bd`, Le fonds

- [x] Demande de « Import collectif QA » → *Détruire* : une confirmation dit « Détruire « Import collectif QA » ? Ses images et tout le travail fait dessus sont effacés, dans tous les projets. Irréversible. » ; l'accepter : « « Import collectif QA » : détruit, avec ses images et tout le travail fait dessus. » s'affiche, et la demande a quitté la liste
- [x] Sous `collectif`, Bibliothèque rechargée : « Import collectif QA » n'y est plus

### Le fonds : d'où vient chaque document, et rendre la copie gardée — compte `admin-bd`, Administration

- [x] « 🗄️ Le fonds », *Documents*, « esther v1 » : « Importé le JJ/MM/AAAA, dans « … » ; qui l'a importé n'est pas écrit. », et « Employé par … : » suivi de ses collections
- [x] *Documents*, « Retrait QA » : la puce « appelé par personne », « Importé par … (proprio), le …, dans « … ». », et « Copie gardée ici (projet « … »). » suivie d'une liste de collections et d'un bouton *Rendre* — la liste ne propose que des collections de ce projet
- [x] Choisir « Collection Test » → *Rendre* : « Copie rendue à « Collection Test », avec tout son travail. » s'affiche, la puce « appelé par personne » a disparu, et « Employé par … : Collection Test » s'affiche
- [x] Sous `proprio`, Bibliothèque rechargée : « Retrait QA » est revenu dans sa liste, avec 1 planche, et l'Atelier l'ouvre sur cette planche

### Importer au fonds, puis détruire — compte `admin-bd`, Administration puis Bibliothèque

- [x] « 🗄️ Le fonds », *Importer au fonds*, titre vide, *+ Importer au fonds* : « Donnez un titre à l'album. » s'affiche, et rien n'est créé
- [x] Titre « Fonds QA », une image, *+ Importer au fonds* : « « Fonds QA » est au fonds, appelé par personne : 1 planche importée. » s'affiche, et « Fonds QA » apparaît dans *Documents* avec « appelé par personne » et « Copie gardée ici (sans projet). »
- [x] Bibliothèque : « Fonds QA » n'est pas dans la liste des albums ; Atelier : la liste *Album* ne le propose pas — une copie gardée n'est pas un album de travail
- [x] Retour au fonds, « Fonds QA » → *Détruire* : la confirmation dit ce qui part ; l'accepter : « « Fonds QA » : détruit, avec ses images et tout le travail fait dessus. », et il a quitté *Documents*

### Le fonds ne leur est pas montré — comptes `proprio` et `arrivant`, Administration

- [x] Sous `proprio` : la page n'a pas de bloc « 🗄️ Le fonds », ni de bloc « 👥 Comptes et groupes », et aucun message d'erreur ne le remplace
- [x] Sous `arrivant` : pas de bloc « 🗄️ Le fonds » non plus

### Un responsable demande la suppression de son projet — comptes `admin-bd` et `proprio`, Administration

- [x] Sous `admin-bd`, « 🗂️ Projets » : créer « Projet QA » (*Nouveau projet*, *+ Créer le projet*), puis dans sa fiche, *Qui y entre* : faire entrer le compte `proprio`, et passer sa ligne à « responsable du projet ». Le rôle est encore là après F5
- [x] Sous `proprio`, « 🗂️ Projets », fiche de « Projet QA », partie *Ce projet* : sous la phrase « Vous réglez qui entre dans ce projet… se demande à un administrateur de l'instance. », un bouton « Demander sa suppression… » et aucun champ
- [x] Cliquer ce bouton : il laisse place à un champ « Pourquoi le supprimer » qui prend le focus, avec « Envoyer la demande » et « Annuler » ; *Annuler* referme et rend le focus au bouton
- [x] Rouvrir, *Envoyer la demande* sans motif : « Dites pourquoi : c'est ce que l'administrateur lira pour décider. » s'affiche sur la rangée du bouton, et rien ne part
- [x] Avec un motif, *Envoyer la demande* : la puce « suppression demandée le JJ/MM/AAAA » remplace le bouton, et juste dessous « Votre demande est partie à un administrateur. Rien n'est supprimé d'ici sa réponse. » ; la fiche n'a pas bougé dans la page
- [x] Sous `admin-bd`, « 🗄️ Le fonds » rechargé : « … demande la suppression du projet « Projet QA » », avec le motif et sans certification ; *Supprimer le projet* → la confirmation dit « Supprimer le projet « Projet QA » ? Ses membres en sortent. Il ne se supprime que vide. » ; l'accepter : « Le projet « Projet QA » est supprimé. », et « 🗂️ Projets » ne le liste plus

### À l'étroit — comptes `stagiaire` et `admin-bd`, fenêtre à 375 puis 320 px

- [x] Sous `stagiaire`, Bibliothèque à 375 px : la page ne défile pas de côté, et le bouton *Supprimer…* d'une ligne reste entier et lisible
- [x] À 320 px, *Supprimer…* sur « Travail partagé QA » : le panneau tient dans la fenêtre sans défiler de côté, ses deux cartes passent l'une sous l'autre, et la case de certification et son libellé se lisent en entier
- [x] Sous `admin-bd`, Administration à 320 px : le bloc « 🗄️ Le fonds » ne fait pas défiler la page de côté, et les boutons *Détruire* / *Garder* d'une demande restent entiers. Revenir à la largeur ordinaire

### Rendre la recette — `C:\temp\bd-recette\etat-de-base.ps1`

- [x] `C:\temp\bd-recette\etat-de-base.ps1 restaurer` : il répond « bd-app : healthy » (ou « running »)
- [x] Sous `stagiaire`, Bibliothèque : « esther v1 » est là, et aucun album « … QA » ne subsiste
