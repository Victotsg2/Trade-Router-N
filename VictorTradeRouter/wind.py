from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from routing import (
    WorldRouteResult,
    _line,
    _region_context,
    _visible,
)


DATA_DIR = Path(__file__).with_name("data")
HANDOFF = DATA_DIR / "wind_v2.json"
LEGACY_HANDOFF = DATA_DIR / "source_import" / "naval_route_trade_wind_handoff_v2.json"
WIND_DISCLAIMER = (
    "Regional wind speed variations, very slow winds, gusts and storms are not accounted for "
    "and may change actual travel time."
)

# These values are deliberately isolated and labelled: Hoy is the supplied
# preliminary empirical curve; Been and Pembroke remain configurable heuristics.
BEEN_HEURISTIC_POINTS = ((0.0, 8.5), (15.0, 9.0), (45.0, 5.0), (75.0, 2.0), (90.0, 0.5), (180.0, 0.25))
PEMBROKE_PROXY_POINTS = ((0.0, 8.6), (15.0, 9.0), (45.0, 6.0), (75.0, 3.4), (90.0, 2.2), (180.0, 0.75))


@dataclass
class WindRoutePlan:
    route: WorldRouteResult
    ship: str
    wind_at_departure_deg: float
    eta_minutes: float | None
    eta_status: str
    relative_time_score: float
    original_shortest_distance_px: float
    selected_distance_px: float
    candidate_count: int
    route_choice: str
    segment_evaluations: list[dict[str, Any]]
    tack_points: list[dict[str, Any]]
    sail_instructions: list[dict[str, Any]]
    warnings: list[str]
    strategy: str
    selection_explanation: str | None
    eta_advantage_minutes: float | None
    candidate_summaries: list[dict[str, Any]]
    disclaimer: str = WIND_DISCLAIMER


@lru_cache(maxsize=1)
def load_handoff() -> dict[str, Any]:
    for candidate in (HANDOFF, LEGACY_HANDOFF):
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        "The wind-model data is missing. Re-extract the complete package to a short path "
        "such as C:\\VictorTradeRouter."
    )


def wind_toward_at_elapsed(wind_at_departure_deg: float, elapsed_minutes: float) -> float:
    return (float(wind_at_departure_deg) + 6.0 * float(elapsed_minutes)) % 360.0


def hud_arrow_to_world_wind(
    ship_bearing_deg: float,
    hud_arrow_relative_deg: float,
    *,
    arrow_represents_toward: bool = True,
) -> float:
    result = (float(ship_bearing_deg) + float(hud_arrow_relative_deg)) % 360.0
    return result if arrow_represents_toward else (result + 180.0) % 360.0


def heading_bearing(a: tuple[int, int], b: tuple[int, int]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    return math.degrees(math.atan2(dx, -dy)) % 360.0


def angular_difference(a: float, b: float) -> float:
    return abs((float(a) - float(b) + 180.0) % 360.0 - 180.0)


def _interpolate(points: tuple[tuple[float, float], ...], value: float) -> float:
    value = max(points[0][0], min(points[-1][0], float(value)))
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if value <= x1:
            fraction = 0.0 if x1 == x0 else (value - x0) / (x1 - x0)
            return y0 + fraction * (y1 - y0)
    return points[-1][1]


def modeled_speed_knots(ship: str, heading_deg: float, wind_toward_deg: float) -> dict[str, Any]:
    deviation = angular_difference(heading_deg, wind_toward_deg)
    handoff = load_handoff()["wind_model_v2"]
    if ship == "Hoy":
        points = tuple(
            (float(row["deviation_deg"]), float(row["speed_knots"]))
            for row in handoff["hoy"]["normalized_speed_curve_knots"]
        )
        # Beyond the tested 90-degree range, retain the measured boundary as a
        # conservative floor rather than inventing an extrapolated curve.
        speed = _interpolate(points, min(deviation, 90.0))
        status = "EMPIRICAL_PRELIMINARY" if deviation <= 90.0 else "OUTSIDE_TESTED_RANGE_BOUNDARY_FLOOR"
    elif ship == "Been":
        speed = _interpolate(BEEN_HEURISTIC_POINTS, deviation)
        status = "PARTIAL_EMPIRICAL_HEURISTIC"
    elif ship == "Pembroke":
        speed = _interpolate(PEMBROKE_PROXY_POINTS, deviation)
        status = "PROXY_ASSUMED_FROM_BEEN"
    else:
        raise ValueError(f"Unknown ship wind model: {ship}")
    return {
        "speed_knots": max(0.1, float(speed)),
        "relative_wind_deviation_deg": deviation,
        "model_status": status,
    }


def sail_instruction(ship: str, tack_required: bool, speed_knots: float) -> str:
    if ship == "Hoy":
        return (
            "Turn toward the next cyan route segment. Use the spanker to bring the bow through, then return to forward trim."
            if tack_required
            else "Hold the cyan route line with forward trim; use the spanker only for a course correction."
        )
    if ship == "Been":
        if tack_required or speed_knots < 1.0:
            return "Turn toward the next cyan route segment. Shiver the topsail during the turn, use the spanker to bring the bow through, then retrim the topsail for forward drive."
        return "Keep the topsail driving forward. Shiver it only if the ship begins losing or reversing progress."
    if ship == "Pembroke":
        if tack_required:
            return "Turn toward the next cyan route segment. Use unequal Fore/Main/Mizzen settings to rotate the ship, then restore forward trim."
        return "Keep Fore/Main/Mizzen set for forward drive; correct the heading with temporary sail asymmetry."
    raise ValueError(f"Unknown ship: {ship}")


def _segment_cost(
    distance_px: float,
    heading_deg: float,
    ship: str,
    wind_at_departure_deg: float,
    elapsed_minutes: float,
    pixels_per_nautical_mile: float | None,
) -> tuple[float, float, dict[str, Any]]:
    wind = wind_toward_at_elapsed(wind_at_departure_deg, elapsed_minutes)
    model = modeled_speed_knots(ship, heading_deg, wind)
    relative_cost = distance_px / model["speed_knots"]
    if pixels_per_nautical_mile:
        minutes = distance_px / pixels_per_nautical_mile / model["speed_knots"] * 60.0
    else:
        minutes = 0.0
    model = dict(model, wind_toward_deg=wind, heading_deg=heading_deg, distance_px=distance_px)
    return relative_cost, minutes, model


def _dogleg_options(
    region_id: str,
    a: tuple[int, int],
    b: tuple[int, int],
) -> list[tuple[int, int]]:
    _, _, nav, _, _, _, strict = _region_context(region_id)
    ax, ay = a
    bx, by = b
    length = math.hypot(bx - ax, by - ay)
    if length < 70 or not strict[ay, ax] or not strict[by, bx]:
        return []
    ux, uy = (bx - ax) / length, (by - ay) / length
    px, py = -uy, ux
    candidates = []
    for fraction in (0.24, 0.36, 0.50):
        offset = max(20.0, min(125.0, length * fraction))
        for side in (-1.0, 1.0):
            point = (int(round((ax + bx) / 2 + side * px * offset)), int(round((ay + by) / 2 + side * py * offset)))
            x, y = point
            if 0 <= x < strict.shape[1] and 0 <= y < strict.shape[0] and strict[y, x]:
                if _visible(a, point, strict) and _visible(point, b, strict):
                    candidates.append(point)
    return candidates


def _evaluate_polyline(
    points: list[tuple[int, int]],
    ship: str,
    wind_at_departure_deg: float,
    elapsed_minutes: float,
    pixels_per_nautical_mile: float | None,
) -> tuple[float, float, list[dict[str, Any]]]:
    score = 0.0
    minutes = 0.0
    rows = []
    for a, b in zip(points, points[1:]):
        distance = math.hypot(b[0] - a[0], b[1] - a[1])
        relative, delta_minutes, row = _segment_cost(
            distance,
            heading_bearing(a, b),
            ship,
            wind_at_departure_deg,
            elapsed_minutes + minutes,
            pixels_per_nautical_mile,
        )
        score += relative
        minutes += delta_minutes
        rows.append(row)
    return score, minutes, rows


def _apply_tacks(
    route: WorldRouteResult,
    ship: str,
    wind_at_departure_deg: float,
    pixels_per_nautical_mile: float | None,
    *,
    strategy: str,
    allow_tacks: bool,
    tack_delay_minutes: float = 0.0,
) -> tuple[WorldRouteResult, float, float, list[dict[str, Any]]]:
    route = copy.deepcopy(route)
    elapsed_minutes = 0.0
    relative_score = 0.0
    evaluations: list[dict[str, Any]] = []
    tack_points: list[dict[str, Any]] = []

    for leg_index, leg in enumerate(route.legs):
        revised_waypoints = [leg.waypoints[0]]
        for a, b in zip(leg.waypoints, leg.waypoints[1:]):
            direct_score, direct_minutes, direct_rows = _evaluate_polyline(
                [a, b], ship, wind_at_departure_deg, elapsed_minutes, pixels_per_nautical_mile
            )
            direct_model = direct_rows[0]
            best = (direct_score, direct_minutes, [a, b], direct_rows)
            materially_unfavorable = direct_model["speed_knots"] < 3.25 or direct_model["relative_wind_deviation_deg"] > 60.0
            tacks_enabled_now = allow_tacks and (
                tack_delay_minutes <= 0.0
                or (pixels_per_nautical_mile is not None and elapsed_minutes >= tack_delay_minutes)
            )
            if materially_unfavorable and tacks_enabled_now:
                for tack in _dogleg_options(leg.region_id, a, b):
                    candidate = _evaluate_polyline(
                        [a, tack, b], ship, wind_at_departure_deg, elapsed_minutes, pixels_per_nautical_mile
                    )
                    candidate_objective = candidate[1] if pixels_per_nautical_mile else candidate[0]
                    best_objective = best[1] if pixels_per_nautical_mile else best[0]
                    if candidate_objective < best_objective * 0.92:
                        best = (candidate[0], candidate[1], [a, tack, b], candidate[2])
            if len(best[2]) == 3:
                tack = best[2][1]
                instruction = sail_instruction(ship, True, min(row["speed_knots"] for row in best[3]))
                tack_elapsed = None
                tack_wind = None
                if pixels_per_nautical_mile:
                    first_row = best[3][0]
                    first_minutes = first_row["distance_px"] / pixels_per_nautical_mile / first_row["speed_knots"] * 60.0
                    tack_elapsed = elapsed_minutes + first_minutes
                    tack_wind = wind_toward_at_elapsed(wind_at_departure_deg, tack_elapsed)
                tack_points.append({
                    "region_id": leg.region_id,
                    "point": tack,
                    "leg_index": leg_index,
                    "instruction": instruction,
                    "expected_elapsed_minutes": None if tack_elapsed is None else round(tack_elapsed, 2),
                    "expected_wind_toward_deg": None if tack_wind is None else round(tack_wind, 1),
                    "strategy": strategy,
                })
                revised_waypoints.append(tack)
            revised_waypoints.append(b)
            relative_score += best[0]
            elapsed_minutes += best[1]
            evaluations.extend(
                dict(row, region_id=leg.region_id, leg_index=leg_index, tack_segment=len(best[2]) == 3)
                for row in best[3]
            )

        revised_route: list[tuple[int, int]] = []
        for a, b in zip(revised_waypoints, revised_waypoints[1:]):
            revised_route.extend(_line(a, b)[:-1])
        revised_route.append(revised_waypoints[-1])
        leg.waypoints = revised_waypoints
        leg.route_pixels = revised_route
        leg.route_length_px = sum(
            math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(revised_route, revised_route[1:])
        )

    route.total_distance_px = sum(leg.route_length_px for leg in route.legs)
    route.tack_points = tack_points
    return route, relative_score, elapsed_minutes, evaluations


def choose_wind_route(
    candidates: list[WorldRouteResult],
    ship: str,
    wind_at_departure_deg: float,
    *,
    pixels_per_nautical_mile: float | None = None,
) -> WindRoutePlan:
    if not candidates:
        raise ValueError("At least one safe route candidate is required.")
    if pixels_per_nautical_mile is not None and pixels_per_nautical_mile <= 0:
        pixels_per_nautical_mile = None
    strategy_specs = [
        ("direct_progress", False, 0.0),
        ("immediate_wind", True, 0.0),
    ]
    if pixels_per_nautical_mile:
        strategy_specs.extend([
            ("delayed_tack_6m", True, 6.0),
            ("delayed_tack_12m", True, 12.0),
            ("delayed_tack_18m", True, 18.0),
        ])
    # Without a verified distance/time scale, rotating-wind arrival time cannot
    # be simulated honestly. Keep the shortest safe corridor instead of chasing
    # an immediately favorable but potentially wasteful detour.
    corridor_candidates = candidates if pixels_per_nautical_mile else candidates[:1]
    planned = []
    for candidate_index, candidate in enumerate(corridor_candidates):
        for strategy, allow_tacks, delay in strategy_specs:
            planned_route, score, minutes, rows = _apply_tacks(
                candidate,
                ship,
                wind_at_departure_deg,
                pixels_per_nautical_mile,
                strategy=strategy,
                allow_tacks=allow_tacks,
                tack_delay_minutes=delay,
            )
            objective = minutes if pixels_per_nautical_mile else score
            planned.append({
                "objective": objective,
                "route": planned_route,
                "relative_score": score,
                "eta_minutes": minutes,
                "rows": rows,
                "candidate_index": candidate_index,
                "strategy": strategy,
            })
    planned.sort(key=lambda item: item["objective"])
    best_objective = planned[0]["objective"]
    tolerance = max(0.25, best_objective * 0.005) if pixels_per_nautical_mile else best_objective * 0.005
    near_tied = [item for item in planned if item["objective"] <= best_objective + tolerance]
    strategy_rank = {"direct_progress": 0, "delayed_tack_18m": 1, "delayed_tack_12m": 2, "delayed_tack_6m": 3, "immediate_wind": 4}
    selected_plan = min(near_tied, key=lambda item: (item["route"].total_distance_px, strategy_rank[item["strategy"]]))
    selected = selected_plan["route"]
    relative_score = selected_plan["relative_score"]
    eta_minutes = selected_plan["eta_minutes"]
    rows = selected_plan["rows"]
    selected_index = selected_plan["candidate_index"]
    strategy = selected_plan["strategy"]
    baseline = next(item for item in planned if item["candidate_index"] == 0 and item["strategy"] == "direct_progress")
    eta_advantage = baseline["eta_minutes"] - eta_minutes if pixels_per_nautical_mile else None
    if selected_index != 0:
        selected.route_choice = "wind_favored_tp_corridor"
    elif strategy.startswith("delayed_tack") and selected.tack_points:
        selected.route_choice = "direct_progress_delayed_tack"
    elif strategy == "immediate_wind" and selected.tack_points:
        selected.route_choice = "shortest_safe_with_tacks"
    else:
        selected.route_choice = "shortest_safe"
    warnings = []
    selection_explanation = None
    if selected_index != 0:
        if eta_advantage is not None and eta_advantage > 0:
            minutes = int(eta_advantage)
            seconds = int(round((eta_advantage - minutes) * 60))
            selection_explanation = f"Wind-favored route selected — estimated {minutes}m {seconds:02d}s faster."
        else:
            selection_explanation = "Wind-favored route selected after full-voyage comparison."
        warnings.append(selection_explanation)
    if strategy.startswith("delayed_tack") and selected.tack_points:
        first_tack = selected.tack_points[0]
        if first_tack["expected_elapsed_minutes"] is not None:
            selection_explanation = f"Direct progress recommended. Tack after ~{first_tack['expected_elapsed_minutes']:.0f} min as wind rotates."
            warnings.append(selection_explanation)
    if pixels_per_nautical_mile is None:
        eta_status = "MAP_SCALE_NOT_CALIBRATED"
        eta_value = None
    else:
        eta_status = "APPROXIMATE_DIRECTION_ONLY"
        eta_value = eta_minutes
    instructions = []
    for index, tack in enumerate(selected.tack_points, start=1):
        instructions.append({"step": index, **tack})
    return WindRoutePlan(
        route=selected,
        ship=ship,
        wind_at_departure_deg=float(wind_at_departure_deg) % 360.0,
        eta_minutes=eta_value,
        eta_status=eta_status,
        relative_time_score=relative_score,
        original_shortest_distance_px=candidates[0].total_distance_px,
        selected_distance_px=selected.total_distance_px,
        candidate_count=len(candidates),
        route_choice=selected.route_choice,
        segment_evaluations=rows,
        tack_points=selected.tack_points,
        sail_instructions=instructions,
        warnings=warnings,
        strategy=strategy,
        selection_explanation=selection_explanation,
        eta_advantage_minutes=eta_advantage,
        candidate_summaries=[{
            "strategy": item["strategy"],
            "corridor_index": item["candidate_index"],
            "regions": item["route"].region_sequence,
            "route_distance_px": round(item["route"].total_distance_px, 2),
            "eta_minutes": None if not pixels_per_nautical_mile else round(item["eta_minutes"], 3),
            "relative_time_score": round(item["relative_score"], 3),
            "selected": item is selected_plan,
        } for item in planned],
    )
