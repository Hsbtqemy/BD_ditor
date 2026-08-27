---
chantier: SHARE-1
statut: à venir
---

# SHARE-1 — session ShareDocs : une d'instance, et une par personne

**Point de départ** — fiche ouverte le 2026-08-27 en cadrant AUTH-2, qui a mis le défaut
au jour sans être le bon endroit pour le corriger. Aucune ligne écrite.

## Reste

### La session
- [ ] `pipeline/sharedocs.py` garde ses identifiants par PRINCIPAL et non plus dans un dictionnaire de module : deux personnes connectées à deux comptes Huma-Num ne s'écrasent plus l'une l'autre
- [ ] Une session d'INSTANCE, alimentée par `BD_SHAREDOCS_URL/USER/PASS`, sert de repli à qui n'a pas connecté le sien — c'est le comportement d'aujourd'hui, il ne doit pas changer
- [ ] Sans proxy d'auth (`BD_AUTH_PROXY` faux), tout retombe dans un unique emplacement : le mono-poste se comporte EXACTEMENT comme avant, prouvé par un test
- [ ] Les mots de passe restent en mémoire serveur, jamais sur disque, jamais en base — l'invariant de `docs/hebergement-securite.md` tient après le changement
- [ ] `/api/sharedocs/etat` dit LEQUEL des deux comptes répondrait, sinon on dépose sans savoir où

### Le suivi
- [ ] Le dépôt d'une sauvegarde est un acte JOURNALISÉ (A3) : aujourd'hui `POST /api/sharedocs/deposer-sauvegarde` n'appelle pas `journal` du tout, donc rien ne dit qui a déposé quoi, ni sous quel compte
- [ ] L'événement distingue la personne qui a cliqué du compte Huma-Num utilisé — ce sont deux faits différents dès qu'existe une session d'instance

### Ce qui ne bouge pas
- [ ] La liste d'hôtes autorisés (`BD_SHAREDOCS_ALLOWED_HOSTS`) et le refus des IP internes valent pour toutes les sessions, y compris personnelles : le correctif SSRF ne doit pas se contourner en apportant sa propre URL

## Contexte

Différé derrière AUTH-2 pour une raison de fond : « par personne » n'a pas de sens tant
qu'il n'y a pas de personnes. En mono-poste le défaut est invisible — il n'y a qu'un
utilisateur, donc la session unique est la sienne.

Constat d'origine, mesuré le 2026-08-27 : `pipeline/sharedocs.py:34` porte
`_session: dict = {"url": None, "user": None, "password": None}`, un dictionnaire de
module, donc UNE session pour tout le processus serveur. Le premier connecté la fixe pour
tout le monde ; en multi-utilisateur, Bob déposerait sur Huma-Num sous le compte d'Alice.

Décision du 2026-08-27 : les DEUX, pas l'un ou l'autre. Un compte d'instance (le porteur
du projet) parce qu'un dépôt pérenne institutionnel n'a pas vocation à dépendre de qui
est connecté ; et des comptes personnels parce qu'ils apportent le suivi, l'usage des
dossiers propres à chacun, et l'absence de conflit d'écriture. La résolution est simple :
ma session si j'en ai une, celle de l'instance sinon.

Ce que ça ne résout PAS, et qu'il ne faut pas espérer : il n'y a aucun « transfert de
droit » possible depuis Authelia. L'application ne voit jamais de mot de passe — c'est le
principe même d'AUTH-1 — et ShareDocs Huma-Num est un système de comptes séparé, sans
fédération avec le proxy. Un accès ShareDocs ne se dérive pas d'une identification
Authelia : il se saisit, ou il vient de l'instance.
