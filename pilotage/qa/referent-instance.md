---
passe: Le référent de l'instance
chantier: AUTH-12
duree: 15 min
derniere: —
---

# QA — le référent de l'instance, et ses deux états muets

**Où** — le serveur LOCAL, `uvicorn main:app --reload` sur `http://127.0.0.1:8000`, et non
la pile de recette. C'est délibéré : les trois états se produisent en posant deux variables
d'environnement et en redémarrant, ce qui sur la recette voudrait dire redémarrer `bd-app`
et déranger le décor des autres passes. En local, ça ne coûte rien à personne — et l'état
« absent » y est même le défaut, puisque aucun décor de développement ne pose ces variables.

**Ce que la passe éprouve.** Le bloc existe pour ses deux états MUETS, pas pour le cas qui
va bien. `BD_REFERENT_NOM` / `BD_REFERENT_CONTACT` ne se voyaient jusqu'ici que dans le
bandeau de portée vide, donc par qui n'a accès à rien : celui qui peut les corriger ne les
voyait jamais. Ce qui se regarde ici est donc : est-ce qu'un référent manquant SE VOIT, et
est-ce qu'un référent à moitié posé se voit comme un défaut plutôt que comme une réponse.

**Les trois états ne se valent pas, et l'écran doit le montrer.** « Personne n'est désigné »
manque, et ne trompe personne. « Nommé sans contact » TROMPE : le bandeau nomme alors
quelqu'un sans dire comment l'atteindre, à une personne qui ne peut rien faire d'autre que
le contacter. Le second doit se lire plus fort que le premier — c'est l'attendu, pas un
détail d'esthétique.

**Poser les variables**, sous PowerShell, avant de lancer le serveur. Les retirer se fait en
fermant le terminal, ou en les remettant à `""` :

```powershell
$env:BD_REFERENT_NOM = "Ana Ruiz"
$env:BD_REFERENT_CONTACT = "ana@labo.fr"
.venv\Scripts\python -m uvicorn main:app
```

Le serveur lit ces variables **au démarrage** : chaque changement demande de l'arrêter
(`Ctrl+C`) et de le relancer. Un rechargement de page ne suffit pas.

### L'état qui manque — aucune variable posée
**Aucune des deux variables**, serveur relancé, `http://127.0.0.1:8000/administration`.

- [ ] Le bloc « 📇 Référent de l'instance » est visible, en deuxième position, entre « 🏷️ Version servie » et « 👥 Comptes et groupes »
- [ ] Il dit « **Personne n'est désigné.** », et cette ligne est en AMBRE, distincte du texte gris de la page
- [ ] Sous cette ligne, une note dit ce que ça coûte — qu'une personne sans accès voit un bandeau qui ne peut nommer personne — et nomme les DEUX variables à poser
- [ ] Le chapeau du bloc dit que le référent « se règle dans l'environnement du serveur », et non ici : aucun champ, aucun bouton d'enregistrement dans ce bloc

### Le cul-de-sac — un nom sans contact
**`BD_REFERENT_NOM` seule**, `BD_REFERENT_CONTACT` vide ou absente, serveur relancé.

- [ ] La ligne dit le nom posé, suivi de « **aucun contact déclaré.** »
- [ ] Elle est en ROUGE et porte une barre verticale à sa gauche — plus voyante que l'ambre de l'état précédent, qu'on vient de voir
- [ ] La note nomme `BD_REFERENT_CONTACT` et **ne parle pas** de `BD_REFERENT_NOM` : la variable juste ne doit pas être remise en doute
- [ ] Ouvrir `/` (l'Atelier) dans la même session : le bandeau de portée vide n'apparaît pas, puisqu'en local la portée est totale. C'est normal — le bandeau se regarde dans la zone suivante

### Le cas qui va bien, et sa variante
**Les deux variables posées**, serveur relancé.

- [ ] La ligne dit le nom, puis le contact, en texte ORDINAIRE — ni ambre, ni rouge, ni barre
- [ ] Le contact n'est **pas** un lien cliquable : ce bloc constate un réglage, il ne sert pas à écrire au référent
- [ ] Aucune note ne s'affiche sous la ligne : il n'y a rien à expliquer
- [ ] **Variante** — `BD_REFERENT_CONTACT` seule, `BD_REFERENT_NOM` vide, serveur relancé : la ligne dit « Aucun nom déclaré » en gris, suivi du contact, et reste en texte ordinaire. Une adresse sans nom reste une adresse : ce n'est pas un défaut, et l'écran ne doit pas crier

### Réservé, et ce que voit l'autre
**`BD_AUTH_PROXY=1` posée, aucune autre**, serveur relancé. Sans proxy devant, aucune
identité ne parvient : la portée est VIDE, c'est-à-dire exactement le décor de la personne
que le référent est censé servir.

```powershell
$env:BD_AUTH_PROXY = "1"
```

- [ ] `/administration` : le bloc « 📇 Référent de l'instance » **n'apparaît pas du tout** — ni vide, ni grisé. « 🏷️ Version servie » et « 👥 Comptes et groupes » ont disparu de même ; « 🩺 Moteurs » reste
- [ ] `/` : le bandeau de portée vide s'affiche. Avec les deux variables posées en plus de `BD_AUTH_PROXY`, il nomme le référent et rend son contact CLIQUABLE — c'est là que le lien a un sens, et c'est l'autre écran
- [ ] Avec `BD_REFERENT_NOM` seule en plus de `BD_AUTH_PROXY` : noter ce que dit le bandeau, sans rien corriger. **Cette case est une OBSERVATION, pas un attendu** — le comportement du bandeau dans cet état est signalé à la coordination et n'a pas été modifié par ce chantier

### Largeur et thème
- [ ] Thème clair (🌙 → ☀), les trois états rejoués : l'ambre et le rouge restent lisibles sur fond clair, et se distinguent toujours l'un de l'autre
- [ ] Contraste élevé : les deux couleurs tiennent, et la barre verticale du cul-de-sac reste visible
- [ ] Outils de développement, mode appareil à 320 px, état « cul-de-sac » : la note passe à la ligne sans rien pousser hors de l'écran, et la barre verticale reste collée au texte

### Remise en état
- [ ] Fermer le terminal du serveur, ou remettre les trois variables à `""` : aucune trace ne subsiste, ces réglages ne touchent pas la base
