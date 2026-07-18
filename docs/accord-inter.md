# Accord inter-annotateurs (ANN-5)

> **But.** Quand plusieurs linguistes corrigent : mesurer l'accord et repérer les **points de
> divergence** (qualité, arbitrage). Cœur partagé `accord_inter.py`, exposé par la route
> `GET /api/analyse/accord-inter`, l'outil `tools/rapport_accord_inter.py` et le panneau
> **👥 Inter** de l'Exploration (à côté de 🎯 Accord). Dépend d'INFRA-2 (`auteur`).

## Contrainte du modèle → accord de RÉVISION (pas de parallèle)

Le modèle ne garde qu'**une** correction courante par token (avec son `auteur`) — pas
d'annotations parallèles indépendantes. La donnée multi-auteurs vit donc dans le **journal A3**
(`evenement`), où chaque correction de token est un événement (agent + `avant`/`après`) et où
`cible_id` (l'id de la correction) est **stable** (ON CONFLICT DO UPDATE) → une **chaîne de
révisions** par token.

On mesure donc l'**accord de révision** : quand un annotateur **re-touche** le token laissé par
un **autre**, garde-t-il (accord) ou change-t-il (divergence) la valeur, par champ ? L'événement
porte déjà `avant` (valeur du précédent) et `après` (du courant) ; l'agent précédent de la chaîne
donne l'identité. Ce n'est **pas** un kappa d'annotation parallèle — c'est adapté au modèle
« une vérité corrigée dans le temps ».

## Ce que le rapport donne

- **Par champ** (lemme, POS, morpho) : nombre de re-touches inter-auteurs, accords (valeur gardée),
  taux.
- **Par paire d'auteurs** : accord global (aucun champ changé) sur leurs re-touches communes.
- **Points de divergence** : liste `citation · forme [champ] auteurA=x → auteurB=y` (bornée). La
  citation peut être absente si le token_correction a été supprimé (le **journal lui survit**).

> **Rare avant le multi-utilisateur.** Sans auth à plusieurs (piste C), tout est fait par un seul
> agent (ou anonyme) → aucune re-touche inter-auteurs. La **capacité est prête** pour ce moment-là.

## Usage

```bash
python tools/rapport_accord_inter.py                  # rapport lisible (stdout)
python tools/rapport_accord_inter.py --json r.json    # + export JSON complet
python tools/rapport_accord_inter.py --csv r.csv      # + export CSV (accord par champ)
```

Dans l'app : **Exploration → 👥 Inter** (route `GET /api/analyse/accord-inter`) — mêmes chiffres :
re-touches, auteurs, taux par champ (barre), par paire, et divergences.

## Périmètre

- **Couvert** : accord de révision par champ + par paire, divergences citées. Route + CLI +
  panneau, cœur unique testé une fois (`tests/test_accord_inter.py`).
- **Hors périmètre** (différé) : kappa/accord d'annotation **parallèle** (nécessiterait de stocker
  des jugements indépendants — nouveau modèle) ; pondération de désaccord ; accord sur les **tags**
  et attributs (ici : uniquement la grammaire des tokens).
