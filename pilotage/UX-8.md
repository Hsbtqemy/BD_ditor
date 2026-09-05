---
chantier: UX-8
statut: à venir
---

# UX-8 — annoter au doigt, pas seulement consulter

**Point de départ** — 2026-09-05. Décision prise en tranchant la deuxième case d'UX-7 :
la Visionneuse n'est pas une surface de consultation qu'on rendrait lisible faute de
mieux, c'est l'écran de travail, et il doit rester un écran de travail au doigt.

**Dépend d'UX-7.** Les tiroirs y restent, parce qu'ils relèvent du 1.4.10 et qu'ils
servent aussi bien le téléphone que la tablette. Sans eux, il n'y a pas de canevas à
toucher : 540 px de chrome fixe sur une tablette de 768 en laissent 228.

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
- [ ] Le comportement du `pointerdown`/`pointermove` existant est relu sous l'angle tactile : le code vise la souris, et `PointerEvent` unifie les deux — reste à savoir ce qui casse quand deux pointeurs arrivent en même temps
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
