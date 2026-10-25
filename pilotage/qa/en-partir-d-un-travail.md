---
passe: En partir d'un travail — la copie à un cran, la demande, entre deux projets, repartir de zéro, supprimer et retirer
chantier: COL-3
duree: 45 min
derniere: jamais
---

# QA — la tranche 3b de COL-3 : partir du travail d'un autre, le refaire, l'effacer, le retirer

**Écrite le 2026-10-25 sur la recette reconstruite sur la 3b complète**, décor de l'état `avant-3b`, posé par les
routes de l'application : `proprio` est responsable du « Projet principal » ; `arrivant` est membre de ce projet et
propriétaire de « Carnet d'arrivant », où vit une copie d'« esther v1 » amorcée jusqu'à la transcription ; `stagiaire`
écrit dans « Collection Test » et lit « Carnet d'arrivant » ; `invite` est responsable du « Projet QA », dont la base
porte une copie de « Lot JP2 QA » découpée — ce document n'a plus aucune copie dans le projet principal ; une
« Notice sans travail » attend au fonds. Non jouée. Elle porte sur l'écran tranché sur maquette le 2026-10-25
(`pilotage/COL-3.md`, zone « Tranche 3b — l'écran ») et sur le serveur relu trois fois.

**Les comptes** : `proprio`, `arrivant`, `stagiaire`, `invite`, `admin-bd` (second facteur). Une fenêtre privée par
compte. `proprio` trouve en arrivant une ligne « Lot JP2 QA a été retiré du projet par admin-bd » dans « Étude B » :
c'est le décor, « Vu » la fait partir. **Ce que la passe ne juge pas** : 320 px et la grande police (mesurés par les
tests) ; la règle de la dernière copie dans tous ses détours (tests et trois relectures).

## Reste

### Qui crée une collection — `proprio` puis `stagiaire`

- [ ] `stagiaire`, Bibliothèque : « + Créer une collection » est sous le bloc Collections, éteint ; son infobulle nomme `proprio` comme celui qui crée
- [ ] `proprio`, Administration → Projets → « Projet principal » : la case « Les membres peuvent créer des collections » est décochée ; la cocher
- [ ] `stagiaire`, F5 : « + Créer une collection » s'allume, et crée une collection

### Copie… dans le projet — `stagiaire`, « Collection Test »

- [ ] « + Prendre dans le projet… » : sur « esther v1 » de « Carnet d'arrivant », « Copie… » déplie une échelle sous la ligne, « Images seules » cochée, et un tableau dit en NOMBRES ce que chaque cran ajoute (cases, bulles, texte…)
- [ ] « Images seules » → la copie est faite tout de suite, et apparaît dans « Collection Test »
- [ ] De nouveau « Copie… » sur la même ligne, « Jusqu'à la transcription » (le cran du texte) → le bouton dit « Demander » ; envoyé, la ligne dit que la demande attend la propriétaire (sans la nommer)

### La propriétaire répond — `arrivant`, Bibliothèque, « Carnet d'arrivant »

- [ ] ⚑ marque la collection ; l'onglet *Albums* porte la demande en tête, avec ses nombres
- [ ] « Accepter : copier dans « Collection Test » » → la demande disparaît ; `stagiaire`, F5 : la nouvelle copie est dans « Collection Test », et sa ligne dit son cran (transcription)

### Entre deux projets — `proprio`, puis `invite`

- [ ] `proprio`, Administration → Projets → « Projet principal » (ou la tête du projet dans la Bibliothèque), « + Prendre du fonds… » : chercher « Lot JP2 QA », choisir le cran « jusqu'au découpage », un motif → la ligne répond « demandé », sans nommer de projet
- [ ] Même geste sur « Notice sans travail », même cran → la même réponse « demandé », mot pour mot
- [ ] `invite`, Administration → Projets → « Projet QA » : la demande est en tête de la fiche ; « Depuis quelle copie » propose la copie de « Lot JP2 QA » ; « Accepter »
- [ ] `invite`, Bibliothèque, tête du « Projet QA » : la demande n'y est plus (déjà répondue), ou s'y lit répondue
- [ ] `proprio`, fiche du projet, « Au fonds » : la demande est « acceptée », sans le nom du projet source ; la copie de « Lot JP2 QA » est dans la base du projet principal

### Repartir de zéro — `proprio`, puis `stagiaire`, puis `admin-bd`

- [ ] `proprio`, fiche d'« esther v1 » (de « Collection Test ») : « Repartir de zéro… » ouvre un panneau avec un tableau « qui perd quoi » (qui, combien de gestes de chaque sorte) ; « Repartir de la transcription » → la tête de l'album porte la puce « repartie de la transcription le … »
- [ ] `stagiaire`, une planche de « Lot TIFF QA » (qu'il n'a pas créé) : ↺ ouvre un panneau qui dit qu'une planche ne se remet pas à zéro sur demande, et renvoie à l'album entier ou à un administrateur — aucun bouton d'envoi
- [ ] `stagiaire`, fiche de « Lot TIFF QA » : « Repartir de zéro… » vers « Images seules » exige un motif et la certification, puis part en demande
- [ ] `admin-bd`, Administration → À faire : la demande est dans une tranche ROSE ; « Garder » la laisse ; la rouvrir (ou en refaire une), « Repartir … » demande confirmation puis efface

### Supprimer et retirer — `proprio`, puis `arrivant`

- [ ] `proprio`, la copie « Images seules » qu'a faite `stagiaire` (« Collection Test ») : « Supprimer… », définitivement → le panneau dit qui perd quoi AVANT, puis l'efface sans demande (le document a d'autres copies)
- [ ] `proprio`, « Lot TIFF QA » : « Supprimer… », définitivement → c'est la dernière copie de ce document : le panneau le dit, et le geste devient une DEMANDE à un administrateur
- [ ] `proprio`, la copie d'« esther v1 » de « Carnet d'arrivant » : « Retirer du projet… » → ce qui part et où (au fonds, avec son travail) ; confirmé, elle quitte le projet
- [ ] `arrivant`, « Carnet d'arrivant », onglet *Albums* : la ligne « esther v1 a été retiré du projet par proprio … » en tête ; « Vu » la fait partir, et elle ne revient pas après F5

### « ⟳ Actualiser » se repère — `proprio` et `stagiaire`, Atelier, « esther v1 », même planche

- [ ] `stagiaire` modifie le texte d'une bulle (Transcription, Tab) ; chez `proprio`, au plus 30 s après (ou en revenant sur l'onglet), « ⟳ Actualiser » apparaît en bouton PLEIN, de couleur cyan, seul de son espèce dans la bande — on le voit apparaître sans le chercher (sinon : écrire ici ce qui manque)

### Rendre la recette — PowerShell

- [ ] `C:\temp\bd-recette\etat-de-base.ps1 restaurer avant-3b` finit par « bd-app : running »
