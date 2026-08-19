# WORK MODE UPDATE — Naval Trade Route Tester v2

## Goal
Update the EXISTING 17-region Naval Route Tester. Do not rebuild or replace its current world geometry.

Attach/import:
- `naval_route_trade_wind_handoff_v2.json`
- the existing project/ZIP
- the user's ownership/flag world image if port ownership is not already stored
- the user-provided wind compass and Basic Sailing reference images if useful for UI/reference

## Non-negotiable
Preserve the current:
- 17-region stitched/unified world
- obstacle masks
- TP-zone geometry and TP pair transforms
- ownership/ROI masks
- existing region transforms
- approved hard-clearance routing behavior
- continuous cross-region route rendering

Do not restitch, rescale, redraw, or replace working map geometry.

---

## 1. Merge Trade Calculation + Route Generation
There should no longer be separate "Trade Calculation" and "Route Generation" flows.

Use one player workflow:

1. Trade Origin Port
2. Navigation Start Position
   - Default: origin port
   - Optional: click actual current ship position on map
3. Destination Port
4. Ship
5. Tax
6. Wind at departure
7. `GENERATE TRADE ROUTE`

Generating should simultaneously:
- choose cargo from origin
- compute ship cargo units
- compute purchase cost
- apply taxes
- compute destination sale/profit
- generate safe route
- evaluate wind over time
- compare route alternatives
- add tacks where worthwhile
- produce sail-handling instructions
- produce ETA and warnings

---

## 2. Taxes
Add a `Tax` dropdown:

- Default
- Manual

Default:
- use stored origin Export Tax
- use stored destination Import Tax

Manual:
- show `Origin Export Tax %`
- show `Destination Import Tax %`
- prefill both with defaults
- recalculate economics immediately

Tax values remain editable defaults in the underlying data.

---

## 3. Start/Destination Selection
Keep:
- Starting Region / Port dropdowns
- Destination Region / Port dropdowns

Add:
- `Dropdown | Map` selector

Map mode:
- unified 17-region world map
- first selected port = trade origin
- second selected port = destination
- map and dropdown selections synchronize
- show hover/click port + region
- clear/reset button

Also add optional:
`Navigation Start: Port | Current Position`

If Current Position:
- user clicks their actual ship location on map
- route geometry starts there
- cargo economics still use the selected trade origin port

---

## 4. Wind Input — No Absolute Angle Knowledge Required
The game usually does not give the player an absolute wind angle.

Use a HUD-matching input:

- Player enters the in-game `Bearing` number.
- Show a compass that behaves visually like the game HUD.
- The ship icon remains fixed.
- Compass labels rotate based on entered ship bearing.
- Player drags the wind arrow until it visually matches the in-game HUD.
- Tool converts this internally to global wind direction.

Default convention:
- 0° = North
- 90° = East
- 180° = South
- 270° = West
- wind arrow represents the direction wind is pushing/blowing TOWARD

Keep the transform configurable in case later validation shows the in-game arrow uses the opposite convention.

The player should not need to type an absolute wind angle.

---

## 5. Global Wind Rotation
Use DIRECTION only.

Do not model:
- random regional wind speed
- slow-wind events
- storms
- gusts

Global direction rotates clockwise 360° every 60 minutes:

`wind(t) = (wind_at_departure + 6° * elapsed_minutes) mod 360`

Evaluate the changing wind throughout the voyage, not as one fixed direction.

Permanent disclaimer:

> Wind estimates account for global wind direction and its clockwise rotation. Regional wind speed variations, very slow winds, gusts and storms are not accounted for and may change actual travel time.

---

## 6. Route Objective
Do not automatically choose the geometrically shortest route.

Generate and compare safe candidates:
- shortest safe route
- wind-favored safe route
- alternative TP corridors where realistic

Primary objective:
`minimum estimated travel time`

Safety remains mandatory:
- no land
- no rocks
- no shoals
- approved hard clearance
- valid TP transitions
- port entry/exit exceptions only where necessary

A longer route may win if it is materially faster under wind.

---

## 7. Wind Speed Model
All ship wind-direction models normalize the BEST practical angle to:

`9.0 kt`

Do not use the raw speed seen in recordings as a universal maximum because instantaneous wind intensity is intentionally ignored.

### Hoy — preliminary empirical curve
Deviation from best/favorable heading:

| Deviation | Modeled Speed |
|---|---:|
| 0° | 9.0 kt |
| 15° | 7.7 kt |
| 30° | 5.9 kt |
| 45° | 4.5 kt |
| 60° | 3.2 kt |
| 75° | 1.9 kt |
| 90° | 0.5 kt |

Do not confidently extrapolate beyond about 90° yet.

Hoy favorable behavior:
- approximately parallel/downwind

### Been
Status:
- partial empirical + heuristic

Known:
- best at a slight favorable angle rather than direct favorable alignment
- bad sail state against wind can create reverse movement
- observed approximately -1.3 kt in a bad state
- sail adjustment at almost unchanged bearing changed speed materially
- favorable raw test reached about 8.8–8.9 kt

Do not invent a fake precise polar curve.
Keep its angle-performance parameters configurable.

### Pembroke
No direct test available.

Use a PROXY:
- base it on Been's general behavior
- peak normalized speed = 9.0 kt
- same preference for a slight favorable angle
- BETTER than Been as wind becomes more frontal/unfavorable
- reduce Been's frontal/headwind penalty
- keep this proxy configurable and internal

Do not present the Pembroke curve as measured/confirmed.

---

## 8. Sail Handling

### General Basic Sailing rules
Use the user's Basic Sailing guide as tactical logic:

- TRIM = catch wind / strongest useful force
- SHIVER = mostly avoid wind / neutralize a sail
- BACK/ABACK = can create reverse force
- sails not intended to catch wind should be kept approximately neutral/parallel to wind
- asymmetric sail force can create yaw and help turn

The example guide speeds are illustrative ONLY. Do not use them as universal calibration.

### Hoy
- has movable spanker
- use spanker for turn/tack assistance
- do not invent a numeric speed or turn bonus for it

### Been
- has movable spanker
- has movable topsail
- topsail can push ship backward against bad wind
- SHIVER topsail when trimming would create backward/near-zero progress
- use spanker for maneuvering/yaw assistance
- once new heading is established, return to best forward configuration

### Pembroke
Correction:
- 3 controllable mast groups: Fore, Main, Mizzen
- spanker exists but is NOT movable
- NEVER tell player to trim/shiver Pembroke spanker
- use asymmetric Fore/Main/Mizzen states to help turn/tack
- restore best propulsion configuration after maneuver

---

## 9. Tacking
Tacking must be part of pathfinding, not an after-the-fact visual decoration.

When direct heading is materially unfavorable:
1. test safe alternate headings on both sides
2. calculate wind-relative performance
3. ensure progress toward next waypoint/TP/port
4. respect obstacle clearance
5. select tack sequence with best estimated time
6. re-evaluate as wind rotates
7. add tack points to route
8. show ship-specific sail instructions at tack points

Do not create pointless zig-zags.

---

## 10. Diplomacy / Enemy Warnings
Ownership must be stored PER PORT, not just per region, because some regions are mixed.

Current ownership reference has 8 nation groups:
- Royal Navy
- Marine Impériale
- United States Navy
- Austria
- Armada Española
- Portugal
- Imperial Andouran Navy
- Pirate Republic

Use the user's ownership/flag world image to populate `port -> nation`.

Do not guess any unreadable flag/label.

If mixed:
`region_control = MIXED`
and keep port ownership authoritative.

Add:
- Player Nation
- Enemy / diplomacy relationships

Example:
`French ↔ British = At War`

Warn if:
- origin is enemy-controlled
- destination is enemy-controlled
- selected route crosses controlled territory/ports tagged as enemy

For now:
- WARN
- do not block route

---

## 11. Warnings
Normal UI should stay quiet.

Only show actionable warnings for:
1. route is materially unoptimal
2. unfavorable wind materially slows route / tack required
3. enemy territory

No "everything is good" banners.

---

## 12. Player UI Data
Do NOT expose raw internal data-quality labels in the normal UI such as:
- CONFIRMED
- ESTIMATED
- CONFIRMED_FROM_SCREENSHOT
- CONFIRMED_FROM_VIDEO
- DERIVED
- PROXY
- HEURISTIC

Keep them in debug/data tables only.

Normal route result should show:
- Origin → Destination
- Cargo
- Ship
- Cargo units
- Purchase cost
- Expected sale
- Expected profit
- Applied taxes
- Route distance
- ETA
- Regions / TP transitions
- wind at departure + expected rotation
- tack points
- sail instructions

---

## 13. Preserve Existing Trade Data Rules
- Use recorded game destination sell values whenever available.
- Use inferred formula only if a sell value is genuinely missing and keep that status internal.
- Cargo Distance is for game trade economics.
- Cargo Distance is NOT safe sailing-route distance.
- Do not model depreciation.
- Keep +1 carried cargo item rule.
- Preserve existing 58-port tax/economy data.

---

## 14. Important Existing Geometry Correction
Deadman's Murcia is an ACTIVE current port in East Somerset.

If the existing geometry pack still lacks its true port node:
- do not guess coordinates
- flag it for geometry confirmation
- economics may work before geometry is confirmed
- do not generate a fake route endpoint

---

## 15. Test Cases After Update
Test at least:

1. Hoy + favorable wind, same-region route
2. Hoy + poor wind, tack required
3. Been + bad topsail wind where shiver is recommended
4. Been route where a slightly longer wind-favored path beats shortest path
5. Pembroke using proxy model and Fore/Main/Mizzen turn logic
6. Long cross-region route where wind rotates significantly during voyage
7. Manual tax override
8. Map-based start/destination selection
9. Actual-current-position navigation start outside origin harbor
10. Enemy-controlled start/destination/route warning
11. Route with no warning conditions
12. Verify storms/slow-wind intensity never enter optimization

At the end, report:
- what was implemented
- what remains heuristic/proxy
- any ownership entries that could not be confidently read
- whether Deadman's Murcia geometry is present
- whether map/path scale is calibrated for precise knot-based ETA
