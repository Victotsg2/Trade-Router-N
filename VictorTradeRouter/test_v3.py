from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from routing import (
    RouteDiagnosticError,
    _reachable_navigation_water,
    _region_context,
    _transition_catalog,
    audit_port_navigation_anchors,
    generate_world_route_candidates,
    load_regions,
    resolve_current_position,
)
from wind import choose_wind_route, setup_wind_for_target, wind_toward_at_elapsed


class NavalTradeV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.louisbourg_to_griffard = generate_world_route_candidates(
            "BEL", "BEL-P02", "GRF", "GRF-P01", max_candidates=8
        )
        cls.louisbourg_to_port_royal = generate_world_route_candidates(
            "BEL", "BEL-P02", "KIN", "KIN-P01", max_candidates=8
        )

    def test_all_stage1_ports_have_reachable_navigation_anchors(self):
        audit = audit_port_navigation_anchors()
        self.assertEqual(len(audit), 57)
        self.assertTrue(all(row["port_navigation_anchor"] for row in audit))

    def test_four_blocked_semantic_ports_use_reviewed_harbor_water(self):
        audit = {row["port_id"]: row for row in audit_port_navigation_anchors()}
        expected = {
            "IDL-P04": [769, 272],
            "ESO-P03": [439, 347],
            "LEB-P01": [952, 376],
            "GRF-P01": [338, 359],
        }
        for port_id, point in expected.items():
            self.assertEqual(audit[port_id]["port_navigation_anchor"], point)
            self.assertNotEqual(audit[port_id]["port_semantic_point"], point)

    def test_every_tp_pair_has_reachable_candidate_points(self):
        catalog, _ = _transition_catalog()
        self.assertGreater(len(catalog), 0)
        for tp_id, info in catalog.items():
            self.assertGreater(len(info["candidates"]), 0, tp_id)
            for entry, exit_point in info["candidates"]:
                entry_water = _reachable_navigation_water(entry.region_id)
                exit_water = _reachable_navigation_water(exit_point.region_id)
                self.assertTrue(entry_water[entry.point[1], entry.point[0]], tp_id)
                self.assertTrue(exit_water[exit_point.point[1], exit_point.point[0]], tp_id)

    def test_region_tp_graph_is_fully_connected(self):
        catalog, _ = _transition_catalog()
        graph = {row["region_id"]: set() for row in load_regions()}
        for info in catalog.values():
            for entry, exit_point in info["candidates"][:1]:
                graph[entry.region_id].add(exit_point.region_id)
        for start in graph:
            reached = {start}
            stack = [start]
            while stack:
                stack.extend(graph[stack.pop()] - reached)
                reached.update(stack)
            self.assertEqual(reached, set(graph), start)

    def test_louisbourg_to_griffard_uses_nearby_water_and_routes(self):
        route = self.louisbourg_to_griffard[0]
        self.assertTrue(route.collision_free)
        self.assertTrue(route.clearance_respected)
        griffard = next(row for row in route.anchor_resolutions if row["port_id"] == "GRF-P01")
        self.assertEqual(griffard["port_semantic_point"], [402, 382])
        self.assertEqual(griffard["port_navigation_anchor"], [338, 359])

    def test_current_position_just_on_shore_snaps_to_connected_water(self):
        _, _, nav, _, _, _, _ = _region_context("BEL")
        reachable = _reachable_navigation_water("BEL")
        seed = None
        height, width = nav.shape
        for y, x in np.argwhere(reachable):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = int(x + dx), int(y + dy)
                if 0 <= nx < width and 0 <= ny < height and not nav[ny, nx]:
                    seed = (nx, ny)
                    break
            if seed:
                break
        self.assertIsNotNone(seed)
        point, diagnostic = resolve_current_position("BEL", seed)
        self.assertTrue(reachable[point[1], point[0]])
        self.assertEqual(diagnostic["code"], "CURRENT_POSITION_SAFE_SNAP")

    def test_invalid_current_position_has_specific_diagnostic(self):
        with self.assertRaises(RouteDiagnosticError) as caught:
            resolve_current_position("BEL", (-1, -1))
        self.assertEqual(caught.exception.code, "CURRENT_POSITION_INVALID")

    def test_louisbourg_port_royal_compares_full_voyage_strategies(self):
        # The scale and wind below are deterministic regression inputs only.
        # They are not presented as verified game calibration.
        plan = choose_wind_route(
            self.louisbourg_to_port_royal,
            "Hoy",
            setup_wind_for_target(0),
            pixels_per_nautical_mile=100,
        )
        strategies = {row["strategy"] for row in plan.candidate_summaries}
        self.assertTrue({"direct_progress", "immediate_wind", "delayed_tack_6m", "delayed_tack_12m", "delayed_tack_18m"}.issubset(strategies))
        selected = next(row for row in plan.candidate_summaries if row["selected"])
        self.assertAlmostEqual(selected["eta_minutes"], min(row["eta_minutes"] for row in plan.candidate_summaries), delta=0.25)
        if plan.route.total_distance_px > self.louisbourg_to_port_royal[0].total_distance_px:
            baseline = next(row for row in plan.candidate_summaries if row["corridor_index"] == 0 and row["strategy"] == "direct_progress")
            self.assertLess(selected["eta_minutes"], baseline["eta_minutes"])

    def test_wind_still_rotates_clockwise_six_degrees_per_minute(self):
        self.assertEqual(wind_toward_at_elapsed(350, 5), 20)

    def test_ui_has_clear_endpoint_states_and_eight_point_compass(self):
        source = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
        for text in ("SELECT ORIGIN", "SELECT DESTINATION", "SELECTION READY", "ORIGIN", "DESTINATION"):
            self.assertIn(text, source)
        for direction in ("N", "NE", "E", "SE", "S", "SW", "W", "NW"):
            self.assertIn(f'(\"{direction}\",', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
