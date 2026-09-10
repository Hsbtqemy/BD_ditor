---
passe: Export de dépôt depuis l'écran
chantier: EXP-1
duree: 25 min
---

# QA — l'export de dépôt, et la garde qui ne doit pas glisser

Le serveur est verrouillé par 29 tests et trois passes de mutation ; ce que la suite ne
peut pas voir, c'est **qui a le bloc sous les yeux**. C'est précisément là qu'AUTH-4 s'est
fait prendre : le référent d'une collection, une simple adresse, s'était retrouvé derrière
la garde du PARTAGE parce qu'il vivait dans un panneau gardé. L'erreur échoue en se
FERMANT — elle ne casse aucun test, et une revue de sécurité l'approuve.

Deux droits distincts cohabitent ici, et la passe existe pour les voir séparément :

- **lire** la collection suffit à TÉLÉCHARGER ;
- **la posséder** est exigé pour DÉPOSER sur ShareDocs.

Elle se rejoue à chaque fois que `colDetail` change de structure, qu'un format s'ajoute, ou
qu'une garde se déplace dans `routes/depot.py` ou `main.deposer_export`.

**Elle se joue EN LOCAL, sur une base jetable — pas sur le VPS.** La zone qui compte
demande de voir l'écran sous DEUX identités, ce que le mono-poste ne permet pas : sans
proxy la portée est totale, donc tout est administrable et la garde ne se voit jamais.
`tools/faux_proxy_auth.py` existe pour cet angle mort précis.

**Décor** (une fois, ~5 min). En PowerShell — les commandes du docstring de l'outil sont
en syntaxe bash, où `VAR=x commande` marche ; ici il faut poser les variables d'abord :

```powershell
$env:BD_DATA_DIR = "C:\temp\qa-depot"; $env:BD_DB_PATH = "C:\temp\qa-depot\demo.sqlite"
python tools/semer_demo.py                     # corpus jetable : albums, planches, texte
$env:BD_AUTH_PROXY = "1"
$env:BD_AUTH_LOGOUT_URL = "http://127.0.0.1:8002/_connexion"
python -m uvicorn main:app --port 8003          # l'application, derrière le drapeau
```

Puis, dans un SECOND terminal, `python tools/faux_proxy_auth.py`, et
<http://127.0.0.1:8002/_connexion> pour choisir qui l'on est.

Deux identités suffisent, et elles sont les deux côtés de la garde :

| Identité | Ce qu'elle est | Ce qu'elle doit voir |
|---|---|---|
| `claire` | groupe `chercheurs`, un accès **lecture** accordé | le bloc d'export, **sans** la ligne de dépôt |
| `admin` | `bd-admins` | le bloc **et** la ligne de dépôt |

L'accès de `claire` se pose sous `admin`, dans *Administration → 👥 Collections* : déplier
une collection, `claire` / utilisateur / lecture. Pour la voir en PROPRIÉTAIRE plutôt qu'en
administratrice, faites-lui créer sa propre collection depuis son identité — le créateur en
devient propriétaire, et la ligne de dépôt doit y apparaître.

⚠ `faux_proxy_auth.py` n'authentifie personne : il pose l'identité qu'on lui demande,
`bd-admins` comprise. Il n'écoute que sur `127.0.0.1`, et cela ne suffit pas à le rendre
inoffensif ailleurs.

### Le bloc est là pour qui LIT

- [x] Connecté comme `claire`, *Administration → 👥 Collections*, la collection se déplie et montre un bloc **Export de dépôt**
- [x] Ce bloc porte les trois lignes — fiche de description, enregistrements, manifeste IIIF — et aucune n'est grisée
- [x] La ligne **Déposer sur ShareDocs** est ABSENTE pour `claire`
- [x] Connecté comme propriétaire, le même bloc porte EN PLUS la ligne de dépôt

### Ce qui sort est le bon fichier

**Sous `claire`** — lire doit suffire à TÉLÉCHARGER, et c'est cette moitié de la garde qu'on
éprouve ici. **Une exception** : la case `couverture.albums` ne discrimine rien sous `claire`,
sa portée se confondant avec la collection — un export qui ignorerait `collection_id` et
déverserait le corpus rendrait le même chiffre. Elle se joue sous **`admin`**, et seulement
une fois qu'une DEUXIÈME collection existe.

- [x] *Fiche de description → JSON* télécharge un fichier nommé `depot-description-c<id>-<date>-<heure>.json`
- [x] Ce JSON ouvert, `identite.nom` porte le nom de la collection déployée, et `couverture.albums` compte ses albums à elle — pas ceux du corpus
- [x] *Fiche de description → CSV* s'ouvre dans un tableur avec les accents corrects (é, à, œ), sans réglage d'encodage
- [x] *Enregistrements → CSV (zip)* donne une archive dont chaque `.csv` s'ouvre lisiblement
- [x] *Enregistrements → XLSX* ouvre un classeur à plusieurs onglets, dont `fiche` et `arbre` — ou affiche un message nommant `openpyxl` si l'extra n'est pas installé sur l'instance

### Le manifeste dit ce qu'il retient

**Sous `claire`** — c'est le même droit que la zone précédente, le téléchargement.

**L'adresse à saisir**, pour les cases qui en demandent une :
`https://sharedocs.huma-num.fr/bdediteur/derivatives`. Deux valeurs sont à ÉVITER, et
aucune des deux ne se devine — `diagnostic_base_url` les traite à part. Un hôte local
(`127.0.0.1`, `localhost`, `*.local`) ajoute un constat « hôte local », donc un
`AVERTISSEMENTS.txt` **même sur une collection publique** : la case suivante paraîtrait
alors échouer sans défaut. Et `https://exemple.org/iiif` EST le placeholder : il est
refusé dès que le manifeste est destiné à être remis.

- [x] Sans rien saisir dans le champ d'adresse, *Manifeste IIIF → Télécharger* produit un fichier nommé `depot-iiif-apercu-…`, et non un refus
- [x] L'`AVERTISSEMENTS.txt` de cet aperçu commence par « APERÇU » et dit quoi mettre dans le champ — l'adresse publique du dossier `derivatives/`, pas un « serveur IIIF »
- [x] Avec une adresse renseignée, le nom du fichier ne contient plus `apercu`
- [x] Avec une adresse, sur une collection NON déclarée `public`, l'archive contient `AVERTISSEMENTS.txt` — **le manifeste amputé DIT qu'il l'est**. DROIT-1 ferme par défaut : sans régime `public`, les images ne partent pas, les Canvas si. Sans cette annonce, « j'ai retenu mes images » et « j'ai perdu mes images » seraient indistinguables — et `valider_iiif.py` n'exempte un manifeste de l'exigence d'images QUE s'il porte `« Scans non diffusés »` dans son `requiredStatement`. Le fichier du zip est le même geste, pour l'humain qui l'ouvre
- [x] Ce fichier nomme la cause EXACTE, et non un message générique. **Cinq sont possibles**, et le décor décide laquelle : « déclarée `<statut>` » ; « déclarée `<statut>`, et son embargo court jusqu'au … » ; « déclare une date d'embargo illisible (…, attendu AAAA-MM-JJ) » ; « ne déclare aucun régime de diffusion » — celui d'une collection dont `statut_diffusion` est vide, donc d'une base de démonstration ; « aucune collection n'est nommée ». Cette case en énumérait TROIS jusqu'au 2026-09-10, et les deux manquantes étaient justement celles qu'une base neuve produit : une énumération incomplète fait lire un échec là où le message est exact
- [x] Sur une collection déclarée `public` et hors embargo, l'archive ne contient PAS `AVERTISSEMENTS.txt`, et un `manifest-a*.json` porte des URL commençant par l'adresse saisie
- [x] Cocher **avec le texte relevé** sur une collection non publique fait refuser le manifeste, avec un message qui propose de citer plutôt que de publier

### Le dépôt, et son compte

**Sous propriétaire**, donc `claire` sur SA collection — déposer exige de POSSÉDER, pas de
lire, et c'est l'autre moitié de la garde. Sans identifiants Huma-Num sous la main, seules
les trois premières cases se cochent : laisser les autres vides et le DIRE, une case non
cochée faute de décor n'étant pas un échec.

- [x] Sans session ShareDocs ouverte, la ligne de dépôt n'offre PAS de bouton mais un lien « Se connecter à ShareDocs… », et une phrase qui dit qu'aucune session n'est ouverte
- [ ] Ce lien ouvre l'Atelier avec la modale de connexion DÉJÀ dépliée, et un bouton « ← Retour » visible en haut
      *(Non cochée le 2026-09-10, et le défaut est CONNU : la modale est un piège à focus, `#back-link` vit
      dans le bandeau de la page, donc il est derrière elle. La sortie n'est pas un secret — la modale porte
      un `Fermer ✕` —, mais elle demande deux clics et le premier parle de la BOÎTE, pas du TRAJET. Non
      réparé exprès : la deuxième case de SHARE-2 supprime l'aller-retour lui-même, en ouvrant la session
      depuis Administration. **Cette note se RETIRE le jour où SHARE-2 aboutit** — la case redeviendra soit
      vraie, soit sans objet.)*
- [x] « ← Retour » ramène bien sur *Administration*, et non sur la page précédente au hasard
- [x] Une fois connecté, la ligne de dépôt montre le compte employé et retrouve son sélecteur et son bouton
- [x] Propriétaire, la ligne de dépôt propose les six artefacts, chacun d'un libellé distinct et lisible
- [x] Un dépôt réussi affiche le chemin ET le compte Huma-Num employé
- [x] Le compte affiché est bien celui attendu — le sien si une session personnelle est ouverte, `instance` sinon
- [x] Un dossier INEXISTANT affiche un message qui NOMME le dossier en cause, dit que le dépôt ne crée aucun dossier manquant, et rappelle qu'on attend un chemin relatif — pas un « 404 » nu
- [ ] Un dossier en LECTURE SEULE affiche le message de ShareDocs sur le dossier non inscriptible, distinct du précédent
      *(NON TESTABLE le 2026-09-10, faute de décor et non par échec : le compte d'essai a l'écriture partout
      dans `@Shares`. Ce qu'il faudrait pour la jouer — un partage ouvert en lecture seule, ou un montage de
      type `tools`. À NE PAS confondre avec `@Shares` lui-même, essayé ce jour-là : point de montage virtuel,
      ShareDocs y répond **500** et non 403, donc c'est le catch-all `status >= 400` qui parle et la case
      n'est pas exercée.)*

### Étroit, clavier, thèmes

**Sous l'identité qui voit le bloc le plus COMPLET** — propriétaire ou `admin` : la ligne de
dépôt doit être à l'écran pour qu'on mesure sa largeur, sa tabulation et ses contrastes.

- [x] À 375 px de large, aucune ligne du bloc ne déborde horizontalement ; les libellés passent à la ligne
- [x] Chaque bouton et chaque champ du bloc s'atteint à la tabulation, dans l'ordre visuel, avec un contour de focus visible
- [x] En thème sombre comme en clair, un message d'erreur du bloc reste lisible et n'est pas signalé par la seule couleur
- [x] Le champ d'adresse d'images et le sélecteur d'artefact portent un libellé annoncé par un lecteur d'écran
