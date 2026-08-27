---
chantier: CONC-1
statut: à venir
---

# CONC-1 — cache de crop, purge des jobs, annulation préemptive

**Point de départ** — trois défauts de cycle de vie relevés à l'audit, jamais repris :
verrou de crop trop large, registre de jobs sans purge, annulation non préemptive.

## Reste

- [ ] Le verrou `_crop_lock` (`pipeline/ocr.py:138`) ne couvre plus que la manipulation du dictionnaire de cache : il enveloppe aujourd'hui l'ouverture du master, le crop, le resize LANCZOS et l'encodage PNG (`:155-178`), tout sérialisé
- [ ] Un TTL ferme le master gardé ouvert dans `_crop_cache` (`pipeline/ocr.py:135`), qui n'est fermé aujourd'hui qu'à l'ouverture d'une AUTRE planche — un master de 50 Mo reste donc résident indéfiniment
- [ ] Le registre `_jobs` (`pipeline/jobs.py:19`) est purgé de ses entrées anciennes, et sa taille ne croît plus indéfiniment
- [ ] Annuler un lot interrompt réellement une passe longue en cours, et le sous-processus Kumiko est tué et non laissé orphelin
- [ ] Un test couvre l'annulation d'un job long sans laisser de processus résiduel

## Contexte

Effort M, priorité P3. Fuite lente : invisible en session courte, sensible sur un serveur
qui tourne des jours — donc un problème qui n'apparaîtra vraiment qu'**après** INFRA-1.

Recoupe CONC-2 : les deux parlent de cycle de vie des ressources, mais CONC-2 traite des
modèles ML (RAM, OOM) et CONC-1 des ressources d'application (fichiers ouverts, verrous,
registres). Ne pas les fusionner : les correctifs ne touchent pas les mêmes fichiers.
