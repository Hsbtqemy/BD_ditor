---
passe: Le formulaire de construction d'une grille
chantier: ANN-7
duree: 50 min
---

# QA — construire une grille au formulaire, la publier, l'employer, la retoucher

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur
`fcc3d67` ou après, état `apres-moustache` restauré (`C:\temp\bd-recette\etat-de-base.ps1
restaurer apres-moustache`). Les mots de passe sont dans `C:\temp\bd-recette\comptes.txt`,
hors dépôt. Tout se joue sous `proprio`, responsable de « Projet principal », dans une
fenêtre privée à 1 280 px de large, sauf mention contraire.

**Ce que la passe éprouve** — le formulaire de l'option HYBRIDE tranchée par Hugo sur
maquette le 2026-11-03 (`edc9ae7`) : trois colonnes de taille stable (le plan, la fiche et ses
questions, l'aperçu tel que la page Annotation le montre), chaque champ gardé quand on le
quitte, sans « Enregistrer », et une entrée employée qui se retire et ne se supprime jamais.

**Le décor de l'état restauré.** « Sons et images (fictive) » est la seule grille de « Projet
principal » : FERMÉE, v1 publiée et active ; son entrée « cri » porte 2 relevés. La passe crée
deux grilles, « Lieux QA » (fermée) et « Libre QA » (ouverte).

**Ce que la passe ne joue pas.** L'import d'un classeur et son bilan : `test_e2e_grilles_projet`
et la zone « Corriger dans le formulaire ↗ » ci-dessous seulement. Le masquage d'une grille par
collection n'a pas d'écran. Les choix à confirmer sont dans `pilotage/ANN-7.md`, case « Les
choix du formulaire de construction sont confirmés » : la passe les montre, elle ne les tranche
pas.

### Créer une grille fermée, sous `proprio`
- [x] *Administration › Projets › Projet principal*, bloc « Grilles » : « + Construire une grille » ouvre le formulaire, le champ du nom a le focus, et « Créer la grille » est éteint ; à côté, « Donnez-lui un nom. »
- [x] Taper « Lieux QA », Tab : « Créer la grille » reste éteint et dit « Dites sur quoi elle porte (B). » ; la question A, « Fermée ou ouverte ? », a « Fermée » coché
- [x] Question B, cocher « La case » : « Créer la grille » s'allume ; le cliquer : le titre devient « Lieux QA », l'adresse porte `&grille=`, et la tête dit « brouillon v1 »
- [x] Les trois colonnes sont là, le plan à gauche, la fiche au milieu, l'aperçu à droite ; cliquer tour à tour « Toute la grille » puis une rubrique (zone suivante) ne change la largeur d'aucune des trois

### Deux rubriques, deux entrées, sous `proprio`
- [x] « + Rubrique », taper « Intérieur », Tab : le nœud « Intérieur » paraît dans le plan, marqué comme courant, et « ✓ enregistré » s'affiche
- [x] « + Entrée » : tant que le nom est vide, les autres questions de l'entrée sont éteintes et la fiche dit « ● Donnez-lui un nom » ; taper « domicile », Tab : la fiche dit « Entrée · Intérieur » au-dessus du nom, et les questions s'allument
- [x] Cocher « Une variante parmi plusieurs » : la question dit « ● Ajoutez au moins une variante. », la ligne « domicile » du plan dit « ● à compléter », et « Publier la v1… » est éteint, la raison au survol
- [x] Dans le champ de variante neuve, « cuisine », Tab, puis « chambre », Tab : les deux variantes sont listées, le ● a disparu de la question et du plan, et l'aperçu montre « cuisine » et « chambre » sous « domicile »
- [x] Une fois ses variantes posées, les autres réponses de la question de forme de « domicile » sont éteintes, et leur survol dit pourquoi
- [x] « + Rubrique » « Extérieur », puis « + Entrée » « rue », et dans sa définition « une voie de la ville », Tab : l'aperçu montre les rubriques « Intérieur » puis « Extérieur », et son guide, sous la grille, la définition de « rue »
- [x] Aucune question n'a de paragraphe d'aide sous elle : l'aide se lit au survol de son titre (ⓘ ou infobulle)

### Publier, activer, employer, sous `proprio`
- [x] « Publier la v1… » (allumé) se confirme sur place, sans fenêtre ; confirmer : un message dit « La version 1 est publiée »
- [x] « Activer la v1 » : le message dit que la grille est active dans le projet ; la tête du formulaire dit « v1 publiée · un brouillon v2 naîtra au premier changement »
- [x] *Annotation* (nav 🖍️), un album de « Projet principal » (« esther v1 »), une planche, une case choisie : les onglets de la grille montrent « Lieux QA », et dans cet onglet « domicile » se déplie en « cuisine », « chambre »
- [x] Dans « Lieux QA », poser « rue » sur la case choisie : la ligne « rue » se lit dans « Ce qui est posé » (elle servira à la zone « Une entrée employée, grille fermée »)

### Réordonner, sous `proprio`
- [x] Revenir au formulaire de « Lieux QA » (*Administration › Projets › Projet principal*, « Modifier… » sur sa ligne). Cliquer « Intérieur » dans le plan, puis ↓ (« Descendre Intérieur ») : l'aperçu montre « Extérieur » puis « Intérieur », et la tête dit « brouillon v2 »
- [x] Le focus sur la ligne « Intérieur » du plan (Tab jusqu'à elle), Alt + ↑ : l'aperçu revient à « Intérieur » puis « Extérieur », et le focus est resté sur « Intérieur »
- [x] ↑ sur la première rubrique est éteint, et son survol dit « Déjà au bord »
- [x] Cliquer « Toute la grille » dans le plan : « Note de la v2 » est vide (la note de la v1 ne s'y recopie pas) ; y écrire « Intérieur d'abord », Tab, recharger la page : la note est restée
- [x] « ← Projet principal » en tête du formulaire : la fiche du projet revient, le focus sur « Modifier… » de « Lieux QA », et l'adresse ne porte plus `&grille=`

### Une entrée employée, grille fermée, sous `proprio`
- [x] « Modifier… » sur « Sons et images (fictive) » : la tête dit « v1 publiée · un brouillon v2 naîtra au premier changement »
- [x] Cliquer « cri » dans le plan : la fiche dit « 2 relevés la portent. » ; ses gestes offrent « Retirer », et NI « Supprimer l'entrée… » NI « Fusionner dans… »
- [x] Sur « cri », la question de forme et celle de la liste restent modifiables (la grille est fermée : le changement irait au brouillon) — ne rien changer
- [x] Cliquer une entrée que personne n'emploie (sans « relevé » dans sa fiche) : elle offre « Supprimer l'entrée… », et pas « Retirer »
- [x] Revenir sur « cri », « Retirer » : la fiche dit « Retirée : elle ne se pose plus ; 2 relevés la portent, à revoir. », offre « Remettre en usage », et la tête dit « brouillon v2 »
- [x] « Remettre en usage » : « Retirer » revient ; la v1 active n'a pas changé (sur la page Annotation, « cri » se pose toujours dans « Sons et images (fictive) »)

### Une entrée employée, grille ouverte, sous `proprio`
- [x] Bloc « Grilles », « + Construire une grille » : « Libre QA », « Ouverte », porte sur « La case », « Créer la grille » : la tête dit « ouverte · s'écrit en place »
- [x] « + Rubrique » « Sons », « + Entrée » « bruit », Tab ; « Activer dans le projet », en tête du formulaire (aucune publication : une ouverte n'a qu'une version) : un message dit qu'elle est active dans le projet
- [x] *Annotation*, la même case, onglet « Libre QA » : poser « bruit » ; revenir au formulaire de « Libre QA », cliquer « bruit » : la fiche dit « 1 relevé la porte. », ses gestes offrent « Retirer » ET « Fusionner dans… », et pas « Supprimer l'entrée… »
- [x] Sur « bruit », les réponses de la question de forme et de celle de la liste sont éteintes, et leur survol dit pourquoi
- [x] Sur une grille ouverte, la question A de « Toute la grille » est éteinte, et son survol dit « La nature d'une grille ne change pas après sa création. »

### Deux onglets sur la même entrée, sous `proprio`
- [x] Deux onglets de la même fenêtre sur le formulaire de « Lieux QA », « rue » choisie dans les deux. Onglet B : définition « l'autre », Tab. Onglet A : définition « la mienne », Tab : un bandeau « Définition modifiée » paraît au-dessus de la fiche, dit « Version enregistrée : l'autre », et le champ garde « la mienne »
- [x] Tant que le bandeau attend, changer un autre champ de l'onglet A puis le quitter : rien ne part (onglet B, rechargé, ne le montre pas)
- [x] Onglet A, « Remplacer par la mienne » : le bandeau disparaît ; onglet B rechargé montre « la mienne »

### « Corriger dans le formulaire ↗ », sous `proprio` (demande un tableur)
- [x] Bloc « Grilles », « ⤓ Tableur » sur « Lieux QA » : un `.xlsx` se télécharge. Dans le tableur, feuille des entrées, écrire « nuage » dans la colonne « 2. Se pose sur » de « rue » (la colonne avertit sans refuser : accepter l'avertissement), enregistrer en `.xlsx`
- [x] « ⤒ Réimporter… » sur « Lieux QA », choisir le fichier, « Vérifier » : le bilan dit une faute sur « rue », avec un bouton « Corriger dans le formulaire ↗ »
- [x] Le cliquer : le formulaire s'ouvre sur « Lieux QA », « rue » courante dans le plan et dans la fiche

### Étroit, grande police, clavier, sous `proprio`
- [x] Fenêtre réduite à 700 px de large : le formulaire est remplacé par « Le formulaire se sert sur un écran large : élargissez la fenêtre, ou réduisez le zoom. La grille se retouche aussi dans le tableur (⤓ Tableur). », sans défilement de côté ; revenue à 1 280 px, le formulaire revient tel qu'il était
- [x] À 1 280 px, « Aa » → la plus grande police : le formulaire tient sur trois colonnes, ou dit qu'il est trop étroit — noter lequel (le seuil est à 64rem de fiche, un choix à confirmer)
- [x] Au clavier seul : Tab atteint le plan ; ↓ ↑, Début et Fin s'y déplacent de ligne en ligne ; Entrée sur une ligne la rend courante ; Tab mène ensuite à la fiche puis à l'aperçu, sans piège
- [x] En thème clair puis sombre (*Aa*), le ● des attentes, les éteints et le bandeau de conflit se lisent
