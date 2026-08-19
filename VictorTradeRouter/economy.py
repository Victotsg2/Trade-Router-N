from __future__ import annotations

import json
import math
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


ECONOMY_DATA = Path(__file__).with_name("data") / "economy_data.json"


def load_economy(path: Path = ECONOMY_DATA) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_economy(data: dict[str, Any], path: Path = ECONOMY_DATA) -> None:
    errors = validate_economy(data)
    blocking = [row for row in errors if row["severity"] == "ERROR"]
    if blocking:
        raise ValueError("; ".join(row["message"] for row in blocking))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = value.replace("’", "'").replace("‘", "'")
    return re.sub(r"[^a-z0-9]", "", value.lower())


def canonical_port_name(name: str, data: dict[str, Any]) -> str:
    lookup = {normalized(row["display_name"]): row["display_name"] for row in data["ports"]}
    for alias, canonical in data.get("aliases", {}).items():
        lookup[normalized(alias)] = canonical
    return lookup.get(normalized(name), name)


def money_round(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def port_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["display_name"]: row for row in data["ports"]}


def purchase_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["origin_port"]: row for row in data["cargo_purchase_data"]}


def sale_index(data: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (row["origin_port"], row["destination_port"]): row
        for row in data["destination_sales"]
    }


def ship_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["ship"]: row for row in data["ships"]}


def calculate_trade(
    data: dict[str, Any],
    origin_port: str,
    destination_port: str,
    ship_name: str,
    origin_export_tax_percent: float | None = None,
    destination_import_tax_percent: float | None = None,
) -> dict[str, Any]:
    origin_port = canonical_port_name(origin_port, data)
    destination_port = canonical_port_name(destination_port, data)
    if origin_port == destination_port:
        raise ValueError("Origin and destination must be different ports.")

    ports = port_index(data)
    purchases = purchase_index(data)
    ships = ship_index(data)
    if origin_port not in purchases:
        raise ValueError(f"No purchase data for {origin_port}.")
    if destination_port not in ports:
        raise ValueError(f"Unknown destination port: {destination_port}.")
    if ship_name not in ships:
        raise ValueError(f"Unknown ship: {ship_name}.")

    purchase = purchases[origin_port]
    origin = ports[origin_port]
    destination = ports[destination_port]
    ship = ships[ship_name]
    observation = sale_index(data).get((origin_port, destination_port))

    base_price = float(purchase["base_price_gbp"])
    weight = float(purchase["weight_tons"])
    export_tax_percent = (
        float(origin["export_tax_percent"])
        if origin_export_tax_percent is None
        else float(origin_export_tax_percent)
    )
    import_tax_percent = (
        float(destination["import_tax_percent"])
        if destination_import_tax_percent is None
        else float(destination_import_tax_percent)
    )
    if not 0 <= export_tax_percent <= 100 or not 0 <= import_tax_percent <= 100:
        raise ValueError("Tax percentages must be between 0 and 100.")
    purchase_total = money_round(base_price * (1 + export_tax_percent / 100))

    if observation is not None and observation.get("displayed_sell_value_gbp") is not None:
        cargo_distance = observation.get("cargo_distance_m")
        gross_sale = int(observation["displayed_sell_value_gbp"])
        distance_status = observation.get("distance_status", "NEEDS_REVIEW")
        value_status = observation.get("value_status", "NEEDS_REVIEW")
        sale_source = observation.get("source", observation.get("source_recording", "recorded"))
    elif observation is not None and observation.get("cargo_distance_m") is not None:
        cargo_distance = float(observation["cargo_distance_m"])
        gross_sale = money_round(base_price * (1.25 + cargo_distance / 4000))
        distance_status = observation.get("distance_status", "NEEDS_REVIEW")
        value_status = "DERIVED"
        sale_source = "inferred_formula_for_missing_value"
    else:
        cargo_distance = None
        gross_sale = None
        distance_status = "MISSING"
        value_status = "MISSING"
        sale_source = "missing_recorded_distance_and_value"

    hold_units = math.floor(float(ship["cargo_capacity_tons"]) / weight)
    total_units = hold_units + int(data["cargo_capacity_rule"]["carried_extra_units"])
    result: dict[str, Any] = {
        "origin_port": origin_port,
        "destination_port": destination_port,
        "cargo": purchase["cargo"],
        "ship": ship_name,
        "base_price_gbp": base_price,
        "base_price_status": purchase["base_price_status"],
        "weight_tons": weight,
        "weight_status": purchase["weight_status"],
        "origin_export_tax_percent": export_tax_percent,
        "destination_import_tax_percent": import_tax_percent,
        "tax_mode": "Default" if origin_export_tax_percent is None and destination_import_tax_percent is None else "Manual",
        "purchase_total_per_unit_gbp": purchase_total,
        "cargo_distance_m": cargo_distance,
        "cargo_distance_status": distance_status,
        "gross_sell_value_per_unit_gbp": gross_sale,
        "gross_sell_value_status": value_status,
        "sale_source": sale_source,
        "ship_hold_units": hold_units,
        "player_extra_units": int(data["cargo_capacity_rule"]["carried_extra_units"]),
        "total_units": total_units,
        "generated_route_distance_px": None,
        "generated_route_distance_status": "CALCULATED_SEPARATELY_BY_PATHFINDER",
    }
    if gross_sale is None:
        result.update(
            {
                "destination_import_tax_per_unit_gbp": None,
                "net_sale_per_unit_gbp": None,
                "profit_per_unit_gbp": None,
                "total_purchase_cost_gbp": None,
                "total_net_revenue_gbp": None,
                "total_profit_gbp": None,
            }
        )
        return result

    import_tax = money_round(gross_sale * import_tax_percent / 100)
    net_sale = gross_sale - import_tax
    profit_per_unit = net_sale - purchase_total
    result.update(
        {
            "destination_import_tax_per_unit_gbp": import_tax,
            "net_sale_per_unit_gbp": net_sale,
            "profit_per_unit_gbp": profit_per_unit,
            "total_purchase_cost_gbp": purchase_total * total_units,
            "total_net_revenue_gbp": net_sale * total_units,
            "total_profit_gbp": profit_per_unit * total_units,
        }
    )
    return result


def validate_economy(data: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def add(severity: str, code: str, message: str) -> None:
        findings.append({"severity": severity, "code": code, "message": message})

    ports = data.get("ports", [])
    names = [row.get("display_name") for row in ports]
    if len(ports) != 58:
        add("ERROR", "PORT_COUNT", f"Expected 58 economy ports; found {len(ports)}.")
    if len(set(names)) != len(names):
        add("ERROR", "DUPLICATE_PORT", "Economy port names are not unique.")
    known = set(names)
    route_eligible = [row for row in ports if row.get("route_eligible")]
    if len(route_eligible) != 57:
        add("ERROR", "ROUTE_PORT_COUNT", f"Expected 57 coordinate-backed ports; found {len(route_eligible)}.")
    deadman = next((row for row in ports if row.get("display_name") == "Deadman's Murcia"), None)
    if deadman is None:
        add("ERROR", "DEADMAN_MISSING", "Deadman's Murcia is missing from the economy port list.")
    elif deadman.get("route_eligible"):
        add("ERROR", "DEADMAN_COORDINATE", "Deadman's Murcia cannot be route-eligible without a confirmed coordinate.")

    purchases = data.get("cargo_purchase_data", [])
    if len(purchases) != 58:
        add("ERROR", "PURCHASE_COUNT", f"Expected 58 cargo purchase rows; found {len(purchases)}.")
    for row in purchases:
        if row.get("origin_port") not in known:
            add("ERROR", "PURCHASE_UNKNOWN_PORT", f"Unknown purchase origin: {row.get('origin_port')}.")
        for field in ("base_price_status", "weight_status"):
            if row.get(field) not in {"CONFIRMED", "ESTIMATED"}:
                add("ERROR", "PURCHASE_STATUS", f"Invalid {field} for {row.get('origin_port')}.")

    seen_pairs: set[tuple[str, str]] = set()
    for row in data.get("destination_sales", []):
        pair = (row.get("origin_port"), row.get("destination_port"))
        if pair in seen_pairs:
            add("ERROR", "DUPLICATE_SALE_PAIR", f"Duplicate destination row: {pair[0]} -> {pair[1]}.")
        seen_pairs.add(pair)
        if pair[0] not in known or pair[1] not in known:
            add("ERROR", "SALE_UNKNOWN_PORT", f"Unknown destination-row port in {pair[0]} -> {pair[1]}.")
        if pair[0] == pair[1]:
            add("ERROR", "SELF_SALE", f"Self-destination row found for {pair[0]}.")

    if len(data.get("ships", [])) != 3:
        add("ERROR", "SHIP_COUNT", f"Expected 3 ships; found {len(data.get('ships', []))}.")
    if not findings:
        add("PASS", "VALID", "Economy data passed structural validation.")
    return findings
