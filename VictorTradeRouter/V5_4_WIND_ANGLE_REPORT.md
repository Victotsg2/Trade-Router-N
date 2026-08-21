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
- When map scale is unavailable, routing prefers the fewest valid TP transfers and then compares wind/tacking among those corridors. Raw pixels from separate regional screenshots are not treated as verified cross-region travel time.
- The Princeton → Cumberland Hill regression now uses the direct Lebarde → New Catalina TP instead of detouring through West Somerset.
- Lebarde routes to Jones' Outpost use that same direct one-TP corridor.
- The unified route image overlays each complete paired TP polygon transparently and uses short direction arrows at the selected matching positions. It draws no dashed cross-map line or `TP IN`/`TP OUT` label.
- Paired teleport sampling now prefers the safe polygon center rather than the maximum-clearance edge. The Lebarde → New Catalina transition uses `(u=0.5, v=0.5)` in both boxes, away from the neighboring Griffard's Rock TP.
- Corrected reversed Lebarde side assignments: `LEB-TP06` (right vertical) now pairs with `NCA-TP01`, and `LEB-TP02` (left vertical) now pairs with `BTS-TP04`. No TP polygon was moved or resized.

The original imported handoff files remain unchanged for audit history; their former parallel/downwind Hoy assumption is superseded by the user's confirmed beam-reach diagram.
