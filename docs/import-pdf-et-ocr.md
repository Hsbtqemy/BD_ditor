# Import PDF & réutilisation de la couche OCR — exploration et stratégie

> Réflexion de conception menée le 2026-06-13, **sur de vraies données**.
> **Statut : différé** — non implémenté. Piste à activer **le jour où l'on sera
> confronté à des documents PDF** (récupérations, ou dépôts de scans en PDF).
> Rien n'est codé dans l'app ; seul un outil de diagnostic existe
> ([tools/pdf_check.py](../tools/pdf_check.py)).

## 1. Le principe

Un PDF n'est pas une image mais un **conteneur de pages**. Ajouter `.pdf` à la
liste blanche ne suffit pas (Pillow ne rasterise pas un PDF). Il faut **éclater le
PDF en pages → 1 page = 1 planche**, ce qui rentre dans le modèle de données
existant sans le modifier (le PDF n'est qu'une *source* d'import).

## 2. La tension : OCR de l'app vs couche OCR du PDF

L'app océrise **par région** (EasyOCR sur chaque bulle) — c'est le composant ML le
plus lourd (~1,5 Go résident, problématique sur le VPS 4 Go). Or beaucoup de PDF
portent déjà une **couche de texte OCR** (par page, avec positions des mots).

**Opportunité** : récolter cette couche et **remplir les bulles par géométrie**
(mots dont la boîte tombe dans la bulle) au lieu de lancer EasyOCR. Bénéfices :
éviter de re-océriser un album de 80+ pages, **ne pas exécuter EasyOCR du tout**
(gain mémoire/CPU décisif sur le VPS), texte souvent meilleur.

## 3. Résultats empiriques (deux extrêmes mesurés)

Testés avec `tools/pdf_check.py` (rendu 300 dpi) :

| PDF | Pages | Couche texte | Qualité sur les **bulles** |
|---|---|---|---|
| *Obelix and Co.* (Anna's Archive, récupéré) | 52 | 100 % des pages | ❌ **inexploitable** : « TUEY'RE AFTER ME! », « IPLINE » (DISCIPLINE), « a14 », « $ » |
| `OCR….pdf` (scan **Hot Folder** du projet) | 5 | 100 % des pages | ✅ **largement bon** : « QUI EST-CE ? », « ÉLOIGNEZ-VOUS », « LE GÉNÉRAL LIMOGES », « IL EST HORS ?E QUESTION ?E » |

**Constats :**
- La **prose typographiée** s'OCR parfaitement partout ; c'est le **lettrage
  dessiné des bulles** qui distingue les sources.
- **Scan « récupéré » (OCR générique)** → bulles = bruit → réutiliser = pré-remplir
  du n'importe quoi.
- **Scan maison (Hot Folder)** → bulles ≈ 90 % correctes ; seul défaut
  systématique : **le D lu comme P** (« PE » pour « DE », « ORPNUNG » pour
  « ORDNUNG »).
- **La géométrie fonctionne** : les mots ressortent en **pixels master** cohérents
  au DPI de rendu (prose ≈ 26 px de haut, lettrage de bulle ≈ 75 px).
- Rendu 300 dpi → masters ~2400×3250 px (Anna's) / ~2800×3830 px (Hot Folder).

## 4. Conclusions

1. **La valeur de la réutilisation dépend ENTIÈREMENT de la source.** → ne jamais
   imposer la couche ; **choix par import** : « réutiliser la couche PDF » vs
   « re-océriser (EasyOCR) » vs « laisser vide ».
2. **Pour les scans maison, la réutilisation vaut le coup** (qualité + gain VPS).
   Pour les récupérations type Anna's Archive, EasyOCR (ou rien) reste préférable.
3. **Mapping trivial** si le master = la page rendue au DPI choisi : mots et
   régions détectées vivent alors dans le même repère (pixels master).

## 5. Design recommandé (si/quand on implémente)

```
Import PDF (page = planche) :
  • rendu page @300 dpi → image = MASTER de la planche
  • extraction mots + boîtes (pdfplumber) → ×(dpi/72) → pixels master
  • stockage des mots+boîtes par planche            ← seul vrai ajout au modèle
Pipeline ensuite :
  • cases (Kumiko) → bulles (YOLO) → passe « texte » :
      - couche PDF présente ET choisie → remplir chaque bulle par les mots qui
        tombent dedans (ordre de lecture) ; PAS d'EasyOCR
      - sinon → EasyOCR (repli), comme aujourd'hui
  • toujours éditable (only_empty) : l'humain corrige le résidu (PE→DE…)
```

## 6. Stack technique retenue (propre côté licence)

| Besoin | Lib | Licence | Notes |
|---|---|---|---|
| Rendu page → image | **pypdfium2** 5.9 | Apache/BSD | binaire embarqué, pip-only, wheels cp314 OK |
| Extraction mots + boîtes | **pdfplumber** 0.11 (pdfminer.six) | MIT | coords en points, origine haut-gauche |

- **Écartés** : PyMuPDF (AGPL — clause réseau gênante en hébergé) ; pdf2image/Poppler
  (binaire système en plus).
- **Déjà installés dans le venv** pour l'exploration, **mais PAS dans les
  `requirements`** (PDF non implémenté). À ajouter aux requirements le jour de
  l'implémentation.
- Outil de diagnostic : `tools/pdf_check.py` (analyse un PDF local ou ShareDocs :
  présence/qualité de la couche, coords master, dimensions de rendu).

## 7. Questions ouvertes (à trancher au moment d'implémenter)

- **Stockage de la couche** : petite table SQLite (`mots_pdf` : planche_id, texte,
  x,y,w,h) vs JSON annexe par planche.
- **Auto-correction « D→P »** : tentant mais risqué → recommandation : **non**,
  laisser l'humain corriger (cohérent avec « pré-remplissage éditable »).
- **DPI de rendu** : 300 = minimum acceptable (validé), bonne base ; ajustable.
- **UX** : un PDF de 50 pages = 50 planches d'un coup (adapter la progression
  d'import, comme pour le lot ShareDocs).

## 8. Lien avec le reste

- Cohérent avec la pipeline ShareDocs : un PDF est une source comme une autre.
- Le **gain VPS** (pas d'EasyOCR pour les scans maison océrisés) rejoint les
  contraintes mémoire décrites dans [hebergement-securite.md](hebergement-securite.md).
