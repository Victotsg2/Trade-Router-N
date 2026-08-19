# Naval Trade Route Tester v3 — Merge Validation

## V3 PATCH COMPLETE — CALIBRATION ITEMS REMAIN

The attached v3 trade-test patch was applied incrementally to the compact 17-region project. The existing world was not rebuilt, restitched, rescaled, or replaced.

## Successfully implemented

- Separate semantic port markers and connected harbor-water navigation anchors.
- Safe endpoint resolution for Port Louis, Caledonia, Castle Landing, and Griffard's Rock without editing Stage 1 geometry.
- Louisbourg → Griffard's Rock now succeeds; Griffard's semantic point `(402, 382)` routes to reviewed harbor water `(338, 359)`.
- Current-position validation and local shoreline snapping up to 24 px, with isolated-water and unsafe selections rejected.
- Multiple reachable points inside each TP polygon plus alternate TP-corridor fallback.
- Specific route error codes and a downloadable **Route Diagnostics** view; normal player errors remain concise.
- Full-voyage wind comparison across shortest-safe, immediate-wind, delayed-tack (6/12/18 minute), and alternate TP-corridor strategies when a verified scale exists.
- Clockwise global wind rotation remains 6° per elapsed minute and wind intensity remains excluded.
- Non-shortest route explanations and planned tack time/expected wind details.
- High-contrast map selection states for **ORIGIN**, **DESTINATION**, and **SELECTION READY**.
- HUD-style octagonal compass with N, NE, E, SE, S, SW, W, and NW.

## Preserved data and geometry

- **118 of 118 protected geometry files are byte-for-byte unchanged.**
- Raw obstacle masks, navigation masks, ownership masks, TP polygons/pairs, coordinate transforms, and unified map registration match the SHA-256 baseline.
- All 58 economic ports, taxes, cargo data, sale data, ship data, diplomacy data, and v2 wind inputs remain present.
- Deadman's Murcia remains active for economics but route-ineligible until an exact navigable-water anchor is supplied.
- The two independent Lebarde ↔ West Somerset TP pairs remain independent.
- Cargo Distance remains separate from generated obstacle-safe route distance.

## Validation results

- Geometry integrity: **PASS** — 118/118 protected files unchanged.
- Stage 1 port-anchor audit: **PASS** — 57/57 coordinate-backed ports resolve to connected navigation water.
- TP portal audit: **PASS** — every paired TP has reachable candidate points on both sides.
- Region graph: **PASS** — all 17 regions are mutually connected through the preserved TP graph.
- Economy validation: **PASS** — 58 ports, 3,240 destination rows, statuses preserved, taxes separate, and +1 carried cargo unit.
- Representative route suite: **PASS** — seven same-region and cross-region voyages.
- Unit/regression suite: **PASS** — 24 tests, including endpoint snapping, TP reachability, Louisbourg → Griffard's Rock, Louisbourg → Port Royal candidate comparison, current-position snapping, wind rotation, UI states, and compass directions.
- Live Streamlit UI: **PASS** — origin/destination states and compass visually checked; no browser console warnings or errors.

## Louisbourg → Port Royal regression note

The patch did not supply the exact departure wind angle or a verified pixels-per-nautical-mile scale from the 49:48.8 recording. Replaying its real ETA would therefore require guessing, which this release does not do.

A deterministic regression fixture using **0° wind toward** and **100 px per nautical mile** (test-only inputs, not claimed calibration) generated eight safe corridors and compared 40 corridor/strategy combinations. The shortest corridor's direct-progress ETA was 1,135.231 minutes; its immediate-wind variant was 546.491 minutes. The selected test-only corridor was Belle Isles → Îles de Louis → Saint-Pierre → Kingston at 535.424 minutes. Its longer distance was accepted only because its simulated full-voyage ETA was lower. These values validate comparison behavior only and are not player-facing game predictions.

## Items still blocking precise/full optimization

1. **Verified map/path scale:** required for trustworthy nautical-mile conversion, ETA, and time-driven wind rotation in normal use.
2. **Recorded departure wind for the 49:48.8 validation voyage:** required to replay that exact voyage rather than a regression fixture.
3. **Deadman's Murcia geometry:** active for economics, but its exact coordinate and harbor-water anchor remain unconfirmed.
4. **Been calibration:** its exact speed-versus-relative-wind curve remains partial/heuristic.
5. **Pembroke calibration:** it remains a Been-based proxy, not a measured curve.
6. **Sail turn timing:** numeric spanker/mast-asymmetry effects remain unmeasured.
7. **Ownership mapping:** no ownership image was present in the v2 package, so ownership remains user-editable rather than guessed.
8. **Missing trade observations:** unresolved rows remain missing; no values were fabricated.

The package does not implement multi-stop trade loops or profit-per-minute optimization.
