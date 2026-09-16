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
>
> **« Étude B » tombe de la même façon, et aucune case ne la demande.** esther v1 vit
> aussi ailleurs, donc sa suppression RÉUSSIT — jouée par erreur le 2026-09-16, en
> cherchant une collection à faire refuser. Elle emporte deux choses que la remise en
> état ne rendait pas : ses termes locaux `grille-b` et `ambiance-b`, dont *Un terme
> qu'on ne lit pas ne se voit pas* a besoin, deviennent GLOBAUX ; et `proprio`, qui
> n'atteint plus esther v1 que par elle une fois « Collection Test » supprimée, ne voit
> plus AUCUN album. Ne supprimer que ce que les cases nomment.

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
- [ ] Le même refus, rejoué en descendant le formulaire jusqu'à *Enregistrer* : le message rouge s'affiche juste sous les boutons de « Collection Test », lisible sans faire défiler, et pas sous la dernière collection de la liste
- [ ] Ajouter un mot à la description, puis *Enregistrer* : « enregistrée » s'affiche sous les mêmes boutons, et l'écran ne saute pas — *Enregistrer* est encore à la hauteur où l'on a cliqué
- [x] La collection dépliée nomme l'Administration comme l'endroit où l'on règle qui entre, avec un lien qui y mène

### Les autres la lisent sans la modifier

- [x] Sous `lectrice` : « Collection Test » se déplie, montre sa description et son référent, et aucun champ n'est modifiable
- [x] Sous `stagiaire` : même chose — écrire dans une collection n'est pas la décrire
- [x] Sous `arrivant` : « Collection Test » n'apparaît pas du tout, et l'écran ne ressemble pas à une panne

### Créer ne demande qu'une identité

**Le décor du refus n'existe pas d'office** : aucun album ne vit seulement dans une
collection de `proprio`. Pour la seconde moitié de la dernière case, sous `proprio` et APRÈS
avoir supprimé « Collection Test » : créer « Collection isolée » ; *+ Nouvel album*
« Album isolé », Collection = « Collection isolée », sans planche ; supprimer « Collection
isolée » — c'est elle que le refus doit compter. Puis supprimer l'album (🗑), et la
collection, qui part alors sans refus. **Le refus s'affiche dans « Collection isolée »,
sous ses boutons.** Joué le 2026-09-16, il tombait en bas du bloc, sous toutes les
collections ; COL-2 l'a ramené près du geste le jour même. S'il retombe en bas, c'est une
régression à signaler, pas un détour à faire.

- [x] Sous `arrivant` : le bouton de création est là ; créer « Carnet d'arrivant » ouvre aussitôt SON formulaire, dont il est propriétaire
- [x] Le message qui suit la création dit où faire entrer quelqu'un, avec le lien vers l'Administration
- [x] Sous `arrivant`, supprimer « Carnet d'arrivant » (vide) réussit
- [x] Sous `proprio`, supprimer « Collection Test », dont l'album esther v1 vit aussi ailleurs, puis une collection dont un album ne vit QUE là : le second refus compte les albums qui resteraient sans collection, et la collection survit au refus

### L'Administration n'a gardé que les accès

**Sous `admin-bd`**, *Administration*.

- [x] Le bloc « 👥 Accès aux collections » ne permet ni de créer, ni de renommer, ni de supprimer une collection, ni d'en changer le référent
- [x] Chaque collection y renvoie vers la Bibliothèque pour ce qu'elle EST, avec un lien
- [x] Le bloc déclare quels groupes d'administration voient tout le corpus, en nommant `bd-admins`
- [ ] « Collection Test » dépliée, saisir `annotateurs` et laisser le genre sur « Utilisateur ou groupe ? », puis *+ Accorder* : un refus rouge s'affiche sous la ligne d'ajout de « Collection Test » et demande de choisir, et la liste des accès n'a pas changé

### Étroit, clavier, thèmes

**Sous `proprio`.**

- [x] À 375 px, le formulaire tient en une colonne, sans débordement de côté ; les notes passent à la ligne
- [x] Chaque champ du formulaire s'atteint à la tabulation dans l'ordre visuel, et porte un libellé annoncé par un lecteur d'écran
- [x] En thème clair comme en sombre, la pastille d'embargo échu se lit, et ne tient pas à la seule couleur

### Remettre en état

La passe a supprimé « Collection Test » et changé son régime. Sans cette zone, les passes
qui s'appuient sur elle échouent plus tard sur un décor absent — et rien ne dira que la
cause est ici. L'état ci-dessous est celui mesuré le 2026-09-14, avant le jeu.

**La ligne *+ Accorder* n'a pas de genre par défaut** : choisir **Groupe** pour
`annotateurs` et `etudiants`, **Utilisateur** pour `stagiaire` — le bouton refuse tant
que ce n'est pas fait. Le 2026-09-16, « Utilisateur » était présélectionné, et les deux
groupes ont d'abord été posés en utilisateurs : un groupe accordé ainsi n'ouvre rien à
personne, et la liste n'en dit que « n'a pas encore ouvert l'application ». COL-2 a
retiré la présélection le jour même.

**Si « Étude B » a été supprimée** (cf. l'avertissement de tête) : la recréer sous
`proprio` ; ranger esther v1 dans « Collection Test » et dans « Étude B » **sous
`admin-bd`**, puisque `proprio` ne le voit plus ; puis, sous `proprio`, *Exploration →
📖 Lexique*, passer la **Portée** de `grille-b` et de `ambiance-b` sur « Étude B » — la
valeur `tendue` suit sa dimension, `commun` reste global. « Étude B » ne reçoit aucun
accès : `proprio` y était seul.

- [x] « Collection Test » est recréée depuis la Bibliothèque **sous `proprio`**, qui en redevient donc propriétaire du même coup
- [x] L'album *esther v1* y est rattaché
- [x] Ses trois accès sont reposés dans *Administration → 👥 Accès aux collections* : `annotateurs` en **lecture** avec « peut exporter » COCHÉE, `etudiants` en **écriture**, `stagiaire` en **écriture** — les trois en genre « groupe » sauf `stagiaire`, qui est un utilisateur
- [x] Son régime de diffusion est ramené à VIDE, et non laissé sur `public` : c'est ainsi que *Export de dépôt* attend de la trouver
- [x] Sous `lectrice`, la Bibliothèque remontre « esther v1 » : le décor est rendu, et on le constate au lieu de le supposer
