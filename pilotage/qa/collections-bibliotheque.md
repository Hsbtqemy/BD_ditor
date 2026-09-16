---
passe: Les collections dans la Bibliothèque
chantier: COL-2
duree: 20 min
derniere: 2026-09-16
---

# QA — ce que la collection EST se gère dans la Bibliothèque, qui entre dans l'Administration

Le déménagement est verrouillé par ses tests : la création sans droit, l'édition gardée,
le régime de diffusion aligné sur le serveur, le 409 de la suppression, les renvois entre
les deux écrans. Ce que la passe regarde est ce qu'aucun test ne lit : si le formulaire se
COMPREND, si ses notes disent vrai, et si l'on trouve son chemin d'un écran à l'autre sous
chaque identité.

> ⚠ **Cette passe DÉTRUIT du décor, et il faut le savoir avant de commencer.** Sa zone
> « Créer ne demande qu'une identité » fait supprimer « Collection Test », et cette
> suppression RÉUSSIT : esther v1 vit aussi dans « Étude B » et dans la collection par
> défaut, donc aucune garde ne s'y oppose. Or « Collection Test » porte le décor de quatre
> autres passes — l'écriture de `stagiaire` (*Normaliser la casse*), celle de `collectif`
> par `etudiants` (*Compte collectif*), la lecture de `lectrice` (*Un terme qu'on ne lit
> pas ne se voit pas*), l'accès de `proprio` (*Ce que l'annotateur a vu*). La jouer AVANT
> elles les casse en silence : elles échoueront plus tard sur un décor absent, qu'on
> prendra pour un défaut de l'application.
>
> **La jouer donc en FIN de série**, et fermer sa dernière zone avant de passer à autre
> chose. Elle change en outre le régime de diffusion en `public`, ce dont *Export de dépôt*
> dépend.

**Sur la pile locale**, `https://bd.127-0-0-1.sslip.io`. `proprio` possède « Collection
Test », `lectrice` la lit par le groupe `annotateurs`, et `stagiaire` y écrit depuis la
passe *Le droit d'exporter, à l'écran* — vérifié le 2026-09-14, et s'il ne l'a plus, lui
accorder cette écriture d'abord. `arrivant` n'a aucun accès nulle part.

### Le propriétaire décrit sa collection

**Sous `proprio`**, *Bibliothèque → 📚 Collections*, « Collection Test » dépliée.

- [x] Le formulaire se lit en trois groupes, dans cet ordre : ce qu'elle est (nom, description, dates), sa diffusion (régime, embargo, licence, base légale), son référent
- [x] Le régime de diffusion est une liste fermée, sans saisie libre
- [x] Passer le régime à `public` et enregistrer : le message le confirme, et après rechargement la collection affiche `public`
- [x] Sous la date d'embargo, une note dit que la date RETIENT et ne rend jamais rien publiable toute seule
- [x] Une date d'embargo passée (`2020-01-01`) est signalée comme échue, là même où on la modifie
- [x] Une date illisible (`31/12/2030`) n'efface rien et ne passe pas pour une date : elle est signalée comme illisible
- [x] La note du référent dit que c'est une ADRESSE, qui ne sort d'aucun export, et pas le responsable scientifique
- [x] Prendre le nom « Collection par défaut » est refusé, avec un message lisible
- [x] La collection dépliée nomme l'Administration comme l'endroit où l'on règle qui entre, avec un lien qui y mène

### Les autres la lisent sans la modifier

- [x] Sous `lectrice` : « Collection Test » se déplie, montre sa description et son référent, et aucun champ n'est modifiable
- [x] Sous `stagiaire` : même chose — écrire dans une collection n'est pas la décrire
- [x] Sous `arrivant` : « Collection Test » n'apparaît pas du tout, et l'écran ne ressemble pas à une panne

### Créer ne demande qu'une identité

- [x] Sous `arrivant` : le bouton de création est là ; créer « Carnet d'arrivant » ouvre aussitôt SON formulaire, dont il est propriétaire
- [x] Le message qui suit la création dit où faire entrer quelqu'un, avec le lien vers l'Administration
- [x] Sous `arrivant`, supprimer « Carnet d'arrivant » (vide) réussit
- [x] Sous `proprio`, supprimer « Collection Test », dont l'album esther v1 vit aussi ailleurs, puis une collection dont un album ne vit QUE là : le second refus compte les albums qui resteraient sans collection, et la collection survit au refus

### L'Administration n'a gardé que les accès

**Sous `admin-bd`**, *Administration*.

- [x] Le bloc « 👥 Accès aux collections » ne permet ni de créer, ni de renommer, ni de supprimer une collection, ni d'en changer le référent
- [x] Chaque collection y renvoie vers la Bibliothèque pour ce qu'elle EST, avec un lien
- [x] Le bloc déclare quels groupes d'administration voient tout le corpus, en nommant `bd-admins`

### Étroit, clavier, thèmes

**Sous `proprio`.**

- [x] À 375 px, le formulaire tient en une colonne, sans débordement de côté ; les notes passent à la ligne
- [x] Chaque champ du formulaire s'atteint à la tabulation dans l'ordre visuel, et porte un libellé annoncé par un lecteur d'écran
- [x] En thème clair comme en sombre, la pastille d'embargo échu se lit, et ne tient pas à la seule couleur

### Remettre en état

La passe a supprimé « Collection Test » et changé son régime. Sans cette zone, les passes
qui s'appuient sur elle échouent plus tard sur un décor absent — et rien ne dira que la
cause est ici. L'état ci-dessous est celui mesuré le 2026-09-14, avant le jeu.

- [x] « Collection Test » est recréée depuis la Bibliothèque **sous `proprio`**, qui en redevient donc propriétaire du même coup
- [x] L'album *esther v1* y est rattaché
- [x] Ses trois accès sont reposés dans *Administration → 👥 Accès aux collections* : `annotateurs` en **lecture** avec « peut exporter » COCHÉE, `etudiants` en **écriture**, `stagiaire` en **écriture** — les trois en genre « groupe » sauf `stagiaire`, qui est un utilisateur
- [x] Son régime de diffusion est ramené à VIDE, et non laissé sur `public` : c'est ainsi que *Export de dépôt* attend de la trouver
- [x] Sous `lectrice`, la Bibliothèque remontre « esther v1 » : le décor est rendu, et on le constate au lieu de le supposer
