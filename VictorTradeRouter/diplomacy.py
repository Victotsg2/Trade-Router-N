from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA = Path(__file__).with_name("data")
OWNERSHIP_FILE = DATA / "port_ownership.json"
SETTINGS_FILE = DATA / "v2_settings.json"
NATIONS = [
    "Royal Navy",
    "Marine Impériale",
    "United States Navy",
    "Austria",
    "Armada Española",
    "Portugal",
    "Imperial Andouran Navy",
    "Pirate Republic",
]


def load_ownership() -> dict[str, Any]:
    return json.loads(OWNERSHIP_FILE.read_text(encoding="utf-8"))


def save_ownership(data: dict[str, Any]) -> None:
    ports = data.get("ports", {})
    invalid = sorted({nation for nation in ports.values() if nation not in NATIONS})
    if invalid:
        raise ValueError(f"Unknown nation label(s): {', '.join(invalid)}")
    OWNERSHIP_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_settings() -> dict[str, Any]:
    return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))


def save_settings(data: dict[str, Any]) -> None:
    scale = data.get("pixels_per_nautical_mile")
    if scale is not None and float(scale) <= 0:
        raise ValueError("Pixels per nautical mile must be positive or left blank.")
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def region_controls(economy: dict[str, Any], ownership: dict[str, Any]) -> dict[str, str]:
    owners = ownership.get("ports", {})
    grouped: dict[str, set[str]] = {}
    for port in economy["ports"]:
        nation = owners.get(port["display_name"])
        if nation:
            grouped.setdefault(port["region"], set()).add(nation)
    controls = {}
    for region in {port["region"] for port in economy["ports"]}:
        nations = grouped.get(region, set())
        controls[region] = next(iter(nations)) if len(nations) == 1 else ("MIXED" if len(nations) > 1 else "UNKNOWN")
    return controls


def diplomacy_warnings(
    economy: dict[str, Any],
    ownership: dict[str, Any],
    origin_port: str,
    destination_port: str,
    region_sequence: list[str],
    enemy_nations: list[str],
) -> list[str]:
    enemies = set(enemy_nations)
    if not enemies:
        return []
    owner_by_port = ownership.get("ports", {})
    warnings = []
    origin_owner = owner_by_port.get(origin_port)
    destination_owner = owner_by_port.get(destination_port)
    if origin_owner in enemies:
        warnings.append(f"Origin {origin_port} is controlled by enemy nation {origin_owner}.")
    if destination_owner in enemies:
        warnings.append(f"Destination {destination_port} is controlled by enemy nation {destination_owner}.")
    controls = region_controls(economy, ownership)
    for region in dict.fromkeys(region_sequence):
        owner = controls.get(region)
        if owner in enemies:
            warning = f"Route crosses {region}, currently mapped to enemy nation {owner}."
            if warning not in warnings:
                warnings.append(warning)
    return warnings
