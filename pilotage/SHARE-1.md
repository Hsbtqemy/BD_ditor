---
chantier: SHARE-1
statut: livré
---

# SHARE-1 — session ShareDocs : une d'instance, et une par personne

**Arrêté sur** — la relecture d'après commit, `ecfbb2a`, 28 août : un compte inconnu se
refuse au lieu de s'interpréter. Trois défauts de la même forme, sur un chantier déjà
commité et une suite verte.

Avant elle, le chantier entier, commit `a5426b2` : les deux sortes de sessions, la garde
du compte d'instance, le dépôt journalisé et le sélecteur de compte de l'explorateur.
`_session`, dictionnaire de module, cesse d'être la session de tout le monde.

Le chantier est **livré** : les quatre commits vivent sur `origin/dev`.

## Reste

### La session
- [x] `pipeline/sharedocs.py` garde ses identifiants par PRINCIPAL et non plus dans un dictionnaire de module : deux personnes connectées à deux comptes Huma-Num ne s'écrasent plus l'une l'autre
- [x] Une session d'INSTANCE, alimentée par `BD_SHAREDOCS_URL/USER/PASS`, sert de repli à qui n'a pas connecté le sien
> **Cette case a changé en cours de route, et il faut le dire.** Elle ajoutait « c'est le
> comportement d'aujourd'hui, il ne doit pas changer ». Il a changé, sur décision du
> 2026-08-28 : la session d'instance est désormais vivante DÈS LE DÉMARRAGE, sans que
> personne ne clique. La rédaction d'origine se contredisait — aujourd'hui, le mot de passe
> d'env n'est qu'un repli de FORMULAIRE, si bien qu'il fallait que quelqu'un se connecte
> pour qu'un repli existe ; « sert de repli à qui n'a pas connecté le sien » n'était donc
> vrai qu'après amorçage. La contrepartie est assumée : toute personne admise sur
> l'instance peut s'en servir — ce qui était déjà le cas une fois quelqu'un connecté.
- [x] Sans proxy d'auth (`BD_AUTH_PROXY` faux), tout retombe dans un unique emplacement : le mono-poste se comporte EXACTEMENT comme avant, prouvé par un test
- [x] Derrière le proxy SANS identité, AUCUNE session personnelle n'est possible — les ranger toutes sous une même clé y ferait partager un compte Huma-Num entre inconnus, c'est-à-dire le défaut même du chantier sous une autre forme. Fermeture par défaut, comme la portée vide d'AUTH-2
- [x] Les mots de passe restent en mémoire serveur, jamais sur disque, jamais en base — l'invariant de `docs/hebergement-securite.md` tient après le changement
- [x] `/api/sharedocs/etat` dit LEQUEL des deux comptes répondrait, sinon on dépose sans savoir où
- [x] Forcer un compte absent est une ERREUR NOMMÉE, jamais un repli silencieux sur l'autre : déposer sous un compte qu'on n'a pas choisi est exactement ce que ce chantier corrige

### Le compte de l'instance n'appartient à personne
- [x] Le couper ou le remplacer est réservé aux administrateurs (décision du 2026-08-28). Sans cette garde, la première personne qui clique « déconnexion » prive tout le monde du repli — une action personnelle aux effets collectifs, qui marche parfaitement et casse pour les autres
- [x] Se déconnecter ferme MA session seulement, et l'écran cesse d'annoncer « non connecté » à tort quand celle de l'instance prend le relais
- [x] Coupée, elle ne repart PAS de l'environnement au premier accès suivant : sans la distinction « pas encore chargée » / « coupée exprès », la couper n'aurait aucun effet
- [x] Elle n'est pas validée au chargement : un PROPFIND de vérification ferait dépendre le démarrage de la disponibilité d'Huma-Num, et un serveur qui refuse de servir le corpus local parce qu'un service distant est en panne serait un mauvais échange

### Le suivi
- [x] Le dépôt d'une sauvegarde est un acte JOURNALISÉ (A3) : `POST /api/sharedocs/deposer-sauvegarde` n'appelait pas `journal` du tout, donc rien ne disait qui avait déposé quoi, ni sous quel compte
- [x] L'événement distingue la personne qui a cliqué du compte Huma-Num utilisé — ce sont deux faits différents dès qu'existe une session d'instance. `cible_table='sharedocs'` n'est pas une table du schéma, et c'est déjà le contrat du journal (`cible_id` n'est pas une FK) ; l'undo ne le voit pas, sa liste blanche de tables ne le contient pas

### L'écran
- [x] Le compte se CHOISIT (décision du 2026-08-28), et le sélecteur gouverne TOUT le panneau — pas seulement le dépôt : on navigue dans l'arborescence de celui sous lequel on déposera. Choisir au dernier moment ferait déposer ailleurs que là où l'on regarde
- [x] Le sélecteur ne paraît que s'il y a vraiment un choix : un choix à une seule branche n'en est pas un
- [x] Changer de compte relance la navigation à la RACINE — un chemin valide chez l'un ne l'est pas forcément chez l'autre
- [x] Le compte EMPLOYÉ est rendu par le serveur et affiché après le dépôt : une sauvegarde partie sous un compte personnel atterrit dans un espace qui s'en va avec la personne, et c'est le genre de chose qu'on veut lire au moment où ça arrive

### Ce qui ne bouge pas
- [x] La liste d'hôtes autorisés (`BD_SHAREDOCS_ALLOWED_HOSTS`) et le refus des IP internes valent pour toutes les sessions, y compris personnelles : le correctif SSRF ne doit pas se contourner en apportant sa propre URL. Une seule fonction `_valider` borde les deux sortes de sessions — deux validations distinctes finiraient par ne plus border la même chose

### Le cliquet
- [x] Les quatre routes de session sortent de `HORS_PERIMETRE` : elles ne touchent toujours pas au corpus, mais elles consultent désormais QUI appelle. Une de leurs lignes disait « session par personne : cf. SHARE-1 » — la liste portait sa propre échéance
- [x] Vingt-quatre gardes vérifiées par mutation, dont la clé par principal (mutée en clé partagée : c'est le défaut d'origine, reproduit à la demande)

### Ce que la relecture d'après commit a trouvé
> Trois défauts de LA MÊME FORME : une comparaison d'égalité qui décide, sans clause pour
> ce qui n'est ni l'un ni l'autre. `== "instance"` puis « sinon, le compte personnel »
> traite le cas inconnu comme un cas connu.
- [x] Un compte inconnu est REFUSÉ (422 nommant les valeurs acceptées), il ne retombe plus en silence sur le compte personnel. Un administrateur écrivant « instace » ouvrait sa propre session et recevait `{"connecte": true}` : il croyait avoir remplacé le compte de l'instance, le repli de tout le monde restait inchangé, et rien ne le disait
- [x] Le refus est le MÊME partout. La lecture refusait déjà via `resoudre`, mais en 400 : la même faute de frappe donnait un message clair sur `liste` et un effet silencieux sur `connexion`
- [x] À l'import, le contrôle passe AVANT toute création : le mot mal orthographié échouait fichier par fichier — autant d'erreurs que de chemins — et créait un album vide au passage, la cause réelle ne paraissant nulle part
- [x] L'écran n'a plus qu'UN rendu de l'état de connexion. Se connecter depuis l'explorateur ne mettait rien à jour : libellé sans l'origine, sélecteur périmé alors qu'un choix venait d'apparaître, « Mon compte… » encore affiché après avoir servi. Deux chemins rendaient la même chose et avaient divergé le jour même — le défaut que le dépôt combat partout ailleurs, appliqué à du code écrit dans l'heure

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
