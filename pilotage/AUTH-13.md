---
chantier: AUTH-13
statut: différé
---

# AUTH-13 — la porte d'entrée : une page de présentation, et la demande d'un compte et d'un projet

**Point de départ** — 2026-10-10, en conversation, pendant le cadrage de la tranche 1 de
`COL-3`. Hugo : *« Depuis l'extérieur, si on n'a pas de compte, on peut demander la création
d'un compte et la création d'un projet. Mais ça doit être justifié de fait. »* Puis, devant ce
que ce pas coûte : *« On peut garder ce projet pour plus tard. Je pense surtout à une page de
présentation. Mais on garde ça pour quand tout sera à peu près construit et abouti. »*

## Reste

### Différé par Hugo — 2026-10-10

- [x] **Le chantier attend que le reste soit construit** — décision de Hugo, phrase ci-dessus. Rien n'est conçu au-delà de cette fiche, et rien ne se code
- [ ] **Ce qui le rouvre est constaté** — attendu : la tranche 2 de `COL-3` est livrée, donc le mécanisme de demande existe (qui demande, quand, pourquoi ; la place dans « À regarder » ; « accepter » ou « refuser ») et n'est pas à écrire deux fois ; et Hugo juge l'outil assez abouti pour le présenter. Le renvoi est posé chez `COL-3`, case « La demande venue de l'extérieur »

### La forme — à trancher à la réouverture

- [ ] **La page de présentation** — attendu : ce qu'elle dit, à qui, et où elle vit. C'est d'elle que Hugo parle d'abord. Deux lieux possibles, et ils n'ont pas le même coût : une page de l'application, donc un chemin soustrait à la connexion ; ou une page servie à côté, qui ne touche ni l'application ni sa garde
- [ ] **La demande est justifiée, et c'est la justification qui filtre** — attendu : ses champs arrêtés. Hugo ne borne pas QUI demande ; il exige qu'on dise pourquoi, « notamment scientifique ». La justification rejoint le projet accepté (colonne proposée dès la tranche 1 de `COL-3`)
- [ ] **Une écriture ouverte à l'internet entier a ses plafonds** — attendu : tranché et éprouvé. Tailles, cadence, et ce qui arrête un robot. Relevé le 2026-10-10 : rien de l'application ne se joint aujourd'hui sans compte (`default_policy: 'deny'` dans la configuration d'Authelia, `forward_auth` sur tout le domaine), et `AUTH-7` a écrit ce que vaut ce pas — « ce n'est pas un degré, c'est un régime »
- [ ] **Ce qu'on garde de quelqu'un qui n'est pas un utilisateur** — attendu : dit, avec sa durée. Nom, courriel, rattachement, justification ; et le sort d'une demande refusée. C'est le corps « PERSONNES » de `docs/dossier-base-legale.md`, dont `AUTH-1` attend la réponse
- [ ] **Comment on répond au demandeur** — attendu : tranché. L'application n'envoie aucun courriel, et `COL-3` a écarté toute messagerie : l'administrateur répond de sa boîte, ou l'application apprend à écrire
- [ ] **Qui crée le compte** — attendu : dit. L'application LIT l'annuaire et n'y écrit pas (`AUTH-6`, compte de service en lecture seule) : accepter une demande, c'est aujourd'hui un administrateur qui crée le compte dans l'annuaire, puis le projet. `AUTH-7` a déjà pesé l'inscription par invitation, et ce qu'elle demanderait
- [ ] **Les albums ne se cochent pas de l'extérieur** — attendu : confirmé. Qui n'a pas de compte ne voit pas le fonds ; sa demande dit en clair sur quel corpus il veut travailler, et la demande groupée de documents se dépose une fois le projet accepté (`COL-3`, case « Qui dépose la demande de départ d'un projet »)

## Contexte

Né d'un malentendu utile. La session cadrait la demande de documents « à la création d'un
projet » et proposait de borner QUI peut demander un projet ; Hugo parlait d'autre chose —
de l'entrée dans l'instance, par quelqu'un qui n'y est pas encore. Les deux lectures, et
celle qui a été démentie, sont gardées dans `pilotage/COL-3.md`, zone « Précisé par Hugo —
2026-10-10 ».

D'ici la réouverture, une demande venue de l'extérieur arrive par le contact du référent de
l'instance (`AUTH-4`), et l'administrateur la saisit lui-même en créant le projet.

Tout ce qui touche une garde passe par une relecture croisée : ce chantier ouvrirait la
première surface jointe sans compte, et sa relecture ne peut pas être celle de qui l'écrit.
