# READY FOR STAGE 2

## Automated validation

| # | Check | Status | Detail |
|---:|---|---|---|
| 1 | All 17 regions exist | PASS | Found 17 regions |
| 2 | All 57 trade ports exist | PASS | Found 57 ports |
| 3 | Every port belongs to a valid region | PASS | All region references valid |
| 4 | Every port navigation anchor lies in navigable water | PASS | All anchors pass |
| 5 | No port anchor lies inside an obstacle | PASS | All anchors pass |
| 6 | Every TP has a valid destination | PASS | All destinations reference another valid region |
| 7 | Every TP polygon lies primarily in navigable space | PASS | Minimum navigable coverage 100.0% |
| 8 | Every paired_tp_id points to an existing TP | PASS | All non-null references exist |
| 9 | Reciprocal pairings have compatible region destinations | PASS | All resolved pairings are reciprocal and compatible |
| 10 | Neighbor-region obstacles excluded from owned geometry | PASS | All raw obstacles are subsets of explicit ownership masks; overlays visually reviewed |
| 11 | No source map is missing | PASS | All 17 standardized region folders are complete |
| 12 | Normalized coordinates are in [0,1] | PASS | All port and TP normalized coordinates pass |
| 13 | Intentional duplicate TP links are preserved | PASS | LEB→WSO 2; WSO→LEB 2 |
| 14 | Raw obstacle masks exist for every region | PASS | 17/17 present |
| 15 | Navigation masks exist for every region | PASS | 17/17 present |

All automated checks pass. Saint-Nicholas geometry, the duplicate Lebarde/West Somerset pairings, and the cleaned Santa Maria review presentation have been confirmed.

No Stage 2 routing, ship, wind, cargo, profit, timing, or route-line logic is included.
