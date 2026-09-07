---
chantier: EXP-1
statut: livré
---

# EXP-1 — exposer les exports de dépôt dans l'UI

**Arrêté sur** — 2026-09-08, `027ca7f` : **LE CHANTIER EST FAIT ET VÉRIFIÉ À L'ÉCRAN.**
Trois routes de téléchargement sur une collection nommée (`routes/depot.py`), une route de
dépôt ShareDocs (`main.deposer_export`), un bloc **Export de dépôt** dans le panneau
Collections. 32 tests Python, 9 tests Node, et SIX vérifications par mutation — les routes
de téléchargement (5 défauts), le manifeste IIIF (7), la garde de format, le message du
refus, le lien d'aller-retour (2) et le débordement. Toutes rouges sur le test qui prétend
les couvrir. Reste la FUSION
vers `main`, qui est la mise en production.

**La passe de QA a trouvé trois défauts que la suite ne pouvait pas voir**, et c'est le
fait marquant. Un refus qui nommait deux gestes que personne n'avait tentés (message
hérité d'un accesseur générique). Un champ obligatoire que personne ne pouvait remplir —
on ne nomme pas l'adresse d'images qu'on n'a pas publiées. Un `404` nu là où le chemin
saisi était le fil d'Ariane de l'interface web. Aucun n'était un défaut de CODE : les
trois étaient dans ce que l'écran DIT ou DEMANDE.

## Reste

- [x] Un bouton produit la fiche de description de collection et les enregistrements de métadonnées côté serveur, sans accès shell
- [x] Le manifeste IIIF est produit par la même voie
- [x] Le fichier produit est téléchargeable par le navigateur ET déposable sur ShareDocs, sur le patron déjà en place pour `/api/sauvegarde`
- [x] Les cœurs restent partagés entre la CLI et la route : aucune logique d'export n'est réécrite côté serveur, comme l'import de vocabulaire a déjà une CLI et un bouton
- [x] Le choix d'exposer ou non le crosswalk et la provenance est tranché et écrit
- [x] La passe `pilotage/qa/export-depot.md` est jouée, et sa zone « Le bloc est là pour qui LIT » est verte : le bloc s'affiche pour un participant NON propriétaire, la ligne de dépôt seulement pour un propriétaire. **Jouée le 2026-09-08**, derrière `faux_proxy_auth.py`, sur une base jetable — quatre zones sur quatre, et elle a trouvé trois défauts qu'aucun test n'avait vus
- [ ] Le chantier est FUSIONNÉ sur `origin/main`, donc déployé — le VPS suit cette branche seule (INFRA-10). `origin/dev` suffit à l'INTÉGRATION et le journal ne dément plus ; cette case-ci parle de la mise en production, et elle attend la passe de QA

## Contexte

**Différé, pas interrompu.** Mise en attente actée le 2026-08-27. Aucun code n'a été
écrit ; c'est le C5 de `docs/roadmap.md`, renommé ici en EXP-1 pour suivre le vocabulaire
de codes du journal.

Le raisonnement tient en une phrase : la doctrine « scripts hors-app » supposait le
mono-poste. Elle ne survit pas au déploiement — non parce qu'elle était mauvaise, mais
parce que sa condition disparaît.

Le patron existe déjà deux fois dans le dépôt (`/api/sauvegarde` pour le fichier produit
côté serveur, `lexique_import.py` pour le cœur partagé CLI + route). Ce chantier n'invente
rien : il applique. C'est ce qui le rend peu risqué une fois INFRA-1 fait.

## Ce que l'implémentation a tranché

**La collection est un segment de CHEMIN, pas un paramètre facultatif.** Les trois outils
traitent `collection_id=None` comme « corpus entier », sans consulter la moindre portée :
c'est le bon défaut sur la machine de la base, et c'est exactement ce qu'une route ne doit
jamais faire. Une route qui l'oublierait répondrait 200, avec un fichier plausible,
contenant le corpus des autres. En chemin, le cas cesse d'être joignable — et un test
porte sur la FORME des chemins déclarés, pour que les routes ajoutées plus tard en
héritent sans qu'on y repense.

**Lire suffit pour télécharger, posséder est exigé pour déposer.** Le premier point est un
arbitrage rendu le 2026-09-07 : ces artefacts DÉCRIVENT un périmètre auquel on est déjà
admis, et DROIT-1 le dit dans ces termes. Le second est à moi, et il se renverse en une
ligne (`administrer=True` dans `deposer_export`) : emporter un fichier pour soi n'est pas
l'écrire dans un dossier partagé dont l'application ne contrôle pas l'audience — c'est le
second des deux motifs qui réservent déjà `deposer-sauvegarde`, et le seul qui s'applique
ici, décrire une collection n'étant pas un geste d'exploitation.

**Trois extractions, toutes dans le sens du partage.** `zip_tables` et `xlsx_tables`
sortent du `main()` des métadonnées, et la CLI passe désormais par elles — sans quoi le
chemin partagé ne serait exercé par aucun test. `_ecrire_xlsx` levait un `SystemExit`
quand `openpyxl` manque : parfait pour une CLI, intenable pour un cœur partagé, puisqu'il
n'hérite pas d'`Exception` et traverse les gardes d'un serveur ; il devient
`ExportIndisponible`. Et les constats de l'IIIF deviennent des DONNÉES
(`diagnostic_base_url`, `diagnostic_regime`), la CLI ne gardant que la mise en forme.

**Ce dernier point est le vrai enseignement du chantier.** L'outil range ses décisions de
droits dans des messages `stderr` destinés à un humain devant un terminal. Un
téléchargement n'a personne devant lui. Les taire aurait effacé ce qui distingue un dépôt
qui RETIENT ses scans d'un dépôt qui les a OUBLIÉS — la confusion même que
`requiredStatement` existe pour empêcher côté visionneuse. D'où `AVERTISSEMENTS.txt` dans
l'archive, et des refus qui reprennent le message de l'outil AU MOT PRÈS : deux textes qui
disent la même chose aujourd'hui divergent au premier ajustement, et c'est alors la route
qui ment, puisque c'est elle qu'on lit le moins.

**Le crosswalk et la provenance restent en CLI, avec leur condition de réouverture.** Ils
se produisent au moment de DÉPOSER — geste rare, préparé, qui suppose déjà un accès à
l'entrepôt — là où la fiche, les enregistrements et le manifeste se consultent en cours de
travail. L'argument est écrit dans `docs/export-metadonnees.md`, et il est réfutable : le
crosswalk DC/DataCite est justement ce que Nakala attend, donc dès qu'un dépôt se fait
sans que personne n'ait de shell, les deux suivent par le même patron.

## Ce que ce chantier a laissé ouvert à côté de lui

`statut_diffusion` n'a **aucun champ à l'écran**. Le manifeste n'emporte ses images que
d'une collection déclarée `public` ; on peut désormais produire ce manifeste sans shell,
et il faut toujours `tools/gerer_collections.py` pour lever la retenue. `PATCH
/api/collections/{id}` accepte pourtant le champ. Le trou est dans le PARCOURS, pas dans le
code — et il n'apparaît qu'une fois l'export exposé, ce qui est la seule raison de le noter
ici plutôt que de l'avoir prévu.
