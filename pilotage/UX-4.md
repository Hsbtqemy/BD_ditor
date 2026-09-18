---
chantier: UX-4
statut: différé
---

# UX-4 — cohérence visuelle inter-surfaces

**Arrêté sur** — 2026-09-14, `55b0e18` : l'état ÉTEINT d'un bouton se voit enfin. Trois
familles sur quatre — `ghost`, `icon-btn`, `danger` — étaient indistinguables de leur jumeau
actif, `.primary` étant la seule servie ; elles reprennent sa valeur. C'est le PREMIER commit
de code du chantier et il ne ferme aucune case : le statut passe à `interrompu` parce que
`à venir` décrit une fiche qui n'a pas commencé, et que l'outil dément mécaniquement un
`à venir` portant des commits de code. (Ce statut a changé le 2026-09-18 — voir ci-dessous ;
la phrase reste telle quelle, elle date la décision du 14.)

**La direction visuelle est TRANCHÉE le 2026-09-18** — maquette du jour, **direction D**,
choisie par Hugo. Quatre directions lui ont été montrées, construites sur le contenu RÉEL du
bloc « Qui entre » : **A « Sobre »** (l'existant, discipliné), **B « Éditoriale »** (le
tableau respire, les messages en colonne latérale, les titres en serif), **C « Panneaux »**
(une fiche par accès, les quatre actes liés tenus en UNE case). Il a demandé « un truc entre
A et B » ; **D** est née de cette demande, et c'est elle qu'il retient.

**Ce que D prend à B.** Le papier chaud, les titres en serif (Spectral) sur une interface en
sans (IBM Plex Sans), le filet sous l'en-tête, et le RYTHME des lignes — 14 px au lieu de 11.
C'est cette respiration qui fait l'essentiel de l'effet, davantage que la couleur ou la
fonte : à savoir avant de chiffrer le chantier, parce qu'elle se voit plus qu'un changement
de palette et coûte moins cher.

**Ce que D garde de A.** Un cadre qui fait du bloc une unité, la bande teintée sur les actes
liés, et les messages DANS le flux. **La colonne latérale de B est écartée**, et la raison
vaut d'être gardée : elle ne survit pas sous 48em et demanderait une seconde conception pour
l'étroit — alors que l'écran en a déjà une, les cartes de l'étape 3 d'`AUTH-12`. Une
direction qui oblige à dessiner deux fois le même écran se paie à chaque retouche.

**Ce que D invente.** Les messages deviennent des filets de couleur en marge au lieu
d'encadrés pleins : la hiérarchie se garde, le poids d'alerte disparaît.

**Acquis indépendamment du choix**, les quatre directions le portaient : les emoji remplacés
par des icônes dessinées, les dates en chiffres tabulaires, et un vrai bouton NOMMÉ pour le
retrait.

**Le statut passe donc à `différé`, et pas à autre chose.** Il n'y a pas une ligne de code :
Hugo a choisi une DIRECTION, il n'a pas ouvert le chantier. `livré` déclarerait une
intégration qui n'existe pas, et `à venir` reste démenti par le commit de code du 14. Ce qui
rouvrira la fiche n'est pas un autre chantier mais **deux décisions qui ne sont pas prises** :
dans quel ORDRE les surfaces s'alignent, et ce qu'on fait des panneaux de l'Administration.
Tant qu'elles manquent, écrire du code reviendrait à les trancher en passant.

**Ce que D fait aux cases de « L'alignement des cinq surfaces » : elle y RÉPOND, elle ne les
remplace pas.** La première demande que les quatre autres surfaces suivent l'Exploration ; ce
qui est tranché aujourd'hui, c'est VERS QUOI elles vont. Les cases restent telles quelles, et
se cocheront sur du code — aucune n'est ajoutée ici, puisque rien n'est ouvert.

**Point de départ** — l'Exploration a été soignée récemment et sert de référence ; les
QUATRE autres surfaces ne s'y sont jamais alignées. Elles étaient trois quand cette fiche
a été écrite : `/administration` est arrivée depuis (UX-10, 2026-09-07), et elle est la
plus jeune donc la moins alignée.

## Reste

### L'alignement des cinq surfaces
- [ ] Les espacements et la typographie de Recherche, Bibliothèque, Atelier et Administration suivent ceux de l'Exploration, sans valeur en dur qui contourne les tokens de `static/style.css`
- [ ] Un même composant (bouton, champ, pastille, panneau) a la même apparence sur les cinq surfaces
- [ ] **L'Administration est reprise en priorité** : ses panneaux ont été construits pour FONCTIONNER, l'un après l'autre et par des chantiers différents (INFRA-10, AUTH-3/AUTH-7, SANTE-1, EXP-1), sans qu'aucun ne réponde de l'ensemble. Attendu : les quatre panneaux se lisent comme une même page, et non comme quatre écrans empilés
- [ ] L'audit axe (`pytest -m e2e`) reste sans violation sérieuse ou critique sur les cinq surfaces et les deux thèmes après réalignement
- [ ] Aucun petit texte coloré n'utilise un accent brut : les tokens d'encre AA-sûrs sont respectés (règle d'accessibilité de CLAUDE.md)

### Le panneau des accès se lit comme un tableau
- [ ] La liste des accès d'une collection est un `<table class="corpus-table">` dans un `.table-cadre`, comme les quatre autres tableaux larges du dépôt — dont celui des comptes, sur la MÊME page : « peut exporter » et « groupe / utilisateur » s'écrivent une fois en `<th scope="col">` au lieu d'une fois par ligne
- [ ] Le `<details>` par collection RESTE, et le tableau vit dedans : c'est un dépliant, pas une ligne, et trois audits attendent `#col-body .col-item`
- [ ] La ligne d'ajout devient un `<tfoot>` dont les champs tombent sous leurs colonnes — c'est elle qui débordait de 89 px à 375 et de 144 à 320, et son `flex-wrap` de rattrapage est documenté dans `style.css` à `.contrib-add`
- [ ] `date_creation` devient une colonne « Depuis le », tronquée à dix caractères comme `derniere_vue` dans la table des comptes : `_acces_de` la renvoie déjà et l'écran n'en rendait rien
- [ ] `jamais_vu` devient une colonne « Signal », la même que la septième colonne de la table des comptes, et ses TROIS états survivent — marqueur si vrai, rien si faux, rien non plus pour un groupe, parce que l'application ne peut pas le savoir
- [ ] Les `aria-label` fabriqués par concaténation (« Niveau de X », « X peut exporter ») disparaissent au profit des en-têtes de colonne croisés avec un `<th scope="row">` portant le principal
- [ ] Les sélecteurs épinglés par les audits survivent à la restructuration **sans devenir creux** : `#col-body .col-item`, `.col-principal` (le champ de la ligne d'ajout, pas la cellule d'une ligne d'accès), `.acces-jamais-vu`, `input[data-export][data-principal]`
- [ ] `test_e2e_reflow` et l'audit axe repassent sur le tableau ENCADRÉ des accès — `.qe-cadre`, dans la Bibliothèque : un tableau ENCADRÉ est conforme au 1.4.10, qui tolère le défilement horizontal d'un contenu à deux dimensions, mais le cadre porte `tabindex="0"` et un `role="region"` étiqueté — sans quoi la zone défilante ne s'atteint pas au clavier. **Le cadre a déménagé avec l'étape 3 d'`AUTH-12` (`6ea6b60`) : il ne vit plus dans `/administration`, et c'est dans la fiche de la collection qu'il s'éprouve désormais**
- [ ] **Ce que la ligne d'accès devient sous le seuil étroit est DÉCIDÉ, pas hérité** — et la case ci-dessus ne suffit pas à l'obtenir : un tableau qui défile latéralement la passe en étant tout aussi pénible. Relevé à 375 px le 2026-09-13, sur l'état actuel : `.acces-liste li` est un `flex` à `flex-wrap` dont tous les enfants sont FRÈRES, donc ils passent à la ligne un par un sans regroupement — le ✕ se retrouve seul sur sa ligne, la case d'export glisse sous le sélecteur au lieu de rester avec lui, et la ligne d'ajout se disloque de même. Rien ne déborde, l'audit de reflow est vert, et c'est illisible quand même. Attendu : dire ce qu'une ligne devient sous le seuil — tableau défilant dans son cadre, ou retour en blocs empilés reprenant les en-têtes — et l'éprouver à 375 ET à 320, sur une collection qui a au moins trois accès
- [ ] Le tableau fini ne porte **aucune colonne d'identité** — ni nom lisible, ni dernière visite, ni nombre d'actes (raison en Contexte : la réserve est écrite, et le cliquet ne la défendrait pas)
- [ ] Le `<select>` de niveau reste tel quel, et la colonne « Niveau » est faite pour pouvoir changer SEULE : la rendre en cases à cocher appartient à `AUTH-10`, sur lequel l'équipe a décidé le 2026-09-10 de ne rien engager

  **Renvoi vers `AUTH-12`, posé le 2026-09-18 : l'écran a DÉPASSÉ cette case, qui reste une trace et n'est pas réécrite.** Le `<select>` de niveau n'existe plus. « Qui entre » (`6ea6b60`) rend les droits en ACTES cochables — *lire*, *annoter*, *organiser les albums*, *gérer le vocabulaire*, *lancer la reconnaissance automatique*, *décider qui entre*, plus *exporter* hors rang —, et le panneau qui portait cette colonne a quitté l'Administration pour la Bibliothèque. Ce que la case gardait en réserve est donc arrivé, mais par `AUTH-12` et non par `AUTH-10` : la décision du 2026-09-10 de ne rien engager sur `AUTH-10` n'a pas été rouverte, et la prévoyance de cette case — « la colonne est faite pour pouvoir changer SEULE » — s'est vérifiée. Elle garde son intérêt comme trace de ce qui avait été anticipé, et à quel prix ; lui faire dire aujourd'hui ce qu'elle ne disait pas la détruirait comme trace sans rien apprendre à personne

### Le menu d'export annonce ce qu'il va faire
- [ ] **Les trois formats d'export de l'Atelier ont le même effet apparent, ou le disent.** Mesuré le 2026-09-13 pendant la recette : « Export CSV » et « Export TEI P5 » posent un `Content-Disposition: attachment` et TÉLÉCHARGENT (`album_2_c2.csv`, `album_2_tei.xml`) ; « Export JSON-LD » n'en pose aucun et AFFICHE le JSON dans un onglet. Les trois boutons se suivent dans le même menu, sous le même intertitre, et rien ne distingue leur effet avant le clic — relevé par l'équipe, qui a cru à une panne. Attendu : soit la route JSON pose l'en-tête comme ses deux voisines, soit les libellés disent lequel ouvre et lesquels téléchargent
- [ ] **Le choix ne doit pas aveugler le cliquet de `tests/test_droit_export.py`.** Il repère les portes de sortie par leur source ET par leur chemin PRÉCISÉMENT parce que l'export JSON d'un album ne pose aucun en-tête de pièce jointe : c'est le contre-exemple qui justifie la double détection. Poser cet en-tête le ferait disparaître, et une détection par en-tête seul redeviendrait plausible — donc fausse le jour de la porte suivante. À vérifier AVANT de trancher, pas après
- [ ] **Le menu lui-même porte le mauvais nom dans les passes de QA**, et c'est un signe : il s'appelle « ⇅ Import / Export », « Exporter » n'y étant qu'un intertitre non cliquable. `pilotage/qa/droit-export.md` l'annonçait comme « menu ☰ », qui n'existe qu'en largeur de téléphone et pour tout autre chose. Attendu : les passes nomment les contrôles comme l'écran les nomme
- [ ] **Trancher le sort de « 💾 Sauvegarde (.sqlite) », quatrième entrée du même groupe.** Relevé en recette le 2026-09-13 sous un compte stagiaire : les trois formats cèdent la place à « Exporter : droit manquant… », elle reste. Mesuré — `#btn-backup` n'est câblé qu'une fois dans tout `static/` (`viewer.js`), sans aucune lecture de droits, et le serveur refuse par un 403 NOMMÉ (réservée aux administrateurs, `DROIT-1`). Les deux côtés se défendent, d'où une décision et non un correctif : `AUTH-2` accepte que l'UI découvre un refus en recevant son 403 — `peut_ecrire` ne traverse même pas jusqu'au client ; mais le principe de ce menu-ci était « une entrée qui DIT pourquoi, plutôt qu'un bouton qui disparaît », et l'écran offre ici un geste qui n'aboutira pas, à côté de trois qui s'expliquent. Attendu : ou bien elle se comporte comme ses voisines, ou bien la doctrine est ÉCRITE pour que la question ne se rouvre pas — aucune décision n'existe aujourd'hui, ni dans `pilotage/` ni dans `docs/`, vérifié
- [ ] **Et sa PLACE est la même question, posée autrement** : le tableau d'inventaire de `DROIT-2` situe cette porte dans l'Administration — « Sauvegarde · Administration · toute la base · administrateurs » — alors qu'elle vit aussi sous l'intertitre « Exporter » de l'Atelier. L'inventaire écrit et l'écran ne disent pas la même chose ; l'un des deux doit céder. Le coût de la faire disparaître de l'Atelier est connu : `viewer.js` ne lit aucune identité aujourd'hui, mais `/api/moi` porte déjà `acces.groupes_admin` et `common.identite()` existe

### L'Exploration elle-même, et sa concordance alignée
- [ ] La colonne de tags n'introduit plus une SECONDE fonte dans la ligne : le texte KWIC est en `ui-monospace` (`.kwic-aligned`), les pastilles en `"Segoe UI", system-ui` (`.kw-tags`), et les deux se lisent côte à côte sur la même ligne
- [ ] Le rythme vertical ne casse plus sur les seules lignes taguées : l'écart entre lignes vaut `.2308rem` quand les pastilles portent leur propre rembourrage, si bien qu'une ligne avec tags est plus haute que ses voisines nues. Attendu : une hauteur de ligne stable, taguée ou non
- [ ] Les lignes se distinguent les unes des autres AU REPOS, et pas seulement au survol — `.kwic-aligned .kwic-row:hover > span` en est aujourd'hui la seule séparation, sur des lignes serrées à trois pixels d'intervalle
- [ ] Ce que devient une bulle qui revient PLUSIEURS fois est décidé : `hom*` rend sept occurrences dont trois viennent de la même bulle, qui répète à l'identique son jeu de trois pastilles. Attendu : dire si l'on assume la répétition (une ligne = une occurrence, les pastilles sont celles de sa région) ou si on l'atténue — et l'écrire, parce que c'est un choix de lecture et non un défaut

### L'état ÉTEINT d'un bouton se voit
- [ ] Une garde retient l'écart : un bouton `disabled` diffère VISIBLEMENT de son jumeau
      actif, pour les quatre familles et dans les deux thèmes. Rien ne le retient
      aujourd'hui — les deux seules assertions du dépôt sur cet état sont de COMPORTEMENT
      (`is_disabled`, `to_be_disabled`), et une règle CSS retirée par mégarde ne ferait
      tomber aucun test
- [ ] Tranché : `.dropdown-menu button:disabled` garde `opacity: .55` et `cursor: default`
      là où la maison dit désormais `.45` et `not-allowed`. Deux valeurs pour le même état
      dans la même feuille, chacune avec son intention écrite — ou bien elles s'unifient,
      ou bien la raison de les distinguer est écrite à côté des deux
- [ ] Vérifié à l'écran, dans les deux thèmes : `opacity: .45` sur `.danger`, texte blanc
      sur fond rouge, reste lisible. Le 1.4.3 exempte les contrôles désactivés, donc l'audit
      axe ne le dira jamais — c'est une lecture humaine ou rien
- [ ] Ce que pose le commentaire de `majBoutonCasse()` est vérifié plutôt que supposé : il
      affirme que Chrome supprime l'infobulle d'un contrôle `disabled`, et c'est la raison
      ÉCRITE de faire porter le sens au libellé. L'équipe a pourtant vu l'infobulle changer
      le 2026-09-14. Si elle s'affiche, la conclusion tient toujours — un libellé porteur
      vaut mieux qu'une infobulle — mais elle ne tient plus par cette raison-là

## Contexte

Effort M, priorité P3. Les deux cases d'accessibilité sont là parce que c'est
exactement le genre de chantier qui casse l'accessibilité sans le vouloir : réaligner des
couleurs « pour que ce soit cohérent » est la manière la plus rapide de réintroduire un
accent brut sur du petit texte, ce que le dépôt a déjà corrigé une fois.

À traiter avec UX-3, mêmes fichiers.

**L'Administration entre dans le périmètre le 2026-09-08**, sur un constat d'usage énoncé
pendant EXP-1 : *« il faudra certainement reprendre l'esthétique de cette page à l'avenir,
mais pour l'instant, on vise le fonctionnel »*. C'est un arbitrage, pas un oubli, et il
mérite d'être écrit ici plutôt que de se perdre — une intention de ce genre s'évapore
exactement comme les fiches périmées se fabriquent.

La cause est structurelle et vaut d'être notée : cette page est la seule dont les blocs
ont été posés par des chantiers SÉPARÉS, chacun ajoutant le sien sans que personne ne
réponde de l'ensemble. La version servie (INFRA-10), les collections et la vue des comptes
(AUTH-3, AUTH-7), les moteurs (SANTE-1), l'export de dépôt (EXP-1) — cinq origines, cinq
mises en forme locales. Les autres surfaces ont été dessinées d'un tenant.

## Le panneau des accès — ce qui a décidé la forme, le 2026-09-13

**D'où vient la demande.** Pendant la recette de `DROIT-2`, en regardant le panneau :
« on pourrait organiser plutôt en mode tableau et aligné ? ça permettrait de ne pas mettre
les descriptions à côté, mais au-dessus, et ne pas répéter les éléments. » C'est exactement
ce que cette fiche demande à l'Administration — se lire comme une page et non comme quatre
écrans empilés —, et le panneau des accès est le seul des quatre à ne pas déjà le faire :
la vue des comptes, dix centimètres plus bas, est un `corpus-table` à sept colonnes.

**Ce que la mise en tableau échange.** Aujourd'hui les lignes passent à la ligne
(`flex-wrap`) et restent lisibles à l'étroit, au prix d'un libellé « peut exporter »
répété autant de fois qu'il y a d'accès. Un tableau aligne au large et défile latéralement
dans son cadre à 320 px. Pour un panneau d'administration, l'alignement a été préféré —
et le défilement encadré est la voie que `tests/test_e2e_reflow.py` classe déjà conforme,
le 1.4.10 tolérant explicitement ce cas pour un contenu à deux dimensions.

**Pourquoi aucune colonne d'identité, et pourquoi ça mérite d'être écrit ici.** La
docstring de `liste_comptes` refuse déjà de joindre le nom lisible ou la dernière visite à
un propriétaire de collection : « il n'y gagnerait rien qu'il ne sache déjà (il choisit qui
il ajoute) et y verrait la composition d'équipes qui ne sont pas la sienne ». Ce panneau
est vu par des propriétaires, pas seulement par des administrateurs. **Et le cliquet des
sorties d'identité ne le dirait pas** : `/api/collections/{id}/acces` ne figure ni dans
`SORTIES_DECLAREES` ni dans `NON_BALAYE` de `tests/test_sorties_identite.py` — elle est
balayée, mais le semis n'insère aucune ligne `collection_acces`, donc la réponse est vide
et la surface passe pour muette. C'est le mode d'échec que `AUTH-5` s'écrit à elle-même.
Une colonne d'identité ajoutée ici n'allumerait donc **aucun rouge** : si le besoin revient,
elle se déclare à la main ET le semis se complète.

**Ce qui attend d'atterrir dans ce tableau**, et qui justifie de prévoir la colonne
« Signal » plutôt que de la découvrir après : deux cases ouvertes d'`AUTH-6` — une
collection dont l'unique propriétaire perd son groupe doit être signalée, et un groupe
renommé ou supprimé dans l'annuaire doit échouer en disant « je n'ai pas pu vérifier »
plutôt qu'en déclarant l'accès mort. Les deux sont bloquées sur la même décision non
prise, celle de faire lire l'annuaire à l'application — qui donnerait aussi
l'autocomplétion du champ « Login ou nom de groupe », aujourd'hui un champ libre où une
faute de frappe et un arrivant produisent la même absence.

**Repéré en chemin et laissé hors périmètre** : rien n'avertit AVANT qu'on s'apprête à
retirer le dernier propriétaire d'une collection. `_compte_proprietaires` existe côté
serveur, mais ne sert qu'à refuser en 409 une fois le geste fait. C'est un défaut
d'`AUTH-3`, pas de cohérence visuelle, et le noter ici plutôt que l'y coder est
délibéré.

## L'Exploration entre à son tour dans le périmètre — 2026-09-14

**Constat d'usage énoncé pendant la recette d'ANA-6**, en regardant la concordance alignée
rendre `hom*` : « il faudra reprendre l'esthétique également ». Écrit ici pour exactement la
même raison que l'Administration le 2026-09-08 — une intention de ce genre s'évapore.

**Mais celle-ci ne s'AJOUTE pas à la liste, elle en corrige la PRÉMISSE.** Le point de départ
de cette fiche pose que « l'Exploration a été soignée récemment et sert de référence », et la
première case du Reste en découle directement : aligner Recherche, Bibliothèque, Atelier et
Administration SUR l'Exploration. Si sa concordance est elle-même à reprendre, on alignerait
quatre surfaces sur un étalon qu'on n'a pas revérifié.

Le point de départ n'est pas réécrit : il est daté, et il décrivait l'état d'alors. C'est
cette section qui le nuance et la zone ci-dessus qui en tire les cases. **Conséquence
d'ORDRE, et c'est le seul vrai changement** : « L'Exploration elle-même » se traite AVANT la
première case de « L'alignement des cinq surfaces », sans quoi l'alignement propagerait ce
qu'on vient de relever.

**Les quatre constats ont été confirmés un par un par l'équipe**, et chacun se vérifie dans
`static/style.css` au lieu de rester une impression : deux fontes dans la même ligne, un
rythme vertical qui ne casse que sur les lignes taguées, aucune séparation au repos, et la
répétition du jeu de pastilles pour une bulle qui revient. Le quatrième est le seul qui
puisse se conclure par « on assume » — les trois autres sont des écarts, pas des arbitrages.

**Ce qui n'est PAS touché ici**, et qui attend une décision : la première case de
« L'alignement des cinq surfaces » dit toujours « suivent ceux de l'Exploration », sans
réserve. La corriger changerait le périmètre d'une case ouverte, ce qui appartient à l'équipe
et non à cette note.

## Un état de bouton qui ne se voyait pas — 2026-09-14

**Relevé par l'équipe en jouant `qa/normaliser-casse`** : « quand tu dis "éteint", ça ne veut
pas dire grand-chose visuellement. Il n'y a pas de changement de couleur ou de grisage. Juste
le tooltip qui change. » La passe portait exactement cette case dans sa zone « Clavier,
thèmes » — elle a fait son travail, et c'est la deuxième fois en deux jours qu'une passe
rapporte ce qu'aucune suite ne voit.

**Trois familles sur quatre étaient indistinguables**, mesuré sur un banc isolé comparant les
styles CALCULÉS d'un bouton et de son jumeau désactivé : `ghost`, `icon-btn` et `danger`
rendaient la même couleur, la même bordure, `opacity: 1` et `cursor: pointer`, dans les deux
thèmes. `.primary` était la seule famille servie.

**La cause éclaire le chantier autant que le défaut.** Ce n'est pas un grisage oublié mais un
grisage ÉCRASÉ : ces classes posent `color` en dur, ce qui l'emporte sur le rendu par défaut
du navigateur. Un bouton SANS règle de couleur se grise tout seul — c'est le cas des entrées
de menu déroulant. Le défaut ne frappe donc que les familles STYLÉES, et il ne se voit pas en
relisant la feuille, puisque la règle fautive est celle qui MANQUE. Une revue de CSS ne
trouve pas ce genre de chose ; un banc qui compare deux états, oui.

**Et « cohérence inter-surfaces » ne le décrit pas, ce qui valait d'ouvrir une zone.** Le
défaut était uniforme sur les cinq surfaces : elles étaient cohéremment fautives. Ce qui est
réparé ici est une incohérence INTERNE au système de composants — une famille sur quatre
avait sa règle d'état. La case « un même composant a la même apparence sur les cinq
surfaces » ne l'aurait jamais attrapé.

**Le pire cas n'était pas celui qui a été signalé** : `#btn-export` de la Recherche et
`#btn-export-analyse` de l'Exploration naissent `disabled` DANS le gabarit. C'était l'état
initial de deux surfaces sur cinq, et non un cas de bord atteint après quelques gestes.

## Renvoi vers AUTH-12 — 2026-09-16

**Le panneau des accès est l'écran que le cadrage de la gestion des comptes transforme** :
un choix dans l'annuaire au lieu d'un champ libre, des accès en actes liés, et peut-être un
déménagement dans la collection de la Bibliothèque (décision 2 d'`AUTH-12`). La décision du
2026-09-13 de cette fiche — le tableau, aucune colonne d'identité, la colonne « Signal » —
vaut dans chacune des formes qu'`AUTH-12` décrit. Ces formes — une liste et une fiche côte à
côte, des onglets, une page par objet — se choisiront sur des maquettes interactives, et la
forme retenue doit être celle que ce chantier étend à l'Administration, pas un sixième
style. Refaire le tableau des accès avant ces décisions ferait refaire le travail.

**Tranché le 2026-09-17.** La forme est la liste et la fiche côte à côte (2026-09-16). Hugo a
retenu le déménagement (décision 2 (b)) : les accès d'UNE collection passeront dans sa fiche,
dans la Bibliothèque, et c'est à ce geste que la refonte du tableau se joint. Le principal se
choisira dans une liste de l'annuaire, groupes en tête, avec une saisie libre signalée
(décision 4 (2)). Rien n'est à faire ici avant la lecture de l'annuaire d'`AUTH-6`.

## Ce que l'étape 3 d'AUTH-12 a fait de la zone « Le panneau des accès se lit comme un tableau » — 2026-09-18

Relu sur le code de `6ea6b60`, à la demande de la coordination, **par LECTURE seule et sans
qu'aucune case soit cochée** : une case cochée sur lecture dirait qu'un geste a été joué
quand personne ne l'a joué. Trois réponses possibles pour chacune — (a) l'étape 3 la
satisfait, (b) elle l'a rendue caduque autrement, (c) elle demande encore un geste. Le
panneau a déménagé : tout ce qui suit vit dans `static/corpus.js`, dans la fiche de la
collection, et non plus dans l'Administration.

- **Le tableau dans son cadre** — (a). `qeTableauHtml` rend un `<table class="corpus-table
  qe-table">` dans un `<div class="table-cadre qe-cadre">`, et « exporter » comme le genre
  s'écrivent une fois en `<th scope="col">`.
- **Le `<details>` par collection reste** — (a). `colItem` le construit, « Qui entre » vit
  dans son `.col-detail`, et `#col-body .col-item` reste l'ancre des audits — dans la
  Bibliothèque désormais (`templates/corpus.html`).
- **La ligne d'ajout devient un `<tfoot>`** — (c), et c'est la seule de la zone qui n'a pas
  été faite. `qeAjoutHtml` rend un `<div class="qe-ajout-ligne">` SOUS le tableau, hors de
  lui : ses champs ne tombent donc pas sous leurs colonnes. Le débordement qui motivait le
  `<tfoot>` a été traité autrement (le cadre défilant, et une liste déroulante qui rétrécit
  à 320 px) ; reste à décider si la forme `<tfoot>` est encore voulue, ou si elle tombe avec
  sa raison.
- **« Depuis le »** — (a). `qeDepuis` tronque `date_creation` à dix caractères ; la colonne
  existe dans le tableau, et la carte la dit en toutes lettres sous 48em.
- **« Signal » et ses trois états** — (a) pour la propriété, (b) pour son point de
  comparaison. `qeSignal` marque si `jamais_vu` est vrai, ne dit rien s'il est faux, et rien
  non plus pour un groupe — parce que le serveur rend `jamais_vu: null` sur un groupe
  (`_acces_de`), et que l'écran teste `=== true`. En revanche la « septième colonne de la
  table des comptes », qui servait d'étalon, n'existe plus : cette table a été remplacée par
  une fiche (`3eb52e8`) et sa route retirée (`bfb9d32`).
- **Les `aria-label` concaténés remplacés par des en-têtes croisés** — (a) dans le tableau,
  (b) sous le seuil étroit, (c) pour ce qui compte vraiment. Les deux libellés que la case
  nommait ont disparu : chaque case croise un `<th scope="row">` portant le principal avec
  les en-têtes de ses colonnes, par `aria-labelledby`. Sous 48em il n'y a plus de tableau
  mais des cartes, où le croisement se fait vers le nom et le libellé — la propriété tient,
  la forme `th scope="row"` n'y a plus de sens. Un `aria-label` concaténé subsiste sur le
  bouton ✕ (« Retirer l'accès de … ») : la case ne le nommait pas, et un bouton ne peut pas
  s'en passer. **Ce qu'aucune lecture n'établit** : qu'un lecteur d'écran ÉNONCE réellement
  la liaison. Cela se joue sous NVDA, et personne ne l'a fait.
- **Les sélecteurs épinglés survivent sans devenir creux** — (a) pour deux, (b) pour un, et
  un reste à trancher. `#col-body .col-item` et `.acces-jamais-vu` sont toujours épinglés
  (`tests/test_e2e_a11y.py`). `input[data-export][data-principal]` n'existe plus nulle part,
  ni dans le code ni dans les tests : il est devenu
  `input.qe-case[data-hors-rang="exporter"][data-principal]`, et les tests ont suivi dans le
  même commit — donc caduc, sans le sélecteur creux que la case redoutait, ce qui est
  exactement ce qu'elle demandait. Reste `.col-principal` : la classe survit sur le champ de
  la ligne d'ajout, mais **plus aucun test ne l'épingle et aucune règle de `style.css` ne
  l'emploie**. C'est le risque inverse de celui que la case visait — non pas un sélecteur qui
  ne trouve rien, mais une classe que rien ne réclame. À retirer, ou à ré-épingler.

**Les trois dernières cases de la zone ne sont pas relues ici** : ce que la ligne devient
sous le seuil étroit demande une mesure à 375 et 320 px, l'absence de colonne d'identité est
une réserve à vérifier sur le tableau fini, et le `<select>` de niveau a déjà son renvoi du
même jour.
