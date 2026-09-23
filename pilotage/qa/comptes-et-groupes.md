---
passe: Comptes et groupes
chantier: AUTH-12
duree: 30 min
derniere: 2026-09-23
---

# QA — « 👥 Comptes et groupes » : lire qui utilise l'instance, sans deviner

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur un
commit qui porte le bloc ET l'étape 3 (`6ea6b60` ou après), avec la lecture de l'annuaire
configurée (et non sa doublure). L'annuaire est sur `https://annuaire.127-0-0-1.sslip.io`.
Les mots de passe sont dans `C:\temp\bd-recette\comptes.txt`, hors dépôt. Une fenêtre privée
par identité.

**Ce que la passe éprouve.** Le bloc remplace « 👤 Comptes vus » : il LIT l'annuaire pour
montrer tous les comptes et groupes, venus ou non, et ce que chacun ouvre — dit en ACTES
(« lire », « tous les actes, dont décider qui entre ») et non en niveaux, depuis l'étape 3.
Il ne modifie rien, sauf la nature d'un compte : les accès se RÈGLENT dans la Bibliothèque,
en tête de la collection, et le bloc n'y mène que par des liens. Les gestes joués sont ceux
que la maquette validée faisait jouer d'abord à l'administrateur : répondre à « je ne vois
rien », suivre un cours, lire ce qu'un départ laisserait.

**Ce que la passe ne joue pas, et où c'est éprouvé.** L'annuaire EN PANNE : l'arrêter
toucherait la pile, et c'est joué par `tests/test_e2e_comptes_groupes.py` (les trois états
de l'annuaire). Le regroupement de « À regarder » au-delà de cinq signaux du même code : la
recette n'a pas six arrivants, et c'est joué par le même fichier. Ce qui se passe une fois
ARRIVÉ dans la Bibliothèque — la collection dépliée, le groupe présélectionné, le tableau
des actes — appartient à la passe *Qui entre*, qui le joue en entier ; ici on vérifie le
départ du trajet, pas son arrivée.

**Une case MODIFIE un compte existant** (la nature, zone « Déclarer un login partagé ») et le
remet dans son état : `collectif` porte le décor de la passe *Compte collectif*, qui exige
qu'il soit « une personne » au départ. Ne pas sauter la remise en état.

### Qui voit le bloc
- [x] Sous `proprio`, *Administration* : aucun bloc « 👥 Comptes et groupes » sur la page, et aucun message d'erreur à sa place
- [x] Sous `admin-bd`, *Administration* : le bloc « 👥 Comptes et groupes » est là, et la ligne sous son titre dit « Annuaire lu à HH:MM. », sans les mots « Doublure de test »

### Répondre à « je ne vois rien »
- [x] Sous `admin-bd`, dans le filtre du bloc, taper `arriv` : la liste ne garde que la ligne d'`arrivant`. Cliquer dessus : sa fiche s'ouvre à droite, et l'adresse du navigateur se termine par `?compte=arrivant`
- [x] Dans cette fiche, la section *Collections* ne liste aucune collection et dit « Aucune collection ne lui est ouverte : l'application lui montre un corpus vide. »
- [x] Filtrer `lectrice`, ouvrir sa fiche : la section *Groupes* montre `annotateurs`, et la section *Collections* montre « Collection Test » suivie de ses ACTES — la mention commence par « lire », jamais par « lecture » — et se termine par « — par le groupe annotateurs »
- [x] Dans cette fiche, cliquer `annotateurs` : l'axe passe à *Groupes*, la fiche du groupe s'ouvre, et `lectrice` figure dans sa section *Membres*
- [x] Bouton « Retour » du navigateur : la fiche de `lectrice` revient, axe *Comptes*
- [x] Copier l'adresse du navigateur, l'ouvrir dans un nouvel onglet de la même fenêtre : la même fiche s'ouvre directement

### Suivre un cours
- [x] Axe *Groupes*, fiche d'`annotateurs` : le lien « Défini dans l'annuaire ↗ » ouvre l'annuaire dans un NOUVEL onglet, et l'onglet de l'application reste sur la fiche
- [x] Dans la section *Membres*, chaque compte porte « vu le JJ/MM » ou la pastille « aucune connexion » ; le titre de la section dit « Membres — N jamais venu(s) » quand au moins un membre porte cette pastille, et « Membres » seul sinon
- [x] Dans la section *Collections ouvertes*, les collections déjà ouvertes à ce groupe portent leurs actes en toutes lettres, puis vient « Ouvrir une collection à ce groupe » : une liste qui propose les mêmes collections que l'axe *Collections*, par ordre alphabétique, et un bouton « Régler qui entre… ». Aucune case à cocher, aucun niveau : rien ne s'accorde depuis cette fiche
- [x] Axe *Comptes* : le lien « + Dans l'annuaire ↗ » est en tête de liste ; axe *Collections* : il n'y est plus

### Lire une collection, et aller régler qui entre
- [x] Axe *Collections*, fiche de « Collection Test » : la section *Qui entre* liste `annotateurs` avec « lire » et `proprio` avec « tous les actes, dont décider qui entre », chacun avec 👥 ou 👤, sans aucune case à cocher — et une ligne dit que les accès se lisent ici et se règlent dans la fiche de la collection, dans la Bibliothèque
- [x] Cliquer un nom de *Qui entre* : la fiche de ce groupe ou de ce compte s'ouvre
- [x] Revenir sur « Collection Test », cliquer *Régler qui entre* : la Bibliothèque s'ouvre sur « Collection Test » dépliée, le focus clavier sur le titre « Qui entre » de la collection. Revenir à l'Administration pour la suite

### Ce qu'un départ laisserait
- [x] Axe *Comptes*, fiche de `stagiaire` : la partie *Départ* est REPLIÉE, et son titre porte une pastille « rien à orpheliner » ou « laisse … »
- [x] Déplier *Départ* : trois étapes — retirer ses accès à son nom, le retirer de ses groupes dans l'annuaire, le supprimer dans l'annuaire — et la troisième dit ce qui resterait à ce login, ou « rien à orpheliner ». Aucune ne dit « recommandé », « possible » ni « archives »
- [x] La première étape envoie au bon endroit : elle dit « dans « Qui entre » de chaque collection, dans la Bibliothèque », et compte les accès à son nom (ou dit qu'il n'en a aucun)

### Déclarer un login partagé — et remettre en état
- [x] Fiche de `collectif`, sélecteur *Nature* : le passer de « une personne » à « un login partagé ». Sous le sélecteur : « Nature enregistrée. », et le sélecteur garde le focus
- [x] Recharger la page (F5) : la fiche de `collectif` montre toujours « un login partagé »
- [x] Déplier « Ce que change un login partagé » : le texte cite l'accord inter-annotateurs, « collectif-N », les cinq minutes de Ctrl+Z, et qu'aucun droit d'accès n'en dépend
- [x] **Remise en état** : repasser le sélecteur à « une personne », « Nature enregistrée. » s'affiche, et après F5 il le reste

### Trier
- [x] Axe *Comptes*, « Récents d'abord » : les dates « vu le » décroissent de haut en bas, et toutes les lignes « aucune connexion » sont en fin de liste
- [x] Sans rien toucher d'autre, passer à l'axe *Groupes* : « Récents d'abord » est toujours enfoncé, les « actif le » décroissent, et « aucune venue » est en fin de liste
- [x] Axe *Collections* : les « modifiée le » décroissent, « jamais modifiée » en fin de liste ; F5 garde l'axe *Collections* et « Récents d'abord »
- [x] « A → Z » sur l'axe *Comptes* : ordre alphabétique des noms lisibles, accents compris (« Étudiant » range avec les E)

### Clavier, largeur, thèmes

**Les quatre cases de hauteur et de largeur supposent une pile reconstruite sur `c888740` ou
après** (2026-09-23). Avant `644d090`, le cadre suivait la longueur de la liste et plafonnait
à 80rem ; avant `c888740`, il se comptait depuis le haut de la PAGE et débordait d'une fenêtre
courte — défaut trouvé par Hugo en jouant cette passe, le 2026-09-23.

- [x] Au clavier seul : Tab jusqu'à la première ligne de la liste, `↓` passe à la suivante, `Fin` à la dernière, `Entrée` ouvre la fiche
- [x] Outils de développement, mode appareil à 375 px de large : la liste occupe le bloc ; choisir un compte fait apparaître sa fiche SEULE, avec « ← Liste » en tête ; « ← Liste » ramène la liste, focus sur la ligne choisie ; rien ne dépasse à droite
- [x] Fenêtre agrandie : passer de l'axe *Comptes* à l'axe *Collections*, qui compte moins de lignes — le cadre garde la même hauteur, et « Moteurs de reconnaissance », dessous, ne remonte pas
- [x] Mode appareil à 1280 × 500, la page amenée sur le titre « Comptes et groupes » : le bloc ENTIER tient dans la fenêtre — on voit le bas du cadre sans défiler davantage
- [x] Dans cette même fenêtre, la liste des comptes porte sa propre barre de défilement, et le cadre ne s'allonge pas pour les montrer tous
- [x] Fenêtre agrandie, la fiche de `lectrice` : *Groupes* et *Collections* côte à côte, sur une même ligne ; la fiche d'une collection : *Qui entre* sur toute la largeur de la fiche
- [x] Thème clair (🌙 → ☀) : « ⚠ À regarder », les pastilles « aucune connexion » (ambre) et « absent de l'annuaire » (rouge, s'il y en a) restent lisibles
- [x] Dans le bloc, aucun texte ne dit « principal », « genre » ni « utilisateur » — en particulier sur les fiches que la doublure des tests ne produit pas : un compte de l'annuaire (pastille « compte de l'annuaire », et aucune partie *Départ*), un groupe portant « rôle de l'annuaire », et toute pastille « absent de l'annuaire ». Les trois fiches ordinaires sont mesurées par `tests/test_e2e_qui_entre.py`
