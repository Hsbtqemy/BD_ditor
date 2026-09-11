---
chantier: INFRA-4
statut: livré
---

# INFRA-4 — retirer l'instrumentation import-timing

**Arrêté sur** — 2026-09-11, `2c35697` : la mesure est prise, écrite dans `docs/exploitation.md`, et l'instrument est retiré dans le même commit — dans cet ordre-là, qui était toute la subtilité du chantier.

**Point de départ** — dette propre et assumée, posée pour mesurer la vitesse d'import sur
le VPS. La mesure n'avait pas été faite, faute de VPS (INFRA-1).

**Le blocage est LEVÉ — 2026-09-05.** INFRA-1 est livré : l'instance sert en HTTPS sur
`bd.edito-revue.fr`, et la mesure que cette instrumentation attendait est devenue faisable.
Elle n'avait toujours PAS été prise au 2026-09-10, et c'était alors la seule chose qui
retînt le chantier — l'ordre des deux cases ci-dessous compte plus qu'avant, pas moins.

## Reste

- [x] **La mesure est faite sur le VPS, et son résultat est écrit** — 2026-09-11, sept masters TIFF importés depuis ShareDocs par un compte personnel, en deux lots dont un avec segmentation. Le tableau et ce qu'on en tire sont dans `docs/exploitation.md`, section « La vitesse d'import depuis ShareDocs — mesurée ». **Le résultat renverse ce qu'on supposait** : l'import est borné par le RÉSEAU — environ 20 Mo/s, 60 à 90 % du temps d'une planche —, la dérivation coûte 5 ms par Mo et la segmentation moins d'une seconde en régime établi. 3 à 4 s par planche, segmentation comprise
- [x] **L'instrument est retiré, chronomètres compris** — `2c35697`. L'impression seule aurait laissé six variables de chronométrage mortes ; les douze lignes partent ensemble, et une recherche de `import-timing` comme de `perf_counter` ne renvoie plus rien dans `main.py`. `import time` reste : `time.monotonic()` sert ailleurs, au cache des comptes vus
- [x] **La suite reste verte après retrait** — `pytest` (suite par défaut, test `live` compris) sort en 0 le 2026-09-11. Aucun test ne lisait l'instrument, ce qui était attendu : une impression de diagnostic n'a pas de contrat

## Ce que l'instrument a appris en dernier, sur lui-même — 2026-09-11

**Son `0.00` voulait dire « non mesuré », pas « gratuit ».** La première passe a rendu
`segment=0.00s` sur quatre fichiers. Le code initialisait la variable à `0.0` et ne la
remplaçait que si la segmentation était DEMANDÉE — or la case du panneau ShareDocs est
décochée par défaut. Lu tel quel, ce zéro faisait conclure que la segmentation ne coûtait
rien ; il a fallu relire la branche pour voir qu'elle n'avait pas tourné, et relancer un
import case cochée pour obtenir le vrai chiffre.

**La leçon vaut pour tout instrument qu'on reposera** : une valeur par défaut numérique se
lit comme une mesure. Écrire `—`, `n/a` ou omettre le champ quand la phase n'a pas eu lieu
distingue « rien fait » de « fait en zéro seconde » ; `0.00` ne le fait pas. Le tableau de
`docs/exploitation.md` note donc `—` là où l'instrument imprimait `0.00`.

**Et la mesure a réfuté une prévision faite en la demandant** : on attendait que la
segmentation — Kumiko en sous-processus, sous le verrou ML — soit la phase lourde, et c'est
la raison pour laquelle le second lot a été demandé. Elle coûte moins d'une seconde ; le
réseau, lui, fait l'essentiel. Sans le second lot, on aurait retiré l'instrument en gardant
la mauvaise idée.

## Contexte

Effort S, priorité P2. La seule subtilité est l'ordre : retirer l'instrumentation avant
d'avoir pris la mesure ferait perdre la raison même de l'avoir posée — d'où la première
case, qui n'est pas du code.

Dépendait donc d'INFRA-1 dans les faits, sans en dépendre techniquement — **verrou levé le
2026-09-05** (cf. l'entête). Ce qui retient le chantier n'est plus une attente mais un
geste : aller prendre la mesure sur une instance qui tourne.
