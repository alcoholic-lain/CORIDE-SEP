# Kizuna

Kizuna is a Django hackathon template with five placeholder modules (M1–M5) and a shared core app, ready to be rebranded and filled in with your team's features.

## Modules

| Module | Function | Owner |
|---|---|---|
| M1 | Messaging and reviews (chat, guest mode, voice calls) | — |
| M2 | Placeholder module | — |
| M3 | Placeholder module | — |
| M4 | Placeholder module | — |
| M5 | Placeholder module | — |

## Project state

Most modules are still scaffolds. M1 ships a working guest chat with reviews/moderation as a reference implementation. See each app's log, spec, and preview:

| App | Log | Spec | Preview |
|---|---|---|---|
| kizuna (core) | [AI.log](kizuna/AI.log) | — | [preview](kizuna/screenshots/home.png) |
| M1 | [AI.log](m1/AI.log) | [spec](m1/05_communication-feedback.md) | [preview](m1/screenshots/coms.png) |
| M2 | [AI.log](m2/AI.log) | [spec](m2/04_reservation-management.md) | [preview](m2/screenshots/reservations.png) |
| M3 | [AI.log](m3/AI.log) | [spec](m3/03_trip-management.md) | [preview](m3/screenshots/trips.png) |
| M4 | [AI.log](m4/AI.log) | [spec](m4/01_user-management.md) | [preview](m4/screenshots/users.png) |
| M5 | [AI.log](m5/AI.log) | [spec](m5/02_vehicle-management.md) | [preview](m5/screenshots/vehicles.png) |

## Development

See [DEV.md](DEV.md) to install and run the project.
The native Android client lives in `mobile/`; its test instructions are also documented in [DEV.md](DEV.md).
