# Ce qu'une grille peut demander

*Pour qui conçoit une grille d'annotation, avant de toucher au tableur. Cette page dit ce que
l'outil sait faire, ce que cela donne à l'écran, et ce qu'il ne sait pas faire. La façon de
l'écrire dans le fichier est ailleurs : [import-grille.md](import-grille.md).*

Une grille est une liste d'**entrées** : ce qu'on peut relever sur une planche. Poser une
entrée sur un endroit de la planche fait un **relevé**.

Tous les exemples viennent de la **Grille d'exemple**, fictive, que chaque bac à sable reçoit.
Le plus court chemin pour comprendre une ligne de cette page est de la poser là-bas :
ouvrez *Mon bac à sable*, puis la page Annotation.

## Deux choix pour toute la grille

- **Fermée ou ouverte ?** Une grille fermée change par versions : on la publie, et elle ne
  bouge plus. Une grille ouverte n'a qu'une version, qui s'enrichit pendant le travail : on tape
  un mot qu'elle n'a pas, et une entrée naît. Cette entrée est simple, sans rubrique, et
  personne ne lui a écrit de définition.
- **Sur quoi porte-t-elle d'ordinaire ?** Des mots, une zone, une case… C'est la réponse à la
  question 2 ci-dessous pour toutes les entrées qui ne disent pas la leur.

## Six questions, pour chaque entrée

| Question | Réponses possibles | À l'écran | À essayer |
|---|---|---|---|
| **1. Où se range-t-elle ?** | Une rubrique, sur autant de niveaux qu'il faut, ou aucune | Le plan de la grille, repliable | *Chocs*, sous *Bruits*, sous *A. Sons* |
| **2. Sur quoi se pose-t-elle ?** | Des mots · une zone entière (bulle, cartouche, texte hors bulle, boîte de personnage, détail d'image) · une case · la planche | On désigne des mots, ou on choisit la zone, et l'entrée porte dessus | *cri* sur des mots, *regard caméra* sur une case, *ambiance sonore* sur la planche |
| **3. Combien de fois ?** | Une seule fois par cible, ou plusieurs | « Une seule » : en choisir une autre remplace | *ton de voix*, une fois par zone |
| **4. Que choisit-on en la posant ?** | Rien · **une** variante · **zéro, une ou plusieurs** cases d'une liste | Les variantes ou les cases apparaissent sous l'entrée | *onomatopée de choc* (variantes), *origine du son* (cases) |
| **5. Faut-il écrire quelque chose ?** | Non, ou un champ libre, dont la grille donne le nom | Un champ sur la ligne du relevé | *origine du son*, champ « lieu » |
| **6. Faut-il désigner une autre zone ?** | Non, ou oui | « Désigner sur la planche », puis un clic sur l'autre zone | *réponse à une autre bulle* |

À chaque entrée, et à chaque variante, le guide peut joindre une définition, des exemples, une
structure et un piège : ce que l'annotateur lit au moment de choisir.

### Trois précisions qui décident souvent

- **Des mots, c'est dans UNE zone.** Ils peuvent être voisins ou non, mais un relevé ne court
  pas sur deux bulles. Si le phénomène en traverse deux : un relevé dans chacune, ou un lien
  (question 6).
- **Variantes ou cases : ce qu'on veut compter.** Un relevé compte toujours pour **une**
  occurrence de l'entrée, quel que soit le nombre de cases cochées. Si deux choix doivent
  compter pour deux, écrivez deux entrées, ou des variantes posées deux fois.
- **« Attendu » ne veut pas dire « obligatoire ».** Une variante se choisit forcément en
  posant. Mais un champ libre ou un lien manquant n'empêchent pas de poser : le relevé
  s'enregistre, marqué **à compléter**, et la Synthèse le rappelle.

## Le lien vers une autre zone

C'est la possibilité la moins évidente sur le papier. Ce qu'elle fait aujourd'hui :

- On pose d'abord l'entrée, puis, sur sa ligne, on désigne l'autre zone. Tant qu'elle n'est pas
  désignée, le relevé est à compléter.
- **Le départ** suit la question 2 : une zone entière, ou des mots.
- **L'arrivée** est toujours une zone entière, jamais des mots. Elle ne peut pas être la zone
  de départ.
- Un relevé porte **un seul** lien. Deux zones à désigner, ce sont deux relevés.
- On désigne sur **la planche ouverte**. Un lien vers une autre planche n'est pas offert à
  l'écran.
- La grille ne peut pas dire **quelle sorte** de zone viser : le oui vaut pour toutes.
- Le lien n'a **pas de sens** propre : c'est le nom de l'entrée qui dit ce qu'il signifie
  (« réponse à… »). Rien ne marque la zone d'arrivée comme répondant à quoi que ce soit.
- Si la zone liée disparaît, le relevé passe **à revoir**, et son texte reste lisible.

## Ce qu'une grille ne peut pas demander

- **Variantes et cases à la fois** : une entrée n'a qu'une forme.
- **Une question propre à une variante** : le champ libre, le lien, la cible et le nombre de
  fois se règlent sur l'entrée, pour toutes ses variantes.
- **Une règle entre deux entrées** : ni « si A, alors B », ni « A interdit B ».
- **Plusieurs champs libres**, ou un champ qui ne serait pas du texte : un champ par entrée,
  500 caractères, ni nombre, ni date, ni liste.
- **Le personnage partout** : une entrée peut se poser sur la boîte d'un personnage, dans une
  case, mais pas sur le personnage à travers tout l'album.
- **Mêler des mots et une zone** dans une même entrée : elle se pose sur des mots, ou sur des
  zones. Plusieurs sortes de zones se combinent, pas davantage.

Ce qui n'est pas dans ces deux listes n'existe pas : une grille ne peut rien demander d'autre.
Si l'analyse a besoin d'autre chose, c'est une évolution de l'outil, et elle se discute avant
d'écrire la grille.

**Les relevés restent dans l'instance pour l'instant** : ni grille ni relevé ne sortent encore
d'un export.
