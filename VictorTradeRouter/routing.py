from __future__ import annotations

import csv
import heapq
import io
import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt, label


DATA = Path(__file__).with_name("stage1_data")
# Adaptive clearance policy. The raw obstacle mask remains the absolute boundary;
# these values only decide how closely a valid water route may approach it.
OPEN_WATER_CLEARANCE_PX = 14.0
NARROW_PASSAGE_CLEARANCE_PX = 10.0
PORT_APPROACH_CLEARANCE_PX = 5.0
TP_APPROACH_CLEARANCE_PX = 8.0
OPEN_WATER_CLEARANCE_PENALTY = 0.35
TRANSFORMS_FILE = Path(__file__).with_name("tp_transforms.json")
ANCHORS_FILE = Path(__file__).with_name("data") / "navigation_anchors_v3.json"


class RouteDiagnosticError(ValueError):
    def __init__(self, code: str, player_message: str, details: dict | None = None):
        super().__init__(player_message)
        self.code = code
        self.player_message = player_message
        self.details = details or {}


@dataclass(frozen=True)
class PortAnchorResolution:
    region_id: str
    port_id: str
    display_name: str
    semantic_point: tuple[int, int]
    navigation_anchor: tuple[int, int]
    snapped_distance_px: float
    status: str
    source: str

    def as_dict(self) -> dict:
        return {
            "region_id": self.region_id,
            "port_id": self.port_id,
            "display_name": self.display_name,
            "port_semantic_point": list(self.semantic_point),
            "port_navigation_anchor": list(self.navigation_anchor),
            "snapped_distance_px": round(self.snapped_distance_px, 3),
            "status": self.status,
            "source": self.source,
        }


@dataclass
class RouteResult:
    region_id: str
    region_name: str
    start_name: str
    destination_name: str
    start_kind: str
    destination_kind: str
    waypoints: list[tuple[int, int]]
    route_pixels: list[tuple[int, int]]
    collision_free: bool
    clearance_respected: bool
    route_length_px: float
    minimum_clearance_px: float
    core_minimum_clearance_px: float
    required_clearance_px: float
    endpoint_exception_px: float
    overlay_png: bytes


@dataclass(frozen=True)
class TPPoint:
    tp_id: str
    region_id: str
    point: tuple[int, int]
    relative_position: tuple[float, float]


@dataclass(frozen=True)
class TPTransition:
    pair_id: str
    from_tp_id: str
    to_tp_id: str
    from_region_id: str
    to_region_id: str
    relative_position: tuple[float, float]
    transformed_position: tuple[float, float]
    matching_location: bool
    orientation_resolved: bool
    transform_name: str


@dataclass
class WorldRouteResult:
    start_port_name: str
    destination_port_name: str
    region_sequence: list[str]
    legs: list[RouteResult]
    transitions: list[TPTransition]
    total_distance_px: float
    collision_free: bool
    clearance_respected: bool
    transition_locations_match: bool
    orientation_warnings: list[str]
    sequences_evaluated: int
    optimization_complete: bool
    navigation_start_name: str | None = None
    tack_points: list[dict] = field(default_factory=list)
    route_choice: str = "shortest_safe"
    anchor_resolutions: list[dict] = field(default_factory=list)
    diagnostics: list[dict] = field(default_factory=list)

    @property
    def teleport_count(self) -> int:
        return len(self.transitions)


@lru_cache(maxsize=1)
def load_regions() -> list[dict]:
    return json.loads((DATA / "world_database.json").read_text(encoding="utf-8"))["regions"]


@lru_cache(maxsize=1)
def world_alignment() -> dict:
    return json.loads(Path(__file__).with_name("world_alignment.json").read_text(encoding="utf-8"))


def regional_to_world(region_id: str, point: tuple[int, int]) -> tuple[int, int]:
    """Map a regional source-image point into the locked unified-world coordinates."""
    settings = world_alignment()
    if region_id not in settings["regions"]:
        raise ValueError(f"Unknown region transform: {region_id}")
    first, second = settings["regions"][region_id]
    x, y = point
    return (
        int(round(first[0] * x + first[1] * y + first[2])),
        int(round(second[0] * x + second[1] * y + second[2])),
    )


@lru_cache(maxsize=4)
def world_navigation_samples(step: int = 24) -> tuple[tuple[int, int, str, int, int], ...]:
    """Return click targets on owned navigable water without changing any mask."""
    samples: list[tuple[int, int, str, int, int]] = []
    for region in load_regions():
        region_id = region["region_id"]
        _, folder = load_region(region_id)
        nav = np.asarray(Image.open(folder / "navigation_water_mask.png").convert("L")) > 127
        owned = np.asarray(Image.open(folder / "ownership_mask.png").convert("L")) > 127
        valid = nav & owned
        height, width = valid.shape
        for y in range(step // 2, height, step):
            for x in range(step // 2, width, step):
                if valid[y, x]:
                    wx, wy = regional_to_world(region_id, (x, y))
                    samples.append((wx, wy, region_id, x, y))
    return tuple(samples)


@lru_cache(maxsize=32)
def load_region(region_id: str) -> tuple[dict, Path]:
    folder = DATA / "regions" / region_id
    if not folder.is_dir():
        raise ValueError(f"Unknown region: {region_id}")
    return json.loads((folder / "geometry.json").read_text(encoding="utf-8")), folder


def ports(region_id: str) -> list[dict]:
    geometry, _ = load_region(region_id)
    return list(geometry["ports"])


def locations(region_id: str) -> list[dict]:
    geometry, _ = load_region(region_id)
    names = {r["region_id"]: r["region_name"] for r in load_regions()}
    result = [
        {"key": p["port_id"], "label": f"Port — {p['display_name']}", "kind": "port", "data": p}
        for p in geometry["ports"]
    ]
    result.extend(
        {
            "key": tp["tp_id"],
            "label": f"TP — {names.get(tp['destination_region_id'], tp['destination_region_id'])}",
            "kind": "tp",
            "data": tp,
        }
        for tp in geometry["teleport_zones"]
    )
    return result


@lru_cache(maxsize=32)
def _region_context(region_id: str):
    geometry, folder = load_region(region_id)
    source = Image.open(folder / "source.png").convert("RGB")
    nav = np.asarray(Image.open(folder / "navigation_water_mask.png").convert("L")) > 127
    obstacles = np.asarray(Image.open(folder / "raw_obstacle_mask.png").convert("L")) > 127
    clearance = distance_transform_edt(~obstacles)
    required = NARROW_PASSAGE_CLEARANCE_PX
    all_strict = nav & ~obstacles & (clearance >= required)
    components, count = label(all_strict, structure=np.ones((3, 3), dtype=np.uint8))
    if not count:
        raise ValueError(f"{geometry['region']['region_name']} has no water meeting the clearance rule.")
    sizes = np.bincount(components.ravel())
    sizes[0] = 0
    strict = components == int(np.argmax(sizes))
    return geometry, source, nav, obstacles, clearance, required, strict


def _polygon_mask(polygon: list[list[int]], shape: tuple[int, int]) -> np.ndarray:
    zone = Image.new("1", (shape[1], shape[0]))
    ImageDraw.Draw(zone).polygon([(int(x), int(y)) for x, y in polygon], fill=1)
    return np.asarray(zone, dtype=bool)


def _point_for_location(location: dict, nav: np.ndarray, clearance: np.ndarray) -> tuple[int, int]:
    data = location["data"]
    if location["kind"] == "port":
        return int(data["pixel_x"]), int(data["pixel_y"])
    candidates = _polygon_mask(data["polygon_coordinates"], nav.shape) & nav
    if not candidates.any():
        raise ValueError(f"TP {data['tp_id']} contains no navigable point.")
    score = np.where(candidates, clearance, -1)
    y, x = np.unravel_index(np.argmax(score), score.shape)
    return int(x), int(y)


def _neighbors(point: tuple[int, int], shape: tuple[int, int]):
    x, y = point
    h, w = shape
    for dx, dy, cost in (
        (1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1),
        (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)),
        (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2)),
    ):
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h:
            yield (nx, ny), cost


def _reconstruct(came: dict, current: tuple[int, int]) -> list[tuple[int, int]]:
    path = []
    while current is not None:
        path.append(current)
        current = came[current]
    return path[::-1]


def _clearance_cost_multiplier(clearance_px: float) -> float:
    """Prefer 14 px open water while still permitting necessary 10 px channels."""
    if clearance_px >= OPEN_WATER_CLEARANCE_PX:
        return 1.0
    span = OPEN_WATER_CLEARANCE_PX - NARROW_PASSAGE_CLEARANCE_PX
    shortfall = (OPEN_WATER_CLEARANCE_PX - clearance_px) / span
    return 1.0 + OPEN_WATER_CLEARANCE_PENALTY * max(0.0, min(1.0, shortfall)) ** 2


def _astar(
    mask: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    clearance: np.ndarray | None = None,
) -> list[tuple[int, int]]:
    queue = [(0.0, start)]
    came = {start: None}
    score = {start: 0.0}
    while queue:
        _, current = heapq.heappop(queue)
        if current == goal:
            return _reconstruct(came, current)
        for nxt, step in _neighbors(current, mask.shape):
            if not mask[nxt[1], nxt[0]]:
                continue
            multiplier = 1.0
            if clearance is not None:
                multiplier = _clearance_cost_multiplier(float(clearance[nxt[1], nxt[0]]))
            tentative = score[current] + step * multiplier
            if tentative < score.get(nxt, math.inf):
                score[nxt] = tentative
                came[nxt] = current
                heapq.heappush(queue, (tentative + math.hypot(goal[0] - nxt[0], goal[1] - nxt[1]), nxt))
    raise ValueError("No safe route exists between these locations at the required clearance.")


def _escape_path(nav: np.ndarray, strict: np.ndarray, start: tuple[int, int]) -> list[tuple[int, int]]:
    if not nav[start[1], start[0]]:
        raise ValueError(f"Endpoint {start} is outside the navigation-water mask.")
    if strict[start[1], start[0]]:
        return [start]
    queue = [(0.0, start)]
    came = {start: None}
    score = {start: 0.0}
    while queue:
        distance, current = heapq.heappop(queue)
        if strict[current[1], current[0]]:
            return _reconstruct(came, current)
        for nxt, step in _neighbors(current, nav.shape):
            if not nav[nxt[1], nxt[0]]:
                continue
            candidate = distance + step
            if candidate < score.get(nxt, math.inf):
                score[nxt] = candidate
                came[nxt] = current
                heapq.heappush(queue, (candidate, nxt))
    raise ValueError(f"Endpoint {start} cannot reach the main safe-water area without crossing an obstacle.")


def _approach_clearance(kind: str) -> float:
    if kind == "port":
        return PORT_APPROACH_CLEARANCE_PX
    if kind == "tp":
        return TP_APPROACH_CLEARANCE_PX
    return NARROW_PASSAGE_CLEARANCE_PX


def _adaptive_escape(
    nav: np.ndarray,
    obstacles: np.ndarray,
    clearance: np.ndarray,
    strict: np.ndarray,
    start: tuple[int, int],
    kind: str,
) -> tuple[list[tuple[int, int]], float]:
    """Connect an endpoint to the 10 px core using its local approach tier.

    An exact recorded endpoint can sit inside its tier (for example, beside a
    dock or near the edge of a TP rectangle). In that case only the shortest
    initial escape is exempt from the tier; raw obstacles are never exempt.
    """
    water = nav & ~obstacles
    minimum = _approach_clearance(kind)
    tier = water & (clearance >= minimum)
    components, count = label(tier, structure=np.ones((3, 3), dtype=np.uint8))
    if not count:
        raise ValueError(f"Endpoint {start} has no water meeting its {minimum:g} px approach clearance.")
    connected_ids = set(int(value) for value in np.unique(components[strict]))
    connected_ids.discard(0)
    connected_tier = tier & np.isin(components, list(connected_ids))
    if not connected_tier.any():
        raise ValueError(f"Endpoint {start} cannot reach the main safe-water area at its approach clearance.")

    endpoint_escape = _escape_path(water, connected_tier, start)
    tier_escape = _escape_path(connected_tier, strict, endpoint_escape[-1])
    endpoint_leg = _simplify(endpoint_escape, water)
    tier_leg = _simplify(tier_escape, connected_tier)
    waypoints = endpoint_leg[:-1] + tier_leg
    exception_length = sum(
        math.hypot(b[0] - a[0], b[1] - a[1])
        for a, b in zip(endpoint_escape, endpoint_escape[1:])
    )
    return waypoints, exception_length


@lru_cache(maxsize=1)
def _anchor_settings() -> dict:
    if not ANCHORS_FILE.exists():
        return {"anchors": {}}
    return json.loads(ANCHORS_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=32)
def _reachable_navigation_water(region_id: str) -> np.ndarray:
    _, _, nav, _, _, _, strict = _region_context(region_id)
    components, _ = label(nav, structure=np.ones((3, 3), dtype=np.uint8))
    connected_ids = set(int(value) for value in np.unique(components[strict]))
    connected_ids.discard(0)
    return nav & np.isin(components, list(connected_ids))


def _nearest_reachable_point(
    region_id: str,
    seed: tuple[int, int],
    max_radius_px: float,
) -> tuple[int, int] | None:
    _, _, _, _, clearance, _, _ = _region_context(region_id)
    reachable = _reachable_navigation_water(region_id)
    sx, sy = seed
    height, width = reachable.shape
    if not (0 <= sx < width and 0 <= sy < height):
        return None
    if reachable[sy, sx]:
        return seed
    radius = int(math.ceil(max_radius_px))
    x0, x1 = max(0, sx - radius), min(width, sx + radius + 1)
    y0, y1 = max(0, sy - radius), min(height, sy + radius + 1)
    ys, xs = np.nonzero(reachable[y0:y1, x0:x1])
    if not len(xs):
        return None
    xs, ys = xs + x0, ys + y0
    distances = np.hypot(xs - sx, ys - sy)
    valid = distances <= max_radius_px
    if not valid.any():
        return None
    candidates = [
        (float(distances[index]), -float(clearance[ys[index], xs[index]]), int(xs[index]), int(ys[index]))
        for index in np.flatnonzero(valid)
    ]
    _, _, x, y = min(candidates)
    return x, y


@lru_cache(maxsize=128)
def resolve_port_navigation_anchor(region_id: str, port_id: str) -> PortAnchorResolution:
    port = _port_record(region_id, port_id)
    semantic = (int(port["pixel_x"]), int(port["pixel_y"]))
    entry = _anchor_settings().get("anchors", {}).get(port_id, {})
    explicit = entry.get("port_navigation_anchor") or entry.get("preferred_point")
    seed = tuple(int(value) for value in explicit) if explicit else semantic
    max_radius = float(entry.get("max_snap_distance_px", 96.0))
    anchor = _nearest_reachable_point(region_id, seed, max_radius)
    if anchor is None:
        raise RouteDiagnosticError(
            "DESTINATION_ANCHOR_INVALID",
            f"{port['display_name']} does not yet have a reachable harbor-water anchor.",
            {"region_id": region_id, "port_id": port_id, "semantic_point": semantic, "attempted_seed": seed},
        )
    _, _, nav, obstacles, clearance, _, strict = _region_context(region_id)
    try:
        _adaptive_escape(nav, obstacles, clearance, strict, anchor, "port")
    except ValueError as exc:
        raise RouteDiagnosticError(
            "START_TO_WATER_UNREACHABLE",
            f"{port['display_name']}'s nearby harbor water cannot connect to the safe-water area.",
            {"region_id": region_id, "port_id": port_id, "navigation_anchor": anchor, "cause": str(exc)},
        ) from exc
    distance = math.hypot(anchor[0] - semantic[0], anchor[1] - semantic[1])
    if explicit:
        status = "EXPLICIT_NAVIGATION_ANCHOR"
    elif anchor == semantic:
        status = "UNCHANGED_REACHABLE"
    else:
        status = "LOCAL_SAFE_SNAP"
    return PortAnchorResolution(
        region_id,
        port_id,
        port["display_name"],
        semantic,
        anchor,
        distance,
        status,
        entry.get("source", "automatic_connectivity_audit"),
    )


def resolve_current_position(region_id: str, point: tuple[int, int], max_radius_px: float = 24.0) -> tuple[tuple[int, int], dict]:
    _, _, nav, obstacles, _, _, _ = _region_context(region_id)
    reachable = _reachable_navigation_water(region_id)
    x, y = int(point[0]), int(point[1])
    height, width = nav.shape
    if not (0 <= x < width and 0 <= y < height):
        raise RouteDiagnosticError("CURRENT_POSITION_INVALID", "The selected current position is outside the regional map.", {"region_id": region_id, "point": [x, y]})
    if reachable[y, x] and not obstacles[y, x]:
        return (x, y), {"code": "CURRENT_POSITION_VALID", "original_point": [x, y], "navigation_point": [x, y], "snapped_distance_px": 0.0}
    if nav[y, x] and not reachable[y, x]:
        raise RouteDiagnosticError(
            "CURRENT_POSITION_INVALID",
            "That point is in isolated water and cannot reach the open navigation area. Pick nearby open water.",
            {"region_id": region_id, "point": [x, y], "reason": "isolated_navigation_component"},
        )
    snapped = _nearest_reachable_point(region_id, (x, y), max_radius_px)
    if snapped is None:
        raise RouteDiagnosticError(
            "CURRENT_POSITION_INVALID",
            "That point is not close enough to reachable water. Pick just offshore.",
            {"region_id": region_id, "point": [x, y], "max_snap_distance_px": max_radius_px},
        )
    saw_water = False
    for lx, ly in _line((x, y), snapped):
        is_water = bool(nav[ly, lx] and not obstacles[ly, lx])
        if is_water:
            saw_water = True
        elif saw_water:
            raise RouteDiagnosticError(
                "CURRENT_POSITION_INVALID",
                "The nearest water is across land. Pick the water on your current side of the shoreline.",
                {"region_id": region_id, "point": [x, y], "attempted_snap": list(snapped)},
            )
    distance = math.hypot(snapped[0] - x, snapped[1] - y)
    return snapped, {"code": "CURRENT_POSITION_SAFE_SNAP", "original_point": [x, y], "navigation_point": list(snapped), "snapped_distance_px": round(distance, 3)}


def audit_port_navigation_anchors() -> list[dict]:
    findings = []
    for region in load_regions():
        for port in ports(region["region_id"]):
            findings.append(resolve_port_navigation_anchor(region["region_id"], port["port_id"]).as_dict())
    return findings


def _line(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
    x0, y0 = a
    x1, y1 = b
    count = max(abs(x1 - x0), abs(y1 - y0), 1)
    return list(dict.fromkeys(
        (int(round(x0 + (x1 - x0) * i / count)), int(round(y0 + (y1 - y0) * i / count)))
        for i in range(count + 1)
    ))


def _visible(a: tuple[int, int], b: tuple[int, int], mask: np.ndarray) -> bool:
    return all(mask[y, x] for x, y in _line(a, b))


def _simplify(path: list[tuple[int, int]], mask: np.ndarray) -> list[tuple[int, int]]:
    if len(path) < 3:
        return path
    result = [path[0]]
    anchor = 0
    while anchor < len(path) - 1:
        farthest = anchor + 1
        for candidate in range(len(path) - 1, anchor + 1, -1):
            if _visible(path[anchor], path[candidate], mask):
                farthest = candidate
                break
        result.append(path[farthest])
        anchor = farthest
    return result


def _draw_overlay(source, route, waypoints, start_name, end_name, start_kind, end_kind) -> bytes:
    image = source.convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.line(route, fill=(0, 25, 45, 210), width=9, joint="curve")
    draw.line(route, fill=(0, 235, 255, 255), width=4, joint="curve")
    for i, point in enumerate(waypoints[1:-1], start=1):
        draw.ellipse((point[0]-6, point[1]-6, point[0]+6, point[1]+6), fill="white", outline=(0,25,45), width=3)
        draw.text((point[0]+9, point[1]-10), str(i), fill="white", stroke_width=3, stroke_fill=(0,25,45))
    sx, sy = waypoints[0]
    ex, ey = waypoints[-1]
    draw.ellipse((sx-9, sy-9, sx+9, sy+9), fill=(50, 225, 120), outline=(0, 25, 45), width=3)
    end_color = (255, 190, 40) if end_kind == "tp" else (255, 85, 85)
    draw.rectangle((ex-9, ey-9, ex+9, ey+9), fill=end_color, outline=(0, 25, 45), width=3)
    draw.text((12, 12), f"{start_name}  →  {end_name}", fill="white", stroke_width=3, stroke_fill=(0,0,0))
    if start_kind == "tp":
        draw.text((sx+12, sy+8), "TP exit", fill="white", stroke_width=3, stroke_fill=(0,0,0))
    if end_kind == "tp":
        draw.text((ex+12, ey+8), "TP entry", fill="white", stroke_width=3, stroke_fill=(0,0,0))
    out = io.BytesIO()
    image.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


@lru_cache(maxsize=512)
def generate_route_between_points(
    region_id: str,
    start: tuple[int, int],
    end: tuple[int, int],
    start_name: str,
    end_name: str,
    start_kind: str = "port",
    end_kind: str = "port",
) -> RouteResult:
    geometry, source, nav, obstacles, clearance, required, strict = _region_context(region_id)
    if start == end:
        raise ValueError("Route endpoints must be different.")
    h, w = nav.shape
    if not (0 <= start[0] < w and 0 <= start[1] < h and 0 <= end[0] < w and 0 <= end[1] < h):
        raise ValueError("A route endpoint is outside its regional map.")
    start_leg, start_exception = _adaptive_escape(nav, obstacles, clearance, strict, start, start_kind)
    end_outbound, end_exception = _adaptive_escape(nav, obstacles, clearance, strict, end, end_kind)
    core = _astar(strict, start_leg[-1], end_outbound[-1], clearance)
    core_leg = _simplify(core, strict)
    end_leg = end_outbound[::-1]
    waypoints = start_leg[:-1] + core_leg + end_leg[1:]
    route = []
    for a, b in zip(waypoints, waypoints[1:]):
        route.extend(_line(a, b)[:-1])
    route.append(waypoints[-1])
    collision_free = all(nav[y, x] and not obstacles[y, x] for x, y in route)
    length = sum(math.hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(route, route[1:]))
    clearances = [float(clearance[y, x]) for x, y in route]
    core_clearances = [float(clearance[y, x]) for x, y in core]
    exception_length = start_exception + end_exception
    return RouteResult(
        region_id, geometry["region"]["region_name"], start_name, end_name, start_kind, end_kind,
        waypoints, route, collision_free, min(core_clearances) + 1e-6 >= required,
        length, min(clearances), min(core_clearances), required, exception_length,
        _draw_overlay(source, route, waypoints, start_name, end_name, start_kind, end_kind),
    )


def generate_route(region_id: str, start_key: str, destination_key: str) -> RouteResult:
    items = {item["key"]: item for item in locations(region_id)}
    if start_key not in items or destination_key not in items:
        raise ValueError("The selected location does not exist in this region.")
    if start_key == destination_key:
        raise ValueError("Start and destination must be different.")
    _, _, nav, _, clearance, _, _ = _region_context(region_id)
    start_item, end_item = items[start_key], items[destination_key]
    start = (
        resolve_port_navigation_anchor(region_id, start_key).navigation_anchor
        if start_item["kind"] == "port"
        else _point_for_location(start_item, nav, clearance)
    )
    end = (
        resolve_port_navigation_anchor(region_id, destination_key).navigation_anchor
        if end_item["kind"] == "port"
        else _point_for_location(end_item, nav, clearance)
    )
    return generate_route_between_points(
        region_id, start, end, start_item["label"], end_item["label"], start_item["kind"], end_item["kind"]
    )


def _uv_to_point(uv: tuple[float, float], polygon: list[list[int]]) -> tuple[int, int]:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return (
        int(round(min(xs) + uv[0] * (max(xs) - min(xs)))),
        int(round(min(ys) + uv[1] * (max(ys) - min(ys)))),
    )


@lru_cache(maxsize=1)
def _transform_settings() -> dict:
    if not TRANSFORMS_FILE.exists():
        return {"default": {"transform": "identity", "orientation_resolved": False}, "pairs": {}}
    return json.loads(TRANSFORMS_FILE.read_text(encoding="utf-8"))


def _apply_transform(uv: tuple[float, float], name: str) -> tuple[float, float]:
    u, v = uv
    transforms = {
        "identity": (u, v), "flip_u": (1-u, v), "flip_v": (u, 1-v),
        "flip_both": (1-u, 1-v), "swap_uv": (v, u),
        "swap_uv_flip_u": (1-v, u), "swap_uv_flip_v": (v, 1-u),
    }
    if name not in transforms:
        raise ValueError(f"Unsupported TP transform: {name}")
    return transforms[name]


@lru_cache(maxsize=1)
def _tp_records() -> dict[str, dict]:
    records = {}
    for region in load_regions():
        geometry, _ = load_region(region["region_id"])
        for tp in geometry["teleport_zones"]:
            records[tp["tp_id"]] = tp
    return records


@lru_cache(maxsize=1)
def _pair_records() -> list[dict]:
    with (DATA / "teleport_pairs.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _matching_pair_point_candidates(
    pair: dict,
    transform_name: str,
    limit: int = 6,
) -> list[tuple[TPPoint, TPPoint]]:
    records = _tp_records()
    a, b = records[pair["tp_a_id"]], records[pair["tp_b_id"]]
    _, _, nav_a, obstacles_a, clear_a, _, _ = _region_context(a["region_id"])
    _, _, nav_b, obstacles_b, clear_b, _, _ = _region_context(b["region_id"])
    mask_a = _polygon_mask(a["polygon_coordinates"], nav_a.shape) & nav_a & ~obstacles_a
    mask_b = _polygon_mask(b["polygon_coordinates"], nav_b.shape) & nav_b & ~obstacles_b
    reachable_a = _reachable_navigation_water(a["region_id"])
    reachable_b = _reachable_navigation_water(b["region_id"])
    candidates = []
    for u in np.linspace(0.05, 0.95, 19):
        for v in np.linspace(0.05, 0.95, 19):
            uv_a = (float(u), float(v))
            uv_b = _apply_transform(uv_a, transform_name)
            pa = _uv_to_point(uv_a, a["polygon_coordinates"])
            pb = _uv_to_point(uv_b, b["polygon_coordinates"])
            if not (0 <= pa[0] < nav_a.shape[1] and 0 <= pa[1] < nav_a.shape[0]):
                continue
            if not (0 <= pb[0] < nav_b.shape[1] and 0 <= pb[1] < nav_b.shape[0]):
                continue
            if (
                mask_a[pa[1], pa[0]]
                and mask_b[pb[1], pb[0]]
                and reachable_a[pa[1], pa[0]]
                and reachable_b[pb[1], pb[0]]
            ):
                score = min(float(clear_a[pa[1], pa[0]]), float(clear_b[pb[1], pb[0]]))
                candidates.append((score, uv_a, uv_b, pa, pb))
    if not candidates:
        raise RouteDiagnosticError(
            "TP_EXIT_INVALID",
            "A teleport pair has no mutually reachable water position.",
            {"pair_id": pair["pair_id"], "tp_a_id": pair["tp_a_id"], "tp_b_id": pair["tp_b_id"]},
        )
    tier_candidates = [item for item in candidates if item[0] >= TP_APPROACH_CLEARANCE_PX]
    if tier_candidates:
        candidates = tier_candidates
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = []
    seen = set()
    for _, uv_a, uv_b, pa, pb in candidates:
        key = (pa, pb)
        if key in seen:
            continue
        seen.add(key)
        selected.append((
            TPPoint(a["tp_id"], a["region_id"], pa, uv_a),
            TPPoint(b["tp_id"], b["region_id"], pb, uv_b),
        ))
        if len(selected) >= limit:
            break
    return selected


def _matching_pair_points(pair: dict, transform_name: str) -> tuple[TPPoint, TPPoint]:
    return _matching_pair_point_candidates(pair, transform_name, limit=1)[0]


@lru_cache(maxsize=1)
def _transition_catalog():
    settings = _transform_settings()
    by_tp, points = {}, {}
    for pair in _pair_records():
        override = settings.get("pairs", {}).get(pair["pair_id"], {})
        default = settings.get("default", {})
        transform_name = override.get("transform", default.get("transform", "identity"))
        resolved = bool(override.get("orientation_resolved", default.get("orientation_resolved", False)))
        candidates = _matching_pair_point_candidates(pair, transform_name)
        point_a, point_b = candidates[0]
        points[point_a.tp_id], points[point_b.tp_id] = point_a, point_b
        by_tp[point_a.tp_id] = {"pair": pair, "other": point_b.tp_id, "transform": transform_name, "resolved": resolved, "from_uv": point_a.relative_position, "to_uv": point_b.relative_position, "candidates": candidates}
        by_tp[point_b.tp_id] = {"pair": pair, "other": point_a.tp_id, "transform": transform_name, "resolved": resolved, "from_uv": point_b.relative_position, "to_uv": point_a.relative_position, "candidates": [(b_point, a_point) for a_point, b_point in candidates]}
    return by_tp, points


def _port_record(region_id: str, port_id: str) -> dict:
    match = next((p for p in ports(region_id) if p["port_id"] == port_id), None)
    if match is None:
        raise ValueError(f"Port {port_id} does not exist in {region_id}.")
    return match


def _tp_label(tp_id: str, arrival: bool) -> str:
    tp = _tp_records()[tp_id]
    names = {r["region_id"]: r["region_name"] for r in load_regions()}
    other = names.get(tp["destination_region_id"], tp["destination_region_id"])
    return f"TP {'exit from' if arrival else 'entry to'} {other}"


def generate_world_route_candidates(
    start_region_id: str,
    start_port_id: str,
    destination_region_id: str,
    destination_port_id: str,
    *,
    navigation_start_region_id: str | None = None,
    navigation_start_point: tuple[int, int] | None = None,
    navigation_start_name: str | None = None,
    max_candidates: int = 12,
    distance_slack: float = 1.75,
) -> list[WorldRouteResult]:
    """Generate safe TP-corridor candidates from the locked Stage 1 geometry.

    The original public route function still returns the geometrically shortest
    candidate. Wind-aware callers can compare this bounded candidate set without
    restitching, rescaling, or modifying any map/mask/TP data.
    """
    region_ids = {r["region_id"] for r in load_regions()}
    if start_region_id not in region_ids or destination_region_id not in region_ids:
        raise ValueError("The selected region does not exist.")
    start_port = _port_record(start_region_id, start_port_id)
    destination_port = _port_record(destination_region_id, destination_port_id)
    try:
        start_anchor = resolve_port_navigation_anchor(start_region_id, start_port_id)
    except RouteDiagnosticError as exc:
        raise RouteDiagnosticError("START_ANCHOR_INVALID", exc.player_message, exc.details) from exc
    try:
        destination_anchor = resolve_port_navigation_anchor(destination_region_id, destination_port_id)
    except RouteDiagnosticError as exc:
        raise RouteDiagnosticError("DESTINATION_ANCHOR_INVALID", exc.player_message, exc.details) from exc
    anchor_resolutions = [start_anchor.as_dict(), destination_anchor.as_dict()]
    route_diagnostics: list[dict] = []
    route_start_region_id = navigation_start_region_id or start_region_id
    if route_start_region_id not in region_ids:
        raise RouteDiagnosticError("REGION_TRANSFORM_ERROR", "The selected current-position region is not registered in the world map.", {"region_id": route_start_region_id})
    start_point = start_anchor.navigation_anchor
    route_start_label = navigation_start_name or f"Port — {start_port['display_name']}"
    if navigation_start_point is not None:
        start_point, current_diagnostic = resolve_current_position(route_start_region_id, navigation_start_point)
        route_diagnostics.append(current_diagnostic)
    destination_point = destination_anchor.navigation_anchor
    by_tp, transition_points = _transition_catalog()
    tps_by_region = {}
    for tp_id, point in transition_points.items():
        tps_by_region.setdefault(point.region_id, []).append(tp_id)

    def evaluate(departures: tuple[str, ...]):
        legs, transitions = [], []
        region_id, point = route_start_region_id, start_point
        point_name = route_start_label
        point_kind = "current_position" if navigation_start_point is not None else "port"
        for departure_tp in departures:
            info = by_tp[departure_tp]
            attempted = []
            chosen = None
            for target, arrival in info["candidates"]:
                if target.region_id != region_id:
                    continue
                try:
                    candidate_leg = generate_route_between_points(
                        region_id, point, target.point, point_name, _tp_label(departure_tp, arrival=False), point_kind, "tp"
                    )
                    chosen = (candidate_leg, target, arrival)
                    break
                except ValueError as exc:
                    attempted.append({"target_point": list(target.point), "cause": str(exc)})
            if chosen is None:
                raise RouteDiagnosticError(
                    "TP_ENTRY_UNREACHABLE",
                    "A teleport approach could not be reached safely; alternate portal points and corridors were checked.",
                    {"region_id": region_id, "tp_id": departure_tp, "start_point": list(point), "attempts": attempted},
                )
            leg, target, arrival = chosen
            legs.append(leg)
            arrival_tp = arrival.tp_id
            transitions.append(TPTransition(
                info["pair"]["pair_id"], departure_tp, arrival_tp, region_id, arrival.region_id,
                target.relative_position, arrival.relative_position, True, info["resolved"], info["transform"],
            ))
            region_id, point = arrival.region_id, arrival.point
            point_name, point_kind = _tp_label(arrival_tp, arrival=True), "tp"
        try:
            legs.append(generate_route_between_points(
                region_id, point, destination_point, point_name, f"Port — {destination_port['display_name']}", point_kind, "port"
            ))
        except ValueError as exc:
            raise RouteDiagnosticError(
                "LOCAL_LEG_BLOCKED",
                f"The final local approach to {destination_port['display_name']} could not be connected safely.",
                {"region_id": region_id, "start_point": list(point), "destination_anchor": list(destination_point), "cause": str(exc)},
            ) from exc
        return legs, transitions

    # Enumerate complete TP sequences by an admissible straight-line lower bound.
    # Each evaluated candidate is then priced with the real obstacle-safe pathfinder.
    counter = 0
    queue = [(0.0, counter, "partial", route_start_region_id, start_point, (), frozenset({route_start_region_id}))]
    completed: list[tuple[float, list[RouteResult], list[TPTransition]]] = []
    failures = []
    evaluated = 0
    while queue:
        lower_bound, _, kind, region_id, point, departures, visited_regions = heapq.heappop(queue)
        if completed and lower_bound > completed[0][0] * distance_slack:
            break
        if kind == "complete":
            evaluated += 1
            try:
                legs, transitions = evaluate(departures)
                actual = sum(leg.route_length_px for leg in legs)
                completed.append((actual, legs, transitions))
                completed.sort(key=lambda item: item[0])
            except RouteDiagnosticError as exc:
                failures.append({"code": exc.code, "message": exc.player_message, "details": exc.details})
            except ValueError as exc:
                failures.append({"code": "LOCAL_LEG_BLOCKED", "message": str(exc), "details": {}})
            if evaluated >= max_candidates:
                break
            continue
        if region_id == destination_region_id:
            counter += 1
            final_bound = lower_bound + math.hypot(destination_point[0] - point[0], destination_point[1] - point[1])
            heapq.heappush(queue, (final_bound, counter, "complete", region_id, point, departures, visited_regions))
        for departure_tp in tps_by_region.get(region_id, []):
            target = transition_points[departure_tp]
            arrival = transition_points[by_tp[departure_tp]["other"]]
            if arrival.region_id in visited_regions:
                continue
            counter += 1
            next_bound = lower_bound + math.hypot(target.point[0] - point[0], target.point[1] - point[1])
            heapq.heappush(queue, (
                next_bound, counter, "partial", arrival.region_id, arrival.point,
                departures + (departure_tp,), visited_regions | {arrival.region_id},
            ))

    if not completed:
        raise RouteDiagnosticError(
            "NO_VALID_TP_CORRIDOR",
            "No safe connected route was found after checking nearby harbor water, teleport-zone points, and alternate corridors.",
            {"start_port": start_port["display_name"], "destination_port": destination_port["display_name"], "failures": failures},
        )
    results = []
    optimization_complete = not queue
    for index, (total_distance, legs, transitions) in enumerate(completed):
        warnings = [
            f"{t.pair_id} ({t.from_tp_id} → {t.to_tp_id}) uses '{t.transform_name}' because flip/rotation orientation is unresolved."
            for t in transitions if not t.orientation_resolved
        ]
        results.append(WorldRouteResult(
            start_port["display_name"], destination_port["display_name"], [leg.region_name for leg in legs], legs, transitions,
            total_distance, all(leg.collision_free for leg in legs), all(leg.clearance_respected for leg in legs),
            all(t.matching_location for t in transitions), warnings, evaluated, optimization_complete,
            route_start_label, [], "shortest_safe" if index == 0 else "alternative_tp_corridor",
            anchor_resolutions, list(route_diagnostics),
        ))
    return results


def generate_world_route(
    start_region_id: str,
    start_port_id: str,
    destination_region_id: str,
    destination_port_id: str,
    *,
    navigation_start_region_id: str | None = None,
    navigation_start_point: tuple[int, int] | None = None,
    navigation_start_name: str | None = None,
) -> WorldRouteResult:
    return generate_world_route_candidates(
        start_region_id,
        start_port_id,
        destination_region_id,
        destination_port_id,
        navigation_start_region_id=navigation_start_region_id,
        navigation_start_point=navigation_start_point,
        navigation_start_name=navigation_start_name,
        max_candidates=12,
    )[0]


def _font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _dashed_line(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], fill, width=5, dash=16, gap=10):
    for start, end in zip(points, points[1:]):
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        if length == 0:
            continue
        distance = 0.0
        while distance < length:
            finish = min(distance + dash, length)
            p1 = (int(round(start[0] + (end[0] - start[0]) * distance / length)), int(round(start[1] + (end[1] - start[1]) * distance / length)))
            p2 = (int(round(start[0] + (end[0] - start[0]) * finish / length)), int(round(start[1] + (end[1] - start[1]) * finish / length)))
            draw.line((p1, p2), fill=fill, width=width)
            distance += dash + gap


def render_unified_route(result: WorldRouteResult) -> bytes:
    """Draw the route directly on the locked world map, with no report header."""
    settings = world_alignment()
    world_path = Path(__file__).parent / settings["world_map"]
    world = Image.open(world_path).convert("RGB")
    header_height = 0
    canvas = world.copy()
    draw = ImageDraw.Draw(canvas)

    def world_point(region_id: str, point: tuple[int, int]) -> tuple[int, int]:
        first, second = settings["regions"][region_id]
        x, y = point
        return (
            int(round(first[0] * x + first[1] * y + first[2])),
            header_height + int(round(second[0] * x + second[1] * y + second[2])),
        )

    transformed_legs = []
    for leg in result.legs:
        route = [world_point(leg.region_id, point) for point in leg.route_pixels]
        waypoints = [world_point(leg.region_id, point) for point in leg.waypoints]
        transformed_legs.append((route, waypoints, leg))
        draw.line(route, fill=(2, 20, 29), width=8, joint="curve")
        draw.line(route, fill=(0, 240, 255), width=4, joint="curve")
        for point in waypoints[1:-1]:
            draw.ellipse((point[0]-3, point[1]-3, point[0]+3, point[1]+3), fill="white", outline=(2,20,29), width=1)

    for index in range(len(transformed_legs) - 1):
        entry = transformed_legs[index][1][-1]
        exit_point = transformed_legs[index + 1][1][0]
        _dashed_line(draw, [entry, exit_point], (5, 18, 26), width=9, dash=13, gap=8)
        _dashed_line(draw, [entry, exit_point], (255, 196, 45), width=4, dash=13, gap=8)
        for point in (entry, exit_point):
            x, y = point
            draw.polygon(((x, y-7), (x+7, y), (x, y+7), (x-7, y)), fill=(255,196,45), outline=(5,18,26))
        middle = ((entry[0] + exit_point[0]) // 2, (entry[1] + exit_point[1]) // 2)
        draw.rounded_rectangle((middle[0]-15, middle[1]-10, middle[0]+15, middle[1]+10), radius=5, fill=(10,31,43))
        draw.text(middle, "TP", fill=(255,215,75), font=_font(12, bold=True), anchor="mm")

    for tack in result.tack_points:
        tx, ty = world_point(tack["region_id"], tuple(tack["point"]))
        leg = result.legs[int(tack["leg_index"])]
        tack_point = tuple(tack["point"])
        try:
            tack_index = leg.waypoints.index(tack_point)
        except ValueError:
            tack_index = -1
        if 0 <= tack_index < len(leg.waypoints) - 1:
            next_point = world_point(leg.region_id, leg.waypoints[tack_index + 1])
            dx, dy = next_point[0] - tx, next_point[1] - ty
        else:
            dx, dy = 1.0, 0.0
        length = max(math.hypot(dx, dy), 1.0)
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        tail = (int(round(tx - ux * 14)), int(round(ty - uy * 14)))
        tip = (int(round(tx + ux * 18)), int(round(ty + uy * 18)))
        draw.line((tail, tip), fill=(2, 20, 29), width=11)
        draw.line((tail, tip), fill=(255, 151, 42), width=6)
        arrow = (
            tip,
            (int(round(tip[0] - ux * 13 + px * 8)), int(round(tip[1] - uy * 13 + py * 8))),
            (int(round(tip[0] - ux * 13 - px * 8)), int(round(tip[1] - uy * 13 - py * 8))),
        )
        draw.polygon(arrow, fill=(255, 151, 42), outline=(2, 20, 29))

    start = transformed_legs[0][1][0]
    destination = transformed_legs[-1][1][-1]
    draw.ellipse((start[0]-8, start[1]-8, start[0]+8, start[1]+8), fill=(55,235,125), outline=(2,20,29), width=3)
    draw.ellipse((destination[0]-8, destination[1]-8, destination[0]+8, destination[1]+8), fill=(255,75,75), outline=(2,20,29), width=3)
    draw.text((start[0]+11, start[1]+7), "START", fill="white", font=_font(12, bold=True), stroke_width=2, stroke_fill=(2,20,29))
    draw.text((destination[0]+11, destination[1]+7), "DESTINATION", fill="white", font=_font(12, bold=True), stroke_width=2, stroke_fill=(2,20,29))

    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()
