---
chantier: INFRA-3
statut: livré
---

# INFRA-3 — credentials WebDAV par utilisateur

**Arrêté sur** — 2026-09-10, `4221748` : la seule question restante est tranchée — **on ne persiste
pas** —, et le geste qui l'a rendue facile n'était pas celui qu'on cherchait. Voir « Ce que
la question cachait » ci-dessous.

**Point de départ** — mis en attente exprès : sans sessions réelles (INFRA-1), il n'y a
pas d'utilisateur à qui rattacher des identifiants.

**Le blocage est LEVÉ — 2026-09-05.** INFRA-1 est livré : l'instance sert en HTTPS sur `bd.edito-revue.fr`, derrière Authelia, avec des comptes nommés et des sessions réelles. La raison de la mise en attente n'existe plus, et le statut change avec elle : laisser `différé` ferait annoncer par la fresque qu'on attend une instance qui tourne déjà. SHARE-1 avait déjà posé `_perso`, indexé par principal ; ce qui manquait était le principal lui-même, et il arrive maintenant dans `Remote-User`.

**Relue le 2026-08-31 : la fiche décrivait une fuite refermée depuis trois jours.** Elle
affirmait — vérifié le 2026-08-27 — que `pipeline/sharedocs.py:34` gardait `_session` en
variable globale de module et que `configure()` l'écrasait pour tout le process. Ni l'un
ni l'autre n'existe : SHARE-1 (2026-08-28) a livré `_perso`, un dictionnaire indexé par
principal, et `configurer(..., principal=)` dont le paramètre est OBLIGATOIRE et
keyword-only sans défaut — précisément pour qu'un appelant distrait ne retombe pas sur le
compte de l'instance. Trois des quatre cases sont donc satisfaites par un autre chantier.
La fiche est restée OUVERTE jusqu'au 2026-09-10 sur la seule qui demeurait, et qui n'a
jamais été un portage : faut-il PERSISTER des identifiants ShareDocs, chiffrés, plutôt que
de les redemander à chaque redémarrage du serveur ? **Répondu non ce jour-là**, et la
réponse a coûté moins cher que la question ne le laissait croire.

Aucun commit n'avait cité INFRA-3 avant le 2026-09-10, et il n'y en aura jamais pour ces
trois cases-là : c'est SHARE-1 qui les a fermées, et l'attribution lui revient.

## Reste

- [x] **Chaque utilisateur a ses propres identifiants** — livré par SHARE-1 : une session par principal, résolution « la mienne si j'en ai une, celle de l'instance sinon », et forcer un compte absent est une erreur NOMMÉE plutôt qu'un repli silencieux. **La seconde moitié de la case n'est pas vraie littéralement, et c'est une décision** : le compte d'instance PEUT être saisi dans l'application (`POST /api/sharedocs/connexion` avec `compte=instance`), mais seulement par un administrateur. Ce que la case redoutait — n'importe qui configurant ShareDocs pour tout le monde — est fermé ; l'interdiction absolue de saisie ne l'a jamais été, et l'exiger empêcherait de remplacer un mot de passe expiré sans redémarrer le serveur
- [x] **NON, on ne persiste pas — tranché le 2026-09-10, et la question s'est dissoute plutôt que d'être arbitrée.** Elle supposait que se passer de persistance coûtait « reconfigurer sa session après chaque redémarrage ». Deux faits mesurés le même jour ont retiré ce coût à peu près partout. **Un** : le compte d'INSTANCE se recharge seul de l'environnement au premier accès (`instance()`, chargement paresseux), donc un déploiement le rétablit sans que personne clique — seules les sessions PERSONNELLES meurent. **Deux** : la population qui aurait une session personnelle est minuscule et le restera — les stagiaires n'auront jamais de compte Huma-Num, qui s'ouvre à la demande et pas pour trois mois. Persister reviendrait donc à poser un secret au repos et une clé à gérer, contre la doctrine écrite de `CLAUDE.md`, pour le confort de trois comptes. **À rouvrir si une équipe se met à travailler sous des comptes Huma-Num nominatifs** — ce n'est pas le cas et rien ne l'annonce
- [x] **Un dépôt porte son identité** — livré par SHARE-1 : le dépôt de sauvegarde est journalisé (A3, `cible_table='sharedocs'`) et l'événement distingue LA PERSONNE qui a cliqué du COMPTE Huma-Num employé. Côté serveur distant, c'est le compte personnel qui signe dès qu'il en existe un — sinon celui de l'instance, ce que `GET /api/sharedocs/etat` annonce avant le geste plutôt qu'après
- [x] **Le mono-poste est inchangé** — livré par SHARE-1 : hors proxy, `main._principal_sharedocs` est le seul endroit qui décide qui est « je », et aucune session personnelle ne s'ouvre sans identité (fermeture par défaut, comme la portée vide d'AUTH-2)

## Ce que la question cachait — 2026-09-10

**La lacune n'était pas la persistance : c'est que le compte d'instance n'était pas
déployé.** Mesuré ce jour-là — `BD_SHAREDOCS_URL` / `_USER` / `_PASS` n'apparaissaient ni
dans l'`environment` du service `app`, ni dans `.env.example`, ni dans un fichier de
`docs/`. Or `_env_instance()` exige les TROIS ; sans elles `instance()` rend `None`, et
`resoudre()` sans session personnelle lève « Non connecté à ShareDocs ».

**Donc en production, le repli conçu par SHARE-1 n'existait pas.** Chacun devait saisir ses
propres identifiants Huma-Num — et les ressaisir après chaque déploiement, que la veille
d'INFRA-10 déclenche toute seule depuis le 2026-09-07. C'est la forme déjà vue avec le
référent d'AUTH-4 le 2026-09-09 : **fonctionnalité livrée, jamais configurée**, et rien
dans le dépôt ne pouvait le dire puisque le code, lui, était juste.

**Et la question posée par l'équipe a trouvé la garde qui manquait, gratuitement.** « Peut-on
définir un dossier source, plutôt que de laisser voir `@Home` et `@Shares` ? » — c'est déjà
possible : `_check_url` ne valide que le schéma et l'HÔTE, le chemin de l'URL est libre, et
`_join` refuse tout segment `..` (« un chemin distant ne doit jamais remonter au-dessus de
la racine ShareDocs »). **Faire porter à `BD_SHAREDOCS_URL` le dossier du corpus confine
donc réellement**, côté serveur et non par politesse d'interface. Ce n'est pas un
raffinement : `GET /api/sharedocs/liste` n'a **aucune** garde d'administrateur, si bien que
ce que ce compte voit, toute identité de l'application peut le parcourir.

**Ce qu'un non-administrateur peut faire vers ShareDocs, vérifié route par route** : rien.
`liste` et `importer` ne font qu'AVALER (et `importer` exige l'écriture sur l'album visé) ;
le seul chemin d'écriture distante est le dépôt de sauvegarde, réservé aux administrateurs
(DROIT-1). Câbler ce compte n'ouvre donc aucun droit d'écriture chez Huma-Num.

**Les trois variables sont câblées et laissées VIDES, exprès — même jour, même heure.**
Le raisonnement ci-dessus (« le compte d'instance se recharge seul ») décrit ce que le
mécanisme FAIT, pas ce que la production a. L'équipe a décidé de ne rien y mettre pour
l'instant : la racine utile dépend du projet et ne se choisit pas encore à l'écran, donc la
fixer reviendrait à figer un projet ou à tout exposer. **La décision de ne pas persister ne
dépend pas de ce réglage** — elle tient à ce que la population des sessions personnelles
restera minuscule —, mais il ne faut pas lire cette fiche comme si ShareDocs était
configuré. Il ne l'est pas, et `docs/exploitation.md` dit ce que ça coûte.

**Ce qui reste ouvert ailleurs** : l'idée d'un compte choisi par les administrateurs de
COLLECTION est partie dans `SHARE-3` — elle ne se règle pas par configuration, un album
vivant dans plusieurs collections depuis AUTH-3.

## Contexte

**`différé` jusqu'au 2026-09-05, `à venir` depuis** : c'était une mise en attente
délibérée derrière INFRA-1, pas un travail abandonné en cours de route. Actée le
2026-08-27, levée le jour où l'instance a servi ; aucun commit de code n'a jamais cité ce
code.

**Ce qui a été la raison d'être de cette fiche est traité** — et il vaut la peine de garder
le constat, parce qu'il était juste. Vérifié le 2026-08-27 : `pipeline/sharedocs.py`
gardait alors `_session = {"url", "user", "password"}` en **variable globale de module**,
qu'un `configure()` écrasait pour tout le process. Déployé en multi-utilisateur, la
personne qui configurait ShareDocs le configurait pour tout le monde, et le dépôt lancé
par quelqu'un d'autre serait parti avec ses identifiants à elle. SHARE-1 l'a fermé le
2026-08-28, trois jours plus tard, sans jamais citer INFRA-3 — les deux fiches
décrivaient le même défaut sans le savoir.

**La rupture de doctrine était le vrai sujet, et on ne l'a pas payée.** Ces identifiants
vivent **en mémoire serveur uniquement, jamais sur disque** (cf. CLAUDE.md) ; persister
aurait introduit un secret à chiffrer et une clé à gérer — une décision de conception, pas
un portage. **Écartée le 2026-09-10** : le coût qu'elle prétendait supprimer reposait sur
un repli qui n'était pas déployé, et une fois celui-ci câblé, il ne restait plus qu'un
confort pour trois comptes.

Ne dépend plus d'AUTH-1, livré : il y a désormais un utilisateur en base à qui rattacher
un secret, le jour où l'on décidera qu'il faut en garder un.
