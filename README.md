# Kizuna

Kizuna is a Django hackathon template with five placeholder modules (M1–M5) and a shared core app. Team **Zero-Ichi**'s KIZUNA 2026 app is **Mieruka**: it helps each household see where its electricity goes, warns about waste before the bill, and gives STEG an anonymous overview. The prototype runs on simulated data, labelled as simulated on screen. The full module breakdown is in [k-mod/mieruka-00-index.md](k-mod/mieruka-00-index.md).

## Team and branding

- **App:** Mieruka (見える化, "visibility"). The workspace subject calls the product Nabd; the app uses Mieruka. Adapter IDs keep the `NABD-xxxx` format from the frozen data contract.
- **Team:** Zero-Ichi.
- **App icon:** [assets/mieruka/mieruka-app-icon-v8-rounded.svg](assets/mieruka/mieruka-app-icon-v8-rounded.svg) — v8 flat cartoon, `#CD181F` red background, pale yellow ring, red hat. Full-bleed PNG: [mieruka-app-icon-v8-fullbleed-1024.png](assets/mieruka/mieruka-app-icon-v8-fullbleed-1024.png).
- **Team logo:** [assets/mieruka/zero-itchi-fun-logo.svg](assets/mieruka/zero-itchi-fun-logo.svg) (static) and [assets/mieruka/zero-itchi-fun-logo-animated.svg](assets/mieruka/zero-itchi-fun-logo-animated.svg) (animated) — fox and berries. PNG: [zero-itchi-fun-logo-512.png](assets/mieruka/zero-itchi-fun-logo-512.png); animation page: [zero-itchi-animation.html](assets/mieruka/zero-itchi-animation.html).

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
| M1 | [AI.log](m1/AI.log) | [spec](m1/mieruka-m1-adapter-simulator.md) | [preview](m1/screenshots/placeholder.png) |
| M2 | [AI.log](m2/AI.log) | [spec](m2/mieruka-m2-api-data.md) | [preview](m2/screenshots/placeholder.png) |
| M3 | [AI.log](m3/AI.log) | [spec](m3/mieruka-m3-ai-anomalies.md) | [preview](m3/screenshots/placeholder.png) |
| M4 | [AI.log](m4/AI.log) | [spec](m4/mieruka-m4-user-space-rewards.md) | [preview](m4/screenshots/placeholder.png) |
| M5 | [AI.log](m5/AI.log) | [spec](m5/mieruka-m5-steg-space.md) | [preview](m5/screenshots/placeholder.png) |

## Development

See [DEV.md](DEV.md) to install and run the project.
The native Android client lives in `mobile/`; its test instructions are also documented in [DEV.md](DEV.md).
