# 07 — STEG space (aggregated)

**Status:** MVP (aggregated, with fictional regions) · **Depends on:** 02 api, 03 data

## Purpose

Show STEG the indicators it needs (peaks, anomalies, areas to help) without showing any household. The prototype says: "your household is added to the total, to show how one measurement becomes a regional view."

## Indicators

- Consumption per fictional region (Tunis, Sfax, Kairouan, Tozeur in the prototype). All regions are fictional and labelled as such.
- The evening peak window (20:00 to 22:00 in the prototype).
- Areas to watch, marked as an assumption.

## Rules

| Rule | Requirement |
|---|---|
| Minimum group | No region is shown with fewer than 10 households. |
| No individual data | No route returns one household. |
| Label | Every figure carries "Simulé" or "Hypothèse fictive" when it is one. |

## Tests

- A region with 9 households shows nothing.
- A region with 10 households shows its total.
- The page never shows an address or a name.
