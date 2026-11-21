# 06 — User space

**Status:** MVP · **Platform:** responsive web, shown in the Android app as a WebView · **Depends on:** 02 api

## Screens (from the prototype)

| Screen | Shows | Actions |
|---|---|---|
| Ajouter un adaptateur | Field for NABD-xxxx and a "Scanner (simulé)" button | Pair the adapter |
| Consommation en direct | Total watts, energy kWh, estimated savings, points, live curve | Pause, "Pic inhabituel", "Clim anormale", reset |
| Appareils | Each appliance: ID, watts, state (normal, anormal, corrigé) | None |
| Alerte | Anomaly, the AI's explanation, the recommendation | Apply recommendation |
| Récompenses | Points, kWh avoided, the formula | None |
| Objectif | Monthly goal bar, estimated cost in TND | Change tariff |
| Espace STEG | Aggregated view (see 07) | None |

## Demo flow (10 steps, from the workspace)

1. Open the app and create the profile "Foyer démo".
2. Enter NABD-0003, or scan. It appears in the list.
3. Start the simulation: the curve moves.
4. Click "Clim anormale".
5. Read the alert and the AI's explanation.
6. Apply the recommendation.
7. Show the drop, the kWh avoided and the points.
8. Open the STEG view: aggregated and anonymous.

## Rules

- Every simulated value carries the label "Simulé".
- Text is in French first. English can follow.
- The page works at 390 px width with no horizontal scroll.
- Dark mode follows the system setting.

## Tests

- Each of the 10 steps can be completed without errors.
- Applying a recommendation changes the appliance state to corrigé.
