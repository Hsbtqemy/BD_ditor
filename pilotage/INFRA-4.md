---
chantier: INFRA-4
statut: à venir
---

# INFRA-4 — retirer l'instrumentation import-timing

**Point de départ** — dette propre et assumée, posée pour mesurer la vitesse d'import sur
le VPS. La mesure n'a pas encore été faite, faute de VPS (INFRA-1).

## Reste

- [ ] La mesure de vitesse d'import a effectivement été faite sur le VPS, et son résultat est écrit quelque part de durable
- [ ] L'unique trace restante est retirée — `main.py:914`, un `print("[import-timing] …")` dans la boucle d'import — et une recherche de `import-timing` ne renvoie plus rien
- [ ] La suite de tests reste verte après retrait

## Contexte

Effort S, priorité P2. La seule subtilité est l'ordre : retirer l'instrumentation avant
d'avoir pris la mesure ferait perdre la raison même de l'avoir posée — d'où la première
case, qui n'est pas du code.

Dépend donc d'INFRA-1 dans les faits, sans en dépendre techniquement.
