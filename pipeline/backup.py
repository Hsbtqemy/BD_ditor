"""Sauvegarde de travail : snapshot cohérent de la base SQLite, zippé.

On utilise `VACUUM INTO` (et non une simple copie de fichier) pour obtenir une
copie COHÉRENTE de la base, indépendante du journal WAL — même si des écritures
viennent d'avoir lieu. La sauvegarde ne contient QUE la base (annotations, OCR,
structure, ordre) ; les images master restent sur disque / ShareDocs.
"""
from __future__ import annotations

import io
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from database import get_connection


def make_backup(stamp: str | None = None) -> tuple[str, bytes]:
    """Renvoie (nom_zip_horodaté, octets_zip) d'un snapshot cohérent de la base."""
    stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    src = get_connection()
    src.isolation_level = None        # autocommit : VACUUM refuse une transaction ouverte
    buf = io.BytesIO()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snap = Path(tmp) / "bd_annotator.sqlite"
            src.execute("VACUUM INTO ?", (str(snap),))
            # Zippe directement depuis le fichier (lecture par flux) : évite de
            # charger toute la base en RAM en plus du zip (pic mémoire ÷ ~2).
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(snap, "bd_annotator.sqlite")
    finally:
        src.close()
    return f"bd_annotator_{stamp}.zip", buf.getvalue()
