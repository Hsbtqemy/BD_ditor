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

## Qui peut le lire, et ce qui en sort (AUTH-1, 2026-08-31)

C'est le **seul rapport d'analyse réservé**, et pour une raison qui lui est propre : les
autres portent sur le CORPUS, celui-ci porte sur des **personnes**. Il nomme (`auteurs`),
il apparie (le taux d'accord de deux gens précis) et il cite à la ligne près
(« en pl·3·c2·b1, alice avait NOUN, bob a mis VERB »). Son voisin `GET /api/analyse/accord`
(NLP-1) reste ouvert en lecture : `accord.py` n'a ni `agent` ni `auteur`, il ne nomme
personne.

**Dans l'application — réservé à qui ÉCRIT.** `GET /api/analyse/accord-inter` répond **403**
à qui n'écrit nulle part, et son périmètre suit les albums où l'on écrit, non ceux qu'on
lit. La règle tient en une phrase : *ceux qui voient la mesure sont ceux qu'elle mesure*.
Les propriétaires cumulant l'écriture, ils gardent leur rôle d'arbitre ; un lecteur seul —
un étudiant, un partenaire, un relecteur externe — n'obtient plus le relevé nominatif des
erreurs de gens qui n'ont pas choisi d'être mesurés par lui. Le bouton **👥 Inter** reste
VISIBLE et le panneau affiche le refus du serveur : cacher le bouton priverait la personne
de la raison, ce qui rendrait le silence qu'AUTH-2 combat.

**Au dépôt — les taux, jamais les noms.** Le bloc `qualite.accord_inter` de la fiche
(`description_collection.py`) est déclaré `ouvert` et part à l'entrepôt. Il porte désormais
`nb_auteurs` (un compte) et des `paires` **sans identités**, triées par taux — triées par
`(a, b)`, l'ordre alphabétique des logins transparaissait encore à travers des noms
retirés. La valeur FAIR revendiquée est intacte : « ce corpus a été relu à plusieurs,
accord 0,87 » se dit entièrement sans nommer qui a corrigé qui. Le reste n'était pas de la
paradonnée sur le corpus mais de la donnée sur des personnes, publiée **définitivement** —
un entrepôt garde ses versions, et un désaccord d'un jour ne se retire plus. Trois chemins
étaient concernés, pas deux : le JSON, les CSV, et **l'onglet XLSX**, que l'inventaire des
voies de sortie n'avait pas cité.

**L'outil en ligne de commande, lui, NOMME toujours** (`tools/rapport_accord_inter.py`) :
c'est l'instrument d'arbitrage de l'équipe, il suppose un accès shell, et il ne quitte pas
la machine. Sans les noms il ne servirait à rien — on ne peut pas réunir deux personnes
pour trancher un désaccord si l'on ignore lesquelles.

> **Ce que cela ne referme pas.** `metadonnees_collection.py` déverse le journal A3 entier
> en `evenement.csv` / `activite.csv`, colonne `agent` comprise. C'est une voie de sortie
> distincte, plus large, et une case ouverte d'AUTH-1.

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
