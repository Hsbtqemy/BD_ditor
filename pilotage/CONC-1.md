---
chantier: CONC-1
statut: à venir
audit: AUDIT.md
---

# CONC-1 — cache de crop, purge des jobs, annulation préemptive

**Point de départ** — trois défauts de cycle de vie relevés à l'audit, jamais repris :
verrou de crop trop large, registre de jobs sans purge, annulation non préemptive.

## Reste

- [ ] Le verrou `_crop_lock` (`pipeline/ocr.py`) ne couvre plus que la manipulation du dictionnaire de cache : il enveloppe aujourd'hui **tout le corps de `region_crop_png`** — l'ouverture du master par `_open_image`, le crop, le resize LANCZOS et l'encodage PNG —, tout sérialisé
- [ ] Un TTL ferme le master gardé ouvert dans `_crop_cache` (`pipeline/ocr.py`), qui n'est fermé aujourd'hui qu'à l'ouverture d'une AUTRE planche — un master de 50 Mo reste donc résident indéfiniment
- [ ] Le registre `_jobs` (`pipeline/jobs.py`) est purgé de ses entrées anciennes, et sa taille ne croît plus indéfiniment
- [ ] Annuler un lot interrompt réellement une passe longue en cours, et le sous-processus Kumiko est tué et non laissé orphelin
- [ ] Un test couvre l'annulation d'un job long sans laisser de processus résiduel

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
