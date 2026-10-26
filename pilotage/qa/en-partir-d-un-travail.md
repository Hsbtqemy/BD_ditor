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
3b » et la zone « Le responsable voit tout son projet »).

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
- [x] « Images seules » → la copie est faite tout de suite, et apparaît dans « Collection Test »
- [x] De nouveau « Copie… » sur la même ligne, « Jusqu'à la transcription » (le cran du texte) → le bouton dit « Demander » ; envoyé, la ligne dit que la demande attend la propriétaire (sans la nommer)

### La propriétaire répond — `arrivant`, Bibliothèque, « Carnet d'arrivant »

- [x] ⚑ marque la collection ; l'onglet *Albums* porte la demande en tête, avec ses nombres
- [x] « Accepter : copier dans « Collection Test » » → la demande disparaît ; `stagiaire`, F5 : la nouvelle copie est dans « Collection Test », et sa ligne dit son cran (transcription)

### Entre deux projets — `proprio`, puis `invite`

- [x] `proprio`, Bibliothèque, projet courant « Projet principal », sans collection ni album ouvert (l'adresse `/corpus` seule) : « + Prendre du fonds… » en tête de la fiche ; chercher « Lot JP2 QA », choisir le cran « jusqu'au découpage », un motif → la ligne répond « demandé », sans nommer de projet
- [x] Même geste sur « Notice sans travail », même cran → la même réponse « demandé », mot pour mot
- [x] `invite`, Administration → Projets → « Projet QA » : la demande est en tête de la fiche ; « Depuis quelle copie » propose la copie de « Lot JP2 QA » ; « Accepter »
- [x] `invite`, Bibliothèque, tête du « Projet QA » : la demande n'y est plus (déjà répondue), ou s'y lit répondue
- [x] `proprio`, Administration → Projets → « Projet principal », « Au fonds » : la demande est « acceptée », sans le nom du projet source ; la copie de « Lot JP2 QA » est dans la base du projet principal

### Repartir de zéro — `proprio`, puis `stagiaire`, puis `admin-bd`

- [x] `proprio`, fiche de l'« esther v1 » ORIGINALE de « Collection Test » (celle dont la ligne ne porte aucune puce « copie · jusqu'à … » : la seule qui ait des annotations) : « Repartir de zéro… » ouvre un panneau avec un tableau « qui perd quoi » (qui, combien de gestes de chaque sorte) ; « Repartir de la transcription » → la tête de l'album porte la puce « repartie de la transcription le … »
- [x] `stagiaire`, Bibliothèque, « Collection Test » → la fiche de « Lot TIFF QA » (album qu'il n'a pas créé), dans la liste des planches : ↺ sur une ligne (avant la corbeille), choisir un cran → le panneau dit « … repartir de zéro sur une planche ne se demande pas. Demandez-le pour l'album entier, ou adressez-vous à un administrateur de l'instance. », et n'a AUCUN bouton d'envoi
- [x] `stagiaire`, fiche de « Lot TIFF QA » : « Repartir de zéro… » vers « Images seules » exige un motif et la certification, puis part en demande
- [x] `admin-bd`, Administration → À faire : la demande est dans une tranche ROSE ; « Garder » la laisse ; la rouvrir (ou en refaire une), « Repartir … » demande confirmation puis efface

### Supprimer et retirer — `proprio`, puis `arrivant`

- [x] `proprio`, Bibliothèque, « Collection Test », onglet *Albums* : ouvrir l'« esther v1 » dont la puce dit la copie aux images seules (faite par `stagiaire`, sans travail) ; « Supprimer… » en tête de la fiche, carte « définitivement » → elle dit pourquoi on peut sans demander (« Vous êtes responsable du projet » ou « Vous tenez toutes ses collections ») et que les images restent ; AUCUN tableau « qui perd quoi » (personne n'y a travaillé) ; confirmé, la copie disparaît, sans demande
- [x] `proprio`, Bibliothèque, base « Projet principal » → « Base QA » (seule copie de son document, importée par `admin-bd`) : « Supprimer… », carte « définitivement » → le panneau dit que c'est la dernière copie et qu'un administrateur décide ; motif et certification exigés, « Envoyer la demande » ; la fiche dit ensuite « suppression demandée ». (« Lot TIFF QA », lui, s'efface sans demande : copie d'origine que `proprio` a importée et été seul à toucher — l'exception voulue)
- [x] `admin-bd` (`proprio` ne lit pas « Carnet d'arrivant »), Bibliothèque, collection « Carnet d'arrivant » → son « esther v1 » : « Retirer du projet… » → ce qui part et où (au fonds, avec son travail) ; confirmé, elle quitte le projet
- [x] `arrivant`, « Carnet d'arrivant », onglet *Albums* : la ligne « esther v1 a été retiré du projet par admin-bd … » en tête ; « Vu » la fait partir, et elle ne revient pas après F5

### « ⟳ Actualiser » se repère — `proprio` et `stagiaire`, Atelier, « esther v1 », même planche

- [x] `stagiaire` modifie le texte d'une bulle (Transcription, Tab) ; chez `proprio`, au plus 30 s après (ou en revenant sur l'onglet), « ⟳ Actualiser » apparaît en bouton PLEIN, de couleur cyan, seul de son espèce dans la bande — on le voit apparaître sans le chercher (sinon : écrire ici ce qui manque)

### Rendre la recette — PowerShell

- [x] `C:\temp\bd-recette\etat-de-base.ps1 restaurer avant-3b` finit par « bd-app : running »
