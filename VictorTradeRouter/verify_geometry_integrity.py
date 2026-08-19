from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parent
BASELINE = ROOT / "GEOMETRY_SHA256_BASELINE.json"
REPORT = ROOT / "GEOMETRY_INTEGRITY_REPORT.json"


def main() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8-sig"))
    changed = []
    missing = []
    for item in baseline:
        path = ROOT / item["path"]
        if not path.is_file():
            missing.append(item["path"])
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item["sha256"]:
            changed.append(
                {
                    "path": item["path"],
                    "expected_sha256": item["sha256"],
                    "actual_sha256": digest,
                }
            )
    report = {
        "status": "PASS" if not changed and not missing else "FAIL",
        "baseline_file_count": len(baseline),
        "unchanged_file_count": len(baseline) - len(changed) - len(missing),
        "changed_files": changed,
        "missing_files": missing,
        "scope": "stage1_data plus tp_transforms.json and world_alignment.json",
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
