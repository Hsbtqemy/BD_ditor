---
chantier: NLP-4
statut: interrompu
---

# NLP-4 — spaCy en veille, et sa place dans le processus

**Arrêté sur** — 2026-11-26, `cdd0710` : spaCy est EN VEILLE en production depuis le
2026-11-26 (`BD_NLP=0`, posé par le compose), et le timer de nuit est posé. Le rattrapage ne
reprend plus chaque nuit les bulles sans mot de contenu (`cdd0710`), et le contrôle de
déploiement lit la veille comme voulue (`9698602`) ; les deux sont déployés. Restent : le
premier passage de nuit à lire, la base de mémoire, que l'épreuve profonde du déploiement
remonte à 440 Mo en chargeant torch (cf. `CONC-2`), et la place définitive de spaCy.

## Reste

### La veille (2026-11-26)

- [x] **`BD_NLP=0` met le moteur en veille sans le désinstaller** — attendu : `nlp_available()` faux, le repli d'un moteur absent, les trois gestes de la grammaire refusés par un 503 nommé APRÈS l'autorisation, 🩺 Moteurs qui dit « en veille » et « Éprouver » qui ne charge rien (`a679f68`, `tests/test_nlp_veille.py`)
- [x] **La nuit rend ce que le jour aurait rendu** — attendu : `tools/reindex_nlp.py --a-rattraper` ne refait que les régions sans lemmes ni tokens, et une région retouchée en veille puis rattrapée a les mêmes tokens, corrections et lemmes que sa jumelle retouchée moteur allumé (`a679f68`) ; l'outil refuse en veille
- [x] **Le déploiement met la veille par défaut** — attendu : `BD_NLP=${BD_NLP:-0}` dans `deploy/docker-compose.yml`, `BD_NLP=1` dans `deploy/.env` le rallume, `deploy/reindex-nlp.sh` commité en 100755 (`ffef851`)
- [x] **Le contrôle de déploiement ne prend pas la veille pour une panne** — attendu : sur une instance en veille, `deploy/verifier_deploiement.py` dit « lemmes en veille (BD_NLP=0) — voulu » et le déploiement passe ; une veille que la voie rapide ignore reste une panne (`9698602`, `tests/test_verifier_deploiement.py`). Le déploiement de `5f0777d` avait été REFUSÉ par ce contrôle ; celui de `cdd0710` est passé le 2026-11-26
- [x] **Le rattrapage ne reprend pas chaque nuit ce qu'il a déjà fait** — attendu : une bulle est reprise quand elle n'a aucun token, et une bulle de ponctuation seule jamais ; une région qui n'a qu'une note, quand sa note n'a pas de lemmes (`cdd0710`, `test_une_bulle_sans_mot_de_contenu_ne_revient_pas_chaque_nuit`, quatre mutants tués). Mesuré en production le 2026-11-26 : avant le correctif, deux passages de suite reprenaient les mêmes 418 régions (362 bulles de mots vides, « Ha Ha », « C'est ça », et 56 sans aucun mot, « ? ») ; après, 3 puis « ✓ Rien à rattraper. »
- [ ] **En production, sans passe, la base de mémoire tombe** — attendu : après le déploiement, `/api/sante` porte `"en_veille":["nlp"]`, et une heure après le démarrage, sans passe automatique, `docker exec bd-app grep VmRSS /proc/1/status` donne moins de 300 Mo (contre 531 Mo le 2026-11-26, spaCy seul chargé). Mesuré le 2026-11-26 : `en_veille` présent ; 78 Mo juste après un redémarrage à la main ; 440 Mo après le déploiement de `cdd0710`, avec torch, torchvision et cv2 dans `/proc/1/maps`, et ni `spacy` ni `thinc`. La veille tient ; ce qui remonte la base est l'épreuve profonde du contrôle de déploiement, qui importe les moteurs de bulles et d'OCR dans l'application (`CONC-2`, case « Éprouver »). La case se coche quand elle est fermée
- [ ] **Le timer de nuit est posé et a tourné** — attendu : `systemctl list-timers bd-reindex-nlp.timer` annonce un passage à 3 h, heure de Paris, et le lendemain `journalctl -u bd-reindex-nlp.service -n 20` finit par « ✓ n région(s) réindexée(s) » ou « ✓ Rien à rattraper. ». Posé le 2026-11-26 (prochain passage annoncé le 2026-11-27 à 02:00 UTC) ; reste le journal du premier passage de nuit

### Une meilleure place pour spaCy

- [ ] **Où spaCy doit vivre est décidé par Hugo** — attendu : l'option retenue écrite ici. (a) n'être appelé qu'à la demande — une relecture grammaticale, une passe en lot — et non plus à chaque écriture de texte ; (b) tourner dans un processus à part, ce qui rejoint l'isolation des moteurs (v2) de `CONC-2` ; (c) rester dans l'application, chargé sans torch (mesuré : 318 Mo au lieu de 498, une astuce d'import à verrouiller)
- [ ] **La relecture grammaticale rouvre** — attendu : dans le mode Transcription de l'Atelier, corriger le lemme d'un mot n'est plus refusé, et après une retouche du texte de la bulle la correction suit son mot

## Contexte

**Le constat, 2026-11-26.** Après le redémarrage forcé de `bd-app` (deux OOM la veille, cf.
`CONC-2`), le processus tenait 531 Mo au bout de 33 secondes, sans aucun modèle de passe
chargé : `/api/sante` disait `bulles: false, ocr: false, nlp: true`, et `/proc/1/maps` portait
`libtorch.so`, `libtorch_cpu.so`, `libtorch_python.so`. Reproduit dans l'image
`bdediteur:suite` : l'application seule pèse 70 Mo, charger spaCy la porte à 498 Mo, et torch
arrive avec lui — thinc l'importe s'il le trouve installé, et il l'est pour les passes. Masqué
pendant le chargement, spaCy seul pèse 318 Mo et lemmatise toujours. Les 173 Mio de la mesure
de septembre (`CONC-2`) venaient d'un conteneur sans torch.

**Pourquoi la veille et pas un déchargement.** Décharger le modèle libère l'objet, pas les
bibliothèques importées : la mesure du 2026-11-25 l'avait montré (`modeles_charges` tout à
faux, la mémoire en hausse). Seul un processus qui se termine rend tout. D'où le rattrapage
dans un processus à part, la nuit, plutôt qu'un chargement suivi d'un déchargement dans
l'application.

**Ce que la veille coûte, et ce qu'elle ne coûte pas.** Aucune donnée : corrections, lemmes
déjà indexés et travail restent en base. La page Annotation n'en dépend pas — ses mots
viennent de `mots.py`. Ce qui s'arrête : la relecture grammaticale dans la journée. Ce qui
attend la nuit : les lemmes et l'Exploration d'une région retouchée. Le 2026-11-26, la base
portait vingt corrections grammaticales, toutes du dernier mois, la dernière le 21 novembre ;
le corpus se constitue, la Recherche et l'Exploration servent peu.

**Une perte trouvée en route, et fermée.** Le ré-ancrage aligne l'ancienne suite de mots sur
la nouvelle. Une écriture sans moteur efface l'ancienne : au rattrapage, toutes les
corrections d'une région retouchée ressortaient orphelines. Ce cas existait déjà — une panne
de spaCy le produisait — ; la veille en faisait la règle d'une journée. Sans ancienne suite,
une correction suit désormais sa FORME, à sa place ou au seul mot de cette forme. Un mot qui
a bougé et dont la forme revient la laisse à revérifier : c'est le prix connu, gardé plutôt
que deviné.
