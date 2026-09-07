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

- [ ] Connecté comme `lectrice`, *Administration → 👥 Collections*, la collection se déplie et montre un bloc **Export de dépôt**
- [ ] Ce bloc porte les trois lignes — fiche de description, enregistrements, manifeste IIIF — et aucune n'est grisée
- [ ] La ligne **Déposer sur ShareDocs** est ABSENTE pour `lectrice`
- [ ] Connecté comme propriétaire, le même bloc porte EN PLUS la ligne de dépôt

### Ce qui sort est le bon fichier

- [ ] *Fiche de description → JSON* télécharge un fichier nommé `depot-description-c<id>-<date>-<heure>.json`
- [ ] Ce JSON ouvert, `identite.nom` porte le nom de la collection déployée, et `couverture.albums` compte ses albums à elle — pas ceux du corpus
- [ ] *Fiche de description → CSV* s'ouvre dans un tableur avec les accents corrects (é, à, œ), sans réglage d'encodage
- [ ] *Enregistrements → CSV (zip)* donne une archive dont chaque `.csv` s'ouvre lisiblement
- [ ] *Enregistrements → XLSX* ouvre un classeur à plusieurs onglets, dont `fiche` et `arbre` — ou affiche un message nommant `openpyxl` si l'extra n'est pas installé sur l'instance

### Le manifeste dit ce qu'il retient

- [ ] Sans rien saisir dans le champ d'adresse, *Manifeste IIIF → Télécharger* produit un fichier nommé `depot-iiif-apercu-…`, et non un refus
- [ ] L'`AVERTISSEMENTS.txt` de cet aperçu commence par « APERÇU » et dit quoi mettre dans le champ — l'adresse publique du dossier `derivatives/`, pas un « serveur IIIF »
- [ ] Avec une adresse renseignée, le nom du fichier ne contient plus `apercu`
- [ ] Avec une adresse, sur une collection NON déclarée `public`, l'archive contient `AVERTISSEMENTS.txt`
- [ ] Ce fichier nomme la cause exacte — « déclarée restreint », « embargo court jusqu'au … », « date d'embargo illisible » — et non un message générique
- [ ] Sur une collection déclarée `public` et hors embargo, l'archive ne contient PAS `AVERTISSEMENTS.txt`, et un `manifest-a*.json` porte des URL commençant par l'adresse saisie
- [ ] Cocher **avec le texte relevé** sur une collection non publique fait refuser le manifeste, avec un message qui propose de citer plutôt que de publier

### Le dépôt, et son compte

- [ ] Propriétaire, la ligne de dépôt propose les six artefacts, chacun d'un libellé distinct et lisible
- [ ] Un dépôt réussi affiche le chemin ET le compte Huma-Num employé
- [ ] Le compte affiché est bien celui attendu — le sien si une session personnelle est ouverte, `instance` sinon
- [ ] Un dossier inexistant ou en lecture seule affiche le message renvoyé par ShareDocs, pas « échec »

### Étroit, clavier, thèmes

- [ ] À 375 px de large, aucune ligne du bloc ne déborde horizontalement ; les libellés passent à la ligne
- [ ] Chaque bouton et chaque champ du bloc s'atteint à la tabulation, dans l'ordre visuel, avec un contour de focus visible
- [ ] En thème sombre comme en clair, un message d'erreur du bloc reste lisible et n'est pas signalé par la seule couleur
- [ ] Le champ d'adresse d'images et le sélecteur d'artefact portent un libellé annoncé par un lecteur d'écran
