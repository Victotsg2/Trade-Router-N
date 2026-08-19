# Victor's Trade Router v5.4 — Wind-Angle Correction

## Confirmed behavior

The Hoy performs best with wind on either side of the ship, approximately 90° from the wind-toward direction. Sailing directly with the wind or directly against it is poor.

The Been and Pembroke perform best at a slight oblique wind angle rather than directly aligned. Backed headings are unfavorable. Their existing uncalibrated values are preserved: Been remains partial empirical plus heuristic, and Pembroke remains a Been-based proxy.

## Model correction

- Hoy relative wind angle 90° or 270°: best modeled speed, 9.0 kt normalized
- Hoy relative wind angle 0° or 180°: poor modeled speed, 0.5 kt boundary
- Existing intermediate curve values are interpreted as deviation away from either beam-reach heading.
- Been and Pembroke use a provisional 15° oblique optimum; direct alignment is slightly slower and the backed sector is poor.
- No new Been/Pembroke speeds were inferred from the directional sketch.
- Home recommendations and detailed route planning use the corrected shared Hoy calculation.
- When map scale is unavailable, all bounded safe TP corridors are now compared with a static departure-wind effort score instead of forcing the shortest geometry-only corridor.

The original imported handoff files remain unchanged for audit history; their former parallel/downwind Hoy assumption is superseded by the user's confirmed beam-reach diagram.
