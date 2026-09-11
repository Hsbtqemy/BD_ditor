---
chantier: UX-8
statut: à venir
---

# UX-8 — annoter au doigt, pas seulement consulter

**Point de départ** — 2026-09-05. Décision prise en tranchant la deuxième case d'UX-7 :
la Visionneuse n'est pas une surface de consultation qu'on rendrait lisible faute de
mieux, c'est l'écran de travail, et il doit rester un écran de travail au doigt.

**Dépendait d'UX-7, et le verrou est LEVÉ** — UX-7 est `livré` depuis le 2026-09-05,
19 cases sur 19. Les tiroirs y sont restés, parce qu'ils relèvent du 1.4.10 et qu'ils
servent aussi bien le téléphone que la tablette : sans eux, il n'y a pas de canevas à
toucher — 540 px de chrome fixe sur une tablette de 768 en laissent 228.

**Ce chantier est donc démarrable, et cette page a annoncé le contraire pendant trois
jours** (relevé le 2026-09-08). C'est le mode d'échec le plus coûteux d'une dépendance
écrite : elle ne fait rien échouer, elle fait seulement qu'on ne choisit pas le chantier.
Un blocage périmé se lit exactement comme un blocage réel.

## Reste

### Les cibles
- [ ] Toute cible interactive de la Visionneuse fait au moins **44 × 44 px** (WCAG 2.5.5) sous le seuil tactile — mesuré élément par élément et non déclaré, comme l'a été le reflow
- [ ] Les poignées de redimensionnement des régions restent saisissables au doigt : elles font aujourd'hui quelques pixels, ce qui est un geste de souris et rien d'autre
- [ ] Deux cibles voisines ne se chevauchent pas une fois agrandies — c'est le mode d'échec du 2.5.5 qu'on obtient en agrandissant sans réespacer

### La gestuelle
- [ ] Le canevas accepte le **pincement** pour zoomer et le glissement à deux doigts pour déplacer, sans entrer en conflit avec le tracé d'une région à un doigt
- [ ] Le tracé d'une région au doigt produit le même rectangle qu'à la souris, aux mêmes coordonnées MASTER — la conversion `web_scale` ne connaît pas le type de pointeur, et c'est ce qu'il faut vérifier
- [ ] Le geste de zoom du navigateur n'est PAS désactivé : `user-scalable=no` réglerait le conflit en violant le 1.4.4

### Ce qu'on ne sait pas encore
- [ ] Les écouteurs de tracé de l'Atelier passent aux `PointerEvent`, puis sont relus sous l'angle tactile. **Le code n'en écoute AUCUN aujourd'hui** : le tracé tient sur `mousedown` (la scène), `mousemove` et `mouseup` (la fenêtre), dans `static/viewer.js` — relevé le 2026-09-11, alors que cette case parlait d'un « `pointerdown`/`pointermove` existant ». Le chantier commence donc par un PORTAGE, pas par une relecture. `PointerEvent` unifie souris et doigt — reste à savoir ce qui casse quand deux pointeurs arrivent en même temps
- [ ] La tablette de test est nommée, avec sa taille et son navigateur : « ça marche sur tablette » sans machine désignée est une affirmation invérifiable

## Contexte

**Pourquoi ce n'est pas une lubie de conformité.** Le 2.5.5 est un critère AAA, pas AA :
le dépôt ne le doit pas. C'est l'USAGE qui le demande — annoter une planche assis
ailleurs qu'à un bureau, avec l'album papier à côté, est le geste naturel de ce corpus.
La conformité vient en prime.

**Le risque à surveiller est le conflit de gestes.** Un doigt qui trace une région et un
doigt qui fait défiler la page se ressemblent au premier `pointerdown` ; c'est là que ce
genre de chantier se casse, et pas dans la taille des boutons.

**Recouvrement avec A11Y-2 et UX-7.** A11Y-2 convertit les `px` figés en `rem` (1.4.4,
zoom à 200 %) ; UX-7 traite le reflow à 320 px (1.4.10). Les trois chantiers échouent
souvent pour la même raison — une largeur figée — mais mesurent trois choses distinctes.
Les mener sans savoir qu'ils se touchent est le seul vrai risque.
