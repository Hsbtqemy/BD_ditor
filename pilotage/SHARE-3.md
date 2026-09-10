---
chantier: SHARE-3
statut: à venir
---

# SHARE-3 — un compte ShareDocs choisi par la collection, et non par l'instance

**Point de départ** — 2026-09-10, proposé par l'équipe pendant l'arbitrage d'INFRA-3 :
*« le compte choisi par le ou les administrateurs de la collection ; éventuellement il peut
définir un path pour les autres comptes en sélectionnant quel dossier est la source »*.

**La moitié « dossier source » est DÉJÀ acquise, et sans code** — c'est ce que l'arbitrage
d'INFRA-3 a établi le jour même. `_check_url` ne valide que le schéma et l'hôte, donc l'URL
d'une session peut porter un dossier ; et `_join` refuse tout segment `..`. Faire porter au
compte d'instance l'URL du dossier de corpus confine réellement, côté serveur. Cette fiche
ne porte donc QUE l'autre moitié : que le compte lui-même soit choisi par collection.

**Ce qui la motive.** Aujourd'hui il n'y a qu'un compte partagé pour toute l'instance, et
`GET /api/sharedocs/liste` n'a aucune garde d'administrateur : ce qu'il voit, toute identité
de l'application peut le parcourir. Une racine bien choisie borde ce risque pour UNE
instance mono-projet ; elle ne le borde plus dès que deux collections ne doivent pas voir
les mêmes dossiers, ce qui est le sens même du cloisonnement d'AUTH-2.

## Reste

### Le nœud, à défaire avant tout le reste
- [ ] **Un compte par collection ne peut pas venir de l'environnement, et c'est tout le problème.** Le compte d'instance survit aux redémarrages parce qu'il se recharge de `BD_SHAREDOCS_*` au premier accès. Un compte choisi PAR les administrateurs de collection se saisit dans l'application ; il vit donc en mémoire, et meurt à chaque déploiement — que la veille d'INFRA-10 déclenche toute seule. On retombe exactement sur la question qu'INFRA-3 vient de fermer par la négative : persister, c'est-à-dire un secret au repos et une clé à gérer. Attendu : dire lequel des deux on paie, avant d'écrire une ligne
- [ ] **La sortie par l'environnement est ÉCARTÉE ou retenue, avec sa raison.** Déclarer `BD_SHAREDOCS_COL_<id>_*` ferait survivre les comptes aux redémarrages sans rien persister — mais poser un compte redeviendrait un geste en SSH, c'est-à-dire précisément ce qu'AUTH-7 a supprimé en faisant passer la gestion des comptes par une interface web. Ce serait rendre à la console ce qu'on vient de lui retirer

### L'ambiguïté que le modèle porte déjà
- [ ] **« Le compte de quelle collection ? » n'a pas de réponse unique, et il faut en inventer une.** L'import vise un ALBUM (`POST /api/sharedocs/importer` prend `album_id`), et depuis AUTH-3 un album vit dans PLUSIEURS collections. Le même geste peut donc relever de deux comptes. C'est le cas qu'a déjà rencontré DROIT-1 pour le manifeste IIIF, et sa réponse est le patron disponible : exiger que la collection soit NOMMÉE, fail-closed, plutôt que d'inventer un arbitrage
- [ ] **La résolution actuelle est une règle à DEUX termes, et elle en gagnerait un troisième.** `resoudre(principal, compte)` applique « la mienne si j'en ai une, celle de l'instance sinon » ; un compte de collection s'insère entre les deux, ou au-dessus, et l'ordre est une décision. Attendu : la règle écrite en une phrase avant d'être codée — c'est ce qui a fait la solidité de SHARE-1, et le mode d'échec est connu, « forcer un compte absent est une erreur NOMMÉE, jamais un repli silencieux »

### Ce qui devra être vrai
- [ ] Un membre d'une collection ne parcourt QUE le dossier déclaré pour elle, et la garde est côté serveur — un chemin forgé n'atteint rien d'autre, `..` étant déjà refusé
- [ ] Deux collections aux dossiers disjoints ne se voient pas l'une l'autre, éprouvé sous deux identités et non déduit de la configuration
- [ ] Un import dont l'album appartient à deux collections ne choisit pas tout seul : il exige que la collection soit nommée, ou refuse en le disant
- [ ] Poser ou remplacer le compte d'une collection est un geste de PROPRIÉTAIRE (`peut_administrer`), jamais d'écriture — décider qui voit quoi n'est pas annoter, c'est la distinction qu'AUTH-3 porte déjà
- [ ] Le journal A3 continue de distinguer LA PERSONNE qui a cliqué du COMPTE Huma-Num employé, comme il le fait pour le dépôt de sauvegarde depuis SHARE-1

## Contexte

**Pourquoi ça n'était pas un besoin avant.** Tant que l'instance servait un projet et un
corpus, un compte unique et une racine bien choisie suffisaient. Ce qui change est
l'arrivée de gens pour trois mois — les stagiaires n'auront jamais de compte Huma-Num, qui
s'ouvre à la demande —, et donc le fait que le compte partagé devient le compte de
TRAVAIL de la majorité, alors qu'il avait été conçu comme un REPLI (SHARE-1).

**Ce que ce chantier ne doit pas devenir** : un identifiant Huma-Num par collection stocké
en base. Le dépôt n'a aucun secret en base, c'est un invariant écrit, et le premier qui y
entre ouvre la question de la clé, de sa rotation et de sa sauvegarde — pour un service
tiers dont l'application ne contrôle rien.

**Voisinage.** `SHARE-1` (les deux sortes de sessions, et la règle de résolution),
`INFRA-3` (la persistance, écartée le 2026-09-10, et la racine par l'URL), `AUTH-2`/`AUTH-3`
(le cloisonnement par collection, dont ceci est la transposition au stockage distant),
`DROIT-1` (le patron « exiger que la collection soit nommée »), `AUTH-7` (la gestion des
comptes sans SSH, qu'une sortie par l'environnement contredirait), `SHARE-2` (le parcours
de dépôt, qui refera l'écran).
