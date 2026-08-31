# Dossier — établir la base légale du corpus (DEPOT-1, AUTH-1)

> **À quoi sert ce document.** Il rassemble ce qu'il faut savoir de l'outil pour répondre à
> une seule question : **à quel titre détenons-nous ces données, et que pouvons-nous en
> faire sortir ?** Il est fait pour être porté à un interlocuteur compétent — service
> juridique, référent science ouverte, direction de l'unité — qui ne connaît pas l'outil.
>
> **Deux corps de questions, et un seul dossier** (depuis le 2026-08-31). Les unes portent
> sur les ŒUVRES — à quel titre les détenons-nous, que peut-on en publier (DEPOT-1). Les
> autres portent sur les PERSONNES qui les annotent : l'outil tient un fichier de noms et
> d'adresses, et un journal nominatif de leurs gestes (AUTH-1, § 1 et questions 9 à 12).
> Elles s'adressent peut-être à un interlocuteur différent — un délégué à la protection des
> données plutôt qu'un responsable des droits — mais elles se posent au même moment, sur le
> même outil, et les séparer en deux dossiers ferait tenir deux fois la même réunion.
>
> **Ce qu'il n'est pas.** Il ne conclut rien. L'exception de fouille de textes et de données
> (directive 2019/790, art. 3) y est nommée comme **piste à vérifier**, jamais comme
> réponse : le dépôt s'interdit depuis le 2026-07-16 de coder une politique qu'il ne connaît
> pas, et cette prudence vaut aussi pour la prose.
>
> Suivi : `pilotage/DEPOT-1.md`. Doctrine des droits : `docs/dictionnaire-metadonnees.md`.

---

## 1. Ce que l'outil détient

Outil de recherche pour annoter des bandes dessinées numérisées (corpus franco-belge),
**auto-hébergé, traitement entièrement local, aucune donnée envoyée à un tiers**. Aucune IA
dans la boucle d'annotation : le travail interprétatif est humain, les moteurs
d'apprentissage ne font que du **pré-remplissage éditable** et n'écrasent jamais une
correction humaine.

Trois natures de données coexistent, et la distinction est celle qui compte juridiquement.

| Nature | Contenu | Où |
|---|---|---|
| **L'œuvre reproduite** | scans master (TIFF) et leur dérivé web (JPEG à 25 %) | `corpus/`, `derivatives/` |
| **L'expression de l'œuvre** | le **texte des dialogues**, saisi par OCR puis corrigé à la main (« verbatim ») | `regions.ocr_texte` |
| **Le travail de recherche** | géométrie des cases et bulles, ordre de lecture, découpage éditorial, tags, notes, lemmes / catégories grammaticales / morphologie, personnages et leurs alignements sur des référentiels d'autorité, journal de provenance | tables d'enrichissement |

Le **journal de provenance** (append-only) enregistre qui a produit quoi : chaque acte
d'annotation porte son agent — une personne identifiée, ou un moteur avec sa version. Il
est sérialisable en PROV-O et en TEI. C'est la pièce qui permet de démontrer, le cas
échéant, la nature et l'ampleur du travail humain apporté.

### Une quatrième nature : les données personnelles de l'ÉQUIPE

Les trois natures ci-dessus portent sur le corpus. Il en existe une quatrième, ajoutée à ce
dossier le 2026-08-31 parce qu'elle en était absente : **l'outil détient un fichier de
personnes.** Ce n'est pas une question de droit d'auteur mais de RGPD, et l'interlocuteur
n'est peut-être pas le même — un délégué à la protection des données plutôt qu'un
responsable des droits.

| Donnée | Contenu | Où | D'où elle vient |
|---|---|---|---|
| **Identité de l'annotateur** | login, nom affiché, **adresse électronique** | `utilisateur` (v22) | recopiée des en-têtes posés par le proxy d'auth (Authelia) à chaque passage |
| **Traces d'activité nominatives** | qui a fait quel geste, quand, avec l'avant/après | `evenement`, `activite` (journal A3) | écrites à chaque acte |
| **Traces nominatives dérivées** | qui a corrigé quel mot, qui détient un verrou | `token_correction.auteur`, `planches.verrou_par` | idem |

Quatre points de fait, qui bordent la question sans la trancher :

- **Aucun secret n'est stocké** : ni mot de passe, ni jeton, ni empreinte. L'application
  n'authentifie personne — elle fait confiance au proxy. Un test refuse toute colonne de ce
  genre.
- **L'appartenance aux groupes n'est JAMAIS stockée** : elle est relue dans les en-têtes à
  chaque requête, si bien qu'un retrait dans l'annuaire prend effet immédiatement. Il n'y a
  donc rien à effacer de ce côté.
- **Le journal est append-only par construction** : c'est ce qui fait sa valeur probatoire
  (§ 1) et, en même temps, ce qui rend l'effacement d'une personne non trivial. Les deux
  tiennent ensemble, et c'est la difficulté.
- **Depuis le 2026-08-31, l'identité ne SORT plus** : tout artefact destiné au dépôt
  remplace l'agent humain par un pseudonyme stable (`annotateur-1`…), les moteurs gardant
  leur nom. Le nom et l'adresse ne quittent l'instance que par la **sauvegarde**, réservée
  aux administrateurs. Ce n'est pas de l'anonymisation — dans une petite équipe, l'ordre
  d'arrivée et le volume de travail réidentifient — mais la surface est réduite au minimum
  connu, et un cliquet de test la maintient (`tests/test_sorties_identite.py`).

---

## 2. Ce qui peut en sortir, et par quel geste

C'est le point central : **l'outil distingue quatre sorties, qui n'engagent pas la même
chose.** Aucune n'est automatique — chacune suppose un geste délibéré.

### a. PUBLIER — le manifeste IIIF, destiné à l'entrepôt

Ce qu'on dépose à Nakala : le manifeste et ses Canvas, c'est-à-dire **la géométrie et
l'enrichissement**, bien plus que les planches elles-mêmes. Les images ne sortent que d'une
collection **déclarée `public` et nommée explicitement** ; à défaut, le manifeste est écrit
sans elles et le **déclare** dans l'artefact (un lecteur doit pouvoir distinguer « ce
manifeste retient ses images » de « ce manifeste les a oubliées »). Le texte verbatim n'y
entre que sur demande expresse, et cette demande est **refusée** hors collection publique.

### b. CITER — la figure accompagnée

Un extrait (une case, une bulle) part avec sa référence, la responsabilité, l'édition, la
licence du jeu enrichi et **la base légale du corpus** — y compris la mention « base légale
non établie » tant que c'est le cas. Ce geste n'est **jamais bloqué** par le régime de
diffusion : le régime l'**accompagne**. C'est l'arbitrage interne du projet, et il repose
sur l'hypothèse que citer relève d'un régime distinct de diffuser — **c'est l'une des
questions posées au § 4.**

### c. DÉCRIRE — notices et crosswalks

Fiche de description de la collection, notices Dublin Core et DataCite, indicateurs de
couverture et de provenance. **Le texte verbatim n'y entre jamais.**

### d. EXPORTER un album — et c'est ici qu'il faut être précis

Trois formats par album (JSON-LD, CSV, TEI) **emportent le texte OCR verbatim**. Ils ne sont
bornés **que par l'admission** sur la collection, pas par le régime de diffusion. De même,
la sauvegarde intégrale de la base est téléchargeable — réservée aux administrateurs.

Autrement dit : **toute personne admise sur une collection peut en extraire les images et
le texte intégral.** Ce n'est pas un oubli, c'est l'arbitrage du 2026-08-28 — le travail
d'annotation repose sur les images, et border un membre reviendrait à l'empêcher de
travailler. Le cloisonnement protège de l'accident et sépare les équipes ; il ne protège
pas d'une exfiltration délibérée par quelqu'un d'admis.

---

## 3. Ce que le code borde déjà

Utile à savoir : ces garanties existent, elles sont testées, et elles ne dépendent pas de la
bonne volonté de l'utilisateur.

- **L'application n'authentifie personne.** Elle fait confiance aux en-têtes d'identité
  posés par un portail d'authentification placé devant elle, et seulement si sa
  configuration déclare que ce portail est bien là. Aucun mot de passe, aucun secret en
  base. Sans portail, l'usage est mono-poste.
- **Cloisonnement par collection.** Qui n'a pas accès à une collection ne la voit pas : la
  réponse est « introuvable », jamais « interdit » — la seconde révélerait la composition du
  corpus. Trois niveaux : lecture, écriture, propriété.
- **Le régime de diffusion n'est opposable qu'à la sortie.** À l'intérieur, il ne borde
  rien (§ 2d).
- **L'embargo retient, il ne promeut jamais.** Une collection dont l'embargo court ne fait
  pas sortir ses scans, même déclarée publique. Une échéance passée ne publie rien d'elle-
  même : l'outil ignore *pourquoi* l'embargo existe, et une date qui passe ne dit pas que
  les droits sont acquis. La levée est un acte, avec quelqu'un derrière.
- **Ce qui est déposé est daté.** Les artefacts destinés à l'entrepôt portent leur date de
  génération, et la déclaration de droits qu'ils contiennent est datée elle aussi — figée,
  une assertion non datée deviendrait fausse sans que personne ait menti.

---

## 4. Ce qui reste à établir

Questions posées dans l'ordre où elles se conditionnent. Les quatre premières commandent
les autres.

1. **Quelle institution porte le corpus**, et répond-elle à la définition d'organisme de
   recherche au sens de l'article 3 de la directive 2019/790 ?
2. **D'où viennent les exemplaires numérisés**, et sous quel régime les masters ont-ils été
   produits ? Exemplaires acquis, prêts d'une bibliothèque, numérisation réalisée par un
   partenaire ? La question porte sur l'**accès licite**, qui conditionne l'exception de
   fouille. Elle peut appeler des réponses différentes selon les œuvres — voir § 5.
3. **L'exception de fouille couvre-t-elle nos usages ?** Notre lecture, à confirmer ou à
   corriger : elle couvre la constitution du corpus et son analyse, **pas la rediffusion**.
   Si c'est exact, elle fonde la détention et le travail interne (§ 2d) mais ne fonde
   aucune des sorties du § 2a. Si notre lecture est fausse, c'est le § 2a qu'il faut
   restreindre.
4. **Que doit dire exactement la mention de base légale ?** Une phrase, qui apparaîtra dans
   chaque notice exportée et sur **chaque figure citée** — c'est le texte qui accompagnera
   les extraits dans les articles et les communications.
5. **Quel régime de diffusion par défaut** pour la collection de référence : public,
   embargo (avec quelle échéance), restreint, ou privé ?
6. **L'arbitrage interne du § 2d est-il acceptable** — toute personne admise sur une
   collection en reçoit tout, images et texte intégral compris ? Si non, c'est une décision
   d'architecture à rouvrir, pas un réglage.
7. **La pratique de citation du § 2b tient-elle ?** L'outil produit un extrait accompagné de
   sa référence et de son cadre de droits. Y a-t-il des contraintes — étendue de l'extrait,
   nombre, nature du discours qui l'accompagne — qu'il faudrait inscrire dans l'outil plutôt
   que laisser au jugement de chacun ?
8. **Le texte OCR verbatim** est-il traité comme l'expression protégée de l'œuvre, ou son
   statut se discute-t-il séparément des images ? Le projet a supposé le premier.

### Et quatre questions sur les données de l'équipe (RGPD)

Elles se posent au même moment mais pas forcément à la même personne. Le code ne peut pas
les trancher : il n'existe aucune réponse par défaut qui ne soit un choix déguisé.

9. **Combien de temps garde-t-on le nom et l'adresse d'un annotateur ?** Le miroir
   `utilisateur` est alimenté à chaque passage et n'a aujourd'hui aucune durée de vie. La
   réponse peut être « tant que le projet vit », mais il faut qu'elle soit choisie.
10. **Comment efface-t-on quelqu'un qui quitte l'équipe ?** Trois portées différentes, et
    la troisième est celle qui coince : le miroir `utilisateur` (facile à vider) ; les
    traces dérivées `token_correction.auteur` / `planches.verrou_par` (remplaçables par
    NULL) ; le **journal A3**, append-only, dont l'immuabilité est précisément ce qui lui
    donne sa valeur probatoire au § 1. Faut-il un effacement qui le traverse — et que
    devient alors la démonstration du travail humain ?
11. **Que fait-on des sauvegardes déjà déposées ?** `VACUUM INTO` emporte la base ENTIÈRE,
    donc les adresses, et l'application sait déposer ce zip sur ShareDocs — donc hors de la
    machine, éventuellement sous un compte Huma-Num **personnel**. Un effacement qui ne
    couvrirait que la base vivante laisserait les copies intactes.
12. **Qui est responsable de traitement, et l'annotateur en est-il informé ?** L'outil
    n'affiche aujourd'hui aucune mention de ce genre. Si une information est due, sa place
    naturelle est l'écran où l'identité apparaît déjà — la pastille utilisateur.

---

## 5. Ce qui changera selon la réponse

Peu de code, et c'est voulu — le mécanisme est entier, seule la politique manque.

- **Renseigner la base légale et le régime** est une commande, et tout ce qui sort de
  l'outil les porte aussitôt.
- **Si la base légale est plus étroite qu'espéré**, c'est la branche PUBLIER (§ 2a) qui se
  restreint : il suffit de ne pas déclarer la collection publique, ce que l'outil traite
  déjà comme le cas normal — un manifeste sans images reste déposable, et c'est la forme
  courante d'un dépôt.
- **Si la provenance doit être documentée par œuvre** et non par collection — cas d'un
  corpus mêlant exemplaires personnels, prêts et numérisations de partenaires — il manque
  un champ. Arbitrage du 2026-08-28 : `collection.base_legale` suffit pour l'instant, un
  champ `albums.provenance` restant une entrée de métadonnées possible mais non obligatoire.
  À rouvrir si la réponse à la question 2 l'exige.
- **Si l'arbitrage interne (question 6) est refusé**, le chantier est d'une autre ampleur :
  il faudrait border la lecture des images et du verbatim à l'intérieur même de l'instance,
  ce que le projet a écarté par écrit parce que l'annotation repose sur les images.
