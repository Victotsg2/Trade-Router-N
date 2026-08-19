# Victor's Trade Router v5.1 — Short-Path Fix

## Cause

Windows Explorer silently skipped long filenames under `data/source_import` when the ZIP was extracted inside an already-long Codex output path. The missing v2 wind handoff then caused Home recommendation generation to fail.

## Fix

- Added the active wind handoff at `data/wind_v2.json`.
- Updated the loader to prefer the short path while retaining the original source-import path as a fallback.
- Flattened the release ZIP so `VictorTradeRouter` is its only top-level folder.
- Restored Home and Route Planner to centered horizontal navigation below the header, with a small vertical offset and no left sidebar.
- Preserved all geometry, trading, wind, and tacking behavior.

## Recommended extraction

Extract the new ZIP directly to `C:\`. The app should then be located at `C:\VictorTradeRouter`.
