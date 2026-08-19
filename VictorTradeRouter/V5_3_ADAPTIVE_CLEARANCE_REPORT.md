# Victor's Trade Router v5.3 — Adaptive Clearance Report

## Outcome

**PASS** — the fixed clearance rule was replaced with an adaptive policy without changing the locked Stage 1 maps or geometry assets.

## Implemented policy

- Preferred open-water clearance: **14 px**
- Hard narrow-passage/core clearance: **10 px**
- Port approach clearance: **5 px**
- TP approach clearance: **8 px**
- Raw obstacle mask: **absolute no-cross boundary**

The route search applies a graduated cost below 14 px. This favors ordinary open water but allows a shorter 10 px channel when the alternative is an unnecessary detour. Exact reviewed endpoint pixels retain the existing local endpoint exception only until they connect to their applicable approach tier.

## Verification

- Unit/regression tests: **43/43 passed**
- Additional port/TP endpoint sweep: **127/127 routes passed**
- Lowest core-route clearance observed: **10.0 px**
- Raw-obstacle collisions observed: **0**
- Protected Stage 1 geometry integrity: **118/118 files unchanged**
- Vysarian Isles Saint-Pierre TP → Gyldenvale: **743.6 px**, using the interior passage; old fixed-clearance result was approximately **848 px**
- Tacking remains enabled and was rechecked under an actually unfavorable departure wind after the shorter route changed the test leg's bearing.

No world map, raw obstacle mask, navigation mask, ownership mask, TP polygon/pair, or coordinate transform was rebuilt, rescaled, or replaced.
