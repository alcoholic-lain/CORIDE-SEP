# Module 2 — API and data

**Owner:** Rust dev 1 · **Django app:** `m2` · **Branch:** `m2`
**Dependencies:** M3 (anomaly rule), M4 (rewards formula) · **Used by:** M1 (posts readings), M4 (household screens), M5 (STEG aggregates)
**Plan:** Sprint 1 — schema, data contract and `POST /mesures` · Sprint 2 — pairing, alerts and rewards routes · Sprint 3 — STEG aggregate route and error messages

Source: [k-mod/mieruka-02-api.md](../k-mod/mieruka-02-api.md), [k-mod/mieruka-03-data.md](../k-mod/mieruka-03-data.md). Stack is an open decision (Rust/Axum, FastAPI fallback, or this Django app); see [k-mod/mieruka-00-index.md](../k-mod/mieruka-00-index.md).

## Features

- One server, one SQLite database, no external services.
- Stores measurements, pairs adapters to users and appliances, runs the alert rules through the AI module, and serves the user and STEG spaces.
- User profiles with household size, housing type and region.

## Data and rules

| Table | Main fields | Notes |
|---|---|---|
| `utilisateurs` | id, nom, nb_personnes, type_logement, region | `nb_personnes` drives fair comparison |
| `adaptateurs` | id (NABD-xxxx), utilisateur_id, appareil_id, statut | `actif`, `hors_ligne`, `non_associe` |
| `appareils` | id, nom, type, puissance_nominale_w | "Réfrigérateur", "Climatisation", … |
| `mesures` | adaptateur_id, horodatage, watts, source | Unique on (adaptateur_id, horodatage) |
| `alertes` | id, adaptateur_id, horodatage, type, explication, resolue | Explication comes from M3 |
| `recompenses` | utilisateur_id, periode, kwh_evites, points | One row per user per period |

| Rule | Requirement |
|---|---|
| Anonymity | No route returns another household's data; STEG gets aggregates only. |
| Minimum group | No aggregate for a region with fewer than 10 households. |
| Essential power | Nothing in the API can cut power; there is no route for that. |
| Time | Stored in UTC, shown in Africa/Tunis local time. |
| Errors | Every error returns a readable message in French. |

## Pages

`app_name = "m2"`:

| URL | Purpose |
|---|---|
| `POST /mesures` | An adapter posts a measurement |
| `POST /utilisateurs` | Create a user profile |
| `POST /adaptateurs/associer` | Pair an adapter ID to the user and an appliance |
| `GET /foyer/courbe?periode=` | Live and recent curve for the household |
| `GET /foyer/alertes` | Open alerts with the AI's explanation |
| `POST /alertes/<id>/appliquer` | Apply the recommendation (resolves the alert) |
| `GET /foyer/recompenses` | Points, kWh avoided and the formula |
| `GET /steg/agregat` | Aggregated, anonymous indicators |

## Stories

| ID | Outcome | Priority |
|---|---|---|
| 2.1 | A valid measurement is stored and an invalid one rejected | Must |
| 2.2 | A user creates a profile and pairs an adapter to an appliance | Must |
| 2.3 | Alerts appear only after the AI rule has fired | Must |
| 2.4 | Applying a recommendation resolves the alert | Must |
| 2.5 | STEG aggregates respect the 10-household minimum | Must |

## Integration and checks

- M1 posts readings here; M3 is called on new readings; M4 and M5 read through these routes.
- Migrations apply to an empty SQLite file.
- The unique constraint on `mesures` stops duplicates.
- The STEG route returns nothing for a region with 9 households.
- Deleting a user removes their adapter links but keeps anonymous aggregates.

## Scaffold preview

The screenshot shows the shared placeholder page, not completed module features.

![M2 placeholder](screenshots/placeholder.png)
