---
chantier: SHARE-3
statut: à venir
---

# SHARE-3 — la source ShareDocs se choisit par collection, pas par instance

**Point de départ** — 2026-09-10, proposé par l'équipe pendant l'arbitrage d'INFRA-3 :
*« le compte choisi par le ou les administrateurs de la collection ; éventuellement il peut
définir un path pour les autres comptes en sélectionnant quel dossier est la source »*. Puis
précisé le même jour, et c'est la précision qui cadre le chantier : *« pour l'instant c'est
pour 1 projet, avec surtout un compte, ou plusieurs comptes avec un espace partagé. Mais
dans le futur, s'il y a plusieurs projets qui cohabitent, il faudrait pouvoir définir
certains workplaces ayant leur ShareDocs. »*

**Le fait qui découpe ce chantier en deux paliers de coût très différents : les
IDENTIFIANTS et la RACINE ne sont pas de la même nature.** Le compte Huma-Num — hôte,
login, mot de passe — est un **secret** : il doit vivre dans l'environnement et survivre
aux redémarrages. La racine n'est **qu'un chemin**. Elle n'est pas un secret, donc elle
peut vivre en base, par collection, posée à l'écran, sans toucher à l'invariant « aucun
secret en base ».

**Ce que ce découpage dissout.** La première rédaction de cette fiche annonçait un nœud —
un compte choisi dans l'application ne peut pas venir de l'environnement, donc il meurt à
chaque déploiement, donc il faudrait persister un secret, ce qu'INFRA-3 venait d'écarter.
**Ce nœud ne concerne que le palier 2.** Le palier 1 — la racine — n'a rien à persister.

**Ce que l'attente coûte, et pourquoi elle est tenable.** Au 2026-09-10, `BD_SHAREDOCS_URL`
est laissée VIDE sur la production, exprès : la racine est UNE pour toute l'instance, donc
la fixer reviendrait à figer un projet ou à tout exposer — `GET /api/sharedocs/liste` n'a
aucune garde d'administrateur, et ce que le compte voit, toute identité peut le parcourir.
Personne ne parcourt donc ni n'importe depuis ShareDocs aujourd'hui, stagiaires compris.
C'est écrit dans `docs/exploitation.md` pour qu'on ne le découvre pas le jour de leur
arrivée.

## Un commit de code lui est attribué, et il n'est pas d'elle — 2026-09-10

`4221748` — le commit qui laisse les variables ShareDocs vides — nomme `SHARE-3` dans son
corps pour dire ce qui lèvera l'attente. Il touche `deploy/`, donc il compte comme du code,
et l'outil cherche le code d'un chantier dans le sujet **ou le corps**. **Cette fiche `à
venir` s'affichera donc avec un commit de code alors qu'aucune ligne n'en est écrite**, et
l'écran la démentira — ce démenti est ATTENDU, il ne signale pas un travail commencé.

Le même mécanisme frappe `INFRA-7` le même jour, et `COL-1` depuis plus longtemps. La règle
qui en sort : **le renvoi vers un autre chantier appartient à la fiche, pas au message d'un
commit de code.**

## Reste

### Palier 1 — la racine par collection, sans un seul secret déplacé
- [ ] **La racine est un réglage de COLLECTION, stocké en base, et ce n'est pas une entorse.** Un chemin n'est pas un secret : `collection` gagne une colonne, le compte reste dans l'environnement. Attendu : la doctrine « aucun secret en base » est citée dans la migration elle-même, pour que le prochain lecteur voie que la question a été posée plutôt que contournée
- [ ] **Le confinement est côté SERVEUR, jamais dans l'écran.** `list_dir` et `download` passent déjà par `_join`, qui refuse tout segment `..` — préfixer le chemin demandé par la racine de la collection suffit donc à confiner. Attendu : un chemin forgé passé directement à l'API n'atteint rien au-dessus de la racine, éprouvé par un test qui essaie, et non par lecture du code
- [ ] **Poser la racine est un geste de PROPRIÉTAIRE** (`peut_administrer`), jamais d'écriture : décider ce que les autres verront n'est pas annoter. C'est la distinction qu'AUTH-3 porte déjà, et la leçon d'AUTH-4 — la garde se pose sur l'ACTE, pas sur l'écran qui le contient
- [ ] **L'écran où on la pose est nommé, et la frontière de `COL-2` y répond déjà** : la racine décrit ce que la collection EST vis-à-vis du dehors, comme sa licence ou son embargo — donc la Bibliothèque, avec les autres descripteurs, et non le panneau des accès

### Palier 2 — plusieurs comptes, et le nœud qui reste entier
- [ ] **Un compte par collection ne peut pas venir de l'environnement.** Le compte d'instance survit aux redémarrages parce qu'il se recharge de `BD_SHAREDOCS_*`. Un compte saisi dans l'application vit en mémoire et meurt à chaque déploiement — que la veille d'INFRA-10 déclenche seule. On retombe sur la persistance qu'INFRA-3 a écartée le 2026-09-10. **Ce palier ne s'ouvre donc que si le besoin devient réel**, et l'équipe a dit qu'il ne l'est pas : aujourd'hui un projet, un compte ou plusieurs comptes sur un espace partagé
- [ ] **La sortie par l'environnement est ÉCARTÉE ou retenue, avec sa raison.** Déclarer `BD_SHAREDOCS_COL_<id>_*` ferait survivre les comptes sans rien persister — mais poser un compte redeviendrait un geste en SSH, précisément ce qu'AUTH-7 a supprimé en faisant passer la gestion des comptes par une interface web. Ce serait rendre à la console ce qu'on vient de lui retirer
- [ ] **Le mot « workplace » de la demande est traduit, ou gardé.** L'équipe parle de *workplaces ayant leur ShareDocs* ; le modèle n'a pas cet objet — il a la COLLECTION, qui est déjà l'unité de cloisonnement (AUTH-2) et l'unité de dépôt. Attendu : dire si « workplace » = collection, ou si c'est un palier au-dessus qui n'existe pas encore. En inventer un serait le plus cher des deux, et rien n'indique qu'il le faille

### L'ambiguïté que le modèle porte déjà
- [ ] **« La source de quelle collection ? » n'a pas de réponse unique, et il faut en choisir une.** L'import vise un ALBUM (`POST /api/sharedocs/importer` prend `album_id`), et depuis AUTH-3 un album vit dans PLUSIEURS collections. Le même geste peut donc relever de deux racines. C'est le cas qu'a déjà rencontré DROIT-1 pour le manifeste IIIF, et sa réponse est le patron disponible : exiger que la collection soit NOMMÉE, fail-closed, plutôt que d'inventer un arbitrage
- [ ] **La résolution actuelle est une règle à DEUX termes, et elle en gagne un troisième.** `resoudre(principal, compte)` applique « la mienne si j'en ai une, celle de l'instance sinon ». Attendu : la règle réécrite en une phrase avant d'être codée — c'est ce qui a fait la solidité de SHARE-1, et son mode d'échec est nommé, « forcer un compte absent est une erreur NOMMÉE, jamais un repli silencieux »

### Ce qui devra être vrai
- [ ] Un membre d'une collection ne parcourt QUE la racine déclarée pour elle, éprouvé sous son identité et non déduit de la configuration
- [ ] Deux collections aux racines disjointes ne se voient pas l'une l'autre, éprouvé sous DEUX identités
- [ ] Un import dont l'album appartient à deux collections ne choisit pas tout seul : il exige que la collection soit nommée, ou refuse en le disant
- [ ] Une collection SANS racine déclarée ne retombe pas silencieusement sur la racine du compte — sans quoi l'oubli d'un réglage ouvrirait tout, et c'est le mode d'échec le plus probable de ce chantier
- [ ] Le journal A3 continue de distinguer LA PERSONNE qui a cliqué du COMPTE Huma-Num employé, comme il le fait pour le dépôt de sauvegarde depuis SHARE-1

## Contexte

**Pourquoi ça n'était pas un besoin avant.** Tant que l'instance servait un projet et un
corpus, un compte unique suffisait. Ce qui change tient en deux faits : l'arrivée de gens
pour trois mois — les stagiaires n'auront jamais de compte Huma-Num, qui s'ouvre à la
demande —, donc le compte partagé devient le compte de TRAVAIL de la majorité alors qu'il
avait été conçu comme un REPLI (SHARE-1) ; et la perspective de plusieurs projets sur la
même instance, où une source unique cesse d'avoir un sens.

**Ce que ce chantier ne doit pas devenir** : un identifiant Huma-Num par collection stocké
en base. Le dépôt n'a aucun secret en base, c'est un invariant écrit, et le premier qui y
entre ouvre la question de la clé, de sa rotation et de sa sauvegarde — pour un service
tiers dont l'application ne contrôle rien. Le palier 1 est justement ce qui permet de
répondre au besoin sans y toucher.

**Voisinage.** `SHARE-1` (les deux sortes de sessions, et la règle de résolution),
`INFRA-3` (la persistance écartée le 2026-09-10, et le câblage laissé vide exprès),
`AUTH-2`/`AUTH-3` (le cloisonnement par collection, dont ceci est la transposition au
stockage distant), `COL-2` (la frontière qui dit où le réglage se pose), `DROIT-1` (le
patron « exiger que la collection soit nommée »), `AUTH-7` (la gestion sans SSH, qu'une
sortie par l'environnement contredirait), `SHARE-2` (le parcours de dépôt, qui refera
l'écran).
