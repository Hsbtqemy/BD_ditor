---
chantier: DEPOT-1
statut: différé
---

# DEPOT-1 — établir la base légale, prérequis hors code du dépôt

**Point de départ** — mis en attente exprès : c'est une démarche institutionnelle et
juridique, pas du code. Rien n'a été engagé sur le fond. Fiche ouverte le 2026-08-27 en
montant le journal, parce que ce prérequis ne vivait que dans `docs/`.

**Relue le 2026-08-28, après DROIT-1**, qui a tranché deux de ses cases sans qu'elle le
sache : la surcharge par album est ABANDONNÉE, et le tiering annoncé a été RÉVISÉ — il ne
porte plus sur la nature de la donnée mais sur DEDANS / DEHORS. La fiche disait aussi ne
demander « aucun développement », ce qui reposait sur une doctrine depuis précisée.

**Le dossier à porter est écrit** (`docs/dossier-base-legale.md`, 2026-08-28) : ce que
l'outil détient, ce qui peut en sortir et par quel geste, ce que le code borde déjà, et
huit questions ordonnées. La démarche peut partir avec ses pièces au lieu de partir à
blanc. Le statut reste `différé` : la réponse ne dépend pas du dépôt.

## Reste

### Le dossier à porter
- [x] Le dossier est rédigé (`docs/dossier-base-legale.md`) et se tient sans l'outil : il s'adresse à qui ne le connaît pas. Il ne conclut rien — l'exception de fouille (2019/790 art. 3) y est nommée comme piste à vérifier, jamais comme réponse, parce que la prudence qu'on s'impose dans le code vaut aussi dans la prose
- [x] Il énonce le fait qui doit être dit noir sur blanc à qui tranchera : **les trois exports par album (JSON-LD, CSV, TEI) emportent le texte OCR verbatim**, et ne sont bornés que par l'admission — pas par le régime de diffusion. Toute personne admise sur une collection peut en extraire images et texte intégral. C'est l'arbitrage assumé du 2026-08-28, pas un oubli, mais il se décide en connaissance de cause
- [x] ~~Un champ de provenance par album~~ — **NON RETENU comme obligatoire le 2026-08-28**. `collection.base_legale` reste le véhicule ; `albums.provenance` demeure une entrée de métadonnées possible et intéressante, non requise. À rouvrir si la réponse à la question 2 du dossier (d'où viennent les exemplaires) impose la granularité par œuvre — cas d'un corpus mêlant exemplaires acquis, prêts et numérisations de partenaires

### Établir
- [ ] L'institution porteuse du corpus est identifiée et a été saisie de la question
- [ ] La source des scans est établie et documentée : d'où viennent les masters, sous quel régime ils ont été produits
- [ ] La `base_legale` est arrêtée par écrit, avec sa justification — l'exception TDM est une piste, pas une conclusion
- [ ] Le `statut_diffusion` par défaut de la collection est arrêté (ouvert, embargo, restreint)
- [x] ~~Le principe de surcharge par album est confirmé ou écarté~~ — **ÉCARTÉ le 2026-08-28** (DROIT-1). La raison n'est plus celle qui se discutait ici : depuis AUTH-3 un album vit dans PLUSIEURS collections, si bien qu'« un défaut Collection surchargeable par Album » n'a plus de défaut unique à surcharger. Le besoin réel — un corpus mêlant domaine public et œuvres sous droits — se traite en constituant deux collections

### Renseigner
- [ ] `collection.base_legale` et `collection.statut_diffusion` sont renseignés dans la base pour la collection de référence, et ressortent dans la fiche de description et le crosswalk
- [x] ~~Le tiering annoncé (enrichissement ouvert, scans et OCR verbatim restreints) est cohérent avec la base légale retenue, ou bien il est révisé~~ — **RÉVISÉ le 2026-08-28** (DROIT-1), et pas dans le sens attendu. L'axe n'est plus la NATURE de la donnée mais DEDANS / DEHORS : à l'intérieur de l'instance le régime ne borde rien (l'annotation repose sur les images), il n'est opposable qu'à la sortie, où il sépare PUBLIER de CITER. Border un membre reviendrait à l'empêcher de travailler
- [ ] Reste de cette case, et elle ne se referme pas sans la base légale : vérifier que ce partage PUBLIER / CITER tient face au régime retenu. Citer relève du droit de citation, publier non — si la base légale s'avère plus étroite qu'espéré, c'est la branche PUBLIER qui se restreint, pas le code qui change

## Contexte

**C'est le seul point qui empêche réellement de déposer**, et il n'était dans aucun
ticket : ni backlog, ni audit, ni roadmap en tant qu'item — seulement en note dans
`docs/dictionnaire-metadonnees.md:117` et `docs/roadmap.md:70`.

Toute la piste A (A1 à A6, schémas v15 à v19) a été construite pour rendre une collection
déposable sur Nakala ou HAL. Les champs existent, les crosswalks Dublin Core et DataCite
sortent, le manifeste IIIF est conforme, la provenance est sérialisable en PROV-O. Rien
de tout cela ne se dépose tant que la base légale n'est pas établie.

La doctrine du dépôt était **« décrire, pas imposer »** (décision du 2026-07-16) : ces
champs déclarent un régime, ils ne l'appliquent pas. Elle a été **précisée le 2026-08-28**
(DROIT-1) et non renversée : la déclaration mord désormais **là où la donnée quitte
l'outil**, et nulle part ailleurs. Le manifeste IIIF n'emporte d'images que d'une
collection déclarée `public` et nommée ; la date d'embargo retient sans jamais promouvoir.

Cette fiche ne demande toujours aucun développement **sur le fond** — on ne code pas une
politique qu'on ne connaît pas, et c'est exactement pourquoi elle risquait de rester
invisible indéfiniment. Mais le mécanisme, lui, est désormais ENTIER : le jour où la base
légale est arrêtée, la renseigner est une ligne de CLI, et tout ce qui sort de l'outil la
porte — la figure citable la première, qui écrit aujourd'hui « base légale non établie »
plutôt que de laisser un blanc.

`différé` et non `à venir` : la démarche dépend d'interlocuteurs extérieurs au dépôt.
Elle n'a pas de dépendance technique, et peut donc être ouverte en parallèle de
n'importe quoi d'autre — y compris tout de suite, comme ANN-1.
