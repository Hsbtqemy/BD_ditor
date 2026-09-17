---
passe: Conflit à deux sur le même champ
chantier: CONC-3
duree: 35 min
derniere: —
---

# QA — deux personnes sur la même bulle : l'Atelier le dit, et ne perd rien

Le second temps de `CONC-3` refuse un enregistrement fait sur une version périmée, et
l'Atelier ouvre alors un bandeau au-dessus du champ. La forme du bandeau a été tranchée sur
maquette le 2026-09-17 ; celle de l'attente au départ d'une bulle, le même jour, sans
maquette et sur description. Les tests jouent deux navigateurs derrière un proxy simulé ; ils
ne disent pas si l'heure affichée est celle de l'horloge, si le bandeau se lit à côté de la
saisie, ni si les gestes se comprennent. C'est ce que cette passe regarde, sous deux vrais
comptes.

**Sur la pile locale**, `https://bd.127-0-0-1.sslip.io`, ouverte par `C:\temp\recette-chrome.cmd`
(Chrome sans le proxy du campus). **La pile doit servir `6952f37` ou un commit plus récent** :
sous `admin-bd`, *Administration → 🏷️ Version servie*. Plus ancienne, l'attente au départ
d'une bulle manque ou diffère ; avant `fc557a3`, aucun bandeau ne s'ouvre, et la dernière
écriture efface la précédente sans rien dire. Les mots de passe sont dans
`C:\temp\bd-recette\comptes.txt`, hors dépôt.

**Deux identités : `proprio` dans une fenêtre normale, `stagiaire` dans une fenêtre
privée.** Une session Authelia est partagée par tous les onglets d'une fenêtre, et par
toutes les fenêtres privées. Les deux comptes écrivent sur « Collection Test », donc sur
« esther v1 ». Sur la recette, le nom affiché d'un compte est son login : le bandeau dit
« par stagiaire », là où la production dirait un nom.

**L'ordre compte.** Chaque cas demande que l'écran qui reçoit le bandeau ait été ouvert
AVANT l'enregistrement de l'autre, et ne soit PAS rechargé ensuite : c'est ce qui rend sa
version périmée. Un rechargement de trop, et l'écriture passe sans conflit ; la case échoue
alors sans que l'écran y soit pour rien.

**L'heure du bandeau** est celle de l'autre enregistrement, en heure du poste. Noter l'heure
de l'horloge de Windows au moment de chaque « Enregistré » de l'autre compte : c'est
l'attendu.

### Deux notes sur la même bulle

**Préalable.** Sous `proprio`, l'Atelier sur *esther v1*, première planche, mode
*Annotation* (touche `A`) : choisir une bulle dont la note est VIDE. Ouvrir la même
planche, la même bulle et le même mode sous `stagiaire`. Les deux fenêtres restent côte à
côte pour toute la zone.

- [ ] Sous `stagiaire` : taper « note stagiaire » dans la note, attendre « Enregistré ». Sous `proprio`, SANS recharger : cliquer dans la note et taper « note proprio ». Dans la seconde, un bandeau s'ouvre au-dessus du champ, titré « Note modifiée par stagiaire à » suivi de l'heure notée. Il montre « note stagiaire » sous « Version de stagiaire, enregistrée », et l'indicateur sous le champ dit « En attente de votre choix »
- [ ] Toujours sous `proprio` : « note proprio » est restée dans le champ, et continuer à taper écrit dans le champ, sans avoir cliqué nulle part — le bandeau n'a pas pris le curseur
- [ ] `Maj+Tab` depuis le champ : le contour de focus se pose sur « Garder l'autre », dans le bandeau ; `Maj+Tab` encore, sur « Remplacer par la mienne »
- [ ] Cliquer « Navigation » dans la barre des modes : un message « Choisissez d'abord une version » apparaît, et « Annotation » reste le mode actif. Cliquer une autre bulle sur la planche : même message, et la sélection ne bouge pas
- [ ] Sous `proprio`, ajouter le tag `qa-conflit` à la bulle, puis sous `stagiaire` recharger la page et resélectionner la bulle : elle porte le tag `qa-conflit`, et la note est toujours « note stagiaire »
- [ ] Sous `proprio`, cliquer « Remplacer par la mienne » : le bandeau disparaît, l'indicateur passe à « Enregistré ». Sous `stagiaire`, recharger et resélectionner : la note est celle de `proprio`
- [ ] Sous `proprio`, sans recharger : remplacer la note par « note proprio 2 » et attendre « Enregistré ». Sous `stagiaire`, sans recharger depuis la case précédente : ajouter « (suite) » à la fin de la note. Le bandeau s'ouvre, titré « Note modifiée par proprio à » suivi de l'heure notée, et montre « note proprio 2 »
- [ ] Sous `stagiaire`, cliquer « Garder l'autre » : le bandeau disparaît, le champ affiche « note proprio 2 » et l'indicateur « Enregistré » ; recharger et resélectionner la bulle : la note est toujours « note proprio 2 »
- [ ] Remettre en état, sous `proprio` : retirer la puce `qa-conflit`, vider la note, attendre « Enregistré » ; après rechargement, le panneau *Annotation* de la bulle est vide

### Deux onglets du même compte

**Sous `proprio` seul**, deux onglets de la fenêtre normale, sur la même bulle à note vide,
en mode *Annotation*, ouverts tous les deux avant de rien taper.

- [ ] Onglet 1 : taper « écran 1 », attendre « Enregistré ». Onglet 2, sans recharger : taper « écran 2 ». Le bandeau est titré « Note modifiée depuis un autre écran de ce même compte à » suivi de l'heure, et le mot « proprio » n'y figure nulle part. Au-dessus de la version montrée : « Version de l'autre écran, enregistrée »
- [ ] Remettre en état : dans l'onglet 2, cliquer « Garder l'autre », puis vider la note et attendre « Enregistré » ; après rechargement des deux onglets, la note de la bulle est vide

### Transcription

**Préalable.** Sous `proprio` et sous `stagiaire`, l'Atelier sur la même planche d'*esther
v1*, mode *Transcription* (touche `T`), sur la PREMIÈRE bulle (« Bulle 1 / … »). **Recopier
son texte quelque part avant tout** : la remise en état le demande.

- [ ] Sous `stagiaire` : ajouter « QA » à la fin du texte, attendre « Enregistré ». Sous `proprio`, sans recharger : cliquer à la fin du texte et taper « X ». Le bandeau s'ouvre au-dessus de la zone de texte, titré « Texte modifié par stagiaire à » suivi de l'heure notée, et montre le texte terminé par « QA » ; la zone de texte garde le texte de `proprio`, terminé par « X »
- [ ] Sous `proprio`, pendant le bandeau : « ‹ Précédent » et « Valider + Suivant › » sont grisés et ne répondent pas ; cliquer une autre bulle dans la mini-planche affiche « Choisissez d'abord une version », et l'en-tête dit toujours « Bulle 1 / … »
- [ ] Sous `proprio`, cliquer « Garder l'autre » : le bandeau disparaît, la zone de texte montre le texte terminé par « QA », et les deux boutons de navigation redeviennent actifs
- [ ] Remettre en état, sous `proprio` : remettre dans la zone de texte le texte recopié au préalable, attendre « Enregistré » ; recharger, revenir en *Transcription* sur la première bulle : le texte est celui d'origine

### Quitter une bulle pendant son enregistrement

**Sous `proprio`**, Atelier en *Annotation* sur une bulle à note vide. Un serveur lent se
simule dans Chrome : `F12`, onglet *Network* (*Réseau*), menu de limitation (« No
throttling »), *Add…* : créer un profil « QA lent 2 s » avec **Latency 2000** ms, et un profil
« QA muet 8 s » avec **Latency 8000** ms. La limitation n'agit que tant que les outils de
développement restent ouverts.

- [ ] Profil « QA lent 2 s » actif : taper « lent » dans la note puis, AUSSITÔT, cliquer « Navigation ». L'indicateur sous la note dit « Enregistrement en cours… » et « Annotation » reste le mode actif ; environ deux secondes plus tard, l'Atelier passe de lui-même en *Navigation*, sans second clic
- [ ] Revenir en *Annotation* et attendre le chargement : la note de la bulle est « lent »
- [ ] Profil « QA muet 8 s » : ajouter « muet » à la fin de la note puis cliquer aussitôt « Navigation ». Au bout d'environ cinq secondes, un message dit « L'enregistrement n'a pas encore abouti. Votre saisie reste dans le champ ; refaites le geste pour partir quand même. » ; la note montre toujours « lent muet », et « Annotation » est toujours le mode actif
- [ ] Cliquer de nouveau « Navigation » : le mode change tout de suite. Remettre « No throttling », patienter dix secondes, revenir en *Annotation* : la note est « lent muet »
- [ ] Sans limitation, avec `stagiaire` dans la fenêtre privée sur la même bulle, ouverte avant la suite : sous `stagiaire`, remplacer la note par « stagiaire », attendre « Enregistré ». Sous `proprio`, sans recharger, ajouter « proprio » à la note puis cliquer aussitôt « Navigation » : « Annotation » reste le mode actif, le bandeau s'ouvre, titré « Note modifiée par stagiaire à » suivi de l'heure, et la note de `proprio` est restée dans le champ
- [ ] Remettre en état : sous `proprio`, cliquer « Garder l'autre », vider la note et attendre « Enregistré » ; après rechargement, la note de la bulle est vide ; fermer les outils de développement (les profils créés peuvent rester)

### Une région déplacée, puis supprimée, ailleurs

**Préalable.** Sous `proprio`, mode *Édition* (touche `E`), première planche d'*esther v1* :
`Maj` enfoncée, tirer un petit rectangle DANS une case, puis relâcher. La région apparaît
sélectionnée : c'est une bulle, puisqu'elle est tracée dans une case. Sous `stagiaire`,
ouvrir la même planche en *Édition* : la nouvelle bulle y figure. À partir de là, ne plus
recharger `proprio`.

- [ ] Sous `proprio` : faire glisser la nouvelle bulle à la souris, de quelques millimètres, et relâcher. Aucun message ne dit « rechargée », et la bulle reste où on l'a lâchée — un déplacement seul n'est pas un conflit
- [ ] Sous `stagiaire`, RECHARGER la planche (il n'a pas vu le glissement de `proprio`), puis faire glisser la même bulle ailleurs et relâcher : aucun message. Sous `proprio`, sans recharger : la faire glisser encore. Un message dit « Position modifiée par stagiaire à » suivi de l'heure du geste de `stagiaire`, puis « : la région est rechargée. », et la bulle saute à la position que `stagiaire` lui a donnée
- [ ] Sous `stagiaire` : sélectionner la bulle et appuyer sur `Suppr` ; elle disparaît de son écran. Sous `proprio`, sans recharger : la bulle est encore affichée ; la sélectionner, taper « 100 » dans le champ « X » du panneau, `Entrée`. Un message dit « Cette bulle a été supprimée par stagiaire à » suivi de l'heure de la suppression, reste lisible plusieurs secondes, et la bulle quitte la planche. Le mot « introuvable » n'apparaît nulle part
- [ ] Remise en état : sous `proprio`, recharger la planche ; la bulle tracée au préalable n'y figure plus, et rien d'autre n'a bougé

### Ctrl+Z ne défait pas le geste d'un autre

**Préalable.** Sous `proprio`, une bulle à note vide en mode *Annotation*. `stagiaire` ne
l'ouvre qu'au moment où la case le dit.

- [ ] Sous `proprio` : taper « à défaire » dans la note, attendre « Enregistré ». Sous `stagiaire`, ouvrir la bulle : la note est « à défaire » ; la remplacer par « changée par stagiaire », attendre « Enregistré ». Sous `proprio`, `Échap` pour sortir du champ, puis `Ctrl+Z` : un message dit « Annulation impossible : la note a été modifiée depuis par stagiaire à » suivi de l'heure, et après rechargement la note est toujours « changée par stagiaire »
- [ ] Remettre en état, sous `stagiaire` : vider la note, attendre « Enregistré » ; après rechargement, la note de la bulle est vide

### Petite largeur

**Sous `proprio`**, outils de développement, mode appareil à 375 px, Atelier en
*Annotation* sur une bulle à note vide, le panneau ouvert par ▤. Reproduire la première case
de la première zone, avec `stagiaire` dans l'autre fenêtre, en fenêtre large.

- [ ] À 375 px, le bandeau tient dans la largeur du panneau, sans que la page défile de côté ; « Remplacer par la mienne » et « Garder l'autre » se lisent en entier, l'un à côté de l'autre ou l'un sous l'autre
- [ ] Refermer le panneau par ▤ puis le rouvrir : le bandeau et la saisie de `proprio` y sont toujours
- [ ] Remettre en état : cliquer « Garder l'autre » sous `proprio`, puis vider la note sous `stagiaire` et attendre « Enregistré »
