# Module 1 — Adapter and simulator

**Owner:** Rust dev 2 (Linux) · **Django app:** `m1` · **Branch:** `m1`
**Dependencies:** M2 (data contract, `POST /mesures`) · **Used by:** M2 (stores readings), M3 (anomaly input), M4 (live curve)
**Plan:** Sprint 1 — adapter IDs and simulator posting readings · Sprint 2 — demo scenarios and offline buffer · Sprint 3 — preloaded demo, reset button, backup video

Source: [k-mod/mieruka-01-adapter.md](../k-mod/mieruka-01-adapter.md), [k-mod/mieruka-08-simulator-demo.md](../k-mod/mieruka-08-simulator-demo.md).

## Features

- Adapter identity `NABD-xxxx`, printed on a QR code that carries only the identifier and measures nothing. Demo IDs: `NABD-0001` to `NABD-0005`; the first two are already paired.
- Virtual adapters for five appliances (refrigerator, computer, TV, air conditioner, phone charger), each with a base power and small random variation. The refrigerator cycles on and off.
- Demo scenario buttons: "Pic inhabituel" (brief spike) and "Clim anormale" (air conditioner at higher load).
- Demo modes: live (simulator to API), offline (local data, full 10 steps), preloaded (demo data + "Réinitialiser"), video (60-second recording, never presented as live).
- Optional physical demo: a certified commercial smart plug, or a phone reading a printed QR code. No work on mains, ever.

## Data and rules

One measurement, frozen at hour 1 in one shared file:

```json
{ "adaptateur_id": "NABD-0003", "horodatage": "2026-11-21T20:00:00+01:00", "watts": 110.4, "source": "simulee" }
```

| Rule | Requirement |
|---|---|
| Frequency | One measurement per minute per adapter; a simulated minute is one demo tick. |
| Source label | `source` is `simulee` or `reelle`; the UI shows "Simulé" when it is `simulee`. |
| Unknown ID | Reject with a clear message. |
| Invalid watts | Reject negative or non-numeric values. |
| Duplicate (adapter, timestamp) | Store once. |
| Unpaired adapter | Accept the measurement but show it to no user. |
| Offline | Buffer to local storage and send the backlog once when the network returns. |

## Pages

`app_name = "m1"`:

| URL | Purpose |
|---|---|
| `/` | Simulator control: start/pause, "Pic inhabituel", "Clim anormale", reset |

## Stories

| ID | Outcome | Priority |
|---|---|---|
| 1.1 | Five virtual adapters post one valid measurement per tick | Must |
| 1.2 | A scenario button makes one appliance drift so an alert can fire | Must |
| 1.3 | The demo runs fully offline and replays the buffer once online | Must |
| 1.4 | Preloaded data and a reset button recover from a live bug | Should |
| 1.5 | A certified plug or printed QR code is used for the physical demo | Could |

## Integration and checks

- Readings are posted to M2's `POST /mesures`; M3 and M4 read them from there.
- A valid ID is stored with `source` set; an unknown ID stores nothing.
- Replaying the same measurement does not create a duplicate.
- The offline buffer sends everything, once, when the network comes back.
- The 10-step demo passes three times in a row (checkpoint at 18 h).

## Scaffold preview

The app currently renders the shared placeholder page at `/m1/`, not completed module features. No screenshot has been captured yet.
