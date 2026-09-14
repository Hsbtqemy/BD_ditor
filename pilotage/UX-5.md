---
chantier: UX-5
statut: à venir
---

# UX-5 — Ctrl+Z annule un enregistrement, pas un geste

**Point de départ** — 2026-09-14, en jouant `qa/normaliser-casse`. L'équipe a signalé que
Ctrl+Z « annule mais n'actualise pas, il faut recharger pour le voir ». Une mesure navigateur
a réfuté la prémisse — l'écran se rafraîchit —, et c'est le journal A3 qui a montré ce qui
s'était réellement passé : quatre Ctrl+Z pour défaire ce qui, pour la personne, était un seul
geste.

L'annulation a été livrée sous la piste **D1** le 2026-07-18 (`docs/roadmap.md`) ; `UX-5` est
le code que `docs/undo.md` donne au chantier. Aucun commit de code ne le cite encore — la
seule mention est une note de backlog, `9756074` —, d'où `à venir` et ce `Point de départ`.

## Reste

### L'arbitrage, avant toute ligne de code
- [ ] Tranché et ÉCRIT : à quelle granularité Ctrl+Z annule. Trois voies, qui n'ont pas le
      même coût — regrouper à l'ANNULATION les modifications consécutives d'une même cible
      par un même agent dans une fenêtre de temps ; regrouper à l'ÉCRITURE, en rendant
      explicite le moment où une retouche devient un acte ; ou assumer l'enregistrement
      comme unité et le DIRE à l'écran
- [ ] Le choix préserve l'append-only du journal A3, socle du chantier : un événement ne se
      réécrit jamais. Regrouper à l'annulation le respecte par construction ; regrouper à
      l'écriture change ce que le journal enregistre, donc la provenance qui part au dépôt
      (PROV-O, TEI) — ce coût-là doit être pesé, pas découvert
- [ ] Le choix dit ce qu'il fait des états INTERMÉDIAIRES : le premier Ctrl+Z du 2026-09-14 a
      laissé « l'ngkar », un texte que personne n'a jamais voulu écrire. Poser un état jamais
      souhaité est un défaut distinct de la seule lenteur à revenir en arrière

### Ce que le défaut touche
- [ ] Le périmètre est MESURÉ : la zone de saisie de la Transcription (`trScheduleSave`) et la
      note d'annotation (`scheduleSave`) partagent `SAVE_DEBOUNCE` = 500 ms et journalisent à
      chaque enregistrement. La première est établie par le journal ; la seconde à la lecture
      seulement, et doit être éprouvée avant d'être déclarée touchée
- [ ] Les actes que l'annulation a été CONÇUE pour défaire — la suppression cascade, la
      création d'une région — restent annulables d'un seul Ctrl+Z quel que soit le choix :
      c'est la valeur de sûreté que D1 revendique, et un regroupement trop large l'avalerait
      avec le reste

### Ce que l'écran promet
- [ ] Le toast dit ce qu'il a défait de façon qu'on le VOIE. Il affiche aujourd'hui
      « Annulé : modification d'une région » — un type d'acte, jamais le changement —, si bien
      qu'une annulation d'une seule lettre s'annonce exactement comme celle de toute la bulle
- [ ] Une garde e2e reproduit le geste du 2026-09-14 — une retouche en deux frappes séparées
      de plus de 500 ms, puis un seul Ctrl+Z — et vérifie le résultat que l'arbitrage aura
      décidé. `tests/test_e2e_undo_rafraichit.py` ne l'éprouve pas : son geste unique produit
      un seul enregistrement, et c'est précisément pourquoi il n'a rien reproduit

## Contexte

**Deux conceptions justes qui ne s'étaient jamais rencontrées.** `docs/undo.md` pose le but de
l'annulation : rendre réversible la suppression cascade — « filet fin, complément de la
sauvegarde (gros grain) ». Elle a été pensée pour de GROS actes. L'enregistrement automatique à
500 ms, lui, a été pensé pour ne jamais perdre une frappe. Chacun tient seul. Ensemble, chaque
retouche de 500 ms devient un « acte » que Ctrl+Z défait séparément — et rien, ni dans
`docs/undo.md` ni dans le code, ne dit que c'était voulu. C'est donc un défaut et non une
limite écrite : la maison distingue les deux, et une limite qu'on n'a pas écrite n'en est pas
une.

**Ce que le journal a montré, et pourquoi la mesure navigateur ne l'avait pas vu.** Sur la
bulle 136, la retouche « angkar » → « Angkar » a produit DEUX événements à une seconde d'écart
— 33, le retour arrière ; 34, la frappe —, les 500 ms étant passées entre les deux. Les quatre
annulations de l'équipe : 11:57:43, puis dix-huit secondes de pause, puis 11:58:01, :02, :03 —
trois appuis en trois secondes, la signature de qui réappuie faute de voir un effet. Le premier
avait pourtant bien rafraîchi l'écran : il avait retiré une lettre. Le test navigateur qui
réfutait la prémisse n'a rien reproduit parce que son geste était unique — un clic sur
« Normaliser », donc un seul événement. Il mesurait juste, sur la mauvaise question.

**La case 53 de `qa/normaliser-casse` promet l'annulation par geste** — « la dernière bulle
modifiée retrouve son texte précédent », au singulier — et elle est cochée : elle tient après
un clic sur « Normaliser », pas après une retouche à la main. Elle n'est pas réécrite ici tant
que l'arbitrage n'a pas dit ce qu'elle doit promettre.

**Et le défaut a un coût en recette, mesuré le même jour.** Sous `stagiaire`, la bulle 30
d'*esther v1* a reçu onze modifications en dix-sept secondes — des « t » tapés par la touche de
mode puis effacés à la main, chacun enregistré. La défaire par Ctrl+Z demanderait onze appuis,
et un douzième déferait une normalisation légitime : c'est exactement ce défaut, vu de l'autre
côté.
