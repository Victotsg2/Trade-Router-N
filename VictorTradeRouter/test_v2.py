from __future__ import annotations

import unittest

import numpy as np

from diplomacy import diplomacy_warnings
from economy import calculate_trade, load_economy
from routing import _region_context, generate_world_route_candidates, world_navigation_samples
from wind import (
    WIND_DISCLAIMER,
    choose_wind_route,
    hud_arrow_to_world_wind,
    heading_bearing,
    load_handoff,
    modeled_speed_knots,
    sail_instruction,
    wind_toward_at_elapsed,
)


class NavalTradeV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.economy = load_economy()
        cls.local_candidates = generate_world_route_candidates("BEL", "BEL-P04", "BEL", "BEL-P02", max_candidates=4)

    def test_handoff_and_direction_only_rule(self):
        handoff = load_handoff()
        self.assertEqual(handoff["package"]["version"], "2.0")
        core = handoff["wind_model_v2"]["core_rule"]
        self.assertTrue(core["use_wind_direction_only"])
        self.assertTrue(core["ignore_storms_and_slow_wind_for_optimization"])
        self.assertIn("storms", WIND_DISCLAIMER)

    def test_hud_transform_and_clockwise_rotation(self):
        self.assertEqual(hud_arrow_to_world_wind(193, 90), 283)
        self.assertEqual(hud_arrow_to_world_wind(193, 90, arrow_represents_toward=False), 103)
        self.assertEqual(wind_toward_at_elapsed(350, 5), 20)

    def test_hoy_curve_uses_supplied_values(self):
        self.assertEqual(modeled_speed_knots("Hoy", 90, 0)["speed_knots"], 9.0)
        self.assertEqual(modeled_speed_knots("Hoy", 270, 0)["speed_knots"], 9.0)
        self.assertEqual(modeled_speed_knots("Hoy", 0, 0)["speed_knots"], 0.5)
        self.assertEqual(modeled_speed_knots("Hoy", 180, 0)["speed_knots"], 0.5)
        self.assertEqual(
            modeled_speed_knots("Hoy", 90, 0)["model_status"],
            "EMPIRICAL_PRELIMINARY_BEAM_REACH",
        )

    def test_been_and_pembroke_prefer_oblique_non_backed_wind(self):
        for ship, direct_speed, backed_speed, status in (
            ("Been", 8.5, 0.25, "PARTIAL_EMPIRICAL_OBLIQUE_HEURISTIC"),
            ("Pembroke", 8.6, 0.75, "PROXY_OBLIQUE_ASSUMED_FROM_BEEN"),
        ):
            direct = modeled_speed_knots(ship, 0, 0)
            oblique = modeled_speed_knots(ship, 15, 0)
            backed = modeled_speed_knots(ship, 180, 0)
            self.assertEqual(direct["speed_knots"], direct_speed)
            self.assertEqual(oblique["speed_knots"], 9.0)
            self.assertGreater(oblique["speed_knots"], direct["speed_knots"])
            self.assertEqual(oblique["relative_wind_deviation_deg"], 0.0)
            self.assertFalse(oblique["wind_is_backing"])
            self.assertEqual(backed["speed_knots"], backed_speed)
            self.assertTrue(backed["wind_is_backing"])
            self.assertEqual(oblique["model_status"], status)

    def test_hoy_favorable_same_region_route(self):
        first_leg = self.local_candidates[0].legs[0]
        route_heading = heading_bearing(first_leg.waypoints[0], first_leg.waypoints[1])
        beam_wind = (route_heading - 90.0) % 360.0
        plan = choose_wind_route(self.local_candidates, "Hoy", beam_wind)
        self.assertEqual(len(plan.route.region_sequence), 1)
        self.assertAlmostEqual(plan.segment_evaluations[0]["speed_knots"], 9.0, places=6)

    def test_manual_tax_override_is_separate(self):
        default = calculate_trade(self.economy, "Petit Anvers", "Port Royal", "Hoy")
        manual = calculate_trade(self.economy, "Petit Anvers", "Port Royal", "Hoy", 1, 2)
        self.assertEqual(default["tax_mode"], "Default")
        self.assertEqual(manual["tax_mode"], "Manual")
        self.assertEqual(manual["origin_export_tax_percent"], 1)
        self.assertEqual(manual["destination_import_tax_percent"], 2)
        self.assertNotEqual(default["total_profit_gbp"], manual["total_profit_gbp"])

    def test_poor_wind_adds_only_safe_tacks(self):
        plan = choose_wind_route(self.local_candidates, "Hoy", 135, pixels_per_nautical_mile=100)
        self.assertGreater(len(plan.tack_points), 0)
        for leg in plan.route.legs:
            _, _, nav, obstacles, _, _, _ = _region_context(leg.region_id)
            self.assertTrue(all(nav[y, x] and not obstacles[y, x] for x, y in leg.route_pixels))

    def test_been_and_pembroke_sail_controls(self):
        been = sail_instruction("Been", True, 0.5).lower()
        pembroke = sail_instruction("Pembroke", True, 0.5).lower()
        self.assertIn("shiver", been)
        self.assertIn("topsail", been)
        self.assertIn("fore/main/mizzen", pembroke)
        self.assertNotIn("spanker", pembroke)

    def test_wind_rotation_changes_during_calibrated_route(self):
        plan = choose_wind_route(self.local_candidates, "Been", 30, pixels_per_nautical_mile=100)
        winds = [row["wind_toward_deg"] for row in plan.segment_evaluations]
        self.assertIsNotNone(plan.eta_minutes)
        self.assertGreater(len(winds), 1)
        self.assertTrue(any(abs(wind - winds[0]) > 1 for wind in winds[1:]))

    def test_current_position_can_replace_navigation_start(self):
        _, _, _, _, _, _, strict = _region_context("BEL")
        y, x = np.argwhere(strict)[len(np.argwhere(strict)) // 2]
        candidates = generate_world_route_candidates(
            "BEL", "BEL-P04", "BEL", "BEL-P02",
            navigation_start_region_id="BEL",
            navigation_start_point=(int(x), int(y)),
            navigation_start_name="Current ship position",
            max_candidates=2,
        )
        self.assertEqual(candidates[0].navigation_start_name, "Current ship position")
        self.assertEqual(candidates[0].legs[0].waypoints[0], (int(x), int(y)))

    def test_world_map_has_clickable_owned_water(self):
        samples = world_navigation_samples(48)
        self.assertGreater(len(samples), 100)
        self.assertTrue(all(len(row) == 5 for row in samples))

    def test_enemy_warning_is_per_port_and_nonblocking(self):
        ownership = {"ports": {"Petit Anvers": "Marine Impériale", "Port Royal": "Royal Navy"}}
        warnings = diplomacy_warnings(self.economy, ownership, "Petit Anvers", "Port Royal", ["Belle Isles", "Kingston"], ["Royal Navy"])
        self.assertTrue(any("Destination" in warning for warning in warnings))
        self.assertFalse(diplomacy_warnings(self.economy, ownership, "Petit Anvers", "Port Royal", ["Belle Isles"], []))

    def test_been_can_choose_longer_wind_favored_tp_corridor(self):
        candidates = generate_world_route_candidates("VYS", "VYS-P01", "STP", "STP-P01", max_candidates=4)
        # Full-voyage rotating-wind comparison requires an explicit map scale.
        # This is a regression fixture, not a claimed game calibration.
        plan = choose_wind_route(candidates, "Been", 0, pixels_per_nautical_mile=25)
        self.assertGreater(len(candidates), 1)
        self.assertEqual(plan.route_choice, "wind_favored_tp_corridor")
        self.assertGreater(plan.route.total_distance_px, candidates[0].total_distance_px)
        baseline = next(row for row in plan.candidate_summaries if row["corridor_index"] == 0 and row["strategy"] == "direct_progress")
        selected = next(row for row in plan.candidate_summaries if row["selected"])
        self.assertLess(selected["eta_minutes"], baseline["eta_minutes"])

    def test_long_cross_region_route_rotates_wind(self):
        candidates = generate_world_route_candidates("SSA", "SSA-P01", "ILB", "ILB-P01", max_candidates=4)
        plan = choose_wind_route(candidates, "Hoy", 90, pixels_per_nautical_mile=100)
        winds = [row["wind_toward_deg"] for row in plan.segment_evaluations]
        self.assertGreaterEqual(len(plan.route.region_sequence), 3)
        self.assertIsNotNone(plan.eta_minutes)
        self.assertTrue(any(abs(wind - winds[0]) > 10 for wind in winds[1:]))

    def test_route_can_remain_quiet_when_no_condition_is_material(self):
        candidates = generate_world_route_candidates("SPO", "SPO-P01", "SPO", "SPO-P04", max_candidates=2)
        plan = choose_wind_route(candidates, "Pembroke", 185)
        self.assertEqual(plan.warnings, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
