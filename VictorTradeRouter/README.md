# Victor's Trade Router v5.3

This compact Windows package adds a Winward Project-style trade information page and streamlined Route Planner to the existing 17-region Naval Route Tester. The Stage 1 maps, raw obstacle/navigation/ownership masks, TP zones and pairs, and region transforms remain byte-for-byte unchanged. Version 5.3 updates only the route-clearance policy.

## Start the app

1. Extract the ZIP directly to `C:\` so the included folder becomes `C:\VictorTradeRouter`.
2. Double-click `start_windows.bat`.

The active wind model is also stored at the short path `data/wind_v2.json`. This prevents Windows Explorer from silently skipping the file when the ZIP is opened from a long parent folder.

The ZIP contains the official 64-bit Python 3.12 embeddable archive, not a huge expanded runtime. On first launch, the launcher verifies it, expands a private copy under `%LOCALAPPDATA%\NavalTradeManager\Runtime312`, and downloads binary packages from PyPI. Later launches reuse that private runtime. It does not install Python system-wide, change `PATH`, or compile pandas.

## Home trade information

The **Home** page takes only three inputs: origin port, ship, and departure wind heading. A game-style octagonal compass shows the chosen heading. It displays up to 18 profitable routes ranked by expected profit versus estimated voyage effort.

- Hovering a voyage shows cargo, profit, wind burden, estimated length category, distance source, and general bearing.
- Selecting a route opens the Route Planner with origin, destination, ship, and wind already loaded.
- Time is deliberately shown as **Short / Moderate / Long / Very long**, not a false clock ETA.
- Wind is shown as **Favorable / Manageable / Demanding / Difficult** using the general departure course.
- Home ranking uses recorded game Cargo Distance when available and never substitutes it for the generated obstacle-safe path distance. The full pathfinder runs after selection.

## Route Planner

The **Route Planner** handles the whole player flow in one action:

1. Choose trade origin and destination by dropdown or on the unified map. Map mode uses distinct green **ORIGIN**, red **DESTINATION**, and **SELECTION READY** states.
2. Start navigation at the origin port or click the ship's actual current water position.
3. Choose Hoy, Been, or Pembroke.
4. Use stored taxes or enter manual origin-export and destination-import taxes.
5. Enter the in-game ship Bearing and rotate the octagonal N/NE/E/SE/S/SW/W/NW compass arrow to match the game HUD.
6. Select any known enemies and press **GENERATE TRADE ROUTE**.

Home and Route Planner navigation is centered directly beneath the wide, shallow header banner. After charting, the settings panel closes automatically. Cargo and profit remain visible with the zoomable map; secondary route details, tack orders, validation, and calibration notes stay collapsed. If no verified map scale exists, Voyage Details omits the Time metric instead of presenting an unavailable estimate.

The Streamlit **Light** and **Dark** appearance settings are both supported. Page backgrounds, text, metrics, expanders, captions, and chart containers use the active theme palette; the naval blue/gold banner and controls remain consistent in either mode.

The exported route image is map-only: it has no report banner and no numbered region circles. Orange arrows point along the new course at tack locations.
Teleport jumps show the complete paired TP polygons as translucent cyan zones over their respective regions. The sailing line ends inside the entrance polygon and resumes at the corresponding relative position inside the destination polygon; short gold arrows indicate approach and departure. No cross-map connector or `TP IN`/`TP OUT` text is drawn.
Paired TP routes prefer the matching center position inside both polygons after the 8 px TP clearance floor is met. If that point is unreachable, the router tries progressively more distant interior positions. This keeps adjacent Lebarde boxes visually and operationally distinct.
Lebarde's corrected side assignments are: **right vertical → New Catalina** and **left vertical → Blacktip Shoals**. Their polygons are unchanged; only the reversed destination/pair metadata was corrected.

## Adaptive route clearance

The pathfinder no longer treats 24 px as a universal hard wall:

- **14 px** is the preferred open-water clearance.
- **10 px** is the hard core-route floor through necessary narrow channels and island passages.
- Port departure and arrival approaches use a **5 px** local floor.
- Teleport approaches use an **8 px** local floor.
- An exact reviewed port or TP contact point may begin just inside its local tier; only the shortest connection from that recorded endpoint to the tier is treated as an endpoint exception.
- No endpoint exception or route segment may enter the authoritative raw obstacle mask.

The 14 px preference is cost-based, so a materially shorter 10 px channel can be selected instead of an unnecessary wide detour. This is what allows the Vysarian Isles interior passage to be used while keeping 10 px as the hard core minimum.

## Data center

The former Data & Debug and Data Status pages are combined into one collapsed **Data, Debug & Status** panel at the bottom of both Home and Route Planner.

## Wind and sailing rules

- Global wind direction rotates clockwise by **6° per elapsed minute**.
- Random wind strength, regional slow wind, gusts, and storms are intentionally excluded.
- The Hoy uses the supplied preliminary measured direction curve around its confirmed beam-reach orientation: wind approximately 90° to either side is best, while sailing directly with or directly against the wind is poor.
- Without a verified map scale, routing first prefers the fewest valid TP transfers, then compares departure-wind effort and safe tacking within corridors having that same transfer count. This prevents raw screenshot pixels from making an unnecessary multi-TP detour appear faster. Wind rotation and clock ETA remain unavailable until a scale is calibrated.
- Been remains partial empirical plus configurable heuristic. Its provisional optimum is a slight 15° oblique angle rather than direct alignment, and backed headings are unfavorable. Its guidance can shiver the topsail to avoid reverse force and use the movable spanker for turns.
- Pembroke remains an internal Been-based proxy with the same provisional oblique optimum and better backed-sector tolerance. It uses Fore/Main/Mizzen asymmetry; the fixed spanker is never presented as movable.
- Tacks are tested as safe doglegs during candidate evaluation. A tack is kept only when it improves the modeled full-voyage result while staying in the locked navigation and adaptive-clearance masks.
- With a verified scale, the optimizer compares shortest-safe, immediate-wind, delayed-tack, and alternative TP-corridor strategies through final arrival. A longer corridor wins only when its projected ETA is lower outside the tie tolerance.
- Without a verified scale, the app does not pretend to simulate time-driven rotation; it compares the minimum-transfer safe corridors using departure-wind effort and withholds ETA.

## Endpoint and TP robustness

- The visible/economic port coordinate remains unchanged.
- Routing uses a separate connected harbor-water anchor when the marker itself is blocked or isolated.
- The v3 audit repaired Port Louis, Caledonia, Castle Landing, and Griffard's Rock through this separate layer. Griffard's Rock now routes from nearby reviewed harbor water instead of failing at `(402, 382)`.
- Current-position clicks may snap up to 24 px to reachable water, but isolated water and unsafe cross-land choices are rejected.
- TP transitions try multiple reachable points inside the actual TP polygons and alternate region corridors before reporting failure.
- Player-facing errors are short; endpoint snaps, attempted alternatives, candidate strategies, and diagnostic codes are inspectable under **Data & Debug → Route Diagnostics**.

The permanent player disclaimer is shown in a prominent warning panel:

> Regional wind speed variations, very slow winds, gusts and storms are not accounted for and may change actual travel time.

## ETA calibration

No conversion from route pixels to nautical miles was supplied, and Cargo Distance is game-economy data rather than safe sailing distance. Therefore the package does **not** guess a scale.

Until a verified `pixels per nautical mile` value is entered under **Data & Debug → Model Settings**, the tool compares wind routes with a relative travel-time score and withholds a knot-based ETA. Once a verified scale is entered, it evaluates the 6°/minute wind rotation segment by segment and shows an approximate direction-only ETA.

## Trade and data rules

- All 58 current economic ports and editable tax defaults are preserved.
- Deadman's Murcia is active in East Somerset for economics, but routes remain disabled until its exact navigable-water anchor is confirmed.
- Recorded game destination Value is preferred. `DERIVED` is used internally only when the recorded Value is missing and the formula is genuinely required.
- Destination import tax is applied separately. Depreciation is not modeled.
- Cargo Distance remains separate from generated route distance.
- The ship carries `floor(capacity / cargo weight) + 1` units.
- Confirmation, estimate, derived, proxy, and heuristic labels stay in **Data & Debug**, not in normal player results.

## Diplomacy

Ownership is stored per port and remains editable. The v2 ZIP referenced an ownership image but did not include it, so no nation was guessed. After ownership is entered in **Data & Debug → Ownership**, the app can warn about enemy origin, destination, and confidently single-control route regions. Warnings do not block the route.

## Integrity and tests

Run these with the private runtime after first launch:

```bat
"%LOCALAPPDATA%\NavalTradeManager\Runtime312\py\python.exe" verify_geometry_integrity.py
"%LOCALAPPDATA%\NavalTradeManager\Runtime312\py\python.exe" test_economy.py
"%LOCALAPPDATA%\NavalTradeManager\Runtime312\py\python.exe" test_routes.py
"%LOCALAPPDATA%\NavalTradeManager\Runtime312\py\python.exe" test_v2.py
"%LOCALAPPDATA%\NavalTradeManager\Runtime312\py\python.exe" test_v3.py
"%LOCALAPPDATA%\NavalTradeManager\Runtime312\py\python.exe" test_v4.py
```

Expected geometry result: **PASS**, with all 118 protected files unchanged.

## Important files

- `data/economy_data.json` — authoritative editable trade/economy layer.
- `data/port_ownership.json` — editable per-port nation mapping.
- `data/v2_settings.json` — wind-arrow convention and optional verified map scale.
- `data/navigation_anchors_v3.json` — separate connected-water routing anchors; Stage 1 port coordinates are not edited.
- `data/wind_v2.json` — active short-path copy of the v2 wind handoff.
- `data/source_import/naval_route_trade_wind_handoff_v2.json` — original v2 handoff retained intact as a fallback/audit source.
- `data/source_import/naval_route_trade_test_patch_v3.json` — original v3 trade-test patch retained intact.
- `recommendations.py` — fast profit/wind/voyage-effort ranking for the Home trade board.
- `interface_v4.py` — Winward-style Home, Route Planner, collapsed results, and combined data center.
- `test_adaptive_clearance.py` — adaptive-policy and Vysarian interior-passage regression checks.
- `V5_3_ADAPTIVE_CLEARANCE_REPORT.md` — verification results for this update.
- `wind.py` — wind-direction models, rotating-wind evaluation, safe tack comparison, and sail instructions.
- `routing.py` — preserved geometry pathfinder plus bounded safe-corridor candidates and current-position entry.
- `WORK_MODE_NAVAL_ROUTE_V2_INSTRUCTIONS.md` — the supplied update instructions.
- `WORK_MODE_TRADE_TEST_PATCH_V3.md` — the supplied v3 patch instructions.

The remaining blockers are the Deadman's Murcia route anchor, exact Been curve, direct Pembroke measurements, numeric sail-turn effects, verified port ownership, and map-to-nautical-mile scale. Multi-stop trade-loop and profit-per-minute optimization are not part of this release.
