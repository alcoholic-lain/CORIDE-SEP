# 08 — Simulator and demo

**Status:** MVP · **Depends on:** 01 adapter, 02 api, 06 user space

## Purpose

Make the live demo reliable. The prototype already runs in the browser with five simulated devices; the same behaviour must run against the real API.

## Demo modes

| Mode | When | What |
|---|---|---|
| Live | Normal | Simulator sends to the API |
| Offline | Internet fails | Local data, no network. Runs the full 10 steps. |
| Preloaded | Bug on stage | Demo data already in the database. "Réinitialiser" button. |
| Video | Everything else fails | A 60-second recording made at hour 20, played with an honest explanation |

## Rules

- Never present a recording as live.
- Keep the offline mode and the video ready before the pitch.
- The physical demo is a certified smart plug if someone has one. Otherwise, a phone reads a printed QR code.

## Checks

- The 10-step demo passes three times in a row without errors (checkpoint at 18 h, from the workspace plan).
- The offline mode works with the network disabled.
- The video is recorded and saved before 20 h.
