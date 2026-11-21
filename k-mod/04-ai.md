# 04 — AI module

**Status:** MVP (rules) · **Language:** Python · **Called by:** 02 api · **Depends on:** 03 data

The workspace is explicit: no deep learning, because there is too little data in 24 hours. The AI is a set of simple, explainable rules. Isolation Forest is an optional bonus, compared against the rule.

## Anomaly rule (MVP)

- For each adapter and each hour of the day, keep a sliding median of recent watts.
- Raise an alert when the current value is more than 35% above that median for **3 measurements in a row**.
- One isolated spike never raises an alert. This limits false alarms.
- Alert kinds used in the demo: "Clim anormale", "Pic inhabituel".

## Forecast (bonus)

- Average the same hour over the last 7 days, then adjust by the recent trend.
- Show it as an estimate, labelled as not measured in 24 hours.

## Explanation and recommendation

- Rule-based text, then rephrased into a clear sentence. Example for the air conditioner: "the air conditioner works much harder than usual, probably a set temperature that is too low or a dirty filter." Recommendation: "set it to 26 °C and clean the filter."
- If no language model is available, the predefined sentences are enough. Nothing in the demo depends on a model.

## Output

```json
{ "alerte": "anomalie", "appareil": "Climatisation", "pourcentage_au_dessus": 58,
  "explication": "...", "recommandation": "Réglez la consigne à 26 °C et nettoyez le filtre." }
```

## Tests

- Three measurements above the threshold raise one alert. Two do not.
- A single spike raises nothing.
- The explanation and recommendation are non-empty for each alert kind.
