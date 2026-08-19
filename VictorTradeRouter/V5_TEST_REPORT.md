# Victor's Trade Router v5 — Test Report

Date: 2026-08-18

## Automated validation

- Full Python regression suite: **40/40 passed**
- Economy validation: **58 ports** and **3,240 destination rows** passed
- Protected geometry verification: **118/118 files unchanged**
- Seven representative local/inter-region/TP route smoke tests passed
- A calibrated Belle Isles test route produced a tack and sail instructions, confirming tacking remains active
- The short-path wind handoff exists and loads independently of the long source-import path
- Removed-copy tests confirm the requested explanatory, unavailable-Time, and unfavorable-wind messages are absent

## Browser acceptance

- The header spans the main content width while remaining a shallow 205–250 px banner
- Branding reads **Victor's Trade Router** with no subtitle
- Home and Route Planner are centered below the header without a sidebar
- Home displays **Trade Info**, **Recommended Routes**, and the octagonal eight-direction wind compass
- Recommendation hover copy is **Select Route**
- Route settings collapse after successful generation while cargo, profit, and the map remain visible
- With no verified scale, Voyage Details shows Route distance, Teleports, and Tacks but no Time metric
- The generated acceptance route displayed one tack and a TACK ORDERS section
- The shortened wind limitation notice is visible in a high-contrast gold/red panel
- No browser-console or Streamlit server error was observed during the acceptance pass

## Geometry scope

No Stage 1 map, mask, TP, transform, anchor, or routing-geometry asset was edited.
