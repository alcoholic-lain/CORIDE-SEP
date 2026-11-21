# Module 3 — AI anomalies and recommendations

**Owner:** AI · **Django app:** `m3` · **Branch:** `m3`
**Dependencies:** M2 (measurements) · **Used by:** M2 (alerts), M4 (alert screen, reference for rewards)
**Plan:** Sprint 1 — sliding-median anomaly rule · Sprint 2 — explanation and recommendation text · Sprint 3 — same-hour forecast, optional Isolation Forest comparison

Source: [k-mod/04-ai.md](../k-mod/04-ai.md).

## Features

- Simple, explainable rules in Python; no deep learning (too little data in 24 hours).
- Anomaly detection per adapter and hour of day, with alert kinds "Clim anormale" and "Pic inhabituel".
- Rule-based explanation and recommendation, rephrased into a clear French sentence. Predefined sentences are enough if no language model is available.
- Bonus: same-hour forecast (7-day average adjusted by recent trend), labelled as an estimate.

## Data and rules

| Rule | Requirement |
|---|---|
| Baseline | Sliding median of recent watts per adapter and hour of day. |
| Trigger | Current value more than 35% above the median for 3 measurements in a row. |
| Isolated spike | One spike never raises an alert. |
| Explanation | Non-empty explanation and recommendation for every alert kind. |
| Model dependency | Nothing in the demo depends on a language model. |

Output:

```json
{ "alerte": "anomalie", "appareil": "Climatisation", "pourcentage_au_dessus": 58,
  "explication": "...", "recommandation": "Réglez la consigne à 26 °C et nettoyez le filtre." }
```

## Pages

`app_name = "m3"`:

| URL | Purpose |
|---|---|
| `/` | Rule status and recent alerts (debug view for the team) |

## Stories

| ID | Outcome | Priority |
|---|---|---|
| 3.1 | A drifting appliance raises one alert after 3 readings above threshold | Must |
| 3.2 | Each alert comes with an explanation and a recommendation | Must |
| 3.3 | A same-hour forecast is shown as an estimate | Could |
| 3.4 | Isolation Forest is compared against the rule | Could |

## Integration and checks

- Called by M2 on new measurements; writes `alertes.explication`. M4 shows the result.
- Three measurements above the threshold raise one alert; two do not.
- A single spike raises nothing.
- Explanation and recommendation are non-empty for each alert kind.

## Scaffold preview

The screenshot shows the shared placeholder page, not completed module features.

![Current module placeholder](screenshots/trips.png)
