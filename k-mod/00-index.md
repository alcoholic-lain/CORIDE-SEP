# Nabd: modules (aligned with the team workspace)

Source: `SUBJECT/Nabd__Espace_de_travail_KIZUNA_2026.html` (team workspace, 24 hours, KIZUNA 2026).
Nabd helps each household see where its electricity goes, warns about waste before the bill, and gives STEG an anonymous overview. The prototype runs on simulated data, labelled as simulated on screen.

## Module map

| # | Module | What it does | Source in the workspace |
|---|---|---|---|
| 01 | [adapter](01-adapter.md) | Adapter identity (NABD-xxxx) and measurement intake (`POST /mesures`), simulated or real | Adaptateur, Architecture |
| 02 | [api](02-api.md) | Users, pairing, readings, alerts, rewards, HTTP routes | Architecture, Base de données |
| 03 | [data](03-data.md) | SQLite schema and the frozen data contract | Base de données, Contrat de données |
| 04 | [ai](04-ai.md) | Median anomaly rule, same-hour forecast, recommendation text | IA |
| 05 | [rewards](05-rewards.md) | Fair points for kWh avoided against the household's own reference | Système de récompenses |
| 06 | [user-space](06-user-space.md) | The household's screens: add adapter, live curve, alert, savings | Parcours, Prototype |
| 07 | [steg-space](07-steg-space.md) | Aggregated, anonymous view for STEG, with a minimum of 10 households | Espace STEG |
| 08 | [simulator-demo](08-simulator-demo.md) | Virtual adapters, the demo scenario, offline mode, backup video | Prototype, Démo, Secours |
| 09 | [plan-and-pitch](09-plan-and-pitch.md) | 24-hour plan, team split, checkpoints, pitch, Q&A, risks | 24 h, Équipe, Pitch, Jury, Risques |

## Scope rules from the workspace

- Electricity: we never touch mains. The physical demo is a certified commercial smart plug if a team member has one, or a phone reading a printed QR code. The QR code carries only an identifier (for example NABD-0001) and measures nothing.
- Shown in the product: "Simulated data" wherever simulated values appear.
- Not in MVP: children's section and games (cut), native Android (cut, the web app is responsive), water and solar (vision only).
- Architecture: one server, one database, no external services. A Python AI module is called by the API.

## Open decision

The workspace suggests Rust (Axum) for the API, with FastAPI as the fallback if nobody knows Axum well. Pick within 15 minutes. The repo's existing `m1`–`m5` apps are Django on Vercel; that is not what the workspace describes. Team decision needed before the 0–2 h block.
