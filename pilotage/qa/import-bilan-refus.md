---
passe: L'import de vocabulaire dit ce qu'il a refusé
chantier: AUTH-11
duree: 25 min
derniere: 2026-10-09
---

# QA — le bilan d'un import refusé se lit, et n'en dit pas plus que le serveur

`d2684b5` a changé ce que le panneau 📖 Lexique dit après un import : un toast de synthèse
par motif, une zone de bilan dans la modale, un menu « Importer dans » réduit aux
collections où l'on écrit. Six tests navigateur le verrouillent, mais tous tournent dans un
Chromium sans interface, à 1280 px, en thème clair. Personne n'a regardé ce bilan de ses
yeux, ni dans un autre thème, ni à 320 px, ni sous Firefox.

**Ce que les tests couvrent déjà — ne pas le refaire ici** : le texte exact de la synthèse
dans les trois cas, le compte des toasts, le menu filtré sous deux identités, le menu qui
garde son choix d'un import à l'autre, le bilan masqué après un import en échec, et le fait
que la synthèse ne contient rien d'autre que des chiffres, les deux motifs du serveur et
les phrases fixes du module.

**Ce qui se regarde ici** : les COULEURS du ton (un toast d'erreur qui avait l'air d'un
succès est précisément le défaut que ce commit a trouvé), la lisibilité du bilan dans les
thèmes et aux petites largeurs, et ce qu'on rencontre au clavier quand l'import est fermé.

**Où** — la pile de recette, `https://bd.127-0-0-1.sslip.io`, **reconstruite sur un HEAD
qui contient `d2684b5`** : sur un serveur plus ancien, aucune case ne mesure rien. La passe
suppose le décor de *Un terme qu'on ne lit pas ne se voit pas* (`termes-illisibles.md`) :
la dimension `ambiance-b` est LOCALE à « Étude B », que `stagiaire` ne lit pas ;
`stagiaire` écrit dans « Collection Test » ; `lectrice` ne fait que lire.

**Deux fichiers à préparer**, point-virgule, encodage UTF-8. `qa-partiel.csv` :

```
domaine;domaine_definition;cible;dimension;dimension_definition;dimension_note_portee;valeur;valeur_definition
;;case;axe-qa;;;valeur-qa;
;;case;ambiance-b;;;;
;;case;ambiance-b;;;calme;
```

`qa-refuse.csv` : le même en-tête et les deux lignes `ambiance-b` seulement.

**Une limite qui n'est pas une case** : le motif « en lecture seule pour vous » ne se
produit pas avec ce décor (il faut un terme local à une collection qu'on lit sans y
écrire). Les tests le couvrent ; ne pas le chercher ici.

**Le journal ne montre que ce chapeau, les titres de zone et les cases** (relevé le
2026-10-09, la passe ayant été jouée dans le journal et non dans ce fichier) : le compte et
le panneau de chaque zone sont donc dans son TITRE, et tout ce qui se prépare est ici.

- **L'import** se fait dans *Exploration → 📖 Lexique* — menu « Importer dans », bouton
  « Importer un tableur… », en bas de la fenêtre —, pas par « Importer des images » de
  l'Atelier.
- **Le ton** d'un import est porté par le TOAST, la petite boîte qui paraît dix secondes en
  bas à droite de la fenêtre du navigateur : un trait de 3 px à son bord gauche. La zone de
  bilan qui reste dans la fenêtre du lexique n'a pas de couleur.
- **Avant la première zone**, sous `proprio` : vérifier que `ambiance-b` est bien rangée
  dans « Étude B » (menu « Portée ») — globale, `stagiaire` la verrait et rien ne serait
  refusé.
- **Avant « Un rattachement refusé »**, sous `proprio`, même panneau : créer le domaine
  `champ-test` et le ranger dans Collection Test (menu « Portée ») ; puis passer `axe-qa` —
  née par l'import de la première zone — en « Global » si elle ne l'est pas. On a ainsi une
  dimension GLOBALE et un domaine LOCAL, tous deux visibles et modifiables par `stagiaire` :
  exactement le rattachement que la règle refuse.
- **Avant la première case du « sélecteur Portée »**, sous `proprio`, Bibliothèque →
  📚 Collections → « Étude B » → *Qui entre* : faire entrer `stagiaire` en lecture seule. Il
  lit alors `ambiance-b` sans y écrire. Lui retirer cet accès à la fin de la zone.
- **Pour finir, sous `proprio`** : supprimer `axe-qa`, la valeur `calme` et le domaine
  `champ-test`, pour rendre le décor.

## Constats de la passe du 2026-10-09

Jouée par Hugo sous Chrome et sous Firefox, sur la pile de recette (`22cc644`) : dix-neuf
cases sur vingt.

- **La case du clavier a ÉCHOUÉ, et pas seulement sous `lectrice`** : dès que le lexique
  porte un terme, Tab tournait sur trois arrêts — le champ « Nouveau domaine »,
  « + Domaine », le premier terme — et n'atteignait ni les autres termes, ni l'import, ni
  « Fermer ». Le piège à focus des modales ne connaissait pas `<summary>`. Corrigé par
  `240dde1` ; la case reste ouverte, à rejouer sur une recette qui le contient.
- **Le ton a été cherché au mauvais endroit**, dans la zone de bilan, qui n'en porte
  aucun : il n'est que sur le toast, qui disparaît en dix secondes. Les deux cases tiennent
  une fois le toast repéré ; la remarque reste, sans suite décidée.
- **Le journal ne donnait ni le compte ni le décor** : d'où le chapeau ci-dessus, et un
  premier import fait dans « Global » puis une zone jouée sous `proprio` au lieu de
  `stagiaire` (toasts verts sous Firefox). Sans dommage pour les cases, rejouées depuis.

## Reste

### Le ton se voit — sous `stagiaire`, Exploration → 📖 Lexique, « Importer dans » : Collection Test

- [x] Importer `qa-partiel.csv` : le toast dit « 2 lignes refusées : libellé déjà pris (2) », avec un liseré BLEU (neutre) — ni vert, ni rouge
- [x] Importer `qa-refuse.csv` : le toast commence par « Rien n'a été importé » et porte un liseré ROUGE, distinct au premier regard du toast de l'import précédent
- [x] Après chacun des deux imports, la zone de bilan de la modale donne une ligne par ligne refusée — deux, chacune avec son numéro de ligne dans le fichier et le libellé `ambiance-b` —, et aucune ne contient « Étude B », « caché » ni « collection »
- [x] Après les deux imports, « Importer dans » affiche toujours Collection Test, sans qu'on y ait touché

### Les thèmes et les largeurs — toujours sous `stagiaire`, en rejouant `qa-refuse.csv`

- [x] Thème SOMBRE : le toast rouge et le texte du bilan se lisent sans effort ; le liseré rouge reste distinct de celui d'un succès
- [x] Contraste ÉLEVÉ : même lecture, et le texte du bilan n'est pas plus pâle que le reste de la modale
- [x] Fenêtre à 320 px de large (outils de développement, mode appareil) : le bilan se replie sur plusieurs lignes, la modale ne défile pas en largeur, et la plus longue ligne du bilan se lit en entier, sans être coupée par le bord
- [x] Firefox, thème clair, 1280 px : le toast du fichier refusé est rouge et celui du fichier partiel bleu, comme sous Chrome

### Quand on n'écrit nulle part — sous `lectrice`, Exploration → 📖 Lexique

- [x] Ni menu « Importer dans » ni bouton « Importer un tableur… » : à leur place, la note « Vous n'écrivez dans aucune collection : l'import de vocabulaire vous est fermé » et l'invitation à demander un accès
- [ ] (échouée le 2026-10-09 sur `22cc644`, à rejouer sur une recette qui contient `240dde1`) Au clavier, en partant du haut de la modale, Tab parcourt les contrôles de la modale sans jamais s'arrêter sur un élément invisible ou inerte à l'endroit de l'import
- [x] Avec un lecteur d'écran (NVDA : flèche bas pour lire la modale ligne à ligne), la note est lue, en entier, à l'endroit où serait le menu

### Un rattachement refusé — sous `stagiaire`, Exploration → 📖 Lexique, une fois le décor monté sous `proprio`

- [x] Choisir `champ-test` dans le sélecteur de domaine d'`axe-qa` : un toast ROUGE dit « Rangez d'abord la dimension dans la collection du domaine », et nomme `champ-test` et rien d'autre
- [x] Juste après ce toast, sans recharger, le sélecteur de domaine d'`axe-qa` affiche de nouveau ce qu'il affichait avant le geste — pas `champ-test`
- [x] Recharger la page : `axe-qa` n'est toujours sous aucun domaine

### Le sélecteur « Portée » — sous `stagiaire`, même panneau

- [x] Ouvrir l'éditeur d'un terme d'Étude B que `stagiaire` lit sans y écrire — s'il n'en existe pas, passer cette case : son sélecteur « Portée » est grisé, affiche « Étude B », et le survol dit « En lecture seule pour vous »
- [x] Sur un terme de Collection Test, le menu « Portée » propose Global et Collection Test, et aucune collection où `stagiaire` n'écrit pas
- [x] Sous `proprio`, suivre le conseil du rattachement refusé plus haut : ranger `axe-qa` dans Collection Test, PUIS la rattacher à `champ-test` — les deux gestes passent, sans toast rouge
- [x] Sous `proprio`, ranger le domaine `champ-test` dans Étude B : après « Enregistré », le panneau se recharge, l'éditeur de `champ-test` est rouvert avec le curseur sur son sélecteur, et `axe-qa` — rangée sous lui dans Collection Test — affiche désormais Étude B, sans qu'on l'ait touchée. Ranger ensuite `champ-test` de nouveau dans Collection Test pour rendre le décor : `axe-qa` suit

### Ce que le propriétaire voit — sous `proprio`, même panneau

- [x] « Importer dans » propose Global, Collection Test ET Étude B
- [x] Importer `qa-refuse.csv` dans Étude B : aucune ligne refusée, le toast est VERT ; `calme` apparaît sous `ambiance-b` dans le lexique

