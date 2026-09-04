---
passe: Défilement de l'Exploration
chantier: UX-7
duree: 6 min
derniere: 2026-09-04
---

# QA — l'Exploration défile, et rien ne s'est déplacé au passage

`#explo-app` n'avait ni hauteur ni cadre de défilement, là où `#search-app` et
`#corpus-app` en ont un depuis toujours. Avec `html, body { overflow: hidden }` — dont la
Visionneuse a besoin, sa coque pleine hauteur distribuant le défilement entre ses bandes —
tout ce qui dépassait la fenêtre était donc **coupé** : 1 285 px de contenu inatteignables
sur un écran de 1080, sans barre de défilement et sans que la molette n'y puisse rien.

Deux tests E2E gardent désormais la propriété : le cadre existe, et le bas s'atteint. Ce
qu'ils **ne** voient pas, c'est ce que le passage d'un contenu libre à un contenu encadré
déplace à l'œil. Trois choses en particulier.

**Les bandes collantes du tableau de croisement — et une correction de cette passe.**
La version du 2026-09-04 affirmait ici que l'en-tête de colonnes « venait de s'activer »
grâce au nouveau cadre. **C'était faux, et la case correspondante a été validée sur cette
affirmation** : elle est donc décochée, non pas parce que la réponse était mauvaise, mais
parce que la question l'était.

Mesuré depuis : `.croise` porte `overflow-x: auto`, ce qui en fait le conteneur de
défilement le plus proche pour les **deux** axes — c'est lui l'ancêtre du collage, pas le
cadre de page. Il a la hauteur de son contenu et ne défile jamais verticalement, si bien
que `thead th { top: 0 }` n'a rien à quoi se caler : le collage **vertical est inerte**,
avant comme après. Sur 60 lignes, l'en-tête sort par le haut à y=-1121. Il reste visible
avec le corpus de démonstration pour une tout autre raison : ses dix lignes tiennent dans
la fenêtre.

Le collage **horizontal**, lui, fonctionne — et c'est celui que les 20 colonnes réclament.
C'est là que la passe a trouvé un vrai défaut : le COIN du tableau, qui porte le libellé
des deux axes, était recouvert par les en-têtes de colonnes dès qu'on défilait vers la
droite (`z-index` déclaré 3, reçu 2). Corrigé et gardé par un test E2E.

**La barre d'outils de la page** (`#header`, bande 2) devient `flex: 0 0 auto` : elle
devrait rester fixe pendant que le contenu défile, comme sur la Recherche et la
Bibliothèque. C'est l'attendu ; il se constate.

**Les modales** (Lexique, Accord, Inter) sont en `position: fixed` et ne devraient RIEN
devoir à la position de défilement. C'est vérifié par lecture du CSS, pas à l'écran — la
case ci-dessous est là pour démentir la lecture, si elle a tort.

**Comment jouer la passe.** Une instance de démonstration suffit et vaut mieux qu'un vrai
corpus — elle est jetable :

    BD_DATA_DIR=/tmp/demo BD_DB_PATH=/tmp/demo/demo.sqlite python tools/semer_demo.py
    BD_DATA_DIR=/tmp/demo BD_DB_PATH=/tmp/demo/demo.sqlite python -m uvicorn main:app --port 8011

Ce corpus donne un tableau de croisement de **10 lignes sur 20 colonnes**
(`?vue=croisement`, axes *POS × morphologie*) — assez large pour déborder
horizontalement, **pas assez haut** pour déborder verticalement dans une fenêtre normale.
Les cases sur l'en-tête collant demandent donc de RÉTRÉCIR la fenêtre en hauteur (environ
500 px) : c'est le geste qui met le tableau en situation, et il vaut mieux que d'attendre
un corpus assez gros pour le faire tout seul.

À rejouer si `#explo-app`, `#explo-body` ou la coque pleine hauteur changent.

### Le cadre défile

- [x] Sur `/exploration`, en vue *distribution* (le corpus de démonstration y produit environ 2 300 px de contenu), la molette fait défiler le contenu — et une barre de défilement apparaît à droite du contenu, pas au bord de la fenêtre
- [x] La bande de navigation du site (BéDéditeur · Atelier ‖ Analyse) et la barre d'outils de la page restent IMMOBILES pendant ce défilement
- [x] Le tout dernier élément de la liste est lisible en entier une fois défilé jusqu'en bas — pas coupé par le bord de la fenêtre

### Le collage horizontal du croisement — le seul qui agisse

- [x] La première colonne (`th[scope="row"]`, collante à gauche) reste lisible quand on défile le tableau vers la droite — les 20 colonnes du croisement POS × morphologie le forcent sans rétrécir quoi que ce soit
- [x] Le COIN du tableau (« catégorie (POS) \ morphologie ») reste LISIBLE pendant ce même défilement, et n'est pas recouvert par les en-têtes de colonnes qui passent dessous
- [x] La barre de défilement horizontale appartient au tableau et non à la page : c'est le cadre du croisement qui défile, la barre d'outils et la navigation ne bougent pas

### Ce que cette passe NE vérifie pas, et pourquoi

Le collage **vertical** des en-têtes de colonnes : il ne fonctionne pas, c'est mesuré, et
c'est un constat ouvert d'UX-7 — le réparer demande d'arbitrer un cadre de défilement
imbriqué dans celui de la page. Inutile d'écrire une case pour une propriété qu'on sait
absente ; elle reviendra ici le jour où l'arbitrage sera rendu.

### Ce qui ne doit pas avoir bougé

- [x] Les trois panneaux 📖 Lexique, 🎯 Accord et 👥 Inter s'ouvrent CENTRÉS dans la fenêtre, que la page soit défilée en haut ou en bas
- [x] Le contenu de l'Exploration reste centré horizontalement et garde sa largeur maximale : il ne s'étale pas sur toute la largeur d'un écran large
- [x] Les quatre vues (distribution, concordance, croisement, comparaison) s'affichent entièrement, sans zone vide en bas ni contenu tronqué
- [x] Les deux thèmes (sombre et clair) : la barre de défilement du cadre reste lisible sur le fond du panneau, et ne masque pas de texte
