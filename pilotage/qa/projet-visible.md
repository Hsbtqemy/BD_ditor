---
passe: Le projet se voit — et n'ouvre rien d'autre
chantier: COL-3
duree: 35 min
derniere: —
---

# QA — le projet se lit en haut de chaque page, se règle dans l'Administration, et rien d'autre n'a changé

`6c3e19f`, `9eec56e` puis `7eabeb7` ont posé un étage au-dessus des collections : le PROJET. Tout
l'existant est rangé dans un premier projet ; son nom se lit dans la bande du haut des cinq
surfaces ; la Bibliothèque ne liste que les collections du projet choisi ; l'Administration a
un bloc « 🗂️ Projets ». C'est la tranche 1 de `COL-3`, et sa promesse tient en une phrase :
le projet existe et se voit, et rien d'autre ne change.

**Ce que les tests couvrent déjà — ne pas le refaire ici** : les règles du serveur (qui
règle, qui décide, les refus et leurs codes), les requêtes parties de chaque geste, le nom
qui ne se coupe pas à 320 px, les cinq surfaces sous axe dans les deux thèmes, Chromium et
Firefox.

**Ce qui se regarde ici** : ce que l'écran DIT à quatre personnes qui n'ont pas les mêmes
droits, et s'il le dit là où on le cherche. Une suite verte vérifie des codes et des
structures ; elle ne sait pas si « Vous n'y réglez rien » se comprend.

**Ce que la passe ne juge pas** : la bande du haut à 320 px et à grande police — ce sont les
zones « Après `9eec56e` » des passes *Préférence de police* et *Petites largeurs* ; et la
Recherche, l'Exploration et l'Atelier, qui traversent encore les projets (tranche 4).

**Où** — la pile de recette, `https://bd.127-0-0-1.sslip.io`, **reconstruite sur un HEAD qui
contient `7eabeb7`**. Sa base a migré en version 29 à ce démarrage. Quatre comptes :
`admin-bd` (administrateur), `proprio`, `stagiaire`, `lectrice`. Aucun décor à monter : la
passe crée elle-même son second projet, « Séminaire QA », et les zones se jouent DANS L'ORDRE
— chacune s'appuie sur ce que la précédente a laissé.

### La recette porte le commit — compte `admin-bd`, Administration puis Bibliothèque

- [ ] Administration, bloc « 🏷️ Version servie » : le commit affiché est `7eabeb7` ou un commit plus récent — sur un serveur plus ancien, aucune case de cette passe ne mesure rien
- [ ] Bibliothèque : les collections d'avant sont toutes là (« Collection Test », « Étude B »…), et juste au-dessus du titre « 📚 Collections » on lit « Dans le projet « Projet principal » » — tout l'existant est rangé dans le premier projet

### Un seul projet, un nom et pas de liste — compte `stagiaire`, les cinq surfaces

- [ ] Atelier, Bibliothèque, Recherche, Exploration, Administration : en haut à droite, avant la pastille du compte, on lit « Projet » puis « Projet principal », en simple texte — pas de liste déroulante, rien à cliquer
- [ ] Administration : sous « 🗂️ Projets », une phrase et rien d'autre — elle dit que les projets se règlent par leur responsable, que `stagiaire` est membre de « Projet principal » et n'y règle rien ; aucun champ, aucun bouton, aucun nom d'un autre compte

### Créer un second projet et y faire entrer — compte `admin-bd`, Administration, bloc « 🗂️ Projets »

- [ ] Le bloc montre un champ « Nouveau projet », la phrase « 21 caractères au plus… », un champ pour dire pourquoi le projet existe, et à gauche la liste des projets : « Projet principal », avec son nombre de collections
- [ ] Taper `Séminaire émotions 2026` (23 caractères) puis « + Créer le projet » : un refus en rouge sous le champ, qui donne le plafond ET le nombre de caractères du nom tapé ; aucun projet n'est créé
- [ ] Taper `Séminaire QA`, une justification de deux lignes, puis « + Créer le projet » : le message dit « « Séminaire QA » créé. Il est vide… », sa fiche s'ouvre à droite avec la justification sous « Pourquoi ce projet existe » (les deux lignes séparées), et dans la bande du haut le nom devient une LISTE déroulante à deux noms — sans avoir rechargé la page
- [ ] Fiche de « Séminaire QA », « Qui y entre » : « Faire entrer » → « Un compte, ou un groupe absent de la liste… », taper `proprio`, laisser « Compte ou groupe ? », « + Faire entrer » : un refus demande de dire si c'est un compte ou un groupe. Choisir « Compte » et recommencer : `proprio` apparaît dans la liste, rôle « membre », et le message dit qu'aucune collection ne lui est ouverte pour autant
- [ ] Sur la ligne de `proprio`, passer le rôle à « responsable du projet » : la ligne passe en tête de liste, sans message d'erreur
- [ ] Faire entrer `lectrice` de la même façon et la laisser « membre ». Puis ouvrir « Faire entrer » : si la liste propose des « Groupes de l'annuaire », en choisir un et « + Faire entrer » — il entre sans qu'on ait à dire que c'est un groupe (si la liste n'en propose aucun, l'écrire ici plutôt que de cocher)
- [ ] Sur la ligne de `proprio`, repasser le rôle à « membre » : un refus en rouge dit que c'est le dernier responsable du projet, et le rôle affiché reste « responsable du projet »
- [ ] Sous la liste des membres, deux notes se lisent sans chercher : entrer dans le projet n'ouvre pas ses collections ; les administrateurs règlent tout projet sans figurer dans la liste

### Deux projets, une liste — compte `proprio`, bande du haut et Bibliothèque

- [ ] Sur les cinq surfaces, « Projet » est suivi d'une liste déroulante à deux noms, « Projet principal » choisi
- [ ] Bibliothèque, choisir « Séminaire QA » dans la liste du haut : sans rechargement, la ligne au-dessus de « 📚 Collections » devient « Dans le projet « Séminaire QA » », et la liste dit qu'aucune collection ne lui est ouverte DANS CE PROJET — pas « aucune collection » tout court
- [ ] Toujours sur « Séminaire QA », créer la collection `Étude QA` : elle apparaît. Repasser sur « Projet principal » : elle n'y est pas, et les collections habituelles sont revenues. Revenir sur « Séminaire QA » : elle y est
- [ ] « Séminaire QA » choisi, « + Nouvel album » : la liste « Collection » ne propose QUE « Étude QA », et une ligne dessous dit que seules les collections du projet « Séminaire QA » sont proposées et où changer de projet. Fermer sans enregistrer
- [ ] « Séminaire QA » toujours choisi, ouvrir par son crayon la fiche d'un album du PREMIER projet (la liste des albums, en bas de page, ne suit pas le projet) : sous « Collections », la liste de « + Ranger ici » ne propose pas « Étude QA », et une ligne dit que cet album vit dans le projet « Projet principal » et ne se range pas d'un projet à l'autre
- [ ] « Séminaire QA » choisi, aller sur l'Atelier, revenir à la Bibliothèque, puis recharger la page : le projet choisi est resté « Séminaire QA »
- [ ] « Séminaire QA » choisi, ouvrir l'Atelier puis la Recherche : on y voit toujours les albums et les résultats du premier projet. C'est l'attendu de cette tranche — le projet choisi ne borne que la liste des collections. Dire ici si, à l'usage, on croit s'être trompé de projet

### La responsable règle, elle ne décide pas — compte `proprio`, Administration, bloc « 🗂️ Projets »

- [ ] Pas de champ « Nouveau projet ». À gauche un seul projet, « Séminaire QA » — « Projet principal », où elle n'est que membre, n'y figure pas. La fiche montre la justification que l'administrateur a saisie
- [ ] Fiche, « Collections » : « Étude QA » est un lien ; le suivre ouvre la Bibliothèque sur cette collection dépliée, « Séminaire QA » choisi dans la bande du haut
- [ ] Fiche, « Ce projet » : ni « Renommer », ni champ « Description » ou « Pourquoi ce projet existe », ni « Supprimer le projet » ; à leur place, une phrase dit qu'elle règle qui entre et que renommer ou supprimer se demande à un administrateur de l'instance
- [ ] « Qui y entre » : faire sortir `lectrice` par le ✕ de sa ligne, puis la faire rentrer comme « membre » : les deux gestes passent, chacun laisse un message, et après chacun on est toujours dans la fiche — pas renvoyé en haut de la page

### Membre, rien à régler — compte `lectrice`, Bibliothèque puis Administration

- [ ] Bibliothèque, « Séminaire QA » choisi dans la liste du haut : « Étude QA » N'APPARAÎT PAS — être du projet n'ouvre aucune de ses collections —, et la liste dit qu'aucune collection ne lui est ouverte dans ce projet
- [ ] Administration, sous « 🗂️ Projets » : une seule phrase, qui nomme les deux projets dont elle est membre et dit qu'elle n'y règle rien ; ni liste de membres, ni justification, ni nom de responsable

### Renommer, supprimer, et ce que le serveur refuse — compte `admin-bd`, Administration, bloc « 🗂️ Projets »

- [ ] Fiche de « Projet principal », « Ce projet » : pas de bouton « Supprimer le projet », et une phrase dit que c'est le projet de repli. Le renommer en `Corpus franco-belge` : le message dit « Le projet s'appelle désormais « Corpus franco-belge ». », et la bande du haut porte le nouveau nom sans rechargement
- [ ] Fiche de « Séminaire QA », « Ce projet » : modifier le texte de « Pourquoi ce projet existe », puis « Enregistrer » : le message dit « Justification enregistrée. », et plus haut dans la fiche le texte sous « Pourquoi ce projet existe » est le nouveau, sans rechargement. Dire ici si ce message, placé sous le bouton rouge, se voit sans le chercher
- [ ] Même fiche, « Enregistrer » sans rien avoir changé : « Rien n'a changé. » ; puis vider le champ « Description » et « Enregistrer » : la description disparaît du haut de la fiche
- [ ] Fiche de « Séminaire QA », « Supprimer le projet », confirmer : un refus en rouge — une collection lui appartient, un projet ne se supprime que vide. Le projet est toujours dans la liste
- [ ] Créer un projet `À jeter`, puis le supprimer : la confirmation dit que ses membres en sortent et qu'aucune collection n'est touchée ; il disparaît de la liste du bloc ET de la liste de la bande du haut

### Rien d'autre n'a changé — comptes `admin-bd` puis `proprio`, Administration, Bibliothèque, Atelier

- [ ] Compte `admin-bd`, premier projet choisi dans la bande du haut : Administration → « 👥 Comptes et groupes » → axe *Collections* → « Étude QA » → sous son panneau *Qui entre*, « Décrire dans la Bibliothèque ↗ ». La Bibliothèque s'ouvre sur « Étude QA » dépliée, et la bande du haut est passée d'elle-même sur « Séminaire QA » — pas de message « elle ne vous est pas ouverte, ou elle n'existe pas »
- [ ] Compte `proprio`, premier projet choisi : déplier une collection qu'elle possède — « Qui entre », la description, le régime de diffusion et l'export sont là, comme avant
- [ ] Compte `proprio`, Atelier : ouvrir une planche, modifier la note d'une bulle, puis Ctrl+Z — la note revient, comme avant
