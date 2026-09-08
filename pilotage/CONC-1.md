---
chantier: CONC-1
statut: livré
audit: AUDIT.md
---

# CONC-1 — cache de crop, purge des jobs, annulation préemptive

**Arrêté sur** — 2026-09-08, `407cf95` : **les quatre zones sont CLOSES.** Le
registre dans l'ordre que la lecture du matin avait imposé — `_job_visible` durci d'abord
(`838c931`), purge ensuite (`e17556c`) —, puis la coupe du verrou (`7f13d0f`), puis le TTL
(`dfcc456`), puis l'annulation préemptive (`407cf95`). Une passe de revue est repassée sur
les trois premiers correctifs et y a trouvé quatre choses, dont un DÉFAUT que la purge
avait ouvert (`fc406b0`) : voir les sections datées en bas.

**Trois constats d'audit jamais repris, fermés en un jour — et le chiffre qui compte est
ailleurs : sur cinq cases d'origine, TROIS étaient fausses ou trompeuses**, chacune
démentie par la lecture ou la mesure avant qu'une ligne soit écrite. « Le verrou ne couvre
plus que le dictionnaire » aurait produit un accès après fermeture ; « il faut un fil de
fond » pour le TTL, alors qu'une minuterie éphémère suffit ; « le sous-processus Kumiko
n'est pas tué », alors que la stdlib le tuait déjà. Un audit vieillit moins dans son fond
que dans ses ATTENDUS.

**Le TTL a coûté une mesure et un arbitrage, dans cet ordre — et la mesure a failli
dissoudre l'arbitrage.** Sur un master réel de 53 Mo : le décoder coûte 39 ms, le garder
coûte 53 Mo. Le cache achète donc 39 ms au prix d'une résidence permanente, sur une
requête dont la réponse pèse 593 Ko. Supprimer le cache aurait tout dissous — plus de TTL,
plus de verrou, plus de résidence — et c'est la mesure qui l'écarte : le cache BORNE aussi
la mémoire, et sans lui N requêtes simultanées décodent N masters. Une pointe transitoire
vaut pire qu'une résidence sur un petit VPS.

**La mesure a dépassé l'hypothèse, et c'est ce qui justifie la coupe.** Trois régions d'un
vrai master TIFF, médiane sur cinq passes : ouverture 4-7 %, crop 1,6-2,5 %, resize 19-31 %,
encodage PNG 59-75 %. 85 à 94 % du temps sortent de la sérialisation — et davantage en
régime réel, le master étant caché : une navigation bulle-à-bulle ne garde plus sous le
verrou que le crop, environ 2 %.

Ce que l'ordre a évité se mesure : la purge fait de « job inconnu » l'état FINAL de tout
lot, là où c'était un cas rare. Posée d'abord, elle aurait mis en charge une garde qui
approuvait tout identifiant inconnu — sans rien casser, et sans que rien ne le dise.

**Et les deux mutations ont corrigé les tests avant de valider le code.** Celle qui fait
purger sans regarder le statut rougissait sur « plafond non tenu : 99 », un motif sans
rapport avec la propriété qu'elle démentait : l'assertion sur le lot en cours n'était
jamais atteinte. Réordonnées, celle qui casserait un écran d'abord. Un troisième défaut
était dans le test lui-même — `start_job` tire son id d'un `_counter` GLOBAL que le test
n'isolait pas, donc un vert possible par accident.

**Point de départ** — trois défauts de cycle de vie relevés à l'audit, jamais repris :
verrou de crop trop large, registre de jobs sans purge, annulation non préemptive.

## Reste

### Le verrou de crop
- [x] **Le resize LANCZOS et l'encodage PNG sortent du verrou `_crop_lock`** (`pipeline/ocr.py`), qui enveloppe aujourd'hui tout le corps de `region_crop_png` — ouverture du master par `_open_image`, crop, resize, encodage —, tout sérialisé. **L'attendu d'origine disait « ne couvre plus que la manipulation du dictionnaire de cache » : il est FAUX, et l'appliquer casserait quelque chose** — voir la section datée ci-dessous. `_open_image` et le `crop` restent dedans ; ce qui sort, ce sont les deux étapes qui travaillent sur un objet neuf et local au thread. **Fait le 2026-09-08, `7f13d0f`** — et `crop.load()` sous le verrou EST la sûreté de la sortie : Pillow est paresseux, un crop non matérialisé relirait l'image partagée après qu'un autre thread l'a fermée. Les versions récentes matérialisent déjà ; s'en remettre à cela ferait reposer une propriété de sûreté sur un accident
- [x] Le gain est MESURÉ et non supposé : l'encodage PNG d'un crop de 1600 px est la part la plus chère de l'appel, et c'est ce qui justifie la coupe. Sans mesure, on aura déplacé une accolade. **Mesuré le 2026-09-08** : resize 19-31 %, PNG 59-75 %, soit 85 à 94 % qui sortent. L'hypothèse de la case — « l'encodage est la part la plus chère » — était juste, et le resize à lui seul pesait déjà plus que l'ouverture et le crop réunis

### Le master résident
- [x] Un TTL ferme le master gardé ouvert dans `_crop_cache` (`pipeline/ocr.py`), qui n'est fermé aujourd'hui qu'à l'ouverture d'une AUTRE planche — un master de 50 Mo reste donc résident indéfiniment. **Fait le 2026-09-08, `dfcc456`** : `TTL_MASTER_CROP` (120 s, `config.py`, `BD_TTL_MASTER_CROP=0` pour désarmer). Le délai peut être COURT précisément parce que le défaut de cache est bon marché — 39 ms mesurées : la même mesure qui rend la résidence chère rend son échéance sans risque
- [x] **Le porteur du TTL est tranché par écrit, parce qu'un contrôle paresseux ne répond PAS à la case ci-dessus** : vérifier l'échéance à chaque appel ne ferme rien quand plus personne n'appelle, c'est-à-dire exactement le cas visé. Il faut un fil de fond, donc un objet vivant de plus dans un module qui n'en a aucun — arbitrage, pas implémentation. **Tranché le 2026-09-08 : une MINUTERIE D'INACTIVITÉ, et le raisonnement de la case tenait à un détail près.** Un `threading.Timer` réarmé n'existe QUE tant que le cache tient quelque chose — armé au premier crop, il meurt avec l'image qu'il ferme, et le module n'a aucun objet vivant quand le cache est vide. C'est le fil de fond sans sa permanence, et la case avait raison de refuser le contrôle paresseux
- [x] **La minuterie se réarme quand elle se réveille trop tôt.** Case ajoutée APRÈS coup, parce que le premier jet ne le faisait pas et que le test l'a attrapé au premier lancement : `Event.wait()` rend la main un cheveu avant l'heure, le fil mourait sans successeur, et seul un changement de planche pouvait encore fermer le master — l'état exact qu'on voulait quitter. Un correctif de fuite qui ne fuit plus qu'une fois sur deux, et rien ne l'aurait dit

### Le registre des jobs
- [x] **`_job_visible` distingue « job inconnu » de « job dont toutes les planches sont autorisées », AVANT toute purge.** `main.py` fait `set(jobs.planches_du_job(job_id)) <= autorisees` : pour un identifiant inconnu, `planches_du_job` rend `[]`, l'ensemble vide est inclus dans tout, et la garde répond **True**. Aucune fuite aujourd'hui — les quatre appelants testent l'existence par ailleurs — mais la primitive était permissive et ce sont les ORDRES de vérification qui sauvaient. **Fait le 2026-09-08, `838c931`** : `planches_du_job` rend `None` pour un inconnu, et l'existence se teste AVANT la portée — « ce job n'existe pas » n'est pas une question de périmètre. Le comportement observable ne bouge pas d'un octet ; ce qui change, c'est qu'il ne dépend plus d'une coïncidence
- [x] Le registre `_jobs` (`pipeline/jobs.py`) est purgé de ses entrées anciennes, et sa taille ne croît plus indéfiniment. **Dans cet ordre seulement** : la purge fait passer « job inconnu » d'un cas rare — quelqu'un tape un mauvais numéro — à l'état FINAL de tous les jobs. **Fait le 2026-09-08, `e17556c`** : plafond de `JOBS_CONSERVES = 100` lots TERMINÉS, purge à la création sous `_lock` — seul instant où le registre grandit, donc pas de fil de fond. On borne le NOMBRE et non l'ÂGE, seul des deux à tenir « ne croît plus indéfiniment » : une rafale déborde une purge par ancienneté

- [x] **La revue d'après-coup a trouvé ce que la purge avait ouvert dans `all_jobs`, et ce n'était dans aucun énoncé.** L'énumération lisait `_jobs` sans verrou — liste des identifiants, puis instantané un par un. Sûr tant que le registre ne faisait que GRANDIR ; le RETRAIT rend possible un identifiant listé, purgé, puis interrogé, dont `snapshot` rend `None` — `GET /api/jobs` fait `s["id"]` dessus et répond 500. La Bibliothèque interroge cette route chaque seconde pendant un lot, et c'est le lancement d'un autre lot, depuis le même écran, qui purge ; le poll avale ses erreurs, donc la progression se figerait sans un mot. **Fait le 2026-09-08, `fc406b0`** : `all_jobs` prend `_lock`, celui-là même sous lequel la purge retire — impossible plutôt que rattrapé. Les six autres accès au registre ont été revus un par un, tous déjà sûrs

### L'annulation
- [x] Annuler un lot interrompt réellement une passe longue en cours, et le sous-processus Kumiko est tué et non laissé orphelin. **Fait le 2026-09-08, `407cf95`** : un interrupteur PAR FIL (`pipeline/interruption.py`), consulté par `run_kumiko` entre deux tranches d'attente et par l'OCR entre deux régions. Le délai entre le clic et l'arrêt tombe de 300 s à une demi-seconde. **La seconde moitié de la case était fausse** : mesuré, `subprocess.run(timeout=…)` tue déjà l'enfant dans ses deux clauses `except` — l'orphelin n'existait pas, et c'est le passage à `Popen` qui en prend la charge
- [x] Un test couvre l'annulation d'un job long sans laisser de processus résiduel. **Fait le 2026-09-08, `407cf95`** : un VRAI sous-processus, et le test ne demande à aucun outil système s'il vit — il regarde s'il TRAVAILLE encore, seule forme portable entre Windows et l'image Linux. Il garde une propriété que le correctif pouvait DÉTRUIRE, pas une qu'il apporte
- [x] **L'interrupteur passe par le FIL et non par les signatures.** Case ajoutée : le choix se mesure, il ne se devine pas. Neuf doublures de test remplacent `segment_planche` par un `lambda c, pid` — un paramètre de plus les cassait toutes, pour rendre visible dans quatre signatures une chose qui n'intéresse qu'un appelant. C'est aussi l'idiome du dépôt pour l'agent courant du journal

## Ce que la lecture du code a trouvé, avant d'y toucher — 2026-09-08

Chantier ouvert, les deux fichiers lus en entier. Le fond des trois constats tient, comme
la revérification du 2026-09-07 le disait. Mais **trois des cinq cases cachaient une
décision ou un piège**, et deux d'entre elles auraient produit un défaut en étant suivies à
la lettre. C'est le genre de chose qu'on ne voit pas en relisant l'énoncé : il fallait
ouvrir le code.

**1. Rétrécir `_crop_lock` au dictionnaire seul provoquerait un accès après fermeture.**
L'énoncé d'origine — « ne couvre plus que la manipulation du dictionnaire de cache » — est
séduisant et faux. `_crop_cache` ne garde qu'UNE image, et changer de planche FERME la
précédente. Avec un verrou réduit au dictionnaire : le thread A prend `img` du cache, le
thread B change de planche et ferme cette image-là, A travaille sur un objet fermé. Le
verrou large est précisément ce qui l'empêche aujourd'hui — il est trop large, il n'est pas
gratuit.

La coupe sûre n'est donc pas celle qu'annonçait la case. `_open_image` doit rester dedans
(il peuple le cache), le `crop` aussi (il lit l'image partagée) ; **le resize et l'encodage
PNG peuvent sortir**, parce qu'ils travaillent sur un objet neuf, local au thread, que
personne d'autre ne référence. C'est aussi la part la plus chère, donc le gain reste réel —
mais il fallait le redécrire pour ne pas l'obtenir en cassant autre chose.

**2. Un TTL paresseux ne répond pas à la case qui le demande.** Vérifier l'échéance à
chaque appel de `region_crop_png` ne ferme rien quand plus personne n'appelle — or c'est
exactement le cas visé : un master de 50 Mo résident parce que la personne est partie. Le
TTL suppose donc un fil de fond, c'est-à-dire un objet vivant de plus dans un module qui
n'en a aucun. Ce n'est pas un détail d'implémentation, c'est le seul arbitrage du chantier.

**3. La purge de `_jobs` armerait un fail-open qui existe déjà.** Vérifié aux quatre
appelants :

```python
# main.py, _job_visible
return set(jobs.planches_du_job(job_id)) <= autorisees
```

`planches_du_job` rend `[]` pour un identifiant inconnu, et **l'ensemble vide est inclus
dans tout** : la garde répond `True` sur un job qui n'existe pas. Rien ne fuit aujourd'hui,
et il faut le dire précisément — `GET /api/jobs/{id}` teste `snapshot(...) is None` avant,
`GET /api/jobs` n'énumère que ce qui existe, et `POST …/annuler` retombe sur le 404 de
`cancel_job`. **La primitive est permissive ; ce sont les ordres de vérification à chaque
appel qui sauvent.** Correct par accident, pas par construction — la forme que ce dépôt
connaît par cœur.

Ce qui change avec la purge : « job inconnu » cesse d'être un cas rare — quelqu'un tape un
mauvais numéro — pour devenir **l'état final de tous les jobs**. Le ressort mal ancré passe
d'inerte à chargé. D'où la case ajoutée AVANT celle de la purge : durcir `_job_visible`
d'abord, purger ensuite.

**Aucun code n'avait été écrit à ce stade**, et c'était délibéré : ce chantier touche du
verrou et de l'autorisation, la suite ne pouvait pas être lancée à ce moment-là, et un
correctif de concurrence qu'aucun test n'a vu rougir ne prouve rien. Ces trois constats
sont ce qui se mesure sans rien exécuter ; ils changent l'ORDRE du chantier, ce qui était
le plus utile à établir en premier.

**Le code est venu ensuite, le même jour, une fois la suite disponible** — la zone du
registre dans l'ordre que ces constats imposaient. Ce paragraphe reste ici parce qu'il date
une méthode et non un état : mesurer d'abord ce qui se mesure sans rien exécuter a produit
l'ordre, et l'ordre a évité de charger un ressort mal ancré.

## L'annulation, et le défaut qu'elle a révélé AILLEURS — 2026-09-08

**Le `finally` de `run_kumiko` est le cœur du correctif, et il ne corrige rien** : il
RESTITUE. `subprocess.run` tuait l'enfant gratuitement ; `Popen`, qu'il fallait pour
devenir interruptible, laisse cette charge à l'appelant. Sans ces trois lignes, ce commit
créerait l'orphelin que la case lui demandait de fermer. C'est le troisième cas du
chantier où l'énoncé d'une case décrivait un défaut absent — et le seul où le suivre à la
lettre aurait quand même produit le bon code, par accident.

**Deux défauts trouvés par les tests, toujours.** Le `finally` appelait `communicate()`
sans délai : sur un enfant qui ne répond pas, son exception REMPLAÇAIT celle qui sortait du
`try`, et un dépassement de délai devenait un `TimeoutExpired` nu. Et la doublure du test
de délai cédait après ses 10 000 tranches, plus vite que l'échéance qu'elle devait laisser
expirer — un test qui ne mesurait pas ce qu'il croyait.

**Ce qui est SIGNALÉ et non traité, parce qu'il est plus large que ce chantier.**
`journal.passe_ml` clôt toute exception sur `echec: True`, et une passe interrompue y
entrerait comme une panne — dans une couche append-only, donc incorrigeable. La branche
`interrompu` a été écrite puis RETIRÉE, et la mesure explique pourquoi : aujourd'hui une
passe RATÉE ne laisse **aucune** trace au journal — lot en erreur, table `activite` vide —,
le `rollback` du worker effaçant l'enregistrement qui la décrit. Une branche `interrompu`
y serait du code que rien ne peut rendre vrai. Le défaut est antérieur, il touche la couche
dont la raison d'être est de dire qui a produit quoi, et il appelle une décision sur la
frontière transactionnelle entre provenance et données.

**Traité le jour même, `133de65`**, et cette ligne est ajoutée plutôt que le paragraphe
ci-dessus réécrit : il dit ce qui était vrai au moment du correctif d'annulation, et le
relire ainsi est le seul moyen de comprendre pourquoi la branche `interrompu` y avait été
retirée. `passe_ml` défait désormais la transaction lui-même puis réinscrit une activité
complète ; la branche `interrompu` est revenue avec elle, observable donc testable.

## Le TTL, et ce que le test a trouvé dans le correctif — 2026-09-08

**Deux défauts, et le premier était dans le correctif lui-même.** Écrite avec un simple
`return` quand l'échéance n'est pas atteinte, la minuterie laissait le master résident pour
de bon dès qu'elle se réveillait avant l'heure. Elle se réarme désormais sur le temps qui
RESTE. C'est le deuxième défaut de concurrence introduit par un correctif de concurrence
dans ce chantier — après la course sur `all_jobs`. Le rapprochement vaut d'être écrit : les
deux étaient invisibles à la lecture et visibles à l'exécution.

**Le second était dans le TEST**, et il est de la famille qui inquiète le plus. Mon
assertion sur le réarmement voyait la minuterie armée par le CROP, pas un réarmement : la
mutation qui supprime le réarmement passait au vert. Une assertion increvable ne vaut pas
mieux que pas d'assertion, et celle-ci prétendait garder la ligne qui venait de manquer.
Le test efface la minuterie avant d'appeler son corps, ce qui reconstitue l'état du réveil
anticipé — le seul où le réarmement porte quelque chose.

Quatre mutations tiennent la zone : minuterie jamais armée · contrôle d'âge supprimé (elle
fermerait une image qui vient de servir — la course que `Timer.cancel()` ne rattrape pas,
une minuterie DÉJÀ partie ne s'annule plus) · réarmement supprimé · porte de sortie à TTL
nul ignorée.

**Et `crop.load()`, posé le matin même sous le verrou, est devenu load-bearing** : la
minuterie ferme le master de façon ASYNCHRONE, si bien qu'un crop non matérialisé relirait
une image fermée par un fil qui n'existait pas quand cette ligne a été écrite. Elle avait
été écrite pour ne pas faire reposer une propriété de sûreté sur un accident
d'implémentation ; elle protège aujourd'hui d'une cause qui n'existait pas encore.

## Ce que la passe de revue a trouvé dans ces trois correctifs — 2026-09-08

Suite verte, trois zones closes, six mutations rouges chacune pour sa propre raison. La
revue d'après-coup a quand même trouvé quatre choses, et **la première est un défaut de
concurrence introduit par le correctif d'un défaut de concurrence** — l'objet même de ce
chantier, dans du code écrit pour le fermer.

**1. La purge a ouvert une course sur `all_jobs`** (`fc406b0`, case ci-dessus). Le point
de méthode : la purge a été relue pour ce qu'elle AJOUTE — un plafond — et pas pour ce
qu'elle CHANGE dans les invariants des autres fonctions. « Le registre ne perd jamais
rien » était une propriété non écrite dont un lecteur dépendait.

**2. La coupe du verrou de crop avait un prix, et il n'était pas écrit** (`a163761`). Le
verrou large bornait AUSSI la mémoire : un seul crop décodé à la fois. Chaque thread tient
désormais le sien. Négligeable en régime réel, pas au plafond de `MAX_IMAGE_PIXELS`. Non
mesuré, donc non borné — poser un sémaphore sur une hypothèse serait ce que ce chantier
refuse. Le prix est écrit à côté du gain, faute de quoi il se paierait plus tard et par
quelqu'un qui ne saurait pas d'où il vient.

**3. Un test du registre polluait le suivant sur son chemin d'échec** (dans `fc406b0`).
`test_un_lot_purge_n_est_visible_de_personne` injectait dans le registre RÉEL et ne le
défaisait qu'en cas de succès. Même famille que le `_counter` global attrapé le matin même :
un test écrit pour prouver, qui laisse une chance au hasard.

**4. Trois renvois de ligne sur cinq désignaient autre chose** dans
`docs/hebergement-securite.md` (`9917c1c`), dont un que `e17556c` venait de casser en
déplaçant `_jobs`. Le pire pointait sur `failed += 1` — du code réel, plausible, sans
rien qui signale l'erreur.

**Et une cinquième, laissée ouverte exprès** : le balayage mécanique trouve **30 renvois de
ligne** dans les documents VIVANTS (`docs/`, `pilotage/`, `CLAUDE.md`) — cinq pointent sur
une ligne VIDE, donc certainement morts ; les autres demandent une lecture une par une, et
une décision qui n'appartient pas à ce chantier : un renvoi dans une case OUVERTE égare
aujourd'hui, un renvoi dans un récit DATÉ est une trace qu'on ne réécrit pas. `AUDIT.md` en
est écarté à dessein — c'est un audit daté, ses renvois décrivent l'état du code au jour de
l'audit.

## Contexte

Effort M, priorité P3. Fuite lente : invisible en session courte, sensible sur un serveur
qui tourne des jours — donc un problème qui n'apparaîtra vraiment qu'**après** INFRA-1.
**Cette condition est remplie depuis le 2026-09-05** : l'instance sert en continu sur
`bd.edito-revue.fr`, et c'est le régime où une fuite lente se mesure au lieu de se déduire.

**Les trois constats ont été REVÉRIFIÉS au code le 2026-09-07, et ils tiennent tels
quels** — seuls les numéros de ligne avaient dérivé, et ils ont été remplacés par des noms.
Le verrou enveloppe bien l'ouverture du master, le crop, le resize et l'encodage ; le
master n'est fermé qu'à l'ouverture d'une AUTRE planche ; `_jobs` n'a toujours aucune
purge. Un audit qui vieillit fait douter de son fond alors que c'est souvent son adressage
qui a bougé : ici le fond était intact.

Recoupe CONC-2 : les deux parlent de cycle de vie des ressources, mais CONC-2 traite des
modèles ML (RAM, OOM) et CONC-1 des ressources d'application (fichiers ouverts, verrous,
registres). Ne pas les fusionner : les correctifs ne touchent pas les mêmes fichiers.
