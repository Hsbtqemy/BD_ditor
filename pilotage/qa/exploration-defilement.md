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

**L'en-tête collant du tableau de croisement.** `.croise-table thead th` porte
`position: sticky; top: 0` depuis toujours — mais un élément collant se cale sur son
ancêtre DÉFILANT le plus proche, et il n'y en avait aucun. La règle était donc inerte.
Elle vient de s'activer, sans que personne l'ait demandé : c'est le genre de changement
qui n'apparaît dans aucun diff.

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

- [ ] Sur `/exploration`, en vue *distribution* (le corpus de démonstration y produit environ 2 300 px de contenu), la molette fait défiler le contenu — et une barre de défilement apparaît à droite du contenu, pas au bord de la fenêtre
- [ ] La bande de navigation du site (BéDéditeur · Atelier ‖ Analyse) et la barre d'outils de la page restent IMMOBILES pendant ce défilement
- [ ] Le tout dernier élément de la liste est lisible en entier une fois défilé jusqu'en bas — pas coupé par le bord de la fenêtre

### L'en-tête collant du croisement, qui vient de s'activer

- [ ] En vue *croisement* (axes POS × morphologie), fenêtre rétrécie à ~500 px de haut : les en-têtes de colonnes restent visibles pendant qu'on défile vers le bas
- [ ] Ils se calent SOUS la barre d'outils de la page et non par-dessus : aucun texte n'est masqué par un autre
- [ ] La première colonne (`th[scope="row"]`, elle aussi collante) reste lisible quand on défile le tableau horizontalement — les 20 colonnes du croisement POS × morphologie le forcent sans rétrécir quoi que ce soit

### Ce qui ne doit pas avoir bougé

- [ ] Les trois panneaux 📖 Lexique, 🎯 Accord et 👥 Inter s'ouvrent CENTRÉS dans la fenêtre, que la page soit défilée en haut ou en bas
- [ ] Le contenu de l'Exploration reste centré horizontalement et garde sa largeur maximale : il ne s'étale pas sur toute la largeur d'un écran large
- [ ] Les quatre vues (distribution, concordance, croisement, comparaison) s'affichent entièrement, sans zone vide en bas ni contenu tronqué
- [ ] Les deux thèmes (sombre et clair) : la barre de défilement du cadre reste lisible sur le fond du panneau, et ne masque pas de texte
