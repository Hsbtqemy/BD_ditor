---
passe: L'import de vocabulaire dit ce qu'il a refusé
chantier: AUTH-11
duree: 25 min
derniere: —
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

### Le ton se voit

**Sous `stagiaire`**, *Exploration → 📖 Lexique*, « Importer dans » : Collection Test.

- [ ] Importer `qa-partiel.csv` : le toast dit « 2 lignes refusées : libellé déjà pris (2) », avec un liseré BLEU (neutre) — ni vert, ni rouge
- [ ] Importer `qa-refuse.csv` : le toast commence par « Rien n'a été importé » et porte un liseré ROUGE, distinct au premier regard du toast de l'import précédent
- [ ] Après chacun des deux imports, la zone de bilan de la modale donne une ligne par ligne refusée — deux, chacune avec son numéro de ligne dans le fichier et le libellé `ambiance-b` —, et aucune ne contient « Étude B », « caché » ni « collection »
- [ ] Après les deux imports, « Importer dans » affiche toujours Collection Test, sans qu'on y ait touché

### Les thèmes et les largeurs

**Toujours sous `stagiaire`**, en rejouant `qa-refuse.csv`. Le thème se change par la
bascule de la barre de navigation. Un défaut de thème se rapporte à `A11Y-*`, pas ici.

- [ ] Thème SOMBRE : le toast rouge et le texte du bilan se lisent sans effort ; le liseré rouge reste distinct de celui d'un succès
- [ ] Contraste ÉLEVÉ : même lecture, et le texte du bilan n'est pas plus pâle que le reste de la modale
- [ ] Fenêtre à 320 px de large (outils de développement, mode appareil) : le bilan se replie sur plusieurs lignes, la modale ne défile pas en largeur, et la plus longue ligne du bilan se lit en entier, sans être coupée par le bord
- [ ] Firefox, thème clair, 1280 px : le toast du fichier refusé est rouge et celui du fichier partiel bleu, comme sous Chrome

### Quand on n'écrit nulle part

**Sous `lectrice`**, *Exploration → 📖 Lexique*.

- [ ] Ni menu « Importer dans » ni bouton « Importer un tableur… » : à leur place, la note « Vous n'écrivez dans aucune collection : l'import de vocabulaire vous est fermé » et l'invitation à demander un accès
- [ ] Au clavier, en partant du haut de la modale, Tab parcourt les contrôles de la modale sans jamais s'arrêter sur un élément invisible ou inerte à l'endroit de l'import
- [ ] Avec un lecteur d'écran (NVDA : flèche bas pour lire la modale ligne à ligne), la note est lue, en entier, à l'endroit où serait le menu

### Un rattachement refusé

**Sous `stagiaire`**, *Exploration → 📖 Lexique*, sur une recette qui contient `bef0b83`.
Décor, sous `proprio`, dans le même panneau : créer le domaine `champ-test` et le ranger
dans Collection Test (menu « Portée ») ; puis passer la dimension `axe-qa` — née dans
Collection Test par l'import plus haut — en « Global » par son menu « Portée ». On a ainsi
une dimension GLOBALE et un domaine LOCAL, tous deux visibles et modifiables par
`stagiaire` : exactement le rattachement que la règle refuse.

- [ ] Choisir `champ-test` dans le sélecteur de domaine d'`axe-qa` : un toast ROUGE dit « Rangez d'abord la dimension dans la collection du domaine », et nomme `champ-test` et rien d'autre
- [ ] Juste après ce toast, sans recharger, le sélecteur de domaine d'`axe-qa` affiche de nouveau ce qu'il affichait avant le geste — pas `champ-test`
- [ ] Recharger la page : `axe-qa` n'est toujours sous aucun domaine

### Ce que le propriétaire voit

**Sous `proprio`**, même panneau — l'autre côté, sans quoi les cases précédentes pourraient
passer sur un écran simplement cassé.

- [ ] « Importer dans » propose Global, Collection Test ET Étude B
- [ ] Importer `qa-refuse.csv` dans Étude B : aucune ligne refusée, le toast est VERT ; `calme` apparaît sous `ambiance-b` dans le lexique

**Pour finir, sous `proprio`** : supprimer `axe-qa` (créée par `stagiaire` dans Collection
Test) et la valeur `calme`, pour rendre le décor.
