---
passe: Le regroupement — Échap et le focus des modales, le mode de l'Atelier au rechargement, le cadre au zoom
chantier: —
duree: 15 min
derniere: 2026-10-23
---

# QA — ce que la passe du push a fait corriger : les modales au clavier, F5 dans l'Atelier, la Transcription sur sa bulle, le cadre au zoom

**Écrite le 2026-10-23 sur la recette reconstruite sur `b71a057`**, décor de l'état `apres-lot1`
(« Lot TIFF QA », « pl.3 » : deux cases, des bulles, une boîte personnage). Non jouée. Elle porte
sur ce que la passe `lot-1-suite` et la passe au lecteur d'écran ont relevé, corrigé dans la
foulée : `A11Y-3` (`3718bf1` : un clic dans le vide d'une modale ne lui retire plus le clavier ;
`4a999d1` : après « Enregistrer », le focus va au bouton redessiné, plus en haut de la page),
`UX-12` (`35f393d` : le mode de l'Atelier est dans l'adresse, F5 y rouvre ; `b71a057` : la
Transcription s'ouvre sur la bulle sélectionnée), `UX-7` (`61d648d` : le cadre liste-et-fiche
tient dans la fenêtre sous le zoom ; `8b96f8f` : l'explorateur ShareDocs garde son bouton).

**Ce que la passe ne juge pas** : l'explorateur ShareDocs (« Importer » et sa liste qui défile)
demande un compte Huma-Num, que la recette n'a pas — les tests le jouent sur une doublure ;
ce que Narrateur prononce, que la passe `region-des-messages` reprend.

Les fenêtres privées des comptes. Une passe à jouer dans l'ordre ; la dernière zone rend la
recette.

## Reste

### Une modale garde le clavier — compte `proprio`, Bibliothèque puis Exploration

- [x] Fiche de « Lot TIFF QA », « Modifier » : cliquer sur le TITRE de la fenêtre, puis Échap → elle se ferme, et le focus est sur « Modifier » (Tab puis Maj+Tab le montrent si l'anneau ne se voit pas)
- [x] « Modifier » de nouveau : cliquer dans le VIDE de la boîte, puis Tab plusieurs fois → le focus tourne DANS la fenêtre, jamais derrière elle ; Échap la ferme
- [x] Exploration, « 📖 Lexique » : cliquer sur un texte qui n'est pas un champ, puis Échap → le Lexique se ferme ; au clic, aucun cadre de focus ne s'allume autour de la boîte

### Après « Enregistrer », le clavier reste où l'on était — compte `proprio`, Bibliothèque, au clavier

- [x] Fiche de « Lot TIFF QA » : Tab jusqu'à « Modifier », Entrée ; Tab jusqu'à « Enregistrer », Entrée → « Album enregistré », la fenêtre se ferme, et le focus (son anneau visible) est sur « Modifier » de la fiche — pas en haut de la page : un Tab mène à l'élément qui SUIT « Modifier »
- [x] Une collection que `proprio` possède (« Collection Test »), onglet *Description*, « Modifier », changer un mot, « Enregistrer » → le focus est sur « Modifier » du panneau

### F5 rouvre l'Atelier dans son mode — compte `proprio`, Atelier, « Lot TIFF QA », « pl.3 »

- [x] Sélectionner une bulle, `a` (Annotation) : l'adresse finit par `…&mode=annotation` ; F5 → l'Atelier rouvre en Annotation, sur la même bulle, sa note et ses tags affichés
- [x] `e` (Édition), F5 → en Édition, la même région sélectionnée ; `n` (Navigation) : `mode=` disparaît de l'adresse
- [x] Dans l'adresse, remplacer le mode par `mode=bidule`, Entrée → l'Atelier s'ouvre en Navigation, sans message d'erreur

### La Transcription s'ouvre sur la bulle choisie — compte `proprio`, Atelier, « Lot TIFF QA », « pl.3 »

- [x] Navigation, cliquer la DEUXIÈME bulle de lecture, `t` → « Bulle 2 / … », son texte dans la zone de saisie ; F5 → toujours « Bulle 2 / … »
- [x] `n`, cliquer une CASE qui contient des bulles, `t` → la Transcription s'ouvre sur la première bulle de CETTE case (pas sur la bulle 1 de la planche, si la case n'est pas la première)
- [x] `n`, un clic sur la planche hors de toute région (rien de sélectionné dans le panneau), `t` → « Bulle 1 / … »

### Le cadre tient dans la fenêtre sous le zoom — outils de développement en mode appareil, 1280 × 400

- [x] Compte `proprio`, Bibliothèque, « A+ » jusqu'à 200 % : le cadre liste-et-fiche finit AU-DESSUS du bas de la fenêtre ; la liste et la fiche défilent chacune seule
- [x] Compte `admin-bd`, Administration → Projets, 200 % : même chose ; puis « ↺ » dans chaque fenêtre

### Rendre la recette — PowerShell

- [x] `C:\temp\bd-recette\etat-de-base.ps1 restaurer apres-lot1` finit par « bd-app : running »
