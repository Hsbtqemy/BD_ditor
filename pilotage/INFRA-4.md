---
chantier: INFRA-4
statut: à venir
---

# INFRA-4 — retirer l'instrumentation import-timing

**Point de départ** — dette propre et assumée, posée pour mesurer la vitesse d'import sur
le VPS. La mesure n'avait pas été faite, faute de VPS (INFRA-1).

**Le blocage est LEVÉ — 2026-09-05.** INFRA-1 est livré : l'instance sert en HTTPS sur
`bd.edito-revue.fr`, et la mesure que cette instrumentation attendait est devenue faisable.
Elle n'a toujours PAS été prise, et c'est maintenant la seule chose qui retienne le
chantier — l'ordre des deux cases ci-dessous compte plus qu'avant, pas moins.

## Reste

- [ ] La mesure de vitesse d'import a effectivement été faite sur le VPS, et son résultat est écrit quelque part de durable
- [ ] L'unique trace restante est retirée — dans `main.py`, un `print("[import-timing] …")` chronométrant `download` / `derive` / `segment` dans la boucle d'import — et une recherche de `import-timing` ne renvoie plus rien. **Toujours unique au 2026-09-07**, vérifié : une seule occurrence dans tout le dépôt
- [ ] La suite de tests reste verte après retrait

## Contexte

Effort S, priorité P2. La seule subtilité est l'ordre : retirer l'instrumentation avant
d'avoir pris la mesure ferait perdre la raison même de l'avoir posée — d'où la première
case, qui n'est pas du code.

Dépendait donc d'INFRA-1 dans les faits, sans en dépendre techniquement — **verrou levé le
2026-09-05** (cf. l'entête). Ce qui retient le chantier n'est plus une attente mais un
geste : aller prendre la mesure sur une instance qui tourne.
