---
chantier: DEPOT-1
statut: différé
---

# DEPOT-1 — établir la base légale, prérequis hors code du dépôt

**Point de départ** — mis en attente exprès : c'est une démarche institutionnelle et
juridique, pas du code. Rien n'a été engagé. Fiche ouverte le 2026-08-27 en montant le
journal, parce que ce prérequis ne vivait que dans `docs/`.

## Reste

### Établir
- [ ] L'institution porteuse du corpus est identifiée et a été saisie de la question
- [ ] La source des scans est établie et documentée : d'où viennent les masters, sous quel régime ils ont été produits
- [ ] La `base_legale` est arrêtée par écrit, avec sa justification — l'exception TDM est une piste, pas une conclusion
- [ ] Le `statut_diffusion` par défaut de la collection est arrêté (ouvert, embargo, restreint), et le principe de surcharge par album est confirmé ou écarté

### Renseigner
- [ ] `collection.base_legale` et `collection.statut_diffusion` sont renseignés dans la base pour la collection de référence, et ressortent dans la fiche de description et le crosswalk
- [ ] Le tiering annoncé (enrichissement ouvert, scans et OCR verbatim restreints) est cohérent avec la base légale retenue, ou bien il est révisé

## Contexte

**C'est le seul point qui empêche réellement de déposer**, et il n'était dans aucun
ticket : ni backlog, ni audit, ni roadmap en tant qu'item — seulement en note dans
`docs/dictionnaire-metadonnees.md:117` et `docs/roadmap.md:70`.

Toute la piste A (A1 à A6, schémas v15 à v19) a été construite pour rendre une collection
déposable sur Nakala ou HAL. Les champs existent, les crosswalks Dublin Core et DataCite
sortent, le manifeste IIIF est conforme, la provenance est sérialisable en PROV-O. Rien
de tout cela ne se dépose tant que la base légale n'est pas établie.

La doctrine du dépôt est **« décrire, pas imposer »** (décision du 2026-07-16) : ces
champs déclarent un régime, ils ne l'appliquent pas — l'application reste au portail
d'auth et à l'entrepôt. Cette fiche ne demande donc aucun développement, et c'est
exactement pourquoi elle risquait de rester invisible indéfiniment.

`différé` et non `à venir` : la démarche dépend d'interlocuteurs extérieurs au dépôt.
Elle n'a pas de dépendance technique, et peut donc être ouverte en parallèle de
n'importe quoi d'autre — y compris tout de suite, comme ANN-1.
