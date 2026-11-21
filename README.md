# Kizuna

Kizuna is a Django hackathon template with five placeholder modules (M1–M5) and a shared core app. The KIZUNA 2026 subject is **Nabd**: it helps each household see where its electricity goes, warns about waste before the bill, and gives STEG an anonymous overview. The prototype runs on simulated data, labelled as simulated on screen. The full module breakdown is in [k-mod/00-index.md](k-mod/00-index.md).

## Modules

| Module | Function | Owner |
|---|---|---|
| M1 | Adapter and simulator (NABD-xxxx IDs, `POST /mesures` readings, demo scenarios, offline mode) | Rust dev 2 |
| M2 | API and data (SQLite schema, pairing, alerts, rewards and STEG routes) | Rust dev 1 |
| M3 | AI anomalies (sliding-median rule, explanation, recommendation) | AI |
| M4 | User space and rewards (household screens, fair points for kWh avoided) | Member 4 |
| M5 | STEG space (aggregated, anonymous, 10-household minimum) | Member 4 |

## Project state

All modules are scaffolds that render the shared placeholder page. See each app's log, spec, and preview:

| App | Log | Spec | Preview |
|---|---|---|---|
| kizuna (core) | [AI.log](kizuna/AI.log) | — | [preview](kizuna/screenshots/home.png) |
| M1 | [AI.log](m1/AI.log) | [spec](m1/01_adapter-simulator.md) | — |
| M2 | [AI.log](m2/AI.log) | [spec](m2/02_api-data.md) | [preview](m2/screenshots/reservations.png) |
| M3 | [AI.log](m3/AI.log) | [spec](m3/03_ai-anomalies.md) | [preview](m3/screenshots/trips.png) |
| M4 | [AI.log](m4/AI.log) | [spec](m4/04_user-space-rewards.md) | [preview](m4/screenshots/users.png) |
| M5 | [AI.log](m5/AI.log) | [spec](m5/05_steg-space.md) | [preview](m5/screenshots/vehicles.png) |

## Development

See [DEV.md](DEV.md) to install and run the project.
The native Android client lives in `mobile/`; its test instructions are also documented in [DEV.md](DEV.md).
