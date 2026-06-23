# Dépendances tierces vendues (tests)

## axe.min.js — [axe-core](https://github.com/dequelabs/axe-core)

Moteur d'audit d'accessibilité (WCAG 2.x) injecté dans Chromium par
`tests/test_e2e_a11y.py`. Vendu ici pour que l'audit tourne **hors ligne**, comme
le reste du projet (aucun `npm install`, aucun accès réseau au moment des tests).

- **Version** : axe-core 4.10.2
- **Licence** : Mozilla Public License 2.0 (MPL-2.0) — Deque Systems.
- Si le fichier est absent, `tests/test_e2e_a11y.py` se **skippe proprement**.

### Mettre à jour

```bash
curl -sSL https://cdn.jsdelivr.net/npm/axe-core@<version>/axe.min.js \
  -o tests/js/vendor/axe.min.js
```

puis ajuster le numéro de version ci-dessus.
