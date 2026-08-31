---
chantier: AUTH-5
statut: livré
---

# AUTH-5 — le cliquet des voies de sortie : ce qui laisse partir une identité doit l'avoir déclaré

**Arrêté sur** — la relecture d'après commit, `0ff38c7`, 31 août : **le cliquet mentait à
l'endroit précis qu'il surveille.** Son contrôle « un trou déclaré qui n'existe plus » ne
pouvait jamais être vrai pour un outil — sous le même préfixe `("outil", …)`,
`SORTIES_DECLAREES` range des SORTIES et `NON_BALAYE` des OUTILS entiers, si bien qu'on
comparait un nom de fichier à des clés de sortie. Démontré dans les deux sens : avec
l'ancien contrôle, rendre `verifier_moteurs.py` exportateur tout en le laissant déclaré
hors balayage laisse les TROIS tests verts. Huit raisons ont aussi été resserrées — elles
disaient « aucune sortie » d'outils qui impriment un compte rendu ; elles disent maintenant
ce qui se vérifie.

Avant elle, le chantier entier, commit `af03075`, 31 août :
`tests/test_sorties_identite.py`, trois cliquets et deux tables déclarées. 61 surfaces
balayées, 11 émettent une identité, six mutations rouges, 21 à 26 s sur une suite de 180 s.

Ce que l'écriture a appris, et qui n'était pas dans la conception : **le semis est le mode
d'échec**, et il l'a été trois fois avant d'être vert pour la bonne raison. Avec une seule
sentinelle, `accord-inter` ressortait muette — elle ne compte que les re-touches ENTRE
auteurs. Sans lemme sur la correction, la concordance ne trouvait rien et paraissait muette
alors qu'elle sait filtrer par auteur. Sans dépliage des zip, un XLSX et la sauvegarde
passaient pour muets. Chaque fois, le cliquet était VERT — et faux. D'où
`test_le_semis_est_visible`, qui n'était pas prévu sous cette forme.

Deux arbitrages se sont confirmés à l'usage plutôt qu'en théorie : les routes PARAMÉTRÉES
étaient bien à balayer (`/api/regions/{id}/tokens` porte l'`auteur` des corrections,
`/api/albums/{id}/planches` porte `verrou_par`), et les trois routes d'EXPORT sortaient en
422 faute de paramètres de requête — le balayage les comptait « non atteintes » alors que
`/api/export/json` émet le login. Un cliquet qui ne voit pas les exports ne vaut rien.

**Point de départ** — fiche ouverte le 2026-08-31, au lendemain immédiat d'un échec de
méthode. AUTH-1 porte depuis le 27 août une case qui dit qu'un inventaire des voies de
sortie « se fait en énumérant ce qui SORT, pas ce dont on se souvient ». Elle a été
corrigée **trois fois**, chaque fois en énumérant mieux, et chaque fois elle était encore
courte.

- **27 août** : « la seule voie de sortie est la sauvegarde ».
- **28 août** : incomplet — `tools/provenance_export.py` sérialise le journal, donc les
  logins.
- **31 août, au matin** : incomplet encore, et l'inventaire précédent avait été fait de
  mémoire. On énumère alors *à la main* ce qui lit `evenement` / `activite` /
  `utilisateur` : six voies, dont trois manquées, dont une ROUTE HTTP.
- **31 août, l'après-midi** : cette énumération-là, faite à la main et avec soin, était
  **encore** courte d'un chemin. `tools/metadonnees_collection.py` a trois sorties et non
  deux : le JSON, les CSV, et un onglet XLSX qui publiait les logins joints par « ; ».

Ce qui l'a trouvé n'est aucune des quatre relectures : c'est un `KeyError`, quand le champ
a été retiré du dict que l'onglet lisait. **Le constat qui ouvre ce chantier n'est donc pas
« il faut mieux énumérer » — c'est que l'énumération à la main a échoué quatre fois de
suite, et qu'il n'y a aucune raison de croire la cinquième.**

Le dépôt sait déjà faire autre chose, et c'est le patron à copier : `test_autorisation.py`
énumère les routes de l'application et exige que chacune ait été TRANCHÉE — soit elle
consulte la portée, soit elle figure sur `HORS_PERIMETRE` avec sa raison écrite. Absente
des deux, la suite échoue. Il ferme la porte de l'OUBLI, pas celle de l'erreur. C'est
exactement ce qui manque ici.

## Reste

### Le décor et les sentinelles
- [x] Trois sentinelles distinctes sont semées, une par SORTE d'identité — un login, un nom lisible, un courriel — parce qu'AUTH-1 les distingue déjà : « ce n'est pas l'email ni le nom lisible, mais un login identifie une personne ». Une sentinelle unique rendrait la déclaration grossière, et une surface autorisée à nommer pourrait se mettre à publier des courriels sans que rien ne bronche
- [x] Le décor place chaque sentinelle dans TOUTES les colonnes qui la portent : `utilisateur` (login, nom, email), `evenement.agent`, `activite.agent`, `token_correction.auteur`, `planches.verrou_par`. Une colonne oubliée au semis est un trou que le cliquet ne verra jamais — et c'est le mode d'échec du cliquet lui-même
- [x] Les sentinelles sont choisies pour être introuvables par accident (aucune sous-chaîne d'un mot français, d'un chemin, d'un nom de colonne) : un faux positif rend un cliquet insupportable, et un cliquet insupportable finit désactivé

### Le balayage
- [x] Les 19 fichiers de `tools/` sont balayés ou déclarés hors balayage avec leur raison — un outil qui n'exporte rien le dit, il ne s'absente pas. C'est là que trois des quatre oublis se trouvaient, et c'est là que les conséquences sont définitives : l'entrepôt garde ses versions
- [x] Les 51 routes GET sont balayées, les 16 paramétrées comprises, leurs ids venant du décor. Les exclure laisserait un trou CONNU D'AVANCE : `/api/planches/{id}` porte `verrou_par` et `/api/regions/{id}/tokens` porte l'`auteur` des corrections
- [x] Le balayage lit les FICHIERS produits autant que `stdout`, et un classeur XLSX par ses CELLULES — un XLSX est un zip, le lire en octets ne prouve rien. C'est la faute qu'une mutation a révélée le 31 août sur le test du dépôt

### La déclaration
- [x] Toute sortie où une sentinelle apparaît figure dans une table `SORTIES_DECLAREES` avec la SORTE émise et sa raison écrite ; une sortie non déclarée fait échouer la suite
- [x] La table ne ment pas : une déclaration qui annonce une sorte que la surface n'émet plus est signalée, comme `test_les_listes_ne_mentent_pas` le fait déjà pour les routes. Une liste périmée est pire qu'absente — elle rassure
- [x] L'existant est DÉCLARÉ tel quel pour obtenir le premier vert, y compris ce qu'on juge mauvais, avec la raison « à traiter, cf. AUTH-1 ». Le cliquet est un instrument d'inventaire, pas un arbitrage de masse : chaque décision mérite la sienne, comme celle du 31 août sur l'accord inter-annotateurs

### Vérifications
- [x] Le cliquet est prouvé par MUTATION et non par sa couleur : remettre un login dans une sortie déclarée muette doit le faire échouer, et retirer une surface de la table aussi
- [x] Le coût en temps est mesuré et écrit : un cliquet qui doublerait la suite par défaut serait déplacé vers un marqueur, et le dire vaut mieux que le découvrir

## Contexte

**Ce que ce cliquet NE fait pas.** Il ne dit pas qu'une sortie est légitime — il dit
qu'elle a été VUE. La différence est la même que pour `test_autorisation.py`, qui vérifie
qu'une route consulte la portée sans jamais vérifier qu'elle en tire la bonne conclusion.
Les arbitrages restent des arbitrages ; ce qui change, c'est qu'aucun ne se prend plus par
défaut, faute d'avoir remarqué qu'il y avait quelque chose à décider.

**Pourquoi trois sortes et pas une.** AUTH-1 a établi que le login, le nom lisible et le
courriel ne sortent pas par les mêmes chemins ni avec les mêmes conséquences : les deux
derniers ne quittent l'instance que par la sauvegarde, le premier part dans les exports de
provenance, qui ont vocation à être DÉPOSÉS. Une déclaration par sorte permet d'écrire
« cette surface peut nommer, elle ne peut pas joindre » — ce qui est la vraie règle, et
qu'une sentinelle unique ne saurait pas exprimer.

**Le mode d'échec du cliquet est le semis.** Une sentinelle absente d'une colonne rend
muette toute surface qui ne lit que cette colonne, et le vert est alors un mensonge. C'est
la même famille que les deux assertions vacantes trouvées le 31 août — une non-vacuité
prouvée sur l'ensemble, un `stdout` vide parce que l'outil écrit dans un fichier. La
parade est de vérifier, pour chaque sentinelle, qu'AU MOINS une surface l'émet : si
personne ne la voit passer, c'est le décor qui est faux, pas le code qui est propre.

**Le nom.** `AUTH-5` plutôt que `SEC-3` : le sujet est l'identité et ce qu'elle devient,
c'est-à-dire la suite directe d'AUTH-1, dont il vient fermer une case en la remplaçant par
quelque chose qui ne pourrit pas.
