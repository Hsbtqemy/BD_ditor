---
passe: Écran « par où commencer »
chantier: UX-6
duree: 20 min
derniere: 2026-08-27
---

# QA — carte d'accueil : le bon volume d'information

Cette passe est écrite **avant l'écran**, exprès. La question qu'elle pose — huit étapes,
est-ce trop ou pas assez ? — ne se tranche pas sur une liste, et se tranche encore moins
une fois l'écran construit, quand on y est attaché. Fixer les attendus maintenant, c'est
accepter à l'avance qu'ils puissent condamner ce qu'on aura fait.

Elle se rejoue à chaque fois que la carte change de contenu : étape ajoutée, retirée,
fusionnée, ou reformulée. Le verdict sur le nombre d'étapes se reporte dans le `Reste` de
`pilotage/UX-6.md`.

Elle demande **un lecteur qui n'a pas construit l'outil**, et de préférence deux — les
cases sur « trop » et « pas assez » ne veulent rien dire lues par celui qui a écrit la
carte. Sans lecteur disponible, les zones *Chronomètre*, *Les liens tiennent* et *Étroit
et clavier* restent jouables seules ; la zone *Trop, ou pas assez* attend.

### Chronomètre

- [ ] Lu du début à la fin sans cliquer, l'écran prend moins de deux minutes, montre en main
- [ ] Aucune étape n'a besoin d'être dépliée, survolée ou cliquée pour qu'on comprenne ce qu'elle recouvre
- [ ] Le lecteur arrive au bas de la carte sans l'avoir abandonnée en route, et le dit

### Trop, ou pas assez

- [ ] Écran fermé, le lecteur cite de mémoire au moins trois étapes et nomme la surface de chacune
- [ ] Le lecteur ne demande « et ça, ça se fait où ? » pour aucun geste que la chaîne exige — une question de ce genre nomme l'étape qui manque
- [ ] Aucune étape n'est qualifiée d'évidente ou de sautable par deux lecteurs différents — un accord sur ce point nomme l'étape de trop
- [ ] Après lecture, le lecteur sait dire que les passes ML ne font que pré-remplir et que l'annotation reste humaine
- [ ] Le lecteur sait dire, sans rouvrir la carte, par quoi commencer sur un corpus vide et par quoi commencer sur un corpus déjà rempli

### Les liens tiennent

- [ ] Chaque étape ouvre la surface **et** l'outil annoncés en un clic, sans écran intermédiaire
- [ ] Une étape dont le moteur est absent se lit comme optionnelle, pas comme cassée — vérifié en coupant un moteur, pas en le supposant
- [ ] L'étape 8 ne promet que les exports que l'UI porte : rien sur la carte ne renvoie à un bouton qui n'existe pas
- [ ] Rappelée depuis chacune des quatre surfaces, la carte revient à l'identique

### Fermeture et retour

- [ ] Fermée sans cocher « ne plus afficher » (croix, puis Échap), la carte revient au chargement suivant
- [ ] « Ne plus afficher » coché, aucun rechargement ne la rouvre — et le rappel depuis la nav la rouvre quand même
- [ ] Le focus revient sur l'élément qui a ouvert la carte à chaque fermeture, quel que soit le moyen de fermer
- [ ] Tant que la carte est ouverte, la tabulation ne descend jamais dans la page derrière

### Étroit et clavier

- [ ] Sur 375 px de large, la carte se lit sans défilement horizontal et la fermeture reste atteignable
- [ ] À 200 % de zoom navigateur, aucune étape n'est tronquée ni recouverte
- [ ] Toute la carte se parcourt et s'active au clavier seul, sans piège ni saut d'ordre
- [ ] En thème clair comme en thème sombre, aucun texte d'étape ne descend sous le contraste lisible
