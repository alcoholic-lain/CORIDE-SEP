# 09 — Plan, team and pitch

**Source:** the workspace's 24-hour plan, team roles, checklist, pitch scripts, Q&A and risks.

## Timeline (from the workspace)

| Hours | Phase | Output |
|---|---|---|
| 0–2 | Scoping | Data contract written, stack chosen, Git repo ready |
| 2–8 | Foundations | API, database, simulator, screen skeleton. POST /mesures stores data. |
| 8–12 | Intelligence | Detection, alerts, explanations. An anomaly fires end to end. |
| 12–14 | Integration 1 | Whole 10-step journey runs |
| 14–18 | Finishing | STEG view, rewards, offline demo |
| 18–21 | Freeze and test | No new features. Three clean rehearsals. |
| 21–24 | Pitch | Slides, rehearsal, backup video |

Checkpoints: h1 (contract frozen), h6, h12, h18 (feature freeze).

## Team (from the workspace; names to confirm)

| Role | Owns |
|---|---|
| AI | 04 ai, forecast, recommendation text, simulated dataset |
| Rust dev 1 | 02 api, 03 data, alert rules, kWh calculation |
| Rust dev 2 (Linux) | 01 adapter, 08 simulator, local deploy, offline mode |
| Member 4 (confirm) | 06 user space, 07 STEG view, slides and pitch |

Git: one branch per person; merge at h6, h12 and h18.

## Pitch (3 minutes, workspace script)

- 0:00 Problem: electricity is invisible, the bill arrives late, STEG sees peaks too late.
- 0:30 Nabd connects the home, the building and the institution.
- 1:00 Live demo, labelled simulated. An air conditioner drifts; the AI explains and recommends; the user applies it; consumption drops.
- 2:00 STEG view, aggregated. No household is ever cut off. Rewards compare each home to itself.
- 2:40 Honest prototype today; certified plugs, then water and solar tomorrow.

Key lines: "We don't sell a meter; we make electricity readable." · "What you see is simulated, and it says so on screen." · "Nobody is ever cut off."

The 5-minute version adds two sourced figures (Tunisia and Japan) and an architecture slide.

## Q&A

The workspace has 18 prepared answers. Keep them in the deck. The ones most likely from the jury: why AI, how false alarms are avoided, what happens when the internet fails, and how the data is protected.

## Risks

| Risk | Fallback |
|---|---|
| No hardware | Labelled simulator, printed QR code |
| Internet down | Offline demo mode, video |
| Live bug | Preloaded data, reset button |
| Running late | Freeze at h18, cut bonus features |
| Stack too ambitious | Switch to FastAPI after 15 minutes of hesitation |
| Electrical danger | No work on live circuits, ever |

## Sources to cite

The workspace says to find two reliable sources (STEG, ANME, or the Japanese energy agency) for every figure in the pitch. Nothing in it is an official number yet.
