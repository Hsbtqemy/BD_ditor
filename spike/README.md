# Spike OCR — banc d'essai (exploratoire, hors application)

But : **trancher la pile OCR sur de VRAIES planches franco-belges**, pas sur des
benchmarks anglophones. La recherche a montré qu'aucun chiffre OCR n'existe pour
le franco-belge ; ce banc les produit sur ton corpus.

> Ce dossier est **exploratoire** : il ne fait pas partie de l'application
> (`main.py`/`pipeline/`), n'est ni testé ni couvert. Il informe le futur
> `pipeline/ocr.py`.

## Fichiers

| Fichier | Rôle | Statut |
|---|---|---|
| `ocr_engines.py` | adaptateurs (tesseract, easyocr, doctr, paddleocr, rapidocr), auto-détection | ✅ validé (EasyOCR) |
| `make_sample.py` | planche BD synthétique (texte FR majuscules en bulles) | ✅ |
| `run_bench.py` | exécute les moteurs dispo (par bulle / planche) → rapport HTML + CSV | ✅ validé |
| `bulles.py` | détecteur de bulles YOLOv8 `ogkalu` (passe 2) → sidecar `.json` | ⚠️ code prêt, non testé (ultralytics absent) |
| `sharedocs_ocr.py` | WebDAV ShareDocs : download planches + OCR via watch-folder ABBYY | ⚠️ code prêt, non testé (identifiants requis) |

## Démarrage rapide (validation locale)

```bash
pip install -r spike/requirements-spike.txt   # au moins easyocr
python spike/make_sample.py                    # planche synthétique
python spike/run_bench.py --mode both          # -> spike/report.html + .csv
```

Résultat déjà obtenu (EasyOCR sur l'image synthétique) : lecture correcte du
français **avec accents** (`SÛR`, `À`, `GÉNIAL`, `ÉCHARPE`, `GÈLE`), ~1,3 s/bulle.
Erreurs mineures (`2OH`→`20H`). ⚠️ Image synthétique = texte net : **proxy**, pas
une vraie planche.

## Le vrai test (à faire avec tes données)

```
1. Récupérer ~10 planches Esther depuis ShareDocs (sharedocs_ocr.download_dir)
2. Détecter les bulles            : python spike/bulles.py planche*.png
3. Banc local (par bulle)         : python spike/run_bench.py --images <dir> --mode bulles
4. Référence ABBYY (tant que dispo): sharedocs_ocr.ocr_via_watchfolder(..., engine="AbbyyServer")
5. Comparer report.html -> décider la pile de PRODUCTION (locale)
```

## Ce qu'il me faut de toi

1. **Identifiants ShareDocs** : `https://sharedocs.huma-num.fr/dav.php/`,
   user `<id>@webdav`, mot de passe d'application. (Puis
   `python spike/sharedocs_ocr.py --user <id>@webdav --password ...` liste les
   outils OCR disponibles sur ton compte.)
2. **Contrat ABBYY encore actif ?** Il était « valable jusqu'à juin 2026 » — on
   est en juin 2026. À confirmer avant d'en faire une référence.

## Rappels (doc Huma-Num)

- ABBYY = **900 pages/an/utilisateur** → inutilisable pour le volume (corpus =
  milliers de planches) ; bon pour un **échantillon de référence** seulement.
- ABBYY océrise un **document entier**, pas par bulle → la détection de bulles
  reste open-source en amont quoi qu'il arrive.
- AbbyyCloud → Azure (externe) : à éviter pour des scans sous droits ; préférer
  **AbbyyServer** (interne). Watch-folder : fichiers purgés à 21 j, nom unique
  sur 23 j, latence 1–24 h.

## Conclusion provisoire

Pour la **production** (volume + par bulle), la pile reste **locale open-source** :
détection bulles `ogkalu` YOLOv8 → crops → OCR (EasyOCR/docTR/Tesseract `fra`).
ABBYY-via-ShareDocs sert de **plafond de qualité** pour calibrer, pas de moteur
de production.
