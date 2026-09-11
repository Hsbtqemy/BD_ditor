---
passe: L'annuaire vu depuis l'écran
chantier: AUTH-7
duree: 25 min
derniere: 2026-09-11
---

# QA — créer, grouper et retrouver un compte sans shell

**Où** — la pile de recette locale : l'application sur `https://bd.127-0-0-1.sslip.io`,
l'annuaire sur `https://annuaire.127-0-0-1.sslip.io`. Certificats de recette à accepter.
Une fenêtre privée par identité.

**Ce qui a été fait AVANT la passe, par la session qui a monté la pile, et qui n'est donc
pas à cocher ici.** L'installation a suivi le guide (`docs/deploiement-docker.md`, section
« Amorcer l'annuaire ») à une différence près : sous Windows, Docker Desktop ne rend pas les
adresses des conteneurs joignables depuis l'hôte, si bien que l'amorçage est passé par le
port 17170 de LLDAP publié sur la boucle locale au lieu du tunnel SSH. Authelia a refusé de
démarrer avant l'amorçage (`LDAP Result Code 49 "Invalid Credentials"`), puis a démarré
(`Startup complete`) après le redémarrage prescrit. Le tunnel reste donc non éprouvé.

**Ce que la passe éprouve** : la raison d'être d'AUTH-7, que le geste d'administration des
comptes cesse d'exiger un shell sur le serveur.

### L'accès à l'annuaire
- [ ] Sous `lectrice`, `https://annuaire.127-0-0-1.sslip.io` est REFUSÉ par Authelia : l'interface de LLDAP ne s'affiche pas
- [ ] Sous `admin-bd`, le second facteur est demandé (enrôlement TOTP la première fois, code dans `authelia/notification.txt` de la pile), puis la page de connexion de LLDAP s'affiche
- [ ] `admin-bd` s'y connecte avec le même mot de passe, et la liste des comptes montre les huit comptes de la recette (le service `authelia` compris) et `admin`

### Le geste sans shell
- [ ] Dans l'interface de LLDAP, un compte `essai-recette` est créé, avec un mot de passe, sans groupe
- [ ] `essai-recette` se connecte à l'application (mot de passe seul) et voit le bandeau « Aucune collection ne vous est ouverte. »
- [ ] Dans LLDAP, `essai-recette` est ajouté au groupe `annotateurs` ; sans se reconnecter ni rien redémarrer, la Bibliothèque lui montre « esther v1 » au plus cinq minutes plus tard. L'application relit les groupes à chaque requête, mais Authelia ne relit ceux de l'annuaire qu'à son intervalle de rafraîchissement, cinq minutes par défaut : noter le délai réellement observé

### Le mot de passe oublié
- [ ] Au portail, « Mot de passe oublié ? » pour `lectrice` : le lien arrive dans `authelia/notification.txt`, et le nouveau mot de passe permet d'entrer
- [ ] Le même geste pour `admin-bd` ÉCHOUE : LLDAP interdit au compte de service de changer le mot de passe d'un `lldap_admin`. Attendu : l'échec est visible à l'écran, et le recours est l'interface de LLDAP

### Le vérificateur
- [ ] Depuis le dépôt, `python deploy/verifier_comptes.py` commence par « REPLI — l'annuaire LDAP est le backend actif » : le fichier de comptes y est annoncé comme recours et non comme la source des connexions
