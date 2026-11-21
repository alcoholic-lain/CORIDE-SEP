# 05 — Rewards

**Status:** MVP (points for kWh avoided) · **Depends on:** 03 data, 04 ai

## Principles (from the workspace)

1. **Fair:** each household is compared to its own history and to households of the same size. Never to a national average.
2. **Never cut off:** essential electricity is never blocked. Exceeding a goal costs nothing; there are only gains.
3. **Transparent:** the formula is shown on screen.

## Formula

```
reference(appareil, heure) = médiane des watts de cet appareil à cette heure, avant l'anomalie
kwh_evites = max(0, reference − watts_mesurés) × intervalle en heures
points = floor(kwh_evites × 500)
```

The demo uses 500 points per kWh avoided (the value in the prototype). The score is shown next to the formula.

## Rules

| Rule | Requirement |
|---|---|
| Source | Points only come from kWh avoided against the reference. |
| Monthly goal | A household sets a monthly goal. Missing it does not reduce points. |
| Tariff | Shown in TND per kWh as an assumption the user can change. |
| Funding | Not implemented in the MVP. Donations and sponsorship never affect access. |

## Tests

- Points match the formula for a hand-calculated example.
- Using more than the reference earns zero points, and nothing is subtracted.
- The formula text on screen matches the code.
