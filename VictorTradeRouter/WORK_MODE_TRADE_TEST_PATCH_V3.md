# WORK MODE PATCH v3 — Full Trade-Test Findings + Blocked Route Fixes

Update the EXISTING Naval Trade / 17-region Route Tester incrementally.

Use:
- `naval_route_trade_test_patch_v3.json`
- the existing v2 handoff already merged into the project
- the compressed full-route recording `Hoytrade (1).mp4` if available in the Work-mode conversation

Do **not** rebuild, restitch, rescale, or replace the current world geometry.

## A. Fix false "location/path blocked" failures first

The user has encountered valid routes/starting positions being rejected as blocked, including a Louisbourg -> Griffard's Rock attempt.

Perform a systematic geometry/pathfinder audit rather than fixing only that one route.

### 1. Port points vs navigation anchors
A port's label/marker coordinate is not guaranteed to be valid open water.

For every port store two concepts:

- `port_semantic_point`
  - UI marker
  - cargo/trade origin identity
- `port_navigation_anchor`
  - nearest valid harbor/open-water point that can actually connect to the pathfinder

Never require a route to begin from a land/dock pixel simply because that is where the port icon is located.

### 2. Local safe snapping
When a valid port/current-position endpoint is inside:
- land,
- obstacle,
- or only the derived clearance buffer,

attempt a local safe snap to the nearest **reachable** navigable water.

Important:
- never snap across land
- never teleport through an island/peninsula
- verify local water connectivity
- keep the snapped distance small and auditable

### 3. Harbor exceptions
Use the already-approved port arrival/departure exception inside a small harbor connection zone.
After leaving that zone, restore full hard-clearance behavior.

Do not globally lower obstacle clearance to solve a harbor problem.

### 4. TP zones
A TP is a zone, not one center point.

When routing to a TP:
- search multiple reachable points inside its valid rectangle/polygon
- choose a safe reachable portal point
- preserve relative entry/exit mapping
- validate the mapped exit position is open/reachable water

### 5. Derived buffer vs raw obstacle mask
The raw obstacle mask is authoritative.

Check whether the hard-clearance buffer accidentally closes:
- harbor mouths
- narrow legitimate channels
- TP approaches

Fix these with explicit harbor/TP transition handling rather than weakening world safety.

### 6. Coordinate transforms
Audit region/world transforms for:
- start anchors
- destination anchors
- TP entries/exits
- current-position clicks

A transformed point must not land on a different shoreline/obstacle because of stitching offsets.

### 7. Fallback search
If one local TP corridor fails:
- try other points in that TP zone
- then try other valid TP corridors
- only return "blocked" after all legitimate candidates fail

### 8. Better diagnostics
Replace generic `Path blocked` debugging with specific internal causes:

- START_ANCHOR_INVALID
- DESTINATION_ANCHOR_INVALID
- START_TO_WATER_UNREACHABLE
- LOCAL_LEG_BLOCKED
- TP_ENTRY_UNREACHABLE
- TP_EXIT_INVALID
- REGION_TRANSFORM_ERROR
- NO_VALID_TP_CORRIDOR
- CURRENT_POSITION_INVALID

Keep raw diagnostics in debug output.
The normal player UI should show a short understandable message.

---

## B. Update wind optimization using the 49:48 Hoy trade test

Validation run:
- Ship: Hoy
- Origin: Louisbourg
- Destination: Port Royal
- Duration: about 49:49
- Wind strength averaged around 23 kt, but **IGNORE WIND STRENGTH**
- Only wind direction and its clockwise 6°/minute rotation belong in the model

The user's key observation:
- initial wind leaving Louisbourg was poor for the Hoy
- wind improved by the first TP
- the generated route appeared to chase an early favorable direction too aggressively
- sailing more directly toward Kingston and tacking later may have been faster overall

### Required optimizer change
Do not optimize each local segment greedily for the best current wind.

Generate and fully simulate several safe strategies:

1. Shortest safe route
2. Immediate wind-favored route
3. Direct-progress / delayed-tack route
4. Alternative TP corridors
5. Delayed-tack variants when the wind is expected to rotate into a better position

For every candidate:
- start with departure wind
- advance wind at 6° clockwise per elapsed minute
- recalculate relative wind and modeled speed on every segment
- include tack legs
- simulate through the final destination
- compare **total ETA**

Choose the route with the lowest predicted arrival time.

A locally slower leg can be correct if it:
- makes more direct progress,
- avoids unnecessary distance,
- and reaches a better wind phase later.

Do not choose a large detour merely because it immediately produces higher speed.

---

## C. Delayed tacking behavior

The pathfinder should be allowed to intentionally:

- continue making useful direct progress in mediocre wind,
- wait for the global wind to rotate,
- tack later when the timing becomes beneficial.

For long routes, this must be evaluated automatically.

If delayed tacking wins, show:
- where the tack is expected,
- approximate elapsed time at tack,
- expected wind direction at that time,
- ship-specific sail instruction.

Do not create decorative tacks.

---

## D. Hoy model remains direction-only

Continue using the existing preliminary Hoy curve normalized to 9.0 kt at the best angle.

The 49-minute test supports the existing direction-only concept:
- bad relative angle -> low progress
- wind rotates -> speed improves
- later favorable phases -> high speed

Do not derive a wind-strength multiplier from the ~23 kt shown during the test.

---

## E. Regression tests

Run these before calling the patch complete:

### Geometry/start tests
1. Every current port can resolve to a valid water navigation anchor.
2. Every current port can be used as a destination without failing because its marker is on shore/dock.
3. Current-position map clicks just offshore route correctly.
4. Port/current-position points close to shore snap safely instead of falsely failing.
5. Every TP pair has reachable entry/exit water points.
6. All region nodes remain connected according to the known TP network.

### Specific bug tests
7. Louisbourg -> Griffard's Rock.
   - Must not return a generic blocked message.
   - If it truly fails, report the exact local leg and reason.
   - Try alternate TP points/corridors automatically.

### Wind route tests
8. Louisbourg -> Port Royal with Hoy:
   compare shortest-safe, immediate-wind, direct-progress/delayed-tack, and alternate corridor candidates.
9. Verify that a longer wind-favored route is chosen ONLY if total simulated ETA is lower.
10. Verify wind advances 6°/minute throughout the simulation.
11. Verify the optimizer never uses random wind-speed intensity.

---

## F. UI changes from this validation run

When a non-shortest route wins, explain why in one concise line, for example:

`Wind-favored route selected — estimated 2m 14s faster.`

When delayed tacking wins:

`Direct progress recommended. Tack after ~12 min as wind rotates.`

Only show `PATH BLOCKED` after:
- endpoint anchor recovery,
- local safe snapping,
- TP-zone point search,
- and alternate corridor search
have all failed.

If a route is possible but wind is poor, show `UNFAVORABLE WIND`, not `PATH BLOCKED`.

---

## G. Preserve all existing v2 behavior

Keep:
- unified 17-region geometry
- raw obstacle masks
- hard-clearance safety
- valid TP mapping
- merged trade + route workflow
- Default/Manual taxes
- map + dropdown selection
- actual-current-position option
- HUD-matching wind input
- Hoy/Been/Pembroke sail logic
- tacking
- diplomacy warnings
- storm/slow-wind disclaimer
- internal data-quality metadata hidden from normal UI

At completion, report:
1. root cause(s) of false blocked-start/path failures,
2. which anchors/TPs were repaired,
3. Louisbourg -> Griffard's regression result,
4. Louisbourg -> Port Royal candidate ETAs,
5. whether delayed tacking changes the selected Hoy route,
6. any remaining geometry/path-scale/wind calibration limitations.
