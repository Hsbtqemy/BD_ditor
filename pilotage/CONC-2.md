---
chantier: CONC-2
statut: interrompu
---

# CONC-2 — isolation subprocess des moteurs ML (v2)

**Arrêté sur** — 2026-11-25, `f2d7932` : **ROUVERT**, sur la condition que l'abandon avait
écrite — un process d'API réellement tué, observé et daté. En production, le conteneur a été
tué deux fois par manque de mémoire le 2026-11-25 (la dernière à 13:00 UTC), 2,4 Go au plus
haut. Trois commits sur `dev` : plus de va-et-vient entre les modèles torch, déchargés
ensemble après dix minutes sans passe, et `malloc_trim` (`75adff9`) ; `MALLOC_ARENA_MAX=2`
dans l'image (`fd04b9f`) ; une passe automatique à la fois dans l'Atelier (`f2d7932`). Ni
poussés ni déployés : la mesure en production et la limite mémoire du conteneur restent à
faire.

Avant cela, 2026-09-02 : **ABANDONNÉ**, la question de fond enfin tranchée. Le
`Reste` restait ouvert exprès — c'était le sens de ce statut : la fiche garde son raisonnement
au lieu d'être supprimée avec lui. Une seule case a été cochée en fermant, celle qui
survit à l'abandon (l'empreinte mémoire), et sa mesure est partie dans
`docs/deploiement-docker.md` § 2, où un déployeur la cherchera.

Avant cela, `63c221c`, 2026-08-31 : une case avait été traitée SANS rouvrir le chantier et
sans rapport avec l'isolation — un lot qui meurt hors du `try` par passe s'annonçait
« terminé », il s'annonce désormais en `echec` avec la panne nommée.

Avant lui, 2026-06-26, `b9743bd` : la v1 est livrée (déchargement par moteur,
orchestrateur `pipeline/modeles.py`, libération en fin de lot et avant passe interactive,
route `POST /api/ml/liberer`, modèles résidents exposés dans `/api/sante`). L'option (c),
seule à garantir le zéro-OOM, est restée dehors.

## Reste

### L'isolation des moteurs (v2)

- [ ] Les moteurs ML tournent dans un process séparé de l'API, redémarrable, de sorte qu'un OOM du worker n'emporte pas le serveur
- [x] **Un lot qui MEURT le dit** (2026-08-31, `63c221c`). Deux lectures SQLite échappent au `try` par passe — l'ouverture de la connexion et la relecture du verrou —, donc deux « database is locked » possibles, exactement ce que le WAL et le 409 d'`OperationalError` gèrent partout ailleurs. Le `finally` posait alors « terminé » : mesuré `statut=termine done=0/3 erreurs=[]`, une réussite AFFIRMÉE sur un lot mort à la première planche. Il pose `echec`, la panne est collectée et nommée, la barre passe au rouge. **L'annulation prime** : demandée avant la panne, c'est elle qui explique l'arrêt. La trace part sur stderr sans relever l'exception — « database is locked » ne dit pas OÙ, et relever laisserait mourir un thread daemon sur une exception non traitée
- [ ] Le worker se relance seul après un kill — c'est l'isolation subprocess, et il n'y a pas d'autre façon de l'obtenir. **L'autre moitié de cette case était inexacte** et le reste : un lot ne peut pas être « laissé en *en cours* pour toujours », le registre vivant en RAM (`pipeline/jobs.py`, threads daemon) — un process tué l'emporte avec lui plutôt que de le figer. Il ne reste donc aucune trace du lot perdu, ce qui est un autre défaut, non traité
- [ ] Enchaîner segmentation, bulles, OCR puis NLP sur une vraie planche ne tue plus le process de l'API, reproduit sur la machine où l'OOM du 2026-06-24 avait été observé
- [x] **L'empreinte mémoire est documentée, et la recommandation de dimensionnement avec** (2026-09-02) : pic mesuré 1,216 Gio pour les trois passes enchaînées sur un vrai master, d'où 4 Go recommandés. La mesure vit maintenant dans `docs/deploiement-docker.md` § 2 — le guide n'y disait RIEN du dimensionnement, on louait un VPS sans savoir lequel. C'est la seule case qui survit à l'abandon, et elle sert INFRA-1 sans rien devoir à l'isolation

### La mémoire en production (2026-11-25)

- [x] **Les passes interactives ne font plus de va-et-vient entre les modèles torch** — attendu : la passe des bulles ne décharge plus l'OCR, ni l'OCR les bulles ; les deux partent ensemble après `BD_TTL_MODELES` sans passe (600 s par défaut), une passe en cours repousse l'échéance, spaCy reste chargé (`75adff9`, `tests/test_conc2_memoire_ml.py`)
- [x] **Un déchargement rend la mémoire au système** — attendu : `malloc_trim(0)` après tout déchargement (`75adff9`), et `MALLOC_ARENA_MAX=2` dans l'étape `runtime` de l'image (`fd04b9f`)
- [x] **L'Atelier ne lance qu'une passe automatique à la fois** — attendu : pendant une passe, un second clic sur une entrée du menu ⚙ Traitement dit « … : déjà en cours » et n'envoie aucune requête (`f2d7932`, `test_une_passe_automatique_a_la_fois`)
- [ ] **En production, la mémoire redescend quand les passes s'arrêtent** — attendu : après le déploiement, sur une journée d'annotation où des passes tournent, `docker exec bd-app grep -E 'VmRSS|VmHWM' /proc/1/status` donne un `VmHWM` sous 1,5 Go, et un `VmRSS` sous 600 Mo quinze minutes après la dernière passe
- [ ] **Le conteneur a une limite mémoire** — attendu : `mem_limit` et `memswap_limit`, égaux, dans `deploy/docker-compose.yml` : 2 Go d'abord, 1,5 Go une fois la case précédente mesurée. Décision de Hugo : le VPS a 3,8 Go, partagés avec d'autres projets
- [ ] **« Éprouver » ne laisse pas torch dans l'application** — attendu : dans l'Administration, 🩺 Moteurs, « Éprouver » sur une instance où aucune passe n'a tourné, puis `docker exec bd-app grep VmRSS /proc/1/status` : la mémoire n'a pas pris les quelques centaines de Mo d'`import ultralytics` et d'`import easyocr`, qui restent jusqu'au redémarrage (`sante._verifier_bulles`, `_verifier_ocr` importent DANS le processus ; vu le 2026-11-26 en mettant spaCy en veille, `NLP-4`)

## Contexte

**Rouvert le 2026-11-25, et la prémisse de l'abandon ne tient plus.** Le VPS de production a
2 cœurs et 3,8 Go, swap de 2 Go presque plein, et héberge d'autres projets ; l'abandon
reposait sur une mesure faite dans un conteneur de 8,17 Go, sur UNE séquence de passes. Ce
jour-là, plusieurs personnes annotaient : `bd-app` tenait 1,8 Go et un cœur à 100 %, et a été
tué deux fois (`OOMKilled`). Ce qu'ont montré les mesures, dans l'ordre :

- 55 minutes après le redémarrage, `VmRSS` 1,75 Go, `VmHWM` 2,4 Go, 19 fils ;
- une quarantaine de passes lancées À LA MAIN depuis l'Atelier en douze heures, dont l'OCR
  de la planche 1302 cinq fois de suite, et un lot ;
- `/api/sante` : l'OCR et spaCy chargés, les bulles non. `POST /api/ml/liberer` les a bien
  déchargés (`modeles_charges` tout à faux), et la mémoire est passée de 1,94 à 2,12 Go au
  lieu de baisser : glibc ne rendait rien. C'est la FRAGMENTATION, nourrie par le
  va-et-vient — chaque passe déchargeait l'autre modèle torch pour charger le sien ;
- ni le trafic d'annotation (1 855 `PUT /api/regions/N` et 2 231 empreintes en une heure,
  quelques requêtes SQL chacune, sans image), ni le journal WAL (vide), ni un import (aucun
  en douze heures) n'expliquaient la mémoire. Le `%CPU` de `docker top` (10 %) est une
  moyenne sur la vie du process : le cœur saturé l'est par pics, pendant les passes.

**Le 2026-11-26, la base n'était pas celle qu'on croyait.** Redémarré, `bd-app` tenait 531 Mo
au bout de 33 secondes, aucun modèle de passe chargé : spaCy y faisait venir torch (thinc
l'importe s'il est installé). L'application seule pèse 70 Mo dans l'image, avec spaCy 498 Mo.
spaCy est mis en veille dans l'application et rattrapé la nuit dans un processus à part
(`NLP-4`). Après une passe, torch reste importé même modèles déchargés (mesuré : environ
160 Mo) : le seuil de 600 Mo de la case « En production » en tient compte.

**L'isolation (v2) retrouve un mérite que la v1 n'a pas** : la mémoire d'un sous-process
revient au système à sa sortie, entière, ce que ni `malloc_trim` ni les réserves bornées ne
garantissent. Elle reste ouverte ; la mesure de la case « En production » dira si elle
devient nécessaire.

**PRÉMISSE À RÉEXAMINER (mesure du 2026-08-27).** Dans un conteneur à 8,17 Go, avec le
torch CPU, les **trois moteurs chargés ensemble tiennent dans 833,6 Mio** — application
seule 49,7 Mio, + spaCy 143,4, + YOLOv8 826,4, + EasyOCR 833,6. Soit ~10 % de la mémoire
disponible, très loin d'un OOM.

L'OOM du 2026-06-24 a probablement été causé par le **torch CUDA**, retiré depuis
(`7171040`) : il charge les runtimes CUDA en mémoire même sans GPU.

**Confirmé sur un VRAI master** (`corpus/album_2/planche_0002.tif`, 3748×4710, 17,7 Mpx,
400 dpi), les trois passes enchaînées dans un seul conteneur : app + spaCy 173 Mio →
import 407,7 Mio → segmentation 410,5 Mio → bulles 779 Mio → OCR **1,036 Gio**, **pic
observé 1,216 Gio**. Soit **15 % des 8,17 Go**. Résultats réels : 12 cases, 24 bulles,
24 régions avec texte OCR.

**La raison d'être de cette fiche a donc disparu.** Elle existait pour garantir le
zéro-OOM ; l'OOM venait du torch CUDA, pas de l'architecture. Reste à trancher : la
clore, ou l'abandonner en gardant son `Reste` comme trace du raisonnement. L'isolation
subprocess garde un mérite propre — un crash du worker n'emporte pas l'API — mais ce
n'est plus le même chantier, ni la même urgence, et il faudrait le réécrire sous cet
angle.

**L'OOM n'était pas théorique** : observé le 2026-06-24 en annotant une vraie planche, le
process tué SANS traceback Python. Les données committées étaient saines — c'est le seul
point rassurant.

La v1 libère, mais ne peut pas garantir le zéro-OOM : tant qu'un modèle torch est chargé,
le runtime occupe la RAM. Seule l'isolation en process séparé le garantit, d'où cette v2.

Contournement immédiat, toujours valable : lancer les passes ML séparément et redémarrer
entre les grosses.

Lien direct avec INFRA-1 : un VPS contraint atteindra cette limite avant un poste de dev.
Traiter CONC-2 v2 avant ou pendant le déploiement, pas après le premier incident.

## La décision, et ce qui la rouvrirait (2026-09-02)

**ABANDONNÉ.** Ce chantier existait pour garantir le zéro-OOM ; l'OOM venait du torch
CUDA, retiré depuis (`7171040`). Sur la mesure qui compte — les trois passes enchaînées
sur un vrai master, dans un conteneur de 8,17 Go — le pic est de **1,216 Gio, soit 15 %**.
Isoler les moteurs pour se prémunir de ce chiffre-là serait payer une architecture entière
contre un risque qu'on a mesuré absent.

**Le mérite résiduel est réel et nommé** : un crash du worker n'emporterait pas l'API.
C'est un autre chantier — la RÉSILIENCE, pas la mémoire — et on n'en ouvre pas la fiche,
parce que rien ne l'a demandé : depuis le retrait du torch CUDA, aucune mort de process
n'a été observée. Ouvrir un chantier sur une panne qu'on n'a pas vue, c'est fabriquer de
la dette qui a l'air d'une prévoyance.

**Ce qui rouvre le dossier**, et il faut que ce soit écrit sinon la décision se rejouera de
mémoire : un process d'API réellement tué par une passe ML, observé et daté. Deux traces
en donneraient le signal — un lot en `echec` portant une panne qui n'est pas
« database is locked » (`pipeline/jobs.py` les nomme depuis `63c221c`), ou un redémarrage
d'uvicorn sans traceback Python. La première est visible dans l'écran des lots, la seconde
dans les journaux du conteneur. **C'est arrivé le 2026-11-25** (cf. le haut du Contexte).

**Un défaut connexe reste non traité et sans fiche** : le registre des lots vit en RAM
(`pipeline/jobs.py`, threads démons), donc un process tué l'emporte avec lui — il ne reste
aucune trace du lot perdu. C'est noté ici plutôt qu'ailleurs parce que c'est le même
raisonnement : il ne coûte rien tant que le process ne meurt pas.
