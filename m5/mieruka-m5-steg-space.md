# Module 5 — STEG space (aggregated)

**Owner:** Member 4 (confirm) · **Django app:** `m5` · **Branch:** `m5`
**Dependencies:** M2 (`/steg/agregat`, data) · **Used by:** Pitch (final demo step)
**Plan:** Sprint 1 — consumption per fictional region · Sprint 2 — evening peak window and areas to watch · Sprint 3 — labels, polish and pitch screenshots

Source: [k-mod/mieruka-07-steg-space.md](../k-mod/mieruka-07-steg-space.md).

## Features

- Shows STEG the indicators it needs (peaks, anomalies, areas to help) without showing any household.
- Consumption per fictional region (Tunis, Sfax, Kairouan, Tozeur), all labelled as fictional.
- Evening peak window (20:00 to 22:00) and areas to watch, marked as an assumption.
- "Your household is added to the total", to show how one measurement becomes a regional view.

## Data and rules

| Rule | Requirement |
|---|---|
| Minimum group | No region is shown with fewer than 10 households. |
| No individual data | No route or page returns one household. |
| Label | Every figure carries "Simulé" or "Hypothèse fictive" when it is one. |

## Pages

`app_name = "m5"`:

| URL | Purpose |
|---|---|
| `/` | Espace STEG: regional totals, peak window, areas to watch |

## Stories

| ID | Outcome | Priority |
|---|---|---|
| 5.1 | STEG sees consumption per region, aggregated and anonymous | Must |
| 5.2 | The evening peak window is highlighted | Must |
| 5.3 | Areas to watch are listed and marked as an assumption | Should |

## Integration and checks

- Reads M2's aggregate route only; never household-level routes.
- A region with 9 households shows nothing; a region with 10 shows its total.
- The page never shows an address or a name.

## Scaffold preview

The screenshot shows the shared placeholder page, not completed module features.

![M5 placeholder](screenshots/placeholder.png)
