---
passe: Comptes et groupes
chantier: AUTH-12
duree: 30 min
derniere: —
---

# QA — « 👥 Comptes et groupes » : lire qui utilise l'instance, sans deviner

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur un
commit qui porte le bloc (`3eb52e8` ou après), avec la lecture de l'annuaire configurée (et non sa doublure).
L'annuaire est sur `https://annuaire.127-0-0-1.sslip.io`. Les mots de passe sont dans
`C:\temp\bd-recette\comptes.txt`, hors dépôt. Une fenêtre privée par identité.

**Ce que la passe éprouve.** Le bloc remplace « 👤 Comptes vus » : il LIT l'annuaire pour
montrer tous les comptes et groupes, venus ou non, et ce que chacun ouvre. Il ne modifie
rien, sauf la nature d'un compte. Les gestes joués sont ceux que la maquette validée faisait
jouer d'abord à l'administrateur : répondre à « je ne vois rien », suivre un cours, lire ce
qu'un départ laisserait.

**Ce que la passe ne joue pas, et où c'est éprouvé.** L'annuaire EN PANNE : l'arrêter
toucherait la pile, et c'est joué par `tests/test_e2e_comptes_groupes.py` (les trois états
de l'annuaire). Le regroupement de « À regarder » au-delà de cinq signaux du même code : la
recette n'a pas six arrivants, et c'est joué par le même fichier.

**Une case MODIFIE un compte existant** (la nature, zone « Déclarer un login partagé ») et le
remet dans son état : `collectif` porte le décor de la passe *Compte collectif*, qui exige
qu'il soit « une personne » au départ. Ne pas sauter la remise en état.

### Qui voit le bloc
- [ ] Sous `proprio`, *Administration* : aucun bloc « 👥 Comptes et groupes » sur la page, et aucun message d'erreur à sa place
- [ ] Sous `admin-bd`, *Administration* : le bloc « 👥 Comptes et groupes » est là, et la ligne sous son titre dit « Annuaire lu à HH:MM. », sans les mots « Doublure de test »

### Répondre à « je ne vois rien »
- [ ] Sous `admin-bd`, dans le filtre du bloc, taper `arriv` : la liste ne garde que la ligne d'`arrivant`. Cliquer dessus : sa fiche s'ouvre à droite, et l'adresse du navigateur se termine par `?compte=arrivant`
- [ ] Dans cette fiche, la section *Collections* ne liste aucune collection et dit « Aucune collection ne lui est ouverte : l'application lui montre un corpus vide. »
- [ ] Filtrer `lectrice`, ouvrir sa fiche : la section *Groupes* montre `annotateurs`, et la section *Collections* montre « Collection Test » avec « lecture — par le groupe annotateurs »
- [ ] Dans cette fiche, cliquer `annotateurs` : l'axe passe à *Groupes*, la fiche du groupe s'ouvre, et `lectrice` figure dans sa section *Membres*
- [ ] Bouton « Retour » du navigateur : la fiche de `lectrice` revient, axe *Comptes*
- [ ] Copier l'adresse du navigateur, l'ouvrir dans un nouvel onglet de la même fenêtre : la même fiche s'ouvre directement

### Suivre un cours
- [ ] Axe *Groupes*, fiche d'`annotateurs` : le lien « Défini dans l'annuaire ↗ » ouvre l'annuaire dans un NOUVEL onglet, et l'onglet de l'application reste sur la fiche
- [ ] Dans la section *Membres*, chaque compte porte « vu le JJ/MM » ou la pastille « aucune connexion » ; le titre de la section dit « Membres — N jamais venu(s) » quand au moins un membre porte cette pastille, et « Membres » seul sinon
- [ ] Dans la section *Collections ouvertes*, une phrase dit qu'ouvrir une collection à ce groupe se fera depuis la fiche de la collection, et qu'on le règle d'ici là dans « 👥 Accès aux collections »
- [ ] Axe *Comptes* : le lien « + Dans l'annuaire ↗ » est en tête de liste ; axe *Collections* : il n'y est plus

### Lire une collection, et aller régler qui entre
- [ ] Axe *Collections*, fiche de « Collection Test » : la section *Qui entre* liste `annotateurs` en « lecture » et `proprio` en « propriétaire », chacun avec 👥 ou 👤, sans aucune case à cocher
- [ ] Cliquer un nom de *Qui entre* : la fiche de ce groupe ou de ce compte s'ouvre
- [ ] Revenir sur « Collection Test », cliquer *Régler qui entre* : la page remonte au panneau « 👥 Accès aux collections », « Collection Test » y est dépliée, et le focus clavier est sur son titre

### Ce qu'un départ laisserait
- [ ] Axe *Comptes*, fiche de `stagiaire` : la partie *Départ* est REPLIÉE, et son titre porte une pastille « rien à orpheliner » ou « laisse … »
- [ ] Déplier *Départ* : trois étapes — retirer ses accès à son nom, le retirer de ses groupes dans l'annuaire, le supprimer dans l'annuaire — et la troisième dit ce qui resterait à ce login, ou « rien à orpheliner ». Aucune ne dit « recommandé », « possible » ni « archives »

### Déclarer un login partagé — et remettre en état
- [ ] Fiche de `collectif`, sélecteur *Nature* : le passer de « une personne » à « un login partagé ». Sous le sélecteur : « Nature enregistrée. », et le sélecteur garde le focus
- [ ] Recharger la page (F5) : la fiche de `collectif` montre toujours « un login partagé »
- [ ] Déplier « Ce que change un login partagé » : le texte cite l'accord inter-annotateurs, « collectif-N », les cinq minutes de Ctrl+Z, et qu'aucun droit d'accès n'en dépend
- [ ] **Remise en état** : repasser le sélecteur à « une personne », « Nature enregistrée. » s'affiche, et après F5 il le reste

### Trier
- [ ] Axe *Comptes*, « Récents d'abord » : les dates « vu le » décroissent de haut en bas, et toutes les lignes « aucune connexion » sont en fin de liste
- [ ] Sans rien toucher d'autre, passer à l'axe *Groupes* : « Récents d'abord » est toujours enfoncé, les « actif le » décroissent, et « aucune venue » est en fin de liste
- [ ] Axe *Collections* : les « modifiée le » décroissent, « jamais modifiée » en fin de liste ; F5 garde l'axe *Collections* et « Récents d'abord »
- [ ] « A → Z » sur l'axe *Comptes* : ordre alphabétique des noms lisibles, accents compris (« Étudiant » range avec les E)

### Clavier, largeur, thèmes
- [ ] Au clavier seul : Tab jusqu'à la première ligne de la liste, `↓` passe à la suivante, `Fin` à la dernière, `Entrée` ouvre la fiche
- [ ] Outils de développement, mode appareil à 375 px de large : la liste occupe le bloc ; choisir un compte fait apparaître sa fiche SEULE, avec « ← Liste » en tête ; « ← Liste » ramène la liste, focus sur la ligne choisie ; rien ne dépasse à droite
- [ ] Thème clair (🌙 → ☀) : « ⚠ À regarder », les pastilles « aucune connexion » (ambre) et « absent de l'annuaire » (rouge, s'il y en a) restent lisibles
- [ ] Dans le bloc « 👥 Comptes et groupes » SEULEMENT — le panneau « 👥 Accès aux collections » change à l'étape suivante —, aucun texte ne dit « principal », « genre » ni « utilisateur »
