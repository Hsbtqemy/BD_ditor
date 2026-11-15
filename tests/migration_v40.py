"""Ce que la v40 (ANN-7, « Une grille dérivée dit d'où elle vient ») change à toute base qui
migre, pour les tests de migration des versions d'AVANT : ils migrent jusqu'à la version
courante, et comparent « avant » et « après » ligne à ligne. La v40 :

- pose quatre colonnes sur `grille` (`COLONNES_V40`, écrites ici à la main pour que ces
  tests ne soient pas le miroir d'une constante) : `identifiant`, rempli pour TOUTE grille,
  et l'origine, `derivee_de_*`, NULL pour toutes ;
- pose l'index unique de l'identifiant (`INDEX_V40`), dans `_migrate` et non dans
  `SCHEMA_SQL` : une base faite du seul `SCHEMA_SQL` ne l'a pas.

Rien d'autre ne change. Ce que la v40 vaut est éprouvé par `tests/test_migration_v40.py`,
sur la vraie base v39."""

COLONNES_V40 = {"grille": ("identifiant", "derivee_de_identifiant", "derivee_de_nom",
                           "derivee_de_version")}
INDEX_V40 = ("idx_grille_identifiant",)


def sans_la_v40(table: str, ligne: dict) -> dict:
    """Une ligne lue APRÈS la migration, sans ce que la v40 y a posé."""
    return {k: v for k, v in ligne.items() if k not in COLONNES_V40.get(table, ())}
