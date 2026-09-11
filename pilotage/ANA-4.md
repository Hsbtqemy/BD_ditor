---
chantier: ANA-4
statut: interrompu
---

# ANA-4 — keyness (log-vraisemblance) dans la comparaison A/B

**Arrêté sur** — 2026-09-11, `d0f0f87` : la comparaison se classe par écart de fréquence relative OU par keyness, au choix, dans l'URL et dans l'export. Reste une seule case, qui n'est pas du code : montrer sur un corpus RÉEL ce que la mesure fait remonter. Le corpus local est trop petit pour le trancher, et la case dit pourquoi.

**Point de départ** — la comparaison A/B existe et fonctionne ; elle classe par écart de
fréquence relative, ce qui favorise mécaniquement les mots fréquents.

## Reste

- [x] La métrique de classement est sélectionnable dans la vue Comparaison (écart de fréquence relative ou log-vraisemblance) — « Classer par », visible en comparaison seule ; la barre montre la force de la mesure choisie, la ligne d'information la nomme, l'export trie comme l'écran et porte les deux colonnes ; une mesure inconnue est un 422. `d0f0f87` ; `test_la_comparaison_classe_par_la_mesure_demandee`, `test_l_export_de_la_comparaison_trie_comme_l_ecran`, `test_la_keyness_se_choisit_voyage_dans_l_url_et_part_avec_l_export`
- [ ] Sur un corpus réel, le classement par keyness fait remonter au moins un mot rare-mais-distinctif que l'écart de fréquence relative enterrait. **Mesuré le 2026-09-11 sur la base locale, et non tranché** : deux albums, 353 et 90 tokens. La keyness fait bien DESCENDRE les mots fréquents des deux côtés — « de » de 1er à 6e pour B, « pas » de 2e à 9e pour A — et fait entrer dans le top 10 de B « nous », « taire », « regarde », « camarade », rangs 11 à 14 à l'écart. Mais ce sont des hapax, G² 3,19, sous le seuil usuel de 3,84 : sur 443 tokens, « fait remonter » se constate sans rien prouver. À refaire sur un corpus de production, ou après le peuplement d'ANN-1
- [x] Le choix de métrique passe dans l'URL, comme le reste de l'état d'Exploration (partageable) — `metrique=ll`, le défaut omis comme `tag_scope` ; une valeur inconnue retombe sur le défaut, et le rechargement restaure le choix. `d0f0f87` ; `test_la_keyness_se_choisit_voyage_dans_l_url_et_part_avec_l_export`
- [x] Un test verrouille le calcul de log-vraisemblance sur un jeu de comptes connu — `vraisemblance.py`, valeurs en forme close (2·f·ln 2) ou figées, et l'accord des deux mesures sur le CÔTÉ vérifié sur une grille. `d0f0f87` ; `test_log_vraisemblance_sur_des_comptes_connus`, `test_les_deux_mesures_s_accordent_sur_le_cote` ; neuf mutations sur le chantier, neuf tuées

## Contexte

Effort S au backlog : le calcul est une formule sur des comptes déjà disponibles côté
serveur, l'essentiel du travail est le sélecteur et le passage dans l'URL.

C'est le raffinement le moins cher des quatre vues d'Exploration, et celui qui change le
plus ce qu'on voit — la comparaison actuelle dit surtout que « le » est fréquent des deux
côtés.
