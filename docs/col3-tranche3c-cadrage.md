# COL-3, tranche 3c — le responsable voit son projet, le projet borne ses collections, qui tient l'espace efface : cadrage

Rendu le 2026-10-26, sur `dev` à `ad95350` (schéma **37** : la 3b de `COL-3` et la tranche 1
d'`ANN-7` intégrées). Rien n'est codé ni exécuté. Ce qui est marqué **lu** a été lu dans le
code à ce commit ; ce qui est marqué **supposé** ne l'a pas été, ou reste à mesurer. Les
sept décisions de Hugo du 2026-10-26 (`pilotage/COL-3.md`, zones « Le responsable voit tout
son projet, et le projet borne ses collections » et « La séance de simplification des règles
d'effacement ») sont numérotées **F1 à F7** ; elles PRIMENT, et cette note ne les rediscute
pas : elle dit ce qu'elles font au code. Ce qu'elles laissent ouvert est numéroté **Q1 à
Q14**, en fin de note, chaque fois avec la proposition la plus fermée et la plus simple. Le
tableau « Qui peut quoi » de la séance (artefact `JqKwb5EyHTfz1VFUr43RTJ`) n'a pas été lu
ici : tout ce qu'il tranche est repris dans la fiche, et c'est la fiche qui est suivie.

La zone « Relevé en jouant la passe de la 3b — la Bibliothèque ne distingue ni les copies ni
les espaces » n'est pas cadrée ici : elle attend sa maquette, avec le wizard (lot 4). Deux de
ses cases croisent la 3c (le bloc Collections qui dit le niveau, puisque le responsable va
lire des collections qu'il ne lisait pas ; les albums qu'on ne fait que lire) : la maquette
de la 3c et la sienne gagnent à se tenir dans la même séance.

---

## Ce que la 3c livre, en gestes

1. **Le responsable LIT toutes les collections de son projet** (F1) — une lecture dérivée,
   jamais recopiée : qui cesse d'être responsable cesse de lire. Lire n'ouvre ni l'écriture,
   ni l'export, ni « Qui entre ».
2. **On n'entre dans une collection que si l'on est du projet** (F2) — `PUT …/acces` refuse
   par un 409 nommé un principal qui n'est pas du projet ; « Qui entre » ne propose que les
   membres ; à la migration, les accès hors projet entrent dans le projet.
3. **Qui tient l'espace efface, les autres demandent** (F3) — supprimer définitivement et
   repartir de zéro, sans rien demander : le responsable partout dans son projet, le
   propriétaire de toutes les collections de l'album, l'administrateur, le propriétaire de
   son bac à sable. Plus de chemin du créateur. Le journal ne décide plus rien.
4. **Une demande d'effacement va au responsable du projet** (F4), qui y répond dans la fiche
   du projet ; l'administrateur en recours ; la dernière copie d'un document à
   l'administrateur seul.
5. **Une planche se demande aussi** (F5) — supprimer une planche ou la remettre à zéro,
   motif à l'appui, à la même personne que l'album (renverse B4).
6. **E7 gardé, depuis les seules collections où le responsable écrit** (F6).
7. **Un compte partagé n'efface jamais hors de son bac à sable** (F7), quel que soit son rôle.

Ce que la 3c ne livre pas : la Recherche et l'Exploration bornées au projet (tranche 4) ; la
voie 3 (le responsable co-propriétaire de toutes les collections, écartée le 2026-10-26) —
le responsable lit et efface, il ne règle toujours pas « Qui entre » d'une collection qu'il
ne possède pas ; l'écran des copies et des espaces (lot 4).

---

## Ce qui existe déjà (lu)

- **`Portee.__init__`** dérive déjà UNE collection par projet, la base (D10) : à partir des
  triplets de `bases_des_projets`, le responsable en est propriétaire, le membre y entre au
  niveau `acces_membres`. Rien n'est écrit dans `collection_acces`. Le cumul des niveaux se
  fait juste après, une fois ; `export` est `(export | propriete) & lecture`. `pour_export`,
  `pour_le_corpus` et `_ordinaire` repassent des ensembles déjà dérivés sans redériver.
- **`_clause_effacement`**, commune à `clause_suppression_directe` et à
  `clause_repartir_directe`, est un `CASE` à quatre chemins : le bac à sable à soi ; « tenir
  l'album » (`_sql_tient_l_album` : posséder toutes ses collections hors bacs, ou gérer son
  projet hors bacs — et, pour une suppression, une sœur vivante hors projet isolé) ; puis le
  CRÉATEUR, ses quatre moitiés — `clause_destruction` (écrire dans toutes les collections),
  `copie.creee_par`, pas de compte partagé, et `NOT _sql_travail_d_autrui` (le journal, dix
  sources) — avec, pour la dernière copie, l'exception de la copie d'origine jamais touchée
  (`geste_sur_copie`). Le compte partagé est exclu des chemins 2 et 3 par `pas_partage`.
- **Les routes de l'effacement** passent toutes l'accesseur gardé EN ÉCRITURE avant la
  clause : `DELETE /api/albums/{id}` et `DELETE /api/planches/{id}` (`main.py`),
  `POST …/albums/{id}/repartir`, `POST …/planches/{id}/repartir`,
  `GET …/repartir/apercu`, `GET …/travail-des-autres` (`routes/fonds.py`). Un responsable
  qui ne lit pas la collection d'un album reçoit donc 404 — le constat de « Carnet
  d'arrivant ». « Retirer du projet » lit déjà en LECTURE (`apercu_du_retrait`,
  `retirer_du_projet`).
- **Les demandes d'effacement** (`suppression_document`, `repartir`) se déposent par
  `_demander_un_document` / `_demander_un_repartir` (accesseur en écriture, 409 si l'on peut
  le faire soi-même, 403 dans un bac à sable) ; elles portent DÉJÀ `demande.projet_id` et
  `projet_nom`, et une ligne `demande_document` (`document_id`, `album_id`, `titre`).
  `peut_repondre_a` les rend à `peut_tenir_le_fonds()` seul ; `repondre_demande` ne laisse
  passer, hors portée totale, que les genres consentis et E7 ; accepter passe par
  `_detruire_album` / `_repartir`, dont la garde est la clause de l'appelant — un
  responsable qui accepte serait donc arrêté par la même règle que s'il effaçait lui-même.
- **Une planche** n'a pas de demande : `delete_planche` et `repartir_planche` répondent 403
  avec un motif qui renvoie à un administrateur (`_MOTIF_DESTRUCTION_PLANCHE`,
  `_MOTIF_REPARTIR_PLANCHE`).
- **`PUT /api/collections/{id}/acces`** ne lit aucun projet : il accepte tout principal (la
  base comprise ; refuse le jeu et les bacs à sable). `retirer_membre` (`routes/projets.py`)
  écrit en toutes lettres que qui sort du projet « ne perd aucun accès de collection posé
  dans un Qui entre ». `test_projets.py::test_un_acces_de_collection_se_passe_d_etre_du_projet`
  et `test_collection_de_base.py::test_un_acces_explicite_s_ajoute_a_la_derivation`
  verrouillent cette doctrine. `create_collection` ne fait propriétaire que qui crée hors
  portée totale — un membre, donc déjà du projet ; `tools/gerer_collections.py creer
  --proprietaire` pose en revanche un propriétaire dans le repli sans rien vérifier.
- **E7** : `demandes_recues_du_projet` et `_accepter_un_amorcer_entre_projets` bornent la
  copie source aux copies que le responsable LIT (`_lues`, relecture croisée de la 3b,
  constat 2). La voie 1 rend ce filtre vide de sens.
- **`geste_sur_copie`** (v36) n'est lue que par la règle de la dernière copie, écrite par
  `journal._noter_le_geste` à chaque `journaliser` d'une cible de geste.
- **`clause_grille`** (ANN-7, tranche 1), moitié (b) : « un annotateur qui a un accès de
  collection sans être du projet doit lire la grille qu'il applique ». La voie 2 rend ce cas
  impossible à l'avenir ; la moitié reste juste et ne coûte rien.

---

## F1 — Voie 1 : le responsable lit toutes les collections de son projet

**`autorisation.py`.** Une fonction de résolution de plus, sur le patron de
`bases_des_projets` : `collections_des_projets(conn, projets)` rend les identifiants de
toutes les collections de ces projets (`sql_projet_de('c') IN (…)`, donc le repli compris
pour une collection sans `projet_id`). `resoudre` et `_portee_d_administrateur` la lisent
pour `projets_geres - bacs` — un bac à sable hors du champ, comme le dit la fiche (son
propriétaire en est déjà le seul responsable ; un invité qui y a créé une collection la garde
fermée au propriétaire, comme aujourd'hui), et le jeu n'a pas de responsable. Une seule
requête de plus par requête HTTP d'un compte responsable, qu'on peut fondre dans celle des
bases. `Portee.__init__` reçoit ces identifiants (`lues_par_le_projet`) et les AJOUTE à
`lecture` AVANT le cumul — jamais à `ecriture`, jamais à `export` (la formule d'`export`
réduit à la lecture, elle n'ajoute rien). Aucune question neuve, aucune renommée.

Ce qui suit de soi, et que les tests doivent JOUER, pas supposer : `peut_lire`,
`clause_album`, `_collections_lues_d_albums`, `clause_terme` (les termes locaux de ces
collections deviennent visibles au responsable), `clause_grille` (b) et (c), les chiffres
de `nb_collections`. Ce qui ne bouge pas : `peut_administrer`, `peut_exporter`,
`clause_rejoindre_directe` (administrer reste exigé), `peut_ecrire_quelque_part`,
`accord-inter` (écrire reste exigé).

**Ce que la lecture emporte, et qu'il faut écrire plutôt que découvrir.** La prise `zero`
(copie vierge) est immédiate « pour qui lit une copie du document dans le projet » : le
responsable pourra prendre une copie vierge d'un document d'une collection fermée — notice
et images seulement, qu'il pouvait déjà demander au fonds par les notices. « En partir »
dans le projet (E4) reste au consentement du propriétaire, et « rejoindre » aussi. La
Recherche et l'Exploration lui montreront le texte des collections fermées de son projet :
c'est le sens même de la décision.

**Routes et clés.** Aucune clé neuve pour la lecture. `GET /api/collections` rend
`mon_niveau = lecture` sur ces collections (`_niveau_dans` lit la portée).
`acces_derives` dit, pour une collection qui n'est PAS la base, une ligne par responsable du
projet au niveau `lecture` (`role: responsable`) ; pour la base, rien ne change.
`proprietaires_de` n'est pas touché (lire n'est pas posséder). « 👥 Comptes et groupes » les
montre par le même chemin (`comptes.py` lit `acces_derives`).

**L'écran.** « Qui entre », dans ses deux montages, gagne le groupe « Par le projet · n » sur
toute collection d'un projet qui a un responsable, lignes sans case ni ✕, « Régler dans le
projet ↗ » (la forme de la 3a, tranchée sur maquette le 2026-10-17 : rien à retrancher). Le
bloc Collections de la Bibliothèque montrera au responsable des collections qu'il ne
voyait pas : c'est la case « Le bloc Collections distingue les espaces » de la zone du
relevé, à maquetter ensemble.

---

## F2 — Voie 2 : on n'entre dans une collection que si l'on est du projet

**La règle, écrite une fois.** `database.est_du_projet_par_reference(conn, projet_id, genre,
principal)` : vrai si `projet_acces` porte EXACTEMENT ce couple pour ce projet (membre ou
responsable). Une RÉFÉRENCE, comme partout (invariant d'AUTH-1) : l'application ne sait pas
de quels groupes un login est membre, hors de la requête de ce login lui-même — d'où **Q2**.
Elle vit dans `database.py`, à côté de `rangement_traverse`, et non dans `autorisation.py`,
qui ne décide pas des écritures de `collection_acces`.

**Les écritures.** `accorder_acces` refuse par un **409 nommé** (« X n'est pas du projet
« P » : faites-le entrer dans le projet d'abord — c'est son responsable qui le fait ») tout
principal hors du projet de la collection, la base comprise. Le refus vient APRÈS la garde
d'administration (403 / 404 inchangés), et avant le contrôle du dernier propriétaire.
`tools/gerer_collections.py creer --proprietaire` refuse de même, par la même fonction —
« par la route comme par l'outil », le patron de `rangement_traverse`. `create_collection`
n'a rien à changer : son seul propriétaire posé est un membre.

**La sortie du projet.** Sans règle, la voie 2 se défait au premier départ : `retirer_membre`
laisse les accès de collection, qui deviennent des accès hors projet. **Q1** propose la plus
fermée : sortir d'un projet retire, dans le même geste et sous le même verrou, les lignes
`collection_acces` du même couple sur les collections de ce projet, chacune journalisée
(`delien`) ; un 409 nommé si l'une de ces lignes est le dernier propriétaire d'une
collection (« désignez un autre propriétaire de « C » d'abord »). La phrase de
`retirer_membre` est renversée, datée. Un bac à sable a déjà cette règle (`_sortir_du_bac`).

**Ce que « Qui entre » propose.** La décision dit « ne propose que les membres du projet ».
L'écran ne peut le faire que si le serveur lui donne cette liste — aujourd'hui réservée à qui
GÈRE le projet (`GET /api/projets/{id}/membres`), et CLAUDE.md écrit que lire une collection
ne nomme « ni ses membres ». Proposé : `GET /api/collections/{id}/acces-du-projet` (déjà
bornée à qui ADMINISTRE la collection, 404 / 403) gagne `membres` — les couples
`genre`/`principal` du projet et le nom lisible d'un login, sans les rôles. Une exposition
NEUVE, que la décision emporte : **Q3** la fait confirmer. Le module `qui-entre.js` les
propose à la place des groupes de l'annuaire, et rend le 409 dans sa ligne ; l'annuaire ne
sert plus qu'à la colonne « Signal » (`…/annuaire`, inchangée).

**La migration.** Cf. § La migration v38 : chaque accès hors projet entre dans le projet,
au rôle `membre` — une photographie, le patron de la v29.

---

## F3 — Qui tient l'espace efface

**La clause.** `_clause_effacement` devient, hors portée totale (inchangée, bornée comprise) :

```
pas d'utilisateur            → 0
bac   = projet de l'album ∈ bacs_a_soi                         (inchangé)
tient = (possède toutes ses collections, hors bacs)
        OU (projet de l'album ∈ projets_gérés, hors bacs)
        ET pas un compte partagé
        [ET une sœur vivante hors projet isolé — suppression seulement]
rendu = bac OU tient
```

C'est `_sql_tient_l_album` plus `pas_partage`, et rien d'autre. Disparaissent : le chemin du
créateur entier (`clause_destruction` comme condition, `copie.creee_par`, la quatrième
moitié `_sql_travail_d_autrui`), l'exception de la copie d'origine (`CRAN_ORIGINE`), son
exception pour une copie née d'une prise, `geste_sur_copie`, et « l'album d'avant le fonds »
(qui n'existait que par `creee_par` NULL). Le `CASE` n'a plus de raison d'être hors du
bornage : plus aucune branche ne lit le journal. `clause_repartir_directe` garde sa
définition (les mêmes chemins sans la dernière copie, **Q6**).

**Le coût.** `tests/test_cout_des_clauses.py` change de propos. Son équivalence « ancien SQL
/ nouveau SQL » compare la forme `CASE` à la forme `OR` d'une MÊME règle : la règle change,
la référence recopiée (`_ancienne`) se réécrit sur la règle neuve, ou se réduit au bornage
(`_bornee_sur_album`, inchangé). Son troisième test (« le travail d'autrui ne se lit que si
le reste tient ») devient plus fort et plus simple : **aucune** clause d'effacement ne lit le
journal, sous aucune identité — un témoin sur `_sources_du_travail` qui n'est jamais appelé.
`GET /api/albums` y gagne ce que `destructible` coûtait (supposé : à mesurer sur la base du
test, 150 albums).

**`autorisation.py`, en bilan.** Retirées : `clause_destruction` (plus aucun appelant — elle
ne servait que le chemin du créateur ; vingt-deux questions deviennent vingt et une) et
`_sql_travail_d_autrui`. Gardés, parce qu'ils servent « qui perd quoi » et ce que lit qui
répond : `_sources_du_travail`, `sql_actes_sur_album`, `_sql_chaine_des_sources` et les
fragments qui en écartent ce qui n'est pas un travail (`_SQL_NAISSANCE_D_UNE_COPIE`,
`_SQL_ORDRE_DES_PLANCHES`, `_SQL_EFFACER_OU_RETIRER`, `_SQL_COUCHE_VIT`). L'import de
`CRAN_ORIGINE` tombe. La nature d'un compte reste lue, au seul `pas_partage` : c'est F7.

**Les routes.** Les six routes de l'effacement passent de `_get_album(…, ecriture=True)` (ou
`_get_planche`) à l'accesseur en LECTURE : « lire suffit » au responsable (F3), et la clause
décide du reste. Conséquence voulue : qui LIT un album sans pouvoir l'effacer reçoit un 403
nommé au lieu de 404 — l'objet est lisible, « 404, jamais 403 » ne s'applique pas ; qui ne
le lit pas reçoit toujours 404. Le jeu reste refusé par `_refuser_le_jeu` (409), qui ne
dépendait pas de l'accesseur. `travail-des-autres` garde sa borne (`clause_repartir_directe`)
et passe aussi en lecture ; sa phrase de refus (`_MOTIF_TRAVAIL`) perd « ou qui l'a créé ».

**Les motifs.** Un refus ne dit toujours pas laquelle des conditions manque. Proposé :
`_MOTIF_DESTRUCTION` — « Supprimer définitivement cet album revient au responsable de son
projet ou à qui tient toutes ses collections : demandez-le ; si c'est la dernière copie de ce
document, c'est un administrateur qui répond. Vous pouvez le supprimer de votre collection,
où il est gardé au fonds avec son travail. » ; `_MOTIF_REPARTIR` sur le même patron ; les
motifs de planche disent qu'elle se demande (F5). `_MOTIF_DESTRUCTION_BAC` perd « ou par qui
l'a créée » (**Q4**). Les mots exacts sont des mots d'écran : à relire avec la maquette.

**Les clés publiées** (`GET /api/albums`). `destructible` garde son nom et son sens (« sans
rien demander », la clause de suppression). **Une clé neuve, `effacable`** —
`clause_repartir_directe`, la plus large des deux — parce qu'aujourd'hui l'écran n'offre
« Supprimer… » et « Repartir de zéro… » que sur `ecrivable`, et qu'un responsable qui ne
fait que LIRE l'album doit se les voir offrir : sans elle, il ne repartirait pas de zéro et
ne pourrait pas demander la dernière copie. La dixième clé devient onzième. `derniere_copie`
et `soeur` élargissent leur borne de « qui écrit dans la copie » à « qui y écrit OU peut
l'effacer » (`ecrivable OR effacable`) : ce sont les mots du panneau de qui l'ouvre.
`partage` ne change pas (le rangement ne traverse pas les projets, donc un responsable n'a
jamais de collection non lue dans le sien).

**L'écran.** « Supprimer… » et « Repartir de zéro… » s'offrent sur `ecrivable || effacable`.
Dans `static/lib/echelle.js`, `POUVOIRS.createur` et `createurIntact` disparaissent ;
`pouvoir()` ne connaît plus que `admin`, `bac`, `responsable`, `proprietaire` ;
`panneauRepartir` dit « la demande part au responsable du projet » (ou « à un
administrateur » pour la dernière copie et quand le projet n'a pas de responsable — le
serveur le dit, cf. F4) et perd son mode `planche` (F5). Dans `static/lib/suppression.js`,
`definitif()` et `apresDefinitif()` changent de destinataire de la même façon ;
`IMAGES_RESTENT`, la certification et « qui perd quoi » restent. Les mots sont mesurés par
`tests/test_echelle_ecran.py` et `tests/test_suppression_ecran.py`, qui suivent.

**`ACTES`** (`GET /api/droits`). L'avertissement « Supprimer définitivement un album efface
ses images… » est porté par l'acte `structurer` (ÉCRITURE) : un écrivain n'efface plus. Il
passe à `decider` (PROPRIÉTAIRE), tel quel — un libellé validé par Hugo le 2026-09-17 qui
change de ligne : **Q13**. `tests/test_droits.py` le suit (`structurer["avertissement"]`).

---

## F4 — Une demande d'effacement va au responsable du projet

**Le destinataire se DÉRIVE, il ne se stocke pas.** `demande.projet_id` est déjà écrit au
dépôt, et une copie ne change jamais de projet. Le destinataire se lit au moment où l'on en a
besoin — le patron d'E7 (`projets_qui_tiennent`) : les responsables NON PARTAGÉS du projet ;
s'il n'y en a aucun, ou que la copie est la DERNIÈRE de son document, ou qu'elle est gardée
au fonds, l'administrateur seul. Rien à migrer, et rien qui vieillisse quand un responsable
arrive ou part (**Q10**).

**`peut_repondre_a`** apprend les genres d'effacement (`GENRES_EFFACEMENT` :
`suppression_document`, `suppression_planche`, `repartir`) : la portée totale, ou
`peut_gerer_projet(demande["projet"])` — à qui elle s'adresse. Elle ne dit pas si le geste
passe : répondre, c'est effacer à la place de qui demande, et l'acceptation traverse déjà
`_detruire_album` / `_repartir`, dont la garde est la clause de qui répond. D'où
**`repondable` = `peut_repondre_a` ET la clause d'effacement sur la copie**, relevée sous le
verrou : faux pour un responsable devant une dernière copie, faux pour un responsable compte
partagé (F7), sans qu'`autorisation.py` lise une nature de plus. Le propriétaire de toutes
les collections, qui efface seul, n'est pas destinataire (**Q8**).

**`peut_nommer_le_demandeur`** : le responsable du projet de la copie lit qui demande — on
n'efface pas le travail de quelqu'un sur la demande d'un inconnu, et il lit désormais toutes
les collections de son projet (F1), donc ne découvre personne qu'il ne voie déjà. Par le
paramètre `consentement` (`genre`, `projets`), comme E7. Dans `GET /api/albums`, la clé
`demande` nomme alors le demandeur à ce responsable aussi.

**Les routes.**
- **Une route neuve, `GET /api/projets/{id}/demandes-d-effacement`**, à qui GÈRE le projet
  (404 / 403 nommé, la borne de `demandes-recues`) ; aucune dans un projet isolé. Les
  demandes d'effacement en attente de ce projet, chacune avec : le demandeur nommé, le
  motif, `certifie_le`, le document (titre), la planche s'il y en a une, le cran d'un
  `repartir`, `derniere_copie`, `repondable`, et « qui perd quoi » — `_travail_des_autres(…,
  recopie_a_part=not portee.tout)`, la mesure que lit l'administrateur, le travail recopié
  d'une autre copie compté sans nom et l'importateur du document tu, comme dans
  `travail-des-autres`. Séparée de `demandes-recues` plutôt que mêlée : l'adressage d'E7
  (les projets qui tiennent un travail) et celui-ci (le projet de la copie) ne se lisent pas
  pareil, et deux règles dans une route finiraient par se contredire. L'écran peut les
  montrer dans un même bloc.
- **`repondre_demande`** : hors portée totale, un genre d'effacement se connaît si l'on gère
  le projet de la demande ET qu'on lit la copie (404 sinon, le même qu'elle existe ou non) ;
  403 nommé si `peut_repondre_a` répond oui et la garde non (« c'est la dernière copie de ce
  document : un administrateur y répond »). Le reste est inchangé — accepter appelle
  `_detruire_album` ou `_repartir` avec la portée de qui répond.
- **`GET /api/demandes`** (l'administrateur) : chaque demande d'effacement gagne `attend`,
  les responsables qui peuvent y répondre (nommés), ou `null` — « à vous ». C'est la forme
  déjà servie aux demandes consenties (`_attend`, `BDEchelle.attend`) ; l'administrateur
  peut toujours répondre à leur place (« ou à sa place », la fiche).
- **Le dépôt** (`_demander_un_document`, `_demander_un_repartir`, et celui d'une planche) :
  l'accesseur en écriture devient « écrire dans l'album, OU gérer son projet » — le
  responsable qui ne fait que lire doit pouvoir demander la dernière copie à
  l'administrateur (**Q7**). `_deja_demandee` et les 409 « déjà demandé » disent « le
  responsable du projet y répondra », ou « un administrateur » quand c'est à lui.

**L'écran.** Où le responsable lit et répond : la fiche du projet, dans la Bibliothèque (la
zone qui porte déjà les demandes d'en partir reçues, `#bi-e7-zone`) ET dans la vue Projets
de l'Administration (le bloc « Demandes d'en partir » de la 3b) — les deux montages qu'E7 a
déjà. La forme — un bloc « À répondre » commun aux deux genres, ou deux blocs ; « qui perd
quoi » déplié ou non ; la tranche ROSE de « À faire » reprise — **à trancher sur maquette**
(**Q9**). Le rappel « n demandes » de la bande d'outils de la Bibliothèque (`#bi-rappels`)
les compte. « À faire » de l'Administration garde toutes les demandes d'effacement, avec
« attend … » ou « à vous ».

**Les demandes en attente à la migration.** Elles sont toutes adressées, aujourd'hui, à un
administrateur. Proposé : rien à faire — la dérivation les adresse d'elle-même au
responsable du projet le lendemain, l'administrateur garde la main, et celles d'une
dernière copie restent à lui (**Q10**). Le test de migration les COMPTE, par genre, avant et
après.

---

## F5 — Une planche se demande aussi

**Le modèle.** Un genre neuf, `suppression_planche` (`DEMANDE_SUPPRESSION_PLANCHE`, dans
`GENRES_DEMANDE` et `GENRES_EFFACEMENT`) ; « repartir » d'une planche reste le genre
`repartir`, que la planche distingue. Deux colonnes sur `demande`, posées par la v38 :
`planche_id` (sans clé étrangère : la demande survit à la planche ; ses identifiants ne
reviennent plus depuis la v30) et `planche_numero` (le numéro le jour du dépôt, pour qu'une
demande close dise encore de quoi elle parlait — le patron de `demande_document.titre`). La
ligne `demande_document` porte l'album et le document, comme pour l'album.

**Les règles.** Le dépôt suit celui de l'album : motif et certification exigés (422 nommés),
409 si l'on peut le faire soi-même, 403 dans un bac à sable. Une demande par planche et par
genre en attente ; refusée si une suppression de l'ALBUM attend déjà (409 : elle
l'emporterait). La planche doit être de l'album nommé : accepter relit `planches.album_id`
et refuse sinon (409, « refusez cette demande »). Les clôtures : supprimer la planche par un
autre chemin clôt ses demandes (acceptées) ; détruire l'album les clôt (acceptées pour une
suppression — la planche est partie —, refusées pour un `repartir`, le patron de
`_clore_lignes_d_une_copie_detruite`) ; repartir l'album plus bas satisfait un `repartir` de
planche (déjà dans `_accepter_un_repartir` : « rien au-dessus du cran »). Retirer du projet
laisse les demandes de suppression (l'administrateur en décide au fonds) et clôt les
`repartir`, comme aujourd'hui. La planche d'une dernière copie : **Q5**.

**Les routes.** `POST /api/demandes` reçoit `planche_id` (genre `suppression_planche`, ou
`repartir` avec `cran`) ; `delete_planche` et `repartir_planche` gardent leur 403, dont le
motif dit désormais qu'elle se DEMANDE. `GET /api/albums/{id}/planches` gagne, planche par
planche, la demande qui attend (genre, date ; le demandeur sous la borne de
`peut_nommer_le_demandeur`) : l'écran n'offre pas de la redéposer.

**L'écran.** La corbeille et ↺ d'une planche ouvrent le panneau à deux issues (faire, ou
demander) au lieu d'être éteints ; la ligne dit « suppression demandée » comme un album.
`panneauRepartir` perd son mode `planche`. À maquetter avec F4.

---

## F6 — E7 gardé, depuis les collections où le responsable écrit

`demandes_recues_du_projet` : `copies` ne porte que les copies du projet que le responsable
ÉCRIT (`clause_album(…, ecriture=True)`, un `_ecrites` à côté de `_lues`), aperçus compris ;
`_accepter_un_amorcer_entre_projets` refuse (404, le même qu'une copie qui n'existe pas) une
source qu'il n'écrit pas. Une demande dont il n'écrit aucune copie se lit encore, sans
copie à nommer : il peut la refuser, l'administrateur y répondre à sa place — la phrase
d'aujourd'hui, « que vous lisez » devenant « où vous écrivez ». Le test qui verrouille le
constat 2 (`test_le_responsable_source_ne_consent_qu_avec_une_copie_qu_il_lit`) se réécrit
sur l'écriture, et gagne le cas neuf : une copie qu'il LIT par la voie 1 sans l'écrire n'est
pas offerte. Le texte d'`htmlSourcesE7` (`echelle.js`) suit.

---

## F7 — Un compte partagé n'efface jamais hors de son bac à sable

Déjà vrai pour les chemins 2 et 3 (`pas_partage`) ; la 3c le garde sur la seule règle qui
reste, et l'étend à la réponse (`repondable`, F4). Un compte partagé responsable demande
comme un annotateur, et une demande qui ne s'adresserait qu'à lui va à l'administrateur
(**Q14**). Dans son bac à sable, il efface (`bac`, inchangé).

---

## La migration v38

**La vraie base v37.** `tools/fabriquer_base_de_version.py <tête de dev> tests/bases/v37-<sha>.sql`,
le commit étant la tête de `dev` au début du chantier (`ad95350` aujourd'hui ; son code est
celui de `3dc6b48`, les commits qui suivent ne touchant que `pilotage/`). L'outil gagne
`_parcours_v37` — joué par le code v37, avec les routes qu'il a —, ce que la v38 peut
manquer :
- un accès hors projet : un compte et un groupe qui ne sont d'aucun projet, posés par `PUT
  …/acces` (le code v37 l'accepte) sur une collection d'un projet ordinaire, et un compte
  sur une collection du repli ; et, pour éprouver l'exclusion, rien de tel dans un bac à
  sable (impossible par les routes : le test le pose à la main, sur la base chargée) ;
- une collection d'un projet que son responsable ne lit pas, possédée par un membre, avec un
  album dedans (la « Carnet d'arrivant » du constat) ;
- une copie créée par un simple écrivain (`copie.creee_par`), qu'il a touchée et qu'un autre
  a touchée — des lignes dans `geste_sur_copie` ;
- des demandes d'effacement EN ATTENTE : une suppression sur une copie qui a une sœur, une
  sur une dernière copie, un `repartir` ; et une close ;
- un compte déclaré partagé (`PATCH /api/comptes/{login}/nature`) responsable d'un projet.

Le parcours note ces faits dans l'en-tête du fichier, comme les versions d'avant.

**Les étapes** (dans `_migrate`, gardées par la version, idempotentes) :
1. `demande.planche_id INTEGER`, `demande.planche_numero INTEGER`, par PRÉSENCE. `cran` est
   aujourd'hui la dernière colonne de `demande`, avec son commentaire SOUS elle : le
   commentaire de la nouvelle dernière colonne descend sous elle, celui de `cran` remonte
   (règle de la v29, § Schéma & migrations de `CLAUDE.md`).
2. Les accès hors projet entrent : `INSERT OR IGNORE INTO projet_acces (projet_id, genre,
   principal, role) SELECT DISTINCT sql_projet_de(c), ca.genre, ca.principal, 'membre' FROM
   collection_acces ca JOIN collection c …` hors projets isolés (bacs à sable, jeu) — le
   patron de la v29, sans journal comme elle. `INSERT OR IGNORE` sur la clé `(projet_id,
   genre, principal)` : un responsable ou un membre déjà là n'est pas touché. Mesuré en
   production le 2026-10-26 : 0 ligne ; l'étape est pour les autres instances et pour ce qui
   naîtrait d'ici le déploiement.
3. `DROP TABLE IF EXISTS geste_sur_copie` — **proposé** (cf. § Ce qui devient mort) ;
   **Q11**.

Rien d'autre ne change : aucune reconstruction, aucun identifiant touché, aucune vue (les
vues sont recréées comme toujours). `tests/test_migration_v38.py` charge la vraie base v37,
migre, et vérifie : les deux colonnes, NULL partout ; les accès hors projet devenus membres
(et eux seuls : le nombre de lignes de `projet_acces` augmente exactement de ce compte) ;
rien dans les projets isolés ; `geste_sur_copie` absente ; les demandes en attente
inchangées en nombre et en contenu ; tout le reste égal ligne à ligne (le patron de
`test_migration_v37.py`). Les tests de migration des versions précédentes (v31 à v37, et
`test_identifiants_v30.py`) listent `geste_sur_copie` parmi les tables neuves : ils la
retirent de la liste ; l'outil de fabrication borne son compte à `36 <= version < 38`.

---

## Ce qui devient mort

**Code.** `Portee.clause_destruction` ; `_sql_travail_d_autrui` ; la branche du créateur de
`_clause_effacement` et ses paramètres ; `CRAN_ORIGINE` dans `autorisation.py` ;
`journal._noter_le_geste` et `_CIBLES_DE_GESTE` (et l'appel dans `journaliser`) ; dans
`routes/analyse.py`, le commentaire « relecture de `geste_sur_copie` » (la région restant
utile dans la charge, l'écriture ne bouge pas) ; `POUVOIRS.createur` et `createurIntact`
dans `echelle.js` ; le mode `planche` de `panneauRepartir`. `copie.creee_par` et
`copie.cran` RESTENT : ils disent qui a créé et jusqu'où, au fonds, sous une demande et dans
« qui perd quoi » — et la zone du relevé veut publier `creee_par`. Les marques `recopiee`
RESTENT : « qui perd quoi » compte le recopié à part.

**`geste_sur_copie`.** Proposé : la RETIRER (v38), plutôt que la garder dormante. Une table
et non une colonne — `DROP TABLE` ne pose aucun des problèmes d'un `DROP COLUMN` — ; elle ne
porte que des couples (copie, login), dont le journal garde la vérité ; rien ne la publie ni
ne l'exporte ; et dormante, elle cesserait d'être écrite : si une règle future voulait la
relire, elle mentirait sur tout ce qui s'est fait entre-temps. Le coût : huit fichiers de
test de migration et l'outil de fabrication (une borne de version), et les tests qui
l'éprouvent (ci-dessous).

**Les tests, par sort** (nommés par fichier ; chacun verrouillait ce qui tombe) :
- *Retirés* (ils éprouvent `geste_sur_copie` ou la quatrième moitié du créateur) :
  `test_qui_efface.py` — `test_un_geste_defait_compte_encore_pour_la_derniere_copie`,
  `test_supprimer_la_region_d_un_autre_est_un_geste`, `test_une_correction_retiree_est_un_geste`,
  `test_retirer_la_correction_d_un_autre_est_un_geste`,
  `test_valider_une_planche_partie_depuis_est_un_geste`,
  `test_hors_de_la_derniere_copie_la_regle_lit_ce_qui_vit`.
- *Renversés* : `test_qui_efface.py::test_le_createur_seul_efface_encore` (il demande) ;
  `::test_une_planche_suit_la_regle_du_document` et
  `test_fonds.py::test_une_planche_suit_la_regle_du_document` (elle se demande) ;
  `test_fonds.py::test_qui_a_importe_seul_supprime_tout_de_suite`,
  `test_copies_soeurs.py::test_qui_a_cree_la_copie_la_supprime_seul`,
  `test_fonds.py::test_un_album_d_avant_le_fonds_se_demande` (tout se demande désormais : le
  test se réduit à « l'écrivain demande ») ;
  `test_destruction.py::test_qui_ecrit_dans_toutes_ses_collections_detruit`,
  `::test_un_album_d_une_seule_collection_se_detruit_comme_avant`, et ses deux tests unitaires
  de `clause_destruction` ;
  `test_bac_a_sable.py::test_l_invite_supprime_la_copie_vierge_qu_il_a_prise` et
  `::test_l_invite_garde_la_regle_commune_sur_sa_copie` (**Q4**) ;
  `test_projets.py::test_un_acces_de_collection_se_passe_d_etre_du_projet`,
  `::test_etre_d_un_projet_ne_touche_aucun_ensemble_de_collections` (pour le responsable),
  `::test_etre_du_projet_n_ouvre_que_sa_collection_de_base` (le paramètre `responsable`),
  `test_collection_de_base.py::test_la_base_n_ouvre_qu_elle_meme` (sa moitié responsable) et
  `::test_un_acces_explicite_s_ajoute_a_la_derivation` (un compte du projet),
  `test_appartenance_albums_portees.py::test_etre_responsable_du_projet_n_ouvre_pas_le_nom_d_une_collection` ;
  `test_amorcer_entre_projets.py::test_le_responsable_source_ne_consent_qu_avec_une_copie_qu_il_lit`
  (F6).
- *Réécrits sur « qui perd quoi »* : la famille de `test_fonds.py` qui éprouvait la RÈGLE par
  le travail d'autrui (`test_le_travail_d_un_autre_fait_demander` jusqu'à
  `test_ranger_ailleurs_n_est_pas_y_travailler…`, `test_le_refus_ne_dit_pas_laquelle…`,
  `test_la_clause_aux_extremites_et_ses_parametres_lies`) — les mêmes décors, l'attendu lu
  dans `travail_des_autres` au lieu d'un 204 ou d'un 403 : les dix sources restent la mesure,
  elles ne décident plus ; `test_qui_efface.py::test_repartir_ou_retirer_du_projet_n_est_pas_un_travail_sur_l_album`
  et, dans `test_releves_coutures.py` (ANN-7), `test_un_releve_d_un_autre_interdit_la_suppression_directe`
  et `test_la_regle_du_travail_d_autrui_lit_le_releve_lui_meme` (la seconde lit aussi
  `geste_sur_copie`), de même.
- *Adaptés* : `test_cout_des_clauses.py` (F3) ; `test_droits.py` (l'acte `decider` pose un
  accès à un membre du projet ; l'avertissement change de ligne) ; les tests qui attendaient
  404 d'une lectrice sur un geste d'effacement attendent 403
  (`test_qui_efface.py::test_qui_n_ecrit_pas_n_efface_rien`) ; les messages « un
  administrateur y répondra » des tests de demande ; `test_echelle_ecran.py`,
  `test_suppression_ecran.py`, `tests/js/*.test.js` des deux modules.

---

## Les règles d'autorisation

En bilan : **une question retirée** (`clause_destruction`) ; **deux qui s'étendent** —
`peut_repondre_a` (les genres d'effacement, au responsable du projet) et
`peut_nommer_le_demandeur` (les mêmes) ; **deux qui changent de sens** —
`clause_suppression_directe` et `clause_repartir_directe`, qui ne lisent plus le journal ;
**une dérivation de plus** dans `Portee.__init__` (la lecture du responsable). **Une clé
neuve** (`effacable`), deux bornes élargies (`derniere_copie`, `soeur`), `repondable` sur une
route neuve. Hors de `autorisation.py`, une règle d'écriture neuve
(`est_du_projet_par_reference`, F2). `CLAUDE.md` se réécrit en conséquence (§ Autorisation :
« Qui EFFACE sans demander » réécrit ; « Supprimer a deux réponses », « Le PROJET est un
étage » — « être d'un projet n'ouvre aucune autre collection que sa base » ne vaut plus que
pour le membre —, « Une garde d'interface se pose sur l'ACTE » — les compteurs —, « Le BAC À
SABLE » datés ; § Journal de provenance : « le journal est aussi une ENTRÉE d'autorisation »
est RENVERSÉ, daté — depuis la v38, il ne décide plus rien et ne sert qu'à montrer).

### Ce qui fuit si l'on se trompe

- **La lecture dérivée qui passe dans un bac à sable** — mutant : `projets_geres` sans
  `- bacs_a_sable` ; un invité qui y a créé une collection la verrait ouverte au
  propriétaire du bac.
- **La lecture dérivée qui ouvre plus que la lecture** — mutants : l'ajouter à `ecriture`,
  ou à `export` ; ou la recopier dans `collection_acces` (elle survivrait à une
  rétrogradation). Test : rétrogradé, il ne lit plus ; l'export d'une collection qu'il ne
  fait que lire est refusé (403), par la route et par `pour_export`.
- **E7 qui envoie une collection fermée** — mutant : `_lues` gardé ; le travail d'une
  collection qu'il lit sans y écrire part dans un autre projet.
- **Un accès hors projet qui passe** — mutants : le contrôle fait sur le repli au lieu du
  projet de la collection (`sql_projet_de` oublié pour un `projet_id` NULL) ; un groupe
  accepté parce qu'un login du même nom est membre (le `genre` oublié) ; l'outil sans le
  contrôle.
- **Le responsable d'un autre projet qui efface ou répond ici** — mutants : `projets` au lieu
  de `projets_geres` ; le projet lu sur les collections au lieu de `sql_projet_d_album`
  (une copie gardée au fonds) ; `demandes-d-effacement` sans le filtre `projet_id` — il y
  lirait des noms, des motifs et « qui perd quoi » d'un autre projet.
- **La dernière copie qui sort du fonds sans administrateur** — mutants : `_sql_une_soeur`
  oublié dans la suppression ; `repondable` sans la clause ; une sœur ISOLÉE comptée comme
  une sœur.
- **Un compte partagé responsable qui efface ou accepte** — mutant : `pas_partage` posé sur
  le seul chemin du propriétaire.
- **Une planche d'un autre album détruite par une demande** — mutant : accepter sur
  `planche_id` sans relire son album.
- **La migration qui fait entrer dans un bac à sable ou dans le mauvais projet** — mutants :
  l'exclusion des isolés oubliée ; `c.projet_id` au lieu de `sql_projet_de('c')`.

---

## Les identités de la relecture croisée

Sous chacune, les mêmes gestes — lire la liste, supprimer, repartir (album, planche),
demander, répondre, lire « qui perd quoi », poser un accès — et le JSON brut des réponses :

1. le **responsable** d'un projet qui, avant la 3c, ne lisait pas une collection de son
   projet (« Carnet d'arrivant ») ;
2. un **second responsable** du même projet ;
3. le **responsable d'un autre projet** ;
4. un **propriétaire** d'une collection, de toutes les collections d'un album, et d'une
   seule ;
5. un **propriétaire hors du projet** avant migration (il en devient membre) ;
6. un **annotateur créateur** d'une copie (il demandait déjà, ou effaçait seul) ;
7. un **membre par un groupe seulement** (Q2) ;
8. une **lectrice** ;
9. un **compte partagé responsable** ;
10. l'**administrateur** (borné, avec un bac à sable) et le **mono-poste** ;
11. le **propriétaire d'un bac à sable** et son **invité** (créateur dans le bac).

Sur une base qui porte : un projet sans responsable (le repli), deux copies sœurs dont une
isolée, une dernière copie, une copie gardée au fonds, des demandes d'effacement de chaque
genre en attente — dont une sur une planche —, et une demande E7.

---

## Le découpage en commits

0. **La vraie base v37** : `_parcours_v37` dans l'outil, `tests/bases/v37-<sha>.sql`
   fabriquée. Aucun comportement.
1. **La règle d'effacement simplifiée** (F3, F7), sans migration : la clause, la suppression
   de `clause_destruction` et de `_sql_travail_d_autrui`, `journal._noter_le_geste` qui
   cesse d'écrire (la table reste, dormante, jusqu'au commit suivant), les accesseurs en
   lecture, les motifs, `effacable` et les deux bornes, les tests de la règle retirés,
   renversés et réécrits, `test_cout_des_clauses.py`.
2. **La v38, la voie 1 et la voie 2** (F1, F2, F6) : la migration entière — les colonnes de
   planche (dormantes jusqu'au commit 3), les accès hors projet, `DROP TABLE
   geste_sur_copie` — et son test ; la lecture dérivée ; le 409 de `PUT …/acces` et de
   l'outil ; la sortie du projet (Q1) ; `membres` dans `acces-du-projet` (Q3) ;
   `acces_derives` ; E7 sur l'écriture. Toute la v38 dans UN commit : une recette migrée
   entre deux commits ne repasserait pas une étape ajoutée ensuite (`_migrate` sort tôt dès
   que la version est atteinte).
3. **Les demandes au responsable et la planche** (F4, F5) : `peut_repondre_a`,
   `peut_nommer_le_demandeur`, `GENRES_EFFACEMENT`, `suppression_planche`, le dépôt
   élargi, `demandes-d-effacement`, `attend`, les clôtures, la demande d'une planche dans
   `GET …/planches`.
4. **L'écran**, après la maquette (Q9) : les deux montages du bloc des demandes, « Qui
   entre » (« Par le projet » sur toute collection, les membres proposés, le 409), les
   panneaux (`echelle.js`, `suppression.js`), la corbeille et ↺ d'une planche.
5. **La documentation** : `docs/modele-et-droits.md`, `docs/guide-utilisateur.md`,
   `CLAUDE.md` (cf. § Les règles d'autorisation), chaque renversement daté.

Chaque commit de code cite `COL-3`. Le commit 1 laisse l'écran mentir sur le destinataire
d'une demande (« un administrateur ») jusqu'au commit 4 : sur `dev` seulement, comme les
tranches d'avant, et rien ne part vers `main` avant le commit 4.

**Relecture croisée obligatoire** (la 3c touche `autorisation.py`, ouvre une lecture et
déplace qui répond), par une session qui ne l'a pas écrite, sous les identités ci-dessus,
après le commit 3 et avant l'écran.

**Estimation** (supposée, sur le rythme de la 3b) : commit 0, une demi-journée ; commit 1,
une journée (la règle est plus simple, mais une cinquantaine de tests changent de sort) ;
commit 2, une journée ; commit 3, une journée et demie ; la relecture croisée et ses
corrections, une journée ; l'écran, une journée et demie après la maquette ; la
documentation, une demi-journée. **Environ sept journées de session**, plus la séance de
maquette.

### Les gardes à éprouver par mutants

- la lecture dérivée : ni écriture, ni export, ni bac à sable, et retirée avec le rôle ;
- la clause : le responsable d'un autre projet n'efface rien ; posséder une seule collection
  ne suffit pas ; la dernière copie n'est jamais supprimée par le responsable ni le
  propriétaire ; repartir l'est (Q6) ; le compte partagé jamais ;
- aucune clause d'effacement ne lit le journal (le témoin de `test_cout_des_clauses.py`) ;
- `repondable` faux sur la dernière copie et pour un compte partagé, et l'acceptation
  refusée de même (403) ;
- `demandes-d-effacement` bornée au projet géré, et « qui perd quoi » sans nom pour le
  recopié ;
- le 409 de la voie 2 sur le projet de la collection, `genre` compris, par la route et par
  l'outil ; la sortie du projet qui retire les accès (Q1) ;
- la demande d'une planche : la planche relue sur son album, une seule en attente, les
  clôtures ;
- la migration : les accès hors projet entrés et eux seuls, rien dans un projet isolé, les
  demandes en attente intactes.

### Les passes de QA que la 3c périme

Rédigées ou réécrites, jamais cochées par qui les écrit, et relues ensemble avant d'être
rendues :
- **`supprimer-n-est-pas-sortir`** — RÉÉCRITE : elle éprouve « qui l'a importé, seul,
  supprime », que la 3c retire ; les deux réponses et la certification restent, le
  destinataire change, la planche se demande ;
- **`en-partir-d-un-travail`** — rejouée sur ses zones « Repartir de zéro » et « Supprimer
  et retirer » (« Retirer du projet » jouée par `admin-bd` faute de mieux le 2026-10-26 : par
  `proprio` désormais) et sur « Depuis quelle copie » (F6) ;
- **`qui-entre`** et **`comptes-et-groupes`** — relues : chaque accès qu'elles posent vise un
  membre du projet, sinon la case attend le 409 ; « Par le projet » sur toute collection ;
- **`administration-a-l-echelle`** — sa zone « À faire » : « attend … » sur les demandes
  d'effacement ;
- **`bac-a-sable`** — si Q4 est tranchée comme proposé : l'invité ne supprime plus sa copie ;
- **`projet-visible`** et **`bibliotheque-en-calque`** — le responsable voit des collections
  qu'il ne voyait pas : leurs cases de comptes de collections sont à relire ;
- une passe **neuve**, courte, pour le bloc des demandes dans la fiche du projet (les deux
  montages), après la maquette ;
- `petites-largeurs` et `preference-de-police` sur ce bloc.

---

## Les décisions qui restent à Hugo

| | Question | Proposé (le plus fermé, le plus simple) |
|---|---|---|
| Q1 | Qui SORT d'un projet garde-t-il ses accès de collection ? | Non : retirés dans le même geste, journalisés ; 409 nommé s'il est le dernier propriétaire d'une collection |
| Q2 | Un compte membre seulement PAR UN GROUPE reçoit-il un accès personnel ? | Non : la référence exacte de `projet_acces` ; le 409 dit de le faire entrer par son login, ou de donner l'accès au groupe |
| Q3 | Le propriétaire d'une collection lit la liste des membres du projet (pour « Qui entre ») | Oui, à qui administre la collection : les principaux et leur nom lisible, sans les rôles |
| Q4 | Dans un bac à sable, l'invité perd-il tout effacement, son propre import compris ? | Oui : seul le propriétaire du bac efface ; rien ne s'y demande |
| Q5 | Supprimer une planche d'une DERNIÈRE copie va-t-il à l'administrateur, comme l'album ? | Oui, la même clause. Coût : un album importé une fois est presque toujours une dernière copie — le mauvais fichier ira à l'administrateur |
| Q6 | Repartir de zéro sur la dernière copie reste-t-il sans la règle de la dernière copie ? | Oui, comme aujourd'hui : rien ne sort du fonds |
| Q7 | Qui peut DÉPOSER une demande d'effacement ? | Qui écrit dans l'album, ou gère son projet ; une lectrice, non |
| Q8 | Le propriétaire de toutes les collections, non responsable, est-il destinataire ? | Non : il efface lui-même s'il le veut ; les demandes vont au responsable et à l'administrateur |
| Q9 | Où le responsable lit et répond aux demandes | Les deux fiches du projet (Bibliothèque et Administration), forme sur maquette |
| Q10 | Le destinataire et les demandes en attente | Dérivé de `demande.projet_id`, jamais stocké ; rien à migrer, l'administrateur garde la main |
| Q11 | `geste_sur_copie` | Retirée en v38 (`DROP TABLE`), pas gardée dormante |
| Q12 | Une copie de son projet GARDÉE AU FONDS : le responsable l'efface-t-il ? | Non : le fonds reste à l'administrateur (et le responsable ne la lit pas) |
| Q13 | L'avertissement « Supprimer définitivement… » (libellé du 2026-09-17) | Passe de l'acte `structurer` à l'acte `decider`, tel quel |
| Q14 | Une demande qui ne s'adresserait qu'à un responsable compte partagé | Va à l'administrateur : un compte partagé n'est jamais destinataire |

**Tranché le 2026-10-26.** Hugo a répondu à Q1, Q3, Q4 et Q5 ; le pilotage a pris les dix
autres telles que proposées, parce qu'elles découlent des décisions de la séance.

- **Q1 — Hugo : ses accès partent avec lui**, comme proposé.
- **Q3 — Hugo : les noms, sans les rôles**, comme proposé. Ce que cela veut dire, écrit après
  la relecture croisée du 2026-10-27 : la liste `membres` d'`acces-du-projet` ne porte pas le
  rôle — mais les `lignes` de la même réponse nomment déjà les responsables du projet
  (propriétaires de la base, lecteurs des autres collections par F1), et rien ne les tait.
- **Q4 — Hugo, CONTRE la proposition** : « le bac à sable n'a pas d'importance, encore une fois.
  L'import, la suppression, ça n'a pas trop d'effets ». Dans un bac à sable, **quiconque y écrit
  efface** (supprimer un album ou une planche, repartir de zéro), invité compris, son import ou
  non. Rien ne s'y demande, comme avant. Le compte partagé y efface comme les autres (COL-4).
- **Q5 — Hugo, CONTRE la proposition** : une planche n'est pas le document, qui reste au fonds.
  Supprimer une planche, même d'une dernière copie, suit la règle de **repartir de zéro** : le
  responsable ou le propriétaire de toutes les collections la supprime, et la demande d'un
  annotateur va au responsable. Seule la suppression d'un ALBUM qui est la dernière copie va à
  l'administrateur.
- **Q5 complétée — Hugo, 2026-10-27**, sur le constat 3 de la relecture croisée : la règle
  ci-dessus laissait le responsable VIDER la dernière copie planche à planche, images
  comprises, sans administrateur — le détour que la règle de l'album fermait. Il se ferme :
  **supprimer une planche de la DERNIÈRE copie va à l'administrateur, comme l'album** (la
  clause de la suppression, `clause_suppression_directe`) ; la demande d'une telle planche
  s'adresse à l'administrateur. **Repartir de zéro** sur une planche garde la règle de
  repartir. Hors de la dernière copie, rien ne change : le responsable ou le propriétaire de
  toutes les collections supprime la planche, et la demande d'un annotateur va au responsable.
- **Q2, Q6 à Q14 — le pilotage, comme proposé.** Q2 est forcée par l'invariant d'AUTH-6
  (l'annuaire ne décide d'aucun accès) ; Q9, la forme, se tranche sur maquette.

---

## Ce que cette note n'a pas pu établir

- Le gain de coût de `GET /api/albums` sans le journal dans `destructible` : supposé, à
  mesurer au commit 1 sur la scène de `test_cout_des_clauses.py`.
- Le nombre exact de tests qui changent de sort : la liste ci-dessus est nommée par
  recherche dans `tests/`, pas par une passe ; le commit 1 la mesure par la suite entière.
- Si la fiche du « Projet principal » a un responsable : la fiche le dit sans responsable en
  production, et `proprio` en est responsable sur la recette. La règle n'en dépend pas ; la
  passe de QA, si.
