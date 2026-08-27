---
chantier: UX-6
statut: à venir
---

# UX-6 — écran « par où commencer » et guide utilisateur

**Point de départ** — le dépôt n'a aucune porte d'entrée : `/` ouvre directement la
Visionneuse en mode Navigation, sur un corpus qui peut être vide, sans rien dire de la
chaîne qui y mène. Et `docs/` ne contient que des notes de *conception*, une roadmap et
un renvoi de backlog — aucun mode d'emploi. Rien n'est commencé.

## Reste

### Arbitrages
- [ ] La liste des étapes et leur ordre sont figés AVANT la première ligne de code, chaque étape nommant une surface et un geste : c'est le contrat commun de l'écran et du guide, et le laisser flotter ferait diverger les deux
- [ ] Le rang vis-à-vis de UX-3 est tranché et écrit dans les deux fiches : UX-3 veut rendre les quatre modes de la Visionneuse compréhensibles *sans* documentation, UX-6 les explique — décider lequel passe d'abord, ou acter qu'ils sont indépendants

### Écran « par où commencer »
- [ ] L'écran s'ouvre au premier chargement d'une des quatre surfaces et une seule fois : après fermeture, un rechargement ne le rouvre pas (état en `localStorage`, clé préfixée `bd-` comme celles de `static/theme.js`)
- [ ] Il porte une case « ne plus afficher » distincte de la fermeture : sortir par Échap ou par la croix ne vaut pas renoncement définitif
- [ ] Il est rappelable à tout moment depuis la nav transverse, sur les quatre surfaces — donc injecté par `static/theme.js`, pas recopié dans quatre gabarits
- [ ] Chaque étape mène en un clic à la surface ET à l'outil qu'elle décrit (deep-link, cf. `docs/navigation-round-trip.md`), pas seulement à la page d'accueil de cette surface
- [ ] L'écran est bâti sur `static/lib/dialog.js` — piège à focus, Échap, retour du focus au déclencheur — sans modale réécrite pour l'occasion
- [ ] L'écran dit ce que l'outil ne fait PAS : les trois passes ML ne font que pré-remplir, l'annotation reste entièrement humaine ; une carte muette là-dessus laisserait croire à une chaîne automatique
- [ ] Une étape dont le moteur est absent (`GET /api/sante` la donne indisponible) se présente comme optionnelle et non comme cassée

### Guide utilisateur
- [ ] `docs/guide-utilisateur.md` existe et couvre les étapes retenues et les quatre surfaces du point de vue de la tâche — « transcrire une bulle », « corriger un lemme » — jamais de l'architecture
- [ ] Chaque étape de l'écran renvoie à une section du guide qui existe : aucune ancre morte, vérifié en fin de chantier
- [ ] Le guide traite le cas des moteurs optionnels absents (503 sur la route, mention dans `/api/sante`) au lieu de supposer l'installation complète
- [ ] `README.md` et la section « Vue d'ensemble » de `CLAUDE.md` nomment le guide comme la documentation d'usage du dépôt, distincte des notes de conception
- [ ] Une note de conception courte justifie le parcours retenu, les étapes écartées et le refus de la visite guidée surlignée

### Vérifications
- [ ] `pytest -m e2e` reste sans violation axe sérieuse ou critique sur les quatre surfaces × deux thèmes, **écran ouvert** : l'audit actuel ne voit jamais de modale au chargement
- [ ] La suite E2E existante passe sans qu'aucun test n'ait été réécrit pour contourner l'écran : le harnais le neutralise explicitement, en un seul endroit
- [ ] Aucun petit texte coloré de l'écran n'utilise un accent brut : tokens d'encre AA-sûrs, règle d'accessibilité de `CLAUDE.md`
- [ ] Sur 375 px de large, la carte des étapes reste lisible et la fermeture atteignable sans défilement horizontal

## Contexte

Forme retenue le 2026-08-27 : un **écran « par où commencer »** — une carte des étapes,
chacune renvoyant par deep-link à sa surface et à son outil. Pas de visite guidée
surlignant les vrais éléments : elle se couple au DOM des quatre surfaces, or UX-3
(hiérarchie des actions) et UX-4 (cohérence inter-surfaces) sont ouverts et vont
précisément déplacer ces éléments. Une visite écrite maintenant serait à réécrire deux
fois. L'assistant de mise en route — celui qui *fait* les gestes du premier corpus — a
été écarté pour une autre raison : il dupliquerait la Bibliothèque, qui porte déjà la
création d'album, l'import de planches et le lancement des lots.

Déclenchement retenu : **premier chargement, persisté dans le navigateur**. La variante
« tant que le corpus est vide » avait un avantage réel — un fait objectif, lu en base,
rien à désynchroniser — mais elle rate le cas dominant ici : un corpus déjà rempli par
quelqu'un d'autre, ouvert par une personne qui n'a jamais vu l'outil. Le prix est connu
et accepté : un autre profil de navigateur revoit l'écran.

Le chantier a une **dette d'infrastructure de test** qui n'est pas anecdotique. La
fixture `page` de pytest-playwright ouvre un contexte neuf par test, donc un
`localStorage` vide : sans précaution, l'écran s'affiche devant *chaque* test E2E et
intercepte le premier clic. `tests/test_e2e_navigation.py` et `tests/test_e2e_a11y.py`
enchaînent `page.goto(...)` puis cliquent immédiatement — ils tomberaient tous ensemble.
D'où la case qui exige un seul point de neutralisation : la tentation, face à trente
tests rouges, est d'ajouter trente fermetures.

La **documentation est la moitié du chantier, pas son appendice** : `docs/` documente
depuis le début les décisions de conception, jamais l'usage. L'écran d'accueil sans
guide derrière lui ne serait qu'un sommaire pointant vers des pages qui n'expliquent
rien ; le guide sans écran resterait invisible. Les deux se tiennent, et la case des
ancres mortes est là pour que le lien entre eux soit vérifié plutôt que supposé.

Rangé **C6** dans la piste C de `docs/roadmap.md`, P2·M, **déclenché par C1** — la même
bascule que C5 : en mono-poste, l'outil s'apprend en le construisant, et la question ne
se pose pas. Déployé, il s'ouvre devant quelqu'un qui n'a jamais vu la chaîne.

Reste hors périmètre, faute d'être tranché : une aide contextuelle par surface (un « ? »
qui ouvre la section correspondante du guide). C'est un second chantier, à ouvrir une
fois le guide écrit et ses sections stabilisées.
