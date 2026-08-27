---
chantier: CONC-2
statut: interrompu
---

# CONC-2 — isolation subprocess des moteurs ML (v2)

**Arrêté sur** — 2026-06-26, `b9743bd` : la v1 est livrée (déchargement par moteur,
orchestrateur `pipeline/modeles.py`, libération en fin de lot et avant passe interactive,
route `POST /api/ml/liberer`, modèles résidents exposés dans `/api/sante`). L'option (c),
seule à garantir le zéro-OOM, est restée dehors.

## Reste

- [ ] Les moteurs ML tournent dans un process séparé de l'API, redémarrable, de sorte qu'un OOM du worker n'emporte pas le serveur
- [ ] Le worker se relance seul après un kill, et le lot en cours est marqué en échec plutôt que laissé en « en cours » pour toujours
- [ ] Enchaîner segmentation, bulles, OCR puis NLP sur une vraie planche ne tue plus le process de l'API, reproduit sur la machine où l'OOM du 2026-06-24 avait été observé
- [ ] L'empreinte mémoire de chaque moteur est documentée, avec la recommandation de dimensionnement pour le VPS

## Contexte

**PRÉMISSE À RÉEXAMINER (mesure du 2026-08-27).** Dans un conteneur à 8,17 Go, avec le
torch CPU, les **trois moteurs chargés ensemble tiennent dans 833,6 Mio** — application
seule 49,7 Mio, + spaCy 143,4, + YOLOv8 826,4, + EasyOCR 833,6. Soit ~10 % de la mémoire
disponible, très loin d'un OOM.

L'OOM du 2026-06-24 a probablement été causé par le **torch CUDA**, retiré depuis
(`7171040`) : il charge les runtimes CUDA en mémoire même sans GPU.

**Confirmé sur un VRAI master** (`corpus/album_2/planche_0002.tif`, 3748×4710, 17,7 Mpx,
400 dpi), les trois passes enchaînées dans un seul conteneur : app + spaCy 173 Mio →
import 407,7 Mio → segmentation 410,5 Mio → bulles 779 Mio → OCR **1,036 Gio**, **pic
observé 1,216 Gio**. Soit **15 % des 8,17 Go**. Résultats réels : 12 cases, 24 bulles,
24 régions avec texte OCR.

**La raison d'être de cette fiche a donc disparu.** Elle existait pour garantir le
zéro-OOM ; l'OOM venait du torch CUDA, pas de l'architecture. Reste à trancher : la
clore, ou l'abandonner en gardant son `Reste` comme trace du raisonnement. L'isolation
subprocess garde un mérite propre — un crash du worker n'emporte pas l'API — mais ce
n'est plus le même chantier, ni la même urgence, et il faudrait le réécrire sous cet
angle.

**L'OOM n'était pas théorique** : observé le 2026-06-24 en annotant une vraie planche, le
process tué SANS traceback Python. Les données committées étaient saines — c'est le seul
point rassurant.

La v1 libère, mais ne peut pas garantir le zéro-OOM : tant qu'un modèle torch est chargé,
le runtime occupe la RAM. Seule l'isolation en process séparé le garantit, d'où cette v2.

Contournement immédiat, toujours valable : lancer les passes ML séparément et redémarrer
entre les grosses.

Lien direct avec INFRA-1 : un VPS contraint atteindra cette limite avant un poste de dev.
Traiter CONC-2 v2 avant ou pendant le déploiement, pas après le premier incident.
