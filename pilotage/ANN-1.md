---
chantier: ANN-1
statut: interrompu
---

# ANN-1 — peupler le vocabulaire d'étude avec les linguistes

**Arrêté sur** — 2026-09-08, `48a40a2` : le matériel de la séance est prêt (proposition de
vocabulaire, arbitrage d'import, cliquet de complétude). Rien n'est importé, aucune case
n'est cochée — la séance n'a pas eu lieu, et c'est elle qui coche.

## Reste

### Décision d'équipe
- [ ] Une séance avec les linguistes a fixé la liste des domaines d'étude ouverts (au moins « émotions » et « représentation »), en PARTANT de `tools/vocabulaire-etude-propose.csv` — l'élaguer, l'augmenter ou le récuser, mais ne pas repartir de la page blanche
- [ ] Chaque dimension retenue porte une `definition` ET une `note_portee` non vides — c'est le « situé » du lexique, et sans lui l'export SKOS sort creux ; le cliquet du 2026-09-08 ne vérifie QUE le CSV, rien ne tient cet invariant en base
- [ ] L'arbitrage écrit le 2026-09-08 dans `docs/import-vocabulaire.md` (amorcer par le tableur, finir dans l'app, amender AVANT le premier import) est accepté en séance — ou récusé, la note disant alors pourquoi
- [ ] Chaque dimension déclare dans sa `note_portee` si elle est MONO- ou MULTI-valuée : `personnage_attribut` et `region_attribut` sont N-N tous les deux et n'en refuseront aucune, donc la note est le SEUL endroit où cette règle existe
- [ ] La portée du vocabulaire est tranchée — global (`collection_id` NULL) ou local à une collection ; elle ne se pose qu'à la CRÉATION du terme, et un réimport ailleurs ne déménage rien

### Peuplement
- [ ] Le CSV amendé est importé APRÈS la séance, et `GET /api/lexique` renvoie un « % défini » supérieur à 0 — ce qui demande de cocher « défini » dans le panneau 📖 Lexique, l'import laissant tout `provisoire` exprès
- [ ] Une planche réelle est annotée de bout en bout avec ce vocabulaire, sans qu'aucun terme manquant n'ait dû être inventé en cours de route
- [ ] La vue Croisement de l'Exploration affiche un axe `dim:<id>` peuplé et non vide — donc en codant des cases QUI ONT du texte : le croisement compte des TOKENS, et 27 des 45 cases du corpus local sont muettes
- [ ] Si un axe `cible=personnage` doit servir (genre, âge, origine perçue, rôle actanciel), des LOCUTEURS sont posés : le croisement joint ces axes par `bulle_locuteur`, une simple présence (`personnage_presence`) n'y suffit pas, et le corpus local compte 0 personnage

## Contexte

C'est **la finalité du projet**, et la seule fiche P1 qui ne dépende d'aucun code : tout
le socle technique existe. Le blocage historique — « liste fermée vs vocabulaire
émergent » — n'existe plus : B0 (v20) a rendu l'ajout de domaine gratuit, et A4 (v17) a
donné à chaque terme sa définition et sa note de portée.

Ce qui reste est une décision d'équipe, pas une décision de conception. La roadmap
(`docs/roadmap.md`, piste B1) recommande de l'ouvrir tôt et en parallèle du reste,
précisément parce qu'elle exige une discussion humaine en amont et que rien ne la
débloque côté code.

**Ce qui est prêt** (2026-09-08) — `tools/vocabulaire-etude-propose.csv` : deux domaines,
neuf axes, quarante et une valeurs, importable tel quel (éprouvé sur base jetable : aucune
anomalie, idempotent au rejeu). Ce n'est **pas** un vocabulaire décidé, et il ne prétend pas
l'être : c'est de quoi ne pas ouvrir la séance sur une page blanche, fait pour être élagué
autant qu'augmenté.

### Une correction, d'abord

Cette fiche annonçait un « piège documenté dans `docs/lexique-situe.md` : un terme créé sans
`note_portee` reste `provisoire` ». **C'est faux, deux fois.** Ce n'est écrit nulle part dans
ce document, et le code dit le contraire : `etat` est une case à cocher LIBRE
(`static/exploration.js`), validée contre deux valeurs et rien d'autre (`socle.py`,
`_ETATS_LEXIQUE`), sans le moindre lien avec `note_portee`.

Le vrai danger est le **symétrique**, et il est pire : rien n'empêche de cocher « défini »
sur un terme dont la note de portée est vide. Le « % défini » de `GET /api/lexique`
afficherait alors 100 % pendant que l'export SKOS sort creux — un indicateur qui rassure en
ne mesurant pas ce qu'on croit qu'il mesure. Le cliquet posé le 2026-09-08 ne ferme pas cet
angle : il ne regarde que le CSV, avant qu'il n'entre en base.

### Ce que la séance doit savoir avant de choisir ses axes

**Une émotion ne peut pas se coder sur le personnage.** `personnage_attribut` attache une
valeur à l'ENTITÉ, donc pour tout le corpus — le schéma le dit (« profil sociolinguistique
du locuteur ») et la conception aussi (`docs/personnages-et-attribution.md` §13.1 : le
personnage porte le PROFIL, la case porte la SITUATION). Une colère posée sur un personnage
le rendrait en colère de la première à la dernière planche. D'où le partage de la
proposition — émotions sur la CASE, traits stables (genre, âge, origine perçue, rôle) sur le
PERSONNAGE — et ce partage est le seul point de la proposition qui ne soit pas négociable :
il est imposé par le modèle, pas par un goût.

**Il n'existe aucun ancrage « ce personnage-ci, dans cette case-ci ».** C'est la limite
réelle du modèle pour une étude d'émotions, et aucun choix de vocabulaire ne la contourne :
une case codée « colère » où trois personnages figurent ne dit pas QUI est en colère. Le seul
contournement disponible est le croisement *profil du locuteur × situation de la case* — la
requête-thèse de §13.1 — qui ne vaut que pour les personnages qui PARLENT. À décider en
séance : est-ce que l'étude s'en accommode, ou faut-il ouvrir un chantier de modèle ?

**Et le Croisement compte des TOKENS.** Mesuré le 2026-09-08 sur le corpus local : **27 des
45 cases n'ont aucun token**, soit 60 %. Une émotion codée sur une case muette est
parfaitement enregistrée, parfaitement exportée, et **invisible dans la vue Croisement** —
qui part de `tokens_effectifs` et rejoint la case par `region_attribut ... IN (r.id,
r.parent_id)`. Pour une étude d'émotions en bande dessinée, où la case sans texte est un lieu
d'affect majeur, c'est un angle mort à connaître avant de bâtir un protocole de codage
dessus, pas après. Même mécanique côté personnage : ces axes-là passent par
`bulle_locuteur`, donc un personnage montré mais muet ne pèse rien, et le corpus local compte
0 personnage, 0 locuteur, 0 présence.

**Enfin, le tableur n'amende pas ce qu'il a créé.** Mesuré le même jour, et silencieux : une
glose corrigée dans le CSV puis rejouée ne remplace pas celle qui est en base, le bilan
annonçant « 0 créé, 9 déjà présents ». D'où l'ordre des opérations, écrit dans
`docs/import-vocabulaire.md` : **la séance amende le CSV, ensuite seulement on importe.**
Importer la proposition avant la séance coûterait la reprise à la main de chaque glose
discutée.
