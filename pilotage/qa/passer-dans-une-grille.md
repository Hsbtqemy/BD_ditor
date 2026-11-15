---
passe: « Passer dans une grille… » et les quatre constats de la montée
chantier: ANN-7
duree: 30 min
---

# QA — faire passer une étiquette du Mode libre dans « Sons et images (fictive) »

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur `1d811ee`
(« ANN-7 : Ctrl+Z d'un relevé passé ou fusionné nomme l'entrée ») ou après, état
`apres-moustache` restauré (`C:\temp\bd-recette\etat-de-base.ps1 restaurer apres-moustache`).
Les mots de passe sont dans `C:\temp\bd-recette\comptes.txt`. Deux fenêtres côte à côte, à
1 280 px de large (`fenetres.ps1 proprio stagiaire`).

**Le décor.** « Projet principal » : sa grille de travail (onglet « Mode libre ») et « Sons et
images (fictive) », FERMÉE, v1 publiée et active. « ton de voix » s'y pose une seule fois sur
une bulle, avec les valeurs « chuchoté » et « crié » ; « regard caméra » se pose sur une case,
sans valeur ; « ambiance sonore de la planche » sur la planche.

**Écrite le 2026-11-15** d'après le rapport de l'agent qui a codé le geste ; jouée par personne
à l'écran. Le geste et la plupart des cases sont joués par `tests/test_passer_dans_une_grille.py`
(l'API) et `tests/test_e2e_annotation_page.py` (la page). Indépendante de
`pilotage/qa/montee-de-version.md` : chacune part de l'état restauré.

### Préparer, sous `stagiaire`
- [ ] Page Annotation, planche 1, onglet « Mode libre », sur une bulle : taper « voix : crié » puis Entrée ; sur une seconde bulle, « voix : murmure » ; sur une case, « voix : crié » : les trois relevés se lisent dans ce qui est posé
- [ ] « ✎ » sur « voix » : « Passer dans une grille… » est éteint ; le cliquer dit « Passer une étiquette dans une autre grille : les responsables du projet », et rien ne s'ouvre d'autre

### Le bilan, sous `proprio`
- [ ] Page Annotation, même planche, « Mode libre », « ✎ » sur « voix », « Passer dans une grille… » : sous la ligne, la grille « Sons et images (fictive) · v1 » est déjà choisie, la phrase dit « Aucune entrée « voix » dans la version 1 active … écrivez-la dans le brouillon, publiez, montez la version, puis revenez », et « Passer » est grisé
- [ ] Choisir l'entrée « ton de voix » : la table montre « « crié » · 2 → crié » et « « murmure » · 1 → — aucune — » ; la phrase dit « 1 relevé passe … 2 restent dans le Mode libre » ; dessous, « reste · l'entrée ne se pose pas sur ce type de zone 1 » et « reste · la valeur n'a pas d'équivalent 1 »
- [ ] Dans la table, mettre « murmure » sur « chuchoté » : la phrase se relit et dit « 2 relevés passent » ; « Passer » n'est plus grisé ; le survol de « Passer » grisé, avant, disait pourquoi

### Deux écrans
- [ ] Fenêtre `stagiaire`, sans recharger, poser « voix : crié » sur une troisième bulle ; fenêtre `proprio`, « Passer » : un message dit que le bilan n'est plus celui qu'on a lu, la phrase se redessine avec un relevé de plus, et rien n'a bougé dans la liste de ce qui est posé

### Passer, sous `proprio`
- [ ] « Passer » : l'annonce dit « Passée dans Sons et images (fictive) › ton de voix : 3 relevés, 1 reste » ; les trois bulles portent « ton de voix · crié » ou « · chuchoté » dans ce qui est posé, et la case garde « voix · crié »
- [ ] Recherche, « crié » dans le champ : la case est trouvée par son étiquette, les trois bulles non (une grille fermée n'entre pas dans l'index)
- [ ] Bibliothèque, l'album, « Autres gestes », « Supprimer… » : « qui perd quoi » ne nomme pas `proprio` pour le passage ; seule `stagiaire` y compte des relevés
- [ ] Administration › Projets › « Projet principal », bloc « Grilles » : aucune version neuve de « Sons et images (fictive) » (toujours « v1 publiée · active », pas de brouillon)

### Ctrl+Z, sous `stagiaire`
- [ ] Fenêtre `stagiaire`, « ⟳ Actualiser », puis Ctrl+Z hors d'un champ (son dernier geste : « voix : crié » sur la troisième bulle, passé depuis) : le message dit « Annulation impossible : l'entrée a été modifiée depuis par » suivi du nom de `proprio`, et offre « Passer ce geste » ; la bulle garde son « ton de voix · crié »

### L'étiquette vidée, sous `proprio`
- [ ] Retirer le relevé « voix · crié » de la case (✕) ; sur une nouvelle bulle, « voix : chuchoté » ; « ✎ » sur « voix », « Passer dans une grille… », entrée « ton de voix » : la phrase finit par « « voix » sera vide : vous pourrez la retirer. »
- [ ] « Passer » : sous la ligne, « Retirer « voix » : personne ne la pose, elle disparaît. » s'ouvre aussitôt, le focus sur « Retirer » ; « Retirer » : « voix » quitte le Mode libre

### Les quatre constats de la montée, sous `proprio`
- [ ] Fenêtre `stagiaire`, onglet « Sons et images (fictive) », sur une case : poser « regard caméra » ; il se lit dans ce qui est posé, sans valeur
- [ ] Administration, « Sons et images (fictive) », « Modifier… », passer « regard caméra » à variantes (« direct », « de biais »), « Publier la v2… », « Publier la v2 » ; rouvrir « Modifier… » : l'en-tête du formulaire offre « Monter à la version 2… », et plus « Activer la v2 »
- [ ] « Monter à la version 2… » de l'en-tête : le formulaire se ferme et la confirmation s'ouvre sous la ligne de la grille, la phrase du bilan au focus ; « Monter à la version 2 »
- [ ] Fenêtre `stagiaire`, la page Annotation restée ouverte sur la planche : « ⟳ Actualiser » paraît, et son infobulle dit « la grille « Sons et images (fictive) » est passée à une autre version », sans « étiquettes »
- [ ] Après « Actualiser », un relevé « regard caméra » posé avant la montée se lit « à compléter · choisissez une valeur », et sa ligne offre un choix « choisissez une valeur… » ; y choisir « direct » : la ligne ne dit plus « à compléter », et Synthèse › À revoir ne la montre plus
