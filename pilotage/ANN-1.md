---
chantier: ANN-1
statut: à venir
---

# ANN-1 — peupler le vocabulaire d'étude avec les linguistes

**Point de départ** — la structure est complète et livrée (domaines B0/v20, lexique SKOS
A4/v17, attributs émergents ANN-2/v11) ; aucun terme d'étude n'y a encore été versé.

## Reste

### Décision d'équipe
- [ ] Une séance avec les linguistes a fixé la liste des domaines d'étude ouverts (au moins « émotions » et « représentation »), chacun créé dans le panneau 📖 Lexique
- [ ] Chaque dimension créée porte une `definition` ET une `note_portee` non vides — c'est le « situé » du lexique, et sans lui l'export SKOS sort creux
- [ ] Le choix entre saisie à la main et amorçage CSV (`tools/importer_vocabulaire.py`) est tranché et écrit dans `docs/import-vocabulaire.md`

### Peuplement
- [ ] Le domaine « émotions » a ses dimensions et valeurs peuplées, et `GET /api/lexique` renvoie un « % défini » supérieur à 0
- [ ] Une planche réelle est annotée de bout en bout avec ce vocabulaire, sans qu'aucun terme manquant n'ait dû être inventé en cours de route
- [ ] La vue Croisement de l'Exploration affiche un axe `dim:<id>` peuplé et non vide

## Contexte

C'est **la finalité du projet**, et la seule fiche P1 qui ne dépende d'aucun code : tout
le socle technique existe. Le blocage historique — « liste fermée vs vocabulaire
émergent » — n'existe plus : B0 (v20) a rendu l'ajout de domaine gratuit, et A4 (v17) a
donné à chaque terme sa définition et sa note de portée.

Ce qui reste est une décision d'équipe, pas une décision de conception. La roadmap
(`docs/roadmap.md`, piste B1) recommande de l'ouvrir tôt et en parallèle du reste,
précisément parce qu'elle exige une discussion humaine en amont et que rien ne la
débloque côté code.

Attention au piège documenté dans `docs/lexique-situe.md` : un terme créé sans
`note_portee` reste `provisoire`, et un corpus entier annoté avec des termes provisoires
n'est pas déposable en l'état.
