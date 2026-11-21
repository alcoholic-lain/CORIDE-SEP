# 02 — API

**Status:** MVP · **Stack:** to decide (see 00-index). The workspace suggests Rust with Axum, or FastAPI as the fallback. · **Depends on:** 03 data, 04 ai, 05 rewards

## Purpose

One server that stores measurements, runs the rules and alerts, serves the user space and the STEG space, and calls the AI module. The workspace says: one server, one database, no external services.

## Routes (proposed)

| Method | Route | Purpose |
|---|---|---|
| POST | `/mesures` | An adapter posts a measurement (contract in 01) |
| POST | `/utilisateurs` | Create a user profile (name, household size, housing type, region) |
| POST | `/adaptateurs/associer` | Pair an adapter ID to the user and an appliance |
| GET | `/foyer/courbe?periode=` | Live and recent curve for the household |
| GET | `/foyer/alertes` | Open alerts with the AI's explanation |
| POST | `/alertes/<id>/appliquer` | Apply the recommendation (marks the alert resolved) |
| GET | `/foyer/recompenses` | Points, kWh avoided, and the formula shown on screen |
| GET | `/steg/agregat` | Aggregated, anonymous indicators (see 07) |

## Rules

| Rule | Requirement |
|---|---|
| Anonymity | No route returns another household's data. The STEG route returns aggregates only. |
| Minimum group | An aggregate is not returned for a region with fewer than 10 households. |
| Essential power | Nothing in the API can cut power. There is no route for that. |
| Errors | Every error returns a readable message in French. |

## Checks before merging

- `POST /mesures` stores a valid measurement and rejects an invalid one.
- The alert route returns an alert only after the AI's rule has fired.
- The STEG route returns nothing for a region with 9 households.
