---
chantier: INFRA-3
statut: différé
---

# INFRA-3 — credentials WebDAV par utilisateur

**Point de départ** — mis en attente exprès : sans sessions réelles (INFRA-1), il n'y a
pas d'utilisateur à qui rattacher des identifiants.

**Relue le 2026-08-31 : la fiche décrivait une fuite refermée depuis trois jours.** Elle
affirmait — vérifié le 2026-08-27 — que `pipeline/sharedocs.py:34` gardait `_session` en
variable globale de module et que `configure()` l'écrasait pour tout le process. Ni l'un
ni l'autre n'existe : SHARE-1 (2026-08-28) a livré `_perso`, un dictionnaire indexé par
principal, et `configurer(..., principal=)` dont le paramètre est OBLIGATOIRE et
keyword-only sans défaut — précisément pour qu'un appelant distrait ne retombe pas sur le
compte de l'instance. Trois des quatre cases sont donc satisfaites par un autre chantier.
La fiche reste `différé` sur la seule qui demeure, et qui n'a jamais été un portage :
faut-il PERSISTER des identifiants ShareDocs, chiffrés, plutôt que de les redemander à
chaque redémarrage du serveur ?

Aucun commit n'a jamais cité INFRA-3, et il n'y en aura pas pour ces trois cases : c'est
SHARE-1 qui les a fermées, et l'attribution lui revient.

## Reste

- [x] **Chaque utilisateur a ses propres identifiants** — livré par SHARE-1 : une session par principal, résolution « la mienne si j'en ai une, celle de l'instance sinon », et forcer un compte absent est une erreur NOMMÉE plutôt qu'un repli silencieux. **La seconde moitié de la case n'est pas vraie littéralement, et c'est une décision** : le compte d'instance PEUT être saisi dans l'application (`POST /api/sharedocs/connexion` avec `compte=instance`), mais seulement par un administrateur. Ce que la case redoutait — n'importe qui configurant ShareDocs pour tout le monde — est fermé ; l'interdiction absolue de saisie ne l'a jamais été, et l'exiger empêcherait de remplacer un mot de passe expiré sans redémarrer le serveur
- [ ] **La seule question qui reste, et elle n'a pas de réponse évidente** : faut-il persister ces identifiants, chiffrés, plutôt que de les redemander à chaque redémarrage ? Ce n'est pas un portage de l'existant mais une RUPTURE DE DOCTRINE assumée — aujourd'hui rien n'est sur disque (cf. CLAUDE.md), donc il n'y a ni secret à protéger ni clé à gérer. Persister introduit les deux. Le coût de ne rien faire est connu et modeste : reconfigurer sa session après chaque redémarrage du serveur
- [x] **Un dépôt porte son identité** — livré par SHARE-1 : le dépôt de sauvegarde est journalisé (A3, `cible_table='sharedocs'`) et l'événement distingue LA PERSONNE qui a cliqué du COMPTE Huma-Num employé. Côté serveur distant, c'est le compte personnel qui signe dès qu'il en existe un — sinon celui de l'instance, ce que `GET /api/sharedocs/etat` annonce avant le geste plutôt qu'après
- [x] **Le mono-poste est inchangé** — livré par SHARE-1 : hors proxy, `main._principal_sharedocs` est le seul endroit qui décide qui est « je », et aucune session personnelle ne s'ouvre sans identité (fermeture par défaut, comme la portée vide d'AUTH-2)

## Contexte

**Différé, pas interrompu** : c'est une mise en attente délibérée derrière INFRA-1, pas
un travail abandonné en cours de route. Mise en attente actée le 2026-08-27 ; aucun
commit de code n'a jamais cité ce code.

**Ce qui a été la raison d'être de cette fiche est traité** — et il vaut la peine de garder
le constat, parce qu'il était juste. Vérifié le 2026-08-27 : `pipeline/sharedocs.py`
gardait alors `_session = {"url", "user", "password"}` en **variable globale de module**,
qu'un `configure()` écrasait pour tout le process. Déployé en multi-utilisateur, la
personne qui configurait ShareDocs le configurait pour tout le monde, et le dépôt lancé
par quelqu'un d'autre serait parti avec ses identifiants à elle. SHARE-1 l'a fermé le
2026-08-28, trois jours plus tard, sans jamais citer INFRA-3 — les deux fiches
décrivaient le même défaut sans le savoir.

**Reste la rupture de doctrine, intacte.** Aujourd'hui ces identifiants vivent **en
mémoire serveur uniquement, jamais sur disque** (cf. CLAUDE.md). Persister introduirait
un secret à chiffrer et une clé à gérer — donc une décision de conception, pas un
portage. Elle n'est toujours pas prise, et rien ne presse : le coût de s'en passer est de
reconfigurer sa session après un redémarrage. C'est la seule chose que cette fiche
attend encore.

Ne dépend plus d'AUTH-1, livré : il y a désormais un utilisateur en base à qui rattacher
un secret, le jour où l'on décidera qu'il faut en garder un.
