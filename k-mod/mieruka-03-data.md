# 03 — Data

**Status:** MVP · **Storage:** SQLite (one database) · **Source:** workspace table "Base de données" and the frozen contract

## Tables (from the workspace)

| Table | Main fields | Notes |
|---|---|---|
| `utilisateurs` | id, nom, nb_personnes, type_logement, region | `nb_personnes` drives fair comparison in 05 |
| `adaptateurs` | id (NABD-xxxx), utilisateur_id, appareil_id, statut | Statut: `actif`, `hors_ligne`, `non_associe` |
| `appareils` | id, nom, type, puissance_nominale_w | Appliance: "Réfrigérateur", "Climatisation", etc. |
| `mesures` | adaptateur_id, horodatage, watts, source | `source` is `simulee` or `reelle`. Unique on (adaptateur_id, horodatage). |
| `alertes` | id, adaptateur_id, horodatage, type, explication, resolue | Type: `anomalie`. Explication comes from 04. |
| `recompenses` | utilisateur_id, periode, kwh_evites, points | One row per user per period |

## Rules

- Times are stored in UTC and shown in local time (Africa/Tunis).
- Measurements are kept for the whole demo. There is no retention policy in the MVP.
- No table holds a name in a shared report. The STEG view reads aggregates only.

## Checks

- Migrations apply to an empty SQLite file.
- The unique constraint on `mesures` stops duplicates.
- Deleting a user removes their adapters' links but keeps anonymous aggregates.
