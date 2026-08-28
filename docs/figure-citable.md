# Figure citable — citer n'est pas publier

> **DROIT-1 (2026-08-28).** Le chantier ne restreint presque rien : il rend POSSIBLE
> l'usage savant d'un corpus qu'on ne peut pas diffuser. `collection.statut_diffusion`
> existait depuis la v14 sans que rien ne le respecte ; il devient opposable **au seul
> endroit où la donnée sort**, et il y distingue deux gestes que rien ne rapproche.

## Le partage, en une phrase

**Publier**, c'est mettre un corpus à disposition. **Citer**, c'est extraire une case
identifiée pour l'accompagner d'un discours. Le premier geste porte sur une collection
entière et suppose d'en avoir le droit ; le second est l'usage même que la recherche
revendique — et un fonds sous droits est justement celui qu'on cite plutôt que de le
diffuser.

La ligne passe donc par la **nature de l'acte**, jamais par un volume. Un plafond (« vingt
figures par export ») serait un chiffre qu'on ne saurait pas justifier, et la fiche DROIT-1
met en garde contre le fait de coder une politique qu'on ne connaît pas encore : la base
légale du corpus n'est pas établie (DEPOT-1).

| | Publier | Citer |
|---|---|---|
| Porte sur | une collection | un extrait identifié |
| Artefact | manifeste IIIF, paquet de dépôt | figure + légende + notice |
| Régime | exige `public` **et** une collection **nommée** | ne bloque jamais, **accompagne** |
| Outil | `tools/iiif_manifest.py` | `POST /api/figures`, cœur `figure.py` |

## À l'intérieur de l'instance : rien ne change

`statut_diffusion` ne borde **rien** entre les murs. Qui est admis sur une collection en
reçoit tout, scans compris. Deux raisons, et la première suffit :

- **le travail d'annotation REPOSE sur les images** — border un membre reviendrait à
  l'empêcher de travailler, c'est-à-dire à annuler AUTH-3 pour ces collections ;
- l'usage interne relève de la recherche, avec ses droits de citation et de diffusion
  accompagnée.

Le cloisonnement entre équipes reste l'affaire d'AUTH-2 et AUTH-3 : *qui* voit *quel
corpus*. DROIT-1 ne s'y superpose pas.

## Ce que produit une figure

`POST /api/figures` renvoie un zip : par région, un PNG recadré dans le master, sa légende
prête à coller, et la même chose en JSON.

```
figures_20260828_143000.zip
├─ pl-3-c2.png     recadrage net dans le master (borné à 2000 px)
├─ pl-3-c2.txt     Tintin — Le Lotus bleu, Hergé, Casterman, 1936 —
│                  pl. 3 · c2 — Corpus : Étude coloniale —
│                  Licence du jeu enrichi : CC-BY-4.0 —
│                  Base légale : base légale non établie (cf. DEPOT-1) —
│                  Reproduction au titre de la courte citation, à fin
│                  d'illustration d'un propos scientifique. — Extrait le : 2026-08-28
└─ pl-3-c2.json    les mêmes champs, structurés, + region_id
```

**Le nom du fichier porte le repère, pas la clé primaire** : une figure se retrouve dans un
dossier de travail par ce qu'elle montre. Repli sur `region-<id>` quand la mention
`citation` n'a pas été demandée — un fichier doit rester nommé quoi qu'on ait coché.

### Pourquoi le paquet, et pas l'image seule

`GET /api/regions/{id}/crop` rendait déjà le PNG. Ce qui manquait n'est pas l'image, c'est
le **lien** entre l'image et sa référence : ce qui rend une citation défendable, c'est
qu'elle soit **courte, identifiée et accompagnée**. Livrer les trois séparément revient à
laisser recréditer à la main — et c'est à la main que l'accompagnement se perd.

### Les mentions sont choisies

Une légende d'article, une légende de diapositive et une notice de catalogue n'ont pas les
mêmes besoins. `champs` prend un sous-ensemble de `figure.CHAMPS` ; imposer un gabarit
obligerait à le retailler hors de l'outil, donc à en sortir, donc à perdre le lien.

L'**ordre**, en revanche, ne se choisit pas : il est bibliographique, celui de `CHAMPS`, et
non celui de la demande. Sans cela deux figures d'une même communication porteraient des
légendes de forme différente.

| Champ | Contenu |
|---|---|
| `titre` | série et titre de l'album |
| `auteur` | contributions N0 (`nom (rôle)`) si présentes, sinon `albums.auteur` *legacy* — jamais les deux |
| `editeur` · `annee` · `isbn` | l'édition détenue (`date_edition` prime sur `annee`) |
| `citation` | repère dérivé `pl. 3 · c2 · b1` (jamais stocké, cf. `docs/numerotation-et-citation.md`) |
| `collection` | corpus d'étude crédité — `collection_id` le désigne, un album vivant dans plusieurs |
| `licence` | licence du **jeu enrichi**, jamais celle de l'œuvre |
| `base_legale` | à quel titre le corpus est détenu |
| `mention_citation` | la formule de courte citation |
| `date_export` | date d'extraction |

**Un champ demandé mais vide ne produit rien** — une légende ne doit pas annoncer
« ISBN : » suivi du vide. Une seule exception, et elle est délibérée : `base_legale`
s'affiche même absente, sous la forme « base légale non établie (cf. DEPOT-1) ». C'est
aujourd'hui la vérité du dépôt, et la taire ferait passer pour réglé ce qui ne l'est pas —
sur l'artefact même qui sort de l'instance.

### Ce que la citation ne contourne pas

Le cloisonnement d'AUTH-2 s'applique entièrement : chaque région passe par l'accesseur
gardé, et une région hors portée est un 404 comme partout. Sans cette garde, la figure
serait devenue le trou par lequel tout le corpus se lit en images.

## Publier : le manifeste IIIF

C'est le seul artefact du dépôt qui émette des URL d'images vers l'extérieur — donc le seul
point où le régime devient opposable. La règle est **fail-closed** et tient en une phrase :

> **Publier suppose de nommer la collection qu'on publie.**

Sans `--collection`, l'outil porte sur le corpus entier, donc sur aucun régime déclaré, et
n'emporte aucune image. Cela règle du même coup le cas d'un album vivant dans plusieurs
collections (AUTH-3) sans inventer d'arbitrage : le régime qui s'applique est celui de la
collection **au nom de laquelle** on publie.

`--verbatim` (le texte OCR dans les annotations) est **refusé** hors `public` : publier le
texte d'une œuvre sous droits est de la diffusion, pas de la citation. Le message renvoie
vers le geste qui convient.

### Un manifeste amputé le déclare

Les Canvas **survivent** sans image : ils gardent leurs dimensions master et leurs
annotations de régions, si bien que la géométrie et l'enrichissement restent publiables.
C'est exactement le scénario de la piste A — déposer ouvertement son travail sur un fonds
qu'on ne peut pas diffuser.

Le manifeste porte alors un `requiredStatement` (que IIIF impose aux visionneuses
d'afficher) : *« Scans non diffusés »*. Le dire dans l'artefact plutôt que sur la console
n'est pas cosmétique — la console se perd au premier pipeline, le manifeste voyage avec les
données.

`tools/valider_iiif.py` n'exempte un Canvas vide **que** sur cette déclaration. La nuance
porte tout : sans elle, « ce manifeste retient ses images » et « ce manifeste a oublié ses
images » deviendraient indistinguables, et la règle cesserait de mesurer quoi que ce soit.

## Ce qui a changé ailleurs

**`GET /api/sauvegarde` est réservée aux administrateurs.** Elle déverse la base entière,
toutes collections confondues. L'arbitrage du 2026-08-27 la laissait ouverte à tout compte
et portait sa propre condition de réouverture — « dès qu'un tiering de droits est effectif
(DROIT-1), cette décision se rejoue » —, qui vient de se déclencher. Elle reste **entière**
(une sauvegarde partielle ne restaure pas une instance) et change de public : sauvegarder
est un geste d'exploitation, pas de recherche.

**La surcharge de droits par album est abandonnée par écrit.** Le dictionnaire l'annonçait ;
depuis AUTH-3 un album vit dans plusieurs collections, si bien qu'« un défaut Collection
surchargeable par Album » n'a plus de défaut unique à surcharger. Le besoin réel — un
corpus mêlant domaine public et œuvres sous droits — se traite en constituant deux
collections, sans dupliquer les albums.

## Ce que ce chantier ne fait pas

**Il ne remplace pas une base légale.** `base_legale` reste une question ouverte
(DEPOT-1) : le mécanisme est ici, la politique ne l'est pas. C'est délibéré — restreindre
selon une règle qu'on ne connaît pas revient à coder une politique inventée.

**Il ne rend pas l'instance étanche.** Comme AUTH-2, il protège de l'accident et de la
confusion, pas d'une exfiltration délibérée par quelqu'un qu'on a admis.
