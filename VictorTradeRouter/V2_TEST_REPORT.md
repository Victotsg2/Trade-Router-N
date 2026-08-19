# V2 Test Report

Date: 2026-08-18

## Automated results

- Geometry integrity: **PASS** — 118/118 protected files unchanged.
- Economy: **PASS** — 58 current ports, 3,240 destination rows, status preservation, separate taxes, and +1 carried cargo unit.
- Existing obstacle-safe routes: **PASS** — all seven representative same-region and cross-region routes.
- V2 tests: **PASS** — 14 tests.
- Streamlit smoke run: **PASS** — no script exceptions; default combined Petit Anvers → Port Royal result generated; map and current-position modes rendered.

## Required v2 scenarios

1. Hoy favorable direction model, same-region route — PASS.
2. Hoy poor wind with a safe worthwhile tack — PASS.
3. Been bad topsail state recommends shiver — PASS.
4. Been can choose a longer wind-favored TP corridor over the shortest corridor — PASS.
5. Pembroke proxy uses Fore/Main/Mizzen and never gives a movable-spanker instruction — PASS.
6. Long cross-region voyage advances wind clockwise throughout the calibrated test simulation — PASS.
7. Manual origin-export and destination-import tax override — PASS.
8. Unified-map port selection mode renders with 57 coordinate-backed clickable ports — PASS.
9. Current-position navigation start replaces route geometry start while retaining the trade origin — PASS.
10. Enemy origin/destination/route warning logic is per-port and nonblocking — PASS.
11. Quiet route result when no warning condition is material — PASS.
12. Storms, gusts, regional slow wind, and random intensity never enter optimization — PASS.

The calibrated test simulations use an explicit test scale solely to exercise time-driven rotation. The shipped user setting remains blank, so the app does not claim that the test scale is the game's real scale.
