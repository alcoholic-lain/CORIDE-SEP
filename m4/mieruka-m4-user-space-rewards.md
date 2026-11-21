# Module 4 — User space and rewards

**Owner:** Member 4 (confirm) · **Django app:** `m4` · **Branch:** `m4`
**Dependencies:** M2 (routes), M3 (alerts and reference) · **Used by:** M5 (household joins the regional total)
**Plan:** Sprint 1 — add adapter and live curve screens · Sprint 2 — alert screen and apply recommendation · Sprint 3 — rewards, monthly goal and tariff

Source: [k-mod/mieruka-06-user-space.md](../k-mod/mieruka-06-user-space.md), [k-mod/mieruka-05-rewards.md](../k-mod/mieruka-05-rewards.md).

## Features

- Responsive web screens for the household, also shown in the Android app's WebView.
- Add an adapter (NABD-xxxx field or "Scanner (simulé)"), live consumption curve, appliance list with state (normal, anormal, corrigé), alert with explanation, rewards and monthly goal.
- Fair rewards: points for kWh avoided against the household's own reference, with the formula shown on screen.

## Data and rules

```
reference(appareil, heure) = médiane des watts de cet appareil à cette heure, avant l'anomalie
kwh_evites = max(0, reference − watts_mesurés) × intervalle en heures
points = floor(kwh_evites × 500)
```

| Rule | Requirement |
|---|---|
| Fair | Compare each household to its own history and same-size households, never a national average. |
| Never cut off | Essential electricity is never blocked; exceeding a goal costs nothing. |
| Transparent | The formula on screen matches the code. |
| Tariff | Shown in TND per kWh as an assumption the user can change. |
| Labels | Every simulated value carries "Simulé". French first. |
| Layout | Works at 390 px with no horizontal scroll; dark mode follows the system. |

## Pages

`app_name = "m4"`:

| URL | Purpose |
|---|---|
| `/` | Consommation en direct: watts, kWh, savings, points, live curve |
| `/adaptateur/` | Ajouter un adaptateur |
| `/appareils/` | Appliance list and state |
| `/alerte/<id>/` | Alert, explanation, "Appliquer la recommandation" |
| `/recompenses/` | Points, kWh avoided, formula, monthly goal |

## Stories

| ID | Outcome | Priority |
|---|---|---|
| 4.1 | A user creates "Foyer démo" and pairs NABD-0003 | Must |
| 4.2 | The live curve moves when the simulation starts | Must |
| 4.3 | The user reads the alert and applies the recommendation | Must |
| 4.4 | The drop, kWh avoided and points are shown with the formula | Must |
| 4.5 | The user sets a monthly goal and changes the tariff | Should |

## Integration and checks

- Reads M2's household routes; the appliance state becomes corrigé after applying a recommendation.
- Each of the 10 demo steps completes without errors.
- Points match a hand-calculated example; using more than the reference earns zero and subtracts nothing.

## Scaffold preview

The screenshot shows the shared placeholder page, not completed module features.

![M4 placeholder](screenshots/placeholder.png)
