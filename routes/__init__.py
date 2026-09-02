"""Routeurs par domaine — le découpage de `main.py` (ARCH-1).

Chaque module y expose un `router = APIRouter()` que `main.py` inclut. Les chemins et le
contrat d'API sont inchangés : un routeur inclus apparaît dans `app.routes` exactement
comme une route déclarée sur `app`, ce dont dépendent les trois cliquets du dépôt
(autorisation, sorties d'identité, CSP).

Le socle commun vit dans `socle.py`, à la racine — un module de ROUTES ne l'importe que
dans ce sens : `routes/*` → `socle`, jamais l'inverse, et `socle` n'importe pas `main`.
"""
