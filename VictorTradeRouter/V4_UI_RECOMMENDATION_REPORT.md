# Windward Trade Office v4 — UI and Recommendation Update

## Result: COMPLETE

This update changes the interface and adds a recommendation layer without altering the locked world geometry.

## Implemented

- Winward Project-inspired maritime theme using the supplied reference artwork, offline Georgia-style headings, restrained gold/navy controls, and less technical player-facing copy.
- Minimal Home trade board with origin port, ship, and departure wind heading.
- Up to 18 profitable voyage suggestions ranked by total profit versus estimated voyage effort.
- Hover details for destination, region, cargo, total/per-unit profit, time category, wind difficulty, modeled departure speed, deviation, distance basis, and general bearing.
- Selecting a voyage transfers origin, destination, ship, default taxes, origin-port navigation start, and world wind heading into Route Planner.
- Route settings collapse automatically after successful generation.
- Origin → destination, cargo, units, profit per unit, and total profit stay visible.
- Route image contains the map only; its report header and numbered regional-leg circles were removed.
- Tack markers are orange directional arrows aligned with the outbound tack segment.
- Sail instructions were rewritten as direct action orders tied to the orange arrow and white route segment.
- Removed the redundant “Unfavorable wind makes one or more tactical tacks worthwhile.” warning.
- Data & Debug and Data Status are combined into a collapsed Data, Debug & Status panel at the bottom.

## Estimate policy

Home does not claim a clock ETA. It uses Short, Moderate, Long, or Very long plus Favorable, Manageable, Demanding, or Difficult wind. Recorded game Cargo Distance is used only as the quick Home ranking distance basis and remains separate from generated sailing-route distance. Selecting a suggestion runs the full obstacle-safe pathfinder.

## Verification

- Recommendation hover and selection tested in the live interface.
- Selected origin, destination, ship, and wind transferred correctly.
- Successful route generation collapsed the settings panel.
- Cargo/profit summary and route map remained visible.
- Combined bottom data/status panel rendered all expected sections.
- Live browser and server logs contained no errors or warnings after correction.
- V4 automated tests cover ranking, wind responsiveness, economy consistency, map-only output dimensions, directional tack arrows, warning removal, sail-order clarity, and interface structure.
- Protected geometry remains subject to the original 118-file SHA-256 integrity baseline.
