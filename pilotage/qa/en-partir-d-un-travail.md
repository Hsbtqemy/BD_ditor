---
passe: En partir d'un travail — la copie à un cran, la demande, entre deux projets, repartir de zéro, supprimer et retirer
chantier: COL-3
duree: 45 min
derniere: 2026-10-26
---

# QA — la tranche 3b de COL-3 : partir du travail d'un autre, le refaire, l'effacer, le retirer

**Écrite le 2026-10-25 sur la recette reconstruite sur la 3b complète**, décor de l'état `avant-3b`, posé par les
routes de l'application : `proprio` est responsable du « Projet principal » ; `arrivant` est membre de ce projet et
propriétaire de « Carnet d'arrivant », où vit une copie d'« esther v1 » amorcée jusqu'à la transcription ; `stagiaire`
écrit dans « Collection Test » et lit « Carnet d'arrivant » ; `invite` est responsable du « Projet QA », dont la base
porte une copie de « Lot JP2 QA » découpée — ce document n'a plus aucune copie dans le projet principal ; une
« Notice sans travail » attend au fonds. Elle porte sur l'écran tranché sur maquette le 2026-10-25
(`pilotage/COL-3.md`, zone « Tranche 3b — l'écran ») et sur le serveur relu trois fois.

**Jouée le 2026-10-26 par Hugo sur `fb453cf`, 23 cases sur 23.** Cinq cases ont été corrigées PENDANT la passe, sur
place : l'écran avait raison, la case avait tort. « + Prendre du fonds… » vit dans la Bibliothèque, pas dans
l'Administration ; l'« esther v1 » à remettre à zéro est l'originale, parmi trois que rien ne distingue ; la copie
« images seules » ne porte aucun travail, donc aucun tableau « qui perd quoi » ; « Lot TIFF QA » s'efface sans demande
(copie d'origine que `proprio` a importée et été seul à toucher) : la dernière copie à DEMANDER se joue sur « Base
QA » ; et `proprio` ne lit pas « Carnet d'arrivant » : le retrait du projet s'y joue sous `admin-bd`. Ce que la passe
a ouvert est dans `pilotage/COL-3.md` (« Un envoi se voit sur son bouton », la zone « Relevé en jouant la passe de la
3b » et la zone « Le responsable voit tout son projet »). **Relue contre le code le 2026-11-03 (`UX-20`)** : les cases que le catalogue de la Bibliothèque et la tranche 3c ont rendues fausses sont réécrites et décochées, chacune dit pourquoi ; les autres restent cochées, et leurs gestes se refont pour construire le décor.

**Les comptes** : `proprio`, `arrivant`, `stagiaire`, `invite`, `admin-bd` (second facteur). Une fenêtre privée par
compte. `proprio` trouve en arrivant une ligne « Lot JP2 QA a été retiré du projet par admin-bd » dans « Étude B » :
c'est le décor, « Vu » la fait partir. **Ce que la passe ne juge pas** : 320 px et la grande police (mesurés par les
tests) ; la règle de la dernière copie dans tous ses détours (tests et trois relectures).

## Reste

### Qui crée une collection — `proprio` puis `stagiaire`

- [x] `stagiaire`, Bibliothèque : « + Créer une collection » est sous le bloc Collections, éteint ; son infobulle nomme `proprio` comme celui qui crée
- [x] `proprio`, Administration → Projets → « Projet principal » : la case « Les membres peuvent créer des collections » est décochée ; la cocher
- [x] `stagiaire`, F5 : « + Créer une collection » s'allume, et crée une collection

### Copie… dans le projet — `stagiaire`, « Collection Test »

- [x] « + Prendre dans le projet… » : sur « esther v1 » de « Carnet d'arrivant », « Copie… » déplie une échelle sous la ligne, « Images seules » cochée, et un tableau dit en NOMBRES ce que chaque cran ajoute (cases, bulles, texte…)
- [ ] « Images seules », « Copier les images » → la copie est faite tout de suite ; dans le catalogue de « Collection Test », « esther v1 » devient une pile, « ▸ 1 copie », et dépliée, sa copie dit « Votre copie », « copie vierge » (décochée le 2026-11-03, `edf0896` : une copie se replie sous son original)
- [x] De nouveau « Copie… » sur la même ligne, « Jusqu'à la transcription » (le cran du texte) → le bouton dit « Demander » ; envoyé, la ligne dit que la demande attend la propriétaire (sans la nommer)

### La propriétaire répond — `arrivant`, Bibliothèque, « Carnet d'arrivant »

- [x] ⚑ marque la collection ; l'onglet *Albums* porte la demande en tête, avec ses nombres
- [ ] « Accepter : copier dans « Collection Test » » → la demande disparaît ; `stagiaire`, F5 : dans « Collection Test », « esther v1 » dit « ▸ 2 copies », et dépliée, l'une de ses deux « Votre copie » dit « copie · jusqu'à la transcription » (décochée le 2026-11-03, `edf0896` : une copie se replie sous son original)

### Entre deux projets — `proprio`, puis `invite`

- [x] `proprio`, Bibliothèque, projet courant « Projet principal », sans collection ni album ouvert (l'adresse `/corpus` seule) : « + Prendre du fonds… » en tête de la fiche ; chercher « Lot JP2 QA », choisir le cran « jusqu'au découpage », un motif → la ligne répond « demandé », sans nommer de projet
- [x] Même geste sur « Notice sans travail », même cran → la même réponse « demandé », mot pour mot
- [x] `invite`, Administration → Projets → « Projet QA » : la demande est en tête de la fiche ; « Depuis quelle copie » propose la copie de « Lot JP2 QA » ; « Accepter »
- [ ] `invite`, Bibliothèque, projet « Projet QA » : la demande répondue n'attend plus — pas d'entrée « À répondre » dans le rail, ni de rappel « … d'en partir » dans la bande d'outils (décochée le 2026-11-03, `d20bc0c` : les demandes d'en partir se lisent dans « À répondre », et non plus en tête de la fiche du projet)
- [x] `proprio`, Administration → Projets → « Projet principal », « Au fonds » : la demande est « acceptée », sans le nom du projet source ; la copie de « Lot JP2 QA » est dans la base du projet principal

### Repartir de zéro — `proprio`, puis `stagiaire`, puis `admin-bd`

- [ ] `proprio`, « Collection Test » : ouvrir la carte « esther v1 » elle-même — l'ORIGINALE, ses copies repliées dessous, la seule qui ait des annotations ; « Autres gestes ▾ », « Repartir de zéro… » ouvre un panneau avec un tableau « qui perd quoi » (qui, combien de gestes de chaque sorte) ; « Repartir de la transcription » → la tête de l'album porte la puce « repartie de la transcription le … » (décochée le 2026-11-03, `edf0896` : les copies se replient sous l'original, et « Repartir de zéro… » est sous « Autres gestes »)
- [ ] `stagiaire`, Bibliothèque, « Collection Test » → « Lot TIFF QA » (album qu'il n'a pas créé), dans la liste des planches : ↺ sur une ligne (avant la corbeille), choisir un cran → le panneau dit « La demande part à » `proprio` (son nom lisible), « responsable du projet, qui décide. Rien n'est effacé d'ici là. », et offre un motif, la certification et « Envoyer la demande » ; *Annuler* sans rien envoyer (décochée le 2026-11-03, `6436a62` : depuis la 3c, repartir de zéro sur une planche se demande, au responsable du projet)
- [ ] `stagiaire`, fiche de « Lot TIFF QA », « Autres gestes ▾ », « Repartir de zéro… » vers « Images seules » : la demande part à `proprio`, responsable du projet ; elle exige un motif et la certification, puis part (décochée le 2026-11-03, `edf0896` et `6436a62` : le geste est sous « Autres gestes », et la demande part au responsable du projet)
- [x] `admin-bd`, Administration → À faire : la demande est dans une tranche ROSE ; « Garder » la laisse ; la rouvrir (ou en refaire une), « Repartir … » demande confirmation puis efface

### Supprimer et retirer — `proprio`, puis `arrivant`

- [ ] `proprio`, Bibliothèque, « Collection Test », onglet *Albums* : déplier « esther v1 » et ouvrir la copie « Copie de » `stagiaire` (son nom) qui dit « copie vierge » (faite par `stagiaire`, sans travail) ; « Autres gestes ▾ », « Supprimer… », carte « définitivement » → « Vous êtes responsable du projet : rien à demander. », et ses images restent ; AUCUN tableau « qui perd quoi » (personne n'y a travaillé) ; confirmé, la copie disparaît, sans demande (décochée le 2026-11-03, `edf0896` : les copies se replient sous l'original, et « Supprimer… » est sous « Autres gestes »)
- [ ] `proprio`, Bibliothèque, base « Projet principal » → « Base QA » (seule copie de son document, importée par `admin-bd`) : « Autres gestes ▾ », « Supprimer… », carte « définitivement » → « C'est la dernière copie de ce document. », et c'est un administrateur qui décide ; motif et certification exigés, « Envoyer la demande » ; la fiche dit ensuite « suppression demandée ». (« Lot TIFF QA », seule copie de son document lui aussi, se demanderait de même : depuis la 3c, l'avoir importé ne dispense plus de demander) (décochée le 2026-11-03, `edf0896` et `8edcad3` : « Supprimer… » est sous « Autres gestes », et l'exception de la copie d'origine est retirée)
- [ ] `proprio`, qui lit « Carnet d'arrivant » par le projet : Bibliothèque, son nom dans le rail ; « esther v1 » y est ÉTEINT, « hors de cette collection », et sa copie « Copie de travail » dessous ; l'ouvrir, « Autres gestes ▾ », « Retirer du projet… » → ce qui part et où (au fonds, avec son travail) ; confirmé, elle quitte le projet (décochée le 2026-11-03, `5e0e100` et `edf0896` : depuis la 3c le responsable lit toutes les collections de son projet, et la copie se replie sous l'original)
- [ ] `arrivant`, « Carnet d'arrivant », onglet *Albums* : la ligne « esther v1 a été retiré du projet par » `proprio` (son nom) « … » en tête ; « Vu » la fait partir, et elle ne revient pas après F5 (décochée le 2026-11-03 : le retrait est fait par `proprio`, et non plus par `admin-bd`)

### « ⟳ Actualiser » se repère — `proprio` et `stagiaire`, Atelier, « esther v1 », même planche

- [x] `stagiaire` modifie le texte d'une bulle (Transcription, Tab) ; chez `proprio`, au plus 30 s après (ou en revenant sur l'onglet), « ⟳ Actualiser » apparaît en bouton PLEIN, de couleur cyan, seul de son espèce dans la bande — on le voit apparaître sans le chercher (sinon : écrire ici ce qui manque)

### Rendre la recette — PowerShell

- [x] `C:\temp\bd-recette\etat-de-base.ps1 restaurer avant-3b` finit par « bd-app : running »
