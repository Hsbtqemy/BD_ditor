"""Helpers partagés par les scripts d'export de métadonnées (tools/)."""
from __future__ import annotations

import subprocess


def version_outil(base_dir) -> dict:
    """Provenance de l'outil produisant l'export (paradonnée / PROV).

    BéDéditeur n'a pas de version déclarée → on identifie le code par sa **révision
    git** (hash court + '+modifié' si l'arbre de travail est sale). `version` reste
    None tant qu'aucune version n'est déclarée. Robuste hors dépôt git (revision=None).
    """
    revision = None
    try:
        r = subprocess.run(["git", "-C", str(base_dir), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            revision = r.stdout.strip()
            d = subprocess.run(["git", "-C", str(base_dir), "status", "--porcelain"],
                              capture_output=True, text=True, timeout=3)
            if d.returncode == 0 and d.stdout.strip():
                revision += "+modifié"
    except Exception:
        revision = None
    return {"nom": "BéDéditeur", "version": None, "revision": revision}
