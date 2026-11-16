---
passe: La montée de version d'une grille fermée
chantier: ANN-7
duree: 30 min
---

# QA — monter « Sons et images (fictive) » de la v1 à la v2 sous des relevés

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur `5a15b5c`
(« ANN-7 : la montée de version dans la documentation ») ou après, état `apres-moustache`
restauré (`C:\temp\bd-recette\etat-de-base.ps1 restaurer apres-moustache`). Les mots de passe
sont dans `C:\temp\bd-recette\comptes.txt`. Deux fenêtres côte à côte, à 1 280 px de large
(`fenetres.ps1 proprio stagiaire`).

**Le décor de l'état restauré.** « Sons et images (fictive) » est la grille de « Projet
principal » : fermée, v1 publiée et active, « Porte sur » des mots. « cri » s'y pose sur des
mots, donc plusieurs fois par zone ; « écho » est une entrée à qualificatifs de « B. Provenance ».

**Écrite le 2026-11-15** d'après le rapport de l'agent qui a codé la montée ; jouée par
personne à l'écran. Le parcours entier est joué par `tests/test_e2e_montee.py`, relu par l'API.

### Préparer la v2
- [x] Fenêtre `stagiaire`, page Annotation, planche 1 : poser « cri » sur deux mots de la même bulle, « écho » sur une autre, « onomatopée de choc · bang » sur une troisième ; marquer « terminée » la bulle de « cri » pour toute la grille, puis pour « B. Provenance » : chaque relevé se lit dans la liste de ce qui est posé, et la minicarte marque la bulle terminée
- [x] Fenêtre `proprio`, Administration › Projets › « Projet principal », bloc « Grilles », « Modifier… » sur la grille : renommer « cri » en « cri poussé », retirer « écho », passer « cri » à « une seule fois », ajouter une entrée « soupir » sous « Voix » ; « ← Projet principal », « Publier la v2… », « Publier la v2 » : la ligne de la grille offre « Monter à la version 2… », et plus « Activer la v2 »

### Le bilan, sous `proprio`
- [x] « Monter à la version 2… » : sous la ligne, la phrase commence par « N relevés passent en version 2. » et dit qu'une cible porte deux relevés d'une entrée qui ne s'y pose plus qu'une fois ; « Refusé · 1 » montre « la zone ↗ » ; « Monter à la version 2 » est grisé, et la raison s'affiche à côté
- [x] « la zone ↗ » ouvre la bulle dans la page Annotation ; fenêtre `stagiaire`, retirer l'un des deux « cri » ; fenêtre `proprio`, « Annuler » puis « Monter à la version 2… » : « Refusé » a disparu
- [x] « À répondre · 1 » dit « « écho » est retirée » ; le menu offre « Laisser : … à revoir » et « Fusionner dans « origine du son » » ; tant que rien n'est choisi, « Monter à la version 2 » reste grisé, et le dit au clic

### Deux écrans pendant la montée
- [x] Fenêtre `stagiaire`, sans recharger, poser « cri » sur un mot d'une autre bulle ; fenêtre `proprio`, choisir « Laisser », puis « Monter à la version 2 » : un message dit que le bilan a changé, et le bilan se redessine avec un relevé de plus
- [x] Fenêtre `proprio`, « Monter à la version 2 » : un message dit « « Sons et images (fictive) » est montée à la version 2 : N relevés passent. », et la ligne dit « v2 publiée · active »

### Après la montée, sous `stagiaire`
- [x] Fenêtre `stagiaire`, sans recharger : « ⟳ Actualiser » paraît dans les trente secondes ; le cliquer : l'onglet de la grille montre « cri poussé » et « soupir », et le relevé « écho » se lit « à revoir », sa cause disant que l'entrée n'est plus dans la grille
- [x] Sur la bulle de « cri », la passe « toute la grille » n'est plus terminée (« soupir » est à regarder), et celle de « B. Provenance » l'est encore
- [x] Ctrl+Z hors d'un champ défait le dernier relevé posé, qui quitte la liste ; poser « soupir » sur un mot réussit, et le relevé se lit dans la liste
- [x] Fenêtre `proprio`, Bibliothèque, l'album de la planche, « Autres gestes », « Supprimer… » : « qui perd quoi » ne nomme pas `proprio` pour la montée
