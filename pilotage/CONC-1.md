---
chantier: CONC-1
statut: à venir
audit: AUDIT.md
---

# CONC-1 — cache de crop, purge des jobs, annulation préemptive

**Point de départ** — trois défauts de cycle de vie relevés à l'audit, jamais repris :
verrou de crop trop large, registre de jobs sans purge, annulation non préemptive.

## Reste

### Le verrou de crop
- [ ] **Le resize LANCZOS et l'encodage PNG sortent du verrou `_crop_lock`** (`pipeline/ocr.py`), qui enveloppe aujourd'hui tout le corps de `region_crop_png` — ouverture du master par `_open_image`, crop, resize, encodage —, tout sérialisé. **L'attendu d'origine disait « ne couvre plus que la manipulation du dictionnaire de cache » : il est FAUX, et l'appliquer casserait quelque chose** — voir la section datée ci-dessous. `_open_image` et le `crop` restent dedans ; ce qui sort, ce sont les deux étapes qui travaillent sur un objet neuf et local au thread
- [ ] Le gain est MESURÉ et non supposé : l'encodage PNG d'un crop de 1600 px est la part la plus chère de l'appel, et c'est ce qui justifie la coupe. Sans mesure, on aura déplacé une accolade

### Le master résident
- [ ] Un TTL ferme le master gardé ouvert dans `_crop_cache` (`pipeline/ocr.py`), qui n'est fermé aujourd'hui qu'à l'ouverture d'une AUTRE planche — un master de 50 Mo reste donc résident indéfiniment
- [ ] **Le porteur du TTL est tranché par écrit, parce qu'un contrôle paresseux ne répond PAS à la case ci-dessus** : vérifier l'échéance à chaque appel ne ferme rien quand plus personne n'appelle, c'est-à-dire exactement le cas visé. Il faut un fil de fond, donc un objet vivant de plus dans un module qui n'en a aucun — arbitrage, pas implémentation

### Le registre des jobs
- [ ] **`_job_visible` distingue « job inconnu » de « job dont toutes les planches sont autorisées », AVANT toute purge.** `main.py` fait `set(jobs.planches_du_job(job_id)) <= autorisees` : pour un identifiant inconnu, `planches_du_job` rend `[]`, l'ensemble vide est inclus dans tout, et la garde répond **True**. Aucune fuite aujourd'hui — les quatre appelants testent l'existence par ailleurs — mais la primitive est permissive et ce sont les ORDRES de vérification qui sauvent
- [ ] Le registre `_jobs` (`pipeline/jobs.py`) est purgé de ses entrées anciennes, et sa taille ne croît plus indéfiniment. **Dans cet ordre seulement** : la purge fait passer « job inconnu » d'un cas rare — quelqu'un tape un mauvais numéro — à l'état FINAL de tous les jobs

### L'annulation
- [ ] Annuler un lot interrompt réellement une passe longue en cours, et le sous-processus Kumiko est tué et non laissé orphelin
- [ ] Un test couvre l'annulation d'un job long sans laisser de processus résiduel

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

**Aucun code n'a été écrit**, et c'est délibéré : ce chantier touche du verrou et de
l'autorisation, la suite ne pouvait pas être lancée pendant cette session, et un correctif
de concurrence qu'aucun test n'a vu rougir ne prouve rien. Ces trois constats sont ce qui
se mesure sans rien exécuter ; ils changent l'ORDRE du chantier, ce qui était le plus utile
à établir en premier.

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
