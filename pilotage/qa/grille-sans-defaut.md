---
passe: Une grille qui ne pose rien par défaut
chantier: ANN-7
duree: 25 min
---

# QA — une grille naît sans dire où se posent ses entrées

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur `0181ba9`
(« ANN-7 : la case fautive du tableur devient enfin rouge dans Excel ») ou après, état `apres-moustache` restauré
(`C:\temp\bd-recette\etat-de-base.ps1 restaurer apres-moustache`). Les mots de passe sont dans
`C:\temp\bd-recette\comptes.txt`, hors dépôt. Tout se joue sous `proprio`, responsable de
« Projet principal », dans une fenêtre privée à 1 280 px de large. Le tableur demande Excel.

**Ce que la passe éprouve** — le cadrage `docs/ann7-grille-sans-defaut-cadrage.md` et les deux
réponses de Hugo du 2026-11-12 : une grille se crée par son nom et sa nature ; une entrée sans
cible attend au brouillon et retient la publication ; ne plus rien poser par défaut l'écrit sur les entrées
qui le suivaient ; dans une grille ouverte qui ne pose rien par défaut, une entrée qui naît à la pose prend la
cible de ce qu'on désigne.

**Le décor de l'état restauré.** « Sons et images (fictive) » est la grille de « Projet
principal » : fermée, v1 publiée, « Porte sur » des mots ; 6 de ses 10 entrées n'ont pas de
cible à elles et suivent cette réponse par défaut.

### Créer une grille qui ne pose rien par défaut, sous `proprio`
- [x] Administration → Projets → « Projet principal », bloc « Grilles », « + Construire une grille » : la fiche montre le nom et la question A, « Fermée ou ouverte ? », et aucune question B ; « Créer la grille » est éteint, son survol dit « Donnez-lui un nom. »
- [x] Taper « Sans réponse QA », Tab, « Créer la grille » : la tête dit « Sans réponse QA » sans « porte sur … » ; dans « Toute la grille », la question B a « Aucun par défaut » coché
- [x] « + Entrée » « escalier », Tab : la question 2 de l'entrée n'offre pas « Comme la grille », et porte le ● « Dites où elle se pose : la grille ne pose rien par défaut. » ; dans le plan, « escalier » dit « ● à compléter »
- [x] « Publier la v1… » est éteint, et son survol dit « 1 entrée à compléter, marquée ● dans le plan. »
- [x] Question 2 d'« escalier », « La case » : le ● disparaît, et « Publier la v1… » s'allume ; publier : la tête dit « v1 publiée · pas active »

### Ne plus rien poser par défaut sur une grille qui pose des mots, sous `proprio`
- [x] Formulaire de « Sons et images (fictive) », « Toute la grille » : la question B a « Des mots » coché ; cliquer « Aucun par défaut » : sous les choix, un cadre dit « « des mots » s'écrira sur 6 entrées qui le suivent : rien ne change pour elles. », avec « Ne plus rien poser par défaut » et « Annuler » ; la tête dit encore « porte sur des mots »
- [x] « Annuler » : le cadre disparaît, « Des mots » est de nouveau coché, la tête dit encore « porte sur des mots », et aucun brouillon n'est né
- [x] « Aucun par défaut », puis « Ne plus rien poser par défaut » : un brouillon v2 naît, la tête ne dit plus « porte sur … », et aucune entrée du plan n'est « à compléter »
- [x] Dans ce brouillon, l'entrée « cri » : sa question 2 a « Des mots » coché, et non « Comme la grille », qui n'est plus offert

### Le tableur, sous `proprio`
- [x] Bloc « Grilles », « ⤓ Tableur » sur « Sans réponse QA », ouvert dans Excel : feuille « 1. La grille », « Porte d'ordinaire sur » est vide, et son aide, colonne C, commence par « Facultatif »
- [ ] Feuille « 2. Les entrées », vider « 2. Se pose sur » d'« escalier » : la case devient rouge ; y remettre « la case » : elle redevient blanche
- [x] La vider de nouveau, enregistrer en `.xlsx` ; « ⤒ Réimporter… » sur « Sans réponse QA », « Vérifier » : le bilan dit une faute sur « escalier », « L'entrée ne dit pas où elle se pose, et la grille ne pose rien par défaut. », et « → répondez à sa question 2, ou donnez à la grille une réponse par défaut (feuille « 1. La grille ») »

### Une grille ouverte qui ne pose rien par défaut, dans la page Annotation, sous `proprio`
- [x] « + Construire une grille » : « Libre sans réponse QA », « Ouverte », « Créer la grille », puis « Activer dans le projet » : un message dit qu'elle est active dans le projet
- [x] Page Annotation, sur une planche de « Projet principal » dont une bulle porte un texte : l'onglet « Libre sans réponse QA », choisir cette bulle, désigner un mot sous l'image, taper « rire » dans « Chercher dans la grille… », cliquer « Créer « rire » » : un relevé « rire » est posé sur ce mot
- [x] Sur la même bulle, Échap pour ne désigner aucun mot, taper « ambiance », « Créer « ambiance » » : un relevé « ambiance » est posé sur toute la bulle
- [x] Retour au formulaire de « Libre sans réponse QA » : la question 2 de « rire » a « Des mots » coché ; celle d'« ambiance » a « Une zone entière », « bulle » seule cochée
