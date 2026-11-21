# 01 — Adapter

**Status:** MVP (simulated) · **Real hardware:** optional (certified commercial plug) · **Depends on:** 03 data contract · **Used by:** 02 api

## Purpose

An adapter is the thing that produces measurements. In the demo it is a virtual adapter (the simulator). In a real pilot it is a certified plug with a measurement chip. The API cannot tell which one sent a value, except from the `source` field.

## Identity

- Each adapter has an ID printed on a QR code: `NABD-xxxx`.
- The QR code carries only the identifier. It does not measure anything.
- The demo has five identifiers: `NABD-0001` to `NABD-0005`. The first two are already paired in the demo.
- An adapter is paired to a user account and to one appliance (see 02).

## Measurement contract

One measurement is:

```json
{ "adaptateur_id": "NABD-0003", "horodatage": "2026-11-21T20:00:00+01:00", "watts": 110.4, "source": "simulee" }
```

- `source` is `simulee` (simulated) or `reelle` (real). The UI must show "Simulated" when it is `simulee`.
- One measurement per minute per adapter. A simulated minute is one tick in the demo.
- This contract is frozen at hour 1 in one shared file. Changes after that need everyone's agreement.

## Rules

| Rule | Requirement |
|---|---|
| Unknown ID | Reject with a clear message. |
| Negative or non-numeric watts | Reject. |
| Duplicate (adapter, timestamp) | Store once. |
| Unpaired adapter | Accept the measurement but do not show it to any user. |
| Offline demo | The simulator writes to local storage when there is no network and sends the backlog when it returns. |

## Simulator behaviour (demo)

- Five appliances: refrigerator, computer, TV, air conditioner, phone charger. Each has a base power and a small random variation.
- The refrigerator cycles on and off.
- Scenarios, triggered by buttons: "Pic inhabituel" (a brief spike on a device) and "Clim anormale" (the air conditioner runs at a higher load).
- The simulator is clearly labelled as simulated on every screen.

## Tests

- A measurement posted with a valid ID is stored with `source` set.
- An unknown ID returns an error and stores nothing.
- Replaying the same measurement does not create a duplicate.
- The offline buffer sends everything, once, when the network comes back.
