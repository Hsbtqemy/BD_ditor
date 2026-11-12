---
chantier: QA-7
statut: à venir
---

# QA-7 — la passe navigateur dans l'image prend plus de trois heures

**Point de départ** — 2026-11-12 : la fusion vers `main` de `22580fc` est partie sans sa
passe navigateur entière dans l'image, coupée vers 22 % par l'arrêt du poste. La suite
ordinaire y était verte, et les deux passes de QA du lot jouées en entier (Hugo, le même
jour : « il faudrait que ce soit push cet après-midi »).

## Reste

### La passe de la fusion du 2026-11-12
- [ ] **Les tests navigateur de `22580fc`, rejoués entiers dans l'image** — attendu : `docker run --rm bdediteur:e2e-22580fc` sur le poste (l'image est déjà construite, rien à refaire) rend 1 286 tests et 0 échec. Coupée le 2026-11-12 vers 22 % (environ 280 tests verts, aucun échec) ; le commit est en production depuis le même jour. Un échec se règle par un correctif sur `dev`, pas par un retour en arrière : les migrations de schéma sont à sens unique

### Faire tenir la passe en une heure
- [ ] **La passe navigateur dans l'image se répartit sur plusieurs processus** — attendu : `docker run --rm bdediteur:e2e` joue les tests navigateur sur au moins quatre processus (`pytest-xdist`, ajouté au verrou de test), en une heure au plus sur le poste, avec le même nombre de tests et 0 échec. Mesuré le 2026-11-12 : 1 286 tests joués un par un, environ 9 secondes chacun, un seul Chromium, alors que Docker dispose de 8 processeurs. À vérifier d'abord : le serveur de test et sa base sont partagés par toute la session, et plusieurs tests règlent la fenêtre ou la police
- [ ] **CLAUDE.md dit les comptes et la durée d'aujourd'hui** — attendu : § Tests, les comptes mesurés le 2026-11-12 par `--collect-only` (suite par défaut 3 554, `not live` 4 839, `not e2e and not live` 3 553, e2e 1 286) à la place de ceux du 2026-09-07, et la durée réelle de la passe navigateur dans l'image à la place de « 184 tests, ~23 min »

## Contexte

En septembre, la passe navigateur dans l'image comptait 184 tests et prenait 23 minutes.
Le 2026-11-12, elle en compte 1 286, soit sept fois plus. Les plus gros fichiers sont ceux
des chantiers récents : la page Annotation (198), l'accessibilité (109), les projets (83), le
zoom de l'interface (70). Le coût d'un test n'a guère changé, autour de 9 secondes : la durée
a grandi avec le nombre.

La règle des passes longues (une passe navigateur entière par lot, avant la fusion vers
`main`) tient tant que la passe tient dans un après-midi. À trois heures et vingt minutes,
elle ne tient plus, et c'est ainsi que cette fusion est partie sans elle.
