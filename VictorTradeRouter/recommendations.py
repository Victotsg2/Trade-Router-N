from __future__ import annotations

import math
from typing import Any

from economy import calculate_trade
from routing import load_regions, ports as geometry_ports, regional_to_world
from wind import heading_bearing, modeled_speed_knots, wind_after_setup


def _world_port_points(economy: dict[str, Any]) -> dict[str, tuple[int, int]]:
    geometry = {
        (region["region_id"], port["port_id"]): port
        for region in load_regions()
        for port in geometry_ports(region["region_id"])
    }
    result: dict[str, tuple[int, int]] = {}
    for port in economy["ports"]:
        record = geometry.get((port["region_id"], port.get("geometry_port_id")))
        if record is None:
            continue
        result[port["display_name"]] = regional_to_world(
            port["region_id"],
            (int(record["pixel_x"]), int(record["pixel_y"])),
        )
    return result


def _wind_rating(speed_knots: float, deviation_deg: float) -> tuple[str, int, str]:
    if speed_knots >= 6.5 and deviation_deg <= 45:
        return "Favorable", 1, "#72c58e"
    if speed_knots >= 3.5:
        return "Manageable", 2, "#d5bd72"
    if speed_knots >= 1.5:
        return "Demanding", 3, "#dc8b55"
    return "Difficult", 4, "#bd5d55"


def generate_trade_recommendations(
    economy: dict[str, Any],
    origin: str,
    ship: str,
    wind_toward_deg: float,
    *,
    limit: int = 18,
) -> list[dict[str, Any]]:
    """Rank profitable destinations with a deliberately rough voyage-effort estimate.

    This fast Home-screen estimate does not run the obstacle pathfinder. It uses
    recorded Cargo Distance when available (otherwise direct unified-map
    distance), general voyage bearing, and the current direction-only ship
    model. The entered wind is the condition while charting; ranking uses the
    wind expected 10 degrees later once sails and course are set. Selecting a
    result still runs the full route planner.
    """
    points = _world_port_points(economy)
    if origin not in points:
        return []
    origin_point = points[origin]
    wind_when_charted = float(wind_toward_deg) % 360.0
    effective_departure_wind = wind_after_setup(wind_when_charted)
    port_rows = {row["display_name"]: row for row in economy["ports"]}
    rows: list[dict[str, Any]] = []
    for destination, destination_point in points.items():
        if destination == origin or not port_rows[destination].get("route_eligible"):
            continue
        trade = calculate_trade(economy, origin, destination, ship)
        profit = trade.get("total_profit_gbp")
        if profit is None or profit <= 0:
            continue
        bearing = heading_bearing(origin_point, destination_point)
        model = modeled_speed_knots(ship, bearing, effective_departure_wind)
        speed = float(model["speed_knots"])
        cargo_distance = trade.get("cargo_distance_m")
        if cargo_distance is None:
            distance_proxy = math.hypot(
                destination_point[0] - origin_point[0],
                destination_point[1] - origin_point[1],
            )
            distance_source = "Unified-map distance proxy"
        else:
            distance_proxy = float(cargo_distance)
            distance_source = "Recorded game Cargo Distance"
        effort = distance_proxy / max(speed, 0.5)
        wind_label, wind_burden, wind_color = _wind_rating(
            speed, float(model["relative_wind_deviation_deg"])
        )
        rows.append({
            "origin": origin,
            "destination": destination,
            "destination_region": port_rows[destination]["region"],
            "ship": ship,
            "wind_toward_deg": wind_when_charted,
            "wind_when_charted_deg": wind_when_charted,
            "effective_departure_wind_deg": effective_departure_wind,
            "cargo": trade["cargo"],
            "cargo_units": trade["total_units"],
            "total_profit_gbp": int(profit),
            "profit_per_unit_gbp": int(trade["profit_per_unit_gbp"]),
            "purchase_per_unit_gbp": int(trade["purchase_total_per_unit_gbp"]),
            "net_sale_per_unit_gbp": int(trade["net_sale_per_unit_gbp"]),
            "cargo_distance_m": cargo_distance,
            "distance_source": distance_source,
            "general_bearing_deg": round(bearing, 1),
            "modeled_departure_speed_knots": round(speed, 2),
            "relative_wind_deviation_deg": round(float(model["relative_wind_deviation_deg"]), 1),
            "wind_rating": wind_label,
            "wind_burden": wind_burden,
            "wind_color": wind_color,
            "effort": effort,
            "raw_rank_score": float(profit) / max(effort, 1.0),
        })
    if not rows:
        return []
    effort_values = sorted(row["effort"] for row in rows)
    q1 = effort_values[len(effort_values) // 4]
    q2 = effort_values[len(effort_values) // 2]
    q3 = effort_values[(len(effort_values) * 3) // 4]
    max_score = max(row["raw_rank_score"] for row in rows) or 1.0
    for row in rows:
        if row["effort"] <= q1:
            row["time_estimate"] = "Short"
        elif row["effort"] <= q2:
            row["time_estimate"] = "Moderate"
        elif row["effort"] <= q3:
            row["time_estimate"] = "Long"
        else:
            row["time_estimate"] = "Very long"
        row["trade_score"] = round(row["raw_rank_score"] / max_score * 100.0, 1)
    rows.sort(key=lambda row: (row["raw_rank_score"], row["total_profit_gbp"]), reverse=True)
    for index, row in enumerate(rows[:limit], start=1):
        row["rank"] = index
    return rows[:limit]
