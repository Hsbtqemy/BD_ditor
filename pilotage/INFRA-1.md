---
chantier: INFRA-1
statut: interrompu
---

# INFRA-1 — déploiement Docker réel sur le VPS

**Arrêté sur** — 2026-08-27, `3720f9f` : l'image est corrigée avant tout build (verrou
QA-1 scindé runtime/dev et installé, modèle `fr_core_news_sm` ajouté). Reste ce qui exige
une machine avec Docker, puis le VPS.

## Reste

### Image — écrite, jamais construite
- [ ] `deploy/Dockerfile` se construit réellement jusqu'au bout : le clone Kumiko, l'install de `requirements-ocr.txt` et les wheels torch passent, et le poids final de l'image est relevé et noté
- [x] Le Dockerfile installe spaCy ET télécharge `fr_core_news_sm` — il n'installait que `requirements.txt` + `requirements-ocr.txt` + `requests`, donc aucun des deux
- [x] Le Dockerfile installe depuis `requirements.lock` (verrou QA-1) et non depuis des bornes `>=` ouvertes
- [x] Les outils de test n'entrent PAS dans l'image : le lock a été scindé en `requirements.lock` (runtime, 12 pins) et `requirements-dev.lock` — un lock unique aurait embarqué Playwright
- [ ] Le conteneur démarre et sert l'application, volume `bd-data` monté sur `/data` (`BD_DATA_DIR` et `HOME` y pointent déjà dans le Dockerfile, pour que les modèles ML ne soient téléchargés qu'une fois)
- [ ] Un redémarrage de conteneur ne perd ni la base, ni `corpus/`, ni les modèles téléchargés

### Déploiement — jamais lancé
- [ ] `deploy/docker-compose.yml` (app + redis + authelia + caddy) monte réellement sur le VPS
- [ ] `GET /api/sante` sur l'instance déployée annonce le NLP **disponible** — c'est le seul contrôle qui prouve que le modèle a bien suivi jusqu'en production
- [ ] Une requête non authentifiée est refusée par Authelia avant d'atteindre l'application
- [ ] La déconnexion fonctionne de bout en bout depuis l'UI, pas seulement via la route `/api/moi`
- [ ] Une sauvegarde prise sur le VPS se restaure sur une machine de dev

## Contexte

**P1, effort L — et la fiche qui débloque le plus de choses** : INFRA-3 (credentials
WebDAV par utilisateur), SEC-2 (le volet CSRF, qui n'a de sens qu'avec des sessions) et
EXP-1 (exposer les exports de dépôt dans l'UI) en dépendent tous, et ANN-5 (accord
inter-annotateurs, livré) ne servira vraiment qu'une fois plusieurs annotateurs en ligne.

Le code applicatif est prêt depuis le 26 juin — **et l'infrastructure est écrite aussi** :
`deploy/` contient déjà le Dockerfile (36 lignes, moteurs ML + Kumiko, un seul worker
parce que l'app garde des états en mémoire), le `docker-compose.yml` à quatre services,
le `Caddyfile`, la config Authelia et un `.dockerignore` soigné. Vérifié le 2026-08-27 :
rien de tout cela n'est à écrire.

Ce qui manque est le geste, pas le fichier : **rien n'a jamais été construit ni lancé**.
C'est de l'infrastructure sur une machine qui n'est pas celle-ci — d'où l'arrêt net, et
d'où le fait que deux mois plus tard rien n'a bougé. Le risque n'est donc pas la
conception, c'est ce qu'un premier `docker compose up` révélera.

Attention au dimensionnement mémoire : CONC-2 documente un OOM observé en enchaînant
segmentation, bulles, OCR et NLP sur une vraie planche. Un VPS contraint reproduira ce
problème plus tôt qu'un poste de dev.

**Corrigé le 2026-08-27 (`3720f9f`), mais non vérifié : aucun Docker sur la machine de
dev.** Le premier build reste à faire ailleurs, et c'est lui qui dira si les wheels torch,
le clone Kumiko et le téléchargement du modèle passent. Les trois secrets attendus par
compose, Caddy et Authelia sont en revanche tous documentés dans `deploy/.env.example`
(vérifié) — ce n'est pas là que ça achoppera.

**Le trou du NLP était le plus coûteux, et il était silencieux.** Sans spaCy, `nlp_available()`
vaut False et tout dégrade *proprement* — aucune erreur, aucun log alarmant. Mais la table
`tokens` n'est jamais peuplée, donc `tokens_effectifs` est vide, donc : l'Exploration
(distribution, concordance, croisement, comparaison) ne montre rien, le statut de relecture
(ANN-4) reste « à faire » sur tout le corpus, les rapports d'accord (NLP-1) et inter-annotateurs
(ANN-5) sortent vides, et la recherche perd les lemmes. **Quatre chantiers livrés seraient
morts en production sans qu'aucun message ne le dise.** Vérifié le 2026-08-27 sur le
Dockerfile ; le lock, lui, prévoit déjà `spacy==3.8.14` et documente
`python -m spacy download fr_core_news_sm`.
